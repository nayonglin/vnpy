"""Independent46-curve/23-pair audit. No report/strategy/engine imports."""
from pathlib import Path
import argparse,hashlib,json,math,time
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';STAGES=LINE/'stages';checks=0
def ok(v,label):
 global checks
 checks+=1
 if not v:raise AssertionError(label)
def near(a,b,label):
 if np.ndim(a)==0 and (a is None or pd.isna(a)):ok(np.ndim(b)==0 and (b is None or pd.isna(b)),label);return
 ok(np.allclose(a,b,rtol=1e-10,atol=1e-6,equal_nan=False),label)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def load(p):return json.loads(Path(p).read_text())
def cmp(a,b):return 0 if math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-6) else (1 if a>b else -1)
def E_metrics(E):
 E=np.asarray(E,float);prev=np.r_[150000.,E[:-1]];defined=bool(np.isfinite(E).all() and (prev>0).all());r=(E-prev)/prev if defined else None;defined=defined and bool(np.isfinite(r).all());std=float(r.std(ddof=1)) if defined else 0.
 return dict(initial_trading_capital=150000.,account_end_equity=float(E[-1]),account_growth_pct=float((E[-1]/150000.-1)*100),balance_max_dd_pct=float((E/np.maximum.accumulate(np.r_[150000.,E])[1:]-1).min()*100),balance_sharpe=float(r.mean()/std*np.sqrt(252)) if defined and std>0 else 0.,balance_returns_defined=defined,nonpositive_trading_equity_days=int((E<=0).sum()))
