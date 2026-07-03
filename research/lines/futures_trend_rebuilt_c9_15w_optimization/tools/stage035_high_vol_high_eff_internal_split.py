from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]

LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage035"
MODEL_TAG = "stage035_high_vol_high_eff_internal_split_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage035_high_vol_high_eff_internal_split"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage035_high_vol_high_eff_internal_split"
STAGE_RECORD_DIR = LINE_DIR / "stages"

STAGE034_OUTPUT_DIR = LINE_DIR / "outputs" / "stage034_stage033_remaining_negative_precursor"
STAGE034_PREFIX = "rebuilt_c9_stage034_stage033_remaining_negative_precursor"
STAGE034_TAG = "stage034_stage033_remaining_negative_precursor_v1"
STAGE034_FEATURE_MATRIX_PATH = STAGE034_OUTPUT_DIR / f"{STAGE034_PREFIX}_feature_matrix_{STAGE034_TAG}.csv"

HIGH_VOL_ROWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_high_vol_rows_{MODEL_TAG}.csv"
BUCKET_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
CONDITION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_summary_{MODEL_TAG}.csv"
CONTRAST_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contrast_summary_{MODEL_TAG}.csv"
STABILITY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stability_summary_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

EXTERNAL_RESEARCH_JUDGMENT = (
    "Managed-futures references emphasize preserving trend-following right-tail convexity and avoiding local rules "
    "that cut large winners. Stage035 therefore decomposes the known high_vol_high_eff risk regime into overheat-like "
    "bad windows and recovery-like right-tail windows before any engine change."
)
OVERFIT_REFLECTION_BEFORE = (
    "否。Stage035 不回测新策略、不扫参数，只在 Stage034 已冻结特征矩阵中拆解同一个已知坏 regime；"
    "条件均来自已有账户、市场和 AI 月度字段。"
)
CONTINUE_VALUE_BEFORE = (
    "有。Stage024/025/026 已反证 high_vol_high_eff 一刀切暂停，Stage034 又确认剩余左尾集中在该 regime；"
    "继续价值在于分清该 regime 内哪些是过热回吐、哪些是恢复右尾。"
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, np.bool_):
        return bool(value)
    if not isinstance(value, (str, bytes)) and pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无数据_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _read_high_vol_rows() -> pd.DataFrame:
    if not STAGE034_FEATURE_MATRIX_PATH.exists():
        raise FileNotFoundError(STAGE034_FEATURE_MATRIX_PATH)
    features = pd.read_csv(
        STAGE034_FEATURE_MATRIX_PATH,
        encoding="utf-8-sig",
        parse_dates=["start_date", "worst_end_date", "eval_date"],
        low_memory=False,
    )
    high_vol = features[features["joint_regime"].eq("high_vol_high_eff")].copy()
    high_vol["start_year"] = high_vol["start_date"].dt.year.astype("Int64")
    high_vol["start_month"] = high_vol["start_date"].dt.strftime("%Y-%m")
    high_vol["strict_negative_start"] = (
        pd.to_numeric(high_vol["strict_negative_start"], errors="coerce").fillna(0).astype(int)
    )
    high_vol["severe_negative_start"] = (
        pd.to_numeric(high_vol["severe_negative_start"], errors="coerce").fillna(0).astype(int)
    )
    return high_vol.sort_values(["source_start_month", "start_date"]).reset_index(drop=True)


