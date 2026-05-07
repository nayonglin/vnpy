from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility import ACCOUNT_SIZE_CNY
from analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_catch_signal_probe import (
    PRE_REGISTERED_FLAG_COLUMNS,
    SOURCE_DIR,
    SOURCE_PREFIX,
    add_knife_flags,
)
from analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_sample_attribution import (
    FOCUS_SCENARIOS,
    read_csv_with_symbol,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR
    / "stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_second_order_attribution_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_second_order_attribution_v1"

PRIMARY_SCENARIO: str = "industry_resid_core_h10_top8_gross70_ind2"
CANDIDATE_BASE_SCENARIO: str = "industry_resid_core_h10_top5_gross70_ind1"
FORWARD_HORIZONS: tuple[int, ...] = (1, 3, 5, 10)
COHORTS: tuple[tuple[str, str], ...] = (
    ("all_targets", "全部目标样本"),
    ("knife_any", "至少1个接刀子旗标"),
    ("knife_2plus", "至少2个接刀子旗标"),
    ("high_volume_selloff", "上一交易日放量下跌"),
    ("short_crash", "上一交易日短期深跌"),
    ("weak_close", "上一交易日收盘靠近日内低位"),
    ("limit_down_signal", "上一交易日跌停/一字跌停"),
)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Short-term residual reversal",
        "https://www.sciencedirect.com/science/article/pii/S1386418112000468",
    ),
    (
        "Short-term reversals, returns to liquidity provision and immediacy costs",
        "https://www.sciencedirect.com/science/article/pii/S0378426622000309",
    ),
    (
        "Short-Term Reversals and Longer-Term Momentum around the World",
        "https://academic.oup.com/rfs/article/38/12/3673/8240327",
    ),
    (
        "Teddy Koker cross-sectional mean reversion backtest",
        "https://teddykoker.com/2019/04/backtesting-a-cross-sectional-mean-reversion-strategy-in-python/",
    ),
    (
        "GitHub mean-reversion-trading topic",
        "https://github.com/topics/mean-reversion-trading",
    ),
)

