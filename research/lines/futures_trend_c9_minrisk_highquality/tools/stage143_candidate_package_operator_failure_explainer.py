from __future__ import annotations

import argparse
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
STAGE = "Stage143"
MODEL_TAG = "stage143_candidate_package_operator_failure_explainer_v1"
OUTPUT_PREFIX = "qmt_roll_stage143_c9_minrisk_candidate_package_operator_failure_explainer"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
TOOLS_DIR = LINE_DIR / "tools"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage143_candidate_package_operator_failure_explainer"

STAGE142_DIR = LINE_DIR / "outputs" / "stage142_candidate_package_contract_validator"
STAGE142_TOOL = TOOLS_DIR / "stage142_candidate_package_contract_validator.py"
STAGE142_PREFIX = "qmt_roll_stage142_c9_minrisk_candidate_package_contract_validator"
STAGE142_TAG = "stage142_candidate_package_contract_validator_v1"
STAGE142_SUMMARY_IN = STAGE142_DIR / f"{STAGE142_PREFIX}_summary_{STAGE142_TAG}.csv"
STAGE142_SCHEMA_IN = STAGE142_DIR / f"{STAGE142_PREFIX}_candidate_package_schema_{STAGE142_TAG}.json"
STAGE142_VALIDATION_IN = STAGE142_DIR / f"{STAGE142_PREFIX}_validation_audit_{STAGE142_TAG}.csv"
STAGE142_GATE_IN = STAGE142_DIR / f"{STAGE142_PREFIX}_gate_status_{STAGE142_TAG}.csv"
STAGE142_REPORT_IN = STAGE142_DIR / f"{STAGE142_PREFIX}_report_{STAGE142_TAG}.md"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMMAND_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_operator_command_manifest_{MODEL_TAG}.csv"
CATALOG_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_failure_reason_catalog_{MODEL_TAG}.csv"
TRIAGE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_sample_triage_cases_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
RUNBOOK_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_operator_runbook_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_operator_status_{MODEL_TAG}.png"
FAILURE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_failure_reason_matrix_{MODEL_TAG}.png"
COMMAND_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_operator_command_safety_matrix_{MODEL_TAG}.png"
TRIAGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_sample_triage_matrix_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"

FAILURE_SPECS = [
    (
        "MISSING_PACKAGE",
        "package_exists",
        0,
        "candidate package directory is missing or unreadable",
        "检查 --candidate-package-dir 是否指向真实候选包根目录，不允许用 fixture 代替。",
        100,
    ),
    (
        "MISSING_OR_INVALID_MANIFEST",
        "manifest_parse_ok",
        0,
        "manifest.json is missing required provenance fields",
        "补齐 manifest.json：candidate_id、line_id、created_at、predeclared_spec_hash、source_stage、true_engine_run_id、provenance_note 等字段。",
        90,
    ),
    (
        "SUMMARY_SCHEMA_MISSING_FIELDS",
        "summary_schema_pass",
        0,
        "summary.csv is missing required metric fields",
        "按 Stage142 schema 补齐收益、回撤、broker10、交易次数、胜率和滑点字段。",
        85,
    ),
    (
        "EVIDENCE_SCHEMA_MISSING_IDS",
        "evidence_schema_pass",
        0,
        "evidence.csv is missing required evidence ids",
        "补齐 Stage141 要求的点时化数据、true engine、OOS、leave-one-year、product-family、monthly-start、right-tail、bottom-loss、PBO/DSR 等证据行。",
        80,
    ),
    (
        "VISUAL_ARTIFACTS_INCOMPLETE",
        "visual_artifacts_pass",
        0,
        "required visual artifacts are incomplete",
        "补齐 equity、drawdown、broker10、minute K atlas、right-tail/bottom-loss atlas；没有视觉证据不能晋级。",
        75,
    ),
    (
        "RETURN_GATE_FAIL",
        "return_gate",
        0,
        "candidate does not retain at least 80% of official total return",
        "停止晋级；不得用参数扫描、样本剔除或年份/品种补丁救援。",
        70,
    ),
    (
        "DRAWDOWN_GATE_FAIL",
        "drawdown_gate",
        0,
        "candidate does not improve max drawdown by the Stage141 hard threshold",
        "停止晋级；不能把局部窗口改善包装成全局低回撤候选。",
        70,
    ),
    (
        "BROKER10_GATE_FAIL",
        "broker_gate",
        0,
        "candidate worsens broker10 hard cap",
        "停止晋级；先做保证金压力归因，不得接入正式候选。",
        65,
    ),
    (
        "EVIDENCE_NOT_ALL_PASS",
        "all_evidence_pass",
        0,
        "one or more evidence rows are present but not passing",
        "逐项补证据；任何缺 OOS、视觉、PBO/DSR 或 no-rescue 证明都不能晋级。",
        60,
    ),
    (
        "SYNTHETIC_CASE_BLOCKED",
        "synthetic_case",
        1,
        "synthetic fixture is only allowed for selftest, never for promotion",
        "只能用于 validator 自测；真实候选必须来自预声明、点时化、真实引擎回放。",
        55,
    ),
    (
        "FORBIDDEN_FIXTURE_MARKER",
        "fixture_marker_blocked",
        1,
        "fixture or synthetic marker is present in candidate provenance",
        "移除伪候选；若是真实包，重新生成 provenance，不能沿用 Stage131/Stage142 fixture 资产。",
        55,
    ),
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


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _clean_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value)


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


