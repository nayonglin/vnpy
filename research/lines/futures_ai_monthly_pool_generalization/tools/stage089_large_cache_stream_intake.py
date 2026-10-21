"""One-pass large CSV intake for a frozen exact793 request cohort; no source/fit."""
from collections import defaultdict,Counter
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,io,json,sqlite3,time
import numpy as np
import pandas as pd
import stage056_uniform_minute_input_audit as uniform
from stage055_minute_input_qualification import reference_grid,qualify_component
LINE=Path(__file__).resolve().parents[1];ROOT=LINE.parents[2]
OUT=LINE/'outputs/stage089_large_cache_stream_intake';REQ=LINE/'outputs/stage083_next_exact_minute_intake'
RAW=ROOT/'examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_stage861_stage860_full_visual_atlas_v1.csv'
sha=uniform.sha

def now():return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
class HashingRaw(io.RawIOBase):
 def __init__(self,raw):super().__init__();self.raw=raw;self.hasher=hashlib.sha256();self.bytes_read=0
 def readable(self):return True
 def readinto(self,buffer):
  n=self.raw.readinto(buffer)
  if n:self.hasher.update(memoryview(buffer)[:n]);self.bytes_read+=n
  return n

def local_stamps(values):
 times=pd.to_datetime(values,format='mixed',errors='coerce')
 if isinstance(times.dtype,pd.DatetimeTZDtype):return times.dt.tz_convert('Asia/Shanghai').dt.tz_localize(None)
 if times.dtype==object:
  def safe(v):
   try:return uniform.execution.local_timestamp(v)
   except (ValueError,TypeError):return pd.NaT
  return pd.to_datetime(values.map(safe),errors='coerce')
 return times

def stream_file(path,specs,chunksize=100000):
 if type(chunksize) is not int or not 1<=chunksize<=100000:raise ValueError('bounded_chunksize_required')
 bynative=defaultdict(list)
 for s in specs:bynative[s['native']].append(s)
 matched=defaultdict(list);invalids=[];invalid_counts=Counter();native_counts=Counter();providers=defaultdict(set);rowbase=0;chunks=0
 with Path(path).open('rb') as raw:
  hashed=HashingRaw(raw)
  with io.BufferedReader(hashed) as buffered:
   with pd.read_csv(buffered,chunksize=chunksize,dtype=str,keep_default_na=False,encoding='utf-8-sig',engine='c',on_bad_lines='error') as reader:
    for chunk in reader:
     chunks+=1
     if len(chunk)>chunksize:raise ValueError('parser_chunk_exceeded_bound')
     needed={'vt_symbol','bar_datetime','open','high','low','close','minute_source'}
     if not needed<=set(chunk):raise ValueError('large_cache_schema_missing')
     chunk=chunk.copy();chunk['source_record_index']=np.arange(rowbase+1,rowbase+1+len(chunk));rowbase+=len(chunk)
     lower=chunk.vt_symbol.str.casefold();part=chunk.loc[lower.isin(bynative)].copy();part['_native']=part.vt_symbol.str.casefold()
     if part.empty:continue
     part['local_datetime']=local_stamps(part.bar_datetime);part['_component']=part.minute_source.map(lambda x:x if x else '__unspecified__')
     for (native,component),group in part.groupby(['_native','_component'],sort=False):
      native_counts[(native,component)]+=len(group);providers[native].add(component);bad=group.local_datetime.isna()
      if bad.any():invalids.append(group.loc[bad].copy());invalid_counts[(native,component)]+=int(bad.sum())
      valid=group.loc[~bad]
      for s in bynative[native]:
       start=pd.Timestamp(s['previous']+'T21:00:00');end=pd.Timestamp(s['day']+'T15:01:00');selected=valid.loc[valid.local_datetime.ge(start)&valid.local_datetime.lt(end)].copy()
       if selected.empty:continue
       natural=selected.local_datetime.dt.strftime('%Y-%m-%d');selected['metadata_lifetime_valid']=natural.ge(s['listed'])&natural.le(s['delisted']);selected['explicit_identity_valid']=True
       for col,value in [('contract_epoch_id',s['epoch']),('source_trade_date',s['day'])]:
        if col in selected:selected['explicit_identity_valid']&=selected[col].ne('')&selected[col].eq(value)
       matched[(s['rid'],component)].append(selected)
   # Drain only any unread trailing bytes, preserving one sequential payload pass.
   while buffered.read(1024*1024):pass
  digest=hashed.hasher.hexdigest();bytecount=hashed.bytes_read
 return dict(matched={k:pd.concat(v,ignore_index=True) for k,v in matched.items()},invalid_timestamp_rows=pd.concat(invalids,ignore_index=True) if invalids else pd.DataFrame(),invalid_counts=dict(invalid_counts),native_counts=dict(native_counts),providers={k:sorted(v) for k,v in providers.items()},io=dict(payload_sha256=digest,bytes_read=bytecount,records=rowbase,chunks=chunks,chunksize=chunksize,full_payload_read_passes=1,sha_computed_in_csv_payload_read=True))

