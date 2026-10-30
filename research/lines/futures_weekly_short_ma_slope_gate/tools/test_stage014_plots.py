"""Synthetic financial paths on the independently frozen mapping calendar."""
import os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/stage014-plots-mpl')
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from stage014_contract import LINE,STARTS,MONTHS,CUTOFF,OBSERVATION_STARTS
try:
 import stage014_plots as plots
except ImportError:
 plots=None


def synthetic_bundle():
 calendar=sorted(set(pd.read_csv(LINE/'outputs/data_stage014_20261030/data_approved/mapping.csv',usecols=['date']).date.astype(str)))
 rows=[];frames=[]
 for i,start in enumerate(STARTS):
  dates=[d for d in calendar if start<=d<=CUTOFF];n=len(dates);progress=np.linspace(0,1,n)
  profit=-410000. if i==0 else (-20000. if i%9==0 else 15000.+i*1200.)
  raw=150000.+profit*progress+1000*np.sin(progress*12);pnl=np.diff(np.r_[150000.,raw])
  amount=np.zeros(n);amount[[n//3,2*n//3]]=min(150000.,30000.+i*2500.)/2
  transfer=amount.cumsum();equity=raw+transfer;reserve=150000.-transfer
  dd=(equity/np.maximum.accumulate(np.r_[150000.,equity])[1:]-1)*100
  previous=np.r_[150000.,equity[:-1]];defined=bool((previous>0).all())
  returns=np.diff(np.r_[150000.,equity])/previous
  sharpe=float(returns.mean()/returns.std(ddof=1)*np.sqrt(252)) if defined else 0.
  margin=np.divide(10000.*165,equity,out=np.full(n,np.nan),where=equity>0)
  exhausted=reserve<=1e-6
  observation=start in OBSERVATION_STARTS
  # No closed rounds in the five observation fixtures; all PnL remains MTM.
  rounds=dict(round_count=0 if observation else 2,round_wins=0 if observation else 1,round_losses=0 if observation else 1,round_flat=0,
    round_win_rate_pct=None if observation else 50.,round_average_win=None if observation else 200.,round_average_loss_abs=None if observation else 100.,
    round_payoff_ratio=None if observation else 2.,round_profit_factor=None if observation else 2.,round_closed_net_pnl=0. if observation else 100.)
  rows.append(dict(start=start,variant='C_R150',arm='C',version='reserve150k',method='fresh_engine',funding_mode='external_topup',cohort_month=int(start[5:7]),
   reserve_initial=150000.,initial_trading_capital=150000.,actual_start=dates[0],actual_end=CUTOFF,trading_days=n,observation_only=observation,
   account_end_equity=equity[-1],account_growth_pct=(equity[-1]/150000.-1)*100,balance_max_dd_pct=dd.min(),balance_sharpe=sharpe,balance_returns_defined=defined,
   real_trading_net_pnl=pnl.sum(),total_transferred=transfer[-1],off_account_reserve_end=reserve[-1],total_slippage=n*2.,total_commission=0.,modeled_fill_count=n,
   transfer_event_days=2,transfer_event_count=3,reserve_exhausted=bool(exhausted.any()),exhaustion_date=dates[np.flatnonzero(exhausted)[0]] if exhausted.any() else '',
   nonpositive_trading_equity_days=int((equity<=0).sum()),trading_margin_peak_pct=np.nanmax(margin),trading_margin_over100_days=int((margin>100).sum()),
   open_round_net_mtm=float(pnl.sum())-rounds['round_closed_net_pnl'],source_path='synthetic/'+start,independent_receipt='synthetic-receipt',**rounds))
  frames.append(pd.DataFrame(dict(start=start,variant='C_R150',date=dates,raw_account_equity=raw,net_pnl=pnl,trading_account_equity=equity,
   reserve_balance=reserve,cumulative_transfer=transfer,transfer_amount=amount,total_account_equity=equity+reserve,slippage=np.full(n,2.),commission=np.zeros(n),
   trade_count=np.ones(n,dtype=int),total_margin_exact=np.full(n,10000.),account_nav=equity/150000.,balance_drawdown_pct=dd)))
 return pd.DataFrame(rows),pd.concat(frames,ignore_index=True)


class FiveStartPlotTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.bundle=synthetic_bundle()
 def setUp(self):self.assertIsNotNone(plots,'Stage014 renderer missing')

 def test_frozen59_calendar_and_cash_bridges_are_complete(self):
  s,d=self.bundle;si,curves=plots.validate_inputs(s,d)
  self.assertEqual((len(si),len(curves),len(d)),(59,59,86049))
  self.assertEqual(int(s.observation_only.sum()),5)
  first=curves['2015-01-01']
  self.assertLess(first.trading_account_equity.iloc[-1],0)
  self.assertEqual(first.account_nav.iloc[0],1)
  np.testing.assert_allclose(first.total_account_equity,300000+first.net_pnl.cumsum())

 def test_missing_scope_wrong_observation_or_method_fails_before_figure(self):
  s,d=self.bundle
  with patch.object(plots,'_figure',side_effect=AssertionError('allocated early')):
   for a,b in ((s.iloc[:-1],d),(s,d.iloc[:-1]),(s,pd.concat([d.iloc[:-1],d.iloc[[0]]]))):
    with self.assertRaises(ValueError):plots.render_five(a,b)
  for field,value in [('method','proven_nonbinding_reuse'),('variant','A_R150'),('observation_only',True),('cohort_month',3)]:
   bad=s.copy();bad.loc[0,field]=value
   with self.subTest(field=field),self.assertRaises(ValueError):plots.validate_inputs(bad,d)

 def test_interior_calendar_is_bound_to_mapping_not_just_count_and_endpoints(self):
  s,d=self.bundle;bad=d.copy();bad.loc[100,'date']='2015-01-10'
  with self.assertRaisesRegex(ValueError,'mapping_calendar'):plots.validate_inputs(s,bad)

 def test_deposits_do_not_become_pnl_or_untransferred_reserve_nav(self):
  s,d=self.bundle
  for field,values in [('net_pnl',d.net_pnl+d.transfer_amount),('account_nav',d.total_account_equity/150000),
   ('trading_account_equity',d.trading_account_equity.clip(lower=0)),('reserve_balance',d.reserve_balance+1)]:
   with self.subTest(field=field),self.assertRaises(ValueError):plots.validate_inputs(s,d.assign(**{field:values}))

 def test_nonfinite_money_is_rejected_but_declared_round_ratio_nulls_are_kept(self):
  s,d=self.bundle
  plots.validate_inputs(s,d)
  for field in ['account_end_equity','real_trading_net_pnl','total_transferred']:
   bad=s.copy();bad.loc[0,field]=np.nan
   with self.subTest(field=field),self.assertRaises(ValueError):plots.validate_inputs(bad,d)
  bad=s.copy();bad.loc[54,'round_profit_factor']=np.inf
  with self.assertRaises(ValueError):plots.validate_inputs(bad,d)

 def test_single_sided_rounds_preserve_null_payoff_and_source_defined_zero_pf(self):
  s,_=self.bundle;row=s.loc[s.start.eq('2026-09-01')].iloc[0].copy()
  row['round_count']=2;row['round_wins']=0;row['round_losses']=2;row['round_flat']=0
  row['round_win_rate_pct']=0.;row['round_average_win']=None;row['round_average_loss_abs']=100.
  row['round_payoff_ratio']=None;row['round_profit_factor']=0.;row['round_closed_net_pnl']=-200.
  row['open_round_net_mtm']=row.real_trading_net_pnl+200.
  plots.validate_round_fields(row)
  row['round_profit_factor']=None
  plots.validate_round_fields(row)
  row['round_wins']=2;row['round_losses']=0;row['round_win_rate_pct']=100.;row['round_average_win']=200.;row['round_average_loss_abs']=None
  row['round_closed_net_pnl']=400.;row['open_round_net_mtm']=row.real_trading_net_pnl-400.
  plots.validate_round_fields(row)

 def test_all59_curves_and_future_matrix_cell_are_preserved_and_status_only_changes(self):
  s,d=self.bundle;pending=plots.render_five(s,d);reviewed=plots.render_five(s,d,reviewed=True)
  self.assertEqual(tuple(pending),plots.FIGURE_NAMES)
  for name in plots.FIGURE_NAMES[1:3]:
   ids=[line.get_gid() for ax in pending[name].axes for line in ax.lines if line.get_gid() in STARTS]
   self.assertEqual(sorted(ids),list(STARTS))
  matrix=[ax for ax in pending[plots.FIGURE_NAMES[3]].axes if ax.images]
  self.assertEqual(len(matrix),4)
  for ax,field in zip(matrix,('real_trading_net_pnl','balance_max_dd_pct','balance_sharpe','total_transferred')):
   for _,row in s.iterrows():
    if field=='balance_sharpe' and not row.balance_returns_defined:continue
    expected=row[field]/1000 if field in {'real_trading_net_pnl','total_transferred'} else row[field]
    self.assertAlmostEqual(float(ax.images[0].get_array()[int(row.start[:4])-2015,MONTHS.index(int(row.start[5:7]))]),expected)
  for ax in matrix:
   self.assertEqual(ax.images[0].get_array().shape,(12,5))
   self.assertTrue(np.ma.getmaskarray(ax.images[0].get_array())[-1,-1])
   self.assertTrue(any(t.get_text()=='FUTURE' for t in ax.texts))
  nav=pending[plots.FIGURE_NAMES[0]].axes[0].lines[0]
  np.testing.assert_array_equal(nav.get_ydata(),d.loc[d.start.eq('2015-01-01'),'account_nav'])
  self.assertLess(pending[plots.FIGURE_NAMES[0]].axes[0].get_ylim()[0],0)
  for name,fig in pending.items():
   other=reviewed[name]
   self.assertIn('PENDING',fig._suptitle.get_text());self.assertIn('REVIEWED',other._suptitle.get_text())
   text=' '.join(t.get_text() for t in fig.texts)
   self.assertIn('NO_PROMOTION',text);self.assertIn('deposits INCLUDED',text);self.assertIn('59 fresh',text)
   for a,b in zip(fig.axes,other.axes):
    self.assertEqual(a.get_ylim(),b.get_ylim());self.assertEqual(a.get_xlim(),b.get_xlim())
    for x,y in zip(a.lines,b.lines):np.testing.assert_array_equal(x.get_ydata(),y.get_ydata())
    for x,y in zip(a.images,b.images):np.testing.assert_array_equal(x.get_array(),y.get_array())
   fig.clear();other.clear()


if __name__=='__main__':unittest.main()
