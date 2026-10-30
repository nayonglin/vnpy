"""Final independent report audit. Lock JSON once only, then visual receipt may bind it."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import ast,copy,hashlib,json,math,sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[4];L=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';R=L/'artifacts/stage007_comparison';checks=0;hashcache={}
def sha(p):
 p=Path(p)
 if str(p) not in hashcache:
  h=hashlib.sha256()
  with p.open('rb') as f:
   for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
  hashcache[str(p)]=h.hexdigest()
 return hashcache[str(p)]
def ok(k,v):
 global checks;checks+=1
 if not v:raise AssertionError(k)
def near(k,a,b):ok(k,math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-6))
roles={'original':(L/'outputs/stage006_A_attempt001',L/'stages/stage006_independent_A_results.json'),'short_only':(L/'outputs/stage006_C_attempt001',L/'stages/stage006_independent_C_results.json'),'long_top20':(L/'outputs/stage007_C_attempt001',L/'stages/stage007_independent_C_results.json')}
review=json.loads(roles['long_top20'][1].read_text());doc=json.loads((R/'comparison.json').read_text());summary=pd.read_csv(R/'summary.csv');annual=pd.read_csv(R/'annual.csv');curve=pd.read_csv(R/'nav_drawdown.csv');old_bound={};counts={};manifests={}
for name in ['stage001_delivery_manifest.json','stage002_delivery_manifest.json','stage003_delivery_manifest.json','stage004_delivery_manifest.json','stage004_delivery_manifest_v2.json','stage005_delivery_manifest.json','stage006_delivery_manifest.json']:
 p=L/'stages'/name;b=json.loads(p.read_text())['files_sha256'];old_bound.update(b);counts[name]=len(b);manifests[str(p)]=sha(p)
 for p,h in b.items():ok('frozen:'+name+':'+p,Path(p).is_file() and sha(p)==h)
for p,h in {**doc['source_files_sha256'],**doc['output_files_sha256']}.items():ok('report_binding:'+p,Path(p).is_file() and sha(p)==h)
codes={}
for p in [L/'tools/stage007_report.py',L/'tools/test_stage007_report.py',L/'tools/stage006_report.py',L/'tools/stage001_report.py',ROOT/'research/lines/futures_weekly_formal_no_half_r/tools/stage029_build_artifacts.py',L/'tools/stage005_short_bottom20.py',L/'tools/stage007_long_top20.py',L/'tools/test_stage007_long_top20.py',L/'tools/run_stage007.py',L/'tools/stage007_independent_results.py',Path(__file__)]:
 h=sha(p);codes[str(p)]=h
 if str(p) in old_bound:ok('frozen_accounting_or_core:'+str(p),old_bound[str(p)]==h)
# Re-prove the inherited pure accounting transformation independently, including date constants.
sys.path.insert(0,str(L/'tools'));import stage006_report as accounting
actual_tree,receipt=accounting.price_loader_ast();original=ast.parse((L/'tools/stage001_report.py').read_text());expected=copy.deepcopy(next(n for n in original.body if isinstance(n,ast.FunctionDef) and n.name=='load_ledger'));changed=0
for i,node in enumerate(expected.body):
 if isinstance(node,ast.If) and any(isinstance(x,ast.Constant) and x.value=='slope_arm_flag_mismatch' for x in ast.walk(node)):
  expected.body[i:i+1]=ast.parse("price_gate=read('short_price_range_acceptance.json')\n_stage006_validate_gate(pre,gate,price_gate,role)").body;changed+=1;break
expected.name='_stage006_pure_accounting_loader';dates_replaced={'2020-01-01':0,'2020-01-02':0}
class Dates(ast.NodeTransformer):
 def visit_Constant(self,node):
  if isinstance(node.value,str) and node.value in dates_replaced:
   dates_replaced[node.value]+=1;return ast.copy_location(ast.Constant(value={'2020-01-01':'2015-01-01','2020-01-02':'2015-01-05'}[node.value]),node)
  if node.value=='full_requested_2020_calendar_required':return ast.copy_location(ast.Constant(value='stage006_full_requested_2015_calendar_required'),node)
  return node
expected=Dates().visit(expected);adapted=next(n for n in actual_tree.body if isinstance(n,ast.FunctionDef));ok('exact_loader_AST_and_dates',changed==1 and dates_replaced=={'2020-01-01':1,'2020-01-02':1} and ast.dump(expected,include_attributes=False)==ast.dump(adapted,include_attributes=False));ok('adapter_receipt',receipt==doc['frozen_accounting_loader_adapter'])
metrics={};pres={};settings={};effective={};margin={};curvechecks={};proofshas={}
for role,(p,proof) in roles.items():
 raw=json.loads(proof.read_text());ok(role+'_signed_core',raw['status']=='PASS_WITH_LIMITATIONS' and raw['P0']==raw['P1']==raw['P2']==0);m=raw['metrics'];metrics[role]=m;proofshas[str(proof)]=sha(proof);row=summary.loc[summary.role.eq(role)].iloc[0];pres[role]=json.loads((p/'preflight.json').read_text());settings[role]=json.loads((p/'actual_strategy_settings.json').read_text());effective[role]=json.loads((p/'effective_parameters.json').read_text())
 for k in ['end_equity','total_return_pct','max_dd_pct','sharpe','total_slippage','open_round_net_mtm']:near(role+'_summary_'+k,row[k],m[k])
 near(role+'_fill_count',row['modeled_fill_count'],m['total_trade_count']);near(role+'_end_NAV',row['nav_end'],m['end_equity']/150000)
 for rk,mk in [('round_count','count'),('round_wins','wins'),('round_losses','losses'),('round_flat','flat'),('round_win_rate_pct','win_rate_pct'),('round_average_win','average_win'),('round_average_loss_abs','average_loss_abs'),('round_payoff_ratio','payoff_ratio'),('round_profit_factor','profit_factor'),('round_closed_net_pnl','closed_net_pnl')]:near(role+'_'+rk,row[rk],m['rounds'][mk])
 d=pd.read_csv(p/'daily.csv');ratio=d.total_margin_exact/d.account_equity*1.65*100;margin[role]=dict(configured_margin_max_pct=float(ratio.max()),over100_days=int(ratio.gt(100).sum()));near(role+'_margin',row['actual_margin_to_equity_max_pct'],ratio.max());near(role+'_margin_days',row['actual_margin_over100_days'],ratio.gt(100).sum())
 q=pd.read_csv(R/f'{role}_daily.csv');c=curve.loc[curve.role.eq(role)].reset_index(drop=True);ok(role+'_dates',q.date.equals(d.date) and c.date.equals(d.date));nav=d.account_equity.to_numpy()/150000;dd=(d.account_equity.to_numpy()/np.maximum.accumulate(np.r_[150000,d.account_equity.to_numpy()])[1:]-1)*100
 for j in range(len(d)):
  for suffix,a,b in [('NAV',q.nav.iloc[j],nav[j]),('DD',q.drawdown_pct.iloc[j],dd[j]),('combined_NAV',c.nav.iloc[j],nav[j]),('combined_DD',c.drawdown_pct.iloc[j],dd[j]),('equity',c.account_equity.iloc[j],d.account_equity.iloc[j])]:near(role+f'_{j}_'+suffix,a,b)
 curvechecks[role]=dict(points=len(d),end_NAV=float(nav[-1]),max_DD_pct=float(dd.min()),definition='equity/150000; DD includes initial150000')
 prior=150000.
 for year,g in d.groupby(d.date.astype(str).str[:4],sort=True):
  a=annual.loc[annual.role.eq(role)&annual.year.eq(int(year))].iloc[0]
  for name,left,right in [('initial',a.initial_capital,prior),('end',a.end_equity,g.account_equity.iloc[-1]),('pnl',a.net_pnl,g.net_pnl.sum()),('return',a.total_return_pct,(g.account_equity.iloc[-1]/prior-1)*100),('slip',a.total_slippage,g.slippage.sum()),('fills',a.modeled_fill_count,g.trade_count.sum())]:near(role+'_'+year+'_'+name,left,right)
  prior=float(g.account_equity.iloc[-1])
for role in roles:
 ok(role+'_same_settings',settings[role]==settings['short_only']);ok(role+'_same_effective',effective[role]==effective['short_only']);ok(role+'_same_data',pres[role]['data_identity']==pres['short_only']['data_identity']);ok(role+'_MA_slope_off',pres[role]['short_ma_slope_gate_enabled'] is False and pres[role].get('long_ma_slope_gate_enabled',False) is False)
 ok(role+'_long_flag',pres[role].get('long_price_range_gate_enabled',False) is (role=='long_top20'));ok(role+'_short_flag',pres[role]['short_price_range_gate_enabled'] is (role!='original'))
# Identical short source decisions apart from capital-path-dependent sizing fields.
oldshort=json.loads((roles['short_only'][0]/'short_price_range_decisions.json').read_text());newshort=json.loads((roles['long_top20'][0]/'short_price_range_decisions.json').read_text());skip={'selected_volume_before','selected_volume_after','applied_block'}
clean=lambda rows:[{k:v for k,v in r.items() if k not in skip} for r in rows]
ok('all100_short_decisions_source_and_rule_identical',len(newshort)==100 and clean(newshort)==clean(oldshort));short_changed_sizes=sum(r['selected_volume_before']!=s['selected_volume_before'] for r,s in zip(oldshort,newshort))
gates={role:{k:metrics['long_top20'][k]>=metrics[role][k] for k in ['end_equity','max_dd_pct','sharpe']} for role in ['short_only','original']};ok('gates',gates==doc['fixed_candidate_gates_vs']);ok('no_promotion',doc['promotion_decision']=='NO_PROMOTION');ok('economic_verdict',doc['strategy_verdict_vs_short_only']==('PASS_FIXED_WINDOW_ONLY' if all(gates['short_only'].values()) else 'MIXED_OR_FAIL_NO_RESCUE_TUNING'))
diffs={role:{k:metrics['long_top20'][k]-metrics[role][k] for k in ['end_equity','total_return_pct','max_dd_pct','sharpe']} for role in ['short_only','original']}
for role,difference in diffs.items():
 for k,v in difference.items():near('difference_'+role+'_'+k,doc['difference_vs'][role][k],v)
bridges={}
for role in ['short_only','original']:
 b=dict(closed_net_pnl_difference=metrics['long_top20']['rounds']['closed_net_pnl']-metrics[role]['rounds']['closed_net_pnl'],open_round_net_MTM_difference=metrics['long_top20']['open_round_net_mtm']-metrics[role]['open_round_net_mtm'],end_equity_difference=diffs[role]['end_equity']);near(role+'_bridge',b['closed_net_pnl_difference']+b['open_round_net_MTM_difference'],b['end_equity_difference']);bridges[role]=b
ok('full8613curve_and36annual',len(curve)==8613 and set(curve.role)==set(roles) and len(annual)==36);ok('no_candidate_terminal_MTM',metrics['long_top20']['open_round_net_mtm']==0 and summary.loc[summary.role.eq('long_top20'),'open_round_count'].iloc[0]==0)
testlog=(L/'stages/stage007_independent_tests.log').read_text();ok('52_tests_pass','Ran 52 tests' in testlog and testlog.strip().endswith('OK'))
# Trace strict record-high actual fills from unique order anchors to source decisions.
p=roles['long_top20'][0];fills=pd.read_csv(p/'trades.csv');anchors=pd.read_csv(p/'execution_anchor_requests.csv');candidates=pd.read_csv(p/'entry_candidates.csv');decisions=json.loads((p/'long_price_range_decisions.json').read_text());breakouts=[]
for t in fills.loc[fills.direction.eq('多')&fills.offset.eq('开')].itertuples():
 a=anchors.loc[anchors.order_id.astype(str).eq(str(t.order_id))];ok('long_unique_anchor',len(a)==1);day=str(a.iloc[0].signal_date)[:10];qq=[x for x in decisions if x['signal_date']==day and x['vt_symbol']==t.vt_symbol and x['breakout_exempt']]
 if qq:
  r=qq[0];ok('breakout_actual_above_prior_high',r['signal_close']>r['prior_range_high']);breakouts.append(dict(order_id=t.order_id,trade_id=t.trade_id,signal_date=day,execution_trading_date=t.trading_date,vt_symbol=t.vt_symbol,signal=r['signal'],signal_close=r['signal_close'],prior_high=r['prior_range_high'],actual_fill_price=t.price,actual_fill_volume=t.volume))
bo=L/'stages/stage007_independent_actual_breakouts.csv';pd.DataFrame(breakouts).to_csv(bo,index=False);ok('actual_breakout11_vs_diagnostics13',len(breakouts)==11 and review['long_breakout_exempt_count']==13)
proofs=review['long_prefix_proofs'];terminal=json.loads((p/'terminal.json').read_text());r=dict(status='PASS_WITH_LIMITATIONS',P0=0,P1=0,P2=0,failures=0,reviewed_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),financial_core_checks=review['checks'],report_cross_check_count=checks,independent_tests_passed=52,metrics=metrics,margin=margin,curve_checks=curvechecks,annual_continuous_year_slices=len(annual),same_data_settings_effective=True,long_gate_diagnostics=dict(count=review['long_decision_count'],would_block=review['long_would_block_count'],positive_size_applied_block=review['long_applied_block_count'],breakout_exempt_decisions=review['long_breakout_exempt_count'],actual_breakout_fills=len(breakouts),actual_native_by_signal=review['long_actual_native_by_signal'],prior_prefix_min=min(x['available_daily_count'] for x in proofs),prior_prefix_max=max(x['available_daily_count'] for x in proofs),events_cache_starts_after_known_listing=sum(x['cache_first_after_known_listed_date'] for x in proofs),listing_completeness_proven=False),short_gate_diagnostics=dict(count=review['decision_count'],would_block=review['would_block_count'],positive_size_applied_block=review['blocked_decisions'],all100_source_and_rule_decisions_identical_to_stage006=True,capital_path_sizing_changed_count=short_changed_sizes),actual_open_context_counts=review['actual_open_context_counts'],slope_diagnostics_only=review['MA_slope_diagnostics_only'],cold_start_evidence=review['cold_start_warmup_evidence'],frozen_delivery_counts=counts,old_manifest_sha256=manifests,reviewed_code_sha256=codes,core_proof_sha256=proofshas,report_comparison_sha256=sha(R/'comparison.json'),actual_breakout_evidence_sha256=sha(bo),tests_log_sha256=sha(L/'stages/stage007_independent_tests.log'),fixed_candidate_gates_vs=gates,difference_vs=diffs,end_equity_bridges=bridges,strategy_verdict_vs_short_only=doc['strategy_verdict_vs_short_only'],promotion_decision='NO_PROMOTION',production_qualified=False,financial_replays=0,market_downloads=0,production_accesses=0,actual_strategy_run_interval=dict(started_at=terminal['started_at'],completed_at=terminal['completed_at']),limitations=['All available approved same-epoch cached history is not proven complete listing history;22 long and7 short decision prefixes start later than known listing date;2014 warmup/lifecycle/data gaps inherited.','Repeated same-history structural changes are not OOS evidence; all three economic gates vs short_only fail, no rescue scan.','Zero commission, static margin x1.65 and daily-next-open do not prove historical actual broker margin, minute liquidity, capacity or production readiness.','99 positive-size veto decisions are not99 proven counterfactual fills;13 breakout exemption diagnostics are11 actual new long fills.','Whole-account differences include dynamic equity/integer sizing/risk/opportunity feedback;100 identical short source decisions still have80 capital-path sizing differences.'])
(L/'stages/stage007_independent_final.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k not in ['metrics','reviewed_code_sha256','old_manifest_sha256','core_proof_sha256']},ensure_ascii=False))
