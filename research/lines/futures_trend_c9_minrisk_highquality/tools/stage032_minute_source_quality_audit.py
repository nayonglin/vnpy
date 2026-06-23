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
STAGE = "Stage032"
MODEL_TAG = "stage032_minute_source_quality_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage032_c9_minrisk_minute_source_quality_audit"
ACCOUNT_CAPITAL = 150_000.0
TRADING_DAYS_PER_YEAR = 252
ATLAS_PER_PAGE = 4
LOCAL_WINDOW_BARS = 20

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage010_authoritative_minute_coverage_audit as s010
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE005_DIR = LINE_DIR / "outputs" / "stage005_signal_quality_visual_forensics"
STAGE030_DIR = LINE_DIR / "outputs" / "stage030_stop_retry_event_quality_forensics"
STAGE031_DIR = LINE_DIR / "outputs" / "stage031_reentry_moment_visible_structure_forensics"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage032_minute_source_quality_audit"

FEATURES_IN = STAGE030_DIR / (
    "qmt_roll_stage030_c9_minrisk_stop_retry_event_quality_forensics_features_"
    "stage030_stop_retry_event_quality_forensics_v1.csv"
)
STAGE031_EVENT_FEATURES_IN = STAGE031_DIR / (
    "qmt_roll_stage031_c9_minrisk_reentry_moment_visible_structure_event_features_"
    "stage031_reentry_moment_visible_structure_forensics_v1.csv"
)
OFFICIAL_CURVE_IN = STAGE005_DIR / (
    "qmt_roll_stage005_c9_minrisk_signal_quality_visual_forensics_official_curve_"
    "stage005_signal_quality_visual_forensics_v1.csv"
)

RAW_ROOTS = [
    {
        "source_name": "stage859_gap_backfill",
        "root": EXAMPLE_DIR / "downloaded_futures" / "tqsdk_stage859_stage856_remaining_gap_backfill",
        "kind": "date_or_contract",
        "description": "Stage859 targeted C9 gap backfill files",
    },
    {
        "source_name": "stage448_session_rebuild_batch",
        "root": EXAMPLE_DIR / "downloaded_futures" / "tqsdk_stage448_minute_session_rebuild_batch",
        "kind": "contract",
        "description": "Stage448 minute session rebuild batch",
    },
    {
        "source_name": "stage504_next_real_open_fallback",
        "root": EXAMPLE_DIR / "downloaded_futures" / "tqsdk_stage504_next_real_open_fallback_backfill",
        "kind": "contract",
        "description": "Stage504 next real-open fallback backfill",
    },
    {
        "source_name": "stage446_proxy_extract",
        "root": EXAMPLE_DIR / "downloaded_futures" / "tqsdk_stage446_backtest_minute_proxy_extract",
        "kind": "contract",
        "description": "Stage446 backtest minute proxy extract",
    },
]

SOURCE_ORDER = ["stage861_full_minute"] + [item["source_name"] for item in RAW_ROOTS]
MOMENTS = [
    ("first_stop", "first_stop_time"),
    ("reentry", "reentry_time"),
    ("retry_failed", "retry_failed_time"),
]
REENTRY_STATES = ["flat_retry_failed", "open_after_reentry"]

EVENT_SOURCE_QUALITY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_source_quality_{MODEL_TAG}.csv"
EVENT_BEST_SOURCE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_best_source_{MODEL_TAG}.csv"
SOURCE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_moment_summary_{MODEL_TAG}.csv"
EVENT_QUALITY_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_quality_summary_{MODEL_TAG}.csv"
CONTRIB_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quality_contribution_curve_{MODEL_TAG}.csv"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_quality_contribution_chart_{MODEL_TAG}.png"
SOURCE_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_quality_heatmap_{MODEL_TAG}.png"
MOMENT_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_moment_quality_heatmap_{MODEL_TAG}.png"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_comparison_atlas_page{{page:03d}}_{MODEL_TAG}.png"

_PATH_CACHE: dict[Path, pd.DataFrame] = {}
_SOURCE_CACHE: dict[tuple[str, str, str, str], pd.DataFrame] = {}


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


def _source_order_value(source_name: str) -> int:
    if source_name in SOURCE_ORDER:
        return SOURCE_ORDER.index(source_name)
    return 999


def _normalize_day(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts.normalize()


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


def _load_stage031_events() -> pd.DataFrame:
    if not STAGE031_EVENT_FEATURES_IN.exists():
        return pd.DataFrame()
    data = _read_csv(STAGE031_EVENT_FEATURES_IN)
    data["event_key"] = data["event_key"].astype(str)
    for column in ["reentry_minute_ready", "reentry_range_r", "reentry_volume_ratio_20"]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data


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


def _build_events(features: pd.DataFrame) -> pd.DataFrame:
    data = features[~features["stop_retry_state"].eq("no_event")].copy()
    rows: list[dict[str, Any]] = []
    for event_key, group in data.groupby("event_key", sort=False):
        row = group.iloc[0]
        pnl = pd.to_numeric(group["realized_pnl"], errors="coerce").fillna(0.0)
        rows.append(
            {
                "event_key": event_key,
                "vt_symbol": str(row.get("vt_symbol")),
                "product": str(row.get("product")),
                "direction": str(row.get("direction")),
                "entry_date": _normalize_day(row.get("entry_date")),
                "entry_year": int(row.get("entry_year")) if pd.notna(row.get("entry_year")) else np.nan,
                "stop_retry_state": str(row.get("stop_retry_state")),
                "entry_price_event": _safe_float(row.get("entry_price_event"), _safe_float(row.get("entry_price"))),
                "risk_price_event": _safe_float(row.get("risk_price_event"), _safe_float(row.get("risk_price"))),
                "stop_price": _safe_float(row.get("stop_price")),
                "progress_price": _safe_float(row.get("progress_price")),
                "first_stop_time": pd.to_datetime(row.get("first_stop_time"), errors="coerce"),
                "first_stop_bar_index": _safe_float(row.get("first_stop_bar_index")),
                "reentry_time": pd.to_datetime(row.get("reentry_time"), errors="coerce"),
                "reentry_bar_index": _safe_float(row.get("reentry_bar_index")),
                "retry_failed_time": pd.to_datetime(row.get("retry_failed_time"), errors="coerce"),
                "retry_failed_bar_index": _safe_float(row.get("retry_failed_bar_index")),
                "lot_count": int(len(group)),
                "event_realized_pnl": float(pnl.sum()),
                "positive_pnl": float(pnl.clip(lower=0.0).sum()),
                "negative_pnl": float(pnl.clip(upper=0.0).sum()),
            }
        )
    return pd.DataFrame(rows).sort_values(["entry_date", "event_key"]).reset_index(drop=True)


def _symbol_exchange(vt_symbol: str) -> tuple[str, str]:
    if "." not in vt_symbol:
        return vt_symbol, ""
    symbol, exchange = vt_symbol.rsplit(".", 1)
    return symbol, exchange


def _prepare_minute_frame(frame: pd.DataFrame, source_name: str, source_file: str = "") -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    data = frame.copy()
    if "bar_datetime" not in data.columns and "datetime" in data.columns:
        values = pd.to_numeric(data["datetime"], errors="coerce")
        if values.notna().any() and values.dropna().abs().median() > 10**14:
            data["bar_datetime"] = pd.to_datetime(values, unit="ns", errors="coerce")
        else:
            data["bar_datetime"] = pd.to_datetime(data["datetime"], errors="coerce")
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        if column not in data.columns:
            data[column] = np.nan
        data[column] = pd.to_numeric(data[column], errors="coerce")
    if "vt_symbol" not in data.columns:
        data["vt_symbol"] = ""
    data["vt_symbol"] = data["vt_symbol"].astype(str)
    data = data.dropna(subset=["bar_datetime", "open", "high", "low", "close"]).copy()
    data["bar_date"] = pd.to_datetime(data.get("bar_date", data["bar_datetime"]), errors="coerce")
    data["bar_date"] = data["bar_date"].dt.normalize()
    data["source_name"] = source_name
    if "minute_source" not in data.columns:
        data["minute_source"] = source_name
    data["source_file"] = data.get("source_file", source_file)
    data["source_file"] = data["source_file"].astype(str).replace("", source_file)
    columns = [
        "vt_symbol",
        "bar_datetime",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "open_oi",
        "close_oi",
        "bar_date",
        "source_name",
        "minute_source",
        "source_file",
    ]
    return data[columns].sort_values(["vt_symbol", "bar_datetime"]).reset_index(drop=True)


def _read_minute_path(path: Path, source_name: str) -> pd.DataFrame:
    path = Path(path)
    if path in _PATH_CACHE:
        return _PATH_CACHE[path].copy()
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, encoding="utf-8-sig")
    prepared = _prepare_minute_frame(frame, source_name=source_name, source_file=str(path))
    _PATH_CACHE[path] = prepared
    return prepared.copy()


