"""Real L identity and acceptance checks over synthetic conserved K/L ledgers."""
from pathlib import Path
import json,sys,tempfile,unittest,shutil
import pandas as pd
HERE=Path(__file__).resolve().parent
TOOLS=HERE if HERE.name=='tools' else Path('/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/tools')
sys.path[:0]=[str(HERE),str(TOOLS)]
from test_stage014_build_artifacts import setup as setup_k
try:import stage018_build_artifacts as report
except ImportError:report=None

def setup(line):
 out=setup_k(line);k=out/'K_attempt001';l=out/'L_attempt001';shutil.copytree(k,l)
 for filename,changes in [('actual_strategy_settings.json',None),('metrics.json',{'arm':'L','result_scope':'weekly_three_ma_short_case2_original19'}),('preflight.json',{'arm':'L','control_path':str(k.resolve())})]:
  p=l/filename;value=json.loads(p.read_text())
  if changes:value.update(changes)
  else:value[0]['strategy_class']='ShortCase2NoMacdThreeMaWeeklyIndicatorsStrategy'
  p.write_text(json.dumps(value))
 p=l/'macd_acceptance.json';v=json.loads(p.read_text());v['strategy_class']='ShortCase2NoMacdThreeMaWeeklyIndicatorsStrategy';v['unknown_candidate_signals']=0;p.write_text(json.dumps(v))
 for folder in [k,l]:
  t=pd.read_csv(folder/'trades.csv');t['order_id']=t.trade_id;t.to_csv(folder/'trades.csv',index=False)
  risk=[dict(signal_order_id='T1',signal='long_case1a',contract_vt_symbol='au2606.SHFE')]
  if folder==l:risk.append(dict(signal_order_id='',signal='short_case2',contract_vt_symbol='au2606.SHFE'))
  pd.DataFrame(risk).to_csv(folder/'entry_risk.csv',index=False)
 (l/'entry_candidates.csv').write_text('signal,skip_reason,candidate_status\nshort_case2,,opened\n')
 (l/'short_case2_acceptance.json').write_text(json.dumps(dict(schema='stage018_short_case2_acceptance_v1',strategy_class='ShortCase2NoMacdThreeMaWeeklyIndicatorsStrategy',accepted=True,accepted_signals=['short_case1a','short_case2'],short_case2_gate_allowed=True,short_case1a_gate_allowed=True,case3_gate_allowed=False,short_signal_rejected_count=0,short_case2_candidates=1,short_case2_opened=1,MA_decision_periods=[5,10,20],MA40_decision_enabled=False)))
 (l/'data_quality.json').write_text(json.dumps(dict(held_or_traded_daily_gaps=[],held_or_traded_zero_volume=[],captured_bar_failures=[])))
 (l/'data_read_counts.json').write_text(json.dumps(dict(minute_reads=0,proxy_reads=0,ai_selection_model_load_attempts=0)))
 (out/'L_completed_attempt.json').write_text(json.dumps({'path':str(l.resolve())}))
 (line/'stages').mkdir();contract=line/'stages/contract.md';contract.write_text('synthetic fixture, no strategy execution')
 (out/'stage018_contract_pointer.json').write_text(json.dumps({'path':str(contract.resolve()),'sha256':report.base.sha(contract)}))
 return out

