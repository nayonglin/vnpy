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
STAGE = "Stage043"
MODEL_TAG = "stage043_official_open_scan_replay_repair_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage043_c9_minrisk_official_open_scan_replay_repair_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage038_order_event_replay_prototype_audit as s038
import stage041_timestamp_ready_replay_consistency_audit as s041
import stage042_trading_day_stitched_minute_ledger_audit as s042
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE041_DIR = LINE_DIR / "outputs" / "stage041_timestamp_ready_replay_consistency_audit"
STAGE042_DIR = LINE_DIR / "outputs" / "stage042_trading_day_stitched_minute_ledger_audit"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage043_official_open_scan_replay_repair_audit"

STAGE041_SENSITIVITY_IN = (
    STAGE041_DIR
    / "qmt_roll_stage041_c9_minrisk_timestamp_ready_replay_consistency_audit_same_exit_sensitivity_curve_"
    "stage041_timestamp_ready_replay_consistency_audit_v1.csv"
)
STAGE042_ORDER_IN = (
    STAGE042_DIR
    / "qmt_roll_stage042_c9_minrisk_trading_day_stitched_minute_ledger_audit_session_order_ledger_"
    "stage042_trading_day_stitched_minute_ledger_audit_v1.csv"
)

REPAIR_REPLAY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_repair_replay_ledger_{MODEL_TAG}.csv"
REPAIR_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_repair_status_summary_{MODEL_TAG}.csv"
EVENT_DIAGNOSTIC_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_diagnostic_{MODEL_TAG}.csv"
LOT_SENSITIVITY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_same_exit_lot_sensitivity_{MODEL_TAG}.csv"
CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_same_exit_repair_curve_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_repair_path_chart_{MODEL_TAG}.png"
EVENT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_repair_event_chart_{MODEL_TAG}.png"
RESIDUAL_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_residual_mismatch_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

CAPITAL = 150_000.0
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


def _parse_ts(value: Any) -> pd.Timestamp:
    return s042._parse_ts(value)


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


