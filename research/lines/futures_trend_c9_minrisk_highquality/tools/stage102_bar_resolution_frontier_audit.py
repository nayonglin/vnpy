from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage102"
MODEL_TAG = "stage102_bar_resolution_frontier_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage102_c9_minrisk_bar_resolution_frontier_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOLS_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for path in [str(TOOLS_DIR), str(EXAMPLE_DIR)]:
    if path not in sys.path:
        sys.path.insert(0, path)

import stage038_order_event_replay_prototype_audit as s038  # noqa: E402
import stage045_event_time_field_sync_audit as s045  # noqa: E402
import stage100_absorption_reclaim_preflight as s100  # noqa: E402


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage102_bar_resolution_frontier_audit"

STAGE100_ROWS_IN = (
    LINE_DIR
    / "outputs"
    / "stage100_absorption_reclaim_preflight"
    / "qmt_roll_stage100_c9_minrisk_absorption_reclaim_preflight_preflight_rows_"
    "stage100_absorption_reclaim_preflight_v1.csv"
)

RESOLUTION_ROWS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_resolution_rows_{MODEL_TAG}.csv"
BUCKET_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
EVENT_TIMING_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_timing_summary_{MODEL_TAG}.csv"
PROMOTION_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"

OFFICIAL_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_chart_{MODEL_TAG}.png"
BUCKET_CONTRIBUTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_contribution_chart_{MODEL_TAG}.png"
BUCKET_SUMMARY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_chart_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_chart_{MODEL_TAG}.png"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

PROGRESS_R = 0.5
STOP_R = -0.5
ATLAS_ROWS = 24
ATLAS_PER_PAGE = 4
MAX_ATLAS_BARS = 100
MAXDD_START = pd.Timestamp("2022-05-30")
MAXDD_END = pd.Timestamp("2023-03-09")

BUCKET_ORDER = [
    "same_bar_stop_progress_ambiguous",
    "first_bar_event_no_closed_bar",
    "one_bar_event_close_action_collision",
    "two_to_five_bar_short_runway",
    "gt_five_bar_runway",
    "no_c9_stop_or_progress_before_day_end",
    "invalid_or_missing_minute_path",
]

BUCKET_COLORS = {
    "same_bar_stop_progress_ambiguous": "#7f1d1d",
    "first_bar_event_no_closed_bar": "#dc2626",
    "one_bar_event_close_action_collision": "#f97316",
    "two_to_five_bar_short_runway": "#eab308",
    "gt_five_bar_runway": "#0f766e",
    "no_c9_stop_or_progress_before_day_end": "#2563eb",
    "invalid_or_missing_minute_path": "#64748b",
}


def _json_safe(value: Any) -> Any:
    return s045._json_safe(value)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s045._safe_float(value, default=default)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s038._md_table(frame, max_rows=max_rows)


def _event_bar_index(path: pd.DataFrame, event_time: Any, fallback_count: Any) -> float:
    event_ts = pd.to_datetime(event_time, errors="coerce")
    if pd.notna(event_ts) and not path.empty:
        times = pd.to_datetime(path["bar_datetime_ts"], errors="coerce")
        hits = np.where(times.eq(pd.Timestamp(event_ts)).to_numpy())[0]
        if len(hits):
            return float(hits[0])
    count = _safe_float(fallback_count)
    if np.isfinite(count) and count >= 1:
        return float(count - 1)
    return np.nan


def _resolution_bucket(row: pd.Series) -> str:
    if int(row.get("valid_minute_path", 0)) == 0:
        return "invalid_or_missing_minute_path"
    if str(row.get("replay_c9_first_event", "")) not in {"stop", "progress"}:
        return "no_c9_stop_or_progress_before_day_end"
    if int(row.get("same_bar_stop_progress_ambiguous", 0)) == 1:
        return "same_bar_stop_progress_ambiguous"
    event_idx = _safe_float(row.get("event_bar_idx"))
    if not np.isfinite(event_idx):
        return "invalid_or_missing_minute_path"
    if event_idx <= 0:
        return "first_bar_event_no_closed_bar"
    if event_idx == 1:
        return "one_bar_event_close_action_collision"
    if event_idx <= 5:
        return "two_to_five_bar_short_runway"
    return "gt_five_bar_runway"


