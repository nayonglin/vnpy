from __future__ import annotations

from datetime import datetime
from functools import wraps
from itertools import count
from pathlib import Path
from queue import Full, Queue
from types import MappingProxyType
from typing import Any, Callable, Mapping
import threading
import time
from collections import deque

from qmt_roll_official_live_time import Clock, utc_iso_from_epoch_ns
from qmt_roll_official_live_tick_journal import (
    AsyncTickJournalWriter,
    _durability_barrier,
    _fsync_parent,
)
from qmt_roll_official_live_tick_reader import TickStreamJournalReader
from qmt_roll_official_live_tick_recovery import (
    acknowledge_committed_recovery_manifest,
    acknowledge_recovery_manifest,
    recover_or_isolate_dirty_tail,
)
from qmt_roll_official_live_tick_types import (
    DEFAULT_INGRESS_QUEUE_CAPACITY,
    DEFAULT_SHUTDOWN_DRAIN_SECONDS,
    DEFAULT_WRITER_BATCH_SIZE,
    DEFAULT_WRITER_FLUSH_SECONDS,
    JOURNAL_BATCH_COMMIT_RECORD_TYPE,
    JOURNAL_BATCH_COMMIT_SCHEMA_VERSION,
    JOURNAL_FORMAT_FRAMED_V1,
    JOURNAL_FORMAT_LEGACY_V0,
    JOURNAL_HEADER_RECORD_TYPE,
    JOURNAL_RECORD_TYPE_FIELD,
    JOURNAL_SCHEMA_FRAMED_V1,
    JOURNAL_SCHEMA_LEGACY_V0,
    MAX_FEED_SESSION_ID_BYTES,
    TICK_INGRESS_ENVELOPE_ATTR,
    DurableTickBatch,
    DurableTickCursor,
    DurableTickSnapshot,
    JournalRecoveryResult,
    ShutdownReport,
    SymbolDurableWatermark,
    TickHandlerObservation,
    TickIngressEnvelope,
    TickIngressSnapshot,
    TickStreamFault,
    TickStreamGap,
)


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _exchange_value(tick: Any) -> str:
    exchange = getattr(tick, "exchange", "")
    return _clean(getattr(exchange, "value", exchange))


def _exchange_datetime(tick: Any) -> str:
    value = getattr(tick, "datetime", None)
    if isinstance(value, datetime):
        return value.isoformat(timespec="microseconds")
    return _clean(value)


def _trace_id(feed_session_id: str, ingress_sequence: int) -> str:
    return f"stage179-tick/{feed_session_id}/{int(ingress_sequence)}"


def _immutable_number(tick: Any, field: str) -> int | float:
    value = getattr(tick, field, 0.0)
    if isinstance(value, bool):
        raise TypeError(f"{field} must be an immutable number, got bool")
    if isinstance(value, float):
        return float.__float__(value)
    if isinstance(value, int):
        return int(value)
    raise TypeError(
        f"{field} must be an immutable int/float, got {type(value).__name__}"
    )


def _immutable_tick_row(
    tick: Any,
    *,
    feed_session_id: str,
    ingress_sequence: int,
    symbol_sequence: int,
    received_at_utc: str,
    ingress_epoch_ns: int,
    ingress_monotonic_ns: int,
    trace_id: str,
) -> Mapping[str, Any]:
    row: dict[str, Any] = {
        "feed_session_id": feed_session_id,
        "ingress_sequence": int(ingress_sequence),
        "symbol_sequence": int(symbol_sequence),
        "received_at_utc": received_at_utc,
        "ingress_epoch_ns": int(ingress_epoch_ns),
        "ingress_monotonic_ns": int(ingress_monotonic_ns),
        "trace_id": trace_id,
        # Compatibility aliases consumed by the current Stage608/904 chain.
        "stream_sequence": int(ingress_sequence),
        "symbol_stream_sequence": int(symbol_sequence),
        "received_at": received_at_utc,
        "exchange_datetime": _exchange_datetime(tick),
        "vt_symbol": _clean(getattr(tick, "vt_symbol", "")),
        "symbol": _clean(getattr(tick, "symbol", "")),
        "exchange": _exchange_value(tick),
        "last_price": _immutable_number(tick, "last_price"),
        "bid_price_1": _immutable_number(tick, "bid_price_1"),
        "ask_price_1": _immutable_number(tick, "ask_price_1"),
        "bid_volume_1": _immutable_number(tick, "bid_volume_1"),
        "ask_volume_1": _immutable_number(tick, "ask_volume_1"),
        "limit_up": _immutable_number(tick, "limit_up"),
        "limit_down": _immutable_number(tick, "limit_down"),
    }
    return MappingProxyType(row)


