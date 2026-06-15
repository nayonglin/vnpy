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
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage889"
MODEL_TAG = "stage889_stage863_c9_loss_shape_coverage_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage889_stage863_c9_loss_shape_coverage_audit"

STAGE861_PREFIX = "qmt_roll_stage861_stage860_full_visual_atlas"
STAGE861_TAG = "stage861_stage860_full_visual_atlas_v1"
STAGE863_PREFIX = "qmt_roll_stage863_stage847_c10_budget_lock_engine"
STAGE863_TAG = "stage863_stage847_c10_budget_lock_engine_v1"

FULL_MINUTE_BARS_PATH = OUTPUT_DIR / f"{STAGE861_PREFIX}_full_minute_bars_{STAGE861_TAG}.csv"
STAGE863_CLOSED_LOTS_PATH = OUTPUT_DIR / f"{STAGE863_PREFIX}_closed_lots_{STAGE863_TAG}.csv"
STAGE863_TRADES_PATH = OUTPUT_DIR / f"{STAGE863_PREFIX}_trades_{STAGE863_TAG}.csv"
STAGE863_STOP_RETRY_EVENTS_PATH = OUTPUT_DIR / f"{STAGE863_PREFIX}_stop_retry_events_{STAGE863_TAG}.csv"

FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
SHAPE_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_shape_coverage_{MODEL_TAG}.csv"
PROXY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_summary_{MODEL_TAG}.csv"
PROXY_YEARLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_yearly_{MODEL_TAG}.csv"
RETRY_ROLE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_retry_role_summary_{MODEL_TAG}.csv"
SUMMARY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

C9_ARM = s847.C9_ARM
EARLY_BARS = 60
OPENING_RANGE_BARS = 15
PER_PAGE = 4
MAX_ATLAS_ROWS = 24


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _load_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _direction_sign(direction: Any) -> float:
    return 1.0 if str(direction) == "long" else -1.0


def _prepare_closed_lots() -> pd.DataFrame:
    data = _load_required_csv(STAGE863_CLOSED_LOTS_PATH)
    data = data[data["arm"].astype(str).eq(C9_ARM)].copy()
    if data.empty:
        raise RuntimeError(f"missing C9 closed lots in {STAGE863_CLOSED_LOTS_PATH}")
    for column in ["entry_date", "exit_date"]:
        data[column] = pd.to_datetime(data[column], errors="coerce").dt.normalize()
    numeric_columns = [
        "lot_id",
        "entry_price",
        "exit_price",
        "volume",
        "size",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "winner",
        "big_winner",
        "stop_distance",
        "entry_risk_distance_pct",
    ]
    for column in numeric_columns:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data["entry_year"] = data["entry_date"].dt.year
    data["winner"] = pd.to_numeric(data.get("winner"), errors="coerce").fillna(
        data["realized_pnl"].fillna(0).gt(0).astype(int)
    )
    data["big_winner"] = pd.to_numeric(data.get("big_winner"), errors="coerce").fillna(0).astype(int)
    return data.sort_values(["entry_date", "vt_symbol", "open_trade_id"]).reset_index(drop=True)


def _prepare_minute_bars(vt_symbols: set[str]) -> pd.DataFrame:
    data = _load_required_csv(FULL_MINUTE_BARS_PATH)
    data = data[data["vt_symbol"].astype(str).isin(vt_symbols)].copy()
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    data["bar_date"] = pd.to_datetime(data["bar_date"], errors="coerce").dt.normalize()
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.dropna(subset=["vt_symbol", "bar_datetime", "bar_date", "open", "high", "low", "close"]).reset_index(
        drop=True
    )


def _prepare_event_maps() -> dict[str, dict[str, Any]]:
    trades = _load_required_csv(STAGE863_TRADES_PATH)
    trades = trades[trades["profile"].astype(str).eq(C9_ARM)].copy()
    events = _load_required_csv(STAGE863_STOP_RETRY_EVENTS_PATH)
    events = events[events["profile"].astype(str).eq(C9_ARM)].copy()
    trade_by_id = trades.set_index(trades["trade_id"].astype(str), drop=False)

    event_by_trade: dict[str, dict[str, Any]] = {}
    for _, row in events.iterrows():
        trade_id = str(row.get("trade_id", ""))
        if not trade_id:
            continue
        original_order_id = str(trade_by_id.loc[trade_id, "order_id"]) if trade_id in trade_by_id.index else ""
        reentry_order_id = f"{original_order_id}.stage847_c9.2" if original_order_id else ""
        reentry_trade_id = ""
        if reentry_order_id:
            reentry = trades[
                trades["order_id"].astype(str).eq(reentry_order_id) & trades["offset"].astype(str).eq("Open")
            ]
            if not reentry.empty:
                reentry_trade_id = str(reentry.iloc[0]["trade_id"])
        base = {
            "retry_event_trade_id": trade_id,
            "retry_reentry_trade_id": reentry_trade_id,
            "retry_final_state": str(row.get("final_state", "")),
            "retry_first_stop_time": row.get("first_stop_time", ""),
            "retry_reentry_time": row.get("reentry_time", ""),
            "retry_failed_time": row.get("retry_failed_time", ""),
            "retry_first_stop_bar_index": _safe_float(row.get("first_stop_bar_index")),
            "retry_reentry_bar_index": _safe_float(row.get("reentry_bar_index")),
            "retry_failed_bar_index": _safe_float(row.get("retry_failed_bar_index")),
            "retry_risk_price": _safe_float(row.get("risk_price")),
            "retry_stop_price": _safe_float(row.get("stop_price")),
            "retry_progress_price": _safe_float(row.get("progress_price")),
        }
        original = dict(base)
        original["retry_role"] = "initial_stop_leg"
        event_by_trade[trade_id] = original
        if reentry_trade_id:
            reentry_record = dict(base)
            reentry_record["retry_role"] = "reentry_leg"
            event_by_trade[reentry_trade_id] = reentry_record
    return event_by_trade


