from __future__ import annotations

from datetime import datetime, timedelta
import importlib.metadata
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
STAGE = "Stage163"
MODEL_TAG = "stage163_tqsdk_tick_to_minute_volume_source_diagnostic_v1"
OUTPUT_PREFIX = "qmt_roll_stage163_c9_minrisk_tqsdk_tick_to_minute_volume_source_diagnostic"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage163_tqsdk_tick_to_minute_volume_source_diagnostic"
RAW_DIAGNOSTIC_DIR = OUTPUT_DIR / "raw_diagnostic"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE152_DIR = LINE_DIR / "outputs" / "stage152_authoritative_minute_ohlcv_manifest"
STAGE152_PREFIX = "qmt_roll_stage152_c9_minrisk_authoritative_minute_ohlcv_manifest"
STAGE152_TAG = "stage152_authoritative_minute_ohlcv_manifest_v1"
STAGE152_REQUEST_TEMPLATE_IN = STAGE152_DIR / f"{STAGE152_PREFIX}_request_manifest_template_{STAGE152_TAG}.csv"
STAGE160_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage160_authoritative_minute_arrival_monitor"
    / "qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_summary_"
    "stage160_authoritative_minute_arrival_monitor_v1.csv"
)
STAGE162_DIR = LINE_DIR / "outputs" / "stage162_tqsdk_single_request_proofed_conversion_smoke"
STAGE162_PREFIX = "qmt_roll_stage162_c9_minrisk_tqsdk_single_request_proofed_conversion_smoke"
STAGE162_TAG = "stage162_tqsdk_single_request_proofed_conversion_smoke_v1"
STAGE162_SUMMARY_IN = STAGE162_DIR / f"{STAGE162_PREFIX}_summary_{STAGE162_TAG}.csv"
STAGE162_RAW_SAMPLE_IN = STAGE162_DIR / f"{STAGE162_PREFIX}_raw_bars_sample_{STAGE162_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
SELECTED_REQUEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_request_{MODEL_TAG}.csv"
METHOD_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_method_audit_{MODEL_TAG}.csv"
TICK_FETCH_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tick_fetch_status_{MODEL_TAG}.csv"
TICK_RAW_SAMPLE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tick_raw_sample_{MODEL_TAG}.csv"
TICK_MINUTE_AGG_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tick_minute_agg_sample_{MODEL_TAG}.csv"
DOWNLOADER_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_datadownloader_status_{MODEL_TAG}.csv"
DOWNLOADER_SAMPLE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_datadownloader_sample_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_source_repair_status_{MODEL_TAG}.png"
METHOD_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_method_volume_comparison_{MODEL_TAG}.png"
TICK_AGG_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tick_agg_minute_ohlcv_{MODEL_TAG}.png"
DOWNLOADER_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_datadownloader_probe_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"

REQUEST_ID = os.getenv("STAGE163_REQUEST_ID", "stage152_req_0011_jm2509_DCE_20250709").strip()
TICK_PROBE_MINUTES = int(os.getenv("STAGE163_TICK_PROBE_MINUTES", "90"))
MAX_SECONDS_TICK = int(os.getenv("STAGE163_MAX_SECONDS_TICK", "60"))
MAX_SECONDS_DOWNLOADER = int(os.getenv("STAGE163_MAX_SECONDS_DOWNLOADER", "40"))
TICK_DATA_LENGTH = int(os.getenv("STAGE163_TICK_DATA_LENGTH", "60000"))
RUN_DOWNLOADER = os.getenv("STAGE163_RUN_DOWNLOADER", "1").strip() != "0"
MIN_POSITIVE_VOLUME_MINUTES = int(os.getenv("STAGE163_MIN_POSITIVE_VOLUME_MINUTES", "1"))


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def _read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 4:
        if required:
            raise RuntimeError(f"missing required input: {path}")
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _safe_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _num(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        number = float(row.get(key, default))
    except (TypeError, ValueError):
        return default
    return default if not np.isfinite(number) else number


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.6f}")
        else:
            data[column] = data[column].map(
                lambda value: "" if pd.isna(value) else str(value).replace("|", "\\|").replace("\n", "<br>")
            )
    lines = [
        "| " + " | ".join(str(column) for column in data.columns) + " |",
        "| " + " | ".join(["---"] * len(data.columns)) + " |",
    ]
    for _, row in data.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in data.columns) + " |")
    return "\n".join(lines)


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = _safe_num(curve[column])
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _baseline_metrics(curve: pd.DataFrame) -> dict[str, float]:
    stage160 = _read_csv(STAGE160_SUMMARY_IN, required=False)
    if not stage160.empty:
        row = stage160.iloc[0].to_dict()
        return {
            "end_equity": _num(row, "end_equity", np.nan),
            "total_return_pct": _num(row, "total_return_pct", np.nan),
            "max_drawdown_pct": _num(row, "max_drawdown_pct", np.nan),
            "sharpe": _num(row, "sharpe", np.nan),
            "total_slippage": _num(row, "total_slippage", np.nan),
            "total_trade_count": _num(row, "total_trade_count", np.nan),
            "closed_lot_win_rate_pct": _num(row, "closed_lot_win_rate_pct", np.nan),
            "max_broker10_margin_to_equity_pct": _num(row, "max_broker10_margin_to_equity_pct", np.nan),
        }
    equity = curve["account_equity"].dropna()
    return {
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": (float(equity.iloc[-1]) / float(equity.iloc[0]) - 1.0) * 100.0,
        "max_drawdown_pct": float(curve["drawdown_pct"].min()),
        "sharpe": np.nan,
        "total_slippage": np.nan,
        "total_trade_count": np.nan,
        "closed_lot_win_rate_pct": np.nan,
        "max_broker10_margin_to_equity_pct": float(curve["broker10_margin_to_equity_pct"].max()),
    }


