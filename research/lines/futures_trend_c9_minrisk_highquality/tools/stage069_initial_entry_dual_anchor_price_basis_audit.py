from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import logging
import math
import os
from pathlib import Path
import sys
import time
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage069"
MODEL_TAG = "stage069_initial_entry_dual_anchor_price_basis_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage069_c9_minrisk_initial_entry_dual_anchor_price_basis_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage068_initial_entry_tick_coverage_audit as s068
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage069_initial_entry_dual_anchor_price_basis_audit"
RAW_TICK_DIR = OUTPUT_DIR / "raw_tick"

STAGE068_DIR = LINE_DIR / "outputs" / "stage068_initial_entry_tick_coverage_audit"
STAGE068_PLAN_IN = (
    STAGE068_DIR
    / "qmt_roll_stage068_c9_minrisk_initial_entry_tick_coverage_audit_initial_entry_tick_plan_"
    "stage068_initial_entry_tick_coverage_audit_v1.csv"
)
STAGE068_FEATURES_IN = (
    STAGE068_DIR
    / "qmt_roll_stage068_c9_minrisk_initial_entry_tick_coverage_audit_initial_entry_microstructure_features_"
    "stage068_initial_entry_tick_coverage_audit_v1.csv"
)

DUAL_ANCHOR_PLAN_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dual_anchor_plan_{MODEL_TAG}.csv"
DOWNLOAD_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_download_status_{MODEL_TAG}.csv"
ANCHOR_FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_anchor_price_features_{MODEL_TAG}.csv"
TRADE_COMPARISON_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_anchor_comparison_{MODEL_TAG}.csv"
COVERAGE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_summary_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_price_basis_chart_{MODEL_TAG}.png"
SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_scan_vs_proxy_delta_scatter_{MODEL_TAG}.png"
STATUS_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_anchor_status_chart_{MODEL_TAG}.png"
ATLAS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dual_anchor_tick_atlas_{MODEL_TAG}.png"

INITIAL_CAPITAL = 150_000.0
PRICE_TOL = 1e-8
NEAR_R_TOL = float(os.getenv("STAGE069_NEAR_R_TOL", "0.05"))
DOWNLOAD_WINDOW_MINUTES = int(os.getenv("STAGE069_DOWNLOAD_WINDOW_MINUTES", "3"))
MAX_EVENTS = int(os.getenv("STAGE069_MAX_EVENTS", "0"))
MAX_SECONDS_PER_EVENT = int(os.getenv("STAGE069_MAX_SECONDS_PER_EVENT", "60"))
TICK_DATA_LENGTH = int(os.getenv("STAGE069_TICK_DATA_LENGTH", "12000"))
ENABLE_TQSDK = os.getenv("STAGE069_ENABLE_TQSDK", "0").strip() == "1"
DOWNLOAD_ROLES = {
    item.strip()
    for item in os.getenv("STAGE069_DOWNLOAD_ROLES", "price_proxy_anchor").split(",")
    if item.strip()
}


@dataclass(frozen=True)
class TickRef:
    event_key: str
    anchor_role: str
    path: Path
    source: str


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s068._md_table(frame, max_rows=max_rows)


def _timestamp(value: Any) -> pd.Timestamp:
    return s068._timestamp(value)


def _safe_num(series: pd.Series) -> pd.Series:
    return s068._safe_num(series)


def _normalize_tqsdk_datetime(value: Any) -> pd.Timestamp:
    return s068._normalize_tqsdk_datetime(value)


def _target_minute(anchor_time: Any) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = _timestamp(anchor_time).floor("min")
    return start, start + pd.Timedelta(minutes=1)


def _load_stage068() -> pd.DataFrame:
    plan = _read_csv(STAGE068_PLAN_IN)
    features = _read_csv(STAGE068_FEATURES_IN)
    keep = [
        "event_key",
        "tick_file_path",
        "microstructure_ready",
        "tick_file_exists",
        "first_mid_delta_r",
        "median_mid_delta_r",
    ]
    features = features[[col for col in keep if col in features.columns]].copy()
    features.rename(
        columns={
            "tick_file_path": "stage068_scan_tick_file_path",
            "microstructure_ready": "stage068_scan_ready",
            "tick_file_exists": "stage068_scan_tick_file_exists",
            "first_mid_delta_r": "stage068_scan_first_mid_delta_r",
            "median_mid_delta_r": "stage068_scan_median_mid_delta_r",
        },
        inplace=True,
    )
    data = plan.merge(features, on="event_key", how="left")
    data["download_anchor_time"] = pd.to_datetime(data["download_anchor_time"], errors="coerce")
    data["raw_proxy_anchor_time"] = pd.to_datetime(data["raw_proxy_anchor_time"], errors="coerce")
    data["official_open_price"] = _safe_num(data["official_open_price"])
    data["raw_price"] = _safe_num(data["raw_price"]) if "raw_price" in data.columns else np.nan
    data["risk_price"] = _safe_num(data["risk_price"])
    data["realized_pnl"] = _safe_num(data["realized_pnl"]).fillna(0.0)
    data = data.sort_values(["download_anchor_time", "official_open_trade_id"]).reset_index(drop=True)
    if MAX_EVENTS > 0:
        data = data.head(MAX_EVENTS).copy()
    return data


def _tq_symbol(vt_symbol: str) -> str:
    return s068._tq_symbol(vt_symbol)


def _proxy_tick_path(row: pd.Series) -> Path:
    vt_symbol = str(row["vt_symbol"])
    code, exchange = vt_symbol.split(".", 1)
    anchor = _timestamp(row["anchor_time"])
    trade_id = str(row["official_open_trade_id"]).replace(".", "_")
    name = f"{code}_{anchor:%Y%m%d_%H%M}_candidate_{int(row['candidate_index'])}_{trade_id}_{row['anchor_role']}_tick_backtest.csv"
    return RAW_TICK_DIR / str(row["anchor_role"]) / exchange / name


