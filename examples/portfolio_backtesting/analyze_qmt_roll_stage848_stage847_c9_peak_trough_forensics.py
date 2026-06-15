from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage848"
MODEL_TAG = "stage848_stage847_c9_peak_trough_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage848_stage847_c9_peak_trough_forensics"

WINDOW_START = pd.Timestamp("2022-03-09")
WINDOW_END = pd.Timestamp("2022-06-29")

STAGE830_PREFIX = "qmt_roll_stage830_stage827_c2_broker10_margin_cap"
STAGE830_TAG = "stage830_stage827_c2_broker10_margin_cap_v1"
STAGE847_PREFIX = "qmt_roll_stage847_stage830_c4_stop_retry_engine"
STAGE847_TAG = "stage847_stage830_c4_stop_retry_engine_v1"

C4_ARM = "stage830_stage819_c2_broker10_100_cap"
C9_ARM = "stage847_stage819_c4_05r_stop_retry_once"

CURVE_PATH = OUTPUT_DIR / f"{STAGE847_PREFIX}_curve_{STAGE847_TAG}.csv"
C4_TRADES_PATH = OUTPUT_DIR / f"{STAGE830_PREFIX}_trades_{STAGE830_TAG}.csv"
C4_CLOSED_PATH = OUTPUT_DIR / f"{STAGE830_PREFIX}_closed_lots_{STAGE830_TAG}.csv"
C9_TRADES_PATH = OUTPUT_DIR / f"{STAGE847_PREFIX}_trades_{STAGE847_TAG}.csv"
C9_CLOSED_PATH = OUTPUT_DIR / f"{STAGE847_PREFIX}_closed_lots_{STAGE847_TAG}.csv"
C9_STOP_RETRY_EVENTS_PATH = OUTPUT_DIR / f"{STAGE847_PREFIX}_stop_retry_events_{STAGE847_TAG}.csv"

DAILY_DELTA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_delta_{MODEL_TAG}.csv"
WINDOW_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_summary_{MODEL_TAG}.csv"
CLOSED_DELTA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_direction_pnl_delta_{MODEL_TAG}.csv"
STOP_RETRY_WINDOW_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stop_retry_window_events_{MODEL_TAG}.csv"
STOP_RETRY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stop_retry_window_summary_{MODEL_TAG}.csv"
POSITION_PRESSURE_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_position_pressure_daily_{MODEL_TAG}.csv"
POSITION_PRESSURE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_position_pressure_summary_{MODEL_TAG}.csv"
PRESSURE_DAYS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pressure_days_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
PATH_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_peak_trough_path_chart_{MODEL_TAG}.png"
PNL_DELTA_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_direction_pnl_delta_chart_{MODEL_TAG}.png"
CLUSTER_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cluster_pressure_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stop_retry_window_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stop_retry_window_atlas_page{{page:03d}}_{MODEL_TAG}.png"

PER_PAGE = 4
MAX_ATLAS_ROWS = 16
OPENING_RANGE_BARS = 15


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _normal_date(value: Any) -> pd.Timestamp:
    if pd.isna(value):
        return pd.NaT
    text = str(value)
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        ts = pd.to_datetime(text[:10], errors="coerce")
    else:
        ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    if getattr(ts, "tzinfo", None) is not None:
        ts = pd.Timestamp(ts).tz_convert("Asia/Shanghai").tz_localize(None)
    return pd.Timestamp(ts).normalize()


def _normal_dt(value: Any) -> pd.Timestamp:
    if pd.isna(value):
        return pd.NaT
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    if getattr(ts, "tzinfo", None) is not None:
        ts = pd.Timestamp(ts).tz_convert("Asia/Shanghai").tz_localize(None)
    return pd.Timestamp(ts)


def _numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _product_from_vt(vt_symbol: Any) -> str:
    text = str(vt_symbol)
    if "." not in text:
        return text
    contract, exchange = text.split(".", 1)
    letters = "".join(ch for ch in contract if ch.isalpha())
    return f"{letters}.{exchange}" if letters else text


def _prepare_curve() -> pd.DataFrame:
    curve = _load_csv(CURVE_PATH)
    curve = curve[curve["arm"].astype(str).isin([C4_ARM, C9_ARM])].copy()
    curve["date"] = curve["date"].map(_normal_date)
    curve = curve.dropna(subset=["date"]).sort_values(["arm", "date"]).reset_index(drop=True)
    return _numeric(
        curve,
        [
            "account_equity",
            "nav",
            "drawdown_pct",
            "broker10_margin_to_equity_pct",
            "net_pnl",
            "trade_count",
            "total_slippage",
            "rebased_equity",
            "broker10_margin_to_rebased_equity_pct",
        ],
    )


