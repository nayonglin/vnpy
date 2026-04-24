from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

DAYS_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_selection_rights_days_selection_pairwise_v2_risk_weighted.csv"
SAMPLES_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_training_samples.csv"

SUMMARY_JSON_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_selection_pairwise_v2_tail_risk_summary.json"
TAIL_DATES_CSV_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_selection_pairwise_v2_tail_risk_dates.csv"
TAIL_CASES_CSV_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_selection_pairwise_v2_tail_risk_cases.csv"
FEATURE_DIFF_CSV_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_selection_pairwise_v2_tail_risk_feature_diff.csv"

DATE_COLUMN: str = "candidate_date"

KEY_FEATURE_COLUMNS: tuple[str, ...] = (
    "feature_range_pct_zscore_120",
    "feature_ret_20d_zscore_120",
    "feature_volume_ratio_2v2",
    "feature_oi_delta_1d_pct_zscore_120",
    "feature_close_position_60d",
    "feature_trend_ma20_gap_pct_cs_rank_centered_1d",
    "feature_ma20_ma40_gap_pct_cs_zscore_1d",
    "feature_close_position_60d_cs_zscore_1d",
)


def _parse_id_set(value: object) -> set[str]:
    text = str(value or "").strip()
    if not text:
        return set()
    return {item for item in text.split("|") if item}


def _safe_mean(df: pd.DataFrame, column: str) -> float:
    if column not in df.columns or df.empty:
        return 0.0
    series = pd.to_numeric(df[column], errors="coerce").dropna()
    if series.empty:
        return 0.0
    return float(series.mean())


def load_tail_days() -> pd.DataFrame:
    days_df = pd.read_csv(DAYS_PATH)
    days_df = days_df[days_df["window_name"] == "test_2024_plus"].copy()
    days_df = days_df[days_df["selection_changed"] == 1].copy()
    days_df = days_df[days_df["predicted_minus_actual_candidate_20d_mae_r"] > 0].copy()
    days_df[DATE_COLUMN] = pd.to_datetime(days_df[DATE_COLUMN])

    days_df["tail_risk_type"] = "aggressive_alpha"
    days_df.loc[
        days_df["predicted_minus_actual_candidate_forward_20d_r_multiple"] <= 0,
        "tail_risk_type",
    ] = "catastrophic_tail"
    days_df.sort_values(
        ["tail_risk_type", "predicted_minus_actual_candidate_20d_mae_r"],
        ascending=[True, False],
        inplace=True,
    )
    days_df.reset_index(drop=True, inplace=True)
    return days_df


def load_samples() -> pd.DataFrame:
    samples_df = pd.read_csv(SAMPLES_PATH)
    samples_df[DATE_COLUMN] = pd.to_datetime(samples_df[DATE_COLUMN])
    samples_df.sort_values([DATE_COLUMN, "sample_id"], inplace=True)
    samples_df.reset_index(drop=True, inplace=True)
    return samples_df


