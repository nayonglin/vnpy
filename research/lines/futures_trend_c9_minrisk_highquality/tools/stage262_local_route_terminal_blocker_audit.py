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
STAGE = "Stage262"
MODEL_TAG = "stage262_local_route_terminal_blocker_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage262_c9_minrisk_local_route_terminal_blocker_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage262_local_route_terminal_blocker_audit"

STAGE251_DIR = LINE_DIR / "outputs" / "stage251_dd30_account_floor_true_engine"
STAGE255_DIR = LINE_DIR / "outputs" / "stage255_microstructure_coverage_closure_audit"
STAGE259_DIR = LINE_DIR / "outputs" / "stage259_remaining_route_exhaustion_audit"
STAGE260_DIR = LINE_DIR / "outputs" / "stage260_execution_replay_source_inventory_audit"
STAGE261_IMPORT_DIR = LINE_DIR / "outputs" / "stage261_execution_replay_import_acceptance_packet"
STAGE261_OUTSIDE_DIR = LINE_DIR / "outputs" / "stage261_outside_account_governance_boundary_audit"

STAGE251_PREFIX = "qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine"
STAGE255_PREFIX = "qmt_roll_stage255_c9_minrisk_microstructure_coverage_closure_audit"
STAGE259_PREFIX = "qmt_roll_stage259_c9_minrisk_remaining_route_exhaustion_audit"
STAGE260_PREFIX = "qmt_roll_stage260_c9_minrisk_execution_replay_source_inventory_audit"
STAGE261_IMPORT_PREFIX = "qmt_roll_stage261_c9_minrisk_execution_replay_import_acceptance_packet"
STAGE261_OUTSIDE_PREFIX = "qmt_roll_stage261_c9_minrisk_outside_account_governance_boundary_audit"

STAGE251_TAG = "stage251_dd30_account_floor_true_engine_v1"
STAGE255_TAG = "stage255_microstructure_coverage_closure_audit_v1"
STAGE259_TAG = "stage259_remaining_route_exhaustion_audit_v1"
STAGE260_TAG = "stage260_execution_replay_source_inventory_audit_v1"
STAGE261_IMPORT_TAG = "stage261_execution_replay_import_acceptance_packet_v1"
STAGE261_OUTSIDE_TAG = "stage261_outside_account_governance_boundary_audit_v1"

STAGE251_CURVE_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_curve_{STAGE251_TAG}.csv"
STAGE251_SUMMARY_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_summary_{STAGE251_TAG}.csv"
STAGE255_SUMMARY_IN = STAGE255_DIR / f"{STAGE255_PREFIX}_summary_{STAGE255_TAG}.csv"
STAGE259_SUMMARY_IN = STAGE259_DIR / f"{STAGE259_PREFIX}_summary_{STAGE259_TAG}.csv"
STAGE259_ROUTE_IN = STAGE259_DIR / f"{STAGE259_PREFIX}_route_ledger_{STAGE259_TAG}.csv"
STAGE259_NEXT_IN = STAGE259_DIR / f"{STAGE259_PREFIX}_next_action_queue_{STAGE259_TAG}.csv"
STAGE260_SUMMARY_IN = STAGE260_DIR / f"{STAGE260_PREFIX}_summary_{STAGE260_TAG}.csv"
STAGE260_GATE_IN = STAGE260_DIR / f"{STAGE260_PREFIX}_promotion_gate_{STAGE260_TAG}.csv"
STAGE261_IMPORT_SUMMARY_IN = STAGE261_IMPORT_DIR / f"{STAGE261_IMPORT_PREFIX}_summary_{STAGE261_IMPORT_TAG}.csv"
STAGE261_IMPORT_GATE_IN = STAGE261_IMPORT_DIR / f"{STAGE261_IMPORT_PREFIX}_acceptance_gate_{STAGE261_IMPORT_TAG}.csv"
STAGE261_OUTSIDE_SUMMARY_IN = STAGE261_OUTSIDE_DIR / f"{STAGE261_OUTSIDE_PREFIX}_summary_{STAGE261_OUTSIDE_TAG}.csv"
STAGE261_OUTSIDE_POLICY_IN = STAGE261_OUTSIDE_DIR / f"{STAGE261_OUTSIDE_PREFIX}_policy_summary_{STAGE261_OUTSIDE_TAG}.csv"
STAGE261_OUTSIDE_GATE_IN = STAGE261_OUTSIDE_DIR / f"{STAGE261_OUTSIDE_PREFIX}_invariant_gate_{STAGE261_OUTSIDE_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
TERMINAL_ROUTE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_terminal_route_ledger_{MODEL_TAG}.csv"
OBJECTIVE_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_objective_requirement_audit_{MODEL_TAG}.csv"
BLOCKER_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_blocker_audit_{MODEL_TAG}.csv"
NEXT_ACTION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_action_queue_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_terminal_gate_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_terminal_status_{MODEL_TAG}.png"
ROUTE_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_terminal_matrix_{MODEL_TAG}.png"
OBJECTIVE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_objective_requirement_chart_{MODEL_TAG}.png"
BLOCKER_CHAIN_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_blocker_chain_chart_{MODEL_TAG}.png"
NEXT_ACTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_action_chart_{MODEL_TAG}.png"

