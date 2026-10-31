"""Independent historical-vs-CAS manual ledger checks; synthetic tagged states."""
from pathlib import Path
import copy,json,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[4];sys.path[:0]=[str(ROOT),str(ROOT/'tests'),str(ROOT/'examples/portfolio_backtesting')]
from vnpy.trader.setting import SETTINGS
SETTINGS['log.file']=False;SETTINGS['log.console']=False
import tests.test_weekly19_manual_cash as f
import qmt_roll_weekly19_funding as funds
import qmt_roll_weekly19_runtime as runtime
from qmt_roll_weekly19_funding_store import FundingStore
from qmt_roll_weekly19_pipeline_state import PipelineStateStore
class StrictParentIndependent(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir='/private/tmp');self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve();self.root.chmod(0o700)
  self.start,self.rid=f.initial();at=f.NOW+f.timedelta(minutes=1);one=f.account(balance='130000.00',deposit='10000.00',at=at)
  self.partial=funds.apply_operator_cash_review(self.start,f.review(self.start,one,topups=[f.topup(self.rid,1000000)]),one,at,trading_calendar=f.CALENDAR)
  later=at+f.timedelta(minutes=1);two=f.account(balance='150000.00',deposit='30000.00',at=later)
  self.full=funds.apply_operator_cash_review(self.partial,f.review(self.partial,two,rid='second',topups=[f.topup(self.rid,2000000,'second-transfer',later-f.timedelta(seconds=1))]),two,later,trading_calendar=f.CALENDAR)
 def bundle(self,cash):return dict(schema='weekly19.pipeline-state.v1',revision=0,account_key=f.ACCOUNT,material_release_id=f.RELEASE,funding=copy.deepcopy(cash),runtime=None,decision=None,decision_state=None)
 def corrupt_parent(self):
  bad=copy.deepcopy(self.partial);item=bad['manual_cash_reviews']['review-1'];raw=json.loads(item['raw_payload']);raw['before_funding_sha256']='0'*64;item.update(f.envelope(raw));bad['receipts']['manual-bank-reference-1']['raw_sha256']=item['raw_sha256'];funds.validate_state(bad);return bad
 def test_two_real_separate_funding_commits_remain_valid(self):
  store=FundingStore(self.root/'cash.json');store.create(funds.initial_state(f.ACCOUNT,f.RELEASE,'2026-10-30'));store.commit(0,self.start);store.commit(self.start['revision'],self.partial);store.commit(self.partial['revision'],self.full)
  self.assertEqual(store.load(),self.full);FundingStore._forward_ledger(self.start,self.full)
 def test_actual_pipeline_cas_cannot_adopt_two_reviews_even_with_false_json_flag(self):
  store=PipelineStateStore(self.root/'pipeline.json',f.ACCOUNT,f.RELEASE);store.initialize(self.bundle(self.start));before=store.path.read_bytes()
  with self.assertRaisesRegex(ValueError,'one_manual_review_per_commit'):store.transact(lambda b:dict(b,funding=self.full,strict_manual_parent=False))
  self.assertEqual(store.path.read_bytes(),before)
 def test_actual_pipeline_cas_keeps_parent_hash_gate(self):
  store=PipelineStateStore(self.root/'pipeline.json',f.ACCOUNT,f.RELEASE);store.initialize(self.bundle(self.start));before=store.path.read_bytes();bad=self.corrupt_parent()
  with self.assertRaisesRegex(ValueError,'parent_mismatch'):store.transact(lambda b:dict(b,funding=bad,strict_manual_parent=False))
  self.assertEqual(store.path.read_bytes(),before)
 def test_funding_journal_recovery_cannot_relax_parent_binding(self):
  store=FundingStore(self.root/'cash.json');store.create(funds.initial_state(f.ACCOUNT,f.RELEASE,'2026-10-30'));store.commit(0,self.start);before=store.path.read_bytes();journal=self.root/store.journal_name;journal.write_bytes(store._record(self.corrupt_parent()));journal.chmod(0o600)
  with self.assertRaisesRegex(ValueError,'parent_mismatch'):store.load()
  self.assertEqual(store.path.read_bytes(),before);self.assertTrue(journal.exists())
 def test_real_pipeline_origin_validator_accepts_two_prior_commits_without_changing_origin(self):
  decision=dict(schema='weekly19.runtime-decision.v1',trading_date='2026-10-30',account_fingerprint=f.ACCOUNT,material_release_id=f.RELEASE,confirmed_cash_state=copy.deepcopy(self.start),data_receipt_sha256='a'*64,after_state_sha256='')
  def snapshot(cash,revision):
   body=dict(schema='weekly19.runtime-state.v1',account_key=f.ACCOUNT,material_release_id=f.RELEASE,revision=revision,position_identities={},production_qualified=False,runtime=runtime._encode(dict(confirmed_cash_state=copy.deepcopy(cash),revision=revision,position_identities={},current_receipt_hash='a'*64,days={'2026-10-30':{'decision':copy.deepcopy(decision)}})))
   return dict(body,state_sha256=runtime._state_digest(body))
  origin=snapshot(self.start,0);decision['after_state_sha256']=origin['state_sha256'];origin=snapshot(self.start,0);self.assertEqual(origin['state_sha256'],decision['after_state_sha256'])
  value=self.bundle(self.full);value.update(runtime=snapshot(self.full,2),decision=decision,decision_state=origin)
  store=PipelineStateStore(self.root/'origin.json',f.ACCOUNT,f.RELEASE);store.initialize(value);self.assertEqual(store.read()['decision_state'],origin)
  out=store.transact(lambda b:dict(b,diagnostic='history accepted'));self.assertEqual(out['decision_state'],origin)
if __name__=='__main__':unittest.main(defaultTest='StrictParentIndependent')
