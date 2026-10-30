import importlib.util,unittest
from copy import deepcopy

class NonbindingTests(unittest.TestCase):
 def subject(self):
  self.assertIsNotNone(importlib.util.find_spec('stage013_reuse'),'Stage013 reuse missing')
  import stage013_reuse as m
  return m
 def checks(self):
  return [dict(date='2015-01-06',candidate_key='x',entry_context='flat_entry',direction='long',signal='long_case1a',phase='before_parent_sizing',enabled=True,eligible=True,duplicate=False,weekly_stop_valid=True,range_would_block=False,trading_equity_before=130000.,trading_equity_after=150000.,reserve_before=150000.,reserve_after=130000.,transfer_amount=20000.,cumulative_transfer=20000.,raw_account_equity=130000.,total_account_equity=280000.,selected_volume_after_parent=2),dict(date='2015-01-07',candidate_key='y',entry_context='flat_entry',direction='long',signal='long_case2',phase='before_parent_sizing',enabled=True,eligible=True,duplicate=False,weekly_stop_valid=True,range_would_block=False,trading_equity_before=70000.,trading_equity_after=150000.,reserve_before=130000.,reserve_after=50000.,transfer_amount=80000.,cumulative_transfer=100000.,raw_account_equity=50000.,total_account_equity=200000.,selected_volume_after_parent=1)]
 def test_every_check_is_coupled_and_equal_cap_is_nonbinding(self):
  m=self.subject();rows=self.checks();events=[dict(r,event_id=i+1) for i,r in enumerate(rows)]
  proof=m.prove_checks(rows,events,'2015-01-01');self.assertTrue(proof['accepted']);self.assertEqual(proof['cumulative_transfer'],100000.);self.assertEqual(proof['check_count'],2)
 def test_cap_binding_negative_flow_wrong_gate_or_nonmonotone_are_rejected(self):
  m=self.subject();rows=self.checks();events=[dict(r,event_id=i+1) for i,r in enumerate(rows)]
  for key,value in [('transfer_amount',-1.),('reserve_before',90000.),('cumulative_transfer',19000.),('trading_equity_after',150001.),('range_would_block',True),('selected_volume_after_parent',-1)]:
   bad=deepcopy(rows);bad[1][key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):m.prove_checks(bad,events,'2015-01-01')
  bad=deepcopy(rows);bad[1].update(trading_equity_before=69999.,transfer_amount=80001.,cumulative_transfer=100001.,reserve_after=49999.,raw_account_equity=49999.,total_account_equity=199999.);bad_events=[dict(r,event_id=i+1) for i,r in enumerate(bad)]
  with self.assertRaises(ValueError):m.prove_checks(bad,bad_events,'2015-01-01')
 def test_source_inspector_rejects_parent_reading_reserve(self):
  m=self.subject();self.assertTrue(m.source_independence()['accepted'])
  with self.assertRaises(ValueError):m.reject_reserve_reads('def risk(self):\n return self.reserve_balance\n','bad.py')
  with self.assertRaises(ValueError):m.reject_reserve_reads('def risk(data):\n return data["total_account_equity"]\n','bad.py')
 def test_forged_empty_source_proof_cannot_admit_a_reuse(self):
  m=self.subject()
  with self.assertRaisesRegex(ValueError,'source_independence'):
   m.prove_nonbinding({},'2015-01-01',{},dict(accepted=True,parent_sources_sha256={},reserve_wrapper_sources_sha256={}))
 def test_real2015_fullperiod_reuse_retains_actual_source_and_250k_wealth(self):
  m=self.subject();c=m.contract;f=dict(data_identity=c.load(c.LINE/'stages/stage009_freeze.json')['data_identity'],source_head='a'*40,baseline_freeze=str(c.LINE/'stages/stage009_freeze.json'),baseline_registry=str(c.LINE/'outputs/stage009_multistart/registry.json'))
  for key in ['baseline_freeze','baseline_registry']:f[key+'_sha256']=c.sha(f[key])
  proof=m.prove_nonbinding(f,'2015-01-01');old=c.load(c.LINE/'outputs/stage009_C_20150101_attempt001/metrics.json')
  self.assertTrue(proof['accepted']);self.assertEqual(proof['financial_replays'],0);self.assertEqual(proof['method'],'proven_nonbinding_reuse')
  self.assertIn('raw_metrics',proof,'reuse checkpoint must retain raw150k and wealth250k metrics')
  self.assertEqual(proof['raw_metrics']['end_equity'],old['end_equity']);self.assertAlmostEqual(proof['metrics']['end_equity'],old['end_equity']+100000.);self.assertEqual(proof['metrics']['account_capital'],250000.)
if __name__=='__main__':unittest.main()
