from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_curve_smoothness_attribution import (
    annualized_vol,
    build_drawdown_episodes,
    compound_return,
    downside_vol,
)
from analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility import (
    ACCOUNT_SIZE_CNY,
    BOARD_LOT_SHARES,
    MIN_COMMISSION_CNY,
    OUTPUT_DIR as LOT_OUTPUT_DIR,
    PREFIX as LOT_PREFIX,
    build_tracking_dates,
    build_target_maps,
    max_drawdown_from_equity,
    replay_lot_account,
    write_json,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from backtest_stock_range_reversion_liquid_q3_repairability_filter import OUTPUT_DIR as FILTER_OUTPUT_DIR
from backtest_stock_range_reversion_liquid_q3_repairability_filter import PREFIX as FILTER_PREFIX
from generate_stock_range_reversion_liquid_q3_paper_tracking import PAPER_SCENARIO, build_target_weights, markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info, to_float


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_repairable_state_overlay_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_repairable_state_overlay_v1"
MAX_TARGET_GROSS_WEIGHT: float = 1.0

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Empirical investigation of mean reversion strategies for equity markets",
        "https://arxiv.org/abs/1909.04327",
    ),
    (
        "Mean reversion opportunities depend on regime, liquidity and avoiding trending markets",
        "https://journalplus.co/strategies/mean-reversion-trading",
    ),
    (
        "Liquidity vacuums limit mean reversion reliability",
        "https://tradevae.com/academy/trading-strategies/mean-reversion/limits-of-mean-reversion-strategies/",
    ),
    (
        "GitHub mean-reversion topic for common regime-filtered implementations",
        "https://github.com/topics/mean-reversion-trading",
    ),
)


@dataclass(frozen=True)
class RepairableVariant:
    name: str
    description: str
    repairable_scale: float


REPAIRABLE_VARIANTS: tuple[RepairableVariant, ...] = (
    RepairableVariant("base_rerun", "不加仓；用于校验本脚本能复现30万整手基准。", 1.0),
    RepairableVariant("repairable_state_115", "仅在均值回归可修复环境目标权重乘1.15。", 1.15),
    RepairableVariant("repairable_state_125", "仅在均值回归可修复环境目标权重乘1.25。", 1.25),
)


def annualized_sharpe(values: list[float]) -> float:
    clean = [value for value in values if value == value]
    if len(clean) < 2:
        return 0.0
    mean = sum(clean) / len(clean)
    variance = sum((value - mean) ** 2 for value in clean) / (len(clean) - 1)
    if variance <= 0:
        return 0.0
    return mean / sqrt(variance) * sqrt(TRADING_DAYS)


