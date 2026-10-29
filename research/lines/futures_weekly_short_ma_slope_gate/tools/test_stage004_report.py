import copy,importlib.util,unittest
from pathlib import Path
import numpy as np
import pandas as pd
MODULE=Path(__file__).with_name('stage004_report.py')
def subject():
 s=importlib.util.spec_from_file_location('report',MODULE);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class ReportTests(unittest.TestCase):
 def test_nav_uses_initial_capital_and_drawdown_includes_initial_peak(self):
  m=subject();nav,dd=m.nav_drawdown(np.array([120000.,135000.,180000.,150000.]))
  np.testing.assert_allclose(nav,[.8,.9,1.2,1.]);np.testing.assert_allclose(dd,[-20.,-10.,0.,-100./6.])
 def test_nonfinite_or_nonpositive_nav_is_rejected(self):
  m=subject()
  for e in [[150000.,float('nan')],[150000.,0.],[150000.,-1.],[]]:
   with self.assertRaises(ValueError):m.nav_drawdown(e)
 def ledger(self):
  dates=pd.to_datetime(['2020-01-02','2026-10-29']);base=dict(preflight=dict(start='2020-01-01',end='2026-10-29',data_identity={'a':'x'},daily_addon_enabled=False),daily=pd.DataFrame({'date':dates}),settings={'x':1},effective={'x':1},database_sha256='x')
  a={k:copy.deepcopy(base) for k in ['original','short_only','symmetric','long_ma5']}
  for key,x in a.items():x['preflight'].update(short_ma_slope_gate_enabled=key!='original',long_ma_slope_gate_enabled=key in ['symmetric','long_ma5'])
  a['long_ma5']['preflight']['long_ma_slope_periods']=[5]
  a['long_ma5']['acceptances']={'long_ma_slope_acceptance.json':dict(accepted=True,enabled=True,MA_periods=[5],operator='SINGLE',rule='completed_week_MA5_current_lt_previous')}
  return a
 def test_same_contract_rejects_data_parameter_or_date_change(self):
  m=subject();a=self.ledger();m.require_same_contract(a)
  for key,value in [('settings',{'x':2}),('effective',{'x':2}),('database_sha256','other')]:
   b=copy.deepcopy(a);b['long_ma5'][key]=value
   with self.assertRaises(ValueError):m.require_same_contract(b)
  b=copy.deepcopy(a);b['long_ma5']['preflight']['data_identity']={'a':'other'}
  with self.assertRaises(ValueError):m.require_same_contract(b)
  b=copy.deepcopy(a);b['long_ma5']['daily'].loc[1,'date']=pd.Timestamp('2026-10-30')
  with self.assertRaises(ValueError):m.require_same_contract(b)
 def test_long_ma10_participation_cannot_be_mislabelled_ma5_only(self):
  m=subject();a=self.ledger();a['long_ma5']['acceptances']['long_ma_slope_acceptance.json']['MA_periods']=[5,10]
  with self.assertRaises(ValueError):m.require_same_contract(a)
 def test_output_is_independent_stage004_only(self):
  m=subject()
  for p in [m.LINE/'artifacts/stage002_comparison',m.LINE/'outputs/stage003_blocked_recap']:
   with self.assertRaises(ValueError):m.require_output(p,m.FIGURE)
if __name__=='__main__':unittest.main()