def _build_dual_anchor_plan() -> pd.DataFrame:
    base = _load_stage068()
    rows: list[dict[str, Any]] = []
    for _, row in base.iterrows():
        common = {
            "event_key": row["event_key"],
            "official_open_trade_id": row["official_open_trade_id"],
            "candidate_index": row["candidate_index"],
            "vt_symbol": row["vt_symbol"],
            "tq_symbol": row.get("tq_symbol", _tq_symbol(str(row["vt_symbol"]))),
            "direction": row["direction"],
            "direction_sign": row.get("direction_sign", np.nan),
            "official_open_date": row.get("official_open_date", ""),
            "official_open_price": row.get("official_open_price", np.nan),
            "raw_price": row.get("raw_price", np.nan),
            "raw_source": row.get("raw_source", ""),
            "risk_price": row.get("risk_price", np.nan),
            "realized_pnl": row.get("realized_pnl", 0.0),
            "normalized_product": row.get("normalized_product", ""),
            "product_family": row.get("product_family", ""),
            "timestamp_alignment_class": row.get("timestamp_alignment_class", ""),
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "official_live_version": OFFICIAL_LIVE_VERSION,
        }
        scan_tick_path = str(row.get("stage068_scan_tick_file_path", ""))
        rows.append(
            {
                **common,
                "anchor_role": "event_scan_anchor",
                "anchor_time": row["download_anchor_time"],
                "anchor_source": row.get("anchor_source", "stage043_replay_open_datetime"),
                "anchor_role_note": "official event scan starts here; not necessarily the raw execution price proxy",
                "source_stage": "Stage068/Stage043",
                "tick_path": scan_tick_path,
                "reuse_external_tick_path": True,
            }
        )
        if pd.notna(row["raw_proxy_anchor_time"]):
            rows.append(
                {
                    **common,
                    "anchor_role": "price_proxy_anchor",
                    "anchor_time": row["raw_proxy_anchor_time"],
                    "anchor_source": row.get("raw_source", "raw_proxy"),
                    "anchor_role_note": "raw proxy timestamp used to explain official open price",
                    "source_stage": "Stage040/041/043 raw proxy",
                    "tick_path": "",
                    "reuse_external_tick_path": False,
                }
            )
    plan = pd.DataFrame(rows)
    plan["anchor_time"] = pd.to_datetime(plan["anchor_time"], errors="coerce")
    plan["download_start_dt"] = plan["anchor_time"] - pd.Timedelta(minutes=DOWNLOAD_WINDOW_MINUTES)
    plan["download_end_dt"] = plan["anchor_time"] + pd.Timedelta(minutes=DOWNLOAD_WINDOW_MINUTES)
    plan["target_minute_start"] = plan["anchor_time"].dt.floor("min")
    plan["target_minute_end"] = plan["target_minute_start"] + pd.Timedelta(minutes=1)
    for idx, row in plan.iterrows():
        if str(row.get("tick_path", "")) == "" or str(row.get("tick_path", "")).lower() == "nan":
            plan.at[idx, "tick_path"] = str(_proxy_tick_path(row))
    return plan.sort_values(["anchor_time", "official_open_trade_id", "anchor_role"]).reset_index(drop=True)


def _get_credentials() -> tuple[str, str, dict[str, Any]]:
    return s068._get_credentials()


