"""Literal account/cash-flow fixtures exercise the offline funding safety boundary.

They are deliberately not production qualification evidence.
"""
import copy
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'examples/portfolio_backtesting'))
try:
    import qmt_roll_weekly19_funding as funding
    from qmt_roll_weekly19_funding_store import FundingStore
except ModuleNotFoundError:
    funding = None
    FundingStore = None

NOW = datetime(2026, 10, 30, 16, 35, tzinfo=timezone(timedelta(hours=8)))
ACCOUNT = hashlib.sha256(b'9999\x00test-account').hexdigest()
RELEASE = 'weekly19-test-release'
SOURCE = 'a' * 64


def envelope(raw):
    payload = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return {'raw_payload': payload, 'raw_sha256': hashlib.sha256(payload.encode()).hexdigest()}


def broker(balance='120000.00', deposit='0.00', withdraw='0.00', at=NOW, day='2026-10-30', **overrides):
    raw = dict(schema='weekly19.ctp-account.v1', source_kind='ctp_account_callback',
               account_key=ACCOUNT, material_release_id=RELEASE,
               observed_at=at.isoformat(), trading_day=day, generation_uuid='generation-test-1',
               query_reqid=7, query_complete=True, CurrencyID='CNY',
               BrokerID='9999', AccountID='test-account',
               Balance=balance, Deposit=deposit, Withdraw=withdraw)
    raw.update(overrides)
    return envelope(raw)


def receipt(rid, amount='30000.00', receipt_id='bank-ref-1', at=NOW + timedelta(minutes=1), **overrides):
    raw = dict(schema='weekly19.bank-cashflow.v1', source_kind='broker_cashflow_receipt',
               account_key=ACCOUNT, material_release_id=RELEASE, request_id=rid,
               trading_day='2026-10-30', occurred_at=at.isoformat(), receipt_id=receipt_id,
               Amount=amount, Direction='deposit', Status='completed')
    raw.update(overrides)
    return envelope(raw)


def day_close(closing, next_day='2026-11-02', at=NOW + timedelta(minutes=5), **overrides):
    raw = json.loads(closing['raw_payload'])
    proof = dict(schema='weekly19.cashflow-day-close.v1', source_kind='broker_cashflow_day_close',
                 account_key=ACCOUNT, material_release_id=RELEASE, trading_day=raw['trading_day'],
                 next_trading_day=next_day, closed_at=at.isoformat(),
                 closing_account_sha256=closing['raw_sha256'], Deposit=raw['Deposit'],
                 Withdraw=raw['Withdraw'], cashflows_complete=True, statement_id='close-statement-1')
    proof.update(overrides)
    return envelope(proof)


# Frozen V1 fixture from checkpoint 09e7e07e8; not broker-origin proof.
LEGACY_PARTIAL_STATE = json.loads(r'''{
  "schema": "weekly19.external-funding.v1",
  "revision": 2,
  "account_key": "10a289b890bf2607d307a57084aa05d45d8729e0f2c9b7caf4fc48422070c765",
  "material_release_id": "weekly19-test-release",
  "cold_start_date": "2026-10-30",
  "initial_trading_fen": 15000000,
  "reserve_initial_fen": 15000000,
  "reserve_remaining_fen": 14000000,
  "confirmed_topup_fen": 1000000,
  "requests": {
    "0a0627c2b462c2e0926a7ec5ff04c1c1c2b383252cfdff861f3263975ff66663": {
      "request_id": "0a0627c2b462c2e0926a7ec5ff04c1c1c2b383252cfdff861f3263975ff66663",
      "account_key": "10a289b890bf2607d307a57084aa05d45d8729e0f2c9b7caf4fc48422070c765",
      "material_release_id": "weekly19-test-release",
      "target_week_end": "2026-10-30",
      "admitted_entry_ids": [
        "native-entry-1"
      ],
      "source_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "created_at": "2026-10-30T16:35:00+08:00",
      "expires_at": "2026-11-06T16:35:00+08:00",
      "amount_fen": 3000000,
      "confirmed_fen": 1000000,
      "status": "partially_confirmed",
      "baseline": {
        "trading_day": "2026-10-30",
        "observed_at": "2026-10-30T16:35:00+08:00",
        "raw_sha256": "4879e01c6450e63e9f87115459c5c6c2e90a796c6dcd4af6dbb250394014d857",
        "deposit_fen": 0,
        "withdraw_fen": 0
      },
      "active_baseline": {
        "trading_day": "2026-10-30",
        "observed_at": "2026-10-30T16:35:00+08:00",
        "raw_sha256": "4879e01c6450e63e9f87115459c5c6c2e90a796c6dcd4af6dbb250394014d857",
        "deposit_fen": 0,
        "withdraw_fen": 0
      },
      "confirmed_before_active_day_fen": 0,
      "marked_equity_fen": 12000000
    }
  },
  "receipts": {
    "bank-ref-1": {
      "request_id": "0a0627c2b462c2e0926a7ec5ff04c1c1c2b383252cfdff861f3263975ff66663",
      "amount_fen": 1000000,
      "occurred_at": "2026-10-30T16:36:00+08:00",
      "raw_sha256": "bc1192e4588a9733181e7c1fe8102cd309644a4e294ded75c35b064b7d565e1c",
      "broker_sha256": "554301533bf68edbf7779ed7b0c4cc4f37b1e8fb250f4f2922513c636f29779a"
    }
  },
  "admitted_entries": {
    "c78d5c89c9ecd2ca2ef9523a75e4c2afc392c57e4564d5b1b1ccf69e2cb58261": "0a0627c2b462c2e0926a7ec5ff04c1c1c2b383252cfdff861f3263975ff66663"
  },
  "cashflow_checkpoint": {
    "trading_day": "2026-10-30",
    "observed_at": "2026-10-30T16:37:00+08:00",
    "raw_sha256": "554301533bf68edbf7779ed7b0c4cc4f37b1e8fb250f4f2922513c636f29779a",
    "deposit_fen": 1000000,
    "withdraw_fen": 0
  },
  "day_rolls": [],
  "production_qualified": false
}''')


def _cold_store_worker(path,barrier,queue,initial):
    try:
        barrier.wait(timeout=10)
        try:
            FundingStore(Path(path)).create(initial)
            queue.put('created')
        except funding.FundingError as exc:
            queue.put('already_exists' if 'store_already_exists' in str(exc) else 'error:'+str(exc))
    except BaseException as exc:
        queue.put('worker_error:'+type(exc).__name__+':'+str(exc))


class ExternalFundingTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(funding, 'external funding component is absent')
        self.state = funding.initial_state(ACCOUNT, RELEASE, '2026-10-30')

    def recommend(self, state=None, evidence=None, ids=None, at=NOW):
        return funding.recommend_topup(self.state if state is None else state,
                                      broker() if evidence is None else evidence,
                                      '2026-10-30', ['native-entry-1'] if ids is None else ids,
                                      SOURCE, at)

    def pending(self, balance='120000.00'):
        result = self.recommend(evidence=broker(balance=balance))
        return result['state'], result['recommendation']['request_id']

    def confirm(self, state, rid, amount='30000.00', deposit='30000.00', receipt_id='bank-ref-1', **overrides):
        at = NOW + timedelta(minutes=2)
        return funding.confirm_topup(state, rid, receipt(rid, amount, receipt_id, **overrides),
                                     broker(balance='151000.00', deposit=deposit, at=at), at)

    def test_recommendation_never_mutates_inputs_or_creates_trading_equity(self):
        before = copy.deepcopy(self.state)
        result = self.recommend()
        self.assertEqual(self.state, before)
        self.assertEqual(result['recommendation']['amount_fen'], 3000000)
        self.assertEqual(result['state']['reserve_remaining_fen'], 15000000)
        self.assertEqual(result['state']['confirmed_topup_fen'], 0)
        self.assertFalse(result['recommendation']['production_qualified'])
        self.assertNotIn('trading_equity_fen', result['state'])
        with self.assertRaisesRegex(funding.FundingError, 'funding_pending'):
            funding.assert_open_funding_ready(result['state'], broker(), NOW)

    def test_no_admitted_native_entry_does_not_request_even_when_account_injured(self):
        result = self.recommend(ids=[])
        self.assertEqual(result['recommendation']['status'], 'no_admitted_entry')
        self.assertEqual(result['state']['requests'], {})

    def test_marked_equity_at_floor_or_profit_never_refills_reserve(self):
        for equity in ('150000.00', '200000.00'):
            with self.subTest(equity=equity):
                result = self.recommend(evidence=broker(balance=equity))
                self.assertEqual(result['recommendation']['amount_fen'], 0)
                self.assertEqual(result['state']['reserve_remaining_fen'], 15000000)

    def test_shortfall_capped_at_remaining_offsite_reserve(self):
        state, rid = self.pending(balance='10000.00')
        state = self.confirm(state, rid, amount='140000.00', deposit='140000.00')
        result = self.recommend(state, broker(balance='10000.00', deposit='140000.00', at=NOW + timedelta(minutes=3)),
                                ids=['native-entry-2'], at=NOW + timedelta(minutes=3))
        self.assertEqual(result['recommendation']['amount_fen'], 1000000)

    def test_exact_receipt_and_deposit_delta_reduce_only_offsite_reserve(self):
        state, rid = self.pending()
        before = copy.deepcopy(state)
        accepted = self.confirm(state, rid)
        self.assertEqual(state, before)
        self.assertEqual(accepted['reserve_remaining_fen'], 12000000)
        self.assertEqual(accepted['confirmed_topup_fen'], 3000000)
        self.assertEqual(accepted['requests'][rid]['status'], 'confirmed')
        self.assertFalse(accepted['production_qualified'])
        self.assertIsNone(funding.assert_open_funding_ready(accepted,
            broker(balance='151000.00', deposit='30000.00', at=NOW + timedelta(minutes=2)), NOW + timedelta(minutes=2)))

    def test_balance_increase_or_float_profit_is_not_a_deposit(self):
        state, rid = self.pending()
        with self.assertRaisesRegex(funding.FundingError, 'deposit_delta'):
            self.confirm(state, rid, deposit='0.00')
        self.assertEqual(state['reserve_remaining_fen'], 15000000)

    def test_partial_receipts_are_counted_once_and_block_until_complete(self):
        state, rid = self.pending()
        one = self.confirm(state, rid, amount='10000.00', deposit='10000.00')
        self.assertEqual(one['reserve_remaining_fen'], 14000000)
        self.assertEqual(one['requests'][rid]['status'], 'partially_confirmed')
        with self.assertRaisesRegex(funding.FundingError, 'funding_pending'):
            funding.assert_open_funding_ready(one,
                broker(deposit='10000.00', at=NOW + timedelta(minutes=2)), NOW + timedelta(minutes=2))
        two = funding.confirm_topup(one, rid,
            receipt(rid, '20000.00', 'bank-ref-2', at=NOW + timedelta(minutes=3)),
            broker(deposit='30000.00', at=NOW + timedelta(minutes=4)), NOW + timedelta(minutes=4))
        self.assertEqual(two['reserve_remaining_fen'], 12000000)
        self.assertEqual(two['requests'][rid]['status'], 'confirmed')

    def test_duplicate_receipt_is_idempotent_without_double_debit(self):
        state, rid = self.pending()
        accepted = self.confirm(state, rid)
        replay = self.confirm(accepted, rid)
        self.assertEqual(replay, accepted)
        with self.assertRaisesRegex(funding.FundingError, 'receipt_reused'):
            self.confirm(accepted, rid, amount='29999.00')

    def test_excess_or_unknown_deposit_and_withdrawal_fail_without_partial_state(self):
        state, rid = self.pending()
        before = copy.deepcopy(state)
        for evidence in (broker(deposit='30001.00', at=NOW + timedelta(minutes=2)),
                         broker(deposit='30000.00', withdraw='1.00', at=NOW + timedelta(minutes=2))):
            with self.subTest(evidence=evidence), self.assertRaises(funding.FundingError):
                funding.confirm_topup(state, rid, receipt(rid), evidence, NOW + timedelta(minutes=2))
            self.assertEqual(state, before)
        with self.assertRaisesRegex(funding.FundingError, 'amount_exceeds'):
            self.confirm(state, rid, amount='30001.00', deposit='30001.00')

    def test_unknown_cashflow_blocks_recommendation_and_open(self):
        observed = self.recommend(ids=[])['state']
        evidence = broker(balance='125000.00', deposit='5000.00', at=NOW + timedelta(minutes=1))
        with self.assertRaisesRegex(funding.FundingError, 'unreconciled_cashflow'):
            self.recommend(observed, evidence, at=NOW + timedelta(minutes=1))
        with self.assertRaisesRegex(funding.FundingError, 'unreconciled_cashflow'):
            funding.assert_open_funding_ready(observed, evidence, NOW + timedelta(minutes=1))

    def test_exhausted_reserve_with_positive_equity_does_not_permanently_block_open(self):
        state, rid = self.pending(balance='0.00')
        state = self.confirm(state, rid, amount='150000.00', deposit='150000.00')
        at = NOW + timedelta(minutes=3)
        evidence = broker(balance='100.00', deposit='150000.00', at=at)
        result = self.recommend(state, evidence, ids=['native-entry-2'], at=at)
        self.assertEqual(result['recommendation']['status'], 'reserve_exhausted')
        self.assertEqual(result['state']['requests'][rid]['status'], 'confirmed')
        self.assertIsNone(funding.assert_open_funding_ready(result['state'], evidence, at))
        with self.assertRaisesRegex(funding.FundingError, 'nonpositive_equity'):
            funding.assert_open_funding_ready(result['state'], broker(balance='0.00', deposit='150000.00', at=at), at)

    def test_request_identity_is_stable_and_duplicate_admission_does_not_double_request(self):
        result = self.recommend()
        again = self.recommend(result['state'])
        self.assertEqual(result['recommendation']['request_id'], again['recommendation']['request_id'])
        self.assertEqual(len(again['state']['requests']), 1)
        self.assertEqual(result['state'], again['state'])

    def test_raw_sha_verified_flag_and_account_release_binding_fail_closed(self):
        evidence = broker()
        evidence['raw_sha256'] = '0' * 64
        bads = [evidence, {'verified': True, 'equity': '120000.00'},
                broker(AccountID='another'), broker(material_release_id='another'),
                broker(query_complete=False), broker(CurrencyID='USD')]
        for bad in bads:
            with self.subTest(bad=bad), self.assertRaises(funding.FundingError):
                self.recommend(evidence=bad)

    def test_non_decimal_floats_nonfinite_and_subcent_inputs_rejected(self):
        for amount in (120000.1, 'NaN', 'Infinity', '12.001', '-Infinity', True, '1e5'):
            with self.subTest(amount=amount), self.assertRaises(funding.FundingError):
                self.recommend(evidence=broker(balance=amount))

    def test_naive_stale_future_or_out_of_order_account_timestamp_rejected(self):
        for at in (NOW.replace(tzinfo=None), NOW - timedelta(seconds=301), NOW + timedelta(seconds=1)):
            with self.subTest(at=at), self.assertRaises(funding.FundingError):
                self.recommend(evidence=broker(at=at))
        observed = self.recommend(ids=[])['state']
        with self.assertRaisesRegex(funding.FundingError, 'out_of_order'):
            self.recommend(observed, broker(at=NOW - timedelta(seconds=1)))
        with self.assertRaises(funding.FundingError):
            self.recommend(at=NOW.replace(tzinfo=None))

    def test_receipt_cross_account_release_request_date_or_time_rejected(self):
        state, rid = self.pending()
        bads = [dict(account_key='b' * 64), dict(material_release_id='other'),
                dict(request_id='other'), dict(trading_day='2026-11-02'),
                dict(occurred_at=(NOW - timedelta(seconds=1)).isoformat()),
                dict(Status='pending'), dict(Direction='withdraw')]
        for overrides in bads:
            with self.subTest(overrides=overrides), self.assertRaises(funding.FundingError):
                self.confirm(state, rid, **overrides)

    def test_request_expiry_does_not_consume_reserve_and_blocks_late_confirmation(self):
        state, rid = self.pending()
        late = NOW + timedelta(days=8)
        with self.assertRaisesRegex(funding.FundingError, 'request_expired'):
            funding.confirm_topup(state, rid, receipt(rid, at=late),
                broker(deposit='30000.00', at=late, day='2026-11-07'), late)
        self.assertEqual(state['reserve_remaining_fen'], 15000000)

    def test_day_roll_requires_closing_cashflow_evidence(self):
        observed = self.recommend(ids=[])['state']
        monday = NOW + timedelta(days=3)
        with self.assertRaisesRegex(funding.FundingError, 'day_roll_requires_reconciliation'):
            funding.assert_open_funding_ready(observed, broker(at=monday, day='2026-11-02'), monday)
        rolled = funding.reconcile_trading_day(observed,
            broker(at=NOW + timedelta(minutes=1)), broker(at=monday, day='2026-11-02'), monday,
            continuity_receipt=day_close(broker(at=NOW + timedelta(minutes=1))))
        self.assertIsNone(funding.assert_open_funding_ready(rolled, broker(at=monday, day='2026-11-02'), monday))
        with self.assertRaises(funding.FundingError):
            funding.reconcile_trading_day(observed, broker(deposit='1.00', at=NOW + timedelta(minutes=1)),
                broker(at=monday, day='2026-11-02'), monday,
                continuity_receipt=day_close(broker(at=NOW + timedelta(minutes=1))))

    def test_pending_request_can_cross_friday_night_to_monday_nominal_day_with_full_evidence(self):
        state, rid = self.pending()
        close = broker(at=NOW + timedelta(minutes=1))
        night = NOW.replace(hour=21, minute=0)
        opening = broker(at=night, day='2026-11-02')
        rolled = funding.reconcile_trading_day(state, close, opening, night,
                                              continuity_receipt=day_close(close))
        self.assertEqual(rolled['requests'][rid]['status'], 'pending')
        self.assertEqual(rolled['reserve_remaining_fen'], 15000000)
        at = night + timedelta(minutes=2)
        accepted = funding.confirm_topup(rolled, rid,
            receipt(rid, at=night + timedelta(minutes=1), trading_day='2026-11-02'),
            broker(balance='150000.00', deposit='30000.00', at=at, day='2026-11-02'), at)
        self.assertEqual(accepted['reserve_remaining_fen'], 12000000)
        self.assertEqual(accepted['requests'][rid]['status'], 'confirmed')

    def test_cross_day_missing_closure_or_zero_start_or_raw_receipt_is_fail_closed(self):
        state, rid = self.pending()
        close = broker(at=NOW + timedelta(minutes=1))
        night = NOW.replace(hour=21, minute=0)
        opening = broker(at=night, day='2026-11-02')
        for proof in (None, day_close(close, cashflows_complete=False),
                      day_close(close, closing_account_sha256='0' * 64),
                      day_close(close, next_trading_day='2026-11-03')):
            with self.subTest(proof=proof), self.assertRaises(funding.FundingError):
                funding.reconcile_trading_day(state, close, opening, night, continuity_receipt=proof)
        with self.assertRaises(funding.FundingError):
            funding.reconcile_trading_day(state, close,
                broker(at=night, day='2026-11-02', deposit='30000.00'), night,
                continuity_receipt=day_close(close))
        with self.assertRaises(funding.FundingError):
            funding.confirm_topup(state, rid, receipt(rid, at=night, trading_day='2026-11-02'),
                broker(at=night, day='2026-11-02', deposit='30000.00'), night)

    def test_partial_request_can_finish_after_verified_day_roll(self):
        state, rid = self.pending()
        state = self.confirm(state, rid, amount='10000.00', deposit='10000.00')
        close = broker(deposit='10000.00', at=NOW + timedelta(minutes=3))
        night = NOW.replace(hour=21, minute=0)
        rolled = funding.reconcile_trading_day(state, close,
            broker(at=night, day='2026-11-02'), night, continuity_receipt=day_close(close))
        accepted = funding.confirm_topup(rolled, rid,
            receipt(rid, '20000.00', 'bank-ref-2', at=night + timedelta(minutes=1), trading_day='2026-11-02'),
            broker(deposit='20000.00', at=night + timedelta(minutes=2), day='2026-11-02'),
            night + timedelta(minutes=2))
        self.assertEqual(accepted['reserve_remaining_fen'], 12000000)
        self.assertEqual(accepted['confirmed_topup_fen'], 3000000)

    def test_duplicate_confirmed_receipt_after_day_roll_and_restart_is_still_idempotent(self):
        state, rid = self.pending()
        accepted = self.confirm(state, rid)
        close = broker(deposit='30000.00', at=NOW + timedelta(minutes=3))
        night = NOW.replace(hour=21, minute=0)
        opening = broker(at=night, day='2026-11-02')
        rolled = funding.reconcile_trading_day(accepted, close, opening, night,
                                              continuity_receipt=day_close(close))
        replay = funding.confirm_topup(rolled, rid, receipt(rid), opening, night)
        self.assertEqual(replay, rolled)

    def test_distinct_receipt_cannot_be_backdated_before_verified_day_start(self):
        state, rid = self.pending()
        close = broker(at=NOW + timedelta(minutes=1))
        night = NOW.replace(hour=21, minute=0)
        opening = broker(at=night, day='2026-11-02')
        rolled = funding.reconcile_trading_day(state, close, opening, night,
                                              continuity_receipt=day_close(close))
        with self.assertRaisesRegex(funding.FundingError, 'receipt_before_active_day'):
            funding.confirm_topup(rolled, rid,
                receipt(rid, at=NOW + timedelta(minutes=4), trading_day='2026-11-02'),
                broker(deposit='30000.00', at=night + timedelta(minutes=2), day='2026-11-02'),
                night + timedelta(minutes=2))

    def test_equal_expiration_boundary_is_expired(self):
        state, rid = self.pending()
        expiry = NOW + timedelta(days=7)
        with self.assertRaisesRegex(funding.FundingError, 'request_expired'):
            funding.confirm_topup(state, rid, receipt(rid, at=expiry),
                broker(deposit='30000.00', at=expiry), expiry)

    def test_cold_start_uses_nominal_trading_day_not_observation_calendar_day(self):
        cold = funding.initial_state(ACCOUNT, RELEASE, '2026-11-02')
        prepared = self.recommend(cold, broker(balance='150000.00'), ids=[])['state']
        with self.assertRaisesRegex(funding.FundingError, 'before_cold_start'):
            funding.assert_open_funding_ready(prepared, broker(balance='150000.00'), NOW)
        close = broker(balance='150000.00', at=NOW + timedelta(minutes=1))
        night = NOW.replace(hour=21, minute=0)
        opening = broker(balance='150000.00', at=night, day='2026-11-02')
        rolled = funding.reconcile_trading_day(prepared, close, opening, night,
                                              continuity_receipt=day_close(close))
        self.assertIsNone(funding.assert_open_funding_ready(rolled, opening, night))

    def test_request_cannot_hide_another_request_by_changing_admission_ids(self):
        state, rid = self.pending()
        for ids in (['other-native-entry'], ['native-entry-1', 'other-native-entry']):
            result = self.recommend(state, ids=ids)
            self.assertEqual(result['recommendation']['request_id'], rid)
            self.assertEqual(len(result['state']['requests']), 1)

    def test_source_hash_and_request_identity_are_checked_when_reloading_state(self):
        state, rid = self.pending()
        corrupted = copy.deepcopy(state)
        corrupted['requests'][rid]['admitted_entry_ids'] = ['unrelated-entry']
        with self.assertRaisesRegex(funding.FundingError, 'request_identity'):
            funding.assert_open_funding_ready(corrupted, broker(), NOW)

    def test_corrupt_reserve_or_receipt_ledger_cannot_pass_open(self):
        observed = self.recommend(ids=[])['state']
        for mutation in ({'reserve_remaining_fen': -1}, {'reserve_remaining_fen': 16000000},
                         {'confirmed_topup_fen': 1}, {'production_qualified': True}):
            changed = copy.deepcopy(observed)
            changed.update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(funding.FundingError):
                funding.assert_open_funding_ready(changed, broker(), NOW)


