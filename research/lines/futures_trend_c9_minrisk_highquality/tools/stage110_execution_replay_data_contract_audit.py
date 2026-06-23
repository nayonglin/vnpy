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
STAGE = "Stage110"
MODEL_TAG = "stage110_execution_replay_data_contract_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage110_c9_minrisk_execution_replay_data_contract_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage110_execution_replay_data_contract_audit"
BACKTEST_OUTPUT_DIR = REPO_DIR / "examples" / "portfolio_backtesting" / "backtest_outputs"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE068_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage068_initial_entry_tick_coverage_audit"
    / "qmt_roll_stage068_c9_minrisk_initial_entry_tick_coverage_audit_summary_"
    "stage068_initial_entry_tick_coverage_audit_v1.csv"
)
STAGE079_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage079_tqsdk_tick_manifest_transform_smoke"
    / "qmt_roll_stage079_c9_minrisk_tqsdk_tick_manifest_transform_smoke_summary_"
    "stage079_tqsdk_tick_manifest_transform_smoke_v1.csv"
)
STAGE080_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage080_tick_transform_mismatch_attribution"
    / "qmt_roll_stage080_c9_minrisk_tick_transform_mismatch_attribution_summary_"
    "stage080_tick_transform_mismatch_attribution_v1.csv"
)
STAGE103_CONTRACT_IN = (
    LINE_DIR
    / "outputs"
    / "stage103_orderflow_data_contract_audit"
    / "qmt_roll_stage103_c9_minrisk_orderflow_data_contract_audit_data_contract_"
    "stage103_orderflow_data_contract_audit_v1.csv"
)
STAGE103_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage103_orderflow_data_contract_audit"
    / "qmt_roll_stage103_c9_minrisk_orderflow_data_contract_audit_summary_"
    "stage103_orderflow_data_contract_audit_v1.csv"
)
STAGE108_RISK_IN = (
    LINE_DIR
    / "outputs"
    / "stage108_post_oi_route_reset_risk_map"
    / "qmt_roll_stage108_c9_minrisk_post_oi_route_reset_risk_map_risk_event_map_"
    "stage108_post_oi_route_reset_risk_map_v1.csv"
)
STAGE108_SCORECARD_IN = (
    LINE_DIR
    / "outputs"
    / "stage108_post_oi_route_reset_risk_map"
    / "qmt_roll_stage108_c9_minrisk_post_oi_route_reset_risk_map_route_scorecard_"
    "stage108_post_oi_route_reset_risk_map_v1.csv"
)
STAGE109_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage109_far_from_touch_preflight"
    / "qmt_roll_stage109_c9_minrisk_far_from_touch_preflight_summary_"
    "stage109_far_from_touch_preflight_v1.csv"
)

LIVE_EXECUTION_LEDGER = BACKTEST_OUTPUT_DIR / "qmt_roll_official_live_phase_d_execution_ledger.ndjson"
READONLY_TICKS = BACKTEST_OUTPUT_DIR / "qmt_roll_stage608_readonly_tick_snapshot_probe_ticks_stage608_readonly_tick_snapshot_probe_v1.csv"
READONLY_ORDERS = BACKTEST_OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_orders_stage174_ctp_vnpy_readonly_probe_v1.csv"
READONLY_TRADES = BACKTEST_OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_trades_stage174_ctp_vnpy_readonly_probe_v1.csv"
STAGE587_LIVE_TCA = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_stage587_stage526_live_tca_bridge_dry_run_live_tca_ledger_"
    "stage587_stage526_live_tca_bridge_dry_run_v1.csv"
)
STAGE586_GATES = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_stage586_live_tca_ledger_hook_readiness_gates_stage586_live_tca_ledger_hook_readiness_v1.csv"
)
STAGE615_WRITER_CONTRACT = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_stage615_event_tca_reducer_contract_audit_vt_orderid_writer_contract_"
    "stage615_event_tca_reducer_contract_audit_v1.csv"
)

ASSET_INVENTORY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_asset_inventory_{MODEL_TAG}.csv"
ROUTE_CONTRACT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_contract_reaudit_{MODEL_TAG}.csv"
GAP_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_manifest_{MODEL_TAG}.csv"
PROCUREMENT_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_procurement_manifest_{MODEL_TAG}.csv"
PROMOTION_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_data_blockers_{MODEL_TAG}.png"
ROUTE_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_contract_heatmap_{MODEL_TAG}.png"
ASSET_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_asset_inventory_chart_{MODEL_TAG}.png"
GAP_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_manifest_chart_{MODEL_TAG}.png"

