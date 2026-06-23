from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage108"
MODEL_TAG = "stage108_post_oi_route_reset_risk_map_v1"
OUTPUT_PREFIX = "qmt_roll_stage108_c9_minrisk_post_oi_route_reset_risk_map"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage108_post_oi_route_reset_risk_map"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE102_ROWS_IN = (
    LINE_DIR
    / "outputs"
    / "stage102_bar_resolution_frontier_audit"
    / "qmt_roll_stage102_c9_minrisk_bar_resolution_frontier_audit_resolution_rows_"
    "stage102_bar_resolution_frontier_audit_v1.csv"
)
STAGE102_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage102_bar_resolution_frontier_audit"
    / "qmt_roll_stage102_c9_minrisk_bar_resolution_frontier_audit_summary_"
    "stage102_bar_resolution_frontier_audit_v1.csv"
)
STAGE102_BUCKET_IN = (
    LINE_DIR
    / "outputs"
    / "stage102_bar_resolution_frontier_audit"
    / "qmt_roll_stage102_c9_minrisk_bar_resolution_frontier_audit_bucket_summary_"
    "stage102_bar_resolution_frontier_audit_v1.csv"
)
STAGE103_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage103_orderflow_data_contract_audit"
    / "qmt_roll_stage103_c9_minrisk_orderflow_data_contract_audit_summary_"
    "stage103_orderflow_data_contract_audit_v1.csv"
)
STAGE103_ACTION_IN = (
    LINE_DIR
    / "outputs"
    / "stage103_orderflow_data_contract_audit"
    / "qmt_roll_stage103_c9_minrisk_orderflow_data_contract_audit_action_queue_"
    "stage103_orderflow_data_contract_audit_v1.csv"
)
STAGE103_CONTRACT_IN = (
    LINE_DIR
    / "outputs"
    / "stage103_orderflow_data_contract_audit"
    / "qmt_roll_stage103_c9_minrisk_orderflow_data_contract_audit_data_contract_"
    "stage103_orderflow_data_contract_audit_v1.csv"
)
STAGE107_FEATURES_IN = (
    LINE_DIR
    / "outputs"
    / "stage107_contract_month_oi_patched_root_reaudit"
    / "qmt_roll_stage107_c9_minrisk_contract_month_oi_patched_root_reaudit_features_"
    "stage107_contract_month_oi_patched_root_reaudit_v1.csv"
)
STAGE107_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage107_contract_month_oi_patched_root_reaudit"
    / "qmt_roll_stage107_c9_minrisk_contract_month_oi_patched_root_reaudit_summary_"
    "stage107_contract_month_oi_patched_root_reaudit_v1.csv"
)

ROUTE_SCORECARD_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_scorecard_{MODEL_TAG}.csv"
RISK_EVENT_MAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_risk_event_map_{MODEL_TAG}.csv"
BOTTOM_LOSS_MAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bottom_loss_route_map_{MODEL_TAG}.csv"
NEXT_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_route_gate_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_unresolved_risk_chart_{MODEL_TAG}.png"
ROUTE_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_scorecard_heatmap_{MODEL_TAG}.png"
BOTTOM_LOSS_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bottom_loss_route_chart_{MODEL_TAG}.png"
NEXT_GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_route_gate_chart_{MODEL_TAG}.png"


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
        out = float(value)
        return None if np.isnan(out) or np.isinf(out) else out
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    return value


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


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


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _load_rows() -> pd.DataFrame:
    rows = _read_csv(STAGE102_ROWS_IN)
    rows["official_open_date"] = pd.to_datetime(rows["official_open_date"], errors="coerce").dt.normalize()
    for column in [
        "candidate_index",
        "order_realized_pnl",
        "right_tail_visual",
        "bottom_loss_visual",
        "maxdd_context",
        "low_resolution_zone",
        "first_bar_event",
        "close_signal_next_bar_collision",
        "two_to_five_bar_short_runway",
        "gt_five_bar_runway",
    ]:
        rows[column] = pd.to_numeric(rows[column], errors="coerce").fillna(0)
    return rows


