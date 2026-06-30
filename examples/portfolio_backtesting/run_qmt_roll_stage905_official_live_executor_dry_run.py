from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION
from qmt_roll_official_live_execution_ledger import read_execution_ledger
from qmt_roll_official_live_phase_d_config import (
    READONLY_CONTRACTS_PATH,
    READONLY_ORDERS_PATH,
    READONLY_POSITIONS_PATH,
    STAGE901_PENDING_ORDERS_PATH,
    build_phase_d_config,
)
from run_qmt_alignment_backtest import OUTPUT_DIR
from vnpy.trader.constant import Direction, Exchange, Offset, OrderType
from vnpy.trader.object import OrderRequest


MODEL_TAG = "stage905_official_live_executor_dry_run_v1"
OUTPUT_PREFIX = "qmt_roll_stage905_official_live_executor_dry_run"
STAGE902_MODEL_TAG = "stage902_official_live_phase_d_readiness_gate_v1"
STAGE902_PREFIX = "qmt_roll_stage902_official_live_phase_d_readiness_gate"
STAGE904_MODEL_TAG = "stage904_official_live_c9_intraday_monitor_v1"
STAGE904_PREFIX = "qmt_roll_stage904_official_live_c9_intraday_monitor"
STAGE260_MODEL_TAG = "stage260_official_live_daily_execution_gate_v1"
STAGE260_PREFIX = "qmt_roll_stage260_official_live_daily_execution_gate"
RETRY_INTENT_ROLE = "c9_retry_open_once"
ACTIVE_ORDER_STATUSES = {
    "submitting",
    "submitted",
    "not traded",
    "nottraded",
    "part traded",
    "parttraded",
    "未成交",
    "提交中",
    "部分成交",
}
TERMINAL_ORDER_STATUSES = {
    "all traded",
    "alltraded",
    "filled",
    "cancelled",
    "canceled",
    "rejected",
    "全部成交",
    "已成交",
    "已撤单",
    "已撤销",
    "撤单",
    "拒单",
    "已拒绝",
    "废单",
}


def _paths(target_date: str) -> dict[str, Path]:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return {
        "intents_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_intents_{date_key}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{date_key}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{date_key}_{MODEL_TAG}.md",
    }


def _stage902_summary_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE902_PREFIX}_summary_{date_key}_{STAGE902_MODEL_TAG}.json"


def _stage904_actions_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE904_PREFIX}_actions_{date_key}_{STAGE904_MODEL_TAG}.csv"


def _stage260_summary_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE260_PREFIX}_summary_{date_key}_{STAGE260_MODEL_TAG}.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _read_csv_maybe(path: str | Path | None) -> pd.DataFrame:
    if not path:
        return pd.DataFrame()
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(p, encoding="utf-8-sig")
    except EmptyDataError:
        return pd.DataFrame()


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
    if text in {"close", "平", "closetoday", "closeyesterday", "平今", "平昨", "offset.close", "offset.closetoday", "offset.closeyesterday"}:
        return "close"
    return text


def _normalize_direction(value: Any) -> Direction | None:
    text = _normalize_direction_text(value)
    if text == "long":
        return Direction.LONG
    if text == "short":
        return Direction.SHORT
    return None


def _normalize_offset(value: Any) -> Offset | None:
    text = _normalize_offset_text(value)
    if text == "open":
        return Offset.OPEN
    if text == "close":
        return Offset.CLOSE
    return None


def _split_vt_symbol(vt_symbol: str) -> tuple[str, str]:
    if "." not in vt_symbol:
        return vt_symbol, ""
    return vt_symbol.rsplit(".", 1)


def _contract_row(contracts: pd.DataFrame, vt_symbol: str) -> dict[str, Any] | None:
    if contracts.empty:
        return None
    symbol, exchange = _split_vt_symbol(vt_symbol)
    if "vt_symbol" in contracts.columns:
        matched = contracts[contracts["vt_symbol"].fillna("").astype(str).eq(vt_symbol)]
        if not matched.empty:
            return matched.iloc[0].to_dict()
    if "symbol" in contracts.columns and "exchange" in contracts.columns:
        matched = contracts[
            contracts["symbol"].fillna("").astype(str).eq(symbol)
            & contracts["exchange"].fillna("").astype(str).eq(exchange)
        ]
        if not matched.empty:
            return matched.iloc[0].to_dict()
    return None


