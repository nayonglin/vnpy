from __future__ import annotations

from datetime import datetime, timedelta
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
STAGE = "Stage033"
MODEL_TAG = "stage033_tick_source_feasibility_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage033_c9_minrisk_tick_source_feasibility_audit"
ACCOUNT_CAPITAL = 150_000.0
TRADING_DAYS_PER_YEAR = 252
TICK_MATCH_TOLERANCE_SECONDS = 60
DOWNLOAD_WINDOW_SECONDS_BEFORE = 60
DOWNLOAD_WINDOW_SECONDS_AFTER = 120

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE005_DIR = LINE_DIR / "outputs" / "stage005_signal_quality_visual_forensics"
STAGE030_DIR = LINE_DIR / "outputs" / "stage030_stop_retry_event_quality_forensics"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage033_tick_source_feasibility_audit"

FEATURES_IN = STAGE030_DIR / (
    "qmt_roll_stage030_c9_minrisk_stop_retry_event_quality_forensics_features_"
    "stage030_stop_retry_event_quality_forensics_v1.csv"
)
OFFICIAL_CURVE_IN = STAGE005_DIR / (
    "qmt_roll_stage005_c9_minrisk_signal_quality_visual_forensics_official_curve_"
    "stage005_signal_quality_visual_forensics_v1.csv"
)

TICK_CATALOG_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_local_tick_file_catalog_{MODEL_TAG}.csv"
TICK_ROWS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_normalized_local_tick_rows_{MODEL_TAG}.csv"
EVENT_TICK_COVERAGE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_tick_coverage_{MODEL_TAG}.csv"
DOWNLOAD_PLAN_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tqsdk_tick_download_plan_{MODEL_TAG}.csv"
SOURCE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_tick_readiness_chart_{MODEL_TAG}.png"
CATALOG_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tick_catalog_year_heatmap_{MODEL_TAG}.png"
EVENT_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_tick_coverage_heatmap_{MODEL_TAG}.png"
TICK_SAMPLE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_local_tick_sample_chart_{MODEL_TAG}.png"

MOMENTS = [
    ("first_stop", "first_stop_time"),
    ("reentry", "reentry_time"),
    ("retry_failed", "retry_failed_time"),
]
REENTRY_STATES = ["flat_retry_failed", "open_after_reentry"]


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


def _normalize_day(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_convert(None) if getattr(ts, "tz", None) is not None else ts.tz_localize(None)
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
                "event_realized_pnl": float(pnl.sum()),
                "lot_count": int(len(group)),
                "first_stop_time": pd.to_datetime(row.get("first_stop_time"), errors="coerce"),
                "reentry_time": pd.to_datetime(row.get("reentry_time"), errors="coerce"),
                "retry_failed_time": pd.to_datetime(row.get("retry_failed_time"), errors="coerce"),
            }
        )
    return pd.DataFrame(rows).sort_values(["entry_date", "event_key"]).reset_index(drop=True)


def _source_family(path: Path) -> str:
    name = path.name
    for token in [
        "stage932_official_live_ctp_smoke_order",
        "stage608_readonly_tick_snapshot_probe",
        "stage367_live_one_lot_order",
        "stage285_simnow_open_close_proof",
        "stage258_simnow_smoke_order",
        "stage615_event_tca_reducer_contract_audit",
    ]:
        if token in name:
            return token
    if "tick" in name:
        return "other_tick_named_csv"
    return "unknown"