def _load_oi_features() -> pd.DataFrame:
    features = _read_csv(STAGE107_FEATURES_IN)
    features["official_open_date"] = pd.to_datetime(features["official_open_date"], errors="coerce").dt.normalize()
    for column in [
        "candidate_index",
        "adjusted_panel_ready",
        "bottom_loss_visual",
        "right_tail_visual",
        "target_oi_share",
        "order_realized_pnl",
    ]:
        features[column] = pd.to_numeric(features[column], errors="coerce").fillna(0)
    return features


def _nearest_curve_points(curve: pd.DataFrame, dates: pd.Series) -> pd.DataFrame:
    left = pd.DataFrame({"event_date": pd.to_datetime(dates, errors="coerce").dt.normalize()}).dropna()
    right = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].sort_values("date")
    return pd.merge_asof(left.sort_values("event_date"), right, left_on="event_date", right_on="date", direction="backward")


def _build_risk_event_map(rows: pd.DataFrame, oi: pd.DataFrame, curve: pd.DataFrame) -> pd.DataFrame:
    oi_cols = [
        "candidate_index",
        "adjusted_panel_ready",
        "adjusted_readiness_state",
        "target_rank_bucket",
        "target_oi_share",
        "active_contract_count",
    ]
    merged = rows.merge(oi[oi_cols], on="candidate_index", how="left")
    merged["oi_route_blocked"] = np.where(merged["adjusted_panel_ready"].eq(1), 0, 1)
    merged["near_touch_ohlc_blocked"] = merged["low_resolution_zone"].astype(int)
    merged["orderflow_required"] = np.where(
        merged["near_touch_ohlc_blocked"].eq(1) | merged["oi_route_blocked"].eq(1), 1, 0
    )
    merged["risk_route_label"] = "covered_but_no_rule"
    merged.loc[merged["near_touch_ohlc_blocked"].eq(1), "risk_route_label"] = "minute_ohlc_resolution_blocked"
    merged.loc[merged["oi_route_blocked"].eq(1), "risk_route_label"] = "oi_single_contract_panel_blocked"
    merged.loc[
        merged["near_touch_ohlc_blocked"].eq(1) & merged["oi_route_blocked"].eq(1),
        "risk_route_label",
    ] = "both_ohlc_and_oi_blocked"

    curve_points = _nearest_curve_points(curve, merged["official_open_date"])
    merged = merged.sort_values("official_open_date").reset_index(drop=True)
    curve_points = curve_points.reset_index(drop=True)
    if len(merged) == len(curve_points):
        merged = pd.concat(
            [
                merged,
                curve_points[["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]],
            ],
            axis=1,
        )
    selected = merged[
        [
            "candidate_index",
            "vt_symbol",
            "direction",
            "official_open_date",
            "order_realized_pnl",
            "right_tail_visual",
            "bottom_loss_visual",
            "maxdd_context",
            "resolution_bucket",
            "low_resolution_zone",
            "adjusted_panel_ready",
            "adjusted_readiness_state",
            "target_rank_bucket",
            "target_oi_share",
            "active_contract_count",
            "risk_route_label",
            "orderflow_required",
            "account_equity",
            "drawdown_pct",
            "broker10_margin_to_equity_pct",
        ]
    ].copy()
    return selected.sort_values(["official_open_date", "candidate_index"]).reset_index(drop=True)


def _build_bottom_loss_map(risk: pd.DataFrame) -> pd.DataFrame:
    bottom = risk[risk["bottom_loss_visual"].eq(1)].copy()
    if bottom.empty:
        return pd.DataFrame()
    grouped = (
        bottom.groupby(["risk_route_label", "resolution_bucket", "adjusted_readiness_state"], dropna=False)
        .agg(
            order_count=("candidate_index", "count"),
            pnl_sum=("order_realized_pnl", "sum"),
            pnl_min=("order_realized_pnl", "min"),
            low_resolution_count=("low_resolution_zone", "sum"),
            orderflow_required_count=("orderflow_required", "sum"),
        )
        .reset_index()
        .sort_values(["order_count", "pnl_sum"], ascending=[False, True])
    )
    return grouped.reset_index(drop=True)


def _build_route_scorecard() -> pd.DataFrame:
    stage102 = _read_csv(STAGE102_SUMMARY_IN).iloc[0]
    stage103 = _read_csv(STAGE103_SUMMARY_IN).iloc[0]
    stage107 = _read_csv(STAGE107_SUMMARY_IN).iloc[0]
    action = _read_csv(STAGE103_ACTION_IN)
    contract = _read_csv(STAGE103_CONTRACT_IN)

    def action_row(route_id: str) -> pd.Series:
        rows = action[action["route_id"].eq(route_id)]
        return rows.iloc[0] if not rows.empty else pd.Series(dtype=object)

    def contract_row(route_id: str) -> pd.Series:
        rows = contract[contract["route_id"].eq(route_id)]
        return rows.iloc[0] if not rows.empty else pd.Series(dtype=object)

    rows = [
        {
            "route_id": "contract_month_oi_rank_share",
            "route_family": "external_oi_structure",
            "current_status": "blocked_after_data_repair",
            "evidence": "Stage107 target contract 219/219 found, but SH607 single-contract panel blocks bottom-loss coverage",
            "data_readiness_score": 4,
            "expected_information_gain": 2,
            "implementation_friction": 2,
            "permission_friction": 1,
            "overfit_risk_score": 5,
            "rule_allowed_now": 0,
            "true_engine_allowed_now": 0,
            "key_metric": f"adjusted_ready={stage107['adjusted_panel_ready_count']}/{stage107['timestamp_ready_order_count']}, bottom_loss={stage107['bottom_loss_adjusted_ready_count']}/{stage107['bottom_loss_total_count']}",
            "next_action": "downgrade to forward-watch/explanation only; do not rescue SH607/single-contract panel",
        },
        {
            "route_id": "minute_ohlc_near_touch_rules",
            "route_family": "internal_minute_replay_touch_sensitive",
            "current_status": "blocked_by_bar_resolution",
            "evidence": "Stage102 low-resolution events include right-tail and bottom-loss; close-next-bar collision remains non-actionable",
            "data_readiness_score": 3,
            "expected_information_gain": 2,
            "implementation_friction": 2,
            "permission_friction": 1,
            "overfit_risk_score": 5,
            "rule_allowed_now": 0,
            "true_engine_allowed_now": 0,
            "key_metric": f"low_resolution={stage102['low_resolution_order_count']}/{stage102['timestamp_ready_order_count']}",
            "next_action": "do not revive no-follow/hard-exit/min-risk/breakeven/absorption or close-trigger rules",
        },
        {
            "route_id": "authorized_historical_quote_depth",
            "route_family": "procurement_required_microstructure",
            "current_status": "highest_value_but_data_absent",
            "evidence": "Stage103 gives highest information gain but no local historical full-depth archive",
            "data_readiness_score": 0,
            "expected_information_gain": int(action_row("authorized_historical_quote_depth").get("expected_information_gain", 5)),
            "implementation_friction": int(action_row("authorized_historical_quote_depth").get("implementation_friction", 5)),
            "permission_friction": int(action_row("authorized_historical_quote_depth").get("permission_friction", 5)),
            "overfit_risk_score": 2,
            "rule_allowed_now": 0,
            "true_engine_allowed_now": 0,
            "key_metric": f"contract_pass_rate={contract_row('authorized_historical_quote_depth').get('contract_pass_rate_pct', 0):.1f}%",
            "next_action": "procure licensed historical tick/quote/depth archive or broker-side execution replay",
        },
        {
            "route_id": "broker_or_production_execution_replay",
            "route_family": "same_source_execution_ledger",
            "current_status": "high_value_but_data_absent",
            "evidence": "Stage103 requires same-source execution timestamp ledger; not present locally",
            "data_readiness_score": 0,
            "expected_information_gain": int(action_row("broker_or_production_execution_replay").get("expected_information_gain", 5)),
            "implementation_friction": int(action_row("broker_or_production_execution_replay").get("implementation_friction", 4)),
            "permission_friction": int(action_row("broker_or_production_execution_replay").get("permission_friction", 4)),
            "overfit_risk_score": 2,
            "rule_allowed_now": 0,
            "true_engine_allowed_now": 0,
            "key_metric": f"initial_tick_ready={stage103['initial_entry_tick_ready_count']}/{stage103['initial_entry_tick_planned_count']}",
            "next_action": "export real execution/open proxy ledger; until then no touch-sensitive rule",
        },
        {
            "route_id": "minute_ohlc_far_from_touch_candidate",
            "route_family": "internal_minute_replay_only_if_far_from_touch",
            "current_status": "only_remaining_internal_preflight",
            "evidence": "Stage103 allows only a preflight far from stop/progress and not close-next-bar dependent",
            "data_readiness_score": int(round(contract_row("minute_ohlc_far_from_touch_candidate").get("contract_pass_rate_pct", 30.0) / 20)),
            "expected_information_gain": int(action_row("minute_ohlc_far_from_touch_candidate").get("expected_information_gain", 2)),
            "implementation_friction": int(action_row("minute_ohlc_far_from_touch_candidate").get("implementation_friction", 2)),
            "permission_friction": int(action_row("minute_ohlc_far_from_touch_candidate").get("permission_friction", 1)),
            "overfit_risk_score": 4,
            "rule_allowed_now": 0,
            "true_engine_allowed_now": 0,
            "key_metric": f"contract_pass_rate={contract_row('minute_ohlc_far_from_touch_candidate').get('contract_pass_rate_pct', 30.0):.1f}%",
            "next_action": "if no new data can be procured, design exactly one non-touch preflight spec with official fallback",
        },
        {
            "route_id": "local_tq_tick_or_transform_union",
            "route_family": "local_proxy_tca_only",
            "current_status": "closed_for_rules",
            "evidence": "Stage080 downgraded Tq tick transform union; local tick only TCA/forward-watch",
            "data_readiness_score": 1,
            "expected_information_gain": 1,
            "implementation_friction": 1,
            "permission_friction": 2,
            "overfit_risk_score": 5,
            "rule_allowed_now": 0,
            "true_engine_allowed_now": 0,
            "key_metric": f"initial_entry_tick_ready={stage103['initial_entry_tick_ready_count']}/{stage103['initial_entry_tick_planned_count']}",
            "next_action": "do not revive first/average/topbook transform; use only TCA/forward-watch",
        },
    ]
    scorecard = pd.DataFrame(rows)
    scorecard["route_priority_after_stage108"] = [
        5,
        6,
        1,
        2,
        3,
        7,
    ]
    return scorecard.sort_values("route_priority_after_stage108").reset_index(drop=True)


def _build_next_gate(scorecard: pd.DataFrame, risk: pd.DataFrame) -> pd.DataFrame:
    low_res = int(risk["low_resolution_zone"].sum())
    single_panel = int(risk["adjusted_readiness_state"].eq("single_contract_panel").sum())
    rows = [
        {
            "gate": "do_not_rescue_oi_single_contract_panel",
            "pass": 1,
            "detail": f"single_contract_panel={single_panel}; route downgraded",
        },
        {
            "gate": "do_not_reopen_touch_sensitive_minute_rules",
            "pass": 1,
            "detail": f"low_resolution_zone={low_res}; Stage102 closed",
        },
        {
            "gate": "authorized_orderflow_data_available_now",
            "pass": 0,
            "detail": "not present locally; procurement required",
        },
        {
            "gate": "far_from_touch_internal_preflight_allowed",
            "pass": 1,
            "detail": "only as one frozen preflight, no true engine/A-B yet",
        },
        {
            "gate": "true_engine_or_ab_allowed_now",
            "pass": 0,
            "detail": "no route has enough evidence",
        },
    ]
    return pd.DataFrame(rows)


def _plot_path(curve: pd.DataFrame, risk: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(15, 10), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#111827", lw=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[0].set_title("Stage108 official path with unresolved route blockers")
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#b91c1c", lw=1.0)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#0369a1", lw=1.0)
    axes[2].axhline(100, color="#991b1b", ls="--", lw=0.8)
    axes[2].set_ylabel("broker10 %")

    color_map = {
        "covered_but_no_rule": "#15803d",
        "minute_ohlc_resolution_blocked": "#f97316",
        "oi_single_contract_panel_blocked": "#6b7280",
        "both_ohlc_and_oi_blocked": "#dc2626",
    }
    plot_rows = risk[risk["bottom_loss_visual"].eq(1) | risk["right_tail_visual"].eq(1) | risk["maxdd_context"].eq(1)].copy()
    for label, group in plot_rows.groupby("risk_route_label"):
        color = color_map.get(label, "#6b7280")
        size = np.where(group["bottom_loss_visual"].eq(1), 80, 46)
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
                label=label if ax is axes[0] else None,
            )
    axes[0].legend(loc="upper left", fontsize=8, ncols=2)
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_route_heatmap(scorecard: pd.DataFrame) -> None:
    metrics = [
        "data_readiness_score",
        "expected_information_gain",
        "implementation_friction",
        "permission_friction",
        "overfit_risk_score",
    ]
    matrix = scorecard.set_index("route_id")[metrics]
    fig, ax = plt.subplots(figsize=(12, max(4.8, 0.55 * len(matrix))))
    image = ax.imshow(matrix.to_numpy(dtype=float), vmin=0, vmax=5, cmap="RdYlGn_r", aspect="auto")
    ax.set_xticks(range(len(metrics)))
    ax.set_xticklabels(metrics, rotation=25, ha="right")
    ax.set_yticks(range(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    for y in range(len(matrix.index)):
        for x in range(len(metrics)):
            ax.text(x, y, f"{matrix.iloc[y, x]:.0f}", ha="center", va="center", fontsize=8)
    ax.set_title("Stage108 route scorecard: green is low score, red is high burden/risk")
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(ROUTE_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_bottom_loss(bottom: pd.DataFrame) -> None:
    if bottom.empty:
        return
    frame = bottom.copy()
    frame["label"] = frame["risk_route_label"] + "\n" + frame["resolution_bucket"].astype(str)
    frame = frame.sort_values("pnl_sum")
    fig, ax = plt.subplots(figsize=(13, max(5, 0.45 * len(frame))))
    colors = np.where(frame["orderflow_required_count"].gt(0), "#f97316", "#15803d")
    ax.barh(frame["label"], frame["pnl_sum"] / 1_000_000, color=colors, alpha=0.88)
    for y, row in enumerate(frame.itertuples(index=False)):
        ax.text(row.pnl_sum / 1_000_000, y, f" {int(row.order_count)}", va="center", fontsize=8)
    ax.axvline(0, color="#111827", lw=0.8)
    ax.set_xlabel("bottom-loss PnL sum (m)")
    ax.set_title("Stage108 bottom-loss route map")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(BOTTOM_LOSS_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_next_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.8))
    colors = np.where(gate["pass"].eq(1), "#15803d", "#dc2626")
    ax.barh(gate["gate"], gate["pass"], color=colors, alpha=0.9)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("pass")
    ax.set_title("Stage108 next-route gates")
    for y, (_, row) in enumerate(gate.iterrows()):
        ax.text(0.03, y, str(row["detail"]), va="center", fontsize=8, color="white" if int(row["pass"]) else "#111827")
    fig.tight_layout()
    fig.savefig(NEXT_GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _summary(scorecard: pd.DataFrame, risk: pd.DataFrame, bottom: pd.DataFrame) -> dict[str, Any]:
    stage102 = _read_csv(STAGE102_SUMMARY_IN).iloc[0]
    stage103 = _read_csv(STAGE103_SUMMARY_IN).iloc[0]
    stage107 = _read_csv(STAGE107_SUMMARY_IN).iloc[0]
    order_count = int(stage102["timestamp_ready_order_count"])
    route_allowed = int(scorecard["true_engine_allowed_now"].sum())
    bottom_order_count = int(risk["bottom_loss_visual"].sum())
    bottom_orderflow_required = int(risk.loc[risk["bottom_loss_visual"].eq(1), "orderflow_required"].sum())
    low_resolution_bottom = int(
        risk.loc[risk["bottom_loss_visual"].eq(1), "low_resolution_zone"].sum()
    )
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": "stage108_post_oi_route_reset_no_rule_next_non_touch_or_data_procurement",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "timestamp_ready_order_count": order_count,
        "closed_or_blocked_route_count": int(scorecard["true_engine_allowed_now"].eq(0).sum()),
        "true_engine_allowed_route_count": route_allowed,
        "stage102_low_resolution_order_count": int(stage102["low_resolution_order_count"]),
        "stage102_low_resolution_bottom_loss_count": int(stage102["low_resolution_bottom_loss_count"]),
        "stage103_initial_entry_tick_ready_count": int(stage103["initial_entry_tick_ready_count"]),
        "stage103_initial_entry_tick_ready_rate_pct": float(stage103["initial_entry_tick_ready_rate_pct"]),
        "stage107_adjusted_panel_ready_count": int(stage107["adjusted_panel_ready_count"]),
        "stage107_single_contract_panel_count": int(stage107["single_contract_panel_count"]),
        "bottom_loss_order_count": bottom_order_count,
        "bottom_loss_orderflow_required_count": bottom_orderflow_required,
        "bottom_loss_low_resolution_count": low_resolution_bottom,
        "route_scorecard_count": int(len(scorecard)),
        "next_recommended_route": "authorized_orderflow_or_one_frozen_far_from_touch_preflight",
        "panel_feature_rule_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "end_equity": float(stage102["end_equity"]),
        "total_return_pct": float(stage102["total_return_pct"]),
        "max_drawdown_pct": float(stage102["max_drawdown_pct"]),
        "sharpe": float(stage102["sharpe"]),
        "total_slippage": float(stage102["total_slippage"]),
        "total_trade_count": float(stage102["total_trade_count"]),
        "closed_lot_win_rate_pct": float(stage102["closed_lot_win_rate_pct"]),
        "max_broker10_margin_to_equity_pct": float(stage102["max_broker10_margin_to_equity_pct"]),
    }


def _write_report(
    summary: dict[str, Any],
    scorecard: pd.DataFrame,
    risk: pd.DataFrame,
    bottom: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    bottom_focus = risk[risk["bottom_loss_visual"].eq(1)].copy()
    lines = [
        "# Stage108 post-OI route reset risk map",
        "",
        "## Decision",
        "",
        f"- decision: `{summary['decision']}`",
        "- This stage does not create a trading rule. It consolidates route blockers after the OI route closure.",
        "",
        "## Key Metrics",
        "",
        _md_table(pd.DataFrame([summary])),
        "",
        "## Route Scorecard",
        "",
        _md_table(scorecard),
        "",
        "## Bottom-Loss Focus",
        "",
        _md_table(
            bottom_focus[
                [
                    "candidate_index",
                    "vt_symbol",
                    "official_open_date",
                    "order_realized_pnl",
                    "resolution_bucket",
                    "adjusted_readiness_state",
                    "risk_route_label",
                    "orderflow_required",
                ]
            ],
            max_rows=40,
        ),
        "",
        "## Bottom-Loss Route Aggregation",
        "",
        _md_table(bottom),
        "",
        "## Next Gates",
        "",
        _md_table(gate),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT}`",
        f"- `{ROUTE_HEATMAP_OUT}`",
        f"- `{BOTTOM_LOSS_CHART_OUT}`",
        f"- `{NEXT_GATE_CHART_OUT}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    rows = _load_rows()
    oi = _load_oi_features()
    risk = _build_risk_event_map(rows, oi, curve)
    bottom = _build_bottom_loss_map(risk)
    scorecard = _build_route_scorecard()
    gate = _build_next_gate(scorecard, risk)
    summary = _summary(scorecard, risk, bottom)

    scorecard.to_csv(ROUTE_SCORECARD_OUT, index=False, encoding="utf-8-sig")
    risk.to_csv(RISK_EVENT_MAP_OUT, index=False, encoding="utf-8-sig")
    bottom.to_csv(BOTTOM_LOSS_MAP_OUT, index=False, encoding="utf-8-sig")
    gate.to_csv(NEXT_GATE_OUT, index=False, encoding="utf-8-sig")
    pd.DataFrame([summary]).to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(summary), ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    _plot_path(curve, risk)
    _plot_route_heatmap(scorecard)
    _plot_bottom_loss(bottom)
    _plot_next_gate(gate)
    _write_report(summary, scorecard, risk, bottom, gate)
    print(json.dumps(_json_safe(summary), ensure_ascii=True, indent=2), flush=True)


if __name__ == "__main__":
    main()