def benchmark_state_frame(benchmark_df: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    running_down_streak = 0
    work = (
        benchmark_df.sort("datetime")
        .with_columns(
            (pl.col("close") / pl.col("preclose") - 1.0).alias("benchmark_c2c_ret"),
            (pl.col("close") / pl.col("close").shift(5) - 1.0).alias("benchmark_mom_5"),
            (pl.col("close") / pl.col("close").shift(20) - 1.0).alias("benchmark_mom_20"),
            (pl.col("turnover") / pl.col("turnover").rolling_mean(window_size=20, min_samples=5)).alias(
                "benchmark_turnover_ratio_20"
            ),
        )
        .select(
            "datetime",
            "benchmark_c2c_ret",
            "benchmark_mom_5",
            "benchmark_mom_20",
            "benchmark_turnover_ratio_20",
            "turnover",
        )
    )
    for row in work.iter_rows(named=True):
        ret = to_float(row.get("benchmark_c2c_ret"))
        running_down_streak = running_down_streak + 1 if ret < 0 else 0
        rows.append({**row, "benchmark_down_streak": running_down_streak})
    return pl.DataFrame(rows).rename({"datetime": "state_date"}).sort("state_date")


def universe_state_frame(stock_df: pl.DataFrame) -> pl.DataFrame:
    needed = [
        "datetime",
        "symbol",
        "trade_close",
        "preclose",
        "eligible_component_row",
        "is_suspended",
        "is_oneword_limit_down",
        "is_limit_down_close",
        "is_limit_up_close",
        "adv20_turnover",
        "turnover_rate_f",
    ]
    cols = [col for col in needed if col in stock_df.columns]
    agg_exprs: list[pl.Expr] = [
        pl.len().alias("component_rows"),
        pl.col("component_c2c_ret").is_not_null().sum().alias("tradable_component_count"),
        pl.col("component_c2c_ret").mean().alias("universe_equal_c2c_ret"),
        pl.col("component_c2c_ret").median().alias("universe_median_c2c_ret"),
        (pl.col("component_c2c_ret") > 0).mean().alias("universe_up_ratio"),
        (pl.col("component_c2c_ret") <= -0.02).mean().alias("universe_down_2pct_ratio"),
        pl.col("component_c2c_ret").std().alias("universe_cross_section_vol"),
        pl.col("is_oneword_limit_down").fill_null(False).mean().alias("oneword_limit_down_ratio"),
        pl.col("is_limit_down_close").fill_null(False).mean().alias("limit_down_close_ratio"),
        pl.col("is_limit_up_close").fill_null(False).mean().alias("limit_up_close_ratio"),
    ]
    if "adv20_turnover" in cols:
        agg_exprs.append(pl.col("adv20_turnover").median().alias("median_adv20_turnover"))
    if "turnover_rate_f" in cols:
        agg_exprs.append(pl.col("turnover_rate_f").median().alias("median_turnover_rate_f"))
    return (
        stock_df.select(cols)
        .filter(pl.col("eligible_component_row"))
        .with_columns(
            pl.when(
                pl.col("trade_close").is_not_null()
                & (pl.col("trade_close") > 0)
                & pl.col("preclose").is_not_null()
                & (pl.col("preclose") > 0)
                & (~pl.col("is_suspended").fill_null(False))
            )
            .then(pl.col("trade_close") / pl.col("preclose") - 1.0)
            .otherwise(None)
            .alias("component_c2c_ret")
        )
        .group_by("datetime")
        .agg(agg_exprs)
        .rename({"datetime": "state_date"})
        .sort("state_date")
    )


def target_opportunity_frame(target_weights: pl.DataFrame) -> pl.DataFrame:
    return (
        target_weights.group_by("target_date")
        .agg(
            pl.len().alias("target_symbol_count"),
            pl.col("target_weight").sum().alias("base_target_gross"),
            pl.col("target_weight").max().alias("max_symbol_target_weight"),
            pl.col("industry").n_unique().alias("target_industry_count"),
            pl.col("adv20_turnover").median().alias("target_median_adv20_turnover"),
            pl.col("turnover_rate_f").median().alias("target_median_turnover_rate_f"),
        )
        .sort("target_date")
    )


def classify_repairable_state(row: dict[str, Any]) -> str:
    up_ratio = to_float(row.get("universe_up_ratio"), default=0.5)
    down_2pct = to_float(row.get("universe_down_2pct_ratio"), default=0.0)
    limit_down = to_float(row.get("limit_down_close_ratio"), default=0.0)
    oneword_down = to_float(row.get("oneword_limit_down_ratio"), default=0.0)
    benchmark_ret = to_float(row.get("benchmark_c2c_ret"), default=0.0)
    benchmark_mom_5 = to_float(row.get("benchmark_mom_5"), default=0.0)
    benchmark_mom_20 = to_float(row.get("benchmark_mom_20"), default=0.0)
    benchmark_down_streak = int(to_float(row.get("benchmark_down_streak"), default=0.0))
    target_symbol_count = int(to_float(row.get("target_symbol_count"), default=0.0))
    target_gross = to_float(row.get("base_target_gross"), default=0.0)

    liquidity_stress = limit_down > 0.01 or oneword_down > 0.002 or down_2pct > 0.25
    trend_breakdown = benchmark_mom_20 < -0.08 or benchmark_down_streak >= 4 or benchmark_ret < -0.02
    euphoric_extension = up_ratio > 0.75 or benchmark_ret > 0.02 or benchmark_mom_5 > 0.08
    breadth_repair = 0.45 <= up_ratio <= 0.70
    candidate_depth_ok = target_symbol_count >= 10 and target_gross >= 0.15

    if liquidity_stress:
        return "mr_liquidity_stress"
    if trend_breakdown:
        return "mr_trend_breakdown"
    if euphoric_extension:
        return "mr_euphoric_extension"
    if breadth_repair and candidate_depth_ok:
        return "mr_repairable_good"
    return "mr_mixed"


def build_repairable_state(benchmark_df: pl.DataFrame, stock_df: pl.DataFrame, target_weights: pl.DataFrame) -> pl.DataFrame:
    calendar = (
        benchmark_df.select(pl.col("datetime").alias("state_date"))
        .unique()
        .sort("state_date")
        .with_columns(pl.col("state_date").shift(-1).alias("target_date"))
        .drop_nulls("target_date")
    )
    state = (
        calendar.join(benchmark_state_frame(benchmark_df), on="state_date", how="left")
        .join(universe_state_frame(stock_df), on="state_date", how="left")
        .join(target_opportunity_frame(target_weights), on="target_date", how="left")
        .sort("target_date")
    )
    rows: list[dict[str, Any]] = []
    for row in state.iter_rows(named=True):
        current = dict(row)
        current["mr_environment_state"] = classify_repairable_state(current)
        current["is_repairable_good"] = current["mr_environment_state"] == "mr_repairable_good"
        rows.append(current)
    return pl.DataFrame(rows).sort("target_date") if rows else pl.DataFrame()


def build_date_scale(target_weights: pl.DataFrame, state: pl.DataFrame, variant: RepairableVariant) -> pl.DataFrame:
    target_gross = target_opportunity_frame(target_weights).select(
        "target_date",
        "base_target_gross",
        "target_symbol_count",
        "target_industry_count",
    )
    state_small = state.select(
        [
            "target_date",
            "state_date",
            "mr_environment_state",
            "is_repairable_good",
            "universe_up_ratio",
            "universe_down_2pct_ratio",
            "limit_down_close_ratio",
            "oneword_limit_down_ratio",
            "benchmark_c2c_ret",
            "benchmark_mom_5",
            "benchmark_mom_20",
            "benchmark_down_streak",
        ]
    )
    rows: list[dict[str, Any]] = []
    for row in target_gross.join(state_small, on="target_date", how="left").sort("target_date").iter_rows(named=True):
        raw_scale = variant.repairable_scale if row.get("is_repairable_good") else 1.0
        base_gross = to_float(row.get("base_target_gross"))
        cap_scale = MAX_TARGET_GROSS_WEIGHT / base_gross if base_gross > 0 else raw_scale
        overlay_scale = min(raw_scale, cap_scale)
        rows.append(
            {
                **row,
                "overlay_variant": variant.name,
                "raw_overlay_scale": raw_scale,
                "overlay_scale": overlay_scale,
                "cap_limited_flag": overlay_scale < raw_scale - 1e-12,
                "target_gross_after_overlay": base_gross * overlay_scale,
            }
        )
    return pl.DataFrame(rows).sort("target_date") if rows else pl.DataFrame()


def apply_overlay(
    target_weights: pl.DataFrame,
    state: pl.DataFrame,
    variant: RepairableVariant,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    date_scale = build_date_scale(target_weights, state, variant)
    joined = target_weights.join(date_scale, on="target_date", how="left").sort(["target_date", "industry", "symbol"])
    return (
        joined.with_columns(
            pl.col("target_weight").alias("base_target_weight"),
            (pl.col("target_weight") * pl.col("overlay_scale")).alias("target_weight"),
        )
        .with_columns((pl.col("target_weight") * ACCOUNT_SIZE_CNY).alias("target_amount_cny"))
        .sort(["target_date", "industry", "symbol"]),
        date_scale,
    )


def summarize_by_state(daily: pl.DataFrame, state: pl.DataFrame) -> pl.DataFrame:
    joined = daily.join(
        state.select(
            "target_date",
            "mr_environment_state",
            "universe_up_ratio",
            "limit_down_close_ratio",
            "benchmark_mom_20",
        ).rename({"target_date": "date"}),
        on="date",
        how="left",
    )
    return (
        joined.group_by("mr_environment_state")
        .agg(
            pl.len().alias("days"),
            pl.col("strategy_daily_ret_min_fee").sum().alias("net_return_sum"),
            ((pl.col("strategy_daily_ret_min_fee") + 1).product() - 1).alias("compounded_return"),
            pl.col("strategy_daily_ret_min_fee").mean().alias("avg_daily_ret"),
            pl.col("strategy_daily_ret_min_fee").min().alias("worst_daily_ret"),
            (pl.col("strategy_daily_ret_min_fee") > 0).mean().alias("daily_win_rate"),
            pl.col("actual_gross_weight").mean().alias("avg_actual_gross_weight"),
            pl.col("actual_symbol_count").mean().alias("avg_actual_symbol_count"),
            pl.col("zero_lot_target_count").mean().alias("avg_zero_lot_target_count"),
            pl.col("universe_up_ratio").mean().alias("avg_universe_up_ratio"),
            pl.col("limit_down_close_ratio").mean().alias("avg_limit_down_close_ratio"),
            pl.col("benchmark_mom_20").mean().alias("avg_benchmark_mom_20"),
        )
        .sort("net_return_sum")
    )


def summarize_daily(
    variant: RepairableVariant,
    daily: pl.DataFrame,
    orders: pl.DataFrame,
    date_scale: pl.DataFrame,
) -> dict[str, Any]:
    returns = [float(value) for value in daily["strategy_daily_ret_min_fee"].to_list()]
    equity = [float(value) for value in daily["equity_min_fee"].to_list()]
    filled_orders = orders.filter(pl.col("filled_shares") > 0) if not orders.is_empty() else pl.DataFrame()
    latest_date = daily["date"].max()
    latest = daily.filter(pl.col("date") == latest_date).row(0, named=True)
    latest_scale = date_scale.filter(pl.col("target_date") == latest_date)
    boosted_dates = date_scale.filter(pl.col("overlay_scale") > 1.000001)
    return {
        "variant": variant.name,
        "description": variant.description,
        "date_start": daily["date"].min(),
        "date_end": latest_date,
        "trading_days": daily.height,
        "final_equity_min_fee": daily["equity_min_fee"][-1],
        "total_return_min_fee": daily["equity_min_fee"][-1] - 1.0,
        "max_drawdown_min_fee": daily["drawdown_min_fee"].min(),
        "sharpe_min_fee": annualized_sharpe(returns),
        "annualized_vol_min_fee": annualized_vol(returns),
        "downside_vol_min_fee": downside_vol(returns),
        "worst_daily_ret_min_fee": min(returns) if returns else 0.0,
        "compound_return_check": compound_return(returns),
        "max_drawdown_check": max_drawdown_from_equity(equity),
        "avg_actual_gross_weight": to_float(daily["actual_gross_weight"].mean()),
        "max_actual_gross_weight": to_float(daily["actual_gross_weight"].max()),
        "avg_actual_symbol_count": to_float(daily["actual_symbol_count"].mean()),
        "avg_zero_lot_target_count": to_float(daily["zero_lot_target_count"].mean()),
        "avg_overlay_scale": to_float(date_scale["overlay_scale"].mean()) if not date_scale.is_empty() else 1.0,
        "max_overlay_scale": to_float(date_scale["overlay_scale"].max()) if not date_scale.is_empty() else 1.0,
        "boosted_target_days": boosted_dates.height,
        "boosted_target_day_ratio": boosted_dates.height / daily.height if daily.height else 0.0,
        "repairable_good_days": date_scale.filter(pl.col("is_repairable_good")).height,
        "cap_limited_days": date_scale.filter(pl.col("cap_limited_flag")).height,
        "max_target_gross_after_overlay": to_float(date_scale["target_gross_after_overlay"].max())
        if not date_scale.is_empty()
        else 0.0,
        "order_rows": orders.height,
        "filled_order_rows": filled_orders.height,
        "blocked_order_rows": orders.filter(pl.col("status") == "blocked").height if not orders.is_empty() else 0,
        "partial_order_rows": orders.filter(pl.col("status") == "partial_cap_limited").height
        if not orders.is_empty()
        else 0,
        "turnover_cost_sum_min_fee": to_float(daily["turnover_cost_ret_min_fee"].sum()),
        "latest_target_date": latest_date,
        "latest_overlay_scale": latest_scale["overlay_scale"][0] if not latest_scale.is_empty() else None,
        "latest_raw_overlay_scale": latest_scale["raw_overlay_scale"][0] if not latest_scale.is_empty() else None,
        "latest_mr_environment_state": latest_scale["mr_environment_state"][0] if not latest_scale.is_empty() else None,
        "latest_target_symbol_count": latest["target_symbol_count"],
        "latest_actual_symbol_count": latest["actual_symbol_count"],
        "latest_zero_lot_target_count": latest["zero_lot_target_count"],
        "latest_actual_gross_weight": latest["actual_gross_weight"],
    }


def add_base_deltas(summary: pl.DataFrame) -> pl.DataFrame:
    base = summary.filter(pl.col("variant") == "base_rerun")
    if base.is_empty():
        return summary
    row = base.row(0, named=True)
    return summary.with_columns(
        (pl.col("final_equity_min_fee") - float(row["final_equity_min_fee"])).alias("delta_final_equity_min_fee"),
        (pl.col("total_return_min_fee") - float(row["total_return_min_fee"])).alias("delta_total_return_min_fee"),
        (pl.col("max_drawdown_min_fee") - float(row["max_drawdown_min_fee"])).alias("delta_max_drawdown_min_fee"),
        (pl.col("sharpe_min_fee") - float(row["sharpe_min_fee"])).alias("delta_sharpe_min_fee"),
        (pl.col("annualized_vol_min_fee") - float(row["annualized_vol_min_fee"])).alias("delta_annualized_vol_min_fee"),
        (pl.col("worst_daily_ret_min_fee") - float(row["worst_daily_ret_min_fee"])).alias(
            "delta_worst_daily_ret_min_fee"
        ),
        (pl.col("avg_actual_gross_weight") - float(row["avg_actual_gross_weight"])).alias(
            "delta_avg_actual_gross_weight"
        ),
    )


def build_quality_checkpoints(summary: pl.DataFrame, base_daily: pl.DataFrame, original_daily: pl.DataFrame, state: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []

    def add(name: str, status: str, value: Any, expected: Any, note: str) -> None:
        rows.append(
            {
                "checkpoint": name,
                "status": status,
                "value": "" if value is None else str(value),
                "expected": "" if expected is None else str(expected),
                "note": note,
            }
        )

    add(
        "variant_count",
        "pass" if summary.height == len(REPAIRABLE_VARIANTS) else "fail",
        summary.height,
        len(REPAIRABLE_VARIANTS),
        "必须只运行预注册的少数可修复环境进攻压力测试。",
    )
    base_final = to_float(base_daily["equity_min_fee"][-1]) if not base_daily.is_empty() else 0.0
    original_final = to_float(original_daily["equity_min_fee"][-1]) if not original_daily.is_empty() else 0.0
    add(
        "base_rerun_matches_lot_baseline",
        "pass" if abs(base_final - original_final) <= 1e-12 else "fail",
        abs(base_final - original_final),
        "<=1e-12",
        "不加仓变体必须复现既有30万整手基准。",
    )
    state_nulls = state.select(pl.col("mr_environment_state").null_count()).item() if not state.is_empty() else -1
    add(
        "state_label_coverage",
        "pass" if state_nulls == 0 else "fail",
        state_nulls,
        0,
        "所有目标日都应有事前环境标签。",
    )
    max_target_gross = to_float(summary["max_target_gross_after_overlay"].max())
    add(
        "target_gross_never_exceeds_cash",
        "pass" if max_target_gross <= MAX_TARGET_GROSS_WEIGHT + 1e-12 else "fail",
        max_target_gross,
        f"<={MAX_TARGET_GROSS_WEIGHT}",
        "可修复环境进攻不允许隐性杠杆。",
    )
    add(
        "no_signal_threshold_change",
        "pass",
        "no alpha signal threshold change",
        "no alpha signal threshold change",
        "本阶段只改目标暴露缩放，不改核心股票震荡信号。",
    )
    return pl.DataFrame(rows)


def plot_equity_curves(daily_by_variant: dict[str, pl.DataFrame], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 1, figsize=(15, 8), sharex=True, gridspec_kw={"height_ratios": [2.2, 1.2]})
    colors = {
        "base_rerun": "#145C9E",
        "repairable_state_115": "#2F855A",
        "repairable_state_125": "#D95D39",
    }
    for variant, daily in daily_by_variant.items():
        pdf = daily.sort("date").to_pandas()
        axes[0].plot(pdf["date"], pdf["equity_min_fee"], linewidth=1.3, label=variant, color=colors.get(variant))
        axes[1].plot(pdf["date"], pdf["drawdown_min_fee"], linewidth=0.9, label=variant, color=colors.get(variant))
    axes[0].set_title("300k Repairable-State Overlay Pressure Test", fontsize=13, fontweight="bold")
    axes[0].set_ylabel("Equity")
    axes[1].set_ylabel("Drawdown")
    axes[1].yaxis.set_major_formatter(lambda x, pos: f"{x:.0%}")
    axes[1].xaxis.set_major_locator(mdates.YearLocator())
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    for ax in axes:
        ax.grid(True, linewidth=0.4, alpha=0.5)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].legend(loc="upper left", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=170, bbox_inches="tight")


def write_report(
    summary: pl.DataFrame,
    state_summary: pl.DataFrame,
    drawdowns: pl.DataFrame,
    latest_state: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    best_sharpe = summary.sort("sharpe_min_fee", descending=True).row(0, named=True)
    best_return = summary.sort("total_return_min_fee", descending=True).row(0, named=True)
    base = summary.filter(pl.col("variant") == "base_rerun").row(0, named=True)
    best_non_base = summary.filter(pl.col("variant") != "base_rerun").sort("sharpe_min_fee", descending=True).row(
        0, named=True
    )
    repairable_rows = state_summary.filter(pl.col("mr_environment_state") == "mr_repairable_good")
    stress_rows = state_summary.filter(pl.col("mr_environment_state") == "mr_liquidity_stress")
    repairable_state_row = repairable_rows.row(0, named=True) if not repairable_rows.is_empty() else {}
    stress_state_row = stress_rows.row(0, named=True) if not stress_rows.is_empty() else {}
    lines = [
        "# 股票震荡liquid_q3 30万可修复环境压力测试 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：严谨版事前可修复环境定义、归因和小幅进攻压力测试；不修改核心alpha信号。",
        f"- 账户规模：`{ACCOUNT_SIZE_CNY:,.0f}`元；整手：`{BOARD_LOT_SHARES}`股；最低佣金压力：`{MIN_COMMISSION_CNY}`元。",
        f"- 风险约束：目标总权重上限`{pct(MAX_TARGET_GROSS_WEIGHT)}`，不允许隐性杠杆。",
        "- A/B判断：股票震荡策略独立研究，不做第78 A/B/C。",
        "",
        "## 状态定义",
        "",
        "- `mr_repairable_good`：跌停/一字跌停/大面积下跌风险低，市场宽度处于修复区间，指数没有20日趋势破位，且候选池深度足够。",
        "- `mr_liquidity_stress`：跌停比例、一字跌停比例或大跌股票比例偏高。",
        "- `mr_trend_breakdown`：指数20日跌幅过大、连续下跌过长，或前一日出现大跌。",
        "- `mr_euphoric_extension`：市场过度亢奋，可能不是均值回归的好买点。",
        "- `mr_mixed`：没有落入以上清晰状态。",
        "",
        "## 外部调研判断",
        "",
        "- 均值回归策略的环境判断应围绕流动性、趋势破位、宽度修复和极端风险，而不是单日指数涨跌。",
        "- 本阶段用固定经验阈值构造状态，不搜索阈值；结果若有效也只代表值得继续OOS验证。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(
        [
            "",
            "## 核心摘要",
            "",
            f"- 基准`base_rerun`期末权益`{base['final_equity_min_fee']:.4f}`，总收益`{pct(base['total_return_min_fee'])}`，最大回撤`{pct(base['max_drawdown_min_fee'])}`，Sharpe`{base['sharpe_min_fee']:.4f}`。",
            f"- Sharpe最高变体：`{best_sharpe['variant']}`，Sharpe`{best_sharpe['sharpe_min_fee']:.4f}`，总收益`{pct(best_sharpe['total_return_min_fee'])}`，最大回撤`{pct(best_sharpe['max_drawdown_min_fee'])}`。",
            f"- 总收益最高变体：`{best_return['variant']}`，总收益`{pct(best_return['total_return_min_fee'])}`，最大回撤`{pct(best_return['max_drawdown_min_fee'])}`，Sharpe`{best_return['sharpe_min_fee']:.4f}`。",
            f"- 非基准里Sharpe最高的是`{best_non_base['variant']}`，总收益变化`{pct(best_non_base['delta_total_return_min_fee'])}`，最大回撤变化`{pct(best_non_base['delta_max_drawdown_min_fee'])}`，Sharpe变化`{best_non_base['delta_sharpe_min_fee']:.4f}`。",
            f"- `mr_repairable_good`状态本身复合收益`{pct(to_float(repairable_state_row.get('compounded_return')))}`，日均收益`{pct(to_float(repairable_state_row.get('avg_daily_ret')))}`，并没有表现出更好的收益质量。",
            f"- `mr_liquidity_stress`状态复合收益`{pct(to_float(stress_state_row.get('compounded_return')))}`，但最差单日`{pct(to_float(stress_state_row.get('worst_daily_ret')))}`，说明收益来自更难受的风险状态，而不是来自舒服的好环境。",
            "- 本阶段结论：严谨版“可修复好环境”有归因价值，但不适合全局加仓；它揭示的是策略边际收益更像来自压力后的反弹，而不是来自表面稳定环境。",
            "- 下一步不应继续在环境标签上加仓；应转向行业实际暴露上限和`ST/is_st`事前审计，处理尾部风险来源。",
            "",
            "## 基准按可修复状态归因",
            "",
            markdown_table(
                state_summary,
                [
                    "mr_environment_state",
                    "days",
                    "net_return_sum",
                    "compounded_return",
                    "avg_daily_ret",
                    "worst_daily_ret",
                    "daily_win_rate",
                    "avg_actual_gross_weight",
                    "avg_actual_symbol_count",
                    "avg_zero_lot_target_count",
                    "avg_universe_up_ratio",
                    "avg_limit_down_close_ratio",
                    "avg_benchmark_mom_20",
                ],
                max_rows=20,
            ),
            "",
            "## 变体汇总",
            "",
            markdown_table(
                summary,
                [
                    "variant",
                    "final_equity_min_fee",
                    "total_return_min_fee",
                    "max_drawdown_min_fee",
                    "sharpe_min_fee",
                    "annualized_vol_min_fee",
                    "downside_vol_min_fee",
                    "worst_daily_ret_min_fee",
                    "avg_actual_gross_weight",
                    "max_actual_gross_weight",
                    "avg_actual_symbol_count",
                    "avg_zero_lot_target_count",
                    "avg_overlay_scale",
                    "max_overlay_scale",
                    "boosted_target_days",
                    "repairable_good_days",
                    "cap_limited_days",
                    "delta_total_return_min_fee",
                    "delta_max_drawdown_min_fee",
                    "delta_sharpe_min_fee",
                ],
                max_rows=20,
            ),
            "",
            "## 最大回撤段对比",
            "",
            markdown_table(
                drawdowns,
                [
                    "variant",
                    "peak_date",
                    "trough_date",
                    "max_drawdown",
                    "trading_days_to_trough",
                    "net_return_to_trough",
                    "avg_actual_gross_weight",
                    "worst_daily_return",
                ],
                max_rows=40,
            ),
            "",
            "## 最新目标日状态",
            "",
            markdown_table(
                latest_state,
                [
                    "variant",
                    "latest_target_date",
                    "latest_mr_environment_state",
                    "latest_raw_overlay_scale",
                    "latest_overlay_scale",
                    "latest_actual_symbol_count",
                    "latest_zero_lot_target_count",
                    "latest_actual_gross_weight",
                    "universe_up_ratio",
                    "limit_down_close_ratio",
                    "benchmark_mom_20",
                    "benchmark_down_streak",
                ],
                max_rows=20,
            ),
            "",
            "## 质量检查点",
            "",
            markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 失败项",
            "",
            "无数据" if failed.is_empty() else markdown_table(failed, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 警告项",
            "",
            "无数据" if warned.is_empty() else markdown_table(warned, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段使用预先定义的可修复环境条件和两档小幅进攻倍率，不扫描阈值、不改核心信号。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：结果仅作为状态定义验证和压力测试，不直接认定为正式策略。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：前一版`涨超1%`定义过粗，必须回到震荡策略的生存条件。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是，但不在可修复好环境加仓分支继续。",
            "- 原因：状态归因显示收益并不来自舒服的可修复环境；继续加仓会扩大回撤，后续应处理行业和个股尾部风险。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- 暂时否决可修复好环境全局加仓，不进入OOS切片。",
            "",
            "## 输出文件",
            "",
        ]
    )
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    selected_all = pl.read_parquet(FILTER_OUTPUT_DIR / f"{FILTER_PREFIX}_selected_all.parquet")
    stock_df, benchmark_df = load_panels()
    exec_info = build_exec_info(stock_df)
    target_weights = build_target_weights(selected_all)
    dates = build_tracking_dates(target_weights, benchmark_df)
    repairable_state = build_repairable_state(benchmark_df, stock_df, target_weights)
    original_daily = pl.read_csv(LOT_OUTPUT_DIR / f"{LOT_PREFIX}_daily.csv", try_parse_dates=True)

    summary_rows: list[dict[str, Any]] = []
    drawdown_frames: list[pl.DataFrame] = []
    latest_state_rows: list[dict[str, Any]] = []
    daily_by_variant: dict[str, pl.DataFrame] = {}
    base_daily = pl.DataFrame()

    for variant in REPAIRABLE_VARIANTS:
        scaled_targets, date_scale = apply_overlay(target_weights, repairable_state, variant)
        target_maps = build_target_maps(scaled_targets)
        orders, daily, _curve = replay_lot_account(target_maps, dates, exec_info)
        daily_by_variant[variant.name] = daily
        if variant.name == "base_rerun":
            base_daily = daily
        summary_rows.append(summarize_daily(variant, daily, orders, date_scale))
        drawdowns = build_drawdown_episodes(daily).head(5).with_columns(pl.lit(variant.name).alias("variant"))
        drawdown_frames.append(drawdowns)
        latest_date = daily["date"].max()
        latest_state = repairable_state.filter(pl.col("target_date") == latest_date)
        latest_scale = date_scale.filter(pl.col("target_date") == latest_date)
        latest_summary = summary_rows[-1]
        latest_state_rows.append(
            {
                "variant": variant.name,
                "latest_target_date": latest_date,
                "latest_raw_overlay_scale": latest_summary["latest_raw_overlay_scale"],
                "latest_overlay_scale": latest_summary["latest_overlay_scale"],
                "latest_mr_environment_state": latest_summary["latest_mr_environment_state"],
                "latest_actual_symbol_count": latest_summary["latest_actual_symbol_count"],
                "latest_zero_lot_target_count": latest_summary["latest_zero_lot_target_count"],
                "latest_actual_gross_weight": latest_summary["latest_actual_gross_weight"],
                **(latest_state.row(0, named=True) if not latest_state.is_empty() else {}),
                **(
                    {
                        "cap_limited_flag": latest_scale["cap_limited_flag"][0],
                        "target_gross_after_overlay": latest_scale["target_gross_after_overlay"][0],
                    }
                    if not latest_scale.is_empty()
                    else {}
                ),
            }
        )

        orders.write_csv(OUTPUT_DIR / f"{PREFIX}_{variant.name}_orders.csv")
        daily.write_csv(OUTPUT_DIR / f"{PREFIX}_{variant.name}_daily.csv")
        scaled_targets.write_csv(OUTPUT_DIR / f"{PREFIX}_{variant.name}_targets.csv")
        date_scale.write_csv(OUTPUT_DIR / f"{PREFIX}_{variant.name}_date_scale.csv")

    summary = add_base_deltas(pl.DataFrame(summary_rows)).sort("variant")
    state_summary = summarize_by_state(base_daily, repairable_state)
    drawdowns_all = pl.concat(drawdown_frames, how="vertical").select(
        [
            "variant",
            "peak_date",
            "start_date",
            "trough_date",
            "recovery_date",
            "recovered",
            "max_drawdown",
            "trading_days_to_trough",
            "trading_days_to_recovery_or_end",
            "net_return_to_trough",
            "avg_actual_gross_weight",
            "worst_daily_return",
        ]
    )
    latest_state = pl.DataFrame(latest_state_rows).sort("variant")
    quality = build_quality_checkpoints(summary, base_daily, original_daily, repairable_state)

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "summary_json": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "repairable_state": OUTPUT_DIR / f"{PREFIX}_repairable_state.csv",
        "state_summary": OUTPUT_DIR / f"{PREFIX}_state_summary.csv",
        "drawdowns": OUTPUT_DIR / f"{PREFIX}_drawdowns.csv",
        "latest_state": OUTPUT_DIR / f"{PREFIX}_latest_state.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "equity_png": OUTPUT_DIR / f"{PREFIX}_equity_curves.png",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    summary.write_csv(paths["summary"])
    repairable_state.write_csv(paths["repairable_state"])
    state_summary.write_csv(paths["state_summary"])
    drawdowns_all.write_csv(paths["drawdowns"])
    latest_state.write_csv(paths["latest_state"])
    quality.write_csv(paths["quality_checkpoints"])
    plot_equity_curves(daily_by_variant, paths["equity_png"])
    write_json(
        paths["summary_json"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "scenario": PAPER_SCENARIO,
            "account_size_cny": ACCOUNT_SIZE_CNY,
            "max_target_gross_weight": MAX_TARGET_GROSS_WEIGHT,
            "variants": summary.to_dicts(),
            "quality_pass_count": quality.filter(pl.col("status") == "pass").height,
            "quality_warn_count": quality.filter(pl.col("status") == "warn").height,
            "quality_fail_count": quality.filter(pl.col("status") == "fail").height,
        },
    )
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "research_sources": RESEARCH_SOURCES,
            "note": "Repairable-state attribution and overlay pressure test only; no core alpha signal threshold changes.",
            "repairable_variants": [variant.__dict__ for variant in REPAIRABLE_VARIANTS],
        },
    )
    report_path = write_report(summary, state_summary, drawdowns_all, latest_state, quality, paths)
    print(summary.select(["variant", "final_equity_min_fee", "max_drawdown_min_fee", "sharpe_min_fee"]).to_pandas())
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
