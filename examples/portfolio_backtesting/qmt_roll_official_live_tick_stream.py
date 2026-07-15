from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from itertools import count
from pathlib import Path
from queue import Empty, Full, Queue
from types import MappingProxyType
from typing import Any, Callable, Mapping
import json
import os
import threading
import time
from collections import deque

from qmt_roll_official_live_time import Clock, utc_iso_from_epoch_ns


DEFAULT_INGRESS_QUEUE_CAPACITY = 8192
DEFAULT_WRITER_BATCH_SIZE = 256
DEFAULT_WRITER_FLUSH_SECONDS = 0.050
DEFAULT_SHUTDOWN_DRAIN_SECONDS = 2.0

TICK_INGRESS_ENVELOPE_ATTR = "_stage179_tick_ingress_envelope"


@dataclass(frozen=True, slots=True)
class DurableTickCursor:
    feed_session_id: str
    ingress_sequence: int


@dataclass(frozen=True, slots=True)
class TickIngressEnvelope:
    feed_session_id: str
    ingress_sequence: int
    symbol_sequence: int
    received_at_utc: str
    ingress_epoch_ns: int
    ingress_monotonic_ns: int
    trace_id: str
    tick_row: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class TickHandlerObservation:
    feed_session_id: str
    ingress_sequence: int
    handler_received_monotonic_ns: int


@dataclass(frozen=True, slots=True)
class TickStreamGap:
    feed_session_id: str
    start_ingress_sequence: int
    end_ingress_sequence: int
    reason: str


@dataclass(frozen=True, slots=True)
class TickStreamFault:
    kind: str
    detail: str
    occurred_epoch_ns: int


@dataclass(frozen=True, slots=True)
class TickIngressSnapshot:
    feed_session_id: str
    last_ingress_sequence: int
    queue_depth: int
    queue_capacity: int
    dropped_tick_count: int
    gap: TickStreamGap | None
    fault: TickStreamFault | None
    accepting: bool
    stream_ready: bool
    journal_segment_path: Path


@dataclass(frozen=True, slots=True)
class SymbolDurableWatermark:
    received_at: str
    stream_sequence: int
    symbol_stream_sequence: int
    durable_symbol_sequence: int
    first_buffered_symbol_sequence: int
    evicted_through_symbol_sequence: int


@dataclass(frozen=True, slots=True)
class DurableTickSnapshot:
    feed_session_id: str
    last_ingress_sequence: int
    durable_ingress_sequence: int
    rows: tuple[Mapping[str, Any], ...]
    latest_by_symbol: Mapping[str, Mapping[str, Any]]
    symbol_watermarks: Mapping[str, SymbolDurableWatermark]
    queue_depth: int
    queue_capacity: int
    dropped_tick_count: int
    gap: TickStreamGap | None
    writer_fault: TickStreamFault | None
    writer_alive: bool
    accepting: bool
    stream_ready: bool
    journal_segment_path: Path


@dataclass(frozen=True, slots=True)
class DurableTickBatch:
    records: tuple[Mapping[str, Any], ...]
    next_cursor: DurableTickCursor | None
    durable_through: DurableTickCursor
    caught_up: bool
    gap: TickStreamGap | None


@dataclass(frozen=True, slots=True)
class ShutdownReport:
    drained: bool
    durable_through: DurableTickCursor | None
    remaining_queue_depth: int
    gap: TickStreamGap | None
    writer_fault: TickStreamFault | None


@dataclass(frozen=True, slots=True)
class JournalRecoveryResult:
    previous_durable_cursor: DurableTickCursor | None
    isolated_tail_path: Path | None
    isolated_byte_count: int
    disclosed_gap: TickStreamGap | None


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


