from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage073"
MODEL_TAG = "stage073_initial_entry_raw_stage449_tq_source_integrity_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage073_c9_minrisk_initial_entry_raw_stage449_tq_source_integrity_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage073_initial_entry_raw_stage449_tq_source_integrity_audit"

STAGE045_DIR = LINE_DIR / "outputs" / "stage045_event_time_field_sync_audit"
STAGE072_DIR = LINE_DIR / "outputs" / "stage072_initial_entry_price_source_discrepancy_audit"

STAGE072_AUDIT_IN = (
    STAGE072_DIR
    / "qmt_roll_stage072_c9_minrisk_initial_entry_price_source_discrepancy_audit_source_discrepancy_audit_"
    "stage072_initial_entry_price_source_discrepancy_audit_v1.csv"
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
STAGE072_DECISION_IN = (
    STAGE072_DIR
    / "qmt_roll_stage072_c9_minrisk_initial_entry_price_source_discrepancy_audit_decision_"
    "stage072_initial_entry_price_source_discrepancy_audit_v1.json"
)
STAGE072_SUMMARY_IN = (
    STAGE072_DIR
    / "qmt_roll_stage072_c9_minrisk_initial_entry_price_source_discrepancy_audit_summary_"
    "stage072_initial_entry_price_source_discrepancy_audit_v1.csv"
)

STAGE449_FULL_MINUTE_IN = (
    EXAMPLE_DIR
    / "backtest_outputs"
    / "qmt_roll_stage449_minute_session_rebuild_full_minute_bars_stage449_minute_session_rebuild_full_v1.csv"
)
RAW_ROOTS = [
    EXAMPLE_DIR / "downloaded_futures" / "tqsdk_stage452_true_path_fallback_1455",
    EXAMPLE_DIR / "downloaded_futures" / "tqsdk_stage448_minute_session_rebuild_batch",
]

AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_integrity_audit_{MODEL_TAG}.csv"
CLASS_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_integrity_class_summary_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_source_integrity_chart_{MODEL_TAG}.png"
DELTA_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_delta_chart_{MODEL_TAG}.png"
ATLAS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_raw_stage449_tq_atlas_{MODEL_TAG}.png"

OFFICIAL_LIVE_VERSION = "official_live_stage847_c9_15w_stage819_05r_stop_retry_once"
OFFICIAL_LIVE_ALIAS = "Stage847-C9-15w"
INITIAL_CAPITAL = 150_000.0
EPS = 1e-9


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
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
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


def _contract_parts(vt_symbol: str) -> tuple[str, str]:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return symbol, exchange


def _raw_path(root: Path, vt_symbol: str) -> Path:
    symbol, exchange = _contract_parts(vt_symbol)
    return root / exchange / f"{symbol}_minute_backtest.csv"


def _target_minute(anchor_time: Any) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = pd.to_datetime(anchor_time, errors="coerce").floor("min")
    return start, start + pd.Timedelta(minutes=1)


def _load_raw_anchor_bar(vt_symbol: str, anchor_time: Any) -> dict[str, Any]:
    start, end = _target_minute(anchor_time)
    frames: list[pd.DataFrame] = []
    source_roots: list[str] = []
    for root in RAW_ROOTS:
        path = _raw_path(root, vt_symbol)
        if not path.exists():
            continue
        frame = pd.read_csv(path, encoding="utf-8-sig")
        if frame.empty or "bar_datetime" not in frame.columns:
            continue
        frame["bar_datetime"] = pd.to_datetime(frame["bar_datetime"], errors="coerce").dt.tz_localize(None)
        frame = frame[(frame["bar_datetime"] >= start) & (frame["bar_datetime"] < end)].copy()
        if frame.empty:
            continue
        frame["raw_source_root"] = root.name
        frame["raw_file_path"] = str(path)
        frames.append(frame)
        source_roots.append(root.name)
    if not frames:
        return {
            "raw_anchor_ready": 0,
            "raw_anchor_source_roots": "",
            "raw_anchor_file_path": "",
            "raw_anchor_open": np.nan,
            "raw_anchor_high": np.nan,
            "raw_anchor_low": np.nan,
            "raw_anchor_close": np.nan,
            "raw_anchor_volume": np.nan,
            "raw_anchor_open_oi": np.nan,
            "raw_anchor_close_oi": np.nan,
            "raw_anchor_degenerate_ohlc": 0,
            "raw_anchor_zero_volume": 0,
            "raw_anchor_duplicate_sources": 0,
        }
    data = pd.concat(frames, ignore_index=True)
    data = data.drop_duplicates(subset=["bar_datetime"], keep="last").sort_values("bar_datetime")
    row = data.iloc[0]
    values = {col: _safe_float(row.get(col)) for col in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]}
    degenerate = (
        np.isfinite(values["open"])
        and abs(values["open"] - values["high"]) < EPS
        and abs(values["open"] - values["low"]) < EPS
        and abs(values["open"] - values["close"]) < EPS
    )
    return {
        "raw_anchor_ready": 1,
        "raw_anchor_source_roots": ",".join(sorted(set(source_roots))),
        "raw_anchor_file_path": str(row.get("raw_file_path", "")),
        "raw_anchor_open": values["open"],
        "raw_anchor_high": values["high"],
        "raw_anchor_low": values["low"],
        "raw_anchor_close": values["close"],
        "raw_anchor_volume": values["volume"],
        "raw_anchor_open_oi": values["open_oi"],
        "raw_anchor_close_oi": values["close_oi"],
        "raw_anchor_degenerate_ohlc": int(degenerate),
        "raw_anchor_zero_volume": int(_safe_float(values["volume"], 0.0) == 0.0),
        "raw_anchor_duplicate_sources": int(len(set(source_roots)) > 1),
    }