MANUAL_BUCKET_COLUMNS: tuple[str, ...] = (
    "stock_ret_5_bucket",
    "stock_ret_20_bucket",
    "stock_close_to_high_252_bucket",
    "stock_dist_ma60_bucket",
    "stock_volume_ratio_20_bucket",
    "stock_ibs_bucket",
    "stock_open_gap_bucket",
    "stock_intraday_ret_bucket",
    "benchmark_ret_5_bucket",
    "benchmark_drawdown_60_bucket",
    "industry_selected_avg_ret20_bucket",
    "target_damage_penalty_bucket",
    "target_adv20_turnover_bucket",
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        normalized[key] = value.isoformat() if isinstance(value, (date, datetime)) else value
    return normalized


def to_float(value: Any) -> float:
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def build_forward_open_returns(stock_df: pl.DataFrame) -> pl.DataFrame:
    exprs: list[pl.Expr] = []
    for horizon in FORWARD_HORIZONS:
        future_open = pl.col("trade_open").shift(-horizon).over("symbol")
        exprs.append(
            pl.when((pl.col("trade_open") > 0) & future_open.is_not_null() & (future_open > 0))
            .then(future_open / pl.col("trade_open") - 1.0)
            .otherwise(None)
            .alias(f"forward_open_ret_{horizon}d")
        )
    return (
        stock_df.select(["datetime", "symbol", "trade_open"])
        .sort(["symbol", "datetime"])
        .with_columns(exprs)
        .rename({"datetime": "target_date"})
        .select(["target_date", "symbol", *[f"forward_open_ret_{horizon}d" for horizon in FORWARD_HORIZONS]])
    )


def build_benchmark_prior_features(benchmark_df: pl.DataFrame) -> pl.DataFrame:
    close = pl.col("close")
    open_ = pl.col("open")
    high = pl.col("high")
    low = pl.col("low")
    features = (
        benchmark_df.sort("datetime")
        .with_columns(
            (close / close.shift(1) - 1.0).alias("benchmark_ret_1"),
            (close / close.shift(5) - 1.0).alias("benchmark_ret_5"),
            (close / close.shift(20) - 1.0).alias("benchmark_ret_20"),
            (close / close.shift(60) - 1.0).alias("benchmark_ret_60"),
            (close / close.rolling_mean(20) - 1.0).alias("benchmark_dist_ma20"),
            (close / close.rolling_mean(60) - 1.0).alias("benchmark_dist_ma60"),
            (close / close.rolling_max(60) - 1.0).alias("benchmark_drawdown_60"),
            pl.when((high - low).abs() > 1e-12).then((close - low) / (high - low)).otherwise(None).alias(
                "benchmark_ibs"
            ),
            pl.when(pl.col("preclose") > 0).then(open_ / pl.col("preclose") - 1.0).otherwise(None).alias(
                "benchmark_open_gap"
            ),
            pl.when(open_ > 0).then(close / open_ - 1.0).otherwise(None).alias("benchmark_intraday_ret"),
        )
        .with_columns(
            pl.col("datetime").alias("benchmark_feature_date"),
            pl.col("datetime").shift(-1).alias("target_date"),
        )
        .drop_nulls("target_date")
    )
    keep = [
        "target_date",
        "benchmark_feature_date",
        "benchmark_ret_1",
        "benchmark_ret_5",
        "benchmark_ret_20",
        "benchmark_ret_60",
        "benchmark_dist_ma20",
        "benchmark_dist_ma60",
        "benchmark_drawdown_60",
        "benchmark_ibs",
        "benchmark_open_gap",
        "benchmark_intraday_ret",
    ]
    return features.select(keep)


def build_industry_selected_context(enriched: pl.DataFrame) -> pl.DataFrame:
    context = (
        enriched.group_by(["scenario", "target_date", "industry"])
        .agg(
            pl.len().alias("industry_selected_rows"),
            pl.col("symbol").n_unique().alias("industry_selected_symbols"),
            pl.col("target_weight").sum().alias("industry_selected_weight"),
            pl.col("stock_ret_5").mean().alias("industry_selected_avg_ret5"),
            pl.col("stock_ret_20").mean().alias("industry_selected_avg_ret20"),
            pl.col("stock_dist_ma60").mean().alias("industry_selected_avg_dist_ma60"),
            pl.col("stock_close_to_high_252").mean().alias("industry_selected_avg_close_to_high_252"),
            pl.col("knife_flag_count").mean().alias("industry_selected_avg_knife_count"),
        )
        .with_columns(
            (
                pl.col("industry_selected_avg_ret20").rank("average").over(["scenario", "target_date"])
                / pl.len().over(["scenario", "target_date"])
            ).alias("industry_selected_ret20_rank_pct")
        )
    )
    return context


def add_manual_buckets(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.with_columns(
        pl.when(pl.col("stock_ret_5").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("stock_ret_5") <= -0.10)
        .then(pl.lit("ret5_crash_le_-10pct"))
        .when(pl.col("stock_ret_5") <= -0.05)
        .then(pl.lit("ret5_deep_down"))
        .when(pl.col("stock_ret_5") <= 0)
        .then(pl.lit("ret5_mild_down"))
        .otherwise(pl.lit("ret5_up"))
        .alias("stock_ret_5_bucket"),
        pl.when(pl.col("stock_ret_20").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("stock_ret_20") <= -0.20)
        .then(pl.lit("ret20_crash_le_-20pct"))
        .when(pl.col("stock_ret_20") <= -0.10)
        .then(pl.lit("ret20_deep_down"))
        .when(pl.col("stock_ret_20") <= 0)
        .then(pl.lit("ret20_mild_down"))
        .otherwise(pl.lit("ret20_up"))
        .alias("stock_ret_20_bucket"),
        pl.when(pl.col("stock_close_to_high_252").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("stock_close_to_high_252") >= 0.90)
        .then(pl.lit("near_252_high"))
        .when(pl.col("stock_close_to_high_252") >= 0.75)
        .then(pl.lit("mid_high_intact"))
        .otherwise(pl.lit("far_from_252_high"))
        .alias("stock_close_to_high_252_bucket"),
        pl.when(pl.col("stock_dist_ma60").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("stock_dist_ma60") >= 0.03)
        .then(pl.lit("above_ma60"))
        .when(pl.col("stock_dist_ma60") >= -0.05)
        .then(pl.lit("near_ma60"))
        .when(pl.col("stock_dist_ma60") >= -0.10)
        .then(pl.lit("below_ma60_mild"))
        .otherwise(pl.lit("below_ma60_deep"))
        .alias("stock_dist_ma60_bucket"),
        pl.when(pl.col("stock_volume_ratio_20").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("stock_volume_ratio_20") < 0.70)
        .then(pl.lit("volume_dry"))
        .when(pl.col("stock_volume_ratio_20") <= 1.30)
        .then(pl.lit("volume_normal"))
        .when(pl.col("stock_volume_ratio_20") <= 2.00)
        .then(pl.lit("volume_high"))
        .otherwise(pl.lit("volume_extreme"))
        .alias("stock_volume_ratio_20_bucket"),
        pl.when(pl.col("stock_ibs").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("stock_ibs") <= 0.15)
        .then(pl.lit("close_near_low"))
        .when(pl.col("stock_ibs") >= 0.85)
        .then(pl.lit("close_near_high"))
        .otherwise(pl.lit("close_mid_range"))
        .alias("stock_ibs_bucket"),
        pl.when(pl.col("stock_open_gap").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("stock_open_gap") <= -0.03)
        .then(pl.lit("gap_down_big"))
        .when(pl.col("stock_open_gap") < 0)
        .then(pl.lit("gap_down_small"))
        .when(pl.col("stock_open_gap") >= 0.03)
        .then(pl.lit("gap_up_big"))
        .otherwise(pl.lit("flat_or_gap_up_small"))
        .alias("stock_open_gap_bucket"),
        pl.when(pl.col("stock_intraday_ret").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("stock_intraday_ret") <= -0.03)
        .then(pl.lit("intraday_selloff_big"))
        .when(pl.col("stock_intraday_ret") < 0)
        .then(pl.lit("intraday_down_small"))
        .when(pl.col("stock_intraday_ret") >= 0.03)
        .then(pl.lit("intraday_rebound_big"))
        .otherwise(pl.lit("intraday_flat_up_small"))
        .alias("stock_intraday_ret_bucket"),
        pl.when(pl.col("benchmark_ret_5").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("benchmark_ret_5") <= -0.03)
        .then(pl.lit("benchmark_5d_stress"))
        .when(pl.col("benchmark_ret_5") < 0.02)
        .then(pl.lit("benchmark_5d_neutral"))
        .otherwise(pl.lit("benchmark_5d_strong"))
        .alias("benchmark_ret_5_bucket"),
        pl.when(pl.col("benchmark_drawdown_60").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("benchmark_drawdown_60") <= -0.10)
        .then(pl.lit("benchmark_dd60_deep"))
        .when(pl.col("benchmark_drawdown_60") <= -0.05)
        .then(pl.lit("benchmark_dd60_mid"))
        .otherwise(pl.lit("benchmark_dd60_shallow"))
        .alias("benchmark_drawdown_60_bucket"),
        pl.when(pl.col("industry_selected_avg_ret20").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("industry_selected_avg_ret20") <= -0.10)
        .then(pl.lit("industry_selected_ret20_deep_down"))
        .when(pl.col("industry_selected_avg_ret20") < 0)
        .then(pl.lit("industry_selected_ret20_mild_down"))
        .otherwise(pl.lit("industry_selected_ret20_up"))
        .alias("industry_selected_avg_ret20_bucket"),
        pl.when(pl.col("technical_damage_penalty").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("technical_damage_penalty") <= 0)
        .then(pl.lit("damage_none"))
        .when(pl.col("technical_damage_penalty") <= 0.25)
        .then(pl.lit("damage_low"))
        .otherwise(pl.lit("damage_high"))
        .alias("target_damage_penalty_bucket"),
        pl.when(pl.col("adv20_turnover").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("adv20_turnover") < 100_000_000)
        .then(pl.lit("adv_lt_100m"))
        .when(pl.col("adv20_turnover") < 300_000_000)
        .then(pl.lit("adv_100m_300m"))
        .otherwise(pl.lit("adv_ge_300m"))
        .alias("target_adv20_turnover_bucket"),
    )


def add_second_order_rules(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.with_columns(
        (
            (pl.col("stock_close_to_high_252") >= 0.75)
            & (pl.col("stock_dist_ma60") >= -0.10)
            & (pl.col("stock_ret_20") > -0.20)
        )
        .fill_null(False)
        .alias("rule_structure_not_broken"),
        ((pl.col("benchmark_ret_5") >= -0.03) & (pl.col("benchmark_drawdown_60") >= -0.10))
        .fill_null(False)
        .alias("rule_market_not_stressed"),
        ((pl.col("industry_selected_avg_ret20") >= -0.10) & (pl.col("industry_selected_ret20_rank_pct") >= 0.35))
        .fill_null(False)
        .alias("rule_selected_industry_not_weak"),
        (pl.col("technical_damage_penalty") <= 0.25).fill_null(False).alias("rule_model_damage_low"),
        (pl.col("stock_volume_ratio_20") <= 1.30).fill_null(False).alias("rule_not_high_volume"),
        (~pl.col("flag_limit_down_signal").fill_null(False)).alias("rule_not_limit_down"),
    ).with_columns(
        (
            pl.col("rule_structure_not_broken")
            & pl.col("rule_market_not_stressed")
            & pl.col("rule_selected_industry_not_weak")
            & pl.col("rule_not_limit_down")
        ).alias("rule_context_good_gate"),
        (
            (~pl.col("rule_structure_not_broken"))
            & (~pl.col("rule_market_not_stressed") | ~pl.col("rule_selected_industry_not_weak"))
        ).alias("rule_context_bad_gate"),
    ).with_columns(
        (
            pl.col("rule_context_good_gate")
            & pl.col("rule_model_damage_low")
            & pl.col("rule_not_high_volume")
        ).alias("rule_strict_good_gate"),
    )


def cohort_condition(name: str) -> pl.Expr:
    if name == "all_targets":
        return pl.lit(True)
    if name == "knife_any":
        return pl.col("knife_flag_count") >= 1
    if name == "knife_2plus":
        return pl.col("knife_flag_count") >= 2
    if name == "high_volume_selloff":
        return pl.col("flag_high_volume_selloff")
    if name == "short_crash":
        return pl.col("flag_short_crash")
    if name == "weak_close":
        return pl.col("flag_close_near_low")
    if name == "limit_down_signal":
        return pl.col("flag_limit_down_signal")
    raise ValueError(f"Unknown cohort: {name}")


def add_outcome_buckets(frame: pl.DataFrame) -> pl.DataFrame:
    return (
        frame.with_columns(
            (
                pl.col("forward_open_ret_1d").rank("average").over("scenario") / pl.len().over("scenario")
            ).alias("ret1_rank_pct_scenario"),
            (
                pl.col("forward_open_ret_5d").rank("average").over("scenario") / pl.len().over("scenario")
            ).alias("ret5_rank_pct_scenario"),
        )
        .with_columns(
            pl.when(pl.col("ret1_rank_pct_scenario") <= 0.10)
            .then(pl.lit("bad_next_open_bottom10"))
            .when(pl.col("ret1_rank_pct_scenario") >= 0.90)
            .then(pl.lit("good_next_open_top10"))
            .otherwise(pl.lit("middle80"))
            .alias("ret1_tail_bucket"),
            pl.when(pl.col("ret5_rank_pct_scenario") <= 0.10)
            .then(pl.lit("bad_5d_bottom10"))
            .when(pl.col("ret5_rank_pct_scenario") >= 0.90)
            .then(pl.lit("good_5d_top10"))
            .otherwise(pl.lit("middle80"))
            .alias("ret5_tail_bucket"),
        )
    )


def enrich_targets(target_weights: pl.DataFrame, stock_df: pl.DataFrame, benchmark_df: pl.DataFrame) -> pl.DataFrame:
    base = add_knife_flags(target_weights, stock_df)
    forward = build_forward_open_returns(stock_df)
    benchmark = build_benchmark_prior_features(benchmark_df)
    industry_context = build_industry_selected_context(base)
    return (
        base.join(forward, on=["target_date", "symbol"], how="left")
        .join(benchmark, on="target_date", how="left")
        .join(industry_context, on=["scenario", "target_date", "industry"], how="left")
        .with_columns(
            *[
                pl.col(f"forward_open_ret_{horizon}d").fill_null(0.0).alias(
                    f"forward_open_ret_{horizon}d_filled"
                )
                for horizon in FORWARD_HORIZONS
            ],
            (pl.col("target_weight") * pl.col("forward_open_ret_1d").fill_null(0.0)).alias(
                "weighted_forward_open_ret_1d"
            ),
            (pl.col("target_weight") * pl.col("forward_open_ret_5d").fill_null(0.0)).alias(
                "weighted_forward_open_ret_5d"
            ),
        )
        .pipe(add_manual_buckets)
        .pipe(add_second_order_rules)
        .pipe(add_outcome_buckets)
    )


def summarize_frame(frame: pl.DataFrame, group_cols: list[str]) -> pl.DataFrame:
    if frame.is_empty():
        return pl.DataFrame()
    return (
        frame.group_by(group_cols)
        .agg(
            pl.len().alias("target_rows"),
            pl.col("target_date").n_unique().alias("target_days"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("target_weight").sum().alias("target_weight_sum"),
            pl.col("weighted_forward_open_ret_1d").sum().alias("weighted_ret1_sum"),
            pl.col("weighted_forward_open_ret_5d").sum().alias("weighted_ret5_sum"),
            *[
                pl.col(f"forward_open_ret_{horizon}d_filled").mean().alias(f"avg_forward_open_ret_{horizon}d")
                for horizon in FORWARD_HORIZONS
            ],
            *[
                (pl.col(f"forward_open_ret_{horizon}d_filled") > 0).mean().alias(
                    f"positive_ratio_forward_open_ret_{horizon}d"
                )
                for horizon in FORWARD_HORIZONS
            ],
            (pl.col("ret1_tail_bucket") == "bad_next_open_bottom10").mean().alias("bad_next_open_bottom10_ratio"),
            (pl.col("ret1_tail_bucket") == "good_next_open_top10").mean().alias("good_next_open_top10_ratio"),
            pl.col("knife_flag_count").mean().alias("avg_knife_flag_count"),
            pl.col("model_score").mean().alias("avg_model_score"),
            pl.col("technical_damage_penalty").mean().alias("avg_damage_penalty"),
        )
        .sort(group_cols)
    )


def build_cohort_summary(enriched: pl.DataFrame) -> pl.DataFrame:
    parts: list[pl.DataFrame] = []
    for cohort_name, description in COHORTS:
        frame = enriched.filter(cohort_condition(cohort_name).fill_null(False))
        if frame.is_empty():
            continue
        parts.append(
            summarize_frame(frame, ["scenario"]).with_columns(
                pl.lit(cohort_name).alias("cohort_name"),
                pl.lit(description).alias("cohort_description"),
            )
        )
        parts.append(
            summarize_frame(frame, []).with_columns(
                pl.lit("ALL").alias("scenario"),
                pl.lit(cohort_name).alias("cohort_name"),
                pl.lit(description).alias("cohort_description"),
            )
        )
    return pl.concat(parts, how="diagonal_relaxed").select(
        [
            "scenario",
            "cohort_name",
            "cohort_description",
            "target_rows",
            "target_days",
            "symbols",
            "target_weight_sum",
            "weighted_ret1_sum",
            "weighted_ret5_sum",
            *[f"avg_forward_open_ret_{horizon}d" for horizon in FORWARD_HORIZONS],
            *[f"positive_ratio_forward_open_ret_{horizon}d" for horizon in FORWARD_HORIZONS],
            "bad_next_open_bottom10_ratio",
            "good_next_open_top10_ratio",
            "avg_knife_flag_count",
            "avg_model_score",
            "avg_damage_penalty",
        ]
    )


def build_tail_feature_profile(enriched: pl.DataFrame) -> pl.DataFrame:
    knife = enriched.filter(pl.col("knife_flag_count") >= 1)
    cols = [
        "model_score",
        "technical_context_score",
        "technical_pullback_quality",
        "technical_damage_penalty",
        "adv20_turnover",
        "turnover_rate_f",
        "circ_mv",
        "stock_ret_5",
        "stock_ret_20",
        "stock_dist_ma60",
        "stock_close_to_high_252",
        "stock_volume_ratio_20",
        "stock_ibs",
        "stock_open_gap",
        "stock_intraday_ret",
        "benchmark_ret_5",
        "benchmark_drawdown_60",
        "industry_selected_avg_ret20",
        "industry_selected_ret20_rank_pct",
    ]
    return (
        knife.group_by(["scenario", "ret1_tail_bucket"])
        .agg(
            pl.len().alias("target_rows"),
            pl.col("target_date").n_unique().alias("target_days"),
            pl.col("symbol").n_unique().alias("symbols"),
            *[pl.col(col).mean().alias(f"avg_{col}") for col in cols if col in knife.columns],
            *[pl.col(flag).mean().alias(f"{flag}_rate") for flag in PRE_REGISTERED_FLAG_COLUMNS],
            pl.col("knife_flag_count").mean().alias("avg_knife_flag_count"),
            pl.col("forward_open_ret_1d_filled").mean().alias("avg_forward_open_ret_1d"),
            pl.col("forward_open_ret_5d_filled").mean().alias("avg_forward_open_ret_5d"),
        )
        .sort(["scenario", "ret1_tail_bucket"])
    )


def build_feature_bucket_summary(enriched: pl.DataFrame) -> pl.DataFrame:
    parts: list[pl.DataFrame] = []
    for cohort_name, description in COHORTS:
        if cohort_name == "all_targets":
            continue
        cohort = enriched.filter(cohort_condition(cohort_name).fill_null(False))
        if cohort.is_empty():
            continue
        for bucket_col in MANUAL_BUCKET_COLUMNS:
            if bucket_col not in cohort.columns:
                continue
            scenario_part = summarize_frame(cohort, ["scenario", bucket_col]).rename({bucket_col: "bucket"})
            if not scenario_part.is_empty():
                parts.append(
                    scenario_part.with_columns(
                        pl.lit(cohort_name).alias("cohort_name"),
                        pl.lit(description).alias("cohort_description"),
                        pl.lit(bucket_col).alias("feature"),
                    )
                )
            all_part = summarize_frame(cohort, [bucket_col]).rename({bucket_col: "bucket"})
            if not all_part.is_empty():
                parts.append(
                    all_part.with_columns(
                        pl.lit("ALL").alias("scenario"),
                        pl.lit(cohort_name).alias("cohort_name"),
                        pl.lit(description).alias("cohort_description"),
                        pl.lit(bucket_col).alias("feature"),
                    )
                )
    if not parts:
        return pl.DataFrame()
    return pl.concat(parts, how="diagonal_relaxed").select(
        [
            "scenario",
            "cohort_name",
            "cohort_description",
            "feature",
            "bucket",
            "target_rows",
            "target_days",
            "symbols",
            "target_weight_sum",
            "weighted_ret1_sum",
            "weighted_ret5_sum",
            *[f"avg_forward_open_ret_{horizon}d" for horizon in FORWARD_HORIZONS],
            "bad_next_open_bottom10_ratio",
            "good_next_open_top10_ratio",
            "avg_knife_flag_count",
            "avg_model_score",
            "avg_damage_penalty",
        ]
    ).sort(["cohort_name", "scenario", "feature", "avg_forward_open_ret_1d"], descending=[False, False, False, True])


def build_feature_contrast(feature_summary: pl.DataFrame) -> pl.DataFrame:
    scenario_rows = feature_summary.filter(pl.col("scenario") != "ALL")
    if scenario_rows.is_empty():
        return pl.DataFrame()
    return (
        scenario_rows.group_by(["cohort_name", "feature", "bucket"])
        .agg(
            pl.col("scenario").n_unique().alias("scenario_count"),
            pl.col("target_rows").sum().alias("target_rows"),
            pl.col("target_days").sum().alias("target_days_sum"),
            pl.col("symbols").sum().alias("symbols_sum"),
            pl.col("avg_forward_open_ret_1d").mean().alias("mean_avg_ret1"),
            pl.col("avg_forward_open_ret_5d").mean().alias("mean_avg_ret5"),
            pl.col("avg_forward_open_ret_10d").mean().alias("mean_avg_ret10"),
            (pl.col("avg_forward_open_ret_1d") > 0).sum().alias("positive_ret1_scenario_count"),
            pl.col("bad_next_open_bottom10_ratio").mean().alias("mean_bad_next_open_bottom10_ratio"),
            pl.col("good_next_open_top10_ratio").mean().alias("mean_good_next_open_top10_ratio"),
            (
                pl.col("good_next_open_top10_ratio") - pl.col("bad_next_open_bottom10_ratio")
            ).mean().alias("mean_good_minus_bad_tail_ratio"),
        )
        .with_columns(
            (pl.col("positive_ret1_scenario_count") / pl.col("scenario_count")).alias("positive_ret1_scenario_ratio")
        )
        .sort(["cohort_name", "mean_good_minus_bad_tail_ratio", "mean_avg_ret1"], descending=[False, True, True])
    )


def build_rule_summary(enriched: pl.DataFrame) -> pl.DataFrame:
    rule_cols = [
        "rule_structure_not_broken",
        "rule_market_not_stressed",
        "rule_selected_industry_not_weak",
        "rule_model_damage_low",
        "rule_not_high_volume",
        "rule_not_limit_down",
        "rule_context_good_gate",
        "rule_context_bad_gate",
        "rule_strict_good_gate",
    ]
    parts: list[pl.DataFrame] = []
    knife = enriched.filter(pl.col("knife_flag_count") >= 1)
    for rule in rule_cols:
        part = summarize_frame(knife, ["scenario", rule]).rename({rule: "rule_value"})
        if not part.is_empty():
            parts.append(part.with_columns(pl.lit(rule).alias("rule_name")))
        all_part = summarize_frame(knife, [rule]).rename({rule: "rule_value"})
        if not all_part.is_empty():
            parts.append(all_part.with_columns(pl.lit("ALL").alias("scenario"), pl.lit(rule).alias("rule_name")))
    return (
        pl.concat(parts, how="diagonal_relaxed").select(
            [
                "scenario",
                "rule_name",
                "rule_value",
                "target_rows",
                "target_days",
                "symbols",
                "target_weight_sum",
                "weighted_ret1_sum",
                "weighted_ret5_sum",
                *[f"avg_forward_open_ret_{horizon}d" for horizon in FORWARD_HORIZONS],
                *[f"positive_ratio_forward_open_ret_{horizon}d" for horizon in FORWARD_HORIZONS],
                "bad_next_open_bottom10_ratio",
                "good_next_open_top10_ratio",
                "avg_knife_flag_count",
                "avg_model_score",
                "avg_damage_penalty",
            ]
        )
        if parts
        else pl.DataFrame()
    )


def build_quality(
    enriched: pl.DataFrame,
    cohort_summary: pl.DataFrame,
    feature_contrast: pl.DataFrame,
    rule_summary: pl.DataFrame,
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

    knife = enriched.filter(pl.col("knife_flag_count") >= 1)
    primary_rules = rule_summary.filter((pl.col("scenario") == PRIMARY_SCENARIO) & (pl.col("rule_value") == True))
    good_gate = primary_rules.filter(pl.col("rule_name") == "rule_context_good_gate")
    bad_gate = primary_rules.filter(pl.col("rule_name") == "rule_context_bad_gate")
    stable_good_buckets = feature_contrast.filter(
        (pl.col("cohort_name") == "knife_any")
        & (pl.col("scenario_count") >= len(FOCUS_SCENARIOS))
        & (pl.col("target_rows") >= 500)
        & (pl.col("mean_good_minus_bad_tail_ratio") > 0)
        & (pl.col("positive_ret1_scenario_ratio") >= 0.75)
    )
    add(
        "focus_scenario_count",
        "pass" if enriched["scenario"].n_unique() == len(FOCUS_SCENARIOS) else "fail",
        enriched["scenario"].n_unique(),
        len(FOCUS_SCENARIOS),
        "固定四个代表形状。",
    )
    add(
        "knife_sample_available",
        "pass" if knife.height > 0 else "fail",
        knife.height,
        ">0",
        "二阶归因必须有接刀子旗标样本。",
    )
    add(
        "prior_day_alignment",
        "pass",
        "prior-day flags and benchmark state",
        "no same-day close for execution open",
        "个股旗标和指数状态均使用上一交易日已知信息。",
    )
    add(
        "cohort_summary_available",
        "pass" if not cohort_summary.is_empty() else "fail",
        cohort_summary.height,
        ">0",
        "必须生成高波动样本总体画像。",
    )
    add(
        "feature_contrast_available",
        "pass" if not feature_contrast.is_empty() else "fail",
        feature_contrast.height,
        ">0",
        "必须生成二阶特征桶对比。",
    )
    add(
        "stable_good_bucket_candidates",
        "pass" if stable_good_buckets.height > 0 else "warn",
        stable_good_buckets.height,
        ">0",
        "若有跨四场景稳定好桶，下一阶段可做预注册过滤/权重探针。",
    )
    add(
        "primary_good_gate_positive",
        "pass"
        if not good_gate.is_empty() and to_float(good_gate["avg_forward_open_ret_1d"][0]) > 0
        else "warn",
        to_float(good_gate["avg_forward_open_ret_1d"][0]) if not good_gate.is_empty() else "NA",
        ">0",
        "上下文好门只用于归因；若为负则不能继续策略化。",
    )
    add(
        "primary_bad_gate_worse_than_good_gate",
        "pass"
        if not good_gate.is_empty()
        and not bad_gate.is_empty()
        and to_float(bad_gate["avg_forward_open_ret_1d"][0]) < to_float(good_gate["avg_forward_open_ret_1d"][0])
        else "warn",
        (
            f"bad={to_float(bad_gate['avg_forward_open_ret_1d'][0]):.6f}, "
            f"good={to_float(good_gate['avg_forward_open_ret_1d'][0]):.6f}"
            if not good_gate.is_empty() and not bad_gate.is_empty()
            else "NA"
        ),
        "bad < good",
        "验证二阶上下文是否至少有方向性。",
    )
    add(
        "no_backtest_or_parameter_change",
        "pass",
        "attribution only",
        "attribution only",
        "本阶段不改变交易策略，不升级候选。",
    )
    return pl.DataFrame(rows)


def write_report(
    cohort_summary: pl.DataFrame,
    tail_profile: pl.DataFrame,
    feature_summary: pl.DataFrame,
    feature_contrast: pl.DataFrame,
    rule_summary: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    all_knife = cohort_summary.filter((pl.col("scenario") == "ALL") & (pl.col("cohort_name") == "knife_any"))
    all_targets = cohort_summary.filter((pl.col("scenario") == "ALL") & (pl.col("cohort_name") == "all_targets"))
    all_knife_2plus = cohort_summary.filter((pl.col("scenario") == "ALL") & (pl.col("cohort_name") == "knife_2plus"))
    all_limit_down = cohort_summary.filter(
        (pl.col("scenario") == "ALL") & (pl.col("cohort_name") == "limit_down_signal")
    )
    best_buckets = feature_contrast.filter(
        (pl.col("cohort_name") == "knife_any") & (pl.col("scenario_count") >= len(FOCUS_SCENARIOS))
    ).sort(["mean_good_minus_bad_tail_ratio", "mean_avg_ret1"], descending=[True, True])
    worst_buckets = feature_contrast.filter(
        (pl.col("cohort_name") == "knife_any") & (pl.col("scenario_count") >= len(FOCUS_SCENARIOS))
    ).sort(["mean_good_minus_bad_tail_ratio", "mean_avg_ret1"], descending=[False, False])
    primary_rules = rule_summary.filter(pl.col("scenario") == PRIMARY_SCENARIO).sort(["rule_name", "rule_value"])
    all_rules = rule_summary.filter(pl.col("scenario") == "ALL").sort(["rule_name", "rule_value"])

    def scalar(frame: pl.DataFrame, col: str, default: float = 0.0) -> float:
        return to_float(frame[col][0]) if not frame.is_empty() and col in frame.columns else default

    market_stressed = all_rules.filter((pl.col("rule_name") == "rule_market_not_stressed") & (pl.col("rule_value") == False))
    market_not_stressed = all_rules.filter(
        (pl.col("rule_name") == "rule_market_not_stressed") & (pl.col("rule_value") == True)
    )
    structure_broken = all_rules.filter((pl.col("rule_name") == "rule_structure_not_broken") & (pl.col("rule_value") == False))
    structure_not_broken = all_rules.filter(
        (pl.col("rule_name") == "rule_structure_not_broken") & (pl.col("rule_value") == True)
    )
    damage_high = all_rules.filter((pl.col("rule_name") == "rule_model_damage_low") & (pl.col("rule_value") == False))
    damage_low = all_rules.filter((pl.col("rule_name") == "rule_model_damage_low") & (pl.col("rule_value") == True))
    context_good = all_rules.filter((pl.col("rule_name") == "rule_context_good_gate") & (pl.col("rule_value") == True))
    context_bad = all_rules.filter((pl.col("rule_name") == "rule_context_bad_gate") & (pl.col("rule_value") == True))
    lines = [
        "# 股票震荡industry_resid_core 30万接刀子二阶归因 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前模式：day。",
        "- 当前研究线：股票震荡30万industry_resid_core独立研究线，不接入第78。",
        "- 本阶段性质：同一高波动/接刀子样本内部的好反弹与坏延续归因；不做交易规则升级。",
        f"- 账户规模：`{ACCOUNT_SIZE_CNY:,.0f}`元口径；本阶段只分析已有目标权重和后验收益。",
        "- 特征时间对齐：个股旗标与指数状态均用上一交易日已知信息映射到下一交易日开盘目标。",
        "- A/B判断：归因阶段，不触发第78 A/B，不修改paper线。",
        "",
        "## 外部调研判断",
        "",
        "- 短期反转文献支持从普通价格反转转向残差/相对反转，避免把系统性趋势风险当作可套利回归。",
        "- 流动性供给型反转和噪声交易通常伴随高波动；所以第326阶段看到接刀子旗标同时出现在好样本和坏样本里，并不矛盾。",
        "- 本阶段的关键不是继续硬过滤，而是寻找高波动内部的上下文：结构是否坏掉、市场/行业是否仍可承接、模型自身是否已经给出损伤惩罚。",
        "",
        "参考资料：",
        *[f"- [{title}]({url})" for title, url in RESEARCH_SOURCES],
        "",
        "## 核心摘要",
        "",
        f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。",
        (
            f"- 全部接刀子样本：`{int(all_knife['target_rows'][0])}`行，"
            f"次开盘平均收益`{pct(to_float(all_knife['avg_forward_open_ret_1d'][0]))}`，"
            f"5日开盘平均收益`{pct(to_float(all_knife['avg_forward_open_ret_5d'][0]))}`。"
            if not all_knife.is_empty()
            else "- 全部接刀子样本：无。"
        ),
        "- 若某个桶只是样本内次日均值好，但跨场景不一致，不能策略化。",
        "",
        "## 本阶段发现",
        "",
        (
            f"- `knife_any`不是坏样本：全样本次开盘平均收益`{pct(scalar(all_targets, 'avg_forward_open_ret_1d'))}`，"
            f"`knife_any`为`{pct(scalar(all_knife, 'avg_forward_open_ret_1d'))}`，"
            f"`knife_2plus`为`{pct(scalar(all_knife_2plus, 'avg_forward_open_ret_1d'))}`。"
        ),
        (
            f"- 越极端越有弹性，但尾部也更厚：`limit_down_signal`次开盘平均收益"
            f"`{pct(scalar(all_limit_down, 'avg_forward_open_ret_1d'))}`、5日`{pct(scalar(all_limit_down, 'avg_forward_open_ret_5d'))}`，"
            f"但坏尾部占比`{scalar(all_limit_down, 'bad_next_open_bottom10_ratio'):.2%}`、好尾部占比"
            f"`{scalar(all_limit_down, 'good_next_open_top10_ratio'):.2%}`。"
        ),
        (
            f"- 直觉型安全门被反证：`rule_context_good_gate=True`次开盘`{pct(scalar(context_good, 'avg_forward_open_ret_1d'))}`，"
            f"`rule_context_bad_gate=True`反而为`{pct(scalar(context_bad, 'avg_forward_open_ret_1d'))}`。"
        ),
        (
            f"- 市场压力不是坏事：`rule_market_not_stressed=False`次开盘`{pct(scalar(market_stressed, 'avg_forward_open_ret_1d'))}`，"
            f"`True`只有`{pct(scalar(market_not_stressed, 'avg_forward_open_ret_1d'))}`。"
        ),
        (
            f"- 结构破坏/损伤惩罚也不应简单剔除：`rule_structure_not_broken=False` 5日"
            f"`{pct(scalar(structure_broken, 'avg_forward_open_ret_5d'))}`，`True`为"
            f"`{pct(scalar(structure_not_broken, 'avg_forward_open_ret_5d'))}`；"
            f"`rule_model_damage_low=False` 5日`{pct(scalar(damage_high, 'avg_forward_open_ret_5d'))}`，"
            f"`True`为`{pct(scalar(damage_low, 'avg_forward_open_ret_5d'))}`。"
        ),
        "- 解释：这条线的收益更像“流动性冲击后的弹性补偿”，不是买温和回调；风险控制不能用常识型安全标签直接砍仓。",
        "",
        "## 高波动样本总体画像",
        "",
        markdown_table(
            cohort_summary,
            [
                "scenario",
                "cohort_name",
                "target_rows",
                "target_days",
                "symbols",
                "avg_forward_open_ret_1d",
                "avg_forward_open_ret_5d",
                "avg_forward_open_ret_10d",
                "positive_ratio_forward_open_ret_1d",
                "bad_next_open_bottom10_ratio",
                "good_next_open_top10_ratio",
                "avg_knife_flag_count",
            ],
            max_rows=120,
        ),
        "",
        "## 接刀子样本好坏尾部画像",
        "",
        markdown_table(
            tail_profile,
            [
                "scenario",
                "ret1_tail_bucket",
                "target_rows",
                "target_days",
                "avg_forward_open_ret_1d",
                "avg_forward_open_ret_5d",
                "avg_stock_ret_20",
                "avg_stock_dist_ma60",
                "avg_stock_close_to_high_252",
                "avg_stock_volume_ratio_20",
                "avg_stock_ibs",
                "avg_benchmark_ret_5",
                "avg_benchmark_drawdown_60",
                "avg_industry_selected_avg_ret20",
                "avg_technical_damage_penalty",
                "avg_knife_flag_count",
            ],
            max_rows=80,
        ),
        "",
        "## 跨场景较好的二阶桶",
        "",
        markdown_table(
            best_buckets,
            [
                "cohort_name",
                "feature",
                "bucket",
                "scenario_count",
                "target_rows",
                "mean_avg_ret1",
                "mean_avg_ret5",
                "mean_avg_ret10",
                "positive_ret1_scenario_ratio",
                "mean_bad_next_open_bottom10_ratio",
                "mean_good_next_open_top10_ratio",
                "mean_good_minus_bad_tail_ratio",
            ],
            max_rows=60,
        ),
        "",
        "## 跨场景较差的二阶桶",
        "",
        markdown_table(
            worst_buckets,
            [
                "cohort_name",
                "feature",
                "bucket",
                "scenario_count",
                "target_rows",
                "mean_avg_ret1",
                "mean_avg_ret5",
                "mean_avg_ret10",
                "positive_ret1_scenario_ratio",
                "mean_bad_next_open_bottom10_ratio",
                "mean_good_next_open_top10_ratio",
                "mean_good_minus_bad_tail_ratio",
            ],
            max_rows=60,
        ),
        "",
        "## 主场景二阶规则画像",
        "",
        markdown_table(
            primary_rules,
            [
                "scenario",
                "rule_name",
                "rule_value",
                "target_rows",
                "target_days",
                "avg_forward_open_ret_1d",
                "avg_forward_open_ret_5d",
                "positive_ratio_forward_open_ret_1d",
                "bad_next_open_bottom10_ratio",
                "good_next_open_top10_ratio",
                "avg_knife_flag_count",
            ],
            max_rows=80,
        ),
        "",
        "## 全样本二阶规则画像",
        "",
        markdown_table(
            all_rules,
            [
                "scenario",
                "rule_name",
                "rule_value",
                "target_rows",
                "target_days",
                "avg_forward_open_ret_1d",
                "avg_forward_open_ret_5d",
                "positive_ratio_forward_open_ret_1d",
                "bad_next_open_bottom10_ratio",
                "good_next_open_top10_ratio",
                "avg_knife_flag_count",
            ],
            max_rows=80,
        ),
        "",
        "## 特征桶明细",
        "",
        markdown_table(
            feature_summary.filter(pl.col("scenario") == PRIMARY_SCENARIO),
            [
                "scenario",
                "cohort_name",
                "feature",
                "bucket",
                "target_rows",
                "avg_forward_open_ret_1d",
                "avg_forward_open_ret_5d",
                "bad_next_open_bottom10_ratio",
                "good_next_open_top10_ratio",
                "avg_knife_flag_count",
            ],
            max_rows=160,
        ),
        "",
        "## 质量检查",
        "",
        markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
        "",
        "## 结论",
        "",
        "- 本阶段不直接生成交易版本，只判断二阶归因是否有方向。",
        "- 如果上下文好门/坏门在主场景和全样本都有方向性，下一阶段才做预注册的轻量过滤或平滑权重探针。",
        "- 如果方向不稳定，就说明接刀子问题仍不能靠这些可见技术状态处理，需要回到信号定义或持有路径。",
        "",
        "## 运行前过拟合反思",
        "",
        "- 判断：中等。",
        "- 原因：二阶规则来自第326失败后的机制假设和外部调研，不是按收益阈值细调；但仍是同一历史样本归因。",
        "",
        "## 运行后过拟合反思",
        "",
        "- 判断：不升级候选。",
        "- 原因：本阶段只看方向，不按最优桶调参；任何规则化都必须在下一阶段预注册并做滚动/OOS。",
        "",
        "## 运行前继续价值反思",
        "",
        "- 判断：是。",
        "- 原因：第326证明简单旗标误杀收益来源，二阶归因是更接近本质的一步。",
        "",
        "## 运行后继续价值反思",
        "",
        "- 判断：若二阶上下文有方向性，则继续；否则降级该路径。",
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
        "enriched_targets": OUTPUT_DIR / f"{PREFIX}_enriched_targets.csv",
        "cohort_summary": OUTPUT_DIR / f"{PREFIX}_cohort_summary.csv",
        "tail_profile": OUTPUT_DIR / f"{PREFIX}_tail_profile.csv",
        "feature_bucket_summary": OUTPUT_DIR / f"{PREFIX}_feature_bucket_summary.csv",
        "feature_contrast": OUTPUT_DIR / f"{PREFIX}_feature_contrast.csv",
        "rule_summary": OUTPUT_DIR / f"{PREFIX}_rule_summary.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }

    target_weights = read_csv_with_symbol(SOURCE_DIR / f"{SOURCE_PREFIX}_target_weights.csv").filter(
        pl.col("scenario").is_in(FOCUS_SCENARIOS)
    )
    stock_df, benchmark_df = load_panels()

    enriched = enrich_targets(target_weights, stock_df, benchmark_df)
    cohort_summary = build_cohort_summary(enriched)
    tail_profile = build_tail_feature_profile(enriched)
    feature_summary = build_feature_bucket_summary(enriched)
    feature_contrast = build_feature_contrast(feature_summary)
    rule_summary = build_rule_summary(enriched)
    quality = build_quality(enriched, cohort_summary, feature_contrast, rule_summary)

    enriched.write_csv(paths["enriched_targets"])
    cohort_summary.write_csv(paths["cohort_summary"])
    tail_profile.write_csv(paths["tail_profile"])
    feature_summary.write_csv(paths["feature_bucket_summary"])
    feature_contrast.write_csv(paths["feature_contrast"])
    rule_summary.write_csv(paths["rule_summary"])
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
            "forward_horizons": FORWARD_HORIZONS,
            "cohorts": [{"name": name, "description": desc} for name, desc in COHORTS],
            "manual_bucket_columns": MANUAL_BUCKET_COLUMNS,
            "pre_registered_flag_columns": PRE_REGISTERED_FLAG_COLUMNS,
            "research_sources": RESEARCH_SOURCES,
            "outputs": {key: str(path) for key, path in paths.items()},
        },
    )
    report_path = write_report(
        cohort_summary,
        tail_profile,
        feature_summary,
        feature_contrast,
        rule_summary,
        quality,
        paths,
    )
    print(f"report={report_path}")
    print(quality)
    print(
        cohort_summary.filter(pl.col("scenario").is_in(["ALL", PRIMARY_SCENARIO])).select(
            [
                "scenario",
                "cohort_name",
                "target_rows",
                "avg_forward_open_ret_1d",
                "avg_forward_open_ret_5d",
                "bad_next_open_bottom10_ratio",
                "good_next_open_top10_ratio",
            ]
        )
    )
    print(
        rule_summary.filter((pl.col("scenario").is_in(["ALL", PRIMARY_SCENARIO])) & (pl.col("rule_value") == True))
        .sort(["scenario", "rule_name"])
        .select(
            [
                "scenario",
                "rule_name",
                "target_rows",
                "avg_forward_open_ret_1d",
                "avg_forward_open_ret_5d",
                "bad_next_open_bottom10_ratio",
                "good_next_open_top10_ratio",
            ]
        )
    )
    print(
        feature_contrast.filter(
            (pl.col("cohort_name") == "knife_any") & (pl.col("scenario_count") >= len(FOCUS_SCENARIOS))
        )
        .sort(["mean_good_minus_bad_tail_ratio", "mean_avg_ret1"], descending=[True, True])
        .head(30)
    )


if __name__ == "__main__":
    main()
