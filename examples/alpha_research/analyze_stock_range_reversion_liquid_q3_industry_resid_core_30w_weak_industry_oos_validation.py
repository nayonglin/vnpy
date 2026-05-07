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
from analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_sample_attribution import (
    FOCUS_SCENARIOS,
    read_csv_with_symbol,
)
from analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_source_filter_probe import (
    PREFIX as FILTER_PROBE_PREFIX,
)
from analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_source_filter_probe import (
    OUTPUT_DIR as FILTER_PROBE_OUTPUT_DIR,
)
from analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_source_filter_probe import (
    SOURCE_DIR,
    SOURCE_PREFIX,
    STAGE323_WEAK_INDUSTRIES,
    build_target_contribution_frame,
)
from analyze_stock_range_reversion_liquid_q3_30w_high_return_shape_grid import (
    HIGH_RETURN_TARGET,
    MAX_DRAWDOWN_LIMIT,
    summarize_daily_extra,
    to_float,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_weak_industry_oos_validation_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_weak_industry_oos_validation_v1"

FIXED_FILTER_NAME: str = "drop_stage323_weak_industries"
BASE_FILTER_NAME: str = "base_rerun"
START_YEARS: tuple[int, ...] = tuple(range(2019, 2027))
OOS_YEARS: tuple[int, ...] = tuple(range(2020, 2027))
ROLLING_WINDOWS: tuple[int, ...] = (126, 252, 504)
WALK_FORWARD_WEAK_INDUSTRY_COUNT: int = 2
MIN_TRAIN_INDUSTRY_ROWS: int = 100
PRIMARY_LOW_DD_SCENARIO: str = "industry_resid_core_h10_top8_gross70_ind2"
CANDIDATE_BASE_SCENARIO: str = "industry_resid_core_h10_top5_gross70_ind1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Short-term residual reversal",
        "https://www.sciencedirect.com/science/article/pii/S1386418112000468",
    ),
    (
        "Teddy Koker cross-sectional mean reversion backtest",
        "https://teddykoker.com/2019/04/backtesting-a-cross-sectional-mean-reversion-strategy-in-python/",
    ),
    (
        "GitHub walk-forward validation topic",
        "https://github.com/topics/walk-forward-validation",
    ),
    (
        "Walk-forward validation in trading",
        "https://breakorb.com/blog/walk-forward-validation-trading.html",
    ),
    (
        "Walk-forward optimization definition",
        "https://tradewink.com/glossary/walk-forward-optimization",
    ),
)


@dataclass(frozen=True)
class SegmentStats:
    days: int
    start_date: str
    end_date: str
    final_equity: float
    period_return: float
    annualized_return: float
    max_drawdown: float
    sharpe: float
    avg_actual_gross_weight: float
    active_day_ratio: float
    turnover_cost_sum: float
    filled_order_count_sum: int


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


def summarize_daily_frame(frame: pl.DataFrame) -> SegmentStats:
    ordered = frame.sort("date")
    if ordered.is_empty():
        return SegmentStats(
            days=0,
            start_date="",
            end_date="",
            final_equity=1.0,
            period_return=0.0,
            annualized_return=0.0,
            max_drawdown=0.0,
            sharpe=0.0,
            avg_actual_gross_weight=0.0,
            active_day_ratio=0.0,
            turnover_cost_sum=0.0,
            filled_order_count_sum=0,
        )

    returns = [float(value or 0.0) for value in ordered["strategy_daily_ret_min_fee"].to_list()]
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for daily_ret in returns:
        equity *= 1.0 + daily_ret
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1.0)
    annualized_return = equity ** (TRADING_DAYS / len(returns)) - 1.0 if equity > 0 and returns else -1.0
    return SegmentStats(
        days=len(returns),
        start_date=str(ordered["date"].min()),
        end_date=str(ordered["date"].max()),
        final_equity=equity,
        period_return=equity - 1.0,
        annualized_return=annualized_return,
        max_drawdown=max_drawdown,
        sharpe=annualized_sharpe(returns),
        avg_actual_gross_weight=to_float(ordered["actual_gross_weight"].mean()),
        active_day_ratio=to_float((ordered["actual_gross_weight"] > 0).mean()),
        turnover_cost_sum=to_float(ordered["turnover_cost_ret_min_fee"].sum()),
        filled_order_count_sum=int(ordered["filled_order_count"].sum() or 0),
    )


