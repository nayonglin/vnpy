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
STAGE = "Stage259"
MODEL_TAG = "stage259_remaining_route_exhaustion_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage259_c9_minrisk_remaining_route_exhaustion_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage259_remaining_route_exhaustion_audit"

STAGE099_DIR = LINE_DIR / "outputs" / "stage099_finer_source_feasibility_manifest"
STAGE099_PREFIX = "qmt_roll_stage099_c9_minrisk_finer_source_feasibility_manifest"
STAGE099_TAG = "stage099_finer_source_feasibility_manifest_v1"

STAGE107_DIR = LINE_DIR / "outputs" / "stage107_contract_month_oi_patched_root_reaudit"
STAGE107_PREFIX = "qmt_roll_stage107_c9_minrisk_contract_month_oi_patched_root_reaudit"
STAGE107_TAG = "stage107_contract_month_oi_patched_root_reaudit_v1"

STAGE148_DIR = LINE_DIR / "outputs" / "stage148_objective_gap_route_audit"
STAGE148_PREFIX = "qmt_roll_stage148_c9_minrisk_objective_gap_route_audit"
STAGE148_TAG = "stage148_objective_gap_route_audit_v1"

STAGE249_DIR = LINE_DIR / "outputs" / "stage249_early_runway_frontier_audit"
STAGE249_PREFIX = "qmt_roll_stage249_c9_minrisk_early_runway_frontier_audit"
STAGE249_TAG = "stage249_early_runway_frontier_audit_v1"

STAGE251_DIR = LINE_DIR / "outputs" / "stage251_dd30_account_floor_true_engine"
STAGE251_PREFIX = "qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine"
STAGE251_TAG = "stage251_dd30_account_floor_true_engine_v1"

STAGE252_DIR = LINE_DIR / "outputs" / "stage252_price_volume_consensus_preflight"
STAGE252_PREFIX = "qmt_roll_stage252_c9_minrisk_price_volume_consensus_preflight"
STAGE252_TAG = "stage252_price_volume_consensus_preflight_v1"

STAGE253_DIR = LINE_DIR / "outputs" / "stage253_price_oi_confirmation_preflight"
STAGE253_PREFIX = "qmt_roll_stage253_c9_minrisk_price_oi_confirmation_preflight"
STAGE253_TAG = "stage253_price_oi_confirmation_preflight_v1"

STAGE254_DIR = LINE_DIR / "outputs" / "stage254_aligned_price_oi_contract_audit"
STAGE254_PREFIX = "qmt_roll_stage254_c9_minrisk_aligned_price_oi_contract_audit"
STAGE254_TAG = "stage254_aligned_price_oi_contract_audit_v1"

STAGE255_DIR = LINE_DIR / "outputs" / "stage255_microstructure_coverage_closure_audit"
STAGE255_PREFIX = "qmt_roll_stage255_c9_minrisk_microstructure_coverage_closure_audit"
STAGE255_TAG = "stage255_microstructure_coverage_closure_audit_v1"

STAGE256_DIR = LINE_DIR / "outputs" / "stage256_cftc_cot_cross_market_context_audit"
STAGE256_PREFIX = "qmt_roll_stage256_c9_minrisk_cftc_cot_cross_market_context_audit"
STAGE256_TAG = "stage256_cftc_cot_cross_market_context_audit_v1"

STAGE257_DIR = LINE_DIR / "outputs" / "stage257_member_category_seat_structure_source_audit"
STAGE257_PREFIX = "qmt_roll_stage257_c9_minrisk_member_category_seat_structure_source_audit"
STAGE257_TAG = "stage257_member_category_seat_structure_source_audit_v1"

STAGE258_DIR = LINE_DIR / "outputs" / "stage258_inventory_basis_term_structure_source_audit"
STAGE258_PREFIX = "qmt_roll_stage258_c9_minrisk_inventory_basis_term_structure_source_audit"
STAGE258_TAG = "stage258_inventory_basis_term_structure_source_audit_v1"

STAGE239_DIR = LINE_DIR / "outputs" / "stage239_read_only_universal_signal_quality_audit"
STAGE239_PREFIX = "qmt_roll_stage239_c9_minrisk_read_only_universal_signal_quality_audit"
STAGE239_TAG = "stage239_read_only_universal_signal_quality_audit_v1"

