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

V2: a recommendation is an offer, never a debt. Real marked E at/above the
150k floor can pass this extra funding gate while an old offer remains unpaid.
Current-gap changes require proven retirement/replacement before an actionable
new amount. Stable ORIGINAL native admission IDs are consumed across broker
queries, fills, delivery attempts and repricing; this is not a per-tick equity
replenishment service. V1 states require an explicit one-CAS migration.
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
MAX_OPENING_EQUITY_FEN = 2**63 - 1
OPENING_EXISTING_ACCOUNT_MODE = 'operator_existing_account_v1'
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
    return dict(schema='weekly19.external-funding.v2', funding_contract_version=2, revision=0,
                account_key=_sha(account_key), material_release_id=_text(material_release_id, 'release'),
                cold_start_date=_day(cold_start_date), initial_trading_fen=INITIAL_FEN,
                reserve_initial_fen=INITIAL_FEN, reserve_remaining_fen=INITIAL_FEN,
                confirmed_topup_fen=0, requests={}, receipts={}, admitted_entries={},
                cashflow_checkpoint=None, day_rolls=[], retirements={}, request_attempts={},
                migration=None, production_qualified=False)


def validate_state(state: Any) -> None:
    """Verify conserved cash and request/receipt identities after load or restart."""
    try:
        if (state['schema'] not in ('weekly19.external-funding.v1','weekly19.external-funding.v2')
                or state['production_qualified'] is not False):
            _fail('state_schema_or_qualification_invalid')
        _sha(state['account_key'])
        _text(state['material_release_id'], 'release')
        _day(state['cold_start_date'])
        _integer(state['revision'])
        is_v2=state['schema']=='weekly19.external-funding.v2'
        retirements=state.get('retirements',{}) if is_v2 else {}
        if is_v2:
            if state.get('funding_contract_version')!=2 or not isinstance(retirements,dict) or not isinstance(state.get('request_attempts'),dict):
                _fail('v2_state_ledgers_missing')
            migration=state.get('migration')
            if migration is not None:
                if migration.get('from_schema')!='weekly19.external-funding.v1': _fail('migration_schema_invalid')
                _integer(migration['from_revision']); _sha(migration['legacy_state_sha256'])
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
            if rid in retirements:
                if sums[rid]==amount: _fail('fully_confirmed_request_cannot_retire')
                want='retired_partial' if sums[rid] else 'retired_unpaid'
            if request['status'] != want:
                _fail('request_status_invalid')
            pending += want in ('pending','partially_confirmed')
            if _time(request['created_at']) >= _time(request['expires_at']):
                _fail('request_expiry_invalid')
            _day(request['target_week_end'])
            _sha(request['source_sha256'])
            ids = request['admitted_entry_ids']
            identity=[state['account_key'],state['material_release_id'],request['target_week_end'],ids,request['source_sha256']]
            if 'attempt' in request:
                if not is_v2: _fail('v1_request_attempt_invalid')
                identity.append(_integer(request['attempt']))
            if (not isinstance(ids,list) or not ids
                    or ids!=sorted({_text(entry,'entry_id') for entry in ids}) or rid!=_hash(identity)):
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
                    or (row.get('source_kind')!='operator_manual'and
                        (row['following']['deposit_fen'] != 0 or row['following']['withdraw_fen'] != 0))
                    or (previous_following and row['closing']['trading_day'] != previous_following['trading_day'])):
                _fail('day_roll_chain_invalid')
            previous_following = row['following']
        if previous_following and (cp is None or cp['trading_day'] != previous_following['trading_day']):
            _fail('day_roll_checkpoint_invalid')
        _validate_operator_cash_ledger(state)
        _validate_opening_equity(state)
        if is_v2:
            if set(state['request_attempts'])!=set(state['admitted_entries']):
                _fail('admission_attempt_ledger_keys_invalid')
            for key,attempts in state['request_attempts'].items():
                if (not isinstance(attempts,list) or not attempts or len(attempts)!=len(set(attempts))
                        or attempts[0]!=state['admitted_entries'][key]):
                    _fail('admission_attempt_ledger_invalid')
                for request_id in attempts:
                    request=state['requests'][request_id]
                    if key not in {_admission_key(state,request['target_week_end'],entry) for entry in request['admitted_entry_ids']}:
                        _fail('admission_attempt_request_mismatch')
            covered={rid for attempts in state['request_attempts'].values() for rid in attempts}
            if covered!=set(state['requests']): _fail('request_attempt_ledger_coverage_invalid')
            sequence=[row['attempt'] for row in state['requests'].values() if 'attempt' in row]
            if any(attempt>=len(state['requests']) for attempt in sequence): _fail('request_attempt_sequence_invalid')
            if len(sequence)!=len(set(sequence)): _fail('request_attempt_sequence_duplicate')
            for request_id,proof in retirements.items():
                _validate_retirement(state,state['requests'][request_id],proof)
    except (KeyError, TypeError, AttributeError):
        _fail('state_metadata_invalid')



def _require_v2(state):
    if state['schema']!='weekly19.external-funding.v2':
        _fail('funding_state_upgrade_required')


