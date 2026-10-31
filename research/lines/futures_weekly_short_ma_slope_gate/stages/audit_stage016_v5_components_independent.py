"""Synthetic V5 source/cash/bootstrap/orchestration counterexamples; no real services."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch
ROOT=Path('/Users/mac/.codex/worktrees/weekly19-official-20261031/fian')
sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT/'tests')]
import qmt_roll_weekly19_funding as funding
import qmt_roll_weekly19_broker_evidence as provider
import qmt_roll_weekly19_warm_evidence as warm
import qmt_roll_weekly19_live_pipeline as pipeline
from qmt_roll_weekly19_local_backend import LocalEvidenceBackend
import test_weekly19_external_funding as ff
import test_weekly19_broker_evidence as pf
import test_weekly19_warm_evidence as wf
import test_weekly19_live_pipeline as lf

class CashInitialIndependent(unittest.TestCase):
 def setUp(self):
  self.state=funding.initial_state(ff.ACCOUNT,ff.RELEASE,'2026-10-30')
  self.account=ff.broker(balance='150000.00',deposit='150000.00',Available='150000.00',query_last_seen=True,query_error_rows=0)
 def test_initial_capital_deposit_does_not_debit_external_reserve(self):
  result=funding.begin_cash_observation(self.state,self.account,ff.NOW)
  self.assertEqual(result['reserve_remaining_fen'],15000000);self.assertEqual(result['confirmed_topup_fen'],0)
  self.assertEqual(result['cashflow_checkpoint']['deposit_fen'],15000000);self.assertEqual(result['revision'],1)
 def test_same_initial_raw_is_idempotent_but_new_observation_cannot_reset_checkpoint(self):
  result=funding.begin_cash_observation(self.state,self.account,ff.NOW)
  self.assertEqual(funding.begin_cash_observation(result,self.account,ff.NOW),result)
  raw=json.loads(self.account['raw_payload']);raw['generation_uuid']='another-complete-query'
  with self.assertRaises(funding.FundingError):funding.begin_cash_observation(result,ff.envelope(raw),ff.NOW)
 def test_available_and_native_cash_are_strict_before_initial_checkpoint(self):
  for key,value in [('Available','-0.01'),('Available','NaN'),('Balance','149999.99'),('query_last_seen',1),('query_error_rows',False)]:
   raw=json.loads(self.account['raw_payload']);raw[key]=value
   with self.subTest(key=key,value=value),self.assertRaises(funding.FundingError):funding.begin_cash_observation(self.state,ff.envelope(raw),ff.NOW)
  self.assertIsNone(self.state['cashflow_checkpoint']);self.assertEqual(self.state['revision'],0)
 def test_missing_real_day_close_preserves_cash_and_blocks_open(self):
  state=funding.begin_cash_observation(self.state,self.account,ff.NOW)
  now=ff.NOW+timedelta(days=3)
  account=ff.broker(balance='150100.00',at=now,day='2026-11-02',Available='150100.00',query_last_seen=True,query_error_rows=0)
  backend=object.__new__(LocalEvidenceBackend);backend.config={'cash_sources':{}}
  updated=backend.reconcile_cash(state,{'account':account},now)
  self.assertEqual(updated,state);self.assertIsNot(updated,state)
  self.assertIn('final_broker_day_close_statement',backend.cash_source_blocker)
  with self.assertRaisesRegex(funding.FundingError,'day_roll_requires_reconciliation'):funding.assert_open_funding_ready(updated,account,now)
 def test_caller_finality_and_production_booleans_do_not_create_statement_parser(self):
  with self.assertRaisesRegex(provider.BrokerEvidenceError,'missing_statement'):
   provider.load_cashflow_day_close({'qualified':True,'cashflows_complete':True,'production_qualified':True})

class ProviderV5Independent(unittest.TestCase):
 def setUp(self):
  self.fx=pf.BrokerEvidenceTest();self.fx.setUp();self.addCleanup(self.fx.doCleanups)
  self.wx=wf.WarmEvidenceTest();self.wx.setUp();self.addCleanup(self.wx.doCleanups)
 def test_same_connection_fixture_cannot_claim_production_by_boolean(self):
  self.wx.context['rows']['production_qualified']=True
  with self.assertRaisesRegex(provider.BrokerEvidenceError,'authority_missing'):
   warm.load_warm_broker_snapshot(self.wx.context,**dict(self.wx.policy,require_production_qualification=True))
 def test_raw_epoch_mirror_mismatch_is_not_repaired_by_normalized_rows(self):
  context=copy.deepcopy(self.wx.context)
  context['rows']['_weekly19_native_receipts']['orders']['native_callbacks'][0]['data']['VolumeTotalOriginal']=3
  context['rows']['normalized_orders']=[{'volume':2}]
  with self.assertRaisesRegex(provider.BrokerEvidenceError,'mirror_mismatch'):
   warm.load_warm_broker_snapshot(context,**self.wx.policy)
 def test_unique_parent_plan_and_actual_child_caps_stay_separate(self):
  row=self.fx.order_ledger(planned_volume=2,broker_order_volume=1,order_request_volume=1,planned_direction='long',planned_offset='open',direction='BUY',offset='OPEN')
  bindings=provider.derive_order_intent_bindings([row],expected_account_key=pf.ACCOUNT,material_release_id=pf.RELEASE,execution_profile=pf.PROFILE)
  self.assertEqual((bindings[0]['planned_volume'],bindings[0]['broker_order_volume']),(2,1))
  self.fx.publish(orders=[dict(self.fx.order,VolumeTotalOriginal=1,VolumeTraded=0,OrderStatus='3')])
  raw=json.loads(provider.load_broker_order_updates(self.fx.summary_path,self.fx.manifest_path,bindings,**self.fx._load_kwargs())[0]['raw_payload'])
  self.assertEqual(raw['volume'],1)
  bindings[0]['broker_order_volume']=3
  with self.assertRaisesRegex(provider.BrokerEvidenceError,'volume_mismatch'):
   provider.load_broker_order_updates(self.fx.summary_path,self.fx.manifest_path,bindings,**self.fx._load_kwargs())
 def test_same_native_identity_cannot_bind_two_delivery_intents(self):
  first=self.fx.order_ledger();second=copy.deepcopy(first);second['intent_id']='delivery-2';second['planned_intent_id']=first['intent_id']
  with self.assertRaisesRegex(provider.BrokerEvidenceError,'binding_conflict'):
   provider.derive_order_intent_bindings([first,second],expected_account_key=pf.ACCOUNT,material_release_id=pf.RELEASE,execution_profile=pf.PROFILE)
 def test_capture_authority_cannot_be_constructed_from_boolean(self):
  with self.assertRaisesRegex(provider.BrokerEvidenceError,'authority_loader_required'):provider.CaptureAuthority(True,{}, {},b'0'*32)
 def test_registry_needs_real_production_artifacts_even_after_mock_candidate_qualification(self):
  with patch.object(provider,'_validate_authority_qualification',return_value={'evidence_sha256':'a'*64}):
   with self.assertRaisesRegex(provider.BrokerEvidenceError,'production_manifest_activation_required'):
    provider.create_capture_authority_registry(self.fx.root/'registry',qualification_path=str(self.fx.root/'candidate'),qualification_sha256='a'*64,expected_account_key=pf.ACCOUNT,
     material_release_id=pf.RELEASE,execution_profile=pf.PROFILE,source_commit='a'*40,official_version='fixture-only',critical_files=list(provider.CAPTURE_AUTHORITY_SOURCE_FILES),manifest_created_at_utc=pf.NOW.isoformat(),now=pf.NOW)

class OrchestrationIndependent(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir='/private/tmp');self.addCleanup(self.temp.cleanup)
  self.path=Path(self.temp.name).resolve();self.path.chmod(0o700);self.backend=lf.FixtureBackend()
  self.context=dict(backend=self.backend,state_path=self.path/'state.json',mail_outbox=self.path,account_key=lf.ACCOUNT,material_release_id=lf.RELEASE,cold_start_date='2026-10-30',target_date='2026-10-30',now=lf.NOW,preview=True)
 def test_missing_qualification_fails_before_data_state_and_delivery(self):
  self.context['preview']=False
  with patch.object(self.backend,'load_inputs',side_effect=AssertionError('data before qualification')):
   with self.assertRaisesRegex(ValueError,'fixture_not_production'):pipeline.run_weekly19_support_job('postclose-precompute',context=self.context)
  self.assertFalse(self.context['state_path'].exists());self.assertEqual(self.backend.sends,0)
 def test_committed_bundle_exists_before_report_side_effect_boundary(self):
  seen=[]
  def observe(context,backend,bundle,data,now,preview):
   persisted=pipeline.pipeline_store(context).read();self.assertEqual(persisted,bundle);self.assertIsNotNone(persisted['decision_state']);seen.append(True)
   return {'preview':True}
  with patch.object(pipeline,'_report',side_effect=observe):pipeline.run_weekly19_support_job('postclose-precompute',context=self.context)
  self.assertEqual(seen,[True]);self.assertEqual(self.backend.sends,0)
 def test_cash_transaction_exception_does_not_report_or_invent_state(self):
  pipeline.run_weekly19_support_job('postclose-precompute',context=self.context);before=self.context['state_path'].read_bytes()
  with patch.object(self.backend,'reconcile_cash',side_effect=ValueError('cash backend missing')),patch.object(pipeline,'_report',side_effect=AssertionError('uncommitted report')):
   with self.assertRaisesRegex(ValueError,'cash backend missing'):pipeline.run_weekly19_support_job('postclose-precompute',context=self.context)
  self.assertEqual(before,self.context['state_path'].read_bytes())
 def test_daily_receipt_write_failure_prevents_mail_but_keeps_committed_signal(self):
  self.backend.complete_postclose=lambda *a:(_ for _ in()).throw(ValueError('receipt io'))
  with patch.object(pipeline,'_report',side_effect=AssertionError('mail before receipt')):
   with self.assertRaisesRegex(ValueError,'receipt io'):pipeline.run_weekly19_support_job('postclose-precompute',context=self.context)
  bundle=pipeline.pipeline_store(self.context).read();self.assertIsNotNone(bundle['decision']);self.assertEqual(len(bundle['funding']['requests']),1)
 def test_preview_to_live_mode_is_immutable_even_with_fixture_gate_bypass(self):
  pipeline.run_weekly19_support_job('postclose-precompute',context=self.context)
  self.context['preview']=False;self.backend.require_production=lambda:None
  with self.assertRaisesRegex(ValueError,'preview_state_cannot_become_production'):pipeline.run_weekly19_session_cycle(context=self.context)
  self.assertEqual(self.backend.publishes,0)
 def test_foreign_market_receipt_does_not_initialize_store(self):
  original=self.backend.load_inputs
  def foreign(*a):
   data=original(*a);data['receipt']['material_release_id']='foreign-release';return data
  with patch.object(self.backend,'load_inputs',side_effect=foreign):
   with self.assertRaisesRegex(ValueError,'input_receipt_mismatch'):pipeline.run_weekly19_support_job('postclose-precompute',context=self.context)
  self.assertFalse(self.context['state_path'].exists())

if __name__=='__main__':unittest.main(verbosity=2)
