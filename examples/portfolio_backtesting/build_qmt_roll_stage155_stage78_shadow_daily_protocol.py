from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_REFERENCE_METRICS,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage155_stage78_shadow_daily_protocol_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage155_stage78_shadow_daily_protocol"
STAGE154_PREFIX: str = "qmt_roll_stage154_stage78_shadow_execution_ledger"
STAGE154_TAG: str = "stage154_stage78_shadow_execution_ledger_v1"

STAGE154_TRADE_LEDGER_PATH: Path = OUTPUT_DIR / f"{STAGE154_PREFIX}_trade_ledger_{STAGE154_TAG}.csv"
STAGE154_DAILY_LEDGER_PATH: Path = OUTPUT_DIR / f"{STAGE154_PREFIX}_daily_ledger_{STAGE154_TAG}.csv"
STAGE154_SUMMARY_PATH: Path = OUTPUT_DIR / f"{STAGE154_PREFIX}_summary_{STAGE154_TAG}.json"

SIGNAL_INTENT_SCHEMA_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_signal_intent_schema_{MODEL_TAG}.csv"
ORDER_EVENT_SCHEMA_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_order_event_schema_{MODEL_TAG}.csv"
FILL_EVENT_SCHEMA_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fill_event_schema_{MODEL_TAG}.csv"
POSITION_RECONCILE_SCHEMA_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_position_reconcile_schema_{MODEL_TAG}.csv"
ACCOUNT_RECONCILE_SCHEMA_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_account_reconcile_schema_{MODEL_TAG}.csv"
EXCEPTION_SCHEMA_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_exception_schema_{MODEL_TAG}.csv"
HISTORICAL_INTENT_LEDGER_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_historical_intent_ledger_{MODEL_TAG}.csv"
DAILY_CONTROL_LEDGER_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_control_ledger_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
SOP_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_sop_{MODEL_TAG}.md"

MARGIN_USAGE_WATCH_PCT: float = 80.0
MARGIN_USAGE_ALERT_PCT: float = 100.0
DAILY_ADVERSE_WARN_CASH: float = 20_000.0
DAILY_ADVERSE_ALERT_CASH: float = 50_000.0


def _require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing required artifact: {path}")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _fmt(value: Any, digits: int = 4) -> str:
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    numeric = _safe_float(value, default=float("nan"))
    if math.isnan(numeric):
        return str(value)
    if abs(numeric) >= 1000:
        return f"{numeric:,.0f}"
    return f"{numeric:.{digits}f}"


