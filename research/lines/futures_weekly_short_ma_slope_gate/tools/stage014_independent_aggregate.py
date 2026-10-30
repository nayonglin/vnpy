"""Independent59-curve/12-cohort saved-ledger review. No report/engine imports."""
from pathlib import Path
import argparse,hashlib,json,math,time
import numpy as np
import pandas as pd
from stage014_independent_scope import canonical_starts,mature,scope
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';STAGES=LINE/'stages';checks=0
load=lambda p:json.loads(Path(p).read_text())
def nullable_records(rows):
 return [{k:(None if isinstance(v,float) and not math.isfinite(v) else v) for k,v in row.items()} for row in rows]
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def ok(v,label):
 global checks
 checks+=1
 if not v:raise AssertionError(label)
def near(a,b,label):
 if np.ndim(a)==0 and (a is None or pd.isna(a)):ok(np.ndim(b)==0 and (b is None or pd.isna(b)),label);return
 ok(np.allclose(a,b,rtol=1e-10,atol=1e-6,equal_nan=False),label)
def account(E):
 E=np.asarray(E,float);prev=np.r_[150000.,E[:-1]];defined=bool(np.isfinite(E).all() and (prev>0).all());returns=(E-prev)/prev if defined else None;defined=defined and bool(np.isfinite(returns).all());std=float(returns.std(ddof=1)) if defined and len(returns)>1 else 0.
 return dict(initial_trading_capital=150000.,account_end_equity=E[-1],account_growth_pct=(E[-1]/150000.-1)*100,balance_max_dd_pct=float((E/np.maximum.accumulate(np.r_[150000.,E])[1:]-1).min()*100),balance_sharpe=float(returns.mean()/std*np.sqrt(252)) if defined and std>0 else 0.,balance_returns_defined=defined,nonpositive_trading_equity_days=int((E<=0).sum()))
