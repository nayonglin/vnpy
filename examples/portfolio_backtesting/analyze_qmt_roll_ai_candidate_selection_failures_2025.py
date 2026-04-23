from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

DAYS_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_selection_rights_days_ranker_v2_cs.csv"
SAMPLES_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_training_samples.csv"
MODEL_SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_ranker_summary_ranker_v2_cs.json"

SUMMARY_JSON_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_selection_failures_2025_summary.json"
FAILED_DATES_CSV_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_selection_failures_2025_dates.csv"
FAILED_CASES_CSV_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_selection_failures_2025_cases.csv"
FEATURE_DIFF_CSV_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_selection_failures_2025_feature_diff.csv"

DATE_COLUMN: str = "candidate_date"

KEY_FEATURE_COLUMNS: tuple[str, ...] = (
    "feature_target_risk_to_equity",
    "feature_margin_per_contract_to_equity",
    "feature_stop_distance_pct",
    "feature_ret_20d_zscore_120",
    "feature_signal_strength_signed",
    "feature_reversal_pressure_signed",
    "feature_mid_term_momentum_signed",
    "feature_range_pct_zscore_120",
    "feature_volume_ratio_2v2",
    "feature_oi_delta_1d_pct_zscore_120",
    "feature_close_position_60d",
    "feature_target_risk_to_equity_cs_rank_centered_1d",
    "feature_margin_per_contract_to_equity_cs_zscore_1d",
    "feature_ret_20d_zscore_120_cs_zscore_1d",
    "feature_ma20_ma40_gap_pct_cs_zscore_1d",
    "feature_trend_ma20_gap_pct_cs_rank_centered_1d",
    "feature_close_position_60d_cs_zscore_1d",
)


def _parse_id_set(value: object) -> set[str]:
    if value is None:
        return set()
    text = str(value).strip()
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


def _safe_mode(series: pd.Series) -> str:
    cleaned = series.dropna().astype(str)
    if cleaned.empty:
        return ""
    mode = cleaned.mode()
    if mode.empty:
        return ""
    return str(mode.iloc[0])


def load_failed_days() -> pd.DataFrame:
    days_df = pd.read_csv(DAYS_PATH)
    days_df = days_df[days_df["window_name"] == "test_2025_plus"].copy()
    days_df = days_df[days_df["selection_changed"] == 1].copy()
    days_df = days_df[days_df["predicted_minus_actual_candidate_forward_20d_r_multiple"] < 0].copy()
    days_df[DATE_COLUMN] = pd.to_datetime(days_df[DATE_COLUMN])
    days_df.sort_values("predicted_minus_actual_candidate_forward_20d_r_multiple", inplace=True)
    days_df.reset_index(drop=True, inplace=True)
    return days_df


def load_samples() -> pd.DataFrame:
    samples_df = pd.read_csv(SAMPLES_PATH)
    samples_df[DATE_COLUMN] = pd.to_datetime(samples_df[DATE_COLUMN])
    samples_df.sort_values([DATE_COLUMN, "sample_id"], inplace=True)
    samples_df.reset_index(drop=True, inplace=True)
    return samples_df


