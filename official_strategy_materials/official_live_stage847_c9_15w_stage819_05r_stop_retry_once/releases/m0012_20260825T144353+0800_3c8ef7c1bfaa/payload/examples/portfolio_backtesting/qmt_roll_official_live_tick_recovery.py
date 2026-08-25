from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
import errno
import hashlib
import json
import os
import stat
import time

import qmt_roll_official_live_tick_journal as tick_journal
from qmt_roll_official_live_tick_journal import (
    MAX_JOURNAL_BATCH_BYTES,
    MAX_JOURNAL_LINE_BYTES,
    _clean,
    _commit_frame_matches,
    _parse_record_line,
    _strict_json_int,
    _validated_framed_tick_row_identity,
    _validated_header_segment_id,
)
from qmt_roll_official_live_tick_types import (
    DEFAULT_WRITER_BATCH_SIZE,
    JOURNAL_BATCH_COMMIT_SCHEMA_VERSION,
    JOURNAL_BATCH_COMMIT_RECORD_TYPE,
    JOURNAL_FORMAT_FRAMED_V1,
    JOURNAL_FORMAT_LEGACY_V0,
    JOURNAL_HEADER_RECORD_TYPE,
    JOURNAL_RECORD_TYPE_FIELD,
    JOURNAL_SCHEMA_FRAMED_V1,
    JOURNAL_SCHEMA_LEGACY_V0,
    DurableTickCursor,
    JournalRecoveryResult,
    TickStreamGap,
)


RECOVERY_MANIFEST_RECORD_TYPE = "stage179_recovery_redo_v1"
RECOVERY_MANIFEST_SCHEMA_VERSION = 1
MAX_RECOVERY_MANIFEST_BYTES = 1024 * 1024
MAX_RECOVERY_HEARTBEAT_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class _RecoveryManifestContract:
    result: JournalRecoveryResult
    source_path: Path
    source_device: int
    source_inode: int
    original_size: int
    trusted_end: int
    tail_byte_count: int
    trusted_prefix_sha256: str
    tail_sha256: str
    isolated_tail_path: Path


@dataclass(frozen=True)
class _RedurableHeartbeatEvidence:
    payload: dict[str, Any]
    identity: tuple[int, int, int]
    payload_sha256: str


def _heartbeat_nonnegative_int(
    heartbeat: Mapping[str, Any],
    key: str,
    *,
    fallback: int = 0,
) -> int:
    value = heartbeat[key] if key in heartbeat else fallback
    if type(value) is not int:
        raise ValueError(f"invalid heartbeat integer: {key}")
    if value < 0:
        raise ValueError(f"negative heartbeat integer: {key}")
    return value


def _heartbeat_bool_if_present(
    heartbeat: Mapping[str, Any],
    key: str,
) -> bool | None:
    if key not in heartbeat:
        return None
    value = heartbeat[key]
    if type(value) is not bool:
        raise ValueError(f"invalid heartbeat boolean: {key}")
    return value


def _gap_from_mapping(payload: Mapping[str, Any]) -> TickStreamGap:
    feed_session_id = _clean(payload.get("feed_session_id"))
    reason = _clean(payload.get("reason"))
    start = _strict_json_int(payload.get("start_ingress_sequence"))
    end = _strict_json_int(payload.get("end_ingress_sequence"))
    if start is None or end is None:
        raise ValueError("invalid prior gap sequence")
    if not feed_session_id or not reason or start <= 0 or end < start:
        raise ValueError("invalid prior gap lineage entry")
    return TickStreamGap(feed_session_id, start, end, reason)


def _prior_gap_lineage(
    heartbeat: Mapping[str, Any],
) -> tuple[TickStreamGap, ...]:
    raw_many = heartbeat.get("prior_uncommitted_gaps", [])
    if raw_many is None:
        raw_many = []
    if not isinstance(raw_many, list):
        raise ValueError("prior_uncommitted_gaps must be a list")
    raw_items: list[Mapping[str, Any]] = []
    for item in raw_many:
        if not isinstance(item, Mapping):
            raise ValueError("prior gap lineage entry must be an object")
        raw_items.append(item)
    scalar = heartbeat.get("prior_uncommitted_gap")
    if scalar is not None:
        if not isinstance(scalar, Mapping):
            raise ValueError("prior_uncommitted_gap must be an object")
        raw_items.append(scalar)

    result: list[TickStreamGap] = []
    seen: set[tuple[str, int, int, str]] = set()
    for item in raw_items:
        gap = _gap_from_mapping(item)
        identity = (
            gap.feed_session_id,
            gap.start_ingress_sequence,
            gap.end_ingress_sequence,
            gap.reason,
        )
        if identity in seen:
            continue
        seen.add(identity)
        result.append(gap)
    return tuple(result)


def _journal_session_state(heartbeat: Mapping[str, Any]) -> str:
    state = _clean(heartbeat.get("journal_session_state"))
    allowed = {
        "starting",
        "running",
        "clean_stopped",
        "recovery_required_stopped",
        "fault_stopped",
    }
    if state:
        if state not in allowed:
            raise ValueError(f"unknown journal_session_state: {state}")
        return state
    if heartbeat.get("clean_shutdown") is True:
        return "clean_stopped"
    if heartbeat.get("stopped") is True:
        if (
            heartbeat.get("writer_fault")
            or heartbeat.get("gap_latched")
            or heartbeat.get("market_data_close_error")
            or heartbeat.get("aggregate_close_error")
            or heartbeat.get("shutdown_error")
        ):
            return "fault_stopped"
        return "clean_stopped"
    return "running"


def _current_gap_boundary(
    heartbeat: Mapping[str, Any],
) -> tuple[int, int, str]:
    latched = _heartbeat_bool_if_present(heartbeat, "gap_latched")
    start = _heartbeat_nonnegative_int(
        heartbeat,
        "gap_start_ingress_sequence",
    )
    end = _heartbeat_nonnegative_int(
        heartbeat,
        "gap_end_ingress_sequence",
    )
    reason = _clean(heartbeat.get("gap_reason"))
    populated = bool(start or end or reason)
    if latched is True:
        if start <= 0 or end < start or not reason:
            raise ValueError("gap_latched tuple incomplete or invalid")
    elif populated:
        raise ValueError("gap tuple populated while gap_latched is not true")
    return (start, end, reason) if latched else (0, 0, "")


def _hard_revocation_boundary(
    heartbeat: Mapping[str, Any],
) -> tuple[int, int, str]:
    start = _heartbeat_nonnegative_int(
        heartbeat,
        "journal_commit_revoked_from_ingress_sequence",
    )
    end = _heartbeat_nonnegative_int(
        heartbeat,
        "journal_commit_revoked_through_ingress_sequence",
    )
    reason = _clean(heartbeat.get("journal_commit_revocation_reason"))
    explicit = bool(start or end or reason)
    if explicit and (start <= 0 or end < start or not reason):
        raise ValueError("journal commit revocation tuple incomplete or invalid")
    hard_gap_reasons = {
        "shutdown_drain_timeout",
        "shutdown_durable_mismatch",
        "ingress_queue_full",
        "ingress_not_accepting",
        "ingress_thread_violation",
        "ingress_capture_exception",
        "ingress_fault_latch_exception",
    }
    gap_start, gap_end, gap_reason = _current_gap_boundary(heartbeat)
    if gap_reason in hard_gap_reasons:
        if explicit and (start, end, reason) != (
            gap_start,
            gap_end,
            gap_reason,
        ):
            raise ValueError("gap and journal commit revocation conflict")
        if not explicit:
            start, end, reason = gap_start, gap_end, gap_reason
    elif explicit and gap_reason:
        raise ValueError("non-hard gap conflicts with journal commit revocation")
    return start, end, reason


