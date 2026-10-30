"""Mutation checks for the independent Stage011 risk auditor; no engine."""
from copy import deepcopy
from pathlib import Path
import json,tempfile,unittest
import pandas as pd
import stage011_independent_window as audit
import stage011_independent_aggregate as aggregate

class IndependentRiskMutationTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
  self.old=audit.LINE/'outputs/stage009_A_20150101_attempt001'
  self.settings=json.loads((self.old/'actual_strategy_settings.json').read_text())
  for scope in ['setting','actual']:
   for k in audit.DELTA:self.settings[0][scope][k]=.018
  self.effective=json.loads((self.old/'effective_parameters.json').read_text())
  for k in audit.DELTA:self.effective['spec']['overrides'][k]=.018
  self.risk=pd.read_csv(self.old/'entry_risk.csv');self.risk.risk_ratio=.018
  self.risk.risk_amount_before_directional_30d_boost=(self.risk.limited_balance*.018).clip(lower=1000.,upper=50000000.)*self.risk.risk_multiplier
  self.risk.target_risk_amount=self.risk.risk_amount_before_directional_30d_boost*self.risk.directional_30d_risk_boost_multiplier
 def tearDown(self):self.temp.cleanup()
 def run_audit(self):
  (self.path/'actual_strategy_settings.json').write_text(json.dumps(self.settings));(self.path/'effective_parameters.json').write_text(json.dumps(self.effective));self.risk.to_csv(self.path/'entry_risk.csv',index=False)
  return audit.parameter_audit(self.path,self.old)
 def test_accepts_exact_three_parameter_delta(self):self.assertEqual(self.run_audit()['actual_entry_base_rates'],[.018])
 def test_rejects_extra_parameter_change(self):
  self.settings[0]['actual']['ma_short']=6
  with self.assertRaisesRegex(AssertionError,'only_three_strategy_parameter_deltas'):self.run_audit()
 def test_rejects_second_04_scale(self):
  self.risk.risk_amount_before_directional_30d_boost*=.4;self.risk.target_risk_amount*=.4
  with self.assertRaisesRegex(AssertionError,'independent_floor_capped_scaled_risk_amount'):self.run_audit()
 def test_rejects_unmodified_special_entry_rate(self):
  self.risk.loc[self.risk.index[0],'risk_ratio']=.06
  with self.assertRaisesRegex(AssertionError,'every_actual_entry_base_rate_0018'):self.run_audit()
 def test_rejects_OI_double_removed(self):
  self.settings[0]['actual']['oi_price_confirm_risk_restore_multiplier']=1.
  with self.assertRaisesRegex(AssertionError,'only_three_strategy_parameter_deltas'):self.run_audit()
class AggregateComparisonTests(unittest.TestCase):
 def test_equal_vector_has_one_boolean_result(self):aggregate.near([1.,2.],[1.,2.],'vector')
 def test_vector_mismatch_is_rejected(self):
  with self.assertRaises(AssertionError):aggregate.near([1.,2.],[1.,3.],'vector')
 def test_scalar_null_and_nan_are_equivalent(self):aggregate.near(None,float('nan'),'undefined')
if __name__=='__main__':unittest.main()
