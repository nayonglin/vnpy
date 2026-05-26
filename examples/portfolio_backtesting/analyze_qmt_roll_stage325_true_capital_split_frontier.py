from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import (
    MARGIN_REJECT_PCT,
    MARGIN_REVIEW_PCT,
    SATELLITE_OVERRIDES,
    SATELLITE_RISK_RATIO,
    TOTAL_CAPITAL,
    _c3_overrides,
    _daily_from_analysis,
    _margin_summary,
    _metadata,
    _path_metrics,
    _safe_float,
    _to_builtin,
    _to_markdown_table,
)
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_ROLE, OFFICIAL_STAGE78_VERSION
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR, build_positions_df
from run_qmt_range_reversion_core4_directed_backtest import run_backtest as run_range_backtest
from run_qmt_roll_backtest import run_backtest as run_roll_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


MODEL_TAG = "stage325_true_capital_split_frontier_v1"
OUTPUT_PREFIX = "qmt_roll_stage325_true_capital_split_frontier"
LINE_ID = "futures_trend_drawdown30_preserve_return"


@dataclass(frozen=True)
class CapitalSplit:
    name: str
    c3_capital: float
    satellite_capital: float


SPLITS: tuple[CapitalSplit, ...] = (
    CapitalSplit("c3_500_sat_0", 500_000.0, 0.0),
    CapitalSplit("c3_450_sat_50", 450_000.0, 50_000.0),
    CapitalSplit("c3_400_sat_100", 400_000.0, 100_000.0),
    CapitalSplit("c3_350_sat_150", 350_000.0, 150_000.0),
    CapitalSplit("c3_300_sat_200", 300_000.0, 200_000.0),
    CapitalSplit("c3_250_sat_250", 250_000.0, 250_000.0),
)


def _combine_daily_with_total(c3_daily: pd.DataFrame, satellite_daily: pd.DataFrame) -> pd.DataFrame:
    dates = sorted(set(c3_daily["date"]).union(set(satellite_daily["date"])))
    if not dates:
        return pd.DataFrame()
    base = pd.DataFrame({"date": pd.to_datetime(dates)})
    merged = base.merge(c3_daily, on="date", how="left").merge(satellite_daily, on="date", how="left")
    for column in ["c3_net_pnl", "satellite_net_pnl", "c3_trade_count", "satellite_trade_count"]:
        merged[column] = pd.to_numeric(merged.get(column, 0.0), errors="coerce").fillna(0.0)
    merged["combo_net_pnl"] = merged["c3_net_pnl"] + merged["satellite_net_pnl"]
    merged["balance"] = TOTAL_CAPITAL + merged["combo_net_pnl"].cumsum()
    merged["highlevel"] = merged["balance"].cummax()
    merged["drawdown"] = merged["balance"] - merged["highlevel"]
    merged["ddpercent"] = np.divide(
        merged["drawdown"],
        merged["highlevel"].replace(0.0, np.nan),
    ).fillna(0.0) * 100.0
    merged["trade_count"] = merged["c3_trade_count"] + merged["satellite_trade_count"]
    return merged