def _risk_price(row: pd.Series, event_info: dict[str, Any]) -> float:
    event_risk = _safe_float(event_info.get("retry_risk_price"))
    if event_risk > 0:
        return event_risk
    stop_distance = _safe_float(row.get("stop_distance"))
    if stop_distance > 0:
        return stop_distance
    risk_amount = _safe_float(row.get("risk_amount"))
    size = _safe_float(row.get("size"))
    volume = _safe_float(row.get("volume"))
    if risk_amount > 0 and size > 0 and volume > 0:
        return risk_amount / (size * volume)
    entry_price = _safe_float(row.get("entry_price"))
    risk_pct = _safe_float(row.get("entry_risk_distance_pct"))
    if entry_price > 0 and risk_pct > 0:
        return entry_price * risk_pct
    return np.nan


def _first_r_event(day: pd.DataFrame, direction: str, entry_price: float, risk_price: float, r_value: float) -> tuple[str, int, str]:
    sign = _direction_sign(direction)
    progress_price = entry_price + sign * r_value * risk_price
    adverse_price = entry_price - sign * r_value * risk_price
    for idx, item in enumerate(day.itertuples(index=False)):
        if direction == "long":
            progress_hit = _safe_float(item.high) >= progress_price
            adverse_hit = _safe_float(item.low) <= adverse_price
        else:
            progress_hit = _safe_float(item.low) <= progress_price
            adverse_hit = _safe_float(item.high) >= adverse_price
        if progress_hit and adverse_hit:
            return "ambiguous_same_bar", idx, pd.Timestamp(item.bar_datetime).strftime("%Y-%m-%d %H:%M")
        if adverse_hit:
            return "adverse_first", idx, pd.Timestamp(item.bar_datetime).strftime("%Y-%m-%d %H:%M")
        if progress_hit:
            return "progress_first", idx, pd.Timestamp(item.bar_datetime).strftime("%Y-%m-%d %H:%M")
    return "neither", -1, ""


def _early_state(day: pd.DataFrame, direction: str) -> dict[str, Any]:
    early = day.head(EARLY_BARS).reset_index(drop=True)
    out: dict[str, Any] = {
        "early_bars": int(len(early)),
        "early_state": "missing",
        "early_price_dir_return_pct": np.nan,
        "early_oi_change_pct": np.nan,
        "early_volume_sum": np.nan,
        "early_exit_price": np.nan,
        "early_last_time": "",
    }
    if len(early) < max(15, min(EARLY_BARS, 15)):
        return out
    sign = _direction_sign(direction)
    open_price = _safe_float(early.iloc[0].get("open"))
    close_price = _safe_float(early.iloc[-1].get("close"))
    open_oi = _safe_float(early.iloc[0].get("open_oi"))
    close_oi = _safe_float(early.iloc[-1].get("close_oi"))
    price_ret = sign * (close_price / open_price - 1.0) if open_price > 0 else np.nan
    oi_chg = (close_oi - open_oi) / open_oi if open_oi > 0 else np.nan
    if not np.isfinite(price_ret) or not np.isfinite(oi_chg):
        state = "missing"
    elif price_ret >= 0 and oi_chg >= 0:
        state = "favorable_price_oi_up"
    elif price_ret >= 0 and oi_chg < 0:
        state = "favorable_price_oi_down"
    elif price_ret < 0 and oi_chg >= 0:
        state = "adverse_price_oi_up"
    else:
        state = "adverse_price_oi_down"
    out.update(
        {
            "early_state": state,
            "early_price_dir_return_pct": price_ret * 100.0 if np.isfinite(price_ret) else np.nan,
            "early_oi_change_pct": oi_chg * 100.0 if np.isfinite(oi_chg) else np.nan,
            "early_volume_sum": float(pd.to_numeric(early.get("volume"), errors="coerce").fillna(0).sum()),
            "early_exit_price": close_price,
            "early_last_time": pd.Timestamp(early.iloc[-1]["bar_datetime"]).strftime("%Y-%m-%d %H:%M"),
        }
    )
    return out


