from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage143_stage78_live_review_pack_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage143_stage78_live_review_pack"
FORMAL_PREFIX: str = "qmt_roll_official_stage78_defensive_formal"
STAGE142_PREFIX: str = "qmt_roll_stage142_stage78_live_monitor_guardrails"
STAGE142_TAG: str = "stage142_stage78_live_monitor_guardrails_v1"

DAILY_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_daily.csv"
TRADES_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_trades_2020_2026_04.csv"
POSITION_CHANGES_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_position_changes_2020_2026_04.csv"
RISK_DIAGNOSTICS_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_entry_risk_diagnostics_2020_2026_04.csv"
SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_summary.json"

THRESHOLDS_PATH: Path = OUTPUT_DIR / f"{STAGE142_PREFIX}_thresholds_{STAGE142_TAG}.csv"
CURRENT_STATUS_PATH: Path = OUTPUT_DIR / f"{STAGE142_PREFIX}_current_status_{STAGE142_TAG}.csv"
MONTHLY_STATE_PATH: Path = OUTPUT_DIR / f"{STAGE142_PREFIX}_monthly_state_{STAGE142_TAG}.csv"

ACTION_ITEMS_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_action_items_{MODEL_TAG}.csv"
RECENT_PRODUCT_ATTRIBUTION_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_recent_product_attribution_{MODEL_TAG}.csv"
RECENT_TRADE_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_recent_trade_summary_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
BRIEF_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_brief_{MODEL_TAG}.md"


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


def _product_from_vt_symbol(vt_symbol: Any) -> str:
    raw = str(vt_symbol)
    if "." not in raw:
        return raw
    symbol, exchange = raw.split(".", 1)
    product = "".join(ch for ch in symbol if ch.isalpha())
    return f"{product}.{exchange}" if product else raw