def _margin_daily_param(positions: pd.DataFrame, metadata: dict[str, Any], label: str) -> pd.DataFrame:
    if positions.empty:
        return pd.DataFrame(columns=["date", f"{label}_margin", f"{label}_active_contracts", f"{label}_active_products"])
    frame = positions.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    for column in ["end_pos", "close_price"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    frame["size"] = frame["vt_symbol"].map(metadata["sizes"]).fillna(1.0).astype(float)
    frame["margin_ratio"] = frame["vt_symbol"].map(metadata["margin_ratios"]).fillna(0.15).astype(float)
    frame["abs_end_pos"] = frame["end_pos"].abs()
    frame["position_margin"] = frame["abs_end_pos"] * frame["close_price"].clip(lower=0.0) * frame["size"] * frame["margin_ratio"]
    frame["product_vt_symbol"] = frame["vt_symbol"].map(lambda raw: "".join(ch for ch in str(raw).split(".")[0] if ch.isalpha()))
    frame["active_contract"] = (frame["abs_end_pos"] > 0).astype(int)
    product_daily = (
        frame.groupby(["date", "product_vt_symbol"], as_index=False)
        .agg(product_margin=("position_margin", "sum"), active_contracts=("active_contract", "sum"))
    )
    product_daily["active_product"] = (product_daily["product_margin"] > 0).astype(int)
    return (
        product_daily.groupby("date", as_index=False)
        .agg(
            **{
                f"{label}_margin": ("product_margin", "sum"),
                f"{label}_active_contracts": ("active_contracts", "sum"),
                f"{label}_active_products": ("active_product", "sum"),
            }
        )
        .sort_values("date")
        .reset_index(drop=True)
    )


def _combine_margin_param(
    combo_daily: pd.DataFrame,
    c3_positions: pd.DataFrame,
    satellite_positions: pd.DataFrame,
    metadata: dict[str, Any],
) -> pd.DataFrame:
    if combo_daily.empty:
        return pd.DataFrame()
    margin = combo_daily[["date", "balance"]].copy()
    margin = margin.merge(_margin_daily_param(c3_positions, metadata, "c3"), on="date", how="left")
    margin = margin.merge(_margin_daily_param(satellite_positions, metadata, "satellite"), on="date", how="left")
    for column in [
        "c3_margin",
        "satellite_margin",
        "c3_active_contracts",
        "satellite_active_contracts",
        "c3_active_products",
        "satellite_active_products",
    ]:
        margin[column] = pd.to_numeric(margin.get(column, 0.0), errors="coerce").fillna(0.0)
    margin["total_margin"] = margin["c3_margin"] + margin["satellite_margin"]
    margin["total_active_contracts"] = margin["c3_active_contracts"] + margin["satellite_active_contracts"]
    margin["total_active_products"] = margin["c3_active_products"] + margin["satellite_active_products"]
    margin["margin_to_equity_pct"] = (
        margin["total_margin"] / margin["balance"].replace(0.0, np.nan) * 100.0
    ).fillna(0.0)
    margin["margin_to_initial_capital_pct"] = margin["total_margin"] / TOTAL_CAPITAL * 100.0
    return margin


def _run_c3(capital: float) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    print(f"[stage325] run C3 capital={capital:.0f}", flush=True)
    engine, analysis_df, statistics = run_roll_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=_c3_overrides(START_DT),
        analysis_start=START_DT,
        analysis_end=END_DT,
        preload_start=max(PRELOAD_START_DT, START_DT - timedelta(days=365)),
        capital=capital,
        save_artifacts=False,
        include_start_year_sweep=False,
        file_prefix=f"{OUTPUT_PREFIX}_c3_{int(capital / 1000)}k",
        chart_title=f"Stage325 C3 {capital:,.0f}",
    )
    return _daily_from_analysis(analysis_df, capital, "c3"), build_positions_df(engine), statistics


