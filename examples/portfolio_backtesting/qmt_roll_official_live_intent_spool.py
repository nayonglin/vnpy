from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import socket
import sqlite3
import tempfile
import time
from typing import Any, Iterator, Mapping, Sequence
import uuid

from qmt_roll_official_live_tick_types import (
    DurableTickCursor,
    JOURNAL_SCHEMA_FRAMED_V1,
)
from qmt_roll_official_live_trace import LatencyTrace, TraceValidationError


SCHEMA_VERSION = "1"
EXPECTED_SCHEMA_FINGERPRINT = (
    "135353c9e1fa2fa150c5921b65c7b916dd3a12b6f9079820d5be53c8a570cf0d"
)
INTENT_STATES = (
    "ready",
    "leased",
    "sending",
    "side_effect_unknown",
    "sent",
    "reconciled",
    "expired",
    "blocked",
)
OUTSTANDING_CLOSE_STATES = (
    "ready",
    "leased",
    "sending",
    "side_effect_unknown",
    "blocked",
)
_CLOSE_DELIVERY_ACTIVE_STATES = {
    "ready",
    "leased",
    "sending",
    "side_effect_unknown",
    "sent",
    "reconciled",
}
_SAFE_ZERO_NATIVE_CLOSE_BLOCK_ERRORS = {
    "deadline_expired_close_critical",
    "deadline_clock_domain_mismatch",
    "deadline_monotonic_rollback",
    "pre_send_absolute_deadline_exceeded",
    "pre_send_clock_domain_mismatch",
    "pre_send_monotonic_rollback",
}
_SAFE_ZERO_NATIVE_LEDGER_DISPOSITIONS = {
    "",
    "no_side_effect_retryable",
    "post_slot_no_native_retryable",
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_TRANSITIONS = {
    "leased": {"ready", "sending", "expired", "blocked"},
    "sending": {"ready", "side_effect_unknown", "sent", "blocked"},
    "side_effect_unknown": {"sent", "reconciled", "blocked"},
    "sent": {"reconciled"},
}
_TRACE_OBSERVATION_COLUMNS = {
    "stage904_detected": "stage904_detected_json",
    "stage905_intent_ready": "stage905_intent_ready_json",
    "spool_committed": "spool_committed_json",
    "executor_dequeued": "executor_dequeued_json",
}
_REQUIRED_SCHEMA_COLUMNS = {
    "detector_cursors": {
        "consumer_id",
        "feed_session_id",
        "ingress_sequence",
        "journal_byte_offset",
        "journal_schema",
        "cursor_revision",
        "batch_manifest_sha256",
        "batch_intent_count",
        "updated_epoch_ns",
    },
    "intents": {
        "spool_sequence",
        "intent_id",
        "payload_sha256",
        "trace_id",
        "payload_json",
        "trace_json",
        "state_generation",
        "position_epoch_id",
        "target_date",
        "source",
        "vt_symbol",
        "deadline_epoch_ns",
        "deadline_monotonic_ns",
        "clock_domain_id",
        "state_revision",
        "lease_token",
        "lease_expires_epoch_ns",
        "lease_expires_monotonic_ns",
        "lease_clock_domain_id",
        "recovery_evidence_json",
        *_TRACE_OBSERVATION_COLUMNS.values(),
    },
}


class SpoolError(RuntimeError):
    pass


class SpoolValidationError(SpoolError):
    pass


class SpoolConflictError(SpoolError):
    pass


class SpoolStorageError(SpoolError):
    pass


class DetectorCursorConflictError(SpoolError):
    pass


class SpoolTransitionError(SpoolError):
    pass


@dataclass(frozen=True, slots=True)
class SpoolIntent:
    spool_sequence: int
    intent_id: str
    payload_sha256: str
    trace_id: str
    payload: Mapping[str, Any]
    target_date: str
    source: str
    vt_symbol: str
    position_epoch_id: str
    state_generation: str
    priority: int
    intent_kind: str
    state: str
    deadline_epoch_ns: int
    deadline_monotonic_ns: int
    clock_domain_id: str
    created_epoch_ns: int
    updated_epoch_ns: int
    state_revision: int
    lease_owner: str
    lease_token: str
    lease_expires_epoch_ns: int
    lease_expires_monotonic_ns: int
    lease_clock_domain_id: str
    attempt_count: int
    ledger_disposition: str
    last_error: str


@dataclass(frozen=True, slots=True)
class LeaseRecoveryEvidence:
    intent_id: str
    lease_owner: str
    lease_token: str
    ledger_disposition: str
    ledger_fingerprint: str
    ledger_watermark: int
    ledger_checksum_sha256: str


@dataclass(frozen=True, slots=True)
class DetectorFeedRolloverEvidence:
    previous_cursor: DurableTickCursor
    previous_journal_segment_path: str
    previous_heartbeat_revision_uuid: str
    previous_clean_shutdown: bool
    recovery_previous_durable_cursor: DurableTickCursor
    prior_uncommitted_gap_count: int
    new_feed_session_id: str
    new_journal_segment_path: str
    new_heartbeat_revision_uuid: str
    bridged_empty_feed_sessions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TraceObservation:
    epoch_ns: int
    monotonic_ns: int
    clock_domain_id: str


@dataclass(frozen=True, slots=True)
class IntentLease:
    intent: SpoolIntent
    lease_token: str


@dataclass(frozen=True, slots=True)
class CommitDetectorBatchResult:
    inserted_count: int
    idempotent_count: int
    cursor: DurableTickCursor
    idempotent_replay: bool = False


@dataclass(frozen=True, slots=True)
class ExpireDueResult:
    expired_open_count: int
    blocked_close_count: int


@dataclass(frozen=True, slots=True)
class AuthorizableIntentCandidate:
    intent_id: str
    payload_sha256: str
    intent_kind: str
    intent_role: str
    trace_id: str
    target_date: str
    source: str
    vt_symbol: str
    state_generation: str
    position_epoch_id: str
    root_position_id: str
    position_cycle_id: str
    spool_sequence: int
    state_revision: int
    deadline_epoch_ns: int
    deadline_monotonic_ns: int
    clock_domain_id: str
    ingress_epoch_ns: int


@dataclass(frozen=True, slots=True)
class AuthorizableIntentSnapshot:
    spool_uuid: str
    schema_version: str
    snapshot_digest: str
    cursor_digest: str
    candidate: AuthorizableIntentCandidate | None
    total_intent_count: int
    outstanding_close_count: int
    ready_close_count: int
    ready_open_count: int
    leased_count: int
    sending_count: int
    side_effect_unknown_count: int

    @property
    def inflight_count(self) -> int:
        return (
            self.leased_count
            + self.sending_count
            + self.side_effect_unknown_count
        )


@dataclass(frozen=True, slots=True)
class _ValidatedIntent:
    intent_id: str
    payload_sha256: str
    trace_id: str
    payload_json: str
    trace_json: str
    target_date: str
    source: str
    vt_symbol: str
    position_epoch_id: str
    state_generation: str
    source_feed_session_id: str
    source_ingress_sequence: int
    source_symbol_sequence: int
    durable_cursor_feed_session_id: str
    durable_cursor_ingress_sequence: int
    durable_cursor_journal_byte_offset: int
    durable_cursor_journal_schema: str
    priority: int
    intent_kind: str
    state: str
    deadline_epoch_ns: int
    deadline_monotonic_ns: int
    ingress_monotonic_ns: int
    clock_domain_id: str
    stage904_detected_json: str
    stage905_intent_ready_json: str
    initial_last_error: str


def _required_text(value: Any, *, field_name: str, max_bytes: int = 1024) -> str:
    if not isinstance(value, str):
        raise SpoolValidationError(f"{field_name}_must_be_text")
    normalized = value.strip()
    if not normalized:
        raise SpoolValidationError(f"{field_name}_must_not_be_empty")
    if any(ord(character) < 32 for character in normalized):
        raise SpoolValidationError(f"{field_name}_contains_control_character")
    if len(normalized.encode("utf-8")) > max_bytes:
        raise SpoolValidationError(f"{field_name}_too_long")
    return normalized


def _exact_int(value: Any, *, field_name: str, minimum: int = 0) -> int:
    if hasattr(value, "item") and not isinstance(value, (str, bytes, bytearray)):
        try:
            value = value.item()
        except (AttributeError, ValueError):
            pass
    if type(value) is not int or value < minimum:
        raise SpoolValidationError(
            f"{field_name}_must_be_exact_int_at_least_{minimum}"
        )
    if value > 9_223_372_036_854_775_807:
        raise SpoolValidationError(f"{field_name}_exceeds_sqlite_int64")
    return value


def _canonical_json_value(value: Any, *, field_name: str = "payload") -> Any:
    if value is None or isinstance(value, (str, bool)):
        return value
    if type(value) is int:
        return _exact_int(value, field_name=field_name)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SpoolValidationError(f"{field_name}_must_be_finite")
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise SpoolValidationError(f"{field_name}_key_must_be_text")
            result[key] = _canonical_json_value(
                item,
                field_name=f"{field_name}.{key}",
            )
        return result
    if isinstance(value, (list, tuple)):
        return [
            _canonical_json_value(item, field_name=f"{field_name}[]")
            for item in value
        ]
    if hasattr(value, "item"):
        try:
            scalar = value.item()
        except AttributeError:
            scalar = value
        if scalar is not value:
            return _canonical_json_value(scalar, field_name=field_name)
    raise SpoolValidationError(
        f"{field_name}_json_type_unsupported:{type(value).__name__}"
    )


def _strict_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SpoolValidationError(f"json_duplicate_member:{key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> Any:
    raise SpoolValidationError(f"json_nonfinite_number:{value}")


def _strict_json_loads(value: Any, *, field_name: str) -> dict[str, Any]:
    text = _required_text(value, field_name=field_name, max_bytes=4 * 1024 * 1024)
    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_strict_json_object,
            parse_constant=_reject_json_constant,
        )
    except SpoolValidationError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SpoolValidationError(f"{field_name}_invalid_json") from exc
    if not isinstance(parsed, dict):
        raise SpoolValidationError(f"{field_name}_must_be_object")
    return parsed


def _canonical_json_text(value: Mapping[str, Any], *, field_name: str) -> str:
    normalized = _canonical_json_value(value, field_name=field_name)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _validate_now_stamp(
    *,
    now_epoch_ns: Any,
    now_monotonic_ns: Any,
    clock_domain_id: Any,
) -> tuple[int, int, str]:
    return (
        _exact_int(now_epoch_ns, field_name="now_epoch_ns"),
        _exact_int(now_monotonic_ns, field_name="now_monotonic_ns"),
        _required_text(
            clock_domain_id,
            field_name="clock_domain_id",
            max_bytes=256,
        ),
    )


def _schema_contract_fingerprint(connection: sqlite3.Connection) -> str:
    objects = []
    for row in connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "WHERE sql IS NOT NULL AND (name IN ("
        "'spool_meta', 'detector_cursors', 'intents', "
        "'intents_claim_idx', 'intents_close_state_idx')) "
        "ORDER BY type, name"
    ):
        objects.append(
            {
                "type": row[0],
                "name": row[1],
                "table": row[2],
                "sql": " ".join(str(row[3]).split()),
            }
        )
    columns: dict[str, list[list[Any]]] = {}
    for table_name in ("spool_meta", "detector_cursors", "intents"):
        columns[table_name] = [
            [row[1], row[2], row[3], row[4], row[5]]
            for row in connection.execute(f"PRAGMA table_info({table_name})")
        ]
    encoded = json.dumps(
        {"objects": objects, "columns": columns},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_cursor(cursor: DurableTickCursor, *, field_name: str) -> DurableTickCursor:
    if not isinstance(cursor, DurableTickCursor):
        raise SpoolValidationError(f"{field_name}_must_be_durable_tick_cursor")
    feed_session_id = _required_text(
        cursor.feed_session_id,
        field_name=f"{field_name}_feed_session_id",
        max_bytes=256,
    )
    ingress_sequence = _exact_int(
        cursor.ingress_sequence,
        field_name=f"{field_name}_ingress_sequence",
        minimum=1,
    )
    journal_byte_offset = _exact_int(
        cursor.journal_byte_offset,
        field_name=f"{field_name}_journal_byte_offset",
    )
    if cursor.journal_schema != JOURNAL_SCHEMA_FRAMED_V1:
        raise SpoolValidationError(f"{field_name}_journal_schema_invalid")
    return DurableTickCursor(
        feed_session_id=feed_session_id,
        ingress_sequence=ingress_sequence,
        journal_byte_offset=journal_byte_offset,
        journal_schema=JOURNAL_SCHEMA_FRAMED_V1,
    )


@contextmanager
def _write_transaction(connection: sqlite3.Connection) -> Iterator[None]:
    try:
        connection.execute("BEGIN IMMEDIATE")
    except sqlite3.Error as exc:
        raise SpoolStorageError(
            f"spool_begin_immediate_failed:{getattr(exc, 'sqlite_errorname', type(exc).__name__)}"
        ) from exc
    try:
        yield
    except sqlite3.Error as exc:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise SpoolStorageError(
            f"spool_transaction_failed:{getattr(exc, 'sqlite_errorname', type(exc).__name__)}"
        ) from exc
    except BaseException:
        connection.execute("ROLLBACK")
        raise
    else:
        try:
            connection.execute("COMMIT")
        except sqlite3.Error as exc:
            try:
                connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise SpoolStorageError(
                f"spool_commit_failed:{getattr(exc, 'sqlite_errorname', type(exc).__name__)}"
            ) from exc


def open_spool(path: str | Path) -> sqlite3.Connection:
    spool_path = Path(path)
    spool_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(
        str(spool_path),
        timeout=0.1,
        isolation_level=None,
    )
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA busy_timeout=100")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        initialize_spool(connection)
    except BaseException:
        connection.close()
        raise
    return connection


def initialize_spool(connection: sqlite3.Connection) -> None:
    with _write_transaction(connection):
        user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if user_version not in (0, int(SCHEMA_VERSION)):
            raise SpoolValidationError(
                f"spool_user_version_mismatch:{user_version}!={SCHEMA_VERSION}"
            )
        if user_version == int(SCHEMA_VERSION):
            existing_fingerprint = _schema_contract_fingerprint(connection)
            if existing_fingerprint != EXPECTED_SCHEMA_FINGERPRINT:
                raise SpoolValidationError(
                    "spool_existing_schema_fingerprint_mismatch:"
                    f"{existing_fingerprint}!={EXPECTED_SCHEMA_FINGERPRINT}"
                )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS spool_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            ) WITHOUT ROWID
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS detector_cursors (
                consumer_id TEXT PRIMARY KEY,
                feed_session_id TEXT NOT NULL,
                ingress_sequence INTEGER NOT NULL CHECK (ingress_sequence >= 1),
                journal_byte_offset INTEGER NOT NULL CHECK (journal_byte_offset >= 0),
                journal_schema TEXT NOT NULL,
                cursor_revision INTEGER NOT NULL CHECK (cursor_revision >= 1),
                batch_manifest_sha256 TEXT NOT NULL,
                batch_intent_count INTEGER NOT NULL CHECK (batch_intent_count >= 0),
                updated_epoch_ns INTEGER NOT NULL CHECK (updated_epoch_ns >= 0)
            ) WITHOUT ROWID
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS intents (
                spool_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                intent_id TEXT NOT NULL UNIQUE,
                payload_sha256 TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                trace_json TEXT NOT NULL,
                target_date TEXT NOT NULL,
                source TEXT NOT NULL,
                vt_symbol TEXT NOT NULL,
                position_epoch_id TEXT NOT NULL,
                state_generation TEXT NOT NULL,
                source_feed_session_id TEXT NOT NULL,
                source_ingress_sequence INTEGER NOT NULL CHECK (source_ingress_sequence >= 1),
                source_symbol_sequence INTEGER NOT NULL CHECK (source_symbol_sequence >= 1),
                durable_cursor_feed_session_id TEXT NOT NULL,
                durable_cursor_ingress_sequence INTEGER NOT NULL CHECK (durable_cursor_ingress_sequence >= 1),
                durable_cursor_journal_byte_offset INTEGER NOT NULL CHECK (durable_cursor_journal_byte_offset >= 0),
                durable_cursor_journal_schema TEXT NOT NULL,
                priority INTEGER NOT NULL CHECK (priority IN (0, 1)),
                intent_kind TEXT NOT NULL CHECK (intent_kind IN ('open', 'close')),
                state TEXT NOT NULL CHECK (
                    state IN (
                        'ready', 'leased', 'sending', 'side_effect_unknown',
                        'sent', 'reconciled', 'expired', 'blocked'
                    )
                ),
                deadline_epoch_ns INTEGER NOT NULL CHECK (deadline_epoch_ns >= 0),
                deadline_monotonic_ns INTEGER NOT NULL CHECK (deadline_monotonic_ns >= 0),
                ingress_monotonic_ns INTEGER NOT NULL CHECK (ingress_monotonic_ns >= 0),
                clock_domain_id TEXT NOT NULL,
                created_epoch_ns INTEGER NOT NULL CHECK (created_epoch_ns >= 0),
                updated_epoch_ns INTEGER NOT NULL CHECK (updated_epoch_ns >= 0),
                state_revision INTEGER NOT NULL DEFAULT 0 CHECK (state_revision >= 0),
                lease_owner TEXT NOT NULL DEFAULT '',
                lease_token TEXT NOT NULL DEFAULT '',
                lease_expires_epoch_ns INTEGER NOT NULL DEFAULT 0 CHECK (lease_expires_epoch_ns >= 0),
                lease_expires_monotonic_ns INTEGER NOT NULL DEFAULT 0 CHECK (lease_expires_monotonic_ns >= 0),
                lease_clock_domain_id TEXT NOT NULL DEFAULT '',
                attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
                ledger_disposition TEXT NOT NULL DEFAULT '',
                recovery_evidence_json TEXT NOT NULL DEFAULT '',
                stage904_detected_json TEXT NOT NULL DEFAULT '',
                stage905_intent_ready_json TEXT NOT NULL DEFAULT '',
                spool_committed_json TEXT NOT NULL DEFAULT '',
                executor_dequeued_json TEXT NOT NULL DEFAULT '',
                last_error TEXT NOT NULL DEFAULT ''
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS intents_claim_idx "
            "ON intents(state, priority, spool_sequence)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS intents_close_state_idx "
            "ON intents(intent_kind, state)"
        )
        actual_schema_fingerprint = _schema_contract_fingerprint(connection)
        if (
            EXPECTED_SCHEMA_FINGERPRINT
            and actual_schema_fingerprint != EXPECTED_SCHEMA_FINGERPRINT
        ):
            raise SpoolValidationError(
                "spool_schema_fingerprint_mismatch:"
                f"{actual_schema_fingerprint}!={EXPECTED_SCHEMA_FINGERPRINT}"
            )
        existing = connection.execute(
            "SELECT value FROM spool_meta WHERE key='schema_version'"
        ).fetchone()
        if existing is not None and existing[0] != SCHEMA_VERSION:
            raise SpoolValidationError(
                f"spool_schema_version_mismatch:{existing[0]}!={SCHEMA_VERSION}"
            )
        connection.execute(
            "INSERT OR IGNORE INTO spool_meta(key, value) VALUES('schema_version', ?)",
            (SCHEMA_VERSION,),
        )
        connection.execute(
            "INSERT OR IGNORE INTO spool_meta(key, value) VALUES('spool_uuid', ?)",
            (str(uuid.uuid4()),),
        )
        connection.execute(
            "INSERT OR IGNORE INTO spool_meta(key, value) VALUES('created_epoch_ns', '0')"
        )
        connection.execute(
            "INSERT OR IGNORE INTO spool_meta(key, value) "
            "VALUES('schema_fingerprint', ?)",
            (actual_schema_fingerprint,),
        )
        connection.execute(
            "UPDATE spool_meta SET value=? WHERE key='created_epoch_ns' AND value='0'",
            (str(time.time_ns()),),
        )
        for table_name, required_columns in _REQUIRED_SCHEMA_COLUMNS.items():
            actual_columns = {
                row[1]
                for row in connection.execute(f"PRAGMA table_info({table_name})")
            }
            missing = required_columns - actual_columns
            if missing:
                raise SpoolValidationError(
                    f"spool_schema_columns_missing:{table_name}:{sorted(missing)}"
                )
        metadata = dict(connection.execute("SELECT key, value FROM spool_meta"))
        expected_meta_keys = {
            "schema_version",
            "spool_uuid",
            "created_epoch_ns",
            "schema_fingerprint",
        }
        if set(metadata) != expected_meta_keys:
            raise SpoolValidationError("spool_meta_keys_invalid")
        try:
            parsed_uuid = str(uuid.UUID(metadata["spool_uuid"]))
        except (ValueError, AttributeError) as exc:
            raise SpoolValidationError("spool_uuid_invalid") from exc
        if parsed_uuid != metadata["spool_uuid"]:
            raise SpoolValidationError("spool_uuid_not_canonical")
        created_text = metadata["created_epoch_ns"]
        if re.fullmatch(r"[1-9][0-9]*", created_text) is None:
            raise SpoolValidationError("spool_created_epoch_ns_invalid")
        if metadata["schema_fingerprint"] != actual_schema_fingerprint:
            raise SpoolValidationError("spool_meta_schema_fingerprint_mismatch")
        connection.execute(f"PRAGMA user_version={int(SCHEMA_VERSION)}")


