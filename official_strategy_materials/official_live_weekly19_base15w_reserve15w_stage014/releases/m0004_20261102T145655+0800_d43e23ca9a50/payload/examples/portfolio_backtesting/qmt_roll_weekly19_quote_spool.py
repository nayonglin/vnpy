"""Bind a weekly plan to a real durable MD quote and the existing spool.

No tick is generated here. Callers must supply the canonical live journal and
its actual committed cursor. Offline fixtures are not production evidence.
"""
from __future__ import annotations

from dataclasses import asdict
from collections import OrderedDict
from datetime import datetime, timezone
from threading import RLock
import hashlib
import math
import json
import os
from pathlib import Path
import stat
from typing import Any, Mapping

from qmt_roll_official_execution_profile import WEEKLY19_15W_R150K_PROFILE as PROFILE
from qmt_roll_official_live_tick_reader import TickStreamJournalReader
from qmt_roll_official_live_tick_types import DurableTickCursor, JOURNAL_SCHEMA_FRAMED_V1
from qmt_roll_official_live_trace import LatencyTrace, ClockStamp


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _prefix_digest(path: Path, length: int) -> str:
    metadata = path.lstat()
    _require(stat.S_ISREG(metadata.st_mode) and not path.is_symlink() and metadata.st_uid == os.getuid()
             and not stat.S_IMODE(metadata.st_mode) & 0o022, 'weekly19_quote_journal_security_invalid')
    _require(type(length) is int and 0 < length <= metadata.st_size, 'weekly19_quote_cursor_outside_journal')
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        remaining = length
        while remaining:
            block = handle.read(min(1024 * 1024, remaining))
            _require(bool(block), 'weekly19_quote_journal_truncated')
            digest.update(block)
            remaining -= len(block)
    return digest.hexdigest()


# This cache saves JSON decoding, never the integrity read. Each access still
# hashes the actual committed prefix. Incremental reuse first verifies the old
# prefix against its previously admitted SHA, so a rewrite is never rescued by
# treating it as a new quote. All callers receive detached row dictionaries.
_QUOTE_CACHE = OrderedDict()
_QUOTE_CACHE_LOCK = RLock()


def _cursor_key(cursor):
    return (cursor.feed_session_id, cursor.ingress_sequence,
            cursor.journal_byte_offset, cursor.journal_schema)


def _latest_quote(path, cursor, symbol):
    _require(isinstance(cursor, DurableTickCursor) and cursor.journal_schema == JOURNAL_SCHEMA_FRAMED_V1,
             'weekly19_quote_framed_cursor_required')
    path = Path(path).absolute()
    before = _prefix_digest(path, cursor.journal_byte_offset)
    st = path.lstat()
    file_key = (str(path), st.st_dev, st.st_ino, cursor.feed_session_id)
    key = _cursor_key(cursor)
    with _QUOTE_CACHE_LOCK:
        snapshots = _QUOTE_CACHE.setdefault(file_key, OrderedDict())
        _QUOTE_CACHE.move_to_end(file_key)
        while len(_QUOTE_CACHE) > 8:
            _QUOTE_CACHE.popitem(last=False)
        cached = snapshots.get(key)
        if cached is not None:
            _require(cached['sha256'] == before, 'weekly19_quote_journal_changed')
            _require(symbol in cached['rows'], 'weekly19_quote_symbol_missing')
            return dict(cached['rows'][symbol]), before
        previous = None
        rows = {}
        bases = [entry for entry in snapshots.values()
                 if entry['cursor'].journal_byte_offset < cursor.journal_byte_offset
                 and entry['cursor'].ingress_sequence <= cursor.ingress_sequence]
        if bases:
            base = max(bases, key=lambda entry: entry['cursor'].journal_byte_offset)
            _require(_prefix_digest(path, base['cursor'].journal_byte_offset) == base['sha256'],
                     'weekly19_quote_journal_changed')
            previous = base['cursor']
            rows = dict(base['rows'])
        reader = TickStreamJournalReader(path)
        while True:
            batch = reader.read_after(previous, durable_through=cursor, limit=4096)
            _require(batch.gap is None, 'weekly19_quote_journal_gap_or_invalid_commit')
            for row in batch.records:
                if row.get('vt_symbol'):
                    rows[row['vt_symbol']] = dict(row)
            if batch.caught_up:
                break
            _require(batch.next_cursor is not None and batch.next_cursor != previous,
                     'weekly19_quote_journal_no_progress')
            previous = batch.next_cursor
        _require(before == _prefix_digest(path, cursor.journal_byte_offset), 'weekly19_quote_journal_changed')
        snapshots[key] = dict(cursor=cursor, sha256=before, rows=rows)
        while len(snapshots) > 256:
            snapshots.popitem(last=False)
        _require(symbol in rows, 'weekly19_quote_symbol_missing')
        return dict(rows[symbol]), before


