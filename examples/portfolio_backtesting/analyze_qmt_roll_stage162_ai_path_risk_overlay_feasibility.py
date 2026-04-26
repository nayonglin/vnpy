from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import build_qmt_roll_ai_candidate_training_samples as candidate_samples
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_VERSION
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage162_ai_path_risk_overlay_feasibility_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage162_ai_path_risk_overlay_feasibility"

STAGE78_CANDIDATE_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_official_stage78_defensive_formal_entry_candidate_snapshots_2020_2026_04.csv"
)
STAGE78_ENTRY_RISK_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_official_stage78_defensive_formal_entry_risk_diagnostics_2020_2026_04.csv"
)
STAGE78_TRADES_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_formal_trades_2020_2026_04.csv"

SAMPLES_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_samples_{MODEL_TAG}.csv"
PREDICTIONS_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_predictions_{MODEL_TAG}.csv"
BUCKET_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
SPLIT_METRICS_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_split_metrics_{MODEL_TAG}.csv"
COEFFICIENT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coefficients_{MODEL_TAG}.csv"
MODEL_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_model_{MODEL_TAG}.joblib"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

GROUP_COLUMN: str = "candidate_date"
TARGET_COLUMN: str = "label_path_bad_v1"
SCORE_COLUMN: str = "label_path_risk_score_v1"
PROBABILITY_COLUMN: str = "predicted_path_bad_probability"
TRAIN_END_EXCLUSIVE: str = "2023-01-01"
VALID_START: str = "2023-01-01"
TEST_START: str = "2024-01-01"
BAD_QUANTILE: float = 0.67

FEATURE_COLUMNS: tuple[str, ...] = (
    "active_positions_before",
    "remaining_position_slots",
    "loss_streak",
    "risk_ratio",
    "risk_multiplier",
    "feature_target_risk_to_equity",
    "feature_margin_per_contract_to_equity",
    "feature_allowed_capital_to_equity",
    "feature_single_trade_capital_limit_to_equity",
    "feature_ret_signed_5d",
    "feature_reversal_pressure_signed",
    "feature_mid_term_momentum_signed",
    "feature_trend_ma10_gap_pct",
    "feature_trend_ma20_gap_pct",
    "feature_ma5_ma10_gap_pct",
    "feature_ma10_ma20_gap_pct",
    "feature_ma20_ma40_gap_pct",
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
    "feature_close_position_20d",
    "feature_close_position_60d",
    "feature_candidate_cross_section_count_1d",
)


@dataclass(frozen=True)
class SplitSpec:
    name: str
    start: str | None
    end: str | None


