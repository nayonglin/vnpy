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
STAGE = "Stage844"
MODEL_TAG = "stage844_stage843_c8_reuse_pressure_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage844_stage843_c8_reuse_pressure_forensics"

START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-05-29")

STAGE830_PREFIX = "qmt_roll_stage830_stage827_c2_broker10_margin_cap"
STAGE830_TAG = "stage830_stage827_c2_broker10_margin_cap_v1"
STAGE843_PREFIX = "qmt_roll_stage843_stage830_c4_s3_structural_break_engine"
STAGE843_TAG = "stage843_stage830_c4_s3_structural_break_engine_v1"

C4_ARM = "stage830_stage819_c2_broker10_100_cap"
C8_ARM = "stage843_stage819_c4_s3_two_stop_side_closes"
STRUCTURAL_EXIT_REASON = "stage843_intraday_s3_two_stop_side_closes"

C4_CURVE_PATH = OUTPUT_DIR / f"{STAGE830_PREFIX}_curve_{STAGE830_TAG}.csv"
C4_CLOSED_PATH = OUTPUT_DIR / f"{STAGE830_PREFIX}_closed_lots_{STAGE830_TAG}.csv"
C8_CURVE_PATH = OUTPUT_DIR / f"{STAGE843_PREFIX}_curve_{STAGE843_TAG}.csv"
C8_CLOSED_PATH = OUTPUT_DIR / f"{STAGE843_PREFIX}_closed_lots_{STAGE843_TAG}.csv"
C8_STRUCTURAL_EVENTS_PATH = OUTPUT_DIR / f"{STAGE843_PREFIX}_structural_stop_events_{STAGE843_TAG}.csv"

DAILY_DELTA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_delta_{MODEL_TAG}.csv"
DIRECT_DELTA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_direct_structural_lot_delta_{MODEL_TAG}.csv"
OPEN_DELTA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_open_delta_{MODEL_TAG}.csv"
REUSE_ATTRIBUTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_reuse_attribution_{MODEL_TAG}.csv"
REUSE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_reuse_summary_{MODEL_TAG}.csv"
EVENT_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_windows_{MODEL_TAG}.csv"
EVENT_WINDOW_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_window_summary_{MODEL_TAG}.csv"
PRESSURE_DAYS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pressure_days_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
PATH_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_chart_{MODEL_TAG}.png"
REUSE_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_reuse_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_atlas_page{{page:03d}}_{MODEL_TAG}.png"

HORIZONS = [1, 3, 5, 10, 20]
EVENT_WINDOW_HORIZONS = [0, 1, 3, 5, 10, 20]
MAX_HORIZON = max(HORIZONS)
MAX_ATLAS_EVENTS = 12
PER_PAGE = 4


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
    return pd.Timestamp(ts).tz_localize(None).normalize() if getattr(ts, "tzinfo", None) is None else pd.Timestamp(ts).tz_convert("Asia/Shanghai").tz_localize(None).normalize()


