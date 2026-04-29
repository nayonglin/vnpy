from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_layer_tags, load_panels
from analyze_stock_range_reversion_signal_attribution import add_forward_returns, add_price_features, to_float
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import (
    FEATURE,
    HORIZON,
    INITIAL_EQUITY,
    MAX_INDUSTRY_WEIGHT_PER_BASKET,
    MAX_STOCK_WEIGHT_PER_BASKET,
    MIN_INDUSTRY_DAILY_WIDTH,
    NATIVE_RESULTS_DIR,
    TRADING_DAYS,
    add_path_columns,
    build_benchmark_daily,
    build_calendar,
    build_concentration,
    build_daily_gross,
    build_equity_curve,
    build_lots,
    build_symbol_daily,
    build_turnover,
    bucket_expr,
    pct,
    summarize_curve,
    valid_signal_filter,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_momentum_pullback_attribution_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_momentum_pullback_attribution_v1"

LOOKBACKS: tuple[int, ...] = tuple(int(item) for item in os.getenv("MOMENTUM_LOOKBACKS", "60,120").split(",") if item)
SKIP_DAYS: int = int(os.getenv("MOMENTUM_SKIP_DAYS", "10") or 10)
COST_BPS: tuple[float, ...] = tuple(float(item) for item in os.getenv("COST_BPS", "50").split(",") if item)
STRENGTH_TOP_Q: int = int(os.getenv("STRENGTH_TOP_Q", "4") or 4)
STRENGTH_NOT_WEAK_Q: int = int(os.getenv("STRENGTH_NOT_WEAK_Q", "3") or 3)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "QuantConnect momentum short-term reversal strategy",
        "https://www.quantconnect.com/learning/articles/investment-strategy-library/momentum-short-term-reversal-strategy",
    ),
    (
        "Short-Term Reversals and Longer-Term Momentum around the World",
        "https://academic.oup.com/rfs/article/38/12/3673/8240327",
    ),
    (
        "Momentum review after Jegadeesh and Titman",
        "https://link.springer.com/article/10.1007/s11408-022-00417-8",
    ),
    (
        "Improving Cross Sectional Mean Reversion Strategy in Python",
        "https://teddykoker.com/2019/05/improving-cross-sectional-mean-reversion-strategy-in-python/",
    ),
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def t_stat_expr(mean_col: str, std_col: str, days_col: str) -> pl.Expr:
    return (
        pl.when((pl.col(std_col).is_not_null()) & (pl.col(std_col) > 0) & (pl.col(days_col) > 1))
        .then(pl.col(mean_col) / (pl.col(std_col) / pl.col(days_col).sqrt()))
        .otherwise(0.0)
    )