CONTRACT_COLUMNS = [
    "point_in_time_timestamp",
    "historical_full_coverage",
    "same_source_with_execution",
    "subminute_or_tick_ordering",
    "top_of_book_bid_ask_depth",
    "multi_level_depth_or_queue",
    "aggressor_side_or_trade_prints",
    "raw_packet_hash_and_schema",
    "right_tail_protection_audit",
    "permission_or_license_clear",
]


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
        out = float(value)
        return None if np.isnan(out) or np.isinf(out) else out
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


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


def _safe_float(value: Any, default: float = np.nan) -> float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number) or not np.isfinite(float(number)):
        return default
    return float(number)


def _safe_int(value: Any, default: int = 0) -> int:
    number = _safe_float(value)
    return int(number) if np.isfinite(number) else default


def _count_csv_rows(path: Path) -> int:
    if not path.exists() or path.stat().st_size <= 4:
        return 0
    try:
        return int(len(pd.read_csv(path, encoding="utf-8-sig")))
    except Exception:
        return 0


def _count_ndjson_rows(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip())


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _nearest_curve_points(curve: pd.DataFrame, dates: pd.Series) -> pd.DataFrame:
    left = pd.DataFrame({"event_date": pd.to_datetime(dates, errors="coerce").dt.normalize()}).dropna()
    right = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].sort_values("date")
    return pd.merge_asof(left.sort_values("event_date"), right, left_on="event_date", right_on="date", direction="backward")


