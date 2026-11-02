"""Offline native callback/query fixtures, never a real CTP qualification."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'examples/portfolio_backtesting'))
import run_qmt_roll_stage931_official_live_ctp_submit_adapter as execution

NATIVE_ORDER=dict(BrokerID='9999',InvestorID='test',TradingDay='20261102',InstrumentID='rb2701',ExchangeID='SHFE',
 Direction='1',OrderSysID='SYS1',FrontID=2,SessionID=3,OrderRef='4',CombOffsetFlag='3',
 VolumeTotalOriginal=2,VolumeTraded=0,OrderStatus='3',OrderSubmitStatus='3')

class FakeTd:
 def __init__(self,events): self.events=events
 def onRspSettlementInfoConfirm(self,*a): pass
 def onRspQryTradingAccount(self,*a): pass
 def onRspQryInvestorPosition(self,*a): pass
 def onRspQryOrder(self,*a): pass
 def onRspQryTrade(self,*a): pass
 def reqQryOrder(self,data,reqid):
  self.onRspQryOrder(dict(NATIVE_ORDER),{},reqid,True)
  return 0
 def onRtnOrder(self,data):
  self.events.append('normalized')
  obj=SimpleNamespace(vt_symbol='rb2701.SHFE',symbol='rb2701',exchange='SHFE',direction='空',offset='平今',
     orderid='2_3_4',vt_orderid='CTP.2_3_4',volume=2,traded=0,status='未成交')
  execution.attach_weekly19_native_proof('order',obj)
  self.obj=obj
 def onRtnTrade(self,data): self.events.append('trade')

class Weekly19NativeExecutionTest(unittest.TestCase):
 def identity(self):
  return dict(account_key='a'*64,material_release_id='release',execution_profile='weekly19-15w-r150k',
    service_generation='service',connection_generation='conn')
 def test_native_is_captured_before_normalized_and_hook_restored(self):
  events=[];td=FakeTd(events);rows={};original=FakeTd.onRtnOrder
  def capture(method,native,*,observed_at):
   events.append('durable_native')
   self.assertEqual(native,NATIVE_ORDER)
   return dict(path='/private/tmp/literal-fixture-native.json',sha256='b'*64)
  with execution._instrument_ctp_readiness_callbacks(FakeTd,rows,weekly19_native_capture=capture):
   td.onRtnOrder(dict(NATIVE_ORDER))
  self.assertIs(FakeTd.onRtnOrder,original)
  self.assertEqual(events,['durable_native','normalized'])
  row=execution._object_to_row(td.obj)
  self.assertEqual(row['broker_offset'],'closetoday')
  self.assertEqual(row['native_offset_flag'],'3')
  self.assertEqual(row['weekly19_native_proof']['source_callback'],'onRtnOrder')
 def test_failed_native_durability_keeps_actual_gateway_fact_and_blocks_new_sends(self):
  events=[];td=FakeTd(events);rows={}
  def fail(*args,**kwargs): raise OSError('fixture disk unavailable')
  with execution._instrument_ctp_readiness_callbacks(FakeTd,rows,weekly19_native_capture=fail):
   td.onRtnOrder(dict(NATIVE_ORDER))
  self.assertIn('normalized',events)
  self.assertTrue(rows['_weekly19_native_capture_blockers'])
  self.assertEqual(rows['_weekly19_native_capture_failed_packets'][0]['native'],NATIVE_ORDER)
 def test_query_receipt_freezes_raw_fields_before_pending_clear(self):
  td=FakeTd([]);rows={'_weekly19_capture_identity':self.identity(),
   '_order_query_epoch':dict(active_reqid=7,complete_reqid=None,pending_callbacks=[])}
  with execution._instrument_ctp_readiness_callbacks(FakeTd,rows):
   self.assertEqual(td.reqQryOrder({'BrokerID':'9999','InvestorID':'test'},7),0)
  receipt=rows['_weekly19_native_receipts']['orders']
  self.assertEqual(receipt['native_callbacks'][0]['data'],NATIVE_ORDER)
  self.assertEqual(receipt['request_return_code'],0)
  self.assertTrue(receipt['last_seen'])
  self.assertEqual(receipt['native_callbacks'][0]['reqid'],7)
  self.assertEqual(rows['_order_query_epoch']['pending_callbacks'],[])
  self.assertIn('+',receipt['request_sent_at'])
  self.assertIn('+',receipt['completed_at'])
 def test_late_old_native_instance_is_not_admitted_as_current_generation(self):
  events=[];old=FakeTd(events);active=FakeTd([]);captures=[]
  rows={'_weekly19_active_td_api':active,'_weekly19_capture_identity':self.identity()}
  with execution._instrument_ctp_readiness_callbacks(FakeTd,rows,
      weekly19_native_capture=lambda *a,**kw:captures.append(a)or dict(path='/fixture',sha256='a'*64)):
   old.onRtnOrder(dict(NATIVE_ORDER))
  self.assertEqual(captures,[])
  self.assertIn('normalized',events)
  self.assertTrue(rows['_weekly19_native_capture_blockers'])
  self.assertNotIn('weekly19_native_proof',execution._object_to_row(old.obj))
 def test_late_old_query_instance_cannot_replace_current_frozen_receipt(self):
  active=FakeTd([]);old=FakeTd([])
  rows={'_weekly19_active_td_api':active,'_weekly19_capture_identity':self.identity(),
    '_order_query_epoch':dict(active_reqid=7,complete_reqid=None,pending_callbacks=[])}
  with execution._instrument_ctp_readiness_callbacks(FakeTd,rows):
   old.onRspQryOrder(dict(NATIVE_ORDER),{},7,True)
  self.assertNotIn('orders',rows.get('_weekly19_native_receipts',{}))
  self.assertIsNone(rows['_order_query_epoch']['complete_reqid'])
  self.assertTrue(rows['_weekly19_native_capture_blockers'])

if __name__=='__main__':unittest.main()

class Weekly19ConnectionGenerationTest(unittest.TestCase):
 def test_actual_connection_generation_exists_before_native_startup(self):
  seen=[]
  def startup():
   if not seen or not seen[-1]: raise AssertionError('native startup lacks actual connection generation')
   return {'ready':True}
  obj=execution.CtpExecutionSession(runtime=SimpleNamespace(),service_generation='s',official_version='v',capital=150000,
   readiness_ttl_seconds=3,connect_startup_bundle=startup,disconnect_transport=lambda:None,
   fresh_bundle=lambda *a:None,reserve_api_slot=lambda *a:'',send_order=lambda *a:None,
   connection_generation_observer=seen.append)
  obj.connect();self.assertEqual(obj.connection_generation,seen[-1]);obj.close();self.assertEqual(seen[-1],'')

class Weekly19PhysicalBindingTest(unittest.TestCase):
 def test_actual_vnpy_native_close_enums_remain_business_close_in_cas_and_native_specific_in_proof(self):
  import qmt_roll_official_live_execution_ledger as ledger
  for offset in (execution.Offset.CLOSETODAY,execution.Offset.CLOSEYESTERDAY):
   self.assertEqual(ledger._normalize_offset_text(offset.value),'close')
   self.assertEqual(execution._normalize_offset_text(offset.value),'close')
   self.assertIs(execution._offset_from_payload(offset.value),offset)
  self.assertEqual(ledger._normalize_offset_text('unexpected close'),'unexpected close')
 def test_real_vnpy_direction_values_are_accepted_by_open_date_seal_without_rewriting_raw(self):
  import qmt_roll_official_live_broker_open_date_seal as seal
  for enum,value in ((execution.Direction.LONG,'long'),(execution.Direction.SHORT,'short')):
   self.assertEqual(seal._direction(enum.value),value)
  self.assertIsNone(seal._open(execution.Offset.OPEN.value))
  with self.assertRaises(ValueError):seal._direction('unexpected direction')
  with self.assertRaises(ValueError):seal._open('unexpected offset')
 def test_generic_fill_ledger_retains_parent_direction_and_physical_child_cap(self):
  row=dict(source='weekly19_risk_reduce',intent_kind='risk_close',direction='short',offset='close',
    planned_volume=2,intent_id='delivery',planned_intent_id='planned',material_release_id='release')
  request=SimpleNamespace(volume=1,direction=SimpleNamespace(value='空'),offset=SimpleNamespace(value='平今'))
  base=execution._stage179_warm_callback_base(dict(row=row,request=request),dict(direction='空',offset='平今',
    broker_offset='closetoday',native_offset_flag='3'))
  self.assertEqual(base['planned_direction'],'short')
  self.assertEqual(base['planned_offset'],'close')
  self.assertEqual(base['broker_order_volume'],1)
  self.assertEqual(base['planned_volume'],2)
  self.assertEqual(base['broker_offset'],'closetoday')

class Weekly19TransportContextTest(unittest.TestCase):
 def test_live_session_exposes_existing_transport_context_without_query(self):
  context=dict(connection_generation='conn',rows={'frozen':True})
  session=execution.CtpExecutionSession(runtime=SimpleNamespace(),service_generation='s',official_version='v',capital=150000,
    readiness_ttl_seconds=3,connect_startup_bundle=lambda:{'ready':True},disconnect_transport=lambda:None,
    fresh_bundle=lambda *a:None,reserve_api_slot=lambda *a:'',send_order=lambda *a:None,
    transport_context_provider=lambda:context)
  self.assertIs(session.transport_context(),context)

class Weekly19DeferredBrokerEventTest(unittest.TestCase):
 def test_deferred_is_durable_but_never_applied_and_only_exact_resolved_ids_clear(self):
  rows={};receipt=dict(status='deferred_durable',state_sha256='a'*64,durable_deferred_id='native-order-1')
  errors=execution.weekly19_broker_event_blockers('order',{}, {},lambda *a:receipt,
   receipt_observer=lambda item:execution.weekly19_reconcile_deferred_events(rows,item))
  self.assertEqual(errors,[])
  self.assertTrue(execution.weekly19_deferred_event_blockers(rows))
  execution.weekly19_reconcile_deferred_events(rows,dict(status='applied',state_sha256='b'*64,resolved_deferred_ids=['other']))
  self.assertTrue(execution.weekly19_deferred_event_blockers(rows))
  execution.weekly19_reconcile_deferred_events(rows,dict(status='duplicate',state_sha256='b'*64,resolved_deferred_ids=['native-order-1']))
  self.assertEqual(execution.weekly19_deferred_event_blockers(rows),[])
 def test_missing_durable_deferred_proof_cannot_be_admitted(self):
  for receipt in (dict(status='deferred_durable',state_sha256='a'*64),
                  dict(status='deferred_durable',state_sha256='invalid',durable_deferred_id='id')):
   self.assertTrue(execution.weekly19_broker_event_blockers('order',{}, {},lambda *a:receipt))
 def test_query_replay_requires_real_source_admission_and_durable_state_receipt(self):
  rows={};execution.weekly19_reconcile_deferred_events(rows,dict(status='deferred_durable',state_sha256='a'*64,durable_deferred_id='id'))
  with self.assertRaises(ValueError):
   execution.weekly19_reconcile_deferred_events(rows,dict(source_qualified=True,resolved_deferred_ids=['id']),query_admission=True)
  self.assertTrue(execution.weekly19_deferred_event_blockers(rows))
  execution.weekly19_reconcile_deferred_events(rows,dict(source_qualified=True,state_sha256='b'*64,
   warm_capture_reference=dict(path='/fixture',sha256='c'*64),resolved_deferred_ids=['id']),query_admission=True)
  self.assertEqual(execution.weekly19_deferred_event_blockers(rows),[])

class Weekly19BatchManifestTest(unittest.TestCase):
 def test_actual_split_requests_make_complete_preinsert_child_manifest(self):
  row=dict(intent_id='delivery',planned_intent_id='planned',signal_identity={'intent_id':'planned'},
   trading_date='2026-11-02',vt_symbol='rb2701.SHFE',direction='short',offset='close',planned_volume=2)
  requests=[execution.OrderRequest(symbol='rb2701',exchange=execution.Exchange.SHFE,direction=execution.Direction.SHORT,
    type=execution.OrderType.LIMIT,volume=1,price=4000,offset=offset)for offset in (execution.Offset.CLOSETODAY,execution.Offset.CLOSEYESTERDAY)]
  manifest=execution.weekly19_physical_batch_manifest(row,requests,fingerprint='fp',lease_token='lease',payload_sha256='a'*64,
   service_generation='s',connection_generation='c')
  self.assertEqual(manifest['approved_parent_volume'],2)
  self.assertEqual(len(manifest['expected_children']),2)
  self.assertEqual([x['broker_offset']for x in manifest['expected_children']],['closetoday','closeyesterday'])
  self.assertTrue(all('broker_order_id'not in x for x in manifest['expected_children']))
  self.assertEqual(manifest['expected_children_sha256'],execution._canonical_evidence_sha256(manifest['expected_children']))
 def test_periodic_refresh_uses_existing_session_callback(self):
  session=execution.CtpExecutionSession(runtime=SimpleNamespace(),service_generation='s',official_version='v',capital=150000,
    readiness_ttl_seconds=3,connect_startup_bundle=lambda:{'ready':True},disconnect_transport=lambda:None,
    fresh_bundle=lambda *a:None,reserve_api_slot=lambda *a:'',send_order=lambda *a:None,
    refresh_context_provider=lambda:dict(ready=True,source='existing_completed_queries'))
  self.assertEqual(session.refresh_weekly19_context()['source'],'existing_completed_queries')

 def build_fixture(self,directory):
  paths=execution.ExecutorServicePaths.for_spool(spool_path=Path(directory)/'spool.sqlite3',ledger_path=Path(directory)/'ledger.ndjson')
  session=execution._build_stage179_warm_ctp_session(SimpleNamespace(target_date='2026-10-30',
   execution_profile='weekly19-15w-r150k',connect_wait_seconds=3),SimpleNamespace(output_root=Path(directory)),paths,
   weekly19_context_provider=lambda *a,**kw:None,weekly19_event_consumer=lambda *a:None,
   weekly19_native_capture_factory=lambda **kw:None)
  state=next(cell.cell_contents for cell in session._reserve_api_slot.__closure__ if isinstance(cell.cell_contents,dict)
   and 'intent_contexts'in cell.cell_contents)
  return session,state,paths

 def test_actual_warm_transport_exposes_same_connection_md_objects_without_a_new_gateway(self):
  with tempfile.TemporaryDirectory()as directory:
   session,state,_=self.build_fixture(directory)
   objects={name:object()for name in ('main_engine','event_engine','gateway','td_api')}
   state.update(objects);context=session.transport_context()
   for name,value in objects.items():self.assertIs(context[name],value)

 def test_actual_quota_transaction_persists_complete_childset_before_any_send(self):
  from qmt_roll_official_live_execution_ledger import read_execution_ledger,reserve_execution_ledger_intent
  with tempfile.TemporaryDirectory()as directory:
   session,state,paths=self.build_fixture(directory)
   row=dict(source='weekly19_risk_reduce',execution_profile='weekly19-15w-r150k',intent_id='delivery',
    planned_intent_id='planned',signal_identity={'intent_id':'planned'},trading_date='2026-11-02',
    vt_symbol='rb2701.SHFE',direction='short',offset='close',planned_volume=2)
   requests=[execution.OrderRequest(symbol='rb2701',exchange=execution.Exchange.SHFE,direction=execution.Direction.SHORT,
    type=execution.OrderType.LIMIT,volume=1,price=4000,offset=offset)for offset in (execution.Offset.CLOSETODAY,execution.Offset.CLOSEYESTERDAY)]
   state['connection_generation']='conn'
   context=dict(row=row,requests=requests,fingerprint='fp',service_generation='svc',connection_generation='conn')
   lease=SimpleNamespace(lease_token='lease',intent=SimpleNamespace(target_date='2026-10-30',intent_id='delivery',
    payload_sha256='a'*64,intent_kind='close',vt_symbol='rb2701.SHFE',lease_owner='svc'))
   reservation=reserve_execution_ledger_intent(target_date='2026-10-30',row=row,
    order_request=dict(symbol='rb2701',exchange='SHFE',direction='short',offset='close',volume=2,price=4000),
    close_retry_after_cancel_seconds=30,path=paths.ledger_path,base_event=dict(row,intent_kind='close',intent_payload_sha256='a'*64,
     service_generation='svc',connection_generation='conn',spool_lease_owner='svc',spool_lease_token='lease'))
   self.assertTrue(reservation['reserved'])
   context.update(fingerprint=reservation['intent_fingerprint'],close_submit_attempt_no=reservation['close_submit_attempt_no'],
    close_attempt_lease_token=reservation['close_attempt_lease_token'],reservation_record_checksum=reservation['latest_ledger_event']['record_checksum'])
   state['intent_contexts']['delivery']=context
   batch=session._reserve_api_slot(lease);events=read_execution_ledger(paths.ledger_path)
   self.assertTrue(batch,context.get('api_slot_blocker'));self.assertEqual(len(events),2)
   quota=events[-1];self.assertEqual(quota['event_type'],'api_slot_reserved')
   self.assertEqual(quota['api_slot_batch_id'],context['api_slot_batch_id'])
   self.assertEqual(quota['approved_parent_volume'],2)
   self.assertEqual(len(quota['api_slot_batch_children']),2)
   for index,child in enumerate(quota['api_slot_batch_children']):
    self.assertEqual(child['child_order_index'],index)
    self.assertEqual(child['expected_children'],quota['expected_children'])
    self.assertEqual(child['planned_intent_id'],'planned')
   callback=execution._stage179_warm_callback_base(dict(context,request=requests[0],child_order_id='fp:1/2'),{})
   self.assertEqual(callback['api_slot_batch_id'],batch)
   self.assertEqual(callback['expected_children_sha256'],quota['expected_children_sha256'])
   recovered=execution._stage179_warm_callback_base(dict(row=dict(row,**callback),request=requests[0]),{})
   self.assertEqual(recovered['api_slot_batch_id'],batch)
   self.assertEqual(recovered['expected_children_sha256'],quota['expected_children_sha256'])
   self.assertEqual(recovered['child_order_volume'],1)
   self.assertEqual(session.send_order_call_count,0)

 def test_periodic_refresh_reads_real_query_hooks_and_admits_only_after_all_complete(self):
  with tempfile.TemporaryDirectory()as directory:
   session,state,_=self.build_fixture(directory);state['td_api']=object();state['readiness_state']=execution.CtpReadinessState(account_required=True)
   state['weekly19_native_bridge']=SimpleNamespace(admit_completed_query_bundle=lambda **kw:
    dict(source_qualified=True,warm_capture_reference=dict(path='/literal-fixture',sha256='a'*64)))
   names=['_final_order_query_epoch','_final_trade_query_epoch','_final_position_query_epoch','_final_open_account_funds_query_epoch']
   calls=[]
   from contextlib import ExitStack
   with ExitStack()as stack:
    stack.enter_context(patch.object(execution,'_final_ctp_transport_blockers',return_value=[]))
    for name in names:
     def query(*args,_name=name,**kw):
      calls.append(_name)
      return dict(confirmed=True,callback_count=1,reqid=names.index(_name)+1,blockers=[])
     stack.enter_context(patch.object(execution,name,side_effect=query))
    result=session.refresh_weekly19_context()
   self.assertTrue(result['ready'],result);self.assertEqual(calls,names)
   self.assertIn('weekly19_warm_capture_reference',session.transport_context())
   self.assertEqual(state['readiness_state'].expected_account_reqid,4)
   self.assertEqual(state['readiness_state'].expected_position_reqid,3)
   self.assertEqual(session.send_order_call_count,0)

 def test_native_hook_restore_is_attempted_even_when_transport_or_bridge_close_fails(self):
  with tempfile.TemporaryDirectory()as directory:
   session,state,_=self.build_fixture(directory);calls=[]
   def fail(name):
    calls.append(name);raise OSError(name)
   state['main_engine']=SimpleNamespace(close=lambda:fail('transport'))
   state['weekly19_native_bridge']=SimpleNamespace(close=lambda:fail('bridge'))
   state['callback_context']=SimpleNamespace(__exit__=lambda *a:calls.append('restored'))
   with self.assertRaisesRegex(RuntimeError,'cleanup_failed'):
    session._disconnect_transport()
   self.assertEqual(calls,['transport','bridge','restored'])
   self.assertTrue(state['transport_generation_invalidated'])

class Weekly19NonblockingConnectionReadinessTest(unittest.TestCase):
 def test_startup_readiness_probe_does_not_wait_for_lifecycle_lock(self):
  import threading
  entered=threading.Event();release=threading.Event()
  def startup():
   entered.set();release.wait(2);return {'ready':True}
  session=execution.CtpExecutionSession(runtime=SimpleNamespace(),service_generation='s',official_version='v',capital=150000,
   readiness_ttl_seconds=3,connect_startup_bundle=startup,disconnect_transport=lambda:None,
   fresh_bundle=lambda *a:None,reserve_api_slot=lambda *a:'',send_order=lambda *a:None)
  thread=threading.Thread(target=session.connect);thread.start();self.assertTrue(entered.wait(1))
  try:
   probe=getattr(session,'connection_ready',None);self.assertTrue(callable(probe),'nonblocking lifecycle readiness missing')
   done=threading.Event();results=[]
   waiter=threading.Thread(target=lambda:(results.append(probe()),done.set()));waiter.start()
   self.assertTrue(done.wait(.25),'readiness waited behind startup lifecycle lock')
   self.assertEqual(results,[False])
  finally:release.set();thread.join(2)
  self.assertTrue(session.connection_ready());session.close();self.assertFalse(session.connection_ready())
