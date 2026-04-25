from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, f1_score, log_loss, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from train_qmt_roll_ai_microstructure_shadow_classifier import (
    DATE_COLUMN,
    FEATURE_GROUPS,
    IDENTITY_COLUMNS,
    SOURCE_SAMPLES_PATH,
    _numeric_series,
    _safe_float,
    add_generated_features,
    available_feature_columns,
    feature_group_lookup,
    load_source_samples,
    prepare_x,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "microstructure_relative_wf_v1"
SAMPLES_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_microstructure_relative_walkforward_samples_{MODEL_TAG}.csv"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_microstructure_relative_walkforward_summary_{MODEL_TAG}.json"
PREDICTIONS_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_microstructure_relative_walkforward_predictions_{MODEL_TAG}.csv"
WINDOW_METRICS_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_microstructure_relative_walkforward_window_metrics_{MODEL_TAG}.csv"
BUCKET_ANALYSIS_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_microstructure_relative_walkforward_bucket_analysis_{MODEL_TAG}.csv"
TOP_PICK_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_microstructure_relative_walkforward_top_picks_{MODEL_TAG}.csv"
COEFFICIENT_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_microstructure_relative_walkforward_coefficients_{MODEL_TAG}.csv"
GROUP_ANALYSIS_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_microstructure_relative_walkforward_group_analysis_{MODEL_TAG}.csv"

RANK_COLUMN: str = "label_candidate_quality_score_v2_rank_centered_1d"
QUALITY_COLUMN: str = "label_candidate_quality_score_v2"
CROSS_SECTION_COUNT_COLUMN: str = "label_candidate_cross_section_count_1d"
TARGET_COLUMN: str = "target_relative_quality_top_half"
WEIGHT_COLUMN: str = "sample_weight_relative_quality_rank"
PROBABILITY_COLUMN: str = "predicted_relative_quality_top_probability"

TRAIN_WINDOW_DAYS: int = 720
TEST_WINDOW_DAYS: int = 180
STEP_DAYS: int = 180
MIN_TRAIN_ROWS: int = 80
MIN_TEST_ROWS: int = 20
LOGISTIC_C: float = 0.20
RANDOM_STATE: int = 42


@dataclass(frozen=True)
class WalkForwardWindow:
    window_id: str
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def build_relative_samples() -> tuple[pd.DataFrame, list[str], dict[str, Any]]:
    source_df = add_generated_features(load_source_samples())
    feature_columns = available_feature_columns(source_df)

    samples_df = source_df.copy()
    samples_df[CROSS_SECTION_COUNT_COLUMN] = _numeric_series(samples_df, CROSS_SECTION_COUNT_COLUMN)
    samples_df = samples_df[samples_df[CROSS_SECTION_COUNT_COLUMN] >= 2.0].copy()

    samples_df["target_relative_quality_rank_centered"] = _numeric_series(samples_df, RANK_COLUMN)
    samples_df["target_relative_quality_score_v2"] = _numeric_series(samples_df, QUALITY_COLUMN)
    samples_df[TARGET_COLUMN] = (samples_df["target_relative_quality_rank_centered"] > 0.0).astype("int64")
    samples_df[WEIGHT_COLUMN] = samples_df["target_relative_quality_rank_centered"].abs().clip(lower=0.25, upper=1.0)

    selected_columns = [
        column
        for column in IDENTITY_COLUMNS
        + feature_columns
        + [
            CROSS_SECTION_COUNT_COLUMN,
            RANK_COLUMN,
            QUALITY_COLUMN,
            "target_relative_quality_rank_centered",
            "target_relative_quality_score_v2",
            TARGET_COLUMN,
            WEIGHT_COLUMN,
        ]
        if column in samples_df.columns
    ]
    samples_df = samples_df[selected_columns].copy()
    samples_df[DATE_COLUMN] = pd.to_datetime(samples_df[DATE_COLUMN])
    samples_df.sort_values([DATE_COLUMN, "sample_id"], inplace=True)
    samples_df.reset_index(drop=True, inplace=True)

    schema = {
        "dataset_name": f"qmt_roll_ai_microstructure_relative_walkforward_samples_{MODEL_TAG}",
        "source_dataset": str(SOURCE_SAMPLES_PATH.name),
        "model_usage": "shadow_diagnostic_only_not_trade_switch",
        "target_definition": {
            "target_column": TARGET_COLUMN,
            "target_rule": f"{RANK_COLUMN} > 0 and {CROSS_SECTION_COUNT_COLUMN} >= 2",
            "weight_column": WEIGHT_COLUMN,
            "weight_rule": f"clip(abs({RANK_COLUMN}), 0.25, 1.0)",
        },
        "walk_forward": {
            "train_window_days": TRAIN_WINDOW_DAYS,
            "test_window_days": TEST_WINDOW_DAYS,
            "step_days": STEP_DAYS,
            "min_train_rows": MIN_TRAIN_ROWS,
            "min_test_rows": MIN_TEST_ROWS,
        },
        "model": {
            "type": "logistic_regression",
            "regularization_c": LOGISTIC_C,
            "random_state": RANDOM_STATE,
        },
        "feature_groups": FEATURE_GROUPS,
        "feature_columns": feature_columns,
        "coverage_summary": {
            "rows": int(len(samples_df)),
            "days": int(samples_df[DATE_COLUMN].nunique()),
            "positive_rate": _safe_float(samples_df[TARGET_COLUMN].mean()),
            "avg_cross_section_count": _safe_float(samples_df[CROSS_SECTION_COUNT_COLUMN].mean()),
        },
        "design_judgement": "相对排序标签比绝对20日涨跌更接近真实用法：AI只在同一天候选之间排优先级，不预测全市场方向。",
    }
    return samples_df, feature_columns, schema


def build_walk_forward_windows(samples_df: pd.DataFrame) -> list[WalkForwardWindow]:
    min_date = pd.Timestamp(samples_df[DATE_COLUMN].min()).normalize()
    max_date = pd.Timestamp(samples_df[DATE_COLUMN].max()).normalize()
    windows: list[WalkForwardWindow] = []
    train_start = min_date
    window_index = 1

    while True:
        train_end = train_start + pd.Timedelta(days=TRAIN_WINDOW_DAYS)
        test_start = train_end
        test_end = test_start + pd.Timedelta(days=TEST_WINDOW_DAYS)
        if test_start > max_date:
            break

        train_df = samples_df[(samples_df[DATE_COLUMN] >= train_start) & (samples_df[DATE_COLUMN] < train_end)]
        test_df = samples_df[(samples_df[DATE_COLUMN] >= test_start) & (samples_df[DATE_COLUMN] < test_end)]
        if (
            len(train_df) >= MIN_TRAIN_ROWS
            and len(test_df) >= MIN_TEST_ROWS
            and train_df[TARGET_COLUMN].nunique() >= 2
            and test_df[TARGET_COLUMN].nunique() >= 2
        ):
            windows.append(
                WalkForwardWindow(
                    window_id=f"wf_{window_index:02d}",
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                )
            )
            window_index += 1

        train_start = train_start + pd.Timedelta(days=STEP_DAYS)
        if train_start >= max_date:
            break

    return windows


def train_model(train_df: pd.DataFrame, feature_columns: list[str]) -> Pipeline:
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
    return model


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
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "roc_auc": 0.0,
            "log_loss": 0.0,
            "brier_score": 0.0,
            "avg_rank_centered": 0.0,
            "avg_quality_score_v2": 0.0,
        }

    actual = df[TARGET_COLUMN].astype("int64")
    probability = df[PROBABILITY_COLUMN].astype("float64").clip(1e-6, 1 - 1e-6)
    predicted = (probability >= 0.5).astype("int64")
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
        "precision": _safe_float(precision_score(actual, predicted, zero_division=0)),
        "recall": _safe_float(recall_score(actual, predicted, zero_division=0)),
        "f1": _safe_float(f1_score(actual, predicted, zero_division=0)),
        "roc_auc": _safe_float(auc),
        "log_loss": _safe_float(log_loss(actual, probability, labels=[0, 1])),
        "brier_score": _safe_float(brier_score_loss(actual, probability)),
        "avg_rank_centered": _safe_float(df["target_relative_quality_rank_centered"].mean()),
        "avg_quality_score_v2": _safe_float(df["target_relative_quality_score_v2"].mean()),
    }


