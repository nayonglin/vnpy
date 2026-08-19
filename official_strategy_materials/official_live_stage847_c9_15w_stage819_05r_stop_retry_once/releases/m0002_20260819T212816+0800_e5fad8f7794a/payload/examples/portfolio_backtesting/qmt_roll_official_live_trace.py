from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Any, Mapping
from types import MappingProxyType
import uuid

from qmt_roll_official_live_time import Clock, utc_iso_from_epoch_ns


TRACE_SCHEMA_VERSION = 1
TRACE_DEADLINE_NS = 25_000_000_000
TRACE_UUID_NAMESPACE = uuid.NAMESPACE_URL
MAX_TRACE_JSON_BYTES = 4 * 1024 * 1024
MAX_UTC_EPOCH_NS = 253_402_300_799_999_999_999


class TraceValidationError(ValueError):
    """Raised when trace evidence cannot be trusted as one causal timeline."""


class TraceStage(str, Enum):
    GATEWAY_INGRESS = "gateway_ingress"
    EVENT_HANDLER_OBSERVED = "event_handler_observed"
    JOURNAL_DURABLE = "journal_durable"
    STAGE904_DETECTED = "stage904_detected"
    STAGE905_INTENT_READY = "stage905_intent_ready"
    SPOOL_COMMITTED = "spool_committed"
    EXECUTOR_DEQUEUED = "executor_dequeued"
    BROKER_BUNDLE_READY = "broker_bundle_ready"
    SEND_ORDER_CALLED = "send_order_called"
    FIRST_BROKER_ACK = "first_broker_ack"
    FIRST_FILL = "first_fill"
    CANCEL_REQUESTED = "cancel_requested"
    CANCEL_TERMINAL = "cancel_terminal"
    LEDGER_DURABLE = "ledger_durable"


_CAUSAL_EDGES: tuple[tuple[TraceStage, TraceStage], ...] = (
    (TraceStage.GATEWAY_INGRESS, TraceStage.EVENT_HANDLER_OBSERVED),
    (TraceStage.GATEWAY_INGRESS, TraceStage.JOURNAL_DURABLE),
    (TraceStage.JOURNAL_DURABLE, TraceStage.STAGE904_DETECTED),
    (TraceStage.STAGE904_DETECTED, TraceStage.STAGE905_INTENT_READY),
    (TraceStage.STAGE905_INTENT_READY, TraceStage.SPOOL_COMMITTED),
    (TraceStage.SPOOL_COMMITTED, TraceStage.EXECUTOR_DEQUEUED),
    (TraceStage.EXECUTOR_DEQUEUED, TraceStage.BROKER_BUNDLE_READY),
    (TraceStage.BROKER_BUNDLE_READY, TraceStage.SEND_ORDER_CALLED),
    (TraceStage.SEND_ORDER_CALLED, TraceStage.FIRST_BROKER_ACK),
    (TraceStage.SEND_ORDER_CALLED, TraceStage.FIRST_FILL),
    (TraceStage.SEND_ORDER_CALLED, TraceStage.CANCEL_REQUESTED),
    (TraceStage.CANCEL_REQUESTED, TraceStage.CANCEL_TERMINAL),
    (TraceStage.FIRST_FILL, TraceStage.LEDGER_DURABLE),
)


def _exact_int(
    value: Any,
    *,
    field_name: str,
    minimum: int = 0,
) -> int:
    if type(value) is not int:
        raise TraceValidationError(
            f"{field_name}_must_be_exact_int:actual={type(value).__name__}"
        )
    if value < minimum:
        raise TraceValidationError(f"{field_name}_below_minimum:{value}<{minimum}")
    return value


def _required_text(value: Any, *, field_name: str, max_bytes: int = 512) -> str:
    if not isinstance(value, str):
        raise TraceValidationError(
            f"{field_name}_must_be_text:actual={type(value).__name__}"
        )
    normalized = value.strip()
    if not normalized:
        raise TraceValidationError(f"{field_name}_must_not_be_empty")
    if any(ord(character) < 32 for character in normalized):
        raise TraceValidationError(f"{field_name}_contains_control_character")
    try:
        encoded = normalized.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise TraceValidationError(f"{field_name}_must_be_utf8") from exc
    if len(encoded) > max_bytes:
        raise TraceValidationError(
            f"{field_name}_too_long:{len(encoded)}>{max_bytes}"
        )
    return normalized


