from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
SAMPLES_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_pairwise_samples.csv"

MODEL_TAG: str = "pairwise_cls_v1"
MODEL_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_pairwise_classifier_{MODEL_TAG}.joblib"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_pairwise_classifier_summary_{MODEL_TAG}.json"
COEFFICIENT_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_pairwise_classifier_coefficients_{MODEL_TAG}.csv"
PREDICTIONS_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_pairwise_classifier_predictions_{MODEL_TAG}.csv"
BUCKET_ANALYSIS_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_pairwise_classifier_bucket_analysis_{MODEL_TAG}.csv"

TARGET_COLUMN: str = "label_left_wins"
WEIGHT_COLUMN: str = "label_pair_weight"
GROUP_COLUMN: str = "candidate_date"
STRENGTH_COLUMN: str = "label_pair_strength_bucket"
VALID_START_DATE: str = "2023-01-01"
TEST_START_DATE: str = "2024-01-01"

# Keep the feature set intentionally small. The pairwise dataset is still thin,
# so a high-capacity model would mostly learn noise.
FEATURE_COLUMNS: list[str] = [
    "feature_pair_same_direction",
    "feature_pair_same_signal",
    "delta_risk_ratio",
    "delta_remaining_position_slots",
    "delta_feature_ret_signed_5d",
    "delta_feature_trend_ma20_gap_pct",
    "delta_feature_atr14_pct_zscore_120",
    "delta_feature_lower_wick_pct",
    "delta_feature_volume_ratio_2v2",
    "delta_feature_margin_per_contract_to_equity",
    "delta_feature_oi_delta_1d_pct",
    "delta_feature_oi_delta_1d_pct_zscore_120",
]


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or np.isinf(result):
        return default
    return result


def load_samples() -> pd.DataFrame:
    df = pd.read_csv(SAMPLES_PATH)
    df[GROUP_COLUMN] = pd.to_datetime(df[GROUP_COLUMN])
    df.sort_values([GROUP_COLUMN, "pair_id"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def build_split(df: pd.DataFrame) -> pd.DataFrame:
    valid_start = pd.Timestamp(VALID_START_DATE)
    test_start = pd.Timestamp(TEST_START_DATE)

    split_series = pd.Series("train", index=df.index, dtype="object")
    split_series.loc[df[GROUP_COLUMN] >= valid_start] = "valid"
    split_series.loc[df[GROUP_COLUMN] >= test_start] = "test"
    result = df.copy()
    result["dataset_split"] = split_series
    return result


def prepare_x(df: pd.DataFrame) -> pd.DataFrame:
    x = df[FEATURE_COLUMNS].copy()
    for column in FEATURE_COLUMNS:
        x[column] = pd.to_numeric(x[column], errors="coerce").fillna(0.0)
    return x


def train_model(train_df: pd.DataFrame) -> tuple[Pipeline, dict[str, Any]]:
    x_train = prepare_x(train_df)
    y_train = train_df[TARGET_COLUMN].astype("int64")
    sample_weight = train_df[WEIGHT_COLUMN].astype("float64")

    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    C=0.35,
                    solver="lbfgs",
                    max_iter=2000,
                    random_state=42,
                ),
            ),
        ]
    )
    model.fit(x_train, y_train, classifier__sample_weight=sample_weight)
    metadata = {
        "model_type": "logistic_regression",
        "feature_columns": FEATURE_COLUMNS,
        "target_column": TARGET_COLUMN,
        "weight_column": WEIGHT_COLUMN,
        "train_rows": int(len(train_df)),
        "train_days": int(train_df[GROUP_COLUMN].nunique()),
    }
    return model, metadata


def score_dataframe(model: Pipeline, df: pd.DataFrame) -> np.ndarray:
    x = prepare_x(df)
    probabilities = model.predict_proba(x)[:, 1]
    return np.asarray(probabilities, dtype="float64")


def compute_metrics(df: pd.DataFrame, probability_column: str) -> dict[str, Any]:
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
        }

    actual = df[TARGET_COLUMN].astype("int64")
    probability = df[probability_column].astype("float64").clip(1e-6, 1 - 1e-6)
    predicted = (probability >= 0.5).astype("int64")
    sample_weight = df[WEIGHT_COLUMN].astype("float64")

    try:
        auc = roc_auc_score(actual, probability) if actual.nunique() >= 2 else float("nan")
    except ValueError:
        auc = float("nan")

    return {
        "rows": int(len(df)),
        "days": int(df[GROUP_COLUMN].nunique()),
        "positive_rate": _safe_float(actual.mean()),
        "predicted_positive_rate": _safe_float(predicted.mean()),
        "accuracy": _safe_float(accuracy_score(actual, predicted)),
        "weighted_accuracy": _safe_float(accuracy_score(actual, predicted, sample_weight=sample_weight)),
        "precision": _safe_float(precision_score(actual, predicted, zero_division=0)),
        "recall": _safe_float(recall_score(actual, predicted, zero_division=0)),
        "f1": _safe_float(f1_score(actual, predicted, zero_division=0)),
        "roc_auc": _safe_float(auc),
        "log_loss": _safe_float(log_loss(actual, probability, sample_weight=sample_weight, labels=[0, 1])),
    }