def _opening_range(day: pd.DataFrame, direction: str, entry_price: float) -> dict[str, Any]:
    opening = day.head(OPENING_RANGE_BARS).reset_index(drop=True)
    out = {
        "or_bars": int(len(opening)),
        "or_high": np.nan,
        "or_low": np.nan,
        "or_width_pct": np.nan,
        "or_extension": np.nan,
        "or_extension_bucket": "missing_or",
    }
    if opening.empty:
        return out
    high = float(pd.to_numeric(opening["high"], errors="coerce").max())
    low = float(pd.to_numeric(opening["low"], errors="coerce").min())
    width = high - low
    if not np.isfinite(width) or width <= 0:
        return out
    edge = high if direction == "long" else low
    extension = _direction_sign(direction) * (entry_price - edge) / width
    bucket = "missing_or"
    if np.isfinite(extension):
        if extension <= 0:
            bucket = "inside_or_or_opposite"
        elif extension <= 1:
            bucket = "edge_to_1or"
        else:
            bucket = "extended_gt_1or"
    out.update(
        {
            "or_high": high,
            "or_low": low,
            "or_width_pct": (width / low * 100.0) if low > 0 else np.nan,
            "or_extension": extension,
            "or_extension_bucket": bucket,
        }
    )
    return out


def _lot_minute_features(row: pd.Series, minute_by_symbol: dict[str, pd.DataFrame], event_by_trade: dict[str, dict[str, Any]]) -> dict[str, Any]:
    vt_symbol = str(row.get("vt_symbol", ""))
    entry_date = pd.Timestamp(row.get("entry_date")).normalize()
    direction = str(row.get("direction", ""))
    entry_price = _safe_float(row.get("entry_price"))
    volume = _safe_float(row.get("volume"))
    size = _safe_float(row.get("size"))
    realized_pnl = _safe_float(row.get("realized_pnl"), 0.0)
    event_info = event_by_trade.get(str(row.get("open_trade_id", "")), {})
    risk_price = _risk_price(row, event_info)
    bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
    day = (
        bars[bars["bar_date"].eq(entry_date)].copy().sort_values("bar_datetime").reset_index(drop=True)
        if not bars.empty
        else pd.DataFrame()
    )
    base: dict[str, Any] = {
        "lot_id": int(_safe_float(row.get("lot_id"), -1)),
        "minute_bars_on_entry_day": int(len(day)),
        "minute_coverage_state": "entry_day_covered" if not day.empty else "missing_entry_day",
        "retry_role": event_info.get("retry_role", "non_retry_lot"),
        "retry_final_state": event_info.get("retry_final_state", ""),
        "retry_event_trade_id": event_info.get("retry_event_trade_id", ""),
        "retry_reentry_trade_id": event_info.get("retry_reentry_trade_id", ""),
        "risk_price": risk_price,
        "first_0p5r_outcome": "missing",
        "first_0p5r_bar_index": -1,
        "first_0p5r_time": "",
        "first_1p0r_outcome": "missing",
        "entry_day_mfe_r": np.nan,
        "entry_day_mae_r": np.nan,
        "entry_day_close_return_pct": np.nan,
        "entry_day_close_location_signal_side": np.nan,
        "entry_day_eod_price": np.nan,
        "entry_day_eod_pnl": np.nan,
        "eod_exit_delta": np.nan,
        "held_beyond_entry_day": int(pd.Timestamp(row.get("exit_date")).normalize() > entry_date)
        if pd.notna(row.get("exit_date"))
        else 0,
    }
    if day.empty or not (entry_price > 0 and risk_price > 0 and volume > 0 and size > 0):
        base.update(_early_state(pd.DataFrame(), direction))
        base.update(_opening_range(pd.DataFrame(), direction, entry_price))
        return base
    sign = _direction_sign(direction)
    day_high = float(pd.to_numeric(day["high"], errors="coerce").max())
    day_low = float(pd.to_numeric(day["low"], errors="coerce").min())
    day_close = _safe_float(day.iloc[-1].get("close"))
    favorable = day_high - entry_price if direction == "long" else entry_price - day_low
    adverse = entry_price - day_low if direction == "long" else day_high - entry_price
    first_05, first_05_idx, first_05_time = _first_r_event(day, direction, entry_price, risk_price, 0.5)
    first_10, _, _ = _first_r_event(day, direction, entry_price, risk_price, 1.0)
    day_range = day_high - day_low
    close_location = np.nan
    if day_range > 0:
        close_location = (day_close - day_low) / day_range if direction == "long" else (day_high - day_close) / day_range
    eod_pnl = sign * (day_close - entry_price) * volume * size
    base.update(
        {
            "first_0p5r_outcome": first_05,
            "first_0p5r_bar_index": first_05_idx,
            "first_0p5r_time": first_05_time,
            "first_1p0r_outcome": first_10,
            "entry_day_mfe_r": favorable / risk_price,
            "entry_day_mae_r": adverse / risk_price,
            "entry_day_close_return_pct": sign * (day_close / entry_price - 1.0) * 100.0,
            "entry_day_close_location_signal_side": close_location,
            "entry_day_eod_price": day_close,
            "entry_day_eod_pnl": eod_pnl,
            "eod_exit_delta": eod_pnl - realized_pnl,
        }
    )
    early = _early_state(day, direction)
    if np.isfinite(_safe_float(early.get("early_exit_price"))):
        early_pnl = sign * (_safe_float(early["early_exit_price"]) - entry_price) * volume * size
        early["early_exit_pnl"] = early_pnl
        early["early_exit_delta"] = early_pnl - realized_pnl
    else:
        early["early_exit_pnl"] = np.nan
        early["early_exit_delta"] = np.nan
    base.update(early)
    base.update(_opening_range(day, direction, entry_price))
    return base


