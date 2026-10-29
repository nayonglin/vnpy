from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,math
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[4];L=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';R=L/'artifacts/stage004_comparison';checks={}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for c in iter(lambda:f.read(8*1024*1024),b''):h.update(c)
 return h.hexdigest()
def ok(k,v):
 checks[k]=bool(v)
 if not v:raise AssertionError(k)
def near(k,a,b):ok(k,math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-6))
review=json.loads((L/'stages/stage004_independent_results.json').read_text());doc=json.loads((R/'comparison.json').read_text());summary=pd.read_csv(R/'summary.csv');annual=pd.read_csv(R/'annual.csv');curve=pd.read_csv(R/'nav_drawdown.csv');frozen_counts={};old_bound={}
for n in ['stage001_delivery_manifest.json','stage002_delivery_manifest.json','stage003_delivery_manifest.json']:
 d=json.loads((L/'stages'/n).read_text())['files_sha256'];frozen_counts[n]=len(d);old_bound.update(d)
 for p,h in d.items():ok('frozen_'+n+':'+p,Path(p).is_file() and sha(p)==h)
for p,h in {**doc['source_files_sha256'],**doc['output_files_sha256']}.items():ok('report_binding:'+p,Path(p).is_file() and sha(p)==h)
reviewed_codes={}
for p in [L/'tools/stage004_report.py',L/'tools/test_stage004_report.py',L/'tools/stage001_report.py',ROOT/'research/lines/futures_weekly_formal_no_half_r/tools/stage029_build_artifacts.py']:
 h=sha(p);reviewed_codes[str(p)]=h
 if str(p) in old_bound:ok('imported_report_code_frozen:'+str(p),h==old_bound[str(p)])
controls={'original':(L/'outputs/stage001_A_attempt003',L/'stages/stage001_independent_A_results.json'),'short_only':(L/'outputs/stage001_C_attempt003',L/'stages/stage001_independent_C_results.json'),'symmetric':(L/'outputs/stage002_C_attempt001',L/'stages/stage002_independent_results.json'),'long_ma5':(L/'outputs/stage004_C_attempt001',L/'stages/stage004_independent_results.json')};metrics={};pres={};settings={};effective={};margin={};curve_checks={}
for role,(p,rp) in controls.items():
 m=json.loads(rp.read_text())['metrics'];metrics[role]=m;row=summary.loc[summary.role.eq(role)].iloc[0];pres[role]=json.loads((p/'preflight.json').read_text());settings[role]=json.loads((p/'actual_strategy_settings.json').read_text());effective[role]=json.loads((p/'effective_parameters.json').read_text())
 for k in ['end_equity','total_return_pct','max_dd_pct','sharpe','total_slippage','open_round_net_mtm']:near(role+'_summary_'+k,row[k],m[k])
 near(role+'_fill_count',row['modeled_fill_count'],m['total_trade_count']);near(role+'_NAV_end',row['nav_end'],m['end_equity']/150000)
 for rk,mk in [('round_count','count'),('round_wins','wins'),('round_losses','losses'),('round_flat','flat'),('round_win_rate_pct','win_rate_pct'),('round_average_win','average_win'),('round_average_loss_abs','average_loss_abs'),('round_payoff_ratio','payoff_ratio'),('round_profit_factor','profit_factor'),('round_closed_net_pnl','closed_net_pnl')]:near(role+'_summary_'+rk,row[rk],m['rounds'][mk])
 d=pd.read_csv(p/'daily.csv');ratio=d.total_margin_exact/d.account_equity*1.65*100;margin[role]=dict(configured_margin_max_pct=float(ratio.max()),configured_margin_over100_days=int(ratio.gt(100).sum()));near(role+'_configured_margin_max',row['actual_margin_to_equity_max_pct'],ratio.max());near(role+'_configured_margin_over100',row['actual_margin_over100_days'],ratio.gt(100).sum());near(role+'_legacy_multiplier',row['legacy_broker10_multiplier'],1.1);near(role+'_configured_multiplier',row['actual_broker_margin_multiplier'],1.65)
 q=pd.read_csv(R/f'{role}_daily.csv');c=curve.loc[curve.role.eq(role)].reset_index(drop=True);ok(role+'_curve_dates',q.date.equals(d.date) and c.date.equals(d.date));nav=d.account_equity.to_numpy()/150000;dd=(d.account_equity.to_numpy()/np.maximum.accumulate(np.r_[150000,d.account_equity.to_numpy()])[1:]-1)*100
 for j in range(len(d)):
  near(role+f'_NAV_point_{j}',q.nav.iloc[j],nav[j]);near(role+f'_DD_point_{j}',q.drawdown_pct.iloc[j],dd[j]);near(role+f'_combined_NAV_point_{j}',c.nav.iloc[j],nav[j]);near(role+f'_combined_DD_point_{j}',c.drawdown_pct.iloc[j],dd[j]);near(role+f'_curve_equity_point_{j}',c.account_equity.iloc[j],d.account_equity.iloc[j])
 curve_checks[role]=dict(points=len(d),NAV_end=float(nav[-1]),max_DD_pct=float(dd.min()),definition='NAV=equity/150000; DD includes initial150000 high-water mark')
 prior=150000.
 for year,g in d.groupby(d.date.astype(str).str[:4],sort=True):
  a=annual.loc[annual.role.eq(role)&annual.year.eq(int(year))].iloc[0];near(role+'_'+year+'_initial',a.initial_capital,prior);near(role+'_'+year+'_end',a.end_equity,g.account_equity.iloc[-1]);near(role+'_'+year+'_pnl',a.net_pnl,g.net_pnl.sum());near(role+'_'+year+'_return',a.total_return_pct,(g.account_equity.iloc[-1]/prior-1)*100);near(role+'_'+year+'_slippage',a.total_slippage,g.slippage.sum());near(role+'_'+year+'_fills',a.modeled_fill_count,g.trade_count.sum());prior=float(g.account_equity.iloc[-1])
