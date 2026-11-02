"""Actual private quota reader + pure own-batch gate, offline fixtures only."""
import copy,json,os,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT/'tests')]
import test_weekly19_broker_evidence as broker_tests
from test_weekly19_execution import fixture,NOW,ACCOUNT,RELEASE,query
import qmt_roll_weekly19_broker_evidence as broker
import qmt_roll_weekly19_execution as gate

class PhysicalGateTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir='/private/tmp');self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve();self.root.chmod(0o700)
  self.rows=broker_tests.BrokerEvidenceTest('runTest').batch_ledger(both_native=False)
  self.path=self.root/'ledger.ndjson';self.path.write_text(''.join(json.dumps(r)+'\n'for r in self.rows));self.path.chmod(0o600)
  self.bindings=broker.load_execution_order_intent_bindings(self.path,expected_account_key=ACCOUNT,material_release_id=RELEASE,execution_profile='weekly19-15w-r150k')
  self.intent,self.context=fixture();self.intent.update(intent_id='W19EXEC-delivery',planned_intent_id='intent-1',signal_identity=copy.deepcopy(self.bindings[0]['signal_identity']),
   source='weekly19_risk_reduce',offset='close',intent_kind='risk_close',planned_volume=1)
  self.context['broker_snapshot']['positions']=query('positions',[dict(vt_symbol=self.intent['vt_symbol'],direction='short',volume=2)])
  self.context['execution_ledger_rows']=self.bindings
  self.context['current_delivery_lease']=dict(intent_id='W19EXEC-delivery',payload_sha256='b'*64,lease_token='lease-1',lease_owner='service-1',connection_generation='connection-1')
  self.context['immutable_parent_intent']=dict(self.intent,planned_volume=2)
  self.context['current_physical_batch']=dict(api_slot_batch_id=self.rows[0]['api_slot_batch_id'],weekly19_batch_manifest=copy.deepcopy(self.rows[0]['weekly19_batch_manifest']))
 def test_real_typed_bindings_are_not_misread_as_terminal_execution_events(self):
  self.assertNotIn('event_type',self.bindings[0]);self.assertNotIn('status',self.bindings[0])
  result=gate.evaluate_intent(self.intent,self.context,now=NOW)
  self.assertTrue(result['allowed'],result)
 def test_old_batch_wrong_lease_childset_or_plain_binding_cannot_release_own_batch(self):
  self.assertTrue(gate.evaluate_intent(self.intent,self.context,now=NOW)['allowed'])
  for field,value in [('api_slot_batch_id','0'*24),('weekly19_batch_manifest',dict(self.rows[0]['weekly19_batch_manifest'],spool_lease_token='other')),
    ('weekly19_batch_manifest',dict(self.rows[0]['weekly19_batch_manifest'],expected_children_sha256='0'*64))]:
   with self.subTest(field=field):
    bad=dict(self.context,current_physical_batch=dict(self.context['current_physical_batch'],**{field:value}))
    self.assertFalse(gate.evaluate_intent(self.intent,bad,now=NOW)['allowed'])
  bad=dict(self.context,current_delivery_lease=dict(self.context['current_delivery_lease'],connection_generation='other-generation'))
  self.assertFalse(gate.evaluate_intent(self.intent,bad,now=NOW)['allowed'])
  bad=dict(self.context,execution_ledger_rows=list(self.bindings))
  self.assertFalse(gate.evaluate_intent(self.intent,bad,now=NOW)['allowed'])
 def test_other_native_order_is_still_unknown_exposure(self):
  self.context['broker_snapshot']['orders']=query('orders',[dict(broker_order_id='CTP.11_22_99',vt_symbol=self.intent['vt_symbol'],direction='long',offset='close',volume=1,traded=0,status='working')])
  self.assertFalse(gate.evaluate_intent(self.intent,self.context,now=NOW)['allowed'])
