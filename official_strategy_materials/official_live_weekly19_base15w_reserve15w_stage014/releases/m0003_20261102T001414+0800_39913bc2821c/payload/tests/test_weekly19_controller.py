"""Conditional protocol fixtures; source validators are patched, never real qualification."""
from dataclasses import asdict
from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'examples/portfolio_backtesting'))
import test_weekly19_quote_spool as quote_tests
from test_weekly19_execution import NOW,RELEASE,ACCOUNT
import qmt_roll_official_live_intent_spool as spool
import qmt_roll_official_live_submit_authorization as authorization
try:
 import qmt_roll_weekly19_controller as controller
except ModuleNotFoundError:controller=None

class Weekly19ControllerTest(unittest.TestCase):
 def setUp(self):
  self.assertIsNotNone(controller,'weekly19 controller missing')
  self.fx=quote_tests.Weekly19QuoteSpoolTest('test_weekly_signal_and_new_quote_trace_remain_distinct_and_spoolable')
  self.fx.setUp();self.addCleanup(self.fx.doCleanups)
  self.connection=spool.open_spool(Path(self.fx.temp.name)/'controller.sqlite3');self.addCleanup(self.connection.close)
  self.item=self.fx.prepare()
  import qmt_roll_weekly19_quote_spool as assembly
  assembly.commit_weekly19_quote_batch(self.connection,expected_cursor=None,next_cursor=self.fx.cursor,intents=[self.item],clock=self.fx.clock)
  self.path=Path(self.fx.temp.name)/'authorization.json'
  self.readiness=dict(service_generation='svc',connection_generation='conn',runtime_profile='production-live',
   official_version='official_live_weekly19_base15w_reserve15w_stage014',capital=150000,
   service_kind='warm_live_executor',issued_epoch_ns=self.fx.clock.epoch_ns(),expires_epoch_ns=self.fx.clock.epoch_ns()+10000000000)
  self.source=dict(execution_profile='weekly19-15w-r150k',official_version=self.readiness['official_version'],
   ruleset_version='stage014_week_close_19_short_bottom20_original_risk_external_reserve_v1',material_release_id=RELEASE,
   account_fingerprint=ACCOUNT,source_commit='b'*40,production_source_commit='b'*40,material_source_commit='a'*40,manifest_sha256='b'*64,qualification_sha256='c'*64,
   activation_receipt_sha256='d'*64,daily_receipt_sha256='e'*64,source_data_receipt_sha256='f'*64,
   decision_origin_state_sha256='1'*64,target_cutoff_date='2026-10-30')
 def authority(self):
  return controller.Weekly19ControllerAuthority(controller._AUTHORITY_TOKEN,self.source,lambda now:None,
      self.fx.clock.epoch_ns()+100000000000,{},None)
 def publish(self,authority=None,provider=None):
  return controller.publish_weekly19_controller_authorization(self.connection,spool_path=Path(self.fx.temp.name)/'controller.sqlite3',
   authorization_path=self.path,authority=authority,fresh_context_provider=provider or(lambda row:self.fx.context),
   readiness=self.readiness,clock=self.fx.clock)
 def test_qualified_boolean_cannot_create_authority(self):
  result=self.publish({'qualified':True,'production_qualified':True})
  self.assertEqual(result['status'],'blocked')
  self.assertNotEqual(authorization.read_submit_authorization(self.path).get('status'),'authorized')
 def test_exact_weekly_slow_lane_uses_independent_evidence_contract(self):
  with patch.object(controller,'_validate_fresh_source_proof',return_value=None):result=self.publish(self.authority())
  self.assertEqual(result['status'],'published',result)
  payload=authorization.read_submit_authorization(self.path)
  self.assertEqual(payload['authorization_lane'],'slow_controller')
  self.assertEqual(payload['controller_evidence']['schema'],'weekly19.controller-evidence.v1')
  self.assertNotIn('controller_status',payload['controller_evidence'])
  self.assertNotIn('real_submit_permitted',payload['stage927_evidence'])
  record=payload['authorized_intents'][0]
  blockers=authorization.validate_submit_authorization(path=self.path,target_date='2026-10-30',execution_profile='weekly19-15w-r150k',
   runtime_profile='production-live',order_scope='live',service_generation='svc',connection_generation='conn',
   now_epoch_ns=self.fx.clock.epoch_ns(),intent_id=record['intent_id'],payload_sha256=record['payload_sha256'],intent_kind='open',
   weekly19_bindings=record['weekly19_bindings'],
   **{key:record[key]for key in (*authorization._EXACT_TEXT_FIELDS,*authorization._EXACT_INT_FIELDS)})
  self.assertEqual(blockers,[])
  import run_qmt_roll_stage931_official_live_ctp_submit_adapter as execution
  expected=execution.weekly19_authorization_row_bindings(self.item)
  self.assertEqual(authorization._weekly19_evidence_blockers(payload,expected),[])
  expected['planned_intent_id']='another-native-plan'
  self.assertIn('weekly19_authorization_expected_source_binding_mismatch',
    authorization._weekly19_evidence_blockers(payload,expected))
 def test_stale_cash_or_spool_mutation_cannot_publish(self):
  self.fx.context['broker_snapshot']['orders']['raw_sha256']='0'*64
  with patch.object(controller,'_validate_fresh_source_proof',return_value=None):result=self.publish(self.authority())
  self.assertEqual(result['status'],'blocked')
  self.assertNotEqual(authorization.read_submit_authorization(self.path).get('status'),'authorized')
 def test_old_c9_status_does_not_satisfy_weekly_evidence(self):
  with patch.object(controller,'_validate_fresh_source_proof',return_value=None):self.publish(self.authority())
  payload=authorization.read_submit_authorization(self.path)
  payload['controller_evidence']=dict(controller_status='phase_d_controller_live_real_ready_no_submit_step',expires_epoch_ns=payload['expires_epoch_ns'])
  payload=authorization._signed(payload);authorization._atomic_write_json(self.path,payload)
  blockers=authorization.validate_submit_authorization(path=self.path,target_date='2026-10-30',execution_profile='weekly19-15w-r150k',
   runtime_profile='production-live',order_scope='live',service_generation='svc',connection_generation='conn',now_epoch_ns=self.fx.clock.epoch_ns())
  self.assertTrue(any('weekly19' in value for value in blockers),blockers)