def _candidate_paths(root: Path, vt_symbol: str, entry_day: pd.Timestamp, event_time: Any) -> list[Path]:
    symbol, exchange = _symbol_exchange(vt_symbol)
    if not exchange:
        return []
    folder = root / exchange
    dates: list[pd.Timestamp] = []
    for value in [entry_day, event_time]:
        day = _normalize_day(value)
        if pd.notna(day) and not any(day == existing for existing in dates):
            dates.append(day)
    paths: list[Path] = []
    contract_path = folder / f"{symbol}_minute_backtest.csv"
    if contract_path.exists():
        paths.append(contract_path)
    for day in dates:
        date_path = folder / f"{symbol}_{day.strftime('%Y%m%d')}_minute_backtest.csv"
        if date_path.exists() and date_path not in paths:
            paths.append(date_path)
    if not paths and folder.exists():
        for item in sorted(folder.glob(f"{symbol}*_minute_backtest.csv"))[:20]:
            if item not in paths:
                paths.append(item)
    return paths


def _load_local_source_bars(source_spec: dict[str, Any], vt_symbol: str, entry_day: pd.Timestamp, event_time: Any) -> pd.DataFrame:
    source_name = str(source_spec["source_name"])
    event_day = _normalize_day(event_time)
    cache_key = (
        source_name,
        vt_symbol,
        "" if pd.isna(entry_day) else entry_day.strftime("%Y-%m-%d"),
        "" if pd.isna(event_day) else event_day.strftime("%Y-%m-%d"),
    )
    if cache_key in _SOURCE_CACHE:
        return _SOURCE_CACHE[cache_key].copy()
    paths = _candidate_paths(Path(source_spec["root"]), vt_symbol, entry_day, event_time)
    frames = [_read_minute_path(path, source_name) for path in paths]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        result = pd.DataFrame()
    else:
        result = pd.concat(frames, ignore_index=True, sort=False)
        result = result[result["vt_symbol"].astype(str).eq(vt_symbol)].copy()
        result = result.drop_duplicates(["vt_symbol", "bar_datetime"], keep="last")
        result = result.sort_values(["vt_symbol", "bar_datetime"]).reset_index(drop=True)
    _SOURCE_CACHE[cache_key] = result
    return result.copy()


def _load_stage861_groups(events: pd.DataFrame) -> dict[str, pd.DataFrame]:
    selected_symbols = set(events["vt_symbol"].astype(str).dropna().unique())
    minute_bars = s010.s008.s928._load_stage861_full_minute_bars(selected_symbols)
    minute_bars = _prepare_minute_frame(minute_bars, "stage861_full_minute", "stage861_full_minute_cache")
    return {str(vt_symbol): group.copy() for vt_symbol, group in minute_bars.groupby("vt_symbol", sort=False)}


def _nearest_gap_minutes(bars: pd.DataFrame, event_time: pd.Timestamp) -> tuple[float, float, str, str]:
    if bars.empty or pd.isna(event_time):
        return np.nan, np.nan, "", ""
    times = pd.to_datetime(bars["bar_datetime"], errors="coerce").dropna().sort_values()
    before = times[times.lt(event_time)]
    after = times[times.gt(event_time)]
    before_min = float((event_time - before.iloc[-1]).total_seconds() / 60.0) if not before.empty else np.nan
    after_min = float((after.iloc[0] - event_time).total_seconds() / 60.0) if not after.empty else np.nan
    before_text = before.iloc[-1].strftime("%Y-%m-%d %H:%M:%S") if not before.empty else ""
    after_text = after.iloc[0].strftime("%Y-%m-%d %H:%M:%S") if not after.empty else ""
    return before_min, after_min, before_text, after_text


def _window_path_ready(day: pd.DataFrame, exact_pos: int | None) -> tuple[int, int, float, float]:
    if day.empty:
        return 0, 0, np.nan, np.nan
    if exact_pos is None:
        start, end = 0, min(len(day), LOCAL_WINDOW_BARS * 2 + 1)
    else:
        start = max(0, int(exact_pos) - LOCAL_WINDOW_BARS)
        end = min(len(day), int(exact_pos) + LOCAL_WINDOW_BARS + 1)
    window = day.iloc[start:end].copy()
    if window.empty:
        return 0, 0, np.nan, np.nan
    close_unique = int(pd.to_numeric(window["close"], errors="coerce").dropna().nunique())
    high = pd.to_numeric(window["high"], errors="coerce")
    low = pd.to_numeric(window["low"], errors="coerce")
    close = pd.to_numeric(window["close"], errors="coerce")
    range_total = float(high.max() - low.min()) if high.notna().any() and low.notna().any() else np.nan
    close_span = float(close.max() - close.min()) if close.notna().any() else np.nan
    ready = int((np.isfinite(range_total) and range_total > 0) or close_unique > 1)
    return ready, close_unique, range_total, close_span


