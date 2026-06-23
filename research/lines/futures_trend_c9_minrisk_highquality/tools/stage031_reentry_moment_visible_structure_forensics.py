from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage031"
MODEL_TAG = "stage031_reentry_moment_visible_structure_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage031_c9_minrisk_reentry_moment_visible_structure"
ACCOUNT_CAPITAL = 150_000.0
TRADING_DAYS_PER_YEAR = 252
PER_PAGE = 4
MAX_ATLAS_EVENTS = 20

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage010_authoritative_minute_coverage_audit as s010
import stage030_stop_retry_event_quality_forensics as s030
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE030_DIR = LINE_DIR / "outputs" / "stage030_stop_retry_event_quality_forensics"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage031_reentry_moment_visible_structure_forensics"

FEATURES_IN = STAGE030_DIR / (
    "qmt_roll_stage030_c9_minrisk_stop_retry_event_quality_forensics_features_"
    "stage030_stop_retry_event_quality_forensics_v1.csv"
)
OFFICIAL_CURVE_IN = s030.OFFICIAL_CURVE_IN

EVENT_FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_features_{MODEL_TAG}.csv"
LOT_FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_features_{MODEL_TAG}.csv"
EVENT_SHAPE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_shape_summary_{MODEL_TAG}.csv"
LOT_SHAPE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_shape_summary_{MODEL_TAG}.csv"
SHAPE_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_shape_year_matrix_{MODEL_TAG}.csv"
SHAPE_PRODUCT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_shape_product_matrix_{MODEL_TAG}.csv"
CONTRIB_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contribution_curve_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_reentry_shape_chart_{MODEL_TAG}.png"
SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_reentry_moment_scatter_{MODEL_TAG}.png"
SHAPE_STATE_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_shape_state_heatmap_{MODEL_TAG}.png"
PRODUCT_SHAPE_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_shape_heatmap_{MODEL_TAG}.png"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

REENTRY_STATES = ["flat_retry_failed", "open_after_reentry"]
SHAPE_ORDER = [
    "close_body_strong_reclaim",
    "close_strong_reclaim",
    "thin_close_reclaim",
    "wick_or_close_back_inside",
    "missing_reentry_minute",
]
SHAPE_COLORS = {
    "close_body_strong_reclaim": "#2ca02c",
    "close_strong_reclaim": "#17becf",
    "thin_close_reclaim": "#ff7f0e",
    "wick_or_close_back_inside": "#d62728",
    "missing_reentry_minute": "#7f7f7f",
}
STATE_COLORS = {
    "flat_retry_failed": "#d62728",
    "open_after_reentry": "#2ca02c",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    display = data.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    headers = [str(column) for column in display.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in display.columns) + " |")
    return "\n".join(lines)