def stats_to_dict(stats: SegmentStats) -> dict[str, Any]:
    return {
        "days": stats.days,
        "start_date": stats.start_date,
        "end_date": stats.end_date,
        "final_equity": stats.final_equity,
        "period_return": stats.period_return,
        "annualized_return": stats.annualized_return,
        "max_drawdown": stats.max_drawdown,
        "sharpe": stats.sharpe,
        "avg_actual_gross_weight": stats.avg_actual_gross_weight,
        "active_day_ratio": stats.active_day_ratio,
        "turnover_cost_sum": stats.turnover_cost_sum,
        "filled_order_count_sum": stats.filled_order_count_sum,
    }


def build_fixed_daily() -> pl.DataFrame:
    base_daily = (
        pl.read_csv(SOURCE_DIR / f"{SOURCE_PREFIX}_daily.csv", try_parse_dates=True)
        .filter(pl.col("scenario").is_in(FOCUS_SCENARIOS))
        .with_columns(
            pl.col("scenario").alias("base_scenario"),
            pl.lit(BASE_FILTER_NAME).alias("filter_probe_name"),
            pl.lit("fixed_base").alias("validation_rule"),
        )
    )
    filtered_daily = (
        pl.read_csv(FILTER_PROBE_OUTPUT_DIR / f"{FILTER_PROBE_PREFIX}_daily.csv", try_parse_dates=True)
        .filter(pl.col("filter_probe_name") == FIXED_FILTER_NAME)
        .with_columns(pl.lit("fixed_stage323_weak_industries").alias("validation_rule"))
    )
    return pl.concat([base_daily, filtered_daily], how="diagonal_relaxed").sort(["base_scenario", "date", "scenario"])


