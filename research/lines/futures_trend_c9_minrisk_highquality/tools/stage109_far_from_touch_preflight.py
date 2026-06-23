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
STAGE = "Stage109"
MODEL_TAG = "stage109_far_from_touch_preflight_v1"
OUTPUT_PREFIX = "qmt_roll_stage109_c9_minrisk_far_from_touch_preflight"

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
OUTPUT_DIR = LINE_DIR / "outputs" / "stage109_far_from_touch_preflight"

STAGE102_ROWS_IN = (
    LINE_DIR
    / "outputs"
    / "stage102_bar_resolution_frontier_audit"
    / "qmt_roll_stage102_c9_minrisk_bar_resolution_frontier_audit_resolution_rows_"
    "stage102_bar_resolution_frontier_audit_v1.csv"
)
STAGE108_RISK_IN = (
    LINE_DIR
    / "outputs"
    / "stage108_post_oi_route_reset_risk_map"
    / "qmt_roll_stage108_c9_minrisk_post_oi_route_reset_risk_map_risk_event_map_"
    "stage108_post_oi_route_reset_risk_map_v1.csv"
)

PREFLIGHT_ROWS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_preflight_rows_{MODEL_TAG}.csv"
STATE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_summary_{MODEL_TAG}.csv"
ACCEPTANCE_OVERLAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_acceptance_overlap_{MODEL_TAG}.csv"
DISTINCTNESS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_distinctness_matrix_{MODEL_TAG}.csv"
PROMOTION_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"

OFFICIAL_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_chart_{MODEL_TAG}.png"
STATE_CONTRIBUTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_contribution_chart_{MODEL_TAG}.png"
PROMOTION_GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_chart_{MODEL_TAG}.png"
DISTINCTNESS_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_distinctness_heatmap_{MODEL_TAG}.png"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

FAR_FROM_TOUCH_BUCKETS = {
    "gt_five_bar_runway",
    "no_c9_stop_or_progress_before_day_end",
}
STATE_ORDER = [
    "near_touch_or_close_collision_blocked",
    "short_runway_touch_sensitive",
    "runway_without_near_touch",
    "day_end_no_c9_touch",
]
STATE_COLORS = {
    "near_touch_or_close_collision_blocked": "#dc2626",
    "short_runway_touch_sensitive": "#f97316",
    "runway_without_near_touch": "#0f766e",
    "day_end_no_c9_touch": "#2563eb",
}
ATLAS_ROWS = 20
ATLAS_PER_PAGE = 4
MAX_ATLAS_BARS = 160
PROGRESS_R = 0.5
STOP_R = -0.5


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


def _state_for_bucket(bucket: Any) -> str:
    text = str(bucket)
    if text in {"first_bar_event_no_closed_bar", "one_bar_event_close_action_collision"}:
        return "near_touch_or_close_collision_blocked"
    if text == "two_to_five_bar_short_runway":
        return "short_runway_touch_sensitive"
    if text == "gt_five_bar_runway":
        return "runway_without_near_touch"
    if text == "no_c9_stop_or_progress_before_day_end":
        return "day_end_no_c9_touch"
    return "near_touch_or_close_collision_blocked"


