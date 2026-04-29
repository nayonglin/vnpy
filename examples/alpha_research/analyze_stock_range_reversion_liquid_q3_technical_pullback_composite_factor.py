from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_liquid_q3_alt_strong_pullback_definitions import prepare_panel, t_stat, write_json
from analyze_stock_range_reversion_signal_attribution import to_float
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import (
    FEATURE,
    HORIZON,
    NATIVE_RESULTS_DIR,
    bucket_expr,
    pct,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_technical_pullback_composite_factor_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_technical_pullback_composite_factor_v1"

TOP_K: int = 20
MIN_SIGNAL_DAYS: int = 120
MIN_DAILY_WIDTH: int = 50

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Alpha Architect: Alpha from Short-Term Signals",
        "https://alphaarchitect.com/alpha-from-short-term-signals/",
    ),
    (
        "Short-term momentum/reversal, turnover, and 52-week-high ratio",
        "https://www.sciencedirect.com/science/article/pii/S0927539824000902",
    ),
    (
        "Alpha Architect: short-term momentum definitions",
        "https://alphaarchitect.com/2022/06/short-term-momentum/",
    ),
    (
        "GitHub topic: momentum trading strategy",
        "https://github.com/topics/momentum-trading-strategy",
    ),
)


def safe_mean_expr(cols: list[str], alias: str) -> pl.Expr:
    return (pl.sum_horizontal([pl.col(col).fill_null(0.0) for col in cols]) / float(len(cols))).alias(alias)


def add_rsi_features(work: pl.DataFrame) -> pl.DataFrame:
    out = work.sort(["symbol", "datetime"]).with_columns(
        (pl.col("close") / pl.col("close").shift(1).over("symbol") - 1).alias("_ret_1_for_rsi")
    )
    out = out.with_columns(
        pl.when(pl.col("_ret_1_for_rsi") > 0).then(pl.col("_ret_1_for_rsi")).otherwise(0.0).alias("_rsi_gain"),
        pl.when(pl.col("_ret_1_for_rsi") < 0).then(-pl.col("_ret_1_for_rsi")).otherwise(0.0).alias("_rsi_loss"),
    )
    for length in (2, 3):
        out = out.with_columns(
            pl.col("_rsi_gain").rolling_mean(length).over("symbol").alias(f"_rsi_gain_{length}"),
            pl.col("_rsi_loss").rolling_mean(length).over("symbol").alias(f"_rsi_loss_{length}"),
        ).with_columns(
            pl.when(pl.col(f"_rsi_loss_{length}") > 0)
            .then(100.0 - (100.0 / (1.0 + pl.col(f"_rsi_gain_{length}") / pl.col(f"_rsi_loss_{length}"))))
            .otherwise(100.0)
            .alias(f"rsi{length}")
        )
    return out.drop([col for col in out.columns if col.startswith("_rsi") or col == "_ret_1_for_rsi"])