def add_momentum_features(df: pl.DataFrame, benchmark_df: pl.DataFrame) -> pl.DataFrame:
    work = df.sort(["symbol", "datetime"])
    stock_exprs: list[pl.Expr] = []
    for lookback in LOOKBACKS:
        stock_exprs.extend(
            [
                pl.col("close").shift(SKIP_DAYS).over("symbol").alias(f"_close_lag_{SKIP_DAYS}_{lookback}"),
                pl.col("close").shift(SKIP_DAYS + lookback).over("symbol").alias(
                    f"_close_lag_{SKIP_DAYS + lookback}_{lookback}"
                ),
            ]
        )
    work = work.with_columns(stock_exprs)
    for lookback in LOOKBACKS:
        work = work.with_columns(
            (
                pl.col(f"_close_lag_{SKIP_DAYS}_{lookback}")
                / pl.col(f"_close_lag_{SKIP_DAYS + lookback}_{lookback}")
                - 1
            ).alias(f"strength_raw_{lookback}_skip{SKIP_DAYS}")
        )

    bm = benchmark_df.sort("datetime")
    bm_exprs: list[pl.Expr] = []
    for lookback in LOOKBACKS:
        bm_exprs.extend(
            [
                pl.col("close").shift(SKIP_DAYS).alias(f"_bm_close_lag_{SKIP_DAYS}_{lookback}"),
                pl.col("close").shift(SKIP_DAYS + lookback).alias(f"_bm_close_lag_{SKIP_DAYS + lookback}_{lookback}"),
            ]
        )
    bm = bm.with_columns(bm_exprs)
    for lookback in LOOKBACKS:
        bm = bm.with_columns(
            (
                pl.col(f"_bm_close_lag_{SKIP_DAYS}_{lookback}")
                / pl.col(f"_bm_close_lag_{SKIP_DAYS + lookback}_{lookback}")
                - 1
            ).alias(f"bm_strength_{lookback}_skip{SKIP_DAYS}")
        )
    work = work.join(
        bm.select(["datetime", *[f"bm_strength_{lookback}_skip{SKIP_DAYS}" for lookback in LOOKBACKS]]),
        on="datetime",
        how="left",
    )
    for lookback in LOOKBACKS:
        raw_col = f"strength_raw_{lookback}_skip{SKIP_DAYS}"
        peer_sum = f"_industry_strength_sum_{lookback}"
        peer_count = f"_industry_strength_count_{lookback}"
        peer_mean = f"_industry_strength_peer_mean_{lookback}"
        work = (
            work.with_columns(
                (pl.col(raw_col) - pl.col(f"bm_strength_{lookback}_skip{SKIP_DAYS}")).alias(
                    f"strength_market_excess_{lookback}_skip{SKIP_DAYS}"
                ),
                pl.col(raw_col).sum().over(["datetime", "industry"]).alias(peer_sum),
                pl.col(raw_col).count().over(["datetime", "industry"]).alias(peer_count),
            )
            .with_columns(
                pl.when(pl.col(peer_count) > 1)
                .then((pl.col(peer_sum) - pl.col(raw_col)) / (pl.col(peer_count) - 1))
                .otherwise(None)
                .alias(peer_mean)
            )
            .with_columns((pl.col(raw_col) - pl.col(peer_mean)).alias(f"strength_industry_relative_{lookback}_skip{SKIP_DAYS}"))
        )
    return work.drop([col for col in work.columns if col.startswith("_")])


def _rank_quintile(frame: pl.DataFrame, feature: str, over_cols: list[str], min_width: int, out_col: str) -> pl.DataFrame:
    return (
        frame.filter(
            bucket_expr("liquid_q3")
            & pl.col(feature).is_not_null()
            & pl.col(feature).is_finite()
            & pl.col("industry").is_not_null()
        )
        .with_columns(
            pl.col(feature).rank("ordinal").over(over_cols).alias("_rank"),
            pl.len().over(over_cols).alias("_n"),
        )
        .filter(pl.col("_n") >= min_width)
        .with_columns(((((pl.col("_rank") - 1) * 5) / pl.col("_n")).floor().cast(pl.Int64) + 1).clip(1, 5).alias(out_col))
        .select(["datetime", "symbol", out_col])
    )


def add_strength_quintiles(df: pl.DataFrame) -> pl.DataFrame:
    out = df
    for lookback in LOOKBACKS:
        market_col = f"strength_market_excess_{lookback}_skip{SKIP_DAYS}"
        industry_col = f"strength_industry_relative_{lookback}_skip{SKIP_DAYS}"
        out = out.join(
            _rank_quintile(out, market_col, ["datetime"], 50, f"strength_market_q{lookback}"),
            on=["datetime", "symbol"],
            how="left",
        )
        out = out.join(
            _rank_quintile(out, industry_col, ["datetime", "industry"], MIN_INDUSTRY_DAILY_WIDTH, f"strength_industry_q{lookback}"),
            on=["datetime", "symbol"],
            how="left",
        )
    return out


def add_path_shape(df: pl.DataFrame) -> pl.DataFrame:
    work = df.sort(["symbol", "datetime"])
    path_exprs: list[pl.Expr] = []
    for day in range(1, HORIZON + 1):
        path_exprs.append((pl.col("close").shift(-(day + 1)).over("symbol") / pl.col("entry_close") - 1).alias(f"path_close_ret_{day}"))
    return work.with_columns(path_exprs).with_columns(
        pl.max_horizontal([pl.col(f"path_close_ret_{day}") for day in range(1, HORIZON + 1)]).alias("mfe_close_10"),
        pl.min_horizontal([pl.col(f"path_close_ret_{day}") for day in range(1, HORIZON + 1)]).alias("mae_close_10"),
    )