def _prepare_rows(stage100_rows: pd.DataFrame, merged: pd.DataFrame, groups: dict[str, pd.DataFrame]) -> pd.DataFrame:
    merged_index = merged.set_index("candidate_index", drop=False)
    output_rows: list[dict[str, Any]] = []
    for _, item in stage100_rows.iterrows():
        candidate_index = item.get("candidate_index")
        if candidate_index not in merged_index.index:
            continue
        source = merged_index.loc[candidate_index]
        if isinstance(source, pd.DataFrame):
            source = source.iloc[0]

        scan = s100._pre_event_scan(source, groups)
        entry = _safe_float(item.get("entry_price"))
        risk = _safe_float(item.get("risk_price"))
        sign = s038._direction_sign(item.get("direction"))
        path = pd.DataFrame()
        if not scan.empty and np.isfinite(entry) and np.isfinite(risk) and risk > 0 and sign in {-1, 1}:
            path = s100._path_arrays(scan, entry, risk, sign)
        valid = int(not path.empty)
        event_idx = _event_bar_index(path, item.get("replay_c9_first_event_time"), item.get("pre_event_bar_count"))

        event_high_r = np.nan
        event_low_r = np.nan
        event_close_r = np.nan
        event_progress_touched = 0
        event_stop_touched = 0
        same_bar_stop_progress = 0
        minutes_to_event = np.nan
        completed_bars_before_event = np.nan
        if valid and np.isfinite(event_idx) and 0 <= int(event_idx) < len(path):
            event_bar = path.iloc[int(event_idx)]
            event_high_r = _safe_float(event_bar.get("high_r"))
            event_low_r = _safe_float(event_bar.get("low_r"))
            event_close_r = _safe_float(event_bar.get("close_r"))
            event_progress_touched = int(np.isfinite(event_high_r) and event_high_r >= PROGRESS_R)
            event_stop_touched = int(np.isfinite(event_low_r) and event_low_r <= STOP_R)
            same_bar_stop_progress = int(event_progress_touched == 1 and event_stop_touched == 1)
            start_time = pd.to_datetime(path.iloc[0].get("bar_datetime_ts"), errors="coerce")
            event_time = pd.to_datetime(event_bar.get("bar_datetime_ts"), errors="coerce")
            if pd.notna(start_time) and pd.notna(event_time):
                minutes_to_event = (event_time - start_time).total_seconds() / 60.0
            completed_bars_before_event = max(float(event_idx), 0.0)

        has_c9_event = str(item.get("replay_c9_first_event", "")) in {"stop", "progress"}
        row = {
            **item.to_dict(),
            "valid_minute_path": valid,
            "event_bar_idx": event_idx,
            "completed_bars_before_event": completed_bars_before_event,
            "minutes_from_open_to_event": minutes_to_event,
            "event_bar_high_r": event_high_r,
            "event_bar_low_r": event_low_r,
            "event_bar_close_r": event_close_r,
            "event_bar_progress_touched": event_progress_touched,
            "event_bar_stop_touched": event_stop_touched,
            "same_bar_stop_progress_ambiguous": same_bar_stop_progress,
            "first_bar_event": int(valid and has_c9_event and np.isfinite(event_idx) and event_idx <= 0),
            "close_signal_next_bar_collision": int(valid and has_c9_event and np.isfinite(event_idx) and event_idx == 1),
            "two_to_five_bar_short_runway": int(valid and has_c9_event and np.isfinite(event_idx) and 2 <= event_idx <= 5),
            "gt_five_bar_runway": int(valid and has_c9_event and np.isfinite(event_idx) and event_idx > 5),
            "ohlc_actionability_allowed": 0,
            "true_engine_allowed": 0,
        }
        output_rows.append(row)

    rows = pd.DataFrame(output_rows)
    if rows.empty:
        return rows

    rows["official_open_date"] = pd.to_datetime(rows["official_open_date"], errors="coerce").dt.normalize()
    for column in [
        "order_realized_pnl",
        "right_tail_visual",
        "bottom_loss_visual",
        "maxdd_context",
        "same_bar_stop_progress_ambiguous",
        "first_bar_event",
        "close_signal_next_bar_collision",
        "two_to_five_bar_short_runway",
        "gt_five_bar_runway",
    ]:
        rows[column] = pd.to_numeric(rows[column], errors="coerce").fillna(0)
    rows["resolution_bucket"] = rows.apply(_resolution_bucket, axis=1)
    low_resolution = rows["resolution_bucket"].isin(
        [
            "same_bar_stop_progress_ambiguous",
            "first_bar_event_no_closed_bar",
            "one_bar_event_close_action_collision",
        ]
    )
    rows["low_resolution_zone"] = low_resolution.astype(int)
    rows["selected_for_atlas"] = 0
    selected: list[int] = []
    for condition in [
        rows["same_bar_stop_progress_ambiguous"].eq(1) & rows["right_tail_visual"].eq(1),
        rows["same_bar_stop_progress_ambiguous"].eq(1) & rows["bottom_loss_visual"].eq(1),
        rows["first_bar_event"].eq(1),
        rows["close_signal_next_bar_collision"].eq(1),
        rows["low_resolution_zone"].eq(1) & rows["maxdd_context"].eq(1),
        rows["right_tail_visual"].eq(1),
        rows["bottom_loss_visual"].eq(1),
        rows["gt_five_bar_runway"].eq(1),
    ]:
        subset = rows[condition].copy()
        subset = subset.reindex(subset["order_realized_pnl"].abs().sort_values(ascending=False).index)
        for idx in subset.head(6).index:
            if idx not in selected:
                selected.append(idx)
            if len(selected) >= ATLAS_ROWS:
                break
        if len(selected) >= ATLAS_ROWS:
            break
    rows.loc[selected[:ATLAS_ROWS], "selected_for_atlas"] = 1
    return rows.sort_values(["official_open_date", "candidate_index"]).reset_index(drop=True)


