from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import ast,copy,hashlib,json,math,sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[4];L=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';R=L/'artifacts/stage006_comparison';checks={}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for c in iter(lambda:f.read(8*1024*1024),b''):h.update(c)
 return h.hexdigest()
def ok(k,v):
 checks[k]=bool(v)
 if not v:raise AssertionError(k)
def near(k,a,b):ok(k,math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-6))
review=json.loads((L/'stages/stage006_independent_C_results.json').read_text());doc=json.loads((R/'comparison.json').read_text());summary=pd.read_csv(R/'summary.csv');annual=pd.read_csv(R/'annual.csv');curve=pd.read_csv(R/'nav_drawdown.csv');old_bound={};counts={}
for name in ['stage001_delivery_manifest.json','stage002_delivery_manifest.json','stage003_delivery_manifest.json','stage004_delivery_manifest.json','stage004_delivery_manifest_v2.json','stage005_delivery_manifest.json']:
 b=json.loads((L/'stages'/name).read_text())['files_sha256'];old_bound.update(b);counts[name]=len(b)
 for p,h in b.items():ok('frozen_'+name+':'+p,Path(p).is_file() and sha(p)==h)
for p,h in {**doc['source_files_sha256'],**doc['output_files_sha256']}.items():ok('report_binding:'+p,Path(p).is_file() and sha(p)==h)
codes={}
for p in [L/'tools/stage006_report.py',L/'tools/test_stage006_report.py',L/'tools/stage001_report.py',ROOT/'research/lines/futures_weekly_formal_no_half_r/tools/stage029_build_artifacts.py',L/'tools/stage005_short_bottom20.py',L/'tools/run_stage006.py',L/'tools/test_stage006_runner.py']:
 h=sha(p);codes[str(p)]=h
 if str(p) in old_bound:ok('frozen_pure_accounting:'+str(p),old_bound[str(p)]==h)
# Verify the accounting adapter changes exactly the one declared identity check.
sys.path.insert(0,str(L/'tools'));import stage006_report as report
actual_tree,receipt=report.price_loader_ast();original=ast.parse((L/'tools/stage001_report.py').read_text());expected=copy.deepcopy(next(n for n in original.body if isinstance(n,ast.FunctionDef) and n.name=='load_ledger'));changed=0
for i,node in enumerate(expected.body):
 if isinstance(node,ast.If) and any(isinstance(x,ast.Constant) and x.value=='slope_arm_flag_mismatch' for x in ast.walk(node)):
  expected.body[i:i+1]=ast.parse("price_gate=read('short_price_range_acceptance.json')\n_stage006_validate_gate(pre,gate,price_gate,role)").body;changed+=1;break
expected.name='_stage006_pure_accounting_loader'
replaced_dates={'2020-01-01':0,'2020-01-02':0}
class IndependentWindowDates(ast.NodeTransformer):
 def visit_Constant(self,node):
  if node.value in replaced_dates if isinstance(node.value,str) else False:
   replaced_dates[node.value]+=1;return ast.copy_location(ast.Constant(value={'2020-01-01':'2015-01-01','2020-01-02':'2015-01-05'}[node.value]),node)
  if node.value=='full_requested_2020_calendar_required':return ast.copy_location(ast.Constant(value='stage006_full_requested_2015_calendar_required'),node)
  return node