class TickStreamPipeline:
    """Bounded gateway ingress with one asynchronous durable journal owner."""

    def __init__(
        self,
        *,
        feed_session_id: str,
        journal_segment_path: Path,
        clock: Clock,
        queue_capacity: int = DEFAULT_INGRESS_QUEUE_CAPACITY,
        max_buffer_ticks: int,
        writer_batch_size: int = DEFAULT_WRITER_BATCH_SIZE,
        writer_flush_seconds: float = DEFAULT_WRITER_FLUSH_SECONDS,
        trace_sink: Any | None = None,
    ) -> None:
        normalized_feed_session_id = _clean(feed_session_id)
        if not normalized_feed_session_id:
            raise ValueError("feed_session_id must not be empty")
        try:
            feed_session_id_bytes = normalized_feed_session_id.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("feed_session_id must be valid UTF-8") from exc
        if len(feed_session_id_bytes) > MAX_FEED_SESSION_ID_BYTES:
            raise ValueError(
                "feed_session_id is too long: "
                f"{len(feed_session_id_bytes)} > {MAX_FEED_SESSION_ID_BYTES} bytes"
            )
        if queue_capacity <= 0:
            raise ValueError("queue_capacity must be positive")
        if max_buffer_ticks <= 0:
            raise ValueError("max_buffer_ticks must be positive")
        if writer_batch_size <= 0:
            raise ValueError("writer_batch_size must be positive")
        if writer_batch_size > DEFAULT_WRITER_BATCH_SIZE:
            raise ValueError(
                f"writer_batch_size must be <= {DEFAULT_WRITER_BATCH_SIZE}"
            )
        if writer_flush_seconds <= 0:
            raise ValueError("writer_flush_seconds must be positive")

        self.feed_session_id = normalized_feed_session_id
        self.journal_segment_path = Path(journal_segment_path)
        self.clock = clock
        self.queue_capacity = int(queue_capacity)
        self.max_buffer_ticks = int(max_buffer_ticks)
        self.writer_batch_size = int(writer_batch_size)
        self.writer_flush_seconds = float(writer_flush_seconds)
        self.trace_sink = trace_sink

        self._ingress_queue: Queue[TickIngressEnvelope] = Queue(
            maxsize=self.queue_capacity
        )
        self._ingress_sequence = count(1)
        self._symbol_sequences: dict[str, int] = {}
        self._producer_thread_id: int | None = None
        self._last_ingress_sequence = 0
        self._dropped_tick_count = 0
        self._gap: TickStreamGap | None = None
        self._fault: TickStreamFault | None = None
        self._accepting = True
        self._durable_condition = threading.Condition()
        self._durable_ingress_sequence = 0
        self._durable_journal_byte_offset = 0
        self._durable_rows: deque[Mapping[str, Any]] = deque()
        self._latest_by_symbol: dict[str, Mapping[str, Any]] = {}
        self._evicted_through_by_symbol: dict[str, int] = {}
        self._symbol_watermarks: dict[str, SymbolDurableWatermark] = {}
        self._writer_fault: TickStreamFault | None = None
        self._writer = AsyncTickJournalWriter(self)

    def _extend_gap(self, ingress_sequence: int, *, reason: str) -> None:
        sequence = int(ingress_sequence)
        if self._gap is None:
            self._gap = TickStreamGap(
                feed_session_id=self.feed_session_id,
                start_ingress_sequence=sequence,
                end_ingress_sequence=sequence,
                reason=reason,
            )
        else:
            self._gap = TickStreamGap(
                feed_session_id=self._gap.feed_session_id,
                start_ingress_sequence=self._gap.start_ingress_sequence,
                end_ingress_sequence=sequence,
                reason=self._gap.reason,
            )
        self._accepting = False

    def _latch_fault(
        self,
        *,
        kind: str,
        detail: str,
        ingress_sequence: int,
    ) -> None:
        if self._fault is None:
            try:
                occurred_epoch_ns = int(self.clock.epoch_ns())
            except Exception:
                occurred_epoch_ns = 0
            self._fault = TickStreamFault(
                kind=kind,
                detail=detail,
                occurred_epoch_ns=occurred_epoch_ns,
            )
        self._extend_gap(ingress_sequence, reason=kind)

    def _merge_suffix_gap(
        self,
        *,
        start_ingress_sequence: int,
        end_ingress_sequence: int,
        reason: str,
    ) -> None:
        self._accepting = False
        start = int(start_ingress_sequence)
        end = max(start, int(end_ingress_sequence))
        if self._gap is not None:
            start = min(start, self._gap.start_ingress_sequence)
            end = max(end, self._gap.end_ingress_sequence)
            reason = self._gap.reason
        self._gap = TickStreamGap(
            feed_session_id=self.feed_session_id,
            start_ingress_sequence=start,
            end_ingress_sequence=end,
            reason=reason,
        )

    def _effective_gap(self) -> TickStreamGap | None:
        """Return a gap whose suffix covers every observed ingress identity.

        The gateway callback is deliberately lock-free.  If a writer fault
        races a callback that already allocated a sequence, the stored gap
        can momentarily lag ``_last_ingress_sequence``.  Publishing extends
        that already-latched suffix rather than ever certifying the raced tick.
        """

        gap = self._gap
        if gap is None:
            return None
        end = max(gap.end_ingress_sequence, self._last_ingress_sequence)
        if end == gap.end_ingress_sequence:
            return gap
        return TickStreamGap(
            feed_session_id=gap.feed_session_id,
            start_ingress_sequence=gap.start_ingress_sequence,
            end_ingress_sequence=end,
            reason=gap.reason,
        )

    def _latch_writer_error(self, exc: Exception) -> None:
        self._accepting = False
        try:
            detail = f"{type(exc).__name__}:{exc}"
        except Exception:
            detail = type(exc).__name__
        try:
            occurred_epoch_ns = int(self.clock.epoch_ns())
        except Exception:
            occurred_epoch_ns = 0
        fault = TickStreamFault(
            kind="journal_write_error",
            detail=detail,
            occurred_epoch_ns=occurred_epoch_ns,
        )
        with self._durable_condition:
            self._writer_fault = self._writer_fault or fault
            durable_sequence = self._durable_ingress_sequence
            effective_fault = self._writer_fault
            self._durable_condition.notify_all()
        self._fault = self._fault or effective_fault
        if durable_sequence < self._last_ingress_sequence:
            self._merge_suffix_gap(
                start_ingress_sequence=durable_sequence + 1,
                end_ingress_sequence=self._last_ingress_sequence,
                reason=effective_fault.kind,
            )

    def _rebuild_symbol_watermarks(self) -> None:
        first_buffered: dict[str, int] = {}
        for row in self._durable_rows:
            vt_symbol = _clean(row.get("vt_symbol"))
            if vt_symbol and vt_symbol not in first_buffered:
                first_buffered[vt_symbol] = int(row.get("symbol_sequence", 0) or 0)
        symbols = (
            set(self._latest_by_symbol)
            | set(self._evicted_through_by_symbol)
            | set(first_buffered)
        )
        rebuilt: dict[str, SymbolDurableWatermark] = {}
        for vt_symbol in symbols:
            latest = self._latest_by_symbol.get(vt_symbol, {})
            durable_symbol_sequence = int(
                latest.get(
                    "symbol_sequence",
                    latest.get("symbol_stream_sequence", 0),
                )
                or 0
            )
            rebuilt[vt_symbol] = SymbolDurableWatermark(
                received_at=_clean(latest.get("received_at")),
                stream_sequence=int(latest.get("stream_sequence", 0) or 0),
                symbol_stream_sequence=durable_symbol_sequence,
                durable_symbol_sequence=durable_symbol_sequence,
                first_buffered_symbol_sequence=int(first_buffered.get(vt_symbol, 0)),
                evicted_through_symbol_sequence=int(
                    self._evicted_through_by_symbol.get(vt_symbol, 0)
                ),
            )
        self._symbol_watermarks = rebuilt

    def _validate_durable_batch_locked(
        self,
        batch: list[TickIngressEnvelope],
    ) -> None:
        if self._writer_fault is not None:
            raise RuntimeError(
                "durable_commit_revoked_after_writer_or_shutdown_fault"
            )
        expected = self._durable_ingress_sequence + 1
        for envelope in batch:
            if envelope.feed_session_id != self.feed_session_id:
                raise RuntimeError("writer_batch_feed_session_mismatch")
            for field in (
                "ingress_sequence",
                "symbol_sequence",
                "ingress_epoch_ns",
                "ingress_monotonic_ns",
            ):
                value = getattr(envelope, field)
                if type(value) is not int:
                    raise RuntimeError(
                        "writer_envelope_integer_identity_invalid:"
                        f"field={field};actual_type={type(value).__name__}"
                    )
            if envelope.ingress_sequence != expected:
                raise RuntimeError(
                    "writer_batch_sequence_gap:"
                    f"expected={expected};actual={envelope.ingress_sequence}"
                )
            expected_trace_id = _trace_id(
                envelope.feed_session_id,
                envelope.ingress_sequence,
            )
            expected_identity = {
                "feed_session_id": envelope.feed_session_id,
                "ingress_sequence": envelope.ingress_sequence,
                "stream_sequence": envelope.ingress_sequence,
                "symbol_sequence": envelope.symbol_sequence,
                "symbol_stream_sequence": envelope.symbol_sequence,
                "received_at_utc": envelope.received_at_utc,
                "received_at": envelope.received_at_utc,
                "ingress_epoch_ns": envelope.ingress_epoch_ns,
                "ingress_monotonic_ns": envelope.ingress_monotonic_ns,
                "trace_id": envelope.trace_id,
            }
            if envelope.trace_id != expected_trace_id:
                raise RuntimeError("writer_envelope_trace_identity_mismatch")
            for field, expected_value in expected_identity.items():
                actual_value = envelope.tick_row.get(field)
                if (
                    type(actual_value) is not type(expected_value)
                    or actual_value != expected_value
                ):
                    raise RuntimeError(
                        "writer_tick_row_identity_mismatch:"
                        f"field={field};expected={expected_value!r};"
                        f"actual={actual_value!r}"
                    )
            expected += 1

    def _validate_batch_for_journal(
        self,
        batch: list[TickIngressEnvelope],
    ) -> None:
        if not batch:
            raise RuntimeError("writer_batch_must_not_be_empty")
        with self._durable_condition:
            self._validate_durable_batch_locked(batch)

    def _commit_durable_batch(
        self,
        batch: list[TickIngressEnvelope],
        *,
        journal_byte_offset: int,
    ) -> None:
        if not batch:
            return
        with self._durable_condition:
            self._validate_durable_batch_locked(batch)
            for envelope in batch:
                while len(self._durable_rows) >= self.max_buffer_ticks:
                    evicted = self._durable_rows.popleft()
                    evicted_symbol = _clean(evicted.get("vt_symbol"))
                    if evicted_symbol:
                        evicted_sequence = int(
                            evicted.get(
                                "symbol_sequence",
                                evicted.get("symbol_stream_sequence", 0),
                            )
                            or 0
                        )
                        self._evicted_through_by_symbol[evicted_symbol] = max(
                            self._evicted_through_by_symbol.get(evicted_symbol, 0),
                            evicted_sequence,
                        )
                row = envelope.tick_row
                self._durable_rows.append(row)
                vt_symbol = _clean(row.get("vt_symbol"))
                if vt_symbol:
                    self._latest_by_symbol[vt_symbol] = row
            self._durable_ingress_sequence = batch[-1].ingress_sequence
            self._durable_journal_byte_offset = int(journal_byte_offset)
            self._rebuild_symbol_watermarks()
            self._durable_condition.notify_all()

    def capture_ingress(self, tick: Any) -> TickIngressEnvelope:
        """Copy and enqueue one tick without file I/O or a blocking wait."""

        ingress_sequence = next(self._ingress_sequence)
        self._last_ingress_sequence = ingress_sequence
        vt_symbol = _clean(getattr(tick, "vt_symbol", ""))
        symbol_sequence = self._symbol_sequences.get(vt_symbol, 0) + 1
        self._symbol_sequences[vt_symbol] = symbol_sequence

        ingress_epoch_ns = int(self.clock.epoch_ns())
        received_at_utc = utc_iso_from_epoch_ns(ingress_epoch_ns)
        ingress_monotonic_ns = int(self.clock.monotonic_ns())
        trace_id = _trace_id(self.feed_session_id, ingress_sequence)
        envelope = TickIngressEnvelope(
            feed_session_id=self.feed_session_id,
            ingress_sequence=ingress_sequence,
            symbol_sequence=symbol_sequence,
            received_at_utc=received_at_utc,
            ingress_epoch_ns=ingress_epoch_ns,
            ingress_monotonic_ns=ingress_monotonic_ns,
            trace_id=trace_id,
            tick_row=_immutable_tick_row(
                tick,
                feed_session_id=self.feed_session_id,
                ingress_sequence=ingress_sequence,
                symbol_sequence=symbol_sequence,
                received_at_utc=received_at_utc,
                ingress_epoch_ns=ingress_epoch_ns,
                ingress_monotonic_ns=ingress_monotonic_ns,
                trace_id=trace_id,
            ),
        )
        setattr(tick, TICK_INGRESS_ENVELOPE_ATTR, envelope)

        producer_thread_id = threading.get_ident()
        if self._producer_thread_id is None:
            self._producer_thread_id = producer_thread_id
        elif self._producer_thread_id != producer_thread_id:
            self._dropped_tick_count += 1
            self._latch_fault(
                kind="ingress_thread_violation",
                detail=(
                    f"expected_thread={self._producer_thread_id};"
                    f"actual_thread={producer_thread_id}"
                ),
                ingress_sequence=ingress_sequence,
            )
            return envelope

        if not self._accepting:
            self._dropped_tick_count += 1
            self._extend_gap(ingress_sequence, reason="ingress_not_accepting")
            return envelope

        try:
            self._ingress_queue.put_nowait(envelope)
        except Full:
            self._dropped_tick_count += 1
            self._extend_gap(ingress_sequence, reason="ingress_queue_full")
        return envelope

    def observe_handler(self, tick: Any) -> TickHandlerObservation | None:
        """Record handler time separately; never rewrite authoritative tick time."""

        envelope = getattr(tick, TICK_INGRESS_ENVELOPE_ATTR, None)
        if not isinstance(envelope, TickIngressEnvelope):
            return None
        return TickHandlerObservation(
            feed_session_id=envelope.feed_session_id,
            ingress_sequence=envelope.ingress_sequence,
            handler_received_monotonic_ns=int(self.clock.monotonic_ns()),
        )

    def start(self) -> None:
        self._writer.start()

    def _writer_commit_revoked(self) -> bool:
        with self._durable_condition:
            return self._writer_fault is not None

    def wait_until_durable(self, ingress_sequence: int, *, timeout_seconds: float) -> bool:
        target = int(ingress_sequence)
        deadline = time.monotonic() + max(0.0, float(timeout_seconds))
        with self._durable_condition:
            while (
                self._durable_ingress_sequence < target
                and self._writer_fault is None
            ):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._durable_condition.wait(remaining)
            return self._durable_ingress_sequence >= target

    def wait_until_writer_stops(self, *, timeout_seconds: float) -> bool:
        return self._writer.wait_stopped(timeout_seconds)

    def wait_until_journal_ready(self, *, timeout_seconds: float) -> bool:
        return self._writer.wait_header_durable(timeout_seconds)

    def durable_snapshot(self) -> DurableTickSnapshot:
        with self._durable_condition:
            rows = tuple(self._durable_rows)
            latest_by_symbol = MappingProxyType(dict(self._latest_by_symbol))
            symbol_watermarks = MappingProxyType(dict(self._symbol_watermarks))
            durable_ingress_sequence = self._durable_ingress_sequence
            durable_journal_byte_offset = self._durable_journal_byte_offset
            writer_fault = self._writer_fault
        writer_alive = self._writer.is_alive
        return DurableTickSnapshot(
            feed_session_id=self.feed_session_id,
            last_ingress_sequence=self._last_ingress_sequence,
            durable_ingress_sequence=durable_ingress_sequence,
            rows=rows,
            latest_by_symbol=latest_by_symbol,
            symbol_watermarks=symbol_watermarks,
            queue_depth=self._ingress_queue.qsize(),
            queue_capacity=self.queue_capacity,
            dropped_tick_count=self._dropped_tick_count,
            gap=self._effective_gap(),
            writer_fault=writer_fault,
            writer_alive=writer_alive,
            accepting=self._accepting,
            stream_ready=bool(
                self._accepting
                and self._gap is None
                and self._fault is None
                and writer_fault is None
                and writer_alive
            ),
            journal_segment_path=self.journal_segment_path,
            durable_journal_byte_offset=durable_journal_byte_offset,
            journal_schema=JOURNAL_SCHEMA_FRAMED_V1,
        )

    def shutdown(
        self,
        timeout_seconds: float = DEFAULT_SHUTDOWN_DRAIN_SECONDS,
    ) -> ShutdownReport:
        self.stop_accepting()
        self._writer.request_stop()
        self._writer.start()
        joined = self._writer.join(timeout_seconds)
        remaining = self._ingress_queue.qsize()
        timeout_fault: TickStreamFault | None = None
        with self._durable_condition:
            durable_sequence = self._durable_ingress_sequence
            writer_fault = self._writer_fault
            uncommitted_count = max(
                0,
                self._last_ingress_sequence - durable_sequence,
            )
            unexplained_mismatch = bool(
                uncommitted_count > 0 and self._gap is None
            )
            if (not joined or unexplained_mismatch) and writer_fault is None:
                reason = (
                    "shutdown_drain_timeout"
                    if not joined
                    else "shutdown_durable_mismatch"
                )
                timeout_fault = TickStreamFault(
                    kind=reason,
                    detail=(
                        f"joined={int(joined)};remaining={remaining};"
                        f"uncommitted={uncommitted_count};"
                        f"durable={durable_sequence};last={self._last_ingress_sequence}"
                    ),
                    occurred_epoch_ns=0,
                )
                # Revocation and the reported cursor are one condition-guarded
                # transition.  A writer that reaches commit after this point
                # must observe the fault and cannot advance the cursor.
                self._writer_fault = timeout_fault
                writer_fault = timeout_fault
                self._durable_condition.notify_all()

        if timeout_fault is not None:
            self._fault = self._fault or timeout_fault
            if uncommitted_count > 0:
                self._merge_suffix_gap(
                    start_ingress_sequence=durable_sequence + 1,
                    end_ingress_sequence=self._last_ingress_sequence,
                    reason=timeout_fault.kind,
                )

        drained = bool(
            joined
            and uncommitted_count == 0
            and writer_fault is None
        )
        gap = self._effective_gap()
        durable_through = (
            DurableTickCursor(
                self.feed_session_id,
                durable_sequence,
                journal_byte_offset=self._durable_journal_byte_offset,
                journal_schema=JOURNAL_SCHEMA_FRAMED_V1,
            )
            if durable_sequence > 0
            else None
        )
        return ShutdownReport(
            drained=drained,
            durable_through=durable_through,
            remaining_queue_depth=remaining,
            uncommitted_tick_count=uncommitted_count,
            gap=gap,
            writer_fault=writer_fault,
        )

    def take_ingress_nowait(self) -> TickIngressEnvelope:
        """Return one queued envelope; the async writer becomes the sole caller."""

        return self._ingress_queue.get_nowait()

    def stop_accepting(self) -> None:
        self._accepting = False

    def snapshot(self) -> TickIngressSnapshot:
        return TickIngressSnapshot(
            feed_session_id=self.feed_session_id,
            last_ingress_sequence=self._last_ingress_sequence,
            queue_depth=self._ingress_queue.qsize(),
            queue_capacity=self.queue_capacity,
            dropped_tick_count=self._dropped_tick_count,
            gap=self._effective_gap(),
            fault=self._fault,
            accepting=self._accepting,
            stream_ready=(
                self._accepting and self._gap is None and self._fault is None
            ),
            journal_segment_path=self.journal_segment_path,
        )

    def latch_capture_exception(self, exc: Exception) -> None:
        sequence = max(1, self._last_ingress_sequence)
        try:
            message = str(exc)
        except Exception:
            message = "unprintable"
        self._latch_fault(
            kind="ingress_capture_exception",
            detail=f"{type(exc).__name__}:{message}",
            ingress_sequence=sequence,
        )
        self._dropped_tick_count += 1

    def _force_fail_closed_after_latch_error(self, exc: Exception) -> None:
        """Last-resort state transition that does not call the injected clock."""

        self._dropped_tick_count += 1
        sequence = max(1, self._last_ingress_sequence)
        self._last_ingress_sequence = sequence
        self._accepting = False
        if self._fault is None:
            self._fault = TickStreamFault(
                kind="ingress_fault_latch_exception",
                detail=type(exc).__name__,
                occurred_epoch_ns=0,
            )
        self._extend_gap(sequence, reason="ingress_fault_latch_exception")


