"""Actual TQ calendar capture only; no TqApi/account/order/CTP or source rewrite."""
from pathlib import Path
from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo
import hashlib,json,logging,os,stat,sys,uuid
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[4];STAGE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate/stages'
sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT)]
logging.disable(logging.CRITICAL)
SETTING=Path('/Users/mac/Desktop/person/vnpy_production_live/.vntrader/vt_setting.json')
OLD=Path('/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/outputs/data_stage014_20261030')
SHA=lambda raw:hashlib.sha256(raw).hexdigest()
def file_sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def write_private(path,raw):
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
def main():
 now=datetime.now(ZoneInfo('Asia/Shanghai'));today=now.date();start=date(2026,10,30);end=today+timedelta(days=21)
 base=Path('/Users/mac/Library/Application Support/qmt-roll-stage179/weekly19-calendar-candidates')
 if base.is_symlink():raise ValueError('private_calendar_root_symlink_forbidden')
 base.mkdir(mode=0o700,parents=True,exist_ok=True)
 if base.stat().st_uid!=os.geteuid() or stat.S_IMODE(base.stat().st_mode)!=0o700:raise ValueError('private_calendar_root_0700_required')
 generation=base/('Stage018_calendar_'+now.strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:8]);generation.mkdir(mode=0o700)
 receipt=dict(schema='Stage018.actual-tq-calendar-generation.v1',recorded_at=now.isoformat(),scope='calendar_only_no_strategy_or_account',status='started',production_qualified=False,credential_values_serialized=False,ctp_connections=0,order_api_calls=0,market_daily_downloads=0,calendar_start=start.isoformat(),calendar_end=end.isoformat(),generation_path=str(generation),source_responses=[])
 old_paths=[OLD/'data_approved'/name for name in ('daily.sqlite','mapping.csv','physical_epoch_daily.csv','metadata.csv','receipt.json')]+[OLD/'raw/fresh_calendar.csv']
 receipt['old_frozen_sources_before']={str(p):file_sha(p) for p in old_paths}
 phase='read_actual_stable_settings'
 try:
  fd=os.open(SETTING,os.O_RDONLY|os.O_NOFOLLOW)
  with os.fdopen(fd) as f:
   info=os.fstat(f.fileno())
   if info.st_uid!=os.geteuid() or stat.S_IMODE(info.st_mode)!=0o600:raise ValueError('stable_settings_private_0600_required')
   settings=json.load(f)
  username=str(settings.get('datafeed.username') or '');password=str(settings.get('datafeed.password') or '')
  if not username or not password:raise ValueError('actual_stable_tq_credentials_missing')
  receipt['credential_source']=dict(path=str(SETTING),private_mode='0600',username_present=True,password_present=True,read_only=True)
  from vnpy.trader.setting import SETTINGS
  SETTINGS.update({'datafeed.username':username,'datafeed.password':password,'log.file':False,'log.console':False})
  del settings,username,password
  from tqsdk import TqAuth
  import tqsdk,tqsdk.calendar as calendar,requests
  for name,expected in [('TQ_AUTH_URL','https://auth.shinnytech.com'),('TQ_CHINESE_HOLIDAY_URL','https://files.shinnytech.com/shinny_chinese_holiday.json'),('TQ_CONT_TABLE_URL','https://files.shinnytech.com/continuous_table.json')]:
   if os.environ.get(name,expected)!=expected:raise ValueError('nondefault_tq_calendar_endpoint_forbidden')
  receipt['sdk']=dict(version=tqsdk.__version__,calendar_source_path=calendar.__file__,calendar_source_sha256=file_sha(Path(calendar.__file__)))
  receipt['code_sources_before']={str(p.relative_to(ROOT)):file_sha(p) for p in (Path(__file__),ROOT/'examples/portfolio_backtesting/qmt_roll_weekly19_data_update.py',ROOT/'examples/portfolio_backtesting/build_qmt_roll_stage173_forward_main_contract_data_update.py')}
  allowed={('POST','auth.shinnytech.com','/auth/realms/shinnytech/protocol/openid-connect/token'),('GET','files.shinnytech.com','/shinny_chinese_holiday.json'),('GET','files.shinnytech.com','/continuous_table.json')}
  original=requests.Session.send
  def send(session,request,**kwargs):
   uri=urlsplit(request.url)
   if uri.scheme!='https' or uri.query or (request.method,uri.netloc,uri.path) not in allowed:raise ValueError('calendar_only_http_allowlist_violation')
   if kwargs.get('verify') is False:raise ValueError('calendar_tls_verification_required')
   if kwargs.get('timeout') is None:kwargs['timeout']=(10,30)
   response=original(session,request,**kwargs)
   if uri.netloc=='auth.shinnytech.com':
    receipt['tq_auth_http_status']=response.status_code
   else:
    response.raise_for_status();raw=response.content
    target=generation/Path(uri.path).name;write_private(target,raw)
    receipt['source_responses'].append(dict(url=uri.geturl(),observed_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),status_code=response.status_code,raw_path=str(target),raw_sha256=SHA(raw),raw_bytes=len(raw),headers={k:response.headers[k] for k in ('Date','Last-Modified','ETag','Content-Type') if k in response.headers}))
   return response
  requests.Session.send=send
  try:
   phase='actual_tq_auth_login';auth=TqAuth(SETTINGS['datafeed.username'],SETTINGS['datafeed.password']);auth.login()
   phase='actual_tq_calendar_http'
   products=__import__('pandas').read_csv(ROOT/'examples/portfolio_backtesting/weekly19_assets/static19.csv').product_vt_symbol.astype(str).tolist()
   symbols=['KQ.m@'+p.split('.')[1]+'.'+p.split('.')[0] for p in products]
   cal=calendar.TqContCalendar(start_dt=start,end_dt=end,symbols=symbols,headers=auth._base_headers)
   frame=cal.df.copy();phase='validate_actual_calendar_coverage'
   holidays=json.loads((generation/'shinny_chinese_holiday.json').read_bytes())
   if not isinstance(holidays,list) or not holidays:raise ValueError('holiday_source_missing')
   parsed=[date.fromisoformat(v) for v in holidays]
   year_start=date(min(parsed).year,1,1);year_end=date(max(parsed).year,12,31)
   if start<year_start or end>year_end:raise ValueError('official_tq_holiday_year_coverage_insufficient')
   days=[(v.date() if hasattr(v,'date') else v).isoformat() for v in frame.date]
   if len(days)!=len(set(days)) or days!=sorted(days) or '2026-10-30' not in days or '2026-11-02' not in days:raise ValueError('actual_calendar_required_day_or_uniqueness_failed')
   next_days=[d for d in days if d>today.isoformat()]
   if not next_days or max(days)<(today+timedelta(days=14)).isoformat():raise ValueError('actual_forward_calendar_less_than_14_days')
   if set(frame.columns)-{'date','_cst_date'}!=set(symbols):raise ValueError('actual_calendar_fixed19_columns_mismatch')
   csv=frame.assign(date=frame.date.map(lambda v:v.date().isoformat() if hasattr(v,'date') else v)).to_csv(index=False).encode()
   calendar_path=generation/'forward_calendar.csv';write_private(calendar_path,csv)
   receipt.update(status='captured_actual_tq_calendar_conditional',calendar_path=str(calendar_path),calendar_sha256=SHA(csv),trading_dates=days,next_trading_day=next_days[0],future_calendar_days_coverage=(end-today).days,holiday_source_coverage=[year_start.isoformat(),year_end.isoformat()],trading_dates_sha256=SHA(json.dumps(days,sort_keys=True,separators=(',',':')).encode()),fixed19_columns=symbols,calendar_semantics='installed_TQSDK_weekday_and_actual_vendor_holiday_table; no caller_bdate_guess; future main assignments are calendar-only estimates not execution metadata',reuse_old_snapshot=False)
  finally:requests.Session.send=original
 except Exception as exc:
  # Authentication responses/tokens/usernames are deliberately never serialized.
  receipt.update(status='blocked',failed_phase=phase,error_type=type(exc).__name__,error_details_withheld_for_credentials=True)
 finally:
  receipt['old_frozen_sources_after']={str(p):file_sha(p) for p in old_paths};receipt['old_frozen_sources_unchanged']=receipt['old_frozen_sources_before']==receipt['old_frozen_sources_after']
  if receipt.get('code_sources_before'):receipt['code_sources_after']={p:file_sha(ROOT/p) for p in receipt['code_sources_before']};receipt['code_unchanged']=receipt['code_sources_before']==receipt['code_sources_after']
  raw=json.dumps(receipt,ensure_ascii=False,sort_keys=True,indent=2).encode()+b'\n';write_private(generation/'receipt.json',raw)
  summary={k:v for k,v in receipt.items() if k not in ('credential_source','source_responses')};summary['credential_source_path']=str(SETTING);summary['receipt_path']=str(generation/'receipt.json');summary['receipt_sha256']=SHA(raw)
  (STAGE/'Stage018_signal_scope_calendar_generation_receipt.json').write_text(json.dumps(summary,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
  print(json.dumps({k:summary.get(k) for k in ('status','failed_phase','error_type','next_trading_day','calendar_path','calendar_sha256','calendar_end','receipt_path','receipt_sha256','old_frozen_sources_unchanged')},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