def _validate_recovery_contract(
    path: Path,
    heartbeat: Mapping[str, Any],
) -> None:
    """Reject contradictory authority evidence before touching journal bytes."""

    if not heartbeat and not path.exists():
        return
    _prior_gap_lineage(heartbeat)
    feed_session_id = _clean(heartbeat.get("feed_session_id"))
    if not feed_session_id:
        raise ValueError("feed_session_id_missing")
    schema = _clean(heartbeat.get("journal_schema"))
    schema_contracts = {
        JOURNAL_SCHEMA_FRAMED_V1: (
            JOURNAL_FORMAT_FRAMED_V1,
            JOURNAL_BATCH_COMMIT_SCHEMA_VERSION,
        ),
        JOURNAL_SCHEMA_LEGACY_V0: (JOURNAL_FORMAT_LEGACY_V0, 0),
    }
    if schema not in schema_contracts:
        raise ValueError("journal_schema_missing_or_unsupported")
    expected_format, expected_version = schema_contracts[schema]
    if (
        "journal_format" in heartbeat
        and _clean(heartbeat.get("journal_format")) != expected_format
    ):
        raise ValueError("journal_format_mismatch")
    if "journal_schema_version" in heartbeat:
        version = heartbeat["journal_schema_version"]
        if type(version) is not int or version != expected_version:
            raise ValueError("journal_schema_version_mismatch")

    durable = _heartbeat_nonnegative_int(
        heartbeat,
        "durable_ingress_sequence",
        fallback=_heartbeat_nonnegative_int(
            heartbeat,
            "stream_sequence",
        ),
    )
    last = _heartbeat_nonnegative_int(
        heartbeat,
        "last_ingress_sequence",
        fallback=durable,
    )
    if durable > last:
        raise ValueError("durable_ingress_sequence exceeds last_ingress_sequence")
    durable_offset_present = "durable_journal_byte_offset" in heartbeat
    durable_offset = _heartbeat_nonnegative_int(
        heartbeat,
        "durable_journal_byte_offset",
    )
    if durable_offset_present and schema == JOURNAL_SCHEMA_FRAMED_V1:
        if durable > 0 and durable_offset == 0:
            raise ValueError("framed_durable_cursor_offset_missing")
        if durable == 0 and durable_offset != 0:
            raise ValueError("framed_zero_sequence_offset_nonzero")
    for alias in ("stream_sequence", "journal_tick_count"):
        if alias in heartbeat and _heartbeat_nonnegative_int(
            heartbeat,
            alias,
        ) != durable:
            raise ValueError(f"{alias} mismatches durable_ingress_sequence")

    gap_start, gap_end, gap_reason = _current_gap_boundary(heartbeat)
    revoked_from, revoked_through, _ = _hard_revocation_boundary(heartbeat)
    for label, start, end in (
        ("gap", gap_start, gap_end),
        ("revocation", revoked_from, revoked_through),
    ):
        if start and (
            start != durable + 1
            or end > last
        ):
            raise ValueError(f"{label} range inconsistent with durable/last")

    state = _journal_session_state(heartbeat)
    stopped = _heartbeat_bool_if_present(heartbeat, "stopped")
    clean_shutdown = _heartbeat_bool_if_present(heartbeat, "clean_shutdown")
    if state in {"starting", "running"}:
        if stopped is True:
            raise ValueError("running journal_session_state contradicts stopped")
        if clean_shutdown is True:
            raise ValueError(
                "running journal_session_state contradicts clean_shutdown"
            )
    else:
        if stopped is False:
            raise ValueError("stopped journal_session_state contradicts stopped")
        if state == "clean_stopped":
            if clean_shutdown is False:
                raise ValueError("clean_stopped contradicts clean_shutdown")
            fault_evidence = bool(
                heartbeat.get("writer_fault")
                or gap_reason
                or revoked_from
                or heartbeat.get("market_data_close_error")
                or heartbeat.get("aggregate_close_error")
                or heartbeat.get("shutdown_error")
                or heartbeat.get("exception")
            )
            if fault_evidence:
                raise ValueError("clean_stopped carries fault evidence")
        elif clean_shutdown is True:
            raise ValueError(
                "fault/recovery stopped state contradicts clean_shutdown"
            )

    authority = _heartbeat_bool_if_present(
        heartbeat,
        "journal_authority_committed",
    )
    if authority is True and not path.exists():
        raise ValueError("authoritative_journal_missing")
    if authority is True and path.stat().st_size == 0:
        raise ValueError("authoritative_journal_empty")
    if (
        authority is True
        and schema == JOURNAL_SCHEMA_FRAMED_V1
        and durable > 0
        and not durable_offset_present
    ):
        raise ValueError("authoritative_durable_journal_byte_offset_missing")
    if authority is True and durable_offset > path.stat().st_size:
        raise ValueError("durable_journal_byte_offset_beyond_journal")
    if authority is False and (durable or last or path.exists()):
        raise ValueError("journal_authority_not_committed")


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _gap_mapping(gap: TickStreamGap) -> dict[str, Any]:
    return {
        "feed_session_id": gap.feed_session_id,
        "start_ingress_sequence": gap.start_ingress_sequence,
        "end_ingress_sequence": gap.end_ingress_sequence,
        "reason": gap.reason,
    }


def _cursor_mapping(cursor: DurableTickCursor | None) -> dict[str, Any] | None:
    if cursor is None:
        return None
    return {
        "feed_session_id": cursor.feed_session_id,
        "ingress_sequence": cursor.ingress_sequence,
        "journal_byte_offset": cursor.journal_byte_offset,
        "journal_schema": cursor.journal_schema,
    }


def _recovery_manifest_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.stage179.recovery.json")


def _is_sha256(value: Any) -> bool:
    text = _clean(value)
    return bool(
        len(text) == 64
        and all(character in "0123456789abcdef" for character in text)
    )


def _regular_file_stat(path: Path, *, label: str) -> os.stat_result:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise RuntimeError(f"{label}_missing") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise RuntimeError(f"{label}_not_regular_file")
    return metadata


def _hash_descriptor_range(
    descriptor: int,
    *,
    start: int,
    byte_count: int,
) -> str:
    digest = hashlib.sha256()
    remaining = int(byte_count)
    with os.fdopen(os.dup(descriptor), "rb", buffering=0) as handle:
        handle.seek(int(start))
        while remaining > 0:
            chunk = handle.read(min(1024 * 1024, remaining))
            if not chunk:
                raise OSError(errno.EIO, "recovery hash range ended early")
            digest.update(chunk)
            remaining -= len(chunk)
    return digest.hexdigest()


def _hash_regular_path(path: Path, *, expected_size: int) -> str:
    metadata = _regular_file_stat(path, label="recovery_sidecar")
    if metadata.st_size != expected_size:
        raise RuntimeError("recovery_sidecar_size_mismatch")
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        return _hash_descriptor_range(
            descriptor,
            start=0,
            byte_count=expected_size,
        )
    finally:
        os.close(descriptor)


def _redurable_regular_path(
    path: Path,
    *,
    label: str,
    expected_size: int,
    expected_sha256: str,
) -> None:
    """Re-prove a visible write-ahead artifact before destructive replay.

    A process may die after rename made an entry visible but before the parent
    directory barrier completed.  Visibility on the next start is not itself
    durability proof, so replay must fsync the file and parent again while
    preserving the exact inode, size, and bytes it validated.
    """

    metadata = _regular_file_stat(path, label=label)
    if metadata.st_size != expected_size:
        raise RuntimeError(f"{label}_size_mismatch")
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        opened = os.fstat(descriptor)
        if (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
        ) != (
            metadata.st_dev,
            metadata.st_ino,
            expected_size,
        ):
            raise RuntimeError(f"{label}_changed_before_redurability")
        if _hash_descriptor_range(
            descriptor,
            start=0,
            byte_count=expected_size,
        ) != expected_sha256:
            raise RuntimeError(f"{label}_hash_mismatch")
        tick_journal._durability_barrier(descriptor)
        after_barrier = os.fstat(descriptor)
        if (
            after_barrier.st_dev,
            after_barrier.st_ino,
            after_barrier.st_size,
        ) != (
            metadata.st_dev,
            metadata.st_ino,
            expected_size,
        ):
            raise RuntimeError(f"{label}_changed_during_redurability")
        if _hash_descriptor_range(
            descriptor,
            start=0,
            byte_count=expected_size,
        ) != expected_sha256:
            raise RuntimeError(f"{label}_changed_during_redurability")
    finally:
        os.close(descriptor)
    current = _regular_file_stat(path, label=label)
    if (
        current.st_dev,
        current.st_ino,
        current.st_size,
    ) != (
        metadata.st_dev,
        metadata.st_ino,
        expected_size,
    ):
        raise RuntimeError(f"{label}_changed_during_redurability")
    tick_journal._fsync_parent(path)
    final_descriptor = os.open(str(path), os.O_RDONLY)
    try:
        final = os.fstat(final_descriptor)
        if (
            final.st_dev,
            final.st_ino,
            final.st_size,
        ) != (
            metadata.st_dev,
            metadata.st_ino,
            expected_size,
        ):
            raise RuntimeError(f"{label}_changed_during_redurability")
        if _hash_descriptor_range(
            final_descriptor,
            start=0,
            byte_count=expected_size,
        ) != expected_sha256:
            raise RuntimeError(f"{label}_changed_during_redurability")
    finally:
        os.close(final_descriptor)


