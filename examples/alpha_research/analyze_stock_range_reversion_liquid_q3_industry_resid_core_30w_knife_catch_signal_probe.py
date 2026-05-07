from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

import analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility as lot
from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_30w_high_return_shape_grid import (
    HIGH_RETURN_TARGET,
    MAX_DRAWDOWN_LIMIT,
    summarize_daily_extra,
    to_float,
)
from analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_sample_attribution import (
    FOCUS_SCENARIOS,
    build_stock_features,
    read_csv_with_symbol,
)
from analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_source_filter_probe import (
    SOURCE_DIR,
    SOURCE_PREFIX,
    build_target_contribution_frame,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_catch_signal_probe_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_catch_signal_probe_v1"

BASE_FILTER_NAME: str = "base_rerun"
PRIMARY_SCENARIO: str = "industry_resid_core_h10_top8_gross70_ind2"
CANDIDATE_BASE_SCENARIO: str = "industry_resid_core_h10_top5_gross70_ind1"
ROLLING_WINDOWS: tuple[int, ...] = (126, 252, 504)
PRE_REGISTERED_FLAG_COLUMNS: tuple[str, ...] = (
    "flag_gap_down",
    "flag_intraday_selloff",
    "flag_close_near_low",
    "flag_high_volume_selloff",
    "flag_short_crash",
    "flag_broken_mid_trend",
    "flag_limit_down_signal",
)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Short-term reversals, returns to liquidity provision and immediacy costs",
        "https://www.sciencedirect.com/science/article/pii/S0378426622000309",
    ),
    (
        "Quantpedia short-term reversal summary",
        "https://quantpedia.com/strategies/short-term-reversal-in-stocks/",
    ),
    (
        "Teddy Koker cross-sectional mean reversion backtest",
        "https://teddykoker.com/2019/04/backtesting-a-cross-sectional-mean-reversion-strategy-in-python/",
    ),
    (
        "Mean-reversion failure discussion: avoid falling knives",
        "https://setupalpha.com/blogs/articles/mean-reversion-strategy-failures-complete-fix-guide",
    ),
    (
        "GitHub mean-reversion-trading topic",
        "https://github.com/topics/mean-reversion-trading",
    ),
)


@dataclass(frozen=True)
class KnifeProbe:
    name: str
    description: str
    condition_name: str


PROBES: tuple[KnifeProbe, ...] = (
    KnifeProbe(
        name="drop_gap_and_weak_close",
        description="剔除当日向下跳空且收盘靠近日内低位的信号，避免跳空后仍无承接。",
        condition_name="cond_gap_and_weak_close",
    ),
    KnifeProbe(
        name="drop_high_volume_selloff",
        description="剔除放量且盘中继续下跌的信号，避免放量出货式超跌。",
        condition_name="flag_high_volume_selloff",
    ),
    KnifeProbe(
        name="drop_short_crash",
        description="剔除5日或20日深跌信号，避免短期瀑布式下跌继续扩散。",
        condition_name="flag_short_crash",
    ),
    KnifeProbe(
        name="drop_broken_mid_trend",
        description="剔除远离52周高点且跌破60日均线较深的信号，避免结构性走坏。",
        condition_name="flag_broken_mid_trend",
    ),
    KnifeProbe(
        name="drop_limit_down_signal",
        description="剔除信号日跌停/一字跌停样本，避免交易约束和恐慌延续。",
        condition_name="flag_limit_down_signal",
    ),
    KnifeProbe(
        name="drop_knife_2plus",
        description="剔除至少2个接刀子风险旗标同时出现的信号。",
        condition_name="cond_knife_2plus",
    ),
    KnifeProbe(
        name="drop_knife_3plus",
        description="剔除至少3个接刀子风险旗标同时出现的信号。",
        condition_name="cond_knife_3plus",
    ),
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (date, datetime)):
            normalized[key] = value.isoformat()
        else:
            normalized[key] = value
    return normalized


def annualized_sharpe(returns: list[float]) -> float:
    clean = [value for value in returns if value == value]
    if len(clean) < 2:
        return 0.0
    mean = sum(clean) / len(clean)
    variance = sum((value - mean) ** 2 for value in clean) / (len(clean) - 1)
    if variance <= 0:
        return 0.0
    return mean / sqrt(variance) * sqrt(TRADING_DAYS)


