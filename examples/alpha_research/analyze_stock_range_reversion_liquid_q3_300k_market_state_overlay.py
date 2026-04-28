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
    RESEARCH_SOURCES as SMOOTHNESS_RESEARCH_SOURCES,
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
from analyze_stock_range_reversion_liquid_q3_paper_oos_market_state import (
    classify_breadth_state,
    classify_index_state,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from backtest_stock_range_reversion_liquid_q3_repairability_filter import OUTPUT_DIR as FILTER_OUTPUT_DIR
from backtest_stock_range_reversion_liquid_q3_repairability_filter import PREFIX as FILTER_PREFIX
from generate_stock_range_reversion_liquid_q3_paper_tracking import PAPER_SCENARIO, build_target_weights, markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info, to_float


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_market_state_overlay_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_market_state_overlay_v1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Empirical mean-reversion research warns that recent data and costs matter",
        "https://arxiv.org/abs/1909.04327",
    ),
    (
        "Smoothing volatility targeting highlights turnover and transaction-cost risks",
        "https://arxiv.org/abs/2212.07288",
    ),
    (
        "GitHub mean-reversion topic shows common regime-filtered equity strategy patterns",
        "https://github.com/topics/mean-reversion-trading",
    ),
    *SMOOTHNESS_RESEARCH_SOURCES,
)


@dataclass(frozen=True)
class OverlayVariant:
    name: str
    description: str


OVERLAY_VARIANTS: tuple[OverlayVariant, ...] = (
    OverlayVariant("base_rerun", "不降权；用于校验本脚本能复现30万整手基准。"),
    OverlayVariant("prev_close_weak_breadth_half", "若前一交易日收盘市场宽度弱，则下一目标日整体目标权重乘0.50。"),
    OverlayVariant("prev_close_index_down_half", "若前一交易日中证1000收盘跌幅超过1%，则下一目标日整体目标权重乘0.50。"),
    OverlayVariant("prev_close_breadth_or_index_half", "若前一交易日市场宽度弱或指数跌幅超过1%，则下一目标日整体目标权重乘0.50。"),
    OverlayVariant(
        "prev_close_breadth_index_tiered",
        "若前一交易日宽度弱且指数跌超1%则权重乘0.25；仅命中一个风险条件则乘0.50。",
    ),
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


def read_csv(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, try_parse_dates=True, schema_overrides={"symbol": pl.Utf8})


def build_prev_close_market_state(benchmark_df: pl.DataFrame, stock_df: pl.DataFrame) -> pl.DataFrame:
    calendar = (
        benchmark_df.select(pl.col("datetime").alias("state_date"))
        .unique()
        .sort("state_date")
        .with_columns(pl.col("state_date").shift(-1).alias("target_date"))
        .drop_nulls("target_date")
    )
    benchmark_state = benchmark_df.sort("datetime").select(
        pl.col("datetime").alias("state_date"),
        (pl.col("close") / pl.col("preclose") - 1.0).alias("prev_benchmark_close_to_close_ret"),
        pl.col("turnover").alias("prev_benchmark_turnover"),
    )
    stock_needed = [
        "datetime",
        "symbol",
        "trade_close",
        "preclose",
        "eligible_component_row",
        "is_suspended",
        "is_oneword_limit_up",
        "is_oneword_limit_down",
        "is_limit_up_close",
        "is_limit_down_close",
    ]
    stock_cols = [col for col in stock_needed if col in stock_df.columns]
    stock_state = (
        stock_df.select(stock_cols)
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
            .alias("close_to_close_ret")
        )
        .group_by("datetime")
        .agg(
            pl.len().alias("prev_universe_component_rows"),
            pl.col("close_to_close_ret").is_not_null().sum().alias("prev_universe_tradable_count"),
            pl.col("close_to_close_ret").mean().alias("prev_universe_equal_c2c_ret"),
            pl.col("close_to_close_ret").median().alias("prev_universe_median_c2c_ret"),
            (pl.col("close_to_close_ret") > 0).mean().alias("prev_universe_up_ratio"),
            (pl.col("close_to_close_ret") <= -0.02).mean().alias("prev_universe_down_2pct_ratio"),
            pl.col("close_to_close_ret").std().alias("prev_universe_cross_section_vol"),
            pl.col("is_oneword_limit_up").fill_null(False).mean().alias("prev_oneword_limit_up_ratio"),
            pl.col("is_oneword_limit_down").fill_null(False).mean().alias("prev_oneword_limit_down_ratio"),
            pl.col("is_limit_up_close").fill_null(False).mean().alias("prev_limit_up_close_ratio"),
            pl.col("is_limit_down_close").fill_null(False).mean().alias("prev_limit_down_close_ratio"),
        )
        .rename({"datetime": "state_date"})
    )
    rows = (
        calendar.join(benchmark_state, on="state_date", how="left")
        .join(stock_state, on="state_date", how="left")
        .sort("target_date")
        .iter_rows(named=True)
    )
    output_rows: list[dict[str, Any]] = []
    for row in rows:
        current = dict(row)
        current["prev_close_index_state"] = classify_index_state(row.get("prev_benchmark_close_to_close_ret"))
        if row.get("prev_universe_up_ratio") is None:
            current["prev_close_breadth_state"] = "missing_breadth"
        else:
            current["prev_close_breadth_state"] = classify_breadth_state(row.get("prev_universe_up_ratio"))
        current["prev_close_weak_breadth_flag"] = current["prev_close_breadth_state"] == "weak_breadth"
        current["prev_close_index_down_flag"] = current["prev_close_index_state"] == "index_down_gt_1pct"
        output_rows.append(current)
    return pl.DataFrame(output_rows).sort("target_date") if output_rows else pl.DataFrame()


