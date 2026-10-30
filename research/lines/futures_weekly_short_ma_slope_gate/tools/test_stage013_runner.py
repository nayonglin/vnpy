import importlib.util,unittest
class Reserve100RunnerTests(unittest.TestCase):
 def subject(self):
  self.assertIsNotNone(importlib.util.find_spec('run_stage013'),'Stage013 runner missing')
  import run_stage013 as m
  return m
 def test_C_only_fresh_binding_windows_and_stage013_outputs(self):
  m=self.subject();self.assertEqual(m.output_path('2017-01-01','C','001').name,'stage013_C_20170101_attempt001')
  for start,arm in [('2015-01-01','C'),('2017-01-01','A')]:
   with self.subTest(start=start,arm=arm),self.assertRaises(ValueError):m.output_path(start,arm,'001')
 def test_runner_keeps_old_reference_normalization_and_original_risk(self):
  m=self.subject();import run_stage009
  self.assertIs(m.normalize_settings,run_stage009.normalize_settings);self.assertEqual(m.RESERVE_CAPITAL,100000.);self.assertEqual(m.TOTAL_CAPITAL,250000.)
if __name__=='__main__':unittest.main()
