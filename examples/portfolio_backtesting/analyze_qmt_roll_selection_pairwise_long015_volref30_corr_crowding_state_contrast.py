from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

FORWARD_PREFIX: str = "qmt_roll_selection_pairwise_long015_volref30_corr_crowding_forward_paths"
OUTPUT_PREFIX: str = "qmt_roll_selection_pairwise_long015_volref30_corr_crowding_state_contrast"

EVENT_PATHS_PATH: Path = OUTPUT_DIR / f"{FORWARD_PREFIX}_event_paths.csv"
DATE_PATHS_PATH: Path = OUTPUT_DIR / f"{FORWARD_PREFIX}_date_paths.csv"
DAILY_ATTRIBUTION_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_long015_volref30_corr_crowding_attribution_daily_attribution.csv"

DATE_STATE_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_date_state.csv"
FEATURE_DIFF_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_diff_positive_vs_negative.csv"
STRONG_FEATURE_DIFF_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_diff_strong_positive_vs_negative.csv"
YEAR_SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_summary.csv"
PERIOD_SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_period_summary.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary.json"

OUTCOME_METRIC: str = "fwd20d_delta_net_pnl_after_event"
PRE_WINDOWS: tuple[int, ...] = (5, 20, 60)

EVENT_NUMERIC_COLUMNS: tuple[str, ...] = (
    "selected_volume",
    "selected_volume_ungated",
    "volume_cut",
    "cut_ratio",
    "same_direction_correlation_gate_weight",
    "same_direction_correlation_max_corr",
    "same_direction_correlation_avg_corr",
    "same_direction_correlation_active_count",
    "same_direction_correlation_corr_count",
    "selection_pairwise_score",
    "selection_pairwise_rank",
    "selection_pairwise_feature_ret_20d_zscore_120",
    "selection_pairwise_feature_close_position_60d_cs_zscore_1d",
    "selection_pairwise_feature_range_pct_zscore_120",
    "selection_pairwise_volume_tilt_multiplier",
    "selection_pairwise_volume_tilt_group_size",
    "selection_pairwise_volume_tilt_score_gap",
    "selection_pairwise_volume_tilt_top_gap",
    "active_positions_before",
    "remaining_position_slots",
    "bullish_alignment",
    "bearish_alignment",
    "breakout",
    "rsi_value",
    "margin_ratio",
    "projected_total_margin_after",
    "portfolio_drawdown_pct",
    "loss_streak",
)

CONTRAST_FEATURES: tuple[str, ...] = (
    "event_count",
    "product_count",
    "long_event_count",
    "short_event_count",
    "selected_volume_ungated",
    "volume_cut",
    "avg_cut_ratio",
    "avg_gate_weight",
    "min_gate_weight",
    "avg_max_corr",
    "max_corr",
    "avg_active_count",
    "max_active_count",
    "avg_pairwise_score",
    "avg_pairwise_rank",
    "avg_ret20_zscore",
    "avg_close_position_zscore",
    "avg_range_zscore",
    "avg_volume_tilt_multiplier",
    "avg_volume_tilt_group_size",
    "avg_active_positions_before",
    "avg_remaining_position_slots",
    "bullish_rate",
    "bearish_rate",
    "breakout_rate",
    "avg_rsi",
    "avg_margin_ratio",
    "avg_projected_total_margin_after",
    "avg_portfolio_drawdown_pct",
    "avg_loss_streak",
    "floor_pre5_return_sum",
    "floor_pre5_return_std",
    "floor_pre5_net_pnl_sum",
    "floor_pre5_balance_change",
    "floor_pre5_max_ddpercent",
    "floor_pre20_return_sum",
    "floor_pre20_return_std",
    "floor_pre20_net_pnl_sum",
    "floor_pre20_balance_change",
    "floor_pre20_max_ddpercent",
    "floor_pre60_return_sum",
    "floor_pre60_return_std",
    "floor_pre60_net_pnl_sum",
    "floor_pre60_balance_change",
    "floor_pre60_max_ddpercent",
)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    event_paths = pd.read_csv(EVENT_PATHS_PATH)
    date_paths = pd.read_csv(DATE_PATHS_PATH)
    daily = pd.read_csv(DAILY_ATTRIBUTION_PATH)
    for df in (event_paths, date_paths, daily):
        df["date"] = pd.to_datetime(df["date"])
        df.sort_values("date", inplace=True)
        df.reset_index(drop=True, inplace=True)
    for column in EVENT_NUMERIC_COLUMNS:
        if column in event_paths.columns:
            event_paths[column] = pd.to_numeric(event_paths[column], errors="coerce").fillna(0.0)
    return event_paths, date_paths, daily


