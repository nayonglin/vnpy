from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

LONG015_DAILY_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_v2_volume_tilt_long015_daily.csv"
VOLREF30_DAILY_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_v2_volume_tilt_long015_volref30_daily.csv"
VOLREF30_SNAPSHOT_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_v2_volume_tilt_long015_volref30_entry_candidate_snapshots_2020_2026_04.csv"

SUMMARY_JSON_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_v2_volume_tilt_long015_volref30_failure_cluster_summary.json"
CLUSTER_CSV_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_v2_volume_tilt_long015_volref30_failure_clusters.csv"
DATE_FEATURE_CSV_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_v2_volume_tilt_long015_volref30_failure_cluster_date_features.csv"
DIFF_CSV_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_v2_volume_tilt_long015_volref30_failure_cluster_feature_diff.csv"

WORST_CLUSTER_COUNT: int = 12
BEST_CLUSTER_COUNT: int = 12
MIN_CLUSTER_LENGTH: int = 1


def load_daily_curve(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df.sort_values("date", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def build_delta_frame() -> pd.DataFrame:
    long015 = load_daily_curve(LONG015_DAILY_PATH)
    volref30 = load_daily_curve(VOLREF30_DAILY_PATH)
    merged = long015.merge(
        volref30,
        on="date",
        suffixes=("_long015", "_volref30"),
        how="inner",
    )
    merged["delta_net_pnl"] = merged["net_pnl_volref30"] - merged["net_pnl_long015"]
    merged["delta_balance"] = merged["balance_volref30"] - merged["balance_long015"]
    merged["delta_trade_count"] = merged["trade_count_volref30"] - merged["trade_count_long015"]
    return merged


def build_event_date_feature_frame() -> pd.DataFrame:
    snapshot_df = pd.read_csv(VOLREF30_SNAPSHOT_PATH)
    snapshot_df["date"] = pd.to_datetime(snapshot_df["date"])
    changed_df = snapshot_df[
        (snapshot_df["direction"] == "long")
        & (snapshot_df["is_opened"] == 1)
        & (snapshot_df["selection_pairwise_volume_tilt_applied"] == 1)
        & (snapshot_df["selected_volume"] != snapshot_df["selected_volume_ungated"])
    ].copy()
    grouped = changed_df.groupby("date").agg(
        changed_rows=("product_vt_symbol", "size"),
        product_count=("product_vt_symbol", "nunique"),
        avg_score=("selection_pairwise_score", "mean"),
        max_score=("selection_pairwise_score", "max"),
        avg_score_gap=("selection_pairwise_volume_tilt_score_gap", "mean"),
        max_score_gap=("selection_pairwise_volume_tilt_score_gap", "max"),
        avg_top_gap=("selection_pairwise_volume_tilt_top_gap", "mean"),
        max_top_gap=("selection_pairwise_volume_tilt_top_gap", "max"),
        avg_base_volume=("selection_pairwise_volume_tilt_volume_before", "mean"),
        max_base_volume=("selection_pairwise_volume_tilt_volume_before", "max"),
        avg_group_size=("selection_pairwise_volume_tilt_group_size", "mean"),
        max_group_size=("selection_pairwise_volume_tilt_group_size", "max"),
        avg_active_positions_before=("active_positions_before", "mean"),
        avg_ret20_zscore=("selection_pairwise_feature_ret_20d_zscore_120", "mean"),
        max_ret20_zscore=("selection_pairwise_feature_ret_20d_zscore_120", "max"),
        avg_range_zscore=("selection_pairwise_feature_range_pct_zscore_120", "mean"),
        max_range_zscore=("selection_pairwise_feature_range_pct_zscore_120", "max"),
        avg_rsi=("rsi_value", "mean"),
        max_rsi=("rsi_value", "max"),
        avg_bullish_alignment=("bullish_alignment", "mean"),
        avg_breakout=("breakout", "mean"),
        avg_selected_volume=("selected_volume", "mean"),
        avg_selected_volume_ungated=("selected_volume_ungated", "mean"),
        avg_tilt_multiplier=("selection_pairwise_volume_tilt_multiplier", "mean"),
        avg_tilt_strength=("selection_pairwise_volume_tilt_direction_strength", "mean"),
    )
    grouped.reset_index(inplace=True)
    return grouped


def build_clusters(delta_df: pd.DataFrame) -> pd.DataFrame:
    signed = np.sign(delta_df["delta_net_pnl"].to_numpy(dtype=np.float64))
    cluster_ids: list[int] = []
    current_id = -1
    prev_sign = 0.0
    for sign_value in signed:
        if sign_value == 0.0:
            current_id += 1
            cluster_ids.append(current_id)
            prev_sign = 0.0
            continue
        if sign_value != prev_sign:
            current_id += 1
            prev_sign = sign_value
        cluster_ids.append(current_id)
    clustered = delta_df.copy()
    clustered["cluster_id"] = cluster_ids
    cluster_df = clustered.groupby("cluster_id").agg(
        start_date=("date", "min"),
        end_date=("date", "max"),
        day_count=("date", "size"),
        sum_delta_net_pnl=("delta_net_pnl", "sum"),
        mean_delta_net_pnl=("delta_net_pnl", "mean"),
        min_delta_net_pnl=("delta_net_pnl", "min"),
        max_delta_net_pnl=("delta_net_pnl", "max"),
        sum_delta_trade_count=("delta_trade_count", "sum"),
        end_delta_balance=("delta_balance", "last"),
    )
    cluster_df.reset_index(inplace=True)
    cluster_df["cluster_type"] = np.where(
        cluster_df["sum_delta_net_pnl"] > 0.0,
        "positive",
        np.where(cluster_df["sum_delta_net_pnl"] < 0.0, "negative", "flat"),
    )
    cluster_df = cluster_df[cluster_df["day_count"] >= MIN_CLUSTER_LENGTH].copy()
    cluster_df.sort_values(["start_date", "cluster_id"], inplace=True)
    cluster_df.reset_index(drop=True, inplace=True)
    return cluster_df


def build_cluster_feature_frame(
    cluster_df: pd.DataFrame,
    daily_df: pd.DataFrame,
    event_df: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for row in cluster_df.to_dict(orient="records"):
        start_date = row["start_date"]
        end_date = row["end_date"]
        daily_slice = daily_df[(daily_df["date"] >= start_date) & (daily_df["date"] <= end_date)].copy()
        event_slice = event_df[(event_df["date"] >= start_date) & (event_df["date"] <= end_date)].copy()

        payload: dict[str, object] = dict(row)
        payload["event_day_count"] = int(len(event_slice))
        payload["tilt_changed_rows"] = int(event_slice["changed_rows"].sum()) if len(event_slice) else 0

        for column in (
            "product_count",
            "avg_score",
            "max_score",
            "avg_score_gap",
            "max_score_gap",
            "avg_top_gap",
            "max_top_gap",
            "avg_base_volume",
            "max_base_volume",
            "avg_group_size",
            "max_group_size",
            "avg_active_positions_before",
            "avg_ret20_zscore",
            "max_ret20_zscore",
            "avg_range_zscore",
            "max_range_zscore",
            "avg_rsi",
            "max_rsi",
            "avg_bullish_alignment",
            "avg_breakout",
            "avg_selected_volume",
            "avg_selected_volume_ungated",
            "avg_tilt_multiplier",
            "avg_tilt_strength",
        ):
            payload[column] = float(event_slice[column].mean()) if len(event_slice) else 0.0

        payload["abs_sum_delta_net_pnl"] = abs(float(payload["sum_delta_net_pnl"]))
        payload["first_balance_long015"] = float(daily_slice["balance_long015"].iloc[0]) if len(daily_slice) else 0.0
        payload["first_balance_volref30"] = float(daily_slice["balance_volref30"].iloc[0]) if len(daily_slice) else 0.0
        rows.append(payload)

    result_df = pd.DataFrame(rows)
    result_df.sort_values(
        ["cluster_type", "abs_sum_delta_net_pnl", "day_count"],
        ascending=[True, False, False],
        inplace=True,
    )
    result_df.reset_index(drop=True, inplace=True)
    return result_df


def build_feature_diff_frame(cluster_feature_df: pd.DataFrame) -> pd.DataFrame:
    metric_columns = [
        "day_count",
        "event_day_count",
        "tilt_changed_rows",
        "product_count",
        "avg_score",
        "avg_score_gap",
        "avg_top_gap",
        "avg_base_volume",
        "max_base_volume",
        "avg_group_size",
        "avg_active_positions_before",
        "avg_ret20_zscore",
        "max_ret20_zscore",
        "avg_range_zscore",
        "max_range_zscore",
        "avg_rsi",
        "max_rsi",
        "avg_bullish_alignment",
        "avg_breakout",
        "avg_selected_volume",
        "avg_selected_volume_ungated",
        "avg_tilt_multiplier",
        "sum_delta_trade_count",
    ]
    negative_df = cluster_feature_df[cluster_feature_df["cluster_type"] == "negative"].copy()
    positive_df = cluster_feature_df[cluster_feature_df["cluster_type"] == "positive"].copy()
    rows: list[dict[str, float | str]] = []
    for column in metric_columns:
        negative_mean = float(negative_df[column].mean()) if len(negative_df) else 0.0
        positive_mean = float(positive_df[column].mean()) if len(positive_df) else 0.0
        rows.append(
            {
                "metric": column,
                "negative_mean": negative_mean,
                "positive_mean": positive_mean,
                "negative_minus_positive": negative_mean - positive_mean,
                "negative_abs_mean": float(negative_df[column].abs().mean()) if len(negative_df) else 0.0,
                "positive_abs_mean": float(positive_df[column].abs().mean()) if len(positive_df) else 0.0,
            }
        )
    diff_df = pd.DataFrame(rows)
    diff_df["abs_gap"] = diff_df["negative_minus_positive"].abs()
    diff_df.sort_values(["abs_gap", "metric"], ascending=[False, True], inplace=True)
    diff_df.reset_index(drop=True, inplace=True)
    return diff_df


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    daily_df = build_delta_frame()
    event_df = build_event_date_feature_frame()
    cluster_df = build_clusters(daily_df)
    cluster_feature_df = build_cluster_feature_frame(cluster_df, daily_df, event_df)
    diff_df = build_feature_diff_frame(cluster_feature_df)

    worst_clusters = (
        cluster_feature_df[cluster_feature_df["cluster_type"] == "negative"]
        .sort_values(["sum_delta_net_pnl", "day_count"], ascending=[True, False])
        .head(WORST_CLUSTER_COUNT)
    )
    best_clusters = (
        cluster_feature_df[cluster_feature_df["cluster_type"] == "positive"]
        .sort_values(["sum_delta_net_pnl", "day_count"], ascending=[False, False])
        .head(BEST_CLUSTER_COUNT)
    )

    summary_payload = {
        "daily_count": int(len(daily_df)),
        "event_date_count": int(len(event_df)),
        "total_changed_rows": int(event_df["changed_rows"].sum()),
        "total_delta_net_pnl": float(daily_df["delta_net_pnl"].sum()),
        "negative_cluster_count": int((cluster_feature_df["cluster_type"] == "negative").sum()),
        "positive_cluster_count": int((cluster_feature_df["cluster_type"] == "positive").sum()),
        "negative_cluster_total_delta_net_pnl": float(
            cluster_feature_df.loc[cluster_feature_df["cluster_type"] == "negative", "sum_delta_net_pnl"].sum()
        ),
        "positive_cluster_total_delta_net_pnl": float(
            cluster_feature_df.loc[cluster_feature_df["cluster_type"] == "positive", "sum_delta_net_pnl"].sum()
        ),
        "worst_clusters": worst_clusters.to_dict(orient="records"),
        "best_clusters": best_clusters.to_dict(orient="records"),
        "top_feature_diffs": diff_df.head(20).to_dict(orient="records"),
    }

    cluster_feature_df.to_csv(CLUSTER_CSV_PATH, index=False, encoding="utf-8-sig")
    event_df.merge(
        daily_df[["date", "delta_net_pnl", "delta_balance", "delta_trade_count"]],
        on="date",
        how="left",
    ).to_csv(DATE_FEATURE_CSV_PATH, index=False, encoding="utf-8-sig")
    diff_df.to_csv(DIFF_CSV_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print(f"failure cluster summary json: {SUMMARY_JSON_PATH}")
    print(f"failure cluster csv: {CLUSTER_CSV_PATH}")
    print(f"date feature csv: {DATE_FEATURE_CSV_PATH}")
    print(f"feature diff csv: {DIFF_CSV_PATH}")
    print(json.dumps(summary_payload, ensure_ascii=False, indent=2, default=str))
    print(diff_df.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
