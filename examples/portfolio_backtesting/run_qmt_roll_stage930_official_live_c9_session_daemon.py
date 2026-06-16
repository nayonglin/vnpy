from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_CURRENT_POSITIONS_PATH,
    OFFICIAL_LIVE_SIGNAL_PLAN_PATH,
    OFFICIAL_LIVE_SUMMARY_PATH,
    OFFICIAL_LIVE_VERSION,
)
from qmt_roll_official_live_phase_d_config import (
    PHASE_D_CONFIRM_TEXT,
    PHASE_D_READONLY_REFRESH_CONFIRM_TEXT,
    PHASE_D_READONLY_REFRESH_ENV,
    PHASE_D_REAL_ADAPTER_ENV,
    PHASE_D_REAL_ENABLED_ENV,
    PHASE_D_SESSION_DAEMON_ENV,
    PHASE_D_SHADOW_REFRESH_CONFIRM_TEXT,
    PHASE_D_SHADOW_REFRESH_ENV,
    READONLY_TICKS_PATH,
    STAGE901_PENDING_ORDERS_PATH,
    build_phase_d_config,
)
from qmt_roll_official_live_email_notify import send_official_live_email_notification
from run_qmt_alignment_backtest import OUTPUT_DIR


PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent.parent
PYTHON_PATH = REPO_ROOT / ".py311/bin/python"
STAGE903_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage903_official_live_phase_d_controller.py"
STAGE608_SCRIPT = PROJECT_DIR / "run_ctp_stage608_readonly_tick_snapshot_probe.py"
STAGE927_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage927_official_live_real_submit_arming_gate.py"
STAGE931_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage931_official_live_ctp_submit_adapter.py"

MODEL_TAG = "stage930_official_live_c9_session_daemon_v1"
OUTPUT_PREFIX = "qmt_roll_stage930_official_live_c9_session_daemon"
LATEST_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_official_live_c9_session_daemon_latest_summary.json"
LATEST_REPORT_PATH = OUTPUT_DIR / "qmt_roll_official_live_c9_session_daemon_latest_report.md"
LATEST_HEARTBEAT_PATH = OUTPUT_DIR / "qmt_roll_official_live_c9_session_daemon_heartbeat.json"
LATEST_EVENT_LOG_PATH = OUTPUT_DIR / "qmt_roll_official_live_c9_session_daemon_events.ndjson"
LOCK_PATH = OUTPUT_DIR / "qmt_roll_official_live_c9_session_daemon.lock"
EMAIL_THROTTLE_PATH = OUTPUT_DIR / "qmt_roll_stage930_official_live_email_throttle.json"


def _paths(run_id: str) -> dict[str, Path]:
    return {
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{run_id}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{run_id}_{MODEL_TAG}.md",
        "events_ndjson": OUTPUT_DIR / f"{OUTPUT_PREFIX}_events_{run_id}_{MODEL_TAG}.ndjson",
        "command_log": OUTPUT_DIR / f"{OUTPUT_PREFIX}_command_log_{run_id}_{MODEL_TAG}.log",
    }


def _read_csv_maybe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except Exception:
        return pd.DataFrame()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _to_int(value: Any, default: int = 0) -> int:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return int(number)


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _shell_python_command(script: Path, args: list[str]) -> list[str]:
    env_file = PROJECT_DIR / "ctp_live.local.env"
    framework_dir = REPO_ROOT / ".py311/lib/python3.11/site-packages/vnpy_ctp/api/libs"
    py311_lib = REPO_ROOT / ".py311/lib"
    command = " ".join([shlex.quote(str(PYTHON_PATH)), shlex.quote(str(script)), *[shlex.quote(str(item)) for item in args]])
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


