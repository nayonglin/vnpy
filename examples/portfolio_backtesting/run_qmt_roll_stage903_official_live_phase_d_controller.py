from __future__ import annotations

import argparse
import json
import os
import shlex
import signal
import subprocess
import sys
import time
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from qmt_roll_official_execution_profile import (
    ExecutionStrategyMode,
    OfficialExecutionProfile,
    assert_profile_identity,
    resolve_execution_profile,
)
from qmt_roll_official_live_phase_d_config import (
    CONTROLLER_HEARTBEAT_PATH,
    CONTROLLER_STATE_PATH,
    KILL_SWITCH_PATH,
    PHASE_D_CONFIRM_TEXT,
    PHASE_D_READONLY_REFRESH_CONFIRM_TEXT,
    PHASE_D_REAL_ADAPTER_ENV,
    PHASE_D_REAL_ENABLED_ENV,
    PHASE_D_READONLY_REFRESH_ENV,
    PHASE_D_SESSION_DAEMON_ENV,
    PHASE_D_SHADOW_REFRESH_CONFIRM_TEXT,
    PHASE_D_SHADOW_REFRESH_ENV,
    READONLY_POSITIONS_PATH,
    READONLY_SUMMARY_PATH,
    READONLY_TICKS_PATH,
    READONLY_TRADES_PATH,
    build_phase_d_config,
    phase_d_config_to_dict,
)
from run_qmt_alignment_backtest import OUTPUT_DIR


PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent.parent
MODEL_TAG = "stage903_official_live_phase_d_controller_v1"
OUTPUT_PREFIX = "qmt_roll_stage903_official_live_phase_d_controller"
STAGE902_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage902_official_live_phase_d_readiness_gate.py"
STAGE902_MODEL_TAG = "stage902_official_live_phase_d_readiness_gate_v1"
STAGE902_PREFIX = "qmt_roll_stage902_official_live_phase_d_readiness_gate"
STAGE608_SCRIPT = PROJECT_DIR / "run_ctp_stage608_readonly_tick_snapshot_probe.py"
STAGE608_MODEL_TAG = "stage608_readonly_tick_snapshot_probe_v1"
STAGE904_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage904_official_live_c9_intraday_monitor.py"
STAGE904_MODEL_TAG = "stage904_official_live_c9_intraday_monitor_v1"
STAGE904_PREFIX = "qmt_roll_stage904_official_live_c9_intraday_monitor"
STAGE905_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage905_official_live_executor_dry_run.py"
STAGE905_MODEL_TAG = "stage905_official_live_executor_dry_run_v1"
STAGE905_PREFIX = "qmt_roll_stage905_official_live_executor_dry_run"
STAGE906_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage906_official_live_reconciliation_worker.py"
STAGE906_MODEL_TAG = "stage906_official_live_reconciliation_worker_v1"
STAGE906_PREFIX = "qmt_roll_stage906_official_live_reconciliation_worker"
STAGE907_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage907_official_live_readonly_refresh_gate.py"
STAGE260_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage260_stage78_1_simnow_daily_execution_gate.py"
STAGE260_MODEL_TAG = "stage260_official_live_daily_execution_gate_v1"
STAGE260_PREFIX = "qmt_roll_stage260_official_live_daily_execution_gate"
STAGE251_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage251_phaseb_fresh_pre_submit_gate.py"
STAGE251_MODEL_TAG = "stage251_phaseb_fresh_pre_submit_gate_v1"
STAGE251_PREFIX = "qmt_roll_stage251_phaseb_fresh_pre_submit_gate"
STAGE908_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage908_official_live_submit_adapter_contract.py"
STAGE908_MODEL_TAG = "stage908_official_live_submit_adapter_contract_v1"
STAGE908_PREFIX = "qmt_roll_stage908_official_live_submit_adapter_contract"
STAGE909_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage909_official_live_shadow_refresh_gate.py"
STAGE909_MODEL_TAG = "stage909_official_live_shadow_refresh_gate_v1"
STAGE909_PREFIX = "qmt_roll_stage909_official_live_shadow_refresh_gate"
STAGE914_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage914_official_live_ctp_runtime_preflight.py"
STAGE922_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage922_official_live_target_date_resolver.py"
STAGE923_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage923_official_live_fail_closed_incident.py"
STAGE924_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage924_official_live_account_recovery_gate.py"


def _paths(run_id: str) -> dict[str, Path]:
    return {
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{run_id}_{MODEL_TAG}.json",
        "cycle_plan_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_cycle_plan_{run_id}_{MODEL_TAG}.csv",
        "event_log_ndjson": OUTPUT_DIR / f"{OUTPUT_PREFIX}_events_{run_id}_{MODEL_TAG}.ndjson",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{run_id}_{MODEL_TAG}.md",
        "launchd_plist": OUTPUT_DIR / f"{OUTPUT_PREFIX}_launchd_template_{run_id}_{MODEL_TAG}.plist",
        "heartbeat_json": CONTROLLER_HEARTBEAT_PATH,
        "state_json": CONTROLLER_STATE_PATH,
    }


def _stage902_summary_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE902_PREFIX}_summary_{date_key}_{STAGE902_MODEL_TAG}.json"


def _stage904_summary_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE904_PREFIX}_summary_{date_key}_{STAGE904_MODEL_TAG}.json"


def _stage905_summary_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE905_PREFIX}_summary_{date_key}_{STAGE905_MODEL_TAG}.json"


def _stage906_summary_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE906_PREFIX}_summary_{date_key}_{STAGE906_MODEL_TAG}.json"


def _stage260_summary_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE260_PREFIX}_summary_{date_key}_{STAGE260_MODEL_TAG}.json"


def _stage251_summary_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE251_PREFIX}_summary_{date_key}_{STAGE251_MODEL_TAG}.json"


def _stage908_summary_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE908_PREFIX}_summary_{date_key}_{STAGE908_MODEL_TAG}.json"


def _stage909_summary_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE909_PREFIX}_summary_{date_key}_{STAGE909_MODEL_TAG}.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _read_csv_maybe(path: str | Path | None) -> pd.DataFrame:
    if not path:
        return pd.DataFrame()
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(p, encoding="utf-8-sig")
    except EmptyDataError:
        return pd.DataFrame()


