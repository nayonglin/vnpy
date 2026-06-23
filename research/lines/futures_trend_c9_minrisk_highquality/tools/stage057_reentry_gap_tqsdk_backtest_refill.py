from __future__ import annotations

from datetime import datetime, timedelta
import json
import logging
import math
import os
from pathlib import Path
import time
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage057"
MODEL_TAG = "stage057_reentry_gap_tqsdk_backtest_refill_v1"
OUTPUT_PREFIX = "qmt_roll_stage057_c9_minrisk_reentry_gap_tqsdk_backtest_refill"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE054_DIR = LINE_DIR / "outputs" / "stage054_c9_reentry_reclaim_quality_audit"
STAGE056_DIR = LINE_DIR / "outputs" / "stage056_reentry_gap_local_deep_search"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage057_reentry_gap_tqsdk_backtest_refill"
RAW_MINUTE_DIR = OUTPUT_DIR / "raw_minute"
RAW_TICK_DIR = OUTPUT_DIR / "raw_tick"

MANIFEST_IN = (
    STAGE056_DIR
    / "qmt_roll_stage056_c9_minrisk_reentry_gap_local_deep_search_download_manifest_"
    "stage056_reentry_gap_local_deep_search_v1.csv"
)
CURVE_IN = (
    STAGE054_DIR
    / "qmt_roll_stage054_c9_minrisk_reentry_reclaim_quality_audit_upper_bound_curve_"
    "stage054_c9_reentry_reclaim_quality_audit_v1.csv"
)

EVENT_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_status_{MODEL_TAG}.csv"
MINUTE_BARS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_minute_bars_{MODEL_TAG}.csv"
TICK_REBUILT_BARS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tick_rebuilt_bars_{MODEL_TAG}.csv"
CONTRIB_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_refill_contribution_curve_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_refill_path_chart_{MODEL_TAG}.png"
EVENT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_refill_chart_{MODEL_TAG}.png"
STATUS_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_status_chart_{MODEL_TAG}.png"

