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
STAGE = "Stage147"
MODEL_TAG = "stage147_candidate_gate_status_panel_v1"
OUTPUT_PREFIX = "qmt_roll_stage147_c9_minrisk_candidate_gate_status_panel"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage147_candidate_gate_status_panel"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

STAGE142_DIR = LINE_DIR / "outputs" / "stage142_candidate_package_contract_validator"
STAGE142_PREFIX = "qmt_roll_stage142_c9_minrisk_candidate_package_contract_validator"
STAGE142_TAG = "stage142_candidate_package_contract_validator_v1"
STAGE142_SUMMARY_IN = STAGE142_DIR / f"{STAGE142_PREFIX}_summary_{STAGE142_TAG}.csv"
STAGE142_GATE_IN = STAGE142_DIR / f"{STAGE142_PREFIX}_gate_status_{STAGE142_TAG}.csv"
STAGE142_VALIDATION_IN = STAGE142_DIR / f"{STAGE142_PREFIX}_validation_audit_{STAGE142_TAG}.csv"

STAGE143_DIR = LINE_DIR / "outputs" / "stage143_candidate_package_operator_failure_explainer"
STAGE143_PREFIX = "qmt_roll_stage143_c9_minrisk_candidate_package_operator_failure_explainer"
STAGE143_TAG = "stage143_candidate_package_operator_failure_explainer_v1"
STAGE143_SUMMARY_IN = STAGE143_DIR / f"{STAGE143_PREFIX}_summary_{STAGE143_TAG}.csv"
STAGE143_GATE_IN = STAGE143_DIR / f"{STAGE143_PREFIX}_gate_status_{STAGE143_TAG}.csv"
STAGE143_TRIAGE_IN = STAGE143_DIR / f"{STAGE143_PREFIX}_sample_triage_cases_{STAGE143_TAG}.csv"

STAGE145_DIR = LINE_DIR / "outputs" / "stage145_candidate_package_preflight_linter"
STAGE145_PREFIX = "qmt_roll_stage145_c9_minrisk_candidate_package_preflight_linter"
STAGE145_TAG = "stage145_candidate_package_preflight_linter_v1"
STAGE145_SUMMARY_IN = STAGE145_DIR / f"{STAGE145_PREFIX}_summary_{STAGE145_TAG}.csv"
STAGE145_GATE_IN = STAGE145_DIR / f"{STAGE145_PREFIX}_gate_status_{STAGE145_TAG}.csv"
STAGE145_CHECKLIST_IN = STAGE145_DIR / f"{STAGE145_PREFIX}_preflight_checklist_{STAGE145_TAG}.csv"
STAGE145_ISSUE_IN = STAGE145_DIR / f"{STAGE145_PREFIX}_issue_catalog_{STAGE145_TAG}.csv"

STAGE146_DIR = LINE_DIR / "outputs" / "stage146_candidate_gate_chain_smoke"
STAGE146_PREFIX = "qmt_roll_stage146_c9_minrisk_candidate_gate_chain_smoke"
STAGE146_TAG = "stage146_candidate_gate_chain_smoke_v1"
STAGE146_SUMMARY_IN = STAGE146_DIR / f"{STAGE146_PREFIX}_summary_{STAGE146_TAG}.csv"
STAGE146_GATE_IN = STAGE146_DIR / f"{STAGE146_PREFIX}_gate_status_{STAGE146_TAG}.csv"
STAGE146_STEP_IN = STAGE146_DIR / f"{STAGE146_PREFIX}_step_summary_{STAGE146_TAG}.csv"
STAGE146_COMMAND_IN = STAGE146_DIR / f"{STAGE146_PREFIX}_command_audit_{STAGE146_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
UPSTREAM_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_upstream_status_{MODEL_TAG}.csv"
CHECKLIST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readiness_checklist_{MODEL_TAG}.csv"
STALE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_artifact_freshness_audit_{MODEL_TAG}.csv"
ACTION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_operator_action_panel_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
PANEL_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_operator_status_panel_{MODEL_TAG}.md"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_status_{MODEL_TAG}.png"
UPSTREAM_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_upstream_readiness_matrix_{MODEL_TAG}.png"
CHECKLIST_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readiness_checklist_matrix_{MODEL_TAG}.png"
FRESHNESS_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_artifact_freshness_matrix_{MODEL_TAG}.png"
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