def _run_satellite(capital: float, date_index: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if capital <= 0:
        daily = pd.DataFrame({"date": pd.to_datetime(date_index)})
        daily["satellite_balance"] = 0.0
        daily["satellite_net_pnl"] = 0.0
        daily["satellite_trade_count"] = 0.0
        return daily, pd.DataFrame(), {"total_return": 0.0, "max_ddpercent": 0.0, "sharpe_ratio": 0.0, "total_trade_count": 0}
    print(f"[stage325] run satellite capital={capital:.0f}", flush=True)
    engine, analysis_df, statistics = run_range_backtest(
        risk_ratio=SATELLITE_RISK_RATIO,
        analysis_start=START_DT,
        analysis_end=END_DT,
        preload_start=max(PRELOAD_START_DT, START_DT - timedelta(days=365)),
        capital=capital,
        save_artifacts=False,
        file_prefix=f"{OUTPUT_PREFIX}_satellite_{int(capital / 1000)}k",
        chart_title=f"Stage325 Satellite {capital:,.0f}",
        strategy_tag=f"range_reversion_v8_two_stage_stop_cap{int(capital)}",
        setting_overrides=SATELLITE_OVERRIDES,
    )
    return _daily_from_analysis(analysis_df, capital, "satellite"), build_positions_df(engine), statistics


def _summarize(
    split: CapitalSplit,
    c3_stats: dict[str, Any],
    satellite_stats: dict[str, Any],
    combo_daily: pd.DataFrame,
    margin: pd.DataFrame,
) -> dict[str, Any]:
    combo_metrics = _path_metrics(combo_daily, TOTAL_CAPITAL)
    margin_metrics = _margin_summary(margin)
    return {
        "split_name": split.name,
        "c3_capital": split.c3_capital,
        "satellite_capital": split.satellite_capital,
        "c3_return_pct": _safe_float(c3_stats.get("total_return")),
        "c3_max_dd_pct": _safe_float(c3_stats.get("max_ddpercent")),
        "c3_trade_count": int(_safe_float(c3_stats.get("total_trade_count"))),
        "satellite_return_pct": _safe_float(satellite_stats.get("total_return")),
        "satellite_max_dd_pct": _safe_float(satellite_stats.get("max_ddpercent")),
        "satellite_trade_count": int(_safe_float(satellite_stats.get("total_trade_count"))),
        "combo_end_balance": combo_metrics["end_balance"],
        "combo_return_pct": combo_metrics["total_return_pct"],
        "combo_max_dd_pct": combo_metrics["max_dd_percent"],
        "combo_sharpe": combo_metrics["sharpe_ratio"],
        "combo_trade_count": int(combo_daily["trade_count"].sum()) if not combo_daily.empty else 0,
        **margin_metrics,
    }


def _build_report(summary_df: pd.DataFrame) -> str:
    lines = [
        "# Stage325 真实资金拆分粗前沿",
        "",
        "## 目标",
        "",
        "- 对 Stage024 的失败做结构复验：不是微调 `80/20`，而是粗粒度检查真实资金拆分是否存在可行区间。",
        "- 所有组合总资金固定为 `500,000`，C3 和卫星分别独立回测，再叠加真实日盈亏。",
        "- 主闸门改为相对 50 万 C3 基准收益保留，而不是相对被压到低资金后的 C3 腿。",
        "",
        "## 结果",
        "",
    ]
    display_cols = [
        "split_name",
        "c3_capital",
        "satellite_capital",
        "combo_return_pct",
        "return_retention_vs_c3_500_pct",
        "combo_max_dd_pct",
        "combo_sharpe",
        "max_margin_to_equity_pct",
        "review_days",
        "reject_days",
        "satellite_trade_count",
        "dd_lt_30_ok",
        "retention_vs_c3_500_ge_80_ok",
    ]
    lines.append(_to_markdown_table(summary_df, display_cols, max_rows=100))
    lines.extend(["", "## 阶段判断", ""])
    candidates = summary_df[
        (summary_df["dd_lt_30_ok"] == 1)
        & (summary_df["retention_vs_c3_500_ge_80_ok"] == 1)
        & (summary_df["reject_days"] == 0)
    ]
    if candidates.empty:
        best_dd = summary_df.sort_values(["dd_lt_30_ok", "combo_return_pct"], ascending=[False, False]).head(1)
        if not best_dd.empty:
            row = best_dd.iloc[0]
            lines.append(
                f"- 没有拆分同时满足回撤30以内和相对50万C3收益保留80%以上。"
                f"相对较好的拆分是 `{row['split_name']}`：收益 `{row['combo_return_pct']:.3f}%`，"
                f"最大回撤 `{row['combo_max_dd_pct']:.4f}%`，相对50万C3保留 `{row['return_retention_vs_c3_500_pct']:.2f}%`。"
            )
        lines.append("- 结论：当前卫星腿在50万账户约束下不能解决目标问题，应停止继续围绕这条卫星做资金权重优化。")
    else:
        row = candidates.sort_values("combo_return_pct", ascending=False).iloc[0]
        lines.append(
            f"- 存在研究候选 `{row['split_name']}`：收益 `{row['combo_return_pct']:.3f}%`，"
            f"最大回撤 `{row['combo_max_dd_pct']:.4f}%`，相对50万C3保留 `{row['return_retention_vs_c3_500_pct']:.2f}%`。"
        )
        lines.append("- 结论：可以进入多周期复验，但仍不得直接合入正式78-1。")
    lines.extend(
        [
            "",
            "## 过拟合反思",
            "",
            "- 本阶段只做粗粒度真实资金拆分，不搜索细小权重；如果没有候选，不继续救具体比例。",
            "",
            "## 继续价值反思",
            "",
            "- 如果本阶段失败，组合层仍有价值，但必须换卫星腿；当前卫星在小资金下的合约离散度太高。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = _metadata()
    rows: list[dict[str, Any]] = []
    combo_frames: list[pd.DataFrame] = []
    margin_frames: list[pd.DataFrame] = []

    for split in SPLITS:
        c3_daily, c3_positions, c3_stats = _run_c3(split.c3_capital)
        satellite_daily, satellite_positions, satellite_stats = _run_satellite(split.satellite_capital, c3_daily["date"])
        combo_daily = _combine_daily_with_total(c3_daily, satellite_daily)
        margin = _combine_margin_param(combo_daily, c3_positions, satellite_positions, metadata)
        combo_daily["split_name"] = split.name
        margin["split_name"] = split.name
        combo_frames.append(combo_daily)
        margin_frames.append(margin)
        rows.append(_summarize(split, c3_stats, satellite_stats, combo_daily, margin))

    summary_df = pd.DataFrame(rows)
    c3_500_return = float(summary_df.loc[summary_df["split_name"].eq("c3_500_sat_0"), "combo_return_pct"].iloc[0])
    summary_df["return_retention_vs_c3_500_pct"] = np.where(
        c3_500_return > 0,
        summary_df["combo_return_pct"] / c3_500_return * 100.0,
        0.0,
    )
    summary_df["dd_lt_30_ok"] = (summary_df["combo_max_dd_pct"] >= -30.0).astype(int)
    summary_df["retention_vs_c3_500_ge_80_ok"] = (summary_df["return_retention_vs_c3_500_pct"] >= 80.0).astype(int)
    summary_df["margin_review_ok"] = (
        (summary_df["reject_days"] == 0) & (summary_df["max_margin_to_equity_pct"] < MARGIN_REVIEW_PCT)
    ).astype(int)

    combo_daily_df = pd.concat(combo_frames, ignore_index=True) if combo_frames else pd.DataFrame()
    margin_df = pd.concat(margin_frames, ignore_index=True) if margin_frames else pd.DataFrame()

    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    combo_daily_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combo_daily_{MODEL_TAG}.csv"
    margin_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_{MODEL_TAG}.csv"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    combo_daily_df.to_csv(combo_daily_path, index=False, encoding="utf-8-sig")
    margin_df.to_csv(margin_path, index=False, encoding="utf-8-sig")
    report_path.write_text(_build_report(summary_df), encoding="utf-8")
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "total_capital": TOTAL_CAPITAL,
        "margin_review_pct": MARGIN_REVIEW_PCT,
        "margin_reject_pct": MARGIN_REJECT_PCT,
        "splits": summary_df.to_dict(orient="records"),
        "paths": {
            "summary": str(summary_path),
            "combo_daily": str(combo_daily_path),
            "margin": str(margin_path),
            "report": str(report_path),
        },
    }
    decision_path.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[stage325] summary={summary_path}")
    print(f"[stage325] combo_daily={combo_daily_path}")
    print(f"[stage325] margin={margin_path}")
    print(f"[stage325] report={report_path}")
    print(f"[stage325] decision={decision_path}")
    print(report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
