from __future__ import annotations

from datetime import datetime, timezone
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


MODEL_TAG = "stage603_executable_critical_path_board_v1"
OUTPUT_PREFIX = "qmt_roll_stage603_executable_critical_path_board"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE561_DECISION = OUTPUT_DIR / "qmt_roll_stage561_selector_predictive_audit_protocol_decision_stage561_selector_predictive_audit_protocol_v1.json"
STAGE588_DECISION = OUTPUT_DIR / "qmt_roll_stage588_p0_selector_evidence_priority_audit_decision_stage588_p0_selector_evidence_priority_audit_v1.json"
STAGE588_EVIDENCE = OUTPUT_DIR / "qmt_roll_stage588_p0_selector_evidence_priority_audit_evidence_matrix_stage588_p0_selector_evidence_priority_audit_v1.csv"
STAGE588_GATES = OUTPUT_DIR / "qmt_roll_stage588_p0_selector_evidence_priority_audit_gates_stage588_p0_selector_evidence_priority_audit_v1.csv"
STAGE595_PRODUCT_READY = OUTPUT_DIR / "qmt_roll_stage595_p0_official_endpoint_discovery_product_readiness_stage595_p0_official_endpoint_discovery_v1.csv"
STAGE595_GATES = OUTPUT_DIR / "qmt_roll_stage595_p0_official_endpoint_discovery_gates_stage595_p0_official_endpoint_discovery_v1.csv"
STAGE583_P0_CLOSE_GATES = OUTPUT_DIR / "qmt_roll_stage583_stage526_live_tca_evidence_gap_audit_p0_close_gates_stage583_stage526_live_tca_evidence_gap_audit_v1.csv"
STAGE587_DECISION = OUTPUT_DIR / "qmt_roll_stage587_stage526_live_tca_bridge_dry_run_decision_stage587_stage526_live_tca_bridge_dry_run_v1.json"
STAGE587_GATES = OUTPUT_DIR / "qmt_roll_stage587_stage526_live_tca_bridge_dry_run_gates_stage587_stage526_live_tca_bridge_dry_run_v1.csv"
STAGE591_DECISION = OUTPUT_DIR / "qmt_roll_stage591_stage526_bridge_submit_adapter_dry_run_decision_stage591_stage526_bridge_submit_adapter_dry_run_v1.json"
STAGE591_GATES = OUTPUT_DIR / "qmt_roll_stage591_stage526_bridge_submit_adapter_dry_run_gates_stage591_stage526_bridge_submit_adapter_dry_run_v1.csv"
STAGE591_LIVE_CONTEXT = OUTPUT_DIR / "qmt_roll_stage591_stage526_bridge_submit_adapter_dry_run_live_context_requirements_stage591_stage526_bridge_submit_adapter_dry_run_v1.csv"
STAGE591_SUBMIT_PLAN = OUTPUT_DIR / "qmt_roll_stage591_stage526_bridge_submit_adapter_dry_run_submit_plan_stage591_stage526_bridge_submit_adapter_dry_run_v1.csv"
STAGE601_DECISION = OUTPUT_DIR / "qmt_roll_stage601_risk_slot_source_first_rescreen_decision_stage601_risk_slot_source_first_rescreen_v1.json"
STAGE602_DECISION = OUTPUT_DIR / "qmt_roll_stage602_full57_non_dce_new_family_scout_decision_stage602_full57_non_dce_new_family_scout_v1.json"

GATE_BOARD_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_board_{MODEL_TAG}.csv"
PRODUCT_GAPS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_gap_priority_{MODEL_TAG}.csv"
EXECUTION_GAPS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_execution_gap_priority_{MODEL_TAG}.csv"
TASK_PRIORITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_task_priority_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