def compute_strength_metrics(df: pd.DataFrame, probability_column: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for bucket in ["weak", "medium", "strong"]:
        bucket_df = df[df[STRENGTH_COLUMN] == bucket].copy()
        result[bucket] = compute_metrics(bucket_df, probability_column)
    return result


def build_bucket_analysis(df: pd.DataFrame, probability_column: str) -> pd.DataFrame:
    test_df = df[df["dataset_split"] == "test"].copy()
    if test_df.empty:
        return pd.DataFrame()

    test_df["predicted_bucket"] = pd.qcut(
        test_df[probability_column].rank(method="first"),
        q=3,
        labels=["low_left_win_prob", "mid_left_win_prob", "high_left_win_prob"],
    )
    test_df["prediction_correct"] = (
        (test_df[probability_column] >= 0.5).astype("int64") == test_df[TARGET_COLUMN].astype("int64")
    ).astype("int64")

    summary = (
        test_df.groupby("predicted_bucket", observed=False)
        .agg(
            sample_count=("pair_id", "count"),
            avg_predicted_left_win_prob=(probability_column, "mean"),
            actual_left_win_rate=(TARGET_COLUMN, "mean"),
            weighted_accuracy=("prediction_correct", "mean"),
            avg_quality_gap_abs=("label_quality_gap_abs", "mean"),
            winner_selected_rate=("label_winner_selected", "mean"),
        )
        .reset_index()
    )
    summary["actual_left_win_rate"] = summary["actual_left_win_rate"] * 100.0
    summary["weighted_accuracy"] = summary["weighted_accuracy"] * 100.0
    summary["winner_selected_rate"] = summary["winner_selected_rate"] * 100.0
    return summary


def build_coefficients(model: Pipeline) -> pd.DataFrame:
    classifier: LogisticRegression = model.named_steps["classifier"]
    scaler: StandardScaler = model.named_steps["scaler"]
    coefficients = classifier.coef_[0]
    coefficient_df = pd.DataFrame(
        {
            "feature": FEATURE_COLUMNS,
            "scaled_coefficient": coefficients,
            "abs_scaled_coefficient": np.abs(coefficients),
            "feature_mean": scaler.mean_,
            "feature_scale": scaler.scale_,
        }
    )
    coefficient_df.sort_values("abs_scaled_coefficient", ascending=False, inplace=True)
    coefficient_df.reset_index(drop=True, inplace=True)
    return coefficient_df


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_samples()
    df = build_split(df)

    train_df = df[df["dataset_split"] == "train"].copy()
    valid_df = df[df["dataset_split"] == "valid"].copy()
    test_df = df[df["dataset_split"] == "test"].copy()

    model, metadata = train_model(train_df)

    scored_df = df.copy()
    scored_df["predicted_left_win_probability"] = score_dataframe(model, scored_df)

    split_metrics = {
        "train": compute_metrics(scored_df[scored_df["dataset_split"] == "train"], "predicted_left_win_probability"),
        "valid": compute_metrics(scored_df[scored_df["dataset_split"] == "valid"], "predicted_left_win_probability"),
        "test": compute_metrics(scored_df[scored_df["dataset_split"] == "test"], "predicted_left_win_probability"),
    }
    strength_metrics = {
        "train": compute_strength_metrics(
            scored_df[scored_df["dataset_split"] == "train"], "predicted_left_win_probability"
        ),
        "valid": compute_strength_metrics(
            scored_df[scored_df["dataset_split"] == "valid"], "predicted_left_win_probability"
        ),
        "test": compute_strength_metrics(
            scored_df[scored_df["dataset_split"] == "test"], "predicted_left_win_probability"
        ),
    }
    bucket_df = build_bucket_analysis(scored_df, "predicted_left_win_probability")
    coefficient_df = build_coefficients(model)

    summary = {
        "model_metadata": metadata,
        "model_tag": MODEL_TAG,
        "split_dates": {
            "valid_start_date": VALID_START_DATE,
            "test_start_date": TEST_START_DATE,
        },
        "dataset_rows": int(len(df)),
        "dataset_days": int(df[GROUP_COLUMN].nunique()),
        "split_metrics": split_metrics,
        "strength_metrics": strength_metrics,
        "top_coefficients": coefficient_df.head(20).to_dict(orient="records"),
        "model_judgement": {
            "why_linear_baseline": "pairwise 样本仍然较薄，先用低自由度线性模型验证是否存在稳定方向性信号。",
            "use_sample_weight": "用 label_pair_weight 提升大质量差样本的重要性，降低边缘 pair 的噪声影响。",
        },
    }

    joblib.dump(model, MODEL_OUTPUT_PATH)
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    coefficient_df.to_csv(COEFFICIENT_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    prediction_columns = [
        "pair_id",
        "candidate_date",
        "dataset_split",
        "left_sample_id",
        "right_sample_id",
        TARGET_COLUMN,
        WEIGHT_COLUMN,
        STRENGTH_COLUMN,
        "label_quality_gap_abs",
        "label_winner_selected",
        "predicted_left_win_probability",
    ]
    prediction_columns = [column for column in prediction_columns if column in scored_df.columns]
    scored_df[prediction_columns].to_csv(PREDICTIONS_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    if not bucket_df.empty:
        bucket_df.to_csv(BUCKET_ANALYSIS_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print(f"[ai-candidate-pairwise-classifier] model: {MODEL_OUTPUT_PATH}")
    print(f"[ai-candidate-pairwise-classifier] summary: {SUMMARY_OUTPUT_PATH}")
    print(f"[ai-candidate-pairwise-classifier] coefficients: {COEFFICIENT_OUTPUT_PATH}")
    print(f"[ai-candidate-pairwise-classifier] predictions: {PREDICTIONS_OUTPUT_PATH}")
    print(f"[ai-candidate-pairwise-classifier] bucket analysis: {BUCKET_ANALYSIS_OUTPUT_PATH}")
    print(json.dumps(split_metrics, ensure_ascii=False, indent=2))
    print(json.dumps(strength_metrics, ensure_ascii=False, indent=2))
    if not bucket_df.empty:
        print(bucket_df.to_string(index=False))


if __name__ == "__main__":
    main()
