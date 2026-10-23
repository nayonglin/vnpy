"""No-MACD report boundary tests; only synthetic/read-only ledger arithmetic."""
from pathlib import Path
import json,sys,tempfile,unittest,shutil
HERE=Path(__file__).resolve().parent
TOOLS=HERE if HERE.name=='tools' else Path('/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/tools')
sys.path[:0]=[str(HERE),str(TOOLS)]
from test_stage011_build_artifacts import fixture
try:import stage014_build_artifacts as report
except ImportError:report=None

def setup(line):
 out=fixture(line);h=out/'H_attempt001'
 trades=__import__('pandas').read_csv(h/'trades.csv');trades.loc[trades.trade_id.eq('T2'),'price']=83041;trades.to_csv(h/'trades.csv',index=False)
 clock=trades.copy();clock['execution_datetime']=clock.datetime;clock.to_csv(h/'execution_clock.csv',index=False)
 pd=__import__('pandas');d=pd.read_csv(h/'daily.csv');d.loc[1,['account_equity','net_pnl']]=[979390,829400];d.to_csv(h/'daily.csv',index=False)
 p=pd.read_csv(h/'positions.csv');p.loc[1,['close_price','net_pnl']]=[83041,829400];p.to_csv(h/'positions.csv',index=False)
 d['date']=pd.to_datetime(d.date);m=report.base.curve_metrics(d);m.update(arm='H',result_scope=report.base.SCOPE,total_trade_count=2);(h/'metrics.json').write_text(json.dumps(m))
 for key in report.ai.AI_FLAGS:
  path=h/'actual_strategy_settings.json';a=json.loads(path.read_text());a[0]['actual'][key]=False;a[0]['setting'][key]=False;path.write_text(json.dumps(a))
 proof=dict(schema='stage012_ai_selection_off_v1',accepted=True,model_load_attempts=0,runtime_loaded=False,nonzero_ai_candidate_fields=0)
 (h/'ai_selection_acceptance.json').write_text(json.dumps(proof))
 k=out/'K_attempt001';shutil.copytree(h,k)
 path=k/'actual_strategy_settings.json';a=json.loads(path.read_text());a[0]['strategy_class']='NoMacdThreeMaWeeklyIndicatorsStrategy';path.write_text(json.dumps(a))
 path=k/'metrics.json';m=json.loads(path.read_text());m.update(arm='K',result_scope='weekly_no_macd_original19');path.write_text(json.dumps(m))
 for arm in ['H','K']:
  path=out/(arm+'_attempt001/preflight.json');p=json.loads(path.read_text());p.update(ready_need=21,storage_capacity=41);path.write_text(json.dumps(p))
 (k/'macd_acceptance.json').write_text(json.dumps(dict(schema='stage014_macd_disabled_acceptance_v1',accepted=True,macd_disabled=True,macd_calculation_attempts=0,candidate_case3_count=0,rollover_macd_hist_non_null_count=0)))
 (out/'K_completed_attempt.json').write_text(json.dumps({'path':str(k.resolve())}))
 return out