expected=IndependentWindowDates().visit(expected);ok('exact_two_declared_date_constants',replaced_dates=={'2020-01-01':1,'2020-01-02':1});adapted=next(n for n in actual_tree.body if isinstance(n,ast.FunctionDef));ok('exact_single_identity_AST_replacement',changed==1 and ast.dump(expected,include_attributes=False)==ast.dump(adapted,include_attributes=False));ok('adapter_receipt_exact',receipt==doc['loader_adapter'])
roles={'original':(L/'outputs/stage006_A_attempt001',L/'stages/stage006_independent_A_results.json'),'price_range':(L/'outputs/stage006_C_attempt001',L/'stages/stage006_independent_C_results.json')};metrics={};pres={};settings={};effective={};margin={};curvechecks={}
for role,(p,proof) in roles.items():
 m=json.loads(proof.read_text())['metrics'];metrics[role]=m;row=summary.loc[summary.role.eq(role)].iloc[0];pres[role]=json.loads((p/'preflight.json').read_text());settings[role]=json.loads((p/'actual_strategy_settings.json').read_text());effective[role]=json.loads((p/'effective_parameters.json').read_text())
 for k in ['end_equity','total_return_pct','max_dd_pct','sharpe','total_slippage','open_round_net_mtm']:near(role+'_summary_'+k,row[k],m[k])
 near(role+'_fill_count',row['modeled_fill_count'],m['total_trade_count']);near(role+'_end_NAV',row['nav_end'],m['end_equity']/150000)
 for rk,mk in [('round_count','count'),('round_wins','wins'),('round_losses','losses'),('round_flat','flat'),('round_win_rate_pct','win_rate_pct'),('round_average_win','average_win'),('round_average_loss_abs','average_loss_abs'),('round_payoff_ratio','payoff_ratio'),('round_profit_factor','profit_factor'),('round_closed_net_pnl','closed_net_pnl')]:near(role+'_'+rk,row[rk],m['rounds'][mk])
 d=pd.read_csv(p/'daily.csv');ratio=d.total_margin_exact/d.account_equity*1.65*100;margin[role]=dict(configured_margin_max_pct=float(ratio.max()),over100_days=int(ratio.gt(100).sum()));near(role+'_margin_peak',row['actual_margin_to_equity_max_pct'],ratio.max());near(role+'_margin_days',row['actual_margin_over100_days'],ratio.gt(100).sum())
 q=pd.read_csv(R/f'{role}_daily.csv');c=curve.loc[curve.role.eq(role)].reset_index(drop=True);ok(role+'_curve_dates',q.date.equals(d.date) and c.date.equals(d.date));nav=d.account_equity.to_numpy()/150000;dd=(d.account_equity.to_numpy()/np.maximum.accumulate(np.r_[150000,d.account_equity.to_numpy()])[1:]-1)*100
 for j in range(len(d)):
  near(role+f'_NAV_{j}',q.nav.iloc[j],nav[j]);near(role+f'_DD_{j}',q.drawdown_pct.iloc[j],dd[j]);near(role+f'_combined_NAV_{j}',c.nav.iloc[j],nav[j]);near(role+f'_combined_DD_{j}',c.drawdown_pct.iloc[j],dd[j]);near(role+f'_combined_equity_{j}',c.account_equity.iloc[j],d.account_equity.iloc[j])
 curvechecks[role]=dict(points=len(d),end_NAV=float(nav[-1]),max_DD_pct=float(dd.min()),definition='equity/150000; DD includes initial capital')
 prior=150000.
 for year,g in d.groupby(d.date.astype(str).str[:4],sort=True):
  a=annual.loc[annual.role.eq(role)&annual.year.eq(int(year))].iloc[0];near(role+'_'+year+'_initial',a.initial_capital,prior);near(role+'_'+year+'_end',a.end_equity,g.account_equity.iloc[-1]);near(role+'_'+year+'_pnl',a.net_pnl,g.net_pnl.sum());near(role+'_'+year+'_return',a.total_return_pct,(g.account_equity.iloc[-1]/prior-1)*100);near(role+'_'+year+'_slip',a.total_slippage,g.slippage.sum());near(role+'_'+year+'_fills',a.modeled_fill_count,g.trade_count.sum());prior=float(g.account_equity.iloc[-1])