def _active(request):
    return request['status'] in ('pending','partially_confirmed')


def upgrade_funding_state(state):
    """Explicit deterministic V1 -> V2 migration; persist with ONE CAS commit.

    Old request IDs, receipts, original admission ownership and money are copied
    without reinterpretation. A V2 input is an idempotent read, not a reset.
    """
    validate_state(state)
    if state['schema']=='weekly19.external-funding.v2': return copy.deepcopy(state)
    changed=copy.deepcopy(state)
    changed.update(schema='weekly19.external-funding.v2',funding_contract_version=2,
        retirements={},request_attempts={key:[rid] for key,rid in state['admitted_entries'].items()},
        migration=dict(from_schema=state['schema'],from_revision=state['revision'],legacy_state_sha256=_hash(state)))
    return _finish(state,changed)


def _request_chain(state,request,checkpoint):
    """Find every already-proven closing/opening boundary since this offer."""
    cursor=request['baseline']; hashes=[]
    while cursor['trading_day']!=checkpoint['trading_day']:
        candidates=[row for row in state['day_rolls'] if row['closing']['trading_day']==cursor['trading_day']
                    and row['following']['trading_day']<=checkpoint['trading_day']]
        if len(candidates)!=1: _fail('retirement_continuity_chain_incomplete')
        row=candidates[0]; closing=row['closing']
        if (_time(closing['observed_at'])<_time(cursor['observed_at'])
                or (closing['withdraw_fen']<cursor['withdraw_fen']if row.get('source_kind')=='operator_manual'else closing['withdraw_fen']!=cursor['withdraw_fen'])
                or closing['deposit_fen']<cursor['deposit_fen']):
            _fail('retirement_continuity_chain_invalid')
        hashes.append(_hash(row)); cursor=row['following']
    active=request['active_baseline']
    if (active['trading_day']!=checkpoint['trading_day'] or _time(checkpoint['observed_at'])<_time(active['observed_at'])
            or checkpoint['withdraw_fen']!=active['withdraw_fen']
            or checkpoint['deposit_fen']-active['deposit_fen']
            !=request['confirmed_fen']-request['confirmed_before_active_day_fen']):
        _fail('retirement_unreconciled_cashflow')
    return hashes


def _validate_retirement(state,request,proof):
    if proof.get('request_id')!=request['request_id']: _fail('retirement_request_mismatch')
    checkpoint=proof['broker_checkpoint']; _checkpoint_valid(checkpoint)
    _integer(proof['confirmed_fen']); _integer(proof['unpaid_fen'],1)
    if (proof['request_baseline_sha256']!=_hash(request['baseline'])
            or proof['active_baseline_sha256']!=_hash(request['active_baseline'])
            or proof['day_roll_sha256s']!=_request_chain(state,request,checkpoint)
            or proof['confirmed_fen']!=request['confirmed_fen']
            or proof['unpaid_fen']!=request['amount_fen']-request['confirmed_fen']):
        _fail('retirement_proof_invalid')
    retired=_time(proof['retired_at'])
    if retired<_time(checkpoint['observed_at']): _fail('retirement_time_invalid')
    equity=proof['marked_equity_fen']
    if type(equity) is not int: _fail('retirement_equity_invalid')
    reserve=_integer(proof['reserve_remaining_fen'])
    if reserve>INITIAL_FEN: _fail('retirement_reserve_invalid')
    desired=min(max(INITIAL_FEN-equity,0),reserve)
    reason=proof['reason']
    if reason=='equity_recovered':
        if equity<INITIAL_FEN: _fail('retirement_equity_not_recovered')
    elif reason=='expired_superseded':
        if retired<_time(request['expires_at']): _fail('retirement_request_not_expired')
    elif reason=='superseded_current_gap':
        if desired<=0 or desired==proof['unpaid_fen']: _fail('retirement_gap_not_changed')
    else: _fail('retirement_reason_invalid')


def retire_topup_request(state,request_id,broker,now,*,reason):
    """Withdraw an offer only after full known-cashflow continuity is proven.

    Retirement does not cancel a bank instruction. Any later new cashflow is
    UNKNOWN and blocked until an explicit reconciliation; it is never silently
    attributed to another request. Known receipt replays remain idempotent.
    """
    validate_state(state); _require_v2(state); now=_time(now)
    snapshot=_broker(broker,state,now); _cashflow_match(state,snapshot)
    try: request=state['requests'][request_id]
    except (KeyError,TypeError): _fail('request_unknown')
    if request_id in state['retirements']:
        if state['retirements'][request_id]['reason']!=reason: _fail('retirement_reason_conflict')
        return copy.deepcopy(state)
    if not _active(request): _fail('request_already_confirmed')
    checkpoint=_checkpoint(snapshot)
    proof=dict(request_id=request_id,reason=reason,retired_at=now.isoformat(),broker_checkpoint=checkpoint,
        request_baseline_sha256=_hash(request['baseline']),active_baseline_sha256=_hash(request['active_baseline']),
        day_roll_sha256s=_request_chain(state,request,checkpoint),confirmed_fen=request['confirmed_fen'],
        unpaid_fen=request['amount_fen']-request['confirmed_fen'],marked_equity_fen=snapshot['balance_fen'],
        reserve_remaining_fen=state['reserve_remaining_fen'])
    _validate_retirement(state,request,proof)
    changed=copy.deepcopy(state); changed['retirements'][request_id]=proof
    changed['requests'][request_id]['status']='retired_partial' if request['confirmed_fen'] else 'retired_unpaid'
    changed['cashflow_checkpoint']=checkpoint
    return _finish(state,changed)

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


