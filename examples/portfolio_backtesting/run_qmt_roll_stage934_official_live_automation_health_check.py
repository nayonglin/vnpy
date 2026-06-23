from __future__ import annotations

import argparse
import json
import os
import plistlib
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from qmt_roll_official_live_config import OFFICIAL_LIVE_VERSION
from qmt_roll_official_live_phase_d_config import build_phase_d_config
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage934_official_live_automation_health_check_v1"
OUTPUT_PREFIX = "qmt_roll_stage934_official_live_automation_health_check"
STAGE930_MODEL_TAG = "stage930_official_live_c9_session_daemon_v1"
STAGE930_PREFIX = "qmt_roll_stage930_official_live_c9_session_daemon"
REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_PATH = REPO_ROOT / ".py311/bin/python"
STAGE930_DAEMON_PATH = Path(__file__).resolve().parent / "run_qmt_roll_stage930_official_live_c9_session_daemon.py"
LAUNCHD_REPO_DIR = Path(__file__).resolve().parent / "launchd"
LAUNCHD_INSTALL_DIR = Path.home() / "Library/LaunchAgents"
SESSION_LABELS = {
    "day": "local.qmt-roll.official-live.15w.c9-day-session",
    "night": "local.qmt-roll.official-live.15w.c9-night-session",
}
REPORT_LABELS = {
    "postclose": "local.qmt-roll.official-live.15w.postclose",
    "evening_report": "local.qmt-roll.official-live.15w.evening-report",
}


def _paths(run_id: str) -> dict[str, Path]:
    return {
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{run_id}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{run_id}_{MODEL_TAG}.md",
        "latest_summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_latest_summary.json",
        "latest_report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_latest_report.md",
    }