def _read_detector_cursor_locked(
    connection: sqlite3.Connection,
    *,
    consumer_id: str,
) -> DurableTickCursor | None:
    row = connection.execute(
        "SELECT feed_session_id, ingress_sequence, journal_byte_offset, journal_schema "
        "FROM detector_cursors WHERE consumer_id=?",
        (consumer_id,),
    ).fetchone()
    if row is None:
        return None
    return DurableTickCursor(
        feed_session_id=row["feed_session_id"],
        ingress_sequence=row["ingress_sequence"],
        journal_byte_offset=row["journal_byte_offset"],
        journal_schema=row["journal_schema"],
    )


def read_detector_cursor(
    connection: sqlite3.Connection,
    *,
    consumer_id: str,
) -> DurableTickCursor | None:
    normalized_consumer = _required_text(
        consumer_id,
        field_name="consumer_id",
        max_bytes=256,
    )
    return _read_detector_cursor_locked(
        connection,
        consumer_id=normalized_consumer,
    )


def _validated_intent_payload(
    payload: Mapping[str, Any],
    *,
    now_epoch_ns: int,
    now_monotonic_ns: int,
    clock_domain_id: str,
) -> _ValidatedIntent:
    if not isinstance(payload, Mapping):
        raise SpoolValidationError("intent_payload_must_be_mapping")
    spool_payload = _strict_json_loads(
        payload.get("spool_payload_json"),
        field_name="spool_payload_json",
    )
    forbidden_business_fields = {
        "trace_json",
        "spool_payload_json",
        "payload_sha256",
    } & set(spool_payload)
    if forbidden_business_fields:
        raise SpoolValidationError(
            f"spool_payload_contains_volatile_fields:{sorted(forbidden_business_fields)}"
        )
    payload_json = _canonical_json_text(spool_payload, field_name="spool_payload")
    if payload.get("spool_payload_json") != payload_json:
        raise SpoolValidationError("spool_payload_json_not_canonical")
    intent_id = _required_text(
        spool_payload.get("intent_id"),
        field_name="intent_id",
        max_bytes=512,
    )
    if payload.get("intent_id") != intent_id:
        raise SpoolValidationError("intent_id_outer_payload_mismatch")
    payload_sha256 = _required_text(
        payload.get("payload_sha256"),
        field_name="payload_sha256",
        max_bytes=64,
    )
    if _SHA256_RE.fullmatch(payload_sha256) is None:
        raise SpoolValidationError("payload_sha256_invalid")
    recomputed_sha256 = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    if payload_sha256 != recomputed_sha256:
        raise SpoolValidationError("payload_sha256_recompute_mismatch")
    trace_id = _required_text(
        spool_payload.get("trace_id"),
        field_name="trace_id",
        max_bytes=512,
    )
    if payload.get("trace_id") != trace_id:
        raise SpoolValidationError("trace_id_outer_payload_mismatch")
    trace_json = _required_text(
        payload.get("trace_json"),
        field_name="trace_json",
        max_bytes=4 * 1024 * 1024,
    )
    try:
        trace = LatencyTrace.from_json(trace_json)
    except TraceValidationError as exc:
        raise SpoolValidationError(f"trace_json_invalid:{exc}") from exc
    if trace.trace_id != trace_id:
        raise SpoolValidationError("trace_id_trace_json_mismatch")
    target_date = _required_text(
        spool_payload.get("target_date"),
        field_name="target_date",
        max_bytes=32,
    )
    source = _required_text(
        spool_payload.get("source"),
        field_name="source",
        max_bytes=256,
    )
    vt_symbol = _required_text(
        spool_payload.get("vt_symbol"),
        field_name="vt_symbol",
        max_bytes=128,
    )
    if vt_symbol != trace.vt_symbol:
        raise SpoolValidationError("intent_vt_symbol_trace_mismatch")
    intent_kind = _required_text(
        spool_payload.get("offset"),
        field_name="offset",
        max_bytes=16,
    ).lower()
    if intent_kind not in {"open", "close"}:
        raise SpoolValidationError("intent_offset_invalid")
    executor_status = _required_text(
        spool_payload.get("executor_status"),
        field_name="executor_status",
        max_bytes=128,
    )
    state_by_status = {
        "dry_run_order_request_payload_ready": "ready",
        "expired": "expired",
        "blocked": "blocked",
    }
    if executor_status not in state_by_status:
        raise SpoolValidationError("executor_status_not_spoolable")
    deadline_epoch_ns = _exact_int(
        spool_payload.get("deadline_epoch_ns"),
        field_name="deadline_epoch_ns",
    )
    deadline_monotonic_ns = _exact_int(
        spool_payload.get("deadline_monotonic_ns"),
        field_name="deadline_monotonic_ns",
    )
    if (
        deadline_epoch_ns != trace.deadline_epoch_ns
        or deadline_monotonic_ns != trace.deadline_monotonic_ns
    ):
        raise SpoolValidationError("intent_deadline_trace_mismatch")
    ingress_stamp = trace.stamps.get("gateway_ingress")
    if ingress_stamp is None:
        raise SpoolValidationError("trace_gateway_ingress_missing")
    deadline_domain_mismatch = clock_domain_id != ingress_stamp.clock_domain_id
    deadline_monotonic_rollback = (
        not deadline_domain_mismatch
        and now_monotonic_ns < ingress_stamp.monotonic_ns
    )
    deadline_due = (
        deadline_domain_mismatch
        or deadline_monotonic_rollback
        or now_epoch_ns >= deadline_epoch_ns
        or now_monotonic_ns >= deadline_monotonic_ns
    )
    priority = 0 if intent_kind == "close" else 1
    state = state_by_status[executor_status]
    initial_last_error = ""
    if state == "ready" and deadline_due:
        state = "blocked" if intent_kind == "close" else "expired"
        initial_last_error = (
            "detector_deadline_clock_domain_mismatch"
            if deadline_domain_mismatch
            else "detector_deadline_monotonic_rollback"
            if deadline_monotonic_rollback
            else "detector_deadline_expired_close_critical"
            if intent_kind == "close"
            else "detector_deadline_expired_open"
        )
    elif state == "blocked":
        initial_last_error = "detector_executor_blocked_zero_native"
    elif state == "expired":
        initial_last_error = "detector_executor_expired_zero_native"
    state_generation = _required_text(
        spool_payload.get("state_generation"),
        field_name="state_generation",
        max_bytes=512,
    )
    position_epoch_id = _required_text(
        spool_payload.get("position_epoch_id"),
        field_name="position_epoch_id",
        max_bytes=512,
    )
    generation_prefix = f"{position_epoch_id}:"
    if not state_generation.startswith(generation_prefix):
        raise SpoolValidationError("state_generation_position_epoch_mismatch")
    generation_revision = state_generation[len(generation_prefix) :]
    if (
        re.fullmatch(r"0|[1-9][0-9]*", generation_revision) is None
        or (len(generation_revision) > 1 and generation_revision.startswith("0"))
    ):
        raise SpoolValidationError("state_generation_revision_not_canonical")
    source_feed_session_id = _required_text(
        spool_payload.get("source_feed_session_id"),
        field_name="source_feed_session_id",
        max_bytes=256,
    )
    source_ingress_sequence = _exact_int(
        spool_payload.get("source_ingress_sequence"),
        field_name="source_ingress_sequence",
        minimum=1,
    )
    source_symbol_sequence = _exact_int(
        spool_payload.get("source_symbol_sequence"),
        field_name="source_symbol_sequence",
        minimum=1,
    )
    if (
        source_feed_session_id != trace.feed_session_id
        or source_ingress_sequence != trace.ingress_sequence
        or source_symbol_sequence != trace.symbol_sequence
    ):
        raise SpoolValidationError("intent_source_trace_mismatch")
    durable_cursor_feed_session_id = _required_text(
        spool_payload.get("durable_cursor_feed_session_id"),
        field_name="durable_cursor_feed_session_id",
        max_bytes=256,
    )
    durable_cursor_ingress_sequence = _exact_int(
        spool_payload.get("durable_cursor_ingress_sequence"),
        field_name="durable_cursor_ingress_sequence",
        minimum=1,
    )
    durable_cursor_journal_byte_offset = _exact_int(
        spool_payload.get("durable_cursor_journal_byte_offset"),
        field_name="durable_cursor_journal_byte_offset",
    )
    durable_cursor_journal_schema = _required_text(
        spool_payload.get("durable_cursor_journal_schema"),
        field_name="durable_cursor_journal_schema",
        max_bytes=128,
    )
    if durable_cursor_journal_schema != JOURNAL_SCHEMA_FRAMED_V1:
        raise SpoolValidationError("durable_cursor_journal_schema_invalid")
    if durable_cursor_ingress_sequence < source_ingress_sequence:
        raise SpoolValidationError("durable_cursor_does_not_cover_source_sequence")
    stage904_stamp = trace.stamps.get("stage904_detected")
    stage905_stamp = trace.stamps.get("stage905_intent_ready")
    if stage904_stamp is None or stage905_stamp is None:
        raise SpoolValidationError("trace_stage904_stage905_stamps_missing")
    stage904_json = _canonical_json_text(
        {
            "epoch_ns": stage904_stamp.epoch_ns,
            "monotonic_ns": stage904_stamp.monotonic_ns,
            "clock_domain_id": stage904_stamp.clock_domain_id,
        },
        field_name="stage904_detected",
    )
    stage905_json = _canonical_json_text(
        {
            "epoch_ns": stage905_stamp.epoch_ns,
            "monotonic_ns": stage905_stamp.monotonic_ns,
            "clock_domain_id": stage905_stamp.clock_domain_id,
        },
        field_name="stage905_intent_ready",
    )
    return _ValidatedIntent(
        intent_id=intent_id,
        payload_sha256=payload_sha256,
        trace_id=trace_id,
        payload_json=payload_json,
        trace_json=trace_json,
        target_date=target_date,
        source=source,
        vt_symbol=vt_symbol,
        position_epoch_id=position_epoch_id,
        state_generation=state_generation,
        source_feed_session_id=source_feed_session_id,
        source_ingress_sequence=source_ingress_sequence,
        source_symbol_sequence=source_symbol_sequence,
        durable_cursor_feed_session_id=durable_cursor_feed_session_id,
        durable_cursor_ingress_sequence=durable_cursor_ingress_sequence,
        durable_cursor_journal_byte_offset=durable_cursor_journal_byte_offset,
        durable_cursor_journal_schema=durable_cursor_journal_schema,
        priority=priority,
        intent_kind=intent_kind,
        state=state,
        deadline_epoch_ns=deadline_epoch_ns,
        deadline_monotonic_ns=deadline_monotonic_ns,
        ingress_monotonic_ns=ingress_stamp.monotonic_ns,
        clock_domain_id=ingress_stamp.clock_domain_id,
        stage904_detected_json=stage904_json,
        stage905_intent_ready_json=stage905_json,
        initial_last_error=initial_last_error,
    )