def _bucket_summary(rows: pd.DataFrame) -> pd.DataFrame:
    summary = (
        rows.groupby("resolution_bucket", dropna=False)
        .agg(
            order_count=("official_open_trade_id", "nunique"),
            lot_count=("order_lot_count", "sum"),
            pnl_sum=("order_realized_pnl", "sum"),
            pnl_min=("order_realized_pnl", "min"),
            pnl_max=("order_realized_pnl", "max"),
            right_tail_count=("right_tail_visual", "sum"),
            bottom_loss_count=("bottom_loss_visual", "sum"),
            maxdd_context_count=("maxdd_context", "sum"),
            same_bar_stop_progress_ambiguous_count=("same_bar_stop_progress_ambiguous", "sum"),
            first_bar_event_count=("first_bar_event", "sum"),
            close_signal_next_bar_collision_count=("close_signal_next_bar_collision", "sum"),
            median_event_bar_idx=("event_bar_idx", "median"),
            median_minutes_from_open_to_event=("minutes_from_open_to_event", "median"),
        )
        .reset_index()
    )
    summary["pnl_sign_conflict"] = (summary["pnl_min"].lt(0) & summary["pnl_max"].gt(0)).astype(int)
    summary["tail_conflict"] = (summary["right_tail_count"].gt(0) & summary["bottom_loss_count"].gt(0)).astype(int)
    summary["bucket_order"] = summary["resolution_bucket"].map({key: idx for idx, key in enumerate(BUCKET_ORDER)})
    return summary.sort_values("bucket_order").drop(columns=["bucket_order"]).reset_index(drop=True)


