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
STAGE = "Stage263"
MODEL_TAG = "stage263_external_data_arrival_supergate_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage263_c9_minrisk_external_data_arrival_supergate_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage263_external_data_arrival_supergate_audit"

STAGE112_DIR = LINE_DIR / "outputs" / "stage112_authorized_microstructure_data_drop_validator"
STAGE113_DIR = LINE_DIR / "outputs" / "stage113_microstructure_required_window_coverage"
STAGE114_DIR = LINE_DIR / "outputs" / "stage114_microstructure_procurement_request_bundle"
STAGE117_DIR = LINE_DIR / "outputs" / "stage117_wave0_delivery_verifier"
STAGE120_DIR = LINE_DIR / "outputs" / "stage120_wave0_schema_contract_audit"
STAGE135_DIR = LINE_DIR / "outputs" / "stage135_wave0_real_drop_operator_pack"
STAGE141_DIR = LINE_DIR / "outputs" / "stage141_candidate_promotion_gate_contract"
STAGE251_DIR = LINE_DIR / "outputs" / "stage251_dd30_account_floor_true_engine"
STAGE260_DIR = LINE_DIR / "outputs" / "stage260_execution_replay_source_inventory_audit"
STAGE261_REPLAY_DIR = LINE_DIR / "outputs" / "stage261_execution_replay_import_acceptance_packet"

STAGE112_PREFIX = "qmt_roll_stage112_c9_minrisk_authorized_microstructure_data_drop_validator"
STAGE113_PREFIX = "qmt_roll_stage113_c9_minrisk_microstructure_required_window_coverage"
STAGE114_PREFIX = "qmt_roll_stage114_c9_minrisk_microstructure_procurement_request_bundle"
STAGE117_PREFIX = "qmt_roll_stage117_c9_minrisk_wave0_delivery_verifier"
STAGE120_PREFIX = "qmt_roll_stage120_c9_minrisk_wave0_schema_contract_audit"
STAGE135_PREFIX = "qmt_roll_stage135_c9_minrisk_wave0_real_drop_operator_pack"
STAGE141_PREFIX = "qmt_roll_stage141_c9_minrisk_candidate_promotion_gate_contract"
STAGE251_PREFIX = "qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine"
STAGE260_PREFIX = "qmt_roll_stage260_c9_minrisk_execution_replay_source_inventory_audit"
STAGE261_REPLAY_PREFIX = "qmt_roll_stage261_c9_minrisk_execution_replay_import_acceptance_packet"

STAGE112_TAG = "stage112_authorized_microstructure_data_drop_validator_v1"
STAGE113_TAG = "stage113_microstructure_required_window_coverage_v1"
STAGE114_TAG = "stage114_microstructure_procurement_request_bundle_v1"
STAGE117_TAG = "stage117_wave0_delivery_verifier_v1"
STAGE120_TAG = "stage120_wave0_schema_contract_audit_v1"
STAGE135_TAG = "stage135_wave0_real_drop_operator_pack_v1"
STAGE141_TAG = "stage141_candidate_promotion_gate_contract_v1"
STAGE251_TAG = "stage251_dd30_account_floor_true_engine_v1"
STAGE260_TAG = "stage260_execution_replay_source_inventory_audit_v1"
STAGE261_REPLAY_TAG = "stage261_execution_replay_import_acceptance_packet_v1"

STAGE112_SUMMARY_IN = STAGE112_DIR / f"{STAGE112_PREFIX}_summary_{STAGE112_TAG}.csv"
STAGE112_GATE_IN = STAGE112_DIR / f"{STAGE112_PREFIX}_acceptance_gate_{STAGE112_TAG}.csv"
STAGE113_SUMMARY_IN = STAGE113_DIR / f"{STAGE113_PREFIX}_summary_{STAGE113_TAG}.csv"
STAGE113_GATE_IN = STAGE113_DIR / f"{STAGE113_PREFIX}_coverage_gate_{STAGE113_TAG}.csv"
STAGE114_SUMMARY_IN = STAGE114_DIR / f"{STAGE114_PREFIX}_summary_{STAGE114_TAG}.csv"
STAGE114_GATE_IN = STAGE114_DIR / f"{STAGE114_PREFIX}_procurement_gate_{STAGE114_TAG}.csv"
STAGE117_SUMMARY_IN = STAGE117_DIR / f"{STAGE117_PREFIX}_summary_{STAGE117_TAG}.csv"
STAGE117_GATE_IN = STAGE117_DIR / f"{STAGE117_PREFIX}_w0_delivery_gate_status_{STAGE117_TAG}.csv"
STAGE120_SUMMARY_IN = STAGE120_DIR / f"{STAGE120_PREFIX}_summary_{STAGE120_TAG}.csv"
STAGE120_GATE_IN = STAGE120_DIR / f"{STAGE120_PREFIX}_schema_contract_gate_status_{STAGE120_TAG}.csv"
STAGE135_SUMMARY_IN = STAGE135_DIR / f"{STAGE135_PREFIX}_summary_{STAGE135_TAG}.csv"
STAGE135_GATE_IN = STAGE135_DIR / f"{STAGE135_PREFIX}_operator_pack_gate_status_{STAGE135_TAG}.csv"
STAGE141_SUMMARY_IN = STAGE141_DIR / f"{STAGE141_PREFIX}_summary_{STAGE141_TAG}.csv"
STAGE141_GATE_IN = STAGE141_DIR / f"{STAGE141_PREFIX}_gate_status_{STAGE141_TAG}.csv"
STAGE251_CURVE_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_curve_{STAGE251_TAG}.csv"
STAGE251_SUMMARY_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_summary_{STAGE251_TAG}.csv"
STAGE260_SUMMARY_IN = STAGE260_DIR / f"{STAGE260_PREFIX}_summary_{STAGE260_TAG}.csv"
STAGE260_GATE_IN = STAGE260_DIR / f"{STAGE260_PREFIX}_promotion_gate_{STAGE260_TAG}.csv"
STAGE260_FIELD_IN = STAGE260_DIR / f"{STAGE260_PREFIX}_execution_replay_field_contract_{STAGE260_TAG}.csv"
STAGE261_REPLAY_SUMMARY_IN = STAGE261_REPLAY_DIR / f"{STAGE261_REPLAY_PREFIX}_summary_{STAGE261_REPLAY_TAG}.csv"
STAGE261_REPLAY_GATE_IN = STAGE261_REPLAY_DIR / f"{STAGE261_REPLAY_PREFIX}_acceptance_gate_{STAGE261_REPLAY_TAG}.csv"
STAGE261_REPLAY_SCHEMA_IN = STAGE261_REPLAY_DIR / f"{STAGE261_REPLAY_PREFIX}_required_schema_contract_{STAGE261_REPLAY_TAG}.csv"
STAGE261_REPLAY_SELFTEST_IN = STAGE261_REPLAY_DIR / f"{STAGE261_REPLAY_PREFIX}_fixture_selftest_results_{STAGE261_REPLAY_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
ROUTE_SUPERGATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_supergate_{MODEL_TAG}.csv"
ARTIFACT_READINESS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_artifact_readiness_{MODEL_TAG}.csv"
ARRIVAL_DECISION_TREE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_arrival_decision_tree_{MODEL_TAG}.csv"
MISSING_EVIDENCE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_missing_evidence_ledger_{MODEL_TAG}.csv"
SUPERGATE_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_supergate_status_{MODEL_TAG}.csv"
NEXT_ACTION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_action_queue_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_supergate_status_{MODEL_TAG}.png"
ROUTE_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_supergate_heatmap_{MODEL_TAG}.png"
ARTIFACT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_artifact_readiness_matrix_{MODEL_TAG}.png"
DECISION_TREE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_arrival_decision_tree_chart_{MODEL_TAG}.png"
MISSING_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_missing_evidence_chart_{MODEL_TAG}.png"

