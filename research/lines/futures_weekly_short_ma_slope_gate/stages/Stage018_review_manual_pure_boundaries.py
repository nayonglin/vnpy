"""Independent pure manual funding cases; no live backend or native sources."""
from pathlib import Path
import copy,importlib.util,json,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[4];sys.path[:0]=[str(ROOT),str(ROOT/'tests'),str(ROOT/'examples/portfolio_backtesting')]
import tests.test_weekly19_manual_cash as fixture
import qmt_roll_weekly19_funding as funds
from qmt_roll_weekly19_funding_store import FundingStore
class ManualPureIndependent(unittest.TestCase):
 def scenario(self,amount=3000000):
  state,rid=fixture.initial();at=fixture.NOW+fixture.timedelta(minutes=1);current=fixture.account(balance='150000.00',deposit=str(amount/100),at=at)
  record=fixture.review(state,current,topups=[fixture.topup(rid,amount)])
  updated=funds.apply_operator_cash_review(state,record,current,at,trading_calendar=fixture.CALENDAR)
  return state,rid,at,current,record,updated
 def test_receipt_id_is_unique_across_different_review_ids(self):
  state,rid,at,current,record,partial=self.scenario(1000000);later=at+fixture.timedelta(minutes=1);two=fixture.account(deposit='20000.00',at=later)
  replay=fixture.review(partial,two,rid='independent-review-2',topups=[fixture.topup(rid,1000000,at=later-fixture.timedelta(seconds=1))]);before=copy.deepcopy(partial)
  with self.assertRaises(ValueError):funds.apply_operator_cash_review(partial,replay,two,later,trading_calendar=fixture.CALENDAR)
  self.assertEqual(before,partial)
 def test_old_applied_review_does_not_reconcile_new_cash_or_new_day(self):
  state,rid,at,current,record,updated=self.scenario();later=at+fixture.timedelta(hours=1)
  unchanged=fixture.account(balance='160000.00',deposit='30000.00',at=later,generation_uuid='new-real-generation')
  same=funds.apply_operator_cash_review(updated,record,unchanged,later,trading_calendar=fixture.CALENDAR);self.assertEqual(same,updated);funds.assert_open_funding_ready(same,unchanged,later)
  for unknown in [fixture.account(deposit='30001.00',at=later),fixture.account(deposit='0.00',day='2026-11-02',at=later)]:
   with self.subTest(unknown=unknown['raw_sha256']):
    replay=funds.apply_operator_cash_review(updated,record,unknown,later,trading_calendar=fixture.CALENDAR)
    with self.assertRaises(ValueError):funds.assert_open_funding_ready(replay,unknown,later)
    self.assertEqual(replay['confirmed_topup_fen'],3000000)
 def test_profit_equity_is_not_manual_topup_or_a_forced_old_debt(self):
  state,rid=fixture.initial();at=fixture.NOW+fixture.timedelta(minutes=1);current=fixture.account(balance='160000.00',at=at);before=copy.deepcopy(current)
  updated=funds.apply_operator_cash_review(state,fixture.review(state,current),current,at,trading_calendar=fixture.CALENDAR)
  self.assertEqual(updated['confirmed_topup_fen'],0);self.assertEqual(updated['reserve_remaining_fen'],15000000);self.assertEqual(current,before);funds.assert_open_funding_ready(updated,current,at)
 def test_failed_gross_reconciliation_never_partially_changes_input(self):
  state,rid=fixture.initial();at=fixture.NOW+fixture.timedelta(minutes=1);current=fixture.account(deposit='40000.00',at=at);record=fixture.review(state,current,topups=[fixture.topup(rid)]);before=copy.deepcopy((state,current,record))
  with self.assertRaises(ValueError):funds.apply_operator_cash_review(state,record,current,at,trading_calendar=fixture.CALENDAR)
  self.assertEqual((state,current,record),before)
 def test_manual_schema_cannot_create_auto_receipt_or_qualification(self):
  state,rid,at,current,record,updated=self.scenario()
  with self.assertRaises(ValueError):funds.confirm_topup(state,record,current,at)
  for key in ('production_qualified','source_qualified','broker_automatically_verified'):
   raw=json.loads(record['raw_payload']);raw[key]=True
   with self.subTest(key=key),self.assertRaises(ValueError):funds.apply_operator_cash_review(state,fixture.envelope(raw),current,at,trading_calendar=fixture.CALENDAR)
 def test_missing_intermediate_closed_day_rejected_with_authoritative_calendar(self):
  state,rid=fixture.initial();at=fixture.NOW.replace(month=11,day=3,hour=9,minute=1);current=fixture.account(day='2026-11-03',at=at);record=fixture.review(state,current,closed=[fixture.close()]);before=copy.deepcopy(state)
  with self.assertRaisesRegex(ValueError,'closed_trading_days_incomplete'):funds.apply_operator_cash_review(state,record,current,at,trading_calendar=fixture.CALENDAR)
  self.assertEqual(state,before)
 def test_cash_review_parent_hash_rewrite_rejected_by_store(self):
  state,rid,at,current,record,updated=self.scenario();bad=copy.deepcopy(updated);item=bad['manual_cash_reviews']['review-1'];raw=json.loads(item['raw_payload']);raw['before_funding_sha256']='0'*64;item.update(fixture.envelope(raw));bad['receipts']['manual-bank-reference-1']['raw_sha256']=item['raw_sha256']
  with tempfile.TemporaryDirectory(dir='/private/tmp')as temp:
   root=Path(temp).resolve();root.chmod(0o700);store=FundingStore(root/'cash.json');store.create(funds.initial_state(fixture.ACCOUNT,fixture.RELEASE,'2026-10-30'));store.commit(0,state)
   with self.assertRaisesRegex(ValueError,'parent_mismatch'):store.commit(state['revision'],bad)
   self.assertEqual(store.load(),state)
 def test_even_empty_manual_fact_is_append_only_in_forward_store(self):
  state,rid=fixture.initial();at=fixture.NOW+fixture.timedelta(minutes=1);current=fixture.account(balance='150000.00',at=at);updated=funds.apply_operator_cash_review(state,fixture.review(state,current),current,at,trading_calendar=fixture.CALENDAR)
  with tempfile.TemporaryDirectory(dir='/private/tmp')as temp:
   root=Path(temp).resolve();root.chmod(0o700);store=FundingStore(root/'cash.json');store.create(funds.initial_state(fixture.ACCOUNT,fixture.RELEASE,'2026-10-30'));store.commit(0,state);store.commit(state['revision'],updated)
   bad=copy.deepcopy(updated);bad['manual_cash_reviews'].clear();bad['revision']+=1;funds.validate_state(bad)
   with self.assertRaisesRegex(ValueError,'manual_review_ledger_rollback'):store.commit(updated['revision'],bad)
   self.assertEqual(store.load(),updated)
if __name__=='__main__':unittest.main(defaultTest='ManualPureIndependent')
