from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import logging
import math
import os
from pathlib import Path
import re
import sys
import time
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage068"
MODEL_TAG = "stage068_initial_entry_tick_coverage_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage068_c9_minrisk_initial_entry_tick_coverage_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage067_reentry_microstructure_stability_audit as s067
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage068_initial_entry_tick_coverage_audit"
RAW_TICK_DIR = OUTPUT_DIR / "raw_tick"

STAGE041_DIR = LINE_DIR / "outputs" / "stage041_timestamp_ready_replay_consistency_audit"
STAGE043_DIR = LINE_DIR / "outputs" / "stage043_official_open_scan_replay_repair_audit"
STAGE044_DIR = LINE_DIR / "outputs" / "stage044_c2_directional_stop_semantics_audit"
STAGE045_DIR = LINE_DIR / "outputs" / "stage045_event_time_field_sync_audit"
STAGE047_DIR = LINE_DIR / "outputs" / "stage047_vol_participation_joint_state_audit"

STAGE041_ALIGNMENT_IN = (
    STAGE041_DIR
    / "qmt_roll_stage041_c9_minrisk_timestamp_ready_replay_consistency_audit_timestamp_alignment_"
    "stage041_timestamp_ready_replay_consistency_audit_v1.csv"
)
STAGE043_REPLAY_IN = (
    STAGE043_DIR
    / "qmt_roll_stage043_c9_minrisk_official_open_scan_replay_repair_audit_repair_replay_ledger_"
    "stage043_official_open_scan_replay_repair_audit_v1.csv"
)
STAGE044_VARIANT_IN = (
    STAGE044_DIR
    / "qmt_roll_stage044_c9_minrisk_c2_directional_stop_semantics_audit_variant_replay_ledger_"
    "stage044_c2_directional_stop_semantics_audit_v1.csv"
)
STAGE045_LEDGER_IN = (
    STAGE045_DIR
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_event_sync_ledger_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE045_CURVE_IN = (
    STAGE045_DIR
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE045_SUMMARY_IN = (
    STAGE045_DIR
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_summary_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE047_FEATURES_IN = (
    STAGE047_DIR
    / "qmt_roll_stage047_c9_minrisk_vol_participation_joint_state_audit_features_"
    "stage047_vol_participation_joint_state_audit_v1.csv"
)

PLAN_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_initial_entry_tick_plan_{MODEL_TAG}.csv"
DOWNLOAD_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_download_status_{MODEL_TAG}.csv"
FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_initial_entry_microstructure_features_{MODEL_TAG}.csv"
COVERAGE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_summary_{MODEL_TAG}.csv"
ALIGNMENT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_timestamp_alignment_summary_{MODEL_TAG}.csv"
YEAR_FAMILY_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_family_matrix_{MODEL_TAG}.csv"
CORRELATION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_correlation_summary_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_coverage_chart_{MODEL_TAG}.png"
HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_family_coverage_heatmap_{MODEL_TAG}.png"
STATUS_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_download_status_chart_{MODEL_TAG}.png"
FEATURE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_microstructure_feature_chart_{MODEL_TAG}.png"
ATLAS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_microstructure_atlas_{MODEL_TAG}.png"

OFFICIAL_VARIANT_ID = "stage827_directional_c2_stop_start0_stop_first"
INITIAL_CAPITAL = 150_000.0

DOWNLOAD_WINDOW_MINUTES = int(os.getenv("STAGE068_DOWNLOAD_WINDOW_MINUTES", "3"))
MAX_EVENTS = int(os.getenv("STAGE068_MAX_EVENTS", "0"))
MAX_SECONDS_PER_EVENT = int(os.getenv("STAGE068_MAX_SECONDS_PER_EVENT", "60"))
TICK_DATA_LENGTH = int(os.getenv("STAGE068_TICK_DATA_LENGTH", "12000"))
ENABLE_TQSDK = os.getenv("STAGE068_ENABLE_TQSDK", "0").strip() == "1"


@dataclass(frozen=True)
class TickRef:
    event_key: str
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
    return s067._md_table(frame, max_rows=max_rows)


def _safe_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


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


def _normalize_product(vt_symbol: Any) -> str:
    symbol = "" if pd.isna(vt_symbol) else str(vt_symbol)
    if "." not in symbol:
        return symbol or "UNKNOWN"
    code, exchange = symbol.split(".", 1)
    match = re.match(r"^([A-Za-z]+)", code)
    if not match:
        return symbol
    return f"{match.group(1)}.{exchange}"


def _product_family(product: str) -> tuple[str, str]:
    return s067.PRODUCT_FAMILY.get(product, ("unknown", "未分类"))


def _tq_symbol(vt_symbol: str) -> str:
    code, exchange = vt_symbol.split(".", 1)
    return f"{exchange}.{code}"


def _direction_sign(direction: Any) -> float:
    text = str(direction).lower()
    if text == "long":
        return 1.0
    if text == "short":
        return -1.0
    return np.nan


def _first_valid_timestamp(row: pd.Series, columns: list[str]) -> pd.Timestamp:
    for column in columns:
        if column in row.index:
            ts = _timestamp(row.get(column))
            if pd.notna(ts):
                return ts
    return pd.NaT


def _first_valid_number(row: pd.Series, columns: list[str]) -> float:
    for column in columns:
        if column in row.index:
            value = pd.to_numeric(pd.Series([row.get(column)]), errors="coerce").iloc[0]
            if pd.notna(value):
                return float(value)
    return np.nan


def _load_stage045_ledger() -> pd.DataFrame:
    ledger = _read_csv(STAGE045_LEDGER_IN)
    if "full_event_sync_exact" in ledger.columns:
        ledger = ledger[pd.to_numeric(ledger["full_event_sync_exact"], errors="coerce").fillna(0).eq(1)].copy()
    ledger["candidate_index"] = pd.to_numeric(ledger["candidate_index"], errors="coerce").astype("Int64")
    ledger["official_open_trade_id"] = ledger["official_open_trade_id"].astype(str)
    return ledger.sort_values(["official_open_date", "candidate_index", "official_open_trade_id"]).reset_index(drop=True)


def _load_stage043() -> pd.DataFrame:
    data = _read_csv(STAGE043_REPLAY_IN)
    keep = [
        "candidate_index",
        "official_open_trade_id",
        "candidate_date",
        "candidate_datetime",
        "vt_symbol",
        "product_vt_symbol",
        "direction",
        "planned_entry_price",
        "planned_stop_price",
        "planned_stop_distance",
        "candidate_selected_volume",
        "official_open_datetime",
        "official_open_date",
        "official_open_price",
        "official_open_volume",
        "stage861_day_ready",
        "stage861_bar_count",
        "replay_open_datetime",
        "replay_open_time",
        "replay_open_price",
        "replay_open_price_source",
        "replay_open_minus_official",
        "replay_open_abs_delta",
        "replay_risk_price",
        "replay_c9_stop_price",
        "replay_c9_progress_price",
        "replay_event_family",
        "timestamp_reconstruction_status",
        "timestamp_alignment_class",
        "timestamp_first_time",
        "timestamp_last_time",
        "timestamp_source",
        "raw_ready",
        "raw_price",
        "raw_source",
        "raw_bar_count",
        "raw_first_time",
        "raw_last_time",
        "engine_selected_ready",
        "engine_selected_price",
        "engine_selected_source",
        "engine_selected_bar_count",
        "engine_selected_first_time",
        "engine_selected_last_time",
        "engine_proxy_kind",
        "engine_selected_minus_official",
        "engine_selected_exact_official",
    ]
    data = data[[col for col in keep if col in data.columns]].copy()
    data["candidate_index"] = pd.to_numeric(data["candidate_index"], errors="coerce").astype("Int64")
    data["official_open_trade_id"] = data["official_open_trade_id"].astype(str)
    return data.drop_duplicates(["candidate_index", "official_open_trade_id"], keep="first")


def _load_stage041_alignment() -> pd.DataFrame:
    data = _read_csv(STAGE041_ALIGNMENT_IN)
    keep = [
        "candidate_index",
        "official_open_trade_id",
        "timestamp_reconstruction_status",
        "timestamp_alignment_class",
        "timestamp_first_time",
        "timestamp_last_time",
        "timestamp_source",
        "timestamp_first_time_ts",
        "timestamp_last_time_ts",
        "raw_first_time_ts",
        "raw_last_time_ts",
        "stage861_first_open_time_ts",
        "timestamp_bar_ready",
        "candidate_date_bar_count",
        "raw_ready",
        "raw_bar_count",
        "engine_selected_ready",
        "engine_selected_bar_count",
    ]
    data = data[[col for col in keep if col in data.columns]].copy()
    data["candidate_index"] = pd.to_numeric(data["candidate_index"], errors="coerce").astype("Int64")
    data["official_open_trade_id"] = data["official_open_trade_id"].astype(str)
    rename = {
        col: f"stage041_{col}"
        for col in data.columns
        if col not in {"candidate_index", "official_open_trade_id"}
    }
    data.rename(columns=rename, inplace=True)
    return data.drop_duplicates(["candidate_index", "official_open_trade_id"], keep="first")


def _load_stage044_official_variant() -> pd.DataFrame:
    data = _read_csv(STAGE044_VARIANT_IN)
    data = data[data["variant_id"].astype(str).eq(OFFICIAL_VARIANT_ID)].copy()
    if data.empty:
        raise RuntimeError(f"missing official Stage044 variant rows: {OFFICIAL_VARIANT_ID}")
    keep = [
        "candidate_index",
        "official_open_trade_id",
        "stage043_replay_event_family",
        "stage043_event_family_match",
        "stage042_session_convention_status",
        "official_open_price",
        "replay_open_price",
        "planned_stop_price",
        "replay_risk_price",
        "stage827_directional_c2_stop_price",
        "stage827_directional_c2_confirm_price",
        "variant_c2_stop_price",
        "variant_c2_confirm_price",
        "planned_minus_directional_c2_stop",
        "planned_stop_side",
        "replay_scan_source",
        "stage861_day_ready",
        "replay_event_family",
        "replay_first_stop_time",
        "replay_reentry_time",
        "replay_retry_failed_time",
        "replay_c2_hit_time",
        "replay_c2_confirm_time",
        "first_bar_time",
        "first_bar_open",
        "first_bar_high",
        "first_bar_low",
        "first_bar_close",
        "replay_c9_stop_price",
        "replay_c9_progress_price",
        "replay_c9_first_event",
        "replay_c9_first_event_time",
    ]
    data = data[[col for col in keep if col in data.columns]].copy()
    data["candidate_index"] = pd.to_numeric(data["candidate_index"], errors="coerce").astype("Int64")
    data["official_open_trade_id"] = data["official_open_trade_id"].astype(str)
    rename = {
        col: f"stage044_{col}"
        for col in data.columns
        if col not in {"candidate_index", "official_open_trade_id"}
    }
    data.rename(columns=rename, inplace=True)
    return data.drop_duplicates(["candidate_index", "official_open_trade_id"], keep="first")


def _load_stage047_pnl() -> pd.DataFrame:
    data = _read_csv(STAGE047_FEATURES_IN)
    if "open_trade_id" not in data.columns:
        return pd.DataFrame(columns=["official_open_trade_id"])
    for column in [
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "volume",
        "entry_price",
        "exit_price",
        "first_30m_directional_r",
        "entry_day_mfe_r",
        "entry_day_mae_r",
        "stage861_entry_day_minute_bars",
    ]:
        if column in data.columns:
            data[column] = _safe_num(data[column])
    agg_spec: dict[str, Any] = {
        "realized_pnl": ("realized_pnl", "sum"),
        "closed_lot_count": ("open_trade_id", "size"),
    }
    optional_first = [
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "exit_date",
        "entry_context",
        "layer_kind",
        "risk_multiplier",
        "ai_product_pool_rank",
        "active_positions_before",
        "same_direction_correlation_active_count",
        "stage861_entry_day_minute_bars",
        "first_30m_directional_r",
        "entry_day_mfe_r",
        "entry_day_mae_r",
    ]
    for col in optional_first:
        if col in data.columns:
            agg_spec[f"stage047_{col}"] = (col, "first")
    grouped = data.groupby("open_trade_id", as_index=False).agg(**agg_spec)
    grouped.rename(columns={"open_trade_id": "official_open_trade_id"}, inplace=True)
    grouped["official_open_trade_id"] = grouped["official_open_trade_id"].astype(str)
    return grouped


def _build_plan() -> pd.DataFrame:
    ledger = _load_stage045_ledger()
    stage043 = _load_stage043()
    stage041 = _load_stage041_alignment()
    stage044 = _load_stage044_official_variant()
    pnl = _load_stage047_pnl()
    plan = ledger.merge(stage043, on=["candidate_index", "official_open_trade_id"], how="left", suffixes=("", "_stage043"))
    plan = plan.merge(stage041, on=["candidate_index", "official_open_trade_id"], how="left")
    plan = plan.merge(stage044, on=["candidate_index", "official_open_trade_id"], how="left")
    plan = plan.merge(pnl, on="official_open_trade_id", how="left")

    if len(plan) != len(ledger):
        raise RuntimeError(f"plan row count mismatch: ledger={len(ledger)} plan={len(plan)}")

    for col in [
        "candidate_selected_volume",
        "official_open_volume",
        "official_open_price",
        "replay_open_price",
        "replay_risk_price",
        "planned_stop_price",
        "planned_stop_distance",
        "realized_pnl",
    ]:
        if col in plan.columns:
            plan[col] = _safe_num(plan[col])

    plan["event_key"] = plan["official_open_trade_id"].astype(str)
    plan["download_anchor_time"] = plan.apply(
        lambda row: _first_valid_timestamp(row, ["replay_open_datetime", "stage044_first_bar_time", "official_open_datetime"]),
        axis=1,
    )
    plan["raw_proxy_anchor_time"] = plan.apply(
        lambda row: _first_valid_timestamp(
            row,
            [
                "timestamp_first_time",
                "stage041_timestamp_first_time",
                "stage041_timestamp_first_time_ts",
                "raw_first_time",
                "stage041_raw_first_time_ts",
                "engine_selected_first_time",
            ],
        ),
        axis=1,
    )
    plan["anchor_source"] = np.select(
        [
            plan["replay_open_datetime"].notna(),
            plan.get("stage044_first_bar_time", pd.Series(index=plan.index, dtype=object)).notna(),
            plan["official_open_datetime"].notna(),
        ],
        ["stage043_replay_open_datetime", "stage044_first_bar_time", "official_open_datetime"],
        default="missing",
    )
    plan["download_start_dt"] = plan["download_anchor_time"] - pd.Timedelta(minutes=DOWNLOAD_WINDOW_MINUTES)
    plan["download_end_dt"] = plan["download_anchor_time"] + pd.Timedelta(minutes=DOWNLOAD_WINDOW_MINUTES)
    plan["target_minute_start"] = plan["download_anchor_time"].dt.floor("min")
    plan["target_minute_end"] = plan["target_minute_start"] + pd.Timedelta(minutes=1)

    plan["normalized_product"] = plan["vt_symbol"].map(_normalize_product)
    family_rows = [_product_family(product) for product in plan["normalized_product"].astype(str)]
    plan["product_family"] = [item[0] for item in family_rows]
    plan["product_family_note"] = [item[1] for item in family_rows]
    plan["direction_sign"] = plan["direction"].map(_direction_sign)
    plan["tq_symbol"] = plan["vt_symbol"].map(_tq_symbol)
    plan["open_year"] = pd.to_datetime(plan["official_open_date"], errors="coerce").dt.year.astype("Int64")
    plan["realized_pnl"] = plan["realized_pnl"].fillna(0.0)
    plan["risk_price"] = plan.apply(
        lambda row: _first_valid_number(row, ["replay_risk_price", "stage044_replay_risk_price", "planned_stop_distance"]),
        axis=1,
    )
    plan["official_volume_to_risk_depth_note"] = "pending_tick_depth"
    plan["download_window_minutes_each_side"] = DOWNLOAD_WINDOW_MINUTES
    plan["stage"] = STAGE
    plan["model_tag"] = MODEL_TAG
    plan["official_live_version"] = OFFICIAL_LIVE_VERSION
    plan["official_live_alias"] = OFFICIAL_LIVE_ALIAS
    plan = plan.sort_values(["download_anchor_time", "candidate_index", "official_open_trade_id"]).reset_index(drop=True)
    if MAX_EVENTS > 0:
        plan = plan.head(MAX_EVENTS).copy()
    return plan


def _tick_path(row: pd.Series) -> Path:
    vt_symbol = str(row["vt_symbol"])
    code, exchange = vt_symbol.split(".", 1)
    anchor = _timestamp(row["download_anchor_time"])
    trade_id = str(row["official_open_trade_id"]).replace(".", "_")
    name = f"{code}_{anchor:%Y%m%d_%H%M}_candidate_{int(row['candidate_index'])}_{trade_id}_initial_tick_backtest.csv"
    return RAW_TICK_DIR / exchange / name


def _event_key_from_tick_file(path: Path) -> str | None:
    match = re.search(r"_BACKTESTING_(\d+)_initial_tick_backtest\.csv$", path.name)
    if not match:
        return None
    return f"BACKTESTING.{match.group(1)}"


def _discover_tick_refs() -> dict[str, TickRef]:
    refs: dict[str, TickRef] = {}
    if RAW_TICK_DIR.exists():
        for path in sorted(RAW_TICK_DIR.rglob("*_initial_tick_backtest.csv")):
            event_key = _event_key_from_tick_file(path)
            if event_key is not None:
                refs[event_key] = TickRef(event_key=event_key, path=path, source="stage068_initial_entry")
    return refs


def _target_minute(anchor_time: Any) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = _timestamp(anchor_time).floor("min")
    return start, start + pd.Timedelta(minutes=1)


def _evaluate_ticks(row: pd.Series, ticks: pd.DataFrame) -> dict[str, Any]:
    result: dict[str, Any] = {"tick_rows": int(len(ticks)), "target_minute_rows": 0, "valid_top_book_rows": 0}
    if ticks.empty or "tick_datetime" not in ticks.columns:
        return result
    data = ticks.copy()
    data["tick_datetime"] = pd.to_datetime(data["tick_datetime"], errors="coerce")
    data = data.dropna(subset=["tick_datetime"]).sort_values("tick_datetime")
    start, end = _target_minute(row["download_anchor_time"])
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


def _download_ticks(row: pd.Series, username: str, password: str, credential_status: dict[str, Any]) -> dict[str, Any]:
    path = _tick_path(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    status: dict[str, Any] = {
        "event_key": row["event_key"],
        "candidate_index": row["candidate_index"],
        "official_open_trade_id": row["official_open_trade_id"],
        "vt_symbol": row["vt_symbol"],
        "tq_symbol": row["tq_symbol"],
        "download_anchor_time": row["download_anchor_time"],
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
            status["download_status"] = "cached_stage068"
            return status
        except Exception as exc:
            status["message"] = f"cached_read_failed:{type(exc).__name__}:{exc}"

    if not ENABLE_TQSDK:
        status["download_status"] = "planned_not_downloaded"
        return status
    if not username or not password:
        status["download_status"] = "missing_credentials"
        return status
    if pd.isna(_timestamp(row["download_anchor_time"])):
        status["download_status"] = "missing_anchor_time"
        return status

    try:
        from tqsdk import BacktestFinished, TqApi, TqAuth, TqBacktest, TqSim
    except Exception as exc:
        status["download_status"] = "import_failed"
        status["message"] = repr(exc)[:500]
        return status

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
                "candidate_index": row["candidate_index"],
                "official_open_trade_id": row["official_open_trade_id"],
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
        dedup_cols = ["event_key", "tick_datetime", "last_price"] if "last_price" in data.columns else ["event_key", "tick_datetime"]
        data = data.drop_duplicates(dedup_cols, keep="last").sort_values(["event_key", "tick_datetime"])
        data.to_csv(path, index=False, encoding="utf-8-sig")
    if status["download_status"] == "unknown":
        status["download_status"] = "extracted" if not data.empty else "empty"
    status.update(_evaluate_ticks(row, data))
    return status


def _download_or_check(plan: pd.DataFrame) -> pd.DataFrame:
    username, password, credential_status = _get_credentials()
    rows = [_download_ticks(row, username, password, credential_status) for _, row in plan.iterrows()]
    status = pd.DataFrame(rows)
    if "download_status" in status.columns:
        status["tick_file_exists_after"] = status["tick_path"].map(lambda p: Path(str(p)).exists())
    return status


def _extract_features(row: pd.Series, tick_ref: TickRef | None) -> dict[str, Any]:
    base: dict[str, Any] = {
        "event_key": row["event_key"],
        "candidate_index": row["candidate_index"],
        "official_open_trade_id": row["official_open_trade_id"],
        "vt_symbol": row["vt_symbol"],
        "normalized_product": row["normalized_product"],
        "product_family": row["product_family"],
        "product_family_note": row["product_family_note"],
        "direction": row["direction"],
        "direction_sign": row["direction_sign"],
        "official_open_date": row.get("official_open_date"),
        "download_anchor_time": row["download_anchor_time"],
        "raw_proxy_anchor_time": row["raw_proxy_anchor_time"],
        "anchor_source": row["anchor_source"],
        "timestamp_alignment_class": row.get("timestamp_alignment_class", row.get("stage041_timestamp_alignment_class", "")),
        "stage042_session_convention_status": row.get("stage042_session_convention_status", ""),
        "official_open_price": row.get("official_open_price", np.nan),
        "official_open_volume": row.get("official_open_volume", np.nan),
        "candidate_selected_volume": row.get("candidate_selected_volume", np.nan),
        "risk_price": row.get("risk_price", np.nan),
        "realized_pnl": row.get("realized_pnl", 0.0),
        "closed_lot_count": row.get("closed_lot_count", 0),
        "open_year": row.get("open_year", np.nan),
        "tick_source": tick_ref.source if tick_ref else "",
        "tick_file_exists": bool(tick_ref),
        "tick_file_path": str(tick_ref.path) if tick_ref else str(_tick_path(row)),
        "tick_rows_total": 0,
        "tick_rows_target_minute": 0,
        "valid_top_book_rows": 0,
        "microstructure_ready": False,
        "median_spread": np.nan,
        "median_spread_r": np.nan,
        "p90_spread_r": np.nan,
        "median_depth1": np.nan,
        "median_depth1_log": np.nan,
        "median_book_imbalance": np.nan,
        "median_directional_book_imbalance": np.nan,
        "official_open_volume_to_median_depth1": np.nan,
        "candidate_selected_volume_to_median_depth1": np.nan,
        "volume_delta_target": np.nan,
        "amount_delta_target": np.nan,
        "open_interest_delta_target": np.nan,
        "directional_mid_move_r": np.nan,
        "directional_last_move_r": np.nan,
        "median_mid_price": np.nan,
        "first_mid_price": np.nan,
        "last_mid_price": np.nan,
        "first_mid_minus_official_open": np.nan,
        "median_mid_minus_official_open": np.nan,
        "first_mid_delta_r": np.nan,
        "median_mid_delta_r": np.nan,
        "official_open_inside_first_spread": np.nan,
        "anchor_price_exact": False,
    }
    if not tick_ref:
        return base
    try:
        ticks = pd.read_csv(tick_ref.path, encoding="utf-8-sig")
    except Exception as exc:
        base["tick_read_error"] = f"{type(exc).__name__}:{exc}"
        return base
    if ticks.empty or "tick_datetime" not in ticks.columns:
        return base

    ticks["tick_datetime"] = pd.to_datetime(ticks["tick_datetime"], errors="coerce")
    ticks = ticks.dropna(subset=["tick_datetime"]).sort_values("tick_datetime")
    base["tick_rows_total"] = int(len(ticks))
    start, end = _target_minute(row["download_anchor_time"])
    target = ticks[(ticks["tick_datetime"] >= start) & (ticks["tick_datetime"] < end)].copy()
    base["tick_rows_target_minute"] = int(len(target))
    if target.empty:
        return base

    for col in ["last_price", "ask_price1", "ask_volume1", "bid_price1", "bid_volume1", "volume", "amount", "open_interest"]:
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

    valid["spread"] = valid["ask_price1"] - valid["bid_price1"]
    valid["mid_price"] = (valid["ask_price1"] + valid["bid_price1"]) / 2.0
    valid["depth1"] = valid["ask_volume1"].fillna(0) + valid["bid_volume1"].fillna(0)
    depth_denom = valid["depth1"].replace(0, np.nan)
    valid["book_imbalance"] = (valid["bid_volume1"].fillna(0) - valid["ask_volume1"].fillna(0)) / depth_denom

    risk_price = pd.to_numeric(pd.Series([row.get("risk_price")]), errors="coerce").iloc[0]
    if pd.isna(risk_price) or risk_price <= 0:
        risk_price = np.nan
    direction_sign = pd.to_numeric(pd.Series([row.get("direction_sign")]), errors="coerce").iloc[0]
    if pd.notna(risk_price):
        valid["spread_r"] = valid["spread"] / risk_price
    else:
        valid["spread_r"] = np.nan

    base["microstructure_ready"] = True
    base["median_spread"] = float(valid["spread"].median())
    base["median_spread_r"] = float(valid["spread_r"].median()) if valid["spread_r"].notna().any() else np.nan
    base["p90_spread_r"] = float(valid["spread_r"].quantile(0.90)) if valid["spread_r"].notna().any() else np.nan
    base["median_depth1"] = float(valid["depth1"].median())
    base["median_depth1_log"] = float(np.log1p(valid["depth1"].median()))
    base["median_book_imbalance"] = float(valid["book_imbalance"].median())
    if pd.notna(direction_sign):
        base["median_directional_book_imbalance"] = float(direction_sign * valid["book_imbalance"].median())
    base["median_mid_price"] = float(valid["mid_price"].median())
    base["first_mid_price"] = float(valid["mid_price"].iloc[0])
    base["last_mid_price"] = float(valid["mid_price"].iloc[-1])
    official_open_price = pd.to_numeric(pd.Series([row.get("official_open_price")]), errors="coerce").iloc[0]
    if pd.notna(official_open_price):
        first_mid_delta = valid["mid_price"].iloc[0] - official_open_price
        median_mid_delta = valid["mid_price"].median() - official_open_price
        base["first_mid_minus_official_open"] = float(first_mid_delta)
        base["median_mid_minus_official_open"] = float(median_mid_delta)
        if pd.notna(risk_price):
            base["first_mid_delta_r"] = float(first_mid_delta / risk_price)
            base["median_mid_delta_r"] = float(median_mid_delta / risk_price)
        first_row = valid.iloc[0]
        base["official_open_inside_first_spread"] = int(first_row["bid_price1"] <= official_open_price <= first_row["ask_price1"])
        base["anchor_price_exact"] = bool(abs(first_mid_delta) <= 1e-8)
    if pd.notna(direction_sign) and pd.notna(risk_price):
        base["directional_mid_move_r"] = float(direction_sign * (valid["mid_price"].iloc[-1] - valid["mid_price"].iloc[0]) / risk_price)
        last_valid = target.dropna(subset=["last_price"])
        if len(last_valid) >= 2:
            base["directional_last_move_r"] = float(
                direction_sign * (last_valid["last_price"].iloc[-1] - last_valid["last_price"].iloc[0]) / risk_price
            )
    median_depth = valid["depth1"].median()
    if pd.notna(median_depth) and median_depth > 0:
        base["official_open_volume_to_median_depth1"] = float(row.get("official_open_volume", np.nan) / median_depth)
        base["candidate_selected_volume_to_median_depth1"] = float(row.get("candidate_selected_volume", np.nan) / median_depth)

    for source_col, out_col in [
        ("volume", "volume_delta_target"),
        ("amount", "amount_delta_target"),
        ("open_interest", "open_interest_delta_target"),
    ]:
        values = target[source_col].dropna()
        if len(values) >= 2:
            base[out_col] = float(values.iloc[-1] - values.iloc[0])
    return base


def _build_features(plan: pd.DataFrame) -> pd.DataFrame:
    refs = _discover_tick_refs()
    rows = [_extract_features(row, refs.get(str(row["event_key"]))) for _, row in plan.iterrows()]
    features = pd.DataFrame(rows)
    features["microstructure_ready"] = features["microstructure_ready"].astype(bool)
    features["tick_file_exists"] = features["tick_file_exists"].astype(bool)
    return features


def _coverage_summary(features: pd.DataFrame, status: pd.DataFrame) -> pd.DataFrame:
    status_counts = status["download_status"].value_counts(dropna=False).to_dict() if "download_status" in status.columns else {}
    rows: list[dict[str, Any]] = []
    groups = [
        ("all_initial_entries", features),
        ("microstructure_ready", features[features["microstructure_ready"]]),
        ("tick_file_exists_not_ready", features[features["tick_file_exists"] & ~features["microstructure_ready"]]),
        ("microstructure_missing", features[~features["microstructure_ready"]]),
    ]
    for bucket, group in groups:
        rows.append(
            {
                "bucket": bucket,
                "event_count": int(len(group)),
                "product_count": int(group["normalized_product"].nunique()) if not group.empty else 0,
                "family_count": int(group["product_family"].nunique()) if not group.empty else 0,
                "year_count": int(group["open_year"].nunique()) if not group.empty else 0,
                "net_realized_pnl": float(group["realized_pnl"].sum()) if not group.empty else 0.0,
                "positive_pnl": float(group.loc[group["realized_pnl"] > 0, "realized_pnl"].sum()) if not group.empty else 0.0,
                "negative_pnl_abs": float(-group.loc[group["realized_pnl"] < 0, "realized_pnl"].sum()) if not group.empty else 0.0,
                "median_spread_r": float(group["median_spread_r"].median())
                if not group.empty and group["median_spread_r"].notna().any()
                else np.nan,
                "median_depth1": float(group["median_depth1"].median())
                if not group.empty and group["median_depth1"].notna().any()
                else np.nan,
                "anchor_price_exact_count": int(group["anchor_price_exact"].sum())
                if "anchor_price_exact" in group.columns and not group.empty
                else 0,
                "median_abs_first_mid_delta_r": float(group["first_mid_delta_r"].abs().median())
                if "first_mid_delta_r" in group.columns and not group.empty and group["first_mid_delta_r"].notna().any()
                else np.nan,
                "download_status_counts": json.dumps(_json_safe(status_counts), ensure_ascii=False) if bucket == "all_initial_entries" else "",
            }
        )
    return pd.DataFrame(rows)


def _alignment_summary(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for klass, group in features.groupby("timestamp_alignment_class", dropna=False):
        rows.append(
            {
                "timestamp_alignment_class": str(klass),
                "event_count": int(len(group)),
                "microstructure_ready_count": int(group["microstructure_ready"].sum()),
                "product_count": int(group["normalized_product"].nunique()),
                "family_count": int(group["product_family"].nunique()),
                "year_count": int(group["open_year"].nunique()),
                "net_realized_pnl": float(group["realized_pnl"].sum()),
                "positive_pnl": float(group.loc[group["realized_pnl"] > 0, "realized_pnl"].sum()),
                "negative_pnl_abs": float(-group.loc[group["realized_pnl"] < 0, "realized_pnl"].sum()),
            }
        )
    return pd.DataFrame(rows).sort_values("event_count", ascending=False)


def _year_family_matrix(features: pd.DataFrame) -> pd.DataFrame:
    matrix = (
        features.groupby(["open_year", "product_family"], dropna=False)
        .agg(
            event_count=("event_key", "size"),
            microstructure_ready_count=("microstructure_ready", "sum"),
            net_realized_pnl=("realized_pnl", "sum"),
            positive_pnl=("realized_pnl", lambda s: float(s[s > 0].sum())),
            negative_pnl_abs=("realized_pnl", lambda s: float(-s[s < 0].sum())),
        )
        .reset_index()
    )
    matrix["microstructure_ready_rate_pct"] = np.where(
        matrix["event_count"] > 0,
        matrix["microstructure_ready_count"] / matrix["event_count"] * 100.0,
        np.nan,
    )
    return matrix.sort_values(["open_year", "product_family"])


def _feature_correlations(features: pd.DataFrame) -> pd.DataFrame:
    ready = features[features["microstructure_ready"]].copy()
    cols = [
        "median_spread_r",
        "p90_spread_r",
        "median_depth1_log",
        "median_book_imbalance",
        "median_directional_book_imbalance",
        "official_open_volume_to_median_depth1",
        "candidate_selected_volume_to_median_depth1",
        "volume_delta_target",
        "open_interest_delta_target",
        "directional_mid_move_r",
        "directional_last_move_r",
        "first_mid_delta_r",
        "median_mid_delta_r",
    ]
    rows: list[dict[str, Any]] = []
    for col in cols:
        if col not in ready.columns:
            continue
        sample = ready[[col, "realized_pnl"]].dropna()
        rows.append(
            {
                "feature": col,
                "n": int(len(sample)),
                "unique_count": int(sample[col].nunique()) if not sample.empty else 0,
                "spearman_to_realized_pnl": sample[col].corr(sample["realized_pnl"], method="spearman")
                if len(sample) >= 3 and sample[col].nunique() > 1
                else np.nan,
                "pearson_to_realized_pnl": sample[col].corr(sample["realized_pnl"], method="pearson")
                if len(sample) >= 3 and sample[col].nunique() > 1
                else np.nan,
            }
        )
    corr = pd.DataFrame(rows)
    if not corr.empty:
        corr["abs_spearman_to_realized_pnl"] = corr["spearman_to_realized_pnl"].abs()
        corr = corr.sort_values("abs_spearman_to_realized_pnl", ascending=False, na_position="last")
    return corr


def _official_curve() -> pd.DataFrame:
    curve = _read_csv(STAGE045_CURVE_IN)
    if "arm" in curve.columns:
        curve = curve[curve["arm"].astype(str).eq("A_official_stage847_c9_15w")].copy()
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce")
    return curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def _official_metrics() -> dict[str, Any]:
    if STAGE045_SUMMARY_IN.exists():
        summary = _read_csv(STAGE045_SUMMARY_IN)
        if not summary.empty:
            row = summary.iloc[0]
            return {
                "end_equity": float(row.get("end_equity", np.nan)),
                "total_return_pct": float(row.get("total_return_pct", np.nan)),
                "max_drawdown_pct": float(row.get("max_drawdown_pct", np.nan)),
                "sharpe": float(row.get("sharpe", np.nan)),
                "total_slippage": float(row.get("total_slippage", np.nan)),
                "total_trade_count": float(row.get("total_trade_count", np.nan)),
                "closed_lot_win_rate_pct": float(row.get("closed_lot_win_rate_pct", np.nan)),
                "max_broker10_margin_to_equity_pct": float(row.get("max_broker10_margin_to_equity_pct", np.nan)),
            }
    curve = _official_curve()
    equity = curve["account_equity"].astype(float)
    drawdown = (equity / equity.cummax() - 1.0) * 100.0
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    ret_std = returns.std(ddof=0)
    return {
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / INITIAL_CAPITAL - 1.0) * 100.0),
        "max_drawdown_pct": float(drawdown.min()),
        "sharpe": float(returns.mean() / ret_std * np.sqrt(252.0)) if ret_std and ret_std > 0 else np.nan,
        "total_slippage": float(curve["slippage"].sum()) if "slippage" in curve.columns else np.nan,
        "total_trade_count": float(curve["trade_count"].sum()) if "trade_count" in curve.columns else np.nan,
        "closed_lot_win_rate_pct": np.nan,
        "max_broker10_margin_to_equity_pct": float(curve["broker10_margin_to_equity_pct"].max())
        if "broker10_margin_to_equity_pct" in curve.columns
        else np.nan,
    }


def _plot_path(features: pd.DataFrame) -> None:
    curve = _official_curve()
    events = features.copy()
    events["download_anchor_time"] = pd.to_datetime(events["download_anchor_time"], errors="coerce")
    events = events.dropna(subset=["download_anchor_time"]).sort_values("download_anchor_time")
    events["cum_ready_pnl"] = events["realized_pnl"].where(events["microstructure_ready"], 0.0).cumsum()
    events["cum_missing_pnl"] = events["realized_pnl"].where(~events["microstructure_ready"], 0.0).cumsum()
    events["cum_all_initial_entry_pnl"] = events["realized_pnl"].cumsum()

    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=False)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#0072b2", linewidth=2.0)
    ready = events[events["microstructure_ready"]]
    missing = events[~events["microstructure_ready"]]
    if not ready.empty:
        axes[0].scatter(
            ready["download_anchor_time"],
            np.interp(
                ready["download_anchor_time"].astype("int64"),
                curve["date"].astype("int64"),
                curve["account_equity"] / 1_000_000,
            ),
            s=42,
            color="#009e73",
            label="tick ready",
            alpha=0.8,
        )
    if not missing.empty:
        axes[0].scatter(
            missing["download_anchor_time"],
            np.interp(
                missing["download_anchor_time"].astype("int64"),
                curve["date"].astype("int64"),
                curve["account_equity"] / 1_000_000,
            ),
            s=28,
            color="#d55e00",
            label="planned / missing tick",
            alpha=0.62,
        )
    axes[0].set_title("Stage068 official equity path with initial-entry tick coverage plan")
    axes[0].set_ylabel("Equity (million CNY)")
    axes[0].grid(alpha=0.25)
    axes[0].legend(loc="upper left", fontsize=8)

    axes[1].plot(events["download_anchor_time"], events["cum_all_initial_entry_pnl"] / 10_000, color="#0072b2", linewidth=2.0, label="all planned initial entries")
    axes[1].plot(events["download_anchor_time"], events["cum_ready_pnl"] / 10_000, color="#009e73", linewidth=2.0, label="tick-ready PnL")
    axes[1].plot(events["download_anchor_time"], events["cum_missing_pnl"] / 10_000, color="#d55e00", linewidth=2.0, label="missing tick PnL")
    axes[1].axhline(0, color="black", linewidth=0.8)
    axes[1].set_title("Initial-entry realized PnL contribution by coverage status")
    axes[1].set_ylabel("Cumulative PnL (10k CNY)")
    axes[1].grid(alpha=0.25)
    axes[1].legend(loc="upper left", fontsize=8)

    align = (
        events.groupby("timestamp_alignment_class", dropna=False)["realized_pnl"]
        .sum()
        .sort_values(ascending=True)
        .tail(12)
    )
    colors = ["#d55e00" if value < 0 else "#009e73" for value in align.values]
    axes[2].barh(align.index.astype(str), align.values / 10_000, color=colors, alpha=0.82)
    axes[2].axvline(0, color="black", linewidth=0.8)
    axes[2].set_title("Timestamp alignment buckets are coverage boundary, not trading signal")
    axes[2].set_xlabel("Net realized PnL (10k CNY)")
    axes[2].grid(axis="x", alpha=0.25)

    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_heatmap(matrix: pd.DataFrame) -> None:
    if matrix.empty:
        return
    pivot_count = matrix.pivot_table(index="product_family", columns="open_year", values="event_count", aggfunc="sum", fill_value=0)
    pivot_pnl = matrix.pivot_table(index="product_family", columns="open_year", values="net_realized_pnl", aggfunc="sum", fill_value=0)
    fig, axes = plt.subplots(1, 2, figsize=(16, max(6, len(pivot_count) * 0.45)))
    im0 = axes[0].imshow(pivot_count.values, aspect="auto", cmap="Blues")
    axes[0].set_title("Initial-entry plan count by year/family")
    axes[0].set_xticks(range(len(pivot_count.columns)))
    axes[0].set_xticklabels([str(c) for c in pivot_count.columns], rotation=45, ha="right")
    axes[0].set_yticks(range(len(pivot_count.index)))
    axes[0].set_yticklabels(pivot_count.index)
    for i in range(pivot_count.shape[0]):
        for j in range(pivot_count.shape[1]):
            val = int(pivot_count.iloc[i, j])
            if val:
                axes[0].text(j, i, str(val), ha="center", va="center", fontsize=7)
    fig.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04)

    im1 = axes[1].imshow(pivot_pnl.values / 10_000, aspect="auto", cmap="RdYlGn")
    axes[1].set_title("Realized PnL contribution by year/family")
    axes[1].set_xticks(range(len(pivot_pnl.columns)))
    axes[1].set_xticklabels([str(c) for c in pivot_pnl.columns], rotation=45, ha="right")
    axes[1].set_yticks(range(len(pivot_pnl.index)))
    axes[1].set_yticklabels(pivot_pnl.index)
    for i in range(pivot_pnl.shape[0]):
        for j in range(pivot_pnl.shape[1]):
            val = pivot_pnl.iloc[i, j] / 10_000
            if abs(val) >= 10:
                axes[1].text(j, i, f"{val:.0f}", ha="center", va="center", fontsize=7)
    fig.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.04)

    fig.tight_layout()
    fig.savefig(HEATMAP_OUT, dpi=180)
    plt.close(fig)


def _plot_status(status: pd.DataFrame) -> None:
    if status.empty or "download_status" not in status.columns:
        return
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    counts = status["download_status"].value_counts()
    axes[0].bar(counts.index.astype(str), counts.values, color="#0072b2", alpha=0.82)
    axes[0].set_title("Stage068 download/cache status")
    axes[0].set_ylabel("Event count")
    axes[0].tick_params(axis="x", rotation=30)
    valid = status.copy()
    if "valid_top_book_rows" in valid.columns:
        valid["valid_top_book_rows"] = pd.to_numeric(valid["valid_top_book_rows"], errors="coerce").fillna(0)
        axes[1].hist(valid["valid_top_book_rows"], bins=20, color="#009e73", alpha=0.82)
    axes[1].set_title("Valid top-book rows in target minute")
    axes[1].set_xlabel("Rows")
    axes[1].grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(STATUS_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_feature_chart(features: pd.DataFrame) -> None:
    ready = features[features["microstructure_ready"]].copy()
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    if ready.empty:
        for ax in axes.ravel():
            ax.text(0.5, 0.5, "No ready tick microstructure yet", ha="center", va="center", fontsize=13)
            ax.set_axis_off()
        fig.tight_layout()
        fig.savefig(FEATURE_CHART_OUT, dpi=180)
        plt.close(fig)
        return
    axes[0, 0].scatter(ready["median_spread_r"], ready["realized_pnl"] / 10_000, c=ready["direction_sign"], cmap="coolwarm", alpha=0.75)
    axes[0, 0].axhline(0, color="black", linewidth=0.8)
    axes[0, 0].set_title("Spread / risk vs realized PnL")
    axes[0, 0].set_xlabel("median spread / risk")
    axes[0, 0].set_ylabel("PnL (10k)")
    axes[0, 1].scatter(ready["official_open_volume_to_median_depth1"], ready["realized_pnl"] / 10_000, color="#d55e00", alpha=0.75)
    axes[0, 1].axhline(0, color="black", linewidth=0.8)
    axes[0, 1].set_title("Order size / top-book depth")
    axes[0, 1].set_xlabel("official open volume / median depth1")
    axes[1, 0].scatter(ready["median_directional_book_imbalance"], ready["realized_pnl"] / 10_000, color="#cc79a7", alpha=0.75)
    axes[1, 0].axhline(0, color="black", linewidth=0.8)
    axes[1, 0].set_title("Directional book imbalance")
    axes[1, 0].set_xlabel("directional imbalance")
    axes[1, 1].scatter(ready["directional_mid_move_r"], ready["realized_pnl"] / 10_000, color="#009e73", alpha=0.75)
    axes[1, 1].axhline(0, color="black", linewidth=0.8)
    axes[1, 1].set_title("Target-minute directional mid move")
    axes[1, 1].set_xlabel("directional mid move / risk")
    for ax in axes.ravel():
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(FEATURE_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_atlas(features: pd.DataFrame) -> None:
    ready = features[features["microstructure_ready"]].copy()
    sample = ready.sort_values("realized_pnl").head(4)
    sample = pd.concat([sample, ready.sort_values("realized_pnl").tail(4)], ignore_index=True)
    if "event_key" in sample.columns:
        sample = sample.drop_duplicates("event_key", keep="first")
    if sample.empty:
        sample = features.sort_values("realized_pnl").head(8).copy()
    n = min(8, len(sample))
    fig, axes = plt.subplots(n, 1, figsize=(14, max(4, 2.4 * n)), sharex=False)
    if n == 1:
        axes = np.array([axes])
    for ax, (_, row) in zip(axes, sample.head(n).iterrows()):
        path = Path(str(row.get("tick_file_path", "")))
        if bool(row.get("microstructure_ready")) and path.exists():
            ticks = pd.read_csv(path, encoding="utf-8-sig")
            ticks["tick_datetime"] = pd.to_datetime(ticks["tick_datetime"], errors="coerce")
            start, end = _target_minute(row["download_anchor_time"])
            target = ticks[(ticks["tick_datetime"] >= start) & (ticks["tick_datetime"] < end)].copy()
            for col in ["last_price", "ask_price1", "bid_price1"]:
                target[col] = _safe_num(target[col]) if col in target.columns else np.nan
            if not target.empty:
                ax.plot(target["tick_datetime"], target["last_price"], color="#0072b2", linewidth=1.4, label="last")
                ax.plot(target["tick_datetime"], target["ask_price1"], color="#d55e00", linewidth=0.9, alpha=0.7, label="ask1")
                ax.plot(target["tick_datetime"], target["bid_price1"], color="#009e73", linewidth=0.9, alpha=0.7, label="bid1")
        ax.axhline(row.get("official_open_price", np.nan), color="black", linestyle="--", linewidth=0.8, label="official open")
        title = (
            f"{row['official_open_trade_id']} {row['vt_symbol']} {row['direction']} "
            f"{pd.to_datetime(row['download_anchor_time']).strftime('%Y-%m-%d %H:%M')} "
            f"PnL={row['realized_pnl'] / 10000:.1f}w ready={bool(row['microstructure_ready'])}"
        )
        ax.set_title(title, fontsize=9)
        ax.grid(alpha=0.22)
        ax.legend(loc="upper left", fontsize=7)
    fig.tight_layout()
    fig.savefig(ATLAS_OUT, dpi=180)
    plt.close(fig)


def _build_decision(
    plan: pd.DataFrame,
    features: pd.DataFrame,
    status: pd.DataFrame,
    coverage: pd.DataFrame,
    alignment: pd.DataFrame,
    official_metrics: dict[str, Any],
) -> dict[str, Any]:
    planned_count = int(len(plan))
    ready_count = int(features["microstructure_ready"].sum()) if not features.empty else 0
    missing_count = planned_count - ready_count
    anchor_price_exact_count = int(features["anchor_price_exact"].sum()) if "anchor_price_exact" in features.columns else 0
    ready_anchor_price_mismatch_count = int(ready_count - anchor_price_exact_count)
    full_sync_count = int(plan["full_event_sync_exact"].fillna(0).astype(int).sum()) if "full_event_sync_exact" in plan.columns else planned_count
    download_status_counts = status["download_status"].value_counts(dropna=False).to_dict() if "download_status" in status.columns else {}
    timestamp_class_counts = features["timestamp_alignment_class"].astype(str).value_counts(dropna=False).to_dict() if not features.empty else {}

    if ready_count == planned_count and planned_count > 0:
        decision = "stage068_initial_entry_tick_coverage_ready_watch_only_no_rule"
        next_step = "run_initial_entry_microstructure_stability_audit_before_any_rule"
    else:
        decision = "stage068_initial_entry_tick_coverage_plan_created_download_required_no_rule"
        next_step = "run_predeclared_full_or_batched_tick_download_then_reaudit_coverage"

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
        "planned_initial_entry_count": planned_count,
        "full_event_sync_exact_count": full_sync_count,
        "microstructure_ready_count": ready_count,
        "microstructure_missing_count": missing_count,
        "coverage_ready_rate_pct": ready_count / planned_count * 100.0 if planned_count else np.nan,
        "anchor_price_exact_count": anchor_price_exact_count,
        "ready_anchor_price_mismatch_count": ready_anchor_price_mismatch_count,
        "download_window_minutes_each_side": DOWNLOAD_WINDOW_MINUTES,
        "enable_tqsdk": ENABLE_TQSDK,
        "max_events": MAX_EVENTS,
        "download_status_counts": download_status_counts,
        "timestamp_alignment_class_counts": timestamp_class_counts,
        "outputs": {
            "plan": PLAN_OUT,
            "download_status": DOWNLOAD_STATUS_OUT,
            "features": FEATURES_OUT,
            "coverage_summary": COVERAGE_SUMMARY_OUT,
            "alignment_summary": ALIGNMENT_SUMMARY_OUT,
            "year_family_matrix": YEAR_FAMILY_MATRIX_OUT,
            "correlation": CORRELATION_OUT,
            "path_chart": PATH_CHART_OUT,
            "heatmap": HEATMAP_OUT,
            "status_chart": STATUS_CHART_OUT,
            "feature_chart": FEATURE_CHART_OUT,
            "atlas": ATLAS_OUT,
        },
    }


def _write_report(
    decision: dict[str, Any],
    coverage: pd.DataFrame,
    alignment: pd.DataFrame,
    matrix: pd.DataFrame,
    corr: pd.DataFrame,
) -> None:
    top_family = (
        matrix.groupby("product_family", as_index=False)
        .agg(event_count=("event_count", "sum"), net_realized_pnl=("net_realized_pnl", "sum"), ready=("microstructure_ready_count", "sum"))
        .sort_values("event_count", ascending=False)
        .head(12)
    )
    ready_count = decision["microstructure_ready_count"]
    planned_count = decision["planned_initial_entry_count"]
    lines = [
        f"# {STAGE} 初始开仓 tick/盘口覆盖审计",
        "",
        "## 结论",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 当前正式版：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`。",
        f"- 计划覆盖初始开仓：`{planned_count}` 笔；已有可用 tick 盘口：`{ready_count}` 笔；缺口：`{decision['microstructure_missing_count']}` 笔。",
        f"- 已下载 tick 中价格锚点 exact：`{decision['anchor_price_exact_count']}` 笔；非 exact：`{decision['ready_anchor_price_mismatch_count']}` 笔。非 exact 不代表信号好坏，只说明 raw tick 与官方回放价格基准仍需归一化。",
        f"- 本阶段不新增交易规则、不跑 true engine、不触发 A/B；它只是把 Stage045 已同步的初始开仓转换成可执行性数据计划。",
        f"- 下载窗口：初始开仓 anchor 前后各 `{DOWNLOAD_WINDOW_MINUTES}` 分钟；默认 `STAGE068_ENABLE_TQSDK=0`，避免临时抽样下载引入偏差。",
        "",
        "## 官方基准",
        "",
        f"- 期末权益：`{decision['official_metrics'].get('end_equity')}`",
        f"- 总收益：`{decision['official_metrics'].get('total_return_pct')}`",
        f"- 最大回撤：`{decision['official_metrics'].get('max_drawdown_pct')}`",
        f"- Sharpe：`{decision['official_metrics'].get('sharpe')}`",
        f"- 总滑点：`{decision['official_metrics'].get('total_slippage')}`",
        f"- 总交易次数：`{decision['official_metrics'].get('total_trade_count')}`",
        f"- 胜率：`{decision['official_metrics'].get('closed_lot_win_rate_pct')}`",
        "",
        "## 覆盖摘要",
        "",
        _md_table(coverage),
        "",
        "## timestamp/session 边界",
        "",
        _md_table(alignment, max_rows=12),
        "",
        "## 产品族覆盖",
        "",
        _md_table(top_family, max_rows=12),
        "",
        "## 微观结构相关性",
        "",
        _md_table(corr, max_rows=12),
        "",
        "## 视觉文件",
        "",
        f"- 资金曲线覆盖图：`{PATH_CHART_OUT}`",
        f"- 年份/产品族热图：`{HEATMAP_OUT}`",
        f"- 下载状态图：`{STATUS_CHART_OUT}`",
        f"- 微观结构特征图：`{FEATURE_CHART_OUT}`",
        f"- tick atlas：`{ATLAS_OUT}`",
        "",
        "## 判断",
        "",
        "- 本阶段的第一性判断：盘口数据优先用于流动性、排队深度、价差和订单规模相对容量审计；在覆盖不足和价格基准未归一前，不能把盘口形态写成方向性交易规则。",
        "- Stage045 已证明 timestamp-ready 子集事件语义精确，但这里进一步显示初始开仓 tick 资产仍需独立补齐；缺口本身不是交易信号。",
        "- 下一步只能按计划补全或分批补全 tick，再做稳定性审计；不允许按已下载/未下载、timestamp class、产品族或年份反推规则。",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plan = _build_plan()
    _write_csv(plan, PLAN_OUT)

    status = _download_or_check(plan)
    _write_csv(status, DOWNLOAD_STATUS_OUT)

    features = _build_features(plan)
    _write_csv(features, FEATURES_OUT)

    coverage = _coverage_summary(features, status)
    alignment = _alignment_summary(features)
    matrix = _year_family_matrix(features)
    corr = _feature_correlations(features)
    _write_csv(coverage, COVERAGE_SUMMARY_OUT)
    _write_csv(alignment, ALIGNMENT_SUMMARY_OUT)
    _write_csv(matrix, YEAR_FAMILY_MATRIX_OUT)
    _write_csv(corr, CORRELATION_OUT)

    official_metrics = _official_metrics()
    decision = _build_decision(plan, features, status, coverage, alignment, official_metrics)
    summary = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": decision["decision"],
        "planned_initial_entry_count": decision["planned_initial_entry_count"],
        "microstructure_ready_count": decision["microstructure_ready_count"],
        "microstructure_missing_count": decision["microstructure_missing_count"],
        "coverage_ready_rate_pct": decision["coverage_ready_rate_pct"],
        "anchor_price_exact_count": decision["anchor_price_exact_count"],
        "ready_anchor_price_mismatch_count": decision["ready_anchor_price_mismatch_count"],
        "end_equity": official_metrics.get("end_equity"),
        "total_return_pct": official_metrics.get("total_return_pct"),
        "max_drawdown_pct": official_metrics.get("max_drawdown_pct"),
        "sharpe": official_metrics.get("sharpe"),
        "total_slippage": official_metrics.get("total_slippage"),
        "total_trade_count": official_metrics.get("total_trade_count"),
        "win_rate_pct": official_metrics.get("closed_lot_win_rate_pct"),
        "ab_triggered": False,
        "strategy_rule_created": False,
        "true_engine_run": False,
    }
    _write_csv(pd.DataFrame([summary]), SUMMARY_OUT)
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _plot_path(features)
    _plot_heatmap(matrix)
    _plot_status(status)
    _plot_feature_chart(features)
    _plot_atlas(features)
    _write_report(decision, coverage, alignment, matrix, corr)

    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
