from __future__ import annotations

import fcntl
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
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
PRE_API_SLOT_SAFE_TERMINAL_VERSION = 1
PRE_API_SLOT_SAFE_TERMINAL_EVENT = "pre_api_slot_no_side_effect_safe_terminal"
POST_API_SLOT_SAFE_TERMINAL_EVENT = "post_api_slot_no_native_safe_terminal"
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
    "logical_close_root_id",
    "prior_close_terminal_checksum",
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
    "close_execution_attempt_no",
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
    PRE_API_SLOT_SAFE_TERMINAL_EVENT,
    "final_pre_send_gate_blocked_after_reserve",
    "api_slot_reservation_blocked",
    "adapter_exception_after_reserve",
    "spool_crash_recovery_pre_send_safe_terminal",
    POST_API_SLOT_SAFE_TERMINAL_EVENT,
}
EXECUTION_LEDGER_READER_CAPABILITIES = frozenset(
    {
        "ledger_schema_1",
        "intent_fingerprint_v1",
        "intent_fingerprint_v2",
        "close_uuid_lease_v1",
        "batch_api_slot_cas_v1",
        "spool_crash_recovery_v1",
        "pre_api_slot_safe_terminal_v1",
    }
)
RECOVERY_SIDE_EFFECT_EVENTS = {
    "api_slot_reserved",
    "send_order_called",
    "send_order_returned",
    "send_order_returned_empty",
    "submitted_to_ctp",
    "adapter_exception_after_send",
    "unknown_order_status_after_send",
    "residual_order_active_after_cancel",
    "residual_order_unknown_after_cancel",
    "cancel_order_called",
    "fill_reconciliation_pending",
    "order_traded_volume_observed_without_trade_detail",
    "filled_or_part_filled",
    "native_order_identity_persisted_before_insert",
    "native_order_identity_return_mismatch",
}
RECOVERY_RECONCILED_EVENTS = {
    "close_volume_reconciled_without_trade_detail",
}

_WARM_RESERVATION_IDENTITY_FIELDS = (
    "target_date",
    "intent_id",
    "intent_payload_sha256",
    "intent_kind",
    "intent_fingerprint",
    "spool_lease_owner",
    "spool_lease_token",
)


@dataclass(frozen=True)
class LedgerRecoveryDecision:
    disposition: str
    blocker: str
    intent_fingerprint: str
    evidence_event_type: str
    safe_terminal_appended: bool


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
    for key in (
        "logical_close_root_id",
        "prior_close_terminal_checksum",
        "close_execution_attempt_no",
    ):
        value = payload.get(key)
        if _clean(value):
            fingerprint_payload[key] = value
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


def append_broker_callback_event_once(
    event: dict[str, Any],
    path: Path = LIVE_EXECUTION_LEDGER_PATH,
) -> dict[str, Any]:
    """Durably append one normalized broker callback exactly once.

    The callback key is derived by the adapter from broker identities and
    cumulative state, never from callback arrival order.  Duplicate delivery
    after reconnect is therefore an idempotent replay; a key collision with a
    different payload fails closed.
    """

    callback_key = _clean(event.get("broker_callback_key"))
    if not callback_key:
        raise ValueError("broker_callback_key is required")
    if not _clean(event.get("event_type")):
        raise ValueError("broker_callback_event_type is required")
    if not _clean(event.get("target_date")):
        raise ValueError("broker_callback_target_date is required")

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
                    "idempotent_replay": False,
                    "blocker": integrity_error,
                    "ledger_event": {},
                }
            existing = [
                row
                for row in rows
                if _clean(row.get("broker_callback_key")) == callback_key
            ]
            if len(existing) > 1:
                return {
                    "appended": False,
                    "idempotent_replay": False,
                    "blocker": (
                        "duplicate_broker_callback_key_in_ledger:"
                        f"{callback_key};count={len(existing)}"
                    ),
                    "ledger_event": {},
                }
            if existing:
                prior = existing[0]
                comparable_prior = {
                    key: value
                    for key, value in prior.items()
                    if key not in {"schema_version", "generated_at", "record_checksum"}
                }
                comparable_event = {
                    key: value
                    for key, value in event.items()
                    if key not in {"schema_version", "generated_at", "record_checksum"}
                }
                if json.dumps(
                    comparable_prior,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    default=str,
                ) != json.dumps(
                    comparable_event,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    default=str,
                ):
                    return {
                        "appended": False,
                        "idempotent_replay": False,
                        "blocker": (
                            "broker_callback_key_payload_mismatch:"
                            f"{callback_key}"
                        ),
                        "ledger_event": {},
                    }
                return {
                    "appended": False,
                    "idempotent_replay": True,
                    "blocker": "",
                    "ledger_event": prior,
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
                "idempotent_replay": False,
                "blocker": "",
                "ledger_event": durable_payload,
            }
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def advance_cancel_duty_state(
    *,
    target_date: str,
    duty_key: str,
    expected_states: tuple[str, ...],
    next_state: str,
    owner_id: str,
    lease_seconds: int,
    event: dict[str, Any],
    allow_expired_takeover: bool = False,
    path: Path = LIVE_EXECUTION_LEDGER_PATH,
) -> dict[str, Any]:
    """CAS one physical cancel duty through its crash-recovery states."""

    allowed = {"reserved", "api_called", "api_returned", "query_reconciled"}
    if next_state not in allowed:
        raise ValueError(f"unsupported_cancel_duty_state:{next_state}")
    if not duty_key or not target_date or not owner_id:
        raise ValueError("cancel_duty_identity_missing")
    now_ns = time.time_ns()
    path.parent.mkdir(parents=True, exist_ok=True)
    path_was_missing = not path.exists()
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.seek(0)
            rows = _parse_ledger_lines(handle.read().splitlines())
            integrity_error = _ledger_integrity_blocker(rows)
            if integrity_error:
                return {"advanced": False, "blocker": integrity_error, "ledger_event": {}}
            prior = next(
                (
                    row
                    for row in reversed(rows)
                    if _clean(row.get("event_type")) == "cancel_duty_state_transition"
                    and _clean(row.get("cancel_duty_key")) == duty_key
                ),
                None,
            )
            current = _clean((prior or {}).get("cancel_duty_state"))
            if current == "query_reconciled":
                return {"advanced": False, "idempotent_replay": True, "blocker": "", "ledger_event": prior}
            if current not in set(expected_states):
                return {
                    "advanced": False,
                    "blocker": f"cancel_duty_state_cas_mismatch:current={current or 'none'}",
                    "ledger_event": prior or {},
                }
            prior_owner = _clean((prior or {}).get("cancel_duty_owner_id"))
            expired = _strict_positive_int(
                (prior or {}).get("cancel_duty_lease_expires_epoch_ns")
            )
            if (
                prior_owner
                and prior_owner != owner_id
                and not (
                    allow_expired_takeover
                    and expired is not None
                    and expired <= now_ns
                )
            ):
                return {
                    "advanced": False,
                    "blocker": "cancel_duty_owner_lease_active",
                    "ledger_event": prior or {},
                }
            prior_generation = int(
                _to_float((prior or {}).get("cancel_duty_generation"), 0.0)
            )
            next_generation = int(
                _to_float(event.get("cancel_duty_generation"), 0.0)
            )
            generation_valid = bool(
                (not current and next_generation == 1)
                or (
                    current in {"api_called", "api_returned"}
                    and next_state == "reserved"
                    and next_generation == prior_generation + 1
                    and next_generation <= 2
                )
                or (
                    current
                    and not (
                        current in {"api_called", "api_returned"}
                        and next_state == "reserved"
                    )
                    and next_generation == prior_generation
                )
            )
            if not generation_valid:
                return {
                    "advanced": False,
                    "blocker": (
                        "cancel_duty_generation_not_monotonic:"
                        f"prior={prior_generation};next={next_generation};"
                        f"transition={current or 'none'}->{next_state}"
                    ),
                    "ledger_event": prior or {},
                }
            payload = {
                "schema_version": LEDGER_SCHEMA_VERSION,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                **event,
                "event_type": "cancel_duty_state_transition",
                "target_date": target_date,
                "cancel_duty_key": duty_key,
                "cancel_duty_previous_state": current,
                "cancel_duty_state": next_state,
                "cancel_duty_owner_id": owner_id,
                "cancel_duty_lease_expires_epoch_ns": (
                    now_ns + max(1, int(lease_seconds)) * 1_000_000_000
                ),
                "cancel_duty_takeover": int(bool(prior_owner and prior_owner != owner_id)),
            }
            durable_payload = _with_record_checksum(payload)
            _durable_append_locked(
                handle,
                payload,
                created_path=path if path_was_missing else None,
            )
            return {"advanced": True, "blocker": "", "ledger_event": durable_payload}
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


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