def _read_tick_candidate(path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    base = {
        "path": str(path),
        "file_name": path.name,
        "source_family": _source_family(path),
        "file_size_bytes": path.stat().st_size if path.exists() else 0,
        "is_tick_like": 0,
        "is_synthetic": int("synthetic" in path.name.lower() or "SIMTCA" in path.name),
        "row_count": 0,
        "symbol_count": 0,
        "min_datetime": "",
        "max_datetime": "",
        "min_year": np.nan,
        "max_year": np.nan,
        "columns": "",
        "parse_note": "",
    }
    try:
        frame = pd.read_csv(path, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        base["parse_note"] = "empty_csv"
        return pd.DataFrame(), base
    except Exception as exc:  # pragma: no cover - diagnostic path
        base["parse_note"] = f"read_error:{type(exc).__name__}"
        return pd.DataFrame(), base
    base["columns"] = ",".join(map(str, frame.columns))
    if frame.empty:
        base["parse_note"] = "no_rows"
        return pd.DataFrame(), base
    tick_like_cols = {"last_price", "bid_price_1", "ask_price_1", "volume_delta"}
    if not tick_like_cols.intersection(set(map(str, frame.columns))):
        base["parse_note"] = "not_tick_schema"
        return pd.DataFrame(), base
    if "datetime" not in frame.columns:
        base["parse_note"] = "missing_datetime"
        return pd.DataFrame(), base
    data = frame.copy()
    data["datetime"] = pd.to_datetime(data["datetime"], errors="coerce", utc=False)
    try:
        data["datetime"] = data["datetime"].dt.tz_localize(None)
    except (TypeError, AttributeError):
        pass
    if "vt_symbol" not in data.columns:
        if {"symbol", "exchange"}.issubset(data.columns):
            data["vt_symbol"] = data["symbol"].astype(str) + "." + data["exchange"].astype(str)
        else:
            data["vt_symbol"] = ""
    data["vt_symbol"] = data["vt_symbol"].astype(str)
    for column in [
        "last_price",
        "volume",
        "last_volume",
        "volume_delta",
        "turnover",
        "open_interest",
        "bid_price_1",
        "ask_price_1",
        "bid_volume_1",
        "ask_volume_1",
    ]:
        if column not in data.columns:
            data[column] = np.nan
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=["datetime"]).copy()
    data["source_file"] = str(path)
    data["source_family"] = base["source_family"]
    data["is_synthetic"] = base["is_synthetic"]
    data["tick_date"] = data["datetime"].dt.normalize()
    data["tick_year"] = data["datetime"].dt.year
    data["spread_1"] = data["ask_price_1"] - data["bid_price_1"]
    data["has_trade_volume_hint"] = (
        pd.to_numeric(data["volume_delta"], errors="coerce").fillna(0).gt(0)
        | pd.to_numeric(data["last_volume"], errors="coerce").fillna(0).gt(0)
    ).astype(int)
    keep = [
        "source_file",
        "source_family",
        "is_synthetic",
        "vt_symbol",
        "datetime",
        "tick_date",
        "tick_year",
        "last_price",
        "volume",
        "last_volume",
        "volume_delta",
        "turnover",
        "open_interest",
        "bid_price_1",
        "ask_price_1",
        "bid_volume_1",
        "ask_volume_1",
        "spread_1",
        "has_trade_volume_hint",
    ]
    normalized = data[keep].sort_values(["datetime", "vt_symbol"]).reset_index(drop=True)
    base.update(
        {
            "is_tick_like": 1,
            "row_count": int(len(normalized)),
            "symbol_count": int(normalized["vt_symbol"].replace("", np.nan).dropna().nunique()),
            "min_datetime": normalized["datetime"].min().strftime("%Y-%m-%d %H:%M:%S") if not normalized.empty else "",
            "max_datetime": normalized["datetime"].max().strftime("%Y-%m-%d %H:%M:%S") if not normalized.empty else "",
            "min_year": int(normalized["tick_year"].min()) if not normalized.empty else np.nan,
            "max_year": int(normalized["tick_year"].max()) if not normalized.empty else np.nan,
            "parse_note": "tick_schema_ok",
        }
    )
    return normalized, base


def _discover_local_ticks() -> tuple[pd.DataFrame, pd.DataFrame]:
    paths = sorted((EXAMPLE_DIR / "backtest_outputs").glob("*tick*.csv"))
    rows: list[pd.DataFrame] = []
    catalog: list[dict[str, Any]] = []
    for path in paths:
        data, meta = _read_tick_candidate(path)
        catalog.append(meta)
        if not data.empty:
            rows.append(data)
    tick_rows = pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()
    catalog_frame = pd.DataFrame(catalog).sort_values(["is_tick_like", "source_family", "file_name"], ascending=[False, True, True])
    return catalog_frame.reset_index(drop=True), tick_rows.reset_index(drop=True)


def _tq_symbol(vt_symbol: str) -> str:
    if "." not in vt_symbol:
        return vt_symbol
    symbol, exchange = vt_symbol.rsplit(".", 1)
    return f"{exchange}.{symbol}"


def _tqsdk_capability() -> dict[str, Any]:
    result = {
        "tqsdk_import_ok": 0,
        "data_downloader_import_ok": 0,
        "tqsdk_version": "",
        "historical_tick_download_supported_by_docs": 1,
        "dur_sec_for_tick": 0,
        "requires_tqsdk_professional_or_authorized_account": 1,
        "download_attempted": 0,
        "download_attempted_reason": "audit_only_no_credentials_no_network_download",
    }
    try:
        import tqsdk  # type: ignore

        result["tqsdk_import_ok"] = 1
        result["tqsdk_version"] = str(getattr(tqsdk, "__version__", ""))
    except Exception as exc:
        result["download_attempted_reason"] = f"tqsdk_import_failed:{type(exc).__name__}"
        return result
    try:
        from tqsdk.tools import DataDownloader  # noqa: F401

        result["data_downloader_import_ok"] = 1
    except Exception as exc:
        result["download_attempted_reason"] = f"DataDownloader_import_failed:{type(exc).__name__}"
    return result


def _event_tick_coverage(events: pd.DataFrame, ticks: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if ticks.empty:
        tick_by_symbol: dict[str, pd.DataFrame] = {}
    else:
        tick_by_symbol = {str(vt_symbol): group.copy() for vt_symbol, group in ticks.groupby("vt_symbol", sort=False)}
    for _, event in events.iterrows():
        vt_symbol = str(event.get("vt_symbol"))
        symbol_ticks = tick_by_symbol.get(vt_symbol, pd.DataFrame())
        for moment, time_col in MOMENTS:
            event_time = pd.to_datetime(event.get(time_col), errors="coerce")
            base = {
                "event_key": event.get("event_key", ""),
                "vt_symbol": vt_symbol,
                "product": event.get("product", ""),
                "direction": event.get("direction", ""),
                "entry_date": event.get("entry_date"),
                "entry_year": event.get("entry_year", np.nan),
                "stop_retry_state": event.get("stop_retry_state", ""),
                "event_realized_pnl": _safe_float(event.get("event_realized_pnl"), 0.0),
                "lot_count": int(event.get("lot_count", 0)),
                "moment": moment,
                "event_time": event_time,
                "event_time_ready": int(pd.notna(event_time)),
                "local_tick_row_count_same_symbol": int(len(symbol_ticks)),
                "local_tick_row_count_same_day": 0,
                "local_tick_rows_near_event": 0,
                "local_tick_files_near_event": 0,
                "nearest_tick_abs_seconds": np.nan,
                "nearest_tick_time": "",
                "nearest_tick_source_family": "",
                "nearest_tick_file": "",
                "bar_reconstruct_tick_count": 0,
                "bar_reconstruct_ready": 0,
                "trade_volume_hint_ready": 0,
                "local_tick_coverage_bucket": "missing_event_time",
            }
            if pd.isna(event_time):
                rows.append(base)
                continue
            if symbol_ticks.empty:
                base["local_tick_coverage_bucket"] = "no_local_tick_symbol"
                rows.append(base)
                continue
            event_day = pd.Timestamp(event_time).normalize()
            same_day = symbol_ticks[symbol_ticks["tick_date"].eq(event_day)].copy()
            base["local_tick_row_count_same_day"] = int(len(same_day))
            if same_day.empty:
                base["local_tick_coverage_bucket"] = "no_local_tick_event_day"
                nearest = symbol_ticks.copy()
            else:
                nearest = same_day.copy()
            nearest["abs_seconds"] = (pd.to_datetime(nearest["datetime"], errors="coerce") - event_time).abs().dt.total_seconds()
            nearest = nearest.dropna(subset=["abs_seconds"]).sort_values("abs_seconds")
            if not nearest.empty:
                nrow = nearest.iloc[0]
                base.update(
                    {
                        "nearest_tick_abs_seconds": float(nrow["abs_seconds"]),
                        "nearest_tick_time": pd.Timestamp(nrow["datetime"]).strftime("%Y-%m-%d %H:%M:%S"),
                        "nearest_tick_source_family": str(nrow.get("source_family", "")),
                        "nearest_tick_file": str(nrow.get("source_file", "")),
                    }
                )
            if same_day.empty:
                rows.append(base)
                continue
            near = same_day[
                (pd.to_datetime(same_day["datetime"], errors="coerce") - event_time).abs().dt.total_seconds()
                <= TICK_MATCH_TOLERANCE_SECONDS
            ].copy()
            base["local_tick_rows_near_event"] = int(len(near))
            base["local_tick_files_near_event"] = int(near["source_file"].nunique()) if not near.empty else 0
            bar_window = same_day[
                (pd.to_datetime(same_day["datetime"], errors="coerce") >= event_time)
                & (pd.to_datetime(same_day["datetime"], errors="coerce") < event_time + pd.Timedelta(seconds=60))
            ].copy()
            base["bar_reconstruct_tick_count"] = int(len(bar_window))
            base["bar_reconstruct_ready"] = int(len(bar_window) >= 2)
            base["trade_volume_hint_ready"] = int(
                pd.to_numeric(bar_window.get("has_trade_volume_hint", pd.Series(dtype=float)), errors="coerce").fillna(0).sum() > 0
            )
            if base["bar_reconstruct_ready"] and base["trade_volume_hint_ready"]:
                base["local_tick_coverage_bucket"] = "local_tick_bar_and_volume_ready"
            elif base["bar_reconstruct_ready"]:
                base["local_tick_coverage_bucket"] = "local_tick_bar_ready_no_volume_hint"
            elif base["local_tick_rows_near_event"] > 0:
                base["local_tick_coverage_bucket"] = "local_tick_near_event_insufficient_bar"
            else:
                base["local_tick_coverage_bucket"] = "no_local_tick_near_event"
            rows.append(base)
    return pd.DataFrame(rows).sort_values(["entry_date", "event_key", "moment"]).reset_index(drop=True)


def _download_plan(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, event in events.iterrows():
        for moment, time_col in MOMENTS:
            event_time = pd.to_datetime(event.get(time_col), errors="coerce")
            if pd.isna(event_time):
                continue
            start_dt = pd.Timestamp(event_time) - pd.Timedelta(seconds=DOWNLOAD_WINDOW_SECONDS_BEFORE)
            end_dt = pd.Timestamp(event_time) + pd.Timedelta(seconds=DOWNLOAD_WINDOW_SECONDS_AFTER)
            rows.append(
                {
                    "event_key": event.get("event_key", ""),
                    "vt_symbol": event.get("vt_symbol", ""),
                    "tq_symbol": _tq_symbol(str(event.get("vt_symbol", ""))),
                    "moment": moment,
                    "event_time": event_time,
                    "start_dt": start_dt,
                    "end_dt": end_dt,
                    "dur_sec": 0,
                    "csv_file_name_suggestion": (
                        f"{str(event.get('vt_symbol', '')).replace('.', '_')}_"
                        f"{pd.Timestamp(event_time).strftime('%Y%m%d_%H%M%S')}_{moment}_tick.csv"
                    ),
                    "reason": "Stage033 follow-up only; not downloaded in this audit.",
                }
            )
    return pd.DataFrame(rows).sort_values(["vt_symbol", "event_time", "moment"]).reset_index(drop=True)


def _source_summary(catalog: pd.DataFrame, ticks: pd.DataFrame, coverage: pd.DataFrame, plan: pd.DataFrame, capability: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    tick_like = catalog[catalog["is_tick_like"].eq(1)].copy() if not catalog.empty else pd.DataFrame()
    for family, group in tick_like.groupby("source_family", dropna=False):
        sub_ticks = ticks[ticks["source_family"].eq(family)] if not ticks.empty else pd.DataFrame()
        rows.append(
            {
                "source_name": f"local_{family}",
                "source_type": "local_csv",
                "file_count": int(len(group)),
                "row_count": int(pd.to_numeric(group["row_count"], errors="coerce").fillna(0).sum()),
                "symbol_count": int(sub_ticks["vt_symbol"].nunique()) if not sub_ticks.empty else 0,
                "min_datetime": sub_ticks["datetime"].min().strftime("%Y-%m-%d %H:%M:%S") if not sub_ticks.empty else "",
                "max_datetime": sub_ticks["datetime"].max().strftime("%Y-%m-%d %H:%M:%S") if not sub_ticks.empty else "",
                "event_moment_count": int(len(coverage)),
                "event_moment_near_count": int(
                    pd.to_numeric(
                        coverage[coverage["nearest_tick_source_family"].eq(family)]["local_tick_rows_near_event"],
                        errors="coerce",
                    )
                    .fillna(0)
                    .gt(0)
                    .sum()
                ),
                "historical_download_plan_rows": 0,
                "ready_for_stage030_replay": 0,
                "note": "local live/smoke/synthetic tick files; not historical event coverage",
            }
        )
    rows.append(
        {
            "source_name": "tqsdk_DataDownloader_dur_sec_0",
            "source_type": "external_api_capability",
            "file_count": 0,
            "row_count": 0,
            "symbol_count": 0,
            "min_datetime": "",
            "max_datetime": "",
            "event_moment_count": int(len(coverage)),
            "event_moment_near_count": 0,
            "historical_download_plan_rows": int(len(plan)),
            "ready_for_stage030_replay": 0,
            "note": (
                f"import_ok={capability.get('tqsdk_import_ok')}; "
                f"downloader_ok={capability.get('data_downloader_import_ok')}; "
                "docs support historical tick download but audit did not authenticate or download"
            ),
        }
    )
    return pd.DataFrame(rows)


def _contribution_curve(curve: pd.DataFrame, events: pd.DataFrame, coverage: pd.DataFrame) -> pd.DataFrame:
    event_buckets = coverage[coverage["moment"].eq("reentry")].copy()
    no_reentry = events[~events["stop_retry_state"].isin(REENTRY_STATES)].copy()
    if not no_reentry.empty:
        no_reentry = no_reentry.assign(local_tick_coverage_bucket="no_reentry_state")
        event_buckets = pd.concat(
            [
                event_buckets[
                    [
                        "event_key",
                        "entry_date",
                        "event_realized_pnl",
                        "local_tick_coverage_bucket",
                    ]
                ],
                no_reentry[["event_key", "entry_date", "event_realized_pnl", "local_tick_coverage_bucket"]],
            ],
            ignore_index=True,
            sort=False,
        )
    out = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].copy()
    event_buckets["entry_date"] = pd.to_datetime(event_buckets["entry_date"], errors="coerce").dt.normalize()
    event_buckets["event_realized_pnl"] = pd.to_numeric(event_buckets["event_realized_pnl"], errors="coerce").fillna(0.0)
    daily_all = event_buckets.groupby("entry_date")["event_realized_pnl"].sum()
    out["cum_pnl_stop_retry_events_all"] = out["date"].map(daily_all).fillna(0.0).cumsum()
    for bucket in sorted(event_buckets["local_tick_coverage_bucket"].dropna().astype(str).unique()):
        daily = event_buckets[event_buckets["local_tick_coverage_bucket"].astype(str).eq(bucket)].groupby("entry_date")[
            "event_realized_pnl"
        ].sum()
        out[f"cum_pnl_tick_bucket_{bucket}"] = out["date"].map(daily).fillna(0.0).cumsum()
    return out


def _plot_path(contrib: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True, constrained_layout=True)
    axes[0].plot(contrib["date"], contrib["account_equity"], color="#111827", linewidth=1.1, label="official equity")
    axes[0].set_title("Official C9/15w equity")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="best")

    axes[1].plot(contrib["date"], contrib["drawdown_pct"], color="#dc2626", linewidth=1.0, label="drawdown %")
    axes[1].set_title("Official drawdown and broker10")
    axes[1].grid(True, alpha=0.25)
    ax2 = axes[1].twinx()
    ax2.plot(contrib["date"], contrib["broker10_margin_to_equity_pct"], color="#2563eb", linewidth=0.8, alpha=0.75)

    axes[2].plot(contrib["date"], contrib["cum_pnl_stop_retry_events_all"], color="#111827", linewidth=1.2, label="all audited events")
    for column, color in [
        ("cum_pnl_tick_bucket_no_local_tick_event_day", "#dc2626"),
        ("cum_pnl_tick_bucket_no_local_tick_symbol", "#f97316"),
        ("cum_pnl_tick_bucket_no_reentry_state", "#9333ea"),
        ("cum_pnl_tick_bucket_local_tick_bar_and_volume_ready", "#16a34a"),
    ]:
        if column in contrib.columns:
            axes[2].plot(contrib["date"], contrib[column], linewidth=1.0, label=column.replace("cum_pnl_tick_bucket_", ""))
    axes[2].axhline(0, color="#6b7280", linewidth=0.8)
    axes[2].set_title("Cumulative event PnL by local tick readiness bucket")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend(loc="best", fontsize=8)
    fig.suptitle("Stage033 tick-source feasibility path", fontsize=14)
    fig.savefig(PATH_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_catalog_heatmap(ticks: pd.DataFrame) -> None:
    if ticks.empty:
        fig, ax = plt.subplots(figsize=(9, 4), constrained_layout=True)
        ax.axis("off")
        ax.text(0.5, 0.5, "No local tick-like rows found", ha="center", va="center")
        fig.savefig(CATALOG_HEATMAP_OUT, dpi=150)
        plt.close(fig)
        return
    pivot = (
        ticks.pivot_table(index="source_family", columns="tick_year", values="last_price", aggfunc="count", fill_value=0)
        .sort_index()
    )
    matrix = np.log10(pivot.to_numpy(dtype=float) + 1.0)
    fig, ax = plt.subplots(figsize=(11, max(4, 0.55 * len(pivot.index) + 2)), constrained_layout=True)
    im = ax.imshow(matrix, aspect="auto", cmap="YlGnBu")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([str(int(col)) for col in pivot.columns], fontsize=8)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = int(pivot.iloc[i, j])
            ax.text(j, i, str(value), ha="center", va="center", fontsize=7)
    ax.set_title("Local tick-like row count by source family and year")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02, label="log10(rows+1)")
    fig.savefig(CATALOG_HEATMAP_OUT, dpi=150)
    plt.close(fig)


def _plot_event_heatmap(coverage: pd.DataFrame) -> None:
    if coverage.empty:
        return
    buckets = sorted(coverage["local_tick_coverage_bucket"].dropna().astype(str).unique())
    pivot = (
        coverage.pivot_table(index="local_tick_coverage_bucket", columns="moment", values="event_key", aggfunc="count", fill_value=0)
        .reindex(index=buckets)
        .reindex(columns=[moment for moment, _ in MOMENTS], fill_value=0)
    )
    matrix = pivot.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(10, max(4, 0.55 * len(pivot.index) + 2)), constrained_layout=True)
    im = ax.imshow(matrix, aspect="auto", cmap="YlOrRd")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, fontsize=8)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, str(int(matrix[i, j])), ha="center", va="center", fontsize=8)
    ax.set_title("Stage030 event moments by local tick coverage bucket")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    fig.savefig(EVENT_HEATMAP_OUT, dpi=150)
    plt.close(fig)