def _credentials() -> dict[str, Any]:
    try:
        from vnpy.trader.setting import SETTINGS
    except Exception as exc:
        return {"username": "", "password": "", "username_present": 0, "password_present": 0, "error": repr(exc)[:300]}
    username = str(SETTINGS.get("datafeed.username", "") or "")
    password = str(SETTINGS.get("datafeed.password", "") or "")
    return {
        "username": username,
        "password": password,
        "username_present": int(bool(username)),
        "password_present": int(bool(password)),
        "username_len": len(username),
        "password_len": len(password),
        "error": "",
    }


def _normalize_tqsdk_datetime(value: Any) -> pd.Timestamp:
    from vnpy.trader.utility import ZoneInfo

    ts = pd.to_datetime(value, unit="ns", errors="coerce", utc=True)
    if pd.isna(ts):
        return pd.NaT
    return ts.tz_convert(ZoneInfo("Asia/Shanghai")).tz_localize(None)


def _to_tq_symbol(vt_symbol: str) -> str:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return f"{exchange}.{symbol}"


def _select_request(manifest: pd.DataFrame) -> pd.Series:
    hit = manifest[manifest["request_id"].astype(str).eq(REQUEST_ID)]
    if hit.empty:
        raise RuntimeError(f"Stage163 request not found in Stage152 manifest: {REQUEST_ID}")
    return hit.iloc[0]


def _tqsdk_env_info() -> dict[str, Any]:
    info = {"tqsdk_import_ok": 0, "tqsdk_version": "", "datadownloader_import_ok": 0}
    try:
        __import__("tqsdk")
        info["tqsdk_import_ok"] = 1
        try:
            info["tqsdk_version"] = importlib.metadata.version("tqsdk")
        except importlib.metadata.PackageNotFoundError:
            info["tqsdk_version"] = "unknown"
    except Exception as exc:
        info["tqsdk_import_error"] = repr(exc)[:300]
    try:
        from tqsdk.tools import DataDownloader  # noqa: F401

        info["datadownloader_import_ok"] = 1
    except Exception as exc:
        info["datadownloader_import_error"] = repr(exc)[:300]
    return info


def _stage162_method_row() -> dict[str, Any]:
    summary = _read_csv(STAGE162_SUMMARY_IN, required=False)
    raw = _read_csv(STAGE162_RAW_SAMPLE_IN, required=False)
    row = summary.iloc[0].to_dict() if not summary.empty else {}
    return {
        "method_id": "stage162_backtest_get_kline_serial_1m",
        "method_type": "tqsdk_backtest_kline",
        "attempted": int(not summary.empty),
        "status": str(row.get("fetch_status", "missing_stage162_summary")),
        "row_count": int(_num(row, "normalized_row_count", 0)),
        "positive_volume_row_count": int(_num(row, "positive_volume_row_count", 0)),
        "positive_turnover_row_count": int(raw["amount"].notna().sum()) if not raw.empty and "amount" in raw.columns else 0,
        "source_file": str(STAGE162_SUMMARY_IN.relative_to(REPO_DIR)),
        "eligible_for_stage152_delivery": 0,
        "message": "Stage162 kline path produced price/OI but zero volume; retained as negative control.",
    }