def summarize_daily_frame(frame: pl.DataFrame) -> dict[str, Any]:
    ordered = frame.sort("date")
    if ordered.is_empty():
        return {
            "days": 0,
            "start_date": "",
            "end_date": "",
            "final_equity": 1.0,
            "period_return": 0.0,
            "annualized_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe": 0.0,
            "avg_actual_gross_weight": 0.0,
            "active_day_ratio": 0.0,
        }
    returns = [float(value or 0.0) for value in ordered["strategy_daily_ret_min_fee"].to_list()]
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for daily_ret in returns:
        equity *= 1.0 + daily_ret
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1.0)
    annualized_return = equity ** (TRADING_DAYS / len(returns)) - 1.0 if equity > 0 and returns else -1.0
    return {
        "days": len(returns),
        "start_date": str(ordered["date"].min()),
        "end_date": str(ordered["date"].max()),
        "final_equity": equity,
        "period_return": equity - 1.0,
        "annualized_return": annualized_return,
        "max_drawdown": max_drawdown,
        "sharpe": annualized_sharpe(returns),
        "avg_actual_gross_weight": to_float(ordered["actual_gross_weight"].mean()),
        "active_day_ratio": to_float((ordered["actual_gross_weight"] > 0).mean()),
    }


def add_knife_flags(frame: pl.DataFrame, stock_df: pl.DataFrame) -> pl.DataFrame:
    stock_features = (
        build_stock_features(stock_df)
        .sort(["symbol", "date"])
        .with_columns(
            pl.col("date").alias("feature_date"),
            pl.col("date").shift(-1).over("symbol").alias("target_date"),
        )
        .drop("date")
        .drop_nulls("target_date")
    )
    joined = frame.join(stock_features, on=["target_date", "symbol"], how="left")
    flag_exprs = [
        (pl.col("stock_open_gap") <= -0.03).fill_null(False).alias("flag_gap_down"),
        (pl.col("stock_intraday_ret") <= -0.03).fill_null(False).alias("flag_intraday_selloff"),
        (pl.col("stock_ibs") <= 0.15).fill_null(False).alias("flag_close_near_low"),
        (
            (pl.col("stock_volume_ratio_20") >= 1.80)
            & ((pl.col("stock_intraday_ret") <= -0.015) | (pl.col("stock_ret_1") <= -0.03))
        )
        .fill_null(False)
        .alias("flag_high_volume_selloff"),
        ((pl.col("stock_ret_5") <= -0.10) | (pl.col("stock_ret_20") <= -0.20))
        .fill_null(False)
        .alias("flag_short_crash"),
        ((pl.col("stock_dist_ma60") <= -0.10) & (pl.col("stock_close_to_high_252") <= 0.75))
        .fill_null(False)
        .alias("flag_broken_mid_trend"),
        (pl.col("is_limit_down_close").fill_null(False) | pl.col("is_oneword_limit_down").fill_null(False)).alias(
            "flag_limit_down_signal"
        ),
    ]
    flagged = joined.with_columns(flag_exprs)
    flag_sum = sum(pl.col(col).cast(pl.Int8) for col in PRE_REGISTERED_FLAG_COLUMNS)
    counted = flagged.with_columns(flag_sum.alias("knife_flag_count"))
    return counted.with_columns(
        (pl.col("flag_gap_down") & pl.col("flag_close_near_low")).alias("cond_gap_and_weak_close"),
        (pl.col("knife_flag_count") >= 2).alias("cond_knife_2plus"),
        (pl.col("knife_flag_count") >= 3).alias("cond_knife_3plus"),
    )


def condition_expr(condition_name: str) -> pl.Expr:
    return pl.col(condition_name).fill_null(False)