FULL_ENTRY_DECISION_COUNT = 219


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 4:
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return number if np.isfinite(number) else None
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    if pd.isna(value):
        return None
    return value


def _row(frame: pd.DataFrame) -> dict[str, Any]:
    return frame.iloc[0].to_dict() if not frame.empty else {}


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _safe_div(num: float, den: float) -> float:
    return float(num) / float(den) if abs(float(den)) > 1e-12 else np.nan


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    lines = [
        "| " + " | ".join(str(column) for column in data.columns) + " |",
        "| " + " | ".join(["---"] * len(data.columns)) + " |",
    ]
    for _, row in data.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in data.columns) + " |")
    return "\n".join(lines)


def _load_inputs() -> dict[str, Any]:
    return {
        "stage251_curve": _read_csv(STAGE251_CURVE_IN),
        "stage251_summary": _read_csv(STAGE251_SUMMARY_IN),
        "stage255_summary": _row(_read_csv(STAGE255_SUMMARY_IN)),
        "stage259_summary": _row(_read_csv(STAGE259_SUMMARY_IN)),
        "stage259_route": _read_csv(STAGE259_ROUTE_IN),
        "stage259_next": _read_csv(STAGE259_NEXT_IN),
        "stage260_summary": _row(_read_csv(STAGE260_SUMMARY_IN)),
        "stage260_gate": _read_csv(STAGE260_GATE_IN),
        "stage261_import_summary": _row(_read_csv(STAGE261_IMPORT_SUMMARY_IN)),
        "stage261_import_gate": _read_csv(STAGE261_IMPORT_GATE_IN),
        "stage261_outside_summary": _row(_read_csv(STAGE261_OUTSIDE_SUMMARY_IN)),
        "stage261_outside_policy": _read_csv(STAGE261_OUTSIDE_POLICY_IN),
        "stage261_outside_gate": _read_csv(STAGE261_OUTSIDE_GATE_IN),
    }


def _official_summary(stage251_summary: pd.DataFrame) -> dict[str, Any]:
    arm = stage251_summary.get("arm", pd.Series(dtype=str)).astype(str)
    official = stage251_summary[arm.eq("A_official_stage847_c9_15w")]
    return _row(official) if not official.empty else _row(stage251_summary)


def _official_curve(stage251_curve: pd.DataFrame) -> pd.DataFrame:
    curve = stage251_curve.copy()
    arm = curve.get("arm", pd.Series(dtype=str)).astype(str)
    official = curve[arm.eq("A_official_stage847_c9_15w")].copy()
    if official.empty:
        official = curve.copy()
    official["date"] = pd.to_datetime(official["date"], errors="coerce")
    for column in ["account_equity", "drawdown_pct"]:
        official[column] = pd.to_numeric(official[column], errors="coerce")
    return official[official["date"].notna()].sort_values("date").reset_index(drop=True)


