from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import signal
import threading
import time
import uuid
from collections import deque
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from vnpy.event import EventEngine
from vnpy.trader.constant import Exchange
from vnpy.trader.engine import MainEngine
from vnpy.trader.event import EVENT_ACCOUNT, EVENT_CONTRACT, EVENT_LOG, EVENT_ORDER, EVENT_POSITION, EVENT_TICK, EVENT_TRADE
from vnpy.trader.object import SubscribeRequest

from qmt_roll_live_context_adapter import collect_snapshot_from_main_engine
from qmt_roll_official_live_tick_stream import (
    DurableTickSnapshot,
    JournalRecoveryResult,
    JOURNAL_BATCH_COMMIT_SCHEMA_VERSION,
    JOURNAL_FORMAT_FRAMED_V1,
    JOURNAL_SCHEMA_FRAMED_V1,
    SymbolDurableWatermark,
    TickStreamGap,
    TickStreamPipeline,
    acknowledge_committed_recovery_manifest,
    acknowledge_recovery_manifest,
    install_gateway_tick_ingress,
    recover_or_isolate_dirty_tail,
)
from qmt_roll_official_live_time import SystemClock


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage608_readonly_tick_snapshot_probe_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage608_readonly_tick_snapshot_probe"
TICK_SNAPSHOT_COMMIT_SCHEMA_VERSION: int = 1
SYMBOL_EVICTION_WATERMARK_SCHEMA_VERSION: int = 1
SYSTEM_CLOCK = SystemClock()


def _snapshot_stream_collections(
    lock: threading.Lock,
    *,
    logs: list[dict[str, Any]],
    tick_buffer: deque[dict[str, Any]],
    latest_by_symbol: dict[str, dict[str, Any]],
    sequence: int,
) -> dict[str, Any]:
    """Copy callback-owned state under one short critical section."""

    with lock:
        copied_ticks = list(tick_buffer)
        published_sequence = max(
            (int(row.get("stream_sequence", 0) or 0) for row in copied_ticks),
            default=0,
        )
        return {
            "logs": list(logs),
            "ticks": copied_ticks,
            "latest_by_symbol": dict(latest_by_symbol),
            # Never advertise a sequence before the same snapshot contains
            # its row; the callback may still be fsyncing the journal outside
            # this lock.
            "sequence": min(int(sequence), published_sequence),
        }


def _symbol_tick_watermarks(
    watched_symbols: list[str],
    latest_by_symbol: dict[str, dict[str, Any]],
    durable_watermarks: Mapping[str, SymbolDurableWatermark] | None = None,
) -> dict[str, dict[str, Any]]:
    """Publish one bounded, durable liveness marker per currently watched symbol."""

    result: dict[str, dict[str, Any]] = {}
    for vt_symbol in sorted({_clean(item) for item in watched_symbols if _clean(item)}):
        row = latest_by_symbol.get(vt_symbol) or {}
        durable = (durable_watermarks or {}).get(vt_symbol)
        result[vt_symbol] = {
            "received_at": _clean(row.get("received_at")),
            "stream_sequence": int(row.get("stream_sequence", 0) or 0),
            "symbol_stream_sequence": int(
                row.get("symbol_stream_sequence", row.get("stream_sequence", 0))
                or 0
            ),
            "durable_symbol_sequence": int(
                durable.durable_symbol_sequence if durable is not None else 0
            ),
            "first_buffered_symbol_sequence": int(
                durable.first_buffered_symbol_sequence if durable is not None else 0
            ),
            "evicted_through_symbol_sequence": int(
                durable.evicted_through_symbol_sequence if durable is not None else 0
            ),
        }
    return result


SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
ACCOUNT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_accounts_{MODEL_TAG}.csv"
POSITION_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
ORDER_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_orders_{MODEL_TAG}.csv"
TRADE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
CONTRACT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contracts_{MODEL_TAG}.csv"
TICK_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ticks_{MODEL_TAG}.csv"
LOG_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_logs_{MODEL_TAG}.csv"
TARGET_SYMBOL_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_target_symbols_{MODEL_TAG}.csv"
POSITION_QUERY_CALLBACK_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_position_query_callbacks_{MODEL_TAG}.csv"
STREAM_JOURNAL_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tick_stream_{MODEL_TAG}.ndjson"
STREAM_HEARTBEAT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tick_stream_heartbeat_{MODEL_TAG}.json"

DEFAULT_SUBMIT_PLAN = OUTPUT_DIR / (
    "qmt_roll_stage591_stage526_bridge_submit_adapter_dry_run_"
    "submit_plan_stage591_stage526_bridge_submit_adapter_dry_run_v1.csv"
)

CTP_ENV_KEYS: dict[str, str] = {
    "userid": "CTP_USERID",
    "password": "CTP_PASSWORD",
    "brokerid": "CTP_BROKERID",
    "td_address": "CTP_TD_ADDRESS",
    "md_address": "CTP_MD_ADDRESS",
    "appid": "CTP_APPID",
    "auth_code": "CTP_AUTH_CODE",
    "product_info": "CTP_PRODUCT_INFO",
}


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return f"{value[:2]}***{value[-2:]}"


def _env_status() -> dict[str, Any]:
    status: dict[str, Any] = {}
    for logical_name, env_key in CTP_ENV_KEYS.items():
        value = os.getenv(env_key, "")
        status[logical_name] = {
            "env_key": env_key,
            "configured": bool(value),
            "masked_value": _mask(value) if logical_name in {"userid", "brokerid"} else "",
        }
    return status


def _required_env_missing() -> list[str]:
    required = ["userid", "password", "brokerid", "td_address", "md_address", "appid", "auth_code"]
    return [CTP_ENV_KEYS[name] for name in required if not os.getenv(CTP_ENV_KEYS[name], "")]


def _gateway_import_status() -> dict[str, Any]:
    if not importlib.util.find_spec("vnpy_ctp"):
        return {
            "vnpy_ctp_spec_available": False,
            "ctp_gateway_import_available": False,
            "error": "vnpy_ctp module spec not found",
        }
    try:
        from vnpy_ctp import CtpGateway

        return {
            "vnpy_ctp_spec_available": True,
            "ctp_gateway_import_available": True,
            "default_name": getattr(CtpGateway, "default_name", ""),
            "error": "",
        }
    except Exception as exc:
        return {
            "vnpy_ctp_spec_available": True,
            "ctp_gateway_import_available": False,
            "default_name": "",
            "error": repr(exc),
        }


def _ctp_setting_from_env() -> dict[str, Any]:
    return {
        "用户名": os.getenv("CTP_USERID", ""),
        "密码": os.getenv("CTP_PASSWORD", ""),
        "经纪商代码": os.getenv("CTP_BROKERID", ""),
        "交易服务器": os.getenv("CTP_TD_ADDRESS", ""),
        "行情服务器": os.getenv("CTP_MD_ADDRESS", ""),
        "产品名称": os.getenv("CTP_APPID", ""),
        "授权编码": os.getenv("CTP_AUTH_CODE", ""),
        "产品信息": os.getenv("CTP_PRODUCT_INFO", ""),
    }


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _prior_authority_lineage(
    previous_heartbeat: dict[str, Any],
) -> dict[str, Any]:
    return {
        "prior_authoritative_feed_session_id": _clean(
            previous_heartbeat.get("feed_session_id")
        ),
        "prior_authoritative_journal_segment_path": _clean(
            previous_heartbeat.get("journal_segment_path")
            or previous_heartbeat.get("journal_path")
        ),
        "prior_authoritative_heartbeat_revision_uuid": _clean(
            previous_heartbeat.get("heartbeat_revision_uuid")
        ),
        "prior_authoritative_journal_session_state": _clean(
            previous_heartbeat.get("journal_session_state")
        ),
        "prior_authoritative_clean_shutdown": (
            previous_heartbeat.get("clean_shutdown") is True
        ),
    }


def _clean_empty_feed_bridge(
    previous_heartbeat: dict[str, Any],
) -> dict[str, Any] | None:
    required_state = {
        "journal_authority_committed": True,
        "journal_session_state": "clean_stopped",
        "clean_shutdown": True,
        "stopped": True,
        "stream_ready": False,
        "transport_ready": False,
        "writer_alive": False,
        "accepting": False,
        "gap_latched": False,
    }
    if any(previous_heartbeat.get(key) != value for key, value in required_state.items()):
        return None
    if (
        previous_heartbeat.get("writer_fault") not in (None, "", {})
        or previous_heartbeat.get("dropped_tick_count") != 0
        or previous_heartbeat.get("queue_depth") != 0
        or previous_heartbeat.get("last_ingress_sequence") != 0
        or previous_heartbeat.get("durable_ingress_sequence") != 0
        or previous_heartbeat.get("durable_journal_byte_offset") != 0
        or _clean(previous_heartbeat.get("journal_schema"))
        != JOURNAL_SCHEMA_FRAMED_V1
        or previous_heartbeat.get("prior_uncommitted_gaps") != []
    ):
        return None
    empty_feed = _clean(previous_heartbeat.get("feed_session_id"))
    empty_path = _clean(
        previous_heartbeat.get("journal_segment_path")
        or previous_heartbeat.get("journal_path")
    )
    empty_revision = _clean(previous_heartbeat.get("heartbeat_revision_uuid"))
    prior_feed = _clean(
        previous_heartbeat.get("prior_authoritative_feed_session_id")
    )
    prior_path = _clean(
        previous_heartbeat.get("prior_authoritative_journal_segment_path")
    )
    prior_revision = _clean(
        previous_heartbeat.get("prior_authoritative_heartbeat_revision_uuid")
    )
    recovered = previous_heartbeat.get("recovery_previous_durable_cursor")
    if (
        not empty_feed
        or not empty_path
        or not empty_revision
        or not prior_feed
        or not prior_path
        or not prior_revision
        or previous_heartbeat.get("prior_authoritative_journal_session_state")
        != "clean_stopped"
        or previous_heartbeat.get("prior_authoritative_clean_shutdown") is not True
        or not isinstance(recovered, dict)
        or _clean(recovered.get("feed_session_id")) != prior_feed
        or type(recovered.get("ingress_sequence")) is not int
        or recovered.get("ingress_sequence") <= 0
        or type(recovered.get("journal_byte_offset")) is not int
        or recovered.get("journal_byte_offset") <= 0
        or _clean(recovered.get("journal_schema")) != JOURNAL_SCHEMA_FRAMED_V1
    ):
        return None
    existing = previous_heartbeat.get(
        "prior_authoritative_empty_feed_sessions",
        [],
    )
    if not isinstance(existing, list) or len(existing) >= 64:
        return None
    required_empty_fields = {
        "feed_session_id",
        "journal_segment_path",
        "heartbeat_revision_uuid",
        "journal_session_state",
        "clean_shutdown",
        "durable_ingress_sequence",
        "durable_journal_byte_offset",
    }
    seen_feeds: set[str] = set()
    for item in existing:
        if not isinstance(item, dict) or set(item) != required_empty_fields:
            return None
        feed = _clean(item.get("feed_session_id"))
        if (
            not feed
            or feed in {prior_feed, empty_feed}
            or feed in seen_feeds
            or not _clean(item.get("journal_segment_path"))
            or not _clean(item.get("heartbeat_revision_uuid"))
            or item.get("journal_session_state") != "clean_stopped"
            or item.get("clean_shutdown") is not True
            or item.get("durable_ingress_sequence") != 0
            or item.get("durable_journal_byte_offset") != 0
        ):
            return None
        seen_feeds.add(feed)
    empty_record = {
        "feed_session_id": empty_feed,
        "journal_segment_path": empty_path,
        "heartbeat_revision_uuid": empty_revision,
        "journal_session_state": "clean_stopped",
        "clean_shutdown": True,
        "durable_ingress_sequence": 0,
        "durable_journal_byte_offset": 0,
    }
    return {
        "lineage": {
            "prior_authoritative_feed_session_id": prior_feed,
            "prior_authoritative_journal_segment_path": prior_path,
            "prior_authoritative_heartbeat_revision_uuid": prior_revision,
            "prior_authoritative_journal_session_state": "clean_stopped",
            "prior_authoritative_clean_shutdown": True,
        },
        "recovery_previous_durable_cursor": dict(recovered),
        "empty_feed_sessions": [*existing, empty_record],
    }


def _split_vt_symbol(vt_symbol: str) -> tuple[str, Exchange] | None:
    if "." not in vt_symbol:
        return None
    symbol, exchange_text = vt_symbol.rsplit(".", 1)
    symbol = symbol.strip()
    exchange_text = exchange_text.strip()
    if not symbol or not exchange_text:
        return None
    try:
        return symbol, Exchange(exchange_text)
    except ValueError:
        return None


def _load_target_symbols(submit_plan: Path | None, cli_symbols: list[str]) -> list[str]:
    symbols: list[str] = []
    for item in cli_symbols:
        text = _clean(item)
        if text:
            symbols.append(text)
    if submit_plan and submit_plan.exists():
        frame = pd.read_csv(submit_plan, encoding="utf-8-sig")
        if "vt_symbol" in frame.columns:
            for item in frame["vt_symbol"].dropna().astype(str):
                text = _clean(item)
                if text:
                    symbols.append(text)
    seen: set[str] = set()
    result: list[str] = []
    for symbol in symbols:
        if symbol not in seen:
            result.append(symbol)
            seen.add(symbol)
    return result