def build_signal_tail_attribution(enriched_contrib: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    ranked = (
        enriched_contrib.sort(["scenario", "open_to_next_open_ret_filled"])
        .with_columns(
            (pl.col("open_to_next_open_ret_filled").rank("ordinal").over("scenario") / pl.len().over("scenario")).alias(
                "signal_return_rank_pct"
            )
        )
        .with_columns(
            pl.when(pl.col("signal_return_rank_pct") <= 0.10)
            .then(pl.lit("bottom10_signal_next_open"))
            .when(pl.col("signal_return_rank_pct") >= 0.90)
            .then(pl.lit("top10_signal_next_open"))
            .otherwise(pl.lit("middle80_signal_next_open"))
            .alias("signal_tail_bucket")
        )
    )
    flag_rows: list[pl.DataFrame] = []
    for flag in [*PRE_REGISTERED_FLAG_COLUMNS, "cond_gap_and_weak_close", "cond_knife_2plus", "cond_knife_3plus"]:
        if flag not in ranked.columns:
            continue
        flag_rows.append(
            ranked.group_by(["scenario", "signal_tail_bucket", flag])
            .agg(
                pl.len().alias("target_rows"),
                pl.col("target_date").n_unique().alias("target_days"),
                pl.col("symbol").n_unique().alias("symbols"),
                pl.col("target_weight").sum().alias("target_weight_sum"),
                pl.col("raw_target_contribution").sum().alias("raw_target_contribution_sum"),
                pl.col("open_to_next_open_ret_filled").mean().alias("avg_open_to_next_open_ret"),
                (pl.col("open_to_next_open_ret_filled") > 0).mean().alias("positive_row_ratio"),
                pl.col("knife_flag_count").mean().alias("avg_knife_flag_count"),
            )
            .rename({flag: "flag_value"})
            .with_columns(pl.lit(flag).alias("feature"))
        )
    flag_attr = (
        pl.concat(flag_rows, how="diagonal_relaxed").sort(["scenario", "signal_tail_bucket", "feature", "flag_value"])
        if flag_rows
        else pl.DataFrame()
    )
    bucket_summary = (
        ranked.group_by(["scenario", "signal_tail_bucket"])
        .agg(
            pl.len().alias("target_rows"),
            pl.col("target_date").n_unique().alias("target_days"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("target_weight").sum().alias("target_weight_sum"),
            pl.col("raw_target_contribution").sum().alias("raw_target_contribution_sum"),
            pl.col("open_to_next_open_ret_filled").mean().alias("avg_open_to_next_open_ret"),
            (pl.col("open_to_next_open_ret_filled") > 0).mean().alias("positive_row_ratio"),
            pl.col("knife_flag_count").mean().alias("avg_knife_flag_count"),
            *[pl.col(flag).mean().alias(f"{flag}_rate") for flag in PRE_REGISTERED_FLAG_COLUMNS],
        )
        .sort(["scenario", "signal_tail_bucket"])
    )
    return bucket_summary, flag_attr


def apply_probe(enriched_targets: pl.DataFrame, probe: KnifeProbe) -> tuple[pl.DataFrame, pl.DataFrame]:
    drop_cond = condition_expr(probe.condition_name)
    scaled = (
        enriched_targets.with_columns(
            pl.col("target_weight").alias("base_target_weight"),
            pl.when(drop_cond).then(pl.lit(0.0)).otherwise(pl.lit(1.0)).alias("filter_weight_multiplier"),
        )
        .with_columns((pl.col("target_weight") * pl.col("filter_weight_multiplier")).alias("target_weight"))
        .filter(pl.col("target_weight") > 0)
        .sort(["target_date", "symbol"])
    )
    scale_daily = (
        enriched_targets.with_columns(pl.when(drop_cond).then(pl.lit(0.0)).otherwise(pl.lit(1.0)).alias("multiplier"))
        .group_by(["scenario", "target_date"])
        .agg(
            pl.col("target_weight").sum().alias("base_target_gross_weight"),
            (pl.col("target_weight") * pl.col("multiplier")).sum().alias("filtered_target_gross_weight"),
            (pl.col("multiplier") < 0.999999).sum().alias("filtered_row_count"),
            pl.len().alias("base_row_count"),
            pl.col("knife_flag_count").mean().alias("avg_knife_flag_count"),
        )
        .with_columns(
            pl.lit(probe.name).alias("filter_probe_name"),
            (pl.col("filtered_row_count") / pl.col("base_row_count")).alias("filtered_row_ratio"),
        )
    )
    return scaled, scale_daily


def add_base_deltas(summary: pl.DataFrame) -> pl.DataFrame:
    base = (
        summary.filter(pl.col("filter_probe_name") == BASE_FILTER_NAME)
        .select(
            "base_scenario",
            pl.col("final_equity_min_fee").alias("base_final_equity_min_fee"),
            pl.col("total_return_min_fee").alias("base_total_return_min_fee"),
            pl.col("max_drawdown_min_fee").alias("base_max_drawdown_min_fee"),
            pl.col("sharpe_min_fee").alias("base_sharpe_min_fee"),
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
                "base_avg_actual_gross_weight",
            ]
        )
    )


def build_segment_summary(daily: pl.DataFrame, group_cols: list[str], segment_col: str | None = None) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, group in daily.partition_by(group_cols, as_dict=True).items():
        key_tuple = key if isinstance(key, tuple) else (key,)
        row = {col: value for col, value in zip(group_cols, key_tuple)}
        row.update(summarize_daily_frame(group))
        if segment_col and segment_col in row:
            row[segment_col] = int(row[segment_col])
        rows.append(row)
    return pl.DataFrame(rows, infer_schema_length=None).sort(group_cols) if rows else pl.DataFrame()


def build_delta(summary: pl.DataFrame, key_cols: list[str]) -> pl.DataFrame:
    baseline = summary.filter(pl.col("filter_probe_name") == BASE_FILTER_NAME).select(
        *key_cols,
        pl.col("period_return").alias("baseline_period_return"),
        pl.col("annualized_return").alias("baseline_annualized_return"),
        pl.col("max_drawdown").alias("baseline_max_drawdown"),
        pl.col("sharpe").alias("baseline_sharpe"),
        pl.col("avg_actual_gross_weight").alias("baseline_avg_actual_gross_weight"),
    )
    return (
        summary.join(baseline, on=key_cols, how="left")
        .with_columns(
            (pl.col("period_return") - pl.col("baseline_period_return")).alias("period_return_delta_vs_baseline"),
            (pl.col("annualized_return") - pl.col("baseline_annualized_return")).alias(
                "annualized_return_delta_vs_baseline"
            ),
            (pl.col("max_drawdown") - pl.col("baseline_max_drawdown")).alias("max_drawdown_improvement_vs_baseline"),
            (pl.col("sharpe") - pl.col("baseline_sharpe")).alias("sharpe_delta_vs_baseline"),
            (pl.col("avg_actual_gross_weight") - pl.col("baseline_avg_actual_gross_weight")).alias(
                "avg_actual_gross_weight_delta_vs_baseline"
            ),
            (pl.col("period_return") > pl.col("baseline_period_return")).alias("beats_baseline_return"),
            (pl.col("max_drawdown") > pl.col("baseline_max_drawdown")).alias("beats_baseline_drawdown"),
            (pl.col("sharpe") > pl.col("baseline_sharpe")).alias("beats_baseline_sharpe"),
            (
                (pl.col("period_return") > pl.col("baseline_period_return"))
                & (pl.col("max_drawdown") > pl.col("baseline_max_drawdown"))
            ).alias("beats_baseline_return_and_drawdown"),
        )
        .sort([*key_cols, "filter_probe_name"])
    )


def build_scorecard(delta: pl.DataFrame, group_cols: list[str]) -> pl.DataFrame:
    return (
        delta.filter(pl.col("filter_probe_name") != BASE_FILTER_NAME)
        .group_by(group_cols)
        .agg(
            pl.len().alias("sample_count"),
            pl.col("beats_baseline_return").sum().alias("return_beat_count"),
            pl.col("beats_baseline_drawdown").sum().alias("drawdown_beat_count"),
            pl.col("beats_baseline_sharpe").sum().alias("sharpe_beat_count"),
            pl.col("beats_baseline_return_and_drawdown").sum().alias("return_and_drawdown_beat_count"),
            pl.col("period_return_delta_vs_baseline").mean().alias("avg_period_return_delta"),
            pl.col("period_return_delta_vs_baseline").median().alias("median_period_return_delta"),
            pl.col("period_return_delta_vs_baseline").min().alias("worst_period_return_delta"),
            pl.col("max_drawdown_improvement_vs_baseline").mean().alias("avg_max_drawdown_improvement"),
            pl.col("max_drawdown_improvement_vs_baseline").median().alias("median_max_drawdown_improvement"),
            pl.col("max_drawdown_improvement_vs_baseline").min().alias("worst_max_drawdown_improvement"),
            pl.col("sharpe_delta_vs_baseline").mean().alias("avg_sharpe_delta"),
            pl.col("sharpe_delta_vs_baseline").median().alias("median_sharpe_delta"),
            pl.col("sharpe_delta_vs_baseline").min().alias("worst_sharpe_delta"),
            pl.col("avg_actual_gross_weight_delta_vs_baseline").mean().alias("avg_gross_weight_delta"),
        )
        .with_columns(
            (pl.col("return_beat_count") / pl.col("sample_count")).alias("return_beat_ratio"),
            (pl.col("drawdown_beat_count") / pl.col("sample_count")).alias("drawdown_beat_ratio"),
            (pl.col("sharpe_beat_count") / pl.col("sample_count")).alias("sharpe_beat_ratio"),
            (pl.col("return_and_drawdown_beat_count") / pl.col("sample_count")).alias(
                "return_and_drawdown_beat_ratio"
            ),
        )
        .sort(group_cols)
    )


def build_rolling_summary(daily: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, group in daily.partition_by(["base_scenario", "filter_probe_name"], as_dict=True).items():
        base_scenario, filter_name = key
        ordered = group.sort("date")
        for window in ROLLING_WINDOWS:
            if ordered.height < window:
                continue
            for end_idx in range(window - 1, ordered.height):
                frame = ordered.slice(end_idx - window + 1, window)
                stats = summarize_daily_frame(frame)
                rows.append(
                    {
                        "base_scenario": base_scenario,
                        "filter_probe_name": filter_name,
                        "window_days": window,
                        "window_start": stats["start_date"],
                        "window_end": stats["end_date"],
                        **stats,
                    }
                )
    return pl.DataFrame(rows, infer_schema_length=None).sort(
        ["base_scenario", "filter_probe_name", "window_days", "window_end"]
    )


def build_quality(summary: pl.DataFrame, year_scorecard: pl.DataFrame, rolling_scorecard: pl.DataFrame) -> pl.DataFrame:
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

    stress = summary.filter(pl.col("filter_probe_name") != BASE_FILTER_NAME)
    improve_both = stress.filter(
        (pl.col("delta_total_return_min_fee") > 0) & (pl.col("delta_max_drawdown_min_fee") > 0)
    )
    high_target = stress.filter(
        (pl.col("total_return_min_fee") >= HIGH_RETURN_TARGET) & (pl.col("max_drawdown_min_fee") >= MAX_DRAWDOWN_LIMIT)
    )
    primary_rolling = rolling_scorecard.filter(
        (pl.col("base_scenario") == PRIMARY_SCENARIO) & (pl.col("window_days") == 252)
    )
    primary_rolling_good = primary_rolling.filter(pl.col("return_and_drawdown_beat_ratio") >= 0.50)
    year_good = year_scorecard.filter(pl.col("return_and_drawdown_beat_ratio") >= 0.50)
    add(
        "probe_count",
        "pass" if stress["filter_probe_name"].n_unique() == len(PROBES) else "fail",
        stress["filter_probe_name"].n_unique(),
        len(PROBES),
        "只运行预注册接刀子风险探针。",
    )
    add(
        "any_full_sample_improves_both",
        "pass" if improve_both.height > 0 else "warn",
        f"{improve_both.height}/{stress.height}",
        ">0",
        "若全样本都没有同向改善，本方向应降级。",
    )
    add(
        "candidate_high_return_and_within_20pct",
        "pass" if high_target.height > 0 else "warn",
        f"{high_target.height}/{stress.height}",
        ">0",
        "30万目标是高收益且回撤20%以内；本阶段只作探针。",
    )
    add(
        "yearly_any_probe_majority",
        "pass" if year_good.height > 0 else "warn",
        f"{year_good.height}/{year_scorecard.height}",
        ">0",
        "年度多数同向改善比单一全样本更重要。",
    )
    add(
        "primary_252d_any_probe_majority",
        "pass" if primary_rolling_good.height > 0 else "warn",
        f"{primary_rolling_good.height}/{primary_rolling.height}",
        ">0",
        "主场景252日滚动同向改善率需要过半。",
    )
    add(
        "no_reallocation_of_freed_cash",
        "pass",
        "cash freed",
        "cash freed",
        "过滤释放现金不重分配，避免把过滤效果伪装成加仓。",
    )
    add(
        "prior_day_feature_alignment",
        "pass",
        "feature_date shifted to next target_date",
        "no same-day close at execution open",
        "接刀子旗标只使用上一交易日收盘后已知信息。",
    )
    add(
        "exploratory_multiple_probe_warning",
        "warn",
        "pre-registered probes",
        "needs follow-up OOS",
        "虽然阈值来自第一性原理，但多探针仍不能直接升级候选。",
    )
    return pl.DataFrame(rows)


def write_report(
    signal_tail_summary: pl.DataFrame,
    flag_attribution: pl.DataFrame,
    summary: pl.DataFrame,
    year_scorecard: pl.DataFrame,
    rolling_scorecard: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    stress = summary.filter(pl.col("filter_probe_name") != BASE_FILTER_NAME)
    improve_both = stress.filter(
        (pl.col("delta_total_return_min_fee") > 0) & (pl.col("delta_max_drawdown_min_fee") > 0)
    )
    best_return = stress.sort(["total_return_min_fee", "max_drawdown_min_fee"], descending=[True, True]).row(
        0, named=True
    )
    best_dd = stress.sort(["max_drawdown_min_fee", "total_return_min_fee"], descending=[True, True]).row(0, named=True)
    primary_rolling_252 = rolling_scorecard.filter(
        (pl.col("base_scenario") == PRIMARY_SCENARIO) & (pl.col("window_days") == 252)
    ).sort("return_and_drawdown_beat_ratio", descending=True)
    lines = [
        "# 股票震荡industry_resid_core 30万接刀子信号探针 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前模式：day。",
        "- 当前研究线：股票震荡30万industry_resid_core独立研究线，不接入第78。",
        "- 本阶段性质：继续下跌/接刀子风险旗标归因与少量预注册过滤探针。",
        "- 特征时间对齐：所有个股技术旗标使用上一交易日收盘后已知信息，映射到下一交易日开盘目标，避免前视。",
        f"- 账户规模：`{lot.ACCOUNT_SIZE_CNY:,.0f}`元；过滤释放现金不重分配。",
        "- A/B判断：独立研究线探针，不触发第78 A/B。",
        "",
        "## 外部调研判断",
        "",
        "- 短期反转可以理解为流动性供给补偿，但不是所有下跌都应该买；趋势性继续下跌是均值回归的核心尾部风险。",
        "- 公开资料反复强调成交量、缺口、是否仍在下跌、是否有承接；本阶段只把这些翻译成少量事前可识别旗标。",
        "- GitHub和博客示例可参考流程，但不能替代A股整手、涨跌停、交易成本和本地股票池约束。",
        "",
        "参考资料：",
        *[f"- [{title}]({url})" for title, url in RESEARCH_SOURCES],
        "",
        "## 核心摘要",
        "",
        f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。",
        f"- 全样本收益和回撤同时改善：`{improve_both.height}/{stress.height}`。",
        f"- 收益最高探针：`{best_return['scenario']}`，总收益`{pct(best_return['total_return_min_fee'])}`，最大回撤`{pct(best_return['max_drawdown_min_fee'])}`，Sharpe `{best_return['sharpe_min_fee']:.3f}`。",
        f"- 回撤最浅探针：`{best_dd['scenario']}`，总收益`{pct(best_dd['total_return_min_fee'])}`，最大回撤`{pct(best_dd['max_drawdown_min_fee'])}`，Sharpe `{best_dd['sharpe_min_fee']:.3f}`。",
        "",
        "## 信号尾部旗标画像",
        "",
        markdown_table(
            signal_tail_summary,
            [
                "scenario",
                "signal_tail_bucket",
                "target_rows",
                "target_days",
                "symbols",
                "raw_target_contribution_sum",
                "avg_open_to_next_open_ret",
                "positive_row_ratio",
                "avg_knife_flag_count",
                "flag_gap_down_rate",
                "flag_intraday_selloff_rate",
                "flag_close_near_low_rate",
                "flag_high_volume_selloff_rate",
                "flag_short_crash_rate",
                "flag_broken_mid_trend_rate",
                "flag_limit_down_signal_rate",
            ],
            max_rows=80,
        ),
        "",
        "## 旗标贡献归因",
        "",
        markdown_table(
            flag_attribution.filter(pl.col("flag_value") == True),
            [
                "scenario",
                "signal_tail_bucket",
                "feature",
                "target_rows",
                "target_days",
                "symbols",
                "target_weight_sum",
                "raw_target_contribution_sum",
                "avg_open_to_next_open_ret",
                "positive_row_ratio",
                "avg_knife_flag_count",
            ],
            max_rows=120,
        ),
        "",
        "## 过滤探针全样本汇总",
        "",
        markdown_table(
            summary,
            [
                "base_scenario",
                "filter_probe_name",
                "total_return_min_fee",
                "max_drawdown_min_fee",
                "delta_total_return_min_fee",
                "delta_max_drawdown_min_fee",
                "sharpe_min_fee",
                "delta_sharpe_min_fee",
                "avg_actual_gross_weight",
                "avg_filtered_target_gross_weight",
                "avg_filtered_row_ratio",
            ],
            max_rows=160,
        ),
        "",
        "## 年度记分",
        "",
        markdown_table(
            year_scorecard,
            [
                "base_scenario",
                "filter_probe_name",
                "sample_count",
                "return_beat_ratio",
                "drawdown_beat_ratio",
                "sharpe_beat_ratio",
                "return_and_drawdown_beat_ratio",
                "avg_period_return_delta",
                "worst_period_return_delta",
                "avg_max_drawdown_improvement",
                "worst_max_drawdown_improvement",
                "avg_sharpe_delta",
            ],
            max_rows=160,
        ),
        "",
        "## 主场景252日滚动记分",
        "",
        markdown_table(
            primary_rolling_252,
            [
                "base_scenario",
                "filter_probe_name",
                "window_days",
                "sample_count",
                "return_beat_ratio",
                "drawdown_beat_ratio",
                "sharpe_beat_ratio",
                "return_and_drawdown_beat_ratio",
                "avg_period_return_delta",
                "median_period_return_delta",
                "worst_period_return_delta",
                "avg_max_drawdown_improvement",
                "median_max_drawdown_improvement",
                "worst_max_drawdown_improvement",
                "avg_sharpe_delta",
            ],
            max_rows=120,
        ),
        "",
        "## 质量检查",
        "",
        markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
        "",
        "## 结论",
        "",
        "- 若只有回撤改善但收益下降，说明旗标更像降仓风险控制，不是可替代alpha。",
        "- 若年度和252日滚动也能同向改善，下一步才值得把对应旗标拿去做更严格的walk-forward和成本压力。",
        "- 本阶段不升级正式候选，不修改paper线，不接入第78。",
        "",
        "## 运行前过拟合反思",
        "",
        "- 判断：中等。",
        "- 原因：旗标阈值来自第一性原理和外部调研，但一次测试多个探针仍有选择偏差。",
        "",
        "## 运行后过拟合反思",
        "",
        "- 判断：不直接升级候选。",
        "- 原因：必须看年度/滚动是否支持，且后续不能按最优探针继续细调阈值。",
        "",
        "## 运行前继续价值反思",
        "",
        "- 判断：是。",
        "- 原因：第325阶段说明行业名单不是根因，应该回到个股是否继续下跌的可识别状态。",
        "",
        "## 运行后继续价值反思",
        "",
        "- 判断：若无稳定同向改善，则本方向降级；若有，则进入更严格walk-forward。",
        "",
        "## 输出文件",
        "",
    ]
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    paths["report"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    return paths["report"]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "signal_tail_summary": OUTPUT_DIR / f"{PREFIX}_signal_tail_summary.csv",
        "flag_attribution": OUTPUT_DIR / f"{PREFIX}_flag_attribution.csv",
        "scale_daily": OUTPUT_DIR / f"{PREFIX}_scale_daily.csv",
        "daily": OUTPUT_DIR / f"{PREFIX}_daily.csv",
        "orders": OUTPUT_DIR / f"{PREFIX}_orders.csv",
        "year_summary": OUTPUT_DIR / f"{PREFIX}_year_summary.csv",
        "year_delta": OUTPUT_DIR / f"{PREFIX}_year_delta.csv",
        "year_scorecard": OUTPUT_DIR / f"{PREFIX}_year_scorecard.csv",
        "rolling_summary": OUTPUT_DIR / f"{PREFIX}_rolling_summary.csv",
        "rolling_delta": OUTPUT_DIR / f"{PREFIX}_rolling_delta.csv",
        "rolling_scorecard": OUTPUT_DIR / f"{PREFIX}_rolling_scorecard.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }

    target_weights = read_csv_with_symbol(SOURCE_DIR / f"{SOURCE_PREFIX}_target_weights.csv").filter(
        pl.col("scenario").is_in(FOCUS_SCENARIOS)
    )
    base_daily = pl.read_csv(SOURCE_DIR / f"{SOURCE_PREFIX}_daily.csv", try_parse_dates=True).filter(
        pl.col("scenario").is_in(FOCUS_SCENARIOS)
    )
    base_summary = pl.read_csv(SOURCE_DIR / f"{SOURCE_PREFIX}_summary.csv", try_parse_dates=True).filter(
        pl.col("scenario").is_in(FOCUS_SCENARIOS)
    )
    stock_df, benchmark_df = load_panels()
    exec_info = build_exec_info(stock_df)

    enriched_targets = add_knife_flags(target_weights, stock_df)
    contrib = build_target_contribution_frame(target_weights, base_daily, stock_df)
    enriched_contrib = add_knife_flags(contrib, stock_df)
    signal_tail_summary, flag_attribution = build_signal_tail_attribution(enriched_contrib)

    summary_rows: list[dict[str, Any]] = []
    daily_frames: list[pl.DataFrame] = []
    orders_frames: list[pl.DataFrame] = []
    scale_frames: list[pl.DataFrame] = []

    base_daily_for_segments = base_daily.with_columns(
        pl.col("scenario").alias("base_scenario"),
        pl.lit(BASE_FILTER_NAME).alias("filter_probe_name"),
    )
    daily_frames.append(base_daily_for_segments)
    for row in base_summary.iter_rows(named=True):
        base_scenario = str(row["scenario"])
        base_row = dict(row)
        base_row["base_scenario"] = base_scenario
        base_row["filter_probe_name"] = BASE_FILTER_NAME
        base_row["filter_probe_description"] = "不做接刀子信号过滤。"
        base_row["avg_filtered_target_gross_weight"] = base_row.get("shape_basket_gross_weight")
        base_row["avg_filtered_row_ratio"] = 0.0
        summary_rows.append(normalize_row(base_row))

    for base_scenario in FOCUS_SCENARIOS:
        scenario_targets = enriched_targets.filter(pl.col("scenario") == base_scenario)
        original_dates = lot.build_tracking_dates(scenario_targets.drop("scenario"), benchmark_df)
        for probe in PROBES:
            filtered_targets, scale_daily = apply_probe(scenario_targets, probe)
            target_maps = lot.build_target_maps(filtered_targets.drop("scenario"))
            orders, daily, _curves = lot.replay_lot_account(target_maps, original_dates, exec_info)
            scenario_name = f"{base_scenario}_{probe.name}"
            orders = orders.with_columns(
                pl.lit(scenario_name).alias("scenario"),
                pl.lit(base_scenario).alias("base_scenario"),
                pl.lit(probe.name).alias("filter_probe_name"),
            )
            daily = daily.with_columns(
                pl.lit(scenario_name).alias("scenario"),
                pl.lit(base_scenario).alias("base_scenario"),
                pl.lit(probe.name).alias("filter_probe_name"),
            )
            scale_daily = scale_daily.with_columns(
                pl.lit(base_scenario).alias("base_scenario"),
                pl.lit(probe.description).alias("filter_probe_description"),
            )
            summary = lot.summarize_orders(orders, daily)
            summary = summarize_daily_extra(summary, daily)
            summary.update(
                {
                    "scenario": scenario_name,
                    "base_scenario": base_scenario,
                    "filter_probe_name": probe.name,
                    "filter_probe_description": probe.description,
                    "avg_filtered_target_gross_weight": to_float(scale_daily["filtered_target_gross_weight"].mean()),
                    "avg_base_target_gross_weight": to_float(scale_daily["base_target_gross_weight"].mean()),
                    "avg_filtered_row_ratio": to_float(scale_daily["filtered_row_ratio"].mean()),
                    "max_filtered_target_gross_weight": to_float(scale_daily["filtered_target_gross_weight"].max()),
                    "avg_daily_knife_flag_count": to_float(scale_daily["avg_knife_flag_count"].mean()),
                }
            )
            summary_rows.append(normalize_row(summary))
            daily_frames.append(daily)
            orders_frames.append(orders)
            scale_frames.append(scale_daily)

    summary = add_base_deltas(pl.DataFrame(summary_rows, infer_schema_length=None)).sort(
        ["base_scenario", "filter_probe_name"]
    )
    daily_all = pl.concat(daily_frames, how="diagonal_relaxed")
    orders_all = pl.concat(orders_frames, how="diagonal_relaxed") if orders_frames else pl.DataFrame()
    scale_all = pl.concat(scale_frames, how="diagonal_relaxed") if scale_frames else pl.DataFrame()

    year_summary = build_segment_summary(
        daily_all.with_columns(pl.col("date").dt.year().alias("year")),
        ["base_scenario", "filter_probe_name", "year"],
        segment_col="year",
    )
    year_delta = build_delta(year_summary, ["base_scenario", "year"])
    year_scorecard = build_scorecard(year_delta, ["base_scenario", "filter_probe_name"])
    rolling_summary = build_rolling_summary(daily_all)
    rolling_delta = build_delta(rolling_summary, ["base_scenario", "window_days", "window_start", "window_end"])
    rolling_scorecard = build_scorecard(rolling_delta, ["base_scenario", "filter_probe_name", "window_days"])
    quality = build_quality(summary, year_scorecard, rolling_scorecard)

    summary.write_csv(paths["summary"])
    signal_tail_summary.write_csv(paths["signal_tail_summary"])
    flag_attribution.write_csv(paths["flag_attribution"])
    scale_all.write_csv(paths["scale_daily"])
    daily_all.write_csv(paths["daily"])
    orders_all.write_csv(paths["orders"])
    year_summary.write_csv(paths["year_summary"])
    year_delta.write_csv(paths["year_delta"])
    year_scorecard.write_csv(paths["year_scorecard"])
    rolling_summary.write_csv(paths["rolling_summary"])
    rolling_delta.write_csv(paths["rolling_delta"])
    rolling_scorecard.write_csv(paths["rolling_scorecard"])
    quality.write_csv(paths["quality"])
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_dir": str(SOURCE_DIR),
            "source_prefix": SOURCE_PREFIX,
            "focus_scenarios": FOCUS_SCENARIOS,
            "primary_scenario": PRIMARY_SCENARIO,
            "candidate_base_scenario": CANDIDATE_BASE_SCENARIO,
            "probes": [
                {"name": probe.name, "description": probe.description, "condition_name": probe.condition_name}
                for probe in PROBES
            ],
            "pre_registered_flag_columns": PRE_REGISTERED_FLAG_COLUMNS,
            "rolling_windows": ROLLING_WINDOWS,
            "research_sources": RESEARCH_SOURCES,
            "outputs": {key: str(path) for key, path in paths.items()},
        },
    )
    report_path = write_report(
        signal_tail_summary,
        flag_attribution,
        summary,
        year_scorecard,
        rolling_scorecard,
        quality,
        paths,
    )
    print(f"report={report_path}")
    print(quality)
    print(summary.select(["base_scenario", "filter_probe_name", "total_return_min_fee", "max_drawdown_min_fee", "delta_total_return_min_fee", "delta_max_drawdown_min_fee", "sharpe_min_fee", "avg_filtered_row_ratio"]))
    print(year_scorecard)
    print(rolling_scorecard.filter((pl.col("base_scenario") == PRIMARY_SCENARIO) & (pl.col("window_days") == 252)))


if __name__ == "__main__":
    main()