def _quality_label(exact_found: int, range_ready: int, volume_ready: int, window_ready: int, missing_reason: str) -> tuple[str, int]:
    if exact_found != 1:
        rank = 0
        if missing_reason == "missing_event_time":
            return "missing_event_time", rank
        if missing_reason == "missing_source_file":
            return "missing_source_file", rank
        if missing_reason == "missing_day":
            return "missing_event_day", rank
        return "missing_exact_bar", rank
    if range_ready and volume_ready:
        return "exact_range_volume_ready", 5
    if range_ready:
        return "exact_range_volume_missing", 4
    if volume_ready:
        return "exact_zero_range_volume_ready", 3
    if window_ready:
        return "exact_zero_range_no_volume_path_ready", 2
    return "exact_zero_range_no_volume_no_path", 1


def _inspect_source_moment(
    event: pd.Series,
    moment: str,
    time_col: str,
    source_name: str,
    bars: pd.DataFrame,
) -> dict[str, Any]:
    event_time = pd.to_datetime(event.get(time_col), errors="coerce")
    entry_day = _normalize_day(event.get("entry_date"))
    base: dict[str, Any] = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "event_key": event.get("event_key", ""),
        "vt_symbol": event.get("vt_symbol", ""),
        "product": event.get("product", ""),
        "direction": event.get("direction", ""),
        "entry_date": entry_day,
        "entry_year": event.get("entry_year", np.nan),
        "stop_retry_state": event.get("stop_retry_state", ""),
        "event_realized_pnl": _safe_float(event.get("event_realized_pnl"), 0.0),
        "lot_count": int(event.get("lot_count", 0)),
        "moment": moment,
        "event_time": event_time,
        "source_name": source_name,
        "source_order": _source_order_value(source_name),
        "source_file": "",
        "source_file_ready": 0,
        "same_day_bar_count": 0,
        "exact_bar_found": 0,
        "bar_pos": np.nan,
        "nearest_before_minutes": np.nan,
        "nearest_after_minutes": np.nan,
        "nearest_before_time": "",
        "nearest_after_time": "",
        "open": np.nan,
        "high": np.nan,
        "low": np.nan,
        "close": np.nan,
        "volume": np.nan,
        "open_oi": np.nan,
        "close_oi": np.nan,
        "range_abs": np.nan,
        "body_abs": np.nan,
        "range_ready": 0,
        "body_ready": 0,
        "volume_ready": 0,
        "oi_delta": np.nan,
        "oi_delta_nonzero": 0,
        "window_path_ready": 0,
        "window_close_unique": 0,
        "window_range_abs": np.nan,
        "window_close_span_abs": np.nan,
        "quality_label": "missing_event_time",
        "quality_rank": 0,
    }
    if pd.isna(event_time):
        base["quality_label"], base["quality_rank"] = _quality_label(0, 0, 0, 0, "missing_event_time")
        return base
    if bars.empty:
        base["quality_label"], base["quality_rank"] = _quality_label(0, 0, 0, 0, "missing_source_file")
        return base
    data = bars.copy().sort_values("bar_datetime").reset_index(drop=True)
    base["source_file_ready"] = 1
    same_day = data[data["bar_date"].eq(entry_day)].copy().sort_values("bar_datetime").reset_index(drop=True)
    base["same_day_bar_count"] = int(len(same_day))
    if same_day.empty:
        before_min, after_min, before_time, after_time = _nearest_gap_minutes(data, event_time)
        base.update(
            {
                "nearest_before_minutes": before_min,
                "nearest_after_minutes": after_min,
                "nearest_before_time": before_time,
                "nearest_after_time": after_time,
            }
        )
        base["quality_label"], base["quality_rank"] = _quality_label(0, 0, 0, 0, "missing_day")
        return base
    times = pd.to_datetime(same_day["bar_datetime"], errors="coerce")
    matches = np.flatnonzero(times.eq(event_time).to_numpy())
    if len(matches) == 0:
        before_min, after_min, before_time, after_time = _nearest_gap_minutes(same_day, event_time)
        ready, close_unique, range_total, close_span = _window_path_ready(same_day, None)
        base.update(
            {
                "nearest_before_minutes": before_min,
                "nearest_after_minutes": after_min,
                "nearest_before_time": before_time,
                "nearest_after_time": after_time,
                "window_path_ready": ready,
                "window_close_unique": close_unique,
                "window_range_abs": range_total,
                "window_close_span_abs": close_span,
            }
        )
        base["quality_label"], base["quality_rank"] = _quality_label(0, 0, 0, ready, "missing_exact_bar")
        return base
    pos = int(matches[0])
    bar = same_day.iloc[pos]
    source_file = str(bar.get("source_file", ""))
    open_price = _safe_float(bar.get("open"))
    high_price = _safe_float(bar.get("high"))
    low_price = _safe_float(bar.get("low"))
    close_price = _safe_float(bar.get("close"))
    volume = _safe_float(bar.get("volume"))
    open_oi = _safe_float(bar.get("open_oi"))
    close_oi = _safe_float(bar.get("close_oi"))
    range_abs = high_price - low_price if np.isfinite(high_price) and np.isfinite(low_price) else np.nan
    body_abs = abs(close_price - open_price) if np.isfinite(open_price) and np.isfinite(close_price) else np.nan
    oi_delta = close_oi - open_oi if np.isfinite(open_oi) and np.isfinite(close_oi) else np.nan
    range_ready = int(np.isfinite(range_abs) and range_abs > 0)
    body_ready = int(np.isfinite(body_abs) and body_abs > 0)
    volume_ready = int(np.isfinite(volume) and volume > 0)
    oi_delta_nonzero = int(np.isfinite(oi_delta) and abs(oi_delta) > 0)
    window_ready, close_unique, range_total, close_span = _window_path_ready(same_day, pos)
    label, rank = _quality_label(1, range_ready, volume_ready, window_ready, "")
    base.update(
        {
            "source_file": source_file,
            "exact_bar_found": 1,
            "bar_pos": pos,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volume,
            "open_oi": open_oi,
            "close_oi": close_oi,
            "range_abs": range_abs,
            "body_abs": body_abs,
            "range_ready": range_ready,
            "body_ready": body_ready,
            "volume_ready": volume_ready,
            "oi_delta": oi_delta,
            "oi_delta_nonzero": oi_delta_nonzero,
            "window_path_ready": window_ready,
            "window_close_unique": close_unique,
            "window_range_abs": range_total,
            "window_close_span_abs": close_span,
            "quality_label": label,
            "quality_rank": rank,
        }
    )
    return base