def _operator_command_manifest(candidate_placeholder: str) -> pd.DataFrame:
    rows = [
        {
            "command_id": "compile_stage142_validator",
            "command": f".py311/bin/python -m py_compile {STAGE142_TOOL.relative_to(REPO_DIR)}",
            "purpose": "确认 Stage142 validator 语法可执行。",
            "allowed_now": 1,
            "mutates_official_config": 0,
            "true_engine_run": 0,
            "ab_triggered": 0,
            "order_api_called": 0,
            "ctp_connected": 0,
            "expected_success_signal": "returncode=0",
        },
        {
            "command_id": "run_stage142_default_selftest",
            "command": f".py311/bin/python {STAGE142_TOOL.relative_to(REPO_DIR)}",
            "purpose": "跑默认 no_package + fixture selftest，确认 validator 自身闸门正常。",
            "allowed_now": 1,
            "mutates_official_config": 0,
            "true_engine_run": 0,
            "ab_triggered": 0,
            "order_api_called": 0,
            "ctp_connected": 0,
            "expected_success_signal": "validator_ready=1,current_package_promotion_allowed=0",
        },
        {
            "command_id": "validate_real_candidate_package",
            "command": f".py311/bin/python {STAGE142_TOOL.relative_to(REPO_DIR)} --candidate-package-dir {candidate_placeholder} --case-id real_candidate_YYYYMMDD",
            "purpose": "验证未来真实候选包。默认期望仍不自动 promotion，人工读取失败原因后再决定是否进入 Stage141/true-engine 证据复核。",
            "allowed_now": 1,
            "mutates_official_config": 0,
            "true_engine_run": 0,
            "ab_triggered": 0,
            "order_api_called": 0,
            "ctp_connected": 0,
            "expected_success_signal": "validation_audit 中候选 case 的 would_pass_if_real/promotion_allowed 明确给出",
        },
        {
            "command_id": "inspect_stage142_summary",
            "command": f"sed -n '1,5p' {STAGE142_SUMMARY_IN.relative_to(REPO_DIR)}",
            "purpose": "检查 Stage142 当前总闸门状态。",
            "allowed_now": 1,
            "mutates_official_config": 0,
            "true_engine_run": 0,
            "ab_triggered": 0,
            "order_api_called": 0,
            "ctp_connected": 0,
            "expected_success_signal": "decision 与 validator_ready 字段可见",
        },
        {
            "command_id": "inspect_stage142_validation_audit",
            "command": f"sed -n '1,20p' {STAGE142_VALIDATION_IN.relative_to(REPO_DIR)}",
            "purpose": "查看每个 case 的失败字段和 promotion_allowed。",
            "allowed_now": 1,
            "mutates_official_config": 0,
            "true_engine_run": 0,
            "ab_triggered": 0,
            "order_api_called": 0,
            "ctp_connected": 0,
            "expected_success_signal": "每个 case 均有 hard flags",
        },
    ]
    return pd.DataFrame(rows)