def _asset_inventory() -> pd.DataFrame:
    s068 = _read_csv(STAGE068_SUMMARY_IN).iloc[0]
    s079 = _read_csv(STAGE079_SUMMARY_IN).iloc[0]
    s080 = _read_csv(STAGE080_SUMMARY_IN).iloc[0]
    s103 = _read_csv(STAGE103_SUMMARY_IN).iloc[0]
    s109 = _read_csv(STAGE109_SUMMARY_IN).iloc[0]
    live_rows = _count_ndjson_rows(LIVE_EXECUTION_LEDGER)
    readonly_tick_rows = _count_csv_rows(READONLY_TICKS)
    readonly_order_rows = _count_csv_rows(READONLY_ORDERS)
    readonly_trade_rows = _count_csv_rows(READONLY_TRADES)
    stage587_valid = 0
    stage587_rows = 0
    if STAGE587_LIVE_TCA.exists():
        live_tca = _read_csv(STAGE587_LIVE_TCA)
        stage587_rows = len(live_tca)
        stage587_valid = int(pd.to_numeric(live_tca.get("valid_live_tca_sample", 0), errors="coerce").fillna(0).sum())
    hook_gates_pass = 0
    hook_gates_total = 0
    if STAGE586_GATES.exists():
        gates = _read_csv(STAGE586_GATES)
        hook_gates_total = len(gates)
        hook_gates_pass = int(pd.to_numeric(gates.get("passed", 0), errors="coerce").fillna(0).sum())
    writer_fields = 0
    if STAGE615_WRITER_CONTRACT.exists():
        writer_fields = int(len(_read_csv(STAGE615_WRITER_CONTRACT)))

    raw_tick_dirs = list((LINE_DIR / "outputs").glob("stage*/raw_tick"))
    raw_tick_file_count = sum(len(list(path.rglob("*.csv"))) for path in raw_tick_dirs)

    rows = [
        {
            "asset_id": "authorized_historical_quote_depth",
            "asset_family": "licensed_historical_microstructure",
            "status": "absent_locally",
            "evidence_path": "",
            "planned_count": int(s103["initial_entry_tick_planned_count"]),
            "ready_count": 0,
            "ready_rate_pct": 0.0,
            "contract_pass_rate_pct": 0.0,
            "rule_usable": 0,
            "tca_or_forward_watch_only": 0,
            "blocking_reason": "no licensed historical quote/depth/orderflow archive with raw provenance",
        },
        {
            "asset_id": "broker_or_production_execution_replay",
            "asset_family": "same_source_execution_ledger",
            "status": "not_present_for_history",
            "evidence_path": str(LIVE_EXECUTION_LEDGER),
            "planned_count": int(s103["initial_entry_tick_planned_count"]),
            "ready_count": live_rows,
            "ready_rate_pct": 0.0,
            "contract_pass_rate_pct": 0.0,
            "rule_usable": 0,
            "tca_or_forward_watch_only": 1,
            "blocking_reason": "phase-d execution ledger is missing or has no mapped historical EVENT_ORDER/EVENT_TRADE/EVENT_TICK rows",
        },
        {
            "asset_id": "ctp_readonly_forward_tick_snapshot",
            "asset_family": "forward_watch_realtime",
            "status": "code_path_exists_no_rows_now",
            "evidence_path": str(READONLY_TICKS),
            "planned_count": 1,
            "ready_count": readonly_tick_rows,
            "ready_rate_pct": float(readonly_tick_rows > 0) * 100.0,
            "contract_pass_rate_pct": 20.0 if readonly_tick_rows > 0 else 0.0,
            "rule_usable": 0,
            "tca_or_forward_watch_only": 1,
            "blocking_reason": "read-only tick file currently has no rows; forward capture cannot backfill history",
        },
        {
            "asset_id": "ctp_readonly_order_trade_callbacks",
            "asset_family": "forward_watch_execution_callbacks",
            "status": "empty_readonly_files",
            "evidence_path": f"{READONLY_ORDERS};{READONLY_TRADES}",
            "planned_count": 2,
            "ready_count": readonly_order_rows + readonly_trade_rows,
            "ready_rate_pct": float(readonly_order_rows + readonly_trade_rows > 0) * 100.0,
            "contract_pass_rate_pct": 0.0,
            "rule_usable": 0,
            "tca_or_forward_watch_only": 1,
            "blocking_reason": "no mapped order/trade callback rows available for this research line",
        },
        {
            "asset_id": "stage068_initial_entry_tq_tick_archive",
            "asset_family": "local_tq_tick_initial_entry",
            "status": "partial_ready_downgraded",
            "evidence_path": str(STAGE068_SUMMARY_IN),
            "planned_count": int(s068["planned_initial_entry_count"]),
            "ready_count": int(s068["microstructure_ready_count"]),
            "ready_rate_pct": float(s068["coverage_ready_rate_pct"]),
            "contract_pass_rate_pct": 30.0,
            "rule_usable": 0,
            "tca_or_forward_watch_only": 1,
            "blocking_reason": "only 5/219 initial entries ready and anchor price exact count is zero",
        },
        {
            "asset_id": "stage079_tq_dur0_transform_smoke",
            "asset_family": "local_tq_tick_transform",
            "status": "small_manifest_mixed",
            "evidence_path": str(STAGE079_SUMMARY_IN),
            "planned_count": int(s079["manifest_size"]),
            "ready_count": int(s079["target_tick_ready_count"]),
            "ready_rate_pct": 100.0,
            "contract_pass_rate_pct": 30.0,
            "rule_usable": int(s079["rule_candidate_allowed_count"]),
            "tca_or_forward_watch_only": 1,
            "blocking_reason": "same-source transform verified for only 8/28; no rule candidate allowed",
        },
        {
            "asset_id": "stage080_tq_transform_union",
            "asset_family": "local_tq_tick_transform",
            "status": "closed_for_rules",
            "evidence_path": str(STAGE080_SUMMARY_IN),
            "planned_count": int(s080["manifest_size"]),
            "ready_count": int(s080["first_tick_state_union_exact_count"]),
            "ready_rate_pct": 100.0 * float(s080["first_tick_state_union_exact_count"]) / max(float(s080["manifest_size"]), 1.0),
            "contract_pass_rate_pct": 30.0,
            "rule_usable": int(s080["rule_candidate_allowed_count"]),
            "tca_or_forward_watch_only": 1,
            "blocking_reason": "Tq transform union downgraded to TCA; no unified topbook transform",
        },
        {
            "asset_id": "stage587_live_tca_bridge_dry_run",
            "asset_family": "dry_run_execution_tca_contract",
            "status": "contract_only_no_live_samples",
            "evidence_path": str(STAGE587_LIVE_TCA),
            "planned_count": stage587_rows,
            "ready_count": stage587_valid,
            "ready_rate_pct": 100.0 * stage587_valid / max(stage587_rows, 1),
            "contract_pass_rate_pct": 20.0 if stage587_rows else 0.0,
            "rule_usable": 0,
            "tca_or_forward_watch_only": 1,
            "blocking_reason": "valid live TCA sample count is zero; dry-run only",
        },
        {
            "asset_id": "stage586_615_event_hook_contracts",
            "asset_family": "code_capability_contract",
            "status": "code_contract_exists_data_absent",
            "evidence_path": f"{STAGE586_GATES};{STAGE615_WRITER_CONTRACT}",
            "planned_count": hook_gates_total + writer_fields,
            "ready_count": hook_gates_pass + writer_fields,
            "ready_rate_pct": 100.0 * (hook_gates_pass + writer_fields) / max(hook_gates_total + writer_fields, 1),
            "contract_pass_rate_pct": 20.0,
            "rule_usable": 0,
            "tca_or_forward_watch_only": 1,
            "blocking_reason": "framework/event hooks exist, but no historical replay rows or natural live sample depth",
        },
        {
            "asset_id": "local_raw_tick_dirs_in_line",
            "asset_family": "local_file_inventory",
            "status": "files_exist_but_closed_by_stage080",
            "evidence_path": str(LINE_DIR / "outputs"),
            "planned_count": len(raw_tick_dirs),
            "ready_count": raw_tick_file_count,
            "ready_rate_pct": np.nan,
            "contract_pass_rate_pct": 0.0,
            "rule_usable": 0,
            "tca_or_forward_watch_only": 1,
            "blocking_reason": "raw tick files are route-specific artifacts; previous stability gates closed them for rules",
        },
        {
            "asset_id": "stage109_internal_ohlc_candidate",
            "asset_family": "internal_minute_ohlc",
            "status": "closed",
            "evidence_path": str(STAGE109_SUMMARY_IN),
            "planned_count": int(s109["timestamp_ready_order_count"]),
            "ready_count": int(s109["frozen_far_from_touch_proxy_order_count"]),
            "ready_rate_pct": 100.0 * float(s109["frozen_far_from_touch_proxy_order_count"]) / float(s109["timestamp_ready_order_count"]),
            "contract_pass_rate_pct": 0.0,
            "rule_usable": 0,
            "tca_or_forward_watch_only": 0,
            "blocking_reason": "far-from-touch proxy degenerates to elapsed no-touch/no-progress",
        },
    ]
    frame = pd.DataFrame(rows)
    frame["ready_rate_pct"] = pd.to_numeric(frame["ready_rate_pct"], errors="coerce")
    frame["contract_pass_rate_pct"] = pd.to_numeric(frame["contract_pass_rate_pct"], errors="coerce").fillna(0.0)
    return frame