def _warm_reservation_identity_blocker(
    rows: list[dict[str, Any]],
    identity: dict[str, Any],
) -> tuple[str, dict[str, Any] | None, int]:
    """Resolve one exact warm reservation under the caller's ledger lock."""

    reservation_checksum = _clean(identity.get("reservation_record_checksum"))
    if len(reservation_checksum) != 64:
        return "warm_reservation_record_checksum_missing_or_invalid", None, -1
    for field_name in _WARM_RESERVATION_IDENTITY_FIELDS:
        if not _clean(identity.get(field_name)):
            return f"warm_reservation_identity_missing:{field_name}", None, -1
    indexes = [
        index
        for index, event in enumerate(rows)
        if _clean(event.get("record_checksum")) == reservation_checksum
    ]
    if len(indexes) != 1:
        return (
            "warm_reservation_record_checksum_not_unique_or_missing",
            None,
            -1,
        )
    reservation_index = indexes[0]
    reservation = rows[reservation_index]
    if _clean(reservation.get("event_type")) != "reserved":
        return "warm_reservation_checksum_not_reserved_event", None, -1
    for field_name in _WARM_RESERVATION_IDENTITY_FIELDS:
        if _clean(reservation.get(field_name)) != _clean(identity.get(field_name)):
            return f"warm_reservation_identity_mismatch:{field_name}", None, -1

    fingerprint = _clean(identity.get("intent_fingerprint"))
    latest_reservation = next(
        (
            event
            for event in reversed(rows)
            if _clean(event.get("event_type")) == "reserved"
            and _clean(event.get("intent_fingerprint")) == fingerprint
        ),
        None,
    )
    if latest_reservation is not reservation:
        return "warm_reservation_cas_stale_reservation", None, -1
    return "", reservation, reservation_index


def _event_matches_warm_identity(
    event: dict[str, Any],
    identity: dict[str, Any],
) -> bool:
    return all(
        _clean(event.get(field_name)) == _clean(identity.get(field_name))
        for field_name in _WARM_RESERVATION_IDENTITY_FIELDS
    )


def _warm_reservation_side_effect_after(
    rows: list[dict[str, Any]],
    *,
    reservation_index: int,
    identity: dict[str, Any],
) -> dict[str, Any] | None:
    for event in rows[reservation_index + 1 :]:
        if not _event_matches_warm_identity(event, identity):
            continue
        event_type = _clean(event.get("event_type"))
        if event_type in RECOVERY_SIDE_EFFECT_EVENTS or (
            event_type == "adapter_exception_after_reserve"
            and _to_float(event.get("send_slot_reserved"), 0.0) == 1.0
        ):
            return event
    return None


def _valid_pre_api_slot_safe_terminal(
    event: dict[str, Any],
    reservation: dict[str, Any],
) -> bool:
    if _clean(event.get("event_type")) != PRE_API_SLOT_SAFE_TERMINAL_EVENT:
        return False
    if (
        _strict_positive_int(event.get("safe_terminal_version"))
        != PRE_API_SLOT_SAFE_TERMINAL_VERSION
        or _clean(event.get("reservation_record_checksum"))
        != _clean(reservation.get("record_checksum"))
    ):
        return False
    if not _event_matches_warm_identity(event, reservation):
        return False
    zero_fields = (
        "api_slot_reserved",
        "send_slot_reserved",
        "send_order_call_count",
        "cancel_order_call_count",
    )
    if any(_to_float(event.get(field_name), -1.0) != 0.0 for field_name in zero_fields):
        return False
    if _clean(event.get("api_slot_batch_id")):
        return False
    broker_order_ids = event.get("broker_order_ids")
    return broker_order_ids == []