class FundingV2AdviceTest(unittest.TestCase):
    setUp=ExternalFundingTest.setUp
    recommend=ExternalFundingTest.recommend
    pending=ExternalFundingTest.pending
    confirm=ExternalFundingTest.confirm
    """A pending recommendation is an offer, never a debt or synthetic equity."""
    def test_v2_unpaid_advice_does_not_block_when_real_marked_equity_recovers(self):
        state,rid=self.pending()
        at=NOW+timedelta(minutes=3); evidence=broker(balance='151000.00',at=at)
        self.assertIsNone(funding.assert_open_funding_ready(state,evidence,at))
        result=self.recommend(state,evidence,at=at)
        self.assertEqual(result['recommendation']['amount_fen'],0)
        self.assertEqual(result['recommendation']['status'],'equity_at_or_above_floor')
        self.assertEqual(result['state']['reserve_remaining_fen'],15000000)
        self.assertEqual(result['state']['requests'][rid]['confirmed_fen'],0)

    def test_v2_partial_cash_that_reaches_floor_does_not_force_remaining_offer(self):
        state,rid=self.pending()
        partial=self.confirm(state,rid,amount='10000.00',deposit='10000.00')
        at=NOW+timedelta(minutes=3); evidence=broker(balance='150000.00',deposit='10000.00',at=at)
        self.assertIsNone(funding.assert_open_funding_ready(partial,evidence,at))
        result=self.recommend(partial,evidence,at=at)
        self.assertEqual(result['recommendation']['amount_fen'],0)
        self.assertEqual(result['state']['reserve_remaining_fen'],14000000)
        self.assertEqual(result['state']['requests'][rid]['confirmed_fen'],1000000)

    def test_v2_changed_current_gap_needs_proven_refresh_before_actionable_new_offer(self):
        state,rid=self.pending()
        at=NOW+timedelta(minutes=1); evidence=broker(balance='100000.00',at=at)
        changed=self.recommend(state,evidence,at=at)
        advice=changed['recommendation']
        self.assertEqual(advice['amount_fen'],5000000)
        self.assertEqual(advice['historical_request_remaining_fen'],3000000)
        self.assertEqual(advice['status'],'request_refresh_required')
        self.assertFalse(advice['actionable'])
        self.assertIsNone(advice['request_id'])
        retired=funding.retire_topup_request(changed['state'],rid,evidence,at,reason='superseded_current_gap')
        again=self.recommend(retired,evidence,at=at)
        newrid=again['recommendation']['request_id']
        self.assertNotEqual(newrid,rid)
        self.assertTrue(again['recommendation']['actionable'])
        self.assertEqual(again['recommendation']['amount_fen'],5000000)
        self.assertEqual(again['state']['requests'][rid]['status'],'retired_unpaid')
        self.assertEqual(again['state']['requests'][rid]['amount_fen'],3000000)
        self.assertEqual(again['state']['admitted_entries'],state['admitted_entries'])
        self.assertEqual(next(iter(again['state']['request_attempts'].values())),[rid,newrid])

    def test_v2_retirement_preserves_paid_reserve_and_late_unknown_money_is_blocked(self):
        state,rid=self.pending()
        partial=self.confirm(state,rid,amount='10000.00',deposit='10000.00')
        at=NOW+timedelta(minutes=3); evidence=broker(balance='150000.00',deposit='10000.00',at=at)
        retired=funding.retire_topup_request(partial,rid,evidence,at,reason='equity_recovered')
        self.assertEqual(retired['requests'][rid]['status'],'retired_partial')
        self.assertEqual(retired['reserve_remaining_fen'],14000000)
        self.assertEqual(retired['receipts'],partial['receipts'])
        self.assertIn(rid,retired['retirements'])
        self.assertEqual(retired['retirements'][rid]['unpaid_fen'],2000000)
        with self.assertRaisesRegex(funding.FundingError,'retired_request'):
            funding.confirm_topup(retired,rid,
                receipt(rid,'20000.00','late-bank-ref',at=at+timedelta(minutes=1)),
                broker(balance='170000.00',deposit='30000.00',at=at+timedelta(minutes=2)),at+timedelta(minutes=2))
        with self.assertRaisesRegex(funding.FundingError,'unreconciled_cashflow'):
            funding.assert_open_funding_ready(retired,
                broker(balance='170000.00',deposit='30000.00',at=at+timedelta(minutes=2)),at+timedelta(minutes=2))
        replay=funding.confirm_topup(retired,rid,receipt(rid,'10000.00'),evidence,at)
        self.assertEqual(replay,retired)

    def test_v2_unknown_or_missing_day_continuity_cannot_retire_even_when_equity_recovers(self):
        state,rid=self.pending()
        with self.assertRaises(funding.FundingError):
            funding.retire_topup_request(state,rid,broker(balance='150000.00',deposit='1.00'),NOW,reason='equity_recovered')
        monday=NOW+timedelta(days=3)
        with self.assertRaisesRegex(funding.FundingError,'day_roll_requires_reconciliation'):
            funding.retire_topup_request(state,rid,broker(balance='150000.00',at=monday,day='2026-11-02'),monday,reason='equity_recovered')
        self.assertEqual(state['reserve_remaining_fen'],15000000)

    def test_v2_expired_partial_can_be_proven_retired_then_new_week_admitted(self):
        state,rid=self.pending()
        state=self.confirm(state,rid,amount='10000.00',deposit='10000.00')
        at=NOW+timedelta(minutes=3); current_deposit='10000.00'; current_day='2026-10-30'
        for next_day in ('2026-11-02','2026-11-03','2026-11-04','2026-11-05','2026-11-06'):
            close=broker(balance='142000.00',deposit=current_deposit,at=at,day=current_day)
            following=datetime.fromisoformat(next_day+'T16:35:00+08:00')
            next_broker=broker(balance='142000.00',at=following,day=next_day)
            state=funding.reconcile_trading_day(state,close,next_broker,following,
                continuity_receipt=day_close(close,next_day=next_day,at=at+timedelta(minutes=1)))
            at=following+timedelta(minutes=1); current_deposit='0.00'; current_day=next_day
        evidence=broker(balance='142000.00',at=at,day=current_day)
        state=funding.retire_topup_request(state,rid,evidence,at,reason='expired_superseded')
        self.assertEqual(state['reserve_remaining_fen'],14000000)
        self.assertEqual(state['requests'][rid]['status'],'retired_partial')
        result=funding.recommend_topup(state,evidence,'2026-11-06',['new-native-entry'],SOURCE,at)
        self.assertEqual(result['recommendation']['amount_fen'],800000)
        self.assertNotEqual(result['recommendation']['request_id'],rid)
        self.assertEqual(result['state']['receipts'],state['receipts'])

    def test_v2_same_funded_original_admission_is_consumed_across_generation_and_source_changes(self):
        state,rid=self.pending()
        paid=self.confirm(state,rid)
        at=NOW+timedelta(minutes=3)
        evidence=broker(balance='130000.00',deposit='30000.00',at=at,generation_uuid='another-generation')
        result=funding.recommend_topup(paid,evidence,'2026-10-30',['native-entry-1'],'b'*64,at)
        self.assertEqual(result['recommendation']['status'],'duplicate_admission')
        self.assertEqual(result['recommendation']['amount_fen'],0)
        self.assertEqual(len(result['state']['requests']),1)
        self.assertEqual(result['state']['reserve_remaining_fen'],12000000)

    def test_v2_recovery_retires_original_admission_without_refunding_same_signal_later(self):
        state,rid=self.pending()
        at=NOW+timedelta(minutes=1); evidence=broker(balance='150000.00',at=at)
        state=funding.retire_topup_request(state,rid,evidence,at,reason='equity_recovered')
        result=self.recommend(state,broker(balance='130000.00',at=at+timedelta(minutes=1)),at=at+timedelta(minutes=1))
        self.assertEqual(result['recommendation']['status'],'duplicate_admission')
        self.assertEqual(len(result['state']['requests']),1)

    def test_v2_explicit_migration_preserves_v1_identity_paid_receipts_and_single_revision(self):
        old=copy.deepcopy(LEGACY_PARTIAL_STATE); before=copy.deepcopy(old)
        funding.validate_state(old)
        upgraded=funding.upgrade_funding_state(old)
        self.assertEqual(old,before)
        self.assertEqual(upgraded['schema'],'weekly19.external-funding.v2')
        self.assertEqual(upgraded['revision'],old['revision']+1)
        for key in ('account_key','material_release_id','cold_start_date','reserve_remaining_fen','confirmed_topup_fen',
                    'requests','receipts','admitted_entries','cashflow_checkpoint','day_rolls'):
            self.assertEqual(upgraded[key],old[key])
        self.assertEqual(funding.upgrade_funding_state(upgraded),upgraded)
        with self.assertRaisesRegex(funding.FundingError,'upgrade_required'):
            funding.assert_open_funding_ready(old,broker(balance='150000.00',deposit='10000.00',at=NOW+timedelta(minutes=3)),NOW+timedelta(minutes=3))

    def test_v2_recovered_equity_still_rejects_unknown_cash_and_retired_offer_never_is_debt(self):
        state,rid=self.pending()
        at=NOW+timedelta(minutes=1)
        with self.assertRaisesRegex(funding.FundingError,'unreconciled_cashflow'):
            funding.assert_open_funding_ready(state,broker(balance='151000.00',deposit='1.00',at=at),at)
        retired=funding.retire_topup_request(state,rid,broker(balance='150000.00',at=at),at,reason='equity_recovered')
        self.assertIsNone(funding.assert_open_funding_ready(retired,broker(balance='130000.00',at=at),at))

    def test_v2_partial_refresh_and_new_payment_preserve_old_paid_cash_without_replenishment(self):
        state,rid=self.pending(); state=self.confirm(state,rid,amount='10000.00',deposit='10000.00')
        at=NOW+timedelta(minutes=3); evidence=broker(balance='140000.00',deposit='10000.00',at=at)
        retired=funding.retire_topup_request(state,rid,evidence,at,reason='superseded_current_gap')
        result=self.recommend(retired,evidence,at=at); newrid=result['recommendation']['request_id']
        paid=funding.confirm_topup(result['state'],newrid,receipt(newrid,'10000.00','bank-ref-new',at=at+timedelta(minutes=1)),
            broker(balance='150000.00',deposit='20000.00',at=at+timedelta(minutes=2)),at+timedelta(minutes=2))
        self.assertEqual((paid['reserve_remaining_fen'],paid['confirmed_topup_fen']),(13000000,2000000))
        self.assertEqual(paid['requests'][rid]['status'],'retired_partial')
        self.assertEqual(paid['requests'][newrid]['status'],'confirmed')
        self.assertEqual(len(paid['receipts']),2)
        bad=copy.deepcopy(result['state'])
        next(iter(bad['request_attempts'].values())).pop()
        with self.assertRaisesRegex(funding.FundingError,'request_attempt'):
            funding.validate_state(bad)

    def test_v2_retirement_does_not_erase_cashflow_or_accept_invalid_reasons(self):
        state,rid=self.pending()
        for reason in ('expired_superseded','equity_recovered','superseded_current_gap','operator_says_ok'):
            with self.subTest(reason=reason),self.assertRaises(funding.FundingError):
                funding.retire_topup_request(state,rid,broker(),NOW,reason=reason)
        self.assertEqual(state['reserve_remaining_fen'],15000000)