def _terminal_route_ledger(inputs: dict[str, Any]) -> pd.DataFrame:
    base = inputs["stage259_route"].copy()
    keep_columns = [
        "route_id",
        "route_family",
        "latest_evidence",
        "current_state",
        "ready_count",
        "denominator_count",
        "context_ready_pct",
        "rule_ready_count",
        "rule_ready_pct",
        "blocker_kind",
        "strategy_rule_allowed",
        "true_engine_allowed",
        "ab_allowed",
        "needs_external_data",
        "next_action",
    ]
    base = base[[column for column in keep_columns if column in base.columns]].copy()
    s260 = inputs["stage260_summary"]
    s261i = inputs["stage261_import_summary"]
    s261o = inputs["stage261_outside_summary"]
    extra = pd.DataFrame(
        [
            {
                "route_id": "execution_replay_import_packet",
                "route_family": "data_intake_infrastructure",
                "latest_evidence": "Stage261 import acceptance packet",
                "current_state": "packet_ready_but_real_data_absent",
                "ready_count": _to_int(s261i.get("required_schema_field_count")),
                "denominator_count": _to_int(s261i.get("required_schema_field_count")),
                "context_ready_pct": 1.0,
                "rule_ready_count": _to_int(s261i.get("accepted_real_replay_package_count")),
                "rule_ready_pct": 0.0,
                "blocker_kind": "real_replay_package_absent",
                "strategy_rule_allowed": 0,
                "true_engine_allowed": 0,
                "ab_allowed": 0,
                "needs_external_data": 1,
                "next_action": "drop real broker/production replay package through Stage261 runbook",
            },
            {
                "route_id": "local_execution_replay_inventory",
                "route_family": "same_source_execution_data",
                "latest_evidence": "Stage260 source inventory",
                "current_state": "no_accepted_same_source_replay_file",
                "ready_count": _to_int(s260.get("accepted_same_source_replay_file_count")),
                "denominator_count": 1,
                "context_ready_pct": 0.0,
                "rule_ready_count": 0,
                "rule_ready_pct": 0.0,
                "blocker_kind": "same_source_execution_missing",
                "strategy_rule_allowed": 0,
                "true_engine_allowed": 0,
                "ab_allowed": 0,
                "needs_external_data": 1,
                "next_action": "external broker replay or authorized orderflow required",
            },
            {
                "route_id": "outside_account_governance_only",
                "route_family": "deployment_governance",
                "latest_evidence": "Stage261 outside-account boundary audit",
                "current_state": "pure_transfer_invariant_no_alpha",
                "ready_count": _to_int(s261o.get("policy_count")),
                "denominator_count": _to_int(s261o.get("policy_count")),
                "context_ready_pct": 1.0,
                "rule_ready_count": _to_int(s261o.get("candidate_ready_count")),
                "rule_ready_pct": 0.0,
                "blocker_kind": "consolidated_drawdown_invariant",
                "strategy_rule_allowed": 0,
                "true_engine_allowed": 0,
                "ab_allowed": 0,
                "needs_external_data": 0,
                "next_action": "may be used for cash-flow planning only, not drawdown-reduction alpha",
            },
        ]
    )
    terminal = pd.concat([base, extra], ignore_index=True)
    terminal["terminal_closed_or_external_wait"] = (
        terminal["strategy_rule_allowed"].astype(int).eq(0)
        & terminal["true_engine_allowed"].astype(int).eq(0)
        & terminal["ab_allowed"].astype(int).eq(0)
    ).astype(int)
    terminal["local_actionable_alpha_now"] = (
        terminal["strategy_rule_allowed"].astype(int).eq(1)
        | terminal["true_engine_allowed"].astype(int).eq(1)
        | terminal["ab_allowed"].astype(int).eq(1)
    ).astype(int)
    return terminal


