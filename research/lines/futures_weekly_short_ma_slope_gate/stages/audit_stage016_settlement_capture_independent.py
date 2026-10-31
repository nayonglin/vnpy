"""Native settlement callback fixtures only; no CTP or source qualification."""
import copy,hashlib,json,sys,tempfile,time,unittest
from pathlib import Path
from datetime import datetime,timedelta
from unittest.mock import patch
R=Path('/Users/mac/.codex/worktrees/weekly19-official-20261031/fian');sys.path.insert(0,str(R/'examples/portfolio_backtesting'))
import qmt_roll_weekly19_settlement_capture as s
NOW=datetime.fromisoformat('2026-10-31T19:00:00+08:00');ACCOUNT={'BrokerID':'9999','AccountID':'independent-fixture-only'}
class API:
 reqid=6
 def __init__(self):self.calls=[]
 def reqQrySettlementInfo(self,request,reqid):self.calls.append((dict(request),reqid));return 0
 def reqOrderInsert(self,*a):raise AssertionError('no orders')
 def reqFromBankToFutureByFuture(self,*a):raise AssertionError('no transfer')
 def onRspQrySettlementInfo(self,*a):pass
class SettlementIndependent(unittest.TestCase):
 def collector(self):
  c=s.SettlementQueryCollector(ACCOUNT,trading_day='20261030',connection_generation='fixture-connection');api=API();c.begin(api,reqid=7,now=NOW,current_generation='fixture-connection');return c,api
 def row(self,seq=42):return dict(BrokerID='9999',InvestorID=ACCOUNT['AccountID'],AccountID=ACCOUNT['AccountID'],CurrencyID='CNY',TradingDay='20261030',SettlementID=5,SequenceNo=seq,Content='fixture only, no financial statement meaning')
 def receive(self,c,row,last=True,error=None,reqid=7,gen='fixture-connection',at=NOW):c.on_callback(row,{}if error is None else error,reqid,last,connection_generation=gen,observed_at=at)
 def test_null_rspinfo_shape_and_nonzero_sequence_origin_preserve_raw_only(self):
  c,api=self.collector();row=self.row();self.receive(c,row);row['Content']='caller mutation';out=c.export(NOW);body=json.loads(out['raw_payload'])
  self.assertEqual(body['callbacks'][0]['error'],{});self.assertNotEqual(body['rows'][0]['Content'],'caller mutation')
  self.assertEqual(body['statement_sequence']['first'],42);self.assertFalse(body['statement_sequence']['start_origin_qualified']);self.assertFalse(body['statement_finality_qualified']);self.assertFalse(body['production_qualified']);self.assertEqual(out['raw_sha256'],hashlib.sha256(out['raw_payload'].encode()).hexdigest());self.assertEqual(api.calls[0][0]['TradingDay'],'20261030')
 def test_duplicate_gap_and_cross_statement_id_are_never_raw_complete(self):
  for second in [self.row(42),self.row(44),dict(self.row(43),SettlementID=6)]:
   c,_=self.collector();self.receive(c,self.row(42),last=False);self.receive(c,second)
   with self.subTest(second=second),self.assertRaises(s.SettlementCaptureError):c.export(NOW)
 def test_missing_native_sequence_fields_are_not_invented(self):
  for field in ['SequenceNo','SettlementID']:
   c,_=self.collector();row=self.row();row.pop(field);self.receive(c,row)
   with self.subTest(field=field),self.assertRaises(s.SettlementCaptureError):c.export(NOW)
 def test_absent_account_currency_are_explicit_unknown_not_filled_CNY(self):
  c,_=self.collector();row=self.row();row.pop('AccountID');row.pop('CurrencyID');self.receive(c,row);body=json.loads(c.export(NOW)['raw_payload'])
  self.assertEqual(body['native_statement_fields_unknown'],['AccountID','CurrencyID']);self.assertNotIn('AccountID',body['rows'][0]);self.assertNotIn('CurrencyID',body['rows'][0]);self.assertFalse(body['statement_finality_qualified'])
 def test_wrong_reqid_generation_and_explicit_error_cannot_complete(self):
  c,_=self.collector();self.receive(c,self.row(),reqid=99)
  with self.assertRaises(s.SettlementCaptureError):c.export(NOW)
  for error,gen in [({'ErrorID':1},'fixture-connection'),({'ErrorID':False},'fixture-connection'),({},'old-connection')]:
   c,_=self.collector();self.receive(c,self.row(),error=error,gen=gen)
   with self.subTest(error=error,gen=gen),self.assertRaises(s.SettlementCaptureError):c.export(NOW)
 def test_query_last_is_not_finality_and_stale_or_future_timing_rejected(self):
  c,_=self.collector();self.receive(c,self.row());self.assertFalse(json.loads(c.export(NOW)['raw_payload'])['statement_finality_qualified'])
  with self.assertRaises(s.SettlementCaptureError):c.export(NOW+timedelta(seconds=301))
  c,_=self.collector();self.receive(c,self.row(),at=NOW+timedelta(seconds=1))
  with self.assertRaises(s.SettlementCaptureError):c.export(NOW)
 def test_capture_inside_checkout_rejects_before_even_fake_query(self):
  api=API()
  with self.assertRaisesRegex(s.SettlementCaptureError,'outside_checkout'):
   s.capture_settlement_on_existing_connection(api,ACCOUNT,trading_day='20261030',connection_generation=lambda:'fixture-connection',clock=lambda:NOW,deadline=time.monotonic()+5,private_capture_dir=R)
  self.assertEqual(api.calls,[])
 def test_native_hook_is_restored_even_when_body_raises(self):
  c,api=self.collector();original=API.onRspQrySettlementInfo
  with self.assertRaisesRegex(RuntimeError,'fixture exit'):
   with s.instrument_settlement_callback(api,c,connection_generation=lambda:'fixture-connection',clock=lambda:NOW):raise RuntimeError('fixture exit')
  self.assertIs(API.onRspQrySettlementInfo,original)
if __name__=='__main__':unittest.main(verbosity=2)
