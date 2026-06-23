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
STAGE = "Stage267"
MODEL_TAG = "stage267_external_data_acceptance_orchestrator_v1"
OUTPUT_PREFIX = "qmt_roll_stage267_c9_minrisk_external_data_acceptance_orchestrator"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage267_external_data_acceptance_orchestrator"

STAGE251_DIR = LINE_DIR / "outputs" / "stage251_dd30_account_floor_true_engine"
STAGE263_DIR = LINE_DIR / "outputs" / "stage263_external_data_arrival_supergate_audit"
STAGE264_DIR = LINE_DIR / "outputs" / "stage264_external_data_inbox_arrival_monitor"
STAGE265_DIR = LINE_DIR / "outputs" / "stage265_execution_replay_real_package_validator"
STAGE266_DIR = LINE_DIR / "outputs" / "stage266_authorized_w0_real_package_validator"

STAGE251_PREFIX = "qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine"
STAGE263_PREFIX = "qmt_roll_stage263_c9_minrisk_external_data_arrival_supergate_audit"
STAGE264_PREFIX = "qmt_roll_stage264_c9_minrisk_external_data_inbox_arrival_monitor"
STAGE265_PREFIX = "qmt_roll_stage265_c9_minrisk_execution_replay_real_package_validator"
STAGE266_PREFIX = "qmt_roll_stage266_c9_minrisk_authorized_w0_real_package_validator"

STAGE251_TAG = "stage251_dd30_account_floor_true_engine_v1"
STAGE263_TAG = "stage263_external_data_arrival_supergate_audit_v1"
STAGE264_TAG = "stage264_external_data_inbox_arrival_monitor_v1"
STAGE265_TAG = "stage265_execution_replay_real_package_validator_v1"
STAGE266_TAG = "stage266_authorized_w0_real_package_validator_v1"

STAGE251_CURVE_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_curve_{STAGE251_TAG}.csv"
STAGE251_SUMMARY_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_summary_{STAGE251_TAG}.csv"
STAGE263_ROUTE_IN = STAGE263_DIR / f"{STAGE263_PREFIX}_route_supergate_{STAGE263_TAG}.csv"
STAGE263_MISSING_IN = STAGE263_DIR / f"{STAGE263_PREFIX}_missing_evidence_ledger_{STAGE263_TAG}.csv"
STAGE264_SUMMARY_IN = STAGE264_DIR / f"{STAGE264_PREFIX}_summary_{STAGE264_TAG}.csv"
STAGE264_PACKAGE_INVENTORY_IN = STAGE264_DIR / f"{STAGE264_PREFIX}_package_inventory_{STAGE264_TAG}.csv"
STAGE265_SUMMARY_IN = STAGE265_DIR / f"{STAGE265_PREFIX}_summary_{STAGE265_TAG}.csv"
STAGE265_GATE_IN = STAGE265_DIR / f"{STAGE265_PREFIX}_package_gate_{STAGE265_TAG}.csv"
STAGE266_SUMMARY_IN = STAGE266_DIR / f"{STAGE266_PREFIX}_summary_{STAGE266_TAG}.csv"
STAGE266_GATE_IN = STAGE266_DIR / f"{STAGE266_PREFIX}_package_gate_{STAGE266_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
ROUTE_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_acceptance_status_{MODEL_TAG}.csv"
COVERAGE_DEBT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_debt_ledger_{MODEL_TAG}.csv"
GATE_CASCADE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_downstream_gate_cascade_{MODEL_TAG}.csv"
FALSE_POSITIVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_false_positive_rejection_ledger_{MODEL_TAG}.csv"
NEXT_ACTION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_orchestrator_next_action_{MODEL_TAG}.csv"
RUNBOOK_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ACCEPTANCE_RUNBOOK_{MODEL_TAG}.md"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_acceptance_status_{MODEL_TAG}.png"
ROUTE_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_acceptance_heatmap_{MODEL_TAG}.png"
COVERAGE_DEBT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_debt_chart_{MODEL_TAG}.png"
GATE_CASCADE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_downstream_gate_cascade_chart_{MODEL_TAG}.png"
FALSE_POSITIVE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_false_positive_rejection_chart_{MODEL_TAG}.png"
NEXT_ACTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_action_chart_{MODEL_TAG}.png"


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


