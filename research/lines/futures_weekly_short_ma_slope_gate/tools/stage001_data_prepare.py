"""Independent 19-product daily-only append to 2026-10-29; no strategy execution."""
from pathlib import Path
from datetime import datetime,date
from zoneinfo import ZoneInfo
import contextlib, hashlib, importlib.util, io, json, logging, os, re, shutil, signal, sqlite3, sys, time
import pandas as pd
ROOT=Path(__file__).resolve().parents[4]
LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate'
SOURCE=Path('/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian')
OLD=SOURCE/'research/lines/futures_weekly_formal_no_half_r'
BASE=OLD/'outputs/stage032_latest_data/data_approved'
OUT=LINE/'outputs/data_stage001_20261029'
TARGET='2026-10-29'; TZ=ZoneInfo('Asia/Shanghai')
HELPER=ROOT/'research/lines/futures_weekly_formal_no_half_r/tools/stage032_latest_data.py'
spec=importlib.util.spec_from_file_location('frozen_stage032_daily_helper',HELPER); helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
sha=helper.sha; dump=helper.dump; FIELDS=helper.FIELDS

def main():
 if OUT.exists():raise ValueError('immutable_data_output_exists')
 OUT.mkdir();rawdir=OUT/'raw';rawdir.mkdir();(rawdir/'raw_daily').mkdir();target=OUT/'data_approved'
 os.environ.update(TZ='Asia/Shanghai',OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED='0',OFFICIAL_LIVE_PHASE_D_SESSION_DAEMON_ENABLED='0');time.tzset()
 receipt=json.loads((BASE/'receipt.json').read_text());assert receipt['date_end']=='2026-10-28' and receipt['data_ready_for_bounded_replay']
 products=receipt['products'];assert len(products)==len(set(products))==19
 basefiles=[p for p in BASE.iterdir() if p.is_file() and p.name!='source_manifest.json']
 inputs={str(p):sha(p) for p in basefiles+[BASE/'source_manifest.json',HELPER,Path(__file__)]}
 prior=json.loads((BASE/'source_manifest.json').read_text())['files']
 for p in basefiles:
  if str(p) in prior and prior[str(p)]!=inputs[str(p)]:raise ValueError('frozen_base_changed:'+p.name)
 epochs=pd.read_csv(BASE/'physical_epochs.csv',dtype=str).fillna('').to_dict('records')
 olddaily=pd.read_csv(BASE/'physical_epoch_daily.csv',dtype=str).fillna('');oldmap=pd.read_csv(BASE/'mapping.csv',dtype=str).fillna('')
 heldpath=OLD/'outputs/stage032_A_attempt002/positions.csv';pendpath=OLD/'outputs/stage032_A_attempt002/pending_orders.csv'
 inputs[str(heldpath)]=sha(heldpath);inputs[str(pendpath)]=sha(pendpath)
 held=pd.read_csv(heldpath,usecols=['date','vt_symbol','end_pos']);held=sorted(set(held.loc[held.date.eq(TARGET if TARGET in set(held.date) else '2026-10-28') & held.end_pos.ne(0),'vt_symbol']))
 pending=pd.read_csv(pendpath);pending=sorted(set(pending.vt_symbol)) if 'vt_symbol' in pending else []
 recent=sorted(set(olddaily.loc[olddaily.date.eq('2026-10-28'),'vt_symbol']))
 status={'schema':'weekly_short_slope_data_probe_v1','target':TARGET,'started_at':datetime.now(TZ).isoformat(),'financial_replays':0,'ctp_connected':False,'order_api_calls':0,'guards':{'insert_order_calls':0,'cancel_order_calls':0}}
 api=None;phase='preflight';oldlogging=logging.root.manager.disable;oldsignal=signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('bounded_data_budget')))
 try:
  if datetime.now(TZ)<datetime(2026,10,29,15,30,tzinfo=TZ):raise ValueError('target_not_completed')
  logging.disable(logging.CRITICAL);signal.alarm(160)
  creds=json.loads(Path('/Users/mac/Desktop/fian/.vntrader/vt_setting.json').read_text())
  phase='fresh_mapping'
  with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
   from tqsdk import TqApi,TqAuth,TqSim
   from tqsdk.calendar import TqContCalendar
   import requests
   auth=TqAuth(creds['datafeed.username'],creds['datafeed.password']);auth.login()
   response=requests.get('https://files.shinnytech.com/continuous_table.json',headers=auth._base_headers,timeout=25);response.raise_for_status()
   (rawdir/'fresh_main_continuous_table.raw.json').write_bytes(response.content)
   TqContCalendar.continuous={'KQ.m@'+k:v for k,v in response.json().items()}
   symbols=['KQ.m@'+p.split('.')[1]+'.'+p.split('.')[0] for p in products]
   cal=TqContCalendar(start_dt=date(2026,10,28),end_dt=date(2026,10,30),symbols=symbols,headers=auth._base_headers)
  cal.df.to_csv(rawdir/'fresh_calendar.csv',index=False)
  rows=[]
  for r in cal.df.to_dict('records'):
   day=str(r['date'])[:10]
   for prod,key in zip(products,symbols):
    v='' if pd.isna(r.get(key)) else str(r[key])
    if not v or '.' not in v:raise ValueError('fresh_mapping_missing:'+prod+':'+day)
    ex,code=v.split('.',1);rows.append(dict(date=day,product=prod.split('.')[0],exchange=prod.split('.')[1],continuous_symbol_tq=key,continuous_symbol_vt=prod,main_contract_tq=v,main_contract_vt=code+'.'+ex))
  fresh=pd.DataFrame(rows);newmap=fresh.loc[fresh.date.eq(TARGET)].copy();helper.validate_mapping(newmap,products,[TARGET])
  overlap=oldmap.loc[oldmap.date.eq('2026-10-28')].merge(fresh.loc[fresh.date.eq('2026-10-28')],on=['date','continuous_symbol_vt'],suffixes=('_frozen','_fresh'));overlap['main_matches']=overlap.main_contract_vt_frozen.eq(overlap.main_contract_vt_fresh);overlap.to_csv(rawdir/'mapping_overlap.csv',index=False)
  if len(overlap)!=19 or not overlap.main_matches.all():raise ValueError('frozen_mapping_observation_changed')
  new_symbols=sorted(set(newmap.main_contract_vt)-set(oldmap.main_contract_vt))
  if new_symbols:raise ValueError('new_contract_metadata_required:'+repr(new_symbols))
  wanted=sorted(set(recent)|set(held)|set(pending)|set(newmap.main_contract_vt))
  if len(wanted)>48:raise ValueError('contract_budget_exceeded')
  for sym in wanted:
   if re.sub(r'\d+(?=\.)','',sym) not in products:raise ValueError('outside_original19')
   helper.epoch_for(sym,TARGET,epochs)
  selection=dict(products=products,recent_tail=recent,frozen_held=held,frozen_pending=pending,new_main=sorted(set(newmap.main_contract_vt)),wanted=wanted,count=len(wanted),new_metadata_symbols=new_symbols,selection_uses_profit=False)
  dump(rawdir/'selection.json',selection);newmap.to_csv(rawdir/'new_mapping.csv',index=False)
  def blocked(key):
   def f(*a,**kw):status['guards'][key]+=1;raise RuntimeError('order_api_forbidden')
   return f
  TqApi.insert_order=blocked('insert_order_calls');TqApi.cancel_order=blocked('cancel_order_calls')
  phase='daily_serials'
  with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
   api=TqApi(TqSim(),auth=auth,disable_print=True,debug=False);serials={}
   async def subscribe():
    for sym in wanted:
     code,ex=sym.split('.');serials[sym]=api.get_kline_serial(ex+'.'+code,86400,data_length=30)
   api.create_task(subscribe())
   while len(serials)!=len(wanted) or not all(api.is_serial_ready(x) for x in serials.values()):api.wait_update(deadline=time.time()+1)
  rawrows=[];observation=[];statuses=[]
  frozenlookup={(r['vt_symbol'],r['date']):r for r in olddaily.loc[olddaily.date.eq('2026-10-28')].to_dict('records')}
  for sym,serial in sorted(serials.items()):
   raw=serial.copy();p=rawdir/'raw_daily'/(sym+'.csv');raw.to_csv(p,index=False);digest=sha(p)
   f=raw.loc[pd.to_numeric(raw.datetime).gt(0)&pd.to_numeric(raw.id).ge(0)].copy();f['date']=pd.to_datetime(pd.to_numeric(f.datetime),unit='ns',utc=True).dt.tz_convert(TZ).dt.strftime('%Y-%m-%d')
   if f.date.duplicated().any() or 'duration' not in f:raise ValueError('daily_schema_or_duplicate:'+sym)
   for r in f.loc[f.date.eq(TARGET)].to_dict('records'):
    rawrows.append(dict(vt_symbol=sym,date=TARGET,**{k:r[k] for k in FIELDS},duration=r['duration'],source_id='stage001_predeclared_Tq_daily_close_oi_20261029',source_path=str(p),source_sha256=digest,source_locator=json.dumps({'date':TARGET,'id':r['id'],'datetime_ns':r['datetime']})))
   for r in f.loc[f.date.eq('2026-10-28')].to_dict('records'):
    old=frozenlookup.get((sym,'2026-10-28'))
    if old:observation.append(dict(vt_symbol=sym,date='2026-10-28',old_authority_preserved=True,differences={k:{'frozen':float(old[k]),'fresh':float(r[k])} for k in FIELDS if float(old[k])!=float(r[k])}))
   statuses.append(dict(vt_symbol=sym,raw_sha256=digest,target_rows=int(f.date.eq(TARGET).sum()),excluded_forming_or_future_rows=int(f.date.gt(TARGET).sum())))
  dump(rawdir/'new_rows.json',rawrows);dump(rawdir/'overlap_observations.json',observation);dump(rawdir/'contract_statuses.json',statuses)
  accepted,rejected=helper.admit_rows(rawrows,epochs,{TARGET})
  required={(s,TARGET) for s in set(newmap.main_contract_vt)|set(held)|set(pending)};helper.require_daily_keys(accepted,required)
  oldkeys=set(zip(olddaily.vt_symbol,olddaily.date));assert not any((r['vt_symbol'],r['date']) in oldkeys for r in accepted)
  phase='assemble';target.mkdir()
  for p in basefiles:
   if p.name in {'daily.sqlite','physical_epoch_daily.csv','mapping.csv','receipt.json','source_manifest.json'}:continue
   shutil.copyfile(p,target/p.name)
  new=pd.DataFrame(accepted,columns=olddaily.columns).sort_values(['date','vt_symbol']);newmap=newmap[list(oldmap.columns)].sort_values(['date','continuous_symbol_vt'])
  for name,frame in [('physical_epoch_daily.csv',new),('mapping.csv',newmap)]:
   prefix=(BASE/name).read_bytes();assert prefix.endswith(b'\n');(target/name).write_bytes(prefix+frame.to_csv(index=False,header=False).encode())
  dbproof=helper.append_sqlite(BASE/'daily.sqlite',target/'daily.sqlite',accepted)
  new.to_csv(target/'admitted_20261029_daily.csv',index=False);newmap.to_csv(target/'admitted_20261029_mapping.csv',index=False)
  pd.DataFrame(rejected,columns=['vt_symbol','date','classification','source_path','source_sha256','source_locator']).to_csv(target/'rejected_20261029_not_bar.csv',index=False)
  merged=pd.read_csv(target/'physical_epoch_daily.csv',dtype=str).fillna('');assert merged.iloc[:len(olddaily)].reset_index(drop=True).equals(olddaily.reset_index(drop=True));assert not merged.duplicated(['vt_symbol','date']).any()
  proof=dict(**dbproof,old_accepted_rows=len(olddaily),new_accepted_rows=len(new),accepted_rows=len(merged),old_physical_rows_all_fields_exact=True,old_physical_csv_bytes_prefix_exact=True,old_mapping_bytes_prefix_exact=True,metadata_bytes_unchanged=sha(BASE/'metadata.csv')==sha(target/'metadata.csv'),physical_epochs_bytes_unchanged=sha(BASE/'physical_epochs.csv')==sha(target/'physical_epochs.csv'),required_key_count=len(required),required_keys_missing=0,zero_invalid_rejected=len(rejected),units='single_sided_volume_close_oi',no_price_or_date_fallback=True)
  dump(target/'stage001_additive_preservation_proof.json',proof)
  result={**receipt,'schema':'stage001_independent19_Tq_daily_extension_v1','date_end':TARGET,'requested_financial_end':TARGET,'status':'prepared_independent19_additive_Tq_20261029','accepted_rows':len(merged),'base_data_directory':str(BASE),'base_receipt_sha256':sha(BASE/'receipt.json'),'base_source_manifest_sha256':sha(BASE/'source_manifest.json'),'data_ready':True,'data_ready_for_bounded_replay':True,'historical_main_reconstruction_complete':False,'units':'single_sided_volume_close_oi','next_trading_date':'2026-10-30','latest_day_is_completed_week':False,'source_consensus_claim':False,'source_authority':'Stage032 frozen <=20261028 preserved; predeclared fresh Tq close_oi 20261029 only','new_data':proof,'latest_probe_directory':str(rawdir),'financial_replays':0,'ctp_connected':False,'order_api_calls':0,'promotion_decision':'NO_PROMOTION','completed_at':datetime.now(TZ).isoformat(),'readiness_limitations':receipt['readiness_limitations']+['10/29 Tq daily observed after 15:30; not exchange-final arbitration. 10/30 forming rows excluded.','Original19 standalone snapshot; no source from ongoing44 research. All historical PIT, lifecycle gaps, static metadata and capacity limitations inherited.']}
  dump(target/'receipt.json',result)
  changed=[p for p,d in inputs.items() if sha(p)!=d]
  if changed:raise ValueError('frozen_inputs_changed')
  status.update(status='data_ready',new_accepted_rows=len(new),required_keys_missing=0,data_directory=str(target),base_inputs_unchanged=True,new_mapping_rows=len(newmap),contract_count=len(wanted),source_manifest_inherits_lineage=True)
 except Exception as exc:
  status.update(status='failed',failure_stage=phase,error_type=type(exc).__name__,data_gate_detail=str(exc) if isinstance(exc,ValueError) else None)
 finally:
  signal.alarm(0);signal.signal(signal.SIGALRM,oldsignal)
  if api:
   with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):api.close()
  logging.disable(oldlogging);status['completed_at']=datetime.now(TZ).isoformat();dump(OUT/'probe_receipt.json',status)
 if status['status']=='data_ready':
  files={**inputs,**{str(p):sha(p) for p in OUT.rglob('*') if p.is_file()}}
  dump(target/'source_manifest.json',dict(schema='stage001_independent19_source_manifest_v1',files=files,source_manifest_self_not_in_files=True,immutable_output=True,lineage_manifest_sha256=sha(BASE/'source_manifest.json'),inherited_sources_kept_via_frozen_lineage_not_recopied=True))
 print(json.dumps(status,ensure_ascii=False))
 return 0 if status['status']=='data_ready' else 1
if __name__=='__main__':raise SystemExit(main())
