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
STAGE = "Stage121"
MODEL_TAG = "stage121_wave0_schema_cli_entry_selftest_v1"
OUTPUT_PREFIX = "qmt_roll_stage121_c9_minrisk_wave0_schema_cli_entry_selftest"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage121_wave0_schema_cli_entry_selftest"

STAGE120_TOOL = LINE_DIR / "tools" / "stage120_wave0_schema_contract_audit.py"
STAGE120_OUT_DIR = LINE_DIR / "outputs" / "stage120_wave0_schema_contract_audit"
STAGE120_SUMMARY = STAGE120_OUT_DIR / "qmt_roll_stage120_c9_minrisk_wave0_schema_contract_audit_summary_stage120_wave0_schema_contract_audit_v1.csv"
STAGE120_GATES = STAGE120_OUT_DIR / "qmt_roll_stage120_c9_minrisk_wave0_schema_contract_audit_schema_contract_gate_status_stage120_wave0_schema_contract_audit_v1.csv"
STAGE120_REQUEST_SCHEMA = STAGE120_OUT_DIR / "qmt_roll_stage120_c9_minrisk_wave0_schema_contract_audit_w0_request_schema_status_stage120_wave0_schema_contract_audit_v1.csv"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE116_MANIFEST = (
    LINE_DIR
    / "outputs"
    / "stage116_wave0_pipeline_intake_packet"
    / "qmt_roll_stage116_c9_minrisk_wave0_pipeline_intake_packet_w0_delivery_manifest_template_"
    "stage116_wave0_pipeline_intake_packet_v1.csv"
)
STAGE119_SYNTHETIC_MANIFEST = (
    LINE_DIR
    / "outputs"
    / "stage119_wave0_drop_manifest_builder"
    / "qmt_roll_stage119_c9_minrisk_wave0_drop_manifest_builder_synthetic_drop_positive_built_manifest_"
    "stage119_wave0_drop_manifest_builder_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CASE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_summary_{MODEL_TAG}.csv"
CASE_GATE_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_cli_status_{MODEL_TAG}.png"
GATE_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_gate_matrix_{MODEL_TAG}.png"
CASE_OUTCOME_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_outcome_chart_{MODEL_TAG}.png"

DECISION = "stage121_stage120_cli_entry_selftest_passed_no_real_data_no_strategy"
MBP10 = "authorized_mbp10_l2_minimum"
MBO = "authorized_mbo_l3_preferred"


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
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


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


def _run_stage120_case(case_id: str, args: list[str], expected_real_pass: int) -> tuple[dict[str, Any], pd.DataFrame]:
    command = [sys.executable, str(STAGE120_TOOL), *args]
    completed = subprocess.run(command, cwd=REPO_DIR, text=True, capture_output=True, check=False)
    decision_json = _parse_json_stdout(completed.stdout)
    summary = _read_csv(STAGE120_SUMMARY)
    gates = _read_csv(STAGE120_GATES)
    if gates.empty:
        gates = pd.DataFrame(columns=["gate_id", "observed", "required", "pass_now", "severity"])
    gates["case_id"] = case_id

    row = summary.iloc[0] if not summary.empty else pd.Series(dtype=object)
    real_pass = int(row.get("real_w0_schema_contract_pass", 0) or 0)
    real_data = int(row.get("real_w0_data_delivered", 0) or 0)
    true_engine_allowed = int(row.get("true_engine_allowed", 0) or 0)
    test_pass = int(completed.returncode == 0 and real_pass == expected_real_pass and true_engine_allowed == 0)
    case = {
        "case_id": case_id,
        "returncode": int(completed.returncode),
        "decision": decision_json.get("decision", row.get("decision", "")),
        "real_w0_data_delivered": real_data,
        "real_w0_schema_contract_pass": real_pass,
        "real_stage112_intake_allowed_now": int(row.get("real_stage112_intake_allowed_now", 0) or 0),
        "true_engine_allowed": true_engine_allowed,
        "strategy_feature_usable": int(row.get("strategy_feature_usable", 0) or 0),
        "planning_gate_pass_count": int(row.get("planning_gate_pass_count", 0) or 0),
        "planning_gate_count": int(row.get("planning_gate_count", 0) or 0),
        "data_hard_gate_pass_count": int(row.get("data_hard_gate_pass_count", 0) or 0),
        "data_hard_gate_count": int(row.get("data_hard_gate_count", 0) or 0),
        "expected_real_schema_contract_pass": int(expected_real_pass),
        "test_pass": test_pass,
        "stderr_tail": completed.stderr[-400:],
    }
    return case, gates


def _restore_stage120_default() -> None:
    subprocess.run([sys.executable, str(STAGE120_TOOL)], cwd=REPO_DIR, text=True, capture_output=True, check=True)


def _plot_official_path(request_schema: pd.DataFrame) -> None:
    curve = _load_curve()
    request_schema = request_schema.copy()
    request_schema["trading_day"] = pd.to_datetime(request_schema["trading_day"], errors="coerce")
    colors = {MBP10: "#0F766E", MBO: "#7C2D12"}
    fig, axes = plt.subplots(3, 1, figsize=(16, 10), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#202939", linewidth=1.1)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#DC2626", linewidth=1.0)
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#0369A1", linewidth=1.0)
    axes[2].axhline(100, color="#B91C1C", linestyle="--", linewidth=0.9)
    for idx, schema in enumerate([MBP10, MBO]):
        rows = request_schema[request_schema["required_schema_request"].eq(schema)]
        points = _nearest_curve_points(curve, rows["trading_day"])
        offset = (idx - 0.5) * 0.35
        axes[0].scatter(points["date"], points["account_equity"] / 1_000_000 + offset, color=colors[schema], s=42, alpha=0.7, label=schema)
        axes[1].scatter(points["date"], points["drawdown_pct"] + offset, color=colors[schema], s=42, alpha=0.7)
        axes[2].scatter(points["date"], points["broker10_margin_to_equity_pct"] + offset, color=colors[schema], s=42, alpha=0.7)
    axes[0].set_ylabel("equity (m)")
    axes[1].set_ylabel("drawdown %")
    axes[2].set_ylabel("broker10 %")
    for ax in axes:
        ax.grid(alpha=0.25)
    axes[0].legend(loc="upper left", fontsize=8)
    fig.suptitle("Stage121 Stage120 CLI selftest on official path; no real W0 accepted")
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_gate_matrix(gates: pd.DataFrame) -> None:
    pivot = gates.pivot_table(index="gate_id", columns="case_id", values="pass_now", aggfunc="max", fill_value=0)
    case_order = [case for case in ["default_no_args", "cli_empty_template", "cli_synthetic_manifest"] if case in pivot.columns]
    pivot = pivot[case_order]
    fig, ax = plt.subplots(figsize=(10, 7))
    image = ax.imshow(pivot.to_numpy(), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=20, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    for y in range(len(pivot.index)):
        for x in range(len(pivot.columns)):
            ax.text(x, y, "P" if int(pivot.iloc[y, x]) else "F", ha="center", va="center", color="#111827", fontsize=8)
    ax.set_title("Stage121 Stage120 CLI gate matrix")
    fig.colorbar(image, ax=ax, shrink=0.75)
    fig.tight_layout()
    fig.savefig(GATE_MATRIX_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_case_outcomes(case_summary: pd.DataFrame) -> None:
    metrics = ["real_w0_data_delivered", "real_w0_schema_contract_pass", "true_engine_allowed", "test_pass"]
    plot_data = case_summary.set_index("case_id")[metrics]
    fig, ax = plt.subplots(figsize=(11, 5))
    plot_data.plot(kind="bar", ax=ax, color=["#0369A1", "#0F766E", "#B91C1C", "#15803D"])
    ax.set_ylim(0, 1.2)
    ax.set_ylabel("binary status")
    ax.set_title("Stage121 CLI entry outcomes")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(CASE_OUTCOME_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, case_summary: pd.DataFrame, gates: pd.DataFrame) -> None:
    report = f"""# Stage121 W0 schema CLI entry selftest

## Decision

- decision: `{summary.iloc[0]['decision']}`
- nature: Stage120 CLI regression selftest only; no strategy rule, no true engine, no A/B, no CTP connection, no order API, no external download.

## Case Summary

{_md_table(case_summary)}

## Gate Matrix

{_md_table(gates[['case_id', 'gate_id', 'observed', 'required', 'pass_now', 'severity']], max_rows=60)}

## Visual Outputs

- official path CLI status: `{PATH_CHART_OUT}`
- case gate matrix: `{GATE_MATRIX_CHART_OUT}`
- case outcome chart: `{CASE_OUTCOME_CHART_OUT}`

## Judgment

Stage120 can now be called with an external manifest path. Empty and synthetic manifests remain blocked from real schema acceptance, and Stage120 default outputs are restored after the selftest.
"""
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cases = [
        ("default_no_args", [], 0),
        (
            "cli_empty_template",
            ["--manifest", str(STAGE116_MANIFEST), "--manifest-label", "cli_empty_template", "--skip-synthetic-selftest"],
            0,
        ),
        (
            "cli_synthetic_manifest",
            ["--manifest", str(STAGE119_SYNTHETIC_MANIFEST), "--manifest-label", "cli_synthetic_fixture", "--skip-synthetic-selftest"],
            0,
        ),
    ]
    case_rows: list[dict[str, Any]] = []
    gate_frames: list[pd.DataFrame] = []
    try:
        for case_id, args, expected_real_pass in cases:
            case, gates = _run_stage120_case(case_id, args, expected_real_pass)
            case_rows.append(case)
            gate_frames.append(gates)
    finally:
        _restore_stage120_default()

    case_summary = pd.DataFrame(case_rows)
    gates = pd.concat(gate_frames, ignore_index=True) if gate_frames else pd.DataFrame()
    stage120_summary = _read_csv(STAGE120_SUMMARY)
    base = stage120_summary.iloc[0] if not stage120_summary.empty else pd.Series(dtype=object)
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": DECISION if int(case_summary["test_pass"].sum()) == len(case_summary) else "stage121_stage120_cli_entry_selftest_failed",
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "case_count": int(len(case_summary)),
                "test_pass_count": int(case_summary["test_pass"].sum()),
                "test_fail_count": int(len(case_summary) - case_summary["test_pass"].sum()),
                "stage120_default_restored": 1,
                "real_w0_data_delivered": 0,
                "real_w0_schema_contract_pass": 0,
                "real_stage112_intake_allowed_now": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "end_equity": float(base.get("end_equity", np.nan)),
                "total_return_pct": float(base.get("total_return_pct", np.nan)),
                "max_drawdown_pct": float(base.get("max_drawdown_pct", np.nan)),
                "sharpe": float(base.get("sharpe", np.nan)),
                "total_slippage": float(base.get("total_slippage", np.nan)),
                "total_trade_count": float(base.get("total_trade_count", np.nan)),
                "closed_lot_win_rate_pct": float(base.get("closed_lot_win_rate_pct", np.nan)),
                "max_broker10_margin_to_equity_pct": float(base.get("max_broker10_margin_to_equity_pct", np.nan)),
            }
        ]
    )

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(case_summary, CASE_SUMMARY_OUT)
    _write_csv(gates, CASE_GATE_STATUS_OUT)

    request_schema = _read_csv(STAGE120_REQUEST_SCHEMA)
    _plot_official_path(request_schema)
    _plot_gate_matrix(gates)
    _plot_case_outcomes(case_summary)
    _write_report(summary, case_summary, gates)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": str(summary.iloc[0]["decision"]),
        "summary_path": SUMMARY_OUT,
        "case_summary_path": CASE_SUMMARY_OUT,
        "case_gate_status_path": CASE_GATE_STATUS_OUT,
        "report_path": REPORT_OUT,
        "charts": [PATH_CHART_OUT, GATE_MATRIX_CHART_OUT, CASE_OUTCOME_CHART_OUT],
        "stage120_default_restored": 1,
        "real_w0_data_delivered": 0,
        "real_w0_schema_contract_pass": 0,
        "real_stage112_intake_allowed_now": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