def _tick_probe(row: pd.Series, credential: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    request_start = pd.Timestamp(row["request_start_ts"])
    request_end = pd.Timestamp(row["request_end_ts"])
    query_start = request_start - timedelta(minutes=15)
    query_end = min(request_end, request_start + timedelta(minutes=TICK_PROBE_MINUTES))
    tq_symbol = _to_tq_symbol(str(row["vt_symbol"]))
    status: dict[str, Any] = {
        "method_id": "tqsdk_backtest_get_tick_serial_aggregate_1m",
        "request_id": str(row["request_id"]),
        "vt_symbol": str(row["vt_symbol"]),
        "tq_symbol": tq_symbol,
        "query_start_ts": query_start.strftime("%Y-%m-%d %H:%M:%S"),
        "query_end_ts": query_end.strftime("%Y-%m-%d %H:%M:%S"),
        "credential_present": int(credential["username_present"] and credential["password_present"]),
        "tick_fetch_status": "not_started",
        "tick_row_count": 0,
        "minute_row_count": 0,
        "positive_volume_minute_count": 0,
        "positive_turnover_minute_count": 0,
        "elapsed_seconds": 0.0,
        "message": "",
    }
    if not status["credential_present"]:
        status["tick_fetch_status"] = "missing_credentials"
        status["message"] = credential.get("error", "") or "vnpy SETTINGS datafeed credentials missing"
        return pd.DataFrame(), pd.DataFrame(), status
    try:
        from tqsdk import BacktestFinished, TqApi, TqAuth, TqBacktest, TqSim
    except Exception as exc:
        status["tick_fetch_status"] = "import_failed"
        status["message"] = repr(exc)[:500]
        return pd.DataFrame(), pd.DataFrame(), status

    logging.getLogger().setLevel(logging.WARNING)
    logging.getLogger("tqsdk").setLevel(logging.WARNING)
    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, Any]] = set()
    started = time.time()
    api = None
    try:
        api = TqApi(
            TqSim(),
            backtest=TqBacktest(start_dt=query_start.to_pydatetime(), end_dt=query_end.to_pydatetime()),
            auth=TqAuth(str(credential["username"]), str(credential["password"])),
            disable_print=True,
        )
        ticks = api.get_tick_serial(tq_symbol, data_length=TICK_DATA_LENGTH)
        while True:
            if time.time() - started > MAX_SECONDS_TICK:
                status["tick_fetch_status"] = "timeout"
                status["message"] = f"timeout_after_{MAX_SECONDS_TICK}s"
                break
            if not api.wait_update(deadline=time.time() + 2.0):
                continue
            if not api.is_changing(ticks.iloc[-1], "datetime"):
                continue
            item = ticks.iloc[-1].to_dict()
            tick_dt = _normalize_tqsdk_datetime(item.get("datetime"))
            if pd.isna(tick_dt):
                continue
            key = (item.get("datetime"), item.get("last_price"), item.get("volume"))
            if key in seen:
                continue
            seen.add(key)
            record = {
                "request_id": str(row["request_id"]),
                "exchange": str(row["exchange"]),
                "vt_symbol": str(row["vt_symbol"]),
                "tq_symbol": tq_symbol,
                "tick_datetime": pd.Timestamp(tick_dt),
            }
            for col in [
                "last_price",
                "highest",
                "lowest",
                "volume",
                "amount",
                "open_interest",
                "bid_price1",
                "ask_price1",
                "bid_volume1",
                "ask_volume1",
            ]:
                if col in item:
                    record[col] = item.get(col)
            rows.append(record)
    except BacktestFinished:
        status["tick_fetch_status"] = "extracted"
    except Exception as exc:
        status["tick_fetch_status"] = "failed"
        status["message"] = repr(exc)[:500]
    finally:
        if api is not None:
            api.close()

    ticks_df = pd.DataFrame(rows)
    if not ticks_df.empty:
        ticks_df["tick_datetime"] = pd.to_datetime(ticks_df["tick_datetime"], errors="coerce")
        ticks_df = ticks_df.dropna(subset=["tick_datetime"]).sort_values("tick_datetime").drop_duplicates(
            ["vt_symbol", "tick_datetime", "last_price", "volume"], keep="last"
        )
        for col in ["last_price", "highest", "lowest", "volume", "amount", "open_interest", "bid_price1", "ask_price1"]:
            if col in ticks_df.columns:
                ticks_df[col] = _safe_num(ticks_df[col])
    if status["tick_fetch_status"] == "not_started":
        status["tick_fetch_status"] = "extracted" if not ticks_df.empty else "empty"
    minutes = _aggregate_ticks_to_minutes(ticks_df)
    status.update(
        {
            "tick_row_count": int(len(ticks_df)),
            "minute_row_count": int(len(minutes)),
            "positive_volume_minute_count": int(minutes["volume"].fillna(0).gt(0).sum()) if "volume" in minutes.columns else 0,
            "positive_turnover_minute_count": int(minutes["turnover"].fillna(0).gt(0).sum()) if "turnover" in minutes.columns else 0,
            "elapsed_seconds": round(time.time() - started, 2),
        }
    )
    return ticks_df, minutes, status


