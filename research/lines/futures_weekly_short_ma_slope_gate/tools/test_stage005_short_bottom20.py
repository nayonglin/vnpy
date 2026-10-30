import unittest
from copy import deepcopy
import pandas as pd
from test_stage001_slope_gate import Parent
from stage005_short_bottom20 import RangeHistory,range_strategy_class

def frame(close=120):
 return pd.DataFrame([dict(vt_symbol='rb2010.SHFE',date='2020-05-01',contract_epoch_id='old',open=200,high=500,low=1,close=200,volume=1),dict(vt_symbol='rb2010.SHFE',date='2020-05-29',contract_epoch_id='new',open=150,high=200,low=100,close=150,volume=1),dict(vt_symbol='rb2010.SHFE',date='2020-06-01',contract_epoch_id='new',open=130,high=160,low=110,close=close,volume=1),dict(vt_symbol='rb2010.SHFE',date='2020-06-02',contract_epoch_id='new',open=130,high=1000,low=2,close=130,volume=1)])
class RangeTests(unittest.TestCase):
 def obj(self,price=120,enabled=True):
  s=range_strategy_class(Parent,RangeHistory(frame(price)),enabled)();return s
 def size(self,s,price=120,direction='short',context='flat_entry',signal='short_case1a'):
  b=s.bar();b.close_price=price;return s._calculate_entry_sizing('rb2010.SHFE',direction,b,s.history(),{'signal':signal},entry_context=context)
 def test_prefix_all_daily_same_epoch_and_future_outlier_excluded(self):
  r=RangeHistory(frame()).snapshot('rb2010.SHFE','2020-06-01',120)
  self.assertEqual((r['range_low'],r['range_high'],r['history_bar_count'],r['history_start']),(100,200,2,'2020-05-29'));self.assertEqual(r['contract_epoch_id'],'new');self.assertAlmostEqual(r['range_position'],.2)
 def test_boundary_and_below_block_without_parent_mutation(self):
  for price in [110,120]:
   for context in ['flat_entry','env_probe','reverse_entry']:
    s=self.obj(price);old=deepcopy(s.result);self.assertEqual(self.size(s,price,context=context)['selected_volume'],0);self.assertEqual(s.result,old);self.assertEqual(s.targets,{});self.assertEqual(s.pending_margin_reservation,0);self.assertTrue(s.short_price_range_decisions[-1]['applied_block'])
 def test_above_bottom20_allows(self):
  s=self.obj(120.01);self.assertIs(self.size(s,120.01),s.result)
 def test_long_rollover_and_disabled_unchanged_no_MA_filters(self):
  for direction,context,signal,enabled in [('long','flat_entry','long_case1a',True),('long','flat_entry','long_case2',True),('short','rollover_reopen','short_case1a',True),('short','flat_entry','short_case1a',False)]:
   s=self.obj(enabled=enabled);self.assertIs(self.size(s,direction=direction,context=context,signal=signal),s.result);self.assertFalse(s.research_short_ma_slope_gate_enabled);self.assertFalse(s.research_long_ma_slope_gate_enabled)
 def test_zero_parent_size_not_applied(self):
  s=self.obj();s.result['selected_volume']=0;self.assertIs(self.size(s),s.result);self.assertFalse(s.short_price_range_decisions[-1]['applied_block'])
 def test_invalid_missing_or_mismatched_data_fails(self):
  for name in ['missing','mismatch']:
   h=RangeHistory(frame())
   with self.assertRaises(ValueError):h.snapshot('rb2010.SHFE','2020-06-03' if name=='missing' else '2020-06-01',999)
  f=frame();f.loc[2,'low']=float('nan')
  with self.assertRaises(ValueError):RangeHistory(f)
  with self.assertRaises(ValueError):RangeHistory(pd.concat([frame(),frame().iloc[[0]]]))
 def test_flat_range_is_rejected_without_division(self):
  f=frame().iloc[[2]].copy();f[['open','high','low','close']]=100;r=RangeHistory(f).snapshot('rb2010.SHFE','2020-06-01',100);self.assertTrue(r['would_block']);self.assertIsNone(r['range_position']);self.assertEqual(r['range_status'],'flat_range_reject')
 def test_final_guard_rejects_bypass_and_allows_valid(self):
  for price in [120,121]:
   s=self.obj(price);b=s.bar();b.close_price=price
   if price==120:
    with self.assertRaisesRegex(ValueError,'short_price_range_gate_bypassed'):s._open_position(None,'rb2010.SHFE','short',3,b,'short_case1a',s.history(),{'signal':'short_case1a'})
   else:self.assertEqual(s._open_position(None,'rb2010.SHFE','short',3,b,'short_case1a',s.history(),{'signal':'short_case1a'}),'opened')
if __name__=='__main__':unittest.main()