def _load_inputs() -> dict[str, Any]:
    return {
        "stage251_curve": _read_csv(STAGE251_CURVE_IN),
        "stage251_summary": _read_csv(STAGE251_SUMMARY_IN),
        "stage263_route": _read_csv(STAGE263_ROUTE_IN),
        "stage263_missing": _read_csv(STAGE263_MISSING_IN, required=False),
        "stage264_summary": _read_csv(STAGE264_SUMMARY_IN),
        "stage264_package_inventory": _read_csv(STAGE264_PACKAGE_INVENTORY_IN),
        "stage265_summary": _read_csv(STAGE265_SUMMARY_IN),
        "stage265_gate": _read_csv(STAGE265_GATE_IN),
        "stage266_summary": _read_csv(STAGE266_SUMMARY_IN),
        "stage266_gate": _read_csv(STAGE266_GATE_IN),
    }


def _gate_pass_count(gate: pd.DataFrame) -> tuple[int, int]:
    if gate.empty:
        return 0, 0
    return int(gate["pass_now"].sum()), int(len(gate))


def _route_status(inputs: dict[str, Any]) -> pd.DataFrame:
    route = inputs["stage263_route"].copy()
    stage264_inventory = inputs["stage264_package_inventory"]
    stage265_summary = _row(inputs["stage265_summary"])
    stage266_summary = _row(inputs["stage266_summary"])
    stage265_gate_pass, stage265_gate_count = _gate_pass_count(inputs["stage265_gate"])
    stage266_gate_pass, stage266_gate_count = _gate_pass_count(inputs["stage266_gate"])
    rows: list[dict[str, Any]] = []
    for _, item in route.iterrows():
        route_id = str(item["route_id"])
        inventory = stage264_inventory[stage264_inventory["route_id"].astype(str).eq(route_id)]
        if route_id == "authorized_orderflow_mbp10_mbo_w0_chain":
            validator_stage = "Stage266"
            accepted_count = _to_int(_get(stage266_summary, "accepted_w0_package_count"))
            package_candidate_count = _to_int(_get(stage266_summary, "drop_root_candidate_count"))
            package_root_exists_count = _to_int(_get(stage266_summary, "drop_root_exists_count"))
            package_with_files_count = _to_int(_get(stage266_summary, "drop_root_with_files_count"))
            validator_gate_pass = stage266_gate_pass
            validator_gate_count = stage266_gate_count
            validator_primary_ready = _to_int(_get(stage266_summary, "ready_route_window_count"))
            validator_primary_missing = _to_int(_get(stage266_summary, "missing_route_window_count"))
            validator_secondary_ready = _to_int(_get(stage266_summary, "request_hard_accept_count"))
            expected_files_or_roles = _to_int(_get(stage266_summary, "expected_file_count_per_package"))
            file_or_role_ready = _to_int(_get(stage266_summary, "best_known_role_file_count"))
            next_if_accepted = "Stage112/113 intake -> Stage141 promotion"
            blocked_by = "no_authorized_w0_drop_root_or_files"
        else:
            validator_stage = "Stage265"
            accepted_count = _to_int(_get(stage265_summary, "accepted_package_count"))
            package_candidate_count = _to_int(_get(stage265_summary, "package_candidate_count"))
            package_root_exists_count = _to_int(_get(stage265_summary, "package_root_exists_count"))
            package_with_files_count = _to_int(_get(stage265_summary, "package_with_files_count"))
            validator_gate_pass = stage265_gate_pass
            validator_gate_count = stage265_gate_count
            validator_primary_ready = _to_int(_get(item.to_dict(), "primary_ready_count"))
            validator_primary_missing = _to_int(_get(item.to_dict(), "primary_missing_count"))
            validator_secondary_ready = _to_int(_get(stage265_summary, "accepted_package_count"))
            expected_files_or_roles = _to_int(_get(stage265_summary, "required_file_role_count"))
            file_or_role_ready = _to_int(_get(stage265_summary, "file_role_pass_count"))
            next_if_accepted = "Stage260 field/source audit -> tail atlas -> Stage141 promotion"
            blocked_by = "no_broker_production_execution_replay_package"
        package_complete_count = int(inventory["package_complete_now"].sum()) if not inventory.empty else 0
        downstream_release_allowed = int(accepted_count > 0 and _to_int(item["strategy_rule_allowed_now"]) == 1)
        route_state = "accepted_wait_downstream_release" if accepted_count > 0 else str(item["route_decision"])
        rows.append(
            {
                "route_id": route_id,
                "route_name": str(item["route_name"]),
                "validator_stage": validator_stage,
                "contract_packet_ready": _to_int(item["contract_packet_ready"]),
                "stage264_package_candidate_count": int(len(inventory)),
                "stage264_package_complete_count": package_complete_count,
                "validator_package_candidate_count": package_candidate_count,
                "validator_package_root_exists_count": package_root_exists_count,
                "validator_package_with_files_count": package_with_files_count,
                "accepted_external_package_count": accepted_count,
                "primary_expected_unit": str(item["primary_expected_unit"]),
                "primary_expected_count": _to_int(item["primary_expected_count"]),
                "primary_ready_count": validator_primary_ready,
                "primary_missing_count": validator_primary_missing,
                "secondary_expected_unit": str(item["secondary_expected_unit"]),
                "secondary_expected_count": _to_int(item["secondary_expected_count"]),
                "secondary_ready_count": validator_secondary_ready,
                "secondary_missing_count": max(_to_int(item["secondary_expected_count"]) - validator_secondary_ready, 0),
                "expected_files_or_roles": expected_files_or_roles,
                "file_or_role_ready_count": file_or_role_ready,
                "validator_gate_pass_count": validator_gate_pass,
                "validator_gate_count": validator_gate_count,
                "downstream_release_allowed_now": downstream_release_allowed,
                "strategy_rule_allowed_now": 0,
                "true_engine_allowed_now": 0,
                "ab_allowed_now": 0,
                "route_state": route_state,
                "blocked_by": blocked_by if accepted_count == 0 else "downstream_stage_not_released_yet",
                "next_if_accepted": next_if_accepted,
                "promotion_ready": 0,
            }
        )
    return pd.DataFrame(rows)


