"""Synthetic notification transaction boundaries; no historical financial replay."""
from pathlib import Path
from copy import deepcopy
import sys,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4];sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT/'tests')]
import qmt_roll_weekly19_live_pipeline as pipeline
import qmt_roll_weekly19_runtime as runtime
import test_weekly19_daily_mail_pipeline as fixtures
class ReportTransaction(unittest.TestCase):
 def setUp(self):
  self.fixture=fixtures.DailyMailIntegrationTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown);self.fixture.monday(preview=False);self.context=self.fixture.context;self.backend=self.fixture.backend;self.store=pipeline.pipeline_store(self.context)
 def assert_original(self,now,before):
  self.assertEqual(now['decision'],before['decision']);self.assertEqual(now['decision_state'],before['decision_state'])
 def test_new_actual_account_runtime_is_committed_before_injected_delivery_without_strategy_replay(self):
  before=self.store.read();self.backend.balance='151000.00';seen=[]
  def sender(report):
   current=self.store.read();self.assert_original(current,before);self.assertNotEqual(current['runtime']['state_sha256'],before['runtime']['state_sha256']);seen.append(report['schema']);return {'email_status':'sent'}
  self.backend.send_mail=sender
  with patch.object(runtime.Runtime,'process_completed_day',side_effect=AssertionError('report attempted strategy replay')):
   result=pipeline.run_weekly19_support_job('postclose-report',context=self.context)
  self.assertEqual(seen,['weekly19.daily-risk-report.v1']);self.assertEqual(result['daily_mail']['delivery']['status'],'sent');self.assert_original(self.store.read(),before);self.assertEqual(self.backend.publishes,0)
 def test_unknown_delivery_is_visible_but_committed_state_and_original_decision_survive(self):
  before=self.store.read();self.backend.balance='151000.00';calls=[]
  def unknown(_):calls.append(1);return {'email_status':'delivery_unknown'}
  self.backend.send_mail=unknown
  for _ in range(2):
   with self.assertRaisesRegex(ValueError,'daily_mail_delivery_delivery_unknown'):
    pipeline.run_weekly19_support_job('postclose-report',context=self.context)
  current=self.store.read();self.assert_original(current,before);self.assertNotEqual(current['runtime']['state_sha256'],before['runtime']['state_sha256']);self.assertEqual(calls,[1]);self.assertEqual(self.backend.publishes,0)
 def test_receipt_drift_does_not_send_or_rewrite_origin(self):
  before=self.store.read();old=self.backend.load_inputs;calls=[]
  def changed(target,now):
   data=old(target,now);data['receipt']=dict(data['receipt'],independent_source_drift='not_original_receipt');return data
  self.backend.load_inputs=changed;self.backend.send_mail=lambda _:calls.append(1)
  with self.assertRaisesRegex(ValueError,'original_data_receipt_mismatch'):
   pipeline.run_weekly19_support_job('postclose-report',context=self.context)
  self.assertEqual(calls,[]);self.assert_original(self.store.read(),before);self.assertEqual(self.backend.publishes,0)
if __name__=='__main__':unittest.main()
