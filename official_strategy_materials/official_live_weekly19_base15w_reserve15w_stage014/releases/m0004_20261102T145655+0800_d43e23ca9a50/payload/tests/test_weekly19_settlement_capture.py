"""Raw settlement-query fixture. Query completion never certifies final cash."""
from datetime import datetime,timedelta
import hashlib,json,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'examples/portfolio_backtesting'))
from qmt_roll_weekly19_settlement_capture import SettlementQueryCollector,instrument_settlement_callback,capture_settlement_on_existing_connection,SettlementCaptureError
NOW=datetime.fromisoformat('2026-10-31T19:00:00+08:00')
ACCOUNT=dict(BrokerID='9999',AccountID='named-fixture-only')
class API:
 reqid=20
 def __init__(self):self.calls=[]
 def reqQrySettlementInfo(self,payload,reqid):
  self.calls.append(('reqQrySettlementInfo',dict(payload),reqid));return 0
 def reqOrderInsert(self,*a):raise AssertionError('forbidden')
 def reqFromBankToFutureByFuture(self,*a):raise AssertionError('forbidden')
 def onRspQrySettlementInfo(self,*a):self.calls.append(('original_callback',))
class SettlementTests(unittest.TestCase):
 def collector(self):return SettlementQueryCollector(ACCOUNT,trading_day='20261030',connection_generation='connection-fixture')
 def row(self,seq=1,content='explicit fixture; no broker format'):
  return dict(BrokerID='9999',InvestorID='named-fixture-only',AccountID='named-fixture-only',CurrencyID='CNY',TradingDay='20261030',SettlementID=1,SequenceNo=seq,Content=content)
 def begin(self,c):api=API();self.assertEqual(c.begin(api,reqid=21,now=NOW,current_generation='connection-fixture'),0);return api
 def callback(self,c,row=None,last=True,**kw):
  args=dict(connection_generation='connection-fixture',observed_at=NOW);args.update(kw)
  c.on_callback(self.row()if row is None else row,{'ErrorID':0},21,last,**args)
 def test_native_chunks_are_preserved_without_parsing_or_finality_claim(self):
  c=self.collector();api=self.begin(c);a=self.row(1,'first content');b=self.row(2,'second content')
  self.callback(c,a,False);self.callback(c,b);out=c.export(NOW);raw=json.loads(out['raw_payload'])
  self.assertEqual(raw['rows'],[a,b]);self.assertFalse(raw['statement_finality_qualified']);self.assertFalse(raw['production_qualified'])
  self.assertEqual(api.calls[0][1]['TradingDay'],'20261030');self.assertEqual(hashlib.sha256(out['raw_payload'].encode()).hexdigest(),out['raw_sha256'])
 def test_missing_last_error_future_and_generation_mismatch_are_rejected(self):
  c=self.collector();self.begin(c);self.callback(c,last=False)
  with self.assertRaisesRegex(SettlementCaptureError,'incomplete'):c.export(NOW)
  c=self.collector();self.begin(c);self.callback(c,connection_generation='other')
  with self.assertRaisesRegex(SettlementCaptureError,'incomplete'):c.export(NOW)
  c=self.collector();self.begin(c);self.callback(c,observed_at=NOW+timedelta(seconds=1))
  with self.assertRaisesRegex(SettlementCaptureError,'time_invalid'):c.export(NOW)
 def test_foreign_account_or_requested_day_rejected(self):
  for key,value in [('InvestorID','foreign'),('TradingDay','20261102'),('CurrencyID','USD')]:
   c=self.collector();self.begin(c);self.callback(c,dict(self.row(),**{key:value}))
   with self.assertRaises(SettlementCaptureError):c.export(NOW)
 def test_native_null_error_info_is_empty_dict_and_remains_unmodified(self):
  c=self.collector();self.begin(c);c.on_callback(self.row(),{},21,True,connection_generation='connection-fixture',observed_at=NOW)
  raw=json.loads(c.export(NOW)['raw_payload']);self.assertEqual(raw['callbacks'][0]['error'],{});self.assertFalse(raw['statement_finality_qualified'])
 def test_sequence_identity_and_raw_unknown_fields_are_explicit(self):
  for bad in [dict(self.row(1),Content='different duplicate'),dict(self.row(2),SettlementID=2),dict(self.row(3)),dict(self.row(2),SequenceNo=None)]:
   c=self.collector();self.begin(c);self.callback(c,self.row(1),False);self.callback(c,bad)
   with self.assertRaises(SettlementCaptureError):c.export(NOW)
  c=self.collector();self.begin(c);row=self.row();row.pop('CurrencyID');row['AccountID']='';self.callback(c,row)
  raw=json.loads(c.export(NOW)['raw_payload']);self.assertEqual(raw['native_statement_fields_unknown'],['AccountID','CurrencyID']);self.assertFalse(raw['statement_sequence']['start_origin_qualified'])
 def test_hook_is_one_native_instance_and_restores_original(self):
  c=self.collector();api=self.begin(c);other=API();old=API.onRspQrySettlementInfo
  with instrument_settlement_callback(api,c,connection_generation=lambda:'connection-fixture',clock=lambda:NOW):
   other.onRspQrySettlementInfo(self.row(),{'ErrorID':0},21,True);self.assertEqual(c.rows,[])
   api.onRspQrySettlementInfo(self.row(),{'ErrorID':0},21,True)
  self.assertIs(API.onRspQrySettlementInfo,old);self.assertTrue(json.loads(c.export(NOW)['raw_payload'])['query_complete'])
 def test_existing_connection_capture_is_private_and_never_calls_mutators(self):
  class ImmediateAPI(API):
   def reqQrySettlementInfo(api,payload,reqid):
    API.reqQrySettlementInfo(api,payload,reqid);api.onRspQrySettlementInfo(self.row(),{'ErrorID':0},reqid,True);return 0
  with tempfile.TemporaryDirectory(dir='/private/tmp')as d:
   root=Path(d).resolve();root.chmod(0o700);api=ImmediateAPI()
   with patch('qmt_roll_weekly19_settlement_capture.time.sleep'):
    result=capture_settlement_on_existing_connection(api,ACCOUNT,trading_day='20261030',connection_generation=lambda:'connection-fixture',clock=lambda:NOW,deadline=time.monotonic()+5,private_capture_dir=root)
   path=Path(result['path']);self.assertEqual(path.stat().st_mode&0o777,0o600);self.assertFalse(result['statement_finality_qualified']);self.assertEqual(result['sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
   self.assertEqual([r[0]for r in api.calls].count('reqQrySettlementInfo'),1)
if __name__=='__main__':unittest.main()
