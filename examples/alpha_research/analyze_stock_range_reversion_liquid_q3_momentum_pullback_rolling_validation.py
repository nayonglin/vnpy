from __future__ import annotations

import json
from datetime import date, datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from backtest_stock_range_reversion_industry_neutral_merged_portfolio import HORIZON, NATIVE_RESULTS_DIR, TRADING_DAYS, pct


SOURCE_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_momentum_pullback_attribution_2018_2026"
).expanduser().resolve()
SOURCE_PREFIX: str = "stock_range_reversion_liquid_q3_momentum_pullback_attribution_v1"
OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_momentum_pullback_rolling_validation_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_momentum_pullback_rolling_validation_v1"

BASELINE_SCENARIO: str = "baseline_liquid_q3_current"
PRIMARY_SCENARIO: str = "weak_market60_q1q2_diagnostic"
REALLOCATED_SCENARIO: str = "weak_market60_q1q2_reallocated"
NEGATIVE_CONTROL_SCENARIO: str = "strong_market60_q4q5_no_realloc"
AUDIT_SCENARIOS: tuple[str, ...] = (
    BASELINE_SCENARIO,
    PRIMARY_SCENARIO,
    REALLOCATED_SCENARIO,
    NEGATIVE_CONTROL_SCENARIO,
)
COST_BPS: float = 50.0
GAP_DAYS: int = 10
ROLLING_TRAIN_DAYS: int = 504
ROLLING_TEST_DAYS: int = 63
ROLLING_STEP_DAYS: int = 63
ROLLING_WINDOWS: tuple[int, ...] = (126, 252, 504)
START_YEARS: tuple[int, ...] = tuple(range(2018, 2027))
OOS_YEARS: tuple[int, ...] = tuple(range(2020, 2027))

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "scikit-learn TimeSeriesSplit gap",
        "https://sklearn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html",
    ),
    (
        "Bailey/Lopez de Prado PBO paper",
        "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253",
    ),
    (
        "GitHub walk-forward-validation topic",
        "https://github.com/topics/walk-forward-validation",
    ),
)


def to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if result == result else default


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def markdown_table(frame: pl.DataFrame, columns: list[str], max_rows: int = 80) -> str:
    if frame.is_empty():
        return "无数据"
    cols = [col for col in columns if col in frame.columns]
    if not cols:
        return "无数据"
    return frame.select(cols).head(max_rows).to_pandas().to_markdown(index=False)


def read_source_csv(name: str) -> pl.DataFrame:
    path = SOURCE_DIR / f"{SOURCE_PREFIX}_{name}.csv"
    return pl.read_csv(
        path,
        try_parse_dates=True,
        schema_overrides={
            "symbol": pl.Utf8,
            "vt_symbol": pl.Utf8,
            "bs_code": pl.Utf8,
            "code": pl.Utf8,
        },
    )


def summarize_returns(returns: list[float]) -> dict[str, float]:
    if not returns:
        return {
            "total_return": 0.0,
            "annualized_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe": 0.0,
            "daily_mean": 0.0,
            "daily_std": 0.0,
        }
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for value in returns:
        equity *= 1.0 + value
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1.0)
    mean = sum(returns) / len(returns)
    variance = sum((item - mean) ** 2 for item in returns) / (len(returns) - 1) if len(returns) > 1 else 0.0
    std = variance**0.5
    return {
        "total_return": equity - 1.0,
        "annualized_return": equity ** (TRADING_DAYS / len(returns)) - 1 if equity > 0 else -1.0,
        "max_drawdown": worst,
        "sharpe": mean / std * sqrt(TRADING_DAYS) if std > 0 else 0.0,
        "daily_mean": mean,
        "daily_std": std,
    }


def summarize_curve_frame(frame: pl.DataFrame) -> dict[str, Any]:
    ordered = frame.sort("date")
    returns = [float(value) for value in ordered["strategy_daily_ret"].to_list()]
    stats = summarize_returns(returns)
    return {
        "days": len(returns),
        "start_date": str(ordered["date"].min()) if ordered.height else "",
        "end_date": str(ordered["date"].max()) if ordered.height else "",
        "period_return": stats["total_return"],
        "annualized_return": stats["annualized_return"],
        "max_drawdown": stats["max_drawdown"],
        "sharpe": stats["sharpe"],
        "avg_gross_exposure": to_float(ordered["target_gross_exposure"].mean()) if ordered.height else 0.0,
        "one_way_turnover_sum": to_float(ordered["one_way_turnover"].sum()) if ordered.height else 0.0,
        "annualized_one_way_turnover": to_float(ordered["one_way_turnover"].mean()) * TRADING_DAYS
        if ordered.height
        else 0.0,
    }


