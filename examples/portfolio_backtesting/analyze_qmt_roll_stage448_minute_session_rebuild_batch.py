from __future__ import annotations

import json
import logging
import math
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from tqsdk import BacktestFinished, TqApi, TqAuth, TqBacktest, TqSim
from vnpy.trader.setting import SETTINGS
from vnpy.trader.utility import ZoneInfo


logging.getLogger().setLevel(logging.WARNING)
logging.getLogger("tqsdk").setLevel(logging.WARNING)

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
RAW_ROOT = PROJECT_DIR / "downloaded_futures" / os.getenv(
    "STAGE448_RAW_SUBDIR", "tqsdk_stage448_minute_session_rebuild_batch"
)

MODEL_TAG = os.getenv("STAGE448_MODEL_TAG", "stage448_minute_session_rebuild_batch_v1")
OUTPUT_PREFIX = os.getenv("STAGE448_OUTPUT_PREFIX", "qmt_roll_stage448_minute_session_rebuild_batch")
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE443_LEDGER_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage443_execution_proxy_calibration_trade_gap_ledger_stage443_execution_proxy_calibration_v1.csv"
)
REQUIRED_TARGETS_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage444_intraday_proxy_data_readiness_required_proxy_targets_stage444_intraday_proxy_data_readiness_v1.csv"
)
PRIORITY_TARGETS_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage444_intraday_proxy_data_readiness_priority_targets_stage444_intraday_proxy_data_readiness_v1.csv"
)
SYMBOL_PLAN_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage444_intraday_proxy_data_readiness_symbol_download_plan_stage444_intraday_proxy_data_readiness_v1.csv"
)
STAGE446_BARS_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage446_tqsdk_backtest_minute_proxy_extract_minute_bars_stage446_tqsdk_backtest_minute_proxy_extract_v1.csv"
)

STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_extract_status_{MODEL_TAG}.csv"
BARS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_minute_bars_{MODEL_TAG}.csv"
COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_coverage_{MODEL_TAG}.csv"
PROXY_PRICE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_prices_{MODEL_TAG}.csv"
DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ledger_proxy_detail_{MODEL_TAG}.csv"
METRIC_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_metric_summary_{MODEL_TAG}.csv"
SYMBOL_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_symbol_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

CHINA_TZ = ZoneInfo("Asia/Shanghai")
TARGET_SCOPE = os.getenv("STAGE448_TARGET_SCOPE", "high").strip().lower()
MAX_SYMBOLS = int(os.getenv("STAGE448_MAX_SYMBOLS", "20"))
SYMBOL_OFFSET = int(os.getenv("STAGE448_SYMBOL_OFFSET", "0"))
MAX_SECONDS_PER_SYMBOL = int(os.getenv("STAGE448_MAX_SECONDS_PER_SYMBOL", "150"))
START_PADDING_MINUTES = int(os.getenv("STAGE448_START_PADDING_MINUTES", "10"))
END_PADDING_MINUTES = int(os.getenv("STAGE448_END_PADDING_MINUTES", "10"))
FORCE_REFRESH = os.getenv("STAGE448_FORCE_REFRESH", "0").strip() == "1"

NIGHT_SESSION_CLASS = "night_session_next_trade_day_open_proxy"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return view.to_markdown(index=False)


def _require_credentials() -> tuple[str, str]:
    username = str(SETTINGS.get("datafeed.username", ""))
    password = str(SETTINGS.get("datafeed.password", ""))
    if not username or not password:
        raise RuntimeError("TqSdk credentials are missing in vn.py SETTINGS.")
    return username, password


def _to_tqsdk_symbol(vt_symbol: str) -> str:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return f"{exchange}.{symbol}"


def _load_targets() -> pd.DataFrame:
    if TARGET_SCOPE == "all":
        path = REQUIRED_TARGETS_PATH
    else:
        path = PRIORITY_TARGETS_PATH
    targets = pd.read_csv(path, encoding="utf-8-sig")
    for column in ["decision_date", "next_trade_date", "target_start", "target_end"]:
        targets[column] = pd.to_datetime(targets[column], errors="coerce").dt.tz_localize(None)
    targets["abs_next_open_adverse_cash"] = pd.to_numeric(
        targets.get("abs_next_open_adverse_cash", 0.0), errors="coerce"
    ).fillna(0.0)
    targets["calendar_validation_required"] = pd.to_numeric(
        targets.get("calendar_validation_required", 0), errors="coerce"
    ).fillna(0).astype(int)
    return targets.dropna(subset=["vt_symbol", "target_start", "target_end"]).copy()


def _load_plan() -> pd.DataFrame:
    if not SYMBOL_PLAN_PATH.exists():
        return pd.DataFrame(columns=["vt_symbol", "suggested_tqsdk_symbol"])
    plan = pd.read_csv(SYMBOL_PLAN_PATH, encoding="utf-8-sig")
    if "suggested_tqsdk_symbol" not in plan.columns:
        plan["suggested_tqsdk_symbol"] = plan["vt_symbol"].map(_to_tqsdk_symbol)
    return plan