def _route_contract_reaudit(asset: pd.DataFrame) -> pd.DataFrame:
    contract = _read_csv(STAGE103_CONTRACT_IN).copy()
    for column in CONTRACT_COLUMNS:
        contract[column] = pd.to_numeric(contract[column], errors="coerce").fillna(0).astype(int)
    contract["stage110_current_state"] = contract["route_id"].map(
        {
            "authorized_historical_quote_depth": "still_absent_locally",
            "broker_or_production_execution_replay": "live_ledger_missing_or_no_history_rows",
            "ctp_realtime_forward_capture": "code_path_exists_but_not_historical",
            "minute_ohlc_far_from_touch_candidate": "closed_by_stage109",
            "local_tq_initial_entry_tick_archive": "partial_5_of_219_only",
            "local_tq_transform_union": "closed_by_stage080",
        }
    ).fillna("not_reaudited")
    contract["stage110_rule_allowed_now"] = 0
    contract["stage110_true_engine_allowed_now"] = 0
    contract["stage110_ab_allowed_now"] = 0
    contract["stage110_contract_pass_count"] = contract[CONTRACT_COLUMNS].sum(axis=1)
    contract["stage110_contract_pass_rate_pct"] = (
        100.0 * contract["stage110_contract_pass_count"] / len(CONTRACT_COLUMNS)
    )
    return contract


