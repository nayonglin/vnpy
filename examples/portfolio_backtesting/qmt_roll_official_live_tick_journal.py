from __future__ import annotations

from pathlib import Path
from queue import Empty
from types import MappingProxyType
from typing import Any, Mapping
import errno
import hashlib
import json
import os
import threading
import time

from qmt_roll_official_live_tick_types import (
    JOURNAL_BATCH_COMMIT_RECORD_TYPE,
    JOURNAL_BATCH_COMMIT_SCHEMA_VERSION,
    JOURNAL_HEADER_RECORD_TYPE,
    JOURNAL_RECORD_TYPE_FIELD,
    DurableTickBatch,
    DurableTickCursor,
    JournalRecoveryResult,
    TickIngressEnvelope,
    TickStreamGap,
)


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _durability_barrier(file_descriptor: int) -> None:
    """The single seam for journal durability and fault injection."""

    os.fsync(file_descriptor)


def _write_all(handle: Any, payload: bytes) -> None:
    """Write every byte even when a raw file object reports a short write."""

    remaining = memoryview(payload)
    while remaining:
        written = handle.write(remaining)
        if not isinstance(written, int) or written <= 0:
            raise OSError(errno.EIO, "journal write made no forward progress")
        remaining = remaining[written:]


def _validated_header_segment_id(
    header: Mapping[str, Any],
    *,
    feed_session_id: str,
) -> str:
    try:
        schema = int(header.get("schema_version", 0) or 0)
        first_sequence = int(header.get("first_ingress_sequence", 0) or 0)
    except (TypeError, ValueError):
        return ""
    segment_id = _clean(header.get("segment_id"))
    if not (
        header.get(JOURNAL_RECORD_TYPE_FIELD) == JOURNAL_HEADER_RECORD_TYPE
        and schema == JOURNAL_BATCH_COMMIT_SCHEMA_VERSION
        and _clean(header.get("feed_session_id")) == feed_session_id
        and segment_id
        and first_sequence == 1
    ):
        return ""
    return segment_id


def _commit_frame_is_valid(
    frame: Mapping[str, Any],
    *,
    pending_rows: list[dict[str, Any]],
    pending_payload: bytes,
    feed_session_id: str,
    segment_id: str,
    previous_durable_sequence: int,
) -> bool:
    try:
        frame_schema = int(frame.get("schema_version", 0) or 0)
        frame_previous = int(
            frame.get("previous_durable_ingress_sequence", -1)
        )
        frame_start = int(frame.get("first_ingress_sequence", 0) or 0)
        frame_end = int(frame.get("last_ingress_sequence", 0) or 0)
        frame_count = int(frame.get("row_count", 0) or 0)
        frame_byte_count = int(frame.get("payload_byte_count", -1))
        pending_start = int(pending_rows[0].get("ingress_sequence", 0) or 0)
        pending_end = int(pending_rows[-1].get("ingress_sequence", 0) or 0)
    except (IndexError, TypeError, ValueError):
        return False
    return bool(
        frame.get(JOURNAL_RECORD_TYPE_FIELD) == JOURNAL_BATCH_COMMIT_RECORD_TYPE
        and frame_schema == JOURNAL_BATCH_COMMIT_SCHEMA_VERSION
        and _clean(frame.get("feed_session_id")) == feed_session_id
        and _clean(frame.get("segment_id")) == segment_id
        and frame_previous == previous_durable_sequence
        and frame_start == previous_durable_sequence + 1
        and frame_start == pending_start
        and frame_end == pending_end
        and frame_count == len(pending_rows)
        and frame_byte_count == len(pending_payload)
        and _clean(frame.get("payload_sha256"))
        == hashlib.sha256(pending_payload).hexdigest()
    )