def assign_capped_weights(frame: pl.DataFrame, scenario: str, description: str, reallocate: bool) -> pl.DataFrame:
    if frame.is_empty():
        return frame
    work = frame.drop(
        [
            col
            for col in [
                "candidate_count",
                "selected_industry_count",
                "selected_industry_stock_count",
                "basket_gross_weight",
                "scenario",
                "scenario_description",
                "bucket",
                "weight_mode",
            ]
            if col in frame.columns
        ]
    ).with_columns(
        pl.len().over("datetime").alias("candidate_count"),
        pl.col("industry").n_unique().over("datetime").alias("selected_industry_count"),
        pl.len().over(["datetime", "industry"]).alias("selected_industry_stock_count"),
    )
    if reallocate:
        work = (
            work.with_columns(
                pl.min_horizontal(
                    1.0 / pl.col("selected_industry_count"),
                    pl.lit(MAX_INDUSTRY_WEIGHT_PER_BASKET),
                ).alias("_industry_budget")
            )
            .with_columns(
                pl.min_horizontal(
                    pl.col("_industry_budget") / pl.col("selected_industry_stock_count"),
                    pl.lit(MAX_STOCK_WEIGHT_PER_BASKET),
                ).alias("basket_weight")
            )
            .drop("_industry_budget")
        )
    return work.with_columns(
        pl.col("basket_weight").sum().over("datetime").alias("basket_gross_weight"),
        pl.lit(scenario).alias("scenario"),
        pl.lit(description).alias("scenario_description"),
        pl.lit("liquid_q3").alias("bucket"),
        pl.lit("reallocated_capped" if reallocate else "original_weight_no_realloc").alias("weight_mode"),
    )


def select_current_liquid_q3_candidates(df: pl.DataFrame) -> pl.DataFrame:
    work = df.filter(bucket_expr("liquid_q3") & valid_signal_filter())
    ranked = (
        work.with_columns(
            pl.col(FEATURE).rank("ordinal").over(["datetime", "industry"]).alias("_rank"),
            pl.len().over(["datetime", "industry"]).alias("_industry_width"),
        )
        .filter(pl.col("_industry_width") >= MIN_INDUSTRY_DAILY_WIDTH)
        .with_columns(((((pl.col("_rank") - 1) * 5) / pl.col("_industry_width")).floor().cast(pl.Int64) + 1).clip(1, 5).alias("feature_group"))
        .filter(pl.col("feature_group") == 5)
        .drop("_rank")
    )
    return assign_capped_weights(
        ranked,
        "baseline_liquid_q3_current",
        "当前liquid_q3行业内超跌top组，原始行业/单票上限权重",
        reallocate=True,
    )