def read_weekly19_quote_snapshot(journal_segment_path, *, durable_through, symbol,
                               clock, trading_date, session):
    """Read a genuine committed ingress quote, never a bar or generated tick.

    The process-local caller binds the broker TradingDay and the authoritative
    session. Integrity remains tied to the real framed row and dual clock.
    """
    row, _ = _latest_quote(journal_segment_path, durable_through, symbol)
    trace = LatencyTrace.from_ingress_row(row, clock=clock)
    now = ClockStamp.from_clock(clock)
    ingress = trace.stamps['gateway_ingress']
    _require(ingress.epoch_ns <= now.epoch_ns < trace.deadline_epoch_ns
             and ingress.monotonic_ns <= now.monotonic_ns < trace.deadline_monotonic_ns,
             'weekly19_quote_expired_or_future')
    _require(session.get('trading_date') == trading_date and bool(session.get('session_id')),
             'weekly19_quote_session_binding_missing')
    bid, ask = row.get('bid_price_1'), row.get('ask_price_1')
    _require(type(bid) in (int, float) and type(ask) in (int, float) and math.isfinite(bid) and math.isfinite(ask) and 0 < bid <= ask,
             'weekly19_quote_executable_side_missing')
    return dict(symbol=symbol, vt_symbol=symbol, bid=bid, ask=ask,
        observed_at=datetime.fromtimestamp(row['ingress_epoch_ns']/1_000_000_000,tz=timezone.utc).isoformat(),
        trading_date=trading_date, session_id=session['session_id'],
        quote_row_sha256=_digest(row), source_feed_session_id=row['feed_session_id'],
        source_ingress_sequence=row['ingress_sequence'])


def validate_weekly19_quote_proof(payload: Mapping[str, Any], trace: LatencyTrace) -> None:
    _require(payload.get('execution_profile') == PROFILE.profile_key and payload.get('source') in PROFILE.allowed_intent_sources,
             'weekly19_quote_profile_or_source_mismatch')
    proof = payload.get('weekly19_quote_proof')
    _require(isinstance(proof, Mapping) and proof.get('schema') == 'weekly19.durable-quote.v1', 'weekly19_quote_proof_missing')
    cursor = DurableTickCursor(**proof['durable_cursor'])
    for field in ('feed_session_id', 'ingress_sequence', 'journal_byte_offset', 'journal_schema'):
        _require(payload.get('durable_cursor_' + field) == getattr(cursor, field), 'weekly19_quote_cursor_binding_mismatch')
    row, prefix = _latest_quote(Path(proof['journal_segment_path']), cursor, payload['vt_symbol'])
    _require(prefix == proof.get('journal_prefix_sha256') and _digest(row) == proof.get('quote_row_sha256'),
             'weekly19_quote_proof_digest_mismatch')
    _require(row['feed_session_id'] == trace.feed_session_id and row['ingress_sequence'] == trace.ingress_sequence
             and row['symbol_sequence'] == trace.symbol_sequence and row['vt_symbol'] == trace.vt_symbol,
             'weekly19_quote_trace_source_mismatch')
    ingress = trace.stamps['gateway_ingress']
    _require(row['ingress_epoch_ns'] == ingress.epoch_ns and row['ingress_monotonic_ns'] == ingress.monotonic_ns
             and row['clock_domain_id'] == ingress.clock_domain_id, 'weekly19_quote_trace_ingress_mismatch')
    _require('weekly19_quote_admitted' in trace.stamps and 'stage904_detected' not in trace.stamps,
             'weekly19_c9_detector_trace_forbidden')
    _require(payload.get('signal_identity', {}).get('intent_id') == payload.get('planned_intent_id'),
             'weekly19_quote_signal_identity_mismatch')
    _require(payload.get('data_receipt_sha256') == proof.get('data_receipt_sha256'), 'weekly19_quote_data_receipt_mismatch')
    _require(payload.get('state_generation') == proof.get('state_generation') and
             payload.get('position_epoch_id') == proof.get('position_epoch_id'), 'weekly19_quote_durable_generation_mismatch')


