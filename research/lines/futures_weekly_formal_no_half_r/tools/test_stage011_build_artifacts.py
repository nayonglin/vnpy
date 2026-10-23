"""Pure report checks: exact review binding, daily-open gate, unchanged FIFO math."""
from pathlib import Path
import importlib.util,json,sys,tempfile,unittest
import pandas as pd
HERE=Path(__file__).resolve().parent
TOOLS=HERE if (HERE/'stage008_build_artifacts.py').is_file() else Path('/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/tools')
sys.path[:0]=[str(Path(__file__).resolve().parent),str(TOOLS)]
try:import stage011_build_artifacts as report
except ImportError:report=None

def audit(**changes):
 return dict(schema='stage011_daily_bar_open_acceptance_v1',accepted=True,verdict='PASS_DECLARED_BAR_OPEN_MODEL',minute_reads=0,proxy_reads=0,daily_price_mismatch_count=0,daily_data_invalid_count=0,trade_count=2,anchor_request_count=2,details=[],**changes)

def fixture(line):
 out=line/'outputs';(out/'stage005_data').mkdir(parents=True)
 pd.DataFrame({'date':['2020-01-02','2026-10-22']}).to_csv(out/'stage005_data/mapping.csv',index=False)
 def js(path,value):path.write_text(json.dumps(value))
 for arm,klass in [('J','WeeklyIndicatorsStrategy'),('H','ThreeMaWeeklyIndicatorsStrategy')]:
  p=out/(arm+'_attempt001');p.mkdir()
  js(out/(arm+'_completed_attempt.json'),{'path':str(p.resolve())})
  actual=dict(ma_short=5,ma_mid=10,ma_long=20,ma_extra_long=40,capital_base=150000,research_exact_array_manager_size=41,**{f:False for f in report.FLAGS})
  js(p/'actual_strategy_settings.json',[dict(strategy_class=klass,actual=actual,setting=actual,engine_capital=150000)])
  js(p/'terminal.json',dict(status='completed_pending_independent_review',error=None))
  js(p/'preflight.json',dict(universe_products=sorted(report.ORIGINAL19),execution_model=report.EXECUTION_MODEL,minute_quote_confirmed=False))
  js(p/'bar_open_acceptance.json',audit())
  effective=dict(spec={'capital':{'account_capital':150000,'c3_capital':150000}},sizes={'au2606.SHFE':10},slippages={'au2606.SHFE':1},rates={'au2606.SHFE':0})
  js(p/'effective_parameters.json',effective)
  daily=pd.DataFrame(dict(date=['2020-01-02','2026-10-22'],account_equity=[149990.,150080.],net_pnl=[-10.,90.],slippage=[10.,10.],commission=[0.,0.],trade_count=[1,1]))
  daily.to_csv(p/'daily.csv',index=False)
  t=pd.DataFrame([dict(trade_id='T1',vt_symbol='au2606.SHFE',direction='多',offset='开',price=100,volume=1,datetime='2020-01-02T09:00:00+08:00',trading_date='2020-01-02'),dict(trade_id='T2',vt_symbol='au2606.SHFE',direction='空',offset='平',price=110,volume=1,datetime='2026-10-22T09:00:00+08:00',trading_date='2026-10-22')])
  t.to_csv(p/'trades.csv',index=False);clock=t.copy();clock['execution_datetime']=clock.datetime;clock.to_csv(p/'execution_clock.csv',index=False)
  pd.DataFrame(dict(date=['2020-01-02','2026-10-22'],vt_symbol=['au2606.SHFE']*2,start_pos=[0,1],end_pos=[1,0],close_price=[100,110],net_pnl=[-10.,90.])).to_csv(p/'positions.csv',index=False)
  d=daily.copy();d['date']=pd.to_datetime(d.date);metrics=report.curve_metrics(d);metrics.update(arm=arm,result_scope=report.SCOPE,total_trade_count=2)
  js(p/'metrics.json',metrics)
  js(p/'postflight.json',dict(inputs_unchanged=True))
 return out

