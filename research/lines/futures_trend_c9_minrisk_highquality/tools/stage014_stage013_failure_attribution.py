from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage014"
MODEL_TAG = "stage014_stage013_failure_attribution_v1"
OUTPUT_PREFIX = "qmt_roll_stage014_c9_minrisk_stage013_failure_attribution"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage013_minrisk_clean_restore_true_engine as s013
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage014_stage013_failure_attribution"
STAGE010_DIR = LINE_DIR / "outputs" / "stage010_authoritative_minute_coverage_audit"
STAGE013_DIR = LINE_DIR / "outputs" / "stage013_minrisk_clean_restore_true_engine"

START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-06-15")
CAPITAL = 150_000.0
PER_PAGE = 4
MAX_ATLAS_ROWS = 20

OFFICIAL_CLOSED_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_closed_lots_stage010_authoritative_minute_coverage_audit_v1.csv"
)
STAGE013_CLOSED_IN = (
    STAGE013_DIR
    / "qmt_roll_stage013_c9_minrisk_clean_restore_true_engine_closed_lots_stage013_minrisk_clean_restore_true_engine_v1.csv"
)
STAGE013_EVENTS_IN = (
    STAGE013_DIR
    / "qmt_roll_stage013_c9_minrisk_clean_restore_true_engine_quality_restore_events_stage013_minrisk_clean_restore_true_engine_v1.csv"
)
STAGE013_CURVE_IN = (
    STAGE013_DIR / "qmt_roll_stage013_c9_minrisk_clean_restore_true_engine_curve_stage013_minrisk_clean_restore_true_engine_v1.csv"
)
STAGE013_COMPARISON_IN = (
    STAGE013_DIR / "qmt_roll_stage013_c9_minrisk_clean_restore_true_engine_comparison_stage013_minrisk_clean_restore_true_engine_v1.csv"
)

LEDGER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_match_ledger_{MODEL_TAG}.csv"
BUCKET_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_attribution_{MODEL_TAG}.csv"
YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_attribution_{MODEL_TAG}.csv"
TOP_DELTA_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_negative_delta_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_attribution_chart_{MODEL_TAG}.png"
CONTRIB_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delta_contribution_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s013._json_safe(value)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s013._safe_float(value, default=default)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "No data."
    return s013._md_table(frame, max_rows=max_rows)