def _gap_manifest(route: pd.DataFrame, asset: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "gap_id": "licensed_historical_quote_depth_absent",
            "gap_family": "historical_microstructure",
            "evidence_value": 0,
            "required_value": "quote/depth/trade archive covering 2018-2026 C9 orders",
            "severity": "hard",
            "next_action": "procure or import licensed historical quote/depth/orderflow with raw hash and schema",
        },
        {
            "gap_id": "same_source_execution_replay_absent",
            "gap_family": "execution_ledger",
            "evidence_value": int(asset.loc[asset["asset_id"].eq("broker_or_production_execution_replay"), "ready_count"].iloc[0]),
            "required_value": "mapped vt_orderid + EVENT_ORDER/EVENT_TRADE/EVENT_TICK rows for all relevant orders",
            "severity": "hard",
            "next_action": "export broker/production execution replay or build forward capture ledger before rule research",
        },
        {
            "gap_id": "initial_entry_tick_coverage_too_low",
            "gap_family": "local_tq_tick",
            "evidence_value": 5,
            "required_value": ">=95% timestamp-ready initial entries and right-tail/bottom-loss coverage",
            "severity": "hard",
            "next_action": "do not use local Tq tick for rules; keep only TCA/diagnostic usage",
        },
        {
            "gap_id": "internal_ohlc_route_closed",
            "gap_family": "minute_ohlc",
            "evidence_value": 105,
            "required_value": "new independent signal not overlapping elapsed no-touch/no-progress",
            "severity": "hard",
            "next_action": "stop internal OHLC candidate generation until new data exists",
        },
        {
            "gap_id": "raw_provenance_missing_for_rule_replay",
            "gap_family": "provenance",
            "evidence_value": int(route["raw_packet_hash_and_schema"].sum()),
            "required_value": "raw_file, raw_sha256, schema_hash, query params, vendor/license for replay rows",
            "severity": "hard",
            "next_action": "define raw provenance manifest before any feature binding",
        },
        {
            "gap_id": "right_tail_protection_not_proven_for_microstructure",
            "gap_family": "right_tail_gate",
            "evidence_value": int(route["right_tail_protection_audit"].sum()),
            "required_value": "visual coverage of right-tail and bottom-loss samples under same data source",
            "severity": "hard",
            "next_action": "after data import, rerun right-tail protection and bottom-loss separation charts",
        },
    ]
    return pd.DataFrame(rows)


def _procurement_manifest() -> pd.DataFrame:
    rows = [
        {
            "route_id": "authorized_historical_quote_depth",
            "priority": 1,
            "required_fields": "vt_symbol, exchange, exchange_timestamp, receive_timestamp, bid_price_1..5, ask_price_1..5, bid_volume_1..5, ask_volume_1..5, last_price, trade_volume_delta, turnover_delta, open_interest, session_id",
            "required_coverage": "all C9 timestamp-ready and fallback initial/retry/stop/progress windows from 2018-2026",
            "required_provenance": "raw_file, raw_sha256, schema_hash, query_params, vendor_or_exchange_license, timezone, calendar_version",
            "acceptance_gate": ">=95% order-window coverage plus 100% selected right-tail/bottom-loss visual audit",
            "rule_research_allowed_after_gate": 0,
        },
        {
            "route_id": "broker_or_production_execution_replay",
            "priority": 2,
            "required_fields": "signal_id, order_reference, vt_orderid, order_submit_at, order_type, limit_price, status_times, fill_first_at, fill_last_at, avg_fill_price, filled_volume, unfilled_volume, cancelled_volume, commission, account_equity_before, margin_before",
            "required_coverage": "mapped execution lifecycle for all live/paper-forward strategy orders; historical broker export if available",
            "required_provenance": "broker_export_file, export_time, account_id_hash, gateway_name, raw_sha256, reducer_version",
            "acceptance_gate": "bridge_signal_id -> vt_orderid -> EVENT_ORDER/EVENT_TRADE/EVENT_TICK join has valid samples and no missing critical fields",
            "rule_research_allowed_after_gate": 0,
        },
        {
            "route_id": "ctp_forward_capture",
            "priority": 3,
            "required_fields": "EVENT_TICK topbook snapshots, EVENT_ORDER status rows, EVENT_TRADE fills, account/position snapshots, contract metadata, heartbeat",
            "required_coverage": "natural forward samples across sessions/products before predictive audit",
            "required_provenance": "local env fingerprint, gateway name, capture script version, event raw rows, raw_sha256",
            "acceptance_gate": "fresh read-only tick rows >0, order/trade callback rows mapped to simulated or live test intent, then accumulated OOS depth",
            "rule_research_allowed_after_gate": 0,
        },
    ]
    return pd.DataFrame(rows)