STAGE099_MANIFEST_IN = STAGE099_DIR / f"{STAGE099_PREFIX}_manifest_{STAGE099_TAG}.csv"
STAGE099_PRIORITY_IN = STAGE099_DIR / f"{STAGE099_PREFIX}_priority_matrix_{STAGE099_TAG}.csv"
STAGE107_SUMMARY_IN = STAGE107_DIR / f"{STAGE107_PREFIX}_summary_{STAGE107_TAG}.csv"
STAGE148_SUMMARY_IN = STAGE148_DIR / f"{STAGE148_PREFIX}_summary_{STAGE148_TAG}.csv"
STAGE148_ROUTE_IN = STAGE148_DIR / f"{STAGE148_PREFIX}_route_scorecard_{STAGE148_TAG}.csv"
STAGE249_SUMMARY_IN = STAGE249_DIR / f"{STAGE249_PREFIX}_summary_{STAGE249_TAG}.csv"
STAGE251_CURVE_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_curve_{STAGE251_TAG}.csv"
STAGE251_SUMMARY_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_summary_{STAGE251_TAG}.csv"
STAGE252_SUMMARY_IN = STAGE252_DIR / f"{STAGE252_PREFIX}_summary_{STAGE252_TAG}.csv"
STAGE253_SUMMARY_IN = STAGE253_DIR / f"{STAGE253_PREFIX}_summary_{STAGE253_TAG}.csv"
STAGE254_SUMMARY_IN = STAGE254_DIR / f"{STAGE254_PREFIX}_summary_{STAGE254_TAG}.csv"
STAGE255_SUMMARY_IN = STAGE255_DIR / f"{STAGE255_PREFIX}_summary_{STAGE255_TAG}.csv"
STAGE255_ROUTE_IN = STAGE255_DIR / f"{STAGE255_PREFIX}_route_status_{STAGE255_TAG}.csv"
STAGE256_SUMMARY_IN = STAGE256_DIR / f"{STAGE256_PREFIX}_summary_{STAGE256_TAG}.csv"
STAGE257_SUMMARY_IN = STAGE257_DIR / f"{STAGE257_PREFIX}_summary_{STAGE257_TAG}.csv"
STAGE258_SUMMARY_IN = STAGE258_DIR / f"{STAGE258_PREFIX}_summary_{STAGE258_TAG}.csv"
STAGE239_JOINED_IN = STAGE239_DIR / f"{STAGE239_PREFIX}_joined_signal_label_audit_{STAGE239_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
ROUTE_LEDGER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_ledger_{MODEL_TAG}.csv"
OBJECTIVE_GAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_objective_gap_{MODEL_TAG}.csv"
NEXT_ACTION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_action_queue_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_route_exhaustion_{MODEL_TAG}.png"
ROUTE_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_readiness_matrix_{MODEL_TAG}.png"
COVERAGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_coverage_gap_chart_{MODEL_TAG}.png"
OBJECTIVE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_objective_gap_chart_{MODEL_TAG}.png"
NEXT_ACTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_action_queue_chart_{MODEL_TAG}.png"


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
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
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return number if np.isfinite(number) else None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_div(num: float, den: float) -> float:
    return float(num) / float(den) if abs(float(den)) > 1e-12 else np.nan


def _first(frame: pd.DataFrame) -> dict[str, Any]:
    return frame.iloc[0].to_dict() if not frame.empty else {}


def _load_inputs() -> dict[str, pd.DataFrame]:
    return {
        "manifest": _read_csv(STAGE099_MANIFEST_IN),
        "priority": _read_csv(STAGE099_PRIORITY_IN),
        "stage107_summary": _read_csv(STAGE107_SUMMARY_IN),
        "stage148_summary": _read_csv(STAGE148_SUMMARY_IN),
        "stage148_route": _read_csv(STAGE148_ROUTE_IN),
        "stage249_summary": _read_csv(STAGE249_SUMMARY_IN),
        "stage251_curve": _read_csv(STAGE251_CURVE_IN),
        "stage251_summary": _read_csv(STAGE251_SUMMARY_IN),
        "stage252_summary": _read_csv(STAGE252_SUMMARY_IN),
        "stage253_summary": _read_csv(STAGE253_SUMMARY_IN),
        "stage254_summary": _read_csv(STAGE254_SUMMARY_IN),
        "stage255_summary": _read_csv(STAGE255_SUMMARY_IN),
        "stage255_route": _read_csv(STAGE255_ROUTE_IN),
        "stage256_summary": _read_csv(STAGE256_SUMMARY_IN),
        "stage257_summary": _read_csv(STAGE257_SUMMARY_IN),
        "stage258_summary": _read_csv(STAGE258_SUMMARY_IN),
        "stage239_joined": _read_csv(STAGE239_JOINED_IN),
    }


def _official_summary(stage251_summary: pd.DataFrame) -> dict[str, Any]:
    official = stage251_summary[stage251_summary.get("arm", pd.Series(dtype=str)).astype(str).eq("A_official_stage847_c9_15w")]
    return _first(official) if not official.empty else _first(stage251_summary)


