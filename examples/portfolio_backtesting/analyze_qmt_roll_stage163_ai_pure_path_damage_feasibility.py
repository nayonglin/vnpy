from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import analyze_qmt_roll_stage162_ai_path_risk_overlay_feasibility as stage162
from build_qmt_roll_ai_position_training_samples import _locate_entry_index, _safe_float, _safe_ratio, load_contract_bars
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_VERSION
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage163_ai_pure_path_damage_feasibility_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage163_ai_pure_path_damage_feasibility"

SAMPLES_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_samples_{MODEL_TAG}.csv"
PREDICTIONS_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_predictions_{MODEL_TAG}.csv"
BUCKET_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
SPLIT_METRICS_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_split_metrics_{MODEL_TAG}.csv"
COEFFICIENT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coefficients_{MODEL_TAG}.csv"
MODEL_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_model_{MODEL_TAG}.joblib"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

GROUP_COLUMN: str = "candidate_date"
TARGET_COLUMN: str = "label_stage163_pure_path_damage_bad_v1"
SCORE_COLUMN: str = "label_stage163_pure_path_damage_score_v1"
PROBABILITY_COLUMN: str = "predicted_pure_path_damage_bad_probability"
BAD_QUANTILE: float = 0.67

PATH_LABEL_COLUMNS: tuple[str, ...] = (
    "label_stage163_20d_mae_r",
    "label_stage163_40d_mae_r",
    "label_stage163_first_profit_day_40",
    "label_stage163_adverse_before_profit_r",
    "label_stage163_lookahead_days",
    "label_stage163_profit_after_2r_adverse_40",
)


def _normalize_direction(value: object) -> str:
    direction = str(value).lower()
    if direction == "long":
        return "long"
    if direction == "short":
        return "short"
    return direction


def _clip(value: float, lower: float, upper: float) -> float:
    if pd.isna(value) or math.isinf(value):
        return lower
    return float(min(max(value, lower), upper))


def _effective_stop_distance(row: pd.Series) -> float:
    stop_distance = _safe_float(row.get("stop_distance"))
    contract_size = max(_safe_float(row.get("contract_size"), 1.0), 1.0)
    risk_per_contract = _safe_float(row.get("risk_per_contract"))
    if stop_distance <= 0.0 and risk_per_contract > 0.0:
        stop_distance = risk_per_contract / contract_size
    if stop_distance <= 0.0:
        stop_distance = _safe_float(row.get("label_candidate_effective_stop_distance"))
    return max(stop_distance, 1e-6)


def _compute_path_damage_label_row(row: pd.Series) -> dict[str, Any]:
    vt_symbol = str(row.get("contract_vt_symbol", ""))
    bars_df = load_contract_bars(vt_symbol)
    entry_date = pd.Timestamp(row.get(GROUP_COLUMN)).normalize()
    entry_index = _locate_entry_index(bars_df, entry_date)
    entry_price = _safe_float(row.get("entry_price"))
    stop_distance = _effective_stop_distance(row)
    direction = _normalize_direction(row.get("direction"))
    direction_sign = 1.0 if direction == "long" else -1.0

    empty_row = {
        "label_stage163_20d_mae_r": 0.0,
        "label_stage163_40d_mae_r": 0.0,
        "label_stage163_first_profit_day_40": 41.0,
        "label_stage163_adverse_before_profit_r": 0.0,
        "label_stage163_lookahead_days": 0.0,
        "label_stage163_profit_after_2r_adverse_40": 0.0,
        "label_stage163_path_label_available": 0,
    }
    if bars_df.empty or entry_index is None or entry_price <= 0.0 or direction not in {"long", "short"}:
        return empty_row

    end_index = min(entry_index + 40, len(bars_df) - 1)
    lookahead = bars_df.iloc[entry_index : end_index + 1].copy()
    if lookahead.empty:
        return empty_row

    high = lookahead["high"].astype("float64")
    low = lookahead["low"].astype("float64")
    close = lookahead["close"].astype("float64")
    if direction == "long":
        adverse_r = ((entry_price - low) / stop_distance).clip(lower=0.0)
    else:
        adverse_r = ((high - entry_price) / stop_distance).clip(lower=0.0)
    signed_close_r = ((close - entry_price) / stop_distance) * direction_sign

    offsets = np.arange(len(lookahead), dtype="int64")
    future_offsets = offsets[offsets > 0]
    first_profit_day = 41.0
    if len(future_offsets) > 0:
        positive_offsets = future_offsets[np.asarray(signed_close_r.iloc[future_offsets] > 0.0)]
        if len(positive_offsets) > 0:
            first_profit_day = float(int(positive_offsets[0]))

    mae20 = _safe_float(adverse_r.iloc[: min(21, len(adverse_r))].max())
    mae40 = _safe_float(adverse_r.max())
    if first_profit_day <= 40:
        adverse_before_profit = _safe_float(adverse_r.iloc[: int(first_profit_day) + 1].max())
    else:
        adverse_before_profit = mae40
    profit_after_2r_adverse = float(first_profit_day <= 40 and adverse_before_profit >= 2.0)

    return {
        "label_stage163_20d_mae_r": mae20,
        "label_stage163_40d_mae_r": mae40,
        "label_stage163_first_profit_day_40": first_profit_day,
        "label_stage163_adverse_before_profit_r": adverse_before_profit,
        "label_stage163_lookahead_days": float(max(end_index - entry_index, 0)),
        "label_stage163_profit_after_2r_adverse_40": profit_after_2r_adverse,
        "label_stage163_path_label_available": 1,
    }