def _daily_delta(curve: pd.DataFrame) -> pd.DataFrame:
    keep = [
        "date",
        "account_equity",
        "nav",
        "drawdown_pct",
        "broker10_margin_to_equity_pct",
        "net_pnl",
        "trade_count",
        "total_slippage",
        "arm",
        "variant",
        "profile",
    ]
    keep = [column for column in keep if column in curve.columns]
    c4 = curve[curve["arm"].astype(str).eq(C4_ARM)][keep].copy()
    c9 = curve[curve["arm"].astype(str).eq(C9_ARM)][keep].copy()
    c4 = c4.rename(columns={column: f"{column}_C4" for column in keep if column != "date"})
    c9 = c9.rename(columns={column: f"{column}_C9" for column in keep if column != "date"})
    daily = c4.merge(c9, on="date", how="inner").sort_values("date").reset_index(drop=True)
    for metric in [
        "account_equity",
        "nav",
        "drawdown_pct",
        "broker10_margin_to_equity_pct",
        "net_pnl",
        "trade_count",
        "total_slippage",
    ]:
        c4_col = f"{metric}_C4"
        c9_col = f"{metric}_C9"
        if c4_col in daily.columns and c9_col in daily.columns:
            daily[f"{metric}_delta_C9_minus_C4"] = daily[c9_col] - daily[c4_col]
    daily["in_peak_trough_window"] = daily["date"].between(WINDOW_START, WINDOW_END, inclusive="both").astype(int)
    return daily


def _row_on_or_before(frame: pd.DataFrame, date: pd.Timestamp) -> pd.Series:
    eligible = frame[frame["date"].le(date)].copy()
    if eligible.empty:
        raise RuntimeError(f"No curve row on or before {date:%Y-%m-%d}")
    return eligible.sort_values("date").iloc[-1]