def _load_features() -> pd.DataFrame:
    frame = _read_csv(FEATURES_IN)
    for column in ["entry_date", "exit_date", "prev_state_date"]:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.normalize()
    for column in ["first_stop_time", "reentry_time", "retry_failed_time"]:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], errors="coerce")
    for column in [
        "realized_pnl",
        "r_multiple",
        "entry_price",
        "entry_price_event",
        "stop_price",
        "progress_price",
        "risk_price",
        "risk_price_event",
        "first_stop_bar_index",
        "reentry_bar_index",
        "reentry_latency_bars",
        "retry_failed_bar_index",
        "volume",
        "size",
    ]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["vt_symbol"] = frame["vt_symbol"].astype(str)
    frame["direction"] = frame["direction"].astype(str)
    frame["product"] = frame["product"].astype(str)
    frame["stop_retry_state"] = frame["stop_retry_state"].astype(str)
    frame["event_key"] = frame["event_key"].astype(str)
    frame["entry_year"] = pd.to_numeric(frame["entry_year"], errors="coerce").astype("Int64")
    return frame


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(OFFICIAL_CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct", "slippage", "trade_count"]:
        curve[column] = pd.to_numeric(curve.get(column, 0.0), errors="coerce").fillna(0.0)
    prev_equity = curve["account_equity"].shift(1)
    prev_equity.iloc[0] = ACCOUNT_CAPITAL
    curve["daily_return"] = (curve["account_equity"] / prev_equity - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return curve


def _official_metrics(curve: pd.DataFrame, features: pd.DataFrame) -> dict[str, float]:
    returns = pd.to_numeric(curve["daily_return"], errors="coerce").fillna(0.0)
    std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    start = float(curve["account_equity"].iloc[0]) if not curve.empty else ACCOUNT_CAPITAL
    end = float(curve["account_equity"].iloc[-1]) if not curve.empty else ACCOUNT_CAPITAL
    pnl = pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0)
    return {
        "end_equity": end,
        "total_return_pct": (end / start - 1.0) * 100.0 if start else np.nan,
        "max_drawdown_pct": float(pd.to_numeric(curve["drawdown_pct"], errors="coerce").min()),
        "sharpe": float(returns.mean() / std * np.sqrt(TRADING_DAYS_PER_YEAR)) if std > 0 else 0.0,
        "total_slippage": float(pd.to_numeric(curve["slippage"], errors="coerce").sum()),
        "total_trade_count": float(pd.to_numeric(curve["trade_count"], errors="coerce").sum()),
        "closed_lot_win_rate_pct": float((pnl > 0.0).mean() * 100.0),
        "closed_lot_count": float(len(features)),
    }


def _build_reentry_events(features: pd.DataFrame) -> pd.DataFrame:
    data = features[features["stop_retry_state"].isin(REENTRY_STATES)].copy()
    rows: list[dict[str, Any]] = []
    for event_key, group in data.groupby("event_key", sort=False):
        row = group.iloc[0]
        pnl = pd.to_numeric(group["realized_pnl"], errors="coerce").fillna(0.0)
        entry_price = _safe_float(row.get("entry_price_event"), _safe_float(row.get("entry_price")))
        risk_price = _safe_float(row.get("risk_price_event"), _safe_float(row.get("risk_price")))
        if not np.isfinite(risk_price) or risk_price <= 0:
            stop_price = _safe_float(row.get("stop_price"))
            risk_price = abs(entry_price - stop_price) * 2.0 if np.isfinite(entry_price) and np.isfinite(stop_price) else np.nan
        rows.append(
            {
                "event_key": event_key,
                "vt_symbol": str(row.get("vt_symbol")),
                "product": str(row.get("product")),
                "direction": str(row.get("direction")),
                "entry_date": row.get("entry_date"),
                "entry_year": row.get("entry_year"),
                "stop_retry_state": str(row.get("stop_retry_state")),
                "entry_price_event": entry_price,
                "risk_price_event": risk_price,
                "stop_price": _safe_float(row.get("stop_price")),
                "progress_price": _safe_float(row.get("progress_price")),
                "first_stop_time": row.get("first_stop_time"),
                "first_stop_bar_index": _safe_float(row.get("first_stop_bar_index")),
                "reentry_time": row.get("reentry_time"),
                "reentry_bar_index": _safe_float(row.get("reentry_bar_index")),
                "reentry_latency_bars": _safe_float(row.get("reentry_latency_bars")),
                "retry_failed_time": row.get("retry_failed_time"),
                "retry_failed_bar_index": _safe_float(row.get("retry_failed_bar_index")),
                "lot_count": int(len(group)),
                "event_realized_pnl": float(pnl.sum()),
                "positive_pnl": float(pnl.clip(lower=0.0).sum()),
                "negative_pnl": float(pnl.clip(upper=0.0).sum()),
                "event_win_lot_count": int((pnl > 0.0).sum()),
                "entry_quality_label_stage030": str(row.get("entry_quality_label_stage030")),
            }
        )
    return pd.DataFrame(rows)


def _load_minute_groups(events: pd.DataFrame) -> dict[str, pd.DataFrame]:
    selected_symbols = set(events["vt_symbol"].astype(str).dropna().unique())
    minute_bars = s010.s008.s928._load_stage861_full_minute_bars(selected_symbols)
    return s010.s008.s825._minute_groups(minute_bars)


def _signed_move(price: float, entry: float, risk: float, direction: str) -> float:
    if not np.isfinite(price) or not np.isfinite(entry) or not np.isfinite(risk) or risk <= 0:
        return np.nan
    sign = 1.0 if str(direction).lower() == "long" else -1.0
    return sign * (price - entry) / risk


def _bar_position(day: pd.DataFrame, timestamp: Any) -> int | None:
    ts = pd.to_datetime(timestamp, errors="coerce")
    if pd.isna(ts) or day.empty:
        return None
    bar_times = pd.to_datetime(day["bar_datetime"], errors="coerce")
    matches = np.flatnonzero(bar_times.eq(ts).to_numpy())
    if len(matches) == 0:
        return None
    return int(matches[0])


def _reentry_shape(row: dict[str, Any]) -> str:
    if int(row.get("reentry_minute_ready", 0)) != 1:
        return "missing_reentry_minute"
    close_gap = _safe_float(row.get("reentry_close_gap_r"))
    body = _safe_float(row.get("reentry_body_r"))
    close_pos = _safe_float(row.get("reentry_close_position"))
    if close_gap > 0.0 and body > 0.0 and close_pos >= 0.5:
        return "close_body_strong_reclaim"
    if close_gap > 0.0 and close_pos >= 0.5:
        return "close_strong_reclaim"
    if close_gap > 0.0:
        return "thin_close_reclaim"
    return "wick_or_close_back_inside"


def _volume_bucket(value: Any) -> str:
    ratio = _safe_float(value)
    if not np.isfinite(ratio):
        return "volume_missing"
    if ratio >= 1.2:
        return "volume_expansion_ge120"
    if ratio <= 0.8:
        return "volume_contraction_le80"
    return "volume_neutral_80_120"


def _add_reentry_minute_features(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return events
    groups = _load_minute_groups(events)
    rows: list[dict[str, Any]] = []
    for _, event in events.iterrows():
        row = event.to_dict()
        vt_symbol = str(row.get("vt_symbol"))
        entry_day = s010._normalize_day(row.get("entry_date"))
        day = s010._day_for_symbol(groups, vt_symbol, entry_day)
        day = day.copy().reset_index(drop=True) if not day.empty else pd.DataFrame()
        entry = _safe_float(row.get("entry_price_event"))
        risk = _safe_float(row.get("risk_price_event"))
        direction = str(row.get("direction"))
        reentry_pos = _bar_position(day, row.get("reentry_time"))
        first_stop_pos = _bar_position(day, row.get("first_stop_time"))
        row.update(
            {
                "stage861_reentry_day_minute_bars": int(len(day)),
                "reentry_minute_ready": 0,
                "reentry_bar_pos_stage861": np.nan,
                "first_stop_bar_pos_stage861": np.nan,
                "reentry_open_gap_r": np.nan,
                "reentry_close_gap_r": np.nan,
                "reentry_body_r": np.nan,
                "reentry_range_r": np.nan,
                "reentry_close_position": np.nan,
                "reentry_volume_ratio_20": np.nan,
                "reentry_oi_delta": np.nan,
                "worst_adverse_after_stop_to_reentry_r": np.nan,
                "best_favorable_after_stop_to_reentry_r": np.nan,
                "first_stop_to_reentry_close_slope_r_per_bar": np.nan,
            }
        )
        if day.empty or reentry_pos is None or not np.isfinite(entry) or not np.isfinite(risk) or risk <= 0:
            row["reentry_visible_shape"] = "missing_reentry_minute"
            row["reentry_volume_bucket"] = "volume_missing"
            rows.append(row)
            continue
        bar = day.iloc[reentry_pos]
        sign = 1.0 if direction.lower() == "long" else -1.0
        open_price = _safe_float(bar.get("open"))
        high_price = _safe_float(bar.get("high"))
        low_price = _safe_float(bar.get("low"))
        close_price = _safe_float(bar.get("close"))
        favorable_extreme = high_price if sign > 0 else low_price
        adverse_extreme = low_price if sign > 0 else high_price
        range_price = high_price - low_price if np.isfinite(high_price) and np.isfinite(low_price) else np.nan
        close_position = np.nan
        if np.isfinite(range_price) and range_price > 0 and np.isfinite(close_price):
            close_position = (close_price - low_price) / range_price if sign > 0 else (high_price - close_price) / range_price
        prev = day.iloc[max(0, reentry_pos - 20) : reentry_pos]
        prev_volume = pd.to_numeric(prev.get("volume", pd.Series(dtype=float)), errors="coerce")
        prev_volume_mean = float(prev_volume.replace(0.0, np.nan).mean()) if not prev_volume.empty else np.nan
        current_volume = _safe_float(bar.get("volume"))
        volume_ratio = current_volume / prev_volume_mean if np.isfinite(prev_volume_mean) and prev_volume_mean > 0 else np.nan
        first_stop_close = np.nan
        if first_stop_pos is not None and 0 <= first_stop_pos < len(day):
            first_stop_close = _safe_float(day.iloc[first_stop_pos].get("close"))
        window_start = first_stop_pos if first_stop_pos is not None else max(0, reentry_pos - 1)
        window = day.iloc[max(0, window_start) : reentry_pos + 1].copy()
        if not window.empty:
            if sign > 0:
                worst_adverse = pd.to_numeric(window["low"], errors="coerce").map(lambda value: _signed_move(value, entry, risk, direction)).min()
                best_favorable = pd.to_numeric(window["high"], errors="coerce").map(lambda value: _signed_move(value, entry, risk, direction)).max()
            else:
                worst_adverse = pd.to_numeric(window["high"], errors="coerce").map(lambda value: _signed_move(value, entry, risk, direction)).min()
                best_favorable = pd.to_numeric(window["low"], errors="coerce").map(lambda value: _signed_move(value, entry, risk, direction)).max()
        else:
            worst_adverse = np.nan
            best_favorable = np.nan
        latency = _safe_float(row.get("reentry_latency_bars"))
        first_stop_close_r = _signed_move(first_stop_close, entry, risk, direction)
        reentry_close_r = _signed_move(close_price, entry, risk, direction)
        slope = (reentry_close_r - first_stop_close_r) / latency if np.isfinite(latency) and latency > 0 and np.isfinite(first_stop_close_r) else np.nan
        row.update(
            {
                "reentry_minute_ready": 1,
                "reentry_bar_pos_stage861": int(reentry_pos),
                "first_stop_bar_pos_stage861": int(first_stop_pos) if first_stop_pos is not None else np.nan,
                "reentry_open_gap_r": _signed_move(open_price, entry, risk, direction),
                "reentry_close_gap_r": reentry_close_r,
                "reentry_body_r": sign * (close_price - open_price) / risk if np.isfinite(open_price) and np.isfinite(close_price) else np.nan,
                "reentry_range_r": range_price / risk if np.isfinite(range_price) else np.nan,
                "reentry_close_position": close_position,
                "reentry_volume_ratio_20": volume_ratio,
                "reentry_oi_delta": _safe_float(bar.get("close_oi")) - _safe_float(bar.get("open_oi")),
                "worst_adverse_after_stop_to_reentry_r": worst_adverse,
                "best_favorable_after_stop_to_reentry_r": best_favorable,
                "first_stop_to_reentry_close_slope_r_per_bar": slope,
            }
        )
        row["reentry_visible_shape"] = _reentry_shape(row)
        row["reentry_volume_bucket"] = _volume_bucket(row.get("reentry_volume_ratio_20"))
        rows.append(row)
    out = pd.DataFrame(rows)
    out["reentry_visible_shape"] = pd.Categorical(out["reentry_visible_shape"], categories=SHAPE_ORDER, ordered=True)
    return out.sort_values(["entry_date", "event_key"]).reset_index(drop=True)


def _merge_lot_features(features: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    event_cols = [
        "event_key",
        "reentry_minute_ready",
        "reentry_visible_shape",
        "reentry_volume_bucket",
        "reentry_open_gap_r",
        "reentry_close_gap_r",
        "reentry_body_r",
        "reentry_range_r",
        "reentry_close_position",
        "reentry_volume_ratio_20",
        "reentry_oi_delta",
        "worst_adverse_after_stop_to_reentry_r",
        "best_favorable_after_stop_to_reentry_r",
        "first_stop_to_reentry_close_slope_r_per_bar",
        "stage861_reentry_day_minute_bars",
    ]
    merged = features.merge(events[event_cols], on="event_key", how="left")
    merged["reentry_visible_shape"] = merged["reentry_visible_shape"].astype(object).fillna("not_reentered_or_no_event")
    return merged


def _event_shape_summary(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (shape, state), group in events.groupby(["reentry_visible_shape", "stop_retry_state"], observed=False, dropna=False):
        if group.empty:
            continue
        pnl = pd.to_numeric(group["event_realized_pnl"], errors="coerce").fillna(0.0)
        rows.append(
            {
                "reentry_visible_shape": str(shape),
                "stop_retry_state": str(state),
                "event_count": int(len(group)),
                "lot_count": int(pd.to_numeric(group["lot_count"], errors="coerce").fillna(0).sum()),
                "product_count": int(group["product"].nunique()),
                "year_count": int(group["entry_year"].nunique()),
                "event_net_pnl": float(pnl.sum()),
                "event_win_rate_pct": float((pnl > 0.0).mean() * 100.0),
                "median_reentry_close_gap_r": float(pd.to_numeric(group["reentry_close_gap_r"], errors="coerce").median()),
                "median_reentry_body_r": float(pd.to_numeric(group["reentry_body_r"], errors="coerce").median()),
                "median_close_position": float(pd.to_numeric(group["reentry_close_position"], errors="coerce").median()),
                "median_volume_ratio_20": float(pd.to_numeric(group["reentry_volume_ratio_20"], errors="coerce").median()),
                "median_reentry_latency_bars": float(pd.to_numeric(group["reentry_latency_bars"], errors="coerce").median()),
            }
        )
    return pd.DataFrame(rows).sort_values(["reentry_visible_shape", "stop_retry_state"]).reset_index(drop=True)


def _lot_shape_summary(lots: pd.DataFrame) -> pd.DataFrame:
    data = lots[lots["stop_retry_state"].isin(REENTRY_STATES)].copy()
    rows: list[dict[str, Any]] = []
    for (shape, state), group in data.groupby(["reentry_visible_shape", "stop_retry_state"], observed=False, dropna=False):
        if group.empty:
            continue
        pnl = pd.to_numeric(group["realized_pnl"], errors="coerce").fillna(0.0)
        rows.append(
            {
                "reentry_visible_shape": str(shape),
                "stop_retry_state": str(state),
                "lot_count": int(len(group)),
                "event_key_count": int(group["event_key"].nunique()),
                "product_count": int(group["product"].nunique()),
                "year_count": int(group["entry_year"].nunique()),
                "net_pnl": float(pnl.sum()),
                "positive_pnl": float(pnl.clip(lower=0.0).sum()),
                "negative_pnl": float(pnl.clip(upper=0.0).sum()),
                "win_rate_pct": float((pnl > 0.0).mean() * 100.0),
                "median_r_multiple": float(pd.to_numeric(group["r_multiple"], errors="coerce").median()),
            }
        )
    return pd.DataFrame(rows).sort_values(["reentry_visible_shape", "stop_retry_state"]).reset_index(drop=True)


def _shape_year_matrix(lots: pd.DataFrame) -> pd.DataFrame:
    data = lots[lots["stop_retry_state"].isin(REENTRY_STATES)].copy()
    matrix = data.pivot_table(
        index="reentry_visible_shape",
        columns="entry_year",
        values="realized_pnl",
        aggfunc="sum",
        fill_value=0.0,
        observed=False,
    )
    matrix = matrix.reindex(SHAPE_ORDER).fillna(0.0)
    matrix.columns = [str(int(column)) for column in matrix.columns]
    return matrix.reset_index()


def _shape_product_matrix(lots: pd.DataFrame) -> pd.DataFrame:
    data = lots[lots["stop_retry_state"].isin(REENTRY_STATES)].copy()
    matrix = data.pivot_table(
        index="product",
        columns="reentry_visible_shape",
        values="realized_pnl",
        aggfunc="sum",
        fill_value=0.0,
        observed=False,
    )
    for shape in SHAPE_ORDER:
        if shape not in matrix.columns:
            matrix[shape] = 0.0
    matrix["reentry_net_pnl"] = matrix[SHAPE_ORDER].sum(axis=1)
    matrix["reentry_lot_count"] = data.groupby("product").size()
    return matrix.sort_values("reentry_lot_count", ascending=False).reset_index()


def _contribution_curve(lots: pd.DataFrame) -> pd.DataFrame:
    start = lots["exit_date"].min()
    end = lots["exit_date"].max()
    calendar = pd.date_range(start, end, freq="D")
    out = pd.DataFrame({"date": calendar})
    reentry = lots[lots["stop_retry_state"].isin(REENTRY_STATES)].copy()
    out["cum_pnl_reentered_all"] = (
        reentry.groupby("exit_date")["realized_pnl"].sum().reindex(calendar, fill_value=0.0).cumsum().to_numpy(dtype=float)
    )
    for state in REENTRY_STATES:
        sub = reentry[reentry["stop_retry_state"].eq(state)]
        out[f"cum_pnl_{state}"] = (
            sub.groupby("exit_date")["realized_pnl"].sum().reindex(calendar, fill_value=0.0).cumsum().to_numpy(dtype=float)
        )
    for shape in SHAPE_ORDER:
        sub = reentry[reentry["reentry_visible_shape"].astype(str).eq(shape)]
        out[f"cum_pnl_shape_{shape}"] = (
            sub.groupby("exit_date")["realized_pnl"].sum().reindex(calendar, fill_value=0.0).cumsum().to_numpy(dtype=float)
        )
    return out


def _build_summary(metrics: dict[str, float], events: pd.DataFrame, lots: pd.DataFrame) -> pd.DataFrame:
    reentry_lots = lots[lots["stop_retry_state"].isin(REENTRY_STATES)].copy()
    pnl = pd.to_numeric(reentry_lots["realized_pnl"], errors="coerce").fillna(0.0)
    failed = reentry_lots[reentry_lots["stop_retry_state"].eq("flat_retry_failed")]
    open_after = reentry_lots[reentry_lots["stop_retry_state"].eq("open_after_reentry")]
    strong = reentry_lots[reentry_lots["reentry_visible_shape"].astype(str).eq("close_body_strong_reclaim")]
    return pd.DataFrame(
        [
            {
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "end_equity": metrics["end_equity"],
                "total_return_pct": metrics["total_return_pct"],
                "max_drawdown_pct": metrics["max_drawdown_pct"],
                "sharpe": metrics["sharpe"],
                "closed_lot_count": int(len(lots)),
                "reentry_event_count": int(len(events)),
                "reentry_lot_count": int(len(reentry_lots)),
                "reentry_net_pnl": float(pnl.sum()),
                "flat_retry_failed_net_pnl": float(pd.to_numeric(failed["realized_pnl"], errors="coerce").fillna(0.0).sum()),
                "open_after_reentry_net_pnl": float(pd.to_numeric(open_after["realized_pnl"], errors="coerce").fillna(0.0).sum()),
                "close_body_strong_reclaim_lot_count": int(len(strong)),
                "close_body_strong_reclaim_net_pnl": float(pd.to_numeric(strong["realized_pnl"], errors="coerce").fillna(0.0).sum()),
                "reentry_minute_ready_event_count": int(pd.to_numeric(events["reentry_minute_ready"], errors="coerce").fillna(0).sum()),
                "zero_range_reentry_event_count": int(pd.to_numeric(events["reentry_range_r"], errors="coerce").fillna(0.0).eq(0.0).sum()),
                "volume_ratio_ready_event_count": int(pd.to_numeric(events["reentry_volume_ratio_20"], errors="coerce").notna().sum()),
            }
        ]
    )


def _build_decision(
    metrics: dict[str, float],
    summary: pd.DataFrame,
    event_shape_summary: pd.DataFrame,
    lot_shape_summary: pd.DataFrame,
    events: pd.DataFrame,
) -> dict[str, Any]:
    reentry_net = float(summary["reentry_net_pnl"].iloc[0])
    open_after_net = float(summary["open_after_reentry_net_pnl"].iloc[0])
    failed_net = float(summary["flat_retry_failed_net_pnl"].iloc[0])
    by_shape = (
        events.groupby("reentry_visible_shape", observed=False)["event_realized_pnl"]
        .agg(["count", "sum"])
        .reset_index()
        .sort_values("sum", ascending=False)
    )
    best = by_shape.iloc[0].to_dict() if not by_shape.empty else {}
    decision = "stage031_reentry_visible_shape_no_candidate_mixed_future_outcome"
    reason = (
        "Reentry-moment visible shapes are useful for attribution, but the successful/failed split still depends on "
        "future path labels; no broad shape is promoted without a frozen true-engine test."
    )
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": decision,
        "candidate_ready": 0,
        "ab_triggered": 0,
        "reason": reason,
        "official_metrics": metrics,
        "reentry_event_count": int(len(events)),
        "reentry_net_pnl": reentry_net,
        "flat_retry_failed_net_pnl": failed_net,
        "open_after_reentry_net_pnl": open_after_net,
        "best_shape_by_event_pnl": best,
        "event_shape_summary": event_shape_summary.to_dict(orient="records"),
        "lot_shape_summary": lot_shape_summary.to_dict(orient="records"),
        "guardrails": {
            "no_trade_rule": True,
            "no_parameter_sweep": True,
            "no_ctp_or_order_api": True,
            "future_final_state_is_attribution_only": True,
            "uses_only_reentry_or_prior_minute_features": True,
            "reentry_bar_body_range_volume_not_informative_when_zero_range": True,
            "official_pnl_source": str(FEATURES_IN),
            "minute_source": "Stage861 full minute bars via stage010 helper",
        },
        "outputs": {
            "event_features": str(EVENT_FEATURES_OUT),
            "lot_features": str(LOT_FEATURES_OUT),
            "event_shape_summary": str(EVENT_SHAPE_SUMMARY_OUT),
            "lot_shape_summary": str(LOT_SHAPE_SUMMARY_OUT),
            "shape_year_matrix": str(SHAPE_YEAR_OUT),
            "shape_product_matrix": str(SHAPE_PRODUCT_OUT),
            "contribution_curve": str(CONTRIB_CURVE_OUT),
            "summary": str(SUMMARY_OUT),
            "atlas_manifest": str(ATLAS_MANIFEST_OUT),
            "decision": str(DECISION_OUT),
            "report": str(REPORT_OUT),
            "path_chart": str(PATH_CHART_OUT),
            "scatter": str(SCATTER_OUT),
            "shape_state_heatmap": str(SHAPE_STATE_HEATMAP_OUT),
            "product_shape_heatmap": str(PRODUCT_SHAPE_HEATMAP_OUT),
        },
    }


def _plot_path(curve: pd.DataFrame, contribution: pd.DataFrame) -> None:
    merged = curve.merge(contribution, on="date", how="left")
    fig, axes = plt.subplots(4, 1, figsize=(15, 12), sharex=True)
    axes[0].plot(merged["date"], merged["account_equity"], color="#1f77b4", linewidth=1.4)
    axes[0].set_title("Official C9/15w equity")
    axes[0].grid(True, alpha=0.25)
    axes[1].plot(merged["date"], merged["drawdown_pct"], color="#d62728", linewidth=1.1)
    axes[1].set_title("Official drawdown pct")
    axes[1].grid(True, alpha=0.25)
    axes[2].plot(merged["date"], merged["cum_pnl_reentered_all"], color="#111111", linewidth=1.5, label="all reentered")
    axes[2].plot(merged["date"], merged["cum_pnl_flat_retry_failed"], color=STATE_COLORS["flat_retry_failed"], linewidth=1.0, label="flat_retry_failed")
    axes[2].plot(merged["date"], merged["cum_pnl_open_after_reentry"], color=STATE_COLORS["open_after_reentry"], linewidth=1.0, label="open_after_reentry")
    axes[2].axhline(0.0, color="#555555", linewidth=0.8)
    axes[2].set_title("Reentered-event official closed-lot PnL")
    axes[2].legend(loc="upper left")
    axes[2].grid(True, alpha=0.25)
    for shape in SHAPE_ORDER:
        column = f"cum_pnl_shape_{shape}"
        if column in merged:
            axes[3].plot(merged["date"], merged[column], color=SHAPE_COLORS[shape], linewidth=1.1, label=shape)
    axes[3].axhline(0.0, color="#555555", linewidth=0.8)
    axes[3].set_title("Reentry visible shape contribution")
    axes[3].legend(loc="upper left", ncol=2, fontsize=8)
    axes[3].grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_scatter(events: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    for state in REENTRY_STATES:
        sub = events[events["stop_retry_state"].eq(state)]
        axes[0].scatter(
            pd.to_numeric(sub["reentry_latency_bars"], errors="coerce"),
            pd.to_numeric(sub["reentry_close_gap_r"], errors="coerce"),
            s=np.clip(np.sqrt(np.abs(pd.to_numeric(sub["event_realized_pnl"], errors="coerce").fillna(0.0))) / 4.0, 12, 180),
            alpha=0.65,
            color=STATE_COLORS[state],
            label=state,
        )
        axes[1].scatter(
            pd.to_numeric(sub["worst_adverse_after_stop_to_reentry_r"], errors="coerce"),
            pd.to_numeric(sub["first_stop_to_reentry_close_slope_r_per_bar"], errors="coerce"),
            s=np.clip(np.sqrt(np.abs(pd.to_numeric(sub["event_realized_pnl"], errors="coerce").fillna(0.0))) / 4.0, 12, 180),
            alpha=0.65,
            color=STATE_COLORS[state],
            label=state,
        )
    axes[0].axhline(0.0, color="#555555", linewidth=0.8)
    axes[0].set_title("Reentry close gap vs latency")
    axes[0].set_xlabel("latency bars after first stop")
    axes[0].set_ylabel("directional close gap from entry, R")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="best")
    axes[1].axvline(-0.5, color="#555555", linestyle="--", linewidth=0.8)
    axes[1].axhline(0.0, color="#555555", linewidth=0.8)
    axes[1].set_title("Post-stop adverse depth vs reclaim slope")
    axes[1].set_xlabel("worst adverse after stop before reentry, R")
    axes[1].set_ylabel("first-stop to reentry close slope, R/bar")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(loc="best")
    fig.tight_layout()
    fig.savefig(SCATTER_OUT, dpi=160)
    plt.close(fig)


def _plot_shape_state_heatmap(summary: pd.DataFrame) -> None:
    if summary.empty:
        return
    matrix = summary.pivot_table(
        index="reentry_visible_shape",
        columns="stop_retry_state",
        values="event_net_pnl",
        aggfunc="sum",
        fill_value=0.0,
        observed=False,
    )
    matrix = matrix.reindex(SHAPE_ORDER).fillna(0.0)
    for state in REENTRY_STATES:
        if state not in matrix.columns:
            matrix[state] = 0.0
    matrix = matrix[REENTRY_STATES]
    values = matrix.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(8, max(4, 0.55 * len(matrix))))
    vmax = max(abs(np.nanmin(values)), abs(np.nanmax(values)), 1.0)
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    ax.set_xticks(np.arange(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns, rotation=25, ha="right")
    ax.set_title("Event PnL by reentry visible shape and future state")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j] / 10000:.0f}w", ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(SHAPE_STATE_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_product_shape_heatmap(matrix: pd.DataFrame) -> None:
    if matrix.empty:
        return
    data = matrix.set_index("product")[SHAPE_ORDER].head(24)
    values = data.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(11, max(6, 0.35 * len(data))))
    vmax = max(abs(np.nanmin(values)), abs(np.nanmax(values)), 1.0)
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_yticks(np.arange(len(data.index)))
    ax.set_yticklabels(data.index)
    ax.set_xticks(np.arange(len(data.columns)))
    ax.set_xticklabels(data.columns, rotation=30, ha="right")
    ax.set_title("Product x reentry visible shape net PnL")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j] / 10000:.0f}w", ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(PRODUCT_SHAPE_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _select_atlas_events(events: pd.DataFrame) -> pd.DataFrame:
    selected: list[pd.DataFrame] = []
    specs = [
        ("flat_retry_failed", True, 6),
        ("open_after_reentry", False, 6),
        ("close_body_strong_reclaim", True, 4),
        ("wick_or_close_back_inside", False, 4),
    ]
    for key, ascending, count in specs:
        if key in REENTRY_STATES:
            sub = events[events["stop_retry_state"].eq(key)].copy()
        else:
            sub = events[events["reentry_visible_shape"].astype(str).eq(key)].copy()
        if sub.empty:
            continue
        sub = sub.sort_values("event_realized_pnl", ascending=ascending)
        sub["atlas_reason"] = f"{key}_{'worst' if ascending else 'best'}"
        selected.append(sub.head(count))
    if not selected:
        return pd.DataFrame()
    return pd.concat(selected, ignore_index=True, sort=False).drop_duplicates("event_key").head(MAX_ATLAS_EVENTS)