def _download_ticks(row: pd.Series, username: str, password: str, credential_status: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(row["tick_path"]))
    status: dict[str, Any] = {
        "event_key": row["event_key"],
        "official_open_trade_id": row["official_open_trade_id"],
        "candidate_index": row["candidate_index"],
        "anchor_role": row["anchor_role"],
        "vt_symbol": row["vt_symbol"],
        "tq_symbol": row["tq_symbol"],
        "anchor_time": row["anchor_time"],
        "download_start_dt": row["download_start_dt"],
        "download_end_dt": row["download_end_dt"],
        "credential_status": credential_status.get("status", ""),
        "download_status": "unknown",
        "tick_rows": 0,
        "target_minute_rows": 0,
        "valid_top_book_rows": 0,
        "tick_path": str(path),
        "message": "",
    }
    if path.exists() and path.stat().st_size > 0:
        try:
            ticks = pd.read_csv(path, encoding="utf-8-sig")
            status.update(_evaluate_ticks(row, ticks))
            status["download_status"] = "cached_stage068" if bool(row.get("reuse_external_tick_path", False)) else "cached_stage069"
            return status
        except Exception as exc:
            status["message"] = f"cached_read_failed:{type(exc).__name__}:{exc}"

    if row["anchor_role"] not in DOWNLOAD_ROLES:
        status["download_status"] = "planned_not_downloaded_role_disabled"
        return status
    if not ENABLE_TQSDK:
        status["download_status"] = "planned_not_downloaded"
        return status
    if not username or not password:
        status["download_status"] = "missing_credentials"
        return status
    if pd.isna(_timestamp(row["anchor_time"])):
        status["download_status"] = "missing_anchor_time"
        return status

    try:
        from tqsdk import BacktestFinished, TqApi, TqAuth, TqBacktest, TqSim
    except Exception as exc:
        status["download_status"] = "import_failed"
        status["message"] = repr(exc)[:500]
        return status

    path.parent.mkdir(parents=True, exist_ok=True)
    logging.getLogger().setLevel(logging.WARNING)
    logging.getLogger("tqsdk").setLevel(logging.WARNING)
    rows: list[dict[str, Any]] = []
    seen_keys: set[tuple[Any, Any]] = set()
    started = time.time()
    api = None
    try:
        api = TqApi(
            TqSim(),
            backtest=TqBacktest(
                start_dt=_timestamp(row["download_start_dt"]).to_pydatetime(),
                end_dt=_timestamp(row["download_end_dt"]).to_pydatetime(),
            ),
            auth=TqAuth(username, password),
            disable_print=True,
        )
        ticks = api.get_tick_serial(str(row["tq_symbol"]), data_length=TICK_DATA_LENGTH)
        while True:
            if time.time() - started > MAX_SECONDS_PER_EVENT:
                status["download_status"] = "timeout"
                status["message"] = f"timeout_after_{MAX_SECONDS_PER_EVENT}s"
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
            record = {
                "event_key": row["event_key"],
                "official_open_trade_id": row["official_open_trade_id"],
                "candidate_index": row["candidate_index"],
                "anchor_role": row["anchor_role"],
                "vt_symbol": row["vt_symbol"],
                "tq_symbol": row["tq_symbol"],
                "tick_datetime": tick_dt,
            }
            for key_name, value in item.items():
                if key_name == "datetime":
                    continue
                record[str(key_name)] = value
            rows.append(record)
    except BacktestFinished:
        status["download_status"] = "extracted"
    except Exception as exc:
        status["download_status"] = "failed"
        status["message"] = repr(exc)[:500]
    finally:
        if api is not None:
            api.close()

    data = pd.DataFrame(rows)
    if not data.empty:
        data["tick_datetime"] = pd.to_datetime(data["tick_datetime"], errors="coerce")
        data = data.dropna(subset=["tick_datetime"])
        dedup_cols = ["event_key", "anchor_role", "tick_datetime", "last_price"] if "last_price" in data.columns else ["event_key", "anchor_role", "tick_datetime"]
        data = data.drop_duplicates(dedup_cols, keep="last").sort_values(["event_key", "anchor_role", "tick_datetime"])
        data.to_csv(path, index=False, encoding="utf-8-sig")
    if status["download_status"] == "unknown":
        status["download_status"] = "extracted" if not data.empty else "empty"
    status.update(_evaluate_ticks(row, data))
    return status


def _evaluate_ticks(row: pd.Series, ticks: pd.DataFrame) -> dict[str, Any]:
    result = {"tick_rows": int(len(ticks)), "target_minute_rows": 0, "valid_top_book_rows": 0}
    if ticks.empty or "tick_datetime" not in ticks.columns:
        return result
    data = ticks.copy()
    data["tick_datetime"] = pd.to_datetime(data["tick_datetime"], errors="coerce")
    data = data.dropna(subset=["tick_datetime"]).sort_values("tick_datetime")
    start, end = _target_minute(row["anchor_time"])
    target = data[(data["tick_datetime"] >= start) & (data["tick_datetime"] < end)].copy()
    result["target_minute_rows"] = int(len(target))
    if target.empty:
        return result
    for col in ["ask_price1", "bid_price1"]:
        target[col] = _safe_num(target[col]) if col in target.columns else np.nan
    valid = target[
        (target["ask_price1"] > 0)
        & (target["bid_price1"] > 0)
        & (target["ask_price1"] < 1e100)
        & (target["bid_price1"] < 1e100)
        & (target["ask_price1"] >= target["bid_price1"])
    ]
    result["valid_top_book_rows"] = int(len(valid))
    return result


def _download_or_check(plan: pd.DataFrame) -> pd.DataFrame:
    username, password, credential_status = _get_credentials()
    rows = [_download_ticks(row, username, password, credential_status) for _, row in plan.iterrows()]
    status = pd.DataFrame(rows)
    status["tick_file_exists_after"] = status["tick_path"].map(lambda p: Path(str(p)).exists())
    return status


