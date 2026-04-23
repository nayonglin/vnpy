from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

CANDIDATE_SAMPLES_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_training_samples.csv"
PAIR_SAMPLES_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_pairwise_horizon_strong_refined_samples.csv"

MODEL_TAG: str = "refined_environment_v1"
DAILY_ENV_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_refined_environment_daily_{MODEL_TAG}.csv"
FEATURE_SHIFT_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_refined_environment_feature_shift_{MODEL_TAG}.csv"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_refined_environment_summary_{MODEL_TAG}.json"

EFFECTIVE_START_DATE: str = "2025-01-01"

CANDIDATE_AGG_SPEC: dict[str, tuple[str, str]] = {
    "candidate_count_1d": ("sample_id", "count"),
    "selected_rate_1d": ("label_is_selected", "mean"),
    "avg_atr14_pct_zscore_120_1d": ("feature_atr14_pct_zscore_120", "mean"),
    "avg_range_pct_zscore_120_1d": ("feature_range_pct_zscore_120", "mean"),
    "avg_volume_ratio_1d_20d_zscore_120_1d": ("feature_volume_ratio_1d_20d_zscore_120", "mean"),
    "avg_oi_delta_1d_pct_zscore_120_1d": ("feature_oi_delta_1d_pct_zscore_120", "mean"),
    "avg_close_position_60d_1d": ("feature_close_position_60d", "mean"),
    "avg_signal_strength_signed_1d": ("feature_signal_strength_signed", "mean"),
    "avg_mid_term_momentum_signed_1d": ("feature_mid_term_momentum_signed", "mean"),
    "avg_reversal_pressure_signed_1d": ("feature_reversal_pressure_signed", "mean"),
}

PAIR_AGG_SPEC: dict[str, tuple[str, str]] = {
    "pair_count_1d": ("pair_id", "count"),
    "avg_primary_gap_abs_1d": ("label_horizon_primary_gap_abs", "mean"),
    "avg_primary_weight_1d": ("label_horizon_primary_weight", "mean"),
    "same_signal_share_1d": ("feature_pair_same_signal", "mean"),
    "same_direction_share_1d": ("feature_pair_same_direction", "mean"),
    "support_5d_share_1d": ("label_horizon_5d_support_primary", "mean"),
    "winner_selected_rate_1d": ("label_winner_selected", "mean"),
    "avg_abs_delta_trend_ma20_gap_pct_1d": ("abs_delta_feature_trend_ma20_gap_pct", "mean"),
    "avg_abs_delta_ret_20d_zscore_120_1d": ("abs_delta_feature_ret_20d_zscore_120", "mean"),
    "avg_abs_delta_oi_delta_1d_pct_zscore_120_1d": ("abs_delta_feature_oi_delta_1d_pct_zscore_120", "mean"),
    "avg_abs_delta_range_pct_zscore_120_1d": ("abs_delta_feature_range_pct_zscore_120", "mean"),
    "avg_abs_delta_volume_ratio_2v2_1d": ("abs_delta_feature_volume_ratio_2v2", "mean"),
}


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or np.isinf(result):
        return default
    return result


def load_candidate_samples() -> pd.DataFrame:
    df = pd.read_csv(CANDIDATE_SAMPLES_PATH)
    df["candidate_date"] = pd.to_datetime(df["candidate_date"])
    return df


def load_pair_samples() -> pd.DataFrame:
    df = pd.read_csv(PAIR_SAMPLES_PATH)
    df["candidate_date"] = pd.to_datetime(df["candidate_date"])
    return df


def build_candidate_daily_environment(candidate_df: pd.DataFrame) -> pd.DataFrame:
    daily_df = (
        candidate_df.groupby("candidate_date")
        .agg(**{output: pd.NamedAgg(column=column, aggfunc=agg) for output, (column, agg) in CANDIDATE_AGG_SPEC.items()})
        .reset_index()
    )
    return daily_df