def _authority_projection(
    heartbeat: Mapping[str, Any],
) -> dict[str, Any]:
    gap_start, gap_end, gap_reason = _current_gap_boundary(heartbeat)
    revoked_from, revoked_through, revoked_reason = _hard_revocation_boundary(
        heartbeat
    )
    return {
        "feed_session_id": _clean(heartbeat.get("feed_session_id")),
        "journal_schema": _clean(heartbeat.get("journal_schema")),
        "journal_format": _clean(heartbeat.get("journal_format")),
        "journal_schema_version": heartbeat.get("journal_schema_version"),
        "journal_authority_committed": heartbeat.get(
            "journal_authority_committed"
        ),
        "journal_session_state": _journal_session_state(heartbeat),
        "stopped": heartbeat.get("stopped"),
        "clean_shutdown": heartbeat.get("clean_shutdown"),
        "durable_ingress_sequence": _heartbeat_nonnegative_int(
            heartbeat,
            "durable_ingress_sequence",
            fallback=_heartbeat_nonnegative_int(heartbeat, "stream_sequence"),
        ),
        "durable_journal_byte_offset": _heartbeat_nonnegative_int(
            heartbeat,
            "durable_journal_byte_offset",
        ),
        "last_ingress_sequence": _heartbeat_nonnegative_int(
            heartbeat,
            "last_ingress_sequence",
            fallback=_heartbeat_nonnegative_int(
                heartbeat,
                "durable_ingress_sequence",
                fallback=_heartbeat_nonnegative_int(
                    heartbeat,
                    "stream_sequence",
                ),
            ),
        ),
        "current_gap": (
            {
                "start_ingress_sequence": gap_start,
                "end_ingress_sequence": gap_end,
                "reason": gap_reason,
            }
            if gap_start
            else None
        ),
        "revocation": (
            {
                "start_ingress_sequence": revoked_from,
                "end_ingress_sequence": revoked_through,
                "reason": revoked_reason,
            }
            if revoked_from
            else None
        ),
        "prior_uncommitted_gaps": [
            _gap_mapping(gap) for gap in _prior_gap_lineage(heartbeat)
        ],
    }


def _manifest_authority_matches_current(
    expected: Mapping[str, Any],
    heartbeat: Mapping[str, Any],
) -> bool:
    """Allow only a monotonic fail-closed lifecycle mutation during replay."""

    current = _authority_projection(heartbeat)
    if dict(expected) == current:
        return True
    lifecycle_fields = {
        "journal_session_state",
        "stopped",
        "clean_shutdown",
    }
    if any(
        expected.get(key) != current.get(key)
        for key in set(expected) | set(current)
        if key not in lifecycle_fields
    ):
        return False
    return bool(
        expected.get("journal_session_state") in {"starting", "running"}
        and expected.get("stopped") is False
        and expected.get("clean_shutdown") is False
        and current.get("journal_session_state") == "fault_stopped"
        and current.get("stopped") is True
        and current.get("clean_shutdown") is False
        and heartbeat.get("stream_ready") is False
        and heartbeat.get("transport_ready") is False
        and heartbeat.get("writer_alive") is False
        and heartbeat.get("recovery_blocked") is True
    )


def _recovery_result_projection(
    result: JournalRecoveryResult,
) -> dict[str, Any]:
    return {
        "previous_durable_cursor": _cursor_mapping(
            result.previous_durable_cursor
        ),
        "isolated_byte_count": result.isolated_byte_count,
        "disclosed_gap": (
            _gap_mapping(result.disclosed_gap)
            if result.disclosed_gap is not None
            else None
        ),
        "disclosed_gaps": [
            _gap_mapping(gap) for gap in result.disclosed_gaps
        ],
        "journal_schema": result.journal_schema,
    }


