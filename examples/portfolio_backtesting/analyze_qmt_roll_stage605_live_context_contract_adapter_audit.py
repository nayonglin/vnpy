from __future__ import annotations

from datetime import datetime
import json
import math
import os
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


MODEL_TAG = "stage605_live_context_contract_adapter_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage605_live_context_contract_adapter_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE591_TAG = "stage591_stage526_bridge_submit_adapter_dry_run_v1"
STAGE591_PREFIX = "qmt_roll_stage591_stage526_bridge_submit_adapter_dry_run"
STAGE591_SUBMIT_PLAN = OUTPUT_DIR / f"{STAGE591_PREFIX}_submit_plan_{STAGE591_TAG}.csv"
STAGE591_CONTEXT = OUTPUT_DIR / f"{STAGE591_PREFIX}_live_context_requirements_{STAGE591_TAG}.csv"
STAGE591_DECISION = OUTPUT_DIR / f"{STAGE591_PREFIX}_decision_{STAGE591_TAG}.json"

STAGE587_TAG = "stage587_stage526_live_tca_bridge_dry_run_v1"
STAGE587_PREFIX = "qmt_roll_stage587_stage526_live_tca_bridge_dry_run"
STAGE587_TCA_LEDGER = OUTPUT_DIR / f"{STAGE587_PREFIX}_live_tca_ledger_{STAGE587_TAG}.csv"

CONTRACT_SCHEMA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contract_schema_{MODEL_TAG}.csv"
IMPLEMENTATION_GAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_implementation_gap_{MODEL_TAG}.csv"
SIGNAL_CONTRACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_signal_contract_{MODEL_TAG}.csv"
CHAIN_PROGRESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chain_progress_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

ORDER_REFERENCE_PREFIX = "Stage526TCA"
EXPECTED_P0_LIVE_SAMPLES_PER_SIGNAL = 3

