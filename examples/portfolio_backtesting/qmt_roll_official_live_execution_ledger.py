from __future__ import annotations

import fcntl
import hashlib
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_live_phase_d_config import LIVE_EXECUTION_LEDGER_PATH


LEDGER_SCHEMA_VERSION = 1
INTENT_FINGERPRINT_VERSION_V2 = 2
CLOSE_RETRY_AUDIT_VERSION = 1
CLOSE_RETRY_MAX_SUBMIT_ATTEMPTS = 2
CLOSE_RETRY_ATTEMPT2_LEASE_SECONDS = 300
CLOSE_RETRY_KNOWN_ZERO_REASONS = {
    "req_order_insert_not_accepted",
    "terminal_cancelled_zero_fill",
    "terminal_rejected_zero_fill",
}
V2_IDENTITY_FIELDS = ("root_position_id", "position_cycle_id", "intent_role")
INTENT_METADATA_TEXT_FIELDS = (
    "root_position_id",
    "position_cycle_id",
    "position_epoch_id",
    "parent_position_cycle_id",
    "parent_intent_fingerprint",
    "position_direction",
    "entry_risk_date",
    "open_trade_id",
)
INTENT_METADATA_NUMBER_FIELDS = (
    "position_cycle_no",
    "strategy_entry_price",
    "strategy_initial_stop_price",
    "strategy_stop_price",
    "retry_trigger_price",
    "retry_stop_price",
    "retry_original_fill_price",
    "root_entry_price",
    "root_initial_stop_price",
    "root_entry_volume",
)
OPEN_BLOCKING_EVENTS = {
    "reserved",
    "send_order_called",
    "send_order_returned_empty",
    "cancel_order_called",
    "filled_or_part_filled",
    "rejected_or_inactive",
    "submitted_to_ctp",
    "unknown_order_status_after_send",
    "residual_order_active_after_cancel",
    "residual_order_unknown_after_cancel",
    "adapter_exception_after_reserve",
    "fill_reconciliation_pending",
    "api_slot_reserved",
}
CLOSE_BLOCKING_EVENTS = {
    "send_order_called",
    "send_order_returned_empty",
    "filled_or_part_filled",
    "rejected_or_inactive",
    "unknown_order_status_after_send",
    "residual_order_active_after_cancel",
    "residual_order_unknown_after_cancel",
    "fill_reconciliation_pending",
    "api_slot_reserved",
}
CLOSE_PERMANENT_EVIDENCE_EVENTS = {
    "filled_or_part_filled",
    "close_volume_reconciled_without_trade_detail",
    "order_traded_volume_observed_without_trade_detail",
    "fill_reconciliation_pending",
    "unknown_order_status_after_send",
    "residual_order_active_after_cancel",
    "residual_order_unknown_after_cancel",
}
CLOSE_SUBMIT_ATTEMPT_EVENTS = {
    "send_order_called",
    "send_order_returned_empty",
    "cancel_order_called",
    "rejected_or_inactive",
}
LEDGER_INTEGRITY_ERROR_EVENTS = {
    "ledger_decode_error",
    "ledger_checksum_error",
    "ledger_non_object_error",
}
API_SLOT_TYPES = {"send_order", "cancel_order"}
CLOSE_ATTEMPT_LEASE_SAFE_TERMINAL_EVENTS = {
    "final_pre_send_gate_blocked_after_reserve",
    "api_slot_reservation_blocked",
    "adapter_exception_after_reserve",
}


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _normalize_direction_text(value: Any) -> str:
    text = _clean(value).lower()
    if text in {"long", "多", "direction.long"}:
        return "long"
    if text in {"short", "空", "direction.short"}:
        return "short"
    return text


def _normalize_offset_text(value: Any) -> str:
    text = _clean(value).lower()
    if text in {"open", "开", "offset.open"}:
        return "open"
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
    return text


def _to_float(value: Any, default: float = 0.0) -> float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return float(number)


