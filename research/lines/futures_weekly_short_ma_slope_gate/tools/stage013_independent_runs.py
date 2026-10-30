"""Seal 23 accepted Stage013 V2 per-window independent receipts; no finance."""
from pathlib import Path
from collections import Counter
import hashlib,json
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';STAGES=LINE/'stages'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def main():
 out=STAGES/'stage013_independent_runs_review.json'
 if out.exists():raise ValueError('immutable_runs_review_exists')
 fp=STAGES/'stage013_freeze_v2.json';f=load(fp);regp=LINE/'outputs/stage013_multistart_v2/registry.json';reg=load(regp);admission=load(STAGES/'stage013_independent_reuse_admission.json');code=load(STAGES/'stage013_independent_code_review_v2.json');gatep=STAGES/'stage013_canary_independent_review_v2.json';gate=load(gatep)
 assert reg['financial_engine_batch_complete'] and reg['financial_replays_started']==4 and reg['counts']['fresh_validated']==4 and reg['counts']['proven_reuse_validated']==19
 assert reg['freeze_sha256']==sha(fp) and reg['source_head']==f['source_head'] and gate['accepted'] and gate['freeze_sha256']==sha(fp)
 pre=f['pre_engine_failure'];assert pre['failed_dispatches']==1 and pre['engine_runs']==pre['financial_results']==0 and sha(pre['freeze'])==pre['freeze_sha256'] and sha(pre['registry'])==pre['registry_sha256']
 for q,h in f['source_files_sha256'].items():assert sha(q)==h,q
 receiptmap={};checkpointmap={};counts=Counter();windows=[];checks=Counter();entries=Counter()
 for start in f['starts']:
  q=STAGES/'stage013_independent_receipts_v2'/f'{start}_C.json';r=load(q);j=reg['jobs'][start+'|C'];cp=load(j['checkpoint']);assert j['status']=='validated'
  assert r['requested_start']==start and r['path']==j['path'] and r['method']==j['method'] and r['freeze_sha256']==sha(fp) and r['status']=='PASS_WITH_LIMITATIONS'
  assert all(r[k]==0 for k in ['P0','P1','P2','failures']);assert r['checkpoint_sha256']==sha(j['checkpoint']);assert r['source_files_sha256']==(cp['files_sha256'] if j['method']=='fresh_engine' else cp['source_files_sha256'])
  assert r['auditor_source_sha256']==sha(LINE/'tools/stage013_independent_window_v2.py');assert r['stage013_parameter_review']['all_actual_settings_unchanged'] and r['stage013_parameter_review']['all_effective_parameters_unchanged']
  assert abs(r['metrics']['rounds']['closed_net_pnl']+r['metrics']['open_round_net_mtm']-r['real_net_pnl'])<1e-6
  if j['method']=='fresh_engine':assert r['first_binding_prefix']['all_trading_fields_identical_before_binding'] and start in admission['fresh_starts']
  else:assert r['reuse_admission_sha256']==sha(STAGES/'stage013_independent_reuse_admission.json') and start in admission['reuse_starts']
  receiptmap[str(q)]=sha(q);checkpointmap[j['checkpoint']]=sha(j['checkpoint']);counts[j['method']]+=1
  for k in ['raw_core_checks','funding_checks','stage013_checks']:checks[k]+=r[k]
  entries.update(r['stage013_parameter_review']['risk_mode_counts'])
  windows.append(dict(start=start,method=j['method'],path=j['path'],account_display=r['account_display'],real_net_pnl=r['real_net_pnl'],risk=r['risk'],rounds=r['metrics']['rounds'],open_round_net_mtm=r['metrics']['open_round_net_mtm'],entry_rows=r['stage013_parameter_review']['entry_rows']))
 assert dict(counts)=={'proven_nonbinding_reuse':19,'fresh_engine':4};assert len(receiptmap)==23
 assert sha(admission['source_hash_cache'])==admission['source_hash_cache_sha256'];cache=load(admission['source_hash_cache'])['files']
 statdrift={}
 for p,row in cache.items():
  s=Path(p).stat();current=[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
  if current!=row['stat']:
   digest=sha(p);assert digest==row['sha256'],'old_admitted_graph_content_changed:'+p
   after=Path(p).stat();assert [after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns]==current,'unstable_rehash:'+p
   statdrift[p]=dict(sha256=digest,old_stat=row['stat'],current_stat=current,same_content=True)
 result=dict(schema='stage013_independent_23_windows_v2',status='PASS_WITH_LIMITATIONS',accepted=True,P0=0,P1=0,P2=0,failures=[],freeze_sha256=sha(fp),financial_source_head=f['source_head'],registry_sha256=sha(regp),gate_sha256=sha(gatep),reuse_admission_sha256=sha(STAGES/'stage013_independent_reuse_admission.json'),code_review_v2_sha256=sha(STAGES/'stage013_independent_code_review_v2.json'),new_financial_engine_runs=4,proven_nonbinding_reuses=19,old_baseline_controls=23,pre_engine_failed_dispatches=1,failed_dispatch_engines=0,method_counts=dict(counts),checks=dict(checks),reuse_admission_checks=admission['checks'],actual_entry_risk_rows=sum(entries.values()),actual_risk_mode_counts=dict(entries),receipts_sha256=receiptmap,checkpoints_sha256=checkpointmap,windows=windows,old_admitted_graph_content_unchanged=len(cache),old_admitted_graph_stat_unchanged=len(cache)-len(statdrift),stat_drift_rehashed_same_content=statdrift,resolved_preflight_bug={'severity':'P1','status':'fixed_before_any_engine','review_coverage_gap_preserved':True,'evidence':str(STAGES/'stage013_independent_code_review_v2.json')},confidence='Accounting and deterministic reuse accepted within frozen daily model. Generalization bounded by overlapping historical starts, post-history amount choice, zero fees, PIT and capacity limitations.',financial_replays=0,market_downloads=0,production_accesses=0,promotion_decision='NO_PROMOTION',auditor_source_sha256=sha(__file__))
 out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'path':str(out),'sha256':sha(out),'checks':dict(checks),'entries':sum(entries.values())},ensure_ascii=False))
if __name__=='__main__':main()
