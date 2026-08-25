from __future__ import annotations

import argparse
import os
import select
import signal
import subprocess
import sys
import time
from typing import Any


OWNER_LOST_EXIT_CODE = 125
GUARD_CLEANUP_FAILED_EXIT_CODE = 126
TARGET_EXEC_FAILED_EXIT_CODE = 127
POLL_SECONDS = 0.05


def _process_group_alive(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _signal_process_group(process_group_id: int, signum: int) -> None:
    try:
        os.killpg(process_group_id, signum)
    except (PermissionError, ProcessLookupError):
        pass


def _wait_for_process_group_exit(
    target: subprocess.Popen[Any],
    timeout_seconds: float,
) -> bool:
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    while time.monotonic() < deadline:
        target.poll()
        if not _process_group_alive(target.pid):
            return True
        time.sleep(min(POLL_SECONDS, max(0.0, deadline - time.monotonic())))
    target.poll()
    return not _process_group_alive(target.pid)


def _terminate_target_group(
    target: subprocess.Popen[Any],
    *,
    term_grace_seconds: float,
    kill_wait_seconds: float,
) -> bool:
    target.poll()
    if not _process_group_alive(target.pid):
        return True
    _signal_process_group(target.pid, signal.SIGTERM)
    if _wait_for_process_group_exit(target, term_grace_seconds):
        return True
    _signal_process_group(target.pid, signal.SIGKILL)
    return _wait_for_process_group_exit(target, kill_wait_seconds)


def _owner_pipe_event(owner_fd: int, timeout_seconds: float) -> str:
    """Return alive, lost, or protocol_error for the owner-only pipe."""

    readable, _, _ = select.select([owner_fd], [], [], max(0.0, timeout_seconds))
    if not readable:
        return "alive"
    try:
        payload = os.read(owner_fd, 4096)
    except InterruptedError:
        return "alive"
    if not payload:
        return "lost"
    # Stage930 never writes payload bytes. Unexpected data invalidates the
    # ownership contract rather than allowing a corrupt writer to extend it.
    return "protocol_error"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage930 kernel-pipe owner-liveness guard for one managed child."
    )
    parser.add_argument("--owner-fd", type=int, required=True)
    parser.add_argument("--term-grace-seconds", type=float, required=True)
    parser.add_argument("--kill-wait-seconds", type=float, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if args.owner_fd <= 2 or not args.command:
        parser.error("a non-standard owner fd and target command are required")
    return args


def _run_guard(args: argparse.Namespace) -> int:
    owner_fd = int(args.owner_fd)
    shutdown_signal = 0

    def request_shutdown(signum: int, _frame: Any) -> None:
        nonlocal shutdown_signal
        if not shutdown_signal:
            shutdown_signal = int(signum)

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)
    initial_owner_state = _owner_pipe_event(owner_fd, 0.0)
    if initial_owner_state != "alive":
        os.close(owner_fd)
        return OWNER_LOST_EXIT_CODE

    try:
        # The target gets its own process group in the same launchd session.
        # close_fds ensures it cannot inherit the owner-liveness read end.
        target = subprocess.Popen(
            args.command,
            close_fds=True,
            process_group=0,
        )
    except OSError as exc:
        os.close(owner_fd)
        print(f"stage930 managed target exec failed: {exc!r}", file=sys.stderr)
        return TARGET_EXEC_FAILED_EXIT_CODE

    target_return_code: int | None = None
    stop_reason = ""
    try:
        while True:
            target_return_code = target.poll()
            if target_return_code is not None:
                stop_reason = "target_exited"
                break
            if shutdown_signal:
                stop_reason = "guard_signal"
                break
            owner_state = _owner_pipe_event(owner_fd, POLL_SECONDS)
            if owner_state != "alive":
                stop_reason = owner_state
                break

        cleanup_ok = _terminate_target_group(
            target,
            term_grace_seconds=max(0.0, float(args.term_grace_seconds)),
            kill_wait_seconds=max(0.0, float(args.kill_wait_seconds)),
        )
        if not cleanup_ok:
            return GUARD_CLEANUP_FAILED_EXIT_CODE
        if stop_reason == "target_exited":
            return int(target_return_code or 0)
        if stop_reason == "guard_signal":
            return -int(shutdown_signal or signal.SIGTERM)
        return OWNER_LOST_EXIT_CODE
    finally:
        try:
            os.close(owner_fd)
        except OSError:
            pass


def _exit_like_target(return_code: int) -> None:
    if return_code >= 0:
        raise SystemExit(return_code)
    signum = -int(return_code)
    # SIGKILL cannot be caught or have its disposition changed; it is already
    # guaranteed to terminate us with the same negative Popen return code.
    if signum != signal.SIGKILL:
        signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)
    raise SystemExit(128 + signum)


if __name__ == "__main__":
    _exit_like_target(_run_guard(_parse_args()))
