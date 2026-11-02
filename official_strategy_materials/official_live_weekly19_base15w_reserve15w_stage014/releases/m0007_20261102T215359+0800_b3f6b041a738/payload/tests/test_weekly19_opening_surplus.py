"""Synthetic startup equity facts, never strategy profit or real source admission."""
import copy
import hashlib
import inspect
import json
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT/'tests')]
import qmt_roll_weekly19_funding as funds
from qmt_roll_weekly19_funding_store import FundingStore
from test_weekly19_external_funding import ACCOUNT,RELEASE,SOURCE,NOW,broker,envelope,receipt,day_close
MODE='operator_existing_account_v1';DECISION='c'*64

def initial():return funds.initial_state(ACCOUNT,RELEASE,'2026-10-30')
def account(balance='172345.67',deposit='150000.00',at=NOW,day='2026-10-30',**kw):
 return broker(balance=balance,deposit=deposit,at=at,day=day,Available='100000.00',query_last_seen=True,query_error_rows=0,**kw)
def observed(balance='172345.67'):
 return funds.begin_cash_observation(initial(),account(balance),NOW,opening_equity_mode=MODE,operator_decision_id=DECISION)

class ExactOpeningCompatibilityTests(unittest.TestCase):
 def test_default_exact_fixture_retains_original_state_canonical_bytes(self):
  result=funds.begin_cash_observation(initial(),account('150000.00'),NOW)
  self.assertNotIn('opening_equity',result)
  self.assertEqual(hashlib.sha256(funds._canonical(result)).hexdigest(),'778f9e43850d0633173780bd70303cf8391ed83c95745cb4a5ad8984c5d48193')
  for balance in ('149999.99','150000.01'):
   with self.assertRaises(funds.FundingError):funds.begin_cash_observation(initial(),account(balance),NOW)

