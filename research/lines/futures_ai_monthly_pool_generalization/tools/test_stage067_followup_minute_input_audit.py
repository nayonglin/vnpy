import unittest
import stage067_followup_minute_input_audit as audit


class InheritedBindingTests(unittest.TestCase):
 def setUp(self):self.assertTrue(callable(getattr(audit,'verify_inherited_binding',None)),'missing inherited rawSHA verifier')
 def test_three_way_hash_stat_identity(self):
  row=dict(path='p',sha256='abc',bytes=1,mtime_ns=2,inode=3)
  prior=row.copy();listed=dict(path='p',inherited056_payload_sha256='abc',current_bytes='1',current_mtime_ns='2',current_inode='3')
  self.assertTrue(audit.verify_inherited_binding(row,prior,listed))
 def test_current_raw_change_rejected(self):
  row=dict(path='p',sha256='changed',bytes=1,mtime_ns=2,inode=3)
  with self.assertRaises(ValueError):audit.verify_inherited_binding(row,{**row,'sha256':'old'},dict(path='p',inherited056_payload_sha256='old',current_bytes='1',current_mtime_ns='2',current_inode='3'))
 def test_current_stat_or_064_binding_conflict_rejected(self):
  row=dict(path='p',sha256='abc',bytes=1,mtime_ns=2,inode=3);listed=dict(path='p',inherited056_payload_sha256='abc',current_bytes='1',current_mtime_ns='2',current_inode='3')
  for field,value in [('bytes',99),('mtime_ns',99),('inode',99),('path','other')]:
   with self.subTest(field=field),self.assertRaises(ValueError):audit.verify_inherited_binding({**row,field:value},row,listed)

if __name__=='__main__':unittest.main()
