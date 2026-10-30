"""Stage013 cash accounting, completion gates and offline export counterexamples."""
import base64
import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path
import pandas as pd

try:
 import stage013_report as report
except ImportError:
 report=None

STARTS=tuple(f'{year}-{month:02d}-01' for year in range(2015,2027) for month in (1,6) if (year,month)<=(2026,1))
FRESH={'2017-01-01','2017-06-01','2018-01-01','2018-06-01'}


def raw(pnl):
 d=pd.DataFrame(dict(date=pd.date_range('2020-01-01',periods=len(pnl)).strftime('%Y-%m-%d'),net_pnl=pnl))
 d['account_equity']=150000+d.net_pnl.cumsum()
 for field in ['slippage','commission','trade_count','total_margin_exact']:d[field]=0
 return d


def event(before,amount,reserve):
 return dict(date='2020-01-02',event_id=1,raw_account_equity=before,trading_equity_before=before,
  trading_equity_after=before+amount,reserve_before=reserve,reserve_after=reserve-amount,
  total_account_equity=before+reserve,transfer_amount=amount,cumulative_transfer=amount)


def export_summary():
 rows=[]
 for start in STARTS:
  for variant,reserve in [('C_R150',150000),('C_R100',100000)]:
   m=report.summary_metrics(report.project_curve(raw([0,100,0]),[],reserve))
   m.update(start=start,variant=variant,arm='C',reserve_initial=reserve,version='reserve150k' if reserve==150000 else 'reserve100k',
    observation_only=start=='2026-01-01',method='frozen_baseline' if reserve==150000 else 'fresh_engine' if start in FRESH else 'proven_nonbinding_reuse',
    source_path='frozen_old_run' if reserve==150000 or start not in FRESH else 'stage013_fresh_run',independent_receipt='receipt',
    reserve_exhausted=False,exhaustion_date='',trading_margin_peak_pct=0,open_round_net_mtm=0,round_closed_net_pnl=100,
    round_win_rate_pct=50,round_average_win=100,round_average_loss_abs=50,round_payoff_ratio=2,round_profit_factor=2)
   rows.append(m)
 return pd.DataFrame(rows)


class CashAccountingTests(unittest.TestCase):
 def setUp(self):self.assertIsNotNone(report,'Stage013 report is missing')

 def test_nonbinding_cash_stays_outside_nav_with_only_50k_reserve_offset(self):
  r=raw([0,-40000,5000]);a=report.project_curve(r,[event(110000,40000,150000)],150000);b=report.project_curve(r,[event(110000,40000,100000)],100000)
  self.assertEqual(a.trading_account_equity.tolist(),b.trading_account_equity.tolist())
  self.assertEqual(b.account_nav.iloc[0],1)
  self.assertEqual((a.reserve_balance-b.reserve_balance).tolist(),[50000]*3)
  self.assertEqual((a.total_account_equity-b.total_account_equity).tolist(),[50000]*3)
  self.assertEqual(float(b.total_account_equity.iloc[0]),250000)

 def test_partial_topup_is_not_profit_or_full_floor(self):
  d=report.project_curve(raw([0,-120000,5000]),[event(30000,100000,100000)],100000);m=report.summary_metrics(d)
  self.assertEqual(m['account_end_equity'],135000)
  self.assertEqual(m['real_trading_net_pnl'],-115000)
  self.assertEqual(m['total_transferred'],100000)
  self.assertEqual(m['off_account_reserve_end'],0)

 def test_exact_cap_is_allowed_but_overdraw_and_old_50k_identity_are_rejected(self):
  d=report.project_curve(raw([0,-100000]),[event(50000,100000,100000)],100000)
  self.assertEqual(d.trading_account_equity.iloc[-1],150000)
  self.assertEqual(d.reserve_balance.iloc[-1],0)
  with self.assertRaisesRegex(ValueError,'bounded_deficit'):
   report.project_curve(raw([0,-120000]),[event(30000,120000,100000)],100000)
  with self.assertRaisesRegex(ValueError,'fixed_reserve_limit'):
   report.project_curve(raw([0,0]),[],50000)

 def test_negative_equity_is_preserved_with_no_floor_or_cash_creation(self):
  m=report.summary_metrics(report.project_curve(raw([0,-270000]),[],100000))
  self.assertEqual(m['account_end_equity'],-120000)
  self.assertLess(m['balance_max_dd_pct'],-100)
  self.assertEqual(m['real_trading_net_pnl'],-270000)

 def test_funding_alone_cannot_be_profit_improvement_and_pair_identity_is_r100(self):
  a=dict(account_end_equity=150000,real_trading_net_pnl=-40000,account_growth_pct=0,balance_max_dd_pct=-20,balance_sharpe=.2,total_transferred=40000)
  b=dict(a,account_end_equity=160000,total_transferred=50000,account_growth_pct=20/3)
  p=report.pair_metrics(a,b,'2020-01-01','fresh_engine')
  self.assertEqual(p['real_pnl_comparison'],0)
  self.assertEqual(p['delta_real_trading_net_pnl'],0)
  self.assertEqual(p['delta_account_end_equity'],p['delta_deposits'])
  self.assertEqual(p['method100'],'fresh_engine')
  self.assertEqual(p['r100_total_transferred'],50000)
  self.assertNotIn('method50',p)
  self.assertNotIn('three_gate_pass',p)

 def test_receipt_routing_preserves_stage009_control_and_requires_v2_candidate(self):
  with TemporaryDirectory() as td:
   root=Path(td)
   with patch('stage013_report.LINE',root):
    self.assertEqual(report.window_receipt_path('2015-01-01','C_R150'),root/'stages/stage009_independent_receipts/2015-01-01_C.json')
    self.assertEqual(report.window_receipt_path('2015-01-01','C_R100'),root/'stages/stage013_independent_receipts_v2/2015-01-01_C.json')
    with self.assertRaises(ValueError):report.window_receipt_path('2015-01-01','C_R50')

 def test_build_readiness_reads_v2_default_freeze_and_registry_before_any_output(self):
  class ReadinessStop(Exception):pass
  seen=[]
  expected_freeze=report.LINE/'stages/stage013_freeze_v2.json'
  with TemporaryDirectory() as td:
   root=Path(td)
   def controlled_load(path):
    seen.append(Path(path))
    if len(seen)==1:return {'baseline_registry':str(root/'frozen_baseline.json')}
    raise ReadinessStop()
   output=root/'not_built'
   with patch('stage013_report.LINE',root),patch('stage013_report.load',side_effect=controlled_load):
    with self.assertRaises(ReadinessStop):report.build(output=output)
   self.assertEqual(seen,[expected_freeze,root/'outputs/stage013_multistart_v2/registry.json'])
   self.assertFalse(output.exists())

 def test_complete_gate_rejects_partial_scope_or_inflated_new_engine_count(self):
  reg=dict(jobs={s+'|C':dict(status='validated',method='fresh_engine' if s in FRESH else 'proven_nonbinding_reuse') for s in STARTS},
   financial_engine_batch_complete=True,financial_replays_started=4,counts=dict(fresh_validated=4,proven_reuse_validated=19))
  self.assertTrue(report.require_complete(reg))
  from copy import deepcopy
  bad=deepcopy(reg);bad['jobs'].pop('2026-01-01|C')
  with self.assertRaises(ValueError):report.require_complete(bad)
  bad=deepcopy(reg);bad['financial_replays_started']=23
  with self.assertRaises(ValueError):report.require_complete(bad)
  bad=deepcopy(reg);bad['jobs']['2015-01-01|C']['method']='fresh_engine'
  with self.assertRaises(ValueError):report.require_complete(bad)
  bad=deepcopy(reg);bad['counts']['proven_reuse_validated']=18
  with self.assertRaises(ValueError):report.require_complete(bad)


