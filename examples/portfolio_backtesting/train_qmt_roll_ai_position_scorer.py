from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

try:
    from lightgbm import LGBMRegressor
except Exception:  # pragma: no cover
    LGBMRegressor = None


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
SAMPLES_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_position_training_samples.csv"

MODEL_TAG: str = "v3"
MODEL_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_position_scorer_{MODEL_TAG}.joblib"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_position_scorer_summary_{MODEL_TAG}.json"
FEATURE_IMPORTANCE_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_position_scorer_feature_importance_{MODEL_TAG}.csv"
PREDICTIONS_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_position_scorer_predictions_{MODEL_TAG}.csv"
BUCKET_ANALYSIS_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_position_scorer_bucket_analysis_{MODEL_TAG}.csv"

TARGET_COLUMN: str = "label_quality_score_v2_rank_centered_1d"
VALID_START_DATE: str = "2023-01-01"
TEST_START_DATE: str = "2024-01-01"
GROUP_COLUMN: str = "entry_date"
CROSS_SECTIONAL_FLAG_COLUMN: str = "label_quality_score_v3_is_cross_sectional"

CATEGORICAL_COLUMNS: list[str] = [
    "product_symbol",
    "exchange",
    "direction",
    "signal",
    "risk_mode",
    "layer_kind",
    "sizing_method",
]

CONTEXT_NUMERIC_COLUMNS: list[str] = [
    "entry_volume",
    "contract_size",
    "risk_ratio",
    "risk_multiplier",
    "loss_streak",
]

V3_CONTEXT_NUMERIC_COLUMNS: list[str] = [
    "risk_ratio",
    "risk_multiplier",
    "loss_streak",
    "feature_cross_section_count_1d",
    "feature_stop_distance_pct",
    "feature_actual_risk_to_equity",
    "feature_actual_margin_to_equity",
    "feature_allowed_capital_to_equity",
    "feature_single_trade_capital_limit_to_equity",
]

EXCLUDED_FEATURE_COLUMNS: set[str] = {
    "feature_signal",
    "feature_risk_mode",
    "feature_direction",
    "feature_close",
    "feature_open_oi",
    "feature_close_oi",
    "feature_entry_notional",
}

