"""Weekly receipt binds fixed-data and original decision after later fills."""
import copy,os,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT/'tests')]
from test_weekly19_live_pipeline import FixtureBackend,ACCOUNT,RELEASE,NOW
from qmt_roll_weekly19_live_pipeline import run_weekly19_support_job,pipeline_store
from qmt_roll_weekly19_daily_receipt import build_weekly19_daily_receipt,write_weekly19_daily_receipt,Weekly19DailyReceiptError
from qmt_roll_weekly19_pipeline_state import digest
class ReceiptTest(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(dir='/private/tmp');self.parent=Path(self.t.name).resolve();self.parent.chmod(0o700);self.backend=FixtureBackend()
  self.c=dict(backend=self.backend,state_path=self.parent/'state.json',mail_outbox=self.parent,account_key=ACCOUNT,material_release_id=RELEASE,cold_start_date='2026-10-30',target_date='2026-10-30',now=NOW,preview=True)
  run_weekly19_support_job('postclose-precompute',context=self.c);self.bundle=pipeline_store(self.c).read();self.data=self.backend.load_inputs('2026-10-30',NOW)
 def tearDown(self):self.t.cleanup()
 def build(self,**changes):
  kw=dict(bundle=self.bundle,data=self.data,source_commit='a'*40,manifest_sha256='b'*64,generated_at=NOW);kw.update(changes);return build_weekly19_daily_receipt(**kw)
 def test_identity_and_following_session_no_ai_csv(self):
  r=self.build();self.assertEqual(r['data_inventory']['semantic_freshness']['next_trading_session_date'],'2026-11-02')
  self.assertEqual(r['decision_sha256'],digest(self.bundle['decision']));self.assertNotIn('signal_bundle',r);self.assertFalse(r['production_qualified'])
 def test_current_equity_change_does_not_rewrite_decision_receipt(self):
  old=self.build();self.backend.balance='130000.00';run_weekly19_support_job('postclose-precompute',context=self.c);self.bundle=pipeline_store(self.c).read()
  self.assertEqual(self.build(),old)
 def test_changed_market_receipt_refuses_old_decision(self):
  self.data['receipt']['source_sha256']='c'*64
  with self.assertRaisesRegex(Weekly19DailyReceiptError,'market_or_origin'):self.build()
 def test_missing_next_session_and_foreign_release_are_rejected(self):
  self.data['calendar']=[x for x in self.data['calendar']if x<='2026-10-30']
  with self.assertRaises(Weekly19DailyReceiptError):self.build()
  self.data=self.backend.load_inputs('2026-10-30',NOW);self.data['receipt']['material_release_id']='other'
  with self.assertRaises(Weekly19DailyReceiptError):self.build()
 def test_atomic_private_delivery_and_target_rollback_rejected(self):
  p=self.parent/'daily.json';r=self.build();write_weekly19_daily_receipt(p,r);self.assertEqual(p.stat().st_mode&0o777,0o600)
  before=p.read_bytes();r['target_cutoff_date']='2026-10-29'
  with self.assertRaises(Weekly19DailyReceiptError):write_weekly19_daily_receipt(p,r)
  self.assertEqual(before,p.read_bytes())
 def test_no_decision_never_becomes_daily_ready(self):
  self.bundle['decision']=None
  with self.assertRaises(Weekly19DailyReceiptError):self.build()
if __name__=='__main__':unittest.main()
