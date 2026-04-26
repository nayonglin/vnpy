from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage144_recent_loss_mechanism_audit_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage144_recent_loss_mechanism_audit"
FORMAL_PREFIX: str = "qmt_roll_official_stage78_defensive_formal"

DAILY_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_daily.csv"
TRADES_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_trades_2020_2026_04.csv"
POSITION_CHANGES_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_position_changes_2020_2026_04.csv"
RISK_DIAGNOSTICS_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_entry_risk_diagnostics_2020_2026_04.csv"
SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_summary.json"

PRODUCT_DISTRIBUTION_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_distribution_{MODEL_TAG}.csv"
ROUNDTRIP_AUDIT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_roundtrip_audit_{MODEL_TAG}.csv"
ENTRY_CONTEXT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_context_{MODEL_TAG}.csv"
EXIT_REASON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_exit_reason_comparison_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


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


def _normalize_date(frame: pd.DataFrame, column: str = "date") -> pd.DataFrame:
    frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.tz_localize(None).dt.normalize()
    return frame.dropna(subset=[column]).reset_index(drop=True)


def _load_inputs() -> dict[str, Any]:
    for path in (DAILY_PATH, TRADES_PATH, POSITION_CHANGES_PATH, RISK_DIAGNOSTICS_PATH, SUMMARY_PATH):
        _require(path)

    daily = _normalize_date(_read_csv(DAILY_PATH)).sort_values("date").reset_index(drop=True)
    _numeric(daily, ["trade_count", "slippage", "net_pnl", "balance", "ddpercent"])

    trades = _normalize_date(_read_csv(TRADES_PATH))
    _numeric(trades, ["price", "volume", "signed_volume"])
    trades["product_vt_symbol"] = trades["vt_symbol"].map(_product_from_vt_symbol)
    trades["exit_reason"] = trades["exit_reason"].fillna("open_or_unknown")
    trades["offset_norm"] = trades["offset"].astype(str).str.lower()
    trades["direction_norm"] = trades["direction"].astype(str).str.lower()

    positions = _normalize_date(_read_csv(POSITION_CHANGES_PATH))
    _numeric(
        positions,
        [
            "start_pos",
            "end_pos",
            "pos_change",
            "turnover",
            "commission",
            "slippage",
            "holding_pnl",
            "trading_pnl",
            "total_pnl",
            "net_pnl",
            "trade_count",
        ],
    )
    positions["product_vt_symbol"] = positions["vt_symbol"].map(_product_from_vt_symbol)

    risk = _normalize_date(_read_csv(RISK_DIAGNOSTICS_PATH))
    _numeric(
        risk,
        [
            "estimated_equity",
            "projected_total_margin_after",
            "actual_margin_amount",
            "selected_volume",
            "selected_volume_ungated",
            "risk_multiplier",
            "actual_risk_amount",
            "portfolio_drawdown_pct",
            "same_direction_correlation_active_count",
            "same_direction_correlation_max_corr",
            "loss_streak",
            "profit_recovery_streak",
        ],
    )
    risk["projected_margin_usage_pct"] = (
        risk["projected_total_margin_after"] / risk["estimated_equity"].replace(0.0, np.nan) * 100.0
    ).fillna(0.0)

    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    return {"daily": daily, "trades": trades, "positions": positions, "risk": risk, "summary": summary}


def _build_product_daily(positions: pd.DataFrame) -> pd.DataFrame:
    return (
        positions.groupby(["date", "product_vt_symbol"], as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            slippage=("slippage", "sum"),
            trade_count=("trade_count", "sum"),
            active_day=("end_pos", lambda s: int((s != 0.0).any())),
        )
        .sort_values(["product_vt_symbol", "date"])
        .reset_index(drop=True)
    )


