"""Fresh mathematical audit of saved YTD fills/MTM/cash; never replay an engine."""
from pathlib import Path
from collections import defaultdict,deque
import ast,csv,hashlib,json,math,re
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[4];D=Path(__file__).resolve().parent;LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate'
OLD=Path('/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian');L=OLD/'research/lines/futures_weekly_short_ma_slope_gate';RUN=L/'outputs/stage014_C_20260101_attempt001';DATA=L/'outputs/data_stage014_20261030/data_approved';START='2026-01-01';END='2026-10-30';checks=0;cache={}
def sha(p):
 p=Path(p);key=str(p);st=p.stat();finger=(st.st_size,st.st_mtime_ns,st.st_ctime_ns)
 if key in cache and cache[key][0]==finger:return cache[key][1]
 h=hashlib.sha256()
 with p.open('rb')as f:
  for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
 assert finger==(p.stat().st_size,p.stat().st_mtime_ns,p.stat().st_ctime_ns);cache[key]=(finger,h.hexdigest());return h.hexdigest()
def ok(v,label):
 global checks;checks+=1
 if not v:raise AssertionError(label)
def near(a,b,label):ok(np.allclose(a,b,rtol=0,atol=1e-6,equal_nan=False),label)
load=lambda p:json.loads(Path(p).read_text());oldreceipt_path=D/'stage014_independent_receipts/2026-01-01_C.json';oldreceipt=load(oldreceipt_path);oldpins=oldreceipt['source_files_sha256']
ok(set(oldpins)=={str(p)for p in RUN.iterdir()if p.is_file()},'complete74run_output_set')
for p,want in oldpins.items():ok(sha(p)==want,'raw_output_sha:'+Path(p).name)
pre=load(RUN/'preflight.json');ok(pre['method']=='fresh_engine'and pre['start']==START and pre['end']==END and pre['engine_initial_capital']==pre['reserve_initial_capital']==150000,'fresh_run_identity')
cp_path=L/'outputs/stage014_multistart/checkpoints/2026-01-01_C.json';cp=load(cp_path);ok(sha(cp_path)==oldreceipt['checkpoint_sha256'] and cp['method']=='fresh_engine'and cp['reused']is False and cp['source_head']=='688754057ba1dc07caa9edc537ceec486f678372','original_fresh_checkpoint')
eff=load(RUN/'effective_parameters.json');sizes=eff['sizes'];slips=eff['slippages'];rates=eff['rates'];actual=load(RUN/'actual_strategy_settings.json')[0]['actual']
daily=pd.read_csv(RUN/'daily.csv');bridge=pd.read_csv(RUN/'reserve_daily.csv');fills=pd.read_csv(RUN/'trades.csv');clock=pd.read_csv(RUN/'execution_clock.csv');pos=pd.read_csv(RUN/'positions.csv',usecols=['date','vt_symbol','start_pos','end_pos','pre_close','close_price','net_pnl','holding_pnl','trading_pnl','commission','slippage','trade_count']);internal=pd.read_csv(RUN/'internal_equity_daily.csv')
mapping=pd.read_csv(DATA/'mapping.csv',usecols=['date']);dates=sorted(d for d in mapping.date.unique()if START<=d<=END);ok(daily.date.tolist()==bridge.date.tolist()==dates and len(dates)==198 and dates[0]=='2026-01-05'and dates[-1]==END,'actual198calendar')
warm=pos.loc[pos.date.lt(START)];near(warm[['start_pos','end_pos','net_pnl','commission','slippage','trade_count']].to_numpy(),0,'no_warmup_financial_inventory');near(internal.loc[internal.date.lt(START),['estimated_equity','settled_balance']],150000,'warmup_fresh_cash');near(pos.loc[pos.date.eq(dates[0]),['start_pos','end_pos','net_pnl','commission','slippage','trade_count']],0,'first_day_flat');ok(fills.trade_id.tolist()==[f'BACKTESTING.{i}'for i in range(1,len(fills)+1)],'fresh_trade_ids');ok(fills.trading_date.ge(START).all()and fills.trading_date.le(END).all(),'fills_within_window');ok(pd.to_datetime(fills.datetime).is_monotonic_increasing,'chronological_fills');ok(clock.trade_id.tolist()==fills.trade_id.tolist()and clock.trading_date.tolist()==fills.trading_date.tolist(),'execution_clock_binding')
physical=pd.read_csv(DATA/'physical_epoch_daily.csv',usecols=['vt_symbol','date','contract_epoch_id','open','close','high','low','volume','close_oi']);source=physical.set_index(['vt_symbol','date']);byfill=defaultdict(list)
for r in fills.itertuples():
 ok(r.direction in ('多','空')and r.offset in ('开','平')and r.volume>0 and r.volume==int(r.volume),'native_fill_shape');near(r.price,source.loc[(r.vt_symbol,r.trading_date),'open'],'declared_next_daily_open');byfill[(r.trading_date,r.vt_symbol)].append(r)
