from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from validate_qmt_roll_ai_candidate_selection_rights_pairwise_v2 import (
    COMPARISON_METRICS,
    MODEL_PATH,
    MODEL_SUMMARY_PATH,
    PREDICTION_COLUMN,
    QUALITY_COLUMN,
    SELECTED_COLUMN,
    WINDOWS,
    DATE_COLUMN,
    evaluate_window,
    load_model_bundle,
    load_samples,
    predict_daily_scores,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "selection_pairwise_v2_catastrophic_veto_v1"
SELECTION_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_selection_rights_summary_{MODEL_TAG}.json"
WINDOW_SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_selection_rights_windows_{MODEL_TAG}.csv"
DAY_DETAIL_CSV_PATH: Path = OUTPUT_DIR / f"qmt_roll_ai_candidate_selection_rights_days_{MODEL_TAG}.csv"

VETO_PENALTY: float = 1.5


def apply_catastrophic_veto(group_df: pd.DataFrame) -> pd.DataFrame:
    scored_df = group_df.copy()
    veto_mask = (
        (scored_df["direction"] == "short")
        & (scored_df["signal"].isin(["short_case2", "short_case1a"]))
        & (pd.to_numeric(scored_df["feature_ret_20d_zscore_120"], errors="coerce").fillna(0.0) < -0.3)
        & (pd.to_numeric(scored_df["feature_close_position_60d_cs_zscore_1d"], errors="coerce").fillna(0.0) < 0.0)
        & (pd.to_numeric(scored_df["feature_range_pct_zscore_120"], errors="coerce").fillna(0.0) > 0.5)
    )
    scored_df["catastrophic_veto_flag"] = veto_mask.astype("int64")
    scored_df.loc[veto_mask, PREDICTION_COLUMN] = scored_df.loc[veto_mask, PREDICTION_COLUMN] - VETO_PENALTY
    return scored_df


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    samples_df = load_samples()
    model, feature_columns = load_model_bundle()

    scored_groups: list[pd.DataFrame] = []
    for _, group_df in samples_df.groupby(DATE_COLUMN, sort=False):
        scored_group = predict_daily_scores(group_df, model, feature_columns)
        scored_group = apply_catastrophic_veto(scored_group)
        scored_groups.append(scored_group)
    scored_df = pd.concat(scored_groups, ignore_index=True) if scored_groups else samples_df.copy()

    window_summaries: list[dict[str, Any]] = []
    day_frames: list[pd.DataFrame] = []
    for window in WINDOWS:
        day_df, summary = evaluate_window(scored_df, window)
        window_mask = scored_df[DATE_COLUMN] >= pd.Timestamp(window.start_inclusive)
        if window.end_exclusive is not None:
            window_mask &= scored_df[DATE_COLUMN] < pd.Timestamp(window.end_exclusive)
        summary["veto_rate"] = float(scored_df.loc[window_mask, "catastrophic_veto_flag"].mean())
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
        "base_model_path": str(MODEL_PATH),
        "base_summary_source": str(MODEL_SUMMARY_PATH),
        "quality_column": QUALITY_COLUMN,
        "comparison_metrics": list(COMPARISON_METRICS),
        "catastrophic_veto_rule": {
            "direction": "short",
            "signal_in": ["short_case2", "short_case1a"],
            "feature_ret_20d_zscore_120_lt": -0.3,
            "feature_close_position_60d_cs_zscore_1d_lt": 0.0,
            "feature_range_pct_zscore_120_gt": 0.5,
            "prediction_score_penalty": VETO_PENALTY,
        },
        "windows": window_summaries,
    }
    SELECTION_SUMMARY_PATH.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[selection-rights-pairwise-v2-catastrophic-veto] summary json: {SELECTION_SUMMARY_PATH}")
    print(f"[selection-rights-pairwise-v2-catastrophic-veto] window csv: {WINDOW_SUMMARY_CSV_PATH}")
    print(f"[selection-rights-pairwise-v2-catastrophic-veto] day csv: {DAY_DETAIL_CSV_PATH}")
    print(window_df.to_string(index=False))


if __name__ == "__main__":
    main()