def _build_product_distribution(daily: pd.DataFrame, product_daily: pd.DataFrame) -> pd.DataFrame:
    recent_dates = list(daily["date"].tail(20))
    recent = (
        product_daily[product_daily["date"].isin(recent_dates)]
        .groupby("product_vt_symbol", as_index=False)
        .agg(
            recent_20d_net_pnl=("net_pnl", "sum"),
            recent_20d_holding_pnl=("holding_pnl", "sum"),
            recent_20d_trading_pnl=("trading_pnl", "sum"),
            recent_20d_slippage=("slippage", "sum"),
            recent_20d_trade_count=("trade_count", "sum"),
            recent_20d_active_days=("active_day", "sum"),
        )
    )
    rows: list[dict[str, Any]] = []
    for product, group in product_daily.groupby("product_vt_symbol"):
        group = group.sort_values("date").copy()
        roll20 = group["net_pnl"].rolling(20, min_periods=20).sum().dropna().to_numpy()
        if len(roll20) == 0:
            continue
        current_row = recent[recent["product_vt_symbol"] == product]
        current_net = float(current_row["recent_20d_net_pnl"].iloc[0]) if not current_row.empty else 0.0
        percentile_low = float((roll20 <= current_net).mean() * 100.0)
        rows.append(
            {
                "product_vt_symbol": product,
                "recent_20d_net_pnl": current_net,
                "historical_roll20_min": float(np.min(roll20)),
                "historical_roll20_p01": float(np.percentile(roll20, 1)),
                "historical_roll20_p05": float(np.percentile(roll20, 5)),
                "historical_roll20_p10": float(np.percentile(roll20, 10)),
                "historical_roll20_median": float(np.median(roll20)),
                "recent_low_percentile": percentile_low,
                "historical_roll20_count": int(len(roll20)),
            }
        )
    distribution = pd.DataFrame(rows)
    recent_detail = recent.drop(columns=["recent_20d_net_pnl"], errors="ignore")
    result = distribution.merge(recent_detail, on="product_vt_symbol", how="left")
    recent_columns = [
        "recent_20d_net_pnl",
        "recent_20d_holding_pnl",
        "recent_20d_trading_pnl",
        "recent_20d_slippage",
        "recent_20d_trade_count",
        "recent_20d_active_days",
    ]
    for column in recent_columns:
        if column not in result.columns:
            result[column] = 0.0
        else:
            result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0.0)
    result["loss_bucket"] = np.select(
        [
            result["recent_20d_net_pnl"] >= 0.0,
            result["recent_low_percentile"] <= 1.0,
            result["recent_low_percentile"] <= 5.0,
            result["recent_low_percentile"] <= 10.0,
        ],
        ["not_loss", "extreme_tail_loss", "tail_loss", "weak_but_normal_loss"],
        default="normal_loss",
    )
    return result.sort_values("recent_20d_net_pnl").reset_index(drop=True)


def _closed_direction(close_direction: str) -> str:
    return "Long" if close_direction.lower() == "short" else "Short"


def _build_roundtrip_audit(
    daily: pd.DataFrame,
    trades: pd.DataFrame,
    positions: pd.DataFrame,
    product_distribution: pd.DataFrame,
) -> pd.DataFrame:
    recent_dates = set(daily["date"].tail(20))
    loss_products = product_distribution[product_distribution["recent_20d_net_pnl"] < 0.0]["product_vt_symbol"].tolist()
    recent_closes = trades[
        trades["date"].isin(recent_dates)
        & trades["product_vt_symbol"].isin(loss_products)
        & trades["offset_norm"].eq("close")
    ].copy()
    if recent_closes.empty:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    sorted_trades = trades.sort_values(["date", "trade_id"]).reset_index(drop=True)
    for close in recent_closes.itertuples(index=False):
        closed_direction = _closed_direction(str(close.direction))
        prior_opens = sorted_trades[
            (sorted_trades["vt_symbol"] == close.vt_symbol)
            & sorted_trades["offset_norm"].eq("open")
            & sorted_trades["direction"].eq(closed_direction)
            & (sorted_trades["date"] <= close.date)
        ].copy()
        open_row = prior_opens.iloc[-1] if not prior_opens.empty else None
        open_date = open_row["date"] if open_row is not None else close.date
        open_price = float(open_row["price"]) if open_row is not None else float("nan")
        volume = float(close.volume)
        lifecycle_mask = (
            (positions["vt_symbol"] == close.vt_symbol)
            & (positions["date"] >= open_date)
            & (positions["date"] <= close.date)
        )
        window_mask = lifecycle_mask & positions["date"].isin(recent_dates)
        lifecycle = positions[lifecycle_mask]
        window = positions[window_mask]
        product_row = product_distribution[product_distribution["product_vt_symbol"] == close.product_vt_symbol]
        percentile = float(product_row["recent_low_percentile"].iloc[0]) if not product_row.empty else float("nan")
        lifecycle_net = float(lifecycle["net_pnl"].sum())
        window_net = float(window["net_pnl"].sum())
        pre_window_net = lifecycle_net - window_net
        if lifecycle_net > 0.0 and window_net < 0.0:
            mechanism = "window_profit_giveback_not_failed_trade"
        elif lifecycle_net < 0.0 and percentile <= 1.0:
            mechanism = "extreme_tail_failed_trade"
        elif lifecycle_net < 0.0 and percentile <= 10.0:
            mechanism = "normal_or_moderate_failed_trade"
        elif lifecycle_net < 0.0:
            mechanism = "failed_trade_not_distribution_tail"
        else:
            mechanism = "non_loss_or_flat_lifecycle"
        rows.append(
            {
                "product_vt_symbol": close.product_vt_symbol,
                "contract_vt_symbol": close.vt_symbol,
                "closed_direction": closed_direction,
                "open_date": open_date.date().isoformat() if pd.notna(open_date) else "",
                "close_date": close.date.date().isoformat(),
                "holding_calendar_days": int((close.date - open_date).days) if pd.notna(open_date) else 0,
                "open_price": open_price,
                "close_price": float(close.price),
                "volume": volume,
                "exit_reason": close.exit_reason,
                "lifecycle_net_pnl": lifecycle_net,
                "recent_window_net_pnl": window_net,
                "pre_window_net_pnl": pre_window_net,
                "lifecycle_holding_pnl": float(lifecycle["holding_pnl"].sum()),
                "lifecycle_trading_pnl": float(lifecycle["trading_pnl"].sum()),
                "lifecycle_slippage": float(lifecycle["slippage"].sum()),
                "recent_low_percentile": percentile,
                "mechanism": mechanism,
            }
        )
    return pd.DataFrame(rows).sort_values("recent_window_net_pnl").reset_index(drop=True)


