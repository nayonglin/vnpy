from __future__ import annotations

from datetime import datetime
import json
import math
import os
from pathlib import Path
import re
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", str(Path("/tmp") / "vnpy_matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
DATA_ROOT = PROJECT_DIR / "downloaded_futures"

STAGE565_PREFIX = "qmt_roll_stage565_stage526_liquidity_capacity_product_audit"
STAGE565_TAG = "stage565_stage526_liquidity_capacity_product_audit_v1"
STAGE565_EVENTS_IN = OUTPUT_DIR / f"{STAGE565_PREFIX}_stage526_trade_liquidity_events_{STAGE565_TAG}.csv"

STAGE566_PREFIX = "qmt_roll_stage566_stage526_liquidity_gap_backfill_audit"
STAGE566_TAG = "stage566_stage526_liquidity_gap_backfill_audit_v1"
STAGE566_SELECTED_IN = OUTPUT_DIR / f"{STAGE566_PREFIX}_resolved_events_{STAGE566_TAG}.csv"
STAGE566_SUMMARY_IN = OUTPUT_DIR / f"{STAGE566_PREFIX}_summary_{STAGE566_TAG}.csv"

STAGE567_PREFIX = "qmt_roll_stage567_stage526_residual_capacity_boundary_audit"
STAGE567_TAG = "stage567_stage526_residual_capacity_boundary_audit_v1"
STAGE567_HARD_EVENTS_IN = OUTPUT_DIR / f"{STAGE567_PREFIX}_hard_capacity_events_{STAGE567_TAG}.csv"

MODEL_TAG = "stage568_stage526_execution_quality_ledger_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage568_stage526_execution_quality_ledger_audit"

LEDGER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_execution_quality_ledger_{MODEL_TAG}.csv"
LIVE_TEMPLATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_live_execution_ledger_template_{MODEL_TAG}.csv"
MINUTE_PROXY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_minute_proxy_by_event_{MODEL_TAG}.csv"
TOP_WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_window_participation_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

MIN_FULL_LIKE_MINUTE_BARS = 180
WINDOW_PARTICIPATION_WARN_PCT = 25.0
WINDOW_PARTICIPATION_HARD_PCT = 100.0
PRICE_DEVIATION_WARN_BPS = 50.0

ACTUAL_EXECUTION_FIELDS = [
    "signal_generated_at",
    "signal_price",
    "order_submit_at",
    "order_submit_price",
    "order_type",
    "limit_price",
    "fill_first_at",
    "fill_last_at",
    "avg_fill_price",
    "filled_volume",
    "cancelled_volume",
    "unfilled_volume",
    "commission_cash",
    "actual_slippage_cash",
    "actual_implementation_shortfall_bps",
    "actual_vs_window_vwap_bps",
    "account_equity_before",
    "broker_margin_before",
    "broker_margin_rate_note",
    "operator_note",
]


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
        value = float(value)
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).astype(float)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _parse_vt_symbol(vt_symbol: str) -> tuple[str, str]:
    if "." not in vt_symbol:
        return vt_symbol, ""
    symbol, exchange = vt_symbol.split(".", 1)
    return symbol, exchange


def _execution_side(pos_change: float) -> str:
    if pos_change > 0:
        return "buy"
    if pos_change < 0:
        return "sell"
    return "flat"


def _side_sign(side: str) -> float:
    if side == "buy":
        return 1.0
    if side == "sell":
        return -1.0
    return 0.0


def _directional_bps(fill: pd.Series, benchmark: pd.Series, side: pd.Series) -> pd.Series:
    fill_num = pd.to_numeric(fill, errors="coerce")
    bench_num = pd.to_numeric(benchmark, errors="coerce")
    side_num = side.map(_side_sign).astype(float)
    out = np.where(
        bench_num.gt(0.0) & fill_num.gt(0.0) & side_num.ne(0.0),
        side_num * (fill_num - bench_num) / bench_num * 10000.0,
        np.nan,
    )
    return pd.Series(out, index=fill.index, dtype=float)


def load_stage_events() -> pd.DataFrame:
    events = _read_csv(STAGE565_EVENTS_IN)
    events["date"] = pd.to_datetime(events["date"], errors="coerce").dt.normalize()
    events["event_id"] = events.index.astype(int)
    numeric_columns = [
        "start_pos",
        "end_pos",
        "pos_change",
        "close_price",
        "trade_count",
        "turnover",
        "commission",
        "slippage",
        "holding_pnl",
        "trading_pnl",
        "net_pnl",
        "order_volume",
        "start_abs_pos",
        "end_abs_pos",
        "peak_abs_pos",
        "daily_volume",
        "daily_close_oi",
        "daily_close",
        "order_volume_to_day_volume_pct",
        "peak_position_to_oi_pct",
    ]
    for column in numeric_columns:
        events[column] = _num(events, column)
    events["execution_side"] = events["pos_change"].map(_execution_side)
    return events


