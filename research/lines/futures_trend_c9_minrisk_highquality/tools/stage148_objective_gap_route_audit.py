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
STAGE = "Stage148"
MODEL_TAG = "stage148_objective_gap_route_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage148_c9_minrisk_objective_gap_route_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage148_objective_gap_route_audit"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

STAGE141_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage141_candidate_promotion_gate_contract"
    / "qmt_roll_stage141_c9_minrisk_candidate_promotion_gate_contract_summary_"
    "stage141_candidate_promotion_gate_contract_v1.csv"
)
STAGE045_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_summary_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE080_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage080_tick_transform_mismatch_attribution"
    / "qmt_roll_stage080_c9_minrisk_tick_transform_mismatch_attribution_summary_"
    "stage080_tick_transform_mismatch_attribution_v1.csv"
)
STAGE082_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage082_maxdd_episode_label_audit"
    / "qmt_roll_stage082_c9_minrisk_maxdd_episode_label_audit_summary_"
    "stage082_maxdd_episode_label_audit_v1.csv"
)
STAGE083_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage083_account_volatility_gate_proxy_audit"
    / "qmt_roll_stage083_c9_minrisk_account_volatility_gate_proxy_audit_summary_"
    "stage083_account_volatility_gate_proxy_audit_v1.csv"
)
STAGE084_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage084_fixed_capital_multistart_boundary_audit"
    / "qmt_roll_stage084_c9_minrisk_fixed_capital_multistart_boundary_audit_summary_"
    "stage084_fixed_capital_multistart_boundary_audit_v1.csv"
)
STAGE099_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage099_finer_source_feasibility_manifest"
    / "qmt_roll_stage99_c9_minrisk_finer_source_feasibility_manifest_summary_"
    "stage099_finer_source_feasibility_manifest_v1.csv"
)
STAGE099_SUMMARY_ALT_IN = (
    LINE_DIR
    / "outputs"
    / "stage099_finer_source_feasibility_manifest"
    / "qmt_roll_stage099_c9_minrisk_finer_source_feasibility_manifest_summary_"
    "stage099_finer_source_feasibility_manifest_v1.csv"
)
STAGE108_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage108_post_oi_route_reset_risk_map"
    / "qmt_roll_stage108_c9_minrisk_post_oi_route_reset_risk_map_summary_"
    "stage108_post_oi_route_reset_risk_map_v1.csv"
)
STAGE109_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage109_far_from_touch_preflight"
    / "qmt_roll_stage109_c9_minrisk_far_from_touch_preflight_summary_"
    "stage109_far_from_touch_preflight_v1.csv"
)
STAGE147_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage147_candidate_gate_status_panel"
    / "qmt_roll_stage147_c9_minrisk_candidate_gate_status_panel_summary_"
    "stage147_candidate_gate_status_panel_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
REQUIREMENT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_objective_requirement_gap_{MODEL_TAG}.csv"
ROUTE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_scorecard_{MODEL_TAG}.csv"
ACTION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_action_queue_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_gap_status_{MODEL_TAG}.png"
REQUIREMENT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_objective_gap_matrix_{MODEL_TAG}.png"
ROUTE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_scorecard_matrix_{MODEL_TAG}.png"
ACTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_action_priority_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if np.isnan(number) or np.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 4:
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
        else:
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else str(value).replace("|", "\\|"))
    lines = [
        "| " + " | ".join(str(column) for column in data.columns) + " |",
        "| " + " | ".join(["---"] * len(data.columns)) + " |",
    ]
    for _, row in data.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in data.columns) + " |")
    return "\n".join(lines)


def _row(path: Path) -> dict[str, Any]:
    frame = _read_csv(path)
    if frame.empty and path == STAGE099_SUMMARY_IN:
        frame = _read_csv(STAGE099_SUMMARY_ALT_IN)
    return frame.iloc[0].to_dict() if not frame.empty else {}


