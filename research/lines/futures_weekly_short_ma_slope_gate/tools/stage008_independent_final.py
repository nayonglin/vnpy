"""Independent final whole-report review. Generate JSON once, then lock its SHA."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,math
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[4];L=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';S=L/'stages';R=L/'artifacts/stage008_multistart';checks=0;cache={}
def sha(p):
 p=Path(p)
 if str(p) not in cache:
  h=hashlib.sha256()
  with p.open('rb') as f:
   for b in iter(lambda:f.read(8388608),b''):h.update(b)
  cache[str(p)]=h.hexdigest()
 return cache[str(p)]
def ok(v,label):
 global checks;checks+=1
 if not v:raise AssertionError(label)
def equal(a,b):return math.isfinite(float(a)) and math.isfinite(float(b)) and math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-7)
def near(a,b,label):ok(equal(a,b),label)
def nullable(a,b,label):
 if b is None or pd.isna(b):ok(a is None or pd.isna(a),label)
 else:near(a,b,label)
def cmp(a,b):return 0 if equal(a,b) else (1 if a>b else -1)
def main():
 out=S/'stage008_independent_final.json'
 if out.exists():raise ValueError('immutable_final_json_exists')
 aggpath=S/'stage008_independent_aggregate.json';agg=json.loads(aggpath.read_text());ok(agg['status']=='PASS_ALL46_ACCOUNTING_AND_SOURCE_WITH_LIMITATIONS' and agg['failures']==0,'full_independent_aggregate');fpath=S/'stage008_freeze.json';f=json.loads(fpath.read_text());doc=json.loads((R/'comparison.json').read_text());summary=pd.read_csv(R/'summary.csv');paired=pd.read_csv(R/'paired.csv');cohorts=pd.read_csv(R/'cohort_summary.csv');weakest=pd.read_csv(R/'weakest_windows.csv');curve=pd.read_csv(R/'all_daily.csv');annual=pd.read_csv(R/'annual.csv')
 ok(doc['freeze_sha256']==agg['freeze_sha256']==sha(fpath) and doc['financial_source_head']==f['source_head'],'report_freeze');ok(doc['arm_windows']==46 and doc['independent_pairs']==23 and doc['complete_vote_pairs']==22 and doc['observation_pairs']==1 and doc['expected_engine_replays']==42 and doc['reused_arms']==4,'report_scope')
 for p,h in {**doc['source_files_sha256'],**doc['output_files_sha256']}.items():ok(Path(p).is_file() and sha(p)==h,'report_binding:'+p)
 manifest=json.loads((R/'delivery_manifest.json').read_text())
 for p,h in manifest['files_sha256'].items():ok((R/p).is_file() and sha(R/p)==h,'report_delivery:'+p)
 starts=f['starts'];expected={(s,a) for s in starts for a in ['A','C']};ok(len(summary)==46 and set(zip(summary.start,summary.arm))==expected and not summary.duplicated(['start','arm']).any(),'unique46_summary');ok(len(paired)==23 and paired.start.tolist()==starts,'unique23_pairs');ok(len(cohorts)==6 and len(weakest)==30,'six_cohorts_thirty_weakest')
 receipts={};raw={};expected_pairs={};curvepoints=0;annualrows=0
 for start in starts:
  for arm in ['A','C']:
   key=start+'|'+arm;rp=S/f'stage008_independent_receipts/{start}_{arm}.json';r=json.loads(rp.read_text());receipts[key]=r;ok(sha(rp)==agg['receipt_sha256'][str(rp)],'frozen_independent_receipt:'+key);row=summary.loc[summary.start.eq(start)&summary.arm.eq(arm)].iloc[0];m=r['metrics'];path=Path(r['path']);d=pd.read_csv(path/'daily.csv');raw[key]=d;curvepoints+=len(d)
   for k in ['end_equity','total_return_pct','max_dd_pct','sharpe','total_slippage','open_round_net_mtm']:near(row[k],m[k],key+' metric '+k)
   near(row.modeled_fill_count,m['total_trade_count'],key+' fills');near(row.nav_end,m['end_equity']/150000,key+' endNAV')
   for reportkey,indkey in [('round_count','count'),('round_wins','wins'),('round_losses','losses'),('round_flat','flat'),('round_win_rate_pct','win_rate_pct'),('round_average_win','average_win'),('round_average_loss_abs','average_loss_abs'),('round_payoff_ratio','payoff_ratio'),('round_profit_factor','profit_factor'),('round_closed_net_pnl','closed_net_pnl')]:nullable(row[reportkey],m['rounds'][indkey],key+' '+reportkey)
   near(row.actual_margin_to_equity_max_pct,r['risk']['configured_margin_max_pct'],key+' actualmargin');near(row.actual_margin_over100_days,r['risk']['configured_margin_over100_days'],key+' margindays');ok(bool(row.survival_pass)==r['risk']['positive_equity_all_days'],key+' survival');ok(bool(row.configured_margin_pass)==(r['risk']['configured_margin_over100_days']==0 and r['risk']['positive_equity_all_days']),key+' marginpass')
   q=curve.loc[curve.start.eq(start)&curve.arm.eq(arm)].reset_index(drop=True);ok(q.date.equals(d.date),key+' daily_dates');ok(len(q)==len(d),key+' daily_count')
   for k in ['account_equity','net_pnl','slippage','commission','trade_count']:ok(np.allclose(q[k],d[k],rtol=1e-10,atol=1e-7),key+' full_'+k)
   e=d.account_equity.to_numpy();nav=e/150000;dd=100*(e/np.maximum.accumulate(np.r_[150000,e])[1:]-1);ok(np.allclose(q.nav,nav,rtol=1e-12,atol=1e-12),key+' allNAV');ok(np.allclose(q.drawdown_pct,dd,rtol=1e-12,atol=1e-12),key+' allDD')
   cachepath=L/f"outputs/stage008_derived/cache/{start.replace('-','')}_{arm}";cached=json.loads((cachepath/'ledger.json').read_text());ok(cached['attempt_snapshot']==r['source_files_sha256'],key+' cache_exact_original_snapshot')
   for p,h in cached['derivation_sources_sha256'].items():ok(Path(p).is_file() and sha(p)==h,'cache_derivation:'+p)
   prior=150000.
   for year,g in d.groupby(d.date.astype(str).str[:4],sort=True):
    rows=annual.loc[annual.start.eq(start)&annual.arm.eq(arm)&annual.year.eq(int(year))];ok(len(rows)==1,key+' annual_unique'+year);a=rows.iloc[0];annualrows+=1
    for n,left,right in [('initial',a.initial_capital,prior),('end',a.end_equity,g.account_equity.iloc[-1]),('pnl',a.net_pnl,g.net_pnl.sum()),('return',a.total_return_pct,(g.account_equity.iloc[-1]/prior-1)*100),('slip',a.total_slippage,g.slippage.sum()),('fills',a.modeled_fill_count,g.trade_count.sum())]:near(left,right,key+' annual_'+year+n)
    prior=float(g.account_equity.iloc[-1])
  a=receipts[start+'|A']['metrics'];c=receipts[start+'|C']['metrics'];p=paired.loc[paired.start.eq(start)].iloc[0];voting=pd.Timestamp(f['cutoff'])>=pd.Timestamp(start)+pd.DateOffset(years=1);comparison={k:cmp(c[k],a[k]) for k in ['end_equity','max_dd_pct','sharpe']};gates=[comparison['end_equity']>0,comparison['max_dd_pct']>=0,comparison['sharpe']>=0];ok(bool(p.vote_eligible)==voting and bool(p.observation_only)==(not voting),'eligibility:'+start)
  for n,want in [('return_comparison',comparison['end_equity']),('dd_comparison',comparison['max_dd_pct']),('sharpe_comparison',comparison['sharpe'])]:near(p[n],want,'comparison:'+start+n)
  for n,want in zip(['equity_gate','dd_gate','sharpe_gate','three_gate_pass'],gates+[all(gates)]):ok(bool(p[n])==want,'gate:'+start+n)
  for k in ['end_equity','total_return_pct','max_dd_pct','sharpe']:near(p['delta_'+k],c[k]-a[k],'delta:'+start+k)
  expected_pairs[start]=dict(comparison=comparison,gates=gates,voting=voting)
 ok(curvepoints==len(curve)==agg['actual_total_daily_NAV_DD_points']==doc['total_daily_points']==70998,'all70998_points');ok(annualrows==len(annual),'all_annual_slices')
 for name in ['January','June','combined']:
  for sample,mature in [('complete_ge_1y',True),('observation_lt_1y',False)]:
   prow=paired.loc[paired.vote_eligible.eq(mature)&(True if name=='combined' else paired.cohort.eq(name))];selected=summary.loc[summary.start.isin(prow.start)];row=cohorts.loc[cohorts.cohort.eq(name)&cohorts['sample'].eq(sample)].iloc[0];n=len(prow);voters=n if mature else 0
   vals=dict(windows=n,vote_windows=voters,observation_windows=0 if mature else n,return_wins=int(prow.return_comparison.gt(0).sum()) if mature else 0,return_ties=int(prow.return_comparison.eq(0).sum()) if mature else 0,return_losses=int(prow.return_comparison.lt(0).sum()) if mature else 0,dd_wins=int(prow.dd_comparison.gt(0).sum()) if mature else 0,sharpe_wins=int(prow.sharpe_comparison.gt(0).sum()) if mature else 0,three_gate_pass_count=int(prow.three_gate_pass.sum()) if mature else 0)
   for k,v in vals.items():near(row[k],v,'cohort:'+name+sample+k)
   for k in ['return_wins','dd_wins','sharpe_wins','three_gate_pass_count']:nullable(row[k+'_rate_pct'],vals[k]/voters*100 if voters else None,'rate:'+name+sample+k)
   for arm in ['A','C']:
    q=selected.loc[selected.arm.eq(arm)];v={arm+'_negative_return_count':int(q.total_return_pct.lt(0).sum()),arm+'_positive_return_count':int(q.total_return_pct.gt(0).sum()),arm+'_flat_return_count':int(q.total_return_pct.eq(0).sum()),arm+'_survival_failure_count':int((~q.survival_pass).sum()),arm+'_configured_margin_failure_count':int((~q.configured_margin_pass).sum()),arm+'_configured_margin_unknown_count':int(q.configured_margin_unknown.sum()),arm+'_median_dd_pct':q.max_dd_pct.median() if len(q) else None,arm+'_worst_dd_pct':q.max_dd_pct.min() if len(q) else None,arm+'_median_sharpe':q.sharpe.median() if len(q) else None,arm+'_worst_sharpe':q.sharpe.min() if len(q) else None,arm+'_minimum_total_return_pct':q.total_return_pct.min() if len(q) else None}
    for k,want in v.items():nullable(row[k],want,'cohort_risk_distribution:'+name+sample+k)
 for scope,mask in [('complete_ge_1y',summary.vote_eligible),('observation_lt_1y',~summary.vote_eligible),('all_displayed',pd.Series(True,index=summary.index))]:
  for arm in ['A','C']:
   q=summary.loc[mask&summary.arm.eq(arm)]
   for metric,asc in [('total_return_pct',True),('max_dd_pct',True),('sharpe',True),('total_slippage',False),('actual_margin_to_equity_max_pct',False)]:
    expected=q.sort_values([metric,'start'],ascending=[asc,True]).iloc[0];actual=weakest.loc[weakest.scope.eq(scope)&weakest.arm.eq(arm)&weakest.metric.eq(metric)].iloc[0];ok(actual.start==expected.start,'weakest:'+scope+arm+metric);near(actual.value,expected[metric],'weakestvalue:'+scope+arm+metric)
 names=['01_full_2015_nav_drawdown.png','02_january_starts_nav.png','03_june_starts_nav.png','04_start_to_cutoff_heatmaps.png','05_cohort_summary_weakest.png'];ok(doc['five_figures']==names and all((R/n).is_file() for n in names),'five_exact_user_scope_figures');ok(doc['promotion_decision']=='NO_PROMOTION','no_promotion');decision=json.loads((R/'decision.json').read_text());combined=cohorts.loc[cohorts.cohort.eq('combined')&cohorts['sample'].eq('complete_ge_1y')].iloc[0];ok(decision['return_win_count']==combined.return_wins and decision['three_gate_pass_count']==combined.three_gate_pass_count and decision['C_negative_complete_windows']==combined.C_negative_return_count and decision['C_survival_failure_count']==combined.C_survival_failure_count and decision['C_configured_margin_failure_count']==combined.C_configured_margin_failure_count,'decision_statistics')
 expectedverdict='PASS_USER_SCOPE_COMPLETE_WINDOWS_ONLY' if combined.three_gate_pass_count==22 and combined.C_negative_return_count==combined.C_survival_failure_count==combined.C_configured_margin_failure_count==0 else 'MIXED_OR_FAIL_NO_RESCUE_TUNING';ok(doc['strategy_verdict']==decision['strategy_verdict']==expectedverdict,'unrescued_verdict')
 warmuppath=S/'stage008_independent_warmup_final.json';warm=json.loads(warmuppath.read_text());ok(warm['status']=='PASS_ACTUAL_NATIVE21_COMPLETED_WEEK_READINESS' and warm['window_count']==46 and not warm['failures'],'full46_warmup');adapterpath=S/'stage008_independent_accounting_adapter.json';adapter=json.loads(adapterpath.read_text());ok(adapter['all_other_financial_AST_exactly_preserved'] is True,'frozen_pure_accounting_AST')
 for p,h in adapter['reviewed_code_sha256'].items():ok(Path(p).is_file() and sha(p)==h,'accounting_adapter_code:'+p)
 testlog=S/'stage008_independent_final_tests_v3.log';text=testlog.read_text();ok('Ran 46 tests' in text and text.strip().endswith('OK'),'46_independent_tests_passed')
 codes=[L/'tools/stage008_report.py',L/'tools/test_stage008_report.py',L/'tools/stage008_reviewed_visual.py',L/'tools/test_stage008_reviewed_visual.py',L/'tools/stage008_finalize.py',L/'tools/test_stage008_finalize.py',L/'tools/stage008_accounting.py',L/'tools/test_stage008_accounting.py',L/'tools/stage001_report.py',L/'tools/stage006_report.py',ROOT/'research/lines/futures_weekly_formal_no_half_r/tools/stage029_build_artifacts.py',L/'tools/stage005_short_bottom20.py',L/'tools/stage008_independent_window.py',L/'tools/stage008_independent_stream.py',L/'tools/stage008_independent_stream_v2.py',L/'tools/stage008_independent_aggregate.py',L/'tools/stage008_independent_warmup.py',Path(__file__)]
 r=dict(status='PASS_WITH_LIMITATIONS',P0=0,P1=0,P2=0,failures=0,reviewed_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),freeze_sha256=sha(fpath),financial_source_head=f['source_head'],arm_windows=46,paired_windows=23,new_engine_replays=42,reused_arms=4,complete_voting_pairs=22,observation_pairs=['2026-01-01'],core_checks_total=agg['core_checks_total'],aggregate_integrity_checks=agg['aggregate_integrity_checks'],report_checks=checks,daily_NAV_DD_points_checked=curvepoints,annual_continuous_slices_checked=annualrows,actual_native_ready21_checks=warm['actual_native_fills_checked'],independent_tests_passed=46,cohort_summary=cohorts.astype(object).where(pd.notna(cohorts),None).to_dict('records'),worst_complete_windows=agg['worst_complete_windows'],strategy_verdict=expectedverdict,promotion_decision='NO_PROMOTION',production_qualified=False,aggregate_proof_sha256=sha(aggpath),warmup_proof_sha256=sha(warmuppath),pure_accounting_adapter_proof_sha256=sha(adapterpath),report_comparison_sha256=sha(R/'comparison.json'),report_delivery_manifest_sha256=sha(R/'delivery_manifest.json'),pending_figure_sha256={str(R/n):sha(R/n) for n in names},reviewed_code_sha256={str(p):sha(p) for p in codes},test_log_sha256=sha(testlog),financial_replays_by_reviewer=0,market_downloads=0,production_accesses=0,limitations=['23 overlapping fresh-start accounts are descriptive start sensitivity, not23 independent samples or new OOS.','Original19 fixed universe, zero commission/static slippage and static margin x1.65 do not prove historical broker margin/liquidity/capacity or production readiness.','All available same-epoch cached daily history includes signal day for short rule but is not proven complete listing/PIT/lifecycle history.','Whole-account paired differences contain dynamic capital/integer-lot/risk and opportunity feedback, not direct alpha of blocked candidates.','2026Jan under1year is displayed but has0 votes. Five figures follow user start-to-now scope, not unperformed fixed1/2/3-year tests.'])
 out.write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(json.dumps({k:v for k,v in r.items() if k not in ['cohort_summary','reviewed_code_sha256','pending_figure_sha256']},ensure_ascii=False))
if __name__=='__main__':main()