active=pos.loc[pos.date.ge(START)&pos[['start_pos','end_pos','net_pnl','commission','slippage','trade_count']].abs().sum(axis=1).ne(0)].sort_values(['date','vt_symbol']);predpnl=defaultdict(float);predcost=defaultdict(float);predfee=defaultdict(float);count=defaultdict(int);carry=defaultdict(float);marks={};seenfills=set()
for p in active.itertuples():
 size=float(sizes[p.vt_symbol]);slip=float(slips[p.vt_symbol]);rate=float(rates[p.vt_symbol]);near(p.start_pos,carry[p.vt_symbol],'position_start_inventory');near(p.close_price,source.loc[(p.vt_symbol,p.date),'close'],'physical_close_mark')
 if p.start_pos:near(p.pre_close,marks[p.vt_symbol],'holding_previous_mark')
 fs=byfill.get((p.date,p.vt_symbol),[]);signed=lambda f:(1 if f.direction=='多'else-1)*f.volume
 holding=p.start_pos*(p.close_price-p.pre_close)*size;trading=sum(signed(f)*(p.close_price-f.price)*size for f in fs);cost=sum(f.volume*size*slip for f in fs);fee=sum(f.volume*size*f.price*rate for f in fs);net=holding+trading-cost-fee
 near(p.end_pos,p.start_pos+sum(signed(f)for f in fs),'position_end_inventory');near([p.holding_pnl,p.trading_pnl,p.slippage,p.commission,p.net_pnl,p.trade_count],[holding,trading,cost,fee,net,len(fs)],'per_contract_MTM_costs');carry[p.vt_symbol]=p.end_pos;marks[p.vt_symbol]=p.close_price;predpnl[p.date]+=net;predcost[p.date]+=cost;predfee[p.date]+=fee;count[p.date]+=len(fs);seenfills.update(f.trade_id for f in fs)
