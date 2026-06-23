from __future__ import annotations

from dataclasses import fields
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
STAGE = "Stage103"
MODEL_TAG = "stage103_orderflow_data_contract_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage103_c9_minrisk_orderflow_data_contract_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOLS_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for path in [str(TOOLS_DIR), str(EXAMPLE_DIR), str(REPO_DIR)]:
    if path not in sys.path:
        sys.path.insert(0, path)

import stage038_order_event_replay_prototype_audit as s038  # noqa: E402
from vnpy.trader.object import TickData  # noqa: E402


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage103_orderflow_data_contract_audit"

STAGE068_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage068_initial_entry_tick_coverage_audit"
    / "qmt_roll_stage068_c9_minrisk_initial_entry_tick_coverage_audit_summary_"
    "stage068_initial_entry_tick_coverage_audit_v1.csv"
)
STAGE080_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage080_tick_transform_mismatch_attribution"
    / "qmt_roll_stage080_c9_minrisk_tick_transform_mismatch_attribution_summary_"
    "stage080_tick_transform_mismatch_attribution_v1.csv"
)
STAGE099_MANIFEST_IN = (
    LINE_DIR
    / "outputs"
    / "stage099_finer_source_feasibility_manifest"
    / "qmt_roll_stage099_c9_minrisk_finer_source_feasibility_manifest_manifest_"
    "stage099_finer_source_feasibility_manifest_v1.csv"
)
STAGE102_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage102_bar_resolution_frontier_audit"
    / "qmt_roll_stage102_c9_minrisk_bar_resolution_frontier_audit_summary_"
    "stage102_bar_resolution_frontier_audit_v1.csv"
)

LOCAL_ASSET_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_local_asset_audit_{MODEL_TAG}.csv"
DATA_CONTRACT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_data_contract_{MODEL_TAG}.csv"
ACTION_QUEUE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_action_queue_{MODEL_TAG}.csv"
PROMOTION_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

OFFICIAL_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_data_route_chart_{MODEL_TAG}.png"
READINESS_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readiness_heatmap_{MODEL_TAG}.png"
ACTION_QUEUE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_action_queue_chart_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_chart_{MODEL_TAG}.png"


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
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, float):
        if np.isnan(value) or np.isinf(value):
            return None
        return value
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


def _safe_int(value: Any, default: int = 0) -> int:
    number = _safe_float(value)
    return int(number) if np.isfinite(number) else default


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s038._md_table(frame, max_rows=max_rows)


def _tick_field_audit() -> dict[str, Any]:
    field_names = [item.name for item in fields(TickData)]
    bid_price = [name for name in field_names if name.startswith("bid_price_")]
    ask_price = [name for name in field_names if name.startswith("ask_price_")]
    bid_volume = [name for name in field_names if name.startswith("bid_volume_")]
    ask_volume = [name for name in field_names if name.startswith("ask_volume_")]
    return {
        "vnpy_tick_field_count": len(field_names),
        "vnpy_bid_price_level_count": len(bid_price),
        "vnpy_ask_price_level_count": len(ask_price),
        "vnpy_bid_volume_level_count": len(bid_volume),
        "vnpy_ask_volume_level_count": len(ask_volume),
        "vnpy_has_last_price": int("last_price" in field_names),
        "vnpy_has_volume": int("volume" in field_names),
        "vnpy_has_turnover": int("turnover" in field_names),
        "vnpy_has_open_interest": int("open_interest" in field_names),
    }


