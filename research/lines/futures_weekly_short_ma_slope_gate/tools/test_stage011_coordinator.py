import importlib.util,unittest


class UniformCoordinatorTests(unittest.TestCase):
 def subject(self):
  self.assertIsNotNone(importlib.util.find_spec('stage011_coordinator'), 'Stage011 coordinator missing')
  import stage011_coordinator as coordinator
  return coordinator

 def test_canary_only_then44_and_failed_attempt_is_preserved(self):
  m=self.subject();reg=dict(jobs={s+'|'+a:dict(status='pending') for s in m.STARTS for a in ['A','C']})
  self.assertEqual(m.select_pending(reg,'canary'),['2015-01-01|A','2015-01-01|C'])
  for arm in ['A','C']:reg['jobs']['2015-01-01|'+arm]['status']='validated'
  self.assertEqual(len(m.select_pending(reg,'resume')),44)
  reg['jobs']['2016-01-01|A']['status']='failed'
  with self.assertRaises(ValueError):m.select_pending(reg,'resume')

 def test_worker_ceiling_and_namespace_are_stage011(self):
  m=self.subject();self.assertEqual(m.BASE.name,'stage011_multistart');self.assertEqual(m.RUNNER.name,'run_stage011.py')
  self.assertEqual(m.output_path('2015-01-01','A').name,'stage011_A_20150101_attempt001')
  self.assertEqual(m.validate_workers(2),2)
  for workers in [0,3,False]:
   with self.subTest(workers=workers),self.assertRaises(ValueError):m.validate_workers(workers)

if __name__=='__main__':unittest.main()
