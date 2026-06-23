from __future__ import annotations

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
STAGE = "Stage138"
MODEL_TAG = "stage138_wave0_unattended_watch_smoke_v1"
OUTPUT_PREFIX = "qmt_roll_stage138_c9_minrisk_wave0_unattended_watch_smoke"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage138_wave0_unattended_watch_smoke"

PYTHON_BIN = REPO_DIR / ".py311" / "bin" / "python"
STAGE137_TOOL = LINE_DIR / "tools" / "stage137_wave0_watch_inbox_trigger_selftest.py"
STAGE136_TOOL = LINE_DIR / "tools" / "stage136_wave0_watch_inbox_arrival_monitor.py"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE134_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage134_wave0_total_gate_cli_entry_selftest"
    / "qmt_roll_stage134_c9_minrisk_wave0_total_gate_cli_entry_selftest_summary_"
    "stage134_wave0_total_gate_cli_entry_selftest_v1.csv"
)
STAGE136_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage136_wave0_watch_inbox_arrival_monitor"
    / "qmt_roll_stage136_c9_minrisk_wave0_watch_inbox_arrival_monitor_summary_"
    "stage136_wave0_watch_inbox_arrival_monitor_v1.csv"
)
STAGE137_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage137_wave0_watch_inbox_trigger_selftest"
    / "qmt_roll_stage137_c9_minrisk_wave0_watch_inbox_trigger_selftest_summary_"
    "stage137_wave0_watch_inbox_trigger_selftest_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMMAND_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_command_audit_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_smoke_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_smoke_status_{MODEL_TAG}.png"
COMMAND_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_command_dependency_matrix_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"
HISTORY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_watch_history_tail_{MODEL_TAG}.png"


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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
    stage134 = _read_csv(STAGE134_SUMMARY_IN)
    if not stage134.empty:
        row = stage134.iloc[0]
        return {
            "end_equity": float(row.get("end_equity", np.nan)),
            "total_return_pct": float(row.get("total_return_pct", np.nan)),
            "max_drawdown_pct": float(row.get("max_drawdown_pct", np.nan)),
            "sharpe": float(row.get("sharpe", np.nan)),
            "total_slippage": float(row.get("total_slippage", np.nan)),
            "total_trade_count": float(row.get("total_trade_count", np.nan)),
            "closed_lot_win_rate_pct": float(row.get("closed_lot_win_rate_pct", np.nan)),
            "max_broker10_margin_to_equity_pct": float(row.get("max_broker10_margin_to_equity_pct", np.nan)),
        }
    first_equity = float(curve["account_equity"].dropna().iloc[0])
    end_equity = float(curve["account_equity"].dropna().iloc[-1])
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


def _parse_json_from_stdout(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.strip().splitlines()):
        text = line.strip()
        if not text.startswith("{"):
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            continue
    return {}


def _run_command(step_order: int, step_id: str, command: list[str], dependency_passed: int) -> dict[str, Any]:
    if not dependency_passed:
        return {
            "step_order": step_order,
            "step_id": step_id,
            "command": " ".join(command),
            "dependency_passed": 0,
            "executed": 0,
            "returncode": -1,
            "stdout_json_parsed": 0,
            "decision": "skipped_due_failed_dependency",
            "pass_now": 0,
            "blocks_downstream_if_failed": 1,
            "stdout_tail": "",
            "stderr_tail": "",
        }
    result = subprocess.run(command, cwd=REPO_DIR, text=True, capture_output=True, check=False)
    parsed = _parse_json_from_stdout(result.stdout)
    pass_now = int(result.returncode == 0 and bool(parsed))
    return {
        "step_order": step_order,
        "step_id": step_id,
        "command": " ".join(command),
        "dependency_passed": 1,
        "executed": 1,
        "returncode": int(result.returncode),
        "stdout_json_parsed": int(bool(parsed)),
        "decision": str(parsed.get("decision", "")),
        "pass_now": pass_now,
        "blocks_downstream_if_failed": 1,
        "stdout_tail": "\n".join(result.stdout.strip().splitlines()[-3:]),
        "stderr_tail": "\n".join(result.stderr.strip().splitlines()[-3:]),
        **{f"json_{key}": value for key, value in parsed.items() if key in {
            "selftest_pass",
            "case_pass_count",
            "expectation_pass_count",
            "monitor_ready",
            "prior_snapshot_available",
            "arrival_detected_now",
            "stage125_candidate_count",
            "candidate_ready_count",
            "stage133_release_allowed_now",
            "real_w0_data_delivered",
            "stage125_command_executed_count",
            "stage133_command_executed_count",
        }},
    }