def _price_on_tick(price: float, pricetick: float) -> bool:
    if price <= 0 or pricetick <= 0:
        return False
    units = price / pricetick
    return math.isclose(units, round(units), rel_tol=0.0, abs_tol=1e-8)


def _snap_price_to_tick(price: float, pricetick: float, direction: str) -> float:
    if price <= 0 or pricetick <= 0:
        return price
    units = price / pricetick
    if direction == "short":
        return round(math.floor(units) * pricetick, 10)
    if direction == "long":
        return round(math.ceil(units) * pricetick, 10)
    return price


def _opposite_position_direction(order_direction: str) -> str:
    if order_direction == "long":
        return "short"
    if order_direction == "short":
        return "long"
    return ""


def _dedupe_position_snapshots(positions: pd.DataFrame) -> pd.DataFrame:
    if positions.empty:
        return positions
    frame = positions.copy()
    key_columns = [
        column
        for column in (
            "vt_symbol",
            "symbol",
            "exchange",
            "instrument",
            "instrument_id",
            "direction",
            "volume",
            "position",
            "pos",
            "frozen",
            "frozen_volume",
            "yd_volume",
            "price",
        )
        if column in frame.columns
    ]
    if not key_columns:
        return frame.drop_duplicates()
    return frame.drop_duplicates(subset=key_columns, keep="last")


def _position_volume(positions: pd.DataFrame, vt_symbol: str, direction: str) -> float:
    if positions.empty:
        return 0.0
    frame = _dedupe_position_snapshots(positions)
    if "vt_symbol" in frame.columns:
        vt = frame["vt_symbol"].fillna("").astype(str)
    elif "symbol" in frame.columns and "exchange" in frame.columns:
        vt = frame["symbol"].fillna("").astype(str) + "." + frame["exchange"].fillna("").astype(str)
    elif "instrument" in frame.columns:
        vt = frame["instrument"].fillna("").astype(str)
    else:
        return 0.0
    pos_direction = frame.get("direction", pd.Series([""] * len(frame))).map(_normalize_direction_text)
    volume = pd.to_numeric(frame.get("volume", frame.get("position", frame.get("pos", 0.0))), errors="coerce").fillna(0.0)
    frozen = pd.to_numeric(frame.get("frozen", 0.0), errors="coerce").fillna(0.0)
    available = (volume - frozen).clip(lower=0.0)
    return float(available[vt.eq(vt_symbol) & pos_direction.eq(direction)].sum())


def _position_gross_volume(positions: pd.DataFrame, vt_symbol: str, direction: str) -> float:
    if positions.empty:
        return 0.0
    frame = _dedupe_position_snapshots(positions)
    if "vt_symbol" in frame.columns:
        vt = frame["vt_symbol"].fillna("").astype(str)
    elif "symbol" in frame.columns and "exchange" in frame.columns:
        vt = frame["symbol"].fillna("").astype(str) + "." + frame["exchange"].fillna("").astype(str)
    elif "instrument" in frame.columns:
        vt = frame["instrument"].fillna("").astype(str)
    else:
        return 0.0
    pos_direction = frame.get("direction", pd.Series([""] * len(frame))).map(_normalize_direction_text)
    volume = pd.to_numeric(frame.get("volume", frame.get("position", frame.get("pos", 0.0))), errors="coerce").fillna(0.0)
    return float(volume.clip(lower=0.0)[vt.eq(vt_symbol) & pos_direction.eq(direction)].sum())


def _latest_order_statuses(orders: pd.DataFrame) -> pd.Series:
    if orders.empty:
        return pd.Series(dtype=str)
    frame = orders.copy()
    key_source = frame.get("vt_orderid", frame.get("orderid", pd.Series([""] * len(frame))))
    frame["_order_key"] = key_source.fillna("").astype(str)
    empty_key = frame["_order_key"].eq("")
    frame.loc[empty_key, "_order_key"] = [f"row_{idx}" for idx in frame.index[empty_key]]
    frame["_row_order"] = range(len(frame))
    sort_cols = ["_order_key", "_row_order"]
    latest = frame.sort_values(sort_cols).drop_duplicates("_order_key", keep="last")
    if "status" not in latest.columns:
        return pd.Series([""] * len(latest), dtype=str)
    return latest["status"].fillna("").astype(str).str.strip().str.lower()


