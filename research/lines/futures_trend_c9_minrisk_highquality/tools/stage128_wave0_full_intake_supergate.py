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
STAGE = "Stage128"
MODEL_TAG = "stage128_wave0_full_intake_supergate_v1"
OUTPUT_PREFIX = "qmt_roll_stage128_c9_minrisk_wave0_full_intake_supergate"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage128_wave0_full_intake_supergate"

STAGE127_TOOL = LINE_DIR / "tools" / "stage127_wave0_proof_schema_preflight_bridge.py"
STAGE125_TOOL = LINE_DIR / "tools" / "stage125_wave0_receipt_preflight_audit.py"
STAGE123_TOOL = LINE_DIR / "tools" / "stage123_wave0_intake_chain_checkpoint.py"

STAGE127_OUT_DIR = LINE_DIR / "outputs" / "stage127_wave0_proof_schema_preflight_bridge"
STAGE127_SUMMARY = (
    STAGE127_OUT_DIR
    / "qmt_roll_stage127_c9_minrisk_wave0_proof_schema_preflight_bridge_summary_"
    "stage127_wave0_proof_schema_preflight_bridge_v1.csv"
)
STAGE127_REQUEST_AUDIT = (
    STAGE127_OUT_DIR
    / "qmt_roll_stage127_c9_minrisk_wave0_proof_schema_preflight_bridge_request_schema_bridge_audit_"
    "stage127_wave0_proof_schema_preflight_bridge_v1.csv"
)
STAGE127_GATES = (
    STAGE127_OUT_DIR
    / "qmt_roll_stage127_c9_minrisk_wave0_proof_schema_preflight_bridge_proof_schema_bridge_gate_status_"
    "stage127_wave0_proof_schema_preflight_bridge_v1.csv"
)

STAGE125_OUT_DIR = LINE_DIR / "outputs" / "stage125_wave0_receipt_preflight_audit"
STAGE125_SUMMARY = (
    STAGE125_OUT_DIR
    / "qmt_roll_stage125_c9_minrisk_wave0_receipt_preflight_audit_summary_"
    "stage125_wave0_receipt_preflight_audit_v1.csv"
)
STAGE125_REQUEST_STATUS = (
    STAGE125_OUT_DIR
    / "qmt_roll_stage125_c9_minrisk_wave0_receipt_preflight_audit_request_receipt_status_"
    "stage125_wave0_receipt_preflight_audit_v1.csv"
)
STAGE125_GATES = (
    STAGE125_OUT_DIR
    / "qmt_roll_stage125_c9_minrisk_wave0_receipt_preflight_audit_receipt_preflight_gate_status_"
    "stage125_wave0_receipt_preflight_audit_v1.csv"
)

STAGE123_OUT_DIR = LINE_DIR / "outputs" / "stage123_wave0_intake_chain_checkpoint"
STAGE123_SUMMARY = (
    STAGE123_OUT_DIR
    / "qmt_roll_stage123_c9_minrisk_wave0_intake_chain_checkpoint_summary_"
    "stage123_wave0_intake_chain_checkpoint_v1.csv"
)
STAGE123_CASE_SUMMARY = (
    STAGE123_OUT_DIR
    / "qmt_roll_stage123_c9_minrisk_wave0_intake_chain_checkpoint_case_summary_"
    "stage123_wave0_intake_chain_checkpoint_v1.csv"
)
STAGE123_GATES = (
    STAGE123_OUT_DIR
    / "qmt_roll_stage123_c9_minrisk_wave0_intake_chain_checkpoint_gate_status_"
    "stage123_wave0_intake_chain_checkpoint_v1.csv"
)

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
EMPTY_DROP_DIR = STAGE125_OUT_DIR / "empty_drop"
SYNTHETIC_DROP_DIR = LINE_DIR / "outputs" / "stage118_wave0_verifier_selftest" / "synthetic_fixture"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CASE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_summary_{MODEL_TAG}.csv"
STEP_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_step_summary_{MODEL_TAG}.csv"
GATE_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_supergate_status_{MODEL_TAG}.csv"
REQUEST_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_supergate_audit_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_supergate_status_{MODEL_TAG}.png"
CASE_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_supergate_matrix_{MODEL_TAG}.png"
STEP_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_step_returncode_chart_{MODEL_TAG}.png"
REQUEST_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_supergate_matrix_{MODEL_TAG}.png"