REFERENCE_LINKS = [
    "VeighNa community order/trade callback discussion: https://www.vnpy.com/forum/post/69782",
    "vn.py event-driven architecture reference: https://deepwiki.com/vnpy/vnpy/2.1-main-engine-and-event-system",
    "vn.py MainEngine reference: https://deepwiki.com/vnpy/vnpy/2.2-main-engine",
    "vn.py custom gateway order contract reference: https://deepwiki.com/vnpy/vnpy/7.2-creating-custom-gateways",
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def _num(value: Any, default: float = 0.0) -> float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return float(number)


def _bool_int(value: Any) -> int:
    return int(_num(value, 0.0) != 0.0)


def _split_semicolon(value: Any) -> list[str]:
    text = _clean(value)
    if not text:
        return []
    return [part.strip() for part in text.split(";") if part.strip()]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 30) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.copy()
    if columns is not None:
        view = view[[column for column in columns if column in view.columns]]
    if len(view) > max_rows:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def build_contract_schema() -> pd.DataFrame:
    rows = [
        {
            "contract_field": "fresh_contract_snapshot",
            "phase": "pre_submit",
            "source_object": "ContractData",
            "source_method_or_event": "MainEngine.get_contract / EVENT_CONTRACT",
            "local_fields": "size, pricetick, min_volume, max_volume, product, exchange",
            "max_age_seconds": 300,
            "fail_closed_rule": "missing contract or invalid size/pricetick blocks submit",
            "stage591_field": "fresh_contract_snapshot",
            "tca_consumer": "price tick rounding, volume lot validation, contract multiplier",
            "implementation_status": "source_supported_current_snapshot_missing",
            "evidence": "vnpy/trader/engine.py:142,420,471; vnpy/trader/object.py:233",
        },
        {
            "contract_field": "fresh_account_snapshot",
            "phase": "pre_submit",
            "source_object": "AccountData",
            "source_method_or_event": "MainEngine.get_all_accounts/get_account / EVENT_ACCOUNT",
            "local_fields": "accountid, balance, frozen, available, vt_accountid",
            "max_age_seconds": 300,
            "fail_closed_rule": "missing/stale account snapshot blocks submit",
            "stage591_field": "fresh_account_snapshot",
            "tca_consumer": "account_equity_before, available cash and post-trade reconciliation",
            "implementation_status": "source_supported_current_snapshot_missing",
            "evidence": "vnpy/trader/engine.py:147,415,507; vnpy/trader/object.py:201",
        },
        {
            "contract_field": "fresh_position_snapshot",
            "phase": "pre_submit",
            "source_object": "PositionData",
            "source_method_or_event": "MainEngine.get_all_positions/get_position / EVENT_POSITION",
            "local_fields": "volume, frozen, yd_volume, price, pnl, direction",
            "max_age_seconds": 300,
            "fail_closed_rule": "missing/stale position snapshot blocks close/reconcile submit",
            "stage591_field": "fresh_position_snapshot",
            "tca_consumer": "close order eligibility, residual position reconciliation",
            "implementation_status": "source_supported_current_snapshot_missing",
            "evidence": "vnpy/trader/engine.py:145,405; vnpy/trader/object.py:179",
        },
        {
            "contract_field": "live_limit_price",
            "phase": "pre_submit",
            "source_object": "TickData",
            "source_method_or_event": "MainEngine.get_tick / EVENT_TICK",
            "local_fields": "bid_price_1, ask_price_1, last_price, limit_up, limit_down, localtime",
            "max_age_seconds": 10,
            "fail_closed_rule": "missing live quote or operator-approved limit policy blocks submit",
            "stage591_field": "live_limit_price",
            "tca_consumer": "arrival price, limit price, implementation shortfall",
            "implementation_status": "source_supported_current_snapshot_missing",
            "evidence": "vnpy/trader/engine.py:137,373,441; vnpy/trader/object.py:30",
        },
        {
            "contract_field": "account_equity_before",
            "phase": "pre_submit",
            "source_object": "AccountData",
            "source_method_or_event": "fresh account snapshot",
            "local_fields": "balance, available",
            "max_age_seconds": 300,
            "fail_closed_rule": "missing account equity blocks sizing and TCA denominator",
            "stage591_field": "account_equity_before",
            "tca_consumer": "order notional/equity pct and risk after submit",
            "implementation_status": "source_supported_current_snapshot_missing",
            "evidence": "vnpy/trader/object.py:201",
        },
        {
            "contract_field": "broker_margin_before",
            "phase": "pre_submit",
            "source_object": "AccountData + broker/contract margin policy",
            "source_method_or_event": "fresh account/position snapshot plus adapter margin calculation",
            "local_fields": "available, frozen, position volume, contract size",
            "max_age_seconds": 300,
            "fail_closed_rule": "missing margin before/after estimate blocks real submit",
            "stage591_field": "broker_margin_before",
            "tca_consumer": "margin sufficiency, post-submit drift audit",
            "implementation_status": "adapter_calculation_missing",
            "evidence": "vnpy/trader/object.py:201,179,233",
        },
        {
            "contract_field": "price_band_checked",
            "phase": "pre_submit",
            "source_object": "TickData + ContractData",
            "source_method_or_event": "live tick and contract tick-size validation",
            "local_fields": "limit_up, limit_down, pricetick",
            "max_age_seconds": 10,
            "fail_closed_rule": "limit price outside exchange band or off tick-size blocks submit",
            "stage591_field": "price_band_checked",
            "tca_consumer": "reject prevention and price-policy replay",
            "implementation_status": "adapter_check_missing",
            "evidence": "vnpy/trader/object.py:30,233",
        },
        {
            "contract_field": "margin_available_checked",
            "phase": "pre_submit",
            "source_object": "AccountData + planned order",
            "source_method_or_event": "adapter pre-submit risk check",
            "local_fields": "available, planned_volume, price, size",
            "max_age_seconds": 300,
            "fail_closed_rule": "insufficient available margin blocks submit",
            "stage591_field": "margin_available_checked",
            "tca_consumer": "pre-submit risk gate and explainable reject prevention",
            "implementation_status": "adapter_check_missing",
            "evidence": "Stage591 dry-run live_context_requirements has 0 current rows",
        },
        {
            "contract_field": "operator_confirmed",
            "phase": "pre_submit",
            "source_object": "explicit operator token",
            "source_method_or_event": "dry-run-to-real confirmation gate",
            "local_fields": "operator_confirmed, operator_note, confirm_token",
            "max_age_seconds": 300,
            "fail_closed_rule": "no explicit confirmation blocks real submit",
            "stage591_field": "operator_confirmed",
            "tca_consumer": "human approval audit",
            "implementation_status": "confirmation_gate_missing_for_real_submit",
            "evidence": "skills/futures-live-execution-sop/SKILL.md",
        },
        {
            "contract_field": "bridge_signal_id_reference",
            "phase": "submit",
            "source_object": "OrderRequest",
            "source_method_or_event": "OrderRequest.reference",
            "local_fields": "reference",
            "max_age_seconds": 0,
            "fail_closed_rule": "reference must equal Stage526TCA:<bridge_signal_id>",
            "stage591_field": "order_reference",
            "tca_consumer": "join signal intent to returned vt_orderid",
            "implementation_status": "implemented_in_stage591_dry_run",
            "evidence": "vnpy/trader/object.py:321,333,352; Stage591 submit plan",
        },
        {
            "contract_field": "real_vt_orderid_mapping",
            "phase": "submit",
            "source_object": "MainEngine.send_order return value",
            "source_method_or_event": "MainEngine.send_order(req, gateway_name)",
            "local_fields": "vt_orderid",
            "max_age_seconds": 0,
            "fail_closed_rule": "empty vt_orderid or synthetic id blocks zero-bias claim",
            "stage591_field": "vt_orderid",
            "tca_consumer": "join order/trade events to bridge_signal_id",
            "implementation_status": "source_supported_writer_missing",
            "evidence": "vnpy/trader/engine.py:233; vnpy/trader/gateway.py:197",
        },
        {
            "contract_field": "event_order_capture",
            "phase": "post_submit",
            "source_object": "OrderData",
            "source_method_or_event": "EVENT_ORDER",
            "local_fields": "vt_orderid, reference, status, traded, volume, price, datetime",
            "max_age_seconds": 0,
            "fail_closed_rule": "no order event join blocks execution audit",
            "stage591_field": "event_order_capture",
            "tca_consumer": "submit/reject/cancel/partial-fill status ledger",
            "implementation_status": "source_supported_event_join_missing",
            "evidence": "vnpy/trader/gateway.py:112; vnpy/trader/engine.py:378",
        },
        {
            "contract_field": "event_trade_capture",
            "phase": "post_submit",
            "source_object": "TradeData",
            "source_method_or_event": "EVENT_TRADE",
            "local_fields": "vt_orderid, vt_tradeid, price, volume, datetime",
            "max_age_seconds": 0,
            "fail_closed_rule": "no trade event join blocks fill-price TCA",
            "stage591_field": "event_trade_capture",
            "tca_consumer": "avg fill, filled volume, commission/slippage attribution",
            "implementation_status": "source_supported_event_join_missing",
            "evidence": "vnpy/trader/gateway.py:104; vnpy/trader/engine.py:395",
        },
        {
            "contract_field": "event_tick_capture",
            "phase": "post_submit",
            "source_object": "TickData",
            "source_method_or_event": "EVENT_TICK",
            "local_fields": "vt_symbol, datetime, bid/ask, last_price, volume, turnover",
            "max_age_seconds": 0,
            "fail_closed_rule": "no tick capture blocks arrival/VWAP comparison",
            "stage591_field": "event_tick_capture",
            "tca_consumer": "arrival price, live VWAP, participation estimate",
            "implementation_status": "source_supported_event_join_missing",
            "evidence": "vnpy/trader/gateway.py:96; vnpy/trader/engine.py:373",
        },
    ]
    return pd.DataFrame(rows)