def _local_asset_audit() -> pd.DataFrame:
    s068 = _read_csv(STAGE068_SUMMARY_IN).iloc[0]
    s080 = _read_csv(STAGE080_SUMMARY_IN).iloc[0]
    s102 = _read_csv(STAGE102_SUMMARY_IN).iloc[0]
    tick = _tick_field_audit()
    stage066_raw = LINE_DIR / "outputs" / "stage066_tick_microstructure_expansion_attempt" / "raw_tick"
    stage079_raw = LINE_DIR / "outputs" / "stage079_tqsdk_tick_manifest_transform_smoke" / "raw_tick"
    stage068_raw = LINE_DIR / "outputs" / "stage068_initial_entry_tick_coverage_audit" / "raw_tick"
    rows = [
        {
            "asset_id": "stage068_initial_entry_tick_coverage",
            "asset_family": "local_tq_tick_initial_entry",
            "evidence_path": str(STAGE068_SUMMARY_IN),
            "current_status": "download_required_partial_coverage",
            "planned_event_count": _safe_int(s068.get("planned_initial_entry_count")),
            "ready_event_count": _safe_int(s068.get("microstructure_ready_count")),
            "missing_event_count": _safe_int(s068.get("microstructure_missing_count")),
            "coverage_ready_rate_pct": _safe_float(s068.get("coverage_ready_rate_pct")),
            "rule_usable": 0,
            "tca_or_forward_watch_only": 1,
            "note": "initial-entry tick coverage is too sparse for rule research",
        },
        {
            "asset_id": "stage080_tq_tick_transform_mismatch",
            "asset_family": "local_tq_tick_same_source_gate",
            "evidence_path": str(STAGE080_SUMMARY_IN),
            "current_status": "downgraded_to_tca_no_rule",
            "planned_event_count": _safe_int(s080.get("manifest_size")),
            "ready_event_count": _safe_int(s080.get("first_tick_state_union_exact_count")),
            "missing_event_count": _safe_int(s080.get("topbook_or_spread_miss_count")),
            "coverage_ready_rate_pct": np.nan,
            "rule_usable": _safe_int(s080.get("rule_candidate_allowed_count")),
            "tca_or_forward_watch_only": 1,
            "note": str(s080.get("decision")),
        },
        {
            "asset_id": "stage102_bar_resolution_boundary",
            "asset_family": "minute_ohlc_execution_boundary",
            "evidence_path": str(STAGE102_SUMMARY_IN),
            "current_status": "near_touch_ohlc_blocked",
            "planned_event_count": _safe_int(s102.get("timestamp_ready_order_count")),
            "ready_event_count": _safe_int(s102.get("low_resolution_order_count")),
            "missing_event_count": 0,
            "coverage_ready_rate_pct": np.nan,
            "rule_usable": 0,
            "tca_or_forward_watch_only": 0,
            "note": "low-resolution OHLC zone contains both right-tail and bottom-loss orders",
        },
        {
            "asset_id": "vnpy_tick_schema",
            "asset_family": "realtime_capture_schema",
            "evidence_path": "vnpy.trader.object.TickData",
            "current_status": "schema_supports_topbook_snapshot",
            "planned_event_count": 0,
            "ready_event_count": tick["vnpy_tick_field_count"],
            "missing_event_count": 0,
            "coverage_ready_rate_pct": np.nan,
            "rule_usable": 0,
            "tca_or_forward_watch_only": 1,
            "note": (
                f"bid/ask levels price={tick['vnpy_bid_price_level_count']}/"
                f"{tick['vnpy_ask_price_level_count']}, volume={tick['vnpy_bid_volume_level_count']}/"
                f"{tick['vnpy_ask_volume_level_count']}; schema alone is not historical coverage"
            ),
        },
        {
            "asset_id": "stage066_reentry_raw_tick_files",
            "asset_family": "local_tq_tick_reentry_archive",
            "evidence_path": str(stage066_raw),
            "current_status": "archive_exists_but_reentry_route_failed",
            "planned_event_count": 0,
            "ready_event_count": len(list(stage066_raw.rglob("*.csv"))) if stage066_raw.exists() else 0,
            "missing_event_count": 0,
            "coverage_ready_rate_pct": np.nan,
            "rule_usable": 0,
            "tca_or_forward_watch_only": 1,
            "note": "reentry microstructure stability failed at Stage067",
        },
        {
            "asset_id": "stage079_dur0_raw_tick_files",
            "asset_family": "local_tq_tick_transform_smoke",
            "evidence_path": str(stage079_raw),
            "current_status": "transform_smoke_only",
            "planned_event_count": 0,
            "ready_event_count": len(list(stage079_raw.rglob("*.csv"))) if stage079_raw.exists() else 0,
            "missing_event_count": 0,
            "coverage_ready_rate_pct": np.nan,
            "rule_usable": 0,
            "tca_or_forward_watch_only": 1,
            "note": "Tq dur0 route closed by Stage080",
        },
        {
            "asset_id": "stage068_initial_entry_raw_tick_files",
            "asset_family": "local_tq_tick_initial_entry_archive",
            "evidence_path": str(stage068_raw),
            "current_status": "small_initial_entry_archive",
            "planned_event_count": 0,
            "ready_event_count": len(list(stage068_raw.rglob("*.csv"))) if stage068_raw.exists() else 0,
            "missing_event_count": 0,
            "coverage_ready_rate_pct": np.nan,
            "rule_usable": 0,
            "tca_or_forward_watch_only": 1,
            "note": "local archive exists but not enough to repair coverage/provenance",
        },
    ]
    return pd.DataFrame(rows)