class Tests(unittest.TestCase):
 def api(self):self.assertIsNotNone(report,'stage011 implementation missing')
 def test_acceptance_without_review_is_conditional(self):
  self.api();status=report.classify_bar_open(audit())
  self.assertFalse(status['valid_performance_accepted']);self.assertIn('PENDING',status['performance_classification'])
  self.assertIsNone(status['qualified_executable_trade_count'])
 def test_review_binds_both_actual_attempts_and_rejection_wins(self):
  self.api();paths={'J':Path('/tmp/J_attempt001'),'H':Path('/tmp/H_attempt001')}
  review={'schema':'stage011_independent_review_v1','J_attempt_path':str(paths['J']),'H_attempt_path':str(paths['H']),'verdict':'PASS_OFFLINE_RESEARCH'}
  report.bind_review(review,paths)
  status=report.classify_bar_open(audit(),review)
  self.assertTrue(status['valid_performance_accepted']);self.assertFalse(status['production_qualified'])
  self.assertEqual(status['promotion_decision'],'NO_PROMOTION')
  status=report.classify_bar_open({'accepted':False,'verdict':'REJECT_DAILY_VOLUME'},review)
  self.assertFalse(status['valid_performance_accepted']);self.assertIn('DIAGNOSTIC',status['performance_classification'])
  review['H_attempt_path']='/tmp/H_attempt002'
  with self.assertRaisesRegex(ValueError,'review'):report.bind_review(review,paths)
 def test_malformed_review_cannot_accept_daily_model(self):
  self.api()
  with self.assertRaisesRegex(ValueError,'review'):report.classify_bar_open(audit(),{'verdict':'PASS_OFFLINE_RESEARCH'})
 def test_minute_audit_or_unknown_pass_is_not_daily_open_acceptance(self):
  self.api()
  for audit in [{'accepted':True,'verdict':'PASS_POSITIVE_EXECUTION_MINUTES'},{'accepted':True,'verdict':'PASS_UNKNOWN'}]:
   self.assertFalse(report.classify_bar_open(audit)['valid_performance_accepted'])
   self.assertFalse(report.classify_bar_open(audit)['bar_open_model_accepted'])
 def test_fifo_partial_close_math_and_annual_compounding_reused(self):
  self.api()
  trades=pd.DataFrame([dict(trade_id=f'T{i}',vt_symbol='x2501.TEST',direction=d,offset=o,price=p,volume=v,datetime=t) for i,(d,o,p,v,t) in enumerate([('多','开',100,2,'2025-01-01T21:00+08:00'),('空','平',110,1,'2025-01-02T21:00+08:00'),('空','平',95,1,'2025-01-03T21:00+08:00')])])
  seg,s=report.fifo_segments(trades,dict(sizes={'x2501.TEST':10.},slippages={'x2501.TEST':1.},rates={'x2501.TEST':.001}))
  self.assertAlmostEqual(s['closed_net_pnl'],5.95);self.assertAlmostEqual(seg.net_pnl.iloc[0],77.9);self.assertAlmostEqual(seg.net_pnl.iloc[1],-71.95)
  d=pd.DataFrame(dict(date=pd.to_datetime(['2025-12-31','2026-01-02']),account_equity=[200000.,190000.],net_pnl=[50000.,-10000.],trade_count=[1,1],slippage=[1.,2.],commission=[0.,0.]))
  rows=report.annual_rows(d,'H',report.classify_bar_open({}))
  self.assertAlmostEqual(rows[0]['return_pct'],100/3);self.assertEqual(rows[1]['starting_equity'],200000.);self.assertAlmostEqual(rows[1]['return_pct'],-5.)
  self.assertEqual(rows[1]['period'],'2026 YTD')
 def test_old_E9_is_math_only_and_reconciles_without_loading_evidence(self):
  self.api();p=TOOLS.parent/'outputs/E_attempt009'
  if not p.exists():self.skipTest('private E9 ledger absent')
  daily=pd.read_csv(p/'daily.csv');daily['date']=pd.to_datetime(daily.date)
  trades=pd.read_csv(p/'trades.csv');positions=pd.read_csv(p/'positions.csv');positions['date']=pd.to_datetime(positions.date)
  marks=positions.loc[positions.date.eq('2026-10-22')].set_index('vt_symbol').close_price.to_dict()
  effective=json.loads((p/'effective_parameters.json').read_text())
  seg,s=report.fifo_segments(trades,effective,terminal_marks=marks)
  m=report.curve_metrics(daily)
  self.assertEqual(m['end_equity'],335420.);self.assertEqual(m['modeled_fill_count'],108)
  self.assertEqual(len(seg),54);self.assertEqual(s['winning_segments'],24);self.assertAlmostEqual(s['ledger_net_pnl'],185420.)
 def test_daily_open_loader_rejects_identity_bad_gate_count_and_partial_calendar(self):
  self.api()
  with tempfile.TemporaryDirectory() as root:
   out=fixture(Path(root));p=out/'J_attempt001'
   ledger=report.load_ledger(p,'J',report.ORIGINAL19,['2020-01-02','2026-10-22'])
   self.assertEqual(ledger['fifo_stats']['ledger_net_pnl'],80.);self.assertEqual(ledger['metrics']['end_equity'],150080.)
   with self.assertRaisesRegex(ValueError,'calendar'):report.load_ledger(p,'J',report.ORIGINAL19,['2020-01-02','2020-01-03','2026-10-22'])
   path=p/'actual_strategy_settings.json';a=json.loads(path.read_text());a[0]['actual'][report.FLAGS[0]]=True;path.write_text(json.dumps(a))
   with self.assertRaisesRegex(ValueError,'flags'):report.load_ledger(p,'J',report.ORIGINAL19)
   a[0]['actual'][report.FLAGS[0]]=False;a[0]['strategy_class']='ThreeMaWeeklyIndicatorsStrategy';path.write_text(json.dumps(a))
   with self.assertRaisesRegex(ValueError,'class'):report.load_ledger(p,'J',report.ORIGINAL19)
 def test_synthetic_artifacts_are_pending_38_products_and_immutable(self):
  self.api()
  with tempfile.TemporaryDirectory() as root:
   line=Path(root);fixture(line);art=line/'artifacts';art.mkdir();old=art/'old.txt';old.write_bytes(b'frozen')
   result=report.build_artifacts(line)
   self.assertEqual(result['financial_replays'],0);self.assertEqual(result['minute_evidence_files_read'],0)
   data=json.loads((art/'stage011/comparison.json').read_text())
   self.assertEqual(data['decision'],'PENDING_INDEPENDENT_REVIEW');self.assertEqual(data['arms']['H']['modeled_metrics']['end_equity'],150080.)
   self.assertEqual(len(pd.read_csv(art/'stage011/products.csv')),38)
   self.assertEqual(pd.read_csv(art/'stage011/closed_fifo_segments.csv').net_pnl.tolist(),[80.,80.])
   self.assertTrue((art/'stage011_equity_drawdown.png').is_file());self.assertEqual(old.read_bytes(),b'frozen')
   with self.assertRaises(FileExistsError):report.build_artifacts(line)
 def test_previous_artifact_is_never_overwritten(self):
  self.api()
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)/'old.png';p.write_bytes(b'frozen')
   with self.assertRaises(FileExistsError):report.require_new_outputs([p])
   self.assertEqual(p.read_bytes(),b'frozen')

if __name__=='__main__':unittest.main()