def _load_stage449_anchor_bars(events: pd.DataFrame) -> pd.DataFrame:
    symbols = set(events["vt_symbol"].astype(str))
    windows = [
        (_target_minute(row.anchor_time)[0], _target_minute(row.anchor_time)[1])
        for row in events[["anchor_time"]].itertuples(index=False)
    ]
    min_start = min(start for start, _ in windows)
    max_end = max(end for _, end in windows)
    chunks: list[pd.DataFrame] = []
    usecols = ["vt_symbol", "bar_datetime", "open", "high", "low", "close", "volume", "open_oi", "close_oi"]
    for chunk in pd.read_csv(STAGE449_FULL_MINUTE_IN, encoding="utf-8-sig", usecols=usecols, chunksize=200_000):
        chunk = chunk[chunk["vt_symbol"].astype(str).isin(symbols)].copy()
        if chunk.empty:
            continue
        chunk["bar_datetime"] = pd.to_datetime(chunk["bar_datetime"], errors="coerce").dt.tz_localize(None)
        chunk = chunk[(chunk["bar_datetime"] >= min_start) & (chunk["bar_datetime"] < max_end)].copy()
        if not chunk.empty:
            chunks.append(chunk)
    if not chunks:
        return pd.DataFrame(columns=usecols)
    return pd.concat(chunks, ignore_index=True).sort_values(["vt_symbol", "bar_datetime"]).reset_index(drop=True)


def _stage449_anchor_dict(stage449: pd.DataFrame, vt_symbol: str, anchor_time: Any) -> dict[str, Any]:
    start, end = _target_minute(anchor_time)
    data = stage449[
        stage449["vt_symbol"].astype(str).eq(str(vt_symbol))
        & (stage449["bar_datetime"] >= start)
        & (stage449["bar_datetime"] < end)
    ].copy()
    if data.empty:
        return {
            "stage449_anchor_ready": 0,
            "stage449_anchor_open": np.nan,
            "stage449_anchor_high": np.nan,
            "stage449_anchor_low": np.nan,
            "stage449_anchor_close": np.nan,
            "stage449_anchor_volume": np.nan,
            "stage449_anchor_open_oi": np.nan,
            "stage449_anchor_close_oi": np.nan,
            "stage449_anchor_degenerate_ohlc": 0,
            "stage449_anchor_zero_volume": 0,
        }
    row = data.iloc[0]
    values = {col: _safe_float(row.get(col)) for col in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]}
    degenerate = (
        np.isfinite(values["open"])
        and abs(values["open"] - values["high"]) < EPS
        and abs(values["open"] - values["low"]) < EPS
        and abs(values["open"] - values["close"]) < EPS
    )
    return {
        "stage449_anchor_ready": 1,
        "stage449_anchor_open": values["open"],
        "stage449_anchor_high": values["high"],
        "stage449_anchor_low": values["low"],
        "stage449_anchor_close": values["close"],
        "stage449_anchor_volume": values["volume"],
        "stage449_anchor_open_oi": values["open_oi"],
        "stage449_anchor_close_oi": values["close_oi"],
        "stage449_anchor_degenerate_ohlc": int(degenerate),
        "stage449_anchor_zero_volume": int(_safe_float(values["volume"], 0.0) == 0.0),
    }


