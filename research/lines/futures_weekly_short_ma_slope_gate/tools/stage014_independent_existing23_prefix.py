"""Readonly old23 C causal-prefix reconciliation against the matching Stage014 cold starts."""
from pathlib import Path
import argparse,hashlib,json,time
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';S=LINE/'stages';checks=0
load=lambda p:json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def ok(v,label):
 global checks
 checks+=1
 if not v:raise AssertionError(label)
def compare(a,b,label):
 ok(list(a.columns)==list(b.columns) and len(a)==len(b),'shape:'+label)
 for k in a.columns:
  x=a[k].reset_index(drop=True);y=b[k].reset_index(drop=True)
  if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):ok(np.allclose(x,y,rtol=1e-10,atol=1e-6,equal_nan=True),'numeric:'+label+':'+k)
  else:ok(x.fillna('').astype(str).equals(y.fillna('').astype(str)),'text:'+label+':'+k)
def audit(output,pilot=False):
 started=time.monotonic();f=load(S/'stage014_freeze.json');oldreg=load(f['baseline_registry']);reg=load(LINE/'outputs/stage014_multistart/registry.json');starts=sorted(s.split('|')[0] for s in oldreg['jobs'] if s.endswith('|C'));ok(len(starts)==23,'exact_old23_C_controls');
 if pilot:starts=[s for s in starts if reg['jobs'][s+'|C']['status']=='validated']
 else:ok(reg['financial_engine_batch_complete'] and reg['counts']['validated']==59,'new59_complete')
 ok(bool(starts),'at_least_one_matching_completed_start');sourcepins={};rows=[]
 fields={'daily.csv':'date','reserve_daily.csv':'date','trades.csv':'trading_date','execution_clock.csv':'trading_date','internal_equity_daily.csv':'date','weekly_readiness.csv':'date','weekly_bars.csv':'week_end','execution_anchor_requests.csv':'trading_date','entry_risk.csv':'date','entry_candidates.csv':'date'}
 for start in starts:
  old=oldreg['jobs'][start+'|C'];new=reg['jobs'][start+'|C'];a=Path(old['path']);b=Path(new['path']);receipt=S/'stage014_independent_receipts'/f'{start}_C.json';r=load(receipt);ok(r['status']=='PASS_WITH_LIMITATIONS' and r['requested_start']==start and r['freeze_sha256']==sha(S/'stage014_freeze.json'),'accepted_matching_window');detail={}
  for name,day in fields.items():
   pa=a/name;pb=b/name;ha=sha(pa);hb=sha(pb);ok(ha==old['files_sha256'][str(pa)] and hb==new['files_sha256'][str(pb)]==r['source_files_sha256'][str(pb)],'old_new_full_source_SHA:'+name);sourcepins[str(pa)]=ha;sourcepins[str(pb)]=hb;aa=pd.read_csv(pa,float_precision='round_trip');bb=pd.read_csv(pb,float_precision='round_trip');aa=aa.loc[aa[day].astype(str).str[:10].le('2026-10-29')].drop(columns=['result_scope'],errors='ignore');bb=bb.loc[bb[day].astype(str).str[:10].le('2026-10-29')].drop(columns=['result_scope'],errors='ignore');compare(aa,bb,start+':'+name);detail[name]={'prefix_rows':len(aa),'date_authority':day}
  # All position-export rows, not merely the terminal held set. Chunks preserve
  # whole chronological prefix and catch entry, exit, MTM and fee differences.
  pa=a/'positions.csv';pb=b/'positions.csv';ha=sha(pa);hb=sha(pb);ok(ha==old['files_sha256'][str(pa)] and hb==new['files_sha256'][str(pb)]==r['source_files_sha256'][str(pb)],'all_position_source_SHA');sourcepins[str(pa)]=ha;sourcepins[str(pb)]=hb
  def chunks(p):
   for q in pd.read_csv(p,chunksize=100000,float_precision='round_trip'):
    q=q.loc[q.date.astype(str).str[:10].le('2026-10-29')].drop(columns=['result_scope'],errors='ignore')
    if len(q):yield q
  aa=chunks(pa);bb=chunks(pb);total=0
  while True:
   x=next(aa,None);y=next(bb,None)
   if x is None:ok(y is None,'positions_no_extra_prefix');break
   ok(y is not None,'positions_no_missing_prefix');compare(x,y,start+':positions');total+=len(x)
  detail['positions.csv']={'prefix_rows':total,'date_authority':'date'}
  for name in ['reserve_events.json','reserve_checks.json','reserve_snapshots.json','reserve_fill_phases.json']:
   pa=a/name;pb=b/name;ha=sha(pa);hb=sha(pb);ok(ha==old['files_sha256'][str(pa)] and hb==new['files_sha256'][str(pb)]==r['source_files_sha256'][str(pb)],'native_signal_source_SHA');sourcepins[str(pa)]=ha;sourcepins[str(pb)]=hb;left=[x for x in load(pa) if str(x['date'])[:10]<='2026-10-29' and x.get('phase')!='runner_terminal'];right=[x for x in load(pb) if str(x['date'])[:10]<='2026-10-29' and x.get('phase')!='runner_terminal'];ok(left==right,'native_full_causal_prefix:'+start+':'+name);detail[name]={'prefix_rows':len(left),'excluded':'runner_terminal witness'}
  pending={}
  for kind,p,j in [('old29',a,old),('new30',b,new)]:
   q=p/'pending_orders.csv';h=sha(q);ok(h==j['files_sha256'][str(q)],'terminal_queue_source_SHA');sourcepins[str(q)]=h;pending[kind]={'sha256':h,'rows':len(pd.read_csv(q))}
  held=pd.read_csv(a/'positions.csv',usecols=['date','vt_symbol','end_pos']);held=held.loc[held.date.astype(str).str[:10].eq('2026-10-29')&held.end_pos.ne(0)];rows.append(dict(start=start,all_economic_prefix_fields_equal=True,compared_files=detail,old29_held_contracts=held.vt_symbol.tolist(),old29_held_contract_count=len(held),terminal_queues=pending))
 result=dict(schema='stage014_independent_old23_economic_prefix_v1',status='PASS_AVAILABLE_PREFIX_ONLY_WITH_LIMITATIONS' if pilot else 'PASS_WITH_LIMITATIONS',accepted=True,P0=0,P1=0,P2=0,failures=[],freeze_sha256=sha(S/'stage014_freeze.json'),source_head=f['source_head'],baseline_registry_sha256=sha(f['baseline_registry']),new_registry_sha256=sha(LINE/'outputs/stage014_multistart/registry.json'),matching_old_C_windows=len(starts),expected_old_C_windows=23,prefix_end='2026-10-29',checks=checks,windows=rows,source_files_sha256=sourcepins,old29_nonflat_windows=sum(x['old29_held_contract_count']>0 for x in rows),excluded_fields=['management result_scope label','old29 runner_terminal witness; new terminal is30','Terminal pending_orders29 vs30 have different observation times and are bound separately, not claimed equal. Ordinary orders export absent; immutable order anchors and actual executions through29 are compared.'],all_23_economic_prefixes_equal=len(rows)==23,new30_results_not_claimed_equal_to_old29=True,financial_replays=0,market_downloads=0,production_accesses=0,promotion_decision='NO_PROMOTION',seconds=time.monotonic()-started,auditor_source_sha256=sha(__file__))
 output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'path':str(output),'sha256':sha(output),'checks':checks,'nonflat_old29_windows':result['old29_nonflat_windows'],'seconds':result['seconds']},ensure_ascii=False))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=S/'stage014_independent_existing23_prefix_review.json');ap.add_argument('--available-pilot',action='store_true');a=ap.parse_args()
 if a.output.exists():raise ValueError('immutable_prefix_review_exists')
 audit(a.output,a.available_pilot)
if __name__=='__main__':main()
