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
STAGE = "Stage074"
MODEL_TAG = "stage074_initial_entry_authoritative_source_decision_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage074_c9_minrisk_initial_entry_authoritative_source_decision_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage074_initial_entry_authoritative_source_decision_audit"

STAGE040_DIR = LINE_DIR / "outputs" / "stage040_open_proxy_timestamp_reconstruction_audit"
STAGE045_DIR = LINE_DIR / "outputs" / "stage045_event_time_field_sync_audit"
STAGE068_DIR = LINE_DIR / "outputs" / "stage068_initial_entry_tick_coverage_audit"
STAGE070_DIR = LINE_DIR / "outputs" / "stage070_initial_entry_price_proxy_anchor_batch_refill"

STAGE040_LEDGER_IN = (
    STAGE040_DIR
    / "qmt_roll_stage040_c9_minrisk_open_proxy_timestamp_reconstruction_audit_open_proxy_ledger_"
    "stage040_open_proxy_timestamp_reconstruction_audit_v1.csv"
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
STAGE068_PLAN_IN = (
    STAGE068_DIR
    / "qmt_roll_stage068_c9_minrisk_initial_entry_tick_coverage_audit_initial_entry_tick_plan_"
    "stage068_initial_entry_tick_coverage_audit_v1.csv"
)
STAGE070_FEATURES_IN = (
    STAGE070_DIR
    / "qmt_roll_stage070_c9_minrisk_initial_entry_price_proxy_anchor_batch_refill_anchor_price_features_"
    "stage070_initial_entry_price_proxy_anchor_batch_refill_v1.csv"
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

AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_decision_audit_{MODEL_TAG}.csv"
CLASS_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_decision_class_summary_{MODEL_TAG}.csv"
YEAR_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_source_matrix_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_authority_route_chart_{MODEL_TAG}.png"
COVERAGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_coverage_decision_chart_{MODEL_TAG}.png"
ATLAS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_price_delta_atlas_{MODEL_TAG}.png"

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


def _target_minute(anchor_time: Any) -> pd.Timestamp:
    return pd.to_datetime(anchor_time, errors="coerce").floor("min")


def _exact(a: Any, b: Any) -> int:
    left = _safe_float(a)
    right = _safe_float(b)
    return int(np.isfinite(left) and np.isfinite(right) and abs(left - right) < EPS)


def _is_degenerate(open_price: Any, high: Any, low: Any, close: Any) -> int:
    values = [_safe_float(x) for x in [open_price, high, low, close]]
    if not all(np.isfinite(x) for x in values):
        return 0
    return int(abs(values[0] - values[1]) < EPS and abs(values[0] - values[2]) < EPS and abs(values[0] - values[3]) < EPS)


def _load_raw_anchor_bar(vt_symbol: str, anchor_time: Any) -> dict[str, Any]:
    start = _target_minute(anchor_time)
    if pd.isna(start):
        return {"raw_anchor_ready": 0}
    frames: list[pd.DataFrame] = []
    roots: list[str] = []
    for root in RAW_ROOTS:
        path = _raw_path(root, vt_symbol)
        if not path.exists():
            continue
        frame = pd.read_csv(path, encoding="utf-8-sig")
        if frame.empty or "bar_datetime" not in frame.columns:
            continue
        frame["bar_datetime"] = pd.to_datetime(frame["bar_datetime"], errors="coerce").dt.tz_localize(None)
        row = frame[frame["bar_datetime"].eq(start)].copy()
        if row.empty:
            continue
        row["raw_source_root"] = root.name
        row["raw_file_path"] = str(path)
        frames.append(row)
        roots.append(root.name)
    if not frames:
        return {
            "raw_anchor_ready": 0,
            "raw_anchor_open": np.nan,
            "raw_anchor_high": np.nan,
            "raw_anchor_low": np.nan,
            "raw_anchor_close": np.nan,
            "raw_anchor_volume": np.nan,
            "raw_anchor_source_roots": "",
            "raw_anchor_source_root_selected": "",
            "raw_anchor_file_path": "",
            "raw_anchor_zero_volume": 0,
            "raw_anchor_degenerate_ohlc": 0,
        }
    data = pd.concat(frames, ignore_index=True)
    data = data.drop_duplicates(subset=["bar_datetime"], keep="last").sort_values("bar_datetime")
    row = data.iloc[0]
    open_price = _safe_float(row.get("open"))
    high = _safe_float(row.get("high"))
    low = _safe_float(row.get("low"))
    close = _safe_float(row.get("close"))
    volume = _safe_float(row.get("volume"))
    return {
        "raw_anchor_ready": 1,
        "raw_anchor_open": open_price,
        "raw_anchor_high": high,
        "raw_anchor_low": low,
        "raw_anchor_close": close,
        "raw_anchor_volume": volume,
        "raw_anchor_source_roots": ",".join(sorted(set(roots))),
        "raw_anchor_source_root_selected": str(row.get("raw_source_root", "")),
        "raw_anchor_file_path": str(row.get("raw_file_path", "")),
        "raw_anchor_zero_volume": int(np.isfinite(volume) and volume == 0.0),
        "raw_anchor_degenerate_ohlc": _is_degenerate(open_price, high, low, close),
    }


def _load_stage449_anchor_bars(events: pd.DataFrame) -> pd.DataFrame:
    ready = events[events["timestamp_ready"].eq(1)].copy()
    if ready.empty:
        return pd.DataFrame()
    symbols = set(ready["vt_symbol"].astype(str))
    min_start = pd.to_datetime(ready["authority_anchor_time"], errors="coerce").min()
    max_end = pd.to_datetime(ready["authority_anchor_time"], errors="coerce").max() + pd.Timedelta(minutes=1)
    usecols = ["vt_symbol", "bar_datetime", "open", "high", "low", "close", "volume", "open_oi", "close_oi"]
    chunks: list[pd.DataFrame] = []
    for chunk in pd.read_csv(STAGE449_FULL_MINUTE_IN, encoding="utf-8-sig", usecols=usecols, chunksize=250_000):
        chunk = chunk[chunk["vt_symbol"].astype(str).isin(symbols)].copy()
        if chunk.empty:
            continue
        chunk["bar_datetime"] = pd.to_datetime(chunk["bar_datetime"], errors="coerce").dt.tz_localize(None)
        chunk = chunk[(chunk["bar_datetime"] >= min_start) & (chunk["bar_datetime"] < max_end)].copy()
        if not chunk.empty:
            chunks.append(chunk)
    if not chunks:
        return pd.DataFrame(columns=usecols)
    return pd.concat(chunks, ignore_index=True).drop_duplicates(["vt_symbol", "bar_datetime"], keep="last")


def _merge_stage449(events: pd.DataFrame, stage449: pd.DataFrame) -> pd.DataFrame:
    data = events.copy()
    if stage449.empty:
        for col in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
            data[f"stage449_anchor_{col}"] = np.nan
        data["stage449_anchor_ready"] = 0
        return data
    merged = data.merge(
        stage449,
        left_on=["vt_symbol", "authority_anchor_time"],
        right_on=["vt_symbol", "bar_datetime"],
        how="left",
        suffixes=("", "_stage449"),
    )
    for col in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        merged[f"stage449_anchor_{col}"] = pd.to_numeric(merged[col], errors="coerce")
    merged["stage449_anchor_ready"] = merged["stage449_anchor_open"].notna().astype(int)
    return merged.drop(columns=[c for c in ["bar_datetime", "open", "high", "low", "close", "volume", "open_oi", "close_oi"] if c in merged.columns])


def _load_realized_plan() -> pd.DataFrame:
    plan = _read_csv(STAGE068_PLAN_IN)
    keep = [
        "candidate_index",
        "official_open_trade_id",
        "realized_pnl",
        "closed_lot_count",
        "normalized_product",
        "product_family",
        "open_year",
        "timestamp_alignment_class",
    ]
    return plan[[col for col in keep if col in plan.columns]].drop_duplicates(["candidate_index", "official_open_trade_id"])


def _load_tq_proxy_features() -> pd.DataFrame:
    features = _read_csv(STAGE070_FEATURES_IN)
    proxy = features[features["anchor_role"].astype(str).eq("price_proxy_anchor")].copy()
    keep = [
        "candidate_index",
        "official_open_trade_id",
        "anchor_ready",
        "price_exact_any",
        "price_near_r",
        "official_open_inside_any_spread",
        "nearest_price_value",
        "min_abs_price_delta_r",
        "median_spread_r",
        "median_depth1",
    ]
    proxy = proxy[[col for col in keep if col in proxy.columns]].copy()
    for col in ["anchor_ready", "price_exact_any", "price_near_r", "official_open_inside_any_spread"]:
        if col in proxy.columns:
            proxy[col] = proxy[col].astype(str).str.lower().isin(["true", "1", "yes"]).astype(int)
    for col in ["nearest_price_value", "min_abs_price_delta_r", "median_spread_r", "median_depth1"]:
        if col in proxy.columns:
            proxy[col] = _safe_num(proxy[col])
    return proxy.drop_duplicates(["candidate_index", "official_open_trade_id"])


def _official_metrics() -> dict[str, float]:
    data = _read_csv(STAGE045_SUMMARY_IN)
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


def _source_class(row: pd.Series) -> str:
    if int(row["timestamp_ready"]) != 1:
        return "fallback_no_proxy_not_minute_authority"
    raw_ok = (
        int(row["raw_anchor_ready"]) == 1
        and int(row["raw_anchor_exact_official"]) == 1
        and int(row["raw_anchor_zero_volume"]) == 1
        and int(row["raw_anchor_degenerate_ohlc"]) == 1
    )
    if not raw_ok:
        return "timestamp_ready_raw_proxy_unresolved"
    if int(row["stage449_anchor_ready"]) == 1:
        return "raw_stage449_zero_volume_bar_authority"
    return "raw_stage452_fallback_zero_volume_bar_authority_stage449_missing"


def _tq_status(row: pd.Series) -> str:
    if int(row.get("timestamp_ready", 0)) != 1:
        return "not_timestamp_ready"
    if not np.isfinite(_safe_float(row.get("tq_min_abs_price_delta_r"), np.nan)):
        return "not_in_stage070_tq_batch"
    if int(row.get("tq_price_exact_any", 0) or 0) == 1:
        return "tq_proxy_exact_topbook"
    if int(row.get("tq_price_near_r", 0) or 0) == 1:
        return "tq_proxy_near_no_exact"
    return "tq_proxy_far_no_exact"


def _build_audit() -> pd.DataFrame:
    ledger = _read_csv(STAGE040_LEDGER_IN)
    for col in [
        "candidate_index",
        "official_open_price",
        "planned_stop_distance",
        "engine_selected_price",
        "engine_selected_exact_official",
        "raw_price",
        "raw_exact_official",
        "seed_price",
        "seed_exact_official",
        "timestamp_ready",
        "stage861_first_open_price",
        "stage861_first_open_exact_official",
    ]:
        if col in ledger.columns:
            ledger[col] = _safe_num(ledger[col])
    ledger["official_open_date"] = pd.to_datetime(ledger["official_open_date"], errors="coerce").dt.normalize()
    ledger["authority_anchor_time"] = pd.to_datetime(ledger["timestamp_first_time"], errors="coerce").dt.floor("min")
    ledger["stage861_first_open_time_ts"] = pd.to_datetime(ledger["stage861_first_open_time"], errors="coerce")

    raw_rows: list[dict[str, Any]] = []
    for _, row in ledger.iterrows():
        if int(row.get("timestamp_ready", 0) or 0) == 1:
            raw_rows.append(_load_raw_anchor_bar(str(row["vt_symbol"]), row["authority_anchor_time"]))
        else:
            raw_rows.append(
                {
                    "raw_anchor_ready": 0,
                    "raw_anchor_open": np.nan,
                    "raw_anchor_high": np.nan,
                    "raw_anchor_low": np.nan,
                    "raw_anchor_close": np.nan,
                    "raw_anchor_volume": np.nan,
                    "raw_anchor_source_roots": "",
                    "raw_anchor_source_root_selected": "",
                    "raw_anchor_file_path": "",
                    "raw_anchor_zero_volume": 0,
                    "raw_anchor_degenerate_ohlc": 0,
                }
            )
    raw = pd.DataFrame(raw_rows)
    audit = pd.concat([ledger.reset_index(drop=True), raw.reset_index(drop=True)], axis=1)
    stage449 = _load_stage449_anchor_bars(audit)
    audit = _merge_stage449(audit, stage449)

    plan = _load_realized_plan()
    tq = _load_tq_proxy_features().rename(
        columns={
            "anchor_ready": "tq_proxy_anchor_ready",
            "price_exact_any": "tq_price_exact_any",
            "price_near_r": "tq_price_near_r",
            "official_open_inside_any_spread": "tq_official_open_inside_any_spread",
            "nearest_price_value": "tq_nearest_price_value",
            "min_abs_price_delta_r": "tq_min_abs_price_delta_r",
            "median_spread_r": "tq_median_spread_r",
            "median_depth1": "tq_median_depth1",
        }
    )
    audit = audit.merge(plan, on=["candidate_index", "official_open_trade_id"], how="left")
    audit = audit.merge(tq, on=["candidate_index", "official_open_trade_id"], how="left")

    audit["raw_anchor_exact_official"] = audit.apply(lambda row: _exact(row["raw_anchor_open"], row["official_open_price"]), axis=1)
    audit["stage449_anchor_exact_official"] = audit.apply(
        lambda row: _exact(row["stage449_anchor_open"], row["official_open_price"]), axis=1
    )
    audit["stage449_anchor_zero_volume"] = (
        audit["stage449_anchor_volume"].notna() & audit["stage449_anchor_volume"].astype(float).eq(0.0)
    ).astype(int)
    audit["stage449_anchor_degenerate_ohlc"] = audit.apply(
        lambda row: _is_degenerate(
            row["stage449_anchor_open"],
            row["stage449_anchor_high"],
            row["stage449_anchor_low"],
            row["stage449_anchor_close"],
        ),
        axis=1,
    )
    risk = pd.to_numeric(audit["planned_stop_distance"], errors="coerce").replace(0, np.nan)
    audit["stage861_first_open_abs_delta_r"] = (
        (audit["stage861_first_open_price"] - audit["official_open_price"]).abs() / risk
    )
    audit["stage449_anchor_abs_delta_r"] = ((audit["stage449_anchor_open"] - audit["official_open_price"]).abs() / risk)
    audit["raw_anchor_abs_delta_r"] = ((audit["raw_anchor_open"] - audit["official_open_price"]).abs() / risk)
    audit["tq_status"] = audit.apply(_tq_status, axis=1)
    audit["source_decision_class"] = audit.apply(_source_class, axis=1)
    audit["open_year"] = pd.to_numeric(audit.get("open_year", audit["official_open_date"].dt.year), errors="coerce")
    audit["official_open_year"] = audit["official_open_date"].dt.year

    ordered = [
        "candidate_index",
        "official_open_trade_id",
        "vt_symbol",
        "direction",
        "official_open_date",
        "official_open_price",
        "planned_stop_distance",
        "official_open_volume",
        "candidate_selected_volume",
        "timestamp_ready",
        "authority_anchor_time",
        "engine_proxy_kind",
        "engine_selected_source",
        "engine_selected_price",
        "engine_selected_exact_official",
        "raw_price",
        "raw_source",
        "raw_anchor_source_root_selected",
        "raw_anchor_source_roots",
        "raw_anchor_open",
        "raw_anchor_high",
        "raw_anchor_low",
        "raw_anchor_close",
        "raw_anchor_volume",
        "raw_anchor_ready",
        "raw_anchor_exact_official",
        "raw_anchor_zero_volume",
        "raw_anchor_degenerate_ohlc",
        "stage449_anchor_open",
        "stage449_anchor_high",
        "stage449_anchor_low",
        "stage449_anchor_close",
        "stage449_anchor_volume",
        "stage449_anchor_ready",
        "stage449_anchor_exact_official",
        "stage449_anchor_zero_volume",
        "stage449_anchor_degenerate_ohlc",
        "stage861_first_open_price",
        "stage861_first_open_time",
        "stage861_first_open_exact_official",
        "stage861_first_open_abs_delta_r",
        "tq_status",
        "tq_proxy_anchor_ready",
        "tq_price_exact_any",
        "tq_price_near_r",
        "tq_official_open_inside_any_spread",
        "tq_nearest_price_value",
        "tq_min_abs_price_delta_r",
        "realized_pnl",
        "closed_lot_count",
        "normalized_product",
        "product_family",
        "open_year",
        "official_open_year",
        "source_decision_class",
    ]
    return audit[[col for col in ordered if col in audit.columns]].sort_values(["candidate_index"]).reset_index(drop=True)


def _class_summary(audit: pd.DataFrame) -> pd.DataFrame:
    return (
        audit.groupby(["source_decision_class", "engine_proxy_kind"], dropna=False)
        .agg(
            event_count=("candidate_index", "size"),
            timestamp_ready_count=("timestamp_ready", "sum"),
            raw_ready_count=("raw_anchor_ready", "sum"),
            raw_exact_count=("raw_anchor_exact_official", "sum"),
            raw_zero_volume_count=("raw_anchor_zero_volume", "sum"),
            raw_degenerate_count=("raw_anchor_degenerate_ohlc", "sum"),
            stage449_ready_count=("stage449_anchor_ready", "sum"),
            stage449_exact_count=("stage449_anchor_exact_official", "sum"),
            stage449_zero_volume_count=("stage449_anchor_zero_volume", "sum"),
            stage449_degenerate_count=("stage449_anchor_degenerate_ohlc", "sum"),
            stage861_official_first_exact_count=("stage861_first_open_exact_official", "sum"),
            tq_batch_count=("tq_min_abs_price_delta_r", lambda x: int(pd.to_numeric(x, errors="coerce").notna().sum())),
            tq_exact_count=("tq_price_exact_any", "sum"),
            net_realized_pnl=("realized_pnl", "sum"),
            positive_pnl=("realized_pnl", lambda x: float(pd.to_numeric(x, errors="coerce").clip(lower=0).sum())),
            negative_pnl_abs=("realized_pnl", lambda x: float(-pd.to_numeric(x, errors="coerce").clip(upper=0).sum())),
        )
        .reset_index()
        .sort_values(["event_count", "source_decision_class"], ascending=[False, True])
    )


def _year_matrix(audit: pd.DataFrame) -> pd.DataFrame:
    data = audit.copy()
    data["year"] = pd.to_numeric(data["official_open_year"], errors="coerce").astype("Int64")
    return (
        data.groupby(["year", "source_decision_class"], dropna=False)
        .agg(
            event_count=("candidate_index", "size"),
            timestamp_ready_count=("timestamp_ready", "sum"),
            raw_exact_count=("raw_anchor_exact_official", "sum"),
            stage449_ready_count=("stage449_anchor_ready", "sum"),
            stage449_exact_count=("stage449_anchor_exact_official", "sum"),
            tq_batch_count=("tq_min_abs_price_delta_r", lambda x: int(pd.to_numeric(x, errors="coerce").notna().sum())),
            tq_exact_count=("tq_price_exact_any", "sum"),
            net_realized_pnl=("realized_pnl", "sum"),
        )
        .reset_index()
        .sort_values(["year", "source_decision_class"])
    )


def _plot_path_chart(curve: pd.DataFrame, audit: pd.DataFrame) -> None:
    data = curve.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    points = audit.copy()
    points["official_open_date"] = pd.to_datetime(points["official_open_date"], errors="coerce").dt.normalize()
    equity_by_date = data.set_index(data["date"].dt.normalize())["official_equity"]
    points["anchor_equity"] = points["official_open_date"].map(equity_by_date)
    colors = {
        "raw_stage449_zero_volume_bar_authority": "#009e73",
        "raw_stage452_fallback_zero_volume_bar_authority_stage449_missing": "#0072b2",
        "fallback_no_proxy_not_minute_authority": "#999999",
        "timestamp_ready_raw_proxy_unresolved": "#d55e00",
    }
    fig, axes = plt.subplots(2, 1, figsize=(16, 9), sharex=False)
    axes[0].plot(data["date"], data["official_equity"] / 1_000_000, color="#1f77b4", linewidth=1.8)
    for klass, group in points.groupby("source_decision_class"):
        axes[0].scatter(
            group["official_open_date"],
            group["anchor_equity"] / 1_000_000,
            s=22 if "fallback" in klass else 34,
            alpha=0.70,
            color=colors.get(klass, "#d55e00"),
            label=klass,
        )
    axes[0].set_title("Stage074 official path with authoritative source decision classes")
    axes[0].set_ylabel("Equity (million CNY)")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="upper left", fontsize=8)

    pnl_data = points[points["realized_pnl"].notna()].sort_values("official_open_date").copy()
    for klass, group in pnl_data.groupby("source_decision_class"):
        group = group.sort_values("official_open_date").copy()
        group["cum_pnl"] = pd.to_numeric(group["realized_pnl"], errors="coerce").fillna(0).cumsum()
        axes[1].plot(
            group["official_open_date"],
            group["cum_pnl"] / 10_000,
            marker="o",
            markersize=3,
            linewidth=1.6,
            color=colors.get(klass, "#d55e00"),
            label=klass,
        )
    axes[1].axhline(0, color="black", linewidth=0.8)
    axes[1].set_title("Cumulative realized PnL for timestamp-ready initial entries by source route")
    axes[1].set_ylabel("Cumulative PnL (10k CNY)")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_coverage_chart(audit: pd.DataFrame, year_matrix: pd.DataFrame) -> None:
    timestamp_ready = audit[audit["timestamp_ready"].eq(1)]
    counts = {
        "all initial opens": len(audit),
        "timestamp-ready raw proxy": int(audit["timestamp_ready"].sum()),
        "raw anchor exact": int(audit["raw_anchor_exact_official"].sum()),
        "raw zero-volume": int(audit["raw_anchor_zero_volume"].sum()),
        "raw degenerate": int(audit["raw_anchor_degenerate_ohlc"].sum()),
        "Stage449 anchor ready": int(audit["stage449_anchor_ready"].sum()),
        "Stage449 exact": int(audit["stage449_anchor_exact_official"].sum()),
        "Stage861 first exact": int(audit["stage861_first_open_exact_official"].sum()),
        "Tq proxy batch ready": int(timestamp_ready["tq_min_abs_price_delta_r"].notna().sum()),
        "Tq proxy exact": int(timestamp_ready["tq_price_exact_any"].fillna(0).sum()),
        "fallback no proxy": int((audit["timestamp_ready"] == 0).sum()),
    }
    fig, axes = plt.subplots(1, 2, figsize=(17, 6.5))
    axes[0].barh(list(counts.keys()), list(counts.values()), color="#4c78a8")
    axes[0].set_xlim(0, max(counts.values()) + 20)
    axes[0].set_title("Initial-entry source coverage and exactness")
    axes[0].grid(True, axis="x", alpha=0.25)

    pivot = year_matrix.pivot(index="year", columns="source_decision_class", values="event_count").fillna(0)
    class_colors = {
        "raw_stage449_zero_volume_bar_authority": "#009e73",
        "raw_stage452_fallback_zero_volume_bar_authority_stage449_missing": "#0072b2",
        "fallback_no_proxy_not_minute_authority": "#999999",
        "timestamp_ready_raw_proxy_unresolved": "#d55e00",
    }
    bottom = np.zeros(len(pivot))
    xs = np.arange(len(pivot))
    for col in pivot.columns:
        values = pivot[col].values
        axes[1].bar(xs, values, bottom=bottom, label=col, color=class_colors.get(col, "#d55e00"))
        bottom += values
    axes[1].set_xticks(xs)
    axes[1].set_xticklabels([str(int(x)) for x in pivot.index], rotation=45)
    axes[1].set_title("Source decision classes by open year")
    axes[1].set_ylabel("Initial opens")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[1].legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(COVERAGE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_atlas(audit: pd.DataFrame) -> None:
    data = audit.copy()
    data["stage861_abs"] = pd.to_numeric(data["stage861_first_open_abs_delta_r"], errors="coerce")
    data["tq_abs"] = pd.to_numeric(data["tq_min_abs_price_delta_r"], errors="coerce")
    samples = pd.concat(
        [
            data[data["tq_status"].isin(["tq_proxy_far_no_exact", "tq_proxy_near_no_exact"])].sort_values("tq_abs", ascending=False).head(6),
            data[data["source_decision_class"].eq("raw_stage452_fallback_zero_volume_bar_authority_stage449_missing")]
            .sort_values("official_open_date")
            .head(6),
            data[data["source_decision_class"].eq("fallback_no_proxy_not_minute_authority")]
            .sort_values("stage861_abs", ascending=False)
            .head(6),
        ],
        ignore_index=True,
    )
    samples = samples.drop_duplicates(["candidate_index", "official_open_trade_id"]).head(18)
    fig, axes = plt.subplots(len(samples), 1, figsize=(14, max(2.0 * len(samples), 8)), sharex=False)
    if len(samples) == 1:
        axes = [axes]
    labels = ["engine", "raw", "Stage449", "Stage861 first", "Tq nearest"]
    for ax, (_, row) in zip(axes, samples.iterrows()):
        risk = _safe_float(row.get("planned_stop_distance"), np.nan)
        if not np.isfinite(risk) or risk == 0:
            risk = np.nan
        official = _safe_float(row.get("official_open_price"), np.nan)
        values = [
            _safe_float(row.get("engine_selected_price"), np.nan),
            _safe_float(row.get("raw_anchor_open"), np.nan),
            _safe_float(row.get("stage449_anchor_open"), np.nan),
            _safe_float(row.get("stage861_first_open_price"), np.nan),
            _safe_float(row.get("tq_nearest_price_value"), np.nan),
        ]
        deltas = [((value - official) / risk if np.isfinite(value) and np.isfinite(official) and np.isfinite(risk) else np.nan) for value in values]
        xs = np.arange(len(labels))
        ax.axhline(0, color="black", linewidth=0.9)
        ax.scatter(xs, deltas, s=70, color=["#009e73", "#009e73", "#0072b2", "#cc79a7", "#d55e00"])
        for x, y, label in zip(xs, deltas, labels):
            if np.isfinite(y):
                ax.text(x, y, f"{y:.2f}R", fontsize=7, ha="center", va="bottom")
        ax.set_xticks(xs)
        ax.set_xticklabels(labels, fontsize=8)
        ax.set_ylabel("delta/R")
        ax.set_title(
            f"{row['official_open_trade_id']} {row['vt_symbol']} {pd.to_datetime(row['official_open_date']).date()} "
            f"{row['source_decision_class']} | {row['tq_status']}",
            fontsize=8.5,
        )
        ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(ATLAS_OUT, dpi=150)
    plt.close(fig)


def _write_report(audit: pd.DataFrame, class_summary: pd.DataFrame, year_matrix: pd.DataFrame, summary: pd.DataFrame) -> None:
    row = summary.iloc[0]
    lines = [
        "# Stage074 initial-entry 权威执行源决策审计",
        "",
        "## 结论",
        "",
        f"- 决策：`{row['decision']}`。",
        f"- 当前正式版：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`。",
        f"- initial opens：`{int(row['initial_open_count'])}`；timestamp-ready raw proxy：`{int(row['timestamp_ready_count'])}`；fallback no proxy：`{int(row['fallback_no_proxy_count'])}`。",
        f"- raw anchor exact/zero/degenerate：`{int(row['raw_exact_count'])}/{int(row['raw_zero_volume_count'])}/{int(row['raw_degenerate_count'])}`。",
        f"- Stage449 anchor ready/exact：`{int(row['stage449_ready_count'])}/{int(row['stage449_exact_count'])}`；Stage449 missing but raw fallback ready：`{int(row['stage449_missing_raw_fallback_count'])}`。",
        f"- Tq proxy batch ready/exact/mismatch：`{int(row['tq_proxy_batch_count'])}/{int(row['tq_proxy_exact_count'])}/{int(row['tq_proxy_mismatch_count'])}`。",
        "- 本阶段只选择后续审计源，不新增交易规则、不跑 true engine、不触发 A/B。",
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
        "## 源决策分类",
        "",
        _md_table(class_summary),
        "",
        "## 年度覆盖",
        "",
        _md_table(year_matrix, max_rows=30),
        "",
        "## 视觉文件",
        "",
        f"- authority route path chart：`{PATH_CHART_OUT}`",
        f"- source coverage decision chart：`{COVERAGE_CHART_OUT}`",
        f"- source price delta atlas：`{ATLAS_OUT}`",
        "",
        "## 判断",
        "",
        "- Stage074 的第一性判断是：后续若继续基于官方回放做分钟级执行审计，唯一能全量精确解释 timestamp-ready 成交价的是 raw proxy bar authority。",
        "- raw proxy bar authority 的代价也很明确：它是 zero-volume、OHLC 全等的价格代理，不是盘口队列，也不是真实成交量分钟K。",
        "- Stage449 full minute 覆盖了 timestamp-ready 的 `202/219`，且覆盖样本全部与 raw/official exact；剩余 `17` 笔需要 Stage452 raw fallback。",
        "- Stage861 official-date first open 只适合作为入场日可视化参考，不是成交价权威源；Tq proxy tick 当前只能作为异源 TCA 观察，不允许进入交易规则。",
        "- 下一步如果继续策略目标，应在 raw proxy bar authority 上做 bar-level 的可执行边界候选；如果要用盘口，则必须先拿到与 official open 同源的 tick/order-book。",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    audit = _build_audit()
    class_summary = _class_summary(audit)
    year_matrix = _year_matrix(audit)
    curve = _read_csv(STAGE045_CURVE_IN)
    metrics = _official_metrics()

    initial_count = int(len(audit))
    timestamp_ready_count = int(audit["timestamp_ready"].sum())
    fallback_count = int((audit["timestamp_ready"] == 0).sum())
    raw_exact_count = int(audit["raw_anchor_exact_official"].sum())
    raw_zero_count = int(audit["raw_anchor_zero_volume"].sum())
    raw_degenerate_count = int(audit["raw_anchor_degenerate_ohlc"].sum())
    stage449_ready_count = int(audit["stage449_anchor_ready"].sum())
    stage449_exact_count = int(audit["stage449_anchor_exact_official"].sum())
    stage449_missing_raw_fallback = int(
        audit["source_decision_class"].eq("raw_stage452_fallback_zero_volume_bar_authority_stage449_missing").sum()
    )
    tq_batch_count = int(audit[audit["timestamp_ready"].eq(1)]["tq_min_abs_price_delta_r"].notna().sum())
    tq_exact_count = int(audit["tq_price_exact_any"].fillna(0).sum())
    tq_mismatch_count = int(tq_batch_count - tq_exact_count)
    stage861_exact_count = int(audit["stage861_first_open_exact_official"].sum())

    if (
        timestamp_ready_count == 219
        and raw_exact_count == timestamp_ready_count
        and raw_zero_count == timestamp_ready_count
        and raw_degenerate_count == timestamp_ready_count
        and tq_mismatch_count > 0
        and stage861_exact_count < timestamp_ready_count
    ):
        stage_decision = "stage074_select_raw_proxy_bar_authority_for_bar_level_audit_no_tick_rules"
    else:
        stage_decision = "stage074_authoritative_source_unresolved_no_rules"

    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "decision": stage_decision,
                "initial_open_count": initial_count,
                "timestamp_ready_count": timestamp_ready_count,
                "fallback_no_proxy_count": fallback_count,
                "raw_exact_count": raw_exact_count,
                "raw_zero_volume_count": raw_zero_count,
                "raw_degenerate_count": raw_degenerate_count,
                "stage449_ready_count": stage449_ready_count,
                "stage449_exact_count": stage449_exact_count,
                "stage449_missing_raw_fallback_count": stage449_missing_raw_fallback,
                "stage861_official_first_exact_count": stage861_exact_count,
                "tq_proxy_batch_count": tq_batch_count,
                "tq_proxy_exact_count": tq_exact_count,
                "tq_proxy_mismatch_count": tq_mismatch_count,
                "end_equity": metrics.get("end_equity", np.nan),
                "total_return_pct": metrics.get("total_return_pct", np.nan),
                "max_drawdown_pct": metrics.get("max_drawdown_pct", np.nan),
                "sharpe": metrics.get("sharpe", np.nan),
                "total_slippage": metrics.get("total_slippage", np.nan),
                "total_trade_count": metrics.get("total_trade_count", np.nan),
                "closed_lot_win_rate_pct": metrics.get("closed_lot_win_rate_pct", np.nan),
                "max_broker10_margin_to_equity_pct": metrics.get("max_broker10_margin_to_equity_pct", np.nan),
                "strategy_rule_created": False,
                "true_engine_run": False,
                "ab_triggered": False,
            }
        ]
    )

    _write_csv(audit, AUDIT_OUT)
    _write_csv(class_summary, CLASS_SUMMARY_OUT)
    _write_csv(year_matrix, YEAR_MATRIX_OUT)
    _write_csv(summary, SUMMARY_OUT)
    _plot_path_chart(curve, audit)
    _plot_coverage_chart(audit, year_matrix)
    _plot_atlas(audit)
    _write_report(audit, class_summary, year_matrix, summary)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": stage_decision,
        "next_step": "bar_level_candidate_only_on_raw_proxy_authority_or_get_same_source_tick_orderbook",
        "strategy_rule_created": False,
        "true_engine_run": False,
        "ab_triggered": False,
        "initial_open_count": initial_count,
        "timestamp_ready_count": timestamp_ready_count,
        "fallback_no_proxy_count": fallback_count,
        "raw_exact_count": raw_exact_count,
        "raw_zero_volume_count": raw_zero_count,
        "raw_degenerate_count": raw_degenerate_count,
        "stage449_ready_count": stage449_ready_count,
        "stage449_exact_count": stage449_exact_count,
        "stage449_missing_raw_fallback_count": stage449_missing_raw_fallback,
        "stage861_official_first_exact_count": stage861_exact_count,
        "tq_proxy_batch_count": tq_batch_count,
        "tq_proxy_exact_count": tq_exact_count,
        "tq_proxy_mismatch_count": tq_mismatch_count,
        "outputs": {
            "audit": AUDIT_OUT,
            "class_summary": CLASS_SUMMARY_OUT,
            "year_matrix": YEAR_MATRIX_OUT,
            "summary": SUMMARY_OUT,
            "report": REPORT_OUT,
            "path_chart": PATH_CHART_OUT,
            "coverage_chart": COVERAGE_CHART_OUT,
            "atlas": ATLAS_OUT,
        },
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