def build_implementation_gap(
    submit_plan: pd.DataFrame,
    context: pd.DataFrame,
    tca_ledger: pd.DataFrame,
    stage591_decision: dict[str, Any],
) -> pd.DataFrame:
    row_count = len(submit_plan)
    payload_ready = int((submit_plan["submit_status"].astype(str) == "dry_run_order_request_payload_ready").sum()) if row_count else 0
    ref_ready = int(pd.to_numeric(submit_plan.get("reference_carries_bridge_id", 0), errors="coerce").fillna(0).sum()) if row_count else 0
    context_required = int(pd.to_numeric(context.get("required_before_real_submit", 0), errors="coerce").fillna(0).sum()) if not context.empty else 0
    context_present = int(pd.to_numeric(context.get("present_in_dry_run", 0), errors="coerce").fillna(0).sum()) if not context.empty else 0
    vt_mapped = int(submit_plan["vt_orderid"].map(lambda item: 1 if _clean(item) else 0).sum()) if row_count and "vt_orderid" in submit_plan.columns else 0
    joined = int((tca_ledger.get("bridge_join_status", pd.Series(dtype=str)).astype(str) == "joined").sum()) if not tca_ledger.empty else 0
    p0 = tca_ledger[tca_ledger.get("watch_priority", pd.Series(dtype=str)).astype(str).str.startswith("P0")] if not tca_ledger.empty else pd.DataFrame()
    p0_valid = int(pd.to_numeric(p0.get("valid_live_tca_sample", 0), errors="coerce").fillna(0).sum()) if not p0.empty else 0
    p0_required = int(len(p0) * EXPECTED_P0_LIVE_SAMPLES_PER_SIGNAL)

    rows = [
        ("vnpy_order_reference_supported", "source", 1, "OrderRequest.reference and OrderData.reference exist", "vnpy/trader/object.py:130,333,352", "keep"),
        ("vnpy_send_order_returns_vt_orderid", "source", 1, "MainEngine delegates to gateway.send_order and BaseGateway contract returns vt_orderid", "vnpy/trader/engine.py:233; vnpy/trader/gateway.py:197", "keep"),
        ("vnpy_order_trade_tick_events_supported", "source", 1, "EVENT_ORDER/EVENT_TRADE/EVENT_TICK are pushed and cached", "vnpy/trader/event.py:7-9; vnpy/trader/gateway.py:96-115; vnpy/trader/engine.py:373-395", "keep"),
        ("stage591_order_request_payload_ready", "adapter_dry_run", int(payload_ready == row_count and row_count > 0), f"{payload_ready}/{row_count}", str(STAGE591_SUBMIT_PLAN), "keep"),
        ("stage591_reference_bridge_ready", "adapter_dry_run", int(ref_ready == row_count and row_count > 0), f"{ref_ready}/{row_count}", str(STAGE591_SUBMIT_PLAN), "keep"),
        ("dry_run_no_broker_api_call", "safety", int(stage591_decision.get("send_order_api_called_count", 1) == 0 and not stage591_decision.get("ctp_connection_attempted", True)), "send_order=0, ctp_connection=False", str(STAGE591_DECISION), "keep"),
        ("fresh_live_context_adapter", "missing_adapter", int(context_present == context_required and context_required > 0), f"{context_present}/{context_required}", str(STAGE591_CONTEXT), "implement"),
        ("real_vt_orderid_mapping_writer", "missing_adapter", int(vt_mapped == row_count and row_count > 0), f"{vt_mapped}/{row_count}", str(STAGE591_SUBMIT_PLAN), "implement"),
        ("order_trade_tick_join_reducer", "missing_join", int(joined == row_count and row_count > 0), f"{joined}/{row_count}", str(STAGE587_TCA_LEDGER), "implement"),
        ("p0_valid_live_tca_samples", "missing_evidence", int(p0_valid >= p0_required and p0_required > 0), f"{p0_valid}/{p0_required}", str(STAGE587_TCA_LEDGER), "collect_live_or_independent_minute_evidence"),
    ]
    return pd.DataFrame(
        [
            {
                "capability_or_gap": name,
                "layer": layer,
                "passed": passed,
                "observed": observed,
                "evidence": evidence,
                "next_action": action,
            }
            for name, layer, passed, observed, evidence, action in rows
        ]
    )