class OpeningSurplusTests(unittest.TestCase):
 def setUp(self):self.assertIn('opening_equity_mode',inspect.signature(funds.begin_cash_observation).parameters,'explicit opening-equity API missing')
 def test_positive_real_equity_is_only_designated_prestart_surplus(self):
  state=initial();evidence=account();before=copy.deepcopy((state,evidence))
  result=funds.begin_cash_observation(state,evidence,NOW,opening_equity_mode=MODE,operator_decision_id=DECISION)
  self.assertEqual((state,evidence),before);self.assertEqual(result['revision'],1)
  o=result['opening_equity'];self.assertEqual(o['schema'],'weekly19.opening-equity.v1');self.assertEqual(o['mode'],MODE)
  self.assertEqual(o['source_kind'],'operator_manual');self.assertEqual(o['classification'],'operator_designated_pre_start_surplus');self.assertFalse(o['verified_strategy_pnl'])
  self.assertEqual((o['baseline_trading_fen'],o['observed_equity_fen'],o['opening_surplus_fen']),(15000000,17234567,2234567))
  self.assertEqual(o['operator_decision_id'],DECISION);self.assertEqual(o['broker_account'],evidence);self.assertEqual(o['baseline_checkpoint'],result['cashflow_checkpoint'])
  self.assertEqual(result['reserve_remaining_fen'],15000000);self.assertEqual(result['confirmed_topup_fen'],0)
  for key in ('requests','receipts','admitted_entries','request_attempts'):self.assertEqual(result[key],{})
  self.assertFalse(result['production_qualified']);self.assertNotIn('source_qualified',o)
 def test_positive_equity_below_base_retains_negative_signed_delta_and_zero_is_rejected(self):
  for balance,delta in [('150000.00',0),('120000.00',-3000000),('0.01',-14999999),('92233720368547758.07',9223372036854775807-15000000)]:
   with self.subTest(balance=balance):
    result=observed(balance);self.assertEqual(result['opening_equity']['opening_surplus_fen'],delta);self.assertEqual(result['initial_trading_fen'],15000000)
  for balance in ('0.00','-0.01','92233720368547758.08'):
   with self.subTest(balance=balance),self.assertRaises(funds.FundingError):observed(balance)
 def test_explicit_mode_and_decision_are_required_not_silent_flags(self):
  for mode,decision in [(MODE,None),(MODE,'not-sha'),(MODE,True),('unknown',DECISION),([],DECISION),('exact_150k',DECISION)]:
   with self.subTest(mode=mode,decision=decision),self.assertRaises(funds.FundingError):
    funds.begin_cash_observation(initial(),account(),NOW,opening_equity_mode=mode,operator_decision_id=decision)
 def test_original_snapshot_identity_integrity_freshness_and_complete_query_gates_remain(self):
  raw=json.loads(account()['raw_payload'])
  cases=[dict(raw,Available='-0.01'),dict(raw,query_last_seen=False),dict(raw,query_error_rows=1),dict(raw,query_complete=False),dict(raw,AccountID='foreign'),dict(raw,material_release_id='foreign'),dict(raw,observed_at=(NOW+timedelta(seconds=1)).isoformat())]
  for changed in cases:
   with self.subTest(changed=changed),self.assertRaises(funds.FundingError):
    funds.begin_cash_observation(initial(),envelope(changed),NOW,opening_equity_mode=MODE,operator_decision_id=DECISION)
  with self.assertRaises(funds.FundingError):funds.begin_cash_observation(initial(),account(),NOW+timedelta(seconds=301),opening_equity_mode=MODE,operator_decision_id=DECISION)
  with self.assertRaises(funds.FundingError):funds.begin_cash_observation(initial(),dict(account(),raw_sha256='0'*64),NOW,opening_equity_mode=MODE,operator_decision_id=DECISION)
 def test_replay_is_byte_idempotent_but_policy_decision_and_source_cannot_reset(self):
  result=observed();again=funds.begin_cash_observation(result,account(),NOW,opening_equity_mode=MODE,operator_decision_id=DECISION)
  self.assertEqual(funds._canonical(result),funds._canonical(again));self.assertIsNot(result,again)
  for mode,decision,evidence in [('exact_150k',None,account()),(MODE,'d'*64,account()),(MODE,DECISION,account(at=NOW+timedelta(seconds=1)))]:
   with self.subTest(mode=mode),self.assertRaises(funds.FundingError):
    funds.begin_cash_observation(result,evidence,NOW+timedelta(seconds=1),opening_equity_mode=mode,operator_decision_id=decision)
 def test_cannot_attach_operator_policy_to_already_observed_exact_account_or_activity(self):
  exact=funds.begin_cash_observation(initial(),account('150000.00'),NOW)
  with self.assertRaises(funds.FundingError):funds.begin_cash_observation(exact,account('150000.00'),NOW,opening_equity_mode=MODE,operator_decision_id=DECISION)
  prepared=funds.recommend_topup(initial(),account('120000.00'),'2026-10-30',['native'],SOURCE,NOW)['state']
  with self.assertRaises(funds.FundingError):funds.begin_cash_observation(prepared,account(),NOW,opening_equity_mode=MODE,operator_decision_id=DECISION)
 def test_initial_gross_deposit_is_not_a_topup_and_new_unknown_cash_still_blocks(self):
  result=observed();funds.assert_open_funding_ready(result,account(),NOW)
  self.assertEqual(result['cashflow_checkpoint']['deposit_fen'],15000000)
  with self.assertRaisesRegex(funds.FundingError,'unreconciled_cashflow_deposit'):
   funds.assert_open_funding_ready(result,account(deposit='150000.01',at=NOW+timedelta(seconds=1)),NOW+timedelta(seconds=1))
 def test_future_offer_still_targets_original_150k_floor_not_opening_equity(self):
  result=observed();at=NOW+timedelta(seconds=1);low=account('120000.00',at=at)
  proposed=funds.recommend_topup(result,low,'2026-10-30',['native'],SOURCE,at)
  self.assertEqual(proposed['recommendation']['amount_fen'],3000000);self.assertEqual(proposed['state']['opening_equity'],result['opening_equity'])
  self.assertEqual(proposed['state']['confirmed_topup_fen'],0)
 def test_cannot_consume_initial_deposit_again_but_true_new_receipt_preserves_opening(self):
  result=observed();at=NOW+timedelta(seconds=1)
  request=funds.recommend_topup(result,account('120000.00',at=at),'2026-10-30',['native'],SOURCE,at)
  state=request['state'];rid=request['recommendation']['request_id'];at=NOW+timedelta(minutes=1)
  proof=receipt(rid,at=at)
  with self.assertRaises(funds.FundingError):funds.confirm_topup(state,rid,proof,account('150000.00',at=at),at)
  updated=funds.confirm_topup(state,rid,proof,account('150000.00',deposit='180000.00',at=at),at)
  self.assertEqual((updated['confirmed_topup_fen'],updated['reserve_remaining_fen']),(3000000,12000000));self.assertEqual(updated['opening_equity'],result['opening_equity'])
  self.assertEqual(funds.confirm_topup(updated,rid,proof,account('150000.00',deposit='180000.00',at=at),at),updated)
 def test_persisted_opening_fields_and_raw_bridge_are_strictly_revalidated(self):
  result=observed()
  changes=[('observed_equity_fen',True),('observed_equity_fen',17234568),('opening_surplus_fen',2234568),('opening_surplus_fen',True),('baseline_trading_fen',15000001),('verified_strategy_pnl',True),('source_kind','broker_cashflow_receipt'),('classification','strategy_profit'),('operator_decision_id','bad'),('mode','exact_150k'),('accepted_at',(NOW+timedelta(seconds=301)).isoformat())]
  for key,value in changes:
   broken=copy.deepcopy(result);broken['opening_equity'][key]=value
   with self.subTest(key=key),self.assertRaises(funds.FundingError):funds.validate_state(broken)
  for mutate in ('missing','extra','checkpoint','raw','foreign_account','foreign_release'):
   broken=copy.deepcopy(result);o=broken['opening_equity']
   if mutate=='missing':o.pop('operator_decision_id')
   if mutate=='extra':o['source_qualified']=True
   if mutate=='checkpoint':o['baseline_checkpoint']['deposit_fen']=0
   if mutate=='raw':o['broker_account']['raw_sha256']='0'*64
   if mutate=='foreign_account':broken['account_key']='e'*64
   if mutate=='foreign_release':broken['material_release_id']='foreign'
   with self.subTest(mutate=mutate),self.assertRaises(funds.FundingError):funds.validate_state(broken)
 def test_current_checkpoint_cannot_precede_or_lose_the_opening_bridge(self):
  for mutate in ('missing','before_time','before_day','lower_deposit','unproven_day'):
   broken=observed();cp=broken['cashflow_checkpoint']
   if mutate=='missing':broken['cashflow_checkpoint']=None
   if mutate=='before_time':cp['observed_at']=(NOW-timedelta(seconds=1)).isoformat()
   if mutate=='before_day':cp['trading_day']='2026-10-29'
   if mutate=='lower_deposit':cp['deposit_fen']=0
   if mutate=='unproven_day':cp['trading_day']='2026-11-02'
   with self.subTest(mutate=mutate),self.assertRaises(funds.FundingError):funds.validate_state(broken)
 def test_normal_proven_day_roll_retains_opening_without_claiming_new_profit(self):
  result=observed();closing=account(at=NOW+timedelta(minutes=1));monday=NOW+timedelta(days=3)
  following=account(deposit='0.00',at=monday,day='2026-11-02')
  proof=day_close(closing,at=NOW+timedelta(minutes=2))
  updated=funds.reconcile_trading_day(result,closing,following,monday,continuity_receipt=proof)
  self.assertEqual(updated['opening_equity'],result['opening_equity']);funds.validate_state(updated)
  self.assertEqual((updated['confirmed_topup_fen'],updated['reserve_remaining_fen']),(0,15000000))
 def test_manual_day_review_with_real_topup_remains_compatible(self):
  from test_weekly19_manual_cash import review,close,topup
  result=observed();state=funds.recommend_topup(result,account('120000.00'),'2026-10-30',['native'],SOURCE,NOW)['state'];rid=next(iter(state['requests']))
  monday=NOW.replace(month=11,day=2,hour=9,minute=1);current=account('150000.00',deposit='30000.00',at=monday,day='2026-11-02')
  record=review(state,current,closed=[close(dep=15000000)],topups=[topup(rid,at=monday-timedelta(seconds=1),day='2026-11-02')])
  updated=funds.apply_operator_cash_review(state,record,current,monday,trading_calendar=['2026-10-30','2026-11-02'])
  self.assertEqual(updated['opening_equity'],result['opening_equity']);self.assertEqual(updated['confirmed_topup_fen'],3000000);funds.validate_state(updated)

