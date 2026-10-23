"""Synthetic L/M accounting and single-parameter identity boundaries; no replay."""
from pathlib import Path
import json,sys,tempfile,unittest,shutil
import pandas as pd
HERE=Path(__file__).resolve().parent
TOOLS=HERE if HERE.name=='tools' else Path('/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/tools')
sys.path[:0]=[str(HERE),str(TOOLS)]
from test_stage018_build_artifacts import setup as setup_l
try:import stage020_build_artifacts as report
except ImportError:report=None

def setup(line):
 out=setup_l(line);l=out/'L_attempt001';m=out/'M_attempt001';shutil.copytree(l,m)
 for arm,limit in [('L',4),('M',19)]:
  d=out/(arm+'_attempt001');p=d/'actual_strategy_settings.json';v=json.loads(p.read_text())
  for key in ['setting','actual']:v[0][key].update(max_concurrent_positions=limit,enable_portfolio_env_gate=False)
  p.write_text(json.dumps(v))
  c=d/'entry_candidates.csv';frame=pd.read_csv(c);frame['max_concurrent_positions']=limit;frame['effective_max_concurrent_positions']=limit;frame.to_csv(c,index=False)
  p=d/'effective_parameters.json';v=json.loads(p.read_text())
  v['spec']['capital']['max_concurrent_positions']=limit;v['spec'].setdefault('overrides',{})['max_concurrent_positions']=limit;p.write_text(json.dumps(v))
 p=m/'metrics.json';v=json.loads(p.read_text());v.update(arm='M',result_scope='weekly_three_ma_no_position_cap_original19');p.write_text(json.dumps(v))
 p=m/'preflight.json';v=json.loads(p.read_text());v.update(arm='M',control_path=str(l.resolve()));p.write_text(json.dumps(v))
 (m/'no_position_cap_acceptance.json').write_text(json.dumps(dict(schema='stage020_no_position_cap_acceptance_v1',strategy_class='ShortCase2NoMacdThreeMaWeeklyIndicatorsStrategy',accepted=True,universe_product_count=19,original_position_limit=4,candidate_effective_limit=19,configured_position_limit=19,candidate_effective_limit_values=[19],candidate_configured_limit_values=[19],concurrent_limit=0,portfolio_env_gate_enabled=False,max_daily_product_positions=1,implementation='universe_capacity_19_nonbinding_for_fixed_original19',MA40_decision_enabled=False,MA_decision_periods=[5,10,20])))
 contract=line/'stages/stage020_contract.md';contract.write_text('Synthetic no additional position cap fixture')
 (out/'stage020_contract_pointer.json').write_text(json.dumps({'path':str(contract.resolve()),'sha256':report.base.sha(contract)}))
 return out

class Tests(unittest.TestCase):
 def api(self):self.assertIsNotNone(report,'Stage020 report not implemented')
 def test_true_m_identity_and_proof_are_required(self):
  self.api()
  with tempfile.TemporaryDirectory() as tmp:
   out=setup(Path(tmp));p=out/'M_attempt001';r=report.load_m(p,['2020-01-02','2026-10-22'])
   self.assertEqual(r['arm'],'M');self.assertEqual(r['settings'][0]['actual']['max_concurrent_positions'],19)
   self.assertIn(str((p/'no_position_cap_acceptance.json').resolve()),r['sources'])
   q=p/'metrics.json';v=json.loads(q.read_text());v['arm']='L';q.write_text(json.dumps(v))
   with self.assertRaisesRegex(ValueError,'identity'):report.load_m(p)
 def test_unique_setting_difference_and_cap_proof_fail_closed(self):
  self.api()
  with tempfile.TemporaryDirectory() as tmp:
   out=setup(Path(tmp));l=report.prior.load_l(out/'L_attempt001');m=report.load_m(out/'M_attempt001');report.compare_parameter_contract(l,m)
   m['settings'][0]['actual']['ma_long']=21
   with self.assertRaisesRegex(ValueError,'settings'):report.compare_parameter_contract(l,m)
   p=out/'M_attempt001/no_position_cap_acceptance.json';v=json.loads(p.read_text())
   for key,bad in [('concurrent_limit',1),('candidate_effective_limit_values',[4]),('portfolio_env_gate_enabled',True),('max_daily_product_positions',2),('strategy_class','OtherStrategy')]:
    with self.subTest(key=key):
     p.write_text(json.dumps({**v,key:bad}))
     with self.assertRaisesRegex(ValueError,'position_cap'):report.load_m(out/'M_attempt001')
   p.write_text(json.dumps(v));q=out/'M_attempt001/entry_candidates.csv';frame=pd.read_csv(q);frame['effective_max_concurrent_positions']=4;frame.to_csv(q,index=False)
   with self.assertRaisesRegex(ValueError,'position_cap'):report.load_m(out/'M_attempt001')
 def test_pending_output_and_review_paths_and_effective_exact(self):
  self.api()
  with tempfile.TemporaryDirectory() as tmp:
   line=Path(tmp);out=setup(line);report.build_artifacts(line)
   c=json.loads((line/'artifacts/stage020/comparison.json').read_text())
   self.assertEqual(c['decision'],'PENDING_INDEPENDENT_REVIEW');self.assertEqual(set(c['arms']),{'L','M'})
   self.assertEqual(c['arms']['M']['actual_strategy_class'],'ShortCase2NoMacdThreeMaWeeklyIndicatorsStrategy')
   self.assertEqual(c['comparison']['modeled_ending_equity_M_minus_L'],0.);self.assertEqual(c['financial_replays'],0)
   self.assertEqual(len(pd.read_csv(line/'artifacts/stage020/products.csv')),38)
   with self.assertRaises(FileExistsError):report.build_artifacts(line)
   paths={a:out/(a+'_attempt001') for a in ['L','M']};review=dict(schema='stage020_independent_review_v1',verdict='PASS_OFFLINE_RESEARCH',L_attempt_path=str(paths['L']),M_attempt_path=str(paths['M']))
   report.bind_review(review,paths);review['M_attempt_path']=str(out/'M_attempt002')
   with self.assertRaisesRegex(ValueError,'review'):report.bind_review(review,paths)
  with tempfile.TemporaryDirectory() as tmp:
   out=setup(Path(tmp));l=report.prior.load_l(out/'L_attempt001');m=report.load_m(out/'M_attempt001');m['effective']['slippages']['changed']=1
   with self.assertRaisesRegex(ValueError,'effective'):report.compare_parameter_contract(l,m)
if __name__=='__main__':unittest.main()
