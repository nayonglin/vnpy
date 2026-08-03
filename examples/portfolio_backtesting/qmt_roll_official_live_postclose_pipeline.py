from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, IO, Mapping


POSTCLOSE_PIPELINE_SCHEMA_VERSION = 1
POSTCLOSE_PIPELINE_ARTIFACT_KIND = "official_live_postclose_pipeline_receipt"
POSTCLOSE_PIPELINE_STAGES = (
    "resolve-target",
    "refresh-market-data",
    "check-monthly-ai-pool",
    "refresh-monthly-ai-pool",
    "refresh-shadow",
    "issue-daily-data-receipt",
    "generate-postclose-report",
)
_TERMINAL_STATUSES = {"succeeded", "failed"}
_STAGE_SUCCESS_STATUSES = {"succeeded", "skipped_not_required"}
_STAGE_STATUSES = {
    "pending",
    "succeeded",
    "failed",
    "skipped_not_required",
    "skipped_upstream_failed",
}
_RETRYABLE_MONTHLY_BLOCKERS = {
    "production_support_monthly_ai_pool_process_failed",
    "production_support_monthly_ai_pool_not_qualified",
    "production_support_monthly_receipt_refresh_failed",
}
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_COMMIT_RE = re.compile(r"[0-9a-f]{40}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_RUN_ID_RE = re.compile(r"[0-9a-f]{32}")


class PostclosePipelineError(ValueError):
    pass


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PostclosePipelineError("postclose_pipeline_payload_invalid") from exc


def _with_digest(payload: Mapping[str, Any]) -> dict[str, Any]:
    core = {key: value for key, value in payload.items() if key != "receipt_sha256"}
    return {
        **core,
        "receipt_sha256": hashlib.sha256(_canonical_bytes(core)).hexdigest(),
    }


def _zero_api(payload: Mapping[str, Any]) -> None:
    if any(
        payload.get(key) != 0
        for key in (
            "send_order_api_called_count",
            "cancel_order_api_called_count",
            "order_api_called_count",
        )
    ):
        raise PostclosePipelineError("postclose_pipeline_order_api_nonzero")


def _validate_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if (
        payload.get("schema_version") != POSTCLOSE_PIPELINE_SCHEMA_VERSION
        or payload.get("artifact_kind") != POSTCLOSE_PIPELINE_ARTIFACT_KIND
        or not _RUN_ID_RE.fullmatch(str(payload.get("pipeline_run_id", "")))
        or not _DATE_RE.fullmatch(str(payload.get("schedule_date", "")))
        or not _DATE_RE.fullmatch(str(payload.get("target_date", "")))
        or not _COMMIT_RE.fullmatch(str(payload.get("source_commit", "")))
        or not _SHA256_RE.fullmatch(str(payload.get("manifest_sha256", "")))
        or payload.get("status") not in {"running", *_TERMINAL_STATUSES}
    ):
        raise PostclosePipelineError("postclose_pipeline_payload_invalid")
    stages = payload.get("stages")
    if not isinstance(stages, list) or len(stages) != len(POSTCLOSE_PIPELINE_STAGES):
        raise PostclosePipelineError("postclose_pipeline_payload_invalid")
    for expected, row in zip(POSTCLOSE_PIPELINE_STAGES, stages, strict=True):
        if (
            not isinstance(row, dict)
            or row.get("stage") != expected
            or row.get("status") not in _STAGE_STATUSES
        ):
            raise PostclosePipelineError("postclose_pipeline_payload_invalid")
    _zero_api(payload)
    observed_digest = str(payload.get("receipt_sha256", ""))
    expected = _with_digest(payload)
    if observed_digest != expected["receipt_sha256"]:
        raise PostclosePipelineError("postclose_pipeline_payload_invalid")
    return dict(payload)


def new_postclose_pipeline_receipt(
    *,
    pipeline_run_id: str,
    schedule_date: str,
    target_date: str,
    source_commit: str,
    manifest_sha256: str,
    generated_at_utc: str,
) -> dict[str, Any]:
    payload = {
        "schema_version": POSTCLOSE_PIPELINE_SCHEMA_VERSION,
        "artifact_kind": POSTCLOSE_PIPELINE_ARTIFACT_KIND,
        "pipeline_run_id": pipeline_run_id,
        "schedule_date": schedule_date,
        "target_date": target_date,
        "source_commit": source_commit,
        "manifest_sha256": manifest_sha256,
        "generated_at_utc": generated_at_utc,
        "finished_at_utc": "",
        "status": "running",
        "current_stage": "",
        "root_stage": "",
        "root_blocker": "",
        "retry_of": "",
        "daily_data_receipt_sha256": "",
        "report_summary_sha256": "",
        "email_disposition": {},
        "stages": [
            {
                "stage": stage,
                "status": "pending",
                "started_at_utc": "",
                "finished_at_utc": "",
                "blocker": "",
                "outputs": {},
            }
            for stage in POSTCLOSE_PIPELINE_STAGES
        ],
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "order_api_called_count": 0,
    }
    result = _with_digest(payload)
    return _validate_payload(result)


def record_postclose_pipeline_stage(
    payload: Mapping[str, Any],
    *,
    stage: str,
    status: str,
    started_at_utc: str,
    finished_at_utc: str,
    blocker: str = "",
    outputs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    current = _validate_payload(payload)
    if current["status"] != "running" or stage not in POSTCLOSE_PIPELINE_STAGES:
        raise PostclosePipelineError("postclose_pipeline_stage_order_invalid")
    index = POSTCLOSE_PIPELINE_STAGES.index(stage)
    rows = [dict(row) for row in current["stages"]]
    if rows[index]["status"] != "pending" or any(
        row["status"] not in _STAGE_SUCCESS_STATUSES for row in rows[:index]
    ):
        raise PostclosePipelineError("postclose_pipeline_stage_order_invalid")
    if status not in {"succeeded", "failed", "skipped_not_required"}:
        raise PostclosePipelineError("postclose_pipeline_payload_invalid")
    if status == "failed" and not blocker:
        raise PostclosePipelineError("postclose_pipeline_payload_invalid")
    rows[index] = {
        "stage": stage,
        "status": status,
        "started_at_utc": started_at_utc,
        "finished_at_utc": finished_at_utc,
        "blocker": blocker if status == "failed" else "",
        "outputs": dict(outputs or {}),
    }
    result = {
        **current,
        "current_stage": stage,
        "stages": rows,
    }
    if status == "failed":
        result["root_stage"] = stage
        result["root_blocker"] = blocker
    return _validate_payload(_with_digest(result))


def finish_postclose_pipeline_receipt(
    payload: Mapping[str, Any],
    *,
    status: str,
    root_blocker: str,
    email_disposition: Mapping[str, Any],
    daily_data_receipt_sha256: str = "",
    report_summary_sha256: str = "",
    retry_of: str = "",
    finished_at_utc: str,
) -> dict[str, Any]:
    current = _validate_payload(payload)
    if current["status"] != "running" or status not in _TERMINAL_STATUSES:
        raise PostclosePipelineError("postclose_pipeline_payload_invalid")
    rows = [dict(row) for row in current["stages"]]
    if status == "succeeded":
        if any(row["status"] not in _STAGE_SUCCESS_STATUSES for row in rows):
            raise PostclosePipelineError("postclose_pipeline_stage_order_invalid")
        if root_blocker:
            raise PostclosePipelineError("postclose_pipeline_payload_invalid")
        root_stage = ""
    else:
        failed = next((row for row in rows if row["status"] == "failed"), None)
        if failed is None or not root_blocker:
            raise PostclosePipelineError("postclose_pipeline_payload_invalid")
        root_stage = str(failed["stage"])
        for row in rows[POSTCLOSE_PIPELINE_STAGES.index(root_stage) + 1 :]:
            if row["status"] == "pending":
                row["status"] = "skipped_upstream_failed"
    if retry_of and not _RUN_ID_RE.fullmatch(retry_of):
        raise PostclosePipelineError("postclose_pipeline_payload_invalid")
    for digest in (daily_data_receipt_sha256, report_summary_sha256):
        if digest and not _SHA256_RE.fullmatch(digest):
            raise PostclosePipelineError("postclose_pipeline_payload_invalid")
    result = {
        **current,
        "status": status,
        "finished_at_utc": finished_at_utc,
        "root_stage": root_stage,
        "root_blocker": root_blocker,
        "retry_of": retry_of,
        "daily_data_receipt_sha256": daily_data_receipt_sha256,
        "report_summary_sha256": report_summary_sha256,
        "email_disposition": dict(email_disposition),
        "stages": rows,
    }
    return _validate_payload(_with_digest(result))


def _validate_private_parent(parent: Path) -> None:
    try:
        metadata = parent.lstat()
    except OSError as exc:
        raise PostclosePipelineError(
            "postclose_pipeline_parent_security_invalid"
        ) from exc
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
    ):
        raise PostclosePipelineError("postclose_pipeline_parent_security_invalid")


def _validate_private_file(path: Path) -> None:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise PostclosePipelineError("postclose_pipeline_file_security_invalid") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
    ):
        raise PostclosePipelineError("postclose_pipeline_file_security_invalid")


