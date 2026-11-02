"""Synthetic cutover evidence tests; never a real-account qualification."""
import copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT/'tests')]
import test_weekly19_broker_evidence as fixture
NOW,ACCOUNT,RELEASE,PROFILE=fixture.NOW,fixture.ACCOUNT,fixture.RELEASE,fixture.PROFILE
import qmt_roll_weekly19_broker_evidence as provider
from unittest.mock import patch

class CarryInEvidenceTest(unittest.TestCase):
 def setUp(self):
  self.fx=fixture.BrokerEvidenceTest('test_generation_bound_capture_preserves_native_cash_fields_privately')
  self.fx.setUp();self.addCleanup(self.fx.doCleanups)
  self.fx.position['OpenCost']=123400.0
 def policy(self):
  return dict(expected_account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE,now=NOW,
   trusted_source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()for name in provider.CAPTURE_SOURCE_FILES},require_production_qualification=False)
 def test_native_cost_stays_bound_to_same_position_capture(self):
  self.fx.publish()
  value=provider.load_broker_carry_in_positions(self.fx.summary_path,self.fx.manifest_path,**self.policy())
  snapshot=self.fx.load();raw=json.loads(value['raw_payload'])
  self.assertEqual(raw['schema'],'weekly19.ctp-carry-in-positions.v1')
  self.assertEqual(raw['native_positions'][0]['OpenCost'],123400.0)
  self.assertEqual(raw['normalized_positions_sha256'],snapshot['positions']['raw_sha256'])
  self.assertEqual(raw['raw_capture_sha256'],snapshot['provenance']['raw_capture']['sha256'])
  self.assertEqual(hashlib.sha256(value['raw_payload'].encode()).hexdigest(),value['raw_sha256'])
  self.assertFalse(raw['production_qualified'])
 def test_cost_loader_retains_full_native_source_admission(self):
  self.fx.publish()
  bad=self.policy();bad['expected_account_key']='a'*64
  with self.assertRaises(ValueError):provider.load_broker_carry_in_positions(self.fx.summary_path,self.fx.manifest_path,**bad)
  self.fx.mutate_capture(lambda c:c['order_api_counters'].update(order_api_called_count=1))
  with self.assertRaises(ValueError):provider.load_broker_carry_in_positions(self.fx.summary_path,self.fx.manifest_path,**self.policy())

class ExplicitInitializationTest(unittest.TestCase):
 def test_cutover_has_explicit_cli_entry_and_is_not_a_scheduled_job(self):
  import run_qmt_roll_weekly19_live as entry
  import qmt_roll_weekly19_live_pipeline as pipeline
  args=entry.parser().parse_args(['--job','initialize-existing-account','--execution-profile',PROFILE,
   '--context-file','/private/tmp/cfg','--release-manifest','/private/tmp/manifest','--activation-receipt','/private/tmp/activation',
   '--production-qualification-evidence','/private/tmp/qualification'])
  self.assertEqual(args.job,'initialize-existing-account');self.assertNotIn(args.job,pipeline.JOBS)
 def test_initializer_is_not_a_signal_or_delivery_job(self):
  import qmt_roll_weekly19_live_pipeline as pipeline
  from test_weekly19_live_pipeline import PipelineTest
  case=PipelineTest('test_health_and_day_close_are_not_entry_signal_generators');case.setUp();self.addCleanup(case.tearDown)
  # A preview fixture cannot acquire a production startup state or side effects.
  with self.assertRaisesRegex(ValueError,'production_existing_account_initialization_required'):
   pipeline.initialize_weekly19_existing_account(context=case.c)
  self.assertFalse(case.c['state_path'].exists());self.assertEqual(case.backend.sends,0);self.assertEqual(case.backend.publishes,0)
 def test_default_initial_gate_still_rejects_existing_inventory(self):
  from qmt_roll_weekly19_local_backend import LocalEvidenceBackend,LocalBackendError
  backend=object.__new__(LocalEvidenceBackend);backend.config=dict(account_key=ACCOUNT,material_release_id=RELEASE)
  fx=fixture.BrokerEvidenceTest('test_generation_bound_capture_preserves_native_cash_fields_privately');fx.setUp();self.addCleanup(fx.doCleanups);fx.publish()
  with patch.object(backend,'require_production',return_value=None):
   with self.assertRaisesRegex(LocalBackendError,'initial_real_150k_flat_account_required'):backend.validate_initial_account(fx.load(),NOW)

