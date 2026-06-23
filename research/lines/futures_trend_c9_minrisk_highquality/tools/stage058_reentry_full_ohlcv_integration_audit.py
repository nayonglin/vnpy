from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage058"
MODEL_TAG = "stage058_reentry_full_ohlcv_integration_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage058_c9_minrisk_reentry_full_ohlcv_integration_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE054_DIR = LINE_DIR / "outputs" / "stage054_c9_reentry_reclaim_quality_audit"
STAGE055_DIR = LINE_DIR / "outputs" / "stage055_reentry_ohlcv_source_repair_audit"
STAGE056_DIR = LINE_DIR / "outputs" / "stage056_reentry_gap_local_deep_search"
STAGE057_DIR = LINE_DIR / "outputs" / "stage057_reentry_gap_tqsdk_backtest_refill"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage058_reentry_full_ohlcv_integration_audit"

STAGE055_EVENT_IN = (
    STAGE055_DIR
    / "qmt_roll_stage055_c9_minrisk_reentry_ohlcv_source_repair_audit_event_repair_"
    "stage055_reentry_ohlcv_source_repair_audit_v1.csv"
)
STAGE055_DECISION_IN = (
    STAGE055_DIR
    / "qmt_roll_stage055_c9_minrisk_reentry_ohlcv_source_repair_audit_decision_"
    "stage055_reentry_ohlcv_source_repair_audit_v1.json"
)
STAGE056_EVENT_IN = (
    STAGE056_DIR
    / "qmt_roll_stage056_c9_minrisk_reentry_gap_local_deep_search_event_best_"
    "stage056_reentry_gap_local_deep_search_v1.csv"
)
STAGE056_DECISION_IN = (
    STAGE056_DIR
    / "qmt_roll_stage056_c9_minrisk_reentry_gap_local_deep_search_decision_"
    "stage056_reentry_gap_local_deep_search_v1.json"
)
STAGE057_STATUS_IN = (
    STAGE057_DIR
    / "qmt_roll_stage057_c9_minrisk_reentry_gap_tqsdk_backtest_refill_event_status_"
    "stage057_reentry_gap_tqsdk_backtest_refill_v1.csv"
)
STAGE057_TICK_IN = (
    STAGE057_DIR
    / "qmt_roll_stage057_c9_minrisk_reentry_gap_tqsdk_backtest_refill_tick_rebuilt_bars_"
    "stage057_reentry_gap_tqsdk_backtest_refill_v1.csv"
)
STAGE057_DECISION_IN = (
    STAGE057_DIR
    / "qmt_roll_stage057_c9_minrisk_reentry_gap_tqsdk_backtest_refill_decision_"
    "stage057_reentry_gap_tqsdk_backtest_refill_v1.json"
)
CURVE_IN = (
    STAGE054_DIR
    / "qmt_roll_stage054_c9_minrisk_reentry_reclaim_quality_audit_upper_bound_curve_"
    "stage054_c9_reentry_reclaim_quality_audit_v1.csv"
)

INTEGRATED_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_integrated_events_{MODEL_TAG}.csv"
SOURCE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
QUALITY_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quality_summary_{MODEL_TAG}.csv"
YEAR_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_summary_{MODEL_TAG}.csv"
PRODUCT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_summary_{MODEL_TAG}.csv"
FEATURE_BIN_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_bin_summary_{MODEL_TAG}.csv"
CORRELATION_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_correlation_summary_{MODEL_TAG}.csv"
CONTRIB_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contribution_curve_{MODEL_TAG}.csv"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_chart_{MODEL_TAG}.png"
SCATTER_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ohlcv_scatter_{MODEL_TAG}.png"
HEATMAP_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_heatmap_{MODEL_TAG}.png"
ATLAS_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_single_bar_atlas_{MODEL_TAG}.png"

SOURCE_COLORS = {
    "stage055_best_source": "#1f77b4",
    "stage056_local_deep_search": "#2ca02c",
    "stage057_tick_rebuilt": "#17becf",
    "unresolved": "#d62728",
}


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
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if np.isfinite(out) else default


def _safe_int(value: Any, default: int = 0) -> int:
    out = _safe_float(value, np.nan)
    if not np.isfinite(out):
        return default
    return int(out)


