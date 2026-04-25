from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, f1_score, log_loss, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
SOURCE_SAMPLES_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_training_samples.csv"

MODEL_TAG: str = "microstructure20d_shadow_v1"
SAMPLES_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_microstructure_shadow_samples_{MODEL_TAG}.csv"
SCHEMA_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_microstructure_shadow_schema_{MODEL_TAG}.json"
MODEL_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_microstructure_shadow_classifier_{MODEL_TAG}.joblib"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_microstructure_shadow_classifier_summary_{MODEL_TAG}.json"
COEFFICIENT_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_microstructure_shadow_classifier_coefficients_{MODEL_TAG}.csv"
PREDICTIONS_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_microstructure_shadow_classifier_predictions_{MODEL_TAG}.csv"
BUCKET_ANALYSIS_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_microstructure_shadow_classifier_bucket_analysis_{MODEL_TAG}.csv"
GROUP_ANALYSIS_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_microstructure_shadow_classifier_group_analysis_{MODEL_TAG}.csv"

DATE_COLUMN: str = "candidate_date"
TARGET_R_MULTIPLE_COLUMN: str = "label_candidate_forward_20d_r_multiple"
TARGET_COLUMN: str = "target_candidate_forward_20d_positive"
WEIGHT_COLUMN: str = "sample_weight_forward20_abs_r"
PROBABILITY_COLUMN: str = "predicted_forward20_positive_probability"
VALID_START_DATE: str = "2023-01-01"
TEST_START_DATE: str = "2024-01-01"
LOGISTIC_C: float = 0.25
RANDOM_STATE: int = 42

GENERATED_FEATURE_COLUMNS: list[str] = [
    "feature_direction_sign",
    "feature_open_interest_decline_mode",
    "feature_ma_alignment_with_direction",
    "feature_directional_trend_ma20_gap_pct",
    "feature_directional_ma20_ma40_gap_pct",
    "feature_favorable_wick_pct",
    "feature_adverse_wick_pct",
]

FEATURE_GROUPS: dict[str, list[str]] = {
    "kline_size_volatility": [
        "feature_atr14_pct",
        "feature_range_pct",
        "feature_atr14_pct_zscore_120",
        "feature_range_pct_zscore_120",
        "feature_atr14_pct_cs_zscore_1d",
        "feature_range_pct_cs_zscore_1d",
        "feature_range_pct_zscore_120_cs_zscore_1d",
    ],
    "kline_shape_position": [
        "feature_close_vs_prev20_high_pct",
        "feature_close_vs_prev20_low_pct",
        "feature_upper_wick_pct",
        "feature_lower_wick_pct",
        "feature_favorable_wick_pct",
        "feature_adverse_wick_pct",
        "feature_close_position_20d",
        "feature_close_position_60d",
        "feature_close_position_20d_cs_zscore_1d",
        "feature_close_position_60d_cs_zscore_1d",
    ],
    "volume": [
        "feature_vol20",
        "feature_vol60",
        "feature_volume_zscore_20",
        "feature_volume_ratio_1d_20d",
        "feature_volume_ratio_1d_20d_zscore_120",
        "feature_volume_ratio_2v2",
        "feature_volume_oi_surge_flag",
        "feature_volume_zscore_20_cs_zscore_1d",
        "feature_volume_ratio_1d_20d_cs_zscore_1d",
        "feature_volume_ratio_2v2_cs_zscore_1d",
    ],
    "open_interest": [
        "feature_open_oi",
        "feature_close_oi",
        "feature_oi_delta_1d",
        "feature_oi_delta_5d",
        "feature_oi_delta_1d_pct",
        "feature_oi_delta_5d_pct",
        "feature_oi_delta_1d_pct_zscore_120",
        "feature_oi_ratio_2v2",
        "feature_open_interest_decline_mode",
        "feature_oi_delta_1d_pct_cs_zscore_1d",
        "feature_oi_delta_5d_pct_cs_zscore_1d",
        "feature_oi_ratio_2v2_cs_zscore_1d",
    ],
    "moving_average_trend": [
        "feature_ret_5d",
        "feature_ret_10d",
        "feature_ret_20d",
        "feature_ret_signed_5d",
        "feature_trend_ma5_gap_pct",
        "feature_trend_ma10_gap_pct",
        "feature_trend_ma20_gap_pct",
        "feature_ma5_ma10_gap_pct",
        "feature_ma10_ma20_gap_pct",
        "feature_ma20_ma40_gap_pct",
        "feature_ma_alignment_long",
        "feature_ma_alignment_short",
        "feature_ma_alignment_with_direction",
        "feature_directional_trend_ma20_gap_pct",
        "feature_directional_ma20_ma40_gap_pct",
        "feature_signal_strength_signed",
        "feature_reversal_pressure_signed",
        "feature_mid_term_momentum_signed",
        "feature_trend_ma20_gap_pct_cs_zscore_1d",
        "feature_ma20_ma40_gap_pct_cs_zscore_1d",
        "feature_ret_20d_zscore_120",
        "feature_ret_20d_zscore_120_cs_zscore_1d",
    ],
    "portfolio_context": [
        "feature_direction_sign",
        "feature_stop_distance_pct",
        "feature_target_risk_to_equity",
        "feature_margin_per_contract_to_equity",
        "feature_candidate_cross_section_count_1d",
        "loss_streak",
        "active_positions_before",
        "remaining_position_slots",
        "max_concurrent_positions",
    ],
}