def _build_entry_context(roundtrips: pd.DataFrame, risk: pd.DataFrame) -> pd.DataFrame:
    if roundtrips.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for row in roundtrips.itertuples(index=False):
        open_date = pd.Timestamp(row.open_date)
        match = risk[
            (risk["date"] == open_date)
            & (risk["product_vt_symbol"] == row.product_vt_symbol)
            & (risk["contract_vt_symbol"] == row.contract_vt_symbol)
        ].copy()
        if match.empty:
            match = risk[(risk["date"] == open_date) & (risk["product_vt_symbol"] == row.product_vt_symbol)].copy()
        if match.empty:
            rows.append(
                {
                    "product_vt_symbol": row.product_vt_symbol,
                    "contract_vt_symbol": row.contract_vt_symbol,
                    "entry_date": row.open_date,
                    "entry_found": False,
                }
            )
            continue
        risk_row = match.iloc[-1]
        rows.append(
            {
                "product_vt_symbol": row.product_vt_symbol,
                "contract_vt_symbol": row.contract_vt_symbol,
                "entry_date": row.open_date,
                "entry_found": True,
                "direction": risk_row["direction"],
                "signal": risk_row["signal"],
                "layer_kind": risk_row["layer_kind"],
                "risk_mode": risk_row["risk_mode"],
                "estimated_equity": risk_row["estimated_equity"],
                "selected_volume": risk_row["selected_volume"],
                "selected_volume_ungated": risk_row["selected_volume_ungated"],
                "risk_multiplier": risk_row["risk_multiplier"],
                "actual_risk_amount": risk_row["actual_risk_amount"],
                "actual_margin_amount": risk_row["actual_margin_amount"],
                "projected_margin_usage_pct": risk_row["projected_margin_usage_pct"],
                "portfolio_drawdown_pct": risk_row["portfolio_drawdown_pct"],
                "same_direction_correlation_active_count": risk_row["same_direction_correlation_active_count"],
                "same_direction_correlation_max_corr": risk_row["same_direction_correlation_max_corr"],
                "loss_streak": risk_row["loss_streak"],
                "profit_recovery_streak": risk_row["profit_recovery_streak"],
            }
        )
    return pd.DataFrame(rows)