def _data_contract(local_assets: pd.DataFrame) -> pd.DataFrame:
    stage068 = local_assets[local_assets["asset_id"].eq("stage068_initial_entry_tick_coverage")].iloc[0]
    stage080 = local_assets[local_assets["asset_id"].eq("stage080_tq_tick_transform_mismatch")].iloc[0]
    rows = [
        {
            "route_id": "authorized_historical_quote_depth",
            "route_family": "procurement_required_microstructure",
            "current_evidence": "not present locally",
            "next_action": "procure licensed historical tick/quote/depth archive with raw packet hash",
            "priority": 1,
            "expected_information_gain": 5,
            "implementation_friction": 5,
            "permission_friction": 5,
            "rule_allowed_now": 0,
            "true_engine_allowed_now": 0,
            "ab_allowed_now": 0,
            "point_in_time_timestamp": 0,
            "historical_full_coverage": 0,
            "same_source_with_execution": 0,
            "subminute_or_tick_ordering": 0,
            "top_of_book_bid_ask_depth": 0,
            "multi_level_depth_or_queue": 0,
            "aggressor_side_or_trade_prints": 0,
            "raw_packet_hash_and_schema": 0,
            "right_tail_protection_audit": 0,
            "permission_or_license_clear": 0,
        },
        {
            "route_id": "broker_or_production_execution_replay",
            "route_family": "same_source_execution_ledger",
            "current_evidence": "not present locally",
            "next_action": "export broker-side tick/quote and execution timestamp ledger for all timestamp-ready/fallback orders",
            "priority": 2,
            "expected_information_gain": 5,
            "implementation_friction": 4,
            "permission_friction": 4,
            "rule_allowed_now": 0,
            "true_engine_allowed_now": 0,
            "ab_allowed_now": 0,
            "point_in_time_timestamp": 0,
            "historical_full_coverage": 0,
            "same_source_with_execution": 0,
            "subminute_or_tick_ordering": 0,
            "top_of_book_bid_ask_depth": 0,
            "multi_level_depth_or_queue": 0,
            "aggressor_side_or_trade_prints": 0,
            "raw_packet_hash_and_schema": 0,
            "right_tail_protection_audit": 0,
            "permission_or_license_clear": 0,
        },
        {
            "route_id": "ctp_realtime_forward_capture",
            "route_family": "forward_watch_realtime",
            "current_evidence": "vn.py TickData schema supports topbook snapshot fields",
            "next_action": "build forward ledger only; wait for enough natural days before predictive audit",
            "priority": 3,
            "expected_information_gain": 3,
            "implementation_friction": 2,
            "permission_friction": 2,
            "rule_allowed_now": 0,
            "true_engine_allowed_now": 0,
            "ab_allowed_now": 0,
            "point_in_time_timestamp": 0,
            "historical_full_coverage": 0,
            "same_source_with_execution": 0,
            "subminute_or_tick_ordering": 0,
            "top_of_book_bid_ask_depth": 1,
            "multi_level_depth_or_queue": 0,
            "aggressor_side_or_trade_prints": 0,
            "raw_packet_hash_and_schema": 0,
            "right_tail_protection_audit": 0,
            "permission_or_license_clear": 1,
        },
        {
            "route_id": "local_tq_initial_entry_tick_archive",
            "route_family": "local_proxy_tca_only",
            "current_evidence": f"Stage068 ready {stage068['ready_event_count']}/{stage068['planned_event_count']}",
            "next_action": "do not use for rules; only TCA/forward-watch diagnostics",
            "priority": 5,
            "expected_information_gain": 2,
            "implementation_friction": 1,
            "permission_friction": 2,
            "rule_allowed_now": 0,
            "true_engine_allowed_now": 0,
            "ab_allowed_now": 0,
            "point_in_time_timestamp": 1,
            "historical_full_coverage": 0,
            "same_source_with_execution": 0,
            "subminute_or_tick_ordering": 1,
            "top_of_book_bid_ask_depth": 1,
            "multi_level_depth_or_queue": 0,
            "aggressor_side_or_trade_prints": 0,
            "raw_packet_hash_and_schema": 0,
            "right_tail_protection_audit": 0,
            "permission_or_license_clear": 0,
        },
        {
            "route_id": "local_tq_transform_union",
            "route_family": "local_proxy_tca_only",
            "current_evidence": f"Stage080 rule candidates allowed {stage080['rule_usable']}",
            "next_action": "keep downgraded; do not revive first/average/topbook transform",
            "priority": 6,
            "expected_information_gain": 1,
            "implementation_friction": 1,
            "permission_friction": 2,
            "rule_allowed_now": 0,
            "true_engine_allowed_now": 0,
            "ab_allowed_now": 0,
            "point_in_time_timestamp": 1,
            "historical_full_coverage": 0,
            "same_source_with_execution": 0,
            "subminute_or_tick_ordering": 1,
            "top_of_book_bid_ask_depth": 1,
            "multi_level_depth_or_queue": 0,
            "aggressor_side_or_trade_prints": 0,
            "raw_packet_hash_and_schema": 0,
            "right_tail_protection_audit": 0,
            "permission_or_license_clear": 0,
        },
        {
            "route_id": "minute_ohlc_far_from_touch_candidate",
            "route_family": "internal_minute_replay_only_if_far_from_touch",
            "current_evidence": "Stage102 blocks near-touch OHLC execution-sensitive rules",
            "next_action": "only allow a new preflight far from stop/progress and not close-next-bar dependent",
            "priority": 4,
            "expected_information_gain": 2,
            "implementation_friction": 2,
            "permission_friction": 1,
            "rule_allowed_now": 0,
            "true_engine_allowed_now": 0,
            "ab_allowed_now": 0,
            "point_in_time_timestamp": 1,
            "historical_full_coverage": 0,
            "same_source_with_execution": 0,
            "subminute_or_tick_ordering": 0,
            "top_of_book_bid_ask_depth": 0,
            "multi_level_depth_or_queue": 0,
            "aggressor_side_or_trade_prints": 0,
            "raw_packet_hash_and_schema": 1,
            "right_tail_protection_audit": 0,
            "permission_or_license_clear": 1,
        },
    ]
    data = pd.DataFrame(rows)
    data["contract_pass_count"] = data[CONTRACT_COLUMNS].sum(axis=1)
    data["contract_required_count"] = len(CONTRACT_COLUMNS)
    data["contract_pass_rate_pct"] = data["contract_pass_count"] / len(CONTRACT_COLUMNS) * 100.0
    return data.sort_values("priority").reset_index(drop=True)


