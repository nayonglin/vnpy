from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from qmt_roll_official_live_c9_intraday_state import (
    PHASE_RETRY_RECLAIM_LATCHED,
    RETRY_OPEN_ACTION_ROLE,
)


LATE_RETRY_FILL_MAX_SECONDS = 15 * 60
MAX_CLOCK_SKEW_SECONDS = 5
LOCAL_TZ = ZoneInfo("Asia/Shanghai")


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number:
        return default
    return number


def _to_int(value: Any, default: int = 0) -> int:
    number = _to_float(value, float(default))
    if abs(number - round(number)) > 1e-9:
        return default
    return int(round(number))


def _parse_time(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=LOCAL_TZ)
    return parsed.astimezone(LOCAL_TZ)


def _list_value(value: Any) -> list[str]:
    raw = value
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            raw = parsed if isinstance(parsed, list) else [raw]
        except json.JSONDecodeError:
            raw = [raw]
    if not isinstance(raw, (list, tuple, set)):
        return []
    return list(dict.fromkeys(_clean(item) for item in raw if _clean(item)))


def _normalize_direction(value: Any) -> str:
    text = _clean(value).lower()
    if text in {"short", "空", "direction.short"}:
        return "short"
    if text in {"long", "多", "direction.long"}:
        return "long"
    return text


def _normalize_offset(value: Any) -> str:
    text = _clean(value).lower()
    if text in {
        "close",
        "closetoday",
        "closeyesterday",
        "平",
        "平今",
        "平昨",
        "offset.close",
        "offset.closetoday",
        "offset.closeyesterday",
    }:
        return "close"
    if text in {"open", "开", "offset.open"}:
        return "open"
    return text


def _payloads_by_fingerprint(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    for row in rows:
        fingerprint = _clean(row.get("intent_fingerprint"))
        payload = row.get("intent_payload")
        if fingerprint and isinstance(payload, dict):
            payloads[fingerprint] = payload
    return payloads


def _event_value(
    row: dict[str, Any], payloads: dict[str, dict[str, Any]], key: str
) -> Any:
    value = row.get(key)
    if _clean(value):
        return value
    return payloads.get(_clean(row.get("intent_fingerprint")), {}).get(key)


def _event_matches_state(
    row: dict[str, Any],
    payloads: dict[str, dict[str, Any]],
    state: dict[str, Any],
) -> bool:
    return bool(
        _clean(row.get("target_date")) == _clean(state.get("target_date"))
        and _clean(_event_value(row, payloads, "vt_symbol")).upper()
        == _clean(state.get("vt_symbol")).upper()
        and _normalize_direction(_event_value(row, payloads, "direction"))
        == _normalize_direction(state.get("direction"))
        and _normalize_offset(_event_value(row, payloads, "offset")) == "open"
        and _clean(_event_value(row, payloads, "root_position_id"))
        == _clean(state.get("root_position_id"))
        and _clean(_event_value(row, payloads, "position_epoch_id"))
        == _clean(state.get("position_epoch_id"))
        and _clean(_event_value(row, payloads, "position_cycle_id"))
        == _clean(state.get("position_cycle_id"))
        and _clean(_event_value(row, payloads, "intent_role"))
        == RETRY_OPEN_ACTION_ROLE
    )


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "status": "blocked",
        "reason": reason,
        "manual_intervention_required": 1,
        "ledger_event": {},
    }


def _not_applicable(reason: str) -> dict[str, Any]:
    return {
        "status": "not_applicable",
        "reason": reason,
        "manual_intervention_required": 0,
        "ledger_event": {},
    }


def _query_complete(query: Any) -> bool:
    request_sent_at = _parse_time(query.get("request_sent_at")) if isinstance(query, dict) else None
    completed_at = _parse_time(query.get("completed_at")) if isinstance(query, dict) else None
    return bool(
        isinstance(query, dict)
        and query.get("complete") is True
        and query.get("last_seen") is True
        and _to_int(query.get("error_rows"), -1) == 0
        and _to_int(query.get("request_return_code"), -1) == 0
        and _to_int(query.get("reqid"), 0) > 0
        and _to_int(query.get("callback_count"), 0) > 0
        and request_sent_at is not None
        and completed_at is not None
        and (completed_at - request_sent_at).total_seconds() >= -MAX_CLOCK_SKEW_SECONDS
    )