def write_postclose_pipeline_receipt(
    path: Path | str,
    payload: Mapping[str, Any],
) -> None:
    destination = Path(path)
    _validate_payload(payload)
    _validate_private_parent(destination.parent)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        dir=destination.parent,
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(_canonical_bytes(payload))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        parent_fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        temporary.unlink(missing_ok=True)
    _validate_private_file(destination)
    load_and_validate_postclose_pipeline_receipt(
        destination,
        source_commit=str(payload["source_commit"]),
        manifest_sha256=str(payload["manifest_sha256"]),
        schedule_date=str(payload["schedule_date"]),
    )


def load_and_validate_postclose_pipeline_receipt(
    path: Path | str,
    *,
    source_commit: str,
    manifest_sha256: str,
    schedule_date: str | None = None,
) -> dict[str, Any]:
    candidate = Path(path)
    _validate_private_parent(candidate.parent)
    _validate_private_file(candidate)
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PostclosePipelineError("postclose_pipeline_payload_invalid") from exc
    if not isinstance(payload, dict):
        raise PostclosePipelineError("postclose_pipeline_payload_invalid")
    result = _validate_payload(payload)
    if result["source_commit"] != source_commit:
        raise PostclosePipelineError("postclose_pipeline_source_commit_mismatch")
    if result["manifest_sha256"] != manifest_sha256:
        raise PostclosePipelineError("postclose_pipeline_manifest_mismatch")
    if schedule_date is not None and result["schedule_date"] != schedule_date:
        raise PostclosePipelineError("postclose_pipeline_schedule_date_mismatch")
    return result


def postclose_pipeline_retry_eligible(payload: Mapping[str, Any]) -> bool:
    try:
        current = _validate_payload(payload)
    except PostclosePipelineError:
        return False
    return bool(
        current["status"] == "failed"
        and current.get("retry_of", "") == ""
        and current.get("root_stage") == "refresh-monthly-ai-pool"
        and current.get("root_blocker") in _RETRYABLE_MONTHLY_BLOCKERS
        and current.get("order_api_called_count") == 0
    )


def open_postclose_pipeline_lock(path: Path | str) -> IO[str]:
    candidate = Path(path)
    _validate_private_parent(candidate.parent)
    descriptor = os.open(candidate, os.O_RDWR | os.O_CREAT, 0o600)
    os.fchmod(descriptor, 0o600)
    handle = os.fdopen(descriptor, "r+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        handle.close()
        raise PostclosePipelineError("postclose_pipeline_lock_busy") from exc
    _validate_private_file(candidate)
    return handle