def _active_order_count(orders: pd.DataFrame) -> int:
    statuses = _latest_order_statuses(orders)
    return int(statuses.isin(ACTIVE_ORDER_STATUSES).sum())


def _unknown_order_status_count(orders: pd.DataFrame) -> int:
    statuses = _latest_order_statuses(orders)
    if statuses.empty:
        return 0
    known = ACTIVE_ORDER_STATUSES | TERMINAL_ORDER_STATUSES
    return int((~statuses.isin(known)).sum())


def _clip_price(price: float, lower: float, upper: float) -> float:
    if lower > 0:
        price = max(price, lower)
    if upper > 0:
        price = min(price, upper)
    return price


def _protective_close_price(intent: dict[str, Any], direction_text: str, pricetick: float, fallback_price: float) -> tuple[float, str]:
    protection_ticks = max(1, int(build_phase_d_config().hard_limits.max_slippage_ticks))
    tick_value = pricetick if pricetick > 0 else 0.0
    live_price = _to_float(intent.get("live_price"), 0.0)
    bid = _to_float(intent.get("live_bid_price_1"), 0.0)
    ask = _to_float(intent.get("live_ask_price_1"), 0.0)
    lower = _to_float(intent.get("live_limit_down"), 0.0)
    upper = _to_float(intent.get("live_limit_up"), 0.0)
    if direction_text == "short":
        basis = bid if bid > 0 else live_price if live_price > 0 else fallback_price
        price = basis - protection_ticks * tick_value if tick_value > 0 else basis
        return _clip_price(price, lower, upper), f"marketable_sell_close:bid_or_live={basis};protection_ticks={protection_ticks}"
    if direction_text == "long":
        basis = ask if ask > 0 else live_price if live_price > 0 else fallback_price
        price = basis + protection_ticks * tick_value if tick_value > 0 else basis
        return _clip_price(price, lower, upper), f"marketable_buy_close:ask_or_live={basis};protection_ticks={protection_ticks}"
    return fallback_price, "protective_close_price_invalid_direction"