class Weekly19LateReadinessTest(Weekly19ControllerTest):
 def test_actual_readiness_is_sampled_after_slow_original_risk_proof(self):
  order=[]
  def context(row):
   order.append('risk_proof')
   self.fx.clock.epoch+=4_000_000_000;self.fx.clock.mono+=4_000_000_000
   return self.fx.context
  def current_readiness():
   order.append('readiness')
   return dict(self.readiness,issued_epoch_ns=self.fx.clock.epoch_ns(),expires_epoch_ns=self.fx.clock.epoch_ns()+3_000_000_000)
  with patch.object(controller,'_validate_fresh_source_proof',return_value=None):
   result=controller.publish_weekly19_controller_authorization(self.connection,spool_path=Path(self.fx.temp.name)/'controller.sqlite3',
    authorization_path=self.path,authority=self.authority(),fresh_context_provider=context,readiness=current_readiness,clock=self.fx.clock)
  self.assertEqual(result['status'],'published',result);self.assertEqual(order,['risk_proof','readiness'])

if __name__=='__main__':unittest.main()

class Weekly19ProductionIdentityTest(unittest.TestCase):
 def test_verified_production_head_can_differ_from_material_source_but_cannot_drift(self):
  import tempfile,hashlib
  from types import SimpleNamespace
  with tempfile.TemporaryDirectory()as directory:
   source=Path(directory)/'critical.py';source.write_text('A=1\n')
   pins={str(source):hashlib.sha256(source.read_bytes()).hexdigest()}
   material='a'*40;production='b'*40
   self.assertNotEqual(material,production)
   with patch.object(controller.subprocess,'run',return_value=SimpleNamespace(stdout=production+'\n')):
    controller._assert_pinned_production_source(Path(directory),production,pins)
   with patch.object(controller.subprocess,'run',return_value=SimpleNamespace(stdout='c'*40+'\n')):
    with self.assertRaisesRegex(ValueError,'production_head_drift'):
     controller._assert_pinned_production_source(Path(directory),production,pins)

class Weekly19ProductionManifestTest(unittest.TestCase):
 def test_production_manifest_source_must_equal_verified_head(self):
  with self.assertRaisesRegex(ValueError,'production_manifest_source_mismatch'):
   controller._assert_production_manifest_head({'source_commit':'a'*40},'b'*40)
  controller._assert_production_manifest_head({'source_commit':'b'*40},'b'*40)