class FundingInitialObservationTest(unittest.TestCase):
    def setUp(self):
        self.state=funding.initial_state(ACCOUNT,RELEASE,'2026-10-27')
        self.at=NOW-timedelta(days=2)
        self.evidence=broker(balance='150000.00',deposit='150000.00',at=self.at,day='2026-10-28',
            Available='150000.00',query_last_seen=True,query_error_rows=0)

    def test_begin_any_weekday_pins_real_initial_deposit_without_consuming_reserve_or_admission(self):
        before=copy.deepcopy(self.state)
        result=funding.begin_cash_observation(self.state,self.evidence,self.at)
        self.assertEqual(self.state,before)
        self.assertEqual(result['revision'],1)
        self.assertEqual(result['cashflow_checkpoint']['deposit_fen'],15000000)
        for key in ('reserve_remaining_fen','confirmed_topup_fen','requests','receipts','admitted_entries','request_attempts','day_rolls'):
            self.assertEqual(result[key],before[key])
        self.assertEqual(funding.begin_cash_observation(result,self.evidence,self.at),result)
        self.assertFalse(result['production_qualified'])

    def test_begin_rejects_later_reset_and_no_initial_equity_guess(self):
        result=funding.begin_cash_observation(self.state,self.evidence,self.at)
        later=broker(balance='150000.00',deposit='150000.00',at=self.at+timedelta(seconds=1),day='2026-10-28',
            Available='150000.00',query_last_seen=True,query_error_rows=0)
        with self.assertRaisesRegex(funding.FundingError,'initial_cash_observation_already_exists'):
            funding.begin_cash_observation(result,later,self.at+timedelta(seconds=1))
        without_admission=funding.recommend_topup(self.state,broker(),'2026-10-30',[],SOURCE,NOW)['state']
        noninitial=broker(Available='120000.00',query_last_seen=True,query_error_rows=0)
        with self.assertRaises(funding.FundingError):
            funding.begin_cash_observation(without_admission,noninitial,NOW)
        for balance in ('149999.99','150000.01','-1.00'):
            evidence=broker(balance=balance,at=self.at,day='2026-10-28',Available='150000.00',query_last_seen=True,query_error_rows=0)
            with self.subTest(balance=balance),self.assertRaises(funding.FundingError):
                funding.begin_cash_observation(self.state,evidence,self.at)

    def test_begin_rejects_missing_available_incomplete_query_identity_raw_or_time(self):
        raw=json.loads(self.evidence['raw_payload'])
        cases=[dict(raw,Available=None),dict(raw,Available='NaN'),dict(raw,Available='-0.01'),dict(raw,Available=150000.0),
            dict(raw,query_last_seen=False),dict(raw,query_error_rows=1),dict(raw,query_error_rows=False),
            dict(raw,query_complete=False),dict(raw,AccountID='foreign'),dict(raw,material_release_id='other'),
            dict(raw,observed_at=(self.at+timedelta(seconds=1)).isoformat())]
        missing=dict(raw);missing.pop('Available');cases.append(missing)
        for changed in cases:
            with self.subTest(changed=changed),self.assertRaises(funding.FundingError):
                funding.begin_cash_observation(self.state,envelope(changed),self.at)
        with self.assertRaises(funding.FundingError):
            funding.begin_cash_observation(self.state,dict(self.evidence,raw_sha256='0'*64),self.at)
        with self.assertRaises(funding.FundingError):
            funding.begin_cash_observation(self.state,self.evidence,self.at+timedelta(seconds=301))

    def test_begin_cannot_seed_before_cold_start_or_reinitialize_existing_admissions(self):
        future=funding.initial_state(ACCOUNT,RELEASE,'2026-10-29')
        with self.assertRaises(funding.FundingError): funding.begin_cash_observation(future,self.evidence,self.at)
        pending=funding.recommend_topup(self.state,broker(),'2026-10-30',['native-entry-1'],SOURCE,NOW)['state']
        with self.assertRaises(funding.FundingError): funding.begin_cash_observation(pending,self.evidence,self.at)

    def test_initial_checkpoint_detects_cash_before_first_friday_signal(self):
        observed=funding.begin_cash_observation(self.state,self.evidence,self.at)
        changed=broker(balance='151000.00',deposit='151000.00',at=self.at+timedelta(seconds=30),day='2026-10-28')
        with self.assertRaisesRegex(funding.FundingError,'unreconciled_cashflow_deposit'):
            funding.assert_open_funding_ready(observed,changed,self.at+timedelta(seconds=30))
        friday=broker(balance='150000.00',deposit='0.00',at=NOW,day='2026-10-30')
        with self.assertRaisesRegex(funding.FundingError,'day_roll_requires_reconciliation'):
            funding.recommend_topup(observed,friday,'2026-10-30',['native-entry-1'],SOURCE,NOW)

    def test_initial_observation_is_one_cas_transition_and_restart_safe(self):
        with tempfile.TemporaryDirectory(prefix='weekly19-bootstrap-',dir='/private/tmp') as temp:
            store=FundingStore(Path(temp)/'cash.json');store.create(self.state)
            observed=funding.begin_cash_observation(store.load(),self.evidence,self.at)
            store.commit(0,observed)
            self.assertEqual(store.load(),observed)
            self.assertEqual(funding.begin_cash_observation(store.load(),self.evidence,self.at),observed)


class FundingStoreTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(FundingStore, 'private atomic funding store is absent')
        self.temp = tempfile.TemporaryDirectory(prefix='weekly19-funding-', dir='/private/tmp')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'state.json'
        self.store = FundingStore(self.path)
        self.initial = funding.initial_state(ACCOUNT, RELEASE, '2026-10-30')

    def test_restart_preserves_request_and_receipt_idempotence_with_private_permissions(self):
        self.store.create(self.initial)
        result = funding.recommend_topup(self.store.load(), broker(), '2026-10-30', ['native-entry-1'], SOURCE, NOW)
        self.store.commit(0, result['state'])
        fresh = FundingStore(self.path)
        self.assertEqual(fresh.load(), result['state'])
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.path.with_suffix('.json.lock').stat().st_mode), 0o600)
        with self.assertRaisesRegex(funding.FundingError, 'revision_conflict'):
            self.store.commit(0, result['state'])

    def test_state_and_lock_symlinks_or_nonprivate_files_are_rejected(self):
        target = Path(self.temp.name) / 'target'
        target.write_text('{}')
        self.path.symlink_to(target)
        with self.assertRaises(funding.FundingError):
            self.store.create(self.initial)
        self.path.unlink()
        lock = self.path.with_suffix('.json.lock')
        if lock.exists(): lock.unlink()
        lock.symlink_to(target)
        with self.assertRaises(funding.FundingError):
            self.store.create(self.initial)

    def test_tampered_persistent_state_is_rejected(self):
        self.store.create(self.initial)
        payload = json.loads(self.path.read_text())
        payload['state']['reserve_remaining_fen'] = 0
        self.path.write_text(json.dumps(payload))
        with self.assertRaisesRegex(funding.FundingError, 'checksum'):
            self.store.load()

    def test_pending_write_ahead_journal_is_recovered_before_any_read(self):
        self.store.create(self.initial)
        next_state = funding.recommend_topup(self.initial, broker(), '2026-10-30', ['native-entry-1'], SOURCE, NOW)['state']
        payload = json.dumps(next_state, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        record = dict(schema='weekly19.funding-store.v1', state=next_state,
                      state_sha256=hashlib.sha256(payload.encode()).hexdigest())
        journal = self.path.with_suffix('.json.journal')
        journal.write_text(json.dumps(record))
        journal.chmod(0o600)
        self.assertEqual(self.store.load(), next_state)
        self.assertFalse(journal.exists())
        self.assertEqual(FundingStore(self.path).load(), next_state)

    def test_existing_store_cannot_be_reinitialized_and_journal_cannot_jump_revision(self):
        self.store.create(self.initial)
        with self.assertRaisesRegex(funding.FundingError, 'already_exists'):
            self.store.create(self.initial)
        bad = copy.deepcopy(self.initial)
        bad['revision'] = 7
        payload = json.dumps(bad, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        journal = self.path.with_suffix('.json.journal')
        journal.write_text(json.dumps(dict(schema='weekly19.funding-store.v1', state=bad,
            state_sha256=hashlib.sha256(payload.encode()).hexdigest())))
        journal.chmod(0o600)
        with self.assertRaisesRegex(funding.FundingError, 'journal_revision'):
            self.store.load()

    def test_store_cannot_resurrect_reserve_by_committing_a_valid_older_ledger(self):
        self.store.create(self.initial)
        first = funding.recommend_topup(self.initial, broker(), '2026-10-30', ['native-entry-1'], SOURCE, NOW)['state']
        self.store.commit(0, first)
        rid = next(iter(first['requests']))
        paid = funding.confirm_topup(first, rid, receipt(rid),
            broker(deposit='30000.00', at=NOW + timedelta(minutes=2)), NOW + timedelta(minutes=2))
        self.store.commit(1, paid)
        rollback = copy.deepcopy(first)
        rollback['revision'] = 3
        with self.assertRaisesRegex(funding.FundingError, 'ledger_rollback'):
            self.store.commit(2, rollback)

    def test_file_permissions_hardlinks_and_parent_symlink_fail_closed(self):
        self.store.create(self.initial)
        self.path.chmod(0o644)
        with self.assertRaises(funding.FundingError): self.store.load()
        self.path.chmod(0o600)
        os.link(self.path, Path(self.temp.name) / 'hardlink')
        with self.assertRaises(funding.FundingError): self.store.load()
        parent_link = Path(self.temp.name) / 'parent-link'
        parent_link.symlink_to(self.temp.name, target_is_directory=True)
        with self.assertRaises(funding.FundingError):
            FundingStore(parent_link / 'other.json').create(self.initial)

    def test_cashflow_checkpoint_cannot_move_backward_in_cas_commit(self):
        self.store.create(self.initial)
        first = funding.recommend_topup(self.initial, broker(), '2026-10-30', [], SOURCE, NOW)['state']
        self.store.commit(0, first)
        bad = copy.deepcopy(first)
        bad['revision'] = 2
        bad['cashflow_checkpoint']['observed_at'] = (NOW - timedelta(seconds=1)).isoformat()
        with self.assertRaisesRegex(funding.FundingError, 'checkpoint_rollback'):
            self.store.commit(1, bad)

    def test_v2_store_one_cas_migration_keeps_legacy_paid_cash_and_rejects_downgrade(self):
        old=copy.deepcopy(LEGACY_PARTIAL_STATE)
        payload=json.dumps(old,sort_keys=True,separators=(',',':'),ensure_ascii=False)
        self.path.write_text(json.dumps(dict(schema='weekly19.funding-store.v1',state=old,
            state_sha256=hashlib.sha256(payload.encode()).hexdigest())))
        self.path.chmod(0o600)
        self.assertEqual(self.store.load(),old)
        upgraded=funding.upgrade_funding_state(old)
        self.store.commit(old['revision'],upgraded)
        self.assertEqual(self.store.load(),upgraded)
        downgrade=copy.deepcopy(old); downgrade['revision']=upgraded['revision']+1
        with self.assertRaises(funding.FundingError): self.store.commit(upgraded['revision'],downgrade)

    def test_v2_old_v1_identical_crash_journal_can_recover_before_explicit_upgrade(self):
        old=copy.deepcopy(LEGACY_PARTIAL_STATE)
        payload=json.dumps(old,sort_keys=True,separators=(',',':'),ensure_ascii=False)
        record=json.dumps(dict(schema='weekly19.funding-store.v1',state=old,
            state_sha256=hashlib.sha256(payload.encode()).hexdigest()))
        self.path.write_text(record); self.path.chmod(0o600)
        journal=self.path.with_suffix('.json.journal'); journal.write_text(record); journal.chmod(0o600)
        self.assertEqual(self.store.load(),old)
        self.assertFalse(journal.exists())

    def test_v2_store_cannot_delete_retirement_to_resurrect_old_offer(self):
        self.store.create(self.initial)
        first=funding.recommend_topup(self.initial,broker(),'2026-10-30',['native-entry-1'],SOURCE,NOW)['state']
        self.store.commit(0,first); rid=next(iter(first['requests']))
        retired=funding.retire_topup_request(first,rid,broker(balance='150000.00'),NOW,reason='equity_recovered')
        self.store.commit(1,retired)
        bad=copy.deepcopy(retired); bad['revision']=3; bad['retirements']={}; bad['requests'][rid]['status']='pending'
        with self.assertRaisesRegex(funding.FundingError,'retirement_ledger'):
            self.store.commit(2,bad)

    def test_io_v3_lock_creation_avoids_macos_nonexclusive_creat_enoent(self):
        native_open=os.open
        def macos_open(path,flags,*args,**kwargs):
            if path==self.path.name+'.lock' and flags&os.O_CREAT and not flags&os.O_EXCL:
                raise FileNotFoundError('macOS openat cold-create race')
            return native_open(path,flags,*args,**kwargs)
        with mock.patch('qmt_roll_weekly19_funding_store.os.open',side_effect=macos_open):
            self.store.create(self.initial)
            self.assertEqual(self.store.load(),self.initial)
        self.assertEqual(stat.S_IMODE(self.path.with_suffix('.json.lock').stat().st_mode),0o600)

    def test_io_v3_lock_removed_between_exclusive_create_and_open_is_bounded_retried(self):
        native_open=os.open; phase=[0]
        def removed_race(path,flags,*args,**kwargs):
            if path==self.path.name+'.lock' and phase[0]<2:
                phase[0]+=1
                if flags&os.O_EXCL: raise FileExistsError('competing first create')
                raise FileNotFoundError('removed before open-existing')
            return native_open(path,flags,*args,**kwargs)
        with mock.patch('qmt_roll_weekly19_funding_store.os.open',side_effect=removed_race):
            self.store.create(self.initial)
            self.assertEqual(self.store.load(),self.initial)

    def test_io_v3_continuously_removed_lock_fails_closed_after_bounded_retry(self):
        native_open=os.open
        def endless_race(path,flags,*args,**kwargs):
            if path==self.path.name+'.lock':
                if flags&os.O_EXCL: raise FileExistsError('competing first create')
                raise FileNotFoundError('removed before open-existing')
            return native_open(path,flags,*args,**kwargs)
        with mock.patch('qmt_roll_weekly19_funding_store.os.open',side_effect=endless_race):
            with self.assertRaisesRegex(funding.FundingError,'lock_create_race_exhausted'):
                self.store.create(self.initial)
        self.assertFalse(self.path.exists())

    def test_io_v3_real_cold_concurrent_first_creation_preserves_one_initial_ledger(self):
        context=multiprocessing.get_context('fork')
        for iteration in range(8):
            path=Path(self.temp.name)/('cold-'+str(iteration)+'.json')
            barrier=context.Barrier(8); queue=context.Queue()
            workers=[context.Process(target=_cold_store_worker,args=(str(path),barrier,queue,self.initial)) for _ in range(8)]
            for worker in workers: worker.start()
            results=[queue.get(timeout=15) for _ in workers]
            for worker in workers:
                worker.join(timeout=15)
                self.assertEqual(worker.exitcode,0)
            queue.close(); queue.join_thread()
            with self.subTest(iteration=iteration,results=results):
                self.assertEqual(results.count('created'),1)
                self.assertEqual(results.count('already_exists'),7)
                self.assertEqual(FundingStore(path).load(),self.initial)


if __name__ == '__main__':
    unittest.main()