def _objective_audit(inputs: dict[str, Any], route_ledger: pd.DataFrame) -> pd.DataFrame:
    s255 = inputs["stage255_summary"]
    s259 = inputs["stage259_summary"]
    s260 = inputs["stage260_summary"]
    s261i = inputs["stage261_import_summary"]
    s261o = inputs["stage261_outside_summary"]
    rows = [
        {
            "requirement_id": "new_research_line_based_on_official",
            "status": "proven",
            "pass_now": 1,
            "evidence": "LINE exists and Stage251/255-262 all compare against official A arm.",
        },
        {
            "requirement_id": "reduce_max_drawdown",
            "status": "missing",
            "pass_now": 0,
            "evidence": f"Stage261 outside total DD improvement best nonofficial={_to_float(s261o.get('best_nonofficial_total_dd_improvement_pp')):.4f}pp; no candidate.",
        },
        {
            "requirement_id": "retain_at_least_80pct_return",
            "status": "not_with_drawdown_candidate",
            "pass_now": 0,
            "evidence": f"Only pure transfers retain return={_to_float(s261o.get('best_nonofficial_return_retention')):.4f} but reduce consolidated drawdown by 0; Stage251 active DD gate retained only 0.1260.",
        },
        {
            "requirement_id": "no_overfit_universal_rule",
            "status": "not_applicable_no_rule",
            "pass_now": 0,
            "evidence": "No rule candidate survived; avoiding overfit is satisfied as a guard, not as a completed strategy.",
        },
        {
            "requirement_id": "minute_k_entry_exit_actionable",
            "status": "blocked_by_same_source_data",
            "pass_now": 0,
            "evidence": f"Stage255/260 orderflow/execution replay coverage={_to_int(s260.get('full_orderflow_ready_order_count'))}/{_to_int(s260.get('full_orderflow_expected_order_count'), FULL_ENTRY_DECISION_COUNT)}.",
        },
        {
            "requirement_id": "visual_capital_curve_each_stage",
            "status": "proven_for_completed_stages",
            "pass_now": 1,
            "evidence": "Stages 255-262 generated official capital-path visuals and gate charts.",
        },
        {
            "requirement_id": "high_quality_signal_min_risk_max_return",
            "status": "missing",
            "pass_now": 0,
            "evidence": "Stage259 strategy_rule_allowed_route_count=0; no high-quality actionable signal source remains locally.",
        },
        {
            "requirement_id": "true_engine_or_ab_candidate",
            "status": "missing",
            "pass_now": 0,
            "evidence": f"Stage259 true_engine_allowed={_to_int(s259.get('true_engine_allowed_route_count'))}; Stage261 import accepted packages={_to_int(s261i.get('accepted_real_replay_package_count'))}.",
        },
        {
            "requirement_id": "local_no_external_route_available",
            "status": "proven_terminal",
            "pass_now": 1,
            "evidence": f"Route ledger local_actionable_alpha_now={int(route_ledger['local_actionable_alpha_now'].sum())}; Stage255 minute feature coverage={_to_int(s255.get('minute_feature_ready_order_count'))}/{_to_int(s255.get('minute_feature_expected_order_count'))}.",
        },
    ]
    return pd.DataFrame(rows)


def _blocker_audit(inputs: dict[str, Any]) -> pd.DataFrame:
    s259 = inputs["stage259_summary"]
    s260 = inputs["stage260_summary"]
    s261i = inputs["stage261_import_summary"]
    s261o = inputs["stage261_outside_summary"]
    rows = [
        {
            "blocker_id": "stage259_local_routes_exhausted",
            "evidence_stage": "Stage259",
            "blocking_condition": "all local strategy routes closed or need external data",
            "observed": _to_int(s259.get("strategy_rule_allowed_route_count")),
            "required_to_unblock": 1,
            "still_blocked": 1,
            "external_state_required": 1,
        },
        {
            "blocker_id": "stage260_same_source_replay_absent",
            "evidence_stage": "Stage260",
            "blocking_condition": "no accepted same-source execution replay file and 0/219 coverage",
            "observed": _to_int(s260.get("accepted_same_source_replay_file_count")),
            "required_to_unblock": 1,
            "still_blocked": 1,
            "external_state_required": 1,
        },
        {
            "blocker_id": "stage261_import_packet_no_real_data",
            "evidence_stage": "Stage261 import",
            "blocking_condition": "import packet exists but no real replay package supplied",
            "observed": _to_int(s261i.get("real_replay_package_supplied")),
            "required_to_unblock": 1,
            "still_blocked": 1,
            "external_state_required": 1,
        },
        {
            "blocker_id": "stage261_outside_account_no_alpha",
            "evidence_stage": "Stage261 outside account",
            "blocking_condition": "only local no-external governance route does not reduce consolidated drawdown",
            "observed": _to_float(s261o.get("best_nonofficial_total_dd_improvement_pp")),
            "required_to_unblock": 5.0,
            "still_blocked": 1,
            "external_state_required": 0,
        },
        {
            "blocker_id": "stage262_terminal_confirmation",
            "evidence_stage": "Stage262",
            "blocking_condition": "no local actionable alpha route remains after import packet and governance boundary audit",
            "observed": 0,
            "required_to_unblock": 1,
            "still_blocked": 1,
            "external_state_required": 1,
        },
    ]
    frame = pd.DataFrame(rows)
    frame["counts_toward_repeated_blocker"] = 1
    return frame


