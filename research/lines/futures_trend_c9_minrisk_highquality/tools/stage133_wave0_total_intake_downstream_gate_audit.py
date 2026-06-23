from __future__ import annotations

import argparse
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage133"
MODEL_TAG = "stage133_wave0_total_intake_downstream_gate_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage133_c9_minrisk_wave0_total_intake_downstream_gate_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage133_wave0_total_intake_downstream_gate_audit"
SHADOW_ROOT_BASE = OUTPUT_DIR / "shadow_authorized_microstructure_intake_cases"

STAGE128_TOOL = LINE_DIR / "tools" / "stage128_wave0_full_intake_supergate.py"
STAGE112_TOOL = LINE_DIR / "tools" / "stage112_authorized_microstructure_data_drop_validator.py"
STAGE113_TOOL = LINE_DIR / "tools" / "stage113_microstructure_required_window_coverage.py"

EMPTY_DROP_DIR = LINE_DIR / "outputs" / "stage125_wave0_receipt_preflight_audit" / "empty_drop"
STAGE131_POSITIVE_DROP_DIR = (
    LINE_DIR
    / "outputs"
    / "stage131_wave0_positive_drop_supergate_audit"
    / "positive_drop"
    / "contract_positive_fixture_drop"
)

STAGE128_OUT_DIR = LINE_DIR / "outputs" / "stage128_wave0_full_intake_supergate"
STAGE128_SUMMARY = (
    STAGE128_OUT_DIR
    / "qmt_roll_stage128_c9_minrisk_wave0_full_intake_supergate_summary_"
    "stage128_wave0_full_intake_supergate_v1.csv"
)
STAGE128_CASE_SUMMARY = (
    STAGE128_OUT_DIR
    / "qmt_roll_stage128_c9_minrisk_wave0_full_intake_supergate_case_summary_"
    "stage128_wave0_full_intake_supergate_v1.csv"
)
STAGE128_REQUEST_AUDIT = (
    STAGE128_OUT_DIR
    / "qmt_roll_stage128_c9_minrisk_wave0_full_intake_supergate_request_supergate_audit_"
    "stage128_wave0_full_intake_supergate_v1.csv"
)

STAGE119_OUT_DIR = LINE_DIR / "outputs" / "stage119_wave0_drop_manifest_builder"
STAGE119_CLI_MANIFEST = (
    STAGE119_OUT_DIR
    / "qmt_roll_stage119_c9_minrisk_wave0_drop_manifest_builder_cli_drop_supergate_intake_chain_built_manifest_"
    "stage119_wave0_drop_manifest_builder_v1.csv"
)

STAGE131_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage131_wave0_positive_drop_supergate_audit"
    / "qmt_roll_stage131_c9_minrisk_wave0_positive_drop_supergate_audit_summary_"
    "stage131_wave0_positive_drop_supergate_audit_v1.csv"
)
CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CASE_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_downstream_audit_{MODEL_TAG}.csv"
EXPECTATION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_expectation_audit_{MODEL_TAG}.csv"
STAGE128_CASES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage128_case_snapshots_{MODEL_TAG}.csv"
STAGE128_REQUESTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage128_request_snapshots_{MODEL_TAG}.csv"
SHADOW_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_shadow_intake_manifest_rows_{MODEL_TAG}.csv"
STAGE112_FILE_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage112_shadow_file_audit_{MODEL_TAG}.csv"
STAGE112_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage112_shadow_acceptance_gate_{MODEL_TAG}.csv"
STAGE113_FILE_INDEX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage113_shadow_file_index_{MODEL_TAG}.csv"
STAGE113_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage113_shadow_coverage_gate_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_total_gate_status_{MODEL_TAG}.png"
EXPECTATION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_expectation_matrix_{MODEL_TAG}.png"
CASE_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_downstream_matrix_{MODEL_TAG}.png"
DOWNSTREAM_GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage112_113_shadow_gate_chart_{MODEL_TAG}.png"

DECISION = "stage133_total_intake_downstream_gate_blocks_non_real_data_no_strategy"
CLI_READY_DECISION = "stage133_cli_total_intake_release_ready_for_stage112_113_no_strategy"
CLI_BLOCKED_DECISION = "stage133_cli_total_intake_release_blocked_no_strategy"
CLI_EXPECTATION_FAILED_DECISION = "stage133_cli_total_intake_release_expectation_failed"


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


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "nat"} else text


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


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    if curve.empty:
        raise RuntimeError(f"missing curve input: {CURVE_IN}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _nearest_curve_points(curve: pd.DataFrame, dates: pd.Series) -> pd.DataFrame:
    left = pd.DataFrame({"event_date": pd.to_datetime(dates, errors="coerce").dt.normalize()}).dropna()
    right = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].sort_values("date")
    return pd.merge_asof(left.sort_values("event_date"), right, left_on="event_date", right_on="date", direction="backward")


