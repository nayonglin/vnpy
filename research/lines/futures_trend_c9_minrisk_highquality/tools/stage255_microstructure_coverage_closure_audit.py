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
STAGE = "Stage255"
MODEL_TAG = "stage255_microstructure_coverage_closure_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage255_c9_minrisk_microstructure_coverage_closure_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage255_microstructure_coverage_closure_audit"

STAGE111_DIR = LINE_DIR / "outputs" / "stage111_execution_replay_intake_acceptance"
STAGE112_DIR = LINE_DIR / "outputs" / "stage112_authorized_microstructure_data_drop_validator"
STAGE117_DIR = LINE_DIR / "outputs" / "stage117_wave0_delivery_verifier"
STAGE136_DIR = LINE_DIR / "outputs" / "stage136_wave0_watch_inbox_arrival_monitor"
STAGE140_DIR = LINE_DIR / "outputs" / "stage140_wave0_unattended_watch_preinstall_status_panel"
STAGE141_DIR = LINE_DIR / "outputs" / "stage141_candidate_promotion_gate_contract"
STAGE179_DIR = LINE_DIR / "outputs" / "stage179_predecision_lookback_point_in_time_validator"
STAGE180_DIR = LINE_DIR / "outputs" / "stage180_cutoff_filtered_predecision_feature_source"
STAGE181_DIR = LINE_DIR / "outputs" / "stage181_cutoff_filtered_minute_feature_materializer"
STAGE238_DIR = LINE_DIR / "outputs" / "stage238_formal_feature_gate"
STAGE239_DIR = LINE_DIR / "outputs" / "stage239_read_only_universal_signal_quality_audit"
STAGE251_DIR = LINE_DIR / "outputs" / "stage251_dd30_account_floor_true_engine"

STAGE111_PREFIX = "qmt_roll_stage111_c9_minrisk_execution_replay_intake_acceptance"
STAGE112_PREFIX = "qmt_roll_stage112_c9_minrisk_authorized_microstructure_data_drop_validator"
STAGE117_PREFIX = "qmt_roll_stage117_c9_minrisk_wave0_delivery_verifier"
STAGE136_PREFIX = "qmt_roll_stage136_c9_minrisk_wave0_watch_inbox_arrival_monitor"
STAGE140_PREFIX = "qmt_roll_stage140_c9_minrisk_wave0_unattended_watch_preinstall_status_panel"
STAGE141_PREFIX = "qmt_roll_stage141_c9_minrisk_candidate_promotion_gate_contract"
STAGE179_PREFIX = "qmt_roll_stage179_c9_minrisk_predecision_lookback_point_in_time_validator"
STAGE180_PREFIX = "qmt_roll_stage180_c9_minrisk_cutoff_filtered_predecision_feature_source"
STAGE181_PREFIX = "qmt_roll_stage181_c9_minrisk_cutoff_filtered_minute_feature_materializer"
STAGE238_PREFIX = "qmt_roll_stage238_c9_minrisk_formal_feature_gate"
STAGE239_PREFIX = "qmt_roll_stage239_c9_minrisk_read_only_universal_signal_quality_audit"
STAGE251_PREFIX = "qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine"

STAGE111_TAG = "stage111_execution_replay_intake_acceptance_v1"
STAGE112_TAG = "stage112_authorized_microstructure_data_drop_validator_v1"
STAGE117_TAG = "stage117_wave0_delivery_verifier_v1"
STAGE136_TAG = "stage136_wave0_watch_inbox_arrival_monitor_v1"
STAGE140_TAG = "stage140_wave0_unattended_watch_preinstall_status_panel_v1"
STAGE141_TAG = "stage141_candidate_promotion_gate_contract_v1"
STAGE179_TAG = "stage179_predecision_lookback_point_in_time_validator_v1"
STAGE180_TAG = "stage180_cutoff_filtered_predecision_feature_source_v1"
STAGE181_TAG = "stage181_cutoff_filtered_minute_feature_materializer_v1"
STAGE238_TAG = "stage238_formal_feature_gate_v1"
STAGE239_TAG = "stage239_read_only_universal_signal_quality_audit_v1"
STAGE251_TAG = "stage251_dd30_account_floor_true_engine_v1"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COVERAGE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_ledger_{MODEL_TAG}.csv"
ROUTE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_status_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
SCHEMA_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_filtered_source_schema_probe_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_coverage_status_{MODEL_TAG}.png"
COVERAGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_ledger_chart_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"
SCHEMA_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_schema_probe_chart_{MODEL_TAG}.png"
ROUTE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_status_chart_{MODEL_TAG}.png"

FULL_ENTRY_DECISION_COUNT = 219
W0_EXPECTED_REQUEST_COUNT = 41
W0_EXPECTED_WINDOW_COUNT = 70