class RecordExportTests(unittest.TestCase):
 def setUp(self):self.assertIsNotNone(report,'Stage013 report is missing')

 def test_all_23_chinese_window_exports_keep_identity_after_index_lookup(self):
  summary=export_summary()
  with TemporaryDirectory() as td:
   root=Path(td);(root/'stages').mkdir()
   with patch('stage013_report.LINE',root),patch('stage013_report.load',return_value={'source_head':'old_engine'}):
    report.write_window_records(summary,pd.DataFrame(),{'source_head':'new_frozen','baseline_freeze':'old_freeze'})
   files=list((root/'stages/stage013_windows').glob('*.md'))
   self.assertEqual(len(files),23)
   full='\n'.join(p.read_text() for p in files)
   for start in STARTS:
    self.assertIn(start+('（观察）' if start=='2026-01-01' else '')+'|原C：15万备用金',full)
    self.assertIn(start+('（观察）' if start=='2026-01-01' else '')+'|原C：10万备用金',full)
   self.assertIn('旧引擎HEAD=old_engine',full)
   self.assertIn('总预算25/30万不同',full)
   self.assertNotIn('5万版',full)

 def test_offline_html_embeds_five_images_and_all_46_rows_without_legacy_identity(self):
  summary=export_summary();names=[f'{i:02d}.png' for i in range(1,6)]
  png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jE1sAAAAASUVORK5CYII=')
  with TemporaryDirectory() as td:
   folder=Path(td)
   for name in names:(folder/name).write_bytes(png)
   report.write_reports(folder,summary,pd.DataFrame([{'cohort':'combined','windows':23}]),names,False)
   page=(folder/report.HTML_NAME).read_text();markdown=(folder/'report.md').read_text()
   self.assertEqual(page.count('src="data:image/png;base64,'),5)
   self.assertEqual(page.count('<tr data-start='),46)
   self.assertEqual(page.count('<option value='),24)
   self.assertNotIn('<script src=',page)
   self.assertNotIn('src="http',page)
   self.assertIn('4份真实新回放＋19份严格无绑定证明复用',page)
   self.assertIn('Stage013',page)
   self.assertIn('10万',page)
   self.assertIn('25万/30万',page)
   self.assertIn('独立复核中',page)
   self.assertNotIn('Stage012',page)
   self.assertNotIn('C_R50',page)
   self.assertNotIn('method50',page)
   self.assertIn('NO_PROMOTION',markdown)


if __name__=='__main__':unittest.main()