class Tests(unittest.TestCase):
 def api(self):self.assertIsNotNone(report,'stage018 report not implemented')
 def test_l_identity_is_true_l_and_all_acceptance_sources_pinned(self):
  self.api()
  with tempfile.TemporaryDirectory() as tmp:
   out=setup(Path(tmp));p=out/'L_attempt001';r=report.load_l(p,['2020-01-02','2026-10-22'])
   self.assertEqual(r['arm'],'L');self.assertEqual(r['metrics']['end_equity'],979390.)
   for n in ['short_case2_acceptance.json','macd_acceptance.json','ai_selection_acceptance.json','entry_candidates.csv']:self.assertIn(str((p/n).resolve()),r['sources'])
   f=p/'actual_strategy_settings.json';v=json.loads(f.read_text());v[0]['strategy_class']='NoMacdThreeMaWeeklyIndicatorsStrategy';f.write_text(json.dumps(v))
   with self.assertRaisesRegex(ValueError,'identity'):report.load_l(p)
 def test_short_gate_macd_ai_and_candidate_mismatch_fail_closed(self):
  self.api()
  with tempfile.TemporaryDirectory() as tmp:
   out=setup(Path(tmp));p=out/'L_attempt001';f=p/'short_case2_acceptance.json';v=json.loads(f.read_text())
   for key,bad in [('accepted',False),('case3_gate_allowed',True),('MA40_decision_enabled',True),('short_case2_gate_allowed',False),('short_case2_opened',2)]:
    with self.subTest(key=key):
     f.write_text(json.dumps({**v,key:bad}))
     with self.assertRaises(ValueError):report.load_l(p)
   f.write_text(json.dumps(v))
   for filename,key,bad in [('macd_acceptance.json','macd_calculation_attempts',1),('macd_acceptance.json','strategy_class','NoMacdThreeMaWeeklyIndicatorsStrategy'),('ai_selection_acceptance.json','model_load_attempts',1),('data_read_counts.json','minute_reads',1)]:
    q=p/filename;original=json.loads(q.read_text());q.write_text(json.dumps({**original,key:bad}))
    with self.subTest(filename=filename,key=key):
     with self.assertRaises(ValueError):report.load_l(p)
    q.write_text(json.dumps(original))
   (p/'entry_candidates.csv').write_text('signal,skip_reason,candidate_status\nshort_case2,short_signal_rejected,skipped\n')
   with self.assertRaisesRegex(ValueError,'short'):report.load_l(p)
 def test_final_review_binds_exact_k_l_and_rejection_is_not_accepted(self):
  self.api();paths={'K':Path('/tmp/K_attempt001'),'L':Path('/tmp/L_attempt001')}
  review=dict(schema='stage018_independent_review_v1',verdict='PASS_OFFLINE_RESEARCH',K_attempt_path=str(paths['K']),L_attempt_path=str(paths['L']))
  report.bind_review(review,paths)
  quality=dict(schema='stage011_daily_bar_open_acceptance_v1',accepted=True,verdict='PASS_DECLARED_BAR_OPEN_MODEL',minute_reads=0,proxy_reads=0,daily_price_mismatch_count=0,daily_data_invalid_count=0)
  self.assertTrue(report.prior.status(quality,review)['valid_performance_accepted'])
  rejected=report.prior.status(quality,{**review,'verdict':'REJECT_ACCOUNTING'})
  self.assertFalse(rejected['valid_performance_accepted']);self.assertIn('REJECTED',rejected['performance_classification'])
  review['L_attempt_path']='/tmp/L_attempt002'
  with self.assertRaisesRegex(ValueError,'review'):report.bind_review(review,paths)
 def test_pending_outputs_are_separate_and_immutable_and_effective_exact(self):
  self.api()
  with tempfile.TemporaryDirectory() as tmp:
   line=Path(tmp);out=setup(line);r=report.build_artifacts(line)
   c=json.loads((line/'artifacts/stage018/comparison.json').read_text())
   self.assertEqual(c['decision'],'PENDING_INDEPENDENT_REVIEW');self.assertEqual(c['arms']['L']['actual_strategy_class'],'ShortCase2NoMacdThreeMaWeeklyIndicatorsStrategy')
   self.assertEqual(c['comparison']['modeled_ending_equity_L_minus_K'],0.);self.assertEqual(c['arms']['L']['entry_fill_attribution']['short_case2_planned_opened'],1);self.assertEqual(c['arms']['L']['entry_fill_attribution']['short_case2_actual_open_fills'],0);self.assertEqual(c['arms']['L']['entry_fill_attribution']['unfilled_entry_plan_rows'],1);self.assertEqual(len(pd.read_csv(line/'artifacts/stage018/products.csv')),38)
   self.assertEqual(r['financial_replays'],0)
   with self.assertRaises(FileExistsError):report.build_artifacts(line)
  with tempfile.TemporaryDirectory() as tmp:
   line=Path(tmp);out=setup(line);p=out/'L_attempt001/effective_parameters.json';v=json.loads(p.read_text());v['unapproved_extra']='change';p.write_text(json.dumps(v))
   with self.assertRaisesRegex(ValueError,'effective'):report.build_artifacts(line)

if __name__=='__main__':unittest.main()
