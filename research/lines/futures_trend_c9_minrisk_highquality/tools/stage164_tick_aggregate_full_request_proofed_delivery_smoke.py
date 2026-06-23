from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
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
STAGE = "Stage164"
MODEL_TAG = "stage164_tick_aggregate_full_request_proofed_delivery_smoke_v1"
OUTPUT_PREFIX = "qmt_roll_stage164_c9_minrisk_tick_aggregate_full_request_proofed_delivery_smoke"
PROOF_NORMALIZATION_VERSION = "stage164_tick_aggregate_full_request_proofed_delivery_v1"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage164_tick_aggregate_full_request_proofed_delivery_smoke"

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
STAGE152_WINDOWS_IN = STAGE152_DIR / f"{STAGE152_PREFIX}_required_window_contract_{STAGE152_TAG}.csv"
STAGE160_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage160_authoritative_minute_arrival_monitor"
    / "qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_summary_"
    "stage160_authoritative_minute_arrival_monitor_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
SELECTED_REQUEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_request_{MODEL_TAG}.csv"
FETCH_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tick_fetch_status_{MODEL_TAG}.csv"
WINDOW_PRECHECK_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_precheck_{MODEL_TAG}.csv"
RAW_SAMPLE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_raw_tick_sample_{MODEL_TAG}.csv"
NORMALIZED_SAMPLE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_normalized_bars_sample_{MODEL_TAG}.csv"
DELIVERY_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delivery_audit_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_delivery_status_{MODEL_TAG}.png"
KLINE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_full_request_tick_agg_ohlcv_{MODEL_TAG}.png"
WINDOW_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_precheck_matrix_{MODEL_TAG}.png"
DELIVERY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delivery_matrix_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"

REQUEST_ID = os.getenv("STAGE164_REQUEST_ID", "stage152_req_0011_jm2509_DCE_20250709").strip()
WRITE_INCOMING = os.getenv("STAGE164_WRITE_INCOMING", "1").strip() != "0"
OVERWRITE_EXISTING = os.getenv("STAGE164_OVERWRITE_EXISTING", "0").strip() == "1"
MAX_SECONDS_TICK = int(os.getenv("STAGE164_MAX_SECONDS_TICK", "120"))
TICK_DATA_LENGTH = int(os.getenv("STAGE164_TICK_DATA_LENGTH", "120000"))
MIN_NORMALIZED_ROWS = int(os.getenv("STAGE164_MIN_NORMALIZED_ROWS", "10"))


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