def _read_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _normalize_day(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce", format="mixed")
    if pd.isna(ts):
        return pd.NaT
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts.normalize()


def _state_group(value: Any) -> str:
    text = str(value)
    if text.startswith("clean_restore_stopped"):
        return "clean_restore_stopped"
    if text == "clean_restore_open":
        return "clean_restore_open"
    if text == "no_restore_not_clean_30m":
        return "no_restore_not_clean_30m"
    if text == "c9_stop_retry_before_quality_restore":
        return "c9_stop_retry_before_quality_restore"
    if text == "official_path_missing_stage861_observation":
        return "official_path_missing_stage861_observation"
    return text


def _prepare_closed(path: Path) -> pd.DataFrame:
    data = _read_required_csv(path)
    data["entry_day"] = data["entry_date"].map(_normalize_day)
    data["exit_day"] = data["exit_date"].map(_normalize_day)
    for column in ["realized_pnl", "volume", "r_multiple", "entry_price", "exit_price", "size"]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data


def _prepare_events() -> pd.DataFrame:
    events = _read_required_csv(STAGE013_EVENTS_IN)
    events["entry_day"] = events["datetime"].map(_normalize_day)
    events["entry_year"] = events["entry_day"].dt.year
    events["state_group"] = events["final_state"].map(_state_group)
    for column in [
        "entry_price",
        "risk_price",
        "original_volume",
        "scout_volume",
        "deferred_volume",
        "restore_volume",
        "estimated_restore_pnl",
        "first_30m_directional_r",
        "first_30m_mae_r",
        "clean_passed",
    ]:
        if column in events.columns:
            events[column] = pd.to_numeric(events[column], errors="coerce")
    return events


def _match_closed_lots(events: pd.DataFrame, official: pd.DataFrame, candidate: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for event_index, event in events.reset_index(drop=True).iterrows():
        base_mask = (
            official["vt_symbol"].astype(str).eq(str(event["vt_symbol"]))
            & official["direction"].astype(str).eq(str(event["direction"]))
            & official["entry_day"].eq(event["entry_day"])
        )
        c_mask = (
            candidate["vt_symbol"].astype(str).eq(str(event["vt_symbol"]))
            & candidate["direction"].astype(str).eq(str(event["direction"]))
            & candidate["entry_day"].eq(event["entry_day"])
        )
        official_lots = official.loc[base_mask].copy()
        candidate_lots = candidate.loc[c_mask].copy()
        official_pnl = float(pd.to_numeric(official_lots.get("realized_pnl", 0.0), errors="coerce").fillna(0.0).sum())
        candidate_pnl = float(pd.to_numeric(candidate_lots.get("realized_pnl", 0.0), errors="coerce").fillna(0.0).sum())
        official_positive = float(pd.to_numeric(official_lots.get("realized_pnl", 0.0), errors="coerce").clip(lower=0.0).fillna(0.0).sum())
        official_negative = float(pd.to_numeric(official_lots.get("realized_pnl", 0.0), errors="coerce").clip(upper=0.0).fillna(0.0).sum())
        candidate_positive = float(pd.to_numeric(candidate_lots.get("realized_pnl", 0.0), errors="coerce").clip(lower=0.0).fillna(0.0).sum())
        candidate_negative = float(pd.to_numeric(candidate_lots.get("realized_pnl", 0.0), errors="coerce").clip(upper=0.0).fillna(0.0).sum())
        official_exit_day = official_lots["exit_day"].max() if not official_lots.empty else pd.NaT
        rows.append(
            {
                "event_index": int(event_index),
                "entry_day": event["entry_day"],
                "entry_year": int(event["entry_year"]) if pd.notna(event["entry_year"]) else np.nan,
                "vt_symbol": event["vt_symbol"],
                "product_vt_symbol": event.get("product_vt_symbol", ""),
                "direction": event["direction"],
                "final_state": event["final_state"],
                "state_group": event["state_group"],
                "entry_price": _safe_float(event.get("entry_price")),
                "risk_price": _safe_float(event.get("risk_price")),
                "progress_price": _safe_float(event.get("progress_price")),
                "adverse_price": _safe_float(event.get("adverse_price")),
                "restore_price": _safe_float(event.get("restore_price")),
                "restore_time": event.get("restore_time", ""),
                "restore_stop_time": event.get("restore_stop_time", ""),
                "c9_first_stop_time": event.get("c9_first_stop_time", ""),
                "observation_end": event.get("observation_end", ""),
                "first_30m_directional_r": _safe_float(event.get("first_30m_directional_r")),
                "first_30m_mae_r": _safe_float(event.get("first_30m_mae_r")),
                "clean_passed": _safe_float(event.get("clean_passed"), 0.0),
                "original_volume": _safe_float(event.get("original_volume"), 0.0),
                "scout_volume": _safe_float(event.get("scout_volume"), 0.0),
                "deferred_volume": _safe_float(event.get("deferred_volume"), 0.0),
                "restore_volume": _safe_float(event.get("restore_volume"), 0.0),
                "estimated_restore_pnl": _safe_float(event.get("estimated_restore_pnl"), 0.0),
                "official_lots": int(len(official_lots)),
                "candidate_lots": int(len(candidate_lots)),
                "official_volume": float(pd.to_numeric(official_lots.get("volume", 0.0), errors="coerce").fillna(0.0).sum()),
                "candidate_volume": float(pd.to_numeric(candidate_lots.get("volume", 0.0), errors="coerce").fillna(0.0).sum()),
                "official_pnl": official_pnl,
                "candidate_pnl": candidate_pnl,
                "delta_candidate_minus_official": candidate_pnl - official_pnl,
                "official_positive_pnl": official_positive,
                "official_negative_pnl": official_negative,
                "candidate_positive_pnl": candidate_positive,
                "candidate_negative_pnl": candidate_negative,
                "official_exit_day": official_exit_day,
                "match_status": "exact_event_entry_match" if len(official_lots) else "unmatched_official_closed_lot",
            }
        )
    ledger = pd.DataFrame(rows)
    ledger["official_exit_day"] = pd.to_datetime(ledger["official_exit_day"], errors="coerce")
    return ledger


def _bucket_stats(ledger: pd.DataFrame) -> pd.DataFrame:
    stats = (
        ledger.groupby("state_group", dropna=False)
        .agg(
            events=("event_index", "size"),
            matched_events=("official_lots", lambda x: int((pd.to_numeric(x, errors="coerce") > 0).sum())),
            products=("product_vt_symbol", "nunique"),
            years=("entry_year", "nunique"),
            official_pnl=("official_pnl", "sum"),
            candidate_pnl=("candidate_pnl", "sum"),
            delta_candidate_minus_official=("delta_candidate_minus_official", "sum"),
            official_positive_pnl=("official_positive_pnl", "sum"),
            official_negative_pnl=("official_negative_pnl", "sum"),
            candidate_positive_pnl=("candidate_positive_pnl", "sum"),
            candidate_negative_pnl=("candidate_negative_pnl", "sum"),
            original_volume=("original_volume", "sum"),
            scout_volume=("scout_volume", "sum"),
            deferred_volume=("deferred_volume", "sum"),
            restore_volume=("restore_volume", "sum"),
            estimated_restore_pnl=("estimated_restore_pnl", "sum"),
            median_first_30m_directional_r=("first_30m_directional_r", "median"),
            median_first_30m_mae_r=("first_30m_mae_r", "median"),
        )
        .reset_index()
        .sort_values("delta_candidate_minus_official")
    )
    total_delta = float(stats["delta_candidate_minus_official"].sum())
    stats["delta_share_pct"] = np.where(
        abs(total_delta) > 1e-9,
        stats["delta_candidate_minus_official"] / total_delta * 100.0,
        np.nan,
    )
    return stats


def _year_stats(ledger: pd.DataFrame) -> pd.DataFrame:
    return (
        ledger.groupby(["entry_year", "state_group"], dropna=False)
        .agg(
            events=("event_index", "size"),
            official_pnl=("official_pnl", "sum"),
            candidate_pnl=("candidate_pnl", "sum"),
            delta_candidate_minus_official=("delta_candidate_minus_official", "sum"),
            deferred_volume=("deferred_volume", "sum"),
            restore_volume=("restore_volume", "sum"),
        )
        .reset_index()
        .sort_values(["entry_year", "delta_candidate_minus_official"])
    )


def _plot_path_attribution(curve: pd.DataFrame, ledger: pd.DataFrame) -> None:
    data = curve.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed")
    top = ledger.sort_values("delta_candidate_minus_official").head(12)
    fig, axes = plt.subplots(3, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    colors = {
        s013.A_ARM: "#2563eb",
        s013.C_ARM: "#0f766e",
    }
    labels = {
        s013.A_ARM: "A official C9/15w",
        s013.C_ARM: "C Stage013 min-risk clean restore",
    }
    for arm, group in data.groupby("arm"):
        group = group.sort_values("date")
        axes[0].plot(group["date"], group["account_equity"], label=labels.get(arm, arm), color=colors.get(arm))
        axes[1].plot(group["date"], group["drawdown_pct"], label=labels.get(arm, arm), color=colors.get(arm))
        axes[2].plot(group["date"], group["broker10_margin_to_equity_pct"], label=labels.get(arm, arm), color=colors.get(arm))
    for _, row in top.iterrows():
        when = pd.to_datetime(row["entry_day"], errors="coerce")
        if pd.isna(when):
            continue
        for ax in axes:
            ax.axvline(when, color="#dc2626", alpha=0.18, linewidth=0.9)
    axes[0].set_title("Stage014 A/C path with top Stage013 event-level PnL-delta markers")
    axes[1].set_title("Drawdown")
    axes[2].set_title("Broker10 margin to equity pct")
    axes[2].axhline(100.0, color="#dc2626", linestyle="--", linewidth=0.9, alpha=0.7)
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best")
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_delta_contribution(ledger: pd.DataFrame) -> None:
    data = ledger.copy()
    data["sort_day"] = pd.to_datetime(data["official_exit_day"], errors="coerce")
    data["sort_day"] = data["sort_day"].fillna(pd.to_datetime(data["entry_day"], errors="coerce"))
    groups = sorted(data["state_group"].dropna().unique())
    fig, axes = plt.subplots(2, 1, figsize=(18, 10), sharex=True, constrained_layout=True)
    colors = {
        "clean_restore_open": "#2563eb",
        "clean_restore_stopped": "#dc2626",
        "no_restore_not_clean_30m": "#7c3aed",
        "c9_stop_retry_before_quality_restore": "#ea580c",
        "official_path_missing_stage861_observation": "#64748b",
    }
    for group in groups:
        part = data[data["state_group"].eq(group)].copy().sort_values("sort_day")
        if part.empty:
            continue
        part["cum_delta"] = part["delta_candidate_minus_official"].cumsum()
        part["cum_official"] = part["official_pnl"].cumsum()
        axes[0].step(part["sort_day"], part["cum_delta"], where="post", label=group, color=colors.get(group))
        axes[1].step(part["sort_day"], part["cum_official"], where="post", label=group, color=colors.get(group))
    all_data = data.sort_values("sort_day")
    all_data["cum_delta"] = all_data["delta_candidate_minus_official"].cumsum()
    all_data["cum_official"] = all_data["official_pnl"].cumsum()
    axes[0].step(all_data["sort_day"], all_data["cum_delta"], where="post", color="#111827", linewidth=2.0, label="ALL")
    axes[1].step(all_data["sort_day"], all_data["cum_official"], where="post", color="#111827", linewidth=2.0, label="ALL")
    axes[0].set_title("C minus A event-level realized PnL delta by Stage013 state")
    axes[1].set_title("Official realized PnL carried by those Stage013 event states")
    for ax in axes:
        ax.axhline(0.0, color="#334155", linewidth=0.8, alpha=0.7)
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best", fontsize=8)
    fig.savefig(CONTRIB_CHART_OUT, dpi=170)
    plt.close(fig)


def _select_atlas_events(ledger: pd.DataFrame) -> pd.DataFrame:
    selected: list[pd.DataFrame] = []
    selected.append(ledger.sort_values("delta_candidate_minus_official").head(8))
    no_restore = ledger[ledger["state_group"].eq("no_restore_not_clean_30m")].sort_values("official_pnl", ascending=False).head(4)
    if not no_restore.empty:
        selected.append(no_restore)
    stopped_winners = ledger[
        ledger["state_group"].eq("clean_restore_stopped") & ledger["official_pnl"].gt(0)
    ].sort_values("official_pnl", ascending=False).head(4)
    if not stopped_winners.empty:
        selected.append(stopped_winners)
    c9_winners = ledger[
        ledger["state_group"].eq("c9_stop_retry_before_quality_restore") & ledger["official_pnl"].gt(0)
    ].sort_values("official_pnl", ascending=False).head(4)
    if not c9_winners.empty:
        selected.append(c9_winners)
    return (
        pd.concat(selected, ignore_index=True, sort=False)
        .drop_duplicates(["event_index"])
        .head(MAX_ATLAS_ROWS)
    )


def _plot_atlas(ledger: pd.DataFrame, minute_bars: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_events(ledger)
    if selected.empty:
        return [], pd.DataFrame()
    minute_by_symbol = s013.s002.s825._minute_groups(minute_bars)
    pages = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.2, 3.4 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            vt_symbol = str(row["vt_symbol"])
            entry_day = pd.Timestamp(row["entry_day"])
            day = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            day = (
                day[day["bar_date"].eq(entry_day)].copy().sort_values("bar_datetime").head(520).reset_index(drop=True)
                if not day.empty
                else pd.DataFrame()
            )
            if day.empty:
                ax.axis("off")
                ax.text(0.5, 0.5, f"missing minute bars {vt_symbol} {entry_day:%Y-%m-%d}", ha="center", va="center")
            else:
                s013.s002.s825._plot_candles(ax, day)
                for price_col, color, linestyle, label in [
                    ("entry_price", "#2563eb", "-", "entry"),
                    ("progress_price", "#16a34a", "--", "+0.5R progress"),
                    ("adverse_price", "#dc2626", ":", "-0.5R stop"),
                    ("restore_price", "#7c3aed", "-.", "restore"),
                    ("entry_price", "#ea580c", "-.", "restore stop at entry"),
                ]:
                    price = _safe_float(row.get(price_col))
                    if np.isfinite(price):
                        ax.axhline(price, color=color, linestyle=linestyle, linewidth=0.9, label=label)
                for time_col, color, label in [
                    ("observation_end", "#64748b", "30m check"),
                    ("restore_time", "#7c3aed", "restore"),
                    ("restore_stop_time", "#ea580c", "restore stop"),
                    ("c9_first_stop_time", "#dc2626", "C9 stop"),
                ]:
                    idx = s013._index_for_time(day, row.get(time_col))
                    if idx >= 0:
                        ax.axvline(idx, color=color, linewidth=1.0, alpha=0.85, label=label)
                ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    dedup = dict(zip(labels, handles))
                    ax.legend(dedup.values(), dedup.keys(), loc="best", fontsize=7)
                ax.grid(True, alpha=0.18)
            ax.set_title(
                (
                    f"{vt_symbol} {row.get('direction')} {entry_day:%Y-%m-%d} {row.get('state_group')} "
                    f"A={_safe_float(row.get('official_pnl'), 0):,.0f} C={_safe_float(row.get('candidate_pnl'), 0):,.0f} "
                    f"delta={_safe_float(row.get('delta_candidate_minus_official'), 0):,.0f} "
                    f"orig/scout/rest={int(_safe_float(row.get('original_volume'), 0))}/"
                    f"{int(_safe_float(row.get('scout_volume'), 0))}/"
                    f"{int(_safe_float(row.get('restore_volume'), 0))}"
                ),
                fontsize=8.2,
                loc="left",
            )
            manifest.append(
                {
                    "page": page,
                    "event_index": int(row["event_index"]),
                    "vt_symbol": vt_symbol,
                    "entry_day": entry_day.strftime("%Y-%m-%d"),
                    "direction": row.get("direction", ""),
                    "state_group": row.get("state_group", ""),
                    "official_pnl": _safe_float(row.get("official_pnl")),
                    "candidate_pnl": _safe_float(row.get("candidate_pnl")),
                    "delta_candidate_minus_official": _safe_float(row.get("delta_candidate_minus_official")),
                }
            )
        fig.suptitle("Stage014 Stage013 failure attribution minute-K atlas", fontsize=12)
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=170)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _summary(ledger: pd.DataFrame, bucket: pd.DataFrame) -> pd.DataFrame:
    matched = int(ledger["official_lots"].gt(0).sum())
    total = int(len(ledger))
    clean_open = bucket[bucket["state_group"].eq("clean_restore_open")]
    no_restore = bucket[bucket["state_group"].eq("no_restore_not_clean_30m")]
    c9_stop = bucket[bucket["state_group"].eq("c9_stop_retry_before_quality_restore")]
    stopped = bucket[bucket["state_group"].eq("clean_restore_stopped")]
    row = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "stage013_events": total,
        "exact_matched_events": matched,
        "unmatched_events": total - matched,
        "event_level_official_pnl": float(ledger["official_pnl"].sum()),
        "event_level_candidate_pnl": float(ledger["candidate_pnl"].sum()),
        "event_level_delta_candidate_minus_official": float(ledger["delta_candidate_minus_official"].sum()),
        "clean_restore_open_official_pnl": float(clean_open["official_pnl"].sum()) if not clean_open.empty else 0.0,
        "clean_restore_open_delta": float(clean_open["delta_candidate_minus_official"].sum()) if not clean_open.empty else 0.0,
        "no_restore_official_pnl": float(no_restore["official_pnl"].sum()) if not no_restore.empty else 0.0,
        "no_restore_delta": float(no_restore["delta_candidate_minus_official"].sum()) if not no_restore.empty else 0.0,
        "c9_stop_before_quality_official_pnl": float(c9_stop["official_pnl"].sum()) if not c9_stop.empty else 0.0,
        "c9_stop_before_quality_delta": float(c9_stop["delta_candidate_minus_official"].sum()) if not c9_stop.empty else 0.0,
        "clean_restore_stopped_official_pnl": float(stopped["official_pnl"].sum()) if not stopped.empty else 0.0,
        "clean_restore_stopped_delta": float(stopped["delta_candidate_minus_official"].sum()) if not stopped.empty else 0.0,
        "decision": "stage014_stage013_failure_attribution_no_trade_rule",
    }
    return pd.DataFrame([row])


def _decision(summary: pd.DataFrame) -> dict[str, Any]:
    row = summary.iloc[0].to_dict()
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": "stage014_stage013_failure_attribution_no_trade_rule",
        "summary": row,
        "order_api_called": False,
        "ctp_connected": False,
        "outputs": {
            "summary": str(SUMMARY_OUT),
            "ledger": str(LEDGER_OUT),
            "bucket": str(BUCKET_OUT),
            "year": str(YEAR_OUT),
            "top_delta": str(TOP_DELTA_OUT),
            "path_chart": str(PATH_CHART_OUT),
            "contribution_chart": str(CONTRIB_CHART_OUT),
            "atlas_manifest": str(ATLAS_MANIFEST_OUT),
            "report": str(REPORT_OUT),
            "decision": str(DECISION_OUT),
        },
        "external_research_judgment": (
            "Trend-following right-tail returns are path-dependent; attribution should isolate whether a proposed execution "
            "gate cuts winner exposure before designing any new rule. Stage014 is read-only and does not tune Stage013."
        ),
        "overfit_reflection_before": (
            "No: this is a read-only attribution using exact event/closed-lot joins and no new trading branch."
        ),
        "continue_value_before": (
            "Yes: Stage013 failed badly; identifying the failure mechanism is required before changing research direction."
        ),
        "overfit_reflection_after": (
            "No: no parameter or product/year/direction rule was selected; using this attribution to tune Stage013 would be overfitting."
        ),
        "continue_value_after": (
            "Yes for attribution, no for the Stage013 shape. The next step should avoid default minimum-risk gates unless an entry-time structure preserves right-tail exposure."
        ),
    }


def _write_report(
    summary: pd.DataFrame,
    bucket: pd.DataFrame,
    year: pd.DataFrame,
    top_delta: pd.DataFrame,
    atlas_paths: list[Path],
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage014 Stage013 failure attribution",
        "",
        f"- generated_at: `{datetime.now().strftime('%Y-%m-%d %H:%M')}`",
        f"- line_id: `{LINE_ID}`",
        f"- official: `{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "- type: read-only attribution; no trading rule, no CTP, no order API.",
        "- decision: `stage014_stage013_failure_attribution_no_trade_rule`",
        "",
        "## External Research Judgment",
        "",
        "- Trend-following research and open-source systematic backtesting projects emphasize right-tail path dependence and position-size accounting.",
        "- Intraday momentum evidence supports early path information, but Stage013 proves that using it as a broad default minimum-risk gate can destroy the trend-following right tail.",
        "- This stage therefore attributes failure before proposing any new candidate.",
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=5),
        "",
        "## Bucket Attribution",
        "",
        _md_table(bucket, max_rows=20),
        "",
        "## Year Attribution",
        "",
        _md_table(year, max_rows=60),
        "",
        "## Top Negative Event Deltas",
        "",
        _md_table(top_delta, max_rows=20),
        "",
        "## Visual Outputs",
        "",
        f"- path attribution chart: `{PATH_CHART_OUT}`",
        f"- delta contribution chart: `{CONTRIB_CHART_OUT}`",
        *[f"- minute atlas: `{path}`" for path in atlas_paths],
        "",
        "## Judgment",
        "",
        f"- overfit_reflection_before: `{decision['overfit_reflection_before']}`",
        f"- overfit_reflection_after: `{decision['overfit_reflection_after']}`",
        f"- continue_value_before: `{decision['continue_value_before']}`",
        f"- continue_value_after: `{decision['continue_value_after']}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("[stage014] loading Stage013/official ledgers", flush=True)
    events = _prepare_events()
    official = _prepare_closed(OFFICIAL_CLOSED_IN)
    candidate = _prepare_closed(STAGE013_CLOSED_IN)
    ledger = _match_closed_lots(events, official, candidate)
    bucket = _bucket_stats(ledger)
    year = _year_stats(ledger)
    top_delta = ledger.sort_values("delta_candidate_minus_official").head(30).copy()
    summary = _summary(ledger, bucket)

    print("[stage014] loading curve and minute bars for visuals", flush=True)
    curve = _read_required_csv(STAGE013_CURVE_IN)
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    metadata = s013.s002.s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s013.s002.s928._load_stage861_full_minute_bars(vt_symbols)

    _plot_path_attribution(curve, ledger)
    _plot_delta_contribution(ledger)
    atlas_paths, atlas_manifest = _plot_atlas(ledger, minute_bars)
    decision = _decision(summary)

    ledger.to_csv(LEDGER_OUT, index=False, encoding="utf-8-sig")
    bucket.to_csv(BUCKET_OUT, index=False, encoding="utf-8-sig")
    year.to_csv(YEAR_OUT, index=False, encoding="utf-8-sig")
    top_delta.to_csv(TOP_DELTA_OUT, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    _write_report(summary, bucket, year, top_delta, atlas_paths, decision)
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("summary")
    print(summary.to_string(index=False))
    print("bucket")
    print(bucket.to_string(index=False))


if __name__ == "__main__":
    main()
