from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

INPUT_PREFIX: str = "qmt_roll_selection_pairwise_long015_volref30_corr_crowding_attribution"
OUTPUT_PREFIX: str = "qmt_roll_selection_pairwise_long015_volref30_corr_crowding_forward_paths"

GATE_EVENTS_PATH: Path = OUTPUT_DIR / f"{INPUT_PREFIX}_gate_events.csv"
DAILY_ATTRIBUTION_PATH: Path = OUTPUT_DIR / f"{INPUT_PREFIX}_daily_attribution.csv"

EVENT_PATHS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_paths.csv"
DATE_PATHS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_date_paths.csv"
BY_YEAR_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_year.csv"
BY_DIRECTION_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_direction.csv"
BY_SIGNAL_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_signal.csv"
BY_PRODUCT_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_product.csv"
BY_CORR_BIN_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_corr_bin.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary.json"

HORIZONS: tuple[int, ...] = (1, 5, 10, 20, 40)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    events = pd.read_csv(GATE_EVENTS_PATH)
    daily = pd.read_csv(DAILY_ATTRIBUTION_PATH)
    events["date"] = pd.to_datetime(events["date"])
    daily["date"] = pd.to_datetime(daily["date"])
    events.sort_values(["date", "product", "direction", "signal"], inplace=True)
    daily.sort_values("date", inplace=True)
    events.reset_index(drop=True, inplace=True)
    daily.reset_index(drop=True, inplace=True)
    return events, daily


def forward_sum(daily: pd.DataFrame, start_index: int, horizon: int, *, include_event_day: bool) -> dict[str, float]:
    begin = start_index if include_event_day else start_index + 1
    end = min(begin + horizon, len(daily))
    if begin >= len(daily) or begin >= end:
        return {
            "delta_net_pnl": 0.0,
            "delta_trade_count": 0.0,
            "delta_slippage": 0.0,
            "day_count": 0.0,
        }
    window = daily.iloc[begin:end]
    return {
        "delta_net_pnl": float(window["delta_net_pnl"].sum()),
        "delta_trade_count": float(window["delta_trade_count"].sum()),
        "delta_slippage": float(window["delta_slippage"].sum()),
        "day_count": float(len(window)),
    }


