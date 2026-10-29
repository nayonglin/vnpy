from pathlib import Path
import json,hashlib,math
import pandas as pd
ROOT=Path(__file__).resolve().parents[4];L=ROOT/'research/lines/futures_weekly_short_ma_slope_gate'
checks={}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for c in iter(lambda:f.read(8*1024*1024),b''):h.update(c)
 return h.hexdigest()
def ok(k,v):
 checks[k]=bool(v)
 if not v:raise AssertionError(k)
def near(k,a,b):ok(k,math.isclose(float(a),float(b),abs_tol=1e-6,rel_tol=1e-10))
review=json.loads((L/'stages/stage002_independent_results.json').read_text());report=L/'artifacts/stage002_comparison';doc=json.loads((report/'comparison.json').read_text());summary=pd.read_csv(report/'summary.csv');annual=pd.read_csv(report/'annual.csv')
old=json.loads((L/'stages/stage001_delivery_manifest.json').read_text())['files_sha256']
for p,h in old.items():ok('old_delivery:'+p,Path(p).is_file() and sha(p)==h)
for p,h in {**doc['source_files_sha256'],**doc['output_files_sha256']}.items():ok('report_binding:'+p,Path(p).is_file() and sha(p)==h)
reviewed_code={}
for p in [L/'tools/stage001_report.py',ROOT/'research/lines/futures_weekly_formal_no_half_r/tools/stage029_build_artifacts.py',L/'tools/stage002_report.py']:
 digest=sha(p);reviewed_code[str(p)]=digest
 if str(p) in old:ok('imported_report_code_frozen:'+str(p),old[str(p)]==digest)
controls={'original':(L/'outputs/stage001_A_attempt003',L/'stages/stage001_independent_A_results.json'),'short_only':(L/'outputs/stage001_C_attempt003',L/'stages/stage001_independent_C_results.json'),'symmetric':(L/'outputs/stage002_C_attempt001',L/'stages/stage002_independent_results.json')};metrics={};pre={};settings={};effective={};margin={}
for role,(p,rp) in controls.items():
 r=json.loads(rp.read_text());metrics[role]=r['metrics'];row=summary.loc[summary.role.eq(role)].iloc[0];m=r['metrics'];pre[role]=json.loads((p/'preflight.json').read_text());settings[role]=json.loads((p/'actual_strategy_settings.json').read_text());effective[role]=json.loads((p/'effective_parameters.json').read_text())
 for k in ['end_equity','total_return_pct','max_dd_pct','sharpe','total_slippage','open_round_net_mtm']:near(role+'_summary_'+k,row[k],m[k])
 near(role+'_fill_count',row['modeled_fill_count'],m['total_trade_count'])
 for rk,mk in [('round_count','count'),('round_wins','wins'),('round_losses','losses'),('round_flat','flat'),('round_win_rate_pct','win_rate_pct'),('round_average_win','average_win'),('round_average_loss_abs','average_loss_abs'),('round_payoff_ratio','payoff_ratio'),('round_profit_factor','profit_factor'),('round_closed_net_pnl','closed_net_pnl')]:near(role+'_summary_'+rk,row[rk],m['rounds'][mk])
 d=pd.read_csv(p/'daily.csv');ratio=d.total_margin_exact/d.account_equity*1.65*100;margin[role]=dict(max_pct=float(ratio.max()),over100_days=int(ratio.gt(100).sum()));near(role+'_margin_max',row['actual_margin_to_equity_max_pct'],ratio.max());near(role+'_margin_over100',row['actual_margin_over100_days'],ratio.gt(100).sum())
 prior=150000.
 for year,g in d.groupby(d.date.astype(str).str[:4],sort=True):
  a=annual.loc[annual.role.eq(role)&annual.year.eq(int(year))].iloc[0];near(role+'_'+year+'_year_initial',a.initial_capital,prior);near(role+'_'+year+'_year_end',a.end_equity,g.account_equity.iloc[-1]);near(role+'_'+year+'_year_pnl',a.net_pnl,g.net_pnl.sum());near(role+'_'+year+'_year_return',a.total_return_pct,(g.account_equity.iloc[-1]/prior-1)*100);near(role+'_'+year+'_year_slippage',a.total_slippage,g.slippage.sum());near(role+'_'+year+'_year_fills',a.modeled_fill_count,g.trade_count.sum());prior=float(g.account_equity.iloc[-1])
for role in ['original','short_only']:
 ok(role+'_same_settings',settings[role]==settings['symmetric']);ok(role+'_same_effective',effective[role]==effective['symmetric']);ok(role+'_same_data',pre[role]['data_identity']==pre['symmetric']['data_identity']);ok(role+'_old_long_not_enabled',pre[role].get('long_ma_slope_gate_enabled',False) is False)
ok('original_short_off',pre['original']['short_ma_slope_gate_enabled'] is False);ok('shortonly_short_on',pre['short_only']['short_ma_slope_gate_enabled'] is True);ok('symmetric_both_on',pre['symmetric']['short_ma_slope_gate_enabled'] is True and pre['symmetric']['long_ma_slope_gate_enabled'] is True)
gates={k:metrics['symmetric'][k]>=metrics['short_only'][k] for k in ['end_equity','max_dd_pct','sharpe']};ok('declared_all_three_gates_fail',not any(gates.values()) and gates==doc['fixed_candidate_gates_vs_short_only']);ok('no_promotion',doc['promotion_decision']=='NO_PROMOTION' and doc['strategy_verdict']=='MIXED_OR_FAIL_NO_RESCUE_TUNING')
for k,v in doc['difference_vs_short_only'].items():near('reported_difference_'+k,v,metrics['symmetric'][k]-metrics['short_only'][k])
result=dict(status='PASS_WITH_LIMITATIONS',P0=0,P1=0,P2=0,check_count=len(checks),failures=0,checks=checks,financial_core_checks=review['checks'],long_actual_open_cross_checks=review['additional_checks'],reviewed_report_code_sha256=reviewed_code,report_comparison_sha256=sha(report/'comparison.json'),source_report_binding_policy='Imported pure-accounting modules additionally bound here and matched immutableStage001 delivery; no old source edited.',metrics=metrics,margin=margin,predeclared_gates_vs_short_only=gates,strategy_verdict='MIXED_OR_FAIL_NO_RESCUE_TUNING',promotion_decision='NO_PROMOTION',production_qualified=False,financial_replays=0,limitations=['Frozen-source consistency and full repricing do not establish market truth or all historical PIT/OOS.','Repeated historical research, zero commission, static margin and daily-next-open model retain limitations.','Gate events are candidate events; net equity difference includes shared-capital path feedback, not direct causal PnL of blocked trades.'])
(L/'stages/stage002_independent_final.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['checks','metrics','reviewed_report_code_sha256']},ensure_ascii=False))
