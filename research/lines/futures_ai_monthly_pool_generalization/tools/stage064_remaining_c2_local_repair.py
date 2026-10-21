"""Current058 exact-held first-C2 requirements and existing local evidence reuse.
No source/target writes, raw minute payload scan, fee change or model fit.
"""
from collections import defaultdict
from pathlib import Path
import json,multiprocessing as mp,sqlite3,time
import numpy as np
import pandas as pd
import stage052_exact_c2_data_requirements as extractor
import stage058_minute_evidence_adapter as adapter
from stage055_minute_input_qualification import reference_grid
source=extractor.source
LINE=Path(__file__).resolve().parents[1]
OUT=LINE/'outputs/stage064_remaining_c2_local_repair'
CURRENT=LINE/'outputs/stage058_minute_augmented_source'
INV=LINE/'outputs/stage054_existing_minute_reusability'
AUDIT=LINE/'outputs/stage056_uniform_minute_input_audit/run_20261020_222826_843552'

def read(p):return pd.read_csv(p,dtype=str,keep_default_na=False)
def classify(supported,accepted,previous_statuses,files,sqlite_candidate,previous_scope=False):
 if accepted:raise ValueError('accepted_event_cannot_remain_first_C2_unknown')
 if not supported:return 'historical_session_research_required'
 if previous_statuses:return 'previously_audited_rejected'
 if previous_scope and not files and not sqlite_candidate:return 'previous_reference_scope_no_local_native_candidate'
 if files or sqlite_candidate:return 'new_event_local_candidates_not_audited'
 return 'new_event_no_local_native_candidate'

def inventory(demands,variants,calendar):
 files=read(INV/'known_light_file_schemas_and_bounds.csv')
 # Include all 1737 cache files; Stage861 metadata stays separate, unopened.
 files['filename_native_hint']=[Path(p).stem.split('_')[0]+'.'+Path(p).parent.name for p in files.path]
 files['native_candidate_key']=[(a or b).casefold() for a,b in zip(files.native_vt_symbol,files.filename_native_hint)]
 nativefiles={k:f.to_dict('records') for k,f in files.groupby('native_candidate_key')}
 oldreq=set(read(LINE/'outputs/stage052_exact_c2_data_requirements/exact_contract_session_requirements.csv').requirement_id)
 audited=read(AUDIT/'all_source_component_audits.csv');audits={k:g.to_dict('records') for k,g in audited.groupby('requirement_id')}
 previous_scope=set(read(AUDIT/'all132_requirement_results.csv').requirement_id)
 accepted={r['requirement_id'] for r in json.loads((AUDIT/'qualified_inputs_manifest.json').read_text())}
 sq={(r['symbol']+'.'+r['exchange']).casefold():r for r in read(INV/'sqlite_1m_indexed_inventory.csv').to_dict('records')}
 meta={r['order_book_id']:r for r in json.loads((source.CALFILE.parent/'futures_metadata.json').read_text())}
 states={r['requirement_id']:r for r in variants};rows=[];pairs=[];components=[]
 for r in demands:
  rid=r['requirement_id'];state=states[rid];hint=r['metadata_order_book_id_hint'];m=meta.get(hint);native=''
  # Vendor snapshot only; filename and date bounds never confer exact identity.
  if m and m.get('exchange')==r['exchange'] and m.get('underlying_symbol','').upper()==r['product'].upper():native=m['trading_code']+'.'+m['exchange']
  try:grid=reference_grid(state,calendar);supported=True;scope_reason='';grid_count=len(grid)
  except ValueError as e:supported=False;scope_reason=str(e);grid_count=None
  candidates=nativefiles.get(native.casefold(),[]) if native else [];old=audits.get(rid,[]);statuses=sorted({a['status'] for a in old})
  classification=classify(supported,rid in accepted,statuses,len(candidates),native.casefold() in sq,rid in previous_scope)
  row={**r,'was_original052_requirement':rid in oldreq,'previous056_scope':rid in previous_scope,'new_following_C2_event':rid not in oldreq,'vendor_native_hint':native,'reference_helper_supported':supported,'reference_scope_reason':scope_reason,
   'expected_reference_minutes':grid_count,'accepted056_same_event':rid in accepted,'previous056_component_count':len(old),'previous056_statuses_json':json.dumps(statuses),
   'candidate_files':len(candidates),'candidate_sqlite':native.casefold() in sq,'repair_class':classification,'physical_session_verified':False,'candidate_qualification_transferred':False,'full_window_known_guaranteed':False}
  rows.append(row)
  for a in old:components.append(a)
  for f in candidates:
   pairs.append(dict(requirement_id=rid,contract_epoch_id=r['contract_epoch_id'],source_trade_date=r['source_trade_date'],path=f['path'],bytes=f['bytes'],
    prior_first_timestamp=f['prior_first_timestamp'],prior_last_timestamp=f['prior_last_timestamp'],prior_stat_matches=f['prior_stat_matches'],
    previously_scanned_for_this_event=any(a['source_path']==f['path'] for a in old),candidate_only=True,reference_helper_supported=supported))
 return rows,pairs,components

