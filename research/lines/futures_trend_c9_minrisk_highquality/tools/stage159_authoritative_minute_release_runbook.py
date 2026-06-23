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
STAGE = "Stage159"
MODEL_TAG = "stage159_authoritative_minute_release_runbook_v1"
OUTPUT_PREFIX = "qmt_roll_stage159_c9_minrisk_authoritative_minute_release_runbook"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage159_authoritative_minute_release_runbook"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

STAGE152_DIR = LINE_DIR / "outputs" / "stage152_authoritative_minute_ohlcv_manifest"
STAGE152_PREFIX = "qmt_roll_stage152_c9_minrisk_authoritative_minute_ohlcv_manifest"
STAGE152_TAG = "stage152_authoritative_minute_ohlcv_manifest_v1"
STAGE152_REQUEST_TEMPLATE_IN = STAGE152_DIR / f"{STAGE152_PREFIX}_request_manifest_template_{STAGE152_TAG}.csv"

STAGE153_DIR = LINE_DIR / "outputs" / "stage153_authoritative_minute_ohlcv_intake_validator"
STAGE153_PREFIX = "qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator"
STAGE153_TAG = "stage153_authoritative_minute_ohlcv_intake_validator_v1"
STAGE153_SUMMARY_IN = STAGE153_DIR / f"{STAGE153_PREFIX}_summary_{STAGE153_TAG}.csv"
STAGE153_GATE_IN = STAGE153_DIR / f"{STAGE153_PREFIX}_gate_status_{STAGE153_TAG}.csv"
STAGE153_FAILURE_QUEUE_IN = STAGE153_DIR / f"{STAGE153_PREFIX}_operator_failure_queue_{STAGE153_TAG}.csv"

STAGE156_DIR = LINE_DIR / "outputs" / "stage156_authoritative_minute_feature_prebuild_gate"
STAGE156_PREFIX = "qmt_roll_stage156_c9_minrisk_authoritative_minute_feature_prebuild_gate"
STAGE156_TAG = "stage156_authoritative_minute_feature_prebuild_gate_v1"
STAGE156_SUMMARY_IN = STAGE156_DIR / f"{STAGE156_PREFIX}_summary_{STAGE156_TAG}.csv"
STAGE156_GATE_IN = STAGE156_DIR / f"{STAGE156_PREFIX}_gate_status_{STAGE156_TAG}.csv"

STAGE157_DIR = LINE_DIR / "outputs" / "stage157_authoritative_minute_feature_builder_empty_run"
STAGE157_PREFIX = "qmt_roll_stage157_c9_minrisk_authoritative_minute_feature_builder_empty_run"
STAGE157_TAG = "stage157_authoritative_minute_feature_builder_empty_run_v1"
STAGE157_SUMMARY_IN = STAGE157_DIR / f"{STAGE157_PREFIX}_summary_{STAGE157_TAG}.csv"
STAGE157_GATE_IN = STAGE157_DIR / f"{STAGE157_PREFIX}_gate_status_{STAGE157_TAG}.csv"

STAGE158_DIR = LINE_DIR / "outputs" / "stage158_authoritative_minute_feature_lineage_audit"
STAGE158_PREFIX = "qmt_roll_stage158_c9_minrisk_authoritative_minute_feature_lineage_audit"
STAGE158_TAG = "stage158_authoritative_minute_feature_lineage_audit_v1"
STAGE158_SUMMARY_IN = STAGE158_DIR / f"{STAGE158_PREFIX}_summary_{STAGE158_TAG}.csv"
STAGE158_GATE_IN = STAGE158_DIR / f"{STAGE158_PREFIX}_gate_status_{STAGE158_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
RELEASE_CHECKLIST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_release_checklist_{MODEL_TAG}.csv"
COMMAND_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_operator_command_manifest_{MODEL_TAG}.csv"
FAILURE_TRIAGE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_failure_triage_{MODEL_TAG}.csv"
READINESS_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readiness_matrix_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
RUNBOOK_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_REAL_DATA_RELEASE_RUNBOOK_{MODEL_TAG}.md"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_release_status_{MODEL_TAG}.png"
CHECKLIST_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_release_checklist_matrix_{MODEL_TAG}.png"
READINESS_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readiness_matrix_{MODEL_TAG}.png"
TRIAGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_failure_triage_bar_{MODEL_TAG}.png"
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
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.6f}")
        else:
            data[column] = data[column].map(
                lambda value: "" if pd.isna(value) else str(value).replace("|", "\\|").replace("\n", "<br>")
            )
    lines = [
        "| " + " | ".join(str(column) for column in data.columns) + " |",
        "| " + " | ".join(["---"] * len(data.columns)) + " |",
    ]
    for _, row in data.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in data.columns) + " |")
    return "\n".join(lines)


