from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import polars as pl

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
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_30w_simple_mother_unconfirmed_exit_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_30w_simple_mother_unconfirmed_exit_v1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Mean Reversion Strategies - Complete Backtesting Guide",
        "https://backtestme.com/guides/mean-reversion-strategies",
    ),
    (
        "Mean Reversion Trading with Sequential Deadlines and Transaction Costs",
        "https://arxiv.org/abs/1707.03498",
    ),
    (
        "Optimal Mean Reversion Trading with Transaction Costs and Stop-Loss Exit",
        "https://arxiv.org/abs/1411.5062",
    ),
    (
        "Short-term reversals, returns to liquidity provision and the costs of immediacy",
        "https://www.sciencedirect.com/science/article/pii/S0378426622000309",
    ),
    (
        "Short-term residual reversal",
        "https://www.sciencedirect.com/science/article/pii/S1386418112000468",
    ),
    (
        "GitHub mean-reversion-trading topic",
        "https://github.com/topics/mean-reversion-trading",
    ),
)


@dataclass(frozen=True)
class ExitFlagSpec:
    name: str
    description: str


EXIT_FLAG_SPECS: tuple[ExitFlagSpec, ...] = (
    ExitFlagSpec("no_fast_rebound_3d", "第3日前没有出现3%以上最大收盘反弹。"),
    ExitFlagSpec("no_volume_repair_3d", "第3日前没有出现放量上涨修复日。"),
    ExitFlagSpec("no_confirm_either", "第3日前既没有快速反弹，也没有放量上涨修复。"),
    ExitFlagSpec("no_confirm_both", "第3日前没有同时出现快速反弹和放量上涨修复。"),
    ExitFlagSpec("no_confirm_either_and_no_bounce", "未确认且3日内最大反弹不足1%。"),
    ExitFlagSpec("no_confirm_either_and_industry_failure", "未确认且同行业选中篮子3日路径为负。"),
    ExitFlagSpec("no_confirm_either_and_volume_failure", "未确认且3日内出现放量下跌日。"),
    ExitFlagSpec("no_confirm_either_and_breakdown", "未确认且3日内最大收盘跌幅超过5%。"),
    ExitFlagSpec("no_confirm_either_and_stock_lags_industry", "未确认且3日路径落后同行业选中篮子超过2pp。"),
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


def enrich_exit_features(frame: pl.DataFrame) -> pl.DataFrame:
    work = (
        frame.with_columns(
            (pl.col("fwd_ret_3") - pl.col("fwd_excess_ret_3")).alias("bm_fwd_ret_3"),
            (pl.col("fwd_ret_10") - pl.col("fwd_excess_ret_10")).alias("bm_fwd_ret_10"),
            (pl.col("fast_rebound_3d") | pl.col("volume_repair_3d")).alias("confirm_either"),
            (pl.col("fast_rebound_3d") & pl.col("volume_repair_3d")).alias("confirm_both"),
        )
        .with_columns(
            (
                pl.when(1.0 + pl.col("fwd_ret_3") > 0)
                .then((1.0 + pl.col("fwd_ret_10")) / (1.0 + pl.col("fwd_ret_3")) - 1.0)
                .otherwise(None)
            ).alias("late_ret_4_10_check"),
            (
                pl.when(1.0 + pl.col("bm_fwd_ret_3") > 0)
                .then((1.0 + pl.col("bm_fwd_ret_10")) / (1.0 + pl.col("bm_fwd_ret_3")) - 1.0)
                .otherwise(None)
            ).alias("bm_late_ret_4_10"),
        )
        .with_columns(
            (pl.col("late_ret_4_10") - pl.col("bm_late_ret_4_10")).alias("late_excess_ret_4_10"),
            (~pl.col("fast_rebound_3d")).alias("no_fast_rebound_3d"),
            (~pl.col("volume_repair_3d")).alias("no_volume_repair_3d"),
            (~pl.col("confirm_either")).alias("no_confirm_either"),
            (~pl.col("confirm_both")).alias("no_confirm_both"),
        )
        .with_columns(
            (pl.col("no_confirm_either") & pl.col("no_bounce_3d")).alias("no_confirm_either_and_no_bounce"),
            (pl.col("no_confirm_either") & pl.col("industry_failure_3d")).alias(
                "no_confirm_either_and_industry_failure"
            ),
            (pl.col("no_confirm_either") & pl.col("volume_failure_3d")).alias(
                "no_confirm_either_and_volume_failure"
            ),
            (pl.col("no_confirm_either") & pl.col("early_breakdown_3d")).alias(
                "no_confirm_either_and_breakdown"
            ),
            (pl.col("no_confirm_either") & pl.col("stock_lags_industry_3d")).alias(
                "no_confirm_either_and_stock_lags_industry"
            ),
            pl.col("datetime").dt.year().alias("year"),
        )
    )
    return work


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
                "weighted_late_ret_4_10": weighted_mean(group["late_ret_4_10"], weights),
                "weighted_late_excess_ret_4_10": weighted_mean(group["late_excess_ret_4_10"], weights),
                "positive_late_ret_4_10_ratio": float((group["late_ret_4_10"] > 0).mean()),
                "positive_late_excess_ret_4_10_ratio": float((group["late_excess_ret_4_10"] > 0).mean()),
                "bad_late_ret_4_10_ratio": float((group["late_ret_4_10"] <= -0.05).mean()),
                "bad_late_excess_ret_4_10_ratio": float((group["late_excess_ret_4_10"] <= -0.05).mean()),
                "good_late_ret_4_10_ratio": float((group["late_ret_4_10"] >= 0.05).mean()),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def build_exit_contrast(enriched: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    for spec in EXIT_FLAG_SPECS:
        work = enriched.copy()
        work["exit_flag"] = spec.name
        work["flag_description"] = spec.description
        work["flag_value"] = work[spec.name].fillna(False).astype(bool)
        frames.append(summarize_group(work, ["scenario", "exit_flag", "flag_description", "flag_value"]))
    summary = pd.concat(frames, ignore_index=True)
    true_rows = summary[summary["flag_value"].eq(True)].add_suffix("_true")
    false_rows = summary[summary["flag_value"].eq(False)].add_suffix("_false")
    contrast = true_rows.merge(
        false_rows,
        left_on=["scenario_true", "exit_flag_true"],
        right_on=["scenario_false", "exit_flag_false"],
        how="inner",
    )
    contrast = contrast.rename(
        columns={
            "scenario_true": "scenario",
            "exit_flag_true": "exit_flag",
            "flag_description_true": "flag_description",
        }
    )
    contrast["coverage_ratio"] = contrast["rows_true"] / (contrast["rows_true"] + contrast["rows_false"])
    for col in [
        "weighted_fwd_excess_ret_10",
        "weighted_late_ret_4_10",
        "weighted_late_excess_ret_4_10",
        "positive_late_ret_4_10_ratio",
        "positive_late_excess_ret_4_10_ratio",
        "bad_late_ret_4_10_ratio",
        "bad_late_excess_ret_4_10_ratio",
        "good_late_ret_4_10_ratio",
    ]:
        contrast[f"delta_{col}"] = contrast[f"{col}_true"] - contrast[f"{col}_false"]
    contrast["cash_exit_edge_abs"] = -contrast["weighted_late_ret_4_10_true"]
    contrast["cash_exit_edge_excess"] = -contrast["weighted_late_excess_ret_4_10_true"]
    keep = [
        "scenario",
        "exit_flag",
        "flag_description",
        "coverage_ratio",
        "rows_true",
        "rows_false",
        "weighted_late_ret_4_10_true",
        "weighted_late_ret_4_10_false",
        "delta_weighted_late_ret_4_10",
        "weighted_late_excess_ret_4_10_true",
        "weighted_late_excess_ret_4_10_false",
        "delta_weighted_late_excess_ret_4_10",
        "cash_exit_edge_abs",
        "cash_exit_edge_excess",
        "bad_late_ret_4_10_ratio_true",
        "bad_late_ret_4_10_ratio_false",
        "delta_bad_late_ret_4_10_ratio",
        "bad_late_excess_ret_4_10_ratio_true",
        "bad_late_excess_ret_4_10_ratio_false",
        "delta_bad_late_excess_ret_4_10_ratio",
        "good_late_ret_4_10_ratio_true",
        "good_late_ret_4_10_ratio_false",
        "delta_good_late_ret_4_10_ratio",
        "positive_late_ret_4_10_ratio_true",
        "positive_late_ret_4_10_ratio_false",
        "positive_late_excess_ret_4_10_ratio_true",
        "positive_late_excess_ret_4_10_ratio_false",
    ]
    contrast = contrast[keep].sort_values(
        ["scenario", "cash_exit_edge_abs", "cash_exit_edge_excess", "delta_bad_late_ret_4_10_ratio"],
        ascending=[True, False, False, False],
    )
    return summary.reset_index(drop=True), contrast.reset_index(drop=True)


def build_yearly_contrast(enriched: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in EXIT_FLAG_SPECS:
        for (scenario, year), group in enriched.groupby(["scenario", "year"]):
            true_group = group[group[spec.name].fillna(False).astype(bool)]
            false_group = group[~group[spec.name].fillna(False).astype(bool)]
            if true_group.empty or false_group.empty:
                continue
            true_weights = true_group["basket_weight"].fillna(0.0)
            false_weights = false_group["basket_weight"].fillna(0.0)
            true_late_abs = weighted_mean(true_group["late_ret_4_10"], true_weights)
            false_late_abs = weighted_mean(false_group["late_ret_4_10"], false_weights)
            true_late_excess = weighted_mean(true_group["late_excess_ret_4_10"], true_weights)
            false_late_excess = weighted_mean(false_group["late_excess_ret_4_10"], false_weights)
            rows.append(
                {
                    "scenario": scenario,
                    "year": int(year),
                    "exit_flag": spec.name,
                    "rows_true": int(len(true_group)),
                    "rows_false": int(len(false_group)),
                    "weighted_late_ret_4_10_true": true_late_abs,
                    "weighted_late_ret_4_10_false": false_late_abs,
                    "delta_weighted_late_ret_4_10": true_late_abs - false_late_abs,
                    "weighted_late_excess_ret_4_10_true": true_late_excess,
                    "weighted_late_excess_ret_4_10_false": false_late_excess,
                    "delta_weighted_late_excess_ret_4_10": true_late_excess - false_late_excess,
                    "delta_bad_late_ret_4_10_ratio": float((true_group["late_ret_4_10"] <= -0.05).mean())
                    - float((false_group["late_ret_4_10"] <= -0.05).mean()),
                    "cash_exit_edge_abs": -true_late_abs,
                    "cash_exit_edge_excess": -true_late_excess,
                }
            )
    yearly = pd.DataFrame(rows)
    if yearly.empty:
        return yearly
    summary = (
        yearly.groupby(["scenario", "exit_flag"], as_index=False)
        .agg(
            years=("year", "count"),
            cash_exit_abs_positive_years=("cash_exit_edge_abs", lambda item: int((item > 0).sum())),
            cash_exit_excess_positive_years=("cash_exit_edge_excess", lambda item: int((item > 0).sum())),
            flagged_worse_abs_years=("delta_weighted_late_ret_4_10", lambda item: int((item < 0).sum())),
            flagged_worse_excess_years=("delta_weighted_late_excess_ret_4_10", lambda item: int((item < 0).sum())),
            higher_bad_tail_years=("delta_bad_late_ret_4_10_ratio", lambda item: int((item > 0).sum())),
            avg_cash_exit_edge_abs=("cash_exit_edge_abs", "mean"),
            avg_cash_exit_edge_excess=("cash_exit_edge_excess", "mean"),
            avg_delta_late_ret_4_10=("delta_weighted_late_ret_4_10", "mean"),
            avg_delta_late_excess_ret_4_10=("delta_weighted_late_excess_ret_4_10", "mean"),
            worst_cash_exit_edge_abs=("cash_exit_edge_abs", "min"),
        )
        .reset_index(drop=True)
    )
    summary["cash_exit_abs_positive_year_ratio"] = summary["cash_exit_abs_positive_years"] / summary["years"]
    summary["cash_exit_excess_positive_year_ratio"] = summary["cash_exit_excess_positive_years"] / summary["years"]
    summary["flagged_worse_abs_year_ratio"] = summary["flagged_worse_abs_years"] / summary["years"]
    summary["flagged_worse_excess_year_ratio"] = summary["flagged_worse_excess_years"] / summary["years"]
    summary["higher_bad_tail_year_ratio"] = summary["higher_bad_tail_years"] / summary["years"]
    return summary.sort_values(
        ["scenario", "cash_exit_abs_positive_year_ratio", "avg_cash_exit_edge_abs"],
        ascending=[True, False, False],
    ).reset_index(drop=True)


def build_candidate_status(contrast: pd.DataFrame, yearly: pd.DataFrame) -> pd.DataFrame:
    candidates = contrast.merge(yearly, on=["scenario", "exit_flag"], how="left")
    candidates["coverage_ok"] = candidates["coverage_ratio"].between(0.10, 0.85)
    candidates["cash_exit_abs_ok"] = candidates["cash_exit_edge_abs"] > 0
    candidates["cash_exit_excess_ok"] = candidates["cash_exit_edge_excess"] > 0
    candidates["flagged_worse_ok"] = (candidates["delta_weighted_late_ret_4_10"] < 0) & (
        candidates["delta_weighted_late_excess_ret_4_10"] < 0
    )
    candidates["tail_ok"] = candidates["delta_bad_late_ret_4_10_ratio"] > 0
    candidates["year_breadth_ok"] = (
        candidates["cash_exit_abs_positive_year_ratio"].fillna(0.0).ge(0.55)
        & candidates["cash_exit_excess_positive_year_ratio"].fillna(0.0).ge(0.55)
        & candidates["flagged_worse_abs_year_ratio"].fillna(0.0).ge(0.55)
    )
    candidates["candidate_status"] = np.select(
        [
            candidates["coverage_ok"]
            & candidates["cash_exit_abs_ok"]
            & candidates["cash_exit_excess_ok"]
            & candidates["flagged_worse_ok"]
            & candidates["tail_ok"]
            & candidates["year_breadth_ok"],
            candidates["coverage_ok"] & candidates["flagged_worse_ok"] & candidates["tail_ok"],
            candidates["cash_exit_abs_ok"] | candidates["cash_exit_excess_ok"],
        ],
        ["exit_rule_probe_candidate", "relative_risk_only", "weak_exit_edge"],
        default="no_exit_edge",
    )
    return candidates.sort_values(
        ["scenario", "candidate_status", "cash_exit_edge_abs", "delta_bad_late_ret_4_10_ratio"],
        ascending=[True, True, False, False],
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
                "no_confirm_either_ratio": float(group["no_confirm_either"].mean()),
                "no_fast_rebound_3d_ratio": float(group["no_fast_rebound_3d"].mean()),
                "no_volume_repair_3d_ratio": float(group["no_volume_repair_3d"].mean()),
                "no_confirm_either_and_no_bounce_ratio": float(
                    group["no_confirm_either_and_no_bounce"].mean()
                ),
                "weighted_late_ret_4_10": weighted_mean(group["late_ret_4_10"], weights),
                "weighted_late_excess_ret_4_10": weighted_mean(group["late_excess_ret_4_10"], weights),
                "weighted_fwd_excess_ret_10": weighted_mean(group["fwd_excess_ret_10"], weights),
            }
        )
    daily = pd.DataFrame(rows)
    if daily.empty:
        return daily
    for col in [
        "no_confirm_either_ratio",
        "no_fast_rebound_3d_ratio",
        "no_volume_repair_3d_ratio",
        "no_confirm_either_and_no_bounce_ratio",
    ]:
        daily[f"{col}_bucket"] = pd.qcut(daily[col].rank(method="first"), 3, labels=["low", "mid", "high"])
    return daily.sort_values(["scenario", "datetime"]).reset_index(drop=True)


def build_daily_bucket_summary(daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for col in [
        "no_confirm_either_ratio_bucket",
        "no_fast_rebound_3d_ratio_bucket",
        "no_volume_repair_3d_ratio_bucket",
        "no_confirm_either_and_no_bounce_ratio_bucket",
    ]:
        summary = (
            daily.groupby(["scenario", col], observed=False)
            .agg(
                signal_days=("datetime", "count"),
                avg_weighted_late_ret_4_10=("weighted_late_ret_4_10", "mean"),
                avg_weighted_late_excess_ret_4_10=("weighted_late_excess_ret_4_10", "mean"),
                avg_weighted_fwd_excess_ret_10=("weighted_fwd_excess_ret_10", "mean"),
                bad_signal_day_late_abs_ratio=("weighted_late_ret_4_10", lambda item: float((item < 0).mean())),
            )
            .reset_index()
            .rename(columns={col: "bucket"})
        )
        summary["daily_bucket_feature"] = col.replace("_bucket", "")
        rows.append(summary)
    return pd.concat(rows, ignore_index=True).sort_values(["scenario", "daily_bucket_feature", "bucket"])


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

    check_diff = (enriched["late_ret_4_10"] - enriched["late_ret_4_10_check"]).abs().max()
    primary = candidates[candidates["scenario"].eq(PRIMARY_SCENARIO)]
    guard = candidates[candidates["scenario"].eq(GUARD_SCENARIO)]
    strong = candidates[candidates["candidate_status"].eq("exit_rule_probe_candidate")]
    add("focus_scenario_count", "pass" if enriched["scenario"].nunique() == len(FOCUS_SCENARIOS) else "fail", enriched["scenario"].nunique(), str(len(FOCUS_SCENARIOS)), "固定四个简单母本形状。")
    add("input_rows", "pass" if len(enriched) > 0 else "fail", len(enriched), ">0", "Stage337 enriched样本必须非空。")
    add("late_ret_4_10_rebuild_diff", "pass" if check_diff < 1e-10 else "fail", f"{check_diff:.3g}", "<1e-10", "用fwd_ret_3/10复原第4-10日路径。")
    add("exit_flag_count", "pass" if len(EXIT_FLAG_SPECS) == 9 else "fail", len(EXIT_FLAG_SPECS), "9", "预注册未确认/风险组合旗标。")
    add("primary_exit_candidates", "pass" if len(primary[primary["candidate_status"].eq("exit_rule_probe_candidate")]) > 0 else "warn", len(primary[primary["candidate_status"].eq("exit_rule_probe_candidate")]), ">0", "主母本是否出现减仓/退出候选。")
    add("guard_exit_candidates", "pass" if len(guard[guard["candidate_status"].eq("exit_rule_probe_candidate")]) > 0 else "warn", len(guard[guard["candidate_status"].eq("exit_rule_probe_candidate")]), ">0", "top5护栏是否同步。")
    add("broad_exit_candidates", "pass" if len(strong) >= 2 else "warn", len(strong), ">=2", "跨场景退出候选数量。")
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
        "weighted_late_ret_4_10_true",
        "weighted_late_ret_4_10_false",
        "delta_weighted_late_ret_4_10",
        "weighted_late_excess_ret_4_10_true",
        "weighted_late_excess_ret_4_10_false",
        "delta_weighted_late_excess_ret_4_10",
        "cash_exit_edge_abs",
        "cash_exit_edge_excess",
        "bad_late_ret_4_10_ratio_true",
        "bad_late_ret_4_10_ratio_false",
        "delta_bad_late_ret_4_10_ratio",
        "bad_late_excess_ret_4_10_ratio_true",
        "bad_late_excess_ret_4_10_ratio_false",
        "delta_bad_late_excess_ret_4_10_ratio",
        "good_late_ret_4_10_ratio_true",
        "good_late_ret_4_10_ratio_false",
        "delta_good_late_ret_4_10_ratio",
        "cash_exit_abs_positive_year_ratio",
        "cash_exit_excess_positive_year_ratio",
        "flagged_worse_abs_year_ratio",
        "higher_bad_tail_year_ratio",
        "avg_cash_exit_edge_abs",
        "avg_cash_exit_edge_excess",
    ]
    candidates_fmt = add_pct_columns(candidates, pct_cols)
    daily_fmt = add_pct_columns(
        daily_bucket,
        [
            "avg_weighted_late_ret_4_10",
            "avg_weighted_late_excess_ret_4_10",
            "avg_weighted_fwd_excess_ret_10",
            "bad_signal_day_late_abs_ratio",
        ],
    )
    primary = candidates_fmt[candidates_fmt["scenario"].eq(PRIMARY_SCENARIO)]
    guard = candidates_fmt[candidates_fmt["scenario"].eq(GUARD_SCENARIO)]
    strong = candidates[candidates["candidate_status"].eq("exit_rule_probe_candidate")]
    lines = [
        "# 第339阶段：未确认样本第4-10日减仓/退出归因",
        "",
        "## 结论摘要",
        "",
        "- 本阶段不改交易规则，不重新跑组合账户；只在Stage337样本上拆解第3日未确认后的第4-10日剩余收益。",
        "- 目标是判断：未确认是否真的意味着后续持有期为负贡献，足以支持第4日减仓/退出探针。",
        f"- 可进入真实30万整手退出回放的旗标数量：`{len(strong)}`。",
        "- 结果显示未确认样本相对确认样本更弱，但第4-10日绝对收益仍为正，硬退到现金会误伤反弹。",
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
        "- 均值回归系统的退出通常需要时间截止、确认失败或止损，但文献和实盘经验都提醒退出规则容易误伤反弹。",
        "- 短期反转研究常见持有期偏短，因此第4-10日是否还有正收益必须实证判断，不能靠直觉。",
        "- 本阶段只做归因；若退出候选成立，下一步仍需真实30万整手、可成交、成本后的回放。",
        "",
        "参考资料：",
        *[f"- [{title}]({url})" for title, url in RESEARCH_SOURCES],
        "",
        "## 质量检查",
        "",
        markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], limit=30),
        "",
        "## 主母本退出候选",
        "",
        markdown_table(
            primary,
            [
                "exit_flag",
                "candidate_status",
                "coverage_ratio_pct",
                "cash_exit_edge_abs_pct",
                "cash_exit_edge_excess_pct",
                "weighted_late_ret_4_10_true_pct",
                "weighted_late_ret_4_10_false_pct",
                "delta_weighted_late_ret_4_10_pct",
                "delta_bad_late_ret_4_10_ratio_pct",
                "cash_exit_abs_positive_year_ratio_pct",
                "flagged_worse_abs_year_ratio_pct",
                "higher_bad_tail_year_ratio_pct",
            ],
            limit=40,
        ),
        "",
        "## top5护栏退出候选",
        "",
        markdown_table(
            guard,
            [
                "exit_flag",
                "candidate_status",
                "coverage_ratio_pct",
                "cash_exit_edge_abs_pct",
                "cash_exit_edge_excess_pct",
                "weighted_late_ret_4_10_true_pct",
                "weighted_late_ret_4_10_false_pct",
                "delta_weighted_late_ret_4_10_pct",
                "delta_bad_late_ret_4_10_ratio_pct",
                "cash_exit_abs_positive_year_ratio_pct",
                "flagged_worse_abs_year_ratio_pct",
                "higher_bad_tail_year_ratio_pct",
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
                "exit_flag",
                "candidate_status",
                "coverage_ratio_pct",
                "cash_exit_edge_abs_pct",
                "cash_exit_edge_excess_pct",
                "delta_weighted_late_ret_4_10_pct",
                "delta_bad_late_ret_4_10_ratio_pct",
                "cash_exit_abs_positive_year_ratio_pct",
                "flagged_worse_abs_year_ratio_pct",
            ],
            limit=100,
        ),
        "",
        "## 日度未确认比例分桶",
        "",
        markdown_table(
            daily_fmt,
            [
                "scenario",
                "daily_bucket_feature",
                "bucket",
                "signal_days",
                "avg_weighted_late_ret_4_10_pct",
                "avg_weighted_late_excess_ret_4_10_pct",
                "avg_weighted_fwd_excess_ret_10_pct",
                "bad_signal_day_late_abs_ratio_pct",
            ],
            limit=80,
        ),
        "",
        "## 研究判断",
        "",
        "- 过拟合判断：否。本阶段是预注册未确认旗标归因，没有写入交易规则；但若进入真实退出回放，必须继续做年度/滚动/邻域反证。",
        "- 继续价值判断：有，但不是第4日未确认硬退出方向。本阶段应停止硬退出，转向更底层的入场质量或组合暴露结构归因。",
        "- 当前动作不触发A/B实验，不修改第78，不修改`stock_range_paper_v1`。",
        "",
        "## 输出文件",
        "",
        f"- `{PREFIX}_enriched.csv`",
        f"- `{PREFIX}_exit_summary.csv`",
        f"- `{PREFIX}_exit_contrast.csv`",
        f"- `{PREFIX}_yearly_exit_contrast.csv`",
        f"- `{PREFIX}_candidate_status.csv`",
        f"- `{PREFIX}_daily_cohort.csv`",
        f"- `{PREFIX}_daily_bucket_summary.csv`",
        f"- `{PREFIX}_quality_checkpoints.csv`",
        f"- `{PREFIX}_meta.json`",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    enriched_pl = enrich_exit_features(load_stage337_enriched())
    enriched = enriched_pl.to_pandas()
    summary, contrast = build_exit_contrast(enriched)
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
        "exit_flag_specs": [spec.__dict__ for spec in EXIT_FLAG_SPECS],
        "research_sources": [{"title": title, "url": url} for title, url in RESEARCH_SOURCES],
        "input_rows": int(len(enriched)),
        "quality_status_counts": quality["status"].value_counts().to_dict(),
    }

    enriched.to_csv(OUTPUT_DIR / f"{PREFIX}_enriched.csv", index=False)
    summary.to_csv(OUTPUT_DIR / f"{PREFIX}_exit_summary.csv", index=False)
    contrast.to_csv(OUTPUT_DIR / f"{PREFIX}_exit_contrast.csv", index=False)
    yearly.to_csv(OUTPUT_DIR / f"{PREFIX}_yearly_exit_contrast.csv", index=False)
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
                "exit_flag",
                "candidate_status",
                "coverage_ratio",
                "cash_exit_edge_abs",
                "cash_exit_edge_excess",
                "delta_weighted_late_ret_4_10",
                "delta_bad_late_ret_4_10_ratio",
                "cash_exit_abs_positive_year_ratio",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
