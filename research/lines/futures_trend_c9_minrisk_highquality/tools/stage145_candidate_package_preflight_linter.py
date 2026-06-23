from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage145"
MODEL_TAG = "stage145_candidate_package_preflight_linter_v1"
OUTPUT_PREFIX = "qmt_roll_stage145_c9_minrisk_candidate_package_preflight_linter"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage145_candidate_package_preflight_linter"

STAGE142_DIR = LINE_DIR / "outputs" / "stage142_candidate_package_contract_validator"
STAGE142_PREFIX = "qmt_roll_stage142_c9_minrisk_candidate_package_contract_validator"
STAGE142_TAG = "stage142_candidate_package_contract_validator_v1"
STAGE142_SCHEMA_IN = STAGE142_DIR / f"{STAGE142_PREFIX}_candidate_package_schema_{STAGE142_TAG}.json"
STAGE142_SUMMARY_IN = STAGE142_DIR / f"{STAGE142_PREFIX}_summary_{STAGE142_TAG}.csv"

STAGE144_DIR = LINE_DIR / "outputs" / "stage144_candidate_package_template_builder"
STAGE144_TEMPLATE_DIR = STAGE144_DIR / "candidate_package_template"
STAGE144_SUMMARY_IN = (
    STAGE144_DIR
    / "qmt_roll_stage144_c9_minrisk_candidate_package_template_builder_summary_"
    "stage144_candidate_package_template_builder_v1.csv"
)

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
ISSUE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_issue_catalog_{MODEL_TAG}.csv"
FILE_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_file_audit_{MODEL_TAG}.csv"
VISUAL_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_visual_audit_{MODEL_TAG}.csv"
CHECKLIST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_preflight_checklist_{MODEL_TAG}.csv"
COMMAND_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_operator_command_manifest_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_linter_status_{MODEL_TAG}.png"
ISSUE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_issue_matrix_{MODEL_TAG}.png"
VISUAL_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_visual_audit_matrix_{MODEL_TAG}.png"
CHECKLIST_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_preflight_checklist_matrix_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"

TEXT_SUFFIXES = {".csv", ".json", ".md", ".txt", ".yaml", ".yml"}
PLACEHOLDER_TOKENS = [
    "TEMPLATE_",
    "TEMPLATE ONLY",
    "template only",
    "template_only",
    "replace with real",
    "Replace this file with real",
]
FORBIDDEN_MARKERS = {"stage131", "stage142", "stage144", "fixture", "synthetic", "template_only", "contract_positive"}


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _schema_requirements(schema: dict[str, Any]) -> dict[str, list[str]]:
    properties = schema.get("properties", {})
    return {
        "manifest_required": list(properties.get("manifest.json", {}).get("required", [])),
        "summary_required": list(properties.get("summary.csv", {}).get("required_columns", [])),
        "evidence_required": list(properties.get("evidence.csv", {}).get("required_evidence_id", [])),
        "visual_required": list(properties.get("visual_artifacts", {}).get("required_artifact_id", [])),
    }


def _template_hashes(requirements: dict[str, list[str]]) -> dict[str, set[str]]:
    hashes: dict[str, set[str]] = {}
    for artifact_id in requirements["visual_required"]:
        paths = list((STAGE144_TEMPLATE_DIR / "artifacts").glob(f"{artifact_id}.*"))
        hashes[artifact_id] = {_sha256(path) for path in paths if path.exists() and path.is_file()}
    return hashes


def _add_issue(
    rows: list[dict[str, Any]],
    *,
    issue_code: str,
    severity: str,
    path: str,
    field: str,
    observed: Any,
    expected: str,
    action: str,
) -> None:
    rows.append(
        {
            "issue_code": issue_code,
            "severity": severity,
            "hard_stop": int(severity == "hard"),
            "path": path,
            "field": field,
            "observed": "" if observed is None else str(observed),
            "expected": expected,
            "operator_action": action,
        }
    )