def _extract_anchor_features(row: pd.Series) -> dict[str, Any]:
    base: dict[str, Any] = {
        "event_key": row["event_key"],
        "official_open_trade_id": row["official_open_trade_id"],
        "candidate_index": row["candidate_index"],
        "anchor_role": row["anchor_role"],
        "vt_symbol": row["vt_symbol"],
        "direction": row["direction"],
        "official_open_date": row.get("official_open_date", ""),
        "anchor_time": row["anchor_time"],
        "anchor_source": row.get("anchor_source", ""),
        "official_open_price": row.get("official_open_price", np.nan),
        "raw_price": row.get("raw_price", np.nan),
        "risk_price": row.get("risk_price", np.nan),
        "realized_pnl": row.get("realized_pnl", 0.0),
        "normalized_product": row.get("normalized_product", ""),
        "product_family": row.get("product_family", ""),
        "timestamp_alignment_class": row.get("timestamp_alignment_class", ""),
        "tick_file_path": row["tick_path"],
        "tick_file_exists": Path(str(row["tick_path"])).exists(),
        "tick_rows_total": 0,
        "tick_rows_target_minute": 0,
        "valid_top_book_rows": 0,
        "anchor_ready": False,
        "first_mid_price": np.nan,
        "median_mid_price": np.nan,
        "first_mid_delta": np.nan,
        "median_mid_delta": np.nan,
        "first_mid_delta_r": np.nan,
        "median_mid_delta_r": np.nan,
        "min_abs_price_delta": np.nan,
        "min_abs_price_delta_r": np.nan,
        "nearest_price_field": "",
        "nearest_price_value": np.nan,
        "nearest_price_time": "",
        "price_exact_any": False,
        "price_near_r": False,
        "official_open_inside_first_spread": np.nan,
        "official_open_inside_any_spread": False,
        "median_spread_r": np.nan,
        "median_depth1": np.nan,
    }
    path = Path(str(row["tick_path"]))
    if not path.exists() or path.stat().st_size == 0:
        return base
    try:
        ticks = pd.read_csv(path, encoding="utf-8-sig")
    except Exception as exc:
        base["tick_read_error"] = f"{type(exc).__name__}:{exc}"
        return base
    if ticks.empty or "tick_datetime" not in ticks.columns:
        return base

    ticks["tick_datetime"] = pd.to_datetime(ticks["tick_datetime"], errors="coerce")
    ticks = ticks.dropna(subset=["tick_datetime"]).sort_values("tick_datetime")
    base["tick_rows_total"] = int(len(ticks))
    start, end = _target_minute(row["anchor_time"])
    target = ticks[(ticks["tick_datetime"] >= start) & (ticks["tick_datetime"] < end)].copy()
    base["tick_rows_target_minute"] = int(len(target))
    if target.empty:
        return base
    for col in ["last_price", "ask_price1", "ask_volume1", "bid_price1", "bid_volume1"]:
        target[col] = _safe_num(target[col]) if col in target.columns else np.nan
    valid = target[
        (target["ask_price1"] > 0)
        & (target["bid_price1"] > 0)
        & (target["ask_price1"] < 1e100)
        & (target["bid_price1"] < 1e100)
        & (target["ask_price1"] >= target["bid_price1"])
    ].copy()
    base["valid_top_book_rows"] = int(len(valid))
    if valid.empty:
        return base
    valid["mid_price"] = (valid["ask_price1"] + valid["bid_price1"]) / 2.0
    valid["spread"] = valid["ask_price1"] - valid["bid_price1"]
    valid["depth1"] = valid["ask_volume1"].fillna(0) + valid["bid_volume1"].fillna(0)
    official_price = float(row["official_open_price"]) if pd.notna(row["official_open_price"]) else np.nan
    risk_price = float(row["risk_price"]) if pd.notna(row["risk_price"]) and float(row["risk_price"]) > 0 else np.nan
    if pd.isna(official_price):
        return base
    base["anchor_ready"] = True
    first_mid_delta = float(valid["mid_price"].iloc[0] - official_price)
    median_mid_delta = float(valid["mid_price"].median() - official_price)
    base["first_mid_price"] = float(valid["mid_price"].iloc[0])
    base["median_mid_price"] = float(valid["mid_price"].median())
    base["first_mid_delta"] = first_mid_delta
    base["median_mid_delta"] = median_mid_delta
    if pd.notna(risk_price):
        base["first_mid_delta_r"] = float(first_mid_delta / risk_price)
        base["median_mid_delta_r"] = float(median_mid_delta / risk_price)
        base["median_spread_r"] = float((valid["spread"] / risk_price).median())
    base["median_depth1"] = float(valid["depth1"].median())
    first_row = valid.iloc[0]
    base["official_open_inside_first_spread"] = int(first_row["bid_price1"] <= official_price <= first_row["ask_price1"])
    base["official_open_inside_any_spread"] = bool(((valid["bid_price1"] <= official_price) & (official_price <= valid["ask_price1"])).any())

    candidates: list[tuple[float, str, float, pd.Timestamp]] = []
    for field in ["last_price", "bid_price1", "ask_price1", "mid_price"]:
        values = valid[["tick_datetime", field]].dropna()
        for _, item in values.iterrows():
            price = float(item[field])
            candidates.append((abs(price - official_price), field, price, pd.Timestamp(item["tick_datetime"])))
    if candidates:
        best = min(candidates, key=lambda x: x[0])
        base["min_abs_price_delta"] = float(best[0])
        base["nearest_price_field"] = best[1]
        base["nearest_price_value"] = float(best[2])
        base["nearest_price_time"] = best[3].strftime("%Y-%m-%d %H:%M:%S")
        if pd.notna(risk_price):
            base["min_abs_price_delta_r"] = float(best[0] / risk_price)
            base["price_near_r"] = bool(best[0] / risk_price <= NEAR_R_TOL)
        base["price_exact_any"] = bool(best[0] <= PRICE_TOL)
    return base


def _build_anchor_features(plan: pd.DataFrame) -> pd.DataFrame:
    rows = [_extract_anchor_features(row) for _, row in plan.iterrows()]
    features = pd.DataFrame(rows)
    for col in ["anchor_ready", "tick_file_exists", "price_exact_any", "price_near_r", "official_open_inside_any_spread"]:
        if col in features.columns:
            features[col] = features[col].astype(bool)
    return features