def _plot_tick_sample(ticks: pd.DataFrame, events: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), constrained_layout=True)
    if ticks.empty:
        axes[0].axis("off")
        axes[0].text(0.5, 0.5, "No local tick sample", ha="center", va="center")
    else:
        real_ticks = ticks[ticks["is_synthetic"].eq(0)].copy()
        sample_source = real_ticks if not real_ticks.empty else ticks
        sample_key = sample_source.groupby(["source_file", "vt_symbol"]).size().sort_values(ascending=False).index[0]
        sample = sample_source[
            sample_source["source_file"].eq(sample_key[0]) & sample_source["vt_symbol"].eq(sample_key[1])
        ].copy()
        sample = sample.sort_values("datetime").head(250)
        x = np.arange(len(sample))
        axes[0].plot(x, sample["last_price"], color="#111827", linewidth=1.0, label="last")
        if sample["bid_price_1"].notna().any():
            axes[0].plot(x, sample["bid_price_1"], color="#2563eb", linewidth=0.8, alpha=0.6, label="bid1")
        if sample["ask_price_1"].notna().any():
            axes[0].plot(x, sample["ask_price_1"], color="#dc2626", linewidth=0.8, alpha=0.6, label="ask1")
        ticks_idx = np.linspace(0, len(sample) - 1, num=min(8, len(sample)), dtype=int)
        axes[0].set_xticks(ticks_idx)
        axes[0].set_xticklabels([pd.Timestamp(sample.iloc[pos]["datetime"]).strftime("%m-%d %H:%M:%S") for pos in ticks_idx], fontsize=7)
        axes[0].set_title(f"Local tick sample: {sample_key[1]} | {Path(sample_key[0]).name}", loc="left", fontsize=9)
        axes[0].legend(loc="best")
        axes[0].grid(True, alpha=0.25)
    events_by_year = events.groupby("entry_year", dropna=False).size().reset_index(name="stop_retry_event_count")
    axes[1].bar(events_by_year["entry_year"].astype(str), events_by_year["stop_retry_event_count"], color="#64748b")
    axes[1].set_title("Stage030 stop/retry event years requiring historical tick reconstruction", loc="left")
    axes[1].set_ylabel("event keys")
    axes[1].tick_params(axis="x", rotation=45)
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.suptitle("Stage033 local tick sample vs historical event need", fontsize=14)
    fig.savefig(TICK_SAMPLE_CHART_OUT, dpi=150)
    plt.close(fig)


