from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage123"
MODEL_TAG = "stage123_wave0_intake_chain_checkpoint_v1"
OUTPUT_PREFIX = "qmt_roll_stage123_c9_minrisk_wave0_intake_chain_checkpoint"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage123_wave0_intake_chain_checkpoint"

STAGE119_TOOL = LINE_DIR / "tools" / "stage119_wave0_drop_manifest_builder.py"
STAGE117_TOOL = LINE_DIR / "tools" / "stage117_wave0_delivery_verifier.py"
STAGE120_TOOL = LINE_DIR / "tools" / "stage120_wave0_schema_contract_audit.py"

STAGE119_OUT_DIR = LINE_DIR / "outputs" / "stage119_wave0_drop_manifest_builder"
STAGE119_SUMMARY = STAGE119_OUT_DIR / "qmt_roll_stage119_c9_minrisk_wave0_drop_manifest_builder_summary_stage119_wave0_drop_manifest_builder_v1.csv"
STAGE119_CASE_SUMMARY = STAGE119_OUT_DIR / "qmt_roll_stage119_c9_minrisk_wave0_drop_manifest_builder_case_summary_stage119_wave0_drop_manifest_builder_v1.csv"

STAGE117_OUT_DIR = LINE_DIR / "outputs" / "stage117_wave0_delivery_verifier"
STAGE117_SUMMARY = STAGE117_OUT_DIR / "qmt_roll_stage117_c9_minrisk_wave0_delivery_verifier_summary_stage117_wave0_delivery_verifier_v1.csv"
STAGE117_REQUEST_STATUS = STAGE117_OUT_DIR / "qmt_roll_stage117_c9_minrisk_wave0_delivery_verifier_w0_request_delivery_status_stage117_wave0_delivery_verifier_v1.csv"
STAGE117_GATE_STATUS = STAGE117_OUT_DIR / "qmt_roll_stage117_c9_minrisk_wave0_delivery_verifier_w0_delivery_gate_status_stage117_wave0_delivery_verifier_v1.csv"

STAGE120_OUT_DIR = LINE_DIR / "outputs" / "stage120_wave0_schema_contract_audit"
STAGE120_SUMMARY = STAGE120_OUT_DIR / "qmt_roll_stage120_c9_minrisk_wave0_schema_contract_audit_summary_stage120_wave0_schema_contract_audit_v1.csv"
STAGE120_GATES = STAGE120_OUT_DIR / "qmt_roll_stage120_c9_minrisk_wave0_schema_contract_audit_schema_contract_gate_status_stage120_wave0_schema_contract_audit_v1.csv"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
EMPTY_DROP_REL = Path("research/lines/futures_trend_c9_minrisk_highquality/outputs/stage119_wave0_drop_manifest_builder/empty_drop")
SYNTHETIC_DROP_REL = Path("research/lines/futures_trend_c9_minrisk_highquality/outputs/stage118_wave0_verifier_selftest/synthetic_fixture")

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CASE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_summary_{MODEL_TAG}.csv"
STEP_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_step_summary_{MODEL_TAG}.csv"
REQUEST_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage117_request_status_{MODEL_TAG}.csv"
GATE_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_chain_status_{MODEL_TAG}.png"
CHAIN_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chain_gate_matrix_{MODEL_TAG}.png"
CASE_OUTCOME_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_outcome_chart_{MODEL_TAG}.png"

DECISION = "stage123_wave0_intake_chain_checkpoint_passed_no_real_data_no_strategy"
CLI_DECISION = "stage123_wave0_intake_chain_checkpoint_cli_completed_no_strategy"


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


def _parse_json_stdout(stdout: str) -> dict[str, Any]:
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        return json.loads(stdout[start : end + 1])
    except json.JSONDecodeError:
        return {}


