import importlib.util,json,unittest
from pathlib import Path
import pandas as pd
HERE=Path(__file__).parent

def load():
 p=HERE/'stage096_quarter_pair_overview.py';assert p.exists(),'pair overview missing';s=importlib.util.spec_from_file_location('pair096',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def fixture(m,enabled):
 return dict(long_weekly_filter=enabled,parameters=dict(stage068_risk_fraction=.0025),hashes={k:'abc' for k in m.SHARED_TABLES},code_snapshot_hashes={k:'same' for k in m.COMMON_CODE})

class PairOverviewTest(unittest.TestCase):
 def test_pair_curves_reuse_original_plot_all_points_and_link_axes(self):
  m=load();d=pd.DataFrame({'date':['2020-01-01','2020-01-02','2020-01-03']});dates=pd.to_datetime(d.date)
  def bundle(e):
   e=pd.Series(e);p=e.cummax().clip(lower=100);dd=(e/p-1)*100
   return dict(d=d,dates=dates,equity=e,peak=p,capital=100.,dd_pct=dd,trough=int(dd.idxmin()),facts=dict(max_drawdown_trough_date='2020-01-02'))
  a,b=bundle([100,90,110]),bundle([100,80,120]);fig,html=m.pair_plot(a,b);self.assertEqual(len(fig.data),8)
  self.assertEqual(list(fig.data[0].y),[.01,.009,.011]);self.assertEqual(list(fig.data[4].y),[.01,.008,.012]);self.assertTrue(fig.layout.xaxis.matches=='x2' or fig.layout.xaxis2.matches=='x');self.assertTrue(str(fig.data[4].name).startswith('周过滤关闭'));self.assertLess(fig.layout.yaxis2.range[0],-20)
 def test_pair_modes_not_half_percent_or_nonmatching_parameters(self):
  m=load();a,b=fixture(m,True),fixture(m,False);m.check_pair_identity(a,b)
  b['parameters']['risk_ratio']=.03
  with self.assertRaisesRegex(ValueError,'pair_parameters'):m.check_pair_identity(a,b)
  a,b=fixture(m,True),fixture(m,False);b['long_weekly_filter']=True
  with self.assertRaisesRegex(ValueError,'pair_modes'):m.check_pair_identity(a,b)

if __name__=='__main__':unittest.main()
