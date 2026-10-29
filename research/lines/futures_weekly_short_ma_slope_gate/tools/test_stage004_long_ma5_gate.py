import unittest
from copy import deepcopy
from test_stage001_slope_gate import Parent,manager
from stage004_long_ma5_gate import long_ma5_strategy_class

class LongMA5Tests(unittest.TestCase):
 def obj(self,a,b,enabled=True):
  s=long_ma5_strategy_class(Parent,enabled)();s.values=[100.]*21;s.values[-6]=a;s.values[-11]=b;s.ams={'rb2010.SHFE':manager(s.values)};return s
 def size(self,s,signal='long_case1a',direction='long',context='flat_entry'):
  return s._calculate_entry_sizing('rb2010.SHFE',direction,s.bar(),s.history(),{'signal':signal},entry_context=context)
 def test_ma10_down_alone_does_not_block(self):
  for signal in ['long_case1a','long_case2']:
   for a in [90,100]:
    s=self.obj(a,110);self.assertIs(self.size(s,signal),s.result);r=s.long_ma_slope_decisions[-1];self.assertLess(r['ma10_delta'],0);self.assertFalse(r['would_block']);self.assertFalse(r['applied_block'])
 def test_ma5_down_blocks_even_ma10_up_without_mutation(self):
  for signal in ['long_case1a','long_case2']:
   for context in ['flat_entry','env_probe','reverse_entry']:
    s=self.obj(110,90);old=deepcopy(s.result);self.assertEqual(self.size(s,signal,context=context)['selected_volume'],0);self.assertEqual(s.result,old);self.assertEqual(s.targets,{});self.assertEqual(s.pending_margin_reservation,0)
 def test_zero_original_sizing_not_counted_as_applied(self):
  s=self.obj(110,90);s.result['selected_volume']=0;self.assertIs(self.size(s),s.result);self.assertFalse(s.long_ma_slope_decisions[-1]['applied_block'])
 def test_short_still_checks_both_ma(self):
  for a,b in [(90,110),(110,90)]:
   s=self.obj(a,b);self.assertEqual(self.size(s,'short_case1a','short')['selected_volume'],0)
 def test_rollover_and_disabled_long_unchanged(self):
  s=self.obj(110,90);self.assertIs(self.size(s,context='rollover_reopen'),s.result);self.assertEqual(s.long_ma_slope_decisions,[])
  s=self.obj(110,90,False);self.assertIs(self.size(s),s.result)
 def test_final_guard_allows_ma10_down_rejects_ma5_down(self):
  for signal in ['long_case1a','long_case2']:
   s=self.obj(90,110);self.assertEqual(s._open_position(None,'rb2010.SHFE','long',3,s.bar(),signal,s.history(),{'signal':signal}),'opened')
   s=self.obj(110,90)
   with self.assertRaisesRegex(ValueError,'long_ma_slope_gate_bypassed'):s._open_position(None,'rb2010.SHFE','long',3,s.bar(),signal,s.history(),{'signal':signal})
if __name__=='__main__':unittest.main()