def _prepare_rows(stage102: pd.DataFrame, risk: pd.DataFrame) -> pd.DataFrame:
    rows = stage102.copy()
    rows["official_open_date"] = pd.to_datetime(rows["official_open_date"], errors="coerce").dt.normalize()
    risk_cols = [
        "candidate_index",
        "account_equity",
        "drawdown_pct",
        "broker10_margin_to_equity_pct",
        "risk_route_label",
        "orderflow_required",
    ]
    if all(column in risk.columns for column in risk_cols):
        rows = rows.merge(risk[risk_cols], on="candidate_index", how="left")
    for column in [
        "candidate_index",
        "order_lot_count",
        "order_realized_pnl",
        "right_tail_visual",
        "bottom_loss_visual",
        "maxdd_context",
        "low_resolution_zone",
        "first_bar_event",
        "close_signal_next_bar_collision",
        "two_to_five_bar_short_runway",
        "gt_five_bar_runway",
        "event_bar_idx",
        "pre_event_mfe_r",
        "pre_event_mae_r",
        "pre_event_close_r",
        "account_equity",
        "drawdown_pct",
        "broker10_margin_to_equity_pct",
    ]:
        if column in rows.columns:
            rows[column] = pd.to_numeric(rows[column], errors="coerce")

    rows["calendar_year"] = rows["official_open_date"].dt.year
    rows["far_from_touch_state"] = rows["resolution_bucket"].map(_state_for_bucket)
    rows["frozen_far_from_touch_proxy"] = rows["resolution_bucket"].isin(FAR_FROM_TOUCH_BUCKETS).astype(int)
    rows["near_touch_excluded_by_spec"] = rows["frozen_far_from_touch_proxy"]
    rows["close_next_bar_collision_excluded_by_spec"] = rows["frozen_far_from_touch_proxy"]
    rows["old_shape_overlap_stage064_time_stop_no_progress"] = rows["frozen_far_from_touch_proxy"]
    rows["old_shape_overlap_stage102_runway_bucket"] = rows["frozen_far_from_touch_proxy"]
    rows["new_independent_information_present"] = 0
    rows["preflight_rule_allowed"] = 0
    rows["true_engine_allowed"] = 0

    selected = []
    candidates = rows[rows["frozen_far_from_touch_proxy"].eq(1)].copy()
    selection_filters = [
        candidates["right_tail_visual"].eq(1),
        candidates["bottom_loss_visual"].eq(1),
        candidates["maxdd_context"].eq(1),
        candidates["far_from_touch_state"].eq("day_end_no_c9_touch"),
        candidates["far_from_touch_state"].eq("runway_without_near_touch"),
    ]
    for condition in selection_filters:
        subset = candidates[condition].copy()
        subset = subset.reindex(subset["order_realized_pnl"].abs().sort_values(ascending=False).index)
        for idx in subset.head(6).index:
            if idx not in selected:
                selected.append(idx)
            if len(selected) >= ATLAS_ROWS:
                break
        if len(selected) >= ATLAS_ROWS:
            break
    rows["selected_for_atlas"] = 0
    rows.loc[selected[:ATLAS_ROWS], "selected_for_atlas"] = 1
    return rows.sort_values(["official_open_date", "candidate_index"]).reset_index(drop=True)


def _state_summary(rows: pd.DataFrame) -> pd.DataFrame:
    summary = (
        rows.groupby("far_from_touch_state", dropna=False)
        .agg(
            order_count=("candidate_index", "count"),
            lot_count=("order_lot_count", "sum"),
            pnl_sum=("order_realized_pnl", "sum"),
            pnl_min=("order_realized_pnl", "min"),
            pnl_max=("order_realized_pnl", "max"),
            right_tail_count=("right_tail_visual", "sum"),
            bottom_loss_count=("bottom_loss_visual", "sum"),
            maxdd_context_count=("maxdd_context", "sum"),
            product_count=("product", "nunique"),
            year_count=("calendar_year", "nunique"),
            frozen_proxy_count=("frozen_far_from_touch_proxy", "sum"),
            old_shape_overlap_count=("old_shape_overlap_stage064_time_stop_no_progress", "sum"),
            independent_signal_count=("new_independent_information_present", "sum"),
        )
        .reset_index()
    )
    summary["tail_conflict"] = (summary["right_tail_count"].gt(0) & summary["bottom_loss_count"].gt(0)).astype(int)
    summary["pnl_sign_conflict"] = (summary["pnl_min"].lt(0) & summary["pnl_max"].gt(0)).astype(int)
    summary["state_order"] = summary["far_from_touch_state"].map({name: idx for idx, name in enumerate(STATE_ORDER)})
    return summary.sort_values("state_order").drop(columns=["state_order"]).reset_index(drop=True)


