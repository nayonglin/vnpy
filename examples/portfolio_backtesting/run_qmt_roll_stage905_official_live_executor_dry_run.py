from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd
from pandas.errors import EmptyDataError

from qmt_roll_official_execution_profile import (
    C9_15W_PROFILE,
    ExecutionStrategyMode,
    OfficialExecutionProfile,
    assert_intent_source_allowed,
    assert_profile_identity,
    resolve_execution_profile,
)
from qmt_roll_official_live_c9_intraday_state import (
    INITIAL_STOP_ACTION_ROLE,
    RETRY_OPEN_ACTION_ROLE,
    RETRY_STOP_ACTION_ROLE,
    generate_position_cycle_id,
    generate_position_epoch_id,
    generate_root_position_id,
)
from qmt_roll_official_live_execution_ledger import read_execution_ledger
from qmt_roll_official_live_phase_d_config import (
    READONLY_CONTRACTS_PATH,
    READONLY_ORDERS_PATH,
    READONLY_POSITIONS_PATH,
    build_phase_d_config,
)
from run_qmt_alignment_backtest import OUTPUT_DIR
from qmt_roll_official_live_time import Clock, SystemClock
from qmt_roll_official_live_trace import (
    ClockStamp,
    LatencyTrace,
    TraceValidationError,
    disposition_for_trace,
)
from vnpy.trader.constant import Direction, Exchange, Offset, OrderType
from vnpy.trader.object import OrderRequest


MODEL_TAG = "stage905_official_live_executor_dry_run_v1"
OUTPUT_PREFIX = "qmt_roll_stage905_official_live_executor_dry_run"
STAGE902_MODEL_TAG = "stage902_official_live_phase_d_readiness_gate_v1"
STAGE902_PREFIX = "qmt_roll_stage902_official_live_phase_d_readiness_gate"
STAGE904_MODEL_TAG = "stage904_official_live_c9_intraday_monitor_v1"
STAGE904_PREFIX = "qmt_roll_stage904_official_live_c9_intraday_monitor"
STAGE904_MAX_AGE_SECONDS = 30
STAGE260_MODEL_TAG = "stage260_official_live_daily_execution_gate_v1"
STAGE260_PREFIX = "qmt_roll_stage260_official_live_daily_execution_gate"
RETRY_INTENT_ROLE = "c9_retry_open_once"
INITIAL_OPEN_INTENT_ROLE = "c9_initial_open"
IDENTITY_TEXT_FIELDS = (
    "root_position_id",
    "position_cycle_id",
    "position_epoch_id",
    "parent_position_cycle_id",
    "intent_role",
    "position_direction",
    "entry_risk_date",
    "open_trade_id",
    "action_id",
)
IDENTITY_NUMBER_FIELDS = (
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
STAGE904_MIGRATION_AUDIT_FIELDS = (
    "manual_intervention_required",
    "risk_alert_level",
    "migration_blocker",
    "recommended_operator_action",
)
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
STAGE904_PROVENANCE_FIELDS = (
    "trace_json",
    "trace_id",
    "source_feed_session_id",
    "source_ingress_sequence",
    "source_symbol_sequence",
    "ingress_epoch_ns",
    "ingress_monotonic_ns",
    "deadline_epoch_ns",
    "deadline_monotonic_ns",
    "durable_cursor_feed_session_id",
    "durable_cursor_ingress_sequence",
    "durable_cursor_journal_byte_offset",
    "durable_cursor_journal_schema",
    "state_generation",
)
STAGE904_EXACT_INT_FIELDS = (
    "source_ingress_sequence",
    "source_symbol_sequence",
    "ingress_epoch_ns",
    "ingress_monotonic_ns",
    "deadline_epoch_ns",
    "deadline_monotonic_ns",
    "durable_cursor_ingress_sequence",
    "durable_cursor_journal_byte_offset",
)
_VOLATILE_INTENT_HASH_FIELDS = {
    "monitor_run_id",
    "generated_at",
    "checked_at",
    "stage904_summary_generated_at",
    "payload_sha256",
    "spool_payload_json",
    "trace_json",
}
SYSTEM_CLOCK = SystemClock()


@dataclass(frozen=True)
class Stage905SnapshotInputs:
    pending_orders: pd.DataFrame
    contracts: pd.DataFrame
    positions: pd.DataFrame
    orders: pd.DataFrame
    stage902_summary: Mapping[str, Any]
    stage260_summary: Mapping[str, Any]
    execution_ledger_rows: Sequence[Mapping[str, Any]]


@dataclass(frozen=True)
class Stage905RunResult:
    intents: pd.DataFrame
    summary: dict[str, Any]
    paths: Mapping[str, Path]


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


def _stage904_summary_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE904_PREFIX}_summary_{date_key}_{STAGE904_MODEL_TAG}.json"


def _stage260_summary_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE260_PREFIX}_summary_{date_key}_{STAGE260_MODEL_TAG}.json"