def _initial_account_snapshot(state, broker, now):
    snapshot=_broker(broker,state,now)
    raw=_parse(broker,'weekly19.ctp-account.v1','ctp_account_callback')
    try:
        _money(raw['Available'],nonnegative=True)
        if (raw.get('query_last_seen') is not True or type(raw.get('query_error_rows')) is not int
                or raw['query_error_rows']!=0): _fail('initial_complete_account_query_required')
    except (KeyError,TypeError): _fail('initial_account_available_missing')
    return snapshot


def _opening_start_valid(state,snapshot,now):
    if (snapshot['trading_day']<state['cold_start_date']
            or now.astimezone(SHANGHAI).date().isoformat()<state['cold_start_date']
            or _time(snapshot['observed_at']).astimezone(SHANGHAI).date().isoformat()<state['cold_start_date']):
        _fail('initial_cash_observation_capital_or_start_invalid')


def _validate_opening_equity(state):
    """A private source-bound baseline, never verified strategy PnL or cash T."""
    if 'opening_equity' not in state:return
    row=state['opening_equity']
    fields={'schema','mode','source_kind','classification','operator_decision_id',
            'baseline_trading_fen','observed_equity_fen','opening_surplus_fen',
            'verified_strategy_pnl','baseline_checkpoint','broker_account','accepted_at'}
    if (state['schema']!='weekly19.external-funding.v2' or not isinstance(row,dict) or set(row)!=fields
            or row['schema']!='weekly19.opening-equity.v1' or row['mode']!=OPENING_EXISTING_ACCOUNT_MODE
            or row['source_kind']!='operator_manual' or row['classification']!='operator_designated_pre_start_surplus'
            or row['verified_strategy_pnl']is not False):
        _fail('opening_equity_metadata_invalid')
    _sha(row['operator_decision_id'])
    equity=_integer(row['observed_equity_fen'],1)
    if (equity>MAX_OPENING_EQUITY_FEN or _integer(row['baseline_trading_fen'])!=INITIAL_FEN
            or type(row['opening_surplus_fen'])is not int or row['opening_surplus_fen']!=equity-INITIAL_FEN):
        _fail('opening_equity_bridge_or_range_invalid')
    if not isinstance(row['accepted_at'],str):_fail('opening_equity_accepted_time_invalid')
    accepted=_time(row['accepted_at'])
    evidence=row['broker_account']
    if not isinstance(evidence,dict) or set(evidence)!={'raw_payload','raw_sha256'}:
        _fail('opening_equity_raw_account_required')
    snapshot=_initial_account_snapshot(state,evidence,accepted)
    _opening_start_valid(state,snapshot,accepted)
    if snapshot['balance_fen']!=equity or row['baseline_checkpoint']!=_checkpoint(snapshot):
        _fail('opening_equity_raw_binding_invalid')
    cursor=row['baseline_checkpoint'];_checkpoint_valid(cursor)
    current=state['cashflow_checkpoint']
    if current is None or state['revision']<1:_fail('opening_equity_checkpoint_required')
    for boundary in state['day_rolls']:
        closing=boundary['closing']
        if (closing['trading_day']!=cursor['trading_day'] or _time(closing['observed_at'])<_time(cursor['observed_at'])
                or closing['deposit_fen']<cursor['deposit_fen'] or closing['withdraw_fen']<cursor['withdraw_fen']):
            _fail('opening_equity_cashflow_bridge_invalid')
        cursor=boundary['following']
    if (current['trading_day']!=cursor['trading_day'] or _time(current['observed_at'])<_time(cursor['observed_at'])
            or current['deposit_fen']<cursor['deposit_fen'] or current['withdraw_fen']<cursor['withdraw_fen']
            or (not state['day_rolls'] and current['deposit_fen']-cursor['deposit_fen']!=state['confirmed_topup_fen'])):
        _fail('opening_equity_cashflow_bridge_invalid')
    for request in state['requests'].values():
        baseline=request['baseline'];opening=row['baseline_checkpoint']
        if (baseline['trading_day']<opening['trading_day'] or _time(baseline['observed_at'])<_time(opening['observed_at'])
                or (baseline['trading_day']==opening['trading_day'] and
                    (baseline['deposit_fen']<opening['deposit_fen'] or baseline['withdraw_fen']<opening['withdraw_fen']))):
            _fail('opening_equity_request_before_baseline')


