"""Independent offline chain counterexamples; mocked authority is never qualification."""
from pathlib import Path
import copy,dataclasses,sys,threading,unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT),str(ROOT/'tests'),str(ROOT/'examples/portfolio_backtesting')]
from vnpy.trader.setting import SETTINGS
SETTINGS['log.file']=False;SETTINGS['log.console']=False
import tests.test_weekly19_execution_service as service_tests
import tests.test_weekly19_backend_execution as backend_tests
import tests.test_weekly19_physical_gate as physical_tests
import qmt_roll_weekly19_controller as controller
import qmt_roll_weekly19_execution as gate
import qmt_roll_weekly19_local_backend as backend_module
import run_qmt_roll_stage931_official_live_ctp_submit_adapter as runner

class ServiceIndependent(unittest.TestCase):
 def setUp(self):
  self.fx=service_tests.Weekly19ExecutionServiceTest('test_missing_real_authority_blocks_before_runner');self.fx.setUp();self.addCleanup(self.fx.doCleanups)
 def test_expired_typed_authority_rejected_before_runner(self):
  auth=dataclasses.replace(self.fx.fx.authority(),expires_epoch_ns=self.fx.clock.epoch_ns())
  service=self.fx.build(auth)
  with self.assertRaisesRegex(ValueError,'expired'):service.start(runtime_actor=self.fx.actor)
  self.assertEqual(self.fx.runner_calls,[]);self.assertIsNone(service._thread)
 def test_source_check_failure_is_latched_even_after_source_restored(self):
  checks=[];broken=[True]
  def actual(at):
   checks.append(at)
   if broken[0]:raise ValueError('independent_actual_source_changed')
  auth=dataclasses.replace(self.fx.fx.authority(),_source_check=actual)
  service=self.fx.build(auth)
  with self.assertRaisesRegex(ValueError,'actual_source_changed'):service.start(runtime_actor=self.fx.actor)
  broken[0]=False
  with self.assertRaisesRegex(ValueError,'invalidated'):service.start(runtime_actor=self.fx.actor)
  self.assertEqual(len(checks),1);self.assertEqual(self.fx.runner_calls,[])
 def test_publication_mutex_contention_does_not_bind_or_start(self):
  service=self.fx.build(self.fx.fx.authority());service._publication_lock.acquire()
  try:result=service.publish(runtime=self.fx.actor,bundle={},data={})
  finally:service._publication_lock.release()
  self.assertEqual(result['status'],'publication_in_progress');self.assertIsNone(service.runtime_actor);self.assertIsNone(service._thread)
 def test_event_consumer_serializes_same_actor(self):
  service=self.fx.build(self.fx.fx.authority());service.bind_actor(self.fx.actor);entered=threading.Event();done=threading.Event();errors=[]
  def consume(*args,**kw):self.assertIs(kw['runtime_actor'],self.fx.actor);entered.set();return {'status':'fixture'}
  service.event_consumer=consume
  def callback():
   try:service._event('trade',{},{});done.set()
   except BaseException as e:errors.append(repr(e))
  with service.actor_lock:
   thread=threading.Thread(target=callback);thread.start();self.assertFalse(entered.wait(.03))
  thread.join(1);self.assertFalse(thread.is_alive());self.assertTrue(done.is_set());self.assertEqual(errors,[])
 def test_deadline_caps_readiness_and_prevents_late_runner_start(self):
  service=self.fx.build(self.fx.fx.authority());end=self.fx.clock.epoch_ns()+2_000_000_000
  service.bind_deadline(end);service._session=self.fx.session
  self.assertEqual(service._readiness()['expires_epoch_ns'],end)
  with self.assertRaisesRegex(ValueError,'replacement'):service.bind_deadline(end+1)
  self.fx.clock.epoch=end
  self.assertTrue(service._lifetime_stopped())
  with self.assertRaisesRegex(ValueError,'lifetime_ended'):service.start(runtime_actor=self.fx.actor)
  self.assertEqual(self.fx.runner_calls,[])
 def test_stop_cannot_be_reversed_by_publishing_same_actor(self):
  service=self.fx.build(self.fx.fx.authority());service._stop.set()
  result=service.publish(runtime=self.fx.actor,bundle={},data={})
  self.assertEqual(result['status'],'blocked');self.assertEqual(self.fx.runner_calls,[]);self.assertIsNone(service._thread)