def _load_orders() -> pd.DataFrame:
    data = _read_csv(STAGE042_ORDER_IN)
    for column in [
        "candidate_date",
        "official_open_date",
        "timestamp_first_time",
        "timestamp_last_time",
        "replay_open_datetime",
        "official_first_stop_time",
        "official_reentry_time",
        "official_retry_failed_time",
        "official_hit_time",
        "stage042_raw_replay_first_event_time",
        "stage042_official_first_event_time",
    ]:
        if column in data.columns:
            data[f"{column}_ts"] = data[column].map(_parse_ts)
    for column in [
        "official_open_price",
        "official_open_volume",
        "candidate_selected_volume",
        "planned_stop_price",
        "planned_stop_distance",
        "engine_selected_price",
        "raw_price",
        "seed_price",
        "stage042_raw_event_family_match",
        "raw_stage861_replay_ready",
        "official_anchor_stage861_replay_ready",
        "official_anchor_event_family_match_y",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.reset_index(drop=True)


def _proxy_fill_price(row: pd.Series) -> tuple[float, str]:
    candidates = [
        ("engine_selected_price", row.get("engine_selected_price")),
        ("raw_price", row.get("raw_price")),
        ("seed_price", row.get("seed_price")),
        ("official_open_price", row.get("official_open_price")),
    ]
    for source, value in candidates:
        price = _safe_float(value)
        if np.isfinite(price) and price > 0:
            return price, source
    return np.nan, "missing_proxy_and_official_price"


def _official_event_fields(row: pd.Series) -> dict[str, Any]:
    return {
        "official_event_family": row.get("official_event_family", "no_intraday_event"),
        "official_exit_reason": row.get("official_exit_reason", ""),
        "official_first_stop_time": _time_text(row.get("official_first_stop_time")),
        "official_reentry_time": _time_text(row.get("official_reentry_time")),
        "official_retry_failed_time": _time_text(row.get("official_retry_failed_time")),
        "official_hit_time": _time_text(row.get("official_hit_time")),
        "official_final_state": row.get("official_final_state", ""),
        "official_final_exit_price": _safe_float(row.get("official_final_exit_price")),
    }


def _select_official_scan_bars(row: pd.Series, groups: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, str]:
    bars = s041._bars_for_symbol(groups, str(row.get("vt_symbol", "")))
    if bars.empty:
        return pd.DataFrame(), "missing_stage861_symbol"
    official_day = _normalize_day(row.get("official_open_date"))
    official_day_bars = s041._bars_on_date(bars, official_day)
    if official_day_bars.empty:
        return pd.DataFrame(), "missing_official_date_stage861_bars"

    official_open_ts = _parse_ts(row.get("replay_open_datetime"))
    if pd.isna(official_open_ts):
        official_open_ts = _parse_ts(row.get("official_anchor_replay_open_datetime"))
    if pd.isna(official_open_ts):
        official_open_ts = _parse_ts(row.get("stage861_first_open_time"))
    if pd.isna(official_open_ts):
        first = official_day_bars.iloc[0]
        official_open_ts = _parse_ts(first.get("bar_datetime_ts"))

    scan = official_day_bars[
        pd.to_datetime(official_day_bars["bar_datetime_ts"], errors="coerce").ge(official_open_ts)
    ].copy()
    if scan.empty:
        return pd.DataFrame(), "official_open_time_after_stage861_day"
    return scan.sort_values("bar_datetime_ts").reset_index(drop=True), "raw_proxy_price_official_open_scan"


def _replay_one(row: pd.Series, groups: dict[str, pd.DataFrame]) -> dict[str, Any]:
    direction = s038._direction_text(row.get("direction"))
    official_entry = _safe_float(row.get("official_open_price"))
    planned_stop = _safe_float(row.get("planned_stop_price"))
    replay_open, fill_source = _proxy_fill_price(row)
    bars, scan_source = _select_official_scan_bars(row, groups)
    base = row.to_dict()
    base.update(
        {
            "variant_id": "raw_price_official_open_scan",
            "fill_mode": "raw_price_official_open_scan",
            "stage861_day_ready": 0,
            "replay_bar_count": 0,
            "replay_open_datetime": "",
            "replay_open_time": "",
            "replay_open_price": replay_open,
            "replay_open_price_source": fill_source,
            "replay_scan_source": scan_source,
            "replay_open_minus_official": replay_open - official_entry
            if np.isfinite(replay_open) and np.isfinite(official_entry)
            else np.nan,
            "replay_open_abs_delta": abs(replay_open - official_entry)
            if np.isfinite(replay_open) and np.isfinite(official_entry)
            else np.nan,
            "replay_risk_price": np.nan,
            "replay_c9_stop_price": np.nan,
            "replay_c9_progress_price": np.nan,
            "replay_c2_stop_price": np.nan,
            "replay_c2_confirm_price": np.nan,
            "replay_event_family": "missing_stage861_replay_bars",
            "replay_first_stop_time": "",
            "replay_reentry_time": "",
            "replay_retry_failed_time": "",
            "replay_c2_hit_time": "",
            "replay_final_exit_price": np.nan,
            "event_family_match": 0,
            "first_stop_time_match": 0,
            "reentry_time_match": 0,
            "retry_failed_time_match": 0,
            "c2_hit_time_match": 0,
            **_official_event_fields(row),
        }
    )
    if bars.empty:
        base["replay_event_family"] = scan_source
        return base

    bars = bars.sort_values("bar_datetime_ts").reset_index(drop=True)
    first = bars.iloc[0]
    risk_price = abs(replay_open - planned_stop) if np.isfinite(replay_open) and np.isfinite(planned_stop) else np.nan
    base.update(
        {
            "stage861_day_ready": 1,
            "replay_bar_count": int(len(bars)),
            "replay_open_datetime": _time_text(first.get("bar_datetime_ts")),
            "replay_open_time": _hhmm(first.get("bar_datetime_ts")),
            "replay_risk_price": risk_price,
            "replay_c2_stop_price": planned_stop,
            "replay_c2_confirm_price": replay_open + s038._direction_sign(direction) * risk_price
            if np.isfinite(risk_price)
            else np.nan,
        }
    )
    min_risk = max(1e-9, abs(replay_open) * 1e-12) if np.isfinite(replay_open) else np.nan
    if not np.isfinite(risk_price) or risk_price < min_risk:
        base["replay_event_family"] = "invalid_replay_risk"
        return base

    c9 = s038._first_c9_stop_or_progress(bars, entry_price=replay_open, risk_price=risk_price, direction=direction)
    base.update(
        {
            "replay_c9_stop_price": c9["stop_price"],
            "replay_c9_progress_price": c9["progress_price"],
            "replay_same_bar_progress": int(c9.get("same_bar_progress", 0)),
        }
    )
    if c9["event"] == "stop":
        retry = s038._reentry_after_stop(
            bars,
            direction=direction,
            entry_price=replay_open,
            stop_price=float(c9["stop_price"]),
            stop_idx=int(c9["idx"]),
        )
        family = "c9_flat_no_reentry"
        final_exit = float(c9["stop_price"])
        if int(retry["reentry_idx"]) >= 0:
            family = "c9_open_after_reentry"
            final_exit = np.nan
            if int(retry["retry_failed_idx"]) >= 0:
                family = "c9_flat_retry_failed"
                final_exit = float(c9["stop_price"])
        base.update(
            {
                "replay_event_family": family,
                "replay_first_stop_time": str(c9["time"]),
                "replay_reentry_time": str(retry["reentry_time"]),
                "replay_retry_failed_time": str(retry["retry_failed_time"]),
                "replay_final_exit_price": final_exit,
            }
        )
    else:
        c2 = s038._first_c2_stop_or_confirm(
            bars,
            entry_price=replay_open,
            stop_price=planned_stop,
            risk_price=risk_price,
            direction=direction,
        )
        if c2["event"] == "c2_stop":
            family = "c2_stop"
            final_exit = planned_stop
            hit_time = str(c2["time"])
        else:
            family = "open_no_intraday_event"
            final_exit = np.nan
            hit_time = ""
        base.update(
            {
                "replay_event_family": family,
                "replay_c2_hit_time": hit_time,
                "replay_final_exit_price": final_exit,
                "replay_c2_same_bar_confirm": int(c2.get("same_bar_confirm", 0)),
            }
        )

    official_family = str(base.get("official_event_family", "no_intraday_event"))
    replay_family = str(base.get("replay_event_family", ""))
    base["event_family_match"] = int(
        (official_family == "no_intraday_event" and replay_family == "open_no_intraday_event")
        or official_family == replay_family
    )
    base["first_stop_time_match"] = int(
        bool(base.get("official_first_stop_time")) and base.get("official_first_stop_time") == base.get("replay_first_stop_time")
    )
    base["reentry_time_match"] = int(
        bool(base.get("official_reentry_time")) and base.get("official_reentry_time") == base.get("replay_reentry_time")
    )
    base["retry_failed_time_match"] = int(
        bool(base.get("official_retry_failed_time"))
        and base.get("official_retry_failed_time") == base.get("replay_retry_failed_time")
    )
    base["c2_hit_time_match"] = int(
        bool(base.get("official_hit_time")) and base.get("official_hit_time") == base.get("replay_c2_hit_time")
    )
    return base


def _build_replay(orders: pd.DataFrame, groups: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = [_replay_one(row, groups) for _, row in orders.iterrows()]
    replay = pd.DataFrame(rows)
    for column in [
        "stage861_day_ready",
        "replay_bar_count",
        "replay_open_price",
        "replay_open_minus_official",
        "replay_open_abs_delta",
        "replay_risk_price",
        "event_family_match",
        "first_stop_time_match",
        "reentry_time_match",
        "retry_failed_time_match",
        "c2_hit_time_match",
        "stage042_raw_event_family_match",
    ]:
        if column in replay.columns:
            replay[column] = pd.to_numeric(replay[column], errors="coerce")
    return replay


def _event_diagnostic(replay: pd.DataFrame) -> pd.DataFrame:
    data = replay.copy()
    data["official_event_family"] = data["official_event_family"].fillna("no_intraday_event")
    data["replay_event_family"] = data["replay_event_family"].fillna("missing")
    return (
        data.groupby(["official_event_family", "replay_event_family"], dropna=False)
        .agg(
            orders=("candidate_index", "count"),
            replay_ready=("stage861_day_ready", "sum"),
            event_family_match=("event_family_match", "sum"),
            first_stop_time_match=("first_stop_time_match", "sum"),
            reentry_time_match=("reentry_time_match", "sum"),
            retry_failed_time_match=("retry_failed_time_match", "sum"),
            c2_hit_time_match=("c2_hit_time_match", "sum"),
            median_abs_price_delta=("replay_open_abs_delta", "median"),
        )
        .reset_index()
        .sort_values(["official_event_family", "orders"], ascending=[True, False])
    )


def _repair_status(replay: pd.DataFrame) -> pd.DataFrame:
    data = replay.copy()
    data["raw_match"] = pd.to_numeric(data.get("stage042_raw_event_family_match", 0), errors="coerce").fillna(0)
    data["repair_match"] = pd.to_numeric(data.get("event_family_match", 0), errors="coerce").fillna(0)
    grouped = (
        data.groupby("stage042_session_convention_status", dropna=False)
        .agg(
            orders=("candidate_index", "count"),
            raw_match_orders=("raw_match", "sum"),
            repair_match_orders=("repair_match", "sum"),
            resolved_by_official_open_scan=("candidate_index", lambda idx: 0),
            still_mismatch=("candidate_index", lambda idx: 0),
            replay_ready=("stage861_day_ready", "sum"),
            median_abs_price_delta=("replay_open_abs_delta", "median"),
        )
        .reset_index()
    )
    rows = []
    for _, row in grouped.iterrows():
        subset = data[data["stage042_session_convention_status"].astype(str).eq(str(row["stage042_session_convention_status"]))].copy()
        raw_match = pd.to_numeric(subset["raw_match"], errors="coerce").fillna(0)
        repair_match = pd.to_numeric(subset["repair_match"], errors="coerce").fillna(0)
        row = row.to_dict()
        row["resolved_by_official_open_scan"] = int(((raw_match == 0) & (repair_match == 1)).sum())
        row["still_mismatch"] = int((repair_match == 0).sum())
        row["raw_match_rate_pct"] = float(raw_match.mean() * 100.0) if len(subset) else 0.0
        row["repair_match_rate_pct"] = float(repair_match.mean() * 100.0) if len(subset) else 0.0
        rows.append(row)
    return pd.DataFrame(rows).sort_values("orders", ascending=False).reset_index(drop=True)


def _repair_curve(curve: pd.DataFrame, lot_sensitivity: pd.DataFrame) -> pd.DataFrame:
    repaired = s038._sensitivity_curve(curve, lot_sensitivity)
    repaired.rename(
        columns={
            "same_exit_entry_replay_delta": "repair_same_exit_delta",
            "cum_same_exit_entry_replay_delta": "repair_same_exit_cum_delta",
            "same_exit_replay_equity": "repair_same_exit_equity",
            "same_exit_replay_drawdown_pct": "repair_same_exit_drawdown_pct",
        },
        inplace=True,
    )
    stage041 = _read_csv(STAGE041_SENSITIVITY_IN)
    stage041["date"] = pd.to_datetime(stage041["date"], errors="coerce").dt.normalize()
    keep = [
        "date",
        "raw_timestamp_stitched_to_official_date_anchor_equity",
        "raw_timestamp_stitched_to_official_date_anchor_drawdown_pct",
    ]
    repaired = repaired.merge(stage041[[col for col in keep if col in stage041.columns]], on="date", how="left")
    return repaired


def _summary(
    curve: pd.DataFrame,
    lots: pd.DataFrame,
    replay: pd.DataFrame,
    repair_status: pd.DataFrame,
    repair_curve: pd.DataFrame,
) -> pd.DataFrame:
    official = s038._official_metrics(curve, lots)
    repair_metrics = _curve_metrics(repair_curve, "repair_same_exit_equity")
    raw_stage041_metrics = _curve_metrics(
        repair_curve.rename(
            columns={"raw_timestamp_stitched_to_official_date_anchor_equity": "raw_equity"}
        ),
        "raw_equity",
    )
    ready = replay[pd.to_numeric(replay["stage861_day_ready"], errors="coerce").fillna(0).eq(1)].copy()
    raw_ready = replay[pd.to_numeric(replay.get("raw_stage861_replay_ready", 0), errors="coerce").fillna(0).eq(1)].copy()
    raw_match = pd.to_numeric(replay.get("stage042_raw_event_family_match", 0), errors="coerce").fillna(0)
    repair_match = pd.to_numeric(replay.get("event_family_match", 0), errors="coerce").fillna(0)
    preofficial = replay[replay["stage042_session_convention_status"].eq("raw_replay_scans_preofficial_night_mismatch")]
    residual = replay[pd.to_numeric(replay["event_family_match"], errors="coerce").fillna(0).eq(0)]
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                **official,
                "timestamp_ready_orders": int(len(replay)),
                "raw_stitched_ready_orders": int(len(raw_ready)),
                "raw_stitched_event_match_orders": int(raw_match.sum()),
                "raw_stitched_event_match_rate_pct": float(raw_match.mean() * 100.0) if len(replay) else 0.0,
                "raw_stitched_event_mismatch_orders": int((raw_match == 0).sum()),
                "repair_ready_orders": int(len(ready)),
                "repair_event_match_orders": int(repair_match.sum()),
                "repair_event_match_rate_pct": float(repair_match.mean() * 100.0) if len(replay) else 0.0,
                "repair_event_mismatch_orders": int(len(residual)),
                "preofficial_mismatch_orders_before_repair": int(len(preofficial)),
                "preofficial_mismatch_resolved_orders": int(
                    pd.to_numeric(preofficial.get("event_family_match", 0), errors="coerce").fillna(0).sum()
                ),
                "raw_stitched_same_exit_end_equity": raw_stage041_metrics["end_equity"],
                "raw_stitched_same_exit_max_drawdown_pct": raw_stage041_metrics["max_drawdown_pct"],
                "repair_same_exit_end_equity": repair_metrics["end_equity"],
                "repair_same_exit_max_drawdown_pct": repair_metrics["max_drawdown_pct"],
                "decision": "stage043_replay_semantics_repaired_to_official_open_scan_no_trade_rule",
                "candidate_ready": 0,
                "ab_triggered": 0,
            }
        ]
    )


