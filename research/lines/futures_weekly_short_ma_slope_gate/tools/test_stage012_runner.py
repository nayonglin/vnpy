import importlib.util,unittest
class Reserve50RunnerTests(unittest.TestCase):
 def subject(self):
  self.assertIsNotNone(importlib.util.find_spec('run_stage012'),'Stage012 runner missing')
  import run_stage012 as m
  return m
 def test_C_only_fresh_binding_windows_and_stage012_outputs(self):
  m=self.subject();self.assertEqual(m.output_path('2016-06-01','C','001').name,'stage012_C_20160601_attempt001')
  for start,arm in [('2015-01-01','C'),('2016-06-01','A')]:
   with self.subTest(start=start,arm=arm),self.assertRaises(ValueError):m.output_path(start,arm,'001')
 def test_runner_keeps_old_reference_normalization_and_original_risk(self):
  m=self.subject();import run_stage009
  self.assertIs(m.normalize_settings,run_stage009.normalize_settings);self.assertEqual(m.RESERVE_CAPITAL,50000.);self.assertEqual(m.TOTAL_CAPITAL,200000.)
if __name__=='__main__':unittest.main()
