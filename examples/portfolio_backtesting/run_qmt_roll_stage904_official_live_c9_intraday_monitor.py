from __future__ import annotations

import argparse
import fcntl
import hashlib
import io
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from qmt_roll_official_live_c9_intraday_state import (
    ATTEMPT_INITIAL,
    ATTEMPT_RETRY,
    INITIAL_STOP_ACTION_ROLE,
    PHASE_DONE,
    PHASE_INITIAL_ARMED,
    PHASE_INITIAL_PROGRESS_LATCHED,
    PHASE_INITIAL_STOP_LATCHED,
    PHASE_RETRY_OPEN,
    PHASE_RETRY_RECLAIM_LATCHED,
    PHASE_RETRY_STOP_LATCHED,
    PHASE_RETRY_WAIT,
    RETRY_OPEN_ACTION_ROLE,
    RETRY_STOP_ACTION_ROLE,
    arm_retry_after_close,
    consume_ticks,
    generate_position_epoch_id,
    generate_root_position_id,
    get_pending_action,
    loads_state,
    mark_feed_gap,
    mark_position_flat,
    mark_retry_filled,
    new_state,
    update_current_position_volume,
)
from qmt_roll_official_live_execution_ledger import (
    append_execution_ledger_event,
    append_reconciled_execution_fill_once,
    latest_position_cycle_open_fill,
    read_execution_ledger,
    weighted_open_fill,
)
from qmt_roll_official_live_late_retry_fill import (
    MAX_CLOCK_SKEW_SECONDS,
    build_late_retry_fill_reconciliation,
    validate_readonly_query_bundle,
)
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CURRENT_POSITIONS_PATH,
    OFFICIAL_LIVE_SUMMARY_PATH,
    OFFICIAL_LIVE_VERSION,
)
from qmt_roll_official_live_phase_d_config import (
    LIVE_EXECUTION_LEDGER_PATH,
    READONLY_ORDERS_PATH,
    READONLY_SUMMARY_PATH,
    READONLY_QUERY_BUNDLE_MANIFEST_PATH,
    READONLY_POSITIONS_PATH,
    READONLY_TRADES_PATH,
    READONLY_TICKS_PATH,
    STAGE901_ENTRY_RISK_PATH,
    STAGE901_TRADES_PATH,
    build_phase_d_config,
)
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage904_official_live_c9_intraday_monitor_v1"
OUTPUT_PREFIX = "qmt_roll_stage904_official_live_c9_intraday_monitor"
STOP_RETRY_R = 0.5
RETRY_INTENT_ROLE = "c9_retry_open_once"
INITIAL_OPEN_INTENT_ROLE = "c9_initial_open"
STATE_SCHEMA_VERSION = 1
STATE_JOURNAL_SCHEMA_VERSION = 1
ALLOWED_TICK_CLOCK_SKEW_SECONDS = 2.0
DEFAULT_STATE_TICK_MAX_AGE_SECONDS = 30
TICK_SNAPSHOT_COMMIT_SCHEMA_VERSION = 1
TICK_SNAPSHOT_STABLE_READ_ATTEMPTS = 3
TICK_SNAPSHOT_STABLE_READ_RETRY_SECONDS = 0.05
TICK_STREAM_HEARTBEAT_PATH = OUTPUT_DIR / (
    "qmt_roll_stage608_readonly_tick_snapshot_probe_tick_stream_heartbeat_"
    "stage608_readonly_tick_snapshot_probe_v1.json"
)
RETRY_OPEN_CONSUMING_LEDGER_EVENTS = {
    "send_order_called",
    "send_order_returned_empty",
    "submitted_to_ctp",
    "filled_or_part_filled",
    "rejected_or_inactive",
    "unknown_order_status_after_send",
    "residual_order_active_after_cancel",
    "residual_order_unknown_after_cancel",
    "cancel_order_called",
}
CLOSE_VOLUME_RECONCILED_EVENT = "close_volume_reconciled_without_trade_detail"
CLOSE_VOLUME_LEDGER_EVENTS = {
    "filled_or_part_filled",
    CLOSE_VOLUME_RECONCILED_EVENT,
}
CLOSE_UNPRICED_EVIDENCE_EVENTS = {
    "order_traded_volume_observed_without_trade_detail",
    "fill_reconciliation_pending",
}
CLOSE_RESIDUAL_BLOCKER_EVENTS = {
    "adapter_exception_after_reserve",
    "residual_order_active_after_cancel",
    "residual_order_unknown_after_cancel",
    "unknown_order_status_after_send",
}
BROKER_ALL_TRADED_STATUSES = {
    "0",
    "all traded",
    "alltraded",
    "filled",
    "status.alltraded",
    "全部成交",
    "已成交",
}
BROKER_TERMINAL_ORDER_STATUSES = BROKER_ALL_TRADED_STATUSES.union(
    {
        "2",
        "4",
        "5",
        "cancelled",
        "canceled",
        "rejected",
        "status.cancelled",
        "status.canceled",
        "status.rejected",
        "已撤单",
        "已撤销",
        "撤单",
        "拒单",
        "已拒绝",
        "废单",
    }
)