def _numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _load_curve(path: Path, arm: str, prefix: str) -> pd.DataFrame:
    curve = _load_csv(path)
    curve = curve[curve["arm"].astype(str).eq(arm)].copy()
    curve["date"] = curve["date"].map(_normal_date)
    curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    curve = _numeric(
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
    keep = [
        "date",
        "account_equity",
        "nav",
        "drawdown_pct",
        "broker10_margin_to_equity_pct",
        "net_pnl",
        "trade_count",
        "total_slippage",
        "rebased_equity",
        "broker10_margin_to_rebased_equity_pct",
        "arm",
        "variant",
        "profile",
        "start_month",
    ]
    keep = [column for column in keep if column in curve.columns]
    curve = curve[keep].copy()
    return curve.rename(columns={column: f"{column}_{prefix}" for column in keep if column != "date"})


def _daily_delta() -> pd.DataFrame:
    c4 = _load_curve(C4_CURVE_PATH, C4_ARM, "C4")
    c8 = _load_curve(C8_CURVE_PATH, C8_ARM, "C8")
    daily = c4.merge(c8, on="date", how="inner").sort_values("date").reset_index(drop=True)
    daily["td_index"] = np.arange(len(daily), dtype=int)
    for metric in [
        "account_equity",
        "nav",
        "drawdown_pct",
        "broker10_margin_to_equity_pct",
        "net_pnl",
        "trade_count",
        "total_slippage",
        "rebased_equity",
        "broker10_margin_to_rebased_equity_pct",
    ]:
        c4_col = f"{metric}_C4"
        c8_col = f"{metric}_C8"
        if c4_col in daily.columns and c8_col in daily.columns:
            daily[f"{metric}_delta_C8_minus_C4"] = daily[c8_col] - daily[c4_col]
    return daily


def _prepare_closed(path: Path, arm: str) -> pd.DataFrame:
    data = _load_csv(path)
    data = data[data["arm"].astype(str).eq(arm)].copy()
    for column in ("entry_date", "exit_date"):
        if column in data.columns:
            data[column] = data[column].map(_normal_date)
    data = _numeric(
        data,
        [
            "entry_price",
            "exit_price",
            "volume",
            "size",
            "realized_pnl",
            "risk_amount",
            "r_multiple",
            "selected_volume",
            "target_risk_amount",
            "stop_distance",
            "entry_risk_distance_pct",
        ],
    )
    data["entry_price_key"] = pd.to_numeric(data["entry_price"], errors="coerce").round(6)
    data["open_key"] = (
        data["entry_date"].dt.strftime("%Y-%m-%d").fillna("")
        + "|"
        + data["vt_symbol"].astype(str)
        + "|"
        + data["direction"].astype(str)
        + "|"
        + data["signal"].astype(str)
        + "|"
        + data["entry_context"].astype(str)
        + "|"
        + data["layer_kind"].astype(str)
        + "|"
        + data["entry_price_key"].astype(str)
    )
    return data


def _open_aggregate(lots: pd.DataFrame, prefix: str) -> pd.DataFrame:
    agg_spec: dict[str, Any] = {
        "lot_id": lambda x: ",".join(str(int(v)) for v in pd.to_numeric(x, errors="coerce").dropna()),
        "open_trade_id": lambda x: ",".join(str(v) for v in x.dropna().astype(str)),
        "close_trade_id": lambda x: ",".join(str(v) for v in x.dropna().astype(str)),
        "entry_date": "min",
        "exit_date": "max",
        "vt_symbol": "first",
        "product": "first",
        "direction": "first",
        "signal": lambda x: "|".join(sorted(set(str(v) for v in x.dropna()))),
        "entry_context": lambda x: "|".join(sorted(set(str(v) for v in x.dropna()))),
        "layer_kind": lambda x: "|".join(sorted(set(str(v) for v in x.dropna()))),
        "exit_reason": lambda x: "|".join(sorted(set(str(v) for v in x.dropna()))),
        "entry_price": "mean",
        "exit_price": "mean",
        "stop_distance": "mean",
        "entry_risk_distance_pct": "mean",
        "volume": "sum",
        "selected_volume": "sum",
        "risk_amount": "sum",
        "target_risk_amount": "sum",
        "realized_pnl": "sum",
        "r_multiple": "sum",
    }
    available = {key: value for key, value in agg_spec.items() if key in lots.columns}
    result = lots.groupby("open_key", dropna=False).agg(available).reset_index()
    return result.add_prefix(f"{prefix}_").rename(columns={f"{prefix}_open_key": "open_key"})


def _pair_open_delta(c4_lots: pd.DataFrame, c8_lots: pd.DataFrame) -> pd.DataFrame:
    c4 = _open_aggregate(c4_lots, "C4")
    c8 = _open_aggregate(c8_lots, "C8")
    merged = c4.merge(c8, on="open_key", how="outer")
    for column in ("entry_date", "exit_date", "vt_symbol", "product", "direction", "signal", "entry_context", "layer_kind"):
        merged[column] = merged.get(f"C8_{column}").combine_first(merged.get(f"C4_{column}"))
    for column in ("volume", "selected_volume", "risk_amount", "target_risk_amount", "realized_pnl", "r_multiple"):
        merged[f"{column}_delta_C8_minus_C4"] = (
            pd.to_numeric(merged.get(f"C8_{column}"), errors="coerce").fillna(0.0)
            - pd.to_numeric(merged.get(f"C4_{column}"), errors="coerce").fillna(0.0)
        )
    merged["entry_date"] = pd.to_datetime(merged["entry_date"], errors="coerce").dt.normalize()
    merged["exit_date"] = pd.to_datetime(merged["exit_date"], errors="coerce").dt.normalize()
    c4_exists = merged["C4_vt_symbol"].notna()
    c8_exists = merged["C8_vt_symbol"].notna()
    volume_delta = pd.to_numeric(merged["volume_delta_C8_minus_C4"], errors="coerce").fillna(0.0)
    merged["exposure_type"] = np.select(
        [
            ~c4_exists & c8_exists,
            c4_exists & ~c8_exists,
            c4_exists & c8_exists & volume_delta.gt(0),
            c4_exists & c8_exists & volume_delta.lt(0),
            c4_exists & c8_exists & volume_delta.eq(0),
        ],
        ["C8_only", "C4_only", "C8_larger", "C8_smaller", "both_equal"],
        default="unknown",
    )
    merged["incremental_c8_exposure"] = merged["exposure_type"].isin(["C8_only", "C8_larger"]).astype(int)
    merged["reduced_c8_exposure"] = merged["exposure_type"].isin(["C4_only", "C8_smaller"]).astype(int)
    merged["same_open_pnl_changed"] = (
        merged["exposure_type"].eq("both_equal")
        & pd.to_numeric(merged["realized_pnl_delta_C8_minus_C4"], errors="coerce").fillna(0.0).ne(0.0)
    ).astype(int)
    merged["c8_structural_direct_exit"] = (
        merged.get("C8_exit_reason", pd.Series(index=merged.index, dtype=object))
        .fillna("")
        .astype(str)
        .str.contains(STRUCTURAL_EXIT_REASON, regex=False)
        .astype(int)
    )
    return merged.sort_values(["entry_date", "open_key"]).reset_index(drop=True)


def _load_structural_events() -> pd.DataFrame:
    events = _load_csv(C8_STRUCTURAL_EVENTS_PATH).copy()
    events["hit_dt"] = pd.to_datetime(events.get("hit_time"), errors="coerce")
    missing = events["hit_dt"].isna()
    if missing.any():
        events.loc[missing, "hit_dt"] = pd.to_datetime(events.loc[missing, "datetime"], errors="coerce")
    events["hit_date"] = events["hit_dt"].map(_normal_date)
    events["entry_date"] = events["datetime"].map(_normal_date)
    events = _numeric(
        events,
        [
            "entry_price",
            "stop_price",
            "exit_price",
            "structural_stop_price_05r",
            "risk_price",
            "structural_stop_r",
            "required_stop_side_closes",
            "volume",
            "trigger_bar_index",
        ],
    )
    events["event_id"] = [f"stage843_s3_{idx:03d}" for idx in range(1, len(events) + 1)]
    return events.sort_values(["hit_date", "hit_dt", "vt_symbol"]).reset_index(drop=True)


def _calendar(daily: pd.DataFrame) -> pd.DataFrame:
    dates = daily["date"].dropna().drop_duplicates().sort_values().reset_index(drop=True)
    return pd.DataFrame({"date": dates, "td_index": np.arange(len(dates), dtype=int)})


def _add_td_index(frame: pd.DataFrame, calendar: pd.DataFrame, date_col: str, out_col: str) -> pd.DataFrame:
    mapping = calendar.set_index("date")["td_index"]
    frame[out_col] = pd.to_datetime(frame[date_col], errors="coerce").dt.normalize().map(mapping)
    return frame


def _nearest_prior_event(
    entry_idx: int,
    events: pd.DataFrame,
    event_indices: np.ndarray,
) -> tuple[pd.Series | None, int]:
    pos = np.searchsorted(event_indices, entry_idx, side="left") - 1
    if pos < 0:
        return None, -1
    event = events.iloc[pos]
    return event, entry_idx - int(event["hit_td_index"])


def _reuse_attribution(delta: pd.DataFrame, events: pd.DataFrame, calendar: pd.DataFrame) -> pd.DataFrame:
    delta = _add_td_index(delta.copy(), calendar, "entry_date", "entry_td_index")
    events = _add_td_index(events.copy(), calendar, "hit_date", "hit_td_index")
    events = events.dropna(subset=["hit_td_index"]).sort_values(["hit_td_index", "hit_dt"]).reset_index(drop=True)
    delta = delta.dropna(subset=["entry_td_index"]).sort_values(["entry_td_index", "open_key"]).reset_index(drop=True)
    if events.empty or delta.empty:
        return pd.DataFrame()
    event_indices = events["hit_td_index"].astype(int).to_numpy()
    rows: list[pd.Series] = []
    for _, row in delta.iterrows():
        if row["c8_structural_direct_exit"] == 1:
            continue
        entry_idx = int(row["entry_td_index"])
        event, trading_days_after = _nearest_prior_event(entry_idx, events, event_indices)
        if event is None or trading_days_after <= 0 or trading_days_after > MAX_HORIZON:
            continue
        item = row.copy()
        item["nearest_event_id"] = event["event_id"]
        item["nearest_event_hit_date"] = event["hit_date"]
        item["nearest_event_hit_time"] = event["hit_dt"]
        item["nearest_event_vt_symbol"] = event.get("vt_symbol", "")
        item["nearest_event_product"] = event.get("product_vt_symbol", "")
        item["nearest_event_direction"] = event.get("direction", "")
        item["trading_days_after_event"] = trading_days_after
        item["same_product_as_nearest_event"] = int(str(row.get("product", "")) == str(event.get("product_vt_symbol", "")))
        item["same_direction_as_nearest_event"] = int(str(row.get("direction", "")) == str(event.get("direction", "")))
        item["same_product_direction_as_nearest_event"] = int(
            item["same_product_as_nearest_event"] and item["same_direction_as_nearest_event"]
        )
        rows.append(item)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _reuse_summary(reuse: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if reuse.empty:
        return pd.DataFrame()
    for horizon in HORIZONS:
        group = reuse[pd.to_numeric(reuse["trading_days_after_event"], errors="coerce").le(horizon)].copy()
        incremental = group[group["incremental_c8_exposure"].eq(1)]
        reduced = group[group["reduced_c8_exposure"].eq(1)]
        same_changed = group[group["same_open_pnl_changed"].eq(1)]
        rows.append(
            {
                "horizon_trading_days": horizon,
                "rows": int(len(group)),
                "incremental_rows": int(len(incremental)),
                "reduced_rows": int(len(reduced)),
                "same_open_changed_rows": int(len(same_changed)),
                "volume_delta_sum": float(pd.to_numeric(group["volume_delta_C8_minus_C4"], errors="coerce").sum()),
                "risk_amount_delta_sum": float(pd.to_numeric(group["risk_amount_delta_C8_minus_C4"], errors="coerce").sum()),
                "realized_pnl_delta_sum": float(pd.to_numeric(group["realized_pnl_delta_C8_minus_C4"], errors="coerce").sum()),
                "incremental_volume_delta_sum": float(pd.to_numeric(incremental["volume_delta_C8_minus_C4"], errors="coerce").sum()),
                "incremental_risk_delta_sum": float(pd.to_numeric(incremental["risk_amount_delta_C8_minus_C4"], errors="coerce").sum()),
                "incremental_pnl_delta_sum": float(pd.to_numeric(incremental["realized_pnl_delta_C8_minus_C4"], errors="coerce").sum()),
                "reduced_volume_delta_sum": float(pd.to_numeric(reduced["volume_delta_C8_minus_C4"], errors="coerce").sum()),
                "reduced_risk_delta_sum": float(pd.to_numeric(reduced["risk_amount_delta_C8_minus_C4"], errors="coerce").sum()),
                "reduced_pnl_delta_sum": float(pd.to_numeric(reduced["realized_pnl_delta_C8_minus_C4"], errors="coerce").sum()),
                "same_open_pnl_delta_sum": float(pd.to_numeric(same_changed["realized_pnl_delta_C8_minus_C4"], errors="coerce").sum()),
                "incremental_positive_rows": int(pd.to_numeric(incremental["realized_pnl_delta_C8_minus_C4"], errors="coerce").gt(0).sum()),
                "incremental_negative_rows": int(pd.to_numeric(incremental["realized_pnl_delta_C8_minus_C4"], errors="coerce").lt(0).sum()),
                "incremental_same_product_pnl": float(
                    pd.to_numeric(
                        incremental[incremental["same_product_as_nearest_event"].eq(1)]["realized_pnl_delta_C8_minus_C4"],
                        errors="coerce",
                    ).sum()
                ),
                "incremental_cross_product_pnl": float(
                    pd.to_numeric(
                        incremental[incremental["same_product_as_nearest_event"].eq(0)]["realized_pnl_delta_C8_minus_C4"],
                        errors="coerce",
                    ).sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def _direct_structural_delta(delta: pd.DataFrame) -> pd.DataFrame:
    direct = delta[delta["c8_structural_direct_exit"].eq(1)].copy()
    if direct.empty:
        return pd.DataFrame()
    direct["exit_date_delta_days_C8_minus_C4"] = (
        pd.to_datetime(direct["C8_exit_date"], errors="coerce") - pd.to_datetime(direct["C4_exit_date"], errors="coerce")
    ).dt.days
    direct["direct_effect_type"] = np.where(
        pd.to_numeric(direct["realized_pnl_delta_C8_minus_C4"], errors="coerce").ge(0),
        "direct_loss_reduced_or_profit_added",
        "direct_winner_cut_or_loss_added",
    )
    return direct.sort_values("realized_pnl_delta_C8_minus_C4").reset_index(drop=True)


def _event_windows(daily: pd.DataFrame, events: pd.DataFrame, calendar: pd.DataFrame) -> pd.DataFrame:
    events = _add_td_index(events.copy(), calendar, "hit_date", "hit_td_index")
    daily_by_idx = daily.set_index("td_index")
    rows: list[dict[str, Any]] = []
    for event in events.dropna(subset=["hit_td_index"]).to_dict("records"):
        event_idx = int(event["hit_td_index"])
        for horizon in EVENT_WINDOW_HORIZONS:
            end_idx = event_idx + horizon
            window = daily_by_idx.loc[
                (daily_by_idx.index >= event_idx) & (daily_by_idx.index <= end_idx)
            ].copy()
            if window.empty:
                continue
            end_row = window.iloc[-1]
            rows.append(
                {
                    "event_id": event["event_id"],
                    "hit_date": event["hit_date"],
                    "hit_time": event["hit_dt"],
                    "vt_symbol": event.get("vt_symbol", ""),
                    "product_vt_symbol": event.get("product_vt_symbol", ""),
                    "direction": event.get("direction", ""),
                    "entry_price": event.get("entry_price", np.nan),
                    "exit_price": event.get("exit_price", np.nan),
                    "structural_stop_price_05r": event.get("structural_stop_price_05r", np.nan),
                    "volume": event.get("volume", np.nan),
                    "horizon_trading_days": horizon,
                    "window_days": int(len(window)),
                    "cum_net_pnl_delta_C8_minus_C4": float(pd.to_numeric(window["net_pnl_delta_C8_minus_C4"], errors="coerce").sum()),
                    "end_equity_delta_C8_minus_C4": float(end_row["account_equity_delta_C8_minus_C4"]),
                    "max_broker10_C8": float(pd.to_numeric(window["broker10_margin_to_equity_pct_C8"], errors="coerce").max()),
                    "max_broker10_C4": float(pd.to_numeric(window["broker10_margin_to_equity_pct_C4"], errors="coerce").max()),
                    "max_broker10_delta_C8_minus_C4": float(pd.to_numeric(window["broker10_margin_to_equity_pct_delta_C8_minus_C4"], errors="coerce").max()),
                    "min_drawdown_C8": float(pd.to_numeric(window["drawdown_pct_C8"], errors="coerce").min()),
                    "min_drawdown_C4": float(pd.to_numeric(window["drawdown_pct_C4"], errors="coerce").min()),
                    "min_drawdown_delta_C8_minus_C4": float(pd.to_numeric(window["drawdown_pct_delta_C8_minus_C4"], errors="coerce").min()),
                    "trade_count_delta_sum": float(pd.to_numeric(window.get("trade_count_delta_C8_minus_C4", 0.0), errors="coerce").sum()),
                    "slippage_delta_sum": float(pd.to_numeric(window.get("total_slippage_delta_C8_minus_C4", 0.0), errors="coerce").sum()),
                }
            )
    return pd.DataFrame(rows)


def _event_window_summary(event_windows: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if event_windows.empty:
        return pd.DataFrame()
    for horizon, group in event_windows.groupby("horizon_trading_days", sort=True):
        rows.append(
            {
                "horizon_trading_days": int(horizon),
                "events": int(len(group)),
                "sum_cum_net_pnl_delta_overlap_allowed": float(pd.to_numeric(group["cum_net_pnl_delta_C8_minus_C4"], errors="coerce").sum()),
                "median_cum_net_pnl_delta": float(pd.to_numeric(group["cum_net_pnl_delta_C8_minus_C4"], errors="coerce").median()),
                "negative_net_pnl_events": int(pd.to_numeric(group["cum_net_pnl_delta_C8_minus_C4"], errors="coerce").lt(0).sum()),
                "max_broker10_delta_event": float(pd.to_numeric(group["max_broker10_delta_C8_minus_C4"], errors="coerce").max()),
                "median_max_broker10_delta": float(pd.to_numeric(group["max_broker10_delta_C8_minus_C4"], errors="coerce").median()),
                "min_drawdown_delta_event": float(pd.to_numeric(group["min_drawdown_delta_C8_minus_C4"], errors="coerce").min()),
                "median_min_drawdown_delta": float(pd.to_numeric(group["min_drawdown_delta_C8_minus_C4"], errors="coerce").median()),
                "events_with_c8_broker10_gt_100": int(pd.to_numeric(group["max_broker10_C8"], errors="coerce").gt(100.0).sum()),
            }
        )
    return pd.DataFrame(rows)


def _pressure_days(daily: pd.DataFrame, events: pd.DataFrame, calendar: pd.DataFrame) -> pd.DataFrame:
    events = _add_td_index(events.copy(), calendar, "hit_date", "hit_td_index")
    events = events.dropna(subset=["hit_td_index"]).sort_values(["hit_td_index", "hit_dt"]).reset_index(drop=True)
    if events.empty:
        return pd.DataFrame()
    event_indices = events["hit_td_index"].astype(int).to_numpy()
    specs = [
        ("top_broker10_delta", "broker10_margin_to_equity_pct_delta_C8_minus_C4", False),
        ("top_c8_broker10", "broker10_margin_to_equity_pct_C8", False),
        ("worst_drawdown_delta", "drawdown_pct_delta_C8_minus_C4", True),
        ("worst_daily_net_pnl_delta", "net_pnl_delta_C8_minus_C4", True),
    ]
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, pd.Timestamp]] = set()
    for category, column, ascending in specs:
        if column not in daily.columns:
            continue
        selected = daily.sort_values(column, ascending=ascending).head(15)
        for _, row in selected.iterrows():
            event, trading_days_after = _nearest_prior_event(int(row["td_index"]), events, event_indices)
            key = (category, pd.Timestamp(row["date"]))
            if key in seen:
                continue
            seen.add(key)
            item = {
                "category": category,
                "date": row["date"],
                "td_index": int(row["td_index"]),
                "account_equity_C4": row.get("account_equity_C4", np.nan),
                "account_equity_C8": row.get("account_equity_C8", np.nan),
                "account_equity_delta_C8_minus_C4": row.get("account_equity_delta_C8_minus_C4", np.nan),
                "net_pnl_delta_C8_minus_C4": row.get("net_pnl_delta_C8_minus_C4", np.nan),
                "drawdown_pct_C4": row.get("drawdown_pct_C4", np.nan),
                "drawdown_pct_C8": row.get("drawdown_pct_C8", np.nan),
                "drawdown_pct_delta_C8_minus_C4": row.get("drawdown_pct_delta_C8_minus_C4", np.nan),
                "broker10_C4": row.get("broker10_margin_to_equity_pct_C4", np.nan),
                "broker10_C8": row.get("broker10_margin_to_equity_pct_C8", np.nan),
                "broker10_delta_C8_minus_C4": row.get("broker10_margin_to_equity_pct_delta_C8_minus_C4", np.nan),
            }
            if event is not None:
                item.update(
                    {
                        "nearest_event_id": event["event_id"],
                        "nearest_event_hit_date": event["hit_date"],
                        "nearest_event_hit_time": event["hit_dt"],
                        "nearest_event_product": event.get("product_vt_symbol", ""),
                        "nearest_event_vt_symbol": event.get("vt_symbol", ""),
                        "nearest_event_direction": event.get("direction", ""),
                        "trading_days_after_nearest_event": trading_days_after,
                    }
                )
            rows.append(item)
    result = pd.DataFrame(rows)
    if not result.empty:
        result.sort_values(["category", "date"], inplace=True)
    return result


def _plot_path(daily: pd.DataFrame, events: pd.DataFrame) -> None:
    if daily.empty:
        return
    fig, axes = plt.subplots(4, 1, figsize=(18, 13), sharex=True, constrained_layout=True)
    date = daily["date"]
    axes[0].plot(date, daily["account_equity_C4"] / 1_000_000, color="#16a34a", linewidth=1.1, label="C4 equity")
    axes[0].plot(date, daily["account_equity_C8"] / 1_000_000, color="#7c3aed", linewidth=1.1, label="C8 equity")
    axes[0].set_title("C4 vs C8 equity path")
    axes[0].set_ylabel("million")
    axes[1].plot(date, daily["account_equity_delta_C8_minus_C4"] / 1_000_000, color="#111827", linewidth=1.0)
    axes[1].axhline(0, color="#6b7280", linewidth=0.8)
    axes[1].set_title("C8-C4 equity delta")
    axes[1].set_ylabel("million")
    axes[2].plot(date, daily["broker10_margin_to_equity_pct_C4"], color="#16a34a", linewidth=1.0, label="C4 broker10")
    axes[2].plot(date, daily["broker10_margin_to_equity_pct_C8"], color="#7c3aed", linewidth=1.0, label="C8 broker10")
    axes[2].plot(date, daily["broker10_margin_to_equity_pct_delta_C8_minus_C4"], color="#f59e0b", linewidth=0.75, alpha=0.85, label="C8-C4")
    axes[2].axhline(100.0, color="#dc2626", linestyle="--", linewidth=0.8)
    axes[2].set_title("Broker10 margin/equity pressure")
    axes[2].set_ylabel("%")
    axes[3].plot(date, daily["drawdown_pct_C4"], color="#16a34a", linewidth=1.0, label="C4 drawdown")
    axes[3].plot(date, daily["drawdown_pct_C8"], color="#7c3aed", linewidth=1.0, label="C8 drawdown")
    axes[3].plot(date, daily["drawdown_pct_delta_C8_minus_C4"], color="#dc2626", linewidth=0.75, alpha=0.85, label="C8-C4")
    axes[3].set_title("Drawdown path")
    axes[3].set_ylabel("%")
    event_dates = pd.to_datetime(events["hit_date"], errors="coerce").dropna().drop_duplicates().sort_values()
    for ax in axes:
        for event_date in event_dates:
            ax.axvline(event_date, color="#9ca3af", linewidth=0.35, alpha=0.25)
        ax.grid(True, alpha=0.22)
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(handles, labels, loc="best")
    fig.suptitle("Stage844 C8 released-capital and pressure path diagnostic", fontsize=13)
    fig.savefig(PATH_CHART_PATH, dpi=150)
    plt.close(fig)


def _plot_reuse_chart(reuse_summary: pd.DataFrame, event_window_summary: pd.DataFrame) -> None:
    if reuse_summary.empty and event_window_summary.empty:
        return
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5), constrained_layout=True)
    if not reuse_summary.empty:
        axes[0].plot(
            reuse_summary["horizon_trading_days"],
            reuse_summary["incremental_pnl_delta_sum"],
            marker="o",
            color="#7c3aed",
            label="incremental exposure pnl",
        )
        axes[0].plot(
            reuse_summary["horizon_trading_days"],
            reuse_summary["same_open_pnl_delta_sum"],
            marker="o",
            color="#2563eb",
            label="same-open pnl delta",
        )
        axes[1].plot(
            reuse_summary["horizon_trading_days"],
            reuse_summary["incremental_risk_delta_sum"],
            marker="o",
            color="#f59e0b",
            label="incremental risk",
        )
    if not event_window_summary.empty:
        axes[2].plot(
            event_window_summary["horizon_trading_days"],
            event_window_summary["median_max_broker10_delta"],
            marker="o",
            color="#dc2626",
            label="median max broker10 delta",
        )
        axes[2].plot(
            event_window_summary["horizon_trading_days"],
            event_window_summary["median_min_drawdown_delta"],
            marker="o",
            color="#111827",
            label="median min dd delta",
        )
    titles = ["Reuse PnL after nearest S3", "Reuse risk after nearest S3", "Event-window pressure median"]
    for ax, title in zip(axes, titles, strict=False):
        ax.axhline(0, color="#6b7280", linewidth=0.8)
        ax.set_title(title)
        ax.set_xlabel("trading days")
        ax.grid(True, alpha=0.22)
        ax.legend(loc="best")
    fig.suptitle("Stage844 C8 reuse attribution summary", fontsize=13)
    fig.savefig(REUSE_CHART_PATH, dpi=150)
    plt.close(fig)


def _plot_event_atlas(event_windows: pd.DataFrame, events: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    if event_windows.empty or events.empty:
        return [], pd.DataFrame()
    wide = event_windows[event_windows["horizon_trading_days"].eq(20)].copy()
    if wide.empty:
        wide = event_windows[event_windows["horizon_trading_days"].eq(event_windows["horizon_trading_days"].max())].copy()
    worst_broker = wide.sort_values("max_broker10_delta_C8_minus_C4", ascending=False).head(6)
    worst_dd = wide.sort_values("min_drawdown_delta_C8_minus_C4", ascending=True).head(4)
    worst_pnl = wide.sort_values("cum_net_pnl_delta_C8_minus_C4", ascending=True).head(4)
    selected_ids = pd.concat([worst_broker, worst_dd, worst_pnl], ignore_index=True)["event_id"].drop_duplicates().head(MAX_ATLAS_EVENTS)
    selected = wide[wide["event_id"].isin(set(selected_ids))].copy()
    if selected.empty:
        return [], pd.DataFrame()
    selected["rank_order"] = selected["event_id"].map({event_id: idx for idx, event_id in enumerate(selected_ids, start=1)})
    selected = selected.sort_values("rank_order")
    event_lookup = events.set_index("event_id")
    vt_symbols = set(selected["vt_symbol"].astype(str).dropna().unique())
    minute_bars = s825._load_minute_bars(vt_symbols)
    minute_by_symbol = s825._minute_groups(minute_bars)
    pages = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    manifest_rows: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.0, 3.3 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            event = event_lookup.loc[row["event_id"]]
            vt_symbol = str(row["vt_symbol"])
            hit_date = pd.Timestamp(row["hit_date"]).normalize()
            direction = str(row["direction"])
            bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            day = bars[bars["bar_date"].eq(hit_date)].copy().sort_values("bar_datetime").reset_index(drop=True) if not bars.empty else pd.DataFrame()
            if day.empty:
                ax.axis("off")
                ax.text(0.5, 0.5, f"missing minute bars {vt_symbol} {hit_date:%Y-%m-%d}", ha="center", va="center")
            else:
                trigger_index = int(_safe_float(event.get("trigger_bar_index"), 260))
                end = min(len(day), max(240, trigger_index + 35))
                window = day.head(end).copy().reset_index(drop=True)
                s825._plot_candles(ax, window)
                for value, color, label, style in [
                    (_safe_float(row.get("entry_price")), "#2563eb", "entry", "-"),
                    (_safe_float(row.get("structural_stop_price_05r")), "#dc2626", "0.5R", "--"),
                    (_safe_float(row.get("exit_price")), "#111827", "exit", "-"),
                ]:
                    if np.isfinite(value):
                        ax.axhline(value, color=color, linestyle=style, linewidth=0.9, alpha=0.9, label=label)
                if 0 <= trigger_index < len(window):
                    ax.axvline(trigger_index, color="#7c3aed", linestyle="--", linewidth=0.9, alpha=0.8)
                ticks = np.linspace(0, len(window) - 1, num=min(8, len(window)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(window.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                ax.tick_params(axis="y", labelsize=7)
                ax.grid(True, alpha=0.18, linewidth=0.5)
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    ax.legend(handles, labels, loc="best", fontsize=7)
            ax.set_title(
                (
                    f"{row['event_id']} {vt_symbol} {direction} {hit_date:%Y-%m-%d} "
                    f"20d_pnl_delta={row['cum_net_pnl_delta_C8_minus_C4']:,.0f} "
                    f"max_broker_delta={row['max_broker10_delta_C8_minus_C4']:.2f}pp "
                    f"min_dd_delta={row['min_drawdown_delta_C8_minus_C4']:.2f}pp"
                ),
                fontsize=8.5,
                loc="left",
            )
            manifest_rows.append(
                {
                    "page": page,
                    "event_id": row["event_id"],
                    "vt_symbol": vt_symbol,
                    "hit_date": hit_date.strftime("%Y-%m-%d"),
                    "direction": direction,
                    "cum_net_pnl_delta_20d": _safe_float(row.get("cum_net_pnl_delta_C8_minus_C4")),
                    "max_broker10_delta_20d": _safe_float(row.get("max_broker10_delta_C8_minus_C4")),
                    "min_drawdown_delta_20d": _safe_float(row.get("min_drawdown_delta_C8_minus_C4")),
                }
            )
        fig.suptitle("Stage844 S3 event minute-K atlas (blue=entry, red=0.5R, black=exit, purple=trigger)", fontsize=13)
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest_rows)


def _direct_summary(direct_delta: pd.DataFrame) -> pd.DataFrame:
    if direct_delta.empty:
        return pd.DataFrame()
    rows = []
    for effect_type, group in direct_delta.groupby("direct_effect_type", dropna=False):
        rows.append(
            {
                "direct_effect_type": effect_type,
                "rows": int(len(group)),
                "volume_delta_sum": float(pd.to_numeric(group["volume_delta_C8_minus_C4"], errors="coerce").sum()),
                "realized_pnl_delta_sum": float(pd.to_numeric(group["realized_pnl_delta_C8_minus_C4"], errors="coerce").sum()),
                "median_realized_pnl_delta": float(pd.to_numeric(group["realized_pnl_delta_C8_minus_C4"], errors="coerce").median()),
                "min_realized_pnl_delta": float(pd.to_numeric(group["realized_pnl_delta_C8_minus_C4"], errors="coerce").min()),
                "max_realized_pnl_delta": float(pd.to_numeric(group["realized_pnl_delta_C8_minus_C4"], errors="coerce").max()),
            }
        )
    rows.append(
        {
            "direct_effect_type": "all",
            "rows": int(len(direct_delta)),
            "volume_delta_sum": float(pd.to_numeric(direct_delta["volume_delta_C8_minus_C4"], errors="coerce").sum()),
            "realized_pnl_delta_sum": float(pd.to_numeric(direct_delta["realized_pnl_delta_C8_minus_C4"], errors="coerce").sum()),
            "median_realized_pnl_delta": float(pd.to_numeric(direct_delta["realized_pnl_delta_C8_minus_C4"], errors="coerce").median()),
            "min_realized_pnl_delta": float(pd.to_numeric(direct_delta["realized_pnl_delta_C8_minus_C4"], errors="coerce").min()),
            "max_realized_pnl_delta": float(pd.to_numeric(direct_delta["realized_pnl_delta_C8_minus_C4"], errors="coerce").max()),
        }
    )
    return pd.DataFrame(rows)


def _path_summary(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()
    max_broker_row = daily.loc[daily["broker10_margin_to_equity_pct_C8"].idxmax()]
    max_broker_delta_row = daily.loc[daily["broker10_margin_to_equity_pct_delta_C8_minus_C4"].idxmax()]
    worst_dd_delta_row = daily.loc[daily["drawdown_pct_delta_C8_minus_C4"].idxmin()]
    worst_pnl_delta_row = daily.loc[daily["net_pnl_delta_C8_minus_C4"].idxmin()]
    last = daily.iloc[-1]
    rows = [
        {
            "metric": "end_equity_delta_C8_minus_C4",
            "date": last["date"],
            "value": float(last["account_equity_delta_C8_minus_C4"]),
            "C4": float(last["account_equity_C4"]),
            "C8": float(last["account_equity_C8"]),
        },
        {
            "metric": "max_C8_broker10",
            "date": max_broker_row["date"],
            "value": float(max_broker_row["broker10_margin_to_equity_pct_C8"]),
            "C4": float(max_broker_row["broker10_margin_to_equity_pct_C4"]),
            "C8": float(max_broker_row["broker10_margin_to_equity_pct_C8"]),
        },
        {
            "metric": "max_broker10_delta_C8_minus_C4",
            "date": max_broker_delta_row["date"],
            "value": float(max_broker_delta_row["broker10_margin_to_equity_pct_delta_C8_minus_C4"]),
            "C4": float(max_broker_delta_row["broker10_margin_to_equity_pct_C4"]),
            "C8": float(max_broker_delta_row["broker10_margin_to_equity_pct_C8"]),
        },
        {
            "metric": "worst_drawdown_delta_C8_minus_C4",
            "date": worst_dd_delta_row["date"],
            "value": float(worst_dd_delta_row["drawdown_pct_delta_C8_minus_C4"]),
            "C4": float(worst_dd_delta_row["drawdown_pct_C4"]),
            "C8": float(worst_dd_delta_row["drawdown_pct_C8"]),
        },
        {
            "metric": "worst_daily_net_pnl_delta_C8_minus_C4",
            "date": worst_pnl_delta_row["date"],
            "value": float(worst_pnl_delta_row["net_pnl_delta_C8_minus_C4"]),
            "C4": float(worst_pnl_delta_row["net_pnl_C4"]),
            "C8": float(worst_pnl_delta_row["net_pnl_C8"]),
        },
    ]
    return pd.DataFrame(rows)


def _write_report(
    path_summary: pd.DataFrame,
    direct_summary: pd.DataFrame,
    reuse_summary: pd.DataFrame,
    event_window_summary: pd.DataFrame,
    pressure_days: pd.DataFrame,
    atlas_paths: list[Path],
) -> None:
    lines = [
        "# Stage844 C8释放资金与风险压力归因",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        f"- 区间：`{START.date()}` 到 `{END.date()}`",
        "- 阶段性质：只读归因；不改正式版、不改候选配置、不连接 CTP、不调用下单。",
        "- 对照口径：C4 = Stage830 `C2 + broker10 100% cap`；C8 = Stage843 `C4 + S3 0.5R 两根止损侧收盘`。",
        "",
        "## 外部调研判断",
        "",
        "- CME 的 futures order type / risk management 资料强调止损和仓位风险是执行纪律，不等同于趋势判断本身。",
        "- CFTC 止损教育资料强调止损可以限制单笔亏损，但无法保证成交价格，也不能替代组合层面的风险控制。",
        "- vn.py 代码结构把策略信号、风控、成交/持仓事件分层；本阶段沿用这个思想，只做 C8 事件后的组合路径归因，不从单笔K线直接推正式规则。",
        "- 判断：S3 已经不是单笔止损问题，而是释放保证金后是否被组合重新使用、以及在低权益分母下是否放大 broker10 的问题。",
        "",
        "## Path Summary",
        "",
        _md_table(path_summary, max_rows=20),
        "",
        "## Direct Structural Lot Delta",
        "",
        _md_table(direct_summary, max_rows=20),
        "",
        "## Reuse Summary",
        "",
        _md_table(reuse_summary, max_rows=20),
        "",
        "## Event Window Summary",
        "",
        _md_table(event_window_summary, max_rows=20),
        "",
        "## Top Pressure Days",
        "",
        _md_table(pressure_days.head(80), max_rows=80),
        "",
        "## Charts",
        "",
        f"- path chart：`{PATH_CHART_PATH}`",
        f"- reuse chart：`{REUSE_CHART_PATH}`",
        *[f"- event atlas：`{path}`" for path in atlas_paths],
        "",
        "## Judgment",
        "",
        "- 本阶段不把 S3 继续参数化；如果 C8 的风险来自后续资金复用，下一步只允许研究低自由度的复用闸门或入场质量过滤。",
        "- 如果复用本身贡献为正但 broker10 继续恶化，问题不是简单冷却，而是权益分母和保证金集中度的组合风险。",
        "- 如果直接退出贡献为正、复用也贡献为正但回撤恶化，说明入场日止损局部正确，组合层面需要避免释放资金立刻堆到同一压力簇。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    daily = _daily_delta()
    calendar = _calendar(daily)
    c4_lots = _prepare_closed(C4_CLOSED_PATH, C4_ARM)
    c8_lots = _prepare_closed(C8_CLOSED_PATH, C8_ARM)
    open_delta = _pair_open_delta(c4_lots, c8_lots)
    structural_events = _load_structural_events()

    direct_delta = _direct_structural_delta(open_delta)
    direct_summary = _direct_summary(direct_delta)
    reuse = _reuse_attribution(open_delta, structural_events, calendar)
    reuse_summary = _reuse_summary(reuse)
    event_windows = _event_windows(daily, structural_events, calendar)
    event_window_summary = _event_window_summary(event_windows)
    pressure_days = _pressure_days(daily, structural_events, calendar)
    path_summary = _path_summary(daily)

    _plot_path(daily, structural_events)
    _plot_reuse_chart(reuse_summary, event_window_summary)
    atlas_paths, atlas_manifest = _plot_event_atlas(event_windows, structural_events)
    _write_report(path_summary, direct_summary, reuse_summary, event_window_summary, pressure_days, atlas_paths)

    daily.to_csv(DAILY_DELTA_PATH, index=False, encoding="utf-8-sig")
    open_delta.to_csv(OPEN_DELTA_PATH, index=False, encoding="utf-8-sig")
    direct_delta.to_csv(DIRECT_DELTA_PATH, index=False, encoding="utf-8-sig")
    reuse.to_csv(REUSE_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    reuse_summary.to_csv(REUSE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    event_windows.to_csv(EVENT_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    event_window_summary.to_csv(EVENT_WINDOW_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    pressure_days.to_csv(PRESSURE_DAYS_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")

    direct_all = direct_summary[direct_summary["direct_effect_type"].eq("all")]
    reuse_20 = reuse_summary[reuse_summary["horizon_trading_days"].eq(20)]
    event_20 = event_window_summary[event_window_summary["horizon_trading_days"].eq(20)]
    path_lookup = path_summary.set_index("metric")["value"].to_dict() if not path_summary.empty else {}
    direct_pnl = float(direct_all["realized_pnl_delta_sum"].iloc[0]) if not direct_all.empty else np.nan
    reuse_incremental_pnl = float(reuse_20["incremental_pnl_delta_sum"].iloc[0]) if not reuse_20.empty else np.nan
    reuse_incremental_risk = float(reuse_20["incremental_risk_delta_sum"].iloc[0]) if not reuse_20.empty else np.nan
    event20_max_broker_delta = float(event_20["max_broker10_delta_event"].iloc[0]) if not event_20.empty else np.nan
    event20_min_dd_delta = float(event_20["min_drawdown_delta_event"].iloc[0]) if not event_20.empty else np.nan

    decision_label = (
        "stage844_c8_diagnostic_reuse_positive_but_pressure_worse"
        if np.isfinite(reuse_incremental_pnl)
        and reuse_incremental_pnl > 0
        and np.isfinite(event20_max_broker_delta)
        and event20_max_broker_delta > 0
        else "stage844_c8_diagnostic_reuse_or_direct_pressure_mixed"
    )
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "backtest_rerun": False,
        "ctp_connected": False,
        "order_api_called": False,
        "decision": decision_label,
        "direct_structural_pnl_delta_C8_minus_C4": direct_pnl,
        "reuse_20d_incremental_pnl_delta_C8_minus_C4": reuse_incremental_pnl,
        "reuse_20d_incremental_risk_delta_C8_minus_C4": reuse_incremental_risk,
        "end_equity_delta_C8_minus_C4": path_lookup.get("end_equity_delta_C8_minus_C4"),
        "max_C8_broker10": path_lookup.get("max_C8_broker10"),
        "max_broker10_delta_C8_minus_C4": path_lookup.get("max_broker10_delta_C8_minus_C4"),
        "event20_max_broker10_delta_event": event20_max_broker_delta,
        "event20_min_drawdown_delta_event": event20_min_dd_delta,
        "path_summary": path_summary.to_dict("records"),
        "direct_summary": direct_summary.to_dict("records"),
        "reuse_summary": reuse_summary.to_dict("records"),
        "event_window_summary": event_window_summary.to_dict("records"),
        "overfit_reflection": (
            "Stage844 is read-only and uses frozen C4/C8 outputs with fixed 1/3/5/10/20-day attribution windows. "
            "It does not scan S3 parameters, products, years, or directions. Turning worst atlas events into a bespoke "
            "rule would be overfitting."
        ),
        "continue_value": (
            "Continue only if the evidence points to a broad mechanism: released capital reuse or broker10 pressure. "
            "Do not continue by tuning S3 itself; that route has already failed full-path promotion."
        ),
        "outputs": {
            "daily_delta": str(DAILY_DELTA_PATH),
            "open_delta": str(OPEN_DELTA_PATH),
            "direct_structural_delta": str(DIRECT_DELTA_PATH),
            "reuse_attribution": str(REUSE_ATTRIBUTION_PATH),
            "reuse_summary": str(REUSE_SUMMARY_PATH),
            "event_windows": str(EVENT_WINDOWS_PATH),
            "event_window_summary": str(EVENT_WINDOW_SUMMARY_PATH),
            "pressure_days": str(PRESSURE_DAYS_PATH),
            "report": str(REPORT_PATH),
            "path_chart": str(PATH_CHART_PATH),
            "reuse_chart": str(REUSE_CHART_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "atlas_pages": [str(path) for path in atlas_paths],
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("path_summary")
    print(path_summary.to_string(index=False))
    print("direct_summary")
    print(direct_summary.to_string(index=False))
    print("reuse_summary")
    print(reuse_summary.to_string(index=False))
    print("event_window_summary")
    print(event_window_summary.to_string(index=False))


if __name__ == "__main__":
    main()
