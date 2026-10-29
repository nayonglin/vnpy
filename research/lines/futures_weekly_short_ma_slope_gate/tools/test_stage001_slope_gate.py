import unittest
from types import SimpleNamespace
from copy import deepcopy
import pandas as pd
try:
 from stage001_slope_gate import slope_snapshot, slope_strategy_class
except ImportError:
 slope_snapshot = slope_strategy_class = None

def manager(values):
 return SimpleNamespace(inner=SimpleNamespace(count=len(values)),completed=[dict(week_end=d.strftime('%Y-%m-%d'),close=x) for d,x in zip(pd.date_range('2020-01-03',periods=len(values),freq='W-FRI'),values)])
class Parent:
 def __init__(self):
  self.values=list(range(100,121));self.ams={'rb2010.SHFE':manager(self.values)};self.calls=[];self.result={'selected_volume':3,'stop_price':200.,'risk_amount':100.,'nested':{'unchanged':True}};self.targets={};self.pending_margin_reservation=0
 def _calculate_entry_sizing(self,*args,**kwargs):self.calls.append(kwargs);return self.result
 def _open_position(self,*args,**kwargs):return 'opened'
 def get_target(self,s):return self.targets.get(s,0)
 def history(self):return pd.DataFrame({'close':self.values})
 def bar(self):return SimpleNamespace(datetime=pd.Timestamp('2020-06-01'),vt_symbol='rb2010.SHFE')
class GateTests(unittest.TestCase):
 def setUp(self):self.assertTrue(callable(slope_snapshot),'missing slope implementation')
 def test_both_down_and_flat_allow(self):
  for v in [list(range(121,100,-1)),[100.]*21]:
   r=slope_snapshot(manager(v),pd.DataFrame({'close':v}),'2020-06-01','rb2010.SHFE');self.assertFalse(r['would_block'])
 def test_positive_either_is_or_not_and(self):
  for v,expected in [([100.]*10+[101.]+[100.]*4+[99.]+[100.]*4+[102.],(True,True)),(list(range(100,121)),(True,True))]:
   r=slope_snapshot(manager(v),pd.DataFrame({'close':v}),'2020-06-01','rb2010.SHFE');self.assertTrue(r['would_block'])
  # Last close compared to t-5 and t-10 independently determines SMA change.
  for a,b in [(110,90),(90,110)]:
   v=[100.]*21;v[-6]=a;v[-11]=b
   r=slope_snapshot(manager(v),pd.DataFrame({'close':v}),'2020-06-01','rb2010.SHFE');self.assertTrue(r['would_block']);self.assertNotEqual(r['ma5_delta']>0,r['ma10_delta']>0)
 def test_uses_observed_tail_not_zero_prefix(self):
  v=list(range(100,121));h=pd.DataFrame({'close':[0.]*20+v})
  self.assertEqual(slope_snapshot(manager(v),h,'2020-06-01','rb2010.SHFE')['ma10_current'],sum(v[-10:])/10)
 def test_invalid_history_epoch_or_future_fails(self):
  for fault in ['short','nan','future','mismatch','epoch']:
   v=list(range(100,121));am=manager(v);h=pd.DataFrame({'close':v})
   if fault=='short':am.inner.count=10
   if fault=='nan':h.loc[20,'close']=float('nan')
   if fault=='future':am.completed[-1]['week_end']='2021-01-01'
   if fault=='mismatch':am.completed[-1]['close']=999.
   if fault=='epoch':am.inner.count=0
   with self.assertRaises(ValueError):slope_snapshot(am,h,'2020-06-01','rb2010.SHFE')
 def test_rejected_short_zero_no_parent_mutation_or_ownership_change(self):
  s=slope_strategy_class(Parent,enabled=True)();old=deepcopy(s.result)
  r=s._calculate_entry_sizing('rb2010.SHFE','short',s.bar(),s.history(),{'signal':'short_case1a'})
  self.assertEqual(r['selected_volume'],0);self.assertEqual(s.result,old);self.assertEqual(s.targets,{});self.assertEqual(s.pending_margin_reservation,0);self.assertTrue(s.short_ma_slope_decisions[-1]['applied_block'])
 def test_long_rollover_disabled_and_noncase1_unchanged(self):
  for enabled,direction,context,signal in [(True,'long','flat_entry','long_case1a'),(True,'short','rollover_reopen','short_case1a'),(False,'short','flat_entry','short_case1a'),(True,'short','flat_entry','short_case2')]:
   s=slope_strategy_class(Parent,enabled=enabled)();r=s._calculate_entry_sizing('rb2010.SHFE',direction,s.bar(),s.history(),{'signal':signal},entry_context=context)
   self.assertIs(r,s.result)
 def test_negative_signal_passes_whole_parent_result(self):
  s=slope_strategy_class(Parent,enabled=True)();s.values=list(range(121,100,-1));s.ams={'rb2010.SHFE':manager(s.values)}
  self.assertIs(s._calculate_entry_sizing('rb2010.SHFE','short',s.bar(),s.history(),{'signal':'short_case1a'}),s.result)
 def test_parent_failure_not_hidden(self):
  class Bad(Parent):
   def _calculate_entry_sizing(self,*a,**k):raise RuntimeError('parent failure')
  s=slope_strategy_class(Bad,enabled=True)()
  with self.assertRaisesRegex(RuntimeError,'parent failure'):s._calculate_entry_sizing('rb2010.SHFE','short',s.bar(),s.history(),{'signal':'short_case1a'})
if __name__=='__main__':unittest.main()
