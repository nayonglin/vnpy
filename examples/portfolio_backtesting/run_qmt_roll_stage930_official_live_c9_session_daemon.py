from __future__ import annotations

import argparse
import atexit
import fcntl
import hashlib
import json
import os
import signal
import shlex
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_execution_profile import (
    ExecutionStrategyMode,
    OfficialExecutionProfile,
    resolve_execution_profile,
)
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_CURRENT_POSITIONS_PATH,
    OFFICIAL_LIVE_SIGNAL_PLAN_PATH,
    OFFICIAL_LIVE_SUMMARY_PATH,
    OFFICIAL_LIVE_VERSION,
)
from qmt_roll_official_live_execution_ledger import ledger_order_api_counts, read_execution_ledger
from qmt_roll_official_live_execution_service import revoke_readiness
from qmt_roll_official_live_intent_spool import notify_executor, wakeup_socket_path
from qmt_roll_official_live_submit_authorization import (
    publish_submit_authorization,
    revoke_submit_authorization,
    submit_authorization_path,
    validate_submit_authorization,
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
    READONLY_POSITIONS_PATH,
    READONLY_SUMMARY_PATH,
    READONLY_TICKS_PATH,
    STAGE901_PENDING_ORDERS_PATH,
    build_phase_d_config,
)
from qmt_roll_official_live_email_notify import send_official_live_email_notification
from qmt_roll_official_live_runtime_profile import (
    ExecutionRuntimeProfile,
    OrderScope,
    resolve_runtime_profile,
)
from run_qmt_alignment_backtest import OUTPUT_DIR


PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent.parent
PYTHON_PATH = REPO_ROOT / ".py311/bin/python"
STAGE903_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage903_official_live_phase_d_controller.py"
STAGE608_SCRIPT = PROJECT_DIR / "run_ctp_stage608_readonly_tick_snapshot_probe.py"
STAGE904_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage904_official_live_c9_intraday_monitor.py"
STAGE905_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage905_official_live_executor_dry_run.py"
STAGE927_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage927_official_live_real_submit_arming_gate.py"
STAGE931_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage931_official_live_ctp_submit_adapter.py"
STAGE935_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py"
STAGE941_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage941_official_live_c9_detector.py"
OWNED_CHILD_GUARD_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage930_owned_child_guard.py"
STAGE905_MODEL_TAG = "stage905_official_live_executor_dry_run_v1"
STAGE905_PREFIX = "qmt_roll_stage905_official_live_executor_dry_run"
STAGE904_MODEL_TAG = "stage904_official_live_c9_intraday_monitor_v1"
STAGE904_PREFIX = "qmt_roll_stage904_official_live_c9_intraday_monitor"

MODEL_TAG = "stage930_official_live_c9_session_daemon_v1"
OUTPUT_PREFIX = "qmt_roll_stage930_official_live_c9_session_daemon"
STAGE372_LAUNCHD_LABELS = {
    "local.qmt-roll.official-live.20w.stage372-day-session",
    "local.qmt-roll.official-live.20w.stage372-night-session",
}