def _parse_json_stdout(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        return {}
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return {"_read_error": "json_payload_not_found"}
    try:
        return json.loads(text[start : end + 1])
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _shell_ctp_readonly_command(script: Path, script_args: list[str]) -> list[str]:
    env_file = PROJECT_DIR / "ctp_live.local.env"
    framework_dir = REPO_ROOT / ".py311/lib/python3.11/site-packages/vnpy_ctp/api/libs"
    py311_lib = REPO_ROOT / ".py311/lib"
    command = " ".join([shlex.quote(sys.executable), shlex.quote(str(script)), *[shlex.quote(str(item)) for item in script_args]])
    shell = "\n".join(
        [
            "set -euo pipefail",
            f"set -a; source {shlex.quote(str(env_file))}; set +a",
            (
                "export DYLD_FRAMEWORK_PATH="
                f"{shlex.quote(str(framework_dir))}:{shlex.quote(str(py311_lib))}"
                "${DYLD_FRAMEWORK_PATH:+:${DYLD_FRAMEWORK_PATH}}"
            ),
            command,
        ]
    )
    return ["bash", "-lc", shell]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _append_events(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _to_int(value: Any, default: int = 0) -> int:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return int(number)


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _parse_time(value: str) -> dt_time:
    hour, minute = value.split(":", 1)
    return dt_time(hour=int(hour), minute=int(minute))


def _parse_generated_at(value: Any) -> datetime | None:
    text = _clean(value)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _age_seconds(value: Any, now: datetime) -> float | None:
    parsed = _parse_generated_at(value)
    if parsed is None:
        return None
    return max(0.0, (now - parsed).total_seconds())


def _time_in_window(now_time: dt_time, start: dt_time, end: dt_time) -> bool:
    if start <= end:
        return start <= now_time < end
    return now_time >= start or now_time < end


def _current_sessions(now: datetime) -> list[dict[str, Any]]:
    config = build_phase_d_config()
    rows: list[dict[str, Any]] = []
    for session in config.sessions:
        start = _parse_time(session.start)
        end = _parse_time(session.end)
        if _time_in_window(now.time(), start, end):
            rows.append(
                {
                    "name": session.name,
                    "start": session.start,
                    "end": session.end,
                    "role": session.role,
                }
            )
    return rows


def _kill_switch_active() -> tuple[bool, dict[str, Any]]:
    payload = _read_json(KILL_SWITCH_PATH)
    active = bool(payload.get("enabled", False) or payload.get("kill_switch_active", False))
    return active, payload


def _run_stage902(
    target_date: str,
    mode: str,
    max_snapshot_age_seconds: int,
    confirm_live_real: str,
    *,
    execution_profile: OfficialExecutionProfile,
) -> dict[str, Any]:
    readiness_mode = "live-real" if mode == "live-real" else "dry-run"
    cmd = [
        sys.executable,
        str(STAGE902_SCRIPT),
        "--target-date",
        target_date,
        "--execution-profile",
        execution_profile.profile_key,
        "--mode",
        readiness_mode,
        "--max-snapshot-age-seconds",
        str(max_snapshot_age_seconds),
    ]
    if readiness_mode == "live-real":
        cmd.extend(["--confirm-live-real", confirm_live_real])
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJECT_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    started = datetime.now()
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    summary = _read_json(_stage902_summary_path(target_date))
    return {
        "command": cmd,
        "exit_code": result.returncode,
        "stdout_tail": result.stdout[-4000:],
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": summary,
    }


def _run_stage909(
    *,
    execution_profile: OfficialExecutionProfile,
    target_date: str,
    shadow_refresh_mode: str,
    analysis_start: str,
    mapping_start: str,
    bar_start: str,
    confirm_shadow_refresh: str,
) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(STAGE909_SCRIPT),
        "--target-date",
        target_date,
        "--execution-profile",
        execution_profile.profile_key,
        "--mode",
        shadow_refresh_mode,
        "--analysis-start",
        analysis_start,
    ]
    if mapping_start:
        cmd.extend(["--mapping-start", mapping_start])
    if bar_start:
        cmd.extend(["--bar-start", bar_start])
    if confirm_shadow_refresh:
        cmd.extend(["--confirm-shadow-refresh", confirm_shadow_refresh])
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJECT_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    started = datetime.now()
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {
        "command": cmd,
        "exit_code": result.returncode,
        "stdout_tail": result.stdout[-4000:],
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": _read_json(_stage909_summary_path(target_date)),
    }


def _run_stage907(
    *,
    refresh_mode: str,
    env_profile: str,
    wait_seconds: int,
    confirm_readonly_refresh: str,
) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(STAGE907_SCRIPT),
        "--mode",
        refresh_mode,
        "--env-profile",
        env_profile,
        "--wait-seconds",
        str(wait_seconds),
    ]
    if confirm_readonly_refresh:
        cmd.extend(["--confirm-readonly-refresh", confirm_readonly_refresh])
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJECT_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    started = datetime.now()
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {
        "command": cmd,
        "exit_code": result.returncode,
        "stdout_tail": result.stdout[-4000:],
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": _parse_json_stdout(result.stdout),
    }


def _run_stage914(
    wait_seconds: int,
    *,
    execution_profile: OfficialExecutionProfile,
) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(STAGE914_SCRIPT),
        "--wait-seconds",
        str(wait_seconds),
        "--execution-profile",
        execution_profile.profile_key,
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJECT_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    started = datetime.now()
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {
        "command": cmd,
        "exit_code": result.returncode,
        "stdout_tail": result.stdout[-4000:],
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": _parse_json_stdout(result.stdout),
    }


def _stage914_result_ready(
    result: dict[str, Any],
    *,
    execution_profile: OfficialExecutionProfile,
) -> bool:
    exit_code = result.get("exit_code")
    if type(exit_code) is not int or exit_code != 0:
        return False
    summary = result.get("summary", {})
    if not isinstance(summary, dict):
        return False
    if summary.get("execution_profile") != execution_profile.profile_key:
        return False
    try:
        assert_profile_identity(
            execution_profile,
            official_version=summary.get("official_live_version"),
            capital=summary.get("capital"),
            capital_label=summary.get("capital_label"),
        )
    except (TypeError, ValueError):
        return False
    return (
        summary.get("preflight_status")
        == "production_readonly_preflight_passed"
        and _to_int(summary.get("blocking_failure_count"), 999) == 0
    )


def _run_stage608_intraday_tick_refresh(
    *,
    symbols: list[str],
    refresh_mode: str,
    wait_seconds: int,
    pre_subscribe_wait_seconds: int,
    stage914_ready: bool,
) -> dict[str, Any]:
    target_symbols = sorted({_clean(symbol) for symbol in symbols if _clean(symbol)})
    if refresh_mode == "skip":
        return {
            "command": [],
            "exit_code": 0,
            "timed_out": 0,
            "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {"status": "intraday_tick_refresh_skipped_by_mode"},
            "tick_rows": int(len(_read_csv_maybe(READONLY_TICKS_PATH))),
            "symbols": target_symbols,
        }
    if not target_symbols:
        return {
            "command": [],
            "exit_code": 0,
            "timed_out": 0,
            "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {"status": "intraday_tick_refresh_skipped_no_symbols"},
            "tick_rows": int(len(_read_csv_maybe(READONLY_TICKS_PATH))),
            "symbols": target_symbols,
        }
    if not stage914_ready:
        return {
            "command": [],
            "exit_code": 0,
            "timed_out": 0,
            "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {"status": "intraday_tick_refresh_skipped_stage914_not_ready"},
            "tick_rows": int(len(_read_csv_maybe(READONLY_TICKS_PATH))),
            "symbols": target_symbols,
        }

    stage_args = [
        "--connect",
        "--wait-seconds",
        str(wait_seconds),
        "--pre-subscribe-wait-seconds",
        str(pre_subscribe_wait_seconds),
        "--submit-plan",
        str(OUTPUT_DIR / "__nonexistent_stage903_intraday_tick_submit_plan.csv"),
    ]
    for symbol in target_symbols:
        stage_args.extend(["--vt-symbol", symbol])
    cmd = _shell_ctp_readonly_command(STAGE608_SCRIPT, stage_args)
    started = datetime.now()
    proc = subprocess.Popen(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    timeout_seconds = max(30, pre_subscribe_wait_seconds + wait_seconds + 60)
    timed_out = 0
    try:
        stdout, _ = proc.communicate(timeout=timeout_seconds)
        exit_code = proc.returncode
    except subprocess.TimeoutExpired:
        timed_out = 1
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, _ = proc.communicate()
        exit_code = -signal.SIGKILL
        stdout = (stdout or "") + f"\nTIMEOUT: killed process group after {timeout_seconds}s\n"
    summary = _read_json(OUTPUT_DIR / f"qmt_roll_stage608_readonly_tick_snapshot_probe_summary_{STAGE608_MODEL_TAG}.json")
    return {
        "command": cmd,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "stdout_tail": (stdout or "")[-4000:],
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": summary,
        "tick_rows": int(len(_read_csv_maybe(READONLY_TICKS_PATH))),
        "symbols": target_symbols,
    }


def _run_stage922(*, data_ready_time: str, as_of: str) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(STAGE922_SCRIPT),
        "--data-ready-time",
        data_ready_time,
    ]
    if as_of:
        cmd.extend(["--as-of", as_of])
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJECT_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    started = datetime.now()
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {
        "command": cmd,
        "exit_code": result.returncode,
        "stdout_tail": result.stdout[-4000:],
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": _parse_json_stdout(result.stdout),
    }


def _run_stage260(
    target_date: str,
    max_snapshot_age_seconds: int,
    *,
    execution_profile: OfficialExecutionProfile,
) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(STAGE260_SCRIPT),
        "--max-snapshot-age-seconds",
        str(max_snapshot_age_seconds),
        "--execution-profile",
        execution_profile.profile_key,
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJECT_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    started = datetime.now()
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {
        "command": cmd,
        "exit_code": result.returncode,
        "stdout_tail": result.stdout[-4000:],
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": _read_json(_stage260_summary_path(target_date)),
    }