def _build_route_ledger(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    s107 = _first(inputs["stage107_summary"])
    s249 = _first(inputs["stage249_summary"])
    s252 = _first(inputs["stage252_summary"])
    s253 = _first(inputs["stage253_summary"])
    s254 = _first(inputs["stage254_summary"])
    s255 = _first(inputs["stage255_summary"])
    s256 = _first(inputs["stage256_summary"])
    s257 = _first(inputs["stage257_summary"])
    s258 = _first(inputs["stage258_summary"])
    stage251 = inputs["stage251_summary"]
    official = _official_summary(stage251)
    c_floor = stage251[stage251.get("arm", pd.Series(dtype=str)).astype(str).eq("C_stage251_dd30_half_account_floor")]
    c_floor_row = _first(c_floor)
    official_return = _to_float(official.get("total_return_pct"))
    c_return = _to_float(c_floor_row.get("total_return_pct"))
    c_dd = _to_float(c_floor_row.get("max_dd_pct"))
    official_dd = _to_float(official.get("max_dd_pct"))
    account_return_retention = _safe_div(c_return, official_return)
    account_dd_improvement = abs(official_dd) - abs(c_dd)

    rows = [
        {
            "route_id": "stage045_timestamp_ready_replay_new_candidate",
            "route_family": "internal_minute_replay",
            "latest_evidence": "Stage249/252/253/254",
            "current_state": "closed_no_local_minute_rule",
            "ready_count": _to_int(s249.get("timestamp_ready_order_count")),
            "denominator_count": 219,
            "context_ready_pct": _safe_div(_to_int(s249.get("timestamp_ready_order_count")), 219),
            "rule_ready_count": 0,
            "rule_ready_pct": 0.0,
            "right_tail_protection": "fail: early runway carries 9/18 right-tail and 9/18 bottom-loss; existing features conflict",
            "blocker_kind": "tail_conflict",
            "strategy_rule_allowed": 0,
            "true_engine_allowed": 0,
            "ab_allowed": 0,
            "needs_external_data": 1,
            "next_action": "stop local threshold rescue; only reopen with higher-information preentry/execution source",
            "key_metric": f"early_pnl_share={_to_float(s249.get('early_runway_pnl_share')):.4f}; pv_split={_to_int(s252.get('split_pass_count'))}/{_to_int(s252.get('valid_split_count'))}; oi_contract_split={_to_int(s254.get('split_pass_count'))}/{_to_int(s254.get('valid_split_count'))}",
        },
        {
            "route_id": "same_source_executable_minute_bars",
            "route_family": "execution_data",
            "latest_evidence": "Stage255",
            "current_state": "minute_feature_complete_but_same_source_execution_missing",
            "ready_count": _to_int(s255.get("minute_feature_ready_order_count")),
            "denominator_count": _to_int(s255.get("minute_feature_expected_order_count")),
            "context_ready_pct": _safe_div(s255.get("minute_feature_ready_order_count", 0), s255.get("minute_feature_expected_order_count", 0)),
            "rule_ready_count": _to_int(s255.get("full_orderflow_ready_order_count")),
            "rule_ready_pct": _safe_div(s255.get("full_orderflow_ready_order_count", 0), s255.get("full_orderflow_expected_order_count", 0)),
            "right_tail_protection": "not testable: broker/production replay missing for all entries",
            "blocker_kind": "same_source_execution_missing",
            "strategy_rule_allowed": 0,
            "true_engine_allowed": 0,
            "ab_allowed": 0,
            "needs_external_data": 1,
            "next_action": "import broker or production execution replay with order/fill/raw provenance",
            "key_metric": f"minute={_to_int(s255.get('minute_feature_ready_order_count'))}/{_to_int(s255.get('minute_feature_expected_order_count'))}; orderflow={_to_int(s255.get('full_orderflow_ready_order_count'))}/{_to_int(s255.get('full_orderflow_expected_order_count'))}",
        },
        {
            "route_id": "authorized_quote_depth_orderflow",
            "route_family": "microstructure",
            "latest_evidence": "Stage255",
            "current_state": "procurement_required",
            "ready_count": _to_int(s255.get("full_orderflow_ready_order_count")),
            "denominator_count": _to_int(s255.get("full_orderflow_expected_order_count")),
            "context_ready_pct": _safe_div(s255.get("full_orderflow_ready_order_count", 0), s255.get("full_orderflow_expected_order_count", 0)),
            "rule_ready_count": 0,
            "rule_ready_pct": 0.0,
            "right_tail_protection": "not testable without MBO/MBP10/depth/trade feed",
            "blocker_kind": "authorized_data_missing",
            "strategy_rule_allowed": 0,
            "true_engine_allowed": 0,
            "ab_allowed": 0,
            "needs_external_data": 1,
            "next_action": "procure authorized MBO/MBP10/depth/trade archive or run forward W0 capture",
            "key_metric": f"real_w0_request={_to_int(s255.get('real_w0_ready_request_count'))}/{_to_int(s255.get('real_w0_expected_request_count'))}; schema_ready={_to_int(s255.get('orderflow_schema_ready_count'))}",
        },
        {
            "route_id": "contract_month_oi_migration",
            "route_family": "contract_curve_structure",
            "latest_evidence": "Stage107",
            "current_state": "data_asset_ready_explanation_only",
            "ready_count": _to_int(s107.get("adjusted_panel_ready_count")),
            "denominator_count": _to_int(s107.get("timestamp_ready_order_count")),
            "context_ready_pct": _safe_div(s107.get("adjusted_panel_ready_count", 0), s107.get("timestamp_ready_order_count", 0)),
            "rule_ready_count": _to_int(s107.get("panel_feature_rule_allowed")),
            "rule_ready_pct": 0.0,
            "right_tail_protection": "fail for rule: rank/share concentrated in rank1 and one single-contract bottom-loss blocks migration comparison",
            "blocker_kind": "explanation_only_tail_conflict",
            "strategy_rule_allowed": 0,
            "true_engine_allowed": 0,
            "ab_allowed": 0,
            "needs_external_data": 0,
            "next_action": "keep as forward-watch/explanation asset; no rank/share rule or rescue split",
            "key_metric": f"adjusted_panel={_to_int(s107.get('adjusted_panel_ready_count'))}/{_to_int(s107.get('timestamp_ready_order_count'))}; single_contract={_to_int(s107.get('single_contract_panel_count'))}",
        },
        {
            "route_id": "member_category_seat_structure",
            "route_family": "external_position_structure",
            "latest_evidence": "Stage257",
            "current_state": "schema_permission_gap",
            "ready_count": _to_int(s257.get("entry_product_total_numeric_ready_count")),
            "denominator_count": _to_int(s257.get("entry_count")),
            "context_ready_pct": _to_float(s257.get("entry_product_total_numeric_ready_pct")),
            "rule_ready_count": _to_int(s257.get("role_ready_entry_count")),
            "rule_ready_pct": _to_float(s257.get("role_ready_entry_pct")),
            "right_tail_protection": "not testable: member category/seat/source license absent",
            "blocker_kind": "schema_permission_gap",
            "strategy_rule_allowed": 0,
            "true_engine_allowed": 0,
            "ab_allowed": 0,
            "needs_external_data": 1,
            "next_action": "obtain stable member/seat id, category, contract-month source, publish timestamp and license",
            "key_metric": f"product_total={_to_int(s257.get('entry_product_total_numeric_ready_count'))}/{_to_int(s257.get('entry_count'))}; role={_to_int(s257.get('role_ready_entry_count'))}/{_to_int(s257.get('entry_count'))}",
        },
        {
            "route_id": "inventory_basis_term_structure",
            "route_family": "physical_market_structure",
            "latest_evidence": "Stage258",
            "current_state": "source_contract_gap",
            "ready_count": _to_int(s258.get("cache_joint_ready_entry_count")),
            "denominator_count": _to_int(s258.get("entry_count")),
            "context_ready_pct": _to_float(s258.get("cache_joint_ready_entry_pct")),
            "rule_ready_count": _to_int(s258.get("full_contract_rule_ready_entry_count")),
            "rule_ready_pct": _to_float(s258.get("full_contract_rule_ready_entry_pct")),
            "right_tail_protection": "not testable: timestamp/license/publication lag/full curve missing",
            "blocker_kind": "source_contract_gap",
            "strategy_rule_allowed": 0,
            "true_engine_allowed": 0,
            "ab_allowed": 0,
            "needs_external_data": 1,
            "next_action": "obtain authorized spot/basis, full warehouse raw/hash, publication lag calendar and curve panel",
            "key_metric": f"cache_joint={_to_int(s258.get('cache_joint_ready_entry_count'))}/{_to_int(s258.get('entry_count'))}; full_contract={_to_int(s258.get('full_contract_rule_ready_entry_count'))}/{_to_int(s258.get('entry_count'))}",
        },
        {
            "route_id": "cftc_cot_cross_market_context",
            "route_family": "external_cross_market_context",
            "latest_evidence": "Stage256",
            "current_state": "low_coverage_tail_conflict",
            "ready_count": _to_int(s256.get("mapped_matched_order_count")),
            "denominator_count": _to_int(s256.get("entry_order_count")),
            "context_ready_pct": _to_float(s256.get("matched_coverage_rate")),
            "rule_ready_count": 0,
            "rule_ready_pct": 0.0,
            "right_tail_protection": "fail: supportive group risk_bad worse and captures only 2/18 right-tail",
            "blocker_kind": "coverage_and_tail_conflict",
            "strategy_rule_allowed": 0,
            "true_engine_allowed": 0,
            "ab_allowed": 0,
            "needs_external_data": 0,
            "next_action": "keep as macro/context note only; do not sweep mapping or COT thresholds",
            "key_metric": f"matched={_to_int(s256.get('mapped_matched_order_count'))}/{_to_int(s256.get('entry_order_count'))}; supportive_pnl={_to_float(s256.get('supportive_pnl_sum')):.0f}",
        },
        {
            "route_id": "account_dd30_floor_true_engine",
            "route_family": "deployment_account_overlay",
            "latest_evidence": "Stage251",
            "current_state": "true_engine_return_retention_failed",
            "ready_count": 1,
            "denominator_count": 1,
            "context_ready_pct": 1.0,
            "rule_ready_count": 0,
            "rule_ready_pct": 0.0,
            "right_tail_protection": "fail: true engine cuts 2021/2023/2025 compounding and retains only a small fraction of return",
            "blocker_kind": "return_retention_failed",
            "strategy_rule_allowed": 0,
            "true_engine_allowed": 0,
            "ab_allowed": 0,
            "needs_external_data": 0,
            "next_action": "do not sweep DD floors; only consider outside-account capital governance that does not change holdings",
            "key_metric": f"return_retention={account_return_retention:.4f}; dd_improvement_pp={account_dd_improvement:.4f}",
        },
    ]
    frame = pd.DataFrame(rows)
    frame["context_missing_count"] = frame["denominator_count"] - frame["ready_count"]
    frame["rule_missing_count"] = frame["denominator_count"] - frame["rule_ready_count"]
    frame["local_rule_candidate_allowed"] = 0
    return frame


def _build_objective_gap(route_ledger: pd.DataFrame, inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    s148 = _first(inputs["stage148_summary"])
    s249 = _first(inputs["stage249_summary"])
    s255 = _first(inputs["stage255_summary"])
    s258 = _first(inputs["stage258_summary"])
    rows = [
        ("official_baseline_preserved", 1, "No official config, CTP, SimNow or order API side effect in Stage249-259 audits."),
        ("minute_feature_coverage_complete", int(_to_int(s255.get("minute_feature_ready_order_count")) == 219), "Stage255 confirms 219/219 minute feature rows and 2190/2190 cells."),
        ("capital_curve_visuals_generated", 1, "Each audit generated official path or capital curve visuals; Stage259 also plots official path."),
        ("max_drawdown_reduction_candidate_exists", 0, "No current candidate reduces drawdown in true engine while preserving return."),
        ("return_retention_ge_80pct_proven", 0, "Stage251 DD30 true engine retained far below 80%; local minute candidates never reached true engine."),
        ("universal_no_overfit_rule_proven", 0, "Split/tail gates fail for local price-volume/OI and early-runway routes."),
        ("right_tail_protection_proven", 0, f"Stage249 early runway contains {_to_int(s249.get('early_runway_right_tail_count'))}/18 right-tail and {_to_int(s249.get('early_runway_bottom_loss_count'))}/18 bottom-loss."),
        ("same_source_execution_or_orderflow_ready", 0, f"Stage255 full orderflow ready {_to_int(s255.get('full_orderflow_ready_order_count'))}/{_to_int(s255.get('full_orderflow_expected_order_count'))}."),
        ("external_source_contract_ready", 0, f"Stage258 physical-market full contract ready {_to_int(s258.get('full_contract_rule_ready_entry_count'))}/{_to_int(s258.get('entry_count'))}."),
        ("true_engine_or_ab_allowed", int(route_ledger["true_engine_allowed"].sum() > 0), "All remaining routes have true_engine_allowed=0 and ab_allowed=0."),
    ]
    frame = pd.DataFrame(rows, columns=["requirement", "proven", "evidence"])
    frame["stage"] = STAGE
    frame["model_tag"] = MODEL_TAG
    frame["prior_objective_missing_requirement_count_stage148"] = _to_int(s148.get("objective_missing_requirement_count"))
    return frame


def _build_next_action_queue(route_ledger: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "rank": 1,
            "next_action_id": "procure_or_capture_authorized_orderflow",
            "action_type": "external_data",
            "can_start_without_external_state": 0,
            "expected_goal_alignment": 3,
            "overfit_risk_if_done_right": 1,
            "reason": "Only route with enough information density to decide before or at early progress boundary.",
        },
        {
            "rank": 2,
            "next_action_id": "import_broker_or_production_execution_replay",
            "action_type": "same_source_replay",
            "can_start_without_external_state": 0,
            "expected_goal_alignment": 3,
            "overfit_risk_if_done_right": 1,
            "reason": "Would replace proxy minute semantics with executable order/fill replay.",
        },
        {
            "rank": 3,
            "next_action_id": "license_spot_basis_warehouse_curve_contract",
            "action_type": "external_data",
            "can_start_without_external_state": 0,
            "expected_goal_alignment": 2,
            "overfit_risk_if_done_right": 1,
            "reason": "Physical-market data can be universal, but current cache lacks source contract.",
        },
        {
            "rank": 4,
            "next_action_id": "obtain_member_category_seat_contract",
            "action_type": "external_data",
            "can_start_without_external_state": 0,
            "expected_goal_alignment": 2,
            "overfit_risk_if_done_right": 1,
            "reason": "Role-separated risk taker data might be useful, but public product-total rank is insufficient.",
        },
        {
            "rank": 5,
            "next_action_id": "outside_account_capital_governance_only",
            "action_type": "deployment_governance",
            "can_start_without_external_state": 1,
            "expected_goal_alignment": 1,
            "overfit_risk_if_done_right": 1,
            "reason": "May improve user experience only if it does not change production holdings; not alpha.",
        },
    ]
    frame = pd.DataFrame(rows)
    frame["strategy_rule_allowed_now"] = 0
    frame["true_engine_allowed_now"] = 0
    return frame


def _build_gate(route_ledger: pd.DataFrame, objective_gap: pd.DataFrame) -> pd.DataFrame:
    rows = [
        ("minute_feature_coverage_complete", int((route_ledger["route_id"].eq("same_source_executable_minute_bars") & (route_ledger["ready_count"] == 219)).any()), "Local minute feature coverage is no longer the gap."),
        ("all_routes_reviewed", int(len(route_ledger) >= 8), "Stage099 routes plus COT/account overlay were reviewed."),
        ("local_rule_candidate_available", 0, "No local route has strategy_rule_allowed=1."),
        ("true_engine_route_available", int(route_ledger["true_engine_allowed"].sum() > 0), "No remaining route can run true engine now."),
        ("return_retention_80_candidate_available", 0, "No current candidate has proven return retention >=80% with drawdown improvement."),
        ("source_contract_ready", 0, "External/member/physical/orderflow source contracts are incomplete."),
        ("right_tail_gate_passed", 0, "Early-runway, price-volume, OI and external context routes have tail conflicts."),
        ("ab_allowed", int(route_ledger["ab_allowed"].sum() > 0), "No A/B trigger."),
        ("order_api_called", 0, "Audit only."),
    ]
    frame = pd.DataFrame(rows, columns=["gate", "passed", "reason"])
    frame["stage"] = STAGE
    frame["model_tag"] = MODEL_TAG
    return frame


def _build_summary(route_ledger: pd.DataFrame, objective_gap: pd.DataFrame, gate: pd.DataFrame, inputs: dict[str, pd.DataFrame]) -> dict[str, Any]:
    official = _official_summary(inputs["stage251_summary"])
    closed_or_blocked = int(route_ledger["strategy_rule_allowed"].eq(0).sum())
    summary = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "run_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": "stage259_remaining_local_routes_exhausted_no_rule_external_data_or_deployment_only",
        "route_count": len(route_ledger),
        "closed_or_blocked_route_count": closed_or_blocked,
        "strategy_rule_allowed_route_count": int(route_ledger["strategy_rule_allowed"].sum()),
        "true_engine_allowed_route_count": int(route_ledger["true_engine_allowed"].sum()),
        "ab_allowed_route_count": int(route_ledger["ab_allowed"].sum()),
        "needs_external_data_route_count": int(route_ledger["needs_external_data"].sum()),
        "objective_requirement_count": len(objective_gap),
        "objective_proven_requirement_count": int(objective_gap["proven"].sum()),
        "objective_missing_requirement_count": int((1 - objective_gap["proven"]).sum()),
        "gate_pass_count": int(gate["passed"].sum()),
        "gate_total_count": len(gate),
        "official_end_equity": _to_float(official.get("end_equity")),
        "official_total_return_pct": _to_float(official.get("total_return_pct")),
        "official_max_dd_pct": _to_float(official.get("max_dd_pct")),
        "official_sharpe": _to_float(official.get("sharpe")),
        "official_total_slippage": _to_float(official.get("total_slippage")),
        "official_total_trade_count": _to_float(official.get("total_trade_count")),
        "official_win_rate_pct": _to_float(official.get("nonzero_daily_win_rate_pct")),
        "official_broker10_peak_pct": _to_float(official.get("max_broker10_margin_to_equity_pct")),
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_or_simnow_connected": 0,
    }
    return summary