def build_variant_selected(base: pl.DataFrame) -> tuple[pl.DataFrame, list[dict[str, Any]]]:
    variants: list[tuple[str, str, pl.Expr, bool]] = [
        (
            "baseline_liquid_q3_current",
            "当前liquid_q3行业内超跌top组",
            pl.lit(True),
            False,
        ),
        (
            "not_weak_market60_q3q5_no_realloc",
            "只保留60日跳10日市场相对强度非弱(q3-q5)，不重分配权重",
            pl.col("strength_market_q60") >= STRENGTH_NOT_WEAK_Q,
            False,
        ),
        (
            "strong_market60_q4q5_no_realloc",
            "只保留60日跳10日市场相对强度强(q4-q5)，不重分配权重",
            pl.col("strength_market_q60") >= STRENGTH_TOP_Q,
            False,
        ),
        (
            "strong_industry60_q4q5_no_realloc",
            "只保留60日跳10日行业相对强度强(q4-q5)，不重分配权重",
            pl.col("strength_industry_q60") >= STRENGTH_TOP_Q,
            False,
        ),
        (
            "weak_market60_q1q2_diagnostic",
            "诊断组：60日跳10日市场相对弱(q1-q2)，不重分配权重",
            pl.col("strength_market_q60") <= 2,
            False,
        ),
        (
            "weak_market60_q1q2_reallocated",
            "诊断组：60日跳10日市场相对弱(q1-q2)，按原行业/单票上限重分配",
            pl.col("strength_market_q60") <= 2,
            True,
        ),
        (
            "weak_industry60_q1q2_diagnostic",
            "诊断组：60日跳10日行业相对弱(q1-q2)，不重分配权重",
            pl.col("strength_industry_q60") <= 2,
            False,
        ),
        (
            "weak_industry60_q1q2_reallocated",
            "诊断组：60日跳10日行业相对弱(q1-q2)，按原行业/单票上限重分配",
            pl.col("strength_industry_q60") <= 2,
            True,
        ),
        (
            "strong_market120_q4q5_no_realloc",
            "只保留120日跳10日市场相对强度强(q4-q5)，不重分配权重",
            pl.col("strength_market_q120") >= STRENGTH_TOP_Q,
            False,
        ),
        (
            "strong_industry120_q4q5_no_realloc",
            "只保留120日跳10日行业相对强度强(q4-q5)，不重分配权重",
            pl.col("strength_industry_q120") >= STRENGTH_TOP_Q,
            False,
        ),
        (
            "weak_market120_q1q2_diagnostic",
            "诊断组：120日跳10日市场相对弱(q1-q2)，不重分配权重",
            pl.col("strength_market_q120") <= 2,
            False,
        ),
        (
            "weak_market120_q1q2_reallocated",
            "诊断组：120日跳10日市场相对弱(q1-q2)，按原行业/单票上限重分配",
            pl.col("strength_market_q120") <= 2,
            True,
        ),
        (
            "weak_industry120_q1q2_diagnostic",
            "诊断组：120日跳10日行业相对弱(q1-q2)，不重分配权重",
            pl.col("strength_industry_q120") <= 2,
            False,
        ),
        (
            "weak_industry120_q1q2_reallocated",
            "诊断组：120日跳10日行业相对弱(q1-q2)，按原行业/单票上限重分配",
            pl.col("strength_industry_q120") <= 2,
            True,
        ),
        (
            "strong_market60_q4q5_reallocated",
            "只保留60日跳10日市场相对强(q4-q5)，按原行业/单票上限重分配",
            pl.col("strength_market_q60") >= STRENGTH_TOP_Q,
            True,
        ),
        (
            "strong_industry60_q4q5_reallocated",
            "只保留60日跳10日行业相对强(q4-q5)，按原行业/单票上限重分配",
            pl.col("strength_industry_q60") >= STRENGTH_TOP_Q,
            True,
        ),
    ]
    frames: list[pl.DataFrame] = []
    scenario_defs: list[dict[str, Any]] = []
    for scenario, description, filter_expr, reallocate in variants:
        selected = base.filter(filter_expr)
        if selected.is_empty():
            continue
        frames.append(assign_capped_weights(selected, scenario, description, reallocate=reallocate))
        scenario_defs.append(
            {
                "scenario": scenario,
                "description": description,
                "bucket": "liquid_q3",
                "weight_mode": "reallocated_capped" if reallocate else "original_weight_no_realloc",
            }
        )
    return pl.concat(frames, how="vertical"), scenario_defs


def build_strength_attribution(selected: pl.DataFrame) -> pl.DataFrame:
    frames: list[pl.DataFrame] = []
    for lookback in LOOKBACKS:
        for scope, q_col, value_col in [
            ("market", f"strength_market_q{lookback}", f"strength_market_excess_{lookback}_skip{SKIP_DAYS}"),
            ("industry", f"strength_industry_q{lookback}", f"strength_industry_relative_{lookback}_skip{SKIP_DAYS}"),
        ]:
            if q_col not in selected.columns:
                continue
            grouped = (
                selected.filter(pl.col(q_col).is_not_null())
                .group_by(q_col)
                .agg(
                    pl.len().alias("candidate_rows"),
                    pl.col("datetime").n_unique().alias("signal_days"),
                    pl.col("symbol").n_unique().alias("symbols"),
                    pl.col(value_col).mean().alias("avg_strength_value"),
                    pl.col("ret_20").mean().alias("avg_recent_ret_20"),
                    pl.col(FEATURE).mean().alias("avg_oversold_score"),
                    pl.col(f"fwd_ret_{HORIZON}").mean().alias("avg_fwd_ret_10"),
                    pl.col(f"fwd_excess_ret_{HORIZON}").mean().alias("avg_fwd_excess_ret_10"),
                    pl.col(f"fwd_excess_ret_{HORIZON}").median().alias("median_fwd_excess_ret_10"),
                    (pl.col(f"fwd_excess_ret_{HORIZON}") > 0).mean().alias("positive_excess_ratio"),
                    pl.col("mfe_close_10").mean().alias("avg_mfe_close_10"),
                    pl.col("mae_close_10").mean().alias("avg_mae_close_10"),
                    pl.col("basket_weight").sum().alias("raw_weight_sum"),
                )
                .rename({q_col: "strength_q"})
                .with_columns(
                    pl.lit(lookback).alias("lookback"),
                    pl.lit(scope).alias("strength_scope"),
                )
            )
            grouped = grouped.join(
                selected.filter(pl.col(q_col).is_not_null())
                .group_by(q_col)
                .agg(pl.col(f"fwd_excess_ret_{HORIZON}").std().alias("fwd_excess_ret_10_std"))
                .rename({q_col: "strength_q"}),
                on="strength_q",
                how="left",
            ).with_columns(t_stat_expr("avg_fwd_excess_ret_10", "fwd_excess_ret_10_std", "signal_days").alias("t_stat_excess_10"))
            frames.append(grouped)
    return pl.concat(frames, how="vertical").sort(["lookback", "strength_scope", "strength_q"]) if frames else pl.DataFrame()


