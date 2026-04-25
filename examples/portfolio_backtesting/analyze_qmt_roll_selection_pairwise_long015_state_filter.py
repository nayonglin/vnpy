from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

BASE_DAILY_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_v2_directional_baseline_daily.csv"
LONG015_DAILY_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_v2_volume_tilt_long015_sweep_fix1_daily.csv"
LONG015_SNAPSHOT_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_v2_volume_tilt_long015_sweep_fix1_entry_candidate_snapshots_2020_2026_04.csv"

SUMMARY_JSON_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_v2_volume_tilt_long015_state_filter_analysis_summary.json"
EVENT_CSV_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_v2_volume_tilt_long015_state_filter_events.csv"
SCAN_CSV_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_v2_volume_tilt_long015_state_filter_scan.csv"


def load_daily_delta() -> pd.DataFrame:
    base_df = pd.read_csv(BASE_DAILY_PATH)
    long_df = pd.read_csv(LONG015_DAILY_PATH)
    base_df["date"] = pd.to_datetime(base_df["date"])
    long_df["date"] = pd.to_datetime(long_df["date"])
    merged = base_df.merge(
        long_df[["date", "net_pnl"]],
        on="date",
        suffixes=("_base", "_long015"),
        how="inner",
    )
    merged.sort_values("date", inplace=True)
    merged.reset_index(drop=True, inplace=True)
    merged["delta_net_pnl"] = merged["net_pnl_long015"] - merged["net_pnl_base"]
    for horizon in (5, 10, 20):
        merged[f"fwd_{horizon}d_delta_net_pnl"] = [
            float(merged["delta_net_pnl"].iloc[index + 1:index + 1 + horizon].sum())
            if index + 1 < len(merged)
            else 0.0
            for index in range(len(merged))
        ]
    return merged


def build_event_frame() -> pd.DataFrame:
    snapshot_df = pd.read_csv(LONG015_SNAPSHOT_PATH)
    snapshot_df["date"] = pd.to_datetime(snapshot_df["date"])
    changed_df = snapshot_df[
        (snapshot_df["direction"] == "long")
        & (snapshot_df["is_opened"] == 1)
        & (snapshot_df["selection_pairwise_volume_tilt_applied"] == 1)
        & (snapshot_df["selected_volume"] != snapshot_df["selected_volume_ungated"])
    ].copy()
    grouped = changed_df.groupby("date").agg(
        changed_rows=("product_vt_symbol", "size"),
        avg_ret20_zscore=("selection_pairwise_feature_ret_20d_zscore_120", "mean"),
        max_ret20_zscore=("selection_pairwise_feature_ret_20d_zscore_120", "max"),
        avg_range_zscore=("selection_pairwise_feature_range_pct_zscore_120", "mean"),
        max_range_zscore=("selection_pairwise_feature_range_pct_zscore_120", "max"),
        avg_rsi=("rsi_value", "mean"),
        max_rsi=("rsi_value", "max"),
        avg_score=("selection_pairwise_score", "mean"),
        score_gap=("selection_pairwise_score", lambda values: float(values.max() - values.min())),
        breakout_rate=("breakout", "mean"),
        bullish_alignment_rate=("bullish_alignment", "mean"),
    )
    grouped.reset_index(inplace=True)
    return grouped


def scan_thresholds(event_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    for column in (
        "avg_ret20_zscore",
        "max_ret20_zscore",
        "avg_range_zscore",
        "max_range_zscore",
        "avg_rsi",
        "max_rsi",
        "score_gap",
    ):
        quantiles = sorted(
            {
                round(float(event_df[column].quantile(q)), 6)
                for q in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8)
            }
        )
        for threshold in quantiles:
            for operator in ("<=", ">="):
                if operator == "<=":
                    mask = event_df[column] <= threshold
                else:
                    mask = event_df[column] >= threshold
                kept_df = event_df[mask]
                if len(kept_df) < 10 or len(kept_df) > len(event_df) - 10:
                    continue
                rows.append(
                    {
                        "column": column,
                        "operator": operator,
                        "threshold": threshold,
                        "kept_event_count": float(len(kept_df)),
                        "sum_fwd_5d_delta": float(kept_df["fwd_5d_delta_net_pnl"].sum()),
                        "mean_fwd_5d_delta": float(kept_df["fwd_5d_delta_net_pnl"].mean()),
                        "sum_fwd_10d_delta": float(kept_df["fwd_10d_delta_net_pnl"].sum()),
                        "mean_fwd_10d_delta": float(kept_df["fwd_10d_delta_net_pnl"].mean()),
                        "sum_fwd_20d_delta": float(kept_df["fwd_20d_delta_net_pnl"].sum()),
                        "mean_fwd_20d_delta": float(kept_df["fwd_20d_delta_net_pnl"].mean()),
                    }
                )
    result_df = pd.DataFrame(rows)
    result_df.sort_values(
        ["mean_fwd_20d_delta", "sum_fwd_20d_delta"],
        ascending=[False, False],
        inplace=True,
    )
    result_df.reset_index(drop=True, inplace=True)
    return result_df


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    daily_df = load_daily_delta()
    event_df = build_event_frame().merge(
        daily_df[
            [
                "date",
                "fwd_5d_delta_net_pnl",
                "fwd_10d_delta_net_pnl",
                "fwd_20d_delta_net_pnl",
            ]
        ],
        on="date",
        how="left",
    )
    event_df["year"] = event_df["date"].dt.year
    scan_df = scan_thresholds(event_df)

    summary_payload = {
        "event_count": int(len(event_df)),
        "changed_row_count": int(event_df["changed_rows"].sum()),
        "year_summary": event_df.groupby("year")["fwd_20d_delta_net_pnl"].agg(["count", "sum", "mean"]).reset_index().to_dict(orient="records"),
        "top_scan_rows": scan_df.head(20).to_dict(orient="records"),
        "bottom_scan_rows": scan_df.tail(20).to_dict(orient="records"),
        "worst_events": event_df.sort_values("fwd_20d_delta_net_pnl").head(15).to_dict(orient="records"),
        "best_events": event_df.sort_values("fwd_20d_delta_net_pnl", ascending=False).head(15).to_dict(orient="records"),
    }

    event_df.to_csv(EVENT_CSV_PATH, index=False, encoding="utf-8-sig")
    scan_df.to_csv(SCAN_CSV_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print(f"state filter summary json: {SUMMARY_JSON_PATH}")
    print(f"state filter events csv: {EVENT_CSV_PATH}")
    print(f"state filter scan csv: {SCAN_CSV_PATH}")
    print(json.dumps(summary_payload, ensure_ascii=False, indent=2, default=str))
    print(scan_df.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
