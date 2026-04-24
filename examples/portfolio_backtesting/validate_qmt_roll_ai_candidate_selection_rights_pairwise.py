from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from build_qmt_roll_ai_candidate_selection_pairwise_samples import (
    GROUP_COLUMN,
    QUALITY_COLUMN,
    build_pair_row,
    choose_left_right,
    filter_rerankable_pool,
)
from qmt_roll_ai_candidate_selection_label_v2 import add_selection_quality_v2_labels


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
SAMPLES_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_training_samples.csv"

MODEL_TAG: str = "selection_pairwise_v1"
MODEL_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_selection_pairwise_classifier_{MODEL_TAG}.joblib"
MODEL_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_selection_pairwise_classifier_summary_{MODEL_TAG}.json"

SELECTION_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_selection_rights_summary_{MODEL_TAG}.json"
WINDOW_SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_selection_rights_windows_{MODEL_TAG}.csv"
DAY_DETAIL_CSV_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_selection_rights_days_{MODEL_TAG}.csv"

PREDICTION_COLUMN: str = "predicted_pairwise_score"
SELECTED_COLUMN: str = "label_is_selected"
DATE_COLUMN: str = GROUP_COLUMN

COMPARISON_METRICS: tuple[str, ...] = (
    QUALITY_COLUMN,
    "label_candidate_forward_10d_r_multiple",
    "label_candidate_forward_20d_r_multiple",
    "label_candidate_20d_mfe_r",
    "label_candidate_20d_mae_r",
)


@dataclass(frozen=True)
class EvaluationWindow:
    name: str
    start_inclusive: str
    end_exclusive: str | None


WINDOWS: tuple[EvaluationWindow, ...] = (
    EvaluationWindow(name="valid_2023", start_inclusive="2023-01-01", end_exclusive="2024-01-01"),
    EvaluationWindow(name="test_2024", start_inclusive="2024-01-01", end_exclusive="2025-01-01"),
    EvaluationWindow(name="test_2025_plus", start_inclusive="2025-01-01", end_exclusive=None),
    EvaluationWindow(name="test_2024_plus", start_inclusive="2024-01-01", end_exclusive=None),
)


