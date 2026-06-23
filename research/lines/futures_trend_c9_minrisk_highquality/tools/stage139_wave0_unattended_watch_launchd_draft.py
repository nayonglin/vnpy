from __future__ import annotations

from datetime import datetime
import json
import plistlib
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage139"
MODEL_TAG = "stage139_wave0_unattended_watch_launchd_draft_v1"
OUTPUT_PREFIX = "qmt_roll_stage139_c9_minrisk_wave0_unattended_watch_launchd_draft"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage139_wave0_unattended_watch_launchd_draft"
LOG_DIR = OUTPUT_DIR / "logs"

PYTHON_BIN = REPO_DIR / ".py311" / "bin" / "python"
STAGE138_TOOL = LINE_DIR / "tools" / "stage138_wave0_unattended_watch_smoke.py"

LABEL = "local.vnpy.c9-minrisk.w0-watch-smoke.draft"
START_INTERVAL_SECONDS = 900

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
STAGE138_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage138_wave0_unattended_watch_smoke"
    / "qmt_roll_stage138_c9_minrisk_wave0_unattended_watch_smoke_summary_"
    "stage138_wave0_unattended_watch_smoke_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CONFIG_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_config_audit_{MODEL_TAG}.csv"
ARTIFACT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_schedule_artifact_matrix_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
PLIST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}.plist"
CRON_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cron_draft.txt"
RUNBOOK_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_operator_runbook.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_draft_status_{MODEL_TAG}.png"
SAFETY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_launchd_safety_matrix_{MODEL_TAG}.png"
ARTIFACT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_artifact_matrix_{MODEL_TAG}.png"
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


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _launchd_plist() -> dict[str, Any]:
    return {
        "Label": LABEL,
        "Disabled": True,
        "ProgramArguments": [str(PYTHON_BIN if PYTHON_BIN.exists() else Path(sys.executable)), str(STAGE138_TOOL)],
        "EnvironmentVariables": {
            "STAGE139_DRAFT_ONLY": "1",
            "VNPY_W0_WATCH_SCOPE": "stage138_smoke_only_no_stage125_133",
        },
        "WorkingDirectory": str(REPO_DIR),
        "StartInterval": START_INTERVAL_SECONDS,
        "StandardOutPath": str(LOG_DIR / f"{LABEL}.out.log"),
        "StandardErrorPath": str(LOG_DIR / f"{LABEL}.err.log"),
    }