def _next_action_queue() -> pd.DataFrame:
    rows = [
        {
            "rank": 1,
            "next_action_id": "supply_real_broker_or_production_execution_replay_package",
            "action_type": "external_state_required",
            "can_start_without_external_state": 0,
            "strategy_rule_allowed_now": 0,
            "reason": "Stage261 import packet is ready; a real package is required to reopen minute execution research.",
        },
        {
            "rank": 2,
            "next_action_id": "procure_or_capture_authorized_orderflow_depth_mbo_mbp10",
            "action_type": "external_state_required",
            "can_start_without_external_state": 0,
            "strategy_rule_allowed_now": 0,
            "reason": "Only higher information orderflow/depth can address early-runway boundary without overfit.",
        },
        {
            "rank": 3,
            "next_action_id": "supply_source_contract_for_physical_or_member_structure",
            "action_type": "external_state_required",
            "can_start_without_external_state": 0,
            "strategy_rule_allowed_now": 0,
            "reason": "Stage257/258 found context coverage but missing source contract, timestamps, license, and role/curve fields.",
        },
        {
            "rank": 4,
            "next_action_id": "stop_local_ohlcv_oi_threshold_and_treasury_rescue",
            "action_type": "closed_stop_condition",
            "can_start_without_external_state": 1,
            "strategy_rule_allowed_now": 0,
            "reason": "Local minute/OHLCV/OI and pure treasury routes are terminally closed for this objective.",
        },
    ]
    return pd.DataFrame(rows)


def _gate(route_ledger: pd.DataFrame, objective: pd.DataFrame, blocker: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "gate_id": "no_official_config_or_order_side_effect",
            "required": 1,
            "observed": 1,
            "pass_now": 1,
            "reason": "Stage262 is read-only terminal audit.",
        },
        {
            "gate_id": "local_actionable_alpha_route_available",
            "required": 1,
            "observed": int(route_ledger["local_actionable_alpha_now"].sum()),
            "pass_now": 0,
            "reason": "No local route allows strategy rule, true engine, or A/B.",
        },
        {
            "gate_id": "objective_requirements_completed",
            "required": len(objective),
            "observed": int(objective["pass_now"].sum()),
            "pass_now": 0,
            "reason": "Core requirements remain missing: drawdown candidate, return-retained universal rule, minute actionable source.",
        },
        {
            "gate_id": "repeated_external_data_blocker_threshold",
            "required": 3,
            "observed": int(blocker["counts_toward_repeated_blocker"].sum()),
            "pass_now": 1,
            "reason": "Same blocker appears across Stage259, Stage260, Stage261 import, Stage261 outside, and Stage262.",
        },
        {
            "gate_id": "meaningful_progress_without_external_state",
            "required": 1,
            "observed": 0,
            "pass_now": 0,
            "reason": "Import packet and outside-account boundary are done; remaining progress requires new data/user-supplied package.",
        },
    ]
    return pd.DataFrame(rows)


def _summary(inputs: dict[str, Any], route_ledger: pd.DataFrame, objective: pd.DataFrame, blocker: pd.DataFrame, gate: pd.DataFrame) -> dict[str, Any]:
    official = _official_summary(inputs["stage251_summary"])
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": "stage262_local_route_terminal_blocked_external_data_required",
        "stage_nature": "read_only_terminal_local_route_and_blocker_audit",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_or_simnow_connected": 0,
        "terminal_route_count": int(len(route_ledger)),
        "local_actionable_alpha_route_count": int(route_ledger["local_actionable_alpha_now"].sum()),
        "external_state_required_route_count": int(pd.to_numeric(route_ledger["needs_external_data"], errors="coerce").fillna(0).sum()),
        "objective_requirement_count": int(len(objective)),
        "objective_requirement_pass_count": int(objective["pass_now"].sum()),
        "core_objective_completed": 0,
        "blocker_evidence_count": int(len(blocker)),
        "repeated_blocker_threshold_satisfied": int(blocker["counts_toward_repeated_blocker"].sum() >= 3),
        "terminal_gate_count": int(len(gate)),
        "terminal_gate_pass_count": int(gate["pass_now"].sum()),
        "meaningful_progress_without_external_state": 0,
        "official_end_equity": _to_float(official.get("end_equity")),
        "official_total_return_pct": _to_float(official.get("total_return_pct")),
        "official_max_dd_pct": _to_float(official.get("max_dd_pct")),
        "official_sharpe": _to_float(official.get("sharpe")),
        "official_total_slippage": _to_float(official.get("total_slippage")),
        "official_total_trade_count": _to_float(official.get("total_trade_count")),
        "official_win_rate_pct": _to_float(official.get("nonzero_daily_win_rate_pct")),
        "official_broker10_peak_pct": _to_float(official.get("max_broker10_margin_to_equity_pct")),
        "visual_file_count": 5,
    }