def audit(folder,output):
 started=time.monotonic();fp=STAGES/'stage014_freeze.json';f=load(fp);sc=scope(f);reg=load(LINE/'outputs/stage014_multistart/registry.json');starts=canonical_starts();ok(reg['source_head']==f['source_head'] and reg['freeze_sha256']==sha(fp),'registry_frozen_identity');ok(set(reg['jobs'])=={s+'|C' for s in starts} and all(j['status']=='validated' and j['method']=='fresh_engine' and j['reused'] is False for j in reg['jobs'].values()),'59_new_independent_engines_only');ok(reg['financial_replays_started']==59 and reg['financial_engine_batch_complete'] is True,'engine_batch_complete_no_reuse')
 manifest=load(folder/'data_manifest.json')['files_sha256'];meta=load(folder/'comparison.json');sources=load(folder/'source_manifest.json')['source_files_sha256'];ok(meta['source_files_sha256']==sources,'same_source_graph');ok(meta['source_head']==f['source_head'] and meta['freeze_sha256']==sha(fp) and meta['months']==f['start_months'],'report_frozen_code_and_month_grid');ok(meta['financial_replays']==59 and meta['reused_candidates']==0 and meta['mature_windows']==54 and meta['observation_windows']==5 and meta['cutoff']==f['cutoff'] and meta['starts']==starts and meta['promotion_decision']=='NO_PROMOTION','declared_59_scope_and_limits')
 for p,h in {**manifest,**sources}.items():ok(sha(p)==h,'actual_source_SHA:'+p)
 s=pd.read_csv(folder/'summary.csv',float_precision='round_trip');d=pd.read_csv(folder/'daily.csv',float_precision='round_trip');coh=pd.read_csv(folder/'cohort_summary.csv',float_precision='round_trip');ev=pd.read_csv(folder/'reserve_events.csv',float_precision='round_trip');ok(len(s)==59 and not s.start.duplicated().any() and set(s.start)==set(starts),'59summary_no_selection');ok(len(d)==86049 and not d.duplicated(['start','date']).any() and set(d.start)==set(starts),'86049daily_no_selection');ok(s.variant.eq('C_R150').all() and d.variant.eq('C_R150').all(),'one_arm_original_C_R150');ok(not (folder/'paired.csv').exists(),'no_fabricated_pair_comparison')
 calendar=sorted(set(pd.read_csv(Path(f['data_directory'])/'mapping.csv',usecols=['date']).date));declared_calendar=load(folder/'calendar.json');ok(declared_calendar['mapping_sha256']==f['data_identity']['mapping_sha256'],'calendar_new_data_SHA');si=s.set_index('start');dg={a:g for a,g in d.groupby('start',sort=False)};receiptmap={};selected={};expected={};rawchecks=fundingchecks=stagechecks=entries=0;events_total=0
 for start in starts:
  j=reg['jobs'][start+'|C'];path=Path(j['path']);rp=STAGES/'stage014_independent_receipts'/f'{start}_C.json';r=load(rp);cp=load(j['checkpoint']);ok(r['status']=='PASS_WITH_LIMITATIONS' and all(r[k]==0 for k in ['P0','P1','P2','failures']) and r['method']=='fresh_engine' and r['reused'] is False and r['freeze_sha256']==sha(fp) and r['frozen_source_head']==f['source_head'],'independent_receipt_exact_identity');ok(r['path']==str(path) and r['requested_start']==start and r['source_files_sha256']==cp['files_sha256']==j['files_sha256'],'complete_output_receipt_checkpoint_binding');ok(r['checkpoint_sha256']==sha(j['checkpoint'])==sources[str(Path(j['checkpoint']).resolve())],'checkpoint_in_report_graph');receiptmap[str(rp)]=sha(rp);rawchecks+=r['raw_core_checks'];fundingchecks+=r['funding_checks'];stagechecks+=r['stage014_checks'];entries+=r['stage014_parameter_review']['entry_rows']
  ok(r['stage014_parameter_review']['all_actual_settings_unchanged_except_declared_start_and_mapping'] and r['stage014_parameter_review']['all_effective_parameters_unchanged_except_declared_start_and_mapping'],'original_complete_actual_settings')
  for name in ['daily.csv','reserve_daily.csv','reserve_events.json','actual_strategy_settings.json','effective_parameters.json','entry_risk.csv']:
   q=path/name;h=sha(q);ok(h==j['files_sha256'][str(q)]==r['source_files_sha256'][str(q)]==sources[str(q)],'selected_ledger_hash:'+name);selected[str(q)]=h
  raw=pd.read_csv(path/'daily.csv',float_precision='round_trip');bridge=pd.read_csv(path/'reserve_daily.csv',float_precision='round_trip');events=load(path/'reserve_events.json');row=si.loc[start];p=dg[start];days=raw.date.astype(str).str[:10].tolist();ok(days==[v for v in calendar if start<=v<=f['cutoff']]==p.date.tolist()==bridge.date.astype(str).str[:10].tolist()==declared_calendar['dates_by_start'][start],'every_actual_exchange_date_exact');byday={}
  for e in events:byday[str(e['date'])[:10]]=byday.get(str(e['date'])[:10],0.)+float(e['transfer_amount'])
  flow=np.array([byday.get(day,0.) for day in days]);T=flow.cumsum();PnL=raw.net_pnl.cumsum().to_numpy();E=150000.+PnL+T;R=150000.-T;W=300000.+PnL;near(raw.account_equity,150000.+PnL,'raw_not_funding_profit');near(E+R,W,'all_days_true_wealth_identity');ok((R>=-1e-6).all() and (R<=150000.+1e-6).all() and (flow>=0).all(),'permanent_reserve_never_replenished_or_overdrawn')
  arrays=dict(raw_account_equity=150000.+PnL,net_pnl=raw.net_pnl.to_numpy(),trading_account_equity=E,reserve_balance=R,cumulative_transfer=T,transfer_amount=flow,total_account_equity=W,slippage=raw.slippage.to_numpy(),commission=raw.commission.to_numpy(),trade_count=raw.trade_count.to_numpy(),total_margin_exact=raw.total_margin_exact.to_numpy(),account_nav=E/150000.,balance_drawdown_pct=(E/np.maximum.accumulate(np.r_[150000.,E])[1:]-1)*100)
  for k,v in arrays.items():near(p[k],v,'daily_reconstructed:'+k)
  for k in ['raw_account_equity','net_pnl','trading_account_equity','reserve_balance','cumulative_transfer','transfer_amount','total_account_equity']:near(bridge[k],arrays[k],'true_wallet:'+k)
  margin=np.divide(raw.total_margin_exact.to_numpy()*165.,E,out=np.full_like(E,np.nan),where=E>0);exhaust=R<=1e-6;fields=account(E);fields.update(real_trading_net_pnl=PnL[-1],total_transferred=T[-1],off_account_reserve_end=R[-1],reserve_initial=150000.,total_slippage=raw.slippage.sum(),total_commission=raw.commission.sum(),modeled_fill_count=int(raw.trade_count.sum()),transfer_event_days=int((flow>0).sum()),transfer_event_count=len(events),trading_days=len(days),reserve_exhausted=bool(exhaust.any()),trading_margin_peak_pct=float(np.nanmax(margin)) if np.isfinite(margin).any() else None,trading_margin_over100_days=int((margin>100).sum()),open_round_net_mtm=r['metrics']['open_round_net_mtm']);fields.update({'round_'+k:v for k,v in r['metrics']['rounds'].items()})
  for k,v in fields.items():near(v,row[k],'independent_summary:'+k)
  near(fields['round_closed_net_pnl']+fields['open_round_net_mtm'],PnL[-1],'closed_rounds_plus_open_MTM_real_PnL');near(fields['total_commission'],0.,'frozen_fee_zero');near(E[-1]-150000.,PnL[-1]+T[-1],'deposit_bridge_not_alpha');ok(row.method=='fresh_engine' and row.arm=='C' and row.cohort_month==int(start[5:7]) and bool(row.observation_only)==(not mature(start,f['cutoff'])) and row.actual_start==days[0] and row.actual_end==days[-1],'window_identity_maturity_dates');date='' if pd.isna(row.exhaustion_date) else str(row.exhaustion_date);ok(date==('' if not exhaust.any() else days[int(np.flatnonzero(exhaust)[0])]),'exact_exhaustion_date')
  projected=ev.loc[ev.start.eq(start)];ok(len(projected)==len(events),'all_events_projected');events_total+=len(events)
  for a,b in zip(events,projected.to_dict('records')):
   for k in ['candidate_key','date','direction','signal','entry_context']:ok(str(a[k])==str(b[k]),'event_identity:'+k)
   for k in ['transfer_amount','trading_equity_before','trading_equity_after','reserve_before','reserve_after','cumulative_transfer','raw_account_equity','total_account_equity']:near(a[k],b[k],'actual_event:'+k)
  expected[start]=fields
 ok(events_total==len(ev),'no_extra_cross_window_events');ok(len(coh)==12 and not coh.duplicated(['cohort','scope']).any(),'12_month_total_maturity_cohorts');names={1:'January',3:'March',6:'June',9:'September',11:'November'};ok(set(zip(coh.cohort,coh.scope))=={(name,kind) for name in [*names.values(),'combined'] for kind in ['mature_ge_1y','observation_lt_1y']},'exact_cohort_scope_labels')
 for row in coh.itertuples():
  g=s.loc[s.observation_only.eq(row.scope=='observation_lt_1y')]
  if row.cohort!='combined':g=g.loc[g.cohort_month.eq(next(k for k,v in names.items() if v==row.cohort))]
  nrows=len(g);sh=g.loc[g.balance_returns_defined,'balance_sharpe'];fields=dict(windows=nrows,negative_real_pnl_windows=int((g.real_trading_net_pnl<0).sum()),positive_real_pnl_windows=int((g.real_trading_net_pnl>0).sum()),min_real_pnl=float(g.real_trading_net_pnl.min()) if nrows else None,median_real_pnl=float(g.real_trading_net_pnl.median()) if nrows else None,worst_E_dd_pct=float(g.balance_max_dd_pct.min()) if nrows else None,minimum_defined_E_sharpe=float(sh.min()) if len(sh) else None,undefined_E_sharpe_windows=int((~g.balance_returns_defined).sum()),reserve_exhausted_windows=int(g.reserve_exhausted.sum()),nonpositive_E_windows=int((g.nonpositive_trading_equity_days>0).sum()),margin_pressure_windows=int((g.trading_margin_over100_days>0).sum()),median_deposit=float(g.total_transferred.median()) if nrows else None,maximum_deposit=float(g.total_transferred.max()) if nrows else None)
  for k,v in fields.items():near(v,getattr(row,k),'independent_cohort_recount:'+k)
 for p,h in manifest.items():ok(sha(p)==h,'projection_immutable_after_audit')
 code=[LINE/'tools'/n for n in ['stage014_report.py','stage014_plots.py','test_stage014_report.py','test_stage014_plots.py','stage014_contract.py','stage013_report.py','stage013_plots.py','stage010_account_nav.py','stage011_report.py','stage014_independent_window.py','stage009_independent_window.py','stage008_independent_window.py']]
 result=dict(schema='stage014_independent_numeric_review_v1',status='PASS_WITH_LIMITATIONS',accepted=True,P0=0,P1=0,P2=0,failures=[],freeze_sha256=sha(fp),financial_source_head=f['source_head'],summary_windows=59,daily_points=86049,mature_windows=54,observation_windows=5,cohort_rows=12,new_financial_engine_runs=59,reused_candidates=0,checks=checks,raw_core_checks=rawchecks,funding_checks=fundingchecks,stage014_checks=stagechecks,actual_entry_risk_rows=entries,data_files_sha256=manifest,audited_code_sha256={str(q):sha(q) for q in code},window_receipts_sha256=receiptmap,selected_ledger_files_sha256=selected,cohort_summary=coh.to_dict('records'),undefined_metric_policy='PF/payoff nullable; E Sharpe0 is only a serialized placeholder when returns_defined=false and UI must display N/A; E<=0 not clipped, positive-E margin only.',confidence='High within frozen daily accounting model; overlapping history-selected sampling, no independent OOS, zero fees/PIT/lifecycle/static margin/capacity limits remain.',financial_replays=0,market_downloads=0,production_accesses=0,promotion_decision='NO_PROMOTION',seconds=time.monotonic()-started,auditor_source_sha256=sha(__file__))
 result['cohort_summary']=nullable_records(result['cohort_summary']);output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(json.dumps({k:result[k] for k in ['status','checks','raw_core_checks','funding_checks','stage014_checks','summary_windows','daily_points','seconds']},ensure_ascii=False));return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--report',type=Path,default=LINE/'artifacts/stage014_five_starts_R150');ap.add_argument('--output',type=Path,default=STAGES/'stage014_independent_numeric_review.json');a=ap.parse_args()
 if a.output.exists():raise ValueError('immutable_numeric_review_exists')
 audit(a.report,a.output)
if __name__=='__main__':main()
