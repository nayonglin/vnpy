"""Durable bundle and job lifecycle regression; fixtures are never live proof."""
import copy, hashlib, json, os, sys, tempfile, unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'examples/portfolio_backtesting'))
import qmt_roll_weekly19_funding as funds
try:
 from qmt_roll_weekly19_pipeline_state import PipelineStateStore, PipelineStateError
except ModuleNotFoundError:
 PipelineStateStore=None;PipelineStateError=ValueError
sys.path.insert(0,str(ROOT/'tests'))
from test_weekly19_runtime import ACCOUNT,RELEASE,build
def bundle():
 return dict(schema='weekly19.pipeline-state.v1',revision=0,account_key=ACCOUNT,material_release_id=RELEASE,
  funding=funds.initial_state(ACCOUNT,RELEASE,'2026-10-30'),runtime=None,decision=None,decision_state=None)
class StateTest(unittest.TestCase):
 def setUp(self):
  self.assertIsNotNone(PipelineStateStore,'state implementation missing')
  self.temp=tempfile.TemporaryDirectory(dir='/private/tmp');self.parent=Path(self.temp.name).resolve();self.parent.chmod(0o700)
  self.path=self.parent/'pipeline.json';self.store=PipelineStateStore(self.path,ACCOUNT,RELEASE)
 def tearDown(self):self.temp.cleanup()
 def test_absent_load_never_initializes_and_initialization_is_once(self):
  self.assertIsNone(self.store.read());self.assertFalse(self.path.exists())
  self.store.initialize(bundle());self.assertEqual(self.store.read(),bundle())
  with self.assertRaises(PipelineStateError):self.store.initialize(bundle())
 def test_transaction_exception_preserves_all_cash_runtime_and_decision(self):
  self.store.initialize(bundle());old=self.path.read_bytes()
  def bad(b):b['funding']['reserve_remaining_fen']=0;raise RuntimeError('injected')
  with self.assertRaises(RuntimeError):self.store.transact(bad)
  self.assertEqual(old,self.path.read_bytes())
 def test_one_bundle_commit_publishes_cash_runtime_and_decision_together(self):
  self.store.initialize(bundle())
  def change(b):b['runtime']=build()[0].export_state();b['diagnostics']={'fixture':1};return b
  out=self.store.transact(change);self.assertEqual(out['revision'],1)
  self.assertEqual(self.store.read()['diagnostics'],{'fixture':1});self.assertEqual(self.path.stat().st_mode&0o777,0o600)
 def test_concurrent_transactions_are_serial_and_never_lose_revision(self):
  self.store.initialize(bundle())
  def worker(_):return self.store.transact(lambda b:dict(b,diagnostics={'n':b.get('diagnostics',{}).get('n',0)+1}))
  with ThreadPoolExecutor(4)as pool:list(pool.map(worker,range(12)))
  self.assertEqual(self.store.read()['revision'],12);self.assertEqual(self.store.read()['diagnostics']['n'],12)
 def test_cold_initialize_race_exactly_one_owner(self):
  def worker(_):
   try:self.store.initialize(bundle());return 'created'
   except PipelineStateError as e:return str(e)
  with ThreadPoolExecutor(4)as pool:out=list(pool.map(worker,range(4)))
  self.assertEqual(out.count('created'),1);self.assertEqual(out.count('pipeline_state_exists'),3)
 def test_symlink_and_hardlink_state_are_rejected(self):
  other=self.parent/'other';other.write_text('{}');other.chmod(0o600);self.path.symlink_to(other)
  with self.assertRaises((PipelineStateError,OSError)):self.store.read()
  self.path.unlink();os.link(other,self.path)
  with self.assertRaises((PipelineStateError,OSError)):self.store.read()
 def test_corrupted_checksum_or_duplicate_keys_are_rejected(self):
  self.store.initialize(bundle());obj=json.loads(self.path.read_text());obj['state']['revision']=99
  self.path.write_text(json.dumps(obj));self.path.chmod(0o600)
  with self.assertRaises(PipelineStateError):self.store.read()
  self.path.write_text('{"schema":1,"schema":2}')
  with self.assertRaises(PipelineStateError):self.store.read()
 def test_funding_rollback_is_rejected_before_replacing_file(self):
  self.store.initialize(bundle());old=self.path.read_bytes()
  def bad(b):b['funding']['reserve_remaining_fen']+=1;return b
  with self.assertRaises((PipelineStateError,funds.FundingError)):self.store.transact(bad)
  self.assertEqual(old,self.path.read_bytes())
 def test_preview_or_missing_legacy_mode_cannot_be_promoted_in_place(self):
  self.store.initialize(bundle())
  with self.assertRaisesRegex(PipelineStateError,'mode_immutable'):self.store.transact(lambda b:dict(b,runtime_mode='production'))
 def test_oversized_next_bundle_never_replaces_readable_current_file(self):
  self.store.initialize(bundle());before=self.path.read_bytes()
  with patch('qmt_roll_weekly19_pipeline_state.MAX_STATE_BYTES',6000):
   with self.assertRaisesRegex(PipelineStateError,'oversized'):self.store.transact(lambda b:dict(b,diagnostics={'oversized':'x'*8000}))
  self.assertEqual(self.path.read_bytes(),before);self.assertEqual(self.store.read(),bundle())
 def test_cross_release_or_account_cannot_resume(self):
  self.store.initialize(bundle())
  with self.assertRaises(PipelineStateError):PipelineStateStore(self.path,ACCOUNT,'foreign').read()
 def test_runtime_state_cannot_bind_other_cash_identity(self):
  self.store.initialize(bundle())
  with self.assertRaises(PipelineStateError):self.store.transact(lambda b:dict(b,runtime={'account_key':ACCOUNT,'material_release_id':'foreign'}))
if __name__=='__main__':unittest.main()
