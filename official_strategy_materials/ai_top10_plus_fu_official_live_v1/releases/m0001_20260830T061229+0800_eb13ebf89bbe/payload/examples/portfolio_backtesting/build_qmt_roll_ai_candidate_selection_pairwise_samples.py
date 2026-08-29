from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qmt_roll_ai_candidate_selection_label_v2 import QUALITY_COLUMN_V2, add_selection_quality_v2_labels


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
SOURCE_SAMPLES_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_training_samples.csv"
PAIRWISE_SAMPLES_OUTPUT_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_selection_pairwise_samples.csv"
PAIRWISE_SCHEMA_OUTPUT_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_selection_pairwise_schema.json"

GROUP_COLUMN: str = "candidate_date"
ENTRY_CONTEXT_COLUMN: str = "entry_context"
SELECTED_COLUMN: str = "label_is_selected"

QUALITY_COLUMN: str = QUALITY_COLUMN_V2
TARGET_COLUMN: str = "label_preferred_left_wins"
WEIGHT_COLUMN: str = "label_preferred_pair_weight"

FEATURE_COLUMNS: list[str] = [
    "feature_pair_same_direction",
    "feature_pair_same_signal",
    "feature_pair_same_risk_mode",
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
    "delta_feature_close_position_60d",
    "delta_feature_ret_20d_zscore_120",
]


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or np.isinf(result):
        return default
    return result