def _event_timing_summary(rows: pd.DataFrame) -> pd.DataFrame:
    data = rows.copy()
    data["event_type_for_timing"] = data["replay_c9_first_event"].where(
        data["replay_c9_first_event"].isin(["stop", "progress"]),
        "no_stop_or_progress",
    )
    summary = (
        data.groupby(["event_type_for_timing", "resolution_bucket"], dropna=False)
        .agg(
            order_count=("official_open_trade_id", "nunique"),
            pnl_sum=("order_realized_pnl", "sum"),
            right_tail_count=("right_tail_visual", "sum"),
            bottom_loss_count=("bottom_loss_visual", "sum"),
            low_resolution_zone_count=("low_resolution_zone", "sum"),
            median_event_bar_idx=("event_bar_idx", "median"),
        )
        .reset_index()
    )
    summary["bucket_order"] = summary["resolution_bucket"].map({key: idx for idx, key in enumerate(BUCKET_ORDER)})
    return summary.sort_values(["event_type_for_timing", "bucket_order"]).drop(columns=["bucket_order"]).reset_index(drop=True)


def _promotion_gate(rows: pd.DataFrame, bucket_summary: pd.DataFrame) -> pd.DataFrame:
    same_bar_dual = int(rows["same_bar_stop_progress_ambiguous"].sum())
    first_bar_events = int(rows["first_bar_event"].sum())
    close_collisions = int(rows["close_signal_next_bar_collision"].sum())
    low_resolution = rows[rows["low_resolution_zone"].eq(1)]
    rows_out = [
        {
            "gate_id": "same_bar_stop_progress_ordering",
            "evidence_value": same_bar_dual,
            "evidence_unit": "event bars where both +0.5R progress and -0.5R stop are touched",
            "pass_for_true_engine": int(same_bar_dual == 0),
            "judgment": "pass_no_dual_touch_observed" if same_bar_dual == 0 else "blocked_without_tick_ordering",
        },
        {
            "gate_id": "no_closed_bar_before_first_event",
            "evidence_value": first_bar_events,
            "evidence_unit": "orders whose C9 stop/progress occurs in the first scan bar",
            "pass_for_true_engine": 0,
            "judgment": "blocked_for_close_based_action",
        },
        {
            "gate_id": "close_signal_next_bar_collision",
            "evidence_value": close_collisions,
            "evidence_unit": "orders where a first close signal would execute in the same bar as C9 event",
            "pass_for_true_engine": 0,
            "judgment": "blocked_for_close_based_action",
        },
        {
            "gate_id": "right_tail_inside_low_resolution_zone",
            "evidence_value": int(low_resolution["right_tail_visual"].sum()),
            "evidence_unit": "right-tail visual orders inside low-resolution zone",
            "pass_for_true_engine": 0,
            "judgment": "blocked_by_right_tail_protection",
        },
        {
            "gate_id": "bottom_loss_not_separable_by_ohlc",
            "evidence_value": int(low_resolution["bottom_loss_visual"].sum()),
            "evidence_unit": "bottom-loss visual orders inside same low-resolution zone",
            "pass_for_true_engine": 0,
            "judgment": "blocked_by_non_separation",
        },
        {
            "gate_id": "bucket_tail_conflict",
            "evidence_value": int(bucket_summary["tail_conflict"].sum()) if not bucket_summary.empty else 0,
            "evidence_unit": "resolution buckets containing both right-tail and bottom-loss orders",
            "pass_for_true_engine": 0,
            "judgment": "blocked_by_mixed_tail_distribution",
        },
        {
            "gate_id": "authorized_orderflow_required",
            "evidence_value": 1,
            "evidence_unit": "tick/depth/latency/queue data route required before execution-sensitive rule",
            "pass_for_true_engine": 0,
            "judgment": "blocked_until_authorized_data",
        },
    ]
    gate = pd.DataFrame(rows_out)
    gate["preflight_only"] = 1
    gate["strategy_feature_usable"] = 0
    return gate


