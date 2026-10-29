import unittest
from copy import deepcopy
from test_stage001_slope_gate import Parent,manager
try:
 from stage002_symmetric_gate import symmetric_strategy_class
except ImportError:symmetric_strategy_class=None
class MirrorTests(unittest.TestCase):
 def setUp(self):self.assertTrue(callable(symmetric_strategy_class),'missing symmetric implementation')
 def obj(self,values=None,enabled=True):
  s=symmetric_strategy_class(Parent,enabled)()
  if values is not None:s.values=values;s.ams={'rb2010.SHFE':manager(values)}
  return s
 def size(self,s,signal='long_case1a',direction='long',context='flat_entry'):
  return s._calculate_entry_sizing('rb2010.SHFE',direction,s.bar(),s.history(),{'signal':signal},entry_context=context)
 def test_negative_either_blocks_both_long_cases_without_mutation(self):
  for signal in ['long_case1a','long_case2']:
   for a,b in [(110,90),(90,110),(110,110)]:
    v=[100.]*21;v[-6]=a;v[-11]=b;s=self.obj(v);old=deepcopy(s.result)
    self.assertEqual(self.size(s,signal)['selected_volume'],0);self.assertEqual(s.result,old);self.assertTrue(s.long_ma_slope_decisions[-1]['applied_block']);self.assertEqual(s.targets,{})
 def test_flat_or_both_positive_allow(self):
  for values in [[100.]*21,list(range(100,121))]:
   s=self.obj(values);self.assertIs(self.size(s),s.result)
 def test_short_filter_still_blocks_positive(self):
  s=self.obj();self.assertEqual(self.size(s,'short_case1a','short')['selected_volume'],0);self.assertTrue(s.short_ma_slope_decisions[-1]['applied_block']);self.assertEqual(s.long_ma_slope_decisions,[])
 def test_disabled_mirror_leaves_long_and_keeps_short_gate(self):
  s=self.obj(list(range(121,100,-1)),False);self.assertIs(self.size(s),s.result)
  s=self.obj(enabled=False);self.assertEqual(self.size(s,'short_case1a','short')['selected_volume'],0)
 def test_rollover_is_unchanged(self):
  s=self.obj(list(range(121,100,-1)));self.assertIs(self.size(s,'long_case1a','long','rollover_reopen'),s.result);self.assertEqual(s.long_ma_slope_decisions,[])
 def test_missing_or_nonfinite_fails(self):
  s=self.obj();s.ams['rb2010.SHFE'].inner.count=0
  with self.assertRaises(ValueError):self.size(s)
 def test_long_open_final_guard_rejects_negative_slope(self):
  s=self.obj(list(range(121,100,-1)))
  with self.assertRaisesRegex(ValueError,'long_ma_slope_gate_bypassed'):s._open_position(None,'rb2010.SHFE','long',3,s.bar(),'long_case2',s.history(),{'signal':'long_case2'})
if __name__=='__main__':unittest.main()