ok('same_actual_settings',settings['original']==settings['price_range']);ok('same_effective',effective['original']==effective['price_range']);ok('same_data_identity',pres['original']['data_identity']==pres['price_range']['data_identity']);ok('new_genuine_no_MA_slope_flags',pres['price_range']['short_ma_slope_gate_enabled'] is False and pres['price_range']['long_ma_slope_gate_enabled'] is False);ok('original_no_slope_gate',pres['original']['short_ma_slope_gate_enabled'] is False and pres['original'].get('long_ma_slope_gate_enabled',False) is False)
gates={k:metrics['price_range'][k]>=metrics['original'][k] for k in ['end_equity','max_dd_pct','sharpe']};ok('computed_mixed_gates',gates==doc['fixed_candidate_gates'] and gates=={'end_equity':False,'max_dd_pct':True,'sharpe':False});ok('fixed_window_fail',doc['strategy_verdict']=='MIXED_OR_FAIL_NO_RESCUE_TUNING' and doc['promotion_decision']=='NO_PROMOTION');diff={k:metrics['price_range'][k]-metrics['original'][k] for k in ['end_equity','total_return_pct','max_dd_pct','sharpe']}
for k,v in diff.items():near('reported_diff_'+k,doc['difference_vs_original'][k],v)
ok('two_full_windows5742',len(curve)==5742 and set(curve.role)==set(roles));ok('no_terminal_MTM',metrics['price_range']['open_round_net_mtm']==0 and summary.loc[summary.role.eq('price_range'),'open_round_count'].iloc[0]==0)
testlog=(L/'stages/stage006_independent_tests.log').read_text();ok('45_independent_tests_pass','Ran 45 tests' in testlog and testlog.strip().endswith('OK'))
identity=json.loads((L/'stages/stage006_independent_identity.json').read_text());ok('old2015_A_identity_through28',identity['status']=='PASS_2015_BASELINE_EXACT_THROUGH_PRIOR_CUTOFF')
areview=json.loads((L/'stages/stage006_independent_A_results.json').read_text());bridge=dict(closed_net_pnl_difference=metrics['price_range']['rounds']['closed_net_pnl']-metrics['original']['rounds']['closed_net_pnl'],open_round_net_MTM_difference=metrics['price_range']['open_round_net_mtm']-metrics['original']['open_round_net_mtm'],end_equity_difference=diff['end_equity']);near('closed_open_bridge',bridge['closed_net_pnl_difference']+bridge['open_round_net_MTM_difference'],bridge['end_equity_difference'])
prefix=review['range_prefix_proofs'];timestamp=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat();terminal=json.loads((roles['price_range'][0]/'terminal.json').read_text());r=dict(status='PASS_WITH_LIMITATIONS',P0=0,P1=0,P2=0,failures=0,reviewed_at=timestamp,independent_tests_passed=45,financial_core_checks=dict(A=areview['checks'],C=review['checks']),report_cross_check_count=len(checks),metrics=metrics,margin=margin,curve_checks=curvechecks,A_disabled_range_diagnostics=dict(count=areview['decision_count'],would_block=areview['would_block_count'],applied=areview['blocked_decisions']),range_diagnostics=dict(count=review['decision_count'],would_block=review['would_block_count'],positive_size_applied_block=review['blocked_decisions'],daily_prefix_min=min(x['available_daily_count'] for x in prefix),daily_prefix_max=max(x['available_daily_count'] for x in prefix),events_with_daily_beyond_engine_week_sources=sum(x['additional_daily_count_beyond_engine_week_sources']>0 for x in prefix),events_cache_starts_after_known_listing=sum(x['cache_first_after_known_listed_date'] for x in prefix),listing_completeness_proven=False),cold_start_evidence=dict(A=areview['cold_start_warmup_evidence'],C=review['cold_start_warmup_evidence']),prior_A_identity_proof_sha256=sha(L/'stages/stage006_independent_identity.json'),end_equity_bridge=bridge,actual_open_context_counts=review['actual_open_context_counts'],slope_diagnostics_only=review['MA_slope_diagnostics_only'],frozen_delivery_counts=counts,reviewed_code_sha256=codes,report_comparison_sha256=sha(R/'comparison.json'),fixed_candidate_gates=gates,difference_vs_original=diff,strategy_verdict='MIXED_OR_FAIL_NO_RESCUE_TUNING',promotion_decision='NO_PROMOTION',production_qualified=False,financial_replays=0,market_downloads=0,production_accesses=0,actual_strategy_run_interval=dict(started_at=terminal['started_at'],completed_at=terminal['completed_at']),limitations=['All cached approved same-epoch daily history is not proven complete listing history;7 events begin after known listing date;2014 warmup/main/lifecycle limitations remain.','Repeated historical development; 2020 improvement fails to generalize to2015 equity/Sharpe; no OOS, alpha or production qualification.','Zero commission, static margin x1.65 and daily-next-open lack historical actual broker margin and depth/capacity proof.','Whole-account difference includes capital sizing/integer/risk/opportunity path feedback; not direct causal PnL of55 blocked candidates.'])
(L/'stages/stage006_independent_final.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k not in ['checks','metrics','reviewed_code_sha256']},ensure_ascii=False))