def _validate_v2_connection_generation(
    *,
    readonly_summary: dict[str, Any],
    summary_bundle: dict[str, Any],
    manifest_account: dict[str, Any],
    summary_account: dict[str, Any],
    trading_day: str,
    generation_uuid: str,
) -> tuple[bool, str, str, str]:
    """Prove every v2 readonly component belongs to one CTP connection epoch."""

    if (
        manifest_account.get("trading_account_response_match") is not True
        or summary_account.get("trading_account_response_match") is not True
    ):
        return (
            False,
            "broker_query_bundle_trading_account_binding_mismatch",
            trading_day,
            generation_uuid,
        )

    snapshot_generation = _clean(
        summary_bundle.get("snapshot_connection_generation")
    )
    snapshot_generations = summary_bundle.get(
        "snapshot_connection_generations"
    )
    required_snapshot_components = (
        "settlement",
        "account",
        "contracts",
        "orders",
        "trades",
        "positions",
    )
    if (
        not snapshot_generation
        or not isinstance(snapshot_generations, dict)
        or summary_bundle.get("full_snapshot_current_generation") is not True
        or any(
            _clean(snapshot_generations.get(name)) != snapshot_generation
            for name in required_snapshot_components
        )
    ):
        return (
            False,
            "broker_query_bundle_snapshot_connection_generation_mismatch",
            trading_day,
            generation_uuid,
        )

    lifecycle = readonly_summary.get("connection_lifecycle")
    if not isinstance(lifecycle, dict):
        return (
            False,
            "broker_query_bundle_connection_lifecycle_missing",
            trading_day,
            generation_uuid,
        )
    lifecycle_snapshots = lifecycle.get("snapshot_connection_generations")
    query_generations = lifecycle.get("query_connection_generations")
    if (
        _clean(lifecycle.get("current_connection_generation"))
        != snapshot_generation
        or _clean(lifecycle.get("readiness_generation"))
        != snapshot_generation
        or not isinstance(lifecycle_snapshots, dict)
        or any(
            _clean(lifecycle_snapshots.get(name)) != snapshot_generation
            for name in required_snapshot_components
        )
        or not isinstance(query_generations, dict)
        or any(
            _clean(query_generations.get(name)) != snapshot_generation
            for name in ("orders", "trades", "positions")
        )
    ):
        return (
            False,
            "broker_query_bundle_connection_lifecycle_mismatch",
            trading_day,
            generation_uuid,
        )
    return True, "", trading_day, generation_uuid


