"""Stage014 report scope, cash accounting and nullable-round export tests."""
import base64
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from stage014_contract import STARTS,MONTHS,OBSERVATION_STARTS,LINE
from test_stage014_plots import synthetic_bundle
try:
 import stage014_report as report
except ImportError:
 report=None


def raw(pnl):
 d=pd.DataFrame(dict(date=pd.date_range('2020-01-01',periods=len(pnl)).strftime('%Y-%m-%d'),net_pnl=pnl))
 d['account_equity']=150000+d.net_pnl.cumsum()
 for k in ['slippage','commission','trade_count','total_margin_exact']:d[k]=0
 return d


def event(before,amount,reserve=150000):
 return dict(date='2020-01-02',event_id=1,raw_account_equity=before,trading_equity_before=before,trading_equity_after=before+amount,
  reserve_before=reserve,reserve_after=reserve-amount,total_account_equity=before+reserve,transfer_amount=amount,cumulative_transfer=amount)


class ReportTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.bundle=synthetic_bundle()
 def setUp(self):self.assertIsNotNone(report,'Stage014 report missing')

 def test_cash_projection_has_one_fixed_reserve_and_keeps_negative_E(self):
  d=report.project_curve(raw([0,-220000]),[event(-70000,150000)])
  m=report.summary_metrics(d)
  self.assertEqual(m['real_trading_net_pnl'],-220000)
  self.assertEqual(m['account_end_equity'],80000)
  self.assertEqual(m['off_account_reserve_end'],0)
  d=report.project_curve(raw([0,-400000]),[event(-250000,150000)])
  self.assertLess(d.account_nav.iloc[-1],0)

 def test_complete_gate_requires_59_fresh_and_frozen_calendar_identity(self):
  reg=dict(jobs={s+'|C':dict(status='validated',method='fresh_engine',reused=False) for s in STARTS},financial_engine_batch_complete=True,financial_replays_started=59)
  self.assertTrue(report.require_complete(reg))
  bad=dict(reg,financial_replays_started=23)
  with self.assertRaises(ValueError):report.require_complete(bad)
  bad=dict(reg,jobs=dict(reg['jobs']));bad['jobs']['2015-01-01|C']=dict(status='validated',method='frozen_baseline',reused=True)
  with self.assertRaises(ValueError):report.require_complete(bad)
  path=LINE/'outputs/data_stage014_20261030/data_approved/mapping.csv'
  calendar=report.mapping_calendar(path,report.FROZEN_MAPPING_SHA256)
  self.assertEqual(sum(len(v) for v in calendar.values()),86049)
  with self.assertRaises(ValueError):report.mapping_calendar(path,'0'*64)

 def test_mature_and_observation_month_groups_are_separate(self):
  s,d=self.bundle;c=report.cohort_summary(s)
  self.assertEqual(len(c),12)
  total=c.loc[c.cohort.eq('combined')].set_index('scope')
  self.assertEqual(int(total.loc['mature_ge_1y','windows']),54)
  self.assertEqual(int(total.loc['observation_lt_1y','windows']),5)
  november=c.loc[c.cohort.eq('November')].set_index('scope')
  self.assertEqual(int(november.loc['mature_ge_1y','windows']),10)
  self.assertEqual(int(november.loc['observation_lt_1y','windows']),1)

 def test_zero_rounds_or_single_sided_rounds_keep_undefined_ratios(self):
  s,_=self.bundle;row=s.loc[s.start.eq('2026-09-01')].iloc[0]
  values=report.row_values(row)
  self.assertGreaterEqual(values.count('N/A'),5)
  self.assertNotIn('inf',' '.join(values).lower())
  for wins,losses in [(2,0),(0,2)]:
   r=row.copy();r['round_count']=2;r['round_wins']=wins;r['round_losses']=losses
   r['round_win_rate_pct']=100 if wins else 0;r['round_average_win']=200 if wins else None;r['round_average_loss_abs']=100 if losses else None
   r['round_payoff_ratio']=None;r['round_profit_factor']=None
   values=report.row_values(r)
   self.assertIn('N/A',values[-2:]);self.assertNotIn('inf',' '.join(values).lower())

 def test_all59_window_exports_keep_identity_and_observation_status(self):
  s,_=self.bundle
  with TemporaryDirectory() as td:
   root=Path(td);(root/'stages').mkdir()
   with patch('stage014_report.LINE',root):report.write_window_records(s,{'source_head':'frozen-head'})
   files=list((root/'stages/stage014_windows').glob('*.md'));self.assertEqual(len(files),59)
   text='\n'.join(p.read_text() for p in files)
   for start in STARTS:self.assertIn(start,text)
   obs=[p.read_text() for p in files if '20251101' in p.name][0]
   self.assertIn('观察',obs);self.assertIn('N/A',obs);self.assertIn('NO_PROMOTION',obs)

 def test_offline_html_embeds_five_images_all59_rows_and_no_fake_pair(self):
  s,_=self.bundle;names=[f'{i:02d}.png' for i in range(5)]
  png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jE1sAAAAASUVORK5CYII=')
  with TemporaryDirectory() as td:
   folder=Path(td)
   for name in names:(folder/name).write_bytes(png)
   report.write_reports(folder,s,report.cohort_summary(s),names,False)
   page=(folder/report.HTML_NAME).read_text()
   self.assertEqual(page.count('src="data:image/png;base64,'),5)
   self.assertEqual(page.count('<tr data-start='),59);self.assertEqual(page.count('<option value='),60)
   self.assertIn('59份真实独立回放',page);self.assertIn('54成熟',page);self.assertIn('5观察',page)
   self.assertNotIn('C_R100',page);self.assertNotIn('paired',page);self.assertNotIn('<script src=',page)
   self.assertNotIn('src="http',page);self.assertIn('N/A',page)


if __name__=='__main__':unittest.main()