def _run_stage251(
    *,
    target_date: str,
    stage260_result: dict[str, Any],
    stage251_mode: str,
    readonly_wrapper: str,
    simnow_front: str,
    wait_seconds: int,
    max_snapshot_age_seconds: int,
    skip_real_block_test: bool,
) -> dict[str, Any]:
    executable_count = _to_int(stage260_result.get("summary", {}).get("executable_count"), 0)
    should_run = stage251_mode == "force" or (stage251_mode == "auto" and executable_count > 0)
    if not should_run:
        return {
            "command": [],
            "exit_code": 0,
            "stdout_tail": "",
            "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {
                "overall_status": "stage251_skipped",
                "skip_reason": f"mode={stage251_mode};stage260_executable_count={executable_count}",
                "total_order_api_called_count": 0,
            },
        }
    cmd = [
        sys.executable,
        str(STAGE251_SCRIPT),
        "--trade-date",
        target_date,
        "--wait-seconds",
        str(wait_seconds),
        "--max-snapshot-age-seconds",
        str(max_snapshot_age_seconds),
        "--simnow-front",
        simnow_front,
        "--readonly-wrapper",
        readonly_wrapper,
    ]
    if skip_real_block_test:
        cmd.append("--skip-real-block-test")
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJECT_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    started = datetime.now()
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {
        "command": cmd,
        "exit_code": result.returncode,
        "stdout_tail": result.stdout[-4000:],
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": _read_json(_stage251_summary_path(target_date)),
    }


def _run_stage904(target_date: str, *, require_broker_fill_price: bool) -> dict[str, Any]:
    config = build_phase_d_config()
    monitor_max_tick_age_seconds = max(
        config.hard_limits.max_tick_age_seconds,
        config.hard_limits.max_controller_cycle_seconds + 15,
    )
    cmd = [
        sys.executable,
        str(STAGE904_SCRIPT),
        "--target-date",
        target_date,
        "--max-tick-age-seconds",
        str(monitor_max_tick_age_seconds),
    ]
    if require_broker_fill_price:
        cmd.append("--require-broker-fill-price")
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJECT_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    started = datetime.now()
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    summary = _read_json(_stage904_summary_path(target_date))
    return {
        "command": cmd,
        "exit_code": result.returncode,
        "stdout_tail": result.stdout[-4000:],
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "monitor_max_tick_age_seconds": monitor_max_tick_age_seconds,
        "summary": summary,
    }


def _skip_stage904_outside_market_session() -> dict[str, Any]:
    now = datetime.now()
    return {
        "command": [],
        "exit_code": 0,
        "stdout_tail": "",
        "started_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "monitor_max_tick_age_seconds": "",
        "summary": {
            "monitor_status": "intraday_monitor_skipped_outside_market_session",
            "action_count": 0,
            "close_dry_run_count": 0,
            "retry_open_dry_run_count": 0,
            "retry_watch_count": 0,
            "order_api_called_count": 0,
        },
    }


def _run_stage904_for_profile(
    profile: OfficialExecutionProfile,
    *,
    target_date: str,
    require_broker_fill_price: bool,
) -> dict[str, Any]:
    if profile.intraday_stop_retry_enabled:
        return _run_stage904(
            target_date,
            require_broker_fill_price=require_broker_fill_price,
        )
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "command": [],
        "exit_code": 0,
        "stdout_tail": "",
        "started_at": now,
        "finished_at": now,
        "monitor_max_tick_age_seconds": "",
        "summary": {
            "execution_profile": profile.profile_key,
            "monitor_status": "intraday_not_applicable_profile_disabled",
            "action_count": 0,
            "close_dry_run_count": 0,
            "retry_open_dry_run_count": 0,
            "retry_watch_count": 0,
            "order_api_called_count": 0,
        },
    }


def _run_stage905(
    target_date: str,
    *,
    execution_profile: OfficialExecutionProfile,
) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(STAGE905_SCRIPT),
        "--target-date",
        target_date,
        "--mode",
        "dry-run",
        "--execution-profile",
        execution_profile.profile_key,
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJECT_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    started = datetime.now()
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    summary = _read_json(_stage905_summary_path(target_date))
    return {
        "command": cmd,
        "exit_code": result.returncode,
        "stdout_tail": result.stdout[-4000:],
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": summary,
    }


