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
STAGE = "Stage134"
MODEL_TAG = "stage134_wave0_total_gate_cli_entry_selftest_v1"
OUTPUT_PREFIX = "qmt_roll_stage134_c9_minrisk_wave0_total_gate_cli_entry_selftest"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage134_wave0_total_gate_cli_entry_selftest"

STAGE133_TOOL = LINE_DIR / "tools" / "stage133_wave0_total_intake_downstream_gate_audit.py"
EMPTY_DROP_DIR = LINE_DIR / "outputs" / "stage125_wave0_receipt_preflight_audit" / "empty_drop"
STAGE131_POSITIVE_DROP_DIR = (
    LINE_DIR
    / "outputs"
    / "stage131_wave0_positive_drop_supergate_audit"
    / "positive_drop"
    / "contract_positive_fixture_drop"
)

STAGE133_OUT_DIR = LINE_DIR / "outputs" / "stage133_wave0_total_intake_downstream_gate_audit"
STAGE133_SUMMARY = (
    STAGE133_OUT_DIR
    / "qmt_roll_stage133_c9_minrisk_wave0_total_intake_downstream_gate_audit_summary_"
    "stage133_wave0_total_intake_downstream_gate_audit_v1.csv"
)
STAGE133_CASE_AUDIT = (
    STAGE133_OUT_DIR
    / "qmt_roll_stage133_c9_minrisk_wave0_total_intake_downstream_gate_audit_case_downstream_audit_"
    "stage133_wave0_total_intake_downstream_gate_audit_v1.csv"
)
STAGE133_EXPECTATION = (
    STAGE133_OUT_DIR
    / "qmt_roll_stage133_c9_minrisk_wave0_total_intake_downstream_gate_audit_expectation_audit_"
    "stage133_wave0_total_intake_downstream_gate_audit_v1.csv"
)
STAGE133_REQUESTS = (
    STAGE133_OUT_DIR
    / "qmt_roll_stage133_c9_minrisk_wave0_total_intake_downstream_gate_audit_stage128_request_snapshots_"
    "stage133_wave0_total_intake_downstream_gate_audit_v1.csv"
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
COMMAND_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_command_audit_{MODEL_TAG}.csv"
STAGE133_SUMMARY_SNAPSHOT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage133_summary_snapshots_{MODEL_TAG}.csv"
STAGE133_CASE_SNAPSHOT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage133_case_snapshots_{MODEL_TAG}.csv"
STAGE133_EXPECTATION_SNAPSHOT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage133_expectation_snapshots_{MODEL_TAG}.csv"
STAGE133_REQUEST_SNAPSHOT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage133_request_snapshots_{MODEL_TAG}.csv"
EXPECTATION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_expectation_audit_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_cli_release_status_{MODEL_TAG}.png"
COMMAND_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_command_matrix_{MODEL_TAG}.png"
EXPECTATION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_expectation_matrix_{MODEL_TAG}.png"
CASE_RELEASE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_release_matrix_{MODEL_TAG}.png"

DECISION = "stage134_stage133_cli_entry_selftests_passed_no_real_data_no_strategy"


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


def _parse_json_stdout(stdout: str) -> dict[str, Any]:
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        return json.loads(stdout[start : end + 1])
    except json.JSONDecodeError:
        return {}


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


def _snapshot_outputs(stage134_case_id: str) -> dict[str, pd.DataFrame]:
    frames = {
        "stage133_summary": _read_csv(STAGE133_SUMMARY),
        "stage133_case": _read_csv(STAGE133_CASE_AUDIT),
        "stage133_expectation": _read_csv(STAGE133_EXPECTATION),
        "stage133_requests": _read_csv(STAGE133_REQUESTS),
    }
    for frame in frames.values():
        if not frame.empty:
            frame["stage134_case_id"] = stage134_case_id
    return frames


def _run_stage133(stage134_case_id: str, command: list[str]) -> tuple[dict[str, Any], dict[str, pd.DataFrame]]:
    completed = subprocess.run(
        command,
        cwd=REPO_DIR,
        text=True,
        capture_output=True,
        check=False,
        timeout=900,
    )
    parsed = _parse_json_stdout(completed.stdout)
    frames = _snapshot_outputs(stage134_case_id)
    return (
        {
            "stage134_case_id": stage134_case_id,
            "command": " ".join(command),
            "returncode": int(completed.returncode),
            "stdout_json_found": int(bool(parsed)),
            "stage133_decision": parsed.get("decision", ""),
            "stage133_release_verdict": parsed.get("release_verdict", ""),
            "stage133_expectation_pass_count": parsed.get("expectation_pass_count", ""),
            "stage133_expectation_count": parsed.get("expectation_count", ""),
            "stage133_downstream_release_allowed_count": parsed.get("downstream_release_allowed_count", ""),
            "stage133_stage128_ready_case_count": parsed.get("stage128_ready_case_count", ""),
            "stdout_tail": completed.stdout[-500:],
            "stderr_tail": completed.stderr[-500:],
        },
        frames,
    )


def _expectations(command_audit: pd.DataFrame, summaries: pd.DataFrame, cases: pd.DataFrame, expectations: pd.DataFrame) -> pd.DataFrame:
    def _cmd(case_id: str) -> pd.Series:
        frame = command_audit[command_audit["stage134_case_id"].eq(case_id)]
        return frame.iloc[0] if not frame.empty else pd.Series(dtype=object)

    def _summary(case_id: str) -> pd.Series:
        frame = summaries[summaries["stage134_case_id"].eq(case_id)]
        return frame.iloc[0] if not frame.empty else pd.Series(dtype=object)

    def _case(case_id: str) -> pd.Series:
        frame = cases[cases["stage134_case_id"].eq(case_id)]
        return frame.iloc[0] if not frame.empty else pd.Series(dtype=object)

    def _expectation_pass(case_id: str, expectation_id: str) -> int:
        frame = expectations[
            expectations["stage134_case_id"].eq(case_id)
            & expectations["expectation_id"].astype(str).eq(expectation_id)
        ]
        if frame.empty:
            return 0
        return int(pd.to_numeric(frame.iloc[0].get("pass_now", 0), errors="coerce") or 0)

    empty_cmd = _cmd("cli_empty_drop_release_blocked")
    empty_sum = _summary("cli_empty_drop_release_blocked")
    fixture_cmd = _cmd("cli_stage131_fixture_release_blocked")
    fixture_sum = _summary("cli_stage131_fixture_release_blocked")
    fixture_case = _case("cli_stage131_fixture_release_blocked")
    default_cmd = _cmd("default_restore_audit")
    default_sum = _summary("default_restore_audit")

    rows = [
        {
            "expectation_id": "cli_empty_returncode_zero",
            "required": "0",
            "observed": str(empty_cmd.get("returncode", "")),
            "pass_now": int(int(empty_cmd.get("returncode", -1)) == 0),
        },
        {
            "expectation_id": "cli_empty_release_blocked",
            "required": "blocked_no_downstream_release",
            "observed": str(empty_sum.get("release_verdict", "")),
            "pass_now": int(str(empty_sum.get("release_verdict", "")) == "blocked_no_downstream_release"),
        },
        {
            "expectation_id": "cli_empty_expected_release_match",
            "required": "1",
            "observed": str(_expectation_pass("cli_empty_drop_release_blocked", "cli_downstream_release_matches_expected")),
            "pass_now": _expectation_pass("cli_empty_drop_release_blocked", "cli_downstream_release_matches_expected"),
        },
        {
            "expectation_id": "cli_fixture_returncode_zero",
            "required": "0",
            "observed": str(fixture_cmd.get("returncode", "")),
            "pass_now": int(int(fixture_cmd.get("returncode", -1)) == 0),
        },
        {
            "expectation_id": "cli_fixture_stage128_positive_ready",
            "required": "1",
            "observed": str(fixture_case.get("stage128_full_supergate_ready", "")),
            "pass_now": int(int(fixture_case.get("stage128_full_supergate_ready", -1)) == 1),
        },
        {
            "expectation_id": "cli_fixture_stage112_rule_blocked",
            "required": "0",
            "observed": str(fixture_case.get("stage112_rule_ready_count", "")),
            "pass_now": int(int(fixture_case.get("stage112_rule_ready_count", -1)) == 0),
        },
        {
            "expectation_id": "cli_fixture_stage113_index_blocked",
            "required": "0",
            "observed": str(fixture_case.get("stage113_indexed_file_count", "")),
            "pass_now": int(int(fixture_case.get("stage113_indexed_file_count", -1)) == 0),
        },
        {
            "expectation_id": "cli_fixture_expected_release_match",
            "required": "1",
            "observed": str(_expectation_pass("cli_stage131_fixture_release_blocked", "cli_downstream_release_matches_expected")),
            "pass_now": _expectation_pass("cli_stage131_fixture_release_blocked", "cli_downstream_release_matches_expected"),
        },
        {
            "expectation_id": "default_restore_returncode_zero",
            "required": "0",
            "observed": str(default_cmd.get("returncode", "")),
            "pass_now": int(int(default_cmd.get("returncode", -1)) == 0),
        },
        {
            "expectation_id": "default_restore_negative_audit_pass",
            "required": "9/9 and release 0",
            "observed": f"{default_sum.get('expectation_pass_count', '')}/{default_sum.get('expectation_count', '')};release={default_sum.get('downstream_release_allowed_count', '')}",
            "pass_now": int(
                int(default_sum.get("expectation_pass_count", -1)) == int(default_sum.get("expectation_count", -2))
                and int(default_sum.get("downstream_release_allowed_count", -1)) == 0
            ),
        },
        {
            "expectation_id": "all_commands_json_found",
            "required": "3",
            "observed": str(int(pd.to_numeric(command_audit.get("stdout_json_found", 0), errors="coerce").fillna(0).sum())),
            "pass_now": int(pd.to_numeric(command_audit.get("stdout_json_found", 0), errors="coerce").fillna(0).sum() == 3),
        },
        {
            "expectation_id": "order_api_ctp_never_called",
            "required": "0/0",
            "observed": f"{int(pd.to_numeric(summaries.get('order_api_called', 0), errors='coerce').fillna(0).sum())}/{int(pd.to_numeric(summaries.get('ctp_connected', 0), errors='coerce').fillna(0).sum())}",
            "pass_now": int(
                pd.to_numeric(summaries.get("order_api_called", 0), errors="coerce").fillna(0).sum() == 0
                and pd.to_numeric(summaries.get("ctp_connected", 0), errors="coerce").fillna(0).sum() == 0
            ),
        },
    ]
    return pd.DataFrame(rows)


def _plot_official_path(curve: pd.DataFrame, requests: pd.DataFrame, summaries: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage134 Stage133 CLI release verdict selftest", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#1f5d4a", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#C2410C", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3B5BDB", linewidth=1.0)
    axes[2].axhline(100, color="#333333", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    if not requests.empty and "trading_day" in requests.columns:
        for case_id, group in requests.groupby("stage134_case_id"):
            points = _nearest_curve_points(curve, group["trading_day"])
            color = "#B91C1C" if "fixture" in case_id else "#A16207"
            marker = "o" if "fixture" in case_id else "x"
            axes[0].scatter(points["date"], points["account_equity"] / 1_000_000, color=color, marker=marker, s=24, alpha=0.45, label=case_id)
            axes[1].scatter(points["date"], points["drawdown_pct"], color=color, marker=marker, s=24, alpha=0.45)
            axes[2].scatter(points["date"], points["broker10_margin_to_equity_pct"], color=color, marker=marker, s=24, alpha=0.45)
        axes[0].legend(loc="upper left", fontsize=8)
    plot = summaries.set_index("stage134_case_id")[["stage128_ready_case_count", "downstream_release_allowed_count"]].copy()
    plot.plot(kind="bar", ax=axes[3], color=["#3B5BDB", "#15803D"])
    axes[3].set_title("Stage133 CLI release verdict by selftest case")
    axes[3].set_ylabel("count")
    axes[3].set_ylim(0, max(1.2, float(plot.to_numpy().max()) + 0.5))
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
    fig, ax = plt.subplots(figsize=(max(8, len(value_cols) * 1.5), max(4.5, len(matrix) * 0.55)))
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title(title)
    ax.set_xticks(np.arange(len(value_cols)))
    ax.set_xticklabels(value_cols, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, command_audit: pd.DataFrame, expectations: pd.DataFrame) -> None:
    report = [
        f"# {STAGE} Stage133 CLI entry selftest",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- scope: Stage133 CLI release verdict selftest only; no strategy rule, true engine, A/B, CTP, order API, or official config change.",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Command Audit",
        "",
        _md_table(command_audit[["stage134_case_id", "returncode", "stdout_json_found", "stage133_decision", "stage133_release_verdict"]]),
        "",
        "## Expectation Audit",
        "",
        _md_table(expectations),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{COMMAND_MATRIX_CHART_OUT.name}`",
        f"- `{EXPECTATION_CHART_OUT.name}`",
        f"- `{CASE_RELEASE_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    runs = [
        (
            "cli_empty_drop_release_blocked",
            [
                sys.executable,
                str(STAGE133_TOOL),
                "--drop-dir",
                str(EMPTY_DROP_DIR),
                "--case-id",
                "cli_empty_drop_release_blocked",
                "--expected-stage112-intake",
                "0",
                "--expected-downstream-release",
                "0",
            ],
        ),
        (
            "cli_stage131_fixture_release_blocked",
            [
                sys.executable,
                str(STAGE133_TOOL),
                "--drop-dir",
                str(STAGE131_POSITIVE_DROP_DIR),
                "--case-id",
                "cli_stage131_fixture_release_blocked",
                "--expected-stage112-intake",
                "1",
                "--expected-downstream-release",
                "0",
            ],
        ),
        ("default_restore_audit", [sys.executable, str(STAGE133_TOOL)]),
    ]
    command_rows: list[dict[str, Any]] = []
    summary_frames: list[pd.DataFrame] = []
    case_frames: list[pd.DataFrame] = []
    expectation_frames: list[pd.DataFrame] = []
    request_frames: list[pd.DataFrame] = []
    for stage134_case_id, command in runs:
        command_row, frames = _run_stage133(stage134_case_id, command)
        command_rows.append(command_row)
        if not frames["stage133_summary"].empty:
            summary_frames.append(frames["stage133_summary"])
        if not frames["stage133_case"].empty:
            case_frames.append(frames["stage133_case"])
        if not frames["stage133_expectation"].empty:
            expectation_frames.append(frames["stage133_expectation"])
        if not frames["stage133_requests"].empty:
            request_frames.append(frames["stage133_requests"])

    command_audit = pd.DataFrame(command_rows)
    summaries = pd.concat(summary_frames, ignore_index=True) if summary_frames else pd.DataFrame()
    cases = pd.concat(case_frames, ignore_index=True) if case_frames else pd.DataFrame()
    stage133_expectations = pd.concat(expectation_frames, ignore_index=True) if expectation_frames else pd.DataFrame()
    requests = pd.concat(request_frames, ignore_index=True) if request_frames else pd.DataFrame()
    expectations = _expectations(command_audit, summaries, cases, stage133_expectations)
    expectation_pass_count = int(pd.to_numeric(expectations["pass_now"], errors="coerce").fillna(0).sum())
    command_returncode_zero_count = int(command_audit["returncode"].eq(0).sum())
    decision = DECISION if expectation_pass_count == len(expectations) and command_returncode_zero_count == len(command_audit) else "stage134_stage133_cli_entry_selftests_failed"
    metrics = _baseline_metrics()
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
                "command_count": len(command_audit),
                "command_returncode_zero_count": command_returncode_zero_count,
                "stage133_cli_case_count": int(pd.to_numeric(summaries.get("cli_mode", 0), errors="coerce").fillna(0).sum()),
                "stage133_default_restore_pass": int(
                    not summaries[summaries["stage134_case_id"].eq("default_restore_audit")].empty
                    and int(summaries[summaries["stage134_case_id"].eq("default_restore_audit")].iloc[0].get("expectation_pass_count", -1))
                    == int(summaries[summaries["stage134_case_id"].eq("default_restore_audit")].iloc[0].get("expectation_count", -2))
                ),
                "cli_expected_release_match_count": int(
                    stage133_expectations[
                        stage133_expectations["expectation_id"].astype(str).eq("cli_downstream_release_matches_expected")
                    ]["pass_now"].sum()
                )
                if not stage133_expectations.empty
                else 0,
                "downstream_release_allowed_count": int(pd.to_numeric(summaries.get("downstream_release_allowed_count", 0), errors="coerce").fillna(0).sum()),
                "expectation_pass_count": expectation_pass_count,
                "expectation_count": len(expectations),
                "real_w0_data_delivered": 0,
                "real_stage112_intake_allowed_now": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                **metrics,
            }
        ]
    )

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(command_audit, COMMAND_AUDIT_OUT)
    _write_csv(summaries, STAGE133_SUMMARY_SNAPSHOT_OUT)
    _write_csv(cases, STAGE133_CASE_SNAPSHOT_OUT)
    _write_csv(stage133_expectations, STAGE133_EXPECTATION_SNAPSHOT_OUT)
    _write_csv(requests, STAGE133_REQUEST_SNAPSHOT_OUT)
    _write_csv(expectations, EXPECTATION_OUT)

    curve = _load_curve()
    _plot_official_path(curve, requests, summaries)
    command_plot = command_audit.copy()
    command_plot["returncode_zero"] = command_plot["returncode"].eq(0).astype(int)
    _plot_matrix(command_plot, "stage134_case_id", ["returncode_zero", "stdout_json_found"], "Stage134 Stage133 command matrix", COMMAND_MATRIX_CHART_OUT)
    _plot_matrix(expectations, "expectation_id", ["pass_now"], "Stage134 expectations", EXPECTATION_CHART_OUT)
    if not cases.empty:
        case_plot = cases.copy()
        for column in ["stage128_full_supergate_ready", "stage112_rule_ready_count", "stage113_indexed_file_count", "downstream_release_allowed_now"]:
            case_plot[column] = pd.to_numeric(case_plot[column], errors="coerce").fillna(0).clip(upper=1)
        case_plot["case_label"] = case_plot["stage134_case_id"].astype(str) + "::" + case_plot["total_case_id"].astype(str)
        _plot_matrix(
            case_plot,
            "case_label",
            ["stage128_full_supergate_ready", "stage112_rule_ready_count", "stage113_indexed_file_count", "downstream_release_allowed_now"],
            "Stage134 case release matrix",
            CASE_RELEASE_CHART_OUT,
        )
    _write_report(summary, command_audit, expectations)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "command_audit": str(COMMAND_AUDIT_OUT),
                "expectations": str(EXPECTATION_OUT),
                "report": str(REPORT_OUT),
                "charts": [str(PATH_CHART_OUT), str(COMMAND_MATRIX_CHART_OUT), str(EXPECTATION_CHART_OUT), str(CASE_RELEASE_CHART_OUT)],
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
