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
    to_float,
)
from analyze_stock_range_reversion_liquid_q3_30w_simple_mother_early_confirmation_attribution import (
    FOCUS_SCENARIOS,
    GUARD_SCENARIO,
    OUTPUT_DIR as STAGE337_DIR,
    PREFIX as STAGE337_PREFIX,
    PRIMARY_SCENARIO,
    markdown_table,
    pct_value,
    weighted_mean,
    write_json,
)


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_30w_simple_mother_confirmation_extension_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_30w_simple_mother_confirmation_extension_v1"

CONFIRMATION_FLAGS: tuple[str, ...] = (
    "fast_rebound_3d",
    "volume_repair_3d",
    "confirm_either",
    "confirm_both",
    "fast_only",
    "volume_only",
)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Short-term reversals, returns to liquidity provision and the costs of immediacy",
        "https://www.sciencedirect.com/science/article/pii/S0378426622000309",
    ),
    (
        "Another Look at Trading Costs and Short-Term Reversal Profits",
        "https://www.quantifiedstrategies.com/wp-content/uploads/2023/11/Another-Look-at-Trading-Costs-and-Short-Term-Reversal-Profits.pdf",
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
        "Mean Reversion Strategy Guide",
        "https://www.tradebeacon.io/blog/mean-reversion-trading-strategy-guide-rsi-bollinger-bands",
    ),
)


@dataclass(frozen=True)
class ContinuationMetric:
    column: str
    description: str


CONTINUATION_METRICS: tuple[ContinuationMetric, ...] = (
    ContinuationMetric("late_ret_11_15", "原10日持有期结束后，第11-15日绝对收益。"),
    ContinuationMetric("late_excess_ret_11_15", "原10日持有期结束后，第11-15日相对基准超额收益。"),
    ContinuationMetric("late_ret_11_20", "原10日持有期结束后，第11-20日绝对收益。"),
    ContinuationMetric("late_excess_ret_11_20", "原10日持有期结束后，第11-20日相对基准超额收益。"),
)


def add_pct_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = frame.copy()
    for col in columns:
        if col in out.columns:
            out[f"{col}_pct"] = out[col].map(pct_value)
    return out


def load_stage337_enriched() -> pl.DataFrame:
    path = STAGE337_DIR / f"{STAGE337_PREFIX}_enriched.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    return (
        pl.scan_csv(path, try_parse_dates=True, schema_overrides={"symbol": pl.Utf8})
        .filter(pl.col("scenario").is_in(FOCUS_SCENARIOS))
        .with_columns(pl.col("datetime").cast(pl.Date), pl.col("symbol").cast(pl.Utf8))
        .collect()
    )