def add_composite_features(work: pl.DataFrame) -> pl.DataFrame:
    out = (
        work.sort(["symbol", "datetime"])
        .with_columns(
            pl.col("close").rolling_mean(50).over("symbol").alias("close_ma50"),
            pl.col("close").rolling_mean(200).over("symbol").alias("close_ma200"),
            pl.col("close").rolling_max(20).over("symbol").alias("high_close_20"),
            pl.col("close").rolling_max(60).over("symbol").alias("high_close_60"),
            pl.col("close").rolling_max(120).shift(20).over("symbol").alias("prior_high_close_120_skip20"),
        )
        .with_columns(
            (pl.col("close_ma20") / pl.col("close_ma20").shift(20).over("symbol") - 1).alias("ma20_slope_20"),
            (pl.col("close_ma50") / pl.col("close_ma50").shift(20).over("symbol") - 1).alias("ma50_slope_20"),
            (pl.col("close") / pl.col("close_ma20") - 1).alias("dist_ma20_now"),
            (pl.col("close") / pl.col("close_ma50") - 1).alias("dist_ma50_now"),
            (pl.col("close") / pl.col("high_close_60")).alias("close_to_high_60"),
            (
                (pl.col("high_close_20") >= pl.col("prior_high_close_120_skip20") * 0.995)
                & pl.col("prior_high_close_120_skip20").is_not_null()
            ).alias("recent_120_breakout"),
        )
        .pipe(add_rsi_features)
    )

    out = out.with_columns(
        (
            ((pl.col("close_to_high_252") - 0.75) / 0.20)
            .clip(0.0, 1.0)
            .alias("score_near_252_high")
        ),
        (
            ((pl.col("close_to_high_60") - 0.88) / 0.10)
            .clip(0.0, 1.0)
            .alias("score_near_60_high")
        ),
        pl.when((pl.col("mom120_skip20_q") >= 4) | (pl.col("mom252_skip20_q") >= 4))
        .then(1.0)
        .otherwise(0.0)
        .alias("score_mid_momentum"),
        pl.when((pl.col("industry_mom120_skip20_q") >= 4) | (pl.col("industry_mom252_skip20_q") >= 4))
        .then(1.0)
        .otherwise(0.0)
        .alias("score_industry_strength"),
        pl.when((pl.col("resid_mom120_skip20") > 0) | (pl.col("resid_mom252_skip20") > 0))
        .then(1.0)
        .otherwise(0.0)
        .alias("score_residual_strength"),
        pl.when(
            (pl.col("close") > pl.col("close_ma120"))
            & (pl.col("close_ma20") > pl.col("close_ma50"))
            & (pl.col("close_ma50") > pl.col("close_ma120"))
            & (pl.col("ma20_slope_20") > 0)
            & (pl.col("ma50_slope_20") > 0)
        )
        .then(1.0)
        .otherwise(0.0)
        .alias("score_trend_structure"),
        pl.when(pl.col("recent_120_breakout") & (pl.col("close") >= pl.col("close_ma50")))
        .then(1.0)
        .otherwise(0.0)
        .alias("score_breakout_pullback_context"),
    )

    out = out.with_columns(
        (((-pl.col("ret_5")).clip(0.0, 0.06) / 0.06) * 0.60 + ((-pl.col("ret_10")).clip(0.0, 0.10) / 0.10) * 0.40).alias(
            "score_price_pullback"
        ),
        (((-pl.col("resid_ret_5")).clip(0.0, 0.05) / 0.05) * 0.65 + ((-pl.col("resid_ret_10")).clip(0.0, 0.08) / 0.08) * 0.35).alias(
            "score_residual_pullback"
        ),
        pl.when((pl.col("volume_ratio_20") >= 0.45) & (pl.col("volume_ratio_20") <= 0.95) & (pl.col("ret_5") < 0))
        .then(((1.05 - pl.col("volume_ratio_20")) / 0.60).clip(0.0, 1.0))
        .otherwise(0.0)
        .alias("score_low_volume_pullback"),
        pl.when((pl.col("close") <= pl.col("close_ma20") * 1.025) & (pl.col("close") >= pl.col("close_ma50") * 0.97))
        .then(1.0)
        .otherwise(0.0)
        .alias("score_ma_pullback"),
        pl.max_horizontal(
            [
                ((35.0 - pl.col("rsi2")) / 35.0).clip(0.0, 1.0),
                ((40.0 - pl.col("rsi3")) / 40.0).clip(0.0, 1.0),
                ((0.40 - pl.col("ibs")) / 0.40).clip(0.0, 1.0),
            ]
        ).alias("score_short_cycle_pullback"),
    )

    out = out.with_columns(
        pl.when(pl.col("close_to_high_252") < 0.75).then(1.0).otherwise(0.0).alias("penalty_far_from_high"),
        pl.when((pl.col("close") < pl.col("close_ma120")) | (pl.col("close_ma50") < pl.col("close_ma120")))
        .then(1.0)
        .otherwise(0.0)
        .alias("penalty_trend_broken"),
        pl.when((pl.col("ret_5") < -0.06) & (pl.col("volume_ratio_20") > 1.30))
        .then(1.0)
        .otherwise(0.0)
        .alias("penalty_high_volume_selloff"),
        pl.when((pl.col("industry_mom120_skip20_q") <= 2) | (pl.col("industry_mom252_skip20_q") <= 2))
        .then(1.0)
        .otherwise(0.0)
        .alias("penalty_weak_industry"),
        pl.when(pl.col("volume_ratio_20") < 0.35).then(1.0).otherwise(0.0).alias("penalty_volume_vacuum"),
    )

    context_cols = [
        "score_mid_momentum",
        "score_near_252_high",
        "score_industry_strength",
        "score_residual_strength",
        "score_trend_structure",
        "score_breakout_pullback_context",
    ]
    pullback_cols = [
        "score_price_pullback",
        "score_residual_pullback",
        "score_low_volume_pullback",
        "score_ma_pullback",
        "score_short_cycle_pullback",
    ]
    penalty_cols = [
        "penalty_far_from_high",
        "penalty_trend_broken",
        "penalty_high_volume_selloff",
        "penalty_weak_industry",
        "penalty_volume_vacuum",
    ]
    out = out.with_columns(
        safe_mean_expr(context_cols, "technical_context_score"),
        safe_mean_expr(pullback_cols, "technical_pullback_quality"),
        safe_mean_expr(penalty_cols, "technical_damage_penalty"),
    )
    return out.with_columns(
        (
            pl.col("technical_context_score") * pl.col("technical_pullback_quality")
            - 0.75 * pl.col("technical_damage_penalty")
        ).alias("technical_pullback_score"),
        (
            (
                pl.col("score_industry_strength")
                + pl.col("score_near_252_high")
                + pl.col("score_residual_pullback")
                + pl.col("score_low_volume_pullback")
            )
            / 4.0
            - 0.50 * pl.col("technical_damage_penalty")
        ).alias("industry_resid_pullback_score"),
        (
            pl.col("technical_context_score") * 0.70
            + pl.col("technical_pullback_quality") * 0.30
            - 0.75 * pl.col("technical_damage_penalty")
        ).alias("context_weighted_score"),
        (
            pl.col("technical_pullback_quality") * 0.70
            + pl.col("technical_context_score") * 0.30
            - 0.75 * pl.col("technical_damage_penalty")
        ).alias("pullback_weighted_score"),
    )