def _summary_rows(
    metrics: dict[str, float],
    features: pd.DataFrame,
    events: pd.DataFrame,
    catalog: pd.DataFrame,
    ticks: pd.DataFrame,
    coverage: pd.DataFrame,
    plan: pd.DataFrame,
    capability: dict[str, Any],
) -> pd.DataFrame:
    local_ready = int(coverage["local_tick_coverage_bucket"].eq("local_tick_bar_and_volume_ready").sum()) if not coverage.empty else 0
    reentry_cov = coverage[coverage["moment"].eq("reentry")].copy() if not coverage.empty else pd.DataFrame()
    reentry_ready_count = (
        int(pd.to_numeric(reentry_cov["event_time_ready"], errors="coerce").fillna(0).sum()) if not reentry_cov.empty else 0
    )
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
            "local_tick_named_csv_count": int(len(catalog)),
            "local_tick_like_file_count": int(catalog["is_tick_like"].sum()) if not catalog.empty else 0,
            "local_tick_like_row_count": int(len(ticks)),
            "local_tick_symbol_count": int(ticks["vt_symbol"].nunique()) if not ticks.empty else 0,
            "event_moment_count": int(len(coverage)),
            "event_moment_local_bar_volume_ready_count": local_ready,
            "reentry_event_moment_slot_count": int(len(reentry_cov)) if not reentry_cov.empty else 0,
            "reentry_event_time_ready_count": reentry_ready_count,
            "reentry_local_bar_volume_ready_count": int(reentry_cov["local_tick_coverage_bucket"].eq("local_tick_bar_and_volume_ready").sum())
            if not reentry_cov.empty
            else 0,
            "tqsdk_import_ok": int(capability.get("tqsdk_import_ok", 0)),
            "tqsdk_data_downloader_import_ok": int(capability.get("data_downloader_import_ok", 0)),
            "tqsdk_tick_download_plan_rows": int(len(plan)),
            "download_attempted": int(capability.get("download_attempted", 0)),
            "decision": "stage033_tick_source_no_candidate_local_history_missing_download_plan_only",
            "candidate_ready": 0,
            "ab_triggered": 0,
        }
    ]
    return pd.DataFrame(rows)


