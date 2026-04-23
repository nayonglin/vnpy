from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)

try:
    from lightgbm import LGBMClassifier
except Exception:  # pragma: no cover
    LGBMClassifier = None


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
SAMPLES_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_training_samples.csv"

MODEL_TAG: str = "selector_v1"
MODEL_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_selector_{MODEL_TAG}.joblib"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_selector_summary_{MODEL_TAG}.json"
FEATURE_IMPORTANCE_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_selector_feature_importance_{MODEL_TAG}.csv"
PREDICTIONS_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_selector_predictions_{MODEL_TAG}.csv"
BUCKET_ANALYSIS_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_selector_bucket_analysis_{MODEL_TAG}.csv"

TARGET_COLUMN: str = "label_is_selected"
GROUP_COLUMN: str = "candidate_date"
VALID_START_DATE: str = "2023-01-01"
TEST_START_DATE: str = "2024-01-01"

CATEGORICAL_COLUMNS: list[str] = [
    "product_symbol",
    "exchange",
    "direction",
    "signal",
    "risk_mode",
    "entry_context",
]

NUMERIC_COLUMNS: list[str] = [
    "risk_ratio",
    "risk_multiplier",
    "loss_streak",
    "active_positions_before",
    "max_concurrent_positions",
    "remaining_position_slots",
    "contracts_by_risk",
    "contracts_by_margin",
    "contracts_by_single_trade_cap",
    "feature_stop_distance_pct",
    "feature_target_risk_to_equity",
    "feature_margin_per_contract_to_equity",
    "feature_allowed_capital_to_equity",
    "feature_single_trade_capital_limit_to_equity",
    "feature_ret_signed_5d",
    "feature_trend_ma5_gap_pct",
    "feature_trend_ma10_gap_pct",
    "feature_trend_ma20_gap_pct",
    "feature_ma5_ma10_gap_pct",
    "feature_ma10_ma20_gap_pct",
    "feature_ma20_ma40_gap_pct",
    "feature_ma_alignment_long",
    "feature_ma_alignment_short",
    "feature_close_vs_prev20_high_pct",
    "feature_close_vs_prev20_low_pct",
    "feature_atr14_pct",
    "feature_range_pct",
    "feature_atr14_pct_zscore_120",
    "feature_range_pct_zscore_120",
    "feature_ret_20d_zscore_120",
    "feature_upper_wick_pct",
    "feature_lower_wick_pct",
    "feature_vol20",
    "feature_vol60",
    "feature_volume_zscore_20",
    "feature_volume_ratio_1d_20d",
    "feature_volume_ratio_1d_20d_zscore_120",
    "feature_oi_delta_1d_pct",
    "feature_oi_delta_5d_pct",
    "feature_oi_delta_1d_pct_zscore_120",
    "feature_oi_ratio_2v2",
    "feature_volume_ratio_2v2",
    "feature_volume_oi_surge_flag",
    "feature_close_position_20d",
    "feature_close_position_60d",
    "feature_signal_strength_signed",
    "feature_reversal_pressure_signed",
    "feature_mid_term_momentum_signed",
]