def build_event_feature_by_date(event_paths: pd.DataFrame) -> pd.DataFrame:
    grouped = event_paths.groupby("date").agg(
        avg_pairwise_score=("selection_pairwise_score", "mean"),
        avg_pairwise_rank=("selection_pairwise_rank", "mean"),
        avg_ret20_zscore=("selection_pairwise_feature_ret_20d_zscore_120", "mean"),
        avg_close_position_zscore=("selection_pairwise_feature_close_position_60d_cs_zscore_1d", "mean"),
        avg_range_zscore=("selection_pairwise_feature_range_pct_zscore_120", "mean"),
        avg_volume_tilt_multiplier=("selection_pairwise_volume_tilt_multiplier", "mean"),
        avg_volume_tilt_group_size=("selection_pairwise_volume_tilt_group_size", "mean"),
        avg_active_positions_before=("active_positions_before", "mean"),
        avg_remaining_position_slots=("remaining_position_slots", "mean"),
        bullish_rate=("bullish_alignment", "mean"),
        bearish_rate=("bearish_alignment", "mean"),
        breakout_rate=("breakout", "mean"),
        avg_rsi=("rsi_value", "mean"),
        avg_margin_ratio=("margin_ratio", "mean"),
        avg_projected_total_margin_after=("projected_total_margin_after", "mean"),
        avg_portfolio_drawdown_pct=("portfolio_drawdown_pct", "mean"),
        avg_loss_streak=("loss_streak", "mean"),
        signals=("signal", lambda values: ",".join(sorted(set(map(str, values))))),
        risk_modes=("risk_mode", lambda values: ",".join(sorted(set(map(str, values))))),
    )
    grouped.reset_index(inplace=True)
    return grouped


def pre_window_features(daily: pd.DataFrame, daily_index: int, window: int) -> dict[str, float]:
    begin = max(0, daily_index - window)
    pre = daily.iloc[begin:daily_index]
    prefix = f"floor_pre{window}"
    if pre.empty:
        return {
            f"{prefix}_return_sum": 0.0,
            f"{prefix}_return_std": 0.0,
            f"{prefix}_net_pnl_sum": 0.0,
            f"{prefix}_balance_change": 0.0,
            f"{prefix}_max_ddpercent": 0.0,
            f"{prefix}_trade_count": 0.0,
            f"{prefix}_slippage": 0.0,
        }
    return {
        f"{prefix}_return_sum": float(pre["return_floor35"].sum()),
        f"{prefix}_return_std": float(pre["return_floor35"].std(ddof=0) if len(pre) > 1 else 0.0),
        f"{prefix}_net_pnl_sum": float(pre["net_pnl_floor35"].sum()),
        f"{prefix}_balance_change": float(pre["balance_floor35"].iloc[-1] - pre["balance_floor35"].iloc[0]),
        f"{prefix}_max_ddpercent": float(pre["ddpercent_floor35"].max()),
        f"{prefix}_trade_count": float(pre["trade_count_floor35"].sum()),
        f"{prefix}_slippage": float(pre["slippage_floor35"].sum()),
    }