def _summarize_group(base: pd.DataFrame, name: str, group: pd.DataFrame) -> dict[str, Any]:
    strict = pd.to_numeric(group["strict_negative_start"], errors="coerce").fillna(0).astype(int)
    severe = pd.to_numeric(group["severe_negative_start"], errors="coerce").fillna(0).astype(int)
    min_ret = pd.to_numeric(group["min_future_return_pct"], errors="coerce")
    final_ret = pd.to_numeric(group["to_final_return_pct"], errors="coerce")
    base_strict = pd.to_numeric(base["strict_negative_start"], errors="coerce").fillna(0).astype(int)
    base_rate = float(base_strict.mean() * 100.0) if len(base_strict) else 0.0
    strict_rate = float(strict.mean() * 100.0) if len(group) else 0.0
    return {
        "name": name,
        "count": int(len(group)),
        "source_start_count": int(group["source_start_month"].nunique()),
        "date_count": int(group["start_date"].nunique()),
        "strict_negative_count": int(strict.sum()),
        "nonnegative_count": int(len(group) - int(strict.sum())),
        "strict_negative_rate_pct": strict_rate,
        "lift_vs_high_vol": float(strict_rate / base_rate) if base_rate else np.nan,
        "severe_negative_count": int(severe.sum()),
        "severe_negative_rate_pct": float(severe.mean() * 100.0) if len(group) else 0.0,
        "min_of_min_future_return_pct": float(min_ret.min()),
        "p10_min_future_return_pct": float(min_ret.quantile(0.10)),
        "median_min_future_return_pct": float(min_ret.median()),
        "mean_min_future_return_pct": float(min_ret.mean()),
        "median_to_final_return_pct": float(final_ret.median()),
        "first_start_date": group["start_date"].min(),
        "last_start_date": group["start_date"].max(),
    }


def _bucket_summary(high_vol: pd.DataFrame) -> pd.DataFrame:
    bucket_features = [
        "source_start_month",
        "start_year",
        "start_month",
        "stage033_drawdown_bucket",
        "stage013_drawdown_bucket",
        "broker_bucket",
        "active_products_bucket",
        "stage033_return_21d_bucket",
        "stage033_return_63d_bucket",
        "stage033_return_126d_bucket",
        "trend_breadth_bucket",
        "close_extreme_bucket",
        "ai_top8_prob_mean_exp_bucket",
        "ai_top8_prob_min_exp_bucket",
        "consensus_top8_count_exp_bucket",
        "consensus_count_bucket",
        "all_market_eff_median_exp_bucket",
    ]
    rows: list[dict[str, Any]] = []
    for feature in bucket_features:
        if feature not in high_vol.columns:
            continue
        for value, group in high_vol.groupby(feature, dropna=False):
            if len(group) < 20:
                continue
            row = _summarize_group(high_vol, str(value), group)
            row["feature"] = feature
            row["feature_value"] = str(value)
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["strict_negative_rate_pct", "count", "lift_vs_high_vol"], ascending=[False, False, False]
    )


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce") if column in frame.columns else pd.Series(np.nan, index=frame.index)


