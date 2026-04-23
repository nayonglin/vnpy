from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

try:
    from lightgbm import LGBMRanker
except Exception:  # pragma: no cover
    LGBMRanker = None


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
SAMPLES_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_training_samples.csv"

MODEL_TAG: str = "pairwise_v1"
MODEL_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_pairwise_ranker_{MODEL_TAG}.joblib"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_pairwise_ranker_summary_{MODEL_TAG}.json"
FEATURE_IMPORTANCE_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_pairwise_ranker_feature_importance_{MODEL_TAG}.csv"
PREDICTIONS_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_pairwise_ranker_predictions_{MODEL_TAG}.csv"
BUCKET_ANALYSIS_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_pairwise_ranker_bucket_analysis_{MODEL_TAG}.csv"

TARGET_COLUMN: str = "label_candidate_quality_score_v2_rank_centered_1d"
QUALITY_COLUMN: str = "label_candidate_quality_score_v2"
SELECTED_COLUMN: str = "label_is_selected"
GROUP_COLUMN: str = "candidate_date"
RELEVANCE_COLUMN: str = "label_candidate_pairwise_relevance_1d"
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
    "active_positions_before",
    "max_concurrent_positions",
    "remaining_position_slots",
    "contracts_by_risk",
    "contracts_by_margin",
    "contracts_by_single_trade_cap",
    "label_selection_status",
    "label_rejection_reason",
    "label_rejection_stage",
    "label_has_trade_link",
    "label_candidate_quality_bucket_v2",
    "label_entry_trade_id",
    "label_exit_date",
    "label_is_selected_rank_pct_1d",
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


def filter_cross_sectional_rows(df: pd.DataFrame) -> pd.DataFrame:
    counts = df.groupby(GROUP_COLUMN)["sample_id"].transform("count")
    return df.loc[counts >= 2].copy()


def add_pairwise_relevance_labels(df: pd.DataFrame) -> pd.DataFrame:
    ranked_df = df.copy()
    descending_rank = ranked_df.groupby(GROUP_COLUMN)[QUALITY_COLUMN].rank(method="dense", ascending=False).astype("int64")
    group_size = ranked_df.groupby(GROUP_COLUMN)["sample_id"].transform("count").astype("int64")
    relevance = (group_size - descending_rank).clip(lower=0).astype("int64")
    ranked_df[RELEVANCE_COLUMN] = relevance
    return ranked_df


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
    split_series.loc[df[GROUP_COLUMN] >= valid_start] = "valid"
    split_series.loc[df[GROUP_COLUMN] >= test_start] = "test"
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


def build_group_sizes(df: pd.DataFrame) -> list[int]:
    if df.empty:
        return []
    group_sizes = df.groupby(GROUP_COLUMN, sort=False).size().astype(int).tolist()
    return group_sizes


def train_model(
    train_df: pd.DataFrame,
    valid_df: pd.DataFrame,
    feature_columns: list[str],
    categorical_columns: list[str],
) -> tuple[Any, dict[str, Any]]:
    if LGBMRanker is None:
        raise RuntimeError("lightgbm ranker is not available in the current environment")

    x_train = prepare_lightgbm_frames(train_df, feature_columns, categorical_columns)
    y_train = train_df[RELEVANCE_COLUMN].astype("int64")
    train_group = build_group_sizes(train_df)

    x_valid = prepare_lightgbm_frames(valid_df, feature_columns, categorical_columns)
    y_valid = valid_df[RELEVANCE_COLUMN].astype("int64")
    valid_group = build_group_sizes(valid_df)

    model = LGBMRanker(
        objective="lambdarank",
        metric="ndcg",
        n_estimators=220,
        learning_rate=0.04,
        num_leaves=15,
        max_depth=4,
        subsample=0.8,
        colsample_bytree=0.7,
        min_child_samples=24,
        reg_alpha=1.0,
        reg_lambda=5.0,
        random_state=42,
        verbosity=-1,
    )

    fit_kwargs: dict[str, Any] = {
        "X": x_train,
        "y": y_train,
        "group": train_group,
        "categorical_feature": categorical_columns,
    }
    if not valid_df.empty:
        fit_kwargs["eval_set"] = [(x_valid, y_valid)]
        fit_kwargs["eval_group"] = [valid_group]
        fit_kwargs["eval_metric"] = "ndcg"
        fit_kwargs["eval_at"] = [1, 3]
        fit_kwargs["callbacks"] = []

    model.fit(**fit_kwargs)
    metadata = {
        "model_type": "lightgbm_ranker",
        "feature_columns": feature_columns,
        "categorical_columns": categorical_columns,
        "target_column": TARGET_COLUMN,
        "relevance_column": RELEVANCE_COLUMN,
        "train_rows": int(len(train_df)),
        "valid_rows": int(len(valid_df)),
        "train_groups": int(len(train_group)),
        "valid_groups": int(len(valid_group)),
    }
    return model, metadata