def _run_command(step_id: str, command: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    completed = subprocess.run(command, cwd=REPO_DIR, text=True, capture_output=True, check=False)
    parsed = _parse_json_stdout(completed.stdout)
    step = {
        "step_id": step_id,
        "command": " ".join(command),
        "returncode": int(completed.returncode),
        "decision": parsed.get("decision", ""),
        "stdout_json_found": int(bool(parsed)),
        "stderr_tail": completed.stderr[-400:],
    }
    return step, parsed


def _stage119_manifest_for_case(case_id: str) -> Path:
    cases = _read_csv(STAGE119_CASE_SUMMARY)
    if cases.empty:
        raise RuntimeError("Stage119 case summary missing after drop build")
    matched = cases[cases["case_id"].astype(str).eq(case_id)]
    if matched.empty:
        raise RuntimeError(f"Stage119 case {case_id} not found")
    return Path(str(matched.iloc[0]["built_manifest_path"])).expanduser().resolve()


def _is_synthetic_case(case_id: str, drop_dir: Path) -> int:
    try:
        synthetic_path = SYNTHETIC_DROP_REL.resolve()
    except FileNotFoundError:
        synthetic_path = (REPO_DIR / SYNTHETIC_DROP_REL).resolve()
    return int("synthetic" in case_id.lower() or drop_dir.resolve() == synthetic_path)


def _run_chain_case(entry_case_id: str, drop_dir: Path, case_id: str, expected_stage112: int) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    drop_dir = drop_dir.expanduser().resolve()
    synthetic_case = _is_synthetic_case(case_id, drop_dir)
    step_rows: list[dict[str, Any]] = []

    step, stage119_json = _run_command(
        "stage119_drop_manifest",
        [
            sys.executable,
            str(STAGE119_TOOL),
            "--drop-dir",
            str(drop_dir),
            "--case-id",
            case_id,
            "--expected-stage112-intake",
            str(expected_stage112),
            "--skip-synthetic-selftest",
        ],
    )
    step_rows.append(step)
    manifest_path = _stage119_manifest_for_case(case_id)
    stage119_summary = _read_csv(STAGE119_SUMMARY)
    stage119_row = stage119_summary.iloc[0] if not stage119_summary.empty else pd.Series(dtype=object)

    step, stage117_json = _run_command("stage117_delivery_verify", [sys.executable, str(STAGE117_TOOL), str(manifest_path)])
    step_rows.append(step)
    stage117_summary = _read_csv(STAGE117_SUMMARY)
    stage117_row = stage117_summary.iloc[0] if not stage117_summary.empty else pd.Series(dtype=object)
    stage117_requests = _read_csv(STAGE117_REQUEST_STATUS)
    if not stage117_requests.empty:
        stage117_requests["entry_case_id"] = entry_case_id
        stage117_requests["chain_case_id"] = case_id
    stage117_gates = _read_csv(STAGE117_GATE_STATUS)
    if not stage117_gates.empty:
        stage117_gates["entry_case_id"] = entry_case_id
        stage117_gates["chain_case_id"] = case_id
        stage117_gates["stage_step"] = "stage117"

    step, stage120_json = _run_command(
        "stage120_schema_audit",
        [
            sys.executable,
            str(STAGE120_TOOL),
            "--manifest",
            str(manifest_path),
            "--manifest-label",
            case_id,
        ],
    )
    step_rows.append(step)
    stage120_summary = _read_csv(STAGE120_SUMMARY)
    stage120_row = stage120_summary.iloc[0] if not stage120_summary.empty else pd.Series(dtype=object)
    stage120_gates = _read_csv(STAGE120_GATES)
    if not stage120_gates.empty:
        stage120_gates["entry_case_id"] = entry_case_id
        stage120_gates["chain_case_id"] = case_id
        stage120_gates["stage_step"] = "stage120"

    stage119_intake = int(stage119_row.get("real_stage112_intake_allowed_now", 0) or 0)
    stage117_intake = int(stage117_row.get("stage112_intake_allowed_now", 0) or 0)
    stage120_schema_pass = int(stage120_row.get("real_w0_schema_contract_pass", 0) or 0)
    final_stage112_ready = int(not synthetic_case and stage119_intake == 1 and stage117_intake == 1 and stage120_schema_pass == 1)
    final_strategy_allowed = 0
    all_commands_ok = int(all(row["returncode"] == 0 for row in step_rows))
    expected_final = int(expected_stage112) if not synthetic_case else 0
    test_pass = int(all_commands_ok and final_stage112_ready == expected_final and final_strategy_allowed == 0)
    final_ready_required = (
        str(expected_final)
        if not synthetic_case
        else "0 because synthetic cannot final accept"
    )

    chain_gates = pd.DataFrame(
        [
            {
                "entry_case_id": entry_case_id,
                "chain_case_id": case_id,
                "stage_step": "chain",
                "gate_id": "commands_returncode_zero",
                "observed": str(all_commands_ok),
                "required": "1",
                "pass_now": all_commands_ok,
                "severity": "orchestration_hard",
            },
            {
                "entry_case_id": entry_case_id,
                "chain_case_id": case_id,
                "stage_step": "chain",
                "gate_id": "stage119_stage112_intake",
                "observed": str(stage119_intake),
                "required": "1 only for real accepted W0",
                "pass_now": stage119_intake,
                "severity": "data_hard",
            },
            {
                "entry_case_id": entry_case_id,
                "chain_case_id": case_id,
                "stage_step": "chain",
                "gate_id": "stage117_stage112_intake",
                "observed": str(stage117_intake),
                "required": "1 only for real accepted W0",
                "pass_now": stage117_intake,
                "severity": "data_hard",
            },
            {
                "entry_case_id": entry_case_id,
                "chain_case_id": case_id,
                "stage_step": "chain",
                "gate_id": "stage120_real_schema_contract_pass",
                "observed": str(stage120_schema_pass),
                "required": "1 only for real accepted W0",
                "pass_now": stage120_schema_pass,
                "severity": "data_hard",
            },
            {
                "entry_case_id": entry_case_id,
                "chain_case_id": case_id,
                "stage_step": "chain",
                "gate_id": "synthetic_case_blocked_from_final",
                "observed": str(synthetic_case),
                "required": "synthetic cannot final accept",
                "pass_now": int(final_stage112_ready == 0 if synthetic_case else 1),
                "severity": "anti_selection_hard",
            },
            {
                "entry_case_id": entry_case_id,
                "chain_case_id": case_id,
                "stage_step": "chain",
                "gate_id": "final_stage112_ready",
                "observed": str(final_stage112_ready),
                "required": final_ready_required,
                "pass_now": int(final_stage112_ready == expected_final),
                "severity": "final_hard",
            },
        ]
    )
    case = {
        "entry_case_id": entry_case_id,
        "chain_case_id": case_id,
        "drop_dir": str(drop_dir),
        "built_manifest_path": str(manifest_path),
        "synthetic_case": synthetic_case,
        "stage119_returncode": int(step_rows[0]["returncode"]),
        "stage117_returncode": int(step_rows[1]["returncode"]),
        "stage120_returncode": int(step_rows[2]["returncode"]),
        "stage119_decision": stage119_json.get("decision", ""),
        "stage117_decision": stage117_json.get("decision", ""),
        "stage120_decision": stage120_json.get("decision", ""),
        "stage119_stage112_intake": stage119_intake,
        "stage117_stage112_intake": stage117_intake,
        "stage120_real_schema_contract_pass": stage120_schema_pass,
        "final_stage112_ready": final_stage112_ready,
        "final_strategy_allowed": final_strategy_allowed,
        "test_pass": test_pass,
    }
    step_frame = pd.DataFrame(step_rows)
    step_frame["entry_case_id"] = entry_case_id
    step_frame["chain_case_id"] = case_id
    gate_frame = pd.concat([chain_gates, stage117_gates, stage120_gates], ignore_index=True)
    return case, step_frame, gate_frame, stage117_requests


def _restore_defaults() -> None:
    subprocess.run([sys.executable, str(STAGE119_TOOL)], cwd=REPO_DIR, text=True, capture_output=True, check=True)
    subprocess.run([sys.executable, str(STAGE117_TOOL)], cwd=REPO_DIR, text=True, capture_output=True, check=True)
    subprocess.run([sys.executable, str(STAGE120_TOOL)], cwd=REPO_DIR, text=True, capture_output=True, check=True)


def _plot_official_path(request_status: pd.DataFrame) -> None:
    curve = _load_curve()
    if request_status.empty:
        return
    chart = request_status.copy()
    chart["trading_day"] = pd.to_datetime(chart["trading_day"], errors="coerce")
    colors = chart["entry_case_id"].map({"empty_drop_chain": "#B91C1C", "synthetic_drop_chain": "#15803D"}).fillna("#0369A1")
    points = _nearest_curve_points(curve, chart["trading_day"])
    points = points.join(chart[["entry_case_id", "hard_accept"]].reset_index(drop=True))
    colors = points["entry_case_id"].map({"empty_drop_chain": "#B91C1C", "synthetic_drop_chain": "#15803D"}).fillna("#0369A1")
    fig, axes = plt.subplots(3, 1, figsize=(16, 10), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#202939", linewidth=1.1)
    axes[0].scatter(points["date"], points["account_equity"] / 1_000_000, color=colors, s=45, alpha=0.7)
    axes[0].set_ylabel("equity (m)")
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#DC2626", linewidth=1.0)
    axes[1].scatter(points["date"], points["drawdown_pct"], color=colors, s=45, alpha=0.7)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#0369A1", linewidth=1.0)
    axes[2].scatter(points["date"], points["broker10_margin_to_equity_pct"], color=colors, s=45, alpha=0.7)
    axes[2].axhline(100, color="#B91C1C", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.suptitle("Stage123 W0 intake chain checkpoint on official path; no real W0 final accepted")
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_chain_matrix(gates: pd.DataFrame) -> None:
    chain = gates[gates["stage_step"].eq("chain")].copy()
    pivot = chain.pivot_table(index="gate_id", columns="entry_case_id", values="pass_now", aggfunc="max", fill_value=0)
    order = [case for case in ["empty_drop_chain", "synthetic_drop_chain", "cli_drop_chain"] if case in pivot.columns]
    pivot = pivot[order]
    fig, ax = plt.subplots(figsize=(9, 5.8))
    image = ax.imshow(pivot.to_numpy(), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=20, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    for y in range(len(pivot.index)):
        for x in range(len(pivot.columns)):
            ax.text(x, y, "P" if int(pivot.iloc[y, x]) else "F", ha="center", va="center", color="#111827", fontsize=8)
    ax.set_title("Stage123 W0 intake chain gates")
    fig.colorbar(image, ax=ax, shrink=0.75)
    fig.tight_layout()
    fig.savefig(CHAIN_MATRIX_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_case_outcomes(case_summary: pd.DataFrame) -> None:
    metrics = ["stage117_stage112_intake", "stage120_real_schema_contract_pass", "final_stage112_ready", "final_strategy_allowed", "test_pass"]
    plot_data = case_summary.set_index("entry_case_id")[metrics]
    fig, ax = plt.subplots(figsize=(12, 5))
    plot_data.plot(kind="bar", ax=ax, color=["#0369A1", "#0F766E", "#A16207", "#B91C1C", "#15803D"])
    ax.set_ylim(0, 1.2)
    ax.set_ylabel("binary status")
    ax.set_title("Stage123 W0 intake chain outcomes")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(CASE_OUTCOME_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, cases: pd.DataFrame, steps: pd.DataFrame, gates: pd.DataFrame) -> None:
    report = f"""# Stage123 W0 intake chain checkpoint

## Decision

- decision: `{summary.iloc[0]['decision']}`
- nature: W0 intake orchestration checkpoint only; no strategy rule, no true engine, no A/B, no CTP connection, no order API, no external download.

## Case Summary

{_md_table(cases)}

## Step Summary

{_md_table(steps)}

## Chain Gates

{_md_table(gates[gates['stage_step'].eq('chain')])}

## Visual Outputs

- official path chain status: `{PATH_CHART_OUT}`
- chain gate matrix: `{CHAIN_MATRIX_CHART_OUT}`
- case outcome chart: `{CASE_OUTCOME_CHART_OUT}`

## Judgment

The intake path is now executable as a single checkpoint. Empty drops fail early; synthetic drops can prove file plumbing but are blocked by real schema acceptance and final ready gates. No real W0 data is accepted.
"""
    REPORT_OUT.write_text(report, encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Stage119 -> Stage117 -> Stage120 W0 intake chain.")
    parser.add_argument("--drop-dir", type=Path, default=None, help="Real W0 drop directory. Omit to run selftests.")
    parser.add_argument("--case-id", default="cli_drop", help="Case id for a CLI drop.")
    parser.add_argument("--expected-stage112-intake", type=int, choices=[0, 1], default=0)
    parser.add_argument("--no-restore", action="store_true", help="Do not restore Stage119/117/120 default outputs after CLI mode.")
    return parser.parse_args()


def main(drop_dir: Path | None = None, case_id: str = "cli_drop", expected_stage112_intake: int = 0, restore_defaults: bool = True) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cli_mode = drop_dir is not None
    if cli_mode:
        cases = [("cli_drop_chain", drop_dir, case_id, expected_stage112_intake)]
    else:
        cases = [
            ("empty_drop_chain", (REPO_DIR / EMPTY_DROP_REL), "chain_empty_drop", 0),
            ("synthetic_drop_chain", (REPO_DIR / SYNTHETIC_DROP_REL), "chain_synthetic_drop", 1),
        ]
    case_rows: list[dict[str, Any]] = []
    step_frames: list[pd.DataFrame] = []
    gate_frames: list[pd.DataFrame] = []
    request_frames: list[pd.DataFrame] = []
    try:
        for entry_case_id, case_drop_dir, chain_case_id, expected in cases:
            case, steps, gates, requests = _run_chain_case(entry_case_id, Path(case_drop_dir), chain_case_id, expected)
            case_rows.append(case)
            step_frames.append(steps)
            gate_frames.append(gates)
            request_frames.append(requests)
    finally:
        if restore_defaults:
            _restore_defaults()

    case_summary = pd.DataFrame(case_rows)
    steps = pd.concat(step_frames, ignore_index=True) if step_frames else pd.DataFrame()
    gates = pd.concat(gate_frames, ignore_index=True) if gate_frames else pd.DataFrame()
    request_status = pd.concat(request_frames, ignore_index=True) if request_frames else pd.DataFrame()
    restored = int(restore_defaults)
    final_ready_count = int(case_summary["final_stage112_ready"].sum()) if not case_summary.empty else 0
    final_strategy_count = int(case_summary["final_strategy_allowed"].sum()) if not case_summary.empty else 0
    test_pass_count = int(case_summary["test_pass"].sum()) if not case_summary.empty else 0
    decision = CLI_DECISION if cli_mode else DECISION
    if test_pass_count != len(case_summary):
        decision = "stage123_wave0_intake_chain_checkpoint_failed"
    base_summary = _read_csv(STAGE119_SUMMARY)
    base = base_summary.iloc[0] if not base_summary.empty else pd.Series(dtype=object)
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": decision,
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "case_count": int(len(case_summary)),
                "test_pass_count": test_pass_count,
                "test_fail_count": int(len(case_summary) - test_pass_count),
                "final_stage112_ready_count": final_ready_count,
                "final_strategy_allowed_count": final_strategy_count,
                "stage119_117_120_default_restored": restored,
                "real_w0_drop_scanned": int(cli_mode),
                "real_w0_data_delivered": int(final_ready_count > 0 and cli_mode),
                "real_stage112_intake_allowed_now": int(final_ready_count > 0 and cli_mode),
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "end_equity": float(base.get("end_equity", np.nan)),
                "total_return_pct": float(base.get("total_return_pct", np.nan)),
                "max_drawdown_pct": float(base.get("max_drawdown_pct", np.nan)),
                "sharpe": float(base.get("sharpe", np.nan)),
                "total_slippage": float(base.get("total_slippage", np.nan)),
                "total_trade_count": float(base.get("total_trade_count", np.nan)),
                "closed_lot_win_rate_pct": float(base.get("closed_lot_win_rate_pct", np.nan)),
                "max_broker10_margin_to_equity_pct": float(base.get("max_broker10_margin_to_equity_pct", np.nan)),
            }
        ]
    )

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(case_summary, CASE_SUMMARY_OUT)
    _write_csv(steps, STEP_SUMMARY_OUT)
    _write_csv(gates, GATE_STATUS_OUT)
    _write_csv(request_status, REQUEST_STATUS_OUT)

    _plot_official_path(request_status)
    _plot_chain_matrix(gates)
    _plot_case_outcomes(case_summary)
    _write_report(summary, case_summary, steps, gates)

    output = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": decision,
        "summary_path": SUMMARY_OUT,
        "case_summary_path": CASE_SUMMARY_OUT,
        "step_summary_path": STEP_SUMMARY_OUT,
        "gate_status_path": GATE_STATUS_OUT,
        "request_status_path": REQUEST_STATUS_OUT,
        "report_path": REPORT_OUT,
        "charts": [PATH_CHART_OUT, CHAIN_MATRIX_CHART_OUT, CASE_OUTCOME_CHART_OUT],
        "final_stage112_ready_count": final_ready_count,
        "final_strategy_allowed_count": final_strategy_count,
        "stage119_117_120_default_restored": restored,
        "real_w0_drop_scanned": int(cli_mode),
        "real_w0_data_delivered": int(final_ready_count > 0 and cli_mode),
        "real_stage112_intake_allowed_now": int(final_ready_count > 0 and cli_mode),
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(output), indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(_json_safe(output), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    args = _parse_args()
    main(
        drop_dir=args.drop_dir,
        case_id=args.case_id,
        expected_stage112_intake=args.expected_stage112_intake,
        restore_defaults=not args.no_restore,
    )
