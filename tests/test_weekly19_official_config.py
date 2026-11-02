import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'examples/portfolio_backtesting'))
import qmt_roll_weekly19_official_config as cfg
class PolicyTest(unittest.TestCase):
 def test_live_cash_verification_is_explicitly_operator_manual(self):
  policy=cfg.build_weekly19_policy_manifest()['execution_policy']
  self.assertEqual(policy['cash_verification_mode'],'operator_manual_v1')
  self.assertEqual(policy['funding_credit'],'operator_review_of_actual_broker_cashflow_only')
  self.assertEqual(policy['risk_capital'],'actual_trading_account_equity_including_mark_to_market')
  self.assertFalse(policy['funding_transfer_api_enabled'])
 def test_full_frozen_settings_match_after_only_asset_resolution(self):
  raw=json.loads((cfg.ASSETS/'actual_settings.json').read_text())['settings'];actual=cfg.build_weekly19_strategy_overrides()
  self.assertEqual(set(raw),set(actual))
  for key,value in raw.items():
   if isinstance(value,str)and value.startswith('@ASSET/'):self.assertEqual(actual[key],str(cfg.ASSETS/value.split('/',1)[1]))
   else:self.assertEqual(actual[key],value,key)
 def test_candidate_preserves_negative_evidence_and_has_no_activation_side_effect(self):
  pointer=ROOT/'official_strategy_materials/CURRENT.json';before=pointer.read_bytes();m=cfg.build_weekly19_policy_manifest()
  self.assertEqual(before,pointer.read_bytes());self.assertFalse(m['production_qualified']);self.assertEqual(m['research']['natural_verdict'],'NO_PROMOTION')
  self.assertFalse(m['execution_policy']['reserve_participates_in_equity']);self.assertFalse(m['execution_policy']['funding_transfer_api_enabled'])
 def test_returned_policy_and_settings_cannot_mutate_fixed_source(self):
  a=cfg.build_weekly19_strategy_overrides();key=next(iter(a));a[key]='corrupted-fixture'
  self.assertNotEqual(cfg.build_weekly19_strategy_overrides()[key],'corrupted-fixture')
  m=cfg.build_weekly19_policy_manifest();m['execution_policy']['ai_enabled']=True
  self.assertFalse(cfg.build_weekly19_policy_manifest()['execution_policy']['ai_enabled'])
class LegacyRiskBoundaryTest(unittest.TestCase):
 def test_legacy_success_summary_cannot_authorize_current_weekly19(self):
  import qmt_roll_official_live_config as active
  result=active.build_official_live_risk_snapshot({'current_variant':{'deployable_pass':1,'days_over_100pct':0,'max_broker10_margin_to_equity_pct':10,'end_equity':999999}})
  self.assertEqual(result['allow_real_new_orders'],0);self.assertIsNone(result['balance']);self.assertFalse(result['source_snapshot_known'])
if __name__=='__main__':unittest.main()
