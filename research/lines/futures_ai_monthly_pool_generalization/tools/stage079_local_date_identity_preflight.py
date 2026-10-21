"""Closed27 date/identity preflight only: no grid, strategy, label or fit."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,hashlib,math,sqlite3,time
import numpy as np
import pandas as pd
import stage056_uniform_minute_input_audit as loader
LINE=Path(__file__).resolve().parents[1];ROOT=LINE.parents[2]
OUT=LINE/'outputs/stage079_local_date_identity_preflight';INV=LINE/'outputs/stage054_existing_minute_reusability';REQ=LINE/'outputs/stage052_exact_c2_data_requirements';AUDIT=LINE/'outputs/stage056_uniform_minute_input_audit/run_20261020_222826_843552';SHFE=LINE/'outputs/stage066_shfe_historical_session_evidence';DCE=LINE/'outputs/stage070_dce_historical_session_evidence'
sha=loader.sha

def now():return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def slice_metrics(frame,start,end,target):
 part=frame.loc[frame.bar_datetime.ge(start)&frame.bar_datetime.lt(end)].sort_values('bar_datetime');n=len(part)
 result=dict(rows=n,first_timestamp=None if not n else part.bar_datetime.iloc[0].isoformat(),last_timestamp=None if not n else part.bar_datetime.iloc[-1].isoformat(),duplicate_timestamps=int(part.bar_datetime.duplicated().sum()),invalid_ohlc_rows=0,aggregate_ohlc=None,target_daily_ohlc_match=None)
 if not n:return result
 try:
  prices=part[['open','high','low','close']].astype(float);invalid=(~np.isfinite(prices.to_numpy())).any(axis=1)|(prices.to_numpy()<=0).any(axis=1)|prices.low.gt(prices[['open','close']].min(axis=1)).to_numpy()|prices.high.lt(prices[['open','close']].max(axis=1)).to_numpy()
 except (ValueError,TypeError):result['invalid_ohlc_rows']=n;return result
 result['invalid_ohlc_rows']=int(invalid.sum())
 if invalid.any():return result
 agg=dict(open=float(prices.open.iloc[0]),high=float(prices.high.max()),low=float(prices.low.min()),close=float(prices.close.iloc[-1]));result['aggregate_ohlc']=agg;result['target_daily_ohlc_match']=all(math.isclose(agg[k],float(target[k]),rel_tol=0,abs_tol=1e-8) for k in agg)
 return result

def window_metrics(frame,day,previous,target):
 return dict(broad=slice_metrics(frame,pd.Timestamp(previous+'T21:00:00'),pd.Timestamp(day+'T15:01:00'),target),day=slice_metrics(frame,pd.Timestamp(day+'T09:00:00'),pd.Timestamp(day+'T15:00:00'),target))

def prepare():
 states=loader.read(REQ/'distinct_state_requirements.csv');unsupported=loader.read(AUDIT/'unsupported_requirements.csv');pairs=loader.read(INV/'exact_requirement_native_cache_candidates.csv')
 selected=states.loc[states.requirement_id.isin(unsupported.requirement_id)&states.requirement_id.isin(pairs.requirement_id)&states.exchange.isin(['SHFE','DCE'])].sort_values(['exchange','product','source_trade_date']);pairs=pairs.loc[pairs.requirement_id.isin(selected.requirement_id)].sort_values(['path','requirement_id'])
 docs=set(loader.read(SHFE/'eleven_candidate_events.csv').loc[lambda x:x.evidence_status.eq('bounded_reference_candidate_only'),'requirement_id'])|set(loader.read(DCE/'exact16_evidence_matrix.csv').loc[lambda x:x.conditional_reference_support.eq('bounded_candidate_supported_no_inputaudit_yet'),'requirement_id'])
 selected=selected.copy();selected['documentary_stratum_hint']=selected.requirement_id.map(lambda x:'doc_candidate_only' if x in docs else 'gap_sensitivity_only')
 assert len(selected)==27 and len(pairs)==35 and pairs.path.nunique()==27 and sum(int(g.iloc[0]['bytes']) for _,g in pairs.groupby('path'))==15948783
 assert selected.documentary_stratum_hint.eq('doc_candidate_only').sum()==7
 return selected,pairs

def run():
 if (OUT/'summary.json').exists():raise ValueError('immutable_output_exists')
 OUT.mkdir(parents=True,exist_ok=True);started=now();timer=time.perf_counter();selected,pairs=prepare()
 selected.to_csv(OUT/'frozen27_scope.csv',index=False);pairs.to_csv(OUT/'frozen35_candidate_links.csv',index=False)
 meta_path=loader.PRIOR/'stage265_deep_daily/rqalpha/futures_metadata.json';cal_path=meta_path.parent/'trading_dates.npy';econ_path=LINE/'outputs/stage006_economic_coverage/epoch_economic_inventory.csv'
 inputs=[Path(__file__),Path(__file__).with_name('test_stage079_local_date_identity_preflight.py'),Path(loader.__file__),REQ/'distinct_state_requirements.csv',AUDIT/'unsupported_requirements.csv',INV/'exact_requirement_native_cache_candidates.csv',SHFE/'eleven_candidate_events.csv',DCE/'exact16_evidence_matrix.csv',econ_path,meta_path,cal_path]
 locked={str(p):sha(p) for p in inputs};scope_sha=sha(OUT/'frozen27_scope.csv');links_sha=sha(OUT/'frozen35_candidate_links.csv')
 plan='# Stage079 结果前冻结日期/identity预检\n\n'+started+'；封闭27events、27CSV、35links、15,948,783bytes。doc7/gap20只是066/070预先分层hint，不输入grid规则、不授source/session资格。每file仅一次056loader，精确vendor native及metadata lifetime，provider独立保留；报前共同source自然21:00至D15:01、D09:00至D15:00半开行数/firstlast/aggregate/targetOHLC比较，空窗口不是OHLC冲突。显式epoch/day字段矛盾和目标行lifetime越界单列reject，全file跨年代仅flag。所有raw SHA/stat、全部35links及零行provider保留；0grid资格/C2/source/labels/fit/production。独审081。\n\n代码/输入SHA：\n```json\n'+json.dumps(dict(source_sha256=locked,scope_sha256=scope_sha,candidate_links_sha256=links_sha),ensure_ascii=False,indent=2)+'\n```\n'
 (OUT/'PLAN.md').write_text(plan)
 # No payload read occurs before the written frozen plan above.
 metas={r['order_book_id']:r for r in json.loads(meta_path.read_text())};epochs={r['contract_epoch_id']:r for r in loader.read(econ_path).to_dict('records')};calendar=[pd.Timestamp(str(x)).strftime('%Y-%m-%d') for x in np.load(cal_path,allow_pickle=False).astype(str)];requests={r['requirement_id']:r for r in selected.to_dict('records')};rows=[];sources=[]
 clean=loader.PRIOR/'stage266_clean_daily/clean_daily.sqlite';dbbefore=clean.stat();targets={}
 with sqlite3.connect(clean.resolve().as_uri()+'?mode=ro',uri=True) as c:
  c.execute('PRAGMA query_only=ON')
  for rid,r in requests.items():
   v=c.execute('SELECT open,high,low,close FROM daily_bars WHERE contract_epoch_id=? AND trade_date=?',[r['contract_epoch_id'],r['source_trade_date']]).fetchone()
   if v is None:raise ValueError('exact_target_daily_missing')
   targets[rid]={k:float(z) for k,z in zip(['open','high','low','close'],v)}
   if any(abs(targets[rid][k]-float(r['source_'+k]))>1e-8 for k in targets[rid]):raise ValueError('052_exact_daily_changed')
 for path,link in pairs.groupby('path',sort=True):
  try:frame,record=loader._load_csv(path);sources.append(record)
  except (OSError,ValueError,UnicodeError,pd.errors.ParserError) as e:
   sources.append(dict(path=path,error=type(e).__name__+':'+str(e)))
   for rid in link.requirement_id:rows.append(dict(requirement_id=rid,source_path=path,status='source_read_or_parse_error',error=str(e)))
   continue
  for rid in link.requirement_id:
   r=requests[rid];epoch=epochs[r['contract_epoch_id']];meta=metas.get(r['metadata_order_book_id_hint']);day=r['source_trade_date'];previous=calendar[calendar.index(day)-1];native='' if not meta else meta['trading_code']+'.'+meta['exchange']
   base=dict(requirement_id=rid,contract_epoch_id=r['contract_epoch_id'],source_trade_date=day,previous_source_trade_date=previous,documentary_stratum_hint=r['documentary_stratum_hint'],source_path=path,source_payload_sha256=record['sha256'],vendor_native_hint=native,target_daily_ohlc_json=canonical(targets[rid]),source_trade_date_is_natural_day=False,complete_session_qualified=False,reference_input_qualified=False,physical_session_verified=False,broker_symbol_qualified=False,source_injection_allowed=False)
   if 'vt_symbol' not in frame or 'bar_datetime' not in frame or not meta:
    rows.append({**base,'status':'native_timestamp_or_metadata_missing'});continue
   native_frame=frame.loc[frame.vt_symbol.astype(str).str.casefold().eq(native.casefold())]
   if native_frame.empty:rows.append({**base,'status':'payload_native_contract_not_observed','native_payload_rows':0});continue
   components=list(native_frame.minute_source.drop_duplicates()) if 'minute_source' in native_frame else ['__file_provider_unspecified__']
   for component in components:
    part=native_frame.loc[native_frame.minute_source.eq(component)].copy() if 'minute_source' in native_frame else native_frame.copy();sid=hashlib.sha256((path+'\n'+record['sha256']+'\n'+component).encode()).hexdigest();row={**base,'source_id':sid,'component':component,'native_payload_rows':len(part)}
    try:binding=loader.make_identity_binding(r,epoch,meta,sid,component,list(part.vt_symbol.unique()));row['metadata_request_identity_consistent']=True;row['binding_json']=canonical(binding)
    except ValueError as e:rows.append({**row,'status':'exact_metadata_identity_reject','identity_error':str(e)});continue
    if part.bar_datetime.isna().any():rows.append({**row,'status':'invalid_payload_timestamp'});continue
    stamps=part.bar_datetime;natural=stamps.dt.strftime('%Y-%m-%d');row['whole_native_payload_rows_outside_metadata_lifetime']=int((natural.lt(meta['listed_date'])|natural.gt(meta['de_listed_date'])).sum())
    broad=part.loc[stamps.ge(pd.Timestamp(previous+'T21:00'))&stamps.lt(pd.Timestamp(day+'T15:01'))];target_natural=broad.bar_datetime.dt.strftime('%Y-%m-%d');outside_life=int((target_natural.lt(meta['listed_date'])|target_natural.gt(meta['de_listed_date'])).sum());row['broad_rows_outside_metadata_lifetime']=outside_life
    mismatches=[]
    for col,value in [('contract_epoch_id',r['contract_epoch_id']),('source_trade_date',day)]:
     if col in broad and len(broad) and (broad[col].isna().any() or not broad[col].astype(str).eq(value).all()):mismatches.append(col)
    metrics=window_metrics(part,day,previous,targets[rid]);row['explicit_target_identity_mismatch_fields_json']=canonical(mismatches)
    for name,metric in metrics.items():
     for key,value in metric.items():row[name+'_'+key+('_json' if key=='aggregate_ohlc' else '')]=canonical(value) if key=='aggregate_ohlc' else value
    row['status']='explicit_target_row_identity_reject' if mismatches else 'target_rows_outside_metadata_lifetime_reject' if outside_life else 'no_target_broad_envelope_rows' if metrics['broad']['rows']==0 else 'target_rows_observed_identity_consistent_not_session_qualified'
    rows.append(row)
 rows.sort(key=lambda r:(r['requirement_id'],r['source_path'],r.get('component','')));pd.DataFrame(rows).to_csv(OUT/'all_provider_window_preflight.csv',index=False);(OUT/'source_bindings.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
 events=[]
 for rid,r in sorted(requests.items()):
  group=[x for x in rows if x['requirement_id']==rid];valid=[x for x in group if x['status']=='target_rows_observed_identity_consistent_not_session_qualified'];events.append(dict(requirement_id=rid,contract_epoch_id=r['contract_epoch_id'],source_trade_date=r['source_trade_date'],documentary_stratum_hint=r['documentary_stratum_hint'],components=len(group),providers_with_any_broad_rows=sum(x.get('broad_rows',0)>0 for x in group),identity_consistent_target_row_providers=len(valid),providers_matching_daily_ohlc=sum(x.get('broad_target_daily_ohlc_match') is True for x in valid),max_broad_rows=max([x.get('broad_rows',0) for x in valid] or [0]),max_day_rows=max([x.get('day_rows',0) for x in valid] or [0]),candidate_data_observed_not_qualified=bool(valid),complete_session_qualified=False,reference_input_qualified=False))
 pd.DataFrame(events).to_csv(OUT/'all27_event_preflight.csv',index=False)
 for p,digest in locked.items():
  if sha(p)!=digest:raise ValueError('locked_source_or_input_changed:'+p)
 for record in sources:
  if 'sha256' not in record:continue
  stat=Path(record['path']).stat()
  if (stat.st_size,stat.st_mtime_ns,stat.st_ino)!=(record['bytes'],record['mtime_ns'],record['inode']):raise ValueError('payload_stat_changed_after_read')
 dbafter=clean.stat()
 if (dbafter.st_size,dbafter.st_mtime_ns,dbafter.st_ino)!=(dbbefore.st_size,dbbefore.st_mtime_ns,dbbefore.st_ino):raise ValueError('RO_daily_db_changed')
 result=pd.DataFrame(events);has=result.candidate_data_observed_not_qualified
 summary=dict(started_at=started,completed_at=now(),elapsed_seconds=time.perf_counter()-timer,events=27,raw_files=27,raw_bytes=15948783,links=35,provider_rows=len(rows),status_counts=pd.Series([x['status'] for x in rows]).value_counts().to_dict(),documentary_events=7,gap_events=20,identity_consistent_events_with_target_rows=int(has.sum()),doc_with_target_rows=int((has&result.documentary_stratum_hint.eq('doc_candidate_only')).sum()),gap_with_target_rows=int((has&result.documentary_stratum_hint.eq('gap_sensitivity_only')).sum()),events_with_matching_daily_ohlc=int(result.providers_matching_daily_ohlc.gt(0).sum()),source_sha256=locked,scope_sha256=scope_sha,candidate_links_sha256=links_sha,plan_sha256=sha(OUT/'PLAN.md'),all_raw_stat_unchanged=True,daily_database_stat_unchanged=True,raw_source_sha256={x['path']:x.get('sha256') for x in sources},output_sha256={p.name:sha(p) for p in OUT.iterdir() if p.is_file()},grid_qualifications=0,C2_calculations=0,source_replays=0,source_injections=0,labels_changed=0,model_fits=0,physical_session_verified=False,production_changes=0,independent_review='pending Stage081')
 (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(canonical({k:v for k,v in summary.items() if k not in ('source_sha256','raw_source_sha256','output_sha256')}),flush=True);return summary
if __name__=='__main__':run()
