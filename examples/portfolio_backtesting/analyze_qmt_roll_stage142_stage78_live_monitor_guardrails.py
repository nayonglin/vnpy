from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage142_stage78_live_monitor_guardrails_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage142_stage78_live_monitor_guardrails"
FORMAL_PREFIX: str = "qmt_roll_official_stage78_defensive_formal"

DAILY_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_daily.csv"
TRADES_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_trades_2020_2026_04.csv"
RISK_DIAGNOSTICS_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_entry_risk_diagnostics_2020_2026_04.csv"
SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_summary.json"

THRESHOLD_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_thresholds_{MODEL_TAG}.csv"
CURRENT_STATUS_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_current_status_{MODEL_TAG}.csv"
MONTHLY_STATE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_state_{MODEL_TAG}.csv"
EXECUTION_COST_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_execution_cost_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

CAPITAL: float = 200_000.0


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
        if pd.api.types.is_numeric_dtype(view[column]):
            view[column] = view[column].map(_fmt)
    return "\n".join(
        [
            "| " + " | ".join(view.columns) + " |",
            "| " + " | ".join(["---"] * len(view.columns)) + " |",
            *["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()],
        ]
    )


def _numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame


def _read_csv(path: Path) -> pd.DataFrame:
    _require(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _load_daily() -> pd.DataFrame:
    daily = _read_csv(DAILY_PATH)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    daily = daily.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    _numeric(
        daily,
        [
            "trade_count",
            "turnover",
            "commission",
            "slippage",
            "trading_pnl",
            "holding_pnl",
            "total_pnl",
            "net_pnl",
            "balance",
            "return",
            "highlevel",
            "drawdown",
            "ddpercent",
        ],
    )
    daily["prev_balance"] = daily["balance"].shift(1).fillna(CAPITAL)
    daily["daily_return_pct"] = daily["net_pnl"] / daily["prev_balance"].replace(0.0, np.nan) * 100.0
    daily["daily_return_pct"] = daily["daily_return_pct"].fillna(0.0)
    daily["slippage_per_trade"] = np.where(
        daily["trade_count"] > 0.0,
        daily["slippage"] / daily["trade_count"],
        0.0,
    )
    daily["rolling_5d_net_pnl"] = daily["net_pnl"].rolling(5, min_periods=3).sum()
    daily["rolling_20d_net_pnl"] = daily["net_pnl"].rolling(20, min_periods=10).sum()
    daily["rolling_63d_net_pnl"] = daily["net_pnl"].rolling(63, min_periods=30).sum()
    daily["rolling_20d_trade_count"] = daily["trade_count"].rolling(20, min_periods=10).sum()
    daily["rolling_20d_slippage"] = daily["slippage"].rolling(20, min_periods=10).sum()
    daily["rolling_20d_slippage_per_trade"] = np.where(
        daily["rolling_20d_trade_count"] > 0.0,
        daily["rolling_20d_slippage"] / daily["rolling_20d_trade_count"],
        0.0,
    )
    daily["month"] = daily["date"].dt.to_period("M").astype(str)
    daily["year"] = daily["date"].dt.year.astype(str)
    return daily


def _load_risk_diagnostics() -> pd.DataFrame:
    risk = _read_csv(RISK_DIAGNOSTICS_PATH)
    risk["date"] = pd.to_datetime(risk["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    _numeric(
        risk,
        [
            "estimated_equity",
            "total_margin_in_use_before",
            "projected_total_margin_after",
            "actual_margin_amount",
            "effective_single_trade_capital_usage_ratio",
            "actual_risk_amount",
            "target_risk_amount",
            "same_direction_correlation_active_count",
            "same_direction_correlation_max_corr",
            "portfolio_drawdown_pct",
            "loss_streak",
            "profit_recovery_streak",
        ],
    )
    risk["projected_margin_usage_pct"] = (
        risk["projected_total_margin_after"] / risk["estimated_equity"].replace(0.0, np.nan) * 100.0
    ).fillna(0.0)
    risk["pre_entry_margin_usage_pct"] = (
        risk["total_margin_in_use_before"] / risk["estimated_equity"].replace(0.0, np.nan) * 100.0
    ).fillna(0.0)
    risk["actual_risk_to_target_pct"] = (
        risk["actual_risk_amount"] / risk["target_risk_amount"].replace(0.0, np.nan) * 100.0
    ).fillna(0.0)
    return risk.sort_values("date").reset_index(drop=True)


def _status_low_is_bad(value: float, watch: float, alert: float, severe: float) -> str:
    if value <= severe:
        return "severe"
    if value <= alert:
        return "alert"
    if value <= watch:
        return "watch"
    return "normal"


def _status_high_is_bad(value: float, watch: float, alert: float, severe: float) -> str:
    if value >= severe:
        return "severe"
    if value >= alert:
        return "alert"
    if value >= watch:
        return "watch"
    return "normal"


def _build_threshold(
    frame: pd.DataFrame,
    metric: str,
    direction: str,
    latest_value: float | None = None,
    source: str = "daily",
    description: str = "",
) -> dict[str, Any]:
    series = pd.to_numeric(frame[metric], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if series.empty:
        watch = alert = severe = historical_min = historical_max = latest = 0.0
    elif series.nunique(dropna=True) <= 1:
        latest = float(series.iloc[-1]) if latest_value is None else latest_value
        constant_value = float(series.iloc[-1])
        return {
            "source": source,
            "metric": metric,
            "direction": direction,
            "description": description,
            "latest_value": latest,
            "watch_threshold": constant_value,
            "alert_threshold": constant_value,
            "severe_threshold": constant_value,
            "historical_min": constant_value,
            "historical_max": constant_value,
            "status": "constant_policy",
        }
    elif direction == "low_is_bad":
        watch = float(series.quantile(0.10))
        alert = float(series.quantile(0.05))
        severe = float(series.quantile(0.01))
        historical_min = float(series.min())
        historical_max = float(series.max())
        latest = float(series.iloc[-1]) if latest_value is None else latest_value
        status = _status_low_is_bad(latest, watch, alert, severe)
        return {
            "source": source,
            "metric": metric,
            "direction": direction,
            "description": description,
            "latest_value": latest,
            "watch_threshold": watch,
            "alert_threshold": alert,
            "severe_threshold": severe,
            "historical_min": historical_min,
            "historical_max": historical_max,
            "status": status,
        }
    else:
        watch = float(series.quantile(0.90))
        alert = float(series.quantile(0.95))
        severe = float(series.quantile(0.99))
        historical_min = float(series.min())
        historical_max = float(series.max())
        latest = float(series.iloc[-1]) if latest_value is None else latest_value
        status = _status_high_is_bad(latest, watch, alert, severe)
    return {
        "source": source,
        "metric": metric,
        "direction": direction,
        "description": description,
        "latest_value": latest,
        "watch_threshold": watch,
        "alert_threshold": alert,
        "severe_threshold": severe,
        "historical_min": historical_min,
        "historical_max": historical_max,
        "status": status,
    }


def _build_thresholds(daily: pd.DataFrame, risk: pd.DataFrame) -> pd.DataFrame:
    latest = daily.iloc[-1]
    risk_latest = risk.iloc[-1] if not risk.empty else pd.Series(dtype=float)
    rows = [
        _build_threshold(daily, "daily_return_pct", "low_is_bad", source="daily", description="单日收益率过低"),
        _build_threshold(daily, "rolling_5d_net_pnl", "low_is_bad", source="daily", description="5日净损益冷启动"),
        _build_threshold(daily, "rolling_20d_net_pnl", "low_is_bad", source="daily", description="20日净损益异常"),
        _build_threshold(daily, "rolling_63d_net_pnl", "low_is_bad", source="daily", description="63日净损益异常"),
        _build_threshold(daily, "ddpercent", "low_is_bad", source="daily", description="组合回撤百分比"),
        _build_threshold(daily, "rolling_20d_trade_count", "high_is_bad", source="daily", description="20日交易频率过高"),
        _build_threshold(daily, "rolling_20d_slippage", "high_is_bad", source="daily", description="20日滑点过高"),
        _build_threshold(
            daily,
            "rolling_20d_slippage_per_trade",
            "high_is_bad",
            source="daily",
            description="20日单笔滑点过高",
        ),
    ]
    if not risk.empty:
        rows.extend(
            [
                _build_threshold(
                    risk,
                    "projected_margin_usage_pct",
                    "high_is_bad",
                    latest_value=_safe_float(risk_latest.get("projected_margin_usage_pct")),
                    source="entry_risk",
                    description="入场后预计保证金占权益比例",
                ),
                _build_threshold(
                    risk,
                    "effective_single_trade_capital_usage_ratio",
                    "high_is_bad",
                    latest_value=_safe_float(risk_latest.get("effective_single_trade_capital_usage_ratio")),
                    source="entry_risk",
                    description="单笔资金使用比例",
                ),
                _build_threshold(
                    risk,
                    "same_direction_correlation_active_count",
                    "high_is_bad",
                    latest_value=_safe_float(risk_latest.get("same_direction_correlation_active_count")),
                    source="entry_risk",
                    description="同方向相关持仓数量",
                ),
                _build_threshold(
                    risk,
                    "same_direction_correlation_max_corr",
                    "high_is_bad",
                    latest_value=_safe_float(risk_latest.get("same_direction_correlation_max_corr")),
                    source="entry_risk",
                    description="同方向最高相关性",
                ),
            ]
        )
    thresholds = pd.DataFrame(rows)
    priority = {"severe": 0, "alert": 1, "watch": 2, "normal": 3, "constant_policy": 4}
    thresholds["status_priority"] = thresholds["status"].map(priority).fillna(9).astype(int)
    return thresholds.sort_values(["status_priority", "source", "metric"]).reset_index(drop=True)


def _build_current_status(thresholds: pd.DataFrame, daily: pd.DataFrame, risk: pd.DataFrame) -> pd.DataFrame:
    latest = daily.iloc[-1]
    rows = [
        {
            "status_item": "latest_daily_date",
            "value": latest["date"].date().isoformat(),
            "status": "info",
            "note": "Stage78正式回测最新交易日",
        },
        {
            "status_item": "latest_balance",
            "value": float(latest["balance"]),
            "status": "info",
            "note": "全周期权益，不是2026单独起跑权益",
        },
        {
            "status_item": "current_ddpercent",
            "value": float(latest["ddpercent"]),
            "status": thresholds.loc[thresholds["metric"].eq("ddpercent"), "status"].iloc[0],
            "note": "当前组合回撤百分比",
        },
        {
            "status_item": "rolling_20d_net_pnl",
            "value": float(latest["rolling_20d_net_pnl"]),
            "status": thresholds.loc[thresholds["metric"].eq("rolling_20d_net_pnl"), "status"].iloc[0],
            "note": "20日净损益",
        },
        {
            "status_item": "rolling_63d_net_pnl",
            "value": float(latest["rolling_63d_net_pnl"]),
            "status": thresholds.loc[thresholds["metric"].eq("rolling_63d_net_pnl"), "status"].iloc[0],
            "note": "63日净损益",
        },
    ]
    if not risk.empty:
        risk_latest = risk.iloc[-1]
        rows.extend(
            [
                {
                    "status_item": "latest_entry_date",
                    "value": risk_latest["date"].date().isoformat(),
                    "status": "info",
                    "note": "最近一次入场诊断日期",
                },
                {
                    "status_item": "projected_margin_usage_pct",
                    "value": float(risk_latest["projected_margin_usage_pct"]),
                    "status": thresholds.loc[thresholds["metric"].eq("projected_margin_usage_pct"), "status"].iloc[0],
                    "note": "最近入场后预计保证金占权益",
                },
            ]
        )
    status_counts = thresholds.groupby("status", as_index=False).agg(metric_count=("metric", "count"))
    for row in status_counts.itertuples(index=False):
        rows.append(
            {
                "status_item": f"threshold_count_{row.status}",
                "value": int(row.metric_count),
                "status": str(row.status),
                "note": "阈值表状态计数",
            }
        )
    return pd.DataFrame(rows)


def _build_monthly_state(daily: pd.DataFrame) -> pd.DataFrame:
    monthly = (
        daily.groupby("month", as_index=False)
        .agg(
            start_date=("date", "min"),
            end_date=("date", "max"),
            net_pnl=("net_pnl", "sum"),
            trade_count=("trade_count", "sum"),
            slippage=("slippage", "sum"),
            min_ddpercent=("ddpercent", "min"),
            max_rolling_20d_loss=("rolling_20d_net_pnl", "min"),
            end_balance=("balance", "last"),
        )
        .sort_values("month")
        .reset_index(drop=True)
    )
    monthly["slippage_per_trade"] = np.where(
        monthly["trade_count"] > 0.0,
        monthly["slippage"] / monthly["trade_count"],
        0.0,
    )
    monthly["positive_month"] = monthly["net_pnl"] > 0.0
    monthly["month_return_on_capital_pct"] = monthly["net_pnl"] / CAPITAL * 100.0
    return monthly


def _build_execution_cost(trades: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    frame = trades.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    frame["product_vt_symbol"] = frame["symbol"].astype(str).str.extract(r"^([A-Za-z]+)", expand=False).fillna("")
    frame["exchange"] = frame["exchange"].astype(str)
    frame["product_vt_symbol"] = frame["product_vt_symbol"] + "." + frame["exchange"]
    _numeric(frame, ["price", "volume", "signed_volume"])

    daily_cost = daily[daily["trade_count"] > 0.0].copy()
    cost_summary = pd.DataFrame(
        [
            {
                "scope": "daily_trade_days",
                "sample_count": int(len(daily_cost)),
                "total_trade_count": float(daily["trade_count"].sum()),
                "total_slippage": float(daily["slippage"].sum()),
                "median_slippage_per_trade": float(daily_cost["slippage_per_trade"].median())
                if not daily_cost.empty
                else 0.0,
                "p90_slippage_per_trade": float(daily_cost["slippage_per_trade"].quantile(0.90))
                if not daily_cost.empty
                else 0.0,
                "p95_slippage_per_trade": float(daily_cost["slippage_per_trade"].quantile(0.95))
                if not daily_cost.empty
                else 0.0,
            }
        ]
    )
    by_product = (
        frame.groupby("product_vt_symbol", as_index=False)
        .agg(
            trade_count=("trade_id", "count"),
            total_volume=("volume", "sum"),
        )
        .sort_values("trade_count", ascending=False)
        .head(12)
    )
    by_product["scope"] = "top_trade_products"
    by_product.rename(columns={"product_vt_symbol": "bucket"}, inplace=True)
    return pd.concat([cost_summary, by_product], ignore_index=True, sort=False)


def _build_summary_payload(
    thresholds: pd.DataFrame,
    current_status: pd.DataFrame,
    monthly_state: pd.DataFrame,
    summary: dict[str, Any],
) -> dict[str, Any]:
    stage78_full = summary["reference_metrics"]["full_2020_2026"]
    status_counts = thresholds.groupby("status").size().to_dict()
    latest_month = monthly_state.iloc[-1].to_dict() if not monthly_state.empty else {}
    return {
        "model_tag": MODEL_TAG,
        "is_strategy_change": False,
        "version_ab_skill_triggered": False,
        "stage78_reference": stage78_full,
        "status_counts": {str(key): int(value) for key, value in status_counts.items()},
        "latest_month": latest_month,
        "current_status": current_status.to_dict(orient="records"),
        "threshold_count": int(len(thresholds)),
        "decision": "monitor_only_keep_stage78",
        "anti_overfit_boundary": (
            "Guardrails are distributional monitoring thresholds only. They do not alter entries, exits, sizing, "
            "or product selection."
        ),
    }


def _write_report(
    thresholds: pd.DataFrame,
    current_status: pd.DataFrame,
    monthly_state: pd.DataFrame,
    execution_cost: pd.DataFrame,
    payload: dict[str, Any],
) -> None:
    stage78 = payload["stage78_reference"]
    threshold_cols = [
        "source",
        "metric",
        "description",
        "latest_value",
        "watch_threshold",
        "alert_threshold",
        "severe_threshold",
        "historical_min",
        "historical_max",
        "status",
    ]
    current_cols = ["status_item", "value", "status", "note"]
    monthly_cols = [
        "month",
        "net_pnl",
        "trade_count",
        "slippage",
        "slippage_per_trade",
        "min_ddpercent",
        "max_rolling_20d_loss",
        "month_return_on_capital_pct",
        "positive_month",
    ]
    report = f"""# Stage142 Stage78准实盘监控阈值审计

## 结论
- 本阶段不是策略版本，不改Stage78，不触发A/B技能；它只生成准实盘监控边界。
- 过拟合判断：否。阈值来自历史分布分位数，只用于预警，不参与下单、止损、仓位或品种选择。
- 是否有价值继续：是。正式版本需要知道“当前异常”与“历史正常波动”的边界，否则后续容易把正常回撤误判成策略失效。
- 当前决策：`{payload["decision"]}`。

## Stage78 正式基准
- 期末权益：{_fmt(stage78.get("end_balance"))}
- 总收益：{_fmt(stage78.get("total_return_pct"))}%
- 最大回撤：{_fmt(stage78.get("max_dd_percent"))}%
- Sharpe：{_fmt(stage78.get("sharpe_ratio"))}
- 总滑点：{_fmt(stage78.get("total_slippage"))}
- 总交易次数：{_fmt(stage78.get("total_trade_count"))}

## 当前状态
{_to_markdown_table(current_status, current_cols, max_rows=30)}

## 监控阈值
{_to_markdown_table(thresholds, threshold_cols, max_rows=30)}

## 最近12个月
{_to_markdown_table(monthly_state.tail(12), monthly_cols, max_rows=12)}

## 执行成本摘要
{_to_markdown_table(execution_cost, max_rows=20)}

## 使用边界
- `watch`：进入复盘观察，不自动降仓。
- `alert`：要求人工检查交易、滑点、保证金、是否有数据异常。
- `severe`：暂停新增研究结论，把当期当成正式复盘对象；仍不代表自动停机。
- 这些阈值不是交易参数，不允许为了改善回测而调分位数。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    for path in (DAILY_PATH, TRADES_PATH, RISK_DIAGNOSTICS_PATH, SUMMARY_PATH):
        _require(path)
    daily = _load_daily()
    risk = _load_risk_diagnostics()
    trades = _read_csv(TRADES_PATH)
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))

    thresholds = _build_thresholds(daily, risk)
    current_status = _build_current_status(thresholds, daily, risk)
    monthly_state = _build_monthly_state(daily)
    execution_cost = _build_execution_cost(trades, daily)
    payload = _build_summary_payload(thresholds, current_status, monthly_state, summary)

    thresholds.to_csv(THRESHOLD_PATH, index=False, encoding="utf-8-sig")
    current_status.to_csv(CURRENT_STATUS_PATH, index=False, encoding="utf-8-sig")
    monthly_state.to_csv(MONTHLY_STATE_PATH, index=False, encoding="utf-8-sig")
    execution_cost.to_csv(EXECUTION_COST_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_report(thresholds, current_status, monthly_state, execution_cost, payload)

    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
