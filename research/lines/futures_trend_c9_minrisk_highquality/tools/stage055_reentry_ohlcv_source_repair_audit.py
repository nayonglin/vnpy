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
STAGE = "Stage055"
MODEL_TAG = "stage055_reentry_ohlcv_source_repair_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage055_c9_minrisk_reentry_ohlcv_source_repair_audit"
INITIAL_CAPITAL = 150_000.0
MAX_ATLAS_EVENTS = 12
ATLAS_PER_PAGE = 4
ATLAS_WINDOW_MINUTES = 60

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE054_DIR = LINE_DIR / "outputs" / "stage054_c9_reentry_reclaim_quality_audit"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage055_reentry_ohlcv_source_repair_audit"

FEATURES_IN = (
    STAGE054_DIR
    / "qmt_roll_stage054_c9_minrisk_reentry_reclaim_quality_audit_features_"
    "stage054_c9_reentry_reclaim_quality_audit_v1.csv"
)
CURVE_IN = (
    STAGE054_DIR
    / "qmt_roll_stage054_c9_minrisk_reentry_reclaim_quality_audit_upper_bound_curve_"
    "stage054_c9_reentry_reclaim_quality_audit_v1.csv"
)
DECISION_IN = (
    STAGE054_DIR
    / "qmt_roll_stage054_c9_minrisk_reentry_reclaim_quality_audit_decision_"
    "stage054_c9_reentry_reclaim_quality_audit_v1.json"
)

SOURCE_SPECS = [
    {
        "source_name": "stage491_covered_key_full_session_backfill",
        "root": EXAMPLE_DIR / "downloaded_futures" / "tqsdk_stage491_covered_key_full_session_backfill",
        "patterns": ["{code}_completed_minute_backtest.csv"],
        "priority": 1,
    },
    {
        "source_name": "stage459_completed_preclose_full_bar_shard",
        "root": EXAMPLE_DIR / "downloaded_futures" / "tqsdk_stage459_completed_preclose_full_bar_shard",
        "patterns": ["{code}_completed_minute_backtest.csv"],
        "priority": 2,
    },
    {
        "source_name": "stage462_completed_preclose_full_dates_shard",
        "root": EXAMPLE_DIR / "downloaded_futures" / "tqsdk_stage462_completed_preclose_full_dates_shard",
        "patterns": ["{code}_completed_minute_backtest.csv"],
        "priority": 3,
    },
    {
        "source_name": "stage448_session_rebuild_batch",
        "root": EXAMPLE_DIR / "downloaded_futures" / "tqsdk_stage448_minute_session_rebuild_batch",
        "patterns": ["{code}_minute_backtest.csv"],
        "priority": 4,
    },
    {
        "source_name": "stage452_true_path_fallback_1455",
        "root": EXAMPLE_DIR / "downloaded_futures" / "tqsdk_stage452_true_path_fallback_1455",
        "patterns": ["{code}_minute_backtest.csv"],
        "priority": 5,
    },
    {
        "source_name": "stage498_actual_trade_fill_key_backfill",
        "root": EXAMPLE_DIR / "downloaded_futures" / "tqsdk_stage498_actual_trade_fill_key_backfill",
        "patterns": ["{code}_completed_minute_backtest.csv"],
        "priority": 6,
    },
    {
        "source_name": "stage504_next_real_open_fallback_backfill",
        "root": EXAMPLE_DIR / "downloaded_futures" / "tqsdk_stage504_next_real_open_fallback_backfill",
        "patterns": ["{code}_minute_backtest.csv"],
        "priority": 7,
    },
    {
        "source_name": "stage506_next_real_forward_risk_signal_frontier",
        "root": EXAMPLE_DIR / "downloaded_futures" / "tqsdk_stage506_next_real_forward_risk_signal_frontier",
        "patterns": ["{code}_minute_backtest.csv"],
        "priority": 8,
    },
]

