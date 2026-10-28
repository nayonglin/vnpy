import unittest
from copy import deepcopy
try:
 from run_stage032_daily_addon import validate_window, normalize_settings, normalize_effective, actual_addon_configuration
except ModuleNotFoundError:
 def missing(*a,**k):raise NotImplementedError('stage032_runner_not_implemented')
 validate_window=normalize_settings=normalize_effective=actual_addon_configuration=missing

class RunnerContractTests(unittest.TestCase):
 def test_2020_window_requires_latest_approved_complete_end(self):
  self.assertEqual(validate_window('2020-01-01','2026-10-28',{'data_ready':True,'date_end':'2026-10-28','data_ready_for_bounded_replay':True}),('2020-01-01','2026-10-28'))
 def test_different_start_or_mismatched_end_rejected(self):
  for start,end,r in [('2015-01-01','2026-10-28',{'date_end':'2026-10-28'}),('2020-01-01','2026-10-28',{'date_end':'2026-10-27'})]:
   with self.assertRaises(ValueError):validate_window(start,end,r)
 def test_unready_partial_snapshot_rejected(self):
  for key in ['data_ready','data_ready_for_bounded_replay']:
   r={'data_ready':True,'data_ready_for_bounded_replay':True,'date_end':'2026-10-28'};r[key]=False
   with self.assertRaises(ValueError):validate_window('2020-01-01','2026-10-28',r)
 def test_actual_addon_flag_must_match_requested_arm(self):
  from types import SimpleNamespace
  for flag in [False,True]:
   st=SimpleNamespace(research_daily_addon_enabled=flag)
   self.assertEqual(actual_addon_configuration(st,flag)['enabled'],flag)
   with self.assertRaises(ValueError):actual_addon_configuration(st,not flag)
 def base_settings(self):return dict(mapping_csv_path='/old/map.csv',trade_start_date='2015-01-01',margin_ratio_overrides='cu2612.SHFE=0.12',risk=.4)
 def test_only_mapping_start_can_change_settings(self):
  old=self.base_settings();new={**old,'mapping_csv_path':'/new/map.csv','trade_start_date':'2020-01-01'};saved=deepcopy(new)
  self.assertEqual(normalize_settings(new,old,'/new/map.csv',{}),old);self.assertEqual(new,saved)
 def test_any_other_setting_drift_rejected(self):
  old=self.base_settings();new={**old,'mapping_csv_path':'/new/map.csv','trade_start_date':'2020-01-01','risk':.8}
  with self.assertRaises(ValueError):normalize_settings(new,old,'/new/map.csv',{})
 def test_wrong_start_or_mapping_rejected(self):
  old=self.base_settings()
  for patch in [dict(mapping_csv_path='/wrong'),dict(trade_start_date='2018-01-01')]:
   new={**old,'mapping_csv_path':'/new/map.csv','trade_start_date':'2020-01-01',**patch}
   with self.assertRaises(ValueError):normalize_settings(new,old,'/new/map.csv',{})
 def effective(self):return dict(sizes={'cu2612.SHFE':5},slippages={'cu2612.SHFE':10.},rates={'cu2612.SHFE':0.},spec={'overrides':self.base_settings(),'capital':150000})
 def test_effective_only_declared_window_mapping_delta(self):
  old=self.effective();new=deepcopy(old);new['spec']['overrides'].update(mapping_csv_path='/new/map.csv',trade_start_date='2020-01-01')
  self.assertEqual(normalize_effective(new,old,'/new/map.csv',{}),old)
 def test_real_effective_overrides_without_setting_only_fields(self):
  old=self.effective()
  for key in ['margin_ratio_overrides','trade_start_date']:del old['spec']['overrides'][key]
  new=deepcopy(old);new['spec']['overrides']['mapping_csv_path']='/new/map.csv'
  self.assertEqual(normalize_effective(new,old,'/new/map.csv',{}),old)
 def test_unapproved_metadata_new_key_rejected(self):
  old=self.effective();new=deepcopy(old);new['sizes']['cu2701.SHFE']=5
  with self.assertRaises(ValueError):normalize_effective(new,old,'/old/map.csv',{})
 def test_existing_metadata_value_cannot_be_repaired(self):
  old=self.effective();new=deepcopy(old);new['sizes']['cu2612.SHFE']=10
  with self.assertRaises(ValueError):normalize_effective(new,old,'/old/map.csv',{})
 def test_approved_new_contract_exact_values_only(self):
  old=self.effective();new=deepcopy(old);approved={'cu2701.SHFE':dict(size=5,slippage=10.,rate=0.,margin_ratio=.12)}
  new['spec']['overrides'].update(mapping_csv_path='/new/map.csv',trade_start_date='2020-01-01',margin_ratio_overrides='cu2612.SHFE=0.12,cu2701.SHFE=0.12')
  for k,v in [('sizes',5),('slippages',10.),('rates',0.)]:new[k]['cu2701.SHFE']=v
  self.assertEqual(normalize_effective(new,old,'/new/map.csv',approved),old)
  new['rates']['cu2701.SHFE']=.01
  with self.assertRaises(ValueError):normalize_effective(new,old,'/new/map.csv',approved)
if __name__=='__main__':unittest.main()