def _promotion_gate(asset: pd.DataFrame, route: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "gate_id": "authorized_historical_quote_depth_ready",
            "evidence_value": int(asset.loc[asset["asset_id"].eq("authorized_historical_quote_depth"), "ready_count"].iloc[0]),
            "required": "nonzero licensed historical archive with provenance",
            "pass_for_true_engine": 0,
            "judgment": "blocked_absent_locally",
        },
        {
            "gate_id": "broker_execution_replay_ready",
            "evidence_value": int(asset.loc[asset["asset_id"].eq("broker_or_production_execution_replay"), "ready_count"].iloc[0]),
            "required": "mapped EVENT_ORDER/EVENT_TRADE/EVENT_TICK rows",
            "pass_for_true_engine": 0,
            "judgment": "blocked_no_replay_rows",
        },
        {
            "gate_id": "local_tq_tick_not_rule_ready",
            "evidence_value": int(asset.loc[asset["asset_id"].eq("stage068_initial_entry_tq_tick_archive"), "ready_count"].iloc[0]),
            "required": ">=95% coverage and same-source execution",
            "pass_for_true_engine": 0,
            "judgment": "blocked_partial_coverage_and_stage080_downgrade",
        },
        {
            "gate_id": "internal_ohlc_candidate_closed",
            "evidence_value": int(asset.loc[asset["asset_id"].eq("stage109_internal_ohlc_candidate"), "ready_count"].iloc[0]),
            "required": "independent non-overlapping signal",
            "pass_for_true_engine": 0,
            "judgment": "blocked_by_stage109",
        },
        {
            "gate_id": "any_route_true_engine_allowed",
            "evidence_value": int(route["stage110_true_engine_allowed_now"].sum()),
            "required": ">=1",
            "pass_for_true_engine": 0,
            "judgment": "blocked_no_route_allowed",
        },
    ]
    gate = pd.DataFrame(rows)
    gate["strategy_feature_usable"] = 0
    return gate


def _summary(
    asset: pd.DataFrame,
    route: pd.DataFrame,
    gap: pd.DataFrame,
    procurement: pd.DataFrame,
    gate: pd.DataFrame,
) -> pd.DataFrame:
    s103 = _read_csv(STAGE103_SUMMARY_IN).iloc[0]
    s109 = _read_csv(STAGE109_SUMMARY_IN).iloc[0]
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": "stage110_execution_replay_data_contract_not_ready_no_rule",
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "asset_count": int(len(asset)),
                "rule_usable_asset_count": int(pd.to_numeric(asset["rule_usable"], errors="coerce").fillna(0).sum()),
                "tca_or_forward_watch_only_asset_count": int(
                    pd.to_numeric(asset["tca_or_forward_watch_only"], errors="coerce").fillna(0).sum()
                ),
                "route_count": int(len(route)),
                "route_true_engine_allowed_count": int(route["stage110_true_engine_allowed_now"].sum()),
                "authorized_historical_quote_depth_ready_count": int(
                    asset.loc[asset["asset_id"].eq("authorized_historical_quote_depth"), "ready_count"].iloc[0]
                ),
                "broker_execution_replay_row_count": int(
                    asset.loc[asset["asset_id"].eq("broker_or_production_execution_replay"), "ready_count"].iloc[0]
                ),
                "readonly_tick_row_count": int(
                    asset.loc[asset["asset_id"].eq("ctp_readonly_forward_tick_snapshot"), "ready_count"].iloc[0]
                ),
                "stage068_initial_entry_tick_ready_count": int(s103["initial_entry_tick_ready_count"]),
                "stage068_initial_entry_tick_ready_rate_pct": float(s103["initial_entry_tick_ready_rate_pct"]),
                "stage109_internal_ohlc_closed": 1,
                "hard_gap_count": int(gap["severity"].eq("hard").sum()),
                "procurement_route_count": int(len(procurement)),
                "promotion_gate_count": int(len(gate)),
                "promotion_gate_pass_count": int(pd.to_numeric(gate["pass_for_true_engine"], errors="coerce").sum()),
                "next_recommended_route": "procure_authorized_quote_depth_or_broker_execution_replay",
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "end_equity": float(s109["end_equity"]),
                "total_return_pct": float(s109["total_return_pct"]),
                "max_drawdown_pct": float(s109["max_drawdown_pct"]),
                "sharpe": float(s109["sharpe"]),
                "total_slippage": float(s109["total_slippage"]),
                "total_trade_count": float(s109["total_trade_count"]),
                "closed_lot_win_rate_pct": float(s109["closed_lot_win_rate_pct"]),
                "max_broker10_margin_to_equity_pct": float(s109["max_broker10_margin_to_equity_pct"]),
            }
        ]
    )


