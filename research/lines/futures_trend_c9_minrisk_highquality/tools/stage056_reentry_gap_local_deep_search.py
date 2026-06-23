from __future__ import annotations

from datetime import timedelta
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage056"
MODEL_TAG = "stage056_reentry_gap_local_deep_search_v1"
OUTPUT_PREFIX = "qmt_roll_stage056_c9_minrisk_reentry_gap_local_deep_search"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
DOWNLOADED_DIR = EXAMPLE_DIR / "downloaded_futures"
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE054_DIR = LINE_DIR / "outputs" / "stage054_c9_reentry_reclaim_quality_audit"
STAGE055_DIR = LINE_DIR / "outputs" / "stage055_reentry_ohlcv_source_repair_audit"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage056_reentry_gap_local_deep_search"

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
CURVE_IN = (
    STAGE054_DIR
    / "qmt_roll_stage054_c9_minrisk_reentry_reclaim_quality_audit_upper_bound_curve_"
    "stage054_c9_reentry_reclaim_quality_audit_v1.csv"
)

SOURCE_SCAN_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_scan_{MODEL_TAG}.csv"
EVENT_BEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_best_{MODEL_TAG}.csv"
SOURCE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
DOWNLOAD_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_download_manifest_{MODEL_TAG}.csv"
CONTRIB_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_contribution_curve_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_path_chart_{MODEL_TAG}.png"
SOURCE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_gap_chart_{MODEL_TAG}.png"
EVENT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_gap_chart_{MODEL_TAG}.png"


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


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _timestamp(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts


def _source_root(path: Path) -> str:
    try:
        relative = path.relative_to(DOWNLOADED_DIR)
    except ValueError:
        return "unknown"
    return relative.parts[0] if relative.parts else "downloaded_futures"


def _tq_symbol(vt_symbol: str) -> str:
    code, exchange = vt_symbol.split(".", 1)
    return f"{exchange}.{code}"


def _session_download_window(event_ts: pd.Timestamp) -> tuple[str, str]:
    if pd.isna(event_ts):
        return "", ""
    start = (event_ts - timedelta(days=1)).replace(hour=20, minute=30, second=0, microsecond=0)
    end = (event_ts + timedelta(days=1)).replace(hour=16, minute=0, second=0, microsecond=0)
    return start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")


def _load_gap_events() -> pd.DataFrame:
    events = _read_csv(STAGE055_EVENT_IN)
    for column in [
        "risk_price",
        "reentry_lot_pnl",
        "entry_year",
        "ohlcv_ready",
        "exact_bar_ready",
        "low_quality_reentry",
    ]:
        events[column] = pd.to_numeric(events[column], errors="coerce")
    events["reentry_time"] = pd.to_datetime(events["reentry_time"], errors="coerce")
    events["reentry_exit_day"] = pd.to_datetime(events["reentry_exit_day"], errors="coerce")
    gap = events[~events["ohlcv_ready"].fillna(0).astype(int).astype(bool)].copy()
    gap["code"] = gap["vt_symbol"].str.split(".").str[0]
    gap["exchange"] = gap["vt_symbol"].str.split(".").str[1]
    return gap.sort_values(["entry_year", "reentry_time", "event_key"]).reset_index(drop=True)


def _all_csv_paths() -> list[Path]:
    return sorted(DOWNLOADED_DIR.rglob("*.csv"))


def _candidate_paths_for_code(paths: list[Path], code: str) -> list[Path]:
    lowered = code.lower()
    return [path for path in paths if lowered in path.name.lower()]


def _scan_path_for_event(path: Path, event: pd.Series) -> dict[str, Any]:
    event_ts = _timestamp(event["reentry_time"])
    base: dict[str, Any] = {
        "event_key": event["event_key"],
        "vt_symbol": event["vt_symbol"],
        "reentry_time": event_ts,
        "entry_year": event["entry_year"],
        "quality_bucket": event["quality_bucket"],
        "reentry_lot_pnl": event["reentry_lot_pnl"],
        "reentry_exit_day": event.get("reentry_exit_day", pd.NaT),
        "risk_price": event["risk_price"],
        "source_root": _source_root(path),
        "source_path": str(path),
        "source_file": path.name,
        "read_error": "",
        "row_count": 0,
        "status": "unread",
        "event_day_rows": 0,
        "exact_bar_ready": 0,
        "ohlcv_ready": 0,
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
    }
    try:
        data = pd.read_csv(path)
    except Exception as exc:  # pragma: no cover - diagnostic output path
        base["status"] = "read_error"
        base["read_error"] = f"{type(exc).__name__}: {exc}"
        return base

    base["row_count"] = len(data)
    if "bar_datetime" not in data.columns:
        base["status"] = "not_minute_no_bar_datetime"
        return base
    data = data.copy()
    data["bar_ts"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    data = data.dropna(subset=["bar_ts"]).sort_values("bar_ts").reset_index(drop=True)
    if data.empty:
        base["status"] = "no_parseable_datetime"
        return base

    same_day = data["bar_ts"].dt.normalize().eq(event_ts.normalize())
    base["event_day_rows"] = int(same_day.sum())
    delta = (data["bar_ts"] - event_ts).abs()
    if delta.notna().any():
        base["nearest_delta_seconds"] = float(delta.min().total_seconds())
    exact = data.index[data["bar_ts"].eq(event_ts)]
    if len(exact) == 0:
        base["status"] = "no_exact_bar"
        return base

    idx = int(exact[0])
    row = data.loc[idx]
    base["exact_bar_ready"] = 1
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        if column in data.columns:
            base[column] = pd.to_numeric(pd.Series([row[column]]), errors="coerce").iloc[0]
    high = float(base["high"]) if pd.notna(base["high"]) else np.nan
    low = float(base["low"]) if pd.notna(base["low"]) else np.nan
    open_ = float(base["open"]) if pd.notna(base["open"]) else np.nan
    close = float(base["close"]) if pd.notna(base["close"]) else np.nan
    volume = float(base["volume"]) if pd.notna(base["volume"]) else np.nan
    risk_price = float(base["risk_price"]) if pd.notna(base["risk_price"]) else np.nan
    bar_range = high - low if np.isfinite(high) and np.isfinite(low) else np.nan
    bar_body = abs(close - open_) if np.isfinite(close) and np.isfinite(open_) else np.nan
    base["bar_range"] = bar_range
    base["bar_body"] = bar_body
    if np.isfinite(bar_range) and bar_range > 0 and np.isfinite(close):
        base["close_position"] = (close - low) / bar_range
    if np.isfinite(risk_price) and risk_price > 0:
        base["range_r"] = bar_range / risk_price if np.isfinite(bar_range) else np.nan
        base["body_r"] = bar_body / risk_price if np.isfinite(bar_body) else np.nan
    if "volume" in data.columns:
        volume_series = pd.to_numeric(data["volume"], errors="coerce")
        prev = volume_series.iloc[max(0, idx - 20) : idx]
        prev_mean = prev[prev > 0].mean()
        if pd.notna(prev_mean) and prev_mean > 0 and np.isfinite(volume):
            base["volume_ratio_20"] = volume / prev_mean
    if np.isfinite(bar_range) and bar_range > 0 and np.isfinite(volume) and volume > 0:
        base["ohlcv_ready"] = 1
        base["status"] = "exact_ohlcv_ready"
    else:
        base["status"] = "exact_zero_range_or_volume"
    return base


def _scan_sources(gap: pd.DataFrame) -> pd.DataFrame:
    paths = _all_csv_paths()
    rows: list[dict[str, Any]] = []
    for _, event in gap.iterrows():
        candidates = _candidate_paths_for_code(paths, str(event["code"]))
        if not candidates:
            rows.append(
                {
                    "event_key": event["event_key"],
                    "vt_symbol": event["vt_symbol"],
                    "reentry_time": event["reentry_time"],
                    "entry_year": event["entry_year"],
                    "quality_bucket": event["quality_bucket"],
                    "reentry_lot_pnl": event["reentry_lot_pnl"],
                    "reentry_exit_day": event.get("reentry_exit_day", pd.NaT),
                    "risk_price": event["risk_price"],
                    "source_root": "none",
                    "source_path": "",
                    "source_file": "",
                    "read_error": "",
                    "row_count": 0,
                    "status": "no_candidate_file",
                    "event_day_rows": 0,
                    "exact_bar_ready": 0,
                    "ohlcv_ready": 0,
                    "nearest_delta_seconds": np.nan,
                }
            )
            continue
        for path in candidates:
            rows.append(_scan_path_for_event(path, event))
    return pd.DataFrame(rows)


def _rank_scan_rows(scan: pd.DataFrame) -> pd.DataFrame:
    data = scan.copy()
    data["status_rank"] = np.select(
        [
            data["ohlcv_ready"].fillna(0).astype(int).eq(1),
            data["exact_bar_ready"].fillna(0).astype(int).eq(1),
            data["event_day_rows"].fillna(0).astype(int).gt(0),
            data["status"].eq("not_minute_no_bar_datetime"),
        ],
        [0, 1, 2, 5],
        default=3,
    )
    data["nearest_rank"] = pd.to_numeric(data["nearest_delta_seconds"], errors="coerce").fillna(10**12)
    data["source_path_rank"] = data["source_path"].fillna("")
    data = data.sort_values(["event_key", "status_rank", "nearest_rank", "source_path_rank"])
    best = data.groupby("event_key", as_index=False).head(1).reset_index(drop=True)
    return best.drop(columns=["status_rank", "nearest_rank", "source_path_rank"], errors="ignore")


def _source_summary(scan: pd.DataFrame) -> pd.DataFrame:
    summary = (
        scan.groupby("source_root", dropna=False)
        .agg(
            scan_rows=("event_key", "count"),
            event_count=("event_key", "nunique"),
            exact_count=("exact_bar_ready", "sum"),
            ohlcv_ready_count=("ohlcv_ready", "sum"),
            event_day_row_sum=("event_day_rows", "sum"),
        )
        .reset_index()
    )
    ready = scan[scan["ohlcv_ready"].fillna(0).astype(int).eq(1)]
    ready_pnl = ready.groupby("source_root")["reentry_lot_pnl"].sum().rename("ready_pnl")
    summary = summary.merge(ready_pnl, on="source_root", how="left")
    summary["ready_pnl"] = summary["ready_pnl"].fillna(0.0)
    return summary.sort_values(["ohlcv_ready_count", "exact_count", "event_count"], ascending=False)


def _download_manifest(best: pd.DataFrame) -> pd.DataFrame:
    unresolved = best[~best["ohlcv_ready"].fillna(0).astype(int).astype(bool)].copy()
    rows: list[dict[str, Any]] = []
    for _, row in unresolved.iterrows():
        event_ts = _timestamp(row["reentry_time"])
        start_dt, end_dt = _session_download_window(event_ts)
        code = str(row["vt_symbol"]).split(".")[0]
        rows.append(
            {
                "event_key": row["event_key"],
                "vt_symbol": row["vt_symbol"],
                "tq_symbol": _tq_symbol(row["vt_symbol"]),
                "reentry_time": event_ts,
                "entry_year": row["entry_year"],
                "quality_bucket": row["quality_bucket"],
                "reentry_lot_pnl": row["reentry_lot_pnl"],
                "current_best_status": row["status"],
                "current_best_source_root": row["source_root"],
                "current_best_source_path": row["source_path"],
                "download_start_dt": start_dt,
                "download_end_dt": end_dt,
                "primary_dur_sec": 60,
                "fallback_dur_sec": 0,
                "suggested_minute_filename": f"{code}_{event_ts:%Y%m%d}_full_session_minute.csv",
                "suggested_tick_filename": f"{code}_{event_ts:%Y%m%d}_around_reentry_tick.csv",
                "reason": "need exact reentry bar with high-low range and positive volume",
            }
        )
    return pd.DataFrame(rows)


def _contribution_curve(curve: pd.DataFrame, best: pd.DataFrame) -> pd.DataFrame:
    out = curve[["date", "account_equity", "official_drawdown_pct", "broker10_margin_to_equity_pct"]].copy()
    events = best.copy()
    events["event_day"] = pd.to_datetime(events["reentry_exit_day"], errors="coerce").dt.normalize()
    events.loc[events["event_day"].isna(), "event_day"] = pd.to_datetime(
        events.loc[events["event_day"].isna(), "reentry_time"], errors="coerce"
    ).dt.normalize()
    events["repaired_by_local_deep_search_pnl"] = np.where(
        events["ohlcv_ready"].fillna(0).astype(int).eq(1),
        events["reentry_lot_pnl"],
        0.0,
    )
    events["still_unresolved_gap_pnl"] = np.where(
        events["ohlcv_ready"].fillna(0).astype(int).eq(0),
        events["reentry_lot_pnl"],
        0.0,
    )
    daily = (
        events.groupby("event_day", dropna=False)[
            ["repaired_by_local_deep_search_pnl", "still_unresolved_gap_pnl", "reentry_lot_pnl"]
        ]
        .sum()
        .reset_index()
        .rename(columns={"event_day": "date", "reentry_lot_pnl": "remaining_gap_event_pnl"})
    )
    out = out.merge(daily, on="date", how="left")
    for column in [
        "repaired_by_local_deep_search_pnl",
        "still_unresolved_gap_pnl",
        "remaining_gap_event_pnl",
    ]:
        out[column] = out[column].fillna(0.0)
        out[f"cum_{column}"] = out[column].cumsum()
    return out


def _plot_path(curve: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=True, gridspec_kw={"height_ratios": [2, 1, 1]})
    axes[0].plot(curve["date"], curve["account_equity"], color="#1f77b4", lw=1.5, label="official equity")
    axes[0].set_yscale("log")
    axes[0].set_title("Stage056 official path with remaining reentry-gap PnL attribution")
    axes[0].set_ylabel("equity log")
    axes[0].legend(loc="upper left")

    axes[1].plot(
        curve["date"],
        curve["cum_repaired_by_local_deep_search_pnl"],
        color="#2ca02c",
        lw=1.4,
        label="cum locally repaired gap PnL",
    )
    axes[1].plot(
        curve["date"],
        curve["cum_still_unresolved_gap_pnl"],
        color="#d62728",
        lw=1.4,
        label="cum still unresolved gap PnL",
    )
    axes[1].axhline(0, color="#666666", lw=0.8)
    axes[1].set_ylabel("PnL")
    axes[1].legend(loc="upper left")

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


def _plot_source_summary(summary: pd.DataFrame) -> None:
    display = summary.head(16).copy()
    fig, ax = plt.subplots(figsize=(13, 8))
    y = np.arange(len(display))
    ax.barh(y - 0.18, display["exact_count"], height=0.35, color="#ff7f0e", label="exact bar")
    ax.barh(y + 0.18, display["ohlcv_ready_count"], height=0.35, color="#2ca02c", label="OHLCV ready")
    ax.set_yticks(y)
    ax.set_yticklabels(display["source_root"])
    ax.invert_yaxis()
    ax.set_xlabel("event-source hits")
    ax.set_title("Stage056 local downloaded_futures gap search by source root")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(SOURCE_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_event_gap(best: pd.DataFrame) -> None:
    display = best.sort_values("reentry_lot_pnl").copy()
    colors = np.where(display["ohlcv_ready"].fillna(0).astype(int).eq(1), "#2ca02c", "#d62728")
    labels = display["vt_symbol"].astype(str) + "\n" + pd.to_datetime(display["reentry_time"]).dt.strftime("%Y-%m-%d")
    fig, ax = plt.subplots(figsize=(15, 9))
    ax.bar(np.arange(len(display)), display["reentry_lot_pnl"], color=colors)
    ax.axhline(0, color="#333333", lw=0.8)
    ax.set_xticks(np.arange(len(display)))
    ax.set_xticklabels(labels, rotation=75, ha="right", fontsize=8)
    ax.set_ylabel("reentry lot PnL")
    ax.set_title("Stage056 remaining gap events: green=locally OHLCV-ready, red=still unresolved")
    fig.tight_layout()
    fig.savefig(EVENT_CHART_OUT, dpi=150)
    plt.close(fig)


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


def _write_report(decision: dict[str, Any], best: pd.DataFrame, summary: pd.DataFrame, manifest: pd.DataFrame) -> None:
    resolved = best[best["ohlcv_ready"].fillna(0).astype(int).eq(1)].copy()
    unresolved = best[best["ohlcv_ready"].fillna(0).astype(int).eq(0)].copy()
    lines = [
        "# Stage056 reentry gap local deep search report",
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- candidate_like: `{decision['candidate_like']}`",
        f"- remaining input events: `{decision['input_gap_event_count']}`",
        f"- locally repaired OHLCV events: `{decision['local_ohlcv_ready_event_count']}`",
        f"- still unresolved events: `{decision['still_unresolved_event_count']}`",
        f"- still unresolved PnL: `{decision['still_unresolved_reentry_pnl']:.2f}`",
        "",
        "## Source Summary",
        "",
        _md_table(summary[["source_root", "event_count", "exact_count", "ohlcv_ready_count", "ready_pnl"]], 20),
        "",
        "## Locally Repaired Events",
        "",
        _md_table(
            resolved[
                [
                    "event_key",
                    "vt_symbol",
                    "reentry_time",
                    "reentry_lot_pnl",
                    "source_root",
                    "status",
                    "range_r",
                    "volume_ratio_20",
                ]
            ],
            20,
        ),
        "",
        "## Still Unresolved Events",
        "",
        _md_table(
            unresolved[
                [
                    "event_key",
                    "vt_symbol",
                    "reentry_time",
                    "entry_year",
                    "reentry_lot_pnl",
                    "source_root",
                    "status",
                    "nearest_delta_seconds",
                ]
            ],
            30,
        ),
        "",
        "## Download Manifest Preview",
        "",
        _md_table(
            manifest[
                [
                    "event_key",
                    "vt_symbol",
                    "tq_symbol",
                    "reentry_time",
                    "current_best_status",
                    "download_start_dt",
                    "download_end_dt",
                    "primary_dur_sec",
                    "fallback_dur_sec",
                ]
            ],
            30,
        ),
        "",
        "## Visual Outputs",
        "",
        f"- path chart: `{PATH_CHART_OUT}`",
        f"- source chart: `{SOURCE_CHART_OUT}`",
        f"- event chart: `{EVENT_CHART_OUT}`",
        "",
        "## Judgment",
        "",
        decision["judgment"],
        "",
    ]
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    gap = _load_gap_events()
    stage055_decision = _read_json(STAGE055_DECISION_IN)
    scan = _scan_sources(gap)
    best = _rank_scan_rows(scan)
    summary = _source_summary(scan)
    manifest = _download_manifest(best)
    curve = _read_csv(CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "official_drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    contrib_curve = _contribution_curve(curve, best)

    local_ready = best[best["ohlcv_ready"].fillna(0).astype(int).eq(1)]
    unresolved = best[best["ohlcv_ready"].fillna(0).astype(int).eq(0)]
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "upstream_stage055_decision": stage055_decision.get("decision"),
        "decision": "stage056_local_deep_search_no_additional_robust_trade_rule",
        "candidate_like": False,
        "input_gap_event_count": int(len(gap)),
        "scanned_csv_file_count": int(scan["source_path"].replace("", np.nan).nunique(dropna=True)),
        "scan_row_count": int(len(scan)),
        "local_ohlcv_ready_event_count": int(len(local_ready)),
        "local_ohlcv_ready_reentry_pnl": float(local_ready["reentry_lot_pnl"].sum()),
        "still_unresolved_event_count": int(len(unresolved)),
        "still_unresolved_reentry_pnl": float(unresolved["reentry_lot_pnl"].sum()),
        "still_unresolved_positive_pnl": float(unresolved.loc[unresolved["reentry_lot_pnl"] > 0, "reentry_lot_pnl"].sum()),
        "still_unresolved_negative_pnl_abs": float(
            -unresolved.loc[unresolved["reentry_lot_pnl"] < 0, "reentry_lot_pnl"].sum()
        ),
        "top_unresolved_pnl_event": (
            unresolved.sort_values("reentry_lot_pnl", ascending=False).head(1)[
                ["event_key", "vt_symbol", "reentry_time", "reentry_lot_pnl", "status", "source_root"]
            ]
            .to_dict("records")
        ),
        "judgment": (
            "A repository-wide local CSV search is useful as a coverage audit, but any newly found "
            "or still-missing OHLCV state remains data readiness only. It must not be converted into "
            "a reentry quality rule until exact bars are complete enough and crossed with a predeclared, "
            "entry-time-visible risk source."
        ),
        "outputs": {
            "source_scan_csv": SOURCE_SCAN_OUT,
            "event_best_csv": EVENT_BEST_OUT,
            "source_summary_csv": SOURCE_SUMMARY_OUT,
            "download_manifest_csv": DOWNLOAD_MANIFEST_OUT,
            "contribution_curve_csv": CONTRIB_CURVE_OUT,
            "path_chart_png": PATH_CHART_OUT,
            "source_chart_png": SOURCE_CHART_OUT,
            "event_chart_png": EVENT_CHART_OUT,
            "decision_json": DECISION_OUT,
            "report_md": REPORT_OUT,
        },
    }

    scan.to_csv(SOURCE_SCAN_OUT, index=False, encoding="utf-8-sig")
    best.to_csv(EVENT_BEST_OUT, index=False, encoding="utf-8-sig")
    summary.to_csv(SOURCE_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    manifest.to_csv(DOWNLOAD_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    contrib_curve.to_csv(CONTRIB_CURVE_OUT, index=False, encoding="utf-8-sig")
    _plot_path(contrib_curve)
    _plot_source_summary(summary)
    _plot_event_gap(best)
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, best, summary, manifest)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
