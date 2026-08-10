from __future__ import annotations

import fcntl
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_live_phase_d_config import LIVE_EXECUTION_LEDGER_PATH


LEDGER_SCHEMA_VERSION = 1
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
}
CLOSE_BLOCKING_EVENTS = {
    "send_order_called",
    "send_order_returned_empty",
    "filled_or_part_filled",
    "rejected_or_inactive",
    "unknown_order_status_after_send",
    "residual_order_active_after_cancel",
    "residual_order_unknown_after_cancel",
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


def event_age_seconds(row: dict[str, Any], now: datetime | None = None) -> float | None:
    generated = _parse_dt(row.get("generated_at"))
    if generated is None:
        return None
    return max(0.0, ((now or datetime.now()) - generated).total_seconds())


def _stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


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
    return payload


def intent_fingerprint(target_date: str, row: dict[str, Any], order_request: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    payload = normalize_intent_payload(target_date, row, order_request)
    fingerprint_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"limit_price", "source", "source_reason", "reference"}
    }
    digest = hashlib.sha256(_stable_json(fingerprint_payload).encode("utf-8")).hexdigest()
    return digest, payload


class ExecutionLedgerIntegrityError(RuntimeError):
    pass


def read_execution_ledger(
    path: Path = LIVE_EXECUTION_LEDGER_PATH,
    *,
    strict: bool = True,
) -> list[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            try:
                lines = handle.read().splitlines()
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except FileNotFoundError:
        return []
    return _parse_ledger_lines(lines, strict=strict)


def _parse_ledger_lines(lines: list[str], *, strict: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in lines:
        text = line.strip()
        if not text:
            continue
        try:
            rows.append(json.loads(text))
        except json.JSONDecodeError as exc:
            if strict:
                raise ExecutionLedgerIntegrityError("execution ledger contains invalid JSON") from exc
            rows.append({"event_type": "ledger_decode_error", "raw_line": text[:500]})
    return rows


def append_execution_ledger_event(event: dict[str, Any], path: Path = LIVE_EXECUTION_LEDGER_PATH) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **event,
    }
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return payload


def reserve_execution_ledger_intent(
    *,
    target_date: str,
    row: dict[str, Any],
    order_request: dict[str, Any],
    close_retry_after_cancel_seconds: int,
    base_event: dict[str, Any],
    path: Path = LIVE_EXECUTION_LEDGER_PATH,
) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        rows = _parse_ledger_lines(handle.read().splitlines(), strict=True)
        duplicate, fingerprint, fingerprint_payload, latest = duplicate_blocker(
            rows=rows,
            target_date=target_date,
            row=row,
            order_request=order_request,
            close_retry_after_cancel_seconds=close_retry_after_cancel_seconds,
        )
        if duplicate:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            return {
                "reserved": False,
                "duplicate_blocker": duplicate,
                "intent_fingerprint": fingerprint,
                "intent_payload": fingerprint_payload,
                "latest_ledger_event": latest or {},
            }
        payload = {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "event_type": "reserved",
            "target_date": target_date,
            "intent_fingerprint": fingerprint,
            "intent_payload": fingerprint_payload,
            **base_event,
        }
        handle.seek(0, 2)
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return {
            "reserved": True,
            "duplicate_blocker": "",
            "intent_fingerprint": fingerprint,
            "intent_payload": fingerprint_payload,
            "latest_ledger_event": payload,
        }


def latest_event_for_fingerprint(rows: list[dict[str, Any]], fingerprint: str) -> dict[str, Any] | None:
    matched = [row for row in rows if _clean(row.get("intent_fingerprint")) == fingerprint]
    return matched[-1] if matched else None


def events_for_fingerprint(rows: list[dict[str, Any]], fingerprint: str) -> list[dict[str, Any]]:
    return [row for row in rows if _clean(row.get("intent_fingerprint")) == fingerprint]


def ledger_order_api_counts(rows: list[dict[str, Any]], target_date: str) -> dict[str, int]:
    dated = [row for row in rows if _clean(row.get("target_date")) == target_date]
    return {
        "send_order_called": sum(1 for row in dated if row.get("event_type") == "send_order_called"),
        "cancel_order_called": sum(1 for row in dated if row.get("event_type") == "cancel_order_called"),
        "reserved": sum(1 for row in dated if row.get("event_type") == "reserved"),
    }


def _event_intent_payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = row.get("intent_payload")
    return payload if isinstance(payload, dict) else {}


def _event_vt_symbol(row: dict[str, Any]) -> str:
    payload = _event_intent_payload(row)
    return _clean(row.get("vt_symbol") or payload.get("vt_symbol"))


def _event_direction(row: dict[str, Any]) -> str:
    payload = _event_intent_payload(row)
    return _normalize_direction_text(row.get("direction") or payload.get("direction"))


def _event_offset(row: dict[str, Any]) -> str:
    payload = _event_intent_payload(row)
    return _normalize_offset_text(row.get("offset") or payload.get("offset"))


def open_fill_rows(rows: list[dict[str, Any]], target_date: str, vt_symbol: str, direction: str) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if _clean(row.get("target_date")) == target_date
        and _clean(row.get("event_type")) == "filled_or_part_filled"
        and _event_vt_symbol(row) == vt_symbol
        and _event_offset(row) == "open"
        and _event_direction(row) == direction.lower()
    ]