def build_calendar_year_summary(daily: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    work = daily.with_columns(pl.col("date").dt.year().alias("year"))
    for key, group in work.partition_by(["base_scenario", "filter_probe_name", "year"], as_dict=True).items():
        base_scenario, filter_name, year = key
        stats = summarize_daily_frame(group)
        rows.append(
            {
                "base_scenario": base_scenario,
                "filter_probe_name": filter_name,
                "year": int(year),
                **stats_to_dict(stats),
            }
        )
    return pl.DataFrame(rows, infer_schema_length=None).sort(["base_scenario", "year", "filter_probe_name"])


def build_start_year_summary(daily: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, group in daily.partition_by(["base_scenario", "filter_probe_name"], as_dict=True).items():
        base_scenario, filter_name = key
        for start_year in START_YEARS:
            frame = group.filter(pl.col("date") >= date(start_year, 1, 1))
            if frame.is_empty():
                continue
            stats = summarize_daily_frame(frame)
            rows.append(
                {
                    "base_scenario": base_scenario,
                    "filter_probe_name": filter_name,
                    "start_year": start_year,
                    "period": f"since_{start_year}",
                    **stats_to_dict(stats),
                }
            )
    return pl.DataFrame(rows, infer_schema_length=None).sort(["base_scenario", "start_year", "filter_probe_name"])


def build_delta(summary: pl.DataFrame, key_cols: list[str]) -> pl.DataFrame:
    baseline = summary.filter(pl.col("filter_probe_name") == BASE_FILTER_NAME).select(
        *key_cols,
        pl.col("period_return").alias("baseline_period_return"),
        pl.col("annualized_return").alias("baseline_annualized_return"),
        pl.col("max_drawdown").alias("baseline_max_drawdown"),
        pl.col("sharpe").alias("baseline_sharpe"),
        pl.col("avg_actual_gross_weight").alias("baseline_avg_actual_gross_weight"),
        pl.col("filled_order_count_sum").alias("baseline_filled_order_count_sum"),
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
            (pl.col("filled_order_count_sum") - pl.col("baseline_filled_order_count_sum")).alias(
                "filled_order_count_delta_vs_baseline"
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
            pl.col("period_return_delta_vs_baseline").max().alias("best_period_return_delta"),
            pl.col("max_drawdown_improvement_vs_baseline").mean().alias("avg_max_drawdown_improvement"),
            pl.col("max_drawdown_improvement_vs_baseline").median().alias("median_max_drawdown_improvement"),
            pl.col("max_drawdown_improvement_vs_baseline").min().alias("worst_max_drawdown_improvement"),
            pl.col("sharpe_delta_vs_baseline").mean().alias("avg_sharpe_delta"),
            pl.col("sharpe_delta_vs_baseline").median().alias("median_sharpe_delta"),
            pl.col("sharpe_delta_vs_baseline").min().alias("worst_sharpe_delta"),
            pl.col("avg_actual_gross_weight_delta_vs_baseline").mean().alias("avg_gross_weight_delta"),
            pl.col("filled_order_count_delta_vs_baseline").mean().alias("avg_filled_order_count_delta"),
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
                        "window_start": stats.start_date,
                        "window_end": stats.end_date,
                        **stats_to_dict(stats),
                    }
                )
    return pl.DataFrame(rows, infer_schema_length=None).sort(
        ["base_scenario", "window_days", "window_end", "filter_probe_name"]
    )


def select_walk_forward_weak_industries(
    contrib: pl.DataFrame,
    base_scenario: str,
    oos_year: int,
) -> tuple[list[str], pl.DataFrame]:
    train = contrib.filter((pl.col("scenario") == base_scenario) & (pl.col("target_date") < date(oos_year, 1, 1)))
    if train.is_empty():
        return [], pl.DataFrame()
    ranked = (
        train.group_by("industry")
        .agg(
            pl.len().alias("target_rows"),
            pl.col("target_date").n_unique().alias("target_days"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("raw_target_contribution").sum().alias("train_contribution_sum"),
            pl.col("open_to_next_open_ret_filled").mean().alias("avg_open_to_next_open_ret"),
            pl.col("target_weight").sum().alias("target_weight_sum"),
        )
        .filter(pl.col("target_rows") >= MIN_TRAIN_INDUSTRY_ROWS)
        .sort(["train_contribution_sum", "target_rows"], descending=[False, True])
    )
    selected = ranked.head(WALK_FORWARD_WEAK_INDUSTRY_COUNT)
    return [str(item) for item in selected["industry"].to_list()], selected


def replay_fold(
    target_weights: pl.DataFrame,
    benchmark_df: pl.DataFrame,
    exec_info: dict[tuple[date, str], Any],
    scenario_name: str,
    base_scenario: str,
    filter_name: str,
    oos_year: int,
    selected_industries: list[str],
) -> tuple[dict[str, Any], pl.DataFrame, pl.DataFrame]:
    year_targets = target_weights.filter(
        (pl.col("scenario") == base_scenario) & (pl.col("target_date") >= date(oos_year, 1, 1)) & (pl.col("target_date") <= date(oos_year, 12, 31))
    )
    if selected_industries:
        filtered_targets = year_targets.filter(~pl.col("industry").is_in(selected_industries))
    else:
        filtered_targets = year_targets
    original_dates = lot.build_tracking_dates(year_targets.drop("scenario"), benchmark_df)
    target_maps = lot.build_target_maps(filtered_targets.drop("scenario"))
    orders, daily, _curves = lot.replay_lot_account(target_maps, original_dates, exec_info)
    orders = orders.with_columns(
        pl.lit(scenario_name).alias("scenario"),
        pl.lit(base_scenario).alias("base_scenario"),
        pl.lit(filter_name).alias("filter_probe_name"),
        pl.lit(oos_year).alias("oos_year"),
    )
    daily = daily.with_columns(
        pl.lit(scenario_name).alias("scenario"),
        pl.lit(base_scenario).alias("base_scenario"),
        pl.lit(filter_name).alias("filter_probe_name"),
        pl.lit(oos_year).alias("oos_year"),
    )
    summary = lot.summarize_orders(orders, daily)
    summary = summarize_daily_extra(summary, daily)
    segment_stats = summarize_daily_frame(daily)
    summary.update(
        {
            "scenario": scenario_name,
            "base_scenario": base_scenario,
            "filter_probe_name": filter_name,
            "oos_year": oos_year,
            **stats_to_dict(segment_stats),
            "selected_industries": "|".join(selected_industries),
            "selected_industry_count": len(selected_industries),
            "target_row_count_before_filter": year_targets.height,
            "target_row_count_after_filter": filtered_targets.height,
            "filtered_target_row_ratio": 1.0 - (filtered_targets.height / year_targets.height if year_targets.height else 1.0),
            "avg_target_gross_before_filter": to_float(
                year_targets.group_by("target_date").agg(pl.col("target_weight").sum()).select("target_weight").mean()
            ),
            "avg_target_gross_after_filter": to_float(
                filtered_targets.group_by("target_date").agg(pl.col("target_weight").sum()).select("target_weight").mean()
            ),
        }
    )
    return normalize_row(summary), orders, daily


def build_walk_forward_validation(
    target_weights: pl.DataFrame,
    contrib: pl.DataFrame,
    benchmark_df: pl.DataFrame,
    exec_info: dict[tuple[date, str], Any],
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []
    order_frames: list[pl.DataFrame] = []
    daily_frames: list[pl.DataFrame] = []
    rank_frames: list[pl.DataFrame] = []

    for base_scenario in FOCUS_SCENARIOS:
        for oos_year in OOS_YEARS:
            selected_industries, selected_rank = select_walk_forward_weak_industries(contrib, base_scenario, oos_year)
            if not selected_rank.is_empty():
                rank_frames.append(
                    selected_rank.with_columns(
                        pl.lit(base_scenario).alias("base_scenario"),
                        pl.lit(oos_year).alias("oos_year"),
                    )
                )
            selected_rows.append(
                {
                    "base_scenario": base_scenario,
                    "oos_year": oos_year,
                    "selected_industries": "|".join(selected_industries),
                    "selected_industry_count": len(selected_industries),
                }
            )
            base_summary, base_orders, base_daily = replay_fold(
                target_weights,
                benchmark_df,
                exec_info,
                scenario_name=f"{base_scenario}_wf_base_{oos_year}",
                base_scenario=base_scenario,
                filter_name=BASE_FILTER_NAME,
                oos_year=oos_year,
                selected_industries=[],
            )
            filtered_summary, filtered_orders, filtered_daily = replay_fold(
                target_weights,
                benchmark_df,
                exec_info,
                scenario_name=f"{base_scenario}_wf_prior_weak_industry_drop_{oos_year}",
                base_scenario=base_scenario,
                filter_name="wf_prior_weak_industry_drop",
                oos_year=oos_year,
                selected_industries=selected_industries,
            )
            summary_rows.extend([base_summary, filtered_summary])
            order_frames.extend([base_orders, filtered_orders])
            daily_frames.extend([base_daily, filtered_daily])

    summary = pl.DataFrame(summary_rows, infer_schema_length=None).sort(
        ["base_scenario", "oos_year", "filter_probe_name"]
    )
    selected = pl.DataFrame(selected_rows, infer_schema_length=None).sort(["base_scenario", "oos_year"])
    orders = pl.concat(order_frames, how="diagonal_relaxed") if order_frames else pl.DataFrame()
    daily = pl.concat(daily_frames, how="diagonal_relaxed") if daily_frames else pl.DataFrame()
    ranks = pl.concat(rank_frames, how="diagonal_relaxed") if rank_frames else pl.DataFrame()
    return summary, build_delta(summary, ["base_scenario", "oos_year"]), selected, ranks, daily


def build_quality(
    fixed_year_scorecard: pl.DataFrame,
    rolling_scorecard: pl.DataFrame,
    wf_delta: pl.DataFrame,
    wf_scorecard: pl.DataFrame,
) -> pl.DataFrame:
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

    fixed_primary = fixed_year_scorecard.filter(
        (pl.col("base_scenario") == PRIMARY_LOW_DD_SCENARIO) & (pl.col("filter_probe_name") == FIXED_FILTER_NAME)
    )
    rolling_primary_252 = rolling_scorecard.filter(
        (pl.col("base_scenario") == PRIMARY_LOW_DD_SCENARIO)
        & (pl.col("filter_probe_name") == FIXED_FILTER_NAME)
        & (pl.col("window_days") == 252)
    )
    wf_primary = wf_scorecard.filter(
        (pl.col("base_scenario") == PRIMARY_LOW_DD_SCENARIO)
        & (pl.col("filter_probe_name") == "wf_prior_weak_industry_drop")
    )
    wf_stress = wf_delta.filter(pl.col("filter_probe_name") == "wf_prior_weak_industry_drop")
    fixed_ratio = to_float(fixed_primary["return_and_drawdown_beat_ratio"][0]) if fixed_primary.height else 0.0
    rolling_ratio = (
        to_float(rolling_primary_252["return_and_drawdown_beat_ratio"][0]) if rolling_primary_252.height else 0.0
    )
    wf_ratio = to_float(wf_primary["return_and_drawdown_beat_ratio"][0]) if wf_primary.height else 0.0
    wf_positive_folds = wf_stress.filter(
        (pl.col("period_return_delta_vs_baseline") > 0) & (pl.col("max_drawdown_improvement_vs_baseline") > 0)
    )

    add(
        "fixed_rule_year_scorecard_available",
        "pass" if fixed_year_scorecard.height > 0 else "fail",
        fixed_year_scorecard.height,
        ">0",
        "固定Stage323弱行业规则必须生成年度验证。",
    )
    add(
        "fixed_primary_year_return_and_dd_ratio",
        "pass" if fixed_ratio >= 0.50 else "warn",
        f"{fixed_ratio:.2%}",
        ">=50%",
        "固定弱行业剔除若只在全样本有效而年度多数无效，不能升级。",
    )
    add(
        "fixed_primary_252d_return_and_dd_ratio",
        "pass" if rolling_ratio >= 0.50 else "warn",
        f"{rolling_ratio:.2%}",
        ">=50%",
        "252日滚动窗口检查规则是否跨市场阶段稳定。",
    )
    add(
        "walk_forward_fold_count",
        "pass" if wf_stress.height >= len(FOCUS_SCENARIOS) * len(OOS_YEARS) else "fail",
        wf_stress.height,
        len(FOCUS_SCENARIOS) * len(OOS_YEARS),
        "walk-forward必须覆盖所有基准形状和OOS年份。",
    )
    add(
        "walk_forward_return_and_dd_positive_folds",
        "pass" if wf_positive_folds.height > 0 else "warn",
        f"{wf_positive_folds.height}/{wf_stress.height}",
        ">0",
        "若过去年份选弱行业到下一年完全无效，则弱行业机制不成立。",
    )
    add(
        "walk_forward_primary_return_and_dd_ratio",
        "pass" if wf_ratio >= 0.50 else "warn",
        f"{wf_ratio:.2%}",
        ">=50%",
        "主低回撤形状的严格走前验证是是否继续的关键。",
    )
    add(
        "candidate_high_return_and_within_20pct",
        "warn",
        "not promoted",
        f"return>={HIGH_RETURN_TARGET:.0%}, max_dd>={MAX_DRAWDOWN_LIMIT:.0%}",
        "本阶段是反证，不寻找新正式候选。",
    )
    add(
        "same_sample_fixed_rule_warning",
        "warn",
        "fixed industries from Stage323",
        "needs walk-forward",
        "固定剔除软件服务/建筑工程仍来自同样本，只能和walk-forward结果一起看。",
    )
    return pl.DataFrame(rows)


def score_row(frame: pl.DataFrame, base_scenario: str, filter_probe_name: str, extra_filter: pl.Expr | None = None) -> dict[str, Any] | None:
    work = frame.filter((pl.col("base_scenario") == base_scenario) & (pl.col("filter_probe_name") == filter_probe_name))
    if extra_filter is not None:
        work = work.filter(extra_filter)
    return work.row(0, named=True) if work.height else None


def write_report(
    fixed_year_delta: pl.DataFrame,
    fixed_year_scorecard: pl.DataFrame,
    fixed_start_scorecard: pl.DataFrame,
    rolling_scorecard: pl.DataFrame,
    wf_delta: pl.DataFrame,
    wf_scorecard: pl.DataFrame,
    wf_selected: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    primary_fixed_year = score_row(fixed_year_scorecard, PRIMARY_LOW_DD_SCENARIO, FIXED_FILTER_NAME)
    candidate_fixed_year = score_row(fixed_year_scorecard, CANDIDATE_BASE_SCENARIO, FIXED_FILTER_NAME)
    primary_rolling_252 = score_row(
        rolling_scorecard,
        PRIMARY_LOW_DD_SCENARIO,
        FIXED_FILTER_NAME,
        pl.col("window_days") == 252,
    )
    primary_wf = score_row(wf_scorecard, PRIMARY_LOW_DD_SCENARIO, "wf_prior_weak_industry_drop")
    wf_positive = wf_delta.filter(
        (pl.col("filter_probe_name") == "wf_prior_weak_industry_drop")
        & (pl.col("period_return_delta_vs_baseline") > 0)
        & (pl.col("max_drawdown_improvement_vs_baseline") > 0)
    )

    lines = [
        "# 股票震荡industry_resid_core 30万弱行业过滤OOS/滚动反证 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前模式：day。",
        "- 当前研究线：股票震荡30万industry_resid_core独立研究线，不接入第78。",
        "- 本阶段性质：第324阶段弱行业过滤的启动年份、滚动窗口、严格走前反证。",
        f"- 固定弱行业：`{'/'.join(STAGE323_WEAK_INDUSTRIES)}`。",
        f"- walk-forward：每个OOS年份只用过去数据选择贡献最弱的`{WALK_FORWARD_WEAK_INDUSTRY_COUNT}`个行业，下一年剔除，释放现金不重分配。",
        "- A/B判断：独立研究线反证，不触发第78 A/B。",
        "",
        "## 外部调研判断",
        "",
        "- 残差/行业内反转的关键不是普通超跌，而是尽量剥离市场和行业暴露后的短期错价。",
        "- walk-forward的核心是过去样本选规则，未来样本检验；如果失败，不能继续用OOS结果调同一个规则。",
        "- GitHub可参考的walk-forward项目多是框架或教学实现，不能直接复制为A股交易系统；本阶段只借用验证思想。",
        "",
        "参考资料：",
        *[f"- [{title}]({url})" for title, url in RESEARCH_SOURCES],
        "",
        "## 核心摘要",
        "",
        f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。",
    ]
    if primary_fixed_year:
        lines.append(
            f"- 固定弱行业规则在主低回撤形状`{PRIMARY_LOW_DD_SCENARIO}`年度验证：收益+回撤同向改善`{int(primary_fixed_year['return_and_drawdown_beat_count'])}/{int(primary_fixed_year['sample_count'])}`，"
            f"平均收益差`{pct(primary_fixed_year['avg_period_return_delta'])}`，平均回撤改善`{pct(primary_fixed_year['avg_max_drawdown_improvement'])}`。"
        )
    if candidate_fixed_year:
        lines.append(
            f"- 第320候选形状`{CANDIDATE_BASE_SCENARIO}`年度验证：收益+回撤同向改善`{int(candidate_fixed_year['return_and_drawdown_beat_count'])}/{int(candidate_fixed_year['sample_count'])}`，"
            f"平均收益差`{pct(candidate_fixed_year['avg_period_return_delta'])}`，平均回撤改善`{pct(candidate_fixed_year['avg_max_drawdown_improvement'])}`。"
        )
    if primary_rolling_252:
        lines.append(
            f"- 主低回撤形状252日滚动：收益跑赢率`{pct(primary_rolling_252['return_beat_ratio'])}`，回撤改善率`{pct(primary_rolling_252['drawdown_beat_ratio'])}`，"
            f"收益+回撤同向改善率`{pct(primary_rolling_252['return_and_drawdown_beat_ratio'])}`。"
        )
    if primary_wf:
        lines.append(
            f"- 严格走前主低回撤形状：收益+回撤同向改善`{int(primary_wf['return_and_drawdown_beat_count'])}/{int(primary_wf['sample_count'])}`，"
            f"平均收益差`{pct(primary_wf['avg_period_return_delta'])}`，平均回撤改善`{pct(primary_wf['avg_max_drawdown_improvement'])}`。"
        )
    lines.append(
        f"- 全部walk-forward折中收益和回撤同时改善：`{wf_positive.height}/{wf_delta.filter(pl.col('filter_probe_name') == 'wf_prior_weak_industry_drop').height}`。"
    )

    lines.extend(
        [
            "",
            "## 固定弱行业年度记分",
            "",
            markdown_table(
                fixed_year_scorecard,
                [
                    "base_scenario",
                    "filter_probe_name",
                    "sample_count",
                    "return_beat_count",
                    "drawdown_beat_count",
                    "sharpe_beat_count",
                    "return_and_drawdown_beat_count",
                    "return_beat_ratio",
                    "drawdown_beat_ratio",
                    "sharpe_beat_ratio",
                    "return_and_drawdown_beat_ratio",
                    "avg_period_return_delta",
                    "worst_period_return_delta",
                    "avg_max_drawdown_improvement",
                    "worst_max_drawdown_improvement",
                    "avg_sharpe_delta",
                    "worst_sharpe_delta",
                    "avg_gross_weight_delta",
                ],
                max_rows=80,
            ),
            "",
            "## 固定弱行业启动年份记分",
            "",
            markdown_table(
                fixed_start_scorecard,
                [
                    "base_scenario",
                    "filter_probe_name",
                    "sample_count",
                    "return_beat_count",
                    "drawdown_beat_count",
                    "sharpe_beat_count",
                    "return_and_drawdown_beat_count",
                    "return_beat_ratio",
                    "drawdown_beat_ratio",
                    "sharpe_beat_ratio",
                    "return_and_drawdown_beat_ratio",
                    "avg_period_return_delta",
                    "worst_period_return_delta",
                    "avg_max_drawdown_improvement",
                    "worst_max_drawdown_improvement",
                    "avg_sharpe_delta",
                    "worst_sharpe_delta",
                    "avg_gross_weight_delta",
                ],
                max_rows=80,
            ),
            "",
            "## 固定弱行业滚动窗口记分",
            "",
            markdown_table(
                rolling_scorecard,
                [
                    "base_scenario",
                    "filter_probe_name",
                    "window_days",
                    "sample_count",
                    "return_beat_count",
                    "drawdown_beat_count",
                    "sharpe_beat_count",
                    "return_and_drawdown_beat_count",
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
                    "median_sharpe_delta",
                    "worst_sharpe_delta",
                ],
                max_rows=120,
            ),
            "",
            "## walk-forward记分",
            "",
            markdown_table(
                wf_scorecard,
                [
                    "base_scenario",
                    "filter_probe_name",
                    "sample_count",
                    "return_beat_count",
                    "drawdown_beat_count",
                    "sharpe_beat_count",
                    "return_and_drawdown_beat_count",
                    "return_beat_ratio",
                    "drawdown_beat_ratio",
                    "sharpe_beat_ratio",
                    "return_and_drawdown_beat_ratio",
                    "avg_period_return_delta",
                    "worst_period_return_delta",
                    "avg_max_drawdown_improvement",
                    "worst_max_drawdown_improvement",
                    "avg_sharpe_delta",
                    "worst_sharpe_delta",
                    "avg_gross_weight_delta",
                ],
                max_rows=80,
            ),
            "",
            "## walk-forward年度明细",
            "",
            markdown_table(
                wf_delta.filter(pl.col("filter_probe_name") == "wf_prior_weak_industry_drop"),
                [
                    "base_scenario",
                    "oos_year",
                    "selected_industries",
                    "period_return",
                    "baseline_period_return",
                    "period_return_delta_vs_baseline",
                    "max_drawdown",
                    "baseline_max_drawdown",
                    "max_drawdown_improvement_vs_baseline",
                    "sharpe",
                    "baseline_sharpe",
                    "sharpe_delta_vs_baseline",
                    "avg_actual_gross_weight",
                    "avg_actual_gross_weight_delta_vs_baseline",
                    "filtered_target_row_ratio",
                ],
                max_rows=120,
            ),
            "",
            "## walk-forward选择行业",
            "",
            markdown_table(
                wf_selected,
                ["base_scenario", "oos_year", "selected_industries", "selected_industry_count"],
                max_rows=120,
            ),
            "",
            "## 质量检查",
            "",
            markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 结论",
            "",
            "- 固定弱行业规则若通过年度/滚动但walk-forward弱，则说明`软件服务/建筑工程`更可能是这段历史的行业特例，而不是可泛化的弱行业机制。",
            "- walk-forward若也有效，才说明“用过去收益来源排除弱行业”有机制价值，可以继续研究行业特异性过滤。",
            "- 本阶段不产生正式候选；下一步只根据反证结果决定是否拆弱行业失败原因。",
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：固定规则有中等偏高过拟合风险，walk-forward风险较低。",
            "- 原因：固定行业来自Stage323同样本归因；walk-forward只用过去样本选择下一年行业。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：不直接升级候选。",
            "- 原因：本阶段是反证，即便固定规则有效，也要看walk-forward是否支持机制泛化。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：Stage324中信号层过滤比risk-on更接近亏损来源，值得用OOS反证决定去留。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：看walk-forward结果；若弱，则停止把行业名单策略化，转向继续下跌特征；若强，则继续做行业失败原因拆解。",
            "",
            "## 输出文件",
            "",
        ]
    )
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    paths["report"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    return paths["report"]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "fixed_year_summary": OUTPUT_DIR / f"{PREFIX}_fixed_year_summary.csv",
        "fixed_year_delta": OUTPUT_DIR / f"{PREFIX}_fixed_year_delta.csv",
        "fixed_year_scorecard": OUTPUT_DIR / f"{PREFIX}_fixed_year_scorecard.csv",
        "fixed_start_summary": OUTPUT_DIR / f"{PREFIX}_fixed_start_summary.csv",
        "fixed_start_delta": OUTPUT_DIR / f"{PREFIX}_fixed_start_delta.csv",
        "fixed_start_scorecard": OUTPUT_DIR / f"{PREFIX}_fixed_start_scorecard.csv",
        "rolling_summary": OUTPUT_DIR / f"{PREFIX}_rolling_summary.csv",
        "rolling_delta": OUTPUT_DIR / f"{PREFIX}_rolling_delta.csv",
        "rolling_scorecard": OUTPUT_DIR / f"{PREFIX}_rolling_scorecard.csv",
        "walk_forward_summary": OUTPUT_DIR / f"{PREFIX}_walk_forward_summary.csv",
        "walk_forward_delta": OUTPUT_DIR / f"{PREFIX}_walk_forward_delta.csv",
        "walk_forward_scorecard": OUTPUT_DIR / f"{PREFIX}_walk_forward_scorecard.csv",
        "walk_forward_selected_industries": OUTPUT_DIR / f"{PREFIX}_walk_forward_selected_industries.csv",
        "walk_forward_industry_rank": OUTPUT_DIR / f"{PREFIX}_walk_forward_industry_rank.csv",
        "walk_forward_daily": OUTPUT_DIR / f"{PREFIX}_walk_forward_daily.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }

    fixed_daily = build_fixed_daily()
    fixed_year_summary = build_calendar_year_summary(fixed_daily)
    fixed_year_delta = build_delta(fixed_year_summary, ["base_scenario", "year"])
    fixed_year_scorecard = build_scorecard(fixed_year_delta, ["base_scenario", "filter_probe_name"])
    fixed_start_summary = build_start_year_summary(fixed_daily)
    fixed_start_delta = build_delta(fixed_start_summary, ["base_scenario", "start_year"])
    fixed_start_scorecard = build_scorecard(fixed_start_delta, ["base_scenario", "filter_probe_name"])
    rolling_summary = build_rolling_summary(fixed_daily)
    rolling_delta = build_delta(rolling_summary, ["base_scenario", "window_days", "window_start", "window_end"])
    rolling_scorecard = build_scorecard(rolling_delta, ["base_scenario", "filter_probe_name", "window_days"])

    target_weights = read_csv_with_symbol(SOURCE_DIR / f"{SOURCE_PREFIX}_target_weights.csv").filter(
        pl.col("scenario").is_in(FOCUS_SCENARIOS)
    )
    base_daily = pl.read_csv(SOURCE_DIR / f"{SOURCE_PREFIX}_daily.csv", try_parse_dates=True).filter(
        pl.col("scenario").is_in(FOCUS_SCENARIOS)
    )
    stock_df, benchmark_df = load_panels()
    exec_info = build_exec_info(stock_df)
    contrib = build_target_contribution_frame(target_weights, base_daily, stock_df)
    wf_summary, wf_delta, wf_selected, wf_rank, wf_daily = build_walk_forward_validation(
        target_weights, contrib, benchmark_df, exec_info
    )
    wf_scorecard = build_scorecard(wf_delta, ["base_scenario", "filter_probe_name"])
    quality = build_quality(fixed_year_scorecard, rolling_scorecard, wf_delta, wf_scorecard)

    fixed_year_summary.write_csv(paths["fixed_year_summary"])
    fixed_year_delta.write_csv(paths["fixed_year_delta"])
    fixed_year_scorecard.write_csv(paths["fixed_year_scorecard"])
    fixed_start_summary.write_csv(paths["fixed_start_summary"])
    fixed_start_delta.write_csv(paths["fixed_start_delta"])
    fixed_start_scorecard.write_csv(paths["fixed_start_scorecard"])
    rolling_summary.write_csv(paths["rolling_summary"])
    rolling_delta.write_csv(paths["rolling_delta"])
    rolling_scorecard.write_csv(paths["rolling_scorecard"])
    wf_summary.write_csv(paths["walk_forward_summary"])
    wf_delta.write_csv(paths["walk_forward_delta"])
    wf_scorecard.write_csv(paths["walk_forward_scorecard"])
    wf_selected.write_csv(paths["walk_forward_selected_industries"])
    wf_rank.write_csv(paths["walk_forward_industry_rank"])
    wf_daily.write_csv(paths["walk_forward_daily"])
    quality.write_csv(paths["quality"])
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_dir": str(SOURCE_DIR),
            "source_prefix": SOURCE_PREFIX,
            "filter_probe_dir": str(FILTER_PROBE_OUTPUT_DIR),
            "filter_probe_prefix": FILTER_PROBE_PREFIX,
            "focus_scenarios": FOCUS_SCENARIOS,
            "fixed_filter_name": FIXED_FILTER_NAME,
            "stage323_weak_industries": STAGE323_WEAK_INDUSTRIES,
            "start_years": START_YEARS,
            "oos_years": OOS_YEARS,
            "rolling_windows": ROLLING_WINDOWS,
            "walk_forward_weak_industry_count": WALK_FORWARD_WEAK_INDUSTRY_COUNT,
            "min_train_industry_rows": MIN_TRAIN_INDUSTRY_ROWS,
            "research_sources": RESEARCH_SOURCES,
            "outputs": {key: str(path) for key, path in paths.items()},
        },
    )
    report_path = write_report(
        fixed_year_delta,
        fixed_year_scorecard,
        fixed_start_scorecard,
        rolling_scorecard,
        wf_delta,
        wf_scorecard,
        wf_selected,
        quality,
        paths,
    )
    print(f"report={report_path}")
    print(quality)
    print(fixed_year_scorecard)
    print(rolling_scorecard.filter(pl.col("window_days") == 252))
    print(wf_scorecard)


if __name__ == "__main__":
    main()