def validate_readonly_query_bundle(
    *,
    readonly_summary: dict[str, Any],
    bundle_manifest: dict[str, Any],
    bundle_evidence: dict[str, Any],
) -> tuple[bool, str, str, str]:
    """Validate one atomically published Stage174 broker query generation.

    Top-level legacy ``row_counts`` are intentionally not part of this
    contract.  Counts and file hashes are bound by the last-published manifest
    and independently re-read from disk by Stage904.
    """

    if not isinstance(bundle_manifest, dict) or not bundle_manifest:
        return False, "broker_query_bundle_manifest_missing", "", ""
    summary_bundle = readonly_summary.get("broker_query_bundle")
    if not isinstance(summary_bundle, dict):
        return False, "broker_query_bundle_summary_missing", "", ""
    manifest_schema = _to_int(bundle_manifest.get("schema_version"), 0)
    summary_schema = _to_int(summary_bundle.get("schema_version"), 0)
    if manifest_schema not in {1, 2}:
        return False, "broker_query_bundle_manifest_schema_invalid", "", ""
    if summary_schema not in {1, 2}:
        return False, "broker_query_bundle_summary_schema_invalid", "", ""
    if manifest_schema != summary_schema:
        return False, "broker_query_bundle_schema_mismatch", "", ""

    generation_uuid = _clean(bundle_manifest.get("generation_uuid"))
    summary_generation = _clean(summary_bundle.get("generation_uuid"))
    try:
        uuid.UUID(generation_uuid)
        generation_uuid_valid = True
    except (ValueError, AttributeError):
        generation_uuid_valid = False
    if (
        not generation_uuid_valid
        or summary_generation != generation_uuid
        or _clean(readonly_summary.get("query_generation_uuid")) != generation_uuid
    ):
        return (
            False,
            "broker_query_bundle_generation_mismatch:"
            f"manifest={generation_uuid};summary={summary_generation}",
            "",
            generation_uuid,
        )

    generated_at = _clean(readonly_summary.get("generated_at"))
    summary_binding = bundle_manifest.get("summary_binding")
    if not isinstance(summary_binding, dict):
        return False, "broker_query_bundle_summary_binding_missing", "", generation_uuid
    if (
        not generated_at
        or _clean(bundle_manifest.get("generated_at")) != generated_at
        or _clean(summary_bundle.get("generated_at")) != generated_at
        or _clean(summary_binding.get("generated_at")) != generated_at
        or _clean(summary_binding.get("status")) != _clean(readonly_summary.get("status"))
    ):
        return False, "broker_query_bundle_summary_binding_mismatch", "", generation_uuid
    if _clean(readonly_summary.get("status")) != "readonly_snapshots_received":
        return False, "broker_query_bundle_summary_status_invalid", "", generation_uuid

    trading_day = _clean(bundle_manifest.get("broker_trading_day"))
    if (
        len(trading_day) != 8
        or not trading_day.isdigit()
        or _clean(summary_bundle.get("broker_trading_day")) != trading_day
        or _clean(readonly_summary.get("broker_trading_day")) != trading_day
    ):
        return (
            False,
            "broker_query_bundle_trading_day_mismatch:"
            f"manifest={trading_day};summary={_clean(readonly_summary.get('broker_trading_day'))}",
            trading_day,
            generation_uuid,
        )

    manifest_account = bundle_manifest.get("account")
    summary_account = summary_bundle.get("account")
    if not isinstance(manifest_account, dict) or not isinstance(summary_account, dict):
        return False, "broker_query_bundle_account_binding_missing", trading_day, generation_uuid
    account_fingerprint = _clean(manifest_account.get("account_fingerprint"))
    if (
        len(account_fingerprint) != 64
        or any(character not in "0123456789abcdef" for character in account_fingerprint.lower())
        or _clean(summary_account.get("account_fingerprint")) != account_fingerprint
        or manifest_account.get("login_account_match") is not True
        or manifest_account.get("response_account_match") is not True
        or summary_account.get("login_account_match") is not True
        or summary_account.get("response_account_match") is not True
    ):
        return False, "broker_query_bundle_account_binding_mismatch", trading_day, generation_uuid
    if manifest_schema == 2:
        (
            connection_generation_ok,
            connection_generation_reason,
            _,
            _,
        ) = _validate_v2_connection_generation(
            readonly_summary=readonly_summary,
            summary_bundle=summary_bundle,
            manifest_account=manifest_account,
            summary_account=summary_account,
            trading_day=trading_day,
            generation_uuid=generation_uuid,
        )
        if not connection_generation_ok:
            return (
                False,
                connection_generation_reason,
                trading_day,
                generation_uuid,
            )

    manifest_queries = bundle_manifest.get("queries")
    summary_queries = summary_bundle.get("queries")
    if not isinstance(manifest_queries, dict) or not isinstance(summary_queries, dict):
        return False, "broker_query_bundle_query_metadata_missing", trading_day, generation_uuid
    metadata_keys = (
        "reqid",
        "request_sent_at",
        "request_return_code",
        "callback_count",
        "data_callback_count",
        "last_seen",
        "completed_at",
        "error_rows",
        "complete",
    )
    query_names = (
        ("orders", "trades", "positions", "account", "contracts")
        if manifest_schema == 2
        else ("orders", "trades", "positions")
    )
    for name in query_names:
        manifest_query = manifest_queries.get(name)
        summary_query = summary_queries.get(name)
        if not _query_complete(manifest_query) or not _query_complete(summary_query):
            return (
                False,
                f"broker_{name}_query_generation_incomplete",
                trading_day,
                generation_uuid,
            )
        query_metadata_keys = metadata_keys
        if name == "positions":
            query_metadata_keys = metadata_keys + (
                "position_raw_row_count",
                "position_normalized_row_count",
                "position_invalid_row_count",
                "position_normalization_complete",
            )
        if any(
            _clean(manifest_query.get(key)) != _clean(summary_query.get(key))
            for key in query_metadata_keys
        ):
            return (
                False,
                f"broker_{name}_query_metadata_mismatch",
                trading_day,
                generation_uuid,
            )
    query_reqids = [
        _to_int(manifest_queries[name].get("reqid"), 0)
        for name in query_names
    ]
    if not all(query_reqids) or len(set(query_reqids)) != len(query_reqids):
        return (
            False,
            "broker_query_reqids_not_distinct",
            trading_day,
            generation_uuid,
        )
    query_times = {
        name: (
            _parse_time(manifest_queries[name].get("request_sent_at")),
            _parse_time(manifest_queries[name].get("completed_at")),
        )
        for name in query_names
    }
    if any(
        next_request is None
        or prior_completed is None
        or (next_request - prior_completed).total_seconds()
        < -MAX_CLOCK_SKEW_SECONDS
        for prior_name, next_name in zip(
            query_names,
            query_names[1:],
            strict=False,
        )
        for prior_completed, next_request in (
            (query_times[prior_name][1], query_times[next_name][0]),
        )
    ):
        return (
            False,
            "broker_query_callback_timeline_invalid",
            trading_day,
            generation_uuid,
        )

    if (
        bundle_manifest.get("complete") is not True
        or summary_bundle.get("complete") is not True
        or bundle_manifest.get("trade_order_join_complete") is not True
        or summary_bundle.get("trade_order_join_complete") is not True
        or bundle_manifest.get("trade_identity_complete") is not True
        or summary_bundle.get("trade_identity_complete") is not True
    ):
        return False, "broker_query_bundle_not_complete", trading_day, generation_uuid

    manifest_artifacts = bundle_manifest.get("artifacts")
    summary_artifacts = summary_bundle.get("artifacts")
    evidence_artifacts = bundle_evidence.get("artifacts")
    if not all(
        isinstance(value, dict)
        for value in (manifest_artifacts, summary_artifacts, evidence_artifacts)
    ):
        return False, "broker_query_bundle_artifact_metadata_missing", trading_day, generation_uuid
    for name in ("orders", "trades", "positions"):
        manifest_artifact = manifest_artifacts.get(name)
        summary_artifact = summary_artifacts.get(name)
        actual_artifact = evidence_artifacts.get(name)
        if not all(
            isinstance(value, dict)
            for value in (manifest_artifact, summary_artifact, actual_artifact)
        ):
            return (
                False,
                f"broker_query_bundle_{name}_artifact_missing",
                trading_day,
                generation_uuid,
            )
        manifest_count = _to_int(manifest_artifact.get("row_count"), -1)
        manifest_hash = _clean(manifest_artifact.get("sha256"))
        if (
            manifest_count < 0
            or len(manifest_hash) != 64
            or any(character not in "0123456789abcdef" for character in manifest_hash.lower())
            or manifest_count != _to_int(summary_artifact.get("row_count"), -2)
            or manifest_count != _to_int(actual_artifact.get("row_count"), -3)
            or manifest_hash != _clean(summary_artifact.get("sha256"))
            or manifest_hash != _clean(actual_artifact.get("sha256"))
        ):
            return (
                False,
                f"broker_query_bundle_{name}_count_or_hash_mismatch",
                trading_day,
                generation_uuid,
            )
        if name in {"orders", "trades"}:
            if manifest_count != _to_int(
                manifest_queries[name].get("data_callback_count"), -1
            ):
                return (
                    False,
                    f"broker_query_bundle_{name}_callback_row_count_mismatch",
                    trading_day,
                    generation_uuid,
                )
        elif (
            manifest_count
            != _to_int(
                manifest_queries["positions"].get(
                    "position_normalized_row_count"
                ),
                -1,
            )
            or _to_int(
                manifest_queries["positions"].get("position_raw_row_count"),
                -1,
            )
            != _to_int(
                manifest_queries["positions"].get("data_callback_count"),
                -2,
            )
            or _to_int(
                manifest_queries["positions"].get("position_invalid_row_count"),
                -1,
            )
            != 0
            or manifest_queries["positions"].get(
                "position_normalization_complete"
            )
            is not True
        ):
            return (
                False,
                "broker_query_bundle_positions_normalization_mismatch",
                trading_day,
                generation_uuid,
            )
        generations = set(_list_value(actual_artifact.get("generation_uuids")))
        if generations and generations != {generation_uuid}:
            return (
                False,
                f"broker_query_bundle_{name}_row_generation_mismatch:{sorted(generations)}",
                trading_day,
                generation_uuid,
            )
        if manifest_count > 0 and generations != {generation_uuid}:
            return (
                False,
                f"broker_query_bundle_{name}_row_generation_missing",
                trading_day,
                generation_uuid,
            )
        fingerprints = set(
            _list_value(actual_artifact.get("account_fingerprints"))
        )
        if manifest_count > 0 and fingerprints != {account_fingerprint}:
            return (
                False,
                f"broker_query_bundle_{name}_row_account_mismatch",
                trading_day,
                generation_uuid,
            )
    trades_evidence = evidence_artifacts["trades"]
    if (
        trades_evidence.get("order_mapping_complete") is not True
        or trades_evidence.get("stable_trade_identity_complete") is not True
    ):
        return (
            False,
            "broker_query_bundle_trade_identity_or_order_mapping_incomplete",
            trading_day,
            generation_uuid,
        )
    return True, "complete_same_generation_broker_query_bundle", trading_day, generation_uuid