ok(seenfills==set(fills.trade_id),'all_fills_accounted_once');near(list(carry.values()),0,'terminal_all_positions_flat')
for r in daily.itertuples():near([r.net_pnl,r.slippage,r.commission,r.trade_count],[predpnl[r.date],predcost[r.date],predfee[r.date],count[r.date]],'daily_MTM_sum')
# FIFO cash/inventory is independently reconstructed from raw fills, not daily PnL.
inventory=defaultdict(deque);roundacc=defaultdict(float);roundmeta={};rounds=[];grossclosed=0.;allcost=0.;fees=0.;E_fifo=[];settled_fifo=[];eventrows=load(RUN/'reserve_events.json');transfers=defaultdict(float)
for event in eventrows:transfers[event['date']]+=event['transfer_amount']
T=0.
for day in dates:
 for r in fills.loc[fills.trading_date.eq(day)].itertuples():
  sym=r.vt_symbol;size=float(sizes[sym]);q=float(r.volume);sgn=1 if r.direction=='多'else-1;fee=q*size*r.price*float(rates[sym]);cost=q*size*float(slips[sym])+fee;fees+=fee;allcost+=cost
  if r.offset=='开':
   ok(not inventory[sym]or inventory[sym][0][2]==sgn,'no_opposing_open');inventory[sym].append([q,r.price,sgn]);roundacc[sym]-=cost;roundmeta.setdefault(sym,dict(vt_symbol=sym,opened_on=day,trade_ids=[]))['trade_ids'].append(r.trade_id)
  else:
   remaining=q;gross=0.;ok(bool(inventory[sym]),'close_requires_inventory');roundmeta[sym]['trade_ids'].append(r.trade_id)
   while remaining:
    lot=inventory[sym][0];ok(lot[2]==-sgn,'close_direction_matches_inventory');take=min(remaining,lot[0]);gross+=take*(r.price-lot[1])*size*lot[2];remaining-=take;lot[0]-=take
    if lot[0]==0:inventory[sym].popleft()
   grossclosed+=gross;roundacc[sym]+=gross-cost
   if not inventory[sym]:rounds.append(dict(roundmeta.pop(sym),closed_on=day,net_pnl=roundacc[sym]));roundacc[sym]=0.
 T+=transfers[day];unrealized=sum(q*(float(source.loc[(sym,day),'close'])-price)*float(sizes[sym])*sgn for sym,lots in inventory.items()for q,price,sgn in lots);settled=150000.+grossclosed-allcost+T;settled_fifo.append(settled);E_fifo.append(settled+unrealized)
Tseries=np.cumsum([transfers[d]for d in dates]);pnl=daily.net_pnl.cumsum().to_numpy();E=150000.+pnl+Tseries;R=150000.-Tseries;W=300000.+pnl
near(E_fifo,E,'FIFO_cash_unrealized_vs_daily_MTM');near(bridge.trading_account_equity,E,'E_daily');near(bridge.reserve_balance,R,'R_daily');near(bridge.total_account_equity,W,'W_daily');near(E+R,W,'wealth_conservation');near(bridge.cumulative_transfer,Tseries,'all_transfer_daily_bridge');near(daily.account_equity,150000.+pnl,'raw_cashflow_neutral_account');ok((R>=0).all(),'no_reserve_overdraft')
i=internal.loc[internal.date.isin(dates)].set_index('date').loc[dates];near(i.estimated_equity,E,'internal_E');near(i.settled_balance,E,'internal_daily_MTM_settlement_wallet')
checksrows=load(RUN/'reserve_checks.json');total=0.;seen=set();rawE=dict(zip(dates,150000.+pnl));checkevents=[]
for r in checksrows:
 near(r['raw_account_equity'],rawE[r['date']],'funding_fill_before_signal_mark');near(r['trading_equity_before'],rawE[r['date']]+total,'funding_actual_before');near(r['reserve_before'],150000.-total,'funding_before_R')
 native=(r['direction']=='long'and r['signal']in ('long_case1a','long_case2'))or(r['direction']=='short'and r['signal']=='short_case1a');eligible=bool(r['enabled']and r['entry_context']in ('flat_entry','reverse_entry')and native and r['weekly_stop_valid']and not r['range_would_block']);ok(r['eligible']==eligible,'funding_qualification');duplicate=eligible and r['candidate_key']in seen;ok(r['duplicate']==duplicate,'funding_dedup')
 if eligible:seen.add(r['candidate_key'])
 want=min(max(150000.-r['trading_equity_before'],0),150000.-total)if eligible and not duplicate else 0.;near(r['transfer_amount'],want,'funding_min_gap_R');total+=want;near([r['cumulative_transfer'],r['trading_equity_after'],r['reserve_after']],[total,r['trading_equity_before']+want,150000.-total],'funding_after')
 if want:checkevents.append(r)