def _launchd_provenance(daemon_started_epoch_ns: int) -> dict[str, Any]:
    label = _clean(os.getenv("XPC_SERVICE_NAME", ""))
    pid = os.getpid()
    parent_pid = os.getppid()
    launchctl_exit_code: int | None = None
    launchctl_job_pid: int | None = None
    if label in STAGE372_LAUNCHD_LABELS:
        try:
            result = subprocess.run(
                [
                    "/bin/launchctl",
                    "print",
                    f"gui/{os.getuid()}/{label}",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=3,
            )
            launchctl_exit_code = result.returncode
            for line in result.stdout.splitlines():
                stripped = line.strip()
                if stripped.startswith("pid ="):
                    try:
                        launchctl_job_pid = int(stripped.split("=", 1)[1].strip())
                    except ValueError:
                        launchctl_job_pid = None
                    break
        except (OSError, subprocess.SubprocessError):
            launchctl_exit_code = None
    return {
        "model_tag": "stage930_launchd_provenance_v1",
        "pid": pid,
        "parent_pid": parent_pid,
        "xpc_service_name": label,
        "launchctl_print_exit_code": launchctl_exit_code,
        "launchctl_job_pid": launchctl_job_pid,
        "daemon_started_epoch_ns": daemon_started_epoch_ns,
        "complete": int(
            parent_pid == 1
            and label in STAGE372_LAUNCHD_LABELS
            and launchctl_exit_code == 0
            and launchctl_job_pid == pid
        ),
    }
LATEST_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_official_live_c9_session_daemon_latest_summary.json"
LATEST_REPORT_PATH = OUTPUT_DIR / "qmt_roll_official_live_c9_session_daemon_latest_report.md"
LATEST_HEARTBEAT_PATH = OUTPUT_DIR / "qmt_roll_official_live_c9_session_daemon_heartbeat.json"
LATEST_EVENT_LOG_PATH = OUTPUT_DIR / "qmt_roll_official_live_c9_session_daemon_events.ndjson"
LOCK_PATH = OUTPUT_DIR / "qmt_roll_official_live_c9_session_daemon.lock"
EMAIL_THROTTLE_PATH = OUTPUT_DIR / "qmt_roll_stage930_official_live_email_throttle.json"
EMAIL_CONTENT_VERSION = "stage930_plain_text_v2"
TICK_STREAM_HEARTBEAT_PATH = OUTPUT_DIR / "qmt_roll_stage608_readonly_tick_snapshot_probe_tick_stream_heartbeat_stage608_readonly_tick_snapshot_probe_v1.json"
TICK_STREAM_JOURNAL_PATH = OUTPUT_DIR / "qmt_roll_stage608_readonly_tick_snapshot_probe_tick_stream_stage608_readonly_tick_snapshot_probe_v1.ndjson"
TICK_STREAM_MANIFEST_PATH = OUTPUT_DIR / "qmt_roll_stage930_official_live_c9_tick_stream_manifest.json"
STAGE941_HEARTBEAT_PATH = OUTPUT_DIR / "qmt_roll_stage941_official_live_c9_detector_heartbeat.json"
STAGE941_SPOOL_PATH = OUTPUT_DIR / "qmt_roll_stage941_official_live_intent_spool.sqlite3"
FAST_LANE_RECENT_RUN_LIMIT = 20
TICK_STREAM_MAX_RESTARTS = 3
TICK_STREAM_RESTART_BACKOFF_SECONDS = 2.0
DETECTOR_MAX_RESTARTS = 3
DETECTOR_RESTART_BACKOFF_SECONDS = 2.0
DETECTOR_HEARTBEAT_MIN_MAX_AGE_SECONDS = 1.0
DETECTOR_HEARTBEAT_POLL_MULTIPLIER = 10.0
TICK_CLOCK_SKEW_SECONDS = 2.0
CHILD_TERM_GRACE_SECONDS = 5.0
CHILD_KILL_WAIT_SECONDS = 5.0
GUARD_TARGET_TERM_GRACE_SECONDS = 2.0
GUARD_TARGET_KILL_WAIT_SECONDS = 2.0
DEFAULT_MAX_SUBMIT_LOGICAL_INTENTS = 1


class DaemonShutdownRequested(BaseException):
    """Unwind immediately without being swallowed by fail-closed cycle handlers."""

    def __init__(self, signum: int) -> None:
        super().__init__(f"stage930 daemon shutdown requested by signal {signum}")
        self.signum = int(signum)


_ACTIVE_CHILDREN: dict[int, subprocess.Popen[Any]] = {}
_ACTIVE_CHILDREN_LOCK = threading.RLock()
_SHUTDOWN_REQUESTED = False
_RUNTIME_OWNS_HEARTBEAT = False
_ATEXIT_REGISTERED = False
_SHUTDOWN_SIGNAL = 0
_SPAWN_IN_PROGRESS = False
_DEFERRED_SHUTDOWN_SIGNAL = 0
_CLEANUP_IN_PROGRESS = False
_STAGE931_SERVICE_PROCESS: subprocess.Popen[Any] | None = None
_STAGE931_SERVICE_RUNTIME: Any | None = None


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


def _age_seconds(value: Any) -> float | None:
    parsed = _parse_dt(value)
    if parsed is None:
        return None
    now = datetime.now(tz=parsed.tzinfo) if parsed.tzinfo is not None else datetime.now()
    return (now - parsed).total_seconds()


def _to_int(value: Any, default: int = 0) -> int:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return int(number)


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _execution_profile_for_args(
    args: argparse.Namespace,
) -> OfficialExecutionProfile:
    return resolve_execution_profile(
        getattr(
            args,
            "execution_profile",
            ExecutionStrategyMode.C9_15W_HISTORICAL.value,
        )
    )


def _profile_uses_intraday_detector(args: argparse.Namespace) -> bool:
    return _execution_profile_for_args(args).intraday_stop_retry_enabled


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


def _active_children_snapshot() -> list[subprocess.Popen[Any]]:
    with _ACTIVE_CHILDREN_LOCK:
        return list(_ACTIVE_CHILDREN.values())


def _register_active_child(process: subprocess.Popen[Any]) -> None:
    with _ACTIVE_CHILDREN_LOCK:
        _ACTIVE_CHILDREN[id(process)] = process


def _unregister_active_child(process: subprocess.Popen[Any] | None) -> None:
    if process is None:
        return
    with _ACTIVE_CHILDREN_LOCK:
        _ACTIVE_CHILDREN.pop(id(process), None)
    owner_write_fd = getattr(process, "_stage930_owner_write_fd", None)
    if isinstance(owner_write_fd, int) and owner_write_fd >= 0:
        try:
            os.close(owner_write_fd)
        except OSError:
            pass
        try:
            setattr(process, "_stage930_owner_write_fd", -1)
        except Exception:
            pass


def _managed_popen(cmd: list[str], **kwargs: Any) -> subprocess.Popen[Any]:
    """Spawn a child with kernel-enforced owner death and process-group cleanup.

    A signal received across the spawn/register critical section is deferred
    until registration completes.  Blocking the signal with pthread_sigmask is
    deliberately avoided because the child would inherit the blocked mask and
    could then ignore the owner's TERM.  A private anonymous pipe has exactly
    one writer, held by Stage930; a tiny watchdog owns the read end and kills
    the target process group on EOF, including uncatchable owner SIGKILL/native
    crash.  The guard launches the real target in a separate process group and
    mirrors its stdout and return code without detaching either process from
    the launchd session.
    """

    global _DEFERRED_SHUTDOWN_SIGNAL, _SPAWN_IN_PROGRESS
    if _SHUTDOWN_REQUESTED:
        raise DaemonShutdownRequested(_SHUTDOWN_SIGNAL or signal.SIGTERM)
    if "pass_fds" in kwargs:
        raise ValueError("managed Stage930 callers must not supply pass_fds")
    if "process_group" in kwargs:
        raise ValueError("managed Stage930 owns the target process group")
    _SPAWN_IN_PROGRESS = True
    process: subprocess.Popen[Any] | None = None
    owner_read_fd, owner_write_fd = os.pipe()
    try:
        if "start_new_session" in kwargs:
            raise ValueError("managed Stage930 children must not start a new session")
        guard_cmd = [
            sys.executable,
            str(OWNED_CHILD_GUARD_SCRIPT),
            "--owner-fd",
            str(owner_read_fd),
            "--term-grace-seconds",
            str(GUARD_TARGET_TERM_GRACE_SECONDS),
            "--kill-wait-seconds",
            str(GUARD_TARGET_KILL_WAIT_SECONDS),
            "--",
            *[str(item) for item in cmd],
        ]
        kwargs["close_fds"] = True
        kwargs["pass_fds"] = (owner_read_fd,)
        kwargs["process_group"] = 0
        process = subprocess.Popen(guard_cmd, **kwargs)
        os.close(owner_read_fd)
        owner_read_fd = -1
        setattr(process, "_stage930_owner_write_fd", owner_write_fd)
        setattr(process, "_stage930_owned_child_guard", True)
        owner_write_fd = -1
        _register_active_child(process)
    except BaseException:
        for descriptor in (owner_read_fd, owner_write_fd):
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
        if process is not None:
            _signal_process_group(process, signal.SIGTERM)
        _SPAWN_IN_PROGRESS = False
        deferred_signal = _DEFERRED_SHUTDOWN_SIGNAL
        _DEFERRED_SHUTDOWN_SIGNAL = 0
        if deferred_signal:
            _handle_shutdown_signal(deferred_signal, None)
        raise
    _SPAWN_IN_PROGRESS = False
    deferred_signal = _DEFERRED_SHUTDOWN_SIGNAL
    _DEFERRED_SHUTDOWN_SIGNAL = 0
    if deferred_signal:
        _handle_shutdown_signal(deferred_signal, None)
    assert process is not None
    return process


def _process_alive(process: subprocess.Popen[Any]) -> bool:
    try:
        return process.poll() is None
    except Exception:
        return True


def _signal_process_group(process: subprocess.Popen[Any], signum: int) -> None:
    try:
        os.killpg(process.pid, signum)
    except ProcessLookupError:
        pass
    except PermissionError:
        # A just-exited group leader may be a reapable zombie on macOS.  Fall
        # back to the direct child; the next poll/wait reaps it and removes the
        # otherwise misleading process-group liveness result.
        try:
            process.send_signal(signum)
        except (AttributeError, PermissionError, ProcessLookupError):
            pass


def _process_group_alive(process: subprocess.Popen[Any]) -> bool:
    try:
        os.killpg(process.pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _wait_for_process(process: subprocess.Popen[Any], timeout_seconds: float) -> bool:
    try:
        process.wait(timeout=max(0.0, timeout_seconds))
        return True
    except subprocess.TimeoutExpired:
        return not _process_alive(process)
    except (AttributeError, ChildProcessError):
        return not _process_alive(process)


def _terminate_managed_child(
    process: subprocess.Popen[Any] | None,
    *,
    term_timeout_seconds: float = CHILD_TERM_GRACE_SECONDS,
    kill_timeout_seconds: float = CHILD_KILL_WAIT_SECONDS,
) -> None:
    if process is None:
        return
    if not _process_alive(process) and not _process_group_alive(process):
        _unregister_active_child(process)
        return
    _signal_process_group(process, signal.SIGTERM)
    leader_finished = _wait_for_process(process, term_timeout_seconds)
    if leader_finished and _process_group_alive(process):
        group_deadline = time.monotonic() + max(0.0, term_timeout_seconds)
        while _process_group_alive(process) and time.monotonic() < group_deadline:
            time.sleep(min(0.05, max(0.0, group_deadline - time.monotonic())))
    if _process_group_alive(process):
        _signal_process_group(process, signal.SIGKILL)
        _wait_for_process(process, kill_timeout_seconds)
    if not _process_alive(process) and not _process_group_alive(process):
        _unregister_active_child(process)


def _terminate_all_active_children(
    *,
    term_timeout_seconds: float = CHILD_TERM_GRACE_SECONDS,
    kill_timeout_seconds: float = CHILD_KILL_WAIT_SECONDS,
) -> None:
    """Terminate every registered child under one shared bounded deadline."""

    children = _active_children_snapshot()
    for process in children:
        _signal_process_group(process, signal.SIGTERM)

    term_deadline = time.monotonic() + max(0.0, term_timeout_seconds)
    remaining = [process for process in children if _process_group_alive(process)]
    while remaining and time.monotonic() < term_deadline:
        time.sleep(min(0.05, max(0.0, term_deadline - time.monotonic())))
        for process in remaining:
            _process_alive(process)
        remaining = [process for process in remaining if _process_group_alive(process)]

    for process in remaining:
        _signal_process_group(process, signal.SIGKILL)
    kill_deadline = time.monotonic() + max(0.0, kill_timeout_seconds)
    for process in remaining:
        _wait_for_process(process, max(0.0, kill_deadline - time.monotonic()))

    for process in children:
        if not _process_alive(process) and not _process_group_alive(process):
            _unregister_active_child(process)


def _shutdown_runtime(reason: str) -> None:
    """Revoke feed ownership before ensuring no execution child survives."""

    global _CLEANUP_IN_PROGRESS, _SHUTDOWN_REQUESTED, _RUNTIME_OWNS_HEARTBEAT
    _SHUTDOWN_REQUESTED = True
    if _CLEANUP_IN_PROGRESS:
        return
    _CLEANUP_IN_PROGRESS = True
    try:
        if _RUNTIME_OWNS_HEARTBEAT:
            try:
                _revoke_tick_stream_heartbeat(reason)
            except Exception:
                pass
            _RUNTIME_OWNS_HEARTBEAT = False
        _stop_stage931_service(reason)
        _terminate_all_active_children()
    finally:
        _CLEANUP_IN_PROGRESS = False


def _handle_shutdown_signal(signum: int, _frame: Any) -> None:
    global _DEFERRED_SHUTDOWN_SIGNAL, _SHUTDOWN_REQUESTED, _SHUTDOWN_SIGNAL
    if not _SHUTDOWN_SIGNAL:
        _SHUTDOWN_SIGNAL = int(signum)
    _SHUTDOWN_REQUESTED = True
    if _SPAWN_IN_PROGRESS:
        _DEFERRED_SHUTDOWN_SIGNAL = int(signum)
        return
    if _CLEANUP_IN_PROGRESS:
        return
    _shutdown_runtime(f"daemon_signal:{signal.Signals(signum).name}")
    raise DaemonShutdownRequested(signum)


def _activate_runtime_ownership() -> None:
    global _ATEXIT_REGISTERED, _RUNTIME_OWNS_HEARTBEAT
    if _SHUTDOWN_REQUESTED:
        raise DaemonShutdownRequested(_SHUTDOWN_SIGNAL or signal.SIGTERM)
    _RUNTIME_OWNS_HEARTBEAT = True
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)
    signal.signal(signal.SIGINT, _handle_shutdown_signal)
    if not _ATEXIT_REGISTERED:
        atexit.register(_shutdown_runtime, "daemon_atexit")
        _ATEXIT_REGISTERED = True


def _run_command(
    cmd: list[str],
    *,
    timeout_seconds: int,
    log_path: Path,
    label: str,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    started = datetime.now()
    proc = _managed_popen(
        cmd,
        cwd=REPO_ROOT,
        env=env or os.environ.copy(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    timed_out = False
    try:
        try:
            stdout, _ = proc.communicate(timeout=timeout_seconds)
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            _terminate_managed_child(proc)
            try:
                stdout, _ = proc.communicate(timeout=CHILD_KILL_WAIT_SECONDS)
            except subprocess.TimeoutExpired:
                _signal_process_group(proc, signal.SIGKILL)
                stdout = ""
            exit_code = -signal.SIGKILL
            stdout = (stdout or "") + f"\nTIMEOUT: terminated process group after {timeout_seconds}s\n"
    finally:
        _unregister_active_child(proc)
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


def _nonzero_position_symbols(frame: pd.DataFrame) -> list[str]:
    if frame.empty:
        return []
    volume_column = next((name for name in ("volume", "position") if name in frame.columns), "")
    frozen_column = "frozen" if "frozen" in frame.columns else ""
    if volume_column or frozen_column:
        mask = pd.Series(False, index=frame.index)
        if volume_column:
            mask |= pd.to_numeric(frame[volume_column], errors="coerce").fillna(0).abs().gt(1e-12)
        if frozen_column:
            mask |= pd.to_numeric(frame[frozen_column], errors="coerce").fillna(0).abs().gt(1e-12)
        frame = frame[mask]
    return _symbols_from_frame(frame)


def _fresh_broker_position_symbols(max_age_seconds: int) -> tuple[bool, list[str], str]:
    """Return a complete fresh broker position snapshot, or no authority to replace retained symbols."""

    summary = _read_json(READONLY_SUMMARY_PATH)
    age = _age_seconds(summary.get("generated_at"))
    if age is None:
        return False, [], "readonly_summary_missing_generated_at"
    if age < -5.0 or age > max(1, int(max_age_seconds)):
        return False, [], "readonly_summary_stale"
    if _clean(summary.get("status")) != "readonly_snapshots_received":
        return False, [], f"readonly_summary_not_authoritative:{_clean(summary.get('status')) or 'unknown'}"
    snapshot = summary.get("broker_snapshot")
    if not isinstance(snapshot, dict):
        return False, [], "readonly_broker_snapshot_missing"
    if "position_query_last_seen" not in snapshot or "position_query_error_rows" not in snapshot:
        return False, [], "readonly_broker_snapshot_completion_fields_missing"
    state = _clean(snapshot.get("position_snapshot_state"))
    last_seen = bool(snapshot.get("position_query_last_seen"))
    error_rows = _to_int(snapshot.get("position_query_error_rows"), 0)
    callback_rows = _to_int(snapshot.get("position_query_callback_rows"), 0)
    if (
        state not in {"positions_received", "confirmed_flat"}
        or not last_seen
        or error_rows != 0
        or callback_rows <= 0
    ):
        return False, [], f"readonly_broker_snapshot_incomplete:{state or 'unknown'}"
    position_frame = _read_csv_maybe(READONLY_POSITIONS_PATH).drop_duplicates()
    expected_position_rows = _to_int(snapshot.get("position_rows"), -1)
    if expected_position_rows < 0 or expected_position_rows != len(position_frame):
        return False, [], "readonly_position_generation_row_count_mismatch"
    symbols = _nonzero_position_symbols(position_frame)
    expected_rows = _to_int(snapshot.get("nonzero_position_rows"), 0)
    actual_nonzero_rows = 0
    if not position_frame.empty:
        volume = pd.to_numeric(
            position_frame.get("volume", position_frame.get("position", 0.0)),
            errors="coerce",
        )
        frozen = pd.to_numeric(position_frame.get("frozen", 0.0), errors="coerce")
        if isinstance(volume, pd.Series):
            volume = volume.fillna(0.0)
        else:
            volume = pd.Series([float(volume)] * len(position_frame), index=position_frame.index)
        if isinstance(frozen, pd.Series):
            frozen = frozen.fillna(0.0)
        else:
            frozen = pd.Series([float(frozen)] * len(position_frame), index=position_frame.index)
        actual_nonzero_rows = int((volume.abs().gt(1e-12) | frozen.abs().gt(1e-12)).sum())
    if expected_rows != actual_nonzero_rows:
        return False, [], "readonly_position_generation_nonzero_count_mismatch"
    if state == "confirmed_flat":
        if expected_position_rows != 0 or expected_rows != 0:
            return False, [], "readonly_confirmed_flat_contains_position_rows"
        return True, [], state
    if expected_rows <= 0 or not symbols:
        return False, [], "readonly_position_file_missing_for_nonzero_snapshot"
    return True, symbols, state


def _durable_non_done_symbols() -> list[str]:
    symbols: list[str] = []
    pattern = f"{STAGE904_PREFIX}_state_*_{STAGE904_MODEL_TAG}.json"
    for path in sorted(OUTPUT_DIR.glob(pattern)):
        payload = _read_json(path)
        states = payload.get("states")
        if not isinstance(states, dict):
            continue
        for state in states.values():
            if not isinstance(state, dict) or _clean(state.get("phase")).lower() == "done":
                continue
            symbol = _clean(state.get("vt_symbol"))
            if symbol:
                symbols.append(symbol)
    return symbols


def _manifest_symbols() -> list[str]:
    payload = _read_json(TICK_STREAM_MANIFEST_PATH)
    raw = payload.get("symbols")
    if not isinstance(raw, list):
        return []
    return [_clean(item) for item in raw if _clean(item)]


def _watched_symbols(
    extra_symbols: list[str],
    *,
    artifact_paths: tuple[Path, ...] = (
        STAGE901_PENDING_ORDERS_PATH,
        OFFICIAL_LIVE_SIGNAL_PLAN_PATH,
        OFFICIAL_LIVE_CURRENT_POSITIONS_PATH,
    ),
    retained_broker_symbols: set[str] | None = None,
    max_readonly_age_seconds: int = 300,
) -> list[str]:
    symbols: list[str] = []
    for item in extra_symbols:
        text = _clean(item)
        if text:
            symbols.append(text)
    for path in artifact_paths:
        symbols.extend(_symbols_from_frame(_read_csv_maybe(path)))
    symbols.extend(_durable_non_done_symbols())
    snapshot_complete, broker_symbols, _snapshot_status = _fresh_broker_position_symbols(max_readonly_age_seconds)
    if retained_broker_symbols is not None:
        if snapshot_complete:
            retained_broker_symbols.clear()
            retained_broker_symbols.update(broker_symbols)
        symbols.extend(sorted(retained_broker_symbols))
    elif snapshot_complete:
        symbols.extend(broker_symbols)
    seen: set[str] = set()
    result: list[str] = []
    for symbol in symbols:
        if symbol in seen:
            continue
        seen.add(symbol)
        result.append(symbol)
    return result


def _watched_symbols_for_args(args: argparse.Namespace) -> list[str]:
    profile = _execution_profile_for_args(args)
    retained = getattr(args, "_retained_broker_symbols", None)
    if retained is None:
        # A daemon restart must not drop a broker-only contract merely because
        # the first readonly refresh is stale or incomplete.  The next complete
        # snapshot will replace (or clear) this conservative carry-forward set.
        retained = set(_manifest_symbols())
        setattr(args, "_retained_broker_symbols", retained)
    return _watched_symbols(
        getattr(args, "vt_symbol", []),
        artifact_paths=(
            profile.pending_orders_path,
            profile.signal_plan_path,
            profile.current_positions_path,
        ),
        retained_broker_symbols=retained,
        max_readonly_age_seconds=_to_int(getattr(args, "max_snapshot_age_seconds", 300), 300),
    )


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _publish_tick_stream_manifest(symbols: list[str]) -> None:
    _atomic_write_json(
        TICK_STREAM_MANIFEST_PATH,
        {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbols": sorted({_clean(symbol) for symbol in symbols if _clean(symbol)}),
            "owner_pid": os.getpid(),
        },
    )


def _revoke_tick_stream_heartbeat(reason: str) -> None:
    """Invalidate any previous child heartbeat before downstream reducers run."""

    previous = _read_json(TICK_STREAM_HEARTBEAT_PATH)
    # A supervisor revocation is not a committed tick snapshot.  Reusing the
    # child's old generation/hash would let Stage904 accept H1 from the child
    # and H2 from this alternate writer as one stable publication.
    previous.pop("tick_snapshot_commit", None)
    previous.pop("tick_snapshot_generation_uuid", None)
    _atomic_write_json(
        TICK_STREAM_HEARTBEAT_PATH,
        {
            **previous,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "tick_stream_supervisor_revoked",
            "stream_ready": False,
            "transport_ready": False,
            "stopped": True,
            "heartbeat_revision_uuid": str(uuid.uuid4()),
            "tick_snapshot_commit_invalidated": True,
            "supervisor_revocation_reason": reason,
            "supervisor_owner_pid": os.getpid(),
        },
    )


def _start_tick_stream(args: argparse.Namespace, paths: dict[str, Path]) -> subprocess.Popen[str] | None:
    if args.tick_refresh_mode != "stream":
        return None
    symbols = _watched_symbols_for_args(args)
    _publish_tick_stream_manifest(symbols)
    _revoke_tick_stream_heartbeat("tick_stream_child_starting")
    stage_args = [
        "--connect",
        "--stream",
        "--pre-subscribe-wait-seconds",
        str(args.pre_subscribe_wait_seconds),
        "--submit-plan",
        str(OUTPUT_DIR / "__nonexistent_stage930_stream_submit_plan.csv"),
        "--watch-manifest",
        str(TICK_STREAM_MANIFEST_PATH),
        "--journal-path",
        str(TICK_STREAM_JOURNAL_PATH),
        "--heartbeat-path",
        str(TICK_STREAM_HEARTBEAT_PATH),
        "--heartbeat-seconds",
        "1",
        "--parent-pid",
        str(os.getpid()),
    ]
    cmd = _shell_python_command(STAGE608_SCRIPT, stage_args)
    log_handle = paths["command_log"].open("a", encoding="utf-8")
    log_handle.write(f"\n===== stage608_tick_stream started_at={datetime.now():%Y-%m-%d %H:%M:%S} =====\n")
    log_handle.flush()
    try:
        process = _managed_popen(
            cmd,
            cwd=REPO_ROOT,
            text=True,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
    finally:
        log_handle.close()
    return process


def _stop_tick_stream(process: subprocess.Popen[str] | None) -> None:
    _terminate_managed_child(process, term_timeout_seconds=10.0)


def _initialize_tick_stream_supervisor(args: argparse.Namespace, paths: dict[str, Path]) -> dict[str, Any]:
    supervisor: dict[str, Any] = {
        "enabled": int(args.tick_refresh_mode == "stream"),
        "process": None,
        "restart_count": 0,
        "max_restarts": max(0, _to_int(getattr(args, "tick_stream_max_restarts", TICK_STREAM_MAX_RESTARTS), TICK_STREAM_MAX_RESTARTS)),
        "next_restart_monotonic": 0.0,
        "last_exit_code": None,
        "last_start_error": "",
        "restart_phase": "running",
        "restart_blocker": "",
    }
    setattr(args, "_tick_stream_supervisor", supervisor)
    if args.tick_refresh_mode != "stream":
        return supervisor
    try:
        supervisor["process"] = _start_tick_stream(args, paths)
    except Exception as exc:
        supervisor["last_start_error"] = repr(exc)
    return supervisor


def _stop_tick_stream_supervisor(supervisor: dict[str, Any]) -> None:
    _stop_tick_stream(supervisor.get("process"))


def _supervise_tick_stream(
    args: argparse.Namespace,
    paths: dict[str, Path],
    *,
    monotonic: Any = time.monotonic,
) -> dict[str, Any] | None:
    supervisor = getattr(args, "_tick_stream_supervisor", None)
    if not isinstance(supervisor, dict):
        return None
    process = supervisor.get("process")
    exit_code: int | None = None
    if process is not None:
        try:
            exit_code = process.poll()
        except Exception as exc:
            exit_code = -1
            supervisor["last_start_error"] = f"poll_error:{exc!r}"
    if process is not None and exit_code is None:
        return supervisor
    if process is not None:
        supervisor["last_exit_code"] = exit_code
        supervisor["process"] = None
        _unregister_active_child(process)
        if getattr(args, "detector_mode", "legacy-subprocess") == "persistent":
            supervisor["restart_phase"] = "awaiting_detector_drain"
        else:
            _revoke_tick_stream_heartbeat(f"tick_stream_child_exited:{exit_code}")
    if (
        getattr(args, "detector_mode", "legacy-subprocess") == "persistent"
        and supervisor.get("restart_phase") == "awaiting_detector_drain"
    ):
        terminal_heartbeat = _read_json(TICK_STREAM_HEARTBEAT_PATH)
        terminal_blocker = _clean_terminal_tick_heartbeat_blocker(
            terminal_heartbeat
        )
        if terminal_blocker:
            supervisor["restart_phase"] = "blocked_unclean_previous_feed"
            supervisor["restart_blocker"] = terminal_blocker
            return supervisor
        if not _persistent_detector_caught_up_for_heartbeat(terminal_heartbeat):
            supervisor["restart_blocker"] = "detector_cursor_not_at_terminal_watermark"
            return supervisor
        supervisor["restart_phase"] = "ready_to_restart"
        supervisor["restart_blocker"] = ""
    if (
        getattr(args, "detector_mode", "legacy-subprocess") == "persistent"
        and supervisor.get("restart_phase") == "blocked_unclean_previous_feed"
    ):
        return supervisor
    if not supervisor.get("enabled"):
        return supervisor
    if _SHUTDOWN_REQUESTED:
        return supervisor
    restart_count = _to_int(supervisor.get("restart_count"), 0)
    max_restarts = _to_int(supervisor.get("max_restarts"), TICK_STREAM_MAX_RESTARTS)
    if restart_count >= max_restarts:
        return supervisor
    now = float(monotonic())
    if now < float(supervisor.get("next_restart_monotonic", 0.0) or 0.0):
        return supervisor
    supervisor["restart_count"] = restart_count + 1
    backoff = max(0.0, float(getattr(args, "tick_stream_restart_backoff_seconds", TICK_STREAM_RESTART_BACKOFF_SECONDS)))
    supervisor["next_restart_monotonic"] = now + backoff
    try:
        supervisor["process"] = _start_tick_stream(args, paths)
        supervisor["last_start_error"] = ""
        supervisor["restart_phase"] = "running"
    except Exception as exc:
        supervisor["last_start_error"] = repr(exc)
    return supervisor


def _clean_terminal_tick_heartbeat_blocker(
    heartbeat: dict[str, Any],
) -> str:
    if not heartbeat:
        return "terminal_tick_heartbeat_missing"
    expected = {
        "journal_authority_committed": True,
        "journal_session_state": "clean_stopped",
        "clean_shutdown": True,
        "stopped": True,
        "stream_ready": False,
        "transport_ready": False,
        "writer_alive": False,
        "accepting": False,
        "gap_latched": False,
    }
    for field, expected_value in expected.items():
        if heartbeat.get(field) != expected_value:
            return f"terminal_tick_heartbeat_invalid:{field}"
    if heartbeat.get("writer_fault") not in (None, "", {}):
        return "terminal_tick_heartbeat_writer_fault"
    if heartbeat.get("dropped_tick_count") != 0:
        return "terminal_tick_heartbeat_dropped_ticks"
    if heartbeat.get("queue_depth") != 0:
        return "terminal_tick_heartbeat_queue_not_empty"
    feed = _clean(heartbeat.get("feed_session_id"))
    last_sequence = heartbeat.get("last_ingress_sequence")
    sequence = heartbeat.get("durable_ingress_sequence")
    offset = heartbeat.get("durable_journal_byte_offset")
    if (
        not feed
        or type(last_sequence) is not int
        or last_sequence < 0
        or type(sequence) is not int
        or sequence < 0
        or type(offset) is not int
        or offset < 0
        or ((sequence == 0) != (offset == 0))
    ):
        return "terminal_tick_heartbeat_cursor_invalid"
    if last_sequence != sequence:
        return "terminal_tick_heartbeat_not_fully_durable"
    return ""


def _persistent_detector_caught_up_for_heartbeat(
    terminal_heartbeat: dict[str, Any],
) -> bool:
    detector_heartbeat = _read_json(STAGE941_HEARTBEAT_PATH)
    cursor = detector_heartbeat.get("cursor_after")
    if not isinstance(cursor, dict):
        return False
    direct_match = bool(
        _clean(cursor.get("feed_session_id"))
        == _clean(terminal_heartbeat.get("feed_session_id"))
        and cursor.get("ingress_sequence")
        == terminal_heartbeat.get("durable_ingress_sequence")
        and cursor.get("journal_byte_offset")
        == terminal_heartbeat.get("durable_journal_byte_offset")
        and _clean(cursor.get("journal_schema"))
        == _clean(terminal_heartbeat.get("journal_schema"))
    )
    if direct_match:
        return True
    recovery_cursor = _clean_empty_terminal_recovery_cursor(terminal_heartbeat)
    durable_through = detector_heartbeat.get("durable_through")
    if recovery_cursor is None or not isinstance(durable_through, dict):
        return False
    return bool(
        detector_heartbeat.get("ready") is True
        and detector_heartbeat.get("stopped") is False
        and detector_heartbeat.get("cycle_status") == "detector_idle_caught_up"
        and detector_heartbeat.get("tick_count") == 0
        and detector_heartbeat.get("blockers") == []
        and _cursor_payload_matches(cursor, recovery_cursor)
        and _cursor_payload_matches(
            durable_through,
            {
                "feed_session_id": _clean(
                    terminal_heartbeat.get("feed_session_id")
                ),
                "ingress_sequence": 0,
                "journal_byte_offset": 0,
                "journal_schema": _clean(
                    terminal_heartbeat.get("journal_schema")
                ),
            },
        )
    )


def _cursor_payload_matches(
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> bool:
    return bool(
        _clean(actual.get("feed_session_id"))
        == _clean(expected.get("feed_session_id"))
        and actual.get("ingress_sequence") == expected.get("ingress_sequence")
        and actual.get("journal_byte_offset")
        == expected.get("journal_byte_offset")
        and _clean(actual.get("journal_schema"))
        == _clean(expected.get("journal_schema"))
    )


def _clean_empty_terminal_recovery_cursor(
    terminal_heartbeat: dict[str, Any],
) -> dict[str, Any] | None:
    if (
        terminal_heartbeat.get("last_ingress_sequence") != 0
        or terminal_heartbeat.get("durable_ingress_sequence") != 0
        or terminal_heartbeat.get("durable_journal_byte_offset") != 0
        or terminal_heartbeat.get("prior_uncommitted_gaps") != []
    ):
        return None
    feed = _clean(terminal_heartbeat.get("feed_session_id"))
    prior_feed = _clean(
        terminal_heartbeat.get("prior_authoritative_feed_session_id")
    )
    recovery = terminal_heartbeat.get("recovery_previous_durable_cursor")
    if (
        not feed
        or not prior_feed
        or feed == prior_feed
        or not _clean(
            terminal_heartbeat.get("prior_authoritative_journal_segment_path")
        )
        or not _clean(
            terminal_heartbeat.get("prior_authoritative_heartbeat_revision_uuid")
        )
        or terminal_heartbeat.get("prior_authoritative_journal_session_state")
        != "clean_stopped"
        or terminal_heartbeat.get("prior_authoritative_clean_shutdown") is not True
        or not isinstance(recovery, dict)
        or _clean(recovery.get("feed_session_id")) != prior_feed
        or type(recovery.get("ingress_sequence")) is not int
        or recovery.get("ingress_sequence") <= 0
        or type(recovery.get("journal_byte_offset")) is not int
        or recovery.get("journal_byte_offset") <= 0
        or _clean(recovery.get("journal_schema")) != "stage179_framed_v1"
    ):
        return None
    existing = terminal_heartbeat.get(
        "prior_authoritative_empty_feed_sessions",
        [],
    )
    required_fields = {
        "feed_session_id",
        "journal_segment_path",
        "heartbeat_revision_uuid",
        "journal_session_state",
        "clean_shutdown",
        "durable_ingress_sequence",
        "durable_journal_byte_offset",
    }
    if not isinstance(existing, list) or len(existing) > 63:
        return None
    seen: set[str] = set()
    for item in existing:
        if not isinstance(item, dict) or set(item) != required_fields:
            return None
        empty_feed = _clean(item.get("feed_session_id"))
        if (
            not empty_feed
            or empty_feed in {feed, prior_feed}
            or empty_feed in seen
            or not _clean(item.get("journal_segment_path"))
            or not _clean(item.get("heartbeat_revision_uuid"))
            or item.get("journal_session_state") != "clean_stopped"
            or item.get("clean_shutdown") is not True
            or item.get("durable_ingress_sequence") != 0
            or item.get("durable_journal_byte_offset") != 0
        ):
            return None
        seen.add(empty_feed)
    return {
        "feed_session_id": prior_feed,
        "ingress_sequence": recovery["ingress_sequence"],
        "journal_byte_offset": recovery["journal_byte_offset"],
        "journal_schema": "stage179_framed_v1",
    }


def _tick_stream_supervisor_public(supervisor: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(supervisor, dict):
        return {"managed": 0}
    process = supervisor.get("process")
    exit_code: int | None = None
    process_alive = False
    owned_child_guard = False
    pid: int | None = None
    if process is not None:
        pid = getattr(process, "pid", None)
        owned_child_guard = bool(getattr(process, "_stage930_owned_child_guard", False))
        try:
            exit_code = process.poll()
            process_alive = exit_code is None
        except Exception:
            exit_code = -1
    return {
        "managed": 1,
        "enabled": _to_int(supervisor.get("enabled"), 0),
        "process_alive": int(process_alive),
        "process_pid": pid,
        "process_is_owned_child_guard": int(owned_child_guard),
        "process_exit_code": exit_code,
        "restart_count": _to_int(supervisor.get("restart_count"), 0),
        "max_restarts": _to_int(supervisor.get("max_restarts"), TICK_STREAM_MAX_RESTARTS),
        "last_exit_code": supervisor.get("last_exit_code"),
        "last_start_error": _clean(supervisor.get("last_start_error")),
        "restart_phase": _clean(supervisor.get("restart_phase")),
        "restart_blocker": _clean(supervisor.get("restart_blocker")),
    }


def _startup_configuration_blockers(args: argparse.Namespace) -> list[str]:
    if (
        not _profile_uses_intraday_detector(args)
        and getattr(args, "detector_mode", "legacy-subprocess") == "persistent"
    ):
        return ["stage372_profile_forbids_c9_persistent_detector"]
    if getattr(args, "detector_mode", "legacy-subprocess") != "persistent":
        return []
    blockers: list[str] = []
    if getattr(args, "stage179_execution_mode", "legacy-once") != "warm":
        blockers.append("persistent_detector_requires_stage179_warm_executor")
    runtime_profile = getattr(args, "runtime_profile", "offline")
    if (args.mode, args.submit_mode) == ("dry-run", "disabled"):
        if runtime_profile not in {
            ExecutionRuntimeProfile.OFFLINE.value,
            ExecutionRuntimeProfile.PRODUCTION_READONLY.value,
        }:
            blockers.append("persistent_detector_no_submit_profile_invalid")
    elif (args.mode, args.submit_mode) == ("live-real", "live-real"):
        if runtime_profile not in {
            ExecutionRuntimeProfile.SIMNOW.value,
            ExecutionRuntimeProfile.BROKER_TEST.value,
            ExecutionRuntimeProfile.PRODUCTION_LIVE.value,
        }:
            blockers.append("persistent_detector_submit_profile_invalid")
    else:
        blockers.append("persistent_detector_controller_submit_mode_mismatch")
    if args.tick_refresh_mode != "stream":
        blockers.append("persistent_detector_requires_stream_tick_owner")
    if not _startup_target_date(args):
        blockers.append("persistent_detector_requires_explicit_target_date")
    return blockers


def _startup_target_date(args: argparse.Namespace) -> str:
    """Preserve legacy latest-completed resolution; persistent must be pinned."""

    return _clean(getattr(args, "target_date", ""))


def _revoke_detector_heartbeat(*, instance_id: str, reason: str) -> None:
    previous = _read_json(STAGE941_HEARTBEAT_PATH)
    _atomic_write_json(
        STAGE941_HEARTBEAT_PATH,
        {
            **previous,
            "model_tag": "stage941_official_live_c9_detector_v1",
            "detector_instance_id": instance_id,
            "parent_pid": os.getpid(),
            "generated_epoch_ns": time.time_ns(),
            "status": "detector_supervisor_revoked",
            "ready": False,
            "stopped": True,
            "supervisor_revocation_reason": reason,
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
        },
    )


def _start_detector(
    args: argparse.Namespace,
    paths: dict[str, Path],
    *,
    target_date: str,
    instance_id: str,
) -> subprocess.Popen[str]:
    _revoke_detector_heartbeat(
        instance_id=instance_id,
        reason="detector_child_starting",
    )
    cmd = [
        str(PYTHON_PATH),
        str(STAGE941_SCRIPT),
        "--target-date",
        target_date,
        "--tick-stream-heartbeat-path",
        str(TICK_STREAM_HEARTBEAT_PATH),
        "--spool-path",
        str(STAGE941_SPOOL_PATH),
        "--detector-heartbeat-path",
        str(STAGE941_HEARTBEAT_PATH),
        "--poll-seconds",
        str(args.detector_poll_seconds),
        "--max-batch-size",
        str(args.detector_batch_size),
        "--max-tick-age-seconds",
        str(args.fast_tick_age_seconds),
        "--instance-id",
        instance_id,
        "--parent-pid",
        str(os.getpid()),
        "--publish-compat-outputs",
    ]
    log_handle = paths["command_log"].open("a", encoding="utf-8")
    log_handle.write(
        f"\n===== stage941_detector started_at={datetime.now():%Y-%m-%d %H:%M:%S} =====\n"
    )
    log_handle.flush()
    try:
        return _managed_popen(
            cmd,
            cwd=REPO_ROOT,
            text=True,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
    finally:
        log_handle.close()


def _initialize_detector_supervisor(
    args: argparse.Namespace,
    paths: dict[str, Path],
    *,
    target_date: str,
) -> dict[str, Any]:
    blockers = _startup_configuration_blockers(args)
    enabled = int(
        getattr(args, "detector_mode", "legacy-subprocess") == "persistent"
        and not blockers
    )
    supervisor: dict[str, Any] = {
        "enabled": enabled,
        "process": None,
        "instance_id": "",
        "restart_count": 0,
        "max_restarts": max(
            0,
            _to_int(
                getattr(args, "detector_max_restarts", DETECTOR_MAX_RESTARTS),
                DETECTOR_MAX_RESTARTS,
            ),
        ),
        "next_restart_monotonic": 0.0,
        "last_exit_code": None,
        "last_start_error": "",
        "blockers": list(blockers),
        "target_date": target_date,
    }
    setattr(args, "_detector_supervisor", supervisor)
    if not enabled:
        return supervisor
    instance_id = str(uuid.uuid4())
    supervisor["instance_id"] = instance_id
    try:
        supervisor["process"] = _start_detector(
            args,
            paths,
            target_date=target_date,
            instance_id=instance_id,
        )
    except Exception as exc:
        supervisor["last_start_error"] = repr(exc)
    return supervisor


def _stop_detector_supervisor(supervisor: dict[str, Any] | None) -> None:
    if isinstance(supervisor, dict):
        _terminate_managed_child(supervisor.get("process"), term_timeout_seconds=10.0)


def _supervise_detector(
    args: argparse.Namespace,
    paths: dict[str, Path],
    *,
    monotonic: Any = time.monotonic,
) -> dict[str, Any] | None:
    supervisor = getattr(args, "_detector_supervisor", None)
    if not isinstance(supervisor, dict):
        return None
    process = supervisor.get("process")
    exit_code: int | None = None
    if process is not None:
        try:
            exit_code = process.poll()
        except Exception as exc:
            exit_code = -1
            supervisor["last_start_error"] = f"poll_error:{exc!r}"
    if process is not None and exit_code is None:
        return supervisor
    if process is not None:
        supervisor["last_exit_code"] = exit_code
        supervisor["process"] = None
        _unregister_active_child(process)
    if not supervisor.get("enabled") or _SHUTDOWN_REQUESTED:
        return supervisor
    restart_count = _to_int(supervisor.get("restart_count"), 0)
    max_restarts = _to_int(supervisor.get("max_restarts"), DETECTOR_MAX_RESTARTS)
    if restart_count >= max_restarts:
        return supervisor
    now = float(monotonic())
    if now < float(supervisor.get("next_restart_monotonic", 0.0) or 0.0):
        return supervisor
    supervisor["restart_count"] = restart_count + 1
    backoff = max(
        0.0,
        float(
            getattr(
                args,
                "detector_restart_backoff_seconds",
                DETECTOR_RESTART_BACKOFF_SECONDS,
            )
        ),
    )
    supervisor["next_restart_monotonic"] = now + backoff
    instance_id = str(uuid.uuid4())
    supervisor["instance_id"] = instance_id
    try:
        supervisor["process"] = _start_detector(
            args,
            paths,
            target_date=_clean(supervisor.get("target_date")),
            instance_id=instance_id,
        )
        supervisor["last_start_error"] = ""
    except Exception as exc:
        supervisor["last_start_error"] = repr(exc)
    return supervisor


def _detector_supervisor_public(supervisor: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(supervisor, dict):
        return {"managed": 0}
    process = supervisor.get("process")
    alive = False
    exit_code: int | None = None
    if process is not None:
        try:
            exit_code = process.poll()
            alive = exit_code is None
        except Exception:
            exit_code = -1
    return {
        "managed": 1,
        "enabled": _to_int(supervisor.get("enabled"), 0),
        "process_alive": int(alive),
        "process_pid": getattr(process, "pid", None) if process is not None else None,
        "process_exit_code": exit_code,
        "instance_id": _clean(supervisor.get("instance_id")),
        "restart_count": _to_int(supervisor.get("restart_count"), 0),
        "max_restarts": _to_int(supervisor.get("max_restarts"), 0),
        "last_exit_code": supervisor.get("last_exit_code"),
        "last_start_error": _clean(supervisor.get("last_start_error")),
        "blockers": list(supervisor.get("blockers") or []),
    }


def _persistent_detector_fast_lane_status(
    args: argparse.Namespace,
    target_date: str,
    paths: dict[str, Path],
) -> dict[str, Any]:
    heartbeat = _read_json(STAGE941_HEARTBEAT_PATH)
    supervisor = _supervise_detector(args, paths)
    public = _detector_supervisor_public(supervisor)
    blockers: list[str] = []
    expected_instance = _clean(
        supervisor.get("instance_id") if isinstance(supervisor, dict) else ""
    )
    if public.get("process_alive") != 1:
        blockers.append("persistent_detector_process_not_alive")
    if _clean(heartbeat.get("model_tag")) != "stage941_official_live_c9_detector_v1":
        blockers.append("persistent_detector_heartbeat_model_mismatch")
    if _clean(heartbeat.get("detector_instance_id")) != expected_instance:
        blockers.append("persistent_detector_heartbeat_instance_mismatch")
    if heartbeat.get("owner_pid") != public.get("process_pid"):
        blockers.append("persistent_detector_heartbeat_owner_mismatch")
    if heartbeat.get("parent_pid") != os.getpid():
        blockers.append("persistent_detector_heartbeat_parent_mismatch")
    if heartbeat.get("ready") is not True or heartbeat.get("stopped") is not False:
        blockers.append("persistent_detector_heartbeat_unready")
    if _clean(heartbeat.get("target_date")) != target_date:
        blockers.append("persistent_detector_target_date_mismatch")
    if _clean(heartbeat.get("consumer_id")) != "stage941":
        blockers.append("persistent_detector_heartbeat_consumer_mismatch")
    if _clean(heartbeat.get("spool_path")) != str(STAGE941_SPOOL_PATH.resolve()):
        blockers.append("persistent_detector_heartbeat_spool_mismatch")
    generated_epoch_ns = heartbeat.get("generated_epoch_ns")
    if type(generated_epoch_ns) is not int or generated_epoch_ns <= 0:
        blockers.append("persistent_detector_heartbeat_time_invalid")
    else:
        heartbeat_age_seconds = (time.time_ns() - generated_epoch_ns) / 1_000_000_000
        max_heartbeat_age_seconds = max(
            DETECTOR_HEARTBEAT_MIN_MAX_AGE_SECONDS,
            float(getattr(args, "detector_poll_seconds", 0.05))
            * DETECTOR_HEARTBEAT_POLL_MULTIPLIER,
        )
        if heartbeat_age_seconds < -TICK_CLOCK_SKEW_SECONDS:
            blockers.append("persistent_detector_heartbeat_from_future")
        elif heartbeat_age_seconds > max_heartbeat_age_seconds:
            blockers.append("persistent_detector_heartbeat_stale")
    send_order_api_count = heartbeat.get("send_order_api_called_count")
    cancel_order_api_count = heartbeat.get("cancel_order_api_called_count")
    order_api_counts_valid = bool(
        type(send_order_api_count) is int
        and send_order_api_count >= 0
        and type(cancel_order_api_count) is int
        and cancel_order_api_count >= 0
    )
    order_api_count = (
        send_order_api_count + cancel_order_api_count
        if order_api_counts_valid
        else 0
    )
    if not order_api_counts_valid:
        blockers.append("persistent_detector_order_api_count_invalid")
    elif order_api_count:
        blockers.append("persistent_detector_order_api_nonzero")
    return {
        "fast_lane_status": (
            "persistent_detector_ready_no_submit"
            if not blockers
            else "persistent_detector_unready_fail_closed"
        ),
        "target_date": target_date,
        "tick_stream": _managed_tick_stream_status(
            args,
            paths,
            _watched_symbols_for_args(args),
        ),
        "detector_supervisor": public,
        "detector_heartbeat": heartbeat,
        "stage904": {"summary": {"source": "persistent_detector_heartbeat"}},
        "stage905": {
            "summary": {
                "source": "persistent_detector_spool_commit",
                "ready_count": _to_int(heartbeat.get("ready_count"), 0),
                "blocked_count": _to_int(heartbeat.get("blocked_count"), 0),
                "expired_count": _to_int(heartbeat.get("expired_count"), 0),
            }
        },
        "stage931": {
            "submit_status": "persistent_detector_submit_disabled_task8",
            "summary": {
                "send_order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
                "order_api_called_count": 0,
            },
        },
        "reduce_close_ready_count": 0,
        "blockers": blockers,
        "send_order_api_called_count": send_order_api_count,
        "cancel_order_api_called_count": cancel_order_api_count,
        "order_api_called_count": order_api_count,
        "order_api_evidence_complete": int(order_api_counts_valid),
        "order_api_evidence_missing_fields": (
            []
            if order_api_counts_valid
            else ["persistent_detector_order_api_count_invalid"]
        ),
        "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _symbol_tick_freshness(
    heartbeat: dict[str, Any],
    symbols: list[str],
    *,
    max_tick_age_seconds: float,
    clock_skew_seconds: float = TICK_CLOCK_SKEW_SECONDS,
) -> dict[str, Any]:
    watermarks = heartbeat.get("symbol_tick_watermarks")
    if not isinstance(watermarks, dict):
        watermarks = {}
    ages: dict[str, float | None] = {}
    missing: list[str] = []
    stalled: list[str] = []
    future: list[str] = []
    invalid: list[str] = []
    watched = sorted({_clean(symbol) for symbol in symbols if _clean(symbol)})
    for symbol in watched:
        row = watermarks.get(symbol)
        if not isinstance(row, dict):
            missing.append(symbol)
            ages[symbol] = None
            continue
        received_at = _clean(row.get("received_at"))
        sequence = _to_int(row.get("stream_sequence"), 0)
        if not received_at or sequence <= 0:
            missing.append(symbol)
            ages[symbol] = None
            continue
        age = _age_seconds(received_at)
        ages[symbol] = round(age, 3) if age is not None else None
        if age is None:
            invalid.append(symbol)
        elif age < -max(0.0, float(clock_skew_seconds)):
            future.append(symbol)
        elif age > max(0.0, float(max_tick_age_seconds)):
            stalled.append(symbol)
    blocked = sorted(set(missing + stalled + future + invalid))
    return {
        "watched_symbols": watched,
        "symbol_tick_ages_seconds": ages,
        "missing_symbol_ticks": missing,
        "stalled_symbol_ticks": stalled,
        "future_symbol_ticks": future,
        "invalid_symbol_tick_times": invalid,
        "blocked_new_risk_symbols": blocked,
        "max_tick_age_seconds": float(max_tick_age_seconds),
        "allowed_clock_skew_seconds": float(clock_skew_seconds),
        "all_symbols_fresh": int(bool(watched) and not blocked),
    }


def _tick_stream_status(
    symbols: list[str],
    *,
    supervisor: dict[str, Any] | None = None,
    max_tick_age_seconds: float = 10.0,
) -> dict[str, Any]:
    _publish_tick_stream_manifest(symbols)
    heartbeat = _read_json(TICK_STREAM_HEARTBEAT_PATH)
    age = _age_seconds(heartbeat.get("generated_at"))
    supervisor_status = _tick_stream_supervisor_public(supervisor)
    process_gate = True
    heartbeat_pid_matches = True
    if supervisor_status.get("managed"):
        process_gate = bool(supervisor_status.get("process_alive"))
        if supervisor_status.get("process_is_owned_child_guard"):
            # The managed Popen is the guard, while Stage608 truthfully writes
            # its own target PID. Bind the heartbeat to this Stage930 owner PID
            # instead; the kernel pipe separately proves the guard is owned.
            heartbeat_pid_matches = _to_int(heartbeat.get("parent_pid"), -1) == os.getpid()
        else:
            heartbeat_pid_matches = (
                supervisor_status.get("process_pid") is not None
                and _to_int(heartbeat.get("pid"), -1) == _to_int(supervisor_status.get("process_pid"), -2)
            )
    transport_ready = bool(
        heartbeat.get("transport_ready", heartbeat.get("stream_ready"))
        and not heartbeat.get("stopped")
        and age is not None
        and -5.0 <= age <= 3.0
        and process_gate
        and heartbeat_pid_matches
    )
    freshness = _symbol_tick_freshness(
        heartbeat,
        symbols,
        max_tick_age_seconds=max_tick_age_seconds,
    )
    all_symbols_ready = bool(
        heartbeat.get("stream_ready")
        and transport_ready
        and freshness["all_symbols_fresh"]
    )
    if not transport_ready:
        refresh_status = "tick_stream_not_ready_fail_closed"
    elif not all_symbols_ready:
        refresh_status = "tick_stream_symbol_freshness_blocked_new_risk"
    else:
        refresh_status = "tick_stream_ready"
    return {
        "refresh_status": refresh_status,
        "exit_code": 0,
        "symbols": symbols,
        "tick_rows": len(_read_csv_maybe(READONLY_TICKS_PATH)),
        "tick_path": str(READONLY_TICKS_PATH.resolve()),
        "heartbeat_path": str(TICK_STREAM_HEARTBEAT_PATH.resolve()),
        "journal_path": str(TICK_STREAM_JOURNAL_PATH.resolve()),
        "heartbeat_age_seconds": round(age, 3) if age is not None else None,
        "transport_ready": int(transport_ready),
        "stream_ready": int(all_symbols_ready),
        "all_symbols_ready": int(all_symbols_ready),
        "heartbeat_pid_matches_process": int(heartbeat_pid_matches),
        "tick_stream_supervisor": supervisor_status,
        "symbol_tick_freshness": freshness,
        "summary": heartbeat,
        "order_api_called_count": 0,
    }


def _managed_tick_stream_status(args: argparse.Namespace, paths: dict[str, Path], symbols: list[str]) -> dict[str, Any]:
    supervisor = _supervise_tick_stream(args, paths)
    if supervisor is None:
        return _tick_stream_status(
            symbols,
            max_tick_age_seconds=float(args.fast_tick_age_seconds),
        )
    return _tick_stream_status(
        symbols,
        supervisor=supervisor,
        max_tick_age_seconds=float(args.fast_tick_age_seconds),
    )


def _run_tick_refresh(args: argparse.Namespace, target_date: str, symbols: list[str], paths: dict[str, Path]) -> dict[str, Any]:
    if args.tick_refresh_mode == "stream":
        return _managed_tick_stream_status(args, paths, symbols)
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


def _stage904_summary_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE904_PREFIX}_summary_{date_key}_{STAGE904_MODEL_TAG}.json"


def _stage905_summary_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE905_PREFIX}_summary_{date_key}_{STAGE905_MODEL_TAG}.json"


def _run_fast_intraday_lane(
    args: argparse.Namespace,
    target_date: str,
    paths: dict[str, Path],
    *,
    submit_reduce_close: bool = True,
) -> dict[str, Any]:
    """Run the risk reducer while the full controller refreshes slow gates."""
    if not _profile_uses_intraday_detector(args):
        return {
            "fast_lane_status": "intraday_not_applicable_profile_disabled",
            "target_date": target_date,
            "stage904": {
                "summary": {
                    "monitor_status": "intraday_not_applicable_profile_disabled",
                    "order_api_called_count": 0,
                }
            },
            "stage905": {"summary": {"ready_count": 0}},
            "stage931": {"summary": {"order_api_called_count": 0}},
            "reduce_close_ready_count": 0,
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
            "order_api_called_count": 0,
            "order_api_evidence_complete": 1,
            "order_api_evidence_missing_fields": [],
            "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    if getattr(args, "detector_mode", "legacy-subprocess") == "persistent":
        return _persistent_detector_fast_lane_status(
            args,
            target_date,
            paths,
        )
    symbols = _watched_symbols_for_args(args)
    stream = _managed_tick_stream_status(args, paths, symbols)
    monitor_args = [
        "--target-date",
        target_date,
        "--max-tick-age-seconds",
        str(args.fast_tick_age_seconds),
    ]
    if args.mode == "live-real":
        monitor_args.append("--require-broker-fill-price")
    stage904 = _run_command(
        [str(PYTHON_PATH), str(STAGE904_SCRIPT), *monitor_args],
        timeout_seconds=max(5, args.fast_step_timeout_seconds),
        log_path=paths["command_log"],
        label=f"stage904_fast_lane_{target_date}",
    )
    stage904_summary = _read_json(_stage904_summary_path(target_date))
    stage905 = _run_command(
        [
            str(PYTHON_PATH),
            str(STAGE905_SCRIPT),
            "--target-date",
            target_date,
            "--execution-profile",
            _execution_profile_for_args(args).profile_key,
            "--mode",
            "dry-run",
        ],
        timeout_seconds=max(5, args.fast_step_timeout_seconds),
        log_path=paths["command_log"],
        label=f"stage905_fast_lane_{target_date}",
    )
    stage905_summary = _read_json(_stage905_summary_path(target_date))
    reduce_close_ready_count = _ready_reduce_close_count(target_date)
    submit: dict[str, Any]
    if (
        submit_reduce_close
        and reduce_close_ready_count > 0
        and args.submit_mode == "live-real"
    ):
        submit = _run_stage931(args, target_date, paths, reduce_close_only=True)
    else:
        submit = {
            "submit_status": (
                "fast_lane_submit_deferred_single_owner"
                if not submit_reduce_close and reduce_close_ready_count > 0
                else "fast_lane_submit_skipped_no_reduce_close_or_not_live_real"
            ),
            "exit_code": 0,
            "summary": {
                "send_order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
                "order_api_called_count": 0,
            },
        }
    submit_summary = submit.get("summary", {})
    send_order_api_called = _to_int(
        submit_summary.get("send_order_api_called_count"), 0
    )
    cancel_order_api_called = _to_int(
        submit_summary.get("cancel_order_api_called_count"), 0
    )
    order_api_called = _to_int(submit_summary.get("order_api_called_count"), 0)
    return {
        "fast_lane_status": (
            "fast_lane_reduce_close_submit_attempted"
            if submit_reduce_close
            and reduce_close_ready_count > 0
            and args.submit_mode == "live-real"
            else "fast_lane_monitor_complete_submit_deferred_single_owner"
            if not submit_reduce_close and reduce_close_ready_count > 0
            else "fast_lane_monitor_complete"
        ),
        "target_date": target_date,
        "tick_stream": stream,
        "stage904": {**{key: value for key, value in stage904.items() if key != "stdout"}, "summary": stage904_summary},
        "stage905": {**{key: value for key, value in stage905.items() if key != "stdout"}, "summary": stage905_summary},
        "stage931": submit,
        "reduce_close_ready_count": reduce_close_ready_count,
        "send_order_api_called_count": send_order_api_called,
        "cancel_order_api_called_count": cancel_order_api_called,
        "order_api_called_count": order_api_called,
        "order_api_evidence_complete": int(
            type(submit_summary.get("send_order_api_called_count")) is int
            and type(submit_summary.get("cancel_order_api_called_count")) is int
        ),
        "order_api_evidence_missing_fields": [
            field
            for field in (
                "send_order_api_called_count",
                "cancel_order_api_called_count",
            )
            if type(submit_summary.get(field)) is not int
        ],
        "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _safe_run_fast_intraday_lane(
    args: argparse.Namespace,
    target_date: str,
    paths: dict[str, Path],
    *,
    submit_reduce_close: bool = True,
) -> dict[str, Any]:
    """Keep one bad reducer iteration from killing the owner daemon/child."""

    try:
        return _run_fast_intraday_lane(
            args,
            target_date,
            paths,
            submit_reduce_close=submit_reduce_close,
        )
    except Exception as exc:
        return {
            "fast_lane_status": "fast_lane_exception_fail_closed",
            "target_date": target_date,
            "exception": repr(exc),
            "reduce_close_ready_count": 0,
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
            "order_api_called_count": 0,
            "order_api_evidence_complete": 0,
            "order_api_evidence_missing_fields": [
                "fast_lane_exception_order_api_evidence_unavailable"
            ],
            "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }


def _record_fast_lane_event(paths: dict[str, Path], result: dict[str, Any], *, phase: str) -> None:
    event_path = paths.get("events_ndjson")
    if event_path is None:
        return
    _append_event(event_path, {"event_type": "stage930_fast_lane", "fast_lane_phase": phase, **result})


def _run_idle_fast_lane(
    args: argparse.Namespace,
    target_date: str,
    paths: dict[str, Path],
    *,
    wait_seconds: float,
    monotonic: Any = time.monotonic,
    sleeper: Any = time.sleep,
) -> dict[str, Any]:
    """Keep the risk reducer active during the old inter-cycle sleep window."""
    if not _profile_uses_intraday_detector(args):
        return {
            "run_count": 0,
            "order_api_called_count": 0,
            "recent_runs": [],
            "fast_lane_status": "intraday_not_applicable_profile_disabled",
        }
    deadline = monotonic() + max(0.0, float(wait_seconds))
    recent_runs: list[dict[str, Any]] = []
    run_count = 0
    send_order_api_called_count = 0
    cancel_order_api_called_count = 0
    order_api_called_count = 0
    order_api_evidence_missing_fields: list[str] = []
    while monotonic() < deadline:
        if _market_execution_session_active():
            result = _safe_run_fast_intraday_lane(args, target_date, paths)
            run_count += 1
            send_order_api_called_count += _to_int(
                result.get("send_order_api_called_count"), 0
            )
            cancel_order_api_called_count += _to_int(
                result.get("cancel_order_api_called_count"), 0
            )
            order_api_called_count += _to_int(result.get("order_api_called_count"), 0)
            if result.get("order_api_evidence_complete") != 1:
                details = result.get("order_api_evidence_missing_fields")
                order_api_evidence_missing_fields.extend(
                    list(details)
                    if isinstance(details, list) and details
                    else ["fast_lane_order_api_evidence_incomplete"]
                )
            recent_runs.append(result)
            recent_runs = recent_runs[-FAST_LANE_RECENT_RUN_LIMIT:]
            try:
                _record_fast_lane_event(paths, result, phase="between_slow_cycles")
            except Exception as exc:
                result["event_record_exception"] = repr(exc)
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        sleeper(min(max(0.1, float(args.fast_poll_seconds)), remaining))
    return {
        "run_count": run_count,
        "send_order_api_called_count": send_order_api_called_count,
        "cancel_order_api_called_count": cancel_order_api_called_count,
        "order_api_called_count": order_api_called_count,
        "order_api_evidence_complete": int(
            not order_api_evidence_missing_fields
        ),
        "order_api_evidence_missing_fields": order_api_evidence_missing_fields,
        "recent_runs": recent_runs,
    }


def _run_command_with_fast_lane(
    cmd: list[str],
    *,
    timeout_seconds: int,
    log_path: Path,
    label: str,
    args: argparse.Namespace,
    target_date: str,
    paths: dict[str, Path],
    env: dict[str, str] | None = None,
    submit_reduce_close: bool = True,
) -> dict[str, Any]:
    """Run one slow child while preserving continuous monitor ownership."""

    started = datetime.now()
    fast_lane_runs: list[dict[str, Any]] = []
    fast_lane_run_count = 0
    fast_lane_send_order_api_called_count = 0
    fast_lane_cancel_order_api_called_count = 0
    fast_lane_order_api_called_count = 0
    fast_lane_order_api_evidence_missing_fields: list[str] = []
    timed_out = False
    proc: subprocess.Popen[Any] | None = None
    stdout = ""
    try:
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as output:
            proc = _managed_popen(
                cmd,
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=output,
                stderr=subprocess.STDOUT,
            )
            deadline = time.monotonic() + timeout_seconds
            next_fast_run = time.monotonic()
            while proc.poll() is None:
                now_monotonic = time.monotonic()
                if now_monotonic >= deadline:
                    timed_out = True
                    _terminate_managed_child(proc)
                    break
                if now_monotonic >= next_fast_run and _market_execution_session_active():
                    fast_result = _safe_run_fast_intraday_lane(
                        args,
                        target_date,
                        paths,
                        submit_reduce_close=submit_reduce_close,
                    )
                    fast_lane_run_count += 1
                    fast_lane_send_order_api_called_count += _to_int(
                        fast_result.get("send_order_api_called_count"), 0
                    )
                    fast_lane_cancel_order_api_called_count += _to_int(
                        fast_result.get("cancel_order_api_called_count"), 0
                    )
                    fast_lane_order_api_called_count += _to_int(
                        fast_result.get("order_api_called_count"), 0
                    )
                    if fast_result.get("order_api_evidence_complete") != 1:
                        details = fast_result.get(
                            "order_api_evidence_missing_fields"
                        )
                        fast_lane_order_api_evidence_missing_fields.extend(
                            list(details)
                            if isinstance(details, list) and details
                            else ["fast_lane_order_api_evidence_incomplete"]
                        )
                    fast_lane_runs.append(fast_result)
                    fast_lane_runs = fast_lane_runs[-FAST_LANE_RECENT_RUN_LIMIT:]
                    try:
                        _record_fast_lane_event(paths, fast_result, phase=f"during_{label}")
                    except Exception as exc:
                        fast_result["event_record_exception"] = repr(exc)
                    next_fast_run = time.monotonic() + max(
                        0.5, float(args.fast_poll_seconds)
                    )
                time.sleep(0.1)
            output.seek(0)
            stdout = output.read()
    finally:
        if proc is not None and proc.poll() is None:
            _terminate_managed_child(proc)
        _unregister_active_child(proc)
    exit_code = -signal.SIGKILL if timed_out else int((proc.returncode if proc else 1) or 0)
    if timed_out:
        stdout += f"\nTIMEOUT: terminated process group after {timeout_seconds}s\n"
    finished = datetime.now()
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(
            f"\n===== {label} started_at={started:%Y-%m-%d %H:%M:%S} "
            f"exit={exit_code} timed_out={int(timed_out)} =====\n"
        )
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
        "fast_lane_runs": fast_lane_runs,
        "fast_lane_run_count": fast_lane_run_count,
        "fast_lane_send_order_api_called_count": fast_lane_send_order_api_called_count,
        "fast_lane_cancel_order_api_called_count": fast_lane_cancel_order_api_called_count,
        "fast_lane_order_api_called_count": fast_lane_order_api_called_count,
        "fast_lane_order_api_evidence_complete": int(
            not fast_lane_order_api_evidence_missing_fields
        ),
        "fast_lane_order_api_evidence_missing_fields": fast_lane_order_api_evidence_missing_fields,
    }


def _run_stage903(args: argparse.Namespace, target_date: str, paths: dict[str, Path]) -> dict[str, Any]:
    cmd = [
        str(PYTHON_PATH),
        str(STAGE903_SCRIPT),
        "--execution-profile",
        _execution_profile_for_args(args).profile_key,
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
    if args.tick_refresh_mode == "stream":
        cmd.extend(["--intraday-tick-refresh-mode", "skip", "--intraday-execution-mode", "external"])
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
    if (
        args.tick_refresh_mode != "stream"
        or not _profile_uses_intraday_detector(args)
    ):
        result = _run_command(
            cmd,
            timeout_seconds=args.controller_timeout_seconds,
            log_path=paths["command_log"],
            label="stage903_controller",
            env=env,
        )
    else:
        fast_target_date = target_date or _default_target_date()
        result = _run_command_with_fast_lane(
            cmd,
            timeout_seconds=args.controller_timeout_seconds,
            log_path=paths["command_log"],
            label="stage903_controller",
            args=args,
            target_date=fast_target_date,
            paths=paths,
            env=env,
            submit_reduce_close=True,
        )
    summary = _extract_json_from_stdout(result.get("stdout", ""))
    return {
        **{key: value for key, value in result.items() if key != "stdout"},
        "summary": summary,
    }


def _run_stage935_preflight(args: argparse.Namespace, paths: dict[str, Path]) -> dict[str, Any]:
    mode = str(args.ai_pool_preflight_mode)
    if mode == "skip":
        return {
            "preflight_status": "ai_pool_preflight_skipped",
            "exit_code": 0,
            "automation_status": "skipped",
            "allowed_to_continue": 1,
        }
    cmd = [
        str(PYTHON_PATH),
        str(STAGE935_SCRIPT),
        "--mode",
        "run" if mode == "run" else "check",
        "--email-policy",
        "changes" if mode == "run" else "never",
    ]
    if args.tick_refresh_mode == "stream":
        result = _run_command_with_fast_lane(
            cmd,
            timeout_seconds=args.ai_pool_timeout_seconds,
            log_path=paths["command_log"],
            label="stage935_ai_pool_preflight",
            args=args,
            target_date=args.target_date or _default_target_date(),
            paths=paths,
            submit_reduce_close=True,
        )
    else:
        result = _run_command(
            cmd,
            timeout_seconds=args.ai_pool_timeout_seconds,
            log_path=paths["command_log"],
            label="stage935_ai_pool_preflight",
        )
    summary = _extract_json_from_stdout(result.get("stdout", ""))
    status = str(summary.get("automation_status", ""))
    allowed = int(result.get("exit_code") == 0 and status in {"monthly_ai_pool_already_current", "monthly_ai_pool_updated"})
    return {
        **{key: value for key, value in result.items() if key != "stdout"},
        "preflight_status": "ai_pool_preflight_passed" if allowed else "ai_pool_preflight_blocked",
        "automation_status": status,
        "action": summary.get("action", ""),
        "expected_eval_date": summary.get("expected_eval_date", ""),
        "current_eval_date": summary.get("current_eval_date", ""),
        "resolved_target_date": summary.get("resolved_target_date", ""),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "order_api_called_count": summary.get("order_api_called_count", 0),
        "allowed_to_continue": allowed,
        "summary": summary,
    }


def _run_stage927(args: argparse.Namespace, target_date: str, paths: dict[str, Path]) -> dict[str, Any]:
    cmd = [str(PYTHON_PATH), str(STAGE927_SCRIPT), "--target-date", target_date, "--confirm-live-real", args.confirm_live_real]
    if args.tick_refresh_mode == "stream":
        result = _run_command_with_fast_lane(
            cmd,
            timeout_seconds=120,
            log_path=paths["command_log"],
            label=f"stage927_arming_{target_date}",
            args=args,
            target_date=target_date,
            paths=paths,
            submit_reduce_close=True,
        )
    else:
        result = _run_command(cmd, timeout_seconds=120, log_path=paths["command_log"], label=f"stage927_arming_{target_date}")
    path = OUTPUT_DIR / f"qmt_roll_stage927_official_live_real_submit_arming_gate_summary_{target_date.replace('-', '')}_stage927_official_live_real_submit_arming_gate_v1.json"
    return {**result, "summary": _read_json(path)}


def _run_stage931(
    args: argparse.Namespace,
    target_date: str,
    paths: dict[str, Path],
    *,
    reduce_close_only: bool = False,
) -> dict[str, Any]:
    if args.submit_mode != "live-real":
        return {
            "submit_status": "submit_adapter_skipped",
            "exit_code": 0,
            "summary": {
                "send_order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
                "order_api_called_count": 0,
            },
        }
    stage_args = [
        "--target-date",
        target_date,
        "--execution-profile",
        _execution_profile_for_args(args).profile_key,
        "--mode",
        "live-real",
        "--confirm-live-real",
        args.confirm_live_real,
        "--max-orders",
        str(args.max_submit_orders),
        "--fill-wait-seconds",
        str(args.fill_wait_seconds),
    ]
    if reduce_close_only:
        stage_args.append("--reduce-close-only")
    cmd = _shell_python_command(STAGE931_SCRIPT, stage_args)
    if args.tick_refresh_mode == "stream" and not reduce_close_only:
        result = _run_command_with_fast_lane(
            cmd,
            timeout_seconds=args.submit_timeout_seconds,
            log_path=paths["command_log"],
            label=f"stage931_submit_{target_date}",
            args=args,
            target_date=target_date,
            paths=paths,
            submit_reduce_close=False,
        )
    else:
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


def _stage179_order_scope(runtime_profile: str) -> OrderScope:
    return {
        ExecutionRuntimeProfile.OFFLINE.value: OrderScope.NONE,
        ExecutionRuntimeProfile.PRODUCTION_READONLY.value: OrderScope.READONLY,
        ExecutionRuntimeProfile.SIMNOW.value: OrderScope.TEST,
        ExecutionRuntimeProfile.BROKER_TEST.value: OrderScope.TEST,
        ExecutionRuntimeProfile.PRODUCTION_LIVE.value: OrderScope.LIVE,
    }[str(runtime_profile)]


def _stage179_runtime(args: argparse.Namespace) -> Any:
    runtime_root = _clean(getattr(args, "stage179_runtime_root", ""))
    return resolve_runtime_profile(
        profile=getattr(args, "runtime_profile", "offline"),
        order_scope=_stage179_order_scope(
            getattr(args, "runtime_profile", "offline")
        ),
        output_root=Path(runtime_root) if runtime_root else None,
        repo_root=REPO_ROOT,
    )


def _start_stage931_service(args: argparse.Namespace) -> subprocess.Popen[Any] | None:
    global _STAGE931_SERVICE_PROCESS, _STAGE931_SERVICE_RUNTIME
    if getattr(args, "stage179_execution_mode", "legacy-once") != "warm":
        return None
    if _STAGE931_SERVICE_PROCESS is not None:
        if _process_alive(_STAGE931_SERVICE_PROCESS):
            return _STAGE931_SERVICE_PROCESS
        _unregister_active_child(_STAGE931_SERVICE_PROCESS)
        _STAGE931_SERVICE_PROCESS = None

    runtime = _stage179_runtime(args)
    stage_args = [
        "--command",
        "serve",
        "--stage179-warm-executor",
        "--execution-profile",
        _execution_profile_for_args(args).profile_key,
        "--mode",
        "live-real" if args.submit_mode == "live-real" else "dry-run",
        "--runtime-profile",
        runtime.profile.value,
        "--order-scope",
        runtime.order_scope.value,
        "--stage179-runtime-root",
        str(runtime.output_root),
        "--target-date",
        _startup_target_date(args),
    ]
    release_manifest = _clean(getattr(args, "release_manifest", ""))
    activation_receipt = _clean(getattr(args, "activation_receipt", ""))
    if release_manifest:
        stage_args.extend(["--stage179-release-manifest", release_manifest])
    if activation_receipt:
        stage_args.extend(["--stage179-activation-receipt", activation_receipt])
    if _clean(getattr(args, "confirm_live_real", "")):
        stage_args.extend(
            ["--confirm-live-real", _clean(args.confirm_live_real)]
        )
    if _clean(getattr(args, "confirm_stage179_activation", "")):
        stage_args.extend(
            [
                "--confirm-stage179-activation",
                _clean(args.confirm_stage179_activation),
            ]
        )
    _STAGE931_SERVICE_RUNTIME = runtime
    _STAGE931_SERVICE_PROCESS = _managed_popen(
        [str(PYTHON_PATH), str(STAGE931_SCRIPT), *stage_args],
        text=True,
    )
    return _STAGE931_SERVICE_PROCESS


def _no_submit_prewarm_order_evidence(readiness: dict[str, Any]) -> dict[str, Any]:
    required_zero_fields = (
        "spool_opened",
        "ctp_module_loaded",
        "send_order_api_called_count",
        "cancel_order_api_called_count",
        "order_api_called_count",
    )
    missing = [
        field
        for field in required_zero_fields
        if type(readiness.get(field)) is not int or readiness.get(field) != 0
    ]
    if readiness.get("service_kind") != "no_submit_prewarm":
        missing.append("service_kind")
    return {
        "complete": int(not missing),
        "missing_fields": missing,
        "send_order_api_called_count": readiness.get(
            "send_order_api_called_count"
        ),
        "cancel_order_api_called_count": readiness.get(
            "cancel_order_api_called_count"
        ),
        "order_api_called_count": readiness.get("order_api_called_count"),
    }


def _status_stage931_service(args: argparse.Namespace) -> dict[str, Any]:
    process = _STAGE931_SERVICE_PROCESS
    runtime = _STAGE931_SERVICE_RUNTIME or _stage179_runtime(args)
    readiness = _read_json(runtime.readiness_path)
    expires_epoch_ns = _to_int(readiness.get("expires_epoch_ns"), 0)
    blockers: list[str] = []
    if process is None or not _process_alive(process):
        blockers.append("stage931_warm_service_not_running")
    expected_status = (
        "ready" if args.submit_mode == "live-real" else "prewarm_no_submit"
    )
    if readiness.get("status") != expected_status:
        blockers.append(
            f"stage931_warm_readiness_not_ready:{readiness.get('status', '')}"
        )
    if expires_epoch_ns <= time.time_ns():
        blockers.append("stage931_warm_readiness_expired")
    if _clean(readiness.get("runtime_profile")) != runtime.profile.value:
        blockers.append("stage931_warm_readiness_profile_mismatch")
    no_submit_evidence = _no_submit_prewarm_order_evidence(readiness)
    if args.submit_mode != "live-real" and not no_submit_evidence["complete"]:
        blockers.append("stage931_no_submit_order_evidence_incomplete")
    return {
        "submit_status": (
            (
                "warm_executor_ready"
                if args.submit_mode == "live-real"
                else "warm_executor_no_submit_ready"
            )
            if not blockers
            else "warm_executor_blocked"
        ),
        "exit_code": 0 if not blockers else 2,
        "process_pid": getattr(process, "pid", None),
        "runtime_profile": runtime.profile.value,
        "readiness_path": str(runtime.readiness_path),
        "readiness": readiness,
        "blockers": blockers,
        "summary": {
            "order_api_called_count": no_submit_evidence[
                "order_api_called_count"
            ],
            "send_order_api_called_count": no_submit_evidence[
                "send_order_api_called_count"
            ],
            "cancel_order_api_called_count": no_submit_evidence[
                "cancel_order_api_called_count"
            ],
            "order_api_evidence_complete": no_submit_evidence["complete"],
            "order_api_evidence_missing_fields": no_submit_evidence[
                "missing_fields"
            ],
        },
    }


def _wake_stage931_service(args: argparse.Namespace) -> bool:
    runtime = _STAGE931_SERVICE_RUNTIME or _stage179_runtime(args)
    return notify_executor(wakeup_socket_path(runtime.spool_path))


def _revoke_stage931_submit_authorization(
    args: argparse.Namespace,
    reason: str,
) -> None:
    runtime = _STAGE931_SERVICE_RUNTIME or _stage179_runtime(args)
    revoke_submit_authorization(
        submit_authorization_path(runtime.output_root),
        reason=reason,
        revoked_epoch_ns=time.time_ns(),
    )


def _publish_stage931_submit_authorization(
    args: argparse.Namespace,
    *,
    target_date: str,
    controller_summary: dict[str, Any],
    stage927_summary: dict[str, Any],
    tick_gate: dict[str, Any],
    service_status: dict[str, Any],
    reduce_close_only: bool,
) -> dict[str, Any]:
    runtime = _STAGE931_SERVICE_RUNTIME or _stage179_runtime(args)
    readiness = service_status.get("readiness")
    if service_status.get("submit_status") != "warm_executor_ready":
        return {"authorized": 0, "blocker": "stage931_warm_service_not_ready"}
    if not isinstance(readiness, dict):
        return {"authorized": 0, "blocker": "stage931_warm_readiness_missing"}
    service_generation = _clean(readiness.get("service_generation"))
    connection_generation = _clean(readiness.get("connection_generation"))
    if not service_generation or not connection_generation:
        return {
            "authorized": 0,
            "blocker": "stage931_warm_readiness_generation_missing",
        }
    ready = _read_csv_maybe(_stage905_intents_path(target_date))
    if ready.empty or "executor_status" not in ready.columns:
        return {
            "authorized": 0,
            "blocker": "stage931_authorized_intents_missing",
        }
    ready = ready[
        ready["executor_status"]
        .fillna("")
        .astype(str)
        .eq("dry_run_order_request_payload_ready")
    ].copy()
    expected_ready_count = _to_int(
        controller_summary.get("stage905_ready_count"),
        -1,
    )
    if expected_ready_count <= 0 or len(ready) != expected_ready_count:
        return {
            "authorized": 0,
            "blocker": (
                "stage931_authorized_intent_count_mismatch:"
                f"{len(ready)}!={expected_ready_count}"
            ),
        }
    authorized_intents: list[dict[str, str]] = []
    seen_intent_ids: set[str] = set()
    for _, row in ready.iterrows():
        intent_id = _clean(row.get("intent_id"))
        payload_sha256 = _clean(row.get("payload_sha256")).lower()
        intent_kind = _clean(row.get("offset")).lower()
        row_target_date = _clean(row.get("target_date"))
        if not intent_id or intent_id in seen_intent_ids:
            return {
                "authorized": 0,
                "blocker": "stage931_authorized_intent_identity_invalid",
            }
        if len(payload_sha256) != 64 or any(
            character not in "0123456789abcdef"
            for character in payload_sha256
        ):
            return {
                "authorized": 0,
                "blocker": "stage931_authorized_intent_payload_sha256_invalid",
            }
        if intent_kind not in {"open", "close"}:
            return {
                "authorized": 0,
                "blocker": "stage931_authorized_intent_kind_invalid",
            }
        if row_target_date != target_date:
            return {
                "authorized": 0,
                "blocker": "stage931_authorized_intent_target_date_mismatch",
            }
        if reduce_close_only and intent_kind != "close":
            return {
                "authorized": 0,
                "blocker": "stage931_reduce_close_authorization_contains_open",
            }
        seen_intent_ids.add(intent_id)
        authorized_intents.append(
            {
                "intent_id": intent_id,
                "payload_sha256": payload_sha256,
                "intent_kind": intent_kind,
            }
        )
    issued_epoch_ns = time.time_ns()
    ttl_seconds = min(
        60.0,
        max(5.0, float(getattr(args, "poll_seconds", 30)) + 5.0),
    )
    readiness_expires_epoch_ns = _to_int(
        readiness.get("expires_epoch_ns"),
        0,
    )
    controller_age_seconds = _age_seconds(
        controller_summary.get("generated_at")
    )
    stage927_age_seconds = _age_seconds(
        stage927_summary.get("generated_at")
    )
    controller_fresh_seconds = min(
        60.0,
        max(5.0, float(getattr(args, "max_snapshot_age_seconds", 60))),
    )
    evidence_expiries: list[tuple[str, int]] = []
    for evidence_name, age_seconds in (
        ("controller", controller_age_seconds),
        ("stage927", stage927_age_seconds),
    ):
        if (
            age_seconds is None
            or age_seconds < -TICK_CLOCK_SKEW_SECONDS
            or age_seconds >= controller_fresh_seconds
        ):
            return {
                "authorized": 0,
                "blocker": f"stage931_{evidence_name}_evidence_stale",
            }
        evidence_expiries.append(
            (
                evidence_name,
                issued_epoch_ns
                + int(
                    (controller_fresh_seconds - max(0.0, age_seconds))
                    * 1_000_000_000
                ),
            )
        )
    tick_expires_epoch_ns = issued_epoch_ns + int(ttl_seconds * 1_000_000_000)
    if not reduce_close_only:
        tick_summary = tick_gate.get("summary")
        tick_age_seconds = _age_seconds(
            tick_summary.get("generated_at")
            if isinstance(tick_summary, dict)
            else None
        )
        if (
            tick_age_seconds is None
            or tick_age_seconds < -TICK_CLOCK_SKEW_SECONDS
            or tick_age_seconds >= 3.0
        ):
            return {
                "authorized": 0,
                "blocker": "stage931_tick_watermark_evidence_stale",
            }
        tick_expires_epoch_ns = issued_epoch_ns + int(
            (3.0 - max(0.0, tick_age_seconds)) * 1_000_000_000
        )
        evidence_expiries.append(("tick", tick_expires_epoch_ns))
    expires_epoch_ns = min(
        issued_epoch_ns + int(ttl_seconds * 1_000_000_000),
        readiness_expires_epoch_ns,
        *(expiry for _, expiry in evidence_expiries),
    )
    if expires_epoch_ns <= issued_epoch_ns:
        return {
            "authorized": 0,
            "blocker": "stage931_warm_readiness_expired_before_authorization",
        }
    payload = publish_submit_authorization(
        path=submit_authorization_path(runtime.output_root),
        target_date=target_date,
        execution_profile=_execution_profile_for_args(args).profile_key,
        runtime_profile=runtime.profile.value,
        order_scope=runtime.order_scope.value,
        service_generation=service_generation,
        connection_generation=connection_generation,
        cycle_id=uuid.uuid4().hex,
        intent_scope="reduce_close_only" if reduce_close_only else "all",
        authorized_intents=authorized_intents,
        issued_epoch_ns=issued_epoch_ns,
        expires_epoch_ns=expires_epoch_ns,
        controller_evidence={
            **controller_summary,
            "expires_epoch_ns": dict(evidence_expiries)["controller"],
        },
        stage927_evidence={
            **stage927_summary,
            "expires_epoch_ns": dict(evidence_expiries)["stage927"],
        },
        broker_gate_evidence=readiness,
        tick_watermark_evidence={
            **tick_gate,
            "expires_epoch_ns": tick_expires_epoch_ns,
        },
    )
    validation_blockers = validate_submit_authorization(
        path=submit_authorization_path(runtime.output_root),
        target_date=target_date,
        execution_profile=_execution_profile_for_args(args).profile_key,
        runtime_profile=runtime.profile.value,
        order_scope=runtime.order_scope.value,
        service_generation=service_generation,
        connection_generation=connection_generation,
        now_epoch_ns=time.time_ns(),
    )
    if validation_blockers:
        revoke_submit_authorization(
            submit_authorization_path(runtime.output_root),
            reason="stage930_published_authorization_validation_failed",
            revoked_epoch_ns=time.time_ns(),
        )
        return {
            "authorized": 0,
            "blocker": ";".join(validation_blockers),
        }
    return {
        "authorized": 1,
        "authorization_path": str(
            submit_authorization_path(runtime.output_root)
        ),
        "cycle_id": payload["cycle_id"],
        "expires_epoch_ns": payload["expires_epoch_ns"],
        "intent_scope": payload["intent_scope"],
        "authorized_intent_count": len(authorized_intents),
    }


def _stop_stage931_service(reason: str) -> None:
    global _STAGE931_SERVICE_PROCESS, _STAGE931_SERVICE_RUNTIME
    process = _STAGE931_SERVICE_PROCESS
    runtime = _STAGE931_SERVICE_RUNTIME
    if runtime is not None:
        try:
            revoke_submit_authorization(
                submit_authorization_path(runtime.output_root),
                reason=reason,
                revoked_epoch_ns=time.time_ns(),
            )
        except Exception:
            pass
        readiness = _read_json(runtime.readiness_path)
        try:
            revoke_readiness(
                runtime.readiness_path,
                service_generation=(
                    _clean(readiness.get("service_generation"))
                    or "stage930-owner"
                ),
                reason=reason,
                revoked_epoch_ns=time.time_ns(),
            )
        except Exception:
            pass
    _terminate_managed_child(process)
    _STAGE931_SERVICE_PROCESS = None
    _STAGE931_SERVICE_RUNTIME = None


def _current_session_name_list() -> list[str]:
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
    return names


def _current_session_names() -> str:
    return ",".join(_current_session_name_list())


def _market_execution_session_active() -> bool:
    config = build_phase_d_config()
    now = datetime.now().time()
    for session in config.sessions:
        start_h, start_m = [int(part) for part in session.start.split(":", 1)]
        end_h, end_m = [int(part) for part in session.end.split(":", 1)]
        start = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
        end = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
        if start <= end:
            active = start <= now <= end
        else:
            active = now >= start or now <= end
        if active and session.role == "market_and_execution":
            return True
    return False


def _build_report(summary: dict[str, Any]) -> str:
    latest = summary.get("latest_cycle", {}) or {}
    controller = latest.get("stage903", {}).get("summary", {}) if isinstance(latest.get("stage903"), dict) else {}
    tick = latest.get("tick_refresh", {}) if isinstance(latest.get("tick_refresh"), dict) else {}
    arming = latest.get("stage927", {}).get("summary", {}) if isinstance(latest.get("stage927"), dict) else {}
    submit = latest.get("stage931", {}).get("summary", {}) if isinstance(latest.get("stage931"), dict) else {}
    ai_pool = summary.get("ai_pool_preflight") or {}
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
            f"- AI池检查：`{ai_pool.get('automation_status', '')}`，expected `{ai_pool.get('expected_eval_date', '')}`，current `{ai_pool.get('current_eval_date', '')}`",
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
    _atomic_write_text(paths["summary_json"], text)
    _atomic_write_text(LATEST_SUMMARY_PATH, text)
    report = _build_report(summary)
    _atomic_write_text(paths["report_md"], report)
    _atomic_write_text(LATEST_REPORT_PATH, report)
    heartbeat = {
        "heartbeat_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "daemon_status": summary.get("daemon_status"),
        "target_date": summary.get("target_date"),
        "cycle_count": summary.get("cycle_count"),
        "current_session_names": summary.get("current_session_names"),
        "order_api_called_count": summary.get("order_api_called_count"),
        "summary_path": str(paths["summary_json"].resolve()),
    }
    _atomic_write_json(LATEST_HEARTBEAT_PATH, heartbeat)


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


def _ready_reduce_close_count(target_date: str) -> int:
    intents = _read_csv_maybe(_stage905_intents_path(target_date))
    if intents.empty or "executor_status" not in intents.columns:
        return 0
    ready = intents[intents["executor_status"].astype(str).eq("dry_run_order_request_payload_ready")].copy()
    if ready.empty:
        return 0
    sources = ready.get("source", pd.Series([""] * len(ready))).fillna("").astype(str)
    offsets = ready.get("offset", pd.Series([""] * len(ready))).fillna("").astype(str).str.lower()
    return int((sources.eq("stage904_c9_intraday_close") & offsets.eq("close")).sum())


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
    tick_result: dict[str, Any] | None = None,
) -> list[str]:
    blockers: list[str] = []
    close_only_reduce_risk = _ready_intents_close_only(target_date)
    if args.submit_mode != "live-real":
        blockers.append(f"submit_mode_not_live_real:{args.submit_mode}")
    if args.mode != "live-real":
        blockers.append(f"controller_mode_not_live_real:{args.mode}")
    if ready_count <= 0:
        blockers.append(f"ready_count={ready_count}")
    if _to_int(getattr(args, "ai_pool_preflight_allowed", 1), 1) != 1 and not close_only_reduce_risk:
        blockers.append("ai_pool_preflight_blocked_new_risk_but_reduce_close_remains_allowed")
    if (
        tick_result is not None
        and _to_int(tick_result.get("all_symbols_ready"), 0) != 1
        and not close_only_reduce_risk
    ):
        blocked_symbols = (
            (tick_result.get("symbol_tick_freshness") or {}).get("blocked_new_risk_symbols")
            if isinstance(tick_result.get("symbol_tick_freshness"), dict)
            else []
        )
        blockers.append(
            "tick_stream_symbols_not_fresh_for_new_risk:"
            + ",".join(map(str, blocked_symbols or []))
        )
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


def _tick_result_ingress_epoch_ns(tick_result: dict[str, Any]) -> int | None:
    if (
        tick_result.get("refresh_status") != "tick_stream_ready"
        or tick_result.get("transport_ready") != 1
        or tick_result.get("stream_ready") != 1
        or tick_result.get("all_symbols_ready") != 1
        or tick_result.get("heartbeat_pid_matches_process") != 1
    ):
        return None
    summary = tick_result.get("summary")
    if not isinstance(summary, dict):
        return None
    latest_ticks = summary.get("symbol_tick_watermarks")
    if not isinstance(latest_ticks, dict):
        latest_ticks = summary.get("latest_ticks")
    if not isinstance(latest_ticks, dict):
        return None
    values = [
        row.get("ingress_epoch_ns")
        for row in latest_ticks.values()
        if isinstance(row, dict)
        and type(row.get("ingress_epoch_ns")) is int
        and row.get("ingress_epoch_ns") > 0
    ]
    return max(values) if values else None


def _tick_result_durable_epoch_ns(tick_result: dict[str, Any]) -> int | None:
    summary = tick_result.get("summary")
    if not isinstance(summary, dict):
        return None
    value = summary.get("generated_epoch_ns")
    return value if type(value) is int and value > 0 else None


def _session_timing_evidence(cycles: list[dict[str, Any]]) -> dict[str, int | None]:
    for cycle in cycles:
        ingress = cycle.get("open_minute_tick_ingress_epoch_ns")
        if type(ingress) is not int or ingress <= 0:
            continue
        return {
            "open_minute_tick_ingress_epoch_ns": ingress,
            "open_minute_tick_cycle_started_epoch_ns": cycle.get(
                "cycle_started_epoch_ns"
            ),
            "open_minute_tick_durable_epoch_ns": cycle.get(
                "open_minute_tick_durable_epoch_ns"
            ),
            "open_minute_tick_cycle_finished_epoch_ns": cycle.get(
                "cycle_finished_epoch_ns"
            ),
        }
    return {
        "open_minute_tick_ingress_epoch_ns": None,
        "open_minute_tick_cycle_started_epoch_ns": None,
        "open_minute_tick_durable_epoch_ns": None,
        "open_minute_tick_cycle_finished_epoch_ns": None,
    }


def _readonly_qualification_cycle(
    cycles: list[dict[str, Any]],
) -> dict[str, Any] | None:
    qualified: dict[str, Any] | None = None
    for cycle in cycles:
        stage903 = cycle.get("stage903")
        summary = (
            stage903.get("summary")
            if isinstance(stage903, dict)
            and isinstance(stage903.get("summary"), dict)
            else {}
        )
        if (
            summary.get("stage914_exit_code") == 0
            and summary.get("stage914_preflight_status")
            == "production_readonly_preflight_passed"
            and summary.get("stage914_blocking_failure_count") == 0
            and summary.get("stage907_refresh_status")
            == "readonly_refresh_completed_snapshot_ready"
            and summary.get("stage907_readonly_status_after")
            == "readonly_snapshots_received"
            and summary.get("stage907_position_snapshot_state_after")
            in {"confirmed_flat", "positions_received"}
        ):
            qualified = cycle
    return qualified


def _missing_order_api_evidence_fields(
    *,
    stage903_result: dict[str, Any],
    stage927_result: dict[str, Any],
    stage931_result: dict[str, Any],
    post_submit_reduce_close: dict[str, Any],
) -> list[str]:
    missing: list[str] = []
    for label, result in (
        ("stage903", stage903_result),
        ("stage931", stage931_result),
        ("post_submit_reduce_close", post_submit_reduce_close),
    ):
        summary = result.get("summary")
        if not isinstance(summary, dict):
            summary = {}
        for field in (
            "send_order_api_called_count",
            "cancel_order_api_called_count",
        ):
            value = summary.get(field)
            if type(value) is not int or value < 0:
                missing.append(f"{label}.summary.{field}")
        if label == "stage903":
            for field in (
                "send_order_api_attempted_count",
                "cancel_order_api_attempted_count",
            ):
                value = summary.get(field)
                if type(value) is not int or value != 0:
                    missing.append(f"{label}.summary.{field}")
            if summary.get("order_api_evidence_complete") != 1:
                missing.append(f"{label}.summary.order_api_evidence_complete")
        elif label == "stage931" and summary.get(
            "order_api_evidence_complete"
        ) != 1:
            missing.append(f"{label}.summary.order_api_evidence_complete")
    for label, result in (
        ("stage903", stage903_result),
        ("stage927", stage927_result),
        ("stage931", stage931_result),
    ):
        if "fast_lane_run_count" not in result:
            continue
        for field in (
            "fast_lane_send_order_api_called_count",
            "fast_lane_cancel_order_api_called_count",
        ):
            value = result.get(field)
            if type(value) is not int or value < 0:
                missing.append(f"{label}.{field}")
        if result.get("fast_lane_order_api_evidence_complete") != 1:
            missing.append(
                f"{label}.fast_lane_order_api_evidence_complete"
            )
    return missing


def run_cycle(args: argparse.Namespace, target_date: str, paths: dict[str, Path]) -> dict[str, Any]:
    cycle_started_epoch_ns = time.time_ns()
    warm_execution = (
        getattr(args, "stage179_execution_mode", "legacy-once") == "warm"
    )
    if warm_execution:
        _start_stage931_service(args)
        _revoke_stage931_submit_authorization(args, "stage930_cycle_refreshing")
    symbols = _watched_symbols_for_args(args)
    if _market_execution_session_active():
        tick_result = _run_tick_refresh(args, target_date, symbols, paths)
    else:
        tick_result = {
            "refresh_status": "tick_refresh_skipped_outside_market_session",
            "exit_code": 0,
            "symbols": symbols,
            "tick_rows": len(_read_csv_maybe(READONLY_TICKS_PATH)),
            "tick_path": str(READONLY_TICKS_PATH.resolve()),
            "order_api_called_count": 0,
        }
    stage903_result = _run_stage903(args, target_date, paths)
    controller_summary = stage903_result.get("summary", {}) if isinstance(stage903_result.get("summary"), dict) else {}
    resolved_target_date = _clean(controller_summary.get("target_date")) or target_date
    ready_count = _to_int(controller_summary.get("stage905_ready_count"), 0)
    stage927_result = _run_stage927(args, resolved_target_date, paths) if resolved_target_date and (args.mode == "live-real" or args.submit_mode == "live-real") else {
        "summary": {"arming_status": "stage927_skipped_dry_run", "real_submit_permitted": 0},
        "exit_code": 0,
    }
    stage927_summary = stage927_result.get("summary", {}) if isinstance(stage927_result.get("summary"), dict) else {}
    pre_submit_tick_gate = tick_result
    if args.tick_refresh_mode == "stream":
        # Slow controller/arming work may outlive one symbol's freshness
        # window.  Re-read the live per-symbol watermarks immediately before
        # Stage931; never authorize a new-risk submit from the cycle-start
        # snapshot alone.
        pre_submit_tick_gate = _managed_tick_stream_status(
            args,
            paths,
            _watched_symbols_for_args(args),
        )
    submit_blockers = _stage931_submit_blockers(
        args,
        resolved_target_date,
        controller_summary,
        stage927_summary,
        ready_count,
        pre_submit_tick_gate,
    )
    if warm_execution:
        stage931_result = _status_stage931_service(args)
        authorization: dict[str, Any]
        if submit_blockers:
            _revoke_stage931_submit_authorization(
                args,
                "stage930_cycle_submit_blocked",
            )
            authorization = {
                "authorized": 0,
                "blocker": ";".join(submit_blockers),
            }
        else:
            authorization = _publish_stage931_submit_authorization(
                args,
                target_date=resolved_target_date,
                controller_summary=controller_summary,
                stage927_summary=stage927_summary,
                tick_gate=pre_submit_tick_gate,
                service_status=stage931_result,
                reduce_close_only=_ready_intents_close_only(
                    resolved_target_date
                ),
            )
            if not authorization.get("authorized"):
                submit_blockers.append(
                    str(
                        authorization.get(
                            "blocker",
                            "stage931_submit_authorization_not_published",
                        )
                    )
                )
                _revoke_stage931_submit_authorization(
                    args,
                    "stage930_cycle_authorization_publish_blocked",
                )
        stage931_result["submit_authorization"] = authorization
        stage931_result["wake_socket_notified"] = int(
            bool(authorization.get("authorized"))
            and _wake_stage931_service(args)
        )
    elif not submit_blockers:
        stage931_result = _run_stage931(args, resolved_target_date, paths)
    else:
        stage931_result = {
            "submit_status": "submit_adapter_skipped_not_armed_or_no_ready",
            "exit_code": 0,
            "skip_reason": ";".join(submit_blockers),
        }
    post_submit_reduce_close: dict[str, Any] = {
        "submit_status": "post_submit_reduce_close_not_needed",
        "exit_code": 0,
        "summary": {
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
            "order_api_called_count": 0,
        },
    }
    if (
        resolved_target_date
        and args.submit_mode == "live-real"
        and not warm_execution
        and _ready_reduce_close_count(resolved_target_date) > 0
    ):
        # The normal adapter owns submission while it runs; its companion fast
        # loop only monitors.  Drain any protective close latched during that
        # window immediately after the owner exits.
        post_submit_reduce_close = _run_stage931(
            args,
            resolved_target_date,
            paths,
            reduce_close_only=True,
        )
    order_api_called = (
        _to_int(stage903_result.get("summary", {}).get("order_api_called_count"), 0)
        + _to_int(stage903_result.get("fast_lane_order_api_called_count"), 0)
        + _to_int(stage927_result.get("summary", {}).get("order_api_called_count"), 0)
        + _to_int(stage927_result.get("fast_lane_order_api_called_count"), 0)
        + _to_int(stage931_result.get("summary", {}).get("order_api_called_count"), 0)
        + _to_int(stage931_result.get("fast_lane_order_api_called_count"), 0)
        + _to_int(post_submit_reduce_close.get("summary", {}).get("order_api_called_count"), 0)
    )
    send_order_api_called = (
        _to_int(stage903_result.get("summary", {}).get("send_order_api_called_count"), 0)
        + _to_int(stage903_result.get("fast_lane_send_order_api_called_count"), 0)
        + _to_int(stage927_result.get("fast_lane_send_order_api_called_count"), 0)
        + _to_int(stage931_result.get("summary", {}).get("send_order_api_called_count"), 0)
        + _to_int(stage931_result.get("fast_lane_send_order_api_called_count"), 0)
        + _to_int(post_submit_reduce_close.get("summary", {}).get("send_order_api_called_count"), 0)
    )
    cancel_order_api_called = (
        _to_int(stage903_result.get("summary", {}).get("cancel_order_api_called_count"), 0)
        + _to_int(stage903_result.get("fast_lane_cancel_order_api_called_count"), 0)
        + _to_int(stage927_result.get("fast_lane_cancel_order_api_called_count"), 0)
        + _to_int(stage931_result.get("summary", {}).get("cancel_order_api_called_count"), 0)
        + _to_int(stage931_result.get("fast_lane_cancel_order_api_called_count"), 0)
        + _to_int(post_submit_reduce_close.get("summary", {}).get("cancel_order_api_called_count"), 0)
    )
    cycle_finished_epoch_ns = time.time_ns()
    open_minute_tick_ingress_epoch_ns = _tick_result_ingress_epoch_ns(
        tick_result
    )
    open_minute_tick_durable_epoch_ns = _tick_result_durable_epoch_ns(
        tick_result
    )
    order_api_evidence_missing_fields = _missing_order_api_evidence_fields(
        stage903_result=stage903_result,
        stage927_result=stage927_result,
        stage931_result=stage931_result,
        post_submit_reduce_close=post_submit_reduce_close,
    )
    return {
        "cycle_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cycle_started_epoch_ns": cycle_started_epoch_ns,
        "cycle_finished_epoch_ns": cycle_finished_epoch_ns,
        "open_minute_tick_ingress_epoch_ns": open_minute_tick_ingress_epoch_ns,
        "open_minute_tick_durable_epoch_ns": (
            open_minute_tick_durable_epoch_ns
            if open_minute_tick_ingress_epoch_ns is not None
            else None
        ),
        "runtime_profile": getattr(args, "runtime_profile", "offline"),
        "target_date": resolved_target_date,
        "requested_target_date": target_date,
        "watched_symbols": symbols,
        "tick_refresh": tick_result,
        "pre_submit_tick_gate": pre_submit_tick_gate,
        "stage903": stage903_result,
        "stage927": stage927_result,
        "stage931": stage931_result,
        "post_submit_reduce_close": post_submit_reduce_close,
        "stage931_submit_blockers": submit_blockers,
        "send_order_api_called_count": send_order_api_called,
        "cancel_order_api_called_count": cancel_order_api_called,
        "order_api_called_count": order_api_called,
        "order_api_evidence_complete": int(
            not order_api_evidence_missing_fields
        ),
        "order_api_evidence_missing_fields": order_api_evidence_missing_fields,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="C9 official live session daemon with tick refresh and submit gating.")
    parser.add_argument(
        "--execution-profile",
        choices=[item.value for item in ExecutionStrategyMode],
        default=ExecutionStrategyMode.STAGE372_20W.value,
    )
    parser.add_argument("--mode", choices=["dry-run", "live-real"], default="dry-run")
    parser.add_argument("--submit-mode", choices=["disabled", "live-real"], default="disabled")
    parser.add_argument("--target-date", default="")
    parser.add_argument("--duration-seconds", type=int, default=0)
    parser.add_argument("--max-cycles", type=int, default=1)
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--tick-refresh-mode", choices=["skip", "plan-only", "refresh", "stream"], default="stream")
    parser.add_argument("--tick-wait-seconds", type=int, default=12)
    parser.add_argument("--pre-subscribe-wait-seconds", type=int, default=4)
    parser.add_argument("--readonly-refresh-mode", choices=["plan-only", "refresh", "auto"], default="auto")
    parser.add_argument("--readonly-wait-seconds", type=int, default=30)
    parser.add_argument("--shadow-refresh-mode", choices=["plan-only", "run", "auto"], default="auto")
    parser.add_argument("--stage251-mode", choices=["skip", "auto", "force"], default="skip")
    parser.add_argument("--max-snapshot-age-seconds", type=int, default=300)
    parser.add_argument("--controller-timeout-seconds", type=int, default=1200)
    parser.add_argument("--submit-timeout-seconds", type=int, default=180)
    parser.add_argument(
        "--max-submit-orders",
        type=int,
        default=DEFAULT_MAX_SUBMIT_LOGICAL_INTENTS,
        help="Maximum logical Stage905 intents per Stage931 run; exchange offset children use the Phase-D physical order limit.",
    )
    parser.add_argument("--fill-wait-seconds", type=int, default=8)
    parser.add_argument("--fast-poll-seconds", type=float, default=1.0)
    parser.add_argument("--fast-tick-age-seconds", type=int, default=10)
    parser.add_argument("--fast-step-timeout-seconds", type=int, default=20)
    parser.add_argument("--tick-stream-max-restarts", type=int, default=TICK_STREAM_MAX_RESTARTS)
    parser.add_argument("--tick-stream-restart-backoff-seconds", type=float, default=TICK_STREAM_RESTART_BACKOFF_SECONDS)
    parser.add_argument(
        "--detector-mode",
        choices=["legacy-subprocess", "persistent"],
        default="legacy-subprocess",
    )
    parser.add_argument("--detector-poll-seconds", type=float, default=0.05)
    parser.add_argument("--detector-batch-size", type=int, default=1024)
    parser.add_argument(
        "--detector-max-restarts",
        type=int,
        default=DETECTOR_MAX_RESTARTS,
    )
    parser.add_argument(
        "--detector-restart-backoff-seconds",
        type=float,
        default=DETECTOR_RESTART_BACKOFF_SECONDS,
    )
    parser.add_argument("--max-consecutive-cycle-errors", type=int, default=3)
    parser.add_argument(
        "--ai-pool-preflight-mode",
        choices=["skip", "check", "run"],
        default="check",
        help="The session-critical path only checks the monthly pool; an explicit run performs the slower update.",
    )
    parser.add_argument("--ai-pool-timeout-seconds", type=int, default=3600)
    parser.add_argument(
        "--stop-all-on-ai-pool-failure",
        action="store_true",
        help="Legacy behavior. Default keeps the daemon alive for risk-reducing closes while blocking opens.",
    )
    parser.add_argument("--confirm-live-real", default="")
    parser.add_argument(
        "--stage179-execution-mode",
        choices=("legacy-once", "warm"),
        default="legacy-once",
    )
    parser.add_argument(
        "--runtime-profile",
        choices=[item.value for item in ExecutionRuntimeProfile],
        default=ExecutionRuntimeProfile.OFFLINE.value,
    )
    parser.add_argument("--release-manifest", default="")
    parser.add_argument("--activation-receipt", default="")
    parser.add_argument("--stage179-runtime-root", default="")
    parser.add_argument("--confirm-stage179-activation", default="")
    parser.add_argument("--vt-symbol", action="append", default=[])
    parser.add_argument("--require-current-session-name", action="append", default=[])
    return parser


def _initialize_runtime_services(
    args: argparse.Namespace,
    paths: dict[str, Path],
    *,
    target_date: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    tick_stream_supervisor = _initialize_tick_stream_supervisor(args, paths)
    detector_supervisor = _initialize_detector_supervisor(
        args,
        paths,
        target_date=target_date,
    )
    ai_pool_preflight = _run_stage935_preflight(args, paths)
    return tick_stream_supervisor, detector_supervisor, ai_pool_preflight


def main() -> None:
    daemon_started_epoch_ns = time.time_ns()
    args = _build_parser().parse_args()
    execution_profile = _execution_profile_for_args(args)
    runtime_profile = getattr(args, "runtime_profile", "offline")
    startup_blockers = _startup_configuration_blockers(args)
    if startup_blockers:
        print(
            json.dumps(
                {
                    "model_tag": MODEL_TAG,
                    "daemon_status": "daemon_blocked_startup_configuration",
                    "mode": args.mode,
                    "submit_mode": args.submit_mode,
                    "detector_mode": args.detector_mode,
                    "startup_blockers": startup_blockers,
                    "order_api_called_count": 0,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        raise SystemExit(2)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    required_sessions = [_clean(item) for item in args.require_current_session_name if _clean(item)]
    current_sessions = _current_session_name_list()
    if required_sessions and not (set(required_sessions) & set(current_sessions)):
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        paths = _paths(run_id)
        summary = {
            "model_tag": MODEL_TAG,
            "run_id": run_id,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "execution_profile": _execution_profile_for_args(args).profile_key,
            "official_live_version": _execution_profile_for_args(args).official_version,
            "mode": args.mode,
            "submit_mode": args.submit_mode,
            "target_date": args.target_date,
            "requested_target_date": args.target_date,
            "cycle_count": 0,
            "daemon_status": "daemon_blocked_outside_required_session",
            "required_current_session_names": required_sessions,
            "current_session_names": ",".join(current_sessions),
            "order_api_called_count": 0,
            "latest_cycle": {
                "cycle_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "target_date": args.target_date,
                "stage903": {"summary": {"controller_status": "stage930_outside_required_session_fail_closed"}},
                "stage927": {"summary": {"arming_status": "stage927_skipped_outside_required_session", "real_submit_permitted": 0}},
                "stage931": {"summary": {"adapter_status": "stage931_skipped_outside_required_session"}},
                "order_api_called_count": 0,
            },
            "outputs": {key: str(value.resolve()) for key, value in paths.items()},
            "latest_outputs": {
                "summary_json": str(LATEST_SUMMARY_PATH.resolve()),
                "report_md": str(LATEST_REPORT_PATH.resolve()),
                "heartbeat_json": str(LATEST_HEARTBEAT_PATH.resolve()),
                "events_ndjson": str(LATEST_EVENT_LOG_PATH.resolve()),
            },
            "judgement": {
                "overfit_before": "否。会话名称限制只约束 launchd 启动窗口，不改策略参数。",
                "continue_before": "是。防止日盘 label 在盘后手动 kickstart 后持锁挡住夜盘 label。",
                "overfit_after": "否。失败时只 fail-closed，不反馈优化。",
                "continue_after": "是。需要在正确交易会话由对应 launchd label 启动守护进程。",
            },
        }
        _write_outputs(paths, summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
        sys.exit(2)
    lock_handle = _acquire_singleton_lock()
    if lock_handle is None:
        summary = {
            "model_tag": MODEL_TAG,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "execution_profile": _execution_profile_for_args(args).profile_key,
            "official_live_version": _execution_profile_for_args(args).official_version,
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
    launchd_provenance = _launchd_provenance(daemon_started_epoch_ns)
    _activate_runtime_ownership()
    _start_stage931_service(args)
    # Market-data coverage starts before the AI-pool check.  The pool governs
    # new risk, but must not delay establishing the read-only risk feed.
    effective_target_date = _startup_target_date(args)
    (
        tick_stream_supervisor,
        detector_supervisor,
        ai_pool_preflight,
    ) = _initialize_runtime_services(
        args,
        paths,
        target_date=effective_target_date,
    )
    args.ai_pool_preflight_allowed = int(ai_pool_preflight.get("allowed_to_continue", 0))
    if args.ai_pool_preflight_allowed != 1 and args.stop_all_on_ai_pool_failure:
        summary = {
            "model_tag": MODEL_TAG,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "execution_profile": _execution_profile_for_args(args).profile_key,
            "official_live_version": _execution_profile_for_args(args).official_version,
            "mode": args.mode,
            "submit_mode": args.submit_mode,
            "detector_mode": args.detector_mode,
            "target_date": args.target_date,
            "requested_target_date": args.target_date,
            "cycle_count": 0,
            "daemon_status": "daemon_blocked_ai_pool_preflight_fail_closed",
            "consecutive_cycle_errors": 0,
            "current_session_names": _current_session_names(),
            "order_api_called_count": 0,
            "ai_pool_preflight": ai_pool_preflight,
            "detector_supervisor": _detector_supervisor_public(
                detector_supervisor
            ),
            "latest_cycle": {
                "cycle_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "target_date": args.target_date,
                "stage903": {"summary": {"controller_status": "stage930_ai_pool_preflight_blocked_fail_closed"}},
                "stage927": {"summary": {"arming_status": "stage927_skipped_ai_pool_preflight_blocked", "real_submit_permitted": 0}},
                "stage931": {"summary": {"adapter_status": "stage931_skipped_ai_pool_preflight_blocked"}},
                "order_api_called_count": 0,
            },
            "outputs": {key: str(value.resolve()) for key, value in paths.items()},
            "latest_outputs": {
                "summary_json": str(LATEST_SUMMARY_PATH.resolve()),
                "report_md": str(LATEST_REPORT_PATH.resolve()),
                "heartbeat_json": str(LATEST_HEARTBEAT_PATH.resolve()),
                "events_ndjson": str(LATEST_EVENT_LOG_PATH.resolve()),
            },
            "judgement": {
                "overfit_before": "否。AI池预检查只验证执行输入是否为最新完整月，不改策略参数。",
                "continue_before": "是。会话守护不能在AI池 stale 时继续生成新开仓。",
                "overfit_after": "否。失败时仅 fail-closed，不反馈优化。",
                "continue_after": "是。需要修复 Stage935 或数据链路后再启动会话守护。",
            },
        }
        _write_outputs(paths, summary)
        send_official_live_email_notification(
            subject=(
                f"[C9/15w][异常] AI池预检查失败 守护未启动 "
                f"expected={ai_pool_preflight.get('expected_eval_date', '')} current={ai_pool_preflight.get('current_eval_date', '')}"
            ),
            body="\n".join(
                [
                    "结论：AI池预检查失败，Stage930 未启动交易循环，避免用旧AI池生成新开仓。",
                    f"状态：{ai_pool_preflight.get('automation_status', '')}",
                    f"应为：{ai_pool_preflight.get('expected_eval_date', '')}",
                    f"当前：{ai_pool_preflight.get('current_eval_date', '')}",
                    f"阻断：{';'.join(map(str, ai_pool_preflight.get('blockers') or [])) or '无'}",
                    "下单API：0",
                ]
            ),
            event_type="stage930_ai_pool_preflight_blocked",
            severity="critical",
            attachments=[paths["report_md"], paths["summary_json"]],
            metadata={"ai_pool_preflight": ai_pool_preflight, "order_api_called_count": 0},
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
        sys.exit(2)
    target_date = effective_target_date
    started = time.monotonic()
    cycles: list[dict[str, Any]] = []
    email_notifications: list[dict[str, Any]] = []
    sent_email_keys: set[str] = set()
    status = "daemon_started"
    consecutive_errors = 0

    while True:
        cycle_attempt_started_epoch_ns = time.time_ns()
        try:
            cycle = run_cycle(args, target_date, paths)
            consecutive_errors = 0
            status = "daemon_running"
        except Exception as exc:
            consecutive_errors += 1
            cycle = {
                "cycle_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "cycle_started_epoch_ns": cycle_attempt_started_epoch_ns,
                "cycle_finished_epoch_ns": time.time_ns(),
                "open_minute_tick_ingress_epoch_ns": None,
                "open_minute_tick_durable_epoch_ns": None,
                "runtime_profile": runtime_profile,
                "target_date": target_date,
                "watched_symbols": _watched_symbols_for_args(args),
                "tick_refresh": {"refresh_status": "cycle_exception_before_or_during_refresh"},
                "stage903": {"summary": {"controller_status": "stage930_cycle_exception_fail_closed"}},
                "stage927": {"summary": {"arming_status": "stage927_skipped_cycle_exception", "real_submit_permitted": 0}},
                "stage931": {"summary": {"adapter_status": "stage931_skipped_cycle_exception"}},
                "send_order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
                "order_api_called_count": 0,
                "order_api_evidence_complete": 0,
                "order_api_evidence_missing_fields": [
                    "cycle_exception_order_api_evidence_unavailable"
                ],
                "cycle_exception": repr(exc),
                "consecutive_cycle_errors": consecutive_errors,
            }
            status = "daemon_cycle_exception_fail_closed"
        cycles.append(cycle)
        _append_event(paths["events_ndjson"], {"event_type": "stage930_cycle", **cycle})
        total_send_order_api = sum(
            _to_int(item.get("send_order_api_called_count"), 0)
            for item in cycles
        )
        total_cancel_order_api = sum(
            _to_int(item.get("cancel_order_api_called_count"), 0)
            for item in cycles
        )
        total_order_api = sum(_to_int(item.get("order_api_called_count"), 0) for item in cycles)
        order_api_evidence_missing_fields = [
            f"cycle[{index}]:{field}"
            for index, item in enumerate(cycles)
            for field in (
                item.get("order_api_evidence_missing_fields")
                if isinstance(
                    item.get("order_api_evidence_missing_fields"), list
                )
                else ["order_api_evidence_missing_fields_invalid"]
            )
        ]
        if any(
            item.get("order_api_evidence_complete") != 1 for item in cycles
        ) and not order_api_evidence_missing_fields:
            order_api_evidence_missing_fields.append(
                "cycle_order_api_evidence_incomplete_without_detail"
            )
        session_timing = _session_timing_evidence(cycles)
        summary = {
            "model_tag": MODEL_TAG,
            "run_id": run_id,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "daemon_started_epoch_ns": daemon_started_epoch_ns,
            "launchd_provenance": launchd_provenance,
            "execution_profile": execution_profile.profile_key,
            "official_live_version": execution_profile.official_version,
            "capital": execution_profile.capital,
            "capital_label": execution_profile.capital_label,
            "runtime_profile": runtime_profile,
            "mode": args.mode,
            "submit_mode": args.submit_mode,
            "detector_mode": args.detector_mode,
            "target_date": _clean(cycle.get("target_date")) or target_date,
            "requested_target_date": target_date,
            "cycle_count": len(cycles),
            "daemon_status": status,
            "consecutive_cycle_errors": consecutive_errors,
            "current_session_names": _current_session_names(),
            "send_order_api_called_count": total_send_order_api,
            "cancel_order_api_called_count": total_cancel_order_api,
            "order_api_called_count": total_order_api,
            "order_api_evidence_complete": int(
                not order_api_evidence_missing_fields
            ),
            "order_api_evidence_missing_fields": order_api_evidence_missing_fields,
            **session_timing,
            "ai_pool_preflight": ai_pool_preflight,
            "detector_supervisor": _detector_supervisor_public(
                detector_supervisor
            ),
            "readonly_qualification_cycle": _readonly_qualification_cycle(
                cycles
            ),
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
        wait_seconds = max(0.5, float(args.poll_seconds))
        if args.duration_seconds:
            wait_seconds = min(wait_seconds, max(0.0, args.duration_seconds - (time.monotonic() - started)))
        try:
            idle_fast_lane = _run_idle_fast_lane(
                args,
                _clean(cycle.get("target_date")) or target_date or _default_target_date(),
                paths,
                wait_seconds=wait_seconds,
            )
        except Exception as exc:
            idle_fast_lane = {
                "run_count": 0,
                "order_api_called_count": 0,
                "recent_runs": [],
                "idle_fast_lane_exception": repr(exc),
            }
            try:
                _append_event(
                    paths["events_ndjson"],
                    {
                        "event_type": "stage930_idle_fast_lane_exception",
                        "exception": repr(exc),
                        "target_date": _clean(cycle.get("target_date")) or target_date,
                    },
                )
            except Exception:
                pass
        if _to_int(idle_fast_lane.get("run_count"), 0) > 0:
            cycle["between_cycle_fast_lane"] = idle_fast_lane
            cycle["send_order_api_called_count"] = _to_int(
                cycle.get("send_order_api_called_count"), 0
            ) + _to_int(idle_fast_lane.get("send_order_api_called_count"), 0)
            cycle["cancel_order_api_called_count"] = _to_int(
                cycle.get("cancel_order_api_called_count"), 0
            ) + _to_int(idle_fast_lane.get("cancel_order_api_called_count"), 0)
            cycle["order_api_called_count"] = _to_int(cycle.get("order_api_called_count"), 0) + _to_int(
                idle_fast_lane.get("order_api_called_count"), 0
            )
            idle_fast_lane_exceptions = [
                str(item.get("fast_lane_status"))
                for item in idle_fast_lane.get("recent_runs", [])
                if isinstance(item, dict)
                and item.get("fast_lane_status")
                == "fast_lane_exception_fail_closed"
            ]
            if idle_fast_lane.get("idle_fast_lane_exception"):
                idle_fast_lane_exceptions.append("idle_fast_lane_exception")
            if idle_fast_lane_exceptions:
                cycle["order_api_evidence_complete"] = 0
                missing = cycle.get("order_api_evidence_missing_fields")
                if not isinstance(missing, list):
                    missing = []
                cycle["order_api_evidence_missing_fields"] = [
                    *missing,
                    *[
                        f"between_cycle_fast_lane:{item}"
                        for item in idle_fast_lane_exceptions
                    ],
                ]
            summary["latest_cycle"] = cycle
            summary["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            summary["send_order_api_called_count"] = sum(
                _to_int(item.get("send_order_api_called_count"), 0)
                for item in cycles
            )
            summary["cancel_order_api_called_count"] = sum(
                _to_int(item.get("cancel_order_api_called_count"), 0)
                for item in cycles
            )
            summary["order_api_called_count"] = sum(_to_int(item.get("order_api_called_count"), 0) for item in cycles)
            summary["order_api_evidence_missing_fields"] = [
                f"cycle[{index}]:{field}"
                for index, item in enumerate(cycles)
                for field in (
                    item.get("order_api_evidence_missing_fields")
                    if isinstance(
                        item.get("order_api_evidence_missing_fields"), list
                    )
                    else ["order_api_evidence_missing_fields_invalid"]
                )
            ]
            summary["order_api_evidence_complete"] = int(
                not summary["order_api_evidence_missing_fields"]
                and all(
                    item.get("order_api_evidence_complete") == 1
                    for item in cycles
                )
            )
            _write_outputs(paths, summary)
        if args.duration_seconds and time.monotonic() - started >= args.duration_seconds:
            status = "daemon_completed_duration"
            summary["daemon_status"] = status
            _write_outputs(paths, summary)
            print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
            return


if __name__ == "__main__":
    shutdown_exit_code = 0
    try:
        main()
    except DaemonShutdownRequested as exc:
        shutdown_exit_code = 128 + int(exc.signum)
    finally:
        _shutdown_runtime("daemon_main_finally")
    if shutdown_exit_code:
        raise SystemExit(shutdown_exit_code)