def _write_plist(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        plistlib.dump(payload, handle, fmt=plistlib.FMT_XML, sort_keys=False)
    with path.open("rb") as handle:
        return plistlib.load(handle)


def _cron_line() -> str:
    python = PYTHON_BIN if PYTHON_BIN.exists() else Path(sys.executable)
    out_log = LOG_DIR / f"{LABEL}.cron.out.log"
    err_log = LOG_DIR / f"{LABEL}.cron.err.log"
    return (
        f"*/15 * * * * cd {REPO_DIR} && {python} {STAGE138_TOOL} "
        f">> {out_log} 2>> {err_log}"
    )


def _write_cron(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(
        [
            "# Stage139 draft only. Do not paste into crontab without operator approval.",
            "# The command is intentionally commented so the artifact is inert by default.",
            f"# {line}",
            "",
        ]
    )
    path.write_text(text, encoding="utf-8")


def _write_runbook(path: Path, loaded_plist: dict[str, Any], cron_line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Stage139 W0 watch launchd/cron draft runbook",
        "",
        "## Scope",
        "",
        "- Draft only: this stage writes artifacts under the research line output directory.",
        "- It does not install LaunchAgents, call launchctl, run Stage138, run Stage125, run Stage133, connect CTP, call order APIs, or change official configs.",
        "- The only programmed command is Stage138, which itself runs Stage137 selftest before Stage136 watch monitor.",
        "",
        "## Launchd Draft",
        "",
        f"- label: `{loaded_plist.get('Label')}`",
        f"- disabled: `{loaded_plist.get('Disabled')}`",
        f"- start_interval_seconds: `{loaded_plist.get('StartInterval')}`",
        f"- plist_path: `{PLIST_OUT}`",
        f"- stdout: `{loaded_plist.get('StandardOutPath')}`",
        f"- stderr: `{loaded_plist.get('StandardErrorPath')}`",
        "",
        "## Cron Draft",
        "",
        "- The cron artifact stores this line commented out:",
        "",
        "```cron",
        f"# {cron_line}",
        "```",
        "",
        "## Pre-Install Manual Gate",
        "",
        "1. Re-run Stage137 and confirm `selftest_pass=1` and Stage125/Stage133 executed counts are zero.",
        "2. Re-run Stage138 and confirm `smoke_pass=1` with `stage133_release_allowed_now=0` until a real W0 drop arrives.",
        "3. Confirm the generated plist still has `Disabled=true`, no `RunAtLoad`, no `KeepAlive`, no CTP or order-submit environment variables, and ProgramArguments points only to Stage138.",
        "4. Only after explicit operator approval, copy the plist into `~/Library/LaunchAgents/` or uncomment the cron line. This stage does not perform that action.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _installed_locations() -> list[Path]:
    return [
        Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist",
        Path("/Library/LaunchAgents") / f"{LABEL}.plist",
        Path("/Library/LaunchDaemons") / f"{LABEL}.plist",
    ]


def _audit_config(loaded_plist: dict[str, Any], cron_line: str) -> pd.DataFrame:
    program_args = [str(item) for item in loaded_plist.get("ProgramArguments", [])]
    joined_args = " ".join(program_args)
    stdout_path = Path(str(loaded_plist.get("StandardOutPath", "")))
    stderr_path = Path(str(loaded_plist.get("StandardErrorPath", "")))
    env_keys = set((loaded_plist.get("EnvironmentVariables") or {}).keys())
    forbidden_env_hit = any("CTP" in key or "ORDER" in key or "SUBMIT" in key for key in env_keys)
    installed_count = sum(int(path.exists()) for path in _installed_locations())
    rows = [
        {
            "check_id": "plist_written_under_line_output",
            "observed": int(PLIST_OUT.exists() and _is_under(PLIST_OUT, OUTPUT_DIR)),
            "required": 1,
            "pass_now": int(PLIST_OUT.exists() and _is_under(PLIST_OUT, OUTPUT_DIR)),
            "detail": str(PLIST_OUT),
        },
        {
            "check_id": "plist_parse_ok",
            "observed": int(bool(loaded_plist)),
            "required": 1,
            "pass_now": int(bool(loaded_plist)),
            "detail": "plistlib.load",
        },
        {
            "check_id": "label_marked_draft",
            "observed": int(str(loaded_plist.get("Label", "")).endswith(".draft")),
            "required": 1,
            "pass_now": int(str(loaded_plist.get("Label", "")).endswith(".draft")),
            "detail": str(loaded_plist.get("Label", "")),
        },
        {
            "check_id": "disabled_true",
            "observed": int(loaded_plist.get("Disabled") is True),
            "required": 1,
            "pass_now": int(loaded_plist.get("Disabled") is True),
            "detail": str(loaded_plist.get("Disabled")),
        },
        {
            "check_id": "no_run_at_load",
            "observed": int("RunAtLoad" not in loaded_plist),
            "required": 1,
            "pass_now": int("RunAtLoad" not in loaded_plist),
            "detail": "RunAtLoad absent",
        },
        {
            "check_id": "no_keep_alive",
            "observed": int("KeepAlive" not in loaded_plist),
            "required": 1,
            "pass_now": int("KeepAlive" not in loaded_plist),
            "detail": "KeepAlive absent",
        },
        {
            "check_id": "no_ctp_order_env",
            "observed": int(not forbidden_env_hit),
            "required": 1,
            "pass_now": int(not forbidden_env_hit),
            "detail": ",".join(sorted(env_keys)),
        },
        {
            "check_id": "program_points_to_stage138",
            "observed": int(program_args[-1:] == [str(STAGE138_TOOL)]),
            "required": 1,
            "pass_now": int(program_args[-1:] == [str(STAGE138_TOOL)]),
            "detail": joined_args,
        },
        {
            "check_id": "program_absent_stage125_133",
            "observed": int("stage125" not in joined_args and "stage133" not in joined_args),
            "required": 1,
            "pass_now": int("stage125" not in joined_args and "stage133" not in joined_args),
            "detail": joined_args,
        },
        {
            "check_id": "working_directory_repo",
            "observed": int(Path(str(loaded_plist.get("WorkingDirectory", ""))).resolve() == REPO_DIR.resolve()),
            "required": 1,
            "pass_now": int(Path(str(loaded_plist.get("WorkingDirectory", ""))).resolve() == REPO_DIR.resolve()),
            "detail": str(loaded_plist.get("WorkingDirectory", "")),
        },
        {
            "check_id": "start_interval_900_seconds",
            "observed": int(loaded_plist.get("StartInterval") == START_INTERVAL_SECONDS),
            "required": 1,
            "pass_now": int(loaded_plist.get("StartInterval") == START_INTERVAL_SECONDS),
            "detail": str(loaded_plist.get("StartInterval")),
        },
        {
            "check_id": "logs_under_line_output",
            "observed": int(_is_under(stdout_path, OUTPUT_DIR) and _is_under(stderr_path, OUTPUT_DIR)),
            "required": 1,
            "pass_now": int(_is_under(stdout_path, OUTPUT_DIR) and _is_under(stderr_path, OUTPUT_DIR)),
            "detail": f"{stdout_path} | {stderr_path}",
        },
        {
            "check_id": "not_installed_to_launch_locations",
            "observed": int(installed_count == 0),
            "required": 1,
            "pass_now": int(installed_count == 0),
            "detail": ";".join(str(path) for path in _installed_locations()),
        },
        {
            "check_id": "cron_draft_line_commented",
            "observed": int(CRON_OUT.exists() and "# */15" in CRON_OUT.read_text(encoding="utf-8")),
            "required": 1,
            "pass_now": int(CRON_OUT.exists() and "# */15" in CRON_OUT.read_text(encoding="utf-8")),
            "detail": str(CRON_OUT),
        },
        {
            "check_id": "cron_points_to_stage138",
            "observed": int(str(STAGE138_TOOL) in cron_line),
            "required": 1,
            "pass_now": int(str(STAGE138_TOOL) in cron_line),
            "detail": cron_line,
        },
        {
            "check_id": "cron_absent_stage125_133",
            "observed": int("stage125" not in cron_line and "stage133" not in cron_line),
            "required": 1,
            "pass_now": int("stage125" not in cron_line and "stage133" not in cron_line),
            "detail": cron_line,
        },
        {
            "check_id": "runbook_created",
            "observed": int(RUNBOOK_OUT.exists()),
            "required": 1,
            "pass_now": int(RUNBOOK_OUT.exists()),
            "detail": str(RUNBOOK_OUT),
        },
        {
            "check_id": "stage138_not_executed_by_stage139",
            "observed": 1,
            "required": 1,
            "pass_now": 1,
            "detail": "draft generation only",
        },
        {
            "check_id": "launchctl_not_called",
            "observed": 1,
            "required": 1,
            "pass_now": 1,
            "detail": "no subprocess launchctl call in script",
        },
    ]
    return pd.DataFrame(rows)


def _artifact_matrix(loaded_plist: dict[str, Any], cron_line: str) -> pd.DataFrame:
    program_args = " ".join(str(item) for item in loaded_plist.get("ProgramArguments", []))
    rows = [
        {
            "artifact_id": "launchd_plist_draft",
            "created": int(PLIST_OUT.exists()),
            "parse_or_format_ok": int(bool(loaded_plist)),
            "safe_disabled_or_commented": int(loaded_plist.get("Disabled") is True),
            "points_to_stage138": int(str(STAGE138_TOOL) in program_args),
            "not_installed": int(sum(int(path.exists()) for path in _installed_locations()) == 0),
            "path": str(PLIST_OUT),
        },
        {
            "artifact_id": "cron_draft_commented",
            "created": int(CRON_OUT.exists()),
            "parse_or_format_ok": int(CRON_OUT.exists() and "# */15" in CRON_OUT.read_text(encoding="utf-8")),
            "safe_disabled_or_commented": int(CRON_OUT.exists() and "# */15" in CRON_OUT.read_text(encoding="utf-8")),
            "points_to_stage138": int(str(STAGE138_TOOL) in cron_line),
            "not_installed": 1,
            "path": str(CRON_OUT),
        },
        {
            "artifact_id": "operator_runbook",
            "created": int(RUNBOOK_OUT.exists()),
            "parse_or_format_ok": int(RUNBOOK_OUT.exists() and "Pre-Install Manual Gate" in RUNBOOK_OUT.read_text(encoding="utf-8")),
            "safe_disabled_or_commented": 1,
            "points_to_stage138": int(str(STAGE138_TOOL) in RUNBOOK_OUT.read_text(encoding="utf-8")) if RUNBOOK_OUT.exists() else 0,
            "not_installed": 1,
            "path": str(RUNBOOK_OUT),
        },
    ]
    return pd.DataFrame(rows)


def _gate_status(config_audit: pd.DataFrame, artifact: pd.DataFrame, stage138_summary: pd.DataFrame) -> pd.DataFrame:
    audit_all_pass = int(not config_audit.empty and int(config_audit["pass_now"].sum()) == len(config_audit))
    artifact_all_pass = int(
        not artifact.empty
        and int(artifact[["created", "parse_or_format_ok", "safe_disabled_or_commented", "points_to_stage138", "not_installed"]].sum().sum())
        == int(artifact.shape[0] * 5)
    )
    stage138_smoke_pass = int(not stage138_summary.empty and int(stage138_summary.iloc[0].get("smoke_pass", 0)) == 1)
    release_locked = int(
        not stage138_summary.empty
        and int(stage138_summary.iloc[0].get("stage133_release_allowed_now", -1)) == 0
        and int(stage138_summary.iloc[0].get("true_engine_allowed", -1)) == 0
    )
    rows = [
        {
            "gate_id": "prior_stage138_smoke_passed",
            "observed": stage138_smoke_pass,
            "required": 1,
            "pass_now": stage138_smoke_pass,
            "severity": "dependency_hard",
        },
        {
            "gate_id": "prior_release_locked_no_strategy",
            "observed": release_locked,
            "required": 1,
            "pass_now": release_locked,
            "severity": "anti_selection_hard",
        },
        {
            "gate_id": "config_safety_checks_all_pass",
            "observed": audit_all_pass,
            "required": 1,
            "pass_now": audit_all_pass,
            "severity": "schedule_hard",
        },
        {
            "gate_id": "artifact_matrix_all_pass",
            "observed": artifact_all_pass,
            "required": 1,
            "pass_now": artifact_all_pass,
            "severity": "schedule_hard",
        },
        {
            "gate_id": "draft_not_installed_or_loaded",
            "observed": int(sum(int(path.exists()) for path in _installed_locations()) == 0),
            "required": 1,
            "pass_now": int(sum(int(path.exists()) for path in _installed_locations()) == 0),
            "severity": "operator_hard",
        },
        {
            "gate_id": "no_stage125_133_or_trading_trigger",
            "observed": 1,
            "required": 1,
            "pass_now": 1,
            "severity": "execution_hard",
        },
    ]
    return pd.DataFrame(rows)


def _write_report(
    summary: pd.DataFrame,
    config_audit: pd.DataFrame,
    artifact: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    report = [
        f"# {STAGE} W0 unattended watch schedule draft",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- scope: generate inert launchd/cron drafts for Stage138 watch smoke; no installation, launchctl, Stage125/133, strategy rule, true engine, A/B, CTP, order API, or official config change.",
        "",
        "## Summary",
        "",
        _md_table(summary.drop(columns=["plist_draft_path", "cron_draft_path", "runbook_path"], errors="ignore")),
        "",
        "## Config Audit",
        "",
        _md_table(config_audit.drop(columns=["detail"], errors="ignore")),
        "",
        "## Artifact Matrix",
        "",
        _md_table(artifact.drop(columns=["path"], errors="ignore")),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
        "## Draft Artifacts",
        "",
        f"- plist: `{PLIST_OUT}`",
        f"- cron draft: `{CRON_OUT}`",
        f"- runbook: `{RUNBOOK_OUT}`",
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{SAFETY_CHART_OUT.name}`",
        f"- `{ARTIFACT_CHART_OUT.name}`",
        f"- `{GATE_CHART_OUT.name}`",
        "",
        "## External References Used",
        "",
        "- Apple Developer launchd daemon/agent guide: https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html",
        "- Python plistlib documentation: https://docs.python.org/3/library/plistlib.html",
        "- launchd.plist man page: https://www.manpagez.com/man/5/launchd.plist/",
    ]
    REPORT_OUT.write_text("\n".join(report) + "\n", encoding="utf-8")


def _plot_official_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage139 launchd/cron draft: inert schedule wrapper around Stage138", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#1f5d4a", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#C2410C", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3B5BDB", linewidth=1.0)
    axes[2].axhline(100, color="#333333", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    cols = [
        "draft_ready",
        "launchd_disabled_true",
        "cron_draft_commented",
        "not_installed_to_launch_locations",
        "stage133_release_allowed_now",
    ]
    plot = summary[cols].T
    plot.columns = ["status"]
    colors = ["#0F766E", "#0F766E", "#0F766E", "#0F766E", "#B91C1C"]
    plot.plot(kind="bar", ax=axes[3], legend=False, color=colors)
    axes[3].set_title("Draft safety status")
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
    fig, ax = plt.subplots(figsize=(max(8.5, len(value_cols) * 1.8), max(4.8, len(matrix) * 0.45)))
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


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    metrics = _baseline_metrics(curve)
    stage138_summary = _read_csv(STAGE138_SUMMARY_IN)

    plist_payload = _launchd_plist()
    loaded_plist = _write_plist(PLIST_OUT, plist_payload)
    cron_line = _cron_line()
    _write_cron(CRON_OUT, cron_line)
    _write_runbook(RUNBOOK_OUT, loaded_plist, cron_line)

    config_audit = _audit_config(loaded_plist, cron_line)
    artifact = _artifact_matrix(loaded_plist, cron_line)
    gate = _gate_status(config_audit, artifact, stage138_summary)

    gate_pass = int(gate["pass_now"].sum())
    gate_count = len(gate)
    config_pass = int(config_audit["pass_now"].sum())
    artifact_pass = int(
        artifact[["created", "parse_or_format_ok", "safe_disabled_or_commented", "points_to_stage138", "not_installed"]].sum().sum()
    )
    artifact_required = int(artifact.shape[0] * 5)
    stage138_smoke_pass = int(not stage138_summary.empty and int(stage138_summary.iloc[0].get("smoke_pass", 0)) == 1)
    stage133_release_allowed_now = int(stage138_summary.iloc[0].get("stage133_release_allowed_now", 0)) if not stage138_summary.empty else 0
    installed_launch_agent_count = sum(int(path.exists()) for path in _installed_locations())
    draft_ready = int(gate_pass == gate_count)
    if draft_ready:
        decision = "stage139_launchd_cron_draft_ready_not_installed_no_strategy"
    else:
        decision = "stage139_launchd_cron_draft_failed_attention_no_strategy"

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
                "launchctl_called": 0,
                "stage138_command_executed": 0,
                "stage125_command_executed": 0,
                "stage133_command_executed": 0,
                "draft_ready": draft_ready,
                "launchd_plist_created": int(PLIST_OUT.exists()),
                "launchd_disabled_true": int(loaded_plist.get("Disabled") is True),
                "cron_draft_created": int(CRON_OUT.exists()),
                "cron_draft_commented": int(CRON_OUT.exists() and "# */15" in CRON_OUT.read_text(encoding="utf-8")),
                "runbook_created": int(RUNBOOK_OUT.exists()),
                "not_installed_to_launch_locations": int(installed_launch_agent_count == 0),
                "installed_launch_agent_count": installed_launch_agent_count,
                "start_interval_seconds": START_INTERVAL_SECONDS,
                "cron_interval_minutes": 15,
                "config_audit_pass_count": config_pass,
                "config_audit_count": len(config_audit),
                "artifact_gate_pass_count": artifact_pass,
                "artifact_gate_count": artifact_required,
                "gate_pass_count": gate_pass,
                "gate_count": gate_count,
                "stage138_smoke_pass": stage138_smoke_pass,
                "stage133_release_allowed_now": stage133_release_allowed_now,
                "real_w0_data_delivered": 0,
                "real_stage112_intake_allowed_now": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "label": LABEL,
                "plist_draft_path": str(PLIST_OUT),
                "cron_draft_path": str(CRON_OUT),
                "runbook_path": str(RUNBOOK_OUT),
                **metrics,
            }
        ]
    )

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(config_audit, CONFIG_AUDIT_OUT)
    _write_csv(artifact, ARTIFACT_OUT)
    _write_csv(gate, GATE_OUT)
    _write_report(summary, config_audit, artifact, gate)
    _plot_official_path(curve, summary)
    _plot_matrix(
        config_audit,
        "check_id",
        ["observed", "required", "pass_now"],
        "Stage139 launchd/cron config safety checks",
        SAFETY_CHART_OUT,
    )
    _plot_matrix(
        artifact,
        "artifact_id",
        ["created", "parse_or_format_ok", "safe_disabled_or_commented", "points_to_stage138", "not_installed"],
        "Stage139 schedule artifact matrix",
        ARTIFACT_CHART_OUT,
    )
    _plot_matrix(gate, "gate_id", ["pass_now"], "Stage139 schedule draft hard gates", GATE_CHART_OUT)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "config_audit": str(CONFIG_AUDIT_OUT),
                "schedule_artifact_matrix": str(ARTIFACT_OUT),
                "gate_status": str(GATE_OUT),
                "report": str(REPORT_OUT),
                "plist_draft": str(PLIST_OUT),
                "cron_draft": str(CRON_OUT),
                "runbook": str(RUNBOOK_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(SAFETY_CHART_OUT),
                    str(ARTIFACT_CHART_OUT),
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
                "launchctl_called": 0,
                "stage138_command_executed": 0,
                "stage125_command_executed": 0,
                "stage133_command_executed": 0,
                "installed_launch_agent_count": installed_launch_agent_count,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
