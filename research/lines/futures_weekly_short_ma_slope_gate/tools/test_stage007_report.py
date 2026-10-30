import copy,importlib.util,unittest
from pathlib import Path
import numpy as np
MODULE=Path(__file__).with_name('stage007_report.py')
def subject():
 s=importlib.util.spec_from_file_location('r',MODULE);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class ReportTests(unittest.TestCase):
 def pre(self):return dict(long_price_range_gate_enabled=True,long_price_range_threshold=.8,long_price_range_history='all_available_same_physical_epoch_daily_strictly_before_signal',long_breakout_above_prior_high_exempt=True)
 def proof(self):return dict(accepted=True,enabled=True,top_fraction=.2,position_threshold=.8,comparison='prior_low_plus_0p8_range_lte_signal_close_lte_prior_high',history_scope='all_available_same_physical_epoch_daily_strictly_before_signal',price_field='signal_day_close',range_fields=['low','high'],includes_signal_day=False,breakout_exemption=True,breakout_rule='signal_close_strictly_gt_prior_high',rollover_gate_applied=False,flat_range_policy='equal_high_block_above_high_exempt_below_high_allow',signals=['long_case1a','long_case2'],listing_start_completeness_proven=False)
 def test_long_gate_prior_scope_and_breakout_are_strict_contract(self):
  m=subject();m.validate_long_gate(self.pre(),self.proof())
  for k,v in [('includes_signal_day',True),('breakout_rule','close_gte_prior_high'),('position_threshold',.2),('signals',['long_case1a']),('rollover_gate_applied',True),('flat_range_policy','allow_all')]:
   d=self.proof();d[k]=v
   with self.assertRaises(ValueError):m.validate_long_gate(self.pre(),d)
 def test_preflight_true_and_point8_are_required(self):
  m=subject()
  for k,v in [('long_price_range_gate_enabled',False),('long_price_range_threshold',.2),('long_breakout_above_prior_high_exempt',False)]:
   p=self.pre();p[k]=v
   with self.assertRaises(ValueError):m.validate_long_gate(p,self.proof())
 def test_nav_dd_preserves_independent_initial_capital(self):
  m=subject();n,d=m.nav_drawdown([120000,180000,150000]);np.testing.assert_allclose(n,[.8,1.2,1]);np.testing.assert_allclose(d,[-20,0,-100/6])
 def test_only_declared_source_roles_and_assigned_output(self):
  m=subject();self.assertEqual(set(m.PATHS),{'original','short_only','long_top20'})
  with self.assertRaises(ValueError):m.require_output(m.LINE/'artifacts/stage006_comparison',m.FIGURE)
if __name__=='__main__':unittest.main()
