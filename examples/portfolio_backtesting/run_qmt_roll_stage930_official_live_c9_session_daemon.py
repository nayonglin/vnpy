from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import signal
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
from qmt_roll_official_live_execution_ledger import ledger_order_api_counts, read_execution_ledger
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
STAGE905_MODEL_TAG = "stage905_official_live_executor_dry_run_v1"
STAGE905_PREFIX = "qmt_roll_stage905_official_live_executor_dry_run"

MODEL_TAG = "stage930_official_live_c9_session_daemon_v1"
OUTPUT_PREFIX = "qmt_roll_stage930_official_live_c9_session_daemon"
LATEST_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_official_live_c9_session_daemon_latest_summary.json"
LATEST_REPORT_PATH = OUTPUT_DIR / "qmt_roll_official_live_c9_session_daemon_latest_report.md"
LATEST_HEARTBEAT_PATH = OUTPUT_DIR / "qmt_roll_official_live_c9_session_daemon_heartbeat.json"
LATEST_EVENT_LOG_PATH = OUTPUT_DIR / "qmt_roll_official_live_c9_session_daemon_events.ndjson"
LOCK_PATH = OUTPUT_DIR / "qmt_roll_official_live_c9_session_daemon.lock"
EMAIL_THROTTLE_PATH = OUTPUT_DIR / "qmt_roll_stage930_official_live_email_throttle.json"
EMAIL_CONTENT_VERSION = "stage930_plain_text_v2"


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


