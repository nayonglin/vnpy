from __future__ import annotations

from datetime import datetime
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
STAGE = "Stage079"
MODEL_TAG = "stage079_tqsdk_tick_manifest_transform_smoke_v1"
OUTPUT_PREFIX = "qmt_roll_stage079_c9_minrisk_tqsdk_tick_manifest_transform_smoke"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage079_tqsdk_tick_manifest_transform_smoke"
RAW_TICK_DIR = OUTPUT_DIR / "raw_tick"

STAGE045_DIR = LINE_DIR / "outputs" / "stage045_event_time_field_sync_audit"
STAGE074_DIR = LINE_DIR / "outputs" / "stage074_initial_entry_authoritative_source_decision_audit"
STAGE078_DIR = LINE_DIR / "outputs" / "stage078_tqsdk_dur0_tick_transform_gate_audit"

STAGE045_CURVE_IN = (
    STAGE045_DIR
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE074_AUDIT_IN = (
    STAGE074_DIR
    / "qmt_roll_stage074_c9_minrisk_initial_entry_authoritative_source_decision_audit_source_decision_audit_"
    "stage074_initial_entry_authoritative_source_decision_audit_v1.csv"
)
STAGE078_MANIFEST_IN = (
    STAGE078_DIR
    / "qmt_roll_stage078_c9_minrisk_tqsdk_dur0_tick_transform_gate_audit_manifest_"
    "stage078_tqsdk_dur0_tick_transform_gate_audit_v1.csv"
)

DOWNLOAD_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_download_status_{MODEL_TAG}.csv"
TRANSFORM_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_transform_audit_{MODEL_TAG}.csv"
YEAR_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_transform_matrix_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
OFFICIAL_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_transform_chart_{MODEL_TAG}.png"
YEAR_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_transform_matrix_chart_{MODEL_TAG}.png"
TICK_ATLAS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tick_transform_atlas_{MODEL_TAG}.png"

OFFICIAL_LIVE_VERSION = "official_live_stage847_c9_15w_stage819_05r_stop_retry_once"
OFFICIAL_LIVE_ALIAS = "Stage847-C9-15w"
INITIAL_CAPITAL = 150_000.0
PRICE_TOL = 1e-9

ENABLE_TQSDK = os.getenv("STAGE079_ENABLE_TQSDK", "0").strip() == "1"
MAX_EVENTS = int(os.getenv("STAGE079_MAX_EVENTS", "0"))
MAX_SECONDS_PER_EVENT = int(os.getenv("STAGE079_MAX_SECONDS_PER_EVENT", "25"))
TICK_DATA_LENGTH = int(os.getenv("STAGE079_TICK_DATA_LENGTH", "12000"))


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
        if pd.isna(value):
            return None
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


def _safe_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


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


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    display = data.copy()
    for col in display.columns:
        if pd.api.types.is_float_dtype(display[col]):
            display[col] = display[col].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    lines = [
        "| " + " | ".join(str(col) for col in display.columns) + " |",
        "| " + " | ".join(["---"] * len(display.columns)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[col]) for col in display.columns) + " |")
    return "\n".join(lines)


def _get_credentials() -> tuple[str, str, dict[str, Any]]:
    try:
        from vnpy.trader.setting import SETTINGS

        username = str(SETTINGS.get("datafeed.username", "") or "")
        password = str(SETTINGS.get("datafeed.password", "") or "")
        name = str(SETTINGS.get("datafeed.name", "") or "")
    except Exception as exc:
        return "", "", {"credential_status": f"read_failed:{type(exc).__name__}", "datafeed_name": ""}
    return username, password, {
        "credential_status": "available" if username and password else "missing",
        "datafeed_name": name,
        "username_present": int(bool(username)),
        "password_present": int(bool(password)),
    }


def _probe_environment() -> dict[str, Any]:
    info = {
        "tqsdk_import_ok": 0,
        "tqsdk_version": "",
        "enable_tqsdk": int(ENABLE_TQSDK),
        "max_seconds_per_event": MAX_SECONDS_PER_EVENT,
        "tick_data_length": TICK_DATA_LENGTH,
    }
    try:
        __import__("tqsdk")
        info["tqsdk_import_ok"] = 1
        try:
            info["tqsdk_version"] = importlib.metadata.version("tqsdk")
        except importlib.metadata.PackageNotFoundError:
            info["tqsdk_version"] = "unknown"
    except Exception as exc:
        info["tqsdk_import_error"] = type(exc).__name__
    return info