def _build_features() -> pd.DataFrame:
    lots = _prepare_closed_lots()
    event_by_trade = _prepare_event_maps()
    minute_bars = _prepare_minute_bars(set(lots["vt_symbol"].astype(str).dropna()))
    minute_by_symbol = s825._minute_groups(minute_bars)
    minute_features = pd.DataFrame(
        [_lot_minute_features(row, minute_by_symbol, event_by_trade) for _, row in lots.iterrows()]
    )
    return lots.merge(minute_features, on="lot_id", how="left")


def _shape_masks(features: pd.DataFrame) -> list[tuple[str, str, pd.Series]]:
    first05 = features["first_0p5r_outcome"].astype(str)
    close_ret = pd.to_numeric(features["entry_day_close_return_pct"], errors="coerce")
    close_loc = pd.to_numeric(features["entry_day_close_location_signal_side"], errors="coerce")
    early_state = features["early_state"].astype(str)
    return [
        (
            "A_adverse_first_05r",
            "Entry-day first 0.5R event is adverse; C9 stop/retry already acts on this family.",
            first05.eq("adverse_first"),
        ),
        (
            "B_progress_first_then_close_below_entry",
            "Entry-day reaches +0.5R first, then closes against entry direction.",
            first05.eq("progress_first") & close_ret.lt(0),
        ),
        (
            "C_progress_first_then_close_adverse_half",
            "Entry-day reaches +0.5R first, then closes in the adverse half of the day range.",
            first05.eq("progress_first") & close_loc.lt(0.5),
        ),
        (
            "D_neither_05r_then_close_below_entry",
            "Entry-day hits neither +/-0.5R, then closes against entry direction.",
            first05.eq("neither") & close_ret.lt(0),
        ),
        (
            "E_early60_adverse_any_oi",
            "First 60 entry-day bars move against signal, regardless of OI.",
            early_state.str.startswith("adverse_price"),
        ),
        (
            "F_early60_adverse_oi_down",
            "First 60 entry-day bars move against signal while OI falls.",
            early_state.eq("adverse_price_oi_down"),
        ),
        (
            "G_or15_extended_gt_1or",
            "Entry price is more than 1x OR15 width beyond the signal-side OR edge.",
            features["or_extension_bucket"].astype(str).eq("extended_gt_1or"),
        ),
    ]