def _aggregate_ticks_to_minutes(ticks: pd.DataFrame) -> pd.DataFrame:
    if ticks.empty or "tick_datetime" not in ticks.columns or "last_price" not in ticks.columns:
        return pd.DataFrame(
            columns=[
                "bar_start_ts",
                "bar_end_ts",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "turnover",
                "open_interest",
                "tick_count",
                "source_method",
            ]
        )
    data = ticks.copy().sort_values("tick_datetime").reset_index(drop=True)
    data["bar_start_ts"] = data["tick_datetime"].dt.floor("min")
    if "volume" in data.columns:
        diff = data["volume"].diff()
        data["volume_delta"] = np.where(diff.ge(0), diff, 0.0)
        if len(data) > 0 and pd.notna(data.loc[0, "volume"]):
            data.loc[0, "volume_delta"] = 0.0
    else:
        data["volume_delta"] = np.nan
    if "amount" in data.columns:
        amount_diff = data["amount"].diff()
        data["turnover_delta"] = np.where(amount_diff.ge(0), amount_diff, 0.0)
        if len(data) > 0 and pd.notna(data.loc[0, "amount"]):
            data.loc[0, "turnover_delta"] = 0.0
    else:
        data["turnover_delta"] = np.nan
    rows = []
    for minute, group in data.groupby("bar_start_ts", sort=True):
        prices = group["last_price"].dropna()
        if prices.empty:
            continue
        rows.append(
            {
                "bar_start_ts": minute,
                "bar_end_ts": minute + pd.Timedelta(minutes=1),
                "open": float(prices.iloc[0]),
                "high": float(prices.max()),
                "low": float(prices.min()),
                "close": float(prices.iloc[-1]),
                "volume": float(group["volume_delta"].fillna(0).sum()),
                "turnover": float(group["turnover_delta"].fillna(0).sum()),
                "open_interest": float(group["open_interest"].dropna().iloc[-1]) if "open_interest" in group and not group["open_interest"].dropna().empty else np.nan,
                "tick_count": int(len(group)),
                "source_method": "tqsdk_backtest_get_tick_serial_aggregate_1m",
            }
        )
    result = pd.DataFrame(rows)
    if not result.empty:
        result["bar_start_ts"] = pd.to_datetime(result["bar_start_ts"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        result["bar_end_ts"] = pd.to_datetime(result["bar_end_ts"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    return result


def _run_datadownloader(row: pd.Series, credential: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    request_start = pd.Timestamp(row["request_start_ts"])
    request_end = pd.Timestamp(row["request_end_ts"])
    query_end = min(request_end, request_start + timedelta(minutes=TICK_PROBE_MINUTES))
    tq_symbol = _to_tq_symbol(str(row["vt_symbol"]))
    out_path = RAW_DIAGNOSTIC_DIR / f"{row['request_id']}.datadownloader_1m.csv"
    status: dict[str, Any] = {
        "method_id": "tqsdk_datadownloader_1m",
        "request_id": str(row["request_id"]),
        "vt_symbol": str(row["vt_symbol"]),
        "tq_symbol": tq_symbol,
        "run_enabled": int(RUN_DOWNLOADER),
        "credential_present": int(credential["username_present"] and credential["password_present"]),
        "download_status": "not_started",
        "csv_path": str(out_path.relative_to(REPO_DIR)),
        "row_count": 0,
        "positive_volume_row_count": 0,
        "positive_turnover_row_count": 0,
        "elapsed_seconds": 0.0,
        "message": "",
    }
    if not RUN_DOWNLOADER:
        status["download_status"] = "disabled"
        return pd.DataFrame(), status
    if not status["credential_present"]:
        status["download_status"] = "missing_credentials"
        status["message"] = credential.get("error", "") or "vnpy SETTINGS datafeed credentials missing"
        return pd.DataFrame(), status
    try:
        from tqsdk import TqApi, TqAuth
        from tqsdk.tools import DataDownloader
    except Exception as exc:
        status["download_status"] = "import_failed"
        status["message"] = repr(exc)[:500]
        return pd.DataFrame(), status
    logging.getLogger().setLevel(logging.WARNING)
    logging.getLogger("tqsdk").setLevel(logging.WARNING)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()
    api = None
    started = time.time()
    try:
        api = TqApi(auth=TqAuth(str(credential["username"]), str(credential["password"])), disable_print=True)
        downloader = DataDownloader(
            api,
            symbol_list=tq_symbol,
            dur_sec=60,
            start_dt=request_start.to_pydatetime(),
            end_dt=query_end.to_pydatetime(),
            csv_file_name=str(out_path),
        )
        while not downloader.is_finished():
            if time.time() - started > MAX_SECONDS_DOWNLOADER:
                status["download_status"] = "timeout"
                status["message"] = f"timeout_after_{MAX_SECONDS_DOWNLOADER}s"
                break
            api.wait_update(deadline=time.time() + 2.0)
        if downloader.is_finished() and status["download_status"] == "not_started":
            status["download_status"] = "finished"
    except Exception as exc:
        status["download_status"] = "failed"
        status["message"] = repr(exc)[:500]
    finally:
        if api is not None:
            api.close()
    data = pd.DataFrame()
    if out_path.exists() and out_path.stat().st_size > 0:
        try:
            data = pd.read_csv(out_path, encoding="utf-8-sig")
        except Exception as exc:
            status["message"] = (status.get("message", "") + f"; csv_read_failed:{type(exc).__name__}")[:500]
    volume_cols = [col for col in data.columns if col.endswith(".volume") or col == "volume"]
    turnover_cols = [col for col in data.columns if col.endswith(".amount") or col == "amount"]
    status["row_count"] = int(len(data))
    status["positive_volume_row_count"] = int(
        sum(pd.to_numeric(data[col], errors="coerce").fillna(0).gt(0).sum() for col in volume_cols)
    ) if not data.empty else 0
    status["positive_turnover_row_count"] = int(
        sum(pd.to_numeric(data[col], errors="coerce").fillna(0).gt(0).sum() for col in turnover_cols)
    ) if not data.empty else 0
    status["elapsed_seconds"] = round(time.time() - started, 2)
    return data, status


def _method_audit(stage162_row: dict[str, Any], tick_status: dict[str, Any], downloader_status: dict[str, Any]) -> pd.DataFrame:
    rows = [stage162_row]
    tick_positive = int(tick_status.get("positive_volume_minute_count", 0))
    rows.append(
        {
            "method_id": "tqsdk_backtest_get_tick_serial_aggregate_1m",
            "method_type": "tqsdk_backtest_tick_aggregate",
            "attempted": 1,
            "status": tick_status.get("tick_fetch_status", ""),
            "row_count": int(tick_status.get("minute_row_count", 0)),
            "positive_volume_row_count": tick_positive,
            "positive_turnover_row_count": int(tick_status.get("positive_turnover_minute_count", 0)),
            "source_file": str(TICK_MINUTE_AGG_OUT.relative_to(REPO_DIR)),
            "eligible_for_stage152_delivery": 0,
            "message": "Diagnostic only; tick aggregation may repair volume but still needs full-request proof/schema/hash/window validation.",
        }
    )
    rows.append(
        {
            "method_id": "tqsdk_datadownloader_1m",
            "method_type": "tqsdk_datadownloader_kline",
            "attempted": int(downloader_status.get("run_enabled", 0)),
            "status": downloader_status.get("download_status", ""),
            "row_count": int(downloader_status.get("row_count", 0)),
            "positive_volume_row_count": int(downloader_status.get("positive_volume_row_count", 0)),
            "positive_turnover_row_count": int(downloader_status.get("positive_turnover_row_count", 0)),
            "source_file": downloader_status.get("csv_path", ""),
            "eligible_for_stage152_delivery": 0,
            "message": str(downloader_status.get("message", ""))[:240],
        }
    )
    return pd.DataFrame(rows)


def _decision(summary: dict[str, Any]) -> tuple[str, str]:
    if summary["datadownloader_positive_volume_row_count"] > 0:
        return (
            "stage163_datadownloader_1m_has_real_volume_prepare_stage164_proofed_delivery_no_rule",
            "stage164_datadownloader_full_request_proofed_delivery_smoke",
        )
    if summary["tick_positive_volume_minute_count"] >= MIN_POSITIVE_VOLUME_MINUTES:
        return (
            "stage163_tick_aggregate_has_real_volume_prepare_full_request_proofed_delivery_no_rule",
            "stage164_tick_aggregate_full_request_proofed_delivery_smoke",
        )
    return (
        "stage163_no_authorized_volume_path_confirmed_wait_or_repair_source_no_rule",
        "repair_tqsdk_volume_source_or_wait_authorized_stage152_package",
    )


def _gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    gates = [
        ("stage162_negative_control_loaded", summary["stage162_kline_loaded"], 1, "context_hard"),
        ("tqsdk_import_ok", summary["tqsdk_import_ok"], 1, "source_hard"),
        ("credentials_present", summary["credential_present"], 1, "source_hard"),
        ("tick_fetch_extracted", int(summary["tick_fetch_status"] in {"extracted", "timeout"}), 1, "source_hard"),
        ("tick_positive_volume_minutes", summary["tick_positive_volume_minute_count"], MIN_POSITIVE_VOLUME_MINUTES, "data_hard"),
        ("datadownloader_import_ok", summary["datadownloader_import_ok"], 1, "source_soft"),
        ("datadownloader_positive_volume_rows", summary["datadownloader_positive_volume_row_count"], 1, "data_soft"),
        ("incoming_files_written", summary["incoming_files_written"], 0, "safety_hard"),
        ("strategy_rule_created", summary["strategy_rule_created"], 0, "strategy_hard"),
        ("true_engine_run", summary["true_engine_run"], 0, "strategy_hard"),
        ("order_api_called", summary["order_api_called"], 0, "safety_hard"),
    ]
    rows = []
    for gate_id, observed, required, severity in gates:
        observed_int = int(observed)
        required_int = int(required)
        rows.append(
            {
                "gate_id": gate_id,
                "observed": observed_int,
                "required": required_int,
                "pass_now": int(observed_int >= required_int) if required_int > 0 else int(observed_int == 0),
                "severity": severity,
            }
        )
    return pd.DataFrame(rows)


def _write_report(
    summary: dict[str, Any],
    selected: pd.DataFrame,
    method_audit: pd.DataFrame,
    tick_status: pd.DataFrame,
    downloader_status: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    text = "\n".join(
        [
            "# Stage163 TqSdk Tick To Minute Volume Source Diagnostic",
            "",
            f"- model_tag: `{MODEL_TAG}`",
            f"- decision: `{summary['decision']}`",
            "- Scope: source repair diagnostic after Stage162 zero-volume kline path.",
            "- Hard lock: no incoming write, no strategy rule, no true engine, no A/B, no CTP, no order API, no official config change.",
            "",
            "## Summary",
            "",
            _md_table(pd.DataFrame([summary])),
            "",
            "## Selected Request",
            "",
            _md_table(selected),
            "",
            "## Method Audit",
            "",
            _md_table(method_audit),
            "",
            "## Tick Fetch Status",
            "",
            _md_table(tick_status),
            "",
            "## DataDownloader Status",
            "",
            _md_table(downloader_status),
            "",
            "## Gate Status",
            "",
            _md_table(gate),
            "",
            "## Next",
            "",
            "- If tick aggregation has positive minute volume, run a full-request proofed delivery smoke in the next stage, still writing only if raw/normalized/proof can be validated.",
            "- If DataDownloader has positive volume, prefer it over tick aggregation for Stage164 because it directly emits 1m bars.",
            "- If neither path has positive volume, stop strategy work and wait for authorized Stage152 delivery or source repair.",
            "",
        ]
    )
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(text, encoding="utf-8")


def _plot_path(curve: pd.DataFrame, summary: dict[str, Any]) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(15, 11), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"], color="#1f77b4", linewidth=1.8)
    axes[0].set_title("Official Path Unchanged; Stage163 Source Repair Diagnostic")
    axes[0].set_ylabel("Equity")
    axes[0].grid(alpha=0.25)
    axes[0].text(
        0.01,
        0.95,
        f"decision={summary['decision']} | tick vol mins={summary['tick_positive_volume_minute_count']} | downloader vol rows={summary['datadownloader_positive_volume_row_count']}",
        transform=axes[0].transAxes,
        va="top",
        fontsize=9,
        bbox={"facecolor": "white", "edgecolor": "#cccccc", "alpha": 0.9},
    )
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#d62728", linewidth=1.3)
    axes[1].axhline(-30, color="#888888", linestyle="--", linewidth=0.9)
    axes[1].set_ylabel("Drawdown %")
    axes[1].grid(alpha=0.25)
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#9467bd", linewidth=1.2)
    axes[2].axhline(100, color="#888888", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("Broker10 %")
    axes[2].grid(alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_method(method_audit: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    data = method_audit.copy()
    y = np.arange(len(data))
    ax.barh(y - 0.18, data["row_count"], height=0.34, color="#1f77b4", label="rows")
    ax.barh(y + 0.18, data["positive_volume_row_count"], height=0.34, color="#2ca02c", label="positive volume rows")
    ax.set_yticks(y)
    ax.set_yticklabels(data["method_id"].tolist())
    ax.set_title("Stage163 Method Comparison: Row Count vs Real Volume")
    ax.grid(axis="x", alpha=0.25)
    ax.legend()
    for idx, row in data.iterrows():
        ax.text(float(row["row_count"]) + 0.5, idx - 0.18, str(int(row["row_count"])), va="center", fontsize=9)
        ax.text(float(row["positive_volume_row_count"]) + 0.5, idx + 0.18, str(int(row["positive_volume_row_count"])), va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(METHOD_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_tick_agg(minutes: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    if minutes.empty:
        axes[0].text(0.5, 0.5, "No tick-aggregated minutes", ha="center", va="center")
        axes[0].axis("off")
        axes[1].axis("off")
    else:
        data = minutes.copy()
        data["bar_start_ts"] = pd.to_datetime(data["bar_start_ts"], errors="coerce")
        axes[0].plot(data["bar_start_ts"], data["close"], color="#1f77b4", linewidth=1.4, label="close")
        axes[0].fill_between(data["bar_start_ts"], data["low"], data["high"], color="#aec7e8", alpha=0.35, label="low-high")
        axes[0].set_title("Tick-Aggregated 1m Price Path")
        axes[0].set_ylabel("Price")
        axes[0].legend()
        axes[0].grid(alpha=0.25)
        axes[1].bar(data["bar_start_ts"], data["volume"], width=0.0007, color="#2ca02c", label="volume")
        axes[1].set_ylabel("Volume delta")
        axes[1].grid(alpha=0.25)
        axes[1].legend()
        fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(TICK_AGG_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_downloader(downloader: pd.DataFrame, status: dict[str, Any]) -> None:
    fig, ax = plt.subplots(figsize=(12, 5))
    if downloader.empty:
        raw_message = str(status.get("message", ""))
        ascii_message = raw_message.encode("ascii", errors="ignore").decode("ascii").strip()
        if not ascii_message:
            ascii_message = "non-ascii vendor error message; see datadownloader_status csv"
        ax.text(
            0.5,
            0.5,
            f"DataDownloader status: {status.get('download_status', '')}\n{ascii_message[:180]}",
            ha="center",
            va="center",
            wrap=True,
        )
        ax.axis("off")
    else:
        volume_cols = [col for col in downloader.columns if col.endswith(".volume") or col == "volume"]
        volume = pd.to_numeric(downloader[volume_cols[0]], errors="coerce").fillna(0) if volume_cols else pd.Series(dtype=float)
        ax.bar(np.arange(len(volume)), volume, color="#2ca02c")
        ax.set_title("DataDownloader 1m Volume Probe")
        ax.set_xlabel("row index")
        ax.set_ylabel(volume_cols[0] if volume_cols else "volume")
        ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(DOWNLOADER_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(13, 7))
    matrix = gate[["pass_now"]].to_numpy(dtype=float)
    ax.imshow(matrix, aspect="auto", cmap=plt.get_cmap("RdYlGn"), vmin=0, vmax=1)
    ax.set_yticks(np.arange(len(gate)))
    ax.set_yticklabels(gate["gate_id"].tolist())
    ax.set_xticks([0])
    ax.set_xticklabels(["pass_now"])
    ax.set_title("Stage163 Gate Status Matrix")
    for row_idx, row in gate.iterrows():
        ax.text(0, row_idx, f"{int(row['observed'])}/{int(row['required'])}", ha="center", va="center", color="black", fontsize=9)
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=170)
    plt.close(fig)


def main() -> None:
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    curve = _load_curve()
    metrics = _baseline_metrics(curve)
    manifest = _read_csv(STAGE152_REQUEST_TEMPLATE_IN)
    selected = _select_request(manifest)
    selected_frame = pd.DataFrame([selected.to_dict()])
    credential = _credentials()
    env = _tqsdk_env_info()

    stage162_row = _stage162_method_row()
    tick_raw, tick_minutes, tick_status = _tick_probe(selected, credential)
    downloader_data, downloader_status = _run_datadownloader(selected, credential)
    method = _method_audit(stage162_row, tick_status, downloader_status)

    decision, next_best_action = _decision(
        {
            "tick_positive_volume_minute_count": int(tick_status.get("positive_volume_minute_count", 0)),
            "datadownloader_positive_volume_row_count": int(downloader_status.get("positive_volume_row_count", 0)),
        }
    )
    summary: dict[str, Any] = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": created_at,
        "line_id": LINE_ID,
        "decision": decision,
        "next_best_action": next_best_action,
        "request_id": str(selected["request_id"]),
        "vt_symbol": str(selected["vt_symbol"]),
        "exchange": str(selected["exchange"]),
        "request_start_ts": str(selected["request_start_ts"]),
        "request_end_ts": str(selected["request_end_ts"]),
        "probe_minutes": TICK_PROBE_MINUTES,
        "credential_present": int(credential["username_present"] and credential["password_present"]),
        "credential_username_len": int(credential.get("username_len", 0)),
        "credential_password_len": int(credential.get("password_len", 0)),
        "tqsdk_import_ok": int(env.get("tqsdk_import_ok", 0)),
        "tqsdk_version": str(env.get("tqsdk_version", "")),
        "datadownloader_import_ok": int(env.get("datadownloader_import_ok", 0)),
        "stage162_kline_loaded": int(stage162_row["attempted"]),
        "stage162_kline_positive_volume_row_count": int(stage162_row["positive_volume_row_count"]),
        "tick_fetch_status": str(tick_status.get("tick_fetch_status", "")),
        "tick_row_count": int(tick_status.get("tick_row_count", 0)),
        "tick_minute_row_count": int(tick_status.get("minute_row_count", 0)),
        "tick_positive_volume_minute_count": int(tick_status.get("positive_volume_minute_count", 0)),
        "tick_positive_turnover_minute_count": int(tick_status.get("positive_turnover_minute_count", 0)),
        "datadownloader_run_enabled": int(downloader_status.get("run_enabled", 0)),
        "datadownloader_status": str(downloader_status.get("download_status", "")),
        "datadownloader_row_count": int(downloader_status.get("row_count", 0)),
        "datadownloader_positive_volume_row_count": int(downloader_status.get("positive_volume_row_count", 0)),
        "datadownloader_positive_turnover_row_count": int(downloader_status.get("positive_turnover_row_count", 0)),
        "incoming_files_written": 0,
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "true_engine_run_count": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "current_package_promotion_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "objective_completion_proven": 0,
        "side_effect_count": 0,
        "visual_output_count": 5,
    }
    summary.update(metrics)
    gate = _gate_status(summary)

    _write_csv(pd.DataFrame([summary]), SUMMARY_OUT)
    _write_csv(selected_frame, SELECTED_REQUEST_OUT)
    _write_csv(method, METHOD_AUDIT_OUT)
    _write_csv(pd.DataFrame([tick_status]), TICK_FETCH_STATUS_OUT)
    _write_csv(tick_raw.head(500), TICK_RAW_SAMPLE_OUT)
    _write_csv(tick_minutes.head(500), TICK_MINUTE_AGG_OUT)
    _write_csv(pd.DataFrame([downloader_status]), DOWNLOADER_STATUS_OUT)
    _write_csv(downloader_data.head(500), DOWNLOADER_SAMPLE_OUT)
    _write_csv(gate, GATE_OUT)
    _write_json(
        DECISION_OUT,
        {
            "decision": decision,
            "summary": summary,
            "outputs": {
                "summary": SUMMARY_OUT,
                "selected_request": SELECTED_REQUEST_OUT,
                "method_audit": METHOD_AUDIT_OUT,
                "tick_fetch_status": TICK_FETCH_STATUS_OUT,
                "tick_raw_sample": TICK_RAW_SAMPLE_OUT,
                "tick_minute_agg": TICK_MINUTE_AGG_OUT,
                "datadownloader_status": DOWNLOADER_STATUS_OUT,
                "datadownloader_sample": DOWNLOADER_SAMPLE_OUT,
                "gate_status": GATE_OUT,
                "report": REPORT_OUT,
                "charts": [PATH_CHART_OUT, METHOD_CHART_OUT, TICK_AGG_CHART_OUT, DOWNLOADER_CHART_OUT, GATE_CHART_OUT],
            },
        },
    )
    _write_report(pd.DataFrame([summary]).iloc[0].to_dict(), selected_frame, method, pd.DataFrame([tick_status]), pd.DataFrame([downloader_status]), gate)
    _plot_path(curve, summary)
    _plot_method(method)
    _plot_tick_agg(tick_minutes)
    _plot_downloader(downloader_data, downloader_status)
    _plot_gate(gate)
    print(json.dumps(_json_safe(summary), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