def _coverage_debt(route_status: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = [
        {
            "debt_id": "local_minute_formal_feature",
            "route_id": "local_closed",
            "unit": "entry_decision_context",
            "expected_count": 219,
            "ready_count": 219,
            "missing_count": 0,
            "can_be_solved_locally": 0,
            "notes": "Stage255/260 closed local minute/formal feature context; rule readiness remains zero.",
        }
    ]
    for _, row in route_status.iterrows():
        rows.append(
            {
                "debt_id": f"{row['route_id']}_primary",
                "route_id": row["route_id"],
                "unit": row["primary_expected_unit"],
                "expected_count": _to_int(row["primary_expected_count"]),
                "ready_count": _to_int(row["primary_ready_count"]),
                "missing_count": _to_int(row["primary_missing_count"]),
                "can_be_solved_locally": 0,
                "notes": row["blocked_by"],
            }
        )
        rows.append(
            {
                "debt_id": f"{row['route_id']}_secondary",
                "route_id": row["route_id"],
                "unit": row["secondary_expected_unit"],
                "expected_count": _to_int(row["secondary_expected_count"]),
                "ready_count": _to_int(row["secondary_ready_count"]),
                "missing_count": _to_int(row["secondary_missing_count"]),
                "can_be_solved_locally": 0,
                "notes": row["blocked_by"],
            }
        )
    return pd.DataFrame(rows)


def _gate_cascade(route_status: pd.DataFrame) -> pd.DataFrame:
    steps = [
        ("contract_packet_ready", "contract packet exists", "contract_packet_ready"),
        ("inbox_package_detected", "candidate package root has files", "validator_package_with_files_count"),
        ("validator_package_accepted", "real package accepted by validator", "accepted_external_package_count"),
        ("coverage_units_ready", "primary and secondary coverage complete", "coverage_ready"),
        ("downstream_stage_released", "Stage112/113 or Stage260 allowed", "downstream_release_allowed_now"),
        ("stage141_promotion_ready", "Stage141 promotion-ready evidence", "promotion_ready"),
        ("strategy_rule_allowed", "strategy rule and true engine allowed", "strategy_rule_allowed_now"),
    ]
    rows: list[dict[str, Any]] = []
    for _, route in route_status.iterrows():
        coverage_ready = int(
            _to_int(route["primary_ready_count"]) >= _to_int(route["primary_expected_count"])
            and _to_int(route["secondary_ready_count"]) >= _to_int(route["secondary_expected_count"])
        )
        route_values = {**route.to_dict(), "coverage_ready": coverage_ready}
        previous_pass = 1
        for order, (gate_id, gate_name, column) in enumerate(steps, start=1):
            observed = _to_int(route_values.get(column))
            if column in {"contract_packet_ready", "downstream_release_allowed_now", "promotion_ready", "strategy_rule_allowed_now"}:
                pass_now = int(observed >= 1)
            else:
                pass_now = int(observed > 0)
            cascade_pass = int(previous_pass and pass_now)
            previous_pass = cascade_pass
            rows.append(
                {
                    "route_id": route["route_id"],
                    "route_name": route["route_name"],
                    "step_order": order,
                    "gate_id": gate_id,
                    "gate_name": gate_name,
                    "observed": observed,
                    "pass_now": pass_now,
                    "cascade_pass_now": cascade_pass,
                }
            )
    return pd.DataFrame(rows)


def _false_positive_rejection() -> pd.DataFrame:
    rows = [
        ("minute_ohlcv_or_oi_only", "local OHLCV/OI context without same-source orderflow/execution replay", 1, "does not prove queue/depth/fill semantics"),
        ("smoke_or_dry_run_files", "smoke, dry-run, or fixture files", 1, "valid for tooling selftest only"),
        ("read_only_account_snapshots", "read-only account or position snapshots", 1, "cannot reconstruct submitted order lifecycle"),
        ("adapter_or_pending_order_contracts", "adapter contracts or pending order drafts", 1, "not executed broker/production evidence"),
        ("ordinary_backtest_trade_ledger", "backtest trades/orders", 1, "generated by strategy engine, not same-source external evidence"),
        ("partial_external_package", "partial W0/replay package with missing roles/schema/hash", 1, "quarantine until validator accepts"),
        ("manual_spreadsheet_or_screenshot", "manual table, screenshot, or copied note", 1, "not machine-verifiable raw hash/schema contract"),
    ]
    return pd.DataFrame(rows, columns=["rejection_id", "artifact_kind", "reject_as_strategy_evidence", "reason"])


def _next_action(route_status: pd.DataFrame) -> pd.DataFrame:
    w0 = _row(route_status[route_status["route_id"].eq("authorized_orderflow_mbp10_mbo_w0_chain")])
    replay = _row(route_status[route_status["route_id"].eq("broker_production_execution_replay_chain")])
    w0_accepted = _to_int(_get(w0, "accepted_external_package_count"))
    replay_accepted = _to_int(_get(replay, "accepted_external_package_count"))
    rows = [
        {
            "priority": 1,
            "action_id": "if_w0_accepted_run_stage112_113_141",
            "condition_now": int(w0_accepted > 0),
            "allowed_now": int(w0_accepted > 0),
            "action": "Run Stage112/113 intake and Stage141 only for the accepted authorized W0 package.",
            "strategy_rule_allowed": 0,
        },
        {
            "priority": 2,
            "action_id": "if_replay_accepted_run_stage260_tail_stage141",
            "condition_now": int(replay_accepted > 0),
            "allowed_now": int(replay_accepted > 0),
            "action": "Run Stage260 field/source audit, tail coverage atlas, then Stage141 only for accepted broker/production replay.",
            "strategy_rule_allowed": 0,
        },
        {
            "priority": 3,
            "action_id": "if_no_packages_keep_stage264_265_266_monitoring",
            "condition_now": int(w0_accepted == 0 and replay_accepted == 0),
            "allowed_now": int(w0_accepted == 0 and replay_accepted == 0),
            "action": "No accepted external package. Re-run Stage264/265/266 after files arrive; do not resume local OHLCV/OI rules.",
            "strategy_rule_allowed": 0,
        },
    ]
    return pd.DataFrame(rows)


def _summary(
    inputs: dict[str, Any],
    route_status: pd.DataFrame,
    coverage_debt: pd.DataFrame,
    gate_cascade: pd.DataFrame,
) -> pd.DataFrame:
    official = _official_summary(inputs["stage251_summary"])
    accepted_routes = int((route_status["accepted_external_package_count"] > 0).sum())
    strategy_allowed_routes = int(route_status["strategy_rule_allowed_now"].sum())
    true_engine_routes = int(route_status["true_engine_allowed_now"].sum())
    external_missing_total = int(coverage_debt[coverage_debt["route_id"].ne("local_closed")]["missing_count"].sum())
    row = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": "stage267_external_acceptance_orchestrator_no_accepted_package_no_rule",
        "stage_nature": "read_only_dual_route_external_data_acceptance_orchestrator",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_or_simnow_connected": 0,
        "external_route_count": int(len(route_status)),
        "contract_packet_ready_route_count": int(route_status["contract_packet_ready"].sum()),
        "accepted_route_count": accepted_routes,
        "strategy_rule_allowed_route_count": strategy_allowed_routes,
        "true_engine_allowed_route_count": true_engine_routes,
        "local_minute_missing_count": int(coverage_debt[coverage_debt["debt_id"].eq("local_minute_formal_feature")]["missing_count"].sum()),
        "external_missing_unit_total": external_missing_total,
        "coverage_debt_row_count": int(len(coverage_debt)),
        "cascade_gate_count": int(len(gate_cascade)),
        "cascade_gate_pass_count": int(gate_cascade["cascade_pass_now"].sum()),
        "objective_completion_proven": 0,
        "strategy_feature_usable": 0,
        "official_end_equity": _to_float(_get(official, "end_equity")),
        "official_total_return_pct": _to_float(_get(official, "total_return_pct")),
        "official_max_dd_pct": _to_float(_get(official, "max_dd_pct", "max_drawdown_pct")),
        "official_sharpe": _to_float(_get(official, "sharpe")),
        "official_total_slippage": _to_float(_get(official, "total_slippage")),
        "official_total_trade_count": _to_float(_get(official, "total_trade_count")),
        "official_win_rate_pct": _to_float(_get(official, "nonzero_daily_win_rate_pct", "closed_lot_win_rate_pct")),
        "official_broker10_peak_pct": _to_float(_get(official, "max_broker10_margin_to_equity_pct")),
        "visual_file_count": 6,
    }
    return pd.DataFrame([row])


