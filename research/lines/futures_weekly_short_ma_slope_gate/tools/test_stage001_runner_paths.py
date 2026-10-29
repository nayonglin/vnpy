import unittest
from copy import deepcopy
from pathlib import Path
from run_stage001 import normalize_settings, ROOT, FROZEN
class RunnerPaths(unittest.TestCase):
 def reference(self):
  import json
  return json.loads((FROZEN/'R_attempt003/actual_strategy_settings.json').read_text())[0]['actual']
 def test_declared_paths_and_start_normalize_without_parameters(self):
  r=self.reference();c=deepcopy(r);mapping=ROOT/'research/lines/futures_weekly_short_ma_slope_gate/outputs/test_mapping.csv'
  c['mapping_csv_path']=str(mapping);c['trade_start_date']='2020-01-01'
  for k,v in list(c.items()):
   if isinstance(v,str):c[k]=v.replace('/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/',str(ROOT)+'/')
  self.assertEqual(normalize_settings(c,r,mapping,{}),r)
 def test_risk_or_ma_changes_fail(self):
  for k,value in [('base_risk_ratio',0.999),('ma_short',6),('max_concurrent_positions',44),('enable_add_position',True)]:
   r=self.reference();c=deepcopy(r);m=Path('/private/tmp/no_such_mapping');c['mapping_csv_path']=str(m);c['trade_start_date']='2020-01-01';c[k]=value
   with self.assertRaises(ValueError):normalize_settings(c,r,m,{})
 def test_arbitrary_path_change_fails(self):
  r=self.reference();c=deepcopy(r);m=Path('/private/tmp/no_such_mapping');c['mapping_csv_path']=str(m);c['trade_start_date']='2020-01-01';c['product_universe_csv_path']='/private/tmp/other_pool.csv'
  with self.assertRaises(ValueError):normalize_settings(c,r,m,{})
if __name__=='__main__':unittest.main()
