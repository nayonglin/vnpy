"""Offline external-reserve accounting for the weekly19 candidate.

This module neither transfers money nor changes broker equity. Evidence envelopes
contain exact UTF-8 JSON text and its SHA256. Hashes prove integrity, not broker
origin: a separately qualified capture adapter is required for production. Every
state remains ``production_qualified=False``.

Admission belongs to the signal adapter: IDs must represent native flat/reverse
long_case1a/long_case2 or short_case1a entries after a completed-week valid stop
and the short bottom20 gate, BEFORE parent sizing (zero final lots do not revoke
admission). This module never infers admission from an order or selected volume.

All functions leave inputs untouched. ``recommend_topup`` returns a
``{state, recommendation}`` envelope; ``confirm_topup`` and
``reconcile_trading_day`` return the next state. Persist that state with
FundingStore.commit before publishing its result or permitting a new open.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

INITIAL_FEN = 15_000_000
MAX_SNAPSHOT_AGE_SECONDS = 300
REQUEST_VALID_DAYS = 7
SHANGHAI = ZoneInfo('Asia/Shanghai')
_SHA = re.compile(r'[0-9a-f]{64}')
_MONEY = re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?')


class FundingError(ValueError):
    """Deterministic fail-closed funding/accounting boundary failure."""


def _fail(reason: str):
    raise FundingError(reason)


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value or len(value) > 512:
        _fail(f'{name}_invalid')
    return value


def _sha(value: Any) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        _fail('sha256_invalid')
    return value


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (ValueError, TypeError, OverflowError):
        _fail('json_invalid')


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _time(value: Any) -> datetime:
    try:
        result = datetime.fromisoformat(value) if isinstance(value, str) else value
        if not isinstance(result, datetime) or result.tzinfo is None or result.utcoffset() is None:
            _fail('timezone_aware_timestamp_required')
        return result
    except (ValueError, OverflowError, TypeError):
        _fail('timezone_aware_timestamp_required')


def _day(value: Any) -> str:
    try:
        if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
            _fail('trading_day_invalid')
        return value
    except (ValueError, TypeError):
        _fail('trading_day_invalid')


def _money(value: Any, *, nonnegative: bool = False) -> int:
    if not isinstance(value, str) or len(value) > 24 or not _MONEY.fullmatch(value):
        _fail('strict_decimal_money_required')
    try:
        amount = Decimal(value)
        fen = int(amount * 100)
        if not amount.is_finite() or (nonnegative and fen < 0):
            _fail('money_invalid')
        return fen
    except (InvalidOperation, ValueError, OverflowError):
        _fail('money_invalid')


def _integer(value: Any, minimum: int = 0):
    if type(value) is not int or value < minimum:
        _fail('state_integer_invalid')
    return value


def _parse(envelope: Any, schema: str, source_kind: str) -> dict:
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                _fail('duplicate_json_key')
            out[key] = value
        return out
    try:
        payload = envelope['raw_payload']
        if not isinstance(payload, str) or len(payload) > 1_000_000:
            _fail('raw_payload_invalid')
        raw = payload.encode('utf-8')
        if hashlib.sha256(raw).hexdigest() != _sha(envelope['raw_sha256']):
            _fail('raw_sha256_mismatch')
        obj = json.loads(payload, object_pairs_hook=unique,
                         parse_constant=lambda _: _fail('nonfinite_json'))
        if not isinstance(obj, dict) or obj.get('schema') != schema or obj.get('source_kind') != source_kind:
            _fail('evidence_schema_or_source_invalid')
        return obj
    except (KeyError, TypeError, UnicodeError, ValueError) as exc:
        if isinstance(exc, FundingError):
            raise
        _fail('raw_evidence_required')


def _binding(raw: dict, state: dict):
    if raw.get('account_key') != state['account_key']:
        _fail('account_mismatch')
    if raw.get('material_release_id') != state['material_release_id']:
        _fail('material_release_mismatch')


def _broker(evidence: dict, state: dict, now: datetime, *, historical=False) -> dict:
    raw = _parse(evidence, 'weekly19.ctp-account.v1', 'ctp_account_callback')
    _binding(raw, state)
    try:
        fingerprint = hashlib.sha256((_text(raw['BrokerID'], 'broker_id') + '\0' +
                                      _text(raw['AccountID'], 'account_id')).encode()).hexdigest()
        if fingerprint != state['account_key']:
            _fail('raw_account_mismatch')
        if raw['CurrencyID'] != 'CNY' or raw['query_complete'] is not True:
            _fail('complete_cny_account_required')
        _integer(raw['query_reqid'], 1)
        _text(raw['generation_uuid'], 'generation_uuid')
        observed = _time(raw['observed_at'])
        age = (now - observed).total_seconds()
        if age < 0 or (not historical and age > MAX_SNAPSHOT_AGE_SECONDS):
            _fail('broker_snapshot_stale_or_future')
        return dict(trading_day=_day(raw['trading_day']), observed_at=observed.isoformat(),
                    balance_fen=_money(raw['Balance']), deposit_fen=_money(raw['Deposit'], nonnegative=True),
                    withdraw_fen=_money(raw['Withdraw'], nonnegative=True),
                    raw_sha256=evidence['raw_sha256'], generation_uuid=raw['generation_uuid'],
                    query_reqid=raw['query_reqid'])
    except (KeyError, TypeError, AttributeError):
        _fail('broker_cashflow_fields_missing')


def initial_state(account_key: str, material_release_id: str, cold_start_date: str) -> dict:
    """Create an unobserved external 150k reserve; never grant trading funds."""
    return dict(schema='weekly19.external-funding.v1', revision=0,
                account_key=_sha(account_key), material_release_id=_text(material_release_id, 'release'),
                cold_start_date=_day(cold_start_date), initial_trading_fen=INITIAL_FEN,
                reserve_initial_fen=INITIAL_FEN, reserve_remaining_fen=INITIAL_FEN,
                confirmed_topup_fen=0, requests={}, receipts={}, admitted_entries={},
                cashflow_checkpoint=None, day_rolls=[], production_qualified=False)


def validate_state(state: Any) -> None:
    """Verify conserved cash and request/receipt identities after load or restart."""
    try:
        if state['schema'] != 'weekly19.external-funding.v1' or state['production_qualified'] is not False:
            _fail('state_schema_or_qualification_invalid')
        _sha(state['account_key'])
        _text(state['material_release_id'], 'release')
        _day(state['cold_start_date'])
        _integer(state['revision'])
        if (_integer(state['initial_trading_fen']) != INITIAL_FEN
                or _integer(state['reserve_initial_fen']) != INITIAL_FEN):
            _fail('initial_capital_contract_invalid')
        remaining = _integer(state['reserve_remaining_fen'])
        total = _integer(state['confirmed_topup_fen'])
        if remaining + total != INITIAL_FEN:
            _fail('reserve_conservation_invalid')
        if not all(isinstance(state[k], dict) for k in ('requests', 'receipts', 'admitted_entries')):
            _fail('state_ledgers_invalid')
        sums = {rid: 0 for rid in state['requests']}
        for receipt_id, row in state['receipts'].items():
            _text(receipt_id, 'receipt_id')
            _sha(row['raw_sha256'])
            _sha(row['broker_sha256'])
            amount = _integer(row['amount_fen'], 1)
            sums[row['request_id']] += amount
            _time(row['occurred_at'])
        if sum(sums.values()) != total:
            _fail('receipt_ledger_conservation_invalid')
        pending = 0
        for rid, request in state['requests'].items():
            _sha(rid)
            if request['request_id'] != rid:
                _fail('request_identity_invalid')
            if request['account_key'] != state['account_key'] or request['material_release_id'] != state['material_release_id']:
                _fail('request_binding_invalid')
            amount = _integer(request['amount_fen'], 1)
            _integer(request['confirmed_fen'])
            if amount > INITIAL_FEN or request['confirmed_fen'] != sums[rid] or not 0 <= sums[rid] <= amount:
                _fail('request_conservation_invalid')
            want = 'confirmed' if sums[rid] == amount else ('partially_confirmed' if sums[rid] else 'pending')
            if request['status'] != want:
                _fail('request_status_invalid')
            pending += want != 'confirmed'
            if _time(request['created_at']) >= _time(request['expires_at']):
                _fail('request_expiry_invalid')
            _day(request['target_week_end'])
            _sha(request['source_sha256'])
            ids = request['admitted_entry_ids']
            if (not isinstance(ids, list) or not ids
                    or ids != sorted({_text(entry, 'entry_id') for entry in ids})
                    or rid != _hash([state['account_key'], state['material_release_id'],
                                    request['target_week_end'], ids, request['source_sha256']])):
                _fail('request_identity_hash_invalid')
            _checkpoint_valid(request['baseline'])
            _checkpoint_valid(request['active_baseline'])
            if not 0 <= _integer(request['confirmed_before_active_day_fen']) <= sums[rid]:
                _fail('request_active_day_conservation_invalid')
        if pending > 1:
            _fail('multiple_pending_requests')
        for key, rid in state['admitted_entries'].items():
            _sha(key)
            if rid not in state['requests']:
                _fail('admission_request_missing')
            request = state['requests'][rid]
            if key not in {_admission_key(state, request['target_week_end'], entry)
                           for entry in request['admitted_entry_ids']}:
                _fail('admission_request_identity_invalid')
        cp = state['cashflow_checkpoint']
        if cp is not None:
            _checkpoint_valid(cp)
        if not isinstance(state['day_rolls'], list):
            _fail('day_roll_ledger_invalid')
        previous_following = None
        for row in state['day_rolls']:
            _checkpoint_valid(row['closing'])
            _checkpoint_valid(row['following'])
            _sha(row['continuity_sha256'])
            _text(row['statement_id'], 'statement_id')
            if (row['following']['trading_day'] <= row['closing']['trading_day']
                    or _time(row['following']['observed_at']) < _time(row['closing']['observed_at'])
                    or row['following']['deposit_fen'] != 0 or row['following']['withdraw_fen'] != 0
                    or (previous_following and row['closing']['trading_day'] != previous_following['trading_day'])):
                _fail('day_roll_chain_invalid')
            previous_following = row['following']
        if previous_following and (cp is None or cp['trading_day'] != previous_following['trading_day']):
            _fail('day_roll_checkpoint_invalid')
    except (KeyError, TypeError, AttributeError):
        _fail('state_metadata_invalid')


def _checkpoint_valid(cp):
    _day(cp['trading_day'])
    _time(cp['observed_at'])
    _sha(cp['raw_sha256'])
    _integer(cp['deposit_fen'])
    _integer(cp['withdraw_fen'])


def _checkpoint(snapshot):
    return {key: snapshot[key] for key in ('trading_day', 'observed_at', 'raw_sha256', 'deposit_fen', 'withdraw_fen')}


def _cashflow_match(state, snapshot, *, expected_deposit_delta=0):
    cp = state['cashflow_checkpoint']
    if cp is None:
        if expected_deposit_delta:
            _fail('request_baseline_missing')
        return
    if snapshot['trading_day'] != cp['trading_day']:
        _fail('day_roll_requires_reconciliation')
    if _time(snapshot['observed_at']) < _time(cp['observed_at']):
        _fail('broker_out_of_order')
    if snapshot['withdraw_fen'] != cp['withdraw_fen']:
        _fail('unreconciled_cashflow_withdrawal')
    if snapshot['deposit_fen'] - cp['deposit_fen'] != expected_deposit_delta:
        _fail('deposit_delta_mismatch' if expected_deposit_delta else 'unreconciled_cashflow_deposit')


def _finish(original, changed):
    changed['revision'] = original['revision']
    if changed != original:
        changed['revision'] += 1
    validate_state(changed)
    return changed


def _admission_key(state, week, entry_id):
    return _hash([state['account_key'], state['material_release_id'], week, entry_id])


def _recommendation(status, request=None):
    result = dict(status=status, amount_fen=0, request_id=None, production_qualified=False)
    if request:
        result.update(request_id=request['request_id'], amount_fen=request['amount_fen'] - request['confirmed_fen'],
                      requested_amount_fen=request['amount_fen'], expires_at=request['expires_at'])
    return result


def recommend_topup(state: dict, broker: dict, target_week_end: str,
                    admitted_entry_ids: list[str], source_sha256: str, now: datetime) -> dict:
    """Recommend min(150k - broker marked equity, offsite reserve), never book it."""
    validate_state(state)
    now = _time(now)
    week = _day(target_week_end)
    _sha(source_sha256)
    if date.fromisoformat(week).weekday() != 4 or date.fromisoformat(week) > now.astimezone(SHANGHAI).date():
        _fail('completed_calendar_week_end_required')
    if not isinstance(admitted_entry_ids, list) or len(admitted_entry_ids) > 1000:
        _fail('admitted_entry_ids_invalid')
    ids = sorted({_text(value, 'entry_id') for value in admitted_entry_ids})
    snapshot = _broker(broker, state, now)
    _cashflow_match(state, snapshot)
    changed = copy.deepcopy(state)
    changed['cashflow_checkpoint'] = _checkpoint(snapshot)
    pending = next((r for r in changed['requests'].values() if r['status'] != 'confirmed'), None)
    if not ids:
        result = _recommendation('no_admitted_entry')
    elif pending:
        result = _recommendation('request_expired' if now >= _time(pending['expires_at']) else 'funding_pending', pending)
    elif snapshot['balance_fen'] >= INITIAL_FEN:
        result = _recommendation('equity_at_or_above_floor')
    elif changed['reserve_remaining_fen'] == 0:
        result = _recommendation('reserve_exhausted')
    else:
        keys = [_admission_key(state, week, entry) for entry in ids]
        fresh = [key for key in keys if key not in changed['admitted_entries']]
        if not fresh:
            result = _recommendation('duplicate_admission')
        else:
            amount = min(INITIAL_FEN - snapshot['balance_fen'], changed['reserve_remaining_fen'])
            rid = _hash([state['account_key'], state['material_release_id'], week, ids, source_sha256])
            request = dict(request_id=rid, account_key=state['account_key'],
                           material_release_id=state['material_release_id'], target_week_end=week,
                           admitted_entry_ids=ids, source_sha256=source_sha256,
                           created_at=now.isoformat(), expires_at=(now + timedelta(days=REQUEST_VALID_DAYS)).isoformat(),
                           amount_fen=amount, confirmed_fen=0, status='pending',
                           baseline=_checkpoint(snapshot), active_baseline=_checkpoint(snapshot),
                           confirmed_before_active_day_fen=0, marked_equity_fen=snapshot['balance_fen'])
            changed['requests'][rid] = request
            for key in fresh:
                changed['admitted_entries'][key] = rid
            result = _recommendation('topup_recommended', request)
    return dict(state=_finish(state, changed), recommendation=result)


def confirm_topup(state: dict, request_id: str, cashflow_receipt: dict, broker: dict, now: datetime) -> dict:
    """Book proven external cash only after exact receipt/Deposit reconciliation.

    Cross-day requests require reconcile_trading_day first. Unknown cash,
    an unproven day rollover, stale evidence, overpayment or expiry needs explicit operator
    reconciliation; no exception decreases the caller's reserve.
    """
    validate_state(state)
    now = _time(now)
    try:
        request = state['requests'][request_id]
    except (KeyError, TypeError):
        _fail('request_unknown')
    raw = _parse(cashflow_receipt, 'weekly19.bank-cashflow.v1', 'broker_cashflow_receipt')
    _binding(raw, state)
    try:
        if raw['request_id'] != request_id:
            _fail('receipt_request_mismatch')
        if raw['Status'] != 'completed' or raw['Direction'] != 'deposit':
            _fail('completed_deposit_receipt_required')
        receipt_id = _text(raw['receipt_id'], 'receipt_id')
        occurred = _time(raw['occurred_at'])
        amount = _money(raw['Amount'], nonnegative=True)
        if amount <= 0:
            _fail('positive_deposit_required')
        if not _time(request['created_at']) <= occurred <= now:
            _fail('receipt_out_of_order_or_future')
        snapshot = _broker(broker, state, now)
        if occurred > _time(snapshot['observed_at']):
            _fail('receipt_after_broker_snapshot')
        if receipt_id in state['receipts']:
            existing = state['receipts'][receipt_id]
            if (existing['raw_sha256'] != cashflow_receipt['raw_sha256']
                    or existing['request_id'] != request_id or existing['amount_fen'] != amount):
                _fail('receipt_reused_with_different_content')
            _cashflow_match(state, snapshot)
            return copy.deepcopy(state)
        if now >= _time(request['expires_at']):
            _fail('request_expired')
        if (_day(raw['trading_day']) != snapshot['trading_day']
                or snapshot['trading_day'] != request['active_baseline']['trading_day']):
            _fail('receipt_day_mismatch')
        if occurred < _time(request['active_baseline']['observed_at']):
            _fail('receipt_before_active_day')
        if amount > request['amount_fen'] - request['confirmed_fen'] or amount > state['reserve_remaining_fen']:
            _fail('amount_exceeds_request_or_reserve')
        if request['status'] == 'confirmed':
            _fail('request_already_confirmed')
        prior = [row for row in state['receipts'].values() if row['request_id'] == request_id]
        if prior and occurred < max(_time(row['occurred_at']) for row in prior):
            _fail('receipt_out_of_order')
        _cashflow_match(state, snapshot, expected_deposit_delta=amount)
        if (snapshot['deposit_fen'] - request['active_baseline']['deposit_fen']
                != request['confirmed_fen'] - request['confirmed_before_active_day_fen'] + amount):
            _fail('request_baseline_deposit_delta_mismatch')
        changed = copy.deepcopy(state)
        changed['reserve_remaining_fen'] -= amount
        changed['confirmed_topup_fen'] += amount
        updated = changed['requests'][request_id]
        updated['confirmed_fen'] += amount
        updated['status'] = 'confirmed' if updated['confirmed_fen'] == updated['amount_fen'] else 'partially_confirmed'
        changed['receipts'][receipt_id] = dict(request_id=request_id, amount_fen=amount,
            occurred_at=occurred.isoformat(), raw_sha256=cashflow_receipt['raw_sha256'],
            broker_sha256=broker['raw_sha256'])
        changed['cashflow_checkpoint'] = _checkpoint(snapshot)
        return _finish(state, changed)
    except (KeyError, TypeError, AttributeError):
        _fail('cashflow_receipt_fields_missing')


def assert_open_funding_ready(state: dict, broker: dict, now: datetime) -> None:
    """Additional funding gate; this does not qualify or authorize an order.

    Exhausted reserve does not block a positive trading account. Pending money
    never counts as equity. Existing close/reduce paths should not call this.
    """
    validate_state(state)
    snapshot = _broker(broker, state, _time(now))
    if state['cashflow_checkpoint'] is None:
        _fail('cashflow_baseline_missing')
    _cashflow_match(state, snapshot)
    if snapshot['trading_day'] < state['cold_start_date']:
        _fail('before_cold_start')
    if any(request['status'] != 'confirmed' for request in state['requests'].values()):
        _fail('funding_pending')
    if snapshot['balance_fen'] <= 0:
        _fail('nonpositive_equity')


def reconcile_trading_day(state: dict, closing_broker: dict, next_broker: dict, now: datetime,
                          *, continuity_receipt: dict | None = None) -> dict:
    """Carry pending requests across a proven, cash-neutral trading-day boundary.

    Require a broker/statement day-close envelope binding the exact closing
    account callback, its FINAL daily Deposit/Withdraw and the authoritative next
    trading day, plus that next day's zero-cashflow starting callback. A Friday
    21:00 callback with Monday TradingDay is valid. No natural-day/UTC shortcut
    substitutes for this evidence. Holiday succession belongs to the qualified
    provider's next_trading_day field, not a weekday guess in this module.
    """
    validate_state(state)
    now = _time(now)
    closing = _broker(closing_broker, state, now, historical=True)
    following = _broker(next_broker, state, now)
    proof = _parse(continuity_receipt, 'weekly19.cashflow-day-close.v1', 'broker_cashflow_day_close')
    _binding(proof, state)
    if state['cashflow_checkpoint'] is None:
        _fail('cashflow_baseline_missing')
    _cashflow_match(state, closing)
    try:
        _text(proof['statement_id'], 'statement_id')
        closed_at = _time(proof['closed_at'])
        if (proof['cashflows_complete'] is not True
                or _day(proof['trading_day']) != closing['trading_day']
                or proof['closing_account_sha256'] != closing['raw_sha256']
                or _money(proof['Deposit'], nonnegative=True) != closing['deposit_fen']
                or _money(proof['Withdraw'], nonnegative=True) != closing['withdraw_fen']):
            _fail('cashflow_day_close_evidence_mismatch')
        if not _time(closing['observed_at']) <= closed_at <= _time(following['observed_at']):
            _fail('cashflow_day_close_time_invalid')
        if (_day(proof['next_trading_day']) != following['trading_day']
                or following['trading_day'] <= closing['trading_day']):
            _fail('continuous_trading_day_evidence_required')
        if following['deposit_fen'] != 0 or following['withdraw_fen'] != 0:
            _fail('unreconciled_cashflow_at_day_roll')
        changed = copy.deepcopy(state)
        changed['day_rolls'].append(dict(closing=_checkpoint(closing), following=_checkpoint(following),
            continuity_sha256=continuity_receipt['raw_sha256'], statement_id=proof['statement_id']))
        changed['cashflow_checkpoint'] = _checkpoint(following)
        for request in changed['requests'].values():
            if request['status'] != 'confirmed':
                if now >= _time(request['expires_at']):
                    _fail('request_expired')
                request['active_baseline'] = _checkpoint(following)
                request['confirmed_before_active_day_fen'] = request['confirmed_fen']
        return _finish(state, changed)
    except (KeyError, TypeError, AttributeError):
        _fail('cashflow_day_close_fields_missing')