def _baseline_metrics() -> dict[str, float]:
    stage131 = _read_csv(STAGE131_SUMMARY_IN)
    if not stage131.empty:
        row = stage131.iloc[0]
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
    curve = _load_curve()
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


def _parse_json_stdout(stdout: str) -> dict[str, Any]:
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        return json.loads(stdout[start : end + 1])
    except json.JSONDecodeError:
        return {}


def _run_stage128_case(total_case_id: str, drop_dir: Path, expected_stage112_intake: int) -> dict[str, Any]:
    completed = subprocess.run(
        [
            sys.executable,
            str(STAGE128_TOOL),
            "--drop-dir",
            str(drop_dir.expanduser().resolve()),
            "--expected-stage112-intake",
            str(expected_stage112_intake),
        ],
        cwd=REPO_DIR,
        text=True,
        capture_output=True,
        check=False,
        timeout=420,
    )
    parsed = _parse_json_stdout(completed.stdout)
    summary = _read_csv(STAGE128_SUMMARY)
    case_summary = _read_csv(STAGE128_CASE_SUMMARY)
    requests = _read_csv(STAGE128_REQUEST_AUDIT)
    if not case_summary.empty:
        case_summary["total_case_id"] = total_case_id
    if not requests.empty:
        requests["total_case_id"] = total_case_id
    built_manifest = _read_csv(STAGE119_CLI_MANIFEST)
    manifest_copy = OUTPUT_DIR / f"{OUTPUT_PREFIX}_{total_case_id}_stage119_manifest_snapshot_{MODEL_TAG}.csv"
    if not built_manifest.empty:
        _write_csv(built_manifest, manifest_copy)
    return {
        "total_case_id": total_case_id,
        "drop_dir": str(drop_dir.expanduser().resolve()),
        "expected_stage112_intake": expected_stage112_intake,
        "returncode": int(completed.returncode),
        "stdout_json_found": int(bool(parsed)),
        "stage128_summary": summary.copy(),
        "stage128_case_summary": case_summary.copy(),
        "stage128_request_audit": requests.copy(),
        "stage119_manifest": built_manifest.copy(),
        "manifest_snapshot": str(manifest_copy) if not built_manifest.empty else "",
        "stdout_tail": completed.stdout[-500:],
        "stderr_tail": completed.stderr[-500:],
    }


def _restore_stage128_default() -> int:
    completed = subprocess.run(
        [sys.executable, str(STAGE128_TOOL)],
        cwd=REPO_DIR,
        text=True,
        capture_output=True,
        check=False,
        timeout=420,
    )
    parsed = _parse_json_stdout(completed.stdout)
    return int(completed.returncode == 0 and parsed.get("negative_selftest_pass", 0) == 1)


def _to_stage112_manifest(source_manifest: pd.DataFrame, total_case_id: str, stage112_module) -> pd.DataFrame:
    if source_manifest.empty:
        return pd.DataFrame()
    risk = _read_csv(stage112_module.STAGE108_RISK_IN)
    right_tail_required = int(pd.to_numeric(risk.get("right_tail_visual", 0), errors="coerce").fillna(0).sum())
    bottom_loss_required = int(pd.to_numeric(risk.get("bottom_loss_visual", 0), errors="coerce").fillna(0).sum())
    rows: list[dict[str, Any]] = []
    for _, row in source_manifest.iterrows():
        rows.append(
            {
                "dataset_id": _clean(row.get("dataset")) or f"{total_case_id}_dataset",
                "schema_type": _clean(row.get("schema_delivered")) or _clean(row.get("required_schema_request")),
                "source_vendor": _clean(row.get("vendor")),
                "source_license": _clean(row.get("license_id")),
                "exchange": _clean(row.get("exchange")),
                "symbol": _clean(row.get("product")),
                "vt_symbol": _clean(row.get("vt_symbol")),
                "trading_day": _clean(row.get("trading_day")),
                "start_ts": _clean(row.get("request_start")),
                "end_ts": _clean(row.get("request_end")),
                "timezone": _clean(row.get("ts_event_timezone")) or "Asia/Shanghai",
                "data_file": _clean(row.get("normalized_parquet_file")),
                "raw_file": _clean(row.get("raw_file")),
                "raw_sha256": _clean(row.get("raw_sha256")),
                "schema_hash": _clean(row.get("schema_hash")),
                "proof_file": _clean(row.get("proof_file")),
                "coverage_proof": _clean(row.get("capture_continuity_proof")),
                "timestamp_ready_order_coverage_pct": 100.0,
                "right_tail_covered_count": right_tail_required,
                "bottom_loss_covered_count": bottom_loss_required,
                "notes": (
                    f"stage133_total_gate_probe total_case_id={total_case_id}; "
                    f"wave_id={_clean(row.get('wave_id'))}; "
                    f"request_id={_clean(row.get('request_id'))}; "
                    f"source_notes={_clean(row.get('notes'))}"
                ),
            }
        )
    return pd.DataFrame(rows)