def _prepare_manifest() -> pd.DataFrame:
    manifest = _read_csv(STAGE078_MANIFEST_IN)
    audit = _read_csv(STAGE074_AUDIT_IN)[
        [
            "candidate_index",
            "raw_anchor_open",
            "raw_anchor_high",
            "raw_anchor_low",
            "raw_anchor_close",
            "raw_anchor_volume",
            "stage449_anchor_open",
            "stage449_anchor_high",
            "stage449_anchor_low",
            "stage449_anchor_close",
            "stage449_anchor_volume",
            "realized_pnl",
            "source_decision_class",
        ]
    ].copy()
    audit["candidate_index"] = _safe_num(audit["candidate_index"]).astype(int)
    data = manifest.merge(audit, on="candidate_index", how="left", suffixes=("", "_stage074"))
    for col in [
        "official_open_date",
        "authority_anchor_time",
        "download_start_dt",
        "download_end_dt",
    ]:
        data[col] = pd.to_datetime(data[col], errors="coerce")
    for col in [
        "candidate_index",
        "official_open_year",
        "dur_sec",
    ]:
        data[col] = _safe_num(data[col]).astype(int)
    for col in [
        "official_open_price",
        "raw_anchor_open",
        "stage449_anchor_open",
        "realized_pnl",
    ]:
        data[col] = _safe_num(data.get(col, pd.Series(np.nan, index=data.index)))
    data = data.sort_values(["official_open_year", "official_open_date", "candidate_index"]).reset_index(drop=True)
    if MAX_EVENTS > 0:
        data = data.head(MAX_EVENTS).copy()
    for idx, row in data.iterrows():
        code, exchange = str(row["vt_symbol"]).split(".", 1)
        filename = str(row["download_csv_file_suggestion"])
        data.at[idx, "raw_tick_path"] = str(RAW_TICK_DIR / exchange / filename)
    return data


