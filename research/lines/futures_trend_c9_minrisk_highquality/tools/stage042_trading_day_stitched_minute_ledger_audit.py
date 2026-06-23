from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage042"
MODEL_TAG = "stage042_trading_day_stitched_minute_ledger_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage042_c9_minrisk_trading_day_stitched_minute_ledger_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage038_order_event_replay_prototype_audit as s038
import stage041_timestamp_ready_replay_consistency_audit as s041
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE041_DIR = LINE_DIR / "outputs" / "stage041_timestamp_ready_replay_consistency_audit"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage042_trading_day_stitched_minute_ledger_audit"

STAGE041_ALIGNMENT_IN = (
    STAGE041_DIR
    / "qmt_roll_stage041_c9_minrisk_timestamp_ready_replay_consistency_audit_timestamp_alignment_"
    "stage041_timestamp_ready_replay_consistency_audit_v1.csv"
)
STAGE041_REPLAY_IN = (
    STAGE041_DIR
    / "qmt_roll_stage041_c9_minrisk_timestamp_ready_replay_consistency_audit_replay_ledger_"
    "stage041_timestamp_ready_replay_consistency_audit_v1.csv"
)
STAGE041_SENSITIVITY_IN = (
    STAGE041_DIR
    / "qmt_roll_stage041_c9_minrisk_timestamp_ready_replay_consistency_audit_same_exit_sensitivity_curve_"
    "stage041_timestamp_ready_replay_consistency_audit_v1.csv"
)

SESSION_ORDER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_session_order_ledger_{MODEL_TAG}.csv"
SESSION_BAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stitched_bar_ledger_{MODEL_TAG}.csv"
EVENT_DIAGNOSTIC_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_diagnostic_{MODEL_TAG}.csv"
STATUS_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_status_summary_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_session_path_chart_{MODEL_TAG}.png"
TIMELINE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_session_timeline_chart_{MODEL_TAG}.png"
EVENT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_diagnostic_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

CAPITAL = 150_000.0
TRADING_DAYS_PER_YEAR = 252
ATLAS_ROWS = 12
ATLAS_PER_PAGE = 4


def _json_safe(value: Any) -> Any:
    return s041._json_safe(value)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s041._safe_float(value, default=default)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s041._md_table(frame, max_rows=max_rows)


def _time_text(value: Any) -> str:
    return s041._time_text(value)


def _hhmm(value: Any) -> str:
    return s041._hhmm(value)


def _normalize_day(value: Any) -> pd.Timestamp:
    return s038._normalize_day(value)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    return s041._drawdown_pct(equity)


def _curve_metrics(frame: pd.DataFrame, equity_col: str) -> dict[str, float]:
    return s041._curve_metrics(frame, equity_col)


