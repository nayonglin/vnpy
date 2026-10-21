"""Closed35 historical CZCE reference-input audit, never source injection or fit."""
from collections import defaultdict
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,multiprocessing as mp,sqlite3,time
import pandas as pd
import stage056_uniform_minute_input_audit as uniform
LINE=Path(__file__).resolve().parents[1];ROOT=LINE.parents[2]
POLICY=LINE/'outputs/stage069_czce_historical_session_primary'
INV=LINE/'outputs/stage054_existing_minute_reusability'
OUT=LINE/'outputs/stage071_historical_czce_input_audit'
_EXPECTED_POLICY_SHA='baba64af116870c1db41fd6e961bb01014cc9256f0f88eafb2326266d409f4b4'
_RULES={};_FILE_REQUESTS={};_POLICY_SHA=None;_CARDS={}
sha=uniform.sha

def now():return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def declared_grid(rule):
 day=rule['source_trade_date'];segments=json.loads(rule['day_segments_json']);night=json.loads(rule['night_interval_json']);values=[]
 if night:values.extend(pd.date_range(night[0],night[1],freq='min',inclusive='left'))
 for start,end in segments:values.extend(pd.date_range(day+'T'+start,day+'T'+end,freq='min',inclusive='left'))
 result=pd.DatetimeIndex(values)
 if not result.is_monotonic_increasing or result.has_duplicates or len(result)!=rule['expected_reference_minutes']:raise ValueError('declared_reference_minutes_invalid')
 return result

def policy_tier(rule):
 gaps=json.loads(rule['explicit_gaps_json'])
 return 'sensitivity_only_additional_primary_gap' if any(g.startswith('early_day_break225_') or g.startswith('SM_2018_2019_') for g in gaps) else 'document_supported_reference_only'

def outside_grid_diagnostic(frame,rule,expected):
 """Broader than min/max expected; exposes undeclared night and end-labels."""
 start=pd.Timestamp(rule['previous_source_trade_date']+'T21:00:00');end=pd.Timestamp(rule['source_trade_date']+'T15:01:00');day9=pd.Timestamp(rule['source_trade_date']+'T09:00:00')
 times=pd.DatetimeIndex(frame.bar_datetime);envelope=times[(times>=start)&(times<end)];extra=envelope[~envelope.isin(expected)]
 return dict(reference_envelope_start=start.isoformat(),reference_envelope_end_exclusive=end.isoformat(),envelope_observed_rows=len(envelope),unexpected_rows_in_broad_envelope=len(extra),unexpected_overnight_rows=int((extra<day9).sum()),unexpected_day_rows=int((extra>=day9).sum()),
  unexpected_timestamps_json=canonical([x.isoformat() for x in extra]),reject_extra_session_rows=bool(len(extra)))

def audit_frame(frame,record,ids):
 audits,passed=uniform._audit_frame(frame,record,ids);bad=set()
 for a in audits:
  rid=a['requirement_id'];rule=_RULES[rid];a.update(historical_reference_policy_id='stage069_CZCE_exact35_documented_reference_candidate_v1',historical_rule_manifest_sha256=_POLICY_SHA,policy_tier=policy_tier(rule),historical_rule_evidence_ids=rule['evidence_ids'],historical_rule_explicit_gaps_json=rule['explicit_gaps_json'],PIT_qualified=False,approved_for_source_injection=False)
  component=a.get('component');meta=uniform._META.get(uniform._REQUESTS[rid]['metadata_order_book_id_hint'])
  if component is None or not meta or 'vt_symbol' not in frame or 'bar_datetime' not in frame:continue
  selected=frame.loc[frame.vt_symbol.astype(str).str.casefold().eq((meta['trading_code']+'.'+meta['exchange']).casefold())]
  if 'minute_source' in selected:selected=selected.loc[selected.minute_source.eq(component)]
  diagnostic=outside_grid_diagnostic(selected,rule,uniform._GRIDS[rid]);a.update(diagnostic)
  if diagnostic['reject_extra_session_rows']:
   a['baseline055_status']=a['status'];a['status']='undeclared_overnight_rows' if diagnostic['unexpected_overnight_rows'] else 'unexpected_day_or_endpoint_rows';bad.add((rid,a.get('source_id')))
 filtered=[]
 for p in passed:
  rid=p['requirement_id'];b=p['binding'];rule=_RULES[rid]
  if (rid,b['source_id']) in bad:continue
  b.update(historical_reference_policy_id='stage069_CZCE_exact35_documented_reference_candidate_v1',historical_rule_manifest_sha256=_POLICY_SHA,policy_tier=policy_tier(rule),historical_rule_evidence_ids=rule['evidence_ids'],historical_rule_sources=[_CARDS[x] for x in rule['evidence_ids'].split('|')],historical_rule_explicit_gaps_json=rule['explicit_gaps_json'],PIT_qualified=False,approved_for_source_injection=False)
  filtered.append(p)
 return audits,filtered

