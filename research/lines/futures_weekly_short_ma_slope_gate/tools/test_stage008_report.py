import copy,importlib.util,unittest
from pathlib import Path
import pandas as pd
MODULE=Path(__file__).with_name('stage008_report.py')
def subject():
 s=importlib.util.spec_from_file_location('r',MODULE);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class AggregateTests(unittest.TestCase):
 def fixture(self,m):
  rows=[]
  for start in m.acct.STARTS:
   meta=m.acct.window_meta(start)
   for arm in ['A','C']:
    observation=meta['observation_only'];c=arm=='C';equity=75000. if observation and c else (300000. if c else 150000.)
    rows.append(dict(start=start,arm=arm,cohort=meta['cohort'],vote_eligible=meta['vote_eligible'],observation_only=observation,actual_start=meta['actual_first_day'],actual_end=m.acct.END,trading_days=meta['trading_days'],end_equity=equity,total_return_pct=(equity/150000.-1)*100,max_dd_pct=-80. if observation and c else (-10. if c else -20.),sharpe=-1. if observation and c else (1.2 if c else 1.),total_slippage=100.,modeled_fill_count=20,nonpositive_equity_days=0,actual_margin_to_equity_max_pct=50.,actual_margin_over100_days=0,nonpositive_equity_risk_ratio_undefined_days=0))
  return pd.DataFrame(rows)
 def test_all46_required_no_duplicate_or_missing_arm(self):
  m=subject();s=self.fixture(m);self.assertEqual(len(m.make_pairs(s)),23)
  for bad in [s.iloc[:-1],pd.concat([s,s.iloc[[0]]],ignore_index=True)]:
   with self.assertRaises(ValueError):m.make_pairs(bad)
 def test_under_one_year_observation_is_shown_but_never_votes(self):
  m=subject();s=self.fixture(m);p=m.make_pairs(s);a=m.aggregate(s,p);c=a[(a.cohort=='combined')&(a['sample']=='complete_ge_1y')].iloc[0];o=a[(a.cohort=='combined')&(a['sample']=='observation_lt_1y')].iloc[0]
  self.assertEqual(c.windows,22);self.assertEqual(c.return_wins,22);self.assertEqual(c.vote_windows,22);self.assertEqual(c.C_negative_return_count,0);self.assertEqual(o.windows,1);self.assertEqual(o.vote_windows,0);self.assertEqual(o.C_negative_return_count,1);self.assertEqual(len(p),23)
 def test_january_june_each_have_11_complete_votes(self):
  m=subject();s=self.fixture(m);a=m.aggregate(s,m.make_pairs(s));self.assertEqual(a[(a['sample']=='complete_ge_1y')&a.cohort.isin(['January','June'])].vote_windows.tolist(),[11,11])
 def test_unequal_duration_returns_have_no_expected_return_average(self):
  m=subject();s=self.fixture(m);a=m.aggregate(s,m.make_pairs(s));self.assertFalse(any('mean_return' in k or 'expected_return' in k for k in a.columns));self.assertIn('C_median_dd_pct',a);self.assertIn('C_worst_sharpe',a)
 def test_float_roundtrip_ties_do_not_create_fake_win(self):
  m=subject();self.assertEqual(m.compare_metric(1000000.+1e-8,1000000.),0);self.assertEqual(m.compare_metric(1000001.,1000000.),1)
 def test_equity_tie_never_passes_strict_higher_equity_gate(self):
  m=subject();s=self.fixture(m);s.loc[(s.start=='2017-01-01')&(s.arm=='C'),['end_equity','total_return_pct']]=[150000.,0.];p=m.make_pairs(s);r=p[p.start=='2017-01-01'].iloc[0];self.assertFalse(r.equity_gate);self.assertFalse(r.three_gate_pass)
 def test_wrong_vote_metadata_cannot_change_denominator(self):
  m=subject();s=self.fixture(m);s.loc[s.start.eq('2026-01-01'),'vote_eligible']=True
  with self.assertRaises(ValueError):m.make_pairs(s)
 def test_five_fixed_user_scope_figure_names(self):
  m=subject();self.assertEqual(len(m.FIGURE_NAMES),5);self.assertIn('02_january_starts_nav.png',m.FIGURE_NAMES);self.assertIn('03_june_starts_nav.png',m.FIGURE_NAMES);self.assertFalse(any('1year' in x or '2year' in x or '3year' in x for x in m.FIGURE_NAMES))
if __name__=='__main__':unittest.main()