def _plot_official_path(inputs: dict[str, pd.DataFrame], route_ledger: pd.DataFrame) -> None:
    curve = inputs["stage251_curve"].copy()
    if "arm" in curve.columns:
        curve = curve[curve["arm"].astype(str).eq("A_official_stage847_c9_15w")].copy()
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce")
    curve = curve[curve["date"].notna()].sort_values("date")
    entries = inputs["stage239_joined"].copy()
    entries["date"] = pd.to_datetime(entries["official_open_date"], errors="coerce")
    entries = entries[entries["date"].notna()].sort_values("date")
    event_curve = pd.merge_asof(entries, curve[["date", "account_equity", "drawdown_pct"]], on="date", direction="backward")

    fig, ax1 = plt.subplots(figsize=(13, 6))
    ax1.plot(curve["date"], curve["account_equity"] / 1_000_000, color="#0f766e", linewidth=2.0, label="Official equity")
    ax1.scatter(
        event_curve["date"],
        event_curve["account_equity"] / 1_000_000,
        s=20,
        marker="x",
        color="#b91c1c",
        alpha=0.75,
        label="Entry: no remaining local route promotion",
    )
    ax1.set_title("Official path after remaining route audit: no local route can promote")
    ax1.set_ylabel("Equity (million CNY)")
    ax1.grid(True, alpha=0.25)

    ax2 = ax1.twinx()
    ax2.fill_between(curve["date"], curve["drawdown_pct"], 0, color="#f59e0b", alpha=0.16, label="Drawdown")
    ax2.set_ylabel("Drawdown %")
    ax2.set_ylim(min(-55, float(curve["drawdown_pct"].min()) - 3), 5)

    text = (
        f"routes={len(route_ledger)} | rule-ready={int(route_ledger['strategy_rule_allowed'].sum())} | "
        f"true-engine-ready={int(route_ledger['true_engine_allowed'].sum())}"
    )
    ax1.text(0.02, 0.04, text, transform=ax1.transAxes, fontsize=10, bbox={"facecolor": "white", "alpha": 0.78, "edgecolor": "#d1d5db"})
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=9)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_route_matrix(route_ledger: pd.DataFrame) -> None:
    columns = [
        "context_ready",
        "rule_ready",
        "right_tail_pass",
        "source_contract_or_execution_ready",
        "true_engine_allowed",
        "ab_allowed",
    ]
    frame = route_ledger.copy()
    frame["context_ready"] = (frame["context_ready_pct"] >= 0.8).astype(int)
    frame["rule_ready"] = frame["strategy_rule_allowed"].astype(int)
    frame["right_tail_pass"] = 0
    frame["source_contract_or_execution_ready"] = np.where(
        frame["route_id"].isin(["contract_month_oi_migration", "cftc_cot_cross_market_context", "account_dd30_floor_true_engine"]),
        1,
        frame["rule_ready"],
    )
    matrix = frame.set_index("route_id")[columns].astype(float)
    fig, ax = plt.subplots(figsize=(12, 6))
    image = ax.imshow(matrix.values, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(columns)))
    ax.set_xticklabels(["Context", "Rule", "Tail", "Source/exe", "True engine", "A/B"], rotation=30, ha="right")
    ax.set_yticks(range(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    for y in range(matrix.shape[0]):
        for x in range(matrix.shape[1]):
            ax.text(x, y, "1" if matrix.iloc[y, x] >= 0.5 else "0", ha="center", va="center", fontsize=8)
    ax.set_title("Route readiness matrix: context exists, promotion gates fail")
    fig.colorbar(image, ax=ax, shrink=0.82)
    fig.tight_layout()
    fig.savefig(ROUTE_MATRIX_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_coverage_gap(route_ledger: pd.DataFrame) -> None:
    frame = route_ledger.copy().sort_values("context_ready_pct")
    y = np.arange(len(frame))
    fig, ax = plt.subplots(figsize=(11.5, 6))
    ax.barh(y - 0.18, frame["context_ready_pct"].fillna(0), height=0.34, color="#2563eb", alpha=0.78, label="Context/cache ready pct")
    ax.barh(y + 0.18, frame["rule_ready_pct"].fillna(0), height=0.34, color="#dc2626", alpha=0.82, label="Rule/source-contract ready pct")
    ax.set_yticks(y)
    ax.set_yticklabels(frame["route_id"])
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("Coverage")
    ax.set_title("Coverage is not rule readiness")
    for idx, (_, row) in enumerate(frame.iterrows()):
        label = f"{int(row['ready_count'])}/{int(row['denominator_count'])} -> rule {int(row['rule_ready_count'])}/{int(row['denominator_count'])}"
        ax.text(1.01, idx, label, va="center", fontsize=8)
    ax.legend(loc="lower right")
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(COVERAGE_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_objective_gap(objective_gap: pd.DataFrame) -> None:
    frame = objective_gap.copy().iloc[::-1]
    colors = np.where(frame["proven"].eq(1), "#16a34a", "#dc2626")
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.barh(frame["requirement"], frame["proven"], color=colors, alpha=0.85)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("Proven")
    ax.set_title("Objective gap after Stage259")
    for y, (_, row) in enumerate(frame.iterrows()):
        ax.text(0.03, y, "PROVEN" if row["proven"] else "MISSING", va="center", fontsize=8)
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OBJECTIVE_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_next_action(next_action: pd.DataFrame) -> None:
    frame = next_action.copy().sort_values("rank", ascending=False)
    colors = np.where(frame["can_start_without_external_state"].eq(1), "#f59e0b", "#64748b")
    fig, ax = plt.subplots(figsize=(11, 5.6))
    ax.barh(frame["next_action_id"], frame["expected_goal_alignment"], color=colors, alpha=0.86)
    ax.set_xlim(0, 3.3)
    ax.set_xlabel("Goal alignment score")
    ax.set_title("Next action queue: data first, no local rule now")
    for y, (_, row) in enumerate(frame.iterrows()):
        label = "external/blocking" if not row["can_start_without_external_state"] else "can audit, not alpha"
        ax.text(0.08, y, label, va="center", fontsize=8, color="#111827")
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(NEXT_ACTION_CHART_OUT, dpi=180)
    plt.close(fig)


def _write_report(summary: dict[str, Any], route_ledger: pd.DataFrame, objective_gap: pd.DataFrame, next_action: pd.DataFrame) -> None:
    external_rows = int(route_ledger["needs_external_data"].sum())
    report = f"""# Stage259 remaining route exhaustion audit

Decision: `{summary['decision']}`

This is a read-only route closure audit. It creates no trading rule, runs no true engine, triggers no A/B, changes no official config, connects no CTP/SimNow, and calls no order API.

## Main result

- Routes reviewed: `{summary['route_count']}`
- Strategy-rule-ready routes: `{summary['strategy_rule_allowed_route_count']}`
- True-engine-ready routes: `{summary['true_engine_allowed_route_count']}`
- A/B-ready routes: `{summary['ab_allowed_route_count']}`
- Routes requiring external data/source contracts: `{external_rows}`
- Objective requirements proven: `{summary['objective_proven_requirement_count']}/{summary['objective_requirement_count']}`
- Gate: `{summary['gate_pass_count']}/{summary['gate_total_count']}`

## Interpretation

The local minute coverage problem is solved, but the local minute-rule problem is not. Stage249 blocks delayed confirmation because early runway carries material PnL and right-tail. Stage252-254 show price/volume/OI combinations are watch-only and split-unstable. Stage255 shows orderflow and same-source execution replay are still `0/219`. Stage257 and Stage258 show member role and physical-market source contracts are incomplete.

The practical conclusion is that continuing to mine local OHLCV/OI thresholds would be overfitting. The next meaningful progress is either authorized orderflow / broker-production execution replay / licensed physical or member-role data, or a deployment governance study that explicitly does not change production holdings.

## Files

- `{SUMMARY_OUT}`
- `{ROUTE_LEDGER_OUT}`
- `{OBJECTIVE_GAP_OUT}`
- `{NEXT_ACTION_OUT}`
- `{GATE_OUT}`
- `{PATH_CHART_OUT}`
- `{ROUTE_MATRIX_CHART_OUT}`
- `{COVERAGE_CHART_OUT}`
- `{OBJECTIVE_CHART_OUT}`
- `{NEXT_ACTION_CHART_OUT}`

## Top next actions

{next_action[['rank', 'next_action_id', 'can_start_without_external_state', 'reason']].to_markdown(index=False)}
"""
    _write_text(REPORT_OUT, report)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    inputs = _load_inputs()
    route_ledger = _build_route_ledger(inputs)
    objective_gap = _build_objective_gap(route_ledger, inputs)
    next_action = _build_next_action_queue(route_ledger)
    gate = _build_gate(route_ledger, objective_gap)
    summary = _build_summary(route_ledger, objective_gap, gate, inputs)

    _write_csv(route_ledger, ROUTE_LEDGER_OUT)
    _write_csv(objective_gap, OBJECTIVE_GAP_OUT)
    _write_csv(next_action, NEXT_ACTION_OUT)
    _write_csv(gate, GATE_OUT)
    _write_csv(pd.DataFrame([summary]), SUMMARY_OUT)
    _write_json(DECISION_OUT, summary)
    _write_report(summary, route_ledger, objective_gap, next_action)

    _plot_official_path(inputs, route_ledger)
    _plot_route_matrix(route_ledger)
    _plot_coverage_gap(route_ledger)
    _plot_objective_gap(objective_gap)
    _plot_next_action(next_action)

    print(json.dumps(_json_safe(summary), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