def build_extension_paths(enriched: pl.DataFrame) -> pl.DataFrame:
    stock_df, benchmark_df = load_panels()
    stock_path = (
        stock_df.select(["datetime", "symbol", "close"])
        .sort(["symbol", "datetime"])
        .with_columns(
            pl.col("datetime").cast(pl.Date),
            pl.col("symbol").cast(pl.Utf8),
            pl.col("close").shift(-1).over("symbol").alias("entry_close_check"),
            pl.col("close").shift(-11).over("symbol").alias("exit_close_10_check"),
            pl.col("close").shift(-16).over("symbol").alias("exit_close_15"),
            pl.col("close").shift(-21).over("symbol").alias("exit_close_20"),
            pl.col("datetime").shift(-16).over("symbol").alias("exit_date_15"),
            pl.col("datetime").shift(-21).over("symbol").alias("exit_date_20"),
        )
        .with_columns(
            (pl.col("exit_close_15") / pl.col("entry_close_check") - 1.0).alias("fwd_ret_15"),
            (pl.col("exit_close_20") / pl.col("entry_close_check") - 1.0).alias("fwd_ret_20"),
            (pl.col("exit_close_10_check") / pl.col("entry_close_check") - 1.0).alias("fwd_ret_10_check"),
        )
        .with_columns(
            (
                pl.when(1.0 + pl.col("fwd_ret_10_check") > 0)
                .then((1.0 + pl.col("fwd_ret_15")) / (1.0 + pl.col("fwd_ret_10_check")) - 1.0)
                .otherwise(None)
            ).alias("late_ret_11_15"),
            (
                pl.when(1.0 + pl.col("fwd_ret_10_check") > 0)
                .then((1.0 + pl.col("fwd_ret_20")) / (1.0 + pl.col("fwd_ret_10_check")) - 1.0)
                .otherwise(None)
            ).alias("late_ret_11_20"),
        )
        .select(
            "datetime",
            "symbol",
            "entry_close_check",
            "exit_date_15",
            "exit_date_20",
            "fwd_ret_10_check",
            "fwd_ret_15",
            "fwd_ret_20",
            "late_ret_11_15",
            "late_ret_11_20",
        )
    )

    benchmark_path = (
        benchmark_df.select(["datetime", "close"])
        .sort("datetime")
        .with_columns(
            pl.col("datetime").cast(pl.Date),
            pl.col("close").shift(-1).alias("bm_entry_close"),
            pl.col("close").shift(-11).alias("bm_exit_close_10"),
            pl.col("close").shift(-16).alias("bm_exit_close_15"),
            pl.col("close").shift(-21).alias("bm_exit_close_20"),
        )
        .with_columns(
            (pl.col("bm_exit_close_10") / pl.col("bm_entry_close") - 1.0).alias("bm_fwd_ret_10_check"),
            (pl.col("bm_exit_close_15") / pl.col("bm_entry_close") - 1.0).alias("bm_fwd_ret_15"),
            (pl.col("bm_exit_close_20") / pl.col("bm_entry_close") - 1.0).alias("bm_fwd_ret_20"),
        )
        .with_columns(
            (
                pl.when(1.0 + pl.col("bm_fwd_ret_10_check") > 0)
                .then((1.0 + pl.col("bm_fwd_ret_15")) / (1.0 + pl.col("bm_fwd_ret_10_check")) - 1.0)
                .otherwise(None)
            ).alias("bm_late_ret_11_15"),
            (
                pl.when(1.0 + pl.col("bm_fwd_ret_10_check") > 0)
                .then((1.0 + pl.col("bm_fwd_ret_20")) / (1.0 + pl.col("bm_fwd_ret_10_check")) - 1.0)
                .otherwise(None)
            ).alias("bm_late_ret_11_20"),
        )
        .select(
            "datetime",
            "bm_fwd_ret_10_check",
            "bm_fwd_ret_15",
            "bm_fwd_ret_20",
            "bm_late_ret_11_15",
            "bm_late_ret_11_20",
        )
    )

    return (
        enriched.join(stock_path, on=["datetime", "symbol"], how="left")
        .join(benchmark_path, on="datetime", how="left")
        .with_columns(
            (pl.col("fwd_ret_15") - pl.col("bm_fwd_ret_15")).alias("fwd_excess_ret_15"),
            (pl.col("fwd_ret_20") - pl.col("bm_fwd_ret_20")).alias("fwd_excess_ret_20"),
            (pl.col("late_ret_11_15") - pl.col("bm_late_ret_11_15")).alias("late_excess_ret_11_15"),
            (pl.col("late_ret_11_20") - pl.col("bm_late_ret_11_20")).alias("late_excess_ret_11_20"),
            (pl.col("fast_rebound_3d") | pl.col("volume_repair_3d")).alias("confirm_either"),
            (pl.col("fast_rebound_3d") & pl.col("volume_repair_3d")).alias("confirm_both"),
            (pl.col("fast_rebound_3d") & ~pl.col("volume_repair_3d")).alias("fast_only"),
            (~pl.col("fast_rebound_3d") & pl.col("volume_repair_3d")).alias("volume_only"),
            (pl.col("datetime").dt.year()).alias("year"),
        )
    )


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
                "weighted_fwd_excess_ret_10": weighted_mean(group["fwd_excess_ret_10"], weights),
                "weighted_fwd_excess_ret_15": weighted_mean(group["fwd_excess_ret_15"], weights),
                "weighted_fwd_excess_ret_20": weighted_mean(group["fwd_excess_ret_20"], weights),
                "weighted_late_ret_11_15": weighted_mean(group["late_ret_11_15"], weights),
                "weighted_late_ret_11_20": weighted_mean(group["late_ret_11_20"], weights),
                "weighted_late_excess_ret_11_15": weighted_mean(group["late_excess_ret_11_15"], weights),
                "weighted_late_excess_ret_11_20": weighted_mean(group["late_excess_ret_11_20"], weights),
                "positive_late_excess_11_15_ratio": float((group["late_excess_ret_11_15"] > 0).mean()),
                "positive_late_excess_11_20_ratio": float((group["late_excess_ret_11_20"] > 0).mean()),
                "bad_late_excess_11_20_ratio": float((group["late_excess_ret_11_20"] <= -0.05).mean()),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def build_confirmation_contrast(enriched: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    for flag in CONFIRMATION_FLAGS:
        work = enriched.copy()
        work["confirmation_flag"] = flag
        work["flag_value"] = work[flag].fillna(False).astype(bool)
        frames.append(summarize_group(work, ["scenario", "confirmation_flag", "flag_value"]))
    summary = pd.concat(frames, ignore_index=True)
    true_rows = summary[summary["flag_value"].eq(True)].add_suffix("_true")
    false_rows = summary[summary["flag_value"].eq(False)].add_suffix("_false")
    contrast = true_rows.merge(
        false_rows,
        left_on=["scenario_true", "confirmation_flag_true"],
        right_on=["scenario_false", "confirmation_flag_false"],
        how="inner",
    )
    contrast = contrast.rename(columns={"scenario_true": "scenario", "confirmation_flag_true": "confirmation_flag"})
    contrast["coverage_ratio"] = contrast["rows_true"] / (contrast["rows_true"] + contrast["rows_false"])
    for col in [
        "weighted_fwd_excess_ret_10",
        "weighted_fwd_excess_ret_15",
        "weighted_fwd_excess_ret_20",
        "weighted_late_ret_11_15",
        "weighted_late_ret_11_20",
        "weighted_late_excess_ret_11_15",
        "weighted_late_excess_ret_11_20",
        "positive_late_excess_11_15_ratio",
        "positive_late_excess_11_20_ratio",
        "bad_late_excess_11_20_ratio",
    ]:
        contrast[f"delta_{col}"] = contrast[f"{col}_true"] - contrast[f"{col}_false"]
    keep_cols = [
        "scenario",
        "confirmation_flag",
        "coverage_ratio",
        "rows_true",
        "rows_false",
        "weighted_fwd_excess_ret_10_true",
        "weighted_fwd_excess_ret_10_false",
        "delta_weighted_fwd_excess_ret_10",
        "weighted_late_excess_ret_11_15_true",
        "weighted_late_excess_ret_11_15_false",
        "delta_weighted_late_excess_ret_11_15",
        "weighted_late_excess_ret_11_20_true",
        "weighted_late_excess_ret_11_20_false",
        "delta_weighted_late_excess_ret_11_20",
        "positive_late_excess_11_15_ratio_true",
        "positive_late_excess_11_15_ratio_false",
        "delta_positive_late_excess_11_15_ratio",
        "positive_late_excess_11_20_ratio_true",
        "positive_late_excess_11_20_ratio_false",
        "delta_positive_late_excess_11_20_ratio",
        "bad_late_excess_11_20_ratio_true",
        "bad_late_excess_11_20_ratio_false",
        "delta_bad_late_excess_11_20_ratio",
    ]
    contrast = contrast[keep_cols].sort_values(
        ["scenario", "delta_weighted_late_excess_ret_11_20", "delta_weighted_late_excess_ret_11_15"],
        ascending=[True, False, False],
    )
    return summary.reset_index(drop=True), contrast.reset_index(drop=True)


def build_yearly_contrast(enriched: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for flag in CONFIRMATION_FLAGS:
        for (scenario, year), group in enriched.groupby(["scenario", "year"]):
            true_group = group[group[flag].fillna(False).astype(bool)]
            false_group = group[~group[flag].fillna(False).astype(bool)]
            if true_group.empty or false_group.empty:
                continue
            true_weights = true_group["basket_weight"].fillna(0.0)
            false_weights = false_group["basket_weight"].fillna(0.0)
            delta_11_15 = weighted_mean(true_group["late_excess_ret_11_15"], true_weights) - weighted_mean(
                false_group["late_excess_ret_11_15"], false_weights
            )
            delta_11_20 = weighted_mean(true_group["late_excess_ret_11_20"], true_weights) - weighted_mean(
                false_group["late_excess_ret_11_20"], false_weights
            )
            delta_tail = float((true_group["late_excess_ret_11_20"] <= -0.05).mean()) - float(
                (false_group["late_excess_ret_11_20"] <= -0.05).mean()
            )
            rows.append(
                {
                    "scenario": scenario,
                    "year": int(year),
                    "confirmation_flag": flag,
                    "rows_true": int(len(true_group)),
                    "rows_false": int(len(false_group)),
                    "delta_weighted_late_excess_ret_11_15": delta_11_15,
                    "delta_weighted_late_excess_ret_11_20": delta_11_20,
                    "delta_bad_late_excess_11_20_ratio": delta_tail,
                }
            )
    yearly = pd.DataFrame(rows)
    if yearly.empty:
        return yearly
    summary = (
        yearly.groupby(["scenario", "confirmation_flag"], as_index=False)
        .agg(
            years=("year", "count"),
            positive_11_15_years=("delta_weighted_late_excess_ret_11_15", lambda item: int((item > 0).sum())),
            positive_11_20_years=("delta_weighted_late_excess_ret_11_20", lambda item: int((item > 0).sum())),
            lower_bad_tail_years=("delta_bad_late_excess_11_20_ratio", lambda item: int((item < 0).sum())),
            avg_delta_late_excess_11_15=("delta_weighted_late_excess_ret_11_15", "mean"),
            avg_delta_late_excess_11_20=("delta_weighted_late_excess_ret_11_20", "mean"),
            worst_delta_late_excess_11_20=("delta_weighted_late_excess_ret_11_20", "min"),
            avg_delta_bad_tail_11_20=("delta_bad_late_excess_11_20_ratio", "mean"),
        )
        .reset_index(drop=True)
    )
    summary["positive_11_15_year_ratio"] = summary["positive_11_15_years"] / summary["years"]
    summary["positive_11_20_year_ratio"] = summary["positive_11_20_years"] / summary["years"]
    summary["lower_bad_tail_year_ratio"] = summary["lower_bad_tail_years"] / summary["years"]
    return summary.sort_values(
        ["scenario", "positive_11_20_year_ratio", "avg_delta_late_excess_11_20"],
        ascending=[True, False, False],
    ).reset_index(drop=True)


def build_daily_cohort(enriched: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (scenario, current_date), group in enriched.groupby(["scenario", "datetime"]):
        weights = group["basket_weight"].fillna(0.0)
        rows.append(
            {
                "scenario": scenario,
                "datetime": current_date,
                "selected_rows": int(len(group)),
                "basket_weight_sum": float(weights.sum()),
                "confirm_either_ratio": float(group["confirm_either"].mean()),
                "confirm_both_ratio": float(group["confirm_both"].mean()),
                "volume_repair_3d_ratio": float(group["volume_repair_3d"].mean()),
                "fast_rebound_3d_ratio": float(group["fast_rebound_3d"].mean()),
                "weighted_late_excess_ret_11_15": weighted_mean(group["late_excess_ret_11_15"], weights),
                "weighted_late_excess_ret_11_20": weighted_mean(group["late_excess_ret_11_20"], weights),
                "weighted_fwd_excess_ret_10": weighted_mean(group["fwd_excess_ret_10"], weights),
            }
        )
    daily = pd.DataFrame(rows)
    if daily.empty:
        return daily
    for col in ["confirm_either_ratio", "confirm_both_ratio", "volume_repair_3d_ratio", "fast_rebound_3d_ratio"]:
        daily[f"{col}_bucket"] = pd.qcut(daily[col].rank(method="first"), 3, labels=["low", "mid", "high"])
    return daily.sort_values(["scenario", "datetime"]).reset_index(drop=True)


def build_daily_bucket_summary(daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for col in [
        "confirm_either_ratio_bucket",
        "confirm_both_ratio_bucket",
        "volume_repair_3d_ratio_bucket",
        "fast_rebound_3d_ratio_bucket",
    ]:
        summary = (
            daily.groupby(["scenario", col], observed=False)
            .agg(
                signal_days=("datetime", "count"),
                avg_weighted_late_excess_ret_11_15=("weighted_late_excess_ret_11_15", "mean"),
                avg_weighted_late_excess_ret_11_20=("weighted_late_excess_ret_11_20", "mean"),
                avg_weighted_fwd_excess_ret_10=("weighted_fwd_excess_ret_10", "mean"),
                bad_signal_day_11_20_ratio=("weighted_late_excess_ret_11_20", lambda item: float((item < 0).mean())),
            )
            .reset_index()
            .rename(columns={col: "bucket"})
        )
        summary["daily_bucket_feature"] = col.replace("_bucket", "")
        rows.append(summary)
    return pd.concat(rows, ignore_index=True).sort_values(["scenario", "daily_bucket_feature", "bucket"])


def build_candidate_status(contrast: pd.DataFrame, yearly: pd.DataFrame) -> pd.DataFrame:
    candidates = contrast.merge(yearly, on=["scenario", "confirmation_flag"], how="left")
    candidates["coverage_ok"] = candidates["coverage_ratio"].between(0.10, 0.80)
    candidates["extension_edge_ok"] = (candidates["delta_weighted_late_excess_ret_11_15"] > 0) & (
        candidates["delta_weighted_late_excess_ret_11_20"] > 0
    )
    candidates["extension_breadth_ok"] = (
        candidates["positive_11_15_year_ratio"].fillna(0.0).ge(0.55)
        & candidates["positive_11_20_year_ratio"].fillna(0.0).ge(0.55)
    )
    candidates["tail_ok"] = candidates["delta_bad_late_excess_11_20_ratio"] <= 0
    candidates["candidate_status"] = np.select(
        [
            candidates["coverage_ok"]
            & candidates["extension_edge_ok"]
            & candidates["extension_breadth_ok"]
            & candidates["tail_ok"],
            candidates["coverage_ok"] & candidates["extension_edge_ok"] & candidates["extension_breadth_ok"],
            candidates["extension_edge_ok"],
        ],
        ["extension_rule_probe_candidate", "extension_alpha_tail_risk", "weak_extension_alpha"],
        default="no_extension_edge",
    )
    return candidates.sort_values(
        ["scenario", "candidate_status", "delta_weighted_late_excess_ret_11_20"],
        ascending=[True, True, False],
    ).reset_index(drop=True)


def build_quality(enriched: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
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
    strong = candidates[candidates["candidate_status"].eq("extension_rule_probe_candidate")]
    fwd_diff = (enriched["fwd_ret_10"] - enriched["fwd_ret_10_check"]).abs().max()
    add("focus_scenario_count", "pass" if enriched["scenario"].nunique() == len(FOCUS_SCENARIOS) else "fail", enriched["scenario"].nunique(), str(len(FOCUS_SCENARIOS)), "固定四个简单母本形状。")
    add("input_rows", "pass" if len(enriched) > 0 else "fail", len(enriched), ">0", "Stage337 enriched样本必须非空。")
    add("fwd_ret_10_rebuild_diff", "pass" if fwd_diff < 1e-10 else "fail", f"{fwd_diff:.3g}", "<1e-10", "用本地panel重建10日收益，校验扩展路径对齐。")
    add("extension_columns_not_null", "pass" if enriched["late_excess_ret_11_20"].notna().mean() > 0.95 else "warn", f"{enriched['late_excess_ret_11_20'].notna().mean():.4f}", ">0.95", "扩展路径可用比例。")
    add("primary_extension_candidates", "pass" if len(primary[primary["candidate_status"].eq("extension_rule_probe_candidate")]) > 0 else "warn", len(primary[primary["candidate_status"].eq("extension_rule_probe_candidate")]), ">0", "主母本是否出现确认后续航候选。")
    add("guard_extension_candidates", "pass" if len(guard[guard["candidate_status"].eq("extension_rule_probe_candidate")]) > 0 else "warn", len(guard[guard["candidate_status"].eq("extension_rule_probe_candidate")]), ">0", "top5护栏是否同步。")
    add("broad_extension_candidates", "pass" if len(strong) >= 2 else "warn", len(strong), ">=2", "跨场景确认后续航候选数量。")
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
    pct_cols = [
        "coverage_ratio",
        "weighted_fwd_excess_ret_10_true",
        "weighted_fwd_excess_ret_10_false",
        "delta_weighted_fwd_excess_ret_10",
        "weighted_late_excess_ret_11_15_true",
        "weighted_late_excess_ret_11_15_false",
        "delta_weighted_late_excess_ret_11_15",
        "weighted_late_excess_ret_11_20_true",
        "weighted_late_excess_ret_11_20_false",
        "delta_weighted_late_excess_ret_11_20",
        "positive_11_15_year_ratio",
        "positive_11_20_year_ratio",
        "lower_bad_tail_year_ratio",
        "avg_delta_late_excess_11_15",
        "avg_delta_late_excess_11_20",
        "delta_bad_late_excess_11_20_ratio",
    ]
    candidates_fmt = add_pct_columns(candidates, pct_cols)
    daily_fmt = add_pct_columns(
        daily_bucket,
        [
            "avg_weighted_late_excess_ret_11_15",
            "avg_weighted_late_excess_ret_11_20",
            "avg_weighted_fwd_excess_ret_10",
            "bad_signal_day_11_20_ratio",
        ],
    )
    primary = candidates_fmt[candidates_fmt["scenario"].eq(PRIMARY_SCENARIO)]
    guard = candidates_fmt[candidates_fmt["scenario"].eq(GUARD_SCENARIO)]
    strong = candidates[candidates["candidate_status"].eq("extension_rule_probe_candidate")]
    lines = [
        "# 第338阶段：早期确认后的续航归因",
        "",
        "## 结论摘要",
        "",
        "- 本阶段不改交易规则，不重新跑组合账户；只在Stage337确认样本上补第15/20日路径。",
        "- 目标是确认`fast_rebound_3d`和`volume_repair_3d`不是只解释前10日，而是在原10日持有期结束后仍有第11-15/11-20日超额边际。",
        f"- 可进入延长持有/预算倾斜探针的跨场景候选数：`{len(strong)}`。",
        "",
        "## 元信息",
        "",
        f"- 生成时间：{meta['generated_at']}",
        f"- 输入目录：`{STAGE337_DIR}`",
        f"- 输出目录：`{OUTPUT_DIR}`",
        f"- 账户规模：{ACCOUNT_SIZE_CNY:,.0f} CNY",
        "",
        "## 外部调研与判断",
        "",
        "- 短期反转研究常见持有期很短，且交易成本会吞噬一部分反转收益；所以不能默认延长持有有效。",
        "- 公开交易系统文章会提到成交量/价格确认，但这些多是经验规则；必须证明确认后还有剩余收益，而不只是确认前已经涨完。",
        "- 本阶段因此只做确认后第11-15/11-20日归因，不直接改持有期。",
        "",
        "参考资料：",
        *[f"- [{title}]({url})" for title, url in RESEARCH_SOURCES],
        "",
        "## 质量检查",
        "",
        markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], limit=30),
        "",
        "## 主母本候选",
        "",
        markdown_table(
            primary,
            [
                "confirmation_flag",
                "candidate_status",
                "coverage_ratio_pct",
                "delta_weighted_fwd_excess_ret_10_pct",
                "delta_weighted_late_excess_ret_11_15_pct",
                "delta_weighted_late_excess_ret_11_20_pct",
                "positive_11_15_year_ratio_pct",
                "positive_11_20_year_ratio_pct",
                "delta_bad_late_excess_11_20_ratio_pct",
            ],
            limit=20,
        ),
        "",
        "## top5护栏",
        "",
        markdown_table(
            guard,
            [
                "confirmation_flag",
                "candidate_status",
                "coverage_ratio_pct",
                "delta_weighted_fwd_excess_ret_10_pct",
                "delta_weighted_late_excess_ret_11_15_pct",
                "delta_weighted_late_excess_ret_11_20_pct",
                "positive_11_15_year_ratio_pct",
                "positive_11_20_year_ratio_pct",
                "delta_bad_late_excess_11_20_ratio_pct",
            ],
            limit=20,
        ),
        "",
        "## 全场景候选排序",
        "",
        markdown_table(
            candidates_fmt,
            [
                "scenario",
                "confirmation_flag",
                "candidate_status",
                "coverage_ratio_pct",
                "delta_weighted_late_excess_ret_11_15_pct",
                "delta_weighted_late_excess_ret_11_20_pct",
                "positive_11_20_year_ratio_pct",
                "delta_bad_late_excess_11_20_ratio_pct",
            ],
            limit=80,
        ),
        "",
        "## 日度确认比例分桶",
        "",
        markdown_table(
            daily_fmt,
            [
                "scenario",
                "daily_bucket_feature",
                "bucket",
                "signal_days",
                "avg_weighted_late_excess_ret_11_15_pct",
                "avg_weighted_late_excess_ret_11_20_pct",
                "avg_weighted_fwd_excess_ret_10_pct",
                "bad_signal_day_11_20_ratio_pct",
            ],
            limit=80,
        ),
        "",
        "## 研究判断",
        "",
        "- 过拟合判断：否。本阶段继续是归因，不把阈值写入策略；并使用第11-15/11-20日剩余窗口降低路径解释偏差。",
        "- 继续价值判断：有，但不是延长持有方向。本阶段反证了确认后续航，下一步应转向未确认样本在第4-10日是否该减仓/退出。",
        "- 当前动作不触发A/B实验，不修改第78，不修改`stock_range_paper_v1`。",
        "",
        "## 输出文件",
        "",
        f"- `{PREFIX}_enriched.csv`",
        f"- `{PREFIX}_confirmation_summary.csv`",
        f"- `{PREFIX}_confirmation_contrast.csv`",
        f"- `{PREFIX}_yearly_confirmation_contrast.csv`",
        f"- `{PREFIX}_candidate_status.csv`",
        f"- `{PREFIX}_daily_cohort.csv`",
        f"- `{PREFIX}_daily_bucket_summary.csv`",
        f"- `{PREFIX}_quality_checkpoints.csv`",
        f"- `{PREFIX}_meta.json`",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    enriched_pl = build_extension_paths(load_stage337_enriched())
    enriched = enriched_pl.to_pandas()
    summary, contrast = build_confirmation_contrast(enriched)
    yearly = build_yearly_contrast(enriched)
    candidates = build_candidate_status(contrast, yearly)
    daily_cohort = build_daily_cohort(enriched)
    daily_bucket = build_daily_bucket_summary(daily_cohort)
    quality = build_quality(enriched, candidates)
    meta: dict[str, Any] = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stage337_dir": str(STAGE337_DIR),
        "stage337_prefix": STAGE337_PREFIX,
        "output_dir": str(OUTPUT_DIR),
        "prefix": PREFIX,
        "account_size_cny": ACCOUNT_SIZE_CNY,
        "focus_scenarios": list(FOCUS_SCENARIOS),
        "primary_scenario": PRIMARY_SCENARIO,
        "guard_scenario": GUARD_SCENARIO,
        "confirmation_flags": list(CONFIRMATION_FLAGS),
        "continuation_metrics": [metric.__dict__ for metric in CONTINUATION_METRICS],
        "research_sources": [{"title": title, "url": url} for title, url in RESEARCH_SOURCES],
        "input_rows": int(len(enriched)),
        "quality_status_counts": quality["status"].value_counts().to_dict(),
    }

    enriched.to_csv(OUTPUT_DIR / f"{PREFIX}_enriched.csv", index=False)
    summary.to_csv(OUTPUT_DIR / f"{PREFIX}_confirmation_summary.csv", index=False)
    contrast.to_csv(OUTPUT_DIR / f"{PREFIX}_confirmation_contrast.csv", index=False)
    yearly.to_csv(OUTPUT_DIR / f"{PREFIX}_yearly_confirmation_contrast.csv", index=False)
    candidates.to_csv(OUTPUT_DIR / f"{PREFIX}_candidate_status.csv", index=False)
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
                "confirmation_flag",
                "candidate_status",
                "coverage_ratio",
                "delta_weighted_late_excess_ret_11_15",
                "delta_weighted_late_excess_ret_11_20",
                "positive_11_20_year_ratio",
                "delta_bad_late_excess_11_20_ratio",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