def _row(path: Path) -> dict[str, Any]:
    frame = _read_csv(path)
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


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    if curve.empty:
        raise RuntimeError(f"missing curve input: {CURVE_IN}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _stage_readiness(
    stage153: dict[str, Any],
    stage156: dict[str, Any],
    stage157: dict[str, Any],
    stage158: dict[str, Any],
) -> pd.DataFrame:
    rows = [
        {
            "stage_id": "Stage153",
            "gate_family": "intake",
            "observed": _int(stage153, "request_ready_count"),
            "required": _int(stage153, "request_count"),
            "hard_pass_now": int(_int(stage153, "request_ready_count") == _int(stage153, "request_count") and _int(stage153, "request_count") > 0),
            "release_blocker": "raw/proof/normalized authoritative package not complete",
        },
        {
            "stage_id": "Stage153",
            "gate_family": "coverage",
            "observed": _int(stage153, "window_coverage_pass_count"),
            "required": _int(stage153, "required_window_count"),
            "hard_pass_now": int(_int(stage153, "window_coverage_pass_count") == _int(stage153, "required_window_count") and _int(stage153, "required_window_count") > 0),
            "release_blocker": "required windows not covered",
        },
        {
            "stage_id": "Stage156",
            "gate_family": "feature_readiness",
            "observed": _int(stage156, "feature_ready_window_count"),
            "required": _int(stage156, "stage153_required_window_count"),
            "hard_pass_now": int(_int(stage156, "feature_ready_window_count") == _int(stage156, "stage153_required_window_count") and _int(stage156, "stage153_required_window_count") > 0),
            "release_blocker": "feature windows not ready",
        },
        {
            "stage_id": "Stage156",
            "gate_family": "positioning_oi",
            "observed": _int(stage156, "positioning_feature_ready_window_count"),
            "required": _int(stage156, "stage153_required_window_count"),
            "hard_pass_now": int(_int(stage156, "positioning_feature_ready_window_count") == _int(stage156, "stage153_required_window_count") and _int(stage156, "stage153_required_window_count") > 0),
            "release_blocker": "open_interest not ready for every window",
        },
        {
            "stage_id": "Stage157",
            "gate_family": "feature_rows",
            "observed": _int(stage157, "feature_table_row_written_count"),
            "required": _int(stage157, "empty_run_window_count"),
            "hard_pass_now": int(_int(stage157, "feature_table_row_written_count") == _int(stage157, "empty_run_window_count") and _int(stage157, "empty_run_window_count") > 0),
            "release_blocker": "feature table rows not emitted",
        },
        {
            "stage_id": "Stage158",
            "gate_family": "lineage",
            "observed": _int(stage158, "lineage_pass_window_count"),
            "required": _int(stage158, "lineage_audit_window_count"),
            "hard_pass_now": int(_int(stage158, "lineage_pass_window_count") == _int(stage158, "lineage_audit_window_count") and _int(stage158, "lineage_audit_window_count") > 0),
            "release_blocker": "feature row lineage not passed",
        },
    ]
    return pd.DataFrame(rows)


