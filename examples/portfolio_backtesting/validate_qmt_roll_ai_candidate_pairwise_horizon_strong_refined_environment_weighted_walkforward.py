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
PAIR_SAMPLES_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_pairwise_horizon_strong_refined_samples.csv"
ENV_DAILY_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_refined_environment_daily_refined_environment_v1.csv"

MODEL_TAG: str = "pairwise_horizon_cls_v3_strong_refined_env_weighted_v1"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_pairwise_horizon_strong_refined_environment_weighted_summary_{MODEL_TAG}.json"
WINDOW_METRICS_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_pairwise_horizon_strong_refined_environment_weighted_window_metrics_{MODEL_TAG}.csv"
PREDICTIONS_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_pairwise_horizon_strong_refined_environment_weighted_predictions_{MODEL_TAG}.csv"

TARGET_COLUMN: str = "label_horizon_primary_left_wins"
WEIGHT_COLUMN: str = "label_horizon_primary_weight"
GROUP_COLUMN: str = "candidate_date"
STRENGTH_COLUMN: str = "label_horizon_primary_strength_bucket"
SUBTYPE_COLUMN: str = "label_strong_pair_subtype"
ENV_GATE_SCORE_COLUMN: str = "env_gate_score"
ENV_GATE_ON_COLUMN: str = "env_gate_on"
ENV_GATE_WEIGHT_COLUMN: str = "env_gate_weight"

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
    WalkForwardWindow("wf_2023", "2023-01-01", "2023-01-01", "2024-01-01"),
    WalkForwardWindow("wf_2024", "2024-01-01", "2024-01-01", "2025-01-01"),
    WalkForwardWindow("wf_2025_plus", "2025-01-01", "2025-01-01", None),
)

ENV_BINARY_RULES: dict[str, float] = {
    "avg_close_position_60d_1d_max": 0.42,
    "avg_range_pct_zscore_120_1d_min": 0.24,
    "selected_rate_1d_max": 0.56,
    "score_min": 2.0,
}

# Continuous gate prototype. The idea is not to fully shut the model off,
# but to shrink it back toward 0.5 when the daily environment looks less favorable.
ENV_WEIGHT_RULES: dict[str, float] = {
    "close_position_good_max": 0.25,
    "close_position_bad_min": 0.60,
    "range_good_min": 0.60,
    "range_bad_max": 0.00,
    "selected_rate_good_max": 0.35,
    "selected_rate_bad_min": 0.75,
    "weight_floor": 0.35,
}


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or np.isinf(result):
        return default
    return result


def _clip01(series: pd.Series) -> pd.Series:
    return series.clip(lower=0.0, upper=1.0)