def _run(cmd: list[str], timeout: int = 5) -> dict[str, Any]:
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
        return {"exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    except Exception as exc:
        return {"exit_code": -1, "stdout": "", "stderr": repr(exc)}


def _read_plist(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("rb") as handle:
            payload = plistlib.load(handle)
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _launchctl_print(label: str) -> dict[str, Any]:
    uid = os.getuid()
    result = _run(["launchctl", "print", f"gui/{uid}/{label}"], timeout=5)
    text = result.get("stdout", "")
    row: dict[str, Any] = {
        "label": label,
        "loaded": result.get("exit_code") == 0,
        "state": "",
        "program": "",
        "last_exit_code": "",
        "runs": "",
        "raw_exit_code": result.get("exit_code"),
        "stderr": result.get("stderr", ""),
    }
    for line in str(text).splitlines():
        stripped = line.strip()
        if stripped.startswith("state = "):
            row["state"] = stripped.split("=", 1)[1].strip()
        elif stripped.startswith("program = "):
            row["program"] = stripped.split("=", 1)[1].strip()
        elif stripped.startswith("last exit code = "):
            row["last_exit_code"] = stripped.split("=", 1)[1].strip()
        elif stripped.startswith("runs = "):
            row["runs"] = stripped.split("=", 1)[1].strip()
    return row


def _plist_status(label: str) -> dict[str, Any]:
    repo_path = LAUNCHD_REPO_DIR / f"{label}.plist"
    installed_path = LAUNCHD_INSTALL_DIR / f"{label}.plist"
    repo_plist = _read_plist(repo_path)
    installed_plist = _read_plist(installed_path)
    installed_args = installed_plist.get("ProgramArguments") or []
    repo_args = repo_plist.get("ProgramArguments") or []
    expected_args = [str(PYTHON_PATH), str(STAGE930_DAEMON_PATH)]
    return {
        "label": label,
        "repo_path": str(repo_path),
        "installed_path": str(installed_path),
        "repo_exists": repo_path.exists(),
        "installed_exists": installed_path.exists(),
        "repo_program_arguments_head": repo_args[:2],
        "installed_program_arguments_head": installed_args[:2],
        "repo_direct_python_stage930": repo_args[:2] == expected_args,
        "installed_direct_python_stage930": installed_args[:2] == expected_args,
        "repo_installed_arguments_match": repo_args == installed_args,
        "repo_working_directory": repo_plist.get("WorkingDirectory", ""),
        "installed_working_directory": installed_plist.get("WorkingDirectory", ""),
        "repo_installed_working_directory_match": repo_plist.get("WorkingDirectory", "") == installed_plist.get("WorkingDirectory", ""),
        "launchctl": _launchctl_print(label),
    }


def _latest_stage930_summary() -> dict[str, Any]:
    paths = sorted(OUTPUT_DIR.glob(f"{STAGE930_PREFIX}_summary_*_{STAGE930_MODEL_TAG}.json"), key=lambda item: item.stat().st_mtime)
    if not paths:
        return {"path": "", "exists": False}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        payload = {"_read_error": repr(exc)}
    return {
        "path": str(path),
        "exists": True,
        "age_seconds": max(0.0, time.time() - path.stat().st_mtime),
        "generated_at": payload.get("generated_at", ""),
        "daemon_status": payload.get("daemon_status", ""),
        "mode": payload.get("mode", ""),
        "submit_mode": payload.get("submit_mode", ""),
        "cycle_count": payload.get("cycle_count", 0),
        "target_date": payload.get("target_date", ""),
        "order_api_called_count": payload.get("order_api_called_count", 0),
        "latest_cycle": payload.get("latest_cycle", {}),
    }


def _current_sessions() -> list[str]:
    config = build_phase_d_config()
    now = datetime.now().time()
    active: list[str] = []
    for session in config.sessions:
        start_h, start_m = [int(part) for part in session.start.split(":", 1)]
        end_h, end_m = [int(part) for part in session.end.split(":", 1)]
        start = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
        end = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
        in_session = start <= now <= end if start <= end else now >= start or now <= end
        if in_session:
            active.append(session.name)
    return active


def _process_status() -> dict[str, Any]:
    screen = _run(["screen", "-ls"], timeout=5)
    pgrep = _run(["pgrep", "-af", "run_qmt_roll_stage930_official_live_c9_session_daemon.py"], timeout=5)
    screen_text = str(screen.get("stdout", ""))
    pgrep_lines = [line.strip() for line in str(pgrep.get("stdout", "")).splitlines() if line.strip()]
    pids: list[str] = []
    process_lines: list[str] = []
    for line in pgrep_lines:
        parts = line.split(maxsplit=1)
        if parts and parts[0].isdigit():
            pids.append(parts[0])
            if len(parts) > 1:
                process_lines.append(line)
    if pids:
        ps_result = _run(["ps", "-p", ",".join(pids), "-o", "pid,ppid,command"], timeout=5)
        process_lines = [
            line
            for line in str(ps_result.get("stdout", "")).splitlines()
            if "run_qmt_roll_stage930_official_live_c9_session_daemon.py" in line
        ]
    return {
        "screen_exit_code": screen.get("exit_code"),
        "screen_sessions": screen_text,
        "screen_qmt_c9_night_active": "qmt_c9_night_20260616" in screen_text,
        "stage930_process_count": len(process_lines),
        "stage930_process_lines": process_lines,
    }


def _build_summary(max_summary_age_seconds: int) -> dict[str, Any]:
    session_plists = {name: _plist_status(label) for name, label in SESSION_LABELS.items()}
    report_launchd = {name: _launchctl_print(label) for name, label in REPORT_LABELS.items()}
    latest = _latest_stage930_summary()
    process = _process_status()
    warnings: list[str] = []
    blockers: list[str] = []
    for name, row in session_plists.items():
        if not row.get("installed_direct_python_stage930"):
            blockers.append(f"{name}_launchd_not_direct_python_stage930")
        if not row.get("repo_installed_arguments_match"):
            warnings.append(f"{name}_repo_installed_program_arguments_mismatch")
        launchctl = row.get("launchctl") or {}
        if not launchctl.get("loaded"):
            blockers.append(f"{name}_launchd_not_loaded")
        if launchctl.get("last_exit_code") in {"126", "Operation not permitted"}:
            blockers.append(f"{name}_launchd_last_exit_126_operation_not_permitted")
    current_sessions = _current_sessions()
    summary_fresh = bool(latest.get("exists")) and float(latest.get("age_seconds") or 999999.0) <= max_summary_age_seconds
    daemon_running = latest.get("daemon_status") == "daemon_running" and latest.get("mode") == "live-real" and latest.get("submit_mode") == "live-real"
    process_running = int(process.get("stage930_process_count") or 0) > 0
    execution_session_now = any(name in {"night", "late_night", "day_am", "day_pm"} for name in current_sessions)
    if execution_session_now and not process_running:
        blockers.append("execution_session_without_stage930_process")
    if process_running and not summary_fresh:
        warnings.append("stage930_process_running_but_latest_summary_stale")
    if process_running and daemon_running and summary_fresh:
        health_status = "healthy_stage930_live_real_daemon_running"
    elif not blockers:
        health_status = "scheduled_launchd_ready_no_current_daemon"
    else:
        health_status = "blocked"
    return {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "health_status": health_status,
        "blockers": blockers,
        "warnings": warnings,
        "current_sessions": current_sessions,
        "max_summary_age_seconds": max_summary_age_seconds,
        "latest_stage930_summary": latest,
        "process_status": process,
        "session_launchd": session_plists,
        "report_launchd": report_launchd,
        "judgement": {
            "overfit_before": "否。健康检查只读取运行态和配置，不改策略参数或信号。",
            "continue_before": "是。自动交易必须能证明守护进程真实运行，不能只看计划任务文件。",
            "overfit_after": "否。输出只用于执行可观测性，不反向影响策略。",
            "continue_after": "是。后续应把该检查纳入每日邮件或外部监控，避免 launchd/screen 状态误判。",
        },
    }


def _build_report(summary: dict[str, Any]) -> str:
    latest = summary.get("latest_stage930_summary") or {}
    process = summary.get("process_status") or {}
    lines = [
        "# Stage934 官方实盘自动化健康检查",
        "",
        f"- 生成时间：{summary.get('generated_at', '')}",
        f"- 健康状态：{summary.get('health_status', '')}",
        f"- 当前交易时段：{', '.join(summary.get('current_sessions') or []) or 'none'}",
        f"- Stage930 进程数：{process.get('stage930_process_count', 0)}",
        f"- screen 夜盘兜底：{'active' if process.get('screen_qmt_c9_night_active') else 'inactive'}",
        f"- 最新 Stage930：{latest.get('daemon_status', '')} / {latest.get('mode', '')} / {latest.get('submit_mode', '')}",
        f"- 最新 summary 年龄秒：{latest.get('age_seconds', '')}",
        f"- 订单 API 次数：{latest.get('order_api_called_count', 0)}",
        f"- 阻断：{';'.join(summary.get('blockers') or []) or 'none'}",
        f"- 警告：{';'.join(summary.get('warnings') or []) or 'none'}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Official live automation health check.")
    parser.add_argument("--max-summary-age-seconds", type=int, default=300)
    args = parser.parse_args()
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = _paths(run_id)
    summary = _build_summary(max_summary_age_seconds=args.max_summary_age_seconds)
    report = _build_report(summary)
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(report, encoding="utf-8")
    paths["latest_summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["latest_report_md"].write_text(report, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
