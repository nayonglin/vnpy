from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from typing import Any

import pandas as pd

from build_qmt_roll_ai_candidate_selection_pairwise_samples import (
    FEATURE_COLUMNS as FEATURE_COLUMNS_V1,
    GROUP_COLUMN,
    QUALITY_COLUMN,
    TARGET_COLUMN,
    WEIGHT_COLUMN,
    _safe_float,
    build_pair_row,
    choose_left_right,
    filter_rerankable_pool,
    load_samples,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
PAIRWISE_SAMPLES_OUTPUT_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_selection_pairwise_samples_v2.csv"
PAIRWISE_SCHEMA_OUTPUT_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_selection_pairwise_schema_v2.json"

WEIGHT_COLUMN_V2: str = "label_preferred_pair_weight_v2"
NOISE_SCORE_COLUMN: str = "label_preferred_noise_score_v2"

FEATURE_COLUMNS_V2: list[str] = FEATURE_COLUMNS_V1 + [
    "delta_feature_range_pct_zscore_120",
    "delta_feature_trend_ma20_gap_pct_cs_rank_centered_1d",
    "delta_feature_ma20_ma40_gap_pct_cs_zscore_1d",
    "delta_feature_close_position_60d_cs_zscore_1d",
]


def _clip01(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def _positive_tail(value: object, threshold: float, upper: float) -> float:
    numeric = _safe_float(value)
    if upper <= threshold:
        return 0.0
    return _clip01((max(numeric - threshold, 0.0)) / (upper - threshold))


def _absolute_tail(value: object, threshold: float, upper: float) -> float:
    numeric = abs(_safe_float(value))
    if upper <= threshold:
        return 0.0
    return _clip01((max(numeric - threshold, 0.0)) / (upper - threshold))


def build_pair_row_v2(pair_id: str, left_row: pd.Series, right_row: pd.Series) -> dict[str, Any]:
    row = build_pair_row(pair_id, left_row, right_row)

    row["delta_feature_range_pct_zscore_120"] = _safe_float(left_row.get("feature_range_pct_zscore_120")) - _safe_float(
        right_row.get("feature_range_pct_zscore_120")
    )
    row["delta_feature_trend_ma20_gap_pct_cs_rank_centered_1d"] = _safe_float(
        left_row.get("feature_trend_ma20_gap_pct_cs_rank_centered_1d")
    ) - _safe_float(right_row.get("feature_trend_ma20_gap_pct_cs_rank_centered_1d"))
    row["delta_feature_ma20_ma40_gap_pct_cs_zscore_1d"] = _safe_float(
        left_row.get("feature_ma20_ma40_gap_pct_cs_zscore_1d")
    ) - _safe_float(right_row.get("feature_ma20_ma40_gap_pct_cs_zscore_1d"))
    row["delta_feature_close_position_60d_cs_zscore_1d"] = _safe_float(
        left_row.get("feature_close_position_60d_cs_zscore_1d")
    ) - _safe_float(right_row.get("feature_close_position_60d_cs_zscore_1d"))

    range_tail = max(
        _positive_tail(left_row.get("feature_range_pct_zscore_120"), 0.8, 3.5),
        _positive_tail(right_row.get("feature_range_pct_zscore_120"), 0.8, 3.5),
    )
    momentum_tail = max(
        _positive_tail(left_row.get("feature_ret_20d_zscore_120"), 1.0, 3.5),
        _positive_tail(right_row.get("feature_ret_20d_zscore_120"), 1.0, 3.5),
    )
    trend_tail = max(
        _absolute_tail(left_row.get("feature_trend_ma20_gap_pct_cs_rank_centered_1d"), 0.5, 1.0),
        _absolute_tail(right_row.get("feature_trend_ma20_gap_pct_cs_rank_centered_1d"), 0.5, 1.0),
    )
    structure_tail = max(
        _absolute_tail(left_row.get("feature_ma20_ma40_gap_pct_cs_zscore_1d"), 1.0, 4.0),
        _absolute_tail(right_row.get("feature_ma20_ma40_gap_pct_cs_zscore_1d"), 1.0, 4.0),
    )
    close_position_tail = max(
        _absolute_tail(left_row.get("feature_close_position_60d_cs_zscore_1d"), 1.0, 4.0),
        _absolute_tail(right_row.get("feature_close_position_60d_cs_zscore_1d"), 1.0, 4.0),
    )

    noise_score = (
        0.30 * range_tail
        + 0.24 * momentum_tail
        + 0.18 * trend_tail
        + 0.16 * structure_tail
        + 0.12 * close_position_tail
    )
    credibility_weight = max(0.35, 1.0 - 0.45 * noise_score)

    row[NOISE_SCORE_COLUMN] = noise_score
    row[WEIGHT_COLUMN_V2] = min(_safe_float(row[WEIGHT_COLUMN]) * credibility_weight, 1.25)
    return row


def build_pairwise_samples_v2(pool_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    pair_rows: list[dict[str, Any]] = []

    for candidate_date, group_df in pool_df.groupby(GROUP_COLUMN, sort=False):
        ordered_rows = list(group_df.itertuples(index=False, name="CandidateRow"))
        if len(ordered_rows) < 2:
            continue

        day_pair_count = 0
        for left_idx, right_idx in combinations(range(len(ordered_rows)), 2):
            row_a = pd.Series(ordered_rows[left_idx]._asdict())
            row_b = pd.Series(ordered_rows[right_idx]._asdict())
            left_row, right_row = choose_left_right(row_a, row_b)
            pair_id = f"{pd.Timestamp(candidate_date).date().isoformat()}__{day_pair_count:03d}"
            pair_rows.append(build_pair_row_v2(pair_id, left_row, right_row))
            day_pair_count += 1

    pairwise_df = pd.DataFrame(pair_rows)
    if not pairwise_df.empty:
        pairwise_df[GROUP_COLUMN] = pd.to_datetime(pairwise_df[GROUP_COLUMN])
        pairwise_df.sort_values([GROUP_COLUMN, "pair_id"], inplace=True)
        pairwise_df.reset_index(drop=True, inplace=True)

    coverage = {
        "source_rows": int(len(pool_df)),
        "source_days": int(pool_df[GROUP_COLUMN].nunique()) if not pool_df.empty else 0,
        "pair_rows": int(len(pairwise_df)),
        "pair_days": int(pairwise_df[GROUP_COLUMN].nunique()) if not pairwise_df.empty else 0,
        "feature_columns": FEATURE_COLUMNS_V2,
    }

    if not pairwise_df.empty:
        coverage.update(
            {
                "left_win_rate": _safe_float(pairwise_df[TARGET_COLUMN].mean()),
                "selection_disagreement_rate": _safe_float(pairwise_df["label_preferred_selection_disagreement"].mean()),
                "winner_selected_rate": _safe_float(pairwise_df["label_preferred_winner_selected"].mean()),
                "median_quality_gap_abs": _safe_float(pairwise_df["label_preferred_quality_gap_abs"].median()),
                "mean_quality_gap_abs": _safe_float(pairwise_df["label_preferred_quality_gap_abs"].mean()),
                "mean_pair_weight_v1": _safe_float(pairwise_df[WEIGHT_COLUMN].mean()),
                "mean_pair_weight_v2": _safe_float(pairwise_df[WEIGHT_COLUMN_V2].mean()),
                "mean_noise_score_v2": _safe_float(pairwise_df[NOISE_SCORE_COLUMN].mean()),
            }
        )

    return pairwise_df, coverage


def build_schema(pairwise_df: pd.DataFrame, coverage: dict[str, Any]) -> dict[str, Any]:
    categorical_columns = [
        column
        for column in pairwise_df.columns
        if pd.api.types.is_object_dtype(pairwise_df[column])
        and column not in {"pair_id", GROUP_COLUMN, "left_sample_id", "right_sample_id"}
    ]
    numeric_columns = [
        column
        for column in pairwise_df.columns
        if column not in categorical_columns and column not in {"pair_id", GROUP_COLUMN, "left_sample_id", "right_sample_id"}
    ]

    return {
        "dataset_name": "qmt_roll_ai_candidate_selection_pairwise_samples_v2",
        "source_dataset": "qmt_roll_ai_candidate_training_samples.csv",
        "target_definition": {
            "target_column": TARGET_COLUMN,
            "weight_column_v1": WEIGHT_COLUMN,
            "weight_column_v2": WEIGHT_COLUMN_V2,
            "noise_score_column": NOISE_SCORE_COLUMN,
            "quality_column": QUALITY_COLUMN,
            "motivation": "在保留 pairwise 选择权监督的前提下，把极端波动/极端趋势尾部下沉到 pair 权重层，而不是继续写进标签。",
        },
        "coverage_summary": coverage,
        "categorical_columns": categorical_columns,
        "numeric_columns": numeric_columns,
        "feature_columns": FEATURE_COLUMNS_V2,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    samples_df = load_samples()
    pool_df = filter_rerankable_pool(samples_df)
    pairwise_df, coverage = build_pairwise_samples_v2(pool_df)
    pairwise_df.to_csv(PAIRWISE_SAMPLES_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    schema = build_schema(pairwise_df, coverage)
    PAIRWISE_SCHEMA_OUTPUT_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[selection-pairwise-samples-v2] rows: {len(pairwise_df)}")
    print(f"[selection-pairwise-samples-v2] csv: {PAIRWISE_SAMPLES_OUTPUT_PATH}")
    print(f"[selection-pairwise-samples-v2] schema: {PAIRWISE_SCHEMA_OUTPUT_PATH}")
    print(json.dumps(coverage, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
