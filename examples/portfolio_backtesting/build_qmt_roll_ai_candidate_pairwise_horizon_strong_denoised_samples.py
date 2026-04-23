from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

SOURCE_SAMPLES_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_pairwise_horizon_samples.csv"
DENOISED_SAMPLES_OUTPUT_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_pairwise_horizon_strong_denoised_samples.csv"
DENOISED_SCHEMA_OUTPUT_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_pairwise_horizon_strong_denoised_schema.json"

STRENGTH_COLUMN: str = "label_horizon_primary_strength_bucket"
OI_NOISE_COLUMN: str = "abs_delta_feature_oi_delta_1d_pct_zscore_120"
STRONG_BUCKET_NAME: str = "strong"
STRONG_OI_NOISE_THRESHOLD: float = 2.0


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


def build_denoised_samples() -> tuple[pd.DataFrame, dict[str, Any]]:
    source_df = load_samples()
    strong_mask = source_df[STRENGTH_COLUMN].eq(STRONG_BUCKET_NAME)
    strong_noise_mask = strong_mask & (source_df[OI_NOISE_COLUMN].astype("float64") > STRONG_OI_NOISE_THRESHOLD)

    denoised_df = source_df.loc[~strong_noise_mask].copy()
    denoised_df.reset_index(drop=True, inplace=True)

    source_split = pd.Series("train", index=source_df.index, dtype="object")
    source_split.loc[source_df["candidate_date"] >= pd.Timestamp("2023-01-01")] = "valid"
    source_split.loc[source_df["candidate_date"] >= pd.Timestamp("2024-01-01")] = "test"

    dropped_df = source_df.loc[strong_noise_mask].copy()
    dropped_df["dataset_split"] = source_split.loc[dropped_df.index]
    kept_strong_df = denoised_df.loc[denoised_df[STRENGTH_COLUMN].eq(STRONG_BUCKET_NAME)].copy()

    coverage = {
        "source_rows": int(len(source_df)),
        "source_days": int(source_df["candidate_date"].nunique()),
        "strong_rows_before": int(strong_mask.sum()),
        "strong_noise_threshold_column": OI_NOISE_COLUMN,
        "strong_noise_threshold": STRONG_OI_NOISE_THRESHOLD,
        "dropped_strong_noise_rows": int(strong_noise_mask.sum()),
        "kept_rows": int(len(denoised_df)),
        "kept_days": int(denoised_df["candidate_date"].nunique()),
        "strong_rows_after": int(kept_strong_df.shape[0]),
    }

    if not dropped_df.empty:
        coverage.update(
            {
                "dropped_split_distribution": dropped_df["dataset_split"].value_counts().sort_index().to_dict(),
                "dropped_left_win_rate": _safe_float(dropped_df["label_horizon_primary_left_wins"].mean()),
                "dropped_mean_primary_gap_abs": _safe_float(dropped_df["label_horizon_primary_gap_abs"].mean()),
                "dropped_mean_oi_noise": _safe_float(dropped_df[OI_NOISE_COLUMN].mean()),
            }
        )

    if not denoised_df.empty:
        coverage.update(
            {
                "kept_left_win_rate": _safe_float(denoised_df["label_horizon_primary_left_wins"].mean()),
                "kept_winner_selected_rate": _safe_float(denoised_df["label_winner_selected"].mean()),
                "kept_strength_distribution": denoised_df[STRENGTH_COLUMN].value_counts().sort_index().to_dict(),
            }
        )

    return denoised_df, coverage


def build_schema(denoised_df: pd.DataFrame, coverage: dict[str, Any]) -> dict[str, Any]:
    categorical_columns = [
        column
        for column in denoised_df.columns
        if pd.api.types.is_object_dtype(denoised_df[column])
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
        for column in denoised_df.columns
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
        "dataset_name": "qmt_roll_ai_candidate_pairwise_horizon_strong_denoised_samples",
        "source_dataset": str(SOURCE_SAMPLES_PATH.name),
        "row_definition": "在第九阶段 horizon pair 样本基础上，只对 strong 组执行极端 OI 冲击去噪后的样本。",
        "strong_denoise_rules": {
            "target_bucket": STRONG_BUCKET_NAME,
            "noise_column": OI_NOISE_COLUMN,
            "drop_condition": f"{STRENGTH_COLUMN} == '{STRONG_BUCKET_NAME}' and {OI_NOISE_COLUMN} > {STRONG_OI_NOISE_THRESHOLD:.1f}",
            "motivation": "极端 strong pair 中，OI 横截面冲击过大更像挤仓/异动噪声，而不是可穿越周期的稳定胜负信号。",
        },
        "target_recommendation": {
            "primary_binary_label": "label_horizon_primary_left_wins",
            "sample_weight_column": "label_horizon_primary_weight",
            "analysis_labels": [
                "label_horizon_5d_support_primary",
                "label_winner_selected",
                "label_horizon_primary_strength_bucket",
            ],
        },
        "coverage_summary": coverage,
        "categorical_columns": categorical_columns,
        "numeric_columns": numeric_columns,
        "notes": [
            "这一步不是全局裁样本，而是只对 strong 组做结构化去噪。",
            "medium 组在第九阶段已出现正向信号，因此不应一起被误伤。",
            "若 strong 去噪后整体表现仍无法稳定转正，下一步更应前移候选定义，而不是继续修剪 pair 尾部。",
        ],
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    denoised_df, coverage = build_denoised_samples()
    denoised_df.to_csv(DENOISED_SAMPLES_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    schema = build_schema(denoised_df, coverage)
    DENOISED_SCHEMA_OUTPUT_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[ai-candidate-pairwise-horizon-strong-denoised-samples] rows: {len(denoised_df)}")
    print(f"[ai-candidate-pairwise-horizon-strong-denoised-samples] csv: {DENOISED_SAMPLES_OUTPUT_PATH}")
    print(f"[ai-candidate-pairwise-horizon-strong-denoised-samples] schema: {DENOISED_SCHEMA_OUTPUT_PATH}")
    print(json.dumps(coverage, ensure_ascii=False, indent=2))
    if not denoised_df.empty:
        preview_columns = [
            "candidate_date",
            "pair_id",
            "label_horizon_primary_left_wins",
            "label_horizon_primary_strength_bucket",
            OI_NOISE_COLUMN,
            "label_horizon_primary_gap_abs",
        ]
        preview_columns = [column for column in preview_columns if column in denoised_df.columns]
        print(denoised_df[preview_columns].head(12).to_string(index=False))


if __name__ == "__main__":
    main()