def _plot_atlas(events: pd.DataFrame) -> pd.DataFrame:
    selected = _select_atlas_events(events)
    if selected.empty:
        return pd.DataFrame()
    groups = _load_minute_groups(selected)
    pages = int(math.ceil(len(selected) / PER_PAGE))
    manifest: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.0, 3.3 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            vt_symbol = str(row.get("vt_symbol"))
            entry_day = s010._normalize_day(row.get("entry_date"))
            day = s010._day_for_symbol(groups, vt_symbol, entry_day)
            day = day.copy().reset_index(drop=True).head(420) if not day.empty else pd.DataFrame()
            if day.empty:
                ax.axis("off")
                ax.text(0.5, 0.5, f"missing minute bars {vt_symbol} {entry_day:%Y-%m-%d}", ha="center", va="center")
            else:
                s010.s008.s825._plot_candles(ax, day)
                entry_price = _safe_float(row.get("entry_price_event"))
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
                    ts = pd.to_datetime(row.get(marker_col), errors="coerce")
                    if pd.isna(ts):
                        continue
                    matches = np.flatnonzero(pd.to_datetime(day["bar_datetime"], errors="coerce").eq(ts).to_numpy())
                    if len(matches):
                        ax.axvline(int(matches[0]), color=color, linewidth=0.9, alpha=0.8, label=label)
                reentry_pos = _bar_position(day, row.get("reentry_time"))
                if reentry_pos is not None:
                    ax.axvspan(max(0, reentry_pos - 1), min(len(day) - 1, reentry_pos + 1), color="#dbeafe", alpha=0.22)
                ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(day.iloc[pos]["bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    dedup = dict(zip(labels, handles))
                    ax.legend(dedup.values(), dedup.keys(), loc="best", fontsize=7)
                ax.grid(True, alpha=0.18)
            title = (
                f"{row.get('atlas_reason', '')} | {vt_symbol} {row.get('direction', '')} {entry_day:%Y-%m-%d} "
                f"state={row.get('stop_retry_state', '')} shape={row.get('reentry_visible_shape', '')} "
                f"pnl={_safe_float(row.get('event_realized_pnl')):,.0f} close_gap={_safe_float(row.get('reentry_close_gap_r')):.2f} "
                f"body={_safe_float(row.get('reentry_body_r')):.2f} pos={_safe_float(row.get('reentry_close_position')):.2f}"
            )
            ax.set_title(title, fontsize=8.0, loc="left")
            manifest.append(
                {
                    "page": page,
                    "vt_symbol": vt_symbol,
                    "entry_date": entry_day.strftime("%Y-%m-%d") if not pd.isna(entry_day) else "",
                    "direction": row.get("direction", ""),
                    "stop_retry_state": row.get("stop_retry_state", ""),
                    "reentry_visible_shape": str(row.get("reentry_visible_shape", "")),
                    "atlas_reason": row.get("atlas_reason", ""),
                    "event_realized_pnl": _safe_float(row.get("event_realized_pnl")),
                    "reentry_close_gap_r": _safe_float(row.get("reentry_close_gap_r")),
                    "reentry_body_r": _safe_float(row.get("reentry_body_r")),
                    "reentry_close_position": _safe_float(row.get("reentry_close_position")),
                    "reentry_time": row.get("reentry_time", ""),
                }
            )
        fig.suptitle("Stage031 C9 reentry-moment visible structure atlas", fontsize=13)
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
    return pd.DataFrame(manifest)


def _write_report(
    metrics: dict[str, float],
    summary: pd.DataFrame,
    decision: dict[str, Any],
    event_shape_summary: pd.DataFrame,
    lot_shape_summary: pd.DataFrame,
    shape_year: pd.DataFrame,
    shape_product: pd.DataFrame,
    atlas_manifest: pd.DataFrame,
) -> None:
    report = f"""# {STAGE} C9 重入当刻可见结构只读法证

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} CST
- 阶段性质：官方 C9/15w stop/retry 重入当刻可见结构归因；不新增交易规则、不改正式配置、不连接 CTP、不调用下单。
- 是否重要突破：否
- 是否触发A/B：否
- 当前官方正式版：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`

## 外部调研与判断

- Clare/Seaton/Thomas/Smith 的趋势跟随论文提示，简单趋势规则比复杂频繁交易更稳，stop-loss 规则未必增加价值，频繁 whipsaw 会伤收益。
- Alpha Architect 对趋势跟随的总结强调，趋势收益本身伴随痛苦路径和 whipsaw；过度过滤会把风险溢价也过滤掉。
- GitHub 上 breakout/scanner 示例通常会用动量、波动或收盘确认过滤假突破，但这些只是工程形态，不构成可直接复制的期货分钟规则。
- 我的判断：如果要继续 stop/retry，只能研究重入当刻已经可见的结构，如收盘是否真正站回入场、当根方向性 body、收盘在区间中的位置、量能是否扩张；不能使用 `open_after_reentry` 这个未来状态。

## 官方基准指标

- 期末权益：`{metrics['end_equity']:,.2f}`
- 总收益：`{metrics['total_return_pct']:.4f}%`
- 最大回撤：`{metrics['max_drawdown_pct']:.4f}%`
- Sharpe：`{metrics['sharpe']:.4f}`
- 总滑点：`{metrics['total_slippage']:,.0f}`
- 总交易次数：`{metrics['total_trade_count']:,.0f}`
- closed-lot 胜率：`{metrics['closed_lot_win_rate_pct']:.4f}%`

## Summary

{_md_table(summary)}

## Event Shape Summary

{_md_table(event_shape_summary)}

## Lot Shape Summary

{_md_table(lot_shape_summary)}

## Shape-Year Matrix

{_md_table(shape_year)}

## Product-Shape Matrix

{_md_table(shape_product, max_rows=30)}

## Atlas Manifest

{_md_table(atlas_manifest, max_rows=40)}

## 视觉观察

- path chart：`{PATH_CHART_OUT}`
  - 同时查看官方权益、回撤、重入事件总体贡献和可见结构贡献。
- scatter：`{SCATTER_OUT}`
  - 查看 reentry close gap、latency、止损后最深逆行和收复斜率与未来成功/失败状态是否清晰分离。Stage861 重入当根多为零 range/零量退化分钟，body、close-position、volume 不作为结论依据。
- shape-state heatmap：`{SHAPE_STATE_HEATMAP_OUT}`
  - 检查重入当刻结构是否同时包含成功与失败，避免用未来标签伪装成规则。
- product-shape heatmap：`{PRODUCT_SHAPE_HEATMAP_OUT}`
  - 检查贡献是否由少数产品块主导。
- minute atlas：`{OUTPUT_DIR}`
  - 标记 first stop、reentry、retry failed，并用浅蓝背景标出重入当根附近。

## 决策

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## 过拟合反思

- 运行前判断：中等。重入成功/失败标签天然是未来信息，很容易误写成规则。
- 运行后判断：以决策为准。本阶段只读输出可见结构，不做参数扫描，不进入 true engine。
- 原因：任何候选都必须在重入当刻可执行，并且不能靠最终状态、年份、产品或方向筛选。

## 继续价值反思

- 运行前判断：有价值。Stage030 证明 stop/retry 总体净负但成功重入有右尾，必须知道重入当刻有没有可观察结构。
- 运行后判断：以决策为准。若可见结构仍混合成功/失败，stop/retry 小变体应停止；若有强结构，也只能先冻结一个真实引擎做反证。
"""
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features = _load_features()
    curve = _load_curve()
    metrics = _official_metrics(curve, features)
    events = _build_reentry_events(features)
    events = _add_reentry_minute_features(events)
    lot_features = _merge_lot_features(features, events)
    event_shape_summary = _event_shape_summary(events)
    lot_shape_summary = _lot_shape_summary(lot_features)
    shape_year = _shape_year_matrix(lot_features)
    shape_product = _shape_product_matrix(lot_features)
    contribution = _contribution_curve(lot_features)
    summary = _build_summary(metrics, events, lot_features)
    decision = _build_decision(metrics, summary, event_shape_summary, lot_shape_summary, events)
    atlas_manifest = _plot_atlas(events)

    events.to_csv(EVENT_FEATURES_OUT, index=False, encoding="utf-8-sig")
    lot_features.to_csv(LOT_FEATURES_OUT, index=False, encoding="utf-8-sig")
    event_shape_summary.to_csv(EVENT_SHAPE_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    lot_shape_summary.to_csv(LOT_SHAPE_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    shape_year.to_csv(SHAPE_YEAR_OUT, index=False, encoding="utf-8-sig")
    shape_product.to_csv(SHAPE_PRODUCT_OUT, index=False, encoding="utf-8-sig")
    contribution.to_csv(CONTRIB_CURVE_OUT, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    _plot_path(curve, contribution)
    _plot_scatter(events)
    _plot_shape_state_heatmap(event_shape_summary)
    _plot_product_shape_heatmap(shape_product)
    _write_report(metrics, summary, decision, event_shape_summary, lot_shape_summary, shape_year, shape_product, atlas_manifest)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
