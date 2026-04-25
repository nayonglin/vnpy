from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

CURRENT_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_formal_current"
FLOOR35_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_formal_floor35"
OUTPUT_PREFIX: str = "qmt_roll_selection_pairwise_long015_volref30_corr_crowding_attribution"

CURRENT_DAILY_PATH: Path = OUTPUT_DIR / f"{CURRENT_PREFIX}_daily.csv"
FLOOR35_DAILY_PATH: Path = OUTPUT_DIR / f"{FLOOR35_PREFIX}_daily.csv"
FLOOR35_SNAPSHOT_PATH: Path = OUTPUT_DIR / f"{FLOOR35_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv"
CURRENT_POSITION_CHANGE_PATH: Path = OUTPUT_DIR / f"{CURRENT_PREFIX}_position_changes_2020_2026_04.csv"
FLOOR35_POSITION_CHANGE_PATH: Path = OUTPUT_DIR / f"{FLOOR35_PREFIX}_position_changes_2020_2026_04.csv"

GATE_EVENTS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_events.csv"
DAILY_ATTRIBUTION_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_attribution.csv"
BY_YEAR_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_year.csv"
BY_DIRECTION_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_direction.csv"
BY_SIGNAL_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_signal.csv"
BY_PRODUCT_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_product.csv"
BY_PRODUCT_PNL_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_product_pnl.csv"
BY_CORR_BIN_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_corr_bin.csv"
BY_REGIME_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_daily_regime.csv"
BY_MONTH_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_month.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary.json"