def _timestamp(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts


def _normalize_numeric(data: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = data.copy()
    for column in columns:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    return out


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    s55 = _read_csv(STAGE055_EVENT_IN)
    s56 = _read_csv(STAGE056_EVENT_IN)
    s57_status = _read_csv(STAGE057_STATUS_IN)
    s57_tick = _read_csv(STAGE057_TICK_IN)
    curve = _read_csv(CURVE_IN)
    for frame in [s55, s56, s57_status, s57_tick]:
        for column in ["reentry_time", "bar_datetime", "reentry_exit_day"]:
            if column in frame.columns:
                frame[column] = pd.to_datetime(frame[column], errors="coerce")
                try:
                    frame[column] = frame[column].dt.tz_localize(None)
                except (TypeError, AttributeError):
                    pass
    s55 = _normalize_numeric(
        s55,
        [
            "entry_year",
            "risk_price",
            "reentry_lot_pnl",
            "reentry_positive_pnl",
            "reentry_negative_pnl_abs",
            "ohlcv_ready",
            "exact_bar_ready",
            "low_quality_reentry",
            "open",
            "high",
            "low",
            "close",
            "volume_y",
            "open_oi",
            "close_oi",
            "bar_range",
            "bar_body",
            "close_position",
            "range_r",
            "body_r",
            "volume_ratio_20",
        ],
    )
    s56 = _normalize_numeric(
        s56,
        [
            "entry_year",
            "risk_price",
            "reentry_lot_pnl",
            "ohlcv_ready",
            "exact_bar_ready",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "open_oi",
            "close_oi",
            "bar_range",
            "bar_body",
            "close_position",
            "range_r",
            "body_r",
            "volume_ratio_20",
        ],
    )
    s57_status = _normalize_numeric(
        s57_status,
        [
            "entry_year",
            "reentry_lot_pnl",
            "minute_ohlcv_ready",
            "tick_rebuilt_ready",
            "tick_target_rows",
            "tick_rebuilt_range",
            "tick_rebuilt_volume_delta",
        ],
    )
    s57_tick = _normalize_numeric(
        s57_tick,
        [
            "open",
            "high",
            "low",
            "close",
            "tick_count",
            "volume_delta",
            "open_oi",
            "close_oi",
            "bar_range",
        ],
    )
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = _normalize_numeric(curve, ["account_equity", "official_drawdown_pct", "broker10_margin_to_equity_pct"])
    decisions = {
        "stage055": _read_json(STAGE055_DECISION_IN),
        "stage056": _read_json(STAGE056_DECISION_IN),
        "stage057": _read_json(STAGE057_DECISION_IN),
    }
    return s55, s56, s57_status, s57_tick, curve, decisions


def _source_row_from_stage055(row: pd.Series) -> dict[str, Any]:
    return {
        "final_source": "stage055_best_source",
        "final_source_detail": row.get("source_name", ""),
        "final_source_path": row.get("source_path", ""),
        "final_source_status": row.get("source_status", ""),
        "final_open": _safe_float(row.get("open")),
        "final_high": _safe_float(row.get("high")),
        "final_low": _safe_float(row.get("low")),
        "final_close": _safe_float(row.get("close")),
        "final_volume": _safe_float(row.get("volume_y")),
        "final_open_oi": _safe_float(row.get("open_oi")),
        "final_close_oi": _safe_float(row.get("close_oi")),
        "final_tick_count": np.nan,
        "final_bar_datetime": _timestamp(row.get("reentry_time")),
        "final_volume_ratio_20": _safe_float(row.get("volume_ratio_20")),
    }


def _source_row_from_stage056(row: pd.Series) -> dict[str, Any]:
    return {
        "final_source": "stage056_local_deep_search",
        "final_source_detail": row.get("source_root", ""),
        "final_source_path": row.get("source_path", ""),
        "final_source_status": row.get("status", ""),
        "final_open": _safe_float(row.get("open")),
        "final_high": _safe_float(row.get("high")),
        "final_low": _safe_float(row.get("low")),
        "final_close": _safe_float(row.get("close")),
        "final_volume": _safe_float(row.get("volume")),
        "final_open_oi": _safe_float(row.get("open_oi")),
        "final_close_oi": _safe_float(row.get("close_oi")),
        "final_tick_count": np.nan,
        "final_bar_datetime": _timestamp(row.get("reentry_time")),
        "final_volume_ratio_20": _safe_float(row.get("volume_ratio_20")),
    }


def _source_row_from_stage057(row: pd.Series, status: pd.Series | None) -> dict[str, Any]:
    detail = "tqsdk_get_tick_serial_rebuilt_bar"
    path = ""
    status_value = "tick_rebuilt_ready"
    if status is not None:
        detail = str(status.get("final_refill_status", detail))
        path = str(status.get("tick_path", ""))
        status_value = str(status.get("tick_status", status_value))
    return {
        "final_source": "stage057_tick_rebuilt",
        "final_source_detail": detail,
        "final_source_path": path,
        "final_source_status": status_value,
        "final_open": _safe_float(row.get("open")),
        "final_high": _safe_float(row.get("high")),
        "final_low": _safe_float(row.get("low")),
        "final_close": _safe_float(row.get("close")),
        "final_volume": _safe_float(row.get("volume_delta")),
        "final_open_oi": _safe_float(row.get("open_oi")),
        "final_close_oi": _safe_float(row.get("close_oi")),
        "final_tick_count": _safe_float(row.get("tick_count")),
        "final_bar_datetime": _timestamp(row.get("bar_datetime")),
        "final_volume_ratio_20": np.nan,
    }


def _empty_source_row() -> dict[str, Any]:
    return {
        "final_source": "unresolved",
        "final_source_detail": "",
        "final_source_path": "",
        "final_source_status": "unresolved",
        "final_open": np.nan,
        "final_high": np.nan,
        "final_low": np.nan,
        "final_close": np.nan,
        "final_volume": np.nan,
        "final_open_oi": np.nan,
        "final_close_oi": np.nan,
        "final_tick_count": np.nan,
        "final_bar_datetime": pd.NaT,
        "final_volume_ratio_20": np.nan,
    }


def _derive_bar_features(row: dict[str, Any], risk_price: float, direction: str) -> dict[str, Any]:
    open_price = _safe_float(row.get("final_open"))
    high = _safe_float(row.get("final_high"))
    low = _safe_float(row.get("final_low"))
    close = _safe_float(row.get("final_close"))
    volume = _safe_float(row.get("final_volume"))
    bar_range = high - low if np.isfinite(high) and np.isfinite(low) else np.nan
    bar_body = abs(close - open_price) if np.isfinite(close) and np.isfinite(open_price) else np.nan
    close_position = np.nan
    if np.isfinite(bar_range) and bar_range > 0 and np.isfinite(close):
        close_position = (close - low) / bar_range
    range_r = bar_range / risk_price if np.isfinite(risk_price) and risk_price > 0 and np.isfinite(bar_range) else np.nan
    body_r = bar_body / risk_price if np.isfinite(risk_price) and risk_price > 0 and np.isfinite(bar_body) else np.nan
    direction_sign = 1 if str(direction).lower() == "long" else -1 if str(direction).lower() == "short" else 0
    directional_body_r = np.nan
    if direction_sign and np.isfinite(close) and np.isfinite(open_price) and np.isfinite(risk_price) and risk_price > 0:
        directional_body_r = direction_sign * (close - open_price) / risk_price
    directional_close_position = np.nan
    if np.isfinite(close_position):
        directional_close_position = close_position if direction_sign >= 0 else 1.0 - close_position
    final_ready = int(np.isfinite(bar_range) and bar_range > 0 and np.isfinite(volume) and volume > 0)
    return {
        "final_bar_range": bar_range,
        "final_bar_body": bar_body,
        "final_close_position": close_position,
        "final_range_r": range_r,
        "final_body_r": body_r,
        "direction_sign": direction_sign,
        "directional_body_r": directional_body_r,
        "directional_close_position": directional_close_position,
        "final_log_volume": math.log1p(volume) if np.isfinite(volume) and volume >= 0 else np.nan,
        "final_ready": final_ready,
    }


def _integrate_events(
    s55: pd.DataFrame,
    s56: pd.DataFrame,
    s57_status: pd.DataFrame,
    s57_tick: pd.DataFrame,
) -> pd.DataFrame:
    s56_by_key = {str(row["event_key"]): row for _, row in s56.iterrows()}
    s57_tick_by_key = {str(row["event_key"]): row for _, row in s57_tick.iterrows()}
    s57_status_by_key = {str(row["event_key"]): row for _, row in s57_status.iterrows()}
    rows: list[dict[str, Any]] = []
    for _, base in s55.sort_values(["entry_year", "reentry_time", "event_key"]).iterrows():
        event_key = str(base["event_key"])
        stage055_ready = _safe_int(base.get("ohlcv_ready")) == 1
        stage056_ready = False
        if event_key in s56_by_key:
            stage056_ready = _safe_int(s56_by_key[event_key].get("ohlcv_ready")) == 1
        if stage055_ready:
            source = _source_row_from_stage055(base)
        elif stage056_ready:
            source = _source_row_from_stage056(s56_by_key[event_key])
        elif event_key in s57_tick_by_key:
            source = _source_row_from_stage057(s57_tick_by_key[event_key], s57_status_by_key.get(event_key))
        else:
            source = _empty_source_row()

        risk_price = _safe_float(base.get("risk_price"))
        derived = _derive_bar_features(source, risk_price, str(base.get("direction", "")))
        product = str(base.get("normalized_product", "") or base.get("product_vt_symbol", "") or base.get("vt_symbol", ""))
        reentry_time = _timestamp(base.get("reentry_time"))
        event_day = _timestamp(base.get("reentry_exit_day"))
        if pd.isna(event_day):
            event_day = reentry_time
        record = {
            "event_key": event_key,
            "trade_id": base.get("trade_id", event_key),
            "vt_symbol": base.get("vt_symbol", ""),
            "normalized_product": product,
            "direction": base.get("direction", ""),
            "entry_year": _safe_int(base.get("entry_year"), -1),
            "reentry_year": int(reentry_time.year) if pd.notna(reentry_time) else -1,
            "reentry_time": reentry_time,
            "reentry_exit_day": event_day.normalize() if pd.notna(event_day) else pd.NaT,
            "quality_bucket": base.get("quality_bucket", ""),
            "low_quality_reentry": _safe_int(base.get("low_quality_reentry")),
            "stop_to_reentry_bars": _safe_float(base.get("stop_to_reentry_bars")),
            "extra_adverse_after_stop_r": _safe_float(base.get("extra_adverse_after_stop_r")),
            "risk_price": risk_price,
            "reentry_lot_count": _safe_float(base.get("reentry_lot_count")),
            "reentry_lot_volume": _safe_float(base.get("reentry_lot_volume")),
            "reentry_lot_pnl": _safe_float(base.get("reentry_lot_pnl"), 0.0),
            "initial_stop_pnl": _safe_float(base.get("initial_stop_pnl")),
            "final_state": base.get("final_state", ""),
            "retry_failed": _safe_int(base.get("retry_failed")),
            "stage055_ohlcv_ready": int(stage055_ready),
            "stage056_ohlcv_ready": int(stage056_ready),
            "stage057_tick_rebuilt_ready": int(event_key in s57_tick_by_key),
            **source,
            **derived,
        }
        rows.append(record)
    out = pd.DataFrame(rows)
    out["final_source_rank"] = out["final_source"].map(
        {"stage055_best_source": 1, "stage056_local_deep_search": 2, "stage057_tick_rebuilt": 3, "unresolved": 9}
    )
    return out.sort_values(["entry_year", "reentry_time", "event_key"]).reset_index(drop=True)


def _group_summary(data: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    return (
        data.groupby(keys, dropna=False)
        .agg(
            event_count=("event_key", "count"),
            ready_count=("final_ready", "sum"),
            reentry_pnl=("reentry_lot_pnl", "sum"),
            positive_pnl=("reentry_lot_pnl", lambda item: item[item > 0].sum()),
            negative_pnl_abs=("reentry_lot_pnl", lambda item: -item[item < 0].sum()),
            positive_event_count=("reentry_lot_pnl", lambda item: int((item > 0).sum())),
            negative_event_count=("reentry_lot_pnl", lambda item: int((item < 0).sum())),
            product_count=("normalized_product", "nunique"),
            year_count=("entry_year", "nunique"),
            median_range_r=("final_range_r", "median"),
            median_body_r=("final_body_r", "median"),
            median_directional_close_position=("directional_close_position", "median"),
            median_log_volume=("final_log_volume", "median"),
        )
        .reset_index()
        .sort_values(["reentry_pnl", "event_count"], ascending=[False, False])
    )


def _qcut_rank_labels(series: pd.Series, max_bins: int = 4) -> pd.Series:
    valid = series.dropna()
    result = pd.Series(index=series.index, dtype="object")
    if valid.empty:
        return result
    unique_count = int(valid.nunique())
    if unique_count < 2 or len(valid) < 4:
        result.loc[valid.index] = "single_or_too_sparse"
        return result
    bins = min(max_bins, unique_count, len(valid))
    labels = [f"q{i + 1}_low_to_high" for i in range(bins)]
    ranks = valid.rank(method="first")
    result.loc[valid.index] = pd.qcut(ranks, q=bins, labels=labels).astype(str)
    return result


def _feature_bin_summary(data: pd.DataFrame) -> pd.DataFrame:
    features = [
        ("final_range_r", "range_r_quartile"),
        ("final_body_r", "body_r_quartile"),
        ("directional_close_position", "directional_close_position_quartile"),
        ("directional_body_r", "directional_body_r_quartile"),
        ("final_log_volume", "log_volume_quartile_source_mixed"),
        ("final_volume_ratio_20", "volume_ratio_20_quartile_stage055_056_only"),
    ]
    rows: list[pd.DataFrame] = []
    for feature, feature_name in features:
        if feature not in data.columns:
            continue
        temp = data.dropna(subset=[feature]).copy()
        if temp.empty:
            continue
        temp["feature_bin"] = _qcut_rank_labels(temp[feature])
        grouped = (
            temp.groupby("feature_bin", dropna=False)
            .agg(
                event_count=("event_key", "count"),
                reentry_pnl=("reentry_lot_pnl", "sum"),
                positive_pnl=("reentry_lot_pnl", lambda item: item[item > 0].sum()),
                negative_pnl_abs=("reentry_lot_pnl", lambda item: -item[item < 0].sum()),
                positive_event_count=("reentry_lot_pnl", lambda item: int((item > 0).sum())),
                negative_event_count=("reentry_lot_pnl", lambda item: int((item < 0).sum())),
                product_count=("normalized_product", "nunique"),
                year_count=("entry_year", "nunique"),
                feature_min=(feature, "min"),
                feature_median=(feature, "median"),
                feature_max=(feature, "max"),
            )
            .reset_index()
        )
        grouped.insert(0, "feature", feature_name)
        rows.append(grouped)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def _correlation_summary(data: pd.DataFrame) -> pd.DataFrame:
    features = [
        "final_range_r",
        "final_body_r",
        "directional_close_position",
        "directional_body_r",
        "final_log_volume",
        "final_volume_ratio_20",
    ]
    rows: list[dict[str, Any]] = []
    for feature in features:
        valid = data[[feature, "reentry_lot_pnl"]].dropna()
        if len(valid) < 4 or valid[feature].nunique() < 2:
            corr = np.nan
        else:
            corr = valid[feature].corr(valid["reentry_lot_pnl"], method="spearman")
        rows.append(
            {
                "feature": feature,
                "n": int(len(valid)),
                "unique_count": int(valid[feature].nunique()) if not valid.empty else 0,
                "spearman_to_reentry_pnl": corr,
                "abs_spearman_to_reentry_pnl": abs(corr) if pd.notna(corr) else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values("abs_spearman_to_reentry_pnl", ascending=False)


def _contribution_curve(curve: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    out = curve[["date", "account_equity", "official_drawdown_pct", "broker10_margin_to_equity_pct"]].copy()
    temp = events.copy()
    temp["event_day"] = pd.to_datetime(temp["reentry_exit_day"], errors="coerce").dt.normalize()
    temp.loc[temp["event_day"].isna(), "event_day"] = pd.to_datetime(
        temp.loc[temp["event_day"].isna(), "reentry_time"], errors="coerce"
    ).dt.normalize()
    for source in SOURCE_COLORS:
        temp[f"pnl_{source}"] = np.where(temp["final_source"].eq(source), temp["reentry_lot_pnl"], 0.0)
    temp["pnl_all_integrated_reentry"] = temp["reentry_lot_pnl"]
    daily_columns = [f"pnl_{source}" for source in SOURCE_COLORS] + ["pnl_all_integrated_reentry"]
    daily = temp.groupby("event_day", dropna=False)[daily_columns].sum().reset_index().rename(columns={"event_day": "date"})
    out = out.merge(daily, on="date", how="left")
    for column in daily_columns:
        out[column] = out[column].fillna(0.0)
        out[f"cum_{column}"] = out[column].cumsum()
    return out


def _plot_path(curve: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=True, gridspec_kw={"height_ratios": [2, 1.2, 1]})
    axes[0].plot(curve["date"], curve["account_equity"], color="#1f77b4", lw=1.4, label="official equity")
    axes[0].set_yscale("log")
    axes[0].set_title("Stage058 full reentry OHLCV integration path")
    axes[0].set_ylabel("equity log")
    axes[0].legend(loc="upper left")

    for source, color in SOURCE_COLORS.items():
        column = f"cum_pnl_{source}"
        if column in curve.columns and curve[column].abs().sum() > 0:
            axes[1].plot(curve["date"], curve[column], lw=1.2, color=color, label=source)
    axes[1].plot(
        curve["date"],
        curve["cum_pnl_all_integrated_reentry"],
        lw=1.7,
        color="#111111",
        label="all integrated reentry PnL",
    )
    axes[1].axhline(0, color="#666666", lw=0.8)
    axes[1].set_ylabel("cumulative PnL")
    axes[1].legend(loc="upper left", fontsize=8)

    axes[2].plot(curve["date"], curve["official_drawdown_pct"], color="#8c564b", lw=1.1, label="official DD %")
    axes[2].plot(
        curve["date"],
        curve["broker10_margin_to_equity_pct"],
        color="#9467bd",
        lw=1.1,
        label="broker10 margin/equity %",
    )
    axes[2].axhline(-40, color="#8c564b", lw=0.8, ls="--")
    axes[2].axhline(100, color="#9467bd", lw=0.8, ls="--")
    axes[2].set_ylabel("pct")
    axes[2].legend(loc="upper left")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_scatter(data: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(14, 11))
    plots = [
        ("final_range_r", "reentry_lot_pnl", "range_r vs PnL"),
        ("directional_close_position", "reentry_lot_pnl", "directional close position vs PnL"),
        ("final_range_r", "final_log_volume", "range_r vs log volume"),
        ("directional_body_r", "reentry_lot_pnl", "directional body_r vs PnL"),
    ]
    max_abs_pnl = max(float(data["reentry_lot_pnl"].abs().max()), 1.0)
    for ax, (x_col, y_col, title) in zip(axes.ravel(), plots):
        for source, group in data.groupby("final_source"):
            valid = group.dropna(subset=[x_col, y_col])
            if valid.empty:
                continue
            sizes = 25 + 250 * valid["reentry_lot_pnl"].abs() / max_abs_pnl
            ax.scatter(
                valid[x_col],
                valid[y_col],
                s=sizes,
                alpha=0.72,
                color=SOURCE_COLORS.get(source, "#7f7f7f"),
                edgecolors="#222222",
                linewidths=0.3,
                label=source,
            )
        ax.axhline(0, color="#555555", lw=0.7)
        ax.set_xlabel(x_col)
        ax.set_ylabel(y_col)
        ax.set_title(title)
    top_labels = data.reindex(data["reentry_lot_pnl"].abs().sort_values(ascending=False).head(5).index)
    ax = axes[0, 0]
    for _, row in top_labels.iterrows():
        if pd.notna(row["final_range_r"]):
            ax.annotate(
                str(row["vt_symbol"]).split(".")[0],
                (row["final_range_r"], row["reentry_lot_pnl"]),
                fontsize=8,
                xytext=(4, 4),
                textcoords="offset points",
            )
    handles, labels = axes[0, 0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=8)
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    fig.savefig(SCATTER_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_heatmap(product_summary: pd.DataFrame, data: pd.DataFrame) -> None:
    top_products = product_summary.reindex(product_summary["reentry_pnl"].abs().sort_values(ascending=False).index)
    top_products = top_products["normalized_product"].head(18).tolist()
    temp = data[data["normalized_product"].isin(top_products)].copy()
    pivot = temp.pivot_table(
        index="normalized_product",
        columns="entry_year",
        values="reentry_lot_pnl",
        aggfunc="sum",
        fill_value=0.0,
    )
    if pivot.empty:
        return
    pivot = pivot.loc[top_products]
    fig, ax = plt.subplots(figsize=(13, max(6, 0.38 * len(pivot) + 2)))
    values = pivot.values
    vmax = float(np.nanmax(np.abs(values))) if values.size else 1.0
    vmax = max(vmax, 1.0)
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([str(int(col)) for col in pivot.columns], rotation=45, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_title("Stage058 reentry PnL by product and year")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            value = values[i, j]
            if abs(value) >= vmax * 0.08:
                ax.text(j, i, f"{value/1000:.0f}k", ha="center", va="center", fontsize=7, color="#111111")
    fig.colorbar(image, ax=ax, label="reentry PnL")
    fig.tight_layout()
    fig.savefig(HEATMAP_CHART_OUT, dpi=150)
    plt.close(fig)


def _atlas_selection(data: pd.DataFrame, limit: int = 16) -> pd.DataFrame:
    selected = []
    selected.extend(data.sort_values("reentry_lot_pnl", ascending=False).head(6).index.tolist())
    selected.extend(data.sort_values("reentry_lot_pnl", ascending=True).head(5).index.tolist())
    for source in ["stage055_best_source", "stage056_local_deep_search", "stage057_tick_rebuilt"]:
        selected.extend(data[data["final_source"].eq(source)].head(2).index.tolist())
    seen: set[int] = set()
    ordered: list[int] = []
    for idx in selected:
        if int(idx) not in seen:
            ordered.append(int(idx))
            seen.add(int(idx))
        if len(ordered) >= limit:
            break
    return data.loc[ordered].copy()


def _plot_atlas(data: pd.DataFrame) -> pd.DataFrame:
    selected = _atlas_selection(data)
    rows = 4
    cols = 4
    fig, axes = plt.subplots(rows, cols, figsize=(16, 14))
    axes_flat = axes.ravel()
    manifest_rows: list[dict[str, Any]] = []
    for ax in axes_flat:
        ax.axis("off")
    for ax, (_, row) in zip(axes_flat, selected.iterrows()):
        ax.axis("on")
        open_price = _safe_float(row["final_open"])
        high = _safe_float(row["final_high"])
        low = _safe_float(row["final_low"])
        close = _safe_float(row["final_close"])
        if not all(np.isfinite(value) for value in [open_price, high, low, close]):
            ax.text(0.5, 0.5, "missing bar", ha="center", va="center")
            continue
        favorable = _safe_float(row["directional_body_r"], 0.0) >= 0
        color = "#2ca02c" if favorable else "#d62728"
        span = max(high - low, abs(close - open_price), 1e-9)
        margin = span * 0.35
        ax.vlines(0.5, low, high, color="#111111", lw=1.5)
        body_low = min(open_price, close)
        body_height = max(abs(close - open_price), span * 0.03)
        ax.add_patch(Rectangle((0.35, body_low), 0.3, body_height, facecolor=color, edgecolor="#111111", alpha=0.75))
        ax.set_xlim(0, 1)
        ax.set_ylim(low - margin, high + margin)
        ax.set_xticks([])
        ax.tick_params(axis="y", labelsize=7)
        title = f"{row['vt_symbol']} {pd.Timestamp(row['reentry_time']):%Y-%m-%d %H:%M}"
        ax.set_title(title, fontsize=8)
        info = (
            f"pnl={row['reentry_lot_pnl']:.0f}\n"
            f"src={row['final_source'].replace('stage0', 's0')}\n"
            f"rangeR={row['final_range_r']:.3f}\n"
            f"dClose={row['directional_close_position']:.2f}"
        )
        ax.text(0.02, 0.98, info, transform=ax.transAxes, va="top", ha="left", fontsize=7)
        manifest_rows.append(
            {
                "event_key": row["event_key"],
                "vt_symbol": row["vt_symbol"],
                "reentry_time": row["reentry_time"],
                "reentry_lot_pnl": row["reentry_lot_pnl"],
                "final_source": row["final_source"],
                "final_range_r": row["final_range_r"],
                "directional_close_position": row["directional_close_position"],
            }
        )
    fig.suptitle("Stage058 selected reentry one-minute OHLCV bars", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(ATLAS_CHART_OUT, dpi=150)
    plt.close(fig)
    return pd.DataFrame(manifest_rows)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    display = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    lines = [
        "| " + " | ".join(str(column) for column in display.columns) + " |",
        "| " + " | ".join(["---"] * len(display.columns)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in display.columns) + " |")
    return "\n".join(lines)


def _write_report(
    decision: dict[str, Any],
    source_summary: pd.DataFrame,
    quality_summary: pd.DataFrame,
    year_summary: pd.DataFrame,
    product_summary: pd.DataFrame,
    feature_bins: pd.DataFrame,
    correlations: pd.DataFrame,
) -> None:
    lines = [
        "# Stage058 full reentry OHLCV integration audit",
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- candidate_like: `{decision['candidate_like']}`",
        f"- full ready events: `{decision['full_ready_event_count']}/{decision['input_event_count']}`",
        f"- unresolved events: `{decision['unresolved_event_count']}`",
        f"- integrated reentry PnL: `{decision['integrated_reentry_pnl']:.2f}`",
        f"- top positive event: `{decision['top_positive_event']['vt_symbol']} {decision['top_positive_event']['reentry_lot_pnl']:.2f}`",
        "",
        "## Source Summary",
        "",
        _md_table(
            source_summary[
                [
                    "final_source",
                    "event_count",
                    "ready_count",
                    "reentry_pnl",
                    "positive_event_count",
                    "negative_event_count",
                    "product_count",
                    "year_count",
                    "median_range_r",
                ]
            ]
        ),
        "",
        "## Quality Bucket Summary",
        "",
        _md_table(quality_summary[["quality_bucket", "event_count", "reentry_pnl", "product_count", "year_count"]], 20),
        "",
        "## Year Summary",
        "",
        _md_table(year_summary[["entry_year", "event_count", "reentry_pnl", "positive_event_count", "negative_event_count"]], 20),
        "",
        "## Top Product Summary",
        "",
        _md_table(
            product_summary[
                [
                    "normalized_product",
                    "event_count",
                    "reentry_pnl",
                    "positive_event_count",
                    "negative_event_count",
                    "year_count",
                ]
            ].reindex(product_summary["reentry_pnl"].abs().sort_values(ascending=False).index),
            20,
        ),
        "",
        "## Feature Correlations",
        "",
        _md_table(correlations, 20),
        "",
        "## Feature Quartile Diagnostics",
        "",
        _md_table(feature_bins[["feature", "feature_bin", "event_count", "reentry_pnl", "product_count", "year_count"]], 40),
        "",
        "## Visual Outputs",
        "",
        f"- path chart: `{PATH_CHART_OUT}`",
        f"- OHLCV scatter: `{SCATTER_CHART_OUT}`",
        f"- product-year heatmap: `{HEATMAP_CHART_OUT}`",
        f"- single-bar atlas: `{ATLAS_CHART_OUT}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _top_event_dict(row: pd.Series) -> dict[str, Any]:
    return {
        "event_key": row.get("event_key", ""),
        "vt_symbol": row.get("vt_symbol", ""),
        "reentry_time": _timestamp(row.get("reentry_time")),
        "reentry_lot_pnl": _safe_float(row.get("reentry_lot_pnl"), 0.0),
        "final_source": row.get("final_source", ""),
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    s55, s56, s57_status, s57_tick, curve, upstream_decisions = _load_inputs()
    events = _integrate_events(s55, s56, s57_status, s57_tick)
    if len(events) != 54:
        raise RuntimeError(f"expected 54 integrated reentry events, got {len(events)}")

    source_summary = _group_summary(events, ["final_source"])
    quality_summary = _group_summary(events, ["quality_bucket"])
    year_summary = _group_summary(events, ["entry_year"]).sort_values("entry_year")
    product_summary = _group_summary(events, ["normalized_product"])
    feature_bins = _feature_bin_summary(events)
    correlations = _correlation_summary(events)
    contribution = _contribution_curve(curve, events)

    atlas_manifest = _plot_atlas(events)
    _plot_path(contribution)
    _plot_scatter(events)
    _plot_heatmap(product_summary, events)

    events.to_csv(INTEGRATED_OUT, index=False, encoding="utf-8-sig")
    source_summary.to_csv(SOURCE_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    quality_summary.to_csv(QUALITY_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    year_summary.to_csv(YEAR_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    feature_bins.to_csv(FEATURE_BIN_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    correlations.to_csv(CORRELATION_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    contribution.to_csv(CONTRIB_CURVE_OUT, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")

    top_positive = events.sort_values("reentry_lot_pnl", ascending=False).iloc[0]
    top_negative = events.sort_values("reentry_lot_pnl", ascending=True).iloc[0]
    max_abs_corr = _safe_float(correlations["abs_spearman_to_reentry_pnl"].max(), np.nan)
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": "stage058_full_reentry_ohlcv_integrated_no_trade_rule",
        "candidate_like": False,
        "input_event_count": int(len(events)),
        "full_ready_event_count": int(events["final_ready"].sum()),
        "unresolved_event_count": int((events["final_source"] == "unresolved").sum()),
        "integrated_reentry_pnl": float(events["reentry_lot_pnl"].sum()),
        "source_counts": {str(k): int(v) for k, v in events["final_source"].value_counts().to_dict().items()},
        "source_pnl": {
            str(row["final_source"]): float(row["reentry_pnl"])
            for _, row in source_summary[["final_source", "reentry_pnl"]].iterrows()
        },
        "top_positive_event": _top_event_dict(top_positive),
        "top_negative_event": _top_event_dict(top_negative),
        "max_abs_spearman_feature_pnl": max_abs_corr,
        "upstream_decisions": {
            "stage055": upstream_decisions["stage055"].get("decision"),
            "stage056": upstream_decisions["stage056"].get("decision"),
            "stage057": upstream_decisions["stage057"].get("decision"),
        },
        "judgment": (
            "Full OHLCV coverage is now available for all 54 C9 reentry events, "
            "but source, candle range, body, close-position and volume diagnostics remain "
            "mixed and right-tail dominated. This is a data asset, not a deployable rule."
        ),
        "outputs": {
            "integrated_events": INTEGRATED_OUT,
            "source_summary": SOURCE_SUMMARY_OUT,
            "quality_summary": QUALITY_SUMMARY_OUT,
            "year_summary": YEAR_SUMMARY_OUT,
            "product_summary": PRODUCT_SUMMARY_OUT,
            "feature_bin_summary": FEATURE_BIN_SUMMARY_OUT,
            "correlation_summary": CORRELATION_SUMMARY_OUT,
            "contribution_curve": CONTRIB_CURVE_OUT,
            "atlas_manifest": ATLAS_MANIFEST_OUT,
            "path_chart": PATH_CHART_OUT,
            "scatter_chart": SCATTER_CHART_OUT,
            "heatmap_chart": HEATMAP_CHART_OUT,
            "atlas_chart": ATLAS_CHART_OUT,
            "report": REPORT_OUT,
        },
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, source_summary, quality_summary, year_summary, product_summary, feature_bins, correlations)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
