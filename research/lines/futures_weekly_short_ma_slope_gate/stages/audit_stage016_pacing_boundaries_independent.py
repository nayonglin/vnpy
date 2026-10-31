"""Pure five-helper timing tests; FakeApi fills empty callback epoch only."""
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[4];sys.path[:0]=[str(ROOT),str(ROOT/'examples/portfolio_backtesting')]
from vnpy.trader.setting import SETTINGS
SETTINGS['log.file']=False;SETTINGS['log.console']=False
import run_qmt_roll_stage931_official_live_ctp_submit_adapter as source
class Clock:
 def __init__(self,values):self.values=iter(values);self.now=0.;self.sleeps=[]
 def monotonic(self):self.now=next(self.values,self.now);return self.now
 def sleep(self,value):assert value>0;self.sleeps.append(value);self.now+=value
class AllPacingIndependent(unittest.TestCase):
 def query(self,kind,values,budget=8.,interval=1.1,hard=None):
  clock=Clock(values);rows={'_ctp_last_query_monotonic':.1,'positions':[]}
  class Api:
   brokerid='offline';userid='fixture';reqid=10
   def __init__(self):self.calls=[]
   def getTradingDay(self):return '20261102'
   def complete(self,kind,reqid):
    self.calls.append(clock.now);rows['_'+kind+'_query_epoch']['complete_reqid']=reqid
    rows[kind+'_query_callbacks'].append(dict(reqid=reqid,last=True,error_id=0,has_data=False));return 0
   def reqQryOrder(self,request,reqid):return self.complete('order',reqid)
   def reqQryInvestorPosition(self,request,reqid):return self.complete('position',reqid)
   def reqQryTrade(self,request,reqid):return self.complete('trade',reqid)
   def reqQryInvestorPositionDetail(self,request,reqid):return self.complete('position_detail',reqid)
  api=Api();fn={'order':source._final_order_query_epoch,'position':source._final_position_query_epoch,'trade':source._final_trade_query_epoch,'detail':source._final_position_detail_query_epoch}[kind]
  extra={}if kind in ('trade','detail')else dict(query_interval_seconds=interval,hard_deadline_monotonic=hard)
  result=fn(api,rows,max_wait_seconds=budget,monotonic=clock.monotonic,sleeper=clock.sleep,**extra)
  return result,api,clock
 def test_all_four_query_crossings_complete_once_after_allowed_boundary(self):
  for kind in ('order','position','trade','detail'):
   with self.subTest(kind=kind):
    result,api,clock=self.query(kind,[.2,1.199999,1.200001]);self.assertTrue(result['confirmed'],result);self.assertEqual(len(api.calls),1);self.assertGreaterEqual(api.calls[0],1.2);self.assertTrue(all(0<s<=.05 for s in clock.sleeps))
 def test_all_four_reject_clock_jump_beyond_actual_deadline_before_query(self):
  for kind in ('order','position','trade','detail'):
   with self.subTest(kind=kind):
    result,api,_=self.query(kind,[.2,1.200001],budget=.5);self.assertFalse(result['confirmed']);self.assertEqual(api.calls,[])
 def test_all_four_do_not_query_when_deadline_passes_before_pacing_ready(self):
  for kind in ('order','position','trade','detail'):
   with self.subTest(kind=kind):
    result,api,_=self.query(kind,[.2,.699999,.700001],budget=.5);self.assertFalse(result['confirmed']);self.assertEqual(api.calls,[])
 def test_order_and_position_keep_minimum_one_second_with_smaller_interval(self):
  for kind in ('order','position'):
   with self.subTest(kind=kind):
    result,api,clock=self.query(kind,[.2,1.099999,1.100001],interval=.01);self.assertTrue(result['confirmed'],result);self.assertGreaterEqual(api.calls[0],1.1);self.assertTrue(clock.sleeps)
 def test_order_and_position_preserve_absolute_hard_deadline(self):
  for kind in ('order','position'):
   with self.subTest(kind=kind):
    result,api,_=self.query(kind,[.2,.3,1.200001],hard=.7);self.assertFalse(result['confirmed']);self.assertEqual(api.calls,[])
 def test_common_helper_crosses_allowed_boundary_without_false_timeout(self):
  clock=Clock([1.199999,1.200001]);reason=source._wait_for_ctp_query_pacing({'_ctp_last_query_monotonic':.1},started=.2,deadline=8.,blocker_namespace='offline',monotonic=clock.monotonic,sleeper=clock.sleep,query_interval_seconds=1.1,poll_seconds=.05);self.assertEqual(reason,'');self.assertTrue(clock.sleeps)
 def test_common_helper_keeps_minimum_one_second_and_real_deadline(self):
  for deadline,expected in [(8.,''),(.7,'offline_pacing_timeout')]:
   with self.subTest(deadline=deadline):
    clock=Clock([1.099999,1.100001]);reason=source._wait_for_ctp_query_pacing({'_ctp_last_query_monotonic':.1},started=.2,deadline=deadline,blocker_namespace='offline',monotonic=clock.monotonic,sleeper=clock.sleep,query_interval_seconds=.01,poll_seconds=.05);self.assertEqual(reason,expected)
if __name__=='__main__':unittest.main(defaultTest='AllPacingIndependent')
