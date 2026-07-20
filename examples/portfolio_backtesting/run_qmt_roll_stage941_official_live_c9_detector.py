from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import tempfile
import threading
import time
from typing import Any, Mapping
import uuid

import pandas as pd

from qmt_roll_official_live_intent_spool import (
    CommitDetectorBatchResult,
    DetectorFeedRolloverEvidence,
    commit_detector_batch,
    notify_executor,
    open_spool,
    read_detector_cursor,
    record_trace_observation,
    spool_counts,
    wakeup_socket_path,
)
from qmt_roll_official_live_tick_reader import TickStreamJournalReader
from qmt_roll_official_live_tick_types import (
    DurableTickBatch,
    DurableTickCursor,
    JOURNAL_SCHEMA_FRAMED_V1,
)
from qmt_roll_official_live_time import Clock, SystemClock
from qmt_roll_official_live_trace import LatencyTrace
import run_qmt_roll_stage904_official_live_c9_intraday_monitor as stage904
import run_qmt_roll_stage905_official_live_executor_dry_run as stage905
from run_qmt_alignment_backtest import OUTPUT_DIR


run_intraday_monitor = stage904.run_intraday_monitor
run_executor_dry_run = stage905.run_executor_dry_run

MODEL_TAG = "stage941_official_live_c9_detector_v1"
DEFAULT_CONSUMER_ID = "stage941"
DEFAULT_TICK_HEARTBEAT_PATH = OUTPUT_DIR / (
    "qmt_roll_stage608_readonly_tick_snapshot_probe_tick_stream_heartbeat_"
    "stage608_readonly_tick_snapshot_probe_v1.json"
)
DEFAULT_SPOOL_PATH = OUTPUT_DIR / "qmt_roll_stage941_official_live_intent_spool.sqlite3"
DEFAULT_HEARTBEAT_PATH = OUTPUT_DIR / "qmt_roll_stage941_official_live_c9_detector_heartbeat.json"
SYSTEM_CLOCK = SystemClock()


@dataclass(frozen=True, slots=True)
class DetectorConfig:
    target_date: str
    tick_stream_heartbeat_path: Path = DEFAULT_TICK_HEARTBEAT_PATH
    spool_path: Path = DEFAULT_SPOOL_PATH
    detector_heartbeat_path: Path = DEFAULT_HEARTBEAT_PATH
    consumer_id: str = DEFAULT_CONSUMER_ID
    max_batch_size: int = 1024
    poll_seconds: float = 0.05
    max_tick_age_seconds: int = 10
    require_broker_fill_price: bool = False
    publish_compat_outputs: bool = False
    instance_id: str = ""
    parent_pid: int = 0
    publication_outbox_path: Path | None = None

    def __post_init__(self) -> None:
        target_date = str(self.target_date).strip()
        consumer_id = str(self.consumer_id).strip()
        if not target_date:
            raise ValueError("detector_target_date_missing")
        if not consumer_id:
            raise ValueError("detector_consumer_id_missing")
        if type(self.max_batch_size) is not int or self.max_batch_size <= 0:
            raise ValueError("detector_max_batch_size_invalid")
        if type(self.max_tick_age_seconds) is not int or self.max_tick_age_seconds <= 0:
            raise ValueError("detector_max_tick_age_seconds_invalid")
        if not isinstance(self.poll_seconds, (int, float)) or self.poll_seconds <= 0:
            raise ValueError("detector_poll_seconds_invalid")
        if type(self.parent_pid) is not int or self.parent_pid < 0:
            raise ValueError("detector_parent_pid_invalid")
        object.__setattr__(self, "target_date", target_date)
        object.__setattr__(self, "consumer_id", consumer_id)
        object.__setattr__(self, "tick_stream_heartbeat_path", Path(self.tick_stream_heartbeat_path))
        object.__setattr__(self, "spool_path", Path(self.spool_path))
        object.__setattr__(self, "detector_heartbeat_path", Path(self.detector_heartbeat_path))
        object.__setattr__(
            self,
            "publication_outbox_path",
            (
                Path(self.publication_outbox_path)
                if self.publication_outbox_path is not None
                else Path(self.spool_path).with_suffix(".compat-publication.json")
            ),
        )
        if self.instance_id:
            object.__setattr__(self, "instance_id", str(self.instance_id).strip())