def _coerce_stage(value: TraceStage | str) -> TraceStage:
    if isinstance(value, TraceStage):
        return value
    if not isinstance(value, str):
        raise TraceValidationError(
            f"trace_stage_must_be_text:actual={type(value).__name__}"
        )
    try:
        return TraceStage(value)
    except ValueError as exc:
        raise TraceValidationError(f"trace_stage_unknown:{value}") from exc


def _strict_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise TraceValidationError(f"trace_json_duplicate_member:{key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> Any:
    raise TraceValidationError(f"trace_json_nonfinite_number:{value}")


def _clock_domain_id(clock: Clock) -> str:
    provider = getattr(clock, "clock_domain_id", None)
    if not callable(provider):
        raise TraceValidationError("clock_domain_provider_missing")
    try:
        value = provider()
    except Exception as exc:
        raise TraceValidationError(
            f"clock_domain_provider_failed:{type(exc).__name__}:{exc}"
        ) from exc
    return _required_text(value, field_name="clock_domain_id", max_bytes=256)


def deterministic_trace_id(feed_session_id: str, ingress_sequence: int) -> str:
    feed = _required_text(
        feed_session_id,
        field_name="feed_session_id",
        max_bytes=256,
    )
    sequence = _exact_int(
        ingress_sequence,
        field_name="ingress_sequence",
        minimum=1,
    )
    return str(uuid.uuid5(TRACE_UUID_NAMESPACE, f"{feed}:{sequence}"))


def _source_tick_trace_id(feed_session_id: str, ingress_sequence: int) -> str:
    return f"stage179-tick/{feed_session_id}/{ingress_sequence}"


@dataclass(frozen=True, slots=True)
class ClockStamp:
    epoch_ns: int
    monotonic_ns: int
    clock_domain_id: str
    utc_iso: str

    def __post_init__(self) -> None:
        epoch_ns = _exact_int(self.epoch_ns, field_name="clock_stamp_epoch_ns")
        if epoch_ns > MAX_UTC_EPOCH_NS:
            raise TraceValidationError(
                f"clock_stamp_epoch_ns_above_maximum:{epoch_ns}>{MAX_UTC_EPOCH_NS}"
            )
        monotonic_ns = _exact_int(
            self.monotonic_ns,
            field_name="clock_stamp_monotonic_ns",
        )
        clock_domain_id = _required_text(
            self.clock_domain_id,
            field_name="clock_domain_id",
            max_bytes=256,
        )
        utc_text = _required_text(self.utc_iso, field_name="clock_stamp_utc")
        try:
            parsed = datetime.fromisoformat(utc_text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise TraceValidationError("clock_stamp_utc_invalid") from exc
        if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
            raise TraceValidationError("clock_stamp_utc_must_be_aware_utc")
        try:
            expected = utc_iso_from_epoch_ns(epoch_ns)
        except (OverflowError, OSError, ValueError) as exc:
            raise TraceValidationError("clock_stamp_epoch_out_of_range") from exc
        if utc_text != expected:
            raise TraceValidationError(
                f"clock_stamp_utc_epoch_mismatch:expected={expected};actual={utc_text}"
            )
        object.__setattr__(self, "epoch_ns", epoch_ns)
        object.__setattr__(self, "monotonic_ns", monotonic_ns)
        object.__setattr__(self, "clock_domain_id", clock_domain_id)
        object.__setattr__(self, "utc_iso", utc_text)

    @classmethod
    def from_clock(cls, clock: Clock) -> "ClockStamp":
        epoch_ns = _exact_int(clock.epoch_ns(), field_name="clock_epoch_ns")
        if epoch_ns > MAX_UTC_EPOCH_NS:
            raise TraceValidationError(
                f"clock_epoch_ns_above_maximum:{epoch_ns}>{MAX_UTC_EPOCH_NS}"
            )
        monotonic_ns = _exact_int(
            clock.monotonic_ns(),
            field_name="clock_monotonic_ns",
        )
        try:
            utc_iso = utc_iso_from_epoch_ns(epoch_ns)
        except (OverflowError, OSError, ValueError) as exc:
            raise TraceValidationError("clock_epoch_out_of_range") from exc
        return cls(
            epoch_ns=epoch_ns,
            monotonic_ns=monotonic_ns,
            clock_domain_id=_clock_domain_id(clock),
            utc_iso=utc_iso,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "epoch_ns": self.epoch_ns,
            "monotonic_ns": self.monotonic_ns,
            "clock_domain_id": self.clock_domain_id,
            "utc_iso": self.utc_iso,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ClockStamp":
        if not isinstance(payload, Mapping):
            raise TraceValidationError("clock_stamp_payload_must_be_mapping")
        expected = {"epoch_ns", "monotonic_ns", "clock_domain_id", "utc_iso"}
        if set(payload) != expected:
            raise TraceValidationError(
                "clock_stamp_fields_invalid:"
                f"missing={sorted(expected - set(payload))};"
                f"unknown={sorted(set(payload) - expected)}"
            )
        return cls(
            epoch_ns=payload["epoch_ns"],
            monotonic_ns=payload["monotonic_ns"],
            clock_domain_id=payload["clock_domain_id"],
            utc_iso=payload["utc_iso"],
        )


@dataclass(frozen=True, slots=True)
class LatencyTrace:
    schema_version: int
    trace_id: str
    source_tick_trace_id: str
    feed_session_id: str
    ingress_sequence: int
    symbol_sequence: int
    vt_symbol: str
    deadline_epoch_ns: int
    deadline_monotonic_ns: int
    stamps: Mapping[str, ClockStamp] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _exact_int(
            self.schema_version,
            field_name="trace_schema_version",
            minimum=TRACE_SCHEMA_VERSION,
        )
        if self.schema_version != TRACE_SCHEMA_VERSION:
            raise TraceValidationError(
                f"trace_schema_version_unsupported:{self.schema_version}"
            )
        normalized_feed_session_id = _required_text(
            self.feed_session_id,
            field_name="feed_session_id",
            max_bytes=256,
        )
        normalized_ingress_sequence = _exact_int(
            self.ingress_sequence,
            field_name="ingress_sequence",
            minimum=1,
        )
        normalized_symbol_sequence = _exact_int(
            self.symbol_sequence,
            field_name="symbol_sequence",
            minimum=1,
        )
        normalized_vt_symbol = _required_text(self.vt_symbol, field_name="vt_symbol")
        object.__setattr__(self, "feed_session_id", normalized_feed_session_id)
        object.__setattr__(self, "ingress_sequence", normalized_ingress_sequence)
        object.__setattr__(self, "symbol_sequence", normalized_symbol_sequence)
        object.__setattr__(self, "vt_symbol", normalized_vt_symbol)
        expected_trace_id = deterministic_trace_id(
            self.feed_session_id,
            self.ingress_sequence,
        )
        normalized_trace_id = _required_text(self.trace_id, field_name="trace_id")
        if normalized_trace_id != expected_trace_id:
            raise TraceValidationError(
                f"trace_id_mismatch:expected={expected_trace_id};"
                f"actual={normalized_trace_id}"
            )
        object.__setattr__(self, "trace_id", normalized_trace_id)
        expected_source = _source_tick_trace_id(
            self.feed_session_id,
            self.ingress_sequence,
        )
        normalized_source_tick_trace_id = _required_text(
            self.source_tick_trace_id,
            field_name="source_tick_trace_id",
        )
        if normalized_source_tick_trace_id != expected_source:
            raise TraceValidationError(
                "source_tick_trace_id_mismatch:"
                f"expected={expected_source};actual={normalized_source_tick_trace_id}"
            )
        object.__setattr__(
            self,
            "source_tick_trace_id",
            normalized_source_tick_trace_id,
        )
        normalized_deadline_epoch_ns = _exact_int(
            self.deadline_epoch_ns,
            field_name="deadline_epoch_ns",
        )
        normalized_deadline_monotonic_ns = _exact_int(
            self.deadline_monotonic_ns,
            field_name="deadline_monotonic_ns",
        )
        object.__setattr__(self, "deadline_epoch_ns", normalized_deadline_epoch_ns)
        object.__setattr__(
            self,
            "deadline_monotonic_ns",
            normalized_deadline_monotonic_ns,
        )
        if not isinstance(self.stamps, Mapping):
            raise TraceValidationError("trace_stamps_must_be_mapping")
        normalized_stamps: dict[str, ClockStamp] = {}
        for raw_stage, stamp in self.stamps.items():
            stage = _coerce_stage(raw_stage)
            if not isinstance(stamp, ClockStamp):
                raise TraceValidationError(
                    f"trace_stamp_value_invalid:{stage.value}:"
                    f"{type(stamp).__name__}"
                )
            normalized_stamps[stage.value] = stamp
        object.__setattr__(self, "stamps", MappingProxyType(normalized_stamps))
        ingress = self.stamps.get(TraceStage.GATEWAY_INGRESS.value)
        if ingress is None:
            raise TraceValidationError("gateway_ingress_stamp_missing")
        expected_epoch_deadline = ingress.epoch_ns + TRACE_DEADLINE_NS
        expected_monotonic_deadline = ingress.monotonic_ns + TRACE_DEADLINE_NS
        if self.deadline_epoch_ns != expected_epoch_deadline:
            raise TraceValidationError(
                "deadline_epoch_ns_tampered:"
                f"expected={expected_epoch_deadline};actual={self.deadline_epoch_ns}"
            )
        if self.deadline_monotonic_ns != expected_monotonic_deadline:
            raise TraceValidationError(
                "deadline_monotonic_ns_tampered:"
                f"expected={expected_monotonic_deadline};"
                f"actual={self.deadline_monotonic_ns}"
            )
        self._validate_causal_stamps()

    def _validate_causal_stamps(self) -> None:
        ingress = self.stamps[TraceStage.GATEWAY_INGRESS.value]
        for stage_value, stamp in self.stamps.items():
            if (
                stamp.clock_domain_id == ingress.clock_domain_id
                and stamp.monotonic_ns < ingress.monotonic_ns
            ):
                raise TraceValidationError(
                    "monotonic_rollback:"
                    f"stage={stage_value};ingress={ingress.monotonic_ns};"
                    f"actual={stamp.monotonic_ns}"
                )
            if (
                stamp.clock_domain_id != ingress.clock_domain_id
                and stamp.epoch_ns < ingress.epoch_ns
            ):
                raise TraceValidationError(
                    "cross_domain_epoch_rollback:"
                    f"stage={stage_value};ingress={ingress.epoch_ns};"
                    f"actual={stamp.epoch_ns}"
                )
        for start_stage, end_stage in _CAUSAL_EDGES:
            start = self.stamps.get(start_stage.value)
            end = self.stamps.get(end_stage.value)
            if (
                start is not None
                and end is not None
                and start.clock_domain_id == end.clock_domain_id
                and end.monotonic_ns < start.monotonic_ns
            ):
                raise TraceValidationError(
                    "monotonic_rollback:"
                    f"start={start_stage.value};end={end_stage.value};"
                    f"start_ns={start.monotonic_ns};end_ns={end.monotonic_ns}"
                )
            if (
                start is not None
                and end is not None
                and start.clock_domain_id != end.clock_domain_id
                and end.epoch_ns < start.epoch_ns
            ):
                raise TraceValidationError(
                    "cross_domain_epoch_rollback:"
                    f"start={start_stage.value};end={end_stage.value};"
                    f"start_ns={start.epoch_ns};end_ns={end.epoch_ns}"
                )

    @classmethod
    def from_ingress_row(
        cls,
        row: Mapping[str, Any],
        *,
        clock: Clock,
    ) -> "LatencyTrace":
        if not isinstance(row, Mapping):
            raise TraceValidationError("ingress_row_must_be_mapping")
        feed_session_id = _required_text(
            row.get("feed_session_id"),
            field_name="feed_session_id",
            max_bytes=256,
        )
        ingress_sequence = _exact_int(
            row.get("ingress_sequence"),
            field_name="ingress_sequence",
            minimum=1,
        )
        symbol_sequence = _exact_int(
            row.get("symbol_sequence"),
            field_name="symbol_sequence",
            minimum=1,
        )
        ingress_epoch_ns = _exact_int(
            row.get("ingress_epoch_ns"),
            field_name="ingress_epoch_ns",
        )
        ingress_monotonic_ns = _exact_int(
            row.get("ingress_monotonic_ns"),
            field_name="ingress_monotonic_ns",
        )
        domain_id = _clock_domain_id(clock)
        normalized_row_domain = _required_text(
            row.get("clock_domain_id"),
            field_name="ingress_clock_domain_id",
            max_bytes=256,
        )
        if normalized_row_domain != domain_id:
            raise TraceValidationError(
                "ingress_clock_domain_mismatch:"
                f"row={normalized_row_domain};clock={domain_id}"
            )
        ingress_stamp = ClockStamp(
            epoch_ns=ingress_epoch_ns,
            monotonic_ns=ingress_monotonic_ns,
            clock_domain_id=domain_id,
            utc_iso=row.get("received_at_utc"),
        )
        source_tick_trace_id = _required_text(
            row.get("trace_id"),
            field_name="source_tick_trace_id",
        )
        return cls(
            schema_version=TRACE_SCHEMA_VERSION,
            trace_id=deterministic_trace_id(feed_session_id, ingress_sequence),
            source_tick_trace_id=source_tick_trace_id,
            feed_session_id=feed_session_id,
            ingress_sequence=ingress_sequence,
            symbol_sequence=symbol_sequence,
            vt_symbol=_required_text(row.get("vt_symbol"), field_name="vt_symbol"),
            deadline_epoch_ns=ingress_epoch_ns + TRACE_DEADLINE_NS,
            deadline_monotonic_ns=ingress_monotonic_ns + TRACE_DEADLINE_NS,
            stamps={TraceStage.GATEWAY_INGRESS.value: ingress_stamp},
        )

    def record_stamp(
        self,
        stage: TraceStage | str,
        stamp: ClockStamp,
    ) -> "LatencyTrace":
        normalized_stage = _coerce_stage(stage)
        if not isinstance(stamp, ClockStamp):
            raise TraceValidationError(
                f"trace_stamp_value_invalid:{normalized_stage.value}:"
                f"{type(stamp).__name__}"
            )
        existing = self.stamps.get(normalized_stage.value)
        if existing is not None:
            if existing == stamp:
                return self
            raise TraceValidationError(f"stamp_conflict:{normalized_stage.value}")
        updated = dict(self.stamps)
        updated[normalized_stage.value] = stamp
        return replace(self, stamps=updated)

    def record_from_clock(
        self,
        stage: TraceStage | str,
        clock: Clock,
    ) -> "LatencyTrace":
        stamp = ClockStamp.from_clock(clock)
        return self.record_stamp(stage, stamp)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "source_tick_trace_id": self.source_tick_trace_id,
            "feed_session_id": self.feed_session_id,
            "ingress_sequence": self.ingress_sequence,
            "symbol_sequence": self.symbol_sequence,
            "vt_symbol": self.vt_symbol,
            "deadline_epoch_ns": self.deadline_epoch_ns,
            "deadline_monotonic_ns": self.deadline_monotonic_ns,
            "stamps": {
                stage: self.stamps[stage].to_dict()
                for stage in sorted(self.stamps)
            },
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "LatencyTrace":
        if not isinstance(payload, Mapping):
            raise TraceValidationError("trace_payload_must_be_mapping")
        expected = {
            "schema_version",
            "trace_id",
            "source_tick_trace_id",
            "feed_session_id",
            "ingress_sequence",
            "symbol_sequence",
            "vt_symbol",
            "deadline_epoch_ns",
            "deadline_monotonic_ns",
            "stamps",
        }
        if set(payload) != expected:
            raise TraceValidationError(
                "trace_fields_invalid:"
                f"missing={sorted(expected - set(payload))};"
                f"unknown={sorted(set(payload) - expected)}"
            )
        raw_stamps = payload["stamps"]
        if not isinstance(raw_stamps, Mapping):
            raise TraceValidationError("trace_stamps_payload_must_be_mapping")
        stamps = {
            _coerce_stage(stage).value: ClockStamp.from_dict(stamp)
            for stage, stamp in raw_stamps.items()
        }
        return cls(
            schema_version=payload["schema_version"],
            trace_id=payload["trace_id"],
            source_tick_trace_id=payload["source_tick_trace_id"],
            feed_session_id=payload["feed_session_id"],
            ingress_sequence=payload["ingress_sequence"],
            symbol_sequence=payload["symbol_sequence"],
            vt_symbol=payload["vt_symbol"],
            deadline_epoch_ns=payload["deadline_epoch_ns"],
            deadline_monotonic_ns=payload["deadline_monotonic_ns"],
            stamps=stamps,
        )

    @classmethod
    def from_json(cls, payload: str) -> "LatencyTrace":
        if not isinstance(payload, str):
            raise TraceValidationError("trace_json_must_be_text")
        try:
            payload_size = len(payload.encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise TraceValidationError("trace_json_must_be_utf8") from exc
        if payload_size > MAX_TRACE_JSON_BYTES:
            raise TraceValidationError(
                f"trace_json_too_large:{payload_size}>{MAX_TRACE_JSON_BYTES}"
            )
        try:
            decoded = json.loads(
                payload,
                object_pairs_hook=_strict_json_object,
                parse_constant=_reject_json_constant,
            )
        except TraceValidationError:
            raise
        except (json.JSONDecodeError, RecursionError, ValueError, OverflowError) as exc:
            raise TraceValidationError(f"trace_json_invalid:{exc}") from exc
        return cls.from_dict(decoded)


@dataclass(frozen=True, slots=True)
class SlaBudget:
    name: str
    start_stage: TraceStage
    end_stage: TraceStage
    slo_ns: int
    hard_limit_ns: int
    required_intermediate_stages: tuple[TraceStage, ...] = ()
    activation_stage: TraceStage | None = None

    def __post_init__(self) -> None:
        _required_text(self.name, field_name="sla_budget_name")
        if not isinstance(self.start_stage, TraceStage):
            raise TraceValidationError("sla_start_stage_invalid")
        if not isinstance(self.end_stage, TraceStage):
            raise TraceValidationError("sla_end_stage_invalid")
        slo_ns = _exact_int(self.slo_ns, field_name=f"{self.name}_slo_ns", minimum=1)
        hard_ns = _exact_int(
            self.hard_limit_ns,
            field_name=f"{self.name}_hard_limit_ns",
            minimum=1,
        )
        if slo_ns >= hard_ns:
            raise TraceValidationError(
                f"sla_budget_limits_invalid:{self.name}:{slo_ns}>={hard_ns}"
            )
        try:
            normalized_required = tuple(self.required_intermediate_stages)
        except TypeError as exc:
            raise TraceValidationError(
                f"sla_required_intermediate_invalid:{self.name}"
            ) from exc
        object.__setattr__(
            self,
            "required_intermediate_stages",
            normalized_required,
        )
        if any(
            not isinstance(stage, TraceStage)
            for stage in normalized_required
        ):
            raise TraceValidationError(
                f"sla_required_intermediate_invalid:{self.name}"
            )
        if len(set(normalized_required)) != len(normalized_required):
            raise TraceValidationError(
                f"sla_required_intermediate_duplicate:{self.name}"
            )
        if self.activation_stage is not None and not isinstance(
            self.activation_stage,
            TraceStage,
        ):
            raise TraceValidationError(f"sla_activation_stage_invalid:{self.name}")


SLA_BUDGETS: tuple[SlaBudget, ...] = (
    SlaBudget(
        "ingress_to_journal_durable",
        TraceStage.GATEWAY_INGRESS,
        TraceStage.JOURNAL_DURABLE,
        500_000_000,
        1_000_000_000,
    ),
    SlaBudget(
        "journal_durable_to_stage904",
        TraceStage.JOURNAL_DURABLE,
        TraceStage.STAGE904_DETECTED,
        500_000_000,
        1_000_000_000,
    ),
    SlaBudget(
        "stage904_to_spool",
        TraceStage.STAGE904_DETECTED,
        TraceStage.SPOOL_COMMITTED,
        250_000_000,
        500_000_000,
        required_intermediate_stages=(TraceStage.STAGE905_INTENT_READY,),
    ),
    SlaBudget(
        "spool_to_executor_dequeue",
        TraceStage.SPOOL_COMMITTED,
        TraceStage.EXECUTOR_DEQUEUED,
        100_000_000,
        500_000_000,
    ),
    SlaBudget(
        "dequeue_to_send_order",
        TraceStage.EXECUTOR_DEQUEUED,
        TraceStage.SEND_ORDER_CALLED,
        15_000_000_000,
        20_000_000_000,
        required_intermediate_stages=(TraceStage.BROKER_BUNDLE_READY,),
    ),
    SlaBudget(
        "ingress_to_send_order",
        TraceStage.GATEWAY_INGRESS,
        TraceStage.SEND_ORDER_CALLED,
        17_000_000_000,
        25_000_000_000,
        required_intermediate_stages=(
            TraceStage.JOURNAL_DURABLE,
            TraceStage.STAGE904_DETECTED,
            TraceStage.STAGE905_INTENT_READY,
            TraceStage.SPOOL_COMMITTED,
            TraceStage.EXECUTOR_DEQUEUED,
            TraceStage.BROKER_BUNDLE_READY,
        ),
    ),
    SlaBudget(
        "send_order_to_first_ack",
        TraceStage.SEND_ORDER_CALLED,
        TraceStage.FIRST_BROKER_ACK,
        2_000_000_000,
        3_000_000_000,
    ),
    SlaBudget(
        "send_order_to_first_fill",
        TraceStage.SEND_ORDER_CALLED,
        TraceStage.FIRST_FILL,
        5_000_000_000,
        8_000_000_000,
        activation_stage=TraceStage.FIRST_FILL,
    ),
    SlaBudget(
        "cancel_to_terminal",
        TraceStage.CANCEL_REQUESTED,
        TraceStage.CANCEL_TERMINAL,
        8_000_000_000,
        10_000_000_000,
        activation_stage=TraceStage.CANCEL_REQUESTED,
    ),
    SlaBudget(
        "fill_to_ledger_durable",
        TraceStage.FIRST_FILL,
        TraceStage.LEDGER_DURABLE,
        500_000_000,
        2_000_000_000,
        activation_stage=TraceStage.FIRST_FILL,
    ),
)


@dataclass(frozen=True, slots=True)
class SlaEvaluation:
    budget_name: str
    status: str
    applicable: bool
    eligible: bool
    passed: bool
    latency_ns: int | None
    slo_met: bool
    hard_limit_met: bool
    audit_epoch_latency_ns: int | None = None
    missing_stages: tuple[str, ...] = ()


def _evaluation(
    budget: SlaBudget,
    *,
    status: str,
    applicable: bool,
    eligible: bool,
    passed: bool,
    latency_ns: int | None = None,
    slo_met: bool = False,
    hard_limit_met: bool = False,
    audit_epoch_latency_ns: int | None = None,
    missing_stages: tuple[str, ...] = (),
) -> SlaEvaluation:
    return SlaEvaluation(
        budget_name=budget.name,
        status=status,
        applicable=applicable,
        eligible=eligible,
        passed=passed,
        latency_ns=latency_ns,
        slo_met=slo_met,
        hard_limit_met=hard_limit_met,
        audit_epoch_latency_ns=audit_epoch_latency_ns,
        missing_stages=missing_stages,
    )


def evaluate_sla(trace: LatencyTrace, budget: SlaBudget) -> SlaEvaluation:
    if not isinstance(trace, LatencyTrace):
        raise TraceValidationError("sla_trace_invalid")
    if not isinstance(budget, SlaBudget):
        raise TraceValidationError("sla_budget_invalid")
    if budget.activation_stage is not None and budget.activation_stage.value not in trace.stamps:
        if budget.end_stage.value in trace.stamps:
            return _evaluation(
                budget,
                status="missing_timestamp",
                applicable=True,
                eligible=False,
                passed=False,
                missing_stages=(budget.activation_stage.value,),
            )
        return _evaluation(
            budget,
            status="not_applicable",
            applicable=False,
            eligible=False,
            passed=False,
        )
    required = (
        budget.start_stage,
        *budget.required_intermediate_stages,
        budget.end_stage,
    )
    missing = tuple(stage.value for stage in required if stage.value not in trace.stamps)
    if missing:
        return _evaluation(
            budget,
            status="missing_timestamp",
            applicable=True,
            eligible=False,
            passed=False,
            missing_stages=missing,
        )
    stamps = [trace.stamps[stage.value] for stage in required]
    if len({stamp.clock_domain_id for stamp in stamps}) != 1:
        start = trace.stamps[budget.start_stage.value]
        end = trace.stamps[budget.end_stage.value]
        audit_epoch_latency_ns = end.epoch_ns - start.epoch_ns
        if audit_epoch_latency_ns < 0:
            raise TraceValidationError(
                "cross_domain_epoch_rollback:"
                f"budget={budget.name};start={start.epoch_ns};end={end.epoch_ns}"
            )
        return _evaluation(
            budget,
            status="clock_domain_mismatch",
            applicable=True,
            eligible=False,
            passed=False,
            audit_epoch_latency_ns=audit_epoch_latency_ns,
        )
    start = trace.stamps[budget.start_stage.value]
    end = trace.stamps[budget.end_stage.value]
    latency_ns = end.monotonic_ns - start.monotonic_ns
    if latency_ns < 0:
        raise TraceValidationError(
            "monotonic_rollback:"
            f"budget={budget.name};start={start.monotonic_ns};"
            f"end={end.monotonic_ns}"
        )
    if latency_ns >= budget.hard_limit_ns:
        return _evaluation(
            budget,
            status="hard_limit_exceeded",
            applicable=True,
            eligible=True,
            passed=False,
            latency_ns=latency_ns,
            slo_met=False,
            hard_limit_met=False,
        )
    if latency_ns > budget.slo_ns:
        return _evaluation(
            budget,
            status="slo_exceeded",
            applicable=True,
            eligible=True,
            passed=False,
            latency_ns=latency_ns,
            slo_met=False,
            hard_limit_met=True,
        )
    return _evaluation(
        budget,
        status="passed",
        applicable=True,
        eligible=True,
        passed=True,
        latency_ns=latency_ns,
        slo_met=True,
        hard_limit_met=True,
    )


def evaluate_all_slas(trace: LatencyTrace) -> tuple[SlaEvaluation, ...]:
    return tuple(evaluate_sla(trace, budget) for budget in SLA_BUDGETS)


def _late_disposition(intent_kind: str) -> str:
    normalized = _required_text(intent_kind, field_name="intent_kind").lower()
    if normalized == "open":
        return "expired"
    if normalized == "close":
        return "blocked"
    raise TraceValidationError(f"intent_kind_unsupported:{intent_kind}")


def deadline_disposition(elapsed_ns: int, intent_kind: str) -> str:
    elapsed = _exact_int(elapsed_ns, field_name="deadline_elapsed_ns")
    if elapsed >= TRACE_DEADLINE_NS:
        return _late_disposition(intent_kind)
    normalized = _required_text(intent_kind, field_name="intent_kind").lower()
    if normalized not in {"open", "close"}:
        raise TraceValidationError(f"intent_kind_unsupported:{intent_kind}")
    return "ready"


def disposition_for_trace(
    trace: LatencyTrace,
    *,
    now: ClockStamp,
    intent_kind: str,
) -> str:
    if not isinstance(trace, LatencyTrace):
        raise TraceValidationError("deadline_trace_invalid")
    if not isinstance(now, ClockStamp):
        raise TraceValidationError("deadline_now_stamp_invalid")
    ingress = trace.stamps[TraceStage.GATEWAY_INGRESS.value]
    if now.clock_domain_id != ingress.clock_domain_id:
        return _late_disposition(intent_kind)
    if now.monotonic_ns < ingress.monotonic_ns:
        raise TraceValidationError(
            "monotonic_rollback:"
            f"ingress={ingress.monotonic_ns};now={now.monotonic_ns}"
        )
    elapsed_ns = now.monotonic_ns - ingress.monotonic_ns
    if (
        now.monotonic_ns >= trace.deadline_monotonic_ns
        or now.epoch_ns >= trace.deadline_epoch_ns
    ):
        return _late_disposition(intent_kind)
    return deadline_disposition(elapsed_ns, intent_kind)


__all__ = [
    "ClockStamp",
    "LatencyTrace",
    "SLA_BUDGETS",
    "SlaBudget",
    "SlaEvaluation",
    "TRACE_DEADLINE_NS",
    "TRACE_SCHEMA_VERSION",
    "TraceStage",
    "TraceValidationError",
    "deadline_disposition",
    "deterministic_trace_id",
    "disposition_for_trace",
    "evaluate_all_slas",
    "evaluate_sla",
]