def base_filter_expr() -> pl.Expr:
    return (
        bucket_expr("liquid_q3")
        & pl.col(f"final_keep_{HORIZON}").fill_null(False)
        & pl.col("final_keep_5").fill_null(False)
        & pl.col(FEATURE).is_not_null()
        & pl.col(FEATURE).is_finite()
        & pl.col("industry").is_not_null()
        & pl.col("technical_pullback_score").is_not_null()
        & pl.col("technical_pullback_score").is_finite()
    )


def add_score_quintiles(work: pl.DataFrame) -> pl.DataFrame:
    ranked = (
        work.filter(base_filter_expr())
        .with_columns(
            pl.col("technical_pullback_score").rank("ordinal").over("datetime").alias("_rank"),
            pl.len().over("datetime").alias("_n"),
        )
        .filter(pl.col("_n") >= MIN_DAILY_WIDTH)
        .with_columns(((((pl.col("_rank") - 1) * 5) / pl.col("_n")).floor().cast(pl.Int64) + 1).clip(1, 5).alias("technical_pullback_score_q"))
        .select(["datetime", "symbol", "technical_pullback_score_q"])
    )
    return work.join(ranked, on=["datetime", "symbol"], how="left")


def model_specs() -> list[dict[str, Any]]:
    return [
        {
            "model": "composite_all8_product_damage",
            "description": "8点统一复合因子：强势背景 * 回调质量 - 损坏惩罚。",
            "score_col": "technical_pullback_score",
            "filter": pl.lit(True),
        },
        {
            "model": "strict_context_pullback_low_damage",
            "description": "严格setup：背景>=0.50、回调>=0.40、损坏<=0.20。",
            "score_col": "technical_pullback_score",
            "filter": (pl.col("technical_context_score") >= 0.50)
            & (pl.col("technical_pullback_quality") >= 0.40)
            & (pl.col("technical_damage_penalty") <= 0.20),
        },
        {
            "model": "industry_resid_core",
            "description": "强行业+近高点+残差回调+缩量的核心子因子。",
            "score_col": "industry_resid_pullback_score",
            "filter": pl.col("technical_damage_penalty") <= 0.40,
        },
        {
            "model": "context_weighted",
            "description": "偏强势背景版本，检查是否只是趋势强度在起作用。",
            "score_col": "context_weighted_score",
            "filter": pl.col("technical_pullback_quality") >= 0.20,
        },
        {
            "model": "pullback_weighted",
            "description": "偏回调质量版本，检查是否只是短期超跌在起作用。",
            "score_col": "pullback_weighted_score",
            "filter": pl.col("technical_context_score") >= 0.35,
        },
    ]