def _run_downstream_shadow(
    total_case_id: str,
    source_manifest: pd.DataFrame,
    stage112_module,
    stage113_module,
) -> dict[str, Any]:
    shadow_root = SHADOW_ROOT_BASE / total_case_id
    if shadow_root.exists():
        shutil.rmtree(shadow_root)
    shadow_root.mkdir(parents=True, exist_ok=True)
    manifest = _to_stage112_manifest(source_manifest, total_case_id, stage112_module)
    if manifest.empty:
        return {
            "shadow_root": str(shadow_root),
            "manifest_rows": 0,
            "stage112_inventory": pd.DataFrame(),
            "stage112_files": pd.DataFrame(),
            "stage112_gate": pd.DataFrame(),
            "stage113_file_index": pd.DataFrame(),
            "stage113_gate": pd.DataFrame(),
        }
    manifest_path = shadow_root / "manifest.csv"
    _write_csv(manifest, manifest_path)

    original_112_roots = list(stage112_module.INTAKE_ROOTS)
    original_113_roots = list(stage113_module.INTAKE_ROOTS)
    try:
        stage112_module.INTAKE_ROOTS = [shadow_root]
        stage113_module.INTAKE_ROOTS = [shadow_root]

        risk = _read_csv(stage112_module.STAGE108_RISK_IN)
        inventory, files = stage112_module._scan_intake_roots(risk)
        coverage = stage112_module._coverage_requirements(risk, inventory)
        stage112_gate = stage112_module._acceptance_gate(inventory, files, coverage)

        windows = stage113_module._build_required_windows()
        file_index = stage113_module._scan_intake_files()
        coverage_audit = stage113_module._coverage_audit(windows, file_index)
        candidate_summary = stage113_module._candidate_summary(windows, coverage_audit)
        stage113_gate = stage113_module._coverage_gate(windows, candidate_summary, coverage_audit, file_index)
    finally:
        stage112_module.INTAKE_ROOTS = original_112_roots
        stage113_module.INTAKE_ROOTS = original_113_roots

    for frame in [inventory, files, stage112_gate, file_index, stage113_gate]:
        if not frame.empty:
            frame["total_case_id"] = total_case_id
    manifest["total_case_id"] = total_case_id
    return {
        "shadow_root": str(shadow_root),
        "manifest_rows": len(manifest),
        "manifest": manifest,
        "stage112_inventory": inventory,
        "stage112_files": files,
        "stage112_gate": stage112_gate,
        "stage113_file_index": file_index,
        "stage113_gate": stage113_gate,
    }