IDENTITY_COLUMNS: list[str] = [
    "sample_id",
    "candidate_index",
    "candidate_datetime",
    DATE_COLUMN,
    "product_vt_symbol",
    "contract_vt_symbol",
    "entry_context",
    "direction",
    "signal",
    "risk_mode",
    "candidate_status",
    "selection_stage",
    "label_is_selected",
]


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or np.isinf(result):
        return default
    return result


def _numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(0.0, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0).astype("float64")


def available_feature_columns(df: pd.DataFrame) -> list[str]:
    columns: list[str] = []
    for group_columns in FEATURE_GROUPS.values():
        for column in group_columns:
            if column in df.columns and column not in columns:
                columns.append(column)
    return columns


def feature_group_lookup(feature_columns: list[str]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for group_name, group_columns in FEATURE_GROUPS.items():
        for column in group_columns:
            lookup.setdefault(column, group_name)
    return {column: lookup.get(column, "other") for column in feature_columns}


def load_source_samples() -> pd.DataFrame:
    df = pd.read_csv(SOURCE_SAMPLES_PATH)
    df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN])
    df.sort_values([DATE_COLUMN, "sample_id"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def add_generated_features(df: pd.DataFrame) -> pd.DataFrame:
    enriched_df = df.copy()
    direction = enriched_df["direction"].astype(str).str.lower()
    direction_sign = np.where(direction == "long", 1.0, -1.0)

    enriched_df["feature_direction_sign"] = direction_sign
    enriched_df["feature_open_interest_decline_mode"] = (
        enriched_df.get("risk_mode", pd.Series("", index=enriched_df.index)).astype(str) == "open_interest_decline"
    ).astype("float64")
    enriched_df["feature_ma_alignment_with_direction"] = np.where(
        direction == "long",
        _numeric_series(enriched_df, "feature_ma_alignment_long"),
        _numeric_series(enriched_df, "feature_ma_alignment_short"),
    )
    enriched_df["feature_directional_trend_ma20_gap_pct"] = (
        _numeric_series(enriched_df, "feature_trend_ma20_gap_pct") * direction_sign
    )
    enriched_df["feature_directional_ma20_ma40_gap_pct"] = (
        _numeric_series(enriched_df, "feature_ma20_ma40_gap_pct") * direction_sign
    )
    enriched_df["feature_favorable_wick_pct"] = np.where(
        direction == "long",
        _numeric_series(enriched_df, "feature_lower_wick_pct"),
        _numeric_series(enriched_df, "feature_upper_wick_pct"),
    )
    enriched_df["feature_adverse_wick_pct"] = np.where(
        direction == "long",
        _numeric_series(enriched_df, "feature_upper_wick_pct"),
        _numeric_series(enriched_df, "feature_lower_wick_pct"),
    )
    return enriched_df


def add_targets(df: pd.DataFrame) -> pd.DataFrame:
    enriched_df = df.copy()
    forward_r = _numeric_series(enriched_df, TARGET_R_MULTIPLE_COLUMN)
    enriched_df[TARGET_COLUMN] = (forward_r > 0.0).astype("int64")
    enriched_df[WEIGHT_COLUMN] = forward_r.abs().clip(lower=0.25, upper=3.0).astype("float64")
    enriched_df["target_candidate_forward_20d_r_multiple"] = forward_r
    enriched_df["target_candidate_quality_score_v2"] = _numeric_series(enriched_df, "label_candidate_quality_score_v2")
    return enriched_df


def build_split(df: pd.DataFrame) -> pd.DataFrame:
    valid_start = pd.Timestamp(VALID_START_DATE)
    test_start = pd.Timestamp(TEST_START_DATE)
    split_series = pd.Series("train", index=df.index, dtype="object")
    split_series.loc[df[DATE_COLUMN] >= valid_start] = "valid"
    split_series.loc[df[DATE_COLUMN] >= test_start] = "test"
    result = df.copy()
    result["dataset_split"] = split_series
    return result


def build_shadow_samples() -> tuple[pd.DataFrame, list[str], dict[str, Any]]:
    source_df = load_source_samples()
    enriched_df = add_targets(add_generated_features(source_df))
    feature_columns = available_feature_columns(enriched_df)
    selected_columns = [
        column
        for column in IDENTITY_COLUMNS
        + feature_columns
        + [
            TARGET_R_MULTIPLE_COLUMN,
            "label_candidate_quality_score_v2",
            "label_candidate_quality_bucket_v2",
            TARGET_COLUMN,
            WEIGHT_COLUMN,
            "target_candidate_forward_20d_r_multiple",
            "target_candidate_quality_score_v2",
        ]
        if column in enriched_df.columns
    ]
    samples_df = enriched_df[selected_columns].copy()
    samples_df = build_split(samples_df)
    samples_df.reset_index(drop=True, inplace=True)

    group_lookup = feature_group_lookup(feature_columns)
    schema = {
        "dataset_name": f"qmt_roll_ai_microstructure_shadow_samples_{MODEL_TAG}",
        "source_dataset": str(SOURCE_SAMPLES_PATH.name),
        "model_usage": "shadow_diagnostic_only_not_trade_switch",
        "target_definition": {
            "target_column": TARGET_COLUMN,
            "target_rule": f"{TARGET_R_MULTIPLE_COLUMN} > 0",
            "weight_column": WEIGHT_COLUMN,
            "weight_rule": "clip(abs(label_candidate_forward_20d_r_multiple), 0.25, 3.0)",
        },
        "split_dates": {
            "valid_start_date": VALID_START_DATE,
            "test_start_date": TEST_START_DATE,
        },
        "feature_groups": FEATURE_GROUPS,
        "feature_group_lookup": group_lookup,
        "feature_columns": feature_columns,
        "generated_feature_columns": [column for column in GENERATED_FEATURE_COLUMNS if column in feature_columns],
        "coverage_summary": {
            "rows": int(len(samples_df)),
            "days": int(samples_df[DATE_COLUMN].nunique()),
            "products": int(samples_df["product_vt_symbol"].nunique()) if "product_vt_symbol" in samples_df.columns else 0,
            "positive_rate": _safe_float(samples_df[TARGET_COLUMN].mean()),
        },
        "design_judgement": "先把K线大小/形态、成交量、持仓量、均线做成影子诊断模型，只评估排序能力，不直接改仓位。这样能验证信息含量，避免把小样本噪声写成交易规则。",
    }
    return samples_df, feature_columns, schema


def prepare_x(df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    x = pd.DataFrame(index=df.index)
    for column in feature_columns:
        x[column] = pd.to_numeric(df[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return x


def train_model(train_df: pd.DataFrame, feature_columns: list[str]) -> tuple[Pipeline, dict[str, Any]]:
    if train_df[TARGET_COLUMN].nunique() < 2:
        raise ValueError("training split has fewer than two target classes")

    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    C=LOGISTIC_C,
                    solver="lbfgs",
                    max_iter=3000,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )
    model.fit(
        prepare_x(train_df, feature_columns),
        train_df[TARGET_COLUMN].astype("int64"),
        classifier__sample_weight=train_df[WEIGHT_COLUMN].astype("float64"),
    )
    metadata = {
        "model_type": "logistic_regression",
        "model_tag": MODEL_TAG,
        "regularization_c": LOGISTIC_C,
        "random_state": RANDOM_STATE,
        "feature_columns": feature_columns,
        "target_column": TARGET_COLUMN,
        "weight_column": WEIGHT_COLUMN,
        "train_rows": int(len(train_df)),
        "train_days": int(train_df[DATE_COLUMN].nunique()),
    }
    return model, metadata


def score_dataframe(model: Pipeline, df: pd.DataFrame, feature_columns: list[str]) -> np.ndarray:
    return np.asarray(model.predict_proba(prepare_x(df, feature_columns))[:, 1], dtype="float64")


def compute_metrics(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {
            "rows": 0,
            "days": 0,
            "positive_rate": 0.0,
            "predicted_positive_rate": 0.0,
            "accuracy": 0.0,
            "weighted_accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "roc_auc": 0.0,
            "log_loss": 0.0,
            "brier_score": 0.0,
            "avg_forward20_r": 0.0,
        }

    actual = df[TARGET_COLUMN].astype("int64")
    probability = df[PROBABILITY_COLUMN].astype("float64").clip(1e-6, 1 - 1e-6)
    predicted = (probability >= 0.5).astype("int64")
    sample_weight = df[WEIGHT_COLUMN].astype("float64")

    try:
        auc = roc_auc_score(actual, probability) if actual.nunique() >= 2 else float("nan")
    except ValueError:
        auc = float("nan")

    return {
        "rows": int(len(df)),
        "days": int(df[DATE_COLUMN].nunique()),
        "positive_rate": _safe_float(actual.mean()),
        "predicted_positive_rate": _safe_float(predicted.mean()),
        "accuracy": _safe_float(accuracy_score(actual, predicted)),
        "weighted_accuracy": _safe_float(accuracy_score(actual, predicted, sample_weight=sample_weight)),
        "precision": _safe_float(precision_score(actual, predicted, zero_division=0)),
        "recall": _safe_float(recall_score(actual, predicted, zero_division=0)),
        "f1": _safe_float(f1_score(actual, predicted, zero_division=0)),
        "roc_auc": _safe_float(auc),
        "log_loss": _safe_float(log_loss(actual, probability, sample_weight=sample_weight, labels=[0, 1])),
        "brier_score": _safe_float(brier_score_loss(actual, probability, sample_weight=sample_weight)),
        "avg_forward20_r": _safe_float(df["target_candidate_forward_20d_r_multiple"].mean()),
    }


def build_coefficients(model: Pipeline, feature_columns: list[str]) -> pd.DataFrame:
    classifier: LogisticRegression = model.named_steps["classifier"]
    scaler: StandardScaler = model.named_steps["scaler"]
    group_lookup = feature_group_lookup(feature_columns)
    coefficient_df = pd.DataFrame(
        {
            "feature": feature_columns,
            "feature_group": [group_lookup[column] for column in feature_columns],
            "scaled_coefficient": classifier.coef_[0],
            "abs_scaled_coefficient": np.abs(classifier.coef_[0]),
            "feature_mean": scaler.mean_,
            "feature_scale": scaler.scale_,
        }
    )
    coefficient_df.sort_values("abs_scaled_coefficient", ascending=False, inplace=True)
    coefficient_df.reset_index(drop=True, inplace=True)
    return coefficient_df


def build_bucket_analysis(scored_df: pd.DataFrame) -> pd.DataFrame:
    bucket_rows: list[dict[str, Any]] = []
    for split_name, split_df in scored_df.groupby("dataset_split", sort=False):
        if split_df.empty:
            continue
        bucket_count = min(5, len(split_df))
        bucket_series = pd.qcut(
            split_df[PROBABILITY_COLUMN].rank(method="first"),
            q=bucket_count,
            labels=[f"q{i + 1}" for i in range(bucket_count)],
        )
        bucket_df = split_df.copy()
        bucket_df["predicted_probability_bucket"] = bucket_series.astype(str)
        for bucket_name, group_df in bucket_df.groupby("predicted_probability_bucket", observed=False):
            bucket_rows.append(
                {
                    "dataset_split": split_name,
                    "predicted_probability_bucket": bucket_name,
                    "sample_count": int(len(group_df)),
                    "avg_probability": _safe_float(group_df[PROBABILITY_COLUMN].mean()),
                    "actual_positive_rate": _safe_float(group_df[TARGET_COLUMN].mean()),
                    "avg_forward20_r": _safe_float(group_df["target_candidate_forward_20d_r_multiple"].mean()),
                    "median_forward20_r": _safe_float(group_df["target_candidate_forward_20d_r_multiple"].median()),
                    "avg_quality_score_v2": _safe_float(group_df["target_candidate_quality_score_v2"].mean()),
                    "selected_rate": _safe_float(group_df["label_is_selected"].mean()) if "label_is_selected" in group_df.columns else 0.0,
                }
            )
    return pd.DataFrame(bucket_rows)


def build_group_analysis(coefficient_df: pd.DataFrame) -> pd.DataFrame:
    if coefficient_df.empty:
        return pd.DataFrame()
    return (
        coefficient_df.groupby("feature_group", observed=False)
        .agg(
            feature_count=("feature", "count"),
            mean_abs_scaled_coefficient=("abs_scaled_coefficient", "mean"),
            max_abs_scaled_coefficient=("abs_scaled_coefficient", "max"),
            net_scaled_coefficient=("scaled_coefficient", "sum"),
        )
        .reset_index()
        .sort_values("mean_abs_scaled_coefficient", ascending=False)
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    samples_df, feature_columns, schema = build_shadow_samples()
    train_df = samples_df[samples_df["dataset_split"] == "train"].copy()

    model, metadata = train_model(train_df, feature_columns)
    scored_df = samples_df.copy()
    scored_df[PROBABILITY_COLUMN] = score_dataframe(model, scored_df, feature_columns)

    split_metrics = {
        split_name: compute_metrics(scored_df[scored_df["dataset_split"] == split_name])
        for split_name in ["train", "valid", "test"]
    }
    coefficient_df = build_coefficients(model, feature_columns)
    bucket_analysis_df = build_bucket_analysis(scored_df)
    group_analysis_df = build_group_analysis(coefficient_df)

    summary = {
        "model_metadata": metadata,
        "model_usage": "shadow_diagnostic_only_not_trade_switch",
        "source_dataset": str(SOURCE_SAMPLES_PATH),
        "output_files": {
            "samples": str(SAMPLES_OUTPUT_PATH),
            "schema": str(SCHEMA_OUTPUT_PATH),
            "model": str(MODEL_OUTPUT_PATH),
            "summary": str(SUMMARY_OUTPUT_PATH),
            "coefficients": str(COEFFICIENT_OUTPUT_PATH),
            "predictions": str(PREDICTIONS_OUTPUT_PATH),
            "bucket_analysis": str(BUCKET_ANALYSIS_OUTPUT_PATH),
            "group_analysis": str(GROUP_ANALYSIS_OUTPUT_PATH),
        },
        "split_dates": {
            "valid_start_date": VALID_START_DATE,
            "test_start_date": TEST_START_DATE,
        },
        "dataset_rows": int(len(scored_df)),
        "dataset_days": int(scored_df[DATE_COLUMN].nunique()),
        "split_metrics": split_metrics,
        "top_coefficients": coefficient_df.head(25).to_dict(orient="records"),
        "feature_group_analysis": group_analysis_df.to_dict(orient="records"),
        "bucket_analysis": bucket_analysis_df.to_dict(orient="records"),
        "model_judgement": {
            "first_principle": "AI只负责判断这些市场微观结构变量是否有可迁移的信息含量；没有经过回测和纸面跟踪前，不应该变成仓位开关。",
            "feature_mapping": "K线大小=ATR/Range及其zscore；形态=上下影线和收盘位置；成交量=volume ratio/zscore；持仓量=OI delta/ratio；均线=MA gap/alignment。",
            "next_decision_rule": "只有当测试集分桶呈单调性，且后续走前/纸面交易仍保持排序能力，才考虑把分数作为降权或候选排序特征。",
        },
    }

    samples_df.to_csv(SAMPLES_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    SCHEMA_OUTPUT_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    joblib.dump(model, MODEL_OUTPUT_PATH)
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    coefficient_df.to_csv(COEFFICIENT_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    scored_df.to_csv(PREDICTIONS_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    bucket_analysis_df.to_csv(BUCKET_ANALYSIS_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    group_analysis_df.to_csv(GROUP_ANALYSIS_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print(f"[microstructure-shadow] samples: {SAMPLES_OUTPUT_PATH}")
    print(f"[microstructure-shadow] summary: {SUMMARY_OUTPUT_PATH}")
    print(f"[microstructure-shadow] predictions: {PREDICTIONS_OUTPUT_PATH}")
    print(json.dumps(split_metrics, ensure_ascii=False, indent=2))
    print(bucket_analysis_df.to_string(index=False))


if __name__ == "__main__":
    main()