DECISION = "stage128_full_intake_supergate_negative_selftests_passed_no_real_data"
CLI_DECISION = "stage128_full_intake_supergate_cli_completed_no_strategy"


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
    if curve.empty:
        raise RuntimeError(f"missing curve input: {CURVE_IN}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _baseline_metrics(curve: pd.DataFrame) -> dict[str, float]:
    first_equity = float(curve["account_equity"].dropna().iloc[0])
    end_equity = float(curve["account_equity"].dropna().iloc[-1])
    stage125 = _read_csv(STAGE125_SUMMARY)
    if not stage125.empty:
        row = stage125.iloc[0]
        return {
            "end_equity": float(row.get("end_equity", end_equity)),
            "total_return_pct": float(row.get("total_return_pct", (end_equity / first_equity - 1.0) * 100.0)),
            "max_drawdown_pct": float(row.get("max_drawdown_pct", curve["drawdown_pct"].min())),
            "sharpe": float(row.get("sharpe", np.nan)),
            "total_slippage": float(row.get("total_slippage", np.nan)),
            "total_trade_count": float(row.get("total_trade_count", np.nan)),
            "closed_lot_win_rate_pct": float(row.get("closed_lot_win_rate_pct", np.nan)),
            "max_broker10_margin_to_equity_pct": float(row.get("max_broker10_margin_to_equity_pct", curve["broker10_margin_to_equity_pct"].max())),
        }
    return {
        "end_equity": end_equity,
        "total_return_pct": (end_equity / first_equity - 1.0) * 100.0,
        "max_drawdown_pct": float(curve["drawdown_pct"].min()),
        "sharpe": np.nan,
        "total_slippage": np.nan,
        "total_trade_count": np.nan,
        "closed_lot_win_rate_pct": np.nan,
        "max_broker10_margin_to_equity_pct": float(curve["broker10_margin_to_equity_pct"].max()),
    }


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


def _run_command(entry_case_id: str, stage_step: str, command: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    completed = subprocess.run(
        command,
        cwd=REPO_DIR,
        text=True,
        capture_output=True,
        check=False,
        timeout=240,
    )
    parsed = _parse_json_stdout(completed.stdout)
    return (
        {
            "entry_case_id": entry_case_id,
            "stage_step": stage_step,
            "command": " ".join(command),
            "returncode": int(completed.returncode),
            "stdout_json_found": int(bool(parsed)),
            "decision": parsed.get("decision", ""),
            "stdout_tail": completed.stdout[-500:],
            "stderr_tail": completed.stderr[-500:],
        },
        parsed,
    )


def _first_row(path: Path) -> pd.Series:
    frame = _read_csv(path)
    if frame.empty:
        return pd.Series(dtype=object)
    return frame.iloc[0]


def _sum_column(path: Path, column: str) -> int:
    frame = _read_csv(path)
    if frame.empty or column not in frame.columns:
        return 0
    return int(pd.to_numeric(frame[column], errors="coerce").fillna(0).sum())


def _prepare_stage_case(
    entry_case_id: str,
    drop_dir: Path,
    expected_stage112_intake: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    resolved_drop = drop_dir.expanduser().resolve()
    step_rows: list[dict[str, Any]] = []

    step, _ = _run_command(
        entry_case_id,
        "stage127_schema_bridge",
        [
            sys.executable,
            str(STAGE127_TOOL),
            "--drop-dir",
            str(resolved_drop),
            "--case-id",
            f"{entry_case_id}_schema_bridge",
        ],
    )
    step_rows.append(step)
    stage127_row = _first_row(STAGE127_SUMMARY)
    stage127_requests = _read_csv(STAGE127_REQUEST_AUDIT)
    stage127_gates = _read_csv(STAGE127_GATES)

    step, _ = _run_command(
        entry_case_id,
        "stage125_receipt_preflight",
        [
            sys.executable,
            str(STAGE125_TOOL),
            "--drop-dir",
            str(resolved_drop),
            "--case-id",
            f"{entry_case_id}_receipt_preflight",
        ],
    )
    step_rows.append(step)
    stage125_row = _first_row(STAGE125_SUMMARY)
    stage125_requests = _read_csv(STAGE125_REQUEST_STATUS)
    stage125_gates = _read_csv(STAGE125_GATES)

    step, _ = _run_command(
        entry_case_id,
        "stage123_intake_chain",
        [
            sys.executable,
            str(STAGE123_TOOL),
            "--drop-dir",
            str(resolved_drop),
            "--case-id",
            f"{entry_case_id}_intake_chain",
            "--expected-stage112-intake",
            str(expected_stage112_intake),
        ],
    )
    step_rows.append(step)
    stage123_row = _first_row(STAGE123_SUMMARY)
    stage123_case = _first_row(STAGE123_CASE_SUMMARY)
    stage123_gates = _read_csv(STAGE123_GATES)
    stage123_ready_for_request_gate = int(stage123_row.get("final_stage112_ready_count", 0) or 0)

    if not stage127_requests.empty:
        stage127_requests["entry_case_id"] = entry_case_id
        stage127_requests["stage127_proof_schema_bridge_ready"] = stage127_requests["proof_schema_bridge_ready"]
    if not stage125_requests.empty:
        stage125_requests["entry_case_id"] = entry_case_id
    request_audit = stage127_requests.copy()
    if not request_audit.empty and not stage125_requests.empty:
        keep = [
            "request_id",
            "role_complete",
            "checksum_match",
            "proof_required_fields_present",
            "preflight_request_ready",
        ]
        merged = stage125_requests[[column for column in keep if column in stage125_requests.columns]].copy()
        request_audit = request_audit.merge(merged, on="request_id", how="left")
    if not request_audit.empty:
        request_audit["stage127_125_request_ready"] = (
            pd.to_numeric(request_audit.get("proof_schema_bridge_ready", 0), errors="coerce").fillna(0).astype(int)
            & pd.to_numeric(request_audit.get("preflight_request_ready", 0), errors="coerce").fillna(0).astype(int)
        )
        request_audit["full_supergate_request_ready"] = (
            request_audit["stage127_125_request_ready"]
            & int(stage123_ready_for_request_gate == 1)
        )
        request_audit["strategy_use_allowed_now"] = 0

    gate_rows = []
    command_returncode_zero = int(all(row["returncode"] == 0 for row in step_rows))
    stage127_bridge_ready = int(stage127_row.get("proof_schema_bridge_ready_count", 0) or 0)
    stage125_ready = int(stage125_row.get("ready_for_stage123", 0) or 0)
    stage123_ready = stage123_ready_for_request_gate
    stage123_strategy = int(stage123_row.get("final_strategy_allowed_count", 0) or 0)
    request_count = int(stage127_row.get("request_count", 41) or 41)
    final_supergate_ready = int(
        command_returncode_zero == 1
        and stage127_bridge_ready == request_count
        and stage125_ready == 1
        and stage123_ready == 1
        and stage123_strategy == 0
    )
    gates = [
        ("commands_returncode_zero", command_returncode_zero, "1", command_returncode_zero, "orchestration_hard"),
        ("stage127_schema_bridge_ready", f"{stage127_bridge_ready}/{request_count}", f"{request_count}/{request_count}", int(stage127_bridge_ready == request_count), "data_hard"),
        ("stage125_receipt_ready_for_stage123", stage125_ready, "1", int(stage125_ready == 1), "data_hard"),
        ("stage123_final_stage112_ready", stage123_ready, "1", int(stage123_ready == 1), "final_hard"),
        ("strategy_allowed_zero", stage123_strategy, "0", int(stage123_strategy == 0), "anti_selection_hard"),
        ("full_supergate_ready", final_supergate_ready, "1 only for real accepted W0", final_supergate_ready, "final_hard"),
    ]
    for gate_id, observed, required, pass_now, severity in gates:
        gate_rows.append(
            {
                "entry_case_id": entry_case_id,
                "gate_id": gate_id,
                "observed": str(observed),
                "required": str(required),
                "pass_now": int(pass_now),
                "severity": severity,
            }
        )

    case = {
        "entry_case_id": entry_case_id,
        "drop_dir": str(resolved_drop),
        "expected_stage112_intake": expected_stage112_intake,
        "stage127_returncode": int(step_rows[0]["returncode"]),
        "stage125_returncode": int(step_rows[1]["returncode"]),
        "stage123_returncode": int(step_rows[2]["returncode"]),
        "stage127_bridge_ready_count": stage127_bridge_ready,
        "stage125_ready_for_stage123": stage125_ready,
        "stage123_final_stage112_ready_count": stage123_ready,
        "stage123_final_strategy_allowed_count": stage123_strategy,
        "final_supergate_ready": final_supergate_ready,
        "strategy_use_allowed_now": 0,
        "rule_preflight_allowed_now": 0,
        "stage127_decision": str(stage127_row.get("decision", "")),
        "stage125_decision": str(stage125_row.get("decision", "")),
        "stage123_decision": str(stage123_row.get("decision", "")),
        "stage123_chain_case_id": str(stage123_case.get("chain_case_id", "")),
    }
    return case, step_rows, pd.DataFrame(gate_rows), request_audit, stage123_gates


def _build_default_cases() -> list[tuple[str, Path, int]]:
    return [
        ("empty_drop_supergate", EMPTY_DROP_DIR, 0),
        ("synthetic_fixture_supergate", SYNTHETIC_DROP_DIR, 1),
    ]


def _build_cli_cases(drop_dir: Path, expected_stage112_intake: int) -> list[tuple[str, Path, int]]:
    return [("cli_drop_supergate", drop_dir, expected_stage112_intake)]


def _restore_default_stage_outputs() -> int:
    commands = [
        [sys.executable, str(STAGE127_TOOL)],
        [sys.executable, str(STAGE125_TOOL)],
        [sys.executable, str(STAGE123_TOOL)],
    ]
    results = [
        subprocess.run(command, cwd=REPO_DIR, text=True, capture_output=True, check=False, timeout=240)
        for command in commands
    ]
    return int(all(result.returncode == 0 for result in results))


def _plot_official_path(curve: pd.DataFrame, request_audit: pd.DataFrame, case_summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage128 official path with full W0 intake supergate status", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#1f5d4a", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#C2410C", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3B5BDB", linewidth=1.0)
    axes[2].axhline(100, color="#333333", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    if not request_audit.empty:
        for idx, (entry_case_id, group) in enumerate(request_audit.groupby("entry_case_id")):
            points = _nearest_curve_points(curve, group["trading_day"])
            ready = pd.to_numeric(group["full_supergate_request_ready"], errors="coerce").fillna(0).reset_index(drop=True)
            color = "#15803D" if int(ready.sum()) > 0 else ["#B91C1C", "#A16207", "#0369A1"][idx % 3]
            marker = "o" if idx == 0 else "x"
            axes[0].scatter(points["date"], points["account_equity"] / 1_000_000, color=color, marker=marker, s=34, alpha=0.62, label=entry_case_id)
            axes[1].scatter(points["date"], points["drawdown_pct"], color=color, marker=marker, s=34, alpha=0.62)
            axes[2].scatter(points["date"], points["broker10_margin_to_equity_pct"], color=color, marker=marker, s=34, alpha=0.62)
        axes[0].legend(loc="upper left", fontsize=8)
    metrics = [
        "stage127_bridge_ready_count",
        "stage125_ready_for_stage123",
        "stage123_final_stage112_ready_count",
        "final_supergate_ready",
    ]
    plot = case_summary.set_index("entry_case_id")[metrics] if not case_summary.empty else pd.DataFrame()
    if not plot.empty:
        plot.plot(kind="bar", ax=axes[3], color=["#3B5BDB", "#0F766E", "#A16207", "#15803D"])
        axes[3].set_ylim(0, max(1.2, float(plot.to_numpy().max()) + 0.5))
    axes[3].set_ylabel("count / flag")
    axes[3].set_title("Case supergate outcomes")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_case_matrix(case_summary: pd.DataFrame) -> None:
    columns = [
        "stage127_returncode",
        "stage125_returncode",
        "stage123_returncode",
        "stage127_bridge_ready_count",
        "stage125_ready_for_stage123",
        "stage123_final_stage112_ready_count",
        "final_supergate_ready",
        "strategy_use_allowed_now",
    ]
    matrix = case_summary.set_index("entry_case_id")[columns].copy()
    for column in ["stage127_returncode", "stage125_returncode", "stage123_returncode"]:
        matrix[column] = matrix[column].eq(0).astype(int)
    matrix["stage127_bridge_ready_count"] = matrix["stage127_bridge_ready_count"].gt(0).astype(int)
    data = matrix.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(12, 4.8))
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage128 case supergate matrix")
    ax.set_xticks(np.arange(len(columns)))
    ax.set_xticklabels(columns, rotation=35, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(CASE_MATRIX_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_step_chart(step_summary: pd.DataFrame) -> None:
    chart = step_summary.copy()
    chart["returncode_zero"] = chart["returncode"].eq(0).astype(int)
    pivot = chart.pivot_table(index="stage_step", columns="entry_case_id", values="returncode_zero", aggfunc="max", fill_value=0)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    image = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage128 step returncodes")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=20, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for y in range(len(pivot.index)):
        for x in range(len(pivot.columns)):
            ax.text(x, y, int(pivot.iloc[y, x]), ha="center", va="center", fontsize=9)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(STEP_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_request_matrix(request_audit: pd.DataFrame) -> None:
    if request_audit.empty:
        return
    columns = [
        "proof_schema_bridge_ready",
        "role_complete",
        "checksum_match",
        "proof_required_fields_present",
        "preflight_request_ready",
        "full_supergate_request_ready",
        "strategy_use_allowed_now",
    ]
    available = [column for column in columns if column in request_audit.columns]
    sample = request_audit[request_audit["entry_case_id"].eq(request_audit["entry_case_id"].iloc[0])].copy()
    data = sample[available].apply(pd.to_numeric, errors="coerce").fillna(0).clip(upper=1).to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(10, 10))
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage128 request supergate matrix (first case)")
    ax.set_xticks(np.arange(len(available)))
    ax.set_xticklabels(available, rotation=35, ha="right")
    y_labels = [rid if idx % 4 == 0 else "" for idx, rid in enumerate(sample["request_id"])]
    ax.set_yticks(np.arange(len(sample)))
    ax.set_yticklabels(y_labels, fontsize=7)
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(REQUEST_CHART_OUT, dpi=170)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, case_summary: pd.DataFrame, step_summary: pd.DataFrame, gates: pd.DataFrame) -> None:
    report = [
        f"# {STAGE} W0 full intake supergate",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- scope: Stage127 -> Stage125 -> Stage123 orchestration only; no strategy rule, true-engine run, A/B, order API, CTP connection, or external download.",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Case Summary",
        "",
        _md_table(case_summary),
        "",
        "## Step Summary",
        "",
        _md_table(step_summary[["entry_case_id", "stage_step", "returncode", "decision", "stdout_json_found"]]),
        "",
        "## Supergate Status",
        "",
        _md_table(gates),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{CASE_MATRIX_CHART_OUT.name}`",
        f"- `{STEP_CHART_OUT.name}`",
        f"- `{REQUEST_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(report) + "\n", encoding="utf-8")


def main(drop_dir: Path | None = None, expected_stage112_intake: int = 1) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cases = _build_cli_cases(drop_dir, expected_stage112_intake) if drop_dir is not None else _build_default_cases()
    case_rows: list[dict[str, Any]] = []
    step_rows: list[dict[str, Any]] = []
    gate_frames: list[pd.DataFrame] = []
    request_frames: list[pd.DataFrame] = []
    stage123_gate_frames: list[pd.DataFrame] = []
    for entry_case_id, case_drop_dir, expected in cases:
        case, steps, gates, request_audit, stage123_gates = _prepare_stage_case(entry_case_id, case_drop_dir, expected)
        case_rows.append(case)
        step_rows.extend(steps)
        gate_frames.append(gates)
        if not request_audit.empty:
            request_frames.append(request_audit)
        if not stage123_gates.empty:
            stage123_gates["entry_case_id_supergate"] = entry_case_id
            stage123_gate_frames.append(stage123_gates)

    restored_defaults = _restore_default_stage_outputs()
    curve = _load_curve()
    metrics = _baseline_metrics(curve)
    case_summary = pd.DataFrame(case_rows)
    step_summary = pd.DataFrame(step_rows)
    gates = pd.concat(gate_frames, ignore_index=True) if gate_frames else pd.DataFrame()
    request_audit = pd.concat(request_frames, ignore_index=True) if request_frames else pd.DataFrame()
    stage123_gate_detail = pd.concat(stage123_gate_frames, ignore_index=True) if stage123_gate_frames else pd.DataFrame()
    all_commands_ok = int(step_summary["returncode"].eq(0).all()) if not step_summary.empty else 0
    full_ready_count = int(case_summary["final_supergate_ready"].sum()) if not case_summary.empty else 0
    strategy_allowed_count = int(case_summary["strategy_use_allowed_now"].sum()) if not case_summary.empty else 0
    cli_mode = int(drop_dir is not None)
    negative_selftest_pass = int((not cli_mode) and all_commands_ok == 1 and full_ready_count == 0 and strategy_allowed_count == 0)
    decision = CLI_DECISION if cli_mode else DECISION
    if cli_mode and full_ready_count > 0:
        decision = "stage128_full_intake_supergate_ready_for_stage112_no_strategy"
    if (not cli_mode) and negative_selftest_pass == 0:
        decision = "stage128_full_intake_supergate_negative_selftests_failed"
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
                "cli_mode": cli_mode,
                "case_count": len(case_summary),
                "step_count": len(step_summary),
                "all_commands_returncode_zero": all_commands_ok,
                "negative_selftest_pass": negative_selftest_pass,
                "stage123_125_127_default_restored": restored_defaults,
                "full_supergate_ready_count": full_ready_count,
                "strategy_allowed_count": strategy_allowed_count,
                "real_w0_drop_scanned": cli_mode,
                "real_w0_data_delivered": int(cli_mode and full_ready_count > 0),
                "real_stage112_intake_allowed_now": int(cli_mode and full_ready_count > 0),
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "gate_pass_count": int(gates["pass_now"].sum()) if not gates.empty else 0,
                "gate_count": len(gates),
                "data_hard_gate_pass_count": int(gates.loc[gates["severity"].eq("data_hard"), "pass_now"].sum()) if not gates.empty else 0,
                "data_hard_gate_count": int(gates["severity"].eq("data_hard").sum()) if not gates.empty else 0,
                **metrics,
            }
        ]
    )

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(case_summary, CASE_SUMMARY_OUT)
    _write_csv(step_summary, STEP_SUMMARY_OUT)
    _write_csv(gates, GATE_STATUS_OUT)
    _write_csv(request_audit, REQUEST_AUDIT_OUT)
    if not stage123_gate_detail.empty:
        _write_csv(stage123_gate_detail, OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage123_gate_detail_{MODEL_TAG}.csv")

    _plot_official_path(curve, request_audit, case_summary)
    _plot_case_matrix(case_summary)
    _plot_step_chart(step_summary)
    _plot_request_matrix(request_audit)
    _write_report(summary, case_summary, step_summary, gates)
    _write_json = lambda path, payload: path.write_text(
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "case_summary": str(CASE_SUMMARY_OUT),
                "step_summary": str(STEP_SUMMARY_OUT),
                "gates": str(GATE_STATUS_OUT),
                "request_audit": str(REQUEST_AUDIT_OUT),
                "report": str(REPORT_OUT),
                "charts": [str(PATH_CHART_OUT), str(CASE_MATRIX_CHART_OUT), str(STEP_CHART_OUT), str(REQUEST_CHART_OUT)],
            },
            "locks": {
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, sort_keys=True))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stage127 -> Stage125 -> Stage123 W0 full intake supergate.")
    parser.add_argument("--drop-dir", type=Path, default=None, help="Real W0 drop directory. Omit to run negative selftests.")
    parser.add_argument("--expected-stage112-intake", type=int, choices=[0, 1], default=1)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    main(drop_dir=args.drop_dir, expected_stage112_intake=args.expected_stage112_intake)
