from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_30w_high_return_shape_grid import (
    ACCOUNT_SIZE_CNY,
    NATIVE_RESULTS_DIR,
    OUTPUT_DIR as SOURCE_DIR,
    PREFIX as SOURCE_PREFIX,
    to_float,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import pct


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_30w_simple_mother_early_confirmation_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_30w_simple_mother_early_confirmation_v1"

FOCUS_SCENARIOS: tuple[str, ...] = (
    "top8_gross50_ind2",
    "top5_gross50_ind2",
    "top8_gross70_ind2",
    "top5_gross70_ind2",
)
PRIMARY_SCENARIO: str = "top8_gross50_ind2"
GUARD_SCENARIO: str = "top5_gross50_ind2"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Why Your Mean-Reversion Strategy Fails",
        "https://setupalpha.com/blogs/articles/mean-reversion-strategy-failures-complete-fix-guide",
    ),
    (
        "Mean Reversion Strategies - Complete Backtesting Guide",
        "https://backtestme.com/guides/mean-reversion-strategies",
    ),
    (
        "Mean Reversion Strategy Guide",
        "https://www.tradebeacon.io/blog/mean-reversion-trading-strategy-guide-rsi-bollinger-bands",
    ),
    (
        "Optimal Mean Reversion Trading with Transaction Costs and Stop-Loss Exit",
        "https://arxiv.org/abs/1411.5062",
    ),
    (
        "Short-term residual reversal",
        "https://www.efmaefm.org/0EFMSYMPOSIUM/2012/papers/017_update.pdf",
    ),
    (
        "GitHub mean-reversion-trading topic",
        "https://github.com/topics/mean-reversion-trading",
    ),
)


@dataclass(frozen=True)
class FlagSpec:
    name: str
    direction: str
    description: str


