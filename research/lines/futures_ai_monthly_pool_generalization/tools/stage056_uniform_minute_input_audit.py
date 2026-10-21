"""Uniform conditional minute-input audit; never C2 outcomes, source fills or fit."""
from copy import deepcopy
from datetime import date,datetime
import hashlib,io,json,math,multiprocessing as mp,sqlite3,time
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from stage055_minute_input_qualification import reference_grid,qualify_component
from stage018_finite_path_ledger import execution

LINE=Path(__file__).resolve().parents[1];ROOT=LINE.parents[2]
OUT=LINE/'outputs/stage056_uniform_minute_input_audit'
REQDIR=LINE/'outputs/stage052_exact_c2_data_requirements';INV=LINE/'outputs/stage054_existing_minute_reusability'
PRIOR=ROOT/'research/lines/futures_trend_rollover_shape_same_volume/outputs'
EXPECTED_055='9736b1b0a362e4a12b2c7839db067c59e0a3b430be0c65c384f2a4433ba9d8c2'
_REQUESTS={};_GRIDS={};_EPOCHS={};_META={};_FILE_REQ={};_CACHE={}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return pd.read_csv(path,dtype=str,keep_default_na=False)
def canonical_day(value):
 if not isinstance(value,str):raise ValueError('invalid_iso_source_day')
 try:d=date.fromisoformat(value)
 except ValueError:raise ValueError('invalid_iso_source_day') from None
 if d.isoformat()!=value:raise ValueError('invalid_iso_source_day')
 return value


def make_identity_binding(request,epoch,metadata,source_id,component,observed_symbols):
 day=canonical_day(request['source_trade_date']);key=request['contract_epoch_id'];exchange,product,month=key.split('.')
 if epoch.get('contract_epoch_id')!=key or str(epoch.get('contract_yyyymm'))!=month or epoch.get('exchange')!=exchange or epoch.get('product','').upper()!=product.upper():raise ValueError('exact_epoch_catalog_identity_mismatch')
 if epoch.get('order_book_id')!=request.get('metadata_order_book_id_hint') or metadata.get('order_book_id')!=epoch.get('order_book_id') or metadata.get('exchange')!=exchange or metadata.get('underlying_symbol','').upper()!=product.upper():raise ValueError('exact_epoch_vendor_metadata_mismatch')
 listed=canonical_day(metadata.get('listed_date'));delisted=canonical_day(metadata.get('de_listed_date'))
 if not listed<=day<=delisted:raise ValueError('source_trade_day_outside_metadata_contract_lifetime')
 native=metadata.get('trading_code','')+'.'+exchange
 if not observed_symbols or any(not isinstance(s,str) or s.casefold()!=native.casefold() for s in observed_symbols):raise ValueError('payload_native_contract_mismatch')
 if not isinstance(source_id,str) or not source_id or not isinstance(component,str) or not component:raise ValueError('source_component_identity_missing')
 return dict(contract_epoch_id=key,source_trade_date=day,source_id=source_id,component=component,
   identity_basis='exact_epoch_catalog_month_and_order_book_id; vendor_metadata_native_payload_key; source_day_within_exact_contract_metadata_lifetime',
   metadata_order_book_id=metadata['order_book_id'],metadata_native_key=native,metadata_listed_date=listed,metadata_delisted_date=delisted,
   broker_symbol_qualified=False,physical_session_verified=False)


def session_envelope(frame,expected):
 return frame.loc[frame.bar_datetime.ge(expected[0])&frame.bar_datetime.le(expected[-1])].copy()


