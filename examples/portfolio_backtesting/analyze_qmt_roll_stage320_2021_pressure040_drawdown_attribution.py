from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_backtest_runtime_guard import assert_stage196_database_sentinels
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_manifest,
    build_official_stage78_overrides,
)
from qmt_universe import PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR, build_positions_df, build_trades_df
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO
from run_qmt_roll_stage310_stage78_1_drawdown_gate_engine_validation import _pressure040_overrides


MODEL_TAG = "stage320_2021_pressure040_drawdown_attribution_v1"
OUTPUT_PREFIX = "qmt_roll_stage320_2021_pressure040_drawdown_attribution"
LINE_ID = "futures_trend_drawdown30_preserve_return"
ANALYSIS_END = datetime(2021, 8, 31)


def _product_from_vt_symbol(vt_symbol: str) -> str:
    symbol, _, exchange = vt_symbol.partition(".")
    match = re.match(r"[A-Za-z]+", symbol)
    root = match.group(0) if match else symbol
    return f"{root}.{exchange}" if exchange else root


def _drawdown_window(analysis_df: pd.DataFrame) -> dict[str, Any]:
    curve = analysis_df[["balance"]].copy().sort_index()
    curve["peak"] = curve["balance"].cummax()
    curve["dd_pct"] = curve["balance"] / curve["peak"] - 1.0
    trough = curve.loc[curve["dd_pct"].idxmin()]
    peak_candidates = curve.loc[curve.index <= trough.name]
    peak = peak_candidates.loc[peak_candidates["balance"].idxmax()]
    return {
        "peak_date": pd.Timestamp(peak.name).date(),
        "peak_balance": float(peak["balance"]),
        "trough_date": pd.Timestamp(trough.name).date(),
        "trough_balance": float(trough["balance"]),
        "max_dd_pct": float(trough["dd_pct"] * 100.0),
        "curve": curve,
    }