def _row(frame: pd.DataFrame) -> dict[str, Any]:
    return frame.iloc[0].to_dict() if not frame.empty else {}


def _num(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if np.isnan(number) or np.isinf(number):
        return default
    return number


def _int(row: dict[str, Any], key: str, default: int = 0) -> int:
    return int(round(_num(row, key, float(default))))


def _file_age_minutes(path: Path, now: datetime) -> float:
    if not path.exists():
        return np.nan
    return (now - datetime.fromtimestamp(path.stat().st_mtime)).total_seconds() / 60.0


def _gate_rate(path: Path) -> tuple[int, int]:
    gate = _read_csv(path)
    if gate.empty or "pass_now" not in gate.columns:
        return 0, 0
    passed = int(pd.to_numeric(gate["pass_now"], errors="coerce").fillna(0).sum())
    return passed, len(gate)


def _upstream_status(now: datetime, rows: dict[str, dict[str, Any]]) -> pd.DataFrame:
    specs = [
        {
            "stage_id": "Stage142",
            "role": "candidate package contract validator",
            "summary": STAGE142_SUMMARY_IN,
            "gate": STAGE142_GATE_IN,
            "ready_flag": _int(rows["stage142"], "validator_ready"),
            "expected_block_flag": int(_int(rows["stage142"], "current_package_promotion_allowed") == 0),
        },
        {
            "stage_id": "Stage143",
            "role": "operator runbook and failure explainer",
            "summary": STAGE143_SUMMARY_IN,
            "gate": STAGE143_GATE_IN,
            "ready_flag": _int(rows["stage143"], "operator_runbook_ready"),
            "expected_block_flag": int(_int(rows["stage143"], "current_package_promotion_allowed") == 0),
        },
        {
            "stage_id": "Stage145",
            "role": "candidate package preflight linter",
            "summary": STAGE145_SUMMARY_IN,
            "gate": STAGE145_GATE_IN,
            "ready_flag": _int(rows["stage145"], "linter_ready"),
            "expected_block_flag": int(
                _int(rows["stage145"], "default_template_blocked") == 1
                and _int(rows["stage145"], "preflight_pass", 1) == 0
            ),
        },
        {
            "stage_id": "Stage146",
            "role": "Stage145 -> Stage142 -> Stage143 chain smoke",
            "summary": STAGE146_SUMMARY_IN,
            "gate": STAGE146_GATE_IN,
            "ready_flag": _int(rows["stage146"], "chain_smoke_ready"),
            "expected_block_flag": int(_int(rows["stage146"], "any_promotion_allowed") == 0),
        },
    ]
    out_rows = []
    for spec in specs:
        gate_pass, gate_count = _gate_rate(spec["gate"])
        summary_exists = int(spec["summary"].exists())
        gate_exists = int(spec["gate"].exists())
        out_rows.append(
            {
                "stage_id": spec["stage_id"],
                "role": spec["role"],
                "summary_exists": summary_exists,
                "gate_exists": gate_exists,
                "summary_age_min": _file_age_minutes(spec["summary"], now),
                "gate_age_min": _file_age_minutes(spec["gate"], now),
                "ready_flag": spec["ready_flag"],
                "expected_no_promotion_or_template_block": spec["expected_block_flag"],
                "gate_pass_count": gate_pass,
                "gate_count": gate_count,
                "gate_all_pass": int(gate_count > 0 and gate_pass == gate_count),
                "official_config_changed": _int(rows[spec["stage_id"].lower()], "official_config_changed"),
                "true_engine_run": _int(rows[spec["stage_id"].lower()], "true_engine_run"),
                "ab_triggered": _int(rows[spec["stage_id"].lower()], "ab_triggered"),
                "order_api_called": _int(rows[spec["stage_id"].lower()], "order_api_called"),
                "ctp_connected": _int(rows[spec["stage_id"].lower()], "ctp_connected"),
            }
        )
    return pd.DataFrame(out_rows)


def _freshness_audit(now: datetime) -> pd.DataFrame:
    paths = [
        ("stage142_summary", STAGE142_SUMMARY_IN, "summary"),
        ("stage142_gate", STAGE142_GATE_IN, "gate"),
        ("stage142_validation", STAGE142_VALIDATION_IN, "detail"),
        ("stage143_summary", STAGE143_SUMMARY_IN, "summary"),
        ("stage143_gate", STAGE143_GATE_IN, "gate"),
        ("stage143_triage", STAGE143_TRIAGE_IN, "detail"),
        ("stage145_summary", STAGE145_SUMMARY_IN, "summary"),
        ("stage145_gate", STAGE145_GATE_IN, "gate"),
        ("stage145_checklist", STAGE145_CHECKLIST_IN, "detail"),
        ("stage145_issue_catalog", STAGE145_ISSUE_IN, "detail"),
        ("stage146_summary", STAGE146_SUMMARY_IN, "summary"),
        ("stage146_gate", STAGE146_GATE_IN, "gate"),
        ("stage146_step_summary", STAGE146_STEP_IN, "detail"),
        ("stage146_command_audit", STAGE146_COMMAND_IN, "detail"),
    ]
    rows = []
    for artifact_id, path, kind in paths:
        exists = int(path.exists())
        age_min = _file_age_minutes(path, now)
        rows.append(
            {
                "artifact_id": artifact_id,
                "artifact_kind": kind,
                "exists": exists,
                "age_min": age_min,
                "fresh_24h": int(exists == 1 and age_min <= 24 * 60),
                "size_bytes": int(path.stat().st_size) if path.exists() else 0,
                "path": str(path),
            }
        )
    return pd.DataFrame(rows)


def _readiness_checklist(rows: dict[str, dict[str, Any]], upstream: pd.DataFrame, freshness: pd.DataFrame) -> pd.DataFrame:
    true_engine_total = sum(
        _int(rows[key], "true_engine_run") + _int(rows[key], "true_engine_run_count")
        for key in ["stage142", "stage143", "stage145", "stage146"]
    )
    official_config_total = sum(_int(rows[key], "official_config_changed") for key in rows)
    ab_total = sum(_int(rows[key], "ab_triggered") for key in rows)
    order_total = sum(_int(rows[key], "order_api_called") for key in rows)
    ctp_total = sum(_int(rows[key], "ctp_connected") for key in rows)
    supplied_total = sum(_int(rows[key], "real_candidate_package_supplied") for key in rows)
    promotion_total = sum(
        _int(rows[key], "current_package_promotion_allowed") + _int(rows[key], "any_promotion_allowed")
        for key in rows
    )
    checks = [
        ("stage146_chain_smoke_ready", _int(rows["stage146"], "chain_smoke_ready"), 1, "latest full chain smoke is ready"),
        ("stage145_linter_ready", _int(rows["stage145"], "linter_ready"), 1, "preflight linter is available"),
        ("stage145_template_blocked", _int(rows["stage145"], "default_template_blocked"), 1, "template package is blocked by design"),
        ("stage145_current_preflight_not_passed", int(_int(rows["stage145"], "preflight_pass", 1) == 0), 1, "no real package has passed preflight"),
        ("stage142_validator_ready", _int(rows["stage142"], "validator_ready"), 1, "contract validator is available"),
        (
            "stage142_validation_expectations_pass",
            int(_int(rows["stage142"], "validation_expectation_pass_count") >= 4),
            1,
            "validator selftest expectations pass",
        ),
        ("stage143_explainer_ready", _int(rows["stage143"], "operator_runbook_ready"), 1, "operator failure explainer is available"),
        ("all_upstream_gates_pass", int(not upstream.empty and int(upstream["gate_all_pass"].sum()) == len(upstream)), 1, "all upstream hard gates pass"),
        ("freshness_artifacts_present", int(not freshness.empty and int(freshness["exists"].sum()) == len(freshness)), 1, "all expected status artifacts exist"),
        ("real_candidate_package_supplied", supplied_total, 0, "no real package has been supplied"),
        ("current_package_promotion_allowed", promotion_total, 0, "no package is currently promotable"),
        ("true_engine_run", true_engine_total, 0, "no true engine was run"),
        ("official_config_changed", official_config_total, 0, "official config unchanged"),
        ("ab_triggered", ab_total, 0, "no A/B experiment triggered"),
        ("order_api_called", order_total, 0, "no order API call"),
        ("ctp_connected", ctp_total, 0, "no CTP connection"),
    ]
    out_rows = []
    for check_id, observed, required, note in checks:
        pass_now = int(observed == required)
        out_rows.append(
            {
                "check_id": check_id,
                "observed": observed,
                "required": required,
                "pass_now": pass_now,
                "operator_note": note,
            }
        )
    return pd.DataFrame(out_rows)


def _action_panel(rows: dict[str, dict[str, Any]]) -> pd.DataFrame:
    real_package = sum(_int(rows[key], "real_candidate_package_supplied") for key in rows)
    preflight_pass = _int(rows["stage145"], "preflight_pass", 0)
    chain_ready = _int(rows["stage146"], "chain_smoke_ready", 0)
    return pd.DataFrame(
        [
            {
                "priority": 1,
                "state": "no_real_candidate_package",
                "active": int(real_package == 0),
                "allowed_action": "wait_real_candidate_or_keep_readonly_status_panel",
                "blocked_action": "do_not_run_true_engine_or_ab_without_real_preflight_pass",
                "operator_reason": "Stage145 has only blocked the Stage144 template; no real package has passed preflight.",
            },
            {
                "priority": 2,
                "state": "real_package_supplied_but_not_preflighted",
                "active": int(real_package > 0 and preflight_pass == 0),
                "allowed_action": "run_stage145_preflight_first",
                "blocked_action": "do_not_send_package_to_stage142_or_stage143_before_preflight_pass",
                "operator_reason": "Stage146 contract requires Stage145 preflight_pass=1 before validator/explainer handoff.",
            },
            {
                "priority": 3,
                "state": "preflight_passed_package_ready_for_contract",
                "active": int(real_package > 0 and preflight_pass == 1 and chain_ready == 1),
                "allowed_action": "run_stage142_then_stage143_on_same_package",
                "blocked_action": "do_not_promote_until_all_stage141_contract_evidence_passes",
                "operator_reason": "Even a preflight-passed package still needs full contract evidence and anti-overfit gates.",
            },
        ]
    )


def _gate_status(summary: pd.DataFrame, upstream: pd.DataFrame, checklist: pd.DataFrame, freshness: pd.DataFrame) -> pd.DataFrame:
    row = _row(summary)
    rows = [
        {
            "gate_id": "status_panel_ready",
            "observed": _int(row, "status_panel_ready"),
            "required": 1,
            "pass_now": int(_int(row, "status_panel_ready") == 1),
            "severity": "panel_hard",
        },
        {
            "gate_id": "upstream_summaries_present",
            "observed": int(upstream["summary_exists"].sum()) if not upstream.empty else 0,
            "required": len(upstream),
            "pass_now": int(not upstream.empty and int(upstream["summary_exists"].sum()) == len(upstream)),
            "severity": "dependency_hard",
        },
        {
            "gate_id": "upstream_gates_all_pass",
            "observed": int(upstream["gate_all_pass"].sum()) if not upstream.empty else 0,
            "required": len(upstream),
            "pass_now": int(not upstream.empty and int(upstream["gate_all_pass"].sum()) == len(upstream)),
            "severity": "dependency_hard",
        },
        {
            "gate_id": "readiness_checklist_all_pass",
            "observed": int(checklist["pass_now"].sum()) if not checklist.empty else 0,
            "required": len(checklist),
            "pass_now": int(not checklist.empty and int(checklist["pass_now"].sum()) == len(checklist)),
            "severity": "panel_hard",
        },
        {
            "gate_id": "required_artifacts_present",
            "observed": int(freshness["exists"].sum()) if not freshness.empty else 0,
            "required": len(freshness),
            "pass_now": int(not freshness.empty and int(freshness["exists"].sum()) == len(freshness)),
            "severity": "artifact_hard",
        },
        {
            "gate_id": "no_current_promotion_allowed",
            "observed": _int(row, "current_package_promotion_allowed"),
            "required": 0,
            "pass_now": int(_int(row, "current_package_promotion_allowed") == 0),
            "severity": "anti_selection_hard",
        },
        {
            "gate_id": "no_true_engine_or_execution_side_effect",
            "observed": _int(row, "side_effect_count"),
            "required": 0,
            "pass_now": int(_int(row, "side_effect_count") == 0),
            "severity": "execution_safety_hard",
        },
    ]
    return pd.DataFrame(rows)


def _write_panel(
    summary: pd.DataFrame,
    upstream: pd.DataFrame,
    checklist: pd.DataFrame,
    freshness: pd.DataFrame,
    actions: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    lines = [
        f"# {STAGE} candidate gate status panel",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{row['decision']}`",
        f"- recommended_action: `{row['recommended_action']}`",
        f"- current_package_promotion_allowed: `{row['current_package_promotion_allowed']}`",
        f"- side_effect_count: `{row['side_effect_count']}`",
        "",
        "## Operator Summary",
        "",
        "- This panel is read-only. It does not run Stage145, Stage142, Stage143, true engine, A/B, order API, or CTP.",
        "- With no real candidate package supplied, the correct state is blocked/no-promotion while the gate chain remains ready.",
        "- If a real package appears, run Stage145 preflight first and only pass the same package to Stage142/143 when preflight_pass=1.",
        "",
        "## External Research Judgment",
        "",
        "- Great Expectations Data Docs support human-readable validation status from saved validation results.",
        "- Frictionless validation emphasizes comprehensive error details in validation output.",
        "- pre-commit/pre-commit.ci motivate local/CI checks that surface status without changing production state.",
        "",
        "## Summary",
        "",
        _md_table(summary.drop(columns=["candidate_package_dir"], errors="ignore")),
        "",
        "## Upstream Status",
        "",
        _md_table(upstream),
        "",
        "## Readiness Checklist",
        "",
        _md_table(checklist),
        "",
        "## Operator Actions",
        "",
        _md_table(actions),
        "",
        "## Artifact Freshness",
        "",
        _md_table(freshness[["artifact_id", "artifact_kind", "exists", "age_min", "fresh_24h", "size_bytes"]], max_rows=20),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{UPSTREAM_CHART_OUT.name}`",
        f"- `{CHECKLIST_CHART_OUT.name}`",
        f"- `{FRESHNESS_CHART_OUT.name}`",
        f"- `{GATE_CHART_OUT.name}`",
    ]
    text = "\n".join(lines) + "\n"
    PANEL_OUT.write_text(text, encoding="utf-8")
    REPORT_OUT.write_text(text, encoding="utf-8")


def _plot_official_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    row = summary.iloc[0]
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage147 read-only candidate gate status panel", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#14532D", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#B45309", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3657D6", linewidth=1.0)
    axes[2].axhline(100, color="#333333", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    labels = [
        "panel_ready",
        "chain_ready",
        "template_blocked",
        "real_pkg",
        "promotion",
        "side_effect",
    ]
    values = [
        row["status_panel_ready"],
        row["latest_chain_smoke_ready"],
        row["stage145_template_blocked"],
        row["real_candidate_package_supplied"],
        row["current_package_promotion_allowed"],
        row["side_effect_count"],
    ]
    axes[3].bar(labels, values, color=["#0F766E", "#0F766E", "#0F766E", "#B45309", "#B91C1C", "#B91C1C"])
    axes[3].set_title("Current gate state")
    axes[3].set_ylabel("flag / count")
    axes[3].tick_params(axis="x", labelrotation=25)
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


def _plot_freshness(freshness: pd.DataFrame) -> None:
    plot_data = freshness.copy()
    plot_data["exists_flag"] = pd.to_numeric(plot_data["exists"], errors="coerce").fillna(0)
    plot_data["fresh_24h_flag"] = pd.to_numeric(plot_data["fresh_24h"], errors="coerce").fillna(0)
    plot_data["non_empty"] = (pd.to_numeric(plot_data["size_bytes"], errors="coerce").fillna(0) > 4).astype(int)
    _plot_matrix(
        plot_data,
        "artifact_id",
        ["exists_flag", "fresh_24h_flag", "non_empty"],
        "Stage147 artifact freshness",
        FRESHNESS_CHART_OUT,
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    curve = _load_curve()
    stage142 = _row(_read_csv(STAGE142_SUMMARY_IN))
    stage143 = _row(_read_csv(STAGE143_SUMMARY_IN))
    stage145 = _row(_read_csv(STAGE145_SUMMARY_IN))
    stage146 = _row(_read_csv(STAGE146_SUMMARY_IN))
    rows = {"stage142": stage142, "stage143": stage143, "stage145": stage145, "stage146": stage146}

    upstream = _upstream_status(now, rows)
    freshness = _freshness_audit(now)
    checklist = _readiness_checklist(rows, upstream, freshness)
    actions = _action_panel(rows)

    side_effect_count = sum(
        _int(rows[key], "official_config_changed")
        + _int(rows[key], "true_engine_run")
        + _int(rows[key], "true_engine_run_count")
        + _int(rows[key], "ab_triggered")
        + _int(rows[key], "order_api_called")
        + _int(rows[key], "ctp_connected")
        for key in rows
    )
    promotion_allowed = sum(
        _int(rows[key], "current_package_promotion_allowed") + _int(rows[key], "any_promotion_allowed")
        for key in rows
    )
    real_package_supplied = sum(_int(rows[key], "real_candidate_package_supplied") for key in rows)
    readiness_all_pass = int(not checklist.empty and int(checklist["pass_now"].sum()) == len(checklist))
    status_panel_ready = int(readiness_all_pass and side_effect_count == 0)
    decision = (
        "stage147_gate_status_panel_ready_no_candidate_no_strategy"
        if status_panel_ready == 1 and real_package_supplied == 0 and promotion_allowed == 0
        else "stage147_gate_status_panel_attention_required_no_strategy"
    )
    recommended_action = (
        "wait_real_candidate_or_keep_readonly_status_panel"
        if real_package_supplied == 0
        else "run_stage145_preflight_first"
    )
    metrics_source = stage146 or stage142
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": decision,
                "recommended_action": recommended_action,
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "true_engine_run_count": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "side_effect_count": side_effect_count,
                "status_panel_ready": status_panel_ready,
                "latest_chain_smoke_ready": _int(stage146, "chain_smoke_ready"),
                "stage145_linter_ready": _int(stage145, "linter_ready"),
                "stage145_template_blocked": _int(stage145, "default_template_blocked"),
                "stage145_preflight_pass": _int(stage145, "preflight_pass", -1),
                "stage142_validator_ready": _int(stage142, "validator_ready"),
                "stage142_validation_expectation_pass_count": _int(stage142, "validation_expectation_pass_count"),
                "stage143_explainer_ready": _int(stage143, "operator_runbook_ready"),
                "upstream_ready_count": int(upstream["ready_flag"].sum()),
                "upstream_count": len(upstream),
                "upstream_gate_all_pass_count": int(upstream["gate_all_pass"].sum()),
                "readiness_check_pass_count": int(checklist["pass_now"].sum()),
                "readiness_check_count": len(checklist),
                "artifact_present_count": int(freshness["exists"].sum()),
                "artifact_count": len(freshness),
                "fresh_24h_count": int(freshness["fresh_24h"].sum()),
                "real_candidate_package_supplied": real_package_supplied,
                "current_package_promotion_allowed": promotion_allowed,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "real_stage112_intake_allowed_now": 0,
                "candidate_package_dir": str(stage146.get("candidate_package_dir", "")),
                "end_equity": float(metrics_source.get("end_equity", np.nan)),
                "total_return_pct": float(metrics_source.get("total_return_pct", np.nan)),
                "max_drawdown_pct": float(metrics_source.get("max_drawdown_pct", np.nan)),
                "sharpe": float(metrics_source.get("sharpe", np.nan)),
                "total_slippage": float(metrics_source.get("total_slippage", np.nan)),
                "total_trade_count": float(metrics_source.get("total_trade_count", np.nan)),
                "closed_lot_win_rate_pct": float(metrics_source.get("closed_lot_win_rate_pct", np.nan)),
                "max_broker10_margin_to_equity_pct": float(
                    metrics_source.get("max_broker10_margin_to_equity_pct", np.nan)
                ),
            }
        ]
    )
    gate = _gate_status(summary, upstream, checklist, freshness)

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(upstream, UPSTREAM_OUT)
    _write_csv(checklist, CHECKLIST_OUT)
    _write_csv(freshness, STALE_OUT)
    _write_csv(actions, ACTION_OUT)
    _write_csv(gate, GATE_OUT)
    _write_panel(summary, upstream, checklist, freshness, actions, gate)
    _plot_official_path(curve, summary)
    _plot_matrix(
        upstream,
        "stage_id",
        ["summary_exists", "gate_exists", "ready_flag", "expected_no_promotion_or_template_block", "gate_all_pass"],
        "Stage147 upstream readiness",
        UPSTREAM_CHART_OUT,
    )
    _plot_matrix(checklist, "check_id", ["pass_now"], "Stage147 readiness checklist", CHECKLIST_CHART_OUT)
    _plot_freshness(freshness)
    _plot_matrix(gate, "gate_id", ["pass_now"], "Stage147 gate status", GATE_CHART_OUT)

    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "recommended_action": recommended_action,
            "inputs": {
                "stage142_summary": str(STAGE142_SUMMARY_IN),
                "stage143_summary": str(STAGE143_SUMMARY_IN),
                "stage145_summary": str(STAGE145_SUMMARY_IN),
                "stage146_summary": str(STAGE146_SUMMARY_IN),
            },
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "upstream_status": str(UPSTREAM_OUT),
                "readiness_checklist": str(CHECKLIST_OUT),
                "artifact_freshness_audit": str(STALE_OUT),
                "operator_action_panel": str(ACTION_OUT),
                "gate_status": str(GATE_OUT),
                "operator_status_panel": str(PANEL_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(UPSTREAM_CHART_OUT),
                    str(CHECKLIST_CHART_OUT),
                    str(FRESHNESS_CHART_OUT),
                    str(GATE_CHART_OUT),
                ],
            },
            "locks": {
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "true_engine_run_count": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "current_package_promotion_allowed": promotion_allowed,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