def _case_row(total_case_id: str, result: dict[str, Any], downstream: dict[str, Any] | None) -> dict[str, Any]:
    stage128_summary = result["stage128_summary"]
    stage128_cases = result["stage128_case_summary"]
    stage128_summary_row = stage128_summary.iloc[0] if not stage128_summary.empty else pd.Series(dtype=object)
    stage128_case_row = stage128_cases.iloc[0] if not stage128_cases.empty else pd.Series(dtype=object)
    stage128_ready = int(stage128_case_row.get("final_supergate_ready", 0) or 0)
    strategy_allowed = int(stage128_case_row.get("strategy_use_allowed_now", 0) or 0)

    if downstream is None:
        return {
            "total_case_id": total_case_id,
            "drop_dir": result["drop_dir"],
            "stage128_returncode": int(result["returncode"]),
            "stage128_full_supergate_ready": stage128_ready,
            "stage128_real_w0_data_delivered_claim": int(stage128_summary_row.get("real_w0_data_delivered", 0) or 0),
            "stage128_strategy_allowed": strategy_allowed,
            "downstream_action": "skipped_stage128_not_ready",
            "shadow_manifest_rows": 0,
            "stage112_fixture_marker_count": 0,
            "stage112_basic_intake_pass_count": 0,
            "stage112_rule_ready_count": 0,
            "stage113_fixture_marker_count": 0,
            "stage113_indexed_file_count": 0,
            "stage113_coverage_gate_pass_count": 0,
            "downstream_release_allowed_now": 0,
        }

    stage112_files = downstream["stage112_files"]
    stage113_index = downstream["stage113_file_index"]
    stage113_gate = downstream["stage113_gate"]
    stage112_marker_count = (
        int(stage112_files.get("old_source_marker", pd.Series(dtype=str)).map(_clean).ne("").sum())
        if not stage112_files.empty
        else 0
    )
    stage112_basic = (
        int(pd.to_numeric(stage112_files.get("basic_intake_pass", 0), errors="coerce").fillna(0).sum())
        if not stage112_files.empty
        else 0
    )
    stage112_ready = (
        int(pd.to_numeric(stage112_files.get("rule_research_ready", 0), errors="coerce").fillna(0).sum())
        if not stage112_files.empty
        else 0
    )
    stage113_marker = (
        int(stage113_index.get("read_error", pd.Series(dtype=str)).astype(str).str.contains("blocked_local_fixture_marker", na=False).sum())
        if not stage113_index.empty
        else 0
    )
    stage113_indexed = (
        int(pd.to_numeric(stage113_index.get("file_exists", 0), errors="coerce").fillna(0).sum())
        if not stage113_index.empty
        else 0
    )
    stage113_gate_pass = (
        int(pd.to_numeric(stage113_gate.get("pass_now", 0), errors="coerce").fillna(0).sum())
        if not stage113_gate.empty
        else 0
    )
    downstream_release = int(stage128_ready == 1 and stage112_ready > 0 and stage113_gate_pass == len(stage113_gate) and stage113_indexed > 0)
    return {
        "total_case_id": total_case_id,
        "drop_dir": result["drop_dir"],
        "stage128_returncode": int(result["returncode"]),
        "stage128_full_supergate_ready": stage128_ready,
        "stage128_real_w0_data_delivered_claim": int(stage128_summary_row.get("real_w0_data_delivered", 0) or 0),
        "stage128_strategy_allowed": strategy_allowed,
        "downstream_action": "stage112_113_shadow_checked",
        "shadow_manifest_rows": int(downstream["manifest_rows"]),
        "stage112_fixture_marker_count": stage112_marker_count,
        "stage112_basic_intake_pass_count": stage112_basic,
        "stage112_rule_ready_count": stage112_ready,
        "stage113_fixture_marker_count": stage113_marker,
        "stage113_indexed_file_count": stage113_indexed,
        "stage113_coverage_gate_pass_count": stage113_gate_pass,
        "downstream_release_allowed_now": downstream_release,
    }


def _default_expectations(case_audit: pd.DataFrame, stage128_default_restored: int) -> pd.DataFrame:
    empty = case_audit[case_audit["total_case_id"].eq("empty_drop_total_gate")]
    fixture = case_audit[case_audit["total_case_id"].eq("stage131_positive_fixture_total_gate")]
    empty_row = empty.iloc[0] if not empty.empty else pd.Series(dtype=object)
    fixture_row = fixture.iloc[0] if not fixture.empty else pd.Series(dtype=object)
    rows = [
        {
            "expectation_id": "empty_drop_stage128_not_ready",
            "required": "0",
            "observed": str(empty_row.get("stage128_full_supergate_ready", "")),
            "pass_now": int(int(empty_row.get("stage128_full_supergate_ready", -1)) == 0),
        },
        {
            "expectation_id": "empty_drop_downstream_skipped",
            "required": "skipped_stage128_not_ready",
            "observed": str(empty_row.get("downstream_action", "")),
            "pass_now": int(str(empty_row.get("downstream_action", "")) == "skipped_stage128_not_ready"),
        },
        {
            "expectation_id": "stage131_fixture_stage128_positive_ready",
            "required": "1",
            "observed": str(fixture_row.get("stage128_full_supergate_ready", "")),
            "pass_now": int(int(fixture_row.get("stage128_full_supergate_ready", -1)) == 1),
        },
        {
            "expectation_id": "stage131_fixture_stage112_marker_detected",
            "required": ">=1",
            "observed": str(fixture_row.get("stage112_fixture_marker_count", "")),
            "pass_now": int(int(fixture_row.get("stage112_fixture_marker_count", 0)) >= 1),
        },
        {
            "expectation_id": "stage131_fixture_stage112_rule_blocked",
            "required": "0",
            "observed": str(fixture_row.get("stage112_rule_ready_count", "")),
            "pass_now": int(int(fixture_row.get("stage112_rule_ready_count", -1)) == 0),
        },
        {
            "expectation_id": "stage131_fixture_stage113_marker_detected",
            "required": ">=1",
            "observed": str(fixture_row.get("stage113_fixture_marker_count", "")),
            "pass_now": int(int(fixture_row.get("stage113_fixture_marker_count", 0)) >= 1),
        },
        {
            "expectation_id": "stage131_fixture_stage113_index_blocked",
            "required": "0",
            "observed": str(fixture_row.get("stage113_indexed_file_count", "")),
            "pass_now": int(int(fixture_row.get("stage113_indexed_file_count", -1)) == 0),
        },
        {
            "expectation_id": "downstream_release_zero_all_cases",
            "required": "0",
            "observed": str(int(pd.to_numeric(case_audit["downstream_release_allowed_now"], errors="coerce").fillna(0).sum())),
            "pass_now": int(pd.to_numeric(case_audit["downstream_release_allowed_now"], errors="coerce").fillna(0).sum() == 0),
        },
        {
            "expectation_id": "stage128_default_restored",
            "required": "1",
            "observed": str(stage128_default_restored),
            "pass_now": stage128_default_restored,
        },
    ]
    return pd.DataFrame(rows)