for role in ['original','short_only','symmetric']:
 ok(role+'_same_settings',settings[role]==settings['long_ma5']);ok(role+'_same_effective',effective[role]==effective['long_ma5']);ok(role+'_same_data',pres[role]['data_identity']==pres['long_ma5']['data_identity']);expected_long=role=='symmetric';ok(role+'_old_long_flag',pres[role].get('long_ma_slope_gate_enabled',False) is expected_long)
ok('original_short_off',pres['original']['short_ma_slope_gate_enabled'] is False);ok('old_short_only_on',pres['short_only']['short_ma_slope_gate_enabled'] is True);ok('old_symmetric_short_on',pres['symmetric']['short_ma_slope_gate_enabled'] is True);ok('new_declared_long_only_MA5',pres['long_ma5']['long_ma_slope_periods']==[5]);ok('new_short_still_on',pres['long_ma5']['short_ma_slope_gate_enabled'] is True)
gates={};differences={}
for role in ['original','short_only','symmetric']:
 gates[role]={k:metrics['long_ma5'][k]>=metrics[role][k] for k in ['end_equity','max_dd_pct','sharpe']};ok('declared_gates_'+role,gates[role]==doc['fixed_candidate_gates_vs'][role]);differences[role]={k:metrics['long_ma5'][k]-metrics[role][k] for k in ['end_equity','total_return_pct','max_dd_pct','sharpe']}
 for k,v in differences[role].items():near('reported_diff_'+role+'_'+k,doc['difference_vs'][role][k],v)
ok('predeclared_mixed_fail',not all(gates['symmetric'].values()) and doc['strategy_verdict_vs_symmetric']=='MIXED_OR_FAIL_NO_RESCUE_TUNING');ok('no_promotion',doc['promotion_decision']=='NO_PROMOTION');ok('curves_four_full_windows',len(curve)==6608 and set(curve.role)==set(controls))
terminal=json.loads((L/'outputs/stage004_C_attempt001/terminal.json').read_text());ok('actual_run_time',terminal['started_at'].startswith('2026-10-30T01:01:05') and terminal['completed_at'].startswith('2026-10-30T01:02:32'))
result=dict(status='PASS_WITH_LIMITATIONS',P0=0,P1=0,P2=0,reviewed_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),financial_core_checks=review['checks'],additional_gate_fill_checks=review['additional_checks'],report_cross_check_count=len(checks),failures=0,checks=checks,metrics=metrics,margin=margin,curve_checks=curve_checks,old_frozen_delivery_binding_counts=frozen_counts,reviewed_report_code_sha256=reviewed_codes,comparison_sha256=sha(R/'comparison.json'),fixed_gates_vs=gates,differences_vs=differences,design_time_label_correction='Design header01:03 was a hand-entered projected time; immutable input bytes preserved. Runner terminal actual interval01:01:05--01:02:32 is authoritative; contract values and source hashes unchanged.',strategy_verdict='MIXED_OR_FAIL_NO_RESCUE_TUNING',promotion_decision='NO_PROMOTION',financial_replays=0,market_downloads=0,production_accesses=0,production_qualified=False,limitations=['Historical internal development; this user-specified revision follows observed negative results and is not fresh OOS.','Zero commission, static margin, daily-next-open and historical source limitations remain.','Changes in equity include shared-capital path feedback; not directly causal PnL of blocked or permitted entries.'])
(L/'stages/stage004_independent_final.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['checks','metrics','reviewed_report_code_sha256']},ensure_ascii=False))
