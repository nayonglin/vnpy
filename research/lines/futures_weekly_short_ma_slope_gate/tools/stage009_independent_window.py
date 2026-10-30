"""Independent raw fill/PnL audit plus separate real internal-wallet reconstruction."""
from pathlib import Path
from collections import defaultdict
import argparse,ast,copy,hashlib,inspect,json,math,sys
import numpy as np
import pandas as pd
import stage008_independent_window as raw_audit
ROOT=Path(__file__).resolve().parents[4];L=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';DATA=L/'outputs/data_stage001_20261029/data_approved';checks=0
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8388608),b''):h.update(b)
 return h.hexdigest()
def ok(v,label):
 global checks;checks+=1
 if not v:raise AssertionError(label)
def near(a,b,label):ok(math.isfinite(float(a)) and math.isfinite(float(b)) and math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-6),label)
def raw_aux_sharpe(equity):
 # Exact frozen s650 diagnostic convention, not a wealth return definition.
 r=pd.Series(equity,dtype=float).pct_change().replace([np.inf,-np.inf],np.nan).fillna(0.);std=float(r.std(ddof=1))
 return 0. if not math.isfinite(std) or std<=0 else float(r.mean()/std*math.sqrt(252.))
def raw_audit_adapter():
 original=ast.parse(inspect.getsource(raw_audit.audit));tree=copy.deepcopy(original);fn=tree.body[0];changed=0
 for node in ast.walk(fn):
  if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='dict' and {'end_equity','total_return_pct','max_dd_pct','sharpe'}<={x.arg for x in node.keywords}:
   for arg in node.keywords:
    if arg.arg=='sharpe':arg.value=ast.Call(func=ast.Name(id='_stage009_raw_aux_sharpe',ctx=ast.Load()),args=[ast.Name(id='eq',ctx=ast.Load())],keywords=[]);changed+=1
 if changed!=1:raise AssertionError('one_exact_raw_aux_sharpe_expression_required')
 fn.name='_stage009_wallet_raw_audit';env=vars(raw_audit);env['_stage009_raw_aux_sharpe']=raw_aux_sharpe;exec(compile(ast.fix_missing_locations(tree),str(Path(__file__))+'::raw_aux_sharpe_adapter','exec'),env)
 proof=dict(changed_expressions=changed,original_function_AST_sha256=hashlib.sha256(ast.dump(original,include_attributes=False).encode()).hexdigest(),adapted_function_AST_sha256=hashlib.sha256(ast.dump(tree,include_attributes=False).encode()).hexdigest(),scope='Only auxiliary raw150k Sharpe diagnostic uses exact frozen s650 pct_change/inf-to-NaN/fill0; all fills/PnL/inventory/fees/positions/calendar/flags and cash conservation unchanged; original file/function not replaced.')
 return env['_stage009_wallet_raw_audit'],proof
def native_allowed(row,actual):
 signal=row['signal'];direction=row['direction'];return (direction=='long' and signal in {'long_case1a','long_case2'} and actual['long_entry_enabled']) or (direction=='short' and signal=='short_case1a' and actual['short_entry_enabled'])