def _load_tq_target_tick(row: pd.Series) -> dict[str, Any]:
    tick_path = Path(str(row.get("tick_file_path", "")))
    start, end = _target_minute(row["anchor_time"])
    if not tick_path.exists() or tick_path.stat().st_size == 0:
        return {
            "tq_tick_ready": 0,
            "tq_tick_rows": 0,
            "tq_last_min": np.nan,
            "tq_last_max": np.nan,
            "tq_bid_min": np.nan,
            "tq_bid_max": np.nan,
            "tq_ask_min": np.nan,
            "tq_ask_max": np.nan,
            "tq_volume_min": np.nan,
            "tq_volume_max": np.nan,
            "tq_open_interest_min": np.nan,
            "tq_open_interest_max": np.nan,
            "tq_exact_official": 0,
        }
    ticks = pd.read_csv(tick_path, encoding="utf-8-sig")
    ticks["tick_datetime"] = pd.to_datetime(ticks["tick_datetime"], errors="coerce")
    target = ticks[(ticks["tick_datetime"] >= start) & (ticks["tick_datetime"] < end)].copy()
    if target.empty:
        return {
            "tq_tick_ready": 0,
            "tq_tick_rows": 0,
            "tq_last_min": np.nan,
            "tq_last_max": np.nan,
            "tq_bid_min": np.nan,
            "tq_bid_max": np.nan,
            "tq_ask_min": np.nan,
            "tq_ask_max": np.nan,
            "tq_volume_min": np.nan,
            "tq_volume_max": np.nan,
            "tq_open_interest_min": np.nan,
            "tq_open_interest_max": np.nan,
            "tq_exact_official": 0,
        }
    official = _safe_float(row["official_open_price"])
    result: dict[str, Any] = {"tq_tick_ready": 1, "tq_tick_rows": int(len(target))}
    exact = False
    for prefix, col in [
        ("last", "last_price"),
        ("bid", "bid_price1"),
        ("ask", "ask_price1"),
        ("volume", "volume"),
        ("open_interest", "open_interest"),
    ]:
        if col in target.columns:
            series = _safe_num(target[col])
            result[f"tq_{prefix}_min"] = float(series.min()) if series.notna().any() else np.nan
            result[f"tq_{prefix}_max"] = float(series.max()) if series.notna().any() else np.nan
            if prefix in {"last", "bid", "ask"}:
                exact = exact or bool((series - official).abs().lt(EPS).any())
    result["tq_exact_official"] = int(exact)
    return result


def _exact(a: Any, b: Any) -> int:
    left = _safe_float(a)
    right = _safe_float(b)
    return int(np.isfinite(left) and np.isfinite(right) and abs(left - right) < EPS)


def _diagnose(row: pd.Series) -> str:
    source_exact = (
        int(row["engine_selected_exact_official"]) == 1
        and int(row["raw_anchor_open_exact_official"]) == 1
        and int(row["stage449_anchor_open_exact_official"]) == 1
    )
    degenerate = int(row["raw_anchor_degenerate_ohlc"]) == 1 and int(row["stage449_anchor_degenerate_ohlc"]) == 1
    zero_volume = int(row["raw_anchor_zero_volume"]) == 1 and int(row["stage449_anchor_zero_volume"]) == 1
    tq_exact = int(row["tq_exact_official"]) == 1
    outside = str(row["root_cause_class"]) == "outside_target_book_range"
    if source_exact and degenerate and zero_volume and outside and not tq_exact:
        return "stage449_raw_zero_volume_open_exact_tq_book_outside"
    if source_exact and degenerate and zero_volume and not tq_exact:
        return "stage449_raw_zero_volume_open_exact_tq_no_exact"
    if source_exact and not tq_exact:
        return "stage449_raw_open_exact_tq_no_exact"
    if source_exact and tq_exact:
        return "all_sources_exact"
    return "source_integrity_unresolved"