def _build_trade_comparison(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for event_key, group in features.groupby("event_key", dropna=False):
        scan = group[group["anchor_role"].eq("event_scan_anchor")]
        proxy = group[group["anchor_role"].eq("price_proxy_anchor")]
        scan_row = scan.iloc[0] if not scan.empty else pd.Series(dtype=object)
        proxy_row = proxy.iloc[0] if not proxy.empty else pd.Series(dtype=object)
        scan_delta = pd.to_numeric(pd.Series([scan_row.get("min_abs_price_delta_r")]), errors="coerce").iloc[0]
        proxy_delta = pd.to_numeric(pd.Series([proxy_row.get("min_abs_price_delta_r")]), errors="coerce").iloc[0]
        scan_ready = bool(scan_row.get("anchor_ready", False))
        proxy_ready = bool(proxy_row.get("anchor_ready", False))
        scan_exact = bool(scan_row.get("price_exact_any", False))
        proxy_exact = bool(proxy_row.get("price_exact_any", False))
        if proxy_exact:
            basis_class = "price_proxy_anchor_exact"
        elif scan_exact:
            basis_class = "event_scan_anchor_exact"
        elif proxy_ready and scan_ready and pd.notna(proxy_delta) and pd.notna(scan_delta) and proxy_delta < scan_delta:
            basis_class = "price_proxy_anchor_closer"
        elif scan_ready and proxy_ready:
            basis_class = "paired_no_proxy_improvement"
        elif scan_ready and not proxy_ready:
            basis_class = "scan_ready_proxy_pending"
        elif proxy_ready and not scan_ready:
            basis_class = "proxy_ready_scan_pending"
        else:
            basis_class = "both_pending"
        anchor_gap_minutes = np.nan
        if pd.notna(scan_row.get("anchor_time", pd.NaT)) and pd.notna(proxy_row.get("anchor_time", pd.NaT)):
            anchor_gap_minutes = float(
                abs((_timestamp(scan_row.get("anchor_time")) - _timestamp(proxy_row.get("anchor_time"))).total_seconds()) / 60.0
            )
        rows.append(
            {
                "event_key": event_key,
                "official_open_trade_id": scan_row.get("official_open_trade_id", proxy_row.get("official_open_trade_id", "")),
                "candidate_index": scan_row.get("candidate_index", proxy_row.get("candidate_index", np.nan)),
                "vt_symbol": scan_row.get("vt_symbol", proxy_row.get("vt_symbol", "")),
                "direction": scan_row.get("direction", proxy_row.get("direction", "")),
                "official_open_date": scan_row.get("official_open_date", proxy_row.get("official_open_date", "")),
                "official_open_price": scan_row.get("official_open_price", proxy_row.get("official_open_price", np.nan)),
                "raw_price": scan_row.get("raw_price", proxy_row.get("raw_price", np.nan)),
                "risk_price": scan_row.get("risk_price", proxy_row.get("risk_price", np.nan)),
                "realized_pnl": scan_row.get("realized_pnl", proxy_row.get("realized_pnl", 0.0)),
                "normalized_product": scan_row.get("normalized_product", proxy_row.get("normalized_product", "")),
                "product_family": scan_row.get("product_family", proxy_row.get("product_family", "")),
                "timestamp_alignment_class": scan_row.get("timestamp_alignment_class", proxy_row.get("timestamp_alignment_class", "")),
                "scan_anchor_time": scan_row.get("anchor_time", ""),
                "proxy_anchor_time": proxy_row.get("anchor_time", ""),
                "anchor_gap_minutes": anchor_gap_minutes,
                "scan_ready": scan_ready,
                "proxy_ready": proxy_ready,
                "scan_price_exact_any": scan_exact,
                "proxy_price_exact_any": proxy_exact,
                "scan_min_abs_price_delta_r": scan_delta,
                "proxy_min_abs_price_delta_r": proxy_delta,
                "scan_first_mid_delta_r": scan_row.get("first_mid_delta_r", np.nan),
                "proxy_first_mid_delta_r": proxy_row.get("first_mid_delta_r", np.nan),
                "scan_inside_any_spread": bool(scan_row.get("official_open_inside_any_spread", False)),
                "proxy_inside_any_spread": bool(proxy_row.get("official_open_inside_any_spread", False)),
                "price_basis_class": basis_class,
                "proxy_improves_abs_delta_r": bool(
                    proxy_ready and scan_ready and pd.notna(proxy_delta) and pd.notna(scan_delta) and proxy_delta < scan_delta
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["scan_anchor_time", "event_key"]).reset_index(drop=True)


def _coverage_summary(anchor_features: pd.DataFrame, comparison: pd.DataFrame, status: pd.DataFrame) -> pd.DataFrame:
    status_counts = status["download_status"].value_counts(dropna=False).to_dict() if not status.empty else {}
    rows: list[dict[str, Any]] = []
    groups = [
        ("all_anchor_rows", anchor_features),
        ("event_scan_anchor", anchor_features[anchor_features["anchor_role"].eq("event_scan_anchor")]),
        ("price_proxy_anchor", anchor_features[anchor_features["anchor_role"].eq("price_proxy_anchor")]),
        ("anchor_ready", anchor_features[anchor_features["anchor_ready"]]),
        ("price_exact_any", anchor_features[anchor_features["price_exact_any"]]),
    ]
    for bucket, data in groups:
        rows.append(
            {
                "bucket": bucket,
                "row_count": int(len(data)),
                "trade_count": int(data["event_key"].nunique()) if not data.empty else 0,
                "anchor_ready_count": int(data["anchor_ready"].sum()) if not data.empty else 0,
                "price_exact_count": int(data["price_exact_any"].sum()) if not data.empty else 0,
                "inside_any_spread_count": int(data["official_open_inside_any_spread"].sum()) if not data.empty else 0,
                "median_abs_delta_r": float(data["min_abs_price_delta_r"].median())
                if not data.empty and data["min_abs_price_delta_r"].notna().any()
                else np.nan,
                "net_realized_pnl": float(data.drop_duplicates("event_key")["realized_pnl"].sum()) if not data.empty else 0.0,
                "download_status_counts": json.dumps(_json_safe(status_counts), ensure_ascii=False) if bucket == "all_anchor_rows" else "",
            }
        )
    class_rows = (
        comparison.groupby("price_basis_class", dropna=False)
        .agg(
            row_count=("event_key", "size"),
            net_realized_pnl=("realized_pnl", "sum"),
            scan_ready_count=("scan_ready", "sum"),
            proxy_ready_count=("proxy_ready", "sum"),
            proxy_improves_count=("proxy_improves_abs_delta_r", "sum"),
        )
        .reset_index()
        .rename(columns={"price_basis_class": "bucket"})
    )
    class_rows["trade_count"] = class_rows["row_count"]
    for col in ["anchor_ready_count", "price_exact_count", "inside_any_spread_count", "median_abs_delta_r", "download_status_counts"]:
        class_rows[col] = np.nan
    class_rows = class_rows[
        ["bucket", "row_count", "trade_count", "anchor_ready_count", "price_exact_count", "inside_any_spread_count", "median_abs_delta_r", "net_realized_pnl", "download_status_counts"]
    ]
    return pd.concat([pd.DataFrame(rows), class_rows], ignore_index=True)


def _official_curve() -> pd.DataFrame:
    return s068._official_curve()


def _official_metrics() -> dict[str, Any]:
    return s068._official_metrics()


def _plot_path(comparison: pd.DataFrame) -> None:
    curve = _official_curve()
    events = comparison.copy()
    events["scan_anchor_time"] = pd.to_datetime(events["scan_anchor_time"], errors="coerce")
    events = events.dropna(subset=["scan_anchor_time"]).sort_values("scan_anchor_time")
    classes = sorted(events["price_basis_class"].dropna().unique())
    palette = {
        "price_proxy_anchor_exact": "#009e73",
        "event_scan_anchor_exact": "#0072b2",
        "price_proxy_anchor_closer": "#56b4e9",
        "paired_no_proxy_improvement": "#cc79a7",
        "scan_ready_proxy_pending": "#d55e00",
        "both_pending": "#999999",
    }
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=False)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#0072b2", linewidth=2.0)
    for cls in classes:
        data = events[events["price_basis_class"].eq(cls)]
        if data.empty:
            continue
        axes[0].scatter(
            data["scan_anchor_time"],
            np.interp(data["scan_anchor_time"].astype("int64"), curve["date"].astype("int64"), curve["account_equity"] / 1_000_000),
            s=34,
            color=palette.get(cls, "#999999"),
            label=cls,
            alpha=0.72,
        )
    axes[0].set_title(f"{STAGE} official path by scan/proxy price-basis class")
    axes[0].set_ylabel("Equity (million CNY)")
    axes[0].grid(alpha=0.25)
    axes[0].legend(loc="upper left", fontsize=7)
    for cls in classes:
        data = events[events["price_basis_class"].eq(cls)].copy()
        data["cum_pnl"] = data["realized_pnl"].cumsum()
        axes[1].plot(data["scan_anchor_time"], data["cum_pnl"] / 10_000, marker="o", linewidth=1.6, color=palette.get(cls, "#999999"), label=cls)
    axes[1].axhline(0, color="black", linewidth=0.8)
    axes[1].set_title("Initial-entry PnL contribution by price-basis class")
    axes[1].set_ylabel("Cumulative PnL (10k CNY)")
    axes[1].grid(alpha=0.25)
    axes[1].legend(loc="upper left", fontsize=7)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_scatter(comparison: pd.DataFrame) -> None:
    paired = comparison[comparison["scan_ready"] & comparison["proxy_ready"]].copy()
    fig, ax = plt.subplots(figsize=(8, 7))
    if paired.empty:
        ax.text(0.5, 0.5, "No paired scan/proxy ready rows", ha="center", va="center", fontsize=13)
        ax.set_axis_off()
    else:
        x = paired["scan_min_abs_price_delta_r"].astype(float)
        y = paired["proxy_min_abs_price_delta_r"].astype(float)
        ax.scatter(x, y, s=90, c=paired["realized_pnl"], cmap="RdYlGn", edgecolor="black", linewidth=0.5)
        lim = float(np.nanmax([x.max(), y.max(), 0.1]))
        ax.plot([0, lim], [0, lim], color="black", linestyle="--", linewidth=1.0)
        ax.axhline(NEAR_R_TOL, color="#999999", linestyle=":", linewidth=1.0)
        ax.axvline(NEAR_R_TOL, color="#999999", linestyle=":", linewidth=1.0)
        for _, row in paired.iterrows():
            ax.text(row["scan_min_abs_price_delta_r"], row["proxy_min_abs_price_delta_r"], str(row["candidate_index"]), fontsize=8)
        ax.set_xlabel("event scan anchor min abs price delta / R")
        ax.set_ylabel("price proxy anchor min abs price delta / R")
        ax.set_title("Scan anchor vs raw price-proxy anchor price basis")
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(SCATTER_OUT, dpi=180)
    plt.close(fig)


def _plot_status(anchor_features: pd.DataFrame, status: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    role_ready = (
        anchor_features.groupby("anchor_role", as_index=False)
        .agg(anchor_rows=("event_key", "size"), ready=("anchor_ready", "sum"), exact=("price_exact_any", "sum"))
        .sort_values("anchor_role")
    )
    x = np.arange(len(role_ready))
    axes[0].bar(x - 0.2, role_ready["anchor_rows"], width=0.2, label="rows", color="#999999")
    axes[0].bar(x, role_ready["ready"], width=0.2, label="ready", color="#0072b2")
    axes[0].bar(x + 0.2, role_ready["exact"], width=0.2, label="price exact", color="#009e73")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(role_ready["anchor_role"], rotation=20, ha="right")
    axes[0].set_title("Anchor role readiness")
    axes[0].legend(fontsize=8)
    counts = status["download_status"].value_counts() if "download_status" in status.columns else pd.Series(dtype=int)
    axes[1].bar(counts.index.astype(str), counts.values, color="#d55e00", alpha=0.78)
    axes[1].set_title("Download/cache status")
    axes[1].tick_params(axis="x", rotation=30)
    axes[1].grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(STATUS_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_atlas(anchor_features: pd.DataFrame, comparison: pd.DataFrame) -> None:
    paired_keys = comparison[comparison["scan_ready"] | comparison["proxy_ready"]]["event_key"].head(6).tolist()
    if not paired_keys:
        paired_keys = comparison["event_key"].head(6).tolist()
    rows = anchor_features[anchor_features["event_key"].isin(paired_keys)].copy()
    rows["anchor_role_order"] = rows["anchor_role"].map({"event_scan_anchor": 0, "price_proxy_anchor": 1}).fillna(9)
    rows = rows.sort_values(["event_key", "anchor_role_order"])
    n_events = len(paired_keys)
    fig, axes = plt.subplots(n_events, 2, figsize=(16, max(4, 2.8 * n_events)), squeeze=False)
    for i, event_key in enumerate(paired_keys):
        subset = rows[rows["event_key"].eq(event_key)]
        for j, role in enumerate(["event_scan_anchor", "price_proxy_anchor"]):
            ax = axes[i, j]
            row_df = subset[subset["anchor_role"].eq(role)]
            if row_df.empty:
                ax.text(0.5, 0.5, "missing role", ha="center", va="center")
                ax.set_axis_off()
                continue
            row = row_df.iloc[0]
            path = Path(str(row["tick_file_path"]))
            if path.exists():
                ticks = pd.read_csv(path, encoding="utf-8-sig")
                ticks["tick_datetime"] = pd.to_datetime(ticks["tick_datetime"], errors="coerce")
                start, end = _target_minute(row["anchor_time"])
                target = ticks[(ticks["tick_datetime"] >= start) & (ticks["tick_datetime"] < end)].copy()
                for col in ["last_price", "ask_price1", "bid_price1"]:
                    target[col] = _safe_num(target[col]) if col in target.columns else np.nan
                if not target.empty:
                    ax.plot(target["tick_datetime"], target["last_price"], color="#0072b2", linewidth=1.2, label="last")
                    ax.plot(target["tick_datetime"], target["ask_price1"], color="#d55e00", linewidth=0.8, alpha=0.7, label="ask1")
                    ax.plot(target["tick_datetime"], target["bid_price1"], color="#009e73", linewidth=0.8, alpha=0.7, label="bid1")
            ax.axhline(row.get("official_open_price", np.nan), color="black", linestyle="--", linewidth=0.8, label="official open")
            title = (
                f"{role} {row['official_open_trade_id']} {row['vt_symbol']} "
                f"{pd.to_datetime(row['anchor_time']).strftime('%Y-%m-%d %H:%M')} "
                f"deltaR={row.get('min_abs_price_delta_r', np.nan):.3f}"
            )
            ax.set_title(title, fontsize=8)
            ax.grid(alpha=0.22)
            ax.legend(loc="upper left", fontsize=6)
    fig.tight_layout()
    fig.savefig(ATLAS_OUT, dpi=180)
    plt.close(fig)


def _build_decision(
    plan: pd.DataFrame,
    anchor_features: pd.DataFrame,
    comparison: pd.DataFrame,
    coverage: pd.DataFrame,
    official_metrics: dict[str, Any],
) -> dict[str, Any]:
    scan_rows = anchor_features[anchor_features["anchor_role"].eq("event_scan_anchor")]
    proxy_rows = anchor_features[anchor_features["anchor_role"].eq("price_proxy_anchor")]
    paired = comparison[comparison["scan_ready"] & comparison["proxy_ready"]]
    proxy_exact = int(proxy_rows["price_exact_any"].sum()) if not proxy_rows.empty else 0
    scan_exact = int(scan_rows["price_exact_any"].sum()) if not scan_rows.empty else 0
    proxy_improves = int(paired["proxy_improves_abs_delta_r"].sum()) if not paired.empty else 0
    if len(paired) > 0 and proxy_improves == len(paired):
        decision = "stage069_price_proxy_anchor_explains_scan_mismatch_no_rule"
        next_step = "download_remaining_price_proxy_anchors_and_reaudit_before_microstructure_stability"
    else:
        decision = "stage069_dual_anchor_price_basis_partial_unresolved_no_rule"
        next_step = "expand_paired_dual_anchor_download_and_check_continuous_adjustment_basis"
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_metrics": official_metrics,
        "decision": decision,
        "next_step": next_step,
        "strategy_rule_created": False,
        "true_engine_run": False,
        "ab_triggered": False,
        "base_trade_count": int(comparison["event_key"].nunique()),
        "anchor_plan_rows": int(len(plan)),
        "scan_anchor_ready_count": int(scan_rows["anchor_ready"].sum()) if not scan_rows.empty else 0,
        "proxy_anchor_ready_count": int(proxy_rows["anchor_ready"].sum()) if not proxy_rows.empty else 0,
        "scan_price_exact_count": scan_exact,
        "proxy_price_exact_count": proxy_exact,
        "paired_ready_count": int(len(paired)),
        "proxy_improves_abs_delta_count": proxy_improves,
        "near_r_tolerance": NEAR_R_TOL,
        "enable_tqsdk": ENABLE_TQSDK,
        "download_roles": sorted(DOWNLOAD_ROLES),
        "max_events": MAX_EVENTS,
        "outputs": {
            "dual_anchor_plan": DUAL_ANCHOR_PLAN_OUT,
            "download_status": DOWNLOAD_STATUS_OUT,
            "anchor_features": ANCHOR_FEATURES_OUT,
            "trade_comparison": TRADE_COMPARISON_OUT,
            "coverage_summary": COVERAGE_SUMMARY_OUT,
            "path_chart": PATH_CHART_OUT,
            "scatter": SCATTER_OUT,
            "status_chart": STATUS_CHART_OUT,
            "atlas": ATLAS_OUT,
        },
    }


def _write_report(decision: dict[str, Any], coverage: pd.DataFrame, comparison: pd.DataFrame) -> None:
    paired = comparison[comparison["scan_ready"] & comparison["proxy_ready"]].copy()
    class_summary = (
        comparison.groupby("price_basis_class", as_index=False)
        .agg(
            trade_count=("event_key", "size"),
            net_realized_pnl=("realized_pnl", "sum"),
            proxy_improves=("proxy_improves_abs_delta_r", "sum"),
        )
        .sort_values("trade_count", ascending=False)
    )
    lines = [
        f"# {STAGE} 初始开仓双锚点价格基准审计",
        "",
        "## 结论",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 当前正式版：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`。",
        f"- base trade count：`{decision['base_trade_count']}`；anchor plan rows：`{decision['anchor_plan_rows']}`。",
        f"- scan anchor ready：`{decision['scan_anchor_ready_count']}`；proxy anchor ready：`{decision['proxy_anchor_ready_count']}`；paired ready：`{decision['paired_ready_count']}`。",
        f"- scan price exact：`{decision['scan_price_exact_count']}`；proxy price exact：`{decision['proxy_price_exact_count']}`；proxy improves abs delta：`{decision['proxy_improves_abs_delta_count']}`。",
        "- 本阶段不新增交易规则、不跑 true engine、不触发 A/B；目标是区分官方事件扫描时间与 raw proxy 成交价时间。",
        "",
        "## 官方基准",
        "",
        f"- 期末权益：`{decision['official_metrics'].get('end_equity')}`",
        f"- 总收益：`{decision['official_metrics'].get('total_return_pct')}`",
        f"- 最大回撤：`{decision['official_metrics'].get('max_drawdown_pct')}`",
        f"- Sharpe：`{decision['official_metrics'].get('sharpe')}`",
        f"- 总滑点：`{decision['official_metrics'].get('total_slippage')}`",
        f"- 总交易次数：`{decision['official_metrics'].get('total_trade_count')}`",
        "",
        "## 覆盖摘要",
        "",
        _md_table(coverage),
        "",
        "## 价格基准分类",
        "",
        _md_table(class_summary),
        "",
        "## paired ready 样本",
        "",
        _md_table(
            paired[
                [
                    "official_open_trade_id",
                    "vt_symbol",
                    "timestamp_alignment_class",
                    "anchor_gap_minutes",
                    "scan_min_abs_price_delta_r",
                    "proxy_min_abs_price_delta_r",
                    "scan_price_exact_any",
                    "proxy_price_exact_any",
                    "price_basis_class",
                ]
            ],
            max_rows=12,
        ),
        "",
        "## 视觉文件",
        "",
        f"- 资金曲线价格基准图：`{PATH_CHART_OUT}`",
        f"- scan/proxy delta 散点：`{SCATTER_OUT}`",
        f"- anchor 状态图：`{STATUS_CHART_OUT}`",
        f"- 双锚点 tick atlas：`{ATLAS_OUT}`",
        "",
        "## 判断",
        "",
        "- 初始开仓的 `official_open_price` 来自 raw proxy 成交价锚点，而 Stage045/068 的 official-open scan anchor 是事件语义扫描起点；二者不能混为一个 tick 时间点。",
        "- 对夜盘 raw proxy 样本，日盘 scan anchor 的价格偏差不是交易信号，而是锚点定义差异。",
        "- 后续 microstructure/TCA 应先用 price_proxy_anchor 对齐成交价，再单独用 event_scan_anchor 审计 C9/C2 日内事件；覆盖未满前禁止规则化。",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plan = _build_dual_anchor_plan()
    _write_csv(plan, DUAL_ANCHOR_PLAN_OUT)

    status = _download_or_check(plan)
    _write_csv(status, DOWNLOAD_STATUS_OUT)

    anchor_features = _build_anchor_features(plan)
    _write_csv(anchor_features, ANCHOR_FEATURES_OUT)

    comparison = _build_trade_comparison(anchor_features)
    coverage = _coverage_summary(anchor_features, comparison, status)
    _write_csv(comparison, TRADE_COMPARISON_OUT)
    _write_csv(coverage, COVERAGE_SUMMARY_OUT)

    official_metrics = _official_metrics()
    decision = _build_decision(plan, anchor_features, comparison, coverage, official_metrics)
    summary = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": decision["decision"],
        "base_trade_count": decision["base_trade_count"],
        "anchor_plan_rows": decision["anchor_plan_rows"],
        "scan_anchor_ready_count": decision["scan_anchor_ready_count"],
        "proxy_anchor_ready_count": decision["proxy_anchor_ready_count"],
        "scan_price_exact_count": decision["scan_price_exact_count"],
        "proxy_price_exact_count": decision["proxy_price_exact_count"],
        "paired_ready_count": decision["paired_ready_count"],
        "proxy_improves_abs_delta_count": decision["proxy_improves_abs_delta_count"],
        "end_equity": official_metrics.get("end_equity"),
        "total_return_pct": official_metrics.get("total_return_pct"),
        "max_drawdown_pct": official_metrics.get("max_drawdown_pct"),
        "sharpe": official_metrics.get("sharpe"),
        "total_slippage": official_metrics.get("total_slippage"),
        "total_trade_count": official_metrics.get("total_trade_count"),
        "strategy_rule_created": False,
        "true_engine_run": False,
        "ab_triggered": False,
    }
    _write_csv(pd.DataFrame([summary]), SUMMARY_OUT)
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _plot_path(comparison)
    _plot_scatter(comparison)
    _plot_status(anchor_features, status)
    _plot_atlas(anchor_features, comparison)
    _write_report(decision, coverage, comparison)

    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