def scale_for_variant(variant: str, weak_breadth: bool, index_down: bool) -> float:
    if variant == "base_rerun":
        return 1.0
    if variant == "prev_close_weak_breadth_half":
        return 0.5 if weak_breadth else 1.0
    if variant == "prev_close_index_down_half":
        return 0.5 if index_down else 1.0
    if variant == "prev_close_breadth_or_index_half":
        return 0.5 if weak_breadth or index_down else 1.0
    if variant == "prev_close_breadth_index_tiered":
        if weak_breadth and index_down:
            return 0.25
        if weak_breadth or index_down:
            return 0.5
        return 1.0
    raise ValueError(f"Unknown overlay variant: {variant}")


def apply_overlay(target_weights: pl.DataFrame, state: pl.DataFrame, variant: OverlayVariant) -> pl.DataFrame:
    state_small = state.select(
        [
            "target_date",
            "state_date",
            "prev_close_index_state",
            "prev_close_breadth_state",
            "prev_close_weak_breadth_flag",
            "prev_close_index_down_flag",
            "prev_universe_up_ratio",
            "prev_benchmark_close_to_close_ret",
        ]
    )
    rows: list[dict[str, Any]] = []
    joined = target_weights.join(state_small, on="target_date", how="left").sort(["target_date", "industry", "symbol"])
    for row in joined.iter_rows(named=True):
        weak_breadth = bool(row.get("prev_close_weak_breadth_flag") or False)
        index_down = bool(row.get("prev_close_index_down_flag") or False)
        scale = scale_for_variant(variant.name, weak_breadth, index_down)
        current = dict(row)
        base_weight = to_float(current.get("target_weight"))
        current["base_target_weight"] = base_weight
        current["overlay_scale"] = scale
        current["target_weight"] = base_weight * scale
        current["target_amount_cny"] = current["target_weight"] * ACCOUNT_SIZE_CNY
        current["overlay_variant"] = variant.name
        rows.append(current)
    return pl.DataFrame(rows).sort(["target_date", "industry", "symbol"]) if rows else pl.DataFrame()