def _stage260_decisions_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE260_PREFIX}_decisions_{date_key}_{STAGE260_MODEL_TAG}.csv"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _age_seconds(value: Any, *, now_epoch_ns: int | None = None) -> float | None:
    text = _clean(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if now_epoch_ns is None:
        now = datetime.now(parsed.tzinfo) if parsed.tzinfo is not None else datetime.now()
    else:
        now = datetime.fromtimestamp(now_epoch_ns / 1_000_000_000, tz=parsed.tzinfo)
    return max(0.0, (now - parsed).total_seconds())


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


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _atomic_write_df(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    frame.to_csv(temporary, index=False, encoding="utf-8-sig")
    os.replace(temporary, path)


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


def _canonical_binary_flag(value: Any) -> tuple[bool, int]:
    """Accept only numeric 0/1; never coerce strings or bools into authority."""

    if value is None or pd.api.types.is_bool(value) or isinstance(value, str):
        return False, 0
    try:
        if bool(pd.isna(value)):
            return False, 0
        number = float(value)
    except (TypeError, ValueError):
        return False, 0
    if not math.isfinite(number) or number not in {0.0, 1.0}:
        return False, 0
    return True, int(number)


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


def _pending_order_intents(pending_orders: pd.DataFrame, target_date: str = "") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(pending_orders.to_dict(orient="records"), start=1):
        vt_symbol = _clean(row.get("vt_symbol"))
        direction = _normalize_direction_text(row.get("direction"))
        offset = _normalize_offset_text(row.get("offset"))
        item = {
                "intent_id": f"STAGE905-PENDING-{idx:03d}",
                "target_date": target_date,
                "source": "stage901_pending_order",
                "vt_symbol": vt_symbol,
                "direction": direction,
                "offset": offset,
                "planned_volume": _to_float(row.get("volume"), 0.0),
                "limit_price": _to_float(row.get("price"), 0.0),
                "source_reason": _clean(row.get("status")),
            }
        if target_date and vt_symbol and direction in {"long", "short"} and offset == "open":
            root_position_id = generate_root_position_id(
                target_date=target_date,
                vt_symbol=vt_symbol,
                direction=direction,
            )
            planned_epoch_id = ""
            planned_entry_at = _clean(row.get("datetime") or row.get("generated_at"))
            planned_fill_identity = _clean(
                row.get("vt_orderid") or row.get("orderid") or row.get("intent_id")
            )
            if planned_entry_at and planned_fill_identity:
                planned_epoch_id = generate_position_epoch_id(
                    target_date=target_date,
                    vt_symbol=vt_symbol,
                    direction=direction,
                    entry_filled_at=planned_entry_at,
                    fill_identity=f"stage901_pending:{planned_fill_identity}",
                )
            item.update(
                {
                    "root_position_id": root_position_id,
                    "position_cycle_id": generate_position_cycle_id(root_position_id=root_position_id, cycle_no=0),
                    "position_cycle_no": 0,
                    "intent_role": INITIAL_OPEN_INTENT_ROLE,
                    "position_direction": direction,
                    "strategy_entry_price": _to_float(row.get("price"), 0.0),
                    "strategy_initial_stop_price": _to_float(row.get("stop_price"), 0.0),
                    "root_entry_price": _to_float(row.get("price"), 0.0),
                    "root_initial_stop_price": _to_float(row.get("stop_price"), 0.0),
                    "root_entry_volume": _to_float(row.get("volume"), 0.0),
                }
            )
            if planned_epoch_id:
                item["position_epoch_id"] = planned_epoch_id
        rows.append(item)
    return rows


def _stage260_daily_intents(
    decisions: pd.DataFrame,
    *,
    summary: Mapping[str, Any],
    profile: OfficialExecutionProfile,
    target_date: str,
) -> list[dict[str, Any]]:
    if profile.intraday_stop_retry_enabled:
        return []
    if _clean(summary.get("execution_profile")) != profile.profile_key:
        raise ValueError("stage260_execution_profile_mismatch")
    if _clean(summary.get("trade_date")) != target_date:
        raise ValueError("stage260_summary_target_date_mismatch")
    pending_cohort_id = _clean(summary.get("pending_cohort_id"))
    if (
        len(pending_cohort_id) != 64
        or any(
            character not in "0123456789abcdef"
            for character in pending_cohort_id
        )
    ):
        raise ValueError("stage260_summary_pending_cohort_invalid")
    assert_profile_identity(
        profile,
        official_version=summary.get("official_live_version"),
        capital=_to_float(summary.get("capital"), 0.0),
        capital_label=summary.get("capital_label"),
    )
    if int(_to_float(summary.get("order_api_called_count"), -1.0)) != 0:
        raise ValueError("stage260_order_api_count_nonzero")
    executable = decisions[
        decisions.get(
            "execution_action",
            pd.Series([""] * len(decisions), index=decisions.index),
        )
        .fillna("")
        .astype(str)
        .eq("simnow_executable")
    ]
    declared_executable = int(_to_float(summary.get("executable_count"), -1.0))
    if declared_executable != len(executable):
        raise ValueError(
            "stage260_executable_count_mismatch:"
            f"{declared_executable}!={len(executable)}"
        )
    rows: list[dict[str, Any]] = []
    for raw in executable.to_dict(orient="records"):
        if _clean(raw.get("execution_profile")) != profile.profile_key:
            raise ValueError("stage260_decision_execution_profile_mismatch")
        assert_profile_identity(
            profile,
            official_version=raw.get("official_live_version"),
            capital=_to_float(raw.get("capital"), 0.0),
            capital_label=raw.get("capital_label"),
        )
        source = _clean(raw.get("intent_source"))
        assert_intent_source_allowed(profile, source)
        decision_id = _clean(raw.get("decision_id"))
        if (
            len(decision_id) != 64
            or any(character not in "0123456789abcdef" for character in decision_id)
        ):
            raise ValueError("stage260_decision_id_invalid")
        row_target_date = _clean(raw.get("trade_date"))
        if row_target_date != target_date:
            raise ValueError("stage260_decision_target_date_mismatch")
        if _clean(raw.get("pending_cohort_id")) != pending_cohort_id:
            raise ValueError("stage260_decision_pending_cohort_mismatch")
        rows.append(
            {
                "intent_id": f"STAGE905-STAGE260-{decision_id}",
                "decision_id": decision_id,
                "target_date": target_date,
                "source": source,
                "execution_profile": profile.profile_key,
                "official_live_version": profile.official_version,
                "capital": profile.capital,
                "capital_label": profile.capital_label,
                "pending_cohort_id": pending_cohort_id,
                "vt_symbol": _clean(raw.get("vt_symbol")),
                "direction": _normalize_direction_text(raw.get("direction")),
                "offset": _normalize_offset_text(raw.get("offset")),
                "planned_volume": _to_float(raw.get("planned_volume"), 0.0),
                "limit_price": _to_float(raw.get("theoretical_price"), 0.0),
                "source_reason": _clean(raw.get("execution_reason")),
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


def _copy_stage904_provenance(
    intent: dict[str, Any],
    action: Mapping[str, Any],
) -> None:
    for field_name in STAGE904_PROVENANCE_FIELDS:
        value = action.get(field_name)
        if value is not None and not (isinstance(value, float) and math.isnan(value)):
            intent[field_name] = value


def _stable_payload_sha256(intent: Mapping[str, Any]) -> str:
    payload: dict[str, Any] = {}
    for key in sorted(intent):
        if (
            key in _VOLATILE_INTENT_HASH_FIELDS
            or key.endswith("_generated_at")
            or key.endswith("_checked_at")
        ):
            continue
        value = intent[key]
        if isinstance(value, float) and math.isnan(value):
            value = None
        elif hasattr(value, "item") and not isinstance(value, (str, bytes, bytearray)):
            try:
                value = value.item()
            except (AttributeError, ValueError):
                pass
        payload[key] = value
    encoded = json.dumps(
        _canonical_spool_json_value(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_spool_json_value(value: Any, *, field_name: str = "payload") -> Any:
    """Return strict JSON data without lossy ``default=str`` coercion."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if type(value) is int:
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return None
        if not math.isfinite(value):
            raise ValueError(f"{field_name}_must_be_finite")
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{field_name}_key_must_be_text")
            normalized[key] = _canonical_spool_json_value(
                item,
                field_name=f"{field_name}.{key}",
            )
        return normalized
    if isinstance(value, (list, tuple)):
        return [
            _canonical_spool_json_value(item, field_name=f"{field_name}[]")
            for item in value
        ]
    if hasattr(value, "item"):
        try:
            scalar = value.item()
        except AttributeError:
            scalar = value
        if scalar is not value:
            return _canonical_spool_json_value(scalar, field_name=field_name)
    raise ValueError(f"{field_name}_json_type_unsupported:{type(value).__name__}")


def _stage904_intents(stage904_actions: pd.DataFrame) -> list[dict[str, Any]]:
    if stage904_actions.empty or "monitor_action" not in stage904_actions.columns:
        return []
    rows: list[dict[str, Any]] = []
    close_actions = stage904_actions[stage904_actions["monitor_action"].astype(str).eq("close_dry_run")]
    for idx, row in enumerate(close_actions.to_dict(orient="records"), start=1):
        current_direction = _normalize_direction_text(row.get("direction"))
        close_direction = "short" if current_direction == "long" else "long" if current_direction == "short" else ""
        intent = {
                "intent_id": _clean(row.get("action_id")),
                "target_date": _clean(row.get("target_date")),
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
                "monitor_run_id": _clean(row.get("monitor_run_id")),
                "source_reason": _clean(row.get("monitor_reason")),
            }
        for key in IDENTITY_TEXT_FIELDS:
            value = _clean(row.get(key))
            if value:
                intent[key] = value
        for key in IDENTITY_NUMBER_FIELDS:
            if _clean(row.get(key)):
                intent[key] = _to_float(row.get(key), 0.0)
        for key in STAGE904_MIGRATION_AUDIT_FIELDS:
            value = row.get(key)
            if key == "manual_intervention_required":
                valid, normalized = _canonical_binary_flag(value)
                intent[key] = normalized if valid else value
            elif _clean(value):
                intent[key] = _clean(value)
        _copy_stage904_provenance(intent, row)
        rows.append(intent)
    retry_actions = stage904_actions[stage904_actions["monitor_action"].astype(str).eq("retry_open_dry_run")]
    for idx, row in enumerate(retry_actions.to_dict(orient="records"), start=1):
        intent = {
                "intent_id": _clean(row.get("action_id")),
                "target_date": _clean(row.get("target_date")),
                "source": "stage904_c9_intraday_retry_open",
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
                "monitor_run_id": _clean(row.get("monitor_run_id")),
                "source_reason": _clean(row.get("monitor_reason")),
            }
        for key in IDENTITY_TEXT_FIELDS:
            value = _clean(row.get(key))
            if value:
                intent[key] = value
        for key in IDENTITY_NUMBER_FIELDS:
            if _clean(row.get(key)):
                intent[key] = _to_float(row.get(key), 0.0)
        for key in STAGE904_MIGRATION_AUDIT_FIELDS:
            value = row.get(key)
            if key == "manual_intervention_required":
                valid, normalized = _canonical_binary_flag(value)
                intent[key] = normalized if valid else value
            elif _clean(value):
                intent[key] = _clean(value)
        _copy_stage904_provenance(intent, row)
        rows.append(intent)
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

    def close_priority(row: dict[str, Any]) -> tuple[int, float, float]:
        source = _clean(row.get("source"))
        source_priority = 0 if source == "stage904_c9_intraday_close" else 1 if source == "stage901_pending_order" else 9
        return source_priority, -_to_float(row.get("position_cycle_no"), -1.0), -_to_float(row.get("planned_volume"), 0.0)

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


def _required_exact_int(value: Any, *, field_name: str, minimum: int = 0) -> int:
    if hasattr(value, "item") and not isinstance(value, (str, bytes, bytearray)):
        try:
            value = value.item()
        except (AttributeError, ValueError):
            pass
    if type(value) is not int or value < minimum:
        raise TraceValidationError(f"{field_name}_must_be_exact_int_at_least_{minimum}")
    return value


def _stage904_batch_summary_blockers(
    actions: pd.DataFrame,
    summary: Mapping[str, Any],
) -> tuple[str, ...]:
    blockers: list[str] = []
    monitor_actions = (
        actions.get("monitor_action", pd.Series(dtype=str)).astype(str)
        if not actions.empty
        else pd.Series(dtype=str)
    )
    expected_counts = {
        "action_count": int(len(actions)),
        "close_dry_run_count": int(monitor_actions.eq("close_dry_run").sum()),
        "retry_open_dry_run_count": int(
            monitor_actions.eq("retry_open_dry_run").sum()
        ),
        "retry_watch_count": int(monitor_actions.eq("retry_watch").sum()),
        "blocked_count": int(monitor_actions.isin(["block", "retry_block"]).sum()),
        "order_api_called_count": int(
            pd.to_numeric(
                actions.get("order_api_called", pd.Series(dtype=int)),
                errors="coerce",
            ).fillna(0).sum()
        ),
    }
    for field_name, expected in expected_counts.items():
        try:
            actual = _required_exact_int(summary.get(field_name), field_name=field_name)
        except TraceValidationError as exc:
            blockers.append(f"stage904_summary_count_invalid:{exc}")
            continue
        if actual != expected:
            blockers.append(
                f"stage904_summary_count_mismatch:{field_name}:"
                f"expected={expected};actual={actual}"
            )
    summary_cursor = summary.get("durable_batch_cursor")
    if not isinstance(summary_cursor, Mapping):
        blockers.append("stage904_summary_durable_batch_cursor_missing")
    elif summary_cursor:
        expected_cursor_fields = {
            "feed_session_id",
            "ingress_sequence",
            "journal_byte_offset",
            "journal_schema",
        }
        if set(summary_cursor) != expected_cursor_fields:
            blockers.append("stage904_summary_durable_batch_cursor_fields_invalid")
        else:
            try:
                _required_exact_int(
                    summary_cursor.get("ingress_sequence"),
                    field_name="summary_durable_cursor_ingress_sequence",
                    minimum=1,
                )
                _required_exact_int(
                    summary_cursor.get("journal_byte_offset"),
                    field_name="summary_durable_cursor_journal_byte_offset",
                )
            except TraceValidationError as exc:
                blockers.append(f"stage904_summary_durable_batch_cursor_invalid:{exc}")
            if not _clean(summary_cursor.get("feed_session_id")):
                blockers.append("stage904_summary_durable_batch_cursor_feed_missing")
            if _clean(summary_cursor.get("journal_schema")) != "stage179_framed_v1":
                blockers.append("stage904_summary_durable_batch_cursor_schema_invalid")
    elif not actions.empty:
        blockers.append("stage904_summary_durable_batch_cursor_empty_with_actions")
    return tuple(blockers)


def _validated_stage904_trace(
    intent: Mapping[str, Any],
    *,
    stage904_summary: Mapping[str, Any] | None = None,
) -> LatencyTrace:
    trace = LatencyTrace.from_json(_clean(intent.get("trace_json")))
    ingress = trace.stamps["gateway_ingress"]
    expected_values = {
        "trace_id": trace.trace_id,
        "source_feed_session_id": trace.feed_session_id,
        "source_ingress_sequence": trace.ingress_sequence,
        "source_symbol_sequence": trace.symbol_sequence,
        "ingress_epoch_ns": ingress.epoch_ns,
        "ingress_monotonic_ns": ingress.monotonic_ns,
        "deadline_epoch_ns": trace.deadline_epoch_ns,
        "deadline_monotonic_ns": trace.deadline_monotonic_ns,
    }
    for field_name, expected in expected_values.items():
        actual = intent.get(field_name)
        if isinstance(expected, int):
            actual = _required_exact_int(actual, field_name=field_name)
        else:
            actual = _clean(actual)
        if actual != expected:
            raise TraceValidationError(
                f"stage904_trace_outer_mismatch:{field_name}:"
                f"expected={expected};actual={actual}"
            )
    if _clean(intent.get("vt_symbol")) != trace.vt_symbol:
        raise TraceValidationError("stage904_trace_outer_mismatch:vt_symbol")
    durable_feed = _clean(intent.get("durable_cursor_feed_session_id"))
    durable_sequence = _required_exact_int(
        intent.get("durable_cursor_ingress_sequence"),
        field_name="durable_cursor_ingress_sequence",
        minimum=1,
    )
    durable_offset = _required_exact_int(
        intent.get("durable_cursor_journal_byte_offset"),
        field_name="durable_cursor_journal_byte_offset",
    )
    if durable_feed != trace.feed_session_id or durable_sequence < trace.ingress_sequence:
        raise TraceValidationError("stage904_durable_cursor_does_not_cover_trigger")
    if _clean(intent.get("durable_cursor_journal_schema")) != "stage179_framed_v1":
        raise TraceValidationError("stage904_durable_cursor_schema_invalid")
    position_epoch_id = _clean(intent.get("position_epoch_id"))
    state_generation = _clean(intent.get("state_generation"))
    generation_prefix = f"{position_epoch_id}:"
    generation_revision = (
        state_generation[len(generation_prefix) :]
        if position_epoch_id and state_generation.startswith(generation_prefix)
        else ""
    )
    if (
        not generation_revision.isdecimal()
        or str(int(generation_revision)) != generation_revision
    ):
        raise TraceValidationError("stage904_state_generation_invalid")
    if stage904_summary is not None:
        summary_cursor = stage904_summary.get("durable_batch_cursor")
        if not isinstance(summary_cursor, Mapping):
            raise TraceValidationError("stage904_summary_durable_batch_cursor_missing")
        summary_feed = _clean(summary_cursor.get("feed_session_id"))
        summary_schema = _clean(summary_cursor.get("journal_schema"))
        summary_sequence = _required_exact_int(
            summary_cursor.get("ingress_sequence"),
            field_name="summary_durable_cursor_ingress_sequence",
            minimum=1,
        )
        summary_offset = _required_exact_int(
            summary_cursor.get("journal_byte_offset"),
            field_name="summary_durable_cursor_journal_byte_offset",
        )
        if summary_feed != durable_feed or summary_schema != "stage179_framed_v1":
            raise TraceValidationError("stage904_summary_durable_cursor_identity_mismatch")
        if summary_sequence < durable_sequence or summary_offset < durable_offset:
            raise TraceValidationError("stage904_summary_durable_cursor_does_not_cover_action")
    return trace


def _stable_reason_codes(reasons: Sequence[str]) -> tuple[str, ...]:
    codes: set[str] = set()
    for reason in reasons:
        code = reason.split(":", 1)[0].split("=", 1)[0].strip()
        if code:
            codes.add(code)
    return tuple(sorted(codes))


def _validate_intent(
    intent: dict[str, Any],
    *,
    contracts: pd.DataFrame,
    positions: pd.DataFrame,
    orders: pd.DataFrame,
    stage902_summary: dict[str, Any],
    stage904_summary: dict[str, Any],
    stage260_summary: dict[str, Any],
    mode: str,
    clock: Clock = SYSTEM_CLOCK,
    require_stage904_trace: bool = False,
    now_stamp: ClockStamp | None = None,
    stage904_batch_blockers: Sequence[str] = (),
) -> dict[str, Any]:
    config = build_phase_d_config()
    reasons: list[str] = []
    vt_symbol = _clean(intent.get("vt_symbol"))
    symbol, exchange_value = _split_vt_symbol(vt_symbol)
    exchange: Exchange | None = None
    if exchange_value:
        try:
            exchange = Exchange(exchange_value)
        except ValueError:
            reasons.append(f"invalid_exchange:{exchange_value}")
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
    manual_flag_valid, manual_flag = _canonical_binary_flag(
        intent.get("manual_intervention_required")
    )
    manual_migration_blocked = bool(
        (manual_flag_valid and manual_flag == 1)
        or _clean(intent.get("migration_blocker"))
        or _clean(intent.get("risk_alert_level")).upper() in {"P0", "P1"}
    )
    current_stamp = now_stamp if now_stamp is not None else ClockStamp.from_clock(clock)
    deadline_status = ""

    root_position_id = _clean(intent.get("root_position_id"))
    position_cycle_id = _clean(intent.get("position_cycle_id"))
    intent_role = _clean(intent.get("intent_role"))
    if root_position_id or position_cycle_id:
        missing_identity = [
            key
            for key, value in (
                ("root_position_id", root_position_id),
                ("position_cycle_id", position_cycle_id),
                ("intent_role", intent_role),
            )
            if not value
        ]
        if missing_identity:
            reasons.append(f"incomplete_v2_intent_identity:missing={','.join(missing_identity)}")
    if (intraday_close_intent or intraday_retry_open_intent) and not _clean(intent.get("position_epoch_id")):
        reasons.append("stage904_position_epoch_id_missing")
    if intraday_close_intent or intraday_retry_open_intent:
        reasons.extend(stage904_batch_blockers)
        if not _clean(intent.get("intent_id")) or not _clean(intent.get("action_id")):
            reasons.append("stage904_action_id_missing")
        if intraday_retry_open_intent and intent_role != RETRY_OPEN_ACTION_ROLE:
            reasons.append("stage904_retry_open_intent_role_mismatch")
        if intraday_close_intent and intent_role not in {
            INITIAL_STOP_ACTION_ROLE,
            RETRY_STOP_ACTION_ROLE,
        }:
            reasons.append("stage904_close_intent_role_mismatch")
    if intraday_retry_open_intent and not manual_flag_valid:
        reasons.append("stage904_manual_intervention_required_invalid")
    if intraday_close_intent or intraday_retry_open_intent:
        stage904_age = _age_seconds(
            stage904_summary.get("generated_at"),
            now_epoch_ns=current_stamp.epoch_ns,
        )
        stage904_run_id = _clean(
            stage904_summary.get("monitor_run_id") or stage904_summary.get("run_id")
        )
        intent_run_id = _clean(intent.get("monitor_run_id"))
        monitor_status = _clean(stage904_summary.get("monitor_status"))
        if _clean(stage904_summary.get("model_tag")) != STAGE904_MODEL_TAG:
            reasons.append("stage904_summary_model_tag_mismatch")
        if _clean(stage904_summary.get("target_date")) != _clean(intent.get("target_date")):
            reasons.append("stage904_summary_target_date_mismatch")
        if stage904_age is None or stage904_age > STAGE904_MAX_AGE_SECONDS:
            reasons.append(f"stage904_summary_stale_or_missing:{stage904_age}")
        if intraday_retry_open_intent and monitor_status != "intraday_monitor_retry_open_dry_run":
            reasons.append("stage904_summary_not_authoritative_for_retry_open")
        if intraday_close_intent and monitor_status not in {
            "intraday_monitor_close_dry_run",
            "intraday_monitor_blocked",
        }:
            reasons.append("stage904_summary_not_authoritative_for_close")
        if not stage904_run_id or not intent_run_id or stage904_run_id != intent_run_id:
            reasons.append("stage904_monitor_run_id_mismatch")
        if _clean(intent.get("trace_json")):
            try:
                trace = _validated_stage904_trace(
                    intent,
                    stage904_summary=(
                        stage904_summary if require_stage904_trace else None
                    ),
                )
                deadline_status = disposition_for_trace(
                    trace,
                    now=current_stamp,
                    intent_kind=offset_text,
                )
                if "stage904_detected" not in trace.stamps:
                    raise TraceValidationError("stage904_detected_stamp_missing")
                if "stage905_intent_ready" not in trace.stamps:
                    trace = trace.record_stamp(
                        "stage905_intent_ready",
                        current_stamp,
                    )
                intent["trace_json"] = trace.to_json()
            except TraceValidationError as exc:
                reasons.append(f"stage904_trace_invalid:{exc}")
        elif require_stage904_trace:
            reasons.append("stage904_trace_missing")
        if deadline_status == "expired":
            reasons.append("stage179_deadline_expired_open")
        elif deadline_status == "blocked":
            reasons.append("stage179_deadline_expired_close_critical")

    if force_skip_reason:
        reasons.append(force_skip_reason)
    if offset_text == "open" and manual_migration_blocked:
        reasons.append("stage904_manual_migration_blocker")
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
    if intraday_close_intent or intraday_retry_open_intent:
        original_price = price
        price, price_adjustment_reason = _protective_close_price(intent, direction_text, pricetick, original_price)
        if price <= 0:
            reasons.append("protective_intraday_price_missing")
        elif original_price > 0:
            trigger_label = "stop_trigger_price" if intraday_close_intent else "retry_trigger_price"
            price_adjustment_reason = f"{price_adjustment_reason};{trigger_label}={original_price};order_price={price}"
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
    elif deadline_status == "expired":
        status = "expired"
    elif deadline_status == "blocked":
        status = "blocked"
    else:
        status = "blocked" if reasons else "dry_run_order_request_payload_ready"
    if not reasons and direction and offset and exchange:
        req = OrderRequest(
            symbol=symbol,
            exchange=exchange,
            direction=direction,
            type=OrderType.LIMIT,
            volume=volume,
            price=price,
            offset=offset,
            reference=f"Stage905PhaseD:{intent.get('intent_id')}",
        )
        order_request_payload = {
            "intent_id": _clean(intent.get("intent_id")),
            "source": source,
            "target_date": _clean(intent.get("target_date")),
            "execution_profile": _clean(intent.get("execution_profile")),
            "official_live_version": _clean(
                intent.get("official_live_version")
            ),
            "capital": _to_float(intent.get("capital"), 0.0),
            "capital_label": _clean(intent.get("capital_label")),
            "monitor_run_id": _clean(intent.get("monitor_run_id")),
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
        for key in (
            *IDENTITY_TEXT_FIELDS,
            *IDENTITY_NUMBER_FIELDS,
            *STAGE904_MIGRATION_AUDIT_FIELDS,
        ):
            if _clean(intent.get(key)):
                order_request_payload[key] = intent[key]

    unique_reasons = ";".join(dict.fromkeys(reasons))
    stable_order_payload = {
        key: value
        for key, value in order_request_payload.items()
        if key != "monitor_run_id"
    }
    spool_payload = {
        **intent,
        "executor_status": status,
        "executor_reason_codes": _stable_reason_codes(reasons),
        "resolved_limit_price": price,
        "pricetick": pricetick,
        "broker_matching_position_volume": broker_match_volume,
        "order_request": stable_order_payload,
    }
    stable_spool_payload = {
        key: value
        for key, value in spool_payload.items()
        if key not in _VOLATILE_INTENT_HASH_FIELDS
        and not key.endswith("_generated_at")
        and not key.endswith("_checked_at")
    }
    spool_payload_json = json.dumps(
        _canonical_spool_json_value(stable_spool_payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    payload_sha256 = hashlib.sha256(spool_payload_json.encode("utf-8")).hexdigest()

    return {
        **intent,
        "payload_sha256": payload_sha256,
        "spool_payload_json": spool_payload_json,
        "executor_mode": mode,
        "executor_status": status,
        "executor_reason": unique_reasons,
        "symbol": symbol,
        "exchange": exchange_value,
        "pricetick": pricetick,
        "price_adjustment_reason": price_adjustment_reason,
        "broker_matching_position_volume": broker_match_volume,
        "active_order_count": active_orders,
        "order_request_json": json.dumps(order_request_payload, ensure_ascii=False, sort_keys=True),
        "order_request_price": _to_float(order_request_payload.get("price"), 0.0),
        "order_request_volume": _to_float(order_request_payload.get("volume"), 0.0),
        "stage904_monitor_status": (
            _clean(stage904_summary.get("monitor_status"))
            if intraday_close_intent or intraday_retry_open_intent
            else ""
        ),
        "stage904_summary_generated_at": (
            _clean(stage904_summary.get("generated_at"))
            if intraday_close_intent or intraday_retry_open_intent
            else ""
        ),
        "send_order_api_called": 0,
        "cancel_order_api_called": 0,
        "checked_at": datetime.fromtimestamp(
            current_stamp.epoch_ns / 1_000_000_000
        ).strftime("%Y-%m-%d %H:%M:%S"),
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


def run_executor_dry_run(
    target_date: str,
    mode: str = "dry-run",
    stage904_actions: pd.DataFrame | Any | None = None,
    stage904_summary: Mapping[str, Any] | None = None,
    snapshots: Stage905SnapshotInputs | None = None,
    include_stage901_pending: bool = True,
    execution_profile: (
        OfficialExecutionProfile | str | ExecutionStrategyMode
    ) = C9_15W_PROFILE,
    stage260_decisions: pd.DataFrame | None = None,
    clock: Clock = SYSTEM_CLOCK,
    write_compat_outputs: bool = True,
) -> Stage905RunResult:
    profile = (
        execution_profile
        if isinstance(execution_profile, OfficialExecutionProfile)
        else resolve_execution_profile(execution_profile)
    )
    intraday_inputs_supplied = (
        stage904_actions is not None or stage904_summary is not None
    )
    if not profile.intraday_stop_retry_enabled:
        if intraday_inputs_supplied:
            raise ValueError("stage372_intraday_input_forbidden")
        if include_stage901_pending:
            raise ValueError("stage372_stage901_pending_forbidden")
        stage904_actions = pd.DataFrame(columns=["monitor_action"])
        stage904_summary = {
            "target_date": target_date,
            "monitor_status": "intraday_not_applicable_profile_disabled",
        }
    if stage904_actions is not None and not isinstance(stage904_actions, pd.DataFrame):
        result_actions = getattr(stage904_actions, "actions", None)
        result_summary = getattr(stage904_actions, "summary", None)
        if not isinstance(result_actions, pd.DataFrame) or not isinstance(result_summary, Mapping):
            raise TypeError("stage904_actions_must_be_dataframe_or_stage904_run_result")
        if stage904_summary is not None and dict(stage904_summary) != dict(result_summary):
            raise ValueError("stage904_run_result_summary_conflict")
        if _clean(getattr(stage904_actions, "target_date", "")) != target_date:
            raise ValueError("stage904_run_result_target_date_mismatch")
        result_run_id = _clean(getattr(stage904_actions, "monitor_run_id", ""))
        if result_run_id != _clean(result_summary.get("monitor_run_id")):
            raise ValueError("stage904_run_result_monitor_run_id_mismatch")
        stage904_summary = result_summary
        stage904_actions = result_actions
    if (stage904_actions is None) != (stage904_summary is None):
        raise ValueError("stage904_in_memory_inputs_must_be_paired")
    in_memory_stage904 = bool(
        profile.intraday_stop_retry_enabled and stage904_actions is not None
    )
    if (
        in_memory_stage904
        and _clean(stage904_summary.get("target_date")) != target_date
    ):
        raise ValueError("stage904_in_memory_target_date_mismatch")

    paths = _paths(target_date)
    run_now = ClockStamp.from_clock(clock)
    generated_at = datetime.fromtimestamp(
        run_now.epoch_ns / 1_000_000_000
    ).strftime("%Y-%m-%d %H:%M:%S")
    if write_compat_outputs:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        _atomic_write_df(paths["intents_csv"], pd.DataFrame())
        _atomic_write_text(
            paths["summary_json"],
            json.dumps(
                {
                    "model_tag": MODEL_TAG,
                    "generated_at": generated_at,
                    "target_date": target_date,
                    "executor_status": "executor_running_fail_closed",
                    "ready_count": 0,
                    "blocked_count": 1,
                    "send_order_api_called_count": 0,
                    "cancel_order_api_called_count": 0,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

    if stage904_actions is None:
        stage904_actions = _read_csv_maybe(_stage904_actions_path(target_date))
    else:
        stage904_actions = stage904_actions.copy(deep=True)
    if stage904_summary is None:
        stage904_summary_data = _read_json(_stage904_summary_path(target_date))
    else:
        stage904_summary_data = dict(stage904_summary)
    stage904_batch_blockers = (
        _stage904_batch_summary_blockers(
            stage904_actions,
            stage904_summary_data,
        )
        if in_memory_stage904
        else ()
    )
    if snapshots is None:
        pending_orders = _read_csv_maybe(profile.pending_orders_path)
        contracts = _read_csv_maybe(READONLY_CONTRACTS_PATH)
        positions = _read_csv_maybe(READONLY_POSITIONS_PATH)
        orders = _read_csv_maybe(READONLY_ORDERS_PATH)
        stage902_summary = _read_json(_stage902_summary_path(target_date))
        stage260_summary = _read_json(_stage260_summary_path(target_date))
        execution_ledger_rows = read_execution_ledger()
        if stage260_decisions is None:
            stage260_decisions = _read_csv_maybe(
                _stage260_decisions_path(target_date)
            )
    else:
        pending_orders = snapshots.pending_orders.copy(deep=True)
        contracts = snapshots.contracts.copy(deep=True)
        positions = snapshots.positions.copy(deep=True)
        orders = snapshots.orders.copy(deep=True)
        stage902_summary = dict(snapshots.stage902_summary)
        stage260_summary = dict(snapshots.stage260_summary)
        execution_ledger_rows = [dict(row) for row in snapshots.execution_ledger_rows]
    if stage260_decisions is None:
        stage260_decisions = pd.DataFrame()
    else:
        stage260_decisions = stage260_decisions.copy(deep=True)

    pending_intents = []
    if include_stage901_pending:
        pending_intents = _suppress_stage901_pending_after_stop_close(
            _pending_order_intents(pending_orders, target_date),
            ledger_rows=execution_ledger_rows,
            target_date=target_date,
        )
    stage260_intents = _stage260_daily_intents(
        stage260_decisions,
        summary=stage260_summary,
        profile=profile,
        target_date=target_date,
    )
    raw_intents = _dedupe_intents(
        pending_intents
        + stage260_intents
        + _stage904_intents(stage904_actions)
    )
    for row in raw_intents:
        assert_intent_source_allowed(profile, row.get("source"))
        row["execution_profile"] = profile.profile_key
        row["official_live_version"] = profile.official_version
        row["capital"] = profile.capital
        row["capital_label"] = profile.capital_label
    intent_rows = [
        _validate_intent(
            row,
            contracts=contracts,
            positions=positions,
            orders=orders,
            stage902_summary=stage902_summary,
            stage904_summary=stage904_summary_data,
            stage260_summary=stage260_summary,
            mode=mode,
            clock=clock,
            require_stage904_trace=in_memory_stage904,
            now_stamp=run_now,
            stage904_batch_blockers=stage904_batch_blockers,
        )
        for row in raw_intents
    ]
    intents = pd.DataFrame(intent_rows)
    for field_name in STAGE904_EXACT_INT_FIELDS:
        if any(field_name in row for row in intent_rows):
            intents[field_name] = pd.Series(
                [row.get(field_name) for row in intent_rows],
                dtype=object,
            )
    ready_count = int(intents.get("executor_status", pd.Series(dtype=str)).astype(str).eq("dry_run_order_request_payload_ready").sum()) if not intents.empty else 0
    blocked_count = int(intents.get("executor_status", pd.Series(dtype=str)).astype(str).eq("blocked").sum()) if not intents.empty else 0
    expired_count = int(intents.get("executor_status", pd.Series(dtype=str)).astype(str).eq("expired").sum()) if not intents.empty else 0
    skipped_count = int(intents.get("executor_status", pd.Series(dtype=str)).astype(str).str.startswith("skipped_").sum()) if not intents.empty else 0
    send_count = int(intents.get("send_order_api_called", pd.Series(dtype=float)).sum()) if not intents.empty else 0
    cancel_count = int(intents.get("cancel_order_api_called", pd.Series(dtype=float)).sum()) if not intents.empty else 0
    if stage904_batch_blockers:
        executor_status = "executor_dry_run_blocked"
    elif intents.empty:
        executor_status = "executor_no_intents"
    elif ready_count and not blocked_count:
        executor_status = "executor_dry_run_ready"
    elif blocked_count:
        executor_status = "executor_dry_run_blocked"
    else:
        executor_status = "executor_no_ready_intents"

    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": generated_at,
        "target_date": target_date,
        "execution_profile": profile.profile_key,
        "official_live_version": profile.official_version,
        "official_live_alias": profile.alias,
        "capital": profile.capital,
        "capital_label": profile.capital_label,
        "intraday_stop_retry_enabled": int(
            profile.intraday_stop_retry_enabled
        ),
        "executor_status": executor_status,
        "intent_count": int(len(intents)),
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "expired_count": expired_count,
        "skipped_count": skipped_count,
        "input_blocker_count": int(len(stage904_batch_blockers)),
        "input_blockers": list(stage904_batch_blockers),
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
    if write_compat_outputs:
        _atomic_write_df(paths["intents_csv"], intents)
        _atomic_write_text(
            paths["summary_json"],
            json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        )
        _atomic_write_text(paths["report_md"], _build_report(summary, intents))
    return Stage905RunResult(intents=intents, summary=summary, paths=paths)


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live Phase D executor dry-run.")
    parser.add_argument("--target-date", required=True)
    parser.add_argument("--mode", choices=["dry-run"], default="dry-run")
    parser.add_argument(
        "--execution-profile",
        choices=[item.value for item in ExecutionStrategyMode],
        default=ExecutionStrategyMode.C9_15W.value,
    )
    args = parser.parse_args()

    profile = resolve_execution_profile(args.execution_profile)
    result = run_executor_dry_run(
        args.target_date,
        mode=args.mode,
        execution_profile=profile,
        include_stage901_pending=profile.intraday_stop_retry_enabled,
    )
    print(json.dumps(result.summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