@dataclass(frozen=True, slots=True)
class DetectorCycleResult:
    status: str
    cursor_before: DurableTickCursor | None
    cursor_after: DurableTickCursor | None
    durable_through: DurableTickCursor | None
    tick_count: int
    intent_count: int
    ready_count: int
    blocked_count: int
    expired_count: int
    repaired_commit_stamp_count: int
    notified: bool
    blockers: tuple[str, ...]
    send_order_api_called_count: int = 0
    cancel_order_api_called_count: int = 0


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _exact_nonnegative_int(value: Any, *, field_name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field_name}_invalid")
    return value


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"detector_tick_heartbeat_read_failed:{exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("detector_tick_heartbeat_root_invalid")
    return payload


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        dict(payload),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        parent_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_write_text_durable(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        parent_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        temporary.unlink(missing_ok=True)


def _unlink_durable(path: Path) -> None:
    path = Path(path)
    if not path.exists():
        return
    path.unlink()
    parent_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def _heartbeat_blockers(heartbeat: Mapping[str, Any]) -> tuple[str, ...]:
    blockers: list[str] = []
    required_true = (
        "journal_authority_committed",
        "stream_ready",
        "transport_ready",
        "writer_alive",
        "accepting",
    )
    blockers.extend(
        f"tick_heartbeat_{field}_not_true"
        for field in required_true
        if heartbeat.get(field) is not True
    )
    if heartbeat.get("stopped") is not False:
        blockers.append("tick_heartbeat_stopped")
    if heartbeat.get("gap_latched") is not False:
        blockers.append("tick_heartbeat_gap_latched")
    if heartbeat.get("writer_fault") not in (None, "", {}):
        blockers.append("tick_heartbeat_writer_fault")
    if heartbeat.get("dropped_tick_count") != 0:
        blockers.append("tick_heartbeat_dropped_ticks")
    feed_session_id = _clean(heartbeat.get("feed_session_id"))
    if not feed_session_id:
        blockers.append("tick_heartbeat_feed_session_missing")
    if _clean(heartbeat.get("journal_schema")) != JOURNAL_SCHEMA_FRAMED_V1:
        blockers.append("tick_heartbeat_journal_schema_invalid")
    if not _clean(heartbeat.get("journal_segment_path")):
        blockers.append("tick_heartbeat_journal_segment_missing")
    try:
        durable_sequence = _exact_nonnegative_int(
            heartbeat.get("durable_ingress_sequence"),
            field_name="durable_ingress_sequence",
        )
        durable_offset = _exact_nonnegative_int(
            heartbeat.get("durable_journal_byte_offset"),
            field_name="durable_journal_byte_offset",
        )
        if (durable_sequence == 0) != (durable_offset == 0):
            blockers.append("tick_heartbeat_durable_cursor_incoherent")
    except ValueError as exc:
        blockers.append(str(exc))
    return tuple(sorted(set(blockers)))


def _clean_terminal_heartbeat_blockers(
    heartbeat: Mapping[str, Any],
) -> tuple[str, ...]:
    blockers: list[str] = []
    expected = {
        "journal_authority_committed": True,
        "journal_session_state": "clean_stopped",
        "clean_shutdown": True,
        "stopped": True,
        "stream_ready": False,
        "transport_ready": False,
        "writer_alive": False,
        "accepting": False,
        "gap_latched": False,
    }
    for field, expected_value in expected.items():
        if heartbeat.get(field) != expected_value:
            blockers.append(f"terminal_tick_heartbeat_invalid:{field}")
    if heartbeat.get("writer_fault") not in (None, "", {}):
        blockers.append("terminal_tick_heartbeat_writer_fault")
    for field in ("dropped_tick_count", "queue_depth"):
        if heartbeat.get(field) != 0:
            blockers.append(f"terminal_tick_heartbeat_nonzero:{field}")
    if not _clean(heartbeat.get("feed_session_id")):
        blockers.append("terminal_tick_heartbeat_feed_missing")
    if _clean(heartbeat.get("journal_schema")) != JOURNAL_SCHEMA_FRAMED_V1:
        blockers.append("terminal_tick_heartbeat_schema_invalid")
    if not _clean(heartbeat.get("journal_segment_path")):
        blockers.append("terminal_tick_heartbeat_segment_missing")
    try:
        durable_sequence = _exact_nonnegative_int(
            heartbeat.get("durable_ingress_sequence"),
            field_name="terminal_durable_ingress_sequence",
        )
        durable_offset = _exact_nonnegative_int(
            heartbeat.get("durable_journal_byte_offset"),
            field_name="terminal_durable_journal_byte_offset",
        )
        last_sequence = _exact_nonnegative_int(
            heartbeat.get("last_ingress_sequence"),
            field_name="terminal_last_ingress_sequence",
        )
        if last_sequence != durable_sequence:
            blockers.append("terminal_tick_heartbeat_not_fully_durable")
        if (durable_sequence == 0) != (durable_offset == 0):
            blockers.append("terminal_tick_heartbeat_cursor_incoherent")
    except ValueError as exc:
        blockers.append(str(exc))
    return tuple(sorted(set(blockers)))


def _heartbeat_acceptance_blockers(
    heartbeat: Mapping[str, Any],
) -> tuple[str, ...]:
    running_blockers = _heartbeat_blockers(heartbeat)
    if not running_blockers:
        return ()
    terminal_blockers = _clean_terminal_heartbeat_blockers(heartbeat)
    return terminal_blockers if not terminal_blockers else running_blockers


def _durable_cursor_from_heartbeat(heartbeat: Mapping[str, Any]) -> DurableTickCursor:
    blockers = _heartbeat_acceptance_blockers(heartbeat)
    if blockers:
        raise ValueError("detector_tick_heartbeat_unready:" + ";".join(blockers))
    return DurableTickCursor(
        feed_session_id=_clean(heartbeat.get("feed_session_id")),
        ingress_sequence=_exact_nonnegative_int(
            heartbeat.get("durable_ingress_sequence"),
            field_name="durable_ingress_sequence",
        ),
        journal_byte_offset=_exact_nonnegative_int(
            heartbeat.get("durable_journal_byte_offset"),
            field_name="durable_journal_byte_offset",
        ),
        journal_schema=JOURNAL_SCHEMA_FRAMED_V1,
    )


def _heartbeat_revalidation_blockers(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> tuple[str, ...]:
    blockers = list(_heartbeat_acceptance_blockers(after))
    for field in ("feed_session_id", "journal_schema", "journal_segment_path"):
        if _clean(after.get(field)) != _clean(before.get(field)):
            blockers.append(f"tick_heartbeat_identity_changed:{field}")
    for field in ("durable_ingress_sequence", "durable_journal_byte_offset"):
        try:
            before_value = _exact_nonnegative_int(
                before.get(field),
                field_name=f"before_{field}",
            )
            after_value = _exact_nonnegative_int(
                after.get(field),
                field_name=f"after_{field}",
            )
            if after_value < before_value:
                blockers.append(f"tick_heartbeat_watermark_regressed:{field}")
        except ValueError as exc:
            blockers.append(str(exc))
    lineage_fields = (
        "prior_authoritative_feed_session_id",
        "prior_authoritative_journal_segment_path",
        "prior_authoritative_heartbeat_revision_uuid",
        "prior_authoritative_journal_session_state",
        "prior_authoritative_clean_shutdown",
        "recovery_previous_durable_cursor",
        "prior_uncommitted_gaps",
        "prior_authoritative_empty_feed_sessions",
    )
    if _clean(before.get("prior_authoritative_feed_session_id")):
        for field in lineage_fields:
            if after.get(field) != before.get(field):
                blockers.append(f"tick_heartbeat_rollover_lineage_changed:{field}")
    return tuple(sorted(set(blockers)))


def _read_durable_batch(
    config: DetectorConfig,
    connection: sqlite3.Connection,
    heartbeat: Mapping[str, Any],
) -> DurableTickBatch:
    durable_through = _durable_cursor_from_heartbeat(heartbeat)
    cursor = read_detector_cursor(connection, consumer_id=config.consumer_id)
    reader_cursor = cursor
    reader_path = Path(_clean(heartbeat.get("journal_segment_path")))
    if cursor is not None and cursor.feed_session_id != durable_through.feed_session_id:
        rollover = _validated_rollover_lineage(heartbeat, previous_cursor=cursor)
        if cursor != rollover.recovery_previous_durable_cursor:
            durable_through = rollover.recovery_previous_durable_cursor
            reader_path = Path(rollover.previous_journal_segment_path)
        else:
            reader_cursor = None
    reader = TickStreamJournalReader(reader_path)
    return reader.read_after(
        reader_cursor,
        durable_through=durable_through,
        limit=config.max_batch_size,
    )


def _cursor_from_mapping(value: Any, *, field_name: str) -> DurableTickCursor:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name}_missing")
    feed = _clean(value.get("feed_session_id"))
    sequence = _exact_nonnegative_int(
        value.get("ingress_sequence"),
        field_name=f"{field_name}_ingress_sequence",
    )
    offset = _exact_nonnegative_int(
        value.get("journal_byte_offset"),
        field_name=f"{field_name}_journal_byte_offset",
    )
    schema = _clean(value.get("journal_schema"))
    if not feed or sequence <= 0 or offset <= 0:
        raise ValueError(f"{field_name}_cursor_invalid")
    if schema != JOURNAL_SCHEMA_FRAMED_V1:
        raise ValueError(f"{field_name}_schema_invalid")
    return DurableTickCursor(feed, sequence, offset, schema)


def _validated_rollover_lineage(
    heartbeat: Mapping[str, Any],
    *,
    previous_cursor: DurableTickCursor,
) -> DetectorFeedRolloverEvidence:
    previous_feed = _clean(heartbeat.get("prior_authoritative_feed_session_id"))
    previous_path = _clean(
        heartbeat.get("prior_authoritative_journal_segment_path")
    )
    previous_revision = _clean(
        heartbeat.get("prior_authoritative_heartbeat_revision_uuid")
    )
    previous_state = _clean(
        heartbeat.get("prior_authoritative_journal_session_state")
    )
    previous_clean = heartbeat.get("prior_authoritative_clean_shutdown")
    gaps = heartbeat.get("prior_uncommitted_gaps")
    if previous_feed != previous_cursor.feed_session_id:
        raise ValueError("feed_rollover_previous_feed_mismatch")
    if not previous_path or not previous_revision:
        raise ValueError("feed_rollover_previous_authority_missing")
    if previous_state != "clean_stopped" or previous_clean is not True:
        raise ValueError("feed_rollover_previous_not_clean")
    if not isinstance(gaps, list) or gaps:
        raise ValueError("feed_rollover_prior_gap_present")
    recovered_cursor = _cursor_from_mapping(
        heartbeat.get("recovery_previous_durable_cursor"),
        field_name="feed_rollover_recovery_previous_durable_cursor",
    )
    if recovered_cursor.feed_session_id != previous_cursor.feed_session_id:
        raise ValueError("feed_rollover_recovered_feed_mismatch")
    new_feed = _clean(heartbeat.get("feed_session_id"))
    new_path = _clean(heartbeat.get("journal_segment_path"))
    new_revision = _clean(heartbeat.get("heartbeat_revision_uuid"))
    if not new_feed or new_feed == previous_feed:
        raise ValueError("feed_rollover_new_feed_invalid")
    if not new_path or new_path == previous_path or not new_revision:
        raise ValueError("feed_rollover_new_authority_invalid")
    bridged_empty_feeds = _validated_empty_feed_sessions(
        heartbeat.get("prior_authoritative_empty_feed_sessions", []),
        previous_feed=previous_feed,
        new_feed=new_feed,
    )
    return DetectorFeedRolloverEvidence(
        previous_cursor=previous_cursor,
        previous_journal_segment_path=previous_path,
        previous_heartbeat_revision_uuid=previous_revision,
        previous_clean_shutdown=True,
        recovery_previous_durable_cursor=recovered_cursor,
        prior_uncommitted_gap_count=0,
        new_feed_session_id=new_feed,
        new_journal_segment_path=new_path,
        new_heartbeat_revision_uuid=new_revision,
        bridged_empty_feed_sessions=bridged_empty_feeds,
    )


def _validated_empty_feed_sessions(
    value: Any,
    *,
    previous_feed: str,
    new_feed: str,
) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > 64:
        raise ValueError("feed_rollover_empty_feed_lineage_invalid")
    feeds: list[str] = []
    required_fields = {
        "feed_session_id",
        "journal_segment_path",
        "heartbeat_revision_uuid",
        "journal_session_state",
        "clean_shutdown",
        "durable_ingress_sequence",
        "durable_journal_byte_offset",
    }
    for item in value:
        if not isinstance(item, Mapping) or set(item) != required_fields:
            raise ValueError("feed_rollover_empty_feed_evidence_invalid")
        feed = _clean(item.get("feed_session_id"))
        if (
            not feed
            or feed in {previous_feed, new_feed}
            or feed in feeds
            or not _clean(item.get("journal_segment_path"))
            or not _clean(item.get("heartbeat_revision_uuid"))
            or item.get("journal_session_state") != "clean_stopped"
            or item.get("clean_shutdown") is not True
            or item.get("durable_ingress_sequence") != 0
            or item.get("durable_journal_byte_offset") != 0
        ):
            raise ValueError("feed_rollover_empty_feed_evidence_invalid")
        feeds.append(feed)
    return tuple(feeds)


def _rollover_evidence_for_commit(
    heartbeat: Mapping[str, Any],
    *,
    previous_cursor: DurableTickCursor | None,
    next_cursor: DurableTickCursor,
) -> DetectorFeedRolloverEvidence | None:
    if previous_cursor is None or previous_cursor.feed_session_id == next_cursor.feed_session_id:
        return None
    evidence = _validated_rollover_lineage(
        heartbeat,
        previous_cursor=previous_cursor,
    )
    if evidence.recovery_previous_durable_cursor != previous_cursor:
        raise ValueError("feed_rollover_previous_cursor_not_caught_up")
    if evidence.new_feed_session_id != next_cursor.feed_session_id:
        raise ValueError("feed_rollover_batch_feed_mismatch")
    return evidence


def _validate_batch_traces(batch: DurableTickBatch, *, clock: Clock) -> None:
    for row in batch.records:
        LatencyTrace.from_ingress_row(row, clock=clock)


def _unstamped_committed_intent_ids(connection: sqlite3.Connection) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            "SELECT intent_id FROM intents "
            "WHERE spool_committed_json='' ORDER BY spool_sequence"
        )
    ]