def _summary(
    curve: pd.DataFrame,
    lots: pd.DataFrame,
    rows: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    gate: pd.DataFrame,
) -> pd.DataFrame:
    metrics = s038._official_metrics(curve, lots)
    low_resolution = rows[rows["low_resolution_zone"].eq(1)]
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": "stage102_bar_resolution_frontier_blocks_ohlc_rule_no_rule",
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "timestamp_ready_order_count": int(len(rows)),
                "resolution_bucket_count": int(rows["resolution_bucket"].nunique()),
                "low_resolution_order_count": int(low_resolution["official_open_trade_id"].nunique()),
                "low_resolution_pnl_sum": float(low_resolution["order_realized_pnl"].sum()),
                "low_resolution_right_tail_count": int(low_resolution["right_tail_visual"].sum()),
                "low_resolution_bottom_loss_count": int(low_resolution["bottom_loss_visual"].sum()),
                "low_resolution_maxdd_context_count": int(low_resolution["maxdd_context"].sum()),
                "same_bar_stop_progress_ambiguous_order_count": int(rows["same_bar_stop_progress_ambiguous"].sum()),
                "first_bar_event_order_count": int(rows["first_bar_event"].sum()),
                "close_signal_next_bar_collision_order_count": int(rows["close_signal_next_bar_collision"].sum()),
                "two_to_five_bar_short_runway_order_count": int(rows["two_to_five_bar_short_runway"].sum()),
                "gt_five_bar_runway_order_count": int(rows["gt_five_bar_runway"].sum()),
                "tail_conflict_bucket_count": int(bucket_summary["tail_conflict"].sum()),
                "pnl_sign_conflict_bucket_count": int(bucket_summary["pnl_sign_conflict"].sum()),
                "promotion_gate_count": int(len(gate)),
                "promotion_gate_pass_count": int(pd.to_numeric(gate["pass_for_true_engine"], errors="coerce").sum()),
                "ohlc_actionability_allowed": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                **metrics,
            }
        ]
    )