def load_daily(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df.sort_values("date", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def to_numeric_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    return df


def product_from_vt_symbol(vt_symbol: str) -> str:
    symbol, _, exchange = str(vt_symbol).partition(".")
    match = re.match(r"([A-Za-z]+)", symbol)
    product = match.group(1) if match else symbol
    return f"{product}.{exchange}" if exchange else product


def build_gate_events() -> pd.DataFrame:
    snapshot_df = pd.read_csv(FLOOR35_SNAPSHOT_PATH)
    snapshot_df["date"] = pd.to_datetime(snapshot_df["date"])
    numeric_columns = [
        "is_opened",
        "selected_volume",
        "selected_volume_ungated",
        "same_direction_correlation_gate_enabled",
        "same_direction_correlation_gate_weight",
        "same_direction_correlation_active_count",
        "same_direction_correlation_corr_count",
        "same_direction_correlation_max_corr",
        "same_direction_correlation_avg_corr",
        "active_positions_before",
        "selection_pairwise_score",
        "selection_pairwise_rank",
        "selection_pairwise_feature_ret_20d_zscore_120",
        "selection_pairwise_feature_close_position_60d_cs_zscore_1d",
        "selection_pairwise_feature_range_pct_zscore_120",
        "selection_pairwise_volume_tilt_multiplier",
        "selection_pairwise_volume_tilt_group_size",
        "selection_pairwise_volume_tilt_top_gap",
        "selection_pairwise_volume_tilt_score_gap",
    ]
    snapshot_df = to_numeric_columns(snapshot_df, numeric_columns)

    opened_df = snapshot_df[
        (snapshot_df["entry_context"] == "flat_entry")
        & (snapshot_df["is_opened"] == 1)
        & (snapshot_df["same_direction_correlation_gate_enabled"] == 1)
        & (snapshot_df["selected_volume_ungated"] > 0)
    ].copy()
    opened_df["gate_triggered"] = opened_df["same_direction_correlation_gate_weight"] < 0.999999
    opened_df["volume_cut"] = (
        opened_df["selected_volume_ungated"] - opened_df["selected_volume"]
    ).clip(lower=0.0)
    opened_df["cut_ratio"] = np.where(
        opened_df["selected_volume_ungated"] > 0,
        opened_df["volume_cut"] / opened_df["selected_volume_ungated"],
        0.0,
    )
    opened_df["year"] = opened_df["date"].dt.year
    opened_df["month"] = opened_df["date"].dt.to_period("M").astype(str)
    opened_df["product"] = opened_df["product_vt_symbol"].astype(str)
    opened_df["corr_bin"] = pd.cut(
        opened_df["same_direction_correlation_max_corr"],
        bins=[-np.inf, 0.0, 0.4, 0.6, 0.8, np.inf],
        labels=["<=0", "0-0.4", "0.4-0.6", "0.6-0.8", ">=0.8"],
        right=False,
    ).astype(str)
    opened_df["active_count_bin"] = pd.cut(
        opened_df["same_direction_correlation_active_count"],
        bins=[-np.inf, 0.0, 1.0, 3.0, 5.0, np.inf],
        labels=["0", "1", "2-3", "4-5", "6+"],
        right=True,
    ).astype(str)

    return opened_df[opened_df["gate_triggered"]].copy()


def aggregate_events(event_df: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    grouped = event_df.groupby(group_columns, dropna=False).agg(
        event_count=("product", "size"),
        product_count=("product", "nunique"),
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
        avg_pairwise_score=("selection_pairwise_score", "mean"),
        avg_pairwise_rank=("selection_pairwise_rank", "mean"),
    )
    grouped.reset_index(inplace=True)
    grouped["volume_cut_share"] = np.where(
        grouped["selected_volume_ungated"] > 0,
        grouped["volume_cut"] / grouped["selected_volume_ungated"],
        0.0,
    )
    grouped.sort_values(
        ["volume_cut", "event_count", *group_columns],
        ascending=[False, False, *([True] * len(group_columns))],
        inplace=True,
    )
    grouped.reset_index(drop=True, inplace=True)
    return grouped


def build_daily_attribution(event_df: pd.DataFrame) -> pd.DataFrame:
    current_daily = load_daily(CURRENT_DAILY_PATH)
    floor_daily = load_daily(FLOOR35_DAILY_PATH)
    daily_df = current_daily.merge(
        floor_daily,
        on="date",
        suffixes=("_current", "_floor35"),
        how="inner",
    )
    daily_df["delta_net_pnl"] = daily_df["net_pnl_floor35"] - daily_df["net_pnl_current"]
    daily_df["delta_balance"] = daily_df["balance_floor35"] - daily_df["balance_current"]
    daily_df["delta_trade_count"] = daily_df["trade_count_floor35"] - daily_df["trade_count_current"]
    daily_df["delta_slippage"] = daily_df["slippage_floor35"] - daily_df["slippage_current"]
    daily_df["delta_ddpercent"] = daily_df["ddpercent_floor35"] - daily_df["ddpercent_current"]
    daily_df["year"] = daily_df["date"].dt.year
    daily_df["month"] = daily_df["date"].dt.to_period("M").astype(str)

    event_by_date = event_df.groupby("date").agg(
        gate_event_count=("product", "size"),
        gate_product_count=("product", "nunique"),
        gate_selected_volume=("selected_volume", "sum"),
        gate_ungated_volume=("selected_volume_ungated", "sum"),
        gate_volume_cut=("volume_cut", "sum"),
        gate_avg_weight=("same_direction_correlation_gate_weight", "mean"),
        gate_min_weight=("same_direction_correlation_gate_weight", "min"),
        gate_max_corr=("same_direction_correlation_max_corr", "max"),
        gate_avg_corr=("same_direction_correlation_max_corr", "mean"),
        gate_avg_active_count=("same_direction_correlation_active_count", "mean"),
    )
    event_by_date.reset_index(inplace=True)

    merged = daily_df.merge(event_by_date, on="date", how="left")
    fill_columns = [
        "gate_event_count",
        "gate_product_count",
        "gate_selected_volume",
        "gate_ungated_volume",
        "gate_volume_cut",
        "gate_avg_weight",
        "gate_min_weight",
        "gate_max_corr",
        "gate_avg_corr",
        "gate_avg_active_count",
    ]
    for column in fill_columns:
        merged[column] = merged[column].fillna(0.0)
    merged["same_day_gate"] = merged["gate_event_count"] > 0
    merged["gate_event_count_20d"] = merged["gate_event_count"].rolling(20, min_periods=1).sum()
    merged["gate_volume_cut_20d"] = merged["gate_volume_cut"].rolling(20, min_periods=1).sum()
    merged["gate_event_count_60d"] = merged["gate_event_count"].rolling(60, min_periods=1).sum()
    merged["gate_volume_cut_60d"] = merged["gate_volume_cut"].rolling(60, min_periods=1).sum()
    merged["recent_gate_20d"] = merged["gate_event_count_20d"] > 0
    merged["recent_gate_cut_20d"] = merged["gate_volume_cut_20d"] > 0
    merged["recent_gate_60d"] = merged["gate_event_count_60d"] > 0
    return merged


def summarize_daily_regime(daily_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for flag_column in ["same_day_gate", "recent_gate_20d", "recent_gate_cut_20d", "recent_gate_60d"]:
        for flag_value, part in daily_df.groupby(flag_column):
            rows.append(
                {
                    "regime": flag_column,
                    "flag": bool(flag_value),
                    "day_count": int(len(part)),
                    "sum_delta_net_pnl": float(part["delta_net_pnl"].sum()),
                    "mean_delta_net_pnl": float(part["delta_net_pnl"].mean()),
                    "median_delta_net_pnl": float(part["delta_net_pnl"].median()),
                    "positive_day_rate": float((part["delta_net_pnl"] > 0).mean()),
                    "sum_delta_trade_count": float(part["delta_trade_count"].sum()),
                    "sum_delta_slippage": float(part["delta_slippage"].sum()),
                    "last_delta_balance": float(part["delta_balance"].iloc[-1]),
                }
            )
    result_df = pd.DataFrame(rows)
    result_df.sort_values(["regime", "flag"], inplace=True)
    result_df.reset_index(drop=True, inplace=True)
    return result_df


def build_month_frame(daily_df: pd.DataFrame) -> pd.DataFrame:
    month_df = daily_df.groupby("month").agg(
        day_count=("date", "size"),
        sum_delta_net_pnl=("delta_net_pnl", "sum"),
        last_delta_balance=("delta_balance", "last"),
        sum_delta_trade_count=("delta_trade_count", "sum"),
        sum_delta_slippage=("delta_slippage", "sum"),
        gate_event_count=("gate_event_count", "sum"),
        gate_volume_cut=("gate_volume_cut", "sum"),
        max_gate_corr=("gate_max_corr", "max"),
        max_gate_event_count_20d=("gate_event_count_20d", "max"),
        max_gate_volume_cut_20d=("gate_volume_cut_20d", "max"),
    )
    month_df.reset_index(inplace=True)
    month_df.sort_values(["sum_delta_net_pnl", "month"], ascending=[False, True], inplace=True)
    month_df.reset_index(drop=True, inplace=True)
    return month_df


def build_product_pnl_frame() -> pd.DataFrame:
    usecols = ["date", "vt_symbol", "trade_count", "slippage", "net_pnl"]
    current_df = pd.read_csv(CURRENT_POSITION_CHANGE_PATH, usecols=usecols)
    floor_df = pd.read_csv(FLOOR35_POSITION_CHANGE_PATH, usecols=usecols)
    for df in (current_df, floor_df):
        df["product"] = df["vt_symbol"].map(product_from_vt_symbol)
    current_product = current_df.groupby("product").agg(
        net_pnl_current=("net_pnl", "sum"),
        trade_count_current=("trade_count", "sum"),
        slippage_current=("slippage", "sum"),
    )
    floor_product = floor_df.groupby("product").agg(
        net_pnl_floor35=("net_pnl", "sum"),
        trade_count_floor35=("trade_count", "sum"),
        slippage_floor35=("slippage", "sum"),
    )
    merged = current_product.merge(floor_product, left_index=True, right_index=True, how="outer").fillna(0.0)
    merged.reset_index(inplace=True)
    merged["delta_net_pnl"] = merged["net_pnl_floor35"] - merged["net_pnl_current"]
    merged["delta_trade_count"] = merged["trade_count_floor35"] - merged["trade_count_current"]
    merged["delta_slippage"] = merged["slippage_floor35"] - merged["slippage_current"]
    merged.sort_values(["delta_net_pnl", "product"], ascending=[False, True], inplace=True)
    merged.reset_index(drop=True, inplace=True)
    return merged


def top_records(df: pd.DataFrame, n: int = 10) -> list[dict[str, Any]]:
    return df.head(n).to_dict(orient="records")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    gate_events = build_gate_events()
    daily_df = build_daily_attribution(gate_events)
    by_year = aggregate_events(gate_events, ["year"])
    by_direction = aggregate_events(gate_events, ["direction"])
    by_signal = aggregate_events(gate_events, ["signal"])
    by_product = aggregate_events(gate_events, ["product"])
    by_corr_bin = aggregate_events(gate_events, ["corr_bin", "active_count_bin"])
    by_regime = summarize_daily_regime(daily_df)
    by_month = build_month_frame(daily_df)
    by_product_pnl = build_product_pnl_frame()

    gate_events.to_csv(GATE_EVENTS_CSV_PATH, index=False, encoding="utf-8-sig")
    daily_df.to_csv(DAILY_ATTRIBUTION_CSV_PATH, index=False, encoding="utf-8-sig")
    by_year.to_csv(BY_YEAR_CSV_PATH, index=False, encoding="utf-8-sig")
    by_direction.to_csv(BY_DIRECTION_CSV_PATH, index=False, encoding="utf-8-sig")
    by_signal.to_csv(BY_SIGNAL_CSV_PATH, index=False, encoding="utf-8-sig")
    by_product.to_csv(BY_PRODUCT_CSV_PATH, index=False, encoding="utf-8-sig")
    by_product_pnl.to_csv(BY_PRODUCT_PNL_CSV_PATH, index=False, encoding="utf-8-sig")
    by_corr_bin.to_csv(BY_CORR_BIN_CSV_PATH, index=False, encoding="utf-8-sig")
    by_regime.to_csv(BY_REGIME_CSV_PATH, index=False, encoding="utf-8-sig")
    by_month.to_csv(BY_MONTH_CSV_PATH, index=False, encoding="utf-8-sig")

    summary_payload = {
        "analysis": OUTPUT_PREFIX,
        "source_current_prefix": CURRENT_PREFIX,
        "source_floor35_prefix": FLOOR35_PREFIX,
        "daily_count": int(len(daily_df)),
        "gate_triggered_open_count": int(len(gate_events)),
        "gate_triggered_dates": int(gate_events["date"].nunique()),
        "gate_triggered_products": int(gate_events["product"].nunique()),
        "gate_selected_volume": float(gate_events["selected_volume"].sum()),
        "gate_ungated_volume": float(gate_events["selected_volume_ungated"].sum()),
        "gate_volume_cut": float(gate_events["volume_cut"].sum()),
        "gate_volume_cut_share": float(
            gate_events["volume_cut"].sum() / gate_events["selected_volume_ungated"].sum()
            if gate_events["selected_volume_ungated"].sum() > 0
            else 0.0
        ),
        "avg_gate_weight": float(gate_events["same_direction_correlation_gate_weight"].mean()),
        "avg_max_corr": float(gate_events["same_direction_correlation_max_corr"].mean()),
        "max_corr": float(gate_events["same_direction_correlation_max_corr"].max()),
        "avg_active_count": float(gate_events["same_direction_correlation_active_count"].mean()),
        "final_delta_balance": float(daily_df["delta_balance"].iloc[-1]),
        "sum_delta_net_pnl": float(daily_df["delta_net_pnl"].sum()),
        "sum_delta_trade_count": float(daily_df["delta_trade_count"].sum()),
        "sum_delta_slippage": float(daily_df["delta_slippage"].sum()),
        "top_gate_products_by_cut": top_records(by_product, 12),
        "top_product_pnl_improvements": top_records(by_product_pnl, 12),
        "top_product_pnl_deteriorations": by_product_pnl.sort_values(["delta_net_pnl", "product"]).head(12).to_dict(
            orient="records"
        ),
        "top_positive_months": top_records(by_month.sort_values(["sum_delta_net_pnl", "month"], ascending=[False, True])),
        "top_negative_months": top_records(by_month.sort_values(["sum_delta_net_pnl", "month"], ascending=[True, True])),
        "daily_regime_summary": by_regime.to_dict(orient="records"),
        "event_by_year": by_year.to_dict(orient="records"),
        "event_by_direction": by_direction.to_dict(orient="records"),
    }
    SUMMARY_JSON_PATH.write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print(f"summary json: {SUMMARY_JSON_PATH}")
    print(f"gate events csv: {GATE_EVENTS_CSV_PATH}")
    print(f"daily attribution csv: {DAILY_ATTRIBUTION_CSV_PATH}")
    print(f"by product pnl csv: {BY_PRODUCT_PNL_CSV_PATH}")
    print(json.dumps(summary_payload, ensure_ascii=False, indent=2, default=str))
    print("\n[event by year]")
    print(by_year.to_string(index=False))
    print("\n[event by direction]")
    print(by_direction.to_string(index=False))
    print("\n[top gate products]")
    print(by_product.head(12).to_string(index=False))
    print("\n[top product pnl improvements]")
    print(by_product_pnl.head(12).to_string(index=False))
    print("\n[top product pnl deteriorations]")
    print(by_product_pnl.sort_values(["delta_net_pnl", "product"]).head(12).to_string(index=False))
    print("\n[daily regime]")
    print(by_regime.to_string(index=False))


if __name__ == "__main__":
    main()