def _build_audit() -> tuple[pd.DataFrame, dict[str, Any]]:
    stage072 = _read_csv(STAGE072_AUDIT_IN)
    with STAGE072_DECISION_IN.open("r", encoding="utf-8") as fh:
        decision = json.load(fh)
    for col in ["official_open_price", "nearest_price_value", "min_abs_price_delta_r", "realized_pnl", "raw_price"]:
        if col in stage072.columns:
            stage072[col] = _safe_num(stage072[col])
    for col in ["engine_selected_price", "engine_selected_exact_official", "seed_price", "seed_exact_official"]:
        if col in stage072.columns:
            stage072[col] = _safe_num(stage072[col])
    stage072["anchor_time"] = pd.to_datetime(stage072["anchor_time"], errors="coerce")
    stage449 = _load_stage449_anchor_bars(stage072)

    rows: list[dict[str, Any]] = []
    for _, row in stage072.iterrows():
        item = row.to_dict()
        item.update(_load_raw_anchor_bar(str(row["vt_symbol"]), row["anchor_time"]))
        item.update(_stage449_anchor_dict(stage449, str(row["vt_symbol"]), row["anchor_time"]))
        item.update(_load_tq_target_tick(row))
        official = item["official_open_price"]
        item["engine_selected_exact_official"] = int(_safe_float(item.get("engine_selected_exact_official"), 0.0) == 1.0)
        item["seed_exact_official"] = int(_safe_float(item.get("seed_exact_official"), 0.0) == 1.0)
        item["raw_anchor_open_exact_official"] = _exact(item["raw_anchor_open"], official)
        item["stage449_anchor_open_exact_official"] = _exact(item["stage449_anchor_open"], official)
        item["raw_stage449_open_exact"] = _exact(item["raw_anchor_open"], item["stage449_anchor_open"])
        item["engine_selected_raw_open_exact"] = _exact(item.get("engine_selected_price"), item["raw_anchor_open"])
        item["raw_anchor_open_minus_tq_nearest"] = _safe_float(item["raw_anchor_open"]) - _safe_float(item["nearest_price_value"])
        existing_abs_r = _safe_float(item.get("raw_minus_tq_nearest_abs_r"), np.nan)
        if np.isfinite(existing_abs_r):
            item["raw_anchor_open_minus_tq_nearest_abs_r"] = existing_abs_r
        else:
            risk = _safe_float(item.get("risk_price"), np.nan)
            if not np.isfinite(risk) or risk == 0:
                risk = np.nan
            item["raw_anchor_open_minus_tq_nearest_abs_r"] = abs(item["raw_anchor_open_minus_tq_nearest"]) / risk
        item["source_integrity_class"] = _diagnose(pd.Series(item))
        rows.append(item)

    ordered = [
        "event_key",
        "official_open_trade_id",
        "candidate_index",
        "vt_symbol",
        "direction",
        "anchor_time",
        "official_open_price",
        "root_cause_class",
        "source_integrity_class",
        "engine_proxy_kind",
        "engine_selected_source",
        "engine_selected_price",
        "engine_selected_exact_official",
        "seed_source",
        "seed_price",
        "seed_exact_official",
        "raw_anchor_open",
        "raw_anchor_high",
        "raw_anchor_low",
        "raw_anchor_close",
        "raw_anchor_volume",
        "raw_anchor_open_oi",
        "raw_anchor_close_oi",
        "raw_anchor_degenerate_ohlc",
        "raw_anchor_zero_volume",
        "raw_anchor_source_roots",
        "raw_anchor_open_exact_official",
        "stage449_anchor_open",
        "stage449_anchor_high",
        "stage449_anchor_low",
        "stage449_anchor_close",
        "stage449_anchor_volume",
        "stage449_anchor_degenerate_ohlc",
        "stage449_anchor_zero_volume",
        "stage449_anchor_open_exact_official",
        "raw_stage449_open_exact",
        "engine_selected_raw_open_exact",
        "nearest_price_value",
        "min_abs_price_delta_r",
        "raw_anchor_open_minus_tq_nearest",
        "raw_anchor_open_minus_tq_nearest_abs_r",
        "tq_tick_ready",
        "tq_tick_rows",
        "tq_exact_official",
        "tq_last_min",
        "tq_last_max",
        "tq_bid_min",
        "tq_bid_max",
        "tq_ask_min",
        "tq_ask_max",
        "tq_volume_min",
        "tq_volume_max",
        "tq_open_interest_min",
        "tq_open_interest_max",
        "realized_pnl",
        "tick_file_path",
    ]
    audit = pd.DataFrame(rows)
    return audit[[col for col in ordered if col in audit.columns]].sort_values(["anchor_time", "event_key"]).reset_index(drop=True), decision