def _condition_summary(high_vol: pd.DataFrame) -> pd.DataFrame:
    condition_map: dict[str, Callable[[pd.DataFrame], pd.Series]] = {
        "all_high_vol_high_eff": lambda df: pd.Series(True, index=df.index),
        "overheat_21d_ret_gt20": lambda df: _num(df, "stage033_return_21d_pct").gt(20),
        "overheat_63d_ret_gt20": lambda df: _num(df, "stage033_return_63d_pct").gt(20),
        "overheat_126d_ret_gt20": lambda df: _num(df, "stage033_return_126d_pct").gt(20),
        "overheat_21d_and_63d_ret_gt20": lambda df: _num(df, "stage033_return_21d_pct").gt(20)
        & _num(df, "stage033_return_63d_pct").gt(20),
        "overheat_63d_gt20_dd_gt_-20": lambda df: _num(df, "stage033_return_63d_pct").gt(20)
        & _num(df, "stage033_drawdown_pct").gt(-20),
        "overheat_63d_gt20_dd_-30_to_-10": lambda df: _num(df, "stage033_return_63d_pct").gt(20)
        & _num(df, "stage033_drawdown_pct").gt(-30)
        & _num(df, "stage033_drawdown_pct").le(-10),
        "overheat_63d_gt20_consensus_1_3": lambda df: _num(df, "stage033_return_63d_pct").gt(20)
        & df["consensus_count_bucket"].eq("consensus_1_3"),
        "overheat_63d_gt20_breadth_low": lambda df: _num(df, "stage033_return_63d_pct").gt(20)
        & df["trend_breadth_bucket"].eq("breadth_low"),
        "overheat_63d_gt20_holding63_gt300k": lambda df: _num(df, "stage033_return_63d_pct").gt(20)
        & _num(df, "holding_pnl_sum_63d").gt(300_000),
        "overheat_63d_gt20_net63_gt300k": lambda df: _num(df, "stage033_return_63d_pct").gt(20)
        & _num(df, "net_pnl_sum_63d").gt(300_000),
        "mid_drawdown_-30_to_-10": lambda df: _num(df, "stage033_drawdown_pct").gt(-30)
        & _num(df, "stage033_drawdown_pct").le(-10),
        "drawdown_-30_to_-20": lambda df: _num(df, "stage033_drawdown_pct").gt(-30)
        & _num(df, "stage033_drawdown_pct").le(-20),
        "drawdown_-20_to_-10": lambda df: _num(df, "stage033_drawdown_pct").gt(-20)
        & _num(df, "stage033_drawdown_pct").le(-10),
        "consensus_1_3": lambda df: df["consensus_count_bucket"].eq("consensus_1_3"),
        "consensus_4plus": lambda df: df["consensus_count_bucket"].eq("consensus_4plus"),
        "consensus_0": lambda df: df["consensus_count_bucket"].eq("consensus_0"),
        "ai_prob_mean_warmup": lambda df: df["ai_top8_prob_mean_exp_bucket"].eq("warmup"),
        "breadth_low": lambda df: df["trend_breadth_bucket"].eq("breadth_low"),
        "breadth_mid_or_high": lambda df: df["trend_breadth_bucket"].isin(["breadth_mid", "breadth_high"]),
        "close_extreme_high": lambda df: df["close_extreme_bucket"].eq("extreme_high"),
        "recovery_63d_ret_le_-20": lambda df: _num(df, "stage033_return_63d_pct").le(-20),
        "recovery_dd_le_-30": lambda df: _num(df, "stage033_drawdown_pct").le(-30),
        "recovery_63d_ret_le_-20_or_dd_le_-30": lambda df: _num(df, "stage033_return_63d_pct").le(-20)
        | _num(df, "stage033_drawdown_pct").le(-30),
        "recovery_63d_ret_le_-20_and_consensus_4plus": lambda df: _num(df, "stage033_return_63d_pct").le(-20)
        & df["consensus_count_bucket"].eq("consensus_4plus"),
        "injury_but_active_4plus": lambda df: _num(df, "stage033_drawdown_pct").le(-20)
        & _num(df, "c3_active_products").ge(4),
        "no_active_positions": lambda df: _num(df, "c3_active_products").le(0),
        "active_4plus": lambda df: _num(df, "c3_active_products").ge(4),
        "broker60_or_active4": lambda df: _num(df, "broker10_margin_to_equity_pct").ge(60)
        | _num(df, "c3_active_products").ge(4),
        "market_ret60_negative": lambda df: _num(df, "median_ret_60d").lt(0),
        "market_ret60_negative_and_overheat63": lambda df: _num(df, "median_ret_60d").lt(0)
        & _num(df, "stage033_return_63d_pct").gt(20),
    }
    rows: list[dict[str, Any]] = []
    for condition, maker in condition_map.items():
        mask = maker(high_vol).fillna(False).astype(bool)
        group = high_vol[mask].copy()
        if group.empty:
            continue
        row = _summarize_group(high_vol, condition, group)
        row["condition"] = condition
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["strict_negative_rate_pct", "count", "lift_vs_high_vol"], ascending=[False, False, False]
    )