class TypedBatchIndependent(unittest.TestCase):
 def setUp(self):
  self.fx=physical_tests.PhysicalGateTest('test_real_typed_bindings_are_not_misread_as_terminal_execution_events');self.fx.setUp();self.addCleanup(self.fx.doCleanups)
 def test_same_order_binding_cannot_be_reused_by_foreign_payload_or_owner(self):
  self.assertTrue(gate.evaluate_intent(self.fx.intent,self.fx.context,now=physical_tests.NOW)['allowed'])
  for key in ('payload_sha256','lease_owner','lease_token'):
   with self.subTest(key=key):
    bad=dict(self.fx.context,current_delivery_lease=dict(self.fx.context['current_delivery_lease'],**{key:'independent-foreign'}))
    self.assertFalse(gate.evaluate_intent(self.fx.intent,bad,now=physical_tests.NOW)['allowed'])
 def test_nested_typed_binding_pollution_does_not_become_capacity(self):
  self.fx.bindings[0]['approved_parent_volume']=999999
  self.assertFalse(gate.evaluate_intent(self.fx.intent,self.fx.context,now=physical_tests.NOW)['allowed'])
 def test_parent_remaining_cap_and_actual_partial_fill_are_conserved(self):
  parent=dict(intent_id='delivery',planned_intent_id='business',signal_order_id='order',signal_identity={'intent_id':'business'},vt_symbol='rb2612.SHFE',direction='long',offset='open',planned_volume=225)
  row=dict(parent,planned_volume=125)
  life=dict(schema='weekly19.actual-fill-lifecycle.v1',planned_intent_id='business',delivery_intent_id='delivery',signal_order_id='order',durable_state_sha256='a'*64,business_approved_volume=225,business_filled_volume=100,business_remaining_volume=125,delivery_approved_volume=225,delivery_filled_volume=100,delivery_remaining_volume=125,delivery_trade_ids=['native-trade'])
  context=dict(actual_fill_lifecycle=life,durable_state_sha256='a'*64,open_risk_proof=dict(selected_volume=125))
  transport=dict(weekly19_immutable_parent_intent=parent,weekly19_current_physical_child=dict(volume=125))
  self.assertEqual(runner._weekly19_physical_volume_blockers(row,context,transport),[])
  for changed in [dict(life,delivery_remaining_volume=126),dict(life,delivery_trade_ids=['native-trade','native-trade']),dict(life,business_filled_volume=True),dict(life,durable_state_sha256='b'*64)]:
   with self.subTest(life=changed):
    try:result=runner._weekly19_physical_volume_blockers(row,dict(context,actual_fill_lifecycle=changed),transport)
    except ValueError:result=['rejected']
    self.assertTrue(result)
  self.assertTrue(runner._weekly19_physical_volume_blockers(row,dict(context,open_risk_proof=dict(selected_volume=124)),transport))

class CashReferenceIndependent(unittest.TestCase):
 def setUp(self):
  self.fx=backend_tests.BackendExecutionTests('test_real_source_gate_blocks_before_service_builder_or_connection');self.fx.setUp();self.addCleanup(self.fx.doCleanups)
 def test_raw_cash_reference_or_amount_never_credits_actor_or_store(self):
  self.fx.start();before=self.fx.actor.export_state();file_before=self.fx.store.path.read_bytes()
  changed=copy.deepcopy(self.fx.cfg);changed['cash_sources']={'deposits':[{'path':'/unadmitted/never-read','amount':150000,'source_qualified':True,'production_qualified':True}]}
  self.fx.write(changed);result=self.fx.backend.execution_session_cycle(target_date='2026-10-30',now=self.fx.fx.clock.at)
  self.assertEqual(result['execution']['status'],'warming');self.assertEqual(before,self.fx.actor.export_state());self.assertEqual(file_before,self.fx.store.path.read_bytes())
 def test_active_owner_cannot_adopt_a_new_market_target(self):
  self.fx.start();calls=len(self.fx.calls)
  with self.assertRaisesRegex(ValueError,'new_market_generation'):self.fx.backend.execution_session_cycle(target_date='2026-11-02',now=self.fx.fx.clock.at)
  self.assertEqual(len(self.fx.calls),calls)
 def test_private_context_permission_failure_latches_authority(self):
  self.fx.start();self.fx.path.chmod(0o644)
  with self.assertRaises(ValueError):self.fx.backend.execution_session_cycle(target_date='2026-10-30',now=self.fx.fx.clock.at)
  self.fx.path.chmod(0o600)
  with self.assertRaisesRegex(ValueError,'immutable_fields_changed|invalidated'):self.fx.backend.execution_session_cycle(target_date='2026-10-30',now=self.fx.fx.clock.at)

if __name__=='__main__':unittest.main()