def build_signal_contract(submit_plan: pd.DataFrame, context: pd.DataFrame, tca_ledger: pd.DataFrame) -> pd.DataFrame:
    context_group = (
        context.groupby("bridge_signal_id")
        .agg(
            live_context_required_rows=("required_before_real_submit", lambda series: int(pd.to_numeric(series, errors="coerce").fillna(0).sum())),
            live_context_present_rows=("present_in_dry_run", lambda series: int(pd.to_numeric(series, errors="coerce").fillna(0).sum())),
        )
        .reset_index()
        if not context.empty
        else pd.DataFrame(columns=["bridge_signal_id", "live_context_required_rows", "live_context_present_rows"])
    )
    tca_cols = [
        "bridge_signal_id",
        "bridge_join_status",
        "valid_live_tca_sample",
        "bridge_vt_orderid",
        "bridge_status",
        "bridge_blockers",
        "actual_participation_pct",
    ]
    tca_view = tca_ledger[[column for column in tca_cols if column in tca_ledger.columns]].copy() if not tca_ledger.empty else pd.DataFrame(columns=tca_cols)

    merged = submit_plan.merge(context_group, on="bridge_signal_id", how="left").merge(tca_view, on="bridge_signal_id", how="left", suffixes=("", "_tca"))
    rows: list[dict[str, Any]] = []
    for row in merged.to_dict(orient="records"):
        bridge_signal_id = _clean(row.get("bridge_signal_id"))
        vt_orderid = _clean(row.get("vt_orderid")) or _clean(row.get("bridge_vt_orderid"))
        required = int(_num(row.get("live_context_required_rows"), 0.0))
        present = int(_num(row.get("live_context_present_rows"), 0.0))
        ref_ready = _bool_int(row.get("reference_carries_bridge_id"))
        payload_ready = int(_clean(row.get("submit_status")) == "dry_run_order_request_payload_ready")
        tca_join_status = _clean(row.get("bridge_join_status")) or "not_joined"
        valid_tca = _bool_int(row.get("valid_live_tca_sample"))
        blockers = _split_semicolon(row.get("bridge_blockers"))

        if present < required:
            blocker_class = "fresh_live_context_missing"
        elif not vt_orderid:
            blocker_class = "real_vt_orderid_mapping_missing"
        elif tca_join_status != "joined":
            blocker_class = "order_trade_tick_join_missing"
        elif not valid_tca:
            blocker_class = "valid_live_tca_sample_missing"
        else:
            blocker_class = "ready_for_zero_bias_claim"

        rows.append(
            {
                "bridge_signal_id": bridge_signal_id,
                "event_id": row.get("event_id"),
                "date": row.get("date"),
                "vt_symbol": row.get("vt_symbol"),
                "watch_priority": row.get("watch_priority"),
                "order_reference_ready": ref_ready,
                "dry_run_payload_ready": payload_ready,
                "live_context_required_rows": required,
                "live_context_present_rows": present,
                "vt_orderid_present": int(bool(vt_orderid)),
                "tca_join_status": tca_join_status,
                "valid_live_tca_sample": valid_tca,
                "bridge_blocker_count": len(blockers),
                "next_blocker_class": blocker_class,
            }
        )
    return pd.DataFrame(rows)