def _close_business_action_id(payload_json: str) -> str:
    payload = _strict_json_loads(
        payload_json,
        field_name="close_delivery_payload_json",
    )
    action_id = _required_text(
        payload.get("action_id"),
        field_name="close_delivery_business_action_id",
        max_bytes=512,
    )
    explicit = payload.get("business_action_id")
    if explicit is not None and _required_text(
        explicit,
        field_name="close_delivery_explicit_business_action_id",
        max_bytes=512,
    ) != action_id:
        raise SpoolValidationError("close_delivery_business_action_id_mismatch")
    return action_id


def _close_delivery_rows_locked(
    connection: sqlite3.Connection,
    *,
    business_action_id: str,
) -> list[sqlite3.Row]:
    rows: list[sqlite3.Row] = []
    for row in connection.execute(
        "SELECT * FROM intents WHERE intent_kind='close' "
        "AND source='stage904_c9_intraday_close' ORDER BY spool_sequence"
    ).fetchall():
        _row_to_intent(row)
        if _close_business_action_id(row["payload_json"]) == business_action_id:
            rows.append(row)
    return rows


def _blocked_close_has_safe_zero_native_proof(row: sqlite3.Row) -> bool:
    if row["state"] != "blocked":
        return False
    attempt_count = _exact_int(
        row["attempt_count"],
        field_name="close_delivery_attempt_count",
    )
    ledger_disposition = str(row["ledger_disposition"] or "").strip()
    last_error = str(row["last_error"] or "").strip()
    if attempt_count == 0 and not ledger_disposition:
        return True
    return bool(
        last_error in _SAFE_ZERO_NATIVE_CLOSE_BLOCK_ERRORS
        and ledger_disposition in _SAFE_ZERO_NATIVE_LEDGER_DISPOSITIONS
    )


def inspect_close_delivery_candidate(
    connection: sqlite3.Connection,
    *,
    business_action_id: str,
    candidate_intent_id: str,
) -> str:
    """Classify one delivery without weakening the stable business close latch."""

    normalized_action_id = _required_text(
        business_action_id,
        field_name="close_delivery_business_action_id",
        max_bytes=512,
    )
    normalized_candidate = _required_text(
        candidate_intent_id,
        field_name="close_delivery_candidate_intent_id",
        max_bytes=512,
    )
    rows = _close_delivery_rows_locked(
        connection,
        business_action_id=normalized_action_id,
    )
    exact = [row for row in rows if row["intent_id"] == normalized_candidate]
    if exact:
        if len(exact) != 1:
            raise SpoolValidationError("close_delivery_candidate_identity_duplicate")
        return "idempotent_delivery"
    collision = connection.execute(
        "SELECT 1 FROM intents WHERE intent_id=?",
        (normalized_candidate,),
    ).fetchone()
    if collision is not None:
        raise SpoolConflictError("close_delivery_candidate_intent_id_collision")
    if not rows:
        return "first_delivery"
    if any(row["state"] in _CLOSE_DELIVERY_ACTIVE_STATES for row in rows):
        return "existing_delivery_active_or_terminal"
    latest = rows[-1]
    if _blocked_close_has_safe_zero_native_proof(latest):
        return "safe_zero_native_rearm"
    return "existing_delivery_not_rearmable"


