from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


VALID_DIRECTIONS = {"long", "short", "多", "空", "direction.long", "direction.short"}
VALID_OFFSETS = {
    "open",
    "close",
    "closetoday",
    "closeyesterday",
    "开",
    "平",
    "平今",
    "平昨",
    "offset.open",
    "offset.close",
    "offset.closetoday",
    "offset.closeyesterday",
}


@dataclass(frozen=True)
class ExecutionThresholdConfig:
    order_count_warn: int = 3
    cancel_count_warn: int = 1
    duplicate_intent_warn: int = 1


@dataclass(frozen=True)
class PauseGateState:
    account_trading_allowed: bool = True
    strategy_enabled: bool = True
    session_logged_in: bool = True


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number):
        return default
    return number


def normalize_direction(value: Any) -> str:
    text = clean_text(value).lower()
    if text in {"long", "多", "direction.long"}:
        return "long"
    if text in {"short", "空", "direction.short"}:
        return "short"
    return text


def normalize_offset(value: Any) -> str:
    text = clean_text(value).lower()
    if text in {"open", "开", "offset.open"}:
        return "open"
    if text in {"close", "平", "offset.close", "closetoday", "closeyesterday", "平今", "平昨", "offset.closetoday", "offset.closeyesterday"}:
        return "close"
    return text


def split_vt_symbol(vt_symbol: str) -> tuple[str, str]:
    if "." not in vt_symbol:
        return vt_symbol, ""
    return vt_symbol.rsplit(".", 1)


def price_on_tick(price: float, pricetick: float) -> bool:
    if price <= 0 or pricetick <= 0:
        return False
    units = price / pricetick
    return math.isclose(units, round(units), rel_tol=0.0, abs_tol=1e-8)


def build_contract_lookup(contract_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in contract_rows:
        vt_symbol = clean_text(row.get("vt_symbol"))
        if not vt_symbol:
            symbol = clean_text(row.get("symbol"))
            exchange = clean_text(row.get("exchange"))
            vt_symbol = f"{symbol}.{exchange}" if symbol and exchange else ""
        if vt_symbol:
            lookup[vt_symbol] = row
    return lookup


def validate_order_instruction(
    *,
    vt_symbol: str,
    direction: str,
    offset: str,
    price: float,
    volume: float,
    contract_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    reasons: list[str] = []
    symbol, exchange = split_vt_symbol(vt_symbol)
    direction_norm = normalize_direction(direction)
    offset_norm = normalize_offset(offset)
    contract = contract_lookup.get(vt_symbol)

    if not symbol or not exchange:
        reasons.append("invalid_vt_symbol")
    if direction_norm not in {"long", "short"}:
        reasons.append("invalid_direction")
    if offset_norm not in {"open", "close"}:
        reasons.append("invalid_offset")
    if contract is None:
        reasons.append("contract_not_found")

    pricetick = to_float(contract.get("pricetick") if contract else None)
    min_volume = to_float(contract.get("min_volume") if contract else None)
    max_volume = to_float(contract.get("max_volume") if contract else None)

    if volume <= 0:
        reasons.append("invalid_volume")
    if min_volume and volume < min_volume:
        reasons.append("volume_below_min")
    if max_volume and volume > max_volume:
        reasons.append("volume_above_max")
    if not float(volume).is_integer():
        reasons.append("volume_not_integer_lots")
    if price <= 0:
        reasons.append("invalid_price")
    if pricetick and not price_on_tick(price, pricetick):
        reasons.append("price_not_on_tick")

    return {
        "accepted": not reasons,
        "reasons": reasons,
        "symbol": symbol,
        "exchange": exchange,
        "direction": direction_norm,
        "offset": offset_norm,
        "price": price,
        "volume": volume,
        "pricetick": pricetick,
        "min_volume": min_volume,
        "max_volume": max_volume,
        "order_api_called": 0,
    }


def evaluate_execution_thresholds(
    *,
    order_count: int,
    cancel_count: int,
    duplicate_intent_count: int,
    config: ExecutionThresholdConfig,
) -> list[dict[str, Any]]:
    checks = [
        ("order_count", order_count, config.order_count_warn),
        ("cancel_count", cancel_count, config.cancel_count_warn),
        ("duplicate_intent_count", duplicate_intent_count, config.duplicate_intent_warn),
    ]
    rows: list[dict[str, Any]] = []
    for metric, value, threshold in checks:
        rows.append(
            {
                "metric": metric,
                "value": int(value),
                "threshold": int(threshold),
                "warning": bool(value >= threshold),
                "message": f"{metric} reached threshold {threshold}" if value >= threshold else "",
            }
        )
    return rows


def normalize_ctp_error(error_id: int | str, error_msg: str) -> dict[str, Any]:
    text = clean_text(error_msg)
    lowered = text.lower()
    if "资金" in text and ("不足" in text or "不够" in text):
        category = "insufficient_funds_open"
        severity = "reject"
    elif "持仓" in text and ("不足" in text or "不够" in text or "超过" in text):
        category = "insufficient_position_close"
        severity = "reject"
    elif "平仓" in text and ("不足" in text or "超过" in text or "无" in text):
        category = "insufficient_position_close"
        severity = "reject"
    elif "非交易" in text or "未开市" in text or "市场状态" in text or "不允许" in text or "not trading" in lowered:
        category = "market_state_not_allowed"
        severity = "reject"
    elif clean_text(error_id) in {"0", ""}:
        category = "ok"
        severity = "info"
    else:
        category = "generic_ctp_error"
        severity = "reject"
    return {
        "error_id": clean_text(error_id),
        "error_msg": text,
        "category": category,
        "severity": severity,
        "display_text": f"{category}: {text}" if category != "ok" else "ok",
    }


def evaluate_pause_gate(state: PauseGateState) -> dict[str, Any]:
    reasons: list[str] = []
    if not state.account_trading_allowed:
        reasons.append("account_trading_permission_restricted")
    if not state.strategy_enabled:
        reasons.append("strategy_paused")
    if not state.session_logged_in:
        reasons.append("forced_logout_or_session_not_logged_in")
    return {
        "can_submit": not reasons,
        "reasons": reasons,
        "order_api_called": 0 if reasons else None,
    }