def _plot_official_path(curve: pd.DataFrame, rows: pd.DataFrame, summary: pd.Series) -> None:
    data = curve.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [2.0, 1.0, 1.1]})
    axes[0].plot(data["date"], data["account_equity"], color="#0f172a", linewidth=1.2)
    axes[0].set_ylabel("equity")
    axes[0].grid(True, alpha=0.25)
    points = rows[["official_open_date", "resolution_bucket"]].merge(
        data[["date", "account_equity"]], left_on="official_open_date", right_on="date", how="left"
    )
    for bucket, group in points.groupby("resolution_bucket"):
        axes[0].scatter(
            group["official_open_date"],
            group["account_equity"],
            s=24,
            color=BUCKET_COLORS.get(bucket, "#64748b"),
            label=bucket,
            alpha=0.74,
        )
    axes[0].legend(loc="upper left", fontsize=7, ncol=2)
    axes[1].plot(data["date"], data["drawdown_pct"], color="#dc2626", linewidth=1.0)
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(True, alpha=0.25)
    counts = rows["resolution_bucket"].value_counts().reindex(BUCKET_ORDER).dropna()
    axes[2].bar(counts.index, counts.values, color=[BUCKET_COLORS.get(item, "#64748b") for item in counts.index])
    axes[2].set_ylabel("orders")
    axes[2].tick_params(axis="x", rotation=18)
    axes[2].grid(True, axis="y", alpha=0.25)
    axes[0].set_title(
        f"{STAGE} bar-resolution frontier | orders {int(summary['timestamp_ready_order_count'])} | true_engine_allowed=0"
    )
    fig.tight_layout()
    fig.savefig(OFFICIAL_PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_bucket_contribution(rows: pd.DataFrame) -> None:
    data = rows.sort_values(["official_open_date", "candidate_index"]).copy()
    fig, ax = plt.subplots(figsize=(13, 6))
    for bucket in BUCKET_ORDER:
        group = data[data["resolution_bucket"].eq(bucket)]
        if group.empty:
            continue
        series = group.groupby("official_open_date")["order_realized_pnl"].sum().sort_index().cumsum()
        ax.plot(series.index, series.values, label=bucket, color=BUCKET_COLORS.get(bucket, "#64748b"), linewidth=1.4)
    ax.axhline(0, color="#111827", linewidth=0.8)
    ax.set_title("Stage102 official realized PnL contribution by resolution bucket")
    ax.set_ylabel("cumulative realized PnL")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(BUCKET_CONTRIBUTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_bucket_summary(bucket_summary: pd.DataFrame) -> None:
    data = bucket_summary.copy()
    x = np.arange(len(data))
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True, gridspec_kw={"height_ratios": [1.0, 1.1]})
    colors = [BUCKET_COLORS.get(item, "#64748b") for item in data["resolution_bucket"]]
    axes[0].bar(x, data["order_count"], color=colors, alpha=0.84)
    axes[0].set_ylabel("orders")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[1].bar(x, data["pnl_sum"], color=colors, alpha=0.84)
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[1].set_ylabel("PnL sum")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(data["resolution_bucket"], rotation=18, ha="right")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[0].set_title("Stage102 bucket count and PnL; mixed low-resolution zones block promotion")
    fig.tight_layout()
    fig.savefig(BUCKET_SUMMARY_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 4.8))
    colors = np.where(pd.to_numeric(gate["pass_for_true_engine"], errors="coerce").fillna(0).eq(1), "#16a34a", "#dc2626")
    ax.bar(gate["gate_id"], gate["evidence_value"], color=colors, alpha=0.82)
    ax.set_ylabel("evidence value")
    ax.set_title("Stage102 promotion gates; OHLC actionability still blocked")
    ax.tick_params(axis="x", rotation=22)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_atlas(rows: pd.DataFrame, merged: pd.DataFrame, groups: dict[str, pd.DataFrame]) -> pd.DataFrame:
    selected = rows[rows["selected_for_atlas"].eq(1)].copy()
    selected = selected.head(ATLAS_ROWS)
    if selected.empty:
        return pd.DataFrame()
    merged_index = merged.set_index("candidate_index", drop=False)
    manifest_rows: list[dict[str, Any]] = []
    total_pages = int(np.ceil(len(selected) / ATLAS_PER_PAGE))
    for page in range(total_pages):
        chunk = selected.iloc[page * ATLAS_PER_PAGE : (page + 1) * ATLAS_PER_PAGE]
        fig, axes = plt.subplots(len(chunk), 1, figsize=(13, 3.2 * len(chunk)), squeeze=False)
        out_path = Path(str(ATLAS_TEMPLATE).format(page=page + 1))
        for ax, (_, item) in zip(axes[:, 0], chunk.iterrows()):
            source = merged_index.loc[item["candidate_index"]]
            if isinstance(source, pd.DataFrame):
                source = source.iloc[0]
            scan = s100._pre_event_scan(source, groups)
            entry = _safe_float(item.get("entry_price"))
            risk = _safe_float(item.get("risk_price"))
            sign = s038._direction_sign(item.get("direction"))
            if scan.empty or not np.isfinite(entry) or not np.isfinite(risk) or risk <= 0:
                ax.text(0.5, 0.5, "missing path", transform=ax.transAxes, ha="center", va="center")
                continue
            path = s100._path_arrays(scan, entry, risk, sign).head(MAX_ATLAS_BARS)
            x = path["bar_idx"]
            color = BUCKET_COLORS.get(item["resolution_bucket"], "#334155")
            ax.fill_between(x, path["low_r"], path["high_r"], color="#cbd5e1", alpha=0.48, label="bar high-low R")
            ax.plot(x, path["close_r"], color=color, linewidth=1.25, label="close R")
            ax.axhline(0, color="#111827", linewidth=0.8)
            ax.axhline(PROGRESS_R, color="#16a34a", linewidth=0.8, linestyle="--")
            ax.axhline(STOP_R, color="#dc2626", linewidth=0.8, linestyle="--")
            event_idx = _safe_float(item.get("event_bar_idx"))
            if np.isfinite(event_idx):
                ax.axvline(event_idx, color="#111827", linewidth=1.0, linestyle=":")
                if int(item.get("same_bar_stop_progress_ambiguous", 0)) == 1:
                    ax.axvspan(event_idx - 0.45, event_idx + 0.45, color="#fecaca", alpha=0.35)
            title = (
                f"{item['vt_symbol']} {item['direction']} {pd.Timestamp(item['official_open_date']).date()} | "
                f"{item['resolution_bucket']} | {item['replay_c9_first_event']}@bar {item['event_bar_idx']} | "
                f"pnl {item['order_realized_pnl']:,.0f} | rt {int(item['right_tail_visual'])} "
                f"bl {int(item['bottom_loss_visual'])} md {int(item['maxdd_context'])}"
            )
            ax.set_title(title, fontsize=9)
            ax.set_ylabel("directional R")
            ax.grid(True, alpha=0.25)
            manifest_rows.append(
                {
                    "page": page + 1,
                    "candidate_index": item["candidate_index"],
                    "official_open_trade_id": item["official_open_trade_id"],
                    "vt_symbol": item["vt_symbol"],
                    "direction": item["direction"],
                    "official_open_date": item["official_open_date"],
                    "resolution_bucket": item["resolution_bucket"],
                    "replay_c9_first_event": item["replay_c9_first_event"],
                    "event_bar_idx": item["event_bar_idx"],
                    "same_bar_stop_progress_ambiguous": item["same_bar_stop_progress_ambiguous"],
                    "order_realized_pnl": item["order_realized_pnl"],
                    "right_tail_visual": item["right_tail_visual"],
                    "bottom_loss_visual": item["bottom_loss_visual"],
                    "maxdd_context": item["maxdd_context"],
                    "atlas_path": str(out_path),
                }
            )
        axes[-1, 0].set_xlabel("minute bar index from replay open until C9 first event or day end")
        fig.tight_layout()
        fig.savefig(out_path, dpi=160)
        plt.close(fig)
    return pd.DataFrame(manifest_rows)


