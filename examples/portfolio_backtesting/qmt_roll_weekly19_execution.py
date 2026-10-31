"""Weekly19 execution admission. Pure checks: never connects or submits.

The caller still must verify the release, qualification, activation and receipt.
An allowed result is not an authorization or production qualification.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any, Mapping

from qmt_roll_official_execution_profile import WEEKLY19_15W_R150K_PROFILE as PROFILE
from qmt_roll_weekly19_funding import assert_open_funding_ready


class Weekly19ExecutionError(ValueError):
    pass


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise Weekly19ExecutionError(reason)


def _number(value: Any, *, positive: bool = False) -> Decimal:
    _require(not isinstance(value, bool), 'weekly19_number_invalid')
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise Weekly19ExecutionError('weekly19_number_invalid') from exc
    _require(number.is_finite() and (not positive or number > 0), 'weekly19_number_invalid')
    return number


def _time(value: Any) -> datetime:
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError as exc:
        raise Weekly19ExecutionError('weekly19_timestamp_invalid') from exc
    _require(result.tzinfo is not None, 'weekly19_timestamp_timezone_missing')
    return result


def _fresh(observed: Any, now: datetime, seconds: int) -> None:
    age = (now - _time(observed)).total_seconds()
    _require(0 <= age <= seconds, 'weekly19_snapshot_stale_or_future')


def _raw(envelope: Any) -> dict[str, Any]:
    _require(isinstance(envelope, Mapping), 'weekly19_raw_evidence_missing')
    payload = envelope.get('raw_payload')
    _require(isinstance(payload, str), 'weekly19_raw_payload_invalid')
    _require(hashlib.sha256(payload.encode('utf8')).hexdigest() == envelope.get('raw_sha256'),
             'weekly19_raw_evidence_hash_mismatch')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, 'weekly19_raw_duplicate_key')
            result[key] = value
        return result
    try:
        raw = json.loads(payload, object_pairs_hook=unique,
                         parse_constant=lambda _: (_ for _ in ()).throw(Weekly19ExecutionError('weekly19_raw_nonfinite')))
    except (ValueError, TypeError) as exc:
        raise Weekly19ExecutionError('weekly19_raw_payload_invalid') from exc
    _require(isinstance(raw, dict), 'weekly19_raw_payload_invalid')
    return raw


def _bound(raw: Mapping[str, Any], context: Mapping[str, Any], now: datetime) -> None:
    _require(raw.get('account_key') == context['account_fingerprint'], 'weekly19_account_mismatch')
    _require(raw.get('material_release_id') == context['material_release_id'], 'weekly19_release_mismatch')
    _require(raw.get('trading_day') == context['trading_date'], 'weekly19_trading_day_mismatch')
    _require(raw.get('query_complete') is True, 'weekly19_broker_query_incomplete')
    _require(type(raw.get('query_reqid')) is int and raw['query_reqid'] > 0, 'weekly19_query_reqid_invalid')
    _require(bool(raw.get('generation_uuid')), 'weekly19_generation_missing')
    _fresh(raw.get('observed_at'), now, 300)


def _query(envelope: Any, kind: str, context: Mapping[str, Any], now: datetime) -> dict:
    raw = _raw(envelope)
    _require(raw.get('schema') == f'weekly19.ctp-{kind}.v1', 'weekly19_query_schema_mismatch')
    source = 'ctp_position_query' if kind == 'positions' else 'ctp_order_query'
    _require(raw.get('source_kind') == source, 'weekly19_query_source_mismatch')
    _bound(raw, context, now)
    _require(isinstance(raw.get(kind), list), 'weekly19_query_rows_missing')
    return raw


def assert_intent_identity(intent: Mapping[str, Any], context: Mapping[str, Any]) -> None:
    for field, expected in (
        ('execution_profile', PROFILE.profile_key), ('official_live_version', PROFILE.official_version),
        ('capital_label', PROFILE.capital_label), ('ruleset_version', PROFILE.ruleset_version),
        ('material_release_id', context['material_release_id']),
        ('account_fingerprint', context['account_fingerprint']), ('trading_date', context['trading_date']),
        ('data_receipt_sha256', context['data_receipt_sha256']),
    ):
        _require(intent.get(field) == expected, f'weekly19_{field}_mismatch')
    _require(_number(intent.get('capital')) == Decimal(str(PROFILE.capital)), 'weekly19_capital_mismatch')
    _require(intent.get('source') in PROFILE.allowed_intent_sources, 'weekly19_intent_source_forbidden')
    _require(intent.get('offset') in {'open', 'close'}, 'weekly19_offset_invalid')
    _require(intent.get('direction') in {'long', 'short'}, 'weekly19_direction_invalid')
    for field in ('intent_id', 'signal_order_id', 'signal_datetime', 'physical_epoch_id', 'vt_symbol'):
        _require(isinstance(intent.get(field), str) and bool(intent[field]), f'weekly19_{field}_missing')
    identity = intent.get('signal_identity')
    _require(isinstance(identity, Mapping), 'weekly19_signal_identity_missing')
    for field in ('intent_id', 'signal_order_id', 'signal_datetime', 'trading_date'):
        expected = (intent.get('planned_intent_id') or intent.get('intent_id')) if field == 'intent_id' else intent.get(field)
        _require(identity.get(field) == expected, 'weekly19_signal_identity_mismatch')
    _require(intent.get('target_date') == context['target_cutoff_date'], 'weekly19_completed_target_date_mismatch')
    _require(str(intent['signal_datetime'])[:10] >= context['cold_start_date'], 'weekly19_signal_before_activation')
    _require(intent.get('protection_timing') == 'fresh_completed_week_close', 'weekly19_intraday_protection_forbidden')
    _require(not any(intent.get(k) for k in ('monitor_run_id', 'action_id', 'retry_trigger_price', 'retry_stop_price')),
             'weekly19_c9_metadata_forbidden')
    if intent['offset'] == 'open':
        _require(intent['source'] == 'weekly19_pending_order', 'weekly19_open_source_invalid')
        _require(intent.get('intent_kind') in {'native_entry', 'rollover_reopen'}, 'weekly19_open_kind_invalid')
    else:
        _require(intent['source'] == 'weekly19_risk_reduce', 'weekly19_close_source_invalid')
        _require(intent.get('intent_kind') in {'risk_close', 'rollover_close'}, 'weekly19_close_kind_invalid')


def _execution_ledger_gate(intent, context):
    """Identity projections are never interpreted as callback status rows.

    An existing native binding can only belong to the exact currently leased
    physical batch, proved by the private quota reader and the runner's actual
    immutable parent/manifest. Every older delivery remains a duplicate.
    """
    rows = context.get('execution_ledger_rows', [])
    from qmt_roll_weekly19_broker_evidence import _VerifiedExecutionBindings, _require_verified_execution_bindings
    typed = isinstance(rows, _VerifiedExecutionBindings)
    if typed:
        _require_verified_execution_bindings(rows, True)
    owned_ids = set()
    for row in rows:
        matches = (row.get('intent_id') == intent['intent_id'] or
                   (row.get('planned_intent_id') and row.get('planned_intent_id') == intent.get('planned_intent_id')))
        if not matches:
            continue
        _require(row.get('material_release_id') == context['material_release_id'], 'weekly19_ledger_release_mismatch')
        _require(row.get('account_key') if typed else row.get('account_fingerprint'), 'weekly19_ledger_account_mismatch')
        _require((row.get('account_key') if typed else row.get('account_fingerprint')) == context['account_fingerprint'], 'weekly19_ledger_account_mismatch')
        lease = context.get('current_delivery_lease') or {}
        if typed:
            batch = context.get('current_physical_batch') or {}
            manifest = batch.get('weekly19_batch_manifest') or {}
            parent = context.get('immutable_parent_intent') or {}
            _require(lease.get('intent_id') == intent['intent_id'] == row.get('intent_id') == parent.get('intent_id') == manifest.get('intent_id')
                     and manifest.get('planned_intent_id') == row.get('planned_intent_id') == parent.get('planned_intent_id')
                     and manifest.get('signal_identity') == row.get('signal_identity') == parent.get('signal_identity') == intent['signal_identity']
                     and lease.get('lease_token') and lease['lease_token'] == manifest.get('spool_lease_token')
                     and lease.get('payload_sha256') == manifest.get('intent_payload_sha256')
                     and lease.get('lease_owner') == manifest.get('service_generation')
                     and lease.get('connection_generation') == manifest.get('connection_generation'), 'weekly19_intent_already_bound_other_delivery')
            _require(batch.get('api_slot_batch_id') and batch['api_slot_batch_id'] == row.get('api_slot_batch_id') == row.get('execution_batch_id')
                     and manifest.get('expected_children') == row.get('expected_children')
                     and manifest.get('expected_children_sha256') == row.get('expected_children_sha256')
                     and manifest.get('expected_children_sha256') == hashlib.sha256(json.dumps(manifest['expected_children'],ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
                     and _number(manifest.get('approved_parent_volume'),positive=True) == _number(parent.get('planned_volume'),positive=True) == _number(row.get('approved_parent_volume'),positive=True),
                     'weekly19_owned_physical_batch_mismatch')
            for key in ('vt_symbol','direction','offset'):
                _require(row.get(key) == parent.get(key) == intent.get(key), 'weekly19_owned_physical_identity_mismatch')
            owned_ids.add(row['broker_order_id'])
            continue
        own_zero_native = bool(row.get('event_type') in {'reserved', 'api_slot_reserved'} and
            lease.get('intent_id') == intent['intent_id'] == row.get('intent_id') and
            lease.get('payload_sha256') == row.get('intent_payload_sha256') and
            lease.get('lease_token') and lease.get('lease_token') == row.get('spool_lease_token') and
            not row.get('send_order_api_called_count') and not row.get('filled_volume'))
        if own_zero_native:
            continue
        _require(row.get('status') in {'cancelled','rejected'} and not row.get('filled_volume'), 'weekly19_intent_already_reserved_or_filled')
    return owned_ids


def _evaluate(intent: Mapping[str, Any], context: Mapping[str, Any], now: datetime) -> int:
    _require(now.tzinfo is not None, 'weekly19_now_timezone_missing')
    assert_intent_identity(intent, context)
    requested = _number(intent.get('planned_volume'), positive=True)
    _require(requested == requested.to_integral_value(), 'weekly19_volume_noninteger')
    volume = int(requested)
    snapshot = context['broker_snapshot']
    positions = _query(snapshot.get('positions'), 'positions', context, now)
    orders = _query(snapshot.get('orders'), 'orders', context, now)
    _require(positions['generation_uuid'] == orders['generation_uuid'], 'weekly19_broker_generation_mismatch')
    owned_broker_ids = _execution_ledger_gate(intent, context)
    for row in orders['orders']:
        _require(isinstance(row, Mapping), 'weekly19_order_row_invalid')
        _require(row.get('status') in {'filled', 'cancelled', 'rejected'} or
                 row.get('broker_order_id') in owned_broker_ids and row.get('status') in {'accepted','working','partially_filled'}, 'weekly19_active_or_unknown_order')
    for row in positions['positions']:
        _require(isinstance(row, Mapping) and row.get('direction') in {'long', 'short'}
                 and bool(row.get('vt_symbol')), 'weekly19_position_row_invalid')
        amount = _number(row.get('volume'))
        _require(amount >= 0 and amount == amount.to_integral_value(), 'weekly19_position_volume_invalid')
    metadata, quote, session = context['metadata'], context['quote'], context['session']
    _require(metadata.get('vt_symbol') == intent['vt_symbol'], 'weekly19_contract_mismatch')
    _require((quote.get('vt_symbol') or quote.get('symbol')) == intent['vt_symbol'], 'weekly19_contract_mismatch')
    if quote.get('vt_symbol') and quote.get('symbol'):
        _require(quote['vt_symbol'] == quote['symbol'], 'weekly19_quote_symbol_alias_mismatch')
    _require(metadata.get('physical_epoch_id') == intent['physical_epoch_id'], 'weekly19_epoch_mismatch')
    tick = _number(metadata.get('pricetick'), positive=True)
    price = _number(intent.get('limit_price'), positive=True)
    _require(price % tick == 0, 'weekly19_price_not_on_tick')
    _require(_number(metadata.get('min_volume'), positive=True) <= volume <=
             _number(metadata.get('max_volume'), positive=True), 'weekly19_contract_volume_limit')
    _fresh(quote.get('observed_at'), now, 30)
    _require(_number(quote.get('bid'), positive=True) <= _number(quote.get('ask'), positive=True), 'weekly19_quote_crossed')
    _require(session.get('is_open') is True and quote.get('session_id') == session.get('session_id'), 'weekly19_session_not_open')
    _require(session.get('trading_date') == context['trading_date'] == quote.get('trading_date'), 'weekly19_session_day_mismatch')
    _require(_time(session.get('starts_at')) <= now < _time(session.get('ends_at')), 'weekly19_outside_session')
    if intent['offset'] == 'close':
        direction = 'short' if intent['direction'] == 'long' else 'long'
        actual = sum((_number(row['volume']) for row in positions['positions']
                      if row['vt_symbol'] == intent['vt_symbol'] and row['direction'] == direction), Decimal(0))
        _require(volume <= actual, 'weekly19_close_exceeds_actual_position')
        return volume
    account = _raw(snapshot.get('account'))
    _bound(account, context, now)
    _require(account.get('generation_uuid') == positions['generation_uuid'], 'weekly19_broker_generation_mismatch')
    cash = context['confirmed_cash_state']
    _require(cash.get('revision') == intent.get('requires_funding_revision'), 'weekly19_funding_revision_changed')
    assert_open_funding_ready(cash, snapshot['account'], now)
    proof = context.get('open_risk_proof')
    _require(isinstance(proof, Mapping) and proof.get('schema') == 'weekly19.open-risk-proof.v1',
             'weekly19_current_original_risk_proof_required')
    _require(proof.get('intent_id') == (intent.get('planned_intent_id') or intent['intent_id']), 'weekly19_risk_signal_mismatch')
    quote_hash = hashlib.sha256(json.dumps(dict(quote), ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    _require(proof.get('account_raw_sha256') == snapshot['account']['raw_sha256'] and
             proof.get('quote_sha256') == quote_hash and proof.get('quote_session_id') == quote['session_id'],
             'weekly19_risk_fresh_source_mismatch')
    if intent.get('weekly19_quote_proof'):
        _require(intent['weekly19_quote_proof'].get('durable_state_sha256') == context['durable_state_sha256'],
                 'weekly19_execution_state_changed_reassemble_quote_intent')
    _require(proof.get('source_data_receipt_sha256') == context['data_receipt_sha256'] and
             proof.get('durable_state_sha256') == context['durable_state_sha256'] and
             proof.get('confirmed_funding_revision') == cash['revision'], 'weekly19_risk_state_or_receipt_mismatch')
    _require(_number(proof.get('current_equity')) == _number(account['Balance']) and
             _number(proof.get('current_available')) == _number(account['Available']), 'weekly19_risk_equity_mismatch')
    reference = _number(quote['ask'] if intent['direction'] == 'long' else quote['bid'], positive=True)
    _require(_number(proof.get('execution_reference'), positive=True) == reference, 'weekly19_risk_quote_mismatch')
    stop = _number(proof.get('stop_price'), positive=True)
    _require(stop < reference if intent['direction'] == 'long' else stop > reference, 'weekly19_risk_stop_direction_invalid')
    selected = proof.get('selected_volume')
    _require(type(selected) is int and selected > 0 and not proof.get('blocked_reason'), 'weekly19_original_risk_has_no_capacity')
    volume = min(volume, selected)
    _require(_number(proof.get('approved_volume_cap'), positive=True) >= volume, 'weekly19_risk_plan_volume_cap_exceeded')
    available = _number(account.get('Available'))
    required = max(price, reference) * _number(metadata.get('size'), positive=True) * _number(metadata.get('broker_margin_rate'), positive=True) * volume
    _require(available >= required, 'weekly19_real_available_insufficient')
    if intent['intent_kind'] == 'rollover_reopen':
        dependency = intent.get('depends_on_close_intent_id')
        _require(bool(dependency), 'weekly19_roll_close_dependency_missing')
        completed = [row for row in context.get('completed_close_intents', []) if row.get('intent_id') == dependency]
        _require(len(completed) == 1, 'weekly19_roll_close_not_confirmed')
        close = completed[0]
        _require(close.get('material_release_id') == context['material_release_id'] and
                 close.get('account_fingerprint') == context['account_fingerprint'] and close.get('offset') == 'close',
                 'weekly19_roll_close_identity_mismatch')
        _require(_number(close.get('requested_volume'), positive=True) == _number(close.get('filled_volume')) and
                 bool(close.get('trade_ids')), 'weekly19_roll_close_not_fully_filled')
        _require(close.get('vt_symbol') == intent.get('rollover_from_vt_symbol'), 'weekly19_roll_contract_mismatch')
        fills = close.get('broker_fills')
        _require(isinstance(fills, list) and bool(fills), 'weekly19_roll_actual_fill_evidence_missing')
        trade_ids = set()
        filled = Decimal(0)
        for evidence in fills:
            fill = _raw(evidence)
            _require(fill.get('schema') == 'weekly19.ctp-trade.v1' and
                     fill.get('source_kind') == 'ctp_trade_callback', 'weekly19_roll_fill_source_invalid')
            _require(fill.get('account_key') == context['account_fingerprint'] and
                     fill.get('material_release_id') == context['material_release_id'] and
                     fill.get('intent_id') == dependency and fill.get('vt_symbol') == close['vt_symbol'] and
                     fill.get('offset') == 'close', 'weekly19_roll_fill_identity_mismatch')
            trade_id = fill.get('trade_id')
            _require(isinstance(trade_id, str) and bool(trade_id) and trade_id not in trade_ids,
                     'weekly19_roll_fill_duplicate_or_missing')
            _require(_time(fill.get('trade_datetime')) <= _time(positions['observed_at']),
                     'weekly19_roll_positions_precede_fill')
            trade_ids.add(trade_id)
            filled += _number(fill.get('volume'), positive=True)
        _require(trade_ids == set(close['trade_ids']) and filled == _number(close['filled_volume']),
                 'weekly19_roll_fill_volume_mismatch')
        _require(not any(row['vt_symbol'] == close['vt_symbol'] and _number(row['volume']) > 0 for row in positions['positions']),
                 'weekly19_roll_old_position_not_flat')
    return volume


def evaluate_intent(intent: Mapping[str, Any], context: Mapping[str, Any], *, now: datetime) -> dict[str, Any]:
    """Validate one candidate against fresh read-only evidence without mutation."""
    blockers: list[str] = []
    volume = 0
    try:
        volume = _evaluate(intent, context, now)
    except (ValueError, TypeError, KeyError, AttributeError, InvalidOperation) as exc:
        blockers.append(str(exc) if isinstance(exc, ValueError) else 'weekly19_execution_context_missing_or_invalid')
    return dict(schema='weekly19.execution-gate.v1', intent_id=intent.get('intent_id', ''),
                allowed=not blockers, blockers=blockers, volume=volume,
                execution_profile=PROFILE.profile_key, production_qualified=False,
                order_api_called_count=0, send_order_api_called_count=0, cancel_order_api_called_count=0)