def _plot_path(curve: pd.DataFrame, risk: pd.DataFrame) -> None:
    risk = risk.copy()
    risk["official_open_date"] = pd.to_datetime(risk["official_open_date"], errors="coerce").dt.normalize()
    risk = risk.drop(
        columns=[
            column
            for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]
            if column in risk.columns
        ]
    )
    points = _nearest_curve_points(curve, risk["official_open_date"])
    risk = risk.sort_values("official_open_date").reset_index(drop=True)
    points = points.reset_index(drop=True)
    if len(risk) == len(points):
        risk = pd.concat(
            [risk, points[["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]]],
            axis=1,
        )
    selected = risk[risk["bottom_loss_visual"].eq(1) | risk["right_tail_visual"].eq(1) | risk["maxdd_context"].eq(1)]
    fig, axes = plt.subplots(3, 1, figsize=(15, 10), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#111827", lw=1.2)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#b91c1c", lw=1.0)
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#0369a1", lw=1.0)
    axes[2].axhline(100, color="#991b1b", ls="--", lw=0.8)
    for label, group in selected.groupby("risk_route_label"):
        color = "#dc2626" if "blocked" in str(label) else "#0f766e"
        size = np.where(group["bottom_loss_visual"].eq(1), 84, 44)
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
    axes[0].legend(loc="upper left", fontsize=8)
    axes[0].set_title("Stage110 official path with data-contract blockers; no route true-engine ready")
    axes[0].set_ylabel("equity (m)")
    axes[1].set_ylabel("drawdown %")
    axes[2].set_ylabel("broker10 %")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_route_heatmap(route: pd.DataFrame) -> None:
    matrix = route.set_index("route_id")[CONTRACT_COLUMNS]
    fig, ax = plt.subplots(figsize=(13, max(5.5, 0.55 * len(matrix))))
    image = ax.imshow(matrix.to_numpy(dtype=float), vmin=0, vmax=1, cmap="RdYlGn", aspect="auto")
    ax.set_xticks(range(len(CONTRACT_COLUMNS)))
    ax.set_xticklabels(CONTRACT_COLUMNS, rotation=28, ha="right")
    ax.set_yticks(range(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    for y in range(len(matrix.index)):
        for x in range(len(CONTRACT_COLUMNS)):
            ax.text(x, y, str(int(matrix.iloc[y, x])), ha="center", va="center", fontsize=8)
    ax.set_title("Stage110 route contract reaudit: green 1 means evidence exists, but true_engine_allowed remains 0")
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(ROUTE_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_asset_chart(asset: pd.DataFrame) -> None:
    data = asset.sort_values(["rule_usable", "contract_pass_rate_pct", "ready_rate_pct"], ascending=[True, True, True]).copy()
    fig, ax = plt.subplots(figsize=(13, max(5.5, 0.48 * len(data))))
    colors = np.where(data["rule_usable"].eq(1), "#16a34a", np.where(data["tca_or_forward_watch_only"].eq(1), "#f97316", "#dc2626"))
    ax.barh(data["asset_id"], data["contract_pass_rate_pct"], color=colors, alpha=0.86)
    for y, row in enumerate(data.itertuples(index=False)):
        ready = "" if pd.isna(row.ready_rate_pct) else f" ready {row.ready_rate_pct:.1f}%"
        ax.text(row.contract_pass_rate_pct + 1, y, f"{row.status}{ready}", va="center", fontsize=8)
    ax.set_xlim(0, 105)
    ax.set_xlabel("contract pass rate %")
    ax.set_title("Stage110 local asset inventory; orange is TCA/forward-watch only")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(ASSET_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_gap_chart(gap: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 5.5))
    frame = gap.copy()
    frame["blocked"] = 1
    ax.barh(frame["gap_id"], frame["blocked"], color="#dc2626", alpha=0.86)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("blocked")
    ax.set_title("Stage110 hard gaps before microstructure rule research")
    for y, row in enumerate(frame.itertuples(index=False)):
        ax.text(0.03, y, str(row.gap_family), color="white", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(GAP_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    asset: pd.DataFrame,
    route: pd.DataFrame,
    gap: pd.DataFrame,
    procurement: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    lines = [
        "# Stage110 execution replay data contract audit",
        "",
        "## Decision",
        "",
        f"- decision: `{row['decision']}`",
        "- nature: read-only data-contract audit; no strategy rule, no true engine, no A/B, no CTP connection, no order API.",
        "- frozen question: after Stage109 closes internal minute-OHLC candidates, does the current workspace already contain enough authorized quote/depth or broker execution replay data to resume rule research?",
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
        "## Key Metrics",
        "",
        _md_table(summary),
        "",
        "## Asset Inventory",
        "",
        _md_table(asset, max_rows=30),
        "",
        "## Route Contract Reaudit",
        "",
        _md_table(
            route[
                [
                    "route_id",
                    "stage110_current_state",
                    "stage110_contract_pass_count",
                    "stage110_contract_pass_rate_pct",
                    "stage110_true_engine_allowed_now",
                ]
                + CONTRACT_COLUMNS
            ],
            max_rows=20,
        ),
        "",
        "## Gap Manifest",
        "",
        _md_table(gap, max_rows=20),
        "",
        "## Procurement Manifest",
        "",
        _md_table(procurement, max_rows=10),
        "",
        "## Promotion Gates",
        "",
        _md_table(gate, max_rows=20),
        "",
        "## Visual Outputs",
        "",
        f"- official path data blockers: `{PATH_CHART_OUT}`",
        f"- route contract heatmap: `{ROUTE_HEATMAP_OUT}`",
        f"- asset inventory chart: `{ASSET_CHART_OUT}`",
        f"- gap manifest chart: `{GAP_CHART_OUT}`",
        "",
        "## Judgment",
        "",
        (
            "The workspace has code paths and small diagnostic tick assets, but not the historical or same-source execution replay "
            "data required for a robust minute entry/exit rule. Local Tq tick routes remain TCA/forward-watch only, the official "
            "phase-D execution ledger has no mapped historical rows, and the read-only tick snapshot file is empty. The next valid "
            "research move is data import/procurement or forward capture, not a new OHLC strategy candidate."
        ),
        "",
    ]
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    risk = _read_csv(STAGE108_RISK_IN)
    asset = _asset_inventory()
    route = _route_contract_reaudit(asset)
    gap = _gap_manifest(route, asset)
    procurement = _procurement_manifest()
    gate = _promotion_gate(asset, route)
    summary = _summary(asset, route, gap, procurement, gate)

    _write_csv(asset, ASSET_INVENTORY_OUT)
    _write_csv(route, ROUTE_CONTRACT_OUT)
    _write_csv(gap, GAP_MANIFEST_OUT)
    _write_csv(procurement, PROCUREMENT_MANIFEST_OUT)
    _write_csv(gate, PROMOTION_GATE_OUT)
    _write_csv(summary, SUMMARY_OUT)

    _plot_path(curve, risk)
    _plot_route_heatmap(route)
    _plot_asset_chart(asset)
    _plot_gap_chart(gap)
    _write_report(summary, asset, route, gap, procurement, gate)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": str(summary.iloc[0]["decision"]),
        "summary_path": str(SUMMARY_OUT),
        "report_path": str(REPORT_OUT),
        "asset_inventory_path": str(ASSET_INVENTORY_OUT),
        "route_contract_path": str(ROUTE_CONTRACT_OUT),
        "gap_manifest_path": str(GAP_MANIFEST_OUT),
        "procurement_manifest_path": str(PROCUREMENT_MANIFEST_OUT),
        "promotion_gate_path": str(PROMOTION_GATE_OUT),
        "charts": [str(PATH_CHART_OUT), str(ROUTE_HEATMAP_OUT), str(ASSET_CHART_OUT), str(GAP_CHART_OUT)],
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