def run(workers=4,output_path=None):
 global OUT
 if output_path is not None:OUT=Path(output_path)
 if OUT.exists():raise ValueError('immutable_output_exists')
 OUT.mkdir(parents=True);started=extractor.now();timer=time.perf_counter()
 bindings=json.loads((CURRENT/'bindings.json').read_text());manifest=AUDIT/'qualified_inputs_manifest.json'
 # Same source code as046b/058 and reviewed accepted minute manifest only.
 basebinding=json.loads((extractor.BASE/'bindings.json').read_text())
 locked={p:extractor.sha(p) for p in [*map(Path,basebinding['source_code_sha256']),Path(__file__),Path(__file__).with_name('test_stage064_remaining_c2_local_repair.py'),Path(extractor.__file__),Path(adapter.__file__),source.PANEL,source.CALFILE,source.ECON,CURRENT/'monthly_coldstart_coverage.csv',CURRENT/'bindings.json',manifest,AUDIT/'all_source_component_audits.csv',INV/'known_light_file_schemas_and_bounds.csv',INV/'sqlite_1m_indexed_inventory.csv',AUDIT/'all132_requirement_results.csv',source.CALFILE.parent/'futures_metadata.json',LINE/'outputs/stage052_exact_c2_data_requirements/exact_contract_session_requirements.csv',extractor.BASE/'bindings.json',LINE/'tools/stage055_minute_input_qualification.py']}
 for p,digest in basebinding['source_code_sha256'].items():
  if extractor.sha(p)!=digest:raise ValueError('base_source_hash_changed:'+p)
 adapter.validate_review_gate(LINE/'outputs/stage057_independent_minute_qualification_review/review.json',extractor.sha(manifest));adapter._INDEX=adapter.MinuteEvidenceIndex(manifest)
 before=source.DB.stat();dbid=dict(path=str(source.DB),bytes=before.st_size,mtime_ns=before.st_mtime_ns,inode=before.st_ino)
 if any(dbid[k]!=basebinding['source_database'][k] for k in ['bytes','mtime_ns','inode']):raise ValueError('RO_database_identity_changed')
 coverage=pd.read_csv(CURRENT/'monthly_coldstart_coverage.csv');selected=coverage.loc[coverage.asof_eligible&coverage.maturity_clock_reached&coverage.first_unknown_reason.eq(extractor.REASON)].sort_values(['exchange','product','eval_date'])
 if len(selected)!=1931:raise ValueError('remaining_C2_window_count_changed')
 selected_rows=json.loads(selected.to_json(orient='records'));extractor._SELECTED=defaultdict(list)
 for r in selected_rows:extractor._SELECTED[(r['exchange'],r['product'])].append(r)
 chosen=np.linspace(0,len(selected_rows)-1,12,dtype=int);extractor._SAMPLE_KEYS={(selected_rows[i]['exchange'],selected_rows[i]['product'],selected_rows[i]['eval_date']) for i in chosen}
 calendar=pd.to_datetime(np.load(source.CALFILE,allow_pickle=False).astype(str),format='%Y%m%d');source._CAL=[str(d.date()) for d in calendar if pd.Timestamp('2010-01-01')<=d<=pd.Timestamp('2026-10-16')]
 with sqlite3.connect(source.PANEL.resolve().as_uri()+'?mode=ro',uri=True) as c:
  c.execute('PRAGMA query_only=ON');panel=pd.read_sql_query('SELECT * FROM panel ORDER BY exchange,product,eval_date',c)
 source._PANELS={k:g.to_dict('records') for k,g in panel.groupby(['exchange','product'],sort=True)}
 with sqlite3.connect(source.DB.resolve().as_uri()+'?mode=ro',uri=True) as c:
  c.execute('PRAGMA query_only=ON');raw=pd.read_sql_query('SELECT exchange,product,contract_epoch_id,trade_date,open,high,low,close,volume,close_oi,source_id FROM daily_bars ORDER BY exchange,product,contract_epoch_id,trade_date',c)
 source._RAW={k:g for k,g in raw.groupby(['exchange','product'],sort=False)};source._ECON={r['contract_epoch_id']:r for r in pd.read_csv(source.ECON).to_dict('records')}
 extractor._META_HINTS={k:{f:r.get(f) for f in ('order_book_id','trading_hours','exchange')} for k,r in source._ECON.items()}
 rows=[];samples=[];previous=source.ProductCases;source.ProductCases=adapter.AugmentedProductCases
 print(json.dumps(dict(phase='loaded',windows=1931,products=len(extractor._SELECTED),elapsed=time.perf_counter()-timer)),flush=True)
 try:
  with mp.get_context('fork').Pool(min(4,max(1,workers))) as pool:
   for result in pool.imap_unordered(extractor.worker,sorted(extractor._SELECTED),chunksize=1):rows.extend(result['rows']);samples.extend(result['samples'])
 finally:source.ProductCases=previous
 rows.sort(key=lambda r:(r['exchange'],r['product'],r['eval_date'],r['path_id']));demands,variants=extractor.aggregate_requirements(rows)
 if {(r['exchange'],r['product'],r['eval_date']) for r in rows}!={(r['exchange'],r['product'],r['eval_date']) for r in selected_rows}:raise ValueError('cohort_mapping_changed')
 if not all(r['extraction_status']=='exact_C2_state_identified' for r in rows):raise ValueError('unidentified_exact_C2_state')
 matched,pairs,components=inventory(demands,variants,calendar)
 for name,data in [('window_path_state_mappings',rows),('exact_contract_session_requirements',demands),('distinct_state_requirements',variants),('local_repairability',matched),('native_cache_candidates',pairs),('inherited056_component_audits',components)]:pd.DataFrame(data).to_csv(OUT/(name+'.csv'),index=False)
 (OUT/'trace_samples').mkdir()
 for item in samples:
  c=item['coverage'];(OUT/'trace_samples'/f"{c['exchange']}_{c['product']}_{c['eval_date']}.json").write_text(json.dumps(item,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 if len(samples)!=12:raise ValueError('fixed_sample_count_changed')
 for p,digest in locked.items():
  if extractor.sha(p)!=digest:raise ValueError('source_changed_during_run:'+str(p))
 after=source.DB.stat()
 if (after.st_size,after.st_mtime_ns,after.st_ino)!=(before.st_size,before.st_mtime_ns,before.st_ino):raise ValueError('database_changed_during_run')
 df=pd.DataFrame(matched);supported=df.reference_helper_supported
 summary=dict(started_at=started,completed_at=extractor.now(),elapsed_seconds=time.perf_counter()-timer,selected_windows=1931,window_path_mappings=len(rows),distinct_exact_events=len(demands),distinct_states=len(variants),products=len(extractor._SELECTED),exact_state_identified_rows=len(rows),held_differs_from_target=sum(r['held_differs_from_asof_target'] is True for r in rows),roll_entry_rows=sum(r['entry_kind']=='roll' for r in rows),
  repair_class_events=df.repair_class.value_counts().to_dict(),repair_class_windows=df.groupby('repair_class').distinct_month_windows.sum().to_dict(),new_following_events=int(df.new_following_C2_event.sum()),new_following_windows=int(df.loc[df.new_following_C2_event,'distinct_month_windows'].sum()),helper_supported_events=int(supported.sum()),helper_supported_windows=int(df.loc[supported,'distinct_month_windows'].sum()),
  previous056_component_status_counts=pd.Series([r['status'] for r in components]).value_counts().to_dict(),candidate_events=int(df.candidate_files.gt(0).sum()),candidate_unique_files=len({r['path'] for r in pairs}),new_payload_files_read=0,raw_minute_payload_bytes_read=0,accepted_snapshot_paths_verified=len(adapter._INDEX.snapshots),labels_changed=0,model_fits=0,downloads=0,production_changes=0,source_database=dbid,source_database_unchanged=True,source_sha256={str(p):d for p,d in locked.items()},output_sha256={str(p.relative_to(OUT)):extractor.sha(p) for p in OUT.rglob('*') if p.is_file()},independent_review='pending',physical_session_verified=False,source_trade_date_not_natural_day=True,full_window_recovery_guaranteed=False)
 (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(json.dumps({k:v for k,v in summary.items() if k not in ('source_sha256','output_sha256')},ensure_ascii=False),flush=True)
 return summary
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--output-path');args=parser.parse_args();run(output_path=args.output_path)