def _acceptance_overlap(rows: pd.DataFrame) -> pd.DataFrame:
    data = rows[rows["frozen_far_from_touch_proxy"].eq(1)].copy()
    if data.empty:
        return pd.DataFrame()
    grouped = (
        data.groupby(["far_from_touch_state", "resolution_bucket", "acceptance_state"], dropna=False)
        .agg(
            order_count=("candidate_index", "count"),
            pnl_sum=("order_realized_pnl", "sum"),
            right_tail_count=("right_tail_visual", "sum"),
            bottom_loss_count=("bottom_loss_visual", "sum"),
            maxdd_context_count=("maxdd_context", "sum"),
        )
        .reset_index()
    )
    return grouped.sort_values(["far_from_touch_state", "order_count"], ascending=[True, False]).reset_index(drop=True)


def _distinctness_matrix(rows: pd.DataFrame) -> pd.DataFrame:
    data = rows.copy()
    metrics: list[dict[str, Any]] = []
    for state in STATE_ORDER:
        group = data[data["far_from_touch_state"].eq(state)]
        if group.empty:
            continue
        far = group["frozen_far_from_touch_proxy"].eq(1)
        metrics.append(
            {
                "far_from_touch_state": state,
                "uses_only_elapsed_no_touch": int(far.any()),
                "overlaps_stage102_runway_or_no_event": int(far.any()),
                "overlaps_stage064_time_stop_no_progress": int(
                    group["old_shape_overlap_stage064_time_stop_no_progress"].sum() > 0
                ),
                "contains_mixed_absorption_reclaim_states": int(group["acceptance_state"].nunique(dropna=True) > 1),
                "new_external_or_orderflow_information": 0,
                "right_tail_present": int(group["right_tail_visual"].sum() > 0),
                "bottom_loss_present": int(group["bottom_loss_visual"].sum() > 0),
            }
        )
    return pd.DataFrame(metrics)


