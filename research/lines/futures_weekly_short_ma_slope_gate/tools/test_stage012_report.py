"""Capital-flow counterexamples, independent of trading implementation."""
import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path
import pandas as pd
from stage012_report import project_curve,summary_metrics,pair_metrics,write_window_records


def raw(pnl):
 d=pd.DataFrame(dict(date=pd.date_range('2020-01-01',periods=len(pnl)).strftime('%Y-%m-%d'),net_pnl=pnl))
 d['account_equity']=150000+d.net_pnl.cumsum()
 for k in ['slippage','commission','trade_count','total_margin_exact']:d[k]=0
 return d


def event(before,amount,reserve):
 return dict(date='2020-01-02',event_id=1,raw_account_equity=before,
  trading_equity_before=before,trading_equity_after=before+amount,
  reserve_before=reserve,reserve_after=reserve-amount,total_account_equity=before+reserve,
  transfer_amount=amount,cumulative_transfer=amount)


class CashAccountingTests(unittest.TestCase):
 def test_nonbinding_cash_stays_outside_nav(self):
  r=raw([0,-40000,5000]);a=project_curve(r,[event(110000,40000,150000)],150000);b=project_curve(r,[event(110000,40000,50000)],50000)
  self.assertEqual(a.trading_account_equity.tolist(),b.trading_account_equity.tolist())
  self.assertEqual(b.account_nav.iloc[0],1)
  self.assertEqual((a.reserve_balance-b.reserve_balance).tolist(),[100000]*3)
  self.assertEqual((a.total_account_equity-b.total_account_equity).tolist(),[100000]*3)

 def test_partial_topup_not_profit_or_full_floor(self):
  d=project_curve(raw([0,-80000,5000]),[event(70000,50000,50000)],50000);m=summary_metrics(d)
  self.assertEqual(m['account_end_equity'],125000)
  self.assertEqual(m['real_trading_net_pnl'],-75000)
  self.assertEqual(m['total_transferred'],50000)
  self.assertEqual(m['off_account_reserve_end'],0)

 def test_overdraw_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'bounded_deficit'):
   project_curve(raw([0,-80000]),[event(70000,80000,50000)],50000)

 def test_negative_equity_never_clipped(self):
  m=summary_metrics(project_curve(raw([0,-220000]),[],50000))
  self.assertEqual(m['account_end_equity'],-70000)
  self.assertLess(m['balance_max_dd_pct'],-100)

 def test_funding_alone_cannot_be_profit_improvement(self):
  a=dict(account_end_equity=150000,real_trading_net_pnl=-40000,account_growth_pct=0,balance_max_dd_pct=-20,balance_sharpe=.2,total_transferred=40000)
  b=dict(a,account_end_equity=160000,total_transferred=50000,account_growth_pct=20/3)
  p=pair_metrics(a,b,'2020-01-01','fresh_engine')
  self.assertEqual(p['real_pnl_comparison'],0);self.assertEqual(p['delta_real_trading_net_pnl'],0)
  self.assertEqual(p['delta_account_end_equity'],p['delta_deposits'])


class RecordExportTests(unittest.TestCase):
 def test_index_lookup_retains_window_identity_for_export(self):
  m=summary_metrics(project_curve(raw([0,100,0]),[],50000))
  m.update(start='2015-01-01',observation_only=False,method='proven_nonbinding_reuse',source_path='frozen_old_run',independent_receipt='receipt',
   reserve_exhausted=False,exhaustion_date='',trading_margin_peak_pct=0,open_round_net_mtm=0,round_closed_net_pnl=100,
   round_win_rate_pct=50,round_average_win=100,round_average_loss_abs=50,round_payoff_ratio=2,round_profit_factor=2)
  summary=pd.DataFrame([dict(m,variant=v) for v in ['C_R150','C_R50']])
  with TemporaryDirectory() as td:
   root=Path(td);(root/'stages').mkdir()
   with patch('stage012_report.LINE',root),patch('stage012_report.STARTS',['2015-01-01']),patch('stage012_report.load',return_value={'source_head':'old_engine'}):
    write_window_records(summary,pd.DataFrame(),{'source_head':'new_frozen','baseline_freeze':'old_freeze'})
   files=list((root/'stages/stage012_windows').glob('*.md'))
   self.assertEqual(len(files),1)
   content=files[0].read_text()
   self.assertIn('2015-01-01|原C：15万备用金',content)
   self.assertIn('2015-01-01|原C：5万备用金',content)
   self.assertIn('旧引擎HEAD=old_engine',content)


if __name__=='__main__':unittest.main()
