"""Complete native settlement-query capture, conditional and private only.

A query's last flag proves completion of this response, not accounting finality.
No parser, transfer, order method, connection or production capability exists here.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
import hashlib,json,threading,time,uuid
from pathlib import Path

class SettlementCaptureError(ValueError):pass
_LOCK=threading.Lock()
def _require(ok,reason):
 if not ok:raise SettlementCaptureError(reason)
def _stamp(now):
 _require(isinstance(now,datetime)and now.tzinfo is not None,'settlement_aware_clock_required');return now.isoformat()
def _canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
class SettlementQueryCollector:
 def __init__(self,account,*,trading_day,connection_generation):
  _require(isinstance(account,dict)and all(isinstance(account.get(k),str)and account[k].strip()for k in ('BrokerID','AccountID')),'settlement_actual_account_required')
  _require(isinstance(trading_day,str)and datetime.strptime(trading_day,'%Y%m%d').strftime('%Y%m%d')==trading_day,'settlement_native_day_required')
  _require(isinstance(connection_generation,str)and bool(connection_generation),'settlement_connection_required')
  self.account=deepcopy(account);self.day=trading_day;self.generation=connection_generation
  self.request_id=None;self.sent_at=None;self.return_code=None;self.rows=[];self.callbacks=[];self.invalid=False;self.done=threading.Event();self.lock=threading.RLock()
 def begin(self,td_api,*,reqid,now,current_generation):
  with self.lock:
   _require(self.request_id is None,'settlement_query_already_started');_require(current_generation==self.generation,'settlement_generation_mismatch')
   _require(type(reqid)is int and reqid>0,'settlement_request_id_required');self.request_id=reqid;self.sent_at=_stamp(now)
   payload=dict(BrokerID=self.account['BrokerID'],InvestorID=self.account['AccountID'],AccountID=self.account['AccountID'],CurrencyID='CNY',TradingDay=self.day)
   self.return_code=int(td_api.reqQrySettlementInfo(payload,reqid));self.invalid=self.return_code!=0
   return self.return_code
 def on_callback(self,data,error,reqid,last,*,connection_generation,observed_at):
  with self.lock:
   if connection_generation!=self.generation:self.invalid=True;self.done.set();return
   if reqid!=self.request_id:return
   at=_stamp(observed_at)
   if (self.callbacks and self.callbacks[-1]['last'])or type(last)is not bool or not isinstance(error,dict)or type(error.get('ErrorID',0))is not int or error.get('ErrorID',0)!=0 or datetime.fromisoformat(at)<datetime.fromisoformat(self.sent_at):self.invalid=True
   self.callbacks.append(dict(reqid=reqid,connection_generation=connection_generation,received_at=at,last=last is True,error=deepcopy(error),has_data=bool(data)))
   if data:
    if not isinstance(data,dict):self.invalid=True
    else:self.rows.append(deepcopy(data))
   if last:self.done.set()
 def export(self,now):
  with self.lock:
   observed=_stamp(now)
   _require(not self.invalid and self.return_code==0 and self.callbacks and self.callbacks[-1]['last']and sum(row['last']for row in self.callbacks)==1,'settlement_query_incomplete_or_invalid')
   _require(self.rows and all(isinstance(row.get('Content'),str)for row in self.rows),'settlement_content_not_available')
   _require(0<=(now-datetime.fromisoformat(self.sent_at)).total_seconds()<=300,'settlement_query_stale_or_future')
   _require(all(datetime.fromisoformat(self.sent_at)<=datetime.fromisoformat(row['received_at'])<=now for row in self.callbacks),'settlement_callback_time_invalid')
   unknown=[];sequences=[];settlement_ids=[]
   for row in self.rows:
    _require(row.get('BrokerID')==self.account['BrokerID']and row.get('InvestorID')==self.account['AccountID']and row.get('TradingDay')==self.day,'settlement_native_account_or_day_mismatch')
    for key,expected in [('AccountID',self.account['AccountID']),('CurrencyID','CNY')]:
     if row.get(key)in (None,''):unknown.append(key)
     else:_require(row[key]==expected,'settlement_native_currency_or_account_mismatch')
    _require(type(row.get('SequenceNo'))is int and row['SequenceNo']>=0 and type(row.get('SettlementID'))is int and row['SettlementID']>=0,'settlement_native_sequence_fields_required')
    sequences.append(row['SequenceNo']);settlement_ids.append(row['SettlementID'])
   _require(len(set(settlement_ids))==1 and sequences==list(range(sequences[0],sequences[0]+len(sequences))),'settlement_statement_identity_or_sequence_broken')
   body=dict(schema='weekly19.ctp-settlement-query.v1',source_kind='ctp_settlement_info_query',target_native_trading_day=self.day,
    connection_generation=self.generation,account_source_sha256=hashlib.sha256(_canonical(self.account)).hexdigest(),
    request_id=self.request_id,request_sent_at=self.sent_at,query_return_code=self.return_code,query_complete=True,
    observed_at=observed,callbacks=deepcopy(self.callbacks),rows=deepcopy(self.rows),
    source_collector_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    statement_sequence=dict(first=sequences[0],last=sequences[-1],count=len(sequences),contiguous=True,settlement_id=settlement_ids[0],start_origin_qualified=False),
    native_statement_fields_unknown=sorted(set(unknown)),statement_finality_qualified=False,production_qualified=False,qualification_status='raw_query_complete_unparsed_unqualified')
   raw=_canonical(body);return dict(raw_payload=raw.decode(),raw_sha256=hashlib.sha256(raw).hexdigest())

@contextmanager
def instrument_settlement_callback(td_api,collector,*,connection_generation,clock):
 _require(_LOCK.acquire(blocking=False),'settlement_callback_instrumentation_busy')
 owner=type(td_api);name='onRspQrySettlementInfo';had=name in owner.__dict__;original=getattr(owner,name,None)
 def callback(self,data,error,reqid,last):
  if self is td_api:collector.on_callback(data,error,reqid,last,connection_generation=connection_generation(),observed_at=clock())
  if original is not None:return original(self,data,error,reqid,last)
 try:setattr(owner,name,callback);yield collector
 finally:
  if had:setattr(owner,name,original)
  elif name in owner.__dict__:delattr(owner,name)
  _LOCK.release()

def capture_settlement_on_existing_connection(td_api,account,*,trading_day,connection_generation,clock,deadline,private_capture_dir):
 """Called solely inside the existing Stage174 mutation firewall, before close."""
 from qmt_roll_weekly19_broker_evidence import _external_private,_write_private
 private_capture_dir=Path(private_capture_dir)
 _require(private_capture_dir.is_absolute()and not any((parent/'.git').exists()for parent in (private_capture_dir,*private_capture_dir.parents)),'settlement_private_capture_outside_checkout_required')
 collector=SettlementQueryCollector(account,trading_day=trading_day,connection_generation=connection_generation())
 _require(deadline-time.monotonic()>1.1,'settlement_query_deadline_exhausted')
 # Respect CTP query flow control after the original four-query snapshot.
 time.sleep(1.05)
 with instrument_settlement_callback(td_api,collector,connection_generation=connection_generation,clock=clock):
  td_api.reqid+=1;ret=collector.begin(td_api,reqid=td_api.reqid,now=clock(),current_generation=connection_generation())
  _require(ret==0,'settlement_query_request_rejected')
  _require(collector.done.wait(max(0.,deadline-time.monotonic())),'settlement_query_timeout')
 envelope=collector.export(clock());path=Path(private_capture_dir)/('settlement-'+trading_day+'-'+uuid.uuid4().hex+'.json')
 _external_private(path);payload=_canonical(envelope);_write_private(path,payload)
 return dict(path=str(path),sha256=hashlib.sha256(payload).hexdigest(),raw_sha256=envelope['raw_sha256'],
  target_native_trading_day=trading_day,query_complete=True,statement_finality_qualified=False,production_qualified=False)