FLAG_SPECS: tuple[FlagSpec, ...] = (
    FlagSpec("entry_reversal_day", "positive", "入场当天收阳且收在日内偏高位置。"),
    FlagSpec("entry_weak_close", "risk", "入场当天继续走弱且收在日内偏低位置。"),
    FlagSpec("early_repair_1d", "positive", "入场后第1日收盘收益为正。"),
    FlagSpec("early_repair_3d", "positive", "入场后第3日累计收益为正。"),
    FlagSpec("fast_rebound_3d", "positive", "入场后3日内最大收盘反弹超过3%。"),
    FlagSpec("no_bounce_3d", "risk", "入场后3日内最大收盘反弹不足1%。"),
    FlagSpec("early_breakdown_3d", "risk", "入场后3日内最大收盘跌幅超过5%。"),
    FlagSpec("volume_repair_3d", "positive", "入场后3日内出现放量上涨日。"),
    FlagSpec("volume_failure_3d", "risk", "入场后3日内出现放量下跌日。"),
    FlagSpec("industry_repair_3d", "positive", "同日同行业选中篮子3日平均路径为正。"),
    FlagSpec("industry_failure_3d", "risk", "同日同行业选中篮子3日平均路径为负。"),
    FlagSpec("stock_leads_industry_3d", "positive", "个股3日路径领先同行业选中篮子超过2pp。"),
    FlagSpec("stock_lags_industry_3d", "risk", "个股3日路径落后同行业选中篮子超过2pp。"),
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    mask = values.notna() & weights.notna() & (weights > 0)
    if not mask.any():
        return float("nan")
    return float(np.average(values[mask].astype(float), weights=weights[mask].astype(float)))


def safe_ratio(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else float("nan")


def pct_value(value: Any) -> str:
    return pct(to_float(value, float("nan")))


def markdown_table(frame: pd.DataFrame, columns: list[str], limit: int = 40) -> str:
    if frame.empty:
        return "\n无数据。\n"
    existing = [col for col in columns if col in frame.columns]
    if not existing:
        return "\n无匹配列。\n"
    return frame[existing].head(limit).to_markdown(index=False)


def add_pct_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = frame.copy()
    for col in columns:
        if col in out.columns:
            out[f"{col}_pct"] = out[col].map(pct_value)
    return out


def load_selected() -> pl.DataFrame:
    needed_cols = [
        "datetime",
        "symbol",
        "code_name",
        "industry",
        "scenario",
        "basket_weight",
        "candidate_count",
        "selected_industry_count",
        "selected_industry_stock_count",
        "ret_1",
        "ret_5",
        "ret_10",
        "ret_20",
        "dist_ma20",
        "volume_ratio_20",
        "score_oversold_ret_20",
        "entry_trade_open",
        "entry_trade_high",
        "entry_trade_low",
        "entry_trade_close",
        "fwd_ret_1",
        "fwd_ret_3",
        "fwd_ret_5",
        "fwd_ret_10",
        "fwd_excess_ret_1",
        "fwd_excess_ret_3",
        "fwd_excess_ret_5",
        "fwd_excess_ret_10",
        "mfe_close_10",
        "mae_close_10",
        *[f"path_close_ret_{idx}" for idx in range(1, 11)],
        *[f"stock_daily_ret_{idx}" for idx in range(1, 4)],
        *[f"pnl_date_{idx}" for idx in range(1, 4)],
    ]
    path = SOURCE_DIR / f"{SOURCE_PREFIX}_selected.csv"
    return (
        pl.scan_csv(path, try_parse_dates=True, schema_overrides={"symbol": pl.Utf8})
        .filter(pl.col("scenario").is_in(FOCUS_SCENARIOS))
        .select([col for col in needed_cols])
        .with_row_index("row_id")
        .with_columns(
            pl.col("datetime").cast(pl.Date),
            *[pl.col(f"pnl_date_{idx}").cast(pl.Date) for idx in range(1, 4)],
        )
        .collect()
    )


def build_early_volume_features(selected: pl.DataFrame) -> pl.DataFrame:
    stock_df, _benchmark_df = load_panels()
    volume_lookup = (
        stock_df.select(["datetime", "symbol", "volume", "turnover_rate"])
        .sort(["symbol", "datetime"])
        .with_columns(
            pl.col("datetime").cast(pl.Date),
            pl.col("symbol").cast(pl.Utf8),
            (pl.col("volume") / pl.col("volume").rolling_mean(20).over("symbol")).alias("pnl_volume_ratio_20"),
        )
        .rename({"datetime": "pnl_date"})
    )
    long_frames: list[pl.DataFrame] = []
    for idx in range(1, 4):
        long = (
            selected.select(
                "row_id",
                "symbol",
                pl.col(f"pnl_date_{idx}").alias("pnl_date"),
                pl.col(f"stock_daily_ret_{idx}").alias("early_daily_ret"),
            )
            .join(volume_lookup, on=["symbol", "pnl_date"], how="left")
            .with_columns(pl.lit(idx).alias("early_day"))
        )
        long_frames.append(long)
    early_long = pl.concat(long_frames, how="vertical")
    return (
        early_long.group_by("row_id")
        .agg(
            pl.col("early_daily_ret").max().alias("early_max_daily_ret_3d"),
            pl.col("early_daily_ret").min().alias("early_min_daily_ret_3d"),
            pl.col("pnl_volume_ratio_20").max().alias("early_max_volume_ratio_3d"),
            (
                ((pl.col("early_daily_ret") >= 0.02) & (pl.col("pnl_volume_ratio_20") >= 1.30))
                .cast(pl.Int64)
                .sum()
            ).alias("early_up_volume_days_3d"),
            (
                ((pl.col("early_daily_ret") <= -0.02) & (pl.col("pnl_volume_ratio_20") >= 1.30))
                .cast(pl.Int64)
                .sum()
            ).alias("early_down_volume_days_3d"),
            pl.col("turnover_rate").mean().alias("early_avg_turnover_rate_3d"),
        )
        .with_columns(
            (pl.col("early_up_volume_days_3d") > 0).alias("volume_repair_3d"),
            (pl.col("early_down_volume_days_3d") > 0).alias("volume_failure_3d"),
        )
    )


def enrich_features(selected: pl.DataFrame, early_volume: pl.DataFrame) -> pl.DataFrame:
    industry_context = (
        selected.group_by(["scenario", "datetime", "industry"])
        .agg(
            pl.col("path_close_ret_1").mean().alias("industry_avg_path_close_ret_1"),
            pl.col("path_close_ret_3").mean().alias("industry_avg_path_close_ret_3"),
            pl.col("fwd_excess_ret_10").mean().alias("industry_avg_fwd_excess_ret_10"),
            pl.len().alias("industry_selected_rows"),
        )
    )
    work = (
        selected.join(early_volume, on="row_id", how="left")
        .join(industry_context, on=["scenario", "datetime", "industry"], how="left")
        .with_columns(
            pl.max_horizontal([pl.col(f"path_close_ret_{idx}") for idx in range(1, 4)]).alias("early_max_path_ret_3d"),
            pl.min_horizontal([pl.col(f"path_close_ret_{idx}") for idx in range(1, 4)]).alias("early_min_path_ret_3d"),
            (
                pl.when(pl.col("entry_trade_open") > 0)
                .then(pl.col("entry_trade_close") / pl.col("entry_trade_open") - 1.0)
                .otherwise(None)
            ).alias("entry_intraday_ret"),
            (
                pl.when((pl.col("entry_trade_high") - pl.col("entry_trade_low")).abs() > 1e-12)
                .then(
                    (pl.col("entry_trade_close") - pl.col("entry_trade_low"))
                    / (pl.col("entry_trade_high") - pl.col("entry_trade_low"))
                )
                .otherwise(None)
            ).alias("entry_ibs"),
            (
                pl.when(1.0 + pl.col("path_close_ret_1") > 0)
                .then((1.0 + pl.col("fwd_ret_10")) / (1.0 + pl.col("path_close_ret_1")) - 1.0)
                .otherwise(None)
            ).alias("late_ret_2_10"),
            (
                pl.when(1.0 + pl.col("path_close_ret_3") > 0)
                .then((1.0 + pl.col("fwd_ret_10")) / (1.0 + pl.col("path_close_ret_3")) - 1.0)
                .otherwise(None)
            ).alias("late_ret_4_10"),
        )
        .with_columns(
            ((pl.col("entry_intraday_ret") > 0) & (pl.col("entry_ibs") >= 0.60)).alias("entry_reversal_day"),
            ((pl.col("entry_intraday_ret") < 0) & (pl.col("entry_ibs") <= 0.30)).alias("entry_weak_close"),
            (pl.col("path_close_ret_1") > 0).alias("early_repair_1d"),
            (pl.col("path_close_ret_3") > 0).alias("early_repair_3d"),
            (pl.col("early_max_path_ret_3d") >= 0.03).alias("fast_rebound_3d"),
            (pl.col("early_max_path_ret_3d") < 0.01).alias("no_bounce_3d"),
            (pl.col("early_min_path_ret_3d") <= -0.05).alias("early_breakdown_3d"),
            (pl.col("industry_avg_path_close_ret_3") > 0).alias("industry_repair_3d"),
            (pl.col("industry_avg_path_close_ret_3") < 0).alias("industry_failure_3d"),
            (pl.col("path_close_ret_3") > pl.col("industry_avg_path_close_ret_3") + 0.02).alias(
                "stock_leads_industry_3d"
            ),
            (pl.col("path_close_ret_3") < pl.col("industry_avg_path_close_ret_3") - 0.02).alias(
                "stock_lags_industry_3d"
            ),
            pl.col("datetime").dt.year().alias("year"),
        )
    )
    return add_tail_labels(work)


def add_tail_labels(work: pl.DataFrame) -> pl.DataFrame:
    frames: list[pl.DataFrame] = []
    for scenario in FOCUS_SCENARIOS:
        frame = work.filter(pl.col("scenario") == scenario)
        if frame.is_empty():
            continue
        bad_threshold = frame["fwd_excess_ret_10"].quantile(0.20)
        good_threshold = frame["fwd_excess_ret_10"].quantile(0.80)
        frames.append(
            frame.with_columns(
                (pl.col("fwd_excess_ret_10") <= bad_threshold).alias("bad_tail_20_excess"),
                (pl.col("fwd_excess_ret_10") >= good_threshold).alias("good_tail_20_excess"),
                pl.lit(float(bad_threshold)).alias("scenario_bad_tail_threshold"),
                pl.lit(float(good_threshold)).alias("scenario_good_tail_threshold"),
            )
        )
    return pl.concat(frames, how="vertical") if frames else work


def summarize_group(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in frame.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        weights = group["basket_weight"].fillna(0.0)
        row = {col: key for col, key in zip(group_cols, keys)}
        row.update(
            {
                "rows": int(len(group)),
                "signal_days": int(group["datetime"].nunique()),
                "symbols": int(group["symbol"].nunique()),
                "weight_sum": float(weights.sum()),
                "avg_basket_weight": float(weights.mean()),
                "weighted_fwd_ret_1": weighted_mean(group["fwd_ret_1"], weights),
                "weighted_fwd_ret_3": weighted_mean(group["fwd_ret_3"], weights),
                "weighted_fwd_ret_10": weighted_mean(group["fwd_ret_10"], weights),
                "weighted_fwd_excess_ret_10": weighted_mean(group["fwd_excess_ret_10"], weights),
                "weighted_late_ret_2_10": weighted_mean(group["late_ret_2_10"], weights),
                "weighted_late_ret_4_10": weighted_mean(group["late_ret_4_10"], weights),
                "avg_mfe_close_10": weighted_mean(group["mfe_close_10"], weights),
                "avg_mae_close_10": weighted_mean(group["mae_close_10"], weights),
                "positive_excess_10_ratio": float((group["fwd_excess_ret_10"] > 0).mean()),
                "bad_tail_20_ratio": float(group["bad_tail_20_excess"].mean()),
                "good_tail_20_ratio": float(group["good_tail_20_excess"].mean()),
                "avg_entry_intraday_ret": weighted_mean(group["entry_intraday_ret"], weights),
                "avg_early_max_path_ret_3d": weighted_mean(group["early_max_path_ret_3d"], weights),
                "avg_early_min_path_ret_3d": weighted_mean(group["early_min_path_ret_3d"], weights),
                "avg_industry_path_ret_3d": weighted_mean(group["industry_avg_path_close_ret_3"], weights),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def build_flag_summary(enriched: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    for spec in FLAG_SPECS:
        work = enriched.copy()
        work["flag_name"] = spec.name
        work["flag_direction"] = spec.direction
        work["flag_description"] = spec.description
        work["flag_value"] = work[spec.name].fillna(False).astype(bool)
        frames.append(summarize_group(work, ["scenario", "flag_name", "flag_direction", "flag_value"]))
    flag_summary = pd.concat(frames, ignore_index=True)
    true_rows = flag_summary[flag_summary["flag_value"].eq(True)].add_suffix("_true")
    false_rows = flag_summary[flag_summary["flag_value"].eq(False)].add_suffix("_false")
    contrast = true_rows.merge(
        false_rows,
        left_on=["scenario_true", "flag_name_true"],
        right_on=["scenario_false", "flag_name_false"],
        how="inner",
    )
    contrast = contrast.rename(
        columns={
            "scenario_true": "scenario",
            "flag_name_true": "flag_name",
            "flag_direction_true": "flag_direction",
        }
    )
    contrast["coverage_ratio"] = contrast["rows_true"] / (contrast["rows_true"] + contrast["rows_false"])
    contrast["delta_weighted_fwd_excess_ret_10"] = (
        contrast["weighted_fwd_excess_ret_10_true"] - contrast["weighted_fwd_excess_ret_10_false"]
    )
    contrast["delta_weighted_late_ret_2_10"] = (
        contrast["weighted_late_ret_2_10_true"] - contrast["weighted_late_ret_2_10_false"]
    )
    contrast["delta_weighted_late_ret_4_10"] = (
        contrast["weighted_late_ret_4_10_true"] - contrast["weighted_late_ret_4_10_false"]
    )
    contrast["delta_bad_tail_20_ratio"] = contrast["bad_tail_20_ratio_true"] - contrast["bad_tail_20_ratio_false"]
    contrast["expected_alpha_edge"] = np.where(
        contrast["flag_direction"].eq("positive"),
        contrast["delta_weighted_fwd_excess_ret_10"],
        -contrast["delta_weighted_fwd_excess_ret_10"],
    )
    contrast["expected_late_edge_2_10"] = np.where(
        contrast["flag_direction"].eq("positive"),
        contrast["delta_weighted_late_ret_2_10"],
        -contrast["delta_weighted_late_ret_2_10"],
    )
    contrast["expected_late_edge_4_10"] = np.where(
        contrast["flag_direction"].eq("positive"),
        contrast["delta_weighted_late_ret_4_10"],
        -contrast["delta_weighted_late_ret_4_10"],
    )
    contrast["expected_bad_tail_edge"] = np.where(
        contrast["flag_direction"].eq("positive"),
        -contrast["delta_bad_tail_20_ratio"],
        contrast["delta_bad_tail_20_ratio"],
    )
    contrast = contrast[
        [
            "scenario",
            "flag_name",
            "flag_direction",
            "coverage_ratio",
            "rows_true",
            "rows_false",
            "weighted_fwd_excess_ret_10_true",
            "weighted_fwd_excess_ret_10_false",
            "delta_weighted_fwd_excess_ret_10",
            "weighted_late_ret_2_10_true",
            "weighted_late_ret_2_10_false",
            "delta_weighted_late_ret_2_10",
            "expected_late_edge_2_10",
            "weighted_late_ret_4_10_true",
            "weighted_late_ret_4_10_false",
            "delta_weighted_late_ret_4_10",
            "expected_late_edge_4_10",
            "bad_tail_20_ratio_true",
            "bad_tail_20_ratio_false",
            "delta_bad_tail_20_ratio",
            "expected_alpha_edge",
            "expected_bad_tail_edge",
            "positive_excess_10_ratio_true",
            "positive_excess_10_ratio_false",
            "avg_mfe_close_10_true",
            "avg_mfe_close_10_false",
            "avg_mae_close_10_true",
            "avg_mae_close_10_false",
        ]
    ].sort_values(["scenario", "expected_alpha_edge", "expected_bad_tail_edge"], ascending=[True, False, False])

    yearly = build_yearly_flag_contrast(enriched)
    return flag_summary, contrast.reset_index(drop=True), yearly


def build_yearly_flag_contrast(enriched: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in FLAG_SPECS:
        for (scenario, year), group in enriched.groupby(["scenario", "year"]):
            true_group = group[group[spec.name].fillna(False).astype(bool)]
            false_group = group[~group[spec.name].fillna(False).astype(bool)]
            if true_group.empty or false_group.empty:
                continue
            true_excess = weighted_mean(true_group["fwd_excess_ret_10"], true_group["basket_weight"])
            false_excess = weighted_mean(false_group["fwd_excess_ret_10"], false_group["basket_weight"])
            delta = true_excess - false_excess
            true_late_4_10 = weighted_mean(true_group["late_ret_4_10"], true_group["basket_weight"])
            false_late_4_10 = weighted_mean(false_group["late_ret_4_10"], false_group["basket_weight"])
            late_delta = true_late_4_10 - false_late_4_10
            true_bad = float(true_group["bad_tail_20_excess"].mean())
            false_bad = float(false_group["bad_tail_20_excess"].mean())
            bad_delta = true_bad - false_bad
            rows.append(
                {
                    "scenario": scenario,
                    "year": int(year),
                    "flag_name": spec.name,
                    "flag_direction": spec.direction,
                    "rows_true": int(len(true_group)),
                    "rows_false": int(len(false_group)),
                    "delta_weighted_fwd_excess_ret_10": delta,
                    "delta_weighted_late_ret_4_10": late_delta,
                    "delta_bad_tail_20_ratio": bad_delta,
                    "expected_alpha_edge": delta if spec.direction == "positive" else -delta,
                    "expected_late_edge_4_10": late_delta if spec.direction == "positive" else -late_delta,
                    "expected_bad_tail_edge": -bad_delta if spec.direction == "positive" else bad_delta,
                }
            )
    yearly = pd.DataFrame(rows)
    if yearly.empty:
        return yearly
    summary = (
        yearly.groupby(["scenario", "flag_name", "flag_direction"], as_index=False)
        .agg(
            years=("year", "count"),
            expected_alpha_positive_years=("expected_alpha_edge", lambda item: int((item > 0).sum())),
            expected_tail_positive_years=("expected_bad_tail_edge", lambda item: int((item > 0).sum())),
            expected_late_positive_years=("expected_late_edge_4_10", lambda item: int((item > 0).sum())),
            avg_expected_alpha_edge=("expected_alpha_edge", "mean"),
            avg_expected_late_edge_4_10=("expected_late_edge_4_10", "mean"),
            avg_expected_bad_tail_edge=("expected_bad_tail_edge", "mean"),
            worst_expected_alpha_edge=("expected_alpha_edge", "min"),
            worst_expected_late_edge_4_10=("expected_late_edge_4_10", "min"),
            worst_expected_bad_tail_edge=("expected_bad_tail_edge", "min"),
        )
        .reset_index(drop=True)
    )
    summary["expected_alpha_positive_year_ratio"] = summary["expected_alpha_positive_years"] / summary["years"]
    summary["expected_tail_positive_year_ratio"] = summary["expected_tail_positive_years"] / summary["years"]
    summary["expected_late_positive_year_ratio"] = summary["expected_late_positive_years"] / summary["years"]
    return summary.sort_values(
        ["scenario", "expected_alpha_positive_year_ratio", "avg_expected_alpha_edge"],
        ascending=[True, False, False],
    ).reset_index(drop=True)


def build_flag_candidates(contrast: pd.DataFrame, yearly: pd.DataFrame) -> pd.DataFrame:
    candidates = contrast.merge(yearly, on=["scenario", "flag_name", "flag_direction"], how="left")
    candidates["usable_coverage"] = candidates["coverage_ratio"].between(0.10, 0.90)
    candidates["alpha_and_tail_ok"] = (candidates["expected_alpha_edge"] > 0) & (
        candidates["expected_bad_tail_edge"] > 0
    )
    candidates["prospective_late_ok"] = candidates["expected_late_edge_4_10"] > 0
    candidates["year_breadth_ok"] = candidates["expected_alpha_positive_year_ratio"].fillna(0.0) >= 0.55
    candidates["late_year_breadth_ok"] = candidates["expected_late_positive_year_ratio"].fillna(0.0) >= 0.55
    candidates["candidate_status"] = np.select(
        [
            candidates["alpha_and_tail_ok"]
            & candidates["prospective_late_ok"]
            & candidates["year_breadth_ok"]
            & candidates["late_year_breadth_ok"]
            & candidates["usable_coverage"],
            candidates["alpha_and_tail_ok"] & candidates["usable_coverage"],
        ],
        ["candidate_for_rule_probe", "path_explanation_only"],
        default="weak_or_rejected",
    )
    return candidates.sort_values(
        ["scenario", "candidate_status", "expected_alpha_edge", "expected_bad_tail_edge"],
        ascending=[True, True, False, False],
    ).reset_index(drop=True)


def build_daily_cohort(enriched: pd.DataFrame) -> pd.DataFrame:
    daily = (
        enriched.groupby(["scenario", "datetime"], as_index=False)
        .agg(
            selected_rows=("symbol", "count"),
            basket_weight_sum=("basket_weight", "sum"),
            weighted_fwd_excess_ret_10=("fwd_excess_ret_10", lambda item: np.nan),
        )
    )
    rows: list[dict[str, Any]] = []
    for (scenario, current_date), group in enriched.groupby(["scenario", "datetime"]):
        weights = group["basket_weight"]
        row = {
            "scenario": scenario,
            "datetime": current_date,
            "selected_rows": int(len(group)),
            "basket_weight_sum": float(weights.sum()),
            "weighted_fwd_excess_ret_10": weighted_mean(group["fwd_excess_ret_10"], weights),
            "weighted_fwd_ret_10": weighted_mean(group["fwd_ret_10"], weights),
            "weighted_late_ret_4_10": weighted_mean(group["late_ret_4_10"], weights),
            "early_repair_3d_ratio": float(group["early_repair_3d"].mean()),
            "no_bounce_3d_ratio": float(group["no_bounce_3d"].mean()),
            "early_breakdown_3d_ratio": float(group["early_breakdown_3d"].mean()),
            "industry_repair_3d_ratio": float(group["industry_repair_3d"].mean()),
            "volume_failure_3d_ratio": float(group["volume_failure_3d"].mean()),
        }
        rows.append(row)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    for col in [
        "early_repair_3d_ratio",
        "no_bounce_3d_ratio",
        "early_breakdown_3d_ratio",
        "industry_repair_3d_ratio",
        "volume_failure_3d_ratio",
    ]:
        out[f"{col}_bucket"] = pd.qcut(out[col].rank(method="first"), 3, labels=["low", "mid", "high"])
    return out.sort_values(["scenario", "datetime"]).reset_index(drop=True)


def build_daily_bucket_summary(daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for col in [
        "early_repair_3d_ratio_bucket",
        "no_bounce_3d_ratio_bucket",
        "early_breakdown_3d_ratio_bucket",
        "industry_repair_3d_ratio_bucket",
        "volume_failure_3d_ratio_bucket",
    ]:
        summary = (
            daily.groupby(["scenario", col], observed=False)
            .agg(
                signal_days=("datetime", "count"),
                avg_weighted_fwd_excess_ret_10=("weighted_fwd_excess_ret_10", "mean"),
                avg_weighted_fwd_ret_10=("weighted_fwd_ret_10", "mean"),
                avg_weighted_late_ret_4_10=("weighted_late_ret_4_10", "mean"),
                bad_signal_day_ratio=("weighted_fwd_excess_ret_10", lambda item: float((item < 0).mean())),
            )
            .reset_index()
            .rename(columns={col: "bucket"})
        )
        summary["daily_bucket_feature"] = col.replace("_bucket", "")
        rows.append(summary)
    return pd.concat(rows, ignore_index=True).sort_values(["scenario", "daily_bucket_feature", "bucket"])


def build_quality(candidates: pd.DataFrame, enriched: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    def add(checkpoint: str, status: str, value: Any, expected: str, note: str) -> None:
        rows.append(
            {
                "checkpoint": checkpoint,
                "status": status,
                "value": str(value),
                "expected": expected,
                "note": note,
            }
        )

    primary = candidates[candidates["scenario"].eq(PRIMARY_SCENARIO)]
    guard = candidates[candidates["scenario"].eq(GUARD_SCENARIO)]
    primary_candidates = primary[primary["candidate_status"].eq("candidate_for_rule_probe")]
    guard_candidates = guard[guard["candidate_status"].eq("candidate_for_rule_probe")]
    broad_candidates = candidates[candidates["candidate_status"].eq("candidate_for_rule_probe")]
    add("focus_scenario_count", "pass" if enriched["scenario"].nunique() == len(FOCUS_SCENARIOS) else "fail", enriched["scenario"].nunique(), str(len(FOCUS_SCENARIOS)), "固定四个简单母本形状。")
    add("flag_count", "pass" if len(FLAG_SPECS) == 13 else "fail", len(FLAG_SPECS), "13", "预注册早期兑现/失败旗标数量。")
    add("selected_rows", "pass" if len(enriched) > 0 else "fail", len(enriched), ">0", "选中样本必须非空。")
    add("primary_rule_probe_candidates", "pass" if len(primary_candidates) > 0 else "warn", len(primary_candidates), ">0", "主母本是否出现可进入规则探针的早期旗标。")
    add("guard_rule_probe_candidates", "pass" if len(guard_candidates) > 0 else "warn", len(guard_candidates), ">0", "top5护栏是否出现同步旗标。")
    add("broad_candidate_count", "pass" if len(broad_candidates) >= 3 else "warn", len(broad_candidates), ">=3", "跨场景候选旗标数量。")
    add("no_trade_rule_change", "pass", "attribution_only", "attribution_only", "本阶段不做交易规则、不改回测参数。")
    return pd.DataFrame(rows)


def build_report(
    candidates: pd.DataFrame,
    contrast: pd.DataFrame,
    yearly: pd.DataFrame,
    daily_bucket: pd.DataFrame,
    quality: pd.DataFrame,
    meta: dict[str, Any],
) -> str:
    candidates_fmt = add_pct_columns(
        candidates,
        [
            "coverage_ratio",
            "weighted_fwd_excess_ret_10_true",
            "weighted_fwd_excess_ret_10_false",
            "delta_weighted_fwd_excess_ret_10",
            "weighted_late_ret_2_10_true",
            "weighted_late_ret_2_10_false",
            "delta_weighted_late_ret_2_10",
            "expected_late_edge_2_10",
            "weighted_late_ret_4_10_true",
            "weighted_late_ret_4_10_false",
            "delta_weighted_late_ret_4_10",
            "expected_late_edge_4_10",
            "bad_tail_20_ratio_true",
            "bad_tail_20_ratio_false",
            "delta_bad_tail_20_ratio",
            "expected_alpha_edge",
            "expected_bad_tail_edge",
            "expected_alpha_positive_year_ratio",
            "expected_late_positive_year_ratio",
            "avg_expected_alpha_edge",
            "avg_expected_late_edge_4_10",
            "avg_expected_bad_tail_edge",
        ],
    )
    daily_fmt = add_pct_columns(
        daily_bucket,
        [
            "avg_weighted_fwd_excess_ret_10",
            "avg_weighted_fwd_ret_10",
            "avg_weighted_late_ret_4_10",
            "bad_signal_day_ratio",
        ],
    )
    primary_candidates = candidates_fmt[
        candidates_fmt["scenario"].eq(PRIMARY_SCENARIO)
        & candidates_fmt["candidate_status"].isin(["candidate_for_rule_probe", "path_explanation_only"])
    ].copy()
    probe = candidates[candidates["candidate_status"].eq("candidate_for_rule_probe")]
    lines = [
        "# 第337阶段：简单超跌母本早期反转兑现/失败归因",
        "",
        "## 结论摘要",
        "",
        "- 本阶段不改交易规则，不重新跑策略；只读取简单母本选股样本，补入本地1-3日成交量路径，做早期兑现/失败归因。",
        "- 目标是回答：入场后1-3日的修复、破位、放量、行业同步，是否能解释10日超额收益和坏尾部。",
        "- 为避免把已经发生的前3日收益误读成可交易预测，候选旗标还必须验证第4-10日剩余持有期仍有边际。",
        f"- 可进入下一步规则探针的旗标数量：`{len(probe)}`。",
        f"- 主母本`{PRIMARY_SCENARIO}`可用线索数：`{len(primary_candidates)}`。",
        "",
        "## 元信息",
        "",
        f"- 生成时间：{meta['generated_at']}",
        f"- 输入目录：`{SOURCE_DIR}`",
        f"- 输出目录：`{OUTPUT_DIR}`",
        f"- 账户规模：{ACCOUNT_SIZE_CNY:,.0f} CNY",
        "",
        "## 外部调研与判断",
        "",
        "- 均值回归失败常见原因是入场过早、极端状态延续、没有确认或退出机制；公开资料也强调反转确认和时间/止损机制。",
        "- 最优止损/交易成本文献提醒：退出/持有本质是停止问题，不能用主观故事直接替换成规则。",
        "- 因此本阶段只做归因，要求旗标同时具备收益边际、坏尾部边际和年度广度，才允许进入下一步规则探针。",
        "",
        "参考资料：",
        *[f"- [{title}]({url})" for title, url in RESEARCH_SOURCES],
        "",
        "## 质量检查",
        "",
        markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], limit=30),
        "",
        "## 主母本候选旗标",
        "",
        markdown_table(
            primary_candidates,
            [
                "flag_name",
                "flag_direction",
                "candidate_status",
                "coverage_ratio_pct",
                "expected_alpha_edge_pct",
                "expected_late_edge_4_10_pct",
                "expected_bad_tail_edge_pct",
                "weighted_fwd_excess_ret_10_true_pct",
                "weighted_fwd_excess_ret_10_false_pct",
                "weighted_late_ret_4_10_true_pct",
                "weighted_late_ret_4_10_false_pct",
                "bad_tail_20_ratio_true_pct",
                "bad_tail_20_ratio_false_pct",
                "expected_alpha_positive_year_ratio_pct",
                "expected_late_positive_year_ratio_pct",
                "avg_expected_alpha_edge_pct",
                "avg_expected_late_edge_4_10_pct",
            ],
            limit=40,
        ),
        "",
        "## 全场景候选排序",
        "",
        markdown_table(
            candidates_fmt,
            [
                "scenario",
                "flag_name",
                "flag_direction",
                "candidate_status",
                "coverage_ratio_pct",
                "expected_alpha_edge_pct",
                "expected_late_edge_4_10_pct",
                "expected_bad_tail_edge_pct",
                "expected_alpha_positive_year_ratio_pct",
                "expected_late_positive_year_ratio_pct",
                "avg_expected_alpha_edge_pct",
                "avg_expected_late_edge_4_10_pct",
                "rows_true",
                "rows_false",
            ],
            limit=80,
        ),
        "",
        "## 日度篮子早期状态",
        "",
        markdown_table(
            daily_fmt,
            [
                "scenario",
                "daily_bucket_feature",
                "bucket",
                "signal_days",
                "avg_weighted_fwd_excess_ret_10_pct",
                "avg_weighted_fwd_ret_10_pct",
                "avg_weighted_late_ret_4_10_pct",
                "bad_signal_day_ratio_pct",
            ],
            limit=80,
        ),
        "",
        "## 研究判断",
        "",
        "- 过拟合判断：否。本阶段是归因，不使用结果改变交易规则；但若下一步规则探针使用这些旗标，必须预注册并做年度/滚动反证。",
        "- 继续价值判断：有。组合层预算已经不足，信号层早期路径若能解释坏尾部，是更接近本质的方向。",
        "- 当前动作不触发A/B实验，不修改第78，不修改`stock_range_paper_v1`。",
        "",
        "## 输出文件",
        "",
        f"- `{PREFIX}_enriched.csv`",
        f"- `{PREFIX}_flag_summary.csv`",
        f"- `{PREFIX}_flag_contrast.csv`",
        f"- `{PREFIX}_yearly_flag_contrast.csv`",
        f"- `{PREFIX}_flag_candidates.csv`",
        f"- `{PREFIX}_daily_cohort.csv`",
        f"- `{PREFIX}_daily_bucket_summary.csv`",
        f"- `{PREFIX}_quality_checkpoints.csv`",
        f"- `{PREFIX}_meta.json`",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    selected = load_selected()
    early_volume = build_early_volume_features(selected)
    enriched_pl = enrich_features(selected, early_volume)
    enriched = enriched_pl.to_pandas()
    flag_summary, contrast, yearly = build_flag_summary(enriched)
    candidates = build_flag_candidates(contrast, yearly)
    daily_cohort = build_daily_cohort(enriched)
    daily_bucket = build_daily_bucket_summary(daily_cohort)
    quality = build_quality(candidates, enriched)

    meta: dict[str, Any] = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_dir": str(SOURCE_DIR),
        "source_prefix": SOURCE_PREFIX,
        "output_dir": str(OUTPUT_DIR),
        "prefix": PREFIX,
        "account_size_cny": ACCOUNT_SIZE_CNY,
        "focus_scenarios": list(FOCUS_SCENARIOS),
        "primary_scenario": PRIMARY_SCENARIO,
        "guard_scenario": GUARD_SCENARIO,
        "flag_specs": [spec.__dict__ for spec in FLAG_SPECS],
        "research_sources": [{"title": title, "url": url} for title, url in RESEARCH_SOURCES],
        "input_rows": int(len(enriched)),
        "quality_status_counts": quality["status"].value_counts().to_dict(),
    }

    enriched.to_csv(OUTPUT_DIR / f"{PREFIX}_enriched.csv", index=False)
    flag_summary.to_csv(OUTPUT_DIR / f"{PREFIX}_flag_summary.csv", index=False)
    contrast.to_csv(OUTPUT_DIR / f"{PREFIX}_flag_contrast.csv", index=False)
    yearly.to_csv(OUTPUT_DIR / f"{PREFIX}_yearly_flag_contrast.csv", index=False)
    candidates.to_csv(OUTPUT_DIR / f"{PREFIX}_flag_candidates.csv", index=False)
    daily_cohort.to_csv(OUTPUT_DIR / f"{PREFIX}_daily_cohort.csv", index=False)
    daily_bucket.to_csv(OUTPUT_DIR / f"{PREFIX}_daily_bucket_summary.csv", index=False)
    quality.to_csv(OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv", index=False)
    write_json(OUTPUT_DIR / f"{PREFIX}_meta.json", meta)

    report = build_report(candidates, contrast, yearly, daily_bucket, quality, meta)
    (OUTPUT_DIR / f"{PREFIX}_report.md").write_text(report, encoding="utf-8")

    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print("\nquality:")
    print(quality.to_string(index=False))
    print("\nprimary candidates:")
    primary = candidates[candidates["scenario"].eq(PRIMARY_SCENARIO)].head(20)
    print(
        primary[
            [
                "flag_name",
                "flag_direction",
                "candidate_status",
                "coverage_ratio",
                "expected_alpha_edge",
                "expected_bad_tail_edge",
                "expected_alpha_positive_year_ratio",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