def score_dataframe(
    model: Any,
    df: pd.DataFrame,
    feature_columns: list[str],
    categorical_columns: list[str],
) -> np.ndarray:
    x = prepare_lightgbm_frames(df, feature_columns, categorical_columns)
    predictions = model.predict(x)
    return np.asarray(predictions, dtype="float64")


def compute_metrics(df: pd.DataFrame, prediction_column: str) -> dict[str, Any]:
    actual = df[TARGET_COLUMN].astype("float64")
    predicted = df[prediction_column].astype("float64")
    rmse = mean_squared_error(actual, predicted) ** 0.5
    mae = mean_absolute_error(actual, predicted)
    try:
        r2 = r2_score(actual, predicted) if len(df) >= 2 else float("nan")
    except ValueError:
        r2 = float("nan")
    spearman = actual.corr(predicted, method="spearman")
    return {
        "rows": int(len(df)),
        "rmse": _safe_float(rmse),
        "mae": _safe_float(mae),
        "r2": _safe_float(r2),
        "spearman": _safe_float(spearman if pd.notna(spearman) else 0.0),
    }


def compute_cross_section_metrics(df: pd.DataFrame, prediction_column: str) -> dict[str, Any]:
    if df.empty:
        return {
            "group_count": 0,
            "rows": 0,
            "mean_group_spearman": 0.0,
            "top1_hit_rate": 0.0,
            "top1_avg_target": 0.0,
            "group_avg_target": 0.0,
            "top1_target_lift": 0.0,
            "top1_avg_candidate_quality": 0.0,
            "group_avg_candidate_quality": 0.0,
            "top1_quality_lift": 0.0,
            "top1_selected_rate": 0.0,
            "group_selected_rate": 0.0,
            "top1_selected_lift": 0.0,
            "ndcg_at_1": 0.0,
            "ndcg_at_3": 0.0,
        }

    spearman_values: list[float] = []
    top1_hits = 0
    top1_targets: list[float] = []
    group_avg_targets: list[float] = []
    top1_quality_values: list[float] = []
    group_quality_values: list[float] = []
    top1_selected_values: list[float] = []
    group_selected_values: list[float] = []
    ndcg_at_1_values: list[float] = []
    ndcg_at_3_values: list[float] = []
    group_count = 0

    for _, group_df in df.groupby(GROUP_COLUMN, sort=False):
        actual_target = group_df[TARGET_COLUMN].astype("float64")
        actual_quality = group_df[QUALITY_COLUMN].astype("float64")
        predicted = group_df[prediction_column].astype("float64")

        spearman = float("nan")
        if actual_target.nunique() > 1 and predicted.nunique() > 1:
            spearman = actual_target.corr(predicted, method="spearman")
        if pd.notna(spearman):
            spearman_values.append(float(spearman))

        predicted_order = group_df.sort_values(prediction_column, ascending=False)
        actual_order = group_df.sort_values(QUALITY_COLUMN, ascending=False)
        predicted_top_index = predicted_order.index[0]
        actual_top_index = actual_order.index[0]
        top1_hits += int(predicted_top_index == actual_top_index)

        top1_targets.append(float(actual_target.loc[predicted_top_index]))
        group_avg_targets.append(float(actual_target.mean()))
        top1_quality_values.append(float(actual_quality.loc[predicted_top_index]))
        group_quality_values.append(float(actual_quality.mean()))
        top1_selected_values.append(float(group_df.loc[predicted_top_index, SELECTED_COLUMN]))
        group_selected_values.append(float(group_df[SELECTED_COLUMN].mean()))

        actual_relevance_pred_order = predicted_order[RELEVANCE_COLUMN].astype("float64").to_numpy()
        actual_relevance_best_order = actual_order[RELEVANCE_COLUMN].astype("float64").to_numpy()

        dcg_1 = actual_relevance_pred_order[0]
        ideal_dcg_1 = actual_relevance_best_order[0]
        ndcg_at_1_values.append(float(dcg_1 / ideal_dcg_1) if ideal_dcg_1 > 0 else 0.0)

        k = min(3, len(actual_relevance_pred_order))
        discounts = 1.0 / np.log2(np.arange(2, k + 2))
        dcg_3 = float(np.sum(actual_relevance_pred_order[:k] * discounts))
        ideal_dcg_3 = float(np.sum(actual_relevance_best_order[:k] * discounts))
        ndcg_at_3_values.append(float(dcg_3 / ideal_dcg_3) if ideal_dcg_3 > 0 else 0.0)
        group_count += 1

    mean_group_spearman = float(np.mean(spearman_values)) if spearman_values else 0.0
    top1_avg_target = float(np.mean(top1_targets)) if top1_targets else 0.0
    group_avg_target = float(np.mean(group_avg_targets)) if group_avg_targets else 0.0
    top1_avg_quality = float(np.mean(top1_quality_values)) if top1_quality_values else 0.0
    group_avg_quality = float(np.mean(group_quality_values)) if group_quality_values else 0.0
    top1_selected_rate = float(np.mean(top1_selected_values)) if top1_selected_values else 0.0
    group_selected_rate = float(np.mean(group_selected_values)) if group_selected_values else 0.0

    return {
        "group_count": int(group_count),
        "rows": int(len(df)),
        "mean_group_spearman": mean_group_spearman,
        "top1_hit_rate": float(top1_hits / group_count) if group_count else 0.0,
        "top1_avg_target": top1_avg_target,
        "group_avg_target": group_avg_target,
        "top1_target_lift": float(top1_avg_target - group_avg_target),
        "top1_avg_candidate_quality": top1_avg_quality,
        "group_avg_candidate_quality": group_avg_quality,
        "top1_quality_lift": float(top1_avg_quality - group_avg_quality),
        "top1_selected_rate": top1_selected_rate,
        "group_selected_rate": group_selected_rate,
        "top1_selected_lift": float(top1_selected_rate - group_selected_rate),
        "ndcg_at_1": float(np.mean(ndcg_at_1_values)) if ndcg_at_1_values else 0.0,
        "ndcg_at_3": float(np.mean(ndcg_at_3_values)) if ndcg_at_3_values else 0.0,
    }