def _release_checklist(readiness: pd.DataFrame) -> pd.DataFrame:
    steps = [
        (
            "01_package_completeness",
            "Confirm every Stage152 request has raw/proof/normalized files under incoming/stage152_authoritative_minute_ohlcv.",
            "request_manifest_template",
            "all files present, no template/fixture/synthetic markers",
            "BagIt complete before valid: files must exist before checksum/schema claims matter",
        ),
        (
            "02_stage153_intake",
            "Run Stage153 intake validator after real files arrive.",
            "stage153_summary, request/proof/schema/window audits",
            "request_ready_count == request_count and window_coverage_pass_count == required_window_count",
            "blocks any proof-only, hash mismatch, bad parquet, zero rows, or uncovered windows",
        ),
        (
            "03_stage156_prebuild",
            "Run Stage156 feature prebuild gate.",
            "stage156 feature contract and readiness",
            "feature_ready_window_count == required_window_count and positioning_feature_ready_window_count == required_window_count",
            "ensures OHLCV+OI is ready before feature rows can exist",
        ),
        (
            "04_stage157_builder",
            "Run Stage157 feature builder dry-run/real-run gate.",
            "stage157 schema, build plan, point-in-time selftest",
            "feature rows emitted only from bar_end_ts <= decision_ts and no future mutation sensitivity",
            "prevents future leakage and short-history feature rows",
        ),
        (
            "05_stage158_lineage",
            "Run Stage158 feature row lineage audit.",
            "stage158 PROV contract and lineage audit",
            "lineage_pass_window_count == lineage_audit_window_count",
            "every feature row must trace to proof/raw/normalized/window/schema hashes",
        ),
        (
            "06_readonly_feature_atlas",
            "Only after Stage153/156/157/158 all pass, generate a readonly feature atlas.",
            "feature table with lineage and visual atlas",
            "atlas has no thresholds, no true engine, no A/B, no promotion",
            "visual exploration only; no strategy rule or rescue sweep",
        ),
        (
            "07_candidate_gate",
            "Any later candidate must go through Stage141+ candidate promotion gates.",
            "candidate package, OOS, LOYO, monthly-start, right-tail/bottom-loss visuals",
            "promotion_allowed only if all predeclared gates pass",
            "keeps research output separate from formal/live path",
        ),
    ]
    all_prior_pass = int(readiness["hard_pass_now"].min()) if not readiness.empty else 0
    rows = []
    for idx, (step_id, action, evidence, pass_condition, rationale) in enumerate(steps, start=1):
        data_gate_required = int(idx <= 5)
        allowed_now = 0
        if idx == 1:
            blocker = "waiting_real_authoritative_package"
        elif idx <= 5:
            blocker = "upstream_hard_gate_not_passed"
        else:
            blocker = "requires_all_stage153_156_157_158_pass"
        rows.append(
            {
                "step_order": idx,
                "step_id": step_id,
                "action": action,
                "required_evidence": evidence,
                "pass_condition": pass_condition,
                "rationale": rationale,
                "data_gate_required": data_gate_required,
                "allowed_now": allowed_now,
                "would_be_allowed_after_all_hard_gates": int(all_prior_pass == 1 and idx <= 6),
                "strategy_rule_allowed": 0,
                "primary_blocker_now": blocker,
            }
        )
    return pd.DataFrame(rows)


def _command_manifest() -> pd.DataFrame:
    commands = [
        ("inspect_incoming", "find incoming/stage152_authoritative_minute_ohlcv -type f | sort | wc -l", "readonly_shell", 1),
        ("run_stage153", ".py311/bin/python research/lines/futures_trend_c9_minrisk_highquality/tools/stage153_authoritative_minute_ohlcv_intake_validator.py", "research_output_write", 1),
        ("run_stage156", ".py311/bin/python research/lines/futures_trend_c9_minrisk_highquality/tools/stage156_authoritative_minute_feature_prebuild_gate.py", "research_output_write", 1),
        ("run_stage157", ".py311/bin/python research/lines/futures_trend_c9_minrisk_highquality/tools/stage157_authoritative_minute_feature_builder_empty_run.py", "research_output_write", 1),
        ("run_stage158", ".py311/bin/python research/lines/futures_trend_c9_minrisk_highquality/tools/stage158_authoritative_minute_feature_lineage_audit.py", "research_output_write", 1),
        ("inspect_release_summary", ".py311/bin/python - <<'PY'\nfrom pathlib import Path\nimport pandas as pd\nfor p in Path('research/lines/futures_trend_c9_minrisk_highquality/outputs').glob('stage15*/qmt_roll_stage15*_summary_*.csv'):\n    print(p)\n    print(pd.read_csv(p).head(1).to_string(index=False))\nPY", "readonly_shell", 1),
    ]
    return pd.DataFrame(
        [
            {
                "command_order": idx,
                "command_id": command_id,
                "command": command,
                "command_type": command_type,
                "safe_command": safe_command,
                "contains_ctp_or_order_api": int("ctp" in command.lower() or "order_api" in command.lower()),
                "changes_official_config": 0,
                "allowed_to_execute_now": 0,
                "execution_condition": "only after real authoritative package arrives; still no CTP/order/A-B",
            }
            for idx, (command_id, command, command_type, safe_command) in enumerate(commands, start=1)
        ]
    )