def _write_report(
    summary: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    event_timing_summary: pd.DataFrame,
    gate: pd.DataFrame,
    atlas_manifest: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    report = "\n".join(
        [
            f"# {STAGE} bar-resolution frontier audit",
            "",
            "## Decision",
            "",
            f"- decision: `{row['decision']}`",
            "- nature: read-only execution-resolution audit; no strategy rule, no true engine, no A/B, no CTP, no order API.",
            "- frozen question: can a new minute-OHLC rule safely decide near stop/progress without tick/depth ordering and next-bar execution runway?",
            "",
            "## Baseline Path",
            "",
            f"- end equity: `{row['end_equity']:,.2f}`",
            f"- total return: `{row['total_return_pct']:.4f}%`",
            f"- max drawdown: `{row['max_drawdown_pct']:.4f}%`",
            f"- Sharpe: `{row['sharpe']:.4f}`",
            f"- total slippage: `{row['total_slippage']:,.0f}`",
            f"- total trade count: `{row['total_trade_count']:.0f}`",
            f"- closed lot win rate: `{row['closed_lot_win_rate_pct']:.4f}%`",
            "",
            "## Resolution Summary",
            "",
            f"- timestamp-ready orders: `{int(row['timestamp_ready_order_count'])}`",
            f"- low-resolution orders: `{int(row['low_resolution_order_count'])}`",
            f"- low-resolution PnL: `{row['low_resolution_pnl_sum']:,.0f}`",
            f"- low-resolution right-tail orders: `{int(row['low_resolution_right_tail_count'])}`",
            f"- low-resolution bottom-loss orders: `{int(row['low_resolution_bottom_loss_count'])}`",
            f"- low-resolution maxDD-context orders: `{int(row['low_resolution_maxdd_context_count'])}`",
            f"- same-bar stop/progress ambiguity orders: `{int(row['same_bar_stop_progress_ambiguous_order_count'])}`",
            f"- first-bar event orders: `{int(row['first_bar_event_order_count'])}`",
            f"- close-signal next-bar collision orders: `{int(row['close_signal_next_bar_collision_order_count'])}`",
            f"- tail-conflict bucket count: `{int(row['tail_conflict_bucket_count'])}`",
            f"- promotion gate pass count: `{int(row['promotion_gate_pass_count'])}`",
            "",
            "## Bucket Summary",
            "",
            _md_table(bucket_summary, max_rows=20),
            "",
            "## Event Timing Summary",
            "",
            _md_table(event_timing_summary, max_rows=30),
            "",
            "## Promotion Gates",
            "",
            _md_table(gate, max_rows=20),
            "",
            "## Atlas Manifest",
            "",
            _md_table(atlas_manifest, max_rows=40),
            "",
            "## Visual Outputs",
            "",
            f"- official path chart: `{OFFICIAL_PATH_CHART_OUT}`",
            f"- bucket contribution chart: `{BUCKET_CONTRIBUTION_CHART_OUT}`",
            f"- bucket summary chart: `{BUCKET_SUMMARY_CHART_OUT}`",
            f"- promotion gate chart: `{GATE_CHART_OUT}`",
            f"- atlas manifest: `{ATLAS_MANIFEST_OUT}`",
            "",
            "## Judgment",
            "",
            (
                "The next execution-sensitive idea should not be built on one-minute OHLC alone. "
                "The low-resolution zone contains both right-tail and bottom-loss orders, so OHLC bars do not separate "
                "good from bad risk. Close-based actions also need the next bar for execution; when C9 stop/progress "
                "arrives in the first or second scan bar, the rule is not actionable without tick/depth/latency ordering."
            ),
            "",
        ]
    )
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage100_rows = _read_csv(STAGE100_ROWS_IN)
    merged, curve, lots, _intraday, groups = s045._prepare_event_sync_frame()
    rows = _prepare_rows(stage100_rows, merged, groups)
    bucket_summary = _bucket_summary(rows)
    event_timing_summary = _event_timing_summary(rows)
    gate = _promotion_gate(rows, bucket_summary)
    summary = _summary(curve, lots, rows, bucket_summary, gate)
    atlas_manifest = _plot_atlas(rows, merged, groups)

    _write_csv(rows, RESOLUTION_ROWS_OUT)
    _write_csv(bucket_summary, BUCKET_SUMMARY_OUT)
    _write_csv(event_timing_summary, EVENT_TIMING_SUMMARY_OUT)
    _write_csv(gate, PROMOTION_GATE_OUT)
    _write_csv(summary, SUMMARY_OUT)
    _write_csv(atlas_manifest, ATLAS_MANIFEST_OUT)

    _plot_official_path(curve, rows, summary.iloc[0])
    _plot_bucket_contribution(rows)
    _plot_bucket_summary(bucket_summary)
    _plot_gate(gate)
    _write_report(summary, bucket_summary, event_timing_summary, gate, atlas_manifest)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": str(summary.iloc[0]["decision"]),
        "summary_path": str(SUMMARY_OUT),
        "report_path": str(REPORT_OUT),
        "resolution_rows_path": str(RESOLUTION_ROWS_OUT),
        "bucket_summary_path": str(BUCKET_SUMMARY_OUT),
        "event_timing_summary_path": str(EVENT_TIMING_SUMMARY_OUT),
        "promotion_gate_path": str(PROMOTION_GATE_OUT),
        "atlas_manifest_path": str(ATLAS_MANIFEST_OUT),
        "charts": [
            str(OFFICIAL_PATH_CHART_OUT),
            str(BUCKET_CONTRIBUTION_CHART_OUT),
            str(BUCKET_SUMMARY_CHART_OUT),
            str(GATE_CHART_OUT),
        ],
        "promotion_gate_pass_count": int(summary.iloc[0]["promotion_gate_pass_count"]),
        "ohlc_actionability_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), indent=2))


if __name__ == "__main__":
    main()
