from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage140"
MODEL_TAG = "stage140_wave0_unattended_watch_preinstall_status_panel_v1"
OUTPUT_PREFIX = "qmt_roll_stage140_c9_minrisk_wave0_unattended_watch_preinstall_status_panel"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage140_wave0_unattended_watch_preinstall_status_panel"

LABEL = "local.vnpy.c9-minrisk.w0-watch-smoke.draft"
FORBIDDEN_LAUNCHCTL_SUBCOMMANDS = {
    "bootstrap",
    "bootout",
    "enable",
    "disable",
    "kickstart",
    "load",
    "unload",
    "start",
    "stop",
    "submit",
    "remove",
}

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE134_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage134_wave0_total_gate_cli_entry_selftest"
    / "qmt_roll_stage134_c9_minrisk_wave0_total_gate_cli_entry_selftest_summary_"
    "stage134_wave0_total_gate_cli_entry_selftest_v1.csv"
)
STAGE136_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage136_wave0_watch_inbox_arrival_monitor"
    / "qmt_roll_stage136_c9_minrisk_wave0_watch_inbox_arrival_monitor_summary_"
    "stage136_wave0_watch_inbox_arrival_monitor_v1.csv"
)
STAGE136_SNAPSHOT_IN = (
    LINE_DIR
    / "outputs"
    / "stage136_wave0_watch_inbox_arrival_monitor"
    / "qmt_roll_stage136_c9_minrisk_wave0_watch_inbox_arrival_monitor_candidate_inbox_snapshot_"
    "stage136_wave0_watch_inbox_arrival_monitor_v1.csv"
)
STAGE139_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage139_wave0_unattended_watch_launchd_draft"
    / "qmt_roll_stage139_c9_minrisk_wave0_unattended_watch_launchd_draft_summary_"
    "stage139_wave0_unattended_watch_launchd_draft_v1.csv"
)
STAGE139_CONFIG_AUDIT_IN = (
    LINE_DIR
    / "outputs"
    / "stage139_wave0_unattended_watch_launchd_draft"
    / "qmt_roll_stage139_c9_minrisk_wave0_unattended_watch_launchd_draft_config_audit_"
    "stage139_wave0_unattended_watch_launchd_draft_v1.csv"
)
STAGE139_ARTIFACT_IN = (
    LINE_DIR
    / "outputs"
    / "stage139_wave0_unattended_watch_launchd_draft"
    / "qmt_roll_stage139_c9_minrisk_wave0_unattended_watch_launchd_draft_schedule_artifact_matrix_"
    "stage139_wave0_unattended_watch_launchd_draft_v1.csv"
)
STAGE139_GATE_IN = (
    LINE_DIR
    / "outputs"
    / "stage139_wave0_unattended_watch_launchd_draft"
    / "qmt_roll_stage139_c9_minrisk_wave0_unattended_watch_launchd_draft_gate_status_"
    "stage139_wave0_unattended_watch_launchd_draft_v1.csv"
)
STAGE139_PLIST_IN = (
    LINE_DIR
    / "outputs"
    / "stage139_wave0_unattended_watch_launchd_draft"
    / "qmt_roll_stage139_c9_minrisk_wave0_unattended_watch_launchd_draft.plist"
)
STAGE139_CRON_IN = (
    LINE_DIR
    / "outputs"
    / "stage139_wave0_unattended_watch_launchd_draft"
    / "qmt_roll_stage139_c9_minrisk_wave0_unattended_watch_launchd_draft_cron_draft.txt"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMMAND_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readonly_command_audit_{MODEL_TAG}.csv"
PREINSTALL_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_preinstall_audit_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
DASHBOARD_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_operator_dashboard_{MODEL_TAG}.md"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_preinstall_status_{MODEL_TAG}.png"
COMMAND_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readonly_command_matrix_{MODEL_TAG}.png"
PREINSTALL_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_preinstall_audit_matrix_{MODEL_TAG}.png"
WATCH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_watch_artifact_status_{MODEL_TAG}.png"
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


def _load_plist(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        return plistlib.load(handle)


def _installed_locations() -> list[Path]:
    return [
        Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist",
        Path("/Library/LaunchAgents") / f"{LABEL}.plist",
        Path("/Library/LaunchDaemons") / f"{LABEL}.plist",
    ]


def _run_readonly_command(step_order: int, step_id: str, command: list[str], expected_loaded: int | None = None) -> dict[str, Any]:
    executable = shutil.which(command[0])
    tokens = [Path(command[0]).name, *command[1:]]
    dangerous = int(tokens[0] == "launchctl" and len(tokens) > 1 and tokens[1] in FORBIDDEN_LAUNCHCTL_SUBCOMMANDS)
    if executable is None:
        return {
            "step_order": step_order,
            "step_id": step_id,
            "command": " ".join(command),
            "executable_found": 0,
            "executed": 0,
            "returncode": 127,
            "dangerous_launchctl_subcommand": dangerous,
            "no_mutating_launchctl_subcommand": int(dangerous == 0),
            "expected_loaded": -1 if expected_loaded is None else expected_loaded,
            "loaded_now": -1,
            "pass_now": 0,
            "stdout_tail": "",
            "stderr_tail": f"missing executable: {command[0]}",
        }
    result = subprocess.run(command, cwd=REPO_DIR, text=True, capture_output=True, check=False)
    loaded_now = int(result.returncode == 0) if expected_loaded is not None else -1
    if expected_loaded is None:
        pass_now = int(result.returncode == 0 and dangerous == 0)
    else:
        pass_now = int(loaded_now == expected_loaded and dangerous == 0)
    return {
        "step_order": step_order,
        "step_id": step_id,
        "command": " ".join(command),
        "executable_found": 1,
        "executed": 1,
        "returncode": int(result.returncode),
        "dangerous_launchctl_subcommand": dangerous,
        "no_mutating_launchctl_subcommand": int(dangerous == 0),
        "expected_loaded": -1 if expected_loaded is None else expected_loaded,
        "loaded_now": loaded_now,
        "pass_now": pass_now,
        "stdout_tail": "\n".join(result.stdout.strip().splitlines()[-5:]),
        "stderr_tail": "\n".join(result.stderr.strip().splitlines()[-5:]),
    }


def _readonly_commands() -> pd.DataFrame:
    uid = os.getuid()
    rows = [
        _run_readonly_command(1, "plutil_lint_stage139_plist", ["plutil", "-lint", str(STAGE139_PLIST_IN)]),
        _run_readonly_command(2, "launchctl_print_gui_label_not_loaded", ["launchctl", "print", f"gui/{uid}/{LABEL}"], expected_loaded=0),
        _run_readonly_command(3, "launchctl_print_user_label_not_loaded", ["launchctl", "print", f"user/{uid}/{LABEL}"], expected_loaded=0),
    ]
    return pd.DataFrame(rows)


def _safe_int(frame: pd.DataFrame, column: str, default: int = 0) -> int:
    if frame.empty or column not in frame:
        return default
    value = pd.to_numeric(pd.Series([frame.iloc[0].get(column, default)]), errors="coerce").fillna(default).iloc[0]
    return int(value)


def _stage139_inert_controls(plist_payload: dict[str, Any], cron_text: str) -> dict[str, int]:
    program_args = " ".join(str(item) for item in plist_payload.get("ProgramArguments", []))
    return {
        "plist_parse_ok": int(bool(plist_payload)),
        "plist_disabled_true": int(plist_payload.get("Disabled") is True),
        "no_run_at_load": int("RunAtLoad" not in plist_payload),
        "no_keep_alive": int("KeepAlive" not in plist_payload),
        "program_points_to_stage138": int("stage138_wave0_unattended_watch_smoke.py" in program_args),
        "program_absent_stage125_133": int("stage125" not in program_args and "stage133" not in program_args),
        "cron_still_commented": int("# */15" in cron_text),
        "cron_points_to_stage138": int("stage138_wave0_unattended_watch_smoke.py" in cron_text),
        "cron_absent_stage125_133": int("stage125" not in cron_text and "stage133" not in cron_text),
    }


def _preinstall_audit(
    command_audit: pd.DataFrame,
    plist_payload: dict[str, Any],
    stage136_summary: pd.DataFrame,
    stage139_summary: pd.DataFrame,
    stage139_config: pd.DataFrame,
    stage139_artifact: pd.DataFrame,
    stage139_gate: pd.DataFrame,
    cron_text: str,
) -> pd.DataFrame:
    inert = _stage139_inert_controls(plist_payload, cron_text)
    installed_count = sum(int(path.exists()) for path in _installed_locations())
    log_paths = [
        Path(str(plist_payload.get("StandardOutPath", ""))),
        Path(str(plist_payload.get("StandardErrorPath", ""))),
    ]
    log_parent_writable = int(all(path.parent.exists() and os.access(path.parent, os.W_OK) for path in log_paths))
    plutil_pass = int(
        not command_audit.empty
        and int(command_audit.loc[command_audit["step_id"] == "plutil_lint_stage139_plist", "pass_now"].sum()) == 1
    )
    launchctl_not_loaded = int(
        not command_audit.empty
        and int(command_audit.loc[command_audit["step_id"].str.contains("launchctl_print"), "pass_now"].sum()) == 2
    )
    dangerous_launchctl_count = int(command_audit["dangerous_launchctl_subcommand"].sum()) if not command_audit.empty else 0
    stage139_draft_ready = _safe_int(stage139_summary, "draft_ready")
    stage139_config_pass = int(
        not stage139_config.empty and int(pd.to_numeric(stage139_config["pass_now"], errors="coerce").fillna(0).sum()) == len(stage139_config)
    )
    stage139_artifact_pass = int(
        not stage139_artifact.empty
        and int(
            stage139_artifact[
                ["created", "parse_or_format_ok", "safe_disabled_or_commented", "points_to_stage138", "not_installed"]
            ]
            .apply(pd.to_numeric, errors="coerce")
            .fillna(0)
            .sum()
            .sum()
        )
        == len(stage139_artifact) * 5
    )
    stage139_gate_pass = int(
        not stage139_gate.empty and int(pd.to_numeric(stage139_gate["pass_now"], errors="coerce").fillna(0).sum()) == len(stage139_gate)
    )
    monitor_ready = _safe_int(stage136_summary, "monitor_ready")
    real_w0 = _safe_int(stage136_summary, "real_w0_data_delivered")
    release_locked = int(_safe_int(stage136_summary, "stage133_release_allowed_now", default=-1) == 0)
    rows = [
        ("stage139_summary_draft_ready", stage139_draft_ready, 1, "dependency_hard"),
        ("stage139_config_audit_all_pass", stage139_config_pass, 1, "dependency_hard"),
        ("stage139_artifact_matrix_all_pass", stage139_artifact_pass, 1, "dependency_hard"),
        ("stage139_gate_all_pass", stage139_gate_pass, 1, "dependency_hard"),
        ("plutil_lint_ok", plutil_pass, 1, "plist_hard"),
        ("launchctl_label_not_loaded", launchctl_not_loaded, 1, "operator_hard"),
        ("not_installed_to_launch_locations", int(installed_count == 0), 1, "operator_hard"),
        ("plist_disabled_true", inert["plist_disabled_true"], 1, "inert_hard"),
        ("no_run_at_load", inert["no_run_at_load"], 1, "inert_hard"),
        ("no_keep_alive", inert["no_keep_alive"], 1, "inert_hard"),
        ("program_points_to_stage138_only", int(inert["program_points_to_stage138"] and inert["program_absent_stage125_133"]), 1, "scope_hard"),
        ("cron_still_commented_and_safe", int(inert["cron_still_commented"] and inert["cron_points_to_stage138"] and inert["cron_absent_stage125_133"]), 1, "scope_hard"),
        ("log_parent_writable", log_parent_writable, 1, "operator_hard"),
        ("stage136_monitor_ready", monitor_ready, 1, "watch_hard"),
        ("real_w0_not_delivered_yet", int(real_w0 == 0), 1, "data_state"),
        ("release_locked_no_strategy", release_locked, 1, "anti_selection_hard"),
        ("no_mutating_launchctl_subcommand", int(dangerous_launchctl_count == 0), 1, "execution_hard"),
        ("stage140_did_not_execute_stage138_125_133", 1, 1, "execution_hard"),
    ]
    return pd.DataFrame(
        [
            {
                "check_id": check_id,
                "observed": observed,
                "required": required,
                "pass_now": int(observed == required),
                "severity": severity,
            }
            for check_id, observed, required, severity in rows
        ]
    )


def _gate_status(preinstall_audit: pd.DataFrame) -> pd.DataFrame:
    audit_all_pass = int(not preinstall_audit.empty and int(preinstall_audit["pass_now"].sum()) == len(preinstall_audit))
    critical_pass = int(
        not preinstall_audit.empty
        and int(preinstall_audit.loc[preinstall_audit["severity"].str.endswith("_hard"), "pass_now"].sum())
        == int(preinstall_audit["severity"].str.endswith("_hard").sum())
    )
    rows = [
        {
            "gate_id": "preinstall_audit_all_pass",
            "observed": audit_all_pass,
            "required": 1,
            "pass_now": audit_all_pass,
            "severity": "preinstall_hard",
        },
        {
            "gate_id": "critical_hard_checks_all_pass",
            "observed": critical_pass,
            "required": 1,
            "pass_now": critical_pass,
            "severity": "preinstall_hard",
        },
        {
            "gate_id": "install_still_blocked_without_operator",
            "observed": 1,
            "required": 1,
            "pass_now": 1,
            "severity": "operator_hard",
        },
        {
            "gate_id": "strategy_research_still_blocked_without_real_w0",
            "observed": 1,
            "required": 1,
            "pass_now": 1,
            "severity": "data_hard",
        },
    ]
    return pd.DataFrame(rows)


def _write_dashboard(summary: pd.DataFrame, preinstall_audit: pd.DataFrame, command_audit: pd.DataFrame) -> None:
    row = summary.iloc[0]
    lines = [
        "# Stage140 W0 watch pre-install status dashboard",
        "",
        f"- decision: `{row['decision']}`",
        f"- preinstall_status_ready: `{row['preinstall_status_ready']}`",
        f"- install_recommendation: `{row['install_recommendation']}`",
        f"- real_w0_data_delivered: `{row['real_w0_data_delivered']}`",
        f"- stage133_release_allowed_now: `{row['stage133_release_allowed_now']}`",
        f"- installed_launch_agent_count: `{row['installed_launch_agent_count']}`",
        f"- launchctl_mutating_command_count: `{row['launchctl_mutating_command_count']}`",
        "",
        "## Operator View",
        "",
        "- Do not install the draft automatically.",
        "- If a real W0 drop arrives, run Stage125 receipt preflight first, then Stage133 release verdict.",
        "- Stage112/113 and strategy research remain blocked until real data passes all hard gates.",
        "",
        "## Preinstall Audit",
        "",
        _md_table(preinstall_audit),
        "",
        "## Read-only Commands",
        "",
        _md_table(command_audit.drop(columns=["stdout_tail", "stderr_tail"], errors="ignore")),
        "",
    ]
    DASHBOARD_OUT.write_text("\n".join(lines), encoding="utf-8")


def _write_report(summary: pd.DataFrame, command_audit: pd.DataFrame, preinstall_audit: pd.DataFrame, gate: pd.DataFrame) -> None:
    report = [
        f"# {STAGE} W0 watch pre-install status panel",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- scope: read Stage139 schedule draft, run read-only `plutil -lint` and `launchctl print`, build an operator dashboard; no install, no mutating launchctl subcommand, no Stage138/125/133, no strategy rule, no true engine, no A/B, no CTP, no order API.",
        "",
        "## Summary",
        "",
        _md_table(summary.drop(columns=["dashboard_path"], errors="ignore")),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
        "## Preinstall Audit",
        "",
        _md_table(preinstall_audit),
        "",
        "## Read-only Command Audit",
        "",
        _md_table(command_audit.drop(columns=["stdout_tail", "stderr_tail"], errors="ignore")),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{COMMAND_CHART_OUT.name}`",
        f"- `{PREINSTALL_CHART_OUT.name}`",
        f"- `{WATCH_CHART_OUT.name}`",
        f"- `{GATE_CHART_OUT.name}`",
        "",
        "## External References Used",
        "",
        "- Apple Support launchd script management: https://support.apple.com/guide/terminal/script-management-with-launchd-apdc6c1077b-5d5d-4d35-9c19-60f2397b2369/mac",
        "- plutil man page: https://www.manpagez.com/man/1/plutil/",
        "- launchd.plist man page: https://www.manpagez.com/man/5/launchd.plist/",
    ]
    REPORT_OUT.write_text("\n".join(report) + "\n", encoding="utf-8")


def _plot_official_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage140 pre-install status: read-only checks, no install", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#1f5d4a", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#C2410C", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3B5BDB", linewidth=1.0)
    axes[2].axhline(100, color="#333333", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    cols = [
        "preinstall_status_ready",
        "plutil_lint_ok",
        "launchctl_label_not_loaded",
        "installed_launch_agent_count",
        "real_w0_data_delivered",
        "stage133_release_allowed_now",
    ]
    plot = summary[cols].T
    plot.columns = ["status"]
    plot.plot(kind="bar", ax=axes[3], legend=False, color="#0F766E")
    axes[3].set_title("Pre-install status flags")
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
    fig, ax = plt.subplots(figsize=(max(8.5, len(value_cols) * 1.7), max(4.8, len(matrix) * 0.46)))
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


def _plot_watch_status(summary: pd.DataFrame, stage136_summary: pd.DataFrame, stage139_summary: pd.DataFrame, stage136_snapshot: pd.DataFrame) -> None:
    values = {
        "stage136_monitor_ready": _safe_int(stage136_summary, "monitor_ready"),
        "best_known_files": _safe_int(stage136_summary, "best_known_file_count"),
        "stage125_candidates": _safe_int(stage136_summary, "stage125_candidate_count"),
        "stage133_ready_candidates": _safe_int(stage136_summary, "candidate_ready_count"),
        "candidate_dirs": _safe_int(stage136_summary, "candidate_dir_count"),
        "existing_candidate_dirs": _safe_int(stage136_summary, "existing_candidate_dir_count"),
        "stage139_draft_ready": _safe_int(stage139_summary, "draft_ready"),
        "preinstall_status_ready": _safe_int(summary, "preinstall_status_ready"),
    }
    fig, ax = plt.subplots(figsize=(12, 5.5))
    labels = list(values.keys())
    data = [values[label] for label in labels]
    colors = ["#0F766E" if value > 0 else "#9CA3AF" for value in data]
    ax.bar(labels, data, color=colors)
    ax.set_title("Stage140 W0 watch and schedule artifact status")
    ax.set_ylabel("count / flag")
    ax.tick_params(axis="x", rotation=35)
    ax.grid(axis="y", alpha=0.25)
    if not stage136_snapshot.empty and "candidate_dir" in stage136_snapshot.columns:
        ax.text(
            0.99,
            0.95,
            f"candidate rows: {len(stage136_snapshot)}",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=9,
        )
    fig.tight_layout()
    fig.savefig(WATCH_CHART_OUT, dpi=170)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    metrics = _baseline_metrics(curve)
    stage136_summary = _read_csv(STAGE136_SUMMARY_IN)
    stage136_snapshot = _read_csv(STAGE136_SNAPSHOT_IN)
    stage139_summary = _read_csv(STAGE139_SUMMARY_IN)
    stage139_config = _read_csv(STAGE139_CONFIG_AUDIT_IN)
    stage139_artifact = _read_csv(STAGE139_ARTIFACT_IN)
    stage139_gate = _read_csv(STAGE139_GATE_IN)
    plist_payload = _load_plist(STAGE139_PLIST_IN)
    cron_text = STAGE139_CRON_IN.read_text(encoding="utf-8") if STAGE139_CRON_IN.exists() else ""

    command_audit = _readonly_commands()
    preinstall_audit = _preinstall_audit(
        command_audit,
        plist_payload,
        stage136_summary,
        stage139_summary,
        stage139_config,
        stage139_artifact,
        stage139_gate,
        cron_text,
    )
    gate = _gate_status(preinstall_audit)

    preinstall_status_ready = int(gate["pass_now"].sum() == len(gate))
    real_w0 = _safe_int(stage136_summary, "real_w0_data_delivered")
    stage133_release_allowed_now = _safe_int(stage136_summary, "stage133_release_allowed_now", default=0)
    installed_count = sum(int(path.exists()) for path in _installed_locations())
    launchctl_mutating_count = int(command_audit["dangerous_launchctl_subcommand"].sum()) if not command_audit.empty else 0
    readonly_command_count = int(command_audit["executed"].sum()) if not command_audit.empty else 0
    launchctl_readonly_count = (
        int(command_audit.loc[command_audit["step_id"].str.contains("launchctl"), "executed"].sum()) if not command_audit.empty else 0
    )
    plutil_lint_ok = int(preinstall_audit.loc[preinstall_audit["check_id"] == "plutil_lint_ok", "pass_now"].sum())
    launchctl_label_not_loaded = int(preinstall_audit.loc[preinstall_audit["check_id"] == "launchctl_label_not_loaded", "pass_now"].sum())
    if preinstall_status_ready and real_w0 == 0:
        decision = "stage140_preinstall_status_panel_ready_waiting_real_w0_no_install"
        install_recommendation = "do_not_install_waiting_real_w0"
    elif preinstall_status_ready and real_w0 > 0:
        decision = "stage140_preinstall_status_panel_real_w0_seen_operator_review_no_install"
        install_recommendation = "operator_review_stage125_then_stage133_required"
    else:
        decision = "stage140_preinstall_status_panel_failed_attention_no_install"
        install_recommendation = "do_not_install_fix_preinstall_audit_first"

    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": decision,
                "install_recommendation": install_recommendation,
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "readonly_command_count": readonly_command_count,
                "launchctl_readonly_command_count": launchctl_readonly_count,
                "launchctl_mutating_command_count": launchctl_mutating_count,
                "stage136_command_executed": 0,
                "stage138_command_executed": 0,
                "stage125_command_executed": 0,
                "stage133_command_executed": 0,
                "preinstall_status_ready": preinstall_status_ready,
                "preinstall_audit_pass_count": int(preinstall_audit["pass_now"].sum()),
                "preinstall_audit_count": len(preinstall_audit),
                "gate_pass_count": int(gate["pass_now"].sum()),
                "gate_count": len(gate),
                "plutil_lint_ok": plutil_lint_ok,
                "launchctl_label_not_loaded": launchctl_label_not_loaded,
                "installed_launch_agent_count": installed_count,
                "stage139_draft_ready": _safe_int(stage139_summary, "draft_ready"),
                "stage136_monitor_ready": _safe_int(stage136_summary, "monitor_ready"),
                "stage136_stage125_candidate_count": _safe_int(stage136_summary, "stage125_candidate_count"),
                "stage136_candidate_ready_count": _safe_int(stage136_summary, "candidate_ready_count"),
                "stage136_best_known_file_count": _safe_int(stage136_summary, "best_known_file_count"),
                "stage136_expected_file_count": _safe_int(stage136_summary, "expected_file_count"),
                "stage133_release_allowed_now": stage133_release_allowed_now,
                "real_w0_data_delivered": real_w0,
                "real_stage112_intake_allowed_now": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "dashboard_path": str(DASHBOARD_OUT),
                **metrics,
            }
        ]
    )

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(command_audit, COMMAND_AUDIT_OUT)
    _write_csv(preinstall_audit, PREINSTALL_AUDIT_OUT)
    _write_csv(gate, GATE_OUT)
    _write_dashboard(summary, preinstall_audit, command_audit)
    _write_report(summary, command_audit, preinstall_audit, gate)
    _plot_official_path(curve, summary)
    _plot_matrix(
        command_audit,
        "step_id",
        ["executable_found", "executed", "no_mutating_launchctl_subcommand", "pass_now"],
        "Stage140 read-only command audit",
        COMMAND_CHART_OUT,
    )
    _plot_matrix(
        preinstall_audit,
        "check_id",
        ["observed", "required", "pass_now"],
        "Stage140 pre-install audit",
        PREINSTALL_CHART_OUT,
    )
    _plot_watch_status(summary, stage136_summary, stage139_summary, stage136_snapshot)
    _plot_matrix(gate, "gate_id", ["pass_now"], "Stage140 hard gate status", GATE_CHART_OUT)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "install_recommendation": install_recommendation,
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "readonly_command_audit": str(COMMAND_AUDIT_OUT),
                "preinstall_audit": str(PREINSTALL_AUDIT_OUT),
                "gate_status": str(GATE_OUT),
                "dashboard": str(DASHBOARD_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(COMMAND_CHART_OUT),
                    str(PREINSTALL_CHART_OUT),
                    str(WATCH_CHART_OUT),
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
                "launchctl_mutating_command_count": launchctl_mutating_count,
                "stage136_command_executed": 0,
                "stage138_command_executed": 0,
                "stage125_command_executed": 0,
                "stage133_command_executed": 0,
                "installed_launch_agent_count": installed_count,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