def commit_detector_batch(
    connection: sqlite3.Connection,
    *,
    consumer_id: str,
    expected_cursor: DurableTickCursor | None,
    next_cursor: DurableTickCursor,
    intents: Sequence[Mapping[str, Any]],
    now_epoch_ns: int,
    now_monotonic_ns: int,
    clock_domain_id: str,
    feed_rollover_evidence: DetectorFeedRolloverEvidence | None = None,
) -> CommitDetectorBatchResult:
    normalized_consumer = _required_text(
        consumer_id,
        field_name="consumer_id",
        max_bytes=256,
    )
    normalized_expected = (
        _validate_cursor(expected_cursor, field_name="expected_cursor")
        if expected_cursor is not None
        else None
    )
    normalized_next = _validate_cursor(next_cursor, field_name="next_cursor")
    normalized_now, normalized_monotonic, normalized_domain = _validate_now_stamp(
        now_epoch_ns=now_epoch_ns,
        now_monotonic_ns=now_monotonic_ns,
        clock_domain_id=clock_domain_id,
    )
    rollover_json = ""
    rollover_sha256 = ""
    if feed_rollover_evidence is not None:
        if not isinstance(feed_rollover_evidence, DetectorFeedRolloverEvidence):
            raise SpoolValidationError("feed_rollover_evidence_type_invalid")
        if normalized_expected is None:
            raise DetectorCursorConflictError("feed_rollover_expected_cursor_missing")
        previous_cursor = _validate_cursor(
            feed_rollover_evidence.previous_cursor,
            field_name="feed_rollover_previous_cursor",
        )
        recovered_cursor = _validate_cursor(
            feed_rollover_evidence.recovery_previous_durable_cursor,
            field_name="feed_rollover_recovery_previous_durable_cursor",
        )
        previous_path = _required_text(
            feed_rollover_evidence.previous_journal_segment_path,
            field_name="feed_rollover_previous_journal_segment_path",
            max_bytes=4096,
        )
        previous_revision = _required_text(
            feed_rollover_evidence.previous_heartbeat_revision_uuid,
            field_name="feed_rollover_previous_heartbeat_revision_uuid",
            max_bytes=256,
        )
        new_feed = _required_text(
            feed_rollover_evidence.new_feed_session_id,
            field_name="feed_rollover_new_feed_session_id",
            max_bytes=256,
        )
        new_path = _required_text(
            feed_rollover_evidence.new_journal_segment_path,
            field_name="feed_rollover_new_journal_segment_path",
            max_bytes=4096,
        )
        new_revision = _required_text(
            feed_rollover_evidence.new_heartbeat_revision_uuid,
            field_name="feed_rollover_new_heartbeat_revision_uuid",
            max_bytes=256,
        )
        gap_count = _exact_int(
            feed_rollover_evidence.prior_uncommitted_gap_count,
            field_name="feed_rollover_prior_uncommitted_gap_count",
        )
        if feed_rollover_evidence.previous_clean_shutdown is not True:
            raise DetectorCursorConflictError("feed_rollover_previous_not_clean")
        if gap_count != 0:
            raise DetectorCursorConflictError("feed_rollover_prior_gap_present")
        if previous_cursor != normalized_expected:
            raise DetectorCursorConflictError(
                "feed_rollover_previous_cursor_expected_mismatch"
            )
        if recovered_cursor != previous_cursor:
            raise DetectorCursorConflictError(
                "feed_rollover_previous_cursor_not_caught_up"
            )
        if new_feed != normalized_next.feed_session_id:
            raise DetectorCursorConflictError("feed_rollover_new_feed_mismatch")
        if new_feed == previous_cursor.feed_session_id:
            raise DetectorCursorConflictError("feed_rollover_feed_not_changed")
        if new_path == previous_path:
            raise DetectorCursorConflictError("feed_rollover_segment_not_changed")
        bridged_empty_feeds = feed_rollover_evidence.bridged_empty_feed_sessions
        if type(bridged_empty_feeds) is not tuple or len(bridged_empty_feeds) > 64:
            raise SpoolValidationError("feed_rollover_empty_feed_lineage_invalid")
        normalized_empty_feeds: list[str] = []
        for feed in bridged_empty_feeds:
            normalized_feed = _required_text(
                feed,
                field_name="feed_rollover_bridged_empty_feed_session_id",
                max_bytes=256,
            )
            if (
                normalized_feed in {previous_cursor.feed_session_id, new_feed}
                or normalized_feed in normalized_empty_feeds
            ):
                raise DetectorCursorConflictError(
                    "feed_rollover_empty_feed_lineage_conflict"
                )
            normalized_empty_feeds.append(normalized_feed)
        rollover_json = _canonical_json_text(
            {
                "previous_cursor": {
                    "feed_session_id": previous_cursor.feed_session_id,
                    "ingress_sequence": previous_cursor.ingress_sequence,
                    "journal_byte_offset": previous_cursor.journal_byte_offset,
                    "journal_schema": previous_cursor.journal_schema,
                },
                "previous_journal_segment_path": previous_path,
                "previous_heartbeat_revision_uuid": previous_revision,
                "previous_clean_shutdown": True,
                "recovery_previous_durable_cursor": {
                    "feed_session_id": recovered_cursor.feed_session_id,
                    "ingress_sequence": recovered_cursor.ingress_sequence,
                    "journal_byte_offset": recovered_cursor.journal_byte_offset,
                    "journal_schema": recovered_cursor.journal_schema,
                },
                "prior_uncommitted_gap_count": gap_count,
                "new_feed_session_id": new_feed,
                "new_journal_segment_path": new_path,
                "new_heartbeat_revision_uuid": new_revision,
                "bridged_empty_feed_sessions": normalized_empty_feeds,
            },
            field_name="feed_rollover_evidence",
        )
        rollover_sha256 = hashlib.sha256(rollover_json.encode("utf-8")).hexdigest()
    if isinstance(intents, (str, bytes, bytearray)) or not isinstance(intents, Sequence):
        raise SpoolValidationError("intents_must_be_sequence")

    prepared = [
        _validated_intent_payload(
            raw_payload,
            now_epoch_ns=normalized_now,
            now_monotonic_ns=normalized_monotonic,
            clock_domain_id=normalized_domain,
        )
        for raw_payload in intents
    ]
    for item in prepared:
        if item.source == "stage904_c9_intraday_close":
            if item.intent_kind != "close":
                raise SpoolValidationError("close_delivery_intent_kind_mismatch")
            _close_business_action_id(item.payload_json)
        if item.durable_cursor_feed_session_id != normalized_next.feed_session_id:
            raise DetectorCursorConflictError(
                f"intent_cursor_feed_mismatch:{item.intent_id}"
            )
        if (
            item.durable_cursor_ingress_sequence > normalized_next.ingress_sequence
            or item.durable_cursor_journal_byte_offset
            > normalized_next.journal_byte_offset
        ):
            raise DetectorCursorConflictError(
                f"intent_cursor_not_covered_by_batch:{item.intent_id}"
            )
    if len({item.intent_id for item in prepared}) != len(prepared):
        raise SpoolConflictError("duplicate_intent_id_within_batch")
    manifest_payload = [
        {
            "intent_id": item.intent_id,
            "payload_sha256": item.payload_sha256,
            "trace_id": item.trace_id,
            "payload_json": item.payload_json,
        }
        for item in sorted(prepared, key=lambda candidate: candidate.intent_id)
    ]
    manifest_json = json.dumps(
        manifest_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    batch_manifest_sha256 = hashlib.sha256(
        manifest_json.encode("utf-8")
    ).hexdigest()

    def assert_existing_identical(item: _ValidatedIntent) -> bool:
        existing = connection.execute(
            "SELECT * FROM intents WHERE intent_id=?",
            (item.intent_id,),
        ).fetchone()
        if existing is None:
            return False
        _row_to_intent(existing)
        if (
            existing["payload_sha256"] != item.payload_sha256
            or existing["trace_id"] != item.trace_id
            or existing["payload_json"] != item.payload_json
        ):
            raise SpoolConflictError(f"intent_replay_conflict:{item.intent_id}")
        try:
            stored_trace = LatencyTrace.from_json(existing["trace_json"])
            replay_trace = LatencyTrace.from_json(item.trace_json)
        except TraceValidationError as exc:
            raise SpoolConflictError(
                f"intent_replay_stored_trace_invalid:{item.intent_id}"
            ) from exc
        if stored_trace.trace_id != item.trace_id:
            raise SpoolConflictError(
                f"intent_replay_stored_trace_mismatch:{item.intent_id}"
            )
        volatile_stages = {
            "stage904_detected",
            "stage905_intent_ready",
            "spool_committed",
            "executor_dequeued",
        }
        stored_material = stored_trace.to_dict()
        replay_material = replay_trace.to_dict()
        stored_material["stamps"] = {
            key: value
            for key, value in stored_material["stamps"].items()
            if key not in volatile_stages
        }
        replay_material["stamps"] = {
            key: value
            for key, value in replay_material["stamps"].items()
            if key not in volatile_stages
        }
        if stored_material != replay_material:
            raise SpoolConflictError(
                f"intent_replay_trace_immutable_material_mismatch:{item.intent_id}"
            )
        return True

    inserted_count = 0
    idempotent_count = 0
    idempotent_replay = False
    with _write_transaction(connection):
        if feed_rollover_evidence is not None:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS detector_feed_rollovers (
                    consumer_id TEXT NOT NULL,
                    previous_feed_session_id TEXT NOT NULL,
                    previous_ingress_sequence INTEGER NOT NULL,
                    previous_journal_byte_offset INTEGER NOT NULL,
                    new_feed_session_id TEXT NOT NULL,
                    new_ingress_sequence INTEGER NOT NULL,
                    new_journal_byte_offset INTEGER NOT NULL,
                    evidence_json TEXT NOT NULL,
                    evidence_sha256 TEXT NOT NULL,
                    created_epoch_ns INTEGER NOT NULL,
                    PRIMARY KEY (consumer_id, new_feed_session_id)
                ) WITHOUT ROWID
                """
            )
        current = _read_detector_cursor_locked(
            connection,
            consumer_id=normalized_consumer,
        )
        cursor_metadata = connection.execute(
            "SELECT cursor_revision, batch_manifest_sha256, batch_intent_count "
            "FROM detector_cursors WHERE consumer_id=?",
            (normalized_consumer,),
        ).fetchone()
        if current != normalized_expected and current == normalized_next:
            if (
                cursor_metadata is None
                or cursor_metadata["batch_manifest_sha256"]
                != batch_manifest_sha256
                or cursor_metadata["batch_intent_count"] != len(prepared)
            ):
                raise DetectorCursorConflictError(
                    "detector_cursor_lost_ack_manifest_mismatch"
                )
            if not all(assert_existing_identical(item) for item in prepared):
                raise DetectorCursorConflictError(
                    "detector_cursor_lost_ack_replay_missing_intent"
                )
            if feed_rollover_evidence is not None:
                stored_rollover = connection.execute(
                    "SELECT evidence_sha256 FROM detector_feed_rollovers "
                    "WHERE consumer_id=? AND new_feed_session_id=?",
                    (normalized_consumer, normalized_next.feed_session_id),
                ).fetchone()
                if (
                    stored_rollover is None
                    or stored_rollover["evidence_sha256"] != rollover_sha256
                ):
                    raise DetectorCursorConflictError(
                        "detector_cursor_lost_ack_rollover_evidence_mismatch"
                    )
            idempotent_count = len(prepared)
            idempotent_replay = True
        elif current != normalized_expected:
            raise DetectorCursorConflictError(
                f"detector_cursor_cas_mismatch:expected={normalized_expected};actual={current}"
            )
        if idempotent_replay:
            pass
        elif current is not None:
            if normalized_next.feed_session_id != current.feed_session_id:
                if feed_rollover_evidence is None:
                    raise DetectorCursorConflictError(
                        "detector_cursor_feed_session_changed"
                    )
            elif feed_rollover_evidence is not None:
                raise DetectorCursorConflictError("feed_rollover_not_required")
            elif (
                normalized_next.ingress_sequence <= current.ingress_sequence
                or normalized_next.journal_byte_offset
                <= current.journal_byte_offset
            ):
                raise DetectorCursorConflictError("detector_cursor_regression")

        if not idempotent_replay:
            for item in prepared:
                if assert_existing_identical(item):
                    idempotent_count += 1
                    continue
                if item.source == "stage904_c9_intraday_close":
                    business_action_id = _close_business_action_id(
                        item.payload_json
                    )
                    delivery_disposition = inspect_close_delivery_candidate(
                        connection,
                        business_action_id=business_action_id,
                        candidate_intent_id=item.intent_id,
                    )
                    if delivery_disposition == "safe_zero_native_rearm":
                        if item.state != "ready":
                            raise SpoolConflictError(
                                "close_delivery_rearm_requires_fresh_ready_authorization"
                            )
                        prior_rows = _close_delivery_rows_locked(
                            connection,
                            business_action_id=business_action_id,
                        )
                        prior = prior_rows[-1]
                        prior_error = str(prior["last_error"] or "").strip()
                        changed = connection.execute(
                            "UPDATE intents SET state='expired', updated_epoch_ns=?, "
                            "last_error=?, state_revision=state_revision+1 "
                            "WHERE intent_id=? AND state='blocked' AND state_revision=?",
                            (
                                normalized_now,
                                "close_delivery_rearmed_after_safe_zero_native_expiry:"
                                + (prior_error or "no_prior_error"),
                                prior["intent_id"],
                                prior["state_revision"],
                            ),
                        ).rowcount
                        if changed != 1:
                            raise SpoolConflictError(
                                "close_delivery_rearm_prior_state_cas_lost"
                            )
                    elif delivery_disposition != "first_delivery":
                        raise SpoolConflictError(
                            "close_delivery_business_action_not_rearmable:"
                            f"{delivery_disposition}"
                        )
                connection.execute(
                    """
                    INSERT INTO intents(
                        intent_id, payload_sha256, trace_id, payload_json, trace_json,
                        target_date, source, vt_symbol, position_epoch_id,
                        state_generation, source_feed_session_id,
                        source_ingress_sequence, source_symbol_sequence,
                        durable_cursor_feed_session_id,
                        durable_cursor_ingress_sequence,
                        durable_cursor_journal_byte_offset,
                        durable_cursor_journal_schema,
                        priority, intent_kind, state,
                        deadline_epoch_ns, deadline_monotonic_ns,
                        ingress_monotonic_ns, clock_domain_id,
                        created_epoch_ns, updated_epoch_ns,
                        stage904_detected_json, stage905_intent_ready_json,
                        last_error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.intent_id,
                        item.payload_sha256,
                        item.trace_id,
                        item.payload_json,
                        item.trace_json,
                        item.target_date,
                        item.source,
                        item.vt_symbol,
                        item.position_epoch_id,
                        item.state_generation,
                        item.source_feed_session_id,
                        item.source_ingress_sequence,
                        item.source_symbol_sequence,
                        item.durable_cursor_feed_session_id,
                        item.durable_cursor_ingress_sequence,
                        item.durable_cursor_journal_byte_offset,
                        item.durable_cursor_journal_schema,
                        item.priority,
                        item.intent_kind,
                        item.state,
                        item.deadline_epoch_ns,
                        item.deadline_monotonic_ns,
                        item.ingress_monotonic_ns,
                        item.clock_domain_id,
                        normalized_now,
                        normalized_now,
                        item.stage904_detected_json,
                        item.stage905_intent_ready_json,
                        item.initial_last_error,
                    ),
                )
                inserted_count += 1

            if feed_rollover_evidence is not None:
                existing_rollover = connection.execute(
                    "SELECT evidence_sha256 FROM detector_feed_rollovers "
                    "WHERE consumer_id=? AND new_feed_session_id=?",
                    (normalized_consumer, normalized_next.feed_session_id),
                ).fetchone()
                if existing_rollover is None:
                    connection.execute(
                        """
                        INSERT INTO detector_feed_rollovers(
                            consumer_id, previous_feed_session_id,
                            previous_ingress_sequence,
                            previous_journal_byte_offset,
                            new_feed_session_id, new_ingress_sequence,
                            new_journal_byte_offset, evidence_json,
                            evidence_sha256, created_epoch_ns
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            normalized_consumer,
                            normalized_expected.feed_session_id,
                            normalized_expected.ingress_sequence,
                            normalized_expected.journal_byte_offset,
                            normalized_next.feed_session_id,
                            normalized_next.ingress_sequence,
                            normalized_next.journal_byte_offset,
                            rollover_json,
                            rollover_sha256,
                            normalized_now,
                        ),
                    )
                elif existing_rollover["evidence_sha256"] != rollover_sha256:
                    raise DetectorCursorConflictError(
                        "feed_rollover_evidence_conflict"
                    )

            if cursor_metadata is None:
                connection.execute(
                    """
                    INSERT INTO detector_cursors(
                        consumer_id, feed_session_id, ingress_sequence,
                        journal_byte_offset, journal_schema, cursor_revision,
                        batch_manifest_sha256, batch_intent_count, updated_epoch_ns
                    ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
                    """,
                    (
                        normalized_consumer,
                        normalized_next.feed_session_id,
                        normalized_next.ingress_sequence,
                        normalized_next.journal_byte_offset,
                        normalized_next.journal_schema,
                        batch_manifest_sha256,
                        len(prepared),
                        normalized_now,
                    ),
                )
            else:
                updated_cursor = connection.execute(
                    """
                    UPDATE detector_cursors
                    SET feed_session_id=?, ingress_sequence=?,
                        journal_byte_offset=?, journal_schema=?,
                        cursor_revision=cursor_revision+1,
                        batch_manifest_sha256=?, batch_intent_count=?,
                        updated_epoch_ns=?
                    WHERE consumer_id=? AND feed_session_id=?
                      AND ingress_sequence=? AND journal_byte_offset=?
                      AND journal_schema=? AND cursor_revision=?
                    """,
                    (
                        normalized_next.feed_session_id,
                        normalized_next.ingress_sequence,
                        normalized_next.journal_byte_offset,
                        normalized_next.journal_schema,
                        batch_manifest_sha256,
                        len(prepared),
                        normalized_now,
                        normalized_consumer,
                        current.feed_session_id,
                        current.ingress_sequence,
                        current.journal_byte_offset,
                        current.journal_schema,
                        cursor_metadata["cursor_revision"],
                    ),
                ).rowcount
                if updated_cursor != 1:
                    raise DetectorCursorConflictError(
                        "detector_cursor_update_cas_lost"
                    )
    return CommitDetectorBatchResult(
        inserted_count=inserted_count,
        idempotent_count=idempotent_count,
        cursor=normalized_next,
        idempotent_replay=idempotent_replay,
    )


def _row_to_intent(row: sqlite3.Row) -> SpoolIntent:
    payload = _strict_json_loads(row["payload_json"], field_name="stored_payload_json")
    canonical_payload_json = _canonical_json_text(payload, field_name="stored_payload")
    if canonical_payload_json != row["payload_json"]:
        raise SpoolValidationError("stored_payload_json_not_canonical")
    recomputed_sha256 = hashlib.sha256(
        canonical_payload_json.encode("utf-8")
    ).hexdigest()
    if recomputed_sha256 != row["payload_sha256"]:
        raise SpoolValidationError("stored_payload_sha256_mismatch")
    try:
        trace = LatencyTrace.from_json(row["trace_json"])
    except TraceValidationError as exc:
        raise SpoolValidationError(f"stored_trace_json_invalid:{exc}") from exc
    if trace.trace_id != row["trace_id"] or payload.get("trace_id") != row["trace_id"]:
        raise SpoolValidationError("stored_trace_id_mismatch")
    stored_bindings = {
        "intent_id": row["intent_id"],
        "target_date": row["target_date"],
        "source": row["source"],
        "vt_symbol": row["vt_symbol"],
        "position_epoch_id": row["position_epoch_id"],
        "state_generation": row["state_generation"],
        "source_feed_session_id": row["source_feed_session_id"],
        "source_ingress_sequence": row["source_ingress_sequence"],
        "source_symbol_sequence": row["source_symbol_sequence"],
        "durable_cursor_feed_session_id": row["durable_cursor_feed_session_id"],
        "durable_cursor_ingress_sequence": row["durable_cursor_ingress_sequence"],
        "durable_cursor_journal_byte_offset": row[
            "durable_cursor_journal_byte_offset"
        ],
        "durable_cursor_journal_schema": row["durable_cursor_journal_schema"],
        "deadline_epoch_ns": row["deadline_epoch_ns"],
        "deadline_monotonic_ns": row["deadline_monotonic_ns"],
    }
    for field_name, stored_value in stored_bindings.items():
        if payload.get(field_name) != stored_value:
            raise SpoolValidationError(f"stored_payload_binding_mismatch:{field_name}")
    trace_bindings = {
        "vt_symbol": (trace.vt_symbol, row["vt_symbol"]),
        "source_feed_session_id": (
            trace.feed_session_id,
            row["source_feed_session_id"],
        ),
        "source_ingress_sequence": (
            trace.ingress_sequence,
            row["source_ingress_sequence"],
        ),
        "source_symbol_sequence": (
            trace.symbol_sequence,
            row["source_symbol_sequence"],
        ),
        "deadline_epoch_ns": (trace.deadline_epoch_ns, row["deadline_epoch_ns"]),
        "deadline_monotonic_ns": (
            trace.deadline_monotonic_ns,
            row["deadline_monotonic_ns"],
        ),
    }
    for field_name, (trace_value, stored_value) in trace_bindings.items():
        if trace_value != stored_value:
            raise SpoolValidationError(f"stored_trace_binding_mismatch:{field_name}")
    ingress = trace.stamps.get("gateway_ingress")
    if ingress is None:
        raise SpoolValidationError("stored_trace_gateway_ingress_missing")
    if ingress.monotonic_ns != row["ingress_monotonic_ns"]:
        raise SpoolValidationError(
            "stored_trace_binding_mismatch:ingress_monotonic_ns"
        )
    if ingress.clock_domain_id != row["clock_domain_id"]:
        raise SpoolValidationError("stored_trace_binding_mismatch:clock_domain_id")
    expected_kind = str(payload.get("offset", "")).lower()
    expected_priority = 0 if expected_kind == "close" else 1
    if row["intent_kind"] != expected_kind:
        raise SpoolValidationError("stored_payload_binding_mismatch:intent_kind")
    if row["priority"] != expected_priority:
        raise SpoolValidationError("stored_payload_binding_mismatch:priority")
    for stage, column in _TRACE_OBSERVATION_COLUMNS.items():
        raw_observation = row[column]
        if not raw_observation:
            continue
        observation = _strict_json_loads(
            raw_observation,
            field_name=f"stored_{stage}",
        )
        expected_raw = _validated_trace_observation_json(
            row,
            stage=stage,
            epoch_ns=_exact_int(
                observation.get("epoch_ns"),
                field_name=f"{stage}_epoch_ns",
            ),
            monotonic_ns=_exact_int(
                observation.get("monotonic_ns"),
                field_name=f"{stage}_monotonic_ns",
            ),
            clock_domain_id=_required_text(
                observation.get("clock_domain_id"),
                field_name=f"{stage}_clock_domain_id",
                max_bytes=256,
            ),
        )
        if expected_raw != raw_observation:
            raise SpoolValidationError(
                f"stored_trace_observation_not_canonical:{stage}"
            )
    return SpoolIntent(
        spool_sequence=row["spool_sequence"],
        intent_id=row["intent_id"],
        payload_sha256=row["payload_sha256"],
        trace_id=row["trace_id"],
        payload=payload,
        target_date=row["target_date"],
        source=row["source"],
        vt_symbol=row["vt_symbol"],
        position_epoch_id=row["position_epoch_id"],
        state_generation=row["state_generation"],
        priority=row["priority"],
        intent_kind=row["intent_kind"],
        state=row["state"],
        deadline_epoch_ns=row["deadline_epoch_ns"],
        deadline_monotonic_ns=row["deadline_monotonic_ns"],
        clock_domain_id=row["clock_domain_id"],
        created_epoch_ns=row["created_epoch_ns"],
        updated_epoch_ns=row["updated_epoch_ns"],
        state_revision=row["state_revision"],
        lease_owner=row["lease_owner"],
        lease_token=row["lease_token"],
        lease_expires_epoch_ns=row["lease_expires_epoch_ns"],
        lease_expires_monotonic_ns=row["lease_expires_monotonic_ns"],
        lease_clock_domain_id=row["lease_clock_domain_id"],
        attempt_count=row["attempt_count"],
        ledger_disposition=row["ledger_disposition"],
        last_error=row["last_error"],
    )


def _expire_due_locked(
    connection: sqlite3.Connection,
    *,
    now_epoch_ns: int,
    now_monotonic_ns: int,
    clock_domain_id: str,
) -> ExpireDueResult:
    expired_open = 0
    blocked_close = 0
    rows = connection.execute(
        "SELECT intent_id, intent_kind, deadline_epoch_ns, deadline_monotonic_ns, "
        "ingress_monotonic_ns, clock_domain_id FROM intents "
        "WHERE state IN ('ready', 'leased')"
    ).fetchall()
    for row in rows:
        domain_mismatch = row["clock_domain_id"] != clock_domain_id
        monotonic_rollback = (
            not domain_mismatch
            and now_monotonic_ns < row["ingress_monotonic_ns"]
        )
        due = (
            domain_mismatch
            or monotonic_rollback
            or now_epoch_ns >= row["deadline_epoch_ns"]
            or now_monotonic_ns >= row["deadline_monotonic_ns"]
        )
        if not due:
            continue
        is_close = row["intent_kind"] == "close"
        target = "blocked" if is_close else "expired"
        error = (
            "deadline_clock_domain_mismatch"
            if domain_mismatch
            else "deadline_monotonic_rollback"
            if monotonic_rollback
            else "deadline_expired_close_critical"
            if is_close
            else "deadline_expired_open"
        )
        changed = connection.execute(
            "UPDATE intents SET state=?, updated_epoch_ns=?, lease_owner='', "
            "lease_token='', lease_expires_epoch_ns=0, "
            "lease_expires_monotonic_ns=0, lease_clock_domain_id='', last_error=? "
            ", state_revision=state_revision+1 "
            "WHERE intent_id=? AND state IN ('ready', 'leased')",
            (target, now_epoch_ns, error, row["intent_id"]),
        ).rowcount
        if changed:
            if is_close:
                blocked_close += 1
            else:
                expired_open += 1
    return ExpireDueResult(
        expired_open_count=max(0, int(expired_open)),
        blocked_close_count=max(0, int(blocked_close)),
    )


def expire_due_intents(
    connection: sqlite3.Connection,
    *,
    now_epoch_ns: int,
    now_monotonic_ns: int,
    clock_domain_id: str,
) -> ExpireDueResult:
    normalized_now, normalized_monotonic, normalized_domain = _validate_now_stamp(
        now_epoch_ns=now_epoch_ns,
        now_monotonic_ns=now_monotonic_ns,
        clock_domain_id=clock_domain_id,
    )
    with _write_transaction(connection):
        return _expire_due_locked(
            connection,
            now_epoch_ns=normalized_now,
            now_monotonic_ns=normalized_monotonic,
            clock_domain_id=normalized_domain,
        )


def lease_next(
    connection: sqlite3.Connection,
    *,
    owner_id: str,
    now_epoch_ns: int,
    now_monotonic_ns: int,
    clock_domain_id: str,
    lease_seconds: float,
    authorized_intents: Mapping[str, str] | None = None,
) -> IntentLease | None:
    normalized_owner = _required_text(
        owner_id,
        field_name="owner_id",
        max_bytes=256,
    )
    normalized_now, normalized_monotonic, normalized_domain = _validate_now_stamp(
        now_epoch_ns=now_epoch_ns,
        now_monotonic_ns=now_monotonic_ns,
        clock_domain_id=clock_domain_id,
    )
    if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, (int, float)):
        raise SpoolValidationError("lease_seconds_must_be_number")
    if not math.isfinite(float(lease_seconds)) or lease_seconds <= 0:
        raise SpoolValidationError("lease_seconds_must_be_positive_finite")
    lease_ns = int(float(lease_seconds) * 1_000_000_000)
    lease_expiry = normalized_now + lease_ns
    lease_monotonic_expiry = normalized_monotonic + lease_ns
    _exact_int(lease_expiry, field_name="lease_expires_epoch_ns")
    _exact_int(lease_monotonic_expiry, field_name="lease_expires_monotonic_ns")
    token = uuid.uuid4().hex
    normalized_authorized: dict[str, str] | None = None
    if authorized_intents is not None:
        if not isinstance(authorized_intents, Mapping):
            raise SpoolValidationError("authorized_intents_must_be_mapping")
        normalized_authorized = {}
        for raw_intent_id, raw_payload_sha256 in authorized_intents.items():
            intent_id = _required_text(
                raw_intent_id,
                field_name="authorized_intent_id",
                max_bytes=512,
            )
            payload_sha256 = _required_text(
                raw_payload_sha256,
                field_name="authorized_payload_sha256",
                max_bytes=64,
            ).lower()
            if _SHA256_RE.fullmatch(payload_sha256) is None:
                raise SpoolValidationError(
                    "authorized_payload_sha256_invalid"
                )
            normalized_authorized[intent_id] = payload_sha256

    def row_is_authorized(row: sqlite3.Row) -> bool:
        return bool(
            normalized_authorized is None
            or normalized_authorized.get(str(row["intent_id"]))
            == str(row["payload_sha256"])
        )

    with _write_transaction(connection):
        _expire_due_locked(
            connection,
            now_epoch_ns=normalized_now,
            now_monotonic_ns=normalized_monotonic,
            clock_domain_id=normalized_domain,
        )
        # This is the last authority boundary before an executor owns work.
        # Stage930's authorization snapshot is necessarily stale by the time
        # we arrive here, so serialize the global one-inflight invariant in
        # the same SQLite write transaction as the lease CAS.
        inflight = connection.execute(
            "SELECT 1 FROM intents WHERE state IN ('leased', 'sending') LIMIT 1"
        ).fetchone()
        if inflight is not None:
            return None
        unknown_exists = connection.execute(
            "SELECT 1 FROM intents WHERE state='side_effect_unknown' LIMIT 1"
        ).fetchone() is not None
        close_rows = connection.execute(
            "SELECT * FROM intents WHERE state='ready' AND intent_kind='close' "
            "AND spool_committed_json<>'' "
            "ORDER BY spool_sequence"
        ).fetchall()
        row = next(
            (candidate for candidate in close_rows if row_is_authorized(candidate)),
            None,
        )
        if unknown_exists and normalized_authorized is None:
            # An unknown side effect may coexist only with a freshly
            # broker-authorized protective CLOSE.  A generic caller without
            # the Stage930 authorization map cannot prove that boundary.
            row = None
        if row is None:
            placeholders = ",".join("?" for _ in OUTSTANDING_CLOSE_STATES)
            outstanding = connection.execute(
                "SELECT 1 FROM intents WHERE intent_kind='close' "
                f"AND state IN ({placeholders}) LIMIT 1",
                OUTSTANDING_CLOSE_STATES,
            ).fetchone()
            if outstanding is not None:
                return None
            if unknown_exists:
                # OPEN is never safe while any earlier external side effect
                # remains unknown, even if a stale authorization map lists it.
                return None
            open_rows = connection.execute(
                "SELECT * FROM intents WHERE state='ready' AND intent_kind='open' "
                "AND spool_committed_json<>'' "
                "ORDER BY spool_sequence"
            ).fetchall()
            row = next(
                (candidate for candidate in open_rows if row_is_authorized(candidate)),
                None,
            )
        if row is None:
            return None
        dequeued_json = row["executor_dequeued_json"] or _validated_trace_observation_json(
            row,
            stage="executor_dequeued",
            epoch_ns=normalized_now,
            monotonic_ns=normalized_monotonic,
            clock_domain_id=normalized_domain,
        )
        updated = connection.execute(
            """
            UPDATE intents
            SET state='leased', lease_owner=?, lease_token=?,
                lease_expires_epoch_ns=?, lease_expires_monotonic_ns=?,
                lease_clock_domain_id=?, attempt_count=attempt_count+1,
                updated_epoch_ns=?, state_revision=state_revision+1,
                executor_dequeued_json=?
            WHERE spool_sequence=? AND state='ready' AND state_revision=?
            """,
            (
                normalized_owner,
                token,
                lease_expiry,
                lease_monotonic_expiry,
                normalized_domain,
                normalized_now,
                dequeued_json,
                row["spool_sequence"],
                row["state_revision"],
            ),
        ).rowcount
        if updated != 1:
            raise SpoolTransitionError("lease_claim_lost")
        leased_row = connection.execute(
            "SELECT * FROM intents WHERE spool_sequence=?",
            (row["spool_sequence"],),
        ).fetchone()
        assert leased_row is not None
        intent = _row_to_intent(leased_row)
        return IntentLease(intent=intent, lease_token=token)


def expired_inflight_leases(
    connection: sqlite3.Connection,
    *,
    now_epoch_ns: int,
    now_monotonic_ns: int,
    clock_domain_id: str,
) -> list[IntentLease]:
    normalized_now, normalized_monotonic, normalized_domain = _validate_now_stamp(
        now_epoch_ns=now_epoch_ns,
        now_monotonic_ns=now_monotonic_ns,
        clock_domain_id=clock_domain_id,
    )
    rows = connection.execute(
        """
        SELECT * FROM intents
        WHERE state IN ('leased', 'sending')
          AND lease_token<>''
          AND (
                lease_clock_domain_id<>?
             OR lease_expires_epoch_ns<=?
             OR lease_expires_monotonic_ns<=?
          )
        ORDER BY CASE WHEN intent_kind='close' THEN 0 ELSE 1 END,
                 spool_sequence
        """,
        (normalized_domain, normalized_now, normalized_monotonic),
    ).fetchall()
    return [
        IntentLease(
            intent=_row_to_intent(row),
            lease_token=str(row["lease_token"]),
        )
        for row in rows
    ]


def side_effect_unknown_leases(
    connection: sqlite3.Connection,
) -> list[IntentLease]:
    """Return reconciliation-only intents without making them sendable."""

    rows = connection.execute(
        """
        SELECT * FROM intents
        WHERE state='side_effect_unknown'
          AND lease_owner<>''
          AND lease_token<>''
        ORDER BY spool_sequence
        """
    ).fetchall()
    return [
        IntentLease(
            intent=_row_to_intent(row),
            lease_token=str(row["lease_token"]),
        )
        for row in rows
    ]


def recover_expired_lease(
    connection: sqlite3.Connection,
    *,
    now_epoch_ns: int,
    now_monotonic_ns: int,
    clock_domain_id: str,
    evidence: LeaseRecoveryEvidence,
) -> str:
    if not isinstance(evidence, LeaseRecoveryEvidence):
        raise SpoolValidationError("recovery_evidence_type_invalid")
    normalized_id = _required_text(
        evidence.intent_id,
        field_name="intent_id",
        max_bytes=512,
    )
    normalized_owner = _required_text(
        evidence.lease_owner,
        field_name="lease_owner",
        max_bytes=256,
    )
    normalized_token = _required_text(
        evidence.lease_token,
        field_name="lease_token",
        max_bytes=256,
    )
    normalized_now, normalized_monotonic, normalized_domain = _validate_now_stamp(
        now_epoch_ns=now_epoch_ns,
        now_monotonic_ns=now_monotonic_ns,
        clock_domain_id=clock_domain_id,
    )
    disposition = _required_text(
        evidence.ledger_disposition,
        field_name="ledger_disposition",
        max_bytes=128,
    )
    fingerprint = _required_text(
        evidence.ledger_fingerprint,
        field_name="ledger_fingerprint",
        max_bytes=512,
    )
    watermark = _exact_int(
        evidence.ledger_watermark,
        field_name="ledger_watermark",
    )
    checksum = _required_text(
        evidence.ledger_checksum_sha256,
        field_name="ledger_checksum_sha256",
        max_bytes=64,
    )
    if _SHA256_RE.fullmatch(checksum) is None:
        raise SpoolValidationError("ledger_checksum_sha256_invalid")
    state_by_disposition = {
        "no_side_effect": "ready",
        "unknown": "side_effect_unknown",
        "side_effect_present": "side_effect_unknown",
        "reconciled": "reconciled",
        "blocked_ledger_integrity": "blocked",
    }
    if disposition not in state_by_disposition:
        raise SpoolValidationError("ledger_disposition_invalid")
    new_state = state_by_disposition[disposition]
    evidence_json = _canonical_json_text(
        {
            "intent_id": normalized_id,
            "lease_owner": normalized_owner,
            "lease_token": normalized_token,
            "ledger_disposition": disposition,
            "ledger_fingerprint": fingerprint,
            "ledger_watermark": watermark,
            "ledger_checksum_sha256": checksum,
            "observed_epoch_ns": normalized_now,
            "observed_monotonic_ns": normalized_monotonic,
            "clock_domain_id": normalized_domain,
        },
        field_name="recovery_evidence",
    )
    with _write_transaction(connection):
        row = connection.execute(
            "SELECT * FROM intents WHERE intent_id=?",
            (normalized_id,),
        ).fetchone()
        if row is None or row["state"] not in {"leased", "sending"}:
            raise SpoolTransitionError("expired_lease_not_found")
        _row_to_intent(row)
        recovery_state = row["state"]
        if row["lease_owner"] != normalized_owner:
            raise SpoolTransitionError("recovery_lease_owner_mismatch")
        if row["lease_token"] != normalized_token:
            raise SpoolTransitionError("recovery_lease_token_mismatch")
        lease_expired = (
            row["lease_clock_domain_id"] != normalized_domain
            or normalized_now >= row["lease_expires_epoch_ns"]
            or normalized_monotonic >= row["lease_expires_monotonic_ns"]
        )
        if not lease_expired:
            raise SpoolTransitionError("lease_not_expired")
        if recovery_state == "sending" and new_state == "ready":
            # A sending row created before Stage179 Task11 did not prove the
            # API slot ordering.  New rows become sending only after the
            # durable batch slot and therefore classify as unknown above.
            new_state = "side_effect_unknown"
        absolute_deadline_due = (
            row["clock_domain_id"] != normalized_domain
            or normalized_monotonic < row["ingress_monotonic_ns"]
            or normalized_now >= row["deadline_epoch_ns"]
            or normalized_monotonic >= row["deadline_monotonic_ns"]
        )
        if new_state == "ready" and absolute_deadline_due:
            new_state = "blocked" if row["intent_kind"] == "close" else "expired"
        clear_recovery_lease = new_state != "side_effect_unknown"
        connection.execute(
            """
            UPDATE intents
            SET state=?, updated_epoch_ns=?,
                lease_owner=CASE WHEN ? THEN '' ELSE lease_owner END,
                lease_token=CASE WHEN ? THEN '' ELSE lease_token END,
                lease_expires_epoch_ns=CASE WHEN ? THEN 0 ELSE lease_expires_epoch_ns END,
                lease_expires_monotonic_ns=CASE WHEN ? THEN 0 ELSE lease_expires_monotonic_ns END,
                lease_clock_domain_id=CASE WHEN ? THEN '' ELSE lease_clock_domain_id END,
                ledger_disposition=?,
                recovery_evidence_json=?, last_error=?,
                state_revision=state_revision+1
            WHERE intent_id=? AND state=? AND lease_owner=? AND lease_token=?
            """,
            (
                new_state,
                normalized_now,
                int(clear_recovery_lease),
                int(clear_recovery_lease),
                int(clear_recovery_lease),
                int(clear_recovery_lease),
                int(clear_recovery_lease),
                disposition,
                evidence_json,
                "" if new_state == "ready" else f"lease_recovery_{disposition}",
                normalized_id,
                recovery_state,
                normalized_owner,
                normalized_token,
            ),
        )
    return new_state


def reconcile_side_effect_unknown(
    connection: sqlite3.Connection,
    *,
    now_epoch_ns: int,
    now_monotonic_ns: int,
    clock_domain_id: str,
    evidence: LeaseRecoveryEvidence,
) -> SpoolIntent:
    """CAS one unknown side effect to terminal using exact durable proof.

    This transition deliberately has no path back to ``ready``.  The retained
    owner/token bind broker reconciliation to the exact lease that may have
    crossed the native order API boundary before the process crashed.
    """

    if not isinstance(evidence, LeaseRecoveryEvidence):
        raise SpoolValidationError("recovery_evidence_type_invalid")
    normalized_id = _required_text(
        evidence.intent_id, field_name="intent_id", max_bytes=512
    )
    normalized_owner = _required_text(
        evidence.lease_owner, field_name="lease_owner", max_bytes=256
    )
    normalized_token = _required_text(
        evidence.lease_token, field_name="lease_token", max_bytes=256
    )
    if evidence.ledger_disposition != "reconciled":
        raise SpoolValidationError(
            "side_effect_unknown_reconciliation_disposition_invalid"
        )
    fingerprint = _required_text(
        evidence.ledger_fingerprint,
        field_name="ledger_fingerprint",
        max_bytes=512,
    )
    watermark = _exact_int(
        evidence.ledger_watermark, field_name="ledger_watermark"
    )
    checksum = _required_text(
        evidence.ledger_checksum_sha256,
        field_name="ledger_checksum_sha256",
        max_bytes=64,
    )
    if _SHA256_RE.fullmatch(checksum) is None:
        raise SpoolValidationError("ledger_checksum_sha256_invalid")
    normalized_now, normalized_monotonic, normalized_domain = _validate_now_stamp(
        now_epoch_ns=now_epoch_ns,
        now_monotonic_ns=now_monotonic_ns,
        clock_domain_id=clock_domain_id,
    )
    evidence_json = _canonical_json_text(
        {
            "intent_id": normalized_id,
            "lease_owner": normalized_owner,
            "lease_token": normalized_token,
            "ledger_disposition": "reconciled",
            "ledger_fingerprint": fingerprint,
            "ledger_watermark": watermark,
            "ledger_checksum_sha256": checksum,
            "observed_epoch_ns": normalized_now,
            "observed_monotonic_ns": normalized_monotonic,
            "clock_domain_id": normalized_domain,
        },
        field_name="recovery_evidence",
    )
    with _write_transaction(connection):
        row = connection.execute(
            "SELECT * FROM intents WHERE intent_id=?", (normalized_id,)
        ).fetchone()
        if (
            row is None
            or row["state"] != "side_effect_unknown"
            or row["lease_owner"] != normalized_owner
            or row["lease_token"] != normalized_token
        ):
            raise SpoolTransitionError(
                "side_effect_unknown_reconciliation_compare_and_swap_mismatch"
            )
        _row_to_intent(row)
        changed = connection.execute(
            """
            UPDATE intents
            SET state='reconciled', updated_epoch_ns=?,
                lease_owner='', lease_token='',
                lease_expires_epoch_ns=0, lease_expires_monotonic_ns=0,
                lease_clock_domain_id='', ledger_disposition='reconciled',
                recovery_evidence_json=?, last_error='',
                state_revision=state_revision+1
            WHERE intent_id=? AND state='side_effect_unknown'
              AND lease_owner=? AND lease_token=? AND state_revision=?
            """,
            (
                normalized_now,
                evidence_json,
                normalized_id,
                normalized_owner,
                normalized_token,
                int(row["state_revision"]),
            ),
        ).rowcount
        if changed != 1:
            raise SpoolTransitionError(
                "side_effect_unknown_reconciliation_compare_and_swap_lost"
            )
        updated = connection.execute(
            "SELECT * FROM intents WHERE intent_id=?", (normalized_id,)
        ).fetchone()
        if updated is None:
            raise SpoolStorageError(
                "side_effect_unknown_reconciliation_readback_missing"
            )
        return _row_to_intent(updated)


def record_trace_observation(
    connection: sqlite3.Connection,
    *,
    intent_id: str,
    stage: str,
    epoch_ns: int,
    monotonic_ns: int,
    clock_domain_id: str,
) -> bool:
    normalized_id = _required_text(intent_id, field_name="intent_id", max_bytes=512)
    normalized_stage = _required_text(stage, field_name="stage", max_bytes=64)
    column = _TRACE_OBSERVATION_COLUMNS.get(normalized_stage)
    if column is None:
        raise SpoolValidationError(f"trace_observation_stage_invalid:{normalized_stage}")
    normalized_epoch, normalized_monotonic, normalized_domain = _validate_now_stamp(
        now_epoch_ns=epoch_ns,
        now_monotonic_ns=monotonic_ns,
        clock_domain_id=clock_domain_id,
    )
    with _write_transaction(connection):
        row = connection.execute(
            "SELECT * FROM intents WHERE intent_id=?",
            (normalized_id,),
        ).fetchone()
        if row is None:
            raise SpoolTransitionError("trace_observation_intent_not_found")
        observation_json = _validated_trace_observation_json(
            row,
            stage=normalized_stage,
            epoch_ns=normalized_epoch,
            monotonic_ns=normalized_monotonic,
            clock_domain_id=normalized_domain,
        )
        existing = row[column]
        if existing:
            if existing != observation_json:
                raise SpoolConflictError(
                    f"trace_observation_conflict:{normalized_id}:{normalized_stage}"
                )
            return False
        changed = connection.execute(
            f"UPDATE intents SET {column}=? WHERE intent_id=? AND {column}=''",
            (observation_json, normalized_id),
        ).rowcount
        if changed != 1:
            raise SpoolConflictError(
                f"trace_observation_compare_and_swap_lost:{normalized_id}:{normalized_stage}"
            )
        return True


def _validated_trace_observation_json(
    row: sqlite3.Row,
    *,
    stage: str,
    epoch_ns: int,
    monotonic_ns: int,
    clock_domain_id: str,
) -> str:
    if clock_domain_id != row["clock_domain_id"]:
        raise SpoolValidationError("trace_observation_clock_domain_mismatch")
    observation_json = _canonical_json_text(
        {
            "epoch_ns": epoch_ns,
            "monotonic_ns": monotonic_ns,
            "clock_domain_id": clock_domain_id,
        },
        field_name="trace_observation",
    )
    if stage in {"stage904_detected", "stage905_intent_ready"}:
        trace = LatencyTrace.from_json(row["trace_json"])
        expected = trace.stamps.get(stage)
        if expected is None:
            raise SpoolValidationError(f"trace_seed_stage_missing:{stage}")
        expected_json = _canonical_json_text(
            {
                "epoch_ns": expected.epoch_ns,
                "monotonic_ns": expected.monotonic_ns,
                "clock_domain_id": expected.clock_domain_id,
            },
            field_name=stage,
        )
        if observation_json != expected_json:
            raise SpoolValidationError(f"trace_seed_stage_mismatch:{stage}")
        return observation_json
    predecessor_column = {
        "spool_committed": "stage905_intent_ready_json",
        "executor_dequeued": "spool_committed_json",
    }[stage]
    predecessor_raw = row[predecessor_column]
    if not predecessor_raw:
        raise SpoolValidationError(
            f"trace_observation_predecessor_missing:{stage}"
        )
    predecessor = _strict_json_loads(
        predecessor_raw,
        field_name=f"stored_{predecessor_column}",
    )
    if predecessor.get("clock_domain_id") != clock_domain_id:
        raise SpoolValidationError("trace_observation_predecessor_domain_mismatch")
    predecessor_monotonic = _exact_int(
        predecessor.get("monotonic_ns"),
        field_name=f"{predecessor_column}_monotonic_ns",
    )
    if monotonic_ns < predecessor_monotonic:
        raise SpoolValidationError(
            f"trace_observation_monotonic_regression:{stage}"
        )
    return observation_json


def read_trace_observations(
    connection: sqlite3.Connection,
    *,
    intent_id: str,
) -> dict[str, TraceObservation]:
    normalized_id = _required_text(intent_id, field_name="intent_id", max_bytes=512)
    columns = ", ".join(_TRACE_OBSERVATION_COLUMNS.values())
    row = connection.execute(
        f"SELECT {columns} FROM intents WHERE intent_id=?",
        (normalized_id,),
    ).fetchone()
    if row is None:
        raise SpoolTransitionError("trace_observation_intent_not_found")
    result: dict[str, TraceObservation] = {}
    for stage, column in _TRACE_OBSERVATION_COLUMNS.items():
        raw = row[column]
        if not raw:
            continue
        parsed = _strict_json_loads(raw, field_name=f"stored_{stage}")
        if set(parsed) != {"epoch_ns", "monotonic_ns", "clock_domain_id"}:
            raise SpoolValidationError(f"stored_trace_observation_fields_invalid:{stage}")
        result[stage] = TraceObservation(
            epoch_ns=_exact_int(parsed["epoch_ns"], field_name=f"{stage}_epoch_ns"),
            monotonic_ns=_exact_int(
                parsed["monotonic_ns"],
                field_name=f"{stage}_monotonic_ns",
            ),
            clock_domain_id=_required_text(
                parsed["clock_domain_id"],
                field_name=f"{stage}_clock_domain_id",
                max_bytes=256,
            ),
        )
    return result


def transition_intent(
    connection: sqlite3.Connection,
    *,
    intent_id: str,
    owner_id: str,
    lease_token: str,
    expected_state: str,
    new_state: str,
    now_epoch_ns: int,
    now_monotonic_ns: int,
    clock_domain_id: str,
    last_error: str = "",
    ledger_disposition: str = "",
) -> SpoolIntent:
    normalized_id = _required_text(intent_id, field_name="intent_id", max_bytes=512)
    normalized_owner = _required_text(
        owner_id,
        field_name="owner_id",
        max_bytes=256,
    )
    normalized_token = _required_text(
        lease_token,
        field_name="lease_token",
        max_bytes=256,
    )
    expected = _required_text(expected_state, field_name="expected_state", max_bytes=64)
    target = _required_text(new_state, field_name="new_state", max_bytes=64)
    normalized_now, normalized_monotonic, normalized_domain = _validate_now_stamp(
        now_epoch_ns=now_epoch_ns,
        now_monotonic_ns=now_monotonic_ns,
        clock_domain_id=clock_domain_id,
    )
    if target not in _ALLOWED_TRANSITIONS.get(expected, set()):
        raise SpoolTransitionError(f"transition_not_allowed:{expected}->{target}")
    normalized_error = (
        ""
        if not last_error
        else _required_text(last_error, field_name="last_error", max_bytes=4096)
    )
    normalized_disposition = (
        ""
        if not ledger_disposition
        else _required_text(
            ledger_disposition,
            field_name="ledger_disposition",
            max_bytes=128,
        )
    )

    with _write_transaction(connection):
        row = connection.execute(
            "SELECT * FROM intents WHERE intent_id=?",
            (normalized_id,),
        ).fetchone()
        if (
            row is None
            or row["state"] != expected
            or row["lease_owner"] != normalized_owner
            or row["lease_token"] != normalized_token
        ):
            raise SpoolTransitionError("transition_compare_and_swap_mismatch")
        _row_to_intent(row)
        effective_target = target
        effective_error = normalized_error
        if expected == "leased" and target in {"ready", "sending"}:
            domain_mismatch = row["clock_domain_id"] != normalized_domain
            monotonic_rollback = (
                not domain_mismatch
                and normalized_monotonic < row["ingress_monotonic_ns"]
            )
            deadline_due = (
                domain_mismatch
                or monotonic_rollback
                or normalized_now >= row["deadline_epoch_ns"]
                or normalized_monotonic >= row["deadline_monotonic_ns"]
            )
            if deadline_due:
                effective_target = (
                    "blocked" if row["intent_kind"] == "close" else "expired"
                )
                effective_error = (
                    "pre_send_clock_domain_mismatch"
                    if domain_mismatch
                    else "pre_send_monotonic_rollback"
                    if monotonic_rollback
                    else "pre_send_absolute_deadline_exceeded"
                )
            elif target == "sending" and row["intent_kind"] == "open":
                placeholders = ",".join("?" for _ in OUTSTANDING_CLOSE_STATES)
                outstanding_close = connection.execute(
                    "SELECT 1 FROM intents WHERE intent_kind='close' "
                    f"AND state IN ({placeholders}) LIMIT 1",
                    OUTSTANDING_CLOSE_STATES,
                ).fetchone()
                if outstanding_close is not None:
                    effective_target = "blocked"
                    effective_error = "pre_send_outstanding_close_preempts_open"
        clear_lease = effective_target in {
            "ready",
            "reconciled",
            "blocked",
            "expired",
        }
        changed = connection.execute(
            """
            UPDATE intents
            SET state=?, updated_epoch_ns=?, last_error=?, ledger_disposition=?,
                state_revision=state_revision+1,
                lease_owner=CASE WHEN ? THEN '' ELSE lease_owner END,
                lease_token=CASE WHEN ? THEN '' ELSE lease_token END,
                lease_expires_epoch_ns=CASE WHEN ? THEN 0 ELSE lease_expires_epoch_ns END,
                lease_expires_monotonic_ns=CASE WHEN ? THEN 0 ELSE lease_expires_monotonic_ns END,
                lease_clock_domain_id=CASE WHEN ? THEN '' ELSE lease_clock_domain_id END
            WHERE intent_id=? AND state=? AND lease_owner=? AND lease_token=?
              AND state_revision=?
            """,
            (
                effective_target,
                normalized_now,
                effective_error,
                normalized_disposition,
                int(clear_lease),
                int(clear_lease),
                int(clear_lease),
                int(clear_lease),
                int(clear_lease),
                normalized_id,
                expected,
                normalized_owner,
                normalized_token,
                row["state_revision"],
            ),
        ).rowcount
        if changed != 1:
            raise SpoolTransitionError("transition_compare_and_swap_lost")
        updated = connection.execute(
            "SELECT * FROM intents WHERE intent_id=?",
            (normalized_id,),
        ).fetchone()
        assert updated is not None
        return _row_to_intent(updated)


def _validate_snapshot_schema_locked(
    connection: sqlite3.Connection,
) -> dict[str, str]:
    user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if user_version != int(SCHEMA_VERSION):
        raise SpoolValidationError(
            f"spool_snapshot_user_version_mismatch:{user_version}!={SCHEMA_VERSION}"
        )
    actual_fingerprint = _schema_contract_fingerprint(connection)
    if actual_fingerprint != EXPECTED_SCHEMA_FINGERPRINT:
        raise SpoolValidationError(
            "spool_snapshot_schema_fingerprint_mismatch:"
            f"{actual_fingerprint}!={EXPECTED_SCHEMA_FINGERPRINT}"
        )
    metadata = dict(connection.execute("SELECT key, value FROM spool_meta"))
    if set(metadata) != {
        "schema_version",
        "spool_uuid",
        "created_epoch_ns",
        "schema_fingerprint",
    }:
        raise SpoolValidationError("spool_snapshot_meta_keys_invalid")
    if metadata["schema_version"] != SCHEMA_VERSION:
        raise SpoolValidationError("spool_snapshot_schema_version_mismatch")
    if metadata["schema_fingerprint"] != actual_fingerprint:
        raise SpoolValidationError("spool_snapshot_meta_fingerprint_mismatch")
    try:
        canonical_uuid = str(uuid.UUID(metadata["spool_uuid"]))
    except (ValueError, AttributeError) as exc:
        raise SpoolValidationError("spool_snapshot_uuid_invalid") from exc
    if canonical_uuid != metadata["spool_uuid"]:
        raise SpoolValidationError("spool_snapshot_uuid_not_canonical")
    if re.fullmatch(r"[1-9][0-9]*", metadata["created_epoch_ns"]) is None:
        raise SpoolValidationError("spool_snapshot_created_epoch_ns_invalid")
    return metadata


def _snapshot_cursor_material_locked(
    connection: sqlite3.Connection,
    *,
    allow_uninitialized: bool = False,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT * FROM detector_cursors ORDER BY consumer_id"
    ).fetchall()
    material: list[dict[str, Any]] = []
    stage941_count = 0
    for row in rows:
        consumer_id = _required_text(
            row["consumer_id"],
            field_name="snapshot_cursor_consumer_id",
            max_bytes=256,
        )
        if consumer_id == "stage941":
            stage941_count += 1
        cursor = _validate_cursor(
            DurableTickCursor(
                feed_session_id=row["feed_session_id"],
                ingress_sequence=row["ingress_sequence"],
                journal_byte_offset=row["journal_byte_offset"],
                journal_schema=row["journal_schema"],
            ),
            field_name=f"snapshot_cursor_{consumer_id}",
        )
        cursor_revision = _exact_int(
            row["cursor_revision"],
            field_name=f"snapshot_cursor_revision_{consumer_id}",
            minimum=1,
        )
        manifest_sha256 = _required_text(
            row["batch_manifest_sha256"],
            field_name=f"snapshot_cursor_manifest_{consumer_id}",
            max_bytes=64,
        ).lower()
        if _SHA256_RE.fullmatch(manifest_sha256) is None:
            raise SpoolValidationError(
                f"snapshot_cursor_manifest_invalid:{consumer_id}"
            )
        material.append(
            {
                "consumer_id": consumer_id,
                "feed_session_id": cursor.feed_session_id,
                "ingress_sequence": cursor.ingress_sequence,
                "journal_byte_offset": cursor.journal_byte_offset,
                "journal_schema": cursor.journal_schema,
                "cursor_revision": cursor_revision,
                "batch_manifest_sha256": manifest_sha256,
                "batch_intent_count": _exact_int(
                    row["batch_intent_count"],
                    field_name=f"snapshot_cursor_batch_count_{consumer_id}",
                ),
                "updated_epoch_ns": _exact_int(
                    row["updated_epoch_ns"],
                    field_name=f"snapshot_cursor_updated_epoch_ns_{consumer_id}",
                ),
            }
        )
    if (
        stage941_count == 0
        and allow_uninitialized
        and not rows
    ):
        return material
    if stage941_count != 1:
        raise SpoolValidationError(
            f"spool_snapshot_stage941_cursor_count_invalid:{stage941_count}"
        )
    return material


def _snapshot_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def snapshot_authorizable_intents(
    connection: sqlite3.Connection,
    *,
    now_epoch_ns: int,
    now_monotonic_ns: int,
    clock_domain_id: str,
) -> AuthorizableIntentSnapshot:
    """Read one complete, mutation-free authorization view of the spool.

    Selection is deliberately limited to structural state and deadlines.
    Stage930 remains responsible for source/role/profile whitelisting.  The
    savepoint pins schema, Stage941 cursor metadata and every intent row to one
    SQLite read transaction so two snapshots can be compared without mixing
    generations.
    """

    normalized_now, normalized_monotonic, normalized_domain = _validate_now_stamp(
        now_epoch_ns=now_epoch_ns,
        now_monotonic_ns=now_monotonic_ns,
        clock_domain_id=clock_domain_id,
    )
    savepoint = "stage179_authorizable_snapshot"
    try:
        connection.execute(f"SAVEPOINT {savepoint}")
        metadata = _validate_snapshot_schema_locked(connection)
        rows = connection.execute(
            "SELECT * FROM intents ORDER BY spool_sequence"
        ).fetchall()
        cursor_material = _snapshot_cursor_material_locked(
            connection,
            allow_uninitialized=not rows,
        )
        intents: list[tuple[SpoolIntent, sqlite3.Row]] = []
        intent_material: list[dict[str, Any]] = []
        for row in rows:
            intent = _row_to_intent(row)
            intents.append((intent, row))
            intent_material.append(dict(row))

        counts = {state: 0 for state in INTENT_STATES}
        for intent, _row in intents:
            if intent.state not in counts:
                raise SpoolValidationError(
                    f"spool_snapshot_intent_state_invalid:{intent.state}"
                )
            counts[intent.state] += 1

        def deadline_eligible(item: tuple[SpoolIntent, sqlite3.Row]) -> bool:
            intent, row = item
            return bool(
                intent.clock_domain_id == normalized_domain
                and normalized_monotonic >= row["ingress_monotonic_ns"]
                and normalized_now < intent.deadline_epoch_ns
                and normalized_monotonic < intent.deadline_monotonic_ns
            )

        ready_close = [
            item
            for item in intents
            if item[0].state == "ready"
            and item[0].intent_kind == "close"
            and bool(item[1]["spool_committed_json"])
        ]
        ready_open = [
            item
            for item in intents
            if item[0].state == "ready"
            and item[0].intent_kind == "open"
            and bool(item[1]["spool_committed_json"])
        ]
        outstanding_close_count = sum(
            1
            for intent, _row in intents
            if intent.intent_kind == "close"
            and intent.state in OUTSTANDING_CLOSE_STATES
        )
        active_lease_count = counts["leased"] + counts["sending"]
        inflight_count = active_lease_count + counts["side_effect_unknown"]
        selected: SpoolIntent | None = None
        if active_lease_count == 0:
            eligible_closes = [item for item in ready_close if deadline_eligible(item)]
            if eligible_closes:
                # An unresolved historical/open side effect must never permit
                # another OPEN, but it must not strand a broker-proven
                # position without a protective CLOSE.  Stage931 still runs
                # complete O-P-O, active-order, broker-residual and auth gates
                # before this close can reach the native API.
                selected = eligible_closes[0][0]
            elif (
                counts["side_effect_unknown"] == 0
                and outstanding_close_count == 0
            ):
                eligible_opens = [item for item in ready_open if deadline_eligible(item)]
                if eligible_opens:
                    selected = eligible_opens[0][0]

        candidate = (
            None
            if selected is None
            else AuthorizableIntentCandidate(
                intent_id=selected.intent_id,
                payload_sha256=selected.payload_sha256,
                intent_kind=selected.intent_kind,
                intent_role=_required_text(
                    selected.payload.get("intent_role"),
                    field_name="snapshot_candidate_intent_role",
                    max_bytes=256,
                ),
                trace_id=_required_text(
                    selected.trace_id,
                    field_name="snapshot_candidate_trace_id",
                    max_bytes=512,
                ),
                target_date=selected.target_date,
                source=selected.source,
                vt_symbol=selected.vt_symbol,
                state_generation=_required_text(
                    selected.state_generation,
                    field_name="snapshot_candidate_state_generation",
                    max_bytes=512,
                ),
                position_epoch_id=_required_text(
                    selected.position_epoch_id,
                    field_name="snapshot_candidate_position_epoch_id",
                    max_bytes=512,
                ),
                root_position_id=_required_text(
                    selected.payload.get("root_position_id"),
                    field_name="snapshot_candidate_root_position_id",
                    max_bytes=512,
                ),
                position_cycle_id=_required_text(
                    selected.payload.get("position_cycle_id"),
                    field_name="snapshot_candidate_position_cycle_id",
                    max_bytes=512,
                ),
                spool_sequence=selected.spool_sequence,
                state_revision=selected.state_revision,
                deadline_epoch_ns=selected.deadline_epoch_ns,
                deadline_monotonic_ns=selected.deadline_monotonic_ns,
                clock_domain_id=selected.clock_domain_id,
                ingress_epoch_ns=_exact_int(
                    next(
                        LatencyTrace.from_json(row["trace_json"])
                        .stamps["gateway_ingress"]
                        .epoch_ns
                        for intent, row in intents
                        if intent.intent_id == selected.intent_id
                    ),
                    field_name="snapshot_candidate_ingress_epoch_ns",
                ),
            )
        )
        cursor_digest = _snapshot_digest(cursor_material)
        snapshot_material = {
            "schema_version": SCHEMA_VERSION,
            "schema_fingerprint": metadata["schema_fingerprint"],
            "spool_uuid": metadata["spool_uuid"],
            "cursor_digest": cursor_digest,
            "intents": intent_material,
            "candidate": (
                None
                if candidate is None
                else {
                    field_name: getattr(candidate, field_name)
                    for field_name in candidate.__dataclass_fields__
                }
            ),
            "counts": counts,
            "outstanding_close_count": outstanding_close_count,
        }
        result = AuthorizableIntentSnapshot(
            spool_uuid=metadata["spool_uuid"],
            schema_version=SCHEMA_VERSION,
            snapshot_digest=_snapshot_digest(snapshot_material),
            cursor_digest=cursor_digest,
            candidate=candidate,
            total_intent_count=len(intents),
            outstanding_close_count=outstanding_close_count,
            ready_close_count=len(ready_close),
            ready_open_count=len(ready_open),
            leased_count=counts["leased"],
            sending_count=counts["sending"],
            side_effect_unknown_count=counts["side_effect_unknown"],
        )
        connection.execute(f"RELEASE SAVEPOINT {savepoint}")
        return result
    except sqlite3.Error as exc:
        try:
            connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            connection.execute(f"RELEASE SAVEPOINT {savepoint}")
        except sqlite3.Error:
            pass
        raise SpoolStorageError(
            "spool_snapshot_transaction_failed:"
            f"{getattr(exc, 'sqlite_errorname', type(exc).__name__)}"
        ) from exc
    except BaseException:
        try:
            connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            connection.execute(f"RELEASE SAVEPOINT {savepoint}")
        except sqlite3.Error:
            pass
        raise


def authorization_snapshots_match(
    first: AuthorizableIntentSnapshot,
    second: AuthorizableIntentSnapshot,
) -> bool:
    return bool(
        isinstance(first, AuthorizableIntentSnapshot)
        and isinstance(second, AuthorizableIntentSnapshot)
        and first.spool_uuid == second.spool_uuid
        and first.snapshot_digest == second.snapshot_digest
        and first.cursor_digest == second.cursor_digest
        and first.candidate == second.candidate
    )


def spool_counts(connection: sqlite3.Connection) -> dict[str, int]:
    counts = {state: 0 for state in INTENT_STATES}
    total = 0
    for row in connection.execute(
        "SELECT state, COUNT(*) AS count FROM intents GROUP BY state"
    ):
        count = int(row["count"])
        counts[row["state"]] = count
        total += count
    counts["total"] = total
    return counts


def wakeup_socket_path(spool_path: str | Path) -> Path:
    resolved = str(Path(spool_path).resolve())
    digest = hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:20]
    candidate = Path(spool_path).parent / f".stage179-{digest}.sock"
    if len(str(candidate).encode("utf-8")) <= 100:
        return candidate
    return Path(tempfile.gettempdir()) / f"stage179-{digest}.sock"


def notify_executor(socket_path: str | Path) -> bool:
    destination = str(Path(socket_path))
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
            client.settimeout(0.05)
            client.sendto(b"\x01", destination)
        return True
    except OSError:
        return False


__all__ = [
    "CommitDetectorBatchResult",
    "DetectorCursorConflictError",
    "ExpireDueResult",
    "IntentLease",
    "LeaseRecoveryEvidence",
    "SCHEMA_VERSION",
    "SpoolConflictError",
    "SpoolError",
    "SpoolIntent",
    "SpoolStorageError",
    "SpoolTransitionError",
    "SpoolValidationError",
    "TraceObservation",
    "commit_detector_batch",
    "expire_due_intents",
    "expired_inflight_leases",
    "initialize_spool",
    "inspect_close_delivery_candidate",
    "lease_next",
    "notify_executor",
    "open_spool",
    "read_detector_cursor",
    "read_trace_observations",
    "record_trace_observation",
    "recover_expired_lease",
    "reconcile_side_effect_unknown",
    "side_effect_unknown_leases",
    "spool_counts",
    "transition_intent",
    "wakeup_socket_path",
]