def _promotion_gate(rows: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    far = rows[rows["frozen_far_from_touch_proxy"].eq(1)]
    far_right_tail = int(far["right_tail_visual"].sum())
    far_bottom_loss = int(far["bottom_loss_visual"].sum())
    far_products = int(far["product"].nunique())
    far_years = int(far["calendar_year"].nunique())
    tail_conflict = int(far_right_tail > 0 and far_bottom_loss > 0)
    rows_out = [
        {
            "gate_id": "single_frozen_spec_defined",
            "evidence_value": 1,
            "evidence_unit": "one preflight spec only",
            "pass_for_true_engine": 1,
            "judgment": "pass_preflight_spec_frozen",
        },
        {
            "gate_id": "far_from_c9_touch_zone",
            "evidence_value": int(far["low_resolution_zone"].fillna(0).sum()),
            "evidence_unit": "low-resolution near-touch orders inside frozen proxy",
            "pass_for_true_engine": 1,
            "judgment": "pass_proxy_excludes_first_or_second_bar_touch_collision",
        },
        {
            "gate_id": "not_close_next_bar_collision",
            "evidence_value": int(far["close_signal_next_bar_collision"].fillna(0).sum()),
            "evidence_unit": "close-next-bar collisions inside frozen proxy",
            "pass_for_true_engine": 1,
            "judgment": "pass_no_immediate_collision_in_proxy",
        },
        {
            "gate_id": "not_old_time_stop_or_no_progress_shape",
            "evidence_value": int(far["old_shape_overlap_stage064_time_stop_no_progress"].sum()),
            "evidence_unit": "proxy orders whose only distinction is elapsed no-touch/no-progress",
            "pass_for_true_engine": 0,
            "judgment": "blocked_degenerates_to_stage064_shape",
        },
        {
            "gate_id": "independent_information_beyond_ohlc_absence",
            "evidence_value": int(far["new_independent_information_present"].sum()),
            "evidence_unit": "new external/orderflow fields",
            "pass_for_true_engine": 0,
            "judgment": "blocked_no_new_information",
        },
        {
            "gate_id": "right_tail_protection",
            "evidence_value": far_right_tail,
            "evidence_unit": "right-tail visual orders inside frozen proxy",
            "pass_for_true_engine": 0,
            "judgment": "blocked_proxy_contains_right_tail",
        },
        {
            "gate_id": "bottom_loss_separation",
            "evidence_value": tail_conflict,
            "evidence_unit": "proxy contains both right-tail and bottom-loss orders",
            "pass_for_true_engine": 0,
            "judgment": "blocked_mixed_tail_distribution",
        },
        {
            "gate_id": "cross_product_year_breadth",
            "evidence_value": far_products * 100 + far_years,
            "evidence_unit": "products*100 + years",
            "pass_for_true_engine": int(far_products >= 10 and far_years >= 5),
            "judgment": "pass_not_single_product_or_year" if far_products >= 10 and far_years >= 5 else "blocked_sparse_proxy",
        },
        {
            "gate_id": "true_engine_or_ab_allowed",
            "evidence_value": 0,
            "evidence_unit": "allowed true engine/A-B count",
            "pass_for_true_engine": 0,
            "judgment": "blocked_preflight_only",
        },
    ]
    gate = pd.DataFrame(rows_out)
    gate["preflight_only"] = 1
    gate["strategy_feature_usable"] = 0
    return gate


def _summary_frame(
    curve: pd.DataFrame,
    lots: pd.DataFrame,
    rows: pd.DataFrame,
    state_summary: pd.DataFrame,
    gate: pd.DataFrame,
) -> pd.DataFrame:
    metrics = s038._official_metrics(curve, lots)
    far = rows[rows["frozen_far_from_touch_proxy"].eq(1)]
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": "stage109_far_from_touch_preflight_degenerates_to_no_progress_no_rule",
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "timestamp_ready_order_count": int(len(rows)),
                "frozen_far_from_touch_proxy_order_count": int(len(far)),
                "frozen_far_from_touch_proxy_pnl_sum": float(far["order_realized_pnl"].sum()),
                "frozen_far_from_touch_proxy_right_tail_count": int(far["right_tail_visual"].sum()),
                "frozen_far_from_touch_proxy_bottom_loss_count": int(far["bottom_loss_visual"].sum()),
                "frozen_far_from_touch_proxy_maxdd_context_count": int(far["maxdd_context"].sum()),
                "frozen_far_from_touch_proxy_product_count": int(far["product"].nunique()),
                "frozen_far_from_touch_proxy_year_count": int(far["calendar_year"].nunique()),
                "far_proxy_old_shape_overlap_count": int(
                    far["old_shape_overlap_stage064_time_stop_no_progress"].sum()
                ),
                "far_proxy_independent_signal_count": int(far["new_independent_information_present"].sum()),
                "state_tail_conflict_count": int(state_summary["tail_conflict"].sum()) if not state_summary.empty else 0,
                "promotion_gate_count": int(len(gate)),
                "promotion_gate_pass_count": int(pd.to_numeric(gate["pass_for_true_engine"], errors="coerce").sum()),
                "preflight_rule_allowed": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                **metrics,
            }
        ]
    )


def _nearest_curve_points(curve: pd.DataFrame, rows: pd.DataFrame) -> pd.DataFrame:
    data = rows.copy()
    data["official_open_date"] = pd.to_datetime(data["official_open_date"], errors="coerce").dt.normalize()
    right = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].copy()
    right["date"] = pd.to_datetime(right["date"], errors="coerce").dt.normalize()
    right = right.sort_values("date")
    points = pd.merge_asof(
        data.sort_values("official_open_date"),
        right,
        left_on="official_open_date",
        right_on="date",
        direction="backward",
        suffixes=("", "_curve"),
    )
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        if column not in data.columns or data[column].isna().all():
            points[column] = points[f"{column}_curve"]
        else:
            points[column] = points[column].fillna(points[f"{column}_curve"])
    return points.sort_index()


