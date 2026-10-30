"""Three declared risk deltas must fail closed for every sizing context."""
import importlib.util
import unittest
from copy import deepcopy
import pandas as pd


class UniformRiskTests(unittest.TestCase):
 def subject(self):
  self.assertIsNotNone(importlib.util.find_spec('stage011_risk'), 'Stage011 risk helper missing')
  import stage011_risk as risk
  return risk

 def fixture(self):
  risk=self.subject()
  original={**risk.OLD_RISK, 'risk_ratio_of_total_assets':.018, 'risk_ratio_breakout':.018, 'risk_ratio_ma_cross_breakout':.018, 'min_risk_per_trade':1000, 'oi_price_confirm_risk_restore_multiplier':2., 'directional_30d_risk_boost_multiplier':1.5, 'directional_30d_low_volume_risk_multiplier':.5}
  return risk,original

 def test_only_three_actual_risk_parameters_change_without_second_scaling(self):
  risk,old=self.fixture();current=risk.uniform_overrides(old)
  self.assertEqual({k:v for k,v in current.items() if old.get(k)!=v},risk.NEW_RISK)
  self.assertEqual(risk.restore_reference_risk(current,old),old)
  self.assertEqual(old['risk_ratio_open_interest_surge'],.06)

 def test_unknown_original_risk_and_nonuniform_candidate_fail_closed(self):
  risk,old=self.fixture()
  with self.assertRaises(ValueError):risk.uniform_overrides(dict(old,risk_ratio_open_interest_surge=.04))
  for key in risk.NEW_RISK:
   current=risk.uniform_overrides(old);current[key]=.018*.4
   with self.subTest(key=key),self.assertRaises(ValueError):risk.restore_reference_risk(current,old)

 def test_settings_spec_and_entry_ledger_preserve_every_other_field(self):
  risk,old=self.fixture();baseline=[dict(strategy_class='HistoricalSafetyStrategy',setting=old,actual=deepcopy(old),engine_capital=150000)]
  candidate=deepcopy(baseline)
  for key in ['setting','actual']:candidate[0][key]=risk.uniform_overrides(candidate[0][key])
  effective=dict(spec=dict(capital=dict(risk_multiplier=.4,account_capital=150000),overrides={'enable_add_position':False}),sizes={'x':10},rates={'x':0},slippages={'x':1})
  new_effective=deepcopy(effective);new_effective['spec']['overrides']=risk.uniform_overrides(new_effective['spec']['overrides'])
  entries=pd.DataFrame(dict(entry_context=['flat_entry','rollover_reopen'],risk_mode=['open_interest_surge','open_interest_decline'],risk_ratio=[.018,.018],sizing_method=['risk_budget']*2))
  proof=risk.accept_uniform_risk(candidate,baseline,new_effective,effective,entries)
  self.assertTrue(proof['accepted']);self.assertEqual(proof['entry_risk_count'],2)
  for mutate in ['oi_price_confirm_risk_restore_multiplier','min_risk_per_trade']:
   bad=deepcopy(candidate);bad[0]['actual'][mutate]+=1
   with self.subTest(mutate=mutate),self.assertRaises(ValueError):risk.accept_uniform_risk(bad,baseline,new_effective,effective,entries)
  bad=entries.copy();bad.loc[1,'risk_ratio']=.025
  with self.assertRaises(ValueError):risk.accept_uniform_risk(candidate,baseline,new_effective,effective,bad)
  bad=deepcopy(new_effective);bad['spec']['capital']['risk_multiplier']=.16
  with self.assertRaises(ValueError):risk.accept_uniform_risk(candidate,baseline,bad,effective,entries)
  for missing in ['risk_ratio_breakout','min_risk_per_trade']:
   bad_old=deepcopy(baseline);bad_new=deepcopy(candidate)
   for data in [bad_old,bad_new]:
    for side in ['setting','actual']:del data[0][side][missing]
   with self.subTest(missing=missing),self.assertRaises(ValueError):risk.accept_uniform_risk(bad_new,bad_old,new_effective,effective,entries)

if __name__=='__main__':unittest.main()