def _gate_status(command_audit: pd.DataFrame, stage136_summary: pd.DataFrame, stage137_summary: pd.DataFrame) -> pd.DataFrame:
    stage137_pass = int(not stage137_summary.empty and int(stage137_summary.iloc[0].get("selftest_pass", 0)) == 1)
    stage137_no_downstream = int(
        not stage137_summary.empty
        and int(stage137_summary.iloc[0].get("stage125_command_executed_count", -1)) == 0
        and int(stage137_summary.iloc[0].get("stage133_command_executed_count", -1)) == 0
    )
    stage136_ready = int(not stage136_summary.empty and int(stage136_summary.iloc[0].get("monitor_ready", 0)) == 1)
    stage136_release_locked = int(
        not stage136_summary.empty
        and int(stage136_summary.iloc[0].get("stage133_release_allowed_now", -1)) == 0
        and int(stage136_summary.iloc[0].get("true_engine_allowed", -1)) == 0
    )
    stage136_no_arrival = int(
        not stage136_summary.empty
        and int(stage136_summary.iloc[0].get("arrival_detected_now", -1)) == 0
        and int(stage136_summary.iloc[0].get("candidate_ready_count", -1)) == 0
    )
    all_commands_ok = int(not command_audit.empty and int(command_audit["pass_now"].sum()) == len(command_audit))
    rows = [
        {
            "gate_id": "stage137_selftest_passed",
            "observed": stage137_pass,
            "required": 1,
            "pass_now": stage137_pass,
            "severity": "smoke_hard",
        },
        {
            "gate_id": "stage137_no_stage125_133_execution",
            "observed": stage137_no_downstream,
            "required": 1,
            "pass_now": stage137_no_downstream,
            "severity": "anti_selection_hard",
        },
        {
            "gate_id": "stage136_monitor_ready",
            "observed": stage136_ready,
            "required": 1,
            "pass_now": stage136_ready,
            "severity": "smoke_hard",
        },
        {
            "gate_id": "stage136_release_locked",
            "observed": stage136_release_locked,
            "required": 1,
            "pass_now": stage136_release_locked,
            "severity": "anti_selection_hard",
        },
        {
            "gate_id": "stage136_no_real_w0_arrival_now",
            "observed": stage136_no_arrival,
            "required": 1,
            "pass_now": stage136_no_arrival,
            "severity": "data_state",
        },
        {
            "gate_id": "command_chain_returncode_json_ok",
            "observed": all_commands_ok,
            "required": 1,
            "pass_now": all_commands_ok,
            "severity": "smoke_hard",
        },
    ]
    return pd.DataFrame(rows)