def audit(path,arm,start,end,freeze_path,control=None):
 frozen_sha=sha(freeze_path);frozen=json.loads(freeze_path.read_text());ok(frozen['planned_arm_windows']==46 and frozen['planned_financial_replays']==46,'all46_new');ok(frozen['engine_initial_capital']==frozen['reserve_initial_capital']==150000 and frozen['total_initial_capital']==300000,'capital_contract')
 for name,h in frozen['source_files_sha256'].items():
  p=Path(name);p=p if p.is_absolute() else ROOT/p;ok(p.is_file() and sha(p)==h,'freeze_source:'+name)
 raw_audit.REQUESTED_START=start;raw_audit.REQUESTED_END=end;raw_audit.CONTROL=control;raw_audit.ARM=arm;raw_audit.LEGACY_NO_PRICE=False;raw_audit.checks=0
 old_source=Path(raw_audit.__file__);old_hash=sha(old_source);raw_function,raw_adapter=raw_audit_adapter()
 with np.errstate(divide='ignore',invalid='ignore'):raw=raw_function(path)
 ok(sha(old_source)==old_hash,'old_raw_auditor_unchanged')
 pre=json.loads((path/'preflight.json').read_text());ok(pre['arm']==arm and pre['head']==pre['frozen_source_head']==frozen['source_head'] and pre['freeze_sha256']==frozen_sha and pre['data_identity']==frozen['data_identity'],'actual_frozen_identity');ok(pre['reserve_topup_enabled'] is True and pre['engine_initial_capital']==pre['reserve_initial_capital']==150000 and pre['total_initial_capital']==300000,'actual_two_buckets')
 source=pd.read_csv(DATA/'physical_epoch_daily.csv',dtype={'date':str,'vt_symbol':str,'contract_epoch_id':str});lookup={(r.vt_symbol,r.date):r for r in source.itertuples()};groups={(sym,epoch):g.sort_values('date') for (sym,epoch),g in source.groupby(['vt_symbol','contract_epoch_id'])}
 daily=pd.read_csv(path/'daily.csv');daily.date=daily.date.astype(str).str[:10];days=daily.date.tolist();dayraw=dict(zip(days,daily.account_equity));settings=json.loads((path/'actual_strategy_settings.json').read_text());actual=settings[0]['actual'];events=json.loads((path/'reserve_events.json').read_text());calls=json.loads((path/'reserve_checks.json').read_text());snaps=json.loads((path/'reserve_snapshots.json').read_text());phase=json.loads((path/'reserve_fill_phases.json').read_text());proof=json.loads((path/'reserve_acceptance.json').read_text());fills=pd.read_csv(path/'trades.csv');anchors=pd.read_csv(path/'execution_anchor_requests.csv');effective=json.loads((path/'effective_parameters.json').read_text());candidates=pd.read_csv(path/'entry_candidates.csv');stoplog=pd.read_csv(path/'initial_stop_audit.csv');invalid=pd.read_csv(path/'invalid_weekly_stop_rejections.csv')
 ok(proof['accepted'] is True and proof['enabled'] is True and proof['event_count']==len(events) and proof['check_count']==len(calls) and proof['snapshot_count']==len(snaps),'real_reserve_counts')
 flags=proof['actual_risk_flags'];ok(pre['actual_reserve_risk_flags']==flags,'actual_risk_flags_same')
 for k in ['enable_portfolio_volatility_budget','enable_portfolio_volatility_budget_deleverage','enable_portfolio_overheat_cooldown','enable_portfolio_overheat_cooldown_deleverage']:ok(flags[k] is False,'no_false_cashflow_return_history:'+k)
 for k in ['enable_risk_cluster_heat_deleverage','enable_risk_cluster_margin_cap']:ok(flags[k] is True,'original_risk_retained:'+k)
 ok(proof['next_open_execution_cash_guard_added'] is False and proof['internal_transfers_are_not_profit'] is True,'no_new_execution_gate')
 seen=set();cum=0.;reserve=150000.;eventindex=0;previous='';byday=defaultdict(float);eligibility={};contexts=defaultdict(int);blockedC=invalidstop=duplicates=0
 for r in calls:
  day=str(r['date'])[:10];contexts[r['entry_context']]+=1;ok(day>=previous,'ordered_signal_checks');previous=day;ok(r['enabled'] is True,'actual_reserve_enabled');inwindow=day>=start;rawvalue=dayraw[day] if inwindow else 150000.;before=rawvalue+cum;near(r['trading_equity_before'],before,'real_MTM_before');near(r['reserve_before'],reserve,'reserve_before_chain');near(r['raw_account_equity'],rawvalue,'signal_real_raw_day_anchor')
  basic=inwindow and r['entry_context'] in {'flat_entry','reverse_entry'} and native_allowed(r,actual);eligible=False;dup=False
  if basic:
   real=lookup[(r['vt_symbol'],day)];stop=float(r['weekly_stop_price']);valid=stop<float(real.close) if r['direction']=='long' else stop>float(real.close);ok(math.isfinite(stop) and stop>0 and r['weekly_stop_valid']==valid,'stop_direction_validity')
   selected=stoplog.loc[stoplog.vt_symbol.eq(r['vt_symbol'])&stoplog.date.astype(str).str[:10].eq(day)&stoplog.direction.eq(r['direction'])] if not stoplog.empty else stoplog
   if valid:
    ok(len(selected)>0 and any(math.isclose(float(x),stop,rel_tol=1e-10,abs_tol=1e-7) for x in selected.stop_price),'qualification_equals_original_parent_stop')
   else:invalidstop+=1
   would=False
   if valid and arm=='C' and r['direction']=='short':
    g=groups[(r['vt_symbol'],real.contract_epoch_id)];g=g.loc[g.date.le(day)];low=float(g.low.min());high=float(g.high.max());would=high==low or float(real.close)<=low+.2*(high-low);ok(r['range_checked'] is True and r['range_would_block']==would and r['range_contract_epoch_id']==real.contract_epoch_id,'C_real_same_epoch_range');near(r['range_low'],low,'C_range_low');near(r['range_high'],high,'C_range_high');ok(r['range_history_end']==day,'C_signal_inclusive');blockedC+=int(would)
   eligible=valid and not would
  ok(r['eligible']==eligible,'eligibility_independent');amount=0.
  if eligible:
   dup=r['candidate_key'] in seen
   if not dup:seen.add(r['candidate_key']);amount=min(max(150000.-before,0.),reserve)
  ok(r['duplicate']==dup,'duplicate_candidate_semantics');duplicates+=int(dup);near(r['transfer_amount'],amount,'exact_deficit_bounded_reserve');cum+=amount;reserve-=amount;byday[day]+=amount
  near(r['trading_equity_after'],before+amount,'trading_after');near(r['reserve_after'],reserve,'reserve_after');near(r['cumulative_transfer'],cum,'signal_cumulative');near(r['total_account_equity'],rawvalue+150000.,'wealth_does_not_change_on_transfer')
  if before+amount<=0:ok(r['selected_volume_after_parent']==0,'no_zero_equity_fallback_credit')
  if amount:
   ok(eventindex<len(events),'event_exists_for_positive_check');e=events[eventindex];eventindex+=1;ok(e['event_id']==eventindex and e['candidate_key']==r['candidate_key'],'unique_ordered_transfer_identity')
   for k in ['date','vt_symbol','direction','signal','entry_context','phase','weekly_stop_valid','weekly_stop_week_end','range_checked','range_would_block']:ok(e[k]==r[k],'event_matches_real_signal_check:'+k)
   for k in ['transfer_amount','trading_equity_before','trading_equity_after','reserve_before','reserve_after','cumulative_transfer','raw_account_equity','total_account_equity']:near(e[k],r[k],'event_matches_check:'+k)
   ok(r['phase']=='before_parent_sizing','funding_before_only_parent_sizing')
 ok(eventindex==len(events),'no_extra_or_missing_events');near(proof['cumulative_transfer'],cum,'actual_terminal_cumulative');near(proof['reserve_balance'],reserve,'actual_terminal_reserve')
 # Every ordinary fill must have a phase record; no signal-day fill after sizing.
 counts=defaultdict(int)
 for p in phase:
  n=int(p['fill_count']);near(p['trade_count_after']-p['trade_count_before'],n,'phase_counter_delta');ok(n>=0 and p['post_sizing_fill']==bool(p['reserve_same_day_checks_before'] and n>0),'phase_marker');ok(not p['post_sizing_fill'],'strict_pre_signal_fill_queue');tt=fills.loc[fills.order_id.astype(str).eq(str(p['order_id']))];ok(len(tt)==n and (tt.empty or tt.trading_date.eq(str(p['date'])[:10]).all()),'all_phase_fills_exact_order_anchor');counts[str(p['date'])[:10]]+=n
 for d in daily.itertuples():near(counts[d.date],d.trade_count,'phase_all_daily_fills')
 bridge=pd.read_csv(path/'reserve_daily.csv');ok(bridge.date.astype(str).str[:10].tolist()==days,'full_bucket_calendar');cumulative=0.;trading={};wallet={}
 for row,d in zip(bridge.itertuples(),daily.itertuples()):
  cumulative+=byday[d.date];T=float(d.account_equity)+cumulative;R=150000.-cumulative;W=float(d.account_equity)+150000.;trading[d.date]=T;wallet[d.date]=(cumulative,R,W)
  for name,want in [('raw_account_equity',d.account_equity),('transfer_amount',byday[d.date]),('cumulative_transfer',cumulative),('trading_account_equity',T),('reserve_balance',R),('total_account_equity',W),('net_pnl',d.net_pnl),('slippage',d.slippage),('commission',d.commission),('trade_count',d.trade_count)]:near(getattr(row,name),want,'daily_wallet:'+name)
  ok(R>=-1e-7,'reserve_never_negative');near(T+R,W,'daily_internal_wealth_bridge')
 # Reconstruct each actual update_trade snapshot from marked prior positions and
 # the exact prefix of real fills, rather than trusting event/snapshot claims.
 holdings=defaultdict(float)
 for chunk in pd.read_csv(path/'positions.csv',usecols=['date','vt_symbol','start_pos','pre_close','close_price'],chunksize=100000):
  q=chunk.loc[chunk.start_pos.ne(0)]
  for r in q.itertuples():holdings[str(r.date)[:10]]+=r.start_pos*(r.close_price-r.pre_close)*float(effective['sizes'][r.vt_symbol])
 def trade_number(x):return int(str(x).rsplit('.',1)[-1])
 frows=sorted(fills.to_dict('records'),key=lambda r:trade_number(r['trade_id']));fillindex=0;cost=0.;lastday='';prefix=0.;previousraw=150000.;end_previous={days[i]:150000. if i==0 else float(daily.account_equity.iloc[i-1]) for i in range(len(days))};seq=0;day_last={}
 for s in snaps:
  ok(s['sequence']==seq+1,'snapshot_complete_sequence');seq+=1;day=str(s['date'])[:10];ok(day in wallet,'snapshot_financial_scope');cum_s=float(s['cumulative_transfer']);raw_s=float(s['raw_account_equity']);ok(0<=cum_s<=150000,'snapshot_flow_bounds')
  if s['phase']=='after_update_trade':
   ok(fillindex<len(frows),'snapshot_real_fill_exists');t=frows[fillindex];fillindex+=1;ok(t['trading_date']==day,'snapshot_exact_fill_order_day')
   if day!=lastday:prefix=0.;lastday=day
   size=float(effective['sizes'][t['vt_symbol']]);slip=float(effective['slippages'][t['vt_symbol']]);rate=float(effective['rates'][t['vt_symbol']]);tc=float(t['volume'])*size*(slip+float(t['price'])*rate);cost+=tc;sign=1 if t['direction']=='多' else -1;prefix+=sign*float(t['volume'])*(float(lookup[(t['vt_symbol'],day)].close)-float(t['price']))*size-tc;expectedraw=end_previous[day]+holdings[day]+prefix;near(raw_s,expectedraw,'snapshot_real_marked_fill_prefix');near(s['trade_costs_total'],cost,'snapshot_actual_cost_prefix');priorcum=wallet[days[days.index(day)-1]][0] if days.index(day)>0 else 0.;near(cum_s,priorcum,'no_current_day_transfer_before_signals')
  elif s['phase'] in {'after_on_bars_settlement','runner_terminal'}:near(raw_s,dayraw[day],'snapshot_real_day_end');near(cum_s,wallet[day][0],'snapshot_day_end_actual_transfer')
  else:raise AssertionError('unknown_snapshot_phase')
  near(s['trading_account_equity'],raw_s+cum_s,'snapshot_true_trading_equity');near(s['reserve_balance'],150000.-cum_s,'snapshot_true_reserve');near(s['total_account_equity'],raw_s+150000.,'snapshot_true_wealth');day_last[day]=s
 ok(fillindex==len(frows) and set(day_last)==set(days),'all_fills_and_days_have_real_snapshots')
 for day,s in day_last.items():near(s['trading_account_equity'],trading[day],'last_real_snapshot_matches_daily_trading')
 internal=pd.read_csv(path/'internal_equity_daily.csv');internal=internal.loc[internal.date.astype(str).str[:10].ge(start)]
 ok(internal.date.astype(str).str[:10].tolist()==days,'captured_internal_equity_full_calendar')
 for r in internal.itertuples():near(r.estimated_equity,trading[str(r.date)[:10]],'captured_actual_wallet_equity');near(r.settled_balance,trading[str(r.date)[:10]],'actual_settlement_wallet_equity')
 e=bridge.total_account_equity.to_numpy();returns=np.diff(np.r_[300000.,e])/np.r_[300000.,e][:-1];dd=100*(e/np.maximum.accumulate(np.r_[300000.,e])[1:]-1);total=dict(initial_capital=300000.,end_equity=float(e[-1]),total_return_pct=float((e[-1]/300000.-1)*100),max_dd_pct=float(dd.min()),sharpe=float(returns.mean()/returns.std(ddof=1)*np.sqrt(252)) if returns.std(ddof=1)>0 else 0.,total_slippage=raw['metrics']['total_slippage'],total_trade_count=raw['metrics']['total_trade_count'],rounds=raw['metrics']['rounds'],open_round_net_mtm=raw['metrics']['open_round_net_mtm'])
 reported=json.loads((path/'reserve_total_metrics.json').read_text())
 for k in ['end_equity','total_return_pct','max_dd_pct','sharpe','total_slippage','total_trade_count']:near(total[k],reported[k],'actual300k_reported:'+k)
 near(total['end_equity']-300000.,total['rounds']['closed_net_pnl']+total['open_round_net_mtm'],'no_transfer_profit_closed_open_bridge')
 ok(raw['source_files_sha256']=={str(p):sha(p) for p in path.iterdir() if p.is_file()},'attempt_immutable_during_funding_audit');ok(sha(freeze_path)==frozen_sha,'freeze_immutable')
 rawmetrics=raw.pop('metrics');auxrisk=raw.pop('risk');T=bridge.trading_account_equity;W=bridge.total_account_equity;margin=daily.total_margin_exact*1.65;risk=dict(configured_margin_max_trading_pct=float((margin/T.where(T.gt(0))*100).max()),configured_margin_over100_trading_days=int((margin/T.where(T.gt(0))*100).gt(100).sum()),configured_margin_undefined_trading_days=int(T.le(0).sum()),configured_margin_max_total_pct=float((margin/W.where(W.gt(0))*100).max()),configured_margin_over100_total_days=int((margin/W.where(W.gt(0))*100).gt(100).sum()),nonpositive_trading_equity_days=int(T.le(0).sum()),nonpositive_total_equity_days=int(W.le(0).sum()),minimum_trading_equity=float(T.min()),minimum_total_equity=float(W.min()))
 return dict(**raw,status='PASS_WITH_LIMITATIONS',P0=0,P1=0,P2=0,failures=0,metrics=total,raw_metrics=rawmetrics,risk=risk,raw_auxiliary_risk=auxrisk,raw_aux_sharpe_adapter=raw_adapter,raw_core_checks=raw_audit.checks,funding_checks=checks,freeze_sha256=frozen_sha,frozen_source_head=frozen['source_head'],arm=arm,requested_start=start,end=end,reused=False,old_raw_auditor_sha256=old_hash,old_raw_auditor_source=str(old_source),auditor_source_sha256=sha(Path(__file__)),reserve_diagnostics=dict(signal_checks=len(calls),transfer_events=len(events),cumulative_transfer=cum,reserve_end=reserve,trading_end=trading[days[-1]],total_end=float(e[-1]),context_counts=dict(contexts),C_blocked_short_checks=blockedC,invalid_stop_checks=invalidstop,duplicates=duplicates,phase_rows=len(phase),real_snapshot_rows=len(snaps)),actual_risk_flags=flags,financial_replays=0,market_downloads=0,production_accesses=0)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--path',type=Path,required=True);ap.add_argument('--arm',choices=['A','C'],required=True);ap.add_argument('--start',required=True);ap.add_argument('--end',required=True);ap.add_argument('--freeze',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--control',type=Path);args=ap.parse_args()
 if args.output.exists():raise ValueError('immutable_independent_receipt_exists')
 result=audit(args.path,args.arm,args.start,args.end,args.freeze,args.control);args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x))+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['source_files_sha256','range_prefix_proofs']},ensure_ascii=False,default=str))
if __name__=='__main__':main()