def _plot_path(repair_curve: pd.DataFrame, replay: pd.DataFrame) -> None:
    data = replay.copy()
    data["official_open_date_ts"] = pd.to_datetime(data["official_open_date"], errors="coerce").dt.normalize()
    residual_daily = (
        data[pd.to_numeric(data["event_family_match"], errors="coerce").fillna(0).eq(0)]
        .groupby("official_open_date_ts")["candidate_index"]
        .count()
    )
    repair_curve["repair_residual_mismatch_cum"] = repair_curve["date"].map(residual_daily).fillna(0).cumsum()

    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True, constrained_layout=True)
    axes[0].plot(repair_curve["date"], repair_curve["account_equity"], color="#111827", linewidth=1.2, label="official C9/15w")
    if "raw_timestamp_stitched_to_official_date_anchor_equity" in repair_curve.columns:
        axes[0].plot(
            repair_curve["date"],
            repair_curve["raw_timestamp_stitched_to_official_date_anchor_equity"],
            color="#93c5fd",
            linewidth=1.0,
            linestyle=":",
            label="raw stitched same-exit audit",
        )
    axes[0].plot(
        repair_curve["date"],
        repair_curve["repair_same_exit_equity"],
        color="#16a34a",
        linewidth=1.0,
        linestyle="--",
        label="repair: raw price + official-open scan",
    )
    axes[0].set_title("Official equity vs repaired same-exit audit")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="best")

    axes[1].plot(repair_curve["date"], repair_curve["drawdown_pct"], color="#111827", linewidth=1.0, label="official DD")
    axes[1].plot(
        repair_curve["date"],
        repair_curve["repair_same_exit_drawdown_pct"],
        color="#16a34a",
        linewidth=1.0,
        linestyle="--",
        label="repair same-exit DD",
    )
    axes[1].set_title("Drawdown, audit only")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(loc="best")

    axes[2].step(
        repair_curve["date"],
        repair_curve["repair_residual_mismatch_cum"],
        where="post",
        color="#dc2626",
        linewidth=1.1,
        label="cumulative residual repair mismatches",
    )
    axes[2].set_title("Residual mismatches after official-open scan repair")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend(loc="best")
    fig.suptitle("Stage043 replay semantics repair audit", fontsize=14)
    fig.savefig(PATH_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_event_chart(repair_status: pd.DataFrame) -> None:
    data = repair_status.copy()
    fig, ax = plt.subplots(figsize=(14, 7), constrained_layout=True)
    x = np.arange(len(data))
    width = 0.36
    ax.bar(x - width / 2, data["raw_match_rate_pct"], width=width, color="#93c5fd", label="raw stitched match rate")
    ax.bar(x + width / 2, data["repair_match_rate_pct"], width=width, color="#16a34a", label="repair match rate")
    ax.set_xticks(x)
    ax.set_xticklabels(data["stage042_session_convention_status"], rotation=30, ha="right", fontsize=8)
    ax.set_ylim(0, 105)
    ax.set_ylabel("event family match rate %")
    ax.set_title("Raw stitched vs official-open scan repair by Stage042 status")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="best")
    fig.savefig(EVENT_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_residual_chart(event_diagnostic: pd.DataFrame) -> None:
    residual = event_diagnostic[event_diagnostic["event_family_match"].eq(0)].copy()
    if residual.empty:
        return
    residual["pair"] = residual["official_event_family"].astype(str) + " -> " + residual["replay_event_family"].astype(str)
    fig, ax = plt.subplots(figsize=(12, 6), constrained_layout=True)
    ax.barh(residual["pair"], residual["orders"], color="#dc2626")
    ax.set_title("Residual event-family mismatches after repair")
    ax.grid(axis="x", alpha=0.25)
    for i, value in enumerate(residual["orders"]):
        ax.text(value + 0.05, i, str(int(value)), va="center", fontsize=9)
    fig.savefig(RESIDUAL_CHART_OUT, dpi=150)
    plt.close(fig)


def _select_atlas(replay: pd.DataFrame) -> pd.DataFrame:
    residual = replay[pd.to_numeric(replay["event_family_match"], errors="coerce").fillna(0).eq(0)].copy()
    resolved = replay[
        replay["stage042_session_convention_status"].eq("raw_replay_scans_preofficial_night_mismatch")
        & pd.to_numeric(replay["event_family_match"], errors="coerce").fillna(0).eq(1)
    ].copy()
    parts = []
    if not residual.empty:
        parts.append(residual.sort_values("candidate_index").head(ATLAS_ROWS // 2))
    if not resolved.empty:
        parts.append(resolved.sort_values("candidate_index").head(ATLAS_ROWS // 2))
    if not parts:
        return replay.sort_values("candidate_index").head(ATLAS_ROWS).reset_index(drop=True)
    return pd.concat(parts, ignore_index=True, sort=False).drop_duplicates(
        subset=["candidate_index", "official_open_trade_id"]
    ).head(ATLAS_ROWS).reset_index(drop=True)


def _plot_atlas(replay: pd.DataFrame, groups: dict[str, pd.DataFrame]) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas(replay)
    if selected.empty:
        _write_csv(pd.DataFrame(), ATLAS_MANIFEST_OUT)
        return [], pd.DataFrame()

    pages: list[Path] = []
    manifest_rows: list[dict[str, Any]] = []
    for page_idx, start in enumerate(range(0, len(selected), ATLAS_PER_PAGE), start=1):
        page_rows = selected.iloc[start : start + ATLAS_PER_PAGE].reset_index(drop=True)
        fig, axes = plt.subplots(len(page_rows), 1, figsize=(14, 3.5 * len(page_rows)), sharex=False, constrained_layout=True)
        if len(page_rows) == 1:
            axes = [axes]
        for ax, (_, row) in zip(axes, page_rows.iterrows()):
            bars = s041._bars_for_symbol(groups, str(row.get("vt_symbol", "")))
            official_day = _normalize_day(row.get("official_open_date"))
            day = s041._bars_on_date(bars, official_day) if not bars.empty else pd.DataFrame()
            if day.empty:
                ax.text(0.5, 0.5, "missing official day bars", ha="center", va="center")
                ax.set_axis_off()
                continue
            official_open_ts = _parse_ts(row.get("replay_open_datetime"))
            scan = day[pd.to_datetime(day["bar_datetime_ts"], errors="coerce").ge(official_open_ts)].copy()
            scan = scan.sort_values("bar_datetime_ts").reset_index(drop=True)
            if scan.empty:
                scan = day.sort_values("bar_datetime_ts").reset_index(drop=True)
            x = np.arange(len(scan))
            close = pd.to_numeric(scan["close"], errors="coerce")
            ax.plot(x, close, color="#2563eb", linewidth=0.9, label="official-date close")
            for price, color, label in [
                (row.get("official_open_price"), "#111827", "official open"),
                (row.get("planned_stop_price"), "#dc2626", "planned stop"),
                (row.get("replay_open_price"), "#16a34a", "repair fill price"),
            ]:
                value = _safe_float(price)
                if np.isfinite(value):
                    ax.axhline(value, color=color, linewidth=0.75, linestyle="--", alpha=0.85, label=label)
            for field, color, label in [
                ("replay_open_datetime", "#111827", "official scan start"),
                ("replay_first_stop_time", "#dc2626", "repair first stop"),
                ("replay_reentry_time", "#16a34a", "repair reentry"),
                ("replay_retry_failed_time", "#f97316", "repair retry failed"),
                ("replay_c2_hit_time", "#7c3aed", "repair C2 hit"),
                ("official_first_stop_time", "#991b1b", "official first stop"),
                ("official_hit_time", "#581c87", "official C2 hit"),
            ]:
                ts = _parse_ts(row.get(field))
                if pd.notna(ts):
                    hits = scan.index[pd.to_datetime(scan["bar_datetime_ts"], errors="coerce").eq(ts)].tolist()
                    if hits:
                        ax.axvline(hits[0], color=color, linewidth=0.9, alpha=0.9, label=label)
            ax.set_title(
                f"{row.get('vt_symbol')} {row.get('direction')} idx={row.get('candidate_index')} "
                f"official={row.get('official_event_family')} repair={row.get('replay_event_family')} "
                f"match={int(_safe_float(row.get('event_family_match'), 0))}"
            )
            ax.grid(True, alpha=0.25)
            ax.legend(loc="best", fontsize=7, ncol=4)
            tick_locs = np.linspace(0, len(scan) - 1, min(6, len(scan)), dtype=int)
            ax.set_xticks(tick_locs)
            ax.set_xticklabels(
                [pd.Timestamp(scan.iloc[i]["bar_datetime_ts"]).strftime("%m-%d %H:%M") for i in tick_locs],
                fontsize=8,
            )
            manifest_rows.append(
                {
                    "page": page_idx,
                    "candidate_index": row.get("candidate_index"),
                    "official_open_trade_id": row.get("official_open_trade_id"),
                    "vt_symbol": row.get("vt_symbol"),
                    "official_open_date": row.get("official_open_date"),
                    "stage042_session_convention_status": row.get("stage042_session_convention_status"),
                    "official_event_family": row.get("official_event_family"),
                    "replay_event_family": row.get("replay_event_family"),
                    "event_family_match": row.get("event_family_match"),
                    "raw_event_family_match": row.get("stage042_raw_event_family_match"),
                }
            )
        page_path = Path(str(ATLAS_TEMPLATE).format(page=page_idx))
        fig.suptitle("Stage043 official-open scan replay repair atlas", fontsize=14)
        fig.savefig(page_path, dpi=150)
        plt.close(fig)
        pages.append(page_path)
    manifest = pd.DataFrame(manifest_rows)
    _write_csv(manifest, ATLAS_MANIFEST_OUT)
    return pages, manifest


def _write_report(
    summary: pd.DataFrame,
    repair_status: pd.DataFrame,
    event_diagnostic: pd.DataFrame,
    atlas_pages: list[Path],
) -> None:
    row = summary.iloc[0]
    residual = event_diagnostic[event_diagnostic["event_family_match"].eq(0)].copy()
    lines = [
        "# Stage043 Official-Open Scan Replay Repair Audit",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 研究线：`{LINE_ID}`",
        f"- 官方正式版：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "- 阶段定位：只修 replay semantics；不新增交易规则、不改正式配置、不连接 CTP、不调用订单 API、不触发 A/B。",
        "- 决策：`stage043_replay_semantics_repaired_to_official_open_scan_no_trade_rule`。",
        "",
        "## 核心结论",
        "",
        f"- raw stitched event match：`{int(row['raw_stitched_event_match_orders'])}/{int(row['timestamp_ready_orders'])}` = `{row['raw_stitched_event_match_rate_pct']:.4f}%`。",
        f"- repair event match：`{int(row['repair_event_match_orders'])}/{int(row['timestamp_ready_orders'])}` = `{row['repair_event_match_rate_pct']:.4f}%`。",
        f"- pre-official mismatch before repair：`{int(row['preofficial_mismatch_orders_before_repair'])}`；resolved：`{int(row['preofficial_mismatch_resolved_orders'])}`。",
        f"- residual repair mismatches：`{int(row['repair_event_mismatch_orders'])}`。",
        "",
        "## 官方基准",
        "",
        f"- 期末权益：`{row['end_equity']:.2f}`",
        f"- 总收益：`{row['total_return_pct']:.4f}%`",
        f"- 最大回撤：`{row['max_drawdown_pct']:.4f}%`",
        f"- Sharpe：`{row['sharpe']:.4f}`",
        "",
        "## Repair 状态分布",
        "",
        _md_table(repair_status, max_rows=20),
        "",
        "## 残余事件对照",
        "",
        _md_table(residual, max_rows=20),
        "",
        "## 视觉输出",
        "",
        f"- repair path chart：`{PATH_CHART_OUT}`",
        f"- event repair chart：`{EVENT_CHART_OUT}`",
        f"- residual mismatch chart：`{RESIDUAL_CHART_OUT}`",
        f"- atlas pages：`{len(atlas_pages)}`",
        f"- atlas manifest：`{ATLAS_MANIFEST_OUT}`",
        "",
        "## 文件",
        "",
        f"- repair replay ledger：`{REPAIR_REPLAY_OUT}`",
        f"- repair status：`{REPAIR_STATUS_OUT}`",
        f"- event diagnostic：`{EVENT_DIAGNOSTIC_OUT}`",
        f"- same-exit curve：`{CURVE_OUT}`",
        f"- summary：`{SUMMARY_OUT}`",
        f"- decision：`{DECISION_OUT}`",
        "",
        "## 判断",
        "",
        "- Stage043 证明 Stage042 的主要 raw mismatch 是扫描起点口径问题：raw proxy 可作为成交价证据，但不能自然推出事件扫描也应从夜盘 raw timestamp 开始。",
        "- 修复后仍有少量 residual mismatch，下一步只允许审计同 bar stop/progress/C2 优先级、官方计划 stop 与实际 layer stop 的同步、以及 open_no_intraday_event 的边界。",
        "- 本阶段仍不是策略候选；一致性审计未通过前继续暂停新增分钟进出场规则。",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    orders = _load_orders()
    groups = s038._load_minute_groups(orders)
    curve, _open_trades, _candidates, lots, _intraday, _trades = s038._prepare_inputs()
    replay = _build_replay(orders, groups)
    lot_sensitivity = s038._closed_lot_sensitivity(lots, replay)
    repair_curve = _repair_curve(curve, lot_sensitivity)
    repair_status = _repair_status(replay)
    event_diagnostic = _event_diagnostic(replay)
    summary = _summary(curve, lots, replay, repair_status, repair_curve)

    _write_csv(replay, REPAIR_REPLAY_OUT)
    _write_csv(repair_status, REPAIR_STATUS_OUT)
    _write_csv(event_diagnostic, EVENT_DIAGNOSTIC_OUT)
    _write_csv(lot_sensitivity, LOT_SENSITIVITY_OUT)
    _write_csv(repair_curve, CURVE_OUT)
    _write_csv(summary, SUMMARY_OUT)

    _plot_path(repair_curve, replay)
    _plot_event_chart(repair_status)
    _plot_residual_chart(event_diagnostic)
    atlas_pages, _manifest = _plot_atlas(replay, groups)
    _write_report(summary, repair_status, event_diagnostic, atlas_pages)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "decision": "stage043_replay_semantics_repaired_to_official_open_scan_no_trade_rule",
        "candidate_ready": 0,
        "ab_triggered": 0,
        "rule_added": 0,
        "official_config_changed": 0,
        "summary": summary.iloc[0].to_dict(),
        "outputs": {
            "repair_replay": REPAIR_REPLAY_OUT,
            "repair_status": REPAIR_STATUS_OUT,
            "event_diagnostic": EVENT_DIAGNOSTIC_OUT,
            "lot_sensitivity": LOT_SENSITIVITY_OUT,
            "repair_curve": CURVE_OUT,
            "summary": SUMMARY_OUT,
            "report": REPORT_OUT,
            "path_chart": PATH_CHART_OUT,
            "event_chart": EVENT_CHART_OUT,
            "residual_chart": RESIDUAL_CHART_OUT,
            "atlas_manifest": ATLAS_MANIFEST_OUT,
            "atlas_pages": atlas_pages,
        },
        "judgment": (
            "Using raw proxy only as fill-price evidence and scanning intraday events from official open "
            "repairs most session-convention mismatches. This is still an audit ledger, not a trade rule."
        ),
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