def _load_inputs() -> dict[str, Any]:
    for path in (
        DAILY_PATH,
        TRADES_PATH,
        POSITION_CHANGES_PATH,
        RISK_DIAGNOSTICS_PATH,
        SUMMARY_PATH,
        THRESHOLDS_PATH,
        CURRENT_STATUS_PATH,
        MONTHLY_STATE_PATH,
    ):
        _require(path)
    daily = _read_csv(DAILY_PATH)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    daily = daily.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    _numeric(daily, ["trade_count", "slippage", "net_pnl", "balance", "ddpercent"])

    trades = _read_csv(TRADES_PATH)
    trades["date"] = pd.to_datetime(trades["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    _numeric(trades, ["price", "volume", "signed_volume"])
    trades["product_vt_symbol"] = trades["vt_symbol"].map(_product_from_vt_symbol)

    positions = _read_csv(POSITION_CHANGES_PATH)
    positions["date"] = pd.to_datetime(positions["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    _numeric(positions, ["trade_count", "turnover", "commission", "slippage", "holding_pnl", "trading_pnl", "total_pnl", "net_pnl"])
    positions["product_vt_symbol"] = positions["vt_symbol"].map(_product_from_vt_symbol)

    risk = _read_csv(RISK_DIAGNOSTICS_PATH)
    risk["date"] = pd.to_datetime(risk["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    _numeric(
        risk,
        [
            "estimated_equity",
            "projected_total_margin_after",
            "actual_margin_amount",
            "same_direction_correlation_active_count",
            "same_direction_correlation_max_corr",
            "portfolio_drawdown_pct",
        ],
    )
    risk["projected_margin_usage_pct"] = (
        risk["projected_total_margin_after"] / risk["estimated_equity"].replace(0.0, np.nan) * 100.0
    ).fillna(0.0)

    thresholds = _read_csv(THRESHOLDS_PATH)
    current_status = _read_csv(CURRENT_STATUS_PATH)
    monthly_state = _read_csv(MONTHLY_STATE_PATH)
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    return {
        "daily": daily,
        "trades": trades,
        "positions": positions,
        "risk": risk,
        "thresholds": thresholds,
        "current_status": current_status,
        "monthly_state": monthly_state,
        "summary": summary,
    }


def _recommend_action(metric: str, status: str) -> tuple[str, str]:
    if metric == "rolling_20d_net_pnl":
        return (
            "复盘最近20个交易日的品种贡献、开平仓原因和是否存在集中亏损，不调整策略参数。",
            "禁止为了修复20日亏损去调止损、调品种黑名单或新增单窗口补丁。",
        )
    if metric == "ddpercent":
        return (
            "检查当前回撤是否接近历史压力区，优先核对持仓集中度和保证金占用。",
            "禁止因单次回撤直接降低长期策略风险预算。",
        )
    if "slippage" in metric:
        return (
            "核对近期滑点、成交量和换月合约，判断是否存在执行质量异常。",
            "禁止把执行异常误判为策略Alpha失效。",
        )
    if "margin" in metric:
        return (
            "核对保证金占用和单笔资金限制，确认是否接近部署资金边界。",
            "禁止在保证金异常期间扩大品种池或增加并发。",
        )
    return (
        f"复盘`{metric}`的异常来源，确认是否为数据、执行或正常策略波动。",
        "禁止用单个监控项直接修改交易逻辑。",
    )


def _build_action_items(thresholds: pd.DataFrame) -> pd.DataFrame:
    priority_map = {"severe": 1, "alert": 2, "watch": 3, "normal": 9, "constant_policy": 9}
    rows: list[dict[str, Any]] = []
    actionable = thresholds[thresholds["status"].isin(["severe", "alert", "watch"])].copy()
    for row in actionable.itertuples(index=False):
        action, forbidden = _recommend_action(str(row.metric), str(row.status))
        rows.append(
            {
                "priority": priority_map.get(str(row.status), 9),
                "status": row.status,
                "metric": row.metric,
                "latest_value": row.latest_value,
                "watch_threshold": row.watch_threshold,
                "alert_threshold": row.alert_threshold,
                "severe_threshold": row.severe_threshold,
                "recommended_action": action,
                "forbidden_action": forbidden,
            }
        )
    if not rows:
        rows.append(
            {
                "priority": 9,
                "status": "normal",
                "metric": "all",
                "latest_value": 0.0,
                "watch_threshold": 0.0,
                "alert_threshold": 0.0,
                "severe_threshold": 0.0,
                "recommended_action": "无异常项，保持Stage78正式基准和常规复盘。",
                "forbidden_action": "仍禁止无证据调参。",
            }
        )
    return pd.DataFrame(rows).sort_values(["priority", "metric"]).reset_index(drop=True)


def _build_recent_product_attribution(daily: pd.DataFrame, positions: pd.DataFrame) -> pd.DataFrame:
    recent_dates = sorted(daily["date"].tail(20).unique())
    frame = positions[positions["date"].isin(recent_dates)].copy()
    if frame.empty:
        return pd.DataFrame()
    summary = (
        frame.groupby("product_vt_symbol", as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            trade_count=("trade_count", "sum"),
            slippage=("slippage", "sum"),
            turnover=("turnover", "sum"),
            active_days=("date", lambda s: int(s.nunique())),
        )
        .sort_values("net_pnl")
        .reset_index(drop=True)
    )
    summary["slippage_per_trade"] = np.where(
        summary["trade_count"] > 0.0,
        summary["slippage"] / summary["trade_count"],
        0.0,
    )
    summary["review_bucket"] = np.where(summary["net_pnl"] < 0.0, "loss_source", "profit_or_flat")
    return summary


def _build_recent_trade_summary(daily: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    recent_dates = sorted(daily["date"].tail(20).unique())
    frame = trades[trades["date"].isin(recent_dates)].copy()
    if frame.empty:
        return pd.DataFrame()
    frame["exit_reason"] = frame["exit_reason"].fillna("open_or_unknown")
    summary = (
        frame.groupby(["product_vt_symbol", "direction", "offset", "exit_reason"], as_index=False)
        .agg(
            trade_count=("trade_id", "count"),
            volume=("volume", "sum"),
            avg_price=("price", "mean"),
            first_date=("date", "min"),
            last_date=("date", "max"),
        )
        .sort_values(["trade_count", "volume"], ascending=False)
        .reset_index(drop=True)
    )
    return summary


def _build_summary_payload(
    inputs: dict[str, Any],
    action_items: pd.DataFrame,
    recent_product: pd.DataFrame,
) -> dict[str, Any]:
    daily = inputs["daily"]
    thresholds = inputs["thresholds"]
    summary = inputs["summary"]
    stage78_full = summary["reference_metrics"]["full_2020_2026"]
    latest = daily.iloc[-1]
    severe_count = int((thresholds["status"] == "severe").sum())
    alert_count = int((thresholds["status"] == "alert").sum())
    if severe_count:
        decision = "pause_new_research_review_first"
    elif alert_count:
        decision = "review_first_keep_stage78"
    else:
        decision = "normal_monitoring_keep_stage78"
    loss_products = recent_product[recent_product["net_pnl"] < 0.0].sort_values("net_pnl") if not recent_product.empty else pd.DataFrame()
    loss_total = float(loss_products["net_pnl"].sum()) if not loss_products.empty else 0.0
    top_loss = (
        loss_products.head(5)["product_vt_symbol"].tolist()
        if not loss_products.empty
        else []
    )
    return {
        "model_tag": MODEL_TAG,
        "is_strategy_change": False,
        "version_ab_skill_triggered": False,
        "stage78_reference": stage78_full,
        "latest_date": latest["date"].date().isoformat(),
        "latest_balance": float(latest["balance"]),
        "latest_ddpercent": float(latest["ddpercent"]),
        "decision": decision,
        "action_item_count": int(len(action_items)),
        "alert_count": alert_count,
        "severe_count": severe_count,
        "recent_20d_net_pnl": float(daily["net_pnl"].tail(20).sum()),
        "recent_20d_trade_count": int(daily["trade_count"].tail(20).sum()),
        "recent_20d_slippage": float(daily["slippage"].tail(20).sum()),
        "recent_20d_loss_total_by_product": loss_total,
        "recent_20d_top_loss_products": top_loss,
        "anti_overfit_boundary": (
            "This live review pack converts monitoring alerts into review tasks only. "
            "It must not change strategy parameters or product pools."
        ),
    }


def _write_brief(
    inputs: dict[str, Any],
    action_items: pd.DataFrame,
    recent_product: pd.DataFrame,
    recent_trades: pd.DataFrame,
    payload: dict[str, Any],
) -> None:
    stage78 = payload["stage78_reference"]
    thresholds = inputs["thresholds"]
    current_status = inputs["current_status"]
    monthly_state = inputs["monthly_state"]
    action_cols = [
        "priority",
        "status",
        "metric",
        "latest_value",
        "watch_threshold",
        "alert_threshold",
        "severe_threshold",
        "recommended_action",
        "forbidden_action",
    ]
    product_cols = [
        "product_vt_symbol",
        "net_pnl",
        "holding_pnl",
        "trading_pnl",
        "trade_count",
        "slippage",
        "slippage_per_trade",
        "review_bucket",
    ]
    trade_cols = ["product_vt_symbol", "direction", "offset", "exit_reason", "trade_count", "volume", "first_date", "last_date"]
    threshold_cols = ["metric", "latest_value", "watch_threshold", "alert_threshold", "severe_threshold", "status"]
    monthly_cols = ["month", "net_pnl", "trade_count", "slippage", "min_ddpercent", "max_rolling_20d_loss", "positive_month"]
    report = f"""# Stage143 Stage78准实盘复盘包

## 结论
- 本阶段不是策略版本，不改Stage78，不触发A/B技能。
- 当前决策：`{payload["decision"]}`。
- 过拟合判断：否。这里只把Stage142监控状态转成复盘任务，不新增交易参数、不筛品种、不补弱窗口。
- 是否有价值继续：是。当前20日净损益处于alert，应该先复盘最近20日亏损来源，而不是继续开发新规则。

## Stage78 正式基准
- 期末权益：{_fmt(stage78.get("end_balance"))}
- 总收益：{_fmt(stage78.get("total_return_pct"))}%
- 最大回撤：{_fmt(stage78.get("max_dd_percent"))}%
- Sharpe：{_fmt(stage78.get("sharpe_ratio"))}
- 总滑点：{_fmt(stage78.get("total_slippage"))}
- 总交易次数：{_fmt(stage78.get("total_trade_count"))}

## 当前状态
{_to_markdown_table(current_status, max_rows=20)}

## 行动项
{_to_markdown_table(action_items, action_cols, max_rows=10)}

## 最近20日品种贡献
{_to_markdown_table(recent_product, product_cols, max_rows=20)}

## 最近20日交易摘要
{_to_markdown_table(recent_trades, trade_cols, max_rows=20)}

## 关键监控阈值
{_to_markdown_table(thresholds, threshold_cols, max_rows=20)}

## 最近6个月
{_to_markdown_table(monthly_state.tail(6), monthly_cols, max_rows=6)}

## 使用边界
- 本复盘包只回答“现在要看什么”，不回答“应该怎么改策略”。
- alert期间允许做归因和数据核对，不允许新增止损、黑名单、品种特例、阈值补丁。
- 若后续进入severe，优先复盘和暂停新研究，不做策略优化。
"""
    BRIEF_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    inputs = _load_inputs()
    action_items = _build_action_items(inputs["thresholds"])
    recent_product = _build_recent_product_attribution(inputs["daily"], inputs["positions"])
    recent_trades = _build_recent_trade_summary(inputs["daily"], inputs["trades"])
    payload = _build_summary_payload(inputs, action_items, recent_product)

    action_items.to_csv(ACTION_ITEMS_PATH, index=False, encoding="utf-8-sig")
    recent_product.to_csv(RECENT_PRODUCT_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    recent_trades.to_csv(RECENT_TRADE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_brief(inputs, action_items, recent_product, recent_trades, payload)

    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    print(f"wrote: {BRIEF_PATH}")


if __name__ == "__main__":
    main()
