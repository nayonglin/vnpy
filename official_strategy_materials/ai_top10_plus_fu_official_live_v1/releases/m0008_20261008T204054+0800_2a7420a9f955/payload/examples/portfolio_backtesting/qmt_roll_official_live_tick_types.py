from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


DEFAULT_INGRESS_QUEUE_CAPACITY = 8192
DEFAULT_WRITER_BATCH_SIZE = 256
DEFAULT_WRITER_FLUSH_SECONDS = 0.050
DEFAULT_SHUTDOWN_DRAIN_SECONDS = 2.0
MAX_FEED_SESSION_ID_BYTES = 256

JOURNAL_RECORD_TYPE_FIELD = "_stage179_record_type"
JOURNAL_HEADER_RECORD_TYPE = "tick_journal_header_v1"
JOURNAL_BATCH_COMMIT_RECORD_TYPE = "tick_batch_commit_v1"
JOURNAL_BATCH_COMMIT_SCHEMA_VERSION = 1
JOURNAL_SCHEMA_FRAMED_V1 = "stage179_framed_v1"
JOURNAL_SCHEMA_LEGACY_V0 = "legacy_ndjson_v0"
JOURNAL_FORMAT_FRAMED_V1 = "stage179_framed_ndjson_v1"
JOURNAL_FORMAT_LEGACY_V0 = "legacy_ndjson_v0"

TICK_INGRESS_ENVELOPE_ATTR = "_stage179_tick_ingress_envelope"


@dataclass(frozen=True, slots=True)
class DurableTickCursor:
    feed_session_id: str
    ingress_sequence: int
    journal_byte_offset: int = 0
    journal_schema: str = JOURNAL_SCHEMA_FRAMED_V1


@dataclass(frozen=True, slots=True)
class TickIngressEnvelope:
    feed_session_id: str
    ingress_sequence: int
    symbol_sequence: int
    received_at_utc: str
    ingress_epoch_ns: int
    ingress_monotonic_ns: int
    clock_domain_id: str
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
    durable_journal_byte_offset: int = 0
    journal_schema: str = JOURNAL_SCHEMA_FRAMED_V1


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
    uncommitted_tick_count: int
    gap: TickStreamGap | None
    writer_fault: TickStreamFault | None


@dataclass(frozen=True, slots=True)
class JournalRecoveryResult:
    previous_durable_cursor: DurableTickCursor | None
    isolated_tail_path: Path | None
    isolated_byte_count: int
    disclosed_gap: TickStreamGap | None
    disclosed_gaps: tuple[TickStreamGap, ...] = ()
    journal_schema: str = JOURNAL_SCHEMA_FRAMED_V1
    recovery_transaction_id: str = ""
    recovery_manifest_path: Path | None = None
    recovery_ack_required: bool = False
