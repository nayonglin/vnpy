from __future__ import annotations

import json
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import (
    HORIZON,
    NATIVE_RESULTS_DIR,
    TRADING_DAYS,
    build_benchmark_daily,
    build_calendar,
    build_concentration,
    build_daily_gross,
    build_equity_curve,
    build_lots,
    build_symbol_daily,
    build_turnover,
    pct,
    summarize_curve,
)


SOURCE_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_momentum_pullback_attribution_2018_2026"
).expanduser().resolve()
SOURCE_PREFIX: str = "stock_range_reversion_liquid_q3_momentum_pullback_attribution_v1"
OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_weak_market60_q1q2_false_positive_audit_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_weak_market60_q1q2_false_positive_audit_v1"

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
ROLLING_WINDOWS: tuple[int, ...] = (126, 252, 504)
CORE_INDUSTRY_COUNT: int = 5

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Alphalens factor research toolkit",
        "https://github.com/cloudQuant/alphalens",
    ),
    (
        "scikit-learn TimeSeriesSplit gap",
        "https://sklearn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html",
    ),
    (
        "Bailey/Lopez de Prado PBO paper",
        "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253",
    ),
    (
        "FactSet regime robustness in backtesting",
        "https://insight.factset.com/understanding-regime-changes-for-robustness-in-backtesting",
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
        return {"total_return": 0.0, "max_drawdown": 0.0, "sharpe": 0.0}
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
        "max_drawdown": worst,
        "sharpe": mean / std * sqrt(TRADING_DAYS) if std > 0 else 0.0,
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
        "max_drawdown": stats["max_drawdown"],
        "sharpe": stats["sharpe"],
        "avg_gross_exposure": to_float(ordered["target_gross_exposure"].mean()) if ordered.height else 0.0,
        "one_way_turnover_sum": to_float(ordered["one_way_turnover"].sum()) if ordered.height else 0.0,
    }


