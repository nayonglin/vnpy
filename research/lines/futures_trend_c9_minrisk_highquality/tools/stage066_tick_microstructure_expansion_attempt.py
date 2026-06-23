from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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
STAGE = "Stage066"
MODEL_TAG = "stage066_tick_microstructure_expansion_attempt_v1"
OUTPUT_PREFIX = "qmt_roll_stage066_c9_minrisk_tick_microstructure_expansion_attempt"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage066_tick_microstructure_expansion_attempt"
RAW_TICK_DIR = OUTPUT_DIR / "raw_tick"

STAGE057_RAW_TICK_DIR = LINE_DIR / "outputs/stage057_reentry_gap_tqsdk_backtest_refill/raw_tick"
STAGE058_EVENTS_IN = (
    LINE_DIR
    / "outputs/stage058_reentry_full_ohlcv_integration_audit/"
    "qmt_roll_stage058_c9_minrisk_reentry_full_ohlcv_integration_audit_integrated_events_"
    "stage058_reentry_full_ohlcv_integration_audit_v1.csv"
)
STAGE065_PLAN_IN = (
    LINE_DIR
    / "outputs/stage065_tick_microstructure_asset_audit/"
    "qmt_roll_stage065_c9_minrisk_tick_microstructure_asset_audit_tick_expansion_download_plan_"
    "stage065_tick_microstructure_asset_audit_v1.csv"
)
OFFICIAL_CURVE_IN = (
    LINE_DIR
    / "outputs/stage046_entry_day_confirmed_breakeven_true_engine/"
    "qmt_roll_stage046_c9_minrisk_entry_day_confirmed_breakeven_true_engine_curve_"
    "stage046_entry_day_confirmed_breakeven_true_engine_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DOWNLOAD_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_download_status_{MODEL_TAG}.csv"
EVENT_FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_microstructure_features_{MODEL_TAG}.csv"
COVERAGE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_summary_{MODEL_TAG}.csv"
CORR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_correlation_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_tick_coverage_chart_{MODEL_TAG}.png"
SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_microstructure_scatter_{MODEL_TAG}.png"
HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_product_year_heatmap_{MODEL_TAG}.png"
STATUS_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_download_status_chart_{MODEL_TAG}.png"
ATLAS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_microstructure_atlas_{MODEL_TAG}.png"

OFFICIAL_LIVE_VERSION = "official_live_stage847_c9_15w_stage819_05r_stop_retry_once"
OFFICIAL_LIVE_ALIAS = "Stage847-C9-15w"

MAX_EVENTS = int(os.getenv("STAGE066_MAX_EVENTS", "0"))
MAX_SECONDS_PER_EVENT = int(os.getenv("STAGE066_MAX_SECONDS_PER_EVENT", "75"))
TICK_DATA_LENGTH = int(os.getenv("STAGE066_TICK_DATA_LENGTH", "12000"))
ENABLE_TQSDK = os.getenv("STAGE066_ENABLE_TQSDK", "1").strip() != "0"


@dataclass(frozen=True)
class TickRef:
    event_key: str
    path: Path
    source: str


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


def _safe_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _normalize_product(vt_symbol: str) -> str:
    code, exchange = vt_symbol.split(".", 1)
    prefix = "".join(ch for ch in code if not ch.isdigit()).rstrip("_")
    return f"{prefix}.{exchange}"


def _tq_symbol(vt_symbol: str) -> str:
    code, exchange = vt_symbol.split(".", 1)
    return f"{exchange}.{code}"


def _load_events() -> pd.DataFrame:
    events = _read_csv(STAGE058_EVENTS_IN)
    events["event_key"] = events["event_key"].astype(str)
    events["reentry_time"] = pd.to_datetime(events["reentry_time"], errors="coerce")
    events["reentry_year"] = pd.to_numeric(events["reentry_year"], errors="coerce").astype("Int64")
    events["reentry_lot_pnl"] = pd.to_numeric(events["reentry_lot_pnl"], errors="coerce")
    events["risk_price"] = pd.to_numeric(events["risk_price"], errors="coerce")
    events["direction_sign"] = pd.to_numeric(events["direction_sign"], errors="coerce")
    events["normalized_product"] = events["vt_symbol"].astype(str).map(_normalize_product)
    return events.sort_values(["reentry_time", "event_key"]).reset_index(drop=True)


def _load_plan() -> pd.DataFrame:
    plan = _read_csv(STAGE065_PLAN_IN)
    plan["event_key"] = plan["event_key"].astype(str)
    plan["reentry_time"] = pd.to_datetime(plan["reentry_time"], errors="coerce")
    plan["download_start_dt"] = pd.to_datetime(plan["download_start_dt"], errors="coerce")
    plan["download_end_dt"] = pd.to_datetime(plan["download_end_dt"], errors="coerce")
    plan["reentry_lot_pnl"] = pd.to_numeric(plan["reentry_lot_pnl"], errors="coerce")
    plan["tq_symbol"] = plan["vt_symbol"].astype(str).map(_tq_symbol)
    plan = plan.sort_values(["reentry_time", "event_key"]).reset_index(drop=True)
    if MAX_EVENTS > 0:
        plan = plan.head(MAX_EVENTS).copy()
    return plan


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


def _event_tick_path(row: pd.Series) -> Path:
    vt_symbol = str(row["vt_symbol"])
    code, exchange = vt_symbol.split(".", 1)
    event_ts = _timestamp(row["reentry_time"])
    name = f"{code}_{event_ts:%Y%m%d_%H%M}_{str(row['event_key']).replace('.', '_')}_tick_backtest.csv"
    return RAW_TICK_DIR / exchange / name


def _event_key_from_tick_file(path: Path) -> str | None:
    name = path.name
    if "BACKTESTING_" not in name:
        return None
    suffix = name.split("BACKTESTING_", 1)[1].split("_tick_backtest.csv", 1)[0]
    return f"BACKTESTING.{suffix}"


def _discover_tick_refs() -> dict[str, TickRef]:
    refs: dict[str, TickRef] = {}
    for source, root in [("stage057_existing", STAGE057_RAW_TICK_DIR), ("stage066_expanded", RAW_TICK_DIR)]:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*_tick_backtest.csv")):
            event_key = _event_key_from_tick_file(path)
            if event_key is None:
                continue
            refs[event_key] = TickRef(event_key=event_key, path=path, source=source)
    return refs


def _download_ticks(row: pd.Series, username: str, password: str, credential_status: dict[str, Any]) -> dict[str, Any]:
    path = _event_tick_path(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    status: dict[str, Any] = {
        "event_key": row["event_key"],
        "vt_symbol": row["vt_symbol"],
        "tq_symbol": row["tq_symbol"],
        "reentry_time": row["reentry_time"],
        "reentry_lot_pnl": row["reentry_lot_pnl"],
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
            status["download_status"] = "cached_stage066"
            return status
        except Exception as exc:
            status["message"] = f"cached_read_failed:{type(exc).__name__}:{exc}"

    if not ENABLE_TQSDK:
        status["download_status"] = "skipped_disabled"
        return status
    if not username or not password:
        status["download_status"] = "missing_credentials"
        return status

    try:
        from tqsdk import BacktestFinished, TqApi, TqAuth, TqBacktest, TqSim
    except Exception as exc:
        status["download_status"] = "import_failed"
        status["message"] = repr(exc)[:500]
        return status

    logging.getLogger().setLevel(logging.WARNING)
    logging.getLogger("tqsdk").setLevel(logging.WARNING)
    start_dt = _timestamp(row["download_start_dt"])
    end_dt = _timestamp(row["download_end_dt"])
    rows: list[dict[str, Any]] = []
    seen_keys: set[tuple[Any, Any]] = set()
    started = time.time()
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
        if "last_price" in data.columns:
            data = data.drop_duplicates(["event_key", "tick_datetime", "last_price"], keep="last")
        else:
            data = data.drop_duplicates(["event_key", "tick_datetime"], keep="last")
        data = data.sort_values(["event_key", "tick_datetime"])
        data.to_csv(path, index=False, encoding="utf-8-sig")
    if status["download_status"] == "unknown":
        status["download_status"] = "extracted" if not data.empty else "empty"
    status.update(_evaluate_ticks(row, data))
    return status


def _target_minute(reentry_time: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = reentry_time.floor("min")
    return start, start + pd.Timedelta(minutes=1)


def _evaluate_ticks(row: pd.Series, ticks: pd.DataFrame) -> dict[str, Any]:
    result = {"tick_rows": int(len(ticks)), "target_minute_rows": 0, "valid_top_book_rows": 0}
    if ticks.empty or "tick_datetime" not in ticks.columns:
        return result
    data = ticks.copy()
    data["tick_datetime"] = pd.to_datetime(data["tick_datetime"], errors="coerce")
    data = data.dropna(subset=["tick_datetime"]).sort_values("tick_datetime")
    start, end = _target_minute(_timestamp(row["reentry_time"]))
    target = data[(data["tick_datetime"] >= start) & (data["tick_datetime"] < end)].copy()
    result["target_minute_rows"] = int(len(target))
    if target.empty:
        return result
    for col in ["ask_price1", "bid_price1"]:
        if col in target.columns:
            target[col] = _safe_num(target[col])
        else:
            target[col] = np.nan
    valid = target[
        (target["ask_price1"] > 0)
        & (target["bid_price1"] > 0)
        & (target["ask_price1"] < 1e100)
        & (target["bid_price1"] < 1e100)
        & (target["ask_price1"] >= target["bid_price1"])
    ]
    result["valid_top_book_rows"] = int(len(valid))
    return result


def _extract_features(row: pd.Series, tick_ref: TickRef | None) -> dict[str, Any]:
    base: dict[str, Any] = {
        "event_key": row["event_key"],
        "trade_id": row.get("trade_id", ""),
        "vt_symbol": row["vt_symbol"],
        "normalized_product": row["normalized_product"],
        "direction": row["direction"],
        "direction_sign": row["direction_sign"],
        "reentry_year": row["reentry_year"],
        "reentry_time": row["reentry_time"],
        "quality_bucket": row.get("quality_bucket", ""),
        "reentry_lot_pnl": row["reentry_lot_pnl"],
        "risk_price": row["risk_price"],
        "final_source": row.get("final_source", ""),
        "tick_source": tick_ref.source if tick_ref else "",
        "tick_file_exists": bool(tick_ref),
        "tick_file_path": str(tick_ref.path) if tick_ref else "",
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
        "volume_delta_target": np.nan,
        "amount_delta_target": np.nan,
        "open_interest_delta_target": np.nan,
        "directional_mid_move_r": np.nan,
        "directional_last_move_r": np.nan,
        "median_mid_price": np.nan,
        "first_mid_price": np.nan,
        "last_mid_price": np.nan,
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
    start, end = _target_minute(_timestamp(row["reentry_time"]))
    target = ticks[(ticks["tick_datetime"] >= start) & (ticks["tick_datetime"] < end)].copy()
    base["tick_rows_target_minute"] = int(len(target))
    if target.empty:
        return base

    for col in ["last_price", "ask_price1", "ask_volume1", "bid_price1", "bid_volume1", "volume", "amount", "open_interest"]:
        if col in target.columns:
            target[col] = _safe_num(target[col])
        else:
            target[col] = np.nan

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
    risk_price = float(row["risk_price"]) if pd.notna(row["risk_price"]) and float(row["risk_price"]) > 0 else np.nan
    direction_sign = float(row["direction_sign"]) if pd.notna(row["direction_sign"]) else np.nan
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
    if pd.notna(direction_sign) and pd.notna(risk_price):
        base["directional_mid_move_r"] = float(direction_sign * (valid["mid_price"].iloc[-1] - valid["mid_price"].iloc[0]) / risk_price)
        last_valid = target.dropna(subset=["last_price"])
        if len(last_valid) >= 2:
            base["directional_last_move_r"] = float(
                direction_sign * (last_valid["last_price"].iloc[-1] - last_valid["last_price"].iloc[0]) / risk_price
            )

    for source_col, out_col in [
        ("volume", "volume_delta_target"),
        ("amount", "amount_delta_target"),
        ("open_interest", "open_interest_delta_target"),
    ]:
        values = target[source_col].dropna()
        if len(values) >= 2:
            base[out_col] = float(values.iloc[-1] - values.iloc[0])
    return base


def _build_features(events: pd.DataFrame) -> pd.DataFrame:
    refs = _discover_tick_refs()
    rows = [_extract_features(row, refs.get(str(row["event_key"]))) for _, row in events.iterrows()]
    features = pd.DataFrame(rows)
    features["microstructure_ready"] = features["microstructure_ready"].astype(bool)
    features["tick_file_exists"] = features["tick_file_exists"].astype(bool)
    return features


def _feature_correlations(features: pd.DataFrame) -> pd.DataFrame:
    ready = features[features["microstructure_ready"]].copy()
    cols = [
        "median_spread_r",
        "p90_spread_r",
        "median_depth1_log",
        "median_book_imbalance",
        "median_directional_book_imbalance",
        "volume_delta_target",
        "open_interest_delta_target",
        "directional_mid_move_r",
        "directional_last_move_r",
    ]
    rows: list[dict[str, Any]] = []
    for col in cols:
        sample = ready[[col, "reentry_lot_pnl"]].dropna()
        rows.append(
            {
                "feature": col,
                "n": int(len(sample)),
                "unique_count": int(sample[col].nunique()) if not sample.empty else 0,
                "spearman_to_reentry_pnl": sample[col].corr(sample["reentry_lot_pnl"], method="spearman")
                if len(sample) >= 3 and sample[col].nunique() > 1
                else np.nan,
                "pearson_to_reentry_pnl": sample[col].corr(sample["reentry_lot_pnl"], method="pearson")
                if len(sample) >= 3 and sample[col].nunique() > 1
                else np.nan,
            }
        )
    corr = pd.DataFrame(rows)
    corr["abs_spearman_to_reentry_pnl"] = corr["spearman_to_reentry_pnl"].abs()
    return corr.sort_values("abs_spearman_to_reentry_pnl", ascending=False, na_position="last")


def _coverage_summary(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    groups = [
        ("all_reentry_events", features),
        ("microstructure_ready", features[features["microstructure_ready"]]),
        ("stage057_existing_ready", features[features["microstructure_ready"] & features["tick_source"].eq("stage057_existing")]),
        ("stage066_expanded_ready", features[features["microstructure_ready"] & features["tick_source"].eq("stage066_expanded")]),
        ("microstructure_missing", features[~features["microstructure_ready"]]),
    ]
    for name, data in groups:
        rows.append(
            {
                "bucket": name,
                "event_count": int(len(data)),
                "product_count": int(data["normalized_product"].nunique()) if not data.empty else 0,
                "year_count": int(data["reentry_year"].nunique()) if not data.empty else 0,
                "net_reentry_lot_pnl": float(data["reentry_lot_pnl"].sum()) if not data.empty else 0.0,
                "positive_pnl": float(data.loc[data["reentry_lot_pnl"] > 0, "reentry_lot_pnl"].sum()) if not data.empty else 0.0,
                "negative_pnl_abs": float(-data.loc[data["reentry_lot_pnl"] < 0, "reentry_lot_pnl"].sum()) if not data.empty else 0.0,
                "median_spread_r": float(data["median_spread_r"].median())
                if "median_spread_r" in data and data["median_spread_r"].notna().any()
                else np.nan,
                "median_directional_book_imbalance": float(data["median_directional_book_imbalance"].median())
                if "median_directional_book_imbalance" in data and data["median_directional_book_imbalance"].notna().any()
                else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _official_curve() -> pd.DataFrame:
    curve = _read_csv(OFFICIAL_CURVE_IN)
    arm_cols = [col for col in ["arm", "arm_key", "variant"] if col in curve.columns]
    mask = pd.Series(False, index=curve.index)
    for col in arm_cols:
        values = curve[col].astype(str)
        mask = mask | values.str.contains("A_official", na=False)
        mask = mask | values.str.contains("official_live_stage847_c9_15w", na=False)
    official = curve.loc[mask].copy()
    official["date"] = pd.to_datetime(official["date"], errors="coerce")
    return official.dropna(subset=["date"]).sort_values("date")


def _plot_path(features: pd.DataFrame) -> None:
    official = _official_curve()
    events = features.copy()
    events["reentry_time"] = pd.to_datetime(events["reentry_time"], errors="coerce")
    events = events.dropna(subset=["reentry_time"]).sort_values("reentry_time")
    events["cum_stage057_pnl"] = events["reentry_lot_pnl"].where(events["tick_source"].eq("stage057_existing"), 0).cumsum()
    events["cum_stage066_pnl"] = events["reentry_lot_pnl"].where(events["tick_source"].eq("stage066_expanded"), 0).cumsum()
    events["cum_missing_pnl"] = events["reentry_lot_pnl"].where(~events["microstructure_ready"], 0).cumsum()

    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=False)
    axes[0].plot(official["date"], official["account_equity"] / 1_000_000, color="#0072b2", linewidth=2.0)
    ready_old = events[events["tick_source"].eq("stage057_existing")]
    ready_new = events[events["tick_source"].eq("stage066_expanded")]
    missing = events[~events["microstructure_ready"]]
    for data, color, label, size in [
        (ready_old, "#009e73", "stage057 tick ready", 38),
        (ready_new, "#56b4e9", "stage066 expanded tick ready", 48),
        (missing, "#d55e00", "tick missing", 32),
    ]:
        if data.empty:
            continue
        axes[0].scatter(
            data["reentry_time"],
            np.interp(data["reentry_time"].astype("int64"), official["date"].astype("int64"), official["account_equity"] / 1_000_000),
            s=size,
            color=color,
            label=label,
            alpha=0.78,
        )
    axes[0].set_title("Stage066 official equity path with expanded tick microstructure coverage")
    axes[0].set_ylabel("Equity (million CNY)")
    axes[0].grid(alpha=0.25)
    axes[0].legend(loc="upper left", fontsize=8)

    axes[1].plot(events["reentry_time"], events["cum_stage057_pnl"] / 10_000, color="#009e73", linewidth=2.0, label="stage057 ready PnL")
    axes[1].plot(events["reentry_time"], events["cum_stage066_pnl"] / 10_000, color="#56b4e9", linewidth=2.0, label="stage066 ready PnL")
    axes[1].plot(events["reentry_time"], events["cum_missing_pnl"] / 10_000, color="#d55e00", linewidth=2.0, label="still missing PnL")
    axes[1].axhline(0, color="black", linewidth=0.8)
    axes[1].set_title("Coverage contribution after Stage066 expansion")
    axes[1].set_ylabel("Cumulative PnL (10k CNY)")
    axes[1].grid(alpha=0.25)
    axes[1].legend(loc="upper left", fontsize=8)

    ready = events[events["microstructure_ready"]]
    if not ready.empty:
        axes[2].plot(ready["reentry_time"], ready["median_spread_r"], marker="o", color="#56b4e9", linewidth=1.2, label="median spread / risk")
        axes[2].plot(ready["reentry_time"], ready["median_directional_book_imbalance"], marker="o", color="#cc79a7", linewidth=1.2, label="directional book imbalance")
    axes[2].axhline(0, color="black", linewidth=0.8)
    axes[2].set_title("Point-in-time microstructure diagnostics")
    axes[2].set_ylabel("Feature value")
    axes[2].grid(alpha=0.25)
    axes[2].legend(loc="upper left", fontsize=8)

    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_scatter(features: pd.DataFrame) -> None:
    ready = features[features["microstructure_ready"]].copy()
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    specs = [
        ("median_spread_r", "Median spread / risk"),
        ("median_directional_book_imbalance", "Directional book imbalance"),
        ("median_depth1_log", "Log top-book depth"),
        ("directional_mid_move_r", "Directional mid move / risk"),
    ]
    for ax, (col, title) in zip(axes.reshape(-1), specs):
        sample = ready[[col, "reentry_lot_pnl", "reentry_year", "normalized_product"]].dropna()
        if sample.empty:
            ax.text(0.5, 0.5, "no ready sample", ha="center", va="center")
        else:
            scatter = ax.scatter(
                sample[col],
                sample["reentry_lot_pnl"] / 10_000,
                c=sample["reentry_year"].astype(int),
                cmap="viridis",
                s=65,
                alpha=0.85,
                edgecolor="black",
                linewidth=0.35,
            )
            fig.colorbar(scatter, ax=ax, fraction=0.046, pad=0.04, label="year")
            for _, row in sample.nlargest(2, "reentry_lot_pnl").iterrows():
                ax.annotate(str(row["normalized_product"]), (row[col], row["reentry_lot_pnl"] / 10_000), fontsize=8)
            for _, row in sample.nsmallest(2, "reentry_lot_pnl").iterrows():
                ax.annotate(str(row["normalized_product"]), (row[col], row["reentry_lot_pnl"] / 10_000), fontsize=8)
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_title(title)
        ax.set_ylabel("Reentry lot PnL (10k CNY)")
        ax.grid(alpha=0.25)
    fig.suptitle("Stage066 tick microstructure features vs reentry PnL", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(SCATTER_OUT, dpi=180)
    plt.close(fig)


def _plot_heatmap(features: pd.DataFrame) -> None:
    table = (
        features.pivot_table(
            index="normalized_product",
            columns="reentry_year",
            values="microstructure_ready",
            aggfunc=lambda x: int(np.sum(x)),
            fill_value=0,
        )
        .sort_index()
    )
    fig, ax = plt.subplots(figsize=(12, max(5.5, 0.35 * len(table))))
    im = ax.imshow(table.to_numpy(), cmap="YlGnBu", aspect="auto")
    ax.set_xticks(np.arange(len(table.columns)))
    ax.set_xticklabels([str(int(col)) for col in table.columns], rotation=30, ha="right")
    ax.set_yticks(np.arange(len(table.index)))
    ax.set_yticklabels(table.index)
    for i in range(table.shape[0]):
        for j in range(table.shape[1]):
            ax.text(j, i, str(int(table.iat[i, j])), ha="center", va="center", fontsize=8, color="black")
    ax.set_title("Stage066 microstructure-ready reentry count by product/year")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(HEATMAP_OUT, dpi=180)
    plt.close(fig)


def _plot_status(download_status: pd.DataFrame) -> None:
    if download_status.empty:
        return
    count = download_status["download_status"].value_counts().sort_values(ascending=True)
    pnl = download_status.groupby("download_status")["reentry_lot_pnl"].sum().reindex(count.index)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    axes[0].barh(count.index, count.values, color="#0072b2")
    axes[0].set_title("download status count")
    axes[1].barh(pnl.index, pnl.values / 10_000, color=np.where(pnl.values >= 0, "#009e73", "#d55e00"))
    axes[1].axvline(0, color="#333333", lw=0.8)
    axes[1].set_title("download status PnL (10k CNY)")
    fig.suptitle("Stage066 missing tick expansion attempts")
    fig.tight_layout()
    fig.savefig(STATUS_CHART_OUT, dpi=170)
    plt.close(fig)


def _load_target_ticks(path: Path, event_time: pd.Timestamp) -> pd.DataFrame:
    ticks = pd.read_csv(path, encoding="utf-8-sig")
    ticks["tick_datetime"] = pd.to_datetime(ticks["tick_datetime"], errors="coerce")
    ticks = ticks.dropna(subset=["tick_datetime"]).sort_values("tick_datetime")
    start = event_time - pd.Timedelta(minutes=1)
    end = event_time + pd.Timedelta(minutes=2)
    for col in ["last_price", "ask_price1", "ask_volume1", "bid_price1", "bid_volume1"]:
        if col in ticks.columns:
            ticks[col] = _safe_num(ticks[col])
        else:
            ticks[col] = np.nan
    ticks = ticks[(ticks["tick_datetime"] >= start) & (ticks["tick_datetime"] < end)].copy()
    ticks = ticks[
        (ticks["ask_price1"] > 0)
        & (ticks["bid_price1"] > 0)
        & (ticks["ask_price1"] < 1e100)
        & (ticks["bid_price1"] < 1e100)
        & (ticks["ask_price1"] >= ticks["bid_price1"])
    ].copy()
    if ticks.empty:
        return ticks
    ticks["depth1"] = ticks["ask_volume1"].fillna(0) + ticks["bid_volume1"].fillna(0)
    denom = ticks["depth1"].replace(0, np.nan)
    ticks["imbalance"] = (ticks["bid_volume1"].fillna(0) - ticks["ask_volume1"].fillna(0)) / denom
    return ticks


def _plot_atlas(features: pd.DataFrame) -> None:
    ready = features[features["microstructure_ready"]].copy()
    if ready.empty:
        return
    stage066_ready = ready[ready["tick_source"].eq("stage066_expanded")]
    pieces = []
    if not stage066_ready.empty:
        pieces.extend([stage066_ready.nlargest(2, "reentry_lot_pnl"), stage066_ready.nsmallest(2, "reentry_lot_pnl")])
    pieces.extend([ready.nlargest(1, "reentry_lot_pnl"), ready.nsmallest(1, "reentry_lot_pnl")])
    selected = pd.concat(pieces, ignore_index=True).drop_duplicates("event_key").head(6)
    fig, axes = plt.subplots(len(selected), 2, figsize=(14, max(3.2 * len(selected), 6)))
    if len(selected) == 1:
        axes = np.asarray([axes])
    for row_idx, (_, row) in enumerate(selected.iterrows()):
        event_time = _timestamp(row["reentry_time"])
        ticks = _load_target_ticks(Path(row["tick_file_path"]), event_time)
        ax_price, ax_depth = axes[row_idx]
        if ticks.empty:
            ax_price.text(0.5, 0.5, "no valid ticks", ha="center", va="center")
            ax_depth.axis("off")
            continue
        x = ticks["tick_datetime"]
        ax_price.plot(x, ticks["bid_price1"], color="#0072b2", linewidth=1.0, label="bid1")
        ax_price.plot(x, ticks["ask_price1"], color="#d55e00", linewidth=1.0, label="ask1")
        ax_price.plot(x, ticks["last_price"], color="#222222", linewidth=0.9, alpha=0.65, label="last")
        ax_price.axvline(event_time, color="#7a3db8", linestyle="--", linewidth=1.0, label="reentry")
        ax_price.set_title(
            f"{row['tick_source']} {row['event_key']} {row['vt_symbol']} pnl={row['reentry_lot_pnl'] / 10000:.1f}w"
        )
        ax_price.grid(alpha=0.25)
        ax_price.legend(loc="upper left", fontsize=7)
        ax_depth.plot(x, ticks["depth1"], color="#009e73", linewidth=1.0, label="depth1")
        ax_twin = ax_depth.twinx()
        ax_twin.plot(x, ticks["imbalance"], color="#cc79a7", linewidth=1.0, label="imbalance")
        ax_depth.axvline(event_time, color="#7a3db8", linestyle="--", linewidth=1.0)
        ax_depth.set_title("Top-book depth and imbalance")
        ax_depth.grid(alpha=0.25)
    fig.suptitle("Stage066 point-in-time tick microstructure atlas", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.985])
    fig.savefig(ATLAS_OUT, dpi=170)
    plt.close(fig)


def _write_report(decision: dict[str, Any], coverage: pd.DataFrame, corr: pd.DataFrame, status: pd.DataFrame) -> None:
    lines = [
        "# Stage066 Tick Microstructure Expansion Attempt",
        "",
        f"- Created: {decision['created_at']}",
        f"- Official baseline: `{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        f"- Decision: `{decision['decision']}`",
        "- This is a data-asset expansion audit only. No trading rule, true engine, A/B test, CTP connection, or order API call was used.",
        "",
        "## Download Status",
        "",
        status[
            [
                "event_key",
                "vt_symbol",
                "reentry_time",
                "download_status",
                "tick_rows",
                "target_minute_rows",
                "valid_top_book_rows",
                "reentry_lot_pnl",
                "message",
            ]
        ].to_markdown(index=False),
        "",
        "## Coverage",
        "",
        coverage.to_markdown(index=False),
        "",
        "## Feature Correlation",
        "",
        corr.to_markdown(index=False),
        "",
        "## Judgment",
        "",
        decision["judgment"],
        "",
        "## Outputs",
        "",
    ]
    for name, path in decision["outputs"].items():
        lines.append(f"- {name}: `{path}`")
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_TICK_DIR.mkdir(parents=True, exist_ok=True)
    plan = _load_plan()
    events = _load_events()
    username, password, credential_status = _get_credentials()

    status_rows: list[dict[str, Any]] = []
    for _, row in plan.iterrows():
        status_rows.append(_download_ticks(row, username, password, credential_status))
    download_status = pd.DataFrame(status_rows)

    features = _build_features(events)
    coverage = _coverage_summary(features)
    corr = _feature_correlations(features)
    ready = features[features["microstructure_ready"]]
    missing = features[~features["microstructure_ready"]]
    stage066_ready = features[features["microstructure_ready"] & features["tick_source"].eq("stage066_expanded")]
    max_abs_spearman = float(corr["abs_spearman_to_reentry_pnl"].dropna().max()) if corr["abs_spearman_to_reentry_pnl"].notna().any() else 0.0
    if len(ready) == len(features):
        decision_label = "stage066_reentry_tick_microstructure_full_coverage_ready_no_rule_yet"
    else:
        decision_label = "stage066_reentry_tick_microstructure_expansion_partial_no_rule"

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "created_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": decision_label,
        "strategy_rule_created": False,
        "true_engine_run": False,
        "ab_triggered": False,
        "credential_status": credential_status,
        "input_reentry_event_count": int(len(features)),
        "download_plan_event_count": int(len(plan)),
        "download_attempt_event_count": int(len(download_status)),
        "stage066_ready_count": int(len(stage066_ready)),
        "microstructure_ready_count": int(len(ready)),
        "microstructure_ready_pct": float(100.0 * len(ready) / len(features)) if len(features) else 0.0,
        "microstructure_missing_count": int(len(missing)),
        "ready_reentry_lot_pnl": float(ready["reentry_lot_pnl"].sum()) if not ready.empty else 0.0,
        "missing_reentry_lot_pnl": float(missing["reentry_lot_pnl"].sum()) if not missing.empty else 0.0,
        "ready_product_count": int(ready["normalized_product"].nunique()) if not ready.empty else 0,
        "ready_year_count": int(ready["reentry_year"].nunique()) if not ready.empty else 0,
        "max_abs_spearman_feature_pnl": max_abs_spearman,
        "judgment": (
            "Stage066 only expands point-in-time tick microstructure coverage using the fixed Stage065 spec. "
            "Even if full reentry coverage is reached, spread/depth/imbalance/OI fields remain audit features until "
            "their shape is visually stable, cross-year, and shown not to cut the C9 right tail."
        ),
        "outputs": {
            "summary": SUMMARY_OUT,
            "download_status": DOWNLOAD_STATUS_OUT,
            "event_features": EVENT_FEATURES_OUT,
            "coverage_summary": COVERAGE_OUT,
            "feature_correlations": CORR_OUT,
            "report": REPORT_OUT,
            "official_path_tick_coverage_chart": PATH_CHART_OUT,
            "microstructure_scatter": SCATTER_OUT,
            "coverage_product_year_heatmap": HEATMAP_OUT,
            "download_status_chart": STATUS_CHART_OUT,
            "microstructure_atlas": ATLAS_OUT,
            "raw_tick_dir": RAW_TICK_DIR,
        },
    }
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "line_id": LINE_ID,
                "model_tag": MODEL_TAG,
                "created_at": decision["created_at"],
                "decision": decision["decision"],
                "strategy_rule_created": False,
                "true_engine_run": False,
                "ab_triggered": False,
                "input_reentry_event_count": decision["input_reentry_event_count"],
                "download_plan_event_count": decision["download_plan_event_count"],
                "download_attempt_event_count": decision["download_attempt_event_count"],
                "stage066_ready_count": decision["stage066_ready_count"],
                "microstructure_ready_count": decision["microstructure_ready_count"],
                "microstructure_ready_pct": decision["microstructure_ready_pct"],
                "microstructure_missing_count": decision["microstructure_missing_count"],
                "ready_reentry_lot_pnl": decision["ready_reentry_lot_pnl"],
                "missing_reentry_lot_pnl": decision["missing_reentry_lot_pnl"],
                "ready_product_count": decision["ready_product_count"],
                "ready_year_count": decision["ready_year_count"],
                "max_abs_spearman_feature_pnl": decision["max_abs_spearman_feature_pnl"],
            }
        ]
    )

    summary.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    download_status.to_csv(DOWNLOAD_STATUS_OUT, index=False, encoding="utf-8-sig")
    features.to_csv(EVENT_FEATURES_OUT, index=False, encoding="utf-8-sig")
    coverage.to_csv(COVERAGE_OUT, index=False, encoding="utf-8-sig")
    corr.to_csv(CORR_OUT, index=False, encoding="utf-8-sig")
    _plot_path(features)
    _plot_scatter(features)
    _plot_heatmap(features)
    _plot_status(download_status)
    _plot_atlas(features)
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, coverage, corr, download_status)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
