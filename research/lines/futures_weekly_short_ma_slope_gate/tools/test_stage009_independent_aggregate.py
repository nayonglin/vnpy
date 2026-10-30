"""Adversarial checks on new independent pure aggregate auditor."""
import unittest
import pandas as pd
import numpy as np
from stage009_independent_aggregate import recompute,merge_map,near

class AggregateAuditTests(unittest.TestCase):
 def raw(self):
  return pd.DataFrame(dict(date=['2026-01-05','2026-01-06','2026-01-07'],account_equity=[150000.,140000.,120000.],net_pnl=[0.,-10000.,-20000.],slippage=[0.,1.,2.],commission=[0.,0.,0.],trade_count=[0,1,1],total_margin_exact=[0.,15000.,30000.]))
 def event(self):
  return dict(date='2026-01-06',candidate_key='candidate1',raw_account_equity=140000.,trading_equity_before=140000.,transfer_amount=10000.,reserve_before=150000.,trading_equity_after=150000.,reserve_after=140000.,total_account_equity=290000.,cumulative_transfer=10000.)
 def test_internal_flow_never_changes_total_profit(self):
  _,idle,ic=recompute(self.raw(),[]);_,funded,fc=recompute(self.raw(),[self.event()])
  self.assertEqual(idle['net_pnl'],funded['net_pnl']);self.assertEqual(funded['end_equity'],270000.)
  self.assertEqual(funded['trading_end_equity'],130000.);self.assertEqual(funded['reserve_end_balance'],140000.)
  np.testing.assert_allclose(ic['nav'],fc['nav']);np.testing.assert_allclose(ic['drawdown_pct'],fc['drawdown_pct'])
 def test_self_consistent_event_with_fabricated_raw_fails(self):
  e=self.event();e.update(raw_account_equity=130000.,trading_equity_before=130000.,transfer_amount=20000.,reserve_after=130000.,total_account_equity=280000.,cumulative_transfer=20000.)
  with self.assertRaisesRegex(AssertionError,'event_raw_account_equity'):recompute(self.raw(),[e])
 def test_transfer_double_count_fails(self):
  with self.assertRaisesRegex(AssertionError,'no_duplicate_transfer'):recompute(self.raw(),[self.event(),self.event()])
 def test_inconsistent_raw_pnl_fails(self):
  raw=self.raw();raw.loc[2,'account_equity']+=10000
  with self.assertRaisesRegex(AssertionError,'raw_pnl'):recompute(raw,[])
 def test_negative_raw_not_automatically_total_failure(self):
  raw=self.raw();raw.loc[2,'account_equity']=-10000;raw.loc[2,'net_pnl']=-150000
  _,m,_=recompute(raw,[]);self.assertEqual(m['nonpositive_total_equity_days'],0);self.assertEqual(m['nonpositive_trading_equity_days'],1)
 def test_source_pin_collision_fails(self):
  with self.assertRaisesRegex(AssertionError,'conflicting_source_pin'):merge_map({'path':'old'},{'path':'new'})
 def test_old_round_status_requires_exact_string(self):
  near('DEFINED','DEFINED','round_status')
  with self.assertRaisesRegex(AssertionError,'round_status'):near('UNDEFINED','DEFINED','round_status')
 def test_nan_cannot_pass_metric_comparison(self):
  with self.assertRaises(AssertionError):near(float('nan'),0,'invalid_metric')
if __name__=='__main__':unittest.main()