def weighted_open_fill(rows: list[dict[str, Any]], target_date: str, vt_symbol: str, direction: str) -> dict[str, Any] | None:
    fills = open_fill_rows(rows, target_date, vt_symbol, direction)
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


def duplicate_blocker(
    *,
    rows: list[dict[str, Any]],
    target_date: str,
    row: dict[str, Any],
    order_request: dict[str, Any],
    close_retry_after_cancel_seconds: int,
) -> tuple[str, str, dict[str, Any], dict[str, Any] | None]:
    fingerprint, payload = intent_fingerprint(target_date, row, order_request)
    matched_events = events_for_fingerprint(rows, fingerprint)
    latest = matched_events[-1] if matched_events else None
    if latest is None:
        return "", fingerprint, payload, None
    event_type = _clean(latest.get("event_type"))
    offset = _clean(payload.get("offset")).lower()
    if offset == "close" and any(_clean(item.get("event_type")) == "filled_or_part_filled" for item in matched_events):
        return "ledger_duplicate_close_intent:filled_or_part_filled", fingerprint, payload, latest
    if offset == "close" and any(_clean(item.get("event_type")) == "residual_order_active_after_cancel" for item in matched_events):
        return "ledger_duplicate_close_intent:residual_order_active_after_cancel", fingerprint, payload, latest
    if offset == "close" and any(_clean(item.get("event_type")) == "residual_order_unknown_after_cancel" for item in matched_events):
        return "ledger_duplicate_close_intent:residual_order_unknown_after_cancel", fingerprint, payload, latest
    if offset == "close" and any(_clean(item.get("event_type")) == "unknown_order_status_after_send" for item in matched_events):
        return "ledger_duplicate_close_intent:unknown_order_status_after_send", fingerprint, payload, latest
    if offset == "close" and event_type in {"reserved", "final_pre_send_gate_blocked_after_reserve"}:
        age = event_age_seconds(latest)
        if age is not None and age >= close_retry_after_cancel_seconds:
            return "", fingerprint, payload, latest
        return f"ledger_close_retry_throttled_after_{event_type}:{age}", fingerprint, payload, latest
    if offset == "close" and event_type == "adapter_exception_after_reserve":
        if any(_clean(item.get("event_type")) == "send_order_called" for item in matched_events):
            return "ledger_duplicate_close_intent:send_order_called_before_adapter_exception", fingerprint, payload, latest
        age = event_age_seconds(latest)
        if age is not None and age >= close_retry_after_cancel_seconds:
            return "", fingerprint, payload, latest
        return f"ledger_close_retry_throttled_after_{event_type}:{age}", fingerprint, payload, latest
    if offset == "close" and event_type == "cancel_order_called":
        age = event_age_seconds(latest)
        if age is not None and age >= close_retry_after_cancel_seconds:
            return "", fingerprint, payload, latest
        return f"ledger_close_retry_throttled_after_cancel:{age}", fingerprint, payload, latest
    if offset == "close":
        if event_type in CLOSE_BLOCKING_EVENTS:
            return f"ledger_duplicate_close_intent:{event_type}", fingerprint, payload, latest
        return "", fingerprint, payload, latest
    if event_type == "final_pre_send_gate_blocked_after_reserve":
        age = event_age_seconds(latest)
        throttle_seconds = max(30, close_retry_after_cancel_seconds)
        if age is not None and age < throttle_seconds:
            return f"ledger_open_retry_throttled_after_final_pre_send_gate:{age}", fingerprint, payload, latest
        return "", fingerprint, payload, latest
    if event_type in OPEN_BLOCKING_EVENTS:
        return f"ledger_duplicate_open_intent:{event_type}", fingerprint, payload, latest
    return "", fingerprint, payload, latest