def begin_cash_observation(state: dict, broker: dict, now: datetime, *,
                           opening_equity_mode='exact_150k', operator_decision_id=None) -> dict:
    """Pin initial gross cash without treating its Deposit as a reserve topup.

    Default exact_150k keeps the historical state bytes. The explicit existing
    account mode records real E minus the 150k capital anchor as operator-
    designated PRE-start surplus (possibly negative), never verified strategy
    profit, external reserve or new cash. Source qualification and position
    adoption remain the production caller's independent responsibility.
    """
    validate_state(state); _require_v2(state); now=_time(now)
    if not isinstance(opening_equity_mode,str) or opening_equity_mode not in {'exact_150k',OPENING_EXISTING_ACCOUNT_MODE}:
        _fail('opening_equity_mode_invalid')
    existing_account=opening_equity_mode==OPENING_EXISTING_ACCOUNT_MODE
    if existing_account:_sha(operator_decision_id)
    elif operator_decision_id is not None:_fail('opening_equity_decision_without_policy')
    snapshot=_initial_account_snapshot(state,broker,now)
    if (any(state[key] for key in ('requests','receipts','admitted_entries','day_rolls','retirements','request_attempts'))
            or state['confirmed_topup_fen']!=0 or state['reserve_remaining_fen']!=INITIAL_FEN):
        _fail('initial_cash_observation_after_activity')
    opening=state.get('opening_equity')
    if state['cashflow_checkpoint']is not None:
        if ((opening is not None) != existing_account or
                (opening is not None and opening['operator_decision_id']!=operator_decision_id)):
            _fail('opening_equity_policy_or_decision_change_forbidden')
    if existing_account:
        if not 0<snapshot['balance_fen']<=MAX_OPENING_EQUITY_FEN:_fail('opening_equity_positive_real_account_required')
        if state['cashflow_checkpoint']is None and state['revision']!=0:_fail('opening_equity_initial_revision_required')
    elif snapshot['balance_fen']!=INITIAL_FEN:
        _fail('initial_cash_observation_capital_or_start_invalid')
    _opening_start_valid(state,snapshot,now)
    checkpoint=_checkpoint(snapshot)
    if state['cashflow_checkpoint'] is not None:
        if state['cashflow_checkpoint']!=checkpoint: _fail('initial_cash_observation_already_exists')
        return copy.deepcopy(state)
    changed=copy.deepcopy(state);changed['cashflow_checkpoint']=checkpoint
    if existing_account:
        changed['opening_equity']=dict(schema='weekly19.opening-equity.v1',mode=OPENING_EXISTING_ACCOUNT_MODE,
            source_kind='operator_manual',classification='operator_designated_pre_start_surplus',
            operator_decision_id=operator_decision_id,baseline_trading_fen=INITIAL_FEN,
            observed_equity_fen=snapshot['balance_fen'],opening_surplus_fen=snapshot['balance_fen']-INITIAL_FEN,
            verified_strategy_pnl=False,baseline_checkpoint=copy.deepcopy(checkpoint),
            broker_account={key:broker[key]for key in ('raw_payload','raw_sha256')},accepted_at=now.isoformat())
    return _finish(state,changed)


def assert_opening_equity_forward(current,following):
    """Shared private-store CAS invariant; callers must never make it optional."""
    old_present='opening_equity'in current;new_present='opening_equity'in following
    if not old_present and not new_present:return
    validate_state(current);validate_state(following)
    if old_present:
        if not new_present or current['opening_equity']!=following['opening_equity']:
            _fail('opening_equity_rewrite_or_removal_forbidden')
        return
    if current['cashflow_checkpoint']is not None:
        _fail('opening_equity_policy_after_observation_forbidden')
    row=following['opening_equity']
    expected=begin_cash_observation(current,row['broker_account'],_time(row['accepted_at']),
        opening_equity_mode=row['mode'],operator_decision_id=row['operator_decision_id'])
    if following!=expected:_fail('opening_equity_one_initial_cas_required')


def _admission_key(state, week, entry_id):
    return _hash([state['account_key'], state['material_release_id'], week, entry_id])


def _recommendation(status,amount=0,request=None,*,actionable=False):
    result=dict(status=status,amount_fen=amount,request_id=None,actionable=actionable,production_qualified=False)
    if request is not None:
        result.update(historical_request_id=request['request_id'],
            historical_request_remaining_fen=request['amount_fen']-request['confirmed_fen'],
            requested_amount_fen=request['amount_fen'],expires_at=request['expires_at'])
        if actionable: result['request_id']=request['request_id']
    return result