class AsyncTickJournalWriter:
    """Single owner of the append fd and the fsync durability transition."""

    def __init__(self, pipeline: Any) -> None:
        self.pipeline = pipeline
        self._stop_requested = threading.Event()
        self._stopped = threading.Event()
        self._thread = threading.Thread(
            target=self.run,
            name=f"tick-journal-{pipeline.feed_session_id}",
            daemon=True,
        )
        self._started = False

    @property
    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._thread.start()

    def request_stop(self) -> None:
        self._stop_requested.set()

    def join(self, timeout_seconds: float) -> bool:
        if not self._started:
            return True
        self._thread.join(max(0.0, float(timeout_seconds)))
        return not self._thread.is_alive()

    def wait_stopped(self, timeout_seconds: float) -> bool:
        return self._stopped.wait(max(0.0, float(timeout_seconds)))

    def _next_batch(self) -> list[TickIngressEnvelope]:
        queue = self.pipeline._ingress_queue
        try:
            first = (
                queue.get_nowait()
                if self._stop_requested.is_set()
                else queue.get(timeout=self.pipeline.writer_flush_seconds)
            )
        except Empty:
            return []
        batch = [first]
        deadline = time.monotonic() + self.pipeline.writer_flush_seconds
        while len(batch) < self.pipeline.writer_batch_size:
            if self._stop_requested.is_set():
                timeout = 0.0
            else:
                timeout = max(0.0, deadline - time.monotonic())
            try:
                item = queue.get_nowait() if timeout <= 0 else queue.get(timeout=timeout)
            except Empty:
                break
            batch.append(item)
        return batch

    @staticmethod
    def _serialized_batch(batch: list[TickIngressEnvelope]) -> bytes:
        return "".join(
            json.dumps(
                dict(envelope.tick_row),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
            for envelope in batch
        ).encode("utf-8")

    @staticmethod
    def _serialized_commit_frame(
        batch: list[TickIngressEnvelope],
        payload: bytes,
    ) -> bytes:
        frame = {
            JOURNAL_RECORD_TYPE_FIELD: JOURNAL_BATCH_COMMIT_RECORD_TYPE,
            "schema_version": JOURNAL_BATCH_COMMIT_SCHEMA_VERSION,
            "feed_session_id": batch[0].feed_session_id,
            "segment_id": batch[0].feed_session_id,
            "previous_durable_ingress_sequence": batch[0].ingress_sequence - 1,
            "first_ingress_sequence": batch[0].ingress_sequence,
            "last_ingress_sequence": batch[-1].ingress_sequence,
            "row_count": len(batch),
            "payload_byte_count": len(payload),
            "payload_sha256": hashlib.sha256(payload).hexdigest(),
        }
        return (
            json.dumps(
                frame,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")

    def _serialized_header(self) -> bytes:
        return (
            json.dumps(
                {
                    JOURNAL_RECORD_TYPE_FIELD: JOURNAL_HEADER_RECORD_TYPE,
                    "schema_version": JOURNAL_BATCH_COMMIT_SCHEMA_VERSION,
                    "feed_session_id": self.pipeline.feed_session_id,
                    "segment_id": self.pipeline.feed_session_id,
                    "first_ingress_sequence": 1,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")

    def run(self) -> None:
        path = self.pipeline.journal_segment_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(
                str(path),
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND,
                0o600,
            )
            with os.fdopen(descriptor, "wb", buffering=0) as handle:
                _write_all(handle, self._serialized_header())
                _durability_barrier(handle.fileno())
                _fsync_parent(path)
                while True:
                    if self.pipeline._writer_commit_revoked():
                        return
                    batch = self._next_batch()
                    if not batch:
                        if self._stop_requested.is_set():
                            break
                        continue
                    try:
                        self.pipeline._validate_batch_for_journal(batch)
                        payload = self._serialized_batch(batch)
                        frame = payload + self._serialized_commit_frame(batch, payload)
                        _write_all(handle, frame)
                        _durability_barrier(handle.fileno())
                    except Exception as exc:
                        self.pipeline._latch_writer_error(exc)
                        for _item in batch:
                            self.pipeline._ingress_queue.task_done()
                        return
                    self.pipeline._commit_durable_batch(batch)
                    for _item in batch:
                        self.pipeline._ingress_queue.task_done()
        except Exception as exc:
            self.pipeline._latch_writer_error(exc)
        finally:
            self._stopped.set()


class TickStreamJournalReader:
    def __init__(self, journal_segment_path: Path) -> None:
        self.journal_segment_path = Path(journal_segment_path)

    @staticmethod
    def _gap(
        feed_session_id: str,
        start: int,
        end: int,
        reason: str,
    ) -> TickStreamGap:
        return TickStreamGap(
            feed_session_id=feed_session_id,
            start_ingress_sequence=max(1, int(start)),
            end_ingress_sequence=max(1, int(start), int(end)),
            reason=reason,
        )

    def _read_entries(
        self,
    ) -> tuple[list[tuple[bytes, dict[str, Any]]], str]:
        if not self.journal_segment_path.exists():
            return [], "journal_missing"
        data = self.journal_segment_path.read_bytes()
        entries: list[tuple[bytes, dict[str, Any]]] = []
        parsed_bytes = 0
        parse_error = ""
        for raw_line in data.splitlines(keepends=True):
            if not raw_line.endswith(b"\n"):
                parse_error = "journal_partial_line_before_durable_watermark"
                break
            try:
                row = json.loads(raw_line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                parse_error = "journal_invalid_json_before_durable_watermark"
                break
            if not isinstance(row, dict):
                parse_error = "journal_invalid_record_before_durable_watermark"
                break
            entries.append((raw_line, row))
            parsed_bytes += len(raw_line)
        if not parse_error and parsed_bytes < len(data):
            parse_error = "journal_invalid_suffix_before_durable_watermark"
        return entries, parse_error

    def _validated_framed_rows(
        self,
        entries: list[tuple[bytes, dict[str, Any]]],
        *,
        feed_session_id: str,
        durable_sequence: int,
        parse_error: str,
    ) -> tuple[list[Mapping[str, Any]], TickStreamGap | None]:
        if not entries:
            return [], self._gap(
                feed_session_id,
                1,
                durable_sequence,
                parse_error or "journal_header_missing",
            )
        segment_id = _validated_header_segment_id(
            entries[0][1],
            feed_session_id=feed_session_id,
        )
        if not segment_id:
            return [], self._gap(
                feed_session_id,
                1,
                durable_sequence,
                "journal_header_invalid",
            )

        committed_rows: list[Mapping[str, Any]] = []
        pending_rows: list[dict[str, Any]] = []
        pending_payload = bytearray()
        committed_sequence = 0
        expected_sequence = 1
        reason = ""
        for raw_line, row in entries[1:]:
            control_type = row.get(JOURNAL_RECORD_TYPE_FIELD)
            if control_type == JOURNAL_BATCH_COMMIT_RECORD_TYPE:
                if not _commit_frame_is_valid(
                    row,
                    pending_rows=pending_rows,
                    pending_payload=bytes(pending_payload),
                    feed_session_id=feed_session_id,
                    segment_id=segment_id,
                    previous_durable_sequence=committed_sequence,
                ):
                    reason = "journal_commit_frame_invalid"
                    break
                committed_rows.extend(
                    MappingProxyType(dict(pending))
                    for pending in pending_rows
                )
                committed_sequence = int(
                    row.get("last_ingress_sequence", 0) or 0
                )
                expected_sequence = committed_sequence + 1
                pending_rows.clear()
                pending_payload.clear()
                if committed_sequence >= durable_sequence:
                    break
                continue
            if control_type:
                reason = "journal_unknown_control_record"
                break
            if _clean(row.get("feed_session_id")) != feed_session_id:
                reason = "journal_feed_session_mismatch"
                break
            try:
                sequence = int(row.get("ingress_sequence", 0) or 0)
            except (TypeError, ValueError):
                reason = "journal_sequence_invalid"
                break
            if sequence != expected_sequence:
                reason = "journal_sequence_gap"
                break
            pending_rows.append(row)
            pending_payload.extend(raw_line)
            expected_sequence += 1

        if committed_sequence < durable_sequence:
            return committed_rows, self._gap(
                feed_session_id,
                committed_sequence + 1,
                durable_sequence,
                reason
                or parse_error
                or "journal_rows_missing_commit_frame",
            )
        return [
            row
            for row in committed_rows
            if int(row.get("ingress_sequence", 0) or 0) <= durable_sequence
        ], None

    def _validated_legacy_rows(
        self,
        entries: list[tuple[bytes, dict[str, Any]]],
        *,
        feed_session_id: str,
        durable_sequence: int,
        parse_error: str,
    ) -> tuple[list[Mapping[str, Any]], TickStreamGap | None]:
        committed_rows: list[Mapping[str, Any]] = []
        expected_sequence = 1
        reason = ""
        failure_end = durable_sequence
        for _raw_line, row in entries:
            if row.get(JOURNAL_RECORD_TYPE_FIELD):
                reason = "journal_header_missing"
                break
            if _clean(row.get("feed_session_id")) != feed_session_id:
                reason = "journal_feed_session_mismatch"
                break
            try:
                sequence = int(row.get("ingress_sequence", 0) or 0)
            except (TypeError, ValueError):
                reason = "journal_sequence_invalid"
                break
            if sequence != expected_sequence:
                reason = "journal_sequence_gap"
                failure_end = max(expected_sequence, sequence - 1)
                break
            if sequence > durable_sequence:
                break
            committed_rows.append(MappingProxyType(dict(row)))
            expected_sequence += 1
            if sequence >= durable_sequence:
                break

        if expected_sequence <= durable_sequence:
            return committed_rows, self._gap(
                feed_session_id,
                expected_sequence,
                failure_end,
                reason
                or parse_error
                or "durable_rows_missing_from_journal",
            )
        return committed_rows, None

    def read_after(
        self,
        cursor: DurableTickCursor | None,
        *,
        durable_through: DurableTickCursor,
        limit: int = 1024,
    ) -> DurableTickBatch:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if cursor is not None and cursor.feed_session_id != durable_through.feed_session_id:
            start = min(
                cursor.ingress_sequence + 1,
                max(1, durable_through.ingress_sequence),
            )
            gap = TickStreamGap(
                feed_session_id=durable_through.feed_session_id,
                start_ingress_sequence=start,
                end_ingress_sequence=max(start, durable_through.ingress_sequence),
                reason="cursor_session_mismatch",
            )
            return DurableTickBatch(
                records=(),
                next_cursor=cursor,
                durable_through=durable_through,
                caught_up=False,
                gap=gap,
            )

        after_sequence = cursor.ingress_sequence if cursor is not None else 0
        if after_sequence > durable_through.ingress_sequence:
            gap = TickStreamGap(
                feed_session_id=durable_through.feed_session_id,
                start_ingress_sequence=durable_through.ingress_sequence + 1,
                end_ingress_sequence=after_sequence,
                reason="cursor_ahead_of_durable_watermark",
            )
            return DurableTickBatch(
                records=(),
                next_cursor=cursor,
                durable_through=durable_through,
                caught_up=False,
                gap=gap,
            )

        if durable_through.ingress_sequence == 0:
            validated_rows: list[Mapping[str, Any]] = []
            gap: TickStreamGap | None = None
        else:
            entries, parse_error = self._read_entries()
            first_control_type = (
                entries[0][1].get(JOURNAL_RECORD_TYPE_FIELD)
                if entries
                else None
            )
            contains_framed_control = any(
                row.get(JOURNAL_RECORD_TYPE_FIELD)
                in {JOURNAL_HEADER_RECORD_TYPE, JOURNAL_BATCH_COMMIT_RECORD_TYPE}
                for _raw, row in entries
            )
            if first_control_type == JOURNAL_HEADER_RECORD_TYPE:
                validated_rows, gap = self._validated_framed_rows(
                    entries,
                    feed_session_id=durable_through.feed_session_id,
                    durable_sequence=durable_through.ingress_sequence,
                    parse_error=parse_error,
                )
            elif contains_framed_control:
                validated_rows = []
                gap = self._gap(
                    durable_through.feed_session_id,
                    1,
                    durable_through.ingress_sequence,
                    "journal_header_missing",
                )
            else:
                validated_rows, gap = self._validated_legacy_rows(
                    entries,
                    feed_session_id=durable_through.feed_session_id,
                    durable_sequence=durable_through.ingress_sequence,
                    parse_error=parse_error,
                )

        records = [
            row
            for row in validated_rows
            if int(row.get("ingress_sequence", 0) or 0) > after_sequence
        ][:limit]

        if records:
            next_cursor = DurableTickCursor(
                durable_through.feed_session_id,
                int(records[-1]["ingress_sequence"]),
            )
        else:
            next_cursor = cursor
        next_sequence = next_cursor.ingress_sequence if next_cursor is not None else 0
        return DurableTickBatch(
            records=tuple(records),
            next_cursor=next_cursor,
            durable_through=durable_through,
            caught_up=bool(
                gap is None and next_sequence >= durable_through.ingress_sequence
            ),
            gap=gap,
        )


def _fsync_parent(path: Path) -> None:
    directory_fd = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def recover_or_isolate_dirty_tail(
    journal_path: Path,
    previous_heartbeat: Mapping[str, Any],
) -> JournalRecoveryResult:
    """Recover the last proven journal commit and isolate every unknown suffix.

    Framed journals use the journal commit frames as the recovery authority, so
    a heartbeat that lagged a completed writer batch cannot roll the cursor
    backward.  Legacy raw-NDJSON journals remain readable, but only the strict
    contiguous prefix acknowledged by their heartbeat is trusted.
    """

    path = Path(journal_path)
    feed_session_id = _clean(previous_heartbeat.get("feed_session_id"))
    heartbeat_durable_sequence = int(
        previous_heartbeat.get(
            "durable_ingress_sequence",
            previous_heartbeat.get("stream_sequence", 0),
        )
        or 0
    )
    heartbeat_last_ingress_sequence = int(
        previous_heartbeat.get(
            "last_ingress_sequence",
            previous_heartbeat.get(
                "stream_sequence",
                heartbeat_durable_sequence,
            ),
        )
        or 0
    )
    heartbeat_gap_end = int(
        previous_heartbeat.get("gap_end_ingress_sequence", 0) or 0
    )

    data = path.read_bytes() if path.exists() else b""
    entries: list[tuple[int, int, bytes, dict[str, Any]]] = []
    offset = 0
    for line in data.splitlines(keepends=True):
        line_start = offset
        line_end = offset + len(line)
        if not line.endswith(b"\n"):
            break
        try:
            row = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            break
        if not isinstance(row, dict):
            break
        entries.append((line_start, line_end, line, row))
        offset = line_end

    observed_max_sequence = 0
    for _start, _end, _raw, row in entries:
        if row.get(JOURNAL_RECORD_TYPE_FIELD) == JOURNAL_BATCH_COMMIT_RECORD_TYPE:
            try:
                observed_max_sequence = max(
                    observed_max_sequence,
                    int(row.get("last_ingress_sequence", 0) or 0),
                )
            except (TypeError, ValueError):
                continue
        elif _clean(row.get("feed_session_id")) == feed_session_id:
            try:
                observed_max_sequence = max(
                    observed_max_sequence,
                    int(row.get("ingress_sequence", 0) or 0),
                )
            except (TypeError, ValueError):
                continue

    first_control_type = (
        entries[0][3].get(JOURNAL_RECORD_TYPE_FIELD)
        if entries
        else None
    )
    contains_framed_control = any(
        row.get(JOURNAL_RECORD_TYPE_FIELD)
        in {JOURNAL_HEADER_RECORD_TYPE, JOURNAL_BATCH_COMMIT_RECORD_TYPE}
        for _start, _end, _raw, row in entries
    )
    framed = first_control_type == JOURNAL_HEADER_RECORD_TYPE
    trusted_end = 0
    recovered_durable_sequence = 0
    suffix_reason = ""

    if framed:
        _header_start, header_end, _header_raw, header = entries[0]
        segment_id = _validated_header_segment_id(
            header,
            feed_session_id=feed_session_id,
        )
        valid_header = bool(segment_id)
        if valid_header:
            trusted_end = header_end
        else:
            suffix_reason = "journal_header_invalid"

        pending_rows: list[dict[str, Any]] = []
        pending_payload = bytearray()
        expected_sequence = 1
        for _start, line_end, raw, row in entries[1:] if valid_header else []:
            control_type = row.get(JOURNAL_RECORD_TYPE_FIELD)
            if control_type == JOURNAL_BATCH_COMMIT_RECORD_TYPE:
                valid_frame = _commit_frame_is_valid(
                    row,
                    pending_rows=pending_rows,
                    pending_payload=bytes(pending_payload),
                    feed_session_id=feed_session_id,
                    segment_id=segment_id,
                    previous_durable_sequence=recovered_durable_sequence,
                )
                if not valid_frame:
                    suffix_reason = "journal_commit_frame_invalid"
                    break
                frame_end = int(row.get("last_ingress_sequence", 0) or 0)
                recovered_durable_sequence = frame_end
                expected_sequence = frame_end + 1
                trusted_end = line_end
                pending_rows.clear()
                pending_payload.clear()
                continue

            if control_type:
                suffix_reason = "journal_unknown_control_record"
                break

            row_feed = _clean(row.get("feed_session_id"))
            try:
                row_sequence = int(row.get("ingress_sequence", 0) or 0)
            except (TypeError, ValueError):
                suffix_reason = "journal_sequence_invalid"
                break
            if row_feed != feed_session_id:
                suffix_reason = "journal_feed_session_mismatch"
                break
            if row_sequence != expected_sequence:
                suffix_reason = "journal_sequence_gap"
                break
            pending_rows.append(row)
            pending_payload.extend(raw)
            expected_sequence += 1

        if not suffix_reason and (pending_rows or trusted_end < len(data)):
            suffix_reason = "journal_uncommitted_suffix"
    elif contains_framed_control:
        suffix_reason = "journal_header_missing"
    else:
        expected_sequence = 1
        for _start, line_end, _raw, row in entries:
            if row.get(JOURNAL_RECORD_TYPE_FIELD):
                suffix_reason = "legacy_journal_unknown_record"
                break
            row_feed = _clean(row.get("feed_session_id"))
            try:
                row_sequence = int(row.get("ingress_sequence", 0) or 0)
            except (TypeError, ValueError):
                suffix_reason = "journal_sequence_invalid"
                break
            if row_feed != feed_session_id:
                suffix_reason = "journal_feed_session_mismatch"
                break
            if row_sequence != expected_sequence:
                suffix_reason = "journal_sequence_gap"
                break
            if row_sequence > heartbeat_durable_sequence:
                suffix_reason = "legacy_journal_uncommitted_suffix"
                break
            recovered_durable_sequence = row_sequence
            trusted_end = line_end
            expected_sequence += 1
        if not suffix_reason and trusted_end < len(data):
            suffix_reason = "legacy_journal_uncommitted_suffix"

    tail = data[trusted_end:]
    isolated_tail_path: Path | None = None
    if tail:
        path.parent.mkdir(parents=True, exist_ok=True)
        isolated_tail_path = path.with_name(
            f"{path.name}.dirty.{time.time_ns()}"
        )
        with isolated_tail_path.open("xb") as handle:
            handle.write(tail)
            handle.flush()
            _durability_barrier(handle.fileno())
        with path.open("r+b") as handle:
            handle.truncate(trusted_end)
            handle.flush()
            _durability_barrier(handle.fileno())
        _fsync_parent(path)
    elif framed and path.exists():
        # A complete marker whose original barrier returned an ambiguous
        # outcome becomes authoritative only after recovery re-establishes a
        # successful durability barrier on the retained journal.
        with path.open("r+b") as handle:
            _durability_barrier(handle.fileno())

    previous_cursor = (
        DurableTickCursor(feed_session_id, recovered_durable_sequence)
        if feed_session_id and recovered_durable_sequence > 0
        else None
    )
    disclosed_gap: TickStreamGap | None = None
    gap_end = max(
        heartbeat_durable_sequence,
        heartbeat_last_ingress_sequence,
        heartbeat_gap_end,
        observed_max_sequence,
    )
    if gap_end > recovered_durable_sequence:
        disclosed_gap = TickStreamGap(
            feed_session_id=feed_session_id or "unknown_prior_feed",
            start_ingress_sequence=recovered_durable_sequence + 1,
            end_ingress_sequence=gap_end,
            reason=(
                suffix_reason
                or "durable_cursor_missing_from_journal"
            ),
        )
    elif tail and not feed_session_id:
        disclosed_gap = TickStreamGap(
            feed_session_id="unknown_prior_feed",
            start_ingress_sequence=1,
            end_ingress_sequence=max(1, observed_max_sequence),
            reason=suffix_reason or "unknown_prior_journal_suffix",
        )
    return JournalRecoveryResult(
        previous_durable_cursor=previous_cursor,
        isolated_tail_path=isolated_tail_path,
        isolated_byte_count=len(tail),
        disclosed_gap=disclosed_gap,
    )