def _write_report(summary: pd.DataFrame, command_audit: pd.DataFrame, gate: pd.DataFrame) -> None:
    report = [
        f"# {STAGE} unattended W0 watch smoke",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- scope: run Stage137 trigger selftest, then Stage136 watched inbox monitor if the dependency passes; no Stage125/133 execution, no strategy rule, true engine, A/B, CTP, order API, or official config change.",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Command Audit",
        "",
        _md_table(command_audit.drop(columns=["stdout_tail", "stderr_tail"], errors="ignore")),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{COMMAND_CHART_OUT.name}`",
        f"- `{GATE_CHART_OUT.name}`",
        f"- `{HISTORY_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(report) + "\n", encoding="utf-8")


def _plot_official_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage138 unattended W0 watch smoke: dependency chain, release locked", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#1f5d4a", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#C2410C", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3B5BDB", linewidth=1.0)
    axes[2].axhline(100, color="#333333", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    cols = ["smoke_pass", "stage137_selftest_pass", "stage136_monitor_ready", "stage133_release_allowed_now"]
    plot = summary[cols].T
    plot.columns = ["status"]
    plot.plot(kind="bar", ax=axes[3], legend=False, color="#0F766E")
    axes[3].set_title("Smoke/release status")
    axes[3].set_ylabel("count / flag")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_matrix(frame: pd.DataFrame, index_col: str, value_cols: list[str], title: str, path: Path) -> None:
    matrix = frame.set_index(index_col)[value_cols].copy()
    for column in value_cols:
        matrix[column] = pd.to_numeric(matrix[column], errors="coerce").fillna(0).clip(upper=1)
    data = matrix.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(max(8.5, len(value_cols) * 1.6), max(4.5, len(matrix) * 0.65)))
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title(title)
    ax.set_xticks(np.arange(len(value_cols)))
    ax.set_xticklabels(value_cols, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=9)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


def _plot_history_tail(stage136_summary: pd.DataFrame) -> None:
    history_path = (
        LINE_DIR
        / "outputs"
        / "stage136_wave0_watch_inbox_arrival_monitor"
        / "qmt_roll_stage136_c9_minrisk_wave0_watch_inbox_arrival_monitor_watch_history_"
        "stage136_wave0_watch_inbox_arrival_monitor_v1.csv"
    )
    history = _read_csv(history_path)
    fig, ax = plt.subplots(figsize=(11, 5))
    if history.empty:
        ax.text(0.5, 0.5, "empty history", ha="center", va="center")
        ax.set_axis_off()
    else:
        tail = history.tail(12).copy().reset_index(drop=True)
        x = np.arange(len(tail))
        ax.plot(x, pd.to_numeric(tail["best_known_file_count"], errors="coerce").fillna(0), marker="o", label="known files")
        ax.plot(x, pd.to_numeric(tail["candidate_ready_count"], errors="coerce").fillna(0), marker="s", label="ready candidates")
        ax.plot(x, pd.to_numeric(tail["stage133_release_allowed_now"], errors="coerce").fillna(0), marker="x", label="release allowed")
        ax.set_xticks(x)
        ax.set_xticklabels(tail["snapshot_id"].astype(str), rotation=30, ha="right", fontsize=8)
        ax.set_title("Stage136 watch history tail after Stage138 smoke")
        ax.set_ylabel("count / flag")
        ax.grid(alpha=0.25)
        ax.legend()
    fig.tight_layout()
    fig.savefig(HISTORY_CHART_OUT, dpi=170)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    metrics = _baseline_metrics(curve)
    python = str(PYTHON_BIN if PYTHON_BIN.exists() else Path(sys.executable))
    stage137_command = [python, str(STAGE137_TOOL.relative_to(REPO_DIR))]
    first = _run_command(1, "stage137_trigger_selftest", stage137_command, 1)
    stage137_dependency_passed = int(
        first["pass_now"] == 1
        and int(first.get("json_selftest_pass", 0) or 0) == 1
        and int(first.get("json_stage125_command_executed_count", 0) or 0) == 0
        and int(first.get("json_stage133_command_executed_count", 0) or 0) == 0
    )
    stage136_command = [python, str(STAGE136_TOOL.relative_to(REPO_DIR))]
    second = _run_command(2, "stage136_watch_inbox_monitor", stage136_command, stage137_dependency_passed)
    command_audit = pd.DataFrame([first, second])
    stage136_summary = _read_csv(STAGE136_SUMMARY_IN)
    stage137_summary = _read_csv(STAGE137_SUMMARY_IN)
    gate = _gate_status(command_audit, stage136_summary, stage137_summary)

    gate_pass = int(gate["pass_now"].sum())
    gate_count = len(gate)
    stage137_selftest_pass = int(not stage137_summary.empty and int(stage137_summary.iloc[0].get("selftest_pass", 0)) == 1)
    stage136_monitor_ready = int(not stage136_summary.empty and int(stage136_summary.iloc[0].get("monitor_ready", 0)) == 1)
    arrival_detected_now = int(stage136_summary.iloc[0].get("arrival_detected_now", 0)) if not stage136_summary.empty else 0
    candidate_ready_count = int(stage136_summary.iloc[0].get("candidate_ready_count", 0)) if not stage136_summary.empty else 0
    stage125_candidate_count = int(stage136_summary.iloc[0].get("stage125_candidate_count", 0)) if not stage136_summary.empty else 0
    best_known_file_count = int(stage136_summary.iloc[0].get("best_known_file_count", 0)) if not stage136_summary.empty else 0
    expected_file_count = int(stage136_summary.iloc[0].get("expected_file_count", 0)) if not stage136_summary.empty else 0
    stage133_release_allowed_now = 0
    smoke_pass = int(gate_pass == gate_count and stage137_selftest_pass == 1 and stage136_monitor_ready == 1)
    if smoke_pass and not arrival_detected_now:
        decision = "stage138_unattended_watch_smoke_passed_waiting_no_real_w0_no_strategy"
    elif smoke_pass and arrival_detected_now and candidate_ready_count == 0:
        decision = "stage138_unattended_watch_smoke_passed_partial_w0_detected_stage125_only_no_strategy"
    elif smoke_pass and candidate_ready_count > 0:
        decision = "stage138_unattended_watch_smoke_passed_complete_w0_prompt_stage125_stage133_no_strategy"
    else:
        decision = "stage138_unattended_watch_smoke_failed_attention_no_strategy"

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
                "smoke_pass": smoke_pass,
                "command_count": len(command_audit),
                "command_pass_count": int(command_audit["pass_now"].sum()),
                "gate_pass_count": gate_pass,
                "gate_count": gate_count,
                "stage137_dependency_passed": stage137_dependency_passed,
                "stage137_selftest_pass": stage137_selftest_pass,
                "stage137_case_pass_count": int(stage137_summary.iloc[0].get("case_pass_count", 0)) if not stage137_summary.empty else 0,
                "stage137_expectation_pass_count": int(stage137_summary.iloc[0].get("expectation_pass_count", 0)) if not stage137_summary.empty else 0,
                "stage137_expectation_count": int(stage137_summary.iloc[0].get("expectation_count", 0)) if not stage137_summary.empty else 0,
                "stage137_stage125_command_executed_count": int(stage137_summary.iloc[0].get("stage125_command_executed_count", -1))
                if not stage137_summary.empty
                else -1,
                "stage137_stage133_command_executed_count": int(stage137_summary.iloc[0].get("stage133_command_executed_count", -1))
                if not stage137_summary.empty
                else -1,
                "stage136_monitor_ready": stage136_monitor_ready,
                "stage136_prior_snapshot_available": int(stage136_summary.iloc[0].get("prior_snapshot_available", 0)) if not stage136_summary.empty else 0,
                "stage136_arrival_detected_now": arrival_detected_now,
                "stage136_stage125_candidate_count": stage125_candidate_count,
                "stage136_candidate_ready_count": candidate_ready_count,
                "stage136_best_known_file_count": best_known_file_count,
                "stage136_expected_file_count": expected_file_count,
                "stage133_release_allowed_now": stage133_release_allowed_now,
                "real_w0_data_delivered": int(candidate_ready_count > 0),
                "real_stage112_intake_allowed_now": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                **metrics,
            }
        ]
    )

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(command_audit, COMMAND_OUT)
    _write_csv(gate, GATE_OUT)
    _write_report(summary, command_audit, gate)
    _plot_official_path(curve, summary)
    _plot_matrix(
        command_audit,
        "step_id",
        ["dependency_passed", "executed", "stdout_json_parsed", "pass_now"],
        "Stage138 command dependency matrix",
        COMMAND_CHART_OUT,
    )
    _plot_matrix(gate, "gate_id", ["pass_now"], "Stage138 smoke gate status", GATE_CHART_OUT)
    _plot_history_tail(stage136_summary)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "command_audit": str(COMMAND_OUT),
                "gate_status": str(GATE_OUT),
                "report": str(REPORT_OUT),
                "charts": [str(PATH_CHART_OUT), str(COMMAND_CHART_OUT), str(GATE_CHART_OUT), str(HISTORY_CHART_OUT)],
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


if __name__ == "__main__":
    main()
