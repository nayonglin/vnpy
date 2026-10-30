import importlib.util,unittest
class Reserve50CoordinatorTests(unittest.TestCase):
 def subject(self):
  self.assertIsNotNone(importlib.util.find_spec('stage012_coordinator'),'Stage012 coordinator missing')
  import stage012_coordinator as m
  return m
 def test_canary_one_C_then_remaining8_and_failed_never_redispatched(self):
  m=self.subject();jobs={s+'|C':dict(status='pending' if s in m.FRESH_STARTS else 'validated',method='fresh_engine' if s in m.FRESH_STARTS else 'proven_nonbinding_reuse') for s in m.STARTS};r=dict(jobs=jobs)
  self.assertEqual(m.select_pending(r,'canary'),['2016-06-01|C']);jobs['2016-06-01|C']['status']='validated';self.assertEqual(len(m.select_pending(r,'resume')),8)
  jobs['2017-01-01|C']['status']='failed'
  with self.assertRaises(ValueError):m.select_pending(r,'resume')
 def test_max2_and_separate_namespace(self):
  m=self.subject();self.assertEqual(m.BASE.name,'stage012_multistart');self.assertEqual(m.validate_workers(2),2)
  with self.assertRaises(ValueError):m.validate_workers(3)
if __name__=='__main__':unittest.main()