def _plot_official_path(curve: pd.DataFrame, summary: dict[str, Any]) -> None:
    fig, ax1 = plt.subplots(figsize=(13, 6))
    ax1.plot(curve["date"], curve["account_equity"], color="#1f4e79", linewidth=1.8)
    ax1.set_ylabel("Equity")
    ax1.grid(True, axis="y", alpha=0.25)
    ax2 = ax1.twinx()
    ax2.fill_between(curve["date"], curve["drawdown_pct"], 0, color="#d6616b", alpha=0.16)
    ax2.set_ylabel("Drawdown %")
    ax1.set_title("Stage262 official path with terminal local-route status")
    text = (
        f"local actionable alpha routes: {summary['local_actionable_alpha_route_count']} | "
        f"objective pass: {summary['objective_requirement_pass_count']}/{summary['objective_requirement_count']} | "
        "external data required"
    )
    ax1.text(
        0.01,
        0.96,
        text,
        transform=ax1.transAxes,
        va="top",
        ha="left",
        fontsize=10,
        bbox={"boxstyle": "round,pad=0.35", "fc": "white", "ec": "#888888", "alpha": 0.9},
    )
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_route_matrix(route_ledger: pd.DataFrame) -> None:
    columns = ["strategy_rule_allowed", "true_engine_allowed", "ab_allowed", "needs_external_data", "terminal_closed_or_external_wait"]
    top = route_ledger.copy()
    data = top[columns].apply(pd.to_numeric, errors="coerce").fillna(0).to_numpy(dtype=float)
    labels = top["route_id"].astype(str).tolist()
    fig_height = max(6, len(labels) * 0.38)
    fig, ax = plt.subplots(figsize=(11, fig_height))
    ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xticks(range(len(columns)))
    ax.set_xticklabels(columns, rotation=30, ha="right", fontsize=8)
    for y in range(data.shape[0]):
        for x in range(data.shape[1]):
            ax.text(x, y, str(int(data[y, x])), ha="center", va="center", fontsize=8)
    ax.set_title("Stage262 terminal route matrix")
    fig.tight_layout()
    fig.savefig(ROUTE_MATRIX_OUT, dpi=160)
    plt.close(fig)