def build_selected(work: pl.DataFrame) -> pl.DataFrame:
    keep_cols = [
        "datetime",
        "symbol",
        "code_name",
        "industry",
        "market",
        "adv20_turnover",
        "turnover_rate_f",
        "circ_mv",
        "total_mv",
        FEATURE,
        "technical_pullback_score",
        "technical_context_score",
        "technical_pullback_quality",
        "technical_damage_penalty",
        "industry_resid_pullback_score",
        "context_weighted_score",
        "pullback_weighted_score",
        "ret_5",
        "ret_10",
        "resid_ret_5",
        "resid_ret_10",
        "volume_ratio_20",
        "ibs",
        "rsi2",
        "rsi3",
        "close_to_high_252",
        "mom120_skip20",
        "mom252_skip20",
        "industry_mom120_skip20",
        "industry_mom252_skip20",
        "ma20_slope_20",
        "ma50_slope_20",
        "dist_ma20_now",
        "dist_ma50_now",
        "recent_120_breakout",
        "score_mid_momentum",
        "score_near_252_high",
        "score_industry_strength",
        "score_residual_strength",
        "score_trend_structure",
        "score_breakout_pullback_context",
        "score_price_pullback",
        "score_residual_pullback",
        "score_low_volume_pullback",
        "score_ma_pullback",
        "score_short_cycle_pullback",
        "penalty_far_from_high",
        "penalty_trend_broken",
        "penalty_high_volume_selloff",
        "penalty_weak_industry",
        "penalty_volume_vacuum",
        "mfe_close_10",
        "mae_close_10",
        "fwd_ret_3",
        "fwd_excess_ret_3",
        "fwd_ret_5",
        "fwd_excess_ret_5",
        "fwd_ret_10",
        "fwd_excess_ret_10",
    ]
    frames: list[pl.DataFrame] = []
    for spec in model_specs():
        score_col = spec["score_col"]
        scoped = (
            work.filter(base_filter_expr() & spec["filter"] & pl.col(score_col).is_not_null() & pl.col(score_col).is_finite())
            .with_columns(
                pl.col(score_col).alias("model_score"),
                pl.lit(spec["model"]).alias("model"),
                pl.lit(spec["description"]).alias("model_description"),
            )
            .with_columns(
                pl.col("model_score").rank("ordinal", descending=True).over("datetime").alias("daily_rank"),
                pl.len().over("datetime").alias("daily_candidates"),
            )
            .filter(pl.col("daily_rank") <= TOP_K)
            .select(
                [
                    col
                    for col in [
                        *keep_cols,
                        "model",
                        "model_description",
                        "model_score",
                        "daily_rank",
                        "daily_candidates",
                    ]
                    if col in work.columns or col in {"model", "model_description", "model_score", "daily_rank", "daily_candidates"}
                ]
            )
        )
        if not scoped.is_empty():
            frames.append(scoped)
    return pl.concat(frames, how="vertical").sort(["model", "datetime", "daily_rank"]) if frames else pl.DataFrame()


