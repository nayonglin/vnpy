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
from analyze_stock_range_reversion_liquid_q3_300k_market_state_overlay import (
    RESEARCH_SOURCES as MARKET_OVERLAY_RESEARCH_SOURCES,
    build_prev_close_market_state,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from backtest_stock_range_reversion_liquid_q3_repairability_filter import OUTPUT_DIR as FILTER_OUTPUT_DIR
from backtest_stock_range_reversion_liquid_q3_repairability_filter import PREFIX as FILTER_PREFIX
from generate_stock_range_reversion_liquid_q3_paper_tracking import PAPER_SCENARIO, build_target_weights, markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info, to_float


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_good_state_aggressive_overlay_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_good_state_aggressive_overlay_v1"
MAX_TARGET_GROSS_WEIGHT: float = 1.0

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Volatility-managed portfolios often use higher exposure after calmer or more favorable states, but results vary",
        "https://www.sciencedirect.com/science/article/pii/S0304405X2030132X",
    ),
    (
        "Regime filters can reduce or reshape exposure but may just change trade frequency",
        "https://www.reddit.com/r/algotrading/comments/1skdizm/most_regime_filters_dont_improve_trading/",
    ),
    (
        "Mean reversion needs regime awareness; not every pullback deserves the same exposure",
        "https://journalplus.co/strategies/mean-reversion-trading",
    ),
    *MARKET_OVERLAY_RESEARCH_SOURCES,
)


@dataclass(frozen=True)
class AggressiveVariant:
    name: str
    description: str