def _safe_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _num(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        number = float(row.get(key, default))
    except (TypeError, ValueError):
        return default
    return default if not np.isfinite(number) else number


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
        raise RuntimeError(f"Stage164 request not found in Stage152 manifest: {REQUEST_ID}")
    return hit.iloc[0]


def _resolve_path(path_text: Any) -> Path:
    path = Path(str(path_text))
    return path if path.is_absolute() else REPO_DIR / path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _schema_hash(raw_columns: list[str], normalized_columns: list[str]) -> str:
    payload = {"raw_columns": raw_columns, "normalized_columns": normalized_columns}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _fetch_ticks(row: pd.Series, credential: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    request_start = pd.Timestamp(row["request_start_ts"])
    request_end = pd.Timestamp(row["request_end_ts"])
    query_start = request_start - timedelta(minutes=15)
    query_end = request_end + timedelta(minutes=1)
    tq_symbol = _to_tq_symbol(str(row["vt_symbol"]))
    status: dict[str, Any] = {
        "request_id": str(row["request_id"]),
        "vt_symbol": str(row["vt_symbol"]),
        "tq_symbol": tq_symbol,
        "query_start_ts": query_start.strftime("%Y-%m-%d %H:%M:%S"),
        "query_end_ts": query_end.strftime("%Y-%m-%d %H:%M:%S"),
        "credential_present": int(credential["username_present"] and credential["password_present"]),
        "tick_fetch_status": "not_started",
        "tick_row_count": 0,
        "elapsed_seconds": 0.0,
        "message": "",
    }
    if not status["credential_present"]:
        status["tick_fetch_status"] = "missing_credentials"
        status["message"] = credential.get("error", "") or "vnpy SETTINGS datafeed credentials missing"
        return pd.DataFrame(), status
    try:
        from tqsdk import BacktestFinished, TqApi, TqAuth, TqBacktest, TqSim
    except Exception as exc:
        status["tick_fetch_status"] = "import_failed"
        status["message"] = repr(exc)[:500]
        return pd.DataFrame(), status
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
    status["tick_row_count"] = int(len(ticks_df))
    status["elapsed_seconds"] = round(time.time() - started, 2)
    return ticks_df, status


def _aggregate_ticks(row: pd.Series, ticks: pd.DataFrame) -> pd.DataFrame:
    request_start = pd.Timestamp(row["request_start_ts"])
    request_end = pd.Timestamp(row["request_end_ts"])
    columns = [
        "exchange",
        "vt_symbol",
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
    if ticks.empty or "tick_datetime" not in ticks.columns or "last_price" not in ticks.columns:
        return pd.DataFrame(columns=columns)
    data = ticks.copy().sort_values("tick_datetime").reset_index(drop=True)
    data["bar_start_ts_dt"] = data["tick_datetime"].dt.floor("min")
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
    records: list[dict[str, Any]] = []
    for minute, group in data.groupby("bar_start_ts_dt", sort=True):
        if minute < request_start or minute > request_end:
            continue
        prices = group["last_price"].dropna()
        if prices.empty:
            continue
        records.append(
            {
                "exchange": str(row["exchange"]),
                "vt_symbol": str(row["vt_symbol"]),
                "bar_start_ts": minute.strftime("%Y-%m-%d %H:%M:%S"),
                "bar_end_ts": (minute + pd.Timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S"),
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
    return pd.DataFrame(records, columns=columns)


def _window_precheck(selected: pd.Series, normalized: pd.DataFrame) -> pd.DataFrame:
    windows = _read_csv(STAGE152_WINDOWS_IN)
    selected_windows = windows[
        windows["exchange"].astype(str).eq(str(selected["exchange"]))
        & windows["product"].astype(str).eq(str(selected["product"]))
        & windows["vt_symbol"].astype(str).eq(str(selected["vt_symbol"]))
        & windows["request_date"].astype(str).eq(str(selected["request_date"]))
    ].copy()
    bars = normalized.copy()
    if not bars.empty:
        bars["bar_start_ts_dt"] = pd.to_datetime(bars["bar_start_ts"], errors="coerce")
    rows: list[dict[str, Any]] = []
    for _, window in selected_windows.iterrows():
        start = pd.Timestamp(window["window_start_ts"])
        end = pd.Timestamp(window["window_end_ts"])
        observed = pd.DataFrame()
        if not bars.empty:
            observed = bars[bars["bar_start_ts_dt"].ge(start) & bars["bar_start_ts_dt"].le(end)]
        rows.append(
            {
                "window_id": window["window_id"],
                "window_type": window["window_type"],
                "window_start_ts": window["window_start_ts"],
                "window_end_ts": window["window_end_ts"],
                "priority_class": window["priority_class"],
                "estimated_required_1m_bars": int(window["estimated_required_1m_bars"]),
                "observed_bar_count": int(len(observed)),
                "duplicate_bar_count": int(observed["bar_start_ts"].duplicated().sum()) if not observed.empty else 0,
                "positive_volume_bar_count": int(pd.to_numeric(observed["volume"], errors="coerce").fillna(0).gt(0).sum()) if not observed.empty else 0,
                "coverage_precheck_pass": int(
                    len(observed) > 0
                    and (int(observed["bar_start_ts"].duplicated().sum()) if not observed.empty else 0) == 0
                    and (int(pd.to_numeric(observed["volume"], errors="coerce").fillna(0).gt(0).sum()) if not observed.empty else 0) > 0
                ),
            }
        )
    return pd.DataFrame(rows)


def _write_delivery(row: pd.Series, raw_ticks: pd.DataFrame, normalized: pd.DataFrame, fetch_status: dict[str, Any], window_precheck: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw_path = _resolve_path(row["expected_raw_file"])
    normalized_path = _resolve_path(row["expected_normalized_file"])
    proof_path = _resolve_path(row["expected_proof_file"])
    existing_targets = [str(path.relative_to(REPO_DIR)) for path in [raw_path, normalized_path, proof_path] if path.exists()]
    delivery = {
        "request_id": str(row["request_id"]),
        "write_incoming_enabled": int(WRITE_INCOMING),
        "overwrite_existing": int(OVERWRITE_EXISTING),
        "raw_path": str(raw_path.relative_to(REPO_DIR)),
        "normalized_path": str(normalized_path.relative_to(REPO_DIR)),
        "proof_path": str(proof_path.relative_to(REPO_DIR)),
        "existing_target_count": len(existing_targets),
        "existing_targets": ",".join(existing_targets),
        "raw_written": 0,
        "normalized_written": 0,
        "proof_written": 0,
        "expected_files_written": 0,
        "write_blocker": "",
        "raw_sha256": "",
        "schema_hash": "",
    }
    positive_volume = int(pd.to_numeric(normalized.get("volume", pd.Series(dtype=float)), errors="coerce").fillna(0).gt(0).sum())
    ready = (
        WRITE_INCOMING
        and fetch_status.get("tick_fetch_status") in {"extracted", "timeout"}
        and len(raw_ticks) > 0
        and len(normalized) >= MIN_NORMALIZED_ROWS
        and positive_volume > 0
        and (window_precheck.empty or int(window_precheck["coverage_precheck_pass"].sum()) == len(window_precheck))
        and (OVERWRITE_EXISTING or len(existing_targets) == 0)
    )
    if not ready:
        reasons = []
        if not WRITE_INCOMING:
            reasons.append("write_disabled")
        if fetch_status.get("tick_fetch_status") not in {"extracted", "timeout"}:
            reasons.append("tick_fetch_not_ready")
        if len(raw_ticks) == 0:
            reasons.append("no_raw_ticks")
        if len(normalized) < MIN_NORMALIZED_ROWS:
            reasons.append("not_enough_normalized_rows")
        if positive_volume <= 0:
            reasons.append("no_positive_volume")
        if not window_precheck.empty and int(window_precheck["coverage_precheck_pass"].sum()) != len(window_precheck):
            reasons.append("window_precheck_failed")
        if existing_targets and not OVERWRITE_EXISTING:
            reasons.append("target_exists")
        delivery["write_blocker"] = ",".join(reasons) or "unknown_not_ready"
        return pd.DataFrame([delivery]), delivery

    raw_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    raw_tmp = raw_path.with_name(raw_path.name + ".tmp")
    normalized_tmp = normalized_path.with_name(normalized_path.name + ".tmp")
    proof_tmp = proof_path.with_name(proof_path.name + ".tmp")
    for tmp in [raw_tmp, normalized_tmp, proof_tmp]:
        if tmp.exists():
            tmp.unlink()
    raw_ticks.to_csv(raw_tmp, index=False, encoding="utf-8-sig", compression={"method": "zstd", "level": 3})
    normalized.to_parquet(normalized_tmp, index=False)
    raw_sha = _sha256(raw_tmp)
    schema_hash = _schema_hash(list(raw_ticks.columns), list(normalized.columns))
    proof = {
        "request_id": str(row["request_id"]),
        "vendor_name": "TqSdk",
        "vendor_license": "local vnpy datafeed entitlement for TqSdk historical tick replay; DataDownloader tq_dl entitlement absent",
        "dataset_id": "tqsdk_backtest_tick_serial_aggregate_1m",
        "query_params": {
            "symbols": [_to_tq_symbol(str(row["vt_symbol"]))],
            "interval": "1m",
            "start_ts": str(row["request_start_ts"]),
            "end_ts": str(row["request_end_ts"]),
            "timezone": "Asia/Shanghai",
            "adjustment": "none",
            "source_endpoint": "TqBacktest get_tick_serial",
            "tick_query_start_ts": fetch_status["query_start_ts"],
            "tick_query_end_ts": fetch_status["query_end_ts"],
            "tick_data_length": TICK_DATA_LENGTH,
            "aggregation": "minute OHLC from last_price; volume and turnover from non-negative cumulative tick deltas",
        },
        "raw_file": str(raw_path.relative_to(REPO_DIR)),
        "raw_sha256": raw_sha,
        "schema_hash": schema_hash,
        "normalization_version": PROOF_NORMALIZATION_VERSION,
        "exchange": str(row["exchange"]),
        "vt_symbol": str(row["vt_symbol"]),
        "request_start_ts": str(row["request_start_ts"]),
        "request_end_ts": str(row["request_end_ts"]),
        "timezone": "Asia/Shanghai",
        "session_calendar": f"{row['exchange']} exchange day and night sessions, no bars inserted for non-trading intervals",
        "no_trade_bar_policy": "Only bars with at least one tick are emitted; no zero-volume filler bars are inserted; no-trade intervals remain absent.",
        "synthetic_or_adjusted_flag": False,
        "template_only_not_real_proof": False,
    }
    _write_json(proof_tmp, proof)
    raw_tmp.replace(raw_path)
    normalized_tmp.replace(normalized_path)
    proof_tmp.replace(proof_path)
    delivery.update(
        {
            "raw_written": int(raw_path.exists()),
            "normalized_written": int(normalized_path.exists()),
            "proof_written": int(proof_path.exists()),
            "expected_files_written": int(raw_path.exists()) + int(normalized_path.exists()) + int(proof_path.exists()),
            "raw_sha256": raw_sha,
            "schema_hash": schema_hash,
        }
    )
    return pd.DataFrame([delivery]), delivery


def _gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    gates = [
        ("credentials_present", summary["credential_present"], 1, "source_hard"),
        ("tick_fetch_extracted", int(summary["tick_fetch_status"] in {"extracted", "timeout"}), 1, "source_hard"),
        ("raw_tick_rows", summary["raw_tick_row_count"], 1, "data_hard"),
        ("normalized_rows_min", summary["normalized_row_count"], MIN_NORMALIZED_ROWS, "data_hard"),
        ("positive_volume_rows", summary["positive_volume_row_count"], 1, "data_hard"),
        ("window_precheck_pass", summary["window_precheck_pass_count"], summary["window_precheck_count"], "coverage_hard"),
        ("expected_files_written", summary["expected_files_written"], 3, "delivery_hard"),
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


def _write_report(summary: dict[str, Any], selected: pd.DataFrame, fetch: pd.DataFrame, windows: pd.DataFrame, delivery: pd.DataFrame, gate: pd.DataFrame) -> None:
    text = "\n".join(
        [
            "# Stage164 Tick Aggregate Full Request Proofed Delivery",
            "",
            f"- model_tag: `{MODEL_TAG}`",
            f"- decision: `{summary['decision']}`",
            "- Scope: one Stage152 request raw/normalized/proof delivery from tick-aggregated 1m OHLCV.",
            "- Hard lock: no strategy rule, no true engine, no A/B, no CTP, no order API, no official config change.",
            "",
            "## Summary",
            "",
            _md_table(pd.DataFrame([summary])),
            "",
            "## Selected Request",
            "",
            _md_table(selected),
            "",
            "## Tick Fetch Status",
            "",
            _md_table(fetch),
            "",
            "## Window Precheck",
            "",
            _md_table(windows),
            "",
            "## Delivery Audit",
            "",
            _md_table(delivery),
            "",
            "## Gate Status",
            "",
            _md_table(gate),
            "",
            "## Next",
            "",
            "- If three expected files were written, rerun Stage160 and Stage153 immediately.",
            "- A single request passing does not allow feature building or strategy work; full package gates remain blocked until all required requests/windows pass.",
            "",
        ]
    )
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(text, encoding="utf-8")


def _plot_path(curve: pd.DataFrame, summary: dict[str, Any]) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(15, 11), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"], color="#1f77b4", linewidth=1.8)
    axes[0].set_title("Official Path Unchanged; Stage164 One-Request Delivery Status")
    axes[0].set_ylabel("Equity")
    axes[0].grid(alpha=0.25)
    axes[0].text(
        0.01,
        0.95,
        f"files={summary['expected_files_written']}/3 | rows={summary['normalized_row_count']} | windows={summary['window_precheck_pass_count']}/{summary['window_precheck_count']}",
        transform=axes[0].transAxes,
        va="top",
        fontsize=10,
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


def _plot_kline(normalized: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    if normalized.empty:
        axes[0].text(0.5, 0.5, "No normalized bars", ha="center", va="center")
        axes[0].axis("off")
        axes[1].axis("off")
    else:
        data = normalized.copy()
        data["bar_start_ts"] = pd.to_datetime(data["bar_start_ts"], errors="coerce")
        axes[0].plot(data["bar_start_ts"], data["close"], color="#1f77b4", linewidth=1.4, label="close")
        axes[0].fill_between(data["bar_start_ts"], data["low"], data["high"], color="#aec7e8", alpha=0.35, label="low-high")
        axes[0].set_title("Full Request Tick-Aggregated 1m OHLCV")
        axes[0].set_ylabel("Price")
        axes[0].legend()
        axes[0].grid(alpha=0.25)
        axes[1].bar(data["bar_start_ts"], data["volume"], width=0.0007, color="#2ca02c")
        axes[1].set_ylabel("Volume")
        axes[1].grid(alpha=0.25)
        fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(KLINE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_window(windows: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 4.5))
    if windows.empty:
        ax.text(0.5, 0.5, "No mapped windows", ha="center", va="center")
        ax.axis("off")
    else:
        cols = ["observed_bar_count", "positive_volume_bar_count", "coverage_precheck_pass"]
        matrix = windows[cols].to_numpy(dtype=float)
        scale = matrix.copy()
        if scale[:, :2].max() > 0:
            scale[:, :2] = scale[:, :2] / scale[:, :2].max()
        ax.imshow(scale, aspect="auto", cmap=plt.get_cmap("YlGn"), vmin=0, vmax=1)
        ax.set_xticks(np.arange(len(cols)))
        ax.set_xticklabels(cols, rotation=20, ha="right")
        ax.set_yticks(np.arange(len(windows)))
        ax.set_yticklabels(windows["window_type"].tolist())
        ax.set_title("Stage164 Selected Request Window Precheck")
        for r in range(len(windows)):
            for c, col in enumerate(cols):
                ax.text(c, r, str(int(windows.iloc[r][col])), ha="center", va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(WINDOW_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_delivery(delivery: pd.DataFrame) -> None:
    cols = ["raw_written", "normalized_written", "proof_written"]
    matrix = delivery[cols].to_numpy(dtype=float) if not delivery.empty else np.zeros((1, len(cols)))
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.imshow(matrix, aspect="auto", cmap=plt.get_cmap("RdYlGn"), vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(cols)))
    ax.set_xticklabels(cols, rotation=20, ha="right")
    ax.set_yticks([0])
    ax.set_yticklabels(["selected_request"])
    ax.set_title("Stage164 Expected File Delivery Matrix")
    for col_idx, value in enumerate(matrix[0]):
        ax.text(col_idx, 0, int(value), ha="center", va="center", fontsize=12)
    fig.tight_layout()
    fig.savefig(DELIVERY_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(13, 7))
    matrix = gate[["pass_now"]].to_numpy(dtype=float)
    ax.imshow(matrix, aspect="auto", cmap=plt.get_cmap("RdYlGn"), vmin=0, vmax=1)
    ax.set_yticks(np.arange(len(gate)))
    ax.set_yticklabels(gate["gate_id"].tolist())
    ax.set_xticks([0])
    ax.set_xticklabels(["pass_now"])
    ax.set_title("Stage164 Gate Status Matrix")
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
    raw_ticks, fetch_status = _fetch_ticks(selected, credential)
    normalized = _aggregate_ticks(selected, raw_ticks)
    window_precheck = _window_precheck(selected, normalized)
    delivery, delivery_row = _write_delivery(selected, raw_ticks, normalized, fetch_status, window_precheck)
    decision = (
        "stage164_one_request_tick_aggregate_delivery_written_run_stage160_153_no_rule"
        if int(delivery_row["expected_files_written"]) == 3
        else "stage164_one_request_tick_aggregate_delivery_not_written_no_rule"
    )
    summary: dict[str, Any] = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": created_at,
        "line_id": LINE_ID,
        "decision": decision,
        "next_best_action": "rerun_stage160_then_stage153" if int(delivery_row["expected_files_written"]) == 3 else "inspect_delivery_blocker_or_wait_authorized_package",
        "request_id": str(selected["request_id"]),
        "vt_symbol": str(selected["vt_symbol"]),
        "exchange": str(selected["exchange"]),
        "request_start_ts": str(selected["request_start_ts"]),
        "request_end_ts": str(selected["request_end_ts"]),
        "credential_present": int(fetch_status["credential_present"]),
        "credential_username_len": int(credential.get("username_len", 0)),
        "credential_password_len": int(credential.get("password_len", 0)),
        "tick_fetch_status": str(fetch_status["tick_fetch_status"]),
        "raw_tick_row_count": int(len(raw_ticks)),
        "normalized_row_count": int(len(normalized)),
        "positive_volume_row_count": int(pd.to_numeric(normalized.get("volume", pd.Series(dtype=float)), errors="coerce").fillna(0).gt(0).sum()),
        "positive_turnover_row_count": int(pd.to_numeric(normalized.get("turnover", pd.Series(dtype=float)), errors="coerce").fillna(0).gt(0).sum()),
        "window_precheck_count": int(len(window_precheck)),
        "window_precheck_pass_count": int(window_precheck["coverage_precheck_pass"].sum()) if not window_precheck.empty else 0,
        "write_incoming_enabled": int(WRITE_INCOMING),
        "expected_files_written": int(delivery_row["expected_files_written"]),
        "raw_written": int(delivery_row["raw_written"]),
        "normalized_written": int(delivery_row["normalized_written"]),
        "proof_written": int(delivery_row["proof_written"]),
        "write_blocker": str(delivery_row.get("write_blocker", "")),
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
        "side_effect_count": int(delivery_row["expected_files_written"] > 0),
        "visual_output_count": 5,
    }
    summary.update(metrics)
    gate = _gate_status(summary)

    _write_csv(pd.DataFrame([summary]), SUMMARY_OUT)
    _write_csv(selected_frame, SELECTED_REQUEST_OUT)
    _write_csv(pd.DataFrame([fetch_status]), FETCH_STATUS_OUT)
    _write_csv(window_precheck, WINDOW_PRECHECK_OUT)
    _write_csv(raw_ticks.head(500), RAW_SAMPLE_OUT)
    _write_csv(normalized.head(500), NORMALIZED_SAMPLE_OUT)
    _write_csv(delivery, DELIVERY_AUDIT_OUT)
    _write_csv(gate, GATE_OUT)
    _write_json(
        DECISION_OUT,
        {
            "decision": decision,
            "summary": summary,
            "outputs": {
                "summary": SUMMARY_OUT,
                "selected_request": SELECTED_REQUEST_OUT,
                "tick_fetch_status": FETCH_STATUS_OUT,
                "window_precheck": WINDOW_PRECHECK_OUT,
                "raw_tick_sample": RAW_SAMPLE_OUT,
                "normalized_sample": NORMALIZED_SAMPLE_OUT,
                "delivery_audit": DELIVERY_AUDIT_OUT,
                "gate_status": GATE_OUT,
                "report": REPORT_OUT,
                "charts": [PATH_CHART_OUT, KLINE_CHART_OUT, WINDOW_CHART_OUT, DELIVERY_CHART_OUT, GATE_CHART_OUT],
            },
        },
    )
    _write_report(summary, selected_frame, pd.DataFrame([fetch_status]), window_precheck, delivery, gate)
    _plot_path(curve, summary)
    _plot_kline(normalized)
    _plot_window(window_precheck)
    _plot_delivery(delivery)
    _plot_gate(gate)
    print(json.dumps(_json_safe(summary), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
