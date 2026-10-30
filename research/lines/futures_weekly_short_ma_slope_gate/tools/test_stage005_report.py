import copy,importlib.util,unittest
from pathlib import Path
import numpy as np
import pandas as pd
MODULE=Path(__file__).with_name('stage005_report.py')
def subject():
 s=importlib.util.spec_from_file_location('report',MODULE);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class ReportTests(unittest.TestCase):
 def price(self):return dict(accepted=True,enabled=True,threshold_fraction=.2,comparison='signal_close_lte_low_plus_fraction_times_range',history_scope='all_available_same_physical_epoch_daily_through_signal',price_field='signal_day_close',range_fields=['low','high'],includes_signal_day=True,rollover_gate_applied=False,flat_range_policy='reject',listing_start_completeness_proven=False)
 def pre(self):return dict(arm='C',short_ma_slope_gate_enabled=False,long_ma_slope_gate_enabled=False,short_price_range_gate_enabled=True,short_price_range_threshold=.2,short_price_range_history='all_available_same_physical_epoch_daily_through_signal')
 def test_gate_contract_does_not_disguise_slope_flags(self):
  m=subject();pre=self.pre();m.validate_gate(pre,{'enabled':False},self.price())
  for k,v in [('short_ma_slope_gate_enabled',True),('long_ma_slope_gate_enabled',True),('short_price_range_threshold',.25),('short_price_range_history','accepted_weekly_only'),('short_price_range_gate_enabled',False)]:
   p=copy.deepcopy(pre);p[k]=v
   with self.assertRaises(ValueError):m.validate_gate(p,{'enabled':False},self.price())
 def test_acceptance_signal_price_inclusion_and_no_rollover_are_hard_contract(self):
  m=subject()
  for key,value in [('price_field','weekly_close'),('includes_signal_day',False),('rollover_gate_applied',True),('flat_range_policy','allow'),('listing_start_completeness_proven',True)]:
   proof=self.price();proof[key]=value
   with self.assertRaises(ValueError):m.validate_gate(self.pre(),{'enabled':False},proof)
 def test_ast_adapter_changes_one_gate_check_preserves_arm_and_accounting(self):
  m=subject();tree,receipt=m.price_loader_ast();self.assertEqual(receipt['replaced_gate_checks'],1);self.assertTrue(receipt['original_source_unchanged']);self.assertIn('arm_role_mismatch',receipt['retained_raise_labels']);self.assertIn('daily_equity_conservation',receipt['retained_string_literals'])
 def test_nav_and_dd_include_initial_capital(self):
  m=subject();n,d=m.nav_drawdown([120000.,180000.,150000.]);np.testing.assert_allclose(n,[.8,1.2,1.]);np.testing.assert_allclose(d,[-20.,0.,-100/6])
 def test_same_source_and_dates_are_required(self):
  m=subject();base=dict(preflight=dict(start='2020-01-01',end='2026-10-29',data_identity={'x':'y'}),daily=pd.DataFrame({'date':pd.to_datetime(['2020-01-02','2026-10-29'])}),settings={'x':1},effective={'x':1},database_sha256='same')
  m.same_contract(base,copy.deepcopy(base));other=copy.deepcopy(base);other['settings']['x']=2
  with self.assertRaises(ValueError):m.same_contract(base,other)
 def test_output_stays_stage005(self):
  m=subject()
  with self.assertRaises(ValueError):m.require_output(m.LINE/'artifacts/stage004_comparison',m.FIGURE)
if __name__=='__main__':unittest.main()