def _class_summary(audit: pd.DataFrame) -> pd.DataFrame:
    if audit.empty:
        return pd.DataFrame()
    return (
        audit.groupby(["source_integrity_class", "root_cause_class"], dropna=False)
        .agg(
            event_count=("event_key", "size"),
            engine_selected_exact_count=("engine_selected_exact_official", "sum"),
            seed_exact_count=("seed_exact_official", "sum"),
            raw_exact_count=("raw_anchor_open_exact_official", "sum"),
            stage449_exact_count=("stage449_anchor_open_exact_official", "sum"),
            raw_stage449_exact_count=("raw_stage449_open_exact", "sum"),
            tq_exact_count=("tq_exact_official", "sum"),
            raw_zero_volume_count=("raw_anchor_zero_volume", "sum"),
            raw_degenerate_ohlc_count=("raw_anchor_degenerate_ohlc", "sum"),
            stage449_zero_volume_count=("stage449_anchor_zero_volume", "sum"),
            stage449_degenerate_ohlc_count=("stage449_anchor_degenerate_ohlc", "sum"),
            net_realized_pnl=("realized_pnl", "sum"),
            median_abs_delta_r=("min_abs_price_delta_r", "median"),
            max_abs_delta_r=("min_abs_price_delta_r", "max"),
        )
        .reset_index()
        .sort_values(["event_count", "source_integrity_class"], ascending=[False, True])
    )


def _curve_metrics(curve: pd.DataFrame) -> dict[str, float]:
    equity = pd.to_numeric(curve["official_equity"], errors="coerce").dropna()
    drawdown = pd.to_numeric(curve["official_drawdown_pct"], errors="coerce").dropna()
    return {
        "end_equity": float(equity.iloc[-1]) if not equity.empty else np.nan,
        "total_return_pct": float((equity.iloc[-1] / INITIAL_CAPITAL - 1.0) * 100.0) if not equity.empty else np.nan,
        "max_drawdown_pct": float(drawdown.min()) if not drawdown.empty else np.nan,
    }


def _official_metrics_from_stage072_summary() -> dict[str, float]:
    if not STAGE072_SUMMARY_IN.exists():
        return {}
    data = pd.read_csv(STAGE072_SUMMARY_IN, encoding="utf-8-sig")
    if data.empty:
        return {}
    row = data.iloc[0]
    metrics: dict[str, float] = {}
    for col in [
        "end_equity",
        "total_return_pct",
        "max_drawdown_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
    ]:
        value = _safe_float(row.get(col), np.nan)
        if np.isfinite(value):
            metrics[col] = value
    return metrics


def _official_metrics_from_stage045_summary() -> dict[str, float]:
    if not STAGE045_SUMMARY_IN.exists():
        return {}
    data = pd.read_csv(STAGE045_SUMMARY_IN, encoding="utf-8-sig")
    if data.empty:
        return {}
    row = data.iloc[0]
    metrics: dict[str, float] = {}
    for col in [
        "end_equity",
        "total_return_pct",
        "max_drawdown_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "closed_lot_win_rate_pct",
        "max_broker10_margin_to_equity_pct",
    ]:
        value = _safe_float(row.get(col), np.nan)
        if np.isfinite(value):
            metrics[col] = value
    return metrics