def _cli_expectations(
    case_audit: pd.DataFrame,
    stage128_default_restored: int,
    expected_downstream_release: int | None,
) -> pd.DataFrame:
    row = case_audit.iloc[0] if not case_audit.empty else pd.Series(dtype=object)
    stage128_returncode = int(row.get("stage128_returncode", -1))
    stage128_ready = int(row.get("stage128_full_supergate_ready", 0) or 0)
    strategy_allowed = int(row.get("stage128_strategy_allowed", 0) or 0)
    downstream_action = str(row.get("downstream_action", ""))
    downstream_release = int(row.get("downstream_release_allowed_now", 0) or 0)
    release_consistent = int(
        (stage128_ready == 0 and downstream_action == "skipped_stage128_not_ready" and downstream_release == 0)
        or (stage128_ready == 1 and downstream_action == "stage112_113_shadow_checked")
    )
    rows = [
        {
            "expectation_id": "cli_stage128_returncode_zero",
            "required": "0",
            "observed": str(stage128_returncode),
            "pass_now": int(stage128_returncode == 0),
        },
        {
            "expectation_id": "cli_strategy_allowed_zero",
            "required": "0",
            "observed": str(strategy_allowed),
            "pass_now": int(strategy_allowed == 0),
        },
        {
            "expectation_id": "cli_downstream_action_consistent_with_stage128",
            "required": "skip if Stage128 blocked; check Stage112/113 if Stage128 ready",
            "observed": f"stage128_ready={stage128_ready};action={downstream_action};release={downstream_release}",
            "pass_now": release_consistent,
        },
        {
            "expectation_id": "stage128_default_restored",
            "required": "1",
            "observed": str(stage128_default_restored),
            "pass_now": stage128_default_restored,
        },
    ]
    if expected_downstream_release is not None:
        rows.append(
            {
                "expectation_id": "cli_downstream_release_matches_expected",
                "required": str(expected_downstream_release),
                "observed": str(downstream_release),
                "pass_now": int(downstream_release == expected_downstream_release),
            }
        )
    return pd.DataFrame(rows)


