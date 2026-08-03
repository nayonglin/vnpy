from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any

from qmt_roll_official_live_email_notify import (
    send_official_live_email_notification,
)
from qmt_roll_official_live_lightweight_context import CONTROL_OUTPUT_DIR


FAILURE_NOTIFICATION_STATE_PATH = (
    CONTROL_OUTPUT_DIR / "qmt_roll_official_live_failure_notification_state.json"
)
FAILURE_NOTIFICATION_LOCK_PATH = (
    CONTROL_OUTPUT_DIR / "qmt_roll_official_live_failure_notification.lock"
)
FAILURE_NOTIFICATION_COOLDOWN_SECONDS = 30 * 60

_TOKEN_RE = re.compile(r"[^A-Za-z0-9_.:-]+")
_BLOCKER_RE = re.compile(
    r"production_(?:launcher|support)_[A-Za-z0-9_.:-]{1,100}"
)
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_COMMIT_RE = re.compile(r"[0-9a-f]{40}")
_RUN_ID_RE = re.compile(r"[0-9a-f]{32}")
_SECRET_MARKERS = (
    "password",
    "auth_code",
    "authcode",
    "credential",
    "secret",
    "token",
)
_ALLOWED_JOBS = {
    "day-session",
    "night-session",
    "day-close-readonly",
    "postclose-precompute",
    "postclose-report",
    "monthly-ai-pool",
    "postclose-pipeline",
}
_ALLOWED_BOUNDARIES = {
    "pre-exec",
    "target-date-resolver",
    "daily-data-receipt",
    "precompute",
    "monthly-stage935",
    "monthly-receipt-refresh",
    "unexpected",
    "postclose-pipeline:resolve-target",
    "postclose-pipeline:refresh-market-data",
    "postclose-pipeline:check-monthly-ai-pool",
    "postclose-pipeline:refresh-monthly-ai-pool",
    "postclose-pipeline:refresh-shadow",
    "postclose-pipeline:issue-daily-data-receipt",
    "postclose-pipeline:generate-postclose-report",
    "postclose-pipeline-watchdog",
    "postclose-pipeline-retry",
}
_TERMINAL_STATUSES = {"sent", "dry_run_written"}
_MAILER_STATUSES = {
    "sent",
    "dry_run_written",
    "send_failed",
    "disabled",
    "blocked_missing_config",
}


def _safe_token(value: str, *, fallback: str) -> str:
    cleaned = _TOKEN_RE.sub("_", str(value or "").strip())[:120]
    cleaned = cleaned.strip("_.:-")
    return cleaned or fallback


def normalize_official_live_failure_blocker(
    value: str,
    *,
    fallback: str,
) -> str:
    safe_fallback = _safe_token(
        fallback,
        fallback="production_support_failure",
    )
    candidate = _safe_token(value, fallback=safe_fallback)
    lowered = candidate.lower()
    if (
        _BLOCKER_RE.fullmatch(candidate) is None
        or any(marker in lowered for marker in _SECRET_MARKERS)
    ):
        return safe_fallback
    return candidate


def _safe_job(value: str) -> str:
    candidate = _safe_token(value, fallback="unknown-job")
    return candidate if candidate in _ALLOWED_JOBS else "unknown-job"


def _safe_boundary(value: str) -> str:
    candidate = _safe_token(value, fallback="pre-exec")
    return candidate if candidate in _ALLOWED_BOUNDARIES else "pre-exec"


def _safe_schedule_date(value: str) -> str:
    candidate = str(value or "").strip()
    return candidate if _DATE_RE.fullmatch(candidate) else "unknown-date"


def _safe_commit(value: str) -> str:
    candidate = str(value or "").strip().lower()
    return candidate if _COMMIT_RE.fullmatch(candidate) else ""


def _safe_pipeline_run_id(value: str) -> str:
    candidate = str(value or "").strip().lower()
    return candidate if _RUN_ID_RE.fullmatch(candidate) else ""


def _failure_fingerprint(
    release_commit: str,
    schedule_date: str,
    job: str,
    boundary: str,
    blocker: str,
) -> str:
    return hashlib.sha256(
        "\x1f".join(
            (
                release_commit or "unknown",
                schedule_date,
                job,
                boundary,
                blocker,
            )
        ).encode("utf-8")
    ).hexdigest()


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        current = value.replace(tzinfo=timezone.utc)
    else:
        current = value.astimezone(timezone.utc)
    return current.isoformat().replace("+00:00", "Z")


