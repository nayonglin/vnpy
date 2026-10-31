"""Offline same-connection bridge fixtures; no CTP, publication or qualification."""
import copy
from datetime import datetime,timedelta,timezone
import hashlib,json,os,stat
from pathlib import Path
import sys,tempfile,threading,unittest
from types import SimpleNamespace
from unittest import mock
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'examples/portfolio_backtesting'))
import tests.test_weekly19_runtime as runtime_tests
from tests.test_weekly19_runtime import broker,ACCOUNT,RELEASE,SYMBOL,NOW,receipt,envelope,fixture
import qmt_roll_weekly19_runtime as runtime
import qmt_roll_weekly19_controller as controller
from qmt_roll_weekly19_pipeline_state import PipelineStateStore
import qmt_roll_weekly19_broker_evidence as provider
import qmt_roll_weekly19_warm_evidence as warm
from qmt_roll_official_live_tick_types import DurableTickCursor
try:import qmt_roll_weekly19_session_bridge as bridge_module
except ModuleNotFoundError as exc:
 if exc.name!='qmt_roll_weekly19_session_bridge':raise
 bridge_module=None

class Clock:
 def __init__(self,at):self.at=at;self.mono=10_000_000_000
 def epoch_ns(self):return int(self.at.timestamp()*1e9)
 def monotonic_ns(self):return self.mono
 def clock_domain_id(self):return 'bridge-fixture-boot'

class Events:
 def __init__(self):self.handlers={}
 def register(self,kind,fn):self.handlers.setdefault(kind,[]).append(fn)
 def unregister(self,kind,fn):self.handlers[kind].remove(fn)
 def emit(self,kind,value):
  for handler in self.handlers.get(kind,[]):handler(SimpleNamespace(data=value))

class Gateway:
 gateway_name='CTP'
 def __init__(self,event_engine):self.events=event_engine
 def on_tick(self,tick):self.events.emit('eTick.',tick)

class Main:
 def __init__(self,meta):
  self.event_engine=Events();self.gateway=Gateway(self.event_engine);self.subscriptions=[]
  self.contracts={s:SimpleNamespace(vt_symbol=s,gateway_name='CTP',pricetick=meta['priceticks'][s],size=meta['sizes'][s],min_volume=1,max_volume=10000) for s in meta['vt_symbols']}
 def get_contract(self,symbol):return self.contracts.get(symbol)
 def get_gateway(self,name):return self.gateway if name=='CTP' else None
 def subscribe(self,request,gateway_name):self.subscriptions.append((request.vt_symbol,gateway_name))


def transport(meta,now,*,positions=(),orders=(),trades=(),connection='bridge-connection'):
 identity=dict(account_key=ACCOUNT,material_release_id=RELEASE,execution_profile='weekly19-15w-r150k',service_generation='bridge-service',connection_generation=connection)
 account=dict(BrokerID='9999',AccountID='fixture-account',CurrencyID='CNY',TradingDay='20261102',Balance=150000.,Available=150000.,Deposit=0.,Withdraw=0.,CurrMargin=0.,PositionProfit=0.)
 native=dict(account=[account],positions=list(positions),orders=list(orders),trades=list(trades));rows=dict(_weekly19_capture_identity=identity)
 receipts={}
 for i,kind in enumerate(('account','positions','orders','trades')):
  reqid=301+i;sent=now-timedelta(seconds=20-i*3);done=sent+timedelta(seconds=1);source=native[kind] or [{}]
  callbacks=[dict(data=copy.deepcopy(data),error=dict(ErrorID=0),reqid=reqid,last=j==len(source)-1,received_at=done.isoformat(),connection_generation=identity['connection_generation']) for j,data in enumerate(source)]
  record=dict(identity,schema='weekly19.warm-native-query-epoch.v1',kind=kind,query_reqid=reqid,request_sent_at=sent.isoformat(),completed_at=done.isoformat(),request_return_code=0,request_ret=0,last_seen=True,error_rows=0,native_callbacks=callbacks,late_callback_blockers=[])
  receipts[kind]=record;rows[warm.EPOCH_KEYS[kind]]=dict(complete_reqid=reqid,active_reqid=None,weekly19_native_receipt=copy.deepcopy(record))
 rows['_weekly19_native_receipts']=receipts
 class TD:
  def __getattr__(self,name):
   if name.startswith('reqQry') or name=='connect':raise AssertionError('bridge must not start query/connection')
   raise AttributeError(name)
 main=Main(meta)
 return dict(rows=rows,td_api=TD(),main_engine=main,event_engine=main.event_engine,gateway=main.gateway,**{k:identity[k] for k in ('service_generation','connection_generation')})

