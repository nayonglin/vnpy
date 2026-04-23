from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

SOURCE_SAMPLES_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_pairwise_horizon_strong_denoised_samples.csv"
REFINED_SAMPLES_OUTPUT_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_pairwise_horizon_strong_refined_samples.csv"
REFINED_SCHEMA_OUTPUT_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_pairwise_horizon_strong_refined_schema.json"

STRENGTH_COLUMN: str = "label_horizon_primary_strength_bucket"
STRONG_BUCKET_NAME: str = "strong"
SAME_SIGNAL_COLUMN: str = "feature_pair_same_signal"
TREND_DIFF_COLUMN: str = "abs_delta_feature_trend_ma20_gap_pct"
RET20_DIFF_COLUMN: str = "abs_delta_feature_ret_20d_zscore_120"
TREND_DIFF_FLOOR: float = 0.02
RET20_DIFF_FLOOR: float = 1.4

STRONG_SUBTYPE_COLUMN: str = "label_strong_pair_subtype"
STRONG_REFINED_KEEP_COLUMN: str = "label_strong_refined_is_kept"


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result):
        return default
    return result


def load_samples() -> pd.DataFrame:
    df = pd.read_csv(SOURCE_SAMPLES_PATH)
    df["candidate_date"] = pd.to_datetime(df["candidate_date"])
    df.sort_values(["candidate_date", "pair_id"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def classify_strong_subtype(row: pd.Series) -> str:
    if str(row.get(STRENGTH_COLUMN, "")) != STRONG_BUCKET_NAME:
        return "non_strong"

    same_signal = int(_safe_float(row.get(SAME_SIGNAL_COLUMN)))
    trend_diff = _safe_float(row.get(TREND_DIFF_COLUMN))
    ret20_diff = _safe_float(row.get(RET20_DIFF_COLUMN))

    if same_signal == 1 and trend_diff < TREND_DIFF_FLOOR and ret20_diff < RET20_DIFF_FLOOR:
        return "crowding_noise"
    return "trend_continuation_or_structural"


def build_refined_samples() -> tuple[pd.DataFrame, dict[str, Any]]:
    source_df = load_samples()
    refined_df = source_df.copy()
    refined_df[STRONG_SUBTYPE_COLUMN] = refined_df.apply(classify_strong_subtype, axis=1)
    refined_df[STRONG_REFINED_KEEP_COLUMN] = (
        refined_df[STRONG_SUBTYPE_COLUMN] != "crowding_noise"
    ).astype("int64")

    dropped_df = refined_df[refined_df[STRONG_REFINED_KEEP_COLUMN] == 0].copy()
    kept_df = refined_df[refined_df[STRONG_REFINED_KEEP_COLUMN] == 1].copy()
    kept_df.reset_index(drop=True, inplace=True)

    source_split = pd.Series("train", index=refined_df.index, dtype="object")
    source_split.loc[refined_df["candidate_date"] >= pd.Timestamp("2023-01-01")] = "valid"
    source_split.loc[refined_df["candidate_date"] >= pd.Timestamp("2024-01-01")] = "test"
    dropped_df["dataset_split"] = source_split.loc[dropped_df.index]

    kept_strong_df = kept_df[kept_df[STRENGTH_COLUMN] == STRONG_BUCKET_NAME].copy()

    coverage = {
        "source_rows": int(len(refined_df)),
        "source_days": int(refined_df["candidate_date"].nunique()),
        "strong_rows_before": int((refined_df[STRENGTH_COLUMN] == STRONG_BUCKET_NAME).sum()),
        "strong_same_signal_column": SAME_SIGNAL_COLUMN,
        "strong_trend_diff_column": TREND_DIFF_COLUMN,
        "strong_ret20_diff_column": RET20_DIFF_COLUMN,
        "trend_diff_floor": TREND_DIFF_FLOOR,
        "ret20_diff_floor": RET20_DIFF_FLOOR,
        "dropped_refined_rows": int(len(dropped_df)),
        "kept_rows": int(len(kept_df)),
        "kept_days": int(kept_df["candidate_date"].nunique()),
        "strong_rows_after": int(len(kept_strong_df)),
        "subtype_distribution_before": refined_df[STRONG_SUBTYPE_COLUMN].value_counts().sort_index().to_dict(),
        "subtype_distribution_after": kept_df[STRONG_SUBTYPE_COLUMN].value_counts().sort_index().to_dict(),
    }

    if not dropped_df.empty:
        coverage.update(
            {
                "dropped_split_distribution": dropped_df["dataset_split"].value_counts().sort_index().to_dict(),
                "dropped_left_win_rate": _safe_float(dropped_df["label_horizon_primary_left_wins"].mean()),
                "dropped_mean_primary_gap_abs": _safe_float(dropped_df["label_horizon_primary_gap_abs"].mean()),
                "dropped_mean_trend_diff": _safe_float(dropped_df[TREND_DIFF_COLUMN].mean()),
                "dropped_mean_ret20_diff": _safe_float(dropped_df[RET20_DIFF_COLUMN].mean()),
            }
        )

    if not kept_df.empty:
        coverage.update(
            {
                "kept_left_win_rate": _safe_float(kept_df["label_horizon_primary_left_wins"].mean()),
                "kept_winner_selected_rate": _safe_float(kept_df["label_winner_selected"].mean()),
                "kept_strength_distribution": kept_df[STRENGTH_COLUMN].value_counts().sort_index().to_dict(),
            }
        )

    return kept_df, coverage


def build_schema(refined_df: pd.DataFrame, coverage: dict[str, Any]) -> dict[str, Any]:
    categorical_columns = [
        column
        for column in refined_df.columns
        if pd.api.types.is_object_dtype(refined_df[column])
        and column
        not in {
            "pair_id",
            "candidate_date",
            "left_sample_id",
            "right_sample_id",
            "left_contract_vt_symbol",
            "right_contract_vt_symbol",
            "winner_sample_id",
            "loser_sample_id",
            "winner_contract_vt_symbol",
            "loser_contract_vt_symbol",
        }
    ]
    numeric_columns = [
        column
        for column in refined_df.columns
        if column not in categorical_columns
        and column
        not in {
            "pair_id",
            "candidate_date",
            "left_sample_id",
            "right_sample_id",
            "left_contract_vt_symbol",
            "right_contract_vt_symbol",
            "winner_sample_id",
            "loser_sample_id",
            "winner_contract_vt_symbol",
            "loser_contract_vt_symbol",
        }
    ]

    return {
        "dataset_name": "qmt_roll_ai_candidate_pairwise_horizon_strong_refined_samples",
        "source_dataset": str(SOURCE_SAMPLES_PATH.name),
        "row_definition": "在第十阶段 strong 去噪样本基础上，进一步把 strong 组细分为拥挤噪声型和趋势延续型后的 refined 样本。",
        "strong_refinement_rules": {
            "target_bucket": STRONG_BUCKET_NAME,
            "subtype_column": STRONG_SUBTYPE_COLUMN,
            "crowding_noise_definition": (
                f"{SAME_SIGNAL_COLUMN} == 1 and {TREND_DIFF_COLUMN} < {TREND_DIFF_FLOOR:.2f} "
                f"and {RET20_DIFF_COLUMN} < {RET20_DIFF_FLOOR:.1f}"
            ),
            "keep_column": STRONG_REFINED_KEEP_COLUMN,
            "motivation": "同信号但趋势结构和中期收益结构都没拉开时，strong 更像拥挤尾部噪声，而不是趋势延续胜负。",
        },
        "target_recommendation": {
            "primary_binary_label": "label_horizon_primary_left_wins",
            "sample_weight_column": "label_horizon_primary_weight",
            "analysis_labels": [
                STRONG_SUBTYPE_COLUMN,
                "label_winner_selected",
                "label_horizon_primary_strength_bucket",
            ],
        },
        "coverage_summary": coverage,
        "categorical_columns": categorical_columns,
        "numeric_columns": numeric_columns,
        "notes": [
            "这一步不是继续按单一异常值裁剪，而是给 strong 组增加原型层次。",
            "crowding_noise 更接近同主题拥挤但结构差没有真正拉开的伪强样本。",
            "trend_continuation_or_structural 保留了 strong 中更像真正趋势延续的子集。",
        ],
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    refined_df, coverage = build_refined_samples()
    refined_df.to_csv(REFINED_SAMPLES_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    schema = build_schema(refined_df, coverage)
    REFINED_SCHEMA_OUTPUT_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[ai-candidate-pairwise-horizon-strong-refined-samples] rows: {len(refined_df)}")
    print(f"[ai-candidate-pairwise-horizon-strong-refined-samples] csv: {REFINED_SAMPLES_OUTPUT_PATH}")
    print(f"[ai-candidate-pairwise-horizon-strong-refined-samples] schema: {REFINED_SCHEMA_OUTPUT_PATH}")
    print(json.dumps(coverage, ensure_ascii=False, indent=2))
    if not refined_df.empty:
        preview_columns = [
            "candidate_date",
            "pair_id",
            STRONG_SUBTYPE_COLUMN,
            STRONG_REFINED_KEEP_COLUMN,
            "label_horizon_primary_left_wins",
            "label_horizon_primary_strength_bucket",
            SAME_SIGNAL_COLUMN,
            TREND_DIFF_COLUMN,
            RET20_DIFF_COLUMN,
            "label_horizon_primary_gap_abs",
        ]
        preview_columns = [column for column in preview_columns if column in refined_df.columns]
        print(refined_df[preview_columns].head(12).to_string(index=False))


if __name__ == "__main__":
    main()
