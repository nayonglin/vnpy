from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping
import hashlib
import os

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
    JOURNAL_RECORD_TYPE_FIELD,
    JOURNAL_SCHEMA_FRAMED_V1,
    JOURNAL_SCHEMA_LEGACY_V0,
    DurableTickBatch,
    DurableTickCursor,
    TickStreamGap,
)


MAX_JOURNAL_PAGE_BYTES = 16 * 1024 * 1024
CURSOR_REVERSE_SCAN_CHUNK_BYTES = 4096


def _reader_gap(
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


def _read_record_within(
    handle: Any,
    *,
    hard_end: int,
) -> tuple[bytes, dict[str, Any] | None, str]:
    """Read at most the certified byte range and parse only complete lines."""

    remaining = hard_end - handle.tell()
    if remaining <= 0:
        return b"", None, "journal_unexpected_eof"
    raw_line = handle.readline(min(MAX_JOURNAL_LINE_BYTES + 1, remaining))
    if not raw_line.endswith(b"\n") and handle.tell() >= hard_end:
        return raw_line, None, "journal_record_crosses_durable_offset"
    row, parse_error = _parse_record_line(raw_line)
    return raw_line, row, parse_error


def _validate_framed_cursor_ancestry(
    handle: Any,
    cursor: DurableTickCursor,
    *,
    hard_end: int,
) -> str:
    """Prove one external cursor is reachable from the segment header.

    A locally valid commit is not sufficient: without a trusted hash-chain a
    caller could otherwise point at an orphan batch whose ``previous`` value
    merely claims a missing prefix.  Keep memory bounded to the current batch
    while replaying every commit from the header to the supplied cursor.
    """

    cursor_offset = cursor.journal_byte_offset
    if cursor_offset <= 0 or cursor_offset > hard_end:
        return "cursor_offset_beyond_durable_watermark"
    handle.seek(cursor_offset - 1)
    if handle.read(1) != b"\n":
        return "cursor_offset_not_record_boundary"
    handle.seek(0)
    _raw_header, header, header_error = _read_record_within(
        handle,
        hard_end=hard_end,
    )
    segment_id = (
        _validated_header_segment_id(
            header or {},
            feed_session_id=cursor.feed_session_id,
        )
        if not header_error
        else ""
    )
    if not segment_id:
        return header_error or "journal_header_invalid"

    committed_sequence = 0
    while committed_sequence < cursor.ingress_sequence:
        pending_first = 0
        pending_last = 0
        pending_count = 0
        pending_bytes = 0
        pending_digest = hashlib.sha256()
        expected_sequence = committed_sequence + 1
        while True:
            if handle.tell() >= cursor_offset:
                return "cursor_offset_not_matching_commit_record"
            raw_line, row, parse_error = _read_record_within(
                handle,
                hard_end=hard_end,
            )
            line_end = handle.tell()
            if parse_error:
                return parse_error
            assert row is not None
            control_type = row.get(JOURNAL_RECORD_TYPE_FIELD)
            if control_type == JOURNAL_BATCH_COMMIT_RECORD_TYPE:
                if not _commit_frame_matches(
                    row,
                    pending_first_sequence=pending_first,
                    pending_last_sequence=pending_last,
                    pending_row_count=pending_count,
                    pending_payload_byte_count=pending_bytes,
                    pending_payload_sha256=pending_digest.hexdigest(),
                    feed_session_id=cursor.feed_session_id,
                    segment_id=segment_id,
                    previous_durable_sequence=committed_sequence,
                ):
                    return "journal_commit_frame_invalid"
                frame_end = _strict_json_int(row.get("last_ingress_sequence"))
                if frame_end is None:
                    return "journal_commit_frame_invalid"
                if frame_end > cursor.ingress_sequence:
                    return "cursor_not_reachable_from_header"
                committed_sequence = frame_end
                if committed_sequence == cursor.ingress_sequence:
                    if line_end != cursor_offset:
                        return "cursor_offset_not_matching_commit_record"
                    return ""
                if line_end >= cursor_offset:
                    return "cursor_offset_not_matching_commit_record"
                break
            if control_type:
                return "journal_unknown_control_record"
            sequence, identity_error = _validated_framed_tick_row_identity(
                row,
                feed_session_id=cursor.feed_session_id,
            )
            if identity_error:
                return identity_error
            assert sequence is not None
            if sequence != expected_sequence:
                return "journal_sequence_gap"
            pending_count += 1
            if pending_count > DEFAULT_WRITER_BATCH_SIZE:
                return "journal_batch_row_limit_exceeded"
            pending_first = pending_first or sequence
            pending_last = sequence
            pending_bytes += len(raw_line)
            if pending_bytes > MAX_JOURNAL_BATCH_BYTES:
                return "journal_batch_payload_limit_exceeded"
            pending_digest.update(raw_line)
            expected_sequence += 1

    return "cursor_not_reachable_from_header"


def _validate_cursor_record(
    path: Path,
    cursor: DurableTickCursor,
) -> str:
    """Bind an externally supplied byte cursor to the record it certifies."""

    offset = cursor.journal_byte_offset
    try:
        handle = path.open("rb")
    except FileNotFoundError:
        return "journal_missing"
    with handle:
        file_size = os.fstat(handle.fileno()).st_size
        if offset <= 0 or offset > file_size:
            return "cursor_offset_beyond_journal"
        handle.seek(offset - 1)
        if handle.read(1) != b"\n":
            return "cursor_offset_not_record_boundary"
        search_end = offset - 1
        reversed_chunks: list[bytes] = []
        scanned = 0
        while search_end > 0:
            chunk_size = min(CURSOR_REVERSE_SCAN_CHUNK_BYTES, search_end)
            chunk_start = search_end - chunk_size
            handle.seek(chunk_start)
            chunk = handle.read(chunk_size)
            prior_newline = chunk.rfind(b"\n")
            if prior_newline >= 0:
                reversed_chunks.append(chunk[prior_newline + 1 :])
                break
            reversed_chunks.append(chunk)
            scanned += len(chunk)
            if scanned + 1 > MAX_JOURNAL_LINE_BYTES:
                return "journal_record_too_large"
            search_end = chunk_start
        raw_line = b"".join(reversed(reversed_chunks)) + b"\n"
    if len(raw_line) > MAX_JOURNAL_LINE_BYTES:
        return "journal_record_too_large"
    row, parse_error = _parse_record_line(raw_line)
    if parse_error:
        return parse_error
    assert row is not None
    if cursor.journal_schema == JOURNAL_SCHEMA_FRAMED_V1:
        if not (
            row.get(JOURNAL_RECORD_TYPE_FIELD)
            == JOURNAL_BATCH_COMMIT_RECORD_TYPE
            and _strict_json_int(row.get("schema_version"))
            == JOURNAL_BATCH_COMMIT_SCHEMA_VERSION
            and _clean(row.get("feed_session_id")) == cursor.feed_session_id
            and _clean(row.get("segment_id")) == cursor.feed_session_id
            and _strict_json_int(row.get("last_ingress_sequence"))
            == cursor.ingress_sequence
        ):
            return "cursor_offset_not_matching_commit_record"
        return ""
    if not (
        not row.get(JOURNAL_RECORD_TYPE_FIELD)
        and _clean(row.get("feed_session_id")) == cursor.feed_session_id
        and _strict_json_int(row.get("ingress_sequence"))
        == cursor.ingress_sequence
    ):
        return "cursor_offset_not_matching_legacy_record"
    return ""


def _read_framed_after(
    path: Path,
    cursor: DurableTickCursor | None,
    *,
    durable_through: DurableTickCursor,
    limit: int,
) -> DurableTickBatch:
    feed_session_id = durable_through.feed_session_id
    durable_sequence = int(durable_through.ingress_sequence)
    durable_offset = int(durable_through.journal_byte_offset)
    if durable_offset <= 0:
        gap = _reader_gap(
            feed_session_id,
            1,
            durable_sequence,
            "framed_durable_cursor_offset_missing",
        )
        return DurableTickBatch((), cursor, durable_through, False, gap)
    if not path.exists():
        gap = _reader_gap(
            feed_session_id,
            1,
            durable_sequence,
            "journal_missing",
        )
        return DurableTickBatch((), cursor, durable_through, False, gap)
    file_size = path.stat().st_size
    if durable_offset > file_size:
        gap = _reader_gap(
            feed_session_id,
            1,
            durable_sequence,
            "durable_cursor_offset_beyond_journal",
        )
        return DurableTickBatch((), cursor, durable_through, False, gap)

    committed_sequence = int(cursor.ingress_sequence) if cursor else 0
    next_cursor = cursor
    records: list[Mapping[str, Any]] = []
    page_bytes = 0
    gap: TickStreamGap | None = None
    limited = False

    with path.open("rb") as handle:
        if cursor is None:
            raw_header, header, header_error = _read_record_within(
                handle,
                hard_end=durable_offset,
            )
            header_end = handle.tell()
            segment_id = (
                _validated_header_segment_id(
                    header or {},
                    feed_session_id=feed_session_id,
                )
                if not header_error
                else ""
            )
            if not segment_id:
                gap = _reader_gap(
                    feed_session_id,
                    1,
                    durable_sequence,
                    header_error or "journal_header_invalid",
                )
                return DurableTickBatch((), None, durable_through, False, gap)
        else:
            cursor_offset = int(cursor.journal_byte_offset)
            if cursor_offset <= 0:
                gap = _reader_gap(
                    feed_session_id,
                    cursor.ingress_sequence + 1,
                    durable_sequence,
                    "framed_cursor_offset_missing",
                )
                return DurableTickBatch((), cursor, durable_through, False, gap)
            if cursor_offset > durable_offset:
                gap = _reader_gap(
                    feed_session_id,
                    durable_sequence + 1,
                    cursor.ingress_sequence,
                    "cursor_offset_ahead_of_durable_watermark",
                )
                return DurableTickBatch((), cursor, durable_through, False, gap)
            cursor_error = _validate_framed_cursor_ancestry(
                handle,
                cursor,
                hard_end=durable_offset,
            )
            if cursor_error:
                gap = _reader_gap(
                    feed_session_id,
                    cursor.ingress_sequence + 1,
                    durable_sequence,
                    cursor_error,
                )
                return DurableTickBatch((), cursor, durable_through, False, gap)
            if handle.tell() != cursor_offset:
                gap = _reader_gap(
                    feed_session_id,
                    cursor.ingress_sequence,
                    durable_sequence,
                    "cursor_offset_not_matching_commit_record",
                )
                return DurableTickBatch((), cursor, durable_through, False, gap)
            segment_id = feed_session_id

        while committed_sequence < durable_sequence:
            pending_rows: list[Mapping[str, Any]] = []
            pending_first = 0
            pending_last = 0
            pending_count = 0
            pending_bytes = 0
            pending_digest = hashlib.sha256()
            expected_sequence = committed_sequence + 1

            while True:
                raw_line, row, parse_error = _read_record_within(
                    handle,
                    hard_end=durable_offset,
                )
                line_end = handle.tell()
                if parse_error:
                    gap = _reader_gap(
                        feed_session_id,
                        committed_sequence + 1,
                        durable_sequence,
                        parse_error,
                    )
                    break
                control_type = row.get(JOURNAL_RECORD_TYPE_FIELD)
                if control_type == JOURNAL_BATCH_COMMIT_RECORD_TYPE:
                    if not _commit_frame_matches(
                        row,
                        pending_first_sequence=pending_first,
                        pending_last_sequence=pending_last,
                        pending_row_count=pending_count,
                        pending_payload_byte_count=pending_bytes,
                        pending_payload_sha256=pending_digest.hexdigest(),
                        feed_session_id=feed_session_id,
                        segment_id=segment_id,
                        previous_durable_sequence=committed_sequence,
                    ):
                        gap = _reader_gap(
                            feed_session_id,
                            committed_sequence + 1,
                            durable_sequence,
                            "journal_commit_frame_invalid",
                        )
                        break
                    frame_end = _strict_json_int(
                        row.get("last_ingress_sequence")
                    )
                    if frame_end is None:
                        gap = _reader_gap(
                            feed_session_id,
                            committed_sequence + 1,
                            durable_sequence,
                            "journal_commit_frame_invalid",
                        )
                        break
                    if frame_end > durable_sequence:
                        gap = _reader_gap(
                            feed_session_id,
                            committed_sequence + 1,
                            frame_end,
                            "commit_frame_beyond_durable_watermark",
                        )
                        break
                    if records and len(records) + len(pending_rows) > limit:
                        limited = True
                        break
                    if records and page_bytes + pending_bytes > MAX_JOURNAL_PAGE_BYTES:
                        limited = True
                        break
                    records.extend(pending_rows)
                    page_bytes += pending_bytes
                    committed_sequence = frame_end
                    next_cursor = DurableTickCursor(
                        feed_session_id,
                        committed_sequence,
                        journal_byte_offset=line_end,
                        journal_schema=JOURNAL_SCHEMA_FRAMED_V1,
                    )
                    if (
                        len(records) >= limit
                        and committed_sequence < durable_sequence
                    ):
                        limited = True
                    break
                if control_type:
                    gap = _reader_gap(
                        feed_session_id,
                        committed_sequence + 1,
                        durable_sequence,
                        "journal_unknown_control_record",
                    )
                    break
                sequence, identity_error = (
                    _validated_framed_tick_row_identity(
                        row,
                        feed_session_id=feed_session_id,
                    )
                )
                if identity_error:
                    gap = _reader_gap(
                        feed_session_id,
                        expected_sequence,
                        durable_sequence,
                        identity_error,
                    )
                    break
                assert sequence is not None
                if sequence != expected_sequence:
                    gap = _reader_gap(
                        feed_session_id,
                        expected_sequence,
                        max(expected_sequence, sequence - 1),
                        "journal_sequence_gap",
                    )
                    break
                pending_count += 1
                if pending_count > DEFAULT_WRITER_BATCH_SIZE:
                    gap = _reader_gap(
                        feed_session_id,
                        committed_sequence + 1,
                        durable_sequence,
                        "journal_batch_row_limit_exceeded",
                    )
                    break
                pending_first = pending_first or sequence
                pending_last = sequence
                pending_bytes += len(raw_line)
                if pending_bytes > MAX_JOURNAL_BATCH_BYTES:
                    gap = _reader_gap(
                        feed_session_id,
                        committed_sequence + 1,
                        durable_sequence,
                        "journal_batch_payload_limit_exceeded",
                    )
                    break
                pending_digest.update(raw_line)
                pending_rows.append(MappingProxyType(dict(row)))
                expected_sequence += 1

            if gap is not None or limited:
                break

        if (
            gap is None
            and not limited
            and committed_sequence >= durable_sequence
            and handle.tell() != durable_offset
        ):
            gap = _reader_gap(
                feed_session_id,
                durable_sequence,
                durable_sequence,
                "durable_offset_not_commit_boundary",
            )

    return DurableTickBatch(
        records=tuple(records),
        next_cursor=next_cursor,
        durable_through=durable_through,
        caught_up=bool(
            gap is None
            and not limited
            and committed_sequence >= durable_sequence
        ),
        gap=gap,
    )


def _read_legacy_after(
    path: Path,
    cursor: DurableTickCursor | None,
    *,
    durable_through: DurableTickCursor,
    limit: int,
) -> DurableTickBatch:
    feed_session_id = durable_through.feed_session_id
    durable_sequence = int(durable_through.ingress_sequence)
    if not path.exists():
        gap = _reader_gap(feed_session_id, 1, durable_sequence, "journal_missing")
        return DurableTickBatch((), cursor, durable_through, False, gap)
    file_size = path.stat().st_size
    durable_offset = int(durable_through.journal_byte_offset)
    hard_end = durable_offset if durable_offset > 0 else file_size
    if hard_end > file_size:
        gap = _reader_gap(
            feed_session_id,
            1,
            durable_sequence,
            "durable_cursor_offset_beyond_journal",
        )
        return DurableTickBatch((), cursor, durable_through, False, gap)

    after_sequence = int(cursor.ingress_sequence) if cursor else 0
    expected_sequence = after_sequence + 1 if cursor and cursor.journal_byte_offset > 0 else 1
    next_cursor = cursor
    records: list[Mapping[str, Any]] = []
    page_bytes = 0
    gap: TickStreamGap | None = None
    limited = False
    final_position = 0
    with path.open("rb") as handle:
        if cursor is not None and cursor.journal_byte_offset > 0:
            cursor_offset = int(cursor.journal_byte_offset)
            if cursor_offset > hard_end:
                gap = _reader_gap(
                    feed_session_id,
                    durable_sequence + 1,
                    cursor.ingress_sequence,
                    "cursor_offset_ahead_of_durable_watermark",
                )
                return DurableTickBatch((), cursor, durable_through, False, gap)
            handle.seek(cursor_offset - 1)
            if handle.read(1) != b"\n":
                gap = _reader_gap(
                    feed_session_id,
                    cursor.ingress_sequence + 1,
                    durable_sequence,
                    "cursor_offset_not_record_boundary",
                )
                return DurableTickBatch((), cursor, durable_through, False, gap)
            handle.seek(cursor_offset)

        observed_sequence = after_sequence if handle.tell() else 0
        while observed_sequence < durable_sequence:
            raw_line, row, parse_error = _read_record_within(
                handle,
                hard_end=hard_end,
            )
            line_end = handle.tell()
            if parse_error:
                gap = _reader_gap(
                    feed_session_id,
                    observed_sequence + 1,
                    durable_sequence,
                    parse_error,
                )
                break
            if row.get(JOURNAL_RECORD_TYPE_FIELD):
                gap = _reader_gap(
                    feed_session_id,
                    observed_sequence + 1,
                    durable_sequence,
                    "legacy_journal_unknown_record",
                )
                break
            if _clean(row.get("feed_session_id")) != feed_session_id:
                gap = _reader_gap(
                    feed_session_id,
                    observed_sequence + 1,
                    durable_sequence,
                    "journal_feed_session_mismatch",
                )
                break
            sequence = _strict_json_int(row.get("ingress_sequence"))
            if sequence is None:
                sequence = 0
            if sequence != expected_sequence:
                gap = _reader_gap(
                    feed_session_id,
                    expected_sequence,
                    max(expected_sequence, sequence - 1),
                    "journal_sequence_gap",
                )
                break
            observed_sequence = sequence
            expected_sequence += 1
            if sequence <= after_sequence:
                continue
            if len(records) >= limit:
                limited = True
                break
            if records and page_bytes + len(raw_line) > MAX_JOURNAL_PAGE_BYTES:
                limited = True
                break
            records.append(MappingProxyType(dict(row)))
            page_bytes += len(raw_line)
            next_cursor = DurableTickCursor(
                feed_session_id,
                sequence,
                journal_byte_offset=line_end,
                journal_schema=JOURNAL_SCHEMA_LEGACY_V0,
            )
        final_position = handle.tell()

    if (
        gap is None
        and not limited
        and durable_offset > 0
        and observed_sequence >= durable_sequence
        and final_position != hard_end
    ):
        gap = _reader_gap(
            feed_session_id,
            durable_sequence,
            durable_sequence,
            "durable_offset_not_sequence_boundary",
        )
    next_sequence = next_cursor.ingress_sequence if next_cursor is not None else 0
    return DurableTickBatch(
        records=tuple(records),
        next_cursor=next_cursor,
        durable_through=durable_through,
        caught_up=bool(
            gap is None
            and not limited
            and next_sequence >= durable_sequence
        ),
        gap=gap,
    )


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
        if type(limit) is not int or limit <= 0:
            raise ValueError("limit must be an exact positive integer")
        supported_schemas = {
            JOURNAL_SCHEMA_FRAMED_V1,
            JOURNAL_SCHEMA_LEGACY_V0,
        }
        durable_schema = durable_through.journal_schema
        if durable_schema not in supported_schemas:
            gap = _reader_gap(
                _clean(durable_through.feed_session_id) or "unknown_feed",
                1,
                1,
                "journal_schema_missing_or_unsupported",
            )
            return DurableTickBatch((), cursor, durable_through, False, gap)
        if not _clean(durable_through.feed_session_id):
            gap = _reader_gap(
                "unknown_feed",
                1,
                1,
                "durable_feed_session_id_missing",
            )
            return DurableTickBatch((), cursor, durable_through, False, gap)
        if (
            type(durable_through.ingress_sequence) is not int
            or durable_through.ingress_sequence < 0
            or type(durable_through.journal_byte_offset) is not int
            or durable_through.journal_byte_offset < 0
        ):
            gap = _reader_gap(
                durable_through.feed_session_id,
                1,
                1,
                "durable_cursor_numeric_fields_invalid",
            )
            return DurableTickBatch((), cursor, durable_through, False, gap)
        if (
            durable_schema == JOURNAL_SCHEMA_FRAMED_V1
            and (
                (
                    durable_through.ingress_sequence > 0
                    and durable_through.journal_byte_offset == 0
                )
                or (
                    durable_through.ingress_sequence == 0
                    and durable_through.journal_byte_offset != 0
                )
            )
        ):
            reason = (
                "framed_durable_cursor_offset_missing"
                if durable_through.ingress_sequence > 0
                else "framed_zero_sequence_offset_nonzero"
            )
            gap = _reader_gap(
                durable_through.feed_session_id,
                1,
                max(1, durable_through.ingress_sequence),
                reason,
            )
            return DurableTickBatch((), cursor, durable_through, False, gap)
        if (
            durable_schema == JOURNAL_SCHEMA_LEGACY_V0
            and durable_through.ingress_sequence == 0
            and durable_through.journal_byte_offset != 0
        ):
            gap = _reader_gap(
                durable_through.feed_session_id,
                1,
                1,
                "legacy_zero_sequence_offset_nonzero",
            )
            return DurableTickBatch((), cursor, durable_through, False, gap)
        if cursor is not None:
            if (
                not _clean(cursor.feed_session_id)
                or type(cursor.ingress_sequence) is not int
                or cursor.ingress_sequence < 0
                or type(cursor.journal_byte_offset) is not int
                or cursor.journal_byte_offset < 0
            ):
                gap = _reader_gap(
                    durable_through.feed_session_id,
                    1,
                    max(1, durable_through.ingress_sequence),
                    "cursor_fields_invalid",
                )
                return DurableTickBatch((), cursor, durable_through, False, gap)
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
        if cursor is not None and cursor.ingress_sequence > durable_through.ingress_sequence:
            gap = _reader_gap(
                durable_through.feed_session_id,
                durable_through.ingress_sequence + 1,
                cursor.ingress_sequence,
                "cursor_ahead_of_durable_watermark",
            )
            return DurableTickBatch((), cursor, durable_through, False, gap)
        if cursor is not None and cursor.journal_schema != durable_through.journal_schema:
            gap = _reader_gap(
                durable_through.feed_session_id,
                cursor.ingress_sequence + 1,
                durable_through.ingress_sequence,
                "cursor_journal_schema_mismatch",
            )
            return DurableTickBatch((), cursor, durable_through, False, gap)
        if (
            cursor is not None
            and cursor.journal_schema == JOURNAL_SCHEMA_FRAMED_V1
            and (
                (cursor.ingress_sequence > 0 and cursor.journal_byte_offset == 0)
                or (
                    cursor.ingress_sequence == 0
                    and cursor.journal_byte_offset != 0
                )
            )
        ):
            reason = (
                "framed_cursor_offset_missing"
                if cursor.ingress_sequence > 0
                else "framed_zero_sequence_offset_nonzero"
            )
            gap = _reader_gap(
                durable_through.feed_session_id,
                cursor.ingress_sequence + 1,
                durable_through.ingress_sequence,
                reason,
            )
            return DurableTickBatch((), cursor, durable_through, False, gap)
        if (
            cursor is not None
            and cursor.journal_schema == JOURNAL_SCHEMA_LEGACY_V0
            and cursor.ingress_sequence == 0
            and cursor.journal_byte_offset != 0
        ):
            gap = _reader_gap(
                durable_through.feed_session_id,
                1,
                max(1, durable_through.ingress_sequence),
                "legacy_zero_sequence_offset_nonzero",
            )
            return DurableTickBatch((), cursor, durable_through, False, gap)
        if durable_through.ingress_sequence == 0:
            return DurableTickBatch(
                records=(),
                next_cursor=cursor,
                durable_through=durable_through,
                caught_up=True,
                gap=None,
            )
        if (
            cursor is not None
            and cursor.ingress_sequence > 0
            and cursor.journal_schema == JOURNAL_SCHEMA_LEGACY_V0
        ):
            cursor_error = _validate_cursor_record(
                self.journal_segment_path,
                cursor,
            )
            if cursor_error:
                gap = _reader_gap(
                    durable_through.feed_session_id,
                    cursor.ingress_sequence,
                    durable_through.ingress_sequence,
                    cursor_error,
                )
                return DurableTickBatch((), cursor, durable_through, False, gap)
        if (
            cursor is not None
            and cursor.ingress_sequence == durable_through.ingress_sequence
        ):
            if cursor.journal_byte_offset != durable_through.journal_byte_offset:
                gap = _reader_gap(
                    durable_through.feed_session_id,
                    durable_through.ingress_sequence,
                    durable_through.ingress_sequence,
                    "cursor_offset_mismatch_at_durable_watermark",
                )
                return DurableTickBatch((), cursor, durable_through, False, gap)
            if cursor.journal_schema == JOURNAL_SCHEMA_LEGACY_V0:
                return DurableTickBatch((), cursor, durable_through, True, None)

        if durable_through.journal_schema == JOURNAL_SCHEMA_FRAMED_V1:
            return _read_framed_after(
                self.journal_segment_path,
                cursor,
                durable_through=durable_through,
                limit=limit,
            )
        if durable_through.journal_schema == JOURNAL_SCHEMA_LEGACY_V0:
            return _read_legacy_after(
                self.journal_segment_path,
                cursor,
                durable_through=durable_through,
                limit=limit,
            )
        raise AssertionError("validated journal schema dispatch fell through")