def build_pair_daily_environment(pair_df: pd.DataFrame) -> pd.DataFrame:
    pair_daily_df = (
        pair_df.groupby("candidate_date")
        .agg(**{output: pd.NamedAgg(column=column, aggfunc=agg) for output, (column, agg) in PAIR_AGG_SPEC.items()})
        .reset_index()
    )

    strength_share_df = (
        pair_df.pivot_table(
            index="candidate_date",
            columns="label_horizon_primary_strength_bucket",
            values="pair_id",
            aggfunc="count",
            fill_value=0,
        )
        .rename(columns=lambda value: f"strength_{value}_count_1d")
        .reset_index()
    )
    subtype_share_df = (
        pair_df.pivot_table(
            index="candidate_date",
            columns="label_strong_pair_subtype",
            values="pair_id",
            aggfunc="count",
            fill_value=0,
        )
        .rename(columns=lambda value: f"subtype_{value}_count_1d")
        .reset_index()
    )

    merged_df = pair_daily_df.merge(strength_share_df, on="candidate_date", how="left")
    merged_df = merged_df.merge(subtype_share_df, on="candidate_date", how="left")

    for column in merged_df.columns:
        if column.startswith("strength_") and column.endswith("_count_1d"):
            merged_df[column] = merged_df[column].fillna(0.0)
            merged_df[column.replace("_count_1d", "_share_1d")] = merged_df[column] / merged_df["pair_count_1d"].clip(lower=1.0)
        if column.startswith("subtype_") and column.endswith("_count_1d"):
            merged_df[column] = merged_df[column].fillna(0.0)
            merged_df[column.replace("_count_1d", "_share_1d")] = merged_df[column] / merged_df["pair_count_1d"].clip(lower=1.0)

    return merged_df


def build_daily_environment() -> pd.DataFrame:
    candidate_daily_df = build_candidate_daily_environment(load_candidate_samples())
    pair_daily_df = build_pair_daily_environment(load_pair_samples())
    daily_df = candidate_daily_df.merge(pair_daily_df, on="candidate_date", how="inner")
    daily_df.sort_values("candidate_date", inplace=True)
    daily_df.reset_index(drop=True, inplace=True)

    effective_start = pd.Timestamp(EFFECTIVE_START_DATE)
    daily_df["environment_segment"] = np.where(
        daily_df["candidate_date"] >= effective_start,
        "effective_2025_plus",
        "ineffective_2023_2024",
    )
    daily_df["label_environment_effective"] = (daily_df["candidate_date"] >= effective_start).astype("int64")
    return daily_df


def cohen_d(effective_values: pd.Series, ineffective_values: pd.Series) -> float:
    effective_std = effective_values.std(ddof=1)
    ineffective_std = ineffective_values.std(ddof=1)
    pooled_variance = (((len(effective_values) - 1) * effective_std**2) + ((len(ineffective_values) - 1) * ineffective_std**2))
    denominator = len(effective_values) + len(ineffective_values) - 2
    if denominator <= 0:
        return 0.0
    pooled_std = np.sqrt(pooled_variance / denominator) if pooled_variance > 0 else 0.0
    if pooled_std <= 0.0 or np.isnan(pooled_std):
        return 0.0
    return float((effective_values.mean() - ineffective_values.mean()) / pooled_std)


def build_feature_shift_table(daily_df: pd.DataFrame) -> pd.DataFrame:
    ineffective_df = daily_df[daily_df["label_environment_effective"] == 0].copy()
    effective_df = daily_df[daily_df["label_environment_effective"] == 1].copy()

    excluded_columns = {
        "candidate_date",
        "environment_segment",
        "label_environment_effective",
    }
    numeric_columns = [
        column
        for column in daily_df.columns
        if column not in excluded_columns and pd.api.types.is_numeric_dtype(daily_df[column])
    ]

    rows: list[dict[str, Any]] = []
    for column in numeric_columns:
        ineffective_values = ineffective_df[column].astype("float64")
        effective_values = effective_df[column].astype("float64")
        ineffective_mean = _safe_float(ineffective_values.mean())
        effective_mean = _safe_float(effective_values.mean())
        delta = effective_mean - ineffective_mean
        ratio = effective_mean / ineffective_mean if abs(ineffective_mean) > 1e-9 else float("nan")
        rows.append(
            {
                "feature": column,
                "ineffective_mean": ineffective_mean,
                "effective_mean": effective_mean,
                "delta_effective_minus_ineffective": delta,
                "ratio_effective_div_ineffective": _safe_float(ratio, default=float("nan")),
                "cohen_d": cohen_d(effective_values, ineffective_values),
                "abs_cohen_d": abs(cohen_d(effective_values, ineffective_values)),
            }
        )

    shift_df = pd.DataFrame(rows)
    shift_df.sort_values(["abs_cohen_d", "feature"], ascending=[False, True], inplace=True)
    shift_df.reset_index(drop=True, inplace=True)
    return shift_df