def _plot_official_path(curve: pd.DataFrame, request_snapshots: pd.DataFrame, case_audit: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage133 total intake gate: Stage128 must be followed by Stage112/113 provenance gates", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#1f5d4a", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#C2410C", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3B5BDB", linewidth=1.0)
    axes[2].axhline(100, color="#333333", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    if not request_snapshots.empty and "trading_day" in request_snapshots.columns:
        for idx, (case_id, group) in enumerate(request_snapshots.groupby("total_case_id")):
            points = _nearest_curve_points(curve, group["trading_day"])
            color = "#B91C1C" if "stage131" in case_id else "#A16207"
            marker = "o" if "stage131" in case_id else "x"
            label = f"{case_id} blocked/downstream-gated"
            axes[0].scatter(points["date"], points["account_equity"] / 1_000_000, color=color, marker=marker, s=28, alpha=0.58, label=label)
            axes[1].scatter(points["date"], points["drawdown_pct"], color=color, marker=marker, s=28, alpha=0.58)
            axes[2].scatter(points["date"], points["broker10_margin_to_equity_pct"], color=color, marker=marker, s=28, alpha=0.58)
        axes[0].legend(loc="upper left", fontsize=8)
    metrics = [
        "stage128_full_supergate_ready",
        "stage112_rule_ready_count",
        "stage113_indexed_file_count",
        "downstream_release_allowed_now",
    ]
    plot = case_audit.set_index("total_case_id")[metrics]
    plot.plot(kind="bar", ax=axes[3], color=["#3B5BDB", "#A16207", "#0F766E", "#15803D"])
    axes[3].set_title("Case release path")
    axes[3].set_ylabel("count / flag")
    axes[3].set_ylim(0, max(1.2, float(plot.to_numpy().max()) + 0.5))
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_expectations(expectations: pd.DataFrame) -> None:
    data = expectations[["pass_now"]].to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(10, 5.5))
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage133 total gate expectations")
    ax.set_xticks([0])
    ax.set_xticklabels(["pass"])
    ax.set_yticks(np.arange(len(expectations)))
    ax.set_yticklabels(expectations["expectation_id"])
    for row in range(data.shape[0]):
        ax.text(0, row, "P" if data[row, 0] == 1 else "F", ha="center", va="center", fontsize=9)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(EXPECTATION_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_case_matrix(case_audit: pd.DataFrame) -> None:
    columns = [
        "stage128_full_supergate_ready",
        "stage112_fixture_marker_count",
        "stage112_rule_ready_count",
        "stage113_fixture_marker_count",
        "stage113_indexed_file_count",
        "downstream_release_allowed_now",
    ]
    matrix = case_audit.set_index("total_case_id")[columns].copy()
    matrix["stage112_fixture_marker_count"] = matrix["stage112_fixture_marker_count"].gt(0).astype(int)
    matrix["stage113_fixture_marker_count"] = matrix["stage113_fixture_marker_count"].gt(0).astype(int)
    matrix["stage112_rule_ready_count"] = matrix["stage112_rule_ready_count"].gt(0).astype(int)
    matrix["stage113_indexed_file_count"] = matrix["stage113_indexed_file_count"].gt(0).astype(int)
    data = matrix.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(11, 4.8))
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage133 case downstream matrix")
    ax.set_xticks(np.arange(len(columns)))
    ax.set_xticklabels(columns, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=9)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(CASE_MATRIX_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_downstream_gate(stage112_gate: pd.DataFrame, stage113_gate: pd.DataFrame) -> None:
    rows = []
    if not stage112_gate.empty:
        for _, row in stage112_gate.iterrows():
            rows.append(
                {
                    "gate_id": f"stage112::{row.get('gate_id')}",
                    "pass_now": int(pd.to_numeric(row.get("pass_now", 0), errors="coerce") or 0),
                }
            )
    if not stage113_gate.empty:
        for _, row in stage113_gate.iterrows():
            rows.append(
                {
                    "gate_id": f"stage113::{row.get('gate_id')}",
                    "pass_now": int(pd.to_numeric(row.get("pass_now", 0), errors="coerce") or 0),
                }
            )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return
    data = frame[["pass_now"]].to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(11, max(5.0, len(frame) * 0.32)))
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage133 Stage112/113 shadow gate status")
    ax.set_xticks([0])
    ax.set_xticklabels(["pass"])
    ax.set_yticks(np.arange(len(frame)))
    ax.set_yticklabels(frame["gate_id"], fontsize=8)
    for row in range(data.shape[0]):
        ax.text(0, row, "P" if data[row, 0] == 1 else "F", ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(DOWNSTREAM_GATE_CHART_OUT, dpi=170)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, case_audit: pd.DataFrame, expectations: pd.DataFrame) -> None:
    report = [
        f"# {STAGE} W0 total intake downstream gate audit",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- scope: Stage128 -> Stage112 -> Stage113 release discipline only; no strategy rule, true engine, A/B, CTP, order API, or official config change.",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Case Audit",
        "",
        _md_table(case_audit),
        "",
        "## Expectation Audit",
        "",
        _md_table(expectations),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{EXPECTATION_CHART_OUT.name}`",
        f"- `{CASE_MATRIX_CHART_OUT.name}`",
        f"- `{DOWNSTREAM_GATE_CHART_OUT.name}`",
        "",
        "## Judgment",
        "",
        "Stage128 is necessary but not sufficient. A data drop can be structurally complete for the receipt chain while still being non-real or local fixture data. Stage133 forces downstream release to require Stage112/113 provenance and coverage gates after Stage128.",
    ]
    REPORT_OUT.write_text("\n".join(report) + "\n", encoding="utf-8")


def _build_default_cases() -> list[tuple[str, Path, int]]:
    return [
        ("empty_drop_total_gate", EMPTY_DROP_DIR, 0),
        ("stage131_positive_fixture_total_gate", STAGE131_POSITIVE_DROP_DIR, 1),
    ]


def _build_cli_cases(drop_dir: Path, expected_stage112_intake: int, case_id: str) -> list[tuple[str, Path, int]]:
    return [(case_id, drop_dir, expected_stage112_intake)]


def main(
    drop_dir: Path | None = None,
    expected_stage112_intake: int = 1,
    case_id: str = "cli_total_gate",
    expected_downstream_release: int | None = None,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if SHADOW_ROOT_BASE.exists():
        shutil.rmtree(SHADOW_ROOT_BASE)
    SHADOW_ROOT_BASE.mkdir(parents=True, exist_ok=True)

    stage112_module = _load_module("stage112_authorized_microstructure_data_drop_validator_stage133", STAGE112_TOOL)
    stage113_module = _load_module("stage113_microstructure_required_window_coverage_stage133", STAGE113_TOOL)

    cli_mode = int(drop_dir is not None)
    cases = (
        _build_cli_cases(drop_dir, expected_stage112_intake, case_id)
        if drop_dir is not None
        else _build_default_cases()
    )
    results = []
    case_rows = []
    stage128_case_frames = []
    stage128_request_frames = []
    manifest_frames = []
    stage112_file_frames = []
    stage112_gate_frames = []
    stage113_file_frames = []
    stage113_gate_frames = []

    for total_case_id, drop_dir, expected in cases:
        result = _run_stage128_case(total_case_id, drop_dir, expected)
        results.append(result)
        if not result["stage128_case_summary"].empty:
            stage128_case_frames.append(result["stage128_case_summary"])
        if not result["stage128_request_audit"].empty:
            stage128_request_frames.append(result["stage128_request_audit"])

        stage128_cases = result["stage128_case_summary"]
        stage128_ready = int(stage128_cases.iloc[0].get("final_supergate_ready", 0) or 0) if not stage128_cases.empty else 0
        if stage128_ready == 1:
            downstream = _run_downstream_shadow(total_case_id, result["stage119_manifest"], stage112_module, stage113_module)
            if "manifest" in downstream and not downstream["manifest"].empty:
                manifest_frames.append(downstream["manifest"])
            if not downstream["stage112_files"].empty:
                stage112_file_frames.append(downstream["stage112_files"])
            if not downstream["stage112_gate"].empty:
                stage112_gate_frames.append(downstream["stage112_gate"])
            if not downstream["stage113_file_index"].empty:
                stage113_file_frames.append(downstream["stage113_file_index"])
            if not downstream["stage113_gate"].empty:
                stage113_gate_frames.append(downstream["stage113_gate"])
            case_rows.append(_case_row(total_case_id, result, downstream))
        else:
            case_rows.append(_case_row(total_case_id, result, None))

    stage128_default_restored = _restore_stage128_default()

    curve = _load_curve()
    metrics = _baseline_metrics()
    case_audit = pd.DataFrame(case_rows)
    expectations = (
        _cli_expectations(case_audit, stage128_default_restored, expected_downstream_release)
        if cli_mode
        else _default_expectations(case_audit, stage128_default_restored)
    )
    stage128_cases = pd.concat(stage128_case_frames, ignore_index=True) if stage128_case_frames else pd.DataFrame()
    stage128_requests = pd.concat(stage128_request_frames, ignore_index=True) if stage128_request_frames else pd.DataFrame()
    shadow_manifest = pd.concat(manifest_frames, ignore_index=True) if manifest_frames else pd.DataFrame()
    stage112_files = pd.concat(stage112_file_frames, ignore_index=True) if stage112_file_frames else pd.DataFrame()
    stage112_gate = pd.concat(stage112_gate_frames, ignore_index=True) if stage112_gate_frames else pd.DataFrame()
    stage113_files = pd.concat(stage113_file_frames, ignore_index=True) if stage113_file_frames else pd.DataFrame()
    stage113_gate = pd.concat(stage113_gate_frames, ignore_index=True) if stage113_gate_frames else pd.DataFrame()

    expectation_pass_count = int(pd.to_numeric(expectations["pass_now"], errors="coerce").fillna(0).sum())
    downstream_release_count = int(pd.to_numeric(case_audit["downstream_release_allowed_now"], errors="coerce").fillna(0).sum())
    release_verdict = "ready_for_stage112_113_minutes_research" if downstream_release_count > 0 else "blocked_no_downstream_release"
    if cli_mode:
        decision = CLI_READY_DECISION if downstream_release_count > 0 else CLI_BLOCKED_DECISION
        if expectation_pass_count != len(expectations):
            decision = CLI_EXPECTATION_FAILED_DECISION
    else:
        decision = DECISION if expectation_pass_count == len(expectations) and downstream_release_count == 0 else "stage133_total_intake_downstream_gate_failed"

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
                "cli_case_id": case_id if cli_mode else "",
                "expected_stage112_intake": expected_stage112_intake if cli_mode else "",
                "expected_downstream_release": "" if expected_downstream_release is None else expected_downstream_release,
                "release_verdict": release_verdict,
                "case_count": len(case_audit),
                "stage128_ready_case_count": int(pd.to_numeric(case_audit["stage128_full_supergate_ready"], errors="coerce").fillna(0).sum()),
                "stage112_checked_case_count": int(case_audit["downstream_action"].astype(str).eq("stage112_113_shadow_checked").sum()),
                "stage112_fixture_marker_count": int(pd.to_numeric(case_audit["stage112_fixture_marker_count"], errors="coerce").fillna(0).sum()),
                "stage112_rule_ready_count": int(pd.to_numeric(case_audit["stage112_rule_ready_count"], errors="coerce").fillna(0).sum()),
                "stage113_fixture_marker_count": int(pd.to_numeric(case_audit["stage113_fixture_marker_count"], errors="coerce").fillna(0).sum()),
                "stage113_indexed_file_count": int(pd.to_numeric(case_audit["stage113_indexed_file_count"], errors="coerce").fillna(0).sum()),
                "downstream_release_allowed_count": downstream_release_count,
                "expectation_pass_count": expectation_pass_count,
                "expectation_count": len(expectations),
                "stage128_default_restored": stage128_default_restored,
                "real_w0_data_delivered": int(cli_mode and downstream_release_count > 0),
                "real_stage112_intake_allowed_now": int(cli_mode and downstream_release_count > 0),
                "true_engine_allowed": 0,
                "strategy_feature_usable": int(cli_mode and downstream_release_count > 0),
                **metrics,
            }
        ]
    )

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(case_audit, CASE_AUDIT_OUT)
    _write_csv(expectations, EXPECTATION_OUT)
    _write_csv(stage128_cases, STAGE128_CASES_OUT)
    _write_csv(stage128_requests, STAGE128_REQUESTS_OUT)
    _write_csv(shadow_manifest, SHADOW_MANIFEST_OUT)
    _write_csv(stage112_files, STAGE112_FILE_AUDIT_OUT)
    _write_csv(stage112_gate, STAGE112_GATE_OUT)
    _write_csv(stage113_files, STAGE113_FILE_INDEX_OUT)
    _write_csv(stage113_gate, STAGE113_GATE_OUT)

    _plot_official_path(curve, stage128_requests, case_audit)
    _plot_expectations(expectations)
    _plot_case_matrix(case_audit)
    _plot_downstream_gate(stage112_gate, stage113_gate)
    _write_report(summary, case_audit, expectations)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "release_verdict": release_verdict,
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "case_audit": str(CASE_AUDIT_OUT),
                "expectations": str(EXPECTATION_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(EXPECTATION_CHART_OUT),
                    str(CASE_MATRIX_CHART_OUT),
                    str(DOWNSTREAM_GATE_CHART_OUT),
                ],
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
    parser = argparse.ArgumentParser(description="Run Stage128 -> Stage112 -> Stage113 total W0 intake release verdict.")
    parser.add_argument("--drop-dir", type=Path, default=None, help="Real or candidate W0 drop directory. Omit to run default audit.")
    parser.add_argument("--case-id", default="cli_total_gate", help="Case id used in CLI mode.")
    parser.add_argument("--expected-stage112-intake", type=int, choices=[0, 1], default=1)
    parser.add_argument("--expected-downstream-release", type=int, choices=[0, 1], default=None)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    main(
        drop_dir=args.drop_dir,
        expected_stage112_intake=args.expected_stage112_intake,
        case_id=args.case_id,
        expected_downstream_release=args.expected_downstream_release,
    )