def recommend_topup(state: dict, broker: dict, target_week_end: str,
                    admitted_entry_ids: list[str], source_sha256: str, now: datetime) -> dict:
    """Native-admission batch advice, NOT a per-tick/per-fill replenishment loop.

    IDs must retain the original candidate identity across delivery/requotes and
    account generations. Confirmed or recovery-retired candidates stay consumed.
    A changed gap on an active offer is non-actionable until proven retirement
    and a new attempt; never print a new amount against the old request cap.
    """
    validate_state(state); _require_v2(state); now=_time(now)
    week=_day(target_week_end); _sha(source_sha256)
    if date.fromisoformat(week).weekday()!=4 or date.fromisoformat(week)>now.astimezone(SHANGHAI).date():
        _fail('completed_calendar_week_end_required')
    if not isinstance(admitted_entry_ids,list) or len(admitted_entry_ids)>1000: _fail('admitted_entry_ids_invalid')
    ids=sorted({_text(value,'entry_id') for value in admitted_entry_ids})
    snapshot=_broker(broker,state,now); _cashflow_match(state,snapshot)
    changed=copy.deepcopy(state); changed['cashflow_checkpoint']=_checkpoint(snapshot)
    pending=next((row for row in changed['requests'].values() if _active(row)),None)
    desired=min(max(INITIAL_FEN-snapshot['balance_fen'],0),changed['reserve_remaining_fen'])
    if not ids:
        result=_recommendation('no_admitted_entry',request=pending)
    elif snapshot['balance_fen']>=INITIAL_FEN:
        result=_recommendation('equity_at_or_above_floor',request=pending)
    elif pending:
        remaining=pending['amount_fen']-pending['confirmed_fen']
        if now>=_time(pending['expires_at']):
            result=_recommendation('request_expired',desired,pending)
        elif desired!=remaining:
            result=_recommendation('request_refresh_required',desired,pending)
        else:
            result=_recommendation('funding_pending',desired,pending,actionable=True)
    elif changed['reserve_remaining_fen']==0:
        result=_recommendation('reserve_exhausted')
    else:
        keys=[_admission_key(state,week,entry) for entry in ids]
        eligible=[]
        for key in keys:
            attempts=changed['request_attempts'].get(key,[])
            if not attempts or changed['retirements'].get(attempts[-1],{}).get('reason')=='superseded_current_gap':
                eligible.append(key)
        if not eligible:
            result=_recommendation('duplicate_admission')
        else:
            attempt=len(changed['requests'])
            rid=_hash([state['account_key'],state['material_release_id'],week,ids,source_sha256,attempt])
            request=dict(request_id=rid,account_key=state['account_key'],material_release_id=state['material_release_id'],
                target_week_end=week,admitted_entry_ids=ids,source_sha256=source_sha256,attempt=attempt,
                created_at=now.isoformat(),expires_at=(now+timedelta(days=REQUEST_VALID_DAYS)).isoformat(),
                amount_fen=desired,confirmed_fen=0,status='pending',baseline=_checkpoint(snapshot),
                active_baseline=_checkpoint(snapshot),confirmed_before_active_day_fen=0,marked_equity_fen=snapshot['balance_fen'])
            changed['requests'][rid]=request
            for key in eligible:
                if key not in changed['admitted_entries']: changed['admitted_entries'][key]=rid
                changed['request_attempts'].setdefault(key,[]).append(rid)
            result=_recommendation('topup_recommended',desired,request,actionable=True)
    return dict(state=_finish(state,changed),recommendation=result)