def _scan_text_tokens(package_dir: Path, issue_rows: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    if not package_dir.exists():
        return pd.DataFrame(rows)
    for path in sorted(package_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(package_dir).as_posix()
        token_count = 0
        matched_tokens: list[str] = []
        if path.suffix.lower() in TEXT_SUFFIXES:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for token in PLACEHOLDER_TOKENS:
                count = text.count(token)
                if count:
                    token_count += count
                    matched_tokens.append(token)
            if token_count:
                _add_issue(
                    issue_rows,
                    issue_code="PLACEHOLDER_TEXT_TOKEN",
                    severity="hard",
                    path=rel,
                    field="text",
                    observed=",".join(matched_tokens),
                    expected="no template placeholder token",
                    action="Replace all template placeholders before running Stage142 as a real candidate.",
                )
        rows.append(
            {
                "resource_path": rel,
                "exists": 1,
                "size_bytes": path.stat().st_size,
                "text_scanned": int(path.suffix.lower() in TEXT_SUFFIXES),
                "placeholder_token_count": token_count,
                "matched_tokens": ",".join(matched_tokens),
            }
        )
    return pd.DataFrame(rows)


def _scan_required_files(package_dir: Path, issue_rows: list[dict[str, Any]]) -> None:
    for rel in ["manifest.json", "summary.csv", "evidence.csv", "datapackage.json"]:
        path = package_dir / rel
        if not path.exists() or path.stat().st_size <= 4:
            _add_issue(
                issue_rows,
                issue_code="MISSING_REQUIRED_FILE",
                severity="hard",
                path=rel,
                field="exists",
                observed=0,
                expected="present and non-empty",
                action="Create this required file from the Stage144 template and replace placeholders with real evidence.",
            )


def _scan_manifest(package_dir: Path, requirements: dict[str, list[str]], issue_rows: list[dict[str, Any]]) -> None:
    manifest = _read_json(package_dir / "manifest.json")
    if not manifest:
        _add_issue(
            issue_rows,
            issue_code="MANIFEST_PARSE_FAIL",
            severity="hard",
            path="manifest.json",
            field="json",
            observed="missing_or_invalid",
            expected="valid JSON object",
            action="Write a valid manifest.json before preflight can continue.",
        )
        return
    for field in requirements["manifest_required"]:
        if field not in manifest or str(manifest.get(field, "")).strip() == "":
            _add_issue(
                issue_rows,
                issue_code="MANIFEST_REQUIRED_FIELD_MISSING",
                severity="hard",
                path="manifest.json",
                field=field,
                observed=manifest.get(field),
                expected="non-empty required field",
                action="Fill every Stage142 manifest required field with real provenance.",
            )
    synthetic_case = int(manifest.get("synthetic_case", -1)) if str(manifest.get("synthetic_case", "")).strip() not in {"", "nan"} else -1
    if synthetic_case != 0:
        _add_issue(
            issue_rows,
            issue_code="SYNTHETIC_CASE_NOT_REAL",
            severity="hard",
            path="manifest.json",
            field="synthetic_case",
            observed=synthetic_case,
            expected="0 for real candidate",
            action="Keep template packages blocked; only real point-in-time packages may set synthetic_case=0.",
        )
    joined = " ".join(str(manifest.get(key, "")) for key in ["candidate_id", "fixture_marker", "provenance_note", "source_stage"]).lower()
    matched = sorted(marker for marker in FORBIDDEN_MARKERS if marker in joined)
    if matched:
        _add_issue(
            issue_rows,
            issue_code="FORBIDDEN_PROVENANCE_MARKER",
            severity="hard",
            path="manifest.json",
            field="candidate_id/fixture_marker/provenance_note/source_stage",
            observed=",".join(matched),
            expected="no fixture/synthetic/template marker",
            action="Regenerate the package from real candidate evidence; do not reuse template or fixture provenance.",
        )
    for field in ["candidate_id", "predeclared_spec_hash", "true_engine_run_id"]:
        value = str(manifest.get(field, ""))
        if "TEMPLATE" in value:
            _add_issue(
                issue_rows,
                issue_code="MANIFEST_TEMPLATE_VALUE",
                severity="hard",
                path="manifest.json",
                field=field,
                observed=value,
                expected="real value",
                action="Replace TEMPLATE values before treating this as a real candidate.",
            )


def _scan_summary(package_dir: Path, requirements: dict[str, list[str]], issue_rows: list[dict[str, Any]]) -> None:
    summary = _read_csv(package_dir / "summary.csv")
    if summary.empty:
        _add_issue(
            issue_rows,
            issue_code="SUMMARY_EMPTY_OR_INVALID",
            severity="hard",
            path="summary.csv",
            field="rows",
            observed=0,
            expected="one real metrics row",
            action="Write true engine candidate metrics before Stage142 validation.",
        )
        return
    missing_cols = [column for column in requirements["summary_required"] if column not in summary.columns]
    for column in missing_cols:
        _add_issue(
            issue_rows,
            issue_code="SUMMARY_REQUIRED_COLUMN_MISSING",
            severity="hard",
            path="summary.csv",
            field=column,
            observed="missing",
            expected="required column",
            action="Use the Stage142 schema columns exactly.",
        )
    if missing_cols:
        return
    row = summary.iloc[0]
    if "TEMPLATE" in str(row.get("candidate_id", "")) or "TEMPLATE" in str(row.get("predeclared_spec_hash", "")):
        _add_issue(
            issue_rows,
            issue_code="SUMMARY_TEMPLATE_ID",
            severity="hard",
            path="summary.csv",
            field="candidate_id/predeclared_spec_hash",
            observed=f"{row.get('candidate_id', '')}|{row.get('predeclared_spec_hash', '')}",
            expected="real candidate id and spec hash",
            action="Replace template ids with the frozen real candidate spec id.",
        )
    numeric_expectations = [
        ("candidate_total_return_pct", 0.0, ">", "real candidate return should be non-placeholder"),
        ("candidate_total_trade_count", 0.0, ">", "true engine trade count should be positive"),
        ("candidate_max_broker10_margin_to_equity_pct", 900.0, "<", "broker10 placeholder 999 must be replaced"),
    ]
    for field, threshold, op, expected in numeric_expectations:
        value = pd.to_numeric(pd.Series([row.get(field)]), errors="coerce").iloc[0]
        fail = bool(pd.isna(value) or (value <= threshold if op == ">" else value >= threshold))
        if fail:
            _add_issue(
                issue_rows,
                issue_code="SUMMARY_PLACEHOLDER_METRIC",
                severity="hard",
                path="summary.csv",
                field=field,
                observed=value,
                expected=expected,
                action="Replace placeholder metrics with true engine output.",
            )


def _scan_evidence(package_dir: Path, requirements: dict[str, list[str]], issue_rows: list[dict[str, Any]]) -> None:
    evidence = _read_csv(package_dir / "evidence.csv")
    if evidence.empty:
        _add_issue(
            issue_rows,
            issue_code="EVIDENCE_EMPTY_OR_INVALID",
            severity="hard",
            path="evidence.csv",
            field="rows",
            observed=0,
            expected="all Stage141 evidence rows",
            action="Write evidence.csv from the Stage144 template and back every pass flag with real files.",
        )
        return
    if not {"evidence_id", "pass_now"}.issubset(evidence.columns):
        _add_issue(
            issue_rows,
            issue_code="EVIDENCE_REQUIRED_COLUMNS_MISSING",
            severity="hard",
            path="evidence.csv",
            field="evidence_id/pass_now",
            observed="missing",
            expected="required columns",
            action="Use the Stage142 evidence schema.",
        )
        return
    observed_ids = set(evidence["evidence_id"].astype(str))
    for evidence_id in requirements["evidence_required"]:
        if evidence_id not in observed_ids:
            _add_issue(
                issue_rows,
                issue_code="EVIDENCE_ID_MISSING",
                severity="hard",
                path="evidence.csv",
                field=evidence_id,
                observed="missing",
                expected="present",
                action="Add every Stage141 evidence id before candidate submission.",
            )
    for _, row in evidence.iterrows():
        evidence_id = str(row.get("evidence_id", ""))
        pass_now = int(pd.to_numeric(pd.Series([row.get("pass_now")]), errors="coerce").fillna(0).iloc[0])
        if pass_now != 1:
            _add_issue(
                issue_rows,
                issue_code="EVIDENCE_NOT_PASSING",
                severity="hard",
                path="evidence.csv",
                field=evidence_id,
                observed=pass_now,
                expected="pass_now=1 backed by real evidence",
                action="Do not submit this package until every required evidence row passes with reproducible backing files.",
            )


def _scan_visuals(
    package_dir: Path,
    requirements: dict[str, list[str]],
    template_hashes: dict[str, set[str]],
    issue_rows: list[dict[str, Any]],
) -> pd.DataFrame:
    rows = []
    artifact_dir = package_dir / "artifacts"
    for artifact_id in requirements["visual_required"]:
        matches = sorted(artifact_dir.glob(f"{artifact_id}.*"))
        exists = int(any(path.exists() and path.stat().st_size > 0 for path in matches))
        hash_match = 0
        hashes = []
        for path in matches:
            if path.exists() and path.is_file():
                digest = _sha256(path)
                hashes.append(digest)
                hash_match = max(hash_match, int(digest in template_hashes.get(artifact_id, set())))
        if not exists:
            _add_issue(
                issue_rows,
                issue_code="VISUAL_ARTIFACT_MISSING",
                severity="hard",
                path=f"artifacts/{artifact_id}.*",
                field=artifact_id,
                observed=0,
                expected="real non-empty visual artifact",
                action="Provide real equity/drawdown/broker10/minute atlas visual evidence.",
            )
        if hash_match:
            _add_issue(
                issue_rows,
                issue_code="VISUAL_PLACEHOLDER_HASH_MATCH",
                severity="hard",
                path=",".join(path.relative_to(package_dir).as_posix() for path in matches),
                field=artifact_id,
                observed="matches_stage144_placeholder",
                expected="real visual artifact hash",
                action="Replace Stage144 placeholder PNG with real visual evidence.",
            )
        rows.append(
            {
                "artifact_id": artifact_id,
                "artifact_exists": exists,
                "file_count": len(matches),
                "placeholder_hash_match": hash_match,
                "real_visual_required": 1,
                "sample_hash": hashes[0] if hashes else "",
            }
        )
    return pd.DataFrame(rows)


def _scan_datapackage(package_dir: Path, issue_rows: list[dict[str, Any]]) -> None:
    descriptor = _read_json(package_dir / "datapackage.json")
    if not descriptor:
        _add_issue(
            issue_rows,
            issue_code="DATAPACKAGE_PARSE_FAIL",
            severity="hard",
            path="datapackage.json",
            field="json",
            observed="missing_or_invalid",
            expected="valid descriptor",
            action="Keep a descriptor with resource paths so package contents are auditable.",
        )
        return
    resources = descriptor.get("resources", [])
    if not isinstance(resources, list) or not resources:
        _add_issue(
            issue_rows,
            issue_code="DATAPACKAGE_RESOURCES_EMPTY",
            severity="hard",
            path="datapackage.json",
            field="resources",
            observed=resources,
            expected="non-empty resource list",
            action="List all package resources in datapackage.json.",
        )
        return
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        rel = str(resource.get("path", ""))
        if rel and not (package_dir / rel).exists():
            _add_issue(
                issue_rows,
                issue_code="DATAPACKAGE_RESOURCE_PATH_MISSING",
                severity="hard",
                path="datapackage.json",
                field=rel,
                observed="missing",
                expected="resource path exists",
                action="Fix the datapackage resource path or add the missing file.",
            )


def _run_linter(package_dir: Path, requirements: dict[str, list[str]], reference_hashes: dict[str, set[str]]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    issue_rows: list[dict[str, Any]] = []
    if not package_dir.exists():
        _add_issue(
            issue_rows,
            issue_code="PACKAGE_DIR_MISSING",
            severity="hard",
            path=str(package_dir),
            field="package_dir",
            observed=0,
            expected="existing candidate package directory",
            action="Point --candidate-package-dir to a real candidate package.",
        )
        empty = pd.DataFrame()
        return pd.DataFrame(issue_rows), empty, empty, empty
    _scan_required_files(package_dir, issue_rows)
    _scan_manifest(package_dir, requirements, issue_rows)
    _scan_summary(package_dir, requirements, issue_rows)
    _scan_evidence(package_dir, requirements, issue_rows)
    _scan_datapackage(package_dir, issue_rows)
    file_audit = _scan_text_tokens(package_dir, issue_rows)
    visual_audit = _scan_visuals(package_dir, requirements, reference_hashes, issue_rows)
    issues = pd.DataFrame(issue_rows)
    checklist = _checklist_from_scans(issues, file_audit, visual_audit)
    return issues, file_audit, visual_audit, checklist


def _checklist_from_scans(issues: pd.DataFrame, file_audit: pd.DataFrame, visual_audit: pd.DataFrame) -> pd.DataFrame:
    hard_issue_codes = set(issues["issue_code"].astype(str)) if not issues.empty else set()
    token_count = int(file_audit["placeholder_token_count"].sum()) if not file_audit.empty else 0
    visual_placeholder_count = int(visual_audit["placeholder_hash_match"].sum()) if not visual_audit.empty else 0
    visual_present_count = int(visual_audit["artifact_exists"].sum()) if not visual_audit.empty else 0
    visual_count = len(visual_audit)
    checks = [
        ("package_dir_exists", "PACKAGE_DIR_MISSING" not in hard_issue_codes),
        ("required_files_present", "MISSING_REQUIRED_FILE" not in hard_issue_codes),
        ("manifest_real_not_template", not {"SYNTHETIC_CASE_NOT_REAL", "FORBIDDEN_PROVENANCE_MARKER", "MANIFEST_TEMPLATE_VALUE"} & hard_issue_codes),
        ("summary_metrics_real", not {"SUMMARY_PLACEHOLDER_METRIC", "SUMMARY_TEMPLATE_ID", "SUMMARY_EMPTY_OR_INVALID"} & hard_issue_codes),
        ("all_evidence_pass_now", "EVIDENCE_NOT_PASSING" not in hard_issue_codes),
        ("no_placeholder_text_tokens", token_count == 0),
        ("visual_artifacts_present", visual_present_count == visual_count and visual_count > 0),
        ("visual_artifacts_not_template_hash", visual_placeholder_count == 0),
        ("datapackage_resources_valid", not {"DATAPACKAGE_PARSE_FAIL", "DATAPACKAGE_RESOURCES_EMPTY", "DATAPACKAGE_RESOURCE_PATH_MISSING"} & hard_issue_codes),
    ]
    return pd.DataFrame(
        [
            {
                "check_id": check_id,
                "pass_now": int(pass_now),
                "required": 1,
                "hard_stop": int(not pass_now),
            }
            for check_id, pass_now in checks
        ]
    )


def _operator_commands(package_dir: Path) -> pd.DataFrame:
    rel_script = SCRIPT_PATH.relative_to(REPO_DIR)
    rel_package = package_dir.relative_to(REPO_DIR) if package_dir.is_relative_to(REPO_DIR) else package_dir
    return pd.DataFrame(
        [
            {
                "command_id": "run_default_template_lint_selftest",
                "command": f".py311/bin/python {rel_script}",
                "allowed_now": 1,
                "mutates_official_config": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "purpose": "confirm Stage144 template is blocked by preflight linter",
            },
            {
                "command_id": "lint_future_real_candidate_package",
                "command": f".py311/bin/python {rel_script} --candidate-package-dir <real_candidate_package_dir> --case-id real_candidate_preflight_YYYYMMDD",
                "allowed_now": 1,
                "mutates_official_config": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "purpose": "scan a future real package before Stage142 validator",
            },
            {
                "command_id": "inspect_current_lint_target",
                "command": f"find {rel_package} -maxdepth 2 -type f | sort",
                "allowed_now": 1,
                "mutates_official_config": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "purpose": "inspect target candidate package files",
            },
        ]
    )


def _gate_status(
    summary_flags: dict[str, int],
    issues: pd.DataFrame,
    checklist: pd.DataFrame,
    commands: pd.DataFrame,
    stage142_summary: pd.DataFrame,
) -> pd.DataFrame:
    hard_stop_count = int(issues["hard_stop"].sum()) if not issues.empty else 0
    checklist_blocks = int((checklist["pass_now"] == 0).sum()) if not checklist.empty else 0
    command_safe = int(
        not commands.empty
        and int(commands[["mutates_official_config", "true_engine_run", "ab_triggered", "order_api_called", "ctp_connected"]].sum().sum()) == 0
    )
    stage142_ready = int(not stage142_summary.empty and int(stage142_summary.iloc[0].get("validator_ready", 0)) == 1)
    expected_blocked = int(summary_flags["default_template_mode"] == 1 and hard_stop_count > 0 and summary_flags["preflight_pass"] == 0)
    rows = [
        {
            "gate_id": "stage142_dependency_ready",
            "observed": stage142_ready,
            "required": 1,
            "pass_now": stage142_ready,
            "severity": "dependency_hard",
        },
        {
            "gate_id": "linter_detected_hard_stops",
            "observed": int(hard_stop_count > 0),
            "required": 1,
            "pass_now": int(hard_stop_count > 0),
            "severity": "selftest_hard",
        },
        {
            "gate_id": "template_default_blocked",
            "observed": expected_blocked,
            "required": 1,
            "pass_now": expected_blocked,
            "severity": "anti_selection_hard",
        },
        {
            "gate_id": "checklist_has_blocks",
            "observed": int(checklist_blocks > 0),
            "required": 1,
            "pass_now": int(checklist_blocks > 0),
            "severity": "anti_selection_hard",
        },
        {
            "gate_id": "operator_commands_safe",
            "observed": command_safe,
            "required": 1,
            "pass_now": command_safe,
            "severity": "execution_safety_hard",
        },
    ]
    return pd.DataFrame(rows)


def _write_report(
    summary: pd.DataFrame,
    issues: pd.DataFrame,
    file_audit: pd.DataFrame,
    visual_audit: pd.DataFrame,
    checklist: pd.DataFrame,
    commands: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    lines = [
        f"# {STAGE} candidate package preflight linter",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- scope: scan a candidate package before Stage142 validation for template residue, fake provenance, non-passing evidence, and placeholder visuals.",
        "",
        "## External Research Judgment",
        "",
        "- pre-commit style checks are useful because they fail early before downstream validation is run.",
        "- Frictionless and jsonschema error outputs motivate a flat, machine-readable issue catalog.",
        "- Great Expectations Data Docs motivate a human-readable report alongside the CSV artifacts.",
        "",
        "## Summary",
        "",
        _md_table(summary.drop(columns=["candidate_package_dir"], errors="ignore")),
        "",
        "## Issues",
        "",
        _md_table(issues[["issue_code", "severity", "path", "field", "observed", "operator_action"]], max_rows=60) if not issues.empty else "_no issues_",
        "",
        "## Checklist",
        "",
        _md_table(checklist),
        "",
        "## Visual Audit",
        "",
        _md_table(visual_audit),
        "",
        "## Operator Commands",
        "",
        _md_table(commands[["command_id", "command", "purpose"]]),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{ISSUE_CHART_OUT.name}`",
        f"- `{VISUAL_CHART_OUT.name}`",
        f"- `{CHECKLIST_CHART_OUT.name}`",
        f"- `{GATE_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _plot_official_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage145 preflight linter: template residue blocked before Stage142", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#14532D", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#B45309", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3657D6", linewidth=1.0)
    axes[2].axhline(100, color="#333333", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    status_cols = [
        "linter_ready",
        "default_template_blocked",
        "preflight_pass",
        "true_engine_run",
        "official_config_changed",
    ]
    matrix = summary[status_cols].T
    matrix.columns = ["status"]
    matrix.plot(kind="bar", ax=axes[3], legend=False, color="#0F766E")
    axes[3].set_title("Preflight linter status")
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


def _plot_issue_matrix(issues: pd.DataFrame) -> None:
    if issues.empty:
        frame = pd.DataFrame([{"issue_code": "no_issue", "hard_stop": 0}])
    else:
        frame = (
            issues.groupby("issue_code", as_index=False)
            .agg(hard_stop=("hard_stop", "max"), issue_count=("issue_code", "size"))
            .sort_values("issue_code")
        )
        frame["has_issue"] = 1
    value_cols = ["has_issue", "hard_stop"] if "has_issue" in frame.columns else ["hard_stop"]
    _plot_matrix(frame, "issue_code", value_cols, "Stage145 issue matrix", ISSUE_CHART_OUT)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage145 candidate package preflight linter.")
    parser.add_argument(
        "--candidate-package-dir",
        default=str(STAGE144_TEMPLATE_DIR),
        help="Candidate package directory to lint. Default scans the Stage144 template as a blocking selftest.",
    )
    parser.add_argument("--case-id", default="stage144_template_default_preflight")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    package_dir = Path(args.candidate_package_dir).resolve()
    curve = _load_curve()
    schema = _read_json(STAGE142_SCHEMA_IN)
    stage142_summary = _read_csv(STAGE142_SUMMARY_IN)
    stage144_summary = _read_csv(STAGE144_SUMMARY_IN)
    if not schema:
        raise RuntimeError(f"missing Stage142 schema: {STAGE142_SCHEMA_IN}")
    if stage142_summary.empty:
        raise RuntimeError(f"missing Stage142 summary: {STAGE142_SUMMARY_IN}")
    requirements = _schema_requirements(schema)
    reference_hashes = _template_hashes(requirements)
    issues, file_audit, visual_audit, checklist = _run_linter(package_dir, requirements, reference_hashes)
    hard_stop_count = int(issues["hard_stop"].sum()) if not issues.empty else 0
    issue_count = len(issues)
    preflight_pass = int(hard_stop_count == 0 and not checklist.empty and int(checklist["pass_now"].sum()) == len(checklist))
    default_template_mode = int(package_dir == STAGE144_TEMPLATE_DIR.resolve())
    default_template_blocked = int(default_template_mode == 1 and preflight_pass == 0 and hard_stop_count > 0)
    commands = _operator_commands(package_dir)
    summary_flags = {
        "default_template_mode": default_template_mode,
        "preflight_pass": preflight_pass,
    }
    gate = _gate_status(summary_flags, issues, checklist, commands, stage142_summary)
    linter_ready = int(gate["pass_now"].sum() == len(gate))
    decision = (
        "stage145_preflight_linter_ready_template_blocked_no_strategy"
        if linter_ready and default_template_blocked
        else "stage145_preflight_linter_attention_required_no_strategy"
    )
    row142 = stage142_summary.iloc[0]
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "case_id": args.case_id,
                "decision": decision,
                "stage142_decision": row142.get("decision", ""),
                "stage144_decision": stage144_summary.iloc[0].get("decision", "") if not stage144_summary.empty else "",
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "linter_ready": linter_ready,
                "default_template_mode": default_template_mode,
                "default_template_blocked": default_template_blocked,
                "candidate_package_exists": int(package_dir.exists()),
                "preflight_pass": preflight_pass,
                "issue_count": issue_count,
                "hard_stop_count": hard_stop_count,
                "check_count": len(checklist),
                "check_pass_count": int(checklist["pass_now"].sum()) if not checklist.empty else 0,
                "file_audit_count": len(file_audit),
                "placeholder_text_file_count": int((file_audit["placeholder_token_count"] > 0).sum()) if not file_audit.empty else 0,
                "visual_audit_count": len(visual_audit),
                "visual_placeholder_hash_match_count": int(visual_audit["placeholder_hash_match"].sum()) if not visual_audit.empty else 0,
                "safe_operator_command_count": int(commands["allowed_now"].sum()),
                "unsafe_operator_command_count": int(len(commands) - commands["allowed_now"].sum()),
                "gate_pass_count": int(gate["pass_now"].sum()),
                "gate_count": len(gate),
                "current_package_promotion_allowed": 0,
                "real_candidate_package_supplied": int(default_template_mode == 0),
                "real_stage112_intake_allowed_now": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "candidate_package_dir": str(package_dir),
                "end_equity": float(row142.get("end_equity", np.nan)),
                "total_return_pct": float(row142.get("total_return_pct", np.nan)),
                "max_drawdown_pct": float(row142.get("max_drawdown_pct", np.nan)),
                "sharpe": float(row142.get("sharpe", np.nan)),
                "total_slippage": float(row142.get("total_slippage", np.nan)),
                "total_trade_count": float(row142.get("total_trade_count", np.nan)),
                "closed_lot_win_rate_pct": float(row142.get("closed_lot_win_rate_pct", np.nan)),
                "max_broker10_margin_to_equity_pct": float(row142.get("max_broker10_margin_to_equity_pct", np.nan)),
            }
        ]
    )
    _write_csv(summary, SUMMARY_OUT)
    _write_csv(issues, ISSUE_OUT)
    _write_csv(file_audit, FILE_AUDIT_OUT)
    _write_csv(visual_audit, VISUAL_AUDIT_OUT)
    _write_csv(checklist, CHECKLIST_OUT)
    _write_csv(commands, COMMAND_OUT)
    _write_csv(gate, GATE_OUT)
    _write_report(summary, issues, file_audit, visual_audit, checklist, commands, gate)
    _plot_official_path(curve, summary)
    _plot_issue_matrix(issues)
    _plot_matrix(
        visual_audit,
        "artifact_id",
        ["artifact_exists", "placeholder_hash_match", "real_visual_required"],
        "Stage145 visual artifact audit",
        VISUAL_CHART_OUT,
    )
    _plot_matrix(
        checklist,
        "check_id",
        ["pass_now", "required", "hard_stop"],
        "Stage145 preflight checklist",
        CHECKLIST_CHART_OUT,
    )
    _plot_matrix(gate, "gate_id", ["pass_now"], "Stage145 gate status", GATE_CHART_OUT)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "inputs": {
                "candidate_package_dir": str(package_dir),
                "stage142_schema": str(STAGE142_SCHEMA_IN),
                "stage142_summary": str(STAGE142_SUMMARY_IN),
                "stage144_template_dir": str(STAGE144_TEMPLATE_DIR),
            },
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "issue_catalog": str(ISSUE_OUT),
                "file_audit": str(FILE_AUDIT_OUT),
                "visual_audit": str(VISUAL_AUDIT_OUT),
                "preflight_checklist": str(CHECKLIST_OUT),
                "operator_command_manifest": str(COMMAND_OUT),
                "gate_status": str(GATE_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(ISSUE_CHART_OUT),
                    str(VISUAL_CHART_OUT),
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
                "current_package_promotion_allowed": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