def _load_csv(path,cache=False):
 if path in _CACHE:return _CACHE[path]
 p=Path(path);before=p.stat();payload=p.read_bytes();digest=hashlib.sha256(payload).hexdigest();header=payload.splitlines()[0].decode('utf-8-sig').split(',')
 use=[k for k in ['vt_symbol','bar_datetime','open','high','low','close','minute_source','contract_epoch_id','source_trade_date'] if k in header]
 frame=pd.read_csv(io.BytesIO(payload),usecols=use)
 after=p.stat()
 if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):raise ValueError('source_changed_during_read')
 record=dict(path=path,bytes=before.st_size,mtime_ns=before.st_mtime_ns,inode=before.st_ino,sha256=digest,rows=len(frame),projected_columns=use)
 if 'bar_datetime' in frame:
  stamps=pd.to_datetime(frame.bar_datetime,format='mixed',errors='coerce')
  if isinstance(stamps.dtype,pd.DatetimeTZDtype):stamps=stamps.dt.tz_convert('Asia/Shanghai').dt.tz_localize(None)
  elif stamps.dtype==object:stamps=frame.bar_datetime.map(execution.local_timestamp)
  frame['bar_datetime']=stamps
 if 'minute_source' in frame:frame['minute_source']=frame.minute_source.fillna('__unspecified__').astype(str)
 if cache:_CACHE[path]=(frame,record)
 return frame,record


def _audit_frame(frame,record,request_ids):
 audits=[];passed=[]
 for rid in request_ids:
  req=_REQUESTS[rid];expected=_GRIDS[rid];meta=_META.get(req['metadata_order_book_id_hint']);epoch=_EPOCHS.get(req['contract_epoch_id'])
  base=dict(requirement_id=rid,contract_epoch_id=req['contract_epoch_id'],source_trade_date=req['source_trade_date'],state_id=req['state_id'],source_path=record['path'],source_sha256=record['sha256'],physical_session_verified=False,usable_for_trading=False)
  if not meta or not epoch:
   audits.append({**base,'status':'exact_metadata_identity_missing'});continue
  if 'vt_symbol' not in frame or 'bar_datetime' not in frame:
   audits.append({**base,'status':'native_or_timestamp_column_missing'});continue
  native=(meta['trading_code']+'.'+meta['exchange']).casefold()
  selected=frame.loc[frame.vt_symbol.astype(str).str.casefold().eq(native)]
  if selected.empty:audits.append({**base,'status':'payload_native_contract_mismatch'});continue
  if selected.bar_datetime.isna().any():audits.append({**base,'status':'invalid_timestamp'});continue
  clipped=session_envelope(selected,expected)
  if 'minute_source' in selected:
   components=list(selected.minute_source.drop_duplicates())
  else:components=['__file_provider_unspecified__']
  for component in components:
   part=clipped.loc[clipped.minute_source.eq(component)].copy() if 'minute_source' in clipped else clipped.copy()
   sid=hashlib.sha256((record['path']+'\n'+record['sha256']+'\n'+component).encode()).hexdigest()
   try:binding=make_identity_binding(req,epoch,meta,sid,component,list(part.vt_symbol.unique()) if not part.empty else [meta['trading_code']+'.'+meta['exchange']])
   except ValueError as e:audits.append({**base,'source_id':sid,'component':component,'status':str(e)});continue
   # A zero-row source has no target session identity observation. Keep a reject.
   if part.empty:audits.append({**base,'source_id':sid,'component':component,'status':'no_rows_in_reference_session_envelope','expected_minutes':len(expected),'observed_minutes':0});continue
   binding.update(source_path=record['path'],source_payload_sha256=record['sha256'],source_hash_scope=record.get('hash_scope','entire_csv_single_read'),expected_grid_sha256=hashlib.sha256('\n'.join(t.isoformat() for t in expected).encode()).hexdigest(),kernel055_sha256=EXPECTED_055,expected_minutes=len(expected),reference_session_start=expected[0].isoformat(),reference_session_last=expected[-1].isoformat(),source_daily_OHLC={k:float(req['source_'+k]) for k in ['open','high','low','close']},entry_open=float(req['entry_price']))
   outcome=qualify_component(part,expected,req,binding)
   audits.append({**base,'source_id':sid,'component':component,'binding':binding,**{k:v for k,v in outcome.items() if k!='minute_path'}})
   if outcome['status']=='conditional_reference_input_qualified':passed.append(dict(requirement_id=rid,state_id=req['state_id'],binding=binding,minute_path=outcome['minute_path']))
 return audits,passed


