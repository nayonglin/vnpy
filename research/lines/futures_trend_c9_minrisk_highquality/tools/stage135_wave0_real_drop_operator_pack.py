from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage135"
MODEL_TAG = "stage135_wave0_real_drop_operator_pack_v1"
OUTPUT_PREFIX = "qmt_roll_stage135_c9_minrisk_wave0_real_drop_operator_pack"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage135_wave0_real_drop_operator_pack"

STAGE125_TOOL = LINE_DIR / "tools" / "stage125_wave0_receipt_preflight_audit.py"
STAGE133_TOOL = LINE_DIR / "tools" / "stage133_wave0_total_intake_downstream_gate_audit.py"
STAGE134_TOOL = LINE_DIR / "tools" / "stage134_wave0_total_gate_cli_entry_selftest.py"

STAGE124_DIR = LINE_DIR / "outputs" / "stage124_wave0_delivery_handoff_package"
STAGE124_FILE_CONTRACT_IN = (
    STAGE124_DIR
    / "qmt_roll_stage124_c9_minrisk_wave0_delivery_handoff_package_delivery_file_contract_"
    "stage124_wave0_delivery_handoff_package_v1.csv"
)
STAGE124_READINESS_IN = (
    STAGE124_DIR
    / "qmt_roll_stage124_c9_minrisk_wave0_delivery_handoff_package_readiness_gate_status_"
    "stage124_wave0_delivery_handoff_package_v1.csv"
)
STAGE124_README_IN = (
    STAGE124_DIR
    / "qmt_roll_stage124_c9_minrisk_wave0_delivery_handoff_package_W0_DELIVERY_README_"
    "stage124_wave0_delivery_handoff_package_v1.md"
)
STAGE134_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage134_wave0_total_gate_cli_entry_selftest"
    / "qmt_roll_stage134_c9_minrisk_wave0_total_gate_cli_entry_selftest_summary_"
    "stage134_wave0_total_gate_cli_entry_selftest_v1.csv"
)
CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

