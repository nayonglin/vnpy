from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

import analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility as lot
from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_curve_smoothness_attribution import (
    build_drawdown_episodes,
    build_full_position_daily,
    downside_vol,
)
from analyze_stock_range_reversion_liquid_q3_30w_high_return_shape_grid import (
    ACCOUNT_SIZE_CNY,
    HIGH_RETURN_TARGET,
    MAX_DRAWDOWN_LIMIT,
    summarize_daily_extra,
    to_float,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info


SOURCE_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_replay_2018_2026"
).expanduser().resolve()
SOURCE_PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_replay_v1"

OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_industry_cap_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_industry_cap_v1"

FOCUS_SCENARIOS: tuple[str, ...] = (
    "industry_resid_core_h10_top8_gross100_ind2",
    "industry_resid_core_h10_top5_gross100_ind1",
    "industry_resid_core_h10_top8_gross70_ind2",
    "industry_resid_core_h10_top5_gross70_ind1",
)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Portfolio constraints and regularization",
        "https://bookdown.org/palomar/portfoliooptimizationbook/6.2-portfolio-constraints.html",
    ),
    (
        "cvxportfolio constraints API",
        "https://www.cvxportfolio.com/en/stable/constraints.html",
    ),
    (
        "GitHub sector exposure portfolio constraints search",
        "https://github.com/search?q=sector+exposure+constraint+portfolio+python&type=repositories",
    ),
    (
        "Short-term residual reversal",
        "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1911449",
    ),
    (
        "Combining return reversal and industry momentum",
        "https://www.cxoadvisory.com/technical-trading/combining-return-reversal-and-industry-momentum/",
    ),
)


@dataclass(frozen=True)
class IndustryCapVariant:
    name: str
    cap: float | None
    description: str


