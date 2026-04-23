from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
SAMPLES_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_pairwise_horizon_strong_refined_samples.csv"

MODEL_TAG: str = "pairwise_horizon_cls_v3_strong_refined_walkforward"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_pairwise_horizon_strong_refined_walkforward_summary_{MODEL_TAG}.json"
WINDOW_METRICS_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_pairwise_horizon_strong_refined_walkforward_window_metrics_{MODEL_TAG}.csv"
BUCKET_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_pairwise_horizon_strong_refined_walkforward_bucket_analysis_{MODEL_TAG}.csv"
PREDICTIONS_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_pairwise_horizon_strong_refined_walkforward_predictions_{MODEL_TAG}.csv"

TARGET_COLUMN: str = "label_horizon_primary_left_wins"
WEIGHT_COLUMN: str = "label_horizon_primary_weight"
GROUP_COLUMN: str = "candidate_date"
STRENGTH_COLUMN: str = "label_horizon_primary_strength_bucket"
SUBTYPE_COLUMN: str = "label_strong_pair_subtype"

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


@dataclass(frozen=True)
class WalkForwardWindow:
    name: str
    train_end_exclusive: str
    test_start_inclusive: str
    test_end_exclusive: str | None


WALK_FORWARD_WINDOWS: tuple[WalkForwardWindow, ...] = (
    WalkForwardWindow(
        name="wf_2023",
        train_end_exclusive="2023-01-01",
        test_start_inclusive="2023-01-01",
        test_end_exclusive="2024-01-01",
    ),
    WalkForwardWindow(
        name="wf_2024",
        train_end_exclusive="2024-01-01",
        test_start_inclusive="2024-01-01",
        test_end_exclusive="2025-01-01",
    ),
    WalkForwardWindow(
        name="wf_2025_plus",
        train_end_exclusive="2025-01-01",
        test_start_inclusive="2025-01-01",
        test_end_exclusive=None,
    ),
)


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


def prepare_x(df: pd.DataFrame) -> pd.DataFrame:
    x = df[FEATURE_COLUMNS].copy()
    for column in FEATURE_COLUMNS:
        x[column] = pd.to_numeric(x[column], errors="coerce").fillna(0.0)
    return x


def train_model(train_df: pd.DataFrame) -> Pipeline:
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
    return model


def score_dataframe(model: Pipeline, df: pd.DataFrame) -> np.ndarray:
    probabilities = model.predict_proba(prepare_x(df))[:, 1]
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