def load_samples() -> pd.DataFrame:
    df = pd.read_csv(SOURCE_SAMPLES_PATH)
    df[GROUP_COLUMN] = pd.to_datetime(df[GROUP_COLUMN])
    df.sort_values([GROUP_COLUMN, "candidate_index", "sample_id"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    df = add_selection_quality_v2_labels(df)
    return df


def filter_rerankable_pool(df: pd.DataFrame) -> pd.DataFrame:
    pool_df = df[df[ENTRY_CONTEXT_COLUMN] == "flat_entry"].copy()
    selected_count = pool_df.groupby(GROUP_COLUMN)[SELECTED_COLUMN].transform("sum")
    candidate_count = pool_df.groupby(GROUP_COLUMN)["sample_id"].transform("count")
    mask = (candidate_count >= 2) & (selected_count >= 1) & (selected_count < candidate_count)
    pool_df = pool_df.loc[mask].copy()
    pool_df.reset_index(drop=True, inplace=True)
    return pool_df


def _candidate_rank_tuple(row: pd.Series) -> tuple[float, float, float, float, str]:
    return (
        _safe_float(row.get(QUALITY_COLUMN)),
        _safe_float(row.get("label_candidate_forward_20d_r_multiple")),
        _safe_float(row.get("label_candidate_forward_10d_r_multiple")),
        -_safe_float(row.get("label_candidate_20d_mae_r")),
        str(row.get("sample_id", "")),
    )


def choose_left_right(row_a: pd.Series, row_b: pd.Series) -> tuple[pd.Series, pd.Series]:
    key_a = (_safe_float(row_a.get("candidate_index")), str(row_a.get("sample_id", "")))
    key_b = (_safe_float(row_b.get("candidate_index")), str(row_b.get("sample_id", "")))
    if key_a <= key_b:
        return row_a, row_b
    return row_b, row_a


def compute_pair_label(left_row: pd.Series, right_row: pd.Series) -> dict[str, Any]:
    left_rank = _candidate_rank_tuple(left_row)
    right_rank = _candidate_rank_tuple(right_row)
    left_wins = int(left_rank > right_rank)

    quality_gap = left_rank[0] - right_rank[0]
    forward_20d_gap = left_rank[1] - right_rank[1]
    forward_10d_gap = left_rank[2] - right_rank[2]
    mae_gap = _safe_float(left_row.get("label_candidate_20d_mae_r")) - _safe_float(
        right_row.get("label_candidate_20d_mae_r")
    )
    selection_disagreement = int(_safe_float(left_row.get(SELECTED_COLUMN)) != _safe_float(right_row.get(SELECTED_COLUMN)))

    base_weight = min(max(abs(quality_gap) / 2.0, 0.10), 1.0)
    pair_weight = min(base_weight * (1.25 if selection_disagreement else 1.0), 1.25)

    return {
        TARGET_COLUMN: left_wins,
        "label_preferred_quality_gap": quality_gap,
        "label_preferred_quality_gap_abs": abs(quality_gap),
        "label_preferred_forward_20d_gap": forward_20d_gap,
        "label_preferred_forward_10d_gap": forward_10d_gap,
        "label_preferred_mae_20d_gap": mae_gap,
        "label_preferred_selection_disagreement": selection_disagreement,
        WEIGHT_COLUMN: pair_weight,
        "label_preferred_winner_sample_id": str(left_row["sample_id"] if left_wins else right_row["sample_id"]),
        "label_preferred_winner_selected": int(
            _safe_float(left_row.get(SELECTED_COLUMN)) if left_wins else _safe_float(right_row.get(SELECTED_COLUMN))
        ),
    }


def _delta(left_row: pd.Series, right_row: pd.Series, column: str) -> float:
    return _safe_float(left_row.get(column)) - _safe_float(right_row.get(column))


def build_pair_row(pair_id: str, left_row: pd.Series, right_row: pd.Series) -> dict[str, Any]:
    label_info = compute_pair_label(left_row, right_row)

    row: dict[str, Any] = {
        "pair_id": pair_id,
        GROUP_COLUMN: pd.Timestamp(left_row[GROUP_COLUMN]).date().isoformat(),
        "left_sample_id": str(left_row["sample_id"]),
        "right_sample_id": str(right_row["sample_id"]),
        "left_candidate_index": int(_safe_float(left_row.get("candidate_index"))),
        "right_candidate_index": int(_safe_float(right_row.get("candidate_index"))),
        "left_product_symbol": str(left_row.get("product_symbol", "")),
        "right_product_symbol": str(right_row.get("product_symbol", "")),
        "left_signal": str(left_row.get("signal", "")),
        "right_signal": str(right_row.get("signal", "")),
        "left_direction": str(left_row.get("direction", "")),
        "right_direction": str(right_row.get("direction", "")),
        "left_risk_mode": str(left_row.get("risk_mode", "")),
        "right_risk_mode": str(right_row.get("risk_mode", "")),
        "left_selected": int(_safe_float(left_row.get(SELECTED_COLUMN))),
        "right_selected": int(_safe_float(right_row.get(SELECTED_COLUMN))),
        "left_quality_score": _safe_float(left_row.get(QUALITY_COLUMN)),
        "right_quality_score": _safe_float(right_row.get(QUALITY_COLUMN)),
        "left_forward_10d_r": _safe_float(left_row.get("label_candidate_forward_10d_r_multiple")),
        "right_forward_10d_r": _safe_float(right_row.get("label_candidate_forward_10d_r_multiple")),
        "left_forward_20d_r": _safe_float(left_row.get("label_candidate_forward_20d_r_multiple")),
        "right_forward_20d_r": _safe_float(right_row.get("label_candidate_forward_20d_r_multiple")),
        "left_20d_mae_r": _safe_float(left_row.get("label_candidate_20d_mae_r")),
        "right_20d_mae_r": _safe_float(right_row.get("label_candidate_20d_mae_r")),
        "feature_pair_same_direction": int(str(left_row.get("direction", "")) == str(right_row.get("direction", ""))),
        "feature_pair_same_signal": int(str(left_row.get("signal", "")) == str(right_row.get("signal", ""))),
        "feature_pair_same_risk_mode": int(str(left_row.get("risk_mode", "")) == str(right_row.get("risk_mode", ""))),
        "delta_risk_ratio": _delta(left_row, right_row, "risk_ratio"),
        "delta_remaining_position_slots": _delta(left_row, right_row, "remaining_position_slots"),
        "delta_feature_ret_signed_5d": _delta(left_row, right_row, "feature_ret_signed_5d"),
        "delta_feature_trend_ma20_gap_pct": _delta(left_row, right_row, "feature_trend_ma20_gap_pct"),
        "delta_feature_atr14_pct_zscore_120": _delta(left_row, right_row, "feature_atr14_pct_zscore_120"),
        "delta_feature_lower_wick_pct": _delta(left_row, right_row, "feature_lower_wick_pct"),
        "delta_feature_volume_ratio_2v2": _delta(left_row, right_row, "feature_volume_ratio_2v2"),
        "delta_feature_margin_per_contract_to_equity": _delta(
            left_row, right_row, "feature_margin_per_contract_to_equity"
        ),
        "delta_feature_oi_delta_1d_pct": _delta(left_row, right_row, "feature_oi_delta_1d_pct"),
        "delta_feature_oi_delta_1d_pct_zscore_120": _delta(
            left_row, right_row, "feature_oi_delta_1d_pct_zscore_120"
        ),
        "delta_feature_close_position_60d": _delta(left_row, right_row, "feature_close_position_60d"),
        "delta_feature_ret_20d_zscore_120": _delta(left_row, right_row, "feature_ret_20d_zscore_120"),
    }
    row.update(label_info)

    for feature_column in FEATURE_COLUMNS:
        if feature_column.startswith("delta_"):
            row[f"abs_{feature_column}"] = abs(_safe_float(row[feature_column]))

    return row


def build_pairwise_samples(pool_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
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
            pair_rows.append(build_pair_row(pair_id, left_row, right_row))
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
        "feature_columns": FEATURE_COLUMNS,
    }

    if not pairwise_df.empty:
        coverage.update(
            {
                "left_win_rate": _safe_float(pairwise_df[TARGET_COLUMN].mean()),
                "selection_disagreement_rate": _safe_float(pairwise_df["label_preferred_selection_disagreement"].mean()),
                "winner_selected_rate": _safe_float(pairwise_df["label_preferred_winner_selected"].mean()),
                "median_quality_gap_abs": _safe_float(pairwise_df["label_preferred_quality_gap_abs"].median()),
                "mean_quality_gap_abs": _safe_float(pairwise_df["label_preferred_quality_gap_abs"].mean()),
                "mean_pair_weight": _safe_float(pairwise_df[WEIGHT_COLUMN].mean()),
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
        "dataset_name": "qmt_roll_ai_candidate_selection_pairwise_samples",
        "source_dataset": str(SOURCE_SAMPLES_PATH.name),
        "row_definition": "每一行对应同一交易日内两个可重排候选之间的选择权胜负样本，只覆盖 flat_entry 且当日确实存在选择冲突的候选池。",
        "target_definition": {
            "target_column": TARGET_COLUMN,
            "weight_column": WEIGHT_COLUMN,
            "quality_column": QUALITY_COLUMN,
            "winner_rule": "先比较 v2 未来质量分，再用 20d/10d forward R 与 20d MAE 做稳定 tie-break。",
            "motivation": "把任务收敛为同日候选相对优先级学习，而不是继续做 pointwise 绝对分数回归。",
        },
        "pool_filter": {
            "entry_context": "flat_entry",
            "candidate_count_min": 2,
            "selected_count_min": 1,
            "selected_count_less_than_candidate_count": True,
        },
        "coverage_summary": coverage,
        "categorical_columns": categorical_columns,
        "numeric_columns": numeric_columns,
        "feature_columns": FEATURE_COLUMNS,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    samples_df = load_samples()
    pool_df = filter_rerankable_pool(samples_df)
    pairwise_df, coverage = build_pairwise_samples(pool_df)
    pairwise_df.to_csv(PAIRWISE_SAMPLES_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    schema = build_schema(pairwise_df, coverage)
    PAIRWISE_SCHEMA_OUTPUT_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[selection-pairwise-samples] rows: {len(pairwise_df)}")
    print(f"[selection-pairwise-samples] csv: {PAIRWISE_SAMPLES_OUTPUT_PATH}")
    print(f"[selection-pairwise-samples] schema: {PAIRWISE_SCHEMA_OUTPUT_PATH}")
    print(json.dumps(coverage, ensure_ascii=False, indent=2))
    if not pairwise_df.empty:
        preview_columns = [
            GROUP_COLUMN,
            "pair_id",
            "left_sample_id",
            "right_sample_id",
            TARGET_COLUMN,
            WEIGHT_COLUMN,
            "label_preferred_quality_gap",
            "label_preferred_selection_disagreement",
            "left_selected",
            "right_selected",
        ]
        print(pairwise_df[preview_columns].head(12).to_string(index=False))


if __name__ == "__main__":
    main()