def _summarize_positions(positions_df: pd.DataFrame, peak_date: Any, trough_date: Any) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = positions_df.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame["product"] = frame["vt_symbol"].map(_product_from_vt_symbol)
    window = frame[(frame["date"] > peak_date) & (frame["date"] <= trough_date)].copy()
    if window.empty:
        return pd.DataFrame(), pd.DataFrame()
    product_summary = (
        window.groupby("product", as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            total_pnl=("total_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            slippage=("slippage", "sum"),
            turnover=("turnover", "sum"),
            trade_count=("trade_count", "sum"),
            active_days=("end_pos", lambda values: int((values != 0).sum())),
            max_abs_pos=("end_pos", lambda values: float(values.abs().max())),
        )
        .sort_values("net_pnl")
    )
    daily_summary = (
        window.groupby("date", as_index=False)
        .agg(net_pnl=("net_pnl", "sum"), total_pnl=("total_pnl", "sum"), holding_pnl=("holding_pnl", "sum"), trading_pnl=("trading_pnl", "sum"), slippage=("slippage", "sum"))
        .sort_values("net_pnl")
    )
    return product_summary, daily_summary


def _summarize_trades(trades_df: pd.DataFrame, peak_date: Any, trough_date: Any) -> pd.DataFrame:
    frame = trades_df.copy()
    if frame.empty:
        return pd.DataFrame()
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame["product"] = frame["vt_symbol"].map(_product_from_vt_symbol)
    window = frame[(frame["date"] > peak_date) & (frame["date"] <= trough_date)].copy()
    if window.empty:
        return pd.DataFrame()
    return (
        window.groupby(["product", "direction", "offset"], as_index=False)
        .agg(trades=("trade_id", "count"), volume=("volume", "sum"), avg_price=("price", "mean"))
        .sort_values(["product", "offset", "direction"])
    )


def _build_report(
    drawdown: dict[str, Any],
    product_summary: pd.DataFrame,
    daily_summary: pd.DataFrame,
    trade_summary: pd.DataFrame,
) -> str:
    top_losses = product_summary.head(12) if not product_summary.empty else product_summary
    top_loss_days = daily_summary.head(15) if not daily_summary.empty else daily_summary
    lines = [
        "# Stage320 2021最大回撤归因",
        "",
        "## 定位",
        "",
        "- 本阶段不修改策略参数，只复现 `C_pressure040` 在2021年的最大回撤。",
        "- Stage318/319 已确认全样本最差回撤来自2021-05-12到2021-07-02，供需数据从2023后才有覆盖，无法解释这段回撤。",
        "",
        "## 回撤窗口",
        "",
        f"- 峰值日：`{drawdown['peak_date']}`，权益 `{drawdown['peak_balance']:.2f}`。",
        f"- 谷底日：`{drawdown['trough_date']}`，权益 `{drawdown['trough_balance']:.2f}`。",
        f"- 最大回撤：`{drawdown['max_dd_pct']:.4f}%`。",
        "",
        "## 品种亏损贡献",
        "",
        to_markdown_table(top_losses),
        "",
        "## 最差单日贡献",
        "",
        to_markdown_table(top_loss_days),
        "",
        "## 回撤窗口交易结构",
        "",
        to_markdown_table(trade_summary.head(40) if not trade_summary.empty else trade_summary),
        "",
        "## 初步判断",
        "",
        "- 如果亏损集中在少数相关品种或同一方向商品簇，下一步优先测试跨品种/跨簇风险预算，而不是继续调外生因子阈值。",
        "- 如果亏损主要来自多个独立品种同时趋势反转，则需要研究账户层回撤状态机或新开仓冷却，而不是品种黑名单。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    assert_stage196_database_sentinels()
    manifest = build_official_stage78_manifest()
    overrides = build_official_stage78_overrides()
    overrides["trade_start_date"] = START_DT.date().isoformat()
    overrides.update(_pressure040_overrides())

    engine, analysis_df, statistics = run_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=overrides,
        analysis_start=START_DT,
        analysis_end=ANALYSIS_END,
        preload_start=PRELOAD_START_DT,
        capital=OFFICIAL_STAGE78_CAPITAL,
        save_artifacts=False,
        include_start_year_sweep=False,
        file_prefix=OUTPUT_PREFIX,
        chart_title="Stage320 2021 Pressure040 Drawdown Attribution",
    )
    if analysis_df is None or analysis_df.empty:
        raise RuntimeError("analysis_df is empty")

    drawdown = _drawdown_window(analysis_df)
    positions_df = build_positions_df(engine)
    trades_df = build_trades_df(engine)
    product_summary, daily_summary = _summarize_positions(positions_df, drawdown["peak_date"], drawdown["trough_date"])
    trade_summary = _summarize_trades(trades_df, drawdown["peak_date"], drawdown["trough_date"])
    report = _build_report(drawdown, product_summary, daily_summary, trade_summary)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    product_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_summary_{MODEL_TAG}.csv"
    daily_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_summary_{MODEL_TAG}.csv"
    trade_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_summary_{MODEL_TAG}.csv"
    curve_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curve_{MODEL_TAG}.csv"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

    product_summary.to_csv(product_path, index=False, encoding="utf-8-sig")
    daily_summary.to_csv(daily_path, index=False, encoding="utf-8-sig")
    trade_summary.to_csv(trade_path, index=False, encoding="utf-8-sig")
    drawdown["curve"].reset_index().rename(columns={"index": "date"}).to_csv(curve_path, index=False, encoding="utf-8-sig")
    report_path.write_text(report, encoding="utf-8")

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "manifest": manifest,
        "statistics": {
            "end_balance": float(statistics.get("end_balance", 0) or 0),
            "total_return_pct": float(statistics.get("total_return", 0) or 0),
            "max_dd_percent": float(statistics.get("max_ddpercent", 0) or 0),
            "sharpe_ratio": float(statistics.get("sharpe_ratio", 0) or 0),
            "total_trade_count": int(statistics.get("total_trade_count", 0) or 0),
            "win_ratio_pct": float(statistics.get("win_ratio", 0) or 0),
        },
        "drawdown": {key: value for key, value in drawdown.items() if key != "curve"},
        "paths": {
            "product_summary": str(product_path),
            "daily_summary": str(daily_path),
            "trade_summary": str(trade_path),
            "curve": str(curve_path),
            "report": str(report_path),
        },
    }
    decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print(report)


if __name__ == "__main__":
    main()