FULL_ENTRY_DECISION_COUNT = 219
RIGHT_TAIL_WINDOW_COUNT = 36
BOTTOM_LOSS_WINDOW_COUNT = 37


def _read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 4:
        if required:
            raise RuntimeError(f"missing required input: {path}")
        return pd.DataFrame()
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


def _get(row: dict[str, Any], *keys: str, default: Any = 0) -> Any:
    for key in keys:
        if key in row and not pd.isna(row[key]):
            return row[key]
    return default


def _gate_pass_count(frame: pd.DataFrame) -> int:
    if frame.empty or "pass_now" not in frame.columns:
        return 0
    return int(pd.to_numeric(frame["pass_now"], errors="coerce").fillna(0).sum())


def _gate_count(frame: pd.DataFrame) -> int:
    return int(len(frame)) if not frame.empty else 0


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
        "stage112_summary": _row(_read_csv(STAGE112_SUMMARY_IN)),
        "stage112_gate": _read_csv(STAGE112_GATE_IN),
        "stage113_summary": _row(_read_csv(STAGE113_SUMMARY_IN)),
        "stage113_gate": _read_csv(STAGE113_GATE_IN),
        "stage114_summary": _row(_read_csv(STAGE114_SUMMARY_IN)),
        "stage114_gate": _read_csv(STAGE114_GATE_IN),
        "stage117_summary": _row(_read_csv(STAGE117_SUMMARY_IN)),
        "stage117_gate": _read_csv(STAGE117_GATE_IN),
        "stage120_summary": _row(_read_csv(STAGE120_SUMMARY_IN)),
        "stage120_gate": _read_csv(STAGE120_GATE_IN),
        "stage135_summary": _row(_read_csv(STAGE135_SUMMARY_IN)),
        "stage135_gate": _read_csv(STAGE135_GATE_IN),
        "stage141_summary": _row(_read_csv(STAGE141_SUMMARY_IN)),
        "stage141_gate": _read_csv(STAGE141_GATE_IN),
        "stage251_curve": _read_csv(STAGE251_CURVE_IN),
        "stage251_summary": _read_csv(STAGE251_SUMMARY_IN),
        "stage260_summary": _row(_read_csv(STAGE260_SUMMARY_IN)),
        "stage260_gate": _read_csv(STAGE260_GATE_IN),
        "stage260_field": _read_csv(STAGE260_FIELD_IN),
        "stage261_replay_summary": _row(_read_csv(STAGE261_REPLAY_SUMMARY_IN)),
        "stage261_replay_gate": _read_csv(STAGE261_REPLAY_GATE_IN),
        "stage261_replay_schema": _read_csv(STAGE261_REPLAY_SCHEMA_IN),
        "stage261_replay_selftest": _read_csv(STAGE261_REPLAY_SELFTEST_IN),
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