def _download_or_read_tick(row: pd.Series, username: str, password: str, cred: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(row["raw_tick_path"]))
    status: dict[str, Any] = {
        "candidate_index": int(row["candidate_index"]),
        "official_open_trade_id": row["official_open_trade_id"],
        "vt_symbol": row["vt_symbol"],
        "tq_symbol": row["tq_symbol"],
        "authority_anchor_time": row["authority_anchor_time"],
        "download_start_dt": row["download_start_dt"],
        "download_end_dt": row["download_end_dt"],
        "tick_path": str(path),
        "credential_status": cred.get("credential_status", ""),
        "download_status": "unknown",
        "tick_rows": 0,
        "target_tick_rows": 0,
        "message": "",
    }
    if path.exists() and path.stat().st_size > 0:
        try:
            ticks = pd.read_csv(path, encoding="utf-8-sig")
            status["download_status"] = "cached_stage079"
            status.update(_evaluate_tick_rows(row, ticks))
            return status
        except Exception as exc:
            status["message"] = f"cached_read_failed:{type(exc).__name__}:{exc}"

    if not ENABLE_TQSDK:
        status["download_status"] = "planned_not_downloaded"
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

    path.parent.mkdir(parents=True, exist_ok=True)
    logging.getLogger().setLevel(logging.WARNING)
    logging.getLogger("tqsdk").setLevel(logging.WARNING)
    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
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
            if key in seen:
                continue
            seen.add(key)
            record = {
                "candidate_index": int(row["candidate_index"]),
                "official_open_trade_id": row["official_open_trade_id"],
                "vt_symbol": row["vt_symbol"],
                "tq_symbol": row["tq_symbol"],
                "anchor_time": row["authority_anchor_time"],
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

    ticks = pd.DataFrame(rows)
    if not ticks.empty:
        ticks["tick_datetime"] = pd.to_datetime(ticks["tick_datetime"], errors="coerce")
        ticks = ticks.dropna(subset=["tick_datetime"])
        dedup_cols = ["candidate_index", "tick_datetime", "last_price"] if "last_price" in ticks.columns else ["candidate_index", "tick_datetime"]
        ticks = ticks.drop_duplicates(dedup_cols, keep="last").sort_values(["candidate_index", "tick_datetime"])
        ticks.to_csv(path, index=False, encoding="utf-8-sig")
    if status["download_status"] == "unknown":
        status["download_status"] = "extracted" if not ticks.empty else "empty"
    status.update(_evaluate_tick_rows(row, ticks))
    return status


def _target_minute_bounds(anchor_time: Any) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = _timestamp(anchor_time).floor("min")
    return start, start + pd.Timedelta(minutes=1)


def _evaluate_tick_rows(row: pd.Series, ticks: pd.DataFrame) -> dict[str, Any]:
    result = {"tick_rows": int(len(ticks)), "target_tick_rows": 0}
    if ticks.empty or "tick_datetime" not in ticks.columns:
        return result
    data = ticks.copy()
    data["tick_datetime"] = pd.to_datetime(data["tick_datetime"], errors="coerce")
    data = data.dropna(subset=["tick_datetime"]).sort_values("tick_datetime")
    start, end = _target_minute_bounds(row["authority_anchor_time"])
    target = data[(data["tick_datetime"] >= start) & (data["tick_datetime"] < end)]
    result["tick_rows"] = int(len(data))
    result["target_tick_rows"] = int(len(target))
    return result


def _download_manifest(manifest: pd.DataFrame) -> pd.DataFrame:
    username, password, cred = _get_credentials()
    rows: list[dict[str, Any]] = []
    total = len(manifest)
    for pos, (_, row) in enumerate(manifest.iterrows(), start=1):
        print(
            f"{STAGE} tick manifest {pos}/{total}: candidate={int(row['candidate_index'])} "
            f"{row['tq_symbol']} {pd.Timestamp(row['authority_anchor_time']).strftime('%Y-%m-%d %H:%M:%S')}",
            flush=True,
        )
        rows.append(_download_or_read_tick(row, username, password, cred))
    status = pd.DataFrame(rows)
    status["tick_file_exists_after"] = status["tick_path"].map(lambda p: int(Path(str(p)).exists()))
    return status


def _load_ticks(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        ticks = pd.read_csv(path, encoding="utf-8-sig")
    except Exception:
        return pd.DataFrame()
    if "tick_datetime" not in ticks.columns:
        return pd.DataFrame()
    ticks["tick_datetime"] = pd.to_datetime(ticks["tick_datetime"], errors="coerce")
    ticks = ticks.dropna(subset=["tick_datetime"]).sort_values("tick_datetime")
    for col in [
        "last_price",
        "bid_price1",
        "ask_price1",
        "volume",
        "amount",
        "open_interest",
    ]:
        if col in ticks.columns:
            ticks[col] = _safe_num(ticks[col])
    return ticks


def _transform_row(row: pd.Series, status_row: pd.Series) -> dict[str, Any]:
    path = Path(str(row["raw_tick_path"]))
    ticks = _load_ticks(path)
    start, end = _target_minute_bounds(row["authority_anchor_time"])
    target = ticks[(ticks["tick_datetime"] >= start) & (ticks["tick_datetime"] < end)].copy() if not ticks.empty else pd.DataFrame()
    official_price = _safe_float(row["official_open_price"])
    raw_open = _safe_float(row.get("raw_anchor_open"))
    stage449_open = _safe_float(row.get("stage449_anchor_open"))
    result = {
        "candidate_index": int(row["candidate_index"]),
        "official_open_trade_id": row["official_open_trade_id"],
        "vt_symbol": row["vt_symbol"],
        "tq_symbol": row["tq_symbol"],
        "direction": row["direction"],
        "official_open_year": int(row["official_open_year"]),
        "official_open_date": pd.Timestamp(row["official_open_date"]).strftime("%Y-%m-%d"),
        "authority_anchor_time": pd.Timestamp(row["authority_anchor_time"]).strftime("%Y-%m-%d %H:%M:%S"),
        "official_open_price": official_price,
        "raw_anchor_open": raw_open,
        "stage449_anchor_open": stage449_open,
        "download_status": status_row.get("download_status", ""),
        "tick_path": str(path),
        "tick_rows_total": int(len(ticks)),
        "tick_rows_target_minute": int(len(target)),
        "rebuilt_open_last": np.nan,
        "rebuilt_high_last": np.nan,
        "rebuilt_low_last": np.nan,
        "rebuilt_close_last": np.nan,
        "rebuilt_volume_delta": np.nan,
        "rebuilt_open_interest_first": np.nan,
        "rebuilt_open_exact_official": 0,
        "rebuilt_open_exact_raw": 0,
        "rebuilt_open_exact_stage449": 0,
        "any_last_bid_ask_exact_official": 0,
        "official_inside_any_spread": 0,
        "same_source_transform_verified": 0,
        "rule_candidate_allowed": 0,
        "realized_pnl": _safe_float(row.get("realized_pnl"), 0.0),
        "source_decision_class": row.get("source_decision_class", ""),
    }
    if target.empty or not np.isfinite(official_price):
        return result
    if "last_price" in target.columns:
        last = target["last_price"].dropna()
        if not last.empty:
            result["rebuilt_open_last"] = float(last.iloc[0])
            result["rebuilt_high_last"] = float(last.max())
            result["rebuilt_low_last"] = float(last.min())
            result["rebuilt_close_last"] = float(last.iloc[-1])
            result["rebuilt_open_exact_official"] = int(abs(float(last.iloc[0]) - official_price) <= PRICE_TOL)
            if np.isfinite(raw_open):
                result["rebuilt_open_exact_raw"] = int(abs(float(last.iloc[0]) - raw_open) <= PRICE_TOL)
            if np.isfinite(stage449_open):
                result["rebuilt_open_exact_stage449"] = int(abs(float(last.iloc[0]) - stage449_open) <= PRICE_TOL)
    if "volume" in ticks.columns and not ticks["volume"].dropna().empty:
        target_volume = target["volume"].dropna()
        previous = ticks[ticks["tick_datetime"] < start]["volume"].dropna()
        if not target_volume.empty:
            prev = float(previous.iloc[-1]) if not previous.empty else float(target_volume.iloc[0])
            result["rebuilt_volume_delta"] = max(0.0, float(target_volume.iloc[-1]) - prev)
    if "open_interest" in target.columns and not target["open_interest"].dropna().empty:
        result["rebuilt_open_interest_first"] = float(target["open_interest"].dropna().iloc[0])
    exact_fields = []
    for col in ["last_price", "bid_price1", "ask_price1"]:
        if col in target.columns:
            exact_fields.append(target[col].sub(official_price).abs().le(PRICE_TOL).any())
    result["any_last_bid_ask_exact_official"] = int(any(exact_fields)) if exact_fields else 0
    if {"bid_price1", "ask_price1"}.issubset(target.columns):
        bid = target["bid_price1"]
        ask = target["ask_price1"]
        result["official_inside_any_spread"] = int(((bid <= official_price) & (official_price <= ask)).any())
    result["same_source_transform_verified"] = int(
        result["rebuilt_open_exact_official"] == 1
        and (result["rebuilt_open_exact_raw"] == 1 or result["rebuilt_open_exact_stage449"] == 1)
        and result["tick_rows_target_minute"] > 0
    )
    return result


def _build_transform_audit(manifest: pd.DataFrame, status: pd.DataFrame) -> pd.DataFrame:
    by_candidate = status.set_index("candidate_index", drop=False)
    rows = []
    for _, row in manifest.iterrows():
        candidate = int(row["candidate_index"])
        status_row = by_candidate.loc[candidate] if candidate in by_candidate.index else pd.Series(dtype=object)
        rows.append(_transform_row(row, status_row))
    return pd.DataFrame(rows)


def _year_matrix(transform: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year, group in transform.groupby("official_open_year"):
        rows.append(
            {
                "year": int(year),
                "manifest_rows": int(len(group)),
                "extracted_or_cached": int(group["download_status"].astype(str).isin(["extracted", "cached_stage079"]).sum()),
                "target_tick_ready": int((group["tick_rows_target_minute"] > 0).sum()),
                "rebuilt_open_exact_official": int(group["rebuilt_open_exact_official"].sum()),
                "same_source_transform_verified": int(group["same_source_transform_verified"].sum()),
                "rule_candidate_allowed": int(group["rule_candidate_allowed"].sum()),
                "net_realized_pnl": float(group["realized_pnl"].sum()),
            }
        )
    return pd.DataFrame(rows)


def _official_metrics(curve: pd.DataFrame) -> dict[str, float]:
    curve = curve.copy()
    equity = _safe_num(curve["official_equity" if "official_equity" in curve.columns else "account_equity"]).dropna()
    dd = _safe_num(curve["official_drawdown_pct" if "official_drawdown_pct" in curve.columns else "drawdown_pct"]).dropna()
    daily_ret = _safe_num(curve.get("daily_return", pd.Series(dtype=float))).dropna()
    sharpe = np.nan
    if len(daily_ret) > 2 and daily_ret.std(ddof=1) > 0:
        sharpe = float(daily_ret.mean() / daily_ret.std(ddof=1) * np.sqrt(252))
    return {
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": (float(equity.iloc[-1]) / INITIAL_CAPITAL - 1.0) * 100.0,
        "max_drawdown_pct": float(dd.min()),
        "sharpe": sharpe,
        "total_slippage": float(_safe_num(curve.get("slippage", pd.Series(dtype=float))).fillna(0.0).sum()),
        "total_trade_count": float(_safe_num(curve.get("trade_count", pd.Series(dtype=float))).sum()),
    }


def _decision(summary: dict[str, Any]) -> tuple[str, str]:
    if summary["download_attempted"] == 0:
        return (
            "stage079_not_downloaded_no_rule",
            "rerun_with_STAGE079_ENABLE_TQSDK_1_or_stop_if_no_download_permission",
        )
    if summary["download_success_count"] == 0:
        return (
            "stage079_dur0_tick_download_blocked_or_empty_no_rule",
            "check_tqsdk_permission_or_use_authorized_vendor_tick_before_rules",
        )
    if (
        summary["same_source_transform_verified_count"] == summary["manifest_size"]
        and summary["transform_verified_year_count"] >= summary["manifest_year_count"]
    ):
        return (
            "stage079_small_manifest_transform_smoke_pass_expand_full_219_no_rule",
            "expand_to_all_timestamp_ready_initial_opens_before_microstructure_rules",
        )
    return (
        "stage079_small_manifest_transform_mixed_no_rule",
        "inspect_mismatch_by_year_then_either_fix_transform_or_downgrade_tq_tick_to_tca",
    )


def _plot_official_path(curve: pd.DataFrame, transform: pd.DataFrame) -> None:
    curve = curve.copy()
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce")
    transform = transform.copy()
    transform["official_open_date"] = pd.to_datetime(transform["official_open_date"], errors="coerce")
    transform["bucket"] = np.select(
        [
            transform["same_source_transform_verified"].eq(1),
            transform["tick_rows_target_minute"].gt(0),
            transform["download_status"].astype(str).isin(["failed", "timeout", "empty"]),
        ],
        ["transform_verified", "tick_ready_not_verified", "download_failed_or_empty"],
        default="not_downloaded_or_missing",
    )
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=False, gridspec_kw={"height_ratios": [2, 1, 1.2]})
    equity_col = "official_equity" if "official_equity" in curve.columns else "account_equity"
    dd_col = "official_drawdown_pct" if "official_drawdown_pct" in curve.columns else "drawdown_pct"
    axes[0].plot(curve["date"], curve[equity_col], color="#1f77b4", lw=1.8, label="Official C9/15w equity")
    colors = {
        "transform_verified": "#2ca02c",
        "tick_ready_not_verified": "#ff7f0e",
        "download_failed_or_empty": "#d62728",
        "not_downloaded_or_missing": "#7f7f7f",
    }
    for bucket, data in transform.groupby("bucket"):
        axes[0].scatter(
            data["official_open_date"],
            np.interp(
                data["official_open_date"].astype("int64"),
                curve["date"].astype("int64"),
                curve[equity_col],
            ),
            s=38,
            color=colors.get(bucket, "#7f7f7f"),
            label=bucket,
            alpha=0.85,
        )
    axes[0].set_title("Official path unchanged; Stage079 tick manifest is a data-transform gate")
    axes[0].set_ylabel("Equity")
    axes[0].grid(alpha=0.25)
    axes[0].legend(loc="upper left", fontsize=8)
    axes[1].plot(curve["date"], curve[dd_col], color="#9467bd", lw=1.4)
    axes[1].fill_between(curve["date"], curve[dd_col], 0, color="#9467bd", alpha=0.15)
    axes[1].set_ylabel("Drawdown %")
    axes[1].grid(alpha=0.25)
    for bucket, data in transform.groupby("bucket"):
        daily = data.sort_values("official_open_date").set_index("official_open_date")["realized_pnl"].cumsum()
        axes[2].plot(daily.index, daily.values, color=colors.get(bucket, "#7f7f7f"), marker="o", lw=1.4, label=bucket)
    axes[2].axhline(0, color="black", lw=0.8, alpha=0.5)
    axes[2].set_title("Manifest realized PnL by transform bucket (distribution only)")
    axes[2].set_ylabel("Cumulative PnL")
    axes[2].grid(alpha=0.25)
    axes[2].legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(OFFICIAL_PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_year_matrix(year: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    if year.empty:
        ax.text(0.5, 0.5, "empty year matrix", ha="center", va="center")
        ax.set_axis_off()
    else:
        x = np.arange(len(year))
        width = 0.16
        bars = [
            ("manifest_rows", "#1f77b4"),
            ("extracted_or_cached", "#ff7f0e"),
            ("target_tick_ready", "#2ca02c"),
            ("rebuilt_open_exact_official", "#d62728"),
            ("same_source_transform_verified", "#9467bd"),
        ]
        for idx, (col, color) in enumerate(bars):
            ax.bar(x + (idx - 2) * width, year[col], width=width, label=col, color=color, alpha=0.85)
        ax.set_xticks(x)
        ax.set_xticklabels(year["year"].astype(str))
        ax.set_title("Stage079 tick download and transform coverage by year")
        ax.set_ylabel("Count")
        ax.grid(axis="y", alpha=0.25)
        ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(YEAR_MATRIX_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_tick_atlas(transform: pd.DataFrame) -> None:
    sample = transform.sort_values(["same_source_transform_verified", "tick_rows_target_minute", "official_open_year"], ascending=[False, False, True]).head(8)
    if sample.empty:
        return
    fig, axes = plt.subplots(len(sample), 1, figsize=(14, max(4, 2.2 * len(sample))), squeeze=False)
    for i, (_, row) in enumerate(sample.iterrows()):
        ax = axes[i, 0]
        ticks = _load_ticks(Path(str(row["tick_path"])))
        start, end = _target_minute_bounds(row["authority_anchor_time"])
        window = pd.DataFrame()
        if not ticks.empty and "tick_datetime" in ticks.columns:
            window = ticks[
                (ticks["tick_datetime"] >= start - pd.Timedelta(seconds=20))
                & (ticks["tick_datetime"] <= end + pd.Timedelta(seconds=20))
            ].copy()
        if not window.empty:
            for col, color, label in [
                ("last_price", "#1f77b4", "last"),
                ("ask_price1", "#d62728", "ask1"),
                ("bid_price1", "#2ca02c", "bid1"),
            ]:
                if col in window.columns:
                    ax.plot(window["tick_datetime"], window[col], color=color, lw=1.0, alpha=0.8, label=label)
        else:
            ax.text(0.5, 0.5, "no local tick rows", transform=ax.transAxes, ha="center", va="center", fontsize=9)
        for col, color, label in [
            ("official_open_price", "black", "official"),
            ("raw_anchor_open", "#ff7f0e", "raw"),
            ("stage449_anchor_open", "#9467bd", "stage449"),
        ]:
            value = _safe_float(row.get(col))
            if np.isfinite(value):
                ax.axhline(value, color=color, linestyle="--", lw=0.8, label=label)
        ax.axvline(start, color="#999999", linestyle=":", lw=0.8)
        ax.set_title(
            f"candidate {int(row['candidate_index'])} {row['vt_symbol']} {row['authority_anchor_time']} "
            f"target_ticks={int(row['tick_rows_target_minute'])} transform={int(row['same_source_transform_verified'])}",
            fontsize=9,
        )
        ax.grid(alpha=0.22)
        ax.legend(loc="upper left", fontsize=6, ncol=4)
    fig.tight_layout()
    fig.savefig(TICK_ATLAS_OUT, dpi=160)
    plt.close(fig)


def _write_report(summary: dict[str, Any], transform: pd.DataFrame, year: pd.DataFrame) -> None:
    cols = [
        "candidate_index",
        "vt_symbol",
        "official_open_date",
        "authority_anchor_time",
        "download_status",
        "tick_rows_target_minute",
        "rebuilt_open_last",
        "official_open_price",
        "same_source_transform_verified",
        "rule_candidate_allowed",
    ]
    lines = [
        "# Stage079 TqSdk tick manifest transform smoke",
        "",
        f"- decision: `{summary['decision']}`",
        f"- next_step: `{summary['next_step']}`",
        f"- official: `{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "",
        "## Summary",
        "",
        _md_table(pd.DataFrame([summary])),
        "",
        "## Transform Audit Head",
        "",
        _md_table(transform[cols], max_rows=16),
        "",
        "## Year Matrix",
        "",
        _md_table(year),
        "",
        "## Visual Outputs",
        "",
        f"- official path transform chart: `{OFFICIAL_PATH_CHART_OUT.relative_to(REPO_DIR)}`",
        f"- year matrix chart: `{YEAR_MATRIX_CHART_OUT.relative_to(REPO_DIR)}`",
        f"- tick atlas: `{TICK_ATLAS_OUT.relative_to(REPO_DIR)}`",
        "",
        "## Interpretation",
        "",
        "- This stage is a data-transform smoke test only; it does not add a trading rule or run a true engine.",
        "- `same_source_transform_verified` means the first tick last price in the anchor minute exactly reproduces the official/raw or Stage449 open for that row.",
        "- Even if the small manifest passes, rule permission remains `0` until the full timestamp-ready initial-open set is covered and visually stable.",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_TICK_DIR.mkdir(parents=True, exist_ok=True)
    manifest = _prepare_manifest()
    curve = _read_csv(STAGE045_CURVE_IN)
    env = _probe_environment()
    status = _download_manifest(manifest)
    transform = _build_transform_audit(manifest, status)
    year = _year_matrix(transform)
    metrics = _official_metrics(curve)
    success_statuses = {"extracted", "cached_stage079"}
    summary = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        **metrics,
        **env,
        "manifest_size": int(len(manifest)),
        "manifest_year_count": int(manifest["official_open_year"].nunique()),
        "download_attempted": int(ENABLE_TQSDK),
        "download_success_count": int(status["download_status"].astype(str).isin(success_statuses).sum()),
        "download_failed_or_empty_count": int(status["download_status"].astype(str).isin(["failed", "timeout", "empty"]).sum()),
        "target_tick_ready_count": int((transform["tick_rows_target_minute"] > 0).sum()),
        "rebuilt_open_exact_official_count": int(transform["rebuilt_open_exact_official"].sum()),
        "same_source_transform_verified_count": int(transform["same_source_transform_verified"].sum()),
        "transform_verified_year_count": int(
            transform[transform["same_source_transform_verified"].eq(1)]["official_open_year"].nunique()
        ),
        "rule_candidate_allowed_count": int(transform["rule_candidate_allowed"].sum()),
    }
    decision, next_step = _decision(summary)
    summary["decision"] = decision
    summary["next_step"] = next_step
    _write_csv(status, DOWNLOAD_STATUS_OUT)
    _write_csv(transform, TRANSFORM_AUDIT_OUT)
    _write_csv(year, YEAR_MATRIX_OUT)
    _write_csv(pd.DataFrame([summary]), SUMMARY_OUT)
    DECISION_OUT.write_text(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot_official_path(curve, transform)
    _plot_year_matrix(year)
    _plot_tick_atlas(transform)
    _write_report(summary, transform, year)
    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