def _read_external_intraday_stage(target_date: str, *, stage: str) -> dict[str, Any]:
    """Consume atomically published fast-lane outputs without launching a second monitor."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if stage == "stage904":
        summary = _read_json(_stage904_summary_path(target_date))
        missing_status = "intraday_monitor_external_output_missing"
    elif stage == "stage905":
        summary = _read_json(_stage905_summary_path(target_date))
        missing_status = "executor_external_output_missing"
    else:
        raise ValueError(f"unsupported external intraday stage: {stage}")
    if not summary:
        key = "monitor_status" if stage == "stage904" else "executor_status"
        summary = {key: missing_status, "order_api_called_count": 0}
    return {
        "command": [],
        "exit_code": 0,
        "stdout_tail": "",
        "started_at": now,
        "finished_at": now,
        "summary": summary,
        "external_fast_lane": 1,
    }


def _run_stage906(target_date: str, max_snapshot_age_seconds: int) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(STAGE906_SCRIPT),
        "--target-date",
        target_date,
        "--max-snapshot-age-seconds",
        str(max_snapshot_age_seconds),
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJECT_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    started = datetime.now()
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    summary = _read_json(_stage906_summary_path(target_date))
    return {
        "command": cmd,
        "exit_code": result.returncode,
        "stdout_tail": result.stdout[-4000:],
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": summary,
    }


def _run_stage908(target_date: str, mode: str, confirm_live_real: str) -> dict[str, Any]:
    adapter_mode = "live-real" if mode == "live-real" else "dry-run"
    cmd = [
        sys.executable,
        str(STAGE908_SCRIPT),
        "--target-date",
        target_date,
        "--mode",
        adapter_mode,
    ]
    if adapter_mode == "live-real":
        cmd.extend(["--confirm-live-real", confirm_live_real])
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJECT_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    started = datetime.now()
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {
        "command": cmd,
        "exit_code": result.returncode,
        "stdout_tail": result.stdout[-4000:],
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": _read_json(_stage908_summary_path(target_date)),
    }


def _run_stage923(target_date: str) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(STAGE923_SCRIPT),
        "--target-date",
        target_date,
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJECT_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    started = datetime.now()
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {
        "command": cmd,
        "exit_code": result.returncode,
        "stdout_tail": result.stdout[-4000:],
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": _parse_json_stdout(result.stdout),
    }


def _run_stage924(target_date: str) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(STAGE924_SCRIPT),
        "--target-date",
        target_date,
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJECT_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    started = datetime.now()
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {
        "command": cmd,
        "exit_code": result.returncode,
        "stdout_tail": result.stdout[-4000:],
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": _parse_json_stdout(result.stdout),
    }


def _check_lookup(stage902_summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = stage902_summary.get("blocking_failures", []) or []
    lookup = {str(row.get("check", "")): row for row in rows if isinstance(row, dict)}
    return lookup


def _extract_order_symbols(*frames: pd.DataFrame) -> list[str]:
    symbols: set[str] = set()
    for frame in frames:
        if frame.empty:
            continue
        if "vt_symbol" in frame.columns:
            for value in frame["vt_symbol"].fillna("").astype(str):
                text = value.strip()
                if text:
                    symbols.add(text)
            continue
        if "symbol" in frame.columns and "exchange" in frame.columns:
            symbol_series = frame["symbol"].fillna("").astype(str).str.strip()
            exchange_series = frame["exchange"].fillna("").astype(str).str.strip()
            for symbol, exchange in zip(symbol_series, exchange_series, strict=False):
                if symbol and exchange and "." not in symbol:
                    symbols.add(f"{symbol}.{exchange}")
                elif symbol:
                    symbols.add(symbol)
            continue
        if "symbol" in frame.columns:
            for value in frame["symbol"].fillna("").astype(str):
                text = value.strip()
                if text:
                    symbols.add(text)
    return sorted(symbols)


def _plan_row(step: str, status: str, action: str, reason: str, order_api_called: int = 0) -> dict[str, Any]:
    return {
        "step": step,
        "status": status,
        "action": action,
        "reason": reason,
        "order_api_called": int(order_api_called),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _build_cycle_plan(
    *,
    mode: str,
    target_date: str,
    official_summary: dict[str, Any],
    signal_plan: pd.DataFrame,
    pending_orders: pd.DataFrame,
    current_positions: pd.DataFrame,
    stage909_result: dict[str, Any],
    stage914_result: dict[str, Any],
    stage907_result: dict[str, Any],
    stage260_result: dict[str, Any],
    stage251_result: dict[str, Any],
    stage902_result: dict[str, Any],
    stage904_result: dict[str, Any],
    stage905_result: dict[str, Any],
    stage906_result: dict[str, Any],
    stage908_result: dict[str, Any],
    stage923_result: dict[str, Any],
    stage924_result: dict[str, Any],
    kill_active: bool,
    current_sessions: list[dict[str, Any]],
) -> pd.DataFrame:
    stage902_summary = stage902_result.get("summary", {})
    stage902_blockers = _check_lookup(stage902_summary)
    blocking_count = _to_int(stage902_summary.get("blocking_failure_count"), 999)
    ready_for_real = _to_int(stage902_summary.get("ready_for_phase_d_real"), 0)
    order_api_called = _to_int(stage902_summary.get("order_api_called_count"), 0)
    stage909_summary = stage909_result.get("summary", {})
    stage909_status = str(stage909_summary.get("shadow_refresh_status", ""))
    stage909_mode = str(stage909_summary.get("mode", ""))
    stage914_summary = stage914_result.get("summary", {})
    stage914_status = str(stage914_summary.get("preflight_status", ""))
    stage914_blocking = _to_int(stage914_summary.get("blocking_failure_count"), 999)
    stage914_order_api_called = _to_int(stage914_summary.get("order_api_called_count"), 0)
    stage907_summary = stage907_result.get("summary", {})
    stage907_status = str(stage907_summary.get("refresh_status", ""))
    stage907_mode = str(stage907_summary.get("mode", ""))
    stage907_order_api_called = _to_int(stage907_summary.get("order_api_called_count"), 0)
    stage260_summary = stage260_result.get("summary", {})
    stage260_executable = _to_int(stage260_summary.get("executable_count"), 0)
    stage260_blocked = _to_int(stage260_summary.get("blocked_count"), 0)
    stage260_skipped_flat = _to_int(stage260_summary.get("skipped_flat_count"), 0)
    stage260_skipped_position_mismatch = _to_int(stage260_summary.get("skipped_position_mismatch_count"), 0)
    stage260_order_api_called = _to_int(stage260_summary.get("order_api_called_count"), 0)
    stage251_summary = stage251_result.get("summary", {})
    stage251_status = str(stage251_summary.get("overall_status", ""))
    stage251_order_api_called = _to_int(stage251_summary.get("total_order_api_called_count"), 0)
    stage904_summary = stage904_result.get("summary", {})
    stage904_status = str(stage904_summary.get("monitor_status", ""))
    stage904_order_api_called = _to_int(stage904_summary.get("order_api_called_count"), 0)
    stage904_retry_open_dry_run = _to_int(stage904_summary.get("retry_open_dry_run_count"), 0)
    stage905_summary = stage905_result.get("summary", {})
    stage905_status = str(stage905_summary.get("executor_status", ""))
    stage905_send_called = _to_int(stage905_summary.get("send_order_api_called_count"), 0)
    stage905_cancel_called = _to_int(stage905_summary.get("cancel_order_api_called_count"), 0)
    stage906_summary = stage906_result.get("summary", {})
    stage906_status = str(stage906_summary.get("reconciliation_status", ""))
    stage906_order_api_called = _to_int(stage906_summary.get("order_api_called_count"), 0)
    stage908_summary = stage908_result.get("summary", {})
    stage908_status = str(stage908_summary.get("adapter_contract_status", ""))
    stage908_order_api_called = _to_int(stage908_summary.get("order_api_called_count"), 0)
    stage923_summary = stage923_result.get("summary", {})
    stage923_status = str(stage923_summary.get("incident_status", ""))
    stage923_order_api_called = _to_int(stage923_summary.get("order_api_called_count"), 0)
    stage924_summary = stage924_result.get("summary", {})
    stage924_status = str(stage924_summary.get("recovery_status", ""))
    stage924_order_api_called = _to_int(stage924_summary.get("order_api_called_count"), 0)
    rows: list[dict[str, Any]] = []

    if stage909_status == "shadow_refresh_completed":
        stage909_plan_status = "passed"
    elif stage909_mode == "plan-only":
        stage909_plan_status = "watch"
    else:
        stage909_plan_status = "blocked"
    rows.append(
        _plan_row(
            "shadow_refresh",
            stage909_plan_status,
            "plan or run official data update and profile-bound shadow calculation",
            f"stage909={stage909_status};mode={stage909_mode};attempted={stage909_summary.get('refresh_attempted', '')}",
        )
    )
    rows.append(
        _plan_row(
            "load_official_shadow",
            "passed" if official_summary.get("analysis_end") == target_date else "blocked",
            "load profile-bound official summary/signal/pending/current positions",
            f"analysis_end={official_summary.get('analysis_end', '')};signal={len(signal_plan)};pending={len(pending_orders)};positions={len(current_positions)}",
        )
    )
    rows.append(
        _plan_row(
            "session_window",
            "passed" if current_sessions else "watch",
            "classify current automation session",
            ",".join(row["name"] for row in current_sessions) if current_sessions else "outside configured session",
        )
    )
    rows.append(
        _plan_row(
            "kill_switch",
            "blocked" if kill_active else "passed",
            "stop all submit attempts when kill switch is active",
            "kill switch active" if kill_active else "clear",
        )
    )
    rows.append(
        _plan_row(
            "production_ctp_runtime_preflight",
            "passed" if stage914_status == "production_readonly_preflight_passed" and stage914_blocking == 0 else "blocked",
            "check production live env file and vnpy_ctp framework priority before read-only refresh",
            f"stage914={stage914_status};blocking={stage914_blocking};connect_attempted={stage914_summary.get('connect_attempted', '')}",
            order_api_called=stage914_order_api_called,
        )
    )
    if stage907_status == "readonly_refresh_completed_snapshot_ready":
        stage907_plan_status = "passed"
    elif stage907_mode == "plan-only" and mode != "live-real":
        stage907_plan_status = "watch"
    else:
        stage907_plan_status = "blocked"
    rows.append(
        _plan_row(
            "readonly_refresh",
            stage907_plan_status,
            "plan or run guarded broker read-only refresh before readiness gate",
            f"stage907={stage907_status};mode={stage907_mode};attempted={stage907_summary.get('refresh_attempted', '')}",
            order_api_called=stage907_order_api_called,
        )
    )
    stage260_no_action_idle = (
        stage260_executable == 0
        and stage260_blocked == 0
        and stage260_skipped_flat > 0
        and stage260_skipped_position_mismatch == 0
        and stage260_order_api_called == 0
    )
    if stage260_executable > 0 and stage260_order_api_called == 0:
        stage260_plan_status = "passed"
    elif stage260_no_action_idle:
        stage260_plan_status = "skipped"
    else:
        stage260_plan_status = "blocked"
    rows.append(
        _plan_row(
            "stage260_execution_gate",
            stage260_plan_status,
            "translate official signal into broker-state executable/blocked decision",
            (
                f"executable={stage260_executable};blocked={stage260_blocked};"
                f"skipped_flat={stage260_skipped_flat};"
                f"skipped_position_mismatch={stage260_skipped_position_mismatch}"
            ),
            order_api_called=stage260_order_api_called,
        )
    )
    stage251_legacy_policy = str(stage902_summary.get("legacy_stage251_policy", "optional"))
    if stage251_status == "fresh_pre_submit_gate_passed":
        stage251_plan_status = "passed"
    elif stage251_status == "stage251_skipped" and stage260_executable <= 0:
        stage251_plan_status = "skipped"
    elif stage251_legacy_policy == "optional" and stage251_order_api_called == 0:
        stage251_plan_status = "skipped"
    else:
        stage251_plan_status = "blocked"
    rows.append(
        _plan_row(
            "stage251_fresh_pre_submit_gate",
            stage251_plan_status,
            "legacy SimNow/broker-test pre-submit gate; production live uses current broker/readiness/final-submit gates",
            (
                f"stage251={stage251_status};legacy_policy={stage251_legacy_policy};"
                f"reason={stage251_summary.get('failure_reason', stage251_summary.get('skip_reason', ''))}"
            ),
            order_api_called=stage251_order_api_called,
        )
    )
    rows.append(
        _plan_row(
            "stage902_readiness",
            "passed" if blocking_count == 0 else "blocked",
            "run final Phase D readiness gate",
            f"blocking_failure_count={blocking_count};overall={stage902_summary.get('overall_status', '')}",
            order_api_called=order_api_called,
        )
    )
    rows.append(
        _plan_row(
            "broker_state",
            "blocked" if "broker_readonly_snapshot_fresh" in stage902_blockers else "passed",
            "require fresh broker account/position/order snapshot",
            _clean(stage902_blockers.get("broker_readonly_snapshot_fresh", {}).get("blocker")) or "fresh snapshot gate not blocking",
        )
    )
    rows.append(
        _plan_row(
            "c9_intraday_monitor",
            (
                "skipped"
                if stage904_status
                == "intraday_not_applicable_profile_disabled"
                else "blocked"
                if stage904_status == "intraday_monitor_blocked"
                or "c9_intraday_session_daemon_enabled" in stage902_blockers
                else "passed"
            ),
            (
                "C9 intraday monitor is not applicable to Stage372"
                if stage904_status
                == "intraday_not_applicable_profile_disabled"
                else "monitor C9 0.5R stop/retry during active sessions"
            ),
            (
                f"stage904={stage904_status};"
                f"retry_open_dry_run={stage904_retry_open_dry_run};"
                + (_clean(stage902_blockers.get("c9_intraday_session_daemon_enabled", {}).get("blocker")) or "session daemon gate not blocking")
            ),
            order_api_called=stage904_order_api_called,
        )
    )
    rows.append(
        _plan_row(
            "strategy_submit_adapter",
            "blocked" if "strategy_real_submit_adapter_implemented" in stage902_blockers else "passed",
            "route approved orders to a reviewed vn.py CTP adapter",
            _clean(stage902_blockers.get("strategy_real_submit_adapter_implemented", {}).get("blocker")) or "real adapter gate not blocking",
        )
    )
    rows.append(
        _plan_row(
            "submit",
            "blocked" if stage905_status == "executor_dry_run_blocked" or (mode == "live-real" and ready_for_real != 1) else "dry_run_only",
            "run Stage905 executor dry-run and keep real submit unavailable",
            f"stage905={stage905_status};Stage903 does not call send_order/cancel_order",
            order_api_called=stage905_send_called + stage905_cancel_called,
        )
    )
    rows.append(
        _plan_row(
            "reconcile",
            "passed" if stage906_status == "reconcile_aligned" else "blocked",
            "compare official shadow, executor intents, broker positions/orders/trades",
            f"stage906={stage906_status};alignment={stage906_summary.get('account_state_alignment', '')}",
            order_api_called=stage906_order_api_called,
        )
    )
    rows.append(
        _plan_row(
            "submit_adapter_contract",
            "passed" if stage908_status in {
                "adapter_contract_ready_dry_run",
                "adapter_contract_ready_for_external_live_adapter_review",
                "adapter_contract_no_intents_idle",
            } else "blocked",
            "validate final adapter contract before any real broker integration",
            f"stage908={stage908_status};live_submit_permitted={stage908_summary.get('live_submit_permitted', '')}",
            order_api_called=stage908_order_api_called,
        )
    )
    rows.append(
        _plan_row(
            "fail_closed_incident",
            "passed" if stage923_status in {"phase_d_fail_closed_operator_attention_required", "phase_d_no_incident_monitor_only", "phase_d_no_incident_completion_proven"} else "blocked",
            "produce an auditable operator incident package when Phase D is fail-closed",
            f"stage923={stage923_status};operator_required={stage923_summary.get('operator_action_required', '')}",
            order_api_called=stage923_order_api_called,
        )
    )
    rows.append(
        _plan_row(
            "account_recovery_gate",
            "passed" if stage924_status in {
                "account_recovery_ack_required_fail_closed",
                "account_recovery_manual_keep_fail_closed",
                "account_recovery_manual_action_pending_fail_closed",
                "account_recovery_manual_action_done_rerun_required",
                "account_recovery_non_strategy_position_ack_recorded_fail_closed",
                "account_recovery_not_required_aligned",
            } else "blocked",
            "validate the safe re-entry state after any manual broker account intervention",
            f"stage924={stage924_status};operator_required={stage924_summary.get('operator_action_required', '')}",
            order_api_called=stage924_order_api_called,
        )
    )
    return pd.DataFrame(rows)


def _controller_status(mode: str, kill_active: bool, stage902_result: dict[str, Any], plan: pd.DataFrame) -> str:
    if kill_active:
        return "phase_d_controller_killed"
    if int(stage902_result.get("exit_code", 1)) != 0:
        return "phase_d_controller_readiness_error"
    stage902_summary = stage902_result.get("summary", {})
    blocking_raw = stage902_summary.get("blocking_failure_count")
    ready_real_raw = stage902_summary.get("ready_for_phase_d_real")
    blocking = 999 if blocking_raw is None or blocking_raw == "" else int(blocking_raw)
    ready_real = 0 if ready_real_raw is None or ready_real_raw == "" else int(ready_real_raw)
    plan_blocked = bool(not plan.empty and plan["status"].astype(str).eq("blocked").any())
    if mode == "monitor-only":
        return "phase_d_controller_monitor_only"
    if mode == "dry-run":
        return "phase_d_controller_dry_run_ready_real_disabled" if blocking == 0 and not plan_blocked else "phase_d_controller_dry_run_blocked"
    if ready_real == 1 and not plan_blocked:
        return "phase_d_controller_live_real_ready_no_submit_step"
    return "phase_d_controller_live_real_blocked"


def _write_launchd_template(
    path: Path,
    *,
    mode: str,
    target_date: str,
    target_date_mode: str,
    target_date_data_ready_time: str,
    poll_seconds: int,
) -> None:
    python_path = Path(sys.executable).resolve()
    label = "local.qmt-roll.official-live.phase-d-controller"
    args = [
        str(python_path),
        str(Path(__file__).resolve()),
        "--mode",
        mode,
        "--loop",
        "--poll-seconds",
        str(poll_seconds),
    ]
    if target_date_mode == "latest-completed" and not target_date:
        args.extend(["--target-date-mode", "latest-completed"])
        args.extend(["--target-date-data-ready-time", target_date_data_ready_time])
    elif target_date:
        args.extend(["--target-date", target_date])
    args.extend(
        [
            "--shadow-refresh-mode",
            "auto",
            "--confirm-shadow-refresh",
            PHASE_D_SHADOW_REFRESH_CONFIRM_TEXT,
            "--readonly-refresh-mode",
            "auto",
            "--confirm-readonly-refresh",
            PHASE_D_READONLY_REFRESH_CONFIRM_TEXT,
            "--stage251-mode",
            "skip",
        ]
    )
    arg_lines = "\n".join(f"    <string>{item}</string>" for item in args)
    env_vars = {
        "PYTHONPATH": str(PROJECT_DIR),
        PHASE_D_SESSION_DAEMON_ENV: "1",
        PHASE_D_REAL_ADAPTER_ENV: "1",
        PHASE_D_SHADOW_REFRESH_ENV: "1",
        PHASE_D_READONLY_REFRESH_ENV: "1",
    }
    env_lines = "\n".join(
        f"    <key>{key}</key>\n    <string>{value}</string>" for key, value in env_vars.items()
    )
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{label}</string>
  <key>WorkingDirectory</key>
  <string>{REPO_ROOT}</string>
  <key>ProgramArguments</key>
  <array>
{arg_lines}
  </array>
  <key>EnvironmentVariables</key>
  <dict>
{env_lines}
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>{OUTPUT_DIR / "qmt_roll_official_live_phase_d_controller.launchd.out.log"}</string>
  <key>StandardErrorPath</key>
  <string>{OUTPUT_DIR / "qmt_roll_official_live_phase_d_controller.launchd.err.log"}</string>
</dict>
</plist>
"""
    path.write_text(plist, encoding="utf-8")