def build_coefficients(
    model: Pipeline,
    feature_columns: list[str],
    window: WalkForwardWindow,
) -> pd.DataFrame:
    classifier: LogisticRegression = model.named_steps["classifier"]
    scaler: StandardScaler = model.named_steps["scaler"]
    group_lookup = feature_group_lookup(feature_columns)
    coefficient_df = pd.DataFrame(
        {
            "window_id": window.window_id,
            "train_start": window.train_start.date().isoformat(),
            "train_end": window.train_end.date().isoformat(),
            "test_start": window.test_start.date().isoformat(),
            "test_end": window.test_end.date().isoformat(),
            "feature": feature_columns,
            "feature_group": [group_lookup[column] for column in feature_columns],
            "scaled_coefficient": classifier.coef_[0],
            "abs_scaled_coefficient": np.abs(classifier.coef_[0]),
            "feature_mean": scaler.mean_,
            "feature_scale": scaler.scale_,
        }
    )
    coefficient_df.sort_values(["window_id", "abs_scaled_coefficient"], ascending=[True, False], inplace=True)
    coefficient_df.reset_index(drop=True, inplace=True)
    return coefficient_df


def build_bucket_analysis(predictions_df: pd.DataFrame) -> pd.DataFrame:
    if predictions_df.empty:
        return pd.DataFrame()

    bucket_count = min(5, len(predictions_df))
    bucket_df = predictions_df.copy()
    bucket_df["probability_bucket"] = pd.qcut(
        bucket_df[PROBABILITY_COLUMN].rank(method="first"),
        q=bucket_count,
        labels=[f"q{i + 1}" for i in range(bucket_count)],
    ).astype(str)
    return (
        bucket_df.groupby("probability_bucket", observed=False)
        .agg(
            sample_count=("sample_id", "count"),
            avg_probability=(PROBABILITY_COLUMN, "mean"),
            actual_top_half_rate=(TARGET_COLUMN, "mean"),
            avg_rank_centered=("target_relative_quality_rank_centered", "mean"),
            avg_quality_score_v2=("target_relative_quality_score_v2", "mean"),
            selected_rate=("label_is_selected", "mean"),
        )
        .reset_index()
    )