near(total,Tseries[-1],'funding_total');ok(len(checkevents)==len(eventrows),'funding_event_count');ok(all(not x['post_sizing_fill']for x in load(RUN/'reserve_fill_phases.json')),'all_fills_before_same_day_signals')
ys=[r['net_pnl']for r in rounds];wins=[x for x in ys if x>0];losses=[-x for x in ys if x<0];near(sum(ys),pnl[-1],'closed_cycles_equal_total_PnL');ok(not any(inventory.values()),'terminal_FIFO_empty');near(allcost-fees,daily.slippage.sum(),'total_slippage');near(fees,0,'zero_fees')
previous=np.r_[150000.,E[:-1]];returns=(E-previous)/previous;dd=100*(E/np.maximum.accumulate(np.r_[150000.,E])[1:]-1);trough=int(np.argmin(dd));peak=int(np.argmax(E[:trough+1]))
metrics=dict(initial_trading=150000.,requested_start=START,actual_start=dates[0],actual_end=dates[-1],trading_days=len(dates),end_equity=float(E[-1]),external_topup=float(Tseries[-1]),net_trading_pnl=float(pnl[-1]),reserve_remaining=float(R[-1]),total_wealth=float(W[-1]),account_growth_including_T_pct=float((E[-1]/150000.-1)*100),net_pnl_over_initial_trading_pct=float(pnl[-1]/150000.*100),max_drawdown_pct=float(dd.min()),sharpe=float(returns.mean()/returns.std(ddof=1)*np.sqrt(252)),slippage=float(allcost-fees),commission=float(fees),fills=len(fills),closed_rounds=len(ys),wins=len(wins),losses=len(losses),flat=len(ys)-len(wins)-len(losses),win_rate_pct=len(wins)/len(ys)*100,mean_win=float(np.mean(wins)),mean_loss_abs=float(np.mean(losses)),payoff_ratio=float(np.mean(wins)/np.mean(losses)),profit_factor=float(sum(wins)/sum(losses)),terminal_open_net_mtm=0.,peak_date=dates[peak],peak_equity=float(E[peak]),trough_date=dates[trough],trough_equity=float(E[trough]),min_equity=float(E.min()),static_margin165_peak_pct=float((daily.total_margin_exact.to_numpy()*1.65/E*100).max()))
# Rebind current m2 fixed strategy sources to original research, not inherited C9 labels.
m2=ROOT/'official_strategy_materials/official_live_weekly19_base15w_reserve15w_stage014/releases/m0002_20261101T050816+0800_e89fdcbb6826';manifest=load(m2/'manifest.json');manifestfiles={r['logical_path']:r for r in manifest['files']};assetpath='examples/portfolio_backtesting/weekly19_assets/actual_settings.json';sourcepath='examples/portfolio_backtesting/weekly19_assets/source_manifest.json';asset=load(ROOT/assetpath);sm=load(ROOT/sourcepath)
for path in [assetpath,sourcepath]:ok(sha(ROOT/path)==sha(m2/'payload'/path)==manifestfiles[path]['sha256'],'m2_asset_bytes')
settings=asset['settings'];ok(set(settings)==set(actual)and len(settings)==170,'all_strategy_parameter_keys');delta={k:dict(research=actual[k],m2=settings[k])for k in settings if settings[k]!=actual[k]};ok(set(delta)==set(asset['path_relocations'])|{'trade_start_date'},'only_start_and_four_path_relocations');ok(actual['trade_start_date']==START,'actual_fresh_start')
for k,want in [('risk_ratio_of_total_assets',.018),('risk_ratio_volume_open_interest_surge',.06),('risk_ratio_open_interest_surge',.06),('risk_ratio_open_interest_decline',.025),('min_risk_per_trade',1000.)]:near(settings[k],want,'fixed_original_risk:'+k)
static=pd.read_csv(ROOT/'examples/portfolio_backtesting/weekly19_assets/static19.csv');products=sorted(static.product_vt_symbol.unique());ok(products==pre['universe_products']and len(products)==19,'fixed19_universe')
def nodes(raw):
 result={}
 def walk(n,prefix=''):
  name=prefix
  if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
   name=(prefix+'.'if prefix else'')+n.name;result[name]=hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest()
  for child in ast.iter_child_nodes(n):walk(child,name)
 walk(ast.parse(raw));return result