def _atomic_write_recovery_manifest(
    manifest_path: Path,
    payload: Mapping[str, Any],
) -> None:
    raw_payload_without_digest = _canonical_json_bytes(payload)
    committed_payload = {
        **dict(payload),
        "manifest_sha256": hashlib.sha256(
            raw_payload_without_digest
        ).hexdigest(),
    }
    raw = _canonical_json_bytes(committed_payload) + b"\n"
    if len(raw) > MAX_RECOVERY_MANIFEST_BYTES:
        raise ValueError("recovery_manifest_too_large")
    temporary_path = manifest_path.with_name(
        f".{manifest_path.name}.{os.getpid()}.{time.time_ns()}.tmp"
    )
    descriptor = os.open(
        str(temporary_path),
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb", buffering=0) as handle:
            tick_journal._write_all(handle, raw)
            tick_journal._durability_barrier(handle.fileno())
        if os.path.lexists(str(manifest_path)):
            raise RuntimeError("recovery_manifest_already_exists")
        os.replace(temporary_path, manifest_path)
        tick_journal._fsync_parent(manifest_path)
    finally:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass


def _read_recovery_manifest(path: Path) -> dict[str, Any] | None:
    manifest_path = _recovery_manifest_path(path)
    if not os.path.lexists(str(manifest_path)):
        return None
    _regular_file_stat(manifest_path, label="recovery_manifest")
    with manifest_path.open("rb") as handle:
        raw = handle.read(MAX_RECOVERY_MANIFEST_BYTES + 1)
    if len(raw) > MAX_RECOVERY_MANIFEST_BYTES:
        raise ValueError("recovery_manifest_too_large")
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise ValueError("recovery_manifest_invalid_json") from exc
    if not isinstance(payload, dict):
        raise ValueError("recovery_manifest_invalid_root")
    if raw != _canonical_json_bytes(payload) + b"\n":
        raise ValueError("recovery_manifest_not_canonical")
    manifest_digest = _clean(payload.get("manifest_sha256"))
    unsigned = dict(payload)
    unsigned.pop("manifest_sha256", None)
    if not _is_sha256(manifest_digest) or hashlib.sha256(
        _canonical_json_bytes(unsigned)
    ).hexdigest() != manifest_digest:
        raise ValueError("recovery_manifest_digest_mismatch")
    if (
        payload.get("record_type") != RECOVERY_MANIFEST_RECORD_TYPE
        or _strict_json_int(payload.get("schema_version"))
        != RECOVERY_MANIFEST_SCHEMA_VERSION
        or _clean(payload.get("source_path")) != str(path.resolve())
        or not _is_sha256(payload.get("transaction_id"))
    ):
        raise ValueError("recovery_manifest_contract_invalid")
    transaction_core = payload.get("transaction_core")
    if not isinstance(transaction_core, Mapping) or hashlib.sha256(
        _canonical_json_bytes(transaction_core)
    ).hexdigest() != _clean(payload.get("transaction_id")):
        raise ValueError("recovery_manifest_transaction_mismatch")
    return payload


def _ensure_recovery_sidecar(
    source_descriptor: int,
    *,
    isolated_tail_path: Path,
    trusted_end: int,
    tail_byte_count: int,
    tail_sha256: str,
) -> None:
    if os.path.lexists(str(isolated_tail_path)):
        _redurable_regular_path(
            isolated_tail_path,
            label="recovery_sidecar",
            expected_size=tail_byte_count,
            expected_sha256=tail_sha256,
        )
        return
    temporary_path = isolated_tail_path.with_name(
        f".{isolated_tail_path.name}.{os.getpid()}.{time.time_ns()}.tmp"
    )
    descriptor = os.open(
        str(temporary_path),
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    copied = 0
    digest = hashlib.sha256()
    try:
        with os.fdopen(
            os.dup(source_descriptor),
            "rb",
            buffering=0,
        ) as source, os.fdopen(descriptor, "wb", buffering=0) as target:
            source.seek(trusted_end)
            while copied < tail_byte_count:
                chunk = source.read(
                    min(1024 * 1024, tail_byte_count - copied)
                )
                if not chunk:
                    raise OSError(errno.EIO, "dirty tail copy ended early")
                tick_journal._write_all(target, chunk)
                digest.update(chunk)
                copied += len(chunk)
            if copied != tail_byte_count or digest.hexdigest() != tail_sha256:
                raise OSError(errno.EIO, "dirty tail copy evidence mismatch")
            tick_journal._durability_barrier(target.fileno())
        os.replace(temporary_path, isolated_tail_path)
        tick_journal._fsync_parent(isolated_tail_path)
    finally:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass


def _result_from_manifest(
    payload: Mapping[str, Any],
    *,
    manifest_path: Path,
) -> JournalRecoveryResult:
    result_payload = payload.get("result")
    if not isinstance(result_payload, Mapping):
        raise ValueError("recovery_manifest_result_invalid")
    cursor_payload = result_payload.get("previous_durable_cursor")
    previous_cursor: DurableTickCursor | None = None
    if cursor_payload is not None:
        if not isinstance(cursor_payload, Mapping):
            raise ValueError("recovery_manifest_cursor_invalid")
        sequence = _strict_json_int(cursor_payload.get("ingress_sequence"))
        offset = _strict_json_int(cursor_payload.get("journal_byte_offset"))
        feed_session_id = _clean(cursor_payload.get("feed_session_id"))
        journal_schema = _clean(cursor_payload.get("journal_schema"))
        if (
            sequence is None
            or sequence <= 0
            or offset is None
            or offset < 0
            or not feed_session_id
            or journal_schema not in {
                JOURNAL_SCHEMA_FRAMED_V1,
                JOURNAL_SCHEMA_LEGACY_V0,
            }
        ):
            raise ValueError("recovery_manifest_cursor_invalid")
        previous_cursor = DurableTickCursor(
            feed_session_id,
            sequence,
            journal_byte_offset=offset,
            journal_schema=journal_schema,
        )
    raw_many = result_payload.get("disclosed_gaps")
    if not isinstance(raw_many, list):
        raise ValueError("recovery_manifest_gaps_invalid")
    disclosed_gaps = tuple(
        _gap_from_mapping(item)
        for item in raw_many
        if isinstance(item, Mapping)
    )
    if len(disclosed_gaps) != len(raw_many):
        raise ValueError("recovery_manifest_gaps_invalid")
    raw_scalar = result_payload.get("disclosed_gap")
    disclosed_gap = (
        _gap_from_mapping(raw_scalar)
        if isinstance(raw_scalar, Mapping)
        else None
    )
    if raw_scalar is not None and disclosed_gap is None:
        raise ValueError("recovery_manifest_gap_invalid")
    isolated_byte_count = _strict_json_int(
        result_payload.get("isolated_byte_count")
    )
    if isolated_byte_count is None or isolated_byte_count <= 0:
        raise ValueError("recovery_manifest_isolated_count_invalid")
    isolated_tail_path = Path(_clean(payload.get("isolated_tail_path")))
    journal_schema = _clean(result_payload.get("journal_schema"))
    if not str(isolated_tail_path) or journal_schema not in {
        JOURNAL_SCHEMA_FRAMED_V1,
        JOURNAL_SCHEMA_LEGACY_V0,
    }:
        raise ValueError("recovery_manifest_result_invalid")
    return JournalRecoveryResult(
        previous_cursor,
        isolated_tail_path,
        isolated_byte_count,
        disclosed_gap,
        disclosed_gaps,
        journal_schema,
        recovery_transaction_id=_clean(payload.get("transaction_id")),
        recovery_manifest_path=manifest_path,
        recovery_ack_required=True,
    )


def _validated_result_from_manifest(
    payload: Mapping[str, Any],
    *,
    manifest_path: Path,
) -> JournalRecoveryResult:
    """Bind the mutable outer projection to the transaction-id core."""

    transaction_core = payload.get("transaction_core")
    if not isinstance(transaction_core, Mapping):
        raise ValueError("recovery_manifest_transaction_invalid")
    result = _result_from_manifest(
        payload,
        manifest_path=manifest_path,
    )
    if transaction_core.get("result") != _recovery_result_projection(result):
        raise ValueError("recovery_manifest_result_mismatch")
    return result


def _validated_recovery_manifest_contract(
    path: Path,
    payload: Mapping[str, Any],
    *,
    manifest_path: Path,
) -> _RecoveryManifestContract:
    """Validate every immutable field needed by replay and ACK."""

    path = Path(path).resolve()
    transaction_core = payload.get("transaction_core")
    if not isinstance(transaction_core, Mapping):
        raise ValueError("recovery_manifest_transaction_invalid")
    result = _validated_result_from_manifest(
        payload,
        manifest_path=manifest_path,
    )
    device = _strict_json_int(transaction_core.get("source_device"))
    inode = _strict_json_int(transaction_core.get("source_inode"))
    original_size = _strict_json_int(transaction_core.get("original_size"))
    trusted_end = _strict_json_int(transaction_core.get("trusted_end"))
    tail_byte_count = _strict_json_int(transaction_core.get("tail_byte_count"))
    prefix_sha256 = _clean(transaction_core.get("trusted_prefix_sha256"))
    tail_sha256 = _clean(transaction_core.get("tail_sha256"))
    if (
        device is None
        or device < 0
        or inode is None
        or inode <= 0
        or original_size is None
        or original_size < 0
        or trusted_end is None
        or trusted_end < 0
        or trusted_end >= original_size
        or tail_byte_count is None
        or tail_byte_count != original_size - trusted_end
        or tail_byte_count != result.isolated_byte_count
        or not _is_sha256(prefix_sha256)
        or not _is_sha256(tail_sha256)
        or _clean(transaction_core.get("source_path")) != str(path)
        or _clean(payload.get("source_path")) != str(path)
    ):
        raise ValueError("recovery_manifest_source_contract_invalid")
    expected_sidecar = path.with_name(
        f"{path.name}.dirty.{result.recovery_transaction_id}"
    ).resolve()
    if result.isolated_tail_path != expected_sidecar:
        raise ValueError("recovery_manifest_sidecar_path_mismatch")
    return _RecoveryManifestContract(
        result=result,
        source_path=path,
        source_device=device,
        source_inode=inode,
        original_size=original_size,
        trusted_end=trusted_end,
        tail_byte_count=tail_byte_count,
        trusted_prefix_sha256=prefix_sha256,
        tail_sha256=tail_sha256,
        isolated_tail_path=expected_sidecar,
    )


def _redurable_recovery_manifest_artifacts(
    contract: _RecoveryManifestContract,
    payload: Mapping[str, Any],
    *,
    manifest_path: Path,
) -> tuple[int, int, int]:
    """Re-prove the immutable redo artifacts and return manifest identity."""

    _redurable_regular_path(
        contract.isolated_tail_path,
        label="recovery_sidecar",
        expected_size=contract.tail_byte_count,
        expected_sha256=contract.tail_sha256,
    )
    canonical_manifest = _canonical_json_bytes(payload) + b"\n"
    _redurable_regular_path(
        manifest_path,
        label="recovery_manifest",
        expected_size=len(canonical_manifest),
        expected_sha256=hashlib.sha256(canonical_manifest).hexdigest(),
    )
    if _read_recovery_manifest(contract.source_path) != dict(payload):
        raise RuntimeError("recovery_manifest_changed_during_redurability")
    metadata = _regular_file_stat(
        manifest_path,
        label="recovery_manifest",
    )
    return (metadata.st_dev, metadata.st_ino, metadata.st_size)


def _prove_recovery_source_applied(
    contract: _RecoveryManifestContract,
) -> None:
    """ACK requires the source to be durably truncated to trusted_end."""

    path_metadata = _regular_file_stat(
        contract.source_path,
        label="recovery_source",
    )
    if (
        path_metadata.st_dev,
        path_metadata.st_ino,
    ) != (
        contract.source_device,
        contract.source_inode,
    ):
        raise RuntimeError("recovery_source_changed_before_ack")
    if path_metadata.st_size != contract.trusted_end:
        raise RuntimeError("recovery_source_not_applied")
    descriptor = os.open(str(contract.source_path), os.O_RDONLY)
    try:
        opened = os.fstat(descriptor)
        if (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
        ) != (
            contract.source_device,
            contract.source_inode,
            contract.trusted_end,
        ):
            raise RuntimeError("recovery_source_changed_before_ack")
        if _hash_descriptor_range(
            descriptor,
            start=0,
            byte_count=contract.trusted_end,
        ) != contract.trusted_prefix_sha256:
            raise RuntimeError("recovery_source_prefix_mismatch_before_ack")
        tick_journal._durability_barrier(descriptor)
        after_barrier = os.fstat(descriptor)
        if (
            after_barrier.st_dev,
            after_barrier.st_ino,
            after_barrier.st_size,
        ) != (
            contract.source_device,
            contract.source_inode,
            contract.trusted_end,
        ):
            raise RuntimeError("recovery_source_changed_during_ack")
        if _hash_descriptor_range(
            descriptor,
            start=0,
            byte_count=contract.trusted_end,
        ) != contract.trusted_prefix_sha256:
            raise RuntimeError("recovery_source_changed_during_ack")
    finally:
        os.close(descriptor)
    current = _regular_file_stat(
        contract.source_path,
        label="recovery_source",
    )
    if (
        current.st_dev,
        current.st_ino,
        current.st_size,
    ) != (
        contract.source_device,
        contract.source_inode,
        contract.trusted_end,
    ):
        raise RuntimeError("recovery_source_changed_during_ack")
    tick_journal._fsync_parent(contract.source_path)


def _prepare_and_apply_recovery_transaction(
    path: Path,
    *,
    trusted_end: int,
    expected_identity: tuple[int, int, int],
    previous_heartbeat: Mapping[str, Any],
    result: JournalRecoveryResult,
) -> JournalRecoveryResult:
    """Durably record the recovery result before truncating its evidence."""

    source_metadata = _regular_file_stat(path, label="recovery_source")
    if (
        source_metadata.st_dev,
        source_metadata.st_ino,
        source_metadata.st_size,
    ) != expected_identity:
        raise RuntimeError("journal_changed_during_recovery_open")
    original_size = expected_identity[2]
    tail_byte_count = original_size - trusted_end
    if tail_byte_count <= 0:
        raise ValueError("recovery_transaction_requires_nonempty_tail")

    source_descriptor = os.open(str(path), os.O_RDWR)
    try:
        opened_metadata = os.fstat(source_descriptor)
        opened_identity = (
            opened_metadata.st_dev,
            opened_metadata.st_ino,
            opened_metadata.st_size,
        )
        if opened_identity != expected_identity:
            raise RuntimeError("journal_changed_during_recovery_open")
        prefix_sha256 = _hash_descriptor_range(
            source_descriptor,
            start=0,
            byte_count=trusted_end,
        )
        tail_sha256 = _hash_descriptor_range(
            source_descriptor,
            start=trusted_end,
            byte_count=tail_byte_count,
        )
        result_projection = _recovery_result_projection(result)
        transaction_core = {
            "source_path": str(path.resolve()),
            "source_device": expected_identity[0],
            "source_inode": expected_identity[1],
            "original_size": original_size,
            "trusted_end": trusted_end,
            "trusted_prefix_sha256": prefix_sha256,
            "tail_byte_count": tail_byte_count,
            "tail_sha256": tail_sha256,
            "authority_projection": _authority_projection(previous_heartbeat),
            "result": result_projection,
        }
        transaction_id = hashlib.sha256(
            _canonical_json_bytes(transaction_core)
        ).hexdigest()
        isolated_tail_path = path.with_name(
            f"{path.name}.dirty.{transaction_id}"
        ).resolve()
        manifest_path = _recovery_manifest_path(path).resolve()
        enriched_result = JournalRecoveryResult(
            result.previous_durable_cursor,
            isolated_tail_path,
            tail_byte_count,
            result.disclosed_gap,
            result.disclosed_gaps,
            result.journal_schema,
            recovery_transaction_id=transaction_id,
            recovery_manifest_path=manifest_path,
            recovery_ack_required=True,
        )
        _ensure_recovery_sidecar(
            source_descriptor,
            isolated_tail_path=isolated_tail_path,
            trusted_end=trusted_end,
            tail_byte_count=tail_byte_count,
            tail_sha256=tail_sha256,
        )
        manifest_payload = {
            "record_type": RECOVERY_MANIFEST_RECORD_TYPE,
            "schema_version": RECOVERY_MANIFEST_SCHEMA_VERSION,
            "transaction_id": transaction_id,
            "transaction_core": transaction_core,
            "source_path": str(path.resolve()),
            "isolated_tail_path": str(isolated_tail_path),
            "result": _recovery_result_projection(enriched_result),
        }
        _atomic_write_recovery_manifest(manifest_path, manifest_payload)

        current_fd_metadata = os.fstat(source_descriptor)
        current_path_metadata = _regular_file_stat(
            path,
            label="recovery_source",
        )
        current_fd_identity = (
            current_fd_metadata.st_dev,
            current_fd_metadata.st_ino,
            current_fd_metadata.st_size,
        )
        current_path_identity = (
            current_path_metadata.st_dev,
            current_path_metadata.st_ino,
            current_path_metadata.st_size,
        )
        if (
            current_fd_identity != expected_identity
            or current_path_identity != expected_identity
            or _hash_descriptor_range(
                source_descriptor,
                start=0,
                byte_count=trusted_end,
            )
            != prefix_sha256
            or _hash_descriptor_range(
                source_descriptor,
                start=trusted_end,
                byte_count=tail_byte_count,
            )
            != tail_sha256
        ):
            raise RuntimeError("journal_changed_during_recovery_copy")

        os.ftruncate(source_descriptor, trusted_end)
        tick_journal._durability_barrier(source_descriptor)
        truncated_metadata = os.fstat(source_descriptor)
        if (
            truncated_metadata.st_dev,
            truncated_metadata.st_ino,
            truncated_metadata.st_size,
        ) != (
            expected_identity[0],
            expected_identity[1],
            trusted_end,
        ):
            raise RuntimeError("journal_changed_after_recovery_truncate")
    finally:
        os.close(source_descriptor)
    truncated_path_metadata = _regular_file_stat(
        path,
        label="recovery_source",
    )
    if (
        truncated_path_metadata.st_dev,
        truncated_path_metadata.st_ino,
        truncated_path_metadata.st_size,
    ) != (
        expected_identity[0],
        expected_identity[1],
        trusted_end,
    ):
        raise RuntimeError("journal_changed_after_recovery_truncate")
    tick_journal._fsync_parent(path)
    final_path_metadata = _regular_file_stat(
        path,
        label="recovery_source",
    )
    if (
        final_path_metadata.st_dev,
        final_path_metadata.st_ino,
        final_path_metadata.st_size,
    ) != (
        expected_identity[0],
        expected_identity[1],
        trusted_end,
    ):
        raise RuntimeError("journal_changed_after_recovery_commit")
    return enriched_result


def _replay_recovery_manifest(
    path: Path,
    previous_heartbeat: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> JournalRecoveryResult:
    """Redo a prepared truncate or certify an already-applied truncate."""

    manifest_path = _recovery_manifest_path(path).resolve()
    transaction_core = payload.get("transaction_core")
    if not isinstance(transaction_core, Mapping):
        raise ValueError("recovery_manifest_transaction_invalid")
    expected_authority = transaction_core.get("authority_projection")
    if not isinstance(expected_authority, Mapping) or not (
        _manifest_authority_matches_current(
            expected_authority,
            previous_heartbeat,
        )
    ):
        raise ValueError("recovery_manifest_authority_mismatch")
    contract = _validated_recovery_manifest_contract(
        path,
        payload,
        manifest_path=manifest_path,
    )
    result = contract.result
    device = contract.source_device
    inode = contract.source_inode
    original_size = contract.original_size
    trusted_end = contract.trusted_end
    tail_byte_count = contract.tail_byte_count
    prefix_sha256 = contract.trusted_prefix_sha256
    tail_sha256 = contract.tail_sha256
    _redurable_recovery_manifest_artifacts(
        contract,
        payload,
        manifest_path=manifest_path,
    )

    path_metadata = _regular_file_stat(path, label="recovery_source")
    if (path_metadata.st_dev, path_metadata.st_ino) != (device, inode):
        raise RuntimeError("journal_changed_during_recovery_replay")
    if path_metadata.st_size not in {original_size, trusted_end}:
        raise RuntimeError("journal_size_unknown_during_recovery_replay")
    descriptor = os.open(str(path), os.O_RDWR)
    try:
        opened_metadata = os.fstat(descriptor)
        if (
            opened_metadata.st_dev,
            opened_metadata.st_ino,
            opened_metadata.st_size,
        ) != (
            device,
            inode,
            path_metadata.st_size,
        ):
            raise RuntimeError("journal_changed_during_recovery_replay")
        if _hash_descriptor_range(
            descriptor,
            start=0,
            byte_count=trusted_end,
        ) != prefix_sha256:
            raise RuntimeError("journal_prefix_changed_during_recovery_replay")
        if opened_metadata.st_size == original_size:
            if _hash_descriptor_range(
                descriptor,
                start=trusted_end,
                byte_count=tail_byte_count,
            ) != tail_sha256:
                raise RuntimeError("journal_tail_changed_during_recovery_replay")
            os.ftruncate(descriptor, trusted_end)
        tick_journal._durability_barrier(descriptor)
        replayed_metadata = os.fstat(descriptor)
        if (
            replayed_metadata.st_dev,
            replayed_metadata.st_ino,
            replayed_metadata.st_size,
        ) != (device, inode, trusted_end):
            raise RuntimeError("journal_changed_after_recovery_replay")
    finally:
        os.close(descriptor)
    replayed_path_metadata = _regular_file_stat(
        path,
        label="recovery_source",
    )
    if (
        replayed_path_metadata.st_dev,
        replayed_path_metadata.st_ino,
        replayed_path_metadata.st_size,
    ) != (device, inode, trusted_end):
        raise RuntimeError("journal_changed_after_recovery_replay")
    tick_journal._fsync_parent(path)
    committed_path_metadata = _regular_file_stat(
        path,
        label="recovery_source",
    )
    if (
        committed_path_metadata.st_dev,
        committed_path_metadata.st_ino,
        committed_path_metadata.st_size,
    ) != (device, inode, trusted_end):
        raise RuntimeError("journal_changed_after_recovery_commit")
    return result


def _manifest_source_path(manifest_path: Path) -> Path:
    suffix = ".stage179.recovery.json"
    name = manifest_path.name
    if not name.startswith(".") or not name.endswith(suffix):
        raise ValueError("recovery_manifest_path_invalid")
    source_name = name[1 : -len(suffix)]
    if not source_name:
        raise ValueError("recovery_manifest_path_invalid")
    return manifest_path.with_name(source_name)


def _committed_heartbeat_covers_recovery(
    recovery: JournalRecoveryResult,
    heartbeat: Mapping[str, Any],
) -> bool:
    state = _clean(heartbeat.get("journal_session_state"))
    lifecycle_committed = bool(
        (
            state == "starting"
            and heartbeat.get("stopped") is False
        )
        or (
            state in {"fault_stopped", "recovery_required_stopped"}
            and heartbeat.get("stopped") is True
            and heartbeat.get("clean_shutdown") is False
            and heartbeat.get("writer_alive") is False
        )
    )
    if (
        heartbeat.get("journal_authority_committed") is not True
        or not lifecycle_committed
        or heartbeat.get("stream_ready") is not False
        or heartbeat.get("transport_ready") is not False
        or _clean(heartbeat.get("prior_recovery_transaction_id"))
        != recovery.recovery_transaction_id
        or _clean(heartbeat.get("prior_recovery_manifest_path"))
        != str(recovery.recovery_manifest_path.resolve())
    ):
        return False
    committed_gap_identities = {
        (
            gap.feed_session_id,
            gap.start_ingress_sequence,
            gap.end_ingress_sequence,
            gap.reason,
        )
        for gap in _prior_gap_lineage(heartbeat)
    }
    return all(
        (
            gap.feed_session_id,
            gap.start_ingress_sequence,
            gap.end_ingress_sequence,
            gap.reason,
        )
        in committed_gap_identities
        for gap in recovery.disclosed_gaps
    )


def _read_descriptor_payload(descriptor: int) -> bytes:
    with os.fdopen(os.dup(descriptor), "rb", buffering=0) as handle:
        handle.seek(0)
        return handle.read(MAX_RECOVERY_HEARTBEAT_BYTES + 1)


def _load_redurable_heartbeat_evidence(
    path: Path,
) -> _RedurableHeartbeatEvidence:
    """Read, barrier, and byte-recheck the exact heartbeat used for ACK."""

    path = Path(path).resolve()
    metadata = _regular_file_stat(path, label="recovery_heartbeat")
    if metadata.st_size <= 0 or metadata.st_size > MAX_RECOVERY_HEARTBEAT_BYTES:
        raise ValueError("recovery_heartbeat_size_invalid")
    identity = (metadata.st_dev, metadata.st_ino, metadata.st_size)
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino, opened.st_size) != identity:
            raise RuntimeError("recovery_heartbeat_changed_before_ack")
        raw = _read_descriptor_payload(descriptor)
        if len(raw) != metadata.st_size:
            raise RuntimeError("recovery_heartbeat_changed_during_ack")
        tick_journal._durability_barrier(descriptor)
        after_barrier = os.fstat(descriptor)
        if (
            after_barrier.st_dev,
            after_barrier.st_ino,
            after_barrier.st_size,
        ) != identity:
            raise RuntimeError("recovery_heartbeat_changed_during_ack")
        if _read_descriptor_payload(descriptor) != raw:
            raise RuntimeError("recovery_heartbeat_changed_during_ack")
    finally:
        os.close(descriptor)
    current = _regular_file_stat(path, label="recovery_heartbeat")
    if (current.st_dev, current.st_ino, current.st_size) != identity:
        raise RuntimeError("recovery_heartbeat_changed_during_ack")
    tick_journal._fsync_parent(path)
    final_descriptor = os.open(str(path), os.O_RDONLY)
    try:
        final = os.fstat(final_descriptor)
        if (final.st_dev, final.st_ino, final.st_size) != identity:
            raise RuntimeError("recovery_heartbeat_changed_after_ack_barrier")
        if _read_descriptor_payload(final_descriptor) != raw:
            raise RuntimeError("recovery_heartbeat_changed_after_ack_barrier")
    finally:
        os.close(final_descriptor)
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise ValueError("recovery_heartbeat_invalid_json") from exc
    if not isinstance(payload, dict):
        raise ValueError("recovery_heartbeat_invalid_root")
    return _RedurableHeartbeatEvidence(
        payload=payload,
        identity=identity,
        payload_sha256=hashlib.sha256(raw).hexdigest(),
    )


def _load_redurable_heartbeat(path: Path) -> dict[str, Any]:
    return _load_redurable_heartbeat_evidence(path).payload


def _same_heartbeat_evidence(
    first: _RedurableHeartbeatEvidence,
    second: _RedurableHeartbeatEvidence,
) -> bool:
    return bool(
        first.identity == second.identity
        and first.payload_sha256 == second.payload_sha256
        and first.payload == second.payload
    )


def _manifest_identity_matches(
    manifest_path: Path,
    expected: tuple[int, int, int],
) -> bool:
    metadata = _regular_file_stat(
        manifest_path,
        label="recovery_manifest",
    )
    return (metadata.st_dev, metadata.st_ino, metadata.st_size) == expected


def acknowledge_recovery_manifest(
    recovery: JournalRecoveryResult,
    committed_heartbeat_path: Path,
) -> None:
    """Delete redo authority only after a durable on-disk H1 contains it."""

    if not recovery.recovery_ack_required:
        return
    manifest_path = recovery.recovery_manifest_path
    if manifest_path is None or not recovery.recovery_transaction_id:
        raise ValueError("recovery_ack_handle_missing")
    manifest_path = manifest_path.resolve()
    initial_heartbeat = _load_redurable_heartbeat_evidence(
        committed_heartbeat_path
    )
    source_path = _manifest_source_path(manifest_path)
    if _recovery_manifest_path(source_path).resolve() != manifest_path:
        raise ValueError("recovery_manifest_path_invalid")
    with tick_journal._exclusive_journal_lock(source_path):
        payload = _read_recovery_manifest(source_path)
        if payload is None:
            return
        contract = _validated_recovery_manifest_contract(
            source_path,
            payload,
            manifest_path=manifest_path,
        )
        manifest_recovery = contract.result
        if (
            manifest_recovery.recovery_transaction_id
            != recovery.recovery_transaction_id
        ):
            raise ValueError("recovery_manifest_ack_transaction_mismatch")
        manifest_identity = _redurable_recovery_manifest_artifacts(
            contract,
            payload,
            manifest_path=manifest_path,
        )
        _prove_recovery_source_applied(contract)
        locked_heartbeat = _load_redurable_heartbeat_evidence(
            committed_heartbeat_path
        )
        if not _same_heartbeat_evidence(
            initial_heartbeat,
            locked_heartbeat,
        ):
            raise RuntimeError("recovery_heartbeat_changed_before_manifest_ack")
        if not _committed_heartbeat_covers_recovery(
            manifest_recovery,
            locked_heartbeat.payload,
        ):
            raise ValueError("recovery_manifest_not_committed_in_heartbeat")
        if (
            _read_recovery_manifest(source_path) != dict(payload)
            or not _manifest_identity_matches(
                manifest_path,
                manifest_identity,
            )
        ):
            raise RuntimeError("recovery_manifest_changed_before_ack")
        manifest_path.unlink()
        tick_journal._fsync_parent(manifest_path)


def acknowledge_committed_recovery_manifest(
    committed_heartbeat_path: Path,
) -> bool:
    """Idempotently finish ACK after H1 committed but the owner crashed."""

    initial_heartbeat = _load_redurable_heartbeat_evidence(
        committed_heartbeat_path
    )
    committed_heartbeat = initial_heartbeat.payload
    transaction_id = _clean(
        committed_heartbeat.get("prior_recovery_transaction_id")
    )
    raw_manifest_path = _clean(
        committed_heartbeat.get("prior_recovery_manifest_path")
    )
    if not transaction_id and not raw_manifest_path:
        return False
    if not transaction_id or not raw_manifest_path:
        raise ValueError("recovery_ack_handle_incomplete")
    manifest_path = Path(raw_manifest_path).resolve()
    source_path = _manifest_source_path(manifest_path)
    if _recovery_manifest_path(source_path).resolve() != manifest_path:
        raise ValueError("recovery_manifest_path_invalid")
    with tick_journal._exclusive_journal_lock(source_path):
        payload = _read_recovery_manifest(source_path)
        if payload is None:
            return False
        contract = _validated_recovery_manifest_contract(
            source_path,
            payload,
            manifest_path=manifest_path,
        )
        recovery = contract.result
        if recovery.recovery_transaction_id != transaction_id:
            raise ValueError("recovery_manifest_ack_transaction_mismatch")
        manifest_identity = _redurable_recovery_manifest_artifacts(
            contract,
            payload,
            manifest_path=manifest_path,
        )
        _prove_recovery_source_applied(contract)
        locked_heartbeat = _load_redurable_heartbeat_evidence(
            committed_heartbeat_path
        )
        if not _same_heartbeat_evidence(
            initial_heartbeat,
            locked_heartbeat,
        ):
            raise RuntimeError("recovery_heartbeat_changed_before_manifest_ack")
        if not _committed_heartbeat_covers_recovery(
            recovery,
            locked_heartbeat.payload,
        ):
            raise ValueError("recovery_manifest_not_committed_in_heartbeat")
        if (
            _read_recovery_manifest(source_path) != dict(payload)
            or not _manifest_identity_matches(
                manifest_path,
                manifest_identity,
            )
        ):
            raise RuntimeError("recovery_manifest_changed_before_ack")
        manifest_path.unlink()
        tick_journal._fsync_parent(manifest_path)
    return True


def recover_or_isolate_dirty_tail(
    journal_path: Path,
    previous_heartbeat: Mapping[str, Any],
) -> JournalRecoveryResult:
    """Validate authority, fence the segment, then recover one journal."""

    path = Path(journal_path)
    with tick_journal._exclusive_journal_lock(path):
        pending_manifest = _read_recovery_manifest(path)
        if pending_manifest is not None:
            return _replay_recovery_manifest(
                path,
                previous_heartbeat,
                pending_manifest,
            )
        _validate_recovery_contract(path, previous_heartbeat)
        return _recover_or_isolate_dirty_tail_locked(
            path,
            previous_heartbeat,
        )


def _recover_or_isolate_dirty_tail_locked(
    journal_path: Path,
    previous_heartbeat: Mapping[str, Any],
) -> JournalRecoveryResult:
    """Stream-validate committed batches and isolate every unknown suffix."""

    path = Path(journal_path)
    inherited_gaps = _prior_gap_lineage(previous_heartbeat)
    feed_session_id = _clean(previous_heartbeat.get("feed_session_id"))
    heartbeat_durable_sequence = _heartbeat_nonnegative_int(
        previous_heartbeat,
        "durable_ingress_sequence",
        fallback=_heartbeat_nonnegative_int(
            previous_heartbeat,
            "stream_sequence",
        ),
    )
    heartbeat_last_ingress_sequence = _heartbeat_nonnegative_int(
        previous_heartbeat,
        "last_ingress_sequence",
        fallback=heartbeat_durable_sequence,
    )
    _, heartbeat_gap_end, heartbeat_gap_reason = _current_gap_boundary(
        previous_heartbeat
    )
    declared_schema = _clean(previous_heartbeat.get("journal_schema"))
    if not previous_heartbeat and not path.exists():
        return JournalRecoveryResult(
            None,
            None,
            0,
            None,
            (),
            JOURNAL_SCHEMA_FRAMED_V1,
        )
    if declared_schema not in {
        JOURNAL_SCHEMA_FRAMED_V1,
        JOURNAL_SCHEMA_LEGACY_V0,
    }:
        raise ValueError("journal_schema_missing_or_unsupported")
    session_state = _journal_session_state(previous_heartbeat)
    revoked_from, revoked_through, revocation_reason = _hard_revocation_boundary(
        previous_heartbeat
    )
    explicit_gap_reason = revocation_reason or heartbeat_gap_reason

    initial_stat = path.stat() if path.exists() else None
    file_size = initial_stat.st_size if initial_stat is not None else 0
    trusted_end = 0
    recovered_durable_sequence = 0
    observed_max_sequence = 0
    suffix_reason = ""

    if declared_schema == JOURNAL_SCHEMA_FRAMED_V1 and file_size > 0:
        with path.open("rb") as handle:
            raw_header = handle.readline(MAX_JOURNAL_LINE_BYTES + 1)
            header_end = handle.tell()
            header, header_error = _parse_record_line(raw_header)
            segment_id = (
                _validated_header_segment_id(
                    header or {},
                    feed_session_id=feed_session_id,
                )
                if not header_error
                else ""
            )
            if not segment_id:
                if (
                    header is not None
                    and header.get(JOURNAL_RECORD_TYPE_FIELD)
                    != JOURNAL_HEADER_RECORD_TYPE
                ):
                    suffix_reason = "journal_header_missing"
                else:
                    suffix_reason = header_error or "journal_header_invalid"
            else:
                trusted_end = header_end
                expected_sequence = 1
                pending_first = 0
                pending_last = 0
                pending_count = 0
                pending_bytes = 0
                pending_digest = hashlib.sha256()
                while True:
                    raw_line = handle.readline(MAX_JOURNAL_LINE_BYTES + 1)
                    if not raw_line:
                        break
                    line_end = handle.tell()
                    row, parse_error = _parse_record_line(raw_line)
                    if parse_error:
                        suffix_reason = parse_error
                        break
                    control_type = row.get(JOURNAL_RECORD_TYPE_FIELD)
                    if control_type == JOURNAL_BATCH_COMMIT_RECORD_TYPE:
                        frame_end = _strict_json_int(
                            row.get("last_ingress_sequence")
                        )
                        if frame_end is None:
                            frame_end = 0
                        observed_max_sequence = max(
                            observed_max_sequence,
                            frame_end,
                        )
                        if not _commit_frame_matches(
                            row,
                            pending_first_sequence=pending_first,
                            pending_last_sequence=pending_last,
                            pending_row_count=pending_count,
                            pending_payload_byte_count=pending_bytes,
                            pending_payload_sha256=pending_digest.hexdigest(),
                            feed_session_id=feed_session_id,
                            segment_id=segment_id,
                            previous_durable_sequence=recovered_durable_sequence,
                        ):
                            suffix_reason = "journal_commit_frame_invalid"
                            break
                        if revoked_from > 0 and frame_end >= revoked_from:
                            suffix_reason = revocation_reason
                            break
                        recovered_durable_sequence = frame_end
                        trusted_end = line_end
                        expected_sequence = frame_end + 1
                        pending_first = 0
                        pending_last = 0
                        pending_count = 0
                        pending_bytes = 0
                        pending_digest = hashlib.sha256()
                        continue
                    if control_type:
                        suffix_reason = "journal_unknown_control_record"
                        break
                    row_sequence, identity_error = (
                        _validated_framed_tick_row_identity(
                            row,
                            feed_session_id=feed_session_id,
                        )
                    )
                    if identity_error:
                        suffix_reason = identity_error
                        break
                    assert row_sequence is not None
                    observed_max_sequence = max(
                        observed_max_sequence,
                        row_sequence,
                    )
                    if row_sequence != expected_sequence:
                        suffix_reason = "journal_sequence_gap"
                        break
                    pending_count += 1
                    if pending_count > DEFAULT_WRITER_BATCH_SIZE:
                        suffix_reason = "journal_batch_row_limit_exceeded"
                        break
                    pending_first = pending_first or row_sequence
                    pending_last = row_sequence
                    pending_bytes += len(raw_line)
                    if pending_bytes > MAX_JOURNAL_BATCH_BYTES:
                        suffix_reason = "journal_batch_payload_limit_exceeded"
                        break
                    pending_digest.update(raw_line)
                    expected_sequence += 1
        if not suffix_reason and trusted_end < file_size:
            suffix_reason = "journal_uncommitted_suffix"
    elif declared_schema == JOURNAL_SCHEMA_LEGACY_V0 and file_size > 0:
        expected_sequence = 1
        with path.open("rb") as handle:
            while True:
                raw_line = handle.readline(MAX_JOURNAL_LINE_BYTES + 1)
                if not raw_line:
                    break
                line_end = handle.tell()
                row, parse_error = _parse_record_line(raw_line)
                if parse_error:
                    suffix_reason = parse_error
                    break
                if row.get(JOURNAL_RECORD_TYPE_FIELD):
                    suffix_reason = "legacy_journal_unknown_record"
                    break
                if _clean(row.get("feed_session_id")) != feed_session_id:
                    suffix_reason = "journal_feed_session_mismatch"
                    break
                row_sequence = _strict_json_int(row.get("ingress_sequence"))
                if row_sequence is None:
                    suffix_reason = "journal_sequence_invalid"
                    break
                observed_max_sequence = max(observed_max_sequence, row_sequence)
                if row_sequence != expected_sequence:
                    suffix_reason = "journal_sequence_gap"
                    break
                if row_sequence > heartbeat_durable_sequence:
                    suffix_reason = "legacy_journal_uncommitted_suffix"
                    break
                recovered_durable_sequence = row_sequence
                trusted_end = line_end
                expected_sequence += 1
        if not suffix_reason and trusted_end < file_size:
            suffix_reason = "legacy_journal_uncommitted_suffix"

    tail_byte_count = max(0, file_size - trusted_end)
    current_stat = path.stat() if path.exists() else None
    if (
        (initial_stat is None) != (current_stat is None)
        or (
            initial_stat is not None
            and current_stat is not None
            and (
                initial_stat.st_dev,
                initial_stat.st_ino,
                initial_stat.st_size,
            )
            != (
                current_stat.st_dev,
                current_stat.st_ino,
                current_stat.st_size,
            )
        )
    ):
        raise RuntimeError("journal_changed_during_recovery_scan")

    gap_end = max(
        heartbeat_durable_sequence,
        heartbeat_last_ingress_sequence,
        heartbeat_gap_end,
        revoked_through,
        observed_max_sequence,
    )
    corruption_precedes_declared_durable = bool(
        suffix_reason
        and recovered_durable_sequence < heartbeat_durable_sequence
    )
    recovered_gap_reason = (
        suffix_reason
        if corruption_precedes_declared_durable
        else explicit_gap_reason or suffix_reason
    )
    current_gap: TickStreamGap | None = None
    if gap_end > recovered_durable_sequence:
        current_gap = TickStreamGap(
            feed_session_id or "unknown_prior_feed",
            recovered_durable_sequence + 1,
            gap_end,
            recovered_gap_reason or "durable_cursor_missing_from_journal",
        )
    elif tail_byte_count > 0:
        current_gap = TickStreamGap(
            feed_session_id or "unknown_prior_feed",
            recovered_durable_sequence + 1,
            max(recovered_durable_sequence + 1, observed_max_sequence),
            recovered_gap_reason or "unknown_prior_journal_suffix",
        )
    elif session_state in {"starting", "running", "fault_stopped"}:
        current_gap = TickStreamGap(
            feed_session_id or "unknown_prior_feed",
            recovered_durable_sequence + 1,
            max(recovered_durable_sequence + 1, gap_end),
            "prior_session_unclean",
        )

    disclosed_gaps = list(inherited_gaps)
    if current_gap is not None:
        identity = (
            current_gap.feed_session_id,
            current_gap.start_ingress_sequence,
            current_gap.end_ingress_sequence,
            current_gap.reason,
        )
        if identity not in {
            (
                gap.feed_session_id,
                gap.start_ingress_sequence,
                gap.end_ingress_sequence,
                gap.reason,
            )
            for gap in disclosed_gaps
        }:
            disclosed_gaps.append(current_gap)
    disclosed_gap = current_gap or (disclosed_gaps[-1] if disclosed_gaps else None)
    previous_cursor = (
        DurableTickCursor(
            feed_session_id,
            recovered_durable_sequence,
            journal_byte_offset=trusted_end,
            journal_schema=declared_schema,
        )
        if feed_session_id and recovered_durable_sequence > 0
        else None
    )
    result = JournalRecoveryResult(
        previous_durable_cursor=previous_cursor,
        isolated_tail_path=None,
        isolated_byte_count=tail_byte_count,
        disclosed_gap=disclosed_gap,
        disclosed_gaps=tuple(disclosed_gaps),
        journal_schema=declared_schema,
    )
    if tail_byte_count > 0:
        if initial_stat is None:
            raise RuntimeError("journal_missing_during_recovery_transaction")
        return _prepare_and_apply_recovery_transaction(
            path,
            trusted_end=trusted_end,
            expected_identity=(
                initial_stat.st_dev,
                initial_stat.st_ino,
                initial_stat.st_size,
            ),
            previous_heartbeat=previous_heartbeat,
            result=result,
        )
    if path.exists() and file_size > 0:
        # A complete frame may remain after an earlier barrier returned an
        # ambiguous error.  This new barrier is the durability proof for the
        # recovered cursor; no cursor is exposed if it fails.
        descriptor = os.open(str(path), os.O_RDWR)
        try:
            tick_journal._durability_barrier(descriptor)
        finally:
            os.close(descriptor)
    return result