class AtomicCutoverTest(unittest.TestCase):
 def setUp(self):
  import test_weekly19_adoption as carry
  from qmt_roll_weekly19_local_backend import LocalEvidenceBackend
  from test_weekly19_runtime import envelope
  self.at=carry.NOW
  self.calendar,self.physical,self.bars,self.meta,self.snapshot,self.native,self.quote,_,_=carry.sources()
  for key in ('account','positions','orders'):
   raw=json.loads(self.snapshot[key]['raw_payload']);raw.update(execution_profile=PROFILE,query_last_seen=True,query_error_rows=0)
   self.snapshot[key]=envelope(raw)
  raw=json.loads(self.native['raw_payload']);raw.update(normalized_positions_sha256=self.snapshot['positions']['raw_sha256'])
  self.native=envelope(raw)
  self.temp=tempfile.TemporaryDirectory(dir='/private/tmp');self.addCleanup(self.temp.cleanup);self.parent=Path(self.temp.name).resolve();self.parent.chmod(0o700)
  def write(name,obj):
   path=self.parent/name;value=json.dumps(obj,sort_keys=True,separators=(',',':')).encode();path.write_bytes(value);path.chmod(0o600)
   return dict(path=str(path),sha256=hashlib.sha256(value).hexdigest())
  account=json.loads(self.snapshot['account']['raw_payload']);self.account=account['account_key'];self.release=account['material_release_id']
  metadata=write('metadata.json',dict(schema='Stage024.contract-metadata-capture.v1',envelope=self.quote,producer_source_sha256='a'*64,order_api_calls=0))
  auth=dict(schema='weekly19.operator-existing-account.v1',account_key=self.account,material_release_id=self.release,cold_start_date='2026-11-02',
   completed_day='2026-10-30',adoption_scope='all_current_positions_new_management_cohort',
   authorized_positions=json.loads(self.snapshot['positions']['raw_payload'])['positions'],contract_metadata=metadata,
   operator_authorization=dict(source_kind='explicit_user_message',statement='Synthetic explicit cutover fixture; no production authority.'))
  config=dict(schema='weekly19.live-context.v1',execution_profile=PROFILE,account_key=self.account,material_release_id=self.release,
   cold_start_date='2026-11-02',cash_verification_mode='operator_manual_v1',initial_account_mode='operator_existing_account_v1',
   startup_authorization=write('authorization.json',auth),cash_sources={},broker=dict(summary_path='/private/tmp/NO_REAL_SOURCE',manifest_path='/private/tmp/NO_REAL_MANIFEST',policy={}))
  self.backend=LocalEvidenceBackend(config,repo_root=ROOT,release_manifest=self.parent/'NO_RELEASE',activation_receipt=self.parent/'NO_ACTIVATION',qualification_evidence=self.parent/'NO_QUALIFICATION')
  self.data=dict(metadata=self.meta,calendar=self.calendar,physical_epoch_daily=self.physical,bars_by_day=self.bars,
   receipt=dict(schema='weekly19.data-receipt.v1',complete=True,trading_date='2026-10-30',material_release_id=self.release,source_sha256='b'*64),broker_snapshot=self.snapshot)
  self.context=dict(backend=self.backend,state_path=self.parent/'state.json',mail_outbox=self.parent,account_key=self.account,
   material_release_id=self.release,cold_start_date='2026-11-02',target_date='2026-10-30',now=self.at,preview=False)
  # Patching authority is deliberately fixture-only. Real initialization must
  # load the stable checkout and actual release/qualification/activation chain.
  for method,value in [('require_production',None),('load_inputs',self.data),('read_execution_events',[])]:
   p=patch.object(self.backend,method,return_value=value);p.start();self.addCleanup(p.stop)
  p=patch.object(provider,'load_broker_carry_in_positions',return_value=self.native);p.start();self.addCleanup(p.stop)
 def initialize(self):
  import qmt_roll_weekly19_live_pipeline as pipeline
  return pipeline.initialize_weekly19_existing_account(context=self.context)
 def test_cash_positions_and_protection_commit_together_without_signal_or_side_effect(self):
  import qmt_roll_weekly19_live_pipeline as pipeline
  with patch.object(self.backend,'send_mail',side_effect=AssertionError('SMTP forbidden')),patch.object(self.backend,'publish_execution',side_effect=AssertionError('orders forbidden')):
   result=self.initialize()
  self.assertEqual(result['status'],'existing_account_initialized')
  bundle=pipeline.pipeline_store(self.context).read();self.assertIsNone(bundle['decision']);self.assertIsNone(bundle['decision_state'])
  self.assertEqual(bundle['funding']['reserve_remaining_fen'],15000000);self.assertEqual(bundle['funding']['confirmed_topup_fen'],0)
  self.assertEqual(bundle['funding']['opening_equity']['observed_equity_fen'],17000000)
  actor=pipeline._runtime(bundle,self.data,self.at)
  self.assertEqual(sum(actor.strategy.pos_data.values()),2);self.assertTrue(actor.strategy.states['rb.SHFE'].layers[0].entry_price_synced)
  self.assertEqual(actor.engine.order_intents,{});self.assertEqual(actor.last_processed_day,'')
  before=self.context['state_path'].read_bytes()
  with patch.object(self.backend,'bootstrap_existing_account',side_effect=AssertionError('duplicate adoption forbidden')):
   self.assertEqual(self.initialize()['status'],'already_initialized')
  self.assertEqual(before,self.context['state_path'].read_bytes())
 def test_failed_protection_or_injected_cash_activity_leaves_no_partial_state(self):
  import qmt_roll_weekly19_funding as funds
  original=self.backend.bootstrap_existing_account
  for failure in ('protection','fund_activity'):
   def bad(bundle,data,now):
    if failure=='protection':raise ValueError('synthetic protection rejected')
    actor=original(bundle,data,now)
    result=funds.recommend_topup(actor.confirmed_cash_state,actor.broker_snapshot['account'],'2026-11-02',['synthetic'], 'a'*64, now)
    # A forged initial revision is rejected even if the cash is otherwise valid.
    actor.confirmed_cash_state=copy.deepcopy(result['state']);actor.confirmed_cash_state['revision']+=1
    return actor
   with self.subTest(failure=failure),patch.object(self.backend,'bootstrap_existing_account',side_effect=bad):
    with self.assertRaises(ValueError):self.initialize()
    self.assertFalse(self.context['state_path'].exists())

if __name__=='__main__':unittest.main()