def _parse_ts(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts


def _load_alignment() -> pd.DataFrame:
    data = _read_csv(STAGE041_ALIGNMENT_IN)
    for column in [
        "candidate_date",
        "official_open_date",
        "timestamp_first_time",
        "timestamp_last_time",
        "raw_first_time",
        "raw_last_time",
        "stage861_first_open_time",
        "replay_open_datetime",
        "official_first_stop_time",
        "official_reentry_time",
        "official_retry_failed_time",
        "official_hit_time",
    ]:
        if column in data.columns:
            data[f"{column}_ts"] = data[column].map(_parse_ts)
    for column in [
        "official_open_price",
        "official_open_volume",
        "candidate_selected_volume",
        "planned_stop_price",
        "planned_stop_distance",
        "event_family_match",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data.rename(columns={"event_family_match": "official_anchor_event_family_match"}, inplace=True)
    return data.reset_index(drop=True)


def _load_replay_variant(variant_id: str, prefix: str) -> pd.DataFrame:
    replay = _read_csv(STAGE041_REPLAY_IN)
    data = replay[replay["variant_id"].astype(str).eq(variant_id)].copy()
    keep = [
        "candidate_index",
        "official_open_trade_id",
        "stage861_replay_ready",
        "replay_open_datetime",
        "replay_event_family",
        "replay_first_stop_time",
        "replay_reentry_time",
        "replay_retry_failed_time",
        "replay_c2_hit_time",
        "event_family_match",
        "first_stop_time_match",
        "reentry_time_match",
        "retry_failed_time_match",
        "c2_hit_time_match",
        "replay_bar_count",
    ]
    data = data[[column for column in keep if column in data.columns]].copy()
    rename = {
        column: f"{prefix}_{column}"
        for column in data.columns
        if column not in {"candidate_index", "official_open_trade_id"}
    }
    data.rename(columns=rename, inplace=True)
    for column in data.columns:
        if column.endswith("_time") or column.endswith("_datetime"):
            data[f"{column}_ts"] = data[column].map(_parse_ts)
    return data


def _event_time(row: pd.Series, prefix: str) -> tuple[pd.Timestamp, str]:
    if prefix == "official":
        candidates = [
            ("first_stop", row.get("official_first_stop_time")),
            ("reentry", row.get("official_reentry_time")),
            ("retry_failed", row.get("official_retry_failed_time")),
            ("c2_hit", row.get("official_hit_time")),
        ]
    else:
        candidates = [
            ("first_stop", row.get(f"{prefix}_replay_first_stop_time")),
            ("reentry", row.get(f"{prefix}_replay_reentry_time")),
            ("retry_failed", row.get(f"{prefix}_replay_retry_failed_time")),
            ("c2_hit", row.get(f"{prefix}_replay_c2_hit_time")),
        ]
    parsed = [(label, _parse_ts(value)) for label, value in candidates]
    valid = [(label, ts) for label, ts in parsed if pd.notna(ts)]
    if not valid:
        return pd.NaT, ""
    label, ts = min(valid, key=lambda item: item[1])
    return ts, label


def _segment_for_bar(ts: pd.Timestamp, official_open_ts: pd.Timestamp) -> str:
    if pd.isna(ts) or pd.isna(official_open_ts):
        return "unknown"
    if ts < official_open_ts:
        if ts.hour >= 21:
            return "preofficial_night_same_calendar"
        if ts.hour < 3:
            return "preofficial_night_after_midnight"
        return "preofficial_other"
    if ts.hour < 16:
        return "official_day"
    return "postofficial_other"


def _event_in_frame(stitched: pd.DataFrame, event_ts: pd.Timestamp) -> int:
    if stitched.empty or pd.isna(event_ts):
        return 0
    return int(pd.to_datetime(stitched["bar_datetime_ts"], errors="coerce").eq(event_ts).any())


def _build_ledgers(orders: pd.DataFrame, groups: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    order_rows: list[dict[str, Any]] = []
    bar_rows: list[dict[str, Any]] = []

    for _, row in orders.iterrows():
        vt_symbol = str(row.get("vt_symbol", ""))
        bars = s041._bars_for_symbol(groups, vt_symbol)
        candidate_day = _normalize_day(row.get("candidate_date"))
        official_day = _normalize_day(row.get("official_open_date"))
        raw_ts = _parse_ts(row.get("timestamp_first_time"))
        official_open_ts = _parse_ts(row.get("replay_open_datetime"))
        if pd.isna(official_open_ts):
            official_open_ts = _parse_ts(row.get("stage861_first_open_time"))
        raw_event_ts, raw_event_type = _event_time(row, "raw")
        official_event_ts, official_event_type = _event_time(row, "official")

        official_day_bars = s041._bars_on_date(bars, official_day) if not bars.empty else pd.DataFrame()
        has_raw_bar = int(not bars.empty and pd.notna(raw_ts) and bars["bar_datetime_ts"].eq(raw_ts).any())
        has_official_open_bar = int(
            not official_day_bars.empty and pd.notna(official_open_ts) and official_day_bars["bar_datetime_ts"].eq(official_open_ts).any()
        )

        session_start = raw_ts if bool(has_raw_bar) else official_open_ts
        session_end = official_day_bars["bar_datetime_ts"].max() if not official_day_bars.empty else pd.NaT
        stitched = pd.DataFrame()
        if not bars.empty and pd.notna(session_start) and pd.notna(session_end):
            stitched = bars[
                pd.to_datetime(bars["bar_datetime_ts"], errors="coerce").ge(session_start)
                & pd.to_datetime(bars["bar_datetime_ts"], errors="coerce").le(session_end)
            ].copy()
            stitched = stitched.sort_values("bar_datetime_ts").reset_index(drop=True)

        raw_event_before_official_open = int(
            pd.notna(raw_event_ts) and pd.notna(official_open_ts) and raw_event_ts < official_open_ts
        )
        official_event_before_official_open = int(
            pd.notna(official_event_ts) and pd.notna(official_open_ts) and official_event_ts < official_open_ts
        )
        raw_event_match = int(_safe_float(row.get("raw_event_family_match"), 0.0) == 1.0)
        if not has_raw_bar:
            session_status = "missing_raw_timestamp_bar"
        elif raw_event_before_official_open and not raw_event_match:
            session_status = "raw_replay_scans_preofficial_night_mismatch"
        elif raw_event_before_official_open:
            session_status = "raw_replay_scans_preofficial_night_but_matches"
        elif not raw_event_match:
            session_status = "raw_replay_mismatch_after_official_open"
        else:
            session_status = "session_convention_consistent"

        preofficial_count = 0
        official_day_count = 0
        if not stitched.empty:
            segments = stitched["bar_datetime_ts"].map(lambda value: _segment_for_bar(value, official_open_ts))
            preofficial_count = int(segments.astype(str).str.startswith("preofficial").sum())
            official_day_count = int(segments.eq("official_day").sum())
            for rank, bar in stitched.iterrows():
                bar_ts = _parse_ts(bar.get("bar_datetime_ts"))
                segment = _segment_for_bar(bar_ts, official_open_ts)
                bar_rows.append(
                    {
                        "candidate_index": row.get("candidate_index"),
                        "official_open_trade_id": row.get("official_open_trade_id"),
                        "vt_symbol": vt_symbol,
                        "direction": row.get("direction"),
                        "trading_day": official_day.date().isoformat() if pd.notna(official_day) else "",
                        "candidate_date": candidate_day.date().isoformat() if pd.notna(candidate_day) else "",
                        "bar_rank": int(rank),
                        "bar_datetime": _time_text(bar_ts),
                        "bar_date": str(bar.get("bar_date", "")),
                        "bar_segment": segment,
                        "open": _safe_float(bar.get("open")),
                        "high": _safe_float(bar.get("high")),
                        "low": _safe_float(bar.get("low")),
                        "close": _safe_float(bar.get("close")),
                        "volume": _safe_float(bar.get("volume")),
                        "is_raw_timestamp_anchor": int(pd.notna(raw_ts) and bar_ts == raw_ts),
                        "is_official_open_anchor": int(pd.notna(official_open_ts) and bar_ts == official_open_ts),
                        "is_raw_replay_event": int(pd.notna(raw_event_ts) and bar_ts == raw_event_ts),
                        "is_official_event": int(pd.notna(official_event_ts) and bar_ts == official_event_ts),
                    }
                )

        raw_to_official_minutes = (
            (official_open_ts - raw_ts).total_seconds() / 60.0 if pd.notna(raw_ts) and pd.notna(official_open_ts) else np.nan
        )
        order_item = row.to_dict()
        order_item.update(
            {
                "stage042_trading_day": official_day.date().isoformat() if pd.notna(official_day) else "",
                "stage042_session_start_time": _time_text(session_start),
                "stage042_session_end_time": _time_text(session_end),
                "stage042_session_bar_count": int(len(stitched)),
                "stage042_preofficial_bar_count": preofficial_count,
                "stage042_official_day_bar_count": official_day_count,
                "stage042_has_raw_timestamp_bar": has_raw_bar,
                "stage042_has_official_open_bar": has_official_open_bar,
                "stage042_raw_to_official_open_minutes": raw_to_official_minutes,
                "stage042_raw_replay_first_event_time": _time_text(raw_event_ts),
                "stage042_raw_replay_first_event_type": raw_event_type,
                "stage042_official_first_event_time": _time_text(official_event_ts),
                "stage042_official_first_event_type": official_event_type,
                "stage042_raw_event_before_official_open": raw_event_before_official_open,
                "stage042_official_event_before_official_open": official_event_before_official_open,
                "stage042_raw_event_in_stitched": _event_in_frame(stitched, raw_event_ts),
                "stage042_official_event_in_stitched": _event_in_frame(stitched, official_event_ts),
                "stage042_raw_event_family_match": raw_event_match,
                "stage042_session_convention_status": session_status,
            }
        )
        order_rows.append(order_item)

    return pd.DataFrame(order_rows), pd.DataFrame(bar_rows)


def _prepare_orders() -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    alignment = _load_alignment()
    raw = _load_replay_variant("raw_timestamp_stitched_to_official_date_anchor", "raw")
    official_anchor = _load_replay_variant("official_date_official_open_anchor_subset", "official_anchor")
    orders = alignment.merge(raw, on=["candidate_index", "official_open_trade_id"], how="left")
    orders = orders.merge(official_anchor, on=["candidate_index", "official_open_trade_id"], how="left")
    groups = s038._load_minute_groups(orders)
    return orders, groups


def _event_diagnostic(order_ledger: pd.DataFrame) -> pd.DataFrame:
    data = order_ledger.copy()
    data["stage042_raw_event_family_match"] = pd.to_numeric(
        data["stage042_raw_event_family_match"], errors="coerce"
    ).fillna(0)
    grouped = (
        data.groupby(["timestamp_alignment_class", "stage042_session_convention_status"], dropna=False)
        .agg(
            orders=("candidate_index", "count"),
            raw_replay_ready=("raw_stage861_replay_ready", "sum"),
            raw_event_match_orders=("stage042_raw_event_family_match", "sum"),
            raw_event_before_official_open=("stage042_raw_event_before_official_open", "sum"),
            official_event_before_official_open=("stage042_official_event_before_official_open", "sum"),
            raw_event_in_stitched=("stage042_raw_event_in_stitched", "sum"),
            official_event_in_stitched=("stage042_official_event_in_stitched", "sum"),
            median_raw_to_official_open_minutes=("stage042_raw_to_official_open_minutes", "median"),
            median_session_bar_count=("stage042_session_bar_count", "median"),
        )
        .reset_index()
    )
    grouped["raw_event_match_rate_pct"] = np.where(
        grouped["raw_replay_ready"] > 0,
        grouped["raw_event_match_orders"] / grouped["raw_replay_ready"] * 100.0,
        0.0,
    )
    return grouped.sort_values(["timestamp_alignment_class", "orders"], ascending=[True, False]).reset_index(drop=True)


def _status_summary(order_ledger: pd.DataFrame) -> pd.DataFrame:
    data = order_ledger.copy()
    return (
        data.groupby("stage042_session_convention_status", dropna=False)
        .agg(
            orders=("candidate_index", "count"),
            raw_replay_ready=("raw_stage861_replay_ready", "sum"),
            raw_event_before_official_open=("stage042_raw_event_before_official_open", "sum"),
            raw_event_match_orders=("stage042_raw_event_family_match", "sum"),
            median_raw_to_official_open_minutes=("stage042_raw_to_official_open_minutes", "median"),
            median_session_bar_count=("stage042_session_bar_count", "median"),
        )
        .reset_index()
        .sort_values("orders", ascending=False)
    )


def _plot_path(order_ledger: pd.DataFrame) -> None:
    curve = _read_csv(STAGE041_SENSITIVITY_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    data = order_ledger.copy()
    data["official_open_date_ts"] = pd.to_datetime(data["official_open_date"], errors="coerce").dt.normalize()
    daily_preofficial = (
        data[data["stage042_session_convention_status"].eq("raw_replay_scans_preofficial_night_mismatch")]
        .groupby("official_open_date_ts")["candidate_index"]
        .count()
    )
    curve["preofficial_mismatch_orders"] = curve["date"].map(daily_preofficial).fillna(0).cumsum()

    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True, constrained_layout=True)
    axes[0].plot(curve["date"], curve["account_equity"], color="#111827", linewidth=1.2, label="official C9/15w equity")
    if "raw_timestamp_stitched_to_official_date_anchor_equity" in curve.columns:
        axes[0].plot(
            curve["date"],
            curve["raw_timestamp_stitched_to_official_date_anchor_equity"],
            color="#2563eb",
            linewidth=1.0,
            linestyle=":",
            label="same-exit raw timestamp stitched audit",
        )
    axes[0].set_title("Official equity vs raw timestamp stitched same-exit audit")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="best")

    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#111827", linewidth=1.0, label="official DD")
    if "raw_timestamp_stitched_to_official_date_anchor_drawdown_pct" in curve.columns:
        axes[1].plot(
            curve["date"],
            curve["raw_timestamp_stitched_to_official_date_anchor_drawdown_pct"],
            color="#2563eb",
            linewidth=1.0,
            linestyle=":",
            label="raw stitched same-exit DD",
        )
    axes[1].set_title("Drawdown, audit only")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(loc="best")

    axes[2].step(
        curve["date"],
        curve["preofficial_mismatch_orders"],
        where="post",
        color="#dc2626",
        linewidth=1.1,
        label="cumulative raw-night preofficial mismatches",
    )
    axes[2].set_title("Cumulative raw replay mismatches before official open")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend(loc="best")
    fig.suptitle("Stage042 trading-day stitched minute ledger audit", fontsize=14)
    fig.savefig(PATH_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_timeline(order_ledger: pd.DataFrame) -> None:
    data = order_ledger.copy()
    fig, axes = plt.subplots(1, 2, figsize=(15, 6), constrained_layout=True)
    counts = data["timestamp_alignment_class"].value_counts().sort_values(ascending=True)
    axes[0].barh(counts.index, counts.values, color="#2563eb")
    axes[0].set_title("Raw timestamp alignment classes")
    axes[0].grid(axis="x", alpha=0.25)
    for i, value in enumerate(counts.values):
        axes[0].text(value + 0.5, i, str(int(value)), va="center", fontsize=9)

    minutes = pd.to_numeric(data["stage042_raw_to_official_open_minutes"], errors="coerce").dropna()
    axes[1].hist(minutes, bins=24, color="#16a34a", edgecolor="#14532d", alpha=0.8)
    axes[1].set_title("Raw timestamp to official open minutes")
    axes[1].set_xlabel("minutes")
    axes[1].set_ylabel("orders")
    axes[1].grid(True, alpha=0.25)
    fig.savefig(TIMELINE_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_event_diagnostic(event_diagnostic: pd.DataFrame) -> None:
    if event_diagnostic.empty:
        return
    data = event_diagnostic.copy()
    data["label"] = data["timestamp_alignment_class"].astype(str) + "\n" + data["stage042_session_convention_status"].astype(str)
    fig, ax = plt.subplots(figsize=(16, 7), constrained_layout=True)
    x = np.arange(len(data))
    ax.bar(x, data["orders"], color="#93c5fd", label="orders")
    ax.bar(
        x,
        data["raw_event_before_official_open"],
        color="#dc2626",
        alpha=0.8,
        label="raw event before official open",
    )
    ax.set_xticks(x)
    ax.set_xticklabels(data["label"], rotation=35, ha="right", fontsize=8)
    ax.set_title("Session convention status by alignment class")
    ax.set_ylabel("orders")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="best")
    fig.savefig(EVENT_CHART_OUT, dpi=150)
    plt.close(fig)


def _select_atlas(order_ledger: pd.DataFrame) -> pd.DataFrame:
    data = order_ledger.copy()
    mismatch = data[data["stage042_session_convention_status"].eq("raw_replay_scans_preofficial_night_mismatch")].copy()
    if not mismatch.empty:
        mismatch["stage042_preofficial_bar_count"] = pd.to_numeric(
            mismatch["stage042_preofficial_bar_count"], errors="coerce"
        ).fillna(0)
        selected = mismatch.sort_values(["stage042_preofficial_bar_count", "candidate_index"], ascending=[False, True])
    else:
        selected = data.sort_values("candidate_index")
    return selected.head(ATLAS_ROWS).reset_index(drop=True)


def _plot_atlas(order_ledger: pd.DataFrame, groups: dict[str, pd.DataFrame]) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas(order_ledger)
    if selected.empty:
        _write_csv(pd.DataFrame(), ATLAS_MANIFEST_OUT)
        return [], pd.DataFrame()

    pages: list[Path] = []
    manifest_rows: list[dict[str, Any]] = []
    for page_idx, start in enumerate(range(0, len(selected), ATLAS_PER_PAGE), start=1):
        page_rows = selected.iloc[start : start + ATLAS_PER_PAGE].reset_index(drop=True)
        fig, axes = plt.subplots(len(page_rows), 1, figsize=(14, 3.6 * len(page_rows)), sharex=False, constrained_layout=True)
        if len(page_rows) == 1:
            axes = [axes]
        for ax, (_, row) in zip(axes, page_rows.iterrows()):
            vt_symbol = str(row.get("vt_symbol", ""))
            bars = s041._bars_for_symbol(groups, vt_symbol)
            start_ts = _parse_ts(row.get("stage042_session_start_time"))
            end_ts = _parse_ts(row.get("stage042_session_end_time"))
            official_open_ts = _parse_ts(row.get("replay_open_datetime"))
            if bars.empty or pd.isna(start_ts) or pd.isna(end_ts):
                ax.text(0.5, 0.5, "missing stitched bars", ha="center", va="center")
                ax.set_axis_off()
                continue
            stitched = bars[
                pd.to_datetime(bars["bar_datetime_ts"], errors="coerce").ge(start_ts)
                & pd.to_datetime(bars["bar_datetime_ts"], errors="coerce").le(end_ts)
            ].copy()
            stitched = stitched.sort_values("bar_datetime_ts").reset_index(drop=True)
            if stitched.empty:
                ax.text(0.5, 0.5, "empty stitched session", ha="center", va="center")
                ax.set_axis_off()
                continue
            x = np.arange(len(stitched))
            close = pd.to_numeric(stitched["close"], errors="coerce")
            ax.plot(x, close, color="#2563eb", linewidth=0.9, label="stitched close")
            pre_mask = pd.to_datetime(stitched["bar_datetime_ts"], errors="coerce").lt(official_open_ts)
            if pre_mask.any():
                ax.axvspan(0, int(pre_mask.sum()) - 1, color="#fde68a", alpha=0.28, label="preofficial night span")
            for price, color, label in [
                (row.get("official_open_price"), "#111827", "official open"),
                (row.get("planned_stop_price"), "#dc2626", "planned stop"),
            ]:
                value = _safe_float(price)
                if np.isfinite(value):
                    ax.axhline(value, color=color, linestyle="--", linewidth=0.75, alpha=0.85, label=label)
            for field, color, label in [
                ("timestamp_first_time", "#16a34a", "raw 21:00 anchor"),
                ("replay_open_datetime", "#111827", "official open anchor"),
                ("stage042_raw_replay_first_event_time", "#dc2626", "raw replay first event"),
                ("stage042_official_first_event_time", "#7c3aed", "official first event"),
            ]:
                ts = _parse_ts(row.get(field))
                if pd.notna(ts):
                    hits = stitched.index[pd.to_datetime(stitched["bar_datetime_ts"], errors="coerce").eq(ts)].tolist()
                    if hits:
                        ax.axvline(hits[0], color=color, linewidth=0.9, alpha=0.9, label=label)
            ax.set_title(
                f"{vt_symbol} {row.get('direction')} idx={row.get('candidate_index')} "
                f"status={row.get('stage042_session_convention_status')}"
            )
            ax.grid(True, alpha=0.25)
            ax.legend(loc="best", fontsize=7, ncol=4)
            tick_locs = np.linspace(0, len(stitched) - 1, min(6, len(stitched)), dtype=int)
            ax.set_xticks(tick_locs)
            ax.set_xticklabels(
                [pd.Timestamp(stitched.iloc[i]["bar_datetime_ts"]).strftime("%m-%d %H:%M") for i in tick_locs],
                fontsize=8,
                rotation=0,
            )
            manifest_rows.append(
                {
                    "page": page_idx,
                    "candidate_index": row.get("candidate_index"),
                    "official_open_trade_id": row.get("official_open_trade_id"),
                    "vt_symbol": vt_symbol,
                    "official_open_date": row.get("official_open_date"),
                    "timestamp_alignment_class": row.get("timestamp_alignment_class"),
                    "stage042_session_convention_status": row.get("stage042_session_convention_status"),
                    "raw_replay_event_family": row.get("raw_replay_event_family"),
                    "official_event_family": row.get("official_event_family"),
                    "raw_event_before_official_open": row.get("stage042_raw_event_before_official_open"),
                }
            )
        page_path = Path(str(ATLAS_TEMPLATE).format(page=page_idx))
        fig.suptitle("Stage042 stitched trading-day atlas", fontsize=14)
        fig.savefig(page_path, dpi=150)
        plt.close(fig)
        pages.append(page_path)
    manifest = pd.DataFrame(manifest_rows)
    _write_csv(manifest, ATLAS_MANIFEST_OUT)
    return pages, manifest


def _summary(order_ledger: pd.DataFrame, event_diagnostic: pd.DataFrame) -> pd.DataFrame:
    curve = _read_csv(STAGE041_SENSITIVITY_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    official_metrics = _curve_metrics(curve, "account_equity")
    raw_metrics = _curve_metrics(curve, "raw_timestamp_stitched_to_official_date_anchor_equity")
    data = order_ledger.copy()
    ready_raw = data[pd.to_numeric(data.get("raw_stage861_replay_ready", 0), errors="coerce").fillna(0).eq(1)].copy()
    pre_mismatch = data[data["stage042_session_convention_status"].eq("raw_replay_scans_preofficial_night_mismatch")]
    row = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "end_equity": official_metrics["end_equity"],
        "total_return_pct": official_metrics["total_return_pct"],
        "max_drawdown_pct": official_metrics["max_drawdown_pct"],
        "sharpe": official_metrics["sharpe"],
        "timestamp_ready_orders": int(len(data)),
        "raw_stage861_replay_ready_orders": int(len(ready_raw)),
        "raw_timestamp_in_official_date_orders": int(data["timestamp_alignment_class"].eq("raw_timestamp_in_official_date").sum()),
        "raw_timestamp_in_candidate_date_not_official_orders": int(
            data["timestamp_alignment_class"].eq("raw_timestamp_in_candidate_date_not_official").sum()
        ),
        "raw_timestamp_missing_stage861_timestamp_orders": int(
            data["timestamp_alignment_class"].eq("missing_stage861_timestamp_bar").sum()
        ),
        "session_convention_consistent_orders": int(data["stage042_session_convention_status"].eq("session_convention_consistent").sum()),
        "raw_preofficial_mismatch_orders": int(len(pre_mismatch)),
        "raw_preofficial_any_event_orders": int(data["stage042_raw_event_before_official_open"].sum()),
        "official_preofficial_event_orders": int(data["stage042_official_event_before_official_open"].sum()),
        "median_raw_to_official_open_minutes": float(
            pd.to_numeric(data["stage042_raw_to_official_open_minutes"], errors="coerce").median()
        ),
        "median_stitched_session_bar_count": float(pd.to_numeric(data["stage042_session_bar_count"], errors="coerce").median()),
        "raw_stitched_same_exit_end_equity": raw_metrics["end_equity"],
        "raw_stitched_same_exit_max_drawdown_pct": raw_metrics["max_drawdown_pct"],
        "decision": "stage042_trading_day_stitched_ledger_built_no_trade_rule",
        "candidate_ready": 0,
        "ab_triggered": 0,
    }
    if not event_diagnostic.empty:
        row["diagnostic_groups"] = int(len(event_diagnostic))
    return pd.DataFrame([row])


def _write_report(
    summary: pd.DataFrame,
    status_summary: pd.DataFrame,
    event_diagnostic: pd.DataFrame,
    atlas_pages: list[Path],
) -> None:
    row = summary.iloc[0]
    lines = [
        "# Stage042 Trading-Day Stitched Minute Ledger Audit",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 研究线：`{LINE_ID}`",
        f"- 官方正式版：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "- 阶段定位：只做交易日/session 口径账本审计；不新增交易规则、不改正式配置、不连接 CTP、不调用订单 API、不触发 A/B。",
        "- 决策：`stage042_trading_day_stitched_ledger_built_no_trade_rule`。",
        "",
        "## 核心结论",
        "",
        f"- timestamp-ready orders：`{int(row['timestamp_ready_orders'])}`；raw Stage861 replay ready：`{int(row['raw_stage861_replay_ready_orders'])}`。",
        f"- raw timestamp 在 official date 内：`{int(row['raw_timestamp_in_official_date_orders'])}`；在 candidate date 夜盘但归属 official trading day：`{int(row['raw_timestamp_in_candidate_date_not_official_orders'])}`；Stage861 缺 raw timestamp：`{int(row['raw_timestamp_missing_stage861_timestamp_orders'])}`。",
        f"- raw replay 在 official open 之前触发且造成 mismatch：`{int(row['raw_preofficial_mismatch_orders'])}`；official diagnostics 自身在 official open 前触发：`{int(row['official_preofficial_event_orders'])}`。",
        f"- raw 到 official open 中位间隔：`{row['median_raw_to_official_open_minutes']:.4f}` 分钟；stitched session 中位 bar 数：`{row['median_stitched_session_bar_count']:.4f}`。",
        "",
        "## 官方基准",
        "",
        f"- 期末权益：`{row['end_equity']:.2f}`",
        f"- 总收益：`{row['total_return_pct']:.4f}%`",
        f"- 最大回撤：`{row['max_drawdown_pct']:.4f}%`",
        f"- Sharpe：`{row['sharpe']:.4f}`",
        "",
        "## Session 状态分布",
        "",
        _md_table(status_summary, max_rows=20),
        "",
        "## 事件诊断",
        "",
        _md_table(event_diagnostic, max_rows=30),
        "",
        "## 视觉输出",
        "",
        f"- session path chart：`{PATH_CHART_OUT}`",
        f"- session timeline chart：`{TIMELINE_CHART_OUT}`",
        f"- event diagnostic chart：`{EVENT_CHART_OUT}`",
        f"- atlas pages：`{len(atlas_pages)}`",
        f"- atlas manifest：`{ATLAS_MANIFEST_OUT}`",
        "",
        "## 文件",
        "",
        f"- session order ledger：`{SESSION_ORDER_OUT}`",
        f"- stitched bar ledger：`{SESSION_BAR_OUT}`",
        f"- event diagnostic：`{EVENT_DIAGNOSTIC_OUT}`",
        f"- summary：`{SUMMARY_OUT}`",
        f"- decision：`{DECISION_OUT}`",
        "",
        "## 判断",
        "",
        "- 这一步没有验证任何收益候选；它只是把国内期货夜盘 candidate date 与 official trading day 的 session 关系显式化。",
        "- 如果 raw replay 在 official open 之前扫到了夜盘事件，而官方 diagnostics 从 official-date anchor 扫描，这属于账本 convention 差异，不是信号质量差异。",
        "- 下一步若继续，只能基于该 stitched ledger 修 replay semantics；在 replay 与官方事件口径未通过前，继续暂停新增分钟进出场候选。",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    orders, groups = _prepare_orders()
    order_ledger, bar_ledger = _build_ledgers(orders, groups)
    event_diagnostic = _event_diagnostic(order_ledger)
    status_summary = _status_summary(order_ledger)
    summary = _summary(order_ledger, event_diagnostic)

    _write_csv(order_ledger, SESSION_ORDER_OUT)
    _write_csv(bar_ledger, SESSION_BAR_OUT)
    _write_csv(event_diagnostic, EVENT_DIAGNOSTIC_OUT)
    _write_csv(status_summary, STATUS_SUMMARY_OUT)
    _write_csv(summary, SUMMARY_OUT)

    _plot_path(order_ledger)
    _plot_timeline(order_ledger)
    _plot_event_diagnostic(event_diagnostic)
    atlas_pages, manifest = _plot_atlas(order_ledger, groups)
    _write_report(summary, status_summary, event_diagnostic, atlas_pages)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "decision": "stage042_trading_day_stitched_ledger_built_no_trade_rule",
        "candidate_ready": 0,
        "ab_triggered": 0,
        "rule_added": 0,
        "official_config_changed": 0,
        "summary": summary.iloc[0].to_dict(),
        "outputs": {
            "session_order_ledger": SESSION_ORDER_OUT,
            "stitched_bar_ledger": SESSION_BAR_OUT,
            "event_diagnostic": EVENT_DIAGNOSTIC_OUT,
            "status_summary": STATUS_SUMMARY_OUT,
            "summary": SUMMARY_OUT,
            "report": REPORT_OUT,
            "path_chart": PATH_CHART_OUT,
            "timeline_chart": TIMELINE_CHART_OUT,
            "event_chart": EVENT_CHART_OUT,
            "atlas_manifest": ATLAS_MANIFEST_OUT,
            "atlas_pages": atlas_pages,
        },
        "judgment": (
            "Trading-day stitched ledger is now explicit, but it is an audit ledger only. "
            "Do not use raw timestamp as a minute-rule replay start until official event semantics are reconciled."
        ),
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