def confirm_topup(state: dict, request_id: str, cashflow_receipt: dict, broker: dict, now: datetime) -> dict:
    """Book proven external cash only after exact receipt/Deposit reconciliation.

    Cross-day requests require reconcile_trading_day first. Unknown cash,
    an unproven day rollover, stale evidence, overpayment or expiry needs explicit operator
    reconciliation; no exception decreases the caller's reserve.
    """
    validate_state(state)
    _require_v2(state)
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
        if request_id in state['retirements']:
            _fail('retired_request_late_cashflow_requires_reconciliation')
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

    Exhausted reserve does not block a positive trading account. An unpaid
    offer cannot block E>=150k; it is not a debt. Pending money never counts as
    equity. Existing close/reduce paths should not call this.
    """
    validate_state(state)
    _require_v2(state)
    snapshot = _broker(broker, state, _time(now))
    if state['cashflow_checkpoint'] is None:
        _fail('cashflow_baseline_missing')
    _cashflow_match(state, snapshot)
    if snapshot['trading_day'] < state['cold_start_date']:
        _fail('before_cold_start')
    if snapshot['balance_fen'] < INITIAL_FEN and any(_active(request) for request in state['requests'].values()):
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
    _require_v2(state)
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
            if _active(request):
                request['active_baseline'] = _checkpoint(following)
                request['confirmed_before_active_day_fen'] = request['confirmed_fen']
        return _finish(state, changed)
    except (KeyError, TypeError, AttributeError):
        _fail('cashflow_day_close_fields_missing')

# Explicit operator attestation; never a bank callback, capture HMAC or order permission.
OPERATOR_CASH_ASSERTION = 'I_HAVE_MANUALLY_VERIFIED_ACTUAL_CASHFLOWS_AND_OFFSITE_RESERVE'
OPERATOR_REVIEW_SECONDS = 1800

def _operator_review(envelope, state):
    raw = _parse(envelope, 'weekly19.operator-cash-review.v1', 'operator_manual')
    _binding(raw, state)
    try:
        for key in ('record_id','operator_id','os_user','notes'):
            _text(raw[key], key)
        _integer(raw['os_uid'])
        if (raw['assertion'] != OPERATOR_CASH_ASSERTION or raw['no_unlisted_cashflows'] is not True
                or raw['broker_automatically_verified'] is not False or raw['production_qualified'] is not False
                or raw.get('source_qualified', False) is not False):
            _fail('operator_cash_attestation_required')
        created, expires = _time(raw['created_at']), _time(raw['expires_at'])
        if not 0 < (expires-created).total_seconds() <= OPERATOR_REVIEW_SECONDS:
            _fail('operator_review_acceptance_window_invalid')
        _integer(raw['before_funding_revision']); _sha(raw['before_funding_sha256'])
        _checkpoint_valid(raw['before_checkpoint'])
        if _hash(raw['before_checkpoint']) != _sha(raw['before_checkpoint_sha256']):
            _fail('operator_review_baseline_hash_invalid')
        reserve = _integer(raw['reserve_remaining_fen_before'])
        total = _integer(raw['confirmed_topup_fen_before'])
        if reserve+total != INITIAL_FEN or _integer(raw['expected_reserve_remaining_fen']) > reserve:
            _fail('operator_review_reserve_conservation_invalid')
        reviewed = _broker(raw['reviewed_account'],state,created)
        _money(_parse(raw['reviewed_account'],'weekly19.ctp-account.v1','ctp_account_callback')['Available'],nonnegative=True)
        if not isinstance(raw['topups'],list) or len(raw['topups'])>1000 or not isinstance(raw['closed_days'],list) or len(raw['closed_days'])>1000:
            _fail('operator_review_cash_rows_invalid')
        receipt_ids=[]
        for row in raw['topups']:
            if set(row)!={'request_id','receipt_id','amount_fen','occurred_at','trading_day','admitted_entry_ids','target_week_end','source_sha256'}:
                _fail('operator_topup_fields_invalid')
            _sha(row['request_id']); _text(row['receipt_id'],'receipt_id'); _integer(row['amount_fen'],1)
            _time(row['occurred_at']); _day(row['trading_day']); _day(row['target_week_end']); _sha(row['source_sha256'])
            if not isinstance(row['admitted_entry_ids'],list) or not row['admitted_entry_ids']:
                _fail('operator_topup_admission_missing')
            receipt_ids.append(row['receipt_id'])
        if len(set(receipt_ids))!=len(receipt_ids): _fail('operator_review_receipt_duplicate')
        dates=[]
        for row in raw['closed_days']:
            if set(row)!={'trading_day','final_deposit_fen','final_withdraw_fen','closed_at','statement_reference','cashflows_complete'}:
                _fail('operator_closed_day_fields_invalid')
            dates.append(_day(row['trading_day'])); _integer(row['final_deposit_fen']); _integer(row['final_withdraw_fen'])
            _time(row['closed_at']); _text(row['statement_reference'],'statement_reference')
            if row['cashflows_complete'] is not True: _fail('operator_closed_day_incomplete')
        if dates!=sorted(set(dates)): _fail('operator_closed_days_order_invalid')
        return raw, reviewed
    except (KeyError,TypeError,AttributeError):
        _fail('operator_review_fields_missing')


def _operator_closing(row):
    return dict(trading_day=row['trading_day'],observed_at=_time(row['closed_at']).isoformat(),raw_sha256=_hash(row),
                deposit_fen=row['final_deposit_fen'],withdraw_fen=row['final_withdraw_fen'])


def _operator_cash_totals(raw, snapshot):
    """Revalidate persisted gross facts, not just their self-consistent hashes."""
    cp=raw['before_checkpoint'];days=[row['trading_day']for row in raw['closed_days']]
    same=snapshot['trading_day']==cp['trading_day']
    if (snapshot['trading_day']<cp['trading_day'] or _time(snapshot['observed_at'])<_time(cp['observed_at'])
            or (same and days) or (not same and (not days or days[0]!=cp['trading_day'] or days[-1]>=snapshot['trading_day']))):
        _fail('operator_review_day_sequence_invalid')
    byday={day:0 for day in days+[snapshot['trading_day']]}
    for row in raw['topups']:
        if row['trading_day']not in byday: _fail('operator_topup_trading_day_outside_review')
        byday[row['trading_day']]+=row['amount_fen']
    previous_time=_time(cp['observed_at'])
    for row in raw['closed_days']:
        base_deposit=cp['deposit_fen']if row['trading_day']==cp['trading_day']else 0
        base_withdraw=cp['withdraw_fen']if row['trading_day']==cp['trading_day']else 0
        closed=_time(row['closed_at'])
        if (row['final_deposit_fen']!=base_deposit+byday[row['trading_day']] or row['final_withdraw_fen']<base_withdraw
                or not previous_time<=closed<=_time(snapshot['observed_at'])):
            _fail('operator_closed_day_gross_cash_or_time_mismatch')
        for transfer in raw['topups']:
            if transfer['trading_day']==row['trading_day']and not previous_time<=_time(transfer['occurred_at'])<=closed:
                _fail('operator_topup_outside_declared_trading_day_window')
        previous_time=closed
    if any(row['trading_day']==snapshot['trading_day']and not previous_time<=_time(row['occurred_at'])<=_time(snapshot['observed_at']) for row in raw['topups']):
        _fail('operator_topup_outside_declared_trading_day_window')
    if (snapshot['deposit_fen']!=(cp['deposit_fen']if same else 0)+byday[snapshot['trading_day']]
            or snapshot['withdraw_fen']<(cp['withdraw_fen']if same else 0)):
        _fail('operator_review_unlisted_or_regressing_cashflow')
    if raw['expected_reserve_remaining_fen']!=raw['reserve_remaining_fen_before']-sum(byday.values()):
        _fail('operator_review_offsite_reserve_mismatch')
    return byday


def _validate_operator_cash_ledger(state):
    ledger=state.get('manual_cash_reviews',{})
    if not isinstance(ledger,dict): _fail('operator_review_ledger_invalid')
    covered_receipts=set();covered_rolls=set()
    for record_id, item in ledger.items():
        raw, reviewed=_operator_review(item,state)
        if record_id!=raw['record_id'] or item.get('source_kind')!='operator_manual': _fail('operator_review_ledger_identity_invalid')
        applied=_broker(item['applied_account'],state,_time(item['applied_at']))
        if (_time(item['applied_at'])<_time(raw['created_at']) or _time(item['applied_at'])>=_time(raw['expires_at'])
                or _time(applied['observed_at'])<_time(reviewed['observed_at'])
                or any(applied[k]!=reviewed[k] for k in ('trading_day','deposit_fen','withdraw_fen'))
                or item['after_checkpoint']!=_checkpoint(applied)):
            _fail('operator_review_applied_source_invalid')
        _operator_cash_totals(raw,applied)
        amount=sum(row['amount_fen']for row in raw['topups'])
        if (item['reserve_remaining_fen_after']!=raw['reserve_remaining_fen_before']-amount
                or item['confirmed_topup_fen_after']!=raw['confirmed_topup_fen_before']+amount
                or item['reserve_remaining_fen_after']!=raw['expected_reserve_remaining_fen']):
            _fail('operator_review_ledger_cash_invalid')
        for row in raw['topups']:
            receipt=state['receipts'][row['receipt_id']]
            if (receipt.get('source_kind')!='operator_manual' or receipt.get('manual_review_id')!=record_id
                    or receipt['request_id']!=row['request_id'] or receipt['amount_fen']!=row['amount_fen']
                    or receipt['occurred_at']!=_time(row['occurred_at']).isoformat() or receipt.get('trading_day')!=row['trading_day']
                    or receipt['raw_sha256']!=item['raw_sha256'] or receipt['broker_sha256']!=item['applied_account']['raw_sha256']
                    or row['receipt_id'] in covered_receipts):
                _fail('operator_receipt_ledger_binding_invalid')
            request=state['requests'][row['request_id']]
            if (not _time(request['created_at'])<=_time(row['occurred_at'])<=_time(reviewed['observed_at'])
                    or _time(raw['created_at'])>=_time(request['expires_at'])
                    or _time(item['applied_at'])>=_time(request['expires_at']) or row['amount_fen']>request['amount_fen']):
                _fail('operator_receipt_request_window_invalid')
            if any(row[k]!=request[k] for k in ('admitted_entry_ids','target_week_end','source_sha256')):
                _fail('operator_receipt_admission_binding_invalid')
            covered_receipts.add(row['receipt_id'])
        if raw['closed_days']:
            index=item['day_roll_index'];_integer(index)
            roll=state['day_rolls'][index]
            if (index in covered_rolls or roll.get('source_kind')!='operator_manual' or roll.get('manual_review_id')!=record_id
                    or roll['closing']!=_operator_closing(raw['closed_days'][0]) or roll['following']!=item['after_checkpoint']
                    or roll['continuity_sha256']!=item['raw_sha256'] or roll['statement_id']!='operator:'+record_id):
                _fail('operator_day_roll_ledger_binding_invalid')
            covered_rolls.add(index)
        elif item['day_roll_index'] is not None: _fail('operator_day_roll_unexpected')
    if covered_receipts!={key for key,row in state['receipts'].items()if row.get('source_kind')=='operator_manual'}:
        _fail('operator_receipt_ledger_coverage_invalid')
    if covered_rolls!={i for i,row in enumerate(state['day_rolls'])if row.get('source_kind')=='operator_manual'}:
        _fail('operator_day_roll_ledger_coverage_invalid')


def apply_operator_cash_review(state,review_envelope,broker,now,*,trading_calendar):
    """Apply explicitly reviewed cash facts. Never alter E/Available or send money.

    This pure transition is not source qualification. The production backend
    admits the fresh CTP source independently and commits cash with its actor.
    """
    validate_state(state);_require_v2(state);now=_time(now)
    raw,reviewed=_operator_review(review_envelope,state);snapshot=_broker(broker,state,now)
    _money(_parse(broker,'weekly19.ctp-account.v1','ctp_account_callback')['Available'],nonnegative=True)
    known=state.get('manual_cash_reviews',{}).get(raw['record_id'])
    if known is not None:
        if known['raw_sha256']!=review_envelope['raw_sha256'] or known['raw_payload']!=review_envelope['raw_payload']:
            _fail('operator_review_id_reused_with_different_content')
        # Replaying an old fact does not reconcile a new cash change; the caller
        # still runs the final cashflow gate after processing ALL references.
        return copy.deepcopy(state)
    if not _time(raw['created_at'])<=now<_time(raw['expires_at']): _fail('operator_review_expired_or_future')
    if (state['revision']!=raw['before_funding_revision'] or _hash(state)!=raw['before_funding_sha256']
            or state['cashflow_checkpoint']!=raw['before_checkpoint']
            or state['reserve_remaining_fen']!=raw['reserve_remaining_fen_before']
            or state['confirmed_topup_fen']!=raw['confirmed_topup_fen_before']):
        _fail('operator_review_stale_funding_baseline')
    if (any(snapshot[k]!=reviewed[k]for k in ('trading_day','deposit_fen','withdraw_fen'))
            or _time(snapshot['observed_at'])<_time(reviewed['observed_at'])):
        _fail('operator_review_current_cash_counters_changed')
    cp=state['cashflow_checkpoint']
    if cp is None: _fail('operator_review_initial_cash_observation_required')
    if (_time(snapshot['observed_at'])<_time(cp['observed_at']) or snapshot['trading_day']<cp['trading_day']):
        _fail('operator_review_checkpoint_rollback')
    calendar=[_day(day)for day in trading_calendar]
    if calendar!=sorted(set(calendar)) or cp['trading_day']not in calendar or snapshot['trading_day']not in calendar:
        _fail('operator_review_authoritative_calendar_required')
    expected=[day for day in calendar if cp['trading_day']<=day<snapshot['trading_day']]
    if [row['trading_day']for row in raw['closed_days']]!=expected:
        _fail('operator_review_closed_trading_days_incomplete')
    byday={day:0 for day in expected+[snapshot['trading_day']]};changed=copy.deepcopy(state)
    for row in raw['topups']:
        if row['receipt_id']in changed['receipts']: _fail('operator_receipt_already_consumed')
        request=changed['requests'].get(row['request_id'])
        if request is None: _fail('request_unknown')
        if any(row[k]!=request[k]for k in ('admitted_entry_ids','target_week_end','source_sha256')):
            _fail('operator_topup_original_admission_mismatch')
        occurred=_time(row['occurred_at'])
        if (row['request_id']in state['retirements'] or not _active(request)
                or now>=_time(request['expires_at'])): _fail('operator_topup_request_retired_or_expired')
        if not _time(request['created_at'])<=occurred<=_time(reviewed['observed_at']) or occurred<_time(cp['observed_at']):
            _fail('operator_topup_occurrence_out_of_window')
        if row['trading_day']not in byday: _fail('operator_topup_trading_day_outside_review')
        amount=row['amount_fen']
        if amount>request['amount_fen']-request['confirmed_fen'] or amount>changed['reserve_remaining_fen']:
            _fail('amount_exceeds_request_or_reserve')
        changed['reserve_remaining_fen']-=amount;changed['confirmed_topup_fen']+=amount;request['confirmed_fen']+=amount
        request['status']='confirmed'if request['confirmed_fen']==request['amount_fen']else'partially_confirmed'
        byday[row['trading_day']]+=amount
        changed['receipts'][row['receipt_id']]=dict(request_id=row['request_id'],amount_fen=amount,occurred_at=occurred.isoformat(),
            trading_day=row['trading_day'],raw_sha256=review_envelope['raw_sha256'],broker_sha256=broker['raw_sha256'],
            source_kind='operator_manual',manual_review_id=raw['record_id'])
    _operator_cash_totals(raw,snapshot)
    same=snapshot['trading_day']==cp['trading_day']
    if raw['expected_reserve_remaining_fen']!=changed['reserve_remaining_fen']:
        _fail('operator_review_offsite_reserve_mismatch')
    checkpoint=_checkpoint(snapshot);index=None
    if not same:
        index=len(changed['day_rolls'])
        changed['day_rolls'].append(dict(closing=_operator_closing(raw['closed_days'][0]),following=checkpoint,
            continuity_sha256=review_envelope['raw_sha256'],statement_id='operator:'+raw['record_id'],
            source_kind='operator_manual',manual_review_id=raw['record_id']))
    changed['cashflow_checkpoint']=checkpoint
    for request in changed['requests'].values():
        if _active(request):
            request['active_baseline']=copy.deepcopy(checkpoint);request['confirmed_before_active_day_fen']=request['confirmed_fen']
    changed.setdefault('manual_cash_reviews',{})[raw['record_id']]=dict(review_envelope,source_kind='operator_manual',
        applied_at=now.isoformat(),applied_account=copy.deepcopy(broker),after_checkpoint=checkpoint,day_roll_index=index,
        reserve_remaining_fen_after=changed['reserve_remaining_fen'],confirmed_topup_fen_after=changed['confirmed_topup_fen'])
    return _finish(state,changed)
