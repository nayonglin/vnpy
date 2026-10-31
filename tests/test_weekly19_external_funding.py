"""Literal account/cash-flow fixtures exercise the offline funding safety boundary.

They are deliberately not production qualification evidence.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
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


if __name__ == '__main__':
    unittest.main()