def _paths(target_date: str) -> dict[str, Path]:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return {
        "actions_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_actions_{date_key}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{date_key}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{date_key}_{MODEL_TAG}.md",
        "state_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_{date_key}_{MODEL_TAG}.json",
        "state_journal": OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_transitions_{date_key}_{MODEL_TAG}.ndjson",
        "state_lock": OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_{date_key}_{MODEL_TAG}.lock",
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _read_csv_maybe(
    path: str | Path | None, *, preserve_identity: bool = False
) -> pd.DataFrame:
    if not path:
        return pd.DataFrame()
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    try:
        dtype = (
            {
                "broker_id": "string",
                "account_id": "string",
                "query_generation_uuid": "string",
                "order_sys_id": "string",
                "vt_orderid": "string",
                "vt_tradeid": "string",
                "broker_trade_identity": "string",
            }
            if preserve_identity
            else None
        )
        return pd.read_csv(p, encoding="utf-8-sig", dtype=dtype)
    except EmptyDataError:
        return pd.DataFrame()


def _validated_tick_snapshot_commit(
    heartbeat: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    if not isinstance(heartbeat, dict) or heartbeat.get("_read_error"):
        return {}, "heartbeat_unreadable"
    commit = heartbeat.get("tick_snapshot_commit")
    if not isinstance(commit, dict):
        return {}, "tick_snapshot_commit_missing"
    try:
        schema_version = int(commit.get("schema_version", -1))
        row_count = int(commit.get("row_count", -1))
        stream_sequence = int(commit.get("stream_sequence", -1))
        heartbeat_sequence = int(heartbeat.get("stream_sequence", -1))
        buffered_tick_count = int(heartbeat.get("buffered_tick_count", -1))
    except (TypeError, ValueError):
        return {}, "tick_snapshot_commit_numeric_field_invalid"
    if schema_version != TICK_SNAPSHOT_COMMIT_SCHEMA_VERSION:
        return {}, f"tick_snapshot_commit_schema_invalid:{schema_version}"
    generation_uuid = _clean(commit.get("generation_uuid"))
    try:
        parsed_generation = str(uuid.UUID(generation_uuid))
    except (ValueError, AttributeError):
        return {}, "tick_snapshot_commit_generation_invalid"
    if parsed_generation != generation_uuid:
        return {}, "tick_snapshot_commit_generation_noncanonical"
    digest = _clean(commit.get("sha256")).lower()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        return {}, "tick_snapshot_commit_sha256_invalid"
    feed_session_id = _clean(commit.get("feed_session_id"))
    if not feed_session_id:
        return {}, "tick_snapshot_commit_feed_session_missing"
    if row_count < 0 or stream_sequence < 0:
        return {}, "tick_snapshot_commit_count_invalid"
    if _clean(heartbeat.get("tick_snapshot_generation_uuid")) != generation_uuid:
        return {}, "tick_snapshot_commit_generation_mismatch"
    if _clean(heartbeat.get("heartbeat_revision_uuid")) != generation_uuid:
        return {}, "tick_snapshot_heartbeat_revision_mismatch"
    if _clean(heartbeat.get("feed_session_id")) != feed_session_id:
        return {}, "tick_snapshot_commit_feed_session_mismatch"
    if heartbeat_sequence != stream_sequence:
        return {}, "tick_snapshot_commit_stream_sequence_mismatch"
    if buffered_tick_count != row_count:
        return {}, "tick_snapshot_commit_row_count_mismatch"
    return {
        "schema_version": schema_version,
        "generation_uuid": generation_uuid,
        "sha256": digest,
        "row_count": row_count,
        "feed_session_id": feed_session_id,
        "stream_sequence": stream_sequence,
    }, ""


def _read_committed_tick_snapshot(
    tick_path: Path,
    heartbeat_path: Path,
    *,
    attempts: int = TICK_SNAPSHOT_STABLE_READ_ATTEMPTS,
    retry_seconds: float = TICK_SNAPSHOT_STABLE_READ_RETRY_SECONDS,
) -> tuple[pd.DataFrame, dict[str, Any], str]:
    """Read one stable Stage608 two-file commit without latching feed state.

    The publisher's atomic renames make each file whole, but not mutually
    atomic.  Reading heartbeat-before / exact tick bytes / heartbeat-after
    proves both artifacts belong to one generation.  A publication race is a
    transient cycle blocker, not evidence that market ticks were lost.
    """

    total_attempts = max(1, int(attempts))
    latest_heartbeat: dict[str, Any] = {}
    last_error = "tick_snapshot_commit_not_read"
    for attempt in range(total_attempts):
        heartbeat_before = _read_json(heartbeat_path)
        latest_heartbeat = heartbeat_before
        commit_before, commit_error = _validated_tick_snapshot_commit(
            heartbeat_before
        )
        if commit_error:
            last_error = commit_error
        else:
            try:
                tick_bytes = tick_path.read_bytes()
            except OSError as exc:
                last_error = f"tick_snapshot_bytes_unreadable:{type(exc).__name__}"
            else:
                heartbeat_after = _read_json(heartbeat_path)
                latest_heartbeat = heartbeat_after
                commit_after, after_error = _validated_tick_snapshot_commit(
                    heartbeat_after
                )
                if after_error:
                    last_error = after_error
                elif commit_before != commit_after:
                    last_error = (
                        "tick_snapshot_commit_changed_during_read:"
                        f"before={commit_before.get('generation_uuid', '')};"
                        f"after={commit_after.get('generation_uuid', '')}"
                    )
                elif heartbeat_before != heartbeat_after:
                    # Stage904 consumes readiness, watermarks, subscription
                    # times and commit metadata from the heartbeat.  A writer
                    # that mutates any of those fields between H1 and H2 must
                    # make this invocation transiently fail closed even when
                    # it accidentally preserves the old commit object.
                    last_error = (
                        "tick_snapshot_heartbeat_changed_during_read:"
                        f"generation={commit_after.get('generation_uuid', '')}"
                    )
                else:
                    actual_digest = hashlib.sha256(tick_bytes).hexdigest()
                    if actual_digest != commit_after["sha256"]:
                        last_error = (
                            "tick_snapshot_sha256_mismatch:"
                            f"generation={commit_after['generation_uuid']}"
                        )
                    else:
                        frame: pd.DataFrame | None = None
                        try:
                            frame = pd.read_csv(
                                io.BytesIO(tick_bytes), encoding="utf-8-sig"
                            )
                        except EmptyDataError:
                            frame = pd.DataFrame()
                        except Exception as exc:
                            last_error = (
                                "tick_snapshot_csv_invalid:"
                                f"{type(exc).__name__}:{exc}"
                            )
                        if frame is not None:
                            if len(frame) != commit_after["row_count"]:
                                last_error = (
                                    "tick_snapshot_parsed_row_count_mismatch:"
                                    f"commit={commit_after['row_count']};"
                                    f"parsed={len(frame)}"
                                )
                            else:
                                return frame, heartbeat_after, ""
        if attempt + 1 < total_attempts and retry_seconds > 0:
            time.sleep(float(retry_seconds))
    return (
        pd.DataFrame(),
        latest_heartbeat,
        f"tick_snapshot_commit_unstable_after_{total_attempts}_attempts:{last_error}",
    )


def _sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _broker_account_fingerprint(broker_id: Any, account_id: Any) -> str:
    broker = _clean(broker_id)
    account = _clean(account_id)
    if not broker or not account:
        return ""
    return hashlib.sha256(f"{broker}\0{account}".encode("utf-8")).hexdigest()


def _bundle_frame_evidence(
    frame: pd.DataFrame,
    *,
    path: Path,
    include_query_identity: bool,
) -> dict[str, Any]:
    rows = frame.drop_duplicates().to_dict(orient="records")
    evidence: dict[str, Any] = {
        "row_count": len(rows),
        "sha256": _sha256_file(path),
    }
    if include_query_identity:
        evidence["generation_uuids"] = list(
            dict.fromkeys(
                _clean(row.get("query_generation_uuid"))
                for row in rows
                if _clean(row.get("query_generation_uuid"))
            )
        )
        evidence["account_fingerprints"] = list(
            dict.fromkeys(
                fingerprint
                for row in rows
                if (
                    fingerprint := _broker_account_fingerprint(
                        row.get("broker_id"), row.get("account_id")
                    )
                )
            )
        )
    return evidence


def _build_readonly_query_bundle_evidence(
    *,
    broker_orders: pd.DataFrame,
    broker_trades: pd.DataFrame,
    broker_positions: pd.DataFrame,
) -> dict[str, Any]:
    orders = _bundle_frame_evidence(
        broker_orders,
        path=READONLY_ORDERS_PATH,
        include_query_identity=True,
    )
    trades = _bundle_frame_evidence(
        broker_trades,
        path=READONLY_TRADES_PATH,
        include_query_identity=True,
    )
    positions = _bundle_frame_evidence(
        broker_positions,
        path=READONLY_POSITIONS_PATH,
        include_query_identity=True,
    )
    trade_rows = broker_trades.drop_duplicates().to_dict(orient="records")
    trades["order_mapping_complete"] = all(
        int(_to_float(row.get("order_mapping_complete"), 0.0)) == 1
        and bool(_clean(row.get("vt_orderid")))
        for row in trade_rows
    )
    trades["stable_trade_identity_complete"] = all(
        int(_to_float(row.get("stable_trade_identity_complete"), 0.0)) == 1
        and bool(_clean(row.get("broker_trade_identity")))
        for row in trade_rows
    )
    return {"artifacts": {"orders": orders, "trades": trades, "positions": positions}}


def _fsync_parent(path: Path) -> None:
    try:
        directory_fd = os.open(str(path.parent), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _atomic_write_text(path: Path, text: str, *, durable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(text)
        if durable:
            handle.flush()
            os.fsync(handle.fileno())
    os.replace(temporary, path)
    if durable:
        _fsync_parent(path)


def _atomic_write_df(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    frame.to_csv(temporary, index=False, encoding="utf-8-sig")
    os.replace(temporary, path)


def _new_state_store(target_date: str) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "target_date": target_date,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "states": {},
    }


def _canonical_json(payload: Any) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _journal_record_checksum(payload_without_checksum: dict[str, Any]) -> str:
    return hashlib.sha256(
        _canonical_json(payload_without_checksum).encode("utf-8")
    ).hexdigest()


def _validated_state_store(path: Path, target_date: str) -> dict[str, Any]:
    if not path.exists():
        return _new_state_store(target_date)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("state_store_not_object")
    if int(payload.get("schema_version", -1)) != STATE_SCHEMA_VERSION:
        raise ValueError("state_store_schema_mismatch")
    if _clean(payload.get("target_date")) != target_date:
        raise ValueError("state_store_target_date_mismatch")
    states = payload.get("states")
    if not isinstance(states, dict):
        raise ValueError("state_store_states_not_object")
    for root_position_id, state in states.items():
        if not isinstance(state, dict) or _clean(state.get("root_position_id")) != _clean(root_position_id):
            raise ValueError(f"state_store_invalid_identity:{root_position_id}")
        states[root_position_id] = loads_state(json.dumps(state, ensure_ascii=False, default=str))
    return payload


def _replay_state_journal(
    store: dict[str, Any],
    journal_path: Path,
    target_date: str,
) -> dict[str, Any]:
    """Replay fsynced full-state WAL records newer than the atomic snapshot.

    Every line is validated, including records already reflected by the state
    snapshot.  A damaged tail or a broken per-root revision chain therefore
    fails closed instead of silently falling back to an older risk state.
    """

    if not journal_path.exists():
        return store
    raw_text = journal_path.read_text(encoding="utf-8")
    if raw_text and not raw_text.endswith("\n"):
        raise ValueError("state_journal_truncated_tail")
    states = store.setdefault("states", {})
    groups_by_root: dict[str, list[dict[str, Any]]] = {}
    for line_no, line in enumerate(raw_text.splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"state_journal_blank_record:line={line_no}")
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"state_journal_invalid_json:line={line_no}:{exc}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"state_journal_record_not_object:line={line_no}")
        checksum = _clean(record.get("checksum"))
        unsigned = {key: value for key, value in record.items() if key != "checksum"}
        if not checksum or checksum != _journal_record_checksum(unsigned):
            raise ValueError(f"state_journal_checksum_mismatch:line={line_no}")
        if int(record.get("journal_schema_version", -1)) != STATE_JOURNAL_SCHEMA_VERSION:
            raise ValueError(f"state_journal_schema_mismatch:line={line_no}")
        if _clean(record.get("target_date")) != target_date:
            raise ValueError(f"state_journal_target_date_mismatch:line={line_no}")
        root_position_id = _clean(record.get("root_position_id"))
        position_epoch_id = _clean(record.get("position_epoch_id"))
        state_payload = record.get("state")
        if (
            not root_position_id
            or not position_epoch_id
            or not isinstance(state_payload, dict)
        ):
            raise ValueError(f"state_journal_identity_or_state_missing:line={line_no}")
        if _clean(state_payload.get("root_position_id")) != root_position_id:
            raise ValueError(f"state_journal_root_identity_mismatch:line={line_no}")
        if _clean(state_payload.get("position_epoch_id")) != position_epoch_id:
            raise ValueError(f"state_journal_epoch_identity_mismatch:line={line_no}")
        if _clean(state_payload.get("target_date")) != target_date:
            raise ValueError(f"state_journal_state_target_date_mismatch:line={line_no}")
        previous_revision = int(record.get("previous_revision", -1))
        revision = int(record.get("revision", -1))
        if previous_revision < 0 or revision <= previous_revision:
            raise ValueError(f"state_journal_invalid_revision:line={line_no}")
        if int(state_payload.get("revision", -1)) != revision:
            raise ValueError(f"state_journal_state_revision_mismatch:line={line_no}")
        recovered = loads_state(
            json.dumps(state_payload, ensure_ascii=False, default=str)
        )
        root_groups = groups_by_root.setdefault(root_position_id, [])
        current_group = root_groups[-1] if root_groups else None
        if current_group is None or current_group["position_epoch_id"] != position_epoch_id:
            if any(
                group["position_epoch_id"] == position_epoch_id
                for group in root_groups
            ):
                raise ValueError(
                    "state_journal_epoch_order_regressed:"
                    f"line={line_no};epoch={position_epoch_id}"
                )
            if current_group is not None:
                if _clean(current_group["last_state"].get("phase")) != PHASE_DONE:
                    raise ValueError(
                        "state_journal_nonterminal_epoch_rollover:"
                        f"line={line_no};old_epoch={current_group['position_epoch_id']};"
                        f"new_epoch={position_epoch_id}"
                    )
                if previous_revision != 0:
                    raise ValueError(
                        "state_journal_new_epoch_must_start_at_revision_zero:"
                        f"line={line_no};previous={previous_revision}"
                    )
            current_group = {
                "position_epoch_id": position_epoch_id,
                "records": [],
                "last_revision": None,
                "last_state": None,
            }
            root_groups.append(current_group)
        prior_epoch_revision = current_group["last_revision"]
        if (
            prior_epoch_revision is not None
            and previous_revision != prior_epoch_revision
        ):
            raise ValueError(
                "state_journal_revision_chain_gap:"
                f"line={line_no};root={root_position_id};epoch={position_epoch_id};"
                f"expected={prior_epoch_revision};actual={previous_revision}"
            )
        current_group["records"].append(
            {
                "line_no": line_no,
                "previous_revision": previous_revision,
                "revision": revision,
                "state": recovered,
            }
        )
        current_group["last_revision"] = revision
        current_group["last_state"] = recovered

    for root_position_id, root_groups in groups_by_root.items():
        snapshot = states.get(root_position_id)
        if snapshot is None:
            first_record = root_groups[0]["records"][0]
            if int(first_record["previous_revision"]) != 0:
                raise ValueError(
                    "state_journal_replay_revision_gap:"
                    f"root={root_position_id};store=missing;"
                    f"previous={first_record['previous_revision']}"
                )
            states[root_position_id] = root_groups[-1]["last_state"]
            continue

        snapshot_epoch_id = _clean(snapshot.get("position_epoch_id"))
        snapshot_revision = int(snapshot.get("revision", 0))
        matching_indexes = [
            index
            for index, group in enumerate(root_groups)
            if group["position_epoch_id"] == snapshot_epoch_id
        ]
        if not matching_indexes:
            latest_journal_state = root_groups[-1]["last_state"]
            if (
                _clean(latest_journal_state.get("phase")) == PHASE_DONE
                and snapshot_revision == 0
                and _clean(snapshot.get("phase")) != PHASE_DONE
            ):
                # The atomic snapshot can contain a just-created next epoch
                # before that epoch has a revisioned transition to journal.
                # A terminal final journal epoch plus revision-0 snapshot is
                # the only unambiguous ordering proof in this case.
                continue
            raise ValueError(
                "state_store_journal_epoch_order_unproven:"
                f"root={root_position_id};snapshot_epoch={snapshot_epoch_id};"
                f"journal_epochs={[group['position_epoch_id'] for group in root_groups]}"
            )

        group_index = matching_indexes[0]
        group = root_groups[group_index]
        exact_record = next(
            (
                record
                for record in group["records"]
                if int(record["revision"]) == snapshot_revision
            ),
            None,
        )
        seed_record = next(
            (
                record
                for record in group["records"]
                if int(record["previous_revision"]) == snapshot_revision
            ),
            None,
        )
        if exact_record is not None:
            if _canonical_json(snapshot) != _canonical_json(exact_record["state"]):
                raise ValueError(
                    "state_store_journal_divergence:"
                    f"line={exact_record['line_no']};root={root_position_id};"
                    f"epoch={snapshot_epoch_id};revision={snapshot_revision}"
                )
        elif seed_record is None:
            raise ValueError(
                "state_journal_replay_revision_gap:"
                f"root={root_position_id};epoch={snapshot_epoch_id};"
                f"store={snapshot_revision};"
                f"journal_revisions={[record['revision'] for record in group['records']]}"
            )
        states[root_position_id] = root_groups[-1]["last_state"]
    return store


def _load_state_store(
    path: Path,
    target_date: str,
    *,
    journal_path: Path | None = None,
) -> dict[str, Any]:
    store = _validated_state_store(path, target_date)
    if journal_path is not None:
        store = _replay_state_journal(store, journal_path, target_date)
    return store


def _save_state_store(path: Path, store: dict[str, Any]) -> None:
    payload = dict(store)
    payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str),
        durable=True,
    )


def _checkpoint_state_journal(path: Path) -> None:
    """Atomically replace a WAL already covered by a durable state snapshot.

    Production callers hold the Stage904 state lock across the snapshot write
    and this checkpoint.  A crash before the snapshot is durable leaves the
    old WAL; a crash afterwards may leave either the old WAL or an empty WAL,
    both of which recover to the same committed state.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.checkpoint.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    _fsync_parent(path)


def _commit_state_store_and_checkpoint(
    state_path: Path,
    journal_path: Path,
    store: dict[str, Any],
) -> None:
    """Durably commit the snapshot, then bound future WAL replay to zero."""

    _save_state_store(state_path, store)
    _checkpoint_state_journal(journal_path)


def _append_state_journal(path: Path, *, previous_revision: int, state: dict[str, Any]) -> None:
    revision = int(state.get("revision", 0))
    if revision == int(previous_revision):
        return
    if revision < int(previous_revision):
        raise ValueError(
            f"state_journal_revision_regressed:{revision}<{int(previous_revision)}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "journal_schema_version": STATE_JOURNAL_SCHEMA_VERSION,
        "recorded_at": datetime.now().isoformat(timespec="microseconds"),
        "target_date": state.get("target_date"),
        "root_position_id": state.get("root_position_id"),
        "position_epoch_id": state.get("position_epoch_id"),
        "previous_revision": int(previous_revision),
        "revision": revision,
        "state": json.loads(_canonical_json(state)),
    }
    payload["checksum"] = _journal_record_checksum(payload)
    with path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.write(_canonical_json(payload) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    _fsync_parent(path)


def _ordered_stream_ticks(ticks: pd.DataFrame, vt_symbol: str) -> tuple[list[dict[str, Any]], list[str]]:
    frame = _tick_frame(ticks, vt_symbol)
    if frame.empty:
        return [], ["continuous_tick_rows_missing"]
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, raw in enumerate(frame.to_dict(orient="records"), start=1):
        received_at = _clean(
            raw.get("received_at")
            or raw.get("localtime")
            or raw.get("datetime")
            or raw.get("snapshot_at")
        )
        feed_session_id = _clean(raw.get("feed_session_id"))
        seq_value = raw.get("symbol_stream_sequence")
        if not _clean(seq_value):
            seq_value = raw.get("stream_sequence", raw.get("seq"))
        seq = pd.to_numeric(seq_value, errors="coerce")
        seq_number = float(seq) if not pd.isna(seq) else float("nan")
        if (
            not received_at
            or not feed_session_id
            or pd.isna(seq)
            or seq_number < 0
            or not seq_number.is_integer()
        ):
            errors.append(f"tick_missing_continuous_identity:row={index}")
            continue
        rows.append(
            {
                **raw,
                "received_at": received_at,
                "feed_session_id": feed_session_id,
                "seq": int(seq),
                "vt_symbol": vt_symbol,
            }
        )
    return rows, list(dict.fromkeys(errors))


def _preconsume_tick_gap_reason(
    state: dict[str, Any],
    stream_ticks: list[dict[str, Any]],
) -> str:
    """Validate every unconsumed event before any irreversible transition.

    The heartbeat watermark only proves the newest event.  An older future or
    clock-regressing event in the same buffered batch must latch a feed gap
    before the reducer sees a favorable price; otherwise it could permanently
    waive an initial stop before a later normal watermark exposes the clock
    defect.
    """

    last_seq_by_feed = {
        _clean(feed): int(seq)
        for feed, seq in (state.get("last_seq_by_feed") or {}).items()
        if _clean(feed)
    }
    last_received_by_feed: dict[str, str] = {}
    last_key = state.get("last_tick_order_key")
    if isinstance(last_key, list) and len(last_key) == 3:
        last_received = _clean(last_key[0])
        last_feed = _clean(last_key[1])
        if last_received and last_feed:
            last_received_by_feed[last_feed] = last_received

    ordered = sorted(
        stream_ticks,
        key=lambda row: (_clean(row.get("feed_session_id")), int(row.get("seq", -1))),
    )
    for row in ordered:
        feed_session_id = _clean(row.get("feed_session_id"))
        seq = int(row.get("seq", -1))
        previous_seq = last_seq_by_feed.get(feed_session_id)
        if previous_seq is not None and seq <= previous_seq:
            continue
        received_at = _clean(row.get("received_at"))
        if _parse_dt(received_at) is None:
            return (
                "tick_received_at_invalid_before_consume:"
                f"feed={feed_session_id};seq={seq};value={received_at!r}"
            )
        age = _age_seconds(received_at)
        if age is None:
            return f"tick_received_at_invalid_before_consume:feed={feed_session_id};seq={seq}"
        if age < -ALLOWED_TICK_CLOCK_SKEW_SECONDS:
            return (
                "tick_from_future_before_consume:"
                f"feed={feed_session_id};seq={seq};age={age};"
                f"allowed_skew={ALLOWED_TICK_CLOCK_SKEW_SECONDS}"
            )
        previous_received_at = last_received_by_feed.get(feed_session_id)
        if previous_received_at and _dt_after(previous_received_at, received_at):
            return (
                "tick_received_at_regressed_before_consume:"
                f"feed={feed_session_id};seq={seq};"
                f"previous={previous_received_at};current={received_at}"
            )
        if previous_seq is not None and seq > previous_seq + 1:
            return (
                "tick_sequence_gap_before_consume:"
                f"feed={feed_session_id};previous={previous_seq};current={seq}"
            )
        last_seq_by_feed[feed_session_id] = seq
        last_received_by_feed[feed_session_id] = received_at
    return ""


def _dt_after(left: Any, right: Any) -> bool:
    left_dt = _parse_dt(left)
    right_dt = _parse_dt(right)
    if left_dt is None or right_dt is None:
        return False
    live_tz = timezone(timedelta(hours=8))
    if left_dt.tzinfo is None:
        left_dt = left_dt.replace(tzinfo=live_tz)
    if right_dt.tzinfo is None:
        right_dt = right_dt.replace(tzinfo=live_tz)
    return left_dt.astimezone(timezone.utc) > right_dt.astimezone(timezone.utc)


def _feed_gap_reason(
    *,
    state: dict[str, Any],
    heartbeat: dict[str, Any],
    tick_identity_errors: list[str],
    max_tick_age_seconds: int = DEFAULT_STATE_TICK_MAX_AGE_SECONDS,
) -> str:
    if tick_identity_errors:
        return tick_identity_errors[0]
    heartbeat_age = _age_seconds(heartbeat.get("generated_at"))
    transport_ready = heartbeat.get("transport_ready", heartbeat.get("stream_ready"))
    if not transport_ready or heartbeat_age is None or heartbeat_age > 3.0:
        return f"tick_stream_not_ready_or_stale:age={heartbeat_age}"
    feed_session_id = _clean(heartbeat.get("feed_session_id"))
    if not feed_session_id:
        return "tick_stream_feed_session_missing"
    vt_symbol = _clean(state.get("vt_symbol"))
    watermarks = heartbeat.get("symbol_tick_watermarks")
    if not isinstance(watermarks, dict):
        return "tick_stream_symbol_watermarks_missing"
    watermark = watermarks.get(vt_symbol)
    if not isinstance(watermark, dict):
        return f"tick_stream_symbol_watermark_missing:{vt_symbol}"
    watermark_sequence_value = watermark.get("symbol_stream_sequence")
    if not _clean(watermark_sequence_value):
        watermark_sequence_value = watermark.get("stream_sequence")
    watermark_sequence = pd.to_numeric(watermark_sequence_value, errors="coerce")
    watermark_received_at = _clean(watermark.get("received_at"))
    if pd.isna(watermark_sequence) or int(watermark_sequence) <= 0 or not watermark_received_at:
        return f"tick_stream_symbol_never_received:{vt_symbol}"
    watermark_age = _age_seconds(watermark_received_at)
    if watermark_age is None:
        return f"tick_stream_symbol_watermark_time_invalid:{vt_symbol}"
    if watermark_age < -ALLOWED_TICK_CLOCK_SKEW_SECONDS:
        return (
            f"tick_stream_symbol_tick_from_future:{vt_symbol};age={watermark_age};"
            f"allowed_skew={ALLOWED_TICK_CLOCK_SKEW_SECONDS}"
        )
    if watermark_age > max_tick_age_seconds:
        return (
            f"tick_stream_symbol_silent_stall:{vt_symbol};age={watermark_age};"
            f"max_age={max_tick_age_seconds}"
        )
    if _dt_after(heartbeat.get("feed_started_at"), state.get("entry_filled_at")):
        return "tick_stream_started_after_entry_fill"
    subscribed_at_by_symbol = heartbeat.get("subscribed_at_by_symbol")
    if isinstance(subscribed_at_by_symbol, dict):
        subscribed_at = subscribed_at_by_symbol.get(_clean(state.get("vt_symbol")))
        if subscribed_at and _dt_after(subscribed_at, state.get("entry_filled_at")):
            return "tick_stream_symbol_subscribed_after_entry_fill"
    last_seq_by_feed = state.get("last_seq_by_feed") if isinstance(state.get("last_seq_by_feed"), dict) else {}
    accepted = int((state.get("counters") or {}).get("accepted_ticks", 0))
    if accepted > 0 and last_seq_by_feed and feed_session_id not in last_seq_by_feed:
        return "tick_stream_session_changed_after_state_started"
    return ""


def _tick_buffer_gap_reason(state: dict[str, Any], ticks: pd.DataFrame, heartbeat: dict[str, Any]) -> str:
    last_key = state.get("last_tick_order_key")
    if ticks.empty:
        return ""
    if not isinstance(last_key, list) or len(last_key) != 3:
        # On the first reducer observation the bounded ring may already have
        # discarded the entry-to-now prefix.  A later favorable tick cannot
        # prove that no stop happened in that missing interval, so latch a
        # coverage gap before consuming the retained tail.
        current_feed = _clean(heartbeat.get("feed_session_id"))
        same_feed = ticks
        if current_feed and "feed_session_id" in ticks.columns:
            same_feed = ticks[
                ticks["feed_session_id"].fillna("").astype(str).eq(current_feed)
            ]
        vt_symbol = _clean(state.get("vt_symbol"))
        same_symbol = _tick_frame(same_feed, vt_symbol)
        watermarks = heartbeat.get("symbol_tick_watermarks")
        watermark = watermarks.get(vt_symbol) if isinstance(watermarks, dict) else None
        has_symbol_sequence = bool(
            isinstance(watermark, dict)
            and _clean(watermark.get("symbol_stream_sequence"))
        )
        if has_symbol_sequence:
            journal_count = int(
                _to_float(watermark.get("symbol_stream_sequence"), 0.0)
            )
            buffered_count = int(len(same_symbol))
            coverage_frame = same_symbol
        else:
            # Compatibility for a pre-upgrade Stage608 heartbeat.  Activation
            # deploys Stage608 first; new sessions always take the branch
            # above and never compare a global count with one symbol's rows.
            journal_count = int(
                _to_float(
                    heartbeat.get(
                        "journal_tick_count", heartbeat.get("stream_sequence")
                    ),
                    0.0,
                )
            )
            buffered_count = int(
                _to_float(
                    heartbeat.get("buffered_tick_count"), float(len(ticks))
                )
            )
            coverage_frame = same_feed
        if journal_count > buffered_count >= 0 and not coverage_frame.empty:
            received_column = next(
                (
                    key
                    for key in ("received_at", "localtime", "datetime", "snapshot_at")
                    if key in coverage_frame.columns
                ),
                "",
            )
            if received_column:
                received = pd.to_datetime(
                    coverage_frame[received_column], errors="coerce"
                )
                if received.notna().any():
                    earliest = received.min().isoformat()
                    if _dt_after(earliest, state.get("entry_filled_at")):
                        return (
                            "tick_buffer_overrun_before_first_observation:"
                            f"journal={journal_count};buffered={buffered_count}"
                        )
        return ""
    last_feed = _clean(last_key[1])
    last_seq = pd.to_numeric(last_key[2], errors="coerce")
    current_feed = _clean(heartbeat.get("feed_session_id"))
    if not last_feed or last_feed != current_feed or pd.isna(last_seq):
        return ""
    if "feed_session_id" not in ticks.columns:
        return "tick_buffer_feed_identity_missing"
    has_symbol_sequence = "symbol_stream_sequence" in ticks.columns
    seq_column = (
        "symbol_stream_sequence"
        if has_symbol_sequence
        else "stream_sequence"
        if "stream_sequence" in ticks.columns
        else "seq"
        if "seq" in ticks.columns
        else ""
    )
    if not seq_column:
        return "tick_buffer_sequence_missing"
    same_feed = ticks[ticks["feed_session_id"].fillna("").astype(str).eq(current_feed)]
    if has_symbol_sequence:
        same_feed = _tick_frame(same_feed, _clean(state.get("vt_symbol")))
    sequences = pd.to_numeric(same_feed.get(seq_column), errors="coerce").dropna()
    if not sequences.empty and float(sequences.min()) > float(last_seq) + 1:
        return f"tick_buffer_overrun:last={int(last_seq)};first={int(sequences.min())}"
    return ""


def _event_payload_by_fingerprint(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        fingerprint = _clean(row.get("intent_fingerprint"))
        payload = row.get("intent_payload")
        if fingerprint and isinstance(payload, dict):
            result[fingerprint] = payload
    return result


def _ledger_event_value(row: dict[str, Any], payloads: dict[str, dict[str, Any]], key: str) -> Any:
    value = row.get(key)
    if _clean(value):
        return value
    return payloads.get(_clean(row.get("intent_fingerprint")), {}).get(key)


def _fill_events_for_identity(
    rows: list[dict[str, Any]],
    *,
    target_date: str,
    root_position_id: str,
    position_epoch_id: str,
    position_cycle_id: str,
    intent_role: str,
) -> list[dict[str, Any]]:
    payloads = _event_payload_by_fingerprint(rows)
    matched: list[dict[str, Any]] = []
    seen_trade_ids: set[str] = set()
    seen_reconciliation_keys: set[str] = set()
    for row in rows:
        event_type = _clean(row.get("event_type"))
        if (
            _clean(row.get("target_date")) != target_date
            or event_type not in CLOSE_VOLUME_LEDGER_EVENTS
        ):
            continue
        if _clean(_ledger_event_value(row, payloads, "root_position_id")) != root_position_id:
            continue
        if _clean(_ledger_event_value(row, payloads, "position_epoch_id")) != position_epoch_id:
            continue
        if _clean(_ledger_event_value(row, payloads, "position_cycle_id")) != position_cycle_id:
            continue
        if _clean(_ledger_event_value(row, payloads, "intent_role")) != intent_role:
            continue
        if (
            event_type == CLOSE_VOLUME_RECONCILED_EVENT
            and intent_role not in {INITIAL_STOP_ACTION_ROLE, RETRY_STOP_ACTION_ROLE}
        ):
            # A broker-flat volume reconciliation is deliberately close-only.
            # It must never become evidence for an initial/retry open.
            continue
        if event_type == CLOSE_VOLUME_RECONCILED_EVENT:
            reconciliation_key = _clean(row.get("close_volume_reconciliation_key"))
            if not reconciliation_key or reconciliation_key in seen_reconciliation_keys:
                continue
            seen_reconciliation_keys.add(reconciliation_key)
            matched.append(row)
            continue
        trade_id = _clean(row.get("vt_tradeid") or row.get("trade_fill_key") or row.get("tradeid") or row.get("trade_id"))
        if trade_id and trade_id in seen_trade_ids:
            continue
        if trade_id:
            seen_trade_ids.add(trade_id)
        matched.append(row)
    return matched


def _filled_volume(rows: list[dict[str, Any]]) -> float:
    """Return close volume without double-counting late price callbacks.

    Reconciled rows carry the full broker-proven volume for one physical order,
    not a synthetic priced fill.  If EVENT_TRADE details arrive later, take the
    maximum priced/reconciled volume for that exact fingerprint/order pair.
    """

    priced_by_order: dict[str, float] = {}
    reconciled_by_order: dict[str, float] = {}
    unbound_priced_volume = 0.0
    for row in rows:
        event_type = _clean(row.get("event_type"))
        fingerprint = _clean(row.get("intent_fingerprint"))
        vt_orderid = _clean(row.get("vt_orderid"))
        order_key = f"{fingerprint}\0{vt_orderid}" if vt_orderid else ""
        if event_type == CLOSE_VOLUME_RECONCILED_EVENT:
            if not order_key:
                continue
            reconciled_by_order[order_key] = max(
                reconciled_by_order.get(order_key, 0.0),
                _to_float(row.get("reconciled_close_volume"), 0.0),
            )
            continue
        if event_type != "filled_or_part_filled":
            continue
        volume = _to_float(
            row.get("trade_volume_delta", row.get("volume")), 0.0
        )
        if order_key:
            priced_by_order[order_key] = priced_by_order.get(order_key, 0.0) + volume
        else:
            unbound_priced_volume += volume
    bound_volume = sum(
        max(priced_by_order.get(key, 0.0), reconciled_by_order.get(key, 0.0))
        for key in set(priced_by_order).union(reconciled_by_order)
    )
    return unbound_priced_volume + bound_volume


def _latest_fill_at(rows: list[dict[str, Any]]) -> str:
    return max((_clean(row.get("generated_at")) for row in rows), default="")


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _to_float(value: Any, default: float = 0.0) -> float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return float(number)


def _parse_dt(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _age_seconds(value: Any) -> float | None:
    dt = _parse_dt(value)
    if dt is None:
        return None
    now = datetime.now(dt.tzinfo) if dt.tzinfo is not None else datetime.now()
    return round((now - dt).total_seconds(), 3)


def _tick_age_is_fresh(age_seconds: float | None, max_tick_age_seconds: int) -> bool:
    return bool(
        age_seconds is not None
        and age_seconds >= -ALLOWED_TICK_CLOCK_SKEW_SECONDS
        and age_seconds <= max_tick_age_seconds
    )


def _normalize_direction(value: Any) -> str:
    text = _clean(value).lower()
    if text in {"long", "多", "direction.long"}:
        return "long"
    if text in {"short", "空", "direction.short"}:
        return "short"
    return text


def _normalize_offset(value: Any) -> str:
    text = _clean(value).lower()
    if text in {"open", "开", "offset.open"}:
        return "open"
    if text in {"close", "平", "closetoday", "closeyesterday", "平今", "平昨", "offset.close", "offset.closetoday", "offset.closeyesterday"}:
        return "close"
    return text


def _opposite_direction(direction: str) -> str:
    if direction == "long":
        return "short"
    if direction == "short":
        return "long"
    return ""


def _vt_symbol(row: dict[str, Any]) -> str:
    vt_symbol = _clean(row.get("vt_symbol"))
    if vt_symbol:
        return vt_symbol
    symbol = _clean(row.get("symbol") or row.get("instrument") or row.get("instrument_id"))
    exchange = _clean(row.get("exchange"))
    if symbol and exchange and "." not in symbol:
        return f"{symbol}.{exchange}"
    return symbol


def _date_only(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""
    try:
        return pd.Timestamp(text).date().isoformat()
    except Exception:
        return text[:10]


def _latest_open_trade(trades: pd.DataFrame, vt_symbol: str, direction: str, target_date: str) -> dict[str, Any] | None:
    if trades.empty:
        return None
    frame = trades.copy()
    frame["direction_norm"] = frame.get("direction", "").map(_normalize_direction)
    frame["offset_norm"] = frame.get("offset", "").map(_normalize_offset)
    frame["date_norm"] = frame.get("date", "").map(_date_only)
    matched = frame[
        frame.get("vt_symbol", "").astype(str).eq(vt_symbol)
        & frame["direction_norm"].eq(direction)
        & frame["offset_norm"].eq("open")
        & frame["date_norm"].le(target_date)
    ].copy()
    if matched.empty:
        return None
    matched["_dt"] = pd.to_datetime(matched.get("datetime", matched["date_norm"]), errors="coerce")
    return matched.sort_values("_dt").iloc[-1].to_dict()


def _broker_trade_identity(row: dict[str, Any]) -> str:
    if _clean(row.get("query_generation_uuid")) and int(
        _to_float(row.get("stable_trade_identity_complete"), 0.0)
    ) != 1:
        return ""
    stable_identity = _clean(row.get("broker_trade_identity"))
    if stable_identity:
        return stable_identity
    vt_tradeid = _clean(row.get("vt_tradeid"))
    if vt_tradeid:
        return f"vt:{vt_tradeid}"
    tradeid = _clean(row.get("tradeid") or row.get("trade_id"))
    if tradeid and _clean(row.get("gateway_name")):
        return f"trade:{_clean(row.get('gateway_name'))}:{tradeid}"
    return ""


def _broker_order_identity(row: dict[str, Any]) -> str:
    if _clean(row.get("query_generation_uuid")) and int(
        _to_float(row.get("order_mapping_complete"), 0.0)
    ) != 1:
        return ""
    vt_orderid = _clean(row.get("vt_orderid"))
    if vt_orderid:
        return vt_orderid
    orderid = _clean(row.get("orderid") or row.get("order_id"))
    if not orderid:
        return ""
    gateway_name = _clean(row.get("gateway_name"))
    return f"{gateway_name}.{orderid}" if gateway_name else orderid


def _weighted_broker_open_trade(
    trades: pd.DataFrame,
    vt_symbol: str,
    direction: str,
    target_date: str,
    *,
    broker_trading_day: str = "",
    query_generation_uuid: str = "",
) -> dict[str, Any] | None:
    """Reconstruct only the currently open broker epoch using FIFO trade lots."""

    if trades.empty:
        return None
    frame = trades.reset_index(drop=False).rename(columns={"index": "_source_row"}).copy()
    empty = pd.Series([""] * len(frame), index=frame.index)
    vt_source = frame["vt_symbol"] if "vt_symbol" in frame.columns else empty
    direction_source = frame["direction"] if "direction" in frame.columns else empty
    offset_source = frame["offset"] if "offset" in frame.columns else empty
    date_source = (
        frame["datetime"]
        if "datetime" in frame.columns
        else frame["date"]
        if "date" in frame.columns
        else frame["trading_day"]
        if "trading_day" in frame.columns
        else empty
    )
    frame["direction_norm"] = direction_source.map(_normalize_direction)
    frame["offset_norm"] = offset_source.map(_normalize_offset)
    frame["date_norm"] = date_source.map(_date_only)
    price_source = frame["price"] if "price" in frame.columns else pd.Series([0.0] * len(frame), index=frame.index)
    volume_source = frame["volume"] if "volume" in frame.columns else pd.Series([0.0] * len(frame), index=frame.index)
    frame["price_num"] = pd.to_numeric(price_source, errors="coerce").fillna(0.0)
    frame["volume_num"] = pd.to_numeric(volume_source, errors="coerce").fillna(0.0)
    frame["_dt"] = pd.to_datetime(date_source, errors="coerce")
    accepted_dates = {target_date}
    if broker_trading_day:
        try:
            accepted_dates.add(
                datetime.strptime(broker_trading_day, "%Y%m%d").date().isoformat()
            )
        except ValueError:
            return None
    generation_source = (
        frame["query_generation_uuid"]
        if "query_generation_uuid" in frame.columns
        else empty
    )
    close_direction = _opposite_direction(direction)
    matched = frame[
        vt_source.astype(str).eq(vt_symbol)
        & frame["date_norm"].isin(accepted_dates)
        & (
            generation_source.astype(str).eq(query_generation_uuid)
            if query_generation_uuid
            else pd.Series([True] * len(frame), index=frame.index)
        )
        & frame["price_num"].gt(0)
        & frame["volume_num"].gt(0)
        & (
            (frame["direction_norm"].eq(direction) & frame["offset_norm"].eq("open"))
            | (frame["direction_norm"].eq(close_direction) & frame["offset_norm"].eq("close"))
        )
    ].copy()
    if matched.empty:
        return None
    matched = matched.sort_values(["_dt", "_source_row"], na_position="last")

    open_lots: list[dict[str, Any]] = []
    epoch_first_identity = ""
    epoch_started_at = ""
    epoch_trade_identities: list[str] = []
    epoch_trade_identity_complete = True
    seen_trade_ids: set[str] = set()
    for raw in matched.to_dict(orient="records"):
        source_row = int(_to_float(raw.get("_source_row"), 0.0))
        identity = _broker_trade_identity(raw)
        if identity and identity in seen_trade_ids:
            continue
        if identity:
            seen_trade_ids.add(identity)
        trade_volume = _to_float(raw.get("volume_num"), 0.0)
        if raw.get("offset_norm") == "open" and raw.get("direction_norm") == direction:
            if not open_lots:
                epoch_first_identity = identity
                epoch_started_at = _clean(raw.get("datetime") or raw.get("date") or raw.get("trading_day"))
                epoch_trade_identities = []
                epoch_trade_identity_complete = True
            if identity:
                epoch_trade_identities.append(identity)
            else:
                epoch_trade_identity_complete = False
            open_lots.append({**raw, "remaining_volume": trade_volume, "trade_identity": identity})
            continue
        close_remaining = trade_volume
        while close_remaining > 1e-12 and open_lots:
            lot = open_lots[0]
            consumed = min(close_remaining, _to_float(lot.get("remaining_volume"), 0.0))
            lot["remaining_volume"] = _to_float(lot.get("remaining_volume"), 0.0) - consumed
            close_remaining -= consumed
            if _to_float(lot.get("remaining_volume"), 0.0) <= 1e-12:
                open_lots.pop(0)
        if not open_lots:
            epoch_first_identity = ""
            epoch_started_at = ""
            epoch_trade_identities = []
            epoch_trade_identity_complete = True

    if not open_lots or not epoch_started_at:
        return None
    total_volume = sum(_to_float(row.get("remaining_volume"), 0.0) for row in open_lots)
    if total_volume <= 0:
        return None
    weighted_price = sum(
        _to_float(row.get("price_num"), 0.0) * _to_float(row.get("remaining_volume"), 0.0)
        for row in open_lots
    ) / total_volume
    latest = open_lots[-1]
    remaining_order_ids = [
        _broker_order_identity(row) for row in open_lots
    ]
    order_identity_complete = bool(
        remaining_order_ids and all(remaining_order_ids)
    )
    return {
        **latest,
        "price": weighted_price,
        "volume": total_volume,
        "trade_count": int(len(open_lots)),
        "position_epoch_entry_at": epoch_started_at,
        "position_epoch_fill_identity": epoch_first_identity,
        "position_epoch_trade_identities": list(epoch_trade_identities),
        "remaining_trade_identities": [
            row["trade_identity"] for row in open_lots if row["trade_identity"]
        ],
        "position_epoch_trade_identity_complete": int(
            epoch_trade_identity_complete and bool(epoch_first_identity)
        ),
        "position_epoch_order_ids": list(
            dict.fromkeys(item for item in remaining_order_ids if item)
        ),
        "position_epoch_order_identity_complete": int(order_identity_complete),
        "broker_reported_date": _date_only(latest.get("datetime", latest.get("date", ""))),
        "broker_query_generation_uuid": query_generation_uuid,
        "broker_query_trading_day": broker_trading_day,
        "date": target_date,
    }


def _broker_original_open_trade_before_stage904_close(
    trades: pd.DataFrame,
    vt_symbol: str,
    direction: str,
    target_date: str,
    first_close_fill: dict[str, Any],
    *,
    broker_trading_day: str,
    query_generation_uuid: str,
) -> dict[str, Any] | None:
    if trades.empty:
        return None
    close_direction = _opposite_direction(direction)
    if not vt_symbol or direction not in {"long", "short"} or not close_direction:
        return None
    frame = trades.reset_index(drop=False).rename(columns={"index": "_source_row"}).copy()
    empty = pd.Series([""] * len(frame), index=frame.index)
    vt_source = frame["vt_symbol"] if "vt_symbol" in frame.columns else empty
    direction_source = frame["direction"] if "direction" in frame.columns else empty
    offset_source = frame["offset"] if "offset" in frame.columns else empty
    date_source = frame["datetime"] if "datetime" in frame.columns else frame["date"] if "date" in frame.columns else frame["trading_day"] if "trading_day" in frame.columns else empty
    frame["direction_norm"] = direction_source.map(_normalize_direction)
    frame["offset_norm"] = offset_source.map(_normalize_offset)
    frame["date_norm"] = date_source.map(_date_only)
    frame["price_num"] = pd.to_numeric(frame.get("price", 0.0), errors="coerce").fillna(0.0)
    frame["volume_num"] = pd.to_numeric(frame.get("volume", 0.0), errors="coerce").fillna(0.0)
    accepted_dates = {target_date}
    try:
        accepted_dates.add(
            datetime.strptime(broker_trading_day, "%Y%m%d").date().isoformat()
        )
    except (TypeError, ValueError):
        return None
    if not query_generation_uuid or "query_generation_uuid" not in frame.columns:
        return None
    generation_source = frame["query_generation_uuid"].map(_clean)
    symbol_trades = frame[
        vt_source.astype(str).eq(vt_symbol)
        & frame["date_norm"].isin(accepted_dates)
        & generation_source.eq(query_generation_uuid)
    ].copy()
    if symbol_trades.empty:
        return None
    if any(
        not _broker_trade_identity(row) or not _broker_order_identity(row)
        for row in symbol_trades.to_dict(orient="records")
    ):
        return None

    close_rows = symbol_trades[
        symbol_trades["direction_norm"].eq(close_direction)
        & symbol_trades["offset_norm"].eq("close")
        & symbol_trades["price_num"].gt(0)
        & symbol_trades["volume_num"].gt(0)
    ].copy()
    if close_rows.empty:
        return None
    close_price = _to_float(first_close_fill.get("price"), 0.0)
    close_volume = _to_float(first_close_fill.get("trade_volume_delta", first_close_fill.get("volume")), 0.0)
    matched_close_rows = close_rows
    if close_price > 0:
        by_price = matched_close_rows[matched_close_rows["price_num"].sub(close_price).abs().le(1e-9)]
        if not by_price.empty:
            matched_close_rows = by_price
    if close_volume > 0:
        by_volume = matched_close_rows[matched_close_rows["volume_num"].sub(close_volume).abs().le(1e-9)]
        if not by_volume.empty:
            matched_close_rows = by_volume
    close_source_row = float(matched_close_rows.sort_values("_source_row").iloc[0]["_source_row"])

    open_rows = symbol_trades[
        symbol_trades["direction_norm"].eq(direction)
        & symbol_trades["offset_norm"].eq("open")
        & symbol_trades["_source_row"].lt(close_source_row)
        & symbol_trades["price_num"].gt(0)
        & symbol_trades["volume_num"].gt(0)
    ].copy()
    if open_rows.empty:
        return None
    total_volume = float(open_rows["volume_num"].sum())
    if total_volume <= 0:
        return None
    weighted_price = float((open_rows["price_num"] * open_rows["volume_num"]).sum() / total_volume)
    open_rows["_dt"] = pd.to_datetime(open_rows.get("datetime", open_rows["date_norm"]), errors="coerce")
    latest = open_rows.sort_values(["_source_row"]).iloc[-1].to_dict()
    return {
        **latest,
        "vt_symbol": vt_symbol,
        "direction": direction,
        "offset": "open",
        "price": weighted_price,
        "volume": total_volume,
        "trade_count": int(len(open_rows)),
        "broker_reported_date": _date_only(latest.get("datetime", latest.get("date", ""))),
        "broker_query_generation_uuid": query_generation_uuid,
        "broker_query_trading_day": broker_trading_day,
        "date": target_date,
        "fill_price_source": "readonly_broker_open_trade_before_stage904_stop_close",
    }


def _latest_entry_risk(entry_risk: pd.DataFrame, vt_symbol: str, direction: str, target_date: str) -> dict[str, Any] | None:
    if entry_risk.empty:
        return None
    frame = entry_risk.copy()
    empty = pd.Series([""] * len(frame), index=frame.index)
    direction_source = frame["direction"] if "direction" in frame.columns else empty
    date_source = frame["date"] if "date" in frame.columns else empty
    vt_source = frame["contract_vt_symbol"] if "contract_vt_symbol" in frame.columns else frame["vt_symbol"] if "vt_symbol" in frame.columns else empty
    frame["direction_norm"] = direction_source.map(_normalize_direction)
    frame["date_norm"] = date_source.map(_date_only)
    matched = frame[
        vt_source.astype(str).eq(vt_symbol)
        & frame["direction_norm"].eq(direction)
        & frame["date_norm"].le(target_date)
    ].copy()
    if matched.empty:
        return None
    matched["_dt"] = pd.to_datetime(matched.get("datetime", matched["date_norm"]), errors="coerce")
    return matched.sort_values("_dt").iloc[-1].to_dict()


def _tick_frame(ticks: pd.DataFrame, vt_symbol: str) -> pd.DataFrame:
    if ticks.empty:
        return pd.DataFrame()
    if "vt_symbol" in ticks.columns:
        matched = ticks[ticks["vt_symbol"].fillna("").astype(str).eq(vt_symbol)].copy()
    elif "symbol" in ticks.columns and "exchange" in ticks.columns:
        key = ticks["symbol"].fillna("").astype(str) + "." + ticks["exchange"].fillna("").astype(str)
        matched = ticks[key.eq(vt_symbol)].copy()
    else:
        return pd.DataFrame()
    return matched


def _tick_dt_series(frame: pd.DataFrame) -> pd.Series:
    for key in ("received_at", "localtime", "datetime", "snapshot_at", "generated_at"):
        if key not in frame.columns:
            continue
        series = pd.to_datetime(frame[key], errors="coerce")
        if series.notna().any():
            return series
    return pd.Series(pd.NaT, index=frame.index)


def _fresh_tick_frame(ticks: pd.DataFrame, vt_symbol: str, max_tick_age_seconds: int) -> pd.DataFrame:
    matched = _tick_frame(ticks, vt_symbol)
    if matched.empty:
        return matched
    matched = matched.copy()
    matched["_dt"] = _tick_dt_series(matched)
    matched = matched.dropna(subset=["_dt"])
    if matched.empty:
        return matched
    now = pd.Timestamp.now(tz=matched["_dt"].dt.tz) if matched["_dt"].dt.tz is not None else pd.Timestamp.now()
    ages = (now - matched["_dt"]).dt.total_seconds()
    return matched[
        ages.ge(-ALLOWED_TICK_CLOCK_SKEW_SECONDS)
        & ages.le(max_tick_age_seconds)
    ].copy()


def _tick_row(ticks: pd.DataFrame, vt_symbol: str) -> dict[str, Any] | None:
    matched = _tick_frame(ticks, vt_symbol)
    if matched.empty:
        return None
    matched = matched.copy()
    matched["_dt"] = _tick_dt_series(matched)
    if matched["_dt"].notna().any():
        return matched.sort_values("_dt").iloc[-1].to_dict()
    return matched.iloc[-1].to_dict()


def _tick_age(row: dict[str, Any] | None) -> float | None:
    if not row:
        return None
    for key in ("received_at", "localtime", "datetime", "snapshot_at", "generated_at"):
        if key in row:
            age = _age_seconds(row.get(key))
            if age is not None:
                return age
    return None


def _tick_price(row: dict[str, Any] | None) -> tuple[float, str]:
    if not row:
        return 0.0, "missing_tick"
    for key in ("last_price", "last", "price", "close_price"):
        value = _to_float(row.get(key), 0.0)
        if value > 0:
            return value, key
    bid = _to_float(row.get("bid_price_1"), 0.0)
    ask = _to_float(row.get("ask_price_1"), 0.0)
    if bid > 0 and ask > 0:
        return round((bid + ask) / 2, 10), "mid_bid_ask"
    if bid > 0:
        return bid, "bid_price_1"
    if ask > 0:
        return ask, "ask_price_1"
    return 0.0, "missing_tick_price"


def _tick_value(row: dict[str, Any] | None, *keys: str) -> float:
    if not row:
        return 0.0
    for key in keys:
        value = _to_float(row.get(key), 0.0)
        if value > 0:
            return value
    return 0.0


def _fresh_extreme_price(frame: pd.DataFrame, direction: str, kind: str) -> tuple[float, str]:
    if frame.empty:
        return 0.0, "missing_fresh_tick_batch"
    if kind == "adverse" and direction == "long":
        keys = ("last_price", "last", "price", "close_price", "bid_price_1")
        method = "min"
    elif kind == "adverse" and direction == "short":
        keys = ("last_price", "last", "price", "close_price", "ask_price_1")
        method = "max"
    elif kind == "progress" and direction == "long":
        # Stage847 progress is a traded-price condition.  A wide ask alone
        # cannot permanently waive the initial stop.
        keys = ("last_price", "last", "price", "close_price")
        method = "max"
    else:
        keys = ("last_price", "last", "price", "close_price")
        method = "min"
    values: list[tuple[str, float]] = []
    for key in keys:
        if key not in frame.columns:
            continue
        series = pd.to_numeric(frame[key], errors="coerce").dropna()
        series = series[series.gt(0)]
        if series.empty:
            continue
        value = float(series.min() if method == "min" else series.max())
        values.append((key, value))
    if not values:
        return 0.0, "missing_fresh_tick_price_batch"
    if method == "min":
        source, value = min(values, key=lambda item: item[1])
    else:
        source, value = max(values, key=lambda item: item[1])
    return value, f"{method}_{source}_fresh_batch"


def _broker_position_price(row: dict[str, Any]) -> tuple[float, str]:
    for key in ("price", "avg_price", "open_price", "cost_price"):
        price = _to_float(row.get(key), 0.0)
        if price > 0:
            return price, key
    return 0.0, "broker_fill_price_missing"


def _broker_position_volume(row: dict[str, Any]) -> float:
    volume = _to_float(row.get("volume", row.get("position", row.get("pos", 0.0))), 0.0)
    frozen = _to_float(row.get("frozen", row.get("frozen_volume", 0.0)), 0.0)
    return max(0.0, volume - frozen)


def _broker_position_gross_volume(row: dict[str, Any]) -> float:
    return max(0.0, _to_float(row.get("volume", row.get("position", row.get("pos", 0.0))), 0.0))


def _has_broker_position(broker_positions: pd.DataFrame, vt_symbol: str, direction: str) -> bool:
    if broker_positions.empty:
        return False
    for row in broker_positions.drop_duplicates().to_dict(orient="records"):
        if _vt_symbol(row) == vt_symbol and _normalize_direction(row.get("direction")) == direction:
            if _broker_position_gross_volume(row) > 0:
                return True
    return False


def _broker_symbol_gross_volume(broker_positions: pd.DataFrame, vt_symbol: str) -> float:
    if broker_positions.empty:
        return 0.0
    return sum(
        _broker_position_gross_volume(row)
        for row in broker_positions.drop_duplicates().to_dict(orient="records")
        if _vt_symbol(row) == vt_symbol
    )


def _monitor_positions(shadow_positions: pd.DataFrame, broker_positions: pd.DataFrame) -> pd.DataFrame:
    keyed: dict[tuple[str, str], dict[str, Any]] = {}
    for row in shadow_positions.to_dict(orient="records"):
        vt_symbol = _clean(row.get("vt_symbol"))
        direction = _normalize_direction(row.get("direction"))
        volume = abs(_to_float(row.get("end_pos", row.get("volume", 0.0)), 0.0))
        if not vt_symbol or direction not in {"long", "short"} or volume <= 0:
            continue
        item = dict(row)
        item["position_source"] = "shadow"
        item["volume"] = volume
        keyed[(vt_symbol, direction)] = item

    for row in broker_positions.drop_duplicates().to_dict(orient="records"):
        vt_symbol = _vt_symbol(row)
        direction = _normalize_direction(row.get("direction"))
        volume = _broker_position_volume(row)
        if not vt_symbol or direction not in {"long", "short"} or volume <= 0:
            continue
        price, price_source = _broker_position_price(row)
        item = dict(row)
        item["vt_symbol"] = vt_symbol
        item["direction"] = direction
        item["position_source"] = "broker"
        item["volume"] = volume
        item["end_pos"] = volume
        item["broker_fill_price"] = price
        item["broker_fill_price_source"] = price_source
        keyed[(vt_symbol, direction)] = item

    return pd.DataFrame(list(keyed.values()))


def _ledger_intent_payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = row.get("intent_payload")
    return payload if isinstance(payload, dict) else {}


def _ledger_source(row: dict[str, Any]) -> str:
    payload = _ledger_intent_payload(row)
    return _clean(payload.get("source") or row.get("source"))


def _ledger_intent_role(row: dict[str, Any]) -> str:
    payload = _ledger_intent_payload(row)
    return _clean(payload.get("intent_role") or row.get("intent_role"))


def _ledger_vt_symbol(row: dict[str, Any]) -> str:
    payload = _ledger_intent_payload(row)
    return _clean(row.get("vt_symbol") or payload.get("vt_symbol"))


def _ledger_direction(row: dict[str, Any]) -> str:
    payload = _ledger_intent_payload(row)
    return _normalize_direction(row.get("direction") or payload.get("direction"))


def _ledger_offset(row: dict[str, Any]) -> str:
    payload = _ledger_intent_payload(row)
    return _normalize_offset(row.get("offset") or payload.get("offset"))


def _ledger_trade_identities(row: dict[str, Any] | None) -> set[str]:
    if not row:
        return set()
    raw = row.get("trade_identities")
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            raw = parsed if isinstance(parsed, list) else [raw]
        except json.JSONDecodeError:
            raw = [raw]
    identities = {_clean(item) for item in raw} if isinstance(raw, list) else set()
    vt_tradeid = _clean(row.get("vt_tradeid"))
    if vt_tradeid:
        identities.add(f"vt:{vt_tradeid}")
    tradeid = _clean(row.get("tradeid") or row.get("trade_id"))
    if tradeid:
        identities.add(f"trade:{_clean(row.get('gateway_name'))}:{tradeid}")
    return {identity for identity in identities if identity}


def _stage904_stop_close_fills(
    rows: list[dict[str, Any]],
    target_date: str,
    vt_symbol: str,
    original_direction: str,
    position_epoch_id: str | None = None,
) -> list[dict[str, Any]]:
    close_direction = _opposite_direction(original_direction)
    matched: list[dict[str, Any]] = []
    for row in rows:
        if _clean(row.get("target_date")) != target_date:
            continue
        if _clean(row.get("event_type")) not in CLOSE_VOLUME_LEDGER_EVENTS:
            continue
        if _ledger_vt_symbol(row) != vt_symbol:
            continue
        if _ledger_direction(row) != close_direction:
            continue
        if _ledger_offset(row) != "close":
            continue
        if position_epoch_id is not None:
            payload = _ledger_intent_payload(row)
            if _clean(row.get("position_epoch_id") or payload.get("position_epoch_id")) != position_epoch_id:
                continue
        intent_id = _clean(row.get("intent_id"))
        if (
            intent_id.startswith("STAGE905-C9MON")
            or _ledger_source(row) == "stage904_c9_intraday_close"
            or _ledger_intent_role(row)
            in {INITIAL_STOP_ACTION_ROLE, RETRY_STOP_ACTION_ROLE}
        ):
            matched.append(row)
    return matched


def _stage904_retry_open_attempted(
    rows: list[dict[str, Any]],
    target_date: str,
    vt_symbol: str,
    original_direction: str,
) -> bool:
    for row in rows:
        if _clean(row.get("event_type")) not in RETRY_OPEN_CONSUMING_LEDGER_EVENTS:
            continue
        if _clean(row.get("target_date")) != target_date:
            continue
        if _ledger_vt_symbol(row) != vt_symbol:
            continue
        if _ledger_direction(row) != original_direction:
            continue
        if _ledger_offset(row) != "open":
            continue
        intent_id = _clean(row.get("intent_id"))
        if (
            intent_id.startswith("STAGE905-C9RETRY")
            or _ledger_source(row) == "stage904_c9_intraday_retry_open"
            or _ledger_intent_role(row) == RETRY_INTENT_ROLE
        ):
            return True
    return False


def _retry_action_for_stopped_position(
    *,
    ledger_open_trade: dict[str, Any],
    close_fill: dict[str, Any],
    stop_close_filled_volume: float,
    broker_positions: pd.DataFrame,
    entry_risk: pd.DataFrame,
    ticks: pd.DataFrame,
    target_date: str,
    max_tick_age_seconds: int,
) -> dict[str, Any]:
    vt_symbol = _clean(ledger_open_trade.get("vt_symbol"))
    direction = _normalize_direction(ledger_open_trade.get("direction"))
    volume = _to_float(ledger_open_trade.get("volume"), 0.0)
    fill_price = _to_float(ledger_open_trade.get("price"), 0.0)
    risk_row = _latest_entry_risk(entry_risk, vt_symbol, direction, target_date)
    initial_stop_price = _to_float(risk_row.get("stop_price") if risk_row else None, 0.0)
    risk_price = abs(fill_price - initial_stop_price) if fill_price > 0 and initial_stop_price > 0 else 0.0
    tick = _tick_row(ticks, vt_symbol)
    fresh_ticks = _fresh_tick_frame(ticks, vt_symbol, max_tick_age_seconds)
    tick_age = _tick_age(tick)
    live_price, live_price_source = _tick_price(tick)
    progress_extreme_price, progress_extreme_source = _fresh_extreme_price(fresh_ticks, direction, "progress")
    reasons: list[str] = []
    action = "retry_block"

    if not vt_symbol:
        reasons.append("retry_missing_vt_symbol")
    if direction not in {"long", "short"}:
        reasons.append("retry_invalid_direction")
    if volume <= 0:
        reasons.append("retry_invalid_volume")
    if fill_price <= 0:
        reasons.append("retry_original_fill_price_missing")
    if risk_row is None:
        reasons.append("retry_matching_entry_risk_missing")
    if risk_price <= 0:
        reasons.append("retry_invalid_risk_price")
    if stop_close_filled_volume + 1e-9 < volume:
        reasons.append(f"retry_stop_close_not_fully_filled:{stop_close_filled_volume}<{volume}")
    if _has_broker_position(broker_positions, vt_symbol, direction):
        reasons.append("retry_blocked_broker_position_not_flat_after_stop_close")
    if tick is None:
        reasons.append("retry_fresh_tick_missing")
    if not _tick_age_is_fresh(tick_age, max_tick_age_seconds):
        reasons.append("retry_fresh_tick_missing_stale_or_future")
    if live_price <= 0:
        reasons.append("retry_live_price_missing")

    retry_hit = False
    if risk_price > 0 and progress_extreme_price > 0:
        if direction == "long":
            retry_hit = progress_extreme_price >= fill_price
        elif direction == "short":
            retry_hit = progress_extreme_price <= fill_price

    if not reasons:
        if retry_hit:
            action = "retry_open_dry_run"
            reasons.append("stage847_retry_reclaim_triggered")
        else:
            action = "retry_watch"
            reasons.append("stage847_retry_waiting_for_reclaim")

    return {
        "target_date": target_date,
        "vt_symbol": vt_symbol,
        "direction": direction,
        "position_source": "ledger_stop_close_flat",
        "volume": volume,
        "open_trade_id": _clean(ledger_open_trade.get("trade_id")),
        "open_trade_date": _date_only(ledger_open_trade.get("date")),
        "ledger_open_trade_date": _date_only(ledger_open_trade.get("date")),
        "ledger_open_trade_count": int(_to_float(ledger_open_trade.get("trade_count"), 0.0)),
        "ledger_open_trade_volume": volume,
        "broker_open_trade_date": "",
        "broker_open_trade_count": 0,
        "broker_open_trade_volume": 0.0,
        "entry_risk_date": _date_only(risk_row.get("date") if risk_row else ""),
        "entry_day_active": 1,
        "fill_price": fill_price,
        "fill_price_source": _clean(ledger_open_trade.get("fill_price_source")) or "stage931_execution_ledger_open_fill_weighted_avg",
        "ledger_fill_price": fill_price,
        "broker_fill_price": 0.0,
        "broker_position_avg_price": 0.0,
        "broker_position_avg_price_source": "",
        "initial_stop_price": initial_stop_price,
        "risk_price": risk_price,
        "stop_retry_r": STOP_RETRY_R,
        "stage847_stop_price": fill_price - (1.0 if direction == "long" else -1.0) * STOP_RETRY_R * risk_price if risk_price > 0 else 0.0,
        "stage847_progress_price": fill_price,
        "stage847_retry_trigger_price": fill_price,
        "live_price": live_price,
        "live_price_source": live_price_source,
        "live_bid_price_1": _tick_value(tick, "bid_price_1"),
        "live_ask_price_1": _tick_value(tick, "ask_price_1"),
        "live_limit_up": _tick_value(tick, "limit_up", "upper_limit", "limit_up_price"),
        "live_limit_down": _tick_value(tick, "limit_down", "lower_limit", "limit_down_price"),
        "adverse_extreme_price": _to_float(close_fill.get("price"), 0.0),
        "adverse_extreme_source": "stage931_stop_close_fill",
        "progress_extreme_price": progress_extreme_price,
        "progress_extreme_source": progress_extreme_source,
        "tick_batch_count": int(len(_tick_frame(ticks, vt_symbol))),
        "fresh_tick_batch_count": int(len(fresh_ticks)),
        "tick_age_seconds": tick_age,
        "mark_price_fallback": 0.0,
        "adverse_hit": 0,
        "progress_hit": int(retry_hit),
        "retry_open_attempted": 0,
        "retry_stop_close_fill_price": _to_float(close_fill.get("price"), 0.0),
        "retry_stop_close_fill_volume": stop_close_filled_volume,
        "monitor_action": action,
        "monitor_reason": ";".join(dict.fromkeys(reasons)),
        "order_api_called": 0,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _retry_actions(
    *,
    broker_positions: pd.DataFrame,
    broker_trades: pd.DataFrame,
    execution_ledger_rows: list[dict[str, Any]],
    entry_risk: pd.DataFrame,
    ticks: pd.DataFrame,
    target_date: str,
    max_tick_age_seconds: int,
    readonly_summary: dict[str, Any] | None = None,
    readonly_bundle_manifest: dict[str, Any] | None = None,
    readonly_bundle_evidence: dict[str, Any] | None = None,
) -> pd.DataFrame:
    bundle_ok, _, broker_trading_day, generation_uuid = (
        validate_readonly_query_bundle(
            readonly_summary=readonly_summary or {},
            bundle_manifest=readonly_bundle_manifest or {},
            bundle_evidence=readonly_bundle_evidence or {},
        )
    )
    open_keys: set[tuple[str, str]] = set()
    for row in execution_ledger_rows:
        if _clean(row.get("target_date")) != target_date:
            continue
        if _clean(row.get("event_type")) not in CLOSE_VOLUME_LEDGER_EVENTS:
            continue
        vt_symbol = _ledger_vt_symbol(row)
        offset = _ledger_offset(row)
        direction = _ledger_direction(row)
        if offset == "open" and vt_symbol and direction in {"long", "short"}:
            open_keys.add((vt_symbol, direction))
            continue
        if offset != "close" or not vt_symbol or direction not in {"long", "short"}:
            continue
        original_direction = _opposite_direction(direction)
        intent_id = _clean(row.get("intent_id"))
        if original_direction and (intent_id.startswith("STAGE905-C9MON") or _ledger_source(row) == "stage904_c9_intraday_close"):
            open_keys.add((vt_symbol, original_direction))

    rows: list[dict[str, Any]] = []
    for vt_symbol, direction in sorted(open_keys):
        if _stage904_retry_open_attempted(execution_ledger_rows, target_date, vt_symbol, direction):
            continue
        close_fills = _stage904_stop_close_fills(execution_ledger_rows, target_date, vt_symbol, direction)
        if not close_fills:
            continue
        ledger_open_trade = weighted_open_fill(execution_ledger_rows, target_date, vt_symbol, direction)
        ledger_open_intent_id = _clean(ledger_open_trade.get("intent_id") if ledger_open_trade else "")
        ledger_open_at = _clean(ledger_open_trade.get("generated_at") if ledger_open_trade else "")
        first_close_at = _clean(close_fills[0].get("generated_at"))
        use_broker_fallback = ledger_open_trade is None
        if ledger_open_intent_id.startswith("STAGE905-PENDING") and ledger_open_at and first_close_at and ledger_open_at >= first_close_at:
            use_broker_fallback = True
        if use_broker_fallback:
            if not bundle_ok:
                continue
            ledger_open_trade = _broker_original_open_trade_before_stage904_close(
                broker_trades,
                vt_symbol,
                direction,
                target_date,
                close_fills[0],
                broker_trading_day=broker_trading_day,
                query_generation_uuid=generation_uuid,
            )
        if not ledger_open_trade:
            continue
        stop_close_filled_volume = _filled_volume(close_fills)
        rows.append(
            _retry_action_for_stopped_position(
                ledger_open_trade=ledger_open_trade,
                close_fill=close_fills[-1],
                stop_close_filled_volume=stop_close_filled_volume,
                broker_positions=broker_positions,
                entry_risk=entry_risk,
                ticks=ticks,
                target_date=target_date,
                max_tick_age_seconds=max_tick_age_seconds,
            )
        )
    return pd.DataFrame(rows)


def _action_for_position(
    position: dict[str, Any],
    *,
    trades: pd.DataFrame,
    broker_trades: pd.DataFrame,
    execution_ledger_rows: list[dict[str, Any]],
    entry_risk: pd.DataFrame,
    ticks: pd.DataFrame,
    target_date: str,
    max_tick_age_seconds: int,
    require_broker_fill_price: bool,
    readonly_summary: dict[str, Any] | None = None,
    readonly_bundle_manifest: dict[str, Any] | None = None,
    readonly_bundle_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    vt_symbol = _clean(position.get("vt_symbol"))
    direction = _normalize_direction(position.get("direction"))
    volume = _to_float(position.get("end_pos", position.get("volume", 0.0)), 0.0)
    mark_price = _to_float(position.get("close_price"), 0.0)
    position_source = _clean(position.get("position_source")) or "shadow"
    broker_position_avg_price = _to_float(position.get("broker_fill_price"), 0.0)
    broker_position_avg_price_source = _clean(position.get("broker_fill_price_source"))
    reasons: list[str] = []
    action = "block"

    open_trade = _latest_open_trade(trades, vt_symbol, direction, target_date)
    root_position_id = (
        generate_root_position_id(target_date=target_date, vt_symbol=vt_symbol, direction=direction)
        if target_date and vt_symbol and direction in {"long", "short"}
        else ""
    )
    ledger_open_candidate = latest_position_cycle_open_fill(
        execution_ledger_rows,
        target_date,
        vt_symbol,
        direction,
        root_position_id=root_position_id or None,
    ) or weighted_open_fill(execution_ledger_rows, target_date, vt_symbol, direction)
    bundle_manifest = (
        readonly_bundle_manifest
        if isinstance(readonly_bundle_manifest, dict)
        else {}
    )
    (
        broker_bundle_valid,
        broker_bundle_reason,
        broker_query_trading_day,
        broker_query_generation_uuid,
    ) = validate_readonly_query_bundle(
        readonly_summary=readonly_summary or {},
        bundle_manifest=bundle_manifest,
        bundle_evidence=readonly_bundle_evidence or {},
    )
    broker_open_trade = None
    if broker_bundle_valid:
        broker_open_trade = _weighted_broker_open_trade(
            broker_trades,
            vt_symbol,
            direction,
            target_date,
            broker_trading_day=broker_query_trading_day,
            query_generation_uuid=broker_query_generation_uuid,
        )
    broker_reconstructed_volume = _to_float(
        broker_open_trade.get("volume") if broker_open_trade else None,
        0.0,
    )
    broker_epoch_complete = bool(
        position_source == "broker"
        and broker_open_trade
        and volume > 0
        and abs(broker_reconstructed_volume - volume) <= 1e-9
    )
    broker_trade_identities = {
        _clean(item)
        for item in (broker_open_trade or {}).get("position_epoch_trade_identities", [])
        if _clean(item)
    }
    ledger_trade_identities = _ledger_trade_identities(ledger_open_candidate)
    ledger_matches_current_broker = bool(
        broker_epoch_complete
        and broker_trade_identities.intersection(ledger_trade_identities)
    )
    # A complete current-position reconstruction is the strongest same-day
    # epoch evidence.  An old Stage931 fill must not eclipse a later manual
    # reopen after the broker position first returned to flat.
    if broker_epoch_complete:
        ledger_open_trade = ledger_open_candidate if ledger_matches_current_broker else None
        ledger_position_epoch_id = _clean((ledger_open_trade or {}).get("position_epoch_id"))
        if ledger_position_epoch_id:
            selected_position_epoch_id = ledger_position_epoch_id
            position_epoch_source = "matching_stage931_execution_ledger"
        else:
            try:
                selected_position_epoch_id = generate_position_epoch_id(
                    target_date=target_date,
                    vt_symbol=vt_symbol,
                    direction=direction,
                    entry_filled_at=_clean(broker_open_trade.get("position_epoch_entry_at")),
                    fill_identity=_clean(broker_open_trade.get("position_epoch_fill_identity")),
                )
                position_epoch_source = "readonly_broker_current_epoch_fifo"
            except ValueError:
                selected_position_epoch_id = ""
                position_epoch_source = "readonly_broker_current_epoch_identity_invalid"
    else:
        ledger_open_trade = ledger_open_candidate
        selected_position_epoch_id = _clean((ledger_open_trade or {}).get("position_epoch_id"))
        position_epoch_source = (
            "stage931_execution_ledger_without_complete_broker_reconstruction"
            if selected_position_epoch_id
            else "position_epoch_not_resolved"
        )
    risk_row = _latest_entry_risk(entry_risk, vt_symbol, direction, target_date)
    tick = _tick_row(ticks, vt_symbol)
    fresh_ticks = _fresh_tick_frame(ticks, vt_symbol, max_tick_age_seconds)
    tick_age = _tick_age(tick)
    live_price, live_price_source = _tick_price(tick)
    adverse_extreme_price, adverse_extreme_source = _fresh_extreme_price(fresh_ticks, direction, "adverse")
    progress_extreme_price, progress_extreme_source = _fresh_extreme_price(fresh_ticks, direction, "progress")
    stop_close_fills = _stage904_stop_close_fills(
        execution_ledger_rows,
        target_date,
        vt_symbol,
        direction,
        position_epoch_id=selected_position_epoch_id or None,
    )

    if not vt_symbol:
        reasons.append("missing_vt_symbol")
    if direction not in {"long", "short"}:
        reasons.append("invalid_direction")
    if volume <= 0:
        reasons.append("no_open_volume")
    if position_source == "broker" and not broker_bundle_valid:
        reasons.append(f"broker_query_bundle_unusable:{broker_bundle_reason}")
    ledger_fill_price = _to_float(ledger_open_trade.get("price") if ledger_open_trade else None, 0.0)
    broker_fill_price = (
        _to_float(broker_open_trade.get("price") if broker_open_trade else None, 0.0)
        if broker_epoch_complete
        else 0.0
    )

    shadow_fill_price = _to_float(open_trade.get("price") if open_trade else None, 0.0)
    if broker_fill_price > 0:
        fill_price = broker_fill_price
        fill_price_source = "readonly_broker_current_epoch_fifo_weighted_avg"
    elif ledger_fill_price > 0:
        fill_price = ledger_fill_price
        fill_price_source = "stage931_execution_ledger_open_fill_weighted_avg"
    else:
        fill_price = shadow_fill_price
        fill_price_source = "shadow_open_trade_price"
    initial_stop_price = _to_float(risk_row.get("stop_price") if risk_row else None, 0.0)
    open_trade_date = _date_only(open_trade.get("date") if open_trade else "")
    risk_date = _date_only(risk_row.get("date") if risk_row else "")
    broker_open_trade_date = _date_only(broker_open_trade.get("date") if broker_open_trade else "")
    ledger_open_trade_date = _date_only(ledger_open_trade.get("date") if ledger_open_trade else "")
    ledger_open_source = _ledger_source(ledger_open_trade) if ledger_open_trade else ""
    ledger_open_intent_id = _clean(ledger_open_trade.get("intent_id")) if ledger_open_trade else ""
    entry_filled_at = _clean(
        ((broker_open_trade or {}).get("position_epoch_entry_at") if broker_epoch_complete else "")
        or (ledger_open_trade or {}).get("generated_at")
        or (broker_open_trade or {}).get("datetime")
        or (broker_open_trade or {}).get("snapshot_at")
        or (open_trade or {}).get("datetime")
        or (open_trade or {}).get("date")
    )
    stop_close_latest_at = _clean(stop_close_fills[-1].get("generated_at")) if stop_close_fills else ""
    ledger_open_at = _clean(ledger_open_trade.get("generated_at")) if ledger_open_trade else ""
    forced_close_after_stop_reentry = bool(
        stop_close_fills
        and ledger_fill_price > 0
        and (ledger_open_source == "stage901_pending_order" or ledger_open_intent_id.startswith("STAGE905-PENDING"))
        and (not stop_close_latest_at or not ledger_open_at or ledger_open_at >= stop_close_latest_at)
    )
    opened_today = bool(
        open_trade_date == target_date
        or ledger_open_trade_date == target_date
        or broker_open_trade_date == target_date
    )
    entry_day_active = bool(
        risk_date == target_date
        and (
            opened_today
            or (position_source == "broker" and broker_position_avg_price > 0)
        )
    )
    if not entry_day_active:
        if not reasons:
            action = "watch"
        reasons.append("c9_entry_day_monitor_not_active")
    else:
        if position_source == "broker" and broker_open_trade and not broker_epoch_complete:
            reasons.append(
                "broker_current_epoch_volume_mismatch:"
                f"reconstructed={broker_reconstructed_volume};position={volume}"
            )
        if broker_epoch_complete and not selected_position_epoch_id:
            reasons.append("broker_current_epoch_identity_missing")
        if open_trade is None and ledger_fill_price <= 0 and broker_fill_price <= 0:
            reasons.append("matching_open_trade_missing")
        if risk_row is None:
            reasons.append("matching_entry_risk_missing")
        if require_broker_fill_price and ledger_fill_price <= 0 and broker_fill_price <= 0:
            reasons.append("broker_or_execution_open_trade_fill_price_missing_for_live_real_monitor")
        if tick is None:
            reasons.append("fresh_tick_missing")
        if not _tick_age_is_fresh(tick_age, max_tick_age_seconds):
            reasons.append("fresh_tick_missing_stale_or_future")
        if live_price <= 0:
            reasons.append("live_price_missing")
    risk_price = abs(fill_price - initial_stop_price) if fill_price > 0 and initial_stop_price > 0 else 0.0
    if entry_day_active and risk_price <= 0 and not forced_close_after_stop_reentry:
        reasons.append("invalid_risk_price")

    sign = 1.0 if direction == "long" else -1.0
    stop_price = fill_price - sign * STOP_RETRY_R * risk_price if risk_price > 0 else 0.0
    progress_price = fill_price + sign * STOP_RETRY_R * risk_price if risk_price > 0 else 0.0
    if forced_close_after_stop_reentry and stop_price <= 0:
        stop_price = initial_stop_price if initial_stop_price > 0 else fill_price
        progress_price = fill_price
    adverse_hit = False
    progress_hit = False
    if risk_price > 0:
        if direction == "long":
            adverse_hit = adverse_extreme_price > 0 and adverse_extreme_price <= stop_price
            progress_hit = progress_extreme_price > 0 and progress_extreme_price >= progress_price
        else:
            adverse_hit = adverse_extreme_price > 0 and adverse_extreme_price >= stop_price
            progress_hit = progress_extreme_price > 0 and progress_extreme_price <= progress_price

    if not reasons:
        if forced_close_after_stop_reentry:
            action = "close_dry_run"
            reasons.append("stage901_pending_open_after_stage904_stop_close_forced_close")
        elif adverse_hit:
            action = "close_dry_run"
            reasons.append("stage847_initial_05r_stop_triggered")
        elif progress_hit:
            action = "watch_progress_hit_no_initial_stop"
            reasons.append("stage847_progress_hit_before_adverse")
        else:
            action = "watch"
            reasons.append("no_stage847_intraday_action")

    return {
        "target_date": target_date,
        "vt_symbol": vt_symbol,
        "direction": direction,
        "position_source": position_source,
        "volume": volume,
        "open_trade_id": _clean(open_trade.get("trade_id") if open_trade else ""),
        "open_trade_date": open_trade_date,
        "ledger_open_trade_date": ledger_open_trade_date,
        "ledger_open_trade_count": int(_to_float(ledger_open_trade.get("trade_count") if ledger_open_trade else 0, 0.0)),
        "ledger_open_trade_volume": _to_float(ledger_open_trade.get("volume") if ledger_open_trade else 0.0, 0.0),
        "ledger_open_source": ledger_open_source,
        "ledger_open_intent_id": ledger_open_intent_id,
        "entry_filled_at": entry_filled_at,
        "root_position_id": root_position_id,
        "position_cycle_id": _clean((ledger_open_trade or {}).get("position_cycle_id")),
        "position_cycle_no": int(_to_float((ledger_open_trade or {}).get("position_cycle_no"), 0.0)),
        "position_epoch_id": selected_position_epoch_id,
        "position_epoch_source": position_epoch_source,
        "intent_role": _clean((ledger_open_trade or {}).get("intent_role")),
        "broker_open_trade_date": broker_open_trade_date,
        "broker_open_trade_count": int(_to_float(broker_open_trade.get("trade_count") if broker_open_trade else 0, 0.0)),
        "broker_open_trade_volume": _to_float(broker_open_trade.get("volume") if broker_open_trade else 0.0, 0.0),
        "broker_epoch_reconstruction_complete": int(broker_epoch_complete),
        "broker_epoch_ledger_identity_match": int(ledger_matches_current_broker),
        "broker_position_epoch_entry_at": _clean((broker_open_trade or {}).get("position_epoch_entry_at")),
        "broker_position_epoch_fill_identity": _clean((broker_open_trade or {}).get("position_epoch_fill_identity")),
        "broker_position_epoch_trade_identities": list(
            (broker_open_trade or {}).get("position_epoch_trade_identities", [])
        ),
        "broker_position_epoch_trade_identity_complete": int(
            _to_float(
                (broker_open_trade or {}).get(
                    "position_epoch_trade_identity_complete"
                ),
                0.0,
            )
        ),
        "broker_position_epoch_order_ids": list(
            (broker_open_trade or {}).get("position_epoch_order_ids", [])
        ),
        "broker_position_epoch_order_identity_complete": int(
            _to_float(
                (broker_open_trade or {}).get(
                    "position_epoch_order_identity_complete"
                ),
                0.0,
            )
        ),
        "broker_position_epoch_reported_date": _clean(
            (broker_open_trade or {}).get("broker_reported_date")
        ),
        "broker_query_generation_uuid": broker_query_generation_uuid,
        "broker_query_trading_day": broker_query_trading_day,
        "broker_query_bundle_valid": int(broker_bundle_valid),
        "broker_query_bundle_reason": broker_bundle_reason,
        "broker_trade_snapshot_rows": int(len(broker_trades)),
        "entry_risk_date": risk_date,
        "entry_day_active": int(entry_day_active),
        "fill_price": fill_price,
        "fill_price_source": fill_price_source,
        "ledger_fill_price": ledger_fill_price,
        "broker_fill_price": broker_fill_price,
        "broker_position_avg_price": broker_position_avg_price,
        "broker_position_avg_price_source": broker_position_avg_price_source,
        "initial_stop_price": initial_stop_price,
        "risk_price": risk_price,
        "stop_retry_r": STOP_RETRY_R,
        "stage847_stop_price": stop_price,
        "stage847_progress_price": progress_price,
        "live_price": live_price,
        "live_price_source": live_price_source,
        "live_bid_price_1": _tick_value(tick, "bid_price_1"),
        "live_ask_price_1": _tick_value(tick, "ask_price_1"),
        "live_limit_up": _tick_value(tick, "limit_up", "upper_limit", "limit_up_price"),
        "live_limit_down": _tick_value(tick, "limit_down", "lower_limit", "limit_down_price"),
        "adverse_extreme_price": adverse_extreme_price,
        "adverse_extreme_source": adverse_extreme_source,
        "progress_extreme_price": progress_extreme_price,
        "progress_extreme_source": progress_extreme_source,
        "tick_batch_count": int(len(_tick_frame(ticks, vt_symbol))),
        "fresh_tick_batch_count": int(len(fresh_ticks)),
        "tick_age_seconds": tick_age,
        "mark_price_fallback": mark_price,
        "adverse_hit": int(adverse_hit),
        "progress_hit": int(progress_hit),
        "forced_close_after_stop_reentry": int(forced_close_after_stop_reentry),
        "monitor_action": action,
        "monitor_reason": ";".join(dict.fromkeys(reasons)),
        "order_api_called": 0,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _blocked_state_row(base: dict[str, Any], reason: str) -> dict[str, Any]:
    row = dict(base)
    row["monitor_action"] = "block"
    row["monitor_reason"] = reason
    row["order_api_called"] = 0
    row["checked_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return row


def _fail_closed_uncommitted_feed_cycle(
    *,
    store: dict[str, Any],
    base_rows: list[dict[str, Any]],
    commit_error: str,
) -> tuple[list[dict[str, Any]], int]:
    """Block this invocation without consuming ticks or persisting a gap.

    A mismatched Stage608 snapshot is indistinguishable from a publication
    interleaving until a stable generation can be read.  Returning blocked
    views while leaving ``store`` untouched prevents a normal race from
    permanently poisoning the exact-once feed state.
    """

    reason = f"tick_snapshot_commit_transient_fail_closed:{commit_error}"
    return (
        [_blocked_state_row(row, reason) for row in base_rows],
        len(store.get("states", {})),
    )


def _position_epoch_from_base(base: dict[str, Any]) -> str:
    propagated_epoch_id = _clean(base.get("position_epoch_id"))
    if propagated_epoch_id:
        return propagated_epoch_id
    target_date = _clean(base.get("target_date"))
    vt_symbol = _clean(base.get("vt_symbol"))
    direction = _normalize_direction(base.get("direction"))
    entry_filled_at = _clean(base.get("entry_filled_at"))
    entry_price = _to_float(base.get("fill_price"), 0.0)
    volume = int(round(_to_float(base.get("volume"), 0.0)))
    fill_identity = _clean(
        base.get("open_trade_id")
        or base.get("ledger_open_intent_id")
        or f"{entry_filled_at}|{entry_price}|{volume}"
    )
    if (
        not target_date
        or not vt_symbol
        or direction not in {"long", "short"}
        or not entry_filled_at
        or not fill_identity
    ):
        return ""
    return generate_position_epoch_id(
        target_date=target_date,
        vt_symbol=vt_symbol,
        direction=direction,
        entry_filled_at=entry_filled_at,
        fill_identity=fill_identity,
    )


def _latest_retry_unpriced_fill_evidence(
    state: dict[str, Any], execution_ledger_rows: list[dict[str, Any]]
) -> dict[str, Any] | None:
    matched: list[dict[str, Any]] = []
    for row in execution_ledger_rows:
        if _clean(row.get("event_type")) not in {
            "order_traded_volume_observed_without_trade_detail",
            "fill_reconciliation_pending",
        }:
            continue
        payload = _ledger_intent_payload(row)
        value = lambda key: row.get(key) or payload.get(key)
        if _clean(row.get("target_date")) != _clean(state.get("target_date")):
            continue
        if _ledger_vt_symbol(row) != _clean(state.get("vt_symbol")):
            continue
        if _ledger_direction(row) != _normalize_direction(state.get("direction")):
            continue
        if _ledger_offset(row) != "open":
            continue
        if _clean(value("root_position_id")) != _clean(state.get("root_position_id")):
            continue
        if _clean(value("position_epoch_id")) != _clean(state.get("position_epoch_id")):
            continue
        if _clean(value("position_cycle_id")) != _clean(state.get("position_cycle_id")):
            continue
        if _clean(value("intent_role")) != RETRY_OPEN_ACTION_ROLE:
            continue
        if _to_float(row.get("order_traded_volume"), 0.0) <= 0:
            continue
        matched.append(row)
    return matched[-1] if matched else None


def _mark_retry_fill_from_ledger(
    state: dict[str, Any], execution_ledger_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    if state.get("phase") not in {
        PHASE_RETRY_RECLAIM_LATCHED,
        PHASE_RETRY_OPEN,
        PHASE_RETRY_STOP_LATCHED,
    }:
        return state
    retry_fill = latest_position_cycle_open_fill(
        execution_ledger_rows,
        _clean(state.get("target_date")),
        _clean(state.get("vt_symbol")),
        _normalize_direction(state.get("direction")),
        root_position_id=_clean(state.get("root_position_id")),
        position_epoch_id=_clean(state.get("position_epoch_id")),
        intent_role=RETRY_OPEN_ACTION_ROLE,
    )
    unpriced = _latest_retry_unpriced_fill_evidence(state, execution_ledger_rows)
    priced_volume = int(round(_to_float((retry_fill or {}).get("volume"), 0.0)))
    unpriced_volume = int(
        round(_to_float((unpriced or {}).get("order_traded_volume"), 0.0))
    )
    retry_fill_volume = max(priced_volume, unpriced_volume)
    retry_fill_at = _clean(
        (retry_fill or {}).get("generated_at")
        or (unpriced or {}).get("generated_at")
    )
    retry_fill_price = _to_float((retry_fill or {}).get("price"), 0.0)
    if retry_fill_price <= 0 and unpriced_volume > 0:
        # The C9 retry stop remains anchored to the original entry/stop pair;
        # this provisional value is never used as a new risk threshold.
        retry_fill_price = _to_float(state.get("entry_price"), 0.0)
    if retry_fill_volume <= 0 or not retry_fill_at or retry_fill_price <= 0:
        return state
    if state.get("phase") == PHASE_RETRY_RECLAIM_LATCHED:
        result = mark_retry_filled(
            state,
            retry_fill_at=retry_fill_at,
            retry_fill_price=retry_fill_price,
            retry_fill_volume=retry_fill_volume,
        )
    else:
        result = update_current_position_volume(
            state,
            volume=retry_fill_volume,
        )
        result["retry_filled_volume"] = max(
            int(_to_float(result.get("retry_filled_volume"), 0.0)),
            retry_fill_volume,
        )
    result["retry_fill_price_source"] = (
        "event_trade_weighted_avg"
        if priced_volume >= retry_fill_volume and priced_volume > 0
        else "order_callback_traded_volume_price_pending_original_threshold_only"
    )
    result["retry_fill_reconciliation_pending"] = int(
        unpriced_volume > priced_volume
    )
    return result


def _apply_state_to_position_action(
    base: dict[str, Any],
    *,
    store: dict[str, Any],
    execution_ledger_rows: list[dict[str, Any]],
    ticks: pd.DataFrame,
    heartbeat: dict[str, Any],
    journal_path: Path,
    readonly_summary: dict[str, Any] | None = None,
    readonly_bundle_manifest: dict[str, Any] | None = None,
    readonly_bundle_evidence: dict[str, Any] | None = None,
    broker_positions: pd.DataFrame | None = None,
    max_tick_age_seconds: int = DEFAULT_STATE_TICK_MAX_AGE_SECONDS,
    execution_ledger_path: Path = LIVE_EXECUTION_LEDGER_PATH,
) -> dict[str, Any]:
    if int(_to_float(base.get("entry_day_active"), 0.0)) != 1:
        return base
    vt_symbol = _clean(base.get("vt_symbol"))
    direction = _normalize_direction(base.get("direction"))
    target_date = _clean(base.get("target_date"))
    root_position_id = _clean(base.get("root_position_id"))
    if not target_date or not vt_symbol or direction not in {"long", "short"} or not root_position_id:
        return _blocked_state_row(base, "state_identity_missing")

    states = store.setdefault("states", {})
    state = states.get(root_position_id)
    incoming_cycle_no = int(_to_float(base.get("position_cycle_no"), 0.0))
    incoming_epoch_id = ""
    if incoming_cycle_no == ATTEMPT_INITIAL:
        try:
            incoming_epoch_id = _position_epoch_from_base(base)
        except ValueError as exc:
            return _blocked_state_row(base, f"position_epoch_generation_failed:{exc}")
    if state is not None and incoming_cycle_no == ATTEMPT_INITIAL:
        if (
            _clean(state.get("phase")) == PHASE_RETRY_RECLAIM_LATCHED
            and _clean(base.get("position_source")) == "broker"
            and _to_float(base.get("volume"), 0.0) > 0
        ):
            decision = build_late_retry_fill_reconciliation(
                state=state,
                base=base,
                ledger_rows=execution_ledger_rows,
                readonly_summary=readonly_summary or {},
                bundle_manifest=readonly_bundle_manifest or {},
                bundle_evidence=readonly_bundle_evidence or {},
                max_snapshot_age_seconds=(
                    build_phase_d_config().hard_limits.max_snapshot_age_seconds
                ),
            )
            if _clean(decision.get("status")) == "reconciled":
                append_result = append_reconciled_execution_fill_once(
                    dict(decision.get("ledger_event") or {}),
                    execution_ledger_path,
                )
                append_blocker = _clean(append_result.get("blocker"))
                reconciled_event = append_result.get("ledger_event")
                if append_blocker or not isinstance(reconciled_event, dict) or not reconciled_event:
                    row = _blocked_state_row(
                        base,
                        "late_retry_fill_ledger_append_failed:"
                        f"{append_blocker or 'reconciled_event_missing'}",
                    )
                    row["manual_intervention_required"] = 1
                    row["risk_alert_level"] = "P1"
                    return row
                reconciliation_key = _clean(
                    reconciled_event.get("broker_reconciliation_key")
                )
                if not any(
                    _clean(item.get("broker_reconciliation_key"))
                    == reconciliation_key
                    for item in execution_ledger_rows
                ):
                    execution_ledger_rows.append(reconciled_event)
                base = {
                    **base,
                    "position_epoch_id": _clean(state.get("position_epoch_id")),
                    "position_epoch_source": (
                        "unique_late_retry_fill_broker_reconciliation"
                    ),
                    "position_cycle_id": _clean(state.get("position_cycle_id")),
                    "position_cycle_no": ATTEMPT_RETRY,
                    "intent_role": RETRY_OPEN_ACTION_ROLE,
                    "ledger_open_intent_id": _clean(
                        reconciled_event.get("intent_id")
                    ),
                    "ledger_open_source": "stage904_broker_reconciliation",
                    "ledger_fill_price": _to_float(
                        reconciled_event.get("price"), 0.0
                    ),
                    "broker_epoch_ledger_identity_match": 1,
                    "late_retry_fill_reconciled": 1,
                    "late_retry_fill_reconciliation_key": reconciliation_key,
                    "manual_intervention_required": 0,
                }
                incoming_cycle_no = ATTEMPT_RETRY
                incoming_epoch_id = ""
            elif _clean(decision.get("status")) == "blocked":
                row = _blocked_state_row(
                    base,
                    "late_retry_fill_reconciliation_ambiguous_fail_closed:"
                    f"{_clean(decision.get('reason'))}",
                )
                row["manual_intervention_required"] = 1
                row["risk_alert_level"] = "P1"
                row["recommended_operator_action"] = (
                    "verify_broker_order_trade_then_manual_protective_close"
                )
                return row
    if state is not None and incoming_cycle_no == ATTEMPT_INITIAL:
        stored_epoch_id = _clean(state.get("position_epoch_id"))
        if not incoming_epoch_id:
            return _blocked_state_row(base, "position_epoch_identity_missing")
        if incoming_epoch_id != stored_epoch_id:
            if _clean(state.get("phase")) == PHASE_DONE:
                # One root may legitimately host multiple independent broker
                # fills on the same trading day.  A terminal epoch can roll
                # forward; a live epoch mismatch must fail closed.
                state = None
            else:
                return _blocked_state_row(
                    base,
                    "position_epoch_mismatch_with_nonterminal_state_fail_closed:"
                    f"stored={stored_epoch_id};incoming={incoming_epoch_id}",
                )
    if state is None:
        if incoming_cycle_no == ATTEMPT_RETRY:
            return _blocked_state_row(base, "state_missing_for_existing_retry_cycle_fail_closed")
        entry_filled_at = _clean(base.get("entry_filled_at"))
        entry_price = _to_float(base.get("fill_price"), 0.0)
        original_stop_price = _to_float(base.get("initial_stop_price"), 0.0)
        volume = int(round(_to_float(base.get("volume"), 0.0)))
        if not entry_filled_at:
            return _blocked_state_row(base, "entry_filled_at_missing_for_state")
        if entry_price <= 0 or original_stop_price <= 0 or volume <= 0:
            return _blocked_state_row(base, "entry_price_stop_or_volume_invalid_for_state")
        try:
            state = new_state(
                target_date=target_date,
                vt_symbol=vt_symbol,
                direction=direction,
                position_epoch_id=incoming_epoch_id,
                entry_filled_at=entry_filled_at,
                entry_price=entry_price,
                original_stop_price=original_stop_price,
                volume=volume,
                stop_retry_r=STOP_RETRY_R,
            )
        except ValueError as exc:
            return _blocked_state_row(base, f"state_initialization_failed:{exc}")
        state["strategy_initial_stop_price"] = original_stop_price
        state["strategy_stop_price"] = _to_float(state.get("c9_stop_price"), 0.0)
        state["entry_risk_date"] = _clean(base.get("entry_risk_date"))
        state["open_trade_id"] = _clean(base.get("open_trade_id"))

    previous_revision = int(state.get("revision", 0))
    state = _mark_retry_fill_from_ledger(state, execution_ledger_rows)
    if (
        state.get("phase") == PHASE_INITIAL_STOP_LATCHED
        and _clean(base.get("position_source")) == "broker"
    ):
        broker_residual = int(round(_to_float(base.get("volume"), 0.0)))
        if broker_residual > 0:
            state = update_current_position_volume(
                state, volume=broker_residual
            )

    retry_broker_blocker = ""
    retry_position_volume_source = ""
    if state.get("phase") in {PHASE_RETRY_OPEN, PHASE_RETRY_STOP_LATCHED}:
        ledger_retry_volume = int(
            round(
                _to_float(
                    state.get("retry_filled_volume", state.get("current_position_volume")),
                    0.0,
                )
            )
        )
        if _clean(base.get("position_source")) != "broker":
            retry_broker_blocker = "retry_position_source_is_not_broker"
            broker_volume = 0.0
        elif readonly_summary is None or broker_positions is None:
            retry_broker_blocker = "retry_broker_position_generation_evidence_missing"
            broker_volume = 0.0
        else:
            broker_volume, retry_broker_blocker = _confirmed_broker_position_volume(
                readonly_summary=readonly_summary,
                broker_positions=broker_positions,
                vt_symbol=vt_symbol,
                direction=direction,
                readonly_bundle_manifest=readonly_bundle_manifest,
                readonly_bundle_evidence=readonly_bundle_evidence,
            )
            if broker_volume > 0:
                retry_broker_blocker = ""
        rounded_broker_volume = int(round(broker_volume))
        if broker_volume > 0 and abs(broker_volume - rounded_broker_volume) > 1e-9:
            retry_broker_blocker = f"retry_broker_position_volume_not_integral:{broker_volume}"
        if not retry_broker_blocker and rounded_broker_volume > 0:
            # The broker row is authoritative for the protective second stop;
            # it may be smaller than the retry target after a partial fill.
            state = update_current_position_volume(
                state, volume=rounded_broker_volume
            )
            retry_position_volume_source = "fresh_complete_broker_position_generation"
        elif ledger_retry_volume > 0:
            # EVENT_TRADE is definitive evidence that risk exists even when the
            # independently published readonly CSV has not refreshed yet.
            # Stage931 performs its own final same-connection position query
            # before sending and will fail closed if that broker volume is not
            # yet visible.
            state = update_current_position_volume(
                state, volume=ledger_retry_volume
            )
            retry_position_volume_source = "stage931_event_trade_fill_pending_broker_refresh"
            retry_broker_blocker = ""

    stream_ticks, tick_identity_errors = _ordered_stream_ticks(ticks, vt_symbol)
    gap_reason = _feed_gap_reason(
        state=state,
        heartbeat=heartbeat,
        tick_identity_errors=tick_identity_errors,
        max_tick_age_seconds=max_tick_age_seconds,
    )
    gap_reason = gap_reason or _tick_buffer_gap_reason(state, ticks, heartbeat)
    gap_reason = gap_reason or _preconsume_tick_gap_reason(state, stream_ticks)
    if gap_reason:
        state = mark_feed_gap(state, detected_at=datetime.now().isoformat(), reason=gap_reason)
    state = consume_ticks(state, stream_ticks)
    states[root_position_id] = state
    _append_state_journal(journal_path, previous_revision=previous_revision, state=state)

    pending = get_pending_action(state)
    phase = _clean(state.get("phase"))
    if (
        pending
        and pending.get("action") == "close"
        and int(_to_float(pending.get("attempt_no"), 0.0)) == ATTEMPT_RETRY
        and retry_broker_blocker
    ):
        monitor_action = "retry_block"
        monitor_reason = f"retry_stop_requires_fresh_broker_residual:{retry_broker_blocker}"
    elif pending and pending.get("action") == "close":
        monitor_action = "close_dry_run"
        monitor_reason = _clean(pending.get("reason"))
    elif pending and pending.get("action") == "open":
        monitor_action = "retry_open_dry_run"
        monitor_reason = _clean(pending.get("reason"))
    elif phase == PHASE_INITIAL_PROGRESS_LATCHED:
        monitor_action = "watch_progress_hit_no_initial_stop"
        monitor_reason = "initial_progress_latched_before_adverse"
    elif phase == PHASE_INITIAL_ARMED:
        monitor_action = "watch"
        monitor_reason = "initial_stop_state_armed"
    elif phase == PHASE_RETRY_WAIT:
        monitor_action = "retry_watch"
        monitor_reason = "retry_waiting_for_post_flat_reclaim"
    elif phase == PHASE_RETRY_RECLAIM_LATCHED:
        monitor_action = "retry_watch"
        monitor_reason = "retry_reclaim_latched_but_current_price_unfavorable"
    elif phase == PHASE_RETRY_OPEN:
        if retry_broker_blocker:
            monitor_action = "retry_block"
            monitor_reason = f"retry_open_requires_fresh_broker_position:{retry_broker_blocker}"
        else:
            monitor_action = "watch"
            monitor_reason = "retry_position_open_original_stop_armed"
    elif phase == PHASE_DONE:
        monitor_action = "watch"
        monitor_reason = "position_epoch_done"
    else:
        monitor_action = "block"
        monitor_reason = f"unexpected_state_phase:{phase}"

    result = {
        **base,
        "root_position_id": state["root_position_id"],
        "position_cycle_id": state["position_cycle_id"],
        "position_cycle_no": state["position_cycle_no"],
        "position_epoch_id": state["position_epoch_id"],
        "position_direction": state["direction"],
        "attempt_no": state["attempt_no"],
        "intent_role": _clean((pending or {}).get("intent_role")),
        "action_id": _clean((pending or {}).get("action_id")),
        "state_phase": phase,
        "state_revision": state.get("revision", 0),
        "feed_gap_latched": int(bool(state.get("feed_gap_latched"))),
        "feed_gap_reason": _clean(state.get("feed_gap_reason")),
        "strategy_entry_price": _to_float(state.get("entry_price"), 0.0),
        "strategy_initial_stop_price": _to_float(state.get("strategy_initial_stop_price"), 0.0),
        "strategy_stop_price": _to_float(state.get("c9_stop_price"), 0.0),
        "root_entry_price": _to_float(state.get("entry_price"), 0.0),
        "root_initial_stop_price": _to_float(state.get("strategy_initial_stop_price"), 0.0),
        "root_entry_volume": _to_float(state.get("volume"), 0.0),
        "stage847_stop_price": _to_float(state.get("c9_stop_price"), 0.0),
        "stage847_progress_price": _to_float(state.get("c9_progress_price"), 0.0),
        "stage847_retry_trigger_price": _to_float(state.get("entry_price"), 0.0),
        "retry_stop_price": _to_float(state.get("c9_stop_price"), 0.0),
        "retry_original_fill_price": _to_float(state.get("entry_price"), 0.0),
        "retry_position_volume_source": retry_position_volume_source,
        "monitor_action": monitor_action,
        "monitor_reason": monitor_reason,
        "order_api_called": 0,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if pending:
        if (
            pending.get("action") == "close"
            and int(_to_float(pending.get("attempt_no"), 0.0)) == ATTEMPT_RETRY
        ):
            result["volume"] = _to_float(pending.get("volume"), 0.0)
        elif pending.get("action") == "close":
            result["volume"] = _to_float(base.get("volume"), 0.0)
        else:
            result["volume"] = _to_float(state.get("volume"), 0.0)
    return result


def _state_only_action_row(
    state: dict[str, Any],
    *,
    ticks: pd.DataFrame,
    monitor_action: str,
    monitor_reason: str,
) -> dict[str, Any]:
    vt_symbol = _clean(state.get("vt_symbol"))
    tick = _tick_row(ticks, vt_symbol)
    live_price, live_price_source = _tick_price(tick)
    pending = get_pending_action(state)
    return {
        "target_date": state.get("target_date"),
        "vt_symbol": vt_symbol,
        "direction": state.get("direction"),
        "position_source": "durable_state_after_broker_flat",
        "volume": _to_float(
            (pending or {}).get("volume", state.get("volume")), 0.0
        ),
        "open_trade_id": _clean(state.get("open_trade_id")),
        "entry_risk_date": _clean(state.get("entry_risk_date")),
        "entry_day_active": 1,
        "fill_price": _to_float(state.get("entry_price"), 0.0),
        "fill_price_source": "durable_state_original_entry_fill",
        "initial_stop_price": _to_float(state.get("strategy_initial_stop_price"), 0.0),
        "risk_price": abs(_to_float(state.get("entry_price"), 0.0) - _to_float(state.get("strategy_initial_stop_price"), 0.0)),
        "stop_retry_r": STOP_RETRY_R,
        "stage847_stop_price": _to_float(state.get("c9_stop_price"), 0.0),
        "stage847_progress_price": _to_float(state.get("c9_progress_price"), 0.0),
        "stage847_retry_trigger_price": _to_float(state.get("entry_price"), 0.0),
        "live_price": live_price,
        "live_price_source": live_price_source,
        "live_bid_price_1": _tick_value(tick, "bid_price_1"),
        "live_ask_price_1": _tick_value(tick, "ask_price_1"),
        "live_limit_up": _tick_value(tick, "limit_up", "upper_limit", "limit_up_price"),
        "live_limit_down": _tick_value(tick, "limit_down", "lower_limit", "limit_down_price"),
        "tick_age_seconds": _tick_age(tick),
        "root_position_id": state.get("root_position_id"),
        "position_cycle_id": state.get("position_cycle_id"),
        "position_cycle_no": state.get("position_cycle_no"),
        "position_epoch_id": state.get("position_epoch_id"),
        "position_direction": state.get("direction"),
        "attempt_no": state.get("attempt_no"),
        "intent_role": _clean((pending or {}).get("intent_role")),
        "action_id": _clean((pending or {}).get("action_id")),
        "state_phase": state.get("phase"),
        "state_revision": state.get("revision", 0),
        "feed_gap_latched": int(bool(state.get("feed_gap_latched"))),
        "feed_gap_reason": _clean(state.get("feed_gap_reason")),
        "strategy_entry_price": _to_float(state.get("entry_price"), 0.0),
        "strategy_initial_stop_price": _to_float(state.get("strategy_initial_stop_price"), 0.0),
        "strategy_stop_price": _to_float(state.get("c9_stop_price"), 0.0),
        "root_entry_price": _to_float(state.get("entry_price"), 0.0),
        "root_initial_stop_price": _to_float(state.get("strategy_initial_stop_price"), 0.0),
        "root_entry_volume": _to_float(state.get("volume"), 0.0),
        "retry_trigger_price": _to_float(state.get("entry_price"), 0.0),
        "retry_stop_price": _to_float(state.get("c9_stop_price"), 0.0),
        "retry_original_fill_price": _to_float(state.get("entry_price"), 0.0),
        "close_fill_price_reconciliation_pending": int(
            _to_float(state.get("close_fill_price_reconciliation_pending"), 0.0)
        ),
        "close_volume_reconciliation_keys": list(
            state.get("close_volume_reconciliation_keys", [])
        ),
        "monitor_action": monitor_action,
        "monitor_reason": monitor_reason,
        "order_api_called": 0,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _complete_broker_position_generation(
    *,
    readonly_summary: dict[str, Any],
    broker_positions: pd.DataFrame,
    readonly_bundle_manifest: dict[str, Any] | None = None,
    readonly_bundle_evidence: dict[str, Any] | None = None,
) -> tuple[bool, str, str, str]:
    """Validate one complete, fresh Stage174 position-query generation."""

    bundle_ok, bundle_reason, _, _ = validate_readonly_query_bundle(
        readonly_summary=readonly_summary,
        bundle_manifest=readonly_bundle_manifest or {},
        bundle_evidence=readonly_bundle_evidence or {},
    )
    if not bundle_ok:
        return False, bundle_reason, "", ""
    summary_bundle = readonly_summary.get("broker_query_bundle", {})
    position_query = (
        (summary_bundle.get("queries", {}) or {}).get("positions", {})
        if isinstance(summary_bundle, dict)
        else {}
    )
    generated_at = _clean(position_query.get("completed_at"))
    age = _age_seconds(generated_at)
    hard_age = build_phase_d_config().hard_limits.max_snapshot_age_seconds
    if (
        not generated_at
        or age is None
        or age < -MAX_CLOCK_SKEW_SECONDS
        or age > hard_age
    ):
        return False, f"readonly_position_generation_stale:age={age}", generated_at, ""
    if _clean(readonly_summary.get("status")) != "readonly_snapshots_received":
        return (
            False,
            f"readonly_position_generation_status_invalid:{_clean(readonly_summary.get('status'))}",
            generated_at,
            "",
        )
    snapshot = (
        readonly_summary.get("broker_snapshot")
        if isinstance(readonly_summary.get("broker_snapshot"), dict)
        else {}
    )
    snapshot_state = _clean(snapshot.get("position_snapshot_state"))
    if snapshot_state not in {"confirmed_flat", "positions_received"}:
        return (
            False,
            f"position_snapshot_state_incomplete:{snapshot_state}",
            generated_at,
            snapshot_state,
        )
    if snapshot.get("position_query_last_seen") is not True:
        return False, "position_query_last_callback_missing", generated_at, snapshot_state
    error_rows = int(_to_float(snapshot.get("position_query_error_rows"), -1.0))
    if error_rows != 0:
        return False, f"position_query_error_rows:{error_rows}", generated_at, snapshot_state
    callback_rows = int(_to_float(snapshot.get("position_query_callback_rows"), 0.0))
    if callback_rows <= 0:
        return False, "position_query_callback_rows_missing", generated_at, snapshot_state

    actual_rows = int(len(broker_positions.drop_duplicates()))
    summary_rows = int(_to_float(snapshot.get("position_rows"), -1.0))
    if summary_rows < 0 or summary_rows != actual_rows:
        return (
            False,
            f"position_generation_row_count_mismatch:summary={summary_rows};csv={actual_rows}",
            generated_at,
            snapshot_state,
        )
    nonzero_rows = int(_to_float(snapshot.get("nonzero_position_rows"), -1.0))
    if nonzero_rows < 0:
        return (
            False,
            "position_generation_nonzero_row_count_missing",
            generated_at,
            snapshot_state,
        )
    if snapshot_state == "confirmed_flat" and (summary_rows != 0 or nonzero_rows != 0):
        return (
            False,
            "confirmed_flat_generation_contains_positions",
            generated_at,
            snapshot_state,
        )
    if snapshot_state == "positions_received" and nonzero_rows <= 0:
        return (
            False,
            "positions_received_generation_has_no_nonzero_rows",
            generated_at,
            snapshot_state,
        )
    return True, "complete_position_query_generation", generated_at, snapshot_state


def _confirmed_broker_flat_evidence(
    *,
    readonly_summary: dict[str, Any],
    broker_positions: pd.DataFrame,
    vt_symbol: str,
    direction: str,
    not_before: str = "",
    readonly_bundle_manifest: dict[str, Any] | None = None,
    readonly_bundle_evidence: dict[str, Any] | None = None,
) -> tuple[bool, str, str]:
    complete, reason, generated_at, _ = _complete_broker_position_generation(
        readonly_summary=readonly_summary,
        broker_positions=broker_positions,
        readonly_bundle_manifest=readonly_bundle_manifest,
        readonly_bundle_evidence=readonly_bundle_evidence,
    )
    if not complete:
        return False, reason, generated_at
    if not_before:
        try:
            snapshot_ts = pd.Timestamp(generated_at)
            cutoff_ts = pd.Timestamp(not_before)
            if snapshot_ts.tzinfo is None:
                snapshot_ts = snapshot_ts.tz_localize("Asia/Shanghai")
            else:
                snapshot_ts = snapshot_ts.tz_convert("Asia/Shanghai")
            if cutoff_ts.tzinfo is None:
                cutoff_ts = cutoff_ts.tz_localize("Asia/Shanghai")
            else:
                cutoff_ts = cutoff_ts.tz_convert("Asia/Shanghai")
            if snapshot_ts < cutoff_ts:
                return (
                    False,
                    "complete_flat_snapshot_precedes_close_fill:"
                    f"snapshot={generated_at};close_fill={not_before}",
                    generated_at,
                )
        except (TypeError, ValueError):
            return False, "flat_snapshot_or_close_fill_time_invalid", generated_at
    symbol_gross_volume = _broker_symbol_gross_volume(broker_positions, vt_symbol)
    if symbol_gross_volume > 0:
        return (
            False,
            f"target_symbol_gross_position_present_in_complete_snapshot:{symbol_gross_volume}",
            generated_at,
        )
    return True, "complete_position_query_target_symbol_flat", generated_at


def _close_reconciliation_result(status: str, reason: str, **extra: Any) -> dict[str, Any]:
    return {"status": status, "reason": reason, "events": [], **extra}


def _close_event_matches_state(
    row: dict[str, Any],
    *,
    payloads: dict[str, dict[str, Any]],
    state: dict[str, Any],
    intent_role: str,
) -> bool:
    value = lambda key: _ledger_event_value(row, payloads, key)
    return bool(
        _clean(row.get("target_date")) == _clean(state.get("target_date"))
        and _clean(value("vt_symbol")).upper()
        == _clean(state.get("vt_symbol")).upper()
        and _normalize_direction(value("direction"))
        == _opposite_direction(_normalize_direction(state.get("direction")))
        and _normalize_offset(value("offset")) == "close"
        and _clean(value("root_position_id"))
        == _clean(state.get("root_position_id"))
        and _clean(value("position_epoch_id"))
        == _clean(state.get("position_epoch_id"))
        and _clean(value("position_cycle_id"))
        == _clean(state.get("position_cycle_id"))
        and _clean(value("intent_role")) == intent_role
    )


def _close_order_key(row: dict[str, Any]) -> str:
    fingerprint = _clean(row.get("intent_fingerprint"))
    vt_orderid = _clean(row.get("vt_orderid"))
    return f"{fingerprint}\0{vt_orderid}" if fingerprint and vt_orderid else ""


def _priced_close_volume_by_order(rows: list[dict[str, Any]]) -> dict[str, float]:
    result: dict[str, float] = {}
    for row in rows:
        if _clean(row.get("event_type")) != "filled_or_part_filled":
            continue
        key = _close_order_key(row)
        if not key:
            continue
        result[key] = result.get(key, 0.0) + _to_float(
            row.get("trade_volume_delta", row.get("volume")), 0.0
        )
    return result


def _append_close_volume_reconciliation_once(
    event: dict[str, Any],
    *,
    execution_ledger_path: Path,
) -> dict[str, Any]:
    """Append one close-only reconciliation under the Stage904 state lock.

    The production caller holds the per-date Stage904 state lock, so the
    read/check/append sequence is serialized across monitor restarts.  The
    ledger append itself still uses the execution-ledger flock and fsync path.
    """

    key = _clean(event.get("close_volume_reconciliation_key"))
    if not key:
        return {"appended": False, "blocker": "close_reconciliation_key_missing"}
    current = read_execution_ledger(execution_ledger_path)
    integrity = next(
        (
            _clean(row.get("event_type"))
            for row in current
            if _clean(row.get("event_type"))
            in {"ledger_decode_error", "ledger_non_object_error", "ledger_checksum_error"}
        ),
        "",
    )
    if integrity:
        return {
            "appended": False,
            "blocker": f"ledger_integrity_error:{integrity}",
            "ledger_event": {},
        }
    existing = [
        row
        for row in current
        if _clean(row.get("close_volume_reconciliation_key")) == key
    ]
    if len(existing) > 1:
        return {
            "appended": False,
            "blocker": f"duplicate_close_reconciliation_key:{key}:count={len(existing)}",
            "ledger_event": {},
        }
    if existing:
        prior = existing[0]
        for field in (
            "event_type",
            "target_date",
            "intent_fingerprint",
            "vt_orderid",
            "position_epoch_id",
            "position_cycle_id",
            "intent_role",
            "reconciled_close_volume",
        ):
            if _clean(prior.get(field)) != _clean(event.get(field)):
                return {
                    "appended": False,
                    "blocker": (
                        f"close_reconciliation_key_payload_mismatch:{key}:field={field}"
                    ),
                    "ledger_event": {},
                }
        return {
            "appended": False,
            "blocker": "",
            "ledger_event": prior,
            "idempotent_replay": True,
        }
    durable = append_execution_ledger_event(event, execution_ledger_path)
    return {
        "appended": True,
        "blocker": "",
        "ledger_event": durable,
        "idempotent_replay": False,
    }


def _reconcile_late_stop_close_volume(
    *,
    state: dict[str, Any],
    intent_role: str,
    target_volume: float,
    execution_ledger_rows: list[dict[str, Any]],
    broker_orders: pd.DataFrame,
    broker_positions: pd.DataFrame,
    readonly_summary: dict[str, Any],
    readonly_bundle_manifest: dict[str, Any] | None,
    readonly_bundle_evidence: dict[str, Any] | None,
    execution_ledger_path: Path,
) -> dict[str, Any]:
    """Reconcile only a fully traded Stage904 stop-close with no trade price.

    Broker flatness alone is never sufficient.  Every reconciled physical
    order needs an exact durable Stage931 send/unpriced chain and an all-traded
    row from the same complete Stage174 query generation.
    """

    expected_phase = {
        INITIAL_STOP_ACTION_ROLE: PHASE_INITIAL_STOP_LATCHED,
        RETRY_STOP_ACTION_ROLE: PHASE_RETRY_STOP_LATCHED,
    }.get(intent_role)
    if not expected_phase or _clean(state.get("phase")) != expected_phase:
        return _close_reconciliation_result(
            "not_applicable", "close_reconciliation_role_or_phase_not_stop_close"
        )
    if target_volume <= 0:
        return _close_reconciliation_result(
            "blocked", "close_reconciliation_target_volume_invalid"
        )
    if broker_orders.empty:
        return _close_reconciliation_result(
            "not_applicable", "close_reconciliation_broker_order_snapshot_missing"
        )
    if not execution_ledger_path.exists():
        return _close_reconciliation_result(
            "blocked", "close_reconciliation_durable_ledger_missing"
        )

    # Re-read after the Stage904 state lock is held.  The list loaded before
    # that lock is intentionally not authoritative for an idempotent append.
    durable_rows = read_execution_ledger(execution_ledger_path)
    if any(
        _clean(row.get("event_type"))
        in {"ledger_decode_error", "ledger_non_object_error", "ledger_checksum_error"}
        for row in durable_rows
    ):
        return _close_reconciliation_result(
            "blocked", "close_reconciliation_ledger_integrity_error"
        )
    payloads = _event_payload_by_fingerprint(durable_rows)
    existing_fills = _fill_events_for_identity(
        durable_rows,
        target_date=_clean(state.get("target_date")),
        root_position_id=_clean(state.get("root_position_id")),
        position_epoch_id=_clean(state.get("position_epoch_id")),
        position_cycle_id=_clean(state.get("position_cycle_id")),
        intent_role=intent_role,
    )
    existing_reconciled = [
        row
        for row in existing_fills
        if _clean(row.get("event_type")) == CLOSE_VOLUME_RECONCILED_EVENT
    ]
    if _filled_volume(existing_fills) + 1e-9 >= target_volume and existing_reconciled:
        return _close_reconciliation_result(
            "reconciled",
            "durable_close_volume_reconciliation_already_present",
            events=existing_reconciled,
        )

    bundle_ok, bundle_reason, broker_trading_day, generation_uuid = (
        validate_readonly_query_bundle(
            readonly_summary=readonly_summary,
            bundle_manifest=readonly_bundle_manifest or {},
            bundle_evidence=readonly_bundle_evidence or {},
        )
    )
    if not bundle_ok:
        return _close_reconciliation_result("blocked", bundle_reason)

    matching_sends: list[tuple[int, dict[str, Any]]] = []
    for index, row in enumerate(durable_rows):
        if _clean(row.get("event_type")) != "send_order_called":
            continue
        if not _close_event_matches_state(
            row, payloads=payloads, state=state, intent_role=intent_role
        ):
            continue
        if not _close_order_key(row):
            return _close_reconciliation_result(
                "blocked", "close_reconciliation_send_identity_incomplete"
            )
        fingerprint = _clean(row.get("intent_fingerprint"))
        reserved_before_send = any(
            prior_index < index
            and _clean(prior.get("event_type")) == "reserved"
            and _clean(prior.get("intent_fingerprint")) == fingerprint
            and _close_event_matches_state(
                prior,
                payloads=payloads,
                state=state,
                intent_role=intent_role,
            )
            for prior_index, prior in enumerate(durable_rows)
        )
        if not reserved_before_send:
            return _close_reconciliation_result(
                "blocked",
                f"close_reconciliation_durable_reservation_missing:{fingerprint}",
            )
        matching_sends.append((index, row))
    if not matching_sends:
        return _close_reconciliation_result(
            "not_applicable", "close_reconciliation_durable_send_missing"
        )
    send_counts: dict[str, int] = {}
    for _, send in matching_sends:
        key = _close_order_key(send)
        send_counts[key] = send_counts.get(key, 0) + 1
    duplicate_send_keys = sorted(key for key, count in send_counts.items() if count != 1)
    if duplicate_send_keys:
        return _close_reconciliation_result(
            "blocked",
            f"close_reconciliation_duplicate_send_identity:{duplicate_send_keys}",
        )

    residual_blockers = []
    send_keys = set(send_counts)
    for row in durable_rows:
        if _clean(row.get("event_type")) not in CLOSE_RESIDUAL_BLOCKER_EVENTS:
            continue
        key = _close_order_key(row)
        if key in send_keys:
            residual_blockers.append(
                f"{_clean(row.get('event_type'))}:{key.replace(chr(0), '|')}"
            )
    if residual_blockers:
        return _close_reconciliation_result(
            "blocked",
            "close_reconciliation_residual_order_blocker:"
            + ";".join(residual_blockers),
        )

    priced_by_order = _priced_close_volume_by_order(existing_fills)
    broker_order_rows = broker_orders.drop_duplicates().to_dict(orient="records")
    target_symbol_nonterminal = [
        row
        for row in broker_order_rows
        if _clean(row.get("query_generation_uuid")) == generation_uuid
        and _clean(row.get("vt_symbol")).upper()
        == _clean(state.get("vt_symbol")).upper()
        and _clean(row.get("status")).lower()
        not in BROKER_TERMINAL_ORDER_STATUSES
    ]
    if target_symbol_nonterminal:
        identities = [
            _clean(row.get("vt_orderid")) or "identity_missing"
            for row in target_symbol_nonterminal
        ]
        return _close_reconciliation_result(
            "blocked",
            "close_reconciliation_target_symbol_active_or_unknown_broker_order:"
            f"{identities}",
        )
    candidate_events: list[dict[str, Any]] = []
    latest_evidence_at = ""
    for send_index, send in matching_sends:
        order_key = _close_order_key(send)
        requested_volume = _to_float(send.get("volume"), 0.0)
        if requested_volume <= 0:
            return _close_reconciliation_result(
                "blocked", f"close_reconciliation_send_volume_invalid:{order_key}"
            )
        if priced_by_order.get(order_key, 0.0) + 1e-9 >= requested_volume:
            continue
        fingerprint = _clean(send.get("intent_fingerprint"))
        vt_orderid = _clean(send.get("vt_orderid"))
        evidence_rows = [
            row
            for index, row in enumerate(durable_rows)
            if index > send_index
            and _clean(row.get("event_type")) in CLOSE_UNPRICED_EVIDENCE_EVENTS
            and _clean(row.get("intent_fingerprint")) == fingerprint
            and _clean(row.get("vt_orderid")) == vt_orderid
        ]
        full_evidence = [
            row
            for row in evidence_rows
            if abs(
                _to_float(row.get("order_traded_volume"), 0.0)
                - requested_volume
            )
            <= 1e-9
            and _to_float(row.get("unpriced_volume"), 0.0) > 0
            and _to_float(row.get("residual_volume"), 0.0) <= 1e-9
        ]
        if not full_evidence:
            continue
        evidence = full_evidence[-1]
        evidence_at = _clean(evidence.get("generated_at"))
        if not evidence_at:
            return _close_reconciliation_result(
                "blocked", f"close_reconciliation_evidence_time_missing:{order_key}"
            )
        latest_evidence_at = max(latest_evidence_at, evidence_at)

        exact_orders = [
            row
            for row in broker_order_rows
            if _clean(row.get("query_generation_uuid")) == generation_uuid
            and _clean(row.get("vt_orderid")) == vt_orderid
        ]
        if len(exact_orders) != 1:
            continue
        broker_order = exact_orders[0]
        if (
            int(_to_float(broker_order.get("stable_order_identity_complete"), 0.0))
            != 1
            or _clean(broker_order.get("status")).lower()
            not in BROKER_ALL_TRADED_STATUSES
            or _clean(broker_order.get("vt_symbol")).upper()
            != _clean(state.get("vt_symbol")).upper()
            or _normalize_direction(broker_order.get("direction"))
            != _opposite_direction(_normalize_direction(state.get("direction")))
            or _normalize_offset(broker_order.get("offset")) != "close"
            or abs(_to_float(broker_order.get("volume"), 0.0) - requested_volume)
            > 1e-9
            or abs(
                _to_float(broker_order.get("traded"), 0.0)
                - requested_volume
            )
            > 1e-9
        ):
            continue

        key_payload = {
            "target_date": _clean(state.get("target_date")),
            "position_epoch_id": _clean(state.get("position_epoch_id")),
            "position_cycle_id": _clean(state.get("position_cycle_id")),
            "intent_role": intent_role,
            "intent_fingerprint": fingerprint,
            "vt_orderid": vt_orderid,
            "reconciled_close_volume": requested_volume,
        }
        reconciliation_key = "late-close-" + hashlib.sha256(
            _canonical_json(key_payload).encode("utf-8")
        ).hexdigest()[:24]
        candidate_events.append(
            {
                "event_type": CLOSE_VOLUME_RECONCILED_EVENT,
                "target_date": _clean(state.get("target_date")),
                "generated_at": "",  # Bound to the flat query completion below.
                "reconciled_at": datetime.now().isoformat(timespec="microseconds"),
                "intent_id": _clean(send.get("intent_id")),
                "intent_fingerprint": fingerprint,
                "vt_symbol": _clean(state.get("vt_symbol")),
                "vt_orderid": vt_orderid,
                "direction": _opposite_direction(
                    _normalize_direction(state.get("direction"))
                ),
                "offset": "close",
                "root_position_id": _clean(state.get("root_position_id")),
                "position_epoch_id": _clean(state.get("position_epoch_id")),
                "position_cycle_id": _clean(state.get("position_cycle_id")),
                "position_cycle_no": int(
                    _to_float(state.get("position_cycle_no"), 0.0)
                ),
                "intent_role": intent_role,
                "reconciled_close_volume": requested_volume,
                "broker_order_volume": _to_float(broker_order.get("volume"), 0.0),
                "broker_order_traded_volume": _to_float(
                    broker_order.get("traded"), 0.0
                ),
                "broker_order_status": _clean(broker_order.get("status")),
                "unpriced_volume": _to_float(evidence.get("unpriced_volume"), 0.0),
                "fill_price_reconciliation_pending": 1,
                "fill_price_source": "event_trade_detail_missing",
                "volume_evidence_source": (
                    "durable_order_traded_full_plus_same_generation_order_and_flat"
                ),
                "close_volume_reconciliation_key": reconciliation_key,
                "broker_query_generation_uuid": generation_uuid,
                "broker_trading_day": broker_trading_day,
                "unpriced_evidence_type": _clean(evidence.get("event_type")),
                "unpriced_evidence_at": evidence_at,
            }
        )

    if not candidate_events:
        return _close_reconciliation_result(
            "not_applicable",
            "close_reconciliation_exact_full_order_or_unpriced_evidence_missing",
        )

    # The position query must be from the same validated bundle and at/after
    # the latest durable unpriced observation.  This is the anti position-only
    # inference boundary.
    flat_ok, flat_reason, flat_at = _confirmed_broker_flat_evidence(
        readonly_summary=readonly_summary,
        broker_positions=broker_positions,
        vt_symbol=_clean(state.get("vt_symbol")),
        direction=_normalize_direction(state.get("direction")),
        not_before=latest_evidence_at,
        readonly_bundle_manifest=readonly_bundle_manifest,
        readonly_bundle_evidence=readonly_bundle_evidence,
    )
    if not flat_ok:
        return _close_reconciliation_result("blocked", flat_reason)
    query_metadata = (
        (readonly_summary.get("broker_query_bundle") or {}).get("queries", {})
        if isinstance(readonly_summary.get("broker_query_bundle"), dict)
        else {}
    )
    order_query_started = _clean(
        (query_metadata.get("orders") or {}).get("request_sent_at")
    )
    try:
        query_started_ts = pd.Timestamp(order_query_started)
        evidence_ts = pd.Timestamp(latest_evidence_at)
        if query_started_ts.tzinfo is None:
            query_started_ts = query_started_ts.tz_localize("Asia/Shanghai")
        if evidence_ts.tzinfo is None:
            evidence_ts = evidence_ts.tz_localize("Asia/Shanghai")
        if query_started_ts < evidence_ts - pd.Timedelta(
            seconds=MAX_CLOCK_SKEW_SECONDS
        ):
            return _close_reconciliation_result(
                "blocked", "close_reconciliation_query_precedes_unpriced_evidence"
            )
    except (TypeError, ValueError):
        return _close_reconciliation_result(
            "blocked", "close_reconciliation_query_or_evidence_time_invalid"
        )

    hypothetical = [*existing_fills]
    for event in candidate_events:
        event["generated_at"] = flat_at
        event["broker_flat_confirmed_at"] = flat_at
        hypothetical.append(event)
    proven_volume = _filled_volume(hypothetical)
    if proven_volume + 1e-9 < target_volume:
        return _close_reconciliation_result(
            "blocked",
            f"close_reconciliation_proven_volume_partial:{proven_volume}<{target_volume}",
        )
    if proven_volume > target_volume + 1e-9:
        return _close_reconciliation_result(
            "blocked",
            f"close_reconciliation_proven_volume_exceeds_target:{proven_volume}>{target_volume}",
        )

    durable_events: list[dict[str, Any]] = []
    for event in candidate_events:
        append_result = _append_close_volume_reconciliation_once(
            event, execution_ledger_path=execution_ledger_path
        )
        blocker = _clean(append_result.get("blocker"))
        ledger_event = append_result.get("ledger_event")
        if blocker or not isinstance(ledger_event, dict) or not ledger_event:
            return _close_reconciliation_result(
                "blocked",
                "close_reconciliation_ledger_append_failed:"
                f"{blocker or 'ledger_event_missing'}",
            )
        durable_events.append(ledger_event)
        reconciliation_key = _clean(
            ledger_event.get("close_volume_reconciliation_key")
        )
        if not any(
            _clean(row.get("close_volume_reconciliation_key"))
            == reconciliation_key
            for row in execution_ledger_rows
        ):
            execution_ledger_rows.append(ledger_event)
    return _close_reconciliation_result(
        "reconciled",
        "late_stop_close_volume_proven_without_trade_price",
        events=durable_events,
    )


def _confirmed_broker_position_volume(
    *,
    readonly_summary: dict[str, Any],
    broker_positions: pd.DataFrame,
    vt_symbol: str,
    direction: str,
    readonly_bundle_manifest: dict[str, Any] | None = None,
    readonly_bundle_evidence: dict[str, Any] | None = None,
) -> tuple[float, str]:
    complete, reason, _, _ = _complete_broker_position_generation(
        readonly_summary=readonly_summary,
        broker_positions=broker_positions,
        readonly_bundle_manifest=readonly_bundle_manifest,
        readonly_bundle_evidence=readonly_bundle_evidence,
    )
    if not complete:
        return 0.0, reason
    volume = 0.0
    for row in broker_positions.drop_duplicates().to_dict(orient="records"):
        if (
            _vt_symbol(row) == vt_symbol
            and _normalize_direction(row.get("direction")) == direction
        ):
            volume += _broker_position_volume(row)
    if volume <= 0:
        return 0.0, "target_position_missing_from_complete_snapshot"
    return volume, "complete_position_query_target_present"


def _advance_flat_states(
    *,
    store: dict[str, Any],
    execution_ledger_rows: list[dict[str, Any]],
    broker_positions: pd.DataFrame,
    readonly_summary: dict[str, Any],
    ticks: pd.DataFrame,
    heartbeat: dict[str, Any],
    represented_roots: set[str],
    journal_path: Path,
    max_tick_age_seconds: int,
    readonly_bundle_manifest: dict[str, Any] | None = None,
    readonly_bundle_evidence: dict[str, Any] | None = None,
    broker_orders: pd.DataFrame | None = None,
    execution_ledger_path: Path = LIVE_EXECUTION_LEDGER_PATH,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    states = store.setdefault("states", {})
    broker_order_frame = (
        broker_orders if isinstance(broker_orders, pd.DataFrame) else pd.DataFrame()
    )
    for root_position_id, original in list(states.items()):
        if root_position_id in represented_roots:
            continue
        state = original
        previous_revision = int(state.get("revision", 0))
        state = _mark_retry_fill_from_ledger(state, execution_ledger_rows)
        phase = _clean(state.get("phase"))
        if phase == PHASE_INITIAL_STOP_LATCHED:
            target_close_volume = _to_float(state.get("volume"), 0.0)
            fills = _fill_events_for_identity(
                execution_ledger_rows,
                target_date=_clean(state.get("target_date")),
                root_position_id=root_position_id,
                position_epoch_id=_clean(state.get("position_epoch_id")),
                position_cycle_id=_clean(state.get("position_cycle_id")),
                intent_role=INITIAL_STOP_ACTION_ROLE,
            )
            reconciliation_reason = "priced_close_volume_already_sufficient"
            if _filled_volume(fills) + 1e-9 < target_close_volume:
                reconciliation = _reconcile_late_stop_close_volume(
                    state=state,
                    intent_role=INITIAL_STOP_ACTION_ROLE,
                    target_volume=target_close_volume,
                    execution_ledger_rows=execution_ledger_rows,
                    broker_orders=broker_order_frame,
                    broker_positions=broker_positions,
                    readonly_summary=readonly_summary,
                    readonly_bundle_manifest=readonly_bundle_manifest,
                    readonly_bundle_evidence=readonly_bundle_evidence,
                    execution_ledger_path=execution_ledger_path,
                )
                reconciliation_reason = _clean(reconciliation.get("reason"))
                for event in reconciliation.get("events", []):
                    key = _clean(event.get("close_volume_reconciliation_key"))
                    if key and not any(
                        _clean(item.get("close_volume_reconciliation_key")) == key
                        for item in execution_ledger_rows
                    ):
                        execution_ledger_rows.append(event)
                fills = _fill_events_for_identity(
                    execution_ledger_rows,
                    target_date=_clean(state.get("target_date")),
                    root_position_id=root_position_id,
                    position_epoch_id=_clean(state.get("position_epoch_id")),
                    position_cycle_id=_clean(state.get("position_cycle_id")),
                    intent_role=INITIAL_STOP_ACTION_ROLE,
                )
            flat_evidence_ok, flat_evidence_reason, broker_snapshot_at = (
                _confirmed_broker_flat_evidence(
                    readonly_summary=readonly_summary,
                    broker_positions=broker_positions,
                    vt_symbol=_clean(state.get("vt_symbol")),
                    direction=_normalize_direction(state.get("direction")),
                    not_before=_latest_fill_at(fills) if fills else "",
                    readonly_bundle_manifest=readonly_bundle_manifest,
                    readonly_bundle_evidence=readonly_bundle_evidence,
                )
            )
            if (
                _filled_volume(fills) + 1e-9
                >= target_close_volume
                and flat_evidence_ok
            ):
                state = arm_retry_after_close(
                    state,
                    close_fill_at=_latest_fill_at(fills),
                    broker_flat_at=broker_snapshot_at,
                )
                reconciled = [
                    row
                    for row in fills
                    if _clean(row.get("event_type"))
                    == CLOSE_VOLUME_RECONCILED_EVENT
                ]
                if reconciled:
                    state["close_fill_price_reconciliation_pending"] = 1
                    state["close_volume_reconciliation_keys"] = [
                        _clean(row.get("close_volume_reconciliation_key"))
                        for row in reconciled
                    ]
                    state["close_volume_reconciliation_source"] = (
                        "same_generation_broker_order_and_flat"
                    )
            else:
                reason = (
                    "initial_stop_flat_but_close_fill_or_complete_flat_snapshot_missing:"
                    f"{flat_evidence_reason};close_reconciliation={reconciliation_reason}"
                )
                rows.append(_state_only_action_row(state, ticks=ticks, monitor_action="retry_block", monitor_reason=reason))
        elif phase == PHASE_RETRY_STOP_LATCHED:
            close_target_volume = _to_float(
                state.get("current_position_volume", state.get("volume")), 0.0
            )
            fills = _fill_events_for_identity(
                execution_ledger_rows,
                target_date=_clean(state.get("target_date")),
                root_position_id=root_position_id,
                position_epoch_id=_clean(state.get("position_epoch_id")),
                position_cycle_id=_clean(state.get("position_cycle_id")),
                intent_role=RETRY_STOP_ACTION_ROLE,
            )
            reconciliation_reason = "priced_close_volume_already_sufficient"
            if _filled_volume(fills) + 1e-9 < close_target_volume:
                reconciliation = _reconcile_late_stop_close_volume(
                    state=state,
                    intent_role=RETRY_STOP_ACTION_ROLE,
                    target_volume=close_target_volume,
                    execution_ledger_rows=execution_ledger_rows,
                    broker_orders=broker_order_frame,
                    broker_positions=broker_positions,
                    readonly_summary=readonly_summary,
                    readonly_bundle_manifest=readonly_bundle_manifest,
                    readonly_bundle_evidence=readonly_bundle_evidence,
                    execution_ledger_path=execution_ledger_path,
                )
                reconciliation_reason = _clean(reconciliation.get("reason"))
                for event in reconciliation.get("events", []):
                    key = _clean(event.get("close_volume_reconciliation_key"))
                    if key and not any(
                        _clean(item.get("close_volume_reconciliation_key")) == key
                        for item in execution_ledger_rows
                    ):
                        execution_ledger_rows.append(event)
                fills = _fill_events_for_identity(
                    execution_ledger_rows,
                    target_date=_clean(state.get("target_date")),
                    root_position_id=root_position_id,
                    position_epoch_id=_clean(state.get("position_epoch_id")),
                    position_cycle_id=_clean(state.get("position_cycle_id")),
                    intent_role=RETRY_STOP_ACTION_ROLE,
                )
            flat_evidence_ok, flat_evidence_reason, broker_snapshot_at = (
                _confirmed_broker_flat_evidence(
                    readonly_summary=readonly_summary,
                    broker_positions=broker_positions,
                    vt_symbol=_clean(state.get("vt_symbol")),
                    direction=_normalize_direction(state.get("direction")),
                    not_before=_latest_fill_at(fills) if fills else "",
                    readonly_bundle_manifest=readonly_bundle_manifest,
                    readonly_bundle_evidence=readonly_bundle_evidence,
                )
            )
            if (
                _filled_volume(fills) + 1e-9 >= close_target_volume
                and flat_evidence_ok
            ):
                state = mark_position_flat(state, flat_at=broker_snapshot_at)
                reconciled = [
                    row
                    for row in fills
                    if _clean(row.get("event_type"))
                    == CLOSE_VOLUME_RECONCILED_EVENT
                ]
                if reconciled:
                    state["close_fill_price_reconciliation_pending"] = 1
                    state["close_volume_reconciliation_keys"] = [
                        _clean(row.get("close_volume_reconciliation_key"))
                        for row in reconciled
                    ]
                    state["close_volume_reconciliation_source"] = (
                        "same_generation_broker_order_and_flat"
                    )
            else:
                rows.append(
                    _state_only_action_row(
                        state,
                        ticks=ticks,
                        monitor_action="retry_block",
                        monitor_reason=(
                            "retry_stop_flat_but_close_fill_or_complete_flat_snapshot_missing:"
                            f"{flat_evidence_reason};close_reconciliation={reconciliation_reason}"
                        ),
                    )
                )
        elif phase == PHASE_RETRY_OPEN:
            # A trade callback can arrive before the next broker position CSV.
            # Consume risk ticks and persist the protected phase immediately,
            # but do not publish an executable close until the fresh broker row
            # supplies the exact residual volume.
            stream_ticks, tick_identity_errors = _ordered_stream_ticks(
                ticks, _clean(state.get("vt_symbol"))
            )
            gap_reason = _feed_gap_reason(
                state=state,
                heartbeat=heartbeat,
                tick_identity_errors=tick_identity_errors,
                max_tick_age_seconds=max_tick_age_seconds,
            )
            gap_reason = gap_reason or _tick_buffer_gap_reason(
                state, ticks, heartbeat
            )
            gap_reason = gap_reason or _preconsume_tick_gap_reason(
                state, stream_ticks
            )
            if gap_reason:
                state = mark_feed_gap(
                    state,
                    detected_at=datetime.now().isoformat(),
                    reason=gap_reason,
                )
            state = consume_ticks(state, stream_ticks)
            if state.get("phase") == PHASE_RETRY_STOP_LATCHED:
                monitor_action = "close_dry_run"
                pending = get_pending_action(state)
                reason = _clean((pending or {}).get("reason")) or "retry_failed_at_c9_stop"
            else:
                monitor_action = "retry_watch"
                reason = "retry_fill_protected_from_ledger_while_broker_snapshot_refreshes"
            rows.append(
                _state_only_action_row(
                    state,
                    ticks=ticks,
                    monitor_action=monitor_action,
                    monitor_reason=reason,
                )
            )

        if state.get("phase") in {PHASE_RETRY_WAIT, PHASE_RETRY_RECLAIM_LATCHED}:
            stream_ticks, tick_identity_errors = _ordered_stream_ticks(ticks, _clean(state.get("vt_symbol")))
            gap_reason = _feed_gap_reason(
                state=state,
                heartbeat=heartbeat,
                tick_identity_errors=tick_identity_errors,
                max_tick_age_seconds=max_tick_age_seconds,
            )
            gap_reason = gap_reason or _tick_buffer_gap_reason(state, ticks, heartbeat)
            gap_reason = gap_reason or _preconsume_tick_gap_reason(
                state, stream_ticks
            )
            if gap_reason:
                state = mark_feed_gap(state, detected_at=datetime.now().isoformat(), reason=gap_reason)
            state = consume_ticks(state, stream_ticks)
            pending = get_pending_action(state)
            latest_tick_age = _tick_age(_tick_row(ticks, _clean(state.get("vt_symbol"))))
            retry_tick_fresh = _tick_age_is_fresh(
                latest_tick_age, max_tick_age_seconds
            )
            if pending and pending.get("action") == "open" and retry_tick_fresh:
                rows.append(
                    _state_only_action_row(
                        state,
                        ticks=ticks,
                        monitor_action="retry_open_dry_run",
                        monitor_reason="post_flat_original_entry_reclaimed",
                    )
                )
            elif pending and pending.get("action") == "open" and not retry_tick_fresh:
                rows.append(
                    _state_only_action_row(
                        state,
                        ticks=ticks,
                        monitor_action="retry_block",
                        monitor_reason=f"retry_current_tick_stale:age={latest_tick_age}",
                    )
                )
            elif state.get("feed_gap_latched"):
                rows.append(
                    _state_only_action_row(
                        state,
                        ticks=ticks,
                        monitor_action="retry_block",
                        monitor_reason=f"retry_blocked_feed_gap:{_clean(state.get('feed_gap_reason'))}",
                    )
                )
            else:
                rows.append(
                    _state_only_action_row(
                        state,
                        ticks=ticks,
                        monitor_action="retry_watch",
                        monitor_reason="retry_waiting_for_post_flat_reclaim",
                    )
                )
        states[root_position_id] = state
        _append_state_journal(journal_path, previous_revision=previous_revision, state=state)
    return rows


def _to_markdown(df: pd.DataFrame, columns: list[str], max_rows: int = 80) -> str:
    if df.empty:
        return "_empty_"
    return df.loc[:, [column for column in columns if column in df.columns]].head(max_rows).to_markdown(index=False)


def _build_report(summary: dict[str, Any], actions: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Stage904 Official Live C9 Intraday Monitor",
            "",
            f"- 生成时间：`{summary['generated_at']}`",
            f"- 当前官方实盘：`{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- 目标日期：`{summary['target_date']}`",
            f"- monitor 状态：`{summary['monitor_status']}`",
            f"- 动作数：`{summary['action_count']}`",
            f"- close dry-run 数：`{summary['close_dry_run_count']}`",
            f"- retry open dry-run 数：`{summary['retry_open_dry_run_count']}`",
            f"- order API 调用次数：`{summary['order_api_called_count']}`",
            "",
            "## Actions",
            "",
            _to_markdown(
                actions,
                [
                    "vt_symbol",
                    "direction",
                    "position_source",
                    "volume",
                    "fill_price",
                    "fill_price_source",
                    "initial_stop_price",
                    "stage847_stop_price",
                    "stage847_progress_price",
                    "stage847_retry_trigger_price",
                    "live_price",
                    "adverse_extreme_price",
                    "progress_extreme_price",
                    "fresh_tick_batch_count",
                    "tick_age_seconds",
                    "retry_open_attempted",
                    "monitor_action",
                    "monitor_reason",
                ],
            ),
            "",
            "## 说明",
            "",
            "- 本阶段只计算 C9 入场日 `0.5R` 止损/重试状态，不连接 CTP，不下单。",
            "- 没有 fresh tick 时必须 fail-closed，不能用历史收盘价触发实盘动作。",
            "- 止损后重试只允许一次，且必须先看到真实初始开仓成交、真实止损平仓成交、broker 对应方向空仓和 fresh tick 重回原开仓价。",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run C9 intraday 0.5R stop/retry monitor for official live.")
    parser.add_argument("--target-date", default="", help="Target completed trading day. Defaults to official summary analysis_end.")
    parser.add_argument("--max-tick-age-seconds", type=int, default=10)
    parser.add_argument("--require-broker-fill-price", action="store_true")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    official_summary = _read_json(OFFICIAL_LIVE_SUMMARY_PATH)
    target_date = args.target_date or str(official_summary.get("analysis_end", ""))
    monitor_run_id = (
        f"stage904-{target_date.replace('-', '') or 'latest'}-"
        f"{datetime.now():%Y%m%dT%H%M%S%f}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    )
    paths = _paths(target_date)
    # Clear executable views before any reducer work.  If the process crashes,
    # Stage905 must observe no stale close/retry intent from a previous cycle.
    _atomic_write_df(paths["actions_csv"], pd.DataFrame())
    _atomic_write_text(
        paths["summary_json"],
        json.dumps(
            {
                "model_tag": MODEL_TAG,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "target_date": target_date,
                "monitor_run_id": monitor_run_id,
                "monitor_status": "intraday_monitor_running_fail_closed",
                "order_api_called_count": 0,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    positions = _read_csv_maybe(OFFICIAL_LIVE_CURRENT_POSITIONS_PATH)
    broker_positions = _read_csv_maybe(
        READONLY_POSITIONS_PATH, preserve_identity=True
    )
    broker_orders = _read_csv_maybe(
        READONLY_ORDERS_PATH, preserve_identity=True
    )
    broker_trades = _read_csv_maybe(
        READONLY_TRADES_PATH, preserve_identity=True
    )
    execution_ledger_rows = read_execution_ledger()
    trades = _read_csv_maybe(STAGE901_TRADES_PATH)
    entry_risk = _read_csv_maybe(STAGE901_ENTRY_RISK_PATH)
    (
        ticks,
        tick_stream_heartbeat,
        tick_snapshot_commit_error,
    ) = _read_committed_tick_snapshot(
        READONLY_TICKS_PATH,
        TICK_STREAM_HEARTBEAT_PATH,
    )
    readonly_summary = _read_json(READONLY_SUMMARY_PATH)
    readonly_bundle_manifest = _read_json(READONLY_QUERY_BUNDLE_MANIFEST_PATH)
    readonly_bundle_evidence = _build_readonly_query_bundle_evidence(
        broker_orders=broker_orders,
        broker_trades=broker_trades,
        broker_positions=broker_positions,
    )
    config = build_phase_d_config()
    monitor_positions = _monitor_positions(positions, broker_positions)
    paths["state_lock"].parent.mkdir(parents=True, exist_ok=True)
    state_store_error = ""
    action_rows: list[dict[str, Any]] = []
    state_count = 0
    with paths["state_lock"].open("a+", encoding="utf-8") as state_lock:
        fcntl.flock(state_lock.fileno(), fcntl.LOCK_EX)
        # The pre-lock read is useful for building base rows, but close-volume
        # reconciliation must see any Stage931 append that raced with lock
        # acquisition before it performs its own idempotent ledger append.
        execution_ledger_rows = read_execution_ledger()
        try:
            state_store = _load_state_store(
                paths["state_json"],
                target_date,
                journal_path=paths["state_journal"],
            )
        except Exception as exc:
            state_store = None
            state_store_error = f"state_corrupt_fail_closed:{exc}"

        candidate_positions = monitor_positions
        if args.require_broker_fill_price and not candidate_positions.empty and "position_source" in candidate_positions.columns:
            candidate_positions = candidate_positions[candidate_positions["position_source"].astype(str).eq("broker")].copy()

        base_rows = [
            _action_for_position(
                row,
                trades=trades,
                broker_trades=broker_trades,
                execution_ledger_rows=execution_ledger_rows,
                entry_risk=entry_risk,
                ticks=ticks,
                target_date=target_date,
                max_tick_age_seconds=args.max_tick_age_seconds,
                require_broker_fill_price=bool(args.require_broker_fill_price),
                readonly_summary=readonly_summary,
                readonly_bundle_manifest=readonly_bundle_manifest,
                readonly_bundle_evidence=readonly_bundle_evidence,
            )
            for row in candidate_positions.to_dict(orient="records")
        ]
        if state_store is None:
            action_rows.extend(_blocked_state_row(row, state_store_error) for row in base_rows)
        elif tick_snapshot_commit_error:
            # Do not call either reducer and do not checkpoint the state store.
            # A normal Stage608 two-file publication race must block only this
            # invocation, never persist mark_feed_gap/tick_buffer_overrun.
            action_rows, state_count = _fail_closed_uncommitted_feed_cycle(
                store=state_store,
                base_rows=base_rows,
                commit_error=tick_snapshot_commit_error,
            )
        else:
            for base in base_rows:
                try:
                    action_rows.append(
                        _apply_state_to_position_action(
                            base,
                            store=state_store,
                            execution_ledger_rows=execution_ledger_rows,
                            ticks=ticks,
                            heartbeat=tick_stream_heartbeat,
                            journal_path=paths["state_journal"],
                            readonly_summary=readonly_summary,
                            readonly_bundle_manifest=readonly_bundle_manifest,
                            readonly_bundle_evidence=readonly_bundle_evidence,
                            broker_positions=broker_positions,
                            max_tick_age_seconds=args.max_tick_age_seconds,
                        )
                    )
                except Exception as exc:
                    action_rows.append(_blocked_state_row(base, f"state_reducer_exception_fail_closed:{exc}"))

            represented_broker_roots: set[str] = set()
            for row in broker_positions.drop_duplicates().to_dict(orient="records"):
                vt_symbol = _vt_symbol(row)
                direction = _normalize_direction(row.get("direction"))
                if vt_symbol and direction in {"long", "short"} and _broker_position_gross_volume(row) > 0:
                    represented_broker_roots.add(
                        generate_root_position_id(target_date=target_date, vt_symbol=vt_symbol, direction=direction)
                    )
            action_rows.extend(
                _advance_flat_states(
                    store=state_store,
                    execution_ledger_rows=execution_ledger_rows,
                    broker_positions=broker_positions,
                    readonly_summary=readonly_summary,
                    ticks=ticks,
                    heartbeat=tick_stream_heartbeat,
                    represented_roots=represented_broker_roots,
                    journal_path=paths["state_journal"],
                    max_tick_age_seconds=args.max_tick_age_seconds,
                    readonly_bundle_manifest=readonly_bundle_manifest,
                    readonly_bundle_evidence=readonly_bundle_evidence,
                    broker_orders=broker_orders,
                    execution_ledger_path=LIVE_EXECUTION_LEDGER_PATH,
                )
            )
            state_count = len(state_store.get("states", {}))
            _commit_state_store_and_checkpoint(
                paths["state_json"],
                paths["state_journal"],
                state_store,
            )
        fcntl.flock(state_lock.fileno(), fcntl.LOCK_UN)
    for row in action_rows:
        row["monitor_run_id"] = monitor_run_id
    actions = pd.DataFrame(action_rows)
    close_dry_run_count = int(actions.get("monitor_action", pd.Series(dtype=str)).astype(str).eq("close_dry_run").sum()) if not actions.empty else 0
    retry_open_dry_run_count = int(actions.get("monitor_action", pd.Series(dtype=str)).astype(str).eq("retry_open_dry_run").sum()) if not actions.empty else 0
    retry_watch_count = int(actions.get("monitor_action", pd.Series(dtype=str)).astype(str).eq("retry_watch").sum()) if not actions.empty else 0
    blocked_count = int(actions.get("monitor_action", pd.Series(dtype=str)).astype(str).isin(["block", "retry_block"]).sum()) if not actions.empty else 0
    order_api_called = int(actions.get("order_api_called", pd.Series(dtype=float)).sum()) if not actions.empty else 0
    monitor_status = "intraday_monitor_ready"
    if blocked_count or state_store_error or tick_snapshot_commit_error:
        monitor_status = "intraday_monitor_blocked"
    elif retry_open_dry_run_count:
        monitor_status = "intraday_monitor_retry_open_dry_run"
    elif close_dry_run_count:
        monitor_status = "intraday_monitor_close_dry_run"

    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_date": target_date,
        "monitor_run_id": monitor_run_id,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "monitor_status": monitor_status,
        "action_count": int(len(actions)),
        "blocked_count": blocked_count,
        "close_dry_run_count": close_dry_run_count,
        "retry_open_dry_run_count": retry_open_dry_run_count,
        "retry_watch_count": retry_watch_count,
        "order_api_called_count": order_api_called,
        "readonly_status": readonly_summary.get("status", ""),
        "tick_path": str(READONLY_TICKS_PATH.resolve()),
        "monitor_max_tick_age_seconds": int(args.max_tick_age_seconds),
        "require_broker_fill_price": int(bool(args.require_broker_fill_price)),
        "shadow_position_rows": int(len(positions)),
        "broker_position_rows": int(len(broker_positions)),
        "broker_order_rows": int(len(broker_orders)),
        "broker_trade_rows": int(len(broker_trades)),
        "broker_query_bundle_generation_uuid": _clean(
            readonly_bundle_manifest.get("generation_uuid")
        ),
        "broker_query_bundle_complete": int(
            readonly_bundle_manifest.get("complete") is True
        ),
        "execution_ledger_rows": int(len(execution_ledger_rows)),
        "monitor_position_rows": int(len(monitor_positions)),
        "retry_candidate_rows": int(actions.get("monitor_action", pd.Series(dtype=str)).astype(str).isin(["retry_watch", "retry_open_dry_run", "retry_block"]).sum()) if not actions.empty else 0,
        "durable_state_count": state_count,
        "durable_state_error": state_store_error,
        "durable_state_path": str(paths["state_json"].resolve()),
        "durable_state_journal_path": str(paths["state_journal"].resolve()),
        "tick_stream_heartbeat_path": str(TICK_STREAM_HEARTBEAT_PATH.resolve()),
        "tick_stream_ready": int(bool(tick_stream_heartbeat.get("stream_ready"))),
        "tick_stream_feed_session_id": _clean(tick_stream_heartbeat.get("feed_session_id")),
        "tick_snapshot_commit_generation_uuid": _clean(
            (
                tick_stream_heartbeat.get("tick_snapshot_commit")
                if isinstance(
                    tick_stream_heartbeat.get("tick_snapshot_commit"), dict
                )
                else {}
            ).get("generation_uuid")
        ),
        "tick_snapshot_commit_error": tick_snapshot_commit_error,
        "phase_d_hard_limits": config.hard_limits.__dict__,
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。C9 盘中监控只复刻已冻结的 0.5R 止损/重试状态机，不改参数。",
            "continue_before": "是。没有盘中监控，C9 无法全自动执行入场日风控。",
            "overfit_after": "否。没有根据监控结果调整策略。",
            "continue_after": "是。Stage904 已能产出初始止损和平仓后一次重试开仓候选，下一步由 Stage905/931 承接为真实 order intent。",
        },
    }
    _atomic_write_df(paths["actions_csv"], actions)
    _atomic_write_text(paths["summary_json"], json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    _atomic_write_text(paths["report_md"], _build_report(summary, actions))
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