def append_pre_api_slot_no_side_effect_terminal(
    *,
    target_date: str,
    intent_id: str,
    intent_payload_sha256: str,
    intent_kind: str,
    intent_fingerprint: str,
    reservation_record_checksum: str,
    spool_lease_owner: str,
    spool_lease_token: str,
    blockers: list[str],
    blocked_phase: str,
    base_event: dict[str, Any] | None = None,
    path: Path = LIVE_EXECUTION_LEDGER_PATH,
) -> dict[str, Any]:
    """Atomically prove and close one pre-API reservation with no side effect.

    The append and the API-slot CAS use the same ledger flock.  Therefore a
    successful return proves that no API slot or broker call won the race for
    this exact reservation.
    """

    identity = {
        "target_date": target_date,
        "intent_id": intent_id,
        "intent_payload_sha256": intent_payload_sha256,
        "intent_kind": intent_kind,
        "intent_fingerprint": intent_fingerprint,
        "reservation_record_checksum": reservation_record_checksum,
        "spool_lease_owner": spool_lease_owner,
        "spool_lease_token": spool_lease_token,
    }
    normalized_blockers = [str(item) for item in blockers if str(item)]
    if not normalized_blockers:
        return {
            "appended": False,
            "idempotent_replay": False,
            "blocker": "pre_api_slot_safe_terminal_blockers_missing",
            "ledger_event": {},
        }
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
                    "idempotent_replay": False,
                    "blocker": integrity_error,
                    "ledger_event": {},
                }
            blocker, reservation, reservation_index = (
                _warm_reservation_identity_blocker(rows, identity)
            )
            if blocker or reservation is None:
                return {
                    "appended": False,
                    "idempotent_replay": False,
                    "blocker": blocker,
                    "ledger_event": {},
                }
            side_effect = _warm_reservation_side_effect_after(
                rows,
                reservation_index=reservation_index,
                identity=identity,
            )
            if side_effect is not None:
                return {
                    "appended": False,
                    "idempotent_replay": False,
                    "blocker": (
                        "pre_api_slot_safe_terminal_side_effect_already_recorded:"
                        f"{_clean(side_effect.get('event_type'))}"
                    ),
                    "ledger_event": {},
                }
            prior_terminals = [
                event
                for event in rows[reservation_index + 1 :]
                if _clean(event.get("event_type"))
                == PRE_API_SLOT_SAFE_TERMINAL_EVENT
                and _clean(event.get("reservation_record_checksum"))
                == reservation_record_checksum
            ]
            if prior_terminals:
                prior = prior_terminals[-1]
                if not _valid_pre_api_slot_safe_terminal(prior, reservation):
                    return {
                        "appended": False,
                        "idempotent_replay": False,
                        "blocker": "pre_api_slot_safe_terminal_prior_invalid",
                        "ledger_event": {},
                    }
                return {
                    "appended": False,
                    "idempotent_replay": True,
                    "blocker": "",
                    "ledger_event": prior,
                }

            payload = {
                **(base_event or {}),
                **identity,
                "schema_version": LEDGER_SCHEMA_VERSION,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "event_type": PRE_API_SLOT_SAFE_TERMINAL_EVENT,
                "safe_terminal_version": PRE_API_SLOT_SAFE_TERMINAL_VERSION,
                "safe_terminal_capability": "pre_api_slot_safe_terminal_v1",
                "blocked_phase": _clean(blocked_phase) or "pre_api_slot",
                "blockers": normalized_blockers,
                "final_blockers": normalized_blockers,
                "pre_send_blocked_confirmed": 1,
                "api_slot_reserved": 0,
                "send_slot_reserved": 0,
                "api_slot_batch_id": "",
                "send_order_call_count": 0,
                "cancel_order_call_count": 0,
                "broker_order_ids": [],
            }
            durable_payload = _with_record_checksum(payload)
            _durable_append_locked(
                handle,
                payload,
                created_path=path if path_was_missing else None,
            )
            return {
                "appended": True,
                "idempotent_replay": False,
                "blocker": "",
                "ledger_event": durable_payload,
            }
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def append_post_api_slot_no_native_safe_terminal(
    *,
    identity: dict[str, Any],
    api_slot_batch_id: str,
    blockers: list[str],
    blocked_phase: str,
    path: Path = LIVE_EXECUTION_LEDGER_PATH,
) -> dict[str, Any]:
    """Close a consumed send slot iff no native/send call won the ledger CAS."""

    if not api_slot_batch_id or not blockers:
        return {"appended": False, "blocker": "post_slot_safe_terminal_input_missing"}
    path.parent.mkdir(parents=True, exist_ok=True)
    path_was_missing = not path.exists()
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.seek(0)
            rows = _parse_ledger_lines(handle.read().splitlines())
            integrity_error = _ledger_integrity_blocker(rows)
            if integrity_error:
                return {"appended": False, "blocker": integrity_error}
            blocker, reservation, reservation_index = _warm_reservation_identity_blocker(
                rows, identity
            )
            if blocker or reservation is None:
                return {"appended": False, "blocker": blocker}
            prior = next(
                (
                    row
                    for row in rows[reservation_index + 1 :]
                    if _clean(row.get("event_type")) == POST_API_SLOT_SAFE_TERMINAL_EVENT
                    and _clean(row.get("api_slot_batch_id")) == api_slot_batch_id
                    and _event_matches_warm_identity(row, identity)
                ),
                None,
            )
            if prior is not None:
                if valid_post_api_slot_no_native_safe_terminal(rows, prior):
                    return {
                        "appended": False,
                        "idempotent_replay": True,
                        "blocker": "",
                        "ledger_event": prior,
                    }
                return {
                    "appended": False,
                    "idempotent_replay": False,
                    "blocker": (
                        "post_slot_safe_terminal_prior_invalid_or_superseded"
                    ),
                    "ledger_event": prior,
                }
            batch_slot_rows = [
                row
                for row in rows[reservation_index + 1 :]
                if _clean(row.get("event_type")) == "api_slot_reserved"
                and _clean(row.get("api_slot_type")) == "send_order"
                and _clean(row.get("api_slot_batch_id")) == api_slot_batch_id
            ]
            reservation_attempt = _strict_positive_int(
                reservation.get("close_submit_attempt_no")
            )
            reservation_token = _clean(
                reservation.get("close_attempt_lease_token")
            )
            close_lease_matches = bool(
                (reservation_attempt is None and not reservation_token)
                or (
                    reservation_attempt is not None
                    and reservation_token
                    and _strict_positive_int(
                        identity.get("close_submit_attempt_no")
                    )
                    == reservation_attempt
                    and _clean(identity.get("close_attempt_lease_token"))
                    == reservation_token
                    and all(
                        _strict_positive_int(
                            row.get("close_submit_attempt_no")
                        )
                        == reservation_attempt
                        and _clean(row.get("close_attempt_lease_token"))
                        == reservation_token
                        for row in batch_slot_rows
                    )
                )
            )
            if not batch_slot_rows:
                return {"appended": False, "blocker": "post_slot_safe_terminal_slot_missing"}
            if not all(
                _event_matches_warm_identity(row, identity)
                for row in batch_slot_rows
            ) or not close_lease_matches:
                return {
                    "appended": False,
                    "blocker": "post_slot_safe_terminal_batch_or_lease_mismatch",
                }
            forbidden = next(
                (
                    row
                    for row in rows[reservation_index + 1 :]
                    if _event_matches_warm_identity(row, identity)
                    and (
                        _clean(row.get("event_type"))
                        in {
                        "native_order_identity_persisted_before_insert",
                        "send_order_returned",
                        "submitted_to_ctp",
                        }
                        or (
                            _clean(row.get("event_type")) == "send_order_called"
                            and not (
                                _clean(row.get("native_identity_protocol_version"))
                                == "stage179_preinsert_v1"
                                and _to_float(row.get("native_api_called"), 0.0)
                                == 0.0
                            )
                        )
                    )
                ),
                None,
            )
            if forbidden is not None:
                return {
                    "appended": False,
                    "blocker": f"post_slot_safe_terminal_native_winner:{_clean(forbidden.get('event_type'))}",
                }
            payload = {
                **identity,
                "schema_version": LEDGER_SCHEMA_VERSION,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "event_type": POST_API_SLOT_SAFE_TERMINAL_EVENT,
                "safe_terminal_version": 1,
                "blocked_phase": blocked_phase,
                "blockers": [str(item) for item in blockers if str(item)],
                "api_slot_reserved": 1,
                "send_slot_reserved": 1,
                "api_slot_batch_id": api_slot_batch_id,
                "send_order_call_count": 0,
                "cancel_order_call_count": 0,
                "broker_order_ids": [],
                "native_api_called": 0,
            }
            durable = _with_record_checksum(payload)
            _durable_append_locked(
                handle,
                payload,
                created_path=path if path_was_missing else None,
            )
            return {"appended": True, "blocker": "", "ledger_event": durable}
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def valid_post_api_slot_no_native_safe_terminal(
    rows: list[dict[str, Any]], event: dict[str, Any]
) -> bool:
    if (
        _clean(event.get("event_type")) != POST_API_SLOT_SAFE_TERMINAL_EVENT
        or _strict_positive_int(event.get("safe_terminal_version")) != 1
        or _to_float(event.get("api_slot_reserved"), 0.0) != 1.0
        or _to_float(event.get("send_slot_reserved"), 0.0) != 1.0
        or _to_float(event.get("native_api_called"), -1.0) != 0.0
        or _to_float(event.get("send_order_call_count"), -1.0) != 0.0
        or _to_float(event.get("cancel_order_call_count"), -1.0) != 0.0
        or event.get("broker_order_ids") != []
        or not _clean(event.get("blocked_phase"))
        or not isinstance(event.get("blockers"), list)
        or not event.get("blockers")
    ):
        return False
    batch_id = _clean(event.get("api_slot_batch_id"))
    identity = {
        key: event.get(key, "")
        for key in (*_WARM_RESERVATION_IDENTITY_FIELDS, "reservation_record_checksum")
    }
    reservation_checksum = _clean(identity.get("reservation_record_checksum"))
    reservation_indexes = [
        index
        for index, row in enumerate(rows)
        if _clean(row.get("record_checksum")) == reservation_checksum
    ]
    if len(reservation_indexes) != 1 or not batch_id:
        return False
    reservation_index = reservation_indexes[0]
    reservation = rows[reservation_index]
    if (
        _clean(reservation.get("event_type")) != "reserved"
        or any(
            _clean(reservation.get(field_name))
            != _clean(identity.get(field_name))
            for field_name in _WARM_RESERVATION_IDENTITY_FIELDS
        )
    ):
        return False
    event_index = next(
        (
            index
            for index, row in enumerate(rows)
            if _clean(row.get("record_checksum"))
            == _clean(event.get("record_checksum"))
        ),
        -1,
    )
    if event_index <= reservation_index:
        return False
    batch_slots = [
        row
        for row in rows[reservation_index:event_index]
        if _clean(row.get("event_type")) == "api_slot_reserved"
        and _clean(row.get("api_slot_type")) == "send_order"
        and _clean(row.get("api_slot_batch_id")) == batch_id
    ]
    if not batch_slots or not all(
        _event_matches_warm_identity(row, identity) for row in batch_slots
    ):
        return False
    reservation_attempt = _strict_positive_int(
        reservation.get("close_submit_attempt_no")
    )
    reservation_token = _clean(reservation.get("close_attempt_lease_token"))
    if reservation_attempt is None and not reservation_token:
        pass
    elif not (
        reservation_attempt is not None
        and reservation_token
        and _strict_positive_int(event.get("close_submit_attempt_no"))
        == reservation_attempt
        and _clean(event.get("close_attempt_lease_token"))
        == reservation_token
        and all(
            _strict_positive_int(row.get("close_submit_attempt_no"))
            == reservation_attempt
            and _clean(row.get("close_attempt_lease_token"))
            == reservation_token
            for row in batch_slots
        )
    ):
        return False
    return not any(
        _event_matches_warm_identity(row, identity)
        and (
            _clean(row.get("event_type"))
            in {
            "native_order_identity_persisted_before_insert",
            "send_order_returned",
            "submitted_to_ctp",
            }
            or (
                _clean(row.get("event_type")) == "send_order_called"
                and not (
                    _clean(row.get("native_identity_protocol_version"))
                    == "stage179_preinsert_v1"
                    and _to_float(row.get("native_api_called"), 0.0) == 0.0
                )
            )
        )
        for row in rows[reservation_index + 1 :]
    )


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
                logical_close_root_id = _clean(
                    fingerprint_payload.get("logical_close_root_id")
                )
                effective_close_submit_event_ids = {
                    id(item)
                    for item in _effective_close_submit_attempt_events(rows)
                }
                prior_attempt_numbers = [
                    attempt_no
                    for item in rows
                    if (
                        (
                            logical_close_root_id
                            and _clean(
                                _metadata_value(
                                    item,
                                    (
                                        item.get("intent_payload")
                                        if isinstance(item.get("intent_payload"), dict)
                                        else {}
                                    ),
                                    "logical_close_root_id",
                                )
                            )
                            == logical_close_root_id
                        )
                        or (
                            not logical_close_root_id
                            and _clean(item.get("intent_fingerprint"))
                            in accepted_fingerprints
                        )
                    )
                    and (
                        id(item) in effective_close_submit_event_ids
                        or (
                            logical_close_root_id
                            and _clean(item.get("event_type")) == "reserved"
                            and _clean(item.get("intent_fingerprint"))
                            not in accepted_fingerprints
                        )
                    )
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
                requested_execution_attempt_no = _strict_positive_int(
                    fingerprint_payload.get("close_execution_attempt_no")
                )
                prior_same_fingerprint = any(
                    _clean(item.get("intent_fingerprint"))
                    in accepted_fingerprints
                    and id(item) in effective_close_submit_event_ids
                    for item in rows
                )
                if (
                    requested_execution_attempt_no is not None
                    and not prior_same_fingerprint
                    and requested_execution_attempt_no
                    != close_submit_attempt_no
                ):
                    return {
                        "reserved": False,
                        "duplicate_blocker": (
                            "logical_close_execution_attempt_mismatch:"
                            f"requested={requested_execution_attempt_no};"
                            f"next={close_submit_attempt_no}"
                        ),
                        "intent_fingerprint": fingerprint,
                        "intent_payload": fingerprint_payload,
                        "latest_ledger_event": latest or {},
                    }
                if (
                    close_submit_attempt_no == 2
                    and not prior_same_fingerprint
                ):
                    prior_terminal_checksum = _clean(
                        fingerprint_payload.get("prior_close_terminal_checksum")
                    )
                    try:
                        parsed_checksums = json.loads(prior_terminal_checksum)
                    except json.JSONDecodeError:
                        parsed_checksums = []
                    checksums = (
                        [str(item) for item in parsed_checksums]
                        if isinstance(parsed_checksums, list)
                        and parsed_checksums
                        and all(isinstance(item, str) and item for item in parsed_checksums)
                        else []
                    )
                    terminals = [
                        item
                        for checksum in checksums
                        for item in rows
                        if _clean(item.get("record_checksum")) == checksum
                    ]
                    requested_epoch = _clean(
                        fingerprint_payload.get("position_epoch_id")
                    )
                    expected_children = max(
                        [
                            int(_to_float(item.get("child_order_count"), 1.0))
                            for item in terminals
                        ],
                        default=0,
                    )
                    terminal_children = {
                        _clean(item.get("child_order_id"))
                        or _clean(item.get("vt_orderid"))
                        for item in terminals
                    }
                    def valid_terminal(item: dict[str, Any]) -> bool:
                        item_payload = (
                            item.get("intent_payload")
                            if isinstance(item.get("intent_payload"), dict)
                            else {}
                        )
                        item_type = _clean(item.get("event_type"))
                        authority = bool(
                            item_type == "broker_order_query_terminal_observed"
                            and _to_float(
                                item.get("fill_price_reconciliation_pending"), 1.0
                            )
                            == 0.0
                        ) or bool(
                            item_type == "rejected_or_inactive"
                            and _strict_positive_int(
                                item.get("close_retry_audit_version")
                            )
                            is not None
                            and _to_float(item.get("close_retry_known_zero"), 0.0)
                            == 1.0
                        )
                        return bool(
                            authority
                            and _clean(
                                _metadata_value(
                                    item, item_payload, "logical_close_root_id"
                                )
                            )
                            == logical_close_root_id
                            and _clean(
                                _metadata_value(
                                    item, item_payload, "position_epoch_id"
                                )
                            )
                            == requested_epoch
                            and _strict_positive_int(item.get("close_submit_attempt_no"))
                            == 1
                        )
                    if not (
                        prior_terminal_checksum
                        and len(terminals) == len(checksums)
                        and expected_children == len(terminal_children) == len(terminals)
                        and all(valid_terminal(item) for item in terminals)
                    ):
                        return {
                            "reserved": False,
                            "duplicate_blocker": (
                                "logical_close_prior_terminal_proof_invalid"
                            ),
                            "intent_fingerprint": fingerprint,
                            "intent_payload": fingerprint_payload,
                            "latest_ledger_event": latest or {},
                        }
                if close_submit_attempt_no > CLOSE_RETRY_MAX_SUBMIT_ATTEMPTS:
                    return {
                        "reserved": False,
                        "duplicate_blocker": "logical_close_execution_attempt_cap_reached",
                        "intent_fingerprint": fingerprint,
                        "intent_payload": fingerprint_payload,
                        "latest_ledger_event": latest or {},
                    }
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
            warm_cas_blocker = (
                _warm_api_slot_cas_blocker(rows, base_events)
                if slot_type == "send_order"
                else ""
            )
            if warm_cas_blocker:
                return {
                    "reserved": False,
                    "blocker": warm_cas_blocker,
                    "api_slot_usage": _api_slot_usage(
                        rows, target_date, slot_type
                    ),
                    "requested_count": len(base_events),
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


def _warm_api_slot_cas_blocker(
    rows: list[dict[str, Any]],
    base_events: list[dict[str, Any]],
) -> str:
    """Bind a Stage931 warm send batch to its exact durable reservation."""

    checksums = {
        _clean(event.get("reservation_record_checksum")) for event in base_events
    }
    # Legacy/cold callers do not claim the versioned warm CAS capability.
    if checksums == {""}:
        return ""
    if len(checksums) != 1 or "" in checksums:
        return "warm_api_slot_reservation_checksum_missing_or_mismatch"
    for field_name in _WARM_RESERVATION_IDENTITY_FIELDS:
        values = {_clean(event.get(field_name)) for event in base_events}
        if len(values) != 1 or "" in values:
            return f"warm_api_slot_identity_missing_or_mismatch:{field_name}"
    identity = dict(base_events[0])
    blocker, reservation, reservation_index = _warm_reservation_identity_blocker(
        rows,
        identity,
    )
    if blocker or reservation is None:
        return f"warm_api_slot_{blocker}"
    side_effect = _warm_reservation_side_effect_after(
        rows,
        reservation_index=reservation_index,
        identity=identity,
    )
    if side_effect is not None:
        return (
            "warm_api_slot_side_effect_already_recorded:"
            f"{_clean(side_effect.get('event_type'))}"
        )
    terminal = next(
        (
            event
            for event in reversed(rows[reservation_index + 1 :])
            if _clean(event.get("event_type"))
            == PRE_API_SLOT_SAFE_TERMINAL_EVENT
            and _clean(event.get("reservation_record_checksum"))
            == _clean(identity.get("reservation_record_checksum"))
        ),
        None,
    )
    if terminal is not None:
        if not _valid_pre_api_slot_safe_terminal(terminal, reservation):
            return "warm_api_slot_safe_terminal_invalid"
        return "warm_api_slot_reservation_already_safe_terminal"
    return ""


def _recovery_event_matches_lease(
    event: dict[str, Any],
    *,
    spool_lease_owner: str,
    spool_lease_token: str,
) -> bool:
    if (
        _clean(event.get("spool_lease_owner")) == spool_lease_owner
        and _clean(event.get("spool_lease_token")) == spool_lease_token
    ):
        return True
    children = event.get("api_slot_batch_children")
    if not isinstance(children, list):
        return False
    return any(
        isinstance(child, dict)
        and _clean(child.get("spool_lease_owner")) == spool_lease_owner
        and _clean(child.get("spool_lease_token")) == spool_lease_token
        for child in children
    )


def _recovery_fill_volume(events: list[dict[str, Any]]) -> float:
    identified_total = 0.0
    anonymous_max = 0.0
    seen_trade_ids: set[str] = set()
    for event in events:
        if _clean(event.get("event_type")) != "filled_or_part_filled":
            continue
        trade_identity = _event_trade_identity(event)
        if trade_identity:
            if trade_identity in seen_trade_ids:
                continue
            seen_trade_ids.add(trade_identity)
        volume = max(
            0.0,
            _to_float(
                event.get("trade_volume_delta", event.get("volume")),
                0.0,
            ),
        )
        if trade_identity:
            identified_total += volume
        else:
            # Anonymous legacy callbacks cannot prove that two rows are two
            # distinct fills.  A single full-volume row is usable, but rows
            # without identity must never be accumulated into a false fill.
            anonymous_max = max(anonymous_max, volume)
    return max(identified_total, anonymous_max)


def recover_expired_spool_lease(
    *,
    target_date: str,
    row: dict[str, Any],
    order_request: dict[str, Any],
    spool_lease_owner: str,
    spool_lease_token: str,
    close_retry_after_cancel_seconds: int,
    path: Path = LIVE_EXECUTION_LEDGER_PATH,
) -> LedgerRecoveryDecision:
    """Classify one expired spool lease while holding the ledger write lock.

    A matching reservation without any broker/API evidence is still pre-send
    and receives one durable safe-terminal marker.  Once an API slot or later
    side-effect evidence exists, recovery is reconciliation-only and must
    never make the intent sendable again.
    """

    owner = _clean(spool_lease_owner)
    token = _clean(spool_lease_token)
    if not owner:
        raise ValueError("spool_lease_owner_required")
    if not token:
        raise ValueError("spool_lease_token_required")
    fingerprint, fingerprint_payload = intent_fingerprint(
        target_date,
        row,
        order_request,
    )
    accepted_fingerprints = {
        fingerprint,
        *_legacy_alias_fingerprints(fingerprint_payload),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path_was_missing = not path.exists()
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.seek(0)
            rows = _parse_ledger_lines(handle.read().splitlines())
            integrity_error = _ledger_integrity_blocker(rows)
            if integrity_error:
                return LedgerRecoveryDecision(
                    disposition="blocked_ledger_integrity",
                    blocker=integrity_error,
                    intent_fingerprint=fingerprint,
                    evidence_event_type=integrity_error.split(":", 2)[1],
                    safe_terminal_appended=False,
                )

            unaccepted_lease_evidence = next(
                (
                    event
                    for event in reversed(rows)
                    if _clean(event.get("target_date")) == target_date
                    and _clean(event.get("intent_fingerprint"))
                    not in accepted_fingerprints
                    and _recovery_event_matches_lease(
                        event,
                        spool_lease_owner=owner,
                        spool_lease_token=token,
                    )
                ),
                None,
            )
            if unaccepted_lease_evidence is not None:
                return LedgerRecoveryDecision(
                    disposition="reconcile_only_side_effect_unknown",
                    blocker=(
                        "spool_crash_recovery_unaccepted_fingerprint_lease_evidence"
                    ),
                    intent_fingerprint=fingerprint,
                    evidence_event_type=_clean(
                        unaccepted_lease_evidence.get("event_type")
                    ),
                    safe_terminal_appended=False,
                )

            matched = [
                event
                for event in rows
                if _clean(event.get("target_date")) == target_date
                and _clean(event.get("intent_fingerprint"))
                in accepted_fingerprints
            ]
            exact_reservation_indexes = [
                index
                for index, event in enumerate(matched)
                if _clean(event.get("event_type")) == "reserved"
                and _recovery_event_matches_lease(
                    event,
                    spool_lease_owner=owner,
                    spool_lease_token=token,
                )
            ]
            if not exact_reservation_indexes:
                if matched:
                    return LedgerRecoveryDecision(
                        disposition="reconcile_only_side_effect_unknown",
                        blocker="spool_crash_recovery_lease_evidence_mismatch",
                        intent_fingerprint=fingerprint,
                        evidence_event_type=_clean(matched[-1].get("event_type")),
                        safe_terminal_appended=False,
                    )
                return LedgerRecoveryDecision(
                    disposition="requeue_pre_send",
                    blocker="",
                    intent_fingerprint=fingerprint,
                    evidence_event_type="",
                    safe_terminal_appended=False,
                )

            reservation_index = exact_reservation_indexes[-1]
            reservation = matched[reservation_index]
            after_reservation = matched[reservation_index + 1 :]
            exact_lease_events = [
                event
                for event in after_reservation
                if _recovery_event_matches_lease(
                    event,
                    spool_lease_owner=owner,
                    spool_lease_token=token,
                )
            ]
            known_order_ids = {
                _clean(event.get("vt_orderid"))
                for event in exact_lease_events
                if _clean(event.get("event_type"))
                in {
                    "native_order_identity_persisted_before_insert",
                    "send_order_returned",
                    "submitted_to_ctp",
                }
                and _clean(event.get("vt_orderid"))
            }
            exact_order_events = [
                event
                for event in exact_lease_events
                if not known_order_ids
                or not _clean(event.get("vt_orderid"))
                or _clean(event.get("vt_orderid")) in known_order_ids
            ]
            safe_terminals = [
                event
                for event in exact_lease_events
                if _clean(event.get("event_type"))
                == "spool_crash_recovery_pre_send_safe_terminal"
                and _recovery_event_matches_lease(
                    event,
                    spool_lease_owner=owner,
                    spool_lease_token=token,
                )
            ]
            post_slot_safe = next(
                (
                    (index, event)
                    for index, event in reversed(
                        list(enumerate(exact_lease_events))
                    )
                    if _clean(event.get("event_type"))
                    == POST_API_SLOT_SAFE_TERMINAL_EVENT
                    and valid_post_api_slot_no_native_safe_terminal(rows, event)
                    and _to_float(event.get("send_order_call_count"), -1.0)
                    == 0.0
                    and _to_float(event.get("native_api_called"), -1.0) == 0.0
                    and _clean(event.get("api_slot_batch_id"))
                ),
                None,
            )
            if post_slot_safe is not None:
                safe_index, safe_event = post_slot_safe
                later_native = next(
                    (
                        event
                        for event in exact_lease_events[safe_index + 1 :]
                        if _clean(event.get("event_type"))
                        in {
                            "send_order_called",
                            "native_order_identity_persisted_before_insert",
                            "send_order_returned",
                            "submitted_to_ctp",
                        }
                    ),
                    None,
                )
                if later_native is None:
                    return LedgerRecoveryDecision(
                        disposition="requeue_pre_send",
                        blocker="",
                        intent_fingerprint=fingerprint,
                        evidence_event_type=POST_API_SLOT_SAFE_TERMINAL_EVENT,
                        safe_terminal_appended=False,
                    )
            requested_volume = max(
                0.0,
                _to_float(fingerprint_payload.get("volume"), 0.0),
            )
            filled_volume = _recovery_fill_volume(exact_order_events)
            explicit_reconciled = next(
                (
                    event
                    for event in reversed(exact_order_events)
                    if (
                        _clean(event.get("event_type"))
                        in RECOVERY_RECONCILED_EVENTS
                    )
                    or (
                        _clean(event.get("event_type"))
                        == "broker_order_query_terminal_observed"
                        and _to_float(
                            event.get("fill_price_reconciliation_pending"),
                            1.0,
                        )
                        == 0.0
                    )
                ),
                None,
            )
            if explicit_reconciled is not None or (
                requested_volume > 0 and filled_volume >= requested_volume
            ):
                evidence = explicit_reconciled or next(
                    event
                    for event in reversed(exact_order_events)
                    if _clean(event.get("event_type"))
                    == "filled_or_part_filled"
                )
                return LedgerRecoveryDecision(
                    disposition="reconciled",
                    blocker="",
                    intent_fingerprint=fingerprint,
                    evidence_event_type=_clean(evidence.get("event_type")),
                    safe_terminal_appended=False,
                )

            side_effect = next(
                (
                    event
                    # Any post-reservation broker/API evidence is enough to
                    # forbid requeue, even when it lacks the retained lease
                    # binding.  Such unbound evidence can only keep the row
                    # reconciliation-only; it can never prove reconciled.
                    for event in reversed(after_reservation)
                    if _clean(event.get("event_type"))
                    in RECOVERY_SIDE_EFFECT_EVENTS
                    and not (
                        _clean(event.get("event_type"))
                        == "send_order_called"
                        and _clean(
                            event.get("native_identity_protocol_version")
                        )
                        == "stage179_preinsert_v1"
                        and _to_float(event.get("native_api_called"), 0.0)
                        == 0.0
                    )
                    or (
                        _clean(event.get("event_type"))
                        == "adapter_exception_after_reserve"
                        and _to_float(event.get("send_slot_reserved"), 0.0)
                        == 1.0
                    )
                ),
                None,
            )
            if side_effect is not None:
                return LedgerRecoveryDecision(
                    disposition="reconcile_only_side_effect_unknown",
                    blocker="",
                    intent_fingerprint=fingerprint,
                    evidence_event_type=_clean(side_effect.get("event_type")),
                    safe_terminal_appended=False,
                )

            if safe_terminals:
                return LedgerRecoveryDecision(
                    disposition="requeue_pre_send",
                    blocker="",
                    intent_fingerprint=fingerprint,
                    evidence_event_type=(
                        "spool_crash_recovery_pre_send_safe_terminal"
                    ),
                    safe_terminal_appended=False,
                )

            payload = {
                "schema_version": LEDGER_SCHEMA_VERSION,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "event_type": "spool_crash_recovery_pre_send_safe_terminal",
                "target_date": target_date,
                "intent_fingerprint": fingerprint,
                "intent_payload": fingerprint_payload,
                "spool_lease_owner": owner,
                "spool_lease_token": token,
                "pre_send_exception_confirmed": 1,
                "send_slot_reserved": 0,
                "recovered_from_event_type": _clean(
                    reservation.get("event_type")
                ),
            }
            for key in (
                "intent_id",
                "service_generation",
                "connection_generation",
                "close_submit_attempt_no",
                "close_attempt_lease_token",
            ):
                value = reservation.get(key)
                if _clean(value):
                    payload[key] = value
            _durable_append_locked(
                handle,
                payload,
                created_path=path if path_was_missing else None,
            )
            return LedgerRecoveryDecision(
                disposition="requeue_pre_send",
                blocker="",
                intent_fingerprint=fingerprint,
                evidence_event_type=(
                    "spool_crash_recovery_pre_send_safe_terminal"
                ),
                safe_terminal_appended=True,
            )
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


def _post_slot_terminalized_send_slot_indexes(
    rows: list[dict[str, Any]],
) -> set[int]:
    """Return send-slot rows proven to have reached zero native side effects.

    The strict terminal validator scans the complete tail after its exact
    reservation.  A terminal therefore dominates only its own earlier batch
    and only while no later native/send evidence exists for that lease.
    """

    terminalized: set[int] = set()
    for terminal_index, terminal in enumerate(rows):
        if not valid_post_api_slot_no_native_safe_terminal(rows, terminal):
            continue
        batch_id = _clean(terminal.get("api_slot_batch_id"))
        for slot_index, slot in enumerate(rows[:terminal_index]):
            if (
                _clean(slot.get("event_type")) == "api_slot_reserved"
                and _clean(slot.get("api_slot_type")) == "send_order"
                and _clean(slot.get("api_slot_batch_id")) == batch_id
                and _event_matches_warm_identity(slot, terminal)
                and _strict_positive_int(slot.get("close_submit_attempt_no"))
                == _strict_positive_int(terminal.get("close_submit_attempt_no"))
                and _clean(slot.get("close_attempt_lease_token"))
                == _clean(terminal.get("close_attempt_lease_token"))
            ):
                terminalized.add(slot_index)
    return terminalized


def _effective_close_submit_attempt_events(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    terminalized_slots = _post_slot_terminalized_send_slot_indexes(rows)
    return [
        row
        for index, row in enumerate(rows)
        if _is_close_submit_attempt_event(row)
        and index not in terminalized_slots
    ]


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
    terminalized_slot_indexes = _post_slot_terminalized_send_slot_indexes(
        matched_events
    )
    for item_index, item in enumerate(
        after_reservation,
        start=reservation_index + 1,
    ):
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
            (
                _is_close_submit_attempt_event(item)
                and item_index not in terminalized_slot_indexes
            )
            or event_type in CLOSE_PERMANENT_EVIDENCE_EVENTS
            or event_type in {"submitted_to_ctp", "adapter_exception_after_send"}
            or (
                event_type == "adapter_exception_after_reserve"
                and _to_float(item.get("send_slot_reserved"), 0.0) == 1.0
            )
        ):
            return {"status": "side_effect", "event": item, "token": token}

    immediate_safe_terminals: list[dict[str, Any]] = []
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
        if event_type == PRE_API_SLOT_SAFE_TERMINAL_EVENT:
            if _valid_pre_api_slot_safe_terminal(item, reservation):
                immediate_safe_terminals.append(item)
            continue
        if event_type == POST_API_SLOT_SAFE_TERMINAL_EVENT:
            if valid_post_api_slot_no_native_safe_terminal(
                matched_events, item
            ):
                immediate_safe_terminals.append(item)
            continue
        if event_type == "adapter_exception_after_reserve" and (
            _to_float(item.get("pre_send_exception_confirmed"), 0.0) != 1.0
            or _to_float(item.get("send_slot_reserved"), 0.0) == 1.0
        ):
            continue
        safe_terminals.append(item)
    if immediate_safe_terminals:
        return {
            "status": "safe_terminal_immediate",
            "event": immediate_safe_terminals[-1],
            "token": token,
            "lease_seconds": effective_lease_seconds,
            "retry_cooldown_seconds": effective_retry_cooldown_seconds,
        }
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
    if state in {"safe_terminal", "safe_terminal_immediate"}:
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
    submit_events = _effective_close_submit_attempt_events(matched_events)
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
            iter(
                _effective_close_submit_attempt_events(
                    matched_events[known_zero_index + 1 :]
                )
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
        if lease_status == "safe_terminal_immediate":
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
    if lease_status == "safe_terminal_immediate":
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

    # Open deduplication is a full-history reducer.  A diagnostic row written
    # after an API slot or broker call must never hide the earlier permanent
    # side-effect boundary.
    side_effect = next(
        (
            item
            for item in matched_events
            if _clean(item.get("event_type")) in RECOVERY_SIDE_EFFECT_EVENTS
            or (
                _clean(item.get("event_type"))
                == "adapter_exception_after_reserve"
                and _to_float(item.get("send_slot_reserved"), 0.0) == 1.0
            )
        ),
        None,
    )
    if side_effect is not None:
        return (
            "ledger_duplicate_open_intent:"
            f"{_clean(side_effect.get('event_type'))}",
            fingerprint,
            payload,
            side_effect,
        )

    reservation_indexes = [
        index
        for index, item in enumerate(matched_events)
        if _clean(item.get("event_type")) == "reserved"
    ]
    if reservation_indexes:
        reservation_index = reservation_indexes[-1]
        reservation = matched_events[reservation_index]
        after_reservation = matched_events[reservation_index + 1 :]
        versioned_terminals = [
            item
            for item in after_reservation
            if _clean(item.get("event_type"))
            == PRE_API_SLOT_SAFE_TERMINAL_EVENT
            and _clean(item.get("reservation_record_checksum"))
            == _clean(reservation.get("record_checksum"))
        ]
        if versioned_terminals:
            terminal = versioned_terminals[-1]
            if not _valid_pre_api_slot_safe_terminal(terminal, reservation):
                return (
                    "ledger_open_safe_terminal_invalid",
                    fingerprint,
                    payload,
                    terminal,
                )
            return "", fingerprint, payload, terminal

        legacy_terminal = next(
            (
                item
                for item in reversed(after_reservation)
                if _clean(item.get("event_type"))
                == "final_pre_send_gate_blocked_after_reserve"
            ),
            None,
        )
        if legacy_terminal is not None:
            age = event_age_seconds(legacy_terminal)
            throttle_seconds = max(30, close_retry_after_cancel_seconds)
            if age is not None and age < throttle_seconds:
                return (
                    "ledger_open_retry_throttled_after_final_pre_send_gate:"
                    f"{age}",
                    fingerprint,
                    payload,
                    legacy_terminal,
                )
            return "", fingerprint, payload, legacy_terminal

        legacy_released = next(
            (
                item
                for item in reversed(after_reservation)
                if _clean(item.get("event_type"))
                in {
                    "api_slot_reservation_blocked",
                    "spool_crash_recovery_pre_send_safe_terminal",
                }
            ),
            None,
        )
        if legacy_released is not None:
            return "", fingerprint, payload, legacy_released
        return (
            "ledger_duplicate_open_intent:reserved",
            fingerprint,
            payload,
            reservation,
        )

    if event_type == "final_pre_send_gate_blocked_after_reserve":
        age = event_age_seconds(latest)
        throttle_seconds = max(30, close_retry_after_cancel_seconds)
        if age is not None and age < throttle_seconds:
            return f"ledger_open_retry_throttled_after_final_pre_send_gate:{age}", fingerprint, payload, latest
        return "", fingerprint, payload, latest
    if event_type in OPEN_BLOCKING_EVENTS:
        return f"ledger_duplicate_open_intent:{event_type}", fingerprint, payload, latest
    return "", fingerprint, payload, latest