def build_start_year_summary(equity_curve: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    rows: list[dict[str, Any]] = []
    work = equity_curve.filter(
        (pl.col("scenario").is_in(AUDIT_SCENARIOS)) & (pl.col("roundtrip_cost_bps") == COST_BPS)
    )
    for key, group in work.partition_by(["scenario", "roundtrip_cost_bps"], as_dict=True).items():
        scenario, cost_bps = key
        for start_year in START_YEARS:
            frame = group.filter(pl.col("date") >= date(start_year, 1, 1))
            if frame.is_empty():
                continue
            rows.append(
                {
                    "scenario": scenario,
                    "roundtrip_cost_bps": float(cost_bps),
                    "start_year": start_year,
                    "period": f"since_{start_year}",
                    **summarize_curve_frame(frame),
                }
            )
    start_summary = pl.DataFrame(rows).sort(["start_year", "scenario"]) if rows else pl.DataFrame()
    if start_summary.is_empty():
        return start_summary, pl.DataFrame(), pl.DataFrame()
    baseline = start_summary.filter(pl.col("scenario") == BASELINE_SCENARIO).select(
        "roundtrip_cost_bps",
        "start_year",
        pl.col("period_return").alias("baseline_period_return"),
        pl.col("max_drawdown").alias("baseline_max_drawdown"),
        pl.col("sharpe").alias("baseline_sharpe"),
    )
    start_delta = (
        start_summary.join(baseline, on=["roundtrip_cost_bps", "start_year"], how="left")
        .with_columns(
            (pl.col("period_return") - pl.col("baseline_period_return")).alias("period_return_delta_vs_baseline"),
            (pl.col("max_drawdown") - pl.col("baseline_max_drawdown")).alias("max_drawdown_delta_vs_baseline"),
            (pl.col("sharpe") - pl.col("baseline_sharpe")).alias("sharpe_delta_vs_baseline"),
            (pl.col("period_return") > pl.col("baseline_period_return")).alias("beats_baseline_return"),
            (pl.col("max_drawdown") > pl.col("baseline_max_drawdown")).alias("beats_baseline_drawdown"),
            (pl.col("sharpe") > pl.col("baseline_sharpe")).alias("beats_baseline_sharpe"),
        )
        .sort(["start_year", "scenario"])
    )
    start_scorecard = (
        start_delta.filter(pl.col("scenario") != BASELINE_SCENARIO)
        .group_by(["scenario", "roundtrip_cost_bps"])
        .agg(
            pl.len().alias("start_count"),
            pl.col("beats_baseline_return").sum().alias("return_beat_count"),
            pl.col("beats_baseline_drawdown").sum().alias("drawdown_beat_count"),
            pl.col("beats_baseline_sharpe").sum().alias("sharpe_beat_count"),
            pl.col("period_return_delta_vs_baseline").mean().alias("avg_period_return_delta"),
            pl.col("period_return_delta_vs_baseline").min().alias("worst_period_return_delta"),
            pl.col("max_drawdown_delta_vs_baseline").mean().alias("avg_max_drawdown_delta"),
            pl.col("sharpe_delta_vs_baseline").mean().alias("avg_sharpe_delta"),
            pl.col("sharpe_delta_vs_baseline").min().alias("worst_sharpe_delta"),
        )
        .with_columns(
            (pl.col("return_beat_count") / pl.col("start_count")).alias("return_beat_ratio"),
            (pl.col("drawdown_beat_count") / pl.col("start_count")).alias("drawdown_beat_ratio"),
            (pl.col("sharpe_beat_count") / pl.col("start_count")).alias("sharpe_beat_ratio"),
        )
        .sort("scenario")
    )
    return start_summary, start_delta, start_scorecard


def build_rolling_summary(equity_curve: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    rows: list[dict[str, Any]] = []
    work = equity_curve.filter(
        (pl.col("scenario").is_in(AUDIT_SCENARIOS)) & (pl.col("roundtrip_cost_bps") == COST_BPS)
    )
    for key, group in work.partition_by(["scenario", "roundtrip_cost_bps"], as_dict=True).items():
        scenario, cost_bps = key
        ordered = group.sort("date")
        for window in ROLLING_WINDOWS:
            if ordered.height < window:
                continue
            for end_idx in range(window - 1, ordered.height):
                frame = ordered.slice(end_idx - window + 1, window)
                rows.append(
                    {
                        "scenario": scenario,
                        "roundtrip_cost_bps": float(cost_bps),
                        "window_days": window,
                        "window_start": str(frame["date"].min()),
                        "window_end": str(frame["date"].max()),
                        **summarize_curve_frame(frame),
                    }
                )
    rolling_summary = pl.DataFrame(rows).sort(["window_days", "window_end", "scenario"]) if rows else pl.DataFrame()
    if rolling_summary.is_empty():
        return rolling_summary, pl.DataFrame(), pl.DataFrame()
    baseline = rolling_summary.filter(pl.col("scenario") == BASELINE_SCENARIO).select(
        "roundtrip_cost_bps",
        "window_days",
        "window_start",
        "window_end",
        pl.col("period_return").alias("baseline_period_return"),
        pl.col("max_drawdown").alias("baseline_max_drawdown"),
        pl.col("sharpe").alias("baseline_sharpe"),
    )
    rolling_delta = (
        rolling_summary.join(
            baseline,
            on=["roundtrip_cost_bps", "window_days", "window_start", "window_end"],
            how="left",
        )
        .with_columns(
            (pl.col("period_return") - pl.col("baseline_period_return")).alias("period_return_delta_vs_baseline"),
            (pl.col("max_drawdown") - pl.col("baseline_max_drawdown")).alias("max_drawdown_delta_vs_baseline"),
            (pl.col("sharpe") - pl.col("baseline_sharpe")).alias("sharpe_delta_vs_baseline"),
            (pl.col("period_return") > pl.col("baseline_period_return")).alias("beats_baseline_return"),
            (pl.col("max_drawdown") > pl.col("baseline_max_drawdown")).alias("beats_baseline_drawdown"),
            (pl.col("sharpe") > pl.col("baseline_sharpe")).alias("beats_baseline_sharpe"),
        )
        .sort(["window_days", "window_end", "scenario"])
    )
    rolling_scorecard = (
        rolling_delta.filter(pl.col("scenario") != BASELINE_SCENARIO)
        .group_by(["scenario", "roundtrip_cost_bps", "window_days"])
        .agg(
            pl.len().alias("window_count"),
            pl.col("beats_baseline_return").sum().alias("return_beat_count"),
            pl.col("beats_baseline_drawdown").sum().alias("drawdown_beat_count"),
            pl.col("beats_baseline_sharpe").sum().alias("sharpe_beat_count"),
            pl.col("period_return_delta_vs_baseline").mean().alias("avg_period_return_delta"),
            pl.col("period_return_delta_vs_baseline").median().alias("median_period_return_delta"),
            pl.col("period_return_delta_vs_baseline").min().alias("worst_period_return_delta"),
            pl.col("max_drawdown_delta_vs_baseline").mean().alias("avg_max_drawdown_delta"),
            pl.col("sharpe_delta_vs_baseline").mean().alias("avg_sharpe_delta"),
            pl.col("sharpe_delta_vs_baseline").min().alias("worst_sharpe_delta"),
        )
        .with_columns(
            (pl.col("return_beat_count") / pl.col("window_count")).alias("return_beat_ratio"),
            (pl.col("drawdown_beat_count") / pl.col("window_count")).alias("drawdown_beat_ratio"),
            (pl.col("sharpe_beat_count") / pl.col("window_count")).alias("sharpe_beat_ratio"),
        )
        .sort(["scenario", "window_days"])
    )
    return rolling_summary, rolling_delta, rolling_scorecard


def weighted_signal_summary(selected: pl.DataFrame, fold: dict[str, Any], fold_part: str) -> pl.DataFrame:
    if selected.is_empty():
        return pl.DataFrame()
    work = selected.with_columns(
        (pl.col("basket_weight") * pl.col(f"fwd_excess_ret_{HORIZON}")).alias("_weighted_excess"),
        (pl.col("basket_weight") * pl.col(f"fwd_ret_{HORIZON}")).alias("_weighted_abs"),
    )
    summary = (
        work.group_by("scenario")
        .agg(
            pl.len().alias("candidate_rows"),
            pl.col("datetime").n_unique().alias("signal_days"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("industry").n_unique().alias("industries"),
            pl.col("basket_weight").sum().alias("weight_sum"),
            pl.col(f"fwd_excess_ret_{HORIZON}").mean().alias("avg_fwd_excess_ret_10"),
            pl.col("_weighted_excess").sum().alias("weighted_excess_sum"),
            pl.col("_weighted_abs").sum().alias("weighted_abs_sum"),
            (pl.col(f"fwd_excess_ret_{HORIZON}") > 0).mean().alias("positive_excess_ratio"),
        )
        .with_columns(
            (pl.col("weighted_excess_sum") / pl.col("weight_sum")).alias("weighted_avg_fwd_excess_ret_10"),
            (pl.col("weighted_abs_sum") / pl.col("weight_sum")).alias("weighted_avg_fwd_ret_10"),
        )
    )
    return summary.with_columns(
        pl.lit(fold["fold_id"]).alias("fold_id"),
        pl.lit(fold["fold_type"]).alias("fold_type"),
        pl.lit(fold_part).alias("fold_part"),
        pl.lit(fold["train_start"]).alias("train_start"),
        pl.lit(fold["train_end"]).alias("train_end"),
        pl.lit(fold["valid_start"]).alias("valid_start"),
        pl.lit(fold["valid_end"]).alias("valid_end"),
    ).select(
        [
            "fold_id",
            "fold_type",
            "fold_part",
            "train_start",
            "train_end",
            "valid_start",
            "valid_end",
            "scenario",
            "candidate_rows",
            "signal_days",
            "symbols",
            "industries",
            "weight_sum",
            "avg_fwd_excess_ret_10",
            "weighted_avg_fwd_excess_ret_10",
            "weighted_avg_fwd_ret_10",
            "positive_excess_ratio",
        ]
    )


def build_fold_definitions(calendar: list[date]) -> list[dict[str, Any]]:
    folds: list[dict[str, Any]] = []
    min_date = calendar[0]
    max_date = calendar[-1]
    for year in OOS_YEARS:
        valid_start_idx = next((idx for idx, value in enumerate(calendar) if value >= date(year, 1, 1)), None)
        if valid_start_idx is None:
            continue
        valid_end_idx = next((idx for idx, value in enumerate(calendar) if value >= date(year + 1, 1, 1)), len(calendar)) - 1
        if valid_end_idx < valid_start_idx:
            continue
        train_end_idx = valid_start_idx - GAP_DAYS - 1
        if train_end_idx <= 0:
            continue
        folds.append(
            {
                "fold_id": f"annual_expanding_{year}",
                "fold_type": "annual_expanding",
                "train_start": min_date,
                "train_end": calendar[train_end_idx],
                "valid_start": calendar[valid_start_idx],
                "valid_end": calendar[valid_end_idx],
            }
        )

    valid_start_idx = ROLLING_TRAIN_DAYS + GAP_DAYS
    fold_no = 1
    while valid_start_idx < len(calendar):
        valid_end_idx = min(valid_start_idx + ROLLING_TEST_DAYS - 1, len(calendar) - 1)
        train_end_idx = valid_start_idx - GAP_DAYS - 1
        train_start_idx = train_end_idx - ROLLING_TRAIN_DAYS + 1
        if train_start_idx >= 0 and valid_end_idx > valid_start_idx:
            folds.append(
                {
                    "fold_id": f"quarter_rolling_{fold_no:02d}",
                    "fold_type": "quarter_rolling",
                    "train_start": calendar[train_start_idx],
                    "train_end": calendar[train_end_idx],
                    "valid_start": calendar[valid_start_idx],
                    "valid_end": calendar[valid_end_idx],
                }
            )
            fold_no += 1
        valid_start_idx += ROLLING_STEP_DAYS
    return folds


def build_fold_edge_and_curve(
    selected: pl.DataFrame,
    equity_curve: pl.DataFrame,
    folds: list[dict[str, Any]],
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    edge_frames: list[pl.DataFrame] = []
    curve_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []
    for fold in folds:
        train_selected = selected.filter(
            (pl.col("datetime") >= fold["train_start"]) & (pl.col("datetime") <= fold["train_end"])
        )
        valid_selected = selected.filter(
            (pl.col("datetime") >= fold["valid_start"]) & (pl.col("datetime") <= fold["valid_end"])
        )
        edge_frames.append(weighted_signal_summary(train_selected, fold, "train"))
        edge_frames.append(weighted_signal_summary(valid_selected, fold, "valid_signal"))
        train_summary = weighted_signal_summary(train_selected, fold, "train")
        train_map = {
            row["scenario"]: to_float(row["weighted_avg_fwd_excess_ret_10"])
            for row in train_summary.iter_rows(named=True)
        }
        weak_edge_found = (
            train_map.get(PRIMARY_SCENARIO, -999.0) > train_map.get(BASELINE_SCENARIO, -999.0)
            and train_map.get(PRIMARY_SCENARIO, -999.0) > train_map.get(NEGATIVE_CONTROL_SCENARIO, -999.0)
        )
        decision_rows.append(
            {
                "fold_id": fold["fold_id"],
                "fold_type": fold["fold_type"],
                "train_start": fold["train_start"],
                "train_end": fold["train_end"],
                "valid_start": fold["valid_start"],
                "valid_end": fold["valid_end"],
                "weak_edge_found_in_train": weak_edge_found,
                "train_primary_weighted_excess": train_map.get(PRIMARY_SCENARIO),
                "train_baseline_weighted_excess": train_map.get(BASELINE_SCENARIO),
                "train_negative_control_weighted_excess": train_map.get(NEGATIVE_CONTROL_SCENARIO),
            }
        )
        for scenario in AUDIT_SCENARIOS:
            frame = equity_curve.filter(
                (pl.col("scenario") == scenario)
                & (pl.col("roundtrip_cost_bps") == COST_BPS)
                & (pl.col("date") >= fold["valid_start"])
                & (pl.col("date") <= fold["valid_end"])
            )
            if frame.is_empty():
                continue
            curve_rows.append(
                {
                    "fold_id": fold["fold_id"],
                    "fold_type": fold["fold_type"],
                    "train_start": fold["train_start"],
                    "train_end": fold["train_end"],
                    "valid_start": fold["valid_start"],
                    "valid_end": fold["valid_end"],
                    "scenario": scenario,
                    **summarize_curve_frame(frame),
                }
            )

    edge_summary = pl.concat(edge_frames, how="vertical").sort(["fold_type", "fold_id", "fold_part", "scenario"])
    curve_summary = pl.DataFrame(curve_rows).sort(["fold_type", "fold_id", "scenario"])
    fold_decisions = pl.DataFrame(decision_rows).sort(["fold_type", "fold_id"])
    if curve_summary.is_empty():
        return edge_summary, curve_summary, fold_decisions
    baseline = curve_summary.filter(pl.col("scenario") == BASELINE_SCENARIO).select(
        "fold_id",
        "fold_type",
        pl.col("period_return").alias("baseline_period_return"),
        pl.col("max_drawdown").alias("baseline_max_drawdown"),
        pl.col("sharpe").alias("baseline_sharpe"),
    )
    curve_summary = (
        curve_summary.join(baseline, on=["fold_id", "fold_type"], how="left")
        .with_columns(
            (pl.col("period_return") - pl.col("baseline_period_return")).alias("period_return_delta_vs_baseline"),
            (pl.col("max_drawdown") - pl.col("baseline_max_drawdown")).alias("max_drawdown_delta_vs_baseline"),
            (pl.col("sharpe") - pl.col("baseline_sharpe")).alias("sharpe_delta_vs_baseline"),
            (pl.col("period_return") > pl.col("baseline_period_return")).alias("beats_baseline_return"),
            (pl.col("max_drawdown") > pl.col("baseline_max_drawdown")).alias("beats_baseline_drawdown"),
            (pl.col("sharpe") > pl.col("baseline_sharpe")).alias("beats_baseline_sharpe"),
        )
        .sort(["fold_type", "fold_id", "scenario"])
    )
    return edge_summary, curve_summary, fold_decisions


def build_fold_scorecard(fold_curve_summary: pl.DataFrame) -> pl.DataFrame:
    if fold_curve_summary.is_empty():
        return pl.DataFrame()
    return (
        fold_curve_summary.filter(pl.col("scenario") != BASELINE_SCENARIO)
        .group_by(["fold_type", "scenario"])
        .agg(
            pl.len().alias("fold_count"),
            pl.col("beats_baseline_return").sum().alias("return_beat_count"),
            pl.col("beats_baseline_drawdown").sum().alias("drawdown_beat_count"),
            pl.col("beats_baseline_sharpe").sum().alias("sharpe_beat_count"),
            pl.col("period_return_delta_vs_baseline").mean().alias("avg_period_return_delta"),
            pl.col("period_return_delta_vs_baseline").min().alias("worst_period_return_delta"),
            pl.col("max_drawdown_delta_vs_baseline").mean().alias("avg_max_drawdown_delta"),
            pl.col("sharpe_delta_vs_baseline").mean().alias("avg_sharpe_delta"),
            pl.col("sharpe_delta_vs_baseline").min().alias("worst_sharpe_delta"),
        )
        .with_columns(
            (pl.col("return_beat_count") / pl.col("fold_count")).alias("return_beat_ratio"),
            (pl.col("drawdown_beat_count") / pl.col("fold_count")).alias("drawdown_beat_ratio"),
            (pl.col("sharpe_beat_count") / pl.col("fold_count")).alias("sharpe_beat_ratio"),
        )
        .sort(["fold_type", "scenario"])
    )


def build_edge_decision_scorecard(fold_decisions: pl.DataFrame) -> pl.DataFrame:
    if fold_decisions.is_empty():
        return pl.DataFrame()
    return (
        fold_decisions.group_by("fold_type")
        .agg(
            pl.len().alias("fold_count"),
            pl.col("weak_edge_found_in_train").sum().alias("weak_edge_found_count"),
            pl.col("train_primary_weighted_excess").mean().alias("avg_train_primary_weighted_excess"),
            pl.col("train_baseline_weighted_excess").mean().alias("avg_train_baseline_weighted_excess"),
            pl.col("train_negative_control_weighted_excess").mean().alias("avg_train_negative_control_weighted_excess"),
        )
        .with_columns((pl.col("weak_edge_found_count") / pl.col("fold_count")).alias("weak_edge_found_ratio"))
        .sort("fold_type")
    )


def build_concentration_audit(selected: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for scenario in AUDIT_SCENARIOS:
        subset = selected.filter(pl.col("scenario") == scenario)
        if subset.is_empty():
            continue
        weighted = subset.with_columns(
            (pl.col("basket_weight") * pl.col(f"fwd_excess_ret_{HORIZON}")).alias("_weighted_excess")
        )
        industry = (
            weighted.group_by("industry")
            .agg(
                pl.col("_weighted_excess").sum().alias("weighted_excess_sum"),
                pl.col("_weighted_excess").abs().sum().alias("abs_weighted_excess_sum"),
            )
            .sort("abs_weighted_excess_sum", descending=True)
        )
        symbol = (
            weighted.group_by("symbol")
            .agg(pl.col("_weighted_excess").abs().sum().alias("abs_weighted_excess_sum"))
            .sort("abs_weighted_excess_sum", descending=True)
        )
        total_ind_abs = to_float(industry["abs_weighted_excess_sum"].sum())
        total_symbol_abs = to_float(symbol["abs_weighted_excess_sum"].sum())
        daily = subset.group_by("datetime").agg(
            pl.len().alias("candidate_count"),
            pl.col("industry").n_unique().alias("industry_count"),
            pl.col("basket_gross_weight").first().alias("basket_gross_weight"),
        )
        rows.append(
            {
                "scenario": scenario,
                "candidate_rows": subset.height,
                "signal_days": subset["datetime"].n_unique(),
                "symbols": subset["symbol"].n_unique(),
                "industries": subset["industry"].n_unique(),
                "avg_candidate_count": to_float(daily["candidate_count"].mean()),
                "avg_signal_industry_count": to_float(daily["industry_count"].mean()),
                "p05_signal_industry_count": to_float(daily["industry_count"].quantile(0.05)),
                "avg_basket_gross_weight": to_float(daily["basket_gross_weight"].mean()),
                "top5_industry_abs_share": to_float(industry.head(5)["abs_weighted_excess_sum"].sum()) / total_ind_abs
                if total_ind_abs > 0
                else 0.0,
                "top10_symbol_abs_share": to_float(symbol.head(10)["abs_weighted_excess_sum"].sum()) / total_symbol_abs
                if total_symbol_abs > 0
                else 0.0,
                "top20_symbol_abs_share": to_float(symbol.head(20)["abs_weighted_excess_sum"].sum()) / total_symbol_abs
                if total_symbol_abs > 0
                else 0.0,
            }
        )
    return pl.DataFrame(rows).sort("scenario") if rows else pl.DataFrame()


def build_quality_checkpoints(
    edge_decision_scorecard: pl.DataFrame,
    fold_scorecard: pl.DataFrame,
    rolling_scorecard: pl.DataFrame,
    concentration_audit: pl.DataFrame,
) -> pl.DataFrame:
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

    for fold_type in ["annual_expanding", "quarter_rolling"]:
        row = edge_decision_scorecard.filter(pl.col("fold_type") == fold_type)
        ratio = to_float(row["weak_edge_found_ratio"][0]) if row.height else 0.0
        add(
            f"{fold_type}_train_weak_edge_found_ratio",
            "fail" if ratio < 0.60 else "pass",
            f"{ratio:.2%}",
            ">=60%",
            "只看训练端，若多数折不能发现weak edge，则全样本发现偏重。",
        )
    primary_annual = fold_scorecard.filter(
        (pl.col("fold_type") == "annual_expanding") & (pl.col("scenario") == PRIMARY_SCENARIO)
    )
    primary_quarter = fold_scorecard.filter(
        (pl.col("fold_type") == "quarter_rolling") & (pl.col("scenario") == PRIMARY_SCENARIO)
    )
    for label, row in [("annual", primary_annual), ("quarter", primary_quarter)]:
        sharpe_ratio = to_float(row["sharpe_beat_ratio"][0]) if row.height else 0.0
        dd_ratio = to_float(row["drawdown_beat_ratio"][0]) if row.height else 0.0
        add(
            f"primary_{label}_valid_sharpe_beat_ratio",
            "fail" if sharpe_ratio < 0.60 else "warn" if sharpe_ratio < 0.70 else "pass",
            f"{sharpe_ratio:.2%}",
            ">=70% preferred, >=60% minimum",
            "验证端Sharpe跑赢率过低时不能候选升级。",
        )
        add(
            f"primary_{label}_valid_drawdown_beat_ratio",
            "fail" if dd_ratio < 0.70 else "pass",
            f"{dd_ratio:.2%}",
            ">=70%",
            "弱势修复至少应稳定改善回撤。",
        )
    primary_rolling_504 = rolling_scorecard.filter(
        (pl.col("scenario") == PRIMARY_SCENARIO) & (pl.col("window_days") == 504)
    )
    rolling_sharpe = to_float(primary_rolling_504["sharpe_beat_ratio"][0]) if primary_rolling_504.height else 0.0
    add(
        "primary_504d_rolling_sharpe_beat_ratio",
        "fail" if rolling_sharpe < 0.70 else "pass",
        f"{rolling_sharpe:.2%}",
        ">=70%",
        "长窗口Sharpe跑赢率是是否继续研究的硬条件。",
    )
    primary_conc = concentration_audit.filter(pl.col("scenario") == PRIMARY_SCENARIO)
    top5_ind = to_float(primary_conc["top5_industry_abs_share"][0]) if primary_conc.height else 0.0
    add(
        "primary_top5_industry_abs_share",
        "fail" if top5_ind >= 0.90 else "warn" if top5_ind >= 0.75 else "pass",
        f"{top5_ind:.2%}",
        "<75% preferred, <90% hard",
        "行业贡献过度集中会削弱穿越周期能力。",
    )
    return pl.DataFrame(rows)


def write_report(
    edge_decision_scorecard: pl.DataFrame,
    fold_scorecard: pl.DataFrame,
    start_scorecard: pl.DataFrame,
    rolling_scorecard: pl.DataFrame,
    concentration_audit: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    primary_annual = fold_scorecard.filter(
        (pl.col("fold_type") == "annual_expanding") & (pl.col("scenario") == PRIMARY_SCENARIO)
    )
    primary_quarter = fold_scorecard.filter(
        (pl.col("fold_type") == "quarter_rolling") & (pl.col("scenario") == PRIMARY_SCENARIO)
    )
    reallocated_quarter = fold_scorecard.filter(
        (pl.col("fold_type") == "quarter_rolling") & (pl.col("scenario") == REALLOCATED_SCENARIO)
    )
    train_annual = edge_decision_scorecard.filter(pl.col("fold_type") == "annual_expanding")
    train_quarter = edge_decision_scorecard.filter(pl.col("fold_type") == "quarter_rolling")
    lines = [
        "# 股票震荡liquid_q3 momentum pullback rolling validation v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：对第294阶段弱势修复做启动年份、滚动窗口、年度expanding OOS和季度rolling OOS验证。",
        f"- Gap/embargo：`{GAP_DAYS}`个交易日；季度rolling训练`{ROLLING_TRAIN_DAYS}`日、验证`{ROLLING_TEST_DAYS}`日。",
        "- A/B判断：只做独立股票线验证，不接入正式版本，不触发第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- TimeSeriesSplit的gap思想支持在训练和验证之间留出间隔，降低重叠路径泄漏。",
        "- PBO研究提醒，全样本挑出来的策略即使回测漂亮，也可能是多重试验幻觉。",
        "- GitHub walk-forward样例可借鉴流程，但不能替代本仓库A股信号、行业、成本和成交约束。",
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
            f"- 年度expanding训练端发现weak edge比例：`{pct(to_float(train_annual['weak_edge_found_ratio'][0]) if train_annual.height else 0.0)}`。",
            f"- 季度rolling训练端发现weak edge比例：`{pct(to_float(train_quarter['weak_edge_found_ratio'][0]) if train_quarter.height else 0.0)}`。",
            f"- 诊断组年度OOS Sharpe跑赢率：`{pct(to_float(primary_annual['sharpe_beat_ratio'][0]) if primary_annual.height else 0.0)}`，回撤改善率：`{pct(to_float(primary_annual['drawdown_beat_ratio'][0]) if primary_annual.height else 0.0)}`。",
            f"- 诊断组季度OOS Sharpe跑赢率：`{pct(to_float(primary_quarter['sharpe_beat_ratio'][0]) if primary_quarter.height else 0.0)}`，收益跑赢率：`{pct(to_float(primary_quarter['return_beat_ratio'][0]) if primary_quarter.height else 0.0)}`。",
            f"- 重分配组季度OOS收益跑赢率：`{pct(to_float(reallocated_quarter['return_beat_ratio'][0]) if reallocated_quarter.height else 0.0)}`，Sharpe跑赢率：`{pct(to_float(reallocated_quarter['sharpe_beat_ratio'][0]) if reallocated_quarter.height else 0.0)}`。",
            f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。",
            "",
            "## 训练端edge发现率",
            "",
            markdown_table(
                edge_decision_scorecard,
                [
                    "fold_type",
                    "fold_count",
                    "weak_edge_found_count",
                    "weak_edge_found_ratio",
                    "avg_train_primary_weighted_excess",
                    "avg_train_baseline_weighted_excess",
                    "avg_train_negative_control_weighted_excess",
                ],
            ),
            "",
            "## OOS折叠记分",
            "",
            markdown_table(
                fold_scorecard,
                [
                    "fold_type",
                    "scenario",
                    "fold_count",
                    "return_beat_ratio",
                    "drawdown_beat_ratio",
                    "sharpe_beat_ratio",
                    "avg_period_return_delta",
                    "worst_period_return_delta",
                    "avg_max_drawdown_delta",
                    "avg_sharpe_delta",
                    "worst_sharpe_delta",
                ],
                max_rows=40,
            ),
            "",
            "## 启动年份记分",
            "",
            markdown_table(
                start_scorecard,
                [
                    "scenario",
                    "start_count",
                    "return_beat_ratio",
                    "drawdown_beat_ratio",
                    "sharpe_beat_ratio",
                    "avg_period_return_delta",
                    "worst_period_return_delta",
                    "avg_max_drawdown_delta",
                    "avg_sharpe_delta",
                    "worst_sharpe_delta",
                ],
                max_rows=40,
            ),
            "",
            "## 滚动窗口记分",
            "",
            markdown_table(
                rolling_scorecard,
                [
                    "scenario",
                    "window_days",
                    "window_count",
                    "return_beat_ratio",
                    "drawdown_beat_ratio",
                    "sharpe_beat_ratio",
                    "avg_period_return_delta",
                    "worst_period_return_delta",
                    "avg_max_drawdown_delta",
                    "avg_sharpe_delta",
                    "worst_sharpe_delta",
                ],
                max_rows=60,
            ),
            "",
            "## 集中度审计",
            "",
            markdown_table(
                concentration_audit,
                [
                    "scenario",
                    "candidate_rows",
                    "signal_days",
                    "symbols",
                    "industries",
                    "avg_candidate_count",
                    "avg_signal_industry_count",
                    "p05_signal_industry_count",
                    "top5_industry_abs_share",
                    "top10_symbol_abs_share",
                    "top20_symbol_abs_share",
                ],
            ),
            "",
            "## 质量检查",
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
            "- 判断：有风险。",
            "- 原因：`weak_market60_q1q2`是第294阶段全样本归因后的强结果，必须用过去训练、未来验证回答是否能外推。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：风险下降，但未消失。",
            "- 原因：训练端多数折能发现weak edge，验证端Sharpe/回撤稳定；但行业集中黄灯仍在，且收益跑赢率不是每个窗口都强。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第296阶段伪象审计未否决弱势修复，下一步应做walk-forward验证。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：弱势修复通过了训练端edge发现和多数OOS稳定性检查；下一步可以做30万候选整手复放，但必须保持独立命名和输出。",
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
    selected = read_source_csv("selected_variants").filter(pl.col("scenario").is_in(AUDIT_SCENARIOS))
    equity_curve = read_source_csv("equity_curve").filter(
        (pl.col("scenario").is_in(AUDIT_SCENARIOS)) & (pl.col("roundtrip_cost_bps") == COST_BPS)
    )
    calendar = equity_curve.select("date").unique().sort("date")["date"].to_list()
    folds = build_fold_definitions(calendar)
    fold_edge_summary, fold_curve_summary, fold_decisions = build_fold_edge_and_curve(selected, equity_curve, folds)
    fold_scorecard = build_fold_scorecard(fold_curve_summary)
    edge_decision_scorecard = build_edge_decision_scorecard(fold_decisions)
    start_year_summary, start_year_delta, start_year_scorecard = build_start_year_summary(equity_curve)
    rolling_summary, rolling_delta, rolling_scorecard = build_rolling_summary(equity_curve)
    concentration_audit = build_concentration_audit(selected)
    quality = build_quality_checkpoints(
        edge_decision_scorecard,
        fold_scorecard,
        rolling_scorecard,
        concentration_audit,
    )

    paths: dict[str, Path] = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "fold_edge_summary": OUTPUT_DIR / f"{PREFIX}_fold_edge_summary.csv",
        "fold_curve_summary": OUTPUT_DIR / f"{PREFIX}_fold_curve_summary.csv",
        "fold_decisions": OUTPUT_DIR / f"{PREFIX}_fold_decisions.csv",
        "fold_scorecard": OUTPUT_DIR / f"{PREFIX}_fold_scorecard.csv",
        "edge_decision_scorecard": OUTPUT_DIR / f"{PREFIX}_edge_decision_scorecard.csv",
        "start_year_summary": OUTPUT_DIR / f"{PREFIX}_start_year_summary.csv",
        "start_year_delta": OUTPUT_DIR / f"{PREFIX}_start_year_delta.csv",
        "start_year_scorecard": OUTPUT_DIR / f"{PREFIX}_start_year_scorecard.csv",
        "rolling_summary": OUTPUT_DIR / f"{PREFIX}_rolling_summary.csv",
        "rolling_delta": OUTPUT_DIR / f"{PREFIX}_rolling_delta.csv",
        "rolling_scorecard": OUTPUT_DIR / f"{PREFIX}_rolling_scorecard.csv",
        "concentration_audit": OUTPUT_DIR / f"{PREFIX}_concentration_audit.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    fold_edge_summary.write_csv(paths["fold_edge_summary"])
    fold_curve_summary.write_csv(paths["fold_curve_summary"])
    fold_decisions.write_csv(paths["fold_decisions"])
    fold_scorecard.write_csv(paths["fold_scorecard"])
    edge_decision_scorecard.write_csv(paths["edge_decision_scorecard"])
    start_year_summary.write_csv(paths["start_year_summary"])
    start_year_delta.write_csv(paths["start_year_delta"])
    start_year_scorecard.write_csv(paths["start_year_scorecard"])
    rolling_summary.write_csv(paths["rolling_summary"])
    rolling_delta.write_csv(paths["rolling_delta"])
    rolling_scorecard.write_csv(paths["rolling_scorecard"])
    concentration_audit.write_csv(paths["concentration_audit"])
    quality.write_csv(paths["quality_checkpoints"])
    meta = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_dir": str(SOURCE_DIR),
        "source_prefix": SOURCE_PREFIX,
        "audit_scenarios": AUDIT_SCENARIOS,
        "baseline_scenario": BASELINE_SCENARIO,
        "primary_scenario": PRIMARY_SCENARIO,
        "reallocated_scenario": REALLOCATED_SCENARIO,
        "negative_control_scenario": NEGATIVE_CONTROL_SCENARIO,
        "cost_bps": COST_BPS,
        "gap_days": GAP_DAYS,
        "rolling_train_days": ROLLING_TRAIN_DAYS,
        "rolling_test_days": ROLLING_TEST_DAYS,
        "rolling_step_days": ROLLING_STEP_DAYS,
        "rolling_windows": ROLLING_WINDOWS,
        "oos_years": OOS_YEARS,
        "fold_count": len(folds),
        "research_sources": RESEARCH_SOURCES,
    }
    write_json(paths["meta"], meta)
    report_path = write_report(
        edge_decision_scorecard,
        fold_scorecard,
        start_year_scorecard,
        rolling_scorecard,
        concentration_audit,
        quality,
        paths,
    )
    print(f"report={report_path}")
    print(quality)


if __name__ == "__main__":
    main()
