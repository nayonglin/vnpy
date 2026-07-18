from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from queue import Empty
from typing import Any
from contextlib import contextmanager
import errno
import fcntl
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
    TickIngressEnvelope,
)


MAX_JOURNAL_LINE_BYTES = 4 * 1024 * 1024
MAX_JOURNAL_BATCH_BYTES = 4 * 1024 * 1024
EAGER_FLUSH_BATCH_SIZE = 64


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _durability_barrier(file_descriptor: int) -> None:
    """The single seam for journal durability and fault injection."""

    os.fsync(file_descriptor)


def _fsync_parent(path: Path) -> None:
    directory_fd = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _write_all(handle: Any, payload: bytes) -> None:
    """Write every byte even when a raw file object reports a short write."""

    remaining = memoryview(payload)
    while remaining:
        written = handle.write(remaining)
        if not isinstance(written, int) or written <= 0:
            raise OSError(errno.EIO, "journal write made no forward progress")
        remaining = remaining[written:]


def _strict_json_int(value: Any) -> int | None:
    """Return an exact JSON integer; bool/float/string aliases are invalid."""

    return value if type(value) is int else None


def _validated_framed_tick_row_identity(
    row: Mapping[str, Any],
    *,
    feed_session_id: str,
) -> tuple[int | None, str]:
    """Apply the writer's exact integer identity contract during replay."""

    if _clean(row.get("feed_session_id")) != feed_session_id:
        return None, "journal_feed_session_mismatch"
    values: dict[str, int] = {}
    for field in (
        "ingress_sequence",
        "stream_sequence",
        "symbol_sequence",
        "symbol_stream_sequence",
        "ingress_epoch_ns",
        "ingress_monotonic_ns",
    ):
        value = _strict_json_int(row.get(field))
        if value is None:
            return None, f"journal_tick_identity_invalid:{field}"
        values[field] = value
    if (
        values["ingress_sequence"] <= 0
        or values["symbol_sequence"] <= 0
        or values["ingress_epoch_ns"] < 0
        or values["ingress_monotonic_ns"] < 0
        or values["stream_sequence"] != values["ingress_sequence"]
        or values["symbol_stream_sequence"] != values["symbol_sequence"]
    ):
        return None, "journal_tick_identity_alias_mismatch"
    return values["ingress_sequence"], ""