def _repair_unstamped_commits(
    connection: sqlite3.Connection,
    *,
    clock: Clock,
) -> int:
    repaired = 0
    for intent_id in _unstamped_committed_intent_ids(connection):
        created = record_trace_observation(
            connection,
            intent_id=intent_id,
            stage="spool_committed",
            epoch_ns=clock.epoch_ns(),
            monotonic_ns=clock.monotonic_ns(),
            clock_domain_id=clock.clock_domain_id(),
        )
        repaired += int(created)
    return repaired


def _publication_cursor_payload(
    cursor: DurableTickCursor | None,
) -> dict[str, Any] | None:
    if cursor is None:
        return None
    return {
        "feed_session_id": cursor.feed_session_id,
        "ingress_sequence": cursor.ingress_sequence,
        "journal_byte_offset": cursor.journal_byte_offset,
        "journal_schema": cursor.journal_schema,
    }


def _publication_cursor_from_payload(
    value: Any,
    *,
    field_name: str,
) -> DurableTickCursor | None:
    if value is None:
        return None
    return _cursor_from_mapping(value, field_name=field_name)


def _build_compat_publication(
    *,
    consumer_id: str,
    expected_cursor: DurableTickCursor | None,
    next_cursor: DurableTickCursor,
    stage904_result: Any,
    stage905_result: Any,
) -> dict[str, Any]:
    files = [
        {
            "path": str(Path(stage904_result.paths["actions_csv"]).resolve()),
            "text": stage904_result.actions.to_csv(index=False),
        },
        {
            "path": str(Path(stage904_result.paths["summary_json"]).resolve()),
            "text": json.dumps(
                stage904_result.summary,
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
        },
        {
            "path": str(Path(stage904_result.paths["report_md"]).resolve()),
            "text": stage904._build_report(
                stage904_result.summary,
                stage904_result.actions,
            ),
        },
        {
            "path": str(Path(stage905_result.paths["intents_csv"]).resolve()),
            "text": stage905_result.intents.to_csv(index=False),
        },
        {
            "path": str(Path(stage905_result.paths["summary_json"]).resolve()),
            "text": json.dumps(
                stage905_result.summary,
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
        },
        {
            "path": str(Path(stage905_result.paths["report_md"]).resolve()),
            "text": stage905._build_report(
                stage905_result.summary,
                stage905_result.intents,
            ),
        },
    ]
    core = {
        "schema_version": 1,
        "consumer_id": consumer_id,
        "expected_cursor": _publication_cursor_payload(expected_cursor),
        "next_cursor": _publication_cursor_payload(next_cursor),
        "files": files,
    }
    encoded = json.dumps(
        core,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return {
        **core,
        "payload_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _validated_compat_publication(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("compat_publication_root_invalid")
    if set(payload) != {
        "schema_version",
        "consumer_id",
        "expected_cursor",
        "next_cursor",
        "files",
        "payload_sha256",
    }:
        raise ValueError("compat_publication_fields_invalid")
    core = {key: value for key, value in payload.items() if key != "payload_sha256"}
    encoded = json.dumps(
        core,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    if hashlib.sha256(encoded).hexdigest() != payload.get("payload_sha256"):
        raise ValueError("compat_publication_sha256_mismatch")
    if payload.get("schema_version") != 1 or not _clean(payload.get("consumer_id")):
        raise ValueError("compat_publication_identity_invalid")
    _publication_cursor_from_payload(
        payload.get("expected_cursor"),
        field_name="compat_publication_expected_cursor",
    )
    _publication_cursor_from_payload(
        payload.get("next_cursor"),
        field_name="compat_publication_next_cursor",
    )
    files = payload.get("files")
    if not isinstance(files, list) or len(files) != 6:
        raise ValueError("compat_publication_files_invalid")
    for item in files:
        if (
            not isinstance(item, dict)
            or set(item) != {"path", "text"}
            or not _clean(item.get("path"))
            or not isinstance(item.get("text"), str)
        ):
            raise ValueError("compat_publication_file_invalid")
    return payload


def _publish_compat_publication(payload: dict[str, Any]) -> None:
    validated = _validated_compat_publication(payload)
    for item in validated["files"]:
        _atomic_write_text_durable(Path(item["path"]), item["text"])


def _repair_pending_publication(
    connection: sqlite3.Connection,
    *,
    config: DetectorConfig,
) -> int:
    path = config.publication_outbox_path
    assert path is not None
    if not path.exists():
        return 0
    try:
        payload = _validated_compat_publication(
            json.loads(path.read_text(encoding="utf-8"))
        )
    except Exception as exc:
        raise ValueError(f"compat_publication_outbox_invalid:{exc}") from exc
    if payload["consumer_id"] != config.consumer_id:
        raise ValueError("compat_publication_consumer_mismatch")
    expected = _publication_cursor_from_payload(
        payload["expected_cursor"],
        field_name="compat_publication_expected_cursor",
    )
    next_cursor = _publication_cursor_from_payload(
        payload["next_cursor"],
        field_name="compat_publication_next_cursor",
    )
    current = read_detector_cursor(connection, consumer_id=config.consumer_id)
    if current == next_cursor:
        _publish_compat_publication(payload)
        _unlink_durable(path)
        return 1
    if current == expected:
        _unlink_durable(path)
        return 0
    raise ValueError(
        "compat_publication_cursor_conflict:"
        f"expected={expected};next={next_cursor};current={current}"
    )


def _result(
    *,
    status: str,
    cursor_before: DurableTickCursor | None,
    cursor_after: DurableTickCursor | None,
    durable_through: DurableTickCursor | None,
    tick_count: int = 0,
    intent_count: int = 0,
    ready_count: int = 0,
    blocked_count: int = 0,
    expired_count: int = 0,
    repaired: int = 0,
    notified: bool = False,
    blockers: tuple[str, ...] = (),
) -> DetectorCycleResult:
    return DetectorCycleResult(
        status=status,
        cursor_before=cursor_before,
        cursor_after=cursor_after,
        durable_through=durable_through,
        tick_count=tick_count,
        intent_count=intent_count,
        ready_count=ready_count,
        blocked_count=blocked_count,
        expired_count=expired_count,
        repaired_commit_stamp_count=repaired,
        notified=notified,
        blockers=blockers,
    )


def _result_with_spool_counts(
    connection: sqlite3.Connection,
    **kwargs: Any,
) -> DetectorCycleResult:
    counts = spool_counts(connection)
    kwargs.setdefault("ready_count", int(counts.get("ready", 0)))
    kwargs.setdefault("blocked_count", int(counts.get("blocked", 0)))
    kwargs.setdefault("expired_count", int(counts.get("expired", 0)))
    return _result(**kwargs)


def run_detector_once(
    config: DetectorConfig,
    *,
    clock: Clock = SYSTEM_CLOCK,
) -> DetectorCycleResult:
    if not isinstance(config, DetectorConfig):
        raise TypeError("config_must_be_detector_config")
    connection = open_spool(config.spool_path)
    try:
        repaired = _repair_unstamped_commits(connection, clock=clock)
        _repair_pending_publication(connection, config=config)
        cursor_before = read_detector_cursor(
            connection,
            consumer_id=config.consumer_id,
        )
        try:
            heartbeat = _read_json_object(config.tick_stream_heartbeat_path)
        except ValueError as exc:
            return _result_with_spool_counts(
                connection,
                status="detector_feed_unready",
                cursor_before=cursor_before,
                cursor_after=cursor_before,
                durable_through=None,
                repaired=repaired,
                blockers=(str(exc),),
            )
        heartbeat_blockers = _heartbeat_acceptance_blockers(heartbeat)
        if heartbeat_blockers:
            return _result_with_spool_counts(
                connection,
                status="detector_feed_unready",
                cursor_before=cursor_before,
                cursor_after=cursor_before,
                durable_through=None,
                repaired=repaired,
                blockers=heartbeat_blockers,
            )
        try:
            batch = _read_durable_batch(config, connection, heartbeat)
        except ValueError as exc:
            return _result_with_spool_counts(
                connection,
                status="detector_feed_unready",
                cursor_before=cursor_before,
                cursor_after=cursor_before,
                durable_through=None,
                repaired=repaired,
                blockers=(str(exc),),
            )
        if batch.gap is not None:
            return _result_with_spool_counts(
                connection,
                status="detector_feed_unready",
                cursor_before=cursor_before,
                cursor_after=cursor_before,
                durable_through=batch.durable_through,
                tick_count=len(batch.records),
                repaired=repaired,
                blockers=(f"tick_reader_gap:{batch.gap.reason}",),
            )
        if not batch.records:
            return _result_with_spool_counts(
                connection,
                status=(
                    "detector_idle_caught_up"
                    if batch.caught_up
                    else "detector_waiting_for_durable_batch"
                ),
                cursor_before=cursor_before,
                cursor_after=cursor_before,
                durable_through=batch.durable_through,
                repaired=repaired,
            )
        if batch.next_cursor is None:
            return _result_with_spool_counts(
                connection,
                status="detector_feed_unready",
                cursor_before=cursor_before,
                cursor_after=cursor_before,
                durable_through=batch.durable_through,
                tick_count=len(batch.records),
                repaired=repaired,
                blockers=("tick_reader_next_cursor_missing",),
            )
        _validate_batch_traces(batch, clock=clock)
        stage904_result = run_intraday_monitor(
            target_date=config.target_date,
            max_tick_age_seconds=config.max_tick_age_seconds,
            require_broker_fill_price=config.require_broker_fill_price,
            durable_batch=batch,
            clock=clock,
            write_compat_outputs=False,
            allow_partial_durable_batch=True,
        )
        try:
            after_stage904_heartbeat = _read_json_object(
                config.tick_stream_heartbeat_path
            )
            after_stage904_blockers = _heartbeat_revalidation_blockers(
                heartbeat,
                after_stage904_heartbeat,
            )
        except ValueError as exc:
            after_stage904_blockers = (str(exc),)
            after_stage904_heartbeat = heartbeat
        if after_stage904_blockers:
            return _result_with_spool_counts(
                connection,
                status="detector_feed_unready",
                cursor_before=cursor_before,
                cursor_after=cursor_before,
                durable_through=batch.durable_through,
                tick_count=len(batch.records),
                repaired=repaired,
                blockers=after_stage904_blockers,
            )
        stage905_result = run_executor_dry_run(
            config.target_date,
            mode="dry-run",
            stage904_actions=stage904_result,
            include_stage901_pending=False,
            clock=clock,
            write_compat_outputs=False,
        )
        intents_frame = stage905_result.intents
        if not isinstance(intents_frame, pd.DataFrame):
            raise TypeError("stage905_result_intents_must_be_dataframe")
        intents = intents_frame.to_dict(orient="records")
        publication: dict[str, Any] | None = None
        if config.publish_compat_outputs:
            publication = _build_compat_publication(
                consumer_id=config.consumer_id,
                expected_cursor=cursor_before,
                next_cursor=batch.next_cursor,
                stage904_result=stage904_result,
                stage905_result=stage905_result,
            )
            assert config.publication_outbox_path is not None
            _atomic_write_json(config.publication_outbox_path, publication)
        try:
            before_commit_heartbeat = _read_json_object(
                config.tick_stream_heartbeat_path
            )
            before_commit_blockers = _heartbeat_revalidation_blockers(
                after_stage904_heartbeat,
                before_commit_heartbeat,
            )
        except ValueError as exc:
            before_commit_blockers = (str(exc),)
            before_commit_heartbeat = after_stage904_heartbeat
        if before_commit_blockers:
            return _result_with_spool_counts(
                connection,
                status="detector_feed_unready",
                cursor_before=cursor_before,
                cursor_after=cursor_before,
                durable_through=batch.durable_through,
                tick_count=len(batch.records),
                repaired=repaired,
                blockers=before_commit_blockers,
            )
        commit_stamp_epoch_ns = clock.epoch_ns()
        commit_stamp_monotonic_ns = clock.monotonic_ns()
        commit_result: CommitDetectorBatchResult = commit_detector_batch(
            connection,
            consumer_id=config.consumer_id,
            expected_cursor=cursor_before,
            next_cursor=batch.next_cursor,
            intents=intents,
            now_epoch_ns=commit_stamp_epoch_ns,
            now_monotonic_ns=commit_stamp_monotonic_ns,
            clock_domain_id=clock.clock_domain_id(),
            feed_rollover_evidence=_rollover_evidence_for_commit(
                before_commit_heartbeat,
                previous_cursor=cursor_before,
                next_cursor=batch.next_cursor,
            ),
        )
        for intent in intents:
            record_trace_observation(
                connection,
                intent_id=_clean(intent.get("intent_id")),
                stage="spool_committed",
                epoch_ns=clock.epoch_ns(),
                monotonic_ns=clock.monotonic_ns(),
                clock_domain_id=clock.clock_domain_id(),
            )
        notified = False
        if commit_result.inserted_count or commit_result.idempotent_count:
            notified = notify_executor(wakeup_socket_path(config.spool_path))
        if publication is not None:
            _publish_compat_publication(publication)
            assert config.publication_outbox_path is not None
            _unlink_durable(config.publication_outbox_path)
        counts = spool_counts(connection)
        return _result(
            status="detector_cycle_committed",
            cursor_before=cursor_before,
            cursor_after=commit_result.cursor,
            durable_through=batch.durable_through,
            tick_count=len(batch.records),
            intent_count=len(intents),
            ready_count=int(counts.get("ready", 0)),
            blocked_count=int(counts.get("blocked", 0)),
            expired_count=int(counts.get("expired", 0)),
            repaired=repaired,
            notified=notified,
        )
    finally:
        connection.close()


def _cursor_payload(cursor: DurableTickCursor | None) -> dict[str, Any]:
    if cursor is None:
        return {}
    return {
        "feed_session_id": cursor.feed_session_id,
        "ingress_sequence": cursor.ingress_sequence,
        "journal_byte_offset": cursor.journal_byte_offset,
        "journal_schema": cursor.journal_schema,
    }


def _publish_detector_heartbeat(
    config: DetectorConfig,
    *,
    status: str,
    ready: bool,
    stopped: bool,
    result: DetectorCycleResult | None = None,
    error: str = "",
) -> None:
    payload: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "detector_instance_id": config.instance_id,
        "owner_pid": os.getpid(),
        "parent_pid": config.parent_pid,
        "generated_epoch_ns": time.time_ns(),
        "status": status,
        "ready": bool(ready),
        "stopped": bool(stopped),
        "target_date": config.target_date,
        "consumer_id": config.consumer_id,
        "spool_path": str(config.spool_path.resolve()),
        "tick_stream_heartbeat_path": str(
            config.tick_stream_heartbeat_path.resolve()
        ),
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "error": error,
    }
    if result is not None:
        payload.update(
            {
                "cycle_status": result.status,
                "cursor_before": _cursor_payload(result.cursor_before),
                "cursor_after": _cursor_payload(result.cursor_after),
                "durable_through": _cursor_payload(result.durable_through),
                "tick_count": result.tick_count,
                "intent_count": result.intent_count,
                "ready_count": result.ready_count,
                "blocked_count": result.blocked_count,
                "expired_count": result.expired_count,
                "repaired_commit_stamp_count": result.repaired_commit_stamp_count,
                "blockers": list(result.blockers),
            }
        )
    _atomic_write_json(config.detector_heartbeat_path, payload)


def serve_detector(
    config: DetectorConfig,
    *,
    clock: Clock = SYSTEM_CLOCK,
    stop_event: threading.Event | None = None,
) -> int:
    owned_stop_event = stop_event is None
    stop_event = stop_event or threading.Event()
    previous_handlers: dict[int, Any] = {}

    def request_stop(_signum: int, _frame: Any) -> None:
        stop_event.set()

    if owned_stop_event and threading.current_thread() is threading.main_thread():
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, request_stop)
    _publish_detector_heartbeat(
        config,
        status="detector_starting_unready",
        ready=False,
        stopped=False,
    )
    exit_code = 0
    try:
        while not stop_event.is_set():
            try:
                result = run_detector_once(config, clock=clock)
                ready = result.status in {
                    "detector_cycle_committed",
                    "detector_idle_caught_up",
                    "detector_waiting_for_durable_batch",
                } and not result.blockers
                _publish_detector_heartbeat(
                    config,
                    status=(
                        "detector_running_ready"
                        if ready
                        else "detector_running_unready"
                    ),
                    ready=ready,
                    stopped=False,
                    result=result,
                )
            except Exception as exc:
                exit_code = 2
                _publish_detector_heartbeat(
                    config,
                    status="detector_cycle_exception_unready",
                    ready=False,
                    stopped=False,
                    error=repr(exc),
                )
            stop_event.wait(config.poll_seconds)
    finally:
        _publish_detector_heartbeat(
            config,
            status="detector_stopped_unready",
            ready=False,
            stopped=True,
        )
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
    return exit_code


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Default-off persistent Stage941 C9 durable detector."
    )
    parser.add_argument("--target-date", required=True)
    parser.add_argument(
        "--tick-stream-heartbeat-path",
        type=Path,
        default=DEFAULT_TICK_HEARTBEAT_PATH,
    )
    parser.add_argument("--spool-path", type=Path, default=DEFAULT_SPOOL_PATH)
    parser.add_argument(
        "--detector-heartbeat-path",
        type=Path,
        default=DEFAULT_HEARTBEAT_PATH,
    )
    parser.add_argument("--consumer-id", default=DEFAULT_CONSUMER_ID)
    parser.add_argument("--max-batch-size", type=int, default=1024)
    parser.add_argument("--poll-seconds", type=float, default=0.05)
    parser.add_argument("--max-tick-age-seconds", type=int, default=10)
    parser.add_argument("--require-broker-fill-price", action="store_true")
    parser.add_argument("--publish-compat-outputs", action="store_true")
    parser.add_argument("--instance-id", default="")
    parser.add_argument("--parent-pid", type=int, default=0)
    parser.add_argument("--publication-outbox-path", type=Path, default=None)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    config = DetectorConfig(
        target_date=args.target_date,
        tick_stream_heartbeat_path=args.tick_stream_heartbeat_path,
        spool_path=args.spool_path,
        detector_heartbeat_path=args.detector_heartbeat_path,
        consumer_id=args.consumer_id,
        max_batch_size=args.max_batch_size,
        poll_seconds=args.poll_seconds,
        max_tick_age_seconds=args.max_tick_age_seconds,
        require_broker_fill_price=args.require_broker_fill_price,
        publish_compat_outputs=args.publish_compat_outputs,
        instance_id=args.instance_id or str(uuid.uuid4()),
        parent_pid=args.parent_pid,
        publication_outbox_path=args.publication_outbox_path,
    )
    raise SystemExit(serve_detector(config))


if __name__ == "__main__":
    main()