def _failure_catalog(validation: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if validation.empty:
        return pd.DataFrame(rows)
    for _, row in validation.iterrows():
        case_id = str(row.get("case_id", ""))
        for reason_code, flag_column, trigger_value, description, operator_action, priority in FAILURE_SPECS:
            observed = row.get(flag_column, np.nan)
            if pd.isna(observed):
                continue
            try:
                observed_int = int(observed)
            except (TypeError, ValueError):
                continue
            if observed_int == trigger_value:
                rows.append(
                    {
                        "case_id": case_id,
                        "candidate_id": _clean_text(row.get("candidate_id", "")),
                        "reason_code": reason_code,
                        "flag_column": flag_column,
                        "observed": observed_int,
                        "hard_stop": 1,
                        "priority": priority,
                        "description": description,
                        "operator_action": operator_action,
                    }
                )
    return pd.DataFrame(rows).sort_values(["case_id", "priority", "reason_code"], ascending=[True, False, True]).reset_index(drop=True)


def _triage_cases(validation: pd.DataFrame, catalog: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in validation.iterrows():
        case_id = str(row.get("case_id", ""))
        reasons = catalog[catalog["case_id"] == case_id].copy() if not catalog.empty else pd.DataFrame()
        if reasons.empty:
            primary_reason = "PASSING_REAL_PACKAGE_REQUIRES_MANUAL_REVIEW"
            action = "若 promotion_allowed=1，先冻结 stage record，再按 Stage141 合同做人工复核，不能自动改 official config。"
            hard_stop_count = 0
        else:
            reasons = reasons.sort_values(["priority", "reason_code"], ascending=[False, True])
            primary_reason = str(reasons.iloc[0]["reason_code"])
            action = str(reasons.iloc[0]["operator_action"])
            hard_stop_count = int(reasons["hard_stop"].sum())
        rows.append(
            {
                "case_id": case_id,
                "candidate_id": _clean_text(row.get("candidate_id", "")),
                "would_pass_if_real": int(row.get("would_pass_if_real", 0)),
                "promotion_allowed": int(row.get("promotion_allowed", 0)),
                "expectation_pass": int(row.get("expectation_pass", 0)),
                "hard_stop_count": hard_stop_count,
                "primary_reason": primary_reason,
                "next_operator_action": action,
            }
        )
    return pd.DataFrame(rows)


def _gate_status(stage142_summary: pd.DataFrame, commands: pd.DataFrame, catalog: pd.DataFrame, triage: pd.DataFrame) -> pd.DataFrame:
    if stage142_summary.empty:
        stage142_ready = 0
        stage142_no_promotion = 0
    else:
        row = stage142_summary.iloc[0]
        stage142_ready = int(row.get("validator_ready", 0))
        stage142_no_promotion = int(row.get("current_package_promotion_allowed", 1) == 0)
    command_safe = int(
        not commands.empty
        and int(commands[["mutates_official_config", "true_engine_run", "ab_triggered", "order_api_called", "ctp_connected"]].sum().sum()) == 0
    )
    rows = [
        {
            "gate_id": "stage142_validator_ready",
            "observed": stage142_ready,
            "required": 1,
            "pass_now": stage142_ready,
            "severity": "dependency_hard",
        },
        {
            "gate_id": "stage142_no_current_promotion",
            "observed": stage142_no_promotion,
            "required": 1,
            "pass_now": stage142_no_promotion,
            "severity": "anti_selection_hard",
        },
        {
            "gate_id": "operator_commands_safe",
            "observed": command_safe,
            "required": 1,
            "pass_now": command_safe,
            "severity": "execution_safety_hard",
        },
        {
            "gate_id": "failure_catalog_nonempty",
            "observed": int(len(catalog) > 0),
            "required": 1,
            "pass_now": int(len(catalog) > 0),
            "severity": "explainability_hard",
        },
        {
            "gate_id": "triage_all_cases_covered",
            "observed": int(len(triage) > 0 and triage["case_id"].nunique() == len(triage)),
            "required": 1,
            "pass_now": int(len(triage) > 0 and triage["case_id"].nunique() == len(triage)),
            "severity": "explainability_hard",
        },
    ]
    return pd.DataFrame(rows)


def _schema_requirements(schema: dict[str, Any]) -> dict[str, list[str]]:
    properties = schema.get("properties", {})
    return {
        "manifest_required": list(properties.get("manifest.json", {}).get("required", [])),
        "summary_required": list(properties.get("summary.csv", {}).get("required_columns", [])),
        "evidence_required": list(properties.get("evidence.csv", {}).get("required_evidence_id", [])),
        "visual_required": list(properties.get("visual_artifacts", {}).get("required_artifact_id", [])),
    }


def _write_runbook(
    summary: pd.DataFrame,
    commands: pd.DataFrame,
    catalog: pd.DataFrame,
    triage: pd.DataFrame,
    gate: pd.DataFrame,
    schema: dict[str, Any],
    candidate_placeholder: str,
) -> None:
    requirements = _schema_requirements(schema)
    stage142_decision = ""
    if not summary.empty:
        stage142_decision = str(summary.iloc[0].get("stage142_decision", ""))
    lines = [
        f"# {STAGE} candidate package operator runbook",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        f"- stage142_dependency_decision: `{stage142_decision}`",
        "- scope: explain Stage142 candidate package failures and provide safe operator commands; no strategy rule, no true engine, no A/B, no official config change.",
        "",
        "## External Research Judgment",
        "",
        "- Frictionless validation reports separate machine-readable reports from user-readable errors; Stage143 follows that split with CSV catalogs plus this runbook.",
        "- JSON Schema treats validation as structural assertions; Stage143 keeps the Stage142 schema as the executable contract instead of rewriting it in prose.",
        "- Great Expectations Data Docs motivate a readable validation result surface; Stage143 provides the local markdown equivalent without adding dependency.",
        "",
        "## Safe Command Sequence",
        "",
        _md_table(commands[["command_id", "command", "purpose", "expected_success_signal"]]),
        "",
        "## Candidate Package Minimum Tree",
        "",
        "```text",
        f"{candidate_placeholder}/",
        "  manifest.json",
        "  summary.csv",
        "  evidence.csv",
        "  artifacts/",
        "    equity_curve.*",
        "    drawdown_curve.*",
        "    broker10_curve.*",
        "    minute_k_atlas.*",
        "    right_tail_bottom_loss_atlas.*",
        "```",
        "",
        "## Required Fields",
        "",
        "- manifest.json: " + ", ".join(f"`{item}`" for item in requirements["manifest_required"]),
        "- summary.csv: " + ", ".join(f"`{item}`" for item in requirements["summary_required"]),
        "- evidence.csv evidence_id: " + ", ".join(f"`{item}`" for item in requirements["evidence_required"]),
        "- visual artifacts: " + ", ".join(f"`{item}`" for item in requirements["visual_required"]),
        "",
        "## Sample Triage",
        "",
        _md_table(triage),
        "",
        "## Failure Reason Catalog",
        "",
        _md_table(catalog[["case_id", "reason_code", "hard_stop", "description", "operator_action"]], max_rows=30),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
        "## Hard Rules",
        "",
        "- `promotion_allowed=0` means stop. Do not run true engine, A/B, or official config changes from that package.",
        "- `synthetic_case=1` or any forbidden fixture marker means the package is selftest-only, even if metrics pass.",
        "- Missing visual artifacts are hard failures; this research line requires curve and atlas inspection, not only scalar metrics.",
        "- If a future real package returns `promotion_allowed=1`, freeze a new stage record first and manually verify Stage141 evidence before any candidate discussion.",
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{FAILURE_CHART_OUT.name}`",
        f"- `{COMMAND_CHART_OUT.name}`",
        f"- `{TRIAGE_CHART_OUT.name}`",
        f"- `{GATE_CHART_OUT.name}`",
    ]
    RUNBOOK_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _plot_official_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage143 operator runbook: candidate packages remain blocked until evidence is real", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#155E75", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#B45309", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3657D6", linewidth=1.0)
    axes[2].axhline(100, color="#333333", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    status_cols = [
        "operator_runbook_ready",
        "stage142_validator_ready",
        "failure_catalog_ready",
        "current_package_promotion_allowed",
        "true_engine_run",
        "official_config_changed",
    ]
    matrix = summary[status_cols].T
    matrix.columns = ["status"]
    matrix.plot(kind="bar", ax=axes[3], legend=False, color="#0F766E")
    axes[3].set_title("Operator gate status")
    axes[3].set_ylabel("flag")
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
    fig, ax = plt.subplots(figsize=(max(8.5, len(value_cols) * 1.4), max(4.8, len(matrix) * 0.55)))
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


def _plot_failure_matrix(validation: pd.DataFrame, catalog: pd.DataFrame) -> None:
    reason_codes = [item[0] for item in FAILURE_SPECS]
    rows = []
    for case_id in validation["case_id"].astype(str).tolist():
        row = {"case_id": case_id}
        for reason_code in reason_codes:
            row[reason_code] = int(not catalog.empty and ((catalog["case_id"] == case_id) & (catalog["reason_code"] == reason_code)).any())
        rows.append(row)
    _plot_matrix(pd.DataFrame(rows), "case_id", reason_codes, "Stage143 failure reason matrix", FAILURE_CHART_OUT)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage143 operator runbook and failure explainer for Stage142 candidate packages.")
    parser.add_argument(
        "--candidate-placeholder",
        default="<candidate_package_dir>",
        help="Placeholder path shown in generated runbook commands.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    stage142_summary = _read_csv(STAGE142_SUMMARY_IN)
    validation = _read_csv(STAGE142_VALIDATION_IN)
    stage142_gate = _read_csv(STAGE142_GATE_IN)
    schema = _read_json(STAGE142_SCHEMA_IN)
    if stage142_summary.empty:
        raise RuntimeError(f"missing Stage142 summary: {STAGE142_SUMMARY_IN}")
    if validation.empty:
        raise RuntimeError(f"missing Stage142 validation audit: {STAGE142_VALIDATION_IN}")
    if stage142_gate.empty:
        raise RuntimeError(f"missing Stage142 gate status: {STAGE142_GATE_IN}")
    if not schema:
        raise RuntimeError(f"missing Stage142 schema: {STAGE142_SCHEMA_IN}")

    commands = _operator_command_manifest(args.candidate_placeholder)
    catalog = _failure_catalog(validation)
    triage = _triage_cases(validation, catalog)
    gate = _gate_status(stage142_summary, commands, catalog, triage)
    gate_pass = int(gate["pass_now"].sum() == len(gate))
    command_safe = int(commands[["mutates_official_config", "true_engine_run", "ab_triggered", "order_api_called", "ctp_connected"]].sum().sum() == 0)
    stage142_row = stage142_summary.iloc[0]
    current_package_promotion_allowed = int(stage142_row.get("current_package_promotion_allowed", 0))
    decision = (
        "stage143_operator_failure_explainer_ready_no_candidate_no_strategy"
        if gate_pass and command_safe and current_package_promotion_allowed == 0
        else "stage143_operator_failure_explainer_attention_required_no_strategy"
    )
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": decision,
                "stage142_decision": stage142_row.get("decision", ""),
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "operator_runbook_ready": int(gate_pass),
                "stage142_validator_ready": int(stage142_row.get("validator_ready", 0)),
                "failure_catalog_ready": int(len(catalog) > 0),
                "failure_reason_count": len(catalog),
                "unique_failure_reason_count": int(catalog["reason_code"].nunique()) if not catalog.empty else 0,
                "triage_case_count": len(triage),
                "safe_operator_command_count": int(commands["allowed_now"].sum()),
                "unsafe_operator_command_count": int(len(commands) - commands["allowed_now"].sum()),
                "gate_pass_count": int(gate["pass_now"].sum()),
                "gate_count": len(gate),
                "current_package_promotion_allowed": current_package_promotion_allowed,
                "real_candidate_package_supplied": int(stage142_row.get("real_candidate_package_supplied", 0)),
                "real_stage112_intake_allowed_now": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "end_equity": float(stage142_row.get("end_equity", np.nan)),
                "total_return_pct": float(stage142_row.get("total_return_pct", np.nan)),
                "max_drawdown_pct": float(stage142_row.get("max_drawdown_pct", np.nan)),
                "sharpe": float(stage142_row.get("sharpe", np.nan)),
                "total_slippage": float(stage142_row.get("total_slippage", np.nan)),
                "total_trade_count": float(stage142_row.get("total_trade_count", np.nan)),
                "closed_lot_win_rate_pct": float(stage142_row.get("closed_lot_win_rate_pct", np.nan)),
                "max_broker10_margin_to_equity_pct": float(stage142_row.get("max_broker10_margin_to_equity_pct", np.nan)),
            }
        ]
    )

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(commands, COMMAND_OUT)
    _write_csv(catalog, CATALOG_OUT)
    _write_csv(triage, TRIAGE_OUT)
    _write_csv(gate, GATE_OUT)
    _write_runbook(summary, commands, catalog, triage, gate, schema, args.candidate_placeholder)
    _plot_official_path(curve, summary)
    _plot_failure_matrix(validation, catalog)
    _plot_matrix(
        commands,
        "command_id",
        ["allowed_now", "mutates_official_config", "true_engine_run", "ab_triggered", "order_api_called", "ctp_connected"],
        "Stage143 operator command safety matrix",
        COMMAND_CHART_OUT,
    )
    _plot_matrix(
        triage,
        "case_id",
        ["would_pass_if_real", "promotion_allowed", "expectation_pass"],
        "Stage143 sample triage matrix",
        TRIAGE_CHART_OUT,
    )
    _plot_matrix(gate, "gate_id", ["pass_now"], "Stage143 gate status", GATE_CHART_OUT)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "inputs": {
                "stage142_summary": str(STAGE142_SUMMARY_IN),
                "stage142_schema": str(STAGE142_SCHEMA_IN),
                "stage142_validation": str(STAGE142_VALIDATION_IN),
                "stage142_gate": str(STAGE142_GATE_IN),
                "stage142_report": str(STAGE142_REPORT_IN),
            },
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "operator_command_manifest": str(COMMAND_OUT),
                "failure_reason_catalog": str(CATALOG_OUT),
                "sample_triage_cases": str(TRIAGE_OUT),
                "gate_status": str(GATE_OUT),
                "operator_runbook": str(RUNBOOK_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(FAILURE_CHART_OUT),
                    str(COMMAND_CHART_OUT),
                    str(TRIAGE_CHART_OUT),
                    str(GATE_CHART_OUT),
                ],
            },
            "locks": {
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "current_package_promotion_allowed": current_package_promotion_allowed,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
