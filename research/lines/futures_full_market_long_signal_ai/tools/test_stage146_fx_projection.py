"""Small source-clock fixtures; no native data, fit, or cash."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
P=Path(__file__).with_name('stage146_fx_projection.py')
s=importlib.util.spec_from_file_location('fx146',P)
m=importlib.util.module_from_spec(s) if P.exists() else None
if m is not None:s.loader.exec_module(m)

class FxProjection(unittest.TestCase):
 def setUp(self):
  self.assertIsNotNone(m,'source projection is not implemented')
 def source(self):
  return pd.DataFrame({'date':['2020-01-02','2020-01-03','2020-01-06','2020-01-07'], 'USD_per_EUR':[2.,2.,2.,2.], 'CNY_per_EUR':[12.,14.,16.,18.]})
 def test_same_day_and_future_rows_cannot_change_past(self):
  src=self.source();a=m.project_dates(src,['2020-01-07']).iloc[0]
  src.loc[3,['USD_per_EUR','CNY_per_EUR']]=[100.,1.]
  src=pd.concat([src,pd.DataFrame({'date':['2020-01-08'],'USD_per_EUR':[1.],'CNY_per_EUR':[999.]})],ignore_index=True)
  b=m.project_dates(src,['2020-01-07']).iloc[0]
  self.assertAlmostEqual(a.q,np.log(7/6));self.assertEqual(a.to_dict(),b.to_dict())
  self.assertEqual((a.n_date,a.d_date,a.w_date),('2020-01-06','2020-01-03','2020-01-02'))
  self.assertEqual(a.assigned_time,'2020-01-07T08:00:00+08:00');self.assertEqual(a.decision_time,'2020-01-07T15:00:00+08:00')
  self.assertEqual((a.n_age_days,a.d_age_days,a.w_age_days),(1,4,5))
 def test_missing_immediate_leg_cannot_skip_to_older_valid_row(self):
  src=self.source();src.loc[1,'CNY_per_EUR']=np.nan
  a=m.project_dates(src,['2020-01-07']).iloc[0]
  self.assertEqual(a.fx_missing,1);self.assertTrue(np.isnan(a.q));self.assertEqual(a.d_date,'2020-01-03')
 def test_finalization_row_missing_leg_is_not_a_valid_bridge(self):
  src=self.source();src.loc[2,'USD_per_EUR']=np.nan
  a=m.project_dates(src,['2020-01-07']).iloc[0]
  self.assertEqual(a.fx_missing,1);self.assertTrue(np.isnan(a.q))
 def test_all_mothers_survive_even_without_reference_or_observation(self):
  moms=pd.DataFrame({'sequence_index':[0,1,2], 'event_id':['p0','p1','p2'], 'u_date':['2020-01-07','2020-01-07','2020-01-08'], 'reference_epoch':['','','x'], 'observation_state':['no_observation','missing','observed']})
  out=m.project_mothers(self.source(),moms)
  self.assertEqual(out.event_id.tolist(),['p0','p1','p2']);self.assertEqual(out.fx_missing.tolist(),[0,0,0]);self.assertEqual(out.q.iloc[0],out.q.iloc[1])
if __name__=='__main__':unittest.main()