def _num(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if np.isnan(number) or np.isinf(number):
        return default
    return number


def _int(row: dict[str, Any], key: str, default: int = 0) -> int:
    return int(round(_num(row, key, float(default))))


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    if curve.empty:
        raise RuntimeError(f"missing curve input: {CURVE_IN}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _requirements(rows: dict[str, dict[str, Any]]) -> pd.DataFrame:
    stage147 = rows["stage147"]
    stage141 = rows["stage141"]
    stage045 = rows["stage045"]
    stage080 = rows["stage080"]
    stage109 = rows["stage109"]
    route_real_candidate = _int(stage147, "real_candidate_package_supplied")
    rows_out = [
        {
            "requirement_id": "R01_fixed_baseline_context",
            "requirement": "Use the existing official/C9 research baseline without reselecting it this turn.",
            "status": "proven",
            "pass_now": 1,
            "evidence_stage": "Stage045/Stage147",
            "evidence": f"semantic curve exists; Stage147 end_equity={_num(stage147, 'end_equity'):.2f}",
            "gap": "",
        },
        {
            "requirement_id": "R02_drawdown_reduction_candidate",
            "requirement": "Produce a candidate with lower max drawdown than baseline.",
            "status": "missing",
            "pass_now": 0,
            "evidence_stage": "Stage147",
            "evidence": f"current_package_promotion_allowed={_int(stage147, 'current_package_promotion_allowed')}",
            "gap": "No real candidate package or true-engine candidate exists.",
        },
        {
            "requirement_id": "R03_return_retention_80pct",
            "requirement": "Retain at least 80% of baseline return.",
            "status": "missing",
            "pass_now": 0,
            "evidence_stage": "Stage141",
            "evidence": f"contract threshold fixed at min_return={_num(stage141, 'min_candidate_total_return_pct'):.4f} if present",
            "gap": "Threshold exists, but no candidate has been evaluated against it.",
        },
        {
            "requirement_id": "R04_no_overfit_contract",
            "requirement": "Use predeclared, anti-overfit, no rescue-sweep rules.",
            "status": "partial",
            "pass_now": 0,
            "evidence_stage": "Stage141/142/145",
            "evidence": "promotion contract, package validator, and preflight linter exist",
            "gap": "A real candidate still needs OOS/LOYO/monthly-start/right-tail evidence.",
        },
        {
            "requirement_id": "R05_universal_cycle_robustness",
            "requirement": "Show cross-year, cross-product, monthly-start and right-tail/bottom-loss robustness.",
            "status": "missing",
            "pass_now": 0,
            "evidence_stage": "Stage141/147",
            "evidence": "required in contract; current real_candidate_package_supplied=0",
            "gap": "No candidate has supplied robust evidence.",
        },
        {
            "requirement_id": "R06_minute_k_entry_exit_data",
            "requirement": "Use actionable minute-K entry/exit data on a same-source or authorized basis.",
            "status": "blocked_by_data",
            "pass_now": 0,
            "evidence_stage": "Stage080/109",
            "evidence": (
                f"Stage080 rule candidate allowed={_int(stage080, 'rule_candidate_allowed')}; "
                f"Stage109 preflight_rule_allowed={_int(stage109, 'preflight_rule_allowed')}"
            ),
            "gap": "Current local minute/tick routes do not provide a rule-ready same-source microstructure feed.",
        },
        {
            "requirement_id": "R07_visual_curve_each_stage",
            "requirement": "Generate curve/visual evidence for every research stage.",
            "status": "proven_for_current_stage",
            "pass_now": 1,
            "evidence_stage": "Stage147/Stage148",
            "evidence": "Stage147 has 5 charts; Stage148 creates 5 charts",
            "gap": "",
        },
        {
            "requirement_id": "R08_high_quality_minrisk_signal",
            "requirement": "Identify high-quality signal conditions where minimum risk can pursue maximum return.",
            "status": "missing",
            "pass_now": 0,
            "evidence_stage": "Stage100/101/109",
            "evidence": "absorption/reclaim and far-from-touch preflights were mixed or degenerated",
            "gap": "No surviving first-principles minute signal remains in current data.",
        },
        {
            "requirement_id": "R09_no_execution_side_effect",
            "requirement": "Do not touch live execution, CTP, order API, official config, or A/B until gates require it.",
            "status": "proven",
            "pass_now": 1,
            "evidence_stage": "Stage147",
            "evidence": f"side_effect_count={_int(stage147, 'side_effect_count')}",
            "gap": "",
        },
        {
            "requirement_id": "R10_candidate_gate_chain",
            "requirement": "Real candidate must pass Stage145 before Stage142/143 and promotion contract.",
            "status": "proven_gate_ready_but_waiting",
            "pass_now": 1,
            "evidence_stage": "Stage146/147",
            "evidence": f"chain ready={_int(stage147, 'latest_chain_smoke_ready')}; real package={route_real_candidate}",
            "gap": "Waiting for real candidate package.",
        },
    ]
    return pd.DataFrame(rows_out)


def _route_scorecard(rows: dict[str, dict[str, Any]]) -> pd.DataFrame:
    stage147 = rows["stage147"]
    route_rows = [
        {
            "route_id": "calibrated_timestamp_ready_replay",
            "route_name": "Stage045 calibrated event replay subset",
            "evidence_stage": "Stage045",
            "technical_ready": 1,
            "data_ready": 1,
            "rule_candidate_allowed": 0,
            "overfit_risk_if_forced": 1,
            "right_tail_conflict_known": 0,
            "next_actionable_now": 1,
            "recommended_use": "Only for predeclared new hypothesis audit, not residual mining.",
        },
        {
            "route_id": "same_source_tick_orderflow",
            "route_name": "Authorized same-source tick/orderflow",
            "evidence_stage": "Stage103-147",
            "technical_ready": 1,
            "data_ready": 0,
            "rule_candidate_allowed": 0,
            "overfit_risk_if_forced": 1,
            "right_tail_conflict_known": 0,
            "next_actionable_now": 0,
            "recommended_use": "Wait for real W0 or authorized drop; run Stage125/133/112/113 first.",
        },
        {
            "route_id": "tq_topbook_tick_transform",
            "route_name": "Existing Tq top-book tick transform",
            "evidence_stage": "Stage080",
            "technical_ready": 1,
            "data_ready": 1,
            "rule_candidate_allowed": 0,
            "overfit_risk_if_forced": 1,
            "right_tail_conflict_known": 1,
            "next_actionable_now": 0,
            "recommended_use": "TCA/diagnostic only; not a rule source.",
        },
        {
            "route_id": "account_vol_or_fixed_capital",
            "route_name": "Account volatility/fixed capital overlays",
            "evidence_stage": "Stage083/084",
            "technical_ready": 1,
            "data_ready": 1,
            "rule_candidate_allowed": 0,
            "overfit_risk_if_forced": 1,
            "right_tail_conflict_known": 1,
            "next_actionable_now": 0,
            "recommended_use": "Closed for parameter rescue.",
        },
        {
            "route_id": "existing_visible_maxdd_labels",
            "route_name": "Existing visible maxDD labels",
            "evidence_stage": "Stage082",
            "technical_ready": 1,
            "data_ready": 1,
            "rule_candidate_allowed": 0,
            "overfit_risk_if_forced": 1,
            "right_tail_conflict_known": 1,
            "next_actionable_now": 0,
            "recommended_use": "Closed; do not mine historical loss cohorts.",
        },
        {
            "route_id": "far_from_touch_proxy",
            "route_name": "Frozen far-from-touch proxy",
            "evidence_stage": "Stage109",
            "technical_ready": 1,
            "data_ready": 1,
            "rule_candidate_allowed": _int(rows["stage109"], "preflight_rule_allowed"),
            "overfit_risk_if_forced": 1,
            "right_tail_conflict_known": 1,
            "next_actionable_now": 0,
            "recommended_use": "Closed; degenerated to older no-progress shape.",
        },
        {
            "route_id": "candidate_package_gate",
            "route_name": "Real candidate package gate chain",
            "evidence_stage": "Stage147",
            "technical_ready": _int(stage147, "status_panel_ready"),
            "data_ready": _int(stage147, "real_candidate_package_supplied"),
            "rule_candidate_allowed": _int(stage147, "current_package_promotion_allowed"),
            "overfit_risk_if_forced": 0,
            "right_tail_conflict_known": 0,
            "next_actionable_now": int(_int(stage147, "real_candidate_package_supplied") == 1),
            "recommended_use": "Wait for real package; Stage145 first.",
        },
    ]
    return pd.DataFrame(route_rows)


def _action_queue(requirements: pd.DataFrame, routes: pd.DataFrame) -> pd.DataFrame:
    missing_count = int((requirements["pass_now"] == 0).sum())
    return pd.DataFrame(
        [
            {
                "priority": 1,
                "action_id": "real_w0_or_authorized_orderflow_drop",
                "action": "If new data arrives, run Stage125 -> Stage133 -> Stage112/113 before any signal research.",
                "why": "Minute-K/actionable orderflow is the strongest current blocker.",
                "allowed_now": 0,
                "blocks_removed_if_done": "R06, candidate data readiness",
            },
            {
                "priority": 2,
                "action_id": "new_predeclared_replay_hypothesis_only",
                "action": "If researching without new data, write one new hypothesis on Stage045 timestamp-ready replay that is not a closed route.",
                "why": "This is the only route with technical replay readiness and no need to reselect official baseline.",
                "allowed_now": 1,
                "blocks_removed_if_done": "Potential R08 preflight only",
            },
            {
                "priority": 3,
                "action_id": "real_candidate_package_stage145_first",
                "action": "If a candidate package is supplied, run Stage145 first and require preflight_pass=1.",
                "why": "Prevents template, fixture, synthetic, or evidence-incomplete promotion.",
                "allowed_now": 1,
                "blocks_removed_if_done": "R02-R05 if package is real and passes",
            },
            {
                "priority": 4,
                "action_id": "do_not_repeat_closed_routes",
                "action": "Do not continue no-follow, opening-range, Tq-transform, maxDD-label, account-vol, fixed-capital, or far-from-touch rescues.",
                "why": f"{missing_count} objective requirements remain open; closed routes add overfit risk without solving data/actionability.",
                "allowed_now": 1,
                "blocks_removed_if_done": "Reduces overfit drift",
            },
        ]
    )


def _gate_status(requirements: pd.DataFrame, routes: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    row = summary.iloc[0]
    rows = [
        {
            "gate_id": "audit_generated",
            "observed": _int(row.to_dict(), "objective_gap_audit_ready"),
            "required": 1,
            "pass_now": int(_int(row.to_dict(), "objective_gap_audit_ready") == 1),
            "severity": "audit_hard",
        },
        {
            "gate_id": "no_false_completion",
            "observed": _int(row.to_dict(), "objective_completion_proven"),
            "required": 0,
            "pass_now": int(_int(row.to_dict(), "objective_completion_proven") == 0),
            "severity": "anti_overclaim_hard",
        },
        {
            "gate_id": "missing_requirements_present",
            "observed": int((requirements["pass_now"] == 0).sum()),
            "required": 1,
            "pass_now": int((requirements["pass_now"] == 0).sum() >= 1),
            "severity": "reality_check_hard",
        },
        {
            "gate_id": "no_current_rule_candidate_allowed",
            "observed": int(routes["rule_candidate_allowed"].sum()),
            "required": 0,
            "pass_now": int(routes["rule_candidate_allowed"].sum() == 0),
            "severity": "anti_selection_hard",
        },
        {
            "gate_id": "no_execution_side_effect",
            "observed": _int(row.to_dict(), "side_effect_count"),
            "required": 0,
            "pass_now": int(_int(row.to_dict(), "side_effect_count") == 0),
            "severity": "execution_safety_hard",
        },
    ]
    return pd.DataFrame(rows)


def _write_report(
    summary: pd.DataFrame,
    requirements: pd.DataFrame,
    routes: pd.DataFrame,
    actions: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    lines = [
        f"# {STAGE} objective gap and route audit",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        f"- next_best_action: `{summary.iloc[0]['next_best_action']}`",
        "",
        "## External Research Judgment",
        "",
        "- Time-series momentum evidence supports simple, persistent trend effects across futures, but does not justify mining intraday loss labels.",
        "- Long-horizon trend-following robustness argues for broad, predeclared, cross-market checks before any minute-level overlay.",
        "- Existing open-source futures trend systems are mostly daily/portfolio trend frameworks; they do not solve our same-source minute-K execution evidence gap.",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Objective Requirement Gap",
        "",
        _md_table(requirements),
        "",
        "## Route Scorecard",
        "",
        _md_table(routes),
        "",
        "## Next Action Queue",
        "",
        _md_table(actions),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{REQUIREMENT_CHART_OUT.name}`",
        f"- `{ROUTE_CHART_OUT.name}`",
        f"- `{ACTION_CHART_OUT.name}`",
        f"- `{GATE_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _plot_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    row = summary.iloc[0]
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage148 objective gap audit on official path", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#14532D", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#B45309", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3657D6", linewidth=1.0)
    axes[2].axhline(100, color="#333333", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    labels = ["complete", "missing_req", "route_allowed", "side_effect", "real_pkg"]
    values = [
        row["objective_completion_proven"],
        row["objective_missing_requirement_count"],
        row["rule_candidate_allowed_route_count"],
        row["side_effect_count"],
        row["real_candidate_package_supplied"],
    ]
    colors = ["#0F766E", "#B45309", "#B91C1C", "#B91C1C", "#3657D6"]
    axes[3].bar(labels, values, color=colors)
    axes[3].set_title("Current objective status")
    axes[3].set_ylabel("count / flag")
    axes[3].tick_params(axis="x", labelrotation=20)
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_matrix(frame: pd.DataFrame, index_col: str, value_cols: list[str], title: str, path: Path) -> None:
    matrix = frame.set_index(index_col)[value_cols].copy()
    for column in value_cols:
        matrix[column] = pd.to_numeric(matrix[column], errors="coerce").fillna(0).clip(upper=1)
    data = matrix.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(max(8.5, len(value_cols) * 1.45), max(4.8, len(matrix) * 0.62)))
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title(title)
    ax.set_xticks(np.arange(len(value_cols)))
    ax.set_xticklabels(value_cols, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=8)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


def _plot_actions(actions: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 5.5))
    colors = ["#0F766E" if value else "#B45309" for value in actions["allowed_now"]]
    ax.barh(actions["action_id"], list(reversed(range(1, len(actions) + 1))), color=colors)
    ax.set_title("Stage148 next action queue")
    ax.set_xlabel("priority weight")
    ax.grid(axis="x", alpha=0.25)
    for i, (_, row) in enumerate(actions.iterrows()):
        ax.text(0.05, i, f"allowed={row['allowed_now']}", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(ACTION_CHART_OUT, dpi=170)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    curve = _load_curve()
    rows = {
        "stage141": _row(STAGE141_SUMMARY_IN),
        "stage045": _row(STAGE045_SUMMARY_IN),
        "stage080": _row(STAGE080_SUMMARY_IN),
        "stage082": _row(STAGE082_SUMMARY_IN),
        "stage083": _row(STAGE083_SUMMARY_IN),
        "stage084": _row(STAGE084_SUMMARY_IN),
        "stage099": _row(STAGE099_SUMMARY_IN),
        "stage108": _row(STAGE108_SUMMARY_IN),
        "stage109": _row(STAGE109_SUMMARY_IN),
        "stage147": _row(STAGE147_SUMMARY_IN),
    }
    requirements = _requirements(rows)
    routes = _route_scorecard(rows)
    actions = _action_queue(requirements, routes)
    stage147 = rows["stage147"]
    missing_requirements = int((requirements["pass_now"] == 0).sum())
    rule_allowed_routes = int(routes["rule_candidate_allowed"].sum())
    side_effect_count = (
        _int(stage147, "side_effect_count")
        + _int(stage147, "official_config_changed")
        + _int(stage147, "true_engine_run")
        + _int(stage147, "ab_triggered")
        + _int(stage147, "order_api_called")
        + _int(stage147, "ctp_connected")
    )
    objective_complete = int(missing_requirements == 0 and rule_allowed_routes > 0)
    decision = (
        "stage148_objective_gap_audit_ready_goal_not_complete_no_rule"
        if objective_complete == 0 and side_effect_count == 0
        else "stage148_objective_gap_audit_attention_required"
    )
    next_best_action = "new_predeclared_replay_hypothesis_or_wait_real_w0"
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": decision,
                "next_best_action": next_best_action,
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "true_engine_run_count": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "side_effect_count": side_effect_count,
                "objective_gap_audit_ready": 1,
                "objective_completion_proven": objective_complete,
                "objective_requirement_count": len(requirements),
                "objective_missing_requirement_count": missing_requirements,
                "objective_proven_requirement_count": int((requirements["pass_now"] == 1).sum()),
                "route_count": len(routes),
                "rule_candidate_allowed_route_count": rule_allowed_routes,
                "next_action_allowed_now_count": int(actions["allowed_now"].sum()),
                "real_candidate_package_supplied": _int(stage147, "real_candidate_package_supplied"),
                "current_package_promotion_allowed": _int(stage147, "current_package_promotion_allowed"),
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "end_equity": float(stage147.get("end_equity", np.nan)),
                "total_return_pct": float(stage147.get("total_return_pct", np.nan)),
                "max_drawdown_pct": float(stage147.get("max_drawdown_pct", np.nan)),
                "sharpe": float(stage147.get("sharpe", np.nan)),
                "total_slippage": float(stage147.get("total_slippage", np.nan)),
                "total_trade_count": float(stage147.get("total_trade_count", np.nan)),
                "closed_lot_win_rate_pct": float(stage147.get("closed_lot_win_rate_pct", np.nan)),
                "max_broker10_margin_to_equity_pct": float(
                    stage147.get("max_broker10_margin_to_equity_pct", np.nan)
                ),
            }
        ]
    )
    gate = _gate_status(requirements, routes, summary)

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(requirements, REQUIREMENT_OUT)
    _write_csv(routes, ROUTE_OUT)
    _write_csv(actions, ACTION_OUT)
    _write_csv(gate, GATE_OUT)
    _write_report(summary, requirements, routes, actions, gate)
    _plot_path(curve, summary)
    _plot_matrix(requirements, "requirement_id", ["pass_now"], "Stage148 objective requirement gap", REQUIREMENT_CHART_OUT)
    _plot_matrix(
        routes,
        "route_id",
        ["technical_ready", "data_ready", "rule_candidate_allowed", "overfit_risk_if_forced", "right_tail_conflict_known", "next_actionable_now"],
        "Stage148 route scorecard",
        ROUTE_CHART_OUT,
    )
    _plot_actions(actions)
    _plot_matrix(gate, "gate_id", ["pass_now"], "Stage148 gate status", GATE_CHART_OUT)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "next_best_action": next_best_action,
            "inputs": {
                "stage045_summary": str(STAGE045_SUMMARY_IN),
                "stage080_summary": str(STAGE080_SUMMARY_IN),
                "stage108_summary": str(STAGE108_SUMMARY_IN),
                "stage109_summary": str(STAGE109_SUMMARY_IN),
                "stage147_summary": str(STAGE147_SUMMARY_IN),
            },
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "objective_requirement_gap": str(REQUIREMENT_OUT),
                "route_scorecard": str(ROUTE_OUT),
                "next_action_queue": str(ACTION_OUT),
                "gate_status": str(GATE_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(REQUIREMENT_CHART_OUT),
                    str(ROUTE_CHART_OUT),
                    str(ACTION_CHART_OUT),
                    str(GATE_CHART_OUT),
                ],
            },
            "locks": {
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "true_engine_run_count": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "current_package_promotion_allowed": _int(stage147, "current_package_promotion_allowed"),
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