@contextmanager
def _exclusive_journal_lock(path: Path):
    """Fence a segment writer or recovery mutation with one advisory lock."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f".{path.name}.stage179.lock")
    descriptor = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("journal_segment_lock_contended") from exc
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _validated_header_segment_id(
    header: Mapping[str, Any],
    *,
    feed_session_id: str,
) -> str:
    schema = _strict_json_int(header.get("schema_version"))
    first_sequence = _strict_json_int(header.get("first_ingress_sequence"))
    segment_id = _clean(header.get("segment_id"))
    if not (
        header.get(JOURNAL_RECORD_TYPE_FIELD) == JOURNAL_HEADER_RECORD_TYPE
        and schema == JOURNAL_BATCH_COMMIT_SCHEMA_VERSION
        and _clean(header.get("feed_session_id")) == feed_session_id
        and segment_id == feed_session_id
        and first_sequence == 1
    ):
        return ""
    return segment_id


def _commit_frame_matches(
    frame: Mapping[str, Any],
    *,
    pending_first_sequence: int,
    pending_last_sequence: int,
    pending_row_count: int,
    pending_payload_byte_count: int,
    pending_payload_sha256: str,
    feed_session_id: str,
    segment_id: str,
    previous_durable_sequence: int,
) -> bool:
    frame_schema = _strict_json_int(frame.get("schema_version"))
    frame_previous = _strict_json_int(
        frame.get("previous_durable_ingress_sequence")
    )
    frame_start = _strict_json_int(frame.get("first_ingress_sequence"))
    frame_end = _strict_json_int(frame.get("last_ingress_sequence"))
    frame_count = _strict_json_int(frame.get("row_count"))
    frame_byte_count = _strict_json_int(frame.get("payload_byte_count"))
    return bool(
        pending_row_count > 0
        and frame.get(JOURNAL_RECORD_TYPE_FIELD)
        == JOURNAL_BATCH_COMMIT_RECORD_TYPE
        and frame_schema == JOURNAL_BATCH_COMMIT_SCHEMA_VERSION
        and _clean(frame.get("feed_session_id")) == feed_session_id
        and _clean(frame.get("segment_id")) == segment_id
        and frame_previous == previous_durable_sequence
        and frame_start == previous_durable_sequence + 1
        and frame_start == pending_first_sequence
        and frame_end == pending_last_sequence
        and frame_count == pending_row_count
        and frame_byte_count == pending_payload_byte_count
        and _clean(frame.get("payload_sha256")) == pending_payload_sha256
    )


def _parse_record_line(raw_line: bytes) -> tuple[dict[str, Any] | None, str]:
    if not raw_line:
        return None, "journal_unexpected_eof"
    if len(raw_line) > MAX_JOURNAL_LINE_BYTES:
        return None, "journal_record_too_large"
    if not raw_line.endswith(b"\n"):
        return None, "journal_partial_line_before_durable_watermark"
    try:
        row = json.loads(raw_line)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError, RecursionError):
        return None, "journal_invalid_json_before_durable_watermark"
    if not isinstance(row, dict):
        return None, "journal_invalid_record_before_durable_watermark"
    return row, ""


class AsyncTickJournalWriter:
    """Single owner of the append fd and the fsync durability transition."""

    def __init__(self, pipeline: Any) -> None:
        self.pipeline = pipeline
        self._stop_requested = threading.Event()
        self._stopped = threading.Event()
        self._header_durable = threading.Event()
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

    def wait_header_durable(self, timeout_seconds: float) -> bool:
        return self._header_durable.wait(max(0.0, float(timeout_seconds)))

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
            try:
                item = queue.get_nowait()
            except Empty:
                if (
                    self._stop_requested.is_set()
                    or len(batch)
                    >= min(EAGER_FLUSH_BATCH_SIZE, self.pipeline.writer_batch_size)
                ):
                    break
                timeout = max(0.0, deadline - time.monotonic())
                if timeout <= 0:
                    break
                try:
                    item = queue.get(timeout=timeout)
                except Empty:
                    break
            batch.append(item)
        return batch

    @staticmethod
    def _serialized_batch(batch: list[TickIngressEnvelope]) -> bytes:
        payload = bytearray()
        for envelope in batch:
            raw_line = (
                json.dumps(
                dict(envelope.tick_row),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
                + "\n"
            ).encode("utf-8")
            if len(raw_line) > MAX_JOURNAL_LINE_BYTES:
                raise ValueError("journal_record_too_large")
            if len(payload) + len(raw_line) > MAX_JOURNAL_BATCH_BYTES:
                raise ValueError("journal_batch_payload_limit_exceeded")
            payload.extend(raw_line)
        return bytes(payload)

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
        raw_line = (
            json.dumps(
                frame,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        if len(raw_line) > MAX_JOURNAL_LINE_BYTES:
            raise ValueError("journal_control_record_too_large")
        return raw_line

    def _serialized_header(self) -> bytes:
        raw_line = (
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
        if len(raw_line) > MAX_JOURNAL_LINE_BYTES:
            raise ValueError("journal_control_record_too_large")
        return raw_line

    def run(self) -> None:
        path = self.pipeline.journal_segment_path
        try:
            with _exclusive_journal_lock(path):
                descriptor = os.open(
                    str(path),
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND,
                    0o600,
                )
                with os.fdopen(descriptor, "wb", buffering=0) as handle:
                    _write_all(handle, self._serialized_header())
                    _durability_barrier(handle.fileno())
                    _fsync_parent(path)
                    self._header_durable.set()
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
                        self.pipeline._commit_durable_batch(
                            batch,
                            journal_byte_offset=handle.tell(),
                        )
                        for _item in batch:
                            self.pipeline._ingress_queue.task_done()
        except Exception as exc:
            self.pipeline._latch_writer_error(exc)
        finally:
            self._stopped.set()


def __getattr__(name: str) -> Any:
    """Keep the pre-split public imports without creating import cycles."""

    if name == "TickStreamJournalReader":
        from qmt_roll_official_live_tick_reader import TickStreamJournalReader

        return TickStreamJournalReader
    if name == "recover_or_isolate_dirty_tail":
        from qmt_roll_official_live_tick_recovery import (
            recover_or_isolate_dirty_tail,
        )

        return recover_or_isolate_dirty_tail
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