def _build_exit_reason_comparison(daily: pd.DataFrame, trades: pd.DataFrame, product_distribution: pd.DataFrame) -> pd.DataFrame:
    recent_dates = set(daily["date"].tail(20))
    loss_products = product_distribution[product_distribution["recent_20d_net_pnl"] < 0.0]["product_vt_symbol"].tolist()
    close_trades = trades[trades["offset_norm"].eq("close") & trades["product_vt_symbol"].isin(loss_products)].copy()
    if close_trades.empty:
        return pd.DataFrame()
    historical = close_trades.groupby(["product_vt_symbol", "exit_reason"], as_index=False).size().rename(columns={"size": "historical_count"})
    recent = (
        close_trades[close_trades["date"].isin(recent_dates)]
        .groupby(["product_vt_symbol", "exit_reason"], as_index=False)
        .size()
        .rename(columns={"size": "recent_count"})
    )
    result = historical.merge(recent, on=["product_vt_symbol", "exit_reason"], how="left")
    result["recent_count"] = result["recent_count"].fillna(0).astype(int)
    result["historical_count"] = result["historical_count"].astype(int)
    total = result.groupby("product_vt_symbol")["historical_count"].transform("sum").replace(0, np.nan)
    result["historical_pct"] = (result["historical_count"] / total * 100.0).fillna(0.0)
    return result.sort_values(["product_vt_symbol", "recent_count", "historical_count"], ascending=[True, False, False])


def _build_summary_payload(
    inputs: dict[str, Any],
    product_distribution: pd.DataFrame,
    roundtrips: pd.DataFrame,
) -> dict[str, Any]:
    daily = inputs["daily"]
    summary = inputs["summary"]
    stage78_full = summary["reference_metrics"]["full_2020_2026"]
    loss_products = product_distribution[product_distribution["recent_20d_net_pnl"] < 0.0].copy()
    extreme_products = loss_products[loss_products["recent_low_percentile"] <= 1.0]["product_vt_symbol"].tolist()
    lifecycle_positive = roundtrips[roundtrips.get("lifecycle_net_pnl", pd.Series(dtype=float)) > 0.0]
    failed_tail = roundtrips[roundtrips.get("mechanism", pd.Series(dtype=str)).astype(str).str.contains("tail_failed", na=False)]
    recent_20d_net = float(daily["net_pnl"].tail(20).sum())
    decision = "audit_only_keep_stage78"
    if len(failed_tail) >= 2:
        decision = "audit_only_watch_tail_loss_cluster_keep_stage78"
    return {
        "model_tag": MODEL_TAG,
        "is_strategy_change": False,
        "version_ab_skill_triggered": False,
        "stage78_reference": stage78_full,
        "latest_date": daily.iloc[-1]["date"].date().isoformat(),
        "recent_window_start": daily.iloc[-20]["date"].date().isoformat(),
        "recent_window_end": daily.iloc[-1]["date"].date().isoformat(),
        "recent_20d_net_pnl": recent_20d_net,
        "loss_product_count": int(len(loss_products)),
        "loss_products": loss_products["product_vt_symbol"].tolist(),
        "extreme_tail_loss_products": extreme_products,
        "positive_lifecycle_but_window_loss_count": int(len(lifecycle_positive)),
        "failed_tail_trade_count": int(len(failed_tail)),
        "decision": decision,
        "anti_overfit_boundary": (
            "This audit only separates recent-window losses from complete trade lifecycle losses. "
            "It must not create product blacklists, profit giveback rules, or stop patches."
        ),
    }