class OpeningSurplusStoreTests(unittest.TestCase):
 def setUp(self):
  self.assertIn('opening_equity_mode',inspect.signature(funds.begin_cash_observation).parameters,'explicit opening-equity API missing')
  self.tmp=tempfile.TemporaryDirectory(dir='/private/tmp');self.addCleanup(self.tmp.cleanup)
  self.store=FundingStore(Path(self.tmp.name)/'cash.json');self.store.create(initial())
 def test_first_observation_is_one_cas_then_restart_replay_is_identical(self):
  result=observed();self.store.commit(0,result);loaded=self.store.load();self.assertEqual(loaded,result)
  self.store.commit(1,funds.begin_cash_observation(loaded,account(),NOW,opening_equity_mode=MODE,operator_decision_id=DECISION));self.assertEqual(self.store.load(),result)
 def test_self_consistent_replacement_baseline_is_valid_alone_but_rejected_by_cas(self):
  result=observed();self.store.commit(0,result)
  replacement=observed('175000.00');replacement['revision']=2;funds.validate_state(replacement)
  with self.assertRaisesRegex(funds.FundingError,'opening_equity'):self.store.commit(1,replacement)
  self.assertEqual(self.store.load(),result)
 def test_drop_or_change_policy_is_rejected_even_when_other_state_ledgers_remain_valid(self):
  result=observed();self.store.commit(0,result)
  for mutation in ('drop','decision'):
   replacement=copy.deepcopy(result);replacement['revision']=2
   if mutation=='drop':replacement.pop('opening_equity')
   else:replacement['opening_equity']['operator_decision_id']='d'*64
   funds.validate_state(replacement)
   with self.subTest(mutation=mutation),self.assertRaisesRegex(funds.FundingError,'opening_equity'):self.store.commit(1,replacement)
  self.assertEqual(self.store.load(),result)
 def test_recovery_cannot_replay_a_valid_checksumming_journal_with_another_baseline(self):
  result=observed();self.store.commit(0,result);replacement=observed('175000.00');replacement['revision']=2
  journal=self.store.path.with_name(self.store.journal_name);journal.write_bytes(self.store._record(replacement));journal.chmod(0o600)
  with self.assertRaisesRegex(funds.FundingError,'opening_equity'):self.store.load()
  journal.unlink();self.assertEqual(self.store.load(),result)
 def test_cannot_add_policy_after_exact_baseline_was_already_committed(self):
  exact=funds.begin_cash_observation(initial(),account('150000.00'),NOW);self.store.commit(0,exact)
  replacement=observed('150000.00');replacement['revision']=2;funds.validate_state(replacement)
  with self.assertRaisesRegex(funds.FundingError,'opening_equity'):self.store.commit(1,replacement)
 def test_shared_forward_guard_rejects_opening_combined_with_other_fund_activity(self):
  result=observed();at=NOW+timedelta(seconds=1)
  more=funds.recommend_topup(result,account('120000.00',at=at),'2026-10-30',['native'],SOURCE,at)['state']
  with self.assertRaisesRegex(funds.FundingError,'opening_equity'):funds.assert_opening_equity_forward(initial(),more)