def build_chain_progress(signal_contract: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    phases = [
        ("intent_loaded", "Stage587 intent ledger row exists"),
        ("dry_run_payload", "Stage591 OrderRequest payload is valid"),
        ("fresh_live_context", "all Stage591 live context fields present"),
        ("real_vt_orderid", "exact MainEngine.send_order return value persisted"),
        ("order_trade_tick_join", "EVENT_ORDER/EVENT_TRADE/EVENT_TICK joined to signal"),
        ("valid_tca_sample", "valid live TCA sample passes thresholds"),
    ]
    for row in signal_contract.to_dict(orient="records"):
        required = int(_num(row.get("live_context_required_rows"), 0.0))
        present = int(_num(row.get("live_context_present_rows"), 0.0))
        values = {
            "intent_loaded": 1,
            "dry_run_payload": _bool_int(row.get("dry_run_payload_ready")),
            "fresh_live_context": int(required > 0 and present == required),
            "real_vt_orderid": _bool_int(row.get("vt_orderid_present")),
            "order_trade_tick_join": int(_clean(row.get("tca_join_status")) == "joined"),
            "valid_tca_sample": _bool_int(row.get("valid_live_tca_sample")),
        }
        for phase, description in phases:
            rows.append(
                {
                    "bridge_signal_id": row.get("bridge_signal_id"),
                    "vt_symbol": row.get("vt_symbol"),
                    "watch_priority": row.get("watch_priority"),
                    "phase": phase,
                    "passed": values[phase],
                    "description": description,
                }
            )
    return pd.DataFrame(rows)


def build_gates(
    submit_plan: pd.DataFrame,
    context: pd.DataFrame,
    implementation_gap: pd.DataFrame,
    signal_contract: pd.DataFrame,
    stage591_decision: dict[str, Any],
) -> pd.DataFrame:
    row_count = len(submit_plan)
    p0_count = int(submit_plan.get("is_stage526_p0", pd.Series(dtype=float)).map(_bool_int).sum()) if row_count else 0
    p0_required_samples = p0_count * EXPECTED_P0_LIVE_SAMPLES_PER_SIGNAL
    p0_valid_samples = 0
    hard_rows = [
        ("no_ctp_connection_attempted", not stage591_decision.get("ctp_connection_attempted", True), str(stage591_decision.get("ctp_connection_attempted")), "False", "hard", "This audit must remain dry-run/static."),
        ("no_send_order_api_called", int(stage591_decision.get("send_order_api_called_count", 1)) == 0, str(stage591_decision.get("send_order_api_called_count")), "0", "hard", "No broker API call is allowed in this audit."),
        ("order_reference_supported_and_populated", bool((implementation_gap["capability_or_gap"] == "stage591_reference_bridge_ready").any() and int(implementation_gap.loc[implementation_gap["capability_or_gap"] == "stage591_reference_bridge_ready", "passed"].iloc[0]) == 1), "Stage591 references", "all rows", "hard", "Signal id must survive into OrderRequest.reference."),
        ("vnpy_vt_orderid_contract_supported", bool((implementation_gap["capability_or_gap"] == "vnpy_send_order_returns_vt_orderid").any()), "source present", "source present", "hard", "Adapter must persist exact returned vt_orderid, not synthesize one."),
        ("order_trade_tick_events_supported", bool((implementation_gap["capability_or_gap"] == "vnpy_order_trade_tick_events_supported").any()), "source present", "source present", "hard", "TCA requires event streams."),
        ("dry_run_order_payload_ready", int(signal_contract["dry_run_payload_ready"].sum()) == row_count and row_count > 0, f"{int(signal_contract['dry_run_payload_ready'].sum())}/{row_count}", "all rows", "hard", "Payload contract must be valid before live adapter work."),
        (
            "fresh_live_context_ready",
            int(pd.to_numeric(context.get("present_in_dry_run", 0), errors="coerce").fillna(0).sum()) == int(pd.to_numeric(context.get("required_before_real_submit", 0), errors="coerce").fillna(0).sum()) and not context.empty,
            f"{int(pd.to_numeric(context.get('present_in_dry_run', 0), errors='coerce').fillna(0).sum())}/{int(pd.to_numeric(context.get('required_before_real_submit', 0), errors='coerce').fillna(0).sum())}",
            "all required rows",
            "hard",
            "Contract/account/position/tick/operator context must be fresh before real submit.",
        ),
        ("real_vt_orderid_mapping_ready", int(signal_contract["vt_orderid_present"].sum()) == row_count and row_count > 0, f"{int(signal_contract['vt_orderid_present'].sum())}/{row_count}", "all rows", "hard", "Real submit mapping must exist before TCA join."),
        ("order_trade_tick_join_ready", int((signal_contract["tca_join_status"] == "joined").sum()) == row_count and row_count > 0, f"{int((signal_contract['tca_join_status'] == 'joined').sum())}/{row_count}", "all rows", "hard", "Order/trade/tick events must join to bridge_signal_id."),
        ("p0_valid_live_tca_samples_ready", p0_valid_samples >= p0_required_samples and p0_required_samples > 0, f"{p0_valid_samples}/{p0_required_samples}", "3 samples per P0 signal", "hard", "P0 evidence requires repeated real/independent fill-quality samples."),
    ]
    return pd.DataFrame(
        [
            {
                "gate": name,
                "passed": int(bool(passed)),
                "observed": observed,
                "required": required,
                "severity": severity,
                "rationale": rationale,
            }
            for name, passed, observed, required, severity, rationale in hard_rows
        ]
    )


def plot_chart(
    implementation_gap: pd.DataFrame,
    context: pd.DataFrame,
    signal_contract: pd.DataFrame,
    chain_progress: pd.DataFrame,
    gates: pd.DataFrame,
) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang SC", "Heiti TC", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    fig.suptitle("Stage605 execution no-bias contract audit: source ready, live evidence missing", fontsize=15, fontweight="bold")

    ax = axes[0, 0]
    gap_counts = implementation_gap.groupby("layer")["passed"].agg(["sum", "count"]).reset_index()
    gap_counts["failed"] = gap_counts["count"] - gap_counts["sum"]
    y = np.arange(len(gap_counts))
    ax.barh(y, gap_counts["sum"], color="#2E7D32", label="passed")
    ax.barh(y, gap_counts["failed"], left=gap_counts["sum"], color="#C62828", label="missing/failed")
    ax.set_yticks(y)
    ax.set_yticklabels(gap_counts["layer"])
    ax.set_xlabel("capability count")
    ax.set_title("Capability and adapter gap by layer")
    for idx, row in gap_counts.iterrows():
        ax.text(row["count"] + 0.05, idx, f"{int(row['sum'])}/{int(row['count'])}", va="center", fontsize=9)
    ax.legend(loc="lower right")

    ax = axes[0, 1]
    context_counts = (
        context.groupby("required_field")
        .agg(required=("required_before_real_submit", lambda series: int(pd.to_numeric(series, errors="coerce").fillna(0).sum())),
             present=("present_in_dry_run", lambda series: int(pd.to_numeric(series, errors="coerce").fillna(0).sum())))
        .reset_index()
        if not context.empty
        else pd.DataFrame(columns=["required_field", "required", "present"])
    )
    context_counts = context_counts.sort_values("required_field")
    y = np.arange(len(context_counts))
    ax.barh(y, context_counts["required"], color="#E0E0E0", label="required")
    ax.barh(y, context_counts["present"], color="#1565C0", label="present")
    ax.set_yticks(y)
    ax.set_yticklabels(context_counts["required_field"], fontsize=8)
    ax.set_xlabel("rows")
    ax.set_title("Stage591 live context: still all missing")
    for idx, row in context_counts.iterrows():
        ax.text(row["required"] + 0.05, idx, f"{int(row['present'])}/{int(row['required'])}", va="center", fontsize=8)
    ax.legend(loc="lower right")

    ax = axes[1, 0]
    phase_order = ["intent_loaded", "dry_run_payload", "fresh_live_context", "real_vt_orderid", "order_trade_tick_join", "valid_tca_sample"]
    signal_labels = signal_contract["vt_symbol"].astype(str) + "\n" + signal_contract["watch_priority"].astype(str).str.slice(0, 18)
    matrix = (
        chain_progress.pivot_table(index="bridge_signal_id", columns="phase", values="passed", aggfunc="max")
        .reindex(signal_contract["bridge_signal_id"])
        .reindex(columns=phase_order)
        .fillna(0)
        .astype(float)
    )
    ax.imshow(matrix.values, aspect="auto", cmap=matplotlib.colors.ListedColormap(["#C62828", "#2E7D32"]), vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(phase_order)))
    ax.set_xticklabels(["intent", "payload", "context", "vt_orderid", "event join", "valid TCA"], rotation=30, ha="right")
    ax.set_yticks(np.arange(len(signal_labels)))
    ax.set_yticklabels(signal_labels, fontsize=8)
    ax.set_title("Per-signal chain progress")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, "Y" if matrix.iloc[i, j] else "N", ha="center", va="center", color="white", fontsize=8, fontweight="bold")

    ax = axes[1, 1]
    gates_view = gates.copy()
    colors = np.where(gates_view["passed"].astype(int).eq(1), "#2E7D32", "#C62828")
    y = np.arange(len(gates_view))
    ax.barh(y, np.ones(len(gates_view)), color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels(gates_view["gate"], fontsize=8)
    ax.set_xlim(0, 1)
    ax.set_xticks([])
    ax.set_title("Hard gates")
    for idx, row in gates_view.iterrows():
        label = "PASS" if int(row["passed"]) else f"FAIL {row['observed']}"
        ax.text(0.02, idx, label, va="center", ha="left", color="white", fontsize=8, fontweight="bold")

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def write_report(
    contract_schema: pd.DataFrame,
    implementation_gap: pd.DataFrame,
    signal_contract: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    failed_gates = gates[gates["passed"].astype(int).eq(0)].copy()
    p0_contract = signal_contract[signal_contract["watch_priority"].astype(str).str.startswith("P0")].copy()
    lines = [
        f"# Stage605 Live Context Contract Adapter Audit",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- model_tag: `{MODEL_TAG}`",
        f"- checked_at: `{decision['checked_at']}`",
        "- stage nature: static/dry-run execution contract audit; no strategy replay, no CTP connection, no broker order.",
        f"- decision: `{decision['decision']}`",
        f"- zero_execution_bias_claim_allowed: `{decision['zero_execution_bias_claim_allowed']}`",
        f"- promotion_allowed: `{decision['promotion_allowed']}`",
        "",
        "## External Research And Judgment",
        "",
        *[f"- {item}" for item in REFERENCE_LINKS],
        "",
        "Judgment: vn.py already provides the required primitive contract: OrderRequest.reference can carry the bridge signal id, MainEngine.send_order returns vt_orderid through the gateway, and order/trade/tick/account/position/contract events are available. The missing part is not framework capability; it is the project adapter that captures fresh live context, persists the exact returned vt_orderid, and joins EVENT_ORDER/EVENT_TRADE/EVENT_TICK into the TCA ledger.",
        "",
        "## Key Metrics",
        "",
        f"- submit_plan_rows: `{decision['submit_plan_rows']}`",
        f"- p0_rows: `{decision['p0_rows']}`",
        f"- dry_run_payload_ready_rows: `{decision['dry_run_payload_ready_rows']}`",
        f"- live_context_present_rows: `{decision['live_context_present_rows']}/{decision['live_context_required_rows']}`",
        f"- real_vt_orderid_mappings: `{decision['real_vt_orderid_mappings']}/{decision['submit_plan_rows']}`",
        f"- p0_valid_live_tca_samples: `{decision['p0_valid_live_tca_samples']}/{decision['p0_required_live_tca_samples']}`",
        f"- hard_gates: `{decision['hard_gates_passed']}/{decision['hard_gates_total']}`",
        f"- send_order_api_called_count: `{decision['send_order_api_called_count']}`",
        f"- ctp_connection_attempted: `{decision['ctp_connection_attempted']}`",
        "",
        "## Failed Hard Gates",
        "",
        _md_table(failed_gates, ["gate", "observed", "required", "rationale"], max_rows=20),
        "",
        "## P0 Signal Chain",
        "",
        _md_table(
            p0_contract,
            [
                "bridge_signal_id",
                "vt_symbol",
                "order_reference_ready",
                "dry_run_payload_ready",
                "live_context_present_rows",
                "live_context_required_rows",
                "vt_orderid_present",
                "tca_join_status",
                "valid_live_tca_sample",
                "next_blocker_class",
            ],
            max_rows=10,
        ),
        "",
        "## Implementation Gap",
        "",
        _md_table(implementation_gap, ["capability_or_gap", "layer", "passed", "observed", "next_action"], max_rows=30),
        "",
        "## Contract Schema Snapshot",
        "",
        _md_table(contract_schema, ["contract_field", "phase", "source_object", "max_age_seconds", "implementation_status"], max_rows=30),
        "",
        "## Visual Review Notes",
        "",
        "- The upper-left panel should show source and dry-run layers mostly green while missing adapter/evidence layers remain red.",
        "- The upper-right panel should show every Stage591 live-context field at 0 present rows; this is the immediate blocker before any real submit.",
        "- The lower-left heatmap should show intent and payload green, then turn red at live context, vt_orderid, event join, and valid TCA.",
        "- The lower-right gate panel should fail only the real execution evidence gates, not the dry-run safety gates.",
        "",
        "## Conclusion",
        "",
        "The execution primitive contract is ready, but the deployable adapter is not. The next code-bearing step should implement a fresh live context collector plus a real submit-mapping ledger that writes the exact vt_orderid returned by MainEngine.send_order, then joins EVENT_ORDER/EVENT_TRADE/EVENT_TICK for TCA. Until those rows exist, Stage079/Stage526-like structures cannot claim no real-trading bias.",
        "",
        "## Overfitting Reflection",
        "",
        "No. This audit does not alter signals, parameters, products, sizing, or historical fills. It only checks whether live execution evidence can support the backtest-to-real bridge.",
        "",
        "## Continue Value Reflection",
        "",
        "Yes. The audit identifies a concrete implementation boundary: build the live context adapter and vt_orderid/event join ledger before more selector or product-pool research.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    submit_plan = _read_csv(STAGE591_SUBMIT_PLAN)
    context = _read_csv(STAGE591_CONTEXT)
    stage591_decision = _read_json(STAGE591_DECISION)
    tca_ledger = _read_csv(STAGE587_TCA_LEDGER)

    contract_schema = build_contract_schema()
    implementation_gap = build_implementation_gap(submit_plan, context, tca_ledger, stage591_decision)
    signal_contract = build_signal_contract(submit_plan, context, tca_ledger)
    chain_progress = build_chain_progress(signal_contract)
    gates = build_gates(submit_plan, context, implementation_gap, signal_contract, stage591_decision)

    submit_rows = int(len(submit_plan))
    p0_rows = int(pd.to_numeric(submit_plan.get("is_stage526_p0", 0), errors="coerce").fillna(0).sum()) if submit_rows else 0
    live_context_required = int(pd.to_numeric(context.get("required_before_real_submit", 0), errors="coerce").fillna(0).sum()) if not context.empty else 0
    live_context_present = int(pd.to_numeric(context.get("present_in_dry_run", 0), errors="coerce").fillna(0).sum()) if not context.empty else 0
    vt_mappings = int(signal_contract["vt_orderid_present"].sum()) if not signal_contract.empty else 0
    dry_payload = int(signal_contract["dry_run_payload_ready"].sum()) if not signal_contract.empty else 0
    p0_required_samples = p0_rows * EXPECTED_P0_LIVE_SAMPLES_PER_SIGNAL
    p0_valid_samples = 0
    hard_gates_total = int(len(gates[gates["severity"].eq("hard")]))
    hard_gates_passed = int(gates.loc[gates["severity"].eq("hard"), "passed"].sum())

    decision = {
        "decision": "live_context_contract_ready_adapter_implementation_missing_no_submit",
        "promotion_allowed": False,
        "zero_execution_bias_claim_allowed": False,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "submit_plan_rows": submit_rows,
        "p0_rows": p0_rows,
        "dry_run_payload_ready_rows": dry_payload,
        "live_context_required_rows": live_context_required,
        "live_context_present_rows": live_context_present,
        "real_vt_orderid_mappings": vt_mappings,
        "p0_required_live_tca_samples": p0_required_samples,
        "p0_valid_live_tca_samples": p0_valid_samples,
        "hard_gates_passed": hard_gates_passed,
        "hard_gates_total": hard_gates_total,
        "send_order_api_called_count": int(stage591_decision.get("send_order_api_called_count", 0)),
        "ctp_connection_attempted": bool(stage591_decision.get("ctp_connection_attempted", False)),
        "source_contract_ready": True,
        "next_required_step": "implement_live_context_adapter_and_exact_vt_orderid_event_join_ledger",
        "overfit_reflection": "No. Static execution contract audit only; no strategy parameter, signal, product, or sizing change.",
        "continue_value_reflection": "Yes. It converts the real-trading bias blocker into concrete adapter fields and gates.",
    }

    contract_schema.to_csv(CONTRACT_SCHEMA_PATH, index=False, encoding="utf-8-sig")
    implementation_gap.to_csv(IMPLEMENTATION_GAP_PATH, index=False, encoding="utf-8-sig")
    signal_contract.to_csv(SIGNAL_CONTRACT_PATH, index=False, encoding="utf-8-sig")
    chain_progress.to_csv(CHAIN_PROGRESS_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    plot_chart(implementation_gap, context, signal_contract, chain_progress, gates)
    write_report(contract_schema, implementation_gap, signal_contract, gates, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
