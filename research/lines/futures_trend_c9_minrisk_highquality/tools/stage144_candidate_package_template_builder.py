from __future__ import annotations

import argparse
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import shutil
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage144"
MODEL_TAG = "stage144_candidate_package_template_builder_v1"
OUTPUT_PREFIX = "qmt_roll_stage144_c9_minrisk_candidate_package_template_builder"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
TOOLS_DIR = LINE_DIR / "tools"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage144_candidate_package_template_builder"
TEMPLATE_DIR = OUTPUT_DIR / "candidate_package_template"
TEMPLATE_ARTIFACT_DIR = TEMPLATE_DIR / "artifacts"

STAGE142_TOOL = TOOLS_DIR / "stage142_candidate_package_contract_validator.py"
STAGE142_DIR = LINE_DIR / "outputs" / "stage142_candidate_package_contract_validator"
STAGE142_PREFIX = "qmt_roll_stage142_c9_minrisk_candidate_package_contract_validator"
STAGE142_TAG = "stage142_candidate_package_contract_validator_v1"
STAGE142_SCHEMA_IN = STAGE142_DIR / f"{STAGE142_PREFIX}_candidate_package_schema_{STAGE142_TAG}.json"
STAGE142_SUMMARY_IN = STAGE142_DIR / f"{STAGE142_PREFIX}_summary_{STAGE142_TAG}.csv"
STAGE143_DIR = LINE_DIR / "outputs" / "stage143_candidate_package_operator_failure_explainer"
STAGE143_PREFIX = "qmt_roll_stage143_c9_minrisk_candidate_package_operator_failure_explainer"
STAGE143_TAG = "stage143_candidate_package_operator_failure_explainer_v1"
STAGE143_RUNBOOK_IN = STAGE143_DIR / f"{STAGE143_PREFIX}_operator_runbook_{STAGE143_TAG}.md"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
RESOURCE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_template_resource_manifest_{MODEL_TAG}.csv"
CHECKLIST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_submission_checklist_{MODEL_TAG}.csv"
VALIDATION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage142_template_validation_{MODEL_TAG}.csv"
COMMAND_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_operator_command_manifest_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_template_status_{MODEL_TAG}.png"
RESOURCE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_resource_manifest_matrix_{MODEL_TAG}.png"
VALIDATION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage142_template_validation_matrix_{MODEL_TAG}.png"
CHECKLIST_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_submission_checklist_matrix_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"

REQUIRED_VISUAL_IDS = [
    "equity_curve",
    "drawdown_curve",
    "broker10_curve",
    "minute_k_atlas",
    "right_tail_bottom_loss_atlas",
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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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


def _load_stage142_module() -> Any:
    spec = importlib.util.spec_from_file_location("stage142_candidate_package_contract_validator", STAGE142_TOOL)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import Stage142 validator: {STAGE142_TOOL}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _schema_requirements(schema: dict[str, Any]) -> dict[str, list[str]]:
    properties = schema.get("properties", {})
    return {
        "manifest_required": list(properties.get("manifest.json", {}).get("required", [])),
        "summary_required": list(properties.get("summary.csv", {}).get("required_columns", [])),
        "evidence_required": list(properties.get("evidence.csv", {}).get("required_evidence_id", [])),
        "visual_required": list(properties.get("visual_artifacts", {}).get("required_artifact_id", [])),
    }


def _placeholder_png(path: Path, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 3.2))
    x = np.linspace(0, 1, 50)
    ax.plot(x, 0.45 + 0.12 * np.sin(8 * x), color="#0F766E", linewidth=1.5)
    ax.text(0.5, 0.72, "TEMPLATE ONLY", ha="center", va="center", fontsize=16, fontweight="bold")
    ax.text(0.5, 0.57, title, ha="center", va="center", fontsize=9)
    ax.text(0.5, 0.26, "replace with real evidence before candidate review", ha="center", va="center", fontsize=8)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _template_manifest(candidate_id: str, created_at: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "line_id": LINE_ID,
        "created_at": created_at,
        "predeclared_spec_hash": "TEMPLATE_REPLACE_WITH_REAL_SPEC_HASH",
        "synthetic_case": 1,
        "fixture_marker": "template_only",
        "source_stage": STAGE,
        "true_engine_run_id": "TEMPLATE_REPLACE_WITH_REAL_TRUE_ENGINE_RUN_ID",
        "provenance_note": "Template only. Replace every TEMPLATE field and set synthetic_case=0 only after real point-in-time evidence exists.",
        "template_warning": "This package is intentionally blocked by Stage142 until real metrics and all evidence are supplied.",
    }


