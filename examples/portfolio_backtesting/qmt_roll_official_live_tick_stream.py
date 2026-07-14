from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from itertools import count
from pathlib import Path
from queue import Full, Queue
from types import MappingProxyType
from typing import Any, Callable, Mapping
import threading

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
    """Gateway-hot-path ingress foundation; durable writing is added separately."""

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