REFERENCE_LINKS = [
    "CFA Institute Trading Costs and Electronic Markets: https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2025/trading-costs-and-electronic-markets",
    "pfolio look-ahead bias / point-in-time timestamps: https://www.pfolio.io/academy/look-ahead-bias",
    "Freqtrade lookahead-analysis timing checks: https://www.freqtrade.io/en/stable/lookahead-analysis/",
    "Man Group Trend Following Market Mix: https://www.man.com/insights/trend-following-optimal-market-mix",
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return (
        pd.to_numeric(frame[column], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(default)
        .astype(float)
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
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


def _pct(actual: float, required: float) -> float:
    if required <= 0:
        return 100.0 if actual >= required else 0.0
    return max(0.0, min(100.0, actual / required * 100.0))


def _build_gate_board() -> pd.DataFrame:
    stage588 = _read_json(STAGE588_DECISION)
    stage587 = _read_json(STAGE587_DECISION)
    stage591 = _read_json(STAGE591_DECISION)
    stage601 = _read_json(STAGE601_DECISION)
    stage602 = _read_json(STAGE602_DECISION)
    p0_close = _read_csv(STAGE583_P0_CLOSE_GATES)
    live_context = _read_csv(STAGE591_LIVE_CONTEXT)

    p0_required_samples = float(_num(p0_close, "required_valid_samples").sum())
    p0_valid_samples = float(_num(p0_close, "valid_live_tca_samples").sum())
    p0_remaining_samples = float(_num(p0_close, "remaining_valid_samples").sum())
    live_context_required = int(_num(live_context, "required_before_real_submit").sum())
    live_context_present = int(live_context.loc[_num(live_context, "required_before_real_submit").eq(1), "present_in_dry_run"].pipe(pd.to_numeric, errors="coerce").fillna(0).sum())

    rows = [
        {
            "area": "candidate_return_risk",
            "gate": "Stage526 normal-cost candidate boundary",
            "actual": 1,
            "required": 1,
            "progress_pct": 100.0,
            "status": "ready_for_execution_review",
            "blocking": 0,
            "decision_weight": "foundation",
            "comment": "Stage526 normal-cost candidate exists, but is not final without execution/TCA proof.",
        },
        {
            "area": "execution_no_bias",
            "gate": "OrderRequest dry-run payload with Stage526TCA reference",
            "actual": int(stage591.get("order_request_payload_rows", 0)),
            "required": int(stage591.get("submit_plan_rows", 5)),
            "progress_pct": _pct(float(stage591.get("order_request_payload_rows", 0)), float(stage591.get("submit_plan_rows", 5))),
            "status": "contract_ready",
            "blocking": 0,
            "decision_weight": "critical",
            "comment": "Dry-run adapter builds auditable payloads and keeps send_order disabled.",
        },
        {
            "area": "execution_no_bias",
            "gate": "Fresh live context before real submit",
            "actual": live_context_present,
            "required": live_context_required,
            "progress_pct": _pct(live_context_present, live_context_required),
            "status": "blocked",
            "blocking": 1,
            "decision_weight": "critical",
            "comment": "Real submit cannot start until fresh contract/account/position/limit/margin checks exist.",
        },
        {
            "area": "execution_no_bias",
            "gate": "Real vt_orderid mapping",
            "actual": int(stage591.get("real_vt_orderid_mappings", 0)),
            "required": int(stage591.get("submit_plan_rows", 5)),
            "progress_pct": _pct(float(stage591.get("real_vt_orderid_mappings", 0)), float(stage591.get("submit_plan_rows", 5))),
            "status": "blocked",
            "blocking": 1,
            "decision_weight": "critical",
            "comment": "Zero-bias claim needs send_order return vt_orderid mapped to bridge_signal_id.",
        },
        {
            "area": "execution_no_bias",
            "gate": "P0 valid live TCA samples",
            "actual": p0_valid_samples,
            "required": p0_required_samples,
            "progress_pct": _pct(p0_valid_samples, p0_required_samples),
            "status": "blocked",
            "blocking": 1,
            "decision_weight": "critical",
            "comment": f"Need {int(p0_remaining_samples)} more mapped fills or independent full-day minute samples for P0 close-window gaps.",
        },
        {
            "area": "external_selector",
            "gate": "P0 products with >=2 point-in-time external routes",
            "actual": int(stage588.get("products_with_two_or_more_routes", 0)),
            "required": int(stage588.get("p0_products", 5)),
            "progress_pct": _pct(float(stage588.get("products_with_two_or_more_routes", 0)), float(stage588.get("p0_products", 5))),
            "status": "blocked",
            "blocking": 1,
            "decision_weight": "high",
            "comment": "ao.SHFE and lu.INE still need basis/substitute routes.",
        },
        {
            "area": "external_selector",
            "gate": "P0 products with real event/news/manual-event coverage",
            "actual": int(stage588.get("products_with_real_event_coverage", 0)),
            "required": int(stage588.get("p0_products", 5)),
            "progress_pct": _pct(float(stage588.get("products_with_real_event_coverage", 0)), float(stage588.get("p0_products", 5))),
            "status": "blocked",
            "blocking": 1,
            "decision_weight": "high",
            "comment": "v.DCE, ao.SHFE and lu.INE event ledgers are missing.",
        },
        {
            "area": "external_selector",
            "gate": "Distinct forward collection dates",
            "actual": int(stage588.get("forward_dates", 0)),
            "required": 20,
            "progress_pct": _pct(float(stage588.get("forward_dates", 0)), 20.0),
            "status": "blocked",
            "blocking": 1,
            "decision_weight": "high",
            "comment": "Selector IC audit cannot start at 2/20 dates.",
        },
        {
            "area": "external_selector",
            "gate": "Same-family y/c tie-break frozen",
            "actual": 0,
            "required": 1,
            "progress_pct": 0.0,
            "status": "blocked",
            "blocking": 1,
            "decision_weight": "medium",
            "comment": "y/c are both route-complete but need a predeclared top1-only rule before any sleeve replay.",
        },
        {
            "area": "official_monitor",
            "gate": "Gap products with official auto monitor ready",
            "actual": 0,
            "required": 3,
            "progress_pct": 0.0,
            "status": "blocked",
            "blocking": 1,
            "decision_weight": "high",
            "comment": "v/ao/lu official pages are located, but exact parsed product monitor is not ready.",
        },
        {
            "area": "new_risk_slots",
            "gate": "Deployable new non-DCE independent risk slots",
            "actual": int(stage602.get("deployable_non_dce_new_family_slots_now", 0)),
            "required": 2,
            "progress_pct": _pct(float(stage602.get("deployable_non_dce_new_family_slots_now", 0)), 2.0),
            "status": "blocked",
            "blocking": 1,
            "decision_weight": "medium",
            "comment": "Full57 scout found no deployable non-DCE new family slot.",
        },
        {
            "area": "new_risk_slots",
            "gate": "Effective slots after DCE black_ferrous source resolution",
            "actual": int(stage601.get("effective_slots_if_black_ferrous_source_resolved", 5)),
            "required": int(stage601.get("target_effective_slots", 7)),
            "progress_pct": _pct(float(stage601.get("effective_slots_if_black_ferrous_source_resolved", 5)), float(stage601.get("target_effective_slots", 7))),
            "status": "conditional_shortfall",
            "blocking": 1,
            "decision_weight": "medium",
            "comment": "Even if j/i source is solved, the structure reaches only 5/7 slots.",
        },
    ]
    return pd.DataFrame(rows)


def _build_product_gaps() -> pd.DataFrame:
    evidence = _read_csv(STAGE588_EVIDENCE)
    official = _read_csv(STAGE595_PRODUCT_READY)
    frame = evidence.merge(
        official,
        on=["product_vt_symbol", "product_family"],
        how="left",
    )
    for col in [
        "evidence_score_0_100",
        "route_ready_count",
        "two_route_ready",
        "event_ready",
        "same_family_tiebreak_required",
        "core_corr_watch_flag",
        "official_auto_monitor_ready_rows",
        "waf_or_412_rows",
    ]:
        frame[col] = _num(frame, col)
    frame["official_auto_monitor_ready_rows"] = frame["official_auto_monitor_ready_rows"].fillna(0)
    frame["waf_or_412_rows"] = frame["waf_or_412_rows"].fillna(0)
    frame["missing_two_routes"] = (1 - frame["two_route_ready"].clip(0, 1)).astype(int)
    frame["missing_event"] = (1 - frame["event_ready"].clip(0, 1)).astype(int)
    frame["needs_tiebreak"] = frame["same_family_tiebreak_required"].clip(0, 1).astype(int)
    frame["needs_corr_watch"] = frame["core_corr_watch_flag"].clip(0, 1).astype(int)
    frame["official_monitor_missing"] = np.where(frame["product_vt_symbol"].isin(["v.DCE", "ao.SHFE", "lu.INE"]), (frame["official_auto_monitor_ready_rows"].le(0)).astype(int), 0)
    frame["gap_score"] = (
        (100.0 - frame["evidence_score_0_100"].clip(0, 100))
        + 25 * frame["missing_event"]
        + 20 * frame["missing_two_routes"]
        + 12 * frame["needs_tiebreak"]
        + 10 * frame["needs_corr_watch"]
        + 15 * frame["official_monitor_missing"]
    )
    role = []
    next_action = []
    for row in frame.itertuples(index=False):
        product = str(row.product_vt_symbol)
        if int(row.needs_tiebreak) == 1 and int(row.missing_event) == 0 and int(row.missing_two_routes) == 0:
            role.append("freeze_tiebreak_first")
            next_action.append("Freeze predeclared y/c top1-only tie-break; no replay until frozen.")
        elif int(row.missing_event) == 1 and int(row.missing_two_routes) == 0:
            role.append("event_ledger_first")
            next_action.append("Create point-in-time event/news/manual-event ledger with received_at/source_url/raw_hash.")
        elif int(row.missing_event) == 1 and int(row.missing_two_routes) == 1:
            role.append("route_and_event_first")
            next_action.append("Add forward-only basis/substitute route plus event ledger; official monitor remains non-trading evidence.")
        elif int(row.needs_corr_watch) == 1:
            role.append("corr_watch_only_after_source")
            next_action.append("Do not overweight; use only after source/event/TCA and correlation budget are proven.")
        else:
            role.append("monitor")
            next_action.append("Keep forward monitor; no promotion.")
    frame["priority_role"] = role
    frame["next_action"] = next_action
    return frame.sort_values(["gap_score", "product_vt_symbol"], ascending=[False, True]).reset_index(drop=True)


def _build_execution_gaps() -> pd.DataFrame:
    p0_close = _read_csv(STAGE583_P0_CLOSE_GATES)
    submit_plan = _read_csv(STAGE591_SUBMIT_PLAN)
    live_context = _read_csv(STAGE591_LIVE_CONTEXT)
    rows: list[dict[str, Any]] = []
    for row in p0_close.itertuples(index=False):
        required = float(getattr(row, "required_valid_samples", 3))
        valid = float(getattr(row, "valid_live_tca_samples", 0))
        remaining = float(getattr(row, "remaining_valid_samples", max(0.0, required - valid)))
        priority_score = 100 + 15 * ("hard_daily" in str(getattr(row, "watch_priority", ""))) + 10 * ("roll_old" in str(getattr(row, "risk_types", ""))) + max(0.0, float(getattr(row, "daily_order_volume_pct", 0)))
        rows.append(
            {
                "gap_type": "p0_live_tca_sample",
                "vt_symbol": str(row.vt_symbol),
                "bridge_signal_id": "",
                "watch_priority": str(row.watch_priority),
                "actual": valid,
                "required": required,
                "remaining": remaining,
                "progress_pct": _pct(valid, required),
                "priority_score": priority_score,
                "top_blockers": str(row.top_blockers),
                "next_action": "Collect mapped live fill or independent full-day minute sample with avg_fill/VWAP/shortfall/participation.",
            }
        )
    p0_submit = submit_plan.copy()
    if "watch_priority" in p0_submit.columns:
        p0_submit = p0_submit[p0_submit["watch_priority"].astype(str).str.startswith("P0", na=False)]
    missing_context = (
        live_context.groupby("bridge_signal_id", as_index=False)
        .agg(
            required_fields=("required_field", "count"),
            present_fields=("present_in_dry_run", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).sum())),
            missing_fields=("present_in_dry_run", lambda s: int((pd.to_numeric(s, errors="coerce").fillna(0) == 0).sum())),
        )
    )
    for row in missing_context.itertuples(index=False):
        rows.append(
            {
                "gap_type": "fresh_live_context",
                "vt_symbol": str(row.bridge_signal_id).split("_")[-2] if "_" in str(row.bridge_signal_id) else "",
                "bridge_signal_id": str(row.bridge_signal_id),
                "watch_priority": "pre_submit_live_context",
                "actual": float(row.present_fields),
                "required": float(row.required_fields),
                "remaining": float(row.missing_fields),
                "progress_pct": _pct(float(row.present_fields), float(row.required_fields)),
                "priority_score": 95.0,
                "top_blockers": "fresh_contract/account/position/limit/margin/operator context missing",
                "next_action": "Wire fresh live context snapshot into submit-capable adapter before any real order.",
            }
        )
    for row in p0_submit.itertuples(index=False):
        bridge_id = str(getattr(row, "bridge_signal_id", ""))
        rows.append(
            {
                "gap_type": "real_vt_orderid_mapping",
                "vt_symbol": str(getattr(row, "vt_symbol", "")),
                "bridge_signal_id": bridge_id,
                "watch_priority": str(getattr(row, "watch_priority", "")),
                "actual": 0.0,
                "required": 1.0,
                "remaining": 1.0,
                "progress_pct": 0.0,
                "priority_score": 110.0,
                "top_blockers": "send_order return vt_orderid absent by design in dry-run",
                "next_action": "Persist real vt_orderid immediately after send_order return, then join EVENT_ORDER/EVENT_TRADE/EVENT_TICK.",
            }
        )
    return pd.DataFrame(rows).sort_values(["priority_score", "remaining"], ascending=[False, False]).reset_index(drop=True)


def _build_task_priority(gate_board: pd.DataFrame, product_gaps: pd.DataFrame, execution_gaps: pd.DataFrame) -> pd.DataFrame:
    tca_remaining = int(execution_gaps.loc[execution_gaps["gap_type"].eq("p0_live_tca_sample"), "remaining"].sum())
    live_context_missing = int(execution_gaps.loc[execution_gaps["gap_type"].eq("fresh_live_context"), "remaining"].sum())
    vt_orderid_missing = int(execution_gaps.loc[execution_gaps["gap_type"].eq("real_vt_orderid_mapping"), "remaining"].sum())
    event_missing_products = int(product_gaps["missing_event"].sum())
    route_missing_products = int(product_gaps["missing_two_routes"].sum())
    rows = [
        {
            "rank": 1,
            "task": "close_execution_no_bias_loop",
            "category": "execution",
            "impact": 100,
            "effort": 75,
            "evidence": f"vt_orderid missing {vt_orderid_missing}, live context missing fields {live_context_missing}, P0 TCA remaining {tca_remaining}",
            "why_first": "This is the direct blocker for the objective: real trading must not diverge from replay.",
            "allowed_next": "dry-run/live-context plumbing and mapped evidence collection only",
        },
        {
            "rank": 2,
            "task": "freeze_yc_tiebreak_and_p0_event_ledgers",
            "category": "external_selector",
            "impact": 80,
            "effort": 55,
            "evidence": f"event missing products {event_missing_products}, route missing products {route_missing_products}, forward dates 2/20",
            "why_first": "This turns P0 from hindsight product evidence into forward-auditable selector evidence.",
            "allowed_next": "received_at/source_url/raw_hash ledgers; no historical selector replay",
        },
        {
            "rank": 3,
            "task": "official_monitor_for_v_ao_lu",
            "category": "external_selector",
            "impact": 65,
            "effort": 70,
            "evidence": "official endpoints located but auto monitor ready 0/3; WAF/412 rows remain",
            "why_first": "Fundamental data is useful only if exact product monitors can run forward.",
            "allowed_next": "parser/monitor proof; no trading signal until 20 dates and TCA",
        },
        {
            "rank": 4,
            "task": "authorized_dce_or_alternative_source_for_ji",
            "category": "new_risk_slots",
            "impact": 55,
            "effort": 85,
            "evidence": "j/i would add at most one slot: 4 -> 5, still below target 7",
            "why_first": "Useful, but not enough alone to solve single-slot concentration.",
            "allowed_next": "source authorization or stable alternative source only",
        },
        {
            "rank": 5,
            "task": "non_dce_forward_monitor_only",
            "category": "new_risk_slots",
            "impact": 35,
            "effort": 45,
            "evidence": "full57 scout found 0 deployable non-DCE new slots",
            "why_first": "Worth watching, not worth replaying or sweeping now.",
            "allowed_next": "forward source monitor only; no whitelist",
        },
    ]
    return pd.DataFrame(rows)


def _plot(gate_board: pd.DataFrame, product_gaps: pd.DataFrame, execution_gaps: pd.DataFrame, task_priority: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 11), constrained_layout=True)
    fig.suptitle("Stage603 executable critical path: execution proof is the first blocker", fontsize=16, fontweight="bold")

    ax = axes[0, 0]
    board = gate_board.copy().sort_values("progress_pct", ascending=True)
    colors = ["#2f855a" if value >= 100 else "#ed8936" if value >= 50 else "#e53e3e" for value in board["progress_pct"]]
    short_gate = {
        "Stage526 normal-cost candidate boundary": "Stage526 candidate",
        "OrderRequest dry-run payload with Stage526TCA reference": "OrderRequest contract",
        "Fresh live context before real submit": "fresh live context",
        "Real vt_orderid mapping": "real vt_orderid map",
        "P0 valid live TCA samples": "P0 TCA samples",
        "P0 products with >=2 point-in-time external routes": "P0 >=2 routes",
        "P0 products with real event/news/manual-event coverage": "P0 event ledgers",
        "Distinct forward collection dates": "forward dates",
        "Same-family y/c tie-break frozen": "y/c tiebreak",
        "Gap products with official auto monitor ready": "official monitor",
        "Deployable new non-DCE independent risk slots": "non-DCE new slots",
        "Effective slots after DCE black_ferrous source resolution": "DCE j/i conditional",
    }
    labels = [f"{row.area}: {short_gate.get(str(row.gate), str(row.gate))}" for row in board.itertuples(index=False)]
    ax.barh(labels, board["progress_pct"], color=colors)
    ax.axvline(100, color="#2f855a", linestyle="--", linewidth=1)
    ax.set_xlim(0, 110)
    ax.set_xlabel("progress to gate (%)")
    ax.set_title("Gate board")
    ax.tick_params(axis="y", labelsize=7)
    ax.grid(axis="x", alpha=0.2)

    ax = axes[0, 1]
    heat = product_gaps.set_index("product_vt_symbol")[
        ["two_route_ready", "event_ready", "basis_ready", "inventory_ready", "same_family_tiebreak_required", "core_corr_watch_flag"]
    ].copy()
    heat["same_family_tiebreak_required"] = 1 - heat["same_family_tiebreak_required"].clip(0, 1)
    heat["core_corr_watch_flag"] = 1 - heat["core_corr_watch_flag"].clip(0, 1)
    heat = heat.rename(
        columns={
            "two_route_ready": "2 routes",
            "event_ready": "event",
            "basis_ready": "basis",
            "inventory_ready": "inventory",
            "same_family_tiebreak_required": "tiebreak ok",
            "core_corr_watch_flag": "corr ok",
        }
    )
    image = ax.imshow(heat.to_numpy(dtype=float), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_yticks(np.arange(len(heat.index)))
    ax.set_yticklabels(heat.index.tolist(), fontsize=9)
    ax.set_xticks(np.arange(len(heat.columns)))
    ax.set_xticklabels(heat.columns.tolist(), rotation=25, ha="right", fontsize=8)
    ax.set_title("P0 product evidence matrix")
    for i in range(heat.shape[0]):
        for j in range(heat.shape[1]):
            ax.text(j, i, f"{heat.iloc[i, j]:.0f}", ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[1, 0]
    p0 = execution_gaps[execution_gaps["gap_type"].eq("p0_live_tca_sample")].copy()
    p0 = p0.sort_values("remaining", ascending=True)
    y = np.arange(len(p0))
    ax.barh(y, p0["actual"], color="#2f855a", label="valid")
    ax.barh(y, p0["remaining"], left=p0["actual"], color="#e53e3e", label="remaining")
    ax.set_yticks(y)
    ax.set_yticklabels(p0["vt_symbol"].tolist(), fontsize=9)
    ax.set_xlabel("samples")
    ax.set_title("P0 live TCA samples: 0/9")
    ax.legend(frameon=False, fontsize=8)
    ax.grid(axis="x", alpha=0.2)

    ax = axes[1, 1]
    tasks = task_priority.sort_values("rank", ascending=False)
    scatter = ax.scatter(tasks["effort"], tasks["impact"], s=tasks["impact"] * 7, c=tasks["rank"], cmap="viridis_r", alpha=0.85, edgecolor="white")
    for row in tasks.itertuples(index=False):
        ax.annotate(f"{int(row.rank)} {row.task}", (float(row.effort), float(row.impact)), fontsize=8, xytext=(5, 5), textcoords="offset points")
    ax.set_xlim(35, 95)
    ax.set_ylim(25, 110)
    ax.set_xlabel("effort / friction")
    ax.set_ylabel("impact on objective")
    ax.set_title("Next-action priority")
    ax.grid(alpha=0.2)
    fig.colorbar(scatter, ax=ax, fraction=0.046, pad=0.04, label="rank")

    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    gate_board: pd.DataFrame,
    product_gaps: pd.DataFrame,
    execution_gaps: pd.DataFrame,
    task_priority: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    product_cols = [
        "product_vt_symbol",
        "product_family",
        "evidence_score_0_100",
        "primary_gap",
        "priority_role",
        "gap_score",
        "next_action",
    ]
    exec_cols = [
        "gap_type",
        "vt_symbol",
        "watch_priority",
        "actual",
        "required",
        "remaining",
        "priority_score",
        "next_action",
    ]
    lines = [
        "# Stage603 executable critical path board",
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- main judgement: {decision['main_judgement']}",
        f"- promotion_allowed: `{decision['promotion_allowed']}`",
        f"- trading_whitelist_allowed: `{decision['trading_whitelist_allowed']}`",
        f"- zero_bias_claim_allowed: `{decision['zero_bias_claim_allowed']}`",
        "",
        "## Gate Board",
        "",
        _md_table(gate_board, max_rows=20),
        "",
        "## Task Priority",
        "",
        _md_table(task_priority, max_rows=10),
        "",
        "## Product Gaps",
        "",
        _md_table(product_gaps, product_cols, max_rows=10),
        "",
        "## Execution Gaps",
        "",
        _md_table(execution_gaps, exec_cols, max_rows=20),
        "",
        "## Research references",
        "",
        *[f"- {item}" for item in REFERENCE_LINKS],
        "",
        "## Output files",
        "",
        f"- gate board: `{GATE_BOARD_PATH}`",
        f"- product gaps: `{PRODUCT_GAPS_PATH}`",
        f"- execution gaps: `{EXECUTION_GAPS_PATH}`",
        f"- task priority: `{TASK_PRIORITY_PATH}`",
        f"- chart: `{CHART_PATH}`",
        f"- decision: `{DECISION_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().astimezone()
    generated_at_utc = datetime.now(timezone.utc)

    gate_board = _build_gate_board()
    product_gaps = _build_product_gaps()
    execution_gaps = _build_execution_gaps()
    task_priority = _build_task_priority(gate_board, product_gaps, execution_gaps)

    critical_blockers = int(gate_board[gate_board["decision_weight"].eq("critical") & gate_board["blocking"].eq(1)].shape[0])
    blocked_gates = int(gate_board["blocking"].sum())
    decision = {
        "stage": "Stage303",
        "script_stage": "Stage603",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at_local": generated_at.isoformat(timespec="seconds"),
        "generated_at_utc": generated_at_utc.isoformat(timespec="seconds"),
        "decision": "execution_no_bias_first_source_selector_second_no_promotion",
        "main_judgement": "Stage526仍是正常成本主候选，但目标的第一阻塞不是继续扩池或调参，而是执行无偏差证据：fresh live context、real vt_orderid mapping、P0 0/9 TCA样本。P0外生源和扩池只能排在第二层，未达闸门前禁止收益回测、白名单和A/B。",
        "blocked_gates": blocked_gates,
        "critical_blockers": critical_blockers,
        "p0_tca_valid_samples": int(execution_gaps.loc[execution_gaps["gap_type"].eq("p0_live_tca_sample"), "actual"].sum()),
        "p0_tca_required_samples": int(execution_gaps.loc[execution_gaps["gap_type"].eq("p0_live_tca_sample"), "required"].sum()),
        "real_vt_orderid_mappings": 0,
        "fresh_live_context_progress_pct": float(gate_board.loc[gate_board["gate"].eq("Fresh live context before real submit"), "progress_pct"].iloc[0]),
        "p0_products_with_two_routes": int(_read_json(STAGE588_DECISION).get("products_with_two_or_more_routes", 0)),
        "p0_products_with_event": int(_read_json(STAGE588_DECISION).get("products_with_real_event_coverage", 0)),
        "forward_dates": int(_read_json(STAGE588_DECISION).get("forward_dates", 0)),
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "zero_bias_claim_allowed": False,
        "overfit_boundary": "No return replay, no selector IC, no strategy parameter edits; only gate synthesis from frozen Stage561/583/587/588/591/595/601/602 outputs.",
        "next_step": "Work on submit-capable live context and vt_orderid/TCA mapping first; in parallel keep P0 event/source forward ledgers, but do not run selector replay.",
        "references": REFERENCE_LINKS,
    }

    gate_board.to_csv(GATE_BOARD_PATH, index=False, encoding="utf-8-sig")
    product_gaps.to_csv(PRODUCT_GAPS_PATH, index=False, encoding="utf-8-sig")
    execution_gaps.to_csv(EXECUTION_GAPS_PATH, index=False, encoding="utf-8-sig")
    task_priority.to_csv(TASK_PRIORITY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(gate_board, product_gaps, execution_gaps, task_priority)
    _write_report(gate_board, product_gaps, execution_gaps, task_priority, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