INDUSTRY_CAP_VARIANTS: tuple[IndustryCapVariant, ...] = (
    IndustryCapVariant("base_rerun", None, "不做行业目标权重上限；用于复现第308阶段30万整手复放。"),
    IndustryCapVariant("industry_cap20", 0.20, "同一目标日同一行业目标权重上限20%；不把腾出的权重再分配。"),
    IndustryCapVariant("industry_cap15", 0.15, "同一目标日同一行业目标权重上限15%；不把腾出的权重再分配。"),
    IndustryCapVariant("industry_cap10_stress", 0.10, "同一目标日同一行业目标权重上限10%；只作为压力反证，不作为候选优化。"),
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def read_csv_with_symbol(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, try_parse_dates=True, schema_overrides={"symbol": pl.Utf8})


def annualized_vol(values: list[float]) -> float:
    clean = [value for value in values if value == value]
    if len(clean) < 2:
        return 0.0
    mean = sum(clean) / len(clean)
    variance = sum((value - mean) ** 2 for value in clean) / (len(clean) - 1)
    return sqrt(max(variance, 0.0)) * sqrt(TRADING_DAYS)


def annualized_sharpe(values: list[float]) -> float:
    clean = [value for value in values if value == value]
    if len(clean) < 2:
        return 0.0
    mean = sum(clean) / len(clean)
    variance = sum((value - mean) ** 2 for value in clean) / (len(clean) - 1)
    if variance <= 0:
        return 0.0
    return mean / sqrt(variance) * sqrt(TRADING_DAYS)


def apply_industry_cap(target_weights: pl.DataFrame, variant: IndustryCapVariant) -> pl.DataFrame:
    industry_sum = pl.col("target_weight").sum().over(["scenario", "target_date", "industry"])
    capped = (
        target_weights.with_columns(
            pl.col("scenario").alias("base_scenario"),
            pl.lit(variant.name).alias("cap_name"),
            pl.lit(variant.description).alias("cap_description"),
            pl.lit(variant.cap).alias("industry_cap"),
            pl.col("target_weight").alias("base_target_weight"),
            industry_sum.alias("base_industry_target_weight"),
        )
        .with_columns(
            pl.when(pl.lit(variant.cap).is_null())
            .then(pl.lit(1.0))
            .when(pl.col("base_industry_target_weight") > pl.lit(variant.cap or 0.0))
            .then(pl.lit(variant.cap or 0.0) / pl.col("base_industry_target_weight"))
            .otherwise(pl.lit(1.0))
            .alias("cap_scale")
        )
        .with_columns(
            (pl.col("base_target_weight") * pl.col("cap_scale")).alias("target_weight"),
            (pl.col("base_target_weight") * pl.col("cap_scale") * ACCOUNT_SIZE_CNY).alias("target_amount_cny"),
            (pl.col("base_scenario") + "_" + pl.col("cap_name")).alias("scenario"),
        )
        .sort(["scenario", "target_date", "industry", "symbol"])
    )
    return capped


def summarize_variant(
    base_scenario: str,
    variant: IndustryCapVariant,
    orders: pl.DataFrame,
    daily: pl.DataFrame,
    capped_targets: pl.DataFrame,
) -> dict[str, Any]:
    summary = lot.summarize_orders(orders, daily)
    summary = summarize_daily_extra(summary, daily)
    returns = [float(value) for value in daily["strategy_daily_ret_min_fee"].to_list()]
    selected = capped_targets.filter(pl.col("base_scenario") == base_scenario)
    daily_target = (
        selected.group_by("target_date")
        .agg(
            pl.col("base_target_weight").sum().alias("base_target_gross"),
            pl.col("target_weight").sum().alias("capped_target_gross"),
            (pl.col("cap_scale") < 0.999999).any().alias("has_cap"),
        )
        .sort("target_date")
    )
    industry_target = (
        selected.group_by(["target_date", "industry"])
        .agg(
            pl.col("base_target_weight").sum().alias("base_industry_target_weight"),
            pl.col("target_weight").sum().alias("capped_industry_target_weight"),
            pl.col("cap_scale").first().alias("cap_scale"),
        )
        .sort(["target_date", "industry"])
    )
    cap_days = daily_target.filter(pl.col("has_cap")).height
    cap_industry_days = industry_target.filter(pl.col("cap_scale") < 0.999999).height
    summary.update(
        {
            "scenario": f"{base_scenario}_{variant.name}",
            "base_scenario": base_scenario,
            "cap_name": variant.name,
            "cap_description": variant.description,
            "industry_cap": variant.cap,
            "annualized_vol_min_fee": annualized_vol(returns),
            "downside_vol_min_fee": downside_vol(returns),
            "annualized_sharpe_check": annualized_sharpe(returns),
            "worst_daily_ret_min_fee": min(returns) if returns else 0.0,
            "avg_base_target_gross": to_float(daily_target["base_target_gross"].mean()),
            "avg_capped_target_gross": to_float(daily_target["capped_target_gross"].mean()),
            "avg_target_gross_scale": (
                to_float(daily_target["capped_target_gross"].mean()) / to_float(daily_target["base_target_gross"].mean())
                if to_float(daily_target["base_target_gross"].mean()) > 0
                else 0.0
            ),
            "capped_target_days": cap_days,
            "capped_target_day_ratio": cap_days / daily.height if daily.height else 0.0,
            "capped_industry_days": cap_industry_days,
            "capped_industry_day_ratio": cap_industry_days / industry_target.height if industry_target.height else 0.0,
            "avg_daily_max_industry_target_before": to_float(
                industry_target.group_by("target_date")
                .agg(pl.col("base_industry_target_weight").max().alias("value"))["value"]
                .mean()
            ),
            "avg_daily_max_industry_target_after": to_float(
                industry_target.group_by("target_date")
                .agg(pl.col("capped_industry_target_weight").max().alias("value"))["value"]
                .mean()
            ),
            "max_industry_target_before": to_float(industry_target["base_industry_target_weight"].max()),
            "max_industry_target_after": to_float(industry_target["capped_industry_target_weight"].max()),
        }
    )
    meta_cols = ["shape_horizon", "shape_top_k", "shape_basket_gross_weight", "shape_max_per_industry"]
    summary.update(selected.select(meta_cols).row(0, named=True))
    return summary


def add_base_deltas(summary: pl.DataFrame) -> pl.DataFrame:
    base = (
        summary.filter(pl.col("cap_name") == "base_rerun")
        .select(
            "base_scenario",
            pl.col("final_equity_min_fee").alias("base_final_equity_min_fee"),
            pl.col("total_return_min_fee").alias("base_total_return_min_fee"),
            pl.col("max_drawdown_min_fee").alias("base_max_drawdown_min_fee"),
            pl.col("sharpe_min_fee").alias("base_sharpe_min_fee"),
            pl.col("annualized_vol_min_fee").alias("base_annualized_vol_min_fee"),
            pl.col("downside_vol_min_fee").alias("base_downside_vol_min_fee"),
            pl.col("worst_daily_ret_min_fee").alias("base_worst_daily_ret_min_fee"),
            pl.col("avg_actual_gross_weight").alias("base_avg_actual_gross_weight"),
        )
    )
    return (
        summary.join(base, on="base_scenario", how="left")
        .with_columns(
            (pl.col("final_equity_min_fee") - pl.col("base_final_equity_min_fee")).alias("delta_final_equity_min_fee"),
            (pl.col("total_return_min_fee") - pl.col("base_total_return_min_fee")).alias("delta_total_return_min_fee"),
            (pl.col("max_drawdown_min_fee") - pl.col("base_max_drawdown_min_fee")).alias("delta_max_drawdown_min_fee"),
            (pl.col("sharpe_min_fee") - pl.col("base_sharpe_min_fee")).alias("delta_sharpe_min_fee"),
            (pl.col("annualized_vol_min_fee") - pl.col("base_annualized_vol_min_fee")).alias(
                "delta_annualized_vol_min_fee"
            ),
            (pl.col("downside_vol_min_fee") - pl.col("base_downside_vol_min_fee")).alias("delta_downside_vol_min_fee"),
            (pl.col("worst_daily_ret_min_fee") - pl.col("base_worst_daily_ret_min_fee")).alias(
                "delta_worst_daily_ret_min_fee"
            ),
            (pl.col("avg_actual_gross_weight") - pl.col("base_avg_actual_gross_weight")).alias(
                "delta_avg_actual_gross_weight"
            ),
        )
        .drop(
            [
                "base_final_equity_min_fee",
                "base_total_return_min_fee",
                "base_max_drawdown_min_fee",
                "base_sharpe_min_fee",
                "base_annualized_vol_min_fee",
                "base_downside_vol_min_fee",
                "base_worst_daily_ret_min_fee",
                "base_avg_actual_gross_weight",
            ]
        )
    )


def build_yearly(daily: pl.DataFrame) -> pl.DataFrame:
    if daily.is_empty():
        return pl.DataFrame()
    return (
        daily.with_columns(pl.col("date").dt.year().alias("year"))
        .group_by(["base_scenario", "cap_name", "scenario", "year"])
        .agg(
            ((1 + pl.col("strategy_daily_ret_min_fee")).product() - 1).alias("year_return_min_fee"),
            pl.col("drawdown_min_fee").min().alias("year_curve_drawdown_min_fee"),
            pl.col("actual_gross_weight").mean().alias("avg_actual_gross_weight"),
            pl.col("actual_symbol_count").mean().alias("avg_actual_symbol_count"),
            pl.col("zero_lot_target_count").sum().alias("zero_lot_target_count"),
            pl.col("target_symbol_count").sum().alias("target_symbol_count"),
            pl.col("filled_amount_sum_cny").sum().alias("filled_amount_sum_cny"),
        )
        .with_columns(
            (pl.col("zero_lot_target_count") / pl.col("target_symbol_count")).fill_nan(0.0).alias(
                "zero_lot_target_ratio"
            )
        )
        .sort(["base_scenario", "cap_name", "year"])
    )


def build_actual_industry_exposure(position_daily: pl.DataFrame) -> pl.DataFrame:
    if position_daily.is_empty():
        return pl.DataFrame()
    industry_daily = (
        position_daily.group_by(["base_scenario", "cap_name", "scenario", "date", "industry"])
        .agg(
            pl.col("actual_weight").sum().alias("actual_industry_weight"),
            pl.col("gross_contribution").sum().alias("gross_contribution"),
            pl.col("symbol").n_unique().alias("symbols"),
        )
        .sort(["base_scenario", "cap_name", "date", "actual_industry_weight"], descending=[False, False, False, True])
    )
    return industry_daily


def summarize_actual_industry_exposure(industry_daily: pl.DataFrame) -> pl.DataFrame:
    if industry_daily.is_empty():
        return pl.DataFrame()
    return (
        industry_daily.group_by(["base_scenario", "cap_name", "scenario"])
        .agg(
            pl.col("actual_industry_weight").mean().alias("avg_industry_weight"),
            pl.col("actual_industry_weight").max().alias("max_actual_industry_weight"),
            pl.col("actual_industry_weight").quantile(0.95).alias("p95_actual_industry_weight"),
            (pl.col("actual_industry_weight") > 0.20).mean().alias("industry_days_gt_20_ratio"),
            (pl.col("actual_industry_weight") > 0.15).mean().alias("industry_days_gt_15_ratio"),
            (pl.col("actual_industry_weight") > 0.10).mean().alias("industry_days_gt_10_ratio"),
        )
        .sort(["base_scenario", "cap_name"])
    )


def build_cap_effect(capped_targets: pl.DataFrame) -> pl.DataFrame:
    if capped_targets.is_empty():
        return pl.DataFrame()
    industry_day = (
        capped_targets.group_by(["base_scenario", "cap_name", "target_date", "industry"])
        .agg(
            pl.col("base_target_weight").sum().alias("base_industry_target_weight"),
            pl.col("target_weight").sum().alias("capped_industry_target_weight"),
            pl.col("cap_scale").first().alias("cap_scale"),
        )
    )
    daily = (
        industry_day.group_by(["base_scenario", "cap_name", "target_date"])
        .agg(
            pl.col("base_industry_target_weight").sum().alias("base_target_gross"),
            pl.col("capped_industry_target_weight").sum().alias("capped_target_gross"),
            pl.col("base_industry_target_weight").max().alias("max_industry_before"),
            pl.col("capped_industry_target_weight").max().alias("max_industry_after"),
            (pl.col("cap_scale") < 0.999999).any().alias("has_cap"),
        )
    )
    return (
        daily.group_by(["base_scenario", "cap_name"])
        .agg(
            pl.len().alias("target_days"),
            pl.col("has_cap").sum().alias("capped_days"),
            pl.col("has_cap").mean().alias("capped_day_ratio"),
            pl.col("base_target_gross").mean().alias("avg_base_target_gross"),
            pl.col("capped_target_gross").mean().alias("avg_capped_target_gross"),
            (pl.col("capped_target_gross").mean() / pl.col("base_target_gross").mean()).alias("avg_target_gross_scale"),
            pl.col("max_industry_before").mean().alias("avg_daily_max_industry_before"),
            pl.col("max_industry_after").mean().alias("avg_daily_max_industry_after"),
            pl.col("max_industry_before").max().alias("max_industry_before"),
            pl.col("max_industry_after").max().alias("max_industry_after"),
        )
        .sort(["base_scenario", "cap_name"])
    )


def build_quality(summary: pl.DataFrame, original_daily: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []

    def add(checkpoint: str, status: str, value: Any, expected: Any, note: str) -> None:
        rows.append(
            {
                "checkpoint": checkpoint,
                "status": status,
                "value": "" if value is None else str(value),
                "expected": "" if expected is None else str(expected),
                "note": note,
            }
        )

    add(
        "focus_scenario_count",
        "pass" if summary["base_scenario"].n_unique() == len(FOCUS_SCENARIOS) else "fail",
        summary["base_scenario"].n_unique(),
        len(FOCUS_SCENARIOS),
        "只运行第313阶段归因后的代表形状。",
    )
    add(
        "cap_variant_count",
        "pass" if summary["cap_name"].n_unique() == len(INDUSTRY_CAP_VARIANTS) else "fail",
        summary["cap_name"].n_unique(),
        len(INDUSTRY_CAP_VARIANTS),
        "行业上限只做20/15/10三档压力测试，加base复现。",
    )
    base = summary.filter(pl.col("cap_name") == "base_rerun").select("base_scenario", "final_equity_min_fee")
    original = original_daily.filter(pl.col("scenario").is_in(FOCUS_SCENARIOS)).group_by("scenario").agg(
        pl.col("equity_min_fee").last().alias("original_final_equity_min_fee")
    )
    compare = base.join(original, left_on="base_scenario", right_on="scenario", how="left").with_columns(
        (pl.col("final_equity_min_fee") - pl.col("original_final_equity_min_fee")).abs().alias("diff")
    )
    max_base_diff = to_float(compare["diff"].max()) if not compare.is_empty() else None
    add(
        "base_rerun_matches_stage308",
        "pass" if max_base_diff is not None and max_base_diff <= 1e-12 else "fail",
        max_base_diff,
        "<=1e-12",
        "不设行业上限必须复现第308阶段结果。",
    )
    best_dd = summary.select(pl.col("max_drawdown_min_fee").max()).item()
    best_return = summary.select(pl.col("total_return_min_fee").max()).item()
    add(
        "best_drawdown_within_20pct",
        "pass" if best_dd >= MAX_DRAWDOWN_LIMIT else "warn",
        pct(best_dd),
        ">=-20%",
        "若没有进入20%以内，本阶段不能形成候选策略。",
    )
    add(
        "high_return_target_seen",
        "pass" if best_return >= HIGH_RETURN_TARGET else "warn",
        pct(best_return),
        ">=100%",
        "用户目标是30万本金下高收益。",
    )
    add(
        "no_signal_threshold_change",
        "pass",
        "only industry target exposure cap",
        "only industry target exposure cap",
        "本阶段不改变选股信号、分数、top_k、持有期。",
    )
    add(
        "no_reallocation_after_cap",
        "pass",
        "capped weight is not redistributed",
        "capped weight is not redistributed",
        "行业上限是风险降暴露，不是把权重挪到次优股票。",
    )
    return pl.DataFrame(rows)


def write_report(
    summary: pl.DataFrame,
    yearly: pl.DataFrame,
    drawdowns: pl.DataFrame,
    cap_effect: pl.DataFrame,
    actual_industry_summary: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    pass_dd = summary.filter(pl.col("max_drawdown_min_fee") >= MAX_DRAWDOWN_LIMIT).sort(
        ["total_return_min_fee", "sharpe_min_fee"], descending=[True, True]
    )
    best_dd = summary.sort(["max_drawdown_min_fee", "total_return_min_fee"], descending=[True, True]).row(0, named=True)
    best_return = summary.sort(["total_return_min_fee", "max_drawdown_min_fee"], descending=[True, True]).row(
        0, named=True
    )
    non_base = summary.filter(pl.col("cap_name") != "base_rerun").sort(
        ["delta_max_drawdown_min_fee", "total_return_min_fee"], descending=[True, True]
    )
    best_delta = non_base.row(0, named=True) if not non_base.is_empty() else None
    if best_delta is None:
        delta_line = "- 相对基准回撤改善最大：无"
    elif to_float(best_delta.get("delta_max_drawdown_min_fee")) <= 0:
        delta_line = "- 所有行业上限变体均未改善最大回撤；行业集中不是本轮可交易修复点。"
    else:
        delta_line = (
            f"- 相对基准回撤改善最大：`{best_delta['scenario']}`，回撤改善"
            f"`{pct(best_delta['delta_max_drawdown_min_fee'])}`，收益变化"
            f"`{pct(best_delta['delta_total_return_min_fee'])}`。"
        )
    lines = [
        "# 股票震荡industry_resid_core 30万行业目标暴露上限回放 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前模式：day。",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：固定第308阶段信号和代表组合形状，只测试行业目标权重上限是否能改善第313阶段长回撤。",
        f"- 账户规模：`{ACCOUNT_SIZE_CNY:,.0f}`元；用户回撤目标：`20%`以内；高收益参考目标：`100%`以上。",
        "- A/B判断：股票震荡独立研究，不接入第78，不触发A/B。",
        "",
        "## 外部调研判断",
        "",
        "- 行业/资产暴露上限是组合构建里常见的硬约束，适合处理单一行业风险集中。",
        "- 但对均值回归策略，行业上限如果只是降总暴露，可能会同时砍掉反弹收益；因此本阶段只作为风险层反证，不重分配权重。",
        "- GitHub公开实现更多是组合约束/优化框架或教学策略，不能直接复制为A股30万交易系统。",
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
            f"- 回撤20%以内候选：{'无' if pass_dd.is_empty() else pass_dd['scenario'][0]}",
            f"- 最大回撤最浅：`{best_dd['scenario']}`，总收益`{pct(best_dd['total_return_min_fee'])}`，最大回撤`{pct(best_dd['max_drawdown_min_fee'])}`，Sharpe `{best_dd['sharpe_min_fee']:.3f}`。",
            f"- 总收益最高：`{best_return['scenario']}`，总收益`{pct(best_return['total_return_min_fee'])}`，最大回撤`{pct(best_return['max_drawdown_min_fee'])}`，Sharpe `{best_return['sharpe_min_fee']:.3f}`。",
            delta_line,
            f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。",
            "",
            "## 场景汇总",
            "",
            markdown_table(
                summary,
                [
                    "base_scenario",
                    "cap_name",
                    "industry_cap",
                    "final_equity_min_fee",
                    "total_return_min_fee",
                    "max_drawdown_min_fee",
                    "delta_total_return_min_fee",
                    "delta_max_drawdown_min_fee",
                    "sharpe_min_fee",
                    "annualized_vol_min_fee",
                    "downside_vol_min_fee",
                    "worst_daily_ret_min_fee",
                    "avg_actual_gross_weight",
                    "avg_actual_symbol_count",
                    "avg_target_gross_scale",
                    "capped_target_day_ratio",
                    "zero_lot_target_ratio",
                    "latest_exposure_capture_ratio",
                    "return_over_max_dd",
                ],
                max_rows=160,
            ),
            "",
            "## 行业上限生效强度",
            "",
            markdown_table(
                cap_effect,
                [
                    "base_scenario",
                    "cap_name",
                    "target_days",
                    "capped_days",
                    "capped_day_ratio",
                    "avg_base_target_gross",
                    "avg_capped_target_gross",
                    "avg_target_gross_scale",
                    "avg_daily_max_industry_before",
                    "avg_daily_max_industry_after",
                    "max_industry_before",
                    "max_industry_after",
                ],
                max_rows=120,
            ),
            "",
            "## 实际持仓行业暴露",
            "",
            markdown_table(
                actual_industry_summary,
                [
                    "base_scenario",
                    "cap_name",
                    "avg_industry_weight",
                    "p95_actual_industry_weight",
                    "max_actual_industry_weight",
                    "industry_days_gt_20_ratio",
                    "industry_days_gt_15_ratio",
                    "industry_days_gt_10_ratio",
                ],
                max_rows=120,
            ),
            "",
            "## 最大回撤段",
            "",
            markdown_table(
                drawdowns,
                [
                    "base_scenario",
                    "cap_name",
                    "peak_date",
                    "trough_date",
                    "recovery_date",
                    "recovered",
                    "max_drawdown",
                    "trading_days_to_trough",
                    "trading_days_to_recovery_or_end",
                    "avg_actual_gross_weight",
                    "worst_daily_return",
                ],
                max_rows=100,
            ),
            "",
            "## 年度拆分",
            "",
            markdown_table(
                yearly,
                [
                    "base_scenario",
                    "cap_name",
                    "year",
                    "year_return_min_fee",
                    "year_curve_drawdown_min_fee",
                    "avg_actual_gross_weight",
                    "avg_actual_symbol_count",
                    "zero_lot_target_ratio",
                ],
                max_rows=300,
            ),
            "",
            "## 质量检查",
            "",
            markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否，但要防止把行业上限当成新一轮参数扫。",
            "- 原因：本阶段只测20/15/10三个结构性暴露边界，不改变选股信号，也不把削掉的权重重分配。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：若只有某一档上限有效，仍不能直接认为可交易，需要继续看年份和回撤段；若全部无效，则应否决路线。",
            "- 原因：行业上限是合理风控，但也可能只是样本内削峰。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第313阶段显示亏损行业反复集中，行业暴露上限是比弱广度降权更贴近组合风险的下一步。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：取决于是否能在保留收益的同时把回撤明显压近20%。",
            "- 原因：若行业上限不能解决长回撤，就说明问题更可能在信号层或市场风格层，而不是单一行业集中。",
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
    paths: dict[str, Path] = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "yearly": OUTPUT_DIR / f"{PREFIX}_yearly.csv",
        "drawdowns": OUTPUT_DIR / f"{PREFIX}_drawdowns.csv",
        "cap_effect": OUTPUT_DIR / f"{PREFIX}_cap_effect.csv",
        "position_daily": OUTPUT_DIR / f"{PREFIX}_position_daily.csv",
        "actual_industry_daily": OUTPUT_DIR / f"{PREFIX}_actual_industry_daily.csv",
        "actual_industry_summary": OUTPUT_DIR / f"{PREFIX}_actual_industry_summary.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "capped_targets": OUTPUT_DIR / f"{PREFIX}_capped_targets.csv",
        "orders": OUTPUT_DIR / f"{PREFIX}_orders.csv",
        "daily": OUTPUT_DIR / f"{PREFIX}_daily.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    target_weights = read_csv_with_symbol(SOURCE_DIR / f"{SOURCE_PREFIX}_target_weights.csv").filter(
        pl.col("scenario").is_in(FOCUS_SCENARIOS)
    )
    original_daily = pl.read_csv(SOURCE_DIR / f"{SOURCE_PREFIX}_daily.csv", try_parse_dates=True)
    stock_df, benchmark_df = load_panels()
    exec_info = build_exec_info(stock_df)

    capped_frames: list[pl.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    orders_frames: list[pl.DataFrame] = []
    daily_frames: list[pl.DataFrame] = []
    position_frames: list[pl.DataFrame] = []
    drawdown_frames: list[pl.DataFrame] = []

    for variant in INDUSTRY_CAP_VARIANTS:
        capped = apply_industry_cap(target_weights, variant)
        capped_frames.append(capped)
        for base_scenario in FOCUS_SCENARIOS:
            scenario = f"{base_scenario}_{variant.name}"
            scenario_targets = capped.filter(pl.col("scenario") == scenario).drop("scenario")
            target_maps = lot.build_target_maps(scenario_targets)
            dates = lot.build_tracking_dates(scenario_targets, benchmark_df)
            orders, daily, _curve = lot.replay_lot_account(target_maps, dates, exec_info)
            if not orders.is_empty():
                orders = orders.with_columns(
                    pl.lit(scenario).alias("scenario"),
                    pl.lit(base_scenario).alias("base_scenario"),
                    pl.lit(variant.name).alias("cap_name"),
                )
                orders_frames.append(orders)
            if not daily.is_empty():
                daily = daily.with_columns(
                    pl.lit(scenario).alias("scenario"),
                    pl.lit(base_scenario).alias("base_scenario"),
                    pl.lit(variant.name).alias("cap_name"),
                )
                daily_frames.append(daily)
                summary_rows.append(summarize_variant(base_scenario, variant, orders, daily, capped))
                positions = build_full_position_daily(daily, orders, exec_info)
                if not positions.is_empty():
                    positions = positions.with_columns(
                        pl.lit(scenario).alias("scenario"),
                        pl.lit(base_scenario).alias("base_scenario"),
                        pl.lit(variant.name).alias("cap_name"),
                    )
                    position_frames.append(positions)
                drawdown_frames.append(
                    build_drawdown_episodes(daily)
                    .head(5)
                    .with_columns(
                        pl.lit(scenario).alias("scenario"),
                        pl.lit(base_scenario).alias("base_scenario"),
                        pl.lit(variant.name).alias("cap_name"),
                    )
                )

    capped_targets = pl.concat(capped_frames, how="diagonal_relaxed") if capped_frames else pl.DataFrame()
    orders_all = pl.concat(orders_frames, how="diagonal_relaxed") if orders_frames else pl.DataFrame()
    daily_all = pl.concat(daily_frames, how="diagonal_relaxed") if daily_frames else pl.DataFrame()
    position_daily = pl.concat(position_frames, how="diagonal_relaxed") if position_frames else pl.DataFrame()
    drawdowns = pl.concat(drawdown_frames, how="diagonal_relaxed") if drawdown_frames else pl.DataFrame()
    summary = add_base_deltas(pl.DataFrame(summary_rows)).sort(["base_scenario", "cap_name"])
    yearly = build_yearly(daily_all)
    cap_effect = build_cap_effect(capped_targets)
    actual_industry_daily = build_actual_industry_exposure(position_daily)
    actual_industry_summary = summarize_actual_industry_exposure(actual_industry_daily)
    quality = build_quality(summary, original_daily)

    summary.write_csv(paths["summary"])
    yearly.write_csv(paths["yearly"])
    drawdowns.write_csv(paths["drawdowns"])
    cap_effect.write_csv(paths["cap_effect"])
    position_daily.write_csv(paths["position_daily"])
    actual_industry_daily.write_csv(paths["actual_industry_daily"])
    actual_industry_summary.write_csv(paths["actual_industry_summary"])
    quality.write_csv(paths["quality"])
    capped_targets.write_csv(paths["capped_targets"])
    orders_all.write_csv(paths["orders"])
    daily_all.write_csv(paths["daily"])
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_dir": str(SOURCE_DIR),
            "source_prefix": SOURCE_PREFIX,
            "account_size_cny": ACCOUNT_SIZE_CNY,
            "focus_scenarios": FOCUS_SCENARIOS,
            "industry_cap_variants": [(item.name, item.cap, item.description) for item in INDUSTRY_CAP_VARIANTS],
            "research_sources": RESEARCH_SOURCES,
            "outputs": {key: str(path) for key, path in paths.items()},
        },
    )
    report_path = write_report(summary, yearly, drawdowns, cap_effect, actual_industry_summary, quality, paths)
    print(f"report={report_path}")
    print(summary.select(["base_scenario", "cap_name", "total_return_min_fee", "max_drawdown_min_fee", "sharpe_min_fee"]))
    print(quality)


if __name__ == "__main__":
    main()