def build_summary(daily_df: pd.DataFrame, shift_df: pd.DataFrame) -> dict[str, Any]:
    ineffective_df = daily_df[daily_df["label_environment_effective"] == 0].copy()
    effective_df = daily_df[daily_df["label_environment_effective"] == 1].copy()

    key_features = [
        "candidate_count_1d",
        "pair_count_1d",
        "avg_primary_gap_abs_1d",
        "avg_abs_delta_trend_ma20_gap_pct_1d",
        "avg_abs_delta_ret_20d_zscore_120_1d",
        "avg_abs_delta_oi_delta_1d_pct_zscore_120_1d",
        "strength_strong_share_1d",
        "subtype_trend_continuation_or_structural_share_1d",
        "same_signal_share_1d",
        "support_5d_share_1d",
    ]
    key_feature_stats = []
    for feature in key_features:
        if feature not in daily_df.columns:
            continue
        key_feature_stats.append(
            {
                "feature": feature,
                "ineffective_mean": _safe_float(ineffective_df[feature].mean()),
                "effective_mean": _safe_float(effective_df[feature].mean()),
            }
        )

    return {
        "model_tag": MODEL_TAG,
        "effective_start_date": EFFECTIVE_START_DATE,
        "effective_days": int(effective_df["candidate_date"].nunique()),
        "ineffective_days": int(ineffective_df["candidate_date"].nunique()),
        "effective_date_range": {
            "start": effective_df["candidate_date"].min().date().isoformat() if not effective_df.empty else "",
            "end": effective_df["candidate_date"].max().date().isoformat() if not effective_df.empty else "",
        },
        "ineffective_date_range": {
            "start": ineffective_df["candidate_date"].min().date().isoformat() if not ineffective_df.empty else "",
            "end": ineffective_df["candidate_date"].max().date().isoformat() if not ineffective_df.empty else "",
        },
        "top_shift_features": shift_df.head(15).to_dict(orient="records"),
        "key_feature_stats": key_feature_stats,
        "judgement": {
            "effective_label_definition": "将 2025-01-01 及以后定义为 refined 标签相对有效环境，2023-2024 定义为相对失效环境。",
            "analysis_goal": "识别 refined 标签更可能生效时，对应的候选横截面与 pair 结构画像。",
            "caution": "这一步是环境画像研究，不是可交易的实时环境分类器。后续若要上线，仍需做前视约束和独立验证。",
        },
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    daily_df = build_daily_environment()
    shift_df = build_feature_shift_table(daily_df)
    summary = build_summary(daily_df, shift_df)

    daily_df.to_csv(DAILY_ENV_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    shift_df.to_csv(FEATURE_SHIFT_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[refined-environment] daily env: {DAILY_ENV_OUTPUT_PATH}")
    print(f"[refined-environment] feature shift: {FEATURE_SHIFT_OUTPUT_PATH}")
    print(f"[refined-environment] summary: {SUMMARY_OUTPUT_PATH}")
    display_columns = [
        "feature",
        "ineffective_mean",
        "effective_mean",
        "delta_effective_minus_ineffective",
        "cohen_d",
    ]
    print(shift_df[display_columns].head(20).to_string(index=False))


if __name__ == "__main__":
    main()