def _write_report(
    summary: pd.DataFrame,
    source_summary: pd.DataFrame,
    catalog: pd.DataFrame,
    coverage: pd.DataFrame,
    plan: pd.DataFrame,
    capability: dict[str, Any],
) -> None:
    row = summary.iloc[0].to_dict()
    bucket_summary = (
        coverage.groupby(["moment", "local_tick_coverage_bucket"], dropna=False)
        .agg(event_moment_count=("event_key", "count"), event_pnl=("event_realized_pnl", "sum"))
        .reset_index()
        .sort_values(["moment", "event_moment_count"], ascending=[True, False])
    )
    text = f"""# Stage033 tick/真实成交量分钟源可行性审计

## 定位

- 时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}
- 工作模式：day。
- 研究线：`{LINE_ID}`。
- 官方正式版：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`。
- 阶段性质：只读数据工程可行性审计；不下载外部数据、不新增交易规则、不改正式配置、不连接 CTP、不调用订单 API。

## 外部调研结论

- TqSdk `DataDownloader` 文档说明：`dur_sec=0` 表示 Tick 数据，且可按起止时间输出 CSV；但该工具是 TqSdk 专业版功能，需要认证/授权。
- TqSdk GitHub/README 说明其体系覆盖历史数据、实时数据、Tick 级和 K 线级回测。
- vn.py README 说明 data_recorder 可以实时记录 Tick/K 线到数据库；这证明框架路径存在，但不证明本仓库已有历史 tick。
- 我的判断：补 tick 是技术上可行的，但当前工作区没有覆盖 Stage030 历史事件的本地 tick 数据；不能在没有下载和质检的情况下继续做 stop/retry 当根 OHLCV 规则。

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
- 本地 `*tick*.csv` 文件：`{int(row["local_tick_named_csv_count"])}`；tick-like 文件：`{int(row["local_tick_like_file_count"])}`；tick-like rows：`{int(row["local_tick_like_row_count"])}`；symbols：`{int(row["local_tick_symbol_count"])}`。
- Stage030 event moments：`{int(row["event_moment_count"])}`；本地 tick 可重建 bar 且有成交量线索：`{int(row["event_moment_local_bar_volume_ready_count"])}`。
- reentry moment slots：`{int(row["reentry_event_moment_slot_count"])}`；真实重入时间可用：`{int(row["reentry_event_time_ready_count"])}`；本地 tick 可重建 bar 且有成交量线索：`{int(row["reentry_local_bar_volume_ready_count"])}`。
- TqSdk import：`{int(row["tqsdk_import_ok"])}`；DataDownloader import：`{int(row["tqsdk_data_downloader_import_ok"])}`；tick download plan rows：`{int(row["tqsdk_tick_download_plan_rows"])}`；download_attempted：`0`。
- 决策：`{row["decision"]}`，`candidate_ready=0`，`ab_triggered=0`。

## 本地 tick source 摘要

{_md_table(source_summary, max_rows=20)}

## 事件覆盖桶

{_md_table(bucket_summary, max_rows=30)}

## tick 文件目录前列

{_md_table(catalog[catalog["is_tick_like"].eq(1)].head(15), max_rows=15)}

## 输出文件

- source summary：`{SOURCE_SUMMARY_OUT}`
- tick catalog：`{TICK_CATALOG_OUT}`
- event coverage：`{EVENT_TICK_COVERAGE_OUT}`
- download plan：`{DOWNLOAD_PLAN_OUT}`
- path chart：`{PATH_CHART_OUT}`
- catalog heatmap：`{CATALOG_HEATMAP_OUT}`
- event heatmap：`{EVENT_HEATMAP_OUT}`
- tick sample chart：`{TICK_SAMPLE_CHART_OUT}`

## 视觉观察

- path chart 显示 stop/retry 事件贡献仍未被任何本地 tick-ready 组解释；可用覆盖桶基本是 `no_local_tick_symbol/no_local_tick_event_day`。
- catalog heatmap 显示本地 tick-like 文件集中在 `2026` 附近的 live/smoke/snapshot 证据，以及少量 synthetic TCA 样本；不是 `2018-2026` 历史回测 tick 库。
- tick sample chart 能证明 live tick 结构本身有 bid/ask/last/累计 volume/open_interest 字段，但下方面板显示 Stage030 需要跨 `2018-2026` 多年的历史事件覆盖。

## 过拟合与继续价值

- 过拟合判断：否。本阶段没有写交易规则，也没有用盈亏结果选择阈值；只是判断数据源是否足够支撑分钟级 OHLCV 规则。
- 是否值得继续：有，但只在能取得历史 tick/真实成交量分钟源时继续 stop/retry；否则应换到入场前可见、覆盖完整的外生风险源。

## TODO

- 若继续 stop/retry：按 `{DOWNLOAD_PLAN_OUT}` 的事件窗口，用 TqSdk 专业版 DataDownloader `dur_sec=0` 或同等历史 tick 数据源下载，再复跑 Stage032/033 质量审计。
- 若暂不下载：停止 stop/retry 当根 OHLCV 分支，转向入场前外生风险源或只做 forward watch。
"""
    REPORT_OUT.write_text(text, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features = _load_features()
    curve = _load_curve()
    events = _build_events(features)
    metrics = _official_metrics(curve, features)
    catalog, ticks = _discover_local_ticks()
    capability = _tqsdk_capability()
    coverage = _event_tick_coverage(events, ticks)
    plan = _download_plan(events)
    source_summary = _source_summary(catalog, ticks, coverage, plan, capability)
    contrib = _contribution_curve(curve, events, coverage)
    summary = _summary_rows(metrics, features, events, catalog, ticks, coverage, plan, capability)

    _plot_path(contrib)
    _plot_catalog_heatmap(ticks)
    _plot_event_heatmap(coverage)
    _plot_tick_sample(ticks, events)

    catalog.to_csv(TICK_CATALOG_OUT, index=False, encoding="utf-8-sig")
    ticks.to_csv(TICK_ROWS_OUT, index=False, encoding="utf-8-sig")
    coverage.to_csv(EVENT_TICK_COVERAGE_OUT, index=False, encoding="utf-8-sig")
    plan.to_csv(DOWNLOAD_PLAN_OUT, index=False, encoding="utf-8-sig")
    source_summary.to_csv(SOURCE_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    decision = summary.iloc[0].to_dict()
    decision.update(
        {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tqsdk_capability": capability,
            "external_research": {
                "tqsdk_DataDownloader": "TqSdk docs describe DataDownloader with dur_sec=0 for Tick CSV output; professional/auth required.",
                "vnpy_data_recorder": "vn.py data_recorder can record Tick or K-line data to database in real time.",
                "judgement": "Historical tick reconstruction is feasible only after authorized download; local workspace does not contain Stage030 historical tick coverage.",
            },
            "visual_outputs": {
                "path_chart": PATH_CHART_OUT,
                "catalog_heatmap": CATALOG_HEATMAP_OUT,
                "event_heatmap": EVENT_HEATMAP_OUT,
                "tick_sample_chart": TICK_SAMPLE_CHART_OUT,
            },
        }
    )
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, source_summary, catalog, coverage, plan, capability)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
