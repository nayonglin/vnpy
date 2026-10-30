"""Independent audit adapter counterexamples only. Never runs finance."""
from pathlib import Path
import json,tempfile,unittest
from copy import deepcopy
import pandas as pd
import stage014_independent_window as a
class IndependentAuditTests(unittest.TestCase):
 def test_wallet_changes_exactly_scope_not150k_or300k_economics(self):
  fn,p=a.funding_adapter(a.LINE/'outputs/data_stage014_20261030/data_approved');self.assertTrue(callable(fn));self.assertTrue(p['capital_R150_W300_and_all_economic_audit_expressions_unchanged']);self.assertEqual(p['only_expression_changed'],"frozen['planned_arm_windows']==46 and frozen['planned_financial_replays']==46")
 def test_original_parameters_allow_only_new_mapping_and_March_start(self):
  ref=a.LINE/'outputs/stage009_C_20150101_attempt001';data=a.LINE/'outputs/data_stage014_20261030/data_approved'
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);s=a.load(ref/'actual_strategy_settings.json');e=a.load(ref/'effective_parameters.json')
   for layer in ['actual','setting']:s[0][layer].update(trade_start_date='2015-03-01',mapping_csv_path=str(data/'mapping.csv'))
   e['spec']['overrides'].update(mapping_csv_path=str(data/'mapping.csv'))
   if 'trade_start_date' in e['spec']['overrides']:e['spec']['overrides']['trade_start_date']='2015-03-01'
   (p/'actual_strategy_settings.json').write_text(json.dumps(s));(p/'effective_parameters.json').write_text(json.dumps(e))
   for n in ['actual_daily_addon_configuration.json','entry_risk.csv']:(p/n).write_bytes((ref/n).read_bytes())
   self.assertTrue(a.parameter_audit(p,'2015-03-01',data)['all_effective_parameters_unchanged_except_declared_start_and_mapping'])
   s[0]['actual']['risk_ratio_open_interest_surge']=.018;(p/'actual_strategy_settings.json').write_text(json.dumps(s))
   with self.assertRaises(AssertionError):a.parameter_audit(p,'2015-03-01',data)
 def test_cashflow_account_return_undefined_after_nonpositive_prior_E(self):
  r=a.account_metrics([150000.,0.,100000.]);self.assertFalse(r['returns_defined']);self.assertIsNone(r['sharpe']);self.assertEqual(r['max_dd_pct'],-100.)
 def test_flat_account_is_defined_zero_sharpe(self):
  r=a.account_metrics([150000.,150000.]);self.assertTrue(r['returns_defined']);self.assertEqual(r['sharpe'],0.)
 def test_prefix_rejects_one_cent_PnL_drift(self):
  old=a.LINE/'outputs/stage009_C_20150101_attempt001'
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);d=pd.read_csv(old/'daily.csv');d.loc[10,'net_pnl']+=.01;d.to_csv(p/'daily.csv',index=False)
   with self.assertRaises(AssertionError):a.prefix_audit(p,old)
 def test_raw_empty_first_open_adapter_preserves_accounting_expressions(self):
  fn,p=a.raw_adapter();self.assertTrue(callable(fn));self.assertTrue(p['empty_first_open_signal_date_is_None']);self.assertTrue(p['all_FIFO_MTM_cost_fill_weekly_data_causality_expressions_unchanged'])
 def test_new30_execution_from29_signal_is_outside_old29_execution_prefix(self):
  old=a.LINE/'outputs/stage009_C_20150101_attempt001'
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)
   for name in ['daily.csv','reserve_daily.csv','trades.csv','execution_clock.csv','internal_equity_daily.csv','weekly_readiness.csv','weekly_bars.csv','execution_anchor_requests.csv','reserve_events.json','reserve_checks.json','reserve_snapshots.json','reserve_fill_phases.json']:(p/name).write_bytes((old/name).read_bytes())
   d=pd.read_csv(p/'execution_anchor_requests.csv');row=d.iloc[-1].copy();row['signal_date']='2026-10-29';row['trading_date']='2026-10-30';pd.concat([d,row.to_frame().T],ignore_index=True).to_csv(p/'execution_anchor_requests.csv',index=False)
   self.assertTrue(a.prefix_audit(p,old)['prefix_through_2026_10_29_unchanged'])
 def test_empty_round_payoff_and_PF_not_infinity(self):
  r=a.oldaudit.raw_audit.stats([]);self.assertEqual(r['count'],0);self.assertIsNone(r['payoff_ratio']);self.assertIsNone(r['profit_factor'])
if __name__=='__main__':unittest.main()
