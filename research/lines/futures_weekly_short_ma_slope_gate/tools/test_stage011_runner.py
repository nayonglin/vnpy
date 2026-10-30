import importlib.util,json,unittest
from copy import deepcopy


class UniformRunnerTests(unittest.TestCase):
 def subject(self):
  self.assertIsNotNone(importlib.util.find_spec('run_stage011'), 'Stage011 runner missing')
  import run_stage011 as runner
  return runner

 def test_reference_audit_accepts_only_three_uniform_parameters(self):
  runner=self.subject()
  old=json.loads((runner.FROZEN/'R_attempt003/actual_strategy_settings.json').read_text())[0]['actual']
  current=runner.uniform_overrides(old);mapping=runner.LINE/'outputs/stage011_test_mapping.csv'
  current.update(mapping_csv_path=str(mapping),trade_start_date='2020-06-01')
  for key,value in list(current.items()):
   if isinstance(value,str):current[key]=value.replace('/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/',str(runner.ROOT)+'/')
  self.assertEqual(runner.normalize_settings(current,old,str(mapping),{},'2020-06-01'),old)
  for key,value in [('capital_base',300000),('enable_add_position',True),('risk_ratio_open_interest_decline',.025)]:
   bad=deepcopy(current);bad[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):runner.normalize_settings(bad,old,str(mapping),{},'2020-06-01')

 def test_only_new_output_namespace_and_unchanged_model(self):
  runner=self.subject();self.assertEqual(runner.MODEL,'declared_daily_bar_open_next_bar_v1')
  self.assertEqual(runner.output_path('2020-06-01','C','001').name,'stage011_C_20200601_attempt001')
  with self.assertRaises(ValueError):runner.output_path('2020-06-01','C','../escape')

if __name__=='__main__':unittest.main()