EXCLUDED_COLUMNS: set[str] = {
    "sample_id",
    "candidate_index",
    "candidate_datetime",
    "candidate_date",
    "product_vt_symbol",
    "contract_vt_symbol",
    "contract_symbol",
    "feature_source",
    "candidate_status",
    "skip_reason",
    "selection_stage",
    "entry_trade_id",
    "selected_contract_vt_symbol",
    "selected_entry_price",
    "selected_entry_volume",
    "entry_volume",
    "label_selection_status",
    "label_rejection_reason",
    "label_rejection_stage",
    "label_has_trade_link",
    "label_candidate_quality_bucket_v2",
    "label_entry_trade_id",
    "label_exit_date",
}


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
    df["candidate_date"] = pd.to_datetime(df["candidate_date"])
    df.sort_values(["candidate_date", "sample_id"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def build_feature_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    categorical_columns = [column for column in CATEGORICAL_COLUMNS if column in df.columns]
    numeric_columns = [column for column in NUMERIC_COLUMNS if column in df.columns]
    feature_columns = categorical_columns + numeric_columns
    feature_columns = [column for column in feature_columns if column not in EXCLUDED_COLUMNS]
    return feature_columns, categorical_columns


def build_split(df: pd.DataFrame) -> pd.DataFrame:
    valid_start = pd.Timestamp(VALID_START_DATE)
    test_start = pd.Timestamp(TEST_START_DATE)

    split_series = pd.Series("train", index=df.index, dtype="object")
    split_series.loc[df["candidate_date"] >= valid_start] = "valid"
    split_series.loc[df["candidate_date"] >= test_start] = "test"
    result = df.copy()
    result["dataset_split"] = split_series
    return result


def prepare_lightgbm_frames(
    df: pd.DataFrame,
    feature_columns: list[str],
    categorical_columns: list[str],
) -> pd.DataFrame:
    prepared = df[feature_columns].copy()
    for column in categorical_columns:
        prepared[column] = prepared[column].fillna("__missing__").astype("category")
    for column in feature_columns:
        if column not in categorical_columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce").fillna(0.0)
    return prepared


def train_model(
    train_df: pd.DataFrame,
    valid_df: pd.DataFrame,
    feature_columns: list[str],
    categorical_columns: list[str],
) -> tuple[Any, dict[str, Any]]:
    if LGBMClassifier is None:
        raise RuntimeError("lightgbm is not available in the current environment")

    x_train = prepare_lightgbm_frames(train_df, feature_columns, categorical_columns)
    y_train = train_df[TARGET_COLUMN].astype("int64")
    x_valid = prepare_lightgbm_frames(valid_df, feature_columns, categorical_columns)
    y_valid = valid_df[TARGET_COLUMN].astype("int64")

    model = LGBMClassifier(
        objective="binary",
        n_estimators=220,
        learning_rate=0.04,
        num_leaves=15,
        max_depth=4,
        subsample=0.8,
        colsample_bytree=0.7,
        min_child_samples=30,
        reg_alpha=1.0,
        reg_lambda=5.0,
        random_state=42,
        verbosity=-1,
    )

    fit_kwargs: dict[str, Any] = {
        "X": x_train,
        "y": y_train,
        "categorical_feature": categorical_columns,
    }
    if not valid_df.empty:
        fit_kwargs["eval_set"] = [(x_valid, y_valid)]
        fit_kwargs["eval_metric"] = "binary_logloss"
        fit_kwargs["callbacks"] = []

    model.fit(**fit_kwargs)
    metadata = {
        "model_type": "lightgbm_classifier",
        "feature_columns": feature_columns,
        "categorical_columns": categorical_columns,
        "target_column": TARGET_COLUMN,
        "train_rows": int(len(train_df)),
        "valid_rows": int(len(valid_df)),
    }
    return model, metadata


def score_dataframe(
    model: Any,
    df: pd.DataFrame,
    feature_columns: list[str],
    categorical_columns: list[str],
) -> np.ndarray:
    x = prepare_lightgbm_frames(df, feature_columns, categorical_columns)
    probabilities = model.predict_proba(x)[:, 1]
    return np.asarray(probabilities, dtype="float64")


def compute_metrics(df: pd.DataFrame, probability_column: str) -> dict[str, Any]:
    actual = df[TARGET_COLUMN].astype("int64")
    probability = df[probability_column].astype("float64").clip(1e-6, 1 - 1e-6)
    predicted = (probability >= 0.5).astype("int64")

    try:
        auc = roc_auc_score(actual, probability) if actual.nunique() >= 2 else float("nan")
    except ValueError:
        auc = float("nan")

    return {
        "rows": int(len(df)),
        "positive_rate": _safe_float(actual.mean()),
        "predicted_positive_rate": _safe_float(predicted.mean()),
        "log_loss": _safe_float(log_loss(actual, probability, labels=[0, 1])),
        "roc_auc": _safe_float(auc),
        "accuracy": _safe_float(accuracy_score(actual, predicted)),
        "precision": _safe_float(precision_score(actual, predicted, zero_division=0)),
        "recall": _safe_float(recall_score(actual, predicted, zero_division=0)),
        "f1": _safe_float(f1_score(actual, predicted, zero_division=0)),
    }


def compute_cross_section_metrics(df: pd.DataFrame, probability_column: str) -> dict[str, Any]:
    eligible_df = df.groupby(GROUP_COLUMN).filter(lambda group: len(group) >= 2).copy()
    if eligible_df.empty:
        return {
            "group_count": 0,
            "rows": 0,
            "top1_hit_rate": 0.0,
            "top1_selected_rate": 0.0,
            "group_selected_rate": 0.0,
            "top1_selected_lift": 0.0,
            "top1_avg_candidate_quality": 0.0,
            "group_avg_candidate_quality": 0.0,
            "top1_quality_lift": 0.0,
        }

    top1_hits = 0
    top1_selected_values: list[float] = []
    group_selected_values: list[float] = []
    top1_quality_values: list[float] = []
    group_quality_values: list[float] = []
    group_count = 0

    for _, group_df in eligible_df.groupby(GROUP_COLUMN, sort=False):
        predicted_top_index = group_df[probability_column].astype("float64").idxmax()
        actual_top_index = group_df["label_candidate_quality_score_v2"].astype("float64").idxmax()
        top1_hits += int(predicted_top_index == actual_top_index)

        top1_selected = float(group_df.loc[predicted_top_index, TARGET_COLUMN])
        group_selected = float(group_df[TARGET_COLUMN].mean())
        top1_quality = float(group_df.loc[predicted_top_index, "label_candidate_quality_score_v2"])
        group_quality = float(group_df["label_candidate_quality_score_v2"].mean())

        top1_selected_values.append(top1_selected)
        group_selected_values.append(group_selected)
        top1_quality_values.append(top1_quality)
        group_quality_values.append(group_quality)
        group_count += 1

    top1_selected_rate = float(np.mean(top1_selected_values)) if top1_selected_values else 0.0
    group_selected_rate = float(np.mean(group_selected_values)) if group_selected_values else 0.0
    top1_quality = float(np.mean(top1_quality_values)) if top1_quality_values else 0.0
    group_quality = float(np.mean(group_quality_values)) if group_quality_values else 0.0
    return {
        "group_count": int(group_count),
        "rows": int(len(eligible_df)),
        "top1_hit_rate": float(top1_hits / group_count) if group_count else 0.0,
        "top1_selected_rate": top1_selected_rate,
        "group_selected_rate": group_selected_rate,
        "top1_selected_lift": float(top1_selected_rate - group_selected_rate),
        "top1_avg_candidate_quality": top1_quality,
        "group_avg_candidate_quality": group_quality,
        "top1_quality_lift": float(top1_quality - group_quality),
    }


def build_bucket_analysis(df: pd.DataFrame, probability_column: str) -> pd.DataFrame:
    test_df = df[df["dataset_split"] == "test"].copy()
    if test_df.empty:
        return pd.DataFrame()

    test_df["predicted_bucket"] = pd.qcut(
        test_df[probability_column].rank(method="first"),
        q=3,
        labels=["low_score", "mid_score", "high_score"],
    )

    summary = (
        test_df.groupby("predicted_bucket", observed=False)
        .agg(
            sample_count=("sample_id", "count"),
            avg_predicted_prob=(probability_column, "mean"),
            selected_rate=(TARGET_COLUMN, "mean"),
            avg_candidate_quality=("label_candidate_quality_score_v2", "mean"),
            avg_candidate_forward_10d_r=("label_candidate_forward_10d_r_multiple", "mean"),
            avg_candidate_forward_20d_r=("label_candidate_forward_20d_r_multiple", "mean"),
            avg_candidate_20d_mfe_r=("label_candidate_20d_mfe_r", "mean"),
            avg_candidate_20d_mae_r=("label_candidate_20d_mae_r", "mean"),
            avg_realized_r=("label_realized_r_multiple", "mean"),
        )
        .reset_index()
    )
    summary["selected_rate"] = summary["selected_rate"] * 100.0
    return summary


def build_feature_importance(model: Any, feature_columns: list[str]) -> pd.DataFrame:
    booster = model.booster_
    importance_df = pd.DataFrame(
        {
            "feature": feature_columns,
            "importance_gain": booster.feature_importance(importance_type="gain"),
            "importance_split": booster.feature_importance(importance_type="split"),
        }
    )
    importance_df.sort_values(["importance_gain", "importance_split"], ascending=[False, False], inplace=True)
    importance_df.reset_index(drop=True, inplace=True)
    return importance_df


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_samples()
    df = build_split(df)
    feature_columns, categorical_columns = build_feature_columns(df)

    train_df = df[df["dataset_split"] == "train"].copy()
    valid_df = df[df["dataset_split"] == "valid"].copy()
    test_df = df[df["dataset_split"] == "test"].copy()

    model, metadata = train_model(train_df, valid_df, feature_columns, categorical_columns)

    scored_df = df.copy()
    scored_df["predicted_select_probability"] = score_dataframe(model, scored_df, feature_columns, categorical_columns)

    split_metrics = {
        "train": compute_metrics(scored_df[scored_df["dataset_split"] == "train"], "predicted_select_probability"),
        "valid": compute_metrics(scored_df[scored_df["dataset_split"] == "valid"], "predicted_select_probability"),
        "test": compute_metrics(scored_df[scored_df["dataset_split"] == "test"], "predicted_select_probability"),
    }
    cross_section_metrics = {
        "train": compute_cross_section_metrics(scored_df[scored_df["dataset_split"] == "train"], "predicted_select_probability"),
        "valid": compute_cross_section_metrics(scored_df[scored_df["dataset_split"] == "valid"], "predicted_select_probability"),
        "test": compute_cross_section_metrics(scored_df[scored_df["dataset_split"] == "test"], "predicted_select_probability"),
    }

    bucket_df = build_bucket_analysis(scored_df, "predicted_select_probability")
    importance_df = build_feature_importance(model, feature_columns)

    summary = {
        "model_metadata": metadata,
        "model_tag": MODEL_TAG,
        "split_dates": {
            "valid_start_date": VALID_START_DATE,
            "test_start_date": TEST_START_DATE,
        },
        "dataset_rows": int(len(df)),
        "split_metrics": split_metrics,
        "cross_section_metrics": cross_section_metrics,
        "top_features": importance_df.head(20).to_dict(orient="records"),
        "bucket_recommendation": {
            "low_score": "low_select_probability",
            "mid_score": "medium_select_probability",
            "high_score": "high_select_probability",
        },
    }

    joblib.dump(model, MODEL_OUTPUT_PATH)
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    importance_df.to_csv(FEATURE_IMPORTANCE_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    prediction_columns = [
        "sample_id",
        "candidate_date",
        "product_symbol",
        "direction",
        "signal",
        "risk_mode",
        "dataset_split",
        TARGET_COLUMN,
        "label_rejection_reason",
        "label_candidate_quality_score_v2",
        "label_candidate_quality_score_v2_rank_centered_1d",
        "predicted_select_probability",
    ]
    prediction_columns = [column for column in prediction_columns if column in scored_df.columns]
    scored_df[prediction_columns].to_csv(PREDICTIONS_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    if not bucket_df.empty:
        bucket_df.to_csv(BUCKET_ANALYSIS_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print(f"[ai-candidate-selector] model: {MODEL_OUTPUT_PATH}")
    print(f"[ai-candidate-selector] summary: {SUMMARY_OUTPUT_PATH}")
    print(f"[ai-candidate-selector] feature importance: {FEATURE_IMPORTANCE_OUTPUT_PATH}")
    print(f"[ai-candidate-selector] predictions: {PREDICTIONS_OUTPUT_PATH}")
    print(f"[ai-candidate-selector] bucket analysis: {BUCKET_ANALYSIS_OUTPUT_PATH}")
    print(json.dumps(split_metrics, ensure_ascii=False, indent=2))
    print(json.dumps(cross_section_metrics, ensure_ascii=False, indent=2))
    if not bucket_df.empty:
        print(bucket_df.to_string(index=False))


if __name__ == "__main__":
    main()
