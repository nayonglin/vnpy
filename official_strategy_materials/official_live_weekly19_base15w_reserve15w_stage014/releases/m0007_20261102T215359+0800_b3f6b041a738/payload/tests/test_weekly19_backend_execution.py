"""Conditional backend/lifecycle wiring; no production capability or CTP."""
import copy,json,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT/'tests')]
import test_weekly19_session_bridge as fixtures
import qmt_roll_weekly19_local_backend as local
import qmt_roll_weekly19_controller as controller
import qmt_roll_weekly19_live_pipeline as pipeline
from qmt_roll_weekly19_pipeline_state import PipelineStateStore,digest

class BackendExecutionTests(unittest.TestCase):
 def setUp(self):
  self.fx=fixtures.SessionBridgeTests('test_forged_authority_cannot_create_bridge');self.fx.setUp();self.addCleanup(self.fx.doCleanups)
  self.root=self.fx.root;self.actor=self.fx.actor;self.data=self.fx.data
  self.bundle=copy.deepcopy(self.fx.bundle);self.bundle['runtime_mode']='production'
  self.store=PipelineStateStore(self.root/'production.json',self.actor.account,self.actor.release);self.store.initialize(self.bundle)
  runtime_root=self.root/'runtime';(runtime_root/'state').mkdir(parents=True);(runtime_root/'state').chmod(0o700)
  self.ledger=runtime_root/'state/execution_ledger.ndjson';self.ledger.write_bytes(b'');self.ledger.chmod(0o600)
  self.cfg=dict(schema='weekly19.live-context.v1',execution_profile='weekly19-15w-r150k',account_key=self.actor.account,material_release_id=self.actor.release,
    cold_start_date='2026-10-30',target_date='2026-10-30',state_path=str(self.store.path),daily_receipt_path=str(self.root/'daily'),mail_outbox=str(self.root),
    execution_ledger_path=str(self.ledger),broker=dict(private_capture_dir=str(self.root/'captures'),policy={}),market_data={'generation':'fixture'},cash_sources={})
  self.path=self.root/'context.json';self.write(self.cfg)
  self.backend=local.LocalEvidenceBackend(self.cfg,repo_root=ROOT,release_manifest=self.root/'manifest',activation_receipt=runtime_root/'state/activation_receipt.json',qualification_evidence=self.root/'qualification')
  self.backend.context_file=self.path;self.backend._market_cache=self.data
  self.calls=[];self.stops=[]
  self.service=SimpleNamespace(active=True,runtime_actor=self.actor,actor_lock=__import__('threading').RLock(),
    publish=lambda **kw:self.calls.append(kw)or dict(status='warming',production_qualified=False),stop=lambda **kw:self.stops.append(kw)or dict(status='stopped'))
  self.bridge=SimpleNamespace(last_bundle=self.bundle,data=self.data,close=lambda:self.stops.append('bridge_closed'))
 def write(self,value):self.path.write_text(json.dumps(value));self.path.chmod(0o600)
 def bindings(self):
  return patch.object(controller,'load_weekly19_controller_authority',return_value=self.fx.authority),patch('qmt_roll_weekly19_session_bridge.build_weekly19_session_service',return_value=(self.service,self.bridge)),patch.object(self.backend,'require_production',return_value={})
 def start(self):
  authority,builder,gate=self.bindings()
  with authority,builder as construct,gate:
   result=self.backend.publish_execution(runtime=self.actor,bundle=self.bundle,data=self.data,now=self.fx.clock.at)
  return result,construct
 def test_real_source_gate_blocks_before_service_builder_or_connection(self):
  with patch('qmt_roll_weekly19_session_bridge.build_weekly19_session_service',side_effect=AssertionError('not authorized')):
   with self.assertRaisesRegex(local.LocalBackendError,'stable_production_root'):
    self.backend.publish_execution(runtime=self.actor,bundle=self.bundle,data=self.data,now=self.fx.clock.at)
  self.assertFalse(self.backend.external_action_started)
 def test_exact_actor_source_state_and_existing_serve_args_are_bound_once(self):
  result,builder=self.start();self.assertEqual(result['status'],'warming')
  self.assertEqual(builder.call_count,1);args=builder.call_args.args[0]
  self.assertEqual((args.command,args.mode,args.execution_profile,args.runtime_profile,args.order_scope),('serve','live-real','weekly19-15w-r150k','production-live','live'))
  self.assertTrue(args.stage179_warm_executor);self.assertEqual(Path(args.stage179_runtime_root),self.ledger.parent.parent)
  self.assertIs(builder.call_args.kwargs['runtime_actor'],self.actor);self.assertTrue(builder.call_args.kwargs['require_production_qualification'])
  with patch.object(self.backend,'require_production',side_effect=AssertionError('must use pinned authority')):
   again=self.backend.publish_execution(runtime=self.actor,bundle=self.bundle,data=self.data,now=self.fx.clock.at)
  self.assertEqual(again['status'],'warming');self.assertEqual(len(self.calls),2);self.assertTrue(all(c['runtime']is self.actor for c in self.calls))
 def test_only_unadmitted_cash_references_can_change_without_replacing_actor(self):
  self.start();changed=copy.deepcopy(self.cfg);changed['cash_sources']={'deposits':[{'raw_source_path':'/literal/unadmitted'}]};self.write(changed)
  result=self.backend.execution_session_cycle(target_date='2026-10-30',now=self.fx.clock.at)
  self.assertEqual(result['execution']['status'],'warming');self.assertEqual(self.backend.config['cash_sources'],changed['cash_sources'])
  for key,value in [('execution_profile','c9-15w'),('risk',{'cap':999}),('market_data',{'generation':'other'}),('target_date','2026-11-02'),('broker',{'policy':{'capture_authority_registry':{'path':'/other'}}}),('material_release_id','other'),('source_commit','other')]:
   with self.subTest(key=key):
    bad=copy.deepcopy(changed);bad[key]=value;self.write(bad)
    with self.assertRaisesRegex(ValueError,'immutable_fields_changed'):self.backend.execution_session_cycle(target_date='2026-10-30',now=self.fx.clock.at)
  self.assertEqual(len(self.calls),2)
  self.write(changed)
  with self.assertRaisesRegex(ValueError,'immutable_fields_changed|authority_invalidated'):self.backend.execution_session_cycle(target_date='2026-10-30',now=self.fx.clock.at)
 def test_actor_replacement_state_drift_and_preview_never_start_a_service(self):
  bad=copy.deepcopy(self.bundle);bad['runtime_mode']='preview'
  with patch.object(self.backend,'require_production',return_value={}):
   with self.assertRaisesRegex(ValueError,'production_bundle'):self.backend.publish_execution(runtime=self.actor,bundle=bad,data=self.data,now=self.fx.clock.at)
  self.start()
  with self.assertRaisesRegex(ValueError,'actor_replacement'):self.backend.publish_execution(runtime=object(),bundle=self.bundle,data=self.data,now=self.fx.clock.at)
 def test_active_pipeline_does_not_reload_history_or_restore_another_actor(self):
  self.start()
  context=dict(backend=self.backend,target_date='2026-10-30',now=self.fx.clock.at,preview=False)
  with patch.object(self.backend,'load_inputs',side_effect=AssertionError('history reload forbidden')),patch.object(pipeline,'_runtime',side_effect=AssertionError('actor rebuild forbidden')),patch.object(self.backend,'require_production',side_effect=AssertionError('pinned source authority already bound')):
   result=pipeline.run_weekly19_session_cycle(context=context)
  self.assertEqual(result['status'],'session_cycle');self.assertEqual(result['state_sha256'],digest(self.bundle));self.assertIs(self.calls[-1]['runtime'],self.actor)
 def test_shutdown_waits_for_existing_warm_owner_before_closing_bridge(self):
  self.start();self.service.stop=lambda **kw:dict(status='stop_pending')
  self.assertEqual(self.backend.close_session()['status'],'stop_pending');self.assertNotIn('bridge_closed',self.stops)
  self.service.stop=lambda **kw:dict(status='stopped')
  self.assertEqual(self.backend.close_session()['status'],'stopped');self.assertEqual(self.stops,['bridge_closed'])
  self.backend.close_session();self.assertEqual(self.stops,['bridge_closed'])
  with self.assertRaisesRegex(ValueError,'owner_closed'):self.backend.execution_session_cycle(target_date='2026-10-30',now=self.fx.clock.at)