def add_pre_features(date_state: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    date_to_index = {pd.Timestamp(date): int(index) for index, date in daily[["date"]].itertuples()}
    rows: list[dict[str, Any]] = []
    for row in date_state.to_dict(orient="records"):
        payload = dict(row)
        daily_index = int(date_to_index.get(pd.Timestamp(row["date"]), 0))
        for window in PRE_WINDOWS:
            payload.update(pre_window_features(daily, daily_index, window))
        rows.append(payload)
    return pd.DataFrame(rows)


def classify_period(date_value: pd.Timestamp) -> str:
    if date_value.year == 2021:
        return "2021_negative_year"
    if pd.Timestamp("2025-03-01") <= date_value <= pd.Timestamp("2025-04-30"):
        return "2025_mar_apr_positive_cluster"
    if date_value.year == 2025:
        return "2025_other"
    return "other"


def build_date_state(event_paths: pd.DataFrame, date_paths: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    event_features = build_event_feature_by_date(event_paths)
    date_state = date_paths.merge(event_features, on="date", how="left")
    date_state = add_pre_features(date_state, daily)
    date_state["outcome_group"] = np.where(
        date_state[OUTCOME_METRIC] > 0.0,
        "positive20",
        np.where(date_state[OUTCOME_METRIC] < 0.0, "negative20", "flat20"),
    )
    lower = float(date_state[OUTCOME_METRIC].quantile(0.25))
    upper = float(date_state[OUTCOME_METRIC].quantile(0.75))
    date_state["strong_outcome_group"] = np.where(
        date_state[OUTCOME_METRIC] <= lower,
        "strong_negative20",
        np.where(date_state[OUTCOME_METRIC] >= upper, "strong_positive20", "middle20"),
    )
    date_state["period_group"] = date_state["date"].map(classify_period)
    return date_state


def build_feature_diff(
    date_state: pd.DataFrame,
    left_name: str,
    left_mask: pd.Series,
    right_name: str,
    right_mask: pd.Series,
) -> pd.DataFrame:
    left_df = date_state[left_mask].copy()
    right_df = date_state[right_mask].copy()
    rows: list[dict[str, Any]] = []
    for feature in CONTRAST_FEATURES:
        left_values = pd.to_numeric(left_df[feature], errors="coerce").dropna()
        right_values = pd.to_numeric(right_df[feature], errors="coerce").dropna()
        left_mean = float(left_values.mean()) if len(left_values) else 0.0
        right_mean = float(right_values.mean()) if len(right_values) else 0.0
        left_median = float(left_values.median()) if len(left_values) else 0.0
        right_median = float(right_values.median()) if len(right_values) else 0.0
        rows.append(
            {
                "feature": feature,
                f"{left_name}_mean": left_mean,
                f"{right_name}_mean": right_mean,
                "mean_diff": left_mean - right_mean,
                f"{left_name}_median": left_median,
                f"{right_name}_median": right_median,
                "median_diff": left_median - right_median,
                f"{left_name}_count": int(len(left_values)),
                f"{right_name}_count": int(len(right_values)),
            }
        )
    diff_df = pd.DataFrame(rows)
    diff_df["abs_mean_diff"] = diff_df["mean_diff"].abs()
    diff_df.sort_values(["abs_mean_diff", "feature"], ascending=[False, True], inplace=True)
    diff_df.reset_index(drop=True, inplace=True)
    return diff_df


def summarize_group(date_state: pd.DataFrame, group_column: str) -> pd.DataFrame:
    grouped = date_state.groupby(group_column, dropna=False).agg(
        date_count=("date", "size"),
        mean_fwd20=(OUTCOME_METRIC, "mean"),
        median_fwd20=(OUTCOME_METRIC, "median"),
        hit_rate_fwd20=(OUTCOME_METRIC, lambda values: float((values > 0).mean())),
        mean_fwd5=("fwd5d_delta_net_pnl_after_event", "mean"),
        median_fwd5=("fwd5d_delta_net_pnl_after_event", "median"),
        event_count=("event_count", "sum"),
        volume_cut=("volume_cut", "sum"),
        avg_gate_weight=("avg_gate_weight", "mean"),
        avg_max_corr=("avg_max_corr", "mean"),
        avg_active_count=("avg_active_count", "mean"),
        avg_ret20_zscore=("avg_ret20_zscore", "mean"),
        avg_range_zscore=("avg_range_zscore", "mean"),
        avg_rsi=("avg_rsi", "mean"),
        floor_pre20_return_sum=("floor_pre20_return_sum", "mean"),
        floor_pre20_return_std=("floor_pre20_return_std", "mean"),
        floor_pre20_max_ddpercent=("floor_pre20_max_ddpercent", "mean"),
    )
    grouped.reset_index(inplace=True)
    grouped.sort_values(["mean_fwd20", group_column], ascending=[False, True], inplace=True)
    grouped.reset_index(drop=True, inplace=True)
    return grouped


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    event_paths, date_paths, daily = load_inputs()
    date_state = build_date_state(event_paths, date_paths, daily)

    feature_diff = build_feature_diff(
        date_state,
        "positive20",
        date_state["outcome_group"] == "positive20",
        "negative20",
        date_state["outcome_group"] == "negative20",
    )
    strong_feature_diff = build_feature_diff(
        date_state,
        "strong_positive20",
        date_state["strong_outcome_group"] == "strong_positive20",
        "strong_negative20",
        date_state["strong_outcome_group"] == "strong_negative20",
    )
    year_summary = summarize_group(date_state, "year")
    period_summary = summarize_group(date_state, "period_group")

    best_dates = date_state.sort_values([OUTCOME_METRIC, "date"], ascending=[False, True]).head(12)
    worst_dates = date_state.sort_values([OUTCOME_METRIC, "date"], ascending=[True, True]).head(12)

    date_state.to_csv(DATE_STATE_CSV_PATH, index=False, encoding="utf-8-sig")
    feature_diff.to_csv(FEATURE_DIFF_CSV_PATH, index=False, encoding="utf-8-sig")
    strong_feature_diff.to_csv(STRONG_FEATURE_DIFF_CSV_PATH, index=False, encoding="utf-8-sig")
    year_summary.to_csv(YEAR_SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    period_summary.to_csv(PERIOD_SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")

    summary_payload: dict[str, Any] = {
        "analysis": OUTPUT_PREFIX,
        "date_count": int(len(date_state)),
        "positive20_date_count": int((date_state["outcome_group"] == "positive20").sum()),
        "negative20_date_count": int((date_state["outcome_group"] == "negative20").sum()),
        "positive20_mean": float(
            date_state.loc[date_state["outcome_group"] == "positive20", OUTCOME_METRIC].mean()
        ),
        "negative20_mean": float(
            date_state.loc[date_state["outcome_group"] == "negative20", OUTCOME_METRIC].mean()
        ),
        "strong_positive20_threshold": float(date_state[OUTCOME_METRIC].quantile(0.75)),
        "strong_negative20_threshold": float(date_state[OUTCOME_METRIC].quantile(0.25)),
        "year_summary": year_summary.to_dict(orient="records"),
        "period_summary": period_summary.to_dict(orient="records"),
        "top_positive_vs_negative_feature_diffs": feature_diff.head(20).to_dict(orient="records"),
        "top_strong_feature_diffs": strong_feature_diff.head(20).to_dict(orient="records"),
        "best_dates": best_dates.to_dict(orient="records"),
        "worst_dates": worst_dates.to_dict(orient="records"),
    }
    SUMMARY_JSON_PATH.write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print(f"summary json: {SUMMARY_JSON_PATH}")
    print(f"date state csv: {DATE_STATE_CSV_PATH}")
    print(f"feature diff csv: {FEATURE_DIFF_CSV_PATH}")
    print(json.dumps(summary_payload, ensure_ascii=False, indent=2, default=str))
    print("\n[year summary]")
    print(year_summary.to_string(index=False))
    print("\n[period summary]")
    print(period_summary.to_string(index=False))
    print("\n[top positive vs negative feature diffs]")
    print(feature_diff.head(20).to_string(index=False))
    print("\n[top strong feature diffs]")
    print(strong_feature_diff.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