def summarize_selected(selected: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for model, frame in selected.partition_by("model", as_dict=True).items():
        if isinstance(model, tuple):
            model = model[0]
        daily = (
            frame.group_by("datetime")
            .agg(
                pl.len().alias("daily_selected"),
                pl.col("fwd_excess_ret_3").mean().alias("daily_fwd_excess_ret_3"),
                pl.col("fwd_excess_ret_5").mean().alias("daily_fwd_excess_ret_5"),
                pl.col("fwd_excess_ret_10").mean().alias("daily_fwd_excess_ret_10"),
            )
            .sort("datetime")
        )
        rows.append(
            {
                "model": model,
                "model_description": frame["model_description"][0],
                "selected_rows": frame.height,
                "signal_days": daily.height,
                "symbols": frame["symbol"].n_unique(),
                "avg_daily_selected": to_float(daily["daily_selected"].mean()),
                "avg_daily_candidates_before_topk": to_float(frame["daily_candidates"].mean()),
                "avg_model_score": to_float(frame["model_score"].mean()),
                "avg_context_score": to_float(frame["technical_context_score"].mean()),
                "avg_pullback_quality": to_float(frame["technical_pullback_quality"].mean()),
                "avg_damage_penalty": to_float(frame["technical_damage_penalty"].mean()),
                "avg_ret_5": to_float(frame["ret_5"].mean()),
                "avg_resid_ret_5": to_float(frame["resid_ret_5"].mean()),
                "avg_volume_ratio_20": to_float(frame["volume_ratio_20"].mean()),
                "avg_ibs": to_float(frame["ibs"].mean()),
                "avg_rsi2": to_float(frame["rsi2"].mean()),
                "avg_close_to_high_252": to_float(frame["close_to_high_252"].mean()),
                "avg_fwd_excess_ret_3": to_float(frame["fwd_excess_ret_3"].mean()),
                "avg_fwd_excess_ret_5": to_float(frame["fwd_excess_ret_5"].mean()),
                "avg_fwd_excess_ret_10": to_float(frame["fwd_excess_ret_10"].mean()),
                "positive_excess_10_ratio": to_float((frame["fwd_excess_ret_10"] > 0).mean()),
                "daily_avg_fwd_excess_ret_10": to_float(daily["daily_fwd_excess_ret_10"].mean()),
                "daily_t_stat_excess_10": t_stat(
                    to_float(daily["daily_fwd_excess_ret_10"].mean()),
                    to_float(daily["daily_fwd_excess_ret_10"].std()),
                    daily.height,
                ),
                "avg_mfe_close_10": to_float(frame["mfe_close_10"].mean()),
                "avg_mae_close_10": to_float(frame["mae_close_10"].mean()),
            }
        )
    return pl.DataFrame(rows).sort(["daily_avg_fwd_excess_ret_10", "avg_fwd_excess_ret_10"], descending=[True, True])


def summarize_quintiles(work: pl.DataFrame) -> pl.DataFrame:
    scoped = work.filter(base_filter_expr() & pl.col("technical_pullback_score_q").is_not_null())
    daily = (
        scoped.group_by(["datetime", "technical_pullback_score_q"])
        .agg(
            pl.len().alias("daily_rows"),
            pl.col("technical_pullback_score").mean().alias("daily_score"),
            pl.col("technical_context_score").mean().alias("daily_context"),
            pl.col("technical_pullback_quality").mean().alias("daily_pullback"),
            pl.col("technical_damage_penalty").mean().alias("daily_damage"),
            pl.col("fwd_excess_ret_3").mean().alias("daily_fwd_excess_ret_3"),
            pl.col("fwd_excess_ret_5").mean().alias("daily_fwd_excess_ret_5"),
            pl.col("fwd_excess_ret_10").mean().alias("daily_fwd_excess_ret_10"),
        )
        .sort(["technical_pullback_score_q", "datetime"])
    )
    rows: list[dict[str, Any]] = []
    for q, frame in daily.partition_by("technical_pullback_score_q", as_dict=True).items():
        if isinstance(q, tuple):
            q = q[0]
        sample = scoped.filter(pl.col("technical_pullback_score_q") == q)
        rows.append(
            {
                "score_q": int(q),
                "rows": sample.height,
                "signal_days": frame.height,
                "avg_daily_rows": to_float(frame["daily_rows"].mean()),
                "avg_score": to_float(frame["daily_score"].mean()),
                "avg_context": to_float(frame["daily_context"].mean()),
                "avg_pullback": to_float(frame["daily_pullback"].mean()),
                "avg_damage": to_float(frame["daily_damage"].mean()),
                "avg_fwd_excess_ret_3": to_float(sample["fwd_excess_ret_3"].mean()),
                "avg_fwd_excess_ret_5": to_float(sample["fwd_excess_ret_5"].mean()),
                "avg_fwd_excess_ret_10": to_float(sample["fwd_excess_ret_10"].mean()),
                "positive_excess_10_ratio": to_float((sample["fwd_excess_ret_10"] > 0).mean()),
                "daily_avg_fwd_excess_ret_10": to_float(frame["daily_fwd_excess_ret_10"].mean()),
                "daily_t_stat_excess_10": t_stat(
                    to_float(frame["daily_fwd_excess_ret_10"].mean()),
                    to_float(frame["daily_fwd_excess_ret_10"].std()),
                    frame.height,
                ),
            }
        )
    return pl.DataFrame(rows).sort("score_q")


def summarize_yearly(selected: pl.DataFrame) -> pl.DataFrame:
    return (
        selected.with_columns(pl.col("datetime").dt.year().alias("year"))
        .group_by(["model", "year"])
        .agg(
            pl.len().alias("selected_rows"),
            pl.col("datetime").n_unique().alias("signal_days"),
            pl.col("fwd_excess_ret_10").mean().alias("avg_fwd_excess_ret_10"),
            (pl.col("fwd_excess_ret_10") > 0).mean().alias("positive_excess_10_ratio"),
            pl.col("mfe_close_10").mean().alias("avg_mfe_close_10"),
            pl.col("mae_close_10").mean().alias("avg_mae_close_10"),
        )
        .sort(["model", "year"])
    )


def build_component_snapshot(selected: pl.DataFrame) -> pl.DataFrame:
    component_cols = [
        "score_mid_momentum",
        "score_near_252_high",
        "score_industry_strength",
        "score_residual_strength",
        "score_trend_structure",
        "score_breakout_pullback_context",
        "score_price_pullback",
        "score_residual_pullback",
        "score_low_volume_pullback",
        "score_ma_pullback",
        "score_short_cycle_pullback",
        "penalty_far_from_high",
        "penalty_trend_broken",
        "penalty_high_volume_selloff",
        "penalty_weak_industry",
        "penalty_volume_vacuum",
    ]
    existing = [col for col in component_cols if col in selected.columns]
    if not existing:
        return pl.DataFrame()
    return (
        selected.group_by("model")
        .agg([pl.col(col).mean().alias(f"avg_{col}") for col in existing])
        .sort("model")
    )


def build_quality(summary: pl.DataFrame, quintiles: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, str]] = []
    q5 = quintiles.filter(pl.col("score_q") == 5)
    q1 = quintiles.filter(pl.col("score_q") == 1)
    q5_excess = to_float(q5["daily_avg_fwd_excess_ret_10"][0]) if not q5.is_empty() else 0.0
    q1_excess = to_float(q1["daily_avg_fwd_excess_ret_10"][0]) if not q1.is_empty() else 0.0
    max_q_excess = to_float(quintiles["daily_avg_fwd_excess_ret_10"].max()) if not quintiles.is_empty() else 0.0
    best_q = (
        int(
            quintiles.sort("daily_avg_fwd_excess_ret_10", descending=True)["score_q"][0]
        )
        if not quintiles.is_empty()
        else 0
    )
    rows.append(
        {
            "scope": "factor_quintile",
            "checkpoint": "q5_beats_q1",
            "status": "pass" if q5_excess > q1_excess else "fail",
            "value": f"q5={pct(q5_excess)}, q1={pct(q1_excess)}",
            "expected": "q5 > q1",
            "note": "统一因子至少应呈现高分优于低分的截面单调方向。",
        }
    )
    rows.append(
        {
            "scope": "factor_quintile",
            "checkpoint": "q5_positive",
            "status": "pass" if q5_excess > 0 else "fail",
            "value": pct(q5_excess),
            "expected": ">0",
            "note": "最高分组的10日前向超额应为正。",
        }
    )
    rows.append(
        {
            "scope": "factor_quintile",
            "checkpoint": "q5_is_best_bucket",
            "status": "pass" if q5_excess >= max_q_excess else "warn",
            "value": f"q5={pct(q5_excess)}, best_q={best_q}, best={pct(max_q_excess)}",
            "expected": "q5 is best",
            "note": "若最高分位不是最强，说明复合因子排序仍有过度混合或惩罚不足。",
        }
    )
    for row in summary.iter_rows(named=True):
        model = row["model"]
        days = int(row.get("signal_days") or 0)
        excess = to_float(row.get("daily_avg_fwd_excess_ret_10"))
        t_value = to_float(row.get("daily_t_stat_excess_10"))
        mae = to_float(row.get("avg_mae_close_10"))
        damage = to_float(row.get("avg_damage_penalty"))
        rows.extend(
            [
                {
                    "scope": model,
                    "checkpoint": "coverage",
                    "status": "pass" if days >= MIN_SIGNAL_DAYS else "warn",
                    "value": str(days),
                    "expected": f">={MIN_SIGNAL_DAYS}",
                    "note": "信号日太少容易样本内偶然。",
                },
                {
                    "scope": model,
                    "checkpoint": "daily_excess_positive",
                    "status": "pass" if excess > 0 else "fail",
                    "value": pct(excess),
                    "expected": ">0",
                    "note": "top样本的日均10日超额需要为正。",
                },
                {
                    "scope": model,
                    "checkpoint": "t_stat",
                    "status": "pass" if t_value >= 1.0 else "warn" if t_value > 0 else "fail",
                    "value": f"{t_value:.3f}",
                    "expected": ">=1 preferred",
                    "note": "归因阶段只看方向，不把t值当正式上线标准。",
                },
                {
                    "scope": model,
                    "checkpoint": "tail_risk_mae",
                    "status": "warn" if mae < -0.08 else "pass",
                    "value": pct(mae),
                    "expected": ">-8%",
                    "note": "平均10日MAE过深，后续30万复放容易被尾部击穿。",
                },
                {
                    "scope": model,
                    "checkpoint": "damage_penalty",
                    "status": "warn" if damage > 0.30 else "pass",
                    "value": f"{damage:.3f}",
                    "expected": "<=0.30",
                    "note": "高分样本若仍带明显结构损坏，说明因子没有把坏回调过滤干净。",
                },
            ]
        )
    return pl.DataFrame(rows).sort(["scope", "checkpoint"])