def worker(path):
 ids=_FILE_REQUESTS[path]
 try:frame,record=uniform._load_csv(path);audits,passed=audit_frame(frame,record,ids)
 except (OSError,ValueError,UnicodeError,pd.errors.ParserError) as e:
  record=dict(path=path,error=type(e).__name__+':'+str(e));audits=[dict(requirement_id=rid,source_path=path,status='source_read_or_parse_error',error=record['error']) for rid in ids];passed=[]
 return dict(source=record,audits=audits,passed=passed)

def run(workers=4):
 global _RULES,_FILE_REQUESTS,_POLICY_SHA,_CARDS
 if OUT.exists() and any(p.name!='PLAN.md' for p in OUT.iterdir()):raise ValueError('immutable_output_exists')
 manifest_path=POLICY/'bounded_reference_candidate_manifest.json';_POLICY_SHA=sha(manifest_path)
 if _POLICY_SHA!=_EXPECTED_POLICY_SHA:raise ValueError('frozen069_policy_changed')
 if sha(LINE/'tools/stage055_minute_input_qualification.py')!=uniform.EXPECTED_055:raise ValueError('frozen055_kernel_changed')
 OUT.mkdir(parents=True,exist_ok=True);started=now();timer=time.perf_counter();manifest=json.loads(manifest_path.read_text());_RULES={r['requirement_id']:r for r in manifest['events']}
 if len(_RULES)!=35:raise ValueError('closed35_scope_changed')
 if sum(policy_tier(r)=='sensitivity_only_additional_primary_gap' for r in _RULES.values())!=11:raise ValueError('frozen24_vs11_tier_changed')
 _CARDS={r['id']:r for r in json.loads((POLICY/'sources.json').read_text())}
 states=uniform.read(POLICY/'exact_scope_events.csv');uniform._REQUESTS={r['requirement_id']:r for r in states.to_dict('records')};uniform._GRIDS={rid:declared_grid(r) for rid,r in _RULES.items()}
 if set(uniform._REQUESTS)!=set(_RULES):raise ValueError('closed_event_identity_mismatch')
 uniform._EPOCHS={r['contract_epoch_id']:r for r in uniform.read(LINE/'outputs/stage006_economic_coverage/epoch_economic_inventory.csv').to_dict('records')}
 meta_path=uniform.PRIOR/'stage265_deep_daily/rqalpha/futures_metadata.json';uniform._META={r['order_book_id']:r for r in json.loads(meta_path.read_text())}
 candidates=uniform.read(INV/'exact_requirement_native_cache_candidates.csv');candidates=candidates.loc[candidates.requirement_id.isin(_RULES)]
 _FILE_REQUESTS={p:sorted(set(g.requirement_id)) for p,g in candidates.groupby('path')}
 if len(_FILE_REQUESTS)!=80:raise ValueError('closed_candidate_file_scope_changed')
 locked_paths=[manifest_path,POLICY/'sources.json',POLICY/'exact_scope_events.csv',INV/'exact_requirement_native_cache_candidates.csv',INV/'sqlite_1m_indexed_inventory.csv',LINE/'outputs/stage006_economic_coverage/epoch_economic_inventory.csv',meta_path,Path(__file__),Path(__file__).with_name('test_stage071_historical_czce_input_audit.py'),Path(uniform.__file__),LINE/'tools/stage055_minute_input_qualification.py']
 locked={str(p):sha(p) for p in locked_paths}
 clean=uniform.PRIOR/'stage266_clean_daily/clean_daily.sqlite';before=clean.stat()
 with sqlite3.connect(clean.resolve().as_uri()+'?mode=ro',uri=True) as c:
  c.execute('PRAGMA query_only=ON')
  for r in uniform._REQUESTS.values():
   bar=c.execute('SELECT open,high,low,close FROM daily_bars WHERE contract_epoch_id=? AND trade_date=?',[r['contract_epoch_id'],r['source_trade_date']]).fetchone()
   if bar is None or any(abs(float(r['source_'+k])-float(v))>1e-8 for k,v in zip(['open','high','low','close'],bar)):raise ValueError('exact_daily_binding_changed')
 print(canonical(dict(phase='closed35_preflight',events=35,files=80,bytes=sum(int(g.iloc[0]['bytes']) for _,g in candidates.groupby('path')),workers=workers)),flush=True)
 results=[]
 with mp.get_context('fork').Pool(min(4,max(1,workers))) as pool:
  for result in pool.imap_unordered(worker,sorted(_FILE_REQUESTS),chunksize=1):results.append(result)
 # Existing indexed native candidates only; no whole minute DB scan/hash.
 overview=uniform.read(INV/'sqlite_1m_indexed_inventory.csv');sqby={(r['symbol']+'.'+r['exchange']).casefold():r for r in overview.to_dict('records')};groups=defaultdict(list)
 for rid,r in uniform._REQUESTS.items():
  m=uniform._META.get(r['metadata_order_book_id_hint'])
  if m:
   key=(m['trading_code']+'.'+m['exchange']).casefold()
   if key in sqby:groups[key].append(rid)
 minute_path=ROOT/'.vntrader/database.db';minute_before=minute_path.stat()
 with sqlite3.connect(minute_path.resolve().as_uri()+'?mode=ro',uri=True) as c:
  c.execute('PRAGMA query_only=ON')
  for key,ids in sorted(groups.items()):
   meta=sqby[key];frame=pd.read_sql_query("SELECT symbol,exchange,datetime AS bar_datetime,open_price AS open,high_price AS high,low_price AS low,close_price AS close FROM dbbardata WHERE symbol=? AND exchange=? AND interval='1m' ORDER BY datetime",c,params=[meta['symbol'],meta['exchange']]);frame['vt_symbol']=frame.symbol+'.'+frame.exchange;frame['bar_datetime']=pd.to_datetime(frame.bar_datetime,format='mixed',errors='coerce');frame=frame.drop(columns=['symbol','exchange'])
   digest=hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest();record=dict(path=str(minute_path)+'#dbbardata:'+key,sqlite_path=str(minute_path),native_key=key,bytes=minute_before.st_size,mtime_ns=minute_before.st_mtime_ns,inode=minute_before.st_ino,sha256=digest,rows=len(frame),hash_scope='indexed_projection_csv_not_entire_db')
   audits,passed=audit_frame(frame,record,ids);results.append(dict(source=record,audits=audits,passed=passed))
 audits=[a for x in results for a in x['audits']];passed=[p for x in results for p in x['passed']];sources=[x['source'] for x in results];audits.sort(key=lambda a:(a['requirement_id'],a.get('source_path',''),a.get('component','')));sources.sort(key=lambda r:r['path'])
 groups={}
 for p in passed:
  rid=p['requirement_id'];digest=hashlib.sha256(canonical(p['minute_path']).encode()).hexdigest();groups.setdefault((rid,digest),[]).append(p)
 (OUT/'qualified_paths').mkdir();qualified=[]
 for (rid,digest),members in sorted(groups.items()):
  paths=[canonical(m['minute_path']) for m in members]
  if len(set(paths))!=1:raise ValueError('canonical_dedup_collision')
  data=OUT/'qualified_paths'/(rid+'_'+digest+'.csv');pd.DataFrame(members[0]['minute_path']).to_csv(data,index=False)
  rule=_RULES[rid];qualified.append(dict(requirement_id=rid,state_id=uniform._REQUESTS[rid]['state_id'],data_path=str(data.resolve()),data_csv_sha256=sha(data),canonical_input_sha256=digest,rows=len(members[0]['minute_path']),source_ids=sorted({m['binding']['source_id'] for m in members}),bindings=[m['binding'] for m in members],policy_tier=policy_tier(rule),historical_rule_manifest_sha256=_POLICY_SHA,historical_rule_evidence_ids=rule['evidence_ids'],historical_rule_explicit_gaps_json=rule['explicit_gaps_json'],reference_policy_grid_only=True,physical_session_verified=False,broker_symbol_qualified=False,PIT_qualified=False,usable_for_trading=False,approved_for_source_injection=False))
 pd.DataFrame(audits).to_csv(OUT/'all_source_component_audits.csv',index=False)
 (OUT/'source_bindings.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
 for name,items in [('all_historical_reference_inputs_manifest',qualified),('documentary_reference_inputs_manifest',[q for q in qualified if q['policy_tier']=='document_supported_reference_only']),('additional_gap_sensitivity_inputs_manifest',[q for q in qualified if q['policy_tier']=='sensitivity_only_additional_primary_gap'])]:(OUT/(name+'.json')).write_text(json.dumps(items,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 rows=[]
 for rid,r in sorted(_RULES.items()):
  a=[x for x in audits if x['requirement_id']==rid];q=[x for x in qualified if x['requirement_id']==rid]
  rows.append(dict(requirement_id=rid,contract_epoch_id=r['contract_epoch_id'],source_trade_date=r['source_trade_date'],distinct_month_windows=r['distinct_month_windows'],policy_tier=policy_tier(r),expected_reference_minutes=r['expected_reference_minutes'],components=len(a),qualified_distinct_paths=len(q),qualified_source_members=sum(len(x['source_ids']) for x in q),component_status_counts_json=canonical(pd.Series([x['status'] for x in a]).value_counts().to_dict()),status='conditional_historical_reference_inputs_available' if q else 'no_qualified_historical_reference_input',physical_session_verified=False,approved_for_source_injection=False))
 pd.DataFrame(rows).to_csv(OUT/'all35_requirement_results.csv',index=False)
 for p,digest in locked.items():
  if sha(p)!=digest:raise ValueError('input_or_code_changed_during_audit:'+p)
 for path,stamp in [(clean,before),(minute_path,minute_before)]:
  after=path.stat()
  if (after.st_size,after.st_mtime_ns,after.st_ino)!=(stamp.st_size,stamp.st_mtime_ns,stamp.st_ino):raise ValueError('RO_database_changed_during_audit')
 summary=dict(started_at=started,completed_at=now(),elapsed_seconds=time.perf_counter()-timer,exact_events=35,month_windows=83,raw_csv_files=80,raw_csv_bytes=sum(r.get('bytes',0) for r in sources if 'sqlite_path' not in r),sqlite_native_projections=len([r for r in sources if 'sqlite_path' in r]),source_components=len(audits),component_status_counts=pd.Series([r['status'] for r in audits]).value_counts().to_dict(),qualified_events=len({q['requirement_id'] for q in qualified}),qualified_distinct_paths=len(qualified),qualified_source_members=sum(len(q['source_ids']) for q in qualified),qualified_paths_by_tier=pd.Series([q['policy_tier'] for q in qualified]).value_counts().to_dict(),events_with_multiple_distinct_paths=sum(sum(q['requirement_id']==rid for q in qualified)>1 for rid in _RULES),additional_gap_scope_events=sum(policy_tier(r)=='sensitivity_only_additional_primary_gap' for r in _RULES.values()),policy_sha256=_POLICY_SHA,kernel055_sha256=uniform.EXPECTED_055,source_sha256=locked,raw_source_snapshots_sha256={r['path']:r.get('sha256') for r in sources},output_sha256={str(p.relative_to(OUT)):sha(p) for p in OUT.rglob('*') if p.is_file()},source_replays=0,source_injections=0,model_fits=0,labels_changed=0,downloads=0,production_changes=0,physical_session_verified=False,approved_for_source_injection=False,independent_review='pending Stage076')
 (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(canonical({k:v for k,v in summary.items() if k not in ('source_sha256','output_sha256','raw_source_snapshots_sha256')}),flush=True)
 return summary
if __name__=='__main__':run()