def _audit_csv(path):
 ids=_FILE_REQ[path]
 try:frame,record=_load_csv(path);audits,passed=_audit_frame(frame,record,ids)
 except (OSError,ValueError,UnicodeError,pd.errors.ParserError) as e:
  record=dict(path=path,error=type(e).__name__+':'+str(e),rows=None)
  audits=[dict(requirement_id=rid,source_path=path,status='source_read_or_parse_error',error=record['error']) for rid in ids];passed=[]
 return dict(source=record,audits=audits,passed=passed)


def _audit_sqlite():
 path=ROOT/'.vntrader/database.db';before=path.stat();overview=read(INV/'sqlite_1m_indexed_inventory.csv');by={(r['symbol']+'.'+r['exchange']).casefold():r for r in overview.to_dict('records')}
 groups={}
 for rid,req in _REQUESTS.items():
  meta=_META.get(req['metadata_order_book_id_hint'])
  if meta:
   key=(meta['trading_code']+'.'+meta['exchange']).casefold()
   if key in by:groups.setdefault(key,[]).append(rid)
 results=[]
 with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as c:
  c.execute('PRAGMA query_only=ON')
  for key,ids in sorted(groups.items()):
   meta=by[key];frame=pd.read_sql_query("SELECT symbol,exchange,datetime AS bar_datetime,open_price AS open,high_price AS high,low_price AS low,close_price AS close FROM dbbardata WHERE symbol=? AND exchange=? AND interval='1m' ORDER BY datetime",c,params=[meta['symbol'],meta['exchange']])
   frame['vt_symbol']=frame.symbol+'.'+frame.exchange;frame['bar_datetime']=pd.to_datetime(frame.bar_datetime,format='mixed',errors='coerce');frame=frame.drop(columns=['symbol','exchange'])
   digest=hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest();record=dict(path=str(path)+'#dbbardata:'+key,sqlite_path=str(path),native_key=key,bytes=before.st_size,mtime_ns=before.st_mtime_ns,inode=before.st_ino,sha256=digest,rows=len(frame),hash_scope='indexed_projection_csv_not_entire_db')
   audits,passed=_audit_frame(frame,record,ids);results.append(dict(source=record,audits=audits,passed=passed))
 after=path.stat()
 if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):raise ValueError('minute_sqlite_changed_during_read')
 return results