def _parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _empty_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "updated_at": "",
        "entries": {},
    }


def _validate_private_regular(path: Path, *, expected_mode: int) -> None:
    metadata = path.lstat()
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != expected_mode
    ):
        raise PermissionError("official_live_failure_notify_file_unsafe")


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty_state()
    _validate_private_regular(path, expected_mode=0o600)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or not isinstance(payload.get("entries"), dict)
    ):
        raise ValueError("official_live_failure_notify_state_invalid")
    return payload


def _atomic_write_state(path: Path, payload: Mapping[str, Any]) -> None:
    raw = (
        json.dumps(
            dict(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory_descriptor = os.open(path.parent, directory_flags)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except BaseException:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        temporary.unlink(missing_ok=True)
        raise


def _validate_or_create_private_parent(
    state_path: Path,
    lock_path: Path,
) -> tuple[Path, Path]:
    state = Path(os.path.abspath(state_path.expanduser()))
    lock = Path(os.path.abspath(lock_path.expanduser()))
    if state.parent != lock.parent:
        raise PermissionError("official_live_failure_notify_parent_mismatch")
    parent = state.parent
    if not parent.exists():
        parent.mkdir(parents=True, mode=0o700)
    metadata = parent.lstat()
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
    ):
        raise PermissionError("official_live_failure_notify_parent_unsafe")
    return state, lock


def _open_private_lock(path: Path) -> int:
    if path.exists() or path.is_symlink():
        _validate_private_regular(path, expected_mode=0o600)
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) != 0o600
        ):
            raise PermissionError("official_live_failure_notify_lock_unsafe")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _result(
    status: str,
    *,
    fingerprint: str,
    error_type: str = "",
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "notification_status": status,
        "fingerprint": fingerprint,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "order_api_called_count": 0,
    }
    if error_type:
        result["error_type"] = _safe_token(error_type, fallback="Exception")
    return result


def _entry(
    *,
    fingerprint: str,
    release_commit: str,
    schedule_date: str,
    job: str,
    boundary: str,
    blocker: str,
    status: str,
    now_text: str,
    pipeline_run_id: str = "",
    root_stage: str = "",
    error_type: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "fingerprint": fingerprint,
        "release_commit": release_commit,
        "schedule_date": schedule_date,
        "job": job,
        "boundary": boundary,
        "blocker": blocker,
        "status": status,
        "updated_at": now_text,
    }
    if pipeline_run_id:
        payload["pipeline_run_id"] = pipeline_run_id
    if root_stage:
        payload["root_stage"] = root_stage
    if error_type:
        payload["error_type"] = _safe_token(error_type, fallback="Exception")
    return payload