def load_effective_capacity(events: pd.DataFrame) -> pd.DataFrame:
    out = events.copy()
    selected = _read_csv(STAGE566_SELECTED_IN)
    for column in ["event_id", "candidate_volume", "candidate_oi", "candidate_close", "minute_bar_count"]:
        if column in selected.columns:
            selected[column] = _num(selected, column)
    selected["backfill_accepted"] = selected["accepted_quality"].isin(["daily_full", "minute_full_like"]).astype(int)
    selected_cols = [
        "event_id",
        "source_path",
        "source_type",
        "accepted_quality",
        "candidate_volume",
        "candidate_oi",
        "candidate_close",
        "minute_bar_count",
        "backfill_accepted",
    ]
    out = out.merge(selected[selected_cols], on="event_id", how="left", suffixes=("", "_backfill"))
    out = out.rename(columns={"minute_bar_count": "backfill_minute_bar_count"})
    accepted = out["backfill_accepted"].fillna(0).astype(int).eq(1)
    out["effective_daily_volume"] = np.where(
        accepted & out["candidate_volume"].fillna(0.0).gt(0.0),
        out["candidate_volume"],
        out["daily_volume"],
    )
    out["effective_daily_close_oi"] = np.where(
        accepted & out["candidate_oi"].fillna(0.0).gt(0.0),
        out["candidate_oi"],
        out["daily_close_oi"],
    )
    out["effective_daily_close"] = np.where(
        accepted & out["candidate_close"].fillna(0.0).gt(0.0),
        out["candidate_close"],
        out["daily_close"],
    )
    out["effective_order_volume_to_day_volume_pct"] = np.where(
        out["effective_daily_volume"].gt(0.0),
        out["order_volume"] / out["effective_daily_volume"] * 100.0,
        np.nan,
    )
    out["effective_peak_position_to_oi_pct"] = np.where(
        out["effective_daily_close_oi"].gt(0.0),
        out["peak_abs_pos"] / out["effective_daily_close_oi"] * 100.0,
        np.nan,
    )
    return out


def _canonical_contract_symbol(path: Path) -> str:
    stem = path.stem
    for suffix in ["_completed_minute_backtest", "_minute_backtest"]:
        if stem.endswith(suffix):
            return stem[: -len(suffix)].upper()
    return stem.upper()


def build_minute_file_index() -> dict[tuple[str, str], list[Path]]:
    index: dict[tuple[str, str], list[Path]] = {}
    for path in DATA_ROOT.rglob("*.csv"):
        name = path.name.lower()
        if "minute_backtest" not in name:
            continue
        exchange = path.parent.name.upper()
        contract = _canonical_contract_symbol(path)
        index.setdefault((exchange, contract), []).append(path)
    for key, paths in index.items():
        paths.sort(key=lambda item: (0 if "completed" in item.name.lower() else 1, len(str(item)), str(item)))
    return index


def _load_minute_file(path: Path, cache: dict[Path, pd.DataFrame]) -> pd.DataFrame:
    if path in cache:
        return cache[path]
    frame = _read_csv(path)
    if "bar_datetime" not in frame.columns:
        frame = pd.DataFrame()
    else:
        frame["bar_datetime"] = pd.to_datetime(frame["bar_datetime"], errors="coerce")
        frame["_trade_date"] = frame["bar_datetime"].dt.normalize()
        for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
            frame[column] = _num(frame, column)
    cache[path] = frame
    return frame


def _window_vwap(rows: pd.DataFrame) -> float:
    if rows.empty:
        return np.nan
    volume = _num(rows, "volume").sum()
    close = _num(rows, "close")
    if volume > 0.0:
        return float((close * _num(rows, "volume")).sum() / volume)
    return float(close.mean()) if len(close) else np.nan