class AsyncTickJournalWriter:
    """Single owner of the append fd and the fsync durability transition."""

    def __init__(self, pipeline: "TickStreamPipeline") -> None:
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
            first = queue.get(timeout=self.pipeline.writer_flush_seconds)
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
    def _serialized_batch(batch: list[TickIngressEnvelope]) -> str:
        return "".join(
            json.dumps(
                dict(envelope.tick_row),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
            for envelope in batch
        )

    def run(self) -> None:
        path = self.pipeline.journal_segment_path
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("a", encoding="utf-8", newline="") as handle:
                while True:
                    if self._stop_requested.is_set() and self.pipeline._ingress_queue.empty():
                        break
                    batch = self._next_batch()
                    if not batch:
                        continue
                    try:
                        handle.write(self._serialized_batch(batch))
                        handle.flush()
                        os.fsync(handle.fileno())
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
        if not _clean(feed_session_id):
            raise ValueError("feed_session_id must not be empty")
        if queue_capacity <= 0:
            raise ValueError("queue_capacity must be positive")
        if max_buffer_ticks <= 0:
            raise ValueError("max_buffer_ticks must be positive")
        if writer_batch_size <= 0:
            raise ValueError("writer_batch_size must be positive")
        if writer_flush_seconds <= 0:
            raise ValueError("writer_flush_seconds must be positive")

        self.feed_session_id = _clean(feed_session_id)
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
        self._accepting = False

    def _latch_writer_error(self, exc: Exception) -> None:
        with self._durable_condition:
            start = self._durable_ingress_sequence + 1
        end = max(start, self._last_ingress_sequence)
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
        self._fault = self._fault or fault
        self._merge_suffix_gap(
            start_ingress_sequence=start,
            end_ingress_sequence=end,
            reason=fault.kind,
        )
        with self._durable_condition:
            self._writer_fault = self._writer_fault or fault
            self._durable_condition.notify_all()

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

    def _commit_durable_batch(self, batch: list[TickIngressEnvelope]) -> None:
        if not batch:
            return
        with self._durable_condition:
            if self._writer_fault is not None:
                raise RuntimeError(
                    "durable_commit_revoked_after_writer_or_shutdown_fault"
                )
            expected = self._durable_ingress_sequence + 1
            for envelope in batch:
                if envelope.feed_session_id != self.feed_session_id:
                    raise RuntimeError("writer_batch_feed_session_mismatch")
                if envelope.ingress_sequence != expected:
                    raise RuntimeError(
                        "writer_batch_sequence_gap:"
                        f"expected={expected};actual={envelope.ingress_sequence}"
                    )
                expected += 1
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

    def durable_snapshot(self) -> DurableTickSnapshot:
        with self._durable_condition:
            rows = tuple(self._durable_rows)
            latest_by_symbol = MappingProxyType(dict(self._latest_by_symbol))
            symbol_watermarks = MappingProxyType(dict(self._symbol_watermarks))
            durable_ingress_sequence = self._durable_ingress_sequence
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
            gap=self._gap,
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
        with self._durable_condition:
            durable_sequence = self._durable_ingress_sequence
            writer_fault = self._writer_fault
        drained = bool(joined and remaining == 0 and writer_fault is None)
        if (not joined or remaining > 0) and writer_fault is None:
            start = durable_sequence + 1
            end = max(start, self._last_ingress_sequence)
            fault = TickStreamFault(
                kind="shutdown_drain_timeout",
                detail=(
                    f"joined={int(joined)};remaining={remaining};"
                    f"durable={durable_sequence};last={self._last_ingress_sequence}"
                ),
                occurred_epoch_ns=0,
            )
            self._fault = self._fault or fault
            self._merge_suffix_gap(
                start_ingress_sequence=start,
                end_ingress_sequence=end,
                reason=fault.kind,
            )
            with self._durable_condition:
                self._writer_fault = fault
                writer_fault = fault
                self._durable_condition.notify_all()
            drained = False
        elif (
            durable_sequence != self._last_ingress_sequence
            and self._gap is None
            and writer_fault is None
        ):
            start = durable_sequence + 1
            end = max(start, self._last_ingress_sequence)
            fault = TickStreamFault(
                kind="shutdown_durable_mismatch",
                detail=(
                    f"durable={durable_sequence};last={self._last_ingress_sequence}"
                ),
                occurred_epoch_ns=0,
            )
            self._fault = self._fault or fault
            self._merge_suffix_gap(
                start_ingress_sequence=start,
                end_ingress_sequence=end,
                reason=fault.kind,
            )
            with self._durable_condition:
                self._writer_fault = fault
                writer_fault = fault
                self._durable_condition.notify_all()
            drained = False
        durable_through = (
            DurableTickCursor(self.feed_session_id, durable_sequence)
            if durable_sequence > 0
            else None
        )
        return ShutdownReport(
            drained=drained,
            durable_through=durable_through,
            remaining_queue_depth=remaining,
            gap=self._gap,
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
            gap=self._gap,
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

    @wraps(original_on_tick)
    def wrapped_on_tick(tick: Any, *args: Any, **kwargs: Any) -> Any:
        try:
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

    gateway.on_tick = wrapped_on_tick
    restored = False

    def restore() -> None:
        nonlocal restored
        if restored:
            return
        restored = True
        if gateway.on_tick is wrapped_on_tick:
            gateway.on_tick = original_on_tick

    return restore


class TickStreamJournalReader:
    def __init__(self, journal_segment_path: Path) -> None:
        self.journal_segment_path = Path(journal_segment_path)

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

        records: list[Mapping[str, Any]] = []
        if self.journal_segment_path.exists():
            with self.journal_segment_path.open("r", encoding="utf-8") as handle:
                for raw_line in handle:
                    if not raw_line.endswith("\n"):
                        break
                    try:
                        row = json.loads(raw_line)
                    except json.JSONDecodeError:
                        break
                    if not isinstance(row, dict):
                        continue
                    if _clean(row.get("feed_session_id")) != durable_through.feed_session_id:
                        continue
                    sequence = int(row.get("ingress_sequence", 0) or 0)
                    if sequence <= after_sequence:
                        continue
                    if sequence > durable_through.ingress_sequence:
                        break
                    records.append(MappingProxyType(dict(row)))
                    if len(records) >= limit:
                        break

        gap: TickStreamGap | None = None
        expected = after_sequence + 1
        for row in records:
            sequence = int(row.get("ingress_sequence", 0) or 0)
            if sequence != expected:
                gap = TickStreamGap(
                    feed_session_id=durable_through.feed_session_id,
                    start_ingress_sequence=expected,
                    end_ingress_sequence=max(expected, sequence - 1),
                    reason="journal_sequence_gap",
                )
                break
            expected += 1
        if (
            gap is None
            and expected <= durable_through.ingress_sequence
            and len(records) < limit
        ):
            gap = TickStreamGap(
                feed_session_id=durable_through.feed_session_id,
                start_ingress_sequence=expected,
                end_ingress_sequence=durable_through.ingress_sequence,
                reason="durable_rows_missing_from_journal",
            )

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
    path = Path(journal_path)
    feed_session_id = _clean(previous_heartbeat.get("feed_session_id"))
    durable_sequence = int(
        previous_heartbeat.get(
            "durable_ingress_sequence",
            previous_heartbeat.get("stream_sequence", 0),
        )
        or 0
    )
    last_ingress_sequence = int(
        previous_heartbeat.get(
            "last_ingress_sequence",
            previous_heartbeat.get("stream_sequence", durable_sequence),
        )
        or 0
    )

    data = path.read_bytes() if path.exists() else b""
    trusted_end = 0
    durable_seen = durable_sequence == 0
    offset = 0
    for line in data.splitlines(keepends=True):
        line_end = offset + len(line)
        if not line.endswith(b"\n"):
            break
        try:
            row = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            break
        if not isinstance(row, dict):
            break
        row_feed = _clean(row.get("feed_session_id"))
        row_sequence = int(row.get("ingress_sequence", 0) or 0)
        if row_feed != feed_session_id or row_sequence > durable_sequence:
            break
        trusted_end = line_end
        if row_sequence == durable_sequence:
            durable_seen = True
        offset = line_end

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
            os.fsync(handle.fileno())
        with path.open("r+b") as handle:
            handle.truncate(trusted_end)
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_parent(path)

    previous_cursor = (
        DurableTickCursor(feed_session_id, durable_sequence)
        if feed_session_id and durable_sequence > 0 and durable_seen
        else None
    )
    disclosed_gap: TickStreamGap | None = None
    if feed_session_id and last_ingress_sequence > durable_sequence:
        disclosed_gap = TickStreamGap(
            feed_session_id=feed_session_id,
            start_ingress_sequence=durable_sequence + 1,
            end_ingress_sequence=last_ingress_sequence,
            reason="prior_uncommitted_suffix",
        )
    elif feed_session_id and durable_sequence > 0 and not durable_seen:
        disclosed_gap = TickStreamGap(
            feed_session_id=feed_session_id,
            start_ingress_sequence=1,
            end_ingress_sequence=max(durable_sequence, last_ingress_sequence),
            reason="durable_cursor_missing_from_journal",
        )
    return JournalRecoveryResult(
        previous_durable_cursor=previous_cursor,
        isolated_tail_path=isolated_tail_path,
        isolated_byte_count=len(tail),
        disclosed_gap=disclosed_gap,
    )