def _notify_official_live_failure(
    *,
    job: str,
    boundary: str,
    blocker: str,
    schedule_date: str,
    release_commit: str,
    pipeline_run_id: str = "",
    root_stage: str = "",
    state_path: Path,
    lock_path: Path,
    now: datetime,
    email_sender: Callable[..., Mapping[str, Any]],
) -> dict[str, Any]:
    fingerprint = ""
    try:
        safe_job = _safe_job(job)
        safe_boundary = _safe_boundary(boundary)
        safe_blocker = normalize_official_live_failure_blocker(
            blocker,
            fallback=(
                "production_launcher_failure"
                if safe_job in {"day-session", "night-session"}
                else "production_support_failure"
            ),
        )
        safe_schedule_date = _safe_schedule_date(schedule_date)
        safe_commit = _safe_commit(release_commit)
        safe_pipeline_run_id = _safe_pipeline_run_id(pipeline_run_id)
        safe_root_stage = _safe_token(root_stage, fallback="")
        fingerprint = _failure_fingerprint(
            safe_commit,
            safe_schedule_date,
            safe_job,
            safe_boundary,
            safe_blocker,
        )
        safe_state_path, safe_lock_path = _validate_or_create_private_parent(
            state_path,
            lock_path,
        )
        descriptor = _open_private_lock(safe_lock_path)
        with os.fdopen(descriptor, "r+") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            state = _load_state(safe_state_path)
            entries = dict(state.get("entries") or {})
            existing = entries.get(fingerprint)
            if isinstance(existing, dict):
                existing_status = str(existing.get("status") or "")
                if existing_status in _TERMINAL_STATUSES:
                    return _result(
                        "suppressed_terminal",
                        fingerprint=fingerprint,
                    )
                updated_at = _parse_utc(existing.get("updated_at"))
                now_utc = (
                    now.replace(tzinfo=timezone.utc)
                    if now.tzinfo is None
                    else now.astimezone(timezone.utc)
                )
                if (
                    updated_at is not None
                    and (now_utc - updated_at).total_seconds()
                    < FAILURE_NOTIFICATION_COOLDOWN_SECONDS
                ):
                    return _result(
                        "suppressed_cooldown",
                        fingerprint=fingerprint,
                    )

            now_text = _utc_text(now)
            entries[fingerprint] = _entry(
                fingerprint=fingerprint,
                release_commit=safe_commit,
                schedule_date=safe_schedule_date,
                job=safe_job,
                boundary=safe_boundary,
                blocker=safe_blocker,
                status="reserved",
                now_text=now_text,
                pipeline_run_id=safe_pipeline_run_id,
                root_stage=safe_root_stage,
            )
            state = {
                "schema_version": 1,
                "updated_at": now_text,
                "entries": entries,
            }
            _atomic_write_state(safe_state_path, state)

            subject = (
                f"[C9/15w][生产任务失败][{safe_job}] {safe_blocker}"
            )
            body = "\n".join(
                [
                    "C9/15万生产任务在正常邮件生成前失败。",
                    f"任务：{safe_job}",
                    f"边界：{safe_boundary}",
                    f"阻断码：{safe_blocker}",
                    f"调度日期：{safe_schedule_date}",
                    f"版本：{safe_commit[:12] or 'unknown'}",
                    f"Pipeline：{safe_pipeline_run_id or 'unknown'}",
                    f"根因阶段：{safe_root_stage or 'unknown'}",
                    "send/cancel/order API：0/0/0",
                    "正常信号邮件未生成，不能据此判断为无交易信号。",
                ]
            )
            error_type = ""
            try:
                mailer_result = email_sender(
                    subject=subject,
                    body=body,
                    event_type="official_live_launcher_failure",
                    severity="warning",
                    attachments=[],
                    metadata={
                        "job": safe_job,
                        "boundary": safe_boundary,
                        "blocker": safe_blocker,
                        "schedule_date": safe_schedule_date,
                        "release_commit": safe_commit[:12] or "unknown",
                        "pipeline_run_id": safe_pipeline_run_id,
                        "root_stage": safe_root_stage,
                        "send_order_api_called_count": 0,
                        "cancel_order_api_called_count": 0,
                        "order_api_called_count": 0,
                    },
                )
                status_value = str(mailer_result.get("email_status") or "")
                if status_value not in _MAILER_STATUSES:
                    raise ValueError("official_live_failure_notify_mailer_invalid")
                notification_status = status_value
            except Exception as exc:
                notification_status = "helper_failed"
                error_type = type(exc).__name__

            entries[fingerprint] = _entry(
                fingerprint=fingerprint,
                release_commit=safe_commit,
                schedule_date=safe_schedule_date,
                job=safe_job,
                boundary=safe_boundary,
                blocker=safe_blocker,
                status=notification_status,
                now_text=now_text,
                pipeline_run_id=safe_pipeline_run_id,
                root_stage=safe_root_stage,
                error_type=error_type,
            )
            state = {
                "schema_version": 1,
                "updated_at": now_text,
                "entries": entries,
            }
            _atomic_write_state(safe_state_path, state)
            return _result(
                notification_status,
                fingerprint=fingerprint,
                error_type=error_type,
            )
    except Exception as exc:
        return _result(
            "helper_failed",
            fingerprint=fingerprint,
            error_type=type(exc).__name__,
        )


def notify_official_live_failure(
    *,
    job: str,
    boundary: str,
    blocker: str,
    schedule_date: str,
    release_commit: str = "",
    pipeline_run_id: str = "",
    root_stage: str = "",
) -> dict[str, Any]:
    return _notify_official_live_failure(
        job=job,
        boundary=boundary,
        blocker=blocker,
        schedule_date=schedule_date,
        release_commit=release_commit,
        pipeline_run_id=pipeline_run_id,
        root_stage=root_stage,
        state_path=FAILURE_NOTIFICATION_STATE_PATH,
        lock_path=FAILURE_NOTIFICATION_LOCK_PATH,
        now=datetime.now(timezone.utc),
        email_sender=send_official_live_email_notification,
    )