def _object_to_row(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if is_dataclass(obj):
        row = asdict(obj)
    elif hasattr(obj, "__dict__"):
        row = dict(obj.__dict__)
    else:
        row = {"value": str(obj)}
    for attr in ["vt_symbol", "vt_orderid", "vt_tradeid", "vt_positionid", "vt_accountid", "available"]:
        if hasattr(obj, attr):
            row[attr] = getattr(obj, attr)
    for key, value in list(row.items()):
        if isinstance(value, (datetime, pd.Timestamp)):
            row[key] = value.isoformat()
        elif hasattr(value, "value"):
            row[key] = value.value
        elif isinstance(value, (dict, list, tuple, set)):
            row[key] = json.dumps(value, ensure_ascii=False, default=str)
        elif value is None:
            row[key] = ""
    row.setdefault("snapshot_at", datetime.now().isoformat())
    return row


def _write_df(path: Path, rows: list[dict[str, Any]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def _fsync_parent(path: Path) -> None:
    directory_fd = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _fsync_directory_fd(directory_fd: int) -> None:
    os.fsync(directory_fd)


def _invalidate_open_authority(handle: Any) -> None:
    """Make an already-open authority inode durably unreadable."""

    handle.seek(0)
    handle.truncate(0)
    handle.flush()
    os.fsync(handle.fileno())
    if os.fstat(handle.fileno()).st_size != 0:
        raise OSError("authority invalidation size remained nonzero")


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Durably publish one complete artifact before its commit record."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    prior_handle: Any = None
    directory_fd: int | None = None
    try:
        with temporary.open("w+b") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            if path.exists():
                prior_handle = path.open("r+b")
            try:
                # Acquire the directory capability before replace so EMFILE
                # cannot strand a newly visible authority without a barrier.
                directory_fd = os.open(str(path.parent), os.O_RDONLY)
            except Exception as publication_error:
                if prior_handle is not None:
                    try:
                        _invalidate_open_authority(prior_handle)
                    except Exception as invalidation_error:
                        raise RuntimeError(
                            "atomic_publish_authority_invalidation_failed;"
                            f" publication={publication_error!r};"
                            f" invalidation={invalidation_error!r}"
                        ) from publication_error
                raise
            os.replace(temporary, path)
            try:
                _fsync_directory_fd(directory_fd)
            except Exception as publication_error:
                invalidation_errors: list[str] = []
                for label, authority_handle in (
                    ("replacement", handle),
                    ("pre_replace", prior_handle),
                ):
                    if authority_handle is None:
                        continue
                    try:
                        _invalidate_open_authority(authority_handle)
                    except Exception as invalidation_error:
                        invalidation_errors.append(
                            f"{label}={invalidation_error!r}"
                        )
                if invalidation_errors:
                    raise RuntimeError(
                        "atomic_publish_authority_invalidation_failed;"
                        f" publication={publication_error!r};"
                        " invalidation=" + ",".join(invalidation_errors)
                    ) from publication_error
                raise
    finally:
        if directory_fd is not None:
            os.close(directory_fd)
        if prior_handle is not None:
            prior_handle.close()
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _atomic_write_text(path: Path, text: str) -> None:
    """Publish a complete file so readers never observe a partial snapshot."""

    _atomic_write_bytes(path, text.encode("utf-8"))


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _atomic_write_df(path: Path, rows: list[dict[str, Any]]) -> None:
    _atomic_write_bytes(path, _dataframe_csv_bytes(rows))


def _startup_attempt_path(heartbeat_path: Path) -> Path:
    return heartbeat_path.with_name(f"{heartbeat_path.name}.startup_attempt.json")


def _load_active_lifecycle_guard(
    heartbeat_path: Path,
) -> tuple[dict[str, Any], str]:
    path = _startup_attempt_path(heartbeat_path)
    if not path.exists():
        return {}, ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, repr(exc)
    if not isinstance(payload, dict):
        return {}, "lifecycle guard root must be a JSON object"
    if payload.get("lifecycle_guard_active") is True:
        return payload, ""
    return {}, ""


def _publish_lifecycle_guard(
    heartbeat_path: Path,
    *,
    feed_session_id: str,
    summary: Mapping[str, Any],
    phase: str = "startup_handoff",
    previous_heartbeat: Mapping[str, Any] | None = None,
    owner_pid: int | None = None,
) -> dict[str, Any]:
    if phase not in {"startup_handoff", "terminal_commit"}:
        raise ValueError("lifecycle_guard_phase_invalid")
    previous_heartbeat = previous_heartbeat or {}
    payload = {
        "schema_version": 1,
        "guard_uuid": uuid.uuid4().hex,
        "owner_pid": os.getpid() if owner_pid is None else int(owner_pid),
        "feed_session_id": feed_session_id,
        "created_at": datetime.now().isoformat(timespec="microseconds"),
        "status": "stream_lifecycle_in_progress",
        "phase": phase,
        "lifecycle_guard_active": True,
        "recovery_blocked": True,
        "journal_authority_unsafe": True,
        "stream_ready": False,
        "transport_ready": False,
        "stopped": False,
        "heartbeat_path": str(heartbeat_path.resolve()),
        "journal_segment_path": _clean(
            summary.get("journal_segment_path")
        ),
        "prior_heartbeat_revision_uuid": _clean(
            previous_heartbeat.get("heartbeat_revision_uuid")
        ),
        "capture_quiesced": bool(summary.get("gateway_capture_quiesced")),
        "writer_quiesced": bool(summary.get("writer_quiesced")),
        "pipeline_quiesced": bool(summary.get("pipeline_quiesced")),
    }
    _atomic_write_json(_startup_attempt_path(heartbeat_path), payload)
    return payload


def _publish_startup_attempt_unless_guarded(
    heartbeat_path: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    guard, guard_error = _load_active_lifecycle_guard(heartbeat_path)
    if guard or guard_error:
        return guard
    _atomic_write_json(_startup_attempt_path(heartbeat_path), payload)
    return payload


def _clear_lifecycle_guard(heartbeat_path: Path) -> None:
    path = _startup_attempt_path(heartbeat_path)
    path.unlink(missing_ok=True)
    _fsync_parent(path)


def _fault_stopped_authority(
    previous_heartbeat: Mapping[str, Any],
    *,
    terminal_reason: str,
) -> dict[str, Any]:
    payload = {
        **dict(previous_heartbeat),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "tick_stream_fault_stopped",
        "terminal_reason": terminal_reason,
        "stream_ready": False,
        "transport_ready": False,
        "writer_alive": False,
        "accepting": False,
        "stopped": True,
        "clean_shutdown": False,
        "journal_session_state": "fault_stopped",
        "recovery_blocked": True,
        "heartbeat_revision_uuid": uuid.uuid4().hex,
    }
    payload.pop("tick_snapshot_commit", None)
    payload.pop("tick_snapshot_generation_uuid", None)
    return payload


def _authority_is_strictly_stopped(
    heartbeat: Mapping[str, Any],
) -> bool:
    state = _clean(heartbeat.get("journal_session_state"))
    if state == "clean_stopped":
        expected_clean_shutdown = True
    elif state in {"recovery_required_stopped", "fault_stopped"}:
        expected_clean_shutdown = False
    else:
        return False
    return bool(
        heartbeat.get("journal_authority_committed") is True
        and heartbeat.get("stopped") is True
        and heartbeat.get("clean_shutdown") is expected_clean_shutdown
        and heartbeat.get("stream_ready") is False
        and heartbeat.get("transport_ready") is False
        and heartbeat.get("writer_alive") is False
        and heartbeat.get("accepting") is not True
    )


def _revoke_unclean_previous_authority_before_recovery(
    heartbeat_path: Path,
    *,
    previous_heartbeat: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Revoke orphan running readiness before any recovery or CTP work."""

    previous = dict(previous_heartbeat)
    if not previous or previous.get("journal_authority_committed") is not True:
        return previous, {}
    state = _clean(previous.get("journal_session_state"))
    allowed_states = {
        "starting",
        "running",
        "clean_stopped",
        "recovery_required_stopped",
        "fault_stopped",
    }
    if state not in allowed_states:
        raise RuntimeError("prior_authority_state_invalid")
    if _authority_is_strictly_stopped(previous):
        return previous, {}
    previous_segment = _clean(
        previous.get("journal_segment_path")
        or previous.get("journal_path")
    )
    if not previous_segment:
        raise RuntimeError("prior_authority_journal_segment_missing")
    prior_feed_session_id = _clean(previous.get("feed_session_id"))
    if not prior_feed_session_id:
        raise RuntimeError("prior_authority_feed_session_missing")
    _publish_lifecycle_guard(
        heartbeat_path,
        feed_session_id=prior_feed_session_id,
        summary={"journal_segment_path": previous_segment},
        phase="startup_handoff",
        previous_heartbeat=previous,
    )
    revoked = _fault_stopped_authority(
        previous,
        terminal_reason="orphan_authority_before_recovery",
    )
    _atomic_write_json(heartbeat_path, revoked)
    _clear_lifecycle_guard(heartbeat_path)
    return revoked, {
        "prior_authority_revoked_before_recovery": True,
        "prior_authority_revoked_feed_session_id": _clean(
            previous.get("feed_session_id")
        ),
    }


def _reconcile_lifecycle_guard(
    heartbeat_path: Path,
    *,
    previous_heartbeat: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Consume dead-owner evidence while the caller owns the stream lock."""

    guard, guard_error = _load_active_lifecycle_guard(heartbeat_path)
    if guard_error:
        raise RuntimeError(f"lifecycle_guard_read_error:{guard_error}")
    if not guard:
        return dict(previous_heartbeat), {}
    guard_uuid = _clean(guard.get("guard_uuid"))
    guard_feed = _clean(guard.get("feed_session_id"))
    guard_phase = _clean(guard.get("phase"))
    guard_segment = _clean(guard.get("journal_segment_path"))
    guard_owner_pid = guard.get("owner_pid")
    if (
        type(guard.get("schema_version")) is not int
        or guard.get("schema_version") != 1
        or len(guard_uuid) != 32
        or any(character not in "0123456789abcdef" for character in guard_uuid)
        or not guard_feed
        or guard_phase not in {"startup_handoff", "terminal_commit"}
        or type(guard_owner_pid) is not int
        or guard_owner_pid <= 0
        or not guard_segment
        or _clean(guard.get("heartbeat_path"))
        != str(heartbeat_path.resolve())
    ):
        raise RuntimeError("lifecycle_guard_contract_invalid")

    previous = dict(previous_heartbeat)
    previous_feed = _clean(previous.get("feed_session_id"))
    if guard_phase == "startup_handoff" and previous_feed != guard_feed:
        expected_revision = _clean(
            guard.get("prior_heartbeat_revision_uuid")
        )
        observed_revision = _clean(
            previous.get("heartbeat_revision_uuid")
        )
        if expected_revision != observed_revision:
            raise RuntimeError("lifecycle_guard_prior_authority_mismatch")
        _clear_lifecycle_guard(heartbeat_path)
        return previous, {
            "lifecycle_guard_reconciled": "pre_handoff_no_ctp_connection",
            "reconciled_lifecycle_guard_uuid": guard_uuid,
            "reconciled_lifecycle_guard_feed_session_id": guard_feed,
        }
    if previous_feed != guard_feed:
        raise RuntimeError("lifecycle_guard_feed_session_mismatch")
    previous_segment = _clean(
        previous.get("journal_segment_path")
        or previous.get("journal_path")
    )
    if previous_segment != guard_segment:
        raise RuntimeError("lifecycle_guard_journal_segment_mismatch")
    if previous.get("journal_authority_committed") is not True:
        raise RuntimeError("lifecycle_guard_authority_not_committed")
    owner_death_required = bool(
        (
            guard_phase == "terminal_commit"
            or (
                guard_phase == "startup_handoff"
                and previous_feed == guard_feed
            )
        )
        and (
            guard.get("capture_quiesced") is not True
            or guard.get("writer_quiesced") is not True
            or guard.get("pipeline_quiesced") is not True
        )
    )
    if owner_death_required:
        if guard_owner_pid == os.getpid():
            raise RuntimeError("lifecycle_guard_owner_still_alive")
        try:
            os.kill(guard_owner_pid, 0)
        except ProcessLookupError:
            pass
        except PermissionError as exc:
            raise RuntimeError("lifecycle_guard_owner_identity_uncertain") from exc
        else:
            raise RuntimeError("lifecycle_guard_owner_still_alive")

    state = _clean(previous.get("journal_session_state"))
    evidence = {
        "lifecycle_guard_reconciled": "unclean_authority",
        "reconciled_lifecycle_guard_uuid": guard_uuid,
        "reconciled_lifecycle_guard_feed_session_id": guard_feed,
    }
    allowed_states = {
        "starting",
        "running",
        "clean_stopped",
        "recovery_required_stopped",
        "fault_stopped",
    }
    if state not in allowed_states:
        raise RuntimeError("lifecycle_guard_authority_state_invalid")
    safely_fault_stopped = bool(
        state in {"recovery_required_stopped", "fault_stopped"}
        and _authority_is_strictly_stopped(previous)
    )
    if not safely_fault_stopped:
        previous = _fault_stopped_authority(
            previous,
            terminal_reason="unclean_lifecycle_guard",
        )
        _atomic_write_json(heartbeat_path, previous)
        evidence["lifecycle_guard_reconciled"] = (
            "stale_clean_authority_revoked"
            if state == "clean_stopped"
            else "unclean_authority_revoked"
        )
    _clear_lifecycle_guard(heartbeat_path)
    return previous, evidence


@contextmanager
def _exclusive_stream_owner_lock(heartbeat_path: Path):
    """Fence the single authoritative producer for one heartbeat path."""

    heartbeat_path = Path(heartbeat_path)
    heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = heartbeat_path.with_name(
        f".{heartbeat_path.name}.stage179.owner.lock"
    )
    descriptor = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("stream_owner_lock_contended") from exc
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _publish_blocked_stream_startup(
    heartbeat_path: Path,
    *,
    summary: dict[str, Any],
    previous_heartbeat: Mapping[str, Any],
) -> dict[str, Any]:
    """Fail closed without discarding the only prior recovery pointer."""

    attempt = {
        **summary,
        "stream_ready": False,
        "transport_ready": False,
        "stopped": True,
        "clean_shutdown": True,
        "journal_session_state": "clean_stopped",
        "journal_schema": JOURNAL_SCHEMA_FRAMED_V1,
        "journal_format": JOURNAL_FORMAT_FRAMED_V1,
        "journal_schema_version": JOURNAL_BATCH_COMMIT_SCHEMA_VERSION,
        "journal_authority_committed": False,
        "durable_ingress_sequence": 0,
        "last_ingress_sequence": 0,
    }
    payload = {
        **attempt,
        "recovery_blocked": True,
        "recovery_blocked_reason": _clean(summary.get("status")),
    }
    if previous_heartbeat:
        payload.update(
            {
                "authoritative_heartbeat_path": str(heartbeat_path.resolve()),
                "authoritative_feed_session_id": _clean(
                    previous_heartbeat.get("feed_session_id")
                ),
                "authoritative_journal_segment_path": _clean(
                    previous_heartbeat.get("journal_segment_path")
                ),
                "authoritative_heartbeat_revision_uuid": _clean(
                    previous_heartbeat.get("heartbeat_revision_uuid")
                ),
            }
        )
        prior_state = _clean(previous_heartbeat.get("journal_session_state"))
        if not prior_state:
            prior_state = (
                "clean_stopped"
                if previous_heartbeat.get("clean_shutdown") is True
                else "fault_stopped"
            )
        if prior_state in {"starting", "running"}:
            prior_state = "fault_stopped"
        if prior_state not in {
            "clean_stopped",
            "recovery_required_stopped",
            "fault_stopped",
        }:
            prior_state = "fault_stopped"
        clean_shutdown = prior_state == "clean_stopped"
        authoritative = {
            **dict(previous_heartbeat),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": _clean(summary.get("status")) or "stream_blocked_startup",
            "stream_ready": False,
            "transport_ready": False,
            "writer_alive": False,
            "stopped": True,
            "clean_shutdown": clean_shutdown,
            "journal_session_state": prior_state,
            "recovery_blocked": True,
            "recovery_blocked_reason": _clean(summary.get("status")),
            "startup_attempt_feed_session_id": _clean(
                summary.get("feed_session_id")
            ),
            "heartbeat_revision_uuid": uuid.uuid4().hex,
        }
        authoritative.pop("tick_snapshot_commit", None)
        authoritative.pop("tick_snapshot_generation_uuid", None)
        # Revoke the consumer-visible main heartbeat first.  The sidecar is
        # audit evidence only and must never be the sole fail-close signal.
        _atomic_write_json(heartbeat_path, authoritative)
        _publish_startup_attempt_unless_guarded(heartbeat_path, payload)
        return authoritative
    else:
        payload = {
            **payload,
            "stream_ready": False,
            "stopped": True,
        }
    _atomic_write_json(heartbeat_path, payload)
    return payload


def _publish_unreadable_heartbeat_attempt(
    heartbeat_path: Path,
    *,
    summary: Mapping[str, Any],
) -> None:
    """Preserve corrupt authority bytes while publishing separate evidence."""

    payload = {
        **dict(summary),
        "stream_ready": False,
        "transport_ready": False,
        "stopped": True,
        "clean_shutdown": False,
        "journal_session_state": "fault_stopped",
        "journal_schema": JOURNAL_SCHEMA_FRAMED_V1,
        "journal_format": JOURNAL_FORMAT_FRAMED_V1,
        "journal_schema_version": JOURNAL_BATCH_COMMIT_SCHEMA_VERSION,
        "journal_authority_committed": False,
        "recovery_blocked": True,
        "recovery_blocked_reason": _clean(summary.get("status")),
        "authoritative_heartbeat_path": str(heartbeat_path.resolve()),
    }
    _publish_startup_attempt_unless_guarded(heartbeat_path, payload)


def _effective_recovery_gaps(recovery: Any) -> tuple[Any, ...]:
    gaps = tuple(getattr(recovery, "disclosed_gaps", ()) or ())
    if gaps:
        return gaps
    scalar = getattr(recovery, "disclosed_gap", None)
    return (scalar,) if scalar is not None else ()


def _recover_previous_journal(
    *,
    previous_heartbeat: Mapping[str, Any],
    journal_path: Path,
) -> JournalRecoveryResult:
    """Never reinterpret a non-authoritative bootstrap pointer as a journal."""

    is_pre_stage179 = bool(
        previous_heartbeat
        and "journal_schema" not in previous_heartbeat
        and "journal_authority_committed" not in previous_heartbeat
    )
    if is_pre_stage179:
        feed_session_id = _clean(previous_heartbeat.get("feed_session_id"))
        stopped = previous_heartbeat.get("stopped")
        stream_ready = previous_heartbeat.get("stream_ready")
        sequence = previous_heartbeat.get("stream_sequence", 0)
        alias = previous_heartbeat.get("journal_tick_count", sequence)
        legacy_path = Path(
            _clean(previous_heartbeat.get("journal_path")) or journal_path
        )
        if (
            _clean(previous_heartbeat.get("model_tag")) != MODEL_TAG
            or _clean(previous_heartbeat.get("mode")) != "continuous_tick_stream"
            or _clean(previous_heartbeat.get("status")) != "tick_stream_stopped"
            or not feed_session_id
            or stopped is not True
            or stream_ready is not False
            or previous_heartbeat.get("transport_ready") is not False
            or previous_heartbeat.get("real_order_enabled") is not False
            or type(sequence) is not int
            or sequence < 0
            or type(alias) is not int
            or alias != sequence
            or any(
                type(previous_heartbeat.get(key, 0)) is not int
                or previous_heartbeat.get(key, 0) != 0
                for key in (
                    "send_order_api_called_count",
                    "cancel_order_api_called_count",
                    "order_api_called_count",
                )
            )
        ):
            raise ValueError("legacy_heartbeat_not_cleanly_stopped")
        if os.path.lexists(str(legacy_path)) and not legacy_path.is_file():
            raise ValueError("legacy_journal_not_regular_file")
        observed_sequence = sequence
        legacy_nonempty = False
        if legacy_path.is_file():
            legacy_nonempty = legacy_path.stat().st_size > 0
            with legacy_path.open("rb") as handle:
                while True:
                    raw_line = handle.readline(4 * 1024 * 1024 + 1)
                    if not raw_line:
                        break
                    if len(raw_line) > 4 * 1024 * 1024:
                        break
                    try:
                        row = json.loads(raw_line)
                    except (
                        json.JSONDecodeError,
                        UnicodeDecodeError,
                        ValueError,
                        RecursionError,
                    ):
                        break
                    if not isinstance(row, Mapping):
                        break
                    if _clean(row.get("feed_session_id")) != feed_session_id:
                        continue
                    row_sequence = row.get("stream_sequence")
                    if type(row_sequence) is int and row_sequence > 0:
                        observed_sequence = max(observed_sequence, row_sequence)
        if legacy_nonempty:
            # The old format has neither a durable byte cursor nor a commit
            # frame.  Any bytes that cannot be fully identified are still
            # evidence of at least one unproven suffix record; only a missing
            # or zero-byte file can migrate gap-free at sequence zero.
            observed_sequence = max(observed_sequence, 1)
        # The old writer flushed but did not fsync and exposed no byte cursor.
        # Keep its bytes intact and disclose every observed old-session tick as
        # unproven instead of silently fabricating Stage179 durability.
        disclosed_gap = (
            TickStreamGap(
                feed_session_id,
                1,
                observed_sequence,
                "legacy_pre_stage179_durability_unproven",
            )
            if observed_sequence > 0
            else None
        )
        return JournalRecoveryResult(
            previous_durable_cursor=None,
            isolated_tail_path=None,
            isolated_byte_count=0,
            disclosed_gap=disclosed_gap,
            disclosed_gaps=(disclosed_gap,) if disclosed_gap is not None else (),
            journal_schema="legacy_ndjson_v0",
        )

    if previous_heartbeat.get("journal_authority_committed") is False:
        if (
            not _clean(previous_heartbeat.get("feed_session_id"))
            or _clean(previous_heartbeat.get("journal_schema"))
            != JOURNAL_SCHEMA_FRAMED_V1
            or _clean(previous_heartbeat.get("journal_session_state"))
            != "clean_stopped"
            or previous_heartbeat.get("stopped") is not True
            or previous_heartbeat.get("clean_shutdown") is not True
            or (
                "journal_format" in previous_heartbeat
                and _clean(previous_heartbeat.get("journal_format"))
                != JOURNAL_FORMAT_FRAMED_V1
            )
            or (
                "journal_schema_version" in previous_heartbeat
                and (
                    type(previous_heartbeat.get("journal_schema_version"))
                    is not int
                    or previous_heartbeat.get("journal_schema_version")
                    != JOURNAL_BATCH_COMMIT_SCHEMA_VERSION
                )
            )
            or (
                "gap_latched" in previous_heartbeat
                and previous_heartbeat.get("gap_latched") is not False
            )
            or previous_heartbeat.get("writer_fault")
            or previous_heartbeat.get("stream_ready") is not False
            or previous_heartbeat.get("transport_ready") is not False
            or (
                "writer_alive" in previous_heartbeat
                and previous_heartbeat.get("writer_alive") is not False
            )
            or previous_heartbeat.get("real_order_enabled") is not False
            or any(
                type(previous_heartbeat.get(key, 0)) is not int
                or previous_heartbeat.get(key, 0) != 0
                for key in (
                    "send_order_api_called_count",
                    "cancel_order_api_called_count",
                    "send_order_api_attempted_count",
                    "cancel_order_api_attempted_count",
                    "order_api_called_count",
                )
            )
            or bool(previous_heartbeat.get("tick_snapshot_generation_uuid"))
            or previous_heartbeat.get("tick_snapshot_commit") is not None
        ):
            raise ValueError("non-authoritative heartbeat contract invalid")
        for key in (
            "durable_ingress_sequence",
            "last_ingress_sequence",
            "stream_sequence",
            "journal_tick_count",
        ):
            if key in previous_heartbeat and (
                type(previous_heartbeat[key]) is not int
                or previous_heartbeat[key] != 0
            ):
                raise ValueError("non-authoritative heartbeat carries sequence")
        return JournalRecoveryResult(
            previous_durable_cursor=None,
            isolated_tail_path=None,
            isolated_byte_count=0,
            disclosed_gap=None,
            disclosed_gaps=(),
            journal_schema=JOURNAL_SCHEMA_FRAMED_V1,
        )
    previous_journal_path = Path(
        _clean(previous_heartbeat.get("journal_segment_path"))
        or _clean(previous_heartbeat.get("journal_path"))
        or journal_path
    )
    return recover_or_isolate_dirty_tail(
        previous_journal_path,
        previous_heartbeat,
    )


def _install_readonly_order_guards(
    gateway: Any,
    summary: dict[str, Any],
) -> Any:
    """Make a real order API invocation impossible in this read-only runner."""

    original_send = gateway.send_order
    original_cancel = gateway.cancel_order
    summary.setdefault("send_order_api_attempted_count", 0)
    summary.setdefault("cancel_order_api_attempted_count", 0)

    def reject_send(*_args: Any, **_kwargs: Any) -> str:
        summary["send_order_api_attempted_count"] += 1
        raise RuntimeError("readonly_order_guard_blocked_send_order")

    def reject_cancel(*_args: Any, **_kwargs: Any) -> None:
        summary["cancel_order_api_attempted_count"] += 1
        raise RuntimeError("readonly_order_guard_blocked_cancel_order")

    gateway.send_order = reject_send
    gateway.cancel_order = reject_cancel
    restored = False

    def restore() -> None:
        nonlocal restored
        if restored:
            return
        gateway.send_order = original_send
        gateway.cancel_order = original_cancel
        restored = True

    return restore


_READONLY_API_COUNTER_FIELDS = (
    "send_order_api_called_count",
    "cancel_order_api_called_count",
    "send_order_api_attempted_count",
    "cancel_order_api_attempted_count",
    "order_api_called_count",
)


def _readonly_api_evidence_is_clean(result: Mapping[str, Any]) -> bool:
    if result.get("real_order_enabled") is not False:
        return False
    return all(
        type(result.get(field)) is int and result.get(field) == 0
        for field in _READONLY_API_COUNTER_FIELDS
    )


def _has_lifecycle_error_evidence(result: Mapping[str, Any]) -> bool:
    for key, value in result.items():
        if not (
            key.endswith("_error")
            or key.startswith("engine_close_error:")
        ):
            continue
        if isinstance(value, str):
            if value.strip():
                return True
        elif value:
            return True
    return False


def _durable_terminal_fault_reasons(
    durable: DurableTickSnapshot,
) -> tuple[str, ...]:
    """Explain why one stopped snapshot cannot prove a clean terminal state."""

    reasons: list[str] = []
    if durable.accepting:
        reasons.append("ingress_accepting")
    if durable.writer_alive:
        reasons.append("writer_alive")
    if durable.writer_fault is not None:
        reasons.append("writer_fault")
    if durable.gap is not None:
        reasons.append("gap_latched")
    if durable.queue_depth != 0:
        reasons.append("queue_not_empty")
    if durable.dropped_tick_count != 0:
        reasons.append("dropped_ticks")
    if durable.last_ingress_sequence != durable.durable_ingress_sequence:
        reasons.append("durable_sequence_mismatch")
    return tuple(reasons)


def _stream_terminal_evidence_is_clean(result: Mapping[str, Any]) -> bool:
    required_fields = {
        "journal_authority_committed",
        "stopped",
        "clean_shutdown",
        "stream_ready",
        "transport_ready",
        "gap_latched",
        "writer_fault",
        "writer_alive",
        "accepting",
        "queue_depth",
        "dropped_tick_count",
        "last_ingress_sequence",
        "durable_ingress_sequence",
        "durable_journal_byte_offset",
        "journal_schema",
    }
    if not required_fields.issubset(result):
        return False
    if (
        result.get("journal_authority_committed") is not True
        or result.get("stopped") is not True
        or result.get("clean_shutdown") is not True
        or result.get("stream_ready") is not False
        or result.get("transport_ready") is not False
        or result.get("gap_latched") is not False
        or result.get("writer_fault") is not None
        or result.get("writer_alive") is not False
        or result.get("accepting") is not False
    ):
        return False
    for field in ("queue_depth", "dropped_tick_count"):
        if type(result.get(field)) is not int or result.get(field) != 0:
            return False
    last_sequence = result.get("last_ingress_sequence")
    durable_sequence = result.get("durable_ingress_sequence")
    durable_offset = result.get("durable_journal_byte_offset")
    return bool(
        type(last_sequence) is int
        and type(durable_sequence) is int
        and type(durable_offset) is int
        and last_sequence >= 0
        and last_sequence == durable_sequence
        and durable_offset >= 0
        and ((durable_sequence == 0) == (durable_offset == 0))
        and _clean(result.get("journal_schema"))
        == JOURNAL_SCHEMA_FRAMED_V1
    )


def _stream_exit_code(*, connect: bool, result: Mapping[str, Any]) -> int:
    if not connect:
        return 0
    status = _clean(result.get("status"))
    state = _clean(result.get("journal_session_state"))
    if (
        status.startswith("stream_blocked_")
        or status == "stream_authority_unsafe"
        or result.get("journal_authority_unsafe") is True
        or state in {"fault_stopped", "recovery_required_stopped"}
    ):
        return 2
    if (
        state != "clean_stopped"
        or result.get("ever_stream_ready") is not True
        or not _stream_terminal_evidence_is_clean(result)
        or not _readonly_api_evidence_is_clean(result)
        or _has_lifecycle_error_evidence(result)
    ):
        return 2
    return 0


def _probe_exit_code(*, connect: bool, result: Mapping[str, Any]) -> int:
    if not connect:
        return 0
    log_analysis = result.get("log_analysis")
    log_analysis = log_analysis if isinstance(log_analysis, Mapping) else {}
    broker_snapshot = result.get("broker_snapshot")
    broker_snapshot = (
        broker_snapshot if isinstance(broker_snapshot, Mapping) else {}
    )
    position_state = _clean(broker_snapshot.get("position_snapshot_state"))
    status = _clean(result.get("status"))
    target_count = result.get("target_symbol_count", 0)
    row_counts = result.get("row_counts")
    row_counts = row_counts if isinstance(row_counts, Mapping) else {}
    tick_count = row_counts.get("ticks", 0)
    received_targets = result.get("received_target_symbols")
    missing_targets = result.get("missing_target_tick_symbols")
    if (
        type(target_count) is not int
        or target_count < 0
        or type(tick_count) is not int
        or tick_count < 0
        or not isinstance(received_targets, list)
        or not isinstance(missing_targets, list)
        or not _readonly_api_evidence_is_clean(result)
        or _has_lifecycle_error_evidence(result)
        or log_analysis.get("td_login_success") is not True
        or log_analysis.get("md_login_success") is not True
        or position_state not in {"confirmed_flat", "positions_received"}
        or broker_snapshot.get("position_query_last_seen") is not True
        or broker_snapshot.get("position_query_error_rows") != 0
        or status in {
            "connect_exception",
            "readonly_trading_login_failed",
            "readonly_connected_no_login_outcome",
            "readonly_logs_without_ctp_progress",
        }
        or status.startswith("blocked_")
        or result.get("exception")
        or result.get("aggregate_close_error")
        or (
            target_count > 0
            and (
                status != "readonly_tick_snapshots_received"
                or len(missing_targets) != 0
                or len(received_targets) < target_count
                or tick_count < target_count
            )
        )
    ):
        return 2
    return 0


def _load_heartbeat_mapping(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _heartbeat_owned_by_session(path: Path, feed_session_id: str) -> dict[str, Any]:
    payload = _load_heartbeat_mapping(path)
    if (
        _clean(payload.get("feed_session_id")) == feed_session_id
        and payload.get("journal_authority_committed") is True
    ):
        return payload
    return {}


def _publish_fail_closed_current_authority(
    heartbeat_path: Path,
    *,
    feed_session_id: str,
    summary: dict[str, Any],
    fallback_heartbeat: Mapping[str, Any],
    journal_session_state: str = "fault_stopped",
) -> dict[str, Any]:
    """Revoke a current feed without depending on tick-snapshot publication."""

    current = _heartbeat_owned_by_session(heartbeat_path, feed_session_id)
    base = current or dict(fallback_heartbeat)
    if _clean(base.get("feed_session_id")) != feed_session_id:
        summary["journal_authority_unsafe"] = True
        summary["status"] = "stream_authority_unsafe"
        return {}
    report = summary.get("shutdown_report")
    report = report if isinstance(report, Mapping) else {}
    gap = report.get("gap") if isinstance(report.get("gap"), Mapping) else None
    durable_through = (
        report.get("durable_through")
        if isinstance(report.get("durable_through"), Mapping)
        else {}
    )
    writer_fault = (
        report.get("writer_fault")
        if isinstance(report.get("writer_fault"), Mapping)
        else base.get("writer_fault")
    )
    revoked_reasons = {
        "shutdown_drain_timeout",
        "shutdown_durable_mismatch",
        "ingress_queue_full",
        "ingress_not_accepting",
        "ingress_thread_violation",
        "ingress_capture_exception",
        "ingress_fault_latch_exception",
    }
    gap_reason = _clean(gap.get("reason")) if gap else ""
    gap_start = int(gap.get("start_ingress_sequence", 0) or 0) if gap else 0
    gap_end = int(gap.get("end_ingress_sequence", 0) or 0) if gap else 0
    durable_sequence = int(
        durable_through.get(
            "ingress_sequence",
            base.get("durable_ingress_sequence", 0),
        )
        or 0
    )
    durable_offset = int(
        durable_through.get(
            "journal_byte_offset",
            base.get("durable_journal_byte_offset", 0),
        )
        or 0
    )
    last_ingress_sequence = max(
        int(base.get("last_ingress_sequence", 0) or 0),
        durable_sequence,
        gap_end,
    )
    payload = {
        **base,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": f"tick_stream_{journal_session_state}",
        "terminal_reason": _clean(summary.get("status")),
        "stream_ready": False,
        "transport_ready": False,
        "stopped": True,
        "clean_shutdown": False,
        "journal_session_state": journal_session_state,
        "journal_authority_committed": True,
        "writer_alive": False,
        "writer_fault": writer_fault,
        "stream_sequence": durable_sequence,
        "journal_tick_count": durable_sequence,
        "durable_ingress_sequence": durable_sequence,
        "durable_journal_byte_offset": durable_offset,
        "last_ingress_sequence": last_ingress_sequence,
        "gap_latched": bool(gap),
        "gap_start_ingress_sequence": gap_start,
        "gap_end_ingress_sequence": gap_end,
        "gap_reason": gap_reason,
        "journal_commit_revoked_from_ingress_sequence": (
            gap_start if gap_reason in revoked_reasons else 0
        ),
        "journal_commit_revoked_through_ingress_sequence": (
            gap_end if gap_reason in revoked_reasons else 0
        ),
        "journal_commit_revocation_reason": (
            gap_reason if gap_reason in revoked_reasons else ""
        ),
        "final_heartbeat_error": _clean(summary.get("final_heartbeat_error")),
        "heartbeat_revision_uuid": uuid.uuid4().hex,
    }
    payload.pop("tick_snapshot_commit", None)
    payload.pop("tick_snapshot_generation_uuid", None)
    try:
        _atomic_write_json(heartbeat_path, payload)
    except Exception as exc:
        summary["journal_authority_unsafe"] = True
        summary["authority_revocation_error"] = repr(exc)
        summary["status"] = "stream_authority_unsafe"
        try:
            _publish_startup_attempt_unless_guarded(
                heartbeat_path,
                {
                    **summary,
                    "feed_session_id": feed_session_id,
                    "lifecycle_guard_active": True,
                    "stream_ready": False,
                    "transport_ready": False,
                    "stopped": True,
                    "journal_authority_unsafe": True,
                },
            )
        except Exception:
            pass
        return {}
    summary["journal_authority_unsafe"] = False
    return payload


def _dataframe_csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    """Serialize once so the commit hash covers the exact bytes readers parse."""

    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")


def _publish_tick_snapshot_commit(
    *,
    tick_path: Path,
    heartbeat_path: Path,
    tick_rows: list[dict[str, Any]],
    heartbeat: dict[str, Any],
) -> dict[str, Any]:
    """Publish tick bytes first and the matching heartbeat commit last.

    Atomic rename protects each individual file.  The generation and exact
    byte hash let Stage904 distinguish a normal two-file publication window
    from a real ring-buffer gap, without trusting write order alone.
    """

    tick_bytes = _dataframe_csv_bytes(tick_rows)
    generation_uuid = str(uuid.uuid4())
    commit = {
        "schema_version": TICK_SNAPSHOT_COMMIT_SCHEMA_VERSION,
        "generation_uuid": generation_uuid,
        "sha256": hashlib.sha256(tick_bytes).hexdigest(),
        "row_count": len(tick_rows),
        "feed_session_id": _clean(heartbeat.get("feed_session_id")),
        "stream_sequence": int(heartbeat.get("stream_sequence", 0) or 0),
    }
    committed_heartbeat = {
        **heartbeat,
        "tick_snapshot_commit": commit,
        "tick_snapshot_generation_uuid": generation_uuid,
        # Every authoritative heartbeat mutation is one snapshot revision.
        # Alternate writers must either publish a new committed generation or
        # remove the commit entirely; reusing this revision is never valid.
        "heartbeat_revision_uuid": generation_uuid,
    }
    _atomic_write_bytes(tick_path, tick_bytes)
    # This is the commit point.  Never move it before the tick artifact.
    _atomic_write_json(heartbeat_path, committed_heartbeat)
    return committed_heartbeat


def _append_ndjson(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n")
        handle.flush()
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _stream_tick_row(
    tick: Any,
    *,
    feed_session_id: str,
    stream_sequence: int,
    symbol_stream_sequence: int | None = None,
    received_at: datetime | None = None,
) -> dict[str, Any]:
    now = received_at or datetime.now()
    exchange_dt = getattr(tick, "datetime", None)
    return {
        "feed_session_id": feed_session_id,
        "stream_sequence": int(stream_sequence),
        # Global sequence remains an audit identity.  Reducers consume this
        # per-symbol sequence so normal JM/RB/JM interleaving is not mistaken
        # for a lost JM event.
        "symbol_stream_sequence": int(
            stream_sequence
            if symbol_stream_sequence is None
            else symbol_stream_sequence
        ),
        "received_at": now.isoformat(timespec="microseconds"),
        "exchange_datetime": exchange_dt.isoformat() if isinstance(exchange_dt, datetime) else _clean(exchange_dt),
        "vt_symbol": _clean(getattr(tick, "vt_symbol", "")),
        "symbol": _clean(getattr(tick, "symbol", "")),
        "exchange": _clean(getattr(getattr(tick, "exchange", ""), "value", getattr(tick, "exchange", ""))),
        "last_price": getattr(tick, "last_price", 0.0),
        "bid_price_1": getattr(tick, "bid_price_1", 0.0),
        "ask_price_1": getattr(tick, "ask_price_1", 0.0),
        "bid_volume_1": getattr(tick, "bid_volume_1", 0.0),
        "ask_volume_1": getattr(tick, "ask_volume_1", 0.0),
        "limit_up": getattr(tick, "limit_up", 0.0),
        "limit_down": getattr(tick, "limit_down", 0.0),
    }


def _manifest_symbols(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []
    try:
        if path.suffix.lower() == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            values = payload.get("symbols", payload.get("vt_symbols", [])) if isinstance(payload, dict) else payload
            return [_clean(item) for item in values if _clean(item)] if isinstance(values, list) else []
        if path.suffix.lower() == ".csv":
            frame = pd.read_csv(path, encoding="utf-8-sig")
            column = "vt_symbol" if "vt_symbol" in frame.columns else "symbol" if "symbol" in frame.columns else ""
            return [_clean(item) for item in frame[column].tolist() if _clean(item)] if column else []
        return [_clean(line) for line in path.read_text(encoding="utf-8").splitlines() if _clean(line)]
    except Exception:
        return []


def _append_unique(rows: list[dict[str, Any]], new_rows: list[dict[str, Any]], key_fields: list[str]) -> None:
    seen = {tuple(str(row.get(field, "")) for field in key_fields) for row in rows}
    for row in new_rows:
        key = tuple(str(row.get(field, "")) for field in key_fields)
        if key in seen:
            continue
        rows.append(row)
        seen.add(key)


def _analyze_logs(log_rows: list[dict[str, Any]]) -> dict[str, Any]:
    messages = [str(row.get("msg", "")).strip() for row in log_rows]
    analysis: dict[str, Any] = {
        "td_connected": False,
        "md_connected": False,
        "td_auth_success": False,
        "md_login_success": False,
        "td_login_success": False,
        "td_login_failed": False,
        "td_login_failed_message": "",
        "td_disconnected_after_connect": False,
        "md_disconnected_after_connect": False,
        "status_hint": "no_logs",
    }
    for message in messages:
        if "交易服务器连接成功" in message:
            analysis["td_connected"] = True
            analysis["td_disconnected_after_connect"] = False
        if "行情服务器连接成功" in message:
            analysis["md_connected"] = True
            analysis["md_disconnected_after_connect"] = False
        if "交易服务器授权验证成功" in message:
            analysis["td_auth_success"] = True
        if "行情服务器登录成功" in message:
            analysis["md_login_success"] = True
        if "交易服务器登录成功" in message:
            analysis["td_login_success"] = True
        if "交易服务器登录失败" in message:
            analysis["td_login_failed"] = True
            analysis["td_login_failed_message"] = message
        if "交易服务器连接断开" in message:
            analysis["td_connected"] = False
            analysis["td_login_success"] = False
            analysis["td_disconnected_after_connect"] = True
        if "行情服务器连接断开" in message:
            analysis["md_connected"] = False
            analysis["md_login_success"] = False
            analysis["md_disconnected_after_connect"] = True
    if analysis["td_login_success"]:
        analysis["status_hint"] = "trading_login_success"
    elif analysis["td_login_failed"]:
        analysis["status_hint"] = "trading_login_failed"
    elif analysis["td_connected"] or analysis["md_connected"]:
        analysis["status_hint"] = "connected_but_no_trading_login_outcome"
    elif messages:
        analysis["status_hint"] = "logs_present_without_ctp_progress"
    return analysis


def _analyze_position_snapshot(rows: dict[str, list[dict[str, Any]]], log_analysis: dict[str, Any]) -> dict[str, Any]:
    callbacks = rows.get("position_query_callbacks", [])
    position_rows = rows.get("positions", [])
    data_callbacks = [row for row in callbacks if row.get("has_data")]
    error_callbacks = [row for row in callbacks if int(row.get("error_id") or 0) != 0]
    last_seen = any(bool(row.get("last")) for row in callbacks)
    nonzero_position_rows = []
    for row in position_rows:
        volume = pd.to_numeric(row.get("volume", row.get("position", 0)), errors="coerce")
        frozen = pd.to_numeric(row.get("frozen", 0), errors="coerce")
        if pd.notna(volume) and abs(float(volume)) > 1e-12:
            nonzero_position_rows.append(row)
        elif pd.notna(frozen) and abs(float(frozen)) > 1e-12:
            nonzero_position_rows.append(row)
    state = "position_query_not_available"
    if nonzero_position_rows:
        state = "positions_received"
    elif error_callbacks:
        state = "position_query_error"
    elif last_seen and log_analysis.get("td_login_success"):
        state = "confirmed_flat"
    elif last_seen and data_callbacks and not position_rows:
        state = "position_payload_without_position_rows"
    elif log_analysis.get("td_login_success"):
        state = "position_query_not_completed"
    return {
        "position_snapshot_state": state,
        "position_rows": len(position_rows),
        "nonzero_position_rows": len(nonzero_position_rows),
        "position_query_callback_rows": len(callbacks),
        "position_query_data_callback_rows": len(data_callbacks),
        "position_query_last_seen": bool(last_seen),
        "position_query_error_rows": len(error_callbacks),
    }


def _quiesce_market_data_ingress(
    gateway: Any,
    pipeline: TickStreamPipeline,
    restore_gateway: Any,
) -> dict[str, str]:
    """Linearize stream cutover before draining the durable writer.

    The wrapper stays installed while acceptance is revoked and the market
    data API closes.  Any callback racing that boundary therefore receives an
    ingress identity and extends the explicit suffix gap instead of bypassing
    Stage179 capture.  TD teardown remains with ``MainEngine.close``.
    """

    errors: dict[str, str] = {}
    pipeline.stop_accepting()
    try:
        md_api = getattr(gateway, "md_api", None)
        md_close = getattr(md_api, "close", None)
        if callable(md_close):
            md_close()
            guard_fenced = False
            if hasattr(md_api, "connect_status"):
                try:
                    setattr(md_api, "connect_status", False)
                    if hasattr(md_api, "login_status"):
                        setattr(md_api, "login_status", False)
                    guard_fenced = True
                except Exception:
                    guard_fenced = False
            method_fenced = False
            try:
                setattr(md_api, "close", lambda: None)
                method_fenced = True
            except Exception:
                method_fenced = False
            if not guard_fenced and not method_fenced:
                raise RuntimeError("market_data_close_could_not_be_fenced")
        else:
            gateway.close()
            try:
                setattr(gateway, "close", lambda: None)
            except Exception as exc:
                raise RuntimeError(
                    "gateway_close_could_not_be_fenced"
                ) from exc
    except Exception as exc:
        errors["market_data_close_error"] = repr(exc)
    return errors


def _stop_event_engine_after_close_failure(
    event_engine: EventEngine,
) -> str:
    """Prevent a failed aggregate close from leaking non-daemon threads."""

    def thread_is_alive(name: str) -> bool:
        thread = getattr(event_engine, name, None)
        is_alive = getattr(thread, "is_alive", None)
        if not callable(is_alive):
            return False
        try:
            return bool(is_alive())
        except Exception:
            return True

    if not getattr(event_engine, "_active", False) and not any(
        thread_is_alive(name) for name in ("_timer", "_thread")
    ):
        return ""
    try:
        event_engine.stop()
    except Exception as exc:
        return repr(exc)
    if any(thread_is_alive(name) for name in ("_timer", "_thread")):
        return repr(RuntimeError("event_engine_threads_still_alive"))
    return ""


def _install_native_api_close_fence(
    api: Any,
) -> tuple[Any, dict[str, Any], bool]:
    """Make one native API teardown observable and at-most-once."""

    state: dict[str, Any] = {
        "available": False,
        "entered": False,
        "completed": False,
        "attempt_count": 0,
        "error": "",
    }
    original_close = getattr(api, "close", None)
    if not callable(original_close):
        return None, state, True
    state["available"] = True

    def close_once() -> None:
        if state["entered"]:
            return
        state["entered"] = True
        state["attempt_count"] = 1
        try:
            original_close()
        except Exception as exc:
            state["error"] = repr(exc)
            raise
        else:
            state["completed"] = True

    try:
        setattr(api, "close", close_once)
    except Exception as exc:
        state["fence_error"] = repr(exc)
        return close_once, state, False
    return close_once, state, True


def _install_trading_api_close_fence(
    gateway: Any,
) -> tuple[Any, dict[str, Any], bool]:
    """Fence native TD teardown across aggregate and fallback paths."""

    return _install_native_api_close_fence(getattr(gateway, "td_api", None))


def _install_market_data_api_close_fence(
    gateway: Any,
) -> tuple[Any, dict[str, Any], bool]:
    """Fence native MD teardown across aggregate and fallback paths."""

    return _install_native_api_close_fence(getattr(gateway, "md_api", None))


def _record_native_api_close_state(
    summary: dict[str, Any],
    state: Mapping[str, Any],
    *,
    prefix: str,
) -> None:
    summary[f"{prefix}_close_available"] = bool(state.get("available"))
    summary[f"{prefix}_close_entered"] = bool(state.get("entered"))
    summary[f"{prefix}_close_completed"] = bool(state.get("completed"))
    summary[f"{prefix}_close_attempt_count"] = int(
        state.get("attempt_count", 0) or 0
    )
    if _clean(state.get("error")):
        summary[f"{prefix}_close_error"] = _clean(state.get("error"))
    if _clean(state.get("fence_error")):
        summary[f"{prefix}_close_fence_error"] = _clean(
            state.get("fence_error")
        )


def _record_trading_api_close_state(
    summary: dict[str, Any],
    state: Mapping[str, Any],
) -> None:
    _record_native_api_close_state(summary, state, prefix="trading_api")


def _record_market_data_api_close_state(
    summary: dict[str, Any],
    state: Mapping[str, Any],
) -> None:
    _record_native_api_close_state(summary, state, prefix="market_data_api")


def _close_without_market_data_retry(
    main_engine: MainEngine,
    gateway: Any,
    event_engine: EventEngine,
    *,
    trading_close: Any = None,
) -> dict[str, str]:
    """Close Python/TD resources without invoking an uncertain MD exit twice."""

    errors: dict[str, str] = {}
    event_error = _stop_event_engine_after_close_failure(event_engine)
    if event_error:
        errors["event_engine_stop_error"] = event_error
    for name, engine in tuple(main_engine.engines.items()):
        try:
            engine.close()
        except Exception as exc:
            errors[f"engine_close_error:{name}"] = repr(exc)
    td_api = getattr(gateway, "td_api", None)
    td_close = (
        trading_close
        if callable(trading_close)
        else getattr(td_api, "close", None)
    )
    if callable(td_close):
        try:
            td_close()
        except Exception as exc:
            errors["trading_api_close_error"] = repr(exc)
    return errors


def _close_readonly_main_engine(
    main_engine: Any,
    gateway: Any,
    event_engine: Any,
) -> tuple[dict[str, str], dict[str, Any], dict[str, Any], bool]:
    """Close probe/startup resources without aggregate short-circuit leaks."""

    (
        trading_close_once,
        trading_close_state,
        trading_close_fenced,
    ) = _install_trading_api_close_fence(gateway)
    (
        market_data_close_once,
        market_data_close_state,
        market_data_close_fenced,
    ) = _install_market_data_api_close_fence(gateway)
    errors: dict[str, str] = {}
    aggregate_closed = False
    if main_engine is None:
        if event_engine is not None:
            event_error = _stop_event_engine_after_close_failure(event_engine)
            if event_error:
                errors["event_engine_stop_error"] = event_error
    else:
        if gateway is None or (
            trading_close_fenced and market_data_close_fenced
        ):
            try:
                main_engine.close()
                aggregate_closed = True
            except Exception as exc:
                errors["aggregate_close_error"] = repr(exc)
        else:
            errors["aggregate_close_error"] = repr(
                RuntimeError("native_api_close_fence_unavailable")
            )
        if not aggregate_closed:
            errors.update(
                _close_without_market_data_retry(
                    main_engine,
                    gateway,
                    event_engine,
                    trading_close=trading_close_once,
                )
            )
            if callable(market_data_close_once):
                try:
                    market_data_close_once()
                except Exception as exc:
                    errors["market_data_close_error"] = repr(exc)

    for label, state in (
        ("trading_api", trading_close_state),
        ("market_data_api", market_data_close_state),
    ):
        if state.get("available") and not state.get("completed"):
            errors.setdefault(
                f"{label}_close_error",
                _clean(state.get("error")) or f"{label}_close_not_completed",
            )
    return (
        errors,
        trading_close_state,
        market_data_close_state,
        aggregate_closed,
    )


def _tick_stream_ready(
    *,
    transport_ready: bool,
    expected_symbol_count: int,
    missing_tick_symbol_count: int,
    durable_stream_ready: bool,
    prior_gap: Any | None,
    stopped: bool,
    starting: bool,
) -> bool:
    """Apply the permanent fail-close readiness predicate for one session."""

    return bool(
        transport_ready
        and int(expected_symbol_count) > 0
        and int(missing_tick_symbol_count) == 0
        and durable_stream_ready
        and prior_gap is None
        and not stopped
        and not starting
    )


def _run_probe(connect: bool, wait_seconds: int, pre_subscribe_wait_seconds: int, target_symbols: list[str]) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    gateway_import = _gateway_import_status()
    import_available = bool(gateway_import["ctp_gateway_import_available"])
    rows: dict[str, list[dict[str, Any]]] = {
        "accounts": [],
        "positions": [],
        "orders": [],
        "trades": [],
        "contracts": [],
        "ticks": [],
        "logs": [],
        "position_query_callbacks": [],
    }
    summary: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "connect_requested": connect,
        "wait_seconds": wait_seconds,
        "pre_subscribe_wait_seconds": pre_subscribe_wait_seconds,
        "target_symbols": target_symbols,
        "target_symbol_count": len(target_symbols),
        "vnpy_ctp_import_available": import_available,
        "gateway_import": gateway_import,
        "env_status": _env_status(),
        "missing_required_env": _required_env_missing(),
        "real_order_enabled": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "send_order_api_attempted_count": 0,
        "cancel_order_api_attempted_count": 0,
        "order_api_called_count": 0,
        "subscribe_api_called_count": 0,
        "status": "dry_run_not_connected",
        "connection_target": {
            "td_address": os.getenv("CTP_TD_ADDRESS", ""),
            "md_address": os.getenv("CTP_MD_ADDRESS", ""),
        },
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "accounts": str(ACCOUNT_PATH),
            "positions": str(POSITION_PATH),
            "orders": str(ORDER_PATH),
            "trades": str(TRADE_PATH),
            "contracts": str(CONTRACT_PATH),
            "ticks": str(TICK_PATH),
            "logs": str(LOG_PATH),
            "target_symbols": str(TARGET_SYMBOL_PATH),
            "position_query_callbacks": str(POSITION_QUERY_CALLBACK_PATH),
        },
    }
    if not connect:
        return summary | {"rows": rows}
    if not import_available:
        summary["status"] = "blocked_missing_vnpy_ctp"
        return summary | {"rows": rows}
    missing = _required_env_missing()
    if missing:
        summary["status"] = "blocked_missing_env"
        return summary | {"rows": rows}

    ctp_gateway_module: Any = None
    original_position_rsp: Any = None
    event_engine: Any = None
    main_engine: Any = None
    ctp_gateway: Any = None
    restore_order_guards: Any = None
    try:
        from vnpy_ctp import CtpGateway
        from vnpy_ctp.gateway import ctp_gateway as ctp_gateway_module

        original_position_rsp = (
            ctp_gateway_module.CtpTdApi.onRspQryInvestorPosition
        )

        def instrumented_position_rsp(
            self: Any,
            data: dict,
            error: dict,
            reqid: int,
            last: bool,
        ) -> None:
            rows["position_query_callbacks"].append(
                {
                    "reqid": reqid,
                    "last": bool(last),
                    "has_data": bool(data),
                    "instrument": (
                        str(data.get("InstrumentID", ""))
                        if isinstance(data, dict)
                        else ""
                    ),
                    "position": (
                        data.get("Position", "")
                        if isinstance(data, dict)
                        else ""
                    ),
                    "error_id": (
                        error.get("ErrorID", 0)
                        if isinstance(error, dict)
                        else 0
                    ),
                    "error_msg": (
                        error.get("ErrorMsg", "")
                        if isinstance(error, dict)
                        else ""
                    ),
                    "received_at": datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                }
            )
            return original_position_rsp(self, data, error, reqid, last)

        ctp_gateway_module.CtpTdApi.onRspQryInvestorPosition = (
            instrumented_position_rsp
        )
        event_engine = EventEngine()
        main_engine = MainEngine(event_engine)
        ctp_gateway = main_engine.add_gateway(CtpGateway)
        restore_order_guards = _install_readonly_order_guards(
            ctp_gateway,
            summary,
        )
    except Exception as exc:
        summary["status"] = "probe_initialization_exception"
        summary["exception"] = repr(exc)
        (
            close_errors,
            trading_close_state,
            market_data_close_state,
            _aggregate_closed,
        ) = _close_readonly_main_engine(
            main_engine,
            ctp_gateway,
            event_engine,
        )
        summary.update(
            {
                f"initialization_{key}": value
                for key, value in close_errors.items()
            }
        )
        _record_trading_api_close_state(summary, trading_close_state)
        _record_market_data_api_close_state(summary, market_data_close_state)
        if restore_order_guards is not None:
            try:
                restore_order_guards()
            except Exception as restore_exc:
                summary["order_guard_restore_error"] = repr(restore_exc)
        if ctp_gateway_module is not None and original_position_rsp is not None:
            try:
                ctp_gateway_module.CtpTdApi.onRspQryInvestorPosition = (
                    original_position_rsp
                )
            except Exception as restore_exc:
                summary["position_callback_restore_error"] = repr(
                    restore_exc
                )
        summary["log_analysis"] = _analyze_logs(rows["logs"])
        summary["broker_snapshot"] = _analyze_position_snapshot(
            rows,
            summary["log_analysis"],
        )
        summary["row_counts"] = {key: len(value) for key, value in rows.items()}
        return summary | {"rows": rows}

    def on_account(event: Any) -> None:
        rows["accounts"].append(_object_to_row(event.data))

    def on_position(event: Any) -> None:
        rows["positions"].append(_object_to_row(event.data))

    def on_order(event: Any) -> None:
        rows["orders"].append(_object_to_row(event.data))

    def on_trade(event: Any) -> None:
        rows["trades"].append(_object_to_row(event.data))

    def on_contract(event: Any) -> None:
        rows["contracts"].append(_object_to_row(event.data))

    def on_tick(event: Any) -> None:
        rows["ticks"].append(_object_to_row(event.data))

    def on_log(event: Any) -> None:
        rows["logs"].append(_object_to_row(event.data))

    try:
        event_engine.register(EVENT_ACCOUNT, on_account)
        event_engine.register(EVENT_POSITION, on_position)
        event_engine.register(EVENT_ORDER, on_order)
        event_engine.register(EVENT_TRADE, on_trade)
        event_engine.register(EVENT_CONTRACT, on_contract)
        event_engine.register(EVENT_TICK, on_tick)
        event_engine.register(EVENT_LOG, on_log)
        main_engine.connect(_ctp_setting_from_env(), "CTP")
        time.sleep(max(pre_subscribe_wait_seconds, 0))
        subscribed: list[str] = []
        invalid: list[str] = []
        for vt_symbol in target_symbols:
            parsed = _split_vt_symbol(vt_symbol)
            if parsed is None:
                invalid.append(vt_symbol)
                continue
            symbol, exchange = parsed
            main_engine.subscribe(SubscribeRequest(symbol=symbol, exchange=exchange), "CTP")
            summary["subscribe_api_called_count"] += 1
            subscribed.append(vt_symbol)
        summary["subscribed_symbols"] = subscribed
        summary["invalid_symbols"] = invalid
        time.sleep(max(wait_seconds, 1))
        cache_snapshot = collect_snapshot_from_main_engine(main_engine, target_symbols)
        _append_unique(rows["contracts"], cache_snapshot.get("contracts", []), ["vt_symbol"])
        _append_unique(rows["ticks"], cache_snapshot.get("ticks", []), ["vt_symbol"])
        _append_unique(rows["accounts"], cache_snapshot.get("accounts", []), ["vt_accountid"])
        _append_unique(rows["positions"], cache_snapshot.get("positions", []), ["vt_positionid"])
        target_set = {_clean(item) for item in target_symbols if _clean(item)}
        received_target_symbols = sorted(
            {
                _clean(row.get("vt_symbol"))
                for row in rows["ticks"]
                if _clean(row.get("vt_symbol")) in target_set
            }
        )
        summary["received_target_symbols"] = received_target_symbols
        summary["missing_target_tick_symbols"] = sorted(
            target_set - set(received_target_symbols)
        )
        log_analysis = _analyze_logs(rows["logs"])
        summary["log_analysis"] = log_analysis
        summary["status"] = "connected_or_attempted_readonly_tick_snapshot"
        if rows["ticks"]:
            summary["status"] = "readonly_tick_snapshots_received"
        elif log_analysis["status_hint"] == "trading_login_failed":
            summary["status"] = "readonly_trading_login_failed"
            summary["failure_reason"] = log_analysis["td_login_failed_message"]
        elif log_analysis["status_hint"] == "connected_but_no_trading_login_outcome":
            summary["status"] = "readonly_connected_no_login_outcome"
        elif log_analysis["status_hint"] == "logs_present_without_ctp_progress":
            summary["status"] = "readonly_logs_without_ctp_progress"
    except Exception as exc:
        summary["status"] = "connect_exception"
        summary["exception"] = repr(exc)
    finally:
        if "log_analysis" not in summary:
            summary["log_analysis"] = _analyze_logs(rows["logs"])
        summary["broker_snapshot"] = _analyze_position_snapshot(rows, summary["log_analysis"])
        summary["row_counts"] = {key: len(value) for key, value in rows.items()}
        (
            close_errors,
            trading_close_state,
            market_data_close_state,
            _aggregate_closed,
        ) = _close_readonly_main_engine(
            main_engine,
            ctp_gateway,
            event_engine,
        )
        summary.update(close_errors)
        _record_trading_api_close_state(summary, trading_close_state)
        _record_market_data_api_close_state(summary, market_data_close_state)
        try:
            restore_order_guards()
        except Exception as restore_exc:
            summary["order_guard_restore_error"] = repr(restore_exc)
        try:
            ctp_gateway_module.CtpTdApi.onRspQryInvestorPosition = (
                original_position_rsp
            )
        except Exception as restore_exc:
            summary["position_callback_restore_error"] = repr(restore_exc)
    return summary | {"rows": rows}


def _run_stream_owned(
    *,
    connect: bool,
    pre_subscribe_wait_seconds: int,
    target_symbols: list[str],
    watch_manifest: Path | None,
    journal_path: Path,
    heartbeat_path: Path,
    duration_seconds: int,
    heartbeat_seconds: float,
    max_buffer_ticks: int,
    parent_pid: int = 0,
) -> dict[str, Any]:
    """Keep one read-only market-data connection alive and journal ticks in arrival order."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    feed_session_id = f"{datetime.now():%Y%m%dT%H%M%S}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    gateway_import = _gateway_import_status()
    summary: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "mode": "continuous_tick_stream",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "feed_session_id": feed_session_id,
        "feed_started_at": datetime.now().isoformat(timespec="microseconds"),
        "connect_requested": bool(connect),
        "target_symbols": list(target_symbols),
        "watch_manifest": str(watch_manifest.resolve()) if watch_manifest else "",
        "journal_path": str(journal_path.resolve()),
        "heartbeat_path": str(heartbeat_path.resolve()),
        "tick_snapshot_path": str(TICK_PATH.resolve()),
        "duration_seconds": int(duration_seconds),
        "parent_pid": int(parent_pid),
        "real_order_enabled": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "subscribe_api_called_count": 0,
        "ever_stream_ready": False,
        "status": "stream_dry_run_not_connected",
        "gateway_import": gateway_import,
        "env_status": _env_status(),
        "missing_required_env": _required_env_missing(),
    }
    previous_heartbeat: dict[str, Any] = {}
    if heartbeat_path.exists():
        try:
            payload = json.loads(heartbeat_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("heartbeat root must be a JSON object")
            previous_heartbeat = payload
        except Exception as exc:
            # The corrupt file itself is the only recovery evidence.  Do not
            # overwrite it with a startup-attempt heartbeat.
            summary["status"] = "stream_blocked_heartbeat_read_error"
            summary["heartbeat_read_error"] = repr(exc)
            _publish_unreadable_heartbeat_attempt(
                heartbeat_path,
                summary=summary,
            )
            return summary
    if (
        _clean(previous_heartbeat.get("prior_recovery_transaction_id"))
        or _clean(previous_heartbeat.get("prior_recovery_manifest_path"))
    ):
        try:
            summary["recovery_manifest_restart_acknowledged"] = bool(
                acknowledge_committed_recovery_manifest(heartbeat_path)
            )
        except Exception as exc:
            summary["status"] = "stream_blocked_recovery_manifest_ack_error"
            summary["recovery_manifest_restart_ack_error"] = repr(exc)
            return summary
    try:
        previous_heartbeat, guard_evidence = _reconcile_lifecycle_guard(
            heartbeat_path,
            previous_heartbeat=previous_heartbeat,
        )
        summary.update(guard_evidence)
    except Exception as exc:
        summary["status"] = "stream_blocked_unclean_lifecycle_guard"
        summary["journal_authority_unsafe"] = True
        summary["lifecycle_guard_error"] = repr(exc)
        lifecycle_guard, _ = _load_active_lifecycle_guard(heartbeat_path)
        summary["prior_lifecycle_guard"] = lifecycle_guard
        return summary
    if connect:
        try:
            previous_heartbeat, revoke_evidence = (
                _revoke_unclean_previous_authority_before_recovery(
                    heartbeat_path,
                    previous_heartbeat=previous_heartbeat,
                )
            )
            summary.update(revoke_evidence)
        except Exception as exc:
            summary["status"] = "stream_blocked_prior_authority_revoke_error"
            summary["journal_authority_unsafe"] = True
            summary["prior_authority_revoke_error"] = repr(exc)
            lifecycle_guard, guard_error = _load_active_lifecycle_guard(
                heartbeat_path
            )
            summary["prior_lifecycle_guard"] = lifecycle_guard
            summary["prior_lifecycle_guard_error"] = guard_error
            return summary
    if not connect:
        _publish_blocked_stream_startup(
            heartbeat_path,
            summary=summary,
            previous_heartbeat=previous_heartbeat,
        )
        return summary
    if not gateway_import.get("ctp_gateway_import_available"):
        summary["status"] = "stream_blocked_missing_vnpy_ctp"
        _publish_blocked_stream_startup(
            heartbeat_path,
            summary=summary,
            previous_heartbeat=previous_heartbeat,
        )
        return summary
    if summary["missing_required_env"]:
        summary["status"] = "stream_blocked_missing_env"
        _publish_blocked_stream_startup(
            heartbeat_path,
            summary=summary,
            previous_heartbeat=previous_heartbeat,
        )
        return summary

    journal_segment_path = journal_path.with_name(
        f"{journal_path.stem}.{feed_session_id}{journal_path.suffix or '.ndjson'}"
    )
    try:
        recovery = _recover_previous_journal(
            previous_heartbeat=previous_heartbeat,
            journal_path=journal_path,
        )
    except Exception as exc:
        summary["status"] = "stream_blocked_journal_recovery_error"
        summary["journal_recovery_error"] = repr(exc)
        _publish_blocked_stream_startup(
            heartbeat_path,
            summary=summary,
            previous_heartbeat=previous_heartbeat,
        )
        return summary

    summary["journal_segment_path"] = str(journal_segment_path.resolve())
    effective_recovery_gaps = _effective_recovery_gaps(recovery)
    summary["prior_uncommitted_gap"] = (
        asdict(effective_recovery_gaps[-1]) if effective_recovery_gaps else None
    )
    summary["prior_uncommitted_gaps"] = [
        asdict(gap) for gap in effective_recovery_gaps
    ]
    recovery_previous_durable_cursor = (
        asdict(recovery.previous_durable_cursor)
        if recovery.previous_durable_cursor is not None
        else None
    )
    empty_feed_bridge = _clean_empty_feed_bridge(previous_heartbeat)
    if empty_feed_bridge is None:
        summary.update(_prior_authority_lineage(previous_heartbeat))
        summary["recovery_previous_durable_cursor"] = (
            recovery_previous_durable_cursor
        )
        summary["prior_authoritative_empty_feed_sessions"] = []
    else:
        summary.update(empty_feed_bridge["lineage"])
        summary["recovery_previous_durable_cursor"] = empty_feed_bridge[
            "recovery_previous_durable_cursor"
        ]
        summary["prior_authoritative_empty_feed_sessions"] = empty_feed_bridge[
            "empty_feed_sessions"
        ]
    summary["recovery_isolated_tail_path"] = (
        str(recovery.isolated_tail_path.resolve())
        if recovery.isolated_tail_path is not None
        else ""
    )
    summary["recovery_isolated_byte_count"] = int(recovery.isolated_byte_count)
    summary["prior_recovery_transaction_id"] = (
        recovery.recovery_transaction_id
    )
    summary["prior_recovery_manifest_path"] = (
        str(recovery.recovery_manifest_path.resolve())
        if recovery.recovery_manifest_path is not None
        else ""
    )
    summary["recovery_manifest_ack_required"] = bool(
        recovery.recovery_ack_required
    )

    rows: dict[str, list[dict[str, Any]]] = {"logs": []}
    subscribed: set[str] = set()
    subscribed_at_by_symbol: dict[str, str] = {}
    invalid: set[str] = set()
    stream_state_lock = threading.Lock()
    stop_requested = False
    started_monotonic = time.monotonic()
    last_heartbeat_monotonic = 0.0

    event_engine: Any = None
    main_engine: Any = None
    ctp_gateway: Any = None
    restore_order_guards: Any = None
    try:
        from vnpy_ctp import CtpGateway

        event_engine = EventEngine()
        main_engine = MainEngine(event_engine)
        ctp_gateway = main_engine.add_gateway(CtpGateway)
        restore_order_guards = _install_readonly_order_guards(
            ctp_gateway,
            summary,
        )
        pipeline = TickStreamPipeline(
            feed_session_id=feed_session_id,
            journal_segment_path=journal_segment_path,
            clock=SYSTEM_CLOCK,
            queue_capacity=8192,
            max_buffer_ticks=max_buffer_ticks,
            writer_batch_size=256,
            writer_flush_seconds=0.050,
        )
        restore_gateway = install_gateway_tick_ingress(ctp_gateway, pipeline)
    except Exception as exc:
        (
            close_errors,
            trading_close_state,
            market_data_close_state,
            _aggregate_closed,
        ) = _close_readonly_main_engine(
            main_engine,
            ctp_gateway,
            event_engine,
        )
        summary.update(
            {
                f"pipeline_initialization_{key}": value
                for key, value in close_errors.items()
            }
        )
        if "aggregate_close_error" in close_errors:
            summary["pipeline_initialization_close_error"] = close_errors[
                "aggregate_close_error"
            ]
        _record_trading_api_close_state(summary, trading_close_state)
        _record_market_data_api_close_state(summary, market_data_close_state)
        if restore_order_guards is not None:
            try:
                restore_order_guards()
            except Exception as restore_exc:
                summary["pipeline_initialization_order_guard_restore_error"] = (
                    repr(restore_exc)
                )
        summary["status"] = "stream_blocked_pipeline_initialization_error"
        summary["pipeline_initialization_error"] = repr(exc)
        _publish_blocked_stream_startup(
            heartbeat_path,
            summary=summary,
            previous_heartbeat=previous_heartbeat,
        )
        return summary

    def on_log(event: Any) -> None:
        with stream_state_lock:
            rows["logs"].append(_object_to_row(event.data))
            if len(rows["logs"]) > 500:
                del rows["logs"][:-500]

    def on_tick(event: Any) -> None:
        pipeline.observe_handler(event.data)

    old_sigterm: Any = None
    old_sigint: Any = None
    sigterm_installed = False
    sigint_installed = False

    def request_stop(_signum: int, _frame: Any) -> None:
        nonlocal stop_requested
        stop_requested = True

    def subscribe_new() -> None:
        desired = list(target_symbols) + _manifest_symbols(watch_manifest)
        seen: set[str] = set()
        for vt_symbol in desired:
            vt_symbol = _clean(vt_symbol)
            if not vt_symbol or vt_symbol in seen:
                continue
            seen.add(vt_symbol)
            if vt_symbol in subscribed or vt_symbol in invalid:
                continue
            parsed = _split_vt_symbol(vt_symbol)
            if parsed is None:
                invalid.add(vt_symbol)
                continue
            symbol, exchange = parsed
            main_engine.subscribe(SubscribeRequest(symbol=symbol, exchange=exchange), "CTP")
            summary["subscribe_api_called_count"] += 1
            subscribed.add(vt_symbol)
            subscribed_at_by_symbol[vt_symbol] = datetime.now().isoformat(timespec="microseconds")

    def publish_heartbeat(
        *,
        stopped: bool = False,
        starting: bool = False,
        journal_session_state: str | None = None,
    ) -> dict[str, Any]:
        durable: DurableTickSnapshot = pipeline.durable_snapshot()
        snapshot_latest = {
            vt_symbol: dict(row)
            for vt_symbol, row in durable.latest_by_symbol.items()
        }
        snapshot_ticks = [dict(row) for row in durable.rows]
        snapshot_sequence = int(durable.durable_ingress_sequence)
        with stream_state_lock:
            snapshot_logs = list(rows["logs"])
        log_analysis = _analyze_logs(snapshot_logs)
        desired = set(target_symbols) | set(_manifest_symbols(watch_manifest))
        expected = sorted(item for item in desired if item and item not in invalid)
        missing_tick_symbols = sorted(item for item in expected if item not in snapshot_latest)
        published_latest = {
            vt_symbol: snapshot_latest[vt_symbol]
            for vt_symbol in expected
            if vt_symbol in snapshot_latest
        }
        symbol_tick_watermarks = _symbol_tick_watermarks(
            expected,
            published_latest,
            durable.symbol_watermarks,
        )
        transport_ready = bool(
            log_analysis.get("md_login_success")
            and not stopped
            and not starting
        )
        ready = _tick_stream_ready(
            transport_ready=transport_ready,
            expected_symbol_count=len(expected),
            missing_tick_symbol_count=len(missing_tick_symbols),
            durable_stream_ready=durable.stream_ready,
            prior_gap=(effective_recovery_gaps or None),
            stopped=stopped,
            starting=starting,
        )
        if (
            int(summary.get("send_order_api_attempted_count", 0)) > 0
            or int(summary.get("cancel_order_api_attempted_count", 0)) > 0
        ):
            ready = False
        if ready:
            summary["ever_stream_ready"] = True
        latest_received_at = max(
            (_clean(row.get("received_at")) for row in published_latest.values()),
            default="",
        )
        effective_session_state = journal_session_state or (
            "clean_stopped"
            if stopped
            else "starting"
            if starting
            else "running"
        )
        terminal_snapshot_fault_reasons = (
            _durable_terminal_fault_reasons(durable) if stopped else ()
        )
        terminal_snapshot_downgraded = bool(
            effective_session_state == "clean_stopped"
            and terminal_snapshot_fault_reasons
        )
        if terminal_snapshot_downgraded:
            effective_session_state = "fault_stopped"
            summary["terminal_snapshot_downgraded"] = True
            summary["terminal_snapshot_fault_reasons"] = list(
                terminal_snapshot_fault_reasons
            )
        hard_revocation_reasons = {
            "shutdown_drain_timeout",
            "shutdown_durable_mismatch",
            "ingress_queue_full",
            "ingress_not_accepting",
            "ingress_thread_violation",
            "ingress_capture_exception",
            "ingress_fault_latch_exception",
        }
        revoked_from = (
            int(durable.gap.start_ingress_sequence)
            if durable.gap and durable.gap.reason in hard_revocation_reasons
            else 0
        )
        revoked_through = (
            int(durable.gap.end_ingress_sequence) if revoked_from else 0
        )
        revocation_reason = durable.gap.reason if revoked_from and durable.gap else ""
        heartbeat = {
            **summary,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": (
                "tick_stream_stopped"
                if stopped
                else "tick_stream_starting"
                if starting
                else "tick_stream_ready"
                if ready
                else "tick_stream_waiting_for_market_data"
            ),
            "stream_ready": ready,
            "transport_ready": transport_ready,
            "stopped": bool(stopped),
            "clean_shutdown": effective_session_state == "clean_stopped",
            "journal_session_state": effective_session_state,
            "terminal_snapshot_downgraded": terminal_snapshot_downgraded,
            "terminal_snapshot_fault_reasons": list(
                terminal_snapshot_fault_reasons
            ),
            "journal_schema": JOURNAL_SCHEMA_FRAMED_V1,
            "journal_format": JOURNAL_FORMAT_FRAMED_V1,
            "journal_schema_version": JOURNAL_BATCH_COMMIT_SCHEMA_VERSION,
            "symbol_eviction_watermark_schema_version": (
                SYMBOL_EVICTION_WATERMARK_SCHEMA_VERSION
            ),
            "journal_authority_committed": True,
            "pid": os.getpid(),
            "stream_sequence": snapshot_sequence,
            "journal_tick_count": snapshot_sequence,
            "buffered_tick_count": len(snapshot_ticks),
            "last_ingress_sequence": int(durable.last_ingress_sequence),
            "durable_ingress_sequence": snapshot_sequence,
            "durable_journal_byte_offset": int(
                durable.durable_journal_byte_offset
            ),
            "queue_depth": int(durable.queue_depth),
            "queue_capacity": int(durable.queue_capacity),
            "dropped_tick_count": int(durable.dropped_tick_count),
            "gap_latched": durable.gap is not None,
            "gap_start_ingress_sequence": (
                int(durable.gap.start_ingress_sequence) if durable.gap else 0
            ),
            "gap_end_ingress_sequence": (
                int(durable.gap.end_ingress_sequence) if durable.gap else 0
            ),
            "gap_reason": durable.gap.reason if durable.gap else "",
            "journal_commit_revoked_from_ingress_sequence": revoked_from,
            "journal_commit_revoked_through_ingress_sequence": revoked_through,
            "journal_commit_revocation_reason": revocation_reason,
            "writer_fault": (
                asdict(durable.writer_fault) if durable.writer_fault else None
            ),
            "writer_alive": bool(durable.writer_alive),
            "accepting": bool(durable.accepting),
            "journal_segment_path": str(durable.journal_segment_path.resolve()),
            "subscribed_symbols": sorted(subscribed),
            "subscribed_at_by_symbol": subscribed_at_by_symbol,
            "invalid_symbols": sorted(invalid),
            "missing_tick_symbols": missing_tick_symbols,
            "latest_tick_received_at": latest_received_at,
            # Both maps are bounded to the current watch set.  The compact
            # watermark map is producer-side prewiring for the Task 3 Stage904
            # eviction gate; until that consumer lands it is diagnostic only,
            # just like latest_ticks, and cannot authorize trading.
            "symbol_tick_watermarks": symbol_tick_watermarks,
            "latest_ticks": published_latest,
            "log_analysis": log_analysis,
            "uptime_seconds": round(time.monotonic() - started_monotonic, 3),
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
            "send_order_api_attempted_count": int(
                summary.get("send_order_api_attempted_count", 0)
            ),
            "cancel_order_api_attempted_count": int(
                summary.get("cancel_order_api_attempted_count", 0)
            ),
            "order_api_called_count": 0,
        }
        return _publish_tick_snapshot_commit(
            tick_path=TICK_PATH,
            heartbeat_path=heartbeat_path,
            tick_rows=snapshot_ticks,
            heartbeat=heartbeat,
        )

    final_heartbeat: dict[str, Any] = {}
    shutdown_report: Any = None
    authority_handed_off = False
    lifecycle_guard_active = False
    gateway_capture_quiesced = False
    writer_quiesced = False
    pipeline_quiesced = False
    try:
        event_engine.register(EVENT_LOG, on_log)
        event_engine.register(EVENT_TICK, on_tick)
        old_sigterm = signal.getsignal(signal.SIGTERM)
        old_sigint = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGTERM, request_stop)
        sigterm_installed = True
        signal.signal(signal.SIGINT, request_stop)
        sigint_installed = True
        _publish_lifecycle_guard(
            heartbeat_path,
            feed_session_id=feed_session_id,
            summary=summary,
            phase="startup_handoff",
            previous_heartbeat=previous_heartbeat,
        )
        lifecycle_guard_active = True
        pipeline.start()
        if not pipeline.wait_until_journal_ready(timeout_seconds=2.0):
            summary["status"] = "stream_blocked_journal_header_not_durable"
            raise RuntimeError("journal header durability handshake timed out")
        writer_snapshot = pipeline.durable_snapshot()
        if writer_snapshot.writer_fault is not None or not writer_snapshot.writer_alive:
            summary["status"] = "stream_blocked_journal_writer_not_live"
            raise RuntimeError("journal writer stopped before authority handoff")
        final_heartbeat = publish_heartbeat(starting=True)
        authority_handed_off = True
        committed_starting_heartbeat = _heartbeat_owned_by_session(
            heartbeat_path,
            feed_session_id,
        )
        if not committed_starting_heartbeat:
            summary["status"] = "stream_blocked_recovery_manifest_ack_error"
            raise RuntimeError("starting heartbeat authority could not be reread")
        try:
            acknowledge_recovery_manifest(
                recovery,
                heartbeat_path,
            )
        except Exception:
            summary["status"] = "stream_blocked_recovery_manifest_ack_error"
            raise
        summary["recovery_manifest_acknowledged"] = True
        final_heartbeat = committed_starting_heartbeat
        try:
            _clear_lifecycle_guard(heartbeat_path)
            lifecycle_guard_active = False
            summary["startup_lifecycle_guard_cleared"] = True
        except Exception:
            summary["status"] = "stream_blocked_lifecycle_guard_cleanup_error"
            raise
        handoff_snapshot = pipeline.durable_snapshot()
        if (
            final_heartbeat.get("writer_fault") is not None
            or final_heartbeat.get("writer_alive") is not True
            or handoff_snapshot.writer_fault is not None
            or not handoff_snapshot.writer_alive
        ):
            summary["status"] = "stream_blocked_journal_writer_not_live"
            raise RuntimeError("journal writer stopped during authority handoff")
        main_engine.connect(_ctp_setting_from_env(), "CTP")
        deadline = time.monotonic() + max(0, int(pre_subscribe_wait_seconds))
        while time.monotonic() < deadline and not stop_requested:
            time.sleep(0.1)
        subscribe_new()
        summary["status"] = "tick_stream_running"
        while not stop_requested:
            now_monotonic = time.monotonic()
            if parent_pid > 0:
                try:
                    os.kill(parent_pid, 0)
                except ProcessLookupError:
                    summary["status"] = "tick_stream_parent_exited"
                    break
            if duration_seconds > 0 and now_monotonic - started_monotonic >= duration_seconds:
                break
            if now_monotonic - last_heartbeat_monotonic >= max(0.2, float(heartbeat_seconds)):
                subscribe_new()
                final_heartbeat = publish_heartbeat()
                last_heartbeat_monotonic = now_monotonic
            time.sleep(0.05)
    except Exception as exc:
        if not _clean(summary.get("status")).startswith("stream_blocked_"):
            summary["status"] = "tick_stream_exception"
        summary["exception"] = repr(exc)
    finally:
        summary["gateway_capture_quiesced"] = False
        summary["writer_quiesced"] = False
        summary["pipeline_quiesced"] = False
        guard_authority = _heartbeat_owned_by_session(
            heartbeat_path,
            feed_session_id,
        )
        if guard_authority:
            authority_handed_off = True
            final_heartbeat = guard_authority
        if authority_handed_off:
            try:
                _publish_lifecycle_guard(
                    heartbeat_path,
                    feed_session_id=feed_session_id,
                    summary=summary,
                    phase="terminal_commit",
                    previous_heartbeat=guard_authority or final_heartbeat,
                )
                lifecycle_guard_active = True
            except Exception as exc:
                summary["lifecycle_guard_terminal_publish_error"] = repr(exc)
        quiesce_errors = _quiesce_market_data_ingress(
            ctp_gateway,
            pipeline,
            restore_gateway,
        )
        summary.update(quiesce_errors)
        (
            trading_close_once,
            trading_close_state,
            trading_close_fenced,
        ) = _install_trading_api_close_fence(ctp_gateway)
        aggregate_closed = False
        if "market_data_close_error" in quiesce_errors:
            summary["aggregate_close_skipped_market_data_uncertain"] = True
            summary.update(
                _close_without_market_data_retry(
                    main_engine,
                    ctp_gateway,
                    event_engine,
                    trading_close=trading_close_once,
                )
            )
        elif not trading_close_fenced:
            summary["aggregate_close_skipped_trading_api_unfenced"] = True
            summary.update(
                _close_without_market_data_retry(
                    main_engine,
                    ctp_gateway,
                    event_engine,
                    trading_close=trading_close_once,
                )
            )
        else:
            try:
                main_engine.close()
                aggregate_closed = True
            except Exception as exc:
                summary["aggregate_close_error"] = repr(exc)
                summary.update(
                    _close_without_market_data_retry(
                        main_engine,
                        ctp_gateway,
                        event_engine,
                        trading_close=trading_close_once,
                    )
                )
        _record_trading_api_close_state(summary, trading_close_state)
        if aggregate_closed:
            try:
                restore_gateway()
                gateway_capture_quiesced = True
            except Exception as exc:
                quiesce_errors["gateway_restore_error"] = repr(exc)
            if gateway_capture_quiesced:
                try:
                    restore_order_guards()
                except Exception as exc:
                    quiesce_errors["order_guard_restore_error"] = repr(exc)
        summary["gateway_capture_quiesced"] = gateway_capture_quiesced
        summary.update(quiesce_errors)
        try:
            shutdown_report = pipeline.shutdown(timeout_seconds=2.0)
            summary["shutdown_report"] = asdict(shutdown_report)
        except Exception as exc:
            summary["shutdown_error"] = repr(exc)
        post_shutdown_snapshot = pipeline.durable_snapshot()
        writer_quiesced = not post_shutdown_snapshot.writer_alive
        pipeline_quiesced = bool(
            writer_quiesced and not post_shutdown_snapshot.accepting
        )
        summary["writer_quiesced"] = writer_quiesced
        summary["pipeline_quiesced"] = pipeline_quiesced
        committed_heartbeat = _heartbeat_owned_by_session(
            heartbeat_path,
            feed_session_id,
        )
        if committed_heartbeat:
            authority_handed_off = True
            final_heartbeat = committed_heartbeat
        if authority_handed_off:
            try:
                _publish_lifecycle_guard(
                    heartbeat_path,
                    feed_session_id=feed_session_id,
                    summary=summary,
                    phase="terminal_commit",
                    previous_heartbeat=committed_heartbeat,
                )
                lifecycle_guard_active = True
            except Exception as exc:
                summary["lifecycle_guard_terminal_publish_error"] = repr(exc)
                visible_guard, guard_error = _load_active_lifecycle_guard(
                    heartbeat_path
                )
                lifecycle_guard_active = bool(visible_guard or guard_error)
            clean_shutdown = bool(
                aggregate_closed
                and not quiesce_errors
                and "shutdown_error" not in summary
                and "exception" not in summary
                and "lifecycle_guard_terminal_publish_error" not in summary
                and int(summary.get("send_order_api_attempted_count", 0)) == 0
                and int(summary.get("cancel_order_api_attempted_count", 0)) == 0
                and shutdown_report is not None
                and shutdown_report.drained
                and shutdown_report.writer_fault is None
                and shutdown_report.gap is None
            )
            recovery_required = bool(
                not clean_shutdown
                and aggregate_closed
                and not quiesce_errors
                and "shutdown_error" not in summary
                and "exception" not in summary
                and int(summary.get("send_order_api_attempted_count", 0)) == 0
                and int(summary.get("cancel_order_api_attempted_count", 0)) == 0
                and shutdown_report is not None
                and shutdown_report.writer_fault is not None
                and shutdown_report.writer_fault.kind == "journal_write_error"
                and (
                    shutdown_report.gap is None
                    or shutdown_report.gap.reason == "journal_write_error"
                )
            )
            final_session_state = (
                "clean_stopped"
                if clean_shutdown
                else "recovery_required_stopped"
                if recovery_required
                else "fault_stopped"
            )
            try:
                final_heartbeat = publish_heartbeat(
                    stopped=True,
                    journal_session_state=final_session_state,
                )
            except Exception as exc:
                summary["final_heartbeat_error"] = repr(exc)
                final_heartbeat = _publish_fail_closed_current_authority(
                    heartbeat_path,
                    feed_session_id=feed_session_id,
                    summary=summary,
                    fallback_heartbeat=final_heartbeat,
                    journal_session_state=(
                        "recovery_required_stopped"
                        if final_session_state == "clean_stopped"
                        else final_session_state
                    ),
                )
        else:
            try:
                final_heartbeat = _publish_blocked_stream_startup(
                    heartbeat_path,
                    summary=summary,
                    previous_heartbeat=previous_heartbeat,
                )
            except Exception as exc:
                summary["blocked_final_heartbeat_error"] = repr(exc)
        signal_restore_errors: dict[str, str] = {}
        for signum, old_handler, installed, label in (
            (signal.SIGINT, old_sigint, sigint_installed, "sigint"),
            (signal.SIGTERM, old_sigterm, sigterm_installed, "sigterm"),
        ):
            if not installed:
                continue
            try:
                signal.signal(signum, old_handler)
            except Exception as exc:
                signal_restore_errors[f"{label}_restore_error"] = repr(exc)
        if signal_restore_errors:
            quiesce_errors.update(signal_restore_errors)
            summary.update(signal_restore_errors)
            if authority_handed_off:
                try:
                    final_heartbeat = publish_heartbeat(
                        stopped=True,
                        journal_session_state="fault_stopped",
                    )
                except Exception as exc:
                    summary["signal_restore_final_heartbeat_error"] = repr(
                        exc
                    )
                    final_heartbeat = _publish_fail_closed_current_authority(
                        heartbeat_path,
                        feed_session_id=feed_session_id,
                        summary=summary,
                        fallback_heartbeat=final_heartbeat,
                        journal_session_state="fault_stopped",
                    )
            else:
                _publish_blocked_stream_startup(
                    heartbeat_path,
                    summary=summary,
                    previous_heartbeat=previous_heartbeat,
                )
        if lifecycle_guard_active and not signal_restore_errors:
            terminal_state = _clean(
                final_heartbeat.get("journal_session_state")
            )
            terminal_authority = final_heartbeat.get(
                "journal_authority_committed"
            )
            terminal_persisted = bool(
                final_heartbeat.get("stopped") is True
                and final_heartbeat.get("stream_ready") is False
                and final_heartbeat.get("transport_ready") is False
                and gateway_capture_quiesced
                and writer_quiesced
                and pipeline_quiesced
                and terminal_state
                in {
                    "clean_stopped",
                    "recovery_required_stopped",
                    "fault_stopped",
                }
                and terminal_authority is True
                and summary.get("journal_authority_unsafe") is not True
            )
            if terminal_persisted:
                try:
                    _clear_lifecycle_guard(heartbeat_path)
                    lifecycle_guard_active = False
                except Exception as exc:
                    summary["lifecycle_guard_cleanup_error"] = repr(exc)
        if (
            authority_handed_off
            and not lifecycle_guard_active
            and not (
                gateway_capture_quiesced
                and writer_quiesced
                and pipeline_quiesced
            )
        ):
            summary["status"] = "stream_fatal_unfenced_shutdown"
            summary["fatal_process_exit_code"] = 2
            os._exit(2)
            raise RuntimeError("fatal_process_exit_returned")
    final_durable = pipeline.durable_snapshot()
    return {
        **summary,
        "status": _clean(final_heartbeat.get("status")) or summary["status"],
        "terminal_reason": _clean(summary.get("status")),
        "stopped": True,
        "clean_shutdown": final_heartbeat.get("clean_shutdown"),
        "stream_ready": final_heartbeat.get("stream_ready"),
        "transport_ready": final_heartbeat.get("transport_ready"),
        "journal_authority_committed": final_heartbeat.get(
            "journal_authority_committed"
        ),
        "journal_session_state": _clean(
            final_heartbeat.get("journal_session_state")
        ),
        "stream_sequence": int(final_durable.durable_ingress_sequence),
        "journal_tick_count": int(final_durable.durable_ingress_sequence),
        "last_ingress_sequence": int(final_durable.last_ingress_sequence),
        "durable_ingress_sequence": int(final_durable.durable_ingress_sequence),
        "durable_journal_byte_offset": int(
            final_durable.durable_journal_byte_offset
        ),
        "journal_schema": final_durable.journal_schema,
        "queue_depth": int(final_durable.queue_depth),
        "dropped_tick_count": int(final_durable.dropped_tick_count),
        "gap_latched": final_durable.gap is not None,
        "writer_fault": (
            asdict(final_durable.writer_fault)
            if final_durable.writer_fault
            else None
        ),
        "writer_alive": bool(final_durable.writer_alive),
        "accepting": bool(final_durable.accepting),
        "subscribed_symbols": sorted(subscribed),
        "invalid_symbols": sorted(invalid),
        "latest_tick_received_at": final_heartbeat.get("latest_tick_received_at", ""),
        "send_order_api_attempted_count": int(
            summary.get("send_order_api_attempted_count", 0)
        ),
        "cancel_order_api_attempted_count": int(
            summary.get("cancel_order_api_attempted_count", 0)
        ),
        "order_api_called_count": 0,
    }


def _run_stream(
    *,
    connect: bool,
    pre_subscribe_wait_seconds: int,
    target_symbols: list[str],
    watch_manifest: Path | None,
    journal_path: Path,
    heartbeat_path: Path,
    duration_seconds: int,
    heartbeat_seconds: float,
    max_buffer_ticks: int,
    parent_pid: int = 0,
) -> dict[str, Any]:
    """Run exactly one authoritative stream producer per heartbeat path."""

    try:
        with _exclusive_stream_owner_lock(heartbeat_path):
            return _run_stream_owned(
                connect=connect,
                pre_subscribe_wait_seconds=pre_subscribe_wait_seconds,
                target_symbols=target_symbols,
                watch_manifest=watch_manifest,
                journal_path=journal_path,
                heartbeat_path=heartbeat_path,
                duration_seconds=duration_seconds,
                heartbeat_seconds=heartbeat_seconds,
                max_buffer_ticks=max_buffer_ticks,
                parent_pid=parent_pid,
            )
    except RuntimeError as exc:
        if str(exc) != "stream_owner_lock_contended":
            raise
        # A contender has no authority to revoke or rewrite the active owner.
        return {
            "model_tag": MODEL_TAG,
            "mode": "continuous_tick_stream",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "connect_requested": bool(connect),
            "journal_path": str(journal_path.resolve()),
            "heartbeat_path": str(heartbeat_path.resolve()),
            "real_order_enabled": False,
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
            "send_order_api_attempted_count": 0,
            "cancel_order_api_attempted_count": 0,
            "order_api_called_count": 0,
            "stream_ready": False,
            "transport_ready": False,
            "stopped": True,
            "status": "stream_blocked_owner_lock_contended",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage608 CTP/vn.py read-only tick snapshot probe.")
    parser.add_argument("--connect", action="store_true", help="Actually attempt CTP connection. No orders are sent.")
    parser.add_argument("--stream", action="store_true", help="Keep one read-only market-data session alive and append ordered ticks.")
    parser.add_argument("--wait-seconds", type=int, default=20)
    parser.add_argument("--pre-subscribe-wait-seconds", type=int, default=5)
    parser.add_argument("--submit-plan", type=Path, default=DEFAULT_SUBMIT_PLAN)
    parser.add_argument("--vt-symbol", action="append", default=[], help="Additional vt_symbol to subscribe/read.")
    parser.add_argument("--watch-manifest", type=Path, default=None, help="Optional JSON/CSV/text symbol manifest reread while streaming.")
    parser.add_argument("--journal-path", type=Path, default=STREAM_JOURNAL_PATH)
    parser.add_argument("--heartbeat-path", type=Path, default=STREAM_HEARTBEAT_PATH)
    parser.add_argument("--duration-seconds", type=int, default=0, help="0 means run until SIGTERM/SIGINT.")
    parser.add_argument("--heartbeat-seconds", type=float, default=1.0)
    parser.add_argument("--max-buffer-ticks", type=int, default=2000)
    parser.add_argument("--parent-pid", type=int, default=0, help="Exit when this owning daemon process no longer exists.")
    args = parser.parse_args()

    target_symbols = _load_target_symbols(args.submit_plan, args.vt_symbol)
    if args.stream:
        result = _run_stream(
            connect=bool(args.connect),
            pre_subscribe_wait_seconds=int(args.pre_subscribe_wait_seconds),
            target_symbols=target_symbols,
            watch_manifest=args.watch_manifest,
            journal_path=args.journal_path,
            heartbeat_path=args.heartbeat_path,
            duration_seconds=int(args.duration_seconds),
            heartbeat_seconds=float(args.heartbeat_seconds),
            max_buffer_ticks=int(args.max_buffer_ticks),
            parent_pid=int(args.parent_pid),
        )
        _atomic_write_df(TARGET_SYMBOL_PATH, [{"vt_symbol": item} for item in target_symbols])
        _atomic_write_json(SUMMARY_PATH, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"summary json: {SUMMARY_PATH}")
        exit_code = _stream_exit_code(connect=bool(args.connect), result=result)
        if exit_code:
            raise SystemExit(exit_code)
        return
    result = _run_probe(
        connect=bool(args.connect),
        wait_seconds=int(args.wait_seconds),
        pre_subscribe_wait_seconds=int(args.pre_subscribe_wait_seconds),
        target_symbols=target_symbols,
    )
    rows = result.pop("rows")
    _write_df(ACCOUNT_PATH, rows["accounts"])
    _write_df(POSITION_PATH, rows["positions"])
    _write_df(ORDER_PATH, rows["orders"])
    _write_df(TRADE_PATH, rows["trades"])
    _write_df(CONTRACT_PATH, rows["contracts"])
    _write_df(TICK_PATH, rows["ticks"])
    _write_df(LOG_PATH, rows["logs"])
    _write_df(POSITION_QUERY_CALLBACK_PATH, rows["position_query_callbacks"])
    _write_df(TARGET_SYMBOL_PATH, [{"vt_symbol": item} for item in target_symbols])
    SUMMARY_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"summary json: {SUMMARY_PATH}")
    exit_code = _probe_exit_code(connect=bool(args.connect), result=result)
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