def _add_pure_path_damage_labels(samples_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = samples_df.copy()
    path_label_df = frame.apply(_compute_path_damage_label_row, axis=1, result_type="expand")
    for column in path_label_df.columns:
        frame[column] = path_label_df[column]

    for column in PATH_LABEL_COLUMNS:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)

    mae20 = frame["label_stage163_20d_mae_r"].clip(lower=0.0, upper=8.0)
    mae40 = frame["label_stage163_40d_mae_r"].clip(lower=0.0, upper=8.0)
    adverse_before_profit = frame["label_stage163_adverse_before_profit_r"].clip(lower=0.0, upper=8.0)
    first_profit_wait_component = frame["label_stage163_first_profit_day_40"].clip(lower=0.0, upper=40.0) / 40.0 * 4.0
    frame[SCORE_COLUMN] = (
        0.50 * mae20
        + 0.25 * mae40
        + 0.15 * adverse_before_profit
        + 0.10 * first_profit_wait_component
    ).astype("float64")

    frame[GROUP_COLUMN] = pd.to_datetime(frame[GROUP_COLUMN])
    train_mask = frame[GROUP_COLUMN] < pd.Timestamp(stage162.TRAIN_END_EXCLUSIVE)
    threshold = float(frame.loc[train_mask, SCORE_COLUMN].quantile(BAD_QUANTILE))
    frame[TARGET_COLUMN] = (frame[SCORE_COLUMN] >= threshold).astype("int64")
    frame["label_stage163_bad_threshold_train_q67"] = threshold
    frame["label_stage163_definition"] = (
        "0.50*clip(20d_MAE_R,0,8) + 0.25*clip(40d_MAE_R,0,8) "
        "+ 0.15*clip(adverse_before_first_profit_R,0,8) + 0.10*(min(first_profit_day_40,40)/40*4)"
    )

    label_summary = {
        "bad_quantile": BAD_QUANTILE,
        "bad_threshold": threshold,
        "overall_bad_rate": _safe_float(frame[TARGET_COLUMN].mean()),
        "train_bad_rate": _safe_float(frame.loc[train_mask, TARGET_COLUMN].mean()),
        "sample_count": int(len(frame)),
        "path_label_available_count": int(pd.to_numeric(frame["label_stage163_path_label_available"], errors="coerce").sum()),
        "avg_20d_mae_r": _safe_float(frame["label_stage163_20d_mae_r"].mean()),
        "avg_40d_mae_r": _safe_float(frame["label_stage163_40d_mae_r"].mean()),
        "avg_first_profit_day_40": _safe_float(frame["label_stage163_first_profit_day_40"].mean()),
        "avg_adverse_before_profit_r": _safe_float(frame["label_stage163_adverse_before_profit_r"].mean()),
    }
    return frame, label_summary


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
            "avg_pure_path_damage_score": 0.0,
            "avg_20d_mae_r": 0.0,
            "avg_40d_mae_r": 0.0,
            "avg_first_profit_day_40": 0.0,
            "avg_adverse_before_profit_r": 0.0,
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
        "avg_pure_path_damage_score": _safe_float(df[SCORE_COLUMN].mean()),
        "avg_20d_mae_r": _safe_float(df["label_stage163_20d_mae_r"].mean()),
        "avg_40d_mae_r": _safe_float(df["label_stage163_40d_mae_r"].mean()),
        "avg_first_profit_day_40": _safe_float(df["label_stage163_first_profit_day_40"].mean()),
        "avg_adverse_before_profit_r": _safe_float(df["label_stage163_adverse_before_profit_r"].mean()),
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
        split_df["path_damage_probability_bucket"] = pd.qcut(
            split_df[PROBABILITY_COLUMN].rank(method="first"),
            q=5,
            labels=["q1_low_pred_bad", "q2", "q3", "q4", "q5_high_pred_bad"],
        )
        grouped = (
            split_df.groupby("path_damage_probability_bucket", observed=False)
            .agg(
                sample_count=("sample_id", "count"),
                avg_predicted_bad_probability=(PROBABILITY_COLUMN, "mean"),
                actual_bad_rate=(TARGET_COLUMN, "mean"),
                avg_pure_path_damage_score=(SCORE_COLUMN, "mean"),
                avg_20d_mae_r=("label_stage163_20d_mae_r", "mean"),
                avg_40d_mae_r=("label_stage163_40d_mae_r", "mean"),
                avg_first_profit_day_40=("label_stage163_first_profit_day_40", "mean"),
                avg_adverse_before_profit_r=("label_stage163_adverse_before_profit_r", "mean"),
                avg_profit_after_2r_adverse_40=("label_stage163_profit_after_2r_adverse_40", "mean"),
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

    ordered = test_buckets.sort_values("path_damage_probability_bucket")
    low_bad_rate = _safe_float(ordered.iloc[0]["actual_bad_rate"])
    high_bad_rate = _safe_float(ordered.iloc[-1]["actual_bad_rate"])
    low_mae20 = _safe_float(ordered.iloc[0]["avg_20d_mae_r"])
    high_mae20 = _safe_float(ordered.iloc[-1]["avg_20d_mae_r"])
    low_adverse = _safe_float(ordered.iloc[0]["avg_adverse_before_profit_r"])
    high_adverse = _safe_float(ordered.iloc[-1]["avg_adverse_before_profit_r"])

    if min(valid_auc, test_auc) < 0.56:
        return "fail_oos_auc_too_weak"
    if high_bad_rate <= low_bad_rate + 0.10:
        return "fail_bucket_bad_rate_not_separated"
    if high_mae20 <= low_mae20 and high_adverse <= low_adverse:
        return "fail_bucket_path_damage_not_separated"
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
            "# Stage163 AI Pure Path-Damage Feasibility",
            "",
            "## Boundary",
            "",
            "- This is a monitor-only feasibility test, not a trading rule.",
            "- Source profile is `official_stage78_defensive_v1` candidate snapshots.",
            "- Features are limited to ex-ante candidate/context fields.",
            "- Target is pure path damage, not return maximization.",
            "",
            "## Label",
            "",
            f"- Bad quantile from train split: `{BAD_QUANTILE:.2f}`",
            f"- Bad threshold: `{label_summary['bad_threshold']:.6f}`",
            "- Score: `0.50*20d_MAE_R + 0.25*40d_MAE_R + 0.15*adverse_before_first_profit_R + 0.10*wait_component`",
            "- The label does not reward 20d forward return or MFE.",
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
            "- A trading overlay requires a separate A/C backtest with frozen model and frozen gate profile.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage162._require_inputs()
    samples, coverage = stage162._build_stage78_candidate_samples()
    samples, label_summary = _add_pure_path_damage_labels(samples)
    samples = stage162._assign_split(samples)
    feature_columns = stage162._available_feature_columns(samples)

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
                    "train_end_exclusive": stage162.TRAIN_END_EXCLUSIVE,
                    "valid_start": stage162.VALID_START,
                    "test_start": stage162.TEST_START,
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

    print(f"[stage163-ai-pure-path-damage] samples: {SAMPLES_OUTPUT_PATH}")
    print(f"[stage163-ai-pure-path-damage] predictions: {PREDICTIONS_OUTPUT_PATH}")
    print(f"[stage163-ai-pure-path-damage] split metrics: {SPLIT_METRICS_OUTPUT_PATH}")
    print(f"[stage163-ai-pure-path-damage] bucket summary: {BUCKET_OUTPUT_PATH}")
    print(f"[stage163-ai-pure-path-damage] report: {REPORT_PATH}")
    print(f"[stage163-ai-pure-path-damage] decision: {decision}")
    print(split_metrics.to_string(index=False))
    print(bucket_summary[bucket_summary["dataset_split"].eq("test")].to_string(index=False))


if __name__ == "__main__":
    main()