def _load_seed_bars() -> pd.DataFrame:
    if not STAGE446_BARS_PATH.exists():
        return pd.DataFrame()
    bars = pd.read_csv(STAGE446_BARS_PATH, encoding="utf-8-sig")
    if bars.empty:
        return bars
    bars["bar_datetime"] = pd.to_datetime(bars["bar_datetime"], errors="coerce").dt.tz_localize(None)
    return bars.dropna(subset=["vt_symbol", "bar_datetime"]).copy()


def _selected_symbols(targets: pd.DataFrame, plan: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        targets.groupby(["vt_symbol", "product_vt_symbol"], sort=True)
        .agg(
            target_start=("target_start", "min"),
            target_end=("target_end", "max"),
            target_count=("trade_id", "count"),
            unique_trades=("trade_id", "nunique"),
            max_abs_next_open_adverse_cash=("abs_next_open_adverse_cash", "max"),
            sum_abs_next_open_adverse_cash=("abs_next_open_adverse_cash", "sum"),
            calendar_validation_targets=("calendar_validation_required", "sum"),
        )
        .reset_index()
    )
    if not plan.empty:
        grouped = grouped.merge(plan[["vt_symbol", "suggested_tqsdk_symbol"]], on="vt_symbol", how="left")
    grouped["suggested_tqsdk_symbol"] = grouped["suggested_tqsdk_symbol"].fillna(
        grouped["vt_symbol"].map(_to_tqsdk_symbol)
    )
    grouped = grouped.sort_values(
        ["target_count", "max_abs_next_open_adverse_cash", "sum_abs_next_open_adverse_cash"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    grouped["selection_rank"] = np.arange(1, len(grouped) + 1)
    if SYMBOL_OFFSET > 0:
        grouped = grouped.iloc[SYMBOL_OFFSET:].copy()
    if MAX_SYMBOLS > 0:
        grouped = grouped.head(MAX_SYMBOLS).copy()
    return grouped.reset_index(drop=True)


def _normalize_tqsdk_datetime(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, unit="ns", errors="coerce", utc=True)
    if pd.isna(ts):
        return pd.NaT
    return ts.tz_convert(CHINA_TZ).tz_localize(None)


def _raw_path_for(tq_symbol: str) -> Path:
    exchange, symbol = tq_symbol.split(".", 1)
    return RAW_ROOT / exchange / f"{symbol}_minute_backtest.csv"


def _seed_covers(seed: pd.DataFrame, vt_symbol: str, start_dt: pd.Timestamp, end_dt: pd.Timestamp) -> bool:
    if seed.empty:
        return False
    bars = seed[seed["vt_symbol"].astype(str).eq(vt_symbol)].copy()
    if bars.empty:
        return False
    return bars["bar_datetime"].min() <= start_dt and bars["bar_datetime"].max() >= (end_dt - timedelta(minutes=1))


def _load_raw_if_covered(path: Path, vt_symbol: str, start_dt: pd.Timestamp, end_dt: pd.Timestamp) -> pd.DataFrame:
    if FORCE_REFRESH or not path.exists():
        return pd.DataFrame()
    bars = pd.read_csv(path, encoding="utf-8-sig")
    if bars.empty:
        return bars
    bars["bar_datetime"] = pd.to_datetime(bars["bar_datetime"], errors="coerce").dt.tz_localize(None)
    bars = bars.dropna(subset=["bar_datetime"])
    if bars.empty:
        return bars
    bars["vt_symbol"] = vt_symbol
    return bars


def _extract_symbol(row: Any, username: str, password: str, seed: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]:
    vt_symbol = str(row.vt_symbol)
    tq_symbol = str(row.suggested_tqsdk_symbol)
    start_dt = pd.Timestamp(row.target_start) - timedelta(minutes=START_PADDING_MINUTES)
    end_dt = pd.Timestamp(row.target_end) + timedelta(minutes=END_PADDING_MINUTES)
    raw_path = _raw_path_for(tq_symbol)
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    status = {
        "selection_rank": int(row.selection_rank),
        "vt_symbol": vt_symbol,
        "tq_symbol": tq_symbol,
        "extract_start": start_dt,
        "extract_end": end_dt,
        "target_count": int(row.target_count),
        "unique_trades": int(row.unique_trades),
        "max_abs_next_open_adverse_cash": float(row.max_abs_next_open_adverse_cash),
        "sum_abs_next_open_adverse_cash": float(row.sum_abs_next_open_adverse_cash),
        "calendar_validation_targets": int(row.calendar_validation_targets),
        "raw_path": str(raw_path),
        "status": "unknown",
        "rows": 0,
        "elapsed_seconds": 0.0,
        "message": "",
    }

    cached = _load_raw_if_covered(raw_path, vt_symbol, start_dt, end_dt)
    if not cached.empty:
        status["status"] = "cached_raw"
        status["rows"] = int(len(cached))
        return status, cached

    if _seed_covers(seed, vt_symbol, start_dt, end_dt):
        bars = seed[seed["vt_symbol"].astype(str).eq(vt_symbol)].copy()
        bars.to_csv(raw_path, index=False, encoding="utf-8-sig")
        status["status"] = "seed_stage446"
        status["rows"] = int(len(bars))
        return status, bars

    started = time.time()
    rows: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    api: TqApi | None = None
    try:
        api = TqApi(
            TqSim(),
            backtest=TqBacktest(start_dt=start_dt.to_pydatetime(), end_dt=end_dt.to_pydatetime()),
            auth=TqAuth(username, password),
        )
        klines = api.get_kline_serial(tq_symbol, duration_seconds=60, data_length=500)
        while True:
            if time.time() - started > MAX_SECONDS_PER_SYMBOL:
                status["status"] = "timeout"
                status["message"] = f"timeout_after_{MAX_SECONDS_PER_SYMBOL}s"
                break
            api.wait_update()
            if not api.is_changing(klines.iloc[-1], "datetime"):
                continue
            bar = klines.iloc[-1].to_dict()
            bar_id = int(bar.get("id", -1))
            if bar_id in seen_ids:
                continue
            seen_ids.add(bar_id)
            bar_dt = _normalize_tqsdk_datetime(bar.get("datetime"))
            if pd.isna(bar_dt):
                continue
            rows.append(
                {
                    "vt_symbol": vt_symbol,
                    "tq_symbol": tq_symbol,
                    "bar_datetime": bar_dt,
                    "bar_id": bar_id,
                    "open": float(bar.get("open", np.nan)),
                    "high": float(bar.get("high", np.nan)),
                    "low": float(bar.get("low", np.nan)),
                    "close": float(bar.get("close", np.nan)),
                    "volume": float(bar.get("volume", np.nan)),
                    "open_oi": float(bar.get("open_oi", np.nan)),
                    "close_oi": float(bar.get("close_oi", np.nan)),
                }
            )
    except BacktestFinished:
        status["status"] = "extracted"
    except Exception as exc:
        status["status"] = "failed"
        status["message"] = repr(exc)
    finally:
        if api is not None:
            api.close()

    bars = pd.DataFrame(rows)
    if not bars.empty:
        bars = bars.drop_duplicates(["vt_symbol", "bar_datetime"]).sort_values(["vt_symbol", "bar_datetime"])
        bars.to_csv(raw_path, index=False, encoding="utf-8-sig")
    if status["status"] == "unknown":
        status["status"] = "extracted" if len(bars) else "empty"
    status["rows"] = int(len(bars))
    status["elapsed_seconds"] = round(time.time() - started, 2)
    return status, bars


def _coverage_for_targets(targets: pd.DataFrame, bars: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if bars.empty:
        bars = pd.DataFrame(columns=["vt_symbol", "bar_datetime", "open", "high", "low", "close", "volume"])
    bars = bars.copy()
    bars["bar_datetime"] = pd.to_datetime(bars["bar_datetime"], errors="coerce").dt.tz_localize(None)
    bars = bars.dropna(subset=["bar_datetime"])
    grouped = {symbol: frame.sort_values("bar_datetime") for symbol, frame in bars.groupby("vt_symbol", sort=False)}

    coverage_rows: list[dict[str, Any]] = []
    proxy_rows: list[dict[str, Any]] = []
    for row in targets.itertuples(index=False):
        vt_symbol = str(row.vt_symbol)
        frame = grouped.get(vt_symbol, pd.DataFrame())
        start = pd.Timestamp(row.target_start)
        end = pd.Timestamp(row.target_end)
        in_window = (
            frame[(frame["bar_datetime"] >= start) & (frame["bar_datetime"] < end)].copy()
            if not frame.empty
            else pd.DataFrame()
        )
        count = int(len(in_window))
        first_bar = in_window.iloc[0].to_dict() if count else {}
        last_bar = in_window.iloc[-1].to_dict() if count else {}
        coverage_rows.append(
            {
                "trade_id": str(row.trade_id),
                "vt_symbol": vt_symbol,
                "product_vt_symbol": str(row.product_vt_symbol),
                "proxy_type": str(row.proxy_type),
                "target_start": start,
                "target_end": end,
                "abs_next_open_adverse_cash": float(row.abs_next_open_adverse_cash),
                "calendar_validation_required": int(row.calendar_validation_required),
                "minute_bar_count": count,
                "covered": int(count > 0),
                "first_bar_datetime": first_bar.get("bar_datetime", ""),
                "first_open": first_bar.get("open", np.nan),
                "first_close": first_bar.get("close", np.nan),
                "last_bar_datetime": last_bar.get("bar_datetime", ""),
                "last_open": last_bar.get("open", np.nan),
                "last_close": last_bar.get("close", np.nan),
            }
        )
        if count:
            volume_sum = float(pd.to_numeric(in_window["volume"], errors="coerce").fillna(0.0).sum())
            close_series = pd.to_numeric(in_window["close"], errors="coerce")
            proxy_rows.append(
                {
                    "trade_id": str(row.trade_id),
                    "vt_symbol": vt_symbol,
                    "product_vt_symbol": str(row.product_vt_symbol),
                    "proxy_type": str(row.proxy_type),
                    "proxy_bar_count": count,
                    "proxy_first_time": first_bar.get("bar_datetime", ""),
                    "proxy_first_open": first_bar.get("open", np.nan),
                    "proxy_first_close": first_bar.get("close", np.nan),
                    "proxy_last_time": last_bar.get("bar_datetime", ""),
                    "proxy_last_open": last_bar.get("open", np.nan),
                    "proxy_last_close": last_bar.get("close", np.nan),
                    "proxy_vwap_like": (
                        float((close_series * in_window["volume"]).sum() / volume_sum)
                        if volume_sum > 0
                        else float(close_series.mean())
                    ),
                }
            )
    return pd.DataFrame(coverage_rows), pd.DataFrame(proxy_rows)


def _pivot_proxy(proxy: pd.DataFrame) -> pd.DataFrame:
    if proxy.empty:
        return pd.DataFrame(columns=["trade_id"])
    fields = ["proxy_first_open", "proxy_first_close", "proxy_last_close", "proxy_vwap_like"]
    parts: list[pd.DataFrame] = []
    for field in fields:
        part = proxy.pivot_table(index="trade_id", columns="proxy_type", values=field, aggfunc="first")
        part.columns = [f"{column}_{field}" for column in part.columns]
        parts.append(part)
    return pd.concat(parts, axis=1).reset_index()


def _side_pnl_multiplier(direction: str, offset: str) -> int:
    direction = str(direction)
    offset = str(offset)
    sell_like = (direction == "Short" and offset == "Open") or (direction == "Long" and offset == "Close")
    return 1 if sell_like else -1


def _pnl_delta(row: pd.Series, price_column: str, base_column: str = "same_day_close") -> float:
    price = row.get(price_column, np.nan)
    base = row.get(base_column, np.nan)
    if pd.isna(price) or pd.isna(base):
        return np.nan
    multiplier = _side_pnl_multiplier(str(row.direction), str(row.offset))
    return float(multiplier * (float(price) - float(base)) * float(row.volume) * float(row.size))


def _load_ledger() -> pd.DataFrame:
    ledger = pd.read_csv(STAGE443_LEDGER_PATH, encoding="utf-8-sig")
    for column in ["date", "next_trade_date"]:
        ledger[column] = pd.to_datetime(ledger[column], errors="coerce")
    for column in [
        "same_day_close",
        "next_open",
        "next_close",
        "volume",
        "size",
        "price_tick",
        "next_open_adverse_cash",
    ]:
        ledger[column] = pd.to_numeric(ledger[column], errors="coerce")
    ledger["abs_next_open_adverse_cash"] = ledger["next_open_adverse_cash"].abs()
    ledger["trade_id"] = ledger["trade_id"].astype(str)
    return ledger


def _build_detail(ledger: pd.DataFrame, proxy: pd.DataFrame) -> pd.DataFrame:
    proxy_wide = _pivot_proxy(proxy)
    selected_ids = set(proxy["trade_id"].astype(str)) if not proxy.empty else set()
    detail = ledger[ledger["trade_id"].astype(str).isin(selected_ids)].copy()
    detail = detail.merge(proxy_wide, on="trade_id", how="left")

    detail["same_last5_vwap"] = detail.get("same_day_close_last_5m_proxy_vwap_like")
    detail["same_last5_first_open"] = detail.get("same_day_close_last_5m_proxy_first_open")
    detail["night_open_first"] = detail.get("night_session_open_2100_2105_proxy_first_open")
    detail["night_open_vwap"] = detail.get("night_session_open_2100_2105_proxy_vwap_like")
    detail["day_open_first"] = detail.get("day_session_open_0900_0905_proxy_first_open")
    detail["day_open_vwap"] = detail.get("day_session_open_0900_0905_proxy_vwap_like")

    detail["preferred_real_open_proxy"] = np.where(
        detail["session_proxy_class"].eq(NIGHT_SESSION_CLASS) & detail["night_open_first"].notna(),
        detail["night_open_first"],
        detail["day_open_first"],
    )
    detail["preferred_real_open_proxy_type"] = np.where(
        detail["session_proxy_class"].eq(NIGHT_SESSION_CLASS) & detail["night_open_first"].notna(),
        "night_session_open_2100_2105_first_open",
        "day_session_open_0900_0905_first_open",
    )
    detail.loc[detail["preferred_real_open_proxy"].isna(), "preferred_real_open_proxy_type"] = "missing_open_proxy"

    for column in [
        "same_last5_vwap",
        "same_last5_first_open",
        "night_open_first",
        "night_open_vwap",
        "day_open_first",
        "day_open_vwap",
        "preferred_real_open_proxy",
    ]:
        detail[f"{column}_minus_same_close"] = detail[column] - detail["same_day_close"]
        detail[f"{column}_pnl_delta_vs_same_close"] = detail.apply(_pnl_delta, axis=1, price_column=column)

    detail["preferred_real_open_minus_daily_next_open"] = detail["preferred_real_open_proxy"] - detail["next_open"]
    detail["preferred_real_open_abs_minus_daily_next_open"] = detail[
        "preferred_real_open_minus_daily_next_open"
    ].abs()
    detail["same_last5_abs_minus_same_close"] = (detail["same_last5_vwap"] - detail["same_day_close"]).abs()
    detail["preferred_real_open_abs_minus_same_close"] = (
        detail["preferred_real_open_proxy"] - detail["same_day_close"]
    ).abs()
    detail["daily_next_open_abs_minus_same_close"] = (detail["next_open"] - detail["same_day_close"]).abs()
    detail["valid_same_day_close"] = detail["same_day_close"].gt(0).astype(int)
    detail["valid_next_open"] = detail["next_open"].gt(0).astype(int)
    detail["same_last5_large_mismatch"] = (
        detail["valid_same_day_close"].eq(1)
        & (detail["same_last5_abs_minus_same_close"] >= detail["price_tick"].fillna(1) * 20)
    ).astype(int)
    detail["real_open_vs_daily_next_open_large_mismatch"] = (
        detail["valid_next_open"].eq(1)
        & (detail["preferred_real_open_abs_minus_daily_next_open"] >= detail["price_tick"].fillna(1) * 20)
    ).astype(int)
    return detail.sort_values(["abs_next_open_adverse_cash", "trade_id"], ascending=[False, True])


def _metric_summary(detail: pd.DataFrame, coverage: pd.DataFrame, status: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = [
        {
            "metric": "selected_symbol_count",
            "count": int(len(status)),
            "sum": np.nan,
            "mean": np.nan,
            "median": np.nan,
            "max_abs": np.nan,
            "p95_abs": np.nan,
        },
        {
            "metric": "target_window_count",
            "count": int(len(coverage)),
            "sum": float(len(coverage)),
            "mean": np.nan,
            "median": np.nan,
            "max_abs": np.nan,
            "p95_abs": np.nan,
        },
        {
            "metric": "covered_window_count",
            "count": int(coverage["covered"].sum()) if not coverage.empty else 0,
            "sum": float(coverage["covered"].sum()) if not coverage.empty else 0.0,
            "mean": float(coverage["covered"].mean()) if not coverage.empty else 0.0,
            "median": np.nan,
            "max_abs": np.nan,
            "p95_abs": np.nan,
        },
        {
            "metric": "detail_trade_count",
            "count": int(detail["trade_id"].nunique()) if not detail.empty else 0,
            "sum": np.nan,
            "mean": np.nan,
            "median": np.nan,
            "max_abs": np.nan,
            "p95_abs": np.nan,
        },
    ]
    for metric in [
        "same_last5_abs_minus_same_close",
        "preferred_real_open_abs_minus_daily_next_open",
        "preferred_real_open_abs_minus_same_close",
        "daily_next_open_abs_minus_same_close",
        "same_last5_vwap_pnl_delta_vs_same_close",
        "preferred_real_open_proxy_pnl_delta_vs_same_close",
        "night_open_first_pnl_delta_vs_same_close",
        "day_open_first_pnl_delta_vs_same_close",
    ]:
        if detail.empty or metric not in detail.columns:
            continue
        series = pd.to_numeric(detail[metric], errors="coerce").dropna()
        if series.empty:
            continue
        rows.append(
            {
                "metric": metric,
                "count": int(series.count()),
                "sum": float(series.sum()),
                "mean": float(series.mean()),
                "median": float(series.median()),
                "max_abs": float(series.abs().max()),
                "p95_abs": float(series.abs().quantile(0.95)),
            }
        )
    if not detail.empty:
        valid_same = detail[detail["valid_same_day_close"].eq(1)]
        valid_open = detail[detail["valid_next_open"].eq(1) & detail["preferred_real_open_proxy"].notna()]
        rows.extend(
            [
                {
                    "metric": "invalid_same_day_close_count",
                    "count": int((detail["valid_same_day_close"] == 0).sum()),
                    "sum": float((detail["valid_same_day_close"] == 0).sum()),
                    "mean": np.nan,
                    "median": np.nan,
                    "max_abs": np.nan,
                    "p95_abs": np.nan,
                },
                {
                    "metric": "invalid_next_open_count",
                    "count": int((detail["valid_next_open"] == 0).sum()),
                    "sum": float((detail["valid_next_open"] == 0).sum()),
                    "mean": np.nan,
                    "median": np.nan,
                    "max_abs": np.nan,
                    "p95_abs": np.nan,
                },
                {
                    "metric": "same_last5_large_mismatch_count",
                    "count": int(detail["same_last5_large_mismatch"].sum()),
                    "sum": float(detail["same_last5_large_mismatch"].sum()),
                    "mean": float(detail["same_last5_large_mismatch"].mean()),
                    "median": np.nan,
                    "max_abs": np.nan,
                    "p95_abs": np.nan,
                },
                {
                    "metric": "same_last5_large_mismatch_valid_rate",
                    "count": int(valid_same["same_last5_large_mismatch"].sum()),
                    "sum": float(valid_same["same_last5_large_mismatch"].sum()),
                    "mean": float(valid_same["same_last5_large_mismatch"].mean()) if not valid_same.empty else 0.0,
                    "median": np.nan,
                    "max_abs": float(valid_same["same_last5_abs_minus_same_close"].max()) if not valid_same.empty else np.nan,
                    "p95_abs": float(valid_same["same_last5_abs_minus_same_close"].quantile(0.95)) if not valid_same.empty else np.nan,
                },
                {
                    "metric": "real_open_vs_daily_next_open_large_mismatch_count",
                    "count": int(detail["real_open_vs_daily_next_open_large_mismatch"].sum()),
                    "sum": float(detail["real_open_vs_daily_next_open_large_mismatch"].sum()),
                    "mean": float(detail["real_open_vs_daily_next_open_large_mismatch"].mean()),
                    "median": np.nan,
                    "max_abs": np.nan,
                    "p95_abs": np.nan,
                },
                {
                    "metric": "real_open_vs_daily_next_open_large_mismatch_valid_rate",
                    "count": int(valid_open["real_open_vs_daily_next_open_large_mismatch"].sum()),
                    "sum": float(valid_open["real_open_vs_daily_next_open_large_mismatch"].sum()),
                    "mean": float(valid_open["real_open_vs_daily_next_open_large_mismatch"].mean()) if not valid_open.empty else 0.0,
                    "median": np.nan,
                    "max_abs": float(valid_open["preferred_real_open_abs_minus_daily_next_open"].max()) if not valid_open.empty else np.nan,
                    "p95_abs": float(valid_open["preferred_real_open_abs_minus_daily_next_open"].quantile(0.95)) if not valid_open.empty else np.nan,
                },
            ]
        )
    return pd.DataFrame(rows)


def _symbol_summary(status: pd.DataFrame, coverage: pd.DataFrame, detail: pd.DataFrame) -> pd.DataFrame:
    if status.empty:
        return pd.DataFrame()
    cov = (
        coverage.groupby("vt_symbol", sort=True)
        .agg(
            target_windows=("trade_id", "count"),
            covered_windows=("covered", "sum"),
            covered_trades=("trade_id", lambda s: coverage.loc[s.index, "trade_id"][coverage.loc[s.index, "covered"].eq(1)].nunique()),
        )
        .reset_index()
        if not coverage.empty
        else pd.DataFrame(columns=["vt_symbol", "target_windows", "covered_windows", "covered_trades"])
    )
    det = (
        detail.groupby("vt_symbol", sort=True)
        .agg(
            detail_trades=("trade_id", "nunique"),
            same_last5_large_mismatch=("same_last5_large_mismatch", "sum"),
            real_open_large_mismatch=("real_open_vs_daily_next_open_large_mismatch", "sum"),
            max_same_last5_abs=("same_last5_abs_minus_same_close", "max"),
            max_real_open_abs=("preferred_real_open_abs_minus_daily_next_open", "max"),
            preferred_real_open_cash_delta=("preferred_real_open_proxy_pnl_delta_vs_same_close", "sum"),
        )
        .reset_index()
        if not detail.empty
        else pd.DataFrame(columns=["vt_symbol"])
    )
    out = status.merge(cov, on="vt_symbol", how="left").merge(det, on="vt_symbol", how="left")
    out["window_coverage_rate"] = out["covered_windows"] / out["target_windows"]
    return out.sort_values(["selection_rank", "vt_symbol"])


def _decision(status: pd.DataFrame, coverage: pd.DataFrame, detail: pd.DataFrame) -> dict[str, Any]:
    target_windows = int(len(coverage))
    covered_windows = int(coverage["covered"].sum()) if target_windows else 0
    covered_rate = float(covered_windows / target_windows) if target_windows else 0.0
    detail_trades = int(detail["trade_id"].nunique()) if not detail.empty else 0
    valid_same = detail[detail["valid_same_day_close"].eq(1)] if not detail.empty else pd.DataFrame()
    valid_open = (
        detail[detail["valid_next_open"].eq(1) & detail["preferred_real_open_proxy"].notna()]
        if not detail.empty
        else pd.DataFrame()
    )
    same_large = int(detail["same_last5_large_mismatch"].sum()) if not detail.empty else 0
    open_large = int(detail["real_open_vs_daily_next_open_large_mismatch"].sum()) if not detail.empty else 0
    valid_same_count = int(valid_same["trade_id"].nunique()) if not valid_same.empty else 0
    valid_open_count = int(valid_open["trade_id"].nunique()) if not valid_open.empty else 0
    same_large_rate = float(same_large / valid_same_count) if valid_same_count else 0.0
    open_large_rate = float(open_large / valid_open_count) if valid_open_count else 0.0
    valid_same_with_open = (
        detail[detail["valid_same_day_close"].eq(1) & detail["preferred_real_open_proxy"].notna()]
        if not detail.empty
        else pd.DataFrame()
    )
    extracted_like = status["status"].isin(["extracted", "seed_stage446", "cached_raw"]).sum() if not status.empty else 0
    failed_like = status["status"].isin(["failed", "timeout", "empty"]).sum() if not status.empty else 0

    if (valid_same_count >= 10 or valid_open_count >= 10) and (same_large_rate >= 0.50 or open_large_rate >= 0.50):
        label = "session_proxy_mismatch_confirmed_extend_full_rebuild"
    elif covered_windows > 0:
        label = "partial_session_proxy_ready_need_more_coverage"
    else:
        label = "minute_session_batch_no_coverage"

    return {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_scope": TARGET_SCOPE,
        "symbol_offset": SYMBOL_OFFSET,
        "max_symbols": MAX_SYMBOLS,
        "selected_symbols": int(len(status)),
        "extracted_or_cached_symbols": int(extracted_like),
        "failed_or_timeout_or_empty_symbols": int(failed_like),
        "extracted_minute_bars": int(pd.to_numeric(status.get("rows", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
        if not status.empty
        else 0,
        "target_windows": target_windows,
        "covered_windows": covered_windows,
        "coverage_rate": covered_rate,
        "covered_trade_count": detail_trades,
        "valid_same_day_close_trade_count": valid_same_count,
        "valid_next_open_trade_count": valid_open_count,
        "invalid_same_day_close_count": int((detail["valid_same_day_close"] == 0).sum()) if not detail.empty else 0,
        "invalid_next_open_count": int((detail["valid_next_open"] == 0).sum()) if not detail.empty else 0,
        "same_last5_large_mismatch_count": same_large,
        "same_last5_large_mismatch_rate": same_large_rate,
        "real_open_vs_daily_next_open_large_mismatch_count": open_large,
        "real_open_vs_daily_next_open_large_mismatch_rate": open_large_rate,
        "max_same_last5_abs_minus_same_close": float(detail["same_last5_abs_minus_same_close"].max())
        if not detail.empty
        else 0.0,
        "max_same_last5_abs_minus_same_close_valid": float(valid_same["same_last5_abs_minus_same_close"].max())
        if not valid_same.empty
        else 0.0,
        "max_real_open_abs_minus_daily_next_open": float(detail["preferred_real_open_abs_minus_daily_next_open"].max())
        if not detail.empty
        else 0.0,
        "max_real_open_abs_minus_daily_next_open_valid": float(valid_open["preferred_real_open_abs_minus_daily_next_open"].max())
        if not valid_open.empty
        else 0.0,
        "preferred_real_open_cash_delta_vs_same_close": float(
            pd.to_numeric(detail.get("preferred_real_open_proxy_pnl_delta_vs_same_close", pd.Series(dtype=float)), errors="coerce")
            .dropna()
            .sum()
        )
        if not detail.empty
        else 0.0,
        "preferred_real_open_cash_delta_vs_same_close_valid_same_close": float(
            pd.to_numeric(
                valid_same_with_open.get("preferred_real_open_proxy_pnl_delta_vs_same_close", pd.Series(dtype=float)),
                errors="coerce",
            )
            .dropna()
            .sum()
        )
        if not valid_same_with_open.empty
        else 0.0,
        "same_last5_cash_delta_vs_same_close_valid_same_close": float(
            pd.to_numeric(valid_same.get("same_last5_vwap_pnl_delta_vs_same_close", pd.Series(dtype=float)), errors="coerce")
            .dropna()
            .sum()
        )
        if not valid_same.empty
        else 0.0,
        "decision": label,
        "outputs": {
            "extract_status": str(STATUS_PATH),
            "minute_bars": str(BARS_PATH),
            "window_coverage": str(COVERAGE_PATH),
            "proxy_prices": str(PROXY_PRICE_PATH),
            "ledger_proxy_detail": str(DETAIL_PATH),
            "metric_summary": str(METRIC_SUMMARY_PATH),
            "symbol_summary": str(SYMBOL_SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": "继续分批扩展到全量Stage443订单，完成分钟会话执行ledger后再比较Stage079/Stage103与任何新候选。",
    }


def _write_report(
    status: pd.DataFrame,
    coverage: pd.DataFrame,
    proxy: pd.DataFrame,
    detail: pd.DataFrame,
    metric_summary: pd.DataFrame,
    symbol_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    largest = detail.sort_values(
        ["same_last5_abs_minus_same_close", "preferred_real_open_abs_minus_daily_next_open"],
        ascending=[False, False],
    ).head(40) if not detail.empty else pd.DataFrame()
    report = [
        "# Stage148 分钟会话执行重建扩展批次",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：执行口径重建；不新增策略、不修改 Stage079/Stage103 交易规则。",
        f"- 目标范围：`{TARGET_SCOPE}`。",
        f"- 合约偏移/上限：`{SYMBOL_OFFSET}` / `{MAX_SYMBOLS}`。",
        "",
        "## 外部调研判断",
        "",
        "- TqSdk 文档显示 `TqBacktest + get_kline_serial(..., duration_seconds=60)` 可用于历史分钟K回放。",
        "- `DataDownloader` 属于专业版历史下载工具；Stage145 已确认本地账号没有该下载权限，因此本阶段使用 TqBacktest 回放路径。",
        "- xtquant 官方文档显示历史行情下载依赖 MiniQMT 环境；本地 Python 导入 xtdata 已失败，因此本阶段不依赖 QMT 分钟数据。",
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 选中合约数：`{decision['selected_symbols']}`。",
        f"- 成功/缓存合约数：`{decision['extracted_or_cached_symbols']}`。",
        f"- 失败/超时/空合约数：`{decision['failed_or_timeout_or_empty_symbols']}`。",
        f"- 分钟K数量：`{decision['extracted_minute_bars']}`。",
        f"- 目标窗口覆盖：`{decision['covered_windows']} / {decision['target_windows']} = {decision['coverage_rate']:.4%}`。",
        f"- 已接回账本交易数：`{decision['covered_trade_count']}`。",
        f"- 有效日线same close交易数：`{decision['valid_same_day_close_trade_count']}`；无效same close数量：`{decision['invalid_same_day_close_count']}`。",
        f"- 有效日线next_open交易数：`{decision['valid_next_open_trade_count']}`；无效next_open数量：`{decision['invalid_next_open_count']}`。",
        f"- 14:55相对日线same close大错位：`{decision['same_last5_large_mismatch_count']}`，占有效same close交易 `{decision['same_last5_large_mismatch_rate']:.4%}`。",
        f"- 真实开盘相对日线next_open大错位：`{decision['real_open_vs_daily_next_open_large_mismatch_count']}`，占有效next_open交易 `{decision['real_open_vs_daily_next_open_large_mismatch_rate']:.4%}`。",
        f"- 最大价差：14:55 vs same close `{decision['max_same_last5_abs_minus_same_close']:.4f}`，剔除无效价后 `{decision['max_same_last5_abs_minus_same_close_valid']:.4f}`；真实开盘 vs next_open `{decision['max_real_open_abs_minus_daily_next_open']:.4f}`，剔除无效价后 `{decision['max_real_open_abs_minus_daily_next_open_valid']:.4f}`。",
        f"- 已接回样本真实开盘相对同日收盘现金差估计：`{decision['preferred_real_open_cash_delta_vs_same_close']:.2f}`。",
        f"- 剔除无效same close后，真实开盘相对同日收盘现金差估计：`{decision['preferred_real_open_cash_delta_vs_same_close_valid_same_close']:.2f}`。",
        f"- 剔除无效same close后，14:55 VWAP相对同日收盘现金差估计：`{decision['same_last5_cash_delta_vs_same_close_valid_same_close']:.2f}`。",
        "",
        "## 抽取状态",
        "",
        _md_table(status, max_rows=80),
        "",
        "## 合约摘要",
        "",
        _md_table(symbol_summary, max_rows=80),
        "",
        "## 指标摘要",
        "",
        _md_table(metric_summary, max_rows=80),
        "",
        "## 最大错位样本",
        "",
        _md_table(
            largest[
                [
                    "trade_id",
                    "date",
                    "next_trade_date",
                    "vt_symbol",
                    "direction",
                    "offset",
                    "same_day_close",
                    "same_last5_vwap",
                    "next_open",
                    "preferred_real_open_proxy",
                    "preferred_real_open_proxy_type",
                    "same_last5_abs_minus_same_close",
                    "preferred_real_open_abs_minus_daily_next_open",
                    "preferred_real_open_proxy_pnl_delta_vs_same_close",
                ]
            ]
            if not largest.empty
            else largest,
            max_rows=40,
        ),
        "",
        "## 结论",
        "",
        "- 本阶段不产生新策略候选，也不允许据此优化 Stage079 参数。",
        "- 若错位率继续显著，说明 Stage079/Stage103 后续所有3个月/6个月目标都必须先在分钟会话执行账本上重算。",
        "- 下一步应按相同脚本继续扩展批次，直到全量 Stage443 订单至少覆盖 `14:55/21:00/09:00` 可观测代理。",
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行前过拟合反思：否。只校准执行价格，不改策略规则、不筛坏日期或坏品种。",
        "- 运行后过拟合反思：否。错位只作为执行模型问题处理，不作为过滤条件。",
        "- 运行前继续价值反思：是。Stage147 暴露基础成交口径问题，必须补足。",
        "- 运行后继续价值反思：只要覆盖率和错位证据有效，就应继续全量重建；在同日收盘口径上继续优化短持有体验价值较低。",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    RAW_ROOT.mkdir(parents=True, exist_ok=True)
    targets = _load_targets()
    plan = _load_plan()
    selected = _selected_symbols(targets, plan)
    selected_targets = targets[targets["vt_symbol"].isin(set(selected["vt_symbol"]))].copy()
    seed = _load_seed_bars()
    username, password = _require_credentials()

    status_rows: list[dict[str, Any]] = []
    bar_frames: list[pd.DataFrame] = []
    for row in selected.itertuples(index=False):
        status, bars = _extract_symbol(row, username, password, seed)
        status_rows.append(status)
        if not bars.empty:
            bar_frames.append(bars)
        pd.DataFrame(status_rows).to_csv(STATUS_PATH, index=False, encoding="utf-8-sig")
        print(
            f"{status['status']} rank={status['selection_rank']} {status['vt_symbol']} "
            f"{status['tq_symbol']} rows={status['rows']} elapsed={status['elapsed_seconds']}",
            flush=True,
        )

    status = pd.DataFrame(status_rows)
    bars = pd.concat(bar_frames, ignore_index=True) if bar_frames else pd.DataFrame()
    coverage, proxy = _coverage_for_targets(selected_targets, bars)
    ledger = _load_ledger()
    detail = _build_detail(ledger, proxy)
    metric_summary = _metric_summary(detail, coverage, status)
    symbol_summary = _symbol_summary(status, coverage, detail)
    decision = _decision(status, coverage, detail)

    status.to_csv(STATUS_PATH, index=False, encoding="utf-8-sig")
    bars.to_csv(BARS_PATH, index=False, encoding="utf-8-sig")
    coverage.to_csv(COVERAGE_PATH, index=False, encoding="utf-8-sig")
    proxy.to_csv(PROXY_PRICE_PATH, index=False, encoding="utf-8-sig")
    detail.to_csv(DETAIL_PATH, index=False, encoding="utf-8-sig")
    metric_summary.to_csv(METRIC_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    symbol_summary.to_csv(SYMBOL_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(status, coverage, proxy, detail, metric_summary, symbol_summary, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), flush=True)
    print(f"wrote: {REPORT_PATH}", flush=True)


if __name__ == "__main__":
    main()
