"""Independent auditor mutation checks; no engine or old-file mutation."""
from pathlib import Path
from copy import deepcopy
import json,tempfile,unittest
import numpy as np
import stage013_independent_window as w
import stage013_independent_aggregate as aggregate
class AuditorTests(unittest.TestCase):
 def test_wallet_adapter_changes_only_named_wallet_expressions(self):
  fn,p=w.funding_adapter();self.assertTrue(p['raw150k_FIFOMTM_core_unchanged']);self.assertTrue(p['ordinary150k_funding_floor_unchanged']);self.assertEqual(sum(x['occurrences'] for x in p['explicit_replacements']),15)
 def test_original_risk_settings_and_real_entries_accept(self):
  p=w.LINE/'outputs/stage009_C_20150101_attempt001';r=w.parameter_audit(p,p);self.assertEqual(r['actual_risk_tiers']['open_interest_surge'],.06)
 def test_reject_stage011_uniform_risk_disguised_as_original(self):
  old=w.LINE/'outputs/stage009_C_20150101_attempt001'
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)
   for n in ['effective_parameters.json','entry_risk.csv']:(p/n).symlink_to(old/n)
   s=w.load(old/'actual_strategy_settings.json');s[0]['actual']['risk_ratio_open_interest_surge']=.018;(p/'actual_strategy_settings.json').write_text(json.dumps(s))
   with self.assertRaisesRegex(AssertionError,'all_settings_and_effective_exact_original_C'):w.parameter_audit(p,old)
 def test_prefix_matches_before_binding_and_rejects_wrong_partial_amount(self):
  old=w.LINE/'outputs/stage009_C_20170101_attempt001';ad=w.load(w.STAGES/'stage013_independent_reuse_admission.json');proof=next(x for x in ad['windows'] if x['start']=='2017-01-01')['first_binding']
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)
   for n in ['daily.csv','reserve_daily.csv','trades.csv']:(p/n).symlink_to(old/n)
   calls=w.load(old/'reserve_checks.json');row=next(x for x in calls if x['candidate_key']==proof['candidate_key']);row['transfer_amount']=proof['new100k_transfer'];row['cumulative_transfer']=100000.;(p/'reserve_checks.json').write_text(json.dumps(calls));r=w.prefix_audit(p,old,'2017-01-01',ad);self.assertTrue(r['all_trading_fields_identical_before_binding'])
   row['transfer_amount']+=1.;(p/'reserve_checks.json').write_text(json.dumps(calls))
   with self.assertRaisesRegex(AssertionError,'first_binding_actual_partial_transfer'):w.prefix_audit(p,old,'2017-01-01',ad)
 def test_E_returns_with_nonpositive_denominator_are_marked_undefined(self):
  r=w.curve([150000.,0.,100.],150000.,True);self.assertFalse(r['returns_defined']);self.assertEqual(r['sharpe'],0.)
class AggregateTests(unittest.TestCase):
 def test_vector_equality_is_scalar_boolean(self):aggregate.near([1.,2.],[1.,2.],'same')
 def test_vector_mismatch_rejected(self):
  with self.assertRaises(AssertionError):aggregate.near([1.,2.],[1.,3.],'different')
 def test_account_return_zero_denominator_is_undefined(self):
  r=aggregate.E_metrics(np.array([150000.,0.,100.]));self.assertFalse(r['balance_returns_defined']);self.assertEqual(r['balance_sharpe'],0.)
if __name__=='__main__':unittest.main()