def _route_supergate(inputs: dict[str, Any]) -> pd.DataFrame:
    s112 = inputs["stage112_summary"]
    s113 = inputs["stage113_summary"]
    s114 = inputs["stage114_summary"]
    s117 = inputs["stage117_summary"]
    s120 = inputs["stage120_summary"]
    s135 = inputs["stage135_summary"]
    s260 = inputs["stage260_summary"]
    s261 = inputs["stage261_replay_summary"]

    orderflow_expected_windows = _to_int(_get(s113, "required_window_count"))
    orderflow_covered_windows = _to_int(_get(s113, "covered_window_count"))
    w0_request_count = _to_int(_get(s117, "w0_request_count", "request_count"))
    w0_accepted_count = _to_int(_get(s117, "w0_hard_accept_request_count"))
    orderflow_packet_ready = int(
        _to_int(_get(s135, "operator_pack_ready")) == 1
        and _to_int(_get(s120, "planning_gate_pass_count")) == _to_int(_get(s120, "planning_gate_count"))
        and _to_int(_get(s114, "procurement_batch_count")) > 0
    )

    replay_expected_entries = _to_int(_get(s261, "full_orderflow_expected_order_count"), FULL_ENTRY_DECISION_COUNT)
    replay_ready_entries = _to_int(_get(s261, "full_orderflow_ready_order_count"))
    replay_packet_ready = int(
        _to_int(_get(s261, "acceptance_gate_pass_count")) >= 3
        and _to_int(_get(s261, "fixture_selftest_pass_count")) == _to_int(_get(s261, "fixture_selftest_case_count"))
    )

    rows = [
        {
            "route_id": "authorized_orderflow_mbp10_mbo_w0_chain",
            "route_name": "authorized MBO/MBP10 orderflow/depth W0 chain",
            "external_source_kind": "MBO L3 or MBP-10 L2 depth with raw hash/license",
            "contract_packet_ready": orderflow_packet_ready,
            "real_external_package_supplied": _to_int(_get(s135, "real_w0_data_delivered")),
            "accepted_external_package_count": w0_accepted_count,
            "primary_expected_unit": "required_window",
            "primary_expected_count": orderflow_expected_windows,
            "primary_ready_count": orderflow_covered_windows,
            "primary_missing_count": max(orderflow_expected_windows - orderflow_covered_windows, 0),
            "secondary_expected_unit": "W0_request",
            "secondary_expected_count": w0_request_count,
            "secondary_ready_count": w0_accepted_count,
            "secondary_missing_count": max(w0_request_count - w0_accepted_count, 0),
            "schema_or_field_contract_count": _to_int(_get(s120, "contract_field_count")),
            "schema_or_field_contract_pass_count": _to_int(_get(s120, "real_w0_schema_structural_pass_count", "real_w0_schema_contract_pass")),
            "tail_required_count": _to_int(_get(s113, "right_tail_window_count")) + _to_int(_get(s113, "bottom_loss_window_count")),
            "tail_ready_count": 0,
            "stage_intake_ready_count": _to_int(_get(s112, "rule_ready_data_file_count")),
            "strategy_rule_allowed_now": 0,
            "true_engine_allowed_now": 0,
            "ab_allowed_now": 0,
            "next_gate_sequence": "Stage135 real drop -> Stage117 delivery -> Stage120 schema -> Stage112 intake -> Stage113 coverage -> Stage141 promotion",
            "route_decision": "wait_real_authorized_orderflow_drop",
        },
        {
            "route_id": "broker_production_execution_replay_chain",
            "route_name": "broker/production same-source execution replay chain",
            "external_source_kind": "broker/vn.py/CTP/FIX order lifecycle and fills with same-source top-book context",
            "contract_packet_ready": replay_packet_ready,
            "real_external_package_supplied": _to_int(_get(s261, "real_replay_package_supplied")),
            "accepted_external_package_count": _to_int(_get(s261, "accepted_real_replay_package_count")),
            "primary_expected_unit": "entry_decision",
            "primary_expected_count": replay_expected_entries,
            "primary_ready_count": replay_ready_entries,
            "primary_missing_count": max(replay_expected_entries - replay_ready_entries, 0),
            "secondary_expected_unit": "accepted_same_source_replay_file",
            "secondary_expected_count": 1,
            "secondary_ready_count": _to_int(_get(s260, "accepted_same_source_replay_file_count")),
            "secondary_missing_count": max(1 - _to_int(_get(s260, "accepted_same_source_replay_file_count")), 0),
            "schema_or_field_contract_count": _to_int(_get(s261, "field_contract_count")),
            "schema_or_field_contract_pass_count": _to_int(_get(s261, "field_contract_pass_count")),
            "tail_required_count": 36,
            "tail_ready_count": 0,
            "stage_intake_ready_count": _to_int(_get(s261, "accepted_real_replay_package_count")),
            "strategy_rule_allowed_now": 0,
            "true_engine_allowed_now": 0,
            "ab_allowed_now": 0,
            "next_gate_sequence": "Stage261 import packet -> Stage260 field/source audit -> tail atlas -> Stage141 promotion",
            "route_decision": "wait_real_broker_or_production_replay_drop",
        },
    ]
    frame = pd.DataFrame(rows)
    frame["primary_coverage_pct"] = np.where(
        frame["primary_expected_count"].astype(float) > 0,
        frame["primary_ready_count"].astype(float) / frame["primary_expected_count"].astype(float) * 100.0,
        np.nan,
    )
    frame["route_promotion_ready"] = (
        (frame["contract_packet_ready"] == 1)
        & (frame["real_external_package_supplied"] == 1)
        & (frame["primary_missing_count"] == 0)
        & (frame["schema_or_field_contract_pass_count"] >= frame["schema_or_field_contract_count"])
        & (frame["tail_ready_count"] >= frame["tail_required_count"])
        & (frame["strategy_rule_allowed_now"] == 1)
    ).astype(int)
    return frame