def qualify_snapshot(snapshot,expected,request,binding,invalid_native_timestamps):
 if invalid_native_timestamps:return dict(status='native_component_invalid_timestamp_unassignable',minute_path=None)
 if not snapshot.metadata_lifetime_valid.all():return dict(status='target_rows_outside_metadata_lifetime',minute_path=None)
 if not snapshot.explicit_identity_valid.all():return dict(status='explicit_row_identity_mismatch',minute_path=None)
 frame=snapshot.copy();frame['bar_datetime']=frame.local_datetime
 # Preserve payload provider identity; normalize only the stream's empty marker.
 frame['minute_source']=frame.minute_source.fillna('').replace('', '__unspecified__')
 return qualify_component(frame,expected,request,binding)

def prepare():
 states=uniform.read(REQ/'exact793_state_price_bindings.csv');requirements=uniform.read(REQ/'exact793_contract_session_requirements.csv')
 if len(states)!=793 or states.requirement_id.nunique()!=793 or set(states.requirement_id)!=set(requirements.requirement_id):raise ValueError('frozen793_scope_changed')
 econ_path=LINE/'outputs/stage006_economic_coverage/epoch_economic_inventory.csv';meta_path=uniform.PRIOR/'stage265_deep_daily/rqalpha/futures_metadata.json';cal_path=meta_path.parent/'trading_dates.npy'
 epochs={r['contract_epoch_id']:r for r in uniform.read(econ_path).to_dict('records')};metadata={r['order_book_id']:r for r in json.loads(meta_path.read_text())};calendar=pd.to_datetime(np.load(cal_path,allow_pickle=False).astype(str),format='%Y%m%d');caldays=[x.strftime('%Y-%m-%d') for x in calendar]
 requests={r['requirement_id']:r for r in states.to_dict('records')};specs=[];scopes=[];grids={}
 for rid,r in requests.items():
  epoch=epochs[r['contract_epoch_id']];meta=metadata.get(r['metadata_order_book_id_hint']);day=r['source_trade_date'];previous=caldays[caldays.index(day)-1];identity_error=''
  if not meta:identity_error='metadata_missing';native=''
  else:
   native=(meta['trading_code']+'.'+meta['exchange']).casefold()
   try:uniform.make_identity_binding(r,epoch,meta,'preflight','__scope_only__',[meta['trading_code']+'.'+meta['exchange']])
   except ValueError as e:identity_error=str(e)
  try:expected=reference_grid(r,calendar);supported=True;reason='';grids[rid]=expected
  except ValueError as e:supported=False;reason=str(e)
  if not identity_error:specs.append(dict(rid=rid,native=native,day=day,previous=previous,listed=meta['listed_date'],delisted=meta['de_listed_date'],epoch=r['contract_epoch_id']))
  scopes.append({**r,'previous_source_trade_date':previous,'vendor_native_exact_key':native,'metadata_identity_error':identity_error,'current055_supported':supported,'reference_policy_reason':reason})
 if len(grids)!=15:raise ValueError('current055_supported_count_changed')
 return requests,specs,scopes,grids,epochs,metadata,calendar,[econ_path,meta_path,cal_path]

