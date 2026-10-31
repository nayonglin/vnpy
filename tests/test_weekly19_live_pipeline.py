"""Offline integration fixtures never authorize SMTP, CTP or production."""
import copy, os, sys, tempfile, unittest
from pathlib import Path
from datetime import timedelta
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT/'tests')]
from test_weekly19_runtime import ACCOUNT,RELEASE,NOW,fixture,broker,envelope
import json
def report_broker(**kw):
 b=broker(**kw);a=json.loads(b['account']['raw_payload']);a.update(query_last_seen=True,query_error_rows=0,CurrMargin='0.00');b['account']=envelope(a);return b
import qmt_roll_weekly19_funding as funds
try:
 import qmt_roll_weekly19_live_pipeline as pipeline
except ModuleNotFoundError:pipeline=None
class FixtureBackend:
 def __init__(self):
  self.balance='120000.00';self.calendar,self.epochs,self.bars,self.metadata=fixture();self.events=[];self.publishes=0;self.sends=0
 def require_production(self):raise ValueError('fixture_not_production')
 def load_inputs(self,target_date,now):
  return dict(metadata=self.metadata,calendar=self.calendar,physical_epoch_daily=self.epochs,
   bars_by_day=self.bars,receipt=dict(schema='weekly19.data-receipt.v1',complete=True,trading_date=target_date,material_release_id=RELEASE,source_sha256='b'*64),broker_snapshot=report_broker(balance=self.balance,available='0.00',now=now))
 def reconcile_cash(self,state,snapshot,now):return copy.deepcopy(state)
 def read_execution_events(self,decision,now):return copy.deepcopy(self.events)
 def publish_execution(self,**kw):self.publishes+=1;return {'status':'fixture'}
 def send_mail(self,report):self.sends+=1;return {'email_status':'sent'}
class PipelineTest(unittest.TestCase):
 def setUp(self):
  self.assertIsNotNone(pipeline,'pipeline implementation missing');self.t=tempfile.TemporaryDirectory(dir='/private/tmp');self.parent=Path(self.t.name).resolve();self.parent.chmod(0o700);self.backend=FixtureBackend()
  self.c=dict(backend=self.backend,state_path=self.parent/'state.json',mail_outbox=self.parent,account_key=ACCOUNT,material_release_id=RELEASE,cold_start_date='2026-10-30',target_date='2026-10-30',now=NOW,preview=True)
 def tearDown(self):self.t.cleanup()
 def test_friday_preview_commits_recommendation_without_fake_credit_or_send(self):
  r=pipeline.run_weekly19_support_job('postclose-precompute',context=self.c)
  self.assertEqual(r['status'],'preview_complete');self.assertFalse(r['production_qualified']);self.assertEqual(self.backend.sends,0)
  b=pipeline.pipeline_store(self.c).read();self.assertEqual(b['funding']['confirmed_topup_fen'],0);self.assertEqual(b['funding']['reserve_remaining_fen'],15000000)
  self.assertEqual(b['decision']['funding_recommendation']['amount_fen'],3000000)
  self.assertEqual(r['mail']['equity_fen'],12000000);self.assertFalse(r['mail']['funding_ready'])
 def test_same_day_replay_returns_same_business_state_and_no_duplicate_request(self):
  pipeline.run_weekly19_support_job('postclose-precompute',context=self.c);a=pipeline.pipeline_store(self.c).read()
  pipeline.run_weekly19_support_job('postclose-precompute',context=self.c);b=pipeline.pipeline_store(self.c).read()
  self.assertEqual(a,b);self.assertEqual(len(b['funding']['requests']),1)
 def test_new_equity_on_same_day_preserves_original_signal_snapshot(self):
  pipeline.run_weekly19_support_job('postclose-precompute',context=self.c);a=pipeline.pipeline_store(self.c).read()
  self.backend.balance='130000.00';r=pipeline.run_weekly19_support_job('postclose-precompute',context=self.c);b=pipeline.pipeline_store(self.c).read()
  self.assertEqual(a['decision_state'],b['decision_state']);self.assertEqual(a['decision'],b['decision'])
  self.assertNotEqual(a['runtime']['state_sha256'],b['runtime']['state_sha256']);self.assertEqual(len(b['funding']['requests']),1)
  self.assertEqual(r['mail']['equity_fen'],13000000);self.assertFalse(r['mail']['actionable'])
 def test_preview_state_cannot_be_loaded_by_live_backend(self):
  pipeline.run_weekly19_support_job('postclose-precompute',context=self.c);self.c['preview']=False
  self.backend.require_production=lambda:None
  with self.assertRaisesRegex(ValueError,'preview_state_cannot_become_production'):pipeline.run_weekly19_session_cycle(context=self.c)
 def test_unqualified_production_fails_before_reading_data_or_sending(self):
  self.c['preview']=False
  with self.assertRaisesRegex(ValueError,'fixture_not_production'):pipeline.run_weekly19_support_job('postclose-precompute',context=self.c)
  self.assertFalse(self.c['state_path'].exists());self.assertEqual(self.backend.sends,0)
 def test_ai_job_is_explicitly_disabled_without_loading_signal_or_network(self):
  r=pipeline.run_weekly19_support_job('monthly-ai-pool',context=self.c);self.assertEqual(r['status'],'disabled_for_fixed19');self.assertFalse(self.c['state_path'].exists())
 def test_before_cold_start_cannot_backfill_historical_open(self):
  self.c['cold_start_date']='2026-11-02';r=pipeline.run_weekly19_support_job('postclose-precompute',context=self.c)
  self.assertEqual(r['status'],'skipped_before_weekly19_cold_start');self.assertFalse(self.c['state_path'].exists())
 def test_report_uses_committed_decision_and_does_not_rerun_strategy(self):
  pipeline.run_weekly19_support_job('postclose-precompute',context=self.c);old=pipeline.pipeline_store(self.c).read()
  r=pipeline.run_weekly19_support_job('postclose-report',context=self.c);self.assertEqual(r['status'],'preview_complete');self.assertEqual(old,pipeline.pipeline_store(self.c).read())
 def test_unprocessed_day_report_blocks_instead_of_making_empty_signal_success(self):
  r=pipeline.run_weekly19_support_job('postclose-report',context=self.c);self.assertEqual(r['status'],'blocked');self.assertIn('completed_decision_missing',r['blockers']);self.assertFalse(self.c['state_path'].exists())
 def test_health_and_day_close_are_not_entry_signal_generators(self):
  r=pipeline.run_weekly19_support_job('health',context=self.c);self.assertEqual(r['status'],'not_initialized');self.assertFalse(self.c['state_path'].exists())
 def test_session_preview_never_publishes_or_calls_sender(self):
  pipeline.run_weekly19_support_job('postclose-precompute',context=self.c)
  r=pipeline.run_weekly19_session_cycle(context=self.c);self.assertEqual(r['status'],'preview_no_execution');self.assertEqual(self.backend.publishes,0);self.assertEqual(self.backend.sends,0)
 def test_snapshot_failure_does_not_change_committed_state(self):
  pipeline.run_weekly19_support_job('postclose-precompute',context=self.c);old=self.c['state_path'].read_bytes()
  def bad(*args):raise ValueError('actual_provider_missing')
  self.backend.load_inputs=bad
  with self.assertRaisesRegex(ValueError,'actual_provider_missing'):pipeline.run_weekly19_session_cycle(context=self.c)
  self.assertEqual(old,self.c['state_path'].read_bytes())
if __name__=='__main__':unittest.main()
