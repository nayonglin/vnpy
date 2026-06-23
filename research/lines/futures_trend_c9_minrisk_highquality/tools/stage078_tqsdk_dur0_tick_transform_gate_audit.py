from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage078"
MODEL_TAG = "stage078_tqsdk_dur0_tick_transform_gate_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage078_c9_minrisk_tqsdk_dur0_tick_transform_gate_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage078_tqsdk_dur0_tick_transform_gate_audit"

STAGE045_DIR = LINE_DIR / "outputs" / "stage045_event_time_field_sync_audit"
STAGE074_DIR = LINE_DIR / "outputs" / "stage074_initial_entry_authoritative_source_decision_audit"
STAGE077_DIR = LINE_DIR / "outputs" / "stage077_raw_authority_provenance_tick_backfill_feasibility"

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
STAGE077_SUMMARY_IN = (
    STAGE077_DIR
    / "qmt_roll_stage077_c9_minrisk_raw_authority_provenance_tick_backfill_feasibility_summary_"
    "stage077_raw_authority_provenance_tick_backfill_feasibility_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.csv"
DOWNLOAD_PLAN_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_download_plan_{MODEL_TAG}.csv"
LOCAL_TICK_CATALOG_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_local_tick_catalog_{MODEL_TAG}.csv"
YEAR_GATE_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_gate_matrix_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
OFFICIAL_GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_tq_gate_chart_{MODEL_TAG}.png"
READINESS_ATLAS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readiness_gate_atlas_{MODEL_TAG}.png"
MANIFEST_COVERAGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_manifest_coverage_chart_{MODEL_TAG}.png"

OFFICIAL_LIVE_VERSION = "official_live_stage847_c9_15w_stage819_05r_stop_retry_once"
OFFICIAL_LIVE_ALIAS = "Stage847-C9-15w"
INITIAL_CAPITAL = 150_000.0
MANIFEST_PER_YEAR = 4


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


def _probe_tqsdk_environment() -> dict[str, Any]:
    info: dict[str, Any] = {
        "tqsdk_import_ok": 0,
        "tqsdk_version": "",
        "data_downloader_import_ok": 0,
        "datafeed_username_present": 0,
        "datafeed_password_present": 0,
        "env_username_present": int(bool(os.environ.get("TQSDK_USERNAME") or os.environ.get("TQ_USER"))),
        "env_password_present": int(bool(os.environ.get("TQSDK_PASSWORD") or os.environ.get("TQ_PASS"))),
        "download_allowed_by_env": int(os.environ.get("STAGE078_ALLOW_TQSDK_DOWNLOAD", "0") == "1"),
        "download_attempted": 0,
    }
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            __import__("tqsdk")
        info["tqsdk_import_ok"] = 1
        try:
            info["tqsdk_version"] = importlib.metadata.version("tqsdk")
        except importlib.metadata.PackageNotFoundError:
            info["tqsdk_version"] = "unknown"
    except Exception as exc:  # pragma: no cover - local environment dependent
        info["tqsdk_import_error"] = type(exc).__name__
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            from tqsdk.tools import DataDownloader  # noqa: F401

        info["data_downloader_import_ok"] = 1
    except Exception as exc:  # pragma: no cover - local environment dependent
        info["data_downloader_import_error"] = type(exc).__name__
    try:
        from vnpy.trader.setting import SETTINGS

        info["datafeed_username_present"] = int(bool(SETTINGS.get("datafeed.username")))
        info["datafeed_password_present"] = int(bool(SETTINGS.get("datafeed.password")))
    except Exception as exc:  # pragma: no cover - local environment dependent
        info["vnpy_setting_error"] = type(exc).__name__
    return info


def _to_tq_symbol(vt_symbol: str) -> str:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return f"{exchange}.{symbol}"


def _prepare_stage074(stage074: pd.DataFrame) -> pd.DataFrame:
    audit = stage074.copy()
    audit["official_open_date"] = pd.to_datetime(audit["official_open_date"], errors="coerce")
    audit["authority_anchor_time"] = pd.to_datetime(audit["authority_anchor_time"], errors="coerce")
    audit["official_open_year"] = _safe_num(audit["official_open_year"]).fillna(
        audit["official_open_date"].dt.year
    ).astype(int)
    for col in [
        "candidate_index",
        "timestamp_ready",
        "raw_anchor_ready",
        "raw_anchor_exact_official",
        "stage449_anchor_ready",
        "stage449_anchor_exact_official",
        "tq_proxy_anchor_ready",
        "tq_price_exact_any",
        "tq_official_open_inside_any_spread",
    ]:
        audit[col] = _safe_num(audit.get(col, pd.Series(0, index=audit.index))).fillna(0).astype(int)
    for col in [
        "official_open_price",
        "raw_anchor_open",
        "stage449_anchor_open",
        "tq_min_abs_price_delta_r",
        "realized_pnl",
    ]:
        audit[col] = _safe_num(audit.get(col, pd.Series(np.nan, index=audit.index)))
    audit["tq_symbol"] = audit["vt_symbol"].map(_to_tq_symbol)
    audit = audit.sort_values(["official_open_date", "candidate_index", "official_open_trade_id"]).reset_index(drop=True)
    return audit


def _select_manifest(audit: pd.DataFrame) -> pd.DataFrame:
    ready = audit[(audit["timestamp_ready"] == 1) & audit["authority_anchor_time"].notna()].copy()
    ready["manifest_rank_in_year"] = ready.groupby("official_open_year").cumcount() + 1
    manifest = ready[ready["manifest_rank_in_year"] <= MANIFEST_PER_YEAR].copy()
    manifest = manifest.sort_values(["official_open_year", "manifest_rank_in_year"]).reset_index(drop=True)
    manifest["download_start_dt"] = manifest["authority_anchor_time"] - pd.Timedelta(seconds=30)
    manifest["download_end_dt"] = manifest["authority_anchor_time"] + pd.Timedelta(seconds=90)
    manifest["dur_sec"] = 0
    manifest["selection_rule"] = (
        f"first_{MANIFEST_PER_YEAR}_timestamp_ready_initial_opens_per_year_sorted_by_date_no_pnl_filter"
    )
    manifest["download_csv_file_suggestion"] = manifest.apply(
        lambda row: (
            f"{str(row['vt_symbol']).replace('.', '_')}_"
            f"{pd.Timestamp(row['authority_anchor_time']).strftime('%Y%m%d_%H%M%S')}_"
            f"candidate_{int(row['candidate_index'])}_dur0_tick.csv"
        ),
        axis=1,
    )
    return manifest


def _tick_datetime_column(columns: set[str]) -> str | None:
    for col in ["tick_datetime", "datetime", "datetime_nano", "time"]:
        if col in columns:
            return col
    return None


def _first_existing(columns: set[str], options: list[str]) -> str | None:
    for col in options:
        if col in columns:
            return col
    return None


def _normalize_tick_frame(path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    header = pd.read_csv(path, nrows=0, encoding="utf-8-sig")
    columns = set(header.columns)
    dt_col = _tick_datetime_column(columns)
    last_col = _first_existing(columns, ["last_price", "last"])
    bid_col = _first_existing(columns, ["bid_price1", "bid_price_1", "bid1"])
    ask_col = _first_existing(columns, ["ask_price1", "ask_price_1", "ask1"])
    volume_col = _first_existing(columns, ["volume", "last_volume", "volume_delta"])
    oi_col = _first_existing(columns, ["open_interest", "close_oi", "open_oi"])
    vt_col = _first_existing(columns, ["vt_symbol"])
    tq_col = _first_existing(columns, ["tq_symbol", "symbol"])
    required = [dt_col, last_col, bid_col, ask_col, volume_col]
    schema_ready = int(all(required))
    info = {
        "path": str(path),
        "file_name": path.name,
        "file_size_bytes": path.stat().st_size,
        "has_tick_schema": schema_ready,
        "datetime_column": dt_col or "",
        "last_price_column": last_col or "",
        "bid_price_column": bid_col or "",
        "ask_price_column": ask_col or "",
        "volume_column": volume_col or "",
        "open_interest_column": oi_col or "",
    }
    if not schema_ready:
        info.update(
            {
                "row_count": 0,
                "min_datetime": "",
                "max_datetime": "",
                "vt_symbols": "",
                "tq_symbols": "",
            }
        )
        return pd.DataFrame(), info
    usecols = [col for col in [dt_col, last_col, bid_col, ask_col, volume_col, oi_col, vt_col, tq_col] if col]
    frame = pd.read_csv(path, usecols=usecols, encoding="utf-8-sig")
    norm = pd.DataFrame(
        {
            "tick_datetime": pd.to_datetime(frame[dt_col], errors="coerce"),
            "last_price": _safe_num(frame[last_col]),
            "bid_price1": _safe_num(frame[bid_col]),
            "ask_price1": _safe_num(frame[ask_col]),
            "volume": _safe_num(frame[volume_col]),
            "source_file": str(path),
        }
    )
    if oi_col:
        norm["open_interest"] = _safe_num(frame[oi_col])
    if vt_col:
        norm["vt_symbol"] = frame[vt_col].astype(str)
    if tq_col:
        norm["tq_symbol"] = frame[tq_col].astype(str)
    norm = norm.dropna(subset=["tick_datetime"]).sort_values("tick_datetime").reset_index(drop=True)
    info.update(
        {
            "row_count": int(len(norm)),
            "min_datetime": "" if norm.empty else norm["tick_datetime"].min().strftime("%Y-%m-%d %H:%M:%S"),
            "max_datetime": "" if norm.empty else norm["tick_datetime"].max().strftime("%Y-%m-%d %H:%M:%S"),
            "vt_symbols": "" if "vt_symbol" not in norm else ",".join(sorted(norm["vt_symbol"].dropna().unique())[:5]),
            "tq_symbols": "" if "tq_symbol" not in norm else ",".join(sorted(norm["tq_symbol"].dropna().unique())[:5]),
        }
    )
    return norm, info


def _scan_local_tick_files() -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    tick_files = sorted(
        path
        for path in LINE_DIR.rglob("*.csv")
        if path.is_file()
        and "tick" in path.name.lower()
        and "stage078_tqsdk_dur0_tick_transform_gate_audit" not in str(path)
    )
    rows: list[dict[str, Any]] = []
    frames: dict[str, pd.DataFrame] = {}
    for path in tick_files:
        try:
            norm, info = _normalize_tick_frame(path)
            rows.append(info)
            if not norm.empty:
                frames[str(path)] = norm
        except Exception as exc:
            rows.append(
                {
                    "path": str(path),
                    "file_name": path.name,
                    "file_size_bytes": path.stat().st_size if path.exists() else 0,
                    "has_tick_schema": 0,
                    "row_count": 0,
                    "min_datetime": "",
                    "max_datetime": "",
                    "parse_error": type(exc).__name__,
                }
            )
    catalog = pd.DataFrame(rows)
    if catalog.empty:
        catalog = pd.DataFrame(
            columns=[
                "path",
                "file_name",
                "file_size_bytes",
                "has_tick_schema",
                "row_count",
                "min_datetime",
                "max_datetime",
            ]
        )
    return catalog, frames


def _price_exact_mask(series: pd.Series, price: float) -> pd.Series:
    values = _safe_num(series)
    return values.sub(price).abs().le(1e-9)


def _analyze_manifest(manifest: pd.DataFrame, tick_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    tick_paths = list(tick_frames.keys())
    for _, row in manifest.iterrows():
        candidate_index = int(row["candidate_index"])
        trade_id = str(row["official_open_trade_id"])
        candidate_token = f"candidate_{candidate_index}_".lower()
        trade_token = trade_id.replace(".", "_").lower()
        candidate_matches = [path for path in tick_paths if candidate_token in Path(path).name.lower()]
        trade_matches = [path for path in tick_paths if trade_token in Path(path).name.lower()]
        selected = sorted(set(candidate_matches))
        anchor_time = pd.Timestamp(row["authority_anchor_time"])
        start = pd.Timestamp(row["download_start_dt"])
        end = pd.Timestamp(row["download_end_dt"])
        official_price = _safe_float(row["official_open_price"])
        combined_parts: list[pd.DataFrame] = []
        for path in selected:
            frame = tick_frames[path]
            window = frame[(frame["tick_datetime"] >= start) & (frame["tick_datetime"] <= end)].copy()
            if not window.empty:
                window["source_file"] = path
                combined_parts.append(window)
        combined = pd.concat(combined_parts, ignore_index=True) if combined_parts else pd.DataFrame()
        result = {
            "candidate_index": candidate_index,
            "official_open_trade_id": trade_id,
            "vt_symbol": row["vt_symbol"],
            "tq_symbol": row["tq_symbol"],
            "direction": row["direction"],
            "official_open_date": pd.Timestamp(row["official_open_date"]).strftime("%Y-%m-%d"),
            "official_open_year": int(row["official_open_year"]),
            "official_open_price": official_price,
            "authority_anchor_time": anchor_time.strftime("%Y-%m-%d %H:%M:%S"),
            "download_start_dt": start.strftime("%Y-%m-%d %H:%M:%S"),
            "download_end_dt": end.strftime("%Y-%m-%d %H:%M:%S"),
            "dur_sec": 0,
            "raw_anchor_open": _safe_float(row.get("raw_anchor_open")),
            "stage449_anchor_open": _safe_float(row.get("stage449_anchor_open")),
            "stage074_tq_proxy_anchor_ready": int(row["tq_proxy_anchor_ready"]),
            "stage074_tq_price_exact_any": int(row["tq_price_exact_any"]),
            "stage074_tq_min_abs_price_delta_r": _safe_float(row.get("tq_min_abs_price_delta_r")),
            "candidate_token_match_count": int(len(candidate_matches)),
            "trade_token_match_count": int(len(trade_matches)),
            "matched_local_tick_file_count": int(len(selected)),
            "matched_local_tick_files": ";".join(str(Path(path).relative_to(REPO_DIR)) for path in selected[:8]),
            "local_tick_window_rows": int(len(combined)),
            "local_tick_schema_ready": int(bool(selected) and not combined.empty),
            "local_tick_exact_any": 0,
            "local_tick_inside_spread_any": 0,
            "nearest_tick_time": "",
            "nearest_tick_abs_seconds": np.nan,
            "nearest_tick_last_price": np.nan,
            "nearest_tick_bid1": np.nan,
            "nearest_tick_ask1": np.nan,
            "same_source_transform_verified": 0,
            "rule_candidate_allowed": 0,
            "download_csv_file_suggestion": row["download_csv_file_suggestion"],
            "selection_rule": row["selection_rule"],
        }
        if not combined.empty and np.isfinite(official_price):
            result["local_tick_exact_any"] = int(
                _price_exact_mask(combined["last_price"], official_price).any()
                or _price_exact_mask(combined["bid_price1"], official_price).any()
                or _price_exact_mask(combined["ask_price1"], official_price).any()
            )
            result["local_tick_inside_spread_any"] = int(
                ((_safe_num(combined["bid_price1"]) <= official_price) & (_safe_num(combined["ask_price1"]) >= official_price)).any()
            )
            abs_delta = (combined["tick_datetime"] - anchor_time).abs()
            nearest_idx = abs_delta.idxmin()
            nearest = combined.loc[nearest_idx]
            result["nearest_tick_time"] = pd.Timestamp(nearest["tick_datetime"]).strftime("%Y-%m-%d %H:%M:%S.%f")
            result["nearest_tick_abs_seconds"] = float(abs_delta.loc[nearest_idx].total_seconds())
            result["nearest_tick_last_price"] = _safe_float(nearest["last_price"])
            result["nearest_tick_bid1"] = _safe_float(nearest["bid_price1"])
            result["nearest_tick_ask1"] = _safe_float(nearest["ask_price1"])
        rows.append(result)
    return pd.DataFrame(rows)


def _make_download_plan(manifest_result: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "candidate_index",
        "official_open_trade_id",
        "vt_symbol",
        "tq_symbol",
        "authority_anchor_time",
        "download_start_dt",
        "download_end_dt",
        "dur_sec",
        "download_csv_file_suggestion",
    ]
    plan = manifest_result[cols].copy()
    plan["download_allowed_by_default"] = 0
    plan["download_guard"] = "requires_STAGE078_ALLOW_TQSDK_DOWNLOAD_1_manual_opt_in"
    plan["reason"] = "same-vendor tick transform smoke manifest; not downloaded in default read-only audit"
    return plan


def _official_metrics(curve: pd.DataFrame, summary077: pd.DataFrame) -> dict[str, Any]:
    curve = curve.copy()
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce")
    equity_col = "official_equity" if "official_equity" in curve.columns else "account_equity"
    drawdown_col = "official_drawdown_pct" if "official_drawdown_pct" in curve.columns else "drawdown_pct"
    daily_ret = _safe_num(curve.get("daily_return", pd.Series(np.nan, index=curve.index))).dropna()
    sharpe = np.nan
    if len(daily_ret) > 2 and daily_ret.std(ddof=1) > 0:
        sharpe = float(daily_ret.mean() / daily_ret.std(ddof=1) * np.sqrt(252))
    metrics = {
        "end_equity": float(_safe_num(curve[equity_col]).dropna().iloc[-1]),
        "total_return_pct": (float(_safe_num(curve[equity_col]).dropna().iloc[-1]) / INITIAL_CAPITAL - 1.0) * 100.0,
        "max_drawdown_pct": float(_safe_num(curve[drawdown_col]).min()),
        "sharpe": sharpe,
        "total_slippage": float(_safe_num(curve.get("total_slippage", pd.Series([np.nan]))).dropna().iloc[-1]),
        "total_trade_count": float(_safe_num(curve.get("trade_count", pd.Series(dtype=float))).sum()),
    }
    if not summary077.empty:
        row = summary077.iloc[0]
        for target, options in {
            "end_equity": ["end_equity"],
            "total_return_pct": ["total_return_pct"],
            "max_drawdown_pct": ["max_drawdown_pct", "max_dd_pct"],
            "sharpe": ["sharpe"],
            "total_slippage": ["total_slippage"],
            "total_trade_count": ["total_trade_count"],
            "closed_lot_win_rate_pct": ["closed_lot_win_rate_pct", "win_rate_pct"],
            "broker10_peak_margin_to_equity_pct": ["broker10_peak_margin_to_equity_pct"],
        }.items():
            for col in options:
                if col in summary077.columns and pd.notna(row[col]):
                    metrics[target] = _safe_float(row[col])
                    break
    return metrics


def _build_year_gate_matrix(manifest_result: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year, group in manifest_result.groupby("official_open_year"):
        rows.append(
            {
                "year": int(year),
                "manifest_rows": int(len(group)),
                "candidate_token_file_match": int((group["matched_local_tick_file_count"] > 0).sum()),
                "local_tick_schema_ready": int(group["local_tick_schema_ready"].sum()),
                "local_tick_exact_any": int(group["local_tick_exact_any"].sum()),
                "stage074_tq_ready": int(group["stage074_tq_proxy_anchor_ready"].sum()),
                "stage074_tq_exact": int(group["stage074_tq_price_exact_any"].sum()),
                "same_source_transform_verified": int(group["same_source_transform_verified"].sum()),
                "rule_candidate_allowed": int(group["rule_candidate_allowed"].sum()),
            }
        )
    return pd.DataFrame(rows)


def _plot_official_gate_chart(curve: pd.DataFrame, audit: pd.DataFrame, manifest_result: pd.DataFrame) -> None:
    curve = curve.copy()
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce")
    audit = audit.copy()
    audit["official_open_date"] = pd.to_datetime(audit["official_open_date"], errors="coerce")
    audit["realized_pnl"] = _safe_num(audit["realized_pnl"]).fillna(0.0)
    manifest_ids = set(manifest_result["candidate_index"].astype(int))
    audit["gate_bucket"] = np.select(
        [
            audit["candidate_index"].astype(int).isin(manifest_ids),
            audit["timestamp_ready"].eq(1),
            audit["timestamp_ready"].eq(0),
        ],
        ["stage078_manifest", "timestamp_ready_non_manifest", "fallback_no_proxy"],
        default="other",
    )
    contrib = (
        audit.dropna(subset=["official_open_date"])
        .groupby(["official_open_date", "gate_bucket"], as_index=False)["realized_pnl"]
        .sum()
        .sort_values("official_open_date")
    )
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=False, gridspec_kw={"height_ratios": [2.0, 1.0, 1.2]})
    ax = axes[0]
    equity_col = "official_equity" if "official_equity" in curve.columns else "account_equity"
    dd_col = "official_drawdown_pct" if "official_drawdown_pct" in curve.columns else "drawdown_pct"
    ax.plot(curve["date"], curve[equity_col], color="#1f77b4", lw=1.8, label="Official C9/15w equity")
    marker_dates = pd.to_datetime(manifest_result["official_open_date"], errors="coerce")
    for dt in marker_dates.dropna().unique():
        ax.axvline(pd.Timestamp(dt), color="#d62728", lw=0.5, alpha=0.18)
    ax.set_title("Official path unchanged; Stage078 manifest dates are data-gate anchors")
    ax.set_ylabel("Equity")
    ax.grid(alpha=0.25)
    ax.legend(loc="upper left")

    ax2 = axes[1]
    ax2.plot(curve["date"], curve[dd_col], color="#9467bd", lw=1.4)
    ax2.fill_between(curve["date"], curve[dd_col], 0, color="#9467bd", alpha=0.15)
    ax2.set_ylabel("Drawdown %")
    ax2.grid(alpha=0.25)

    ax3 = axes[2]
    for bucket, color in [
        ("stage078_manifest", "#d62728"),
        ("timestamp_ready_non_manifest", "#2ca02c"),
        ("fallback_no_proxy", "#7f7f7f"),
    ]:
        part = contrib[contrib["gate_bucket"] == bucket].copy()
        if part.empty:
            continue
        daily = part.set_index("official_open_date")["realized_pnl"].sort_index().cumsum()
        ax3.plot(daily.index, daily.values, lw=1.4, color=color, label=bucket)
    ax3.set_title("Realized PnL by data-gate bucket (distribution only, not a signal)")
    ax3.set_ylabel("Cumulative PnL")
    ax3.grid(alpha=0.25)
    ax3.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(OFFICIAL_GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_readiness_atlas(env_info: dict[str, Any], summary: dict[str, Any]) -> None:
    rows = [
        ("TqSdk import", env_info["tqsdk_import_ok"]),
        ("DataDownloader import", env_info["data_downloader_import_ok"]),
        ("datafeed username", env_info["datafeed_username_present"]),
        ("datafeed password", env_info["datafeed_password_present"]),
        ("download opt-in", env_info["download_allowed_by_env"]),
        ("manifest timestamp-ready", 1 if summary["manifest_size"] > 0 else 0),
        ("local candidate tick match", 1 if summary["manifest_local_tick_match_count"] > 0 else 0),
        ("local tick schema ready", 1 if summary["manifest_local_tick_schema_ready_count"] > 0 else 0),
        ("local tick exact any", 1 if summary["manifest_local_tick_exact_any_count"] > 0 else 0),
        ("same transform verified", 1 if summary["manifest_same_source_transform_verified_count"] > 0 else 0),
        ("rule candidate allowed", 1 if summary["rule_candidate_allowed_count"] > 0 else 0),
    ]
    labels = [row[0] for row in rows]
    values = np.array([[float(row[1])] for row in rows])
    fig, ax = plt.subplots(figsize=(9, 6))
    im = ax.imshow(values, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_yticks(np.arange(len(labels)))
    ax.set_yticklabels(labels)
    ax.set_xticks([0])
    ax.set_xticklabels(["ready"])
    for i, (_, value) in enumerate(rows):
        ax.text(0, i, str(int(value)), ha="center", va="center", color="black", fontsize=10)
    ax.set_title("Stage078 same-vendor tick transform readiness gate")
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    fig.tight_layout()
    fig.savefig(READINESS_ATLAS_OUT, dpi=160)
    plt.close(fig)


def _plot_manifest_coverage(year_gate: pd.DataFrame, manifest_result: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), gridspec_kw={"height_ratios": [1.4, 1.0]})
    ax = axes[0]
    if not year_gate.empty:
        x = np.arange(len(year_gate))
        width = 0.16
        bars = [
            ("manifest_rows", "#1f77b4"),
            ("candidate_token_file_match", "#ff7f0e"),
            ("local_tick_schema_ready", "#2ca02c"),
            ("local_tick_exact_any", "#d62728"),
            ("same_source_transform_verified", "#9467bd"),
        ]
        for idx, (col, color) in enumerate(bars):
            ax.bar(x + (idx - 2) * width, year_gate[col], width=width, label=col, color=color, alpha=0.85)
        ax.set_xticks(x)
        ax.set_xticklabels(year_gate["year"].astype(str))
        ax.set_ylabel("Count")
        ax.set_title("Manifest gate coverage by year")
        ax.grid(axis="y", alpha=0.25)
        ax.legend(fontsize=8, ncol=2)

    ax2 = axes[1]
    plot_df = manifest_result.copy()
    plot_df["stage074_delta_r"] = _safe_num(plot_df["stage074_tq_min_abs_price_delta_r"])
    colors = np.where(plot_df["local_tick_exact_any"].eq(1), "#2ca02c", "#7f7f7f")
    ax2.scatter(plot_df["candidate_index"], plot_df["stage074_delta_r"], c=colors, s=38, alpha=0.8)
    ax2.axhline(0, color="black", lw=0.8, alpha=0.4)
    ax2.set_xlabel("Candidate index")
    ax2.set_ylabel("Stage074 Tq min abs delta (R)")
    ax2.set_title("Existing Tq proxy delta remains TCA evidence until same transform is verified")
    ax2.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(MANIFEST_COVERAGE_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(summary: dict[str, Any], manifest_result: pd.DataFrame, year_gate: pd.DataFrame) -> None:
    head_cols = [
        "candidate_index",
        "vt_symbol",
        "official_open_date",
        "authority_anchor_time",
        "matched_local_tick_file_count",
        "local_tick_window_rows",
        "local_tick_exact_any",
        "same_source_transform_verified",
        "rule_candidate_allowed",
    ]
    lines = [
        "# Stage078 TqSdk dur_sec=0 tick transform gate audit",
        "",
        f"- stage: `{STAGE}`",
        f"- model_tag: `{MODEL_TAG}`",
        f"- official: `{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        f"- decision: `{summary['decision']}`",
        f"- next_step: `{summary['next_step']}`",
        "",
        "## External reference conclusion",
        "",
        "- TqSdk DataDownloader official docs state that historical downloads support tick-level data and `dur_sec=0` is Tick, but this is a Professional Edition/download-permission feature.",
        "- TqSdk market data docs show tick series includes top-of-book fields such as bid/ask price 1 and volume-like fields.",
        "- vn.py `TickData` explicitly separates last trade, orderbook snapshot, and intraday statistics from `BarData` OHLCV.",
        "- vn.py `BarGenerator.update_tick` is the canonical tick-to-minute-bar route, using tick `last_price`, cumulative volume and turnover changes.",
        "- Therefore same vendor is not enough: the gate is whether dur0 tick/orderbook can rebuild the Stage449/raw 60s price-proxy open transform at the initial-open anchors.",
        "",
        "## Summary",
        "",
        _md_table(pd.DataFrame([summary])),
        "",
        "## Manifest Head",
        "",
        _md_table(manifest_result[head_cols], max_rows=12),
        "",
        "## Year Gate Matrix",
        "",
        _md_table(year_gate),
        "",
        "## Visual Outputs",
        "",
        f"- official path gate chart: `{OFFICIAL_GATE_CHART_OUT.relative_to(REPO_DIR)}`",
        f"- readiness atlas: `{READINESS_ATLAS_OUT.relative_to(REPO_DIR)}`",
        f"- manifest coverage chart: `{MANIFEST_COVERAGE_CHART_OUT.relative_to(REPO_DIR)}`",
        "",
        "## Interpretation",
        "",
        "- This stage does not add a trading rule and does not run a true engine.",
        "- Local credentials/imports make the TqSdk dur0 route operationally plausible, but default download remains disabled and no new tick is acquired here.",
        "- Existing local tick-like files can match a subset of manifest anchors by filename, yet this only proves file/schema presence; it does not prove the same transform that produced Stage449/raw official-open anchors.",
        "- `same_source_transform_verified=0` and `rule_candidate_allowed=0` for all manifest rows.",
        "",
    ]
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage074 = _prepare_stage074(_read_csv(STAGE074_AUDIT_IN))
    curve = _read_csv(STAGE045_CURVE_IN)
    summary077 = _read_csv(STAGE077_SUMMARY_IN) if STAGE077_SUMMARY_IN.exists() else pd.DataFrame()
    env_info = _probe_tqsdk_environment()
    manifest = _select_manifest(stage074)
    local_catalog, tick_frames = _scan_local_tick_files()
    manifest_result = _analyze_manifest(manifest, tick_frames)
    download_plan = _make_download_plan(manifest_result)
    year_gate = _build_year_gate_matrix(manifest_result)
    metrics = _official_metrics(curve, summary077)

    full_tq_ready = int(stage074["tq_proxy_anchor_ready"].sum())
    full_tq_exact = int(stage074["tq_price_exact_any"].sum())
    full_tq_mismatch = int(((stage074["tq_proxy_anchor_ready"] == 1) & (stage074["tq_price_exact_any"] == 0)).sum())
    summary = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        **metrics,
        **env_info,
        "initial_open_count": int(len(stage074)),
        "timestamp_ready_count": int(stage074["timestamp_ready"].sum()),
        "fallback_no_proxy_count": int((stage074["timestamp_ready"] == 0).sum()),
        "full_existing_tq_proxy_ready_count": full_tq_ready,
        "full_existing_tq_proxy_exact_count": full_tq_exact,
        "full_existing_tq_proxy_mismatch_count": full_tq_mismatch,
        "local_tick_named_csv_count": int(len(local_catalog)),
        "local_tick_schema_file_count": int(_safe_num(local_catalog.get("has_tick_schema", pd.Series(dtype=float))).fillna(0).sum()),
        "local_tick_schema_row_count": int(_safe_num(local_catalog.get("row_count", pd.Series(dtype=float))).fillna(0).sum()),
        "manifest_size": int(len(manifest_result)),
        "manifest_local_tick_match_count": int((manifest_result["matched_local_tick_file_count"] > 0).sum()),
        "manifest_local_tick_schema_ready_count": int(manifest_result["local_tick_schema_ready"].sum()),
        "manifest_local_tick_exact_any_count": int(manifest_result["local_tick_exact_any"].sum()),
        "manifest_stage074_tq_ready_count": int(manifest_result["stage074_tq_proxy_anchor_ready"].sum()),
        "manifest_stage074_tq_exact_count": int(manifest_result["stage074_tq_price_exact_any"].sum()),
        "manifest_stage074_tq_mismatch_count": int(
            (
                (manifest_result["stage074_tq_proxy_anchor_ready"] == 1)
                & (manifest_result["stage074_tq_price_exact_any"] == 0)
            ).sum()
        ),
        "manifest_same_source_transform_verified_count": int(manifest_result["same_source_transform_verified"].sum()),
        "rule_candidate_allowed_count": int(manifest_result["rule_candidate_allowed"].sum()),
        "download_plan_rows": int(len(download_plan)),
        "download_attempted": int(env_info["download_attempted"]),
        "decision": "stage078_tq_dur0_route_environment_ready_but_transform_unverified_no_rule",
        "next_step": "manual_opt_in_download_small_dur0_manifest_then_rebuild_stage449_transform_before_any_rule",
    }
    if summary["download_allowed_by_env"]:
        summary["decision"] = "stage078_download_opt_in_detected_but_not_executed_by_readonly_gate"
        summary["next_step"] = "run_a_separate_explicit_download_stage_with_credentials_and_audited_outputs"

    _write_csv(local_catalog, LOCAL_TICK_CATALOG_OUT)
    _write_csv(manifest_result, MANIFEST_OUT)
    _write_csv(download_plan, DOWNLOAD_PLAN_OUT)
    _write_csv(year_gate, YEAR_GATE_MATRIX_OUT)
    _write_csv(pd.DataFrame([summary]), SUMMARY_OUT)
    DECISION_OUT.write_text(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2), encoding="utf-8")

    _plot_official_gate_chart(curve, stage074, manifest_result)
    _plot_readiness_atlas(env_info, summary)
    _plot_manifest_coverage(year_gate, manifest_result)
    _write_report(summary, manifest_result, year_gate)
    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