def install_gateway_tick_ingress(
    gateway: Any,
    pipeline: TickStreamPipeline,
) -> Callable[[], None]:
    """Stamp before EventEngine enqueue while preserving gateway forwarding."""

    original_on_tick = gateway.on_tick
    capture_enabled = threading.Event()
    capture_enabled.set()
    # The supported CPython 3.11 runtime serializes set add/discard under the
    # GIL.  Unlike a Condition, these hot-path operations never wait on a
    # user-space mutex.  The second Event check closes the clear-vs-add race.
    active_capture_tokens: set[object] = set()
    restore_complete = False

    @wraps(original_on_tick)
    def wrapped_on_tick(tick: Any, *args: Any, **kwargs: Any) -> Any:
        capture_token: object | None = None
        try:
            try:
                if capture_enabled.is_set():
                    capture_token = object()
                    active_capture_tokens.add(capture_token)
                    if not capture_enabled.is_set():
                        active_capture_tokens.discard(capture_token)
                        capture_token = None
                if capture_token is not None:
                    pipeline.capture_ingress(tick)
            except Exception as exc:
                try:
                    pipeline.latch_capture_exception(exc)
                except Exception as latch_exc:
                    try:
                        pipeline._force_fail_closed_after_latch_error(latch_exc)
                    except Exception:
                        pass
            return original_on_tick(tick, *args, **kwargs)
        finally:
            if capture_token is not None:
                active_capture_tokens.discard(capture_token)

    gateway.on_tick = wrapped_on_tick

    def restore() -> None:
        """Fence new captures and wait for every leased capture to finish."""

        nonlocal restore_complete
        deadline = time.monotonic() + DEFAULT_SHUTDOWN_DRAIN_SECONDS
        if restore_complete:
            return
        capture_enabled.clear()
        assignment_error: Exception | None = None
        try:
            if gateway.on_tick is wrapped_on_tick:
                gateway.on_tick = original_on_tick
        except Exception as exc:
            assignment_error = exc
        while active_capture_tokens:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    "gateway ingress capture fence timed out;"
                    f" active_captures={len(active_capture_tokens)}"
                )
            time.sleep(min(0.001, remaining))
        if assignment_error is not None:
            raise assignment_error
        restore_complete = True

    return restore