def build_top_bottom_attribution(attr: pl.DataFrame) -> pl.DataFrame:
    if attr.is_empty():
        return pl.DataFrame()
    rows: list[dict[str, Any]] = []
    for key in attr.select(["lookback", "strength_scope"]).unique().iter_rows(named=True):
        subset = attr.filter((pl.col("lookback") == key["lookback"]) & (pl.col("strength_scope") == key["strength_scope"]))
        q1 = subset.filter(pl.col("strength_q") == 1)
        q5 = subset.filter(pl.col("strength_q") == 5)
        weak = subset.filter(pl.col("strength_q") <= 2)
        strong = subset.filter(pl.col("strength_q") >= 4)
        if q1.height and q5.height:
            rows.append(
                {
                    **key,
                    "comparison": "q5_minus_q1",
                    "excess_diff": to_float(q5["avg_fwd_excess_ret_10"][0]) - to_float(q1["avg_fwd_excess_ret_10"][0]),
                    "abs_diff": to_float(q5["avg_fwd_ret_10"][0]) - to_float(q1["avg_fwd_ret_10"][0]),
                    "mae_diff": to_float(q5["avg_mae_close_10"][0]) - to_float(q1["avg_mae_close_10"][0]),
                    "positive_ratio_diff": to_float(q5["positive_excess_ratio"][0]) - to_float(q1["positive_excess_ratio"][0]),
                }
            )
        if weak.height and strong.height:
            rows.append(
                {
                    **key,
                    "comparison": "q4q5_minus_q1q2",
                    "excess_diff": to_float(strong["avg_fwd_excess_ret_10"].mean()) - to_float(weak["avg_fwd_excess_ret_10"].mean()),
                    "abs_diff": to_float(strong["avg_fwd_ret_10"].mean()) - to_float(weak["avg_fwd_ret_10"].mean()),
                    "mae_diff": to_float(strong["avg_mae_close_10"].mean()) - to_float(weak["avg_mae_close_10"].mean()),
                    "positive_ratio_diff": to_float(strong["positive_excess_ratio"].mean()) - to_float(weak["positive_excess_ratio"].mean()),
                }
            )
    return pl.DataFrame(rows).sort(["lookback", "strength_scope", "comparison"]) if rows else pl.DataFrame()


def build_yearly_strength(selected: pl.DataFrame) -> pl.DataFrame:
    frames: list[pl.DataFrame] = []
    for q_col, label in [("strength_market_q60", "market60"), ("strength_industry_q60", "industry60")]:
        if q_col not in selected.columns:
            continue
        frames.append(
            selected.filter(pl.col(q_col).is_not_null())
            .with_columns(pl.col("datetime").dt.year().alias("year"))
            .group_by(["year", q_col])
            .agg(
                pl.len().alias("candidate_rows"),
                pl.col("datetime").n_unique().alias("signal_days"),
                pl.col(f"fwd_excess_ret_{HORIZON}").mean().alias("avg_fwd_excess_ret_10"),
                (pl.col(f"fwd_excess_ret_{HORIZON}") > 0).mean().alias("positive_excess_ratio"),
            )
            .rename({q_col: "strength_q"})
            .with_columns(pl.lit(label).alias("strength_label"))
        )
    return pl.concat(frames, how="vertical").sort(["strength_label", "year", "strength_q"]) if frames else pl.DataFrame()


