"""Independent 92-curve/46-pair report audit from exact financial ledgers.

Imports no runner, strategy, report accounting or renderer. All cash curves and
metrics below are independently recomputed, including the inherited distinct E
and W undefined-return policies. Complete rounds come from accepted independent
raw inventory receipts and are reconciled against true daily PnL again.
"""
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
def curve(e,initial,positive):
 e=np.asarray(e,float);prev=np.r_[initial,e[:-1]];defined=bool(np.isfinite(e).all() and np.isfinite(prev).all() and ((prev>0) if positive else (prev!=0)).all());r=(e-prev)/prev if defined else None;defined=defined and bool(np.isfinite(r).all());std=float(r.std(ddof=1)) if defined else 0.
 return float(e[-1]),float((e[-1]/initial-1)*100),float((e/np.maximum.accumulate(np.r_[initial,e])[1:]-1).min()*100),float(r.mean()/std*np.sqrt(252)) if defined and std>0 else 0.,defined
def compare(a,b):return 0 if math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-6) else (1 if a>b else -1)
def audit(report,output):
 started=time.monotonic();fpath=STAGES/'stage011_freeze.json';f=load(fpath);newreg=load(LINE/'outputs/stage011_multistart/registry.json');oldreg=load(f['baseline_registry']);starts=f['starts'];wanted={(s,v) for s in starts for v in ['A_old','A_new','C_old','C_new']}
 ok(newreg['freeze_sha256']==sha(fpath) and len(newreg['jobs'])==46 and newreg['financial_replays_started']==46,'exact46_new_financial_replays');ok(all(j['status']=='validated' for j in newreg['jobs'].values()),'all_new_validated')
 ok(sha(f['baseline_delivery_manifest'])==f['baseline_delivery_manifest_sha256']=='b4712560c72548106fb9e4273895e1bfc80c56a6813cdfe3d71b4190b5d5a424','old_control_final_manifest')
 manifest=load(report/'data_manifest.json')['files_sha256']
 for name,h in manifest.items():ok(sha(name)==h,'report_projection_hash:'+name)
 metadata=load(report/'comparison.json');ok(metadata['promotion_decision']=='NO_PROMOTION' and metadata['financial_replays']==46 and metadata['reused_baseline_financial_replays']==46,'report_no_promotion_scope')
 for name,h in metadata['source_files_sha256'].items():ok(sha(name)==h,'report_input_hash:'+name)
 summary=pd.read_csv(report/'summary.csv',float_precision='round_trip');daily=pd.read_csv(report/'daily.csv',float_precision='round_trip');paired=pd.read_csv(report/'paired.csv',float_precision='round_trip');cohorts=pd.read_csv(report/'cohort_summary.csv');reported_events=pd.read_csv(report/'reserve_events.csv',float_precision='round_trip');deltas=pd.read_csv(report/'actual_parameter_deltas.csv',float_precision='round_trip')
 ok(len(summary)==92 and not summary.duplicated(['start','variant']).any() and set(zip(summary.start,summary.variant))==wanted,'exact92_summaries');ok(len(daily)==141996 and not daily.duplicated(['start','variant','date']).any() and set(zip(daily.start,daily.variant))==wanted,'exact141996_daily');ok(len(paired)==46 and not paired.duplicated(['start','arm']).any(),'exact46_pairs')
 si=summary.set_index(['start','variant']);di={(s,v):g for (s,v),g in daily.groupby(['start','variant'],sort=False)};expected={};receipts={};source_bindings={};new_checks=0;flowchecks=0;parameterchecks=0;events_expected=0
 mapping=pd.read_csv(Path(f['data_directory'])/'mapping.csv',usecols=['date']);calendar=sorted(set(mapping.date))
 for start,variant in sorted(wanted):
  arm=variant[0];isnew=variant.endswith('_new');job=(newreg if isnew else oldreg)['jobs'][start+'|'+arm];path=Path(job['path']);receiptpath=STAGES/('stage011_independent_receipts' if isnew else 'stage009_independent_receipts')/f'{start}_{arm}.json';receipt=load(receiptpath);receipts[str(receiptpath)]=sha(receiptpath)
  ok(receipt['status']=='PASS_WITH_LIMITATIONS' and all(receipt[k]==0 for k in ['P0','P1','P2','failures']) and receipt['path']==str(path),'accepted_independent_window')
  if isnew:
   ok(receipt['freeze_sha256']==sha(fpath) and receipt['frozen_source_head']==f['source_head'],'new_receipt_source_identity');new_checks+=receipt['raw_core_checks'];flowchecks+=receipt['funding_checks'];parameterchecks+=receipt['stage011_checks'];ok(receipt['stage011_parameter_review']['actual_entry_base_rates']==[.018],'actual_all_rates0018')
  for name in ['daily.csv','reserve_daily.csv','reserve_events.json','actual_strategy_settings.json','effective_parameters.json','entry_risk.csv']:
   q=path/name;h=sha(q);ok(h==job['files_sha256'][str(q)]==receipt['source_files_sha256'][str(q)],'real_ledger_receipt_hash:'+str(q));source_bindings[str(q)]=h
  raw=pd.read_csv(path/'daily.csv',float_precision='round_trip');bridge=pd.read_csv(path/'reserve_daily.csv',float_precision='round_trip');events=load(path/'reserve_events.json');actual=load(path/'actual_strategy_settings.json')[0]['actual'];pr=di[(start,variant)];m=si.loc[(start,variant)];days=raw.date.astype(str).str[:10].tolist();ok(days==[d for d in calendar if start<=d<=f['cutoff']],'real_interior_exchange_calendar');ok(days==pr.date.tolist()==bridge.date.astype(str).str[:10].tolist(),'reported_real_calendar')
  cum=raw.net_pnl.cumsum().to_numpy();amounts={}
  for e in events:amounts[str(e['date'])[:10]]=amounts.get(str(e['date'])[:10],0.)+float(e['transfer_amount'])
  flow=np.array([amounts.get(d,0.) for d in days]);T=flow.cumsum();E=150000.+cum+T;R=150000.-T;W=300000.+cum;near(raw.account_equity.to_numpy(),150000.+cum,'raw150k_truePnL');ok((R>=-1e-6).all() and (flow>=0).all(),'bounded_monotone_transfers')
  arrays={'raw_account_equity':150000.+cum,'net_pnl':raw.net_pnl.to_numpy(),'trading_account_equity':E,'reserve_balance':R,'cumulative_transfer':T,'transfer_amount':flow,'total_account_equity':W,'slippage':raw.slippage.to_numpy(),'commission':raw.commission.to_numpy(),'trade_count':raw.trade_count.to_numpy(),'total_margin_exact':raw.total_margin_exact.to_numpy(),'account_nav':E/150000.,'balance_drawdown_pct':(E/np.maximum.accumulate(np.r_[150000.,E])[1:]-1)*100,'wealth_nav':W/300000.,'wealth_drawdown_pct':(W/np.maximum.accumulate(np.r_[300000.,W])[1:]-1)*100}
  for name,a in arrays.items():ok(np.allclose(pr[name],a,rtol=1e-10,atol=1e-6),'all_reported_daily:'+name)
  for name,a in arrays.items():
   if name in bridge:ok(np.allclose(bridge[name],a,rtol=1e-10,atol=1e-6),'real_bridge_daily:'+name)
  eend,egrowth,edd,esharp,edef=curve(E,150000.,True);wend,wgrowth,wdd,wsharp,wdef=curve(W,300000.,False);ratios=np.divide(raw.total_margin_exact.to_numpy()*165.,E,out=np.full_like(E,np.nan),where=E>0);exhaust=R<=1e-6
  fields=dict(initial_trading_capital=150000.,account_end_equity=eend,account_growth_pct=egrowth,balance_max_dd_pct=edd,balance_sharpe=esharp,balance_returns_defined=edef,real_trading_net_pnl=float(cum[-1]),total_transferred=float(T[-1]),off_account_reserve_end=float(R[-1]),total_slippage=float(raw.slippage.sum()),total_commission=float(raw.commission.sum()),modeled_fill_count=int(raw.trade_count.sum()),transfer_event_days=int((flow>0).sum()),nonpositive_trading_equity_days=int((E<=0).sum()),trading_days=len(days),wealth_end_equity=wend,wealth_return_pct=wgrowth,wealth_max_dd_pct=wdd,wealth_sharpe=wsharp,wealth_returns_defined=wdef,nonpositive_total_equity_days=int((W<=0).sum()),transfer_event_count=len(events),reserve_exhausted=bool(exhaust.any()),trading_margin_peak_pct=float(np.nanmax(ratios)) if np.isfinite(ratios).any() else None,trading_margin_over100_days=int((ratios>100).sum()),open_round_net_mtm=receipt['metrics']['open_round_net_mtm'])
  for name,value in receipt['metrics']['rounds'].items():fields['round_'+name]=value
  for name,value in fields.items():near(value,m[name],'independent_summary:'+name)
  ok(m.actual_start==days[0] and m.actual_end==days[-1] and bool(m.observation_only)==(start=='2026-01-01'),'summary_dates_observation')
  exhaustion_date='' if pd.isna(m.exhaustion_date) else str(m.exhaustion_date)
  ok(exhaustion_date==('' if not exhaust.any() else days[int(np.flatnonzero(exhaust)[0])]),'summary_exact_exhaustion_date')
  near(fields['round_closed_net_pnl']+fields['open_round_net_mtm'],cum[-1],'closed_open_truePnL_again');near(E[-1]-150000.,cum[-1]+T[-1],'cashflow_not_alpha');near(fields['total_commission'],0.,'zero_commission_explicit')
  ev=reported_events.loc[reported_events.start.eq(start)&reported_events.variant.eq(variant)];ok(len(ev)==len(events),'event_count_projection');events_expected+=len(events)
  for a,b in zip(events,ev.to_dict('records')):
   for name in ['candidate_key','date','signal','direction','entry_context']:ok(str(a[name])==str(b[name]),'event_identity:'+name)
   for name in ['transfer_amount','trading_equity_before','trading_equity_after','reserve_before','reserve_after','cumulative_transfer']:near(a[name],b[name],'event_value:'+name)
  expected[(start,variant)]=fields
 ok(len(reported_events)==events_expected and len(deltas)==138,'all_event_and_parameter_delta_rows')
 deltafields={'delta_account_growth_pp':'account_growth_pct','delta_balance_max_dd_pp':'balance_max_dd_pct','delta_balance_sharpe':'balance_sharpe','delta_real_trading_net_pnl':'real_trading_net_pnl','delta_account_end_equity':'account_end_equity','delta_deposits':'total_transferred','delta_wealth_return_pp':'wealth_return_pct','delta_wealth_max_dd_pp':'wealth_max_dd_pct','delta_wealth_sharpe':'wealth_sharpe'}
 for r in paired.itertuples():
  old=expected[(r.start,r.arm+'_old')];new=expected[(r.start,r.arm+'_new')]
  for name,key in deltafields.items():near(new[key]-old[key],getattr(r,name),'paired_delta:'+name)
  gates=dict(real_pnl_gate=compare(new['real_trading_net_pnl'],old['real_trading_net_pnl'])>0,wealth_dd_gate=compare(new['wealth_max_dd_pct'],old['wealth_max_dd_pct'])>=0,wealth_sharpe_gate=compare(new['wealth_sharpe'],old['wealth_sharpe'])>=0)
  for name,v in gates.items():ok(bool(getattr(r,name))==v,'independent_economic_gate:'+name)
  ok(bool(r.three_gate_pass)==all(gates.values()),'independent_joint_gate');near(r.delta_account_end_equity,r.delta_real_trading_net_pnl+r.delta_deposits,'paired_deposit_PnL_bridge')
  for name,oldvalue in {'risk_ratio_volume_open_interest_surge':.06,'risk_ratio_open_interest_surge':.06,'risk_ratio_open_interest_decline':.025}.items():
   q=deltas.loc[deltas.start.eq(r.start)&deltas.arm.eq(r.arm)&deltas.parameter.eq(name)];ok(len(q)==1,'unique_parameter_delta');near(q.old.iloc[0],oldvalue,'old_risk_delta');near(q.new.iloc[0],.018,'new_risk_delta')
 ok(len(cohorts)==12 and not cohorts.duplicated(['arm','cohort','scope']).any(),'exact12_cohorts')
 for row in cohorts.itertuples():
  q=paired.loc[paired.arm.eq(row.arm)&paired.observation_only.eq(row.scope=='observation_lt_1y')]
  if row.cohort!='combined':q=q.loc[q.cohort.eq(row.cohort)]
  fields=dict(n=len(q),real_pnl_wins=int(q.real_pnl_gate.sum()),wealth_dd_no_worse=int(q.wealth_dd_gate.sum()),wealth_sharpe_no_lower=int(q.wealth_sharpe_gate.sum()),three_gate_pass=int(q.three_gate_pass.sum()),lower_deposit_windows=int((q.delta_deposits< -1e-6).sum()),equal_deposit_windows=int((q.delta_deposits.abs()<=1e-6).sum()),higher_deposit_windows=int((q.delta_deposits>1e-6).sum()))
  for name,value in fields.items():near(value,getattr(row,name),'cohort_recount:'+name)
 for name,h in manifest.items():ok(sha(name)==h,'immutable_projection_after_review')
 codes=[LINE/'tools'/n for n in ['stage011_report.py','stage011_plots.py','stage009_accounting.py','stage010_account_nav.py','stage011_independent_window.py','stage009_independent_window.py','stage008_independent_window.py']]
 result=dict(schema='stage011_independent_numeric_review_v1',status='PASS_WITH_LIMITATIONS',accepted=True,P0=0,P1=0,P2=0,failures=0,freeze_sha256=sha(fpath),financial_source_head=f['source_head'],summary_rows=92,paired_rows=46,daily_points=141996,independent_starts=23,complete_pairs_per_arm=22,observation_pairs_per_arm=1,checks=checks,raw_core_checks=new_checks,funding_checks=flowchecks,parameter_checks=parameterchecks,data_files_sha256=manifest,audited_code_sha256={str(p):sha(p) for p in codes},window_receipts_sha256=receipts,selected_ledger_files_sha256=source_bindings,cohort_summary=cohorts.to_dict('records'),financial_replays=0,market_downloads=0,production_accesses=0,promotion_decision='NO_PROMOTION',confidence='High confidence in fixed-ledger accounting, declared parameter delta and internal next-open causality; limited economic generalization due to repeated overlapping historical windows, incomplete PIT/cost/margin/capacity evidence.',limitations=load(STAGES/'stage009_data_preflight.json')['limitations'],seconds=time.monotonic()-started,auditor_source_sha256=sha(__file__))
 output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['status','checks','raw_core_checks','funding_checks','parameter_checks','summary_rows','paired_rows','daily_points','seconds']},ensure_ascii=False));return result
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--report',type=Path,default=LINE/'artifacts/stage011_uniform_risk_comparison');ap.add_argument('--output',type=Path,default=STAGES/'stage011_independent_numeric_review.json');args=ap.parse_args()
 if args.output.exists():raise ValueError('immutable_numeric_review_exists')
 audit(args.report,args.output)
if __name__=='__main__':main()