def _parse_dt(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _strict_positive_int(value: Any) -> int | None:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return None
    integer = int(number)
    if integer <= 0 or float(number) != float(integer):
        return None
    return integer


def _close_retry_known_zero_event(row: dict[str, Any]) -> bool:
    """Accept only a versioned, fully explicit known-zero terminal audit."""

    event_type = _clean(row.get("event_type"))
    reason = _clean(row.get("close_retry_known_zero_reason"))
    attempt_no = _strict_positive_int(row.get("close_submit_attempt_no"))
    if (
        _strict_positive_int(row.get("close_retry_audit_version"))
        != CLOSE_RETRY_AUDIT_VERSION
        or _to_float(row.get("close_retry_known_zero"), 0.0) != 1.0
        or _to_float(row.get("close_retry_unlock_eligible"), 0.0) != 1.0
        or attempt_no is None
        or attempt_no > CLOSE_RETRY_MAX_SUBMIT_ATTEMPTS
        or reason not in CLOSE_RETRY_KNOWN_ZERO_REASONS
    ):
        return False

    requested_volume = _to_float(row.get("volume"), -1.0)
    residual_volume = _to_float(row.get("residual_volume"), -1.0)
    zero_evidence = (
        requested_volume > 0.0
        and residual_volume == requested_volume
        and _to_float(row.get("order_traded_volume"), -1.0) == 0.0
        and _to_float(row.get("trade_event_total_volume"), -1.0) == 0.0
        and _to_float(row.get("trade_event_priced_volume"), -1.0) == 0.0
        and _to_float(row.get("unpriced_volume"), -1.0) == 0.0
    )
    if not zero_evidence:
        return False

    if event_type == "send_order_returned_empty":
        request_ret = pd.to_numeric(
            row.get("req_order_insert_request_ret"), errors="coerce"
        )
        return bool(
            reason == "req_order_insert_not_accepted"
            and _to_float(row.get("main_engine_send_order_returned_empty"), 0.0)
            == 1.0
            and _to_float(row.get("req_order_insert_audit_observed"), 0.0)
            == 1.0
            and _to_float(row.get("req_order_insert_accepted"), -1.0) == 0.0
            and not pd.isna(request_ret)
            and float(request_ret) != 0.0
            and not _clean(row.get("vt_orderid"))
        )

    if event_type != "rejected_or_inactive":
        return False
    status_class = _clean(row.get("close_terminal_status_class"))
    expected_reason = f"terminal_{status_class}_zero_fill"
    return bool(
        status_class in {"cancelled", "rejected"}
        and reason == expected_reason
        and _to_float(row.get("req_order_insert_audit_observed"), 0.0) == 1.0
        and _to_float(row.get("req_order_insert_accepted"), 0.0) == 1.0
        and _to_float(row.get("order_callback_observed"), 0.0) == 1.0
        and _to_float(row.get("trade_callback_count"), -1.0) == 0.0
        and bool(_clean(row.get("vt_orderid")))
    )


def event_age_seconds(row: dict[str, Any], now: datetime | None = None) -> float | None:
    generated = _parse_dt(row.get("generated_at"))
    if generated is None:
        return None
    return max(0.0, ((now or datetime.now()) - generated).total_seconds())


def _stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _fingerprint_digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def _record_checksum(payload: dict[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "record_checksum"}
    return _fingerprint_digest(body)


def _with_record_checksum(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["record_checksum"] = _record_checksum(result)
    return result


def _fsync_parent_directory(path: Path) -> None:
    """Persist a newly-created ledger directory entry after the file data."""

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_fd = os.open(str(path.parent), flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _durable_append_locked(
    handle: Any,
    payload: dict[str, Any],
    *,
    created_path: Path | None = None,
) -> None:
    handle.seek(0, 2)
    handle.write(json.dumps(_with_record_checksum(payload), ensure_ascii=False, sort_keys=True, default=str) + "\n")
    handle.flush()
    os.fsync(handle.fileno())
    if created_path is not None:
        # File fsync alone does not make the new directory entry durable.  Do
        # this only for first creation; ordinary appends retain the existing
        # single-file-fsync cost and ordering.
        _fsync_parent_directory(created_path)


def _metadata_value(row: dict[str, Any], order_request: dict[str, Any], key: str) -> Any:
    value = row.get(key)
    if value is None or _clean(value) == "":
        value = order_request.get(key)
    return value


def normalize_intent_payload(target_date: str, row: dict[str, Any], order_request: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "target_date": target_date,
        "source": _clean(row.get("source")),
        "vt_symbol": _clean(row.get("vt_symbol") or order_request.get("vt_symbol")),
        "symbol": _clean(order_request.get("symbol")),
        "exchange": _clean(order_request.get("exchange")),
        "direction": _normalize_direction_text(order_request.get("direction") or row.get("direction")),
        "offset": _normalize_offset_text(order_request.get("offset") or row.get("offset")),
        "volume": _to_float(order_request.get("volume", row.get("planned_volume")), 0.0),
        "limit_price": _to_float(order_request.get("price", row.get("limit_price")), 0.0),
        "source_reason": _clean(row.get("source_reason")),
        "reference": _clean(order_request.get("reference")),
    }
    intent_role = _clean(row.get("intent_role") or order_request.get("intent_role"))
    if intent_role:
        payload["intent_role"] = intent_role
    for key in INTENT_METADATA_TEXT_FIELDS:
        value = _clean(_metadata_value(row, order_request, key))
        if value:
            payload[key] = value
    for key in INTENT_METADATA_NUMBER_FIELDS:
        raw_value = _metadata_value(row, order_request, key)
        if _clean(raw_value):
            payload[key] = _to_float(raw_value, 0.0)
    root_present = bool(_clean(payload.get("root_position_id")))
    cycle_present = bool(_clean(payload.get("position_cycle_id")))
    if root_present or cycle_present:
        missing = [key for key in V2_IDENTITY_FIELDS if not _clean(payload.get(key))]
        if missing:
            raise ValueError(f"incomplete_v2_intent_identity:missing={','.join(missing)}")
        payload["fingerprint_version"] = INTENT_FINGERPRINT_VERSION_V2
    # ``intent_role`` existed in the pre-V2 retry-open schema, so a role-only
    # payload remains an explicit legacy V1 compatibility case.
    return payload


def _legacy_v1_fingerprint_payload(payload: dict[str, Any]) -> dict[str, Any]:
    fingerprint_payload = {
        "target_date": payload.get("target_date", ""),
        "vt_symbol": payload.get("vt_symbol", ""),
        "symbol": payload.get("symbol", ""),
        "exchange": payload.get("exchange", ""),
        "direction": payload.get("direction", ""),
        "offset": payload.get("offset", ""),
        "volume": payload.get("volume", 0.0),
    }
    if _clean(payload.get("intent_role")):
        fingerprint_payload["intent_role"] = payload["intent_role"]
    return fingerprint_payload


def _v2_fingerprint_payload(payload: dict[str, Any]) -> dict[str, Any]:
    fingerprint_payload = {
        "fingerprint_version": INTENT_FINGERPRINT_VERSION_V2,
        **_legacy_v1_fingerprint_payload(payload),
        "root_position_id": payload["root_position_id"],
        "position_cycle_id": payload["position_cycle_id"],
        "intent_role": payload["intent_role"],
    }
    position_epoch_id = _clean(payload.get("position_epoch_id"))
    if position_epoch_id:
        fingerprint_payload["position_epoch_id"] = position_epoch_id
    return fingerprint_payload


def intent_fingerprint(target_date: str, row: dict[str, Any], order_request: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    payload = normalize_intent_payload(target_date, row, order_request)
    if int(_to_float(payload.get("fingerprint_version"), 0.0)) == INTENT_FINGERPRINT_VERSION_V2:
        fingerprint_payload = _v2_fingerprint_payload(payload)
    else:
        fingerprint_payload = _legacy_v1_fingerprint_payload(payload)
    digest = _fingerprint_digest(fingerprint_payload)
    return digest, payload


def read_execution_ledger(path: Path = LIVE_EXECUTION_LEDGER_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            try:
                return _parse_ledger_lines(handle.read().splitlines())
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except FileNotFoundError:
        return []


def _parse_ledger_lines(lines: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        text = line.strip()
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            rows.append(
                {
                    "event_type": "ledger_decode_error",
                    "ledger_line_number": line_number,
                    "raw_line": text[:500],
                }
            )
            continue
        if not isinstance(parsed, dict):
            rows.append(
                {
                    "event_type": "ledger_non_object_error",
                    "ledger_line_number": line_number,
                    "raw_line": text[:500],
                }
            )
            continue
        checksum = _clean(parsed.get("record_checksum"))
        if checksum and checksum != _record_checksum(parsed):
            rows.append(
                {
                    "event_type": "ledger_checksum_error",
                    "ledger_line_number": line_number,
                    "raw_line": text[:500],
                }
            )
            continue
        rows.append(parsed)
    return rows


def append_execution_ledger_event(event: dict[str, Any], path: Path = LIVE_EXECUTION_LEDGER_PATH) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path_was_missing = not path.exists()
    payload = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **event,
    }
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            durable_payload = _with_record_checksum(payload)
            _durable_append_locked(
                handle,
                payload,
                created_path=path if path_was_missing else None,
            )
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return durable_payload


def append_reconciled_execution_fill_once(
    event: dict[str, Any],
    path: Path = LIVE_EXECUTION_LEDGER_PATH,
) -> dict[str, Any]:
    """Atomically append one broker-proven late fill, or return its prior row.

    Stage904 can discover a callback-less retry fill from a later complete
    broker snapshot while Stage931 is still writing the same ledger.  The
    reconciliation key is therefore checked and appended under the ledger
    flock so reducer restarts and concurrent cycles cannot double count it.
    """

    reconciliation_key = _clean(event.get("broker_reconciliation_key"))
    if not reconciliation_key:
        raise ValueError("broker_reconciliation_key is required")
    if _clean(event.get("event_type")) != "filled_or_part_filled":
        raise ValueError("reconciled execution event must be a fill")
    if _to_float(event.get("trade_volume_delta"), 0.0) <= 0:
        raise ValueError("reconciled execution fill volume must be positive")
    if _to_float(event.get("price"), 0.0) <= 0:
        raise ValueError("reconciled execution fill price must be positive")

    path.parent.mkdir(parents=True, exist_ok=True)
    path_was_missing = not path.exists()
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.seek(0)
            rows = _parse_ledger_lines(handle.read().splitlines())
            integrity_error = _ledger_integrity_blocker(rows)
            if integrity_error:
                return {
                    "appended": False,
                    "blocker": integrity_error,
                    "ledger_event": {},
                }
            existing = [
                row
                for row in rows
                if _clean(row.get("broker_reconciliation_key"))
                == reconciliation_key
            ]
            if len(existing) > 1:
                return {
                    "appended": False,
                    "blocker": (
                        "duplicate_broker_reconciliation_key_in_ledger:"
                        f"{reconciliation_key};count={len(existing)}"
                    ),
                    "ledger_event": {},
                }
            if existing:
                prior = existing[0]
                for key in (
                    "event_type",
                    "target_date",
                    "intent_fingerprint",
                    "vt_orderid",
                    "position_epoch_id",
                    "position_cycle_id",
                    "trade_fill_key",
                    "trade_volume_delta",
                    "price",
                ):
                    if _clean(prior.get(key)) != _clean(event.get(key)):
                        return {
                            "appended": False,
                            "blocker": (
                                "broker_reconciliation_key_payload_mismatch:"
                                f"{reconciliation_key};field={key}"
                            ),
                            "ledger_event": {},
                        }
                return {
                    "appended": False,
                    "blocker": "",
                    "ledger_event": prior,
                    "idempotent_replay": True,
                }

            payload = {
                "schema_version": LEDGER_SCHEMA_VERSION,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                **event,
            }
            durable_payload = _with_record_checksum(payload)
            _durable_append_locked(
                handle,
                payload,
                created_path=path if path_was_missing else None,
            )
            return {
                "appended": True,
                "blocker": "",
                "ledger_event": durable_payload,
                "idempotent_replay": False,
            }
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def reserve_execution_ledger_intent(
    *,
    target_date: str,
    row: dict[str, Any],
    order_request: dict[str, Any],
    close_retry_after_cancel_seconds: int,
    base_event: dict[str, Any],
    max_daily_send_orders: int | None = None,
    max_daily_cancel_orders: int | None = None,
    close_retry_attempt2_lease_seconds: int = CLOSE_RETRY_ATTEMPT2_LEASE_SECONDS,
    path: Path = LIVE_EXECUTION_LEDGER_PATH,
) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path_was_missing = not path.exists()
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.seek(0)
            rows = _parse_ledger_lines(handle.read().splitlines())
            duplicate, fingerprint, fingerprint_payload, latest = duplicate_blocker(
                rows=rows,
                target_date=target_date,
                row=row,
                order_request=order_request,
                close_retry_after_cancel_seconds=close_retry_after_cancel_seconds,
                close_retry_attempt2_lease_seconds=close_retry_attempt2_lease_seconds,
            )
            if duplicate:
                return {
                    "reserved": False,
                    "duplicate_blocker": duplicate,
                    "intent_fingerprint": fingerprint,
                    "intent_payload": fingerprint_payload,
                    "latest_ledger_event": latest or {},
                }
            close_submit_attempt_no: int | None = None
            close_attempt_lease_token = ""
            close_attempt_lease_takeover_from = ""
            close_attempt_lease_seconds = 0
            close_attempt_retry_cooldown_seconds = 0
            if _normalize_offset_text(fingerprint_payload.get("offset")) == "close":
                accepted_fingerprints = {
                    fingerprint,
                    *_legacy_alias_fingerprints(fingerprint_payload),
                }
                prior_attempt_numbers = [
                    attempt_no
                    for item in rows
                    if _clean(item.get("intent_fingerprint"))
                    in accepted_fingerprints
                    and _is_close_submit_attempt_event(item)
                    and (
                        attempt_no := _strict_positive_int(
                            item.get("close_submit_attempt_no")
                        )
                    )
                    is not None
                ]
                close_submit_attempt_no = (
                    max(prior_attempt_numbers, default=0) + 1
                )
                close_attempt_lease_token = uuid.uuid4().hex
                close_attempt_retry_cooldown_seconds = max(
                    1, int(close_retry_after_cancel_seconds)
                )
                close_attempt_lease_seconds = max(
                    1,
                    int(
                        close_retry_attempt2_lease_seconds
                        if close_submit_attempt_no == 2
                        else close_retry_after_cancel_seconds
                    ),
                )
                if (
                    _clean((latest or {}).get("event_type")) == "reserved"
                    and _strict_positive_int(
                        (latest or {}).get("close_submit_attempt_no")
                    )
                    == close_submit_attempt_no
                ):
                    close_attempt_lease_takeover_from = _clean(
                        (latest or {}).get("close_attempt_lease_token")
                    )
            payload = {
                **base_event,
                "schema_version": LEDGER_SCHEMA_VERSION,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "event_type": "reserved",
                "target_date": target_date,
                "intent_fingerprint": fingerprint,
                "intent_payload": fingerprint_payload,
            }
            if close_submit_attempt_no is not None:
                payload["close_submit_attempt_no"] = close_submit_attempt_no
            if close_attempt_lease_token:
                payload["close_attempt_lease_token"] = close_attempt_lease_token
                payload["close_attempt_lease_seconds"] = (
                    close_attempt_lease_seconds
                )
                payload["close_attempt_retry_cooldown_seconds"] = (
                    close_attempt_retry_cooldown_seconds
                )
                if close_attempt_lease_takeover_from:
                    payload["close_attempt_lease_takeover_from"] = (
                        close_attempt_lease_takeover_from
                    )
            # Deduplication lease only.  API quota is reserved atomically at
            # the actual send/cancel side-effect boundary, so a transient
            # pre-send blocker cannot exhaust the day's order budget.
            durable_payload = _with_record_checksum(payload)
            _durable_append_locked(
                handle,
                payload,
                created_path=path if path_was_missing else None,
            )
            return {
                "reserved": True,
                "duplicate_blocker": "",
                "intent_fingerprint": fingerprint,
                "intent_payload": fingerprint_payload,
                "latest_ledger_event": durable_payload,
                "close_submit_attempt_no": close_submit_attempt_no,
                "close_attempt_lease_token": close_attempt_lease_token,
                "close_attempt_lease_takeover_from": close_attempt_lease_takeover_from,
                "close_attempt_lease_seconds": close_attempt_lease_seconds,
                "close_attempt_retry_cooldown_seconds": (
                    close_attempt_retry_cooldown_seconds
                ),
                "api_slot_usage": {
                    "send_order": _api_slot_usage(rows, target_date, "send_order"),
                    "cancel_order": _api_slot_usage(rows, target_date, "cancel_order"),
                },
            }
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def reserve_execution_api_slot(
    *,
    target_date: str,
    slot_type: str,
    daily_limit: int,
    base_event: dict[str, Any],
    path: Path = LIVE_EXECUTION_LEDGER_PATH,
) -> dict[str, Any]:
    """Atomically reserve one external order-API call before the side effect."""

    if slot_type not in API_SLOT_TYPES:
        raise ValueError(f"unsupported_api_slot_type:{slot_type}")
    if daily_limit <= 0:
        raise ValueError("daily_limit must be positive")
    path.parent.mkdir(parents=True, exist_ok=True)
    path_was_missing = not path.exists()
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.seek(0)
            rows = _parse_ledger_lines(handle.read().splitlines())
            integrity_error = _ledger_integrity_blocker(rows)
            if integrity_error:
                return {"reserved": False, "blocker": integrity_error, "api_slot_usage": 0}
            usage = _api_slot_usage(rows, target_date, slot_type)
            if usage >= daily_limit:
                return {
                    "reserved": False,
                    "blocker": f"ledger_daily_{slot_type}_limit_reached",
                    "api_slot_usage": usage,
                }
            payload = {
                "schema_version": LEDGER_SCHEMA_VERSION,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "event_type": "api_slot_reserved",
                "target_date": target_date,
                "api_slot_type": slot_type,
                "api_slot_reserved": 1,
                "api_slot_limit": int(daily_limit),
                **base_event,
            }
            durable_payload = _with_record_checksum(payload)
            _durable_append_locked(
                handle,
                payload,
                created_path=path if path_was_missing else None,
            )
            return {
                "reserved": True,
                "blocker": "",
                "api_slot_usage": usage + 1,
                "ledger_event": durable_payload,
            }
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def reserve_execution_api_slots(
    *,
    target_date: str,
    slot_type: str,
    daily_limit: int,
    base_events: list[dict[str, Any]],
    path: Path = LIVE_EXECUTION_LEDGER_PATH,
) -> dict[str, Any]:
    """Atomically reserve an all-or-none batch of external API calls.

    A single strategy intent can expand into multiple broker requests (for
    example SHFE/INE close-today plus close-yesterday).  Reserving the batch
    under one ledger lock prevents the first child from consuming quota while
    a later child discovers that the daily limit is already exhausted.
    """

    if slot_type not in API_SLOT_TYPES:
        raise ValueError(f"unsupported_api_slot_type:{slot_type}")
    if daily_limit <= 0:
        raise ValueError("daily_limit must be positive")
    if not base_events:
        raise ValueError("base_events must not be empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    path_was_missing = not path.exists()
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.seek(0)
            rows = _parse_ledger_lines(handle.read().splitlines())
            integrity_error = _ledger_integrity_blocker(rows)
            if integrity_error:
                return {
                    "reserved": False,
                    "blocker": integrity_error,
                    "api_slot_usage": 0,
                    "reserved_count": 0,
                }
            lease_cas_blocker = (
                _close_attempt_api_slot_cas_blocker(rows, base_events)
                if slot_type == "send_order"
                else ""
            )
            if lease_cas_blocker:
                return {
                    "reserved": False,
                    "blocker": lease_cas_blocker,
                    "api_slot_usage": _api_slot_usage(
                        rows, target_date, slot_type
                    ),
                    "requested_count": len(base_events),
                    "reserved_count": 0,
                }
            usage = _api_slot_usage(rows, target_date, slot_type)
            requested_count = len(base_events)
            if usage + requested_count > daily_limit:
                return {
                    "reserved": False,
                    "blocker": f"ledger_daily_{slot_type}_batch_limit_reached",
                    "api_slot_usage": usage,
                    "requested_count": requested_count,
                    "reserved_count": 0,
                }

            batch_id = hashlib.sha256(
                _stable_json(
                    {
                        "target_date": target_date,
                        "slot_type": slot_type,
                        "usage_before": usage,
                        "base_events": base_events,
                    }
                ).encode("utf-8")
            ).hexdigest()[:24]
            # One durable record is the quota transaction.  The complete child
            # list remains embedded for per-child audit, while a crash cannot
            # leave only a prefix of the requested quota reserved.
            payload = {
                **base_events[0],
                "schema_version": LEDGER_SCHEMA_VERSION,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "event_type": "api_slot_reserved",
                "target_date": target_date,
                "api_slot_type": slot_type,
                "api_slot_reserved": 1,
                "api_slot_reserved_count": requested_count,
                "api_slot_limit": int(daily_limit),
                "api_slot_batch_id": batch_id,
                "api_slot_batch_count": requested_count,
                "api_slot_batch_children": base_events,
            }
            durable_payload = _with_record_checksum(payload)
            _durable_append_locked(
                handle,
                payload,
                created_path=path if path_was_missing else None,
            )
            return {
                "reserved": True,
                "blocker": "",
                "api_slot_usage": usage + requested_count,
                "requested_count": requested_count,
                "reserved_count": requested_count,
                "api_slot_batch_id": batch_id,
                "ledger_event": durable_payload,
            }
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def latest_event_for_fingerprint(rows: list[dict[str, Any]], fingerprint: str) -> dict[str, Any] | None:
    matched = [row for row in rows if _clean(row.get("intent_fingerprint")) == fingerprint]
    return matched[-1] if matched else None


def events_for_fingerprint(rows: list[dict[str, Any]], fingerprint: str) -> list[dict[str, Any]]:
    return [row for row in rows if _clean(row.get("intent_fingerprint")) == fingerprint]


def _ledger_integrity_blocker(rows: list[dict[str, Any]]) -> str:
    for row in rows:
        event_type = _clean(row.get("event_type"))
        if event_type in LEDGER_INTEGRITY_ERROR_EVENTS:
            line_number = _clean(row.get("ledger_line_number")) or "unknown"
            return f"ledger_integrity_error:{event_type}:line={line_number}"
    return ""


def _api_slot_usage(rows: list[dict[str, Any]], target_date: str, slot_type: str) -> int:
    """Count reserved slots plus legacy/unpaired API calls without double counting."""

    if slot_type not in API_SLOT_TYPES:
        raise ValueError(f"unsupported_api_slot_type:{slot_type}")
    dated = [row for row in rows if _clean(row.get("target_date")) == target_date]
    reservation_events: list[dict[str, Any]] = []
    for row in dated:
        slot_types = row.get("api_slot_types")
        slot_type_list = slot_types if isinstance(slot_types, list) else []
        if (
            slot_type in slot_type_list or _clean(row.get("api_slot_type")) == slot_type
        ) and _to_float(row.get("api_slot_reserved"), 0.0) == 1.0:
            reservation_events.append(row)
    reservations_by_fingerprint: dict[str, int] = {}
    reservation_count = 0
    for row in reservation_events:
        count = max(1, int(_to_float(row.get("api_slot_reserved_count"), 1.0)))
        reservation_count += count
        children = row.get("api_slot_batch_children")
        child_rows = children if isinstance(children, list) else []
        if child_rows:
            for child in child_rows:
                if not isinstance(child, dict):
                    continue
                fingerprint = _clean(child.get("intent_fingerprint"))
                if fingerprint:
                    reservations_by_fingerprint[fingerprint] = (
                        reservations_by_fingerprint.get(fingerprint, 0) + 1
                    )
        else:
            fingerprint = _clean(row.get("intent_fingerprint"))
            if fingerprint:
                reservations_by_fingerprint[fingerprint] = (
                    reservations_by_fingerprint.get(fingerprint, 0) + count
                )

    external_event_type = f"{slot_type}_called"
    unmatched_external_calls = 0
    paired_remaining = dict(reservations_by_fingerprint)
    for row in dated:
        if _clean(row.get("event_type")) != external_event_type:
            continue
        fingerprint = _clean(row.get("intent_fingerprint"))
        if fingerprint and paired_remaining.get(fingerprint, 0) > 0:
            paired_remaining[fingerprint] -= 1
        else:
            unmatched_external_calls += 1
    return reservation_count + unmatched_external_calls


def ledger_order_api_counts(rows: list[dict[str, Any]], target_date: str) -> dict[str, int]:
    dated = [row for row in rows if _clean(row.get("target_date")) == target_date]
    return {
        "send_order_called": sum(1 for row in dated if row.get("event_type") == "send_order_called"),
        "cancel_order_called": sum(1 for row in dated if row.get("event_type") == "cancel_order_called"),
        "reserved": sum(1 for row in dated if row.get("event_type") == "reserved"),
        "send_order_slot_usage": _api_slot_usage(rows, target_date, "send_order"),
        "cancel_order_slot_usage": _api_slot_usage(rows, target_date, "cancel_order"),
    }


def _event_intent_payload(row: dict[str, Any], linked_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = row.get("intent_payload")
    if isinstance(payload, dict):
        return payload
    return linked_payload or {}


def _event_value(row: dict[str, Any], key: str, linked_payload: dict[str, Any] | None = None) -> Any:
    value = row.get(key)
    if _clean(value):
        return value
    return _event_intent_payload(row, linked_payload).get(key)


def _event_vt_symbol(row: dict[str, Any], linked_payload: dict[str, Any] | None = None) -> str:
    payload = _event_intent_payload(row, linked_payload)
    return _clean(row.get("vt_symbol") or payload.get("vt_symbol"))


def _event_direction(row: dict[str, Any], linked_payload: dict[str, Any] | None = None) -> str:
    payload = _event_intent_payload(row, linked_payload)
    return _normalize_direction_text(row.get("direction") or payload.get("direction"))


def _event_offset(row: dict[str, Any], linked_payload: dict[str, Any] | None = None) -> str:
    payload = _event_intent_payload(row, linked_payload)
    return _normalize_offset_text(row.get("offset") or payload.get("offset"))


def _intent_payloads_by_fingerprint(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    for row in rows:
        fingerprint = _clean(row.get("intent_fingerprint"))
        payload = row.get("intent_payload")
        if fingerprint and isinstance(payload, dict):
            payloads[fingerprint] = payload
    return payloads


def _linked_intent_payload(
    row: dict[str, Any],
    payloads_by_fingerprint: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return payloads_by_fingerprint.get(_clean(row.get("intent_fingerprint")), {})


def _event_trade_identity(row: dict[str, Any]) -> str:
    vt_tradeid = _clean(row.get("vt_tradeid") or row.get("trade_fill_key"))
    if vt_tradeid:
        return f"vt:{vt_tradeid}"
    tradeid = _clean(row.get("tradeid") or row.get("trade_id"))
    if not tradeid:
        return ""
    gateway = _clean(row.get("gateway_name") or row.get("adapter"))
    return f"trade:{gateway}:{tradeid}"


def open_fill_rows(
    rows: list[dict[str, Any]],
    target_date: str,
    vt_symbol: str,
    direction: str,
    *,
    root_position_id: str | None = None,
    position_epoch_id: str | None = None,
    position_cycle_id: str | None = None,
    intent_role: str | None = None,
) -> list[dict[str, Any]]:
    payloads_by_fingerprint = _intent_payloads_by_fingerprint(rows)
    matched: list[dict[str, Any]] = []
    seen_trade_ids: set[str] = set()
    for row in rows:
        linked_payload = _linked_intent_payload(row, payloads_by_fingerprint)
        if _clean(row.get("target_date")) != target_date:
            continue
        if _clean(row.get("event_type")) != "filled_or_part_filled":
            continue
        if _event_vt_symbol(row, linked_payload) != vt_symbol:
            continue
        if _event_offset(row, linked_payload) != "open":
            continue
        if _event_direction(row, linked_payload) != direction.lower():
            continue
        if root_position_id is not None and _clean(_event_value(row, "root_position_id", linked_payload)) != root_position_id:
            continue
        if position_epoch_id is not None and _clean(_event_value(row, "position_epoch_id", linked_payload)) != position_epoch_id:
            continue
        if position_cycle_id is not None and _clean(_event_value(row, "position_cycle_id", linked_payload)) != position_cycle_id:
            continue
        if intent_role is not None and _clean(_event_value(row, "intent_role", linked_payload)) != intent_role:
            continue
        trade_identity = _event_trade_identity(row)
        if trade_identity and trade_identity in seen_trade_ids:
            continue
        if trade_identity:
            seen_trade_ids.add(trade_identity)
        item = dict(row)
        for key in (
            "fingerprint_version",
            "root_position_id",
            "position_epoch_id",
            "position_cycle_id",
            "position_cycle_no",
            "intent_role",
            "strategy_entry_price",
            "strategy_stop_price",
            "retry_trigger_price",
        ):
            if not _clean(item.get(key)) and _clean(linked_payload.get(key)):
                item[key] = linked_payload[key]
        matched.append(item)
    return matched


def weighted_open_fill(
    rows: list[dict[str, Any]],
    target_date: str,
    vt_symbol: str,
    direction: str,
    *,
    root_position_id: str | None = None,
    position_epoch_id: str | None = None,
    position_cycle_id: str | None = None,
    intent_role: str | None = None,
) -> dict[str, Any] | None:
    fills = open_fill_rows(
        rows,
        target_date,
        vt_symbol,
        direction,
        root_position_id=root_position_id,
        position_epoch_id=position_epoch_id,
        position_cycle_id=position_cycle_id,
        intent_role=intent_role,
    )
    if not fills:
        return None
    total_volume = 0.0
    notional = 0.0
    for row in fills:
        if _clean(row.get("fill_price_source")) != "event_trade_weighted_avg":
            continue
        volume = _to_float(row.get("trade_volume_delta", row.get("volume")), 0.0)
        price = _to_float(row.get("price"), 0.0)
        if volume <= 0 or price <= 0:
            continue
        total_volume += volume
        notional += volume * price
    if total_volume <= 0:
        return None
    latest = fills[-1]
    return {
        **latest,
        "vt_symbol": vt_symbol,
        "direction": direction.lower(),
        "offset": "open",
        "price": notional / total_volume,
        "volume": total_volume,
        "trade_count": len(fills),
        "date": target_date,
    }


def latest_position_cycle_open_fill(
    rows: list[dict[str, Any]],
    target_date: str,
    vt_symbol: str,
    direction: str,
    *,
    root_position_id: str | None = None,
    position_epoch_id: str | None = None,
    intent_role: str | None = None,
) -> dict[str, Any] | None:
    fills = open_fill_rows(
        rows,
        target_date,
        vt_symbol,
        direction,
        root_position_id=root_position_id,
        position_epoch_id=position_epoch_id,
        intent_role=intent_role,
    )
    selected_epoch_id = position_epoch_id
    if fills and position_epoch_id is None:
        candidate_epoch_ids = {
            _clean(row.get("position_epoch_id"))
            for row in fills
            if _clean(row.get("position_epoch_id"))
        }
        payloads_by_fingerprint = _intent_payloads_by_fingerprint(rows)
        epoch_first_seen_index: dict[str, int] = {}
        for index, row in enumerate(rows):
            linked_payload = _linked_intent_payload(row, payloads_by_fingerprint)
            epoch_id = _clean(_event_value(row, "position_epoch_id", linked_payload))
            if not epoch_id or epoch_id not in candidate_epoch_ids:
                continue
            if _clean(row.get("target_date")) != target_date:
                continue
            if _event_vt_symbol(row, linked_payload) != vt_symbol:
                continue
            if _event_direction(row, linked_payload) != direction.lower():
                continue
            if _event_offset(row, linked_payload) != "open":
                continue
            if (
                root_position_id is not None
                and _clean(_event_value(row, "root_position_id", linked_payload))
                != root_position_id
            ):
                continue
            epoch_first_seen_index.setdefault(epoch_id, index)
        latest_epoch_id = (
            max(candidate_epoch_ids, key=lambda item: epoch_first_seen_index.get(item, -1))
            if candidate_epoch_ids
            else ""
        )
        if latest_epoch_id:
            selected_epoch_id = latest_epoch_id
            # Cycle numbers restart inside each independent same-day position
            # epoch.  Rank by the epoch's first durable observation, not its
            # last fill append: an old epoch trade callback may arrive after a
            # newer epoch has already opened.
            fills = [
                row for row in fills if _clean(row.get("position_epoch_id")) == latest_epoch_id
            ]
    cycle_candidates: list[tuple[float, int, str]] = []
    for index, row in enumerate(fills):
        cycle_id = _clean(row.get("position_cycle_id"))
        cycle_no = pd.to_numeric(row.get("position_cycle_no"), errors="coerce")
        if cycle_id and not pd.isna(cycle_no):
            cycle_candidates.append((float(cycle_no), index, cycle_id))
    if cycle_candidates:
        latest_cycle_id = max(cycle_candidates)[2]
    else:
        latest_cycle_id = next(
            (_clean(row.get("position_cycle_id")) for row in reversed(fills) if _clean(row.get("position_cycle_id"))),
            "",
        )
    if not latest_cycle_id:
        return None
    return weighted_open_fill(
        rows,
        target_date,
        vt_symbol,
        direction,
        root_position_id=root_position_id,
        position_epoch_id=selected_epoch_id,
        position_cycle_id=latest_cycle_id,
        intent_role=intent_role,
    )


def _legacy_alias_fingerprints(payload: dict[str, Any]) -> set[str]:
    """Return only aliases that were unambiguous in the pre-V2 live schema."""

    if int(_to_float(payload.get("fingerprint_version"), 0.0)) != INTENT_FINGERPRINT_VERSION_V2:
        return set()
    role = _clean(payload.get("intent_role"))
    legacy_payload = _legacy_v1_fingerprint_payload(payload)
    if role in {"c9_initial_open", "c9_initial_stop_close"}:
        # Initial open/stop rows had no role before Stage179.
        legacy_payload.pop("intent_role", None)
    elif role == "c9_retry_open_once":
        # Retry open already carried this role in the legacy schema.
        pass
    else:
        # A roleless retry-stop alias would collide with the initial stop and
        # can therefore never be accepted automatically.
        return set()
    return {_fingerprint_digest(legacy_payload)}


def _is_close_submit_attempt_event(row: dict[str, Any]) -> bool:
    event_type = _clean(row.get("event_type"))
    if event_type in CLOSE_SUBMIT_ATTEMPT_EVENTS:
        return True
    if event_type != "api_slot_reserved":
        return False
    slot_types = row.get("api_slot_types")
    slot_type_list = slot_types if isinstance(slot_types, list) else []
    return bool(
        _clean(row.get("api_slot_type")) == "send_order"
        or "send_order" in slot_type_list
    )


def _close_attempt_lease_state(
    matched_events: list[dict[str, Any]],
    *,
    attempt_no: int,
    lease_seconds: int,
    retry_cooldown_seconds: int,
) -> dict[str, Any]:
    """Return the state of the newest lease for one close submit attempt.

    A reservation is not a broker submit attempt.  It can therefore be
    safely replaced only after an explicit pre-send terminal or after the
    long crash-recovery lease expires.  Broker/API evidence after the lease
    is never a safe terminal.
    """

    reservations = [
        (index, item)
        for index, item in enumerate(matched_events)
        if _clean(item.get("event_type")) == "reserved"
        and _strict_positive_int(item.get("close_submit_attempt_no"))
        == attempt_no
    ]
    if not reservations:
        return {"status": "none", "event": {}}

    reservation_index, reservation = reservations[-1]
    token = _clean(reservation.get("close_attempt_lease_token"))
    if not token:
        return {"status": "invalid_missing_token", "event": reservation}
    recorded_lease_seconds = _strict_positive_int(
        reservation.get("close_attempt_lease_seconds")
    )
    effective_lease_seconds = recorded_lease_seconds or max(1, int(lease_seconds))
    recorded_retry_cooldown_seconds = _strict_positive_int(
        reservation.get("close_attempt_retry_cooldown_seconds")
    )
    effective_retry_cooldown_seconds = (
        recorded_retry_cooldown_seconds
        or max(1, int(retry_cooldown_seconds))
    )

    after_reservation = matched_events[reservation_index + 1 :]
    for item in after_reservation:
        item_attempt_no = _strict_positive_int(
            item.get("close_submit_attempt_no")
        )
        item_token = _clean(item.get("close_attempt_lease_token"))
        belongs_to_lease = bool(
            item_attempt_no == _strict_positive_int(
                reservation.get("close_submit_attempt_no")
            )
            and (not item_token or item_token == token)
        )
        if not belongs_to_lease:
            continue
        event_type = _clean(item.get("event_type"))
        if (
            _is_close_submit_attempt_event(item)
            or event_type in CLOSE_PERMANENT_EVIDENCE_EVENTS
            or event_type in {"submitted_to_ctp", "adapter_exception_after_send"}
            or (
                event_type == "adapter_exception_after_reserve"
                and _to_float(item.get("send_slot_reserved"), 0.0) == 1.0
            )
        ):
            return {"status": "side_effect", "event": item, "token": token}

    safe_terminals: list[dict[str, Any]] = []
    for item in after_reservation:
        if (
            _strict_positive_int(item.get("close_submit_attempt_no"))
            != _strict_positive_int(reservation.get("close_submit_attempt_no"))
            or _clean(item.get("close_attempt_lease_token")) != token
        ):
            continue
        event_type = _clean(item.get("event_type"))
        if event_type not in CLOSE_ATTEMPT_LEASE_SAFE_TERMINAL_EVENTS:
            continue
        if event_type == "adapter_exception_after_reserve" and (
            _to_float(item.get("pre_send_exception_confirmed"), 0.0) != 1.0
            or _to_float(item.get("send_slot_reserved"), 0.0) == 1.0
        ):
            continue
        safe_terminals.append(item)
    if safe_terminals:
        return {
            "status": "safe_terminal",
            "event": safe_terminals[-1],
            "token": token,
            "lease_seconds": effective_lease_seconds,
            "retry_cooldown_seconds": effective_retry_cooldown_seconds,
        }

    age = event_age_seconds(reservation)
    if age is None:
        return {"status": "invalid_timestamp", "event": reservation, "token": token}
    if age >= effective_lease_seconds:
        return {
            "status": "expired",
            "event": reservation,
            "token": token,
            "age_seconds": age,
            "lease_seconds": effective_lease_seconds,
            "retry_cooldown_seconds": effective_retry_cooldown_seconds,
        }
    return {
        "status": "active",
        "event": reservation,
        "token": token,
        "age_seconds": age,
        "lease_seconds": effective_lease_seconds,
        "retry_cooldown_seconds": effective_retry_cooldown_seconds,
    }


def _close_attempt_api_slot_cas_blocker(
    rows: list[dict[str, Any]],
    base_events: list[dict[str, Any]],
) -> str:
    """Validate a protective-close lease in the API-slot ledger lock."""

    attempt_numbers = {
        _strict_positive_int(item.get("close_submit_attempt_no"))
        for item in base_events
    }
    tokens = {_clean(item.get("close_attempt_lease_token")) for item in base_events}
    child_offsets: set[str] = set()
    for item in base_events:
        raw_offset = item.get("child_order_offset") or item.get("offset")
        if _clean(raw_offset):
            child_offsets.add(_normalize_offset_text(raw_offset))
    close_batch = bool(
        any(attempt_no is not None for attempt_no in attempt_numbers)
        or any(tokens)
        or "close" in child_offsets
    )
    if not close_batch:
        return ""
    if child_offsets and child_offsets != {"close"}:
        return "close_attempt_api_slot_batch_offset_missing_or_mismatch"
    if attempt_numbers not in ({1}, {2}):
        return "close_attempt_api_slot_batch_attempt_missing_or_mismatch"

    if len(tokens) != 1 or "" in tokens:
        return "close_attempt_api_slot_batch_lease_token_missing_or_mismatch"
    fingerprints = {_clean(item.get("intent_fingerprint")) for item in base_events}
    if len(fingerprints) != 1 or "" in fingerprints:
        return "close_attempt_api_slot_batch_fingerprint_missing_or_mismatch"

    attempt_no = next(iter(attempt_numbers))
    assert attempt_no is not None
    token = next(iter(tokens))
    fingerprint = next(iter(fingerprints))
    matched_events = [
        item
        for item in rows
        if _clean(item.get("intent_fingerprint")) == fingerprint
    ]
    latest_close_reservation = next(
        (
            item
            for item in reversed(matched_events)
            if _clean(item.get("event_type")) == "reserved"
            and _strict_positive_int(item.get("close_submit_attempt_no"))
            is not None
        ),
        None,
    )
    if latest_close_reservation is None:
        return "close_attempt_api_slot_lease_none"
    if (
        _strict_positive_int(
            latest_close_reservation.get("close_submit_attempt_no")
        )
        != attempt_no
        or _clean(latest_close_reservation.get("close_attempt_lease_token"))
        != token
    ):
        return "close_attempt_api_slot_lease_cas_stale_token"

    lease_state = _close_attempt_lease_state(
        matched_events,
        attempt_no=attempt_no,
        lease_seconds=CLOSE_RETRY_ATTEMPT2_LEASE_SECONDS,
        retry_cooldown_seconds=CLOSE_RETRY_ATTEMPT2_LEASE_SECONDS,
    )
    state = _clean(lease_state.get("status"))
    if state in {"none", "invalid_missing_token", "invalid_timestamp"}:
        return f"close_attempt_api_slot_lease_{state}"
    if _clean(lease_state.get("token")) != token:
        return "close_attempt_api_slot_lease_cas_stale_token"
    if state == "safe_terminal":
        return "close_attempt_api_slot_lease_already_safe_terminal"
    if state == "side_effect":
        return "close_attempt_api_slot_lease_side_effect_already_recorded"
    # Both active and expired remain valid while this token is still the
    # newest reservation.  Whichever process obtains this lock first either
    # appends the API slot or appends a takeover reservation; the loser then
    # observes a stale token.
    return ""


def _close_duplicate_blocker(
    matched_events: list[dict[str, Any]],
    *,
    close_retry_after_cancel_seconds: int,
    close_retry_attempt2_lease_seconds: int = CLOSE_RETRY_ATTEMPT2_LEASE_SECONDS,
) -> tuple[str, dict[str, Any]]:
    """Evaluate the fail-closed protective-close retry state machine."""

    latest = matched_events[-1]
    for item in matched_events:
        event_type = _clean(item.get("event_type"))
        if event_type in CLOSE_PERMANENT_EVIDENCE_EVENTS:
            return f"ledger_duplicate_close_intent:{event_type}", item

    for item in matched_events:
        if _clean(item.get("event_type")) != "reserved":
            continue
        attempt_no = _strict_positive_int(item.get("close_submit_attempt_no"))
        if attempt_no not in {1, 2}:
            return "ledger_close_attempt_lease_attempt_missing_or_invalid", item
        if not _clean(item.get("close_attempt_lease_token")):
            return "ledger_close_attempt_lease_token_missing", item
        if _strict_positive_int(item.get("close_attempt_lease_seconds")) is None:
            return "ledger_close_attempt_lease_seconds_missing_or_invalid", item

    for index, item in enumerate(matched_events):
        if _clean(item.get("event_type")) != "adapter_exception_after_reserve":
            continue
        attempt_no = _strict_positive_int(item.get("close_submit_attempt_no"))
        prior_side_effect_boundary = any(
            _strict_positive_int(prior.get("close_submit_attempt_no"))
            == attempt_no
            and (
                _clean(prior.get("event_type")) == "send_order_called"
                or (
                    _clean(prior.get("event_type")) == "api_slot_reserved"
                    and _clean(prior.get("api_slot_type")) == "send_order"
                )
            )
            for prior in matched_events[:index]
        )
        if (
            attempt_no is None
            or _to_float(item.get("send_slot_reserved"), 0.0) == 1.0
            or prior_side_effect_boundary
        ):
            return (
                "ledger_duplicate_close_intent:send_order_side_effect_unknown_after_exception",
                item,
            )
    submit_events = [
        item for item in matched_events if _is_close_submit_attempt_event(item)
    ]
    known_zero_events = [
        item for item in matched_events if _close_retry_known_zero_event(item)
    ]

    # Any old/unversioned or partially audited submit attempt remains
    # permanently fail-closed.  A later generic batch-audit row must not hide
    # an earlier ambiguous broker side effect.
    for item in submit_events:
        if _strict_positive_int(item.get("close_submit_attempt_no")) is None:
            return (
                "ledger_duplicate_close_intent:unversioned_or_unknown_submit_attempt",
                item,
            )

    attempt_numbers = [
        _strict_positive_int(item.get("close_submit_attempt_no"))
        for item in submit_events
    ]
    if any(
        attempt_no is not None
        and attempt_no >= CLOSE_RETRY_MAX_SUBMIT_ATTEMPTS
        for attempt_no in attempt_numbers
    ):
        return "ledger_duplicate_close_intent:known_zero_retry_limit_reached", latest

    if submit_events and not known_zero_events:
        terminal_candidates = [
            item
            for item in submit_events
            if _clean(item.get("event_type"))
            in {"send_order_returned_empty", "rejected_or_inactive"}
        ]
        evidence = terminal_candidates[-1] if terminal_candidates else submit_events[-1]
        return (
            "ledger_duplicate_close_intent:submit_attempt_not_explicit_known_zero",
            evidence,
        )

    if known_zero_events:
        known_zero = known_zero_events[-1]
        known_zero_index = max(
            index
            for index, item in enumerate(matched_events)
            if item is known_zero
        )
        attempt_no = _strict_positive_int(known_zero.get("close_submit_attempt_no"))
        if attempt_no != 1:
            return "ledger_duplicate_close_intent:known_zero_retry_limit_reached", known_zero
        matching_send_seen = any(
            _clean(item.get("event_type")) == "send_order_called"
            and _strict_positive_int(item.get("close_submit_attempt_no"))
            == attempt_no
            for item in matched_events[:known_zero_index]
        )
        if not matching_send_seen:
            return (
                "ledger_duplicate_close_intent:known_zero_audit_missing_send_call",
                known_zero,
            )
        unresolved_submit_after_terminal = next(
            (
                item
                for item in matched_events[known_zero_index + 1 :]
                if _is_close_submit_attempt_event(item)
            ),
            None,
        )
        if unresolved_submit_after_terminal is not None:
            return (
                "ledger_duplicate_close_intent:submit_attempt_after_known_zero_unresolved",
                unresolved_submit_after_terminal,
            )

        # Attempt 2 uses a unique pre-send lease.  An unfinished lease blocks
        # concurrent reservation for a long crash-recovery interval; a safe
        # terminal releases only the exact same token after the ordinary
        # cooldown.  An expired lease is takeover-eligible, but the old token
        # still must lose the API-slot CAS before any broker call.
        lease_state = _close_attempt_lease_state(
            matched_events[known_zero_index + 1 :],
            attempt_no=2,
            lease_seconds=close_retry_attempt2_lease_seconds,
            retry_cooldown_seconds=close_retry_after_cancel_seconds,
        )
        lease_status = _clean(lease_state.get("status"))
        lease_event = dict(lease_state.get("event") or {})
        if lease_status == "active":
            return (
                "ledger_close_attempt2_lease_active:"
                f"{lease_state.get('age_seconds')}",
                lease_event,
            )
        if lease_status == "invalid_missing_token":
            return "ledger_close_attempt2_lease_token_missing", lease_event
        if lease_status == "invalid_timestamp":
            return "ledger_close_attempt2_lease_timestamp_missing", lease_event
        if lease_status == "side_effect":
            return "ledger_close_attempt2_lease_side_effect_recorded", lease_event
        if lease_status == "expired":
            return "", lease_event

        cooldown_event = lease_event if lease_status == "safe_terminal" else known_zero
        cooldown_seconds = (
            int(lease_state.get("retry_cooldown_seconds"))
            if lease_status == "safe_terminal"
            and _strict_positive_int(
                lease_state.get("retry_cooldown_seconds")
            )
            is not None
            else close_retry_after_cancel_seconds
        )
        age = event_age_seconds(cooldown_event)
        if age is None:
            return (
                "ledger_duplicate_close_intent:known_zero_retry_timestamp_missing",
                cooldown_event,
            )
        if age < cooldown_seconds:
            return f"ledger_close_known_zero_retry_throttled:{age}", cooldown_event
        return "", cooldown_event

    lease_state = _close_attempt_lease_state(
        matched_events,
        attempt_no=1,
        lease_seconds=close_retry_after_cancel_seconds,
        retry_cooldown_seconds=close_retry_after_cancel_seconds,
    )
    lease_status = _clean(lease_state.get("status"))
    lease_event = dict(lease_state.get("event") or {})
    if lease_status == "active":
        return (
            "ledger_close_attempt1_lease_active:"
            f"{lease_state.get('age_seconds')}",
            lease_event,
        )
    if lease_status == "expired":
        return "", lease_event
    if lease_status == "safe_terminal":
        age = event_age_seconds(lease_event)
        if age is None:
            return "ledger_close_attempt1_safe_terminal_timestamp_missing", lease_event
        retry_cooldown_seconds = int(
            lease_state.get("retry_cooldown_seconds")
            or close_retry_after_cancel_seconds
        )
        if age < retry_cooldown_seconds:
            return f"ledger_close_attempt1_safe_terminal_throttled:{age}", lease_event
        return "", lease_event
    if lease_status == "invalid_missing_token":
        return "ledger_close_attempt_lease_token_missing", lease_event
    if lease_status == "invalid_timestamp":
        return "ledger_close_attempt1_lease_timestamp_missing", lease_event
    if lease_status == "side_effect":
        return "ledger_close_attempt1_lease_side_effect_recorded", lease_event
    return "ledger_close_attempt1_lease_missing", latest


def duplicate_blocker(
    *,
    rows: list[dict[str, Any]],
    target_date: str,
    row: dict[str, Any],
    order_request: dict[str, Any],
    close_retry_after_cancel_seconds: int,
    close_retry_attempt2_lease_seconds: int = CLOSE_RETRY_ATTEMPT2_LEASE_SECONDS,
) -> tuple[str, str, dict[str, Any], dict[str, Any] | None]:
    fingerprint, payload = intent_fingerprint(target_date, row, order_request)
    integrity_blocker = _ledger_integrity_blocker(rows)
    if integrity_blocker:
        integrity_row = next(
            (row for row in rows if _clean(row.get("event_type")) in LEDGER_INTEGRITY_ERROR_EVENTS),
            None,
        )
        return integrity_blocker, fingerprint, payload, integrity_row
    accepted_fingerprints = {fingerprint, *_legacy_alias_fingerprints(payload)}
    matched_events = [
        item for item in rows if _clean(item.get("intent_fingerprint")) in accepted_fingerprints
    ]
    latest = matched_events[-1] if matched_events else None
    if latest is None:
        return "", fingerprint, payload, None
    event_type = _clean(latest.get("event_type"))
    offset = _clean(payload.get("offset")).lower()
    if offset == "close":
        blocker, evidence = _close_duplicate_blocker(
            matched_events,
            close_retry_after_cancel_seconds=close_retry_after_cancel_seconds,
            close_retry_attempt2_lease_seconds=close_retry_attempt2_lease_seconds,
        )
        return blocker, fingerprint, payload, evidence
    if event_type == "final_pre_send_gate_blocked_after_reserve":
        age = event_age_seconds(latest)
        throttle_seconds = max(30, close_retry_after_cancel_seconds)
        if age is not None and age < throttle_seconds:
            return f"ledger_open_retry_throttled_after_final_pre_send_gate:{age}", fingerprint, payload, latest
        return "", fingerprint, payload, latest
    if event_type in OPEN_BLOCKING_EVENTS:
        return f"ledger_duplicate_open_intent:{event_type}", fingerprint, payload, latest
    return "", fingerprint, payload, latest