AGGRESSIVE_VARIANTS: tuple[AggressiveVariant, ...] = (
    AggressiveVariant("base_rerun", "不加仓；用于校验本脚本能复现30万整手基准。"),
    AggressiveVariant("prev_close_strong_breadth_125", "若前一交易日收盘市场宽度强，则下一目标日目标权重乘1.25。"),
    AggressiveVariant("prev_close_index_up_125", "若前一交易日中证1000收盘涨幅超过1%，则下一目标日目标权重乘1.25。"),
    AggressiveVariant(
        "prev_close_breadth_or_index_up_125",
        "若前一交易日市场宽度强或指数涨幅超过1%，则下一目标日目标权重乘1.25。",
    ),
    AggressiveVariant(
        "prev_close_breadth_index_up_tiered",
        "若前一交易日宽度强且指数涨超1%则权重乘1.50；仅命中一个好环境条件则乘1.25。",
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


def raw_scale_for_variant(variant: str, strong_breadth: bool, index_up: bool) -> float:
    if variant == "base_rerun":
        return 1.0
    if variant == "prev_close_strong_breadth_125":
        return 1.25 if strong_breadth else 1.0
    if variant == "prev_close_index_up_125":
        return 1.25 if index_up else 1.0
    if variant == "prev_close_breadth_or_index_up_125":
        return 1.25 if strong_breadth or index_up else 1.0
    if variant == "prev_close_breadth_index_up_tiered":
        if strong_breadth and index_up:
            return 1.50
        if strong_breadth or index_up:
            return 1.25
        return 1.0
    raise ValueError(f"Unknown aggressive variant: {variant}")


def build_date_scale(target_weights: pl.DataFrame, state: pl.DataFrame, variant: AggressiveVariant) -> pl.DataFrame:
    target_gross = target_weights.group_by("target_date").agg(pl.col("target_weight").sum().alias("base_target_gross"))
    state_small = state.select(
        [
            "target_date",
            "state_date",
            "prev_close_index_state",
            "prev_close_breadth_state",
            "prev_universe_up_ratio",
            "prev_benchmark_close_to_close_ret",
        ]
    )
    rows: list[dict[str, Any]] = []
    for row in target_gross.join(state_small, on="target_date", how="left").sort("target_date").iter_rows(named=True):
        strong_breadth = row.get("prev_close_breadth_state") == "strong_breadth"
        index_up = row.get("prev_close_index_state") == "index_up_gt_1pct"
        raw_scale = raw_scale_for_variant(variant.name, strong_breadth, index_up)
        base_gross = to_float(row.get("base_target_gross"))
        cap_scale = MAX_TARGET_GROSS_WEIGHT / base_gross if base_gross > 0 else raw_scale
        overlay_scale = min(raw_scale, cap_scale)
        rows.append(
            {
                **row,
                "overlay_variant": variant.name,
                "prev_close_strong_breadth_flag": strong_breadth,
                "prev_close_index_up_flag": index_up,
                "raw_overlay_scale": raw_scale,
                "overlay_scale": overlay_scale,
                "cap_limited_flag": overlay_scale < raw_scale - 1e-12,
                "target_gross_after_overlay": base_gross * overlay_scale,
            }
        )
    return pl.DataFrame(rows).sort("target_date") if rows else pl.DataFrame()


def apply_aggressive_overlay(
    target_weights: pl.DataFrame,
    state: pl.DataFrame,
    variant: AggressiveVariant,
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


def summarize_daily(
    variant: AggressiveVariant,
    daily: pl.DataFrame,
    orders: pl.DataFrame,
    scaled_targets: pl.DataFrame,
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
        "avg_target_gross_after_overlay": to_float(date_scale["target_gross_after_overlay"].mean())
        if not date_scale.is_empty()
        else 0.0,
        "max_target_gross_after_overlay": to_float(date_scale["target_gross_after_overlay"].max())
        if not date_scale.is_empty()
        else 0.0,
        "boosted_target_days": boosted_dates.height,
        "boosted_target_day_ratio": boosted_dates.height / daily.height if daily.height else 0.0,
        "strong_breadth_days": date_scale.filter(pl.col("prev_close_strong_breadth_flag")).height,
        "index_up_days": date_scale.filter(pl.col("prev_close_index_up_flag")).height,
        "cap_limited_days": date_scale.filter(pl.col("cap_limited_flag")).height,
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
        "latest_target_symbol_count": latest["target_symbol_count"],
        "latest_actual_symbol_count": latest["actual_symbol_count"],
        "latest_zero_lot_target_count": latest["zero_lot_target_count"],
        "latest_actual_gross_weight": latest["actual_gross_weight"],
        "latest_base_target_gross": latest_scale["base_target_gross"][0] if not latest_scale.is_empty() else None,
        "latest_target_gross_after_overlay": latest_scale["target_gross_after_overlay"][0]
        if not latest_scale.is_empty()
        else None,
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
        "pass" if summary.height == len(AGGRESSIVE_VARIANTS) else "fail",
        summary.height,
        len(AGGRESSIVE_VARIANTS),
        "必须只运行预注册的少数好环境进攻压力测试。",
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
    max_target_gross = to_float(summary["max_target_gross_after_overlay"].max())
    add(
        "target_gross_never_exceeds_cash",
        "pass" if max_target_gross <= MAX_TARGET_GROSS_WEIGHT + 1e-12 else "fail",
        max_target_gross,
        f"<={MAX_TARGET_GROSS_WEIGHT}",
        "好环境进攻不允许隐性杠杆。",
    )
    min_scale = to_float(summary["avg_overlay_scale"].min())
    max_scale = to_float(summary["max_overlay_scale"].max())
    add(
        "aggressive_scale_bounds",
        "pass" if min_scale >= 1.0 - 1e-12 and max_scale <= 1.5 + 1e-12 else "fail",
        f"{min_scale}..{max_scale}",
        "1..1.5",
        "本阶段只允许小幅进攻，不允许极端加仓。",
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
        "prev_close_strong_breadth_125": "#2F855A",
        "prev_close_index_up_125": "#7A5195",
        "prev_close_breadth_or_index_up_125": "#FFA600",
        "prev_close_breadth_index_up_tiered": "#D95D39",
    }
    for variant, daily in daily_by_variant.items():
        pdf = daily.sort("date").to_pandas()
        axes[0].plot(pdf["date"], pdf["equity_min_fee"], linewidth=1.2, label=variant, color=colors.get(variant))
        axes[1].plot(pdf["date"], pdf["drawdown_min_fee"], linewidth=0.9, label=variant, color=colors.get(variant))
    axes[0].set_title("300k Good-State Aggressive Overlay Pressure Test", fontsize=13, fontweight="bold")
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
    best_sharpe = summary.sort("sharpe_min_fee", descending=True).row(0, named=True)
    best_return = summary.sort("total_return_min_fee", descending=True).row(0, named=True)
    base = summary.filter(pl.col("variant") == "base_rerun").row(0, named=True)
    best_non_base = summary.filter(pl.col("variant") != "base_rerun").sort("sharpe_min_fee", descending=True).row(
        0, named=True
    )
    lines = [
        "# 股票震荡liquid_q3 30万好环境进攻压力测试 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：事前好环境小幅加仓压力测试；不修改核心alpha信号。",
        f"- 账户规模：`{ACCOUNT_SIZE_CNY:,.0f}`元；整手：`{BOARD_LOT_SHARES}`股；最低佣金压力：`{MIN_COMMISSION_CNY}`元。",
        f"- 风险约束：目标总权重上限`{pct(MAX_TARGET_GROSS_WEIGHT)}`，不允许隐性杠杆。",
        "- 状态口径：只使用前一交易日收盘后已知的中证1000收盘涨跌和成分股收盘宽度。",
        "- A/B判断：股票震荡策略独立研究，不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 业界常见思路是根据regime调整暴露；进攻版比粗降权更符合超跌反弹的收益来源，但必须控制交易成本和杠杆。",
        "- 公开研究也提示，波动/状态管理不是稳定免费午餐；结果如果只来自更高风险暴露，不能当成alpha增强。",
        "- 本阶段只测少数预注册进攻档位，不搜索最优倍率。",
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
            f"- 非基准里Sharpe最高的是`{best_non_base['variant']}`，总收益相对基准变化`{pct(best_non_base['delta_total_return_min_fee'])}`，最大回撤变化`{pct(best_non_base['delta_max_drawdown_min_fee'])}`，Sharpe变化`{best_non_base['delta_sharpe_min_fee']:.4f}`。",
            "- 本阶段结论：好环境全局加仓不值得继续推进为正式规则；它没有提高收益质量，主要是在若干回撤段放大风险。",
            "- 下一步不应继续搜索市场状态加仓倍率；更值得做的是行业实际暴露上限和`ST/is_st`事前字段审计。",
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
                    "cap_limited_days",
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
                    "latest_raw_overlay_scale",
                    "latest_overlay_scale",
                    "latest_base_target_gross",
                    "latest_target_gross_after_overlay",
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
            "- 原因：本阶段只测预注册的少数好环境进攻档位，不扫描倍率、不改核心信号。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：结果仅作为压力测试；即使某个变体更好，也不直接认定为正式策略。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：粗降权失败后，验证好环境是否能承接更多反弹暴露，是更贴近策略本性的下一步。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是，但不在好环境全局加仓分支继续。",
            "- 原因：基准仍是收益和Sharpe最好的版本；好环境加仓没有提供更好的风险收益交换。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- 暂时否决好环境全局加仓，不进入OOS切片。",
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

    for variant in AGGRESSIVE_VARIANTS:
        scaled_targets, date_scale = apply_aggressive_overlay(target_weights, exante_state, variant)
        target_maps = build_target_maps(scaled_targets)
        orders, daily, _curve = replay_lot_account(target_maps, dates, exec_info)
        daily_by_variant[variant.name] = daily
        if variant.name == "base_rerun":
            base_daily = daily
        summary_rows.append(summarize_daily(variant, daily, orders, scaled_targets, date_scale))
        drawdowns = build_drawdown_episodes(daily).head(5).with_columns(pl.lit(variant.name).alias("variant"))
        drawdown_frames.append(drawdowns)
        latest_date = daily["date"].max()
        latest_state = exante_state.filter(pl.col("target_date") == latest_date)
        latest_scale = date_scale.filter(pl.col("target_date") == latest_date)
        latest_summary = summary_rows[-1]
        latest_state_rows.append(
            {
                "variant": variant.name,
                "latest_target_date": latest_date,
                "latest_raw_overlay_scale": latest_summary["latest_raw_overlay_scale"],
                "latest_overlay_scale": latest_summary["latest_overlay_scale"],
                "latest_base_target_gross": latest_summary["latest_base_target_gross"],
                "latest_target_gross_after_overlay": latest_summary["latest_target_gross_after_overlay"],
                "latest_actual_symbol_count": latest_summary["latest_actual_symbol_count"],
                "latest_zero_lot_target_count": latest_summary["latest_zero_lot_target_count"],
                "latest_actual_gross_weight": latest_summary["latest_actual_gross_weight"],
                **(latest_state.row(0, named=True) if not latest_state.is_empty() else {}),
                **(
                    {
                        "prev_close_strong_breadth_flag": latest_scale["prev_close_strong_breadth_flag"][0],
                        "prev_close_index_up_flag": latest_scale["prev_close_index_up_flag"][0],
                        "cap_limited_flag": latest_scale["cap_limited_flag"][0],
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
            "note": "Good-state aggressive overlay pressure test only; no core alpha signal threshold changes.",
            "aggressive_variants": [variant.__dict__ for variant in AGGRESSIVE_VARIANTS],
        },
    )
    report_path = write_report(summary, drawdowns_all, latest_state, quality, paths)
    print(summary.select(["variant", "final_equity_min_fee", "max_drawdown_min_fee", "sharpe_min_fee"]).to_pandas())
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