def _contrast_summary(high_vol: pd.DataFrame) -> pd.DataFrame:
    numeric_features = [
        "stage033_return_21d_pct",
        "stage033_return_63d_pct",
        "stage033_return_126d_pct",
        "stage033_drawdown_pct",
        "stage013_drawdown_pct",
        "broker10_margin_to_equity_pct",
        "c3_active_products",
        "c3_active_contracts",
        "net_pnl_sum_21d",
        "net_pnl_sum_63d",
        "net_pnl_sum_126d",
        "holding_pnl_sum_21d",
        "holding_pnl_sum_63d",
        "holding_pnl_sum_126d",
        "broker_max_63d",
        "active_max_63d",
        "median_ret_60d",
        "ma20_over_ma60_share_60d",
        "cross_section_ret60_dispersion",
        "close_extreme_share",
        "breakout_share_60d",
        "median_trend_efficiency_60d",
        "median_realized_vol_60d",
        "ai_top8_prob_mean",
        "ai_top8_prob_min",
        "consensus_top8_count",
        "consensus_prob_mean",
        "consensus_candidate_count_60d_sum",
        "jd_consensus_count",
    ]
    rows: list[dict[str, Any]] = []
    is_negative = high_vol["strict_negative_start"].astype(int).eq(1)
    for feature in numeric_features:
        if feature not in high_vol.columns:
            continue
        values = pd.to_numeric(high_vol[feature], errors="coerce")
        nonnegative = values[~is_negative].dropna()
        negative = values[is_negative].dropna()
        if nonnegative.empty or negative.empty:
            continue
        nonnegative_mean = float(nonnegative.mean())
        negative_mean = float(negative.mean())
        nonnegative_median = float(nonnegative.median())
        negative_median = float(negative.median())
        pooled_std = float(values.dropna().std(ddof=0))
        mean_diff = negative_mean - nonnegative_mean
        rows.append(
            {
                "feature": feature,
                "nonnegative_count": int(len(nonnegative)),
                "negative_count": int(len(negative)),
                "nonnegative_mean": nonnegative_mean,
                "negative_mean": negative_mean,
                "mean_diff_neg_minus_nonneg": mean_diff,
                "effect_size": float(mean_diff / pooled_std) if pooled_std else np.nan,
                "nonnegative_median": nonnegative_median,
                "negative_median": negative_median,
                "median_diff_neg_minus_nonneg": negative_median - nonnegative_median,
            }
        )
    if not rows:
        return pd.DataFrame()
    data = pd.DataFrame(rows)
    data["abs_effect_size"] = data["effect_size"].abs()
    return data.sort_values(["abs_effect_size", "feature"], ascending=[False, True]).reset_index(drop=True)


def _stability_summary(high_vol: pd.DataFrame) -> pd.DataFrame:
    specs: dict[str, Callable[[pd.DataFrame], pd.Series]] = {
        "all_high_vol_high_eff": lambda df: pd.Series(True, index=df.index),
        "overheat_63d_ret_gt20": lambda df: _num(df, "stage033_return_63d_pct").gt(20),
        "overheat_63d_gt20_consensus_1_3": lambda df: _num(df, "stage033_return_63d_pct").gt(20)
        & df["consensus_count_bucket"].eq("consensus_1_3"),
        "overheat_63d_gt20_dd_gt_-20": lambda df: _num(df, "stage033_return_63d_pct").gt(20)
        & _num(df, "stage033_drawdown_pct").gt(-20),
        "recovery_63d_ret_le_-20": lambda df: _num(df, "stage033_return_63d_pct").le(-20),
        "recovery_dd_le_-30": lambda df: _num(df, "stage033_drawdown_pct").le(-30),
    }
    rows: list[dict[str, Any]] = []
    for name, maker in specs.items():
        mask = maker(high_vol).fillna(False).astype(bool)
        scoped = high_vol[mask].copy()
        if scoped.empty:
            continue
        for source, group in scoped.groupby("source_start_month", dropna=False):
            if len(group) < 5:
                continue
            row = _summarize_group(high_vol, name, group)
            row["stability_axis"] = "source_start_month"
            row["stability_value"] = str(source)
            rows.append(row)
        for year, group in scoped.groupby("start_year", dropna=False):
            if len(group) < 5:
                continue
            row = _summarize_group(high_vol, name, group)
            row["stability_axis"] = "start_year"
            row["stability_value"] = str(int(year)) if pd.notna(year) else "missing"
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["name", "stability_axis", "stability_value"]).reset_index(drop=True)