def _action_queue(contract: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in contract.sort_values("priority").iterrows():
        blockers = [column for column in CONTRACT_COLUMNS if int(row[column]) == 0]
        rows.append(
            {
                "priority": row["priority"],
                "route_id": row["route_id"],
                "route_family": row["route_family"],
                "next_action": row["next_action"],
                "blocker_count": len(blockers),
                "top_blockers": ", ".join(blockers[:4]),
                "expected_information_gain": row["expected_information_gain"],
                "implementation_friction": row["implementation_friction"],
                "permission_friction": row["permission_friction"],
                "rule_allowed_now": row["rule_allowed_now"],
                "true_engine_allowed_now": row["true_engine_allowed_now"],
            }
        )
    return pd.DataFrame(rows)


def _promotion_gate(local_assets: pd.DataFrame, contract: pd.DataFrame) -> pd.DataFrame:
    stage068 = local_assets[local_assets["asset_id"].eq("stage068_initial_entry_tick_coverage")].iloc[0]
    stage102 = local_assets[local_assets["asset_id"].eq("stage102_bar_resolution_boundary")].iloc[0]
    same_source_full_history = int(
        (
            contract["same_source_with_execution"].astype(int).eq(1)
            & contract["historical_full_coverage"].astype(int).eq(1)
        ).any()
    )
    microstructure_raw_hash = int(
        (
            contract["raw_packet_hash_and_schema"].astype(int).eq(1)
            & (
                contract["subminute_or_tick_ordering"].astype(int).eq(1)
                | contract["top_of_book_bid_ask_depth"].astype(int).eq(1)
            )
            & contract["historical_full_coverage"].astype(int).eq(1)
        ).any()
    )
    rows = [
        {
            "gate_id": "initial_entry_tick_coverage",
            "evidence_value": _safe_float(stage068.get("coverage_ready_rate_pct")),
            "evidence_unit": "percent ready; requires 95+ before any initial-entry microstructure audit",
            "pass_for_true_engine": int(_safe_float(stage068.get("coverage_ready_rate_pct")) >= 95.0),
            "judgment": "blocked_by_sparse_coverage",
        },
        {
            "gate_id": "same_source_authority",
            "evidence_value": same_source_full_history,
            "evidence_unit": "any route currently same-source with execution and historically complete",
            "pass_for_true_engine": 0,
            "judgment": "blocked_until_broker_or_vendor_ledger",
        },
        {
            "gate_id": "historical_full_coverage",
            "evidence_value": int(contract["historical_full_coverage"].max()),
            "evidence_unit": "any route has full historical coverage now",
            "pass_for_true_engine": 0,
            "judgment": "blocked_until_full_history",
        },
        {
            "gate_id": "raw_provenance_hash",
            "evidence_value": microstructure_raw_hash,
            "evidence_unit": "any historical microstructure route has raw packet hash/schema now",
            "pass_for_true_engine": 0,
            "judgment": "blocked_for_microstructure_rules",
        },
        {
            "gate_id": "minute_ohlc_near_touch_block",
            "evidence_value": _safe_int(stage102.get("ready_event_count")),
            "evidence_unit": "Stage102 low-resolution OHLC orders",
            "pass_for_true_engine": 0,
            "judgment": "blocked_for_near_touch_ohlc_rules",
        },
        {
            "gate_id": "right_tail_protection_audit",
            "evidence_value": int(contract["right_tail_protection_audit"].max()),
            "evidence_unit": "any route has passed right-tail protection audit",
            "pass_for_true_engine": 0,
            "judgment": "blocked_until_visual_tail_gate",
        },
    ]
    gate = pd.DataFrame(rows)
    gate["strategy_feature_usable"] = 0
    return gate


def _summary(
    curve: pd.DataFrame,
    lots: pd.DataFrame,
    local_assets: pd.DataFrame,
    contract: pd.DataFrame,
    gate: pd.DataFrame,
) -> pd.DataFrame:
    metrics = s038._official_metrics(curve, lots)
    stage068 = local_assets[local_assets["asset_id"].eq("stage068_initial_entry_tick_coverage")].iloc[0]
    stage102 = local_assets[local_assets["asset_id"].eq("stage102_bar_resolution_boundary")].iloc[0]
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": "stage103_orderflow_contract_blocks_rules_data_first",
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "route_count": int(len(contract)),
                "local_asset_count": int(len(local_assets)),
                "initial_entry_tick_ready_count": _safe_int(stage068.get("ready_event_count")),
                "initial_entry_tick_planned_count": _safe_int(stage068.get("planned_event_count")),
                "initial_entry_tick_ready_rate_pct": _safe_float(stage068.get("coverage_ready_rate_pct")),
                "stage102_low_resolution_order_count": _safe_int(stage102.get("ready_event_count")),
                "rule_allowed_route_count": int(contract["rule_allowed_now"].sum()),
                "true_engine_allowed_route_count": int(contract["true_engine_allowed_now"].sum()),
                "ab_allowed_route_count": int(contract["ab_allowed_now"].sum()),
                "max_contract_pass_rate_pct": float(contract["contract_pass_rate_pct"].max()),
                "promotion_gate_count": int(len(gate)),
                "promotion_gate_pass_count": int(gate["pass_for_true_engine"].sum()),
                "strategy_feature_usable": 0,
                **metrics,
            }
        ]
    )