def _plot_path_chart(curve: pd.DataFrame, audit: pd.DataFrame) -> None:
    data = curve.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    plot = audit.copy()
    plot["anchor_date"] = pd.to_datetime(plot["anchor_time"], errors="coerce").dt.normalize()
    equity_by_date = data.set_index(data["date"].dt.normalize())["official_equity"]
    plot["anchor_equity"] = plot["anchor_date"].map(equity_by_date)
    colors = {
        "stage449_raw_zero_volume_open_exact_tq_book_outside": "#d55e00",
        "stage449_raw_zero_volume_open_exact_tq_no_exact": "#0072b2",
        "source_integrity_unresolved": "#6b7280",
    }
    fig, axes = plt.subplots(2, 1, figsize=(16, 9), sharex=False)
    axes[0].plot(data["date"], data["official_equity"] / 1_000_000, color="#1f77b4", linewidth=1.8)
    for klass, group in plot.groupby("source_integrity_class"):
        axes[0].scatter(group["anchor_date"], group["anchor_equity"] / 1_000_000, s=52, alpha=0.85, color=colors.get(klass, "#009e73"), label=klass)
    axes[0].set_title("Stage073 official path with source-integrity classes")
    axes[0].set_ylabel("Equity (million CNY)")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="upper left", fontsize=8)

    cumulative = []
    for klass, group in plot.sort_values("anchor_time").groupby("source_integrity_class"):
        item = group[["anchor_time", "realized_pnl"]].copy()
        item["cum_pnl"] = item["realized_pnl"].cumsum()
        item["source_integrity_class"] = klass
        cumulative.append(item)
    if cumulative:
        combined = pd.concat(cumulative, ignore_index=True)
        for klass, group in combined.groupby("source_integrity_class"):
            axes[1].plot(group["anchor_time"], group["cum_pnl"] / 10_000, marker="o", linewidth=1.6, color=colors.get(klass, "#009e73"), label=klass)
    axes[1].axhline(0, color="black", linewidth=0.8)
    axes[1].set_title("Cumulative PnL by source-integrity class")
    axes[1].set_ylabel("Cumulative PnL (10k CNY)")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_delta_chart(audit: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(16, 5.5))
    colors = {
        "stage449_raw_zero_volume_open_exact_tq_book_outside": "#d55e00",
        "stage449_raw_zero_volume_open_exact_tq_no_exact": "#0072b2",
        "source_integrity_unresolved": "#6b7280",
    }
    for klass, group in audit.groupby("source_integrity_class"):
        axes[0].scatter(
            pd.to_datetime(group["anchor_time"], errors="coerce"),
            pd.to_numeric(group["raw_anchor_open_minus_tq_nearest_abs_r"], errors="coerce"),
            s=70,
            alpha=0.8,
            color=colors.get(klass, "#009e73"),
            label=klass,
        )
    axes[0].axhline(0.05, color="black", linestyle="--", linewidth=1.0, label="0.05R")
    axes[0].set_title("Stage449/raw open vs nearest Tq tick top-book")
    axes[0].set_ylabel("|raw open - nearest Tq field| / R")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="best", fontsize=8)

    counts = {
        "engine exact": int(audit["engine_selected_exact_official"].sum()),
        "seed exact": int(audit["seed_exact_official"].sum()),
        "raw exact": int(audit["raw_anchor_open_exact_official"].sum()),
        "Stage449 exact": int(audit["stage449_anchor_open_exact_official"].sum()),
        "raw zero vol": int(audit["raw_anchor_zero_volume"].sum()),
        "raw degenerate": int(audit["raw_anchor_degenerate_ohlc"].sum()),
        "Tq exact": int(audit["tq_exact_official"].sum()),
    }
    axes[1].barh(list(counts.keys()), list(counts.values()), color=["#009e73", "#009e73", "#009e73", "#d55e00", "#d55e00", "#cc79a7"])
    axes[1].set_xlim(0, max(14, max(counts.values()) + 1))
    axes[1].set_title("Source integrity checks across Stage072 mismatches")
    axes[1].grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(DELTA_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_atlas(audit: pd.DataFrame) -> None:
    rows = audit.sort_values(["source_integrity_class", "anchor_time"]).reset_index(drop=True)
    n = len(rows)
    fig, axes = plt.subplots(n, 1, figsize=(15, max(2.1 * n, 8)), sharex=False)
    if n == 1:
        axes = [axes]
    for ax, (_, row) in zip(axes, rows.iterrows()):
        tick_path = Path(str(row.get("tick_file_path", "")))
        target = pd.DataFrame()
        start, end = _target_minute(row["anchor_time"])
        if tick_path.exists() and tick_path.stat().st_size > 0:
            ticks = pd.read_csv(tick_path, encoding="utf-8-sig")
            ticks["tick_datetime"] = pd.to_datetime(ticks["tick_datetime"], errors="coerce")
            target = ticks[(ticks["tick_datetime"] >= start) & (ticks["tick_datetime"] < end)].copy()
        if not target.empty:
            for col, color, label in [
                ("last_price", "#1f77b4", "Tq last"),
                ("ask_price1", "#ff7f0e", "Tq ask1"),
                ("bid_price1", "#2ca02c", "Tq bid1"),
            ]:
                if col in target.columns:
                    target[col] = pd.to_numeric(target[col], errors="coerce")
                    ax.plot(target["tick_datetime"], target[col], color=color, linewidth=0.9, label=label)
        official = _safe_float(row["official_open_price"])
        raw_open = _safe_float(row["raw_anchor_open"])
        stage449_open = _safe_float(row["stage449_anchor_open"])
        ax.axhline(official, color="black", linestyle="--", linewidth=1.0, label="official open")
        if np.isfinite(raw_open):
            ax.axhline(raw_open, color="#cc79a7", linestyle=":", linewidth=1.0, label="raw/Stage449 open")
        if np.isfinite(stage449_open) and abs(stage449_open - raw_open) > EPS:
            ax.axhline(stage449_open, color="#9467bd", linestyle=":", linewidth=1.0, label="Stage449 open")
        ax.set_title(
            f"{row['official_open_trade_id']} {row['vt_symbol']} {pd.to_datetime(row['anchor_time']).strftime('%Y-%m-%d %H:%M')} "
            f"{row['source_integrity_class']} vol={_safe_float(row['raw_anchor_volume'], np.nan):g} deltaR={_safe_float(row['min_abs_price_delta_r']):.3f}",
            fontsize=8.5,
        )
        ax.grid(True, alpha=0.25)
        ax.legend(loc="upper left", fontsize=7)
    fig.tight_layout()
    fig.savefig(ATLAS_OUT, dpi=150)
    plt.close(fig)


def _write_report(audit: pd.DataFrame, class_summary: pd.DataFrame, summary: pd.DataFrame) -> None:
    row = summary.iloc[0]
    lines = [
        "# Stage073 raw/Stage449/Tq 源完整性审计",
        "",
        "## 结论",
        "",
        f"- 决策：`{row['decision']}`。",
        f"- 当前正式版：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`。",
        f"- mismatch 样本：`{int(row['mismatch_count'])}`；engine selected exact：`{int(row['engine_selected_exact_count'])}`；raw exact：`{int(row['raw_exact_count'])}`；Stage449 exact：`{int(row['stage449_exact_count'])}`；Tq exact：`{int(row['tq_exact_count'])}`。",
        f"- raw zero-volume：`{int(row['raw_zero_volume_count'])}`；raw degenerate OHLC：`{int(row['raw_degenerate_ohlc_count'])}`。",
        "- 本阶段不新增交易规则、不跑 true engine、不触发 A/B；只解释同一 anchor minute 下 raw/Stage449 与 Tq tick 的源差异。",
        "",
        "## 官方基准",
        "",
        f"- 期末权益：`{row['end_equity']}`",
        f"- 总收益：`{row['total_return_pct']}`",
        f"- 最大回撤：`{row['max_drawdown_pct']}`",
        f"- Sharpe：`{row['sharpe']}`",
        f"- 总滑点：`{row['total_slippage']}`",
        f"- 总交易次数：`{row['total_trade_count']}`",
        f"- 胜率：`{row['closed_lot_win_rate_pct']}`",
        f"- broker10 峰值：`{row['max_broker10_margin_to_equity_pct']}`",
        "",
        "## 源完整性分类",
        "",
        _md_table(class_summary),
        "",
        "## 样本明细",
        "",
        _md_table(
            audit[
                [
                    "official_open_trade_id",
                    "vt_symbol",
                    "anchor_time",
                    "official_open_price",
                    "engine_selected_price",
                    "engine_selected_source",
                    "raw_anchor_open",
                    "stage449_anchor_open",
                    "raw_anchor_volume",
                    "nearest_price_value",
                    "source_integrity_class",
                    "root_cause_class",
                    "realized_pnl",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## 视觉文件",
        "",
        f"- path/source integrity chart：`{PATH_CHART_OUT}`",
        f"- source delta chart：`{DELTA_CHART_OUT}`",
        f"- raw/Stage449/Tq atlas：`{ATLAS_OUT}`",
        "",
        "## 判断",
        "",
        "- Stage073 把 Stage072 的矛盾进一步收敛：engine selected price、raw minute anchor open、Stage449 full minute anchor open 全部精确等于 official open。",
        "- 但这些 raw/Stage449 anchor bar 全部是 `volume=0` 且 open/high/low/close 全等的退化分钟条；Tq tick top-book 在同一分钟没有 exact official open。",
        "- 因此 official open 当前更像 Stage449/Stage149 的分钟 open proxy 口径，而不是 Tq tick top-book 可成交价。这个差异不能作为高质量/低质量信号。",
        "- 下一步如果继续盘口路线，必须先决定正式研究价格源：要么回到 Stage449/Stage861 分钟 open 口径只做 bar-level 执行审计；要么取得与 official open 同源的 tick/order-book；不能用异源 Tq tick 直接提 spread/depth/imbalance 规则。",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    audit, stage072_decision = _build_audit()
    class_summary = _class_summary(audit)
    curve = _read_csv(STAGE045_CURVE_IN)
    metrics = _curve_metrics(curve)
    official_metrics = _official_metrics_from_stage045_summary()
    official_metrics.update(_official_metrics_from_stage072_summary())
    official_metrics.update(stage072_decision.get("official_metrics", {}))

    mismatch_count = int(len(audit))
    engine_selected_exact = int(audit["engine_selected_exact_official"].sum())
    seed_exact = int(audit["seed_exact_official"].sum())
    raw_exact = int(audit["raw_anchor_open_exact_official"].sum())
    stage449_exact = int(audit["stage449_anchor_open_exact_official"].sum())
    tq_exact = int(audit["tq_exact_official"].sum())
    raw_zero = int(audit["raw_anchor_zero_volume"].sum())
    raw_degenerate = int(audit["raw_anchor_degenerate_ohlc"].sum())
    stage449_zero = int(audit["stage449_anchor_zero_volume"].sum())
    stage449_degenerate = int(audit["stage449_anchor_degenerate_ohlc"].sum())

    if (
        engine_selected_exact == mismatch_count
        and raw_exact == mismatch_count
        and stage449_exact == mismatch_count
        and tq_exact == 0
        and raw_zero == mismatch_count
        and raw_degenerate == mismatch_count
    ):
        stage_decision = "stage073_stage449_zero_volume_open_proxy_vs_tq_tick_source_mismatch_no_rule"
    elif engine_selected_exact == mismatch_count and raw_exact == mismatch_count and tq_exact == 0:
        stage_decision = "stage073_stage449_raw_open_proxy_vs_tq_tick_source_mismatch_no_rule"
    else:
        stage_decision = "stage073_source_integrity_still_unresolved_no_rule"

    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "decision": stage_decision,
                "mismatch_count": mismatch_count,
                "engine_selected_exact_count": engine_selected_exact,
                "seed_exact_count": seed_exact,
                "raw_exact_count": raw_exact,
                "stage449_exact_count": stage449_exact,
                "tq_exact_count": tq_exact,
                "raw_zero_volume_count": raw_zero,
                "raw_degenerate_ohlc_count": raw_degenerate,
                "stage449_zero_volume_count": stage449_zero,
                "stage449_degenerate_ohlc_count": stage449_degenerate,
                "outside_book_count": int(audit["root_cause_class"].eq("outside_target_book_range").sum()),
                "end_equity": official_metrics.get("end_equity", metrics["end_equity"]),
                "total_return_pct": official_metrics.get("total_return_pct", metrics["total_return_pct"]),
                "max_drawdown_pct": official_metrics.get("max_drawdown_pct", metrics["max_drawdown_pct"]),
                "sharpe": official_metrics.get("sharpe", np.nan),
                "total_slippage": official_metrics.get("total_slippage", np.nan),
                "total_trade_count": official_metrics.get("total_trade_count", np.nan),
                "closed_lot_win_rate_pct": official_metrics.get("closed_lot_win_rate_pct", np.nan),
                "max_broker10_margin_to_equity_pct": official_metrics.get("max_broker10_margin_to_equity_pct", np.nan),
                "strategy_rule_created": False,
                "true_engine_run": False,
                "ab_triggered": False,
            }
        ]
    )

    _write_csv(audit, AUDIT_OUT)
    _write_csv(class_summary, CLASS_SUMMARY_OUT)
    _write_csv(summary, SUMMARY_OUT)
    _plot_path_chart(curve, audit)
    _plot_delta_chart(audit)
    _plot_atlas(audit)
    _write_report(audit, class_summary, summary)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": stage_decision,
        "next_step": "choose_single_authoritative_execution_data_source_before_initial_entry_tca_or_rules",
        "strategy_rule_created": False,
        "true_engine_run": False,
        "ab_triggered": False,
        "mismatch_count": mismatch_count,
        "engine_selected_exact_count": engine_selected_exact,
        "seed_exact_count": seed_exact,
        "raw_exact_count": raw_exact,
        "stage449_exact_count": stage449_exact,
        "tq_exact_count": tq_exact,
        "raw_zero_volume_count": raw_zero,
        "raw_degenerate_ohlc_count": raw_degenerate,
        "outputs": {
            "audit": AUDIT_OUT,
            "class_summary": CLASS_SUMMARY_OUT,
            "summary": SUMMARY_OUT,
            "report": REPORT_OUT,
            "path_chart": PATH_CHART_OUT,
            "delta_chart": DELTA_CHART_OUT,
            "atlas": ATLAS_OUT,
        },
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