def _plot_official_path(curve: pd.DataFrame, rows: pd.DataFrame, summary: pd.Series) -> None:
    curve = curve.copy()
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    points = _nearest_curve_points(
        curve,
        rows[rows["frozen_far_from_touch_proxy"].eq(1)]
        [
            [
                "candidate_index",
                "official_open_date",
                "far_from_touch_state",
                "right_tail_visual",
                "bottom_loss_visual",
                "maxdd_context",
                "account_equity",
                "drawdown_pct",
                "broker10_margin_to_equity_pct",
            ]
        ],
    )
    fig, axes = plt.subplots(3, 1, figsize=(15, 10), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#111827", lw=1.2)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#b91c1c", lw=1.0)
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#0369a1", lw=1.0)
    axes[2].axhline(100, color="#991b1b", ls="--", lw=0.8)
    axes[0].set_ylabel("equity (m)")
    axes[1].set_ylabel("drawdown %")
    axes[2].set_ylabel("broker10 %")
    for state, group in points.groupby("far_from_touch_state"):
        color = STATE_COLORS.get(state, "#64748b")
        size = np.where(group["bottom_loss_visual"].eq(1), 82, 42)
        edge = np.where(group["right_tail_visual"].eq(1), "#111827", "white")
        for ax, column, scale in [
            (axes[0], "account_equity", 1_000_000),
            (axes[1], "drawdown_pct", 1),
            (axes[2], "broker10_margin_to_equity_pct", 1),
        ]:
            ax.scatter(
                group["official_open_date"],
                group[column] / scale,
                s=size,
                c=color,
                edgecolors=edge,
                linewidths=0.6,
                alpha=0.82,
                label=state if ax is axes[0] else None,
            )
    axes[0].set_title(
        f"{STAGE} far-from-touch preflight | proxy orders {int(summary['frozen_far_from_touch_proxy_order_count'])} | true_engine_allowed=0"
    )
    axes[0].legend(loc="upper left", fontsize=8)
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(OFFICIAL_PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_state_contribution(rows: pd.DataFrame) -> None:
    data = rows.sort_values(["official_open_date", "candidate_index"]).copy()
    fig, ax = plt.subplots(figsize=(13, 6.5))
    for state in STATE_ORDER:
        group = data[data["far_from_touch_state"].eq(state)]
        if group.empty:
            continue
        series = group.groupby("official_open_date")["order_realized_pnl"].sum().sort_index().cumsum()
        ax.plot(series.index, series.values / 1_000_000, label=state, color=STATE_COLORS.get(state, "#64748b"), lw=1.4)
    ax.axhline(0, color="#111827", lw=0.8)
    ax.set_title("Stage109 official realized PnL contribution by far-from-touch preflight state")
    ax.set_ylabel("cumulative realized PnL (m)")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(STATE_CONTRIBUTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 5.2))
    colors = np.where(pd.to_numeric(gate["pass_for_true_engine"], errors="coerce").fillna(0).eq(1), "#15803d", "#dc2626")
    ax.barh(gate["gate_id"], gate["evidence_value"], color=colors, alpha=0.86)
    ax.set_xlabel("evidence value")
    ax.set_title("Stage109 promotion gates; independent-signal and right-tail gates block true engine")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(PROMOTION_GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_distinctness(matrix: pd.DataFrame) -> None:
    if matrix.empty:
        return
    columns = [
        "uses_only_elapsed_no_touch",
        "overlaps_stage102_runway_or_no_event",
        "overlaps_stage064_time_stop_no_progress",
        "contains_mixed_absorption_reclaim_states",
        "new_external_or_orderflow_information",
        "right_tail_present",
        "bottom_loss_present",
    ]
    data = matrix.set_index("far_from_touch_state")[columns]
    fig, ax = plt.subplots(figsize=(12, 5.2))
    image = ax.imshow(data.to_numpy(dtype=float), vmin=0, vmax=1, cmap="RdYlGn_r", aspect="auto")
    ax.set_xticks(range(len(columns)))
    ax.set_xticklabels(columns, rotation=25, ha="right")
    ax.set_yticks(range(len(data.index)))
    ax.set_yticklabels(data.index)
    for y in range(len(data.index)):
        for x in range(len(columns)):
            ax.text(x, y, str(int(data.iloc[y, x])), ha="center", va="center", fontsize=8)
    ax.set_title("Stage109 distinctness audit: red 1 means overlap/risk, green 0 means absent")
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(DISTINCTNESS_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_atlas(rows: pd.DataFrame, merged: pd.DataFrame, groups: dict[str, pd.DataFrame]) -> pd.DataFrame:
    selected = rows[rows["selected_for_atlas"].eq(1)].head(ATLAS_ROWS).copy()
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
            state = item["far_from_touch_state"]
            color = STATE_COLORS.get(state, "#334155")
            ax.fill_between(x, path["low_r"], path["high_r"], color="#cbd5e1", alpha=0.48, label="bar high-low R")
            ax.plot(x, path["close_r"], color=color, lw=1.2, label="close R")
            ax.axhline(0, color="#111827", lw=0.8)
            ax.axhline(PROGRESS_R, color="#16a34a", lw=0.8, ls="--")
            ax.axhline(STOP_R, color="#dc2626", lw=0.8, ls="--")
            event_idx = _safe_float(item.get("event_bar_idx"))
            if np.isfinite(event_idx):
                ax.axvline(event_idx, color="#111827", lw=0.9, ls=":")
            title = (
                f"{item['vt_symbol']} {item['direction']} {pd.Timestamp(item['official_open_date']).date()} | "
                f"{state} | {item['resolution_bucket']} | event {item['replay_c9_first_event']}@bar {item['event_bar_idx']} | "
                f"pnl {item['order_realized_pnl']:,.0f} | rt {int(item['right_tail_visual'])} "
                f"bl {int(item['bottom_loss_visual'])} md {int(item['maxdd_context'])}"
            )
            ax.set_title(title, fontsize=9)
            ax.set_ylabel("directional R")
            ax.grid(alpha=0.25)
            manifest_rows.append(
                {
                    "page": page + 1,
                    "candidate_index": item["candidate_index"],
                    "official_open_trade_id": item["official_open_trade_id"],
                    "vt_symbol": item["vt_symbol"],
                    "direction": item["direction"],
                    "official_open_date": item["official_open_date"],
                    "far_from_touch_state": item["far_from_touch_state"],
                    "resolution_bucket": item["resolution_bucket"],
                    "acceptance_state": item["acceptance_state"],
                    "replay_c9_first_event": item["replay_c9_first_event"],
                    "event_bar_idx": item["event_bar_idx"],
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
    state_summary: pd.DataFrame,
    acceptance_overlap: pd.DataFrame,
    distinctness: pd.DataFrame,
    gate: pd.DataFrame,
    atlas_manifest: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    report = "\n".join(
        [
            "# Stage109 far-from-touch preflight",
            "",
            "## Decision",
            "",
            f"- decision: `{row['decision']}`",
            "- nature: read-only preflight; no strategy rule, no true engine, no A/B, no CTP, no order API.",
            "- frozen question: can the remaining internal minute-OHLC route produce a genuinely new far-from-touch signal, not just elapsed no-touch/no-progress under another name?",
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
            "## Frozen Proxy Summary",
            "",
            f"- timestamp-ready orders: `{int(row['timestamp_ready_order_count'])}`",
            f"- frozen far-from-touch proxy orders: `{int(row['frozen_far_from_touch_proxy_order_count'])}`",
            f"- proxy PnL sum: `{row['frozen_far_from_touch_proxy_pnl_sum']:,.0f}`",
            f"- proxy right-tail orders: `{int(row['frozen_far_from_touch_proxy_right_tail_count'])}`",
            f"- proxy bottom-loss orders: `{int(row['frozen_far_from_touch_proxy_bottom_loss_count'])}`",
            f"- proxy maxDD-context orders: `{int(row['frozen_far_from_touch_proxy_maxdd_context_count'])}`",
            f"- proxy product/year breadth: `{int(row['frozen_far_from_touch_proxy_product_count'])}` products, `{int(row['frozen_far_from_touch_proxy_year_count'])}` years",
            f"- old-shape overlap count: `{int(row['far_proxy_old_shape_overlap_count'])}`",
            f"- independent new-signal count: `{int(row['far_proxy_independent_signal_count'])}`",
            f"- promotion gate pass count: `{int(row['promotion_gate_pass_count'])}/{int(row['promotion_gate_count'])}`",
            "",
            "## State Summary",
            "",
            _md_table(state_summary, max_rows=20),
            "",
            "## Acceptance Overlap",
            "",
            _md_table(acceptance_overlap, max_rows=30),
            "",
            "## Distinctness Matrix",
            "",
            _md_table(distinctness, max_rows=20),
            "",
            "## Promotion Gates",
            "",
            _md_table(gate, max_rows=20),
            "",
            "## Atlas Manifest",
            "",
            _md_table(atlas_manifest, max_rows=30),
            "",
            "## Visual Outputs",
            "",
            f"- official path chart: `{OFFICIAL_PATH_CHART_OUT}`",
            f"- state contribution chart: `{STATE_CONTRIBUTION_CHART_OUT}`",
            f"- promotion gate chart: `{PROMOTION_GATE_CHART_OUT}`",
            f"- distinctness heatmap: `{DISTINCTNESS_HEATMAP_OUT}`",
            f"- atlas manifest: `{ATLAS_MANIFEST_OUT}`",
            "",
            "## Judgment",
            "",
            (
                "The only internally available far-from-touch proxy is the absence of C9 stop/progress for a runway or until day-end. "
                "That is not a new signal; it collapses into the previously closed time-stop/no-progress family and the Stage102 runway bucket. "
                "The proxy also contains both right-tail and bottom-loss orders, so turning it into a reduction/exit/restore rule would either cut winners or fail to isolate the drawdown source."
            ),
            "",
        ]
    )
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage102 = _read_csv(STAGE102_ROWS_IN)
    risk = _read_csv(STAGE108_RISK_IN)
    merged, curve, lots, _intraday, groups = s045._prepare_event_sync_frame()
    rows = _prepare_rows(stage102, risk)
    state_summary = _state_summary(rows)
    acceptance_overlap = _acceptance_overlap(rows)
    distinctness = _distinctness_matrix(rows)
    gate = _promotion_gate(rows, state_summary)
    summary = _summary_frame(curve, lots, rows, state_summary, gate)
    atlas_manifest = _plot_atlas(rows, merged, groups)

    _write_csv(rows, PREFLIGHT_ROWS_OUT)
    _write_csv(state_summary, STATE_SUMMARY_OUT)
    _write_csv(acceptance_overlap, ACCEPTANCE_OVERLAP_OUT)
    _write_csv(distinctness, DISTINCTNESS_OUT)
    _write_csv(gate, PROMOTION_GATE_OUT)
    _write_csv(summary, SUMMARY_OUT)
    _write_csv(atlas_manifest, ATLAS_MANIFEST_OUT)

    _plot_official_path(curve, rows, summary.iloc[0])
    _plot_state_contribution(rows)
    _plot_gate(gate)
    _plot_distinctness(distinctness)
    _write_report(summary, state_summary, acceptance_overlap, distinctness, gate, atlas_manifest)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": str(summary.iloc[0]["decision"]),
        "summary_path": str(SUMMARY_OUT),
        "report_path": str(REPORT_OUT),
        "preflight_rows_path": str(PREFLIGHT_ROWS_OUT),
        "state_summary_path": str(STATE_SUMMARY_OUT),
        "acceptance_overlap_path": str(ACCEPTANCE_OVERLAP_OUT),
        "distinctness_matrix_path": str(DISTINCTNESS_OUT),
        "promotion_gate_path": str(PROMOTION_GATE_OUT),
        "atlas_manifest_path": str(ATLAS_MANIFEST_OUT),
        "charts": [
            str(OFFICIAL_PATH_CHART_OUT),
            str(STATE_CONTRIBUTION_CHART_OUT),
            str(PROMOTION_GATE_CHART_OUT),
            str(DISTINCTNESS_HEATMAP_OUT),
        ],
        "promotion_gate_pass_count": int(summary.iloc[0]["promotion_gate_pass_count"]),
        "preflight_rule_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), indent=2))


if __name__ == "__main__":
    main()