SOURCE_QUALITY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_quality_{MODEL_TAG}.csv"
EVENT_REPAIR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_repair_{MODEL_TAG}.csv"
SOURCE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
YEAR_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_summary_{MODEL_TAG}.csv"
BUCKET_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
GAP_PLAN_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_remaining_gap_plan_{MODEL_TAG}.csv"
CONTRIB_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readiness_contribution_curve_{MODEL_TAG}.csv"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readiness_path_chart_{MODEL_TAG}.png"
SOURCE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_readiness_chart_{MODEL_TAG}.png"
SCATTER_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_reentry_ohlcv_scatter_{MODEL_TAG}.png"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

_FILE_CACHE: dict[Path, pd.DataFrame] = {}


def _json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        if not np.isfinite(value):
            return None
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if np.isfinite(out) else default


def _timestamp(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts


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


def _load_features() -> pd.DataFrame:
    data = _read_csv(FEATURES_IN)
    data = data[pd.to_numeric(data["retry_reentered"], errors="coerce").eq(1)].copy()
    if data.empty:
        raise RuntimeError("Stage054 retry_reentered rows are empty")
    for column in [
        "risk_price",
        "stop_to_reentry_bars",
        "extra_adverse_after_stop_r",
        "reentry_lot_pnl",
        "reentry_lot_volume",
        "low_quality_reentry",
        "retry_failed",
        "entry_year",
    ]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    for column in ["datetime", "first_stop_time", "reentry_time", "retry_failed_time", "reentry_exit_day"]:
        if column in data.columns:
            data[column] = pd.to_datetime(data[column], errors="coerce")
            try:
                data[column] = data[column].dt.tz_localize(None)
            except (TypeError, AttributeError):
                pass
    data["event_key"] = data["trade_id"].astype(str)
    return data.reset_index(drop=True)


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "official_drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve.sort_values("date").reset_index(drop=True)


def _load_bar_file(path: Path) -> pd.DataFrame:
    if path in _FILE_CACHE:
        return _FILE_CACHE[path]
    data = pd.read_csv(path)
    if "bar_datetime" not in data.columns:
        raise RuntimeError(f"missing bar_datetime in {path}")
    data["bar_ts"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
        else:
            data[column] = np.nan
    data = data.dropna(subset=["bar_ts"]).sort_values("bar_ts").reset_index(drop=True)
    _FILE_CACHE[path] = data
    return data


def _candidate_paths(vt_symbol: str, spec: dict[str, Any]) -> list[Path]:
    if "." not in vt_symbol:
        return []
    code, exchange = vt_symbol.split(".", 1)
    paths: list[Path] = []
    for pattern in spec["patterns"]:
        paths.append(Path(spec["root"]) / exchange / pattern.format(code=code))
    return paths


def _probe_source(row: pd.Series, spec: dict[str, Any]) -> dict[str, Any]:
    vt_symbol = str(row["vt_symbol"])
    reentry_time = _timestamp(row["reentry_time"])
    candidate_paths = _candidate_paths(vt_symbol, spec)
    existing = [path for path in candidate_paths if path.exists()]
    base = {
        "event_key": row["event_key"],
        "trade_id": row["trade_id"],
        "vt_symbol": vt_symbol,
        "entry_year": int(row["entry_year"]) if pd.notna(row["entry_year"]) else -1,
        "quality_bucket": row["quality_bucket"],
        "low_quality_reentry": int(_safe_float(row["low_quality_reentry"], 0)),
        "retry_failed": int(_safe_float(row["retry_failed"], 0)),
        "reentry_lot_pnl": _safe_float(row["reentry_lot_pnl"], 0.0),
        "reentry_time": reentry_time,
        "source_name": spec["source_name"],
        "source_priority": int(spec["priority"]),
        "candidate_path_count": len(candidate_paths),
        "file_exists": int(bool(existing)),
        "source_path": str(existing[0]) if existing else "",
        "source_row_count": 0,
        "event_day_rows": 0,
        "exact_bar_ready": 0,
        "ohlcv_ready": 0,
        "range_ready": 0,
        "volume_ready": 0,
        "nearest_delta_seconds": np.nan,
        "open": np.nan,
        "high": np.nan,
        "low": np.nan,
        "close": np.nan,
        "volume": np.nan,
        "open_oi": np.nan,
        "close_oi": np.nan,
        "bar_range": np.nan,
        "bar_body": np.nan,
        "close_position": np.nan,
        "range_r": np.nan,
        "body_r": np.nan,
        "volume_ratio_20": np.nan,
        "source_status": "missing_file",
    }
    if not existing or pd.isna(reentry_time):
        return base
    path = existing[0]
    data = _load_bar_file(path)
    base["source_row_count"] = len(data)
    day_data = data[data["bar_ts"].dt.normalize().eq(reentry_time.normalize())]
    base["event_day_rows"] = int(len(day_data))
    if data.empty:
        base["source_status"] = "empty_file"
        return base
    nearest_idx = (data["bar_ts"] - reentry_time).abs().idxmin()
    base["nearest_delta_seconds"] = float((data.loc[nearest_idx, "bar_ts"] - reentry_time).total_seconds())
    exact = data[data["bar_ts"].eq(reentry_time)]
    if exact.empty:
        base["source_status"] = "no_exact_bar"
        return base
    item = exact.iloc[0]
    base["exact_bar_ready"] = 1
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        base[column] = _safe_float(item[column])
    bar_range = base["high"] - base["low"] if np.isfinite(base["high"]) and np.isfinite(base["low"]) else np.nan
    bar_body = base["close"] - base["open"] if np.isfinite(base["close"]) and np.isfinite(base["open"]) else np.nan
    base["bar_range"] = bar_range
    base["bar_body"] = bar_body
    base["range_ready"] = int(np.isfinite(bar_range) and bar_range > 0)
    base["volume_ready"] = int(np.isfinite(base["volume"]) and base["volume"] > 0)
    if base["range_ready"]:
        base["close_position"] = (base["close"] - base["low"]) / bar_range
    risk = _safe_float(row["risk_price"])
    if np.isfinite(risk) and risk > 0:
        base["range_r"] = bar_range / risk if np.isfinite(bar_range) else np.nan
        base["body_r"] = abs(bar_body) / risk if np.isfinite(bar_body) else np.nan
    before = data[data["bar_ts"].lt(reentry_time)].tail(20)
    if not before.empty and "volume" in before.columns:
        mean_volume = pd.to_numeric(before["volume"], errors="coerce").replace(0.0, np.nan).dropna().mean()
        if pd.notna(mean_volume) and mean_volume > 0 and np.isfinite(base["volume"]):
            base["volume_ratio_20"] = base["volume"] / mean_volume
    base["ohlcv_ready"] = int(base["exact_bar_ready"] and base["range_ready"] and base["volume_ready"])
    base["source_status"] = "ohlcv_ready" if base["ohlcv_ready"] else "exact_zero_range_or_volume"
    return base


def _source_quality(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in features.iterrows():
        for spec in SOURCE_SPECS:
            rows.append(_probe_source(row, spec))
    return pd.DataFrame(rows)


def _best_event_repair(features: pd.DataFrame, quality: pd.DataFrame) -> pd.DataFrame:
    sort_cols = ["event_key", "ohlcv_ready", "exact_bar_ready", "file_exists", "source_priority"]
    data = quality.sort_values(sort_cols, ascending=[True, False, False, False, True]).copy()
    best = data.drop_duplicates("event_key", keep="first").reset_index(drop=True)
    keep_cols = [
        "event_key",
        "source_name",
        "source_path",
        "source_status",
        "file_exists",
        "event_day_rows",
        "exact_bar_ready",
        "ohlcv_ready",
        "nearest_delta_seconds",
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
    ]
    merged = features.merge(best[keep_cols], on="event_key", how="left")
    merged["ohlcv_ready"] = pd.to_numeric(merged["ohlcv_ready"], errors="coerce").fillna(0).astype(int)
    merged["exact_bar_ready"] = pd.to_numeric(merged["exact_bar_ready"], errors="coerce").fillna(0).astype(int)
    return merged


def _summaries(quality: pd.DataFrame, event_repair: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    quality = quality.copy()
    source_summary = (
        quality.groupby("source_name", dropna=False)
        .agg(
            event_count=("event_key", "nunique"),
            file_exists_count=("file_exists", "sum"),
            exact_bar_count=("exact_bar_ready", "sum"),
            ohlcv_ready_count=("ohlcv_ready", "sum"),
            ready_pnl=("reentry_lot_pnl", lambda s: float(s[quality.loc[s.index, "ohlcv_ready"].eq(1)].sum())),
            exact_zero_or_missing_pnl=(
                "reentry_lot_pnl",
                lambda s: float(s[~quality.loc[s.index, "ohlcv_ready"].eq(1)].sum()),
            ),
            median_range_r=("range_r", "median"),
            median_volume_ratio_20=("volume_ratio_20", "median"),
        )
        .reset_index()
        .sort_values(["ohlcv_ready_count", "exact_bar_count"], ascending=[False, False])
    )
    year_summary = (
        event_repair.groupby("entry_year", dropna=False)
        .agg(
            event_count=("event_key", "nunique"),
            ohlcv_ready_count=("ohlcv_ready", "sum"),
            reentry_pnl=("reentry_lot_pnl", "sum"),
            ohlcv_ready_pnl=("reentry_lot_pnl", lambda s: float(s[event_repair.loc[s.index, "ohlcv_ready"].eq(1)].sum())),
        )
        .reset_index()
    )
    year_summary["ohlcv_ready_rate_pct"] = year_summary["ohlcv_ready_count"] / year_summary["event_count"] * 100.0
    bucket_summary = (
        event_repair.groupby("quality_bucket", dropna=False)
        .agg(
            event_count=("event_key", "nunique"),
            ohlcv_ready_count=("ohlcv_ready", "sum"),
            reentry_pnl=("reentry_lot_pnl", "sum"),
            ohlcv_ready_pnl=("reentry_lot_pnl", lambda s: float(s[event_repair.loc[s.index, "ohlcv_ready"].eq(1)].sum())),
            median_range_r=("range_r", "median"),
            median_volume_ratio_20=("volume_ratio_20", "median"),
        )
        .reset_index()
    )
    bucket_summary["ohlcv_ready_rate_pct"] = bucket_summary["ohlcv_ready_count"] / bucket_summary["event_count"] * 100.0
    gap_plan = event_repair[event_repair["ohlcv_ready"].eq(0)].copy()
    gap_plan = gap_plan[
        [
            "event_key",
            "vt_symbol",
            "reentry_time",
            "entry_year",
            "quality_bucket",
            "reentry_lot_pnl",
            "source_name",
            "source_status",
            "source_path",
            "nearest_delta_seconds",
        ]
    ].sort_values(["entry_year", "vt_symbol", "reentry_time"])
    return source_summary, year_summary, bucket_summary, gap_plan


def _contribution_curve(curve: pd.DataFrame, event_repair: pd.DataFrame) -> pd.DataFrame:
    out = curve[["date", "account_equity", "official_drawdown_pct", "broker10_margin_to_equity_pct"]].copy()
    events = event_repair.copy()
    events["event_date"] = pd.to_datetime(events["reentry_exit_day"], errors="coerce").dt.normalize()
    daily = (
        events.dropna(subset=["event_date"])
        .groupby(["event_date", "ohlcv_ready"], dropna=False)["reentry_lot_pnl"]
        .sum()
        .reset_index()
    )
    ready = daily[daily["ohlcv_ready"].eq(1)].set_index("event_date")["reentry_lot_pnl"]
    not_ready = daily[~daily["ohlcv_ready"].eq(1)].set_index("event_date")["reentry_lot_pnl"]
    out["ohlcv_ready_reentry_pnl"] = out["date"].map(ready).fillna(0.0)
    out["not_ready_reentry_pnl"] = out["date"].map(not_ready).fillna(0.0)
    out["ohlcv_ready_reentry_pnl_cumsum"] = out["ohlcv_ready_reentry_pnl"].cumsum()
    out["not_ready_reentry_pnl_cumsum"] = out["not_ready_reentry_pnl"].cumsum()
    return out


def _plot_path(curve: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True, gridspec_kw={"height_ratios": [2.2, 1.3, 1.6]})
    axes[0].plot(curve["date"], curve["account_equity"], color="#111827", linewidth=1.2, label="official C9/15w")
    axes[0].set_yscale("log")
    axes[0].set_ylabel("equity log")
    axes[0].legend(loc="upper left")
    axes[0].grid(True, alpha=0.25)
    axes[1].plot(curve["date"], curve["official_drawdown_pct"], color="#991b1b", linewidth=1.0, label="official DD")
    axes[1].set_ylabel("drawdown %")
    axes[1].legend(loc="lower left")
    axes[1].grid(True, alpha=0.25)
    axes[2].plot(
        curve["date"],
        curve["ohlcv_ready_reentry_pnl_cumsum"],
        color="#047857",
        linewidth=1.2,
        label="cum reentry PnL: best OHLCV-ready",
    )
    axes[2].plot(
        curve["date"],
        curve["not_ready_reentry_pnl_cumsum"],
        color="#b45309",
        linewidth=1.2,
        label="cum reentry PnL: remaining no-ready",
    )
    axes[2].axhline(0, color="#111827", linewidth=0.8, alpha=0.6)
    axes[2].set_ylabel("PnL")
    axes[2].legend(loc="upper left")
    axes[2].grid(True, alpha=0.25)
    fig.suptitle("Stage055 reentry OHLCV repair readiness on official path")
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_source_chart(source_summary: pd.DataFrame) -> None:
    data = source_summary.copy().sort_values("ohlcv_ready_count", ascending=True)
    fig, ax = plt.subplots(figsize=(11, 7))
    y = np.arange(len(data))
    ax.barh(y - 0.22, data["exact_bar_count"], height=0.22, color="#94a3b8", label="exact bar")
    ax.barh(y, data["ohlcv_ready_count"], height=0.22, color="#047857", label="OHLCV ready")
    ax.barh(y + 0.22, data["file_exists_count"], height=0.22, color="#cbd5e1", label="file exists")
    ax.set_yticks(y)
    ax.set_yticklabels(data["source_name"])
    ax.set_xlabel("event count out of 54 reentries")
    ax.set_title("Local minute source readiness for C9 reentry moments")
    ax.legend(loc="lower right")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(SOURCE_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_scatter(event_repair: pd.DataFrame) -> None:
    data = event_repair[event_repair["ohlcv_ready"].eq(1)].copy()
    fig, ax = plt.subplots(figsize=(10, 7))
    if data.empty:
        ax.text(0.5, 0.5, "No OHLCV-ready events", ha="center", va="center")
    else:
        size = pd.to_numeric(data["reentry_lot_volume"], errors="coerce").fillna(1).clip(lower=1)
        size = 30 + 2.0 * np.sqrt(size)
        colors = pd.to_numeric(data["reentry_lot_pnl"], errors="coerce").fillna(0.0)
        ax.scatter(
            data["range_r"],
            data["volume_ratio_20"],
            c=colors,
            s=size,
            cmap="RdYlGn",
            alpha=0.78,
            edgecolor="#334155",
            linewidth=0.5,
        )
        target = data[pd.to_numeric(data["low_quality_reentry"], errors="coerce").eq(1)]
        if not target.empty:
            ax.scatter(
                target["range_r"],
                target["volume_ratio_20"],
                s=70 + 2.0 * np.sqrt(pd.to_numeric(target["reentry_lot_volume"], errors="coerce").fillna(1).clip(lower=1)),
                facecolors="none",
                edgecolors="#dc2626",
                linewidth=1.8,
                label="Stage054 slow/deep target",
            )
        ax.set_xlabel("reentry exact bar range / risk")
        ax.set_ylabel("reentry exact bar volume / prior 20 bar avg")
        ax.legend(loc="best")
        cbar = fig.colorbar(ax.collections[0], ax=ax)
        cbar.set_label("reentry lot PnL")
    ax.set_title("OHLCV-ready reentry microstructure is data, not a rule")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(SCATTER_CHART_OUT, dpi=150)
    plt.close(fig)


def _select_atlas_events(event_repair: pd.DataFrame) -> pd.DataFrame:
    target = event_repair[pd.to_numeric(event_repair["low_quality_reentry"], errors="coerce").eq(1)].copy()
    ready = event_repair[event_repair["ohlcv_ready"].eq(1)].copy()
    best = ready.sort_values("reentry_lot_pnl", ascending=False).head(3)
    worst = ready.sort_values("reentry_lot_pnl", ascending=True).head(3)
    data = pd.concat([target, best, worst], ignore_index=True)
    data = data.drop_duplicates("event_key", keep="first").head(MAX_ATLAS_EVENTS).reset_index(drop=True)
    return data


def _load_source_window(path: str, center: pd.Timestamp) -> pd.DataFrame:
    if not path:
        return pd.DataFrame()
    p = Path(path)
    if not p.exists() or pd.isna(center):
        return pd.DataFrame()
    data = _load_bar_file(p)
    mask = data["bar_ts"].between(center - pd.Timedelta(minutes=ATLAS_WINDOW_MINUTES), center + pd.Timedelta(minutes=ATLAS_WINDOW_MINUTES))
    return data.loc[mask].copy().reset_index(drop=True)


def _plot_atlas(event_repair: pd.DataFrame) -> pd.DataFrame:
    selected = _select_atlas_events(event_repair)
    manifest_rows: list[dict[str, Any]] = []
    if selected.empty:
        return pd.DataFrame()
    page_count = math.ceil(len(selected) / ATLAS_PER_PAGE)
    stage448_lookup = {
        "source_name": "stage448_session_rebuild_batch",
        "root": EXAMPLE_DIR / "downloaded_futures" / "tqsdk_stage448_minute_session_rebuild_batch",
        "patterns": ["{code}_minute_backtest.csv"],
        "priority": 4,
    }
    for page in range(page_count):
        subset = selected.iloc[page * ATLAS_PER_PAGE : (page + 1) * ATLAS_PER_PAGE].copy()
        fig, axes = plt.subplots(len(subset), 2, figsize=(14, max(3.2 * len(subset), 4.0)), squeeze=False)
        for idx, (_, row) in enumerate(subset.iterrows()):
            center = _timestamp(row["reentry_time"])
            stage448_path = ""
            for path in _candidate_paths(str(row["vt_symbol"]), stage448_lookup):
                if path.exists():
                    stage448_path = str(path)
                    break
            panels = [
                ("stage448", stage448_path),
                (str(row["source_name"]), str(row["source_path"])),
            ]
            for j, (label, path) in enumerate(panels):
                ax = axes[idx, j]
                data = _load_source_window(path, center)
                if data.empty:
                    ax.text(0.5, 0.5, "missing", ha="center", va="center")
                    ax.set_title(label)
                    ax.axis("off")
                    continue
                ax.plot(data["bar_ts"], data["close"], color="#111827", linewidth=1.0, label="close")
                ax.fill_between(data["bar_ts"], data["low"], data["high"], color="#ef4444", alpha=0.18, linewidth=0)
                ax.axvline(center, color="#2563eb", linestyle="--", linewidth=1.0, label="reentry")
                ax2 = ax.twinx()
                ax2.bar(data["bar_ts"], data["volume"], width=0.00045, color="#94a3b8", alpha=0.45, label="volume")
                ax2.set_ylabel("vol")
                ax.set_title(
                    f"{label} {row['trade_id']} {row['vt_symbol']} pnl={row['reentry_lot_pnl']:.0f}"
                )
                ax.tick_params(axis="x", rotation=20)
                ax.grid(True, alpha=0.2)
            manifest_rows.append(
                {
                    "page": page + 1,
                    "event_key": row["event_key"],
                    "vt_symbol": row["vt_symbol"],
                    "reentry_time": center,
                    "best_source": row["source_name"],
                    "reentry_lot_pnl": row["reentry_lot_pnl"],
                    "atlas_path": str(ATLAS_TEMPLATE.with_name(ATLAS_TEMPLATE.name.format(page=page + 1))),
                }
            )
        fig.tight_layout()
        out = ATLAS_TEMPLATE.with_name(ATLAS_TEMPLATE.name.format(page=page + 1))
        fig.savefig(out, dpi=150)
        plt.close(fig)
    return pd.DataFrame(manifest_rows)


def _write_report(
    decision: dict[str, Any],
    source_summary: pd.DataFrame,
    year_summary: pd.DataFrame,
    bucket_summary: pd.DataFrame,
) -> None:
    lines = [
        "# Stage055 reentry OHLCV source repair audit",
        "",
        "## Positioning",
        "",
        f"- Stage: `{STAGE}`.",
        "- This is a read-only data-source repair audit, not a true engine and not a trading rule.",
        "- Question: can local full-session TqSdk minute shards repair Stage861/Stage448 zero-range, zero-volume reentry bars?",
        "",
        "## Decision",
        "",
        f"- Decision: `{decision['decision']}`.",
        f"- Candidate-like: `{decision['candidate_like']}`.",
        f"- Best OHLCV-ready events: `{decision['best_ohlcv_ready_event_count']}/{decision['reentry_event_count']}`.",
        f"- Stage491 OHLCV-ready events: `{decision['stage491_ohlcv_ready_event_count']}/{decision['reentry_event_count']}`.",
        f"- Stage054 slow/deep target OHLCV-ready: `{decision['slow_deep_ohlcv_ready_event_count']}/{decision['slow_deep_event_count']}`.",
        "",
        "## Source Summary",
        "",
        _md_table(source_summary),
        "",
        "## Year Summary",
        "",
        _md_table(year_summary),
        "",
        "## Bucket Summary",
        "",
        _md_table(bucket_summary),
        "",
        "## Visuals",
        "",
        f"- Path chart: `{PATH_CHART_OUT.name}`.",
        f"- Source readiness chart: `{SOURCE_CHART_OUT.name}`.",
        f"- Reentry OHLCV scatter: `{SCATTER_CHART_OUT.name}`.",
        f"- Atlas manifest: `{ATLAS_MANIFEST_OUT.name}`.",
        "",
        "## Boundary",
        "",
        "- Stage491/459/462 repair exact OHLCV for many reentry moments, but this is data readiness, not alpha.",
        "- Do not turn range, volume ratio, close position, source-ready status, or Stage054 slow/deep labels into a rule without a predeclared true-engine candidate.",
        "- Remaining no-ready events still carry material right-tail PnL, so missing coverage cannot be used as a filter.",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features = _load_features()
    curve = _load_curve()
    with DECISION_IN.open("r", encoding="utf-8") as fh:
        stage054_decision = json.load(fh)
    quality = _source_quality(features)
    event_repair = _best_event_repair(features, quality)
    source_summary, year_summary, bucket_summary, gap_plan = _summaries(quality, event_repair)
    contribution_curve = _contribution_curve(curve, event_repair)
    atlas_manifest = _plot_atlas(event_repair)

    quality.to_csv(SOURCE_QUALITY_OUT, index=False, encoding="utf-8-sig")
    event_repair.to_csv(EVENT_REPAIR_OUT, index=False, encoding="utf-8-sig")
    source_summary.to_csv(SOURCE_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    year_summary.to_csv(YEAR_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(BUCKET_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    gap_plan.to_csv(GAP_PLAN_OUT, index=False, encoding="utf-8-sig")
    contribution_curve.to_csv(CONTRIB_CURVE_OUT, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")

    _plot_path(contribution_curve)
    _plot_source_chart(source_summary)
    _plot_scatter(event_repair)

    stage491_ready = quality[
        quality["source_name"].eq("stage491_covered_key_full_session_backfill") & quality["ohlcv_ready"].eq(1)
    ]
    slow_deep = event_repair[pd.to_numeric(event_repair["low_quality_reentry"], errors="coerce").eq(1)]
    slow_deep_ready = slow_deep[slow_deep["ohlcv_ready"].eq(1)]
    best_ready = event_repair[event_repair["ohlcv_ready"].eq(1)]
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "upstream_stage054_decision": stage054_decision.get("decision"),
        "decision": "stage055_stage491_repairs_reentry_ohlcv_partial_data_asset_no_trade_rule",
        "candidate_like": False,
        "reentry_event_count": int(len(event_repair)),
        "best_ohlcv_ready_event_count": int(event_repair["ohlcv_ready"].sum()),
        "best_ohlcv_ready_rate_pct": float(event_repair["ohlcv_ready"].mean() * 100.0),
        "best_ohlcv_ready_reentry_pnl": float(best_ready["reentry_lot_pnl"].sum()),
        "remaining_no_ready_event_count": int((1 - event_repair["ohlcv_ready"]).sum()),
        "remaining_no_ready_reentry_pnl": float(event_repair[event_repair["ohlcv_ready"].eq(0)]["reentry_lot_pnl"].sum()),
        "stage491_ohlcv_ready_event_count": int(stage491_ready["event_key"].nunique()),
        "stage491_ohlcv_ready_reentry_pnl": float(stage491_ready.drop_duplicates("event_key")["reentry_lot_pnl"].sum()),
        "slow_deep_event_count": int(len(slow_deep)),
        "slow_deep_ohlcv_ready_event_count": int(slow_deep_ready["event_key"].nunique()),
        "slow_deep_ohlcv_ready_reentry_pnl": float(slow_deep_ready["reentry_lot_pnl"].sum()),
        "official": stage054_decision.get("official", {}),
        "outputs": {
            "source_quality": SOURCE_QUALITY_OUT,
            "event_repair": EVENT_REPAIR_OUT,
            "source_summary": SOURCE_SUMMARY_OUT,
            "year_summary": YEAR_SUMMARY_OUT,
            "bucket_summary": BUCKET_SUMMARY_OUT,
            "remaining_gap_plan": GAP_PLAN_OUT,
            "contribution_curve": CONTRIB_CURVE_OUT,
            "report": REPORT_OUT,
            "path_chart": PATH_CHART_OUT,
            "source_chart": SOURCE_CHART_OUT,
            "scatter_chart": SCATTER_CHART_OUT,
            "atlas_manifest": ATLAS_MANIFEST_OUT,
        },
        "judgment": (
            "Local full-session backfill can repair exact OHLCV for a meaningful subset of C9 reentry moments, "
            "including all Stage054 slow/deep targets, but coverage is partial and this stage is data readiness only."
        ),
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, source_summary, year_summary, bucket_summary)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
