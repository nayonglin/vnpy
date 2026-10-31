"""Independent backend/all-ref/source-order tests; explicit offline fixtures."""
from pathlib import Path
import copy,json,sys,unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[4];sys.path[:0]=[str(ROOT),str(ROOT/'tests'),str(ROOT/'examples/portfolio_backtesting')]
from vnpy.trader.setting import SETTINGS
SETTINGS['log.file']=False;SETTINGS['log.console']=False
import tests.test_weekly19_manual_cash as f
import qmt_roll_weekly19_broker_evidence as broker
from qmt_roll_weekly19_pipeline_state import PipelineStateStore
class ManualBackendIndependent(unittest.TestCase):
 def setUp(self):
  self.fx=f.ManualPrivateEntryTests('test_prepared_record_is_private_and_only_cash_reference_is_published');self.fx.setUp();self.addCleanup(self.fx.doCleanups);self.fx.backend._market_cache={'calendar':f.CALENDAR}
 def write_cash(self,sources):
  cfg=copy.deepcopy(self.fx.cfg);cfg['cash_sources']=sources;self.fx.ctx.write_text(json.dumps(cfg));self.fx.ctx.chmod(0o600)
 def test_bad_mutable_reference_shapes_are_pending_not_an_actor_exception(self):
  for sources in [None,[],{'manual_reviews':None},{'manual_reviews':[None]},{'manual_reviews':[1]},{'manual_reviews':[{}]},{'manual_reviews':[{'path':None,'sha256':'f'*64}]},{'manual_reviews':[{'path':'/literal/missing'}]}]:
   with self.subTest(sources=sources):
    self.write_cash(sources);before=copy.deepcopy(self.fx.state)
    actual=self.fx.backend.reconcile_cash(self.fx.state,{'account':self.fx.current},self.fx.at)
    self.assertEqual(actual,before);self.assertEqual(self.fx.state,before);self.assertTrue(self.fx.backend.cash_source_blocker.startswith('manual_cash_review_pending:'))
 def test_same_record_id_conflict_cannot_be_hidden_after_a_good_reference(self):
  record=self.fx.prepare();result=self.fx.manual.write_and_publish_operator_review(self.fx.backend,record);raw=json.loads(record['raw_payload']);raw['notes']='conflicting same id';other=f.envelope(raw);path=self.fx.records/'other-private.json';path.write_text(other['raw_payload']);path.chmod(0o600)
  refs=[result['reference'],dict(path=str(path),sha256=other['raw_sha256'])];self.write_cash({'manual_reviews':refs})
  actual=self.fx.backend.reconcile_cash(self.fx.state,{'account':self.fx.current},self.fx.at)
  self.assertEqual(actual,self.fx.state);self.assertIn('id_content_conflict',self.fx.backend.cash_source_blocker)
 def test_old_consumed_record_does_not_cover_a_new_unknown_deposit(self):
  self.fx.manual.write_and_publish_operator_review(self.fx.backend,self.fx.prepare());updated=self.fx.backend.reconcile_cash(self.fx.state,{'account':self.fx.current},self.fx.at)
  later=self.fx.at+f.timedelta(minutes=1);changed=f.account(deposit='30001.00',at=later)
  again=self.fx.backend.reconcile_cash(updated,{'account':changed},later)
  self.assertEqual(again,updated);self.assertEqual(again['confirmed_topup_fen'],3000000);self.assertIn('manual_cash_review_pending',self.fx.backend.cash_source_blocker)
 def test_invalid_public_input_shape_never_loads_live_sources(self):
  for key,value in [('topups',None),('topups',[True]),('closed_days',{}),('notes',None),('expected_reserve_remaining_fen',True),('topups',[{}])]:
   bad=copy.deepcopy(self.fx.input);bad[key]=value;self.fx.manual._live_inputs.reset_mock()
   with self.subTest(key=key,value=value),self.assertRaises(ValueError):self.fx.manual.prepare_operator_review(self.fx.backend,bad,operator_id='fixture',review_id='bad-shape',now=self.fx.at)
   self.fx.manual._live_inputs.assert_not_called()
 def test_unqualified_real_source_result_is_rejected_before_calendar_or_record(self):
  self.fx.live.stop();cfg=copy.deepcopy(self.fx.cfg);cfg['broker']=dict(summary_path='/literal/not-opened',manifest_path='/literal/not-opened',policy={});self.fx.backend.config=cfg;self.fx.ctx.write_text(json.dumps(cfg));self.fx.ctx.chmod(0o600)
  with mock.patch.object(PipelineStateStore,'read',return_value=dict(runtime_mode='production',funding=self.fx.state)),mock.patch.object(broker,'load_broker_snapshot',return_value=dict(source_qualified=False,account=self.fx.current)),mock.patch.object(self.fx.manual,'_calendar',side_effect=AssertionError('must not reach calendar'))as calendar:
   with self.assertRaisesRegex(ValueError,'source_not_admitted'):self.fx.manual._live_inputs(self.fx.backend,self.fx.at)
  calendar.assert_not_called();self.assertEqual(list(self.fx.records.iterdir()),[])
 def test_reference_publication_preserves_concurrently_added_cash_refs(self):
  record=self.fx.prepare();original=self.fx.manual._append_reference;foreign=dict(path='/literal/unadmitted-existing-reference',sha256='c'*64)
  def concurrent(path,expected,ref):
   cfg=json.loads(self.fx.ctx.read_text());cfg['cash_sources']['manual_reviews']=[foreign];self.fx.ctx.write_text(json.dumps(cfg));self.fx.ctx.chmod(0o600);return original(path,expected,ref)
  with mock.patch.object(self.fx.manual,'_append_reference',side_effect=concurrent):result=self.fx.manual.write_and_publish_operator_review(self.fx.backend,record)
  refs=json.loads(self.fx.ctx.read_text())['cash_sources']['manual_reviews'];self.assertEqual(refs,[foreign,result['reference']]);self.assertFalse(result['funding_consumed'])
if __name__=='__main__':unittest.main(defaultTest='ManualBackendIndependent')