def _artifact_readiness(inputs: dict[str, Any]) -> pd.DataFrame:
    stage_rows = [
        ("Stage112", "authorized data drop validator", inputs["stage112_summary"], inputs["stage112_gate"], "rule_ready_data_file_count", "accepted MBO/MBP10 files"),
        ("Stage113", "required window coverage", inputs["stage113_summary"], inputs["stage113_gate"], "covered_window_count", "covered required windows"),
        ("Stage114", "procurement request bundle", inputs["stage114_summary"], inputs["stage114_gate"], "authorized_data_downloaded", "downloaded authorized files"),
        ("Stage117", "W0 delivery verifier", inputs["stage117_summary"], inputs["stage117_gate"], "w0_hard_accept_request_count", "hard-accepted W0 requests"),
        ("Stage120", "W0 schema contract audit", inputs["stage120_summary"], inputs["stage120_gate"], "real_w0_schema_structural_pass_count", "real schema-pass W0 rows"),
        ("Stage135", "real drop operator pack", inputs["stage135_summary"], inputs["stage135_gate"], "real_w0_data_delivered", "real W0 data delivered"),
        ("Stage141", "candidate promotion contract", inputs["stage141_summary"], inputs["stage141_gate"], "current_candidate_promotion_allowed", "candidate promotion allowed"),
        ("Stage260", "execution replay source inventory", inputs["stage260_summary"], inputs["stage260_gate"], "accepted_same_source_replay_file_count", "accepted replay files"),
        ("Stage261R", "execution replay import packet", inputs["stage261_replay_summary"], inputs["stage261_replay_gate"], "accepted_real_replay_package_count", "accepted replay packages"),
    ]
    rows = []
    for stage, role, summary, gate, data_key, data_unit in stage_rows:
        planning_ready = 1
        if stage == "Stage112":
            planning_ready = int(_gate_count(gate) > 0)
        elif stage == "Stage135":
            planning_ready = _to_int(_get(summary, "operator_pack_ready"))
        elif stage == "Stage141":
            planning_ready = _to_int(_get(summary, "contract_ready"))
        elif stage == "Stage261R":
            planning_ready = int(_to_int(_get(summary, "fixture_selftest_pass_count")) == _to_int(_get(summary, "fixture_selftest_case_count")))
        data_ready = int(_to_int(_get(summary, data_key)) > 0)
        pass_count = _gate_pass_count(gate)
        total_count = _gate_count(gate)
        rows.append(
            {
                "stage": stage,
                "role": role,
                "planning_or_packet_ready": planning_ready,
                "real_data_ready": data_ready,
                "gate_pass_count": pass_count,
                "gate_count": total_count,
                "gate_pass_ratio": pass_count / total_count if total_count else np.nan,
                "data_ready_unit": data_unit,
                "data_ready_count": _to_int(_get(summary, data_key)),
                "decision": str(_get(summary, "decision", default="")),
            }
        )
    return pd.DataFrame(rows)


def _arrival_decision_tree() -> pd.DataFrame:
    rows = [
        {
            "arrival_kind": "authorized_mbp10_or_mbo_drop",
            "first_action": "Place package under Stage135 real drop candidate directory and run Stage117.",
            "required_evidence": "manifest + raw/parquet/proof + source_license + raw_sha256/schema_hash + MBO/MBP10 fields",
            "next_gate_chain": "Stage117 -> Stage120 -> Stage112 -> Stage113 -> Stage141",
            "accepted_outcome": "may start read-only feature attribution only after full windows and promotion contract pass",
            "reject_if": "synthetic/smoke/read-only/mixed-vendor/no-license/partial-tail-coverage",
            "rule_allowed_now": 0,
        },
        {
            "arrival_kind": "broker_or_production_execution_replay_drop",
            "first_action": "Validate with Stage261 execution replay import packet.",
            "required_evidence": "manifest + order_events + trade_events + account_snapshots + tick_or_book_events + raw hashes/license",
            "next_gate_chain": "Stage261 import -> Stage260 source/field audit -> tail atlas -> Stage141",
            "accepted_outcome": "may analyze same-source slippage/fill/lifecycle context only after 219 entry coverage",
            "reject_if": "broken signal-order-trade join/no source license/smoke/adapter/read-only/low coverage",
            "rule_allowed_now": 0,
        },
        {
            "arrival_kind": "partial_authorized_or_replay_drop",
            "first_action": "Quarantine and run only intake diagnostics.",
            "required_evidence": "explicit missing file list, no synthetic filling, immutable partial manifest",
            "next_gate_chain": "same route as source kind after completion",
            "accepted_outcome": "can update missing ledger, cannot create signal or run true engine",
            "reject_if": "operator tries to use partial coverage as an alpha sample",
            "rule_allowed_now": 0,
        },
        {
            "arrival_kind": "smoke_readonly_adapter_pending_order",
            "first_action": "Reject as research evidence.",
            "required_evidence": "none; these files can only test plumbing",
            "next_gate_chain": "no promotion chain",
            "accepted_outcome": "record as negative evidence or operational smoke only",
            "reject_if": "always rejected for strategy research",
            "rule_allowed_now": 0,
        },
        {
            "arrival_kind": "minute_ohlcv_oi_or_local_backtest_trade_ledger",
            "first_action": "Reject for microstructure/execution replay route.",
            "required_evidence": "minute layer is already closed and cannot substitute event/order lifecycle data",
            "next_gate_chain": "no orderflow/replay promotion chain",
            "accepted_outcome": "may remain context only; no new threshold sweep",
            "reject_if": "always rejected as substitute for MBO/MBP10 or execution reports",
            "rule_allowed_now": 0,
        },
    ]
    return pd.DataFrame(rows)