ORDERFLOW_REQUIRED_COLUMNS = {
    "authorized_mbo_l3": [
        "vt_symbol",
        "exchange",
        "trading_day",
        "ts_event",
        "action",
        "side",
        "price",
        "size",
        "order_id",
        "sequence",
    ],
    "authorized_mbp10_l2": [
        "vt_symbol",
        "exchange",
        "trading_day",
        "ts_event",
        "action",
        "side",
        "price",
        "size",
        "bid_price1",
        "ask_price1",
        "bid_size1",
        "ask_size1",
    ],
    "same_source_execution_replay": [
        "vt_symbol",
        "exchange",
        "decision_ts",
        "order_ts",
        "fill_ts",
        "order_price",
        "fill_price",
        "filled_volume",
        "side",
        "source_license",
    ],
}


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


def _row(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {}
    return frame.iloc[0].to_dict()


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


def _load_inputs() -> dict[str, Any]:
    return {
        "stage111_summary": _row(
            _read_csv(STAGE111_DIR / f"{STAGE111_PREFIX}_summary_{STAGE111_TAG}.csv")
        ),
        "stage112_summary": _row(
            _read_csv(STAGE112_DIR / f"{STAGE112_PREFIX}_summary_{STAGE112_TAG}.csv")
        ),
        "stage117_summary": _row(
            _read_csv(STAGE117_DIR / f"{STAGE117_PREFIX}_summary_{STAGE117_TAG}.csv")
        ),
        "stage136_summary": _row(
            _read_csv(STAGE136_DIR / f"{STAGE136_PREFIX}_summary_{STAGE136_TAG}.csv")
        ),
        "stage140_summary": _row(
            _read_csv(STAGE140_DIR / f"{STAGE140_PREFIX}_summary_{STAGE140_TAG}.csv")
        ),
        "stage141_summary": _row(
            _read_csv(STAGE141_DIR / f"{STAGE141_PREFIX}_summary_{STAGE141_TAG}.csv")
        ),
        "stage179_summary": _row(
            _read_csv(STAGE179_DIR / f"{STAGE179_PREFIX}_summary_{STAGE179_TAG}.csv")
        ),
        "stage180_summary": _row(
            _read_csv(STAGE180_DIR / f"{STAGE180_PREFIX}_summary_{STAGE180_TAG}.csv")
        ),
        "stage181_summary": _row(
            _read_csv(STAGE181_DIR / f"{STAGE181_PREFIX}_summary_{STAGE181_TAG}.csv")
        ),
        "stage238_summary": _row(
            _read_csv(STAGE238_DIR / f"{STAGE238_PREFIX}_summary_{STAGE238_TAG}.csv")
        ),
        "stage239_summary": _row(
            _read_csv(STAGE239_DIR / f"{STAGE239_PREFIX}_summary_{STAGE239_TAG}.csv")
        ),
        "stage251_summary_frame": _read_csv(STAGE251_DIR / f"{STAGE251_PREFIX}_summary_{STAGE251_TAG}.csv"),
        "stage251_curve": _read_csv(STAGE251_DIR / f"{STAGE251_PREFIX}_curve_{STAGE251_TAG}.csv"),
        "stage180_manifest": _read_csv(
            STAGE180_DIR / f"{STAGE180_PREFIX}_filtered_source_manifest_{STAGE180_TAG}.csv"
        ),
        "stage238_feature_gate": _read_csv(
            STAGE238_DIR / f"{STAGE238_PREFIX}_feature_gate_audit_{STAGE238_TAG}.csv"
        ),
    }


def _build_schema_probe(manifest: pd.DataFrame) -> pd.DataFrame:
    sample_columns: set[str] = set()
    sample_file = ""
    for rel_path in manifest["filtered_source_file"].dropna().astype(str).head(8):
        path = REPO_DIR / rel_path
        if not path.exists():
            continue
        sample_file = str(path)
        try:
            sample = pd.read_parquet(path)
        except Exception:
            continue
        sample_columns.update(str(col) for col in sample.columns)
        break

    records: list[dict[str, Any]] = []
    for schema_name, columns in ORDERFLOW_REQUIRED_COLUMNS.items():
        for column in columns:
            records.append(
                {
                    "schema_name": schema_name,
                    "required_column": column,
                    "present_in_stage180_filtered_source": int(column in sample_columns),
                    "sample_filtered_source_file": sample_file,
                }
            )
    probe = pd.DataFrame(records)
    if not probe.empty:
        required_counts = probe.groupby("schema_name")["required_column"].transform("count")
        present_counts = probe.groupby("schema_name")["present_in_stage180_filtered_source"].transform("sum")
        probe["schema_present_count"] = present_counts
        probe["schema_required_count"] = required_counts
        probe["schema_ready"] = (present_counts == required_counts).astype(int)
    return probe


def _build_coverage_ledger(inputs: dict[str, Any], schema_probe: pd.DataFrame) -> pd.DataFrame:
    s111 = inputs["stage111_summary"]
    s112 = inputs["stage112_summary"]
    s117 = inputs["stage117_summary"]
    s136 = inputs["stage136_summary"]
    s140 = inputs["stage140_summary"]
    s179 = inputs["stage179_summary"]
    s180 = inputs["stage180_summary"]
    s181 = inputs["stage181_summary"]
    s238 = inputs["stage238_summary"]
    s239 = inputs["stage239_summary"]

    minute_ready = _to_int(s181.get("feature_audit_row_written_count"))
    formal_ready = _to_int(s238.get("formal_row_ready_count"))
    label_ready = _to_int(s239.get("joined_row_count"))
    w0_request_ready = _to_int(s117.get("w0_hard_accept_request_count"))
    w0_window_ready = _to_int(s117.get("w0_hard_accept_window_count"))
    w0_candidate_ready = _to_int(s136.get("candidate_ready_count"))
    real_w0_delivered = max(
        _to_int(s136.get("real_w0_data_delivered")),
        _to_int(s140.get("real_w0_data_delivered")),
        _to_int(s117.get("stage112_intake_allowed_now")),
    )
    schema_ready = int(schema_probe.groupby("schema_name")["schema_ready"].max().fillna(0).max()) if not schema_probe.empty else 0
    execution_ready = _to_int(s111.get("stage932_valid_research_sample_count"))

    rows = [
        {
            "coverage_item": "stage179_point_in_time_request_triplets",
            "layer": "minute_cutoff_feature_source",
            "expected_count": FULL_ENTRY_DECISION_COUNT,
            "ready_count": _to_int(s179.get("filtered_request_ready_count")),
            "coverage_type": "point_in_time_filtered_minute_source",
            "can_be_filled_locally_now": 0,
            "orderflow_capable": 0,
            "status": "complete_for_minute_features",
            "interpretation": "All entry decisions have cutoff-filtered minute source, but direct file use remains blocked.",
        },
        {
            "coverage_item": "stage180_cutoff_filtered_sources",
            "layer": "minute_cutoff_feature_source",
            "expected_count": FULL_ENTRY_DECISION_COUNT,
            "ready_count": _to_int(s180.get("cutoff_filtered_source_ready_count")),
            "coverage_type": "cutoff_filtered_minute_bar_source",
            "can_be_filled_locally_now": 0,
            "orderflow_capable": 0,
            "status": "complete_for_minute_features",
            "interpretation": "Cutoff-filtered sources are complete and future bars were removed.",
        },
        {
            "coverage_item": "stage181_feature_ready_rows",
            "layer": "minute_feature_materialized",
            "expected_count": FULL_ENTRY_DECISION_COUNT,
            "ready_count": minute_ready,
            "coverage_type": "minute_ohlcv_oi_feature_audit",
            "can_be_filled_locally_now": 0,
            "orderflow_capable": 0,
            "status": "complete_for_minute_features",
            "interpretation": "The local supplement is complete for 10 minute-level audit features.",
        },
        {
            "coverage_item": "stage238_formal_feature_rows",
            "layer": "formal_minute_feature_table",
            "expected_count": FULL_ENTRY_DECISION_COUNT,
            "ready_count": formal_ready,
            "coverage_type": "formal_minute_feature_table",
            "can_be_filled_locally_now": 0,
            "orderflow_capable": 0,
            "status": "complete_but_strategy_locked",
            "interpretation": "Formal rows are complete, but Stage239-247 and Stage252-254 did not promote a rule.",
        },
        {
            "coverage_item": "stage239_label_join_rows",
            "layer": "read_only_signal_quality_audit",
            "expected_count": FULL_ENTRY_DECISION_COUNT,
            "ready_count": label_ready,
            "coverage_type": "minute_feature_label_join",
            "can_be_filled_locally_now": 0,
            "orderflow_capable": 0,
            "status": "complete_for_audit",
            "interpretation": "All minute feature rows can be joined to labels for read-only analysis.",
        },
        {
            "coverage_item": "stage117_w0_hard_accept_requests",
            "layer": "authorized_microstructure_drop",
            "expected_count": W0_EXPECTED_REQUEST_COUNT,
            "ready_count": w0_request_ready,
            "coverage_type": "real_mbo_or_mbp10_drop_request",
            "can_be_filled_locally_now": 0,
            "orderflow_capable": 1,
            "status": "missing_external_drop",
            "interpretation": "The W0 smoke package has no hard-accepted real request.",
        },
        {
            "coverage_item": "stage117_w0_hard_accept_windows",
            "layer": "authorized_microstructure_drop",
            "expected_count": W0_EXPECTED_WINDOW_COUNT,
            "ready_count": w0_window_ready,
            "coverage_type": "real_mbo_or_mbp10_drop_window",
            "can_be_filled_locally_now": 0,
            "orderflow_capable": 1,
            "status": "missing_external_drop",
            "interpretation": "The W0 smoke package has no hard-accepted real window.",
        },
        {
            "coverage_item": "stage136_watch_candidate_ready",
            "layer": "authorized_microstructure_drop",
            "expected_count": max(1, _to_int(s136.get("candidate_dir_count"))),
            "ready_count": w0_candidate_ready,
            "coverage_type": "real_w0_inbox_candidate",
            "can_be_filled_locally_now": 0,
            "orderflow_capable": 1,
            "status": "watch_waiting",
            "interpretation": "Watch infrastructure is ready, but no candidate directory contains a real drop.",
        },
        {
            "coverage_item": "full_entry_decision_real_orderflow",
            "layer": "true_orderflow_research_input",
            "expected_count": FULL_ENTRY_DECISION_COUNT,
            "ready_count": 0 if real_w0_delivered == 0 or schema_ready == 0 else FULL_ENTRY_DECISION_COUNT,
            "coverage_type": "mbo_mbp10_or_execution_replay_for_all_entries",
            "can_be_filled_locally_now": 0,
            "orderflow_capable": 1,
            "status": "missing_external_data",
            "interpretation": "No authorized MBO/MBP10 or same-source replay exists for the 219 entry decisions.",
        },
        {
            "coverage_item": "stage111_same_source_execution_replay",
            "layer": "execution_replay",
            "expected_count": FULL_ENTRY_DECISION_COUNT,
            "ready_count": min(execution_ready, FULL_ENTRY_DECISION_COUNT),
            "coverage_type": "broker_or_production_execution_replay",
            "can_be_filled_locally_now": 0,
            "orderflow_capable": 1,
            "status": "missing_external_replay",
            "interpretation": "Smoke snapshots are not valid research samples; no same-source execution replay is ready.",
        },
        {
            "coverage_item": "stage112_rule_ready_data_files",
            "layer": "authorized_microstructure_drop",
            "expected_count": max(W0_EXPECTED_REQUEST_COUNT, _to_int(s112.get("data_file_count"))),
            "ready_count": _to_int(s112.get("rule_ready_data_file_count")),
            "coverage_type": "stage112_schema_and_coverage_acceptance",
            "can_be_filled_locally_now": 0,
            "orderflow_capable": 1,
            "status": "missing_external_drop",
            "interpretation": "Stage112 accepts no rule-ready MBO/MBP10 files.",
        },
    ]
    ledger = pd.DataFrame(rows)
    ledger["missing_count"] = (ledger["expected_count"] - ledger["ready_count"]).clip(lower=0)
    ledger["coverage_pct"] = ledger.apply(lambda r: _safe_div(r["ready_count"], r["expected_count"]), axis=1)
    ledger["complete"] = (ledger["missing_count"].eq(0) & ledger["expected_count"].gt(0)).astype(int)
    return ledger


def _build_route_status(inputs: dict[str, Any], ledger: pd.DataFrame) -> pd.DataFrame:
    s238 = inputs["stage238_summary"]
    s239 = inputs["stage239_summary"]
    s141 = inputs["stage141_summary"]
    stage238_features = inputs["stage238_feature_gate"]
    candidate_allowed = int(pd.to_numeric(stage238_features["strategy_candidate_allowed_now"], errors="coerce").fillna(0).sum())
    diagnostic_only = int(pd.to_numeric(stage238_features["diagnostic_only"], errors="coerce").fillna(0).sum())

    minute_complete = int(ledger.loc[ledger["coverage_item"].eq("stage181_feature_ready_rows"), "complete"].max())
    orderflow_ready = int(ledger.loc[ledger["coverage_item"].eq("full_entry_decision_real_orderflow"), "complete"].max())
    execution_ready = int(ledger.loc[ledger["coverage_item"].eq("stage111_same_source_execution_replay"), "complete"].max())

    routes = [
        {
            "route_id": "cutoff_minute_feature_coverage",
            "evidence": f"{_to_int(s238.get('formal_row_ready_count'))}/219 formal rows, {candidate_allowed} candidate features, {diagnostic_only} diagnostic features",
            "coverage_ready": minute_complete,
            "true_engine_allowed": 0,
            "route_state": "completed_but_exhausted",
            "next_action": "do not keep filling minute coverage; it is already complete",
        },
        {
            "route_id": "single_and_small_combo_minute_feature_rules",
            "evidence": f"Stage239 watch-only={_to_int(s239.get('universal_structure_watch_only_count'))}; Stage240-247 and Stage252-254 blocked promotion",
            "coverage_ready": minute_complete,
            "true_engine_allowed": 0,
            "route_state": "closed_no_rule",
            "next_action": "no threshold, split, product, direction, or year rescue",
        },
        {
            "route_id": "authorized_mbo_mbp10_orderflow",
            "evidence": "Stage112/117/136/140 report zero real W0 delivered and zero hard-accepted MBO/MBP10 files",
            "coverage_ready": orderflow_ready,
            "true_engine_allowed": 0,
            "route_state": "blocked_external_data_missing",
            "next_action": "wait for or procure authorized MBO/MBP10 depth package",
        },
        {
            "route_id": "broker_or_production_execution_replay",
            "evidence": "Stage111 has no valid research replay sample; smoke snapshots are insufficient",
            "coverage_ready": execution_ready,
            "true_engine_allowed": 0,
            "route_state": "blocked_external_data_missing",
            "next_action": "import same-source order/fill/replay logs with provenance",
        },
        {
            "route_id": "promotion_contract",
            "evidence": f"Stage141 current_candidate_promotion_allowed={_to_int(s141.get('current_candidate_promotion_allowed'))}",
            "coverage_ready": 0,
            "true_engine_allowed": 0,
            "route_state": "ready_as_gate_no_candidate",
            "next_action": "only use after an ex-ante candidate passes data and robustness gates",
        },
    ]
    route = pd.DataFrame(routes)
    route["readiness_score"] = route["coverage_ready"] + route["true_engine_allowed"]
    return route


def _build_gate_status(inputs: dict[str, Any], ledger: pd.DataFrame, schema_probe: pd.DataFrame) -> pd.DataFrame:
    s140 = inputs["stage140_summary"]
    s141 = inputs["stage141_summary"]
    s239 = inputs["stage239_summary"]

    minute_missing = int(ledger.loc[ledger["coverage_item"].eq("stage181_feature_ready_rows"), "missing_count"].max())
    formal_missing = int(ledger.loc[ledger["coverage_item"].eq("stage238_formal_feature_rows"), "missing_count"].max())
    full_of_missing = int(ledger.loc[ledger["coverage_item"].eq("full_entry_decision_real_orderflow"), "missing_count"].max())
    replay_missing = int(ledger.loc[ledger["coverage_item"].eq("stage111_same_source_execution_replay"), "missing_count"].max())
    w0_window_missing = int(ledger.loc[ledger["coverage_item"].eq("stage117_w0_hard_accept_windows"), "missing_count"].max())
    any_orderflow_schema_ready = int(schema_probe.groupby("schema_name")["schema_ready"].max().fillna(0).max()) if not schema_probe.empty else 0

    gates = [
        {
            "gate_id": "minute_feature_coverage_complete",
            "category": "coverage_closure",
            "evidence_value": 1 if minute_missing == 0 else 0,
            "pass_now": int(minute_missing == 0),
            "block_reason": "" if minute_missing == 0 else "minute_feature_rows_missing",
        },
        {
            "gate_id": "formal_feature_table_complete",
            "category": "coverage_closure",
            "evidence_value": 1 if formal_missing == 0 else 0,
            "pass_now": int(formal_missing == 0),
            "block_reason": "" if formal_missing == 0 else "formal_rows_missing",
        },
        {
            "gate_id": "single_feature_route_not_promoted",
            "category": "anti_overfit",
            "evidence_value": _to_int(s239.get("strategy_feature_usable")),
            "pass_now": int(_to_int(s239.get("strategy_feature_usable")) == 0),
            "block_reason": "",
        },
        {
            "gate_id": "w0_hard_accept_windows_present",
            "category": "orderflow_data",
            "evidence_value": W0_EXPECTED_WINDOW_COUNT - w0_window_missing,
            "pass_now": int(w0_window_missing == 0),
            "block_reason": "" if w0_window_missing == 0 else "w0_real_windows_missing",
        },
        {
            "gate_id": "mbo_or_mbp10_schema_present",
            "category": "orderflow_data",
            "evidence_value": any_orderflow_schema_ready,
            "pass_now": any_orderflow_schema_ready,
            "block_reason": "" if any_orderflow_schema_ready else "stage180_minute_bars_lack_orderbook_event_columns",
        },
        {
            "gate_id": "full_219_real_orderflow_coverage",
            "category": "orderflow_data",
            "evidence_value": FULL_ENTRY_DECISION_COUNT - full_of_missing,
            "pass_now": int(full_of_missing == 0),
            "block_reason": "" if full_of_missing == 0 else "all_entry_orderflow_missing",
        },
        {
            "gate_id": "same_source_execution_replay_present",
            "category": "execution_replay",
            "evidence_value": FULL_ENTRY_DECISION_COUNT - replay_missing,
            "pass_now": int(replay_missing == 0),
            "block_reason": "" if replay_missing == 0 else "same_source_replay_missing",
        },
        {
            "gate_id": "promotion_candidate_allowed",
            "category": "promotion",
            "evidence_value": _to_int(s141.get("current_candidate_promotion_allowed")),
            "pass_now": int(_to_int(s141.get("current_candidate_promotion_allowed")) == 1),
            "block_reason": "" if _to_int(s141.get("current_candidate_promotion_allowed")) == 1 else "no_candidate_passes_contract",
        },
        {
            "gate_id": "no_official_or_runtime_side_effect",
            "category": "execution_safety",
            "evidence_value": max(
                _to_int(s140.get("official_config_changed")),
                _to_int(s140.get("strategy_rule_created")),
                _to_int(s140.get("order_api_called")),
                _to_int(s140.get("ctp_connected")),
            ),
            "pass_now": int(
                max(
                    _to_int(s140.get("official_config_changed")),
                    _to_int(s140.get("strategy_rule_created")),
                    _to_int(s140.get("order_api_called")),
                    _to_int(s140.get("ctp_connected")),
                )
                == 0
            ),
            "block_reason": "",
        },
    ]
    gate = pd.DataFrame(gates)
    gate["true_engine_allowed"] = 0
    gate["strategy_feature_usable"] = 0
    return gate


def _build_summary(inputs: dict[str, Any], ledger: pd.DataFrame, route: pd.DataFrame, gate: pd.DataFrame, schema_probe: pd.DataFrame) -> pd.DataFrame:
    s112 = inputs["stage112_summary"]
    s117 = inputs["stage117_summary"]
    s181 = inputs["stage181_summary"]
    s238 = inputs["stage238_summary"]
    s239 = inputs["stage239_summary"]
    official_frame = inputs["stage251_summary_frame"]
    official = official_frame[official_frame["arm"].astype(str).eq("A_official_stage847_c9_15w")]
    official_row = official.iloc[0].to_dict() if not official.empty else {}

    minute_missing = int(ledger.loc[ledger["coverage_item"].eq("stage181_feature_ready_rows"), "missing_count"].max())
    full_of_missing = int(ledger.loc[ledger["coverage_item"].eq("full_entry_decision_real_orderflow"), "missing_count"].max())
    w0_request_missing = int(ledger.loc[ledger["coverage_item"].eq("stage117_w0_hard_accept_requests"), "missing_count"].max())
    w0_window_missing = int(ledger.loc[ledger["coverage_item"].eq("stage117_w0_hard_accept_windows"), "missing_count"].max())
    replay_missing = int(ledger.loc[ledger["coverage_item"].eq("stage111_same_source_execution_replay"), "missing_count"].max())
    gate_pass_count = int(pd.to_numeric(gate["pass_now"], errors="coerce").fillna(0).sum())

    decision = "stage255_minute_coverage_complete_real_orderflow_missing_no_rule"
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": decision,
                "stage_nature": "read_only_microstructure_coverage_closure_audit",
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_or_simnow_connected": 0,
                "minute_feature_expected_order_count": FULL_ENTRY_DECISION_COUNT,
                "minute_feature_ready_order_count": _to_int(s181.get("feature_audit_row_written_count")),
                "minute_feature_missing_order_count": minute_missing,
                "minute_feature_ready_cell_count": _to_int(s181.get("feature_ready_cell_count")),
                "formal_feature_ready_row_count": _to_int(s238.get("formal_row_ready_count")),
                "formal_candidate_feature_count": _to_int(s238.get("strategy_candidate_feature_count")),
                "stage239_candidate_feature_count": _to_int(s239.get("candidate_feature_count")),
                "stage239_watch_only_count": _to_int(s239.get("universal_structure_watch_only_count")),
                "real_w0_expected_request_count": W0_EXPECTED_REQUEST_COUNT,
                "real_w0_ready_request_count": _to_int(s117.get("w0_hard_accept_request_count")),
                "real_w0_missing_request_count": w0_request_missing,
                "real_w0_expected_window_count": W0_EXPECTED_WINDOW_COUNT,
                "real_w0_ready_window_count": _to_int(s117.get("w0_hard_accept_window_count")),
                "real_w0_missing_window_count": w0_window_missing,
                "stage112_rule_ready_data_file_count": _to_int(s112.get("rule_ready_data_file_count")),
                "stage112_accepted_mbo_file_count": _to_int(s112.get("accepted_mbo_file_count")),
                "stage112_accepted_mbp10_file_count": _to_int(s112.get("accepted_mbp10_file_count")),
                "full_orderflow_expected_order_count": FULL_ENTRY_DECISION_COUNT,
                "full_orderflow_ready_order_count": FULL_ENTRY_DECISION_COUNT - full_of_missing,
                "full_orderflow_missing_order_count": full_of_missing,
                "same_source_execution_replay_missing_order_count": replay_missing,
                "orderflow_schema_ready_count": int(schema_probe.groupby("schema_name")["schema_ready"].max().fillna(0).sum()) if not schema_probe.empty else 0,
                "route_count": int(len(route)),
                "route_true_engine_allowed_count": int(pd.to_numeric(route["true_engine_allowed"], errors="coerce").fillna(0).sum()),
                "gate_count": int(len(gate)),
                "gate_pass_count": gate_pass_count,
                "strategy_feature_usable": 0,
                "objective_completion_proven": 0,
                "official_end_equity": _to_float(official_row.get("end_equity"), np.nan),
                "official_total_return_pct": _to_float(official_row.get("total_return_pct"), np.nan),
                "official_max_dd_pct": _to_float(official_row.get("max_dd_pct"), np.nan),
                "official_sharpe": _to_float(official_row.get("sharpe"), np.nan),
                "official_total_slippage": _to_float(official_row.get("total_slippage"), np.nan),
                "official_total_trade_count": _to_float(official_row.get("total_trade_count"), np.nan),
                "official_win_rate_pct": _to_float(official_row.get("nonzero_daily_win_rate_pct"), np.nan),
                "official_broker10_peak_pct": _to_float(official_row.get("max_broker10_margin_to_equity_pct"), np.nan),
                "visual_file_count": 5,
            }
        ]
    )


