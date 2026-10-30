"""Final rehash of every59 fresh output file and receipt; no financial computation."""
from pathlib import Path
import hashlib,json,time
from stage014_independent_scope import scope,mature
ROOT=Path(__file__).resolve().parents[4];L=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';S=L/'stages'
load=lambda p:json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 started=time.monotonic();out=S/'stage014_independent_runs_review.json'
 if out.exists():raise ValueError('immutable_runs_review_exists')
 fp=S/'stage014_freeze.json';f=load(fp);sc=scope(f);regp=L/'outputs/stage014_multistart/registry.json';reg=load(regp);gatep=S/'stage014_canary_independent_review.json';gate=load(gatep);assert gate['accepted'] and gate['prefix_through_2026_10_29_unchanged'] and gate['freeze_sha256']==sha(fp)
 assert reg['freeze_sha256']==sha(fp) and reg['source_head']==f['source_head'] and reg['financial_engine_batch_complete'] is True and reg['financial_replays_started']==59 and all(j['status']=='validated' for j in reg['jobs'].values())
 for p,h in f['source_files_sha256'].items():assert sha(p)==h,p
 receipts={};checkpoints={};outputs={};windows=[];counts=dict(raw_core_checks=0,funding_checks=0,stage014_checks=0,entry_risk_rows=0);bytes_hashed=0
 for start in sc['starts']:
  j=reg['jobs'][start+'|C'];p=Path(j['path']);q=S/'stage014_independent_receipts'/f'{start}_C.json';r=load(q);cp=load(j['checkpoint']);assert r['status']=='PASS_WITH_LIMITATIONS' and all(r[k]==0 for k in ['P0','P1','P2','failures']) and r['method']==j['method']==cp['method']=='fresh_engine' and r['reused'] is cp['reused'] is False
  assert r['requested_start']==start and r['path']==str(p) and r['freeze_sha256']==sha(fp) and r['frozen_source_head']==f['source_head'];assert r['checkpoint_sha256']==sha(j['checkpoint']) and r['auditor_source_sha256']==sha(L/'tools/stage014_independent_window.py')
  actual={str(x):sha(x) for x in p.iterdir() if x.is_file()};assert actual==r['source_files_sha256']==j['files_sha256']==cp['files_sha256'],'complete_output_content_changed:'+start;outputs.update(actual);bytes_hashed+=sum(Path(x).stat().st_size for x in actual)
  assert r['stage014_parameter_review']['all_actual_settings_unchanged_except_declared_start_and_mapping'] and r['stage014_parameter_review']['all_effective_parameters_unchanged_except_declared_start_and_mapping'];assert abs(r['metrics']['rounds']['closed_net_pnl']+r['metrics']['open_round_net_mtm']-r['real_net_pnl'])<1e-6
  if start=='2015-01-01':assert r['canary_prefix']['prefix_through_2026_10_29_unchanged'] and gate['receipts_sha256'][str(q)]==sha(q)
  for key in ['raw_core_checks','funding_checks','stage014_checks']:counts[key]+=r[key]
  counts['entry_risk_rows']+=r['stage014_parameter_review']['entry_rows'];receipts[str(q)]=sha(q);checkpoints[j['checkpoint']]=sha(j['checkpoint']);windows.append(dict(start=start,mature=mature(start),account_display=r['account_display'],real_net_pnl=r['real_net_pnl'],risk=r['risk'],rounds=r['metrics']['rounds'],open_round_net_mtm=r['metrics']['open_round_net_mtm']))
 assert len(windows)==59 and sum(w['mature'] for w in windows)==54
 for p,h in gate['checkpoints_sha256'].items():assert sha(p)==h
 result=dict(schema='stage014_independent_59_fresh_runs_review_v1',status='PASS_WITH_LIMITATIONS',accepted=True,P0=0,P1=0,P2=0,failures=[],source_head=f['source_head'],freeze_sha256=sha(fp),registry_sha256=sha(regp),gate_sha256=sha(gatep),fresh_financial_runs=59,reused_candidates=0,mature_windows=54,observation_windows=5,checks=counts,complete_financial_output_files_sha256=outputs,output_files_rehashed=len(outputs),output_bytes_rehashed=bytes_hashed,receipts_sha256=receipts,checkpoints_sha256=checkpoints,windows=windows,data_admission_sha256=sha(S/'stage014_independent_data_admission.json'),code_admission_sha256=sha(S/'stage014_independent_code_review.json'),financial_replays=0,market_downloads=0,production_accesses=0,promotion_decision='NO_PROMOTION',confidence='Frozen-model accounting accepted; historical overlap/selection, zero fees, inherited PIT/lifecycle/structural gaps and static margin/capacity prevent promotion.',seconds=time.monotonic()-started,auditor_source_sha256=sha(__file__))
 out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'path':str(out),'sha256':sha(out),'checks':counts,'files':len(outputs),'bytes':bytes_hashed,'seconds':result['seconds']},ensure_ascii=False))
if __name__=='__main__':main()