EXCLUDED_COLUMNS: set[str] = {
    "sample_id",
    "entry_trade_id",
    "entry_datetime",
    "entry_date",
    "product_vt_symbol",
    "contract_vt_symbol",
    "contract_symbol",
    "feature_source",
    "feature_signal",
    "feature_risk_mode",
    "feature_direction",
    "label_size_bucket",
    "label_size_bucket_v2",
    "label_quality_score_v3_bucket",
    "label_entry_trade_id",
    "label_exit_date",
}


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_samples() -> pd.DataFrame:
    df = pd.read_csv(SAMPLES_PATH)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df.sort_values(["entry_date", "entry_trade_id"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def build_feature_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    categorical_columns = [column for column in CATEGORICAL_COLUMNS if column in df.columns]
    if MODEL_TAG == "v3":
        cross_section_rank_columns = [
            column for column in df.columns if column.startswith("feature_") and column.endswith("_cs_rank_centered_1d")
        ]
        numeric_columns = [column for column in V3_CONTEXT_NUMERIC_COLUMNS if column in df.columns]
        numeric_columns.extend(cross_section_rank_columns)
        numeric_columns = list(dict.fromkeys(numeric_columns))
    else:
        feature_numeric_columns = [column for column in df.columns if column.startswith("feature_")]
        feature_numeric_columns = [column for column in feature_numeric_columns if column not in EXCLUDED_FEATURE_COLUMNS]
        numeric_columns = [column for column in CONTEXT_NUMERIC_COLUMNS if column in df.columns]
        numeric_columns.extend(feature_numeric_columns)
        numeric_columns = list(dict.fromkeys(numeric_columns))

    feature_columns = categorical_columns + numeric_columns
    feature_columns = [column for column in feature_columns if column not in EXCLUDED_COLUMNS]
    return feature_columns, categorical_columns


def build_split(df: pd.DataFrame) -> pd.DataFrame:
    valid_start = pd.Timestamp(VALID_START_DATE)
    test_start = pd.Timestamp(TEST_START_DATE)

    split_series = pd.Series("train", index=df.index, dtype="object")
    split_series.loc[df["entry_date"] >= valid_start] = "valid"
    split_series.loc[df["entry_date"] >= test_start] = "test"
    df = df.copy()
    df["dataset_split"] = split_series
    return df


def prepare_lightgbm_frames(
    df: pd.DataFrame,
    feature_columns: list[str],
    categorical_columns: list[str],
) -> pd.DataFrame:
    prepared = df[feature_columns].copy()
    for column in categorical_columns:
        prepared[column] = prepared[column].astype("category")
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
    if LGBMRegressor is None:
        raise RuntimeError("lightgbm is not available in the current environment")

    x_train = prepare_lightgbm_frames(train_df, feature_columns, categorical_columns)
    y_train = train_df[TARGET_COLUMN].astype("float64")
    x_valid = prepare_lightgbm_frames(valid_df, feature_columns, categorical_columns)
    y_valid = valid_df[TARGET_COLUMN].astype("float64")

    model = LGBMRegressor(
        objective="regression",
        n_estimators=240,
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
        fit_kwargs["eval_metric"] = "l2"
        fit_kwargs["callbacks"] = []

    model.fit(**fit_kwargs)
    metadata = {
        "model_type": "lightgbm_regressor",
        "feature_columns": feature_columns,
        "categorical_columns": categorical_columns,
        "target_column": TARGET_COLUMN,
        "train_rows": len(train_df),
        "valid_rows": len(valid_df),
    }
    return model, metadata


def score_dataframe(
    model: Any,
    df: pd.DataFrame,
    feature_columns: list[str],
    categorical_columns: list[str],
) -> np.ndarray:
    x = prepare_lightgbm_frames(df, feature_columns, categorical_columns)
    return np.asarray(model.predict(x), dtype="float64")


def compute_metrics(df: pd.DataFrame, prediction_column: str) -> dict[str, Any]:
    actual = df[TARGET_COLUMN].astype("float64")
    predicted = df[prediction_column].astype("float64")
    rmse = mean_squared_error(actual, predicted) ** 0.5
    mae = mean_absolute_error(actual, predicted)
    r2 = r2_score(actual, predicted)
    spearman = actual.corr(predicted, method="spearman")
    pearson = actual.corr(predicted, method="pearson")
    return {
        "rows": int(len(df)),
        "rmse": _safe_float(rmse),
        "mae": _safe_float(mae),
        "r2": _safe_float(r2),
        "spearman_corr": _safe_float(spearman),
        "pearson_corr": _safe_float(pearson),
        "actual_mean": _safe_float(actual.mean()),
        "predicted_mean": _safe_float(predicted.mean()),
    }


def compute_cross_section_metrics(df: pd.DataFrame, prediction_column: str) -> dict[str, Any]:
    eligible_df = df.groupby(GROUP_COLUMN).filter(lambda group: len(group) >= 2).copy()
    if eligible_df.empty:
        return {
            "group_count": 0,
            "rows": 0,
            "mean_group_spearman": 0.0,
            "top1_hit_rate": 0.0,
            "top1_avg_target": 0.0,
            "group_avg_target": 0.0,
            "top1_target_lift": 0.0,
        }

    spearman_values: list[float] = []
    top1_hits = 0
    top1_targets: list[float] = []
    group_avg_targets: list[float] = []
    group_count = 0

    for _, group_df in eligible_df.groupby(GROUP_COLUMN, sort=False):
        actual = group_df[TARGET_COLUMN].astype("float64")
        predicted = group_df[prediction_column].astype("float64")
        spearman = actual.corr(predicted, method="spearman")
        if pd.notna(spearman):
            spearman_values.append(float(spearman))

        predicted_top_index = predicted.idxmax()
        actual_top_index = actual.idxmax()
        top1_hits += int(predicted_top_index == actual_top_index)
        top1_targets.append(float(actual.loc[predicted_top_index]))
        group_avg_targets.append(float(actual.mean()))
        group_count += 1

    mean_group_spearman = float(np.mean(spearman_values)) if spearman_values else 0.0
    top1_avg_target = float(np.mean(top1_targets)) if top1_targets else 0.0
    group_avg_target = float(np.mean(group_avg_targets)) if group_avg_targets else 0.0
    return {
        "group_count": int(group_count),
        "rows": int(len(eligible_df)),
        "mean_group_spearman": mean_group_spearman,
        "top1_hit_rate": float(top1_hits / group_count) if group_count else 0.0,
        "top1_avg_target": top1_avg_target,
        "group_avg_target": group_avg_target,
        "top1_target_lift": float(top1_avg_target - group_avg_target),
    }


def build_bucket_analysis(df: pd.DataFrame, prediction_column: str) -> pd.DataFrame:
    test_df = df[(df["dataset_split"] == "test") & (df[CROSS_SECTIONAL_FLAG_COLUMN] > 0)].copy()
    if test_df.empty:
        return pd.DataFrame()

    test_df["predicted_bucket"] = pd.qcut(
        test_df[prediction_column].rank(method="first"),
        q=3,
        labels=["low_score", "mid_score", "high_score"],
    )
    test_df["realized_win_flag"] = (test_df["label_realized_pnl_amount"] > 0).astype(float)

    summary = (
        test_df.groupby("predicted_bucket", observed=False)
        .agg(
            sample_count=("sample_id", "count"),
            avg_predicted_score=(prediction_column, "mean"),
            avg_target_score=(TARGET_COLUMN, "mean"),
            avg_quality_score_v2=("label_quality_score_v2", "mean"),
            avg_quality_score_v1=("label_quality_score", "mean"),
            avg_realized_r=("label_realized_r_multiple", "mean"),
            avg_realized_return_pct=("label_realized_return_pct", "mean"),
            avg_forward_10d_return_pct=("label_forward_10d_return_pct", "mean"),
            avg_forward_20d_return_pct=("label_forward_20d_return_pct", "mean"),
            avg_20d_mfe_r=("label_20d_mfe_r", "mean"),
            avg_20d_mae_r=("label_20d_mae_r", "mean"),
            win_rate=("realized_win_flag", "mean"),
        )
        .reset_index()
    )
    summary["win_rate"] = summary["win_rate"] * 100.0
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
    eligible_df = df[df[CROSS_SECTIONAL_FLAG_COLUMN] > 0].copy()
    feature_columns, categorical_columns = build_feature_columns(df)

    train_df = eligible_df[eligible_df["dataset_split"] == "train"].copy()
    valid_df = eligible_df[eligible_df["dataset_split"] == "valid"].copy()
    test_df = eligible_df[eligible_df["dataset_split"] == "test"].copy()

    model, metadata = train_model(train_df, valid_df, feature_columns, categorical_columns)

    scored_df = df.copy()
    scored_df["predicted_quality_score"] = score_dataframe(model, scored_df, feature_columns, categorical_columns)
    scored_eligible_df = scored_df[scored_df[CROSS_SECTIONAL_FLAG_COLUMN] > 0].copy()

    split_metrics = {
        "train": compute_metrics(scored_eligible_df[scored_eligible_df["dataset_split"] == "train"], "predicted_quality_score"),
        "valid": compute_metrics(scored_eligible_df[scored_eligible_df["dataset_split"] == "valid"], "predicted_quality_score"),
        "test": compute_metrics(scored_eligible_df[scored_eligible_df["dataset_split"] == "test"], "predicted_quality_score"),
    }
    cross_section_metrics = {
        "train": compute_cross_section_metrics(scored_eligible_df[scored_eligible_df["dataset_split"] == "train"], "predicted_quality_score"),
        "valid": compute_cross_section_metrics(scored_eligible_df[scored_eligible_df["dataset_split"] == "valid"], "predicted_quality_score"),
        "test": compute_cross_section_metrics(scored_eligible_df[scored_eligible_df["dataset_split"] == "test"], "predicted_quality_score"),
    }

    bucket_df = build_bucket_analysis(scored_df, "predicted_quality_score")
    importance_df = build_feature_importance(model, feature_columns)

    summary = {
        "model_metadata": metadata,
        "model_tag": MODEL_TAG,
        "split_dates": {
            "valid_start_date": VALID_START_DATE,
            "test_start_date": TEST_START_DATE,
        },
        "dataset_rows": int(len(df)),
        "cross_sectional_rows": int(len(eligible_df)),
        "split_metrics": split_metrics,
        "cross_section_metrics": cross_section_metrics,
        "top_features": importance_df.head(20).to_dict(orient="records"),
        "bucket_recommendation": {
            "low_score": "0.7x",
            "mid_score": "1.0x",
            "high_score": "1.2x",
        },
    }

    joblib.dump(
        {
            "model": model,
            "feature_columns": feature_columns,
            "categorical_columns": categorical_columns,
            "target_column": TARGET_COLUMN,
            "split_dates": {"valid_start_date": VALID_START_DATE, "test_start_date": TEST_START_DATE},
        },
        MODEL_OUTPUT_PATH,
    )

    summary_path = SUMMARY_OUTPUT_PATH
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    importance_df.to_csv(FEATURE_IMPORTANCE_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    prediction_columns = [
        "sample_id",
        "entry_date",
        "product_symbol",
        "direction",
        "signal",
        "risk_mode",
        "dataset_split",
        CROSS_SECTIONAL_FLAG_COLUMN,
        TARGET_COLUMN,
        "label_quality_score_v2",
        "label_realized_r_multiple",
        "label_forward_10d_return_pct",
        "label_forward_20d_return_pct",
        "predicted_quality_score",
    ]
    scored_df[prediction_columns].to_csv(PREDICTIONS_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    bucket_df.to_csv(BUCKET_ANALYSIS_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print(f"[ai-train] model: {MODEL_OUTPUT_PATH}")
    print(f"[ai-train] summary: {SUMMARY_OUTPUT_PATH}")
    print(f"[ai-train] feature importance: {FEATURE_IMPORTANCE_OUTPUT_PATH}")
    print(f"[ai-train] predictions: {PREDICTIONS_OUTPUT_PATH}")
    print(f"[ai-train] bucket analysis: {BUCKET_ANALYSIS_OUTPUT_PATH}")
    print(json.dumps(split_metrics, ensure_ascii=False, indent=2))
    print(json.dumps(cross_section_metrics, ensure_ascii=False, indent=2))
    if not bucket_df.empty:
        print(bucket_df.to_string(index=False))


if __name__ == "__main__":
    main()