def _to_markdown(df: pd.DataFrame, columns: list[str], max_rows: int = 80) -> str:
    if df.empty:
        return "_empty_"
    return df.loc[:, [column for column in columns if column in df.columns]].head(max_rows).to_markdown(index=False)


def _build_report(summary: dict[str, Any], plan: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Stage903 Official Live Phase D Controller",
            "",
            f"- 生成时间：`{summary['generated_at']}`",
            f"- 当前官方实盘：`{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- 运行模式：`{summary['mode']}`",
            f"- 目标日期：`{summary['target_date']}`",
            f"- 目标日期来源：`{summary['target_date_source']}`",
            f"- 控制器状态：`{summary['controller_status']}`",
            f"- 当前 session：`{summary['current_session_names']}`",
            f"- order API 调用次数：`{summary['order_api_called_count']}`",
            f"- Stage608 临近 tick 刷新：`{summary.get('stage608_intraday_tick_status', '')}`，行数 `{summary.get('stage608_intraday_tick_rows', '')}`",
            "",
            "## Cycle Plan",
            "",
            _to_markdown(plan, ["step", "status", "action", "reason", "order_api_called"], max_rows=80),
            "",
            "## 说明",
            "",
            "- Stage903 是常驻控制器骨架：负责心跳、状态、kill switch、readiness gate 和周期计划。",
            "- Stage909 覆盖日终数据更新和当前 execution profile 的官方 shadow 信号计算，默认 `plan-only`。",
            "- Stage903 当前已串联 Stage904 盘中监控、Stage905 executor dry-run 和 Stage906 对账 worker。",
            "- Stage914 在 Stage907 前检查 production-live env 与 vnpy_ctp runtime；预检不通过时只读刷新会降级为 `plan-only`。",
            "- Stage908 覆盖最后一层提交 adapter 合约审计，但不连接 broker、不提交委托。",
            "- Stage907 只读刷新 gate 默认 `plan-only`，只有显式 env gate 和确认文本齐全时才连接 CTP 读快照。",
            "- 本阶段不连接 CTP，不调用 `send_order`，不调用 `cancel_order`。",
            "- 真实执行应在后续独立 executor 中实现，并继续由 Stage902/Stage903 fail-closed 闸门控制。",
            "",
        ]
    )