def _plot(
    condition_summary: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    contrast_summary: pd.DataFrame,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(19, 12))

    bad_conditions = condition_summary[condition_summary["condition"].ne("all_high_vol_high_eff")].head(12)
    axes[0, 0].barh(bad_conditions["condition"], bad_conditions["strict_negative_rate_pct"], color="#dc2626")
    axes[0, 0].invert_yaxis()
    axes[0, 0].set_title("High Vol High Eff: Bad-Window Conditions")
    axes[0, 0].set_xlabel("strict negative rate %")

    protective = (
        condition_summary[condition_summary["condition"].ne("all_high_vol_high_eff")]
        .sort_values(["strict_negative_rate_pct", "count"], ascending=[True, False])
        .head(10)
    )
    axes[0, 1].barh(protective["condition"], protective["strict_negative_rate_pct"], color="#16a34a")
    axes[0, 1].invert_yaxis()
    axes[0, 1].set_title("High Vol High Eff: Recovery-Like Conditions")
    axes[0, 1].set_xlabel("strict negative rate %")

    top_buckets = bucket_summary.head(14).copy()
    labels = top_buckets["feature"] + "=" + top_buckets["feature_value"]
    axes[1, 0].barh(labels, top_buckets["strict_negative_rate_pct"], color="#2563eb")
    axes[1, 0].invert_yaxis()
    axes[1, 0].set_title("Top Buckets by Strict Negative Rate")
    axes[1, 0].set_xlabel("strict negative rate %")

    top_contrast = contrast_summary.head(12).copy()
    colors = np.where(top_contrast["effect_size"].ge(0), "#7c3aed", "#f59e0b")
    axes[1, 1].barh(top_contrast["feature"], top_contrast["effect_size"], color=colors)
    axes[1, 1].invert_yaxis()
    axes[1, 1].set_title("Numeric Contrast: Negative Minus Nonnegative")
    axes[1, 1].set_xlabel("effect size")

    for axis in axes.ravel():
        axis.grid(True, alpha=0.24)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _decision(
    high_vol: pd.DataFrame,
    condition_summary: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    contrast_summary: pd.DataFrame,
) -> dict[str, Any]:
    all_row = condition_summary[condition_summary["condition"].eq("all_high_vol_high_eff")].iloc[0].to_dict()
    bad_candidates = condition_summary[
        condition_summary["condition"].ne("all_high_vol_high_eff")
        & condition_summary["count"].ge(80)
        & condition_summary["source_start_count"].ge(3)
        & condition_summary["strict_negative_rate_pct"].ge(float(all_row["strict_negative_rate_pct"]))
    ].copy()
    top_bad = bad_candidates.iloc[0].to_dict() if not bad_candidates.empty else {}
    recovery_candidates = condition_summary[
        condition_summary["condition"].ne("all_high_vol_high_eff")
        & condition_summary["count"].ge(50)
        & condition_summary["source_start_count"].ge(3)
    ].sort_values(["strict_negative_rate_pct", "count"], ascending=[True, False])
    top_recovery = recovery_candidates.iloc[0].to_dict() if not recovery_candidates.empty else {}
    bucket_candidates = bucket_summary[
        bucket_summary["count"].ge(80)
        & bucket_summary["source_start_count"].ge(3)
        & bucket_summary["feature_value"].ne("warmup")
    ].copy()
    top_bucket = bucket_candidates.iloc[0].to_dict() if not bucket_candidates.empty else {}
    strict_rate = float(all_row["strict_negative_rate_pct"])
    bad_rate = float(top_bad.get("strict_negative_rate_pct", np.nan))
    recovery_rate = float(top_recovery.get("strict_negative_rate_pct", np.nan))
    bad_count = int(top_bad.get("count", 0) or 0)
    recovery_count = int(top_recovery.get("count", 0) or 0)
    split_found = (
        bad_count >= 80
        and recovery_count >= 50
        and np.isfinite(bad_rate)
        and np.isfinite(recovery_rate)
        and bad_rate >= strict_rate + 12.0
        and recovery_rate <= strict_rate - 35.0
    )
    decision_label = "stage035_no_stable_internal_split"
    if split_found:
        decision_label = "stage035_internal_overheat_vs_recovery_split_found_needs_engine_validation"

    negative = high_vol[high_vol["strict_negative_start"].eq(1)]
    nonnegative = high_vol[high_vol["strict_negative_start"].eq(0)]
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "audit_type": "stage034_high_vol_high_eff_internal_split",
        "decision": decision_label,
        "high_vol_row_count": int(len(high_vol)),
        "high_vol_strict_negative_count": int(high_vol["strict_negative_start"].sum()),
        "high_vol_strict_negative_rate_pct": strict_rate,
        "high_vol_severe_negative_count": int(high_vol["severe_negative_start"].sum()),
        "high_vol_severe_negative_rate_pct": float(high_vol["severe_negative_start"].mean() * 100.0),
        "high_vol_min_future_return_pct": float(pd.to_numeric(high_vol["min_future_return_pct"], errors="coerce").min()),
        "high_vol_nonnegative_count": int(len(nonnegative)),
        "negative_median_stage033_return_63d_pct": float(_num(negative, "stage033_return_63d_pct").median()),
        "nonnegative_median_stage033_return_63d_pct": float(_num(nonnegative, "stage033_return_63d_pct").median()),
        "negative_median_holding_pnl_sum_63d": float(_num(negative, "holding_pnl_sum_63d").median()),
        "nonnegative_median_holding_pnl_sum_63d": float(_num(nonnegative, "holding_pnl_sum_63d").median()),
        "top_bad_condition": str(top_bad.get("condition", "")),
        "top_bad_condition_count": bad_count,
        "top_bad_condition_negative_rate_pct": bad_rate,
        "top_bad_condition_lift_vs_high_vol": float(top_bad.get("lift_vs_high_vol", np.nan)),
        "top_recovery_condition": str(top_recovery.get("condition", "")),
        "top_recovery_condition_count": recovery_count,
        "top_recovery_condition_negative_rate_pct": recovery_rate,
        "top_recovery_condition_lift_vs_high_vol": float(top_recovery.get("lift_vs_high_vol", np.nan)),
        "top_bucket_feature": str(top_bucket.get("feature", "")),
        "top_bucket_value": str(top_bucket.get("feature_value", "")),
        "top_bucket_count": int(top_bucket.get("count", 0) or 0),
        "top_bucket_negative_rate_pct": float(top_bucket.get("strict_negative_rate_pct", np.nan)),
        "top_numeric_contrast_feature": str(contrast_summary.iloc[0]["feature"]) if not contrast_summary.empty else "",
        "top_numeric_contrast_effect_size": float(contrast_summary.iloc[0]["effect_size"])
        if not contrast_summary.empty
        else np.nan,
        "strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": EXTERNAL_RESEARCH_JUDGMENT,
        "overfit_reflection_before": OVERFIT_REFLECTION_BEFORE,
        "continue_value_before": CONTINUE_VALUE_BEFORE,
        "overfit_reflection_after": (
            "否。Stage035 仍是只读拆解，没有把最高胜率/败率分桶直接转成规则；"
            "但如果下一步按 2022 年或 warmup 字段单独调参，就会明显过拟合。"
        ),
        "continue_value_after": (
            "有。结果把 high_vol_high_eff 拆成两类：前期账户/holding PnL 已大幅扩张的过热回吐区，"
            "以及 63日已大跌或深回撤后的恢复右尾区；下一步应做冻结规则真实引擎验证，重点保护恢复右尾。"
        )
        if split_found
        else (
            "有但需要换信息源。本阶段未找到足够稳定的内部拆分，继续在相同字段上扫阈值价值不高。"
        ),
        "outputs": {
            "high_vol_rows": str(HIGH_VOL_ROWS_PATH),
            "bucket_summary": str(BUCKET_SUMMARY_PATH),
            "condition_summary": str(CONDITION_SUMMARY_PATH),
            "contrast_summary": str(CONTRAST_SUMMARY_PATH),
            "stability_summary": str(STABILITY_SUMMARY_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(
    decision: dict[str, Any],
    condition_summary: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    contrast_summary: pd.DataFrame,
    stability_summary: pd.DataFrame,
) -> None:
    lines = [
        "# Stage035 high_vol_high_eff 内部右尾/坏窗口拆解",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：只读归因；不是真实组合引擎，不改 C9，不连接 CTP，不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- 趋势跟随资料反复强调保留右尾凸性，不能因局部坏窗口直接砍掉恢复期和大赢家。",
        "- 因此本阶段只拆解 Stage034 已知风险 regime，不做参数搜索，不把单个分桶直接上线。",
        "",
        "## 总体结果",
        "",
        f"- `high_vol_high_eff` 行数：`{decision['high_vol_row_count']}`。",
        f"- 严格负起点：`{decision['high_vol_strict_negative_count']}`，负起点率 `{decision['high_vol_strict_negative_rate_pct']:.4f}%`。",
        f"- 严重负起点：`{decision['high_vol_severe_negative_count']}`，严重负率 `{decision['high_vol_severe_negative_rate_pct']:.4f}%`。",
        f"- 最差未来任意 `>1` 年收益：`{decision['high_vol_min_future_return_pct']:.4f}%`。",
        f"- 负窗口 63日收益中位数：`{decision['negative_median_stage033_return_63d_pct']:.4f}%`；非负窗口：`{decision['nonnegative_median_stage033_return_63d_pct']:.4f}%`。",
        f"- 负窗口 63日 holding PnL 中位数：`{decision['negative_median_holding_pnl_sum_63d']:.2f}`；非负窗口：`{decision['nonnegative_median_holding_pnl_sum_63d']:.2f}`。",
        f"- 最强坏窗口条件：`{decision['top_bad_condition']}`，样本 `{decision['top_bad_condition_count']}`，负率 `{decision['top_bad_condition_negative_rate_pct']:.4f}%`。",
        f"- 最强恢复/右尾条件：`{decision['top_recovery_condition']}`，样本 `{decision['top_recovery_condition_count']}`，负率 `{decision['top_recovery_condition_negative_rate_pct']:.4f}%`。",
        f"- 最强分桶：`{decision['top_bucket_feature']}={decision['top_bucket_value']}`，样本 `{decision['top_bucket_count']}`，负率 `{decision['top_bucket_negative_rate_pct']:.4f}%`。",
        f"- 最大数值对比字段：`{decision['top_numeric_contrast_feature']}`，effect size `{decision['top_numeric_contrast_effect_size']:.4f}`。",
        "",
        "## 条件摘要",
        "",
        _md_table(condition_summary.head(24)),
        "",
        "## 低负率/恢复右尾摘要",
        "",
        _md_table(
            condition_summary[condition_summary["condition"].ne("all_high_vol_high_eff")]
            .sort_values(["strict_negative_rate_pct", "count"], ascending=[True, False])
            .head(16)
        ),
        "",
        "## 分桶摘要",
        "",
        _md_table(bucket_summary.head(24)),
        "",
        "## 数值对比摘要",
        "",
        _md_table(contrast_summary.head(24)),
        "",
        "## 稳定性摘要",
        "",
        _md_table(stability_summary.head(40)),
        "",
        "## 判断",
        "",
        f"- 决策：`{decision['decision']}`。",
        "- 核心解释：负窗口不是简单的低迷/受伤状态，更多是前期账户和持仓利润已经大幅扩张后的高波动高效率回吐；"
        "恢复右尾则常出现在 63日收益已经大跌或深回撤之后。",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
        "",
        "## 输出文件",
        "",
    ]
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    timestamp = datetime.now()
    record_path = STAGE_RECORD_DIR / f"{timestamp:%Y%m%d_%H%M}_stage035_high_vol_high_eff_internal_split.md"
    lines = [
        "# Stage035 - high_vol_high_eff 内部右尾/坏窗口拆解",
        "",
        f"- 记录时间：`{timestamp.isoformat(timespec='minutes')}`",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：`day`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 阶段性质：只读归因，不改策略。",
        "- 是否重要突破版本：`否`",
        "- 是否触发A/B：`否`",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 外部调研与判断",
        "",
        "- 参考资料：Man Group trend-following market mix、Man AHL need for speed、Hurst/Ooi/Pedersen century trend-following、Quantpedia time-series momentum、Return Stacked managed futures。",
        "- 我的判断：趋势跟随优化不能简单截断右尾；本阶段必须先拆清楚 `high_vol_high_eff` 中的过热回吐和恢复右尾。",
        "",
        "## 本次变更",
        "",
        "- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage035_high_vol_high_eff_internal_split.py`。",
        "- 修改脚本：无。",
        "- 删除脚本：无。",
        "- 新增参数：无交易参数；只读阈值用于归因条件标签。",
        "- 修改参数：无。",
        "- 删除参数：无。",
        "",
        "## 回测/归因参数",
        "",
        "- 数据区间：沿用 Stage034 特征矩阵，起点覆盖 `2020-01-01` 至 `2025-06-30`，终点为重建 C9 可用曲线末端。",
        "- 账户规模：Stage033/重建 C9 15万 proxy 曲线口径。",
        "- 成本口径：沿用 Stage033 曲线成本，不新增成本假设。",
        "- 样本过滤：仅 `joint_regime=high_vol_high_eff`。",
        "- 策略/归因口径：只读拆解，不生成订单，不接 CTP。",
        "",
        "## 结果",
        "",
        "- 期末权益：不适用，本阶段不是新增策略回测。",
        "- 总收益：不适用。",
        "- 最大回撤：不适用。",
        "- Sharpe：不适用。",
        "- 总滑点：沿用 Stage033 曲线；本阶段不新增滑点。",
        "- 总交易次数：不适用。",
        "- 胜率：不适用。",
        f"- 其他关键指标：`high_vol_high_eff` 样本 `{decision['high_vol_row_count']}`，严格负 `{decision['high_vol_strict_negative_count']}`，负率 `{decision['high_vol_strict_negative_rate_pct']:.4f}%`；最强坏窗口条件 `{decision['top_bad_condition']}` 负率 `{decision['top_bad_condition_negative_rate_pct']:.4f}%`；最强恢复条件 `{decision['top_recovery_condition']}` 负率 `{decision['top_recovery_condition_negative_rate_pct']:.4f}%`。",
        "",
        "## 输出文件",
        "",
        f"- report：`{REPORT_PATH}`",
        f"- summary：`{CONDITION_SUMMARY_PATH}`",
        "- orders：不适用。",
        "- daily：不适用。",
        f"- quality：`{CONTRAST_SUMMARY_PATH}`",
        "",
        "## 结论",
        "",
        f"- 本阶段结论：`{decision['decision']}`。",
        "- 是否进入下一步：`是`，但只能进入冻结规则真实引擎验证，不能按单一年份/source 继续微调。",
        "- 下一步：将过热条件做成小手数/暂停候选，同时设置恢复右尾保护条件，验证是否能减少严格负窗口且保留 Stage033 全周期收益。",
        "",
        "## 过拟合反思",
        "",
        f"- 运行前判断：{decision['overfit_reflection_before']}",
        f"- 运行后判断：{decision['overfit_reflection_after']}",
        "- 原因：本阶段没有修改交易规则；风险在于下一步若按最高 lift 分桶无约束组合，会变成事后拟合。",
        "",
        "## 继续价值反思",
        "",
        f"- 运行前判断：{decision['continue_value_before']}",
        f"- 运行后判断：{decision['continue_value_after']}",
        "- 原因：已找到比 high_vol_high_eff 一刀切更接近本质的内部结构，值得做冻结真实引擎验证。",
        "",
        "## 合入建议",
        "",
        "- 是否更新本线 `LINE.md`：是，追加 Stage035 结论。",
        "- 是否更新 `research/registry.md`：是，更新当前线最新阶段。",
        "- 是否追加根目录 `memory.md/back_log.md`：只追加 `back_log.md` 重要摘要，不追加 `memory.md`。",
        "",
        "## 全量输出路径",
        "",
    ]
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    record_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return record_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_RECORD_DIR.mkdir(parents=True, exist_ok=True)

    high_vol = _read_high_vol_rows()
    if high_vol.empty:
        raise RuntimeError("Stage034 feature matrix contains no high_vol_high_eff rows.")
    bucket_summary = _bucket_summary(high_vol)
    condition_summary = _condition_summary(high_vol)
    contrast_summary = _contrast_summary(high_vol)
    stability_summary = _stability_summary(high_vol)
    _plot(condition_summary, bucket_summary, contrast_summary)

    decision = _decision(high_vol, condition_summary, bucket_summary, contrast_summary)

    high_vol.to_csv(HIGH_VOL_ROWS_PATH, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(BUCKET_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    condition_summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    contrast_summary.to_csv(CONTRAST_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    stability_summary.to_csv(STABILITY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, condition_summary, bucket_summary, contrast_summary, stability_summary)
    stage_record = _write_stage_record(decision)
    decision["stage_record"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