def run(prepare_only=False):
 if (OUT/'summary.json').exists():raise ValueError('immutable_output_exists')
 OUT.mkdir(parents=True,exist_ok=True);started=now();timer=time.perf_counter();requests,specs,scopes,grids,epochs,metadata,calendar,data_inputs=prepare()
 stat=RAW.stat()
 if stat.st_size!=221112973:raise ValueError('frozen_large_cache_size_changed')
 existing_plan=json.loads((OUT/'PLAN.json').read_text()) if (OUT/'PLAN.json').exists() else None
 if existing_plan:header=bytes.fromhex(existing_plan['raw_identity']['header_hex'])
 else:
  with RAW.open('rb') as f:header=f.readline()
 (OUT/'original_header.bin').write_bytes(header);pd.DataFrame(scopes).to_csv(OUT/'frozen793_scope.csv',index=False)
 code_inputs=[Path(__file__),Path(__file__).with_name('test_stage089_large_cache_stream_intake.py'),Path(uniform.__file__),LINE/'tools/stage055_minute_input_qualification.py',ROOT/'examples/portfolio_backtesting/qmt_roll_intraday_execution.py']
 protected=[LINE/'outputs/stage073_reviewed_evidence_union/qualified_inputs_manifest.json',LINE/'outputs/stage073_union_augmented_source/monthly_coldstart_coverage.csv',LINE/'outputs/stage075_targets_followup_augmented/monthly_target_identification.csv']
 locked={str(p):sha(p) for p in [*code_inputs,*data_inputs,*protected,REQ/'exact793_state_price_bindings.csv',REQ/'exact793_contract_session_requirements.csv',REQ/'remaining1926_window_mappings.csv']}
 if sha(LINE/'tools/stage055_minute_input_qualification.py')!=uniform.EXPECTED_055:raise ValueError('frozen055_kernel_changed')
 raw_identity=dict(path=str(RAW),bytes=stat.st_size,mtime_ns=stat.st_mtime_ns,inode=stat.st_ino,header_hex=header.hex(),header_only_pre_read_bytes=len(header))
 plan=dict(started_at=started,scope_events=793,current055_supported=15,historical_policy_pending=778,scope_sha256=sha(OUT/'frozen793_scope.csv'),code_and_inputs_sha256=locked,raw_identity=raw_identity,
   io_policy='one sequential full payload pass through hashing RawIOBase and pandas C read_csv chunks<=100000; separate header-only pre-read reported; no 793 per-case rescans',selection='all exact793 vendor-native metadata-lifetime requests in broad prev common source natural21 to D15:01, providers independent; keep duplicates/invalid/extra; no R/outcome case choice',qualification='current05515 only; all778 pending policy regardless of rows; no provider stitching, no endpoint rounding, no source injection or labels',public_references=['https://pandas.pydata.org/docs/user_guide/io.html','https://github.com/pandas-dev/pandas/blob/main/doc/source/user_guide/io.rst'],new_network_downloads=0,model_fits=0)
 if existing_plan:
  for key in ['scope_events','current055_supported','historical_policy_pending','scope_sha256','code_and_inputs_sha256','raw_identity']:
   if plan[key]!=existing_plan[key]:raise ValueError('frozen_preflight_plan_changed:'+key)
  plan=existing_plan
 else:(OUT/'PLAN.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
 print(canonical(dict(phase='frozen_before_payload_read',scope793=793,current055=15,raw_bytes=stat.st_size,scope_sha256=plan['scope_sha256'],code_sha256=locked[str(Path(__file__))])),flush=True)
 if prepare_only:return plan
 # This is the only full large-file read in the producer.
 result=stream_file(RAW,specs,chunksize=100000);after=RAW.stat()
 if result['io']['bytes_read']!=stat.st_size or (after.st_size,after.st_mtime_ns,after.st_ino)!=(stat.st_size,stat.st_mtime_ns,stat.st_ino):raise ValueError('large_payload_bytecount_or_identity_changed')
 rawsha=result['io']['payload_sha256'];scope_by={s['requirement_id']:s for s in scopes};spec_by={s['rid']:s for s in specs};audits=[];qualified=[];snapshots=[];coverage=[]
 (OUT/'matched_snapshots').mkdir();(OUT/'qualified_paths').mkdir()
 invalid=result['invalid_timestamp_rows']
 if not invalid.empty:invalid.to_csv(OUT/'native_invalid_timestamp_rows_unassigned.csv',index=False)
 for rid,r in sorted(requests.items()):
  scope=scope_by[rid];native=scope['vendor_native_exact_key'];components=result['providers'].get(native,[]);totalrows=0;validlife=0;snapshotcount=0;passcount=0
  for component in components:
   part=result['matched'].get((rid,component));sid=hashlib.sha256((str(RAW)+'\n'+rawsha+'\n'+component).encode()).hexdigest();base=dict(requirement_id=rid,state_id=r['state_id'],contract_epoch_id=r['contract_epoch_id'],source_trade_date=r['source_trade_date'],component=component,source_id=sid,source_path=str(RAW),source_payload_sha256=rawsha,current055_supported=scope['current055_supported'],physical_session_verified=False,PIT_qualified=False,usable_for_trading=False,approved_for_source_injection=False)
   invalid_count=result['invalid_counts'].get((native,component),0);base['native_invalid_timestamp_unassignable_rows']=invalid_count;base['native_provider_total_rows']=result['native_counts'].get((native,component),0)
   if part is None:
    audits.append({**base,'status':'no_rows_in_broad_reference_envelope','matched_rows':0});continue
   totalrows+=len(part);validlife+=int((part.metadata_lifetime_valid&part.explicit_identity_valid).sum());snapshotcount+=1
   snap=OUT/'matched_snapshots'/(rid+'_'+hashlib.sha256(component.encode()).hexdigest()[:16]+'.csv');part.to_csv(snap,index=False);snapsha=sha(snap);snapshots.append(dict(requirement_id=rid,component=component,path=str(snap.resolve()),sha256=snapsha,rows=len(part),source_id=sid,raw_source_sha256=rawsha));base.update(matched_snapshot_path=str(snap.resolve()),matched_snapshot_sha256=snapsha,matched_rows=len(part),duplicate_local_timestamps=int(part.local_datetime.duplicated().sum()),metadata_lifetime_invalid_rows=int((~part.metadata_lifetime_valid).sum()),explicit_identity_invalid_rows=int((~part.explicit_identity_valid).sum()),first_local_timestamp=part.local_datetime.min().isoformat(),last_local_timestamp=part.local_datetime.max().isoformat())
   if not scope['current055_supported']:
    audits.append({**base,'status':'rows_observed_pending_historical_policy','reference_policy_reason':scope['reference_policy_reason']});continue
   meta=metadata[r['metadata_order_book_id_hint']]
   try:binding=uniform.make_identity_binding(r,epochs[r['contract_epoch_id']],meta,sid,component,list(part.vt_symbol.unique()))
   except ValueError as e:audits.append({**base,'status':'exact_metadata_identity_reject','identity_error':str(e)});continue
   expected=grids[rid];binding.update(source_path=str(RAW),source_payload_sha256=rawsha,source_hash_scope='entire_large_csv_sha256_same_sequential_read_as_stream_filter',matched_snapshot_path=str(snap.resolve()),matched_snapshot_sha256=snapsha,expected_grid_sha256=hashlib.sha256('\n'.join(t.isoformat() for t in expected).encode()).hexdigest(),kernel055_sha256=uniform.EXPECTED_055,expected_minutes=len(expected),reference_session_start=expected[0].isoformat(),reference_session_last=expected[-1].isoformat(),source_daily_OHLC={k:float(r['source_'+k]) for k in ['open','high','low','close']},entry_open=float(r['entry_price']),PIT_qualified=False,approved_for_source_injection=False)
   outcome=qualify_snapshot(part,expected,r,binding,invalid_count);audits.append({**base,'binding_json':canonical(binding),**{k:v for k,v in outcome.items() if k!='minute_path'}})
   if outcome['status']=='conditional_reference_input_qualified':
    path=outcome['minute_path'];digest=hashlib.sha256(canonical(path).encode()).hexdigest();data=OUT/'qualified_paths'/(rid+'_'+digest+'.csv');pd.DataFrame(path).to_csv(data,index=False);passcount+=1
    qualified.append(dict(requirement_id=rid,state_id=r['state_id'],data_path=str(data.resolve()),data_csv_sha256=sha(data),canonical_input_sha256=digest,rows=len(path),source_ids=[sid],bindings=[binding],reference_policy_grid_only=True,physical_session_verified=False,broker_symbol_qualified=False,PIT_qualified=False,usable_for_trading=False,approved_for_source_injection=False))
  coverage.append(dict(requirement_id=rid,state_id=r['state_id'],contract_epoch_id=r['contract_epoch_id'],source_trade_date=r['source_trade_date'],vendor_native_exact_key=native,metadata_identity_error=scope['metadata_identity_error'],current055_supported=scope['current055_supported'],reference_policy_reason=scope['reference_policy_reason'],observed_native_providers=len(components),matched_provider_snapshots=snapshotcount,broad_matched_rows=totalrows,exact_lifetime_identity_rows=validlife,qualified_distinct_provider_paths=passcount,physical_session_verified=False,PIT_qualified=False,source_injection_allowed=False))
 # Same exact canonical input may be deduplicated, retaining all provider bindings.
 dedup={}
 for q in qualified:
  key=(q['requirement_id'],q['canonical_input_sha256'])
  if key not in dedup:dedup[key]=q
  else:dedup[key]['source_ids']=sorted(set(dedup[key]['source_ids']+q['source_ids']));dedup[key]['bindings'].extend(q['bindings'])
 manifest=list(dedup.values());pd.DataFrame(coverage).to_csv(OUT/'all793_coverage.csv',index=False);pd.DataFrame(audits).to_csv(OUT/'all_provider_component_audits.csv',index=False);(OUT/'matched_snapshot_bindings.json').write_text(json.dumps(snapshots,ensure_ascii=False,indent=2)+'\n');(OUT/'qualified_reference_inputs_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 for p,digest in locked.items():
  if sha(p)!=digest:raise ValueError('frozen_input_code_or_old_source_changed:'+p)
 after=RAW.stat()
 if (after.st_size,after.st_mtime_ns,after.st_ino)!=(stat.st_size,stat.st_mtime_ns,stat.st_ino):raise ValueError('large_source_stat_changed_after_intake')
 cov=pd.DataFrame(coverage);summary=dict(started_at=started,completed_at=now(),elapsed_seconds=time.perf_counter()-timer,scope_events=793,current055_supported=15,historical_policy_pending=778,events_with_broad_rows=int(cov.broad_matched_rows.gt(0).sum()),supported15_with_broad_rows=int((cov.current055_supported&cov.broad_matched_rows.gt(0)).sum()),pending778_with_broad_rows=int((~cov.current055_supported&cov.broad_matched_rows.gt(0)).sum()),matched_snapshots=len(snapshots),matched_rows=int(cov.broad_matched_rows.sum()),native_unassigned_invalid_timestamp_rows=len(invalid),qualified_events=len({q['requirement_id'] for q in manifest}),qualified_distinct_paths=len(manifest),qualified_source_members=sum(len(q['source_ids']) for q in manifest),component_status_counts=pd.Series([a['status'] for a in audits]).value_counts().to_dict(),io=result['io'],header_only_pre_read_bytes=len(header),raw_identity=raw_identity,raw_stat_unchanged=True,protected119_4767_1374_sha256={str(p):locked[str(p)] for p in protected},old_source_label_manifest_unchanged=True,code_and_inputs_sha256=locked,scope_sha256=plan['scope_sha256'],plan_sha256=sha(OUT/'PLAN.json'),output_sha256={str(p.relative_to(OUT)):sha(p) for p in OUT.rglob('*') if p.is_file()},source_replays=0,source_injections=0,labels_changed=0,model_fits=0,network_downloads=0,production_changes=0,physical_session_verified=False,PIT_qualified=False,independent_review='pending Stage091')
 (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(canonical({k:v for k,v in summary.items() if k not in ('code_and_inputs_sha256','output_sha256','protected119_4767_1374_sha256')}),flush=True);return summary
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args();run(prepare_only=args.prepare_only)