def build_late_retry_fill_reconciliation(
    *,
    state: dict[str, Any],
    base: dict[str, Any],
    ledger_rows: list[dict[str, Any]],
    readonly_summary: dict[str, Any],
    bundle_manifest: dict[str, Any] | None = None,
    bundle_evidence: dict[str, Any] | None = None,
    now: datetime | None = None,
    max_snapshot_age_seconds: int = 300,
    max_clock_skew_seconds: int = MAX_CLOCK_SKEW_SECONDS,
    max_fill_window_seconds: int = LATE_RETRY_FILL_MAX_SECONDS,
) -> dict[str, Any]:
    """Prove a callback-less retry fill from one complete broker generation.

    This routine never guesses from a position row alone.  The current broker
    epoch must consist solely of trades for one ``vt_orderid`` and that order
    must map to exactly one durable Stage931 retry intent in the original
    position epoch/cycle.  Ambiguous evidence is deliberately returned as a
    manual-intervention blocker.
    """

    if _clean(state.get("phase")) != PHASE_RETRY_RECLAIM_LATCHED:
        return _not_applicable("state_not_retry_reclaim_latched")
    if _clean(base.get("position_source")) != "broker":
        return _not_applicable("position_source_not_broker")
    if _to_int(base.get("broker_epoch_reconstruction_complete"), 0) != 1:
        return _blocked("broker_current_epoch_not_complete")

    bundle_ok, bundle_reason, broker_trading_day, bundle_generation = (
        validate_readonly_query_bundle(
            readonly_summary=readonly_summary,
            bundle_manifest=bundle_manifest or {},
            bundle_evidence=bundle_evidence or {},
        )
    )
    if not bundle_ok:
        return _blocked(bundle_reason)
    if (
        _clean(base.get("broker_query_generation_uuid")) != bundle_generation
        or _clean(base.get("broker_query_trading_day")) != broker_trading_day
    ):
        return _blocked(
            "broker_epoch_query_generation_binding_mismatch:"
            f"base={_clean(base.get('broker_query_generation_uuid'))}/"
            f"{_clean(base.get('broker_query_trading_day'))};"
            f"bundle={bundle_generation}/{broker_trading_day}"
        )

    summary_bundle = readonly_summary.get("broker_query_bundle", {})
    query_metadata = summary_bundle.get("queries", {}) if isinstance(summary_bundle, dict) else {}
    query_request_times = [
        _parse_time((query_metadata.get(name) or {}).get("request_sent_at"))
        for name in ("orders", "trades", "positions")
    ]
    query_completion_times = [
        _parse_time((query_metadata.get(name) or {}).get("completed_at"))
        for name in ("orders", "trades", "positions")
    ]
    if any(value is None for value in query_request_times + query_completion_times):
        return _blocked("readonly_query_timeline_missing")
    concrete_request_times = [value for value in query_request_times if value is not None]
    concrete_completion_times = [value for value in query_completion_times if value is not None]
    query_started_at = min(concrete_request_times)
    snapshot_at = max(concrete_completion_times)
    trade_query_completed_at = query_completion_times[1]
    position_query_completed_at = query_completion_times[2]
    published_at = _parse_time(readonly_summary.get("generated_at"))
    current = now or datetime.now(tz=LOCAL_TZ)
    if current.tzinfo is None:
        current = current.replace(tzinfo=LOCAL_TZ)
    else:
        current = current.astimezone(LOCAL_TZ)
    if published_at is None:
        return _blocked("readonly_snapshot_publish_time_missing")
    if published_at < snapshot_at and (
        snapshot_at - published_at
    ).total_seconds() > max_clock_skew_seconds:
        return _blocked("readonly_snapshot_published_before_query_completion")
    publish_age = (current - published_at).total_seconds()
    if publish_age < -max_clock_skew_seconds:
        return _blocked(f"readonly_snapshot_age_invalid:{publish_age}")
    snapshot_age = (current - snapshot_at).total_seconds()
    if snapshot_age < -max_clock_skew_seconds or snapshot_age > max_snapshot_age_seconds:
        return _blocked(f"readonly_snapshot_age_invalid:{snapshot_age}")
    if _clean(readonly_summary.get("status")) != "readonly_snapshots_received":
        return _blocked("readonly_snapshot_status_invalid")
    snapshot = readonly_summary.get("broker_snapshot")
    if not isinstance(snapshot, dict):
        return _blocked("readonly_broker_snapshot_missing")
    if (
        _clean(snapshot.get("position_snapshot_state")) != "positions_received"
        or snapshot.get("position_query_last_seen") is not True
        or _to_int(snapshot.get("position_query_error_rows"), -1) != 0
    ):
        return _blocked("readonly_position_generation_not_complete")
    manifest_artifacts = bundle_manifest.get("artifacts", {}) if isinstance(bundle_manifest, dict) else {}
    summary_trade_rows = _to_int(
        (manifest_artifacts.get("trades") or {}).get("row_count")
        if isinstance(manifest_artifacts.get("trades"), dict)
        else None,
        -1,
    )
    base_trade_rows = _to_int(base.get("broker_trade_snapshot_rows"), -1)
    if summary_trade_rows < 0 or summary_trade_rows != base_trade_rows:
        return _blocked(
            "readonly_trade_generation_row_count_mismatch:"
            f"summary={summary_trade_rows};csv={base_trade_rows}"
        )

    order_ids = _list_value(base.get("broker_position_epoch_order_ids"))
    trade_identities = _list_value(
        base.get("broker_position_epoch_trade_identities")
    )
    if _to_int(base.get("broker_position_epoch_order_identity_complete"), 0) != 1:
        return _blocked("broker_current_epoch_order_identity_incomplete")
    if _to_int(base.get("broker_position_epoch_trade_identity_complete"), 0) != 1:
        return _blocked("broker_current_epoch_trade_identity_incomplete")
    if len(order_ids) != 1:
        return _blocked(f"broker_current_epoch_order_id_ambiguous:{order_ids}")
    if not trade_identities:
        return _blocked("broker_current_epoch_trade_identity_missing")
    vt_orderid = order_ids[0]
    broker_entry_at_text = _clean(base.get("broker_position_epoch_entry_at"))
    broker_entry_at = _parse_time(broker_entry_at_text)
    if broker_entry_at is None:
        return _blocked("broker_current_epoch_entry_time_missing")
    broker_reported_date = _clean(base.get("broker_position_epoch_reported_date"))
    try:
        broker_trading_date = datetime.strptime(
            broker_trading_day, "%Y%m%d"
        ).date().isoformat()
    except ValueError:
        return _blocked("broker_query_bundle_trading_day_invalid")
    if broker_reported_date not in {
        _clean(state.get("target_date")),
        broker_trading_date,
    }:
        return _blocked(
            "broker_current_epoch_trade_date_outside_bound_trading_days:"
            f"trade={broker_reported_date};target={_clean(state.get('target_date'))};"
            f"broker={broker_trading_date}"
        )
    broker_volume = _to_float(base.get("broker_open_trade_volume"), 0.0)
    current_volume = _to_float(base.get("volume"), 0.0)
    broker_price = _to_float(base.get("broker_fill_price"), 0.0)
    if (
        broker_volume <= 0
        or abs(broker_volume - current_volume) > 1e-9
        or abs(broker_volume - round(broker_volume)) > 1e-9
    ):
        return _blocked(
            "broker_current_epoch_volume_invalid:"
            f"trades={broker_volume};position={current_volume}"
        )
    if broker_price <= 0:
        return _blocked("broker_current_epoch_fill_price_missing")

    payloads = _payloads_by_fingerprint(ledger_rows)
    indexed = list(enumerate(ledger_rows))
    matching_sends = [
        (index, row)
        for index, row in indexed
        if _clean(row.get("event_type")) == "send_order_called"
        and _clean(row.get("vt_orderid")) == vt_orderid
        and _event_matches_state(row, payloads, state)
    ]
    if len(matching_sends) != 1:
        return _blocked(
            "retry_send_order_match_not_unique:"
            f"vt_orderid={vt_orderid};count={len(matching_sends)}"
        )
    send_index, send = matching_sends[0]
    fingerprint = _clean(send.get("intent_fingerprint"))
    if not fingerprint:
        return _blocked("retry_send_fingerprint_missing")

    all_retry_sends = [
        row
        for _, row in indexed
        if _clean(row.get("event_type")) == "send_order_called"
        and _event_matches_state(row, payloads, state)
    ]
    unique_retry_order_ids = {
        _clean(row.get("vt_orderid")) for row in all_retry_sends if _clean(row.get("vt_orderid"))
    }
    if unique_retry_order_ids != {vt_orderid}:
        return _blocked(
            f"multiple_retry_open_orders_in_cycle:{sorted(unique_retry_order_ids)}"
        )

    reserved_before_send = any(
        index < send_index
        and _clean(row.get("event_type")) == "reserved"
        and _clean(row.get("intent_fingerprint")) == fingerprint
        for index, row in indexed
    )
    if not reserved_before_send:
        return _blocked("retry_durable_reservation_missing_before_send")

    evidence_types = {
        "residual_order_unknown_after_cancel",
        "order_traded_volume_observed_without_trade_detail",
        "fill_reconciliation_pending",
    }
    terminal_evidence = [
        (index, row)
        for index, row in indexed
        if index > send_index
        and _clean(row.get("intent_fingerprint")) == fingerprint
        and _clean(row.get("vt_orderid")) == vt_orderid
        and _clean(row.get("event_type")) in evidence_types
    ]
    if not terminal_evidence:
        return _blocked("retry_unknown_or_unpriced_fill_evidence_missing")
    _, evidence = terminal_evidence[-1]

    existing_priced_fills = [
        row
        for index, row in indexed
        if index > send_index
        and _clean(row.get("intent_fingerprint")) == fingerprint
        and _clean(row.get("vt_orderid")) == vt_orderid
        and _clean(row.get("event_type")) == "filled_or_part_filled"
        and _to_float(row.get("trade_volume_delta"), 0.0) > 0
    ]
    if existing_priced_fills:
        return _not_applicable("priced_retry_fill_already_present")

    reclaim_at = _parse_time(state.get("retry_reclaim_latched_at"))
    send_at = _parse_time(send.get("generated_at"))
    evidence_at = _parse_time(evidence.get("generated_at"))
    if reclaim_at is None or send_at is None or evidence_at is None:
        return _blocked("retry_reclaim_send_or_evidence_time_missing")
    if send_at < reclaim_at and (reclaim_at - send_at).total_seconds() > max_clock_skew_seconds:
        return _blocked("retry_send_precedes_reclaim_latch")
    if evidence_at < send_at and (send_at - evidence_at).total_seconds() > max_clock_skew_seconds:
        return _blocked("retry_unknown_evidence_precedes_send")
    if broker_entry_at < send_at and (send_at - broker_entry_at).total_seconds() > max_clock_skew_seconds:
        return _blocked("broker_fill_precedes_retry_send")
    if broker_entry_at > evidence_at and (
        broker_entry_at - evidence_at
    ).total_seconds() > max_fill_window_seconds:
        return _blocked("broker_fill_outside_unknown_order_window")
    if (
        trade_query_completed_at is None
        or position_query_completed_at is None
        or (
            broker_entry_at - trade_query_completed_at
        ).total_seconds()
        > max_clock_skew_seconds
        or (
            broker_entry_at - position_query_completed_at
        ).total_seconds()
        > max_clock_skew_seconds
    ):
        return _blocked("broker_query_callbacks_precede_reconciled_trade")
    if query_started_at < evidence_at and (
        evidence_at - query_started_at
    ).total_seconds() > max_clock_skew_seconds:
        return _blocked("broker_query_request_precedes_unknown_order_evidence")
    if query_started_at < send_at or (
        snapshot_at - send_at
    ).total_seconds() > max_fill_window_seconds:
        return _blocked("broker_query_generation_outside_retry_causal_window")

    requested_volume = _to_float(send.get("volume"), 0.0)
    residual_volume = _to_float(evidence.get("residual_volume"), requested_volume)
    if requested_volume <= 0 or broker_volume > requested_volume + 1e-9:
        return _blocked(
            "broker_fill_exceeds_retry_request:"
            f"fill={broker_volume};request={requested_volume}"
        )
    if (
        _clean(evidence.get("event_type")) == "residual_order_unknown_after_cancel"
        and residual_volume > 0
        and broker_volume > residual_volume + 1e-9
    ):
        return _blocked(
            "broker_fill_exceeds_unknown_residual:"
            f"fill={broker_volume};residual={residual_volume}"
        )

    key_payload = {
        "target_date": _clean(state.get("target_date")),
        "position_epoch_id": _clean(state.get("position_epoch_id")),
        "position_cycle_id": _clean(state.get("position_cycle_id")),
        "vt_orderid": vt_orderid,
        "trade_identities": sorted(trade_identities),
        "volume": broker_volume,
    }
    reconciliation_key = "late-retry-" + hashlib.sha256(
        json.dumps(key_payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()[:24]
    event = {
        "event_type": "filled_or_part_filled",
        "target_date": _clean(state.get("target_date")),
        # Callback-less recovery must err on the side of protecting risk.  The
        # exact fill instant is not callback-proven, so the durable send call is
        # the conservative earliest cutoff.  Stage904 will therefore consume
        # adverse ticks between send and the later broker query and can latch
        # the second stop immediately.
        "generated_at": send_at.isoformat(),
        "broker_trade_at": broker_entry_at_text,
        "reconciled_at": current.isoformat(),
        "intent_id": _clean(send.get("intent_id")),
        "intent_fingerprint": fingerprint,
        "vt_symbol": _clean(state.get("vt_symbol")),
        "vt_orderid": vt_orderid,
        "direction": _normalize_direction(state.get("direction")),
        "offset": "open",
        "root_position_id": _clean(state.get("root_position_id")),
        "position_epoch_id": _clean(state.get("position_epoch_id")),
        "position_cycle_id": _clean(state.get("position_cycle_id")),
        "position_cycle_no": 1,
        "intent_role": RETRY_OPEN_ACTION_ROLE,
        "adapter": "Stage904BrokerReconciliation",
        "volume": requested_volume,
        "price": broker_price,
        "fill_price_source": "event_trade_weighted_avg",
        "fill_evidence_source": "fresh_broker_trade_vt_orderid_reconciled",
        "trade_volume_delta": broker_volume,
        "trade_fill_key": f"broker-reconciled:{reconciliation_key}",
        "trade_identities": sorted(trade_identities),
        "residual_volume": max(0.0, requested_volume - broker_volume),
        "late_fill_after_cancel": 1,
        "broker_reconciled_late_retry_fill": 1,
        "broker_reconciliation_key": reconciliation_key,
        "broker_snapshot_generated_at": _clean(readonly_summary.get("generated_at")),
        "broker_query_started_at": query_started_at.isoformat(),
        "broker_query_completed_at": snapshot_at.isoformat(),
        "broker_query_generation_uuid": bundle_generation,
        "broker_trading_day": broker_trading_day,
        "unknown_order_evidence_type": _clean(evidence.get("event_type")),
    }
    return {
        "status": "reconciled",
        "reason": "unique_late_retry_fill_proven_by_broker_order_and_trade",
        "manual_intervention_required": 0,
        "ledger_event": event,
    }


__all__ = [
    "LATE_RETRY_FILL_MAX_SECONDS",
    "MAX_CLOCK_SKEW_SECONDS",
    "build_late_retry_fill_reconciliation",
    "validate_readonly_query_bundle",
]