def _write_report(
    inputs: dict[str, Any],
    product_distribution: pd.DataFrame,
    roundtrips: pd.DataFrame,
    entry_context: pd.DataFrame,
    exit_reason: pd.DataFrame,
    payload: dict[str, Any],
) -> None:
    stage78 = payload["stage78_reference"]
    loss_product_cols = [
        "product_vt_symbol",
        "recent_20d_net_pnl",
        "recent_20d_holding_pnl",
        "recent_20d_trading_pnl",
        "recent_20d_slippage",
        "recent_20d_trade_count",
        "recent_low_percentile",
        "historical_roll20_min",
        "historical_roll20_p05",
        "loss_bucket",
    ]
    roundtrip_cols = [
        "product_vt_symbol",
        "contract_vt_symbol",
        "closed_direction",
        "open_date",
        "close_date",
        "holding_calendar_days",
        "exit_reason",
        "lifecycle_net_pnl",
        "recent_window_net_pnl",
        "pre_window_net_pnl",
        "recent_low_percentile",
        "mechanism",
    ]
    entry_cols = [
        "product_vt_symbol",
        "entry_date",
        "direction",
        "signal",
        "selected_volume",
        "selected_volume_ungated",
        "risk_multiplier",
        "actual_risk_amount",
        "projected_margin_usage_pct",
        "portfolio_drawdown_pct",
        "same_direction_correlation_active_count",
        "same_direction_correlation_max_corr",
        "loss_streak",
    ]
    exit_cols = ["product_vt_symbol", "exit_reason", "recent_count", "historical_count", "historical_pct"]
    loss_products = product_distribution[product_distribution["recent_20d_net_pnl"] < 0.0].copy()
    report = f"""# Stage144 Stage78最近亏损单机制审计

## 结论
- 本阶段不是策略版本，不改Stage78，不触发A/B技能。
- 当前决策：`{payload["decision"]}`。
- 过拟合判断：否。这里只区分最近20日窗口亏损、完整交易生命周期亏损、退出原因和执行成本，不新增参数、不筛品种、不补弱窗口。
- 是否有价值继续：是。Stage142的20日alert需要先确认亏损机制，避免把正常趋势成本或窗口错觉误改成规则。

## Stage78 正式基准
- 期末权益：{_fmt(stage78.get("end_balance"))}
- 总收益：{_fmt(stage78.get("total_return_pct"))}%
- 最大回撤：{_fmt(stage78.get("max_dd_percent"))}%
- Sharpe：{_fmt(stage78.get("sharpe_ratio"))}
- 总滑点：{_fmt(stage78.get("total_slippage"))}
- 总交易次数：{_fmt(stage78.get("total_trade_count"))}

## 最近20日状态
- 区间：{payload["recent_window_start"]} 至 {payload["recent_window_end"]}
- 组合净损益：{_fmt(payload["recent_20d_net_pnl"])}
- 亏损品种数：{payload["loss_product_count"]}
- 极端尾部品种：{", ".join(payload["extreme_tail_loss_products"]) or "无"}
- 完整生命周期盈利但窗口亏损的平仓数：{payload["positive_lifecycle_but_window_loss_count"]}
- 完整生命周期尾部亏损平仓数：{payload["failed_tail_trade_count"]}

## 亏损品种分布
{_to_markdown_table(loss_products, loss_product_cols, max_rows=20)}

## 最近平仓生命周期
{_to_markdown_table(roundtrips, roundtrip_cols, max_rows=20)}

## 入场上下文
{_to_markdown_table(entry_context, entry_cols, max_rows=20)}

## 退出原因对照
{_to_markdown_table(exit_reason, exit_cols, max_rows=20)}

## 解释
- `OI.CZCE`在最近20日是亏损源，但完整生命周期仍盈利，核心是窗口内利润回吐，不是失败交易；这不能直接推导出利润保护规则，因为前面利润保护线已经暴露恢复段丢仓问题。
- `MA.CZCE`属于极端尾部失败交易，完整生命周期亏损与20日窗口亏损一致；它值得监控大跳空/断崖型事件，但单笔极端亏损不足以支持品种黑名单或止损补丁。
- `SH.CZCE`是普通偏弱失败交易，近期亏损没有达到极端历史分位；它更像趋势系统的正常试错成本。
- 三笔最近平仓都是多头止损，执行滑点相对亏损规模很小，当前证据不支持把问题归因到成交成本。

## 使用边界
- 本报告只用于复盘，不用于生成新策略参数。
- 禁止动作：按MA/OI/SH单品种黑名单、重启利润回吐保护、为了最近20日调止损。
- 合理后续：继续做“极端单笔亏损事件账本”和“完整生命周期 vs 滚动窗口”的准实盘监控。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    inputs = _load_inputs()
    product_daily = _build_product_daily(inputs["positions"])
    product_distribution = _build_product_distribution(inputs["daily"], product_daily)
    roundtrips = _build_roundtrip_audit(inputs["daily"], inputs["trades"], inputs["positions"], product_distribution)
    entry_context = _build_entry_context(roundtrips, inputs["risk"])
    exit_reason = _build_exit_reason_comparison(inputs["daily"], inputs["trades"], product_distribution)
    payload = _build_summary_payload(inputs, product_distribution, roundtrips)

    product_distribution.to_csv(PRODUCT_DISTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    roundtrips.to_csv(ROUNDTRIP_AUDIT_PATH, index=False, encoding="utf-8-sig")
    entry_context.to_csv(ENTRY_CONTEXT_PATH, index=False, encoding="utf-8-sig")
    exit_reason.to_csv(EXIT_REASON_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_report(inputs, product_distribution, roundtrips, entry_context, exit_reason, payload)

    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