def run_once(args: argparse.Namespace) -> dict[str, Any]:
    config = build_phase_d_config()
    execution_profile = resolve_execution_profile(
        getattr(
            args,
            "execution_profile",
            ExecutionStrategyMode.C9_15W_HISTORICAL.value,
        )
    )
    now = datetime.now()
    run_id = now.strftime("%Y%m%d_%H%M%S")
    paths = _paths(run_id)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    official_summary = _read_json(execution_profile.summary_path)
    target_resolver_result: dict[str, Any] = {
        "command": [],
        "exit_code": 0,
        "stdout_tail": "",
        "summary": {
            "resolver_status": "target_date_resolver_skipped",
            "resolved_target_date": "",
            "requires_shadow_refresh": "",
            "requires_data_update": "",
            "order_api_called_count": 0,
        },
    }
    if args.target_date:
        target_date = args.target_date
        target_date_source = "explicit_cli_target_date"
    elif args.target_date_mode == "latest-completed":
        target_resolver_result = _run_stage922(
            data_ready_time=args.target_date_data_ready_time,
            as_of=args.target_date_as_of,
        )
        target_date = _clean(target_resolver_result.get("summary", {}).get("resolved_target_date")) or str(
            official_summary.get("analysis_end", "")
        )
        target_date_source = "stage922_latest_completed_trading_day"
    else:
        target_date = str(official_summary.get("analysis_end", ""))
        target_date_source = "official_summary_analysis_end"
    resolver_summary = target_resolver_result.get("summary", {})
    effective_shadow_refresh_mode = args.shadow_refresh_mode
    if args.shadow_refresh_mode == "auto":
        resolver_needs_refresh = (
            _to_int(resolver_summary.get("requires_shadow_refresh"), 0) == 1
            or _to_int(resolver_summary.get("requires_data_update"), 0) == 1
        )
        official_target_mismatch = str(official_summary.get("analysis_end", "")) != target_date
        effective_shadow_refresh_mode = "run" if resolver_needs_refresh or official_target_mismatch else "plan-only"
    stage909_result = _run_stage909(
        execution_profile=execution_profile,
        target_date=target_date,
        shadow_refresh_mode=effective_shadow_refresh_mode,
        analysis_start=args.shadow_analysis_start,
        mapping_start=args.shadow_mapping_start,
        bar_start=args.shadow_bar_start,
        confirm_shadow_refresh=args.confirm_shadow_refresh,
    )
    official_summary = _read_json(execution_profile.summary_path)
    signal_plan = _read_csv_maybe(execution_profile.signal_plan_path)
    pending_orders = _read_csv_maybe(execution_profile.pending_orders_path)
    current_positions = _read_csv_maybe(
        execution_profile.current_positions_path
    )
    readonly_summary = _read_json(READONLY_SUMMARY_PATH)
    kill_active, kill_payload = _kill_switch_active()
    sessions = _current_sessions(now)
    market_execution_session_active = any(
        _clean(session.get("role")) == "market_and_execution" for session in sessions
    )

    stage914_result = _run_stage914(
        wait_seconds=args.readonly_wait_seconds,
        execution_profile=execution_profile,
    )
    stage914_ready = _stage914_result_ready(
        stage914_result,
        execution_profile=execution_profile,
    )
    readonly_age = _age_seconds(readonly_summary.get("generated_at"), now)
    broker_snapshot = readonly_summary.get("broker_snapshot", {}) if isinstance(readonly_summary.get("broker_snapshot"), dict) else {}
    readonly_snapshot_usable = readonly_summary.get("status") == "readonly_snapshots_received" and _clean(
        broker_snapshot.get("position_snapshot_state")
    ) in {"confirmed_flat", "positions_received"}
    config = build_phase_d_config()
    readonly_refresh_headroom_seconds = max(
        60,
        int(args.readonly_wait_seconds) + int(config.hard_limits.max_controller_cycle_seconds) + 30,
    )
    readonly_refresh_age_limit_seconds = max(
        0,
        int(args.max_snapshot_age_seconds) - int(readonly_refresh_headroom_seconds),
    )
    readonly_stale = (
        readonly_age is None
        or readonly_age > readonly_refresh_age_limit_seconds
        or not readonly_snapshot_usable
    )
    if not stage914_ready:
        effective_readonly_refresh_mode = "plan-only"
    elif args.readonly_refresh_mode == "auto":
        effective_readonly_refresh_mode = "refresh" if readonly_stale and market_execution_session_active else "plan-only"
    else:
        effective_readonly_refresh_mode = args.readonly_refresh_mode
    stage907_result = _run_stage907(
        refresh_mode=effective_readonly_refresh_mode,
        env_profile=args.readonly_env_profile,
        wait_seconds=args.readonly_wait_seconds,
        confirm_readonly_refresh=args.confirm_readonly_refresh,
    )
    stage260_result = _run_stage260(
        target_date=target_date,
        max_snapshot_age_seconds=args.max_snapshot_age_seconds,
        execution_profile=execution_profile,
    )
    stage251_result = _run_stage251(
        target_date=target_date,
        stage260_result=stage260_result,
        stage251_mode=args.stage251_mode,
        readonly_wrapper=args.stage251_readonly_wrapper,
        simnow_front=args.stage251_simnow_front,
        wait_seconds=args.stage251_wait_seconds,
        max_snapshot_age_seconds=args.max_snapshot_age_seconds,
        skip_real_block_test=args.stage251_skip_real_block_test,
    )
    stage902_result = _run_stage902(
        target_date=target_date,
        mode=args.mode,
        max_snapshot_age_seconds=args.max_snapshot_age_seconds,
        confirm_live_real=args.confirm_live_real,
        execution_profile=execution_profile,
    )
    broker_positions = _read_csv_maybe(READONLY_POSITIONS_PATH)
    broker_trades = _read_csv_maybe(READONLY_TRADES_PATH)
    symbols = _extract_order_symbols(signal_plan, pending_orders, current_positions, broker_positions, broker_trades)
    effective_intraday_refresh_mode = (
        "skip" if args.intraday_execution_mode == "external" else args.intraday_tick_refresh_mode
    )
    stage608_intraday_result = _run_stage608_intraday_tick_refresh(
        symbols=symbols,
        refresh_mode=effective_intraday_refresh_mode if market_execution_session_active else "skip",
        wait_seconds=args.intraday_tick_wait_seconds,
        pre_subscribe_wait_seconds=args.intraday_pre_subscribe_wait_seconds,
        stage914_ready=stage914_ready,
    )
    if not execution_profile.intraday_stop_retry_enabled:
        stage904_result = _run_stage904_for_profile(
            execution_profile,
            target_date=target_date,
            require_broker_fill_price=False,
        )
        stage905_result = _run_stage905(
            target_date=target_date,
            execution_profile=execution_profile,
        )
    elif args.intraday_execution_mode == "external":
        stage904_result = _read_external_intraday_stage(target_date, stage="stage904")
        stage905_result = _read_external_intraday_stage(target_date, stage="stage905")
    elif market_execution_session_active:
        stage904_result = _run_stage904_for_profile(
            execution_profile,
            target_date=target_date,
            require_broker_fill_price=args.mode == "live-real",
        )
        stage905_result = _run_stage905(
            target_date=target_date,
            execution_profile=execution_profile,
        )
    else:
        stage904_result = _skip_stage904_outside_market_session()
        stage905_result = _run_stage905(
            target_date=target_date,
            execution_profile=execution_profile,
        )
    stage906_max_snapshot_age_seconds = (
        int(args.reconciliation_max_snapshot_age_seconds)
        if int(args.reconciliation_max_snapshot_age_seconds) > 0
        else int(args.max_snapshot_age_seconds)
    )
    stage906_result = _run_stage906(
        target_date=target_date,
        max_snapshot_age_seconds=stage906_max_snapshot_age_seconds,
    )
    stage908_result = _run_stage908(
        target_date=target_date,
        mode=args.mode,
        confirm_live_real=args.confirm_live_real,
    )
    stage923_result = _run_stage923(target_date=target_date)
    stage924_result = _run_stage924(target_date=target_date)
    plan = _build_cycle_plan(
        mode=args.mode,
        target_date=target_date,
        official_summary=official_summary,
        signal_plan=signal_plan,
        pending_orders=pending_orders,
        current_positions=current_positions,
        stage909_result=stage909_result,
        stage914_result=stage914_result,
        stage907_result=stage907_result,
        stage260_result=stage260_result,
        stage251_result=stage251_result,
        stage902_result=stage902_result,
        stage904_result=stage904_result,
        stage905_result=stage905_result,
        stage906_result=stage906_result,
        stage908_result=stage908_result,
        stage923_result=stage923_result,
        stage924_result=stage924_result,
        kill_active=kill_active,
        current_sessions=sessions,
    )
    controller_status = _controller_status(args.mode, kill_active, stage902_result, plan)
    order_api_called = int(plan["order_api_called"].sum()) if not plan.empty else 0
    current_session_names = ",".join(row["name"] for row in sessions) if sessions else ""

    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": args.mode,
        "target_date": target_date,
        "target_date_mode": args.target_date_mode,
        "target_date_source": target_date_source,
        "stage922_exit_code": target_resolver_result.get("exit_code"),
        "stage922_resolver_status": target_resolver_result.get("summary", {}).get("resolver_status", ""),
        "stage922_requires_shadow_refresh": target_resolver_result.get("summary", {}).get("requires_shadow_refresh", ""),
        "stage922_requires_data_update": target_resolver_result.get("summary", {}).get("requires_data_update", ""),
        "execution_profile": execution_profile.profile_key,
        "official_live_version": execution_profile.official_version,
        "official_live_alias": execution_profile.alias,
        "capital": execution_profile.capital,
        "capital_label": execution_profile.capital_label,
        "controller_status": controller_status,
        "current_sessions": sessions,
        "current_session_names": current_session_names,
        "signal_count": int(len(signal_plan)),
        "pending_order_count": int(len(pending_orders)),
        "current_position_count": int(len(current_positions)),
        "watched_symbols": symbols,
        "kill_switch_active": kill_active,
        "kill_switch_payload": kill_payload,
        "readonly_status": readonly_summary.get("status", ""),
        "stage909_exit_code": stage909_result.get("exit_code"),
        "stage909_shadow_refresh_status": stage909_result.get("summary", {}).get("shadow_refresh_status", ""),
        "stage909_refresh_attempted": stage909_result.get("summary", {}).get("refresh_attempted", ""),
        "stage909_requested_shadow_refresh_mode": args.shadow_refresh_mode,
        "stage909_effective_shadow_refresh_mode": effective_shadow_refresh_mode,
        "stage907_exit_code": stage907_result.get("exit_code"),
        "stage914_exit_code": stage914_result.get("exit_code"),
        "stage914_preflight_status": stage914_result.get("summary", {}).get("preflight_status", ""),
        "stage914_blocking_failure_count": stage914_result.get("summary", {}).get("blocking_failure_count", ""),
        "stage914_order_api_called_count": stage914_result.get("summary", {}).get("order_api_called_count", ""),
        "stage907_refresh_status": stage907_result.get("summary", {}).get("refresh_status", ""),
        "stage907_refresh_attempted": stage907_result.get("summary", {}).get("refresh_attempted", ""),
        "stage907_env_profile": stage907_result.get("summary", {}).get("env_profile", ""),
        "stage907_readonly_status_after": stage907_result.get("summary", {}).get("readonly_status_after", ""),
        "stage907_position_snapshot_state_after": stage907_result.get("summary", {}).get("position_snapshot_state_after", ""),
        "stage907_requested_refresh_mode": args.readonly_refresh_mode,
        "stage907_effective_refresh_mode": effective_readonly_refresh_mode,
        "stage907_readonly_age_seconds_before_refresh": readonly_age,
        "stage907_readonly_refresh_headroom_seconds": readonly_refresh_headroom_seconds,
        "stage907_readonly_refresh_age_limit_seconds": readonly_refresh_age_limit_seconds,
        "stage907_readonly_stale_before_refresh": int(bool(readonly_stale)),
        "stage260_exit_code": stage260_result.get("exit_code"),
        "stage260_executable_count": stage260_result.get("summary", {}).get("executable_count", ""),
        "stage260_blocked_count": stage260_result.get("summary", {}).get("blocked_count", ""),
        "stage260_skipped_flat_count": stage260_result.get("summary", {}).get("skipped_flat_count", ""),
        "stage260_skipped_position_mismatch_count": stage260_result.get("summary", {}).get("skipped_position_mismatch_count", ""),
        "stage260_order_api_called_count": stage260_result.get("summary", {}).get("order_api_called_count", ""),
        "stage251_exit_code": stage251_result.get("exit_code"),
        "stage251_overall_status": stage251_result.get("summary", {}).get("overall_status", ""),
        "stage251_order_api_called_count": stage251_result.get("summary", {}).get("total_order_api_called_count", ""),
        "stage902_exit_code": stage902_result.get("exit_code"),
        "stage902_overall_status": stage902_result.get("summary", {}).get("overall_status", ""),
        "stage902_blocking_failure_count": stage902_result.get("summary", {}).get("blocking_failure_count", ""),
        "stage608_intraday_tick_exit_code": stage608_intraday_result.get("exit_code"),
        "stage608_intraday_tick_status": stage608_intraday_result.get("summary", {}).get("status", ""),
        "stage608_intraday_tick_rows": stage608_intraday_result.get("tick_rows", ""),
        "stage608_intraday_tick_symbols": stage608_intraday_result.get("symbols", []),
        "stage608_intraday_tick_timed_out": stage608_intraday_result.get("timed_out", 0),
        "stage904_exit_code": stage904_result.get("exit_code"),
        "stage904_monitor_status": stage904_result.get("summary", {}).get("monitor_status", ""),
        "stage904_close_dry_run_count": stage904_result.get("summary", {}).get("close_dry_run_count", 0),
        "stage904_retry_open_dry_run_count": stage904_result.get("summary", {}).get("retry_open_dry_run_count", 0),
        "stage904_retry_watch_count": stage904_result.get("summary", {}).get("retry_watch_count", 0),
        "stage905_exit_code": stage905_result.get("exit_code"),
        "stage905_executor_status": stage905_result.get("summary", {}).get("executor_status", ""),
        "stage905_ready_count": stage905_result.get("summary", {}).get("ready_count", 0),
        "stage905_blocked_count": stage905_result.get("summary", {}).get("blocked_count", 0),
        "send_order_api_called_count": stage905_result.get("summary", {}).get("send_order_api_called_count", ""),
        "cancel_order_api_called_count": stage905_result.get("summary", {}).get("cancel_order_api_called_count", ""),
        "stage906_exit_code": stage906_result.get("exit_code"),
        "stage906_reconciliation_status": stage906_result.get("summary", {}).get("reconciliation_status", ""),
        "stage906_account_state_alignment": stage906_result.get("summary", {}).get("account_state_alignment", ""),
        "stage906_blocking_failure_count": stage906_result.get("summary", {}).get("blocking_failure_count", ""),
        "stage906_max_snapshot_age_seconds": stage906_max_snapshot_age_seconds,
        "stage908_exit_code": stage908_result.get("exit_code"),
        "stage908_adapter_contract_status": stage908_result.get("summary", {}).get("adapter_contract_status", ""),
        "stage908_live_submit_permitted": stage908_result.get("summary", {}).get("live_submit_permitted", ""),
        "stage908_blocking_failure_count": stage908_result.get("summary", {}).get("blocking_failure_count", ""),
        "stage923_exit_code": stage923_result.get("exit_code"),
        "stage923_incident_status": stage923_result.get("summary", {}).get("incident_status", ""),
        "stage923_operator_action_required": stage923_result.get("summary", {}).get("operator_action_required", ""),
        "stage924_exit_code": stage924_result.get("exit_code"),
        "stage924_recovery_status": stage924_result.get("summary", {}).get("recovery_status", ""),
        "stage924_operator_action_required": stage924_result.get("summary", {}).get("operator_action_required", ""),
        "order_api_called_count": order_api_called,
        "env_gates": {
            PHASE_D_SESSION_DAEMON_ENV: _env_enabled(PHASE_D_SESSION_DAEMON_ENV),
            PHASE_D_REAL_ADAPTER_ENV: _env_enabled(PHASE_D_REAL_ADAPTER_ENV),
            PHASE_D_REAL_ENABLED_ENV: _env_enabled(PHASE_D_REAL_ENABLED_ENV),
            PHASE_D_READONLY_REFRESH_ENV: _env_enabled(PHASE_D_READONLY_REFRESH_ENV),
            PHASE_D_SHADOW_REFRESH_ENV: _env_enabled(PHASE_D_SHADOW_REFRESH_ENV),
            "confirm_live_real_ok": args.confirm_live_real == PHASE_D_CONFIRM_TEXT,
            "confirm_readonly_refresh_ok": args.confirm_readonly_refresh == PHASE_D_READONLY_REFRESH_CONFIRM_TEXT,
            "confirm_shadow_refresh_ok": args.confirm_shadow_refresh == PHASE_D_SHADOW_REFRESH_CONFIRM_TEXT,
        },
        "phase_d_config": phase_d_config_to_dict(config),
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "stage922_command": target_resolver_result.get("command", []),
        "stage909_command": stage909_result.get("command", []),
        "stage902_command": stage902_result.get("command", []),
        "stage914_command": stage914_result.get("command", []),
        "stage907_command": stage907_result.get("command", []),
        "stage260_command": stage260_result.get("command", []),
        "stage251_command": stage251_result.get("command", []),
        "stage608_intraday_tick_command": stage608_intraday_result.get("command", []),
        "stage904_command": stage904_result.get("command", []),
        "stage905_command": stage905_result.get("command", []),
        "stage906_command": stage906_result.get("command", []),
        "stage908_command": stage908_result.get("command", []),
        "stage923_command": stage923_result.get("command", []),
        "stage924_command": stage924_result.get("command", []),
        "judgement": {
            "external_research_conclusion": (
                "vn.py is event-driven and exposes send_order/cancel_order through MainEngine; "
                "FIA/FCA/CFTC guidance supports local pre-trade controls, throttles, kill switch, "
                "continuity, and reconciliation before unattended trading."
            ),
            "overfit_before": "否。Stage903 是执行控制器，不改策略参数、品种、方向、R倍数或回测样本。",
            "continue_before": "是。Phase D 必须先有常驻控制面，否则无法自动化心跳、熔断和对账。",
            "overfit_after": "否。输出只是控制状态和 readiness 结果，不反向影响策略。",
            "continue_after": "是。下一步应把 broker read-only refresh 与 Stage260/251 串入 controller，再做真实 executor dry-run adapter review。",
        },
    }
    heartbeat = {
        "heartbeat_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "controller_status": controller_status,
        "mode": args.mode,
        "target_date": target_date,
        "target_date_mode": args.target_date_mode,
        "target_date_source": target_date_source,
        "current_session_names": current_session_names,
        "order_api_called_count": order_api_called,
        "kill_switch_active": kill_active,
        "watched_symbols": symbols,
        "summary_path": str(paths["summary_json"].resolve()),
    }

    plan.to_csv(paths["cycle_plan_csv"], index=False, encoding="utf-8-sig")
    _write_json(paths["summary_json"], summary)
    _write_json(paths["heartbeat_json"], heartbeat)
    _write_json(paths["state_json"], summary)
    paths["report_md"].write_text(_build_report(summary, plan), encoding="utf-8")
    _append_events(
        paths["event_log_ndjson"],
        [
            {
                "event_type": "phase_d_controller_cycle",
                "run_id": run_id,
                "controller_status": controller_status,
                "target_date": target_date,
                "order_api_called_count": order_api_called,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            *[
                {
                    "event_type": "phase_d_controller_step",
                    "run_id": run_id,
                    **row,
                }
                for row in plan.to_dict(orient="records")
            ],
        ],
    )
    if args.write_launchd_template:
        _write_launchd_template(
            paths["launchd_plist"],
            mode="dry-run" if args.mode == "monitor-only" else args.mode,
            target_date="" if args.target_date_mode == "latest-completed" and not args.target_date else target_date,
            target_date_mode=args.target_date_mode,
            target_date_data_ready_time=args.target_date_data_ready_time,
            poll_seconds=args.poll_seconds,
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live Phase D controller scaffold.")
    parser.add_argument(
        "--execution-profile",
        choices=[item.value for item in ExecutionStrategyMode],
        default=ExecutionStrategyMode.STAGE372_20W.value,
    )
    parser.add_argument("--target-date", default="", help="Target completed trading day. Defaults to official summary analysis_end.")
    parser.add_argument(
        "--target-date-mode",
        choices=["official-summary", "latest-completed"],
        default="official-summary",
        help="When --target-date is omitted, resolve from official summary or Stage922 latest-completed resolver.",
    )
    parser.add_argument("--target-date-data-ready-time", default="16:30")
    parser.add_argument("--target-date-as-of", default="")
    parser.add_argument("--mode", choices=["monitor-only", "dry-run", "live-real"], default="dry-run")
    parser.add_argument("--max-snapshot-age-seconds", type=int, default=300)
    parser.add_argument(
        "--reconciliation-max-snapshot-age-seconds",
        type=int,
        default=0,
        help=(
            "Optional Stage906-only snapshot age. Use only for post-close preview reconciliation; "
            "0 keeps the normal --max-snapshot-age-seconds fresh-submit policy."
        ),
    )
    parser.add_argument("--confirm-live-real", default="")
    parser.add_argument("--shadow-refresh-mode", choices=["plan-only", "run", "auto"], default="plan-only")
    parser.add_argument("--shadow-analysis-start", default="")
    parser.add_argument("--shadow-mapping-start", default="")
    parser.add_argument("--shadow-bar-start", default="")
    parser.add_argument("--confirm-shadow-refresh", default="")
    parser.add_argument("--readonly-refresh-mode", choices=["plan-only", "refresh", "auto"], default="plan-only")
    parser.add_argument("--readonly-env-profile", choices=["production-live", "simnow", "broker-test"], default="production-live")
    parser.add_argument("--readonly-wait-seconds", type=int, default=30)
    parser.add_argument("--confirm-readonly-refresh", default="")
    parser.add_argument("--stage251-mode", choices=["skip", "auto", "force"], default="skip")
    parser.add_argument("--stage251-readonly-wrapper", choices=["simnow", "broker-test"], default="simnow")
    parser.add_argument("--stage251-simnow-front", default=os.getenv("SIMNOW_FRONT", "trading"))
    parser.add_argument("--stage251-wait-seconds", type=int, default=90)
    parser.add_argument("--stage251-skip-real-block-test", action="store_true")
    parser.add_argument("--intraday-tick-refresh-mode", choices=["skip", "refresh"], default="refresh")
    parser.add_argument(
        "--intraday-execution-mode",
        choices=["integrated", "external"],
        default="integrated",
        help="external lets Stage930 own the single fast Stage904/905 lane.",
    )
    parser.add_argument("--intraday-tick-wait-seconds", type=int, default=8)
    parser.add_argument("--intraday-pre-subscribe-wait-seconds", type=int, default=2)
    parser.add_argument("--loop", action="store_true", help="Run continuously with heartbeat updates.")
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--write-launchd-template", action="store_true")
    args = parser.parse_args()

    if args.loop:
        while True:
            summary = run_once(args)
            print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
            time.sleep(max(5, int(args.poll_seconds)))
    else:
        summary = run_once(args)
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