alpha=[];definition_count=0
for name,row in sm['files'].items():
 path='examples/portfolio_backtesting/weekly19_frozen/'+name;copied=(ROOT/path).read_bytes();old=(OLD/row['source_path']).read_bytes();ok(hashlib.sha256(old).hexdigest()==row['source_sha256'],'original_alpha_source:'+name);ok(sha(ROOT/path)==sha(m2/'payload'/path)==row['copy_sha256']==manifestfiles[path]['sha256'],'m2_locked_alpha:'+name);a,b=nodes(old),nodes(copied)
 for n,want in row['methods'].items():ok(a[n]==b[n]==want,'exact_original_definition:'+n);definition_count+=1
 alpha.append(dict(path=path,sha256=row['copy_sha256'],original_source_path=row['source_path'],original_sha256=row['source_sha256']))
ok(len(alpha)==31 and definition_count==565,'complete_alpha_identity')
# Current entry-risk amounts are rechecked from the recorded actual capital.
risk=pd.read_csv(RUN/'entry_risk.csv');tiers={'regular':.018,'breakout':.018,'ma_cross_breakout':.018,'volume_open_interest_surge':.06,'open_interest_surge':.06,'open_interest_decline':.025}
for r in risk.itertuples():
 near(r.risk_ratio,tiers[r.risk_mode],'actual_entry_rate');budget=min(actual['max_risk_per_trade'],max(1000.,r.limited_balance*r.risk_ratio))*max(0.,r.risk_multiplier);near(r.risk_amount_before_directional_30d_boost,budget,'risk_budget_before_directional');near(r.target_risk_amount,budget*r.directional_30d_risk_boost_multiplier,'risk_budget_after_directional')
for p,want in oldpins.items():ok(sha(p)==want,'raw_stable_after:'+Path(p).name)
out=dict(schema='Stage019.independent-raw-YTD-audit.v2',audit_adapter_correction={'failed_attempt':'Stage019_review_raw_attempt001.log','reason':'Naive FIFO realized-cash partition differs from strategy daily MTM-settled wallet. Source resets settled_balance=estimated_equity after on_bars; compare both captured wallets to independently reconstructed daily E. FIFO realized plus open MTM remains independently checked against E. No raw, strategy, or financial parameter changes.','strategy_source_lines':[1811,3411,3443],'historical_audit':'stage009_independent_window.py:108'},accepted=True,status='PASS_WITH_LIMITATIONS',metrics=metrics,checks=checks,source_run=str(RUN),original_run_method='fresh_engine',current_method='verified_existing_fresh_engine_window',new_financial_replays=0,old_receipt_sha256=sha(oldreceipt_path),checkpoint_sha256=sha(cp_path),raw_files_sha256={p:sha(p)for p in oldpins},source_data_sha256={str(DATA/n):sha(DATA/n)for n in ['daily.sqlite','mapping.csv','physical_epoch_daily.csv','metadata.csv','receipt.json']},m2_manifest_sha256=sha(m2/'manifest.json'),m2_source_commit=manifest['source_commit'],m2_strategy_settings_sha256=sha(ROOT/assetpath),allowed_settings_deltas=delta,m2_original_alpha_files=alpha,original_definitions_compared=definition_count,initial_warmup_fresh=True,source_qualified=False,production_qualified=False,qualification='single 198-day observed-history research window; not official multicycle validation',limitations=['Zero commissions','Fixed slippage','Static margin estimate multiplier1.65','Incomplete historical PIT/lifecycle/capacity evidence','Declared next daily open, no tick executable capacity proof','Research immediate topup vs manual real transfer timing not equivalent'])
p=D/'Stage019_review_raw_result.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');pd.DataFrame(rounds).to_csv(D/'Stage019_review_closed_rounds.csv',index=False);print(json.dumps(dict(status=out['status'],checks=checks,metrics=metrics,result_sha256=sha(p)),ensure_ascii=False))