def _shape_coverage(features: pd.DataFrame) -> pd.DataFrame:
    total_loser_pnl = float(pd.to_numeric(features["realized_pnl"], errors="coerce").clip(upper=0).sum())
    rows: list[dict[str, Any]] = []
    for shape_id, shape_text, mask in _shape_masks(features):
        affected = mask.fillna(False)
        group = features[affected].copy()
        pnl = pd.to_numeric(group["realized_pnl"], errors="coerce").fillna(0.0)
        losers = pnl.lt(0)
        winners = pnl.gt(0)
        loser_pnl = float(pnl[losers].sum())
        rows.append(
            {
                "shape_id": shape_id,
                "shape_text": shape_text,
                "affected_lots": int(affected.sum()),
                "affected_lot_pct": float(affected.mean() * 100.0),
                "affected_pnl": float(pnl.sum()),
                "loser_lots": int(losers.sum()),
                "loser_pnl": loser_pnl,
                "loser_pnl_coverage_pct": float(abs(loser_pnl) / abs(total_loser_pnl) * 100.0)
                if total_loser_pnl < 0
                else 0.0,
                "winner_lots": int(winners.sum()),
                "winner_pnl": float(pnl[winners].sum()),
                "big_winner_lots": int(pd.to_numeric(group.get("big_winner"), errors="coerce").fillna(0).sum()),
                "median_r": float(pd.to_numeric(group.get("r_multiple"), errors="coerce").median()) if len(group) else np.nan,
                "median_entry_day_close_return_pct": float(
                    pd.to_numeric(group.get("entry_day_close_return_pct"), errors="coerce").median()
                )
                if len(group)
                else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _proxy_definitions(features: pd.DataFrame) -> list[dict[str, Any]]:
    first05 = features["first_0p5r_outcome"].astype(str)
    close_ret = pd.to_numeric(features["entry_day_close_return_pct"], errors="coerce")
    close_loc = pd.to_numeric(features["entry_day_close_location_signal_side"], errors="coerce")
    early_state = features["early_state"].astype(str)
    return [
        {
            "proxy_id": "EOD1_progress_first_close_below_entry",
            "proxy_type": "entry_day_eod_exit",
            "rule_text": "If +0.5R is hit first but entry day closes against the signal, exit at entry-day close.",
            "mask": first05.eq("progress_first") & close_ret.lt(0),
        },
        {
            "proxy_id": "EOD2_progress_first_close_adverse_half",
            "proxy_type": "entry_day_eod_exit",
            "rule_text": "If +0.5R is hit first but close is in the adverse half of the entry-day range, exit at entry-day close.",
            "mask": first05.eq("progress_first") & close_loc.lt(0.5),
        },
        {
            "proxy_id": "EOD3_neither_05r_close_below_entry",
            "proxy_type": "entry_day_eod_exit",
            "rule_text": "If neither +/-0.5R is hit and entry day closes against the signal, exit at entry-day close.",
            "mask": first05.eq("neither") & close_ret.lt(0),
        },
        {
            "proxy_id": "EARLY1_exit60_adverse_any_oi",
            "proxy_type": "first60_exit",
            "rule_text": "If first 60 entry-day bars move against signal, exit at the 60th-bar close.",
            "mask": early_state.str.startswith("adverse_price"),
        },
        {
            "proxy_id": "OR1_skip_extended_gt_1or",
            "proxy_type": "skip_entry",
            "rule_text": "Skip entries extended more than 1x OR15 width beyond the signal-side edge.",
            "mask": features["or_extension_bucket"].astype(str).eq("extended_gt_1or"),
        },
    ]


def _proxy_summary(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    original = pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0)
    base_total = float(original.sum())
    rows: list[dict[str, Any]] = []
    yearly_rows: list[dict[str, Any]] = []
    for item in _proxy_definitions(features):
        mask = item["mask"].fillna(False)
        if item["proxy_type"] == "entry_day_eod_exit":
            applicable = mask & features["held_beyond_entry_day"].eq(1) & pd.to_numeric(features["eod_exit_delta"], errors="coerce").notna()
            delta = pd.Series(0.0, index=features.index)
            delta.loc[applicable] = pd.to_numeric(features.loc[applicable, "eod_exit_delta"], errors="coerce").fillna(0.0)
        elif item["proxy_type"] == "first60_exit":
            applicable = mask & pd.to_numeric(features["early_exit_delta"], errors="coerce").notna()
            delta = pd.Series(0.0, index=features.index)
            delta.loc[applicable] = pd.to_numeric(features.loc[applicable, "early_exit_delta"], errors="coerce").fillna(0.0)
        else:
            applicable = mask
            delta = pd.Series(0.0, index=features.index)
            delta.loc[applicable] = -original.loc[applicable]
        winners = applicable & original.gt(0)
        losers = applicable & original.lt(0)
        big = applicable & pd.to_numeric(features["big_winner"], errors="coerce").fillna(0).eq(1)
        yearly = (
            pd.DataFrame(
                {
                    "entry_year": features["entry_year"],
                    "affected": applicable.astype(int),
                    "delta": delta,
                    "winner_delta": np.where(winners, delta, 0.0),
                    "loser_delta": np.where(losers, delta, 0.0),
                    "big_delta": np.where(big, delta, 0.0),
                }
            )
            .groupby("entry_year", dropna=False)
            .agg(
                affected_lots=("affected", "sum"),
                gross_proxy_delta=("delta", "sum"),
                winner_cut=("winner_delta", "sum"),
                loser_saved=("loser_delta", "sum"),
                big_winner_cut=("big_delta", "sum"),
            )
            .reset_index()
        )
        gross_delta = float(delta.sum())
        rows.append(
            {
                "proxy_id": item["proxy_id"],
                "proxy_type": item["proxy_type"],
                "rule_text": item["rule_text"],
                "trigger_lots": int(mask.sum()),
                "applicable_lots": int(applicable.sum()),
                "applicable_lot_pct": float(applicable.mean() * 100.0),
                "affected_original_pnl": float(original.loc[applicable].sum()),
                "gross_proxy_delta": gross_delta,
                "base_total_pnl": base_total,
                "proxy_total_pnl": base_total + gross_delta,
                "winner_cut": float(delta.loc[winners].sum()),
                "loser_saved": float(delta.loc[losers].sum()),
                "big_winner_cut": float(delta.loc[big].sum()),
                "affected_big_winner_lots": int(big.sum()),
                "positive_delta_years": int(yearly["gross_proxy_delta"].gt(0).sum()),
                "negative_delta_years": int(yearly["gross_proxy_delta"].lt(0).sum()),
                "decision_hint": "positive_proxy_only_needs_true_engine" if gross_delta > 0 else "not_promoted_proxy_negative",
            }
        )
        for _, year_row in yearly.iterrows():
            yearly_rows.append(
                {
                    "proxy_id": item["proxy_id"],
                    "entry_year": int(year_row["entry_year"]) if pd.notna(year_row["entry_year"]) else 0,
                    "affected_lots": int(year_row["affected_lots"]),
                    "gross_proxy_delta": float(year_row["gross_proxy_delta"]),
                    "winner_cut": float(year_row["winner_cut"]),
                    "loser_saved": float(year_row["loser_saved"]),
                    "big_winner_cut": float(year_row["big_winner_cut"]),
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(yearly_rows)


def _retry_role_summary(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_cols = ["retry_role", "retry_final_state"]
    for keys, group in features.groupby(group_cols, dropna=False):
        pnl = pd.to_numeric(group["realized_pnl"], errors="coerce").fillna(0.0)
        rows.append(
            {
                "retry_role": str(keys[0]),
                "retry_final_state": str(keys[1]),
                "lots": int(len(group)),
                "pnl_sum": float(pnl.sum()),
                "loser_lots": int(pnl.lt(0).sum()),
                "winner_lots": int(pnl.gt(0).sum()),
                "big_winner_lots": int(pd.to_numeric(group["big_winner"], errors="coerce").fillna(0).sum()),
                "median_r": float(pd.to_numeric(group["r_multiple"], errors="coerce").median()),
            }
        )
    return pd.DataFrame(rows).sort_values(["retry_role", "retry_final_state"]).reset_index(drop=True)


def _plot_summary(shape_coverage: pd.DataFrame, proxy_summary: pd.DataFrame, retry_summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(17, 13), constrained_layout=True)
    axes[0].bar(shape_coverage["shape_id"], shape_coverage["loser_pnl_coverage_pct"], color="#dc2626")
    axes[0].set_title("C9 loser PnL coverage by fixed minute shape")
    axes[0].set_ylabel("loser PnL coverage (%)")
    axes[0].tick_params(axis="x", rotation=20, labelsize=8)
    axes[0].grid(axis="y", alpha=0.2)

    colors = np.where(proxy_summary["gross_proxy_delta"].gt(0), "#16a34a", "#64748b")
    axes[1].bar(proxy_summary["proxy_id"], proxy_summary["gross_proxy_delta"] / 1_000_000, color=colors)
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[1].set_title("Proxy delta for real-time candidate actions")
    axes[1].set_ylabel("delta, million")
    axes[1].tick_params(axis="x", rotation=20, labelsize=8)
    axes[1].grid(axis="y", alpha=0.2)

    retry = retry_summary.copy()
    retry["label"] = retry["retry_role"] + "\n" + retry["retry_final_state"]
    axes[2].bar(retry["label"], retry["pnl_sum"] / 1_000_000, color="#7c3aed")
    axes[2].axhline(0, color="#111827", linewidth=0.8)
    axes[2].set_title("C9 PnL by retry role")
    axes[2].set_ylabel("PnL, million")
    axes[2].tick_params(axis="x", rotation=20, labelsize=8)
    axes[2].grid(axis="y", alpha=0.2)
    fig.savefig(SUMMARY_CHART_PATH, dpi=150)
    plt.close(fig)


def _select_atlas_rows(features: pd.DataFrame) -> pd.DataFrame:
    masks = {shape_id: mask for shape_id, _, mask in _shape_masks(features)}
    parts: list[pd.DataFrame] = []
    for shape_id in [
        "B_progress_first_then_close_below_entry",
        "C_progress_first_then_close_adverse_half",
        "D_neither_05r_then_close_below_entry",
        "E_early60_adverse_any_oi",
        "G_or15_extended_gt_1or",
    ]:
        subset = features[masks[shape_id].fillna(False)].copy()
        if subset.empty:
            continue
        subset["atlas_shape_id"] = shape_id
        parts.append(subset.sort_values("realized_pnl", ascending=True).head(2))
        parts.append(subset.sort_values("realized_pnl", ascending=False).head(2))
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True).drop_duplicates("lot_id").head(MAX_ATLAS_ROWS).reset_index(drop=True)


def _plot_row(ax: plt.Axes, row: pd.Series, minute_by_symbol: dict[str, pd.DataFrame]) -> dict[str, Any]:
    vt_symbol = str(row["vt_symbol"])
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    direction = str(row["direction"])
    bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
    day = (
        bars[bars["bar_date"].eq(entry_date)].copy().sort_values("bar_datetime").head(340).reset_index(drop=True)
        if not bars.empty
        else pd.DataFrame()
    )
    record = {
        "lot_id": int(_safe_float(row.get("lot_id"), -1)),
        "vt_symbol": vt_symbol,
        "entry_date": entry_date.strftime("%Y-%m-%d") if pd.notna(entry_date) else "",
        "atlas_shape_id": str(row.get("atlas_shape_id", "")),
        "chart_missing_minutes": int(day.empty),
    }
    if day.empty:
        ax.axis("off")
        ax.text(0.5, 0.5, f"missing minute bars\n{vt_symbol} {entry_date:%Y-%m-%d}", ha="center", va="center")
        return record
    s825._plot_candles(ax, day)
    entry_price = _safe_float(row.get("entry_price"))
    risk_price = _safe_float(row.get("risk_price"))
    sign = _direction_sign(direction)
    ax.axhline(entry_price, color="#1d4ed8", linewidth=1.0, alpha=0.9, label="entry")
    if risk_price > 0:
        ax.axhline(entry_price - sign * 0.5 * risk_price, color="#ef4444", linewidth=0.9, alpha=0.85, label="-0.5R")
        ax.axhline(entry_price + sign * 0.5 * risk_price, color="#22c55e", linewidth=0.9, alpha=0.85, label="+0.5R")
    if len(day) >= EARLY_BARS:
        ax.axvspan(0, EARLY_BARS - 1, color="#fef3c7", alpha=0.22)
    if len(day) >= OPENING_RANGE_BARS:
        ax.axvspan(0, OPENING_RANGE_BARS - 1, color="#dbeafe", alpha=0.18)
    ax2 = ax.twinx()
    if "close_oi" in day.columns and pd.to_numeric(day["close_oi"], errors="coerce").notna().any():
        ax2.plot(np.arange(len(day)), day["close_oi"], color="#7c3aed", linewidth=0.7, alpha=0.55)
        ax2.tick_params(axis="y", labelsize=6, colors="#7c3aed")
    ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
    ax.set_xticks(ticks)
    ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
    ax.tick_params(axis="y", labelsize=7)
    ax.grid(True, alpha=0.18, linewidth=0.5)
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        dedup = dict(zip(labels, handles))
        ax.legend(dedup.values(), dedup.keys(), loc="best", fontsize=7)
    title = (
        f"lot{int(_safe_float(row.get('lot_id'), -1))} {vt_symbol} {direction} {entry_date:%Y-%m-%d} "
        f"{row.get('atlas_shape_id')} first05={row.get('first_0p5r_outcome')} "
        f"close={_safe_float(row.get('entry_day_close_return_pct')):.2f}% "
        f"loc={_safe_float(row.get('entry_day_close_location_signal_side')):.2f} "
        f"early={row.get('early_state')} pnl={_safe_float(row.get('realized_pnl')):,.0f}"
    )
    ax.set_title(title, fontsize=8.0, loc="left")
    return record


def _plot_atlas(features: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_rows(features)
    if selected.empty:
        return [], pd.DataFrame()
    minute_bars = _prepare_minute_bars(set(selected["vt_symbol"].astype(str).dropna()))
    minute_by_symbol = s825._minute_groups(minute_bars)
    page_count = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    records: list[dict[str, Any]] = []
    for page in range(1, page_count + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.0, 3.25 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            rec = _plot_row(ax, row, minute_by_symbol)
            rec.update(
                {
                    "chart_page": page,
                    "realized_pnl": _safe_float(row.get("realized_pnl")),
                    "first_0p5r_outcome": str(row.get("first_0p5r_outcome", "")),
                    "early_state": str(row.get("early_state", "")),
                    "or_extension_bucket": str(row.get("or_extension_bucket", "")),
                }
            )
            records.append(rec)
        fig.suptitle(
            (
                f"Stage889 C9 loss-shape coverage atlas page {page}/{page_count}; "
                "blue=entry, red=-0.5R, green=+0.5R, purple=OI, yellow=first60, blue shade=OR15"
            ),
            fontsize=13,
        )
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(records)


def _decision(features: pd.DataFrame, proxy_summary: pd.DataFrame) -> str:
    eod = proxy_summary[proxy_summary["proxy_type"].eq("entry_day_eod_exit")]
    positive_eod = eod[eod["gross_proxy_delta"].gt(0)].copy()
    if positive_eod.empty:
        return "stage889_c9_loss_shape_no_clean_new_rule_proxy_negative"
    best = positive_eod.sort_values("gross_proxy_delta", ascending=False).iloc[0]
    loser_pnl = abs(float(pd.to_numeric(features["realized_pnl"], errors="coerce").clip(upper=0).sum()))
    materiality = loser_pnl * 0.01
    if _safe_float(best.get("gross_proxy_delta"), 0.0) < materiality:
        return "stage889_c9_loss_shape_tiny_positive_proxy_year_fragile_no_engine"
    if int(_safe_float(best.get("positive_delta_years"), 0.0)) < int(_safe_float(best.get("negative_delta_years"), 0.0)):
        return "stage889_c9_loss_shape_positive_proxy_year_fragile_no_engine"
    if _safe_float(best.get("winner_cut"), 0.0) < 0 and abs(_safe_float(best.get("winner_cut"), 0.0)) > _safe_float(
        best.get("loser_saved"), 0.0
    ):
        return "stage889_c9_loss_shape_positive_proxy_but_winner_cut_too_high"
    return "stage889_c9_loss_shape_has_frozen_eod_candidate_proxy_only"


def _write_report(
    features: pd.DataFrame,
    shape_coverage: pd.DataFrame,
    proxy_summary: pd.DataFrame,
    proxy_yearly: pd.DataFrame,
    retry_summary: pd.DataFrame,
    atlas_paths: list[Path],
    decision: str,
) -> None:
    total_pnl = float(pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0).sum())
    loser_pnl = float(pd.to_numeric(features["realized_pnl"], errors="coerce").clip(upper=0).sum())
    winner_pnl = float(pd.to_numeric(features["realized_pnl"], errors="coerce").clip(lower=0).sum())
    lines = [
        "# Stage889 C9 亏损分钟形态覆盖审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：C9 本体只读覆盖审计；不新增交易规则、不接真实引擎、不改正式版、不改候选配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- CME 风险管理资料支持预设止损和账户风险约束；CME open interest 资料支持把 OI 作为参与度辅助，而不是独立交易信号。",
        "- 趋势跟随资料支持减少 whipsaw 与假突破，但没有给出可直接复制的分钟参数；本阶段只使用 `0.5R`、`1R`、`OR15`、`first60` 这些本线已冻结过的低自由度形状做覆盖审计。",
        "- 我的判断：如果 C9 剩余亏损没有在这些形态中形成“救亏损多、砍赢家少”的结构，就不应该再在 C9 分钟K本体上扫小参数。",
        "",
        "## 核心总览",
        "",
        f"- C9 closed lots：`{len(features)}`",
        f"- C9 total PnL：`{total_pnl:,.2f}`",
        f"- C9 loser PnL：`{loser_pnl:,.2f}`",
        f"- C9 winner PnL：`{winner_pnl:,.2f}`",
        f"- decision：`{decision}`",
        "",
        "## Shape Coverage",
        "",
        _md_table(shape_coverage, max_rows=30),
        "",
        "## Proxy Summary",
        "",
        _md_table(proxy_summary, max_rows=30),
        "",
        "## Proxy Yearly",
        "",
        _md_table(proxy_yearly, max_rows=100),
        "",
        "## Retry Role Summary",
        "",
        _md_table(retry_summary, max_rows=30),
        "",
        "## Visual Atlas",
        "",
        f"- summary chart：`{SUMMARY_CHART_PATH}`",
        *[f"- atlas：`{path}`" for path in atlas_paths],
        "",
        "## 判断",
        "",
        f"- 决策：`{decision}`",
        "- 若 EOD / first60 / OR proxy 仍然显示右尾误伤大于左尾修复，则 C9 分钟K本体不应继续救参。",
        "- 若某个 EOD proxy 净正但幅度很小、年份不稳或 winner_cut 高，最多保留为复盘标签，不直接进入真实引擎。",
        "- 只有当某个 EOD proxy 同时具备足够幅度、年份稳定性和低 winner_cut，下一步才允许冻结一个真实引擎；仍不得扫描窗口、R小数、品种、方向或年份。",
        "",
        "## 输出文件",
        "",
        f"- features：`{FEATURES_PATH}`",
        f"- shape coverage：`{SHAPE_COVERAGE_PATH}`",
        f"- proxy summary：`{PROXY_SUMMARY_PATH}`",
        f"- proxy yearly：`{PROXY_YEARLY_PATH}`",
        f"- retry role summary：`{RETRY_ROLE_SUMMARY_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。本阶段只使用已冻结过的低自由度形态做覆盖审计，不生成新参数。",
        "- 运行后判断：以输出 decision 为准；若继续围绕微弱正代理扫窗口/R/年份/品种，就是过拟合。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。它能验证 C9 本体是否还有未覆盖的分钟级错误结构。",
        "- 运行后判断：以输出 decision 为准；若只有微弱、年份不稳的正代理，C9 分钟K本体继续价值下降，应转外生信息源或账户层非交易生存线。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features = _build_features()
    shape_coverage = _shape_coverage(features)
    proxy_summary, proxy_yearly = _proxy_summary(features)
    retry_summary = _retry_role_summary(features)
    _plot_summary(shape_coverage, proxy_summary, retry_summary)
    atlas_paths, atlas_manifest = _plot_atlas(features)
    decision = _decision(features, proxy_summary)

    features.to_csv(FEATURES_PATH, index=False, encoding="utf-8-sig")
    shape_coverage.to_csv(SHAPE_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    proxy_summary.to_csv(PROXY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    proxy_yearly.to_csv(PROXY_YEARLY_PATH, index=False, encoding="utf-8-sig")
    retry_summary.to_csv(RETRY_ROLE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    _write_report(features, shape_coverage, proxy_summary, proxy_yearly, retry_summary, atlas_paths, decision)

    best_proxy = proxy_summary.sort_values("gross_proxy_delta", ascending=False).iloc[0].to_dict()
    payload = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "decision": decision,
        "c9_closed_lots": int(len(features)),
        "c9_total_pnl": float(pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0).sum()),
        "c9_loser_pnl": float(pd.to_numeric(features["realized_pnl"], errors="coerce").clip(upper=0).sum()),
        "c9_winner_pnl": float(pd.to_numeric(features["realized_pnl"], errors="coerce").clip(lower=0).sum()),
        "best_proxy": best_proxy,
        "guardrails": {
            "strategy_changed": False,
            "official_stage372_changed": False,
            "official_candidate_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "formal_ab_triggered": False,
            "readonly_only": True,
            "new_rule_created": False,
        },
        "outputs": {
            "features": str(FEATURES_PATH),
            "shape_coverage": str(SHAPE_COVERAGE_PATH),
            "proxy_summary": str(PROXY_SUMMARY_PATH),
            "proxy_yearly": str(PROXY_YEARLY_PATH),
            "retry_role_summary": str(RETRY_ROLE_SUMMARY_PATH),
            "summary_chart": str(SUMMARY_CHART_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