def _plot_official_path(curve: pd.DataFrame, local_assets: pd.DataFrame, summary: pd.Series) -> None:
    data = curve.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [2, 1, 1]})
    axes[0].plot(data["date"], data["account_equity"], color="#0f172a", linewidth=1.2)
    axes[0].set_ylabel("equity")
    axes[0].grid(True, alpha=0.25)
    axes[1].plot(data["date"], data["drawdown_pct"], color="#dc2626", linewidth=1.0)
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(True, alpha=0.25)
    asset_plot = local_assets.copy()
    colors = np.where(asset_plot["rule_usable"].astype(int).eq(1), "#16a34a", "#dc2626")
    axes[2].bar(asset_plot["asset_id"], asset_plot["ready_event_count"], color=colors, alpha=0.82)
    axes[2].set_ylabel("ready/count")
    axes[2].tick_params(axis="x", rotation=24)
    axes[2].grid(True, axis="y", alpha=0.25)
    axes[0].set_title(
        f"{STAGE} orderflow data contract | routes {int(summary['route_count'])} | true_engine_allowed=0"
    )
    fig.tight_layout()
    fig.savefig(OFFICIAL_PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_readiness_heatmap(contract: pd.DataFrame) -> None:
    data = contract.set_index("route_id")[CONTRACT_COLUMNS].astype(int)
    fig, ax = plt.subplots(figsize=(13, 6))
    image = ax.imshow(data.to_numpy(), cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(np.arange(len(CONTRACT_COLUMNS)))
    ax.set_xticklabels(CONTRACT_COLUMNS, rotation=32, ha="right")
    ax.set_yticks(np.arange(len(data.index)))
    ax.set_yticklabels(data.index)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            ax.text(j, i, int(data.iloc[i, j]), ha="center", va="center", fontsize=8)
    ax.set_title("Stage103 data contract readiness; 1 means currently satisfied")
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(READINESS_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_action_queue(action_queue: pd.DataFrame) -> None:
    data = action_queue.sort_values("priority")
    y = np.arange(len(data))
    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.barh(y, data["expected_information_gain"], color="#0f766e", alpha=0.78, label="information gain")
    ax.barh(y, -data["implementation_friction"], color="#f97316", alpha=0.78, label="implementation friction")
    ax.barh(y, -data["permission_friction"], left=-data["implementation_friction"], color="#dc2626", alpha=0.78, label="permission friction")
    ax.set_yticks(y)
    ax.set_yticklabels(data["route_id"])
    ax.axvline(0, color="#111827", linewidth=0.8)
    ax.set_xlabel("positive = value, negative = friction")
    ax.set_title("Stage103 next data actions ranked by value and friction")
    ax.legend(fontsize=8)
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(ACTION_QUEUE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    colors = np.where(gate["pass_for_true_engine"].astype(int).eq(1), "#16a34a", "#dc2626")
    fig, ax = plt.subplots(figsize=(12, 4.8))
    ax.bar(gate["gate_id"], gate["evidence_value"], color=colors, alpha=0.82)
    ax.set_ylabel("evidence value")
    ax.set_title("Stage103 data gates all block rule promotion")
    ax.tick_params(axis="x", rotation=22)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    local_assets: pd.DataFrame,
    contract: pd.DataFrame,
    action_queue: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    report = "\n".join(
        [
            f"# {STAGE} orderflow data contract audit",
            "",
            "## Decision",
            "",
            f"- decision: `{row['decision']}`",
            "- nature: data-contract audit only; no strategy rule, no true engine, no A/B, no CTP, no order API.",
            "- frozen question: after Stage102 blocks near-touch minute OHLC rules, what data contract must be satisfied before any orderflow/microstructure candidate is allowed?",
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
            "## Summary",
            "",
            f"- route count: `{int(row['route_count'])}`",
            f"- local asset count: `{int(row['local_asset_count'])}`",
            f"- initial-entry tick coverage: `{int(row['initial_entry_tick_ready_count'])}/{int(row['initial_entry_tick_planned_count'])}` = `{row['initial_entry_tick_ready_rate_pct']:.4f}%`",
            f"- Stage102 low-resolution OHLC orders: `{int(row['stage102_low_resolution_order_count'])}`",
            f"- rule allowed routes: `{int(row['rule_allowed_route_count'])}`",
            f"- true-engine allowed routes: `{int(row['true_engine_allowed_route_count'])}`",
            f"- A/B allowed routes: `{int(row['ab_allowed_route_count'])}`",
            f"- max data-contract pass rate: `{row['max_contract_pass_rate_pct']:.4f}%`",
            f"- promotion gate pass count: `{int(row['promotion_gate_pass_count'])}`",
            "",
            "## Local Asset Audit",
            "",
            _md_table(local_assets, max_rows=20),
            "",
            "## Data Contract",
            "",
            _md_table(contract, max_rows=20),
            "",
            "## Action Queue",
            "",
            _md_table(action_queue, max_rows=20),
            "",
            "## Promotion Gates",
            "",
            _md_table(gate, max_rows=20),
            "",
            "## Visual Outputs",
            "",
            f"- official path data route chart: `{OFFICIAL_PATH_CHART_OUT}`",
            f"- readiness heatmap: `{READINESS_HEATMAP_OUT}`",
            f"- action queue chart: `{ACTION_QUEUE_CHART_OUT}`",
            f"- promotion gate chart: `{GATE_CHART_OUT}`",
            "",
            "## Judgment",
            "",
            (
                "Orderflow remains the correct next information layer, but the current repo does not yet have the "
                "authorized historical depth/queue contract needed for a rule. CTP/vn.py can represent real-time "
                "top-of-book tick snapshots, and local Tq tick files can help TCA/forward watch, but neither proves "
                "full historical, same-source, right-tail-safe actionability. The next aligned work is data acquisition "
                "or a strictly far-from-touch minute preflight; no microstructure rule is allowed from current assets."
            ),
            "",
        ]
    )
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve, _open_trades, _candidates, lots, _intraday, _trades = s038._prepare_inputs()
    local_assets = _local_asset_audit()
    contract = _data_contract(local_assets)
    action_queue = _action_queue(contract)
    gate = _promotion_gate(local_assets, contract)
    summary = _summary(curve, lots, local_assets, contract, gate)

    _write_csv(local_assets, LOCAL_ASSET_OUT)
    _write_csv(contract, DATA_CONTRACT_OUT)
    _write_csv(action_queue, ACTION_QUEUE_OUT)
    _write_csv(gate, PROMOTION_GATE_OUT)
    _write_csv(summary, SUMMARY_OUT)

    _plot_official_path(curve, local_assets, summary.iloc[0])
    _plot_readiness_heatmap(contract)
    _plot_action_queue(action_queue)
    _plot_gate(gate)
    _write_report(summary, local_assets, contract, action_queue, gate)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": str(summary.iloc[0]["decision"]),
        "summary_path": str(SUMMARY_OUT),
        "report_path": str(REPORT_OUT),
        "local_asset_audit_path": str(LOCAL_ASSET_OUT),
        "data_contract_path": str(DATA_CONTRACT_OUT),
        "action_queue_path": str(ACTION_QUEUE_OUT),
        "promotion_gate_path": str(PROMOTION_GATE_OUT),
        "charts": [
            str(OFFICIAL_PATH_CHART_OUT),
            str(READINESS_HEATMAP_OUT),
            str(ACTION_QUEUE_CHART_OUT),
            str(GATE_CHART_OUT),
        ],
        "rule_allowed_route_count": int(summary.iloc[0]["rule_allowed_route_count"]),
        "true_engine_allowed_route_count": int(summary.iloc[0]["true_engine_allowed_route_count"]),
        "ab_allowed_route_count": int(summary.iloc[0]["ab_allowed_route_count"]),
        "strategy_feature_usable": 0,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), indent=2))


if __name__ == "__main__":
    main()