def _failure_triage(
    stage153_failure_queue: pd.DataFrame,
    readiness: pd.DataFrame,
    stage153: dict[str, Any],
    stage156: dict[str, Any],
    stage157: dict[str, Any],
    stage158: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if not stage153_failure_queue.empty:
        for _, row in stage153_failure_queue.iterrows():
            rows.append(
                {
                    "triage_order": int(row.get("priority", len(rows) + 1)),
                    "source_stage": "Stage153",
                    "failure_id": str(row.get("action_id", "")),
                    "blocking_count": int(row.get("blocking_count", 0)),
                    "operator_action": str(row.get("action", "")),
                    "strategy_rule_allowed": 0,
                }
            )
    for _, row in readiness.iterrows():
        if int(row["hard_pass_now"]) == 0:
            rows.append(
                {
                    "triage_order": len(rows) + 1,
                    "source_stage": row["stage_id"],
                    "failure_id": row["gate_family"],
                    "blocking_count": int(max(int(row["required"]) - int(row["observed"]), 0)),
                    "operator_action": row["release_blocker"],
                    "strategy_rule_allowed": 0,
                }
            )
    rows.extend(
        [
            {
                "triage_order": len(rows) + 1,
                "source_stage": "Stage157",
                "failure_id": "feature_table_file_written",
                "blocking_count": int(_int(stage157, "feature_table_file_written") == 0),
                "operator_action": "feature file intentionally absent until data gates pass",
                "strategy_rule_allowed": 0,
            },
            {
                "triage_order": len(rows) + 1,
                "source_stage": "Stage158",
                "failure_id": "lineage_pass_window_count",
                "blocking_count": int(max(_int(stage158, "lineage_audit_window_count") - _int(stage158, "lineage_pass_window_count"), 0)),
                "operator_action": "rerun lineage after real feature rows exist",
                "strategy_rule_allowed": 0,
            },
        ]
    )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(["triage_order", "source_stage"]).reset_index(drop=True)


def _gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("release_checklist_written", summary["release_checklist_step_count"], summary["release_checklist_step_count"], "contract_hard"),
        ("operator_command_manifest_written", summary["operator_command_count"], summary["operator_command_count"], "contract_hard"),
        ("safe_operator_command_count", summary["safe_operator_command_count"], summary["operator_command_count"], "safety_hard"),
        ("commands_with_ctp_or_order_api", summary["commands_with_ctp_or_order_api"], 0, "safety_hard"),
        ("commands_change_official_config", summary["commands_change_official_config"], 0, "safety_hard"),
        ("all_release_readiness_pass", summary["release_readiness_pass_count"], summary["release_readiness_required_count"], "data_hard"),
        ("feature_atlas_allowed_now", summary["feature_atlas_allowed_now"], 0, "strategy_hard"),
        ("strategy_rule_created", summary["strategy_rule_created"], 0, "strategy_hard"),
        ("true_engine_run", summary["true_engine_run"], 0, "strategy_hard"),
        ("ab_triggered", summary["ab_triggered"], 0, "strategy_hard"),
        ("order_api_called", summary["order_api_called"], 0, "execution_hard"),
        ("ctp_connected", summary["ctp_connected"], 0, "execution_hard"),
        ("side_effect_count", summary["side_effect_count"], 0, "execution_hard"),
    ]
    return pd.DataFrame(
        [
            {
                "gate_id": gate_id,
                "observed": int(observed),
                "required": int(required),
                "pass_now": int(int(observed) == int(required)),
                "severity": severity,
            }
            for gate_id, observed, required, severity in rows
        ]
    )