def _build_quality_rows(events: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    stage861_groups = _load_stage861_groups(events)
    rows: list[dict[str, Any]] = []
    for _, event in events.iterrows():
        vt_symbol = str(event.get("vt_symbol"))
        entry_day = _normalize_day(event.get("entry_date"))
        for moment, time_col in MOMENTS:
            event_time = pd.to_datetime(event.get(time_col), errors="coerce")
            source_bars = stage861_groups.get(vt_symbol, pd.DataFrame())
            rows.append(_inspect_source_moment(event, moment, time_col, "stage861_full_minute", source_bars))
            for source in RAW_ROOTS:
                local_bars = _load_local_source_bars(source, vt_symbol, entry_day, event_time)
                rows.append(_inspect_source_moment(event, moment, time_col, str(source["source_name"]), local_bars))
    return pd.DataFrame(rows), stage861_groups


def _source_summary(quality: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_cols = ["source_name", "moment"]
    for (source, moment), group in quality.groupby(group_cols, sort=False):
        required = int(pd.to_datetime(group["event_time"], errors="coerce").notna().sum())
        exact = int(pd.to_numeric(group["exact_bar_found"], errors="coerce").fillna(0).sum())
        range_ready = int(pd.to_numeric(group["range_ready"], errors="coerce").fillna(0).sum())
        body_ready = int(pd.to_numeric(group["body_ready"], errors="coerce").fillna(0).sum())
        volume_ready = int(pd.to_numeric(group["volume_ready"], errors="coerce").fillna(0).sum())
        oi_delta = int(pd.to_numeric(group["oi_delta_nonzero"], errors="coerce").fillna(0).sum())
        window_ready = int(pd.to_numeric(group["window_path_ready"], errors="coerce").fillna(0).sum())
        source_ready = int(pd.to_numeric(group["source_file_ready"], errors="coerce").fillna(0).sum())
        rows.append(
            {
                "source_name": source,
                "moment": moment,
                "required_moment_count": required,
                "source_file_ready_count": source_ready,
                "same_day_ready_count": int((pd.to_numeric(group["same_day_bar_count"], errors="coerce").fillna(0) > 0).sum()),
                "exact_bar_count": exact,
                "range_ready_count": range_ready,
                "body_ready_count": body_ready,
                "volume_ready_count": volume_ready,
                "oi_delta_nonzero_count": oi_delta,
                "window_path_ready_count": window_ready,
                "exact_bar_rate": exact / required if required else 0.0,
                "range_ready_rate": range_ready / required if required else 0.0,
                "volume_ready_rate": volume_ready / required if required else 0.0,
                "window_path_ready_rate": window_ready / required if required else 0.0,
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["source_order"] = out["source_name"].map(_source_order_value)
    out["moment_order"] = out["moment"].map({name: index for index, (name, _) in enumerate(MOMENTS)})
    return out.sort_values(["source_order", "moment_order"]).drop(columns=["source_order", "moment_order"]).reset_index(drop=True)


def _best_source_table(quality: pd.DataFrame) -> pd.DataFrame:
    data = quality.copy()
    data["local_source"] = data["source_name"].ne("stage861_full_minute")
    data = data.sort_values(
        ["event_key", "moment", "quality_rank", "exact_bar_found", "source_order"],
        ascending=[True, True, False, False, True],
    )
    best = data.groupby(["event_key", "moment"], as_index=False, sort=False).head(1).copy()
    stage861 = quality[quality["source_name"].eq("stage861_full_minute")][
        ["event_key", "moment", "quality_label", "quality_rank", "exact_bar_found", "range_ready", "volume_ready"]
    ].rename(
        columns={
            "quality_label": "stage861_quality_label",
            "quality_rank": "stage861_quality_rank",
            "exact_bar_found": "stage861_exact_bar_found",
            "range_ready": "stage861_range_ready",
            "volume_ready": "stage861_volume_ready",
        }
    )
    local = quality[quality["source_name"].ne("stage861_full_minute")].copy()
    local = local.sort_values(
        ["event_key", "moment", "quality_rank", "exact_bar_found", "source_order"],
        ascending=[True, True, False, False, True],
    )
    best_local = local.groupby(["event_key", "moment"], as_index=False, sort=False).head(1)[
        ["event_key", "moment", "source_name", "quality_label", "quality_rank", "exact_bar_found", "range_ready", "volume_ready"]
    ].rename(
        columns={
            "source_name": "best_local_source_name",
            "quality_label": "best_local_quality_label",
            "quality_rank": "best_local_quality_rank",
            "exact_bar_found": "best_local_exact_bar_found",
            "range_ready": "best_local_range_ready",
            "volume_ready": "best_local_volume_ready",
        }
    )
    keep = [
        "event_key",
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "entry_year",
        "stop_retry_state",
        "event_realized_pnl",
        "lot_count",
        "moment",
        "event_time",
        "source_name",
        "quality_label",
        "quality_rank",
        "exact_bar_found",
        "range_ready",
        "volume_ready",
        "window_path_ready",
        "source_file",
    ]
    out = best[keep].rename(
        columns={
            "source_name": "best_source_name",
            "quality_label": "best_quality_label",
            "quality_rank": "best_quality_rank",
            "exact_bar_found": "best_exact_bar_found",
            "range_ready": "best_range_ready",
            "volume_ready": "best_volume_ready",
            "window_path_ready": "best_window_path_ready",
            "source_file": "best_source_file",
        }
    )
    out = out.merge(stage861, on=["event_key", "moment"], how="left")
    out = out.merge(best_local, on=["event_key", "moment"], how="left")
    out["local_better_than_stage861"] = (
        pd.to_numeric(out["best_local_quality_rank"], errors="coerce").fillna(-1)
        > pd.to_numeric(out["stage861_quality_rank"], errors="coerce").fillna(-1)
    ).astype(int)
    return out.sort_values(["entry_date", "event_key", "moment"]).reset_index(drop=True)


def _event_quality_summary(events: pd.DataFrame, best: pd.DataFrame) -> pd.DataFrame:
    pivot = best.pivot_table(
        index="event_key",
        columns="moment",
        values=[
            "best_source_name",
            "best_quality_label",
            "best_quality_rank",
            "best_range_ready",
            "best_volume_ready",
            "best_local_source_name",
            "best_local_quality_label",
            "best_local_quality_rank",
            "best_local_range_ready",
            "best_local_volume_ready",
            "local_better_than_stage861",
        ],
        aggfunc="first",
    )
    pivot.columns = [f"{metric}_{moment}" for metric, moment in pivot.columns]
    pivot = pivot.reset_index()
    out = events.merge(pivot, on="event_key", how="left")
    reentry_rank = pd.to_numeric(out.get("best_quality_rank_reentry", pd.Series(index=out.index, dtype=float)), errors="coerce")
    reentry_range = pd.to_numeric(out.get("best_range_ready_reentry", pd.Series(index=out.index, dtype=float)), errors="coerce").fillna(0)
    reentry_volume = pd.to_numeric(out.get("best_volume_ready_reentry", pd.Series(index=out.index, dtype=float)), errors="coerce").fillna(0)
    first_stop_range = pd.to_numeric(out.get("best_range_ready_first_stop", pd.Series(index=out.index, dtype=float)), errors="coerce").fillna(0)
    first_stop_volume = pd.to_numeric(out.get("best_volume_ready_first_stop", pd.Series(index=out.index, dtype=float)), errors="coerce").fillna(0)
    out["reentry_has_any_exact_range_or_volume"] = ((reentry_range > 0) | (reentry_volume > 0)).astype(int)
    out["first_stop_has_any_exact_range_or_volume"] = ((first_stop_range > 0) | (first_stop_volume > 0)).astype(int)
    out["reentry_quality_bucket"] = np.select(
        [
            ~out["stop_retry_state"].isin(REENTRY_STATES),
            reentry_rank >= 5,
            reentry_range > 0,
            reentry_volume > 0,
            reentry_rank >= 2,
            reentry_rank == 1,
        ],
        [
            "no_reentry_state",
            "reentry_exact_range_volume_ready",
            "reentry_exact_range_only",
            "reentry_exact_volume_only",
            "reentry_exact_zero_range_no_volume_path_ready",
            "reentry_exact_zero_range_no_volume_no_path",
        ],
        default="reentry_missing_or_no_exact_bar",
    )
    out["first_stop_quality_bucket"] = np.select(
        [
            first_stop_range > 0,
            first_stop_volume > 0,
            pd.to_numeric(out.get("best_quality_rank_first_stop", pd.Series(index=out.index, dtype=float)), errors="coerce").fillna(0) >= 2,
        ],
        [
            "first_stop_exact_range_ready",
            "first_stop_exact_volume_ready",
            "first_stop_exact_zero_range_no_volume_path_ready",
        ],
        default="first_stop_missing_or_degenerate",
    )
    return out.sort_values(["entry_date", "event_key"]).reset_index(drop=True)


def _contribution_curve(curve: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    dates = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].copy()
    out = dates.sort_values("date").reset_index(drop=True)
    event_data = events.copy()
    event_data["entry_date"] = pd.to_datetime(event_data["entry_date"], errors="coerce").dt.normalize()
    event_data["event_realized_pnl"] = pd.to_numeric(event_data["event_realized_pnl"], errors="coerce").fillna(0.0)
    bucket_cols = ["stop_retry_state", "reentry_quality_bucket", "first_stop_quality_bucket"]
    for column in bucket_cols:
        for value in sorted(event_data[column].dropna().astype(str).unique()):
            key = f"cum_pnl_{column}_{value}".replace(" ", "_")
            daily = event_data[event_data[column].astype(str).eq(value)].groupby("entry_date")["event_realized_pnl"].sum()
            out[key] = out["date"].map(daily).fillna(0.0).cumsum()
    daily_all = event_data.groupby("entry_date")["event_realized_pnl"].sum()
    out["cum_pnl_stop_retry_events_all"] = out["date"].map(daily_all).fillna(0.0).cumsum()
    return out


def _plot_path_chart(contrib: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True, constrained_layout=True)
    axes[0].plot(contrib["date"], contrib["account_equity"], color="#111827", linewidth=1.2, label="official equity")
    axes[0].set_title("Official C9/15w equity path")
    axes[0].set_ylabel("equity")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="best")

    axes[1].plot(contrib["date"], contrib["drawdown_pct"], color="#dc2626", linewidth=1.0, label="official drawdown %")
    axes[1].set_title("Official drawdown and broker10 path")
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(True, alpha=0.25)
    ax2 = axes[1].twinx()
    ax2.plot(
        contrib["date"],
        contrib["broker10_margin_to_equity_pct"],
        color="#2563eb",
        linewidth=0.8,
        alpha=0.75,
        label="broker10 margin/equity %",
    )
    ax2.set_ylabel("broker10 %")

    axes[2].plot(
        contrib["date"],
        contrib["cum_pnl_stop_retry_events_all"],
        color="#111827",
        linewidth=1.2,
        label="all stop/retry events",
    )
    for column, color in [
        ("cum_pnl_reentry_quality_bucket_reentry_exact_zero_range_no_volume_path_ready", "#f97316"),
        ("cum_pnl_reentry_quality_bucket_reentry_exact_range_volume_ready", "#16a34a"),
        ("cum_pnl_reentry_quality_bucket_reentry_missing_or_no_exact_bar", "#6b7280"),
        ("cum_pnl_reentry_quality_bucket_no_reentry_state", "#9333ea"),
    ]:
        if column in contrib.columns:
            axes[2].plot(contrib["date"], contrib[column], linewidth=1.0, label=column.replace("cum_pnl_reentry_quality_bucket_", ""))
    axes[2].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[2].set_title("Cumulative event PnL by reentry data-quality bucket")
    axes[2].set_ylabel("cum pnl")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend(loc="best", fontsize=8)
    fig.suptitle("Stage032 minute-source quality contribution path", fontsize=14)
    fig.savefig(PATH_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_source_heatmap(summary: pd.DataFrame) -> None:
    if summary.empty:
        return
    metrics = ["exact_bar_rate", "range_ready_rate", "volume_ready_rate", "window_path_ready_rate"]
    rows: list[dict[str, Any]] = []
    for source, group in summary.groupby("source_name", sort=False):
        item: dict[str, Any] = {"source_name": source}
        for metric in metrics:
            item[metric] = float(pd.to_numeric(group[metric], errors="coerce").mean())
        rows.append(item)
    data = pd.DataFrame(rows)
    data["source_order"] = data["source_name"].map(_source_order_value)
    data = data.sort_values("source_order")
    matrix = data[metrics].to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(11, max(4, 0.55 * len(data) + 2)), constrained_layout=True)
    im = ax.imshow(matrix, aspect="auto", cmap="YlGnBu", vmin=0.0, vmax=1.0)
    ax.set_yticks(np.arange(len(data)))
    ax.set_yticklabels(data["source_name"], fontsize=8)
    ax.set_xticks(np.arange(len(metrics)))
    ax.set_xticklabels([metric.replace("_rate", "") for metric in metrics], rotation=30, ha="right", fontsize=8)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, f"{matrix[i, j] * 100:.0f}%", ha="center", va="center", fontsize=8)
    ax.set_title("Source-level minute quality rates")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    fig.savefig(SOURCE_HEATMAP_OUT, dpi=150)
    plt.close(fig)


def _plot_moment_heatmap(summary: pd.DataFrame) -> None:
    if summary.empty:
        return
    metrics = ["exact_bar_rate", "range_ready_rate", "volume_ready_rate", "window_path_ready_rate"]
    fig, axes = plt.subplots(1, len(metrics), figsize=(18, 5), constrained_layout=True)
    axes_list = list(np.atleast_1d(axes))
    for ax, metric in zip(axes_list, metrics, strict=False):
        pivot = summary.pivot(index="source_name", columns="moment", values=metric).reindex(index=SOURCE_ORDER)
        pivot = pivot[[moment for moment, _ in MOMENTS]]
        matrix = pivot.fillna(0.0).to_numpy(dtype=float)
        im = ax.imshow(matrix, aspect="auto", cmap="YlOrRd", vmin=0.0, vmax=1.0)
        ax.set_title(metric.replace("_rate", ""))
        ax.set_yticks(np.arange(len(pivot.index)))
        ax.set_yticklabels(pivot.index, fontsize=7)
        ax.set_xticks(np.arange(len(pivot.columns)))
        ax.set_xticklabels(pivot.columns, rotation=30, ha="right", fontsize=8)
        for i in range(matrix.shape[0]):
            for j in range(matrix.shape[1]):
                ax.text(j, i, f"{matrix[i, j] * 100:.0f}%", ha="center", va="center", fontsize=7)
    fig.colorbar(im, ax=axes_list, fraction=0.015, pad=0.02)
    fig.suptitle("Minute quality by source and stop/retry moment", fontsize=14)
    fig.savefig(MOMENT_HEATMAP_OUT, dpi=150)
    plt.close(fig)


def _load_bars_for_source(
    source_name: str,
    stage861_groups: dict[str, pd.DataFrame],
    vt_symbol: str,
    entry_day: pd.Timestamp,
    event_time: Any,
) -> pd.DataFrame:
    if source_name == "stage861_full_minute":
        return stage861_groups.get(vt_symbol, pd.DataFrame()).copy()
    specs = {str(item["source_name"]): item for item in RAW_ROOTS}
    if source_name not in specs:
        return pd.DataFrame()
    return _load_local_source_bars(specs[source_name], vt_symbol, entry_day, event_time)


def _event_window(bars: pd.DataFrame, event: pd.Series, preferred_time: Any) -> pd.DataFrame:
    if bars.empty:
        return bars
    entry_day = _normalize_day(event.get("entry_date"))
    day = bars[bars["bar_date"].eq(entry_day)].copy().sort_values("bar_datetime").reset_index(drop=True)
    if day.empty:
        return day
    times = pd.to_datetime(day["bar_datetime"], errors="coerce")
    marker_times = [
        pd.to_datetime(event.get("first_stop_time"), errors="coerce"),
        pd.to_datetime(event.get("reentry_time"), errors="coerce"),
        pd.to_datetime(event.get("retry_failed_time"), errors="coerce"),
        pd.to_datetime(preferred_time, errors="coerce"),
    ]
    positions: list[int] = []
    for ts in marker_times:
        if pd.isna(ts):
            continue
        matches = np.flatnonzero(times.eq(ts).to_numpy())
        if len(matches):
            positions.append(int(matches[0]))
    if not positions:
        return day.head(240)
    start = max(0, min(positions) - 35)
    end = min(len(day), max(positions) + 80)
    return day.iloc[start:end].copy().reset_index(drop=True)


def _plot_minute_panel(ax: plt.Axes, bars: pd.DataFrame, event: pd.Series, quality: pd.Series | None, title_prefix: str) -> None:
    if bars.empty:
        ax.axis("off")
        ax.text(0.5, 0.5, f"{title_prefix}\nmissing minute bars", ha="center", va="center", fontsize=9)
        return
    x = np.arange(len(bars))
    close = pd.to_numeric(bars["close"], errors="coerce")
    high = pd.to_numeric(bars["high"], errors="coerce")
    low = pd.to_numeric(bars["low"], errors="coerce")
    ax.plot(x, close, color="#111827", linewidth=1.0, label="close")
    if np.nanmax(high.to_numpy() - low.to_numpy()) > 0:
        ax.vlines(x, low, high, color="#94a3b8", linewidth=0.55, alpha=0.65, label="range")
    for price_col, color, label in [
        ("entry_price_event", "#2563eb", "entry"),
        ("stop_price", "#dc2626", "0.5R stop"),
        ("progress_price", "#16a34a", "0.5R progress"),
    ]:
        price = _safe_float(event.get(price_col))
        if np.isfinite(price):
            ax.axhline(price, color=color, linewidth=0.85, linestyle="--", alpha=0.85, label=label)
    times = pd.to_datetime(bars["bar_datetime"], errors="coerce")
    for time_col, color, label in [
        ("first_stop_time", "#dc2626", "first stop"),
        ("reentry_time", "#2563eb", "reentry"),
        ("retry_failed_time", "#7c2d12", "retry failed"),
    ]:
        ts = pd.to_datetime(event.get(time_col), errors="coerce")
        if pd.isna(ts):
            continue
        matches = np.flatnonzero(times.eq(ts).to_numpy())
        if len(matches):
            ax.axvline(int(matches[0]), color=color, linewidth=0.95, alpha=0.85, label=label)
    tick_count = min(7, len(bars))
    if tick_count:
        ticks = np.linspace(0, len(bars) - 1, num=tick_count, dtype=int)
        ax.set_xticks(ticks)
        ax.set_xticklabels([pd.Timestamp(bars.iloc[pos]["bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
    quality_text = ""
    if quality is not None and not quality.empty:
        quality_text = (
            f"{quality.get('quality_label', '')}"
            f" r={int(_safe_float(quality.get('range_ready'), 0))}"
            f" v={int(_safe_float(quality.get('volume_ready'), 0))}"
            f" path={int(_safe_float(quality.get('window_path_ready'), 0))}"
        )
    ax.set_title(f"{title_prefix}\n{quality_text}", loc="left", fontsize=7)
    ax.grid(True, alpha=0.2)
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        dedup = dict(zip(labels, handles))
        ax.legend(dedup.values(), dedup.keys(), fontsize=6, loc="best")


def _select_atlas_events(event_summary: pd.DataFrame) -> pd.DataFrame:
    pieces: list[pd.DataFrame] = []
    for state, ascending, count in [
        ("flat_retry_failed", True, 4),
        ("open_after_reentry", False, 4),
        ("flat_no_reentry", True, 4),
    ]:
        subset = event_summary[event_summary["stop_retry_state"].astype(str).eq(state)].copy()
        if subset.empty:
            continue
        subset = subset.sort_values("event_realized_pnl", ascending=ascending)
        subset["atlas_reason"] = f"{state}_{'worst' if ascending else 'best'}"
        pieces.append(subset.head(count))
    if not pieces:
        return pd.DataFrame()
    return pd.concat(pieces, ignore_index=True, sort=False).drop_duplicates("event_key").head(12)


def _plot_atlas(
    event_summary: pd.DataFrame,
    quality: pd.DataFrame,
    stage861_groups: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    selected = _select_atlas_events(event_summary)
    if selected.empty:
        return pd.DataFrame()
    quality_lookup = {
        (str(row.event_key), str(row.moment), str(row.source_name)): row
        for row in quality.itertuples(index=False)
    }
    pages = int(math.ceil(len(selected) / ATLAS_PER_PAGE))
    manifest: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = selected.iloc[(page - 1) * ATLAS_PER_PAGE : page * ATLAS_PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 2, figsize=(18, max(4.0, 3.2 * len(part))), constrained_layout=True)
        axes_array = np.atleast_2d(axes)
        for row_idx, (_, event) in enumerate(part.iterrows()):
            vt_symbol = str(event.get("vt_symbol"))
            entry_day = _normalize_day(event.get("entry_date"))
            preferred_moment = "reentry" if str(event.get("stop_retry_state")) in REENTRY_STATES else "first_stop"
            preferred_time = event.get(f"{preferred_moment}_time")
            local_source = str(event.get(f"best_local_source_name_{preferred_moment}", ""))
            if not local_source or local_source == "nan":
                local_source = "stage859_gap_backfill"
            sources = ["stage861_full_minute", local_source]
            for col_idx, source_name in enumerate(sources):
                bars = _load_bars_for_source(source_name, stage861_groups, vt_symbol, entry_day, preferred_time)
                window = _event_window(bars, event, preferred_time)
                q_key = (str(event.get("event_key")), preferred_moment, source_name)
                quality_row = quality_lookup.get(q_key)
                q_series = pd.Series(quality_row._asdict()) if quality_row is not None else pd.Series(dtype=object)
                title = (
                    f"{source_name} | {vt_symbol} {event.get('direction', '')} {entry_day:%Y-%m-%d} | "
                    f"{event.get('stop_retry_state', '')} | pnl={_safe_float(event.get('event_realized_pnl')):,.0f}"
                )
                _plot_minute_panel(axes_array[row_idx, col_idx], window, event, q_series, title)
                manifest.append(
                    {
                        "page": page,
                        "event_key": event.get("event_key", ""),
                        "vt_symbol": vt_symbol,
                        "entry_date": entry_day.strftime("%Y-%m-%d") if not pd.isna(entry_day) else "",
                        "direction": event.get("direction", ""),
                        "stop_retry_state": event.get("stop_retry_state", ""),
                        "event_realized_pnl": _safe_float(event.get("event_realized_pnl")),
                        "preferred_moment": preferred_moment,
                        "source_name": source_name,
                        "quality_label": q_series.get("quality_label", ""),
                        "range_ready": int(_safe_float(q_series.get("range_ready"), 0)),
                        "volume_ready": int(_safe_float(q_series.get("volume_ready"), 0)),
                        "window_path_ready": int(_safe_float(q_series.get("window_path_ready"), 0)),
                    }
                )
        fig.suptitle("Stage032 minute-source comparison atlas", fontsize=13)
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
    return pd.DataFrame(manifest)


def _summary_rows(
    metrics: dict[str, float],
    features: pd.DataFrame,
    events: pd.DataFrame,
    source_summary: pd.DataFrame,
    event_summary: pd.DataFrame,
    stage031: pd.DataFrame,
) -> pd.DataFrame:
    reentry_events = event_summary[event_summary["stop_retry_state"].isin(REENTRY_STATES)].copy()
    stage861_reentry = source_summary[
        source_summary["source_name"].eq("stage861_full_minute") & source_summary["moment"].eq("reentry")
    ]
    local_summary = source_summary[source_summary["source_name"].ne("stage861_full_minute")]
    local_reentry_range = int(
        local_summary[local_summary["moment"].eq("reentry")]["range_ready_count"].max()
        if not local_summary[local_summary["moment"].eq("reentry")].empty
        else 0
    )
    local_reentry_volume = int(
        local_summary[local_summary["moment"].eq("reentry")]["volume_ready_count"].max()
        if not local_summary[local_summary["moment"].eq("reentry")].empty
        else 0
    )
    stage031_zero_range = np.nan
    stage031_volume_ready = np.nan
    if not stage031.empty:
        stage031_zero_range = int((pd.to_numeric(stage031["reentry_range_r"], errors="coerce").fillna(0.0) == 0.0).sum())
        stage031_volume_ready = int(pd.to_numeric(stage031["reentry_volume_ratio_20"], errors="coerce").notna().sum())
    rows = [
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "official_live_version": OFFICIAL_LIVE_VERSION,
            "official_live_alias": OFFICIAL_LIVE_ALIAS,
            "end_equity": metrics["end_equity"],
            "total_return_pct": metrics["total_return_pct"],
            "max_drawdown_pct": metrics["max_drawdown_pct"],
            "sharpe": metrics["sharpe"],
            "total_slippage": metrics["total_slippage"],
            "total_trade_count": metrics["total_trade_count"],
            "closed_lot_win_rate_pct": metrics["closed_lot_win_rate_pct"],
            "closed_lot_count": int(len(features)),
            "stop_retry_event_count": int(len(events)),
            "stop_retry_event_lot_count": int(pd.to_numeric(events["lot_count"], errors="coerce").fillna(0).sum()),
            "stop_retry_event_net_pnl": float(pd.to_numeric(events["event_realized_pnl"], errors="coerce").fillna(0.0).sum()),
            "reentry_event_count": int(len(reentry_events)),
            "reentry_event_net_pnl": float(pd.to_numeric(reentry_events["event_realized_pnl"], errors="coerce").fillna(0.0).sum()),
            "stage861_reentry_exact_count": int(stage861_reentry["exact_bar_count"].iloc[0]) if not stage861_reentry.empty else 0,
            "stage861_reentry_range_ready_count": int(stage861_reentry["range_ready_count"].iloc[0]) if not stage861_reentry.empty else 0,
            "stage861_reentry_volume_ready_count": int(stage861_reentry["volume_ready_count"].iloc[0]) if not stage861_reentry.empty else 0,
            "stage861_reentry_window_path_ready_count": int(stage861_reentry["window_path_ready_count"].iloc[0]) if not stage861_reentry.empty else 0,
            "best_local_reentry_range_ready_count": local_reentry_range,
            "best_local_reentry_volume_ready_count": local_reentry_volume,
            "events_with_local_better_than_stage861_reentry": int(
                pd.to_numeric(reentry_events.get("local_better_than_stage861_reentry", pd.Series(dtype=float)), errors="coerce")
                .fillna(0)
                .sum()
            ),
            "stage031_reentry_zero_range_events": stage031_zero_range,
            "stage031_reentry_volume_ratio_ready_events": stage031_volume_ready,
            "decision": "stage032_minute_source_quality_no_candidate_data_engineering_required",
            "candidate_ready": 0,
            "ab_triggered": 0,
        }
    ]
    return pd.DataFrame(rows)


def _write_report(
    summary: pd.DataFrame,
    source_summary: pd.DataFrame,
    event_summary: pd.DataFrame,
    atlas_manifest: pd.DataFrame,
) -> None:
    row = summary.iloc[0].to_dict()
    reentry_quality = (
        event_summary.groupby("reentry_quality_bucket", dropna=False)
        .agg(
            event_count=("event_key", "count"),
            lot_count=("lot_count", "sum"),
            net_pnl=("event_realized_pnl", "sum"),
        )
        .reset_index()
        .sort_values("event_count", ascending=False)
    )
    first_stop_quality = (
        event_summary.groupby("first_stop_quality_bucket", dropna=False)
        .agg(
            event_count=("event_key", "count"),
            lot_count=("lot_count", "sum"),
            net_pnl=("event_realized_pnl", "sum"),
        )
        .reset_index()
        .sort_values("event_count", ascending=False)
    )
    text = f"""# Stage032 分钟源质量与替代源审计

## 定位

- 时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}
- 工作模式：day。
- 研究线：`{LINE_ID}`。
- 官方正式版：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`。
- 阶段性质：只读数据质量审计；不新增交易规则、不改正式配置、不连接 CTP、不调用订单 API。
- 外部调研结论：TqSdk 官方文档定义 1 分钟 K 线应提供 `datetime/open/high/low/close/volume/open_oi/close_oi`；vn.py 的分钟 K 也以 tick 聚合 OHLC 和持仓字段为基础。外部异常案例说明历史 K 线可能存在时段或数据质量问题，所以本阶段用逐事件 exact-bar 审计，而不是假设“有分钟文件就可用”。

## 官方基准

- 期末权益：`{row["end_equity"]:,.2f}`
- 总收益：`{row["total_return_pct"]:.4f}%`
- 最大回撤：`{row["max_drawdown_pct"]:.4f}%`
- Sharpe：`{row["sharpe"]:.4f}`
- 总滑点：`{row["total_slippage"]:,.0f}`
- 总交易次数：`{row["total_trade_count"]:,.0f}`
- closed-lot 胜率：`{row["closed_lot_win_rate_pct"]:.4f}%`

## 核心结果

- stop/retry event keys：`{int(row["stop_retry_event_count"])}`，event lots：`{int(row["stop_retry_event_lot_count"])}`，净 PnL：`{row["stop_retry_event_net_pnl"]:,.2f}`。
- reentry event keys：`{int(row["reentry_event_count"])}`，净 PnL：`{row["reentry_event_net_pnl"]:,.2f}`。
- Stage861 reentry exact bar：`{int(row["stage861_reentry_exact_count"])}`；range ready：`{int(row["stage861_reentry_range_ready_count"])}`；volume ready：`{int(row["stage861_reentry_volume_ready_count"])}`；window close-path ready：`{int(row["stage861_reentry_window_path_ready_count"])}`。
- 本地替代源 reentry 最好口径下 range ready：`{int(row["best_local_reentry_range_ready_count"])}`；volume ready：`{int(row["best_local_reentry_volume_ready_count"])}`；reentry local better than Stage861：`{int(row["events_with_local_better_than_stage861_reentry"])}`。
- 决策：`{row["decision"]}`，`candidate_ready=0`，`ab_triggered=0`。

## source x moment 摘要

{_md_table(source_summary, max_rows=30)}

## reentry 质量桶

{_md_table(reentry_quality, max_rows=20)}

## first-stop 质量桶

{_md_table(first_stop_quality, max_rows=20)}

## 视觉产物

- path chart：`{PATH_CHART_OUT}`
- source heatmap：`{SOURCE_HEATMAP_OUT}`
- moment heatmap：`{MOMENT_HEATMAP_OUT}`
- atlas manifest：`{ATLAS_MANIFEST_OUT}`，pages：`{int(atlas_manifest["page"].max()) if not atlas_manifest.empty else 0}`

## 视觉观察

- 资金路径图中 stop/retry 总账仍是负贡献；reentry 相关曲线没有形成能替代正式路径的稳定右尾。
- source heatmap 显示 Stage861 的 exact 覆盖高，但 range/volume 几乎不可用；本地 TqSDK 替代源没有把 reentry 当根修成可用的 OHLCV candle。
- atlas 里 Stage861 与本地 raw 源多表现为 close-to-close 跳动路径可见，但单根 `open=high=low=close` 且 `volume=0`，只能用于路径定位，不能用于 body、区间收盘位置或量能扩张规则。

## 过拟合与继续价值

- 过拟合判断：否。本阶段没有选择交易阈值，也没有用未来盈亏反推参数；它只审计数据是否支持分钟 K 规则。
- 是否值得继续：有，但方向应先转为数据工程或换入场前外生源。若没有 tick/真实成交量分钟源，继续在 stop/retry 当根 body/volume 上挖规则会把数据缺陷过拟合成历史标签。

## TODO

- 若继续 stop/retry 分支，优先补 tick 或真实成交量分钟源，并复跑 exact bar 质量审计。
- 若暂不做数据工程，应停止 stop/retry 小变体，回到入场前可见、覆盖完整的外生风险源，且仍保持资金曲线和视觉 atlas。
"""
    REPORT_OUT.write_text(text, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features = _load_features()
    curve = _load_curve()
    stage031 = _load_stage031_events()
    events = _build_events(features)
    metrics = _official_metrics(curve, features)

    quality, stage861_groups = _build_quality_rows(events)
    source_summary = _source_summary(quality)
    best = _best_source_table(quality)
    event_summary = _event_quality_summary(events, best)
    contrib = _contribution_curve(curve, event_summary)

    _plot_path_chart(contrib)
    _plot_source_heatmap(source_summary)
    _plot_moment_heatmap(source_summary)
    atlas_manifest = _plot_atlas(event_summary, quality, stage861_groups)

    summary = _summary_rows(metrics, features, events, source_summary, event_summary, stage031)
    decision = summary.iloc[0].to_dict()
    decision.update(
        {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "external_research": {
                "tqsdk_docs": "get_kline_serial/get_kline_data_series should expose datetime, OHLC, volume, open_oi, close_oi.",
                "vnpy_docs": "minute bars are generated from tick data and should preserve OHLC and open_interest semantics.",
                "judgement": (
                    "Exact-bar data quality must be audited before turning minute candle body, range, "
                    "or volume into strategy rules."
                ),
            },
            "visual_outputs": {
                "path_chart": PATH_CHART_OUT,
                "source_heatmap": SOURCE_HEATMAP_OUT,
                "moment_heatmap": MOMENT_HEATMAP_OUT,
                "atlas_template": str(ATLAS_TEMPLATE),
            },
        }
    )

    quality.to_csv(EVENT_SOURCE_QUALITY_OUT, index=False, encoding="utf-8-sig")
    best.to_csv(EVENT_BEST_SOURCE_OUT, index=False, encoding="utf-8-sig")
    source_summary.to_csv(SOURCE_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    event_summary.to_csv(EVENT_QUALITY_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    contrib.to_csv(CONTRIB_CURVE_OUT, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, source_summary, event_summary, atlas_manifest)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