def _plot_official_path(curve: pd.DataFrame, summary: pd.Series) -> None:
    curve = curve[curve["arm"].astype(str).eq("A_official_stage847_c9_15w")].copy()
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce")
    curve = curve.sort_values("date")
    fig, axes = plt.subplots(3, 1, figsize=(15, 10), gridspec_kw={"height_ratios": [2.1, 1.0, 0.9]}, sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"], color="#0f172a", linewidth=1.25)
    axes[0].set_ylabel("equity")
    axes[0].set_title("Stage255 official path: minute coverage complete, real orderflow still missing")
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#dc2626", linewidth=1.0)
    axes[1].set_ylabel("drawdown %")
    marker_dates = [curve["date"].min(), curve["date"].max()]
    axes[2].bar(marker_dates, [summary["minute_feature_ready_order_count"], summary["full_orderflow_ready_order_count"]], width=80, color=["#16a34a", "#dc2626"])
    axes[2].set_ylabel("ready entries")
    axes[2].set_yticks([0, 109, 219])
    axes[2].set_ylim(0, 230)
    axes[2].text(marker_dates[0], summary["minute_feature_ready_order_count"] + 5, "minute 219/219", ha="center", fontsize=9)
    axes[2].text(marker_dates[1], summary["full_orderflow_ready_order_count"] + 5, "orderflow 0/219", ha="center", fontsize=9)
    for ax in axes:
        ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_coverage(ledger: pd.DataFrame) -> None:
    plot = ledger.copy()
    plot = plot.sort_values(["orderflow_capable", "expected_count", "coverage_item"], ascending=[True, False, True])
    y = np.arange(len(plot))
    fig, ax = plt.subplots(figsize=(14, max(6, 0.44 * len(plot))))
    ax.barh(y, plot["ready_count"], color="#16a34a", label="ready")
    ax.barh(y, plot["missing_count"], left=plot["ready_count"], color="#dc2626", label="missing")
    ax.set_yticks(y)
    ax.set_yticklabels(plot["coverage_item"], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("count")
    ax.set_title("Stage255 coverage ledger: what is complete vs what still requires external data")
    for idx, row in plot.reset_index(drop=True).iterrows():
        ax.text(row["expected_count"] + 2, idx, f"{int(row['ready_count'])}/{int(row['expected_count'])}", va="center", fontsize=8)
    ax.legend()
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(COVERAGE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_gates(gate: pd.DataFrame) -> None:
    matrix = gate.set_index("gate_id")[["pass_now"]].astype(float)
    fig, ax = plt.subplots(figsize=(7.5, max(4.5, 0.42 * len(matrix))))
    ax.imshow(matrix.to_numpy(), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_xticks([0])
    ax.set_xticklabels(["pass"])
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=8)
    for i, value in enumerate(matrix["pass_now"]):
        ax.text(0, i, "PASS" if value else "FAIL", ha="center", va="center", fontsize=8, color="#111827")
    ax.set_title("Stage255 data and promotion gates")
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_schema(schema_probe: pd.DataFrame) -> None:
    grouped = (
        schema_probe.groupby("schema_name", dropna=False)
        .agg(required=("required_column", "count"), present=("present_in_stage180_filtered_source", "sum"))
        .reset_index()
    )
    grouped["missing"] = grouped["required"] - grouped["present"]
    y = np.arange(len(grouped))
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.barh(y, grouped["present"], color="#16a34a", label="present in Stage180 source")
    ax.barh(y, grouped["missing"], left=grouped["present"], color="#dc2626", label="missing")
    ax.set_yticks(y)
    ax.set_yticklabels(grouped["schema_name"])
    ax.invert_yaxis()
    ax.set_xlabel("required columns")
    ax.set_title("Stage255 orderflow schema probe on cutoff-filtered minute sources")
    for idx, row in grouped.iterrows():
        ax.text(row["required"] + 0.3, idx, f"{int(row['present'])}/{int(row['required'])}", va="center", fontsize=9)
    ax.legend()
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(SCHEMA_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_routes(route: pd.DataFrame) -> None:
    colors = {
        "completed_but_exhausted": "#16a34a",
        "closed_no_rule": "#f97316",
        "blocked_external_data_missing": "#dc2626",
        "ready_as_gate_no_candidate": "#64748b",
    }
    fig, ax = plt.subplots(figsize=(13.5, 5.8))
    x = np.arange(len(route))
    ax.bar(x, route["readiness_score"], color=[colors.get(state, "#64748b") for state in route["route_state"]])
    ax.set_xticks(x)
    ax.set_xticklabels(route["route_id"], rotation=25, ha="right", fontsize=8)
    ax.set_ylim(0, 2.2)
    ax.set_ylabel("coverage + true-engine allowance")
    ax.set_title("Stage255 route status")
    for idx, row in route.iterrows():
        ax.text(idx, row["readiness_score"] + 0.05, row["route_state"], rotation=90, ha="center", va="bottom", fontsize=7)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(ROUTE_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(summary: pd.Series, ledger: pd.DataFrame, route: pd.DataFrame, gate: pd.DataFrame, schema_probe: pd.DataFrame) -> None:
    orderflow_missing = int(summary["full_orderflow_missing_order_count"])
    minute_missing = int(summary["minute_feature_missing_order_count"])
    w0_missing = int(summary["real_w0_missing_request_count"])
    text = f"""# Stage255 Microstructure Coverage Closure Audit

- line_id: `{LINE_ID}`
- created_at: `{summary["created_at"]}`
- decision: `{summary["decision"]}`
- nature: read-only coverage closure; no strategy rule, no true engine, no A/B, no official config change, no CTP/order API

## External Research Judgment

- Order-flow imbalance and order-book imbalance research generally require dynamic book/trade events, queue/depth changes, or signed aggressor flow. Static minute OHLCV/OI bars are not a substitute for MBO/MBP10 or same-source execution replay.
- Local evidence is consistent with that first-principles view: the minute feature layer is complete, but the real microstructure layer is still absent.

## Main Answer

- Minute-level point-in-time supplement: ready `{summary["minute_feature_ready_order_count"]}/219`, missing `{minute_missing}`.
- Formal minute feature table: ready `{summary["formal_feature_ready_row_count"]}/219`.
- Real W0 MBO/MBP10 request package: ready `{summary["real_w0_ready_request_count"]}/41`, missing `{w0_missing}`.
- Real W0 windows: ready `{summary["real_w0_ready_window_count"]}/70`, missing `{summary["real_w0_missing_window_count"]}`.
- Full real orderflow coverage for entry decisions: ready `{summary["full_orderflow_ready_order_count"]}/219`, missing `{orderflow_missing}`.
- Same-source execution replay coverage: missing `{summary["same_source_execution_replay_missing_order_count"]}/219`.

## Route Judgment

The local supplement is finished for minute features. Continuing to "fill coverage" locally would only duplicate low-information OHLCV/OI features that Stage239-247 and Stage252-254 have already blocked from promotion. The remaining gap is external: authorized MBO/MBP10 depth or same-source execution replay.

## Coverage Ledger

{ledger.to_markdown(index=False)}

## Route Status

{route.to_markdown(index=False)}

## Gate Status

{gate.to_markdown(index=False)}

## Schema Probe

{schema_probe.groupby("schema_name", dropna=False).agg(required=("required_column", "count"), present=("present_in_stage180_filtered_source", "sum"), ready=("schema_ready", "max")).reset_index().to_markdown(index=False)}
"""
    _write_text(REPORT_OUT, text)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    inputs = _load_inputs()
    schema_probe = _build_schema_probe(inputs["stage180_manifest"])
    ledger = _build_coverage_ledger(inputs, schema_probe)
    route = _build_route_status(inputs, ledger)
    gate = _build_gate_status(inputs, ledger, schema_probe)
    summary = _build_summary(inputs, ledger, route, gate, schema_probe)

    _write_csv(schema_probe, SCHEMA_OUT)
    _write_csv(ledger, COVERAGE_OUT)
    _write_csv(route, ROUTE_OUT)
    _write_csv(gate, GATE_OUT)
    _write_csv(summary, SUMMARY_OUT)
    _write_json(DECISION_OUT, summary.iloc[0].to_dict())
    _write_report(summary.iloc[0], ledger, route, gate, schema_probe)

    _plot_official_path(inputs["stage251_curve"], summary.iloc[0])
    _plot_coverage(ledger)
    _plot_gates(gate)
    _plot_schema(schema_probe)
    _plot_routes(route)


if __name__ == "__main__":
    main()
