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
STAGE = "Stage146"
MODEL_TAG = "stage146_candidate_gate_chain_smoke_v1"
OUTPUT_PREFIX = "qmt_roll_stage146_c9_minrisk_candidate_gate_chain_smoke"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
TOOLS_DIR = LINE_DIR / "tools"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage146_candidate_gate_chain_smoke"

STAGE145_TOOL = TOOLS_DIR / "stage145_candidate_package_preflight_linter.py"
STAGE142_TOOL = TOOLS_DIR / "stage142_candidate_package_contract_validator.py"
STAGE143_TOOL = TOOLS_DIR / "stage143_candidate_package_operator_failure_explainer.py"

STAGE144_TEMPLATE_DIR = (
    LINE_DIR
    / "outputs"
    / "stage144_candidate_package_template_builder"
    / "candidate_package_template"
)

STAGE142_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage142_candidate_package_contract_validator"
    / "qmt_roll_stage142_c9_minrisk_candidate_package_contract_validator_summary_"
    "stage142_candidate_package_contract_validator_v1.csv"
)

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMMAND_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_command_audit_{MODEL_TAG}.csv"
STEP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_step_summary_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_chain_status_{MODEL_TAG}.png"
STEP_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_step_status_matrix_{MODEL_TAG}.png"
COMMAND_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_command_safety_matrix_{MODEL_TAG}.png"
LOCK_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lock_status_matrix_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"


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
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
        else:
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else str(value).replace("|", "\\|"))
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