def _window_summary(curve: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for arm, group in curve.groupby("arm", dropna=False):
        data = group.sort_values("date").reset_index(drop=True)
        window = data[data["date"].between(WINDOW_START, WINDOW_END, inclusive="both")].copy()
        if window.empty:
            continue
        peak = _row_on_or_before(data, WINDOW_START)
        trough = _row_on_or_before(data, WINDOW_END)
        max_equity_row = window.loc[window["account_equity"].idxmax()]
        min_equity_row = window.loc[window["account_equity"].idxmin()]
        rows.append(
            {
                "arm": str(arm),
                "window_start": WINDOW_START.date().isoformat(),
                "window_end": WINDOW_END.date().isoformat(),
                "peak_date_fixed": pd.Timestamp(peak["date"]).date().isoformat(),
                "trough_date_fixed": pd.Timestamp(trough["date"]).date().isoformat(),
                "peak_equity_fixed": float(peak["account_equity"]),
                "trough_equity_fixed": float(trough["account_equity"]),
                "peak_to_trough_equity_change": float(trough["account_equity"] - peak["account_equity"]),
                "peak_to_trough_return_pct": float((trough["account_equity"] / peak["account_equity"] - 1.0) * 100.0),
                "drawdown_at_peak_pct": float(peak["drawdown_pct"]),
                "drawdown_at_trough_pct": float(trough["drawdown_pct"]),
                "window_min_drawdown_pct": float(window["drawdown_pct"].min()),
                "window_max_broker10_pct": float(window["broker10_margin_to_equity_pct"].max()),
                "window_p95_broker10_pct": float(window["broker10_margin_to_equity_pct"].quantile(0.95)),
                "window_cum_net_pnl": float(window["net_pnl"].sum()),
                "window_trade_count": float(window["trade_count"].sum()),
                "window_slippage": float(window["total_slippage"].sum()),
                "window_max_equity_date": pd.Timestamp(max_equity_row["date"]).date().isoformat(),
                "window_max_equity": float(max_equity_row["account_equity"]),
                "window_min_equity_date": pd.Timestamp(min_equity_row["date"]).date().isoformat(),
                "window_min_equity": float(min_equity_row["account_equity"]),
            }
        )
    summary = pd.DataFrame(rows)
    if {C4_ARM, C9_ARM}.issubset(set(summary["arm"].astype(str))):
        c4 = summary[summary["arm"].eq(C4_ARM)].iloc[0]
        c9 = summary[summary["arm"].eq(C9_ARM)].iloc[0]
        delta: dict[str, Any] = {"arm": "delta_C9_minus_C4"}
        for column in summary.columns:
            if column == "arm":
                continue
            if pd.api.types.is_numeric_dtype(summary[column]):
                delta[column] = float(c9[column] - c4[column])
            else:
                delta[column] = ""
        summary = pd.concat([summary, pd.DataFrame([delta])], ignore_index=True, sort=False)
    return summary


def _prepare_closed(path: Path, arm: str) -> pd.DataFrame:
    data = _load_csv(path).copy()
    if "arm" in data.columns:
        data = data[data["arm"].astype(str).eq(arm)].copy()
    for column in ("entry_date", "exit_date"):
        if column in data.columns:
            data[column] = data[column].map(_normal_date)
    data["product"] = data["vt_symbol"].map(_product_from_vt)
    data["product_direction"] = data["product"].astype(str) + " " + data["direction"].astype(str)
    return _numeric(
        data,
        [
            "entry_price",
            "exit_price",
            "volume",
            "size",
            "realized_pnl",
            "risk_amount",
            "r_multiple",
            "target_risk_amount",
            "selected_volume",
            "stop_distance",
        ],
    )


def _closed_summary(closed: pd.DataFrame, prefix: str) -> pd.DataFrame:
    data = closed.copy()
    data["active_overlap"] = (
        data["entry_date"].le(WINDOW_END) & data["exit_date"].ge(WINDOW_START)
    ).astype(int)
    data["entry_in_window"] = data["entry_date"].between(WINDOW_START, WINDOW_END, inclusive="both").astype(int)
    data["exit_in_window"] = data["exit_date"].between(WINDOW_START, WINDOW_END, inclusive="both").astype(int)
    active = data[data["active_overlap"].eq(1)].copy()
    if active.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for (product, direction), group in active.groupby(["product", "direction"], dropna=False):
        exits = group[group["exit_in_window"].eq(1)]
        entries = group[group["entry_in_window"].eq(1)]
        rows.append(
            {
                "product": str(product),
                "direction": str(direction),
                f"active_overlap_lots_{prefix}": int(len(group)),
                f"entry_in_window_lots_{prefix}": int(len(entries)),
                f"exit_in_window_lots_{prefix}": int(len(exits)),
                f"active_overlap_full_life_pnl_{prefix}": float(pd.to_numeric(group["realized_pnl"], errors="coerce").sum()),
                f"exit_in_window_realized_pnl_{prefix}": float(pd.to_numeric(exits["realized_pnl"], errors="coerce").sum()),
                f"entry_in_window_risk_amount_{prefix}": float(pd.to_numeric(entries["risk_amount"], errors="coerce").sum()),
                f"exit_in_window_winners_{prefix}": int(pd.to_numeric(exits["realized_pnl"], errors="coerce").gt(0).sum()),
                f"exit_in_window_losers_{prefix}": int(pd.to_numeric(exits["realized_pnl"], errors="coerce").lt(0).sum()),
            }
        )
    return pd.DataFrame(rows)


def _closed_delta(c4_closed: pd.DataFrame, c9_closed: pd.DataFrame) -> pd.DataFrame:
    c4 = _closed_summary(c4_closed, "C4")
    c9 = _closed_summary(c9_closed, "C9")
    if c4.empty and c9.empty:
        return pd.DataFrame()
    merged = c4.merge(c9, on=["product", "direction"], how="outer").fillna(0)
    for metric in [
        "active_overlap_lots",
        "entry_in_window_lots",
        "exit_in_window_lots",
        "active_overlap_full_life_pnl",
        "exit_in_window_realized_pnl",
        "entry_in_window_risk_amount",
        "exit_in_window_winners",
        "exit_in_window_losers",
    ]:
        merged[f"{metric}_delta_C9_minus_C4"] = merged.get(f"{metric}_C9", 0) - merged.get(f"{metric}_C4", 0)
    merged["abs_exit_pnl_delta"] = merged["exit_in_window_realized_pnl_delta_C9_minus_C4"].abs()
    return merged.sort_values("abs_exit_pnl_delta", ascending=False).reset_index(drop=True)


def _prepare_stop_retry_events(c9_closed: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    events = _load_csv(C9_STOP_RETRY_EVENTS_PATH).copy()
    events["datetime_norm"] = events["datetime"].map(_normal_dt)
    events["entry_date"] = events["datetime_norm"].map(_normal_date)
    events["product"] = events["product_vt_symbol"].astype(str)
    events["product_direction"] = events["product"].astype(str) + " " + events["direction"].astype(str)
    events = _numeric(
        events,
        [
            "entry_price",
            "stop_price",
            "progress_price",
            "risk_price",
            "stop_r",
            "max_retries",
            "volume",
            "first_stop_bar_index",
            "reentry_bar_index",
            "retry_failed_bar_index",
            "retry_reentered",
            "retry_failed",
            "final_exit_price",
        ],
    )
    window_events = events[events["entry_date"].between(WINDOW_START, WINDOW_END, inclusive="both")].copy()
    if window_events.empty:
        return window_events, pd.DataFrame()

    lots = c9_closed.copy()
    lots["entry_date_key"] = lots["entry_date"].dt.strftime("%Y-%m-%d").fillna("")
    lots["event_key"] = (
        lots["vt_symbol"].astype(str)
        + "|"
        + lots["direction"].astype(str)
        + "|"
        + lots["entry_date_key"]
    )
    lot_by_trade = lots[["open_trade_id", "realized_pnl", "r_multiple", "exit_reason"]].drop_duplicates("open_trade_id")
    lot_by_trade = lot_by_trade.rename(
        columns={
            "open_trade_id": "trade_id",
            "realized_pnl": "initial_open_trade_realized_pnl",
            "r_multiple": "initial_open_trade_r_multiple",
            "exit_reason": "initial_open_trade_exit_reason",
        }
    )
    window_events = window_events.merge(lot_by_trade, on="trade_id", how="left")
    window_events["event_key"] = (
        window_events["vt_symbol"].astype(str)
        + "|"
        + window_events["direction"].astype(str)
        + "|"
        + window_events["entry_date"].dt.strftime("%Y-%m-%d")
    )
    same_key = (
        lots.groupby("event_key", dropna=False)
        .agg(
            same_key_lots=("lot_id", "size"),
            same_key_realized_pnl=("realized_pnl", "sum"),
            same_key_r_multiple=("r_multiple", "sum"),
            same_key_exit_reasons=("exit_reason", lambda s: "|".join(sorted(set(str(v) for v in s.dropna())))),
        )
        .reset_index()
    )
    window_events = window_events.merge(same_key, on="event_key", how="left")

    rows: list[dict[str, Any]] = []
    for keys, group in window_events.groupby(["final_state", "product", "direction"], dropna=False):
        rows.append(
            {
                "final_state": str(keys[0]),
                "product": str(keys[1]),
                "direction": str(keys[2]),
                "events": int(len(group)),
                "volume": float(pd.to_numeric(group["volume"], errors="coerce").sum()),
                "reentered": int(pd.to_numeric(group["retry_reentered"], errors="coerce").fillna(0).sum()),
                "retry_failed": int(pd.to_numeric(group["retry_failed"], errors="coerce").fillna(0).sum()),
                "median_first_stop_bar": float(pd.to_numeric(group["first_stop_bar_index"], errors="coerce").median()),
                "initial_open_trade_pnl": float(pd.to_numeric(group["initial_open_trade_realized_pnl"], errors="coerce").sum()),
                "same_key_total_pnl": float(pd.to_numeric(group["same_key_realized_pnl"], errors="coerce").sum()),
                "same_key_total_r": float(pd.to_numeric(group["same_key_r_multiple"], errors="coerce").sum()),
            }
        )
    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary["abs_same_key_total_pnl"] = summary["same_key_total_pnl"].abs()
        summary = summary.sort_values("abs_same_key_total_pnl", ascending=False).reset_index(drop=True)
    return window_events, summary


def _prepare_trades(path: Path) -> pd.DataFrame:
    data = _load_csv(path).copy()
    data["date"] = data["date"].map(_normal_date)
    data["datetime_norm"] = data["datetime"].map(_normal_dt)
    data["product"] = data["vt_symbol"].map(_product_from_vt)
    return _numeric(data, ["price", "volume", "signed_volume"])


def _size_map(*closed_frames: pd.DataFrame) -> dict[str, float]:
    rows = []
    for frame in closed_frames:
        if frame.empty:
            continue
        rows.append(frame[["vt_symbol", "size"]].dropna())
    if not rows:
        return {}
    data = pd.concat(rows, ignore_index=True, sort=False)
    data["size"] = pd.to_numeric(data["size"], errors="coerce")
    result = data.dropna(subset=["size"]).drop_duplicates("vt_symbol", keep="last")
    return {str(row.vt_symbol): float(row.size) for row in result.itertuples(index=False)}


def _position_pressure_for_arm(
    trades: pd.DataFrame,
    arm_label: str,
    trading_dates: pd.Series,
    sizes: dict[str, float],
) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    data = trades.sort_values(["datetime_norm", "trade_id"]).copy()
    data["position_delta"] = pd.to_numeric(data["signed_volume"], errors="coerce").fillna(0.0)
    data["last_price"] = pd.to_numeric(data["price"], errors="coerce")
    dates = pd.Series(pd.to_datetime(trading_dates, errors="coerce")).dropna().map(_normal_date).drop_duplicates()
    dates = dates[dates.between(WINDOW_START, WINDOW_END, inclusive="both")].sort_values().reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    for current_date in dates:
        upto = data[data["date"].le(current_date)].copy()
        if upto.empty:
            rows.append(
                {
                    "date": current_date,
                    "arm": arm_label,
                    "active_product_direction_count": 0,
                    "total_abs_contracts": 0.0,
                    "total_abs_exposure_proxy": 0.0,
                    "top1_product_direction": "",
                    "top1_share_pct": 0.0,
                    "top3_share_pct": 0.0,
                    "long_share_pct": 0.0,
                    "short_share_pct": 0.0,
                }
            )
            continue
        net = (
            upto.groupby("vt_symbol", dropna=False)
            .agg(position=("position_delta", "sum"), last_price=("last_price", "last"), product=("product", "last"))
            .reset_index()
        )
        net = net[np.abs(pd.to_numeric(net["position"], errors="coerce").fillna(0.0)) > 1e-9].copy()
        if net.empty:
            rows.append(
                {
                    "date": current_date,
                    "arm": arm_label,
                    "active_product_direction_count": 0,
                    "total_abs_contracts": 0.0,
                    "total_abs_exposure_proxy": 0.0,
                    "top1_product_direction": "",
                    "top1_share_pct": 0.0,
                    "top3_share_pct": 0.0,
                    "long_share_pct": 0.0,
                    "short_share_pct": 0.0,
                }
            )
            continue
        net["direction"] = np.where(net["position"].gt(0), "long", "short")
        net["abs_contracts"] = net["position"].abs()
        net["size"] = net["vt_symbol"].astype(str).map(sizes).fillna(1.0)
        net["abs_exposure_proxy"] = net["abs_contracts"] * pd.to_numeric(net["last_price"], errors="coerce").abs().fillna(0.0) * net["size"]
        grouped = (
            net.groupby(["product", "direction"], dropna=False)
            .agg(abs_contracts=("abs_contracts", "sum"), abs_exposure_proxy=("abs_exposure_proxy", "sum"))
            .reset_index()
        )
        grouped["product_direction"] = grouped["product"].astype(str) + " " + grouped["direction"].astype(str)
        grouped = grouped.sort_values("abs_exposure_proxy", ascending=False)
        total_exposure = float(grouped["abs_exposure_proxy"].sum())
        total_contracts = float(grouped["abs_contracts"].sum())
        if total_exposure <= 0:
            grouped["share_pct"] = 0.0
        else:
            grouped["share_pct"] = grouped["abs_exposure_proxy"] / total_exposure * 100.0
        top1 = grouped.iloc[0] if len(grouped) else pd.Series(dtype=object)
        long_exposure = float(grouped[grouped["direction"].eq("long")]["abs_exposure_proxy"].sum())
        short_exposure = float(grouped[grouped["direction"].eq("short")]["abs_exposure_proxy"].sum())
        rows.append(
            {
                "date": current_date,
                "arm": arm_label,
                "active_product_direction_count": int(len(grouped)),
                "total_abs_contracts": total_contracts,
                "total_abs_exposure_proxy": total_exposure,
                "top1_product_direction": str(top1.get("product_direction", "")),
                "top1_share_pct": float(top1.get("share_pct", 0.0)),
                "top3_share_pct": float(grouped.head(3)["share_pct"].sum()),
                "long_share_pct": float(long_exposure / total_exposure * 100.0) if total_exposure > 0 else 0.0,
                "short_share_pct": float(short_exposure / total_exposure * 100.0) if total_exposure > 0 else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _position_pressure_daily(
    c4_trades: pd.DataFrame,
    c9_trades: pd.DataFrame,
    daily_delta: pd.DataFrame,
    c4_closed: pd.DataFrame,
    c9_closed: pd.DataFrame,
) -> pd.DataFrame:
    sizes = _size_map(c4_closed, c9_closed)
    dates = daily_delta.loc[daily_delta["in_peak_trough_window"].eq(1), "date"]
    c4 = _position_pressure_for_arm(c4_trades, "C4", dates, sizes)
    c9 = _position_pressure_for_arm(c9_trades, "C9", dates, sizes)
    pressure = c4.merge(c9, on="date", how="outer", suffixes=("_C4", "_C9")).sort_values("date").reset_index(drop=True)
    for metric in [
        "active_product_direction_count",
        "total_abs_contracts",
        "total_abs_exposure_proxy",
        "top1_share_pct",
        "top3_share_pct",
        "long_share_pct",
        "short_share_pct",
    ]:
        pressure[f"{metric}_delta_C9_minus_C4"] = pressure.get(f"{metric}_C9", 0) - pressure.get(f"{metric}_C4", 0)
    daily_cols = [
        "date",
        "account_equity_delta_C9_minus_C4",
        "drawdown_pct_delta_C9_minus_C4",
        "broker10_margin_to_equity_pct_delta_C9_minus_C4",
        "net_pnl_delta_C9_minus_C4",
        "account_equity_C4",
        "account_equity_C9",
        "drawdown_pct_C4",
        "drawdown_pct_C9",
        "broker10_margin_to_equity_pct_C4",
        "broker10_margin_to_equity_pct_C9",
    ]
    daily_cols = [column for column in daily_cols if column in daily_delta.columns]
    return pressure.merge(daily_delta[daily_cols], on="date", how="left")


def _position_pressure_summary(pressure: pd.DataFrame) -> pd.DataFrame:
    if pressure.empty:
        return pd.DataFrame()
    rows = []
    for bucket, frame in {
        "all_window_days": pressure,
        "c9_worse_drawdown_delta_bottom_quartile": pressure[
            pressure["drawdown_pct_delta_C9_minus_C4"].le(pressure["drawdown_pct_delta_C9_minus_C4"].quantile(0.25))
        ],
        "c9_broker_delta_top_quartile": pressure[
            pressure["broker10_margin_to_equity_pct_delta_C9_minus_C4"].ge(
                pressure["broker10_margin_to_equity_pct_delta_C9_minus_C4"].quantile(0.75)
            )
        ],
        "c9_equity_delta_bottom_quartile": pressure[
            pressure["account_equity_delta_C9_minus_C4"].le(pressure["account_equity_delta_C9_minus_C4"].quantile(0.25))
        ],
    }.items():
        if frame.empty:
            continue
        rows.append(
            {
                "bucket": bucket,
                "days": int(len(frame)),
                "avg_equity_delta_C9_minus_C4": float(frame["account_equity_delta_C9_minus_C4"].mean()),
                "min_equity_delta_C9_minus_C4": float(frame["account_equity_delta_C9_minus_C4"].min()),
                "avg_drawdown_delta_C9_minus_C4": float(frame["drawdown_pct_delta_C9_minus_C4"].mean()),
                "min_drawdown_delta_C9_minus_C4": float(frame["drawdown_pct_delta_C9_minus_C4"].min()),
                "avg_broker10_delta_C9_minus_C4": float(frame["broker10_margin_to_equity_pct_delta_C9_minus_C4"].mean()),
                "max_broker10_delta_C9_minus_C4": float(frame["broker10_margin_to_equity_pct_delta_C9_minus_C4"].max()),
                "avg_top3_share_C4": float(frame["top3_share_pct_C4"].mean()),
                "avg_top3_share_C9": float(frame["top3_share_pct_C9"].mean()),
                "avg_top3_share_delta_C9_minus_C4": float(frame["top3_share_pct_delta_C9_minus_C4"].mean()),
                "avg_short_share_C4": float(frame["short_share_pct_C4"].mean()),
                "avg_short_share_C9": float(frame["short_share_pct_C9"].mean()),
            }
        )
    return pd.DataFrame(rows)


def _pressure_days(pressure: pd.DataFrame) -> pd.DataFrame:
    if pressure.empty:
        return pd.DataFrame()
    score = pressure.copy()
    score["stress_score"] = (
        -pd.to_numeric(score["account_equity_delta_C9_minus_C4"], errors="coerce").rank(pct=True)
        -pd.to_numeric(score["drawdown_pct_delta_C9_minus_C4"], errors="coerce").rank(pct=True)
        + pd.to_numeric(score["broker10_margin_to_equity_pct_delta_C9_minus_C4"], errors="coerce").rank(pct=True)
    )
    keep = [
        "date",
        "stress_score",
        "account_equity_C4",
        "account_equity_C9",
        "account_equity_delta_C9_minus_C4",
        "drawdown_pct_C4",
        "drawdown_pct_C9",
        "drawdown_pct_delta_C9_minus_C4",
        "broker10_margin_to_equity_pct_C4",
        "broker10_margin_to_equity_pct_C9",
        "broker10_margin_to_equity_pct_delta_C9_minus_C4",
        "top1_product_direction_C4",
        "top1_product_direction_C9",
        "top3_share_pct_C4",
        "top3_share_pct_C9",
        "short_share_pct_C4",
        "short_share_pct_C9",
        "total_abs_exposure_proxy_C4",
        "total_abs_exposure_proxy_C9",
    ]
    return score.sort_values("stress_score", ascending=False)[keep].head(20).reset_index(drop=True)


def _plot_path(daily_delta: pd.DataFrame) -> None:
    data = daily_delta[daily_delta["in_peak_trough_window"].eq(1)].copy()
    if data.empty:
        return
    fig, axes = plt.subplots(3, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    axes[0].plot(data["date"], data["account_equity_C4"], label="C4 broker10 cap", color="#16a34a")
    axes[0].plot(data["date"], data["account_equity_C9"], label="C9 stop/retry", color="#7c3aed")
    axes[1].plot(data["date"], data["drawdown_pct_C4"], label="C4", color="#16a34a")
    axes[1].plot(data["date"], data["drawdown_pct_C9"], label="C9", color="#7c3aed")
    axes[2].plot(data["date"], data["broker10_margin_to_equity_pct_C4"], label="C4", color="#16a34a")
    axes[2].plot(data["date"], data["broker10_margin_to_equity_pct_C9"], label="C9", color="#7c3aed")
    axes[0].set_title("Stage848 peak-trough equity path")
    axes[1].set_title("Drawdown pct")
    axes[2].set_title("Broker10 margin to equity pct")
    for ax in axes:
        ax.axvline(WINDOW_START, color="#111827", linewidth=0.8, alpha=0.45)
        ax.axvline(WINDOW_END, color="#111827", linewidth=0.8, alpha=0.45)
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best")
    fig.savefig(PATH_CHART_PATH, dpi=150)
    plt.close(fig)


def _plot_pnl_delta(closed_delta: pd.DataFrame) -> None:
    if closed_delta.empty:
        return
    data = closed_delta.copy()
    data["label"] = data["product"].astype(str) + " " + data["direction"].astype(str)
    data = data.reindex(data["exit_in_window_realized_pnl_delta_C9_minus_C4"].abs().sort_values(ascending=False).index)
    data = data.head(24).iloc[::-1]
    colors = np.where(data["exit_in_window_realized_pnl_delta_C9_minus_C4"].ge(0), "#16a34a", "#dc2626")
    fig, ax = plt.subplots(figsize=(13, 9), constrained_layout=True)
    ax.barh(data["label"], data["exit_in_window_realized_pnl_delta_C9_minus_C4"], color=colors, alpha=0.82)
    ax.axvline(0, color="#111827", linewidth=0.8)
    ax.set_title("Stage848 C9 minus C4 exit-in-window realized PnL by product-direction")
    ax.grid(True, axis="x", alpha=0.25)
    fig.savefig(PNL_DELTA_CHART_PATH, dpi=150)
    plt.close(fig)


def _plot_cluster_pressure(pressure: pd.DataFrame) -> None:
    if pressure.empty:
        return
    data = pressure.copy()
    fig, axes = plt.subplots(3, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    axes[0].plot(data["date"], data["account_equity_delta_C9_minus_C4"], color="#7c3aed", label="equity delta C9-C4")
    axes[0].axhline(0, color="#111827", linewidth=0.8)
    axes[1].plot(
        data["date"],
        data["broker10_margin_to_equity_pct_delta_C9_minus_C4"],
        color="#dc2626",
        label="broker10 delta C9-C4",
    )
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[2].plot(data["date"], data["top3_share_pct_C4"], color="#16a34a", label="C4 top3 share")
    axes[2].plot(data["date"], data["top3_share_pct_C9"], color="#7c3aed", label="C9 top3 share")
    axes[0].set_title("C9-C4 equity delta")
    axes[1].set_title("C9-C4 broker10 delta")
    axes[2].set_title("Product-direction concentration proxy")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best")
    fig.savefig(CLUSTER_CHART_PATH, dpi=150)
    plt.close(fig)


def _select_atlas_events(window_events: pd.DataFrame) -> pd.DataFrame:
    if window_events.empty:
        return pd.DataFrame()
    selected: list[pd.DataFrame] = []
    for state in ["flat_no_reentry", "flat_retry_failed", "open_after_reentry"]:
        part = window_events[window_events["final_state"].astype(str).eq(state)].copy()
        if part.empty:
            continue
        if "same_key_realized_pnl" in part.columns:
            part = part.sort_values("same_key_realized_pnl")
        else:
            part = part.sort_values("entry_date")
        part["atlas_reason"] = state
        selected.append(part.head(6))
    if not selected:
        return pd.DataFrame()
    return pd.concat(selected, ignore_index=True, sort=False).drop_duplicates(["vt_symbol", "entry_date", "direction"]).head(MAX_ATLAS_ROWS)


def _plot_event_atlas(window_events: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_events(window_events)
    if selected.empty:
        return [], pd.DataFrame()
    vt_symbols = set(selected["vt_symbol"].astype(str).dropna().unique())
    minute_bars = s825._load_minute_bars(vt_symbols)
    minute_by_symbol = s825._minute_groups(minute_bars)
    pages = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.0, 3.3 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            vt_symbol = str(row["vt_symbol"])
            entry_date = _normal_date(row["entry_date"])
            direction = str(row["direction"])
            day = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            day = day[day["bar_date"].eq(entry_date)].copy().sort_values("bar_datetime").head(280).reset_index(drop=True) if not day.empty else pd.DataFrame()
            if day.empty:
                ax.axis("off")
                ax.text(0.5, 0.5, f"missing minute bars {vt_symbol} {entry_date:%Y-%m-%d}", ha="center", va="center")
            else:
                s825._plot_candles(ax, day)
                entry_price = _safe_float(row.get("entry_price"))
                stop_price = _safe_float(row.get("stop_price"))
                progress_price = _safe_float(row.get("progress_price"))
                if np.isfinite(entry_price):
                    ax.axhline(entry_price, color="#2563eb", linewidth=0.95, label="entry/reentry")
                if np.isfinite(stop_price):
                    ax.axhline(stop_price, color="#dc2626", linestyle="--", linewidth=0.9, label="0.5R stop")
                if np.isfinite(progress_price):
                    ax.axhline(progress_price, color="#16a34a", linestyle="--", linewidth=0.85, label="0.5R progress")
                for marker_col, color, label in [
                    ("first_stop_time", "#dc2626", "first stop"),
                    ("reentry_time", "#2563eb", "reentry"),
                    ("retry_failed_time", "#7c2d12", "retry failed"),
                ]:
                    ts = _normal_dt(row.get(marker_col))
                    if pd.isna(ts):
                        continue
                    bar_ts = pd.to_datetime(day["bar_datetime"], errors="coerce")
                    matches = day.index[bar_ts.eq(ts)]
                    if len(matches):
                        ax.axvline(int(matches[0]), color=color, linewidth=0.9, alpha=0.8, label=label)
                if len(day) >= OPENING_RANGE_BARS:
                    ax.axvspan(0, OPENING_RANGE_BARS - 1, color="#fef3c7", alpha=0.18)
                ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    dedup = dict(zip(labels, handles))
                    ax.legend(dedup.values(), dedup.keys(), loc="best", fontsize=7)
                ax.grid(True, alpha=0.18)
            title = (
                f"{row.get('atlas_reason', '')} | {vt_symbol} {direction} {entry_date:%Y-%m-%d} "
                f"state={row.get('final_state', '')} same_key_pnl={_safe_float(row.get('same_key_realized_pnl')):,.0f} "
                f"initial_pnl={_safe_float(row.get('initial_open_trade_realized_pnl')):,.0f}"
            )
            ax.set_title(title, fontsize=8.1, loc="left")
            manifest.append(
                {
                    "page": page,
                    "vt_symbol": vt_symbol,
                    "entry_date": entry_date.strftime("%Y-%m-%d"),
                    "direction": direction,
                    "final_state": row.get("final_state", ""),
                    "same_key_realized_pnl": _safe_float(row.get("same_key_realized_pnl")),
                    "initial_open_trade_realized_pnl": _safe_float(row.get("initial_open_trade_realized_pnl")),
                    "first_stop_time": row.get("first_stop_time", ""),
                    "reentry_time": row.get("reentry_time", ""),
                    "retry_failed_time": row.get("retry_failed_time", ""),
                }
            )
        fig.suptitle("Stage848 C9 stop/retry events inside 2022 peak-trough window", fontsize=13)
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _write_report(
    window_summary: pd.DataFrame,
    closed_delta: pd.DataFrame,
    stop_retry_summary: pd.DataFrame,
    pressure_summary: pd.DataFrame,
    pressure_days: pd.DataFrame,
    atlas_paths: list[Path],
) -> None:
    lines = [
        "# Stage848 C9/C4 Peak-Trough Forensics",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- model_tag: `{MODEL_TAG}`",
        f"- source candidate: `{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        f"- window: `{WINDOW_START:%Y-%m-%d}` to `{WINDOW_END:%Y-%m-%d}`",
        "- Scope: read-only attribution. No strategy rule, no parameter search, no CTP/order path.",
        "",
        "## External Reference Judgment",
        "",
        "- CME order/risk education and CFTC stop-loss education support a narrow interpretation: stop orders manage execution risk but do not automatically solve portfolio survival.",
        "- vn.py is used only as the framework reference for deterministic event ordering and portfolio replay semantics.",
        "- Judgment: the C9 failure must be attributed through full-path capital, product-direction concentration, and denominator pressure before any new rule is considered.",
        "",
        "## Window Path Summary",
        "",
        _md_table(window_summary, max_rows=10),
        "",
        "## Product-Direction Closed Lot Delta",
        "",
        _md_table(closed_delta.head(30), max_rows=30),
        "",
        "## C9 Stop/Retry Events In Window",
        "",
        _md_table(stop_retry_summary, max_rows=30),
        "",
        "## Position Concentration Proxy",
        "",
        _md_table(pressure_summary, max_rows=10),
        "",
        "## Worst Pressure Days",
        "",
        _md_table(pressure_days, max_rows=20),
        "",
        "## Charts",
        "",
        f"- peak-trough path chart: `{PATH_CHART_PATH}`",
        f"- product-direction PnL delta chart: `{PNL_DELTA_CHART_PATH}`",
        f"- cluster pressure chart: `{CLUSTER_CHART_PATH}`",
        *[f"- stop/retry atlas: `{path}`" for path in atlas_paths],
        "",
        "## Judgment",
        "",
        "- This stage is diagnostic only. It is not a C10 proposal.",
        "- If the weak window is explained mainly by concentration/denominator pressure rather than by the stop/retry events themselves, the next rule shape must be a low-degree holding-period survival discipline, not another entry-day R multiple or retry-count scan.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _prepare_curve()
    daily = _daily_delta(curve)
    window_summary = _window_summary(curve)

    c4_closed = _prepare_closed(C4_CLOSED_PATH, C4_ARM)
    c9_closed = _prepare_closed(C9_CLOSED_PATH, C9_ARM)
    closed_delta = _closed_delta(c4_closed, c9_closed)

    stop_retry_window_events, stop_retry_summary = _prepare_stop_retry_events(c9_closed)

    c4_trades = _prepare_trades(C4_TRADES_PATH)
    c9_trades = _prepare_trades(C9_TRADES_PATH)
    pressure_daily = _position_pressure_daily(c4_trades, c9_trades, daily, c4_closed, c9_closed)
    pressure_summary = _position_pressure_summary(pressure_daily)
    pressure_days = _pressure_days(pressure_daily)

    atlas_paths, atlas_manifest = _plot_event_atlas(stop_retry_window_events)

    daily_window = daily[daily["in_peak_trough_window"].eq(1)].copy()
    daily_window.to_csv(DAILY_DELTA_PATH, index=False, encoding="utf-8-sig")
    window_summary.to_csv(WINDOW_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    closed_delta.to_csv(CLOSED_DELTA_PATH, index=False, encoding="utf-8-sig")
    stop_retry_window_events.to_csv(STOP_RETRY_WINDOW_EVENTS_PATH, index=False, encoding="utf-8-sig")
    stop_retry_summary.to_csv(STOP_RETRY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    pressure_daily.to_csv(POSITION_PRESSURE_DAILY_PATH, index=False, encoding="utf-8-sig")
    pressure_summary.to_csv(POSITION_PRESSURE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    pressure_days.to_csv(PRESSURE_DAYS_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")

    _plot_path(daily)
    _plot_pnl_delta(closed_delta)
    _plot_cluster_pressure(pressure_daily)
    _write_report(window_summary, closed_delta, stop_retry_summary, pressure_summary, pressure_days, atlas_paths)

    delta = window_summary[window_summary["arm"].eq("delta_C9_minus_C4")]
    delta_row = delta.iloc[0].to_dict() if not delta.empty else {}
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "window_start": WINDOW_START.date().isoformat(),
        "window_end": WINDOW_END.date().isoformat(),
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "formal_ab_triggered": False,
        "decision": "stage848_c9_peak_trough_forensics_no_rule_yet",
        "delta_C9_minus_C4": {key: _json_safe(value) for key, value in delta_row.items()},
        "stop_retry_events_in_window": int(len(stop_retry_window_events)),
        "stop_retry_summary_rows": int(len(stop_retry_summary)),
        "largest_negative_product_direction_exit_pnl_delta": (
            closed_delta.sort_values("exit_in_window_realized_pnl_delta_C9_minus_C4").head(1).to_dict("records")
            if not closed_delta.empty
            else []
        ),
        "position_pressure_proxy": {
            "summary_rows": int(len(pressure_summary)),
            "worst_days_rows": int(len(pressure_days)),
            "note": "Position pressure uses end-of-day trade-reconstructed positions and last trade price times contract size as an exposure proxy, not exact exchange margin.",
        },
        "outputs": {
            "daily_delta": str(DAILY_DELTA_PATH),
            "window_summary": str(WINDOW_SUMMARY_PATH),
            "closed_delta": str(CLOSED_DELTA_PATH),
            "stop_retry_window_events": str(STOP_RETRY_WINDOW_EVENTS_PATH),
            "stop_retry_summary": str(STOP_RETRY_SUMMARY_PATH),
            "position_pressure_daily": str(POSITION_PRESSURE_DAILY_PATH),
            "position_pressure_summary": str(POSITION_PRESSURE_SUMMARY_PATH),
            "pressure_days": str(PRESSURE_DAYS_PATH),
            "report": str(REPORT_PATH),
            "path_chart": str(PATH_CHART_PATH),
            "pnl_delta_chart": str(PNL_DELTA_CHART_PATH),
            "cluster_chart": str(CLUSTER_CHART_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "atlas_paths": [str(path) for path in atlas_paths],
        },
        "overfit_reflection": (
            "No. Stage848 is read-only attribution on a predeclared failed peak-trough window and does not select "
            "new thresholds, years, products, or retry parameters."
        ),
        "continue_value_reflection": (
            "Yes. C9 improves full-path return and Sharpe but worsens C4 drawdown; attribution is needed before "
            "deciding whether a low-degree holding-period survival rule exists."
        ),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