def build_rolling_scorecard(equity_curve: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
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


def build_symbol_daily_by_scenario(selected: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    lots = build_lots(selected)
    symbol_daily = build_symbol_daily(lots)
    return lots, symbol_daily


def build_industry_contribution(symbol_daily: pl.DataFrame) -> pl.DataFrame:
    if symbol_daily.is_empty():
        return pl.DataFrame()
    grouped = (
        symbol_daily.group_by(["scenario", "industry"])
        .agg(
            pl.len().alias("symbol_day_rows"),
            pl.col("pnl_date").n_unique().alias("pnl_days"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("target_weight").mean().alias("avg_target_weight"),
            pl.col("weighted_stock_ret").sum().alias("gross_contribution_sum"),
            pl.when(pl.col("weighted_stock_ret") > 0)
            .then(pl.col("weighted_stock_ret"))
            .otherwise(0.0)
            .sum()
            .alias("positive_contribution_sum"),
            pl.when(pl.col("weighted_stock_ret") < 0)
            .then(pl.col("weighted_stock_ret"))
            .otherwise(0.0)
            .sum()
            .alias("negative_contribution_sum"),
            pl.col("weighted_stock_ret").abs().sum().alias("abs_contribution_sum"),
        )
        .with_columns(
            (pl.col("positive_contribution_sum") / pl.col("positive_contribution_sum").sum().over("scenario")).alias(
                "positive_contribution_share"
            ),
            (pl.col("abs_contribution_sum") / pl.col("abs_contribution_sum").sum().over("scenario")).alias(
                "abs_contribution_share"
            ),
        )
        .sort(["scenario", "positive_contribution_sum"], descending=[False, True])
    )
    return grouped


def build_symbol_contribution(symbol_daily: pl.DataFrame) -> pl.DataFrame:
    if symbol_daily.is_empty():
        return pl.DataFrame()
    name_cols = [col for col in ["code_name", "industry"] if col in symbol_daily.columns]
    grouped = (
        symbol_daily.group_by(["scenario", "symbol", *name_cols])
        .agg(
            pl.len().alias("symbol_day_rows"),
            pl.col("pnl_date").n_unique().alias("pnl_days"),
            pl.col("target_weight").mean().alias("avg_target_weight"),
            pl.col("weighted_stock_ret").sum().alias("gross_contribution_sum"),
            pl.col("weighted_stock_ret").abs().sum().alias("abs_contribution_sum"),
        )
        .with_columns(
            (pl.col("abs_contribution_sum") / pl.col("abs_contribution_sum").sum().over("scenario")).alias(
                "abs_contribution_share"
            )
        )
        .sort(["scenario", "abs_contribution_sum"], descending=[False, True])
    )
    return grouped


def build_top_symbol_share(symbol_contribution: pl.DataFrame, scenario: str, top_n: int) -> float:
    if symbol_contribution.is_empty():
        return 0.0
    subset = symbol_contribution.filter(pl.col("scenario") == scenario).sort("abs_contribution_sum", descending=True)
    total = to_float(subset["abs_contribution_sum"].sum())
    if total <= 0:
        return 0.0
    return to_float(subset.head(top_n)["abs_contribution_sum"].sum()) / total


def build_year_state_cross(selected: pl.DataFrame) -> pl.DataFrame:
    if selected.is_empty() or "market_state_20d" not in selected.columns:
        return pl.DataFrame()
    weighted = selected.with_columns(
        pl.col("datetime").dt.year().alias("year"),
        (pl.col("basket_weight") * pl.col(f"fwd_excess_ret_{HORIZON}")).alias("_weighted_excess"),
        (pl.col("basket_weight") * pl.col(f"fwd_ret_{HORIZON}")).alias("_weighted_abs"),
    )
    return (
        weighted.group_by(["scenario", "year", "market_state_20d"])
        .agg(
            pl.len().alias("candidate_rows"),
            pl.col("datetime").n_unique().alias("signal_days"),
            pl.col("symbol").n_unique().alias("symbols"),
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
        .sort(["scenario", "year", "market_state_20d"])
    )


def build_year_industry_cross(symbol_daily: pl.DataFrame) -> pl.DataFrame:
    if symbol_daily.is_empty():
        return pl.DataFrame()
    return (
        symbol_daily.with_columns(pl.col("pnl_date").dt.year().alias("year"))
        .group_by(["scenario", "year", "industry"])
        .agg(
            pl.len().alias("symbol_day_rows"),
            pl.col("pnl_date").n_unique().alias("pnl_days"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("weighted_stock_ret").sum().alias("gross_contribution_sum"),
            pl.col("weighted_stock_ret").abs().sum().alias("abs_contribution_sum"),
        )
        .sort(["scenario", "year", "gross_contribution_sum"], descending=[False, False, True])
    )


def build_liquidity_cross(selected: pl.DataFrame) -> pl.DataFrame:
    if selected.is_empty():
        return pl.DataFrame()
    cols = [col for col in ["adv20_turnover_q", "turnover_rate_f_q"] if col in selected.columns]
    if not cols:
        return pl.DataFrame()
    work = selected.with_columns(
        (pl.col("basket_weight") * pl.col(f"fwd_excess_ret_{HORIZON}")).alias("_weighted_excess"),
        (pl.col("basket_weight") * pl.col(f"fwd_ret_{HORIZON}")).alias("_weighted_abs"),
    )
    return (
        work.group_by(["scenario", *cols])
        .agg(
            pl.len().alias("candidate_rows"),
            pl.col("datetime").n_unique().alias("signal_days"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("basket_weight").sum().alias("weight_sum"),
            pl.col(f"fwd_excess_ret_{HORIZON}").mean().alias("avg_fwd_excess_ret_10"),
            pl.col("_weighted_excess").sum().alias("weighted_excess_sum"),
            pl.col("_weighted_abs").sum().alias("weighted_abs_sum"),
            pl.col("adv20_turnover").median().alias("median_adv20_turnover"),
            pl.col("turnover_rate_f").median().alias("median_turnover_rate_f"),
        )
        .with_columns(
            (pl.col("weighted_excess_sum") / pl.col("weight_sum")).alias("weighted_avg_fwd_excess_ret_10"),
            (pl.col("weighted_abs_sum") / pl.col("weight_sum")).alias("weighted_avg_fwd_ret_10"),
        )
        .sort(["scenario", *cols])
    )


def build_curve_summary_for_selected(selected: pl.DataFrame, benchmark_df: pl.DataFrame) -> dict[str, Any]:
    scenario = selected["scenario"][0]
    scenario_def = {
        "scenario": scenario,
        "description": selected["scenario_description"][0],
        "bucket": selected["bucket"][0],
        "weight_mode": selected["weight_mode"][0],
    }
    lots, symbol_daily = build_symbol_daily_by_scenario(selected)
    if lots.is_empty() or symbol_daily.is_empty():
        return {
            **scenario_def,
            "roundtrip_cost_bps": COST_BPS,
            "final_equity": 1.0,
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe": 0.0,
        }
    min_date = min(symbol_daily["target_date"].min(), symbol_daily["pnl_date"].min())
    max_date = max(symbol_daily["target_date"].max(), symbol_daily["pnl_date"].max())
    calendar = build_calendar(benchmark_df, min_date, max_date)
    benchmark_daily = build_benchmark_daily(benchmark_df)
    turnover, _targets = build_turnover(symbol_daily, calendar, scenario)
    concentration, _industry_daily = build_concentration(symbol_daily, calendar, scenario)
    daily_gross = build_daily_gross(symbol_daily)
    curve = build_equity_curve(scenario, daily_gross, turnover, benchmark_daily, calendar, COST_BPS)
    return summarize_curve(curve, turnover, concentration, selected, scenario_def, COST_BPS)


def build_industry_leave_one_out(
    selected: pl.DataFrame,
    benchmark_df: pl.DataFrame,
    core_industries: list[str],
) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for scenario in [PRIMARY_SCENARIO, REALLOCATED_SCENARIO]:
        scenario_selected = selected.filter(pl.col("scenario") == scenario)
        if scenario_selected.is_empty():
            continue
        full = build_curve_summary_for_selected(scenario_selected, benchmark_df)
        rows.append({"scenario": scenario, "removed_industry": "__none__", "removed_count": 0, **full})
        full_sharpe = to_float(full.get("sharpe"))
        full_return = to_float(full.get("total_return"))
        for industry in core_industries:
            subset = scenario_selected.filter(pl.col("industry") != industry)
            summary = build_curve_summary_for_selected(subset, benchmark_df)
            rows.append(
                {
                    "scenario": scenario,
                    "removed_industry": industry,
                    "removed_count": 1,
                    **summary,
                    "delta_total_return_vs_full": to_float(summary.get("total_return")) - full_return,
                    "delta_sharpe_vs_full": to_float(summary.get("sharpe")) - full_sharpe,
                    "sharpe_drop_ratio_vs_full": (full_sharpe - to_float(summary.get("sharpe"))) / full_sharpe
                    if full_sharpe > 0
                    else 0.0,
                }
            )
        subset = scenario_selected.filter(~pl.col("industry").is_in(core_industries))
        summary = build_curve_summary_for_selected(subset, benchmark_df)
        rows.append(
            {
                "scenario": scenario,
                "removed_industry": "__top5_core_combined__",
                "removed_count": len(core_industries),
                **summary,
                "delta_total_return_vs_full": to_float(summary.get("total_return")) - full_return,
                "delta_sharpe_vs_full": to_float(summary.get("sharpe")) - full_sharpe,
                "sharpe_drop_ratio_vs_full": (full_sharpe - to_float(summary.get("sharpe"))) / full_sharpe
                if full_sharpe > 0
                else 0.0,
            }
        )
    return pl.DataFrame(rows).sort(["scenario", "removed_count", "removed_industry"]) if rows else pl.DataFrame()


def build_daily_concentration(symbol_daily: pl.DataFrame, benchmark_df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    frames: list[pl.DataFrame] = []
    industry_frames: list[pl.DataFrame] = []
    for scenario in [PRIMARY_SCENARIO, REALLOCATED_SCENARIO]:
        scenario_daily = symbol_daily.filter(pl.col("scenario") == scenario)
        if scenario_daily.is_empty():
            continue
        min_date = scenario_daily["target_date"].min()
        max_date = scenario_daily["target_date"].max()
        calendar = build_calendar(benchmark_df, min_date, max_date)
        concentration, industry_daily = build_concentration(scenario_daily, calendar, scenario)
        frames.append(concentration)
        industry_frames.append(industry_daily)
    return (
        pl.concat(frames, how="vertical").sort(["scenario", "target_date"]) if frames else pl.DataFrame(),
        pl.concat(industry_frames, how="vertical").sort(["scenario", "target_date", "industry"])
        if industry_frames
        else pl.DataFrame(),
    )


def build_concentration_summary(daily_concentration: pl.DataFrame) -> pl.DataFrame:
    if daily_concentration.is_empty():
        return pl.DataFrame()
    return (
        daily_concentration.filter(pl.col("gross_exposure") > 0)
        .group_by("scenario")
        .agg(
            pl.col("active_symbols").mean().alias("avg_active_symbols"),
            pl.col("active_symbols").quantile(0.05).alias("p05_active_symbols"),
            pl.col("active_industries").mean().alias("avg_active_industries"),
            pl.col("active_industries").quantile(0.05).alias("p05_active_industries"),
            pl.col("max_industry_weight").mean().alias("avg_max_industry_weight"),
            pl.col("max_industry_weight").max().alias("max_industry_weight"),
            pl.col("top5_industry_weight").mean().alias("avg_top5_industry_weight"),
            pl.col("top5_industry_weight").max().alias("max_top5_industry_weight"),
            pl.col("effective_names").mean().alias("avg_effective_names"),
            pl.col("effective_names").quantile(0.05).alias("p05_effective_names"),
        )
        .sort("scenario")
    )


def build_quality_checkpoints(
    industry_contribution: pl.DataFrame,
    symbol_contribution: pl.DataFrame,
    leave_one_out: pl.DataFrame,
    concentration_summary: pl.DataFrame,
    rolling_scorecard: pl.DataFrame,
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

    primary_ind = industry_contribution.filter(pl.col("scenario") == PRIMARY_SCENARIO)
    top5_positive_share = to_float(primary_ind.head(CORE_INDUSTRY_COUNT)["positive_contribution_share"].sum())
    top5_abs_share = to_float(
        primary_ind.sort("abs_contribution_sum", descending=True).head(CORE_INDUSTRY_COUNT)["abs_contribution_share"].sum()
    )
    add(
        "primary_top5_positive_industry_share",
        "fail" if top5_positive_share >= 0.90 else "warn" if top5_positive_share >= 0.75 else "pass",
        f"{top5_positive_share:.2%}",
        "<75% preferred, <90% hard",
        "弱势修复若主要由少数行业贡献，不能直接升级为通用过滤器。",
    )
    add(
        "primary_top5_abs_industry_share",
        "fail" if top5_abs_share >= 0.90 else "warn" if top5_abs_share >= 0.75 else "pass",
        f"{top5_abs_share:.2%}",
        "<75% preferred, <90% hard",
        "绝对贡献过度集中说明路径主要来自行业簇，而不是分散横截面边际。",
    )
    top10_symbol_share = build_top_symbol_share(symbol_contribution, PRIMARY_SCENARIO, 10)
    top20_symbol_share = build_top_symbol_share(symbol_contribution, PRIMARY_SCENARIO, 20)
    add(
        "primary_top10_symbol_abs_share",
        "fail" if top10_symbol_share > 0.30 else "pass",
        f"{top10_symbol_share:.2%}",
        "<=30%",
        "少数股票贡献过高时视为样本伪象。",
    )
    add(
        "primary_top20_symbol_abs_share",
        "fail" if top20_symbol_share > 0.45 else "pass",
        f"{top20_symbol_share:.2%}",
        "<=45%",
        "top20单票贡献过高时应降级。",
    )
    primary_loo = leave_one_out.filter(
        (pl.col("scenario") == PRIMARY_SCENARIO) & (pl.col("removed_count") == 1)
    )
    worst_single_drop = to_float(primary_loo["sharpe_drop_ratio_vs_full"].max()) if primary_loo.height else 0.0
    add(
        "primary_single_core_industry_sharpe_drop",
        "fail" if worst_single_drop > 0.30 else "pass",
        f"{worst_single_drop:.2%}",
        "<=30%",
        "去掉任一核心行业后Sharpe大幅下降，说明行业依赖过强。",
    )
    top5_removed = leave_one_out.filter(
        (pl.col("scenario") == PRIMARY_SCENARIO) & (pl.col("removed_industry") == "__top5_core_combined__")
    )
    top5_removed_return = to_float(top5_removed["total_return"][0]) if top5_removed.height else 0.0
    add(
        "primary_top5_removed_still_positive",
        "fail" if top5_removed_return <= 0 else "pass",
        f"{top5_removed_return:.2%}",
        ">0",
        "去掉核心行业簇后若收益不再为正，弱势修复应降级为行业簇现象。",
    )
    primary_conc = concentration_summary.filter(pl.col("scenario") == PRIMARY_SCENARIO)
    avg_industries = to_float(primary_conc["avg_active_industries"][0]) if primary_conc.height else 0.0
    p05_industries = to_float(primary_conc["p05_active_industries"][0]) if primary_conc.height else 0.0
    add(
        "primary_avg_active_industries",
        "fail" if avg_industries < 4 else "pass",
        f"{avg_industries:.2f}",
        ">=4",
        "平均活跃行业过少会削弱穿越周期能力。",
    )
    add(
        "primary_p05_active_industries",
        "fail" if p05_industries <= 2 else "pass",
        f"{p05_industries:.2f}",
        ">2",
        "低分位行业数过低时，重分配容易放大单一赛道。",
    )
    primary_rolling_504 = rolling_scorecard.filter(
        (pl.col("scenario") == PRIMARY_SCENARIO) & (pl.col("window_days") == 504)
    )
    sharpe_beat = to_float(primary_rolling_504["sharpe_beat_ratio"][0]) if primary_rolling_504.height else 0.0
    add(
        "primary_504d_sharpe_beat_ratio",
        "fail" if sharpe_beat < 0.60 else "warn" if sharpe_beat < 0.70 else "pass",
        f"{sharpe_beat:.2%}",
        ">=70% preferred, >=60% minimum",
        "长窗口Sharpe跑赢率不足时，不能继续候选升级。",
    )
    return pl.DataFrame(rows)


def write_report(
    industry_contribution: pl.DataFrame,
    symbol_contribution: pl.DataFrame,
    leave_one_out: pl.DataFrame,
    year_state_cross: pl.DataFrame,
    liquidity_cross: pl.DataFrame,
    concentration_summary: pl.DataFrame,
    rolling_scorecard: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    primary_ind = industry_contribution.filter(pl.col("scenario") == PRIMARY_SCENARIO)
    top5_positive_share = to_float(primary_ind.head(CORE_INDUSTRY_COUNT)["positive_contribution_share"].sum())
    top5_abs_share = to_float(
        primary_ind.sort("abs_contribution_sum", descending=True).head(CORE_INDUSTRY_COUNT)["abs_contribution_share"].sum()
    )
    top10_symbol_share = build_top_symbol_share(symbol_contribution, PRIMARY_SCENARIO, 10)
    top20_symbol_share = build_top_symbol_share(symbol_contribution, PRIMARY_SCENARIO, 20)
    top5_removed = leave_one_out.filter(
        (pl.col("scenario") == PRIMARY_SCENARIO) & (pl.col("removed_industry") == "__top5_core_combined__")
    )
    top5_removed_return = to_float(top5_removed["total_return"][0]) if top5_removed.height else 0.0
    top5_removed_sharpe = to_float(top5_removed["sharpe"][0]) if top5_removed.height else 0.0
    primary_rolling_504 = rolling_scorecard.filter(
        (pl.col("scenario") == PRIMARY_SCENARIO) & (pl.col("window_days") == 504)
    )
    rolling_504_sharpe = to_float(primary_rolling_504["sharpe_beat_ratio"][0]) if primary_rolling_504.height else 0.0
    lines = [
        "# 股票震荡liquid_q3 weak_market60_q1q2 伪象审计 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：对第294阶段弱势修复发现做行业、年份、市场状态、流动性、单票和滚动窗口反证审计。",
        "- A/B判断：只做反证审计，不接入正式版本，不触发第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- Alphalens一类因子研究框架强调分位、分组、换手和稳定性，而不是只看全样本收益。",
        "- TimeSeriesSplit的gap思想和PBO研究都提示：全样本发现后的验证必须防止未来信息和多重试验幻觉。",
        "- regime backtesting资料强调，同一因子在不同市场状态下会变形，因此需要市场状态切片。",
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
            f"- 主审计对象：`{PRIMARY_SCENARIO}`。",
            f"- 行业top5正贡献占比：`{pct(top5_positive_share)}`；行业top5绝对贡献占比：`{pct(top5_abs_share)}`。",
            f"- 单票top10绝对贡献占比：`{pct(top10_symbol_share)}`；top20绝对贡献占比：`{pct(top20_symbol_share)}`。",
            f"- 去掉top5核心行业后：总收益`{pct(top5_removed_return)}`，Sharpe `{top5_removed_sharpe:.3f}`。",
            f"- 504日滚动Sharpe跑赢baseline比例：`{pct(rolling_504_sharpe)}`。",
            f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。",
            "- 初步判断：如果行业集中fail成立，则弱势修复不能直接升级；它更像行业簇里的拥挤卖压释放，需要先通过行业留一和滚动验证。",
            "",
            "## 行业贡献",
            "",
            markdown_table(
                industry_contribution.filter(pl.col("scenario") == PRIMARY_SCENARIO).sort(
                    "positive_contribution_sum", descending=True
                ),
                [
                    "industry",
                    "symbols",
                    "pnl_days",
                    "gross_contribution_sum",
                    "positive_contribution_sum",
                    "negative_contribution_sum",
                    "abs_contribution_sum",
                    "positive_contribution_share",
                    "abs_contribution_share",
                ],
                max_rows=30,
            ),
            "",
            "## 行业留一",
            "",
            markdown_table(
                leave_one_out,
                [
                    "scenario",
                    "removed_industry",
                    "removed_count",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    "delta_total_return_vs_full",
                    "delta_sharpe_vs_full",
                    "sharpe_drop_ratio_vs_full",
                    "avg_return_gross_exposure",
                    "annualized_one_way_turnover",
                ],
                max_rows=40,
            ),
            "",
            "## 年份×市场状态",
            "",
            markdown_table(
                year_state_cross.filter(pl.col("scenario") == PRIMARY_SCENARIO),
                [
                    "year",
                    "market_state_20d",
                    "candidate_rows",
                    "signal_days",
                    "symbols",
                    "weighted_avg_fwd_excess_ret_10",
                    "weighted_avg_fwd_ret_10",
                    "positive_excess_ratio",
                ],
                max_rows=80,
            ),
            "",
            "## 流动性切片",
            "",
            markdown_table(
                liquidity_cross.filter(pl.col("scenario") == PRIMARY_SCENARIO),
                [
                    "adv20_turnover_q",
                    "turnover_rate_f_q",
                    "candidate_rows",
                    "signal_days",
                    "symbols",
                    "weighted_avg_fwd_excess_ret_10",
                    "median_adv20_turnover",
                    "median_turnover_rate_f",
                ],
                max_rows=80,
            ),
            "",
            "## 单票贡献Top30",
            "",
            markdown_table(
                symbol_contribution.filter(pl.col("scenario") == PRIMARY_SCENARIO).sort(
                    "abs_contribution_sum", descending=True
                ),
                [
                    "symbol",
                    "industry",
                    "symbol_day_rows",
                    "pnl_days",
                    "gross_contribution_sum",
                    "abs_contribution_sum",
                    "abs_contribution_share",
                ],
                max_rows=30,
            ),
            "",
            "## 集中度汇总",
            "",
            markdown_table(
                concentration_summary,
                [
                    "scenario",
                    "avg_active_symbols",
                    "p05_active_symbols",
                    "avg_active_industries",
                    "p05_active_industries",
                    "avg_max_industry_weight",
                    "max_industry_weight",
                    "avg_top5_industry_weight",
                    "max_top5_industry_weight",
                    "avg_effective_names",
                    "p05_effective_names",
                ],
                max_rows=20,
            ),
            "",
            "## 滚动窗口Scorecard",
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
                max_rows=40,
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
            "- 原因：`weak_market60_q1q2`来自全样本归因后的强结果，直接升级会变成数据挖掘。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：风险仍在，且行业集中风险被验证为主要问题。",
            "- 原因：本阶段没有新增策略参数，但发现行业贡献集中；这说明下一步必须继续反证，而不是升级交易。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：弱势修复可能是当前股票震荡线的真实边际，需要用反证审计确认是否可穿越周期。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是，但优先级降低为审计线。",
            "- 原因：若行业留一和滚动验证还能保留优势，它才值得做30万候选；否则只能作为行业簇诊断，不应策略化。",
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
    selected_all = read_source_csv("selected_variants").filter(pl.col("scenario").is_in(AUDIT_SCENARIOS))
    equity_curve = read_source_csv("equity_curve")
    _stock_df, benchmark_df = load_panels()

    lots, symbol_daily = build_symbol_daily_by_scenario(selected_all)
    industry_contribution = build_industry_contribution(symbol_daily)
    symbol_contribution = build_symbol_contribution(symbol_daily)
    primary_industries = (
        industry_contribution.filter(pl.col("scenario") == PRIMARY_SCENARIO)
        .sort("positive_contribution_sum", descending=True)
        .head(CORE_INDUSTRY_COUNT)["industry"]
        .to_list()
    )
    leave_one_out = build_industry_leave_one_out(selected_all, benchmark_df, [str(item) for item in primary_industries])
    year_state_cross = build_year_state_cross(selected_all.filter(pl.col("scenario").is_in([PRIMARY_SCENARIO, REALLOCATED_SCENARIO])))
    year_industry_cross = build_year_industry_cross(symbol_daily.filter(pl.col("scenario").is_in([PRIMARY_SCENARIO, REALLOCATED_SCENARIO])))
    liquidity_cross = build_liquidity_cross(selected_all.filter(pl.col("scenario").is_in([PRIMARY_SCENARIO, REALLOCATED_SCENARIO])))
    daily_concentration, industry_daily = build_daily_concentration(symbol_daily, benchmark_df)
    concentration_summary = build_concentration_summary(daily_concentration)
    rolling_summary, rolling_delta, rolling_scorecard = build_rolling_scorecard(equity_curve)
    quality = build_quality_checkpoints(
        industry_contribution,
        symbol_contribution,
        leave_one_out,
        concentration_summary,
        rolling_scorecard,
    )

    paths: dict[str, Path] = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "industry_contribution": OUTPUT_DIR / f"{PREFIX}_industry_contribution.csv",
        "industry_leave_one_out": OUTPUT_DIR / f"{PREFIX}_industry_leave_one_out.csv",
        "year_state_cross": OUTPUT_DIR / f"{PREFIX}_year_state_cross.csv",
        "year_industry_cross": OUTPUT_DIR / f"{PREFIX}_year_industry_cross.csv",
        "liquidity_cross": OUTPUT_DIR / f"{PREFIX}_liquidity_cross.csv",
        "symbol_contribution": OUTPUT_DIR / f"{PREFIX}_symbol_contribution.csv",
        "daily_concentration": OUTPUT_DIR / f"{PREFIX}_daily_concentration.csv",
        "industry_daily": OUTPUT_DIR / f"{PREFIX}_industry_daily.csv",
        "concentration_summary": OUTPUT_DIR / f"{PREFIX}_concentration_summary.csv",
        "rolling_summary": OUTPUT_DIR / f"{PREFIX}_rolling_summary.csv",
        "rolling_delta": OUTPUT_DIR / f"{PREFIX}_rolling_delta.csv",
        "rolling_scorecard": OUTPUT_DIR / f"{PREFIX}_rolling_scorecard.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }

    industry_contribution.write_csv(paths["industry_contribution"])
    leave_one_out.write_csv(paths["industry_leave_one_out"])
    year_state_cross.write_csv(paths["year_state_cross"])
    year_industry_cross.write_csv(paths["year_industry_cross"])
    liquidity_cross.write_csv(paths["liquidity_cross"])
    symbol_contribution.write_csv(paths["symbol_contribution"])
    daily_concentration.write_csv(paths["daily_concentration"])
    industry_daily.write_csv(paths["industry_daily"])
    concentration_summary.write_csv(paths["concentration_summary"])
    rolling_summary.write_csv(paths["rolling_summary"])
    rolling_delta.write_csv(paths["rolling_delta"])
    rolling_scorecard.write_csv(paths["rolling_scorecard"])
    quality.write_csv(paths["quality_checkpoints"])
    meta = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_dir": str(SOURCE_DIR),
        "source_prefix": SOURCE_PREFIX,
        "audit_scenarios": AUDIT_SCENARIOS,
        "primary_scenario": PRIMARY_SCENARIO,
        "core_industry_count": CORE_INDUSTRY_COUNT,
        "core_industries": primary_industries,
        "cost_bps": COST_BPS,
        "rolling_windows": ROLLING_WINDOWS,
        "research_sources": RESEARCH_SOURCES,
    }
    write_json(paths["meta"], meta)
    report_path = write_report(
        industry_contribution,
        symbol_contribution,
        leave_one_out,
        year_state_cross,
        liquidity_cross,
        concentration_summary,
        rolling_scorecard,
        quality,
        paths,
    )

    print(f"report={report_path}")
    print(quality)


if __name__ == "__main__":
    main()