def _parse_stdout_json(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        text = line.strip()
        if not text.startswith("{") or not text.endswith("}"):
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _run_command(step_id: str, command: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    started = datetime.now()
    completed = None
    result = subprocess.run(
        command,
        cwd=REPO_DIR,
        text=True,
        capture_output=True,
        check=False,
    )
    completed = datetime.now()
    parsed = _parse_stdout_json(result.stdout)
    audit = {
        "step_id": step_id,
        "command": " ".join(command),
        "returncode": result.returncode,
        "stdout_json_parsed": int(bool(parsed)),
        "stdout_tail": "\n".join(result.stdout.splitlines()[-3:]),
        "stderr_tail": "\n".join(result.stderr.splitlines()[-5:]),
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "completed_at": completed.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_sec": (completed - started).total_seconds(),
        "mutates_official_config": int(parsed.get("official_config_changed", 0)),
        "true_engine_run": int(parsed.get("true_engine_run", 0)),
        "ab_triggered": int(parsed.get("ab_triggered", 0)),
        "order_api_called": int(parsed.get("order_api_called", 0)),
        "ctp_connected": int(parsed.get("ctp_connected", 0)),
        "current_package_promotion_allowed": int(parsed.get("current_package_promotion_allowed", 0)),
    }
    return audit, parsed


def _commands(candidate_package_dir: Path) -> list[tuple[str, list[str]]]:
    python = sys.executable
    return [
        (
            "stage145_preflight_template_block_selftest",
            [
                python,
                str(STAGE145_TOOL.relative_to(REPO_DIR)),
                "--candidate-package-dir",
                str(candidate_package_dir),
                "--case-id",
                "stage146_chain_template_preflight",
            ],
        ),
        (
            "stage142_contract_validator_default_selftest",
            [python, str(STAGE142_TOOL.relative_to(REPO_DIR))],
        ),
        (
            "stage143_operator_failure_explainer_refresh",
            [python, str(STAGE143_TOOL.relative_to(REPO_DIR))],
        ),
    ]


def _step_summary(command_audit: pd.DataFrame, parsed_payloads: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for _, audit in command_audit.iterrows():
        step_id = str(audit["step_id"])
        payload = parsed_payloads.get(step_id, {})
        if step_id.startswith("stage145"):
            expected_flag = int(payload.get("linter_ready", 0) == 1 and payload.get("default_template_blocked", 0) == 1 and payload.get("preflight_pass", 1) == 0)
            expected_note = "linter ready, default template blocked"
        elif step_id.startswith("stage142"):
            expected_flag = int(payload.get("validator_ready", 0) == 1 and payload.get("current_package_promotion_allowed", 1) == 0)
            expected_note = "validator ready, no promotion"
        elif step_id.startswith("stage143"):
            expected_flag = int(payload.get("operator_runbook_ready", 0) == 1 and payload.get("current_package_promotion_allowed", 1) == 0)
            expected_note = "explainer ready, no promotion"
        else:
            expected_flag = 0
            expected_note = "unknown"
        safety_lock = int(
            int(audit["mutates_official_config"]) == 0
            and int(audit["true_engine_run"]) == 0
            and int(audit["ab_triggered"]) == 0
            and int(audit["order_api_called"]) == 0
            and int(audit["ctp_connected"]) == 0
            and int(audit["current_package_promotion_allowed"]) == 0
        )
        rows.append(
            {
                "step_id": step_id,
                "decision": payload.get("decision", ""),
                "returncode_zero": int(audit["returncode"] == 0),
                "stdout_json_parsed": int(audit["stdout_json_parsed"]),
                "expected_behavior_pass": expected_flag,
                "expected_note": expected_note,
                "safety_lock_pass": safety_lock,
                "official_config_changed": int(audit["mutates_official_config"]),
                "true_engine_run": int(audit["true_engine_run"]),
                "ab_triggered": int(audit["ab_triggered"]),
                "order_api_called": int(audit["order_api_called"]),
                "ctp_connected": int(audit["ctp_connected"]),
                "current_package_promotion_allowed": int(audit["current_package_promotion_allowed"]),
            }
        )
    return pd.DataFrame(rows)


def _gate_status(command_audit: pd.DataFrame, step_summary: pd.DataFrame) -> pd.DataFrame:
    command_count = len(command_audit)
    returncode_ok = int(command_count > 0 and int((command_audit["returncode"] == 0).sum()) == command_count)
    json_ok = int(command_count > 0 and int(command_audit["stdout_json_parsed"].sum()) == command_count)
    expected_ok = int(not step_summary.empty and int(step_summary["expected_behavior_pass"].sum()) == len(step_summary))
    safety_ok = int(not step_summary.empty and int(step_summary["safety_lock_pass"].sum()) == len(step_summary))
    no_promotion = int(command_count > 0 and int(command_audit["current_package_promotion_allowed"].sum()) == 0)
    sequence_ok = int(
        list(command_audit["step_id"])
        == [
            "stage145_preflight_template_block_selftest",
            "stage142_contract_validator_default_selftest",
            "stage143_operator_failure_explainer_refresh",
        ]
    )
    rows = [
        {"gate_id": "command_returncode_all_zero", "observed": returncode_ok, "required": 1, "pass_now": returncode_ok, "severity": "smoke_hard"},
        {"gate_id": "stdout_json_all_parsed", "observed": json_ok, "required": 1, "pass_now": json_ok, "severity": "smoke_hard"},
        {"gate_id": "expected_behavior_all_pass", "observed": expected_ok, "required": 1, "pass_now": expected_ok, "severity": "smoke_hard"},
        {"gate_id": "safety_locks_all_pass", "observed": safety_ok, "required": 1, "pass_now": safety_ok, "severity": "execution_safety_hard"},
        {"gate_id": "no_promotion_any_step", "observed": no_promotion, "required": 1, "pass_now": no_promotion, "severity": "anti_selection_hard"},
        {"gate_id": "sequence_order_stage145_142_143", "observed": sequence_ok, "required": 1, "pass_now": sequence_ok, "severity": "smoke_hard"},
    ]
    return pd.DataFrame(rows)


def _write_report(summary: pd.DataFrame, command_audit: pd.DataFrame, step_summary: pd.DataFrame, gate: pd.DataFrame) -> None:
    lines = [
        f"# {STAGE} candidate gate chain smoke",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- scope: run Stage145 preflight, Stage142 contract validator, and Stage143 failure explainer as a deterministic chain smoke.",
        "",
        "## External Research Judgment",
        "",
        "- Great Expectations Checkpoints motivate bundling validations into a single run with persisted results.",
        "- pre-commit manual run semantics motivate a one-command local gate chain.",
        "- Frictionless validation reports motivate a unified command and step audit.",
        "",
        "## Summary",
        "",
        _md_table(summary.drop(columns=["candidate_package_dir"], errors="ignore")),
        "",
        "## Step Summary",
        "",
        _md_table(step_summary),
        "",
        "## Command Audit",
        "",
        _md_table(command_audit[["step_id", "returncode", "stdout_json_parsed", "duration_sec", "current_package_promotion_allowed", "stdout_tail", "stderr_tail"]], max_rows=10),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{STEP_CHART_OUT.name}`",
        f"- `{COMMAND_CHART_OUT.name}`",
        f"- `{LOCK_CHART_OUT.name}`",
        f"- `{GATE_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _plot_official_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage146 gate chain smoke: Stage145 -> Stage142 -> Stage143", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#14532D", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#B45309", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3657D6", linewidth=1.0)
    axes[2].axhline(100, color="#333333", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    status_cols = [
        "chain_smoke_ready",
        "stage145_default_template_blocked",
        "stage142_validator_ready",
        "stage143_explainer_ready",
        "any_promotion_allowed",
        "true_engine_run_count",
        "official_config_changed",
    ]
    matrix = summary[status_cols].T
    matrix.columns = ["status"]
    matrix.plot(kind="bar", ax=axes[3], legend=False, color="#0F766E")
    axes[3].set_title("Gate chain status")
    axes[3].set_ylabel("flag / count")
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
    fig, ax = plt.subplots(figsize=(max(8.5, len(value_cols) * 1.45), max(4.8, len(matrix) * 0.62)))
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title(title)
    ax.set_xticks(np.arange(len(value_cols)))
    ax.set_xticklabels(value_cols, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=8)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage146 Stage145->Stage142->Stage143 chain smoke.")
    parser.add_argument(
        "--candidate-package-dir",
        default=str(STAGE144_TEMPLATE_DIR),
        help="Package dir for Stage145 preflight selftest. Default is Stage144 template and is expected to be blocked.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidate_package_dir = Path(args.candidate_package_dir).resolve()
    curve = _load_curve()
    command_rows: list[dict[str, Any]] = []
    parsed_payloads: dict[str, dict[str, Any]] = {}
    for step_id, command in _commands(candidate_package_dir):
        audit, parsed = _run_command(step_id, command)
        command_rows.append(audit)
        parsed_payloads[step_id] = parsed
    command_audit = pd.DataFrame(command_rows)
    step_summary = _step_summary(command_audit, parsed_payloads)
    gate = _gate_status(command_audit, step_summary)
    row142 = _read_csv(STAGE142_SUMMARY_IN)
    metrics = row142.iloc[0].to_dict() if not row142.empty else {}
    chain_smoke_ready = int(gate["pass_now"].sum() == len(gate))
    stage145_payload = parsed_payloads.get("stage145_preflight_template_block_selftest", {})
    stage142_payload = parsed_payloads.get("stage142_contract_validator_default_selftest", {})
    stage143_payload = parsed_payloads.get("stage143_operator_failure_explainer_refresh", {})
    any_promotion_allowed = int(command_audit["current_package_promotion_allowed"].sum())
    true_engine_run_count = int(command_audit["true_engine_run"].sum())
    official_config_changed_count = int(command_audit["mutates_official_config"].sum())
    decision = (
        "stage146_gate_chain_smoke_ready_no_candidate_no_strategy"
        if chain_smoke_ready and any_promotion_allowed == 0 and true_engine_run_count == 0 and official_config_changed_count == 0
        else "stage146_gate_chain_smoke_attention_required_no_strategy"
    )
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": decision,
                "official_config_changed": official_config_changed_count,
                "strategy_rule_created": 0,
                "true_engine_run_count": true_engine_run_count,
                "true_engine_run": int(true_engine_run_count > 0),
                "ab_triggered": int(command_audit["ab_triggered"].sum()),
                "order_api_called": int(command_audit["order_api_called"].sum()),
                "ctp_connected": int(command_audit["ctp_connected"].sum()),
                "chain_smoke_ready": chain_smoke_ready,
                "command_count": len(command_audit),
                "command_returncode_zero_count": int((command_audit["returncode"] == 0).sum()),
                "stdout_json_parsed_count": int(command_audit["stdout_json_parsed"].sum()),
                "step_expected_behavior_pass_count": int(step_summary["expected_behavior_pass"].sum()),
                "step_safety_lock_pass_count": int(step_summary["safety_lock_pass"].sum()),
                "gate_pass_count": int(gate["pass_now"].sum()),
                "gate_count": len(gate),
                "stage145_default_template_blocked": int(stage145_payload.get("default_template_blocked", 0)),
                "stage145_preflight_pass": int(stage145_payload.get("preflight_pass", -1)),
                "stage142_validator_ready": int(stage142_payload.get("validator_ready", 0)),
                "stage142_validation_expectation_pass_count": int(stage142_payload.get("validation_expectation_pass_count", 0)),
                "stage143_explainer_ready": int(stage143_payload.get("operator_runbook_ready", 0)),
                "any_promotion_allowed": any_promotion_allowed,
                "current_package_promotion_allowed": any_promotion_allowed,
                "real_candidate_package_supplied": 0,
                "real_stage112_intake_allowed_now": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "candidate_package_dir": str(candidate_package_dir),
                "end_equity": float(metrics.get("end_equity", np.nan)),
                "total_return_pct": float(metrics.get("total_return_pct", np.nan)),
                "max_drawdown_pct": float(metrics.get("max_drawdown_pct", np.nan)),
                "sharpe": float(metrics.get("sharpe", np.nan)),
                "total_slippage": float(metrics.get("total_slippage", np.nan)),
                "total_trade_count": float(metrics.get("total_trade_count", np.nan)),
                "closed_lot_win_rate_pct": float(metrics.get("closed_lot_win_rate_pct", np.nan)),
                "max_broker10_margin_to_equity_pct": float(metrics.get("max_broker10_margin_to_equity_pct", np.nan)),
            }
        ]
    )
    _write_csv(summary, SUMMARY_OUT)
    _write_csv(command_audit, COMMAND_OUT)
    _write_csv(step_summary, STEP_OUT)
    _write_csv(gate, GATE_OUT)
    _write_report(summary, command_audit, step_summary, gate)
    _plot_official_path(curve, summary)
    _plot_matrix(
        step_summary,
        "step_id",
        ["returncode_zero", "stdout_json_parsed", "expected_behavior_pass", "safety_lock_pass"],
        "Stage146 step status",
        STEP_CHART_OUT,
    )
    _plot_matrix(
        command_audit,
        "step_id",
        ["returncode", "stdout_json_parsed", "mutates_official_config", "true_engine_run", "ab_triggered", "order_api_called", "ctp_connected", "current_package_promotion_allowed"],
        "Stage146 command safety",
        COMMAND_CHART_OUT,
    )
    _plot_matrix(
        step_summary,
        "step_id",
        ["official_config_changed", "true_engine_run", "ab_triggered", "order_api_called", "ctp_connected", "current_package_promotion_allowed"],
        "Stage146 lock status",
        LOCK_CHART_OUT,
    )
    _plot_matrix(gate, "gate_id", ["pass_now"], "Stage146 gate status", GATE_CHART_OUT)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "inputs": {
                "candidate_package_dir": str(candidate_package_dir),
                "stage145_tool": str(STAGE145_TOOL),
                "stage142_tool": str(STAGE142_TOOL),
                "stage143_tool": str(STAGE143_TOOL),
            },
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "command_audit": str(COMMAND_OUT),
                "step_summary": str(STEP_OUT),
                "gate_status": str(GATE_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(STEP_CHART_OUT),
                    str(COMMAND_CHART_OUT),
                    str(LOCK_CHART_OUT),
                    str(GATE_CHART_OUT),
                ],
            },
            "locks": {
                "official_config_changed": official_config_changed_count,
                "strategy_rule_created": 0,
                "true_engine_run_count": true_engine_run_count,
                "ab_triggered": int(command_audit["ab_triggered"].sum()),
                "order_api_called": int(command_audit["order_api_called"].sum()),
                "ctp_connected": int(command_audit["ctp_connected"].sum()),
                "current_package_promotion_allowed": any_promotion_allowed,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