def load_samples() -> pd.DataFrame:
    df = pd.read_csv(SAMPLES_PATH)
    df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN])
    df.sort_values([DATE_COLUMN, "candidate_index", "sample_id"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    df = add_selection_quality_v2_labels(df)
    return filter_rerankable_pool(df)


def load_model_bundle() -> tuple[Any, list[str]]:
    summary = json.loads(MODEL_SUMMARY_PATH.read_text(encoding="utf-8"))
    metadata = summary["model_metadata"]
    feature_columns = list(metadata["feature_columns"])
    model = joblib.load(MODEL_PATH)
    return model, feature_columns


def predict_daily_scores(group_df: pd.DataFrame, model: Any, feature_columns: list[str]) -> pd.DataFrame:
    scored_group = group_df.copy()
    scored_group[PREDICTION_COLUMN] = 0.0

    ordered_rows = list(scored_group.itertuples(index=False, name="CandidateRow"))
    if len(ordered_rows) < 2:
        return scored_group

    pair_rows: list[dict[str, Any]] = []
    pair_mappings: list[tuple[str, str]] = []
    for pair_index, (idx_a, idx_b) in enumerate(combinations(range(len(ordered_rows)), 2)):
        row_a = pd.Series(ordered_rows[idx_a]._asdict())
        row_b = pd.Series(ordered_rows[idx_b]._asdict())
        left_row, right_row = choose_left_right(row_a, row_b)
        pair_rows.append(build_pair_row(f"score__{pair_index:03d}", left_row, right_row))
        pair_mappings.append((str(left_row["sample_id"]), str(right_row["sample_id"])))

    pair_df = pd.DataFrame(pair_rows)
    x = pair_df[feature_columns].copy()
    for column in feature_columns:
        x[column] = pd.to_numeric(x[column], errors="coerce").fillna(0.0)
    probabilities = np.asarray(model.predict_proba(x)[:, 1], dtype="float64")
    score_map = {str(sample_id): 0.0 for sample_id in scored_group["sample_id"].tolist()}

    for probability, (left_id, right_id) in zip(probabilities, pair_mappings):
        score_map[left_id] += float(probability)
        score_map[right_id] += float(1.0 - probability)

    scored_group[PREDICTION_COLUMN] = scored_group["sample_id"].map(score_map).astype("float64")
    return scored_group


def _safe_mean(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    return float(pd.to_numeric(series, errors="coerce").dropna().mean())


def _subset_metric(row_df: pd.DataFrame, metric_column: str) -> float:
    if metric_column not in row_df.columns:
        return 0.0
    return _safe_mean(row_df[metric_column])


def evaluate_group(group_df: pd.DataFrame) -> dict[str, Any]:
    actual_k = int(group_df[SELECTED_COLUMN].sum())
    if actual_k <= 0 or actual_k >= len(group_df):
        return {}

    predicted_selected = group_df.nlargest(actual_k, PREDICTION_COLUMN, keep="first").copy()
    oracle_selected = group_df.nlargest(actual_k, QUALITY_COLUMN, keep="first").copy()
    actual_selected = group_df[group_df[SELECTED_COLUMN] == 1].copy()

    actual_ids = set(actual_selected["sample_id"].tolist())
    predicted_ids = set(predicted_selected["sample_id"].tolist())
    oracle_ids = set(oracle_selected["sample_id"].tolist())

    result: dict[str, Any] = {
        "candidate_date": group_df[DATE_COLUMN].iloc[0].date().isoformat(),
        "candidate_count": int(len(group_df)),
        "selected_count": int(actual_k),
        "actual_ids": "|".join(actual_selected["sample_id"].astype(str).tolist()),
        "predicted_ids": "|".join(predicted_selected["sample_id"].astype(str).tolist()),
        "oracle_ids": "|".join(oracle_selected["sample_id"].astype(str).tolist()),
        "selection_changed": int(actual_ids != predicted_ids),
        "selection_overlap_ratio": float(len(actual_ids & predicted_ids) / max(actual_k, 1)),
        "oracle_overlap_ratio": float(len(actual_ids & oracle_ids) / max(actual_k, 1)),
    }

    for metric_column in COMPARISON_METRICS:
        metric_suffix = metric_column.replace("label_", "")
        result[f"actual_{metric_suffix}"] = _subset_metric(actual_selected, metric_column)
        result[f"predicted_{metric_suffix}"] = _subset_metric(predicted_selected, metric_column)
        result[f"oracle_{metric_suffix}"] = _subset_metric(oracle_selected, metric_column)
        result[f"predicted_minus_actual_{metric_suffix}"] = (
            result[f"predicted_{metric_suffix}"] - result[f"actual_{metric_suffix}"]
        )
        result[f"oracle_minus_actual_{metric_suffix}"] = (
            result[f"oracle_{metric_suffix}"] - result[f"actual_{metric_suffix}"]
        )

    return result


def evaluate_window(scored_df: pd.DataFrame, window: EvaluationWindow) -> tuple[pd.DataFrame, dict[str, Any]]:
    start_ts = pd.Timestamp(window.start_inclusive)
    end_ts = pd.Timestamp(window.end_exclusive) if window.end_exclusive else None

    window_df = scored_df[scored_df[DATE_COLUMN] >= start_ts].copy()
    if end_ts is not None:
        window_df = window_df[window_df[DATE_COLUMN] < end_ts].copy()

    if window_df.empty:
        return pd.DataFrame(), {"window_name": window.name, "day_count": 0, "candidate_rows": 0}

    day_rows = [evaluate_group(group_df) for _, group_df in window_df.groupby(DATE_COLUMN, sort=False)]
    day_rows = [row for row in day_rows if row]
    day_df = pd.DataFrame(day_rows)
    if day_df.empty:
        return pd.DataFrame(), {"window_name": window.name, "day_count": 0, "candidate_rows": int(len(window_df))}

    summary: dict[str, Any] = {
        "window_name": window.name,
        "day_count": int(len(day_df)),
        "candidate_rows": int(len(window_df)),
        "avg_candidate_count": float(day_df["candidate_count"].mean()),
        "avg_selected_count": float(day_df["selected_count"].mean()),
        "selection_changed_rate": float(day_df["selection_changed"].mean()),
        "selection_overlap_ratio": float(day_df["selection_overlap_ratio"].mean()),
        "oracle_overlap_ratio": float(day_df["oracle_overlap_ratio"].mean()),
    }

    for metric_column in COMPARISON_METRICS:
        metric_suffix = metric_column.replace("label_", "")
        summary[f"actual_{metric_suffix}"] = float(day_df[f"actual_{metric_suffix}"].mean())
        summary[f"predicted_{metric_suffix}"] = float(day_df[f"predicted_{metric_suffix}"].mean())
        summary[f"oracle_{metric_suffix}"] = float(day_df[f"oracle_{metric_suffix}"].mean())
        summary[f"predicted_minus_actual_{metric_suffix}"] = float(
            day_df[f"predicted_minus_actual_{metric_suffix}"].mean()
        )
        summary[f"oracle_minus_actual_{metric_suffix}"] = float(day_df[f"oracle_minus_actual_{metric_suffix}"].mean())

    day_df.insert(0, "window_name", window.name)
    return day_df, summary


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    samples_df = load_samples()
    model, feature_columns = load_model_bundle()

    scored_groups: list[pd.DataFrame] = []
    for _, group_df in samples_df.groupby(DATE_COLUMN, sort=False):
        scored_groups.append(predict_daily_scores(group_df, model, feature_columns))
    scored_df = pd.concat(scored_groups, ignore_index=True) if scored_groups else samples_df.copy()

    window_summaries: list[dict[str, Any]] = []
    day_frames: list[pd.DataFrame] = []
    for window in WINDOWS:
        day_df, summary = evaluate_window(scored_df, window)
        window_summaries.append(summary)
        if not day_df.empty:
            day_frames.append(day_df)

    window_df = pd.DataFrame(window_summaries)
    all_day_df = pd.concat(day_frames, ignore_index=True) if day_frames else pd.DataFrame()

    window_df.to_csv(WINDOW_SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    if not all_day_df.empty:
        all_day_df.to_csv(DAY_DETAIL_CSV_PATH, index=False, encoding="utf-8-sig")

    summary_payload = {
        "model_tag": MODEL_TAG,
        "model_path": str(MODEL_PATH),
        "summary_source": str(MODEL_SUMMARY_PATH),
        "samples_path": str(SAMPLES_PATH),
        "quality_column": QUALITY_COLUMN,
        "pool_filter": {
            "entry_context": "flat_entry",
            "selected_count_min": 1,
            "selected_count_less_than_candidate_count": True,
        },
        "comparison_metrics": list(COMPARISON_METRICS),
        "windows": window_summaries,
    }
    SELECTION_SUMMARY_PATH.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[selection-rights-pairwise] summary json: {SELECTION_SUMMARY_PATH}")
    print(f"[selection-rights-pairwise] window csv: {WINDOW_SUMMARY_CSV_PATH}")
    print(f"[selection-rights-pairwise] day csv: {DAY_DETAIL_CSV_PATH}")
    print(window_df.to_string(index=False))


if __name__ == "__main__":
    main()