def _missing_evidence_ledger(inputs: dict[str, Any]) -> pd.DataFrame:
    s113 = inputs["stage113_summary"]
    s117 = inputs["stage117_summary"]
    s120 = inputs["stage120_summary"]
    s260 = inputs["stage260_summary"]
    s261 = inputs["stage261_replay_summary"]
    rows = [
        ("authorized_orderflow", "W0 request raw/parquet/proof triplets", _to_int(_get(s117, "w0_request_count")), _to_int(_get(s117, "w0_hard_accept_request_count")), "external_data_absent"),
        ("authorized_orderflow", "all required microstructure windows", _to_int(_get(s113, "required_window_count")), _to_int(_get(s113, "covered_window_count")), "coverage_absent"),
        ("authorized_orderflow", "all 219 entry candidates covered", _to_int(_get(s113, "required_candidate_count")), _to_int(_get(s113, "covered_candidate_count")), "candidate_coverage_absent"),
        ("authorized_orderflow", "right-tail windows covered", _to_int(_get(s113, "right_tail_window_count")), 0, "tail_coverage_absent"),
        ("authorized_orderflow", "bottom-loss windows covered", _to_int(_get(s113, "bottom_loss_window_count")), 0, "tail_coverage_absent"),
        ("authorized_orderflow", "maxDD context windows covered", _to_int(_get(s113, "maxdd_context_window_count")), 0, "stress_coverage_absent"),
        ("authorized_orderflow", "real W0 schema contract pass", _to_int(_get(s117, "w0_request_count")), _to_int(_get(s120, "real_w0_schema_structural_pass_count", "real_w0_schema_contract_pass")), "schema_contract_absent"),
        ("execution_replay", "real replay package supplied", 1, _to_int(_get(s261, "real_replay_package_supplied")), "external_package_absent"),
        ("execution_replay", "accepted real replay package", 1, _to_int(_get(s261, "accepted_real_replay_package_count")), "accepted_package_absent"),
        ("execution_replay", "219 entry same-source coverage", _to_int(_get(s261, "full_orderflow_expected_order_count"), FULL_ENTRY_DECISION_COUNT), _to_int(_get(s261, "full_orderflow_ready_order_count")), "entry_coverage_absent"),
        ("execution_replay", "accepted same-source replay file", 1, _to_int(_get(s260, "accepted_same_source_replay_file_count")), "same_source_file_absent"),
        ("execution_replay", "field contract pass", _to_int(_get(s261, "field_contract_count")), _to_int(_get(s261, "field_contract_pass_count")), "field_contract_absent"),
        ("execution_replay", "right-tail and bottom-loss replay atlas", 36, 0, "tail_visual_coverage_absent"),
        ("execution_replay", "raw hash and source license", 2, 0, "permission_provenance_absent"),
    ]
    frame = pd.DataFrame(rows, columns=["route_id", "evidence_item", "expected_count", "ready_count", "blocker"])
    frame["missing_count"] = (frame["expected_count"] - frame["ready_count"]).clip(lower=0)
    frame["ready_pct"] = np.where(
        frame["expected_count"].astype(float) > 0,
        frame["ready_count"].astype(float) / frame["expected_count"].astype(float) * 100.0,
        np.nan,
    )
    frame["severity"] = np.where(frame["missing_count"] > 0, "hard_blocker", "pass")
    return frame


def _supergate_status(route_supergate: pd.DataFrame, inputs: dict[str, Any]) -> pd.DataFrame:
    s261 = inputs["stage261_replay_summary"]
    rows = [
        ("no_official_config_or_order_side_effect", 1, 1, "Stage263 is read-only and does not call CTP/SimNow/order API."),
        ("two_external_route_contract_packets_ready", 2, int(route_supergate["contract_packet_ready"].sum()), "Both W0/orderflow and execution-replay acceptance packets exist."),
        ("fixture_and_synthetic_guards_ready", 1, int(_to_int(_get(s261, "fixture_selftest_pass_count")) == _to_int(_get(s261, "fixture_selftest_case_count"))), "Stage261 rejects synthetic/smoke/low-coverage cases."),
        ("real_external_route_supplied", 2, int(route_supergate["real_external_package_supplied"].sum()), "No real authorized W0 or broker replay package is present."),
        ("accepted_external_route_ready", 2, int((route_supergate["accepted_external_package_count"] > 0).sum()), "No external package has passed route acceptance."),
        ("primary_coverage_complete", 2, int((route_supergate["primary_missing_count"] == 0).sum()), "Orderflow windows and replay entry coverage are both incomplete."),
        ("schema_or_field_contract_complete", 2, int((route_supergate["schema_or_field_contract_pass_count"] >= route_supergate["schema_or_field_contract_count"]).sum()), "Real schema/field contract evidence is absent."),
        ("tail_and_bottom_loss_coverage_complete", 2, int((route_supergate["tail_ready_count"] >= route_supergate["tail_required_count"]).sum()), "No real right-tail/bottom-loss replay/orderflow coverage."),
        ("strategy_rule_or_true_engine_allowed", 2, int(route_supergate["strategy_rule_allowed_now"].sum()), "No route may create a rule, run true engine, or trigger A/B."),
    ]
    frame = pd.DataFrame(rows, columns=["gate_id", "required", "observed", "reason"])
    frame["pass_now"] = (frame["observed"] >= frame["required"]).astype(int)
    return frame[["gate_id", "required", "observed", "pass_now", "reason"]]


def _next_action_queue(route_supergate: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "priority": 1,
            "action_id": "wait_or_drop_broker_production_execution_replay",
            "route_id": "broker_production_execution_replay_chain",
            "action": "Use the Stage261 import packet when a real broker/production replay bundle arrives.",
            "done_when": "real package supplied=1, accepted package>=1, entry coverage=219/219, field contract=18/18",
            "allowed_now": 1,
            "strategy_rule_allowed": 0,
        },
        {
            "priority": 2,
            "action_id": "wait_or_drop_authorized_mbo_mbp10_w0",
            "route_id": "authorized_orderflow_mbp10_mbo_w0_chain",
            "action": "Use Stage135/117/120/112/113 when an authorized MBO or MBP-10 W0 package arrives.",
            "done_when": "W0 requests=41/41, required windows=485/485, schema/license/hash/tail gates pass",
            "allowed_now": 1,
            "strategy_rule_allowed": 0,
        },
        {
            "priority": 3,
            "action_id": "reject_local_substitutes",
            "route_id": "all",
            "action": "Keep rejecting minute OHLCV, smoke, read-only, adapter, pending-order and generic backtest ledgers as substitutes.",
            "done_when": "No substitute file is promoted without source license, raw hash, same-source join and full coverage.",
            "allowed_now": 1,
            "strategy_rule_allowed": 0,
        },
        {
            "priority": 4,
            "action_id": "do_not_sweep_closed_local_features",
            "route_id": "all",
            "action": "Do not resume OHLCV/OI threshold, product, direction, year or tail-window sweeps.",
            "done_when": "Only external data arrival or read-only data-contract work continues.",
            "allowed_now": 1,
            "strategy_rule_allowed": 0,
        },
    ]
    return pd.DataFrame(rows)