class Tests(unittest.TestCase):
 def api(self):self.assertIsNotNone(report,'stage014 report missing')
 def test_k_true_identity_and_macd_ai_proofs_are_pinned(self):
  self.api()
  with tempfile.TemporaryDirectory() as tmp:
   out=setup(Path(tmp));k=out/'K_attempt001';r=report.load_k(k,['2020-01-02','2026-10-22'])
   self.assertEqual(r['arm'],'K');self.assertEqual(r['metrics']['end_equity'],979390.)
   for name in ['ai_selection_acceptance.json','macd_acceptance.json']:self.assertIn(str((k/name).resolve()),r['sources'])
   path=k/'actual_strategy_settings.json';a=json.loads(path.read_text());a[0]['strategy_class']='ThreeMaWeeklyIndicatorsStrategy';path.write_text(json.dumps(a))
   with self.assertRaisesRegex(ValueError,'identity'):report.load_k(k)
 def test_each_failed_macd_ai_gate_and_old_scope_rejects(self):
  self.api()
  with tempfile.TemporaryDirectory() as tmp:
   out=setup(Path(tmp));k=out/'K_attempt001';path=k/'macd_acceptance.json';original=json.loads(path.read_text())
   for key,value in [('accepted',False),('macd_disabled',False),('macd_calculation_attempts',1),('candidate_case3_count',1),('rollover_macd_hist_non_null_count',1)]:
    with self.subTest(key=key):
     path.write_text(json.dumps({**original,key:value}))
     with self.assertRaisesRegex(ValueError,'MACD'):report.load_k(k)
   path.write_text(json.dumps(original));p=k/'ai_selection_acceptance.json';v=json.loads(p.read_text());v['model_load_attempts']=1;p.write_text(json.dumps(v))
   with self.assertRaisesRegex(ValueError,'AI'):report.load_k(k)
   v['model_load_attempts']=0;p.write_text(json.dumps(v));m=k/'metrics.json';v=json.loads(m.read_text());v['result_scope']='weekly_bar_open_original19';m.write_text(json.dumps(v))
   with self.assertRaisesRegex(ValueError,'identity'):report.load_k(k)
 def test_review_exact_h_k_binding_and_no_review_pending(self):
  self.api();paths={'H':Path('/tmp/H_attempt001'),'K':Path('/tmp/K_attempt001')}
  review=dict(schema='stage014_independent_review_v1',H_attempt_path=str(paths['H']),K_attempt_path=str(paths['K']),verdict='PASS_OFFLINE_RESEARCH')
  report.bind_review(review,paths);review['K_attempt_path']='/tmp/K_attempt002'
  with self.assertRaisesRegex(ValueError,'review'):report.bind_review(review,paths)
 def test_review_acceptance_stays_offline_and_rejection_wins(self):
  self.api();paths={'H':Path('/tmp/H_attempt001'),'K':Path('/tmp/K_attempt001')}
  review=dict(schema='stage014_independent_review_v1',H_attempt_path=str(paths['H']),K_attempt_path=str(paths['K']),verdict='PASS_OFFLINE_RESEARCH')
  report.bind_review(review,paths)
  quality=dict(schema='stage011_daily_bar_open_acceptance_v1',accepted=True,verdict='PASS_DECLARED_BAR_OPEN_MODEL',minute_reads=0,proxy_reads=0,daily_price_mismatch_count=0,daily_data_invalid_count=0)
  good=report.status(quality,review);self.assertTrue(good['valid_performance_accepted']);self.assertFalse(good['production_qualified']);self.assertIsNone(good['qualified_executable_trade_count'])
  review['verdict']='REJECT_EXECUTION';bad=report.status(quality,review);self.assertFalse(bad['valid_performance_accepted']);self.assertIn('DIAGNOSTIC',bad['performance_classification'])
 def test_synthetic_h_k_outputs_preserve_open_closed_and_no_overwrite(self):
  self.api()
  with tempfile.TemporaryDirectory() as tmp:
   line=Path(tmp);setup(line);result=report.build_artifacts(line)
   c=json.loads((line/'artifacts/stage014/comparison.json').read_text())
   self.assertEqual(c['decision'],'PENDING_INDEPENDENT_REVIEW');self.assertEqual(c['arms']['H']['modeled_metrics']['end_equity'],979390.)
   self.assertEqual(c['comparison']['modeled_ending_equity_K_minus_H'],0.)
   self.assertEqual(c['arms']['K']['closed_fifo']['closed_segments'],1);self.assertEqual(c['arms']['K']['closed_fifo']['open_quantity'],0.)
   self.assertEqual(result['financial_replays'],0)
   with self.assertRaises(FileExistsError):report.build_artifacts(line)

if __name__=='__main__':unittest.main()