def _plot_official_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    row = _row(summary)
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax1.plot(curve["date"], curve["account_equity"], color="#2f6f73", linewidth=1.8)
    ax1.set_ylabel("Equity")
    ax1.grid(True, alpha=0.25)
    ax2 = ax1.twinx()
    ax2.fill_between(curve["date"], curve["drawdown_pct"], 0, color="#b5533c", alpha=0.25)
    ax2.set_ylabel("Drawdown %")
    ax1.set_title(
        "Stage267 external acceptance orchestrator | "
        f"accepted routes {row['accepted_route_count']}/{row['external_route_count']} | "
        f"strategy-ready {row['strategy_rule_allowed_route_count']}"
    )
    ax1.text(
        0.015,
        0.95,
        "No external package accepted: no strategy rule / no true engine",
        transform=ax1.transAxes,
        va="top",
        bbox={"facecolor": "white", "edgecolor": "#777777", "alpha": 0.9},
    )
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_route_heatmap(route_status: pd.DataFrame) -> None:
    columns = [
        "contract_packet_ready",
        "stage264_package_complete_count",
        "accepted_external_package_count",
        "downstream_release_allowed_now",
        "strategy_rule_allowed_now",
        "true_engine_allowed_now",
    ]
    data = route_status.set_index("route_id")[columns].copy()
    binary = data.copy()
    for column in columns:
        binary[column] = (pd.to_numeric(binary[column], errors="coerce").fillna(0) > 0).astype(int)
    fig, ax = plt.subplots(figsize=(10.5, 4.5))
    ax.imshow(binary.to_numpy(dtype=float), cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(columns)))
    ax.set_xticklabels(columns, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(len(binary.index)))
    ax.set_yticklabels(binary.index, fontsize=8)
    for i in range(binary.shape[0]):
        for j in range(binary.shape[1]):
            ax.text(j, i, str(int(binary.iloc[i, j])), ha="center", va="center", fontsize=8)
    ax.set_title("Dual-route acceptance heatmap")
    fig.tight_layout()
    fig.savefig(ROUTE_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_coverage_debt(coverage_debt: pd.DataFrame) -> None:
    data = coverage_debt.copy()
    labels = data["debt_id"].astype(str).tolist()
    x = np.arange(len(data))
    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.bar(x, data["ready_count"].to_numpy(dtype=float), color="#5b8c85", label="ready")
    ax.bar(x, data["missing_count"].to_numpy(dtype=float), bottom=data["ready_count"].to_numpy(dtype=float), color="#b5533c", label="missing")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Count")
    ax.set_title("Coverage debt ledger: local closed, external still missing")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(COVERAGE_DEBT_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_gate_cascade(gate_cascade: pd.DataFrame) -> None:
    pivot = gate_cascade.pivot_table(index="route_id", columns="gate_id", values="cascade_pass_now", aggfunc="max", fill_value=0)
    ordered = ["contract_packet_ready", "inbox_package_detected", "validator_package_accepted", "coverage_units_ready", "downstream_stage_released", "stage141_promotion_ready", "strategy_rule_allowed"]
    pivot = pivot[[column for column in ordered if column in pivot.columns]]
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.imshow(pivot.to_numpy(dtype=float), cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(j, i, str(int(pivot.iloc[i, j])), ha="center", va="center", fontsize=8)
    ax.set_title("Downstream gate cascade")
    fig.tight_layout()
    fig.savefig(GATE_CASCADE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_false_positive(false_positive: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 4.8))
    y = np.arange(len(false_positive))
    ax.barh(y, false_positive["reject_as_strategy_evidence"].to_numpy(dtype=float), color="#b5533c")
    ax.set_yticks(y)
    ax.set_yticklabels(false_positive["rejection_id"], fontsize=8)
    ax.set_xlim(0, 1.1)
    ax.set_xlabel("Reject as strategy evidence")
    ax.set_title("False-positive artifacts blocked before strategy layer")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FALSE_POSITIVE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_next_action(next_action: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.8))
    y = np.arange(len(next_action))
    ax.barh(y, next_action["allowed_now"].to_numpy(dtype=float), color=["#5b8c85" if value else "#c7c7c7" for value in next_action["allowed_now"]])
    ax.set_yticks(y)
    ax.set_yticklabels(next_action["action_id"], fontsize=8)
    ax.set_xlim(0, 1.1)
    ax.set_xlabel("Allowed now")
    ax.set_title("Orchestrator next action")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(NEXT_ACTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _runbook(route_status: pd.DataFrame, next_action: pd.DataFrame) -> str:
    return f"""# Stage267 External Data Acceptance Runbook

## Current State

{_md_table(route_status, max_rows=10)}

## Hard Sequence

1. Run Stage264 after any file arrival to detect candidate roots.
2. If authorized W0 files arrive, run Stage266. Only accepted W0 packages may continue to Stage112/113 and Stage141.
3. If broker/production execution replay files arrive, run Stage265. Only accepted replay packages may continue to Stage260, tail coverage atlas, and Stage141.
4. Stage141 or any true-engine/A-B attempt remains forbidden until the upstream route is accepted and downstream release gates pass.

## Current Next Action

{_md_table(next_action, max_rows=10)}
"""


def _report(
    summary: pd.DataFrame,
    route_status: pd.DataFrame,
    coverage_debt: pd.DataFrame,
    gate_cascade: pd.DataFrame,
    false_positive: pd.DataFrame,
    next_action: pd.DataFrame,
) -> str:
    row = _row(summary)
    return f"""# Stage267 external data acceptance orchestrator

## Decision

`{row['decision']}`

This stage is a read-only dual-route orchestrator. It aggregates Stage263 route contracts, Stage264 inbox monitoring, Stage265 broker/production execution replay validation, and Stage266 authorized W0/orderflow validation. It does not create a strategy rule, run true engine, trigger A/B, change official config, connect CTP/SimNow, or call any order API.

## External research judgment

The design follows data-quality orchestration practice: Great Expectations checkpoints aggregate validation suites and actions, Dagster asset checks keep data-quality checks attached to downstream asset materialization, Airflow sensors separate arrival detection from downstream execution, and dbt data tests express failing records as blockers. For this line, the correct shape is a route-level acceptance orchestrator: file arrival is necessary but not sufficient; schema/hash/coverage validation must block downstream strategy research until it passes.

Sources:
- https://docs.greatexpectations.io/docs/0.18/reference/learn/terms/checkpoint/
- https://docs.dagster.io/guides/test/asset-checks
- https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/sensors.html
- https://docs.getdbt.com/docs/build/data-tests

## Summary

- Official A unchanged: equity `{row['official_end_equity']:.2f}`, return `{row['official_total_return_pct']:.4f}%`, maxDD `{row['official_max_dd_pct']:.4f}%`, Sharpe `{row['official_sharpe']:.4f}`, slippage `{row['official_total_slippage']:.0f}`, trades `{row['official_total_trade_count']:.0f}`, win rate `{row['official_win_rate_pct']:.4f}%`.
- External routes: `{row['external_route_count']}`, contract-ready `{row['contract_packet_ready_route_count']}`, accepted `{row['accepted_route_count']}`.
- Strategy-ready routes: `{row['strategy_rule_allowed_route_count']}`; true-engine-ready routes: `{row['true_engine_allowed_route_count']}`.
- Local minute/formal feature missing count: `{row['local_minute_missing_count']}`.
- External missing unit total across route ledgers: `{row['external_missing_unit_total']}`.
- Cascade gates pass: `{row['cascade_gate_pass_count']}/{row['cascade_gate_count']}`.

## Route Acceptance Status

{_md_table(route_status, max_rows=10)}

## Coverage Debt

{_md_table(coverage_debt, max_rows=20)}

## Downstream Gate Cascade

{_md_table(gate_cascade, max_rows=30)}

## False Positive Rejection

{_md_table(false_positive, max_rows=20)}

## Next Action

{_md_table(next_action, max_rows=10)}
"""


def main() -> None:
    inputs = _load_inputs()
    curve = _official_curve(inputs["stage251_curve"])
    route_status = _route_status(inputs)
    coverage_debt = _coverage_debt(route_status)
    gate_cascade = _gate_cascade(route_status)
    false_positive = _false_positive_rejection()
    next_action = _next_action(route_status)
    summary = _summary(inputs, route_status, coverage_debt, gate_cascade)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_csv(summary, SUMMARY_OUT)
    _write_csv(route_status, ROUTE_STATUS_OUT)
    _write_csv(coverage_debt, COVERAGE_DEBT_OUT)
    _write_csv(gate_cascade, GATE_CASCADE_OUT)
    _write_csv(false_positive, FALSE_POSITIVE_OUT)
    _write_csv(next_action, NEXT_ACTION_OUT)

    _plot_official_path(curve, summary)
    _plot_route_heatmap(route_status)
    _plot_coverage_debt(coverage_debt)
    _plot_gate_cascade(gate_cascade)
    _plot_false_positive(false_positive)
    _plot_next_action(next_action)

    _write_text(RUNBOOK_OUT, _runbook(route_status, next_action))
    _write_text(REPORT_OUT, _report(summary, route_status, coverage_debt, gate_cascade, false_positive, next_action))
    _write_json(
        DECISION_OUT,
        {
            "summary": _row(summary),
            "route_status": route_status.to_dict(orient="records"),
            "next_action": next_action.to_dict(orient="records"),
            "outputs": {
                "summary": SUMMARY_OUT,
                "route_status": ROUTE_STATUS_OUT,
                "coverage_debt": COVERAGE_DEBT_OUT,
                "gate_cascade": GATE_CASCADE_OUT,
                "false_positive": FALSE_POSITIVE_OUT,
                "next_action": NEXT_ACTION_OUT,
                "runbook": RUNBOOK_OUT,
                "report": REPORT_OUT,
                "charts": [
                    PATH_CHART_OUT,
                    ROUTE_HEATMAP_OUT,
                    COVERAGE_DEBT_CHART_OUT,
                    GATE_CASCADE_CHART_OUT,
                    FALSE_POSITIVE_CHART_OUT,
                    NEXT_ACTION_CHART_OUT,
                ],
            },
        },
    )
    print(json.dumps(_row(summary), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