class SessionBridgeTests(unittest.TestCase):
 def setUp(self):
  self.assertIsNotNone(bridge_module,'weekly19 session bridge missing')
  self.temp=tempfile.TemporaryDirectory(dir='/private/tmp');self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name).resolve();self.root.chmod(0o700);self.clock=Clock(NOW.replace(hour=21,minute=1))
  self.actor,self.bars=runtime_tests.RuntimeTests.ready(self)
  decision=self.actor.process_completed_day('2026-10-30',self.bars['2026-10-30'],receipt(),broker(),self.actor.confirmed_cash_state)
  self.bundle=dict(schema='weekly19.pipeline-state.v1',revision=0,account_key=ACCOUNT,material_release_id=RELEASE,funding=copy.deepcopy(self.actor.confirmed_cash_state),runtime=self.actor.export_state(),decision=decision,decision_state=self.actor.export_state())
  self.store=PipelineStateStore(self.root/'state.json',ACCOUNT,RELEASE);self.store.initialize(self.bundle)
  self.ledger=self.root/'execution.jsonl';self.ledger.write_bytes(b'');self.ledger.chmod(0o600)
  trusted={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (*provider.CAPTURE_SOURCE_FILES,warm.WARM_SOURCE)}
  self.authority=controller.Weekly19ControllerAuthority(controller._AUTHORITY_TOKEN,dict(account_fingerprint=ACCOUNT,material_release_id=RELEASE,target_cutoff_date='2026-10-30'),lambda at:None,self.clock.epoch_ns()+86_400_000_000_000,dict(expected_account_key=ACCOUNT,material_release_id=RELEASE,execution_profile='weekly19-15w-r150k',trusted_source_hashes=trusted),None)
  self.data=dict(metadata=self.actor.metadata,receipt=receipt(),calendar=self.actor.calendar)
  self.context=transport(self.actor.metadata,self.clock.at)
  self.cash_calls=[]
  def cash(state,snapshot,now):self.cash_calls.append(snapshot['account']['raw_sha256']);return copy.deepcopy(state)
  self.cash=cash
 def make(self,**changes):
  args=dict(runtime_actor=self.actor,bundle=self.bundle,data=self.data,authority=self.authority,state_store=self.store,clock=self.clock,private_root=self.root/'captures',execution_ledger_path=self.ledger,reconcile_cash=self.cash,session_provider=lambda row,transport_context,now:dict(is_open=True,trading_date='2026-11-02',session_id='fixture-night',starts_at=(now-timedelta(minutes=1)).isoformat(),ends_at=(now+timedelta(hours=1)).isoformat()),require_production_qualification=False)
  args.update(changes);bridge=bridge_module.Weekly19SessionBridge(**args);self.addCleanup(bridge.close);return bridge
 def test_forged_authority_cannot_create_bridge(self):
  with self.assertRaisesRegex(ValueError,'typed_controller_authority'):
   self.make(authority={'qualified':True})
 def test_native_before_account_is_only_private_raw_buffer_and_never_fake_applied(self):
  bridge=self.make();native=bridge.native_capture_factory(transport_context=self.context)
  packet=dict(BrokerID='9999',InvestorID='fixture-account',TradingDay='20261102',InstrumentID='rb2612',ExchangeID='SHFE',Direction='0',OrderSysID='SYS',FrontID=11,SessionID=22,OrderRef='33',CombOffsetFlag='0',VolumeTotalOriginal=1,VolumeTraded=0,OrderStatus='3')
  proof=native.capture_native('onRtnOrder',packet,observed_at=self.clock.at)
  self.assertEqual(proof['capture_reference']['admission_state'],'buffered')
  path=Path(proof['capture_reference']['path']);self.assertEqual(path.stat().st_mode&0o777,0o600)
  self.assertEqual(json.loads(path.read_text())['native'],packet)
  self.assertEqual(self.bundle['runtime'],self.store.read()['runtime'])
 def test_same_connection_query_admission_uses_actual_warm_reader_and_subscribes_fixed19(self):
  bridge=self.make();native=bridge.native_capture_factory(transport_context=self.context)
  result=native.admit_completed_startup(transport_context=self.context)
  self.assertFalse(result['source_qualified']);self.assertTrue(Path(result['warm_capture_reference']['path']).is_file())
  self.assertEqual(len(self.context['main_engine'].subscriptions),19)
  self.assertTrue(all(gateway=='CTP' for _,gateway in self.context['main_engine'].subscriptions))
  self.assertTrue(self.cash_calls)
  self.assertIs(bridge.runtime_actor,self.actor)
 def test_md_only_true_ctp_gateway_ingress_reaches_real_durable_journal(self):
  bridge=self.make();native=bridge.native_capture_factory(transport_context=self.context)
  native.admit_completed_startup(transport_context=self.context)
  def tick(gateway):return SimpleNamespace(gateway_name=gateway,vt_symbol=SYMBOL,symbol='rb2612',exchange='SHFE',datetime=self.clock.at,last_price=101.,bid_price_1=100.,ask_price_1=101.,bid_volume_1=10,ask_volume_1=10)
  self.context['gateway'].on_tick(tick('OTHER'));self.assertEqual(native.tick_pipeline.snapshot().last_ingress_sequence,0)
  self.context['gateway'].on_tick(tick('CTP'));self.assertTrue(native.tick_pipeline.wait_until_durable(1,timeout_seconds=2))
  inputs=bridge.publication_inputs_provider(runtime_actor=self.actor,bundle=self.store.read(),data=self.data,now=self.clock.at,transport_context=self.context)
  self.assertEqual(inputs['durable_through'].ingress_sequence,1)
  self.assertEqual(len(inputs['decision']['intents']),len([p for oid,p in self.actor.engine.order_intents.items() if oid not in self.actor.engine.order_terminal]))
  self.assertEqual(Path(inputs['journal_segment_path']).stat().st_mode&0o777,0o600)
 def test_actor_state_rolls_back_when_atomic_store_rejects(self):
  bridge=self.make();before=self.actor.export_state()
  with mock.patch.object(self.store,'transact',side_effect=OSError('fsync failure')):
   with self.assertRaises(OSError):bridge._commit(lambda section:setattr(self.actor,'open_block_reason','must-rollback'))
  self.assertEqual(before,self.actor.export_state())

 def test_post_replace_directory_fsync_failure_reloads_actual_bundle_and_never_returns_applied(self):
  import qmt_roll_weekly19_pipeline_state as state_module
  bridge=self.make();before=self.actor.export_state();fsync=os.fsync
  def fail_directory(fd):
   if stat.S_ISDIR(os.fstat(fd).st_mode):raise OSError('post-replace directory fsync failure')
   return fsync(fd)
  def advance(section):
   self.actor.open_block_reason='actual-post-replace-probe';self.actor.revision+=1;section['post_replace_probe']=True
  with mock.patch.object(state_module.os,'fsync',side_effect=fail_directory):
   with self.assertRaisesRegex(OSError,'post-replace directory fsync failure'):bridge._commit(advance)
  actual=self.store.read();self.assertNotEqual(before['state_sha256'],actual['runtime']['state_sha256'])
  self.assertEqual(self.actor.export_state(),actual['runtime']);self.assertEqual(bridge.last_bundle,actual)
  bridge._commit(lambda section:section.update(recovered_after_uncertain_durability=True))
  self.assertTrue(self.store.read()['session_bridge']['recovered_after_uncertain_durability'])

 def test_commit_failure_with_unreadable_actual_store_poison_owner_until_new_recovery(self):
  bridge=self.make()
  with mock.patch.object(self.store,'transact',side_effect=OSError('commit failure')),mock.patch.object(self.store,'read',side_effect=OSError('read failure')):
   with self.assertRaisesRegex(OSError,'commit failure'):
    bridge._commit(lambda section:section.update(never_success=True))
  with self.assertRaisesRegex(ValueError,'owner_poisoned_after_commit_failure'):
   bridge._commit(lambda section:section.update(forbidden=True))
  with self.assertRaisesRegex(ValueError,'owner_poisoned_after_commit_failure'):
   bridge.publication_inputs_provider(runtime_actor=self.actor,bundle=self.store.read(),data=self.data,now=self.clock.at,transport_context=self.context)

 def prepare_open_batch(self):
  import tests.test_weekly19_broker_evidence as source_tests
  import qmt_roll_official_live_execution_ledger as ledger_module
  plan=next(p for p in self.actor.engine.order_intents.values() if p['offset']=='open')
  with mock.patch.multiple(source_tests,ACCOUNT=ACCOUNT,RELEASE=RELEASE):rows=source_tests.BrokerEvidenceTest('runTest').batch_ledger()
  def bind(value):
   if isinstance(value,list):return [bind(v) for v in value]
   if not isinstance(value,dict):return value
   out={}
   for key,item in value.items():
    if key=='signal_identity':out[key]=copy.deepcopy(plan['signal_identity'])
    elif key=='planned_intent_id':out[key]=plan['intent_id']
    elif key=='signal_order_id':out[key]=plan['signal_order_id']
    elif key=='vt_symbol':out[key]=SYMBOL
    elif key in ('direction','planned_direction'):out[key]='long'
    elif key in ('offset','planned_offset','broker_offset'):out[key]='open'
    elif key=='child_order_offset':out[key]='开'
    elif key=='native_offset_flag':out[key]='0'
    elif key in ('account_key','account_fingerprint'):out[key]=ACCOUNT
    elif key=='material_release_id':out[key]=RELEASE
    elif key=='source':out[key]='weekly19_pending_order'
    elif key=='target_date':out[key]=plan['target_date']
    else:out[key]=bind(item)
   if 'expected_children' in out:out['expected_children_sha256']=digest(out['expected_children'])
   return out
  from qmt_roll_weekly19_pipeline_state import digest
  rows=bind(rows);batchid=digest(dict(target_date=plan['target_date'],slot_type='send_order',usage_before=0,base_events=rows[0]['api_slot_batch_children']))[:24]
  for row in rows:row['api_slot_batch_id']=batchid;row['record_checksum']=ledger_module._record_checksum(row)
  self.ledger.write_text(''.join(json.dumps(row)+'\n' for row in rows));self.ledger.chmod(0o600)
  order=dict(BrokerID='9999',InvestorID='fixture-account',TradingDay='20261102',InstrumentID='rb2612',ExchangeID='SHFE',Direction='0',
      CombOffsetFlag='0',LimitPrice=101.,VolumeTotalOriginal=1,VolumeTraded=0,OrderStatus='3',FrontID=11,SessionID=22,OrderRef='33',
      OrderSysID='SYS-1',InsertDate='20261030',InsertTime='20:58:00')
  other=dict(order,OrderRef='34',OrderSysID='SYS-2')
  self.context=transport(self.actor.metadata,self.clock.at,orders=[order,other])
  return plan,order

 def test_true_order_ahead_of_trade_is_durable_deferred_across_restart_then_exactly_resolved(self):
  from qmt_roll_official_live_execution_ledger import _record_checksum
  import run_qmt_roll_stage931_official_live_ctp_submit_adapter as runner
  plan,order=self.prepare_open_batch();bridge=self.make();native=bridge.native_capture_factory(transport_context=self.context)
  native.admit_completed_startup(transport_context=self.context)
  filled=dict(order,VolumeTraded=1,OrderStatus='0')
  proof=native.capture_native('onRtnOrder',filled,observed_at=self.clock.at)
  result=bridge.event_consumer('order',dict(weekly19_native_proof=proof),dict(planned_intent_id=plan['intent_id']),runtime_actor=self.actor)
  self.assertEqual(result['status'],'deferred_durable');identity=result['durable_deferred_id']
  runner.weekly19_reconcile_deferred_events(self.context['rows'],result)
  self.assertTrue(runner.weekly19_deferred_event_blockers(self.context['rows']))
  saved=self.store.read();self.assertIn(identity,saved['session_bridge']['deferred']);self.assertEqual(self.actor.strategy.get_pos(SYMBOL),0)
  bridge.close()
  from tests.test_weekly19_runtime import build
  saved_snapshot=runtime._decode(saved['runtime']['runtime'])['broker_snapshot']
  self.actor,_=build(saved_snapshot,saved['runtime'],saved['funding'],now=self.clock.at)
  self.bundle=saved;self.data=dict(metadata=self.actor.metadata,receipt=receipt(),calendar=self.actor.calendar)
  self.context=transport(self.actor.metadata,self.clock.at,orders=[order,dict(order,OrderRef='34',OrderSysID='SYS-2')])
  restarted=self.make();second=restarted.native_capture_factory(transport_context=self.context)
  second.admit_completed_startup(transport_context=self.context)
  self.assertIn(identity,self.context['rows']['_weekly19_deferred_broker_events'])
  proof=second.capture_native('onRtnOrder',filled,observed_at=self.clock.at)
  result=restarted.event_consumer('order',dict(weekly19_native_proof=proof),dict(planned_intent_id=plan['intent_id']),runtime_actor=self.actor)
  self.assertEqual(result['status'],'deferred_durable')
  trade=dict(BrokerID='9999',InvestorID='fixture-account',TradingDay='20261102',InstrumentID='rb2612',ExchangeID='SHFE',Direction='0',
      OffsetFlag='0',OrderSysID='SYS-1',TradeID='ACTUAL-BRIDGE-1',TradeDate='20261030',TradeTime='21:01:00',Volume=1,Price=101.5)
  proof=second.capture_native('onRtnTrade',trade,observed_at=self.clock.at)
  before_actor=self.actor.export_state();before_file=self.store.path.read_bytes()
  with mock.patch.object(self.store,'_write',side_effect=OSError('fixture fsync failure')):
   with self.assertRaises(OSError):
    restarted.event_consumer('trade',dict(weekly19_native_proof=proof),dict(planned_intent_id=plan['intent_id']),runtime_actor=self.actor)
  self.assertEqual(before_actor,self.actor.export_state());self.assertEqual(before_file,self.store.path.read_bytes())
  result=restarted.event_consumer('trade',dict(weekly19_native_proof=proof),dict(planned_intent_id=plan['intent_id']),runtime_actor=self.actor)
  self.assertEqual(result['status'],'applied');self.assertIn(identity,result['resolved_deferred_ids'])
  runner.weekly19_reconcile_deferred_events(self.context['rows'],result)
  self.assertFalse(runner.weekly19_deferred_event_blockers(self.context['rows']))
  self.assertEqual(self.actor.strategy.get_pos(SYMBOL),1);self.assertEqual(self.store.read()['session_bridge']['deferred'],{})
  parent=dict(plan,intent_id='W19EXEC-delivery',planned_intent_id=plan['intent_id'],planned_volume=2)
  dynamic=dict(parent,planned_volume=1)
  lifeproof=restarted._actual_fill_lifecycle(dynamic,dict(weekly19_immutable_parent_intent=parent,weekly19_current_physical_child=dict(volume=1)))
  self.assertEqual(lifeproof['business_filled_volume'],1);self.assertEqual(lifeproof['business_remaining_volume'],plan['planned_volume']-1)
  self.assertEqual((lifeproof['delivery_approved_volume'],lifeproof['delivery_filled_volume'],lifeproof['delivery_remaining_volume']),(2,1,1))
  self.assertEqual(len(lifeproof['delivery_trade_ids']),1);self.assertEqual(lifeproof['durable_state_sha256'],self.actor.export_state()['state_sha256'])
  with self.assertRaisesRegex(ValueError,'immutable_delivery_parent_required'):
   restarted._actual_fill_lifecycle(dynamic,dict(weekly19_current_physical_child=dict(volume=1)))
  again=restarted.event_consumer('trade',dict(weekly19_native_proof=proof),dict(planned_intent_id=plan['intent_id']),runtime_actor=self.actor)
  self.assertEqual(again['status'],'duplicate');self.assertEqual(self.actor.strategy.get_pos(SYMBOL),1)
  # The same signed four-query source still says flat. A genuine native fill
  # must stop the next child until a real completed query epoch reconciles it.
  tick=SimpleNamespace(gateway_name='CTP',vt_symbol=SYMBOL,symbol='rb2612',exchange='SHFE',datetime=self.clock.at,last_price=101.,bid_price_1=100.,ask_price_1=101.,bid_volume_1=10,ask_volume_1=10)
  self.context['gateway'].on_tick(tick);self.assertTrue(second.tick_pipeline.wait_until_durable(1,timeout_seconds=2))
  before_actor=self.actor.export_state();before_file=self.store.path.read_bytes()
  with self.assertRaisesRegex(ValueError,'requires_source_reconciliation:broker_strategy_position_mismatch'):
   restarted.fresh_context_provider(dynamic,transport_context=dict(self.context,weekly19_immutable_parent_intent=parent,weekly19_current_physical_child=dict(volume=1)),runtime_actor=self.actor)
  self.assertEqual(before_actor,self.actor.export_state());self.assertEqual(before_file,self.store.path.read_bytes())

 def test_current_risk_context_uses_real_durable_quote_same_warm_snapshot_and_typed_ledger(self):
  bridge=self.make();native=bridge.native_capture_factory(transport_context=self.context)
  native.admit_completed_startup(transport_context=self.context)
  tick=SimpleNamespace(gateway_name='CTP',vt_symbol=SYMBOL,symbol='rb2612',exchange='SHFE',datetime=self.clock.at,last_price=101.,bid_price_1=100.,ask_price_1=101.,bid_volume_1=10,ask_volume_1=10)
  self.context['gateway'].on_tick(tick);self.assertTrue(native.tick_pipeline.wait_until_durable(1,timeout_seconds=2))
  plan=next(p for p in self.actor.engine.order_intents.values() if p['offset']=='open')
  result=bridge.fresh_context_provider(plan,transport_context=self.context,runtime_actor=self.actor)
  self.assertIsInstance(result['execution_ledger_rows'],provider._VerifiedExecutionBindings)
  self.assertEqual(result['quote']['source_ingress_sequence'],1)
  self.assertEqual(result['open_risk_proof']['quote_sha256'],__import__('qmt_roll_weekly19_funding')._hash(result['quote']))
  self.assertEqual(result['open_risk_proof']['account_raw_sha256'],result['broker_snapshot']['account']['raw_sha256'])
  self.assertEqual(result['metadata']['margin_rate_source'],'frozen_model_estimate_not_broker_receipt')
  self.assertTrue(result['metadata']['final_broker_capacity_gate_required'])
  self.assertEqual(result['cash_source_blocker'],'day_roll_requires_reconciliation')
 def test_missing_startup_ledger_still_retains_raw_packet_without_qualification(self):
  bridge=self.make();native=bridge.native_capture_factory(transport_context=self.context);self.ledger.unlink()
  packet=dict(BrokerID='9999',InvestorID='fixture-account',TradingDay='20261102',InstrumentID='rb2612',ExchangeID='SHFE',Direction='0',OrderSysID='SYS',FrontID=11,SessionID=22,OrderRef='33',CombOffsetFlag='0',VolumeTotalOriginal=1,VolumeTraded=0,OrderStatus='3')
  proof=native.capture_native('onRtnOrder',packet,observed_at=self.clock.at)
  body=json.loads(Path(proof['capture_reference']['path']).read_text())
  self.assertEqual(body['native'],packet);self.assertIsNone(body['ledger_snapshot']);self.assertTrue(body['ledger_source_blocker'])
  self.assertEqual(proof['capture_reference']['admission_state'],'buffered')

 def test_startup_buffer_absorbs_original_native_packets_only_after_real_account_epoch(self):
  plan,order=self.prepare_open_batch();bridge=self.make();native=bridge.native_capture_factory(transport_context=self.context)
  trade=dict(BrokerID='9999',InvestorID='fixture-account',TradingDay='20261102',InstrumentID='rb2612',ExchangeID='SHFE',Direction='0',OffsetFlag='0',OrderSysID='SYS-1',TradeID='STARTUP-REAL-1',TradeDate='20261030',TradeTime='21:01:00',Volume=1,Price=101.5)
  # Trade-first is preserved as received; later real Order provides its native
  # OrderSysID mapping. No account/position envelope is fabricated meanwhile.
  first=native.capture_native('onRtnTrade',trade,observed_at=self.clock.at)
  native.capture_native('onRtnOrder',order,observed_at=self.clock.at)
  self.assertEqual(self.actor.strategy.get_pos(SYMBOL),0)
  self.assertEqual(first['capture_reference']['admission_state'],'buffered')
  result=native.admit_completed_startup(transport_context=self.context)
  self.assertFalse(result['source_qualified']);self.assertEqual(self.actor.strategy.get_pos(SYMBOL),1)
  persisted=runtime._decode(self.store.read()['runtime']['runtime'])
  self.assertEqual(len(persisted['fills']),1)
  self.assertTrue(any(row['source']['kind']=='native_startup_recovery' for row in self.store.read()['session_bridge']['event_sources'].values()))

 def test_factory_shares_service_actor_lock_and_never_starts_transport(self):
  from qmt_roll_official_execution_profile import WEEKLY19_15W_R150K_PROFILE as profile
  args=SimpleNamespace(execution_profile=profile.profile_key,runtime_profile='production-live',order_scope='live',stage179_runtime_root=str(self.root/'service'),target_date='2026-10-30')
  service,bridge=bridge_module.build_weekly19_session_service(args,runtime_actor=self.actor,bundle=self.bundle,data=self.data,
      authority=self.authority,state_store=self.store,clock=self.clock,private_root=self.root/'factory',execution_ledger_path=self.ledger,
      reconcile_cash=self.cash,session_provider=lambda row,transport_context,now:{},require_production_qualification=False)
  self.addCleanup(bridge.close)
  self.assertIs(service.actor_lock,bridge.actor_lock);self.assertIs(service.runtime_actor,self.actor)
  self.assertIsNone(service._thread)

 def test_actual_clean_md_tail_commit_allows_typed_feed_rollover_in_real_spool(self):
  from qmt_roll_official_live_intent_spool import open_spool,read_detector_cursor,DetectorFeedRolloverEvidence
  from qmt_roll_official_live_intent_spool import commit_detector_batch
  bridge=self.make()
  class Service:
   actor_lock=threading.RLock()
   spool_path=self.root/'md-spool.sqlite3'
   def bind_actor(service,actor):service.runtime_actor=actor
  bridge.bind_service(Service())
  native=bridge.native_capture_factory(transport_context=self.context);native.admit_completed_startup(transport_context=self.context)
  def emit(context):
   context['gateway'].on_tick(SimpleNamespace(gateway_name='CTP',vt_symbol=SYMBOL,symbol='rb2612',exchange='SHFE',datetime=self.clock.at,last_price=101.,bid_price_1=100.,ask_price_1=101.,bid_volume_1=10,ask_volume_1=10))
  emit(self.context);self.assertTrue(native.tick_pipeline.wait_until_durable(1,timeout_seconds=2));first_feed=native.feed
  native.close()
  connection=open_spool(bridge.service.spool_path)
  try:old=read_detector_cursor(connection,consumer_id='weekly19')
  finally:connection.close()
  self.assertEqual(old.feed_session_id,first_feed)
  self.context=transport(self.actor.metadata,self.clock.at,connection='bridge-connection-2')
  second=bridge.native_capture_factory(transport_context=self.context);second.admit_completed_startup(transport_context=self.context)
  emit(self.context);self.assertTrue(second.tick_pipeline.wait_until_durable(1,timeout_seconds=2))
  inputs=bridge.publication_inputs_provider(runtime_actor=self.actor,bundle=self.store.read(),data=self.data,now=self.clock.at,transport_context=self.context)
  proof=inputs['feed_rollover_evidence'];self.assertIsInstance(proof,DetectorFeedRolloverEvidence)
  self.assertTrue(proof.previous_clean_shutdown);self.assertEqual(proof.previous_cursor,old)
  self.assertNotEqual(second.feed,first_feed)
  connection=open_spool(bridge.service.spool_path)
  try:
   commit_detector_batch(connection,consumer_id='weekly19',expected_cursor=old,next_cursor=inputs['durable_through'],intents=[],now_epoch_ns=self.clock.epoch_ns(),now_monotonic_ns=self.clock.monotonic_ns(),clock_domain_id=self.clock.clock_domain_id(),feed_rollover_evidence=proof)
   self.assertEqual(read_detector_cursor(connection,consumer_id='weekly19').feed_session_id,second.feed)
  finally:connection.close()
 def test_unclean_real_md_shutdown_cannot_be_relabelled_clean_new_feed(self):
  bridge=self.make();native=bridge.native_capture_factory(transport_context=self.context)
  native.tick_pipeline.latch_capture_exception(RuntimeError('fixture actual capture fault'))
  with self.assertRaisesRegex(ValueError,'md_shutdown_not_durable'):native.close()
  with self.assertRaisesRegex(ValueError,'previous_md_not_clean'):
   bridge.native_capture_factory(transport_context=transport(self.actor.metadata,self.clock.at,connection='new-connection'))

 def test_complete_public_service_dry_integration_uses_actor_real_journal_store_and_spool_conditionally(self):
  """Source authority is a literal fixture; this does not qualify production."""
  import qmt_roll_weekly19_funding as funds_module
  from qmt_roll_official_execution_profile import WEEKLY19_15W_R150K_PROFILE as profile
  from qmt_roll_weekly19_execution_service import Weekly19ExecutionService
  from qmt_roll_official_live_submit_authorization import read_submit_authorization
  from qmt_roll_official_live_intent_spool import open_spool
  # A conditional cash-neutral statement explicitly binds the Friday closing
  # callback and Monday opening callback. It is not a real accepted statement.
  closing=broker(balance='150000.00',now=NOW+timedelta(minutes=2))
  def cash(state,snapshot,now):
   if state['cashflow_checkpoint']['trading_day']=='2026-10-30':
    proof=envelope(dict(schema='weekly19.cashflow-day-close.v1',source_kind='broker_cashflow_day_close',account_key=ACCOUNT,
      material_release_id=RELEASE,statement_id='CONDITIONAL-FIXTURE-NOT-BROKER',trading_day='2026-10-30',next_trading_day='2026-11-02',
      closed_at=(NOW+timedelta(minutes=5)).isoformat(),closing_account_sha256=closing['account']['raw_sha256'],Deposit='0.00',Withdraw='0.00',cashflows_complete=True))
    return funds_module.reconcile_trading_day(state,closing['account'],snapshot['account'],now,continuity_receipt=proof)
   return copy.deepcopy(state)
  source=dict(self.authority.bindings,execution_profile=profile.profile_key,official_version=profile.official_version,ruleset_version=profile.ruleset_version,
      source_commit='b'*40,production_source_commit='b'*40,material_source_commit='a'*40,manifest_sha256='b'*64,qualification_sha256='c'*64,
      activation_receipt_sha256='d'*64,daily_receipt_sha256='e'*64,source_data_receipt_sha256=funds_module._hash(self.data['receipt']),
      decision_origin_state_sha256=self.bundle['decision_state']['state_sha256'])
  authority=controller.Weekly19ControllerAuthority(controller._AUTHORITY_TOKEN,source,lambda at:None,self.authority.expires_epoch_ns,self.authority.broker_policy,None)
  bridge=self.make(authority=authority,reconcile_cash=cash);ready=threading.Event();errors=[]
  args=SimpleNamespace(execution_profile=profile.profile_key,runtime_profile='production-live',order_scope='live',stage179_runtime_root=str(self.root/'dry-service'),target_date='2026-10-30')
  class Session:
   def connection_ready(session):return True
   def transport_context(session):return self.context
   def transport_blockers(session):return []
   def readiness_lease(session,**kw):return dict(runtime_profile='production-live',service_kind='warm_live_executor',official_version=profile.official_version,
      capital=150000,service_generation='bridge-service',connection_generation='bridge-connection',issued_epoch_ns=self.clock.epoch_ns(),expires_epoch_ns=self.clock.epoch_ns()+10_000_000_000)
   def refresh_weekly19_context(session):raise AssertionError('fresh admitted epochs need no extra query')
  def runner(args,**kw):
   native=kw['weekly19_native_capture_factory'](transport_context=self.context)
   native.admit_completed_startup(transport_context=self.context)
   self.context['gateway'].on_tick(SimpleNamespace(gateway_name='CTP',vt_symbol=SYMBOL,symbol='rb2612',exchange='SHFE',datetime=self.clock.at,last_price=101.,bid_price_1=100.,ask_price_1=101.,bid_volume_1=10,ask_volume_1=10))
   native.tick_pipeline.wait_until_durable(1,timeout_seconds=2);kw['backend_observer'](Session());ready.set()
   while not kw['stop_requested']():ready.wait(.01);__import__('time').sleep(.005)
   native.close();return 0
  service=Weekly19ExecutionService(args,authority_provider=bridge.authority_provider,fresh_context_provider=bridge.fresh_context_provider,
      event_consumer=bridge.event_consumer,native_capture_factory=bridge.native_capture_factory,publication_inputs_provider=bridge.publication_inputs_provider,clock=self.clock,runner=runner)
  bridge.bind_service(service);self.addCleanup(lambda:service.stop(timeout=3));service.start();self.assertTrue(ready.wait(3))
  original_ids=set(p['intent_id'] for p in self.actor.engine.order_intents.values())
  # Only the production source-qualification validator is bypassed for this
  # offline capability fixture. All cash/model/journal/spool/controller checks run.
  with mock.patch.object(controller,'_validate_fresh_source_proof',return_value=None):
   result=service.publish(runtime=self.actor,bundle=self.store.read(),data=self.data)
  self.assertEqual(result['status'],'published',result);self.assertFalse(result['production_qualified'])
  self.assertEqual(original_ids,set(p['intent_id'] for p in self.actor.engine.order_intents.values()))
  self.assertEqual(self.store.read()['funding']['cashflow_checkpoint']['trading_day'],'2026-11-02')
  authorization=read_submit_authorization(service.authorization_path)
  self.assertEqual(authorization['authorization_lane'],'slow_controller')
  connection=open_spool(service.spool_path)
  try:self.assertEqual(connection.execute('select count(*) from intents').fetchone()[0],1)
  finally:connection.close()
  self.assertEqual(service.stop(timeout=3)['status'],'stopped')

 def test_production_default_needs_preloaded_capability_before_actor_clock_change(self):
  before=self.actor.clock
  with self.assertRaisesRegex(ValueError,'preloaded_capture_authority'):
   self.make(require_production_qualification=True)
  self.assertIs(before,self.actor.clock)
 def test_factory_initial_store_write_failure_restores_gateway_and_stops_md_writer(self):
  bridge=self.make();original=self.context['gateway'].on_tick;created=[]
  pipeline_type=bridge_module.TickStreamPipeline
  def record(**kw):
   result=pipeline_type(**kw);created.append(result);return result
  with mock.patch.object(bridge_module,'TickStreamPipeline',side_effect=record),mock.patch.object(self.store,'_write',side_effect=OSError('fixture owner fsync failure')):
   with self.assertRaises(OSError):bridge.native_capture_factory(transport_context=self.context)
  self.assertIsNone(bridge.native);self.assertEqual(self.context['gateway'].on_tick,original)
  self.assertTrue(created[0].wait_until_writer_stops(timeout_seconds=1))