def _summary(inputs: dict[str, Any], route_supergate: pd.DataFrame, supergate_status: pd.DataFrame) -> pd.DataFrame:
    official = _official_summary(inputs["stage251_summary"])
    s113 = inputs["stage113_summary"]
    s117 = inputs["stage117_summary"]
    s260 = inputs["stage260_summary"]
    s261 = inputs["stage261_replay_summary"]
    row = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": "stage263_external_data_arrival_supergate_ready_wait_real_data_no_rule",
        "stage_nature": "read_only_external_data_arrival_supergate_audit",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_or_simnow_connected": 0,
        "external_data_route_count": int(len(route_supergate)),
        "contract_packet_ready_route_count": int(route_supergate["contract_packet_ready"].sum()),
        "real_data_supplied_route_count": int((route_supergate["real_external_package_supplied"] > 0).sum()),
        "accepted_route_count": int((route_supergate["accepted_external_package_count"] > 0).sum()),
        "strategy_rule_allowed_route_count": int(route_supergate["strategy_rule_allowed_now"].sum()),
        "true_engine_allowed_route_count": int(route_supergate["true_engine_allowed_now"].sum()),
        "authorized_orderflow_required_window_count": _to_int(_get(s113, "required_window_count")),
        "authorized_orderflow_covered_window_count": _to_int(_get(s113, "covered_window_count")),
        "authorized_orderflow_missing_window_count": max(_to_int(_get(s113, "required_window_count")) - _to_int(_get(s113, "covered_window_count")), 0),
        "authorized_w0_request_count": _to_int(_get(s117, "w0_request_count")),
        "authorized_w0_hard_accept_request_count": _to_int(_get(s117, "w0_hard_accept_request_count")),
        "execution_replay_expected_entry_count": _to_int(_get(s261, "full_orderflow_expected_order_count"), FULL_ENTRY_DECISION_COUNT),
        "execution_replay_ready_entry_count": _to_int(_get(s261, "full_orderflow_ready_order_count")),
        "execution_replay_missing_entry_count": _to_int(_get(s261, "full_orderflow_missing_order_count")),
        "execution_replay_required_schema_field_count": _to_int(_get(s261, "required_schema_field_count")),
        "execution_replay_fixture_selftest_pass_count": _to_int(_get(s261, "fixture_selftest_pass_count")),
        "execution_replay_fixture_selftest_case_count": _to_int(_get(s261, "fixture_selftest_case_count")),
        "stage260_accepted_same_source_replay_file_count": _to_int(_get(s260, "accepted_same_source_replay_file_count")),
        "supergate_count": int(len(supergate_status)),
        "supergate_pass_count": int(supergate_status["pass_now"].sum()),
        "strategy_feature_usable": 0,
        "objective_completion_proven": 0,
        "official_end_equity": _to_float(_get(official, "end_equity")),
        "official_total_return_pct": _to_float(_get(official, "total_return_pct")),
        "official_max_dd_pct": _to_float(_get(official, "max_dd_pct", "max_drawdown_pct")),
        "official_sharpe": _to_float(_get(official, "sharpe")),
        "official_total_slippage": _to_float(_get(official, "total_slippage")),
        "official_total_trade_count": _to_float(_get(official, "total_trade_count")),
        "official_win_rate_pct": _to_float(_get(official, "nonzero_daily_win_rate_pct", "closed_lot_win_rate_pct")),
        "official_broker10_peak_pct": _to_float(_get(official, "max_broker10_margin_to_equity_pct")),
        "visual_file_count": 5,
    }
    return pd.DataFrame([row])