def build_case_rows(tail_days_df: pd.DataFrame, samples_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, tail_day in tail_days_df.iterrows():
        trade_date = tail_day[DATE_COLUMN]
        day_samples = samples_df[samples_df[DATE_COLUMN] == trade_date].copy()
        actual_ids = _parse_id_set(tail_day["actual_ids"])
        predicted_ids = _parse_id_set(tail_day["predicted_ids"])
        oracle_ids = _parse_id_set(tail_day["oracle_ids"])

        for _, sample in day_samples.iterrows():
            sample_id = str(sample["sample_id"])
            rows.append(
                {
                    "window_name": tail_day["window_name"],
                    "tail_risk_type": tail_day["tail_risk_type"],
                    "candidate_date": trade_date.date().isoformat(),
                    "sample_id": sample_id,
                    "product_symbol": sample.get("product_symbol"),
                    "direction": sample.get("direction"),
                    "signal": sample.get("signal"),
                    "risk_mode": sample.get("risk_mode"),
                    "is_actual_selected": int(sample_id in actual_ids),
                    "is_predicted_selected": int(sample_id in predicted_ids),
                    "is_oracle_selected": int(sample_id in oracle_ids),
                    "predicted_minus_actual_candidate_forward_20d_r_multiple": float(
                        tail_day["predicted_minus_actual_candidate_forward_20d_r_multiple"]
                    ),
                    "predicted_minus_actual_candidate_20d_mae_r": float(
                        tail_day["predicted_minus_actual_candidate_20d_mae_r"]
                    ),
                    "label_candidate_forward_20d_r_multiple": sample.get("label_candidate_forward_20d_r_multiple"),
                    "label_candidate_20d_mae_r": sample.get("label_candidate_20d_mae_r"),
                    "label_candidate_20d_mfe_r": sample.get("label_candidate_20d_mfe_r"),
                    **{column: sample.get(column) for column in KEY_FEATURE_COLUMNS if column in sample.index},
                }
            )
    case_df = pd.DataFrame(rows)
    case_df.sort_values(["tail_risk_type", "candidate_date", "sample_id"], inplace=True)
    case_df.reset_index(drop=True, inplace=True)
    return case_df


def build_feature_diff(case_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for tail_risk_type, type_df in case_df.groupby("tail_risk_type", sort=False):
        grouped = type_df.groupby("candidate_date", sort=False)
        for feature in KEY_FEATURE_COLUMNS:
            predicted_minus_actual_values: list[float] = []
            for _, group_df in grouped:
                actual_df = group_df[group_df["is_actual_selected"] == 1]
                predicted_df = group_df[group_df["is_predicted_selected"] == 1]
                if actual_df.empty or predicted_df.empty:
                    continue
                predicted_minus_actual_values.append(_safe_mean(predicted_df, feature) - _safe_mean(actual_df, feature))

            if not predicted_minus_actual_values:
                continue
            rows.append(
                {
                    "tail_risk_type": tail_risk_type,
                    "feature": feature,
                    "predicted_minus_actual_mean": float(pd.Series(predicted_minus_actual_values).mean()),
                    "predicted_minus_actual_abs_mean": float(pd.Series(predicted_minus_actual_values).abs().mean()),
                    "sample_count": int(len(predicted_minus_actual_values)),
                }
            )

    feature_diff_df = pd.DataFrame(rows)
    feature_diff_df.sort_values(["tail_risk_type", "predicted_minus_actual_abs_mean"], ascending=[True, False], inplace=True)
    feature_diff_df.reset_index(drop=True, inplace=True)
    return feature_diff_df


def build_summary(tail_days_df: pd.DataFrame, case_df: pd.DataFrame, feature_diff_df: pd.DataFrame) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "focus": "pairwise_v2 残余 MAE 尾部风险分型",
        "tail_day_count": int(len(tail_days_df)),
        "tail_risk_type_counts": tail_days_df["tail_risk_type"].value_counts().sort_index().to_dict(),
        "dates": tail_days_df.assign(candidate_date=tail_days_df[DATE_COLUMN].dt.date.astype(str)).to_dict(orient="records"),
        "type_summary": {},
    }

    for tail_risk_type, type_df in tail_days_df.groupby("tail_risk_type", sort=False):
        case_type_df = case_df[case_df["tail_risk_type"] == tail_risk_type].copy()
        actual_selected_df = case_type_df[case_type_df["is_actual_selected"] == 1].copy()
        predicted_selected_df = case_type_df[case_type_df["is_predicted_selected"] == 1].copy()
        summary["type_summary"][tail_risk_type] = {
            "day_count": int(len(type_df)),
            "mean_predicted_minus_actual_20d_r": float(
                type_df["predicted_minus_actual_candidate_forward_20d_r_multiple"].mean()
            ),
            "mean_predicted_minus_actual_20d_mae_r": float(type_df["predicted_minus_actual_candidate_20d_mae_r"].mean()),
            "actual_selected_profile": {
                "forward_20d_r": _safe_mean(actual_selected_df, "label_candidate_forward_20d_r_multiple"),
                "mae_20d_r": _safe_mean(actual_selected_df, "label_candidate_20d_mae_r"),
                "mfe_20d_r": _safe_mean(actual_selected_df, "label_candidate_20d_mfe_r"),
            },
            "predicted_selected_profile": {
                "forward_20d_r": _safe_mean(predicted_selected_df, "label_candidate_forward_20d_r_multiple"),
                "mae_20d_r": _safe_mean(predicted_selected_df, "label_candidate_20d_mae_r"),
                "mfe_20d_r": _safe_mean(predicted_selected_df, "label_candidate_20d_mfe_r"),
            },
            "largest_feature_drifts": feature_diff_df[feature_diff_df["tail_risk_type"] == tail_risk_type]
            .head(10)
            .to_dict(orient="records"),
        }

    return summary


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tail_days_df = load_tail_days()
    samples_df = load_samples()
    case_df = build_case_rows(tail_days_df, samples_df)
    feature_diff_df = build_feature_diff(case_df)
    summary = build_summary(tail_days_df, case_df, feature_diff_df)

    export_days_df = tail_days_df.copy()
    export_days_df[DATE_COLUMN] = export_days_df[DATE_COLUMN].dt.date.astype(str)
    export_days_df.to_csv(TAIL_DATES_CSV_PATH, index=False, encoding="utf-8-sig")
    case_df.to_csv(TAIL_CASES_CSV_PATH, index=False, encoding="utf-8-sig")
    feature_diff_df.to_csv(FEATURE_DIFF_CSV_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[selection-pairwise-v2-tail-risk] summary: {SUMMARY_JSON_PATH}")
    print(f"[selection-pairwise-v2-tail-risk] dates: {TAIL_DATES_CSV_PATH}")
    print(f"[selection-pairwise-v2-tail-risk] cases: {TAIL_CASES_CSV_PATH}")
    print(f"[selection-pairwise-v2-tail-risk] feature diff: {FEATURE_DIFF_CSV_PATH}")
    print(json.dumps(summary["tail_risk_type_counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
