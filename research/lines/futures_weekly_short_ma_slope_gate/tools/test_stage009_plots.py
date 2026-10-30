"""SYNTHETIC ONLY: complete-scope rendering and metadata rejection tests."""
import os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/stage009-plots-mpl')
import unittest
import numpy as np
import pandas as pd
try:
 from stage009_plots import render_five,FIGURE_NAMES
except ImportError:
 render_five=None
 FIGURE_NAMES=('01_full_2015_nav_drawdown.png','02_january_starts_nav.png','03_june_starts_nav.png','04_reserve_effect_heatmaps.png','05_cohort_reserve_summary.png')
STARTS=tuple(f'{y}-{m:02d}-01' for y in range(2015,2027) for m in (1,6) if (y,m)<=(2026,1))
VARIANTS=('A_idle','A_R','C_idle','C_R')

def synthetic_bundle():
 """Exactly141996 synthetic points; deliberately NOT an exchange calendar."""
 calendars=[pd.bdate_range(s,'2026-10-29') for s in STARTS];total=sum(len(x) for x in calendars)
 counts=[len(x)*35499//total for x in calendars]
 for i in range(35499-sum(counts)):counts[i]+=1
 daily=[];summary=[];pairs=[]
 for i,(start,calendar,n) in enumerate(zip(STARTS,calendars,counts)):
  dates=calendar[np.linspace(0,len(calendar)-1,n).astype(int)];progress=np.linspace(0,1,n);eligible=start!='2026-01-01'
  for variant in VARIANTS:
   arm=variant[0];reserve=variant.endswith('_R');bonus=12000*(i%3-1) if reserve else 0.;equity=300000+(10000+i*3000+bonus+(4000 if arm=='C' else 0))*progress+1800*np.sin(progress*15)
   transfer=(min(140000,5000+i*6000)*progress if reserve else progress*0);remaining=150000-transfer;trading=equity-remaining;pnl=np.diff(np.r_[300000,equity]);nav=equity/300000;dd=(equity/np.maximum.accumulate(np.r_[300000,equity])[1:]-1)*100
   d=pd.DataFrame(dict(start=start,variant=variant,date=dates.strftime('%Y-%m-%d'),total_account_equity=equity,trading_account_equity=trading,reserve_balance=remaining,cumulative_transfer=transfer,net_pnl=pnl,nav=nav,drawdown_pct=dd));daily.append(d)
   ret=np.diff(np.r_[300000,equity])/np.r_[300000,equity[:-1]];sharpe=float(ret.mean()/ret.std(ddof=1)*np.sqrt(252))
   summary.append(dict(start=start,variant=variant,arm=arm,mode='reserve' if reserve else 'idle',actual_start=str(d.date.iloc[0]),actual_end='2026-10-29',trading_days=n,vote_eligible=eligible,observation_only=not eligible,end_equity=equity[-1],total_return_pct=(equity[-1]/300000-1)*100,max_dd_pct=dd.min(),sharpe=sharpe,total_slippage=100.,modeled_fill_count=20,total_transferred=transfer[-1],reserve_end_balance=remaining[-1],trading_end_equity=trading[-1],nonpositive_total_equity_days=0,nonpositive_trading_equity_days=0))
  for arm in ['A','C']:
   a=next(r for r in summary if r['start']==start and r['variant']==arm+'_idle');c=next(r for r in summary if r['start']==start and r['variant']==arm+'_R')
   def cmp(k):return 0 if np.isclose(a[k],c[k],rtol=1e-10,atol=1e-6) else (1 if c[k]>a[k] else -1)
   gates=dict(equity_gate=cmp('end_equity')>0,dd_gate=cmp('max_dd_pct')>=0,sharpe_gate=cmp('sharpe')>=0)
   pairs.append(dict(start=start,arm=arm,cohort='January' if start[5:7]=='01' else 'June',eligible=eligible,vote_eligible=eligible,observation_only=not eligible,**gates,three_gate_pass=all(gates.values())))
 return pd.DataFrame(summary),pd.DataFrame(pairs),pd.concat(daily,ignore_index=True)

class PlotTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.bundle=synthetic_bundle()
 def setUp(self):self.assertIsNotNone(render_five,'Stage009 pure plot renderer missing')
 def test_exact_five_names_four_curves_and_review_changes_titles_only(self):
  s,p,d=self.bundle;pending=render_five(s,p,d);reviewed=render_five(s,p,d,reviewed=True)
  self.assertEqual(tuple(pending),FIGURE_NAMES);self.assertEqual(tuple(reviewed),FIGURE_NAMES)
  self.assertEqual(len(pending[FIGURE_NAMES[0]].axes[0].lines),5)
  for name,fig in pending.items():
   other=reviewed[name];self.assertIn('PENDING',fig._suptitle.get_text());self.assertIn('REVIEWED',other._suptitle.get_text());self.assertEqual(len(fig.axes),len(other.axes))
   for a,b in zip(fig.axes,other.axes):
    self.assertEqual(a.get_xlim(),b.get_xlim());self.assertEqual(a.get_ylim(),b.get_ylim());self.assertEqual(len(a.lines),len(b.lines));self.assertEqual(len(a.images),len(b.images))
    for x,y in zip(a.lines,b.lines):np.testing.assert_array_equal(x.get_ydata(),y.get_ydata())
    for x,y in zip(a.images,b.images):np.testing.assert_array_equal(x.get_array(),y.get_array())
   fig.clear();other.clear()
 def test_rejects_missing_duplicate_or_wrong_window_summary(self):
  s,p,d=self.bundle
  for bad in [s.iloc[:-1],pd.concat([s.iloc[:-1],s.iloc[[0]]]),s.assign(arm='A')]:
   with self.assertRaises(ValueError):render_five(bad,p,d)
  bad=s.copy();bad.loc[0,'actual_end']='2026-10-28'
  with self.assertRaises(ValueError):render_five(bad,p,d)
 def test_observation_never_votes_and_missing_pairs_fail_closed(self):
  s,p,d=self.bundle
  for bad in [p.iloc[:-1],p.assign(vote_eligible=True)]:
   with self.assertRaises(ValueError):render_five(s,bad,d)
  bad=p.copy();bad.loc[0,'equity_gate']=not bool(bad.loc[0,'equity_gate'])
  with self.assertRaises(ValueError):render_five(s,bad,d)
 def test_rejects_truncated_duplicate_or_wrong_capital_daily_curve(self):
  s,p,d=self.bundle
  for bad in [d.iloc[:-1],pd.concat([d.iloc[:-1],d.iloc[[0]]])]:
   with self.assertRaises(ValueError):render_five(s,p,bad)
  bad=d.copy();bad['nav']=bad.total_account_equity/150000
  with self.assertRaises(ValueError):render_five(s,p,bad)
 def test_transfers_cannot_be_counted_as_profit_or_release_idle_reserve(self):
  s,p,d=self.bundle;bad=d.copy();bad.loc[100,'net_pnl']+=5000
  with self.assertRaises(ValueError):render_five(s,p,bad)
  bad=d.copy();bad.loc[0,'reserve_balance']-=100
  with self.assertRaises(ValueError):render_five(s,p,bad)
if __name__=='__main__':unittest.main()