def audit(report,output):
 started=time.monotonic();fp=STAGES/'stage013_freeze_v2.json';f=load(fp);reg=load(LINE/'outputs/stage013_multistart_v2/registry.json');oldreg=load(f['baseline_registry']);admission=load(STAGES/'stage013_independent_reuse_admission.json');starts=f['starts'];wanted={(s,v) for s in starts for v in ['C_R150','C_R100']}
 ok(reg['financial_engine_batch_complete'] is True and reg['financial_replays_started']==4 and len(reg['jobs'])==23 and all(j['status']=='validated' for j in reg['jobs'].values()),'complete23_exact4fresh19proof');ok(reg['counts']['fresh_validated']==4 and reg['counts']['proven_reuse_validated']==19,'method_counts_not23_new_engines');ok(reg['freeze_sha256']==sha(fp),'registry_freeze');ok(sha(f['baseline_delivery_manifest'])==f['baseline_delivery_manifest_sha256']=='b4712560c72548106fb9e4273895e1bfc80c56a6813cdfe3d71b4190b5d5a424','original_C_not_Stage011_uniform_control')
 manifest=load(report/'data_manifest.json')['files_sha256'];meta=load(report/'comparison.json')
 for p,h in {**manifest,**meta['source_files_sha256']}.items():ok(sha(p)==h,'report_source_hash:'+p)
 ok(meta['financial_replays']==4 and meta['proven_candidate_reuses']==19 and meta['reused_baseline_controls']==23 and meta['promotion_decision']=='NO_PROMOTION','transparent_mixed_provenance')
 s=pd.read_csv(report/'summary.csv',float_precision='round_trip');d=pd.read_csv(report/'daily.csv',float_precision='round_trip');p=pd.read_csv(report/'paired.csv',float_precision='round_trip');cohort=pd.read_csv(report/'cohort_summary.csv');ev=pd.read_csv(report/'reserve_events.csv',float_precision='round_trip');ok(len(s)==46 and not s.duplicated(['start','variant']).any() and set(zip(s.start,s.variant))==wanted,'exact46summary');ok(len(d)==70998 and not d.duplicated(['start','variant','date']).any() and set(zip(d.start,d.variant))==wanted,'exact70998daily');ok(len(p)==23 and not p.start.duplicated().any() and set(p.start)==set(starts),'exact23pairs');ok(not any('wealth_' in k or 'three_gate' in k for k in p.columns),'no_same_W_budget_promotion_gate')
 si=s.set_index(['start','variant']);dg={(start,v):g for (start,v),g in d.groupby(['start','variant'],sort=False)};expected={};receipts={};ledgers={};methodcounts={'fresh_engine':0,'proven_nonbinding_reuse':0};rawchecks=fundingchecks=ownchecks=0;events_count=0
 mapping=pd.read_csv(Path(f['data_directory'])/'mapping.csv',usecols=['date']);calendar=sorted(set(mapping.date))
 for start,variant in sorted(wanted):
  old=variant=='C_R150';job=(oldreg if old else reg)['jobs'][start+'|C'];path=Path(job['path']);limit=150000. if old else 100000.;method='frozen_baseline' if old else job['method'];rp=STAGES/('stage009_independent_receipts' if old else 'stage013_independent_receipts_v2')/f'{start}_C.json';r=load(rp);receipts[str(rp)]=sha(rp);ok(r['status']=='PASS_WITH_LIMITATIONS' and all(r[k]==0 for k in ['P0','P1','P2','failures']) and r['path']==str(path),'accepted_exact_window_receipt');pins=job.get('files_sha256') or job['source_files_sha256'];cp=load(job['checkpoint']);ok(sha(job['checkpoint'])==meta['source_files_sha256'][str(Path(job['checkpoint']).resolve())],'checkpoint_in_report_graph')
  if not old:
   methodcounts[method]+=1;ok(r['method']==method and r['freeze_sha256']==sha(fp) and r['frozen_source_head']==f['source_head'],'candidate_receipt_method_and_frozen_identity');rawchecks+=r['raw_core_checks'];fundingchecks+=r['funding_checks'];ownchecks+=r['stage013_checks']
   if method=='proven_nonbinding_reuse':ok(start in admission['reuse_starts'] and r['reused'] is True and path==Path(oldreg['jobs'][start+'|C']['path']),'genuine_same_source_proven_reuse')
   else:ok(start in admission['fresh_starts'] and r['reused'] is False and path!=Path(oldreg['jobs'][start+'|C']['path']) and r['first_binding_prefix']['all_trading_fields_identical_before_binding'] is True,'genuine_binding_new_engine')
  for name in ['daily.csv','reserve_daily.csv','reserve_events.json','actual_strategy_settings.json','effective_parameters.json','entry_risk.csv']:
   q=path/name;h=sha(q);ok(h==pins[str(q)]==r['source_files_sha256'][str(q)],'actual_source_SHA:'+str(q));ledgers[str(q)]=h
  raw=pd.read_csv(path/'daily.csv',float_precision='round_trip');bridge=pd.read_csv(path/'reserve_daily.csv',float_precision='round_trip');events=load(path/'reserve_events.json');projection=dg[(start,variant)];row=si.loc[(start,variant)];days=raw.date.astype(str).str[:10].tolist();ok(days==[x for x in calendar if start<=x<=f['cutoff']],'actual_complete_exchange_calendar');ok(days==projection.date.tolist()==bridge.date.astype(str).str[:10].tolist(),'exact_projection_source_calendar')
  amounts={}
  for e in events:amounts[str(e['date'])[:10]]=amounts.get(str(e['date'])[:10],0.)+float(e['transfer_amount'])
  flow=np.array([amounts.get(day,0.) for day in days]);T=flow.cumsum();PnL=raw.net_pnl.cumsum().to_numpy();E=150000.+PnL+T;R=limit-T;W=150000.+limit+PnL;near(raw.account_equity.to_numpy(),150000.+PnL,'raw150k_plus_truePnL');ok((R>=-1e-6).all() and (flow>=0).all(),'reserve_never_overdrawn');near(E+R,W,'different_budget_wealth_identity')
  arrays=dict(raw_account_equity=150000.+PnL,net_pnl=raw.net_pnl.to_numpy(),trading_account_equity=E,reserve_balance=R,cumulative_transfer=T,transfer_amount=flow,total_account_equity=W,slippage=raw.slippage.to_numpy(),commission=raw.commission.to_numpy(),trade_count=raw.trade_count.to_numpy(),total_margin_exact=raw.total_margin_exact.to_numpy(),account_nav=E/150000.,balance_drawdown_pct=(E/np.maximum.accumulate(np.r_[150000.,E])[1:]-1)*100,reserve_initial=np.full_like(E,limit))
  for key,value in arrays.items():near(projection[key],value,'all_projected_daily:'+key)
  offset=50000. if method=='proven_nonbinding_reuse' else 0.
  for key in ['raw_account_equity','net_pnl','trading_account_equity','cumulative_transfer','transfer_amount']:near(bridge[key],arrays[key],'actual_E_path:'+key)
  for key in ['reserve_balance','total_account_equity']:near(bridge[key]-offset,arrays[key],'only_auxiliary_R_W_projection:'+key)
  fields=E_metrics(E);margin=np.divide(raw.total_margin_exact.to_numpy()*165.,E,out=np.full_like(E,np.nan),where=E>0);exhaust=R<=1e-6;fields.update(real_trading_net_pnl=float(PnL[-1]),total_transferred=float(T[-1]),off_account_reserve_end=float(R[-1]),total_slippage=float(raw.slippage.sum()),total_commission=float(raw.commission.sum()),modeled_fill_count=int(raw.trade_count.sum()),transfer_event_days=int((flow>0).sum()),trading_days=len(days),reserve_initial=limit,transfer_event_count=len(events),reserve_exhausted=bool(exhaust.any()),trading_margin_peak_pct=float(np.nanmax(margin)) if np.isfinite(margin).any() else None,trading_margin_over100_days=int((margin>100).sum()),open_round_net_mtm=r['metrics']['open_round_net_mtm'])
  fields.update({'round_'+k:v for k,v in r['metrics']['rounds'].items()})
  for key,value in fields.items():near(value,row[key],'independent_summary:'+key)
  ok(row.method==method and row.arm=='C' and row.actual_start==days[0] and row.actual_end==days[-1] and bool(row.observation_only)==(start=='2026-01-01'),'summary_method_and_window');date='' if pd.isna(row.exhaustion_date) else str(row.exhaustion_date);ok(date==('' if not exhaust.any() else days[int(np.flatnonzero(exhaust)[0])]),'exact_exhaustion_date');near(fields['round_closed_net_pnl']+fields['open_round_net_mtm'],PnL[-1],'complete_round_open_MTM_truePnL');near(E[-1]-150000.,PnL[-1]+T[-1],'E_growth_deposit_bridge');near(fields['total_commission'],0.,'frozen_zero_commission')
  eventrows=ev.loc[ev.start.eq(start)&ev.variant.eq(variant)];ok(len(eventrows)==len(events),'projected_event_count');events_count+=len(events)
  for original,reported in zip(events,eventrows.to_dict('records')):
   for key in ['candidate_key','date','direction','signal','entry_context']:ok(str(original[key])==str(reported[key]),'event_identity:'+key)
   for key in ['transfer_amount','trading_equity_before','trading_equity_after','cumulative_transfer','raw_account_equity']:near(original[key],reported[key],'event_trading_field:'+key)
   for key in ['reserve_before','reserve_after','total_account_equity']:near(float(original[key])-offset,reported[key],'event_only_R_W_shift:'+key)
  expected[(start,variant)]=fields
 ok(methodcounts=={'fresh_engine':4,'proven_nonbinding_reuse':19} and len(ev)==events_count,'exact4new19proof_and_all_events')
 pairs={'delta_account_end_equity':'account_end_equity','delta_real_trading_net_pnl':'real_trading_net_pnl','delta_account_growth_pp':'account_growth_pct','delta_balance_max_dd_pp':'balance_max_dd_pct','delta_balance_sharpe':'balance_sharpe','delta_deposits':'total_transferred'}
 for row in p.itertuples():
  old=expected[(row.start,'C_R150')];new=expected[(row.start,'C_R100')];method=reg['jobs'][row.start+'|C']['method'];ok(row.method100==method and bool(row.observation_only)==(row.start=='2026-01-01'),'paired_method_and_observation')
  for prefix,metrics in [('r150',old),('r100',new)]:
   for field in ['account_end_equity','real_trading_net_pnl','total_transferred','balance_max_dd_pct','balance_sharpe']:near(metrics[field],getattr(row,prefix+'_'+field),'paired_absolute_metrics:'+prefix+'_'+field)
  for name,key in pairs.items():near(new[key]-old[key],getattr(row,name),'paired_actual_delta:'+name)
  for name,key in [('real_pnl_comparison','real_trading_net_pnl'),('dd_comparison','balance_max_dd_pct'),('sharpe_comparison','balance_sharpe')]:near(cmp(new[key],old[key]),getattr(row,name),'paired_equality_or_order:'+name)
  near(row.delta_account_end_equity,row.delta_real_trading_net_pnl+row.delta_deposits,'paired_cashflow_not_alpha')
  if method=='proven_nonbinding_reuse':
   for name in pairs:near(getattr(row,name),0.,'nineteen_reuse_full_E_metrics_equal:'+name)
  near(new['total_transferred'],min(old['total_transferred'],100000.),'fixed_cap_actual_consumption')
 ok(len(cohort)==6 and not cohort.duplicated(['cohort','scope']).any(),'exact6cohorts')
 for row in cohort.itertuples():
  g=p.loc[p.observation_only.eq(row.scope=='observation_lt_1y')]
  if row.cohort!='combined':g=g.loc[g.cohort.eq(row.cohort)]
  fields=dict(n=len(g),fresh=int(g.method100.eq('fresh_engine').sum()),proof_reuse=int(g.method100.eq('proven_nonbinding_reuse').sum()),real_pnl_higher=int(g.real_pnl_comparison.eq(1).sum()),real_pnl_equal=int(g.real_pnl_comparison.eq(0).sum()),real_pnl_lower=int(g.real_pnl_comparison.eq(-1).sum()),dd_shallower=int(g.dd_comparison.eq(1).sum()),dd_equal=int(g.dd_comparison.eq(0).sum()),dd_deeper=int(g.dd_comparison.eq(-1).sum()),sharpe_higher=int(g.sharpe_comparison.eq(1).sum()),sharpe_equal=int(g.sharpe_comparison.eq(0).sum()),sharpe_lower=int(g.sharpe_comparison.eq(-1).sum()))
  for key,value in fields.items():near(value,getattr(row,key),'independent_cohort_recount:'+key)
 for name,h in manifest.items():ok(sha(name)==h,'projection_immutable_after_independent_audit')
 code=[LINE/'tools'/name for name in ['stage013_report.py','stage013_plots.py','stage013_reuse.py','stage010_account_nav.py','stage011_report.py','stage013_independent_window_v2.py','stage009_independent_window.py','stage008_independent_window.py']]
 result=dict(schema='stage013_independent_numeric_review_v1',status='PASS_WITH_LIMITATIONS',accepted=True,P0=0,P1=0,P2=0,failures=[],freeze_sha256=sha(fp),financial_source_head=f['source_head'],variant_windows=46,paired_windows=23,daily_points=70998,new_financial_runs=4,proven_candidate_reuses=19,old_controls=23,complete_pairs=22,observation_pairs=1,checks=checks,raw_core_checks=rawchecks,funding_checks=fundingchecks,stage013_checks=ownchecks,data_files_sha256=manifest,audited_code_sha256={str(x):sha(x) for x in code},window_receipts_sha256=receipts,selected_ledger_files_sha256=ledgers,cohort_summary=cohort.to_dict('records'),same_budget_W_gates_used=False,confidence='High within frozen daily model for accounting, original risk tiers, each cashflow and19 full-state reuse induction; bounded generalization after history-selected100k and overlapping starts.',financial_replays=0,market_downloads=0,production_accesses=0,promotion_decision='NO_PROMOTION',seconds=time.monotonic()-started,auditor_source_sha256=sha(__file__))
 output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['status','checks','raw_core_checks','funding_checks','stage013_checks','variant_windows','paired_windows','daily_points','seconds']},ensure_ascii=False));return result
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--report',type=Path,default=LINE/'artifacts/stage013_reserve100k_comparison');ap.add_argument('--output',type=Path,default=STAGES/'stage013_independent_numeric_review.json');a=ap.parse_args()
 if a.output.exists():raise ValueError('immutable_stage013_numeric_review_exists')
 audit(a.report,a.output)
if __name__=='__main__':main()