CANDIDATE_DROP_DIRS = [
    LINE_DIR / "inputs" / "w0_real_drop",
    LINE_DIR / "inputs" / "authorized_w0_real_drop",
    LINE_DIR / "data" / "w0_real_drop",
    LINE_DIR / "data" / "authorized_w0_real_drop",
    LINE_DIR / "incoming" / "w0_real_drop",
]
FORBIDDEN_FIXTURE_DIR = (
    LINE_DIR
    / "outputs"
    / "stage131_wave0_positive_drop_supergate_audit"
    / "positive_drop"
    / "contract_positive_fixture_drop"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CANDIDATE_DIR_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_drop_dir_audit_{MODEL_TAG}.csv"
ROLE_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_role_audit_{MODEL_TAG}.csv"
COMMAND_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_operator_command_manifest_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_operator_pack_gate_status_{MODEL_TAG}.csv"
RUNBOOK_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_REAL_W0_OPERATOR_RUNBOOK_{MODEL_TAG}.md"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_operator_pack_status_{MODEL_TAG}.png"
CANDIDATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_drop_dir_matrix_{MODEL_TAG}.png"
COMMAND_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_operator_command_matrix_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_operator_gate_chart_{MODEL_TAG}.png"

DECISION = "stage135_real_drop_operator_pack_ready_waiting_for_real_w0_no_strategy"
REQUEST_RE = re.compile(r"stage114_req_\d{4}")
RAW_SUFFIXES = {".raw", ".dbn", ".dat", ".bin", ".gz", ".zip"}
ROLE_ORDER = ["raw", "normalized_parquet", "proof"]


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


def _role_for_file(path: Path) -> str:
    parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    suffix = "".join(path.suffixes).lower()
    if path.suffix.lower() == ".parquet" or "parquet" in parts or "normalized" in name:
        return "normalized_parquet"
    if path.suffix.lower() == ".json" and ("proof" in parts or "proof" in name):
        return "proof"
    if "raw" in parts or "raw" in name or path.suffix.lower() in RAW_SUFFIXES or suffix.endswith(".csv.gz"):
        return "raw"
    return "ignored"


def _request_id_for_path(path: Path) -> str:
    match = REQUEST_RE.search(str(path))
    return match.group(0) if match else ""


def _path_inside(child: Path, parent: Path) -> int:
    try:
        child.resolve().relative_to(parent.resolve())
        return 1
    except ValueError:
        return 0


def _scan_candidate_dirs(file_contract: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    expected_request_count = int(file_contract["request_id"].nunique()) if not file_contract.empty else 0
    expected_file_count = int(file_contract["required_now"].sum()) if not file_contract.empty and "required_now" in file_contract else 0
    dir_rows: list[dict[str, Any]] = []
    role_rows: list[dict[str, Any]] = []
    for drop_dir in CANDIDATE_DROP_DIRS:
        files = sorted(path for path in drop_dir.rglob("*") if path.is_file()) if drop_dir.exists() else []
        inventory = pd.DataFrame(
            [
                {
                    "path": str(path),
                    "request_id": _request_id_for_path(path),
                    "role": _role_for_file(path),
                    "bytes": int(path.stat().st_size),
                }
                for path in files
            ]
        )
        known = inventory[inventory["role"].isin(ROLE_ORDER) & inventory["request_id"].astype(str).ne("")] if not inventory.empty else pd.DataFrame()
        role_counts = known["role"].value_counts().to_dict() if not known.empty else {}
        request_role_complete = 0
        if not known.empty:
            pivot = known.pivot_table(index="request_id", columns="role", values="path", aggfunc="count", fill_value=0)
            for role in ROLE_ORDER:
                if role not in pivot.columns:
                    pivot[role] = 0
            request_role_complete = int((pivot[ROLE_ORDER].ge(1).all(axis=1)).sum())
        forbidden_fixture = _path_inside(drop_dir, FORBIDDEN_FIXTURE_DIR) or _path_inside(FORBIDDEN_FIXTURE_DIR, drop_dir)
        candidate_ready = int(
            drop_dir.exists()
            and int(len(known)) >= expected_file_count
            and request_role_complete >= expected_request_count
            and not forbidden_fixture
        )
        dir_rows.append(
            {
                "drop_dir": str(drop_dir),
                "exists": int(drop_dir.exists()),
                "total_file_count": len(files),
                "known_file_count": int(len(known)),
                "expected_file_count": expected_file_count,
                "raw_file_count": int(role_counts.get("raw", 0)),
                "normalized_parquet_file_count": int(role_counts.get("normalized_parquet", 0)),
                "proof_file_count": int(role_counts.get("proof", 0)),
                "request_count_with_any_role": int(known["request_id"].nunique()) if not known.empty else 0,
                "request_role_complete_count": request_role_complete,
                "expected_request_count": expected_request_count,
                "under_forbidden_fixture_root": int(forbidden_fixture),
                "candidate_ready_for_stage133": candidate_ready,
            }
        )
        for role in ROLE_ORDER:
            role_rows.append(
                {
                    "drop_dir": str(drop_dir),
                    "artifact_role": role,
                    "observed_count": int(role_counts.get(role, 0)),
                    "expected_count": expected_request_count,
                    "pass_now": int(role_counts.get(role, 0) >= expected_request_count and expected_request_count > 0),
                }
            )
    return pd.DataFrame(dir_rows), pd.DataFrame(role_rows)


def _command_manifest() -> pd.DataFrame:
    real_drop = "<real_w0_drop>"
    return pd.DataFrame(
        [
            {
                "step_order": 1,
                "step_id": "receipt_preflight",
                "required_before_next": 1,
                "command": f".py311/bin/python {STAGE125_TOOL.relative_to(REPO_DIR)} --drop-dir {real_drop} --case-id real_w0_receipt_preflight",
                "expected_verdict": "ready_for_stage123=1",
                "blocks_downstream_if_not_met": 1,
            },
            {
                "step_order": 2,
                "step_id": "total_release_verdict",
                "required_before_next": 1,
                "command": (
                    f".py311/bin/python {STAGE133_TOOL.relative_to(REPO_DIR)} "
                    f"--drop-dir {real_drop} --case-id real_w0_total_gate "
                    "--expected-stage112-intake 1 --expected-downstream-release 1"
                ),
                "expected_verdict": "release_verdict=ready_for_stage112_113_minutes_research",
                "blocks_downstream_if_not_met": 1,
            },
            {
                "step_order": 3,
                "step_id": "cli_selftest_if_command_changed",
                "required_before_next": 0,
                "command": f".py311/bin/python {STAGE134_TOOL.relative_to(REPO_DIR)}",
                "expected_verdict": "expectation_pass_count=12/12",
                "blocks_downstream_if_not_met": 1,
            },
            {
                "step_order": 4,
                "step_id": "never_use_stage131_fixture",
                "required_before_next": 1,
                "command": f"do_not_use {FORBIDDEN_FIXTURE_DIR}",
                "expected_verdict": "must remain blocked_no_downstream_release",
                "blocks_downstream_if_not_met": 1,
            },
        ]
    )


def _gate_status(candidate_dirs: pd.DataFrame, command_manifest: pd.DataFrame, file_contract: pd.DataFrame) -> pd.DataFrame:
    stage134 = _read_csv(STAGE134_SUMMARY_IN)
    stage134_pass = int(
        not stage134.empty
        and int(stage134.iloc[0].get("expectation_pass_count", -1)) == int(stage134.iloc[0].get("expectation_count", -2))
    )
    expected_file_count = int(file_contract["required_now"].sum()) if not file_contract.empty and "required_now" in file_contract else 0
    best_known_count = int(candidate_dirs["known_file_count"].max()) if not candidate_dirs.empty else 0
    candidate_ready = int(candidate_dirs["candidate_ready_for_stage133"].sum()) if not candidate_dirs.empty else 0
    rows = [
        {
            "gate_id": "stage124_delivery_contract_available",
            "observed": str(len(file_contract)),
            "required": "123 file contract rows",
            "pass_now": int(len(file_contract) == 123),
            "severity": "planning_hard",
        },
        {
            "gate_id": "stage133_cli_available",
            "observed": str(int(STAGE133_TOOL.exists())),
            "required": "1",
            "pass_now": int(STAGE133_TOOL.exists()),
            "severity": "orchestration_hard",
        },
        {
            "gate_id": "stage134_cli_selftest_passed",
            "observed": str(stage134_pass),
            "required": "1",
            "pass_now": stage134_pass,
            "severity": "orchestration_hard",
        },
        {
            "gate_id": "operator_commands_manifested",
            "observed": str(len(command_manifest)),
            "required": ">=4 command rows",
            "pass_now": int(len(command_manifest) >= 4),
            "severity": "planning_hard",
        },
        {
            "gate_id": "real_drop_candidate_present",
            "observed": str(int(candidate_dirs["exists"].sum()) if not candidate_dirs.empty else 0),
            "required": ">=1 existing candidate dir with files",
            "pass_now": int(best_known_count > 0),
            "severity": "data_hard",
        },
        {
            "gate_id": "real_drop_candidate_complete",
            "observed": f"{best_known_count}/{expected_file_count}",
            "required": "123/123 known files and 41 complete requests",
            "pass_now": int(candidate_ready > 0),
            "severity": "data_hard",
        },
        {
            "gate_id": "forbidden_fixture_not_candidate",
            "observed": str(int(candidate_dirs["under_forbidden_fixture_root"].sum()) if not candidate_dirs.empty else 0),
            "required": "0",
            "pass_now": int(candidate_dirs.empty or int(candidate_dirs["under_forbidden_fixture_root"].sum()) == 0),
            "severity": "anti_selection_hard",
        },
        {
            "gate_id": "true_engine_allowed_zero",
            "observed": "0",
            "required": "0 until Stage133 real release passes",
            "pass_now": 1,
            "severity": "anti_selection_hard",
        },
    ]
    return pd.DataFrame(rows)


def _write_runbook(summary: pd.DataFrame, command_manifest: pd.DataFrame, candidate_dirs: pd.DataFrame, gate: pd.DataFrame) -> None:
    report = [
        "# Stage135 Real W0 Operator Runbook",
        "",
        "## Purpose",
        "",
        "This runbook is the operator-facing entry for a real W0 data drop. It does not create a trading rule and does not allow true-engine or A/B work by itself.",
        "",
        "## Current Verdict",
        "",
        _md_table(summary),
        "",
        "## Candidate Drop Directories",
        "",
        _md_table(candidate_dirs),
        "",
        "## Required Commands",
        "",
        _md_table(command_manifest),
        "",
        "## Gates",
        "",
        _md_table(gate),
        "",
        "## Rules",
        "",
        "- Put real vendor files under one explicit real W0 drop directory, not under `outputs/` and never under Stage131 fixture paths.",
        "- The drop must satisfy the Stage124 contract: 41 raw files, 41 normalized Parquet files, 41 proof JSON files.",
        "- Run the receipt preflight first; then run Stage133 with `--expected-downstream-release 1`.",
        "- Only `release_verdict=ready_for_stage112_113_minutes_research` can unlock minute/orderflow research.",
        "- Any `blocked_no_downstream_release` result keeps strategy, true engine and A/B locked.",
    ]
    RUNBOOK_OUT.write_text("\n".join(report) + "\n", encoding="utf-8")


def _write_report(summary: pd.DataFrame, command_manifest: pd.DataFrame, candidate_dirs: pd.DataFrame, gate: pd.DataFrame) -> None:
    report = [
        f"# {STAGE} real W0 operator pack",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- scope: real W0 drop operator runbook and directory preflight only; no strategy rule, true engine, A/B, CTP, order API, or official config change.",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Candidate Drop Directories",
        "",
        _md_table(candidate_dirs),
        "",
        "## Command Manifest",
        "",
        _md_table(command_manifest),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{CANDIDATE_CHART_OUT.name}`",
        f"- `{COMMAND_CHART_OUT.name}`",
        f"- `{GATE_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(report) + "\n", encoding="utf-8")


def _plot_official_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage135 real W0 operator pack: waiting for real data, release locked", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#1f5d4a", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#C2410C", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3B5BDB", linewidth=1.0)
    axes[2].axhline(100, color="#333333", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    cols = [
        "operator_pack_ready",
        "existing_candidate_dir_count",
        "candidate_ready_count",
        "stage133_release_allowed_now",
    ]
    plot = summary[cols].T
    plot.columns = ["status"]
    plot.plot(kind="bar", ax=axes[3], legend=False, color="#0F766E")
    axes[3].set_ylim(0, max(1.2, float(plot["status"].max()) + 0.5))
    axes[3].set_title("Operator/release status")
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
    fig, ax = plt.subplots(figsize=(max(8.5, len(value_cols) * 1.5), max(4.5, len(matrix) * 0.55)))
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title(title)
    ax.set_xticks(np.arange(len(value_cols)))
    ax.set_xticklabels(value_cols, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=8)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    metrics = _baseline_metrics(curve)
    file_contract = _read_csv(STAGE124_FILE_CONTRACT_IN)
    candidate_dirs, role_audit = _scan_candidate_dirs(file_contract)
    command_manifest = _command_manifest()
    gate = _gate_status(candidate_dirs, command_manifest, file_contract)
    planning_pass = int(gate[~gate["severity"].astype(str).eq("data_hard")]["pass_now"].sum())
    planning_count = int((~gate["severity"].astype(str).eq("data_hard")).sum())
    data_pass = int(gate[gate["severity"].astype(str).eq("data_hard")]["pass_now"].sum())
    data_count = int((gate["severity"].astype(str).eq("data_hard")).sum())
    candidate_ready = int(candidate_dirs["candidate_ready_for_stage133"].sum()) if not candidate_dirs.empty else 0
    expected_file_count = int(file_contract["required_now"].sum()) if not file_contract.empty and "required_now" in file_contract else 0
    best_known_count = int(candidate_dirs["known_file_count"].max()) if not candidate_dirs.empty else 0
    decision = DECISION if planning_pass == planning_count and candidate_ready == 0 else "stage135_real_drop_operator_pack_needs_attention"
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
                "candidate_dir_count": len(candidate_dirs),
                "existing_candidate_dir_count": int(candidate_dirs["exists"].sum()) if not candidate_dirs.empty else 0,
                "best_known_file_count": best_known_count,
                "expected_file_count": expected_file_count,
                "candidate_ready_count": candidate_ready,
                "operator_command_count": len(command_manifest),
                "operator_pack_ready": int(planning_pass == planning_count),
                "planning_gate_pass_count": planning_pass,
                "planning_gate_count": planning_count,
                "data_gate_pass_count": data_pass,
                "data_gate_count": data_count,
                "stage133_release_allowed_now": 0,
                "real_w0_data_delivered": 0,
                "real_stage112_intake_allowed_now": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                **metrics,
            }
        ]
    )

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(candidate_dirs, CANDIDATE_DIR_AUDIT_OUT)
    _write_csv(role_audit, ROLE_AUDIT_OUT)
    _write_csv(command_manifest, COMMAND_MANIFEST_OUT)
    _write_csv(gate, GATE_OUT)
    _write_runbook(summary, command_manifest, candidate_dirs, gate)
    _write_report(summary, command_manifest, candidate_dirs, gate)
    _plot_official_path(curve, summary)
    _plot_matrix(
        candidate_dirs,
        "drop_dir",
        ["exists", "candidate_ready_for_stage133", "under_forbidden_fixture_root"],
        "Stage135 candidate drop directory matrix",
        CANDIDATE_CHART_OUT,
    )
    _plot_matrix(
        command_manifest,
        "step_id",
        ["required_before_next", "blocks_downstream_if_not_met"],
        "Stage135 operator command matrix",
        COMMAND_CHART_OUT,
    )
    _plot_matrix(gate, "gate_id", ["pass_now"], "Stage135 operator gate status", GATE_CHART_OUT)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "candidate_dirs": str(CANDIDATE_DIR_AUDIT_OUT),
                "command_manifest": str(COMMAND_MANIFEST_OUT),
                "runbook": str(RUNBOOK_OUT),
                "report": str(REPORT_OUT),
                "charts": [str(PATH_CHART_OUT), str(CANDIDATE_CHART_OUT), str(COMMAND_CHART_OUT), str(GATE_CHART_OUT)],
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
