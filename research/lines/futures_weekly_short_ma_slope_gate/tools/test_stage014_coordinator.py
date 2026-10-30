import importlib.util,unittest
from unittest.mock import patch
from types import SimpleNamespace

class FiveStartDispatchTests(unittest.TestCase):
 def subject(self):
  self.assertIsNotNone(importlib.util.find_spec('stage014_coordinator'),'Stage014 coordinator missing')
  import stage014_coordinator as m
  return m
 def test_single_canary_then58_all_fresh_and_failed_stop(self):
  m=self.subject();reg=dict(jobs={s+'|C':dict(status='pending',method='fresh_engine',reused=False) for s in m.STARTS})
  self.assertEqual(m.select_pending(reg,'canary'),['2015-01-01|C']);reg['jobs']['2015-01-01|C']['status']='validated';self.assertEqual(len(m.select_pending(reg,'resume')),58)
  reg['jobs']['2015-03-01|C']['status']='failed'
  with self.assertRaises(ValueError):m.select_pending(reg,'resume')
 def test_max2_and_disk_gate_never_dispatches_with_insufficient_space(self):
  m=self.subject();self.assertEqual(m.BASE.name,'stage014_multistart');self.assertEqual(m.validate_workers(2),2)
  with self.assertRaises(ValueError):m.validate_workers(3)
  f=dict(min_free_disk_bytes=8*1024**3,estimated_bytes_per_run=256*1024**2)
  with patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=1024)):
   with self.assertRaises(ValueError):m.disk_gate(m.ROOT,f,59)
  with patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=72*1024**3)):
   self.assertTrue(m.disk_gate(m.ROOT,f,59)['accepted'])
if __name__=='__main__':unittest.main()