def run_curve_variants(selected_all: pl.DataFrame, scenario_defs: list[dict[str, Any]], benchmark_df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    lots = build_lots(selected_all)
    symbol_daily = build_symbol_daily(lots)
    benchmark_daily = build_benchmark_daily(benchmark_df)
    all_curves: list[pl.DataFrame] = []
    all_summaries: list[dict[str, Any]] = []
    all_yearly: list[pl.DataFrame] = []
    for scenario in scenario_defs:
        name = scenario["scenario"]
        scenario_symbol_daily = symbol_daily.filter(pl.col("scenario") == name)
        scenario_selected = selected_all.filter(pl.col("scenario") == name)
        if scenario_symbol_daily.is_empty():
            continue
        min_date = min(scenario_symbol_daily["target_date"].min(), scenario_symbol_daily["pnl_date"].min())
        max_date = max(scenario_symbol_daily["target_date"].max(), scenario_symbol_daily["pnl_date"].max())
        calendar = build_calendar(benchmark_df, min_date, max_date)
        turnover, _targets = build_turnover(scenario_symbol_daily, calendar, name)
        concentration, _industry_daily = build_concentration(scenario_symbol_daily, calendar, name)
        daily_gross = build_daily_gross(scenario_symbol_daily)
        for cost_bps in COST_BPS:
            curve = build_equity_curve(name, daily_gross, turnover, benchmark_daily, calendar, cost_bps)
            all_curves.append(curve)
            row = summarize_curve(curve, turnover, concentration, scenario_selected, scenario, cost_bps)
            row["excess_total_return_vs_active_benchmark"] = row["total_return"] - row["benchmark_total_return"]
            row["return_over_max_dd"] = row["total_return"] / abs(row["max_drawdown"]) if row["max_drawdown"] else 0.0
            all_summaries.append(row)
            all_yearly.append(
                curve.with_columns(pl.col("date").dt.year().alias("year"))
                .group_by(["scenario", "roundtrip_cost_bps", "year"])
                .agg(
                    ((1 + pl.col("strategy_daily_ret")).product() - 1).alias("year_return"),
                    pl.col("strategy_daily_ret").mean().alias("avg_daily_ret"),
                    pl.col("strategy_daily_ret").std().alias("std_daily_ret"),
                    pl.col("return_gross_exposure").mean().alias("avg_gross_exposure"),
                    pl.col("one_way_turnover").sum().alias("year_one_way_turnover"),
                )
            )
    return (
        pl.DataFrame(all_summaries).sort(["roundtrip_cost_bps", "scenario"]) if all_summaries else pl.DataFrame(),
        pl.concat(all_curves, how="vertical").sort(["roundtrip_cost_bps", "scenario", "date"]) if all_curves else pl.DataFrame(),
        pl.concat(all_yearly, how="vertical").sort(["scenario", "roundtrip_cost_bps", "year"]) if all_yearly else pl.DataFrame(),
    )


def write_report(
    summary: dict[str, Any],
    strength_attr: pl.DataFrame,
    top_bottom: pl.DataFrame,
    curve_summary: pl.DataFrame,
    yearly_strength: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    baseline = curve_summary.filter(pl.col("scenario") == "baseline_liquid_q3_current")
    original_weight = curve_summary.filter(pl.col("weight_mode") == "original_weight_no_realloc").sort("sharpe", descending=True)
    strong60 = strength_attr.filter(
        (pl.col("lookback") == 60) & (pl.col("strength_scope") == "market") & (pl.col("strength_q") >= 4)
    )
    weak60 = strength_attr.filter(
        (pl.col("lookback") == 60) & (pl.col("strength_scope") == "market") & (pl.col("strength_q") <= 2)
    )
    lines = [
        "# 股票震荡liquid_q3 强势池回撤修复归因 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：强者恒强 + 短期均值回归的信号归因和候选过滤模拟；不是正式交易版本。",
        f"- 固定短期回撤信号：`{FEATURE}`，行业内top quintile，`liquid_q3`池。",
        f"- 中期强度：`{LOOKBACKS}`日收益，跳过最近`{SKIP_DAYS}`日，避免和短期超跌信号重叠。",
        "- A/B判断：信号归因，不接入正式版本，不触发第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 学术和开源/业界样例都支持把中期动量与短期反转分开建模。",
        "- 更稳妥的做法不是追涨，而是在中期强势池里找短期回撤修复。",
        "- 本阶段因此只做双排序归因和过滤模拟，不把强度分数直接加进正式权重。",
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
            f"- 样本日期：`{summary['date_min']}` 到 `{summary['date_max']}`。",
            f"- 当前候选行数：`{summary['baseline_candidate_rows']}`，信号日`{summary['baseline_signal_days']}`，股票数`{summary['baseline_symbol_count']}`。",
            f"- 市场60日强势q4-q5候选10日平均超额：`{pct(to_float(strong60['avg_fwd_excess_ret_10'].mean()) if strong60.height else 0.0)}`。",
            f"- 市场60日弱势q1-q2候选10日平均超额：`{pct(to_float(weak60['avg_fwd_excess_ret_10'].mean()) if weak60.height else 0.0)}`。",
        ]
    )
    if baseline.height:
        row = baseline.row(0, named=True)
        lines.append(
            f"- baseline 50bp：总收益`{pct(row['total_return'])}`，最大回撤`{pct(row['max_drawdown'])}`，Sharpe `{row['sharpe']:.3f}`。"
        )
    if original_weight.height:
        row = original_weight.row(0, named=True)
        lines.append(
            f"- 过滤但不重分配的最高Sharpe诊断组：`{row['scenario']}`，总收益`{pct(row['total_return'])}`，最大回撤`{pct(row['max_drawdown'])}`，Sharpe `{row['sharpe']:.3f}`，平均暴露`{pct(row['avg_return_gross_exposure'])}`。"
        )
    lines.extend(
        [
            "",
            "## 强度分桶归因",
            "",
            markdown_table(
                strength_attr,
                [
                    "lookback",
                    "strength_scope",
                    "strength_q",
                    "candidate_rows",
                    "signal_days",
                    "avg_recent_ret_20",
                    "avg_fwd_excess_ret_10",
                    "positive_excess_ratio",
                    "avg_mfe_close_10",
                    "avg_mae_close_10",
                    "t_stat_excess_10",
                ],
                max_rows=80,
            ),
            "",
            "## 强弱差",
            "",
            markdown_table(top_bottom, ["lookback", "strength_scope", "comparison", "excess_diff", "abs_diff", "mae_diff", "positive_ratio_diff"], max_rows=40)
            if not top_bottom.is_empty()
            else "无数据",
            "",
            "## 过滤曲线对比",
            "",
            markdown_table(
                curve_summary,
                [
                    "scenario",
                    "roundtrip_cost_bps",
                    "total_return",
                    "excess_total_return_vs_active_benchmark",
                    "max_drawdown",
                    "sharpe",
                    "return_over_max_dd",
                    "avg_return_gross_exposure",
                    "annualized_one_way_turnover",
                    "avg_active_symbols_when_active",
                    "avg_active_industries_when_active",
                ],
                max_rows=80,
            ),
            "",
            "## 年度强度归因",
            "",
            markdown_table(yearly_strength, ["strength_label", "year", "strength_q", "candidate_rows", "signal_days", "avg_fwd_excess_ret_10", "positive_excess_ratio"], max_rows=120)
            if not yearly_strength.is_empty()
            else "无数据",
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段使用文献常见的中期动量/短期反转拆分，固定60/120日并跳过最近10日，不按结果反向调窗口。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：谨慎偏否。",
            "- 原因：本阶段只归因和模拟，不进入正式交易；但若直接选择最高Sharpe过滤组，就会有明显数据挖掘风险。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：强势池回撤修复能检验当前均值回归是否被弱势陷阱拖累。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：若强势分桶在多数年份和过滤曲线上同时改善回撤/Sharpe，下一步可做严格滚动验证；否则否决接入。",
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
    stock_df, benchmark_df = load_panels()
    layer_tags = load_layer_tags()
    df = add_path_columns(
        add_path_shape(
            add_strength_quintiles(
                add_momentum_features(
                    add_forward_returns(add_price_features(stock_df), benchmark_df).join(
                        layer_tags, on=["datetime", "symbol"], how="left"
                    ),
                    benchmark_df,
                )
            )
        )
    )
    base_selected = select_current_liquid_q3_candidates(df)
    if base_selected.is_empty():
        raise RuntimeError("No baseline candidates.")
    selected_variants, scenario_defs = build_variant_selected(base_selected)
    strength_attr = build_strength_attribution(base_selected)
    top_bottom = build_top_bottom_attribution(strength_attr)
    yearly_strength = build_yearly_strength(base_selected)
    curve_summary, equity_curve, curve_yearly = run_curve_variants(selected_variants, scenario_defs, benchmark_df)

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "date_min": str(base_selected["datetime"].min()),
        "date_max": str(base_selected["datetime"].max()),
        "feature": FEATURE,
        "horizon": HORIZON,
        "lookbacks": LOOKBACKS,
        "skip_days": SKIP_DAYS,
        "cost_bps": COST_BPS,
        "baseline_candidate_rows": base_selected.height,
        "baseline_signal_days": base_selected["datetime"].n_unique(),
        "baseline_symbol_count": base_selected["symbol"].n_unique(),
        "scenario_count": len(scenario_defs),
        "research_sources": RESEARCH_SOURCES,
    }
    if not curve_summary.is_empty():
        baseline = curve_summary.filter(pl.col("scenario") == "baseline_liquid_q3_current")
        best_original_weight = curve_summary.filter(pl.col("weight_mode") == "original_weight_no_realloc").sort("sharpe", descending=True)
        summary.update(
            {
                "baseline_total_return": to_float(baseline["total_return"][0]) if baseline.height else None,
                "baseline_max_drawdown": to_float(baseline["max_drawdown"][0]) if baseline.height else None,
                "baseline_sharpe": to_float(baseline["sharpe"][0]) if baseline.height else None,
                "best_original_weight_scenario": best_original_weight["scenario"][0] if best_original_weight.height else None,
                "best_original_weight_total_return": to_float(best_original_weight["total_return"][0]) if best_original_weight.height else None,
                "best_original_weight_max_drawdown": to_float(best_original_weight["max_drawdown"][0]) if best_original_weight.height else None,
                "best_original_weight_sharpe": to_float(best_original_weight["sharpe"][0]) if best_original_weight.height else None,
                "best_original_weight_avg_exposure": to_float(best_original_weight["avg_return_gross_exposure"][0]) if best_original_weight.height else None,
            }
        )
    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "strength_attribution": OUTPUT_DIR / f"{PREFIX}_strength_attribution.csv",
        "top_bottom": OUTPUT_DIR / f"{PREFIX}_top_bottom.csv",
        "yearly_strength": OUTPUT_DIR / f"{PREFIX}_yearly_strength.csv",
        "curve_summary": OUTPUT_DIR / f"{PREFIX}_curve_summary.csv",
        "equity_curve": OUTPUT_DIR / f"{PREFIX}_equity_curve.csv",
        "curve_yearly": OUTPUT_DIR / f"{PREFIX}_curve_yearly.csv",
        "selected_variants": OUTPUT_DIR / f"{PREFIX}_selected_variants.csv",
        "base_selected": OUTPUT_DIR / f"{PREFIX}_base_selected.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    strength_attr.write_csv(paths["strength_attribution"])
    top_bottom.write_csv(paths["top_bottom"])
    yearly_strength.write_csv(paths["yearly_strength"])
    curve_summary.write_csv(paths["curve_summary"])
    equity_curve.write_csv(paths["equity_curve"])
    curve_yearly.write_csv(paths["curve_yearly"])
    selected_variants.write_csv(paths["selected_variants"])
    base_selected.write_csv(paths["base_selected"])
    write_json(paths["summary"], summary)
    write_json(
        paths["meta"],
        {
            **summary,
            "scenario_defs": scenario_defs,
            "note": "Attribution only; no live target or order generation changed.",
        },
    )
    report_path = write_report(summary, strength_attr, top_bottom, curve_summary, yearly_strength, paths)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
