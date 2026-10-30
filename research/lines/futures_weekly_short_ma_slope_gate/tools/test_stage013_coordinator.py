import importlib.util,unittest
class Reserve100CoordinatorTests(unittest.TestCase):
 def subject(self):
  self.assertIsNotNone(importlib.util.find_spec('stage013_coordinator'),'Stage013 coordinator missing')
  import stage013_coordinator as m
  return m
 def test_canary_one_C_then_remaining3_and_failed_never_redispatched(self):
  m=self.subject();jobs={s+'|C':dict(status='pending' if s in m.FRESH_STARTS else 'validated',method='fresh_engine' if s in m.FRESH_STARTS else 'proven_nonbinding_reuse') for s in m.STARTS};r=dict(jobs=jobs)
  self.assertEqual(m.select_pending(r,'canary'),['2017-01-01|C']);jobs['2017-01-01|C']['status']='validated';self.assertEqual(len(m.select_pending(r,'resume')),3)
  jobs['2017-06-01|C']['status']='failed'
  with self.assertRaises(ValueError):m.select_pending(r,'resume')
 def test_max2_and_separate_namespace(self):
  m=self.subject();self.assertEqual(m.BASE.name,'stage013_multistart_v2');self.assertEqual(m.validate_workers(2),2)
  with self.assertRaises(ValueError):m.validate_workers(3)
 def test_v2_dispatch_uses_attempt002_and_v2_freeze_gate(self):
  import ast
  from pathlib import Path
  m=self.subject();self.assertEqual(m.output_path(m.CANARY).name,'stage013_C_20170101_attempt002')
  tree=ast.parse(Path(m.__file__).read_text());strings=[node.value for node in ast.walk(tree) if isinstance(node,ast.Constant) and isinstance(node.value,str)]
  self.assertIn('stages/stage013_freeze_v2.json',strings);self.assertIn('stages/stage013_canary_independent_review_v2.json',strings)
  self.assertIn('002',strings);self.assertTrue(any('attempt002' in value for value in strings));self.assertFalse(any('attempt001' in value for value in strings))
if __name__=='__main__':unittest.main()