def compute_subtype_metrics(df: pd.DataFrame, probability_column: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for subtype in sorted(df[SUBTYPE_COLUMN].dropna().unique().tolist()):
        subtype_df = df[df[SUBTYPE_COLUMN] == subtype].copy()
        result[subtype] = compute_metrics(subtype_df, probability_column)
    return result


def build_bucket_analysis(df: pd.DataFrame, probability_column: str, *, window_name: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    if df.empty:
        return pd.DataFrame(), {
            "bucket_monotonicity_pass": False,
            "actual_left_win_rate_low": 0.0,
            "actual_left_win_rate_mid": 0.0,
            "actual_left_win_rate_high": 0.0,
        }

    bucket_df = df.copy()
    bucket_df["predicted_bucket"] = pd.qcut(
        bucket_df[probability_column].rank(method="first"),
        q=3,
        labels=["low_left_win_prob", "mid_left_win_prob", "high_left_win_prob"],
    )
    bucket_df["prediction_correct"] = (
        (bucket_df[probability_column] >= 0.5).astype("int64") == bucket_df[TARGET_COLUMN].astype("int64")
    ).astype("int64")
    summary = (
        bucket_df.groupby("predicted_bucket", observed=False)
        .agg(
            sample_count=("pair_id", "count"),
            avg_predicted_left_win_prob=(probability_column, "mean"),
            actual_left_win_rate=(TARGET_COLUMN, "mean"),
            weighted_accuracy=("prediction_correct", "mean"),
            avg_primary_gap_abs=("label_horizon_primary_gap_abs", "mean"),
            avg_trend_diff=("abs_delta_feature_trend_ma20_gap_pct", "mean"),
            avg_ret20_diff=("abs_delta_feature_ret_20d_zscore_120", "mean"),
            winner_selected_rate=("label_winner_selected", "mean"),
        )
        .reset_index()
    )
    summary["window_name"] = window_name
    summary["actual_left_win_rate"] = summary["actual_left_win_rate"] * 100.0
    summary["weighted_accuracy"] = summary["weighted_accuracy"] * 100.0
    summary["winner_selected_rate"] = summary["winner_selected_rate"] * 100.0

    bucket_values = {
        row["predicted_bucket"]: float(row["actual_left_win_rate"])
        for row in summary.to_dict(orient="records")
    }
    low = bucket_values.get("low_left_win_prob", 0.0)
    mid = bucket_values.get("mid_left_win_prob", 0.0)
    high = bucket_values.get("high_left_win_prob", 0.0)
    monotonicity = bool(low <= mid <= high)

    return summary, {
        "bucket_monotonicity_pass": monotonicity,
        "actual_left_win_rate_low": low,
        "actual_left_win_rate_mid": mid,
        "actual_left_win_rate_high": high,
    }


def flatten_metrics(prefix: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {f"{prefix}_{key}": value for key, value in metrics.items()}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source_df = load_samples()

    window_rows: list[dict[str, Any]] = []
    bucket_frames: list[pd.DataFrame] = []
    prediction_frames: list[pd.DataFrame] = []
    summary_payload: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "feature_columns": FEATURE_COLUMNS,
        "windows": [],
    }

    for window in WALK_FORWARD_WINDOWS:
        train_end = pd.Timestamp(window.train_end_exclusive)
        test_start = pd.Timestamp(window.test_start_inclusive)
        train_df = source_df[source_df[GROUP_COLUMN] < train_end].copy()
        test_df = source_df[source_df[GROUP_COLUMN] >= test_start].copy()
        if window.test_end_exclusive is not None:
            test_df = test_df[test_df[GROUP_COLUMN] < pd.Timestamp(window.test_end_exclusive)].copy()

        if train_df.empty or test_df.empty:
            continue

        model = train_model(train_df)
        scored_test_df = test_df.copy()
        scored_test_df["predicted_left_win_probability"] = score_dataframe(model, scored_test_df)
        scored_test_df["window_name"] = window.name

        overall_metrics = compute_metrics(scored_test_df, "predicted_left_win_probability")
        strength_metrics = compute_strength_metrics(scored_test_df, "predicted_left_win_probability")
        subtype_metrics = compute_subtype_metrics(scored_test_df, "predicted_left_win_probability")
        bucket_df, bucket_summary = build_bucket_analysis(
            scored_test_df,
            "predicted_left_win_probability",
            window_name=window.name,
        )

        row: dict[str, Any] = {
            "window_name": window.name,
            "train_end_exclusive": window.train_end_exclusive,
            "test_start_inclusive": window.test_start_inclusive,
            "test_end_exclusive": window.test_end_exclusive or "",
            "train_rows": int(len(train_df)),
            "train_days": int(train_df[GROUP_COLUMN].nunique()),
            "test_rows": int(len(test_df)),
            "test_days": int(test_df[GROUP_COLUMN].nunique()),
        }
        row.update(flatten_metrics("overall", overall_metrics))
        row.update(flatten_metrics("bucket", bucket_summary))

        for bucket_name, bucket_metrics in strength_metrics.items():
            row.update(flatten_metrics(f"strength_{bucket_name}", bucket_metrics))
        for subtype_name, subtype_metric in subtype_metrics.items():
            safe_subtype = subtype_name.replace("-", "_").replace(" ", "_")
            row.update(flatten_metrics(f"subtype_{safe_subtype}", subtype_metric))

        window_rows.append(row)
        if not bucket_df.empty:
            bucket_frames.append(bucket_df)

        prediction_columns = [
            "window_name",
            "pair_id",
            "candidate_date",
            "left_sample_id",
            "right_sample_id",
            STRENGTH_COLUMN,
            SUBTYPE_COLUMN,
            TARGET_COLUMN,
            WEIGHT_COLUMN,
            "predicted_left_win_probability",
            "label_horizon_primary_gap_abs",
            "label_winner_selected",
        ]
        prediction_columns = [column for column in prediction_columns if column in scored_test_df.columns]
        prediction_frames.append(scored_test_df[prediction_columns].copy())

        summary_payload["windows"].append(
            {
                "window_name": window.name,
                "train_end_exclusive": window.train_end_exclusive,
                "test_start_inclusive": window.test_start_inclusive,
                "test_end_exclusive": window.test_end_exclusive,
                "train_rows": int(len(train_df)),
                "train_days": int(train_df[GROUP_COLUMN].nunique()),
                "test_rows": int(len(test_df)),
                "test_days": int(test_df[GROUP_COLUMN].nunique()),
                "overall_metrics": overall_metrics,
                "strength_metrics": strength_metrics,
                "subtype_metrics": subtype_metrics,
                "bucket_summary": bucket_summary,
            }
        )

    metrics_df = pd.DataFrame(window_rows)
    bucket_all_df = pd.concat(bucket_frames, ignore_index=True) if bucket_frames else pd.DataFrame()
    predictions_df = pd.concat(prediction_frames, ignore_index=True) if prediction_frames else pd.DataFrame()

    metrics_df.to_csv(WINDOW_METRICS_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    if not bucket_all_df.empty:
        bucket_all_df.to_csv(BUCKET_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    if not predictions_df.empty:
        predictions_df.to_csv(PREDICTIONS_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    summary_payload["aggregate_judgement"] = {
        "window_count": int(len(summary_payload["windows"])),
        "all_bucket_monotonicity_pass": bool(
            summary_payload["windows"]
            and all(window["bucket_summary"]["bucket_monotonicity_pass"] for window in summary_payload["windows"])
        ),
        "mean_test_auc": _safe_float(metrics_df["overall_roc_auc"].mean()) if not metrics_df.empty else 0.0,
        "mean_test_weighted_accuracy": _safe_float(metrics_df["overall_weighted_accuracy"].mean()) if not metrics_df.empty else 0.0,
    }
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[walkforward] summary: {SUMMARY_OUTPUT_PATH}")
    print(f"[walkforward] window metrics: {WINDOW_METRICS_OUTPUT_PATH}")
    print(f"[walkforward] bucket analysis: {BUCKET_OUTPUT_PATH}")
    print(f"[walkforward] predictions: {PREDICTIONS_OUTPUT_PATH}")
    if not metrics_df.empty:
        display_columns = [
            "window_name",
            "train_rows",
            "test_rows",
            "overall_accuracy",
            "overall_weighted_accuracy",
            "overall_roc_auc",
            "bucket_actual_left_win_rate_low",
            "bucket_actual_left_win_rate_mid",
            "bucket_actual_left_win_rate_high",
            "bucket_bucket_monotonicity_pass",
        ]
        display_columns = [column for column in display_columns if column in metrics_df.columns]
        print(metrics_df[display_columns].to_string(index=False))


if __name__ == "__main__":
    main()