def _to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 20) -> str:
    if df.empty:
        return "_No rows._"
    view = df.copy()
    if columns is not None:
        view = view.loc[:, [column for column in columns if column in view.columns]]
    view = view.head(max_rows).copy()
    for column in view.columns:
        if column in {"date", "decision_date", "plan_date"}:
            view[column] = pd.to_datetime(view[column], errors="coerce").dt.strftime("%Y-%m-%d")
        elif pd.api.types.is_numeric_dtype(view[column]):
            view[column] = view[column].map(_fmt)
    return "\n".join(
        [
            "| " + " | ".join(view.columns) + " |",
            "| " + " | ".join(["---"] * len(view.columns)) + " |",
            *["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()],
        ]
    )


def _read_csv(path: Path) -> pd.DataFrame:
    _require(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _read_json(path: Path) -> dict[str, Any]:
    _require(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _schema(rows: list[dict[str, Any]]) -> pd.DataFrame:
    columns = [
        "field_name",
        "field_type",
        "required",
        "source",
        "description",
        "validation_rule",
        "example",
    ]
    return pd.DataFrame(rows, columns=columns)


def _build_schemas() -> dict[str, pd.DataFrame]:
    signal_intent = _schema(
        [
            {
                "field_name": "shadow_session_id",
                "field_type": "string",
                "required": "yes",
                "source": "generated",
                "description": "影子盘单笔意图主键，不能复用。",
                "validation_rule": "unique; format STAGE78-YYYYMMDD-TRADEID",
                "example": "STAGE78-20200102-BACKTESTING.12",
            },
            {
                "field_name": "strategy_version",
                "field_type": "string",
                "required": "yes",
                "source": "Stage78 config",
                "description": "冻结策略版本。",
                "validation_rule": f"must equal {OFFICIAL_STAGE78_VERSION}",
                "example": OFFICIAL_STAGE78_VERSION,
            },
            {
                "field_name": "decision_date",
                "field_type": "date",
                "required": "yes",
                "source": "Stage78 signal",
                "description": "策略产生理论成交或信号的日期。",
                "validation_rule": "YYYY-MM-DD; trading day",
                "example": "2020-01-02",
            },
            {
                "field_name": "plan_date",
                "field_type": "date",
                "required": "yes",
                "source": "Stage154 next_trade_date",
                "description": "计划提交影子盘订单的日期，历史映射为次一可成交交易日。",
                "validation_rule": "YYYY-MM-DD; plan_date >= decision_date",
                "example": "2020-01-03",
            },
            {
                "field_name": "product_vt_symbol",
                "field_type": "string",
                "required": "yes",
                "source": "Stage154 trade ledger",
                "description": "品种级标识。",
                "validation_rule": "non-empty",
                "example": "SM.CZCE",
            },
            {
                "field_name": "vt_symbol",
                "field_type": "string",
                "required": "yes",
                "source": "Stage154 trade ledger",
                "description": "实际合约标识。",
                "validation_rule": "non-empty; must map to current tradable contract in live mode",
                "example": "SM005.CZCE",
            },
            {
                "field_name": "direction",
                "field_type": "enum",
                "required": "yes",
                "source": "Stage78 signal",
                "description": "交易方向。",
                "validation_rule": "Long or Short",
                "example": "Long",
            },
            {
                "field_name": "offset",
                "field_type": "enum",
                "required": "yes",
                "source": "Stage78 signal",
                "description": "开平标识。",
                "validation_rule": "Open or Close",
                "example": "Open",
            },
            {
                "field_name": "planned_volume",
                "field_type": "number",
                "required": "yes",
                "source": "Stage78 sizing",
                "description": "计划手数。",
                "validation_rule": "integer-like; > 0",
                "example": "8",
            },
            {
                "field_name": "theoretical_price",
                "field_type": "number",
                "required": "yes",
                "source": "Stage78 formal trade",
                "description": "正式回测记录的理论成交价。",
                "validation_rule": "> 0",
                "example": "6388",
            },
            {
                "field_name": "next_open_proxy_price",
                "field_type": "number",
                "required": "yes",
                "source": "Stage154 executable audit",
                "description": "次一交易日开盘代理执行价，用于影子盘偏差审计。",
                "validation_rule": "> 0 when next_open_available=1",
                "example": "6390",
            },
            {
                "field_name": "expected_margin",
                "field_type": "number",
                "required": "yes",
                "source": "Stage154 margin audit",
                "description": "理论新增保证金；平仓为0。",
                "validation_rule": ">= 0",
                "example": "30662.4",
            },
            {
                "field_name": "expected_execution_status",
                "field_type": "enum",
                "required": "yes",
                "source": "Stage154 daily control",
                "description": "当日历史执行/资金状态。",
                "validation_rule": "normal/watch/alert/data_gap classes",
                "example": "normal",
            },
            {
                "field_name": "signal_freeze_flag",
                "field_type": "boolean",
                "required": "yes",
                "source": "operator",
                "description": "信号冻结标识；冻结后只能记录执行事实，不能事后改信号。",
                "validation_rule": "1 before order submission",
                "example": "1",
            },
        ]
    )

    order_event = _schema(
        [
            {
                "field_name": "shadow_session_id",
                "field_type": "string",
                "required": "yes",
                "source": "signal_intent",
                "description": "关联影子盘意图。",
                "validation_rule": "must exist in signal_intent ledger",
                "example": "STAGE78-20200102-BACKTESTING.12",
            },
            {
                "field_name": "broker_order_id",
                "field_type": "string",
                "required": "yes_live",
                "source": "broker/order callback",
                "description": "券商或仿真柜台订单编号。",
                "validation_rule": "non-empty after submit",
                "example": "SIM-ORDER-000001",
            },
            {
                "field_name": "order_submit_time",
                "field_type": "datetime",
                "required": "yes_live",
                "source": "broker/order callback",
                "description": "订单提交时间。",
                "validation_rule": "timezone-aware or local exchange time",
                "example": "2020-01-03 09:00:01",
            },
            {
                "field_name": "account_id",
                "field_type": "string",
                "required": "yes_live",
                "source": "broker",
                "description": "账户标识。",
                "validation_rule": "non-empty; mask if exported",
                "example": "SIM_ACCOUNT",
            },
            {
                "field_name": "order_price",
                "field_type": "number",
                "required": "yes_live",
                "source": "order request",
                "description": "实际报单价格。",
                "validation_rule": "> 0; price_tick aligned",
                "example": "6390",
            },
            {
                "field_name": "order_volume",
                "field_type": "number",
                "required": "yes_live",
                "source": "order request",
                "description": "实际报单手数。",
                "validation_rule": "> 0 and <= planned_volume unless manual exception",
                "example": "8",
            },
            {
                "field_name": "order_status",
                "field_type": "enum",
                "required": "yes_live",
                "source": "broker/order callback",
                "description": "订单状态。",
                "validation_rule": "submitted/partial_filled/filled/cancelled/rejected",
                "example": "submitted",
            },
            {
                "field_name": "rejected_reason",
                "field_type": "string",
                "required": "when_rejected",
                "source": "broker/order callback",
                "description": "拒单原因。",
                "validation_rule": "required when order_status=rejected",
                "example": "insufficient_margin",
            },
        ]
    )

    fill_event = _schema(
        [
            {
                "field_name": "shadow_session_id",
                "field_type": "string",
                "required": "yes",
                "source": "signal_intent",
                "description": "关联影子盘意图。",
                "validation_rule": "must exist in signal_intent ledger",
                "example": "STAGE78-20200102-BACKTESTING.12",
            },
            {
                "field_name": "broker_order_id",
                "field_type": "string",
                "required": "yes_live",
                "source": "order_event",
                "description": "关联订单编号。",
                "validation_rule": "must exist in order_event ledger",
                "example": "SIM-ORDER-000001",
            },
            {
                "field_name": "fill_id",
                "field_type": "string",
                "required": "yes_live",
                "source": "broker/fill callback",
                "description": "成交编号。",
                "validation_rule": "unique per broker_order_id",
                "example": "SIM-FILL-000001",
            },
            {
                "field_name": "fill_time",
                "field_type": "datetime",
                "required": "yes_live",
                "source": "broker/fill callback",
                "description": "成交时间。",
                "validation_rule": ">= order_submit_time",
                "example": "2020-01-03 09:00:05",
            },
            {
                "field_name": "fill_price",
                "field_type": "number",
                "required": "yes_live",
                "source": "broker/fill callback",
                "description": "实际成交价。",
                "validation_rule": "> 0; price_tick aligned",
                "example": "6390",
            },
            {
                "field_name": "fill_volume",
                "field_type": "number",
                "required": "yes_live",
                "source": "broker/fill callback",
                "description": "成交手数。",
                "validation_rule": "> 0 and cumulative <= order_volume",
                "example": "8",
            },
            {
                "field_name": "commission",
                "field_type": "number",
                "required": "yes_live",
                "source": "broker/fill callback",
                "description": "成交手续费。",
                "validation_rule": ">= 0",
                "example": "0",
            },
            {
                "field_name": "slippage_cash",
                "field_type": "number",
                "required": "yes_live",
                "source": "calculated",
                "description": "相对理论价或冻结代理价的成交偏差现金值。",
                "validation_rule": "recalculate from fill_price, theoretical_price, size, volume",
                "example": "80",
            },
        ]
    )

    position_reconcile = _schema(
        [
            {
                "field_name": "reconcile_date",
                "field_type": "date",
                "required": "yes_live",
                "source": "operator/broker",
                "description": "持仓对账日期。",
                "validation_rule": "trading day",
                "example": "2020-01-03",
            },
            {
                "field_name": "account_id",
                "field_type": "string",
                "required": "yes_live",
                "source": "broker",
                "description": "账户标识。",
                "validation_rule": "non-empty",
                "example": "SIM_ACCOUNT",
            },
            {
                "field_name": "vt_symbol",
                "field_type": "string",
                "required": "yes_live",
                "source": "broker position",
                "description": "实际合约标识。",
                "validation_rule": "non-empty",
                "example": "SM005.CZCE",
            },
            {
                "field_name": "strategy_position",
                "field_type": "number",
                "required": "yes_live",
                "source": "shadow ledger",
                "description": "影子盘策略应有净持仓。",
                "validation_rule": "signed quantity",
                "example": "8",
            },
            {
                "field_name": "broker_position",
                "field_type": "number",
                "required": "yes_live",
                "source": "broker position",
                "description": "柜台实际净持仓。",
                "validation_rule": "signed quantity",
                "example": "8",
            },
            {
                "field_name": "position_diff",
                "field_type": "number",
                "required": "yes_live",
                "source": "calculated",
                "description": "实际持仓与策略持仓差异。",
                "validation_rule": "broker_position - strategy_position",
                "example": "0",
            },
            {
                "field_name": "reconcile_status",
                "field_type": "enum",
                "required": "yes_live",
                "source": "calculated",
                "description": "持仓对账状态。",
                "validation_rule": "matched/watch/mismatch",
                "example": "matched",
            },
        ]
    )

    account_reconcile = _schema(
        [
            {
                "field_name": "reconcile_date",
                "field_type": "date",
                "required": "yes_live",
                "source": "operator/broker",
                "description": "资金对账日期。",
                "validation_rule": "trading day",
                "example": "2020-01-03",
            },
            {
                "field_name": "account_id",
                "field_type": "string",
                "required": "yes_live",
                "source": "broker",
                "description": "账户标识。",
                "validation_rule": "non-empty",
                "example": "SIM_ACCOUNT",
            },
            {
                "field_name": "balance",
                "field_type": "number",
                "required": "yes_live",
                "source": "broker account",
                "description": "账户权益。",
                "validation_rule": "> 0",
                "example": "207000",
            },
            {
                "field_name": "available_cash",
                "field_type": "number",
                "required": "yes_live",
                "source": "broker account",
                "description": "可用资金。",
                "validation_rule": ">= 0 unless broker-specific",
                "example": "160000",
            },
            {
                "field_name": "margin_used",
                "field_type": "number",
                "required": "yes_live",
                "source": "broker account",
                "description": "实际占用保证金。",
                "validation_rule": ">= 0",
                "example": "30662.4",
            },
            {
                "field_name": "risk_ratio_pct",
                "field_type": "number",
                "required": "yes_live",
                "source": "broker account",
                "description": "柜台风险率或保证金占用率。",
                "validation_rule": "watch >= 80; alert >= 100",
                "example": "43.9668",
            },
            {
                "field_name": "reconcile_status",
                "field_type": "enum",
                "required": "yes_live",
                "source": "calculated",
                "description": "资金对账状态。",
                "validation_rule": "matched/watch/mismatch",
                "example": "matched",
            },
        ]
    )

    exception = _schema(
        [
            {
                "field_name": "exception_id",
                "field_type": "string",
                "required": "yes_live",
                "source": "generated",
                "description": "异常主键。",
                "validation_rule": "unique",
                "example": "EX-20200103-0001",
            },
            {
                "field_name": "shadow_session_id",
                "field_type": "string",
                "required": "when_trade_related",
                "source": "signal_intent",
                "description": "关联意图，非交易类资金异常可为空。",
                "validation_rule": "must exist when non-empty",
                "example": "STAGE78-20200102-BACKTESTING.12",
            },
            {
                "field_name": "exception_date",
                "field_type": "date",
                "required": "yes_live",
                "source": "generated/operator",
                "description": "异常日期。",
                "validation_rule": "YYYY-MM-DD",
                "example": "2020-01-03",
            },
            {
                "field_name": "exception_type",
                "field_type": "enum",
                "required": "yes_live",
                "source": "calculated/operator",
                "description": "异常类型。",
                "validation_rule": "data_gap/order_reject/fill_deviation/position_mismatch/account_mismatch/margin_alert",
                "example": "fill_deviation",
            },
            {
                "field_name": "severity",
                "field_type": "enum",
                "required": "yes_live",
                "source": "calculated/operator",
                "description": "异常严重度。",
                "validation_rule": "watch/alert/severe",
                "example": "watch",
            },
            {
                "field_name": "decision",
                "field_type": "enum",
                "required": "yes_live",
                "source": "operator",
                "description": "处理决策。",
                "validation_rule": "record_only/retry_order/pause_new_orders/manual_reconcile",
                "example": "record_only",
            },
            {
                "field_name": "resolution_note",
                "field_type": "string",
                "required": "when_resolved",
                "source": "operator",
                "description": "处理说明。只能解释执行和对账，不允许事后改Stage78信号。",
                "validation_rule": "non-empty when resolved_at is set",
                "example": "sim fill matched next-open proxy within threshold",
            },
        ]
    )

    return {
        "signal_intent_schema": signal_intent,
        "order_event_schema": order_event,
        "fill_event_schema": fill_event,
        "position_reconcile_schema": position_reconcile,
        "account_reconcile_schema": account_reconcile,
        "exception_schema": exception,
    }


def _load_inputs() -> dict[str, Any]:
    trade_ledger = _read_csv(STAGE154_TRADE_LEDGER_PATH)
    daily_ledger = _read_csv(STAGE154_DAILY_LEDGER_PATH)
    summary = _read_json(STAGE154_SUMMARY_PATH)

    trade_ledger["date"] = pd.to_datetime(trade_ledger["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    trade_ledger["next_trade_date"] = pd.to_datetime(
        trade_ledger["next_trade_date"], errors="coerce"
    ).dt.tz_localize(None).dt.normalize()
    daily_ledger["date"] = pd.to_datetime(daily_ledger["date"], errors="coerce").dt.tz_localize(None).dt.normalize()

    numeric_trade_columns = [
        "theoretical_price",
        "volume",
        "size",
        "price_tick",
        "margin_ratio",
        "theoretical_notional",
        "theoretical_margin",
        "next_open",
        "next_close",
        "next_open_available",
        "next_close_available",
        "next_bar_missing",
        "next_zero_volume",
        "next_no_range",
        "next_open_adverse_cash",
        "next_close_adverse_cash",
    ]
    for column in numeric_trade_columns:
        trade_ledger[column] = pd.to_numeric(trade_ledger.get(column, 0.0), errors="coerce").fillna(0.0)

    numeric_daily_columns = [
        "net_pnl",
        "balance",
        "ddpercent",
        "audited_trade_count",
        "next_open_adverse_cash",
        "next_close_adverse_cash",
        "max_projected_margin_usage_pct",
        "next_bar_missing_count",
        "next_zero_volume_count",
        "next_open_unavailable_count",
    ]
    for column in numeric_daily_columns:
        daily_ledger[column] = pd.to_numeric(daily_ledger.get(column, 0.0), errors="coerce").fillna(0.0)

    return {
        "trade_ledger": trade_ledger.dropna(subset=["date"]).sort_values(["date", "trade_id"]).reset_index(drop=True),
        "daily_ledger": daily_ledger.dropna(subset=["date"]).sort_values("date").reset_index(drop=True),
        "stage154_summary": summary,
    }


def _build_historical_intent_ledger(trade_ledger: pd.DataFrame, daily_control: pd.DataFrame) -> pd.DataFrame:
    daily_status = daily_control[
        [
            "date",
            "execution_status",
            "shadow_run_permission",
            "allow_new_orders",
            "manual_review_required",
            "max_projected_margin_usage_pct",
        ]
    ].copy()
    daily_status["date"] = pd.to_datetime(daily_status["date"], errors="coerce").dt.normalize()
    merged = trade_ledger.merge(daily_status, on="date", how="left")
    decision_dates = pd.to_datetime(merged["date"], errors="coerce")
    plan_dates = pd.to_datetime(merged["next_trade_date"], errors="coerce")
    rows: list[dict[str, Any]] = []
    for row in merged.itertuples(index=False):
        decision_date = pd.Timestamp(row.date)
        plan_date = pd.Timestamp(row.next_trade_date) if not pd.isna(row.next_trade_date) else pd.NaT
        shadow_session_id = f"STAGE78-{decision_date.strftime('%Y%m%d')}-{row.trade_id}"
        rows.append(
            {
                "shadow_session_id": shadow_session_id,
                "source_trade_id": row.trade_id,
                "strategy_version": OFFICIAL_STAGE78_VERSION,
                "strategy_role": OFFICIAL_STAGE78_ROLE,
                "decision_date": decision_date.date().isoformat(),
                "plan_date": plan_date.date().isoformat() if not pd.isna(plan_date) else "",
                "product_vt_symbol": row.product_vt_symbol,
                "vt_symbol": row.vt_symbol,
                "direction": row.direction,
                "offset": row.offset,
                "exit_reason": "" if pd.isna(row.exit_reason) else row.exit_reason,
                "planned_volume": row.volume,
                "contract_size": row.size,
                "price_tick": row.price_tick,
                "margin_ratio": row.margin_ratio,
                "theoretical_price": row.theoretical_price,
                "next_open_proxy_price": row.next_open,
                "next_close_proxy_price": row.next_close,
                "next_open_available": int(row.next_open_available),
                "next_close_available": int(row.next_close_available),
                "expected_notional": row.theoretical_notional,
                "expected_margin": row.theoretical_margin,
                "expected_execution_status": row.execution_status,
                "shadow_run_permission": row.shadow_run_permission,
                "allow_new_orders": int(row.allow_new_orders),
                "manual_review_required": int(row.manual_review_required),
                "max_projected_margin_usage_pct": row.max_projected_margin_usage_pct,
                "next_open_adverse_cash_proxy": row.next_open_adverse_cash,
                "next_close_adverse_cash_proxy": row.next_close_adverse_cash,
                "signal_freeze_flag": 1,
                "broker_order_id": "",
                "order_submit_time": "",
                "order_status": "",
                "filled_price": "",
                "filled_volume": "",
                "commission": "",
                "slippage_cash": "",
                "position_after": "",
                "account_balance_after": "",
                "reconcile_status": "",
                "exception_code": "",
                "operator_note": "",
            }
        )
    result = pd.DataFrame(rows)
    result["decision_date"] = decision_dates.dt.strftime("%Y-%m-%d").to_numpy()
    result["plan_date"] = plan_dates.dt.strftime("%Y-%m-%d").fillna("").to_numpy()
    return result


def _permission_from_daily_row(row: Any) -> tuple[str, int, str]:
    status = str(row.execution_status)
    margin_usage = _safe_float(row.max_projected_margin_usage_pct)
    has_data_gap = (
        _safe_float(getattr(row, "next_bar_missing_count", 0.0)) > 0.0
        or _safe_float(getattr(row, "next_zero_volume_count", 0.0)) > 0.0
        or _safe_float(getattr(row, "next_open_unavailable_count", 0.0)) > 0.0
    )
    if has_data_gap:
        return "no_new_orders_data_gap", 0, "行情或次日开盘代理价缺口，禁止新增开仓，只允许平风险和人工复核。"
    if status == "alert_margin_usage" or margin_usage >= MARGIN_USAGE_ALERT_PCT:
        return "no_new_orders_margin_alert", 0, "计划保证金占用达到或超过100%，禁止新增开仓。"
    if status == "watch_margin_usage" or margin_usage >= MARGIN_USAGE_WATCH_PCT:
        return "allow_with_margin_review", 1, "计划保证金占用超过80%，允许影子盘记录，但实盘前必须复核可用资金和组合杠杆。"
    if status == "alert_next_open_adverse":
        return "allow_with_execution_review", 1, "历史代理执行冲击达到alert，允许记录，但真实接入前需复核执行窗口和成交偏差。"
    if status == "watch_next_open_adverse":
        return "allow_with_execution_watch", 1, "历史代理执行冲击达到watch，允许记录并标记成交偏差观察。"
    return "allow_normal_shadow_run", 1, "常规影子盘记录，不修改Stage78信号。"


def _build_daily_control_ledger(daily_ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in daily_ledger.itertuples(index=False):
        permission, allow_new_orders, action = _permission_from_daily_row(row)
        margin_usage = _safe_float(row.max_projected_margin_usage_pct)
        status = str(row.execution_status)
        margin_watch = int(margin_usage >= MARGIN_USAGE_WATCH_PCT or status in {"watch_margin_usage", "alert_margin_usage"})
        execution_watch = int(
            status in {"watch_next_open_adverse", "alert_next_open_adverse", "execution_data_gap"}
            or _safe_float(row.next_open_adverse_cash) >= DAILY_ADVERSE_WARN_CASH
        )
        manual_review_required = int(
            allow_new_orders == 0
            or margin_watch
            or execution_watch
            or status != "normal"
        )
        rows.append(
            {
                "date": pd.Timestamp(row.date).date().isoformat(),
                "strategy_version": OFFICIAL_STAGE78_VERSION,
                "execution_status": status,
                "shadow_run_permission": permission,
                "allow_new_orders": allow_new_orders,
                "required_action": action,
                "net_pnl": row.net_pnl,
                "balance": row.balance,
                "ddpercent": row.ddpercent,
                "audited_trade_count": row.audited_trade_count,
                "next_open_adverse_cash": row.next_open_adverse_cash,
                "next_close_adverse_cash": row.next_close_adverse_cash,
                "max_projected_margin_usage_pct": margin_usage,
                "margin_watch": margin_watch,
                "execution_watch": execution_watch,
                "manual_review_required": manual_review_required,
                "no_new_orders_reason": "" if allow_new_orders else action,
            }
        )
    return pd.DataFrame(rows)


def _required_broker_fields_not_available() -> list[str]:
    return [
        "account_id",
        "broker_order_id",
        "order_submit_time",
        "order_price",
        "order_volume",
        "order_status",
        "fill_id",
        "fill_time",
        "fill_price",
        "fill_volume",
        "commission",
        "slippage_cash",
        "broker_position",
        "available_cash",
        "margin_used",
        "risk_ratio_pct",
    ]


def _write_sop(summary: dict[str, Any]) -> None:
    reference = OFFICIAL_STAGE78_REFERENCE_METRICS["full_2020_2026"]
    lines = [
        "# Stage155 Stage78影子盘每日落表SOP",
        "",
        "## 定位",
        "",
        "- 本SOP不是新策略，不修改Stage78正式信号和参数。",
        "- 目标是把理论信号、订单、成交、持仓、资金、异常全部落到可复核的表，形成真实前向OOS证据。",
        "- 执行异常只能触发记录、复核、暂停新增开仓或人工对账，不能倒逼修改Stage78历史规则。",
        "",
        "## 冻结基准",
        "",
        f"- 版本：`{OFFICIAL_STAGE78_VERSION}`",
        f"- 角色：`{OFFICIAL_STAGE78_ROLE}`",
        (
            f"- 全周期参考：期末权益 `{reference['end_balance']:,.0f}`，"
            f"总收益 `{reference['total_return_pct']:.4f}%`，"
            f"最大回撤 `{reference['max_dd_percent']:.4f}%`，"
            f"Sharpe `{reference['sharpe_ratio']:.4f}`，"
            f"总滑点 `{reference['total_slippage']:,.0f}`，"
            f"交易 `{reference['total_trade_count']:,.0f}`。"
        ),
        "",
        "## 每日流程",
        "",
        "1. 收盘后生成Stage78理论信号，写入`signal_intent`，立刻设置`signal_freeze_flag=1`。",
        "2. 次一交易日前检查合约、保证金、可用资金、涨跌停和数据完整性。",
        "3. 模拟盘或影子盘提交订单后写入`order_event`；拒单必须进入`exception`。",
        "4. 成交回报写入`fill_event`，按冻结理论价和次日开盘代理价计算偏差。",
        "5. 收盘后做`position_reconcile`和`account_reconcile`，任何差异必须有异常编号。",
        "6. 每周只复盘执行质量、资金压力和对账稳定性，不复盘信号参数优劣。",
        "",
        "## 硬性控制",
        "",
        f"- 计划保证金占用率 >= `{MARGIN_USAGE_ALERT_PCT:.0f}%`：禁止新增开仓，只允许降风险和人工复核。",
        f"- 计划保证金占用率 >= `{MARGIN_USAGE_WATCH_PCT:.0f}%`：进入margin watch，真实接入前必须确认可用资金。",
        "- 任何次日开盘代理价缺失、零成交量或订单/成交回报缺失：禁止新增开仓直到补齐或人工确认。",
        f"- 单日次日开盘代理执行冲击 >= `{DAILY_ADVERSE_ALERT_CASH:,.0f}`：进入execution alert，只复核执行窗口，不修改策略信号。",
        f"- 单日次日开盘代理执行冲击 >= `{DAILY_ADVERSE_WARN_CASH:,.0f}`：进入execution watch，连续出现时暂停真实放大。",
        "",
        "## 继续推进条件",
        "",
        "- 至少连续30个交易日能稳定产出信号、订单、成交、持仓、资金和异常表。",
        "- 仿真成交价相对次日开盘代理价的偏差没有系统性扩大。",
        "- 资金和持仓对账每天可解释；无法解释的差异不允许进入正式版本。",
        "- 任何策略改动必须另开版本和A/B边界，不能混入Stage78影子盘证据。",
        "",
        "## 当前缺口",
        "",
        f"- 历史意图行数：`{summary['historical_intent_rows']:,}`",
        f"- 每日控制行数：`{summary['daily_control_rows']:,}`",
        f"- 仍需真实或仿真柜台补齐字段：`{summary['required_broker_fields_not_available_count']}`个。",
        f"- 需要人工复核日：`{summary['manual_review_days']}`天。",
        f"- 禁止新增开仓日：`{summary['no_new_orders_days']}`天。",
    ]
    SOP_PATH.write_text("\n".join(lines), encoding="utf-8")


def _build_summary(
    schemas: dict[str, pd.DataFrame],
    historical_intent: pd.DataFrame,
    daily_control: pd.DataFrame,
    stage154_summary: dict[str, Any],
) -> dict[str, Any]:
    required_broker_fields = _required_broker_fields_not_available()
    permission_counts = daily_control["shadow_run_permission"].value_counts().to_dict()
    status_counts = daily_control["execution_status"].value_counts().to_dict()
    manual_review_days = int(daily_control["manual_review_required"].sum())
    no_new_orders_days = int((daily_control["allow_new_orders"] == 0).sum())
    watch_margin_days = int(daily_control["margin_watch"].sum())
    alert_execution_days = int((daily_control["execution_status"] == "alert_next_open_adverse").sum())

    return {
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "is_strategy_change": False,
        "is_backtest": False,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "reference_metrics": OFFICIAL_STAGE78_REFERENCE_METRICS,
        "source_stage154": {
            "trade_ledger": str(STAGE154_TRADE_LEDGER_PATH),
            "daily_ledger": str(STAGE154_DAILY_LEDGER_PATH),
            "audited_trade_count": stage154_summary.get("audited_trade_count"),
            "next_open_available_rate_pct": stage154_summary.get("next_open_available_rate_pct"),
            "max_projected_margin_usage_pct": stage154_summary.get("max_projected_margin_usage_pct"),
        },
        "schema_table_count": len(schemas),
        "schema_rows_total": int(sum(len(frame) for frame in schemas.values())),
        "historical_intent_rows": int(len(historical_intent)),
        "daily_control_rows": int(len(daily_control)),
        "required_broker_fields_not_available_count": len(required_broker_fields),
        "required_broker_fields_not_available": required_broker_fields,
        "manual_review_days": manual_review_days,
        "no_new_orders_days": no_new_orders_days,
        "watch_margin_days": watch_margin_days,
        "alert_execution_days": alert_execution_days,
        "shadow_run_permission_counts": {str(key): int(value) for key, value in permission_counts.items()},
        "execution_status_counts": {str(key): int(value) for key, value in status_counts.items()},
        "current_next_step": "CONNECT_SIMULATED_BROKER_FEEDBACK",
        "judgement": {
            "overfit_before": "否。Stage155只把Stage154历史执行ledger转成真实影子盘数据契约和SOP，不调参、不筛样本。",
            "continue_before": "是。Stage78要证明不是拟合，必须进入真实前向订单/成交/持仓/资金闭环。",
            "overfit_after": "否。本阶段没有产生任何新买卖规则，异常只影响记录和风控许可，不反向修改Stage78。",
            "continue_after": "是。下一步接入仿真柜台回报后，才能把历史OOS证据延伸为真实前向OOS证据。",
        },
        "outputs": {
            "signal_intent_schema": str(SIGNAL_INTENT_SCHEMA_PATH),
            "order_event_schema": str(ORDER_EVENT_SCHEMA_PATH),
            "fill_event_schema": str(FILL_EVENT_SCHEMA_PATH),
            "position_reconcile_schema": str(POSITION_RECONCILE_SCHEMA_PATH),
            "account_reconcile_schema": str(ACCOUNT_RECONCILE_SCHEMA_PATH),
            "exception_schema": str(EXCEPTION_SCHEMA_PATH),
            "historical_intent_ledger": str(HISTORICAL_INTENT_LEDGER_PATH),
            "daily_control_ledger": str(DAILY_CONTROL_LEDGER_PATH),
            "summary": str(SUMMARY_JSON_PATH),
            "report": str(REPORT_PATH),
            "sop": str(SOP_PATH),
        },
    }


def _write_report(summary: dict[str, Any], daily_control: pd.DataFrame) -> None:
    reference = OFFICIAL_STAGE78_REFERENCE_METRICS["full_2020_2026"]
    permission_df = pd.DataFrame(
        [
            {"shadow_run_permission": key, "days": value}
            for key, value in summary["shadow_run_permission_counts"].items()
        ]
    )
    review_days = daily_control[daily_control["manual_review_required"] == 1].copy()
    worst_review_days = review_days.sort_values(
        ["allow_new_orders", "max_projected_margin_usage_pct", "next_open_adverse_cash"],
        ascending=[True, False, False],
    ).head(12)
    outputs_df = pd.DataFrame(
        [{"artifact": key, "path": value} for key, value in summary["outputs"].items()]
    )

    lines = [
        "# Stage155 Stage78影子盘每日落表协议",
        "",
        "## 定位",
        "",
        "- 本阶段不是新策略版本，不修改Stage78正式参数。",
        "- 目标是把Stage154历史执行ledger升级为每日影子盘可落表协议：信号、订单、成交、持仓、资金和异常。",
        "- 历史结果只用于定义字段和控制边界，不用于反向优化品种、日期、阈值或信号。",
        "",
        "## Stage78冻结基准",
        "",
        f"- 版本：`{OFFICIAL_STAGE78_VERSION}`",
        f"- 角色：`{OFFICIAL_STAGE78_ROLE}`",
        (
            f"- 全周期：期末权益 `{reference['end_balance']:,.0f}`，"
            f"总收益 `{reference['total_return_pct']:.4f}%`，"
            f"最大回撤 `{reference['max_dd_percent']:.4f}%`，"
            f"Sharpe `{reference['sharpe_ratio']:.4f}`，"
            f"总滑点 `{reference['total_slippage']:,.0f}`，"
            f"交易 `{reference['total_trade_count']:,.0f}`。"
        ),
        "",
        "## 协议汇总",
        "",
        f"- schema表数量：`{summary['schema_table_count']}`",
        f"- schema字段行数：`{summary['schema_rows_total']}`",
        f"- 历史意图ledger行数：`{summary['historical_intent_rows']:,}`",
        f"- 每日控制ledger行数：`{summary['daily_control_rows']:,}`",
        f"- 仍缺真实/仿真柜台字段：`{summary['required_broker_fields_not_available_count']}`",
        f"- 需要人工复核日：`{summary['manual_review_days']}`",
        f"- 禁止新增开仓日：`{summary['no_new_orders_days']}`",
        f"- 保证金watch日：`{summary['watch_margin_days']}`",
        f"- 执行alert日：`{summary['alert_execution_days']}`",
        f"- 下一步：`{summary['current_next_step']}`",
        "",
        "## 影子盘运行许可分布",
        "",
        _to_markdown_table(permission_df, ["shadow_run_permission", "days"], max_rows=20),
        "",
        "## 需要人工复核的代表日期",
        "",
        _to_markdown_table(
            worst_review_days,
            [
                "date",
                "execution_status",
                "shadow_run_permission",
                "audited_trade_count",
                "next_open_adverse_cash",
                "max_projected_margin_usage_pct",
                "required_action",
            ],
            max_rows=12,
        ),
        "",
        "## 仍需接入的柜台字段",
        "",
        ", ".join(f"`{field}`" for field in summary["required_broker_fields_not_available"]),
        "",
        "## 输出文件",
        "",
        _to_markdown_table(outputs_df, ["artifact", "path"], max_rows=20),
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{summary['judgement']['overfit_before']}",
        f"- 运行前继续价值反思：{summary['judgement']['continue_before']}",
        f"- 运行后过拟合反思：{summary['judgement']['overfit_after']}",
        f"- 运行后继续价值反思：{summary['judgement']['continue_after']}",
        "",
        "## 我的判断",
        "",
        "- Stage155的价值不在于让历史曲线更好，而在于把未来每一天变成不可事后篡改的证据。",
        "- 现在最脆弱的不是信号，而是真实成交回报、账户资金和持仓对账能否稳定落地。",
        "- 如果未来仿真盘和影子盘连续偏离，优先怀疑执行与资金约束；只有跨周期、跨月份都稳定失败，才讨论策略版本。",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    inputs = _load_inputs()
    schemas = _build_schemas()
    daily_control = _build_daily_control_ledger(inputs["daily_ledger"])
    historical_intent = _build_historical_intent_ledger(inputs["trade_ledger"], daily_control)
    summary = _build_summary(schemas, historical_intent, daily_control, inputs["stage154_summary"])

    schema_paths = {
        "signal_intent_schema": SIGNAL_INTENT_SCHEMA_PATH,
        "order_event_schema": ORDER_EVENT_SCHEMA_PATH,
        "fill_event_schema": FILL_EVENT_SCHEMA_PATH,
        "position_reconcile_schema": POSITION_RECONCILE_SCHEMA_PATH,
        "account_reconcile_schema": ACCOUNT_RECONCILE_SCHEMA_PATH,
        "exception_schema": EXCEPTION_SCHEMA_PATH,
    }
    for name, frame in schemas.items():
        frame.to_csv(schema_paths[name], index=False, encoding="utf-8-sig")
    historical_intent.to_csv(HISTORICAL_INTENT_LEDGER_PATH, index=False, encoding="utf-8-sig")
    daily_control.to_csv(DAILY_CONTROL_LEDGER_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_sop(summary)
    _write_report(summary, daily_control)

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"wrote: {REPORT_PATH}")
    print(f"wrote: {SOP_PATH}")


if __name__ == "__main__":
    main()