def load_pair_samples() -> pd.DataFrame:
    df = pd.read_csv(PAIR_SAMPLES_PATH)
    df[GROUP_COLUMN] = pd.to_datetime(df[GROUP_COLUMN])
    df.sort_values([GROUP_COLUMN, "pair_id"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def load_environment_daily() -> pd.DataFrame:
    env_df = pd.read_csv(ENV_DAILY_PATH)
    env_df[GROUP_COLUMN] = pd.to_datetime(env_df[GROUP_COLUMN])

    env_df[ENV_GATE_SCORE_COLUMN] = (
        (env_df["avg_close_position_60d_1d"] <= ENV_BINARY_RULES["avg_close_position_60d_1d_max"]).astype("int64")
        + (env_df["avg_range_pct_zscore_120_1d"] >= ENV_BINARY_RULES["avg_range_pct_zscore_120_1d_min"]).astype("int64")
        + (env_df["selected_rate_1d"] <= ENV_BINARY_RULES["selected_rate_1d_max"]).astype("int64")
    )
    env_df[ENV_GATE_ON_COLUMN] = (env_df[ENV_GATE_SCORE_COLUMN] >= ENV_BINARY_RULES["score_min"]).astype("int64")

    close_component = _clip01(
        (ENV_WEIGHT_RULES["close_position_bad_min"] - env_df["avg_close_position_60d_1d"])
        / (ENV_WEIGHT_RULES["close_position_bad_min"] - ENV_WEIGHT_RULES["close_position_good_max"])
    )
    range_component = _clip01(
        (env_df["avg_range_pct_zscore_120_1d"] - ENV_WEIGHT_RULES["range_bad_max"])
        / (ENV_WEIGHT_RULES["range_good_min"] - ENV_WEIGHT_RULES["range_bad_max"])
    )
    selected_component = _clip01(
        (ENV_WEIGHT_RULES["selected_rate_bad_min"] - env_df["selected_rate_1d"])
        / (ENV_WEIGHT_RULES["selected_rate_bad_min"] - ENV_WEIGHT_RULES["selected_rate_good_max"])
    )
    base_weight = (close_component + range_component + selected_component) / 3.0
    env_df[ENV_GATE_WEIGHT_COLUMN] = ENV_WEIGHT_RULES["weight_floor"] + (
        1.0 - ENV_WEIGHT_RULES["weight_floor"]
    ) * base_weight
    env_df[ENV_GATE_WEIGHT_COLUMN] = env_df[ENV_GATE_WEIGHT_COLUMN].clip(lower=ENV_WEIGHT_RULES["weight_floor"], upper=1.0)
    return env_df


def build_dataset() -> pd.DataFrame:
    pair_df = load_pair_samples()
    env_df = load_environment_daily()
    merged_df = pair_df.merge(
        env_df[
            [
                GROUP_COLUMN,
                ENV_GATE_SCORE_COLUMN,
                ENV_GATE_ON_COLUMN,
                ENV_GATE_WEIGHT_COLUMN,
                "avg_close_position_60d_1d",
                "avg_range_pct_zscore_120_1d",
                "selected_rate_1d",
            ]
        ],
        on=GROUP_COLUMN,
        how="left",
    )
    merged_df[ENV_GATE_SCORE_COLUMN] = merged_df[ENV_GATE_SCORE_COLUMN].fillna(0.0)
    merged_df[ENV_GATE_ON_COLUMN] = merged_df[ENV_GATE_ON_COLUMN].fillna(0).astype("int64")
    merged_df[ENV_GATE_WEIGHT_COLUMN] = merged_df[ENV_GATE_WEIGHT_COLUMN].fillna(ENV_WEIGHT_RULES["weight_floor"]).astype("float64")
    return merged_df


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


def build_bucket_summary(df: pd.DataFrame, probability_column: str) -> dict[str, Any]:
    if df.empty or len(df) < 6:
        return {
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
    summary = (
        bucket_df.groupby("predicted_bucket", observed=False)
        .agg(actual_left_win_rate=(TARGET_COLUMN, "mean"))
        .reset_index()
    )
    values = {row["predicted_bucket"]: float(row["actual_left_win_rate"]) * 100.0 for row in summary.to_dict(orient="records")}
    low = values.get("low_left_win_prob", 0.0)
    mid = values.get("mid_left_win_prob", 0.0)
    high = values.get("high_left_win_prob", 0.0)
    return {
        "bucket_monotonicity_pass": bool(low <= mid <= high),
        "actual_left_win_rate_low": low,
        "actual_left_win_rate_mid": mid,
        "actual_left_win_rate_high": high,
    }


def flatten(prefix: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {f"{prefix}_{key}": value for key, value in payload.items()}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dataset_df = build_dataset()

    window_rows: list[dict[str, Any]] = []
    prediction_frames: list[pd.DataFrame] = []
    summary: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "feature_columns": FEATURE_COLUMNS,
        "environment_binary_rules": ENV_BINARY_RULES,
        "environment_weight_rules": ENV_WEIGHT_RULES,
        "windows": [],
        "research_note": "Weighted gate is a probability shrinker, not a deployable production gate.",
    }

    for window in WALK_FORWARD_WINDOWS:
        train_end = pd.Timestamp(window.train_end_exclusive)
        test_start = pd.Timestamp(window.test_start_inclusive)
        train_df = dataset_df[dataset_df[GROUP_COLUMN] < train_end].copy()
        test_df = dataset_df[dataset_df[GROUP_COLUMN] >= test_start].copy()
        if window.test_end_exclusive is not None:
            test_df = test_df[test_df[GROUP_COLUMN] < pd.Timestamp(window.test_end_exclusive)].copy()
        if train_df.empty or test_df.empty:
            continue

        model = train_model(train_df)
        scored_test_df = test_df.copy()
        scored_test_df["ungated_probability"] = score_dataframe(model, scored_test_df)
        scored_test_df["binary_probability"] = scored_test_df["ungated_probability"]
        scored_test_df.loc[scored_test_df[ENV_GATE_ON_COLUMN] == 0, "binary_probability"] = 0.5
        scored_test_df["weighted_probability"] = 0.5 + scored_test_df[ENV_GATE_WEIGHT_COLUMN] * (
            scored_test_df["ungated_probability"] - 0.5
        )
        scored_test_df["window_name"] = window.name

        ungated_metrics = compute_metrics(scored_test_df, "ungated_probability")
        binary_metrics = compute_metrics(scored_test_df, "binary_probability")
        weighted_metrics = compute_metrics(scored_test_df, "weighted_probability")
        ungated_bucket = build_bucket_summary(scored_test_df, "ungated_probability")
        weighted_bucket = build_bucket_summary(scored_test_df, "weighted_probability")

        row: dict[str, Any] = {
            "window_name": window.name,
            "train_end_exclusive": window.train_end_exclusive,
            "test_start_inclusive": window.test_start_inclusive,
            "test_end_exclusive": window.test_end_exclusive or "",
            "train_rows": int(len(train_df)),
            "train_days": int(train_df[GROUP_COLUMN].nunique()),
            "test_rows": int(len(test_df)),
            "test_days": int(test_df[GROUP_COLUMN].nunique()),
            "gate_weight_mean": _safe_float(scored_test_df[ENV_GATE_WEIGHT_COLUMN].mean()),
            "gate_weight_min": _safe_float(scored_test_df[ENV_GATE_WEIGHT_COLUMN].min()),
            "gate_weight_max": _safe_float(scored_test_df[ENV_GATE_WEIGHT_COLUMN].max()),
        }
        row.update(flatten("ungated", ungated_metrics))
        row.update(flatten("ungated_bucket", ungated_bucket))
        row.update(flatten("binary", binary_metrics))
        row.update(flatten("weighted", weighted_metrics))
        row.update(flatten("weighted_bucket", weighted_bucket))
        window_rows.append(row)

        prediction_columns = [
            "window_name",
            "pair_id",
            GROUP_COLUMN,
            "left_sample_id",
            "right_sample_id",
            STRENGTH_COLUMN,
            SUBTYPE_COLUMN,
            ENV_GATE_SCORE_COLUMN,
            ENV_GATE_ON_COLUMN,
            ENV_GATE_WEIGHT_COLUMN,
            TARGET_COLUMN,
            WEIGHT_COLUMN,
            "ungated_probability",
            "binary_probability",
            "weighted_probability",
            "avg_close_position_60d_1d",
            "avg_range_pct_zscore_120_1d",
            "selected_rate_1d",
        ]
        prediction_columns = [column for column in prediction_columns if column in scored_test_df.columns]
        prediction_frames.append(scored_test_df[prediction_columns].copy())

        summary["windows"].append(
            {
                "window_name": window.name,
                "train_end_exclusive": window.train_end_exclusive,
                "test_start_inclusive": window.test_start_inclusive,
                "test_end_exclusive": window.test_end_exclusive,
                "ungated_metrics": ungated_metrics,
                "binary_metrics": binary_metrics,
                "weighted_metrics": weighted_metrics,
                "ungated_bucket": ungated_bucket,
                "weighted_bucket": weighted_bucket,
                "gate_weight_mean": _safe_float(scored_test_df[ENV_GATE_WEIGHT_COLUMN].mean()),
            }
        )

    window_metrics_df = pd.DataFrame(window_rows)
    prediction_df = pd.concat(prediction_frames, ignore_index=True) if prediction_frames else pd.DataFrame()
    window_metrics_df.to_csv(WINDOW_METRICS_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    if not prediction_df.empty:
        prediction_df.to_csv(PREDICTIONS_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    summary["aggregate_judgement"] = {
        "mean_ungated_auc": _safe_float(window_metrics_df["ungated_roc_auc"].mean()) if not window_metrics_df.empty else 0.0,
        "mean_binary_auc": _safe_float(window_metrics_df["binary_roc_auc"].mean()) if not window_metrics_df.empty else 0.0,
        "mean_weighted_auc": _safe_float(window_metrics_df["weighted_roc_auc"].mean()) if not window_metrics_df.empty else 0.0,
    }
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[env-weighted-walkforward] summary: {SUMMARY_OUTPUT_PATH}")
    print(f"[env-weighted-walkforward] window metrics: {WINDOW_METRICS_OUTPUT_PATH}")
    print(f"[env-weighted-walkforward] predictions: {PREDICTIONS_OUTPUT_PATH}")
    if not window_metrics_df.empty:
        display_columns = [
            "window_name",
            "gate_weight_mean",
            "ungated_roc_auc",
            "binary_roc_auc",
            "weighted_roc_auc",
            "ungated_bucket_bucket_monotonicity_pass",
            "weighted_bucket_bucket_monotonicity_pass",
        ]
        display_columns = [column for column in display_columns if column in window_metrics_df.columns]
        print(window_metrics_df[display_columns].to_string(index=False))


if __name__ == "__main__":
    main()
