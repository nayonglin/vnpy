"""Four frozen standard serial tails; no backtest, range download, or orders."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import contextlib, hashlib, io, json, logging, math, os, signal, time
import numpy as np
import pandas as pd

LINE=Path(__file__).resolve().parents[1]
ROOT=LINE.parents[2]
OUT=LINE/'outputs/stage090_standard_tail_probe'
PLAN=LINE/'outputs/stage087_reference_intake_pilot_plan/pilot_plan.json'
PLAN_SHA='dbe872de107ba88fdcde46112ecfae6e5b5e2ee86d520507b3a0e996d9445543'
def now():return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
class ProbeDeadline(BaseException):pass

def project_tail(raw):
 """Preserve every returned row and integer timestamp; mark padding separately."""
 result=raw.copy();float_timestamp=False
 for column in ['datetime','id']:
  values=result[column]
  if pd.api.types.is_integer_dtype(values.dtype):continue
  if not pd.api.types.is_float_dtype(values.dtype) or not np.isfinite(values).all() or not values.eq(np.floor(values)).all():raise ValueError('invalid_sdk_integral_field')
  if column=='id':
   if values.abs().gt(2**53).any():raise ValueError('sdk_id_out_of_exact_float_range')
  elif values.lt(0).any() or values.ge(float(2**63)).any():raise ValueError('sdk_timestamp_out_of_int64_range')
  integers=values.astype('int64')
  if not integers.astype('float64').eq(values).all():raise ValueError('sdk_float_integer_roundtrip_failed')
  if column=='datetime':
   float_timestamp=True
   if integers.mod(60_000_000_000).ne(0).any():raise ValueError('sdk_float_timestamp_off_minute_lattice')
  result[column]=integers
 result.attrs['timestamp_precision']='SDK float64; exact minute lattice validated; no subminute precision claimed' if float_timestamp else 'original integer nanoseconds preserved'
 result['padding']=result.id.lt(0)&result.datetime.eq(0)
 if ((~result.padding)&(result.datetime.le(0)|result.id.lt(0))).any():raise ValueError('malformed_nonpadding_timestamp')
 # Masking integer with NaN would cast to float and destroy ns precision.
 stamp=pd.Series(pd.NaT,index=result.index,dtype='datetime64[ns, Asia/Shanghai]')
 selected=~result.padding
 stamp.loc[selected]=pd.to_datetime(result.loc[selected,'datetime'],unit='ns',utc=True).dt.tz_convert('Asia/Shanghai')
 result['local_datetime']=stamp
 return result

def identity_status(req,quote):
 if quote.get('instrument_id')!=req['tq_symbol_proposed'] or quote.get('exchange_id')!=req['tq_symbol_proposed'].split('.')[0]:return 'server_symbol_mismatch'
 month=req['metadata_contract_month']
 if quote.get('delivery_year')!=int(month[:4]) or quote.get('delivery_month')!=int(month[4:]):return 'server_delivery_month_mismatch'
 if quote.get('expired') is not True:return 'not_verified_expired'
 expiry=quote.get('expire_datetime')
 if not isinstance(expiry,(int,float)) or not math.isfinite(expiry):return 'expiry_timestamp_missing'
 if pd.Timestamp(expiry,unit='s',tz='UTC').tz_convert('Asia/Shanghai').strftime('%Y-%m-%d')!=req['metadata_delisted_date']:return 'server_metadata_expiry_date_mismatch'
 return 'identity_matches_metadata'

def load_pilots():
 if sha(PLAN)!=PLAN_SHA:raise ValueError('frozen_pilot_plan_changed')
 plan=json.loads(PLAN.read_text());pilots=plan.get('pilot')
 if plan.get('pilot_requests')!=4 or not isinstance(pilots,list) or len(pilots)!=4:raise ValueError('exact_four_required')
 return pilots

def run():
 if OUT.exists():raise ValueError('immutable_output_exists')
 pilots=load_pilots()
 OUT.mkdir()
 freeze={'started_at':now(),'plan_sha256':PLAN_SHA,'probe_sha256':sha(__file__),'fixed_requests':[{k:r[k] for k in ['requirement_id','tq_symbol_proposed','source_trade_date','contract_epoch_id']} for r in pilots],
 'api':'get_kline_serial','duration_seconds':60,'data_length':10000,'requests_max':4,'history_pagination':False,'TqBacktest':False,'range_downloader':False,'account':'TqSim only','trial_purchase':False,'acceptance':'none at capture; independent exact055 qualification required','source_replays':0,'model_fits':0}
 write(OUT/'PLAN.json',freeze)
 receipt={'started_at':now(),'status':'starting','api_instances':0,'serial_request_attempts':0,'broker_connections':0,'order_calls':0,'cancel_calls':0,'credentials_logged':False,'requests':[],'source_replays':0,'model_fits':0}
 api=None
 def timeout(*_):raise ProbeDeadline()
 signal.signal(signal.SIGALRM,timeout);signal.alarm(110)
 try:
  logging.disable(logging.CRITICAL)
  with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
   from tqsdk import TqApi,TqAuth,TqSim
   cfg=json.loads((ROOT/'.vntrader/vt_setting.json').read_text())
   if str(cfg.get('datafeed.name','')).lower()!='tqsdk':raise ValueError('datafeed_mismatch')
   if os.environ.get('TQ_AUTH_URL','https://auth.shinnytech.com').rstrip('/')!='https://auth.shinnytech.com':raise ValueError('nondefault_auth_endpoint')
   user=cfg.get('datafeed.username','');password=cfg.get('datafeed.password','')
   if not user or not password:raise ValueError('local_credentials_missing')
   class ReadOnlyApi(TqApi):
    def insert_order(self,*args,**kwargs):
     receipt['order_calls']+=1;raise RuntimeError('orders_disabled')
    def cancel_order(self,*args,**kwargs):
     receipt['cancel_calls']+=1;raise RuntimeError('cancels_disabled')
   receipt['phase']='construct_api';receipt['api_instances']=1
   api=ReadOnlyApi(account=TqSim(),auth=TqAuth(user,password),debug=False,disable_print=True)
   for req in pilots:
    rr={'requirement_id':req['requirement_id'],'requested_symbol':req['tq_symbol_proposed'],'started_at':now(),'status':'requesting','reference_input_qualified':False}
    receipt['requests'].append(rr);receipt['phase']='serial';receipt['serial_request_attempts']+=1
    try:
     serial=api.get_kline_serial(req['tq_symbol_proposed'],60,data_length=10000)
     deadline=time.time()+12
     while not api.is_serial_ready(serial) and time.time()<deadline:api.wait_update(deadline=min(deadline,time.time()+2))
     if not api.is_serial_ready(serial):rr['status']='serial_not_ready';continue
     raw=serial.copy(deep=True);rawpath=OUT/(req['requirement_id']+'_raw.csv');raw.to_csv(rawpath,index=False)
     rr.update(status='captured_tail',raw_rows=len(raw),raw_file=rawpath.name,raw_sha256=sha(rawpath),raw_timestamp_dtype=str(raw.datetime.dtype))
     projected=project_tail(raw);path=OUT/(req['requirement_id']+'_projected.csv');projected.to_csv(path,index=False)
     good=projected.loc[~projected.padding];start=pd.Timestamp(req['request_start_datetime']);end=pd.Timestamp(req['request_end_datetime'])
     guard=good.loc[good.local_datetime.ge(start)&good.local_datetime.le(end)]
     rr.update(projected_file=path.name,projected_sha256=sha(path),timestamp_precision=projected.attrs['timestamp_precision'],padding_rows=int(projected.padding.sum()),valid_rows=len(good),target_guard_rows=len(guard),first_local=str(good.local_datetime.min()),last_local=str(good.local_datetime.max()))
     receipt['phase']='public_contract_identity'
     quote=api.get_quote(req['tq_symbol_proposed'])
     public={key:getattr(quote,key) for key in ['instrument_id','exchange_id','expired','expire_datetime','delivery_year','delivery_month']}
     public={key:(value if not isinstance(value,float) or math.isfinite(value) else None) for key,value in public.items()}
     rr.update(server_public_identity=public,identity_status=identity_status(req,public))
    except Exception as exc:rr.update(status='request_failed',exception_class=type(exc).__name__)
    finally:rr['completed_at']=now();write(OUT/'progress.json',receipt)
   receipt['status']='bounded_four_request_probe_complete'
 except BaseException as exc:receipt.update(status='bounded_probe_failed',exception_class=type(exc).__name__)
 finally:
  signal.alarm(0)
  if api is not None:
   try:
    signal.alarm(5)
    with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):api.close()
   except BaseException as exc:receipt['close_exception_class']=type(exc).__name__
   finally:signal.alarm(0)
  receipt['completed_at']=now();write(OUT/'receipt.json',receipt)
  print(json.dumps({'status':receipt['status'],'serial_request_attempts':receipt['serial_request_attempts'],'requests':[{'rid':r['requirement_id'],'status':r['status'],'target_rows':r.get('target_guard_rows'),'identity_status':r.get('identity_status')} for r in receipt['requests']]},ensure_ascii=False))
if __name__=='__main__':run()
