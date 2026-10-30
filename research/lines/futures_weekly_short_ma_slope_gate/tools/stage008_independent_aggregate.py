"""Whole frozen multi-start integrity and independent paired/cohort aggregation."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,math
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[4];L=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';S=L/'stages';B=L/'outputs/stage008_multistart';D=L/'outputs/data_stage001_20261029/data_approved';RR=S/'stage008_independent_receipts';checks=0;cache={}
def sha(p):
 p=Path(p)
 if str(p) not in cache:
  h=hashlib.sha256()
  with p.open('rb') as f:
   for b in iter(lambda:f.read(8388608),b''):h.update(b)
  cache[str(p)]=h.hexdigest()
 return cache[str(p)]
def ok(v,k):
 global checks;checks+=1
 if not v:raise AssertionError(k)
def eq(a,b):return math.isfinite(float(a)) and math.isfinite(float(b)) and math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-7)
def near(a,b,k):ok(eq(a,b),k)
def main():
 fpath=S/'stage008_freeze.json';freeze=json.loads(fpath.read_text());fs=sha(fpath);reg=json.loads((B/'registry.json').read_text());starts=[f'{y}-{m:02d}-01' for y in range(2015,2027) for m in [1,6] if (y,m)<=(2026,1)];keys={s+'|'+a for s in starts for a in ['A','C']};ok(freeze['starts']==starts and freeze['cutoff']=='2026-10-29','frozen23');ok(reg['freeze_sha256']==fs and set(reg['jobs'])==keys and all(x['status']=='validated' for x in reg['jobs'].values()),'all46_complete');ok(reg['financial_replays_started']==42 and reg['financial_engine_batch_complete'] is True,'exact42_new_engines')
 ok(set(p.stem for p in RR.glob('*.json'))=={s+'_'+a for s in starts for a in ['A','C']},'exact46_independent_receipts');bindings={};counts={}
 for p,h in freeze['source_files_sha256'].items():ok(Path(p).is_file() and sha(p)==h,'freeze_source:'+p)
 for n in ['stage001_delivery_manifest.json','stage002_delivery_manifest.json','stage003_delivery_manifest.json','stage004_delivery_manifest.json','stage004_delivery_manifest_v2.json','stage005_delivery_manifest.json','stage006_delivery_manifest.json','stage007_delivery_manifest.json']:
  p=S/n;rows=json.loads(p.read_text())['files_sha256'];counts[n]=len(rows)
  for q,h in rows.items():ok(Path(q).is_file() and sha(q)==h,'old_delivery:'+n+':'+q)
 calendar=sorted(pd.read_csv(D/'mapping.csv',usecols=['date']).date.unique());receipts={};rawdaily={};settings={};effective={};summary=[];pointcount=0;auditor=L/'tools/stage008_independent_window.py';paths=set();receiptshas={};cpshas={}
 for start in starts:
  for arm in ['A','C']:
   key=start+'|'+arm;p=RR/f'{start}_{arm}.json';r=json.loads(p.read_text());job=reg['jobs'][key];cp=Path(job['checkpoint']);c=json.loads(cp.read_text());path=Path(r['path']);paths.add(str(path.resolve()));receipts[key]=r;receiptshas[str(p)]=sha(p);cpshas[str(cp)]=sha(cp)
   ok(r['freeze_sha256']==fs and r['frozen_source_head']==freeze['source_head'] and r['arm']==arm and r['requested_start']==start and r['end']==freeze['cutoff'],'receipt_identity:'+key);ok(r['status']=='PASS_WITH_LIMITATIONS' and r['failures']==r['P0']==r['P1']==r['P2']==0,'receipt_pass:'+key);ok(r['auditor_source_sha256']==sha(auditor),'stable_actual_auditor_source:'+key)
   expectedcpkey=hashlib.sha256(json.dumps(dict(source_head=freeze['source_head'],freeze_sha256=fs,cutoff=freeze['cutoff'],arm=arm,start=start),sort_keys=True).encode()).hexdigest();ok(c['checkpoint_key']==expectedcpkey==job['checkpoint_key'],'root_checkpoint_key:'+key);ok(r['source_files_sha256']==c['files_sha256']==job['files_sha256'],'same_exact_output_snapshot:'+key)
   for q,h in r['source_files_sha256'].items():ok(Path(q).is_file() and sha(q)==h,'output:'+q)
   inputs=json.loads((path/'input_manifest.json').read_text())
   for q,h in inputs.items():
    ok(Path(q).is_file() and sha(q)==h,'input:'+q)
    if q in bindings:ok(bindings[q]==h,'no_conflicting_shared_input:'+q)
    bindings[q]=h
   ok(r['reused'] is (key in freeze['reuse_runs']),'explicit_reuse_only:'+key)
   if r['reused']:ok(path.resolve()==Path(freeze['reuse_runs'][key]).resolve(),'exact_reused_path:'+key)
   else:
    pre=json.loads((path/'preflight.json').read_text());ok(pre['head']==pre['frozen_source_head']==freeze['source_head'] and pre['freeze_sha256']==fs,'fresh_real_head:'+key)
   cold=r['cold_start_warmup_evidence'];ok(cold['first_equity']==150000 and cold['first_day_financial_positions']==0 and cold['requested_start']==start,'cold_start:'+key)
   d=pd.read_csv(path/'daily.csv');expected=[x for x in calendar if start<=x<=freeze['cutoff']];ok(d.date.tolist()==expected and cold['calendar_days']==len(d),'full_calendar:'+key);pointcount+=len(d);rawdaily[key]=d
   settings[key]=json.loads((path/'actual_strategy_settings.json').read_text());effective[key]=json.loads((path/'effective_parameters.json').read_text());ok(settings[key][0]['actual']['trade_start_date']==start,'actual_trade_start:'+key)
   e=d.account_equity.to_numpy();rets=np.diff(np.r_[150000,e])/np.r_[150000,e][:-1];dd=(e/np.maximum.accumulate(np.r_[150000,e])[1:]-1)*100;calc=dict(end_equity=float(e[-1]),total_return_pct=(e[-1]/150000-1)*100,max_dd_pct=float(dd.min()),sharpe=float(rets.mean()/rets.std(ddof=1)*np.sqrt(252)),total_slippage=d.slippage.sum(),total_trade_count=d.trade_count.sum())
   for metric,val in calc.items():near(r['metrics'][metric],val,'independent_daily_metric:'+key+':'+metric);near(job['metrics'][metric],val,'checkpoint_metric:'+key+':'+metric)
   margin=d.total_margin_exact/d.account_equity*1.65*100;near(r['risk']['configured_margin_max_pct'],margin.max(),'configured_margin:'+key);near(r['risk']['configured_margin_over100_days'],margin.gt(100).sum(),'configured_margin_days:'+key);ok(r['risk']['positive_equity_all_days']==bool(d.account_equity.gt(0).all()),'survival:'+key)
   mature=pd.Timestamp(freeze['cutoff'])>=pd.Timestamp(start)+pd.DateOffset(years=1);summary.append(dict(key=key,start=start,arm=arm,cohort='January' if start[5:7]=='01' else 'June',complete_ge1year=bool(mature),actual_start=expected[0],end=expected[-1],trading_days=len(d),**r['metrics'],**r['risk'],reused=r['reused'],core_checks=r['checks']))
 ok(len(paths)==46,'46_distinct_accounts');pairs=[];norm=[]
 for start in starts:
  a=receipts[start+'|A'];c=receipts[start+'|C'];ok(settings[start+'|A']==settings[start+'|C'] and effective[start+'|A']==effective[start+'|C'],'same_pair_settings_effective:'+start);ok(rawdaily[start+'|A'].date.equals(rawdaily[start+'|C'].date),'paired_calendar:'+start)
  n=json.loads(json.dumps(settings[start+'|A']))
  for field in ['setting','actual']:ok(n[0][field]['trade_start_date']==start,'declared_only_start_field:'+start+field);n[0][field]['trade_start_date']='<independent_start>'
  norm.append(n);ok(effective[start+'|A']==effective[starts[0]+'|A'],'same_effective_all_starts:'+start)
  am=a['metrics'];cm=c['metrics'];g=dict(equity_higher=bool(cm['end_equity']>am['end_equity'] and not eq(cm['end_equity'],am['end_equity'])),dd_not_worse=bool(cm['max_dd_pct']>=am['max_dd_pct'] or eq(cm['max_dd_pct'],am['max_dd_pct'])),sharpe_not_lower=bool(cm['sharpe']>=am['sharpe'] or eq(cm['sharpe'],am['sharpe'])));pairs.append(dict(start=start,cohort='January' if start[5:7]=='01' else 'June',complete_ge1year=bool(pd.Timestamp(freeze['cutoff'])>=pd.Timestamp(start)+pd.DateOffset(years=1)),**g,all_three_pass=all(g.values()),equity_tie=eq(cm['end_equity'],am['end_equity']),**{'difference_'+k:cm[k]-am[k] for k in ['end_equity','total_return_pct','max_dd_pct','sharpe']}))
 ok(all(n==norm[0] for n in norm),'only_actual_start_changes_across_all23');pdf=pd.DataFrame(pairs);cohorts={}
 for name in ['combined','January','June']:
  q=pdf.loc[pdf.complete_ge1year & (True if name=='combined' else pdf.cohort.eq(name))];cohorts[name]=dict(complete_windows=len(q),equity_higher=int(q.equity_higher.sum()),dd_not_worse=int(q.dd_not_worse.sum()),sharpe_not_lower=int(q.sharpe_not_lower.sum()),all_three_pass=int(q.all_three_pass.sum()),equity_ties=int(q.equity_tie.sum()))
 ok([cohorts[x]['complete_windows'] for x in ['combined','January','June']]==[22,11,11] and pdf.loc[~pdf.complete_ge1year,'start'].tolist()==['2026-01-01'],'mature_cohort_and_observation_coverage')
 tab=pd.DataFrame([{k:v for k,v in x.items() if k!='rounds'} for x in summary]);worst={}
 for arm in ['A','C']:
  q=tab.loc[tab.arm.eq(arm)&tab.complete_ge1year];worst[arm]={}
  for metric in ['end_equity','total_return_pct','max_dd_pct','sharpe']:
   row=q.loc[q[metric].idxmin()];worst[arm][metric]=dict(start=row.start,value=float(row[metric]))
  worst[arm].update(negative_return_windows=int(q.total_return_pct.lt(0).sum()),nonpositive_equity_windows=int((~q.positive_equity_all_days).sum()),configured_margin_over100_windows=int(q.configured_margin_over100_days.gt(0).sum()))
 pd.DataFrame(pairs).to_csv(S/'stage008_independent_paired.csv',index=False);tab.to_csv(S/'stage008_independent_summary.csv',index=False)
 result=dict(status='PASS_ALL46_ACCOUNTING_AND_SOURCE_WITH_LIMITATIONS',P0=0,P1=0,P2=0,failures=0,reviewed_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),freeze_sha256=fs,source_head=freeze['source_head'],arm_windows=46,paired_windows=23,new_engines=42,reused=4,complete_voting_windows=22,observation_windows=['2026-01-01'],actual_total_daily_NAV_DD_points=pointcount,core_checks_total=sum(x['checks'] for x in receipts.values()),aggregate_integrity_checks=checks,cohort_votes=cohorts,worst_complete_windows=worst,receipt_sha256=receiptshas,checkpoint_sha256=cpshas,stable_auditor_source_sha256=sha(auditor),aggregate_source_sha256=sha(Path(__file__)),shared_input_file_count=len(bindings),frozen_delivery_counts=counts,financial_replays=0,market_downloads=0,production_accesses=0,promotion_decision='NO_PROMOTION',limitations=['Overlapping start-to-now accounts are not independent samples, pooled portfolio returns, or OOS evidence.','Warmup and same-epoch full cached daily range preserve causal bounds but do not prove complete listing history/PIT/real broker capacity.'])
 out=S/'stage008_independent_aggregate.json';ok(not out.exists(),'immutable_aggregate_output');out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['receipt_sha256','checkpoint_sha256']},ensure_ascii=False))
if __name__=='__main__':main()