def _prepare():
 global _REQUESTS,_GRIDS,_EPOCHS,_META,_FILE_REQ
 module=LINE/'tools/stage055_minute_input_qualification.py'
 if sha(module)!=EXPECTED_055:raise ValueError('055_kernel_sha_changed_do_not_run')
 calendar=pd.to_datetime(np.load(PRIOR/'stage265_deep_daily/rqalpha/trading_dates.npy',allow_pickle=False).astype(str),format='%Y%m%d')
 _EPOCHS={r['contract_epoch_id']:r for r in read(LINE/'outputs/stage006_economic_coverage/epoch_economic_inventory.csv').to_dict('records')}
 _META={r['order_book_id']:r for r in json.loads((PRIOR/'stage265_deep_daily/rqalpha/futures_metadata.json').read_text())}
 states=read(REQDIR/'distinct_state_requirements.csv');unsupported=[]
 for r in states.to_dict('records'):
  try:expected=reference_grid(r,calendar)
  except ValueError as e:unsupported.append(dict(requirement_id=r['requirement_id'],contract_epoch_id=r['contract_epoch_id'],source_trade_date=r['source_trade_date'],status='unsupported_reference_scope',reason=str(e)));continue
  _REQUESTS[r['requirement_id']]=r;_GRIDS[r['requirement_id']]=expected
 if len(_REQUESTS)!=132 or len(unsupported)!=778:raise ValueError('scope_changed_requires_review')
 with sqlite3.connect((PRIOR/'stage266_clean_daily/clean_daily.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as c:
  c.execute('PRAGMA query_only=ON')
  for req in _REQUESTS.values():
   raw=c.execute('SELECT open,high,low,close FROM daily_bars WHERE contract_epoch_id=? AND trade_date=?',(req['contract_epoch_id'],req['source_trade_date'])).fetchone()
   if raw is None or any(not math.isclose(float(req['source_'+k]),float(v),rel_tol=0,abs_tol=1e-8) for k,v in zip(['open','high','low','close'],raw)):raise ValueError('052_source_state_clean_OHLC_changed')
 pairs=read(INV/'exact_requirement_native_cache_candidates.csv');pairs=pairs.loc[pairs.requirement_id.isin(_REQUESTS)]
 _FILE_REQ={path:sorted(set(f.requirement_id)) for path,f in pairs.groupby('path',sort=True)}
 if len(_FILE_REQ)!=428:raise ValueError('candidate_file_scope_changed_requires_review')
 return unsupported


def choose_missing_pilot(evidence,file_requests,requests):
 rows=evidence.loc[evidence.qualification_level.eq('incomplete_grid') & evidence.source_path.isin(file_requests) & evidence.requirement_id.isin(requests)].sort_values(['epoch','source_trade_date','source_path'])
 return None if rows.empty else rows.iloc[0].to_dict()


def run(workers=4):
 started=datetime.now(ZoneInfo('Asia/Shanghai'));unsupported=_prepare()
 target=OUT/started.strftime('run_%Y%m%d_%H%M%S_%f');target.mkdir(parents=True,exist_ok=False)
 pd.DataFrame(unsupported).to_csv(target/'unsupported_requirements.csv',index=False)
 candidates=read(INV/'exact_requirement_native_cache_candidates.csv');candidates=candidates.loc[candidates.requirement_id.isin(_REQUESTS)]
 order=sorted(_REQUESTS,key=lambda rid:(_REQUESTS[rid]['source_trade_date'],_REQUESTS[rid]['contract_epoch_id']))
 pilotpairs=[]
 for rid in [order[0],order[-1]]:
  choices=sorted(candidates.loc[candidates.requirement_id.eq(rid),'path'])
  if choices:pilotpairs.append((rid,choices[0],'fixed_earliest_or_latest'))
 old=read(INV/'exact_requirement_old_witness_matches.csv')
 for product in ['AU','JM']:
  matched=old.loc[old.qualification_level.eq('conditional_complete_session_OHLC_witness')&old.epoch.str.split('.').str[1].eq(product)].sort_values(['source_trade_date','source_path'])
  if len(matched):r=matched.iloc[0];pilotpairs.append((r.requirement_id,r.source_path,'fixed_old_'+product+'_data_witness'))
 missing=choose_missing_pilot(old,_FILE_REQ,_REQUESTS)
 if missing is not None:pilotpairs.append((missing['requirement_id'],missing['source_path'],'fixed_incomplete_grid_case'))
 (target/'pilot_plan.json').write_text(json.dumps(pilotpairs,ensure_ascii=False,indent=2)+'\n')
 pilot=[]
 for rid,path,reason in pilotpairs:
  if path not in _FILE_REQ:raise ValueError('pilot_file_outside_uniform_scope')
  frame,record=_load_csv(path,cache=True);audits,passed=_audit_frame(frame,record,[rid]);pilot.append(dict(reason=reason,source=record,audits=audits,qualified_paths=len(passed)))
 # Assert prior known complete inputs still qualify as data; no C2 outcome check.
 for p in pilot:
  if p['reason'].startswith('fixed_old_') and not any(a['status']=='conditional_reference_input_qualified' for a in p['audits']):raise ValueError('pilot_old_data_witness_regression')
 (target/'pilot_results.json').write_text(json.dumps(pilot,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 print(json.dumps(dict(phase='pilot_complete',cases=len(pilot),source_files_cached=len(_CACHE),output=str(target)),ensure_ascii=False),flush=True)
 audits=[];sources=[];qualified={};members=[]
 def consume(value):
  sources.append(value['source']);audits.extend(value['audits'])
  for passed in value['passed']:
   canonical=json.dumps(passed['minute_path'],sort_keys=True,separators=(',',':'),allow_nan=False).encode();digest=hashlib.sha256(canonical).hexdigest();key=(passed['requirement_id'],digest)
   if key not in qualified:
    folder=target/'qualified_paths'/passed['requirement_id'];folder.mkdir(parents=True,exist_ok=True);path=folder/(digest+'.csv')
    pd.DataFrame(passed['minute_path']).to_csv(path,index=False)
    qualified[key]=dict(requirement_id=passed['requirement_id'],state_id=passed['state_id'],data_path=str(path),data_csv_sha256=sha(path),canonical_input_sha256=digest,rows=len(passed['minute_path']),source_ids=[],bindings=[],physical_session_verified=False,reference_policy_grid_only=True,usable_for_trading=False)
   qualified[key]['source_ids'].append(passed['binding']['source_id']);qualified[key]['bindings'].append(passed['binding']);members.append(dict(requirement_id=passed['requirement_id'],canonical_input_sha256=digest,source_id=passed['binding']['source_id']))
 with mp.get_context('fork').Pool(processes=min(4,max(1,workers))) as pool:
  for count,value in enumerate(pool.imap_unordered(_audit_csv,sorted(_FILE_REQ),chunksize=1),1):
   consume(value)
   if count%100==0:print(json.dumps(dict(phase='files',processed=count,total=len(_FILE_REQ))),flush=True)
 for value in _audit_sqlite():consume(value)
 if sha(LINE/'tools/stage055_minute_input_qualification.py')!=EXPECTED_055:raise ValueError('055_changed_during_audit_do_not_accept')
 pd.DataFrame(audits).to_csv(target/'all_source_component_audits.csv',index=False)
 (target/'source_bindings.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 paths=list(qualified.values());(target/'qualified_inputs_manifest.json').write_text(json.dumps(paths,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 pd.DataFrame(members).to_csv(target/'qualified_input_source_members.csv',index=False)
 rows=[]
 for rid,req in sorted(_REQUESTS.items()):
  group=[p for p in paths if p['requirement_id']==rid];aa=[a for a in audits if a['requirement_id']==rid]
  rows.append(dict(requirement_id=rid,contract_epoch_id=req['contract_epoch_id'],source_trade_date=req['source_trade_date'],distinct_month_windows=int(req['distinct_month_windows']),qualified_distinct_inputs=len(group),qualified_source_ids=sum(len(p['source_ids']) for p in group),audited_source_components=len(aa),status='conditional_reference_input_available' if group else 'no_qualified_reference_input',physical_session_verified=False,training_eligible=False))
 pd.DataFrame(rows).to_csv(target/'all132_requirement_results.csv',index=False)
 stats=dict(issued_at=started.isoformat(),completed_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),scope_requirements=132,unsupported_requirements=778,scope_month_windows=320,
   csv_files=len(_FILE_REQ),csv_file_reads=sum(1 for s in sources if not s.get('sqlite_path')),pilot_cached_files=len(_CACHE),source_component_audits=len(audits),source_status_counts=pd.Series([a['status'] for a in audits]).value_counts().to_dict(),
   qualified_requirements=sum(r['qualified_distinct_inputs']>0 for r in rows),qualified_month_windows=sum(r['distinct_month_windows'] for r in rows if r['qualified_distinct_inputs']>0),qualified_distinct_inputs=len(paths),qualified_source_members=len(members),
   requirements_with_multiple_distinct_inputs=sum(r['qualified_distinct_inputs']>1 for r in rows),csv_bytes_projected=sum(s.get('bytes',0) for s in sources if not s.get('sqlite_path')),csv_rows_projected=sum(s.get('rows',0) or 0 for s in sources if not s.get('sqlite_path')),
   sqlite_native_projections=sum(bool(s.get('sqlite_path')) for s in sources),strategy_runs=0,C2_outcomes=0,model_fits=0,labels_changed=0,downloads=0,large_221MB_file_read=False,
   kernel055_sha_before_and_after=EXPECTED_055,physical_session_verified=False,broker_qualified=False,conditional_reference_only=True,
   source_code_sha256=sha(Path(__file__)),tests_sha256=sha(Path(__file__).with_name('test_stage056_uniform_minute_input_audit.py')),
   demand_sha256=sha(REQDIR/'exact_contract_session_requirements.csv'),state_sha256=sha(REQDIR/'distinct_state_requirements.csv'))
 (target/'summary.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(output=str(target),**stats),ensure_ascii=False),flush=True)

if __name__=='__main__':run()