def _plot_official_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    row = _row(summary)
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax1.plot(curve["date"], curve["account_equity"], color="#2f6f73", linewidth=1.8, label="official equity")
    ax1.set_ylabel("Equity")
    ax1.grid(True, alpha=0.25)
    ax2 = ax1.twinx()
    ax2.fill_between(curve["date"], curve["drawdown_pct"], 0, color="#b5533c", alpha=0.25, label="drawdown")
    ax2.set_ylabel("Drawdown %")
    title = (
        "Stage263 external data supergate | "
        f"orderflow windows {row['authorized_orderflow_covered_window_count']}/{row['authorized_orderflow_required_window_count']} | "
        f"replay entries {row['execution_replay_ready_entry_count']}/{row['execution_replay_expected_entry_count']}"
    )
    ax1.set_title(title)
    ax1.text(
        0.015,
        0.95,
        "No strategy rule / no true engine / wait real external package",
        transform=ax1.transAxes,
        va="top",
        bbox={"facecolor": "white", "edgecolor": "#777777", "alpha": 0.9},
    )
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_route_heatmap(route_supergate: pd.DataFrame) -> None:
    columns = [
        "contract_packet_ready",
        "real_external_package_supplied",
        "accepted_external_package_count",
        "primary_coverage_complete",
        "schema_or_field_complete",
        "tail_coverage_complete",
        "strategy_rule_allowed_now",
    ]
    data = pd.DataFrame(
        {
            "contract_packet_ready": route_supergate["contract_packet_ready"],
            "real_external_package_supplied": (route_supergate["real_external_package_supplied"] > 0).astype(int),
            "accepted_external_package_count": (route_supergate["accepted_external_package_count"] > 0).astype(int),
            "primary_coverage_complete": (route_supergate["primary_missing_count"] == 0).astype(int),
            "schema_or_field_complete": (route_supergate["schema_or_field_contract_pass_count"] >= route_supergate["schema_or_field_contract_count"]).astype(int),
            "tail_coverage_complete": (route_supergate["tail_ready_count"] >= route_supergate["tail_required_count"]).astype(int),
            "strategy_rule_allowed_now": route_supergate["strategy_rule_allowed_now"],
        }
    )
    fig, ax = plt.subplots(figsize=(11, 3.8))
    ax.imshow(data.to_numpy(dtype=float), cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(columns)))
    ax.set_xticklabels(columns, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(len(route_supergate)))
    ax.set_yticklabels(route_supergate["route_id"], fontsize=8)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            ax.text(j, i, str(int(data.iloc[i, j])), ha="center", va="center", fontsize=9)
    ax.set_title("Route supergate heatmap")
    fig.tight_layout()
    fig.savefig(ROUTE_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_artifact_matrix(artifact: pd.DataFrame) -> None:
    columns = ["planning_or_packet_ready", "real_data_ready", "gate_pass_ratio"]
    data = artifact[columns].copy()
    data["gate_pass_ratio"] = data["gate_pass_ratio"].fillna(0.0)
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.imshow(data.to_numpy(dtype=float), cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(columns)))
    ax.set_xticklabels(columns, rotation=25, ha="right", fontsize=8)
    ax.set_yticks(range(len(artifact)))
    ax.set_yticklabels(artifact["stage"] + " " + artifact["role"], fontsize=7)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            value = data.iloc[i, j]
            label = f"{value:.2f}" if columns[j] == "gate_pass_ratio" else str(int(value))
            ax.text(j, i, label, ha="center", va="center", fontsize=8)
    ax.set_title("Artifact ready, real data not ready")
    fig.tight_layout()
    fig.savefig(ARTIFACT_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_decision_tree(decision_tree: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 6.8))
    ax.axis("off")
    y_positions = np.linspace(0.85, 0.15, len(decision_tree))
    colors = ["#e7f0ef", "#e7f0ef", "#f6eadf", "#f2dddd", "#f2dddd"]
    for idx, (_, row) in enumerate(decision_tree.iterrows()):
        y = y_positions[idx]
        ax.add_patch(plt.Rectangle((0.02, y - 0.055), 0.26, 0.11, facecolor=colors[idx], edgecolor="#666666"))
        ax.add_patch(plt.Rectangle((0.35, y - 0.055), 0.28, 0.11, facecolor="white", edgecolor="#777777"))
        ax.add_patch(plt.Rectangle((0.70, y - 0.055), 0.27, 0.11, facecolor="white", edgecolor="#777777"))
        ax.text(0.15, y, str(row["arrival_kind"]), ha="center", va="center", fontsize=8, weight="bold", wrap=True)
        ax.text(0.49, y, str(row["first_action"]), ha="center", va="center", fontsize=7, wrap=True)
        ax.text(0.835, y, str(row["next_gate_chain"]), ha="center", va="center", fontsize=7, wrap=True)
        ax.annotate("", xy=(0.35, y), xytext=(0.28, y), arrowprops={"arrowstyle": "->", "color": "#555555"})
        ax.annotate("", xy=(0.70, y), xytext=(0.63, y), arrowprops={"arrowstyle": "->", "color": "#555555"})
    ax.text(0.15, 0.96, "arrival kind", ha="center", va="center", fontsize=9, weight="bold")
    ax.text(0.49, 0.96, "first action", ha="center", va="center", fontsize=9, weight="bold")
    ax.text(0.835, 0.96, "gate chain", ha="center", va="center", fontsize=9, weight="bold")
    ax.set_title("Stage263 arrival decision tree")
    fig.tight_layout()
    fig.savefig(DECISION_TREE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_missing_evidence(missing: pd.DataFrame) -> None:
    plot_df = missing.copy()
    plot_df["label"] = plot_df["route_id"] + " | " + plot_df["evidence_item"]
    plot_df = plot_df.sort_values(["route_id", "expected_count"], ascending=[True, False])
    fig, ax = plt.subplots(figsize=(11, 7.2))
    y = np.arange(len(plot_df))
    ax.barh(y, plot_df["expected_count"], color="#e5e5e5", label="expected")
    ax.barh(y, plot_df["ready_count"], color="#2f6f73", label="ready")
    ax.set_yticks(y)
    ax.set_yticklabels(plot_df["label"], fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("Count")
    ax.set_title("Missing external evidence ledger")
    ax.grid(axis="x", alpha=0.25)
    ax.legend(loc="lower right")
    for i, row in enumerate(plot_df.itertuples(index=False)):
        ax.text(row.expected_count + max(plot_df["expected_count"]) * 0.01, i, f"missing {int(row.missing_count)}", va="center", fontsize=7)
    fig.tight_layout()
    fig.savefig(MISSING_CHART_OUT, dpi=160)
    plt.close(fig)


def _report(
    summary: pd.DataFrame,
    route_supergate: pd.DataFrame,
    artifact: pd.DataFrame,
    decision_tree: pd.DataFrame,
    missing: pd.DataFrame,
    supergate: pd.DataFrame,
    next_action: pd.DataFrame,
) -> str:
    row = _row(summary)
    return f"""# Stage263 external data arrival supergate audit

## Decision

`{row['decision']}`

This stage is read-only. It creates no strategy rule, runs no true engine, triggers no A/B, changes no official config, and does not connect CTP/SimNow or call an order API.

## External research judgment

Databento MBO is L3 order-book event data keyed by order id, while MBP-10 is L2 top-ten market-by-price depth. Databento common-field guidance makes `ts_recv` / `ts_event` timestamp semantics central to event ordering. FIX ExecutionReport is an order lifecycle and fill report, not a backtest ledger. Therefore minute OHLCV/OI files, smoke files, read-only snapshots, adapter tests, pending-order lists and generic backtest trades cannot substitute for either route.

Sources:
- https://databento.com/docs/schemas-and-data-formats/mbo
- https://databento.com/docs/schemas-and-data-formats/mbp-10
- https://databento.com/docs/standards-and-conventions/common-fields-enums-types
- https://www.onixs.biz/fix-dictionary/4.4/msgtype_8_8.html

## Summary

- Official A unchanged: equity `{row['official_end_equity']:.2f}`, return `{row['official_total_return_pct']:.4f}%`, maxDD `{row['official_max_dd_pct']:.4f}%`, Sharpe `{row['official_sharpe']:.4f}`, slippage `{row['official_total_slippage']:.0f}`, trades `{row['official_total_trade_count']:.0f}`, win rate `{row['official_win_rate_pct']:.4f}%`.
- Route contracts ready: `{row['contract_packet_ready_route_count']}/{row['external_data_route_count']}`.
- Real external route supplied: `{row['real_data_supplied_route_count']}/{row['external_data_route_count']}`.
- Accepted route: `{row['accepted_route_count']}/{row['external_data_route_count']}`.
- Authorized orderflow coverage: `{row['authorized_orderflow_covered_window_count']}/{row['authorized_orderflow_required_window_count']}` windows, W0 hard accept `{row['authorized_w0_hard_accept_request_count']}/{row['authorized_w0_request_count']}` requests.
- Execution replay coverage: `{row['execution_replay_ready_entry_count']}/{row['execution_replay_expected_entry_count']}` entries, missing `{row['execution_replay_missing_entry_count']}`.
- Supergate pass: `{row['supergate_pass_count']}/{row['supergate_count']}`.

## Route supergate

{_md_table(route_supergate[['route_id', 'contract_packet_ready', 'real_external_package_supplied', 'accepted_external_package_count', 'primary_ready_count', 'primary_expected_count', 'primary_missing_count', 'schema_or_field_contract_pass_count', 'schema_or_field_contract_count', 'tail_ready_count', 'tail_required_count', 'route_decision']])}

## Artifact readiness

{_md_table(artifact[['stage', 'planning_or_packet_ready', 'real_data_ready', 'gate_pass_count', 'gate_count', 'data_ready_count', 'data_ready_unit']], max_rows=20)}

## Arrival decision tree

{_md_table(decision_tree[['arrival_kind', 'first_action', 'next_gate_chain', 'rule_allowed_now']], max_rows=20)}

## Missing evidence

{_md_table(missing[['route_id', 'evidence_item', 'expected_count', 'ready_count', 'missing_count', 'blocker']], max_rows=30)}

## Supergate status

{_md_table(supergate, max_rows=20)}

## Next action

{_md_table(next_action, max_rows=20)}
"""


def main() -> None:
    inputs = _load_inputs()
    curve = _official_curve(inputs["stage251_curve"])
    route_supergate = _route_supergate(inputs)
    artifact = _artifact_readiness(inputs)
    decision_tree = _arrival_decision_tree()
    missing = _missing_evidence_ledger(inputs)
    supergate = _supergate_status(route_supergate, inputs)
    next_action = _next_action_queue(route_supergate)
    summary = _summary(inputs, route_supergate, supergate)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_csv(summary, SUMMARY_OUT)
    _write_csv(route_supergate, ROUTE_SUPERGATE_OUT)
    _write_csv(artifact, ARTIFACT_READINESS_OUT)
    _write_csv(decision_tree, ARRIVAL_DECISION_TREE_OUT)
    _write_csv(missing, MISSING_EVIDENCE_OUT)
    _write_csv(supergate, SUPERGATE_STATUS_OUT)
    _write_csv(next_action, NEXT_ACTION_OUT)

    _plot_official_path(curve, summary)
    _plot_route_heatmap(route_supergate)
    _plot_artifact_matrix(artifact)
    _plot_decision_tree(decision_tree)
    _plot_missing_evidence(missing)

    report_text = _report(summary, route_supergate, artifact, decision_tree, missing, supergate, next_action)
    _write_text(REPORT_OUT, report_text)
    _write_json(
        DECISION_OUT,
        {
            "summary": _row(summary),
            "route_supergate": route_supergate.to_dict(orient="records"),
            "supergate_status": supergate.to_dict(orient="records"),
            "outputs": {
                "summary": SUMMARY_OUT,
                "route_supergate": ROUTE_SUPERGATE_OUT,
                "artifact_readiness": ARTIFACT_READINESS_OUT,
                "arrival_decision_tree": ARRIVAL_DECISION_TREE_OUT,
                "missing_evidence": MISSING_EVIDENCE_OUT,
                "supergate_status": SUPERGATE_STATUS_OUT,
                "next_action": NEXT_ACTION_OUT,
                "report": REPORT_OUT,
                "charts": [
                    PATH_CHART_OUT,
                    ROUTE_HEATMAP_OUT,
                    ARTIFACT_CHART_OUT,
                    DECISION_TREE_CHART_OUT,
                    MISSING_CHART_OUT,
                ],
            },
        },
    )

    print(json.dumps(_row(summary), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