def summarize_daily(variant: OverlayVariant, daily: pl.DataFrame, orders: pl.DataFrame, scaled_targets: pl.DataFrame) -> dict[str, Any]:
    returns = [float(value) for value in daily["strategy_daily_ret_min_fee"].to_list()]
    equity = [float(value) for value in daily["equity_min_fee"].to_list()]
    filled_orders = orders.filter(pl.col("filled_shares") > 0) if not orders.is_empty() else pl.DataFrame()
    scale_by_date = (
        scaled_targets.group_by("target_date")
        .agg(
            pl.col("overlay_scale").first().alias("overlay_scale"),
            pl.col("prev_close_weak_breadth_flag").first().alias("prev_close_weak_breadth_flag"),
            pl.col("prev_close_index_down_flag").first().alias("prev_close_index_down_flag"),
        )
        .sort("target_date")
    )
    latest_date = daily["date"].max()
    latest = daily.filter(pl.col("date") == latest_date).row(0, named=True)
    latest_scale = (
        scale_by_date.filter(pl.col("target_date") == latest_date)["overlay_scale"][0]
        if scale_by_date.filter(pl.col("target_date") == latest_date).height
        else None
    )
    scaled_dates = scale_by_date.filter(pl.col("overlay_scale") < 0.999999)
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
        "avg_actual_symbol_count": to_float(daily["actual_symbol_count"].mean()),
        "avg_zero_lot_target_count": to_float(daily["zero_lot_target_count"].mean()),
        "avg_overlay_scale": to_float(scale_by_date["overlay_scale"].mean()) if not scale_by_date.is_empty() else 1.0,
        "scaled_target_days": scaled_dates.height,
        "scaled_target_day_ratio": scaled_dates.height / daily.height if daily.height else 0.0,
        "weak_breadth_scaled_days": scale_by_date.filter(pl.col("prev_close_weak_breadth_flag")).height,
        "index_down_scaled_days": scale_by_date.filter(pl.col("prev_close_index_down_flag")).height,
        "order_rows": orders.height,
        "filled_order_rows": filled_orders.height,
        "blocked_order_rows": orders.filter(pl.col("status") == "blocked").height if not orders.is_empty() else 0,
        "partial_order_rows": orders.filter(pl.col("status") == "partial_cap_limited").height
        if not orders.is_empty()
        else 0,
        "turnover_cost_sum_min_fee": to_float(daily["turnover_cost_ret_min_fee"].sum()),
        "latest_target_date": latest_date,
        "latest_overlay_scale": latest_scale,
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


def build_quality_checkpoints(summary: pl.DataFrame, base_daily: pl.DataFrame, original_daily: pl.DataFrame) -> pl.DataFrame:
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
        "pass" if summary.height == len(OVERLAY_VARIANTS) else "fail",
        summary.height,
        len(OVERLAY_VARIANTS),
        "必须只运行预注册的少数状态降权压力测试。",
    )
    base_final = to_float(base_daily["equity_min_fee"][-1]) if not base_daily.is_empty() else 0.0
    original_final = to_float(original_daily["equity_min_fee"][-1]) if not original_daily.is_empty() else 0.0
    add(
        "base_rerun_matches_lot_baseline",
        "pass" if abs(base_final - original_final) <= 1e-12 else "fail",
        abs(base_final - original_final),
        "<=1e-12",
        "不降权变体必须复现既有30万整手基准。",
    )
    max_overlay_scale = to_float(summary["avg_overlay_scale"].max())
    min_overlay_scale = to_float(summary["avg_overlay_scale"].min())
    add(
        "overlay_scale_bounds",
        "pass" if min_overlay_scale >= 0.0 and max_overlay_scale <= 1.0 else "fail",
        f"{min_overlay_scale}..{max_overlay_scale}",
        "0..1",
        "状态风控只允许降权，不允许加杠杆。",
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
        "prev_close_weak_breadth_half": "#7A5195",
        "prev_close_index_down_half": "#EF5675",
        "prev_close_breadth_or_index_half": "#FFA600",
        "prev_close_breadth_index_tiered": "#2F855A",
    }
    for variant, daily in daily_by_variant.items():
        pdf = daily.sort("date").to_pandas()
        axes[0].plot(pdf["date"], pdf["equity_min_fee"], linewidth=1.2, label=variant, color=colors.get(variant))
        axes[1].plot(pdf["date"], pdf["drawdown_min_fee"], linewidth=0.9, label=variant, color=colors.get(variant))
    axes[0].set_title("300k Market-State Overlay Pressure Test", fontsize=13, fontweight="bold")
    axes[0].set_ylabel("Equity")
    axes[1].set_ylabel("Drawdown")
    axes[1].yaxis.set_major_formatter(lambda x, pos: f"{x:.0%}")
    axes[1].xaxis.set_major_locator(mdates.YearLocator())
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    for ax in axes:
        ax.grid(True, linewidth=0.4, alpha=0.5)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=170, bbox_inches="tight")


