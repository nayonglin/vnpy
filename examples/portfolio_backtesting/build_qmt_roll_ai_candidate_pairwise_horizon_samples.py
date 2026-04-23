from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

SOURCE_SAMPLES_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_training_samples.csv"
PAIRWISE_SAMPLES_OUTPUT_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_pairwise_horizon_samples.csv"
PAIRWISE_SCHEMA_OUTPUT_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_pairwise_horizon_schema.json"

PRIMARY_HORIZON_WINDOWS: tuple[int, int] = (10, 20)
AUXILIARY_HORIZON_WINDOW: int = 5
PRIMARY_MIN_HORIZON_GAP: float = 0.5
PRIMARY_WEIGHT_CAP: float = 3.0

PAIR_CONTEXT_NUMERIC_COLUMNS: tuple[str, ...] = (
    "risk_ratio",
    "risk_multiplier",
    "loss_streak",
    "active_positions_before",
    "max_concurrent_positions",
    "remaining_position_slots",
)

PAIR_CONTEXT_CATEGORICAL_COLUMNS: tuple[str, ...] = (
    "product_symbol",
    "exchange",
    "direction",
    "signal",
    "risk_mode",
    "selection_stage",
    "entry_context",
)


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result):
        return default
    return result


def _canonicalize_pair(
    left_row: dict[str, Any],
    right_row: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    left_key = (int(_safe_float(left_row.get("candidate_index"))), str(left_row.get("sample_id", "")))
    right_key = (int(_safe_float(right_row.get("candidate_index"))), str(right_row.get("sample_id", "")))
    if left_key <= right_key:
        return left_row, right_row
    return right_row, left_row


def _compare_pair(left_value: float, right_value: float) -> int:
    if left_value > right_value:
        return 1
    if left_value < right_value:
        return 0
    return -1


def _pair_strength_bucket(primary_gap: float) -> str:
    if primary_gap >= 3.0:
        return "strong"
    if primary_gap >= 1.5:
        return "medium"
    return "weak"


def load_candidate_samples() -> pd.DataFrame:
    df = pd.read_csv(SOURCE_SAMPLES_PATH)
    df["candidate_date"] = pd.to_datetime(df["candidate_date"])
    df.sort_values(["candidate_date", "candidate_index", "sample_id"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def build_pair_feature_columns(df: pd.DataFrame) -> tuple[list[str], list[str], list[str]]:
    context_numeric_columns = [
        column
        for column in PAIR_CONTEXT_NUMERIC_COLUMNS
        if column in df.columns and pd.api.types.is_numeric_dtype(df[column])
    ]
    feature_numeric_columns = [
        column
        for column in df.columns
        if column.startswith("feature_") and pd.api.types.is_numeric_dtype(df[column])
    ]
    categorical_columns = [column for column in PAIR_CONTEXT_CATEGORICAL_COLUMNS if column in df.columns]
    return context_numeric_columns, sorted(feature_numeric_columns), categorical_columns


def build_pairwise_samples() -> tuple[pd.DataFrame, dict[str, Any]]:
    samples_df = load_candidate_samples()
    context_numeric_columns, feature_numeric_columns, categorical_columns = build_pair_feature_columns(samples_df)

    pair_rows: list[dict[str, Any]] = []
    raw_pair_rows = 0
    dropped_non_confirmed_rows = 0
    dropped_small_gap_rows = 0

    for candidate_date, group_df in samples_df.groupby("candidate_date", sort=True):
        if len(group_df) < 2:
            continue

        group_records = group_df.to_dict("records")
        for first_row, second_row in combinations(group_records, 2):
            raw_pair_rows += 1
            left_row, right_row = _canonicalize_pair(first_row, second_row)

            left_selected = int(_safe_float(left_row.get("label_is_selected")))
            right_selected = int(_safe_float(right_row.get("label_is_selected")))

            left_5d = _safe_float(left_row.get("label_candidate_forward_5d_r_multiple"))
            right_5d = _safe_float(right_row.get("label_candidate_forward_5d_r_multiple"))
            left_10d = _safe_float(left_row.get("label_candidate_forward_10d_r_multiple"))
            right_10d = _safe_float(right_row.get("label_candidate_forward_10d_r_multiple"))
            left_20d = _safe_float(left_row.get("label_candidate_forward_20d_r_multiple"))
            right_20d = _safe_float(right_row.get("label_candidate_forward_20d_r_multiple"))

            winner_5d = _compare_pair(left_5d, right_5d)
            winner_10d = _compare_pair(left_10d, right_10d)
            winner_20d = _compare_pair(left_20d, right_20d)

            gap_5d = abs(left_5d - right_5d)
            gap_10d = abs(left_10d - right_10d)
            gap_20d = abs(left_20d - right_20d)
            primary_gap = min(gap_10d, gap_20d)

            agreement_10d_20d = int(winner_10d != -1 and winner_20d != -1 and winner_10d == winner_20d)
            support_5d = int(winner_5d != -1 and winner_5d == winner_10d)

            if not agreement_10d_20d:
                dropped_non_confirmed_rows += 1
                continue
            if primary_gap < PRIMARY_MIN_HORIZON_GAP:
                dropped_small_gap_rows += 1
                continue

            primary_left_wins = winner_10d
            winner_row = left_row if primary_left_wins else right_row
            loser_row = right_row if primary_left_wins else left_row

            pair_row: dict[str, Any] = {
                "pair_id": (
                    f"{candidate_date.date().isoformat()}__"
                    f"{left_row.get('sample_id', '')}__vs__{right_row.get('sample_id', '')}"
                ),
                "candidate_date": candidate_date.date().isoformat(),
                "pair_group_size_1d": int(len(group_df)),
                "left_sample_id": str(left_row.get("sample_id", "")),
                "right_sample_id": str(right_row.get("sample_id", "")),
                "left_candidate_index": int(_safe_float(left_row.get("candidate_index"))),
                "right_candidate_index": int(_safe_float(right_row.get("candidate_index"))),
                "left_contract_vt_symbol": str(left_row.get("contract_vt_symbol", "")),
                "right_contract_vt_symbol": str(right_row.get("contract_vt_symbol", "")),
                "winner_sample_id": str(winner_row.get("sample_id", "")),
                "loser_sample_id": str(loser_row.get("sample_id", "")),
                "winner_contract_vt_symbol": str(winner_row.get("contract_vt_symbol", "")),
                "loser_contract_vt_symbol": str(loser_row.get("contract_vt_symbol", "")),
                "left_candidate_status": str(left_row.get("candidate_status", "")),
                "right_candidate_status": str(right_row.get("candidate_status", "")),
                "feature_pair_same_direction": int(left_row.get("direction", "") == right_row.get("direction", "")),
                "feature_pair_same_signal": int(left_row.get("signal", "") == right_row.get("signal", "")),
                "feature_pair_same_risk_mode": int(left_row.get("risk_mode", "") == right_row.get("risk_mode", "")),
                "feature_pair_same_product": int(left_row.get("product_symbol", "") == right_row.get("product_symbol", "")),
                "label_horizon_5d_left_wins": winner_5d,
                "label_horizon_10d_left_wins": winner_10d,
                "label_horizon_20d_left_wins": winner_20d,
                "label_horizon_primary_left_wins": primary_left_wins,
                "label_horizon_primary_right_wins": 1 - primary_left_wins,
                "label_horizon_10d_20d_agree": agreement_10d_20d,
                "label_horizon_5d_support_primary": support_5d,
                "label_left_selected": left_selected,
                "label_right_selected": right_selected,
                "label_winner_selected": int(_safe_float(winner_row.get("label_is_selected"))),
                "label_loser_selected": int(_safe_float(loser_row.get("label_is_selected"))),
                "label_one_selected": int(left_selected + right_selected == 1),
                "label_both_selected": int(left_selected + right_selected == 2),
                "label_neither_selected": int(left_selected + right_selected == 0),
                "label_horizon_5d_gap_abs": gap_5d,
                "label_horizon_10d_gap_abs": gap_10d,
                "label_horizon_20d_gap_abs": gap_20d,
                "label_horizon_primary_gap_abs": primary_gap,
                "label_horizon_primary_weight": min(primary_gap / PRIMARY_WEIGHT_CAP, 1.0),
                "label_horizon_primary_strength_bucket": _pair_strength_bucket(primary_gap),
            }

            for column in categorical_columns:
                left_value = str(left_row.get(column, ""))
                right_value = str(right_row.get(column, ""))
                pair_row[f"left_{column}"] = left_value
                pair_row[f"right_{column}"] = right_value
                pair_row[f"pair_same_{column}"] = int(left_value == right_value)

            for column in context_numeric_columns:
                left_value = _safe_float(left_row.get(column))
                right_value = _safe_float(right_row.get(column))
                pair_row[f"left_{column}"] = left_value
                pair_row[f"right_{column}"] = right_value
                pair_row[f"delta_{column}"] = left_value - right_value

            for column in feature_numeric_columns:
                left_value = _safe_float(left_row.get(column))
                right_value = _safe_float(right_row.get(column))
                pair_row[f"delta_{column}"] = left_value - right_value
                pair_row[f"abs_delta_{column}"] = abs(left_value - right_value)

            pair_rows.append(pair_row)

    pairwise_df = pd.DataFrame(pair_rows)
    if not pairwise_df.empty:
        pairwise_df.sort_values(["candidate_date", "left_candidate_index", "right_candidate_index"], inplace=True)
        pairwise_df.reset_index(drop=True, inplace=True)

    source_group_sizes = samples_df.groupby("candidate_date").size()
    coverage = {
        "source_candidate_rows": int(len(samples_df)),
        "source_candidate_days": int(source_group_sizes.shape[0]),
        "source_days_ge_2_candidates": int((source_group_sizes >= 2).sum()),
        "source_days_ge_3_candidates": int((source_group_sizes >= 3).sum()),
        "raw_pair_rows": int(raw_pair_rows),
        "dropped_non_confirmed_rows": int(dropped_non_confirmed_rows),
        "dropped_small_gap_rows": int(dropped_small_gap_rows),
        "pair_rows": int(len(pairwise_df)),
        "primary_horizon_windows": list(PRIMARY_HORIZON_WINDOWS),
        "auxiliary_horizon_window": AUXILIARY_HORIZON_WINDOW,
        "primary_min_horizon_gap": PRIMARY_MIN_HORIZON_GAP,
        "primary_weight_cap": PRIMARY_WEIGHT_CAP,
    }
    if not pairwise_df.empty:
        coverage.update(
            {
                "primary_left_win_rate": _safe_float(pairwise_df["label_horizon_primary_left_wins"].mean()),
                "winner_selected_rate": _safe_float(pairwise_df["label_winner_selected"].mean()),
                "same_direction_rate": _safe_float(pairwise_df["feature_pair_same_direction"].mean()),
                "primary_support_5d_rate": _safe_float(pairwise_df["label_horizon_5d_support_primary"].mean()),
                "median_primary_gap_abs": _safe_float(pairwise_df["label_horizon_primary_gap_abs"].median()),
                "mean_primary_gap_abs": _safe_float(pairwise_df["label_horizon_primary_gap_abs"].mean()),
                "strength_bucket_distribution": (
                    pairwise_df["label_horizon_primary_strength_bucket"].value_counts().sort_index().to_dict()
                ),
            }
        )
    return pairwise_df, coverage


def build_schema(pairwise_df: pd.DataFrame, coverage: dict[str, Any]) -> dict[str, Any]:
    categorical_columns = [
        column
        for column in pairwise_df.columns
        if pd.api.types.is_object_dtype(pairwise_df[column])
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
        for column in pairwise_df.columns
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
        "dataset_name": "qmt_roll_ai_candidate_pairwise_horizon_samples",
        "source_dataset": str(SOURCE_SAMPLES_PATH.name),
        "row_definition": "每一行对应同一交易日内两个候选的 horizon 胜负样本，主标签要求 10d 与 20d 结果同向确认。",
        "pair_construction_rules": {
            "group_key": "candidate_date",
            "primary_horizon_windows": list(PRIMARY_HORIZON_WINDOWS),
            "auxiliary_horizon_window": AUXILIARY_HORIZON_WINDOW,
            "canonical_order": "按 candidate_index、sample_id 升序固定 left/right，避免镜像重复样本。",
            "primary_filter": (
                "仅保留 10d 与 20d left/right 胜负方向一致，且 min(|10d gap|, |20d gap|) "
                f">= {PRIMARY_MIN_HORIZON_GAP:.2f} 的 pair。"
            ),
            "primary_weight": f"label_horizon_primary_weight = min(label_horizon_primary_gap_abs / {PRIMARY_WEIGHT_CAP:.1f}, 1.0)",
        },
        "target_recommendation": {
            "primary_binary_label": "label_horizon_primary_left_wins",
            "primary_margin_label": "label_horizon_primary_gap_abs",
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
            "这份数据集不再以 quality_score 聚合值定义胜负，而是用显式 horizon 结果构造监督。",
            "主标签要求 10d 与 20d 同向，目的是抑制 5d 短噪声与单一终点偶然性。",
            "5d 仅作为辅助一致性标签，不再作为主监督来源。",
            "delta_feature_* 体现 left 相对 right 的差异，abs_delta_feature_* 体现差异强度。",
            "若这版仍然样本外失效，下一步应继续重构候选定义而不是继续换模型。",
        ],
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pairwise_df, coverage = build_pairwise_samples()
    pairwise_df.to_csv(PAIRWISE_SAMPLES_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    schema = build_schema(pairwise_df, coverage)
    PAIRWISE_SCHEMA_OUTPUT_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[ai-candidate-pairwise-horizon-samples] rows: {len(pairwise_df)}")
    print(f"[ai-candidate-pairwise-horizon-samples] csv: {PAIRWISE_SAMPLES_OUTPUT_PATH}")
    print(f"[ai-candidate-pairwise-horizon-samples] schema: {PAIRWISE_SCHEMA_OUTPUT_PATH}")
    print(json.dumps(coverage, ensure_ascii=False, indent=2))
    if not pairwise_df.empty:
        preview_columns = [
            "candidate_date",
            "left_sample_id",
            "right_sample_id",
            "left_product_symbol",
            "right_product_symbol",
            "label_horizon_primary_left_wins",
            "label_horizon_5d_support_primary",
            "label_horizon_primary_gap_abs",
            "label_horizon_primary_strength_bucket",
        ]
        preview_columns = [column for column in preview_columns if column in pairwise_df.columns]
        print(pairwise_df[preview_columns].head(12).to_string(index=False))


if __name__ == "__main__":
    main()