def build_bucket_analysis(df: pd.DataFrame, prediction_column: str) -> pd.DataFrame:
    test_df = df[df["dataset_split"] == "test"].copy()
    if test_df.empty:
        return pd.DataFrame()

    test_df["predicted_bucket"] = pd.qcut(
        test_df[prediction_column].rank(method="first"),
        q=3,
        labels=["low_score", "mid_score", "high_score"],
    )

    summary = (
        test_df.groupby("predicted_bucket", observed=False)
        .agg(
            sample_count=("sample_id", "count"),
            avg_predicted_score=(prediction_column, "mean"),
            avg_target_score=(TARGET_COLUMN, "mean"),
            avg_candidate_quality=(QUALITY_COLUMN, "mean"),
            selected_rate=(SELECTED_COLUMN, "mean"),
            avg_relevance=(RELEVANCE_COLUMN, "mean"),
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
    df = filter_cross_sectional_rows(df)
    df = add_pairwise_relevance_labels(df)
    df = build_split(df)
    feature_columns, categorical_columns = build_feature_columns(df)

    train_df = df[df["dataset_split"] == "train"].copy()
    valid_df = df[df["dataset_split"] == "valid"].copy()
    test_df = df[df["dataset_split"] == "test"].copy()

    model, metadata = train_model(train_df, valid_df, feature_columns, categorical_columns)

    scored_df = df.copy()
    scored_df["predicted_rank_score"] = score_dataframe(model, scored_df, feature_columns, categorical_columns)

    split_metrics = {
        "train": compute_metrics(scored_df[scored_df["dataset_split"] == "train"], "predicted_rank_score"),
        "valid": compute_metrics(scored_df[scored_df["dataset_split"] == "valid"], "predicted_rank_score"),
        "test": compute_metrics(scored_df[scored_df["dataset_split"] == "test"], "predicted_rank_score"),
    }
    cross_section_metrics = {
        "train": compute_cross_section_metrics(scored_df[scored_df["dataset_split"] == "train"], "predicted_rank_score"),
        "valid": compute_cross_section_metrics(scored_df[scored_df["dataset_split"] == "valid"], "predicted_rank_score"),
        "test": compute_cross_section_metrics(scored_df[scored_df["dataset_split"] == "test"], "predicted_rank_score"),
    }

    bucket_df = build_bucket_analysis(scored_df, "predicted_rank_score")
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
            "low_score": "low_rank_score",
            "mid_score": "medium_rank_score",
            "high_score": "high_rank_score",
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
        QUALITY_COLUMN,
        RELEVANCE_COLUMN,
        SELECTED_COLUMN,
        "label_candidate_forward_10d_r_multiple",
        "label_candidate_forward_20d_r_multiple",
        "predicted_rank_score",
    ]
    prediction_columns = [column for column in prediction_columns if column in scored_df.columns]
    scored_df[prediction_columns].to_csv(PREDICTIONS_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    if not bucket_df.empty:
        bucket_df.to_csv(BUCKET_ANALYSIS_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print(f"[ai-candidate-pairwise-ranker] model: {MODEL_OUTPUT_PATH}")
    print(f"[ai-candidate-pairwise-ranker] summary: {SUMMARY_OUTPUT_PATH}")
    print(f"[ai-candidate-pairwise-ranker] feature importance: {FEATURE_IMPORTANCE_OUTPUT_PATH}")
    print(f"[ai-candidate-pairwise-ranker] predictions: {PREDICTIONS_OUTPUT_PATH}")
    print(f"[ai-candidate-pairwise-ranker] bucket analysis: {BUCKET_ANALYSIS_OUTPUT_PATH}")
    print(json.dumps(split_metrics, ensure_ascii=False, indent=2))
    print(json.dumps(cross_section_metrics, ensure_ascii=False, indent=2))
    if not bucket_df.empty:
        print(bucket_df.to_string(index=False))


if __name__ == "__main__":
    main()
