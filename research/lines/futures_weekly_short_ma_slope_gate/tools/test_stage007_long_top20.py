import unittest
from copy import deepcopy
import pandas as pd
from test_stage001_slope_gate import Parent
from stage005_short_bottom20 import RangeHistory,range_strategy_class
from stage007_long_top20 import PriorRangeHistory,long_top20_strategy_class

def frame(price=180):
 return pd.DataFrame([dict(vt_symbol='rb2010.SHFE',date='2020-05-01',contract_epoch_id='old',open=200,high=900,low=1,close=200,volume=1),dict(vt_symbol='rb2010.SHFE',date='2020-05-29',contract_epoch_id='new',open=150,high=200,low=100,close=150,volume=1),dict(vt_symbol='rb2010.SHFE',date='2020-06-01',contract_epoch_id='new',open=150,high=260,low=90,close=price,volume=1),dict(vt_symbol='rb2010.SHFE',date='2020-06-02',contract_epoch_id='new',open=150,high=1000,low=2,close=150,volume=1)])
class TopTests(unittest.TestCase):
 def obj(self,price=180,enabled=True):
  h=RangeHistory(frame(price));return long_top20_strategy_class(Parent,h,PriorRangeHistory(h),enabled)()
 def size(self,s,price=180,signal='long_case1a',direction='long',context='flat_entry'):
  b=s.bar();b.close_price=price;return s._calculate_entry_sizing('rb2010.SHFE',direction,b,s.history(),{'signal':signal},entry_context=context)
 def test_prior_excludes_current_and_future_and_old_epoch(self):
  h=RangeHistory(frame());before=h.table.copy(deep=True);p=PriorRangeHistory(h);r=p.snapshot('rb2010.SHFE','2020-06-01',180)
  self.assertEqual((r['prior_range_low'],r['prior_range_high'],r['history_bar_count'],r['history_end']),(100,200,1,'2020-05-29'));self.assertTrue(r['would_block']);pd.testing.assert_frame_equal(h.table,before)
 def test_top_boundary_and_equal_high_block_both_long_cases(self):
  for price in [180,190,200]:
   for signal in ['long_case1a','long_case2']:
    for context in ['flat_entry','env_probe','reverse_entry']:
     s=self.obj(price);old=deepcopy(s.result);self.assertEqual(self.size(s,price,signal,context=context)['selected_volume'],0);self.assertEqual(s.result,old);self.assertEqual(s.targets,{});self.assertEqual(s.pending_margin_reservation,0)
 def test_breakout_above_prior_high_exempt_not_current_high(self):
  for price in [200.01,201,250]:
   s=self.obj(price);self.assertIs(self.size(s,price),s.result);r=s.long_price_range_decisions[-1];self.assertTrue(r['breakout_exempt']);self.assertFalse(r['would_block'])
 def test_below_top_and_below_prior_low_allow(self):
  for price in [100,179.99,99]:
   s=self.obj(price);self.assertIs(self.size(s,price),s.result)
 def test_zero_parent_not_counted_and_breakout_does_not_rescue_zero(self):
  for price in [190,201]:
   s=self.obj(price);s.result['selected_volume']=0;self.assertIs(self.size(s,price),s.result);self.assertFalse(s.long_price_range_decisions[-1]['applied_block'])
 def test_disabled_long_and_rollover_unchanged(self):
  s=self.obj(enabled=False);self.assertIs(self.size(s),s.result)
  s=self.obj();self.assertIs(self.size(s,context='rollover_reopen'),s.result);self.assertEqual(s.long_price_range_decisions,[])
 def test_short_exactly_matches_existing_core(self):
  for price in [99,150,201]:
   h=RangeHistory(frame(price));old=range_strategy_class(Parent,h,True)();new=long_top20_strategy_class(Parent,h,PriorRangeHistory(h),True)()
   self.assertEqual(self.size(old,price,'short_case1a','short'),self.size(new,price,'short_case1a','short'));self.assertEqual(old.short_price_range_decisions,new.short_price_range_decisions)
 def test_flat_prior_and_missing_or_mismatched_prior(self):
  f=frame(150);f.loc[1,['open','high','low','close']]=100;h=RangeHistory(f);p=PriorRangeHistory(h)
  self.assertTrue(p.snapshot('rb2010.SHFE','2020-06-01',150)['breakout_exempt'])
  for price,blocked in [(100,True),(99,False)]:
   f=frame(price);f.loc[1,['open','high','low','close']]=100;r=PriorRangeHistory(RangeHistory(f)).snapshot('rb2010.SHFE','2020-06-01',price);self.assertEqual(r['would_block'],blocked)
  with self.assertRaises(ValueError):p.snapshot('rb2010.SHFE','2020-05-29',150)
  with self.assertRaises(ValueError):p.snapshot('rb2010.SHFE','2020-06-01',999)
 def test_final_guard_blocks_top_but_allows_breakout_both_cases(self):
  for signal in ['long_case1a','long_case2']:
   for price in [190,201]:
    s=self.obj(price);b=s.bar();b.close_price=price
    if price==190:
     with self.assertRaisesRegex(ValueError,'long_top20_gate_bypassed'):s._open_position(None,'rb2010.SHFE','long',3,b,signal,s.history(),{'signal':signal})
    else:self.assertEqual(s._open_position(None,'rb2010.SHFE','long',3,b,signal,s.history(),{'signal':signal}),'opened')
if __name__=='__main__':unittest.main()