SPLITS: tuple[SplitSpec, ...] = (
    SplitSpec("train", None, TRAIN_END_EXCLUSIVE),
    SplitSpec("valid", VALID_START, TEST_START),
    SplitSpec("test", TEST_START, None),
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _require_inputs() -> None:
    for path in (STAGE78_CANDIDATE_PATH, STAGE78_ENTRY_RISK_PATH, STAGE78_TRADES_PATH):
        if not path.exists():
            raise FileNotFoundError(path)


def _build_stage78_candidate_samples() -> tuple[pd.DataFrame, dict[str, Any]]:
    original_paths = (
        candidate_samples.CANDIDATE_PATH,
        candidate_samples.ENTRY_RISK_PATH,
        candidate_samples.TRADES_PATH,
    )
    candidate_samples.CANDIDATE_PATH = STAGE78_CANDIDATE_PATH
    candidate_samples.ENTRY_RISK_PATH = STAGE78_ENTRY_RISK_PATH
    candidate_samples.TRADES_PATH = STAGE78_TRADES_PATH
    try:
        samples_df, coverage = candidate_samples.build_training_samples()
    finally:
        (
            candidate_samples.CANDIDATE_PATH,
            candidate_samples.ENTRY_RISK_PATH,
            candidate_samples.TRADES_PATH,
        ) = original_paths
    return samples_df, coverage


def _add_path_risk_labels(samples_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = samples_df.copy()
    for column in [
        "label_candidate_20d_mae_r",
        "label_candidate_20d_mfe_r",
        "label_candidate_forward_10d_r_multiple",
        "label_candidate_forward_20d_r_multiple",
    ]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)

    mae = frame["label_candidate_20d_mae_r"].clip(lower=0.0, upper=6.0)
    mfe = frame["label_candidate_20d_mfe_r"].clip(lower=0.0, upper=8.0)
    forward_10d = frame["label_candidate_forward_10d_r_multiple"].clip(lower=-5.0, upper=8.0)
    forward_20d = frame["label_candidate_forward_20d_r_multiple"].clip(lower=-6.0, upper=10.0)
    frame[SCORE_COLUMN] = (
        0.55 * mae
        - 0.20 * mfe
        - 0.15 * forward_10d
        - 0.25 * forward_20d
    ).astype("float64")

    frame[GROUP_COLUMN] = pd.to_datetime(frame[GROUP_COLUMN])
    train_mask = frame[GROUP_COLUMN] < pd.Timestamp(TRAIN_END_EXCLUSIVE)
    threshold = float(frame.loc[train_mask, SCORE_COLUMN].quantile(BAD_QUANTILE))
    frame[TARGET_COLUMN] = (frame[SCORE_COLUMN] >= threshold).astype("int64")
    frame["label_path_bad_threshold_train_q67"] = threshold
    frame["label_path_risk_definition"] = "0.55*20d_MAE_R -0.20*20d_MFE_R -0.15*10d_R -0.25*20d_R"

    label_summary = {
        "bad_quantile": BAD_QUANTILE,
        "bad_threshold": threshold,
        "overall_bad_rate": _safe_float(frame[TARGET_COLUMN].mean()),
        "train_bad_rate": _safe_float(frame.loc[train_mask, TARGET_COLUMN].mean()),
        "sample_count": int(len(frame)),
    }
    return frame, label_summary


def _assign_split(samples_df: pd.DataFrame) -> pd.DataFrame:
    frame = samples_df.copy()
    frame[GROUP_COLUMN] = pd.to_datetime(frame[GROUP_COLUMN])
    frame["dataset_split"] = "train"
    frame.loc[frame[GROUP_COLUMN] >= pd.Timestamp(VALID_START), "dataset_split"] = "valid"
    frame.loc[frame[GROUP_COLUMN] >= pd.Timestamp(TEST_START), "dataset_split"] = "test"
    return frame


def _available_feature_columns(df: pd.DataFrame) -> list[str]:
    columns: list[str] = []
    for column in FEATURE_COLUMNS:
        if column in df.columns and pd.api.types.is_numeric_dtype(df[column]):
            columns.append(column)
    return columns


def _prepare_x(df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    x = df[feature_columns].copy()
    for column in feature_columns:
        x[column] = pd.to_numeric(x[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return x


def _train_model(train_df: pd.DataFrame, feature_columns: list[str]) -> Pipeline:
    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    C=0.20,
                    solver="lbfgs",
                    max_iter=3000,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )
    model.fit(_prepare_x(train_df, feature_columns), train_df[TARGET_COLUMN].astype("int64"))
    return model


def _score(model: Pipeline, df: pd.DataFrame, feature_columns: list[str]) -> np.ndarray:
    return np.asarray(model.predict_proba(_prepare_x(df, feature_columns))[:, 1], dtype="float64")


def _compute_split_metrics(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {
            "rows": 0,
            "days": 0,
            "bad_rate": 0.0,
            "predicted_bad_rate": 0.0,
            "accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "roc_auc": 0.0,
            "log_loss": 0.0,
            "avg_path_risk_score": 0.0,
            "avg_20d_mae_r": 0.0,
            "avg_20d_forward_r": 0.0,
        }

    y = df[TARGET_COLUMN].astype("int64")
    p = df[PROBABILITY_COLUMN].astype("float64").clip(1e-6, 1 - 1e-6)
    pred = (p >= 0.5).astype("int64")
    try:
        auc = roc_auc_score(y, p) if y.nunique() >= 2 else float("nan")
    except ValueError:
        auc = float("nan")
    return {
        "rows": int(len(df)),
        "days": int(pd.to_datetime(df[GROUP_COLUMN]).nunique()),
        "bad_rate": _safe_float(y.mean()),
        "predicted_bad_rate": _safe_float(pred.mean()),
        "accuracy": _safe_float(accuracy_score(y, pred)),
        "precision": _safe_float(precision_score(y, pred, zero_division=0)),
        "recall": _safe_float(recall_score(y, pred, zero_division=0)),
        "roc_auc": _safe_float(auc),
        "log_loss": _safe_float(log_loss(y, p, labels=[0, 1])),
        "avg_path_risk_score": _safe_float(df[SCORE_COLUMN].mean()),
        "avg_20d_mae_r": _safe_float(pd.to_numeric(df["label_candidate_20d_mae_r"], errors="coerce").mean()),
        "avg_20d_forward_r": _safe_float(
            pd.to_numeric(df["label_candidate_forward_20d_r_multiple"], errors="coerce").mean()
        ),
    }


def _build_split_metrics(scored_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for split in ["train", "valid", "test"]:
        row = _compute_split_metrics(scored_df[scored_df["dataset_split"] == split].copy())
        row["dataset_split"] = split
        rows.append(row)
    return pd.DataFrame(rows)


def _build_bucket_summary(scored_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for split in ["train", "valid", "test"]:
        split_df = scored_df[scored_df["dataset_split"] == split].copy()
        if split_df.empty or len(split_df) < 5:
            continue
        split_df["risk_probability_bucket"] = pd.qcut(
            split_df[PROBABILITY_COLUMN].rank(method="first"),
            q=5,
            labels=["q1_low_pred_bad", "q2", "q3", "q4", "q5_high_pred_bad"],
        )
        grouped = (
            split_df.groupby("risk_probability_bucket", observed=False)
            .agg(
                sample_count=("sample_id", "count"),
                avg_predicted_bad_probability=(PROBABILITY_COLUMN, "mean"),
                actual_bad_rate=(TARGET_COLUMN, "mean"),
                avg_path_risk_score=(SCORE_COLUMN, "mean"),
                avg_20d_mae_r=("label_candidate_20d_mae_r", "mean"),
                avg_20d_mfe_r=("label_candidate_20d_mfe_r", "mean"),
                avg_20d_forward_r=("label_candidate_forward_20d_r_multiple", "mean"),
                selected_rate=("label_is_selected", "mean"),
            )
            .reset_index()
        )
        grouped.insert(0, "dataset_split", split)
        rows.extend(grouped.to_dict(orient="records"))
    return pd.DataFrame(rows)


def _build_coefficients(model: Pipeline, feature_columns: list[str]) -> pd.DataFrame:
    classifier: LogisticRegression = model.named_steps["classifier"]
    scaler: StandardScaler = model.named_steps["scaler"]
    coefficient_df = pd.DataFrame(
        {
            "feature": feature_columns,
            "scaled_coefficient": classifier.coef_[0],
            "abs_scaled_coefficient": np.abs(classifier.coef_[0]),
            "feature_mean": scaler.mean_,
            "feature_scale": scaler.scale_,
        }
    )
    coefficient_df.sort_values("abs_scaled_coefficient", ascending=False, inplace=True)
    coefficient_df.reset_index(drop=True, inplace=True)
    return coefficient_df


def _feasibility_decision(split_metrics: pd.DataFrame, bucket_summary: pd.DataFrame) -> str:
    test_row = split_metrics[split_metrics["dataset_split"] == "test"]
    valid_row = split_metrics[split_metrics["dataset_split"] == "valid"]
    if test_row.empty or valid_row.empty:
        return "fail_missing_oos_split"

    test_auc = _safe_float(test_row.iloc[0]["roc_auc"])
    valid_auc = _safe_float(valid_row.iloc[0]["roc_auc"])
    test_buckets = bucket_summary[bucket_summary["dataset_split"].astype(str).eq("test")].copy()
    if test_buckets.empty:
        return "fail_missing_bucket_summary"

    ordered = test_buckets.sort_values("risk_probability_bucket")
    low_bad_rate = _safe_float(ordered.iloc[0]["actual_bad_rate"])
    high_bad_rate = _safe_float(ordered.iloc[-1]["actual_bad_rate"])
    low_mae = _safe_float(ordered.iloc[0]["avg_20d_mae_r"])
    high_mae = _safe_float(ordered.iloc[-1]["avg_20d_mae_r"])
    low_forward = _safe_float(ordered.iloc[0]["avg_20d_forward_r"])
    high_forward = _safe_float(ordered.iloc[-1]["avg_20d_forward_r"])

    if min(valid_auc, test_auc) < 0.55:
        return "fail_oos_auc_too_weak"
    if high_bad_rate <= low_bad_rate + 0.10:
        return "fail_bucket_bad_rate_not_separated"
    if high_mae <= low_mae and high_forward >= low_forward:
        return "fail_bucket_path_risk_not_separated"
    return "monitor_signal_candidate_only"


def _build_report(
    split_metrics: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    coefficients: pd.DataFrame,
    decision: str,
    label_summary: dict[str, Any],
) -> str:
    return "\n".join(
        [
            "# Stage162 AI Path-Risk Overlay Feasibility",
            "",
            "## Boundary",
            "",
            "- This is a monitor-only feasibility test, not a trading rule.",
            "- Source profile is `official_stage78_defensive_v1` candidate snapshots.",
            "- Features are limited to ex-ante candidate/context fields.",
            "- Target is path risk, not return maximization.",
            "",
            "## Label",
            "",
            f"- Bad quantile from train split: `{BAD_QUANTILE:.2f}`",
            f"- Bad threshold: `{label_summary['bad_threshold']:.6f}`",
            "- Score: `0.55*20d_MAE_R -0.20*20d_MFE_R -0.15*10d_R -0.25*20d_R`",
            "",
            "## Split Metrics",
            "",
            to_markdown_table(split_metrics),
            "",
            "## Bucket Summary",
            "",
            to_markdown_table(bucket_summary),
            "",
            "## Top Coefficients",
            "",
            to_markdown_table(coefficients.head(20)),
            "",
            "## Decision",
            "",
            f"- `{decision}`",
            "- If this remains only monitor-quality, do not wire it into Stage78.",
            "- A trading overlay requires a separate A/C backtest with frozen model and frozen gate profile.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _require_inputs()
    samples, coverage = _build_stage78_candidate_samples()
    samples, label_summary = _add_path_risk_labels(samples)
    samples = _assign_split(samples)
    feature_columns = _available_feature_columns(samples)

    train_df = samples[samples["dataset_split"].eq("train")].copy()
    if train_df.empty:
        raise ValueError("empty train split")
    model = _train_model(train_df, feature_columns)

    scored = samples.copy()
    scored[PROBABILITY_COLUMN] = _score(model, scored, feature_columns)
    split_metrics = _build_split_metrics(scored)
    bucket_summary = _build_bucket_summary(scored)
    coefficients = _build_coefficients(model, feature_columns)
    decision = _feasibility_decision(split_metrics, bucket_summary)

    samples.to_csv(SAMPLES_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    scored.to_csv(PREDICTIONS_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(BUCKET_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    split_metrics.to_csv(SPLIT_METRICS_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    coefficients.to_csv(COEFFICIENT_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    joblib.dump(model, MODEL_OUTPUT_PATH)
    REPORT_PATH.write_text(
        _build_report(split_metrics, bucket_summary, coefficients, decision, label_summary),
        encoding="utf-8",
    )
    SUMMARY_JSON_PATH.write_text(
        json.dumps(
            {
                "model_tag": MODEL_TAG,
                "base_version": OFFICIAL_STAGE78_VERSION,
                "analysis_type": "monitor_only_feasibility_no_strategy_backtest",
                "decision": decision,
                "coverage": coverage,
                "label_summary": label_summary,
                "split_dates": {
                    "train_end_exclusive": TRAIN_END_EXCLUSIVE,
                    "valid_start": VALID_START,
                    "test_start": TEST_START,
                },
                "feature_columns": feature_columns,
                "split_metrics": split_metrics.to_dict(orient="records"),
                "bucket_summary": bucket_summary.to_dict(orient="records"),
                "top_coefficients": coefficients.head(30).to_dict(orient="records"),
                "output_paths": {
                    "samples": str(SAMPLES_OUTPUT_PATH),
                    "predictions": str(PREDICTIONS_OUTPUT_PATH),
                    "bucket_summary": str(BUCKET_OUTPUT_PATH),
                    "split_metrics": str(SPLIT_METRICS_OUTPUT_PATH),
                    "coefficients": str(COEFFICIENT_OUTPUT_PATH),
                    "model": str(MODEL_OUTPUT_PATH),
                    "report": str(REPORT_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    print(f"[stage162-ai-path-risk] samples: {SAMPLES_OUTPUT_PATH}")
    print(f"[stage162-ai-path-risk] predictions: {PREDICTIONS_OUTPUT_PATH}")
    print(f"[stage162-ai-path-risk] split metrics: {SPLIT_METRICS_OUTPUT_PATH}")
    print(f"[stage162-ai-path-risk] bucket summary: {BUCKET_OUTPUT_PATH}")
    print(f"[stage162-ai-path-risk] report: {REPORT_PATH}")
    print(f"[stage162-ai-path-risk] decision: {decision}")
    print(split_metrics.to_string(index=False))
    print(bucket_summary[bucket_summary["dataset_split"].eq("test")].to_string(index=False))


if __name__ == "__main__":
    main()