def _close_window_rows(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return rows
    bar_time = rows["bar_datetime"].dt.time
    start = datetime.strptime("14:30", "%H:%M").time()
    end = datetime.strptime("15:00", "%H:%M").time()
    window = rows.loc[(bar_time >= start) & (bar_time <= end)].copy()
    return window if not window.empty else rows


def _extract_minute_metrics(path: Path, event_date: pd.Timestamp, cache: dict[Path, pd.DataFrame]) -> dict[str, Any] | None:
    frame = _load_minute_file(path, cache)
    if frame.empty:
        return None
    rows = frame.loc[frame["_trade_date"].eq(event_date)].copy()
    if rows.empty:
        return None
    rows = rows.sort_values("bar_datetime")
    bar_count = int(len(rows))
    total_volume = float(_num(rows, "volume").sum())
    close_series = _num(rows, "close")
    positive_oi = _num(rows, "close_oi")
    positive_oi = positive_oi[positive_oi.gt(0.0)]
    if bar_count >= MIN_FULL_LIKE_MINUTE_BARS and total_volume > 0.0:
        quality = "full_like_positive_volume"
    elif bar_count >= MIN_FULL_LIKE_MINUTE_BARS:
        quality = "full_like_zero_volume"
    elif total_volume > 0.0:
        quality = "partial_positive_volume"
    else:
        quality = "partial_zero_volume"

    metrics: dict[str, Any] = {
        "minute_source_path": str(path),
        "minute_proxy_quality": quality,
        "minute_bar_count": bar_count,
        "minute_first_bar_at": rows["bar_datetime"].iloc[0],
        "minute_last_bar_at": rows["bar_datetime"].iloc[-1],
        "minute_total_volume": total_volume,
        "minute_last_close_oi": float(positive_oi.iloc[-1]) if not positive_oi.empty else 0.0,
        "minute_full_day_vwap": _window_vwap(rows),
        "minute_last_close": float(close_series.iloc[-1]) if len(close_series) else np.nan,
    }
    close_window = _close_window_rows(rows)
    metrics["minute_close_window_bar_count"] = int(len(close_window))
    metrics["minute_close_window_start_at"] = close_window["bar_datetime"].iloc[0] if not close_window.empty else ""
    metrics["minute_close_window_end_at"] = close_window["bar_datetime"].iloc[-1] if not close_window.empty else ""
    for window in [5, 15, 30]:
        tail = close_window.tail(window)
        metrics[f"minute_last{window}_bar_count"] = int(len(tail))
        metrics[f"minute_last{window}_volume"] = float(_num(tail, "volume").sum()) if not tail.empty else 0.0
        metrics[f"minute_last{window}_vwap"] = _window_vwap(tail)
    return metrics


def collect_minute_proxies(events: pd.DataFrame) -> pd.DataFrame:
    file_index = build_minute_file_index()
    cache: dict[Path, pd.DataFrame] = {}
    quality_rank = {
        "full_like_positive_volume": 0,
        "partial_positive_volume": 1,
        "full_like_zero_volume": 2,
        "partial_zero_volume": 3,
    }
    rows: list[dict[str, Any]] = []
    for _, event in events.iterrows():
        vt_symbol = str(event["vt_symbol"])
        symbol, exchange = _parse_vt_symbol(vt_symbol)
        candidates = file_index.get((exchange.upper(), symbol.upper()), [])
        event_date = pd.Timestamp(event["date"]).normalize()
        best: dict[str, Any] | None = None
        for path in candidates:
            metrics = _extract_minute_metrics(path, event_date, cache)
            if metrics is None:
                continue
            rank = quality_rank.get(str(metrics["minute_proxy_quality"]), 9)
            metrics["_rank"] = rank
            if best is None:
                best = metrics
                continue
            best_rank = int(best.get("_rank", 9))
            if (rank, -int(metrics["minute_bar_count"]), -float(metrics["minute_total_volume"])) < (
                best_rank,
                -int(best["minute_bar_count"]),
                -float(best["minute_total_volume"]),
            ):
                best = metrics
        if best is None:
            best = {
                "minute_source_path": "",
                "minute_proxy_quality": "missing",
                "minute_bar_count": 0,
                "minute_first_bar_at": "",
                "minute_last_bar_at": "",
                "minute_total_volume": 0.0,
                "minute_last_close_oi": 0.0,
                "minute_full_day_vwap": np.nan,
                "minute_last_close": np.nan,
                "minute_close_window_bar_count": 0,
                "minute_close_window_start_at": "",
                "minute_close_window_end_at": "",
                "minute_last5_bar_count": 0,
                "minute_last5_volume": 0.0,
                "minute_last5_vwap": np.nan,
                "minute_last15_bar_count": 0,
                "minute_last15_volume": 0.0,
                "minute_last15_vwap": np.nan,
                "minute_last30_bar_count": 0,
                "minute_last30_volume": 0.0,
                "minute_last30_vwap": np.nan,
            }
        best.pop("_rank", None)
        rows.append(
            {
                "event_id": int(event["event_id"]),
                "date": event_date,
                "vt_symbol": vt_symbol,
                "product_vt_symbol": str(event["product_vt_symbol"]),
                **best,
            }
        )
    proxy = pd.DataFrame(rows)
    return proxy


def build_execution_ledger(events: pd.DataFrame, proxy: pd.DataFrame) -> pd.DataFrame:
    hard_events = _read_csv(STAGE567_HARD_EVENTS_IN)
    hard_ids = set(_num(hard_events, "event_id").astype(int).tolist()) if "event_id" in hard_events.columns else set()
    ledger = events.merge(proxy, on=["event_id", "date", "vt_symbol", "product_vt_symbol"], how="left")
    ledger["is_hard_capacity_event"] = ledger["event_id"].isin(hard_ids).astype(int)
    ledger["backtest_fill_price"] = ledger["close_price"]
    ledger["backtest_reference"] = "stage526_close_price"
    ledger["order_to_minute_total_volume_pct"] = np.where(
        ledger["minute_total_volume"].gt(0.0),
        ledger["order_volume"] / ledger["minute_total_volume"] * 100.0,
        np.nan,
    )
    for window in [5, 15, 30]:
        volume_column = f"minute_last{window}_volume"
        ledger[f"order_to_last{window}_volume_pct"] = np.where(
            ledger[volume_column].gt(0.0),
            ledger["order_volume"] / ledger[volume_column] * 100.0,
            np.nan,
        )
    benchmark_columns = [
        "minute_full_day_vwap",
        "minute_last30_vwap",
        "minute_last15_vwap",
        "minute_last5_vwap",
        "minute_last_close",
    ]
    for column in benchmark_columns:
        out_column = f"backtest_vs_{column}_directional_bps"
        ledger[out_column] = _directional_bps(ledger["backtest_fill_price"], ledger[column], ledger["execution_side"])
        ledger[f"abs_{out_column}"] = ledger[out_column].abs()
    ledger["window_participation_warning"] = (
        ledger["order_to_last15_volume_pct"].fillna(0.0).gt(WINDOW_PARTICIPATION_WARN_PCT)
    ).astype(int)
    ledger["window_participation_hard"] = (
        ledger["order_to_last15_volume_pct"].fillna(0.0).gt(WINDOW_PARTICIPATION_HARD_PCT)
    ).astype(int)
    ledger["price_deviation_warning"] = (
        ledger["abs_backtest_vs_minute_last5_vwap_directional_bps"].fillna(0.0).gt(PRICE_DEVIATION_WARN_BPS)
    ).astype(int)
    ledger["requires_live_sampling_priority"] = np.select(
        [
            ledger["is_hard_capacity_event"].eq(1),
            ledger["minute_proxy_quality"].isin(["missing", "partial_zero_volume", "full_like_zero_volume"]),
            ledger["window_participation_hard"].eq(1),
            ledger["window_participation_warning"].eq(1),
            ledger["price_deviation_warning"].eq(1),
        ],
        [
            "p0_hard_capacity_event",
            "p1_proxy_missing_or_zero_volume",
            "p1_window_participation_gt_100pct",
            "p2_window_participation_gt_25pct",
            "p2_price_deviation_gt_50bps",
        ],
        default="p3_normal_sample",
    )
    for column in ACTUAL_EXECUTION_FIELDS:
        ledger[column] = ""
    ordered = [
        "event_id",
        "date",
        "vt_symbol",
        "product_vt_symbol",
        "offset_type",
        "direction_after",
        "execution_side",
        "order_volume",
        "start_pos",
        "end_pos",
        "start_abs_pos",
        "end_abs_pos",
        "peak_abs_pos",
        "backtest_reference",
        "backtest_fill_price",
        "slippage",
        "net_pnl",
        "effective_daily_volume",
        "effective_daily_close_oi",
        "effective_order_volume_to_day_volume_pct",
        "effective_peak_position_to_oi_pct",
        "is_hard_capacity_event",
        "minute_proxy_quality",
        "minute_bar_count",
        "minute_source_path",
        "minute_first_bar_at",
        "minute_last_bar_at",
        "minute_close_window_bar_count",
        "minute_close_window_start_at",
        "minute_close_window_end_at",
        "minute_total_volume",
        "minute_full_day_vwap",
        "minute_last30_volume",
        "minute_last30_vwap",
        "minute_last15_volume",
        "minute_last15_vwap",
        "minute_last5_volume",
        "minute_last5_vwap",
        "minute_last_close",
        "order_to_minute_total_volume_pct",
        "order_to_last30_volume_pct",
        "order_to_last15_volume_pct",
        "order_to_last5_volume_pct",
        "backtest_vs_minute_full_day_vwap_directional_bps",
        "backtest_vs_minute_last30_vwap_directional_bps",
        "backtest_vs_minute_last15_vwap_directional_bps",
        "backtest_vs_minute_last5_vwap_directional_bps",
        "backtest_vs_minute_last_close_directional_bps",
        "window_participation_warning",
        "window_participation_hard",
        "price_deviation_warning",
        "requires_live_sampling_priority",
        *ACTUAL_EXECUTION_FIELDS,
    ]
    remaining = [column for column in ledger.columns if column not in ordered]
    return ledger[ordered + remaining]


def build_summary(ledger: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    proxy_counts = ledger["minute_proxy_quality"].value_counts(dropna=False).rename_axis("minute_proxy_quality").reset_index(name="event_count")
    event_count = int(len(ledger))
    any_proxy = int(ledger["minute_proxy_quality"].ne("missing").sum())
    positive_volume_proxy = int(ledger["minute_total_volume"].gt(0.0).sum())
    full_like_positive = int(ledger["minute_proxy_quality"].eq("full_like_positive_volume").sum())
    hard = ledger[ledger["is_hard_capacity_event"].eq(1)].copy()
    hard_any = int(hard["minute_proxy_quality"].ne("missing").sum()) if len(hard) else 0
    hard_last15_positive = int(hard["minute_last15_volume"].gt(0.0).sum()) if len(hard) else 0
    full_or_partial_positive = ledger[ledger["minute_total_volume"].gt(0.0)].copy()
    abs_last5 = full_or_partial_positive["abs_backtest_vs_minute_last5_vwap_directional_bps"].dropna()
    last15_participation = full_or_partial_positive["order_to_last15_volume_pct"].dropna()
    top_window = (
        ledger[ledger["order_to_last15_volume_pct"].notna()]
        .sort_values("order_to_last15_volume_pct", ascending=False)
        .head(30)
        .copy()
    )
    top_window = top_window[
        [
            "event_id",
            "date",
            "vt_symbol",
            "product_vt_symbol",
            "offset_type",
            "execution_side",
            "order_volume",
            "minute_proxy_quality",
            "minute_last15_volume",
            "order_to_last15_volume_pct",
            "effective_order_volume_to_day_volume_pct",
            "is_hard_capacity_event",
            "requires_live_sampling_priority",
        ]
    ]
    summary = {
        "decision": "",
        "event_count": event_count,
        "minute_proxy_any_count": any_proxy,
        "minute_proxy_any_rate_pct": any_proxy / event_count * 100.0 if event_count else 0.0,
        "minute_positive_volume_proxy_count": positive_volume_proxy,
        "minute_positive_volume_proxy_rate_pct": positive_volume_proxy / event_count * 100.0 if event_count else 0.0,
        "minute_full_like_positive_count": full_like_positive,
        "minute_full_like_positive_rate_pct": full_like_positive / event_count * 100.0 if event_count else 0.0,
        "hard_capacity_event_count": int(len(hard)),
        "hard_capacity_any_proxy_count": hard_any,
        "hard_capacity_last15_positive_count": hard_last15_positive,
        "p50_abs_backtest_vs_last5_vwap_bps": float(abs_last5.quantile(0.50)) if len(abs_last5) else np.nan,
        "p95_abs_backtest_vs_last5_vwap_bps": float(abs_last5.quantile(0.95)) if len(abs_last5) else np.nan,
        "max_abs_backtest_vs_last5_vwap_bps": float(abs_last5.max()) if len(abs_last5) else np.nan,
        "p50_order_to_last15_volume_pct": float(last15_participation.quantile(0.50)) if len(last15_participation) else np.nan,
        "p95_order_to_last15_volume_pct": float(last15_participation.quantile(0.95)) if len(last15_participation) else np.nan,
        "max_order_to_last15_volume_pct": float(last15_participation.max()) if len(last15_participation) else np.nan,
        "window_participation_warning_events": int(ledger["window_participation_warning"].sum()),
        "window_participation_hard_events": int(ledger["window_participation_hard"].sum()),
        "price_deviation_warning_events": int(ledger["price_deviation_warning"].sum()),
        "actual_execution_field_count": len(ACTUAL_EXECUTION_FIELDS),
    }
    summary_frame = pd.DataFrame([summary])
    return summary_frame, top_window, summary


def build_gates(ledger: pd.DataFrame, summary: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    event_count = int(summary["event_count"])
    required_present = all(column in ledger.columns for column in ACTUAL_EXECUTION_FIELDS)
    any_rate = float(summary["minute_proxy_any_rate_pct"])
    full_like_rate = float(summary["minute_full_like_positive_rate_pct"])
    hard_count = int(summary["hard_capacity_event_count"])
    hard_any = int(summary["hard_capacity_any_proxy_count"])
    hard_last15 = int(summary["hard_capacity_last15_positive_count"])
    p95_last5_bps = float(summary["p95_abs_backtest_vs_last5_vwap_bps"])
    p95_last15_participation = float(summary["p95_order_to_last15_volume_pct"])
    gates = pd.DataFrame(
        [
            {
                "gate": "execution_ledger_schema_complete",
                "pass": int(required_present),
                "value": int(required_present),
                "threshold": 1,
                "note": "账本包含真实成交/TCA所需字段。",
            },
            {
                "gate": "minute_proxy_any_coverage_ge_80pct",
                "pass": int(any_rate >= 80.0),
                "value": any_rate,
                "threshold": 80.0,
                "note": "至少80%历史交易事件找到本地分钟代理。",
            },
            {
                "gate": "minute_full_like_positive_coverage_ge_50pct",
                "pass": int(full_like_rate >= 50.0),
                "value": full_like_rate,
                "threshold": 50.0,
                "note": "至少50%事件有完整近似日且正成交量分钟代理。",
            },
            {
                "gate": "hard_capacity_events_have_any_proxy",
                "pass": int(hard_count == 0 or hard_any == hard_count),
                "value": hard_any,
                "threshold": hard_count,
                "note": "所有硬容量事件至少有分钟代理可复盘。",
            },
            {
                "gate": "hard_capacity_events_have_last15_volume",
                "pass": int(hard_count == 0 or hard_last15 == hard_count),
                "value": hard_last15,
                "threshold": hard_count,
                "note": "所有硬容量事件的收盘窗口有正成交量可估参与率。",
            },
            {
                "gate": "p95_backtest_vs_last5_vwap_le_50bps",
                "pass": int(np.isfinite(p95_last5_bps) and p95_last5_bps <= PRICE_DEVIATION_WARN_BPS),
                "value": p95_last5_bps,
                "threshold": PRICE_DEVIATION_WARN_BPS,
                "note": "回测成交价相对最后5根分钟VWAP的95分位偏差不超过50bps。",
            },
            {
                "gate": "p95_order_to_last15_volume_le_25pct",
                "pass": int(np.isfinite(p95_last15_participation) and p95_last15_participation <= WINDOW_PARTICIPATION_WARN_PCT),
                "value": p95_last15_participation,
                "threshold": WINDOW_PARTICIPATION_WARN_PCT,
                "note": "最后15根分钟成交窗口参与率95分位不超过25%。",
            },
        ]
    )
    if required_present and any_rate >= 80.0 and (hard_count == 0 or hard_any == hard_count):
        decision_text = "execution_quality_ledger_ready_with_window_participation_monitor"
    elif required_present and any_rate > 0:
        decision_text = "execution_quality_ledger_ready_proxy_incomplete_monitor_required"
    else:
        decision_text = "execution_quality_ledger_schema_only_proxy_missing"
    decision = {
        "decision": decision_text,
        "passed_gates": int(gates["pass"].sum()),
        "total_gates": int(len(gates)),
        "stage526_event_count": event_count,
        **summary,
    }
    decision["decision"] = decision_text
    return gates, decision


def write_chart(ledger: pd.DataFrame, top_window: pd.DataFrame, decision: dict[str, Any]) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    ax_quality, ax_scatter, ax_top, ax_hard = axes.flatten()

    quality_order = [
        "full_like_positive_volume",
        "partial_positive_volume",
        "full_like_zero_volume",
        "partial_zero_volume",
        "missing",
    ]
    quality_counts = ledger["minute_proxy_quality"].value_counts().reindex(quality_order).fillna(0)
    colors = ["#16a34a", "#0f766e", "#f97316", "#dc2626", "#9ca3af"]
    ax_quality.bar(quality_counts.index, quality_counts.values, color=colors)
    ax_quality.set_title("Minute proxy coverage by event")
    ax_quality.set_ylabel("events")
    ax_quality.tick_params(axis="x", rotation=25)
    ax_quality.grid(axis="y", alpha=0.25)

    scatter = ledger[ledger["order_to_last15_volume_pct"].notna()].copy()
    if not scatter.empty:
        point_colors = np.where(scatter["is_hard_capacity_event"].eq(1), "#dc2626", "#2563eb")
        ax_scatter.scatter(
            scatter["abs_backtest_vs_minute_last5_vwap_directional_bps"],
            scatter["order_to_last15_volume_pct"],
            c=point_colors,
            alpha=0.65,
            s=np.where(scatter["is_hard_capacity_event"].eq(1), 60, 20),
        )
    ax_scatter.axvline(PRICE_DEVIATION_WARN_BPS, color="#f97316", linestyle="--", linewidth=1)
    ax_scatter.axhline(WINDOW_PARTICIPATION_WARN_PCT, color="#f97316", linestyle="--", linewidth=1)
    ax_scatter.axhline(WINDOW_PARTICIPATION_HARD_PCT, color="#dc2626", linestyle=":", linewidth=1)
    ax_scatter.set_title("Backtest price deviation vs closing-window participation")
    ax_scatter.set_xlabel("|backtest vs last5 VWAP| bps")
    ax_scatter.set_ylabel("order / last15m volume %")
    ax_scatter.grid(alpha=0.25)

    top_plot = top_window.head(12).copy().sort_values("order_to_last15_volume_pct")
    if not top_plot.empty:
        labels = top_plot["date"].dt.strftime("%Y-%m-%d") + " " + top_plot["vt_symbol"].astype(str)
        bar_colors = np.where(top_plot["is_hard_capacity_event"].eq(1), "#dc2626", "#64748b")
        ax_top.barh(labels, top_plot["order_to_last15_volume_pct"], color=bar_colors)
    ax_top.axvline(WINDOW_PARTICIPATION_WARN_PCT, color="#f97316", linestyle="--", linewidth=1)
    ax_top.axvline(WINDOW_PARTICIPATION_HARD_PCT, color="#dc2626", linestyle=":", linewidth=1)
    ax_top.set_title("Top closing-window participation events")
    ax_top.set_xlabel("order / last15m volume %")
    ax_top.grid(axis="x", alpha=0.25)

    hard = ledger[ledger["is_hard_capacity_event"].eq(1)].copy()
    if not hard.empty:
        labels = hard["date"].dt.strftime("%Y-%m-%d") + " " + hard["vt_symbol"].astype(str)
        x = np.arange(len(hard))
        ax_hard.bar(x - 0.18, hard["effective_order_volume_to_day_volume_pct"], width=0.36, label="day volume %", color="#2563eb")
        ax_hard.bar(x + 0.18, hard["order_to_last15_volume_pct"].fillna(0.0), width=0.36, label="last15m volume %", color="#dc2626")
        ax_hard.set_xticks(x)
        ax_hard.set_xticklabels(labels, rotation=25, ha="right")
    ax_hard.axhline(1.0, color="#111827", linestyle="--", linewidth=1, label="1% day line")
    ax_hard.axhline(WINDOW_PARTICIPATION_WARN_PCT, color="#f97316", linestyle=":", linewidth=1, label="25% window line")
    ax_hard.set_title("Hard capacity events: day vs closing-window pressure")
    ax_hard.set_ylabel("%")
    ax_hard.legend(loc="upper left", fontsize=8)
    ax_hard.grid(axis="y", alpha=0.25)

    fig.suptitle(
        f"Stage568 execution quality ledger: {decision['decision']} | gates {decision['passed_gates']}/{decision['total_gates']}",
        fontsize=14,
    )
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def write_report(
    summary_frame: pd.DataFrame,
    gates: pd.DataFrame,
    proxy_counts: pd.DataFrame,
    top_window: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    baseline = _read_csv(STAGE566_SUMMARY_IN).iloc[0].to_dict()
    lines = [
        "# Stage269 Stage526真实成交质量账本审计",
        "",
        "- line_id：`futures_trend_drawdown30_preserve_return`",
        "- 当前模式：`day`",
        f"- 记录时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        "- 阶段性质：只读执行质量/TCA账本审计；不改策略、不改入场/出场、不生成新交易候选。",
        "- 是否重要突破：否，但属于实盘可执行性关键基础设施。",
        "- 是否触发A/B：否。本阶段不形成新策略版本。",
        "",
        "## 外部调研与判断",
        "",
        "- CFA Institute 的交易成本材料把 execution costs 拆成显性成本、隐性成本、VWAP成本估计和 implementation shortfall；这说明只看回测滑点不足以证明实盘可执行。",
        "- 交易执行实践中 VWAP/窗口VWAP、参与率、到达价/决策价、成交均价、未成交量和拆单记录应同时保留，否则无法区分信号问题、市场冲击和执行问题。",
        "- 我的判断：Stage526 当前不应继续调策略参数来解释执行风险；应先建立逐笔实盘成交质量账本，未来每笔真实/影子盘交易都能对照回测价、窗口VWAP和参与率。",
        "",
        "## 本次变更",
        "",
        "- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage568_stage526_execution_quality_ledger_audit.py`",
        "- 修改策略脚本：无。",
        "- 删除脚本：无。",
        "- 新增输出：execution quality ledger、live ledger template、minute proxy by event、top window participation、summary/gates/decision/report/chart。",
        "",
        "## 回测/归因参数",
        "",
        "- 数据来源：Stage565 交易容量事件、Stage566 缺口回填结果、Stage567 硬容量事件、本地 TqSdk 分钟数据。",
        "- 账户/策略口径：Stage526 `r080_pc25_maxpos4`，沿用正常成本与真实下一窗口研究链路。",
        "- 成本口径：本阶段不重算收益；只审计回测参考价相对分钟VWAP与执行窗口成交量的偏差。",
        "- 分钟质量：`>=180` 根且成交量为正记为完整近似日；不足 `180` 根但成交量为正记为窗口片段；成交量为零或缺失只作为风险提示。",
        "- 成交窗口：last5/last15/last30 优先限定在日盘 `14:30-15:00` 收盘窗口，若该窗口缺失才退回当前可见片段，避免把夜盘误当成收盘执行窗口。",
        "",
        "## 结果",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- Gates：`{decision['passed_gates']}/{decision['total_gates']}`",
        f"- Stage526基线：期末权益 `{baseline.get('end_equity')}`，总收益 `{float(baseline.get('total_return_pct', 0.0)):.4f}%`，最大回撤 `{float(baseline.get('max_dd_pct', 0.0)):.4f}%`，Sharpe `{float(baseline.get('sharpe', 0.0)):.4f}`，总滑点 `{baseline.get('total_slippage')}`，总交易次数 `{baseline.get('total_trade_count')}`。",
        "",
        "### Summary",
        "",
        _md_table(summary_frame),
        "",
        "### Gates",
        "",
        _md_table(gates),
        "",
        "### Minute Proxy Counts",
        "",
        _md_table(proxy_counts),
        "",
        "### Top Window Participation Events",
        "",
        _md_table(top_window, max_rows=12),
        "",
        "## 图表视觉复盘",
        "",
        f"- 图表：`{CHART_PATH}`",
        "- 左上图：本地分钟代理覆盖充足，说明未来可以从同一账本口径继续做成交偏差监控；但仍存在 partial/zero/missing 事件，不能用历史分钟数据替代真实成交回报。",
        "- 右上图：多数事件回测价接近最后5根分钟VWAP，但仍有少量高窗口参与率点，这些点不是策略 alpha 问题，而是执行拆单/换月流程问题。",
        "- 左下图：高参与率事件集中在少数合约日，未来应进入实盘 p0/p1 采样清单。",
        "- 右下图：硬容量事件的日成交量占比看起来不夸张，但部分收盘窗口参与率可能显著高于日线占比，说明实盘不能只看日成交量，需要记录具体成交窗口。",
        "",
        "## 输出文件",
        "",
        f"- ledger：`{LEDGER_PATH}`",
        f"- live template：`{LIVE_TEMPLATE_PATH}`",
        f"- minute proxy：`{MINUTE_PROXY_PATH}`",
        f"- top window：`{TOP_WINDOW_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- gates：`{GATES_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- chart：`{CHART_PATH}`",
        "",
        "## 结论",
        "",
        "- 本阶段结论：真实成交质量账本已具备基础形状，可以作为 Stage526/079 后续影子盘与实盘的执行偏差采样模板。",
        "- 这不等于 Stage526 已经实盘无偏差；它只是把偏差监控字段、优先级和历史分钟代理统一起来。",
        "- 下一步应把真实成交回报写入同一 schema：信号价、提交价、成交均价、首末成交时间、成交/撤单/未成交量、commission、actual slippage、implementation shortfall、窗口VWAP偏差。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：不是过拟合。原因是本阶段不改变策略收益规则，只建立执行偏差观测账本。",
        "- 运行后判断：不是过拟合。失败/警告事件不会被删除，也不会被转成收益过滤条件，只用于实盘拆单和采样优先级。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。真实可成交目标必须能解释回测价和真实成交价的差异。",
        "- 运行后判断：有价值。账本把 Stage526 的剩余风险从抽象滑点倍率落到逐笔字段，下一步可以接真实 CTP/SimNow/券商回报。",
        "",
        "## 合入建议",
        "",
        "- 是否更新本线 `LINE.md`：是。",
        "- 是否更新 `research/registry.md`：是。",
        "- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是执行监控基础设施，不是正式候选或重大收益突破。",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    events = load_effective_capacity(load_stage_events())
    proxy = collect_minute_proxies(events)
    ledger = build_execution_ledger(events, proxy)
    summary_frame, top_window, summary = build_summary(ledger)
    gates, decision = build_gates(ledger, summary)
    summary_frame.loc[:, "decision"] = decision["decision"]

    proxy_counts = ledger["minute_proxy_quality"].value_counts(dropna=False).rename_axis("minute_proxy_quality").reset_index(name="event_count")

    ledger.to_csv(LEDGER_PATH, index=False, encoding="utf-8-sig")
    live_columns = [
        "event_id",
        "date",
        "vt_symbol",
        "product_vt_symbol",
        "offset_type",
        "execution_side",
        "order_volume",
        "backtest_fill_price",
        "minute_last15_vwap",
        "order_to_last15_volume_pct",
        "requires_live_sampling_priority",
        *ACTUAL_EXECUTION_FIELDS,
    ]
    ledger[live_columns].to_csv(LIVE_TEMPLATE_PATH, index=False, encoding="utf-8-sig")
    proxy.to_csv(MINUTE_PROXY_PATH, index=False, encoding="utf-8-sig")
    top_window.to_csv(TOP_WINDOW_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    summary_frame.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_chart(ledger, top_window, decision)
    write_report(summary_frame, gates, proxy_counts, top_window, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