def build_case_rows(failed_days_df: pd.DataFrame, samples_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, failed_day in failed_days_df.iterrows():
        trade_date = failed_day[DATE_COLUMN]
        day_samples = samples_df[samples_df[DATE_COLUMN] == trade_date].copy()
        actual_ids = _parse_id_set(failed_day["actual_ids"])
        predicted_ids = _parse_id_set(failed_day["predicted_ids"])
        oracle_ids = _parse_id_set(failed_day["oracle_ids"])

        for _, sample in day_samples.iterrows():
            sample_id = str(sample["sample_id"])
            rows.append(
                {
                    "candidate_date": trade_date.date().isoformat(),
                    "sample_id": sample_id,
                    "product_symbol": sample.get("product_symbol"),
                    "direction": sample.get("direction"),
                    "signal": sample.get("signal"),
                    "risk_mode": sample.get("risk_mode"),
                    "label_is_selected": int(sample.get("label_is_selected", 0) or 0),
                    "is_actual_selected": int(sample_id in actual_ids),
                    "is_predicted_selected": int(sample_id in predicted_ids),
                    "is_oracle_selected": int(sample_id in oracle_ids),
                    "predicted_minus_actual_candidate_forward_20d_r_multiple": float(
                        failed_day["predicted_minus_actual_candidate_forward_20d_r_multiple"]
                    ),
                    "predicted_minus_actual_candidate_forward_10d_r_multiple": float(
                        failed_day["predicted_minus_actual_candidate_forward_10d_r_multiple"]
                    ),
                    "label_candidate_quality_score_v2": sample.get("label_candidate_quality_score_v2"),
                    "label_candidate_forward_10d_r_multiple": sample.get("label_candidate_forward_10d_r_multiple"),
                    "label_candidate_forward_20d_r_multiple": sample.get("label_candidate_forward_20d_r_multiple"),
                    "label_candidate_20d_mfe_r": sample.get("label_candidate_20d_mfe_r"),
                    "label_candidate_20d_mae_r": sample.get("label_candidate_20d_mae_r"),
                    **{column: sample.get(column) for column in KEY_FEATURE_COLUMNS if column in sample.index},
                }
            )
    case_df = pd.DataFrame(rows)
    case_df.sort_values(
        ["predicted_minus_actual_candidate_forward_20d_r_multiple", "candidate_date", "sample_id"],
        inplace=True,
    )
    case_df.reset_index(drop=True, inplace=True)
    return case_df


def build_feature_diff(case_df: pd.DataFrame) -> pd.DataFrame:
    diff_rows: list[dict[str, Any]] = []
    grouped = case_df.groupby("candidate_date", sort=False)
    for feature in KEY_FEATURE_COLUMNS:
        if feature not in case_df.columns:
            continue
        predicted_minus_actual_values: list[float] = []
        oracle_minus_actual_values: list[float] = []
        for _, group_df in grouped:
            actual_df = group_df[group_df["is_actual_selected"] == 1]
            predicted_df = group_df[group_df["is_predicted_selected"] == 1]
            oracle_df = group_df[group_df["is_oracle_selected"] == 1]
            if actual_df.empty or predicted_df.empty:
                continue
            predicted_minus_actual_values.append(_safe_mean(predicted_df, feature) - _safe_mean(actual_df, feature))
            if not oracle_df.empty:
                oracle_minus_actual_values.append(_safe_mean(oracle_df, feature) - _safe_mean(actual_df, feature))

        if not predicted_minus_actual_values:
            continue
        diff_rows.append(
            {
                "feature": feature,
                "predicted_minus_actual_mean": float(pd.Series(predicted_minus_actual_values).mean()),
                "predicted_minus_actual_abs_mean": float(pd.Series(predicted_minus_actual_values).abs().mean()),
                "oracle_minus_actual_mean": float(pd.Series(oracle_minus_actual_values).mean())
                if oracle_minus_actual_values
                else 0.0,
                "sample_count": int(len(predicted_minus_actual_values)),
            }
        )

    diff_df = pd.DataFrame(diff_rows)
    diff_df.sort_values("predicted_minus_actual_abs_mean", ascending=False, inplace=True)
    diff_df.reset_index(drop=True, inplace=True)
    return diff_df


def build_summary(
    failed_days_df: pd.DataFrame,
    case_df: pd.DataFrame,
    feature_diff_df: pd.DataFrame,
    model_summary: dict[str, Any],
) -> dict[str, Any]:
    actual_selected_df = case_df[case_df["is_actual_selected"] == 1].copy()
    predicted_selected_df = case_df[case_df["is_predicted_selected"] == 1].copy()
    oracle_selected_df = case_df[case_df["is_oracle_selected"] == 1].copy()

    top_feature_list = [row["feature"] for row in model_summary.get("top_features", [])[:10]]

    summary: dict[str, Any] = {
        "focus_window": "test_2025_plus",
        "failure_filter": {
            "selection_changed": 1,
            "predicted_minus_actual_candidate_forward_20d_r_multiple": "< 0",
        },
        "failed_day_count": int(len(failed_days_df)),
        "failed_dates": [dt.date().isoformat() for dt in failed_days_df[DATE_COLUMN].tolist()],
        "mean_predicted_minus_actual_10d_r": float(
            failed_days_df["predicted_minus_actual_candidate_forward_10d_r_multiple"].mean()
        )
        if not failed_days_df.empty
        else 0.0,
        "mean_predicted_minus_actual_20d_r": float(
            failed_days_df["predicted_minus_actual_candidate_forward_20d_r_multiple"].mean()
        )
        if not failed_days_df.empty
        else 0.0,
        "actual_selected_profile": {
            "quality_score_v2": _safe_mean(actual_selected_df, "label_candidate_quality_score_v2"),
            "forward_10d_r": _safe_mean(actual_selected_df, "label_candidate_forward_10d_r_multiple"),
            "forward_20d_r": _safe_mean(actual_selected_df, "label_candidate_forward_20d_r_multiple"),
            "mfe_20d_r": _safe_mean(actual_selected_df, "label_candidate_20d_mfe_r"),
            "mae_20d_r": _safe_mean(actual_selected_df, "label_candidate_20d_mae_r"),
            "top_direction": _safe_mode(actual_selected_df["direction"]) if "direction" in actual_selected_df else "",
            "top_signal": _safe_mode(actual_selected_df["signal"]) if "signal" in actual_selected_df else "",
        },
        "predicted_selected_profile": {
            "quality_score_v2": _safe_mean(predicted_selected_df, "label_candidate_quality_score_v2"),
            "forward_10d_r": _safe_mean(predicted_selected_df, "label_candidate_forward_10d_r_multiple"),
            "forward_20d_r": _safe_mean(predicted_selected_df, "label_candidate_forward_20d_r_multiple"),
            "mfe_20d_r": _safe_mean(predicted_selected_df, "label_candidate_20d_mfe_r"),
            "mae_20d_r": _safe_mean(predicted_selected_df, "label_candidate_20d_mae_r"),
            "top_direction": _safe_mode(predicted_selected_df["direction"]) if "direction" in predicted_selected_df else "",
            "top_signal": _safe_mode(predicted_selected_df["signal"]) if "signal" in predicted_selected_df else "",
        },
        "oracle_selected_profile": {
            "quality_score_v2": _safe_mean(oracle_selected_df, "label_candidate_quality_score_v2"),
            "forward_10d_r": _safe_mean(oracle_selected_df, "label_candidate_forward_10d_r_multiple"),
            "forward_20d_r": _safe_mean(oracle_selected_df, "label_candidate_forward_20d_r_multiple"),
            "mfe_20d_r": _safe_mean(oracle_selected_df, "label_candidate_20d_mfe_r"),
            "mae_20d_r": _safe_mean(oracle_selected_df, "label_candidate_20d_mae_r"),
            "top_direction": _safe_mode(oracle_selected_df["direction"]) if "direction" in oracle_selected_df else "",
            "top_signal": _safe_mode(oracle_selected_df["signal"]) if "signal" in oracle_selected_df else "",
        },
        "model_top_features_reference": top_feature_list,
        "largest_feature_drifts_predicted_minus_actual": feature_diff_df.head(12).to_dict(orient="records"),
        "worst_failed_dates": failed_days_df.head(8).assign(
            candidate_date=failed_days_df[DATE_COLUMN].dt.date.astype(str)
        ).to_dict(orient="records"),
    }
    return summary


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    failed_days_df = load_failed_days()
    samples_df = load_samples()
    case_df = build_case_rows(failed_days_df, samples_df)
    feature_diff_df = build_feature_diff(case_df)
    model_summary = json.loads(MODEL_SUMMARY_PATH.read_text(encoding="utf-8"))
    summary = build_summary(failed_days_df, case_df, feature_diff_df, model_summary)

    failed_days_export = failed_days_df.copy()
    failed_days_export[DATE_COLUMN] = failed_days_export[DATE_COLUMN].dt.date.astype(str)
    failed_days_export.to_csv(FAILED_DATES_CSV_PATH, index=False, encoding="utf-8-sig")
    case_df.to_csv(FAILED_CASES_CSV_PATH, index=False, encoding="utf-8-sig")
    feature_diff_df.to_csv(FEATURE_DIFF_CSV_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[selection-failures-2025] summary: {SUMMARY_JSON_PATH}")
    print(f"[selection-failures-2025] failed dates: {FAILED_DATES_CSV_PATH}")
    print(f"[selection-failures-2025] failed cases: {FAILED_CASES_CSV_PATH}")
    print(f"[selection-failures-2025] feature diff: {FEATURE_DIFF_CSV_PATH}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
