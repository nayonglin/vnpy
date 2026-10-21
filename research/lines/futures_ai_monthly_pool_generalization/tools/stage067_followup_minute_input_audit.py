"""Audit all six known followup CSV candidates and exact native SQLite source.

No C2 outcome, source/financial replay, labels, model or production mutation.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,sqlite3,math
import numpy as np
import pandas as pd
import stage056_uniform_minute_input_audit as audit
from stage055_minute_input_qualification import reference_grid

LINE=Path(__file__).resolve().parents[1];ROOT=LINE.parents[2]
OUT=LINE/'outputs/stage067_followup_minute_input_audit'
PREVIOUS=LINE/'outputs/stage056_uniform_minute_input_audit/run_20261020_222826_843552'
INPUT=LINE/'outputs/stage064_remaining_c2_local_repair/final_classification'
EXPECTED_IDS={'bd575e9df83be4d5f9b5','47567c214e213d326ad6'}


def verify_inherited_binding(current,previous,listed):
 if current['path']!=previous['path'] or current['path']!=listed['path']:raise ValueError('candidate_path_identity_changed')
 if current['sha256']!=previous['sha256'] or current['sha256']!=listed['inherited056_payload_sha256']:raise ValueError('candidate_raw_sha_changed_from_056_or_064')
 for key,other in [('bytes','current_bytes'),('mtime_ns','current_mtime_ns'),('inode','current_inode')]:
  if int(current[key])!=int(previous[key]) or int(current[key])!=int(listed[other]):raise ValueError('candidate_stat_changed:'+key)
 return True


def run():
 if (OUT/'summary.json').exists():raise ValueError('immutable_followup_output_exists')
 started=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
 paths=[LINE/'tools/stage055_minute_input_qualification.py',LINE/'tools/stage056_uniform_minute_input_audit.py',PREVIOUS/'qualified_inputs_manifest.json',PREVIOUS/'source_bindings.json',INPUT/'distinct_state_requirements.csv',INPUT/'new_event_candidate_file_bindings.csv',LINE/'tools/stage058_minute_evidence_adapter.py']
 before={str(p):audit.sha(p) for p in paths}
 if audit.sha(paths[0])!=audit.EXPECTED_055:raise ValueError('frozen_055_changed')
 states=audit.read(INPUT/'distinct_state_requirements.csv');states=states.loc[states.requirement_id.isin(EXPECTED_IDS)]
 candidates=audit.read(INPUT/'new_event_candidate_file_bindings.csv')
 if len(states)!=2 or set(states.requirement_id)!=EXPECTED_IDS or len(candidates)!=6 or set(candidates.requirement_id)!=EXPECTED_IDS:raise ValueError('two_event_six_file_scope_changed')
 audit._REQUESTS={r['requirement_id']:r for r in states.to_dict('records')}
 dates=pd.to_datetime(np.load(audit.PRIOR/'stage265_deep_daily/rqalpha/trading_dates.npy',allow_pickle=False).astype(str),format='%Y%m%d')
 audit._GRIDS={rid:reference_grid(req,dates) for rid,req in audit._REQUESTS.items()}
 audit._EPOCHS={r['contract_epoch_id']:r for r in audit.read(LINE/'outputs/stage006_economic_coverage/epoch_economic_inventory.csv').to_dict('records')}
 audit._META={r['order_book_id']:r for r in json.loads((audit.PRIOR/'stage265_deep_daily/rqalpha/futures_metadata.json').read_text())}
 audit._CACHE={}
 with sqlite3.connect((audit.PRIOR/'stage266_clean_daily/clean_daily.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as c:
  c.execute('PRAGMA query_only=ON')
  for req in audit._REQUESTS.values():
   raw=c.execute('SELECT open,high,low,close FROM daily_bars WHERE contract_epoch_id=? AND trade_date=?',(req['contract_epoch_id'],req['source_trade_date'])).fetchone()
   if raw is None or any(not math.isclose(float(req['source_'+k]),float(v),rel_tol=0,abs_tol=1e-8) for k,v in zip(['open','high','low','close'],raw)):raise ValueError('064_source_state_current_clean_OHLC_mismatch')
 prior={r['path']:r for r in json.loads((PREVIOUS/'source_bindings.json').read_text())};results=[];integrity=[]
 for listed in candidates.sort_values('path').to_dict('records'):
  frame,record=audit._load_csv(listed['path']);verify_inherited_binding(record,prior[listed['path']],listed)
  audits,passed=audit._audit_frame(frame,record,[listed['requirement_id']]);results.append(dict(source=record,audits=audits,passed=passed))
  integrity.append(dict(path=listed['path'],raw_sha256=record['sha256'],current_matches056=True,current_matches064=True,bytes=record['bytes'],mtime_ns=record['mtime_ns'],inode=record['inode']))
 sqlite_results=audit._audit_sqlite();results.extend(sqlite_results)
 all_audits=[];sources=[];qualified={}
 for result in results:
  sources.append(result['source']);all_audits.extend(result['audits'])
  for item in result['passed']:
   canonical=json.dumps(item['minute_path'],sort_keys=True,separators=(',',':'),allow_nan=False).encode();digest=hashlib.sha256(canonical).hexdigest();key=(item['requirement_id'],digest)
   if key not in qualified:
    folder=OUT/'qualified_paths'/item['requirement_id'];folder.mkdir(parents=True,exist_ok=True);path=folder/(digest+'.csv');pd.DataFrame(item['minute_path']).to_csv(path,index=False)
    qualified[key]=dict(requirement_id=item['requirement_id'],state_id=item['state_id'],data_path=str(path),data_csv_sha256=audit.sha(path),canonical_input_sha256=digest,rows=len(item['minute_path']),source_ids=[],bindings=[],physical_session_verified=False,reference_policy_grid_only=True,usable_for_trading=False)
   qualified[key]['source_ids'].append(item['binding']['source_id']);qualified[key]['bindings'].append(item['binding'])
 manifest=list(qualified.values());(OUT/'qualified_inputs_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 (OUT/'source_bindings.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 (OUT/'six_current_raw_sha_verified.json').write_text(json.dumps(integrity,ensure_ascii=False,indent=2)+'\n')
 pd.DataFrame(all_audits).to_csv(OUT/'all_source_component_audits.csv',index=False)
 rows=[]
 for rid,req in audit._REQUESTS.items():
  accepted=[p for p in manifest if p['requirement_id']==rid];row=dict(requirement_id=rid,contract_epoch_id=req['contract_epoch_id'],source_trade_date=req['source_trade_date'],qualified_distinct_inputs=len(accepted),qualified_source_members=sum(len(p['source_ids']) for p in accepted),expected_minutes=len(audit._GRIDS[rid]),first_reference_minute=audit._GRIDS[rid][0].isoformat(),last_reference_minute=audit._GRIDS[rid][-1].isoformat(),physical_session_verified=False,status='conditional_reference_input_available' if accepted else 'all_sources_rejected')
  rows.append(row)
 pd.DataFrame(rows).to_csv(OUT/'two_requirement_results.csv',index=False)
 for p,digest in before.items():
  if audit.sha(p)!=digest:raise ValueError('frozen_background_changed:'+p)
 summary=dict(started_at=started,completed_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),requirements=2,CSV_sources=6,CSV_bytes=sum(r['bytes'] for r in integrity),verified_original056_raw_SHA=6,sqlite_native_projections=len(sqlite_results),source_components=len(all_audits),status_counts=pd.Series([r['status'] for r in all_audits]).value_counts().to_dict(),qualified_requirements=sum(r['qualified_distinct_inputs']>0 for r in rows),qualified_distinct_inputs=len(manifest),qualified_source_members=sum(len(r['source_ids']) for r in manifest),requirements_with_multiple_distinct_inputs=sum(r['qualified_distinct_inputs']>1 for r in rows),old117_manifest_unchanged=True,old117_manifest_sha256=before[str(PREVIOUS/'qualified_inputs_manifest.json')],new_manifest_sha256=audit.sha(OUT/'qualified_inputs_manifest.json'),physical_session_verified=False,conditional_reference_only=True,C2_outcomes=0,full60_replays=0,model_fits=0,labels_changed=0,downloads=0,orders=0,core_modified=False,background_inputs=before,source_code_sha256=audit.sha(Path(__file__)),test_sha256=audit.sha(Path(__file__).with_name('test_stage067_followup_minute_input_audit.py')))
 (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='background_inputs'},ensure_ascii=False))

if __name__=='__main__':run()