def _acquire_singleton_lock() -> Any | None:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = LOCK_PATH.open("w", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    handle.write(f"pid={os.getpid()} started_at={datetime.now():%Y-%m-%d %H:%M:%S}\n")
    handle.flush()
    return handle


def _run_command(cmd: list[str], *, timeout_seconds: int, log_path: Path, label: str) -> dict[str, Any]:
    started = datetime.now()
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=os.environ.copy(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout_seconds,
        check=False,
    )
    finished = datetime.now()
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n===== {label} started_at={started:%Y-%m-%d %H:%M:%S} exit={result.returncode} =====\n")
        handle.write(result.stdout)
        handle.write("\n")
    return {
        "label": label,
        "command": cmd,
        "exit_code": result.returncode,
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": finished.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_seconds": round((finished - started).total_seconds(), 3),
        "stdout_tail": result.stdout[-4000:],
    }


def _extract_json_from_stdout(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        return {}
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    start = stripped.rfind("\n{")
    if start >= 0:
        try:
            return json.loads(stripped[start + 1 :])
        except json.JSONDecodeError:
            return {}
    return {}


def _symbols_from_frame(frame: pd.DataFrame) -> list[str]:
    symbols: list[str] = []
    if frame.empty:
        return symbols
    for column in ("vt_symbol", "contract_vt_symbol"):
        if column not in frame.columns:
            continue
        for item in frame[column].dropna().astype(str):
            text = _clean(item)
            if text:
                symbols.append(text)
    return symbols


def _watched_symbols(extra_symbols: list[str]) -> list[str]:
    symbols: list[str] = []
    for item in extra_symbols:
        text = _clean(item)
        if text:
            symbols.append(text)
    for path in (STAGE901_PENDING_ORDERS_PATH, OFFICIAL_LIVE_SIGNAL_PLAN_PATH, OFFICIAL_LIVE_CURRENT_POSITIONS_PATH):
        symbols.extend(_symbols_from_frame(_read_csv_maybe(path)))
    seen: set[str] = set()
    result: list[str] = []
    for symbol in symbols:
        if symbol in seen:
            continue
        seen.add(symbol)
        result.append(symbol)
    return result


def _run_tick_refresh(args: argparse.Namespace, target_date: str, symbols: list[str], paths: dict[str, Path]) -> dict[str, Any]:
    if args.tick_refresh_mode == "skip":
        return {"refresh_status": "tick_refresh_skipped", "exit_code": 0, "symbols": symbols}
    stage_args = [
        "--wait-seconds",
        str(args.tick_wait_seconds),
        "--pre-subscribe-wait-seconds",
        str(args.pre_subscribe_wait_seconds),
        "--submit-plan",
        str(OUTPUT_DIR / "__nonexistent_stage930_submit_plan.csv"),
    ]
    for symbol in symbols:
        stage_args.extend(["--vt-symbol", symbol])
    if args.tick_refresh_mode == "refresh":
        stage_args.insert(0, "--connect")
        cmd = _shell_python_command(STAGE608_SCRIPT, stage_args)
    else:
        cmd = [str(PYTHON_PATH), str(STAGE608_SCRIPT), *stage_args]
    result = _run_command(
        cmd,
        timeout_seconds=max(30, args.pre_subscribe_wait_seconds + args.tick_wait_seconds + 60),
        log_path=paths["command_log"],
        label=f"stage608_tick_refresh_{target_date}",
    )
    summary = _read_json(OUTPUT_DIR / "qmt_roll_stage608_readonly_tick_snapshot_probe_summary_stage608_readonly_tick_snapshot_probe_v1.json")
    tick_rows = len(_read_csv_maybe(READONLY_TICKS_PATH))
    return {
        **result,
        "refresh_status": summary.get("status", "tick_refresh_unknown"),
        "summary": summary,
        "symbols": symbols,
        "tick_rows": tick_rows,
        "tick_path": str(READONLY_TICKS_PATH.resolve()),
    }


def _run_stage903(args: argparse.Namespace, target_date: str, paths: dict[str, Path]) -> dict[str, Any]:
    cmd = [
        str(PYTHON_PATH),
        str(STAGE903_SCRIPT),
        "--mode",
        args.mode,
        "--shadow-refresh-mode",
        args.shadow_refresh_mode,
        "--confirm-shadow-refresh",
        PHASE_D_SHADOW_REFRESH_CONFIRM_TEXT,
        "--readonly-refresh-mode",
        args.readonly_refresh_mode,
        "--readonly-env-profile",
        "production-live",
        "--readonly-wait-seconds",
        str(args.readonly_wait_seconds),
        "--confirm-readonly-refresh",
        PHASE_D_READONLY_REFRESH_CONFIRM_TEXT,
        "--stage251-mode",
        args.stage251_mode,
        "--max-snapshot-age-seconds",
        str(args.max_snapshot_age_seconds),
    ]
    if target_date:
        cmd.extend(["--target-date", target_date])
    else:
        cmd.extend(["--target-date-mode", "latest-completed"])
    if args.mode == "live-real":
        cmd.extend(["--confirm-live-real", args.confirm_live_real])
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJECT_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    env[PHASE_D_SHADOW_REFRESH_ENV] = "1"
    env[PHASE_D_READONLY_REFRESH_ENV] = "1"
    env[PHASE_D_SESSION_DAEMON_ENV] = "1"
    if args.mode == "live-real":
        env[PHASE_D_REAL_ADAPTER_ENV] = "1"
        if args.confirm_live_real == PHASE_D_CONFIRM_TEXT:
            env[PHASE_D_REAL_ENABLED_ENV] = os.getenv(PHASE_D_REAL_ENABLED_ENV, "")
    else:
        env[PHASE_D_REAL_ADAPTER_ENV] = "1"
        env.pop(PHASE_D_REAL_ENABLED_ENV, None)
    started = datetime.now()
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=args.controller_timeout_seconds,
        check=False,
    )
    finished = datetime.now()
    with paths["command_log"].open("a", encoding="utf-8") as handle:
        handle.write(f"\n===== stage903_controller started_at={started:%Y-%m-%d %H:%M:%S} exit={result.returncode} =====\n")
        handle.write(result.stdout)
        handle.write("\n")
    summary = _extract_json_from_stdout(result.stdout)
    return {
        "exit_code": result.returncode,
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": finished.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_seconds": round((finished - started).total_seconds(), 3),
        "summary": summary,
    }


def _run_stage927(args: argparse.Namespace, target_date: str, paths: dict[str, Path]) -> dict[str, Any]:
    cmd = [str(PYTHON_PATH), str(STAGE927_SCRIPT), "--target-date", target_date, "--confirm-live-real", args.confirm_live_real]
    result = _run_command(cmd, timeout_seconds=120, log_path=paths["command_log"], label=f"stage927_arming_{target_date}")
    path = OUTPUT_DIR / f"qmt_roll_stage927_official_live_real_submit_arming_gate_summary_{target_date.replace('-', '')}_stage927_official_live_real_submit_arming_gate_v1.json"
    return {**result, "summary": _read_json(path)}


def _run_stage931(args: argparse.Namespace, target_date: str, paths: dict[str, Path]) -> dict[str, Any]:
    if args.submit_mode != "live-real":
        return {"submit_status": "submit_adapter_skipped", "exit_code": 0}
    stage_args = [
        "--target-date",
        target_date,
        "--mode",
        "live-real",
        "--confirm-live-real",
        args.confirm_live_real,
        "--max-orders",
        str(args.max_submit_orders),
        "--fill-wait-seconds",
        str(args.fill_wait_seconds),
    ]
    cmd = _shell_python_command(STAGE931_SCRIPT, stage_args)
    result = _run_command(cmd, timeout_seconds=args.submit_timeout_seconds, log_path=paths["command_log"], label=f"stage931_submit_{target_date}")
    summary_path = OUTPUT_DIR / f"qmt_roll_stage931_official_live_ctp_submit_adapter_summary_{target_date.replace('-', '')}_stage931_official_live_ctp_submit_adapter_v1.json"
    return {**result, "summary": _read_json(summary_path)}


def _current_session_names() -> str:
    config = build_phase_d_config()
    now = datetime.now().time()
    names: list[str] = []
    for session in config.sessions:
        start_h, start_m = [int(part) for part in session.start.split(":", 1)]
        end_h, end_m = [int(part) for part in session.end.split(":", 1)]
        start = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
        end = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
        if start <= end:
            active = start <= now <= end
        else:
            active = now >= start or now <= end
        if active:
            names.append(session.name)
    return ",".join(names)


def _build_report(summary: dict[str, Any]) -> str:
    latest = summary.get("latest_cycle", {}) or {}
    controller = latest.get("stage903", {}).get("summary", {}) if isinstance(latest.get("stage903"), dict) else {}
    tick = latest.get("tick_refresh", {}) if isinstance(latest.get("tick_refresh"), dict) else {}
    arming = latest.get("stage927", {}).get("summary", {}) if isinstance(latest.get("stage927"), dict) else {}
    submit = latest.get("stage931", {}).get("summary", {}) if isinstance(latest.get("stage931"), dict) else {}
    return "\n".join(
        [
            "# Stage930 C9 Session Daemon",
            "",
            f"- generated_at: `{summary['generated_at']}`",
            f"- mode: `{summary['mode']}`",
            f"- submit_mode: `{summary['submit_mode']}`",
            f"- target_date: `{summary['target_date']}`",
            f"- cycle_count: `{summary['cycle_count']}`",
            f"- daemon_status: `{summary['daemon_status']}`",
            f"- current_session_names: `{summary['current_session_names']}`",
            f"- order_api_called_count: `{summary['order_api_called_count']}`",
            "",
            "## Latest Cycle",
            "",
            f"- tick_refresh: `{tick.get('refresh_status', '')}` rows `{tick.get('tick_rows', '')}`",
            f"- controller: `{controller.get('controller_status', '')}`",
            f"- stage904: `{controller.get('stage904_monitor_status', '')}` close_dry_run `{controller.get('stage904_close_dry_run_count', '')}`",
            f"- stage905: `{controller.get('stage905_executor_status', '')}` ready `{controller.get('stage905_ready_count', '')}` blocked `{controller.get('stage905_blocked_count', '')}`",
            f"- stage927: `{arming.get('arming_status', '')}` permitted `{arming.get('real_submit_permitted', '')}`",
            f"- stage931: `{submit.get('adapter_status', latest.get('stage931', {}).get('submit_status', ''))}`",
            "",
            "## Discipline",
            "",
            "- Stage930 is the session daemon/control loop for C9 entry-day monitoring.",
            "- Dry-run mode may refresh read-only broker state and ticks, but must not submit or cancel orders.",
            "- Live submit requires Stage927 permitted, exact confirm text, real-submit env, and Stage931 live-real mode.",
            "",
        ]
    )


def _write_outputs(paths: dict[str, Path], summary: dict[str, Any]) -> None:
    text = json.dumps(summary, ensure_ascii=False, indent=2, default=str)
    paths["summary_json"].write_text(text, encoding="utf-8")
    LATEST_SUMMARY_PATH.write_text(text, encoding="utf-8")
    report = _build_report(summary)
    paths["report_md"].write_text(report, encoding="utf-8")
    LATEST_REPORT_PATH.write_text(report, encoding="utf-8")
    heartbeat = {
        "heartbeat_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "daemon_status": summary.get("daemon_status"),
        "target_date": summary.get("target_date"),
        "cycle_count": summary.get("cycle_count"),
        "current_session_names": summary.get("current_session_names"),
        "order_api_called_count": summary.get("order_api_called_count"),
        "summary_path": str(paths["summary_json"].resolve()),
    }
    LATEST_HEARTBEAT_PATH.write_text(json.dumps(heartbeat, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_event(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    with LATEST_EVENT_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def _default_target_date() -> str:
    official_summary = _read_json(OFFICIAL_LIVE_SUMMARY_PATH)
    analysis_end = _clean(official_summary.get("analysis_end"))
    return analysis_end or date.today().isoformat()


def _cycle_controller_summary(cycle: dict[str, Any]) -> dict[str, Any]:
    stage903 = cycle.get("stage903", {}) if isinstance(cycle.get("stage903"), dict) else {}
    return stage903.get("summary", {}) if isinstance(stage903.get("summary"), dict) else {}


def _cycle_submit_summary(cycle: dict[str, Any]) -> dict[str, Any]:
    stage931 = cycle.get("stage931", {}) if isinstance(cycle.get("stage931"), dict) else {}
    return stage931.get("summary", {}) if isinstance(stage931.get("summary"), dict) else {}


def _cycle_email_key(cycle: dict[str, Any]) -> str:
    controller = _cycle_controller_summary(cycle)
    submit = _cycle_submit_summary(cycle)
    arming = cycle.get("stage927", {}).get("summary", {}) if isinstance(cycle.get("stage927"), dict) else {}
    order_api = _to_int(cycle.get("order_api_called_count"), 0)
    ready = _to_int(controller.get("stage905_ready_count"), 0)
    adapter_status = str(submit.get("adapter_status", ""))
    if order_api > 0:
        return f"order_api_{cycle.get('cycle_at', '')}_{order_api}"
    if cycle.get("cycle_exception"):
        return f"cycle_exception_{cycle.get('cycle_at', '')}"
    if adapter_status == "adapter_exception":
        return f"adapter_exception_{cycle.get('cycle_at', '')}"
    if ready > 0:
        return "ready_intents_first_seen"
    if (
        str(controller.get("mode", "")) == "live-real"
        and (
            _to_int(controller.get("stage902_blocking_failure_count"), 0) > 0
            or _to_int(arming.get("real_submit_permitted"), 0) != 1
            or str(controller.get("controller_status", "")).endswith("_blocked")
        )
    ):
        return "live_real_blocked_first_seen"
    return ""


def _email_throttle_allows(key: str, cycle: dict[str, Any], min_seconds: int = 1800) -> tuple[bool, str]:
    if _to_int(cycle.get("order_api_called_count"), 0) > 0:
        return True, "order_api_never_throttled"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    state = _read_json(EMAIL_THROTTLE_PATH)
    last_text = (state.get(digest) or {}).get("last_sent_at") if isinstance(state.get(digest), dict) else ""
    last_dt = None
    if last_text:
        try:
            last_dt = datetime.strptime(str(last_text), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            last_dt = None
    if last_dt is not None and (datetime.now() - last_dt).total_seconds() < min_seconds:
        return False, f"email_throttled:{digest}"
    state[digest] = {"last_sent_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "key": key}
    EMAIL_THROTTLE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return True, digest


def _send_cycle_email_if_needed(
    *,
    paths: dict[str, Path],
    summary: dict[str, Any],
    cycle: dict[str, Any],
    sent_keys: set[str],
) -> dict[str, Any] | None:
    key = _cycle_email_key(cycle)
    if not key or key in sent_keys:
        return None
    throttle_allowed, throttle_key = _email_throttle_allows(key, cycle)
    if not throttle_allowed:
        return {"email_status": "skipped_throttled", "reason": throttle_key, "throttle_path": str(EMAIL_THROTTLE_PATH.resolve())}
    sent_keys.add(key)
    controller = _cycle_controller_summary(cycle)
    submit = _cycle_submit_summary(cycle)
    order_api = _to_int(cycle.get("order_api_called_count"), 0)
    ready = _to_int(controller.get("stage905_ready_count"), 0)
    severity = "critical" if order_api > 0 or submit.get("adapter_status") == "adapter_exception" or cycle.get("cycle_exception") else "warning"
    subject = (
        f"[C9/15w][session][{severity}] {summary['target_date']} "
        f"ready={ready} order_api={order_api}"
    )
    raw_ctp_note = (
        "Stage931 附件包含未脱敏 raw CTP orders/trades，仅用于显式取证。"
        if _env_enabled("OFFICIAL_LIVE_EMAIL_ATTACH_RAW_CTP")
        else "Stage931 raw CTP orders/trades 默认不作为会话邮件附件外发。"
    )
    body = "\n".join(
        [
            "C9/15w 会话守护检测到关键执行事件。",
            "",
            f"生成时间: {summary['generated_at']}",
            f"周期时间: {cycle.get('cycle_at', '')}",
            f"模式: {summary['mode']} / submit={summary['submit_mode']}",
            f"目标日期: {summary['target_date']}",
            f"当前 session: {summary.get('current_session_names', '')}",
            "",
            f"Tick refresh: {(cycle.get('tick_refresh') or {}).get('refresh_status', '')}",
            f"Controller: {controller.get('controller_status', '')}",
            f"Stage905 ready: {ready}",
            f"Stage927 permitted: {((cycle.get('stage927') or {}).get('summary') or {}).get('real_submit_permitted', '')}",
            f"Stage931 status: {submit.get('adapter_status', (cycle.get('stage931') or {}).get('submit_status', ''))}",
            f"Order API calls in cycle: {order_api}",
            f"Cycle exception: {cycle.get('cycle_exception', '')}",
            "",
            "附件包含 Stage930 本轮 summary/report；若发生真实提交，Stage931 会另发订单级明细。",
            raw_ctp_note,
        ]
    )
    attachments: list[Path] = [paths["report_md"], paths["summary_json"]]
    stage931_outputs = submit.get("outputs", {}) if isinstance(submit.get("outputs"), dict) else {}
    stage931_attachment_keys = ["report_md", "summary_json", "submitted_csv"]
    if _env_enabled("OFFICIAL_LIVE_EMAIL_ATTACH_RAW_CTP"):
        stage931_attachment_keys.extend(["orders_csv", "trades_csv"])
    for key_name in stage931_attachment_keys:
        value = stage931_outputs.get(key_name)
        if value:
            attachments.append(Path(value))
    return send_official_live_email_notification(
        subject=subject,
        body=body,
        event_type="stage930_session_key_event",
        severity=severity,
        attachments=attachments,
        metadata={
            "target_date": summary["target_date"],
            "mode": summary["mode"],
            "submit_mode": summary["submit_mode"],
            "cycle_at": cycle.get("cycle_at", ""),
            "stage905_ready_count": ready,
            "order_api_called_count": order_api,
            "stage931_adapter_status": submit.get("adapter_status", ""),
        },
    )


def run_cycle(args: argparse.Namespace, target_date: str, paths: dict[str, Path]) -> dict[str, Any]:
    symbols = _watched_symbols(args.vt_symbol)
    tick_result = _run_tick_refresh(args, target_date, symbols, paths)
    stage903_result = _run_stage903(args, target_date, paths)
    controller_summary = stage903_result.get("summary", {}) if isinstance(stage903_result.get("summary"), dict) else {}
    resolved_target_date = _clean(controller_summary.get("target_date")) or target_date
    ready_count = _to_int(controller_summary.get("stage905_ready_count"), 0)
    stage927_result = _run_stage927(args, resolved_target_date, paths) if resolved_target_date and (args.mode == "live-real" or args.submit_mode == "live-real") else {
        "summary": {"arming_status": "stage927_skipped_dry_run", "real_submit_permitted": 0},
        "exit_code": 0,
    }
    stage927_summary = stage927_result.get("summary", {}) if isinstance(stage927_result.get("summary"), dict) else {}
    if args.submit_mode == "live-real" and ready_count > 0 and _to_int(stage927_summary.get("real_submit_permitted"), 0) == 1:
        stage931_result = _run_stage931(args, resolved_target_date, paths)
    else:
        stage931_result = {
            "submit_status": "submit_adapter_skipped_not_armed_or_no_ready",
            "exit_code": 0,
            "skip_reason": f"ready_count={ready_count};real_submit_permitted={stage927_summary.get('real_submit_permitted', 0)}",
        }
    order_api_called = (
        _to_int(stage903_result.get("summary", {}).get("order_api_called_count"), 0)
        + _to_int(stage927_result.get("summary", {}).get("order_api_called_count"), 0)
        + _to_int(stage931_result.get("summary", {}).get("order_api_called_count"), 0)
    )
    return {
        "cycle_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_date": resolved_target_date,
        "requested_target_date": target_date,
        "watched_symbols": symbols,
        "tick_refresh": tick_result,
        "stage903": stage903_result,
        "stage927": stage927_result,
        "stage931": stage931_result,
        "order_api_called_count": order_api_called,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="C9 official live session daemon with tick refresh and submit gating.")
    parser.add_argument("--mode", choices=["dry-run", "live-real"], default="dry-run")
    parser.add_argument("--submit-mode", choices=["disabled", "live-real"], default="disabled")
    parser.add_argument("--target-date", default="")
    parser.add_argument("--duration-seconds", type=int, default=0)
    parser.add_argument("--max-cycles", type=int, default=1)
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--tick-refresh-mode", choices=["skip", "plan-only", "refresh"], default="refresh")
    parser.add_argument("--tick-wait-seconds", type=int, default=12)
    parser.add_argument("--pre-subscribe-wait-seconds", type=int, default=4)
    parser.add_argument("--readonly-refresh-mode", choices=["plan-only", "refresh", "auto"], default="auto")
    parser.add_argument("--readonly-wait-seconds", type=int, default=30)
    parser.add_argument("--shadow-refresh-mode", choices=["plan-only", "run", "auto"], default="auto")
    parser.add_argument("--stage251-mode", choices=["skip", "auto", "force"], default="skip")
    parser.add_argument("--max-snapshot-age-seconds", type=int, default=300)
    parser.add_argument("--controller-timeout-seconds", type=int, default=1200)
    parser.add_argument("--submit-timeout-seconds", type=int, default=180)
    parser.add_argument("--max-submit-orders", type=int, default=1)
    parser.add_argument("--fill-wait-seconds", type=int, default=8)
    parser.add_argument("--max-consecutive-cycle-errors", type=int, default=3)
    parser.add_argument("--confirm-live-real", default="")
    parser.add_argument("--vt-symbol", action="append", default=[])
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lock_handle = _acquire_singleton_lock()
    if lock_handle is None:
        summary = {
            "model_tag": MODEL_TAG,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "official_live_version": OFFICIAL_LIVE_VERSION,
            "mode": args.mode,
            "submit_mode": args.submit_mode,
            "target_date": args.target_date,
            "daemon_status": "daemon_blocked_already_running",
            "order_api_called_count": 0,
            "lock_path": str(LOCK_PATH.resolve()),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
        sys.exit(3)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = _paths(run_id)
    target_date = args.target_date
    started = time.monotonic()
    cycles: list[dict[str, Any]] = []
    email_notifications: list[dict[str, Any]] = []
    sent_email_keys: set[str] = set()
    status = "daemon_started"
    consecutive_errors = 0

    while True:
        try:
            cycle = run_cycle(args, target_date, paths)
            consecutive_errors = 0
            status = "daemon_running"
        except Exception as exc:
            consecutive_errors += 1
            cycle = {
                "cycle_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "target_date": target_date,
                "watched_symbols": _watched_symbols(args.vt_symbol),
                "tick_refresh": {"refresh_status": "cycle_exception_before_or_during_refresh"},
                "stage903": {"summary": {"controller_status": "stage930_cycle_exception_fail_closed"}},
                "stage927": {"summary": {"arming_status": "stage927_skipped_cycle_exception", "real_submit_permitted": 0}},
                "stage931": {"summary": {"adapter_status": "stage931_skipped_cycle_exception"}},
                "order_api_called_count": 0,
                "cycle_exception": repr(exc),
                "consecutive_cycle_errors": consecutive_errors,
            }
            status = "daemon_cycle_exception_fail_closed"
        cycles.append(cycle)
        _append_event(paths["events_ndjson"], {"event_type": "stage930_cycle", **cycle})
        total_order_api = sum(_to_int(item.get("order_api_called_count"), 0) for item in cycles)
        summary = {
            "model_tag": MODEL_TAG,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "official_live_version": OFFICIAL_LIVE_VERSION,
            "mode": args.mode,
            "submit_mode": args.submit_mode,
            "target_date": _clean(cycle.get("target_date")) or target_date,
            "requested_target_date": target_date,
            "cycle_count": len(cycles),
            "daemon_status": status,
            "consecutive_cycle_errors": consecutive_errors,
            "current_session_names": _current_session_names(),
            "order_api_called_count": total_order_api,
            "latest_cycle": cycle,
            "email_notifications": email_notifications,
            "outputs": {key: str(value.resolve()) for key, value in paths.items()},
            "latest_outputs": {
                "summary_json": str(LATEST_SUMMARY_PATH.resolve()),
                "report_md": str(LATEST_REPORT_PATH.resolve()),
                "heartbeat_json": str(LATEST_HEARTBEAT_PATH.resolve()),
                "events_ndjson": str(LATEST_EVENT_LOG_PATH.resolve()),
            },
            "judgement": {
                "overfit_before": "否。Stage930 是执行会话守护进程，不改 C9 alpha 参数。",
                "continue_before": "是。C9 入场日 0.5R 止损/重试需要盘中持续 tick 判断。",
                "overfit_after": "否。daemon 只影响执行时序和闸门。",
                "continue_after": "是。若要真实自动开平仓，还需 Stage927 permit 与 Stage931 live-real submit evidence。",
            },
        }
        _write_outputs(paths, summary)
        email_result = _send_cycle_email_if_needed(paths=paths, summary=summary, cycle=cycle, sent_keys=sent_email_keys)
        if email_result is not None:
            email_notifications.append(email_result)
            summary["email_notifications"] = email_notifications
            _write_outputs(paths, summary)
        if consecutive_errors >= max(1, args.max_consecutive_cycle_errors):
            status = "daemon_stopped_after_consecutive_cycle_errors"
            summary["daemon_status"] = status
            _write_outputs(paths, summary)
            print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
            sys.exit(2)
        if args.max_cycles and len(cycles) >= args.max_cycles:
            status = "daemon_completed_max_cycles"
            summary["daemon_status"] = status
            _write_outputs(paths, summary)
            print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
            return
        if args.duration_seconds and time.monotonic() - started >= args.duration_seconds:
            status = "daemon_completed_duration"
            summary["daemon_status"] = status
            _write_outputs(paths, summary)
            print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
            return
        time.sleep(max(5, args.poll_seconds))


if __name__ == "__main__":
    main()