def _plot_objective(objective: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 5))
    colors = ["#2ca02c" if value else "#c44e52" for value in objective["pass_now"]]
    ax.barh(objective["requirement_id"], objective["pass_now"], color=colors)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.2)
    ax.set_title("Stage262 objective requirement audit")
    for idx, row in objective.iterrows():
        ax.text(1.02, idx, str(row["status"]), va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(OBJECTIVE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_blocker(blocker: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 5))
    x = np.arange(len(blocker))
    ax.bar(x, blocker["still_blocked"].astype(int), color="#c44e52")
    ax.set_xticks(x)
    ax.set_xticklabels(blocker["evidence_stage"], rotation=20, ha="right")
    ax.set_ylim(0, 1.2)
    ax.set_title("Stage262 repeated blocker evidence chain")
    for idx, row in blocker.iterrows():
        ax.text(idx, 1.03, row["blocker_id"], ha="center", va="bottom", fontsize=7, rotation=90)
    fig.tight_layout()
    fig.savefig(BLOCKER_CHAIN_OUT, dpi=160)
    plt.close(fig)


def _plot_next_action(next_action: pd.DataFrame) -> None:
    columns = ["can_start_without_external_state", "strategy_rule_allowed_now"]
    data = next_action[columns].to_numpy(dtype=float)
    labels = next_action["next_action_id"].astype(str).tolist()
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xticks(range(len(columns)))
    ax.set_xticklabels(["no external", "rule now"], rotation=25, ha="right")
    for y in range(data.shape[0]):
        for x in range(data.shape[1]):
            ax.text(x, y, str(int(data[y, x])), ha="center", va="center", fontsize=8)
    ax.set_title("Stage262 next action status")
    fig.tight_layout()
    fig.savefig(NEXT_ACTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(summary: dict[str, Any], route_ledger: pd.DataFrame, objective: pd.DataFrame, blocker: pd.DataFrame, gate: pd.DataFrame, next_action: pd.DataFrame) -> None:
    report = f"""# Stage262 Local Route Terminal Blocker Audit

- line_id: `{LINE_ID}`
- created_at: `{summary['created_at']}`
- decision: `{summary['decision']}`
- nature: read-only terminal audit; no strategy rule, no true engine, no A/B, no CTP/SimNow connection.

## Summary

- terminal routes audited: `{summary['terminal_route_count']}`
- local actionable alpha routes now: `{summary['local_actionable_alpha_route_count']}`
- external-state routes: `{summary['external_state_required_route_count']}`
- objective requirement pass: `{summary['objective_requirement_pass_count']}/{summary['objective_requirement_count']}`
- repeated blocker evidence count: `{summary['blocker_evidence_count']}`
- repeated blocker threshold satisfied: `{summary['repeated_blocker_threshold_satisfied']}`
- meaningful progress without external state: `{summary['meaningful_progress_without_external_state']}`

## Interpretation

The line has not achieved the objective. It has, however, exhausted the local no-external paths without creating an overfit rule. Minute/formal feature coverage is complete, but actionable orderflow/execution replay remains missing. Pure outside-account transfers do not reduce consolidated drawdown. The only meaningful next state change is external: real broker/production execution replay, authorized orderflow/depth/MBO/MBP10, or a licensed source contract for physical/member structure.

## Objective Audit

{_md_table(objective)}

## Route Ledger

{_md_table(route_ledger, max_rows=30)}

## Blocker Audit

{_md_table(blocker)}

## Terminal Gate

{_md_table(gate)}

## Next Action

{_md_table(next_action)}

## Files

- `{SUMMARY_OUT}`
- `{TERMINAL_ROUTE_OUT}`
- `{OBJECTIVE_AUDIT_OUT}`
- `{BLOCKER_AUDIT_OUT}`
- `{GATE_OUT}`
- `{NEXT_ACTION_OUT}`
- `{PATH_CHART_OUT}`
- `{ROUTE_MATRIX_OUT}`
- `{OBJECTIVE_CHART_OUT}`
- `{BLOCKER_CHAIN_OUT}`
- `{NEXT_ACTION_CHART_OUT}`
"""
    _write_text(REPORT_OUT, report)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    inputs = _load_inputs()
    route_ledger = _terminal_route_ledger(inputs)
    objective = _objective_audit(inputs, route_ledger)
    blocker = _blocker_audit(inputs)
    gate = _gate(route_ledger, objective, blocker)
    next_action = _next_action_queue()
    summary = _summary(inputs, route_ledger, objective, blocker, gate)
    curve = _official_curve(inputs["stage251_curve"])

    _write_csv(pd.DataFrame([summary]), SUMMARY_OUT)
    _write_csv(route_ledger, TERMINAL_ROUTE_OUT)
    _write_csv(objective, OBJECTIVE_AUDIT_OUT)
    _write_csv(blocker, BLOCKER_AUDIT_OUT)
    _write_csv(gate, GATE_OUT)
    _write_csv(next_action, NEXT_ACTION_OUT)
    _write_json(DECISION_OUT, summary)
    _write_report(summary, route_ledger, objective, blocker, gate, next_action)

    _plot_official_path(curve, summary)
    _plot_route_matrix(route_ledger)
    _plot_objective(objective)
    _plot_blocker(blocker)
    _plot_next_action(next_action)

    print(json.dumps(_json_safe(summary), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