def _pending_order_intents(pending_orders: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(pending_orders.to_dict(orient="records"), start=1):
        vt_symbol = _clean(row.get("vt_symbol"))
        rows.append(
            {
                "intent_id": f"STAGE905-PENDING-{idx:03d}",
                "source": "stage901_pending_order",
                "vt_symbol": vt_symbol,
                "direction": _normalize_direction_text(row.get("direction")),
                "offset": _normalize_offset_text(row.get("offset")),
                "planned_volume": _to_float(row.get("volume"), 0.0),
                "limit_price": _to_float(row.get("price"), 0.0),
                "source_reason": _clean(row.get("status")),
            }
        )
    return rows


def _ledger_intent_payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = row.get("intent_payload")
    return payload if isinstance(payload, dict) else {}


def _ledger_vt_symbol(row: dict[str, Any]) -> str:
    payload = _ledger_intent_payload(row)
    return _clean(row.get("vt_symbol") or payload.get("vt_symbol"))


def _ledger_direction(row: dict[str, Any]) -> str:
    payload = _ledger_intent_payload(row)
    return _normalize_direction_text(row.get("direction") or payload.get("direction"))


def _ledger_offset(row: dict[str, Any]) -> str:
    payload = _ledger_intent_payload(row)
    return _normalize_offset_text(row.get("offset") or payload.get("offset"))


def _ledger_source(row: dict[str, Any]) -> str:
    payload = _ledger_intent_payload(row)
    return _clean(row.get("source") or payload.get("source"))


def _opposite_direction_text(direction: str) -> str:
    if direction == "long":
        return "short"
    if direction == "short":
        return "long"
    return ""


def _has_stage904_stop_close_fill(
    ledger_rows: list[dict[str, Any]],
    target_date: str,
    vt_symbol: str,
    original_direction: str,
) -> bool:
    close_direction = _opposite_direction_text(original_direction)
    if not target_date or not vt_symbol or close_direction not in {"long", "short"}:
        return False
    for row in ledger_rows:
        if _clean(row.get("target_date")) != target_date:
            continue
        if _clean(row.get("event_type")) != "filled_or_part_filled":
            continue
        if _ledger_vt_symbol(row) != vt_symbol:
            continue
        if _ledger_direction(row) != close_direction:
            continue
        if _ledger_offset(row) != "close":
            continue
        intent_id = _clean(row.get("intent_id"))
        if intent_id.startswith("STAGE905-C9MON") or _ledger_source(row) == "stage904_c9_intraday_close":
            return True
    return False


def _suppress_stage901_pending_after_stop_close(
    pending_intents: list[dict[str, Any]],
    *,
    ledger_rows: list[dict[str, Any]],
    target_date: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for intent in pending_intents:
        source = _clean(intent.get("source"))
        offset = _normalize_offset_text(intent.get("offset"))
        direction = _normalize_direction_text(intent.get("direction"))
        vt_symbol = _clean(intent.get("vt_symbol"))
        if (
            source == "stage901_pending_order"
            and offset == "open"
            and _has_stage904_stop_close_fill(ledger_rows, target_date, vt_symbol, direction)
        ):
            item = dict(intent)
            item["force_skip_reason"] = "stage901_pending_open_suppressed_after_stage904_stop_close_wait_for_retry"
            reason = _clean(item.get("source_reason"))
            suffix = "suppressed_after_stage904_stop_close_wait_for_stage904_retry"
            item["source_reason"] = f"{reason};{suffix}" if reason else suffix
            rows.append(item)
            continue
        rows.append(intent)
    return rows


def _stage904_intents(stage904_actions: pd.DataFrame) -> list[dict[str, Any]]:
    if stage904_actions.empty or "monitor_action" not in stage904_actions.columns:
        return []
    rows: list[dict[str, Any]] = []
    close_actions = stage904_actions[stage904_actions["monitor_action"].astype(str).eq("close_dry_run")]
    for idx, row in enumerate(close_actions.to_dict(orient="records"), start=1):
        current_direction = _normalize_direction_text(row.get("direction"))
        close_direction = "short" if current_direction == "long" else "long" if current_direction == "short" else ""
        rows.append(
            {
                "intent_id": f"STAGE905-C9MON-{idx:03d}",
                "source": "stage904_c9_intraday_close",
                "vt_symbol": _clean(row.get("vt_symbol")),
                "direction": close_direction,
                "offset": "close",
                "planned_volume": _to_float(row.get("volume"), 0.0),
                "limit_price": _to_float(row.get("stage847_stop_price"), 0.0),
                "stop_trigger_price": _to_float(row.get("stage847_stop_price"), 0.0),
                "trigger_live_price": _to_float(row.get("live_price"), 0.0),
                "trigger_adverse_extreme_price": _to_float(row.get("adverse_extreme_price"), 0.0),
                "live_bid_price_1": _to_float(row.get("live_bid_price_1"), 0.0),
                "live_ask_price_1": _to_float(row.get("live_ask_price_1"), 0.0),
                "live_limit_up": _to_float(row.get("live_limit_up"), 0.0),
                "live_limit_down": _to_float(row.get("live_limit_down"), 0.0),
                "source_reason": _clean(row.get("monitor_reason")),
            }
        )
    retry_actions = stage904_actions[stage904_actions["monitor_action"].astype(str).eq("retry_open_dry_run")]
    for idx, row in enumerate(retry_actions.to_dict(orient="records"), start=1):
        rows.append(
            {
                "intent_id": f"STAGE905-C9RETRY-{idx:03d}",
                "source": "stage904_c9_intraday_retry_open",
                "intent_role": RETRY_INTENT_ROLE,
                "vt_symbol": _clean(row.get("vt_symbol")),
                "direction": _normalize_direction_text(row.get("direction")),
                "offset": "open",
                "planned_volume": _to_float(row.get("volume"), 0.0),
                "limit_price": _to_float(row.get("stage847_retry_trigger_price", row.get("fill_price")), 0.0),
                "retry_trigger_price": _to_float(row.get("stage847_retry_trigger_price", row.get("fill_price")), 0.0),
                "retry_stop_price": _to_float(row.get("stage847_stop_price"), 0.0),
                "retry_original_fill_price": _to_float(row.get("fill_price"), 0.0),
                "trigger_live_price": _to_float(row.get("live_price"), 0.0),
                "trigger_progress_extreme_price": _to_float(row.get("progress_extreme_price"), 0.0),
                "live_bid_price_1": _to_float(row.get("live_bid_price_1"), 0.0),
                "live_ask_price_1": _to_float(row.get("live_ask_price_1"), 0.0),
                "live_limit_up": _to_float(row.get("live_limit_up"), 0.0),
                "live_limit_down": _to_float(row.get("live_limit_down"), 0.0),
                "source_reason": _clean(row.get("monitor_reason")),
            }
        )
    return rows


def _dedupe_intents(intents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    close_grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    open_grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    passthrough: list[dict[str, Any]] = []
    for intent in intents:
        vt_symbol = _clean(intent.get("vt_symbol"))
        direction = _normalize_direction_text(intent.get("direction"))
        offset = _normalize_offset_text(intent.get("offset"))
        if offset == "close":
            close_grouped.setdefault((vt_symbol, direction, offset), []).append(intent)
        elif offset == "open":
            open_grouped.setdefault((vt_symbol, direction, offset), []).append(intent)
        else:
            passthrough.append(intent)

    def close_priority(row: dict[str, Any]) -> tuple[int, float]:
        source = _clean(row.get("source"))
        source_priority = 0 if source == "stage904_c9_intraday_close" else 1 if source == "stage901_pending_order" else 9
        return source_priority, -_to_float(row.get("planned_volume"), 0.0)

    def open_priority(row: dict[str, Any]) -> tuple[int, float]:
        source = _clean(row.get("source"))
        source_priority = 0 if source == "stage904_c9_intraday_retry_open" else 1 if source == "stage901_pending_order" else 9
        return source_priority, -_to_float(row.get("planned_volume"), 0.0)

    deduped: list[dict[str, Any]] = list(passthrough)
    for rows in close_grouped.values():
        if len(rows) == 1:
            deduped.append(rows[0])
            continue
        ordered = sorted(rows, key=close_priority)
        kept = dict(ordered[0])
        removed = ordered[1:]
        removed_sources = ",".join(_clean(row.get("source")) for row in removed)
        kept["dedupe_removed_count"] = len(removed)
        kept["dedupe_removed_sources"] = removed_sources
        reason = _clean(kept.get("source_reason"))
        suffix = f"deduped_close_intents_removed={len(removed)}:{removed_sources}"
        kept["source_reason"] = f"{reason};{suffix}" if reason else suffix
        deduped.append(kept)
    for rows in open_grouped.values():
        if len(rows) == 1:
            deduped.append(rows[0])
            continue
        ordered = sorted(rows, key=open_priority)
        kept = dict(ordered[0])
        removed = ordered[1:]
        removed_sources = ",".join(_clean(row.get("source")) for row in removed)
        kept["dedupe_removed_count"] = len(removed)
        kept["dedupe_removed_sources"] = removed_sources
        reason = _clean(kept.get("source_reason"))
        suffix = f"deduped_open_intents_removed={len(removed)}:{removed_sources}"
        kept["source_reason"] = f"{reason};{suffix}" if reason else suffix
        deduped.append(kept)
    return deduped


def _validate_intent(
    intent: dict[str, Any],
    *,
    contracts: pd.DataFrame,
    positions: pd.DataFrame,
    orders: pd.DataFrame,
    stage902_summary: dict[str, Any],
    stage260_summary: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    config = build_phase_d_config()
    reasons: list[str] = []
    vt_symbol = _clean(intent.get("vt_symbol"))
    symbol, exchange_value = _split_vt_symbol(vt_symbol)
    direction_text = _normalize_direction_text(intent.get("direction"))
    offset_text = _normalize_offset_text(intent.get("offset"))
    direction = _normalize_direction(direction_text)
    offset = _normalize_offset(offset_text)
    price = _to_float(intent.get("limit_price"), 0.0)
    volume = _to_float(intent.get("planned_volume"), 0.0)
    contract = _contract_row(contracts, vt_symbol)
    active_orders = _active_order_count(orders)
    unknown_orders = _unknown_order_status_count(orders)
    stage902_blocking = int(_to_float(stage902_summary.get("blocking_failure_count"), 999))
    stage902_reduce_close_blocking = int(
        _to_float(stage902_summary.get("blocking_failure_count_for_reduce_close"), stage902_blocking)
    )
    stage902_allow_new_open = int(_to_float(stage902_summary.get("allow_new_open"), 0))
    stage902_allow_reduce_close = int(_to_float(stage902_summary.get("allow_reduce_close"), 0))
    stage260_executable = int(_to_float(stage260_summary.get("executable_count"), 0))
    source = _clean(intent.get("source"))
    intraday_close_intent = source == "stage904_c9_intraday_close" and offset_text == "close"
    intraday_retry_open_intent = source == "stage904_c9_intraday_retry_open" and offset_text == "open"
    force_skip_reason = _clean(intent.get("force_skip_reason"))

    if force_skip_reason:
        reasons.append(force_skip_reason)
    stage902_blocking_for_intent = stage902_reduce_close_blocking if offset_text == "close" else stage902_blocking
    if stage902_blocking_for_intent > 0 and not intraday_close_intent:
        reasons.append(f"stage902_blocking_failure_count={stage902_blocking_for_intent}")
    if mode != "dry-run":
        reasons.append("stage905_never_submits_live_orders")
    if active_orders > config.hard_limits.max_open_order_count:
        reasons.append(f"active_order_count={active_orders}")
    if unknown_orders > 0:
        reasons.append(f"unknown_order_status_count={unknown_orders}")
    if not symbol or not exchange_value:
        reasons.append("invalid_vt_symbol")
    if direction is None:
        reasons.append("invalid_direction")
    if offset is None:
        reasons.append("invalid_offset")
    if contract is None:
        reasons.append("contract_not_found")
    if volume <= 0:
        reasons.append("invalid_volume")
    if volume > config.hard_limits.max_single_order_volume:
        reasons.append(f"volume_above_phase_d_limit:{volume}>{config.hard_limits.max_single_order_volume}")
    if not float(volume).is_integer():
        reasons.append("volume_not_integer_lots")
    if price <= 0:
        reasons.append("invalid_price")

    pricetick = _to_float(contract.get("pricetick") if contract else None, 0.0)
    min_volume = _to_float(contract.get("min_volume") if contract else None, 0.0)
    max_volume = _to_float(contract.get("max_volume") if contract else None, 0.0)
    price_adjustment_reason = ""
    if intraday_close_intent:
        original_price = price
        price, price_adjustment_reason = _protective_close_price(intent, direction_text, pricetick, original_price)
        if price <= 0:
            reasons.append("protective_close_price_missing")
        elif original_price > 0:
            price_adjustment_reason = f"{price_adjustment_reason};stop_trigger_price={original_price};order_price={price}"
    if pricetick and price > 0 and not _price_on_tick(price, pricetick):
        original_price = price
        price = _snap_price_to_tick(price, pricetick, direction_text)
        snap_reason = f"limit_price_snapped_to_tick:{original_price}->{price}"
        price_adjustment_reason = f"{price_adjustment_reason};{snap_reason}" if price_adjustment_reason else snap_reason
    if pricetick and not _price_on_tick(price, pricetick):
        reasons.append("price_not_on_tick")
    if min_volume and volume < min_volume:
        reasons.append("volume_below_min")
    if max_volume and volume > max_volume:
        reasons.append("volume_above_contract_max")
    broker_match_volume = 0.0
    if offset_text == "close":
        if stage902_allow_reduce_close != 1:
            reasons.append("stage902_reduce_close_not_allowed")
        broker_match_direction = _opposite_position_direction(direction_text)
        broker_match_volume = _position_volume(positions, vt_symbol, broker_match_direction)
        if broker_match_volume <= 0:
            reasons.append(f"no_matching_{broker_match_direction}_broker_position_to_close")
        elif broker_match_volume < volume:
            reasons.append(f"insufficient_broker_position:{broker_match_volume}<{volume}")
        if stage260_executable <= 0 and not intraday_close_intent:
            reasons.append("stage260_no_executable_close_gate")
    elif offset_text == "open":
        if stage902_allow_new_open != 1:
            reasons.append("stage902_new_open_not_allowed")
        broker_match_volume = _position_gross_volume(positions, vt_symbol, direction_text)
        if broker_match_volume > 0:
            reasons.append(f"same_direction_broker_position_exists_for_open:{broker_match_volume}")
        if stage260_executable <= 0 and not intraday_retry_open_intent:
            reasons.append("stage260_no_executable_open_gate")

    order_request_payload: dict[str, Any] = {}
    skip_existing_stage901_open = (
        source == "stage901_pending_order"
        and offset_text == "open"
        and volume > 0
        and broker_match_volume >= volume
    )
    if skip_existing_stage901_open:
        status = "skipped_existing_broker_position"
        reasons = [f"stage901_open_already_present_in_broker_position:{broker_match_volume}"]
    elif force_skip_reason:
        status = f"skipped_{force_skip_reason}"
        reasons = [force_skip_reason]
    else:
        status = "blocked" if reasons else "dry_run_order_request_payload_ready"
    if not reasons and direction and offset:
        req = OrderRequest(
            symbol=symbol,
            exchange=Exchange(exchange_value),
            direction=direction,
            type=OrderType.LIMIT,
            volume=volume,
            price=price,
            offset=offset,
            reference=f"Stage905PhaseD:{intent.get('intent_id')}",
        )
        order_request_payload = {
            "symbol": req.symbol,
            "exchange": req.exchange.value,
            "direction": req.direction.value,
            "type": req.type.value,
            "volume": req.volume,
            "price": req.price,
            "offset": req.offset.value,
            "reference": req.reference,
            "vt_symbol": req.vt_symbol,
            "gateway_name": _clean(contract.get("gateway_name") if contract else "CTP") or "CTP",
        }

    return {
        **intent,
        "executor_mode": mode,
        "executor_status": status,
        "executor_reason": ";".join(dict.fromkeys(reasons)),
        "symbol": symbol,
        "exchange": exchange_value,
        "pricetick": pricetick,
        "price_adjustment_reason": price_adjustment_reason,
        "broker_matching_position_volume": broker_match_volume,
        "active_order_count": active_orders,
        "order_request_json": json.dumps(order_request_payload, ensure_ascii=False, sort_keys=True),
        "send_order_api_called": 0,
        "cancel_order_api_called": 0,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _to_markdown(df: pd.DataFrame, columns: list[str], max_rows: int = 80) -> str:
    if df.empty:
        return "_empty_"
    return df.loc[:, [column for column in columns if column in df.columns]].head(max_rows).to_markdown(index=False)


def _build_report(summary: dict[str, Any], intents: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Stage905 Official Live Executor Dry Run",
            "",
            f"- 生成时间：`{summary['generated_at']}`",
            f"- 当前官方实盘：`{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- 目标日期：`{summary['target_date']}`",
            f"- executor 状态：`{summary['executor_status']}`",
            f"- intent 数：`{summary['intent_count']}`",
            f"- ready 数：`{summary['ready_count']}`",
            f"- blocked 数：`{summary['blocked_count']}`",
            f"- skipped 数：`{summary.get('skipped_count', 0)}`",
            f"- send_order 调用次数：`{summary['send_order_api_called_count']}`",
            f"- cancel_order 调用次数：`{summary['cancel_order_api_called_count']}`",
            "",
            "## Intents",
            "",
            _to_markdown(
                intents,
                [
                    "intent_id",
                    "source",
                    "vt_symbol",
                    "direction",
                    "offset",
                    "planned_volume",
                    "limit_price",
                    "stop_trigger_price",
                    "trigger_live_price",
                    "trigger_adverse_extreme_price",
                    "retry_trigger_price",
                    "retry_stop_price",
                    "trigger_progress_extreme_price",
                    "price_adjustment_reason",
                    "dedupe_removed_count",
                    "dedupe_removed_sources",
                    "executor_status",
                    "executor_reason",
                ],
            ),
            "",
            "## 说明",
            "",
            "- Stage905 只生成 dry-run `OrderRequest` payload，不连接 CTP，不调用 `send_order` 或 `cancel_order`。",
            "- 平仓必须有 broker 持仓快照；普通日线开仓必须有 Stage260 executable gate。",
            "- C9 止损后一次重试开仓来自 Stage904，必须先通过 ledger/空仓/fresh tick 闭环，不能由人工影子持仓替代。",
            "- 合约快照、持仓快照、活跃委托、Stage902、Stage260 任一缺失都必须 fail-closed。",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live Phase D executor dry-run.")
    parser.add_argument("--target-date", required=True)
    parser.add_argument("--mode", choices=["dry-run"], default="dry-run")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(args.target_date)
    pending_orders = _read_csv_maybe(STAGE901_PENDING_ORDERS_PATH)
    stage904_actions = _read_csv_maybe(_stage904_actions_path(args.target_date))
    contracts = _read_csv_maybe(READONLY_CONTRACTS_PATH)
    positions = _read_csv_maybe(READONLY_POSITIONS_PATH)
    orders = _read_csv_maybe(READONLY_ORDERS_PATH)
    stage902_summary = _read_json(_stage902_summary_path(args.target_date))
    stage260_summary = _read_json(_stage260_summary_path(args.target_date))
    execution_ledger_rows = read_execution_ledger()

    pending_intents = _suppress_stage901_pending_after_stop_close(
        _pending_order_intents(pending_orders),
        ledger_rows=execution_ledger_rows,
        target_date=args.target_date,
    )
    raw_intents = _dedupe_intents(pending_intents + _stage904_intents(stage904_actions))
    intents = pd.DataFrame(
        [
            _validate_intent(
                row,
                contracts=contracts,
                positions=positions,
                orders=orders,
                stage902_summary=stage902_summary,
                stage260_summary=stage260_summary,
                mode=args.mode,
            )
            for row in raw_intents
        ]
    )
    ready_count = int(intents.get("executor_status", pd.Series(dtype=str)).astype(str).eq("dry_run_order_request_payload_ready").sum()) if not intents.empty else 0
    blocked_count = int(intents.get("executor_status", pd.Series(dtype=str)).astype(str).eq("blocked").sum()) if not intents.empty else 0
    skipped_count = int(intents.get("executor_status", pd.Series(dtype=str)).astype(str).str.startswith("skipped_").sum()) if not intents.empty else 0
    send_count = int(intents.get("send_order_api_called", pd.Series(dtype=float)).sum()) if not intents.empty else 0
    cancel_count = int(intents.get("cancel_order_api_called", pd.Series(dtype=float)).sum()) if not intents.empty else 0
    if intents.empty:
        executor_status = "executor_no_intents"
    elif ready_count and not blocked_count:
        executor_status = "executor_dry_run_ready"
    elif blocked_count:
        executor_status = "executor_dry_run_blocked"
    else:
        executor_status = "executor_no_ready_intents"

    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_date": args.target_date,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "executor_status": executor_status,
        "intent_count": int(len(intents)),
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "skipped_count": skipped_count,
        "send_order_api_called_count": send_count,
        "cancel_order_api_called_count": cancel_count,
        "stage902_overall_status": stage902_summary.get("overall_status", ""),
        "stage260_executable_count": stage260_summary.get("executable_count", 0),
        "execution_ledger_rows": int(len(execution_ledger_rows)),
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。executor dry-run 是执行层，不改信号或策略参数。",
            "continue_before": "是。全自动必须能把信号变成可审计 OrderRequest，并在缺少 broker 证据时阻断。",
            "overfit_after": "否。没有根据 executor 结果调整策略。",
            "continue_after": "是。下一步应把 Stage905 接入 Stage903，并补 broker read-only/Stage260 fresh 自动刷新。",
        },
    }
    intents.to_csv(paths["intents_csv"], index=False, encoding="utf-8-sig")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, intents), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