def attach_forward_paths(base_df: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    date_to_index = {pd.Timestamp(date): int(index) for index, date in daily[["date"]].itertuples()}
    rows: list[dict[str, Any]] = []
    for event_index, row in enumerate(base_df.to_dict(orient="records"), start=1):
        date = pd.Timestamp(row["date"])
        if date not in date_to_index:
            continue
        daily_index = int(date_to_index[date])
        payload = dict(row)
        payload["path_index"] = event_index
        payload["daily_index"] = daily_index
        payload["delta_balance_before_event"] = (
            float(daily["delta_balance"].iloc[daily_index - 1]) if daily_index > 0 else 0.0
        )
        payload["delta_balance_on_event"] = float(daily["delta_balance"].iloc[daily_index])
        for horizon in HORIZONS:
            included = forward_sum(daily, daily_index, horizon, include_event_day=True)
            after = forward_sum(daily, daily_index, horizon, include_event_day=False)
            payload[f"fwd{horizon}d_delta_net_pnl_including_event"] = included["delta_net_pnl"]
            payload[f"fwd{horizon}d_delta_net_pnl_after_event"] = after["delta_net_pnl"]
            payload[f"fwd{horizon}d_delta_trade_count_after_event"] = after["delta_trade_count"]
            payload[f"fwd{horizon}d_delta_slippage_after_event"] = after["delta_slippage"]
            payload[f"fwd{horizon}d_day_count_after_event"] = after["day_count"]
        rows.append(payload)
    return pd.DataFrame(rows)


def build_date_events(events: pd.DataFrame) -> pd.DataFrame:
    grouped = events.groupby("date").agg(
        event_count=("product", "size"),
        product_count=("product", "nunique"),
        products=("product", lambda values: ",".join(sorted(set(map(str, values))))),
        long_event_count=("direction", lambda values: int((values == "long").sum())),
        short_event_count=("direction", lambda values: int((values == "short").sum())),
        selected_volume=("selected_volume", "sum"),
        selected_volume_ungated=("selected_volume_ungated", "sum"),
        volume_cut=("volume_cut", "sum"),
        avg_cut_ratio=("cut_ratio", "mean"),
        avg_gate_weight=("same_direction_correlation_gate_weight", "mean"),
        min_gate_weight=("same_direction_correlation_gate_weight", "min"),
        avg_max_corr=("same_direction_correlation_max_corr", "mean"),
        max_corr=("same_direction_correlation_max_corr", "max"),
        avg_active_count=("same_direction_correlation_active_count", "mean"),
        max_active_count=("same_direction_correlation_active_count", "max"),
    )
    grouped.reset_index(inplace=True)
    grouped["dominant_direction"] = np.where(
        grouped["long_event_count"] > grouped["short_event_count"],
        "long",
        np.where(grouped["short_event_count"] > grouped["long_event_count"], "short", "mixed"),
    )
    grouped["year"] = grouped["date"].dt.year
    grouped["month"] = grouped["date"].dt.to_period("M").astype(str)
    return grouped


def summarize_paths(path_df: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    metric = "fwd20d_delta_net_pnl_after_event"
    grouped = path_df.groupby(group_columns, dropna=False).agg(
        row_count=("date", "size"),
        date_count=("date", "nunique"),
        volume_cut=("volume_cut", "sum"),
        selected_volume_ungated=("selected_volume_ungated", "sum"),
        avg_gate_weight=("same_direction_correlation_gate_weight", "mean"),
        avg_max_corr=("same_direction_correlation_max_corr", "mean"),
        max_corr=("same_direction_correlation_max_corr", "max"),
        avg_active_count=("same_direction_correlation_active_count", "mean"),
        mean_fwd5_after=("fwd5d_delta_net_pnl_after_event", "mean"),
        median_fwd5_after=("fwd5d_delta_net_pnl_after_event", "median"),
        mean_fwd10_after=("fwd10d_delta_net_pnl_after_event", "mean"),
        median_fwd10_after=("fwd10d_delta_net_pnl_after_event", "median"),
        mean_fwd20_after=(metric, "mean"),
        median_fwd20_after=(metric, "median"),
        sum_fwd20_after=(metric, "sum"),
        min_fwd20_after=(metric, "min"),
        max_fwd20_after=(metric, "max"),
    )
    grouped.reset_index(inplace=True)
    grouped["hit_rate_fwd20_after"] = (
        path_df.groupby(group_columns, dropna=False)[metric].apply(lambda values: float((values > 0).mean())).to_numpy()
    )
    grouped["volume_cut_share"] = np.where(
        grouped["selected_volume_ungated"] > 0,
        grouped["volume_cut"] / grouped["selected_volume_ungated"],
        0.0,
    )
    grouped.sort_values(["mean_fwd20_after", "row_count"], ascending=[False, False], inplace=True)
    grouped.reset_index(drop=True, inplace=True)
    return grouped


def path_headlines(path_df: pd.DataFrame, prefix: str) -> dict[str, float | int]:
    metric = "fwd20d_delta_net_pnl_after_event"
    return {
        f"{prefix}_row_count": int(len(path_df)),
        f"{prefix}_positive_fwd20_count": int((path_df[metric] > 0).sum()),
        f"{prefix}_negative_fwd20_count": int((path_df[metric] < 0).sum()),
        f"{prefix}_hit_rate_fwd20_after": float((path_df[metric] > 0).mean()) if len(path_df) else 0.0,
        f"{prefix}_mean_fwd20_after": float(path_df[metric].mean()) if len(path_df) else 0.0,
        f"{prefix}_median_fwd20_after": float(path_df[metric].median()) if len(path_df) else 0.0,
        f"{prefix}_mean_fwd10_after": float(path_df["fwd10d_delta_net_pnl_after_event"].mean()) if len(path_df) else 0.0,
        f"{prefix}_median_fwd10_after": float(path_df["fwd10d_delta_net_pnl_after_event"].median()) if len(path_df) else 0.0,
        f"{prefix}_mean_fwd5_after": float(path_df["fwd5d_delta_net_pnl_after_event"].mean()) if len(path_df) else 0.0,
        f"{prefix}_median_fwd5_after": float(path_df["fwd5d_delta_net_pnl_after_event"].median()) if len(path_df) else 0.0,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    events, daily = load_inputs()
    date_events = build_date_events(events)

    event_paths = attach_forward_paths(events, daily)
    date_paths = attach_forward_paths(date_events, daily)

    by_year = summarize_paths(event_paths, ["year"])
    by_direction = summarize_paths(event_paths, ["direction"])
    by_signal = summarize_paths(event_paths, ["signal"])
    by_product = summarize_paths(event_paths, ["product"])
    by_corr_bin = summarize_paths(event_paths, ["corr_bin", "active_count_bin"])

    event_paths.to_csv(EVENT_PATHS_CSV_PATH, index=False, encoding="utf-8-sig")
    date_paths.to_csv(DATE_PATHS_CSV_PATH, index=False, encoding="utf-8-sig")
    by_year.to_csv(BY_YEAR_CSV_PATH, index=False, encoding="utf-8-sig")
    by_direction.to_csv(BY_DIRECTION_CSV_PATH, index=False, encoding="utf-8-sig")
    by_signal.to_csv(BY_SIGNAL_CSV_PATH, index=False, encoding="utf-8-sig")
    by_product.to_csv(BY_PRODUCT_CSV_PATH, index=False, encoding="utf-8-sig")
    by_corr_bin.to_csv(BY_CORR_BIN_CSV_PATH, index=False, encoding="utf-8-sig")

    best_dates = date_paths.sort_values(
        ["fwd20d_delta_net_pnl_after_event", "date"], ascending=[False, True]
    ).head(12)
    worst_dates = date_paths.sort_values(
        ["fwd20d_delta_net_pnl_after_event", "date"], ascending=[True, True]
    ).head(12)
    best_events = event_paths.sort_values(
        ["fwd20d_delta_net_pnl_after_event", "date"], ascending=[False, True]
    ).head(12)
    worst_events = event_paths.sort_values(
        ["fwd20d_delta_net_pnl_after_event", "date"], ascending=[True, True]
    ).head(12)

    summary_payload: dict[str, Any] = {
        "analysis": OUTPUT_PREFIX,
        "input_prefix": INPUT_PREFIX,
        **path_headlines(event_paths, "event"),
        **path_headlines(date_paths, "date"),
        "best_dates_after_20d": best_dates.to_dict(orient="records"),
        "worst_dates_after_20d": worst_dates.to_dict(orient="records"),
        "best_events_after_20d": best_events.to_dict(orient="records"),
        "worst_events_after_20d": worst_events.to_dict(orient="records"),
        "by_year": by_year.to_dict(orient="records"),
        "by_direction": by_direction.to_dict(orient="records"),
        "top_products_by_mean_fwd20": by_product.head(12).to_dict(orient="records"),
        "bottom_products_by_mean_fwd20": by_product.sort_values(
            ["mean_fwd20_after", "row_count"], ascending=[True, False]
        ).head(12).to_dict(orient="records"),
        "by_corr_bin": by_corr_bin.to_dict(orient="records"),
    }
    SUMMARY_JSON_PATH.write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print(f"summary json: {SUMMARY_JSON_PATH}")
    print(f"event paths csv: {EVENT_PATHS_CSV_PATH}")
    print(f"date paths csv: {DATE_PATHS_CSV_PATH}")
    print(json.dumps(summary_payload, ensure_ascii=False, indent=2, default=str))
    print("\n[by year]")
    print(by_year.to_string(index=False))
    print("\n[by direction]")
    print(by_direction.to_string(index=False))
    print("\n[top products]")
    print(by_product.head(12).to_string(index=False))
    print("\n[bottom products]")
    print(by_product.sort_values(["mean_fwd20_after", "row_count"], ascending=[True, False]).head(12).to_string(index=False))
    print("\n[best dates]")
    print(best_dates[["date", "event_count", "products", "volume_cut", "fwd20d_delta_net_pnl_after_event"]].to_string(index=False))
    print("\n[worst dates]")
    print(worst_dates[["date", "event_count", "products", "volume_cut", "fwd20d_delta_net_pnl_after_event"]].to_string(index=False))


if __name__ == "__main__":
    main()
