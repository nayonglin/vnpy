"""Offline scripted-monotonic boundary probes, no real API or sleeping."""
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[4];sys.path[:0]=[str(ROOT),str(ROOT/'examples/portfolio_backtesting')]
from vnpy.trader.setting import SETTINGS
SETTINGS['log.file']=False;SETTINGS['log.console']=False
import run_qmt_roll_stage931_official_live_ctp_submit_adapter as module
class Clock:
 def __init__(self,values):self.values=iter(values);self.now=0.;self.sleeps=[]
 def monotonic(self):self.now=next(self.values,self.now);return self.now
 def sleep(self,seconds):self.sleeps.append(seconds);self.now+=seconds
class PacingFamilyIndependent(unittest.TestCase):
 def query(self,kind,budget):
  boundary=.1+module.CTP_QUERY_INTERVAL_SECONDS
  clock=Clock([.2,boundary-1e-6,boundary+1e-6]);rows={'_ctp_last_query_monotonic':.1}
  class Api:
   brokerid='offline';userid='fixture';reqid=4
   def __init__(self):self.calls=[]
   def getTradingDay(self):return '20261102'
   def reqQryTrade(self,request,reqid):
    self.calls.append(clock.now);rows['_trade_query_epoch']['complete_reqid']=reqid
    rows['trade_query_callbacks'].append(dict(reqid=reqid,last=True,error_id=0,has_data=False));return 0
   def reqQryInvestorPositionDetail(self,request,reqid):
    self.calls.append(clock.now);rows['_position_detail_query_epoch']['complete_reqid']=reqid;return 0
  api=Api();fn=module._final_trade_query_epoch if kind=='trade'else module._final_position_detail_query_epoch
  result=fn(api,rows,max_wait_seconds=budget,monotonic=clock.monotonic,sleeper=clock.sleep)
  return result,api,clock,boundary
 def test_trade_crossing_allowed_boundary_is_not_timeout(self):
  result,api,clock,boundary=self.query('trade',8.)
  self.assertTrue(result['confirmed'],result);self.assertEqual(len(api.calls),1);self.assertGreaterEqual(api.calls[0],boundary)
 def test_position_detail_crossing_allowed_boundary_is_not_timeout(self):
  result,api,clock,boundary=self.query('detail',8.)
  self.assertTrue(result['confirmed'],result);self.assertEqual(len(api.calls),1);self.assertGreaterEqual(api.calls[0],boundary)
 def test_true_deadline_before_allowed_boundary_blocks_both(self):
  for kind in ('trade','detail'):
   with self.subTest(kind=kind):
    result,api,_,_=self.query(kind,.5);self.assertFalse(result['confirmed']);self.assertEqual(api.calls,[])
if __name__=='__main__':unittest.main(defaultTest='PacingFamilyIndependent')