def _parse_dt(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


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


def _run_command(
    cmd: list[str],
    *,
    timeout_seconds: int,
    log_path: Path,
    label: str,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    started = datetime.now()
    proc = subprocess.Popen(
        cmd,
        cwd=REPO_ROOT,
        env=env or os.environ.copy(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout, _ = proc.communicate(timeout=timeout_seconds)
        exit_code = proc.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, _ = proc.communicate()
        exit_code = -signal.SIGKILL
        stdout = (stdout or "") + f"\nTIMEOUT: killed process group after {timeout_seconds}s\n"
    finished = datetime.now()
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n===== {label} started_at={started:%Y-%m-%d %H:%M:%S} exit={exit_code} timed_out={int(timed_out)} =====\n")
        handle.write(stdout or "")
        handle.write("\n")
    return {
        "label": label,
        "command": cmd,
        "exit_code": exit_code,
        "timed_out": int(timed_out),
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": finished.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_seconds": round((finished - started).total_seconds(), 3),
        "stdout": stdout or "",
        "stdout_tail": (stdout or "")[-4000:],
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
    result = _run_command(
        cmd,
        timeout_seconds=args.controller_timeout_seconds,
        log_path=paths["command_log"],
        label="stage903_controller",
        env=env,
    )
    summary = _extract_json_from_stdout(result.get("stdout", ""))
    return {
        **{key: value for key, value in result.items() if key != "stdout"},
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
    summary = _read_json(summary_path)
    started_at = _parse_dt(result.get("started_at"))
    summary_generated_at = _parse_dt(summary.get("generated_at"))
    summary_stale = started_at is not None and (summary_generated_at is None or summary_generated_at < started_at)
    if result.get("timed_out") or summary_stale:
        ledger_counts = ledger_order_api_counts(read_execution_ledger(), target_date)
        blockers = list(summary.get("blockers", [])) if isinstance(summary.get("blockers"), list) else []
        blocker = "stage931_timeout_or_stale_summary"
        if blocker not in blockers:
            blockers.append(blocker)
        summary = {
            **summary,
            "target_date": target_date,
            "adapter_status": "adapter_blocked_timeout_or_stale_summary",
            "blocking_failure_count": max(_to_int(summary.get("blocking_failure_count"), 0), len(blockers), 1),
            "blockers": blockers,
            "stage930_summary_stale_after_submit": int(summary_stale),
            "stage930_submit_timed_out": int(bool(result.get("timed_out"))),
            "ledger_counts_after_timeout_or_stale": ledger_counts,
            "send_order_api_called_count": max(_to_int(summary.get("send_order_api_called_count"), 0), _to_int(ledger_counts.get("send_order_called"), 0)),
            "cancel_order_api_called_count": max(_to_int(summary.get("cancel_order_api_called_count"), 0), _to_int(ledger_counts.get("cancel_order_called"), 0)),
            "order_api_called_count": max(
                _to_int(summary.get("order_api_called_count"), 0),
                _to_int(ledger_counts.get("send_order_called"), 0) + _to_int(ledger_counts.get("cancel_order_called"), 0),
            ),
        }
    return {**{key: value for key, value in result.items() if key != "stdout"}, "summary": summary}


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
            "# Stage930 C9 盘中会话守护报告",
            "",
            f"- 生成时间：`{summary['generated_at']}`",
            f"- 控制器模式：`{summary['mode']}`",
            f"- 真实提交模式：`{summary['submit_mode']}`",
            f"- 目标交易日：`{summary['target_date']}`",
            f"- 已运行轮次：`{summary['cycle_count']}`",
            f"- 守护进程状态：`{summary['daemon_status']}`",
            f"- 当前交易时段：`{summary['current_session_names']}`",
            f"- 下单 API 调用次数：`{summary['order_api_called_count']}`",
            "",
            "## 最近一轮",
            "",
            f"- tick 刷新：`{tick.get('refresh_status', '')}`，行数 `{tick.get('tick_rows', '')}`",
            f"- Controller：`{controller.get('controller_status', '')}`",
            f"- Stage904 平仓/重试监控：`{controller.get('stage904_monitor_status', '')}`，close dry-run `{controller.get('stage904_close_dry_run_count', '')}`，retry open dry-run `{controller.get('stage904_retry_open_dry_run_count', '')}`",
            f"- Stage905 开仓/平仓执行 dry-run：`{controller.get('stage905_executor_status', '')}`，ready `{controller.get('stage905_ready_count', '')}`，blocked `{controller.get('stage905_blocked_count', '')}`",
            f"- Stage927 真实提交闸门：`{arming.get('arming_status', '')}`，是否允许 `{arming.get('real_submit_permitted', '')}`",
            f"- Stage931 真实提交适配器：`{submit.get('adapter_status', latest.get('stage931', {}).get('submit_status', ''))}`",
            "",
            "## 执行纪律",
            "",
            "- Stage930 是 C9 入场日/持仓日盘中守护循环，用来刷新 tick、检查止损/开平仓候选，并按闸门决定是否提交。",
            "- dry-run 模式可以刷新只读账户和行情，但不会报单或撤单。",
            "- live-real 提交必须同时满足 Stage927 放行、确认文本、真实提交环境变量和 Stage931 live-real 模式。",
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


def _stage905_intents_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE905_PREFIX}_intents_{date_key}_{STAGE905_MODEL_TAG}.csv"


def _ready_intents_close_only(target_date: str) -> bool:
    intents = _read_csv_maybe(_stage905_intents_path(target_date))
    if intents.empty or "executor_status" not in intents.columns:
        return False
    ready = intents[intents["executor_status"].astype(str).eq("dry_run_order_request_payload_ready")].copy()
    if ready.empty:
        return False
    sources = ready.get("source", pd.Series([""] * len(ready))).fillna("").astype(str)
    offsets = ready.get("offset", pd.Series([""] * len(ready))).fillna("").astype(str).str.lower()
    return bool(sources.eq("stage904_c9_intraday_close").all() and offsets.eq("close").all())


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
    digest = hashlib.sha256(f"{EMAIL_CONTENT_VERSION}:{key}".encode("utf-8")).hexdigest()
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


def _fmt_number(value: Any, default: str = "-") -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    if float(number).is_integer():
        return str(int(number))
    return f"{float(number):.4f}".rstrip("0").rstrip(".")


def _direction_cn(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"short", "direction.short", "空"}:
        return "空"
    if text in {"long", "direction.long", "多"}:
        return "多"
    return str(value or "").strip() or "-"


def _offset_cn(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"open", "offset.open", "开"}:
        return "开"
    if text in {"close", "closetoday", "closeyesterday", "offset.close", "offset.closetoday", "offset.closeyesterday", "平", "平今", "平昨"}:
        return "平"
    return str(value or "").strip() or "-"


def _short_symbol(value: Any) -> str:
    text = str(value or "").strip()
    return text.split(".", 1)[0] if text else "-"


def _intent_action_text(row: dict[str, Any], *, include_price: bool = True) -> str:
    vt_symbol = str(row.get("vt_symbol", "") or "").strip() or "-"
    direction = _direction_cn(row.get("direction"))
    offset = _offset_cn(row.get("offset"))
    volume = _fmt_number(row.get("planned_volume", row.get("volume", "")))
    price = _fmt_number(row.get("limit_price", row.get("price", "")))
    text = f"{vt_symbol} {direction}{offset} {volume}手"
    if include_price and price != "-":
        text += f"，限价 {price}"
    return text


def _first_intent_subject_text(intents: pd.DataFrame, fallback: str) -> str:
    if intents.empty:
        return fallback
    row = intents.iloc[0].to_dict()
    symbol = _short_symbol(row.get("vt_symbol"))
    direction = _direction_cn(row.get("direction"))
    offset = _offset_cn(row.get("offset"))
    volume = _fmt_number(row.get("planned_volume", row.get("volume", "")))
    if volume == "-":
        return f"{symbol}{direction}{offset}"
    return f"{symbol}{direction}{offset}{volume}手"


def _first_existing_position_subject_text(intents: pd.DataFrame, fallback: str) -> str:
    if intents.empty or "executor_status" not in intents.columns:
        return fallback
    skipped = intents[intents["executor_status"].astype(str).eq("skipped_existing_broker_position")]
    if skipped.empty:
        return fallback
    row = skipped.iloc[0].to_dict()
    symbol = _short_symbol(row.get("vt_symbol"))
    direction = _direction_cn(row.get("direction"))
    broker_volume = _fmt_number(row.get("broker_matching_position_volume"))
    if broker_volume == "-":
        broker_volume = _fmt_number(row.get("planned_volume", row.get("volume", "")))
    return f"{symbol}{direction}单{broker_volume}手" if broker_volume != "-" else f"{symbol}{direction}单"


def _skipped_existing_position_lines(intents: pd.DataFrame) -> list[str]:
    if intents.empty or "executor_status" not in intents.columns:
        return []
    skipped = intents[intents["executor_status"].astype(str).eq("skipped_existing_broker_position")]
    lines: list[str] = []
    for row in skipped.head(3).to_dict(orient="records"):
        broker_volume = _fmt_number(row.get("broker_matching_position_volume"))
        action_text = _intent_action_text(row, include_price=False)
        direction = _direction_cn(row.get("direction"))
        if broker_volume != "-":
            lines.append(f"原计划 {action_text}：已跳过。券商账户已有同方向{direction}单 {broker_volume} 手，系统不会重复开仓。")
        else:
            lines.append(f"原计划 {action_text}：已跳过。券商账户已有同方向仓位，系统不会重复开仓。")
    return lines


def _ready_intent_lines(intents: pd.DataFrame) -> list[str]:
    if intents.empty or "executor_status" not in intents.columns:
        return []
    ready = intents[intents["executor_status"].astype(str).eq("dry_run_order_request_payload_ready")]
    return [f"待提交：{_intent_action_text(row)}。" for row in ready.head(3).to_dict(orient="records")]


def _human_blocker_lines(cycle: dict[str, Any], *, has_existing_position_skip: bool) -> list[str]:
    raw_blockers = [str(item) for item in cycle.get("stage931_submit_blockers", [])]
    if not raw_blockers:
        return ["无。"]
    lines: list[str] = []
    for blocker in raw_blockers:
        if blocker.startswith("ready_count=0"):
            lines.append("没有可提交指令。")
        elif blocker.startswith("real_submit_permitted=0"):
            if has_existing_position_skip:
                lines.append("真实开仓总闸门未放行，是为了防止已有仓位时重复开仓。")
            else:
                lines.append("真实报单总闸门未放行，系统保持 fail-closed。")
        elif blocker.startswith("controller_status="):
            if has_existing_position_skip:
                lines.append("控制器处于保护状态，因为当前账户持仓和理论影子仓位还没有重新对齐。")
            else:
                lines.append("控制器处于保护状态。")
        elif blocker.startswith("stage905_executor_status=executor_no_ready_intents"):
            lines.append("执行层没有 ready 指令。")
        elif blocker.startswith("stage905_blocked_count="):
            lines.append(f"执行层仍有阻断项：{blocker}。")
        else:
            lines.append(f"内部阻断：{blocker}。")
    deduped: list[str] = []
    for line in lines:
        if line not in deduped:
            deduped.append(line)
    return deduped


def _build_cycle_email_content(summary: dict[str, Any], cycle: dict[str, Any]) -> dict[str, Any]:
    controller = _cycle_controller_summary(cycle)
    submit = _cycle_submit_summary(cycle)
    arming = cycle.get("stage927", {}).get("summary", {}) if isinstance(cycle.get("stage927"), dict) else {}
    target_date = str(cycle.get("target_date") or summary.get("target_date") or "")
    intents = _read_csv_maybe(_stage905_intents_path(target_date)) if target_date else pd.DataFrame()
    ready = _to_int(controller.get("stage905_ready_count"), 0)
    order_api = _to_int(cycle.get("order_api_called_count"), 0)
    skipped_existing_lines = _skipped_existing_position_lines(intents)
    ready_lines = _ready_intent_lines(intents)
    has_existing_position_skip = bool(skipped_existing_lines)
    exception_text = str(cycle.get("cycle_exception", "") or "").strip()
    adapter_status = str(submit.get("adapter_status", (cycle.get("stage931") or {}).get("submit_status", "")) or "")

    if order_api > 0:
        severity = "critical"
        status_label = "已报单"
        subject_detail = f"{_first_intent_subject_text(intents, '有真实API调用')} API={order_api}"
        conclusion = "已经调用真实下单或撤单 API。请马上核对委托、成交、持仓和资金。"
    elif exception_text or adapter_status == "adapter_exception":
        severity = "critical"
        status_label = "异常"
        subject_detail = "守护进程异常"
        conclusion = "盘中守护出现异常，本轮没有确认下单。请先看异常原因，不要手工追单。"
    elif ready > 0:
        severity = "warning"
        status_label = "待确认"
        subject_detail = f"{_first_intent_subject_text(intents, '有可提交指令')} 待闸门"
        conclusion = "出现可提交指令，但本轮还没有真实下单；系统会继续走最终报单前检查。"
    elif has_existing_position_skip:
        severity = "info"
        status_label = "无需操作"
        subject_detail = f"已有{_first_existing_position_subject_text(intents, '仓位')} 不重复开仓"
        conclusion = "无需操作。本轮没有下单；系统识别到券商账户已有同方向仓位，已跳过原开仓计划，避免重复开仓。"
    else:
        severity = "info"
        status_label = "监控中"
        subject_detail = "无新报单"
        conclusion = "无需操作。本轮没有可提交指令，也没有真实下单；系统继续监控。"

    monitor_status = str(controller.get("stage904_monitor_status", "") or "")
    if monitor_status == "intraday_monitor_ready":
        stop_line = "盘中止损：正在运行；本轮没有触发止损平仓。"
    elif monitor_status:
        stop_line = f"盘中止损：{monitor_status}。"
    else:
        stop_line = "盘中止损：未拿到本轮状态。"

    if ready_lines:
        signal_lines = ready_lines
    elif skipped_existing_lines:
        signal_lines = skipped_existing_lines
    else:
        signal_lines = ["无可提交指令。"]

    blocker_lines = _human_blocker_lines(cycle, has_existing_position_skip=has_existing_position_skip)
    next_step = "下一步：继续每轮刷新行情、账户和持仓；如果触发止损，系统会走平仓检查和提交通道。"
    if ready > 0 and order_api == 0:
        next_step = "下一步：继续自动检查最终报单闸门；没有成交确认前不要手工追单。"
    elif order_api > 0:
        next_step = "下一步：立即人工核对交易软件里的委托、成交、持仓和资金。"

    body_lines = [
        f"结论：{conclusion}",
        "",
        f"当前信号/仓位：{signal_lines[0]}",
    ]
    body_lines.extend(signal_lines[1:])
    body_lines.extend(
        [
            stop_line,
            next_step,
            "",
            f"本轮结果：可提交 {ready}；下单API {order_api}；异常 {exception_text or '无'}。",
            f"时间：{cycle.get('cycle_at', '')}；时段：{summary.get('current_session_names', '')}；模式：{summary.get('mode', '')}/{summary.get('submit_mode', '')}。",
            "",
            "为什么没有下单：",
        ]
    )
    body_lines.extend(blocker_lines)
    body_lines.extend(
        [
            "",
            "排查用内部状态：",
            f"Stage904={monitor_status or '-'}；Stage905={controller.get('stage905_executor_status', '-')}; Stage906={controller.get('stage906_reconciliation_status', '-')}; Stage927放行={arming.get('real_submit_permitted', '-')}; Stage931={adapter_status or '-'}。",
        ]
    )
    return {
        "severity": severity,
        "subject": f"[C9/15w][{status_label}] {subject_detail}",
        "body": "\n".join(body_lines),
        "status_label": status_label,
        "ready": ready,
        "order_api": order_api,
        "stage931_adapter_status": adapter_status,
    }


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
    content = _build_cycle_email_content(summary, cycle)
    severity = str(content["severity"])
    subject = str(content["subject"])
    body = str(content["body"])
    attachments: list[Path] = [paths["report_md"], paths["summary_json"]]
    submit = _cycle_submit_summary(cycle)
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
            "status_label": content["status_label"],
            "stage905_ready_count": content["ready"],
            "order_api_called_count": content["order_api"],
            "stage931_adapter_status": content["stage931_adapter_status"],
        },
    )


def _stage931_submit_blockers(
    args: argparse.Namespace,
    target_date: str,
    controller_summary: dict[str, Any],
    stage927_summary: dict[str, Any],
    ready_count: int,
) -> list[str]:
    blockers: list[str] = []
    close_only_reduce_risk = _ready_intents_close_only(target_date)
    if args.submit_mode != "live-real":
        blockers.append(f"submit_mode_not_live_real:{args.submit_mode}")
    if args.mode != "live-real":
        blockers.append(f"controller_mode_not_live_real:{args.mode}")
    if ready_count <= 0:
        blockers.append(f"ready_count={ready_count}")
    if _to_int(stage927_summary.get("real_submit_permitted"), 0) != 1 and not close_only_reduce_risk:
        blockers.append(f"real_submit_permitted={stage927_summary.get('real_submit_permitted', 0)}")
    if _clean(controller_summary.get("controller_status")) != "phase_d_controller_live_real_ready_no_submit_step" and not close_only_reduce_risk:
        blockers.append(f"controller_status={controller_summary.get('controller_status', '')}")
    if _clean(controller_summary.get("stage905_executor_status")) != "executor_dry_run_ready":
        blockers.append(f"stage905_executor_status={controller_summary.get('stage905_executor_status', '')}")
    if _to_int(controller_summary.get("stage905_blocked_count"), 999) != 0:
        blockers.append(f"stage905_blocked_count={controller_summary.get('stage905_blocked_count', '')}")
    if _to_int(controller_summary.get("stage905_ready_count"), -1) != ready_count:
        blockers.append(f"stage905_ready_count_mismatch={controller_summary.get('stage905_ready_count', '')}!={ready_count}")
    if _to_int(controller_summary.get("stage904_retry_open_dry_run_count"), 0) > 0 and _clean(controller_summary.get("stage904_monitor_status")) == "intraday_monitor_blocked":
        blockers.append("stage904_retry_present_but_monitor_blocked")
    return blockers


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
    submit_blockers = _stage931_submit_blockers(args, resolved_target_date, controller_summary, stage927_summary, ready_count)
    if not submit_blockers:
        stage931_result = _run_stage931(args, resolved_target_date, paths)
    else:
        stage931_result = {
            "submit_status": "submit_adapter_skipped_not_armed_or_no_ready",
            "exit_code": 0,
            "skip_reason": ";".join(submit_blockers),
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
        "stage931_submit_blockers": submit_blockers,
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