def _write_runbook(
    summary: pd.DataFrame,
    checklist: pd.DataFrame,
    commands: pd.DataFrame,
    triage: pd.DataFrame,
    readiness: pd.DataFrame,
) -> None:
    lines = [
        "# Stage159 Real Data Release Runbook",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- Scope: authoritative 1m OHLCV+volume+open_interest package intake through readonly feature-atlas eligibility.",
        "- Hard lock: no strategy rule, no true engine, no A/B, no CTP, no order API, no official config change.",
        "",
        "## Current Status",
        "",
        _md_table(summary),
        "",
        "## Release Checklist",
        "",
        _md_table(checklist),
        "",
        "## Operator Commands",
        "",
        _md_table(commands),
        "",
        "## Readiness Matrix",
        "",
        _md_table(readiness),
        "",
        "## Failure Triage",
        "",
        _md_table(triage),
        "",
        "## Stop Conditions",
        "",
        "- Stop if any Stage153 raw/proof/normalized file is missing.",
        "- Stop if any proof JSON is schema-invalid, template-only, synthetic, fixture, smoke, or hash-mismatched.",
        "- Stop if any required right-tail, bottom-loss, maxDD, or ordinary window is uncovered.",
        "- Stop if Stage156 feature readiness or OI readiness is incomplete.",
        "- Stop if Stage157 emits feature rows without trailing-bar and no-future selftest passing.",
        "- Stop if Stage158 cannot trace every feature row to proof/raw/normalized/window/schema hashes.",
    ]
    RUNBOOK_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_report(
    summary: pd.DataFrame,
    checklist: pd.DataFrame,
    commands: pd.DataFrame,
    triage: pd.DataFrame,
    readiness: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    lines = [
        f"# {STAGE} 权威分钟真实数据 release runbook",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- 本阶段只固化真实数据到货后的 operator checklist、命令顺序和失败分流；不写 feature table、不创建交易规则、不跑 true engine、不触发 A/B。",
        "",
        "## 外部调研与判断",
        "",
        "- RFC 8493 BagIt 区分 complete 和 valid；Stage159 因此先要求 raw/proof/normalized 三件套完整，再谈 checksum/schema/window 覆盖。",
        "- JSON Schema 用于声明结构和类型约束，但 schema-valid proof 不是充分条件；后续仍要 raw hash、Parquet、window coverage 和 lineage。",
        "- W3C PROV 说明 provenance 用于评估数据质量、可靠性和可信度；Stage159 把 Stage158 lineage 放在 feature atlas 之前。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Release Checklist",
        "",
        _md_table(checklist),
        "",
        "## Readiness Matrix",
        "",
        _md_table(readiness),
        "",
        "## Failure Triage",
        "",
        _md_table(triage),
        "",
        "## Operator Command Manifest",
        "",
        _md_table(commands),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{CHECKLIST_CHART_OUT.name}`",
        f"- `{READINESS_CHART_OUT.name}`",
        f"- `{TRIAGE_CHART_OUT.name}`",
        f"- `{GATE_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _plot_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    row = summary.iloc[0]
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage159 release runbook status on official path", fontsize=14, fontweight="bold")
    x = curve["date"].to_numpy()
    axes[0].plot(x, curve["account_equity"].to_numpy() / 1_000_000, color="#14532D", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(x, curve["drawdown_pct"].to_numpy(), 0, color="#B45309", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(x, curve["broker10_margin_to_equity_pct"].to_numpy(), color="#3657D6", linewidth=1.0)
    axes[2].axhline(100, color="#111827", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    labels = ["requests", "ready", "windows", "covered", "release_pass", "atlas_allowed"]
    values = [
        row["stage153_request_count"],
        row["stage153_request_ready_count"],
        row["stage153_required_window_count"],
        row["stage153_window_coverage_pass_count"],
        row["release_readiness_pass_count"],
        row["feature_atlas_allowed_now"],
    ]
    colors = ["#3657D6", "#B91C1C", "#0F766E", "#B91C1C", "#B91C1C", "#111827"]
    axes[3].bar(labels, values, color=colors)
    axes[3].set_title("Runbook is ready; release remains blocked by missing authoritative package")
    axes[3].set_ylabel("count / flag")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_checklist(checklist: pd.DataFrame) -> None:
    matrix = checklist.set_index("step_id")[["data_gate_required", "allowed_now", "would_be_allowed_after_all_hard_gates", "strategy_rule_allowed"]]
    fig, ax = plt.subplots(figsize=(12, max(5.4, len(matrix) * 0.55)))
    data = matrix.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage159 release checklist state")
    ax.set_xticks(np.arange(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns, rotation=25, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=8)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(CHECKLIST_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_readiness(readiness: pd.DataFrame) -> None:
    matrix = readiness.set_index(["stage_id", "gate_family"])[["observed", "required", "hard_pass_now"]]
    fig, ax = plt.subplots(figsize=(11, max(5.2, len(matrix) * 0.55)))
    data = matrix.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="YlGnBu")
    ax.set_title("Stage159 release readiness matrix")
    ax.set_xticks(np.arange(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns, rotation=25, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels([f"{a}/{b}" for a, b in matrix.index], fontsize=8)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(READINESS_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_triage(triage: pd.DataFrame) -> None:
    data = triage.groupby("failure_id", dropna=False)["blocking_count"].sum().sort_values(ascending=True).tail(18)
    fig, ax = plt.subplots(figsize=(12, max(5.5, len(data) * 0.35)))
    ax.barh(data.index, data.values, color="#B91C1C")
    ax.set_title("Stage159 failure triage blocking counts")
    ax.set_xlabel("blocking count")
    ax.grid(axis="x", alpha=0.25)
    for idx, value in enumerate(data.values):
        ax.text(value + 0.5, idx, int(value), va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(TRIAGE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    matrix = gate.set_index("gate_id")[["pass_now"]]
    fig, ax = plt.subplots(figsize=(8.5, max(5.2, len(matrix) * 0.45)))
    data = matrix.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage159 gate status")
    ax.set_xticks([0])
    ax.set_xticklabels(["pass_now"])
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=8)
    for row in range(data.shape[0]):
        ax.text(0, row, int(data[row, 0]), ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=170)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    curve = _load_curve()
    requests = _read_csv(STAGE152_REQUEST_TEMPLATE_IN)
    stage153 = _row(STAGE153_SUMMARY_IN)
    stage156 = _row(STAGE156_SUMMARY_IN)
    stage157 = _row(STAGE157_SUMMARY_IN)
    stage158 = _row(STAGE158_SUMMARY_IN)
    stage153_gate = _read_csv(STAGE153_GATE_IN)
    stage156_gate = _read_csv(STAGE156_GATE_IN)
    stage157_gate = _read_csv(STAGE157_GATE_IN)
    stage158_gate = _read_csv(STAGE158_GATE_IN)
    stage153_failure_queue = _read_csv(STAGE153_FAILURE_QUEUE_IN)
    if (
        requests.empty
        or not stage153
        or not stage156
        or not stage157
        or not stage158
        or stage153_gate.empty
        or stage156_gate.empty
        or stage157_gate.empty
        or stage158_gate.empty
    ):
        raise RuntimeError("missing Stage152/153/156/157/158 inputs for Stage159")

    readiness = _stage_readiness(stage153, stage156, stage157, stage158)
    checklist = _release_checklist(readiness)
    commands = _command_manifest()
    triage = _failure_triage(stage153_failure_queue, readiness, stage153, stage156, stage157, stage158)

    release_pass_count = int(readiness["hard_pass_now"].sum())
    release_required_count = int(len(readiness))
    feature_atlas_allowed_now = int(release_pass_count == release_required_count and release_required_count > 0)
    decision = "stage159_authoritative_minute_release_runbook_ready_blocked_wait_real_data_no_rule"
    summary_dict: dict[str, Any] = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": decision,
        "next_best_action": "wait_real_authoritative_minute_package_then_run_stage153_156_157_158_before_readonly_feature_atlas",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "true_engine_run_count": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "side_effect_count": 0,
        "stage152_request_template_count": int(len(requests)),
        "stage153_request_count": _int(stage153, "request_count"),
        "stage153_request_ready_count": _int(stage153, "request_ready_count"),
        "stage153_required_window_count": _int(stage153, "required_window_count"),
        "stage153_window_coverage_pass_count": _int(stage153, "window_coverage_pass_count"),
        "stage156_feature_ready_window_count": _int(stage156, "feature_ready_window_count"),
        "stage157_feature_table_row_written_count": _int(stage157, "feature_table_row_written_count"),
        "stage158_lineage_pass_window_count": _int(stage158, "lineage_pass_window_count"),
        "release_checklist_step_count": int(len(checklist)),
        "operator_command_count": int(len(commands)),
        "safe_operator_command_count": int(commands["safe_command"].sum()),
        "commands_with_ctp_or_order_api": int(commands["contains_ctp_or_order_api"].sum()),
        "commands_change_official_config": int(commands["changes_official_config"].sum()),
        "failure_triage_count": int(len(triage)),
        "release_readiness_pass_count": release_pass_count,
        "release_readiness_required_count": release_required_count,
        "feature_atlas_allowed_now": feature_atlas_allowed_now,
        "current_package_promotion_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "objective_completion_proven": 0,
        "visual_output_count": 5,
        "end_equity": float(stage153.get("end_equity", np.nan)),
        "total_return_pct": float(stage153.get("total_return_pct", np.nan)),
        "max_drawdown_pct": float(stage153.get("max_drawdown_pct", np.nan)),
        "sharpe": float(stage153.get("sharpe", np.nan)),
        "total_slippage": float(stage153.get("total_slippage", np.nan)),
        "total_trade_count": float(stage153.get("total_trade_count", np.nan)),
        "closed_lot_win_rate_pct": float(stage153.get("closed_lot_win_rate_pct", np.nan)),
        "max_broker10_margin_to_equity_pct": float(stage153.get("max_broker10_margin_to_equity_pct", np.nan)),
    }
    summary = pd.DataFrame([summary_dict])
    gate = _gate_status(summary_dict)

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(checklist, RELEASE_CHECKLIST_OUT)
    _write_csv(commands, COMMAND_MANIFEST_OUT)
    _write_csv(triage, FAILURE_TRIAGE_OUT)
    _write_csv(readiness, READINESS_MATRIX_OUT)
    _write_csv(gate, GATE_OUT)
    _write_runbook(summary, checklist, commands, triage, readiness)
    _write_report(summary, checklist, commands, triage, readiness, gate)
    _plot_path(curve, summary)
    _plot_checklist(checklist)
    _plot_readiness(readiness)
    _plot_triage(triage)
    _plot_gate(gate)

    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "inputs": {
                "curve": str(CURVE_IN),
                "stage152_request_template": str(STAGE152_REQUEST_TEMPLATE_IN),
                "stage153_summary": str(STAGE153_SUMMARY_IN),
                "stage153_gate": str(STAGE153_GATE_IN),
                "stage153_failure_queue": str(STAGE153_FAILURE_QUEUE_IN),
                "stage156_summary": str(STAGE156_SUMMARY_IN),
                "stage156_gate": str(STAGE156_GATE_IN),
                "stage157_summary": str(STAGE157_SUMMARY_IN),
                "stage157_gate": str(STAGE157_GATE_IN),
                "stage158_summary": str(STAGE158_SUMMARY_IN),
                "stage158_gate": str(STAGE158_GATE_IN),
            },
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "release_checklist": str(RELEASE_CHECKLIST_OUT),
                "operator_command_manifest": str(COMMAND_MANIFEST_OUT),
                "failure_triage": str(FAILURE_TRIAGE_OUT),
                "readiness_matrix": str(READINESS_MATRIX_OUT),
                "gate_status": str(GATE_OUT),
                "runbook": str(RUNBOOK_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(CHECKLIST_CHART_OUT),
                    str(READINESS_CHART_OUT),
                    str(TRIAGE_CHART_OUT),
                    str(GATE_CHART_OUT),
                ],
            },
            "external_research_sources": [
                "https://datatracker.ietf.org/doc/rfc8493/",
                "https://json-schema.org/docs",
                "https://www.w3.org/TR/prov-dm/",
            ],
            "locks": {
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "feature_atlas_allowed_now": feature_atlas_allowed_now,
                "current_package_promotion_allowed": 0,
                "strategy_feature_usable": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