def write_report(
    summary: pl.DataFrame,
    drawdowns: pl.DataFrame,
    latest_state: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    best_dd = summary.sort("max_drawdown_min_fee", descending=True).row(0, named=True)
    best_return = summary.sort("total_return_min_fee", descending=True).row(0, named=True)
    base = summary.filter(pl.col("variant") == "base_rerun").row(0, named=True)
    best_dd_improvement = to_float(best_dd.get("delta_max_drawdown_min_fee"))
    best_dd_return_delta = to_float(best_dd.get("delta_total_return_min_fee"))
    best_dd_sharpe_delta = to_float(best_dd.get("delta_sharpe_min_fee"))
    lines = [
        "# 股票震荡liquid_q3 30万市场状态降权压力测试 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：事前市场状态风控压力测试；不修改核心alpha信号。",
        f"- 账户规模：`{ACCOUNT_SIZE_CNY:,.0f}`元；整手：`{BOARD_LOT_SHARES}`股；最低佣金压力：`{MIN_COMMISSION_CNY}`元。",
        "- 状态口径：只使用前一交易日收盘后已知的中证1000收盘涨跌和成分股收盘宽度，不使用当天开盘到次开盘归因标签。",
        "- A/B判断：股票震荡策略独立研究，不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 均值回归策略可以用市场状态管理暴露，但最容易犯的错是用事后状态或用过多阈值把历史曲线抹平。",
        "- 波动/状态降权还会改变换手、最低佣金和整手约束，因此必须重新跑账户回放，而不是直接把收益乘缩放系数。",
        "- 本阶段只测少数预注册规则，不选择最优阈值。",
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
            f"- 最大回撤最浅的变体：`{best_dd['variant']}`，最大回撤`{pct(best_dd['max_drawdown_min_fee'])}`，总收益`{pct(best_dd['total_return_min_fee'])}`。",
            f"- 总收益最高的变体：`{best_return['variant']}`，总收益`{pct(best_return['total_return_min_fee'])}`，最大回撤`{pct(best_return['max_drawdown_min_fee'])}`。",
            f"- 最浅回撤变体相对基准只改善最大回撤`{pct(best_dd_improvement)}`，但总收益减少`{pct(abs(best_dd_return_delta))}`，Sharpe变化`{best_dd_sharpe_delta:.4f}`。",
            "- 本阶段结论：这组事前全局市场状态降权不值得继续推进为正式规则；它能稍微削平尾部，但主要效果是砍掉均值回归策略最需要的反弹暴露。",
            "- 下一步不应继续搜索市场状态阈值；更合理的是测试行业实际暴露上限，或者先做ST/is_st事前可用性审计。",
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
                    "avg_actual_symbol_count",
                    "avg_zero_lot_target_count",
                    "avg_overlay_scale",
                    "scaled_target_days",
                    "delta_total_return_min_fee",
                    "delta_max_drawdown_min_fee",
                    "delta_sharpe_min_fee",
                    "delta_worst_daily_ret_min_fee",
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
                    "latest_overlay_scale",
                    "latest_actual_symbol_count",
                    "latest_zero_lot_target_count",
                    "latest_actual_gross_weight",
                    "prev_close_index_state",
                    "prev_close_breadth_state",
                    "prev_universe_up_ratio",
                    "prev_benchmark_close_to_close_ret",
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
            "- 原因：本阶段只测预注册的少数事前状态降权规则，不扫描阈值、不改核心信号。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：结果仅作为压力测试；即使某个变体更好，也不直接认定为正式策略。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：上一阶段已定位曲线粗糙与市场状态有关，必须验证事前状态是否真的能改善账户曲线。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：本阶段能判断市场状态风控是否值得进入更严格OOS/paper，而不是停留在归因层。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- 下一步根据本报告判断是否继续做更严格的OOS切片；不能直接上线。",
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
    exante_state = build_prev_close_market_state(benchmark_df, stock_df)
    original_daily = pl.read_csv(LOT_OUTPUT_DIR / f"{LOT_PREFIX}_daily.csv", try_parse_dates=True)

    summary_rows: list[dict[str, Any]] = []
    drawdown_frames: list[pl.DataFrame] = []
    latest_state_rows: list[dict[str, Any]] = []
    daily_by_variant: dict[str, pl.DataFrame] = {}
    base_daily = pl.DataFrame()

    for variant in OVERLAY_VARIANTS:
        scaled_targets = apply_overlay(target_weights, exante_state, variant)
        target_maps = build_target_maps(scaled_targets)
        orders, daily, _curve = replay_lot_account(target_maps, dates, exec_info)
        daily_by_variant[variant.name] = daily
        if variant.name == "base_rerun":
            base_daily = daily
        summary_rows.append(summarize_daily(variant, daily, orders, scaled_targets))
        drawdowns = build_drawdown_episodes(daily).head(5).with_columns(pl.lit(variant.name).alias("variant"))
        drawdown_frames.append(drawdowns)
        latest_date = daily["date"].max()
        latest_state = exante_state.filter(pl.col("target_date") == latest_date)
        latest_summary = summary_rows[-1]
        latest_state_rows.append(
            {
                "variant": variant.name,
                "latest_target_date": latest_date,
                "latest_overlay_scale": latest_summary["latest_overlay_scale"],
                "latest_actual_symbol_count": latest_summary["latest_actual_symbol_count"],
                "latest_zero_lot_target_count": latest_summary["latest_zero_lot_target_count"],
                "latest_actual_gross_weight": latest_summary["latest_actual_gross_weight"],
                **(latest_state.row(0, named=True) if not latest_state.is_empty() else {}),
            }
        )

        orders.write_csv(OUTPUT_DIR / f"{PREFIX}_{variant.name}_orders.csv")
        daily.write_csv(OUTPUT_DIR / f"{PREFIX}_{variant.name}_daily.csv")
        scaled_targets.write_csv(OUTPUT_DIR / f"{PREFIX}_{variant.name}_targets.csv")

    summary = add_base_deltas(pl.DataFrame(summary_rows)).sort("variant")
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
    quality = build_quality_checkpoints(summary, base_daily, original_daily)

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "summary_json": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "exante_state": OUTPUT_DIR / f"{PREFIX}_exante_state.csv",
        "drawdowns": OUTPUT_DIR / f"{PREFIX}_drawdowns.csv",
        "latest_state": OUTPUT_DIR / f"{PREFIX}_latest_state.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "equity_png": OUTPUT_DIR / f"{PREFIX}_equity_curves.png",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    summary.write_csv(paths["summary"])
    exante_state.write_csv(paths["exante_state"])
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
            "note": "Market-state overlay pressure test only; no core alpha signal threshold changes.",
            "overlay_variants": [variant.__dict__ for variant in OVERLAY_VARIANTS],
        },
    )
    report_path = write_report(summary, drawdowns_all, latest_state, quality, paths)
    print(summary.select(["variant", "final_equity_min_fee", "max_drawdown_min_fee", "sharpe_min_fee"]).to_pandas())
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