MAX_EVENTS = int(os.getenv("STAGE057_MAX_EVENTS", "0"))
MAX_SECONDS_PER_EVENT = int(os.getenv("STAGE057_MAX_SECONDS_PER_EVENT", "90"))
ENABLE_TQSDK = os.getenv("STAGE057_ENABLE_TQSDK", "1").strip() != "0"
TICK_WINDOW_MINUTES = int(os.getenv("STAGE057_TICK_WINDOW_MINUTES", "3"))
MINUTE_DATA_LENGTH = int(os.getenv("STAGE057_MINUTE_DATA_LENGTH", "1000"))
TICK_DATA_LENGTH = int(os.getenv("STAGE057_TICK_DATA_LENGTH", "12000"))


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _timestamp(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts


def _normalize_tqsdk_datetime(value: Any) -> pd.Timestamp:
    try:
        from vnpy.trader.utility import ZoneInfo

        ts = pd.to_datetime(value, unit="ns", errors="coerce", utc=True)
        if pd.isna(ts):
            return pd.NaT
        return ts.tz_convert(ZoneInfo("Asia/Shanghai")).tz_localize(None)
    except Exception:
        return _timestamp(value)


def _load_manifest() -> pd.DataFrame:
    data = _read_csv(MANIFEST_IN)
    for column in ["reentry_lot_pnl", "entry_year"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    for column in ["reentry_time", "download_start_dt", "download_end_dt"]:
        data[column] = pd.to_datetime(data[column], errors="coerce")
    data = data.sort_values(["reentry_lot_pnl", "event_key"], ascending=[False, True]).reset_index(drop=True)
    if MAX_EVENTS > 0:
        data = data.head(MAX_EVENTS).copy()
    return data


def _get_credentials() -> tuple[str, str, dict[str, Any]]:
    try:
        from vnpy.trader.setting import SETTINGS

        username = str(SETTINGS.get("datafeed.username", "") or "")
        password = str(SETTINGS.get("datafeed.password", "") or "")
        name = str(SETTINGS.get("datafeed.name", "") or "")
    except Exception as exc:
        return "", "", {"status": f"read_failed:{type(exc).__name__}", "datafeed_name": ""}
    return username, password, {
        "status": "available" if username and password else "missing",
        "datafeed_name": name,
        "username_present": bool(username),
        "username_len": len(username),
        "password_present": bool(password),
        "password_len": len(password),
    }


def _target_minute_bounds(event_ts: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = event_ts.floor("min")
    return start, start + pd.Timedelta(minutes=1)


def _raw_paths(row: pd.Series) -> tuple[Path, Path]:
    vt_symbol = str(row["vt_symbol"])
    code, exchange = vt_symbol.split(".", 1)
    event_ts = _timestamp(row["reentry_time"])
    name = f"{code}_{event_ts:%Y%m%d_%H%M}_{str(row['event_key']).replace('.', '_')}"
    return RAW_MINUTE_DIR / exchange / f"{name}_minute_backtest.csv", RAW_TICK_DIR / exchange / f"{name}_tick_backtest.csv"


def _empty_status(row: pd.Series, credential_status: dict[str, Any], status: str, message: str = "") -> dict[str, Any]:
    return {
        "event_key": row["event_key"],
        "vt_symbol": row["vt_symbol"],
        "tq_symbol": row["tq_symbol"],
        "reentry_time": row["reentry_time"],
        "entry_year": row["entry_year"],
        "quality_bucket": row["quality_bucket"],
        "reentry_lot_pnl": row["reentry_lot_pnl"],
        "minute_status": status,
        "minute_rows": 0,
        "minute_exact_ready": 0,
        "minute_ohlcv_ready": 0,
        "minute_bar_range": np.nan,
        "minute_volume": np.nan,
        "tick_status": status,
        "tick_rows": 0,
        "tick_target_rows": 0,
        "tick_rebuilt_ready": 0,
        "tick_rebuilt_range": np.nan,
        "tick_rebuilt_volume_delta": np.nan,
        "final_refill_status": status,
        "message": message,
        "credential_status": credential_status.get("status", ""),
    }


def _extract_minute(row: pd.Series, username: str, password: str) -> tuple[dict[str, Any], pd.DataFrame]:
    logging.getLogger().setLevel(logging.WARNING)
    logging.getLogger("tqsdk").setLevel(logging.WARNING)
    minute_path, _ = _raw_paths(row)
    minute_path.parent.mkdir(parents=True, exist_ok=True)
    status: dict[str, Any] = {
        "minute_status": "unknown",
        "minute_rows": 0,
        "minute_exact_ready": 0,
        "minute_ohlcv_ready": 0,
        "minute_bar_range": np.nan,
        "minute_volume": np.nan,
        "minute_path": str(minute_path),
        "minute_message": "",
    }
    if minute_path.exists() and minute_path.stat().st_size > 0:
        try:
            cached = pd.read_csv(minute_path, encoding="utf-8-sig")
            status["minute_status"] = "cached"
            return _evaluate_minute(row, cached, status), cached
        except Exception as exc:
            status["minute_message"] = f"cached_read_failed:{type(exc).__name__}:{exc}"

    try:
        from tqsdk import BacktestFinished, TqApi, TqAuth, TqBacktest, TqSim
    except Exception as exc:
        status["minute_status"] = "import_failed"
        status["minute_message"] = repr(exc)[:500]
        return status, pd.DataFrame()

    start_dt = _timestamp(row["download_start_dt"])
    end_dt = _timestamp(row["download_end_dt"])
    started = time.time()
    rows: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    api = None
    try:
        api = TqApi(
            TqSim(),
            backtest=TqBacktest(start_dt=start_dt.to_pydatetime(), end_dt=end_dt.to_pydatetime()),
            auth=TqAuth(username, password),
            disable_print=True,
        )
        klines = api.get_kline_serial(str(row["tq_symbol"]), duration_seconds=60, data_length=MINUTE_DATA_LENGTH)
        while True:
            if time.time() - started > MAX_SECONDS_PER_EVENT:
                status["minute_status"] = "timeout"
                status["minute_message"] = f"timeout_after_{MAX_SECONDS_PER_EVENT}s"
                break
            api.wait_update()
            if not api.is_changing(klines.iloc[-1], "datetime"):
                continue
            item = klines.iloc[-1].to_dict()
            bar_id = int(item.get("id", -1))
            if bar_id in seen_ids:
                continue
            seen_ids.add(bar_id)
            bar_dt = _normalize_tqsdk_datetime(item.get("datetime"))
            if pd.isna(bar_dt):
                continue
            rows.append(
                {
                    "event_key": row["event_key"],
                    "vt_symbol": row["vt_symbol"],
                    "tq_symbol": row["tq_symbol"],
                    "bar_datetime": bar_dt,
                    "bar_id": bar_id,
                    "open": float(item.get("open", np.nan)),
                    "high": float(item.get("high", np.nan)),
                    "low": float(item.get("low", np.nan)),
                    "close": float(item.get("close", np.nan)),
                    "volume": float(item.get("volume", np.nan)),
                    "open_oi": float(item.get("open_oi", np.nan)),
                    "close_oi": float(item.get("close_oi", np.nan)),
                }
            )
    except BacktestFinished:
        status["minute_status"] = "extracted"
    except Exception as exc:
        status["minute_status"] = "failed"
        status["minute_message"] = repr(exc)[:500]
    finally:
        if api is not None:
            api.close()

    data = pd.DataFrame(rows)
    if not data.empty:
        data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
        data = data.dropna(subset=["bar_datetime"])
        data = data.drop_duplicates(["event_key", "bar_datetime"]).sort_values(["event_key", "bar_datetime"])
        data.to_csv(minute_path, index=False, encoding="utf-8-sig")
    if status["minute_status"] == "unknown":
        status["minute_status"] = "extracted" if not data.empty else "empty"
    return _evaluate_minute(row, data, status), data


def _evaluate_minute(row: pd.Series, data: pd.DataFrame, status: dict[str, Any]) -> dict[str, Any]:
    if data.empty or "bar_datetime" not in data.columns:
        status["minute_rows"] = 0
        return status
    data = data.copy()
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    data = data.dropna(subset=["bar_datetime"])
    event_ts = _timestamp(row["reentry_time"])
    status["minute_rows"] = int(len(data))
    exact = data[data["bar_datetime"].eq(event_ts)]
    if exact.empty:
        status["minute_exact_ready"] = 0
        return status
    item = exact.iloc[0]
    high = float(pd.to_numeric(pd.Series([item.get("high")]), errors="coerce").iloc[0])
    low = float(pd.to_numeric(pd.Series([item.get("low")]), errors="coerce").iloc[0])
    volume = float(pd.to_numeric(pd.Series([item.get("volume")]), errors="coerce").iloc[0])
    bar_range = high - low if np.isfinite(high) and np.isfinite(low) else np.nan
    status["minute_exact_ready"] = 1
    status["minute_bar_range"] = bar_range
    status["minute_volume"] = volume
    status["minute_ohlcv_ready"] = int(np.isfinite(bar_range) and bar_range > 0 and np.isfinite(volume) and volume > 0)
    return status


def _extract_ticks(row: pd.Series, username: str, password: str) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    _, tick_path = _raw_paths(row)
    tick_path.parent.mkdir(parents=True, exist_ok=True)
    status: dict[str, Any] = {
        "tick_status": "unknown",
        "tick_rows": 0,
        "tick_target_rows": 0,
        "tick_rebuilt_ready": 0,
        "tick_rebuilt_range": np.nan,
        "tick_rebuilt_volume_delta": np.nan,
        "tick_path": str(tick_path),
        "tick_message": "",
    }
    if tick_path.exists() and tick_path.stat().st_size > 0:
        try:
            cached = pd.read_csv(tick_path, encoding="utf-8-sig")
            status["tick_status"] = "cached"
            rebuilt = _rebuild_tick_minute(row, cached, status)
            return status, cached, rebuilt
        except Exception as exc:
            status["tick_message"] = f"cached_read_failed:{type(exc).__name__}:{exc}"

    try:
        from tqsdk import BacktestFinished, TqApi, TqAuth, TqBacktest, TqSim
    except Exception as exc:
        status["tick_status"] = "import_failed"
        status["tick_message"] = repr(exc)[:500]
        return status, pd.DataFrame(), pd.DataFrame()

    event_ts = _timestamp(row["reentry_time"])
    start_dt = event_ts - pd.Timedelta(minutes=TICK_WINDOW_MINUTES)
    end_dt = event_ts + pd.Timedelta(minutes=TICK_WINDOW_MINUTES + 1)
    started = time.time()
    rows: list[dict[str, Any]] = []
    seen_keys: set[tuple[Any, Any]] = set()
    api = None
    try:
        api = TqApi(
            TqSim(),
            backtest=TqBacktest(start_dt=start_dt.to_pydatetime(), end_dt=end_dt.to_pydatetime()),
            auth=TqAuth(username, password),
            disable_print=True,
        )
        ticks = api.get_tick_serial(str(row["tq_symbol"]), data_length=TICK_DATA_LENGTH)
        while True:
            if time.time() - started > MAX_SECONDS_PER_EVENT:
                status["tick_status"] = "timeout"
                status["tick_message"] = f"timeout_after_{MAX_SECONDS_PER_EVENT}s"
                break
            api.wait_update()
            if not api.is_changing(ticks.iloc[-1], "datetime"):
                continue
            item = ticks.iloc[-1].to_dict()
            tick_dt = _normalize_tqsdk_datetime(item.get("datetime"))
            if pd.isna(tick_dt):
                continue
            key = (item.get("datetime"), item.get("last_price"))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            record = {"event_key": row["event_key"], "vt_symbol": row["vt_symbol"], "tq_symbol": row["tq_symbol"], "tick_datetime": tick_dt}
            for key_name, value in item.items():
                if key_name == "datetime":
                    continue
                record[str(key_name)] = value
            rows.append(record)
    except BacktestFinished:
        status["tick_status"] = "extracted"
    except Exception as exc:
        status["tick_status"] = "failed"
        status["tick_message"] = repr(exc)[:500]
    finally:
        if api is not None:
            api.close()

    ticks = pd.DataFrame(rows)
    if not ticks.empty:
        ticks["tick_datetime"] = pd.to_datetime(ticks["tick_datetime"], errors="coerce")
        ticks = ticks.dropna(subset=["tick_datetime"])
        ticks = ticks.drop_duplicates(["event_key", "tick_datetime", "last_price"], keep="last")
        ticks = ticks.sort_values(["event_key", "tick_datetime"])
        ticks.to_csv(tick_path, index=False, encoding="utf-8-sig")
    if status["tick_status"] == "unknown":
        status["tick_status"] = "extracted" if not ticks.empty else "empty"
    rebuilt = _rebuild_tick_minute(row, ticks, status)
    return status, ticks, rebuilt


def _rebuild_tick_minute(row: pd.Series, ticks: pd.DataFrame, status: dict[str, Any]) -> pd.DataFrame:
    if ticks.empty or "tick_datetime" not in ticks.columns or "last_price" not in ticks.columns:
        status["tick_rows"] = int(len(ticks))
        return pd.DataFrame()
    data = ticks.copy()
    data["tick_datetime"] = pd.to_datetime(data["tick_datetime"], errors="coerce")
    data["last_price"] = pd.to_numeric(data["last_price"], errors="coerce")
    data = data.dropna(subset=["tick_datetime", "last_price"]).sort_values("tick_datetime")
    event_ts = _timestamp(row["reentry_time"])
    target_start, target_end = _target_minute_bounds(event_ts)
    target = data[(data["tick_datetime"] >= target_start) & (data["tick_datetime"] < target_end)].copy()
    status["tick_rows"] = int(len(data))
    status["tick_target_rows"] = int(len(target))
    if target.empty:
        return pd.DataFrame()
    volume_delta = np.nan
    if "volume" in data.columns:
        data["volume"] = pd.to_numeric(data["volume"], errors="coerce")
        target_volume = data[(data["tick_datetime"] >= target_start) & (data["tick_datetime"] < target_end)]["volume"].dropna()
        previous_volume = data[data["tick_datetime"] < target_start]["volume"].dropna()
        if not target_volume.empty:
            previous = float(previous_volume.iloc[-1]) if not previous_volume.empty else float(target_volume.iloc[0])
            volume_delta = max(0.0, float(target_volume.iloc[-1]) - previous)
    open_price = float(target["last_price"].iloc[0])
    high = float(target["last_price"].max())
    low = float(target["last_price"].min())
    close = float(target["last_price"].iloc[-1])
    bar_range = high - low
    rebuilt = pd.DataFrame(
        [
            {
                "event_key": row["event_key"],
                "vt_symbol": row["vt_symbol"],
                "tq_symbol": row["tq_symbol"],
                "bar_datetime": target_start,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "tick_count": int(len(target)),
                "volume_delta": volume_delta,
                "open_oi": float(pd.to_numeric(target.get("open_interest", pd.Series([np.nan])).head(1), errors="coerce").iloc[0])
                if "open_interest" in target.columns
                else np.nan,
                "close_oi": float(pd.to_numeric(target.get("open_interest", pd.Series([np.nan])).tail(1), errors="coerce").iloc[0])
                if "open_interest" in target.columns
                else np.nan,
                "bar_range": bar_range,
            }
        ]
    )
    status["tick_rebuilt_range"] = bar_range
    status["tick_rebuilt_volume_delta"] = volume_delta
    status["tick_rebuilt_ready"] = int(np.isfinite(bar_range) and bar_range > 0 and np.isfinite(volume_delta) and volume_delta > 0)
    return rebuilt


def _process_event(row: pd.Series, username: str, password: str, credential_status: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    if not ENABLE_TQSDK:
        return _empty_status(row, credential_status, "skipped_disabled"), pd.DataFrame(), pd.DataFrame()
    if not username or not password:
        return _empty_status(row, credential_status, "missing_credentials"), pd.DataFrame(), pd.DataFrame()
    base = {
        "event_key": row["event_key"],
        "vt_symbol": row["vt_symbol"],
        "tq_symbol": row["tq_symbol"],
        "reentry_time": row["reentry_time"],
        "entry_year": row["entry_year"],
        "quality_bucket": row["quality_bucket"],
        "reentry_lot_pnl": row["reentry_lot_pnl"],
        "credential_status": credential_status.get("status", ""),
    }
    minute_status, minute_bars = _extract_minute(row, username, password)
    tick_status, ticks, rebuilt = _extract_ticks(row, username, password)
    status = {**base, **minute_status, **tick_status}
    if status.get("minute_ohlcv_ready", 0):
        final = "minute_ohlcv_ready"
    elif status.get("tick_rebuilt_ready", 0):
        final = "tick_rebuilt_ready"
    elif status.get("minute_exact_ready", 0):
        final = "minute_exact_but_not_ohlcv_ready"
    elif status.get("tick_target_rows", 0):
        final = "tick_target_but_not_ohlcv_ready"
    else:
        final = "unresolved_after_tqsdk_backtest"
    status["final_refill_status"] = final
    messages = [str(status.get("minute_message", "")), str(status.get("tick_message", ""))]
    status["message"] = " | ".join(item for item in messages if item)
    return status, minute_bars, rebuilt


def _contribution_curve(curve: pd.DataFrame, status: pd.DataFrame) -> pd.DataFrame:
    out = curve[["date", "account_equity", "official_drawdown_pct", "broker10_margin_to_equity_pct"]].copy()
    events = status.copy()
    events["event_day"] = pd.to_datetime(events["reentry_time"], errors="coerce").dt.normalize()
    events["minute_ready_pnl"] = np.where(events["final_refill_status"].eq("minute_ohlcv_ready"), events["reentry_lot_pnl"], 0.0)
    events["tick_ready_pnl"] = np.where(events["final_refill_status"].eq("tick_rebuilt_ready"), events["reentry_lot_pnl"], 0.0)
    events["still_unresolved_pnl"] = np.where(
        ~events["final_refill_status"].isin(["minute_ohlcv_ready", "tick_rebuilt_ready"]),
        events["reentry_lot_pnl"],
        0.0,
    )
    daily = (
        events.groupby("event_day", dropna=False)[["minute_ready_pnl", "tick_ready_pnl", "still_unresolved_pnl"]]
        .sum()
        .reset_index()
        .rename(columns={"event_day": "date"})
    )
    out = out.merge(daily, on="date", how="left")
    for column in ["minute_ready_pnl", "tick_ready_pnl", "still_unresolved_pnl"]:
        out[column] = out[column].fillna(0.0)
        out[f"cum_{column}"] = out[column].cumsum()
    return out


def _plot_path(curve: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=True, gridspec_kw={"height_ratios": [2, 1, 1]})
    axes[0].plot(curve["date"], curve["account_equity"], lw=1.4, color="#1f77b4", label="official equity")
    axes[0].set_yscale("log")
    axes[0].set_title("Stage057 TqBacktest minute/tick refill attribution")
    axes[0].set_ylabel("equity log")
    axes[0].legend(loc="upper left")
    axes[1].plot(curve["date"], curve["cum_minute_ready_pnl"], lw=1.3, color="#2ca02c", label="minute-ready refill PnL")
    axes[1].plot(curve["date"], curve["cum_tick_ready_pnl"], lw=1.3, color="#17becf", label="tick-ready refill PnL")
    axes[1].plot(curve["date"], curve["cum_still_unresolved_pnl"], lw=1.3, color="#d62728", label="still unresolved PnL")
    axes[1].axhline(0, lw=0.8, color="#555555")
    axes[1].legend(loc="upper left")
    axes[1].set_ylabel("PnL")
    axes[2].plot(curve["date"], curve["official_drawdown_pct"], lw=1.1, color="#8c564b", label="official DD %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], lw=1.1, color="#9467bd", label="broker10 %")
    axes[2].axhline(-40, color="#8c564b", ls="--", lw=0.8)
    axes[2].axhline(100, color="#9467bd", ls="--", lw=0.8)
    axes[2].legend(loc="upper left")
    axes[2].set_ylabel("pct")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_events(status: pd.DataFrame) -> None:
    data = status.sort_values("reentry_lot_pnl").copy()
    color_map = {
        "minute_ohlcv_ready": "#2ca02c",
        "tick_rebuilt_ready": "#17becf",
        "minute_exact_but_not_ohlcv_ready": "#ff7f0e",
        "tick_target_but_not_ohlcv_ready": "#9467bd",
        "unresolved_after_tqsdk_backtest": "#d62728",
    }
    colors = [color_map.get(item, "#7f7f7f") for item in data["final_refill_status"].astype(str)]
    labels = data["vt_symbol"].astype(str) + "\n" + pd.to_datetime(data["reentry_time"]).dt.strftime("%Y-%m-%d %H:%M")
    fig, ax = plt.subplots(figsize=(15, 9))
    ax.bar(np.arange(len(data)), data["reentry_lot_pnl"], color=colors)
    ax.axhline(0, color="#333333", lw=0.8)
    ax.set_xticks(np.arange(len(data)))
    ax.set_xticklabels(labels, rotation=75, ha="right", fontsize=8)
    ax.set_ylabel("reentry lot PnL")
    ax.set_title("Stage057 refill events by final status")
    fig.tight_layout()
    fig.savefig(EVENT_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_status(status: pd.DataFrame) -> None:
    counts = status["final_refill_status"].value_counts().sort_values(ascending=True)
    pnl = status.groupby("final_refill_status")["reentry_lot_pnl"].sum().reindex(counts.index)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    axes[0].barh(counts.index, counts.values, color="#1f77b4")
    axes[0].set_title("event count")
    axes[1].barh(pnl.index, pnl.values, color=np.where(pnl.values >= 0, "#2ca02c", "#d62728"))
    axes[1].axvline(0, color="#333333", lw=0.8)
    axes[1].set_title("reentry PnL")
    fig.suptitle("Stage057 final refill status")
    fig.tight_layout()
    fig.savefig(STATUS_CHART_OUT, dpi=150)
    plt.close(fig)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    display = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    lines = [
        "| " + " | ".join(str(column) for column in display.columns) + " |",
        "| " + " | ".join(["---"] * len(display.columns)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in display.columns) + " |")
    return "\n".join(lines)


def _write_report(decision: dict[str, Any], status: pd.DataFrame) -> None:
    status_view = status[
        [
            "event_key",
            "vt_symbol",
            "reentry_time",
            "reentry_lot_pnl",
            "minute_status",
            "minute_exact_ready",
            "minute_ohlcv_ready",
            "tick_status",
            "tick_target_rows",
            "tick_rebuilt_ready",
            "final_refill_status",
        ]
    ].sort_values("reentry_lot_pnl", ascending=False)
    lines = [
        "# Stage057 reentry gap TqBacktest refill report",
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- candidate_like: `{decision['candidate_like']}`",
        f"- processed events: `{decision['processed_event_count']}`",
        f"- minute OHLCV ready: `{decision['minute_ohlcv_ready_event_count']}`",
        f"- tick rebuilt ready: `{decision['tick_rebuilt_ready_event_count']}`",
        f"- still unresolved: `{decision['still_unresolved_event_count']}`",
        f"- still unresolved PnL: `{decision['still_unresolved_reentry_pnl']:.2f}`",
        "",
        "## Credential Status",
        "",
        _md_table(pd.DataFrame([decision["credential_status"]])),
        "",
        "## Event Status",
        "",
        _md_table(status_view, 40),
        "",
        "## Visual Outputs",
        "",
        f"- path chart: `{PATH_CHART_OUT}`",
        f"- event chart: `{EVENT_CHART_OUT}`",
        f"- status chart: `{STATUS_CHART_OUT}`",
        "",
        "## Judgment",
        "",
        decision["judgment"],
        "",
    ]
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_MINUTE_DIR.mkdir(parents=True, exist_ok=True)
    RAW_TICK_DIR.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest()
    username, password, credential_status = _get_credentials()
    status_rows: list[dict[str, Any]] = []
    minute_frames: list[pd.DataFrame] = []
    rebuilt_frames: list[pd.DataFrame] = []
    for _, row in manifest.iterrows():
        status, minute_bars, rebuilt = _process_event(row, username, password, credential_status)
        status_rows.append(status)
        if not minute_bars.empty:
            minute_frames.append(minute_bars)
        if not rebuilt.empty:
            rebuilt_frames.append(rebuilt)
    status = pd.DataFrame(status_rows)
    minute_bars = pd.concat(minute_frames, ignore_index=True, sort=False) if minute_frames else pd.DataFrame()
    rebuilt_bars = pd.concat(rebuilt_frames, ignore_index=True, sort=False) if rebuilt_frames else pd.DataFrame()

    curve = _read_csv(CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "official_drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    contrib_curve = _contribution_curve(curve, status)

    ready_statuses = ["minute_ohlcv_ready", "tick_rebuilt_ready"]
    ready = status[status["final_refill_status"].isin(ready_statuses)]
    unresolved = status[~status["final_refill_status"].isin(ready_statuses)]
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": "stage057_tqsdk_backtest_refill_data_audit_no_trade_rule",
        "candidate_like": False,
        "credential_status": credential_status,
        "processed_event_count": int(len(status)),
        "minute_ohlcv_ready_event_count": int(status["minute_ohlcv_ready"].fillna(0).astype(int).sum()) if not status.empty else 0,
        "tick_rebuilt_ready_event_count": int(status["tick_rebuilt_ready"].fillna(0).astype(int).sum()) if not status.empty else 0,
        "final_ready_event_count": int(len(ready)),
        "final_ready_reentry_pnl": float(ready["reentry_lot_pnl"].sum()) if not ready.empty else 0.0,
        "still_unresolved_event_count": int(len(unresolved)),
        "still_unresolved_reentry_pnl": float(unresolved["reentry_lot_pnl"].sum()) if not unresolved.empty else 0.0,
        "still_unresolved_positive_pnl": float(unresolved.loc[unresolved["reentry_lot_pnl"] > 0, "reentry_lot_pnl"].sum())
        if not unresolved.empty
        else 0.0,
        "still_unresolved_negative_pnl_abs": float(-unresolved.loc[unresolved["reentry_lot_pnl"] < 0, "reentry_lot_pnl"].sum())
        if not unresolved.empty
        else 0.0,
        "judgment": (
            "TqBacktest minute/tick refill is data engineering evidence only. A ready bar proves data "
            "availability, not signal quality; an unresolved or zero-volume bar must not be used as a "
            "trade filter because Stage056 showed unresolved gaps carry large right-tail PnL."
        ),
        "outputs": {
            "event_status_csv": EVENT_STATUS_OUT,
            "minute_bars_csv": MINUTE_BARS_OUT,
            "tick_rebuilt_bars_csv": TICK_REBUILT_BARS_OUT,
            "contribution_curve_csv": CONTRIB_CURVE_OUT,
            "path_chart_png": PATH_CHART_OUT,
            "event_chart_png": EVENT_CHART_OUT,
            "status_chart_png": STATUS_CHART_OUT,
            "decision_json": DECISION_OUT,
            "report_md": REPORT_OUT,
            "raw_minute_dir": RAW_MINUTE_DIR,
            "raw_tick_dir": RAW_TICK_DIR,
        },
    }

    status.to_csv(EVENT_STATUS_OUT, index=False, encoding="utf-8-sig")
    minute_bars.to_csv(MINUTE_BARS_OUT, index=False, encoding="utf-8-sig")
    rebuilt_bars.to_csv(TICK_REBUILT_BARS_OUT, index=False, encoding="utf-8-sig")
    contrib_curve.to_csv(CONTRIB_CURVE_OUT, index=False, encoding="utf-8-sig")
    _plot_path(contrib_curve)
    _plot_events(status)
    _plot_status(status)
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, status)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
