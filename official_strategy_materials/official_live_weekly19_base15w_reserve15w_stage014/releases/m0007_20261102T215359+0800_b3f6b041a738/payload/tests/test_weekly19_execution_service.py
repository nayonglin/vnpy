"""Conditional service lifecycle fixture; runner never connects or submits."""
from pathlib import Path
import sys
import threading
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'examples/portfolio_backtesting'))
import test_weekly19_controller as controller_tests
import qmt_roll_weekly19_controller as controller
try:
 import qmt_roll_weekly19_execution_service as service_module
except ModuleNotFoundError:service_module=None

class Weekly19ExecutionServiceTest(unittest.TestCase):
 def setUp(self):
  self.assertIsNotNone(service_module,'weekly19 execution lifecycle missing')
  self.fx=controller_tests.Weekly19ControllerTest('test_exact_weekly_slow_lane_uses_independent_evidence_contract')
  self.fx.setUp();self.addCleanup(self.fx.doCleanups)
  self.clock=self.fx.fx.clock;self.actor=SimpleNamespace(execution_state=lambda iid:self.fx.fx.state)
  self.stop_seen=threading.Event();self.backend_seen=threading.Event();self.runner_calls=[]
  readiness=self.fx.readiness
  class Session:
   def transport_context(self):return {}
   def readiness_lease(self,**kwargs):return dict(readiness)
   def refresh_weekly19_context(self):return dict(ready=True,transport_context={})
  self.session=Session()
  def runner(args,**kwargs):
   self.runner_calls.append(kwargs);kwargs['backend_observer'](self.session);self.backend_seen.set()
   while not kwargs['stop_requested']():self.stop_seen.wait(.005)
   self.stop_seen.set();return 0
  self.runner=runner
  self.args=SimpleNamespace(execution_profile='weekly19-15w-r150k',runtime_profile='production-live',order_scope='live',
     stage179_runtime_root=str(Path(self.fx.fx.temp.name)/'service'),target_date='2026-10-30')
 def build(self,authority=None):
  decision=dict(schema='weekly19.runtime-decision.v1',material_release_id=self.fx.source['material_release_id'],
   account_fingerprint=self.fx.source['account_fingerprint'],trading_date='2026-10-30',intents=[self.fx.fx.intent])
  return service_module.Weekly19ExecutionService(self.args,authority_provider=lambda **kw:authority,
   fresh_context_provider=lambda row,**kw:self.fx.fx.context,event_consumer=lambda *a,**kw:dict(status='applied',state_sha256='a'*64),
   native_capture_factory=lambda **kw:None,publication_inputs_provider=lambda **kw:dict(decision=decision,
    journal_segment_path=self.fx.fx.path,durable_through=self.fx.fx.cursor),clock=self.clock,runner=self.runner)
 def test_missing_real_authority_blocks_before_runner(self):
  instance=self.build({'qualified':True})
  with self.assertRaisesRegex(ValueError,'source_authority'):
   instance.start(runtime_actor=self.actor)
  self.assertEqual(self.runner_calls,[])
 def test_one_long_lived_actor_publishes_actual_spool_and_stops_revoke(self):
  instance=self.build(self.fx.authority());self.addCleanup(lambda:instance.stop(timeout=2))
  instance.start(runtime_actor=self.actor);self.assertTrue(self.backend_seen.wait(1))
  with patch.object(controller,'_validate_fresh_source_proof',return_value=None):
   result=instance.publish(runtime=self.actor,bundle={},data={},now=None)
  self.assertEqual(result['status'],'published',result)
  self.assertIs(instance.runtime_actor,self.actor)
  self.assertEqual(len(self.runner_calls),1)
  with self.assertRaisesRegex(ValueError,'actor_replacement'):
   instance.bind_actor(SimpleNamespace())
  result=instance.stop(timeout=2)
  self.assertEqual(result['status'],'stopped')
  import qmt_roll_official_live_submit_authorization as protocol
  self.assertEqual(protocol.read_submit_authorization(instance.authorization_path)['status'],'revoked')

 def test_stale_source_refresh_runs_before_new_readiness_and_can_recover_same_connection(self):
  instance=self.build(self.fx.authority());self.addCleanup(lambda:instance.stop(timeout=2))
  refreshed=[]
  self.session.transport_blockers=lambda:[]if refreshed else['fixture_previous_snapshot_stale']
  self.session.refresh_weekly19_context=lambda:refreshed.append(True)or dict(ready=True)
  instance.start(runtime_actor=self.actor);self.assertTrue(self.backend_seen.wait(1))
  with patch.object(controller,'_validate_fresh_source_proof',return_value=None):
   result=instance.publish(runtime=self.actor,bundle={},data={})
  self.assertEqual(result['status'],'published',result);self.assertEqual(refreshed,[True])

 def test_wall_clock_sleep_staleness_forces_refresh_even_if_monotonic_did_not_advance(self):
  instance=self.build(self.fx.authority());self.addCleanup(lambda:instance.stop(timeout=2))
  instance.start(runtime_actor=self.actor);self.assertTrue(self.backend_seen.wait(1));refreshed=[]
  self.session.transport_context=lambda:dict(rows={'_weekly19_native_receipts':{'account':{
   'completed_at':(instance._now()-timedelta(minutes=10)).isoformat()}}})
  self.session.refresh_weekly19_context=lambda:refreshed.append(True)or dict(ready=True)
  instance._last_refresh_ns=self.clock.monotonic_ns()
  instance._refresh_if_due();self.assertEqual(refreshed,[True])

 def test_deferred_actual_broker_fact_recovers_without_permanent_transport_latch(self):
  instance=self.build(self.fx.authority());self.addCleanup(lambda:instance.stop(timeout=2))
  instance.start(runtime_actor=self.actor);self.assertTrue(self.backend_seen.wait(1))
  pending={'event-1':dict(state_sha256='a'*64)}
  self.session.transport_context=lambda:dict(rows={'_weekly19_deferred_broker_events':pending})
  result=instance.publish(runtime=self.actor,bundle={},data={})
  self.assertEqual(result['status'],'blocked');self.assertIn('awaiting_replay',result['blockers'][0])
  pending.clear()
  with patch.object(controller,'_validate_fresh_source_proof',return_value=None):
   result=instance.publish(runtime=self.actor,bundle={},data={})
  self.assertEqual(result['status'],'published',result)

 def test_each_cycle_assembles_one_business_in_original_order(self):
  instance=self.build(self.fx.authority());self.addCleanup(lambda:instance.stop(timeout=2))
  original=instance.inputs_provider();another=deepcopy(original['decision']['intents'][0])
  another['intent_id']='second-business';another['signal_identity']['intent_id']='second-business'
  original['decision']['intents'].append(another);instance.inputs_provider=lambda **kw:original
  instance.start(runtime_actor=self.actor);self.assertTrue(self.backend_seen.wait(1))
  import run_qmt_roll_stage905_official_live_executor_dry_run as producer
  with patch.object(controller,'_validate_fresh_source_proof',return_value=None),patch.object(producer,'run_executor_dry_run',wraps=producer.run_executor_dry_run)as run:
   instance.publish(runtime=self.actor,bundle={},data={})
   self.assertEqual(run.call_count,1)
   self.assertEqual(run.call_args.kwargs['weekly19_decision']['intents'][0]['intent_id'],self.fx.fx.intent['intent_id'])
   run.reset_mock();instance.publish(runtime=self.actor,bundle={},data={})
   self.assertEqual(run.call_count,1)
   self.assertEqual(run.call_args.kwargs['weekly19_decision']['intents'][0]['intent_id'],'second-business')

 def test_warming_connection_returns_without_waiting_for_startup_or_actor_replay(self):
  instance=self.build(self.fx.authority());self.addCleanup(lambda:instance.stop(timeout=2))
  self.session.connection_ready=lambda:False
  def forbidden(*args,**kwargs):raise AssertionError('warming service must not probe or query')
  self.session.refresh_weekly19_context=forbidden;self.session.readiness_lease=forbidden
  instance.start(runtime_actor=self.actor);self.assertTrue(self.backend_seen.wait(1))
  result=instance.publish(runtime=self.actor,bundle={},data={})
  self.assertEqual(result['status'],'warming',result)

 def test_refresh_and_readiness_never_hold_actor_lock_needed_by_broker_callbacks(self):
  instance=self.build(self.fx.authority());self.addCleanup(lambda:instance.stop(timeout=2))
  self.session.connection_ready=lambda:True
  def callback_must_progress():
   done=threading.Event()
   def replay():
    with instance.actor_lock:done.set()
   thread=threading.Thread(target=replay);thread.start()
   self.assertTrue(done.wait(.25),'publication holds actor lock while waiting for transport')
   thread.join(1)
  def refresh():callback_must_progress();return dict(ready=True)
  def readiness(**kw):callback_must_progress();return self.fx.readiness
  self.session.refresh_weekly19_context=refresh;self.session.readiness_lease=readiness
  instance.start(runtime_actor=self.actor);self.assertTrue(self.backend_seen.wait(1))
  with patch.object(controller,'_validate_fresh_source_proof',return_value=None):
   result=instance.publish(runtime=self.actor,bundle={},data={})
  self.assertEqual(result['status'],'published',result)

 def test_original_runner_and_authorization_lease_share_cli_lifetime_deadline(self):
  instance=self.build(self.fx.authority());self.addCleanup(lambda:instance.stop(timeout=2))
  end=self.clock.epoch_ns()+2_000_000_000
  binder=getattr(instance,'bind_deadline',None);self.assertTrue(callable(binder),'session deadline binding missing')
  binder(end)
  with self.assertRaisesRegex(ValueError,'deadline_replacement'):binder(end+1)
  instance.start(runtime_actor=self.actor);self.assertTrue(self.backend_seen.wait(1))
  self.assertEqual(instance._readiness()['expires_epoch_ns'],end)
  self.assertFalse(self.runner_calls[0]['stop_requested']())
  self.clock.epoch=end+1
  self.assertTrue(self.runner_calls[0]['stop_requested']())
  result=instance.publish(runtime=self.actor,bundle={},data={})
  self.assertNotEqual(result['status'],'published')