def prepare_weekly19_quote_intent(ready_row, *, journal_segment_path, durable_through, execution_state, clock):
    _require(ready_row.get('execution_profile') == PROFILE.profile_key and ready_row.get('source') in PROFILE.allowed_intent_sources,
             'weekly19_quote_profile_or_source_mismatch')
    _require(ready_row.get('executor_status') == 'dry_run_order_request_payload_ready', 'weekly19_quote_intent_not_admitted')
    for key in ('material_release_id', 'account_fingerprint'):
        _require(execution_state.get(key) == ready_row.get(key), 'weekly19_quote_state_identity_mismatch')
    revision = execution_state.get('revision')
    _require(type(revision) is int and revision >= 0, 'weekly19_quote_state_revision_invalid')
    epoch = execution_state.get('position_epoch_id')
    generation = execution_state.get('state_generation')
    _require(isinstance(epoch, str) and bool(epoch) and generation == f'{epoch}:{revision}',
             'weekly19_quote_state_generation_invalid')
    for key in ('root_position_id', 'position_cycle_id', 'durable_state_sha256'):
        _require(isinstance(execution_state.get(key), str) and bool(execution_state[key]), 'weekly19_quote_durable_state_missing')
    row, prefix = _latest_quote(journal_segment_path, durable_through, ready_row['vt_symbol'])
    trace = LatencyTrace.from_ingress_row(row, clock=clock)
    now = ClockStamp.from_clock(clock)
    _require(now.epoch_ns < trace.deadline_epoch_ns and now.monotonic_ns < trace.deadline_monotonic_ns,
             'weekly19_quote_expired')
    trace = trace.record_stamp('weekly19_quote_admitted', now).record_stamp('stage905_intent_ready', now)
    planned_id = ready_row.get('planned_intent_id') or ready_row['intent_id']
    delivery_id = 'W19EXEC-' + _digest(dict(planned_intent_id=planned_id, trace_id=trace.trace_id, state_generation=generation))
    price = row.get('ask_price_1') if ready_row['direction'] == 'long' else row.get('bid_price_1')
    _require(isinstance(price, (int, float)) and not isinstance(price, bool) and price > 0,
             'weekly19_quote_executable_side_missing')
    order = json.loads(ready_row['order_request_json'])
    order.update(intent_id=delivery_id, planned_intent_id=planned_id, price=price,
                 reference=f'Stage905PhaseD:{delivery_id}', state_generation=generation, position_epoch_id=epoch)
    core = {key: value for key, value in ready_row.items()
            if key not in {'order_request_json', 'trace_json', 'spool_payload_json', 'payload_sha256', 'weekly19_gate'}}
    core.update(intent_id=delivery_id, planned_intent_id=planned_id, signal_limit_price=ready_row['limit_price'],
        limit_price=price, resolved_limit_price=price, order_request_price=price,
        order_request=order, trace_context='weekly19_session_quote_v1', trace_id=trace.trace_id,
        intent_role='weekly19_' + ready_row['intent_kind'], root_position_id=execution_state['root_position_id'],
        position_cycle_id=execution_state['position_cycle_id'], state_generation=generation, position_epoch_id=epoch,
        deadline_epoch_ns=trace.deadline_epoch_ns, deadline_monotonic_ns=trace.deadline_monotonic_ns,
        source_feed_session_id=trace.feed_session_id, source_ingress_sequence=trace.ingress_sequence,
        source_symbol_sequence=trace.symbol_sequence, durable_cursor_feed_session_id=durable_through.feed_session_id,
        durable_cursor_ingress_sequence=durable_through.ingress_sequence,
        durable_cursor_journal_byte_offset=durable_through.journal_byte_offset,
        durable_cursor_journal_schema=durable_through.journal_schema,
        weekly19_quote_proof=dict(schema='weekly19.durable-quote.v1',
            journal_segment_path=str(Path(journal_segment_path).absolute()), durable_cursor=asdict(durable_through),
            journal_prefix_sha256=prefix, quote_row_sha256=_digest(row),
            data_receipt_sha256=ready_row['data_receipt_sha256'], state_generation=generation,
            position_epoch_id=epoch, durable_state_sha256=execution_state['durable_state_sha256']))
    for key in ('intent_role', 'root_position_id', 'position_cycle_id'):
        order[key] = core[key]
    validate_weekly19_quote_proof(core, trace)
    encoded = _json(core)
    return {**core, 'spool_payload_json': encoded, 'payload_sha256': hashlib.sha256(encoded.encode()).hexdigest(),
            'trace_json': trace.to_json(), 'order_request_json': _json(order)}


def commit_weekly19_quote_batch(connection, *, consumer_id='weekly19', expected_cursor, next_cursor, intents, clock,
                                feed_rollover_evidence=None):
    from qmt_roll_official_live_intent_spool import commit_detector_batch, record_trace_observation, read_trace_observations
    _require(consumer_id == 'weekly19', 'weekly19_spool_consumer_id_invalid')
    for item in intents:
        validate_weekly19_quote_proof(json.loads(item['spool_payload_json']), LatencyTrace.from_json(item['trace_json']))
    result = commit_detector_batch(connection, consumer_id=consumer_id, expected_cursor=expected_cursor,
        next_cursor=next_cursor, intents=intents, now_epoch_ns=clock.epoch_ns(),
        now_monotonic_ns=clock.monotonic_ns(), clock_domain_id=clock.clock_domain_id(),
        feed_rollover_evidence=feed_rollover_evidence, allow_weekly19_same_cursor_append=True)
    for item in intents:
        if 'spool_committed' not in read_trace_observations(connection, intent_id=item['intent_id']):
            record_trace_observation(connection, intent_id=item['intent_id'], stage='spool_committed',
                epoch_ns=clock.epoch_ns(), monotonic_ns=clock.monotonic_ns(), clock_domain_id=clock.clock_domain_id())
    return result