def _template_summary(candidate_id: str, requirements: dict[str, list[str]]) -> pd.DataFrame:
    values = {
        "candidate_id": candidate_id,
        "predeclared_spec_hash": "TEMPLATE_REPLACE_WITH_REAL_SPEC_HASH",
        "candidate_total_return_pct": 0.0,
        "candidate_max_drawdown_pct": 0.0,
        "candidate_max_broker10_margin_to_equity_pct": 999.0,
        "candidate_total_trade_count": 0,
        "candidate_closed_lot_win_rate_pct": 0.0,
        "candidate_total_slippage": 0.0,
    }
    return pd.DataFrame([{column: values.get(column, "") for column in requirements["summary_required"]}])


def _template_evidence(requirements: dict[str, list[str]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "evidence_id": evidence_id,
                "pass_now": 0,
                "artifact_path": f"evidence/{evidence_id}.md",
                "provenance_note": "TEMPLATE_REPLACE_WITH_REAL_POINT_IN_TIME_EVIDENCE",
                "required_before_promotion": 1,
            }
            for evidence_id in requirements["evidence_required"]
        ]
    )


def _write_template_package(schema: dict[str, Any], candidate_id: str) -> pd.DataFrame:
    if TEMPLATE_DIR.exists():
        shutil.rmtree(TEMPLATE_DIR)
    TEMPLATE_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    evidence_dir = TEMPLATE_DIR / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    requirements = _schema_requirements(schema)
    manifest = _template_manifest(candidate_id, created_at)
    summary = _template_summary(candidate_id, requirements)
    evidence = _template_evidence(requirements)
    _write_json(TEMPLATE_DIR / "manifest.json", manifest)
    _write_csv(summary, TEMPLATE_DIR / "summary.csv")
    _write_csv(evidence, TEMPLATE_DIR / "evidence.csv")
    for evidence_id in requirements["evidence_required"]:
        (evidence_dir / f"{evidence_id}.md").write_text(
            "\n".join(
                [
                    f"# {evidence_id}",
                    "",
                    "Status: TEMPLATE ONLY",
                    "",
                    "Replace this file with real point-in-time evidence before candidate review.",
                    "Do not set pass_now=1 until the corresponding evidence is independently reproducible.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    for artifact_id in requirements["visual_required"]:
        _placeholder_png(TEMPLATE_ARTIFACT_DIR / f"{artifact_id}.png", artifact_id)
    datapackage = {
        "profile": "data-package",
        "name": candidate_id.lower().replace("_", "-"),
        "title": "Stage144 candidate package template only",
        "created": created_at,
        "line_id": LINE_ID,
        "resources": [
            {"name": "manifest", "path": "manifest.json", "format": "json"},
            {"name": "summary", "path": "summary.csv", "format": "csv"},
            {"name": "evidence", "path": "evidence.csv", "format": "csv"},
            *[
                {"name": artifact_id, "path": f"artifacts/{artifact_id}.png", "format": "png"}
                for artifact_id in requirements["visual_required"]
            ],
        ],
        "provenance": {
            "entity": candidate_id,
            "activity": "stage144_template_generation",
            "agent": "codex_local_research_tool",
            "warning": "template only; not a real candidate",
        },
    }
    _write_json(TEMPLATE_DIR / "datapackage.json", datapackage)
    (TEMPLATE_DIR / "README.md").write_text(
        "\n".join(
            [
                "# Stage144 Candidate Package Template",
                "",
                "This directory is a template only. It is intentionally blocked by Stage142.",
                "",
                "Minimum replacement rules:",
                "",
                "1. Replace all `TEMPLATE_` values with real candidate metadata.",
                "2. Set `synthetic_case=0` only after the package is produced from real point-in-time data and a true engine replay.",
                "3. Set evidence `pass_now=1` only when each evidence file is reproducible.",
                "4. Replace all placeholder PNGs with real equity, drawdown, broker10, minute K atlas, and right-tail/bottom-loss atlas images.",
                "5. Run Stage142 validator and Stage143 failure explainer before any candidate discussion.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (TEMPLATE_DIR / "SUBMISSION_CHECKLIST.md").write_text(
        "\n".join(
            [
                "# Submission Checklist",
                "",
                "- [ ] manifest.json has real provenance and `synthetic_case=0`.",
                "- [ ] summary.csv uses true engine metrics, not proxy metrics.",
                "- [ ] evidence.csv has every Stage141 evidence id and every `pass_now=1` is backed by a file.",
                "- [ ] visual artifacts are real, non-placeholder, and visually inspected.",
                "- [ ] Stage142 validation is run and saved in a new stage record.",
                "- [ ] Stage143 failure explainer returns no hard-stop reason for the real package.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rows = []
    for path in sorted(TEMPLATE_DIR.rglob("*")):
        if path.is_file():
            rel = path.relative_to(TEMPLATE_DIR).as_posix()
            rows.append(
                {
                    "resource_path": rel,
                    "present": int(path.exists() and path.stat().st_size > 0),
                    "template_only": 1,
                    "required_before_promotion": int(
                        rel
                        in {
                            "manifest.json",
                            "summary.csv",
                            "evidence.csv",
                            *[f"artifacts/{artifact_id}.png" for artifact_id in requirements["visual_required"]],
                        }
                    ),
                    "replace_before_real_candidate": int(rel.endswith(".png") or rel.startswith("evidence/") or rel in {"manifest.json", "summary.csv", "evidence.csv"}),
                    "purpose": _resource_purpose(rel),
                }
            )
    return pd.DataFrame(rows)


def _resource_purpose(rel_path: str) -> str:
    if rel_path == "manifest.json":
        return "candidate provenance and identity"
    if rel_path == "summary.csv":
        return "true engine performance metrics"
    if rel_path == "evidence.csv":
        return "Stage141 evidence pass/fail matrix"
    if rel_path == "datapackage.json":
        return "data package resource descriptor"
    if rel_path == "README.md":
        return "human-readable package usage note"
    if rel_path == "SUBMISSION_CHECKLIST.md":
        return "manual submission checklist"
    if rel_path.startswith("artifacts/"):
        return "required visual evidence placeholder"
    if rel_path.startswith("evidence/"):
        return "required evidence note placeholder"
    return "supporting template file"


def _submission_checklist(requirements: dict[str, list[str]]) -> pd.DataFrame:
    rows = [
        {
            "check_id": "manifest_real_provenance",
            "required_now": 1,
            "template_pass": 0,
            "real_candidate_required": 1,
            "description": "manifest must have real provenance and synthetic_case=0",
        },
        {
            "check_id": "summary_true_engine_metrics",
            "required_now": 1,
            "template_pass": 0,
            "real_candidate_required": 1,
            "description": "summary metrics must come from true engine replay, not placeholders",
        },
        {
            "check_id": "evidence_all_ids_present",
            "required_now": 1,
            "template_pass": 1,
            "real_candidate_required": 1,
            "description": f"{len(requirements['evidence_required'])} Stage141 evidence ids are present",
        },
        {
            "check_id": "evidence_all_pass_real",
            "required_now": 1,
            "template_pass": 0,
            "real_candidate_required": 1,
            "description": "every evidence row must be backed by reproducible files",
        },
        {
            "check_id": "visual_artifacts_present",
            "required_now": 1,
            "template_pass": 1,
            "real_candidate_required": 1,
            "description": f"{len(requirements['visual_required'])} visual artifact placeholders are present",
        },
        {
            "check_id": "visual_artifacts_real",
            "required_now": 1,
            "template_pass": 0,
            "real_candidate_required": 1,
            "description": "placeholder charts must be replaced by real curve and atlas images",
        },
        {
            "check_id": "stage142_validation_saved",
            "required_now": 1,
            "template_pass": 1,
            "real_candidate_required": 1,
            "description": "Stage144 imports Stage142 validator and verifies this template is blocked",
        },
        {
            "check_id": "no_auto_promotion",
            "required_now": 1,
            "template_pass": 1,
            "real_candidate_required": 1,
            "description": "template cannot promote itself or change official config",
        },
    ]
    return pd.DataFrame(rows)


def _operator_commands(template_dir: Path) -> pd.DataFrame:
    stage142_rel = STAGE142_TOOL.relative_to(REPO_DIR)
    template_rel = template_dir.relative_to(REPO_DIR)
    return pd.DataFrame(
        [
            {
                "command_id": "generate_stage144_template",
                "command": f".py311/bin/python {SCRIPT_PATH.relative_to(REPO_DIR)}",
                "allowed_now": 1,
                "mutates_official_config": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "purpose": "regenerate the template-only candidate package skeleton",
            },
            {
                "command_id": "inspect_template_manifest",
                "command": f"sed -n '1,120p' {template_rel}/manifest.json",
                "allowed_now": 1,
                "mutates_official_config": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "purpose": "confirm template remains synthetic_case=1 until real evidence exists",
            },
            {
                "command_id": "compile_stage142_validator",
                "command": f".py311/bin/python -m py_compile {stage142_rel}",
                "allowed_now": 1,
                "mutates_official_config": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "purpose": "confirm Stage142 validator remains executable before real package submission",
            },
            {
                "command_id": "manual_stage142_real_package_validation",
                "command": f".py311/bin/python {stage142_rel} --candidate-package-dir <real_candidate_package_dir> --case-id real_candidate_YYYYMMDD",
                "allowed_now": 1,
                "mutates_official_config": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "purpose": "validate a future real candidate package after all template placeholders are replaced",
            },
        ]
    )


def _gate_status(
    resource_manifest: pd.DataFrame,
    checklist: pd.DataFrame,
    validation: pd.DataFrame,
    commands: pd.DataFrame,
    stage142_summary: pd.DataFrame,
) -> pd.DataFrame:
    template_files_ready = int(not resource_manifest.empty and int(resource_manifest["present"].sum()) == len(resource_manifest))
    required_resources_ready = int(
        not resource_manifest.empty
        and int(resource_manifest.loc[resource_manifest["required_before_promotion"] == 1, "present"].sum())
        == int(resource_manifest["required_before_promotion"].sum())
    )
    template_blocked = int(
        not validation.empty
        and int(validation.iloc[0].get("would_pass_if_real", 1)) == 0
        and int(validation.iloc[0].get("promotion_allowed", 1)) == 0
    )
    command_safe = int(
        not commands.empty
        and int(commands[["mutates_official_config", "true_engine_run", "ab_triggered", "order_api_called", "ctp_connected"]].sum().sum()) == 0
    )
    stage142_ready = int(not stage142_summary.empty and int(stage142_summary.iloc[0].get("validator_ready", 0)) == 1)
    checklist_has_real_blocks = int(not checklist.empty and int((checklist["template_pass"] == 0).sum()) >= 3)
    rows = [
        {
            "gate_id": "template_files_ready",
            "observed": template_files_ready,
            "required": 1,
            "pass_now": template_files_ready,
            "severity": "artifact_hard",
        },
        {
            "gate_id": "required_resources_present",
            "observed": required_resources_ready,
            "required": 1,
            "pass_now": required_resources_ready,
            "severity": "artifact_hard",
        },
        {
            "gate_id": "template_blocked_by_stage142",
            "observed": template_blocked,
            "required": 1,
            "pass_now": template_blocked,
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
            "gate_id": "stage142_dependency_ready",
            "observed": stage142_ready,
            "required": 1,
            "pass_now": stage142_ready,
            "severity": "dependency_hard",
        },
        {
            "gate_id": "checklist_keeps_template_nonreal",
            "observed": checklist_has_real_blocks,
            "required": 1,
            "pass_now": checklist_has_real_blocks,
            "severity": "anti_overfit_hard",
        },
    ]
    return pd.DataFrame(rows)


def _write_report(
    summary: pd.DataFrame,
    resource_manifest: pd.DataFrame,
    checklist: pd.DataFrame,
    validation: pd.DataFrame,
    commands: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    lines = [
        f"# {STAGE} candidate package template builder",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- scope: generate a template-only candidate package skeleton and prove it remains blocked until real evidence is supplied.",
        "",
        "## External Research Judgment",
        "",
        "- Frictionless Data Package motivates a descriptor plus resource list, so this stage writes `datapackage.json` alongside the Stage142 files.",
        "- JSON Schema motivates executable required-field contracts, so the template is generated from Stage142 schema instead of a hand-written list.",
        "- W3C PROV motivates explicit entity/activity/agent provenance metadata, so the template includes provenance fields and warnings.",
        "- Great Expectations Data Docs motivates human-readable submission guidance, so README and checklist are generated with the machine-readable CSVs.",
        "",
        "## Summary",
        "",
        _md_table(summary.drop(columns=["template_dir"], errors="ignore")),
        "",
        "## Stage142 Template Validation",
        "",
        _md_table(validation),
        "",
        "## Operator Commands",
        "",
        _md_table(commands[["command_id", "command", "purpose"]]),
        "",
        "## Submission Checklist",
        "",
        _md_table(checklist),
        "",
        "## Resource Manifest",
        "",
        _md_table(resource_manifest[["resource_path", "present", "template_only", "replace_before_real_candidate", "purpose"]], max_rows=40),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{RESOURCE_CHART_OUT.name}`",
        f"- `{VALIDATION_CHART_OUT.name}`",
        f"- `{CHECKLIST_CHART_OUT.name}`",
        f"- `{GATE_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _plot_official_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage144 template builder: structure ready, template remains blocked", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#14532D", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#B45309", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3657D6", linewidth=1.0)
    axes[2].axhline(100, color="#333333", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    status_cols = [
        "template_builder_ready",
        "stage142_template_validation_blocked",
        "current_package_promotion_allowed",
        "true_engine_run",
        "official_config_changed",
    ]
    matrix = summary[status_cols].T
    matrix.columns = ["status"]
    matrix.plot(kind="bar", ax=axes[3], legend=False, color="#0F766E")
    axes[3].set_title("Template safety status")
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
    fig, ax = plt.subplots(figsize=(max(8.5, len(value_cols) * 1.35), max(4.8, len(matrix) * 0.42)))
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title(title)
    ax.set_xticks(np.arange(len(value_cols)))
    ax.set_xticklabels(value_cols, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=7)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage144 template-only candidate package builder.")
    parser.add_argument("--candidate-id", default="TEMPLATE_REPLACE_WITH_REAL_CANDIDATE_ID")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    schema = _read_json(STAGE142_SCHEMA_IN)
    stage142_summary = _read_csv(STAGE142_SUMMARY_IN)
    if not schema:
        raise RuntimeError(f"missing Stage142 schema: {STAGE142_SCHEMA_IN}")
    if stage142_summary.empty:
        raise RuntimeError(f"missing Stage142 summary: {STAGE142_SUMMARY_IN}")
    stage142 = _load_stage142_module()
    requirements = _schema_requirements(schema)
    resource_manifest = _write_template_package(schema, args.candidate_id)
    checklist = _submission_checklist(requirements)
    thresholds = stage142._thresholds_from_stage141()
    validation_row = stage142._validate_package(TEMPLATE_DIR, thresholds, "stage144_template_only")
    validation = pd.DataFrame([validation_row])
    validation["expected_would_pass_if_real"] = 0
    validation["expected_promotion_allowed"] = 0
    validation["expectation_pass"] = (
        (validation["would_pass_if_real"].astype(int) == 0)
        & (validation["promotion_allowed"].astype(int) == 0)
    ).astype(int)
    commands = _operator_commands(TEMPLATE_DIR)
    gate = _gate_status(resource_manifest, checklist, validation, commands, stage142_summary)
    gate_pass = int(gate["pass_now"].sum() == len(gate))
    stage142_template_validation_blocked = int(
        int(validation.iloc[0]["would_pass_if_real"]) == 0 and int(validation.iloc[0]["promotion_allowed"]) == 0
    )
    current_package_promotion_allowed = 0
    decision = (
        "stage144_candidate_package_template_ready_template_blocked_no_strategy"
        if gate_pass and stage142_template_validation_blocked
        else "stage144_candidate_package_template_attention_required_no_strategy"
    )
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": decision,
                "stage142_decision": stage142_summary.iloc[0].get("decision", ""),
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "template_builder_ready": gate_pass,
                "template_file_count": len(resource_manifest),
                "template_required_resource_count": int(resource_manifest["required_before_promotion"].sum()),
                "template_required_resource_present_count": int(resource_manifest.loc[resource_manifest["required_before_promotion"] == 1, "present"].sum()),
                "submission_check_count": len(checklist),
                "submission_check_template_pass_count": int(checklist["template_pass"].sum()),
                "submission_check_real_required_count": int(checklist["real_candidate_required"].sum()),
                "stage142_template_validation_blocked": stage142_template_validation_blocked,
                "stage142_template_would_pass_if_real": int(validation.iloc[0]["would_pass_if_real"]),
                "stage142_template_promotion_allowed": int(validation.iloc[0]["promotion_allowed"]),
                "safe_operator_command_count": int(commands["allowed_now"].sum()),
                "unsafe_operator_command_count": int(len(commands) - commands["allowed_now"].sum()),
                "gate_pass_count": int(gate["pass_now"].sum()),
                "gate_count": len(gate),
                "current_package_promotion_allowed": current_package_promotion_allowed,
                "real_candidate_package_supplied": 0,
                "real_stage112_intake_allowed_now": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "template_dir": str(TEMPLATE_DIR),
                "end_equity": float(stage142_summary.iloc[0].get("end_equity", np.nan)),
                "total_return_pct": float(stage142_summary.iloc[0].get("total_return_pct", np.nan)),
                "max_drawdown_pct": float(stage142_summary.iloc[0].get("max_drawdown_pct", np.nan)),
                "sharpe": float(stage142_summary.iloc[0].get("sharpe", np.nan)),
                "total_slippage": float(stage142_summary.iloc[0].get("total_slippage", np.nan)),
                "total_trade_count": float(stage142_summary.iloc[0].get("total_trade_count", np.nan)),
                "closed_lot_win_rate_pct": float(stage142_summary.iloc[0].get("closed_lot_win_rate_pct", np.nan)),
                "max_broker10_margin_to_equity_pct": float(stage142_summary.iloc[0].get("max_broker10_margin_to_equity_pct", np.nan)),
            }
        ]
    )
    _write_csv(summary, SUMMARY_OUT)
    _write_csv(resource_manifest, RESOURCE_OUT)
    _write_csv(checklist, CHECKLIST_OUT)
    _write_csv(validation, VALIDATION_OUT)
    _write_csv(commands, COMMAND_OUT)
    _write_csv(gate, GATE_OUT)
    _write_report(summary, resource_manifest, checklist, validation, commands, gate)
    _plot_official_path(curve, summary)
    _plot_matrix(
        resource_manifest,
        "resource_path",
        ["present", "template_only", "required_before_promotion", "replace_before_real_candidate"],
        "Stage144 template resource manifest",
        RESOURCE_CHART_OUT,
    )
    _plot_matrix(
        validation,
        "case_id",
        [
            "package_exists",
            "manifest_parse_ok",
            "summary_schema_pass",
            "evidence_schema_pass",
            "visual_artifacts_pass",
            "return_gate",
            "drawdown_gate",
            "broker_gate",
            "all_evidence_pass",
            "would_pass_if_real",
            "promotion_allowed",
            "expectation_pass",
        ],
        "Stage144 Stage142 template validation",
        VALIDATION_CHART_OUT,
    )
    _plot_matrix(
        checklist,
        "check_id",
        ["required_now", "template_pass", "real_candidate_required"],
        "Stage144 submission checklist",
        CHECKLIST_CHART_OUT,
    )
    _plot_matrix(gate, "gate_id", ["pass_now"], "Stage144 gate status", GATE_CHART_OUT)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "inputs": {
                "stage142_schema": str(STAGE142_SCHEMA_IN),
                "stage142_summary": str(STAGE142_SUMMARY_IN),
                "stage143_runbook": str(STAGE143_RUNBOOK_IN),
            },
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "resource_manifest": str(RESOURCE_OUT),
                "submission_checklist": str(CHECKLIST_OUT),
                "stage142_template_validation": str(VALIDATION_OUT),
                "operator_command_manifest": str(COMMAND_OUT),
                "gate_status": str(GATE_OUT),
                "report": str(REPORT_OUT),
                "template_dir": str(TEMPLATE_DIR),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(RESOURCE_CHART_OUT),
                    str(VALIDATION_CHART_OUT),
                    str(CHECKLIST_CHART_OUT),
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