def write_report(
    summary: pl.DataFrame,
    quintiles: pl.DataFrame,
    yearly: pl.DataFrame,
    quality: pl.DataFrame,
    component_snapshot: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    best = summary.row(0, named=True) if not summary.is_empty() else None
    q5 = quintiles.filter(pl.col("score_q") == 5)
    q1 = quintiles.filter(pl.col("score_q") == 1)
    q5_excess = to_float(q5["daily_avg_fwd_excess_ret_10"][0]) if not q5.is_empty() else 0.0
    q1_excess = to_float(q1["daily_avg_fwd_excess_ret_10"][0]) if not q1.is_empty() else 0.0
    lines = [
        "# 股票震荡liquid_q3 技术面复合回踩因子归因 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前模式：day。",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：把8个强势回踩定义统一为技术面复合因子，只做信号归因，不做30万整手复放。",
        f"- 每个模型每日最多取top `{TOP_K}` 个样本。",
        "- A/B判断：纯因子归因，不触发A/B。",
        "",
        "## 外部调研判断",
        "",
        "- 短周期反转单独使用通常换手高、成本敏感；复合多个短周期信号、并配合高效交易规则，比单一短反转更合理。",
        "- 52周高点、换手、行业相对反转会改变短期反转/动量的方向，说明8个点应分层组合，而不是简单相加。",
        "- GitHub开源多为动量/技术指标教学或框架样例，可借鉴工程形态，不能替代A股复权、涨跌停、ST、成本和30万整手约束。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(["", "## 核心摘要", ""])
    if best:
        lines.append(
            f"- top样本最优模型：`{best['model']}`，日均10日超额`{pct(best['daily_avg_fwd_excess_ret_10'])}`，样本10日超额`{pct(best['avg_fwd_excess_ret_10'])}`，正超额比例`{pct(best['positive_excess_10_ratio'])}`，t值`{best['daily_t_stat_excess_10']:.3f}`。"
        )
    lines.append(f"- 统一因子分位：q5日均10日超额`{pct(q5_excess)}`，q1日均10日超额`{pct(q1_excess)}`，q5-q1差`{pct(q5_excess - q1_excess)}`。")
    lines.append(f"- 质量检查fail `{failed.height}`项，warn `{warned.height}`项。")
    lines.append("- 判断：如果最高分位和top样本都不能稳定为正，则不进入交易化；若信号层有效，下一步才做30万整手复放。")
    summary_cols = [
        "model",
        "signal_days",
        "selected_rows",
        "avg_daily_candidates_before_topk",
        "avg_model_score",
        "avg_context_score",
        "avg_pullback_quality",
        "avg_damage_penalty",
        "avg_ret_5",
        "avg_resid_ret_5",
        "avg_volume_ratio_20",
        "avg_ibs",
        "avg_rsi2",
        "avg_close_to_high_252",
        "avg_fwd_excess_ret_3",
        "avg_fwd_excess_ret_5",
        "avg_fwd_excess_ret_10",
        "daily_avg_fwd_excess_ret_10",
        "daily_t_stat_excess_10",
        "positive_excess_10_ratio",
        "avg_mfe_close_10",
        "avg_mae_close_10",
    ]
    lines.extend(
        [
            "",
            "## 模型top样本汇总",
            "",
            markdown_table(summary, [col for col in summary_cols if col in summary.columns], max_rows=80),
            "",
            "## 统一因子分位",
            "",
            markdown_table(quintiles, quintiles.columns, max_rows=30),
            "",
            "## 模型说明",
            "",
            markdown_table(summary.select(["model", "model_description"]), ["model", "model_description"], max_rows=80),
            "",
            "## 年度拆分",
            "",
            markdown_table(yearly, yearly.columns, max_rows=180),
            "",
            "## 组件快照",
            "",
            markdown_table(component_snapshot, component_snapshot.columns, max_rows=80) if not component_snapshot.is_empty() else "无组件快照。",
            "",
            "## 质量检查",
            "",
            markdown_table(quality, quality.columns, max_rows=180),
            "",
            "## 运行后结论",
            "",
            "- 本阶段不根据结果调权重；若出现候选，也只能说明技术面复合状态有信号信息，不能说明30万账户可交易。",
            "- 下一步需要优先看分位单调性、年度稳定性、MAE和行业集中，再决定是否做30万整手复放。",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "selected": OUTPUT_DIR / f"{PREFIX}_selected.csv",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "quintiles": OUTPUT_DIR / f"{PREFIX}_quintiles.csv",
        "yearly": OUTPUT_DIR / f"{PREFIX}_yearly.csv",
        "components": OUTPUT_DIR / f"{PREFIX}_components.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
    }
    work = prepare_panel().pipe(add_composite_features).pipe(add_score_quintiles)
    selected = build_selected(work)
    summary = summarize_selected(selected)
    quintiles = summarize_quintiles(work)
    yearly = summarize_yearly(selected)
    component_snapshot = build_component_snapshot(selected)
    quality = build_quality(summary, quintiles)
    selected.write_csv(paths["selected"])
    summary.write_csv(paths["summary"])
    quintiles.write_csv(paths["quintiles"])
    yearly.write_csv(paths["yearly"])
    component_snapshot.write_csv(paths["components"])
    quality.write_csv(paths["quality"])
    report_path = write_report(summary, quintiles, yearly, quality, component_snapshot, paths)
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "top_k": TOP_K,
            "min_signal_days": MIN_SIGNAL_DAYS,
            "factor_structure": {
                "technical_pullback_score": "technical_context_score * technical_pullback_quality - 0.75 * technical_damage_penalty",
                "context_layer": [
                    "12-2/6-2 style skip momentum",
                    "near 52-week high",
                    "strong industry",
                    "residual strength",
                    "trend structure",
                    "breakout pullback context",
                ],
                "pullback_layer": [
                    "recent 5/10d pullback",
                    "residual pullback",
                    "low-volume pullback",
                    "moving-average pullback",
                    "RSI2/RSI3/IBS short-cycle pullback",
                ],
                "damage_layer": [
                    "far from high",
                    "trend broken",
                    "high-volume selloff",
                    "weak industry",
                    "volume vacuum",
                ],
            },
            "models": [{key: value for key, value in item.items() if key != "filter"} for item in model_specs()],
            "outputs": {key: str(path) for key, path in paths.items()},
            "report": str(report_path),
        },
    )
    print(f"wrote {report_path}")


if __name__ == "__main__":
    main()