def build_top_picks(predictions_df: pd.DataFrame) -> pd.DataFrame:
    if predictions_df.empty:
        return pd.DataFrame()

    idx = predictions_df.groupby(DATE_COLUMN)[PROBABILITY_COLUMN].idxmax()
    top_pick_df = predictions_df.loc[idx].copy()
    top_pick_df.sort_values(DATE_COLUMN, inplace=True)
    top_pick_df.reset_index(drop=True, inplace=True)
    return top_pick_df


def build_group_analysis(coefficients_df: pd.DataFrame) -> pd.DataFrame:
    if coefficients_df.empty:
        return pd.DataFrame()
    return (
        coefficients_df.groupby("feature_group", observed=False)
        .agg(
            feature_window_count=("feature", "count"),
            mean_abs_scaled_coefficient=("abs_scaled_coefficient", "mean"),
            median_abs_scaled_coefficient=("abs_scaled_coefficient", "median"),
            max_abs_scaled_coefficient=("abs_scaled_coefficient", "max"),
            mean_scaled_coefficient=("scaled_coefficient", "mean"),
        )
        .reset_index()
        .sort_values("mean_abs_scaled_coefficient", ascending=False)
    )


def run_walk_forward(samples_df: pd.DataFrame, feature_columns: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    windows = build_walk_forward_windows(samples_df)
    prediction_frames: list[pd.DataFrame] = []
    metric_rows: list[dict[str, Any]] = []
    coefficient_frames: list[pd.DataFrame] = []

    for window in windows:
        train_df = samples_df[
            (samples_df[DATE_COLUMN] >= window.train_start) & (samples_df[DATE_COLUMN] < window.train_end)
        ].copy()
        test_df = samples_df[
            (samples_df[DATE_COLUMN] >= window.test_start) & (samples_df[DATE_COLUMN] < window.test_end)
        ].copy()

        model = train_model(train_df, feature_columns)
        test_scored_df = test_df.copy()
        test_scored_df[PROBABILITY_COLUMN] = score_dataframe(model, test_scored_df, feature_columns)
        test_scored_df["window_id"] = window.window_id
        test_scored_df["train_start"] = window.train_start.date().isoformat()
        test_scored_df["train_end"] = window.train_end.date().isoformat()
        test_scored_df["test_start"] = window.test_start.date().isoformat()
        test_scored_df["test_end"] = window.test_end.date().isoformat()
        prediction_frames.append(test_scored_df)

        train_scored_df = train_df.copy()
        train_scored_df[PROBABILITY_COLUMN] = score_dataframe(model, train_scored_df, feature_columns)
        row = {
            "window_id": window.window_id,
            "train_start": window.train_start.date().isoformat(),
            "train_end": window.train_end.date().isoformat(),
            "test_start": window.test_start.date().isoformat(),
            "test_end": window.test_end.date().isoformat(),
        }
        row.update({f"train_{key}": value for key, value in compute_metrics(train_scored_df).items()})
        row.update({f"test_{key}": value for key, value in compute_metrics(test_scored_df).items()})
        metric_rows.append(row)
        coefficient_frames.append(build_coefficients(model, feature_columns, window))

    predictions_df = pd.concat(prediction_frames, ignore_index=True) if prediction_frames else pd.DataFrame()
    window_metrics_df = pd.DataFrame(metric_rows)
    coefficients_df = pd.concat(coefficient_frames, ignore_index=True) if coefficient_frames else pd.DataFrame()
    return predictions_df, window_metrics_df, coefficients_df


def summarize_top_picks(predictions_df: pd.DataFrame, top_pick_df: pd.DataFrame) -> dict[str, Any]:
    if predictions_df.empty or top_pick_df.empty:
        return {}

    baseline_daily_top_rate = predictions_df.groupby(DATE_COLUMN)[TARGET_COLUMN].mean().mean()
    return {
        "top_pick_days": int(len(top_pick_df)),
        "top_pick_hit_rate": _safe_float(top_pick_df[TARGET_COLUMN].mean()),
        "baseline_daily_candidate_top_half_rate": _safe_float(baseline_daily_top_rate),
        "top_pick_edge_vs_daily_baseline": _safe_float(top_pick_df[TARGET_COLUMN].mean() - baseline_daily_top_rate),
        "top_pick_avg_rank_centered": _safe_float(top_pick_df["target_relative_quality_rank_centered"].mean()),
        "top_pick_avg_quality_score_v2": _safe_float(top_pick_df["target_relative_quality_score_v2"].mean()),
        "top_pick_selected_rate": _safe_float(top_pick_df["label_is_selected"].mean()) if "label_is_selected" in top_pick_df.columns else 0.0,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    samples_df, feature_columns, schema = build_relative_samples()
    predictions_df, window_metrics_df, coefficients_df = run_walk_forward(samples_df, feature_columns)
    bucket_analysis_df = build_bucket_analysis(predictions_df)
    top_pick_df = build_top_picks(predictions_df)
    group_analysis_df = build_group_analysis(coefficients_df)

    oos_metrics = compute_metrics(predictions_df) if not predictions_df.empty else {}
    rank_spearman = (
        predictions_df[[PROBABILITY_COLUMN, "target_relative_quality_rank_centered"]]
        .corr(method="spearman")
        .iloc[0, 1]
        if not predictions_df.empty
        else float("nan")
    )
    quality_spearman = (
        predictions_df[[PROBABILITY_COLUMN, "target_relative_quality_score_v2"]].corr(method="spearman").iloc[0, 1]
        if not predictions_df.empty
        else float("nan")
    )

    summary = {
        "model_tag": MODEL_TAG,
        "model_usage": "shadow_diagnostic_only_not_trade_switch",
        "source_dataset": str(SOURCE_SAMPLES_PATH),
        "schema": schema,
        "feature_columns": feature_columns,
        "output_files": {
            "samples": str(SAMPLES_OUTPUT_PATH),
            "summary": str(SUMMARY_OUTPUT_PATH),
            "predictions": str(PREDICTIONS_OUTPUT_PATH),
            "window_metrics": str(WINDOW_METRICS_OUTPUT_PATH),
            "bucket_analysis": str(BUCKET_ANALYSIS_OUTPUT_PATH),
            "top_picks": str(TOP_PICK_OUTPUT_PATH),
            "coefficients": str(COEFFICIENT_OUTPUT_PATH),
            "group_analysis": str(GROUP_ANALYSIS_OUTPUT_PATH),
        },
        "dataset_rows": int(len(samples_df)),
        "dataset_days": int(samples_df[DATE_COLUMN].nunique()),
        "walk_forward_window_count": int(window_metrics_df["window_id"].nunique()) if not window_metrics_df.empty else 0,
        "oos_metrics": oos_metrics,
        "oos_spearman": {
            "probability_vs_rank_centered": _safe_float(rank_spearman),
            "probability_vs_quality_score_v2": _safe_float(quality_spearman),
        },
        "top_pick_summary": summarize_top_picks(predictions_df, top_pick_df),
        "window_metrics": window_metrics_df.to_dict(orient="records"),
        "bucket_analysis": bucket_analysis_df.to_dict(orient="records"),
        "feature_group_analysis": group_analysis_df.to_dict(orient="records"),
        "model_judgement": {
            "first_principle": "截面排序比绝对方向更接近交易系统中的真实用途；如果连同日候选排序都不稳定，就不应该让AI影响仓位。",
            "promotion_rule": "只有走前整体AUC、top-pick命中率、分桶单调性同时成立，才能进入纸面跟踪；仍不能直接接入实盘。",
        },
    }

    samples_df.to_csv(SAMPLES_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    predictions_df.to_csv(PREDICTIONS_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    window_metrics_df.to_csv(WINDOW_METRICS_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    bucket_analysis_df.to_csv(BUCKET_ANALYSIS_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    top_pick_df.to_csv(TOP_PICK_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    coefficients_df.to_csv(COEFFICIENT_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    group_analysis_df.to_csv(GROUP_ANALYSIS_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print(f"[microstructure-relative-wf] summary: {SUMMARY_OUTPUT_PATH}")
    print(f"[microstructure-relative-wf] predictions: {PREDICTIONS_OUTPUT_PATH}")
    print(json.dumps({"oos_metrics": oos_metrics, "top_pick_summary": summary["top_pick_summary"]}, ensure_ascii=False, indent=2))
    print(window_metrics_df.to_string(index=False))
    print(bucket_analysis_df.to_string(index=False))


if __name__ == "__main__":
    main()
