import copy,importlib.util,unittest
from pathlib import Path
import numpy as np
import pandas as pd
MODULE=Path(__file__).with_name('stage006_report.py')
def subject():
 s=importlib.util.spec_from_file_location('report',MODULE);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class ReportTests(unittest.TestCase):
 def pre(self,enabled=True):return dict(arm='C' if enabled else 'A',short_ma_slope_gate_enabled=False,long_ma_slope_gate_enabled=False,short_price_range_gate_enabled=enabled,short_price_range_threshold=.2,short_price_range_history='all_available_same_physical_epoch_daily_through_signal')
 def price(self,enabled=True):return dict(accepted=True,enabled=enabled,applied_block_count=2 if enabled else 0,decision_count=40,would_block_count=12,threshold_fraction=.2,comparison='signal_close_lte_low_plus_fraction_times_range',history_scope='all_available_same_physical_epoch_daily_through_signal',price_field='signal_day_close',range_fields=['low','high'],includes_signal_day=True,rollover_gate_applied=False,flat_range_policy='reject',listing_start_completeness_proven=False)
 def test_baseline_diagnostics_can_exist_without_applying_gate(self):
  m=subject();m.validate_gate(self.pre(False),{'enabled':False},self.price(False),'baseline');x=self.price(False);x['applied_block_count']=1
  with self.assertRaises(ValueError):m.validate_gate(self.pre(False),{'enabled':False},x,'baseline')
 def test_candidate_contract_keeps_fixed20_and_full_epoch_daily(self):
  m=subject();m.validate_gate(self.pre(),{'enabled':False},self.price(),'candidate')
  for k,v in [('short_ma_slope_gate_enabled',True),('long_ma_slope_gate_enabled',True),('short_price_range_threshold',.25),('short_price_range_history','accepted_weekly_only')]:
   p=self.pre();p[k]=v
   with self.assertRaises(ValueError):m.validate_gate(p,{'enabled':False},self.price(),'candidate')
 def test_ast_only_changes_one_gate_and_two_date_constants(self):
  m=subject();tree,r=m.price_loader_ast();self.assertEqual(r['replaced_gate_checks'],1);self.assertEqual(r['replaced_date_constants'],{'2020-01-01':1,'2020-01-02':1});self.assertFalse(r['arm_check_changed']);self.assertIn('arm_role_mismatch',r['retained_raise_labels']);self.assertIn('daily_equity_conservation',r['retained_string_literals']);self.assertTrue(r['original_source_unchanged'])
 def test_nav_dd_include_independent_initial_capital(self):
  m=subject();n,d=m.nav_drawdown([120000.,180000.,150000.]);np.testing.assert_allclose(n,[.8,1.2,1]);np.testing.assert_allclose(d,[-20,0,-100/6])
 def test_2015_window_cannot_be_2020_concatenation(self):
  m=subject();a=dict(preflight=dict(start='2015-01-01',end='2026-10-29',data_identity={'x':'same'}),daily=pd.DataFrame({'date':pd.to_datetime(['2015-01-05','2026-10-29'])}),settings={},effective={},database_sha256='same');m.same_contract(a,copy.deepcopy(a));c=copy.deepcopy(a);c['daily'].iloc[0,0]=pd.Timestamp('2020-01-02')
  with self.assertRaises(ValueError):m.same_contract(a,c)
 def test_output_is_stage006_only(self):
  m=subject()
  with self.assertRaises(ValueError):m.require_output(m.LINE/'artifacts/stage005_comparison',m.FIGURE)
if __name__=='__main__':unittest.main()
