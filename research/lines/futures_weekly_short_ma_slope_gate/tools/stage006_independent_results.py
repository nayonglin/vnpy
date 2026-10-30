"""Independent Stage006 2015 cold-start A/C financial and causal-range audit."""
from pathlib import Path
from collections import defaultdict,deque
import ast,hashlib,json,math,sqlite3,sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';DATA=LINE/'outputs/data_stage001_20261029/data_approved'
checks=0

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def ok(value,label):
 global checks;checks+=1
 if not value:raise AssertionError(label)
def close(a,b,label,tol=1e-6):ok(math.isfinite(float(a)) and math.isfinite(float(b)) and math.isclose(float(a),float(b),abs_tol=tol,rel_tol=1e-10),label)
def direction(s):
 if s in ['多','long','Direction.LONG']:return 1
 if s in ['空','short','Direction.SHORT']:return -1
 raise ValueError('unknown direction:'+str(s))
def stats(xs):
 w=[x for x in xs if x>1e-9];l=[-x for x in xs if x< -1e-9]
 return dict(count=len(xs),wins=len(w),losses=len(l),flat=len(xs)-len(w)-len(l),win_rate_pct=len(w)/len(xs)*100 if xs else 0,average_win=np.mean(w) if w else 0,average_loss_abs=np.mean(l) if l else 0,payoff_ratio=np.mean(w)/np.mean(l) if w and l else None,profit_factor=sum(w)/sum(l) if l else None,closed_net_pnl=sum(xs))
def audit(path):
 before={str(p):sha(p) for p in path.iterdir() if p.is_file()}
 pre=json.loads((path/'preflight.json').read_text());effective=json.loads((path/'effective_parameters.json').read_text());settings=json.loads((path/'actual_strategy_settings.json').read_text());actual=settings[0]['actual']
 for p,h in json.loads((path/'input_manifest.json').read_text()).items():ok(Path(p).is_file() and sha(p)==h,'input_binding:'+p)
 terminal=json.loads((path/'terminal.json').read_text());ok(terminal['status']=='completed_pending_independent_review' and terminal['error'] is None,'terminal_complete')
 ok(json.loads((path/'postflight.json').read_text())['inputs_unchanged'],'postflight')
 proofs={p.name:json.loads(p.read_text()) for p in path.glob('*_acceptance.json')}
 ok(all(v.get('accepted') is True for v in proofs.values()),'all_inherited_acceptances')
 ok(pre['daily_addon_enabled'] is False and pre['universe_product_count']==19 and pre['ready_need']==21 and pre['storage_capacity']==41 and pre['start']=='2015-01-01' and pre['end']=='2026-10-29','contract')
 ok([actual[x] for x in ['ma_short','ma_mid','ma_long']]==[5,10,20],'MAperiods')
 ok(pre.get('short_ma_slope_gate_enabled') is False and pre.get('long_ma_slope_gate_enabled') is False and pre.get('short_price_range_gate_enabled') is (pre['arm']=='C') and pre.get('short_price_range_threshold')==.2,'actual_range_only_no_MA_gates')
 for x in ['enable_stage847_half_r_stop_retry','enable_stage827_intraday_c2_stop','enable_rsi_partial_exit','enable_add_position','enable_donchian_add_position','enable_post_entry_quality_add','selection_pairwise_enabled','enable_selection_pairwise']:
  if x in actual:ok(actual[x] is False,'disabled:'+x)
 daily=pd.read_csv(path/'daily.csv');fills=pd.read_csv(path/'trades.csv');clock=pd.read_csv(path/'execution_clock.csv');anchors=pd.read_csv(path/'execution_anchor_requests.csv');dates=daily.date.astype(str).str[:10].tolist();calendar=sorted(pd.read_csv(DATA/'mapping.csv').date.unique())
 ok(dates==[d for d in calendar if '2015-01-01'<=d<='2026-10-29'],'full_calendar')
 ok(len(fills)==len(clock) and not fills.trade_id.duplicated().any(),'fill_clock_count')
 fills=fills.merge(clock[['trade_id','trading_date','execution_datetime']],on='trade_id',suffixes=('','_clock'),validate='one_to_one')
 ok(fills.trading_date.eq(fills.trading_date_clock).all(),'clock_trade_dates')
 am=dict(zip(anchors.order_id.astype(str),anchors.to_dict('records')));nextday=dict(zip(calendar[:-1],calendar[1:]));source=pd.read_csv(DATA/'physical_epoch_daily.csv',dtype={'vt_symbol':str,'date':str});lookup={(r.vt_symbol,r.date):r for r in source.itertuples()}
 def meta(sym):return (float(effective['sizes'][sym]),float(effective['slippages'][sym]),float(effective['rates'][sym]))
 byfill=defaultdict(list);net=defaultdict(float);inventory=defaultdict(deque);rounds=defaultdict(float);completed=[];closed_total=0;fees_total=0;slips_total=0;entry_fill_count=0
 for r in fills.itertuples():
  sym,day=r.vt_symbol,r.trading_date;anchor=am[str(r.order_id)];ok(anchor['trading_date']==day and nextday[str(anchor['signal_date'])[:10]]==day,'nextday_execution')
  src=lookup[(sym,day)];close(r.price,src.open,'same_contract_daily_open');ok(src.volume>0,'positive_fill_day');ok(float(r.volume)>0 and float(r.volume)==int(r.volume),'integer_fill')
  signed=direction(r.direction)*float(r.volume);size,slip,rate=meta(sym);cost=float(r.volume)*size*(slip+float(r.price)*rate);fees_total+=float(r.volume)*size*float(r.price)*rate;slips_total+=float(r.volume)*size*slip
  oldnet=net[sym];isopen=r.offset in ['开','open','Offset.OPEN'];q=float(r.volume)
  if isopen:
   ok(oldnet==0 or oldnet*signed>0,'open_direction');inventory[sym].append([q,float(r.price),direction(r.direction),cost/q]);rounds[sym]-=cost;entry_fill_count+=1
  else:
   ok(oldnet*signed<0 and q<=abs(oldnet),'close_inventory');remain=q;gross=0
   while remain>0:
    old=inventory[sym][0];n=min(remain,old[0]);pnl=n*(float(r.price)-old[1])*size*old[2]-n*old[3]-n*cost/q;closed_total+=pnl;gross+=n*(float(r.price)-old[1])*size*old[2];old[0]-=n;remain-=n
    if old[0]==0:inventory[sym].popleft()
   rounds[sym]+=gross-cost
  net[sym]+=signed
  if net[sym]==0:
   ok(not inventory[sym],'flat_inventory');completed.append(rounds[sym]);rounds[sym]=0
  byfill[(day,sym)].append((signed,float(r.price),float(r.volume)))
 # Financial rows only; source positions CSV includes zero prewarmup rows.
 cols=['date','vt_symbol','start_pos','end_pos','pre_close','close_price','net_pnl','slippage','commission','trade_count'];chunks=[]
 for c in pd.read_csv(path/'positions.csv',usecols=cols,chunksize=100000):
  financial=c[['start_pos','end_pos','net_pnl','slippage','commission','trade_count']].abs().sum(axis=1).ne(0);chunks.append(c.loc[financial])
 pos=pd.concat(chunks);ok(not pos.duplicated(['date','vt_symbol']).any(),'position_keys');carry=defaultdict(float);prevmark={};daypnl=defaultdict(float);dayfee=defaultdict(float);dayslip=defaultdict(float);daycount=defaultdict(int);presence=defaultdict(set);terminalmarks={}
 for r in pos.sort_values(['date','vt_symbol']).itertuples():
  day,sym=str(r.date)[:10],r.vt_symbol;ok(day in dates,'financial_window');presence[day].add(sym);close(r.start_pos,carry[sym],'held_start_inventory');src=lookup[(sym,day)];ok(src.volume>0,'held_positive_source');close(r.close_price,src.close,'real_position_mark')
  if r.start_pos:close(r.pre_close,prevmark[sym],'continuous_previous_mark')
  size,slip,rate=meta(sym);group=byfill.get((day,sym),[]);pred=r.start_pos*(r.close_price-r.pre_close)*size+sum(s*(r.close_price-p)*size for s,p,q in group)-sum(q*size*(slip+p*rate) for s,p,q in group)
  close(r.end_pos,r.start_pos+sum(s for s,p,q in group),'position_fill_conservation');close(r.net_pnl,pred,'daily_contract_mtm');close(r.slippage,sum(q*size*slip for s,p,q in group),'position_slip');close(r.commission,sum(q*p*size*rate for s,p,q in group),'position_fee');close(r.trade_count,len(group),'position_fill_count')
  carry[sym]=r.end_pos;prevmark[sym]=r.close_price;terminalmarks[sym]=r.close_price;daypnl[day]+=pred;dayslip[day]+=r.slippage;dayfee[day]+=r.commission;daycount[day]+=len(group)
 equity=150000.;equities=[]
 for r in daily.itertuples():
  day=str(r.date)[:10];equity+=daypnl[day];equities.append(equity);close(r.account_equity,equity,'equity_curve');close(r.net_pnl,daypnl[day],'daily_pnl');close(r.slippage,dayslip[day],'daily_slip');close(r.commission,dayfee[day],'daily_fee');close(r.trade_count,daycount[day],'daily_fills')
 for sym,q in net.items():close(q,carry[sym],'terminal_inventory')
 openround=0
 for sym,lots in inventory.items():
  size,slip,rate=meta(sym);mark=terminalmarks[sym];mtm=sum(q*(mark-price)*size*sign for q,price,sign,cost in lots);openround+=rounds[sym]+mtm
 close(sum(completed)+openround,equity-150000,'closed_open_pnl_total');close(slips_total,daily.slippage.sum(),'all_slippage');close(fees_total,daily.commission.sum(),'all_fees')
 eq=np.array(equities);ret=np.diff(np.r_[150000.,eq])/np.r_[150000.,eq][:-1];dd=(eq/np.maximum.accumulate(np.r_[150000.,eq])[1:]-1)*100
 metrics=dict(end_equity=equity,total_return_pct=(equity/150000.-1)*100,max_dd_pct=dd.min(),sharpe=ret.mean()/ret.std(ddof=1)*math.sqrt(252),total_slippage=slips_total,total_trade_count=len(fills),rounds=stats(completed),open_round_net_mtm=openround)
 origmetrics=json.loads((path/'metrics.json').read_text())
 for k in ['end_equity','total_return_pct','max_dd_pct','sharpe']:close(metrics[k],origmetrics[k],'reported_metric:'+k)
 weekly=pd.read_csv(path/'weekly_bars.csv');weeklookup={}
 for r in weekly.itertuples():
  ds=ast.literal_eval(r.source_days);ss=[lookup[(r.vt_symbol,d)] for d in ds];ok(all(x.volume>0 and x.contract_epoch_id==r.contract_epoch_id for x in ss),'weekly_real_positive_same_epoch');ok(ds==sorted(ds) and ds[-1]==r.week_end,'weekly_causal_dates')
  for name,v in [('open',ss[0].open),('high',max(x.high for x in ss)),('low',min(x.low for x in ss)),('close',ss[-1].close),('volume',sum(x.volume for x in ss)),('open_interest',ss[-1].close_oi)]:close(getattr(r,name),v,'weekly_'+name)
  weeklookup[(r.vt_symbol,r.week_end)]=r
 decisions=json.loads((path/'short_price_range_decisions.json').read_text());candidates=pd.read_csv(path/'entry_candidates.csv');blocked=0;proofs=[]
 for side in ['short','long']:
  ok(json.loads((path/(side+'_ma_slope_decisions.json')).read_text())==[],'no_'+side+'_slope_decisions')
  acc=json.loads((path/(side+'_ma_slope_acceptance.json')).read_text());ok(acc['enabled'] is False and acc['decision_count']==0,'no_'+side+'_slope_gate')
 range_acc=json.loads((path/'short_price_range_acceptance.json').read_text());ok(range_acc['enabled'] is (pre['arm']=='C') and range_acc['threshold_fraction']==.2 and range_acc['includes_signal_day'] is True and range_acc['history_scope']=='all_available_same_physical_epoch_daily_through_signal' and range_acc['range_fields']==['low','high'] and range_acc['listing_start_completeness_proven'] is False,'range_contract')
 groups={(sym,ep):g.sort_values('date') for (sym,ep),g in source.groupby(['vt_symbol','contract_epoch_id'])}
 weekdays={}
 for w in weekly.itertuples():weekdays.setdefault((w.vt_symbol,w.contract_epoch_id),[]).append((w.week_end,ast.literal_eval(w.source_days)))
 epochs=pd.read_csv(DATA/'physical_epochs.csv',dtype=str).fillna('');epochinfo={(r.vt_symbol,r.contract_epoch_id):r for r in epochs.itertuples()}
 for r in decisions:
  sym,day=r['vt_symbol'],r['signal_date'];real=lookup[(sym,day)];epoch=real.contract_epoch_id;g=groups[(sym,epoch)].loc[groups[(sym,epoch)].date.le(day)];ok(not g.empty and g.date.max()==day,'nonempty_complete_available_daily_prefix');low=float(g.low.min());high=float(g.high.max());price=float(real.close);threshold=low+.2*(high-low);flat=high==low;want=flat or price<=threshold
  ok(r['contract_epoch_id']==epoch and r['history_scope']=='all_available_same_physical_epoch_daily_through_signal','range_same_physical_epoch');ok(r['history_start']==g.date.min() and r['history_end']==day and r['history_bar_count']==len(g),'range_all_available_prefix_not_just_weekly')
  for k,v in [('signal_close',price),('range_low',low),('range_high',high),('threshold_price',threshold),('threshold_fraction',.2)]:close(r[k],v,'range_source:'+k)
  if flat:ok(r['range_position'] is None and r['range_status']=='flat_range_reject','flat_range_fail_closed')
  else:close(r['range_position'],(price-low)/(high-low),'range_position');ok(r['range_status']=='valid','valid_range_status')
  ok(r['would_block']==want and r['enabled'] is (pre['arm']=='C') and r['direction']=='short' and r['signal']=='short_case1a' and r['entry_context'] in {'flat_entry','env_probe','reverse_entry'},'range_rule_inclusive20');apply=pre['arm']=='C' and want and r['selected_volume_before']>0;ok(r['applied_block']==apply,'range_applied_original_positive_size');close(r['selected_volume_after'],0 if apply else r['selected_volume_before'],'range_after_volume')
  rows=candidates.loc[candidates.date.astype(str).str[:10].eq(day)&candidates.contract_vt_symbol.eq(sym)&candidates.direction.eq('short')&candidates.signal.eq('short_case1a')&candidates.entry_context.eq('flat_entry')];ok(len(rows)>=1,'range_decision_candidate_exists')
  if apply:blocked+=1;ok(rows.selected_volume.eq(0).all() and rows.candidate_status.ne('opened').all(),'range_blocked_candidate_no_open')
  observed={d for end,days in weekdays.get((sym,epoch),[]) if end<=day for d in days};ok(observed<=set(g.date),'accepted_week_days_subset_of_available_daily');e=epochinfo.get((sym,epoch));listed='' if e is None else e.listed_date;proofs.append(dict(signal_date=day,vt_symbol=sym,contract_epoch_id=epoch,available_daily_count=len(g),prefix_first=g.date.min(),prefix_last=g.date.max(),range_low=low,range_high=high,threshold_price=threshold,signal_close=price,accepted_week_source_day_count=len(observed),additional_daily_count_beyond_engine_week_sources=len(set(g.date)-observed),known_listed_date=listed,cache_first_after_known_listed_date=bool(listed and g.date.min()>listed),cache_first_before_known_listed_date=bool(listed and g.date.min()<listed),listing_history_completeness_proven=False))
 native=candidates.loc[candidates.direction.eq('short')&candidates.signal.eq('short_case1a')]
 for r in native.itertuples():
  q=[x for x in decisions if x['vt_symbol']==r.contract_vt_symbol and x['signal_date']==str(r.date)[:10]];ok(bool(q),'all_short_candidates_have_range_proof')
  if pre['arm']=='C' and r.candidate_status=='opened':ok(not any(x['would_block'] for x in q),'opened_short_outside_bottom20')
 opens=candidates.loc[candidates.direction.eq('short')&candidates.candidate_status.eq('opened')]
 roll=pd.read_csv(path/'rollover_shape_same_volume.csv');contexts={};slope_diagnostics={}
 for side,ch in [('long','多'),('short','空')]:
  count={'native':0,'rollover':0};angles={'actual_native_MA5_negative':0,'actual_native_MA5_or_MA10_negative':0,'actual_native_MA5_or_MA10_positive':0}
  for t in fills.loc[fills.direction.eq(ch)&fills.offset.eq('开')].itertuples():
   a=anchors.loc[anchors.order_id.astype(str).eq(str(t.order_id))];ok(len(a)==1,'actual_open_unique_anchor');day=str(a.iloc[0].signal_date)[:10];nn=candidates.loc[candidates.date.astype(str).str[:10].eq(day)&candidates.contract_vt_symbol.eq(t.vt_symbol)&candidates.direction.eq(side)&candidates.candidate_status.eq('opened')];rr=roll.loc[roll.date.astype(str).str[:10].eq(day)&roll.target_contract_vt_symbol.eq(t.vt_symbol)&roll.direction.eq(side)&roll.status.eq('targeted')&roll.final_volume.gt(0)];ok((len(nn)>0)!=(len(rr)>0),'actual_open_unique_native_or_roll')
   if len(nn):
    count['native']+=1
    if side=='short':q=[x for x in decisions if x['vt_symbol']==t.vt_symbol and x['signal_date']==day];ok(bool(q) and (pre['arm']=='A' or not any(x['would_block'] for x in q)),'actual_short_fill_passes_declared_gate')
    epoch=lookup[(t.vt_symbol,day)].contract_epoch_id;ww=weekly.loc[weekly.vt_symbol.eq(t.vt_symbol)&weekly.contract_epoch_id.eq(epoch)&weekly.week_end.le(day)].sort_values('week_end').tail(11);ok(len(ww)==11,'native_indicator_history');cl=ww.close.tolist();delta5=sum(cl[-5:])/5-sum(cl[-6:-1])/5;delta10=sum(cl[-10:])/10-sum(cl[-11:-1])/10;angles['actual_native_MA5_negative']+=int(delta5<0);angles['actual_native_MA5_or_MA10_negative']+=int(delta5<0 or delta10<0);angles['actual_native_MA5_or_MA10_positive']+=int(delta5>0 or delta10>0)
   else:count['rollover']+=1
  contexts[side]=count;slope_diagnostics[side]=angles
 active={};trades_by_day={day:g for day,g in fills.groupby('trading_date')}
 for day in dates:
  tt=trades_by_day.get(day,fills.iloc[:0]);required={sym for sym,q in active.items() if q!=0}|set(tt.vt_symbol);ok(required<=presence.get(day,set()),'all_required_held_days_present')
  for t in tt.itertuples():active[t.vt_symbol]=active.get(t.vt_symbol,0)+direction(t.direction)*t.volume
 controls={};control=LINE/'outputs/stage006_A_attempt001'
 if pre['arm']=='C':
  cp=json.loads((control/'preflight.json').read_text());ok(cp['short_ma_slope_gate_enabled'] is False and cp.get('long_ma_slope_gate_enabled',False) is False and cp['short_price_range_gate_enabled'] is False,'original_no_gate_control');ok(cp['data_identity']==pre['data_identity'],'same_data_identity');ok(json.loads((control/'actual_strategy_settings.json').read_text())==settings,'same_actual_settings');ok(json.loads((control/'effective_parameters.json').read_text())==effective,'same_effective_parameters')
 ok(actual.get('trade_start_date')=='2015-01-01','actual_trade_start_really2015');ok(dates[0]=='2015-01-05' and dates[-1]=='2026-10-29' and len(dates)==2871,'full_independent2015_calendar');close(daily.account_equity.iloc[0],150000,'fresh150000_first_financial_day');ok(fills.loc[fills.trading_date.eq('2015-01-05')].empty,'no_firstday_inherited_fill');ok(all(str(a['signal_date'])[:10]>='2015-01-01' for a in anchors.to_dict('records') if a['offset'] in ['开','open','Offset.OPEN']),'no_prewindow_open_signal_queue')
 for value in [actual.get('capital_base'),settings[0].get('engine_capital'),effective['spec']['capital']['account_capital'],effective['spec']['capital']['c3_capital']]:close(value,150000,'fresh_capital_contract')
 readiness=pd.read_csv(path/'weekly_readiness.csv');ok(str(readiness.date.iloc[0])[:10]=='2015-01-05' and len(readiness)==2871,'readiness_export_full2015');hc=weekly.loc[weekly.vt_symbol.eq('hc1505.SHFE')&weekly.week_end.lt('2015-01-05')];warmup_first=dict(hc1505_completed_weeks_before_start=len(hc),first_readiness=readiness.iloc[0].to_dict(),first_fill_trade_date=str(fills.trading_date.min()),first_open_signal_date=min(str(a['signal_date'])[:10] for a in anchors.to_dict('records') if a['offset'] in ['开','open','Offset.OPEN']))
 ok(len(hc)<21,'hc1505_not_forced_ready_from2014');ok(pre['ready_need']==21 and pre['storage_capacity']==41,'unchanged21ready41store')
 for name in ['stage001_delivery_manifest.json','stage002_delivery_manifest.json','stage003_delivery_manifest.json','stage004_delivery_manifest.json','stage004_delivery_manifest_v2.json','stage005_delivery_manifest.json']:
  bound=json.loads((LINE/'stages'/name).read_text())['files_sha256'];ok(all(Path(p).is_file() and sha(p)==h for p,h in bound.items()),'old_frozen_delivery:'+name)
 ok(before=={str(p):sha(p) for p in path.iterdir() if p.is_file()},'attempt_unchanged')
 return dict(path=str(path),metrics=metrics,position_financial_rows=len(pos),weekly_bar_count=len(weekly),decision_count=len(decisions),would_block_count=sum(r['would_block'] for r in decisions),blocked_decisions=blocked,range_prefix_proofs=proofs,actual_open_context_counts=contexts,MA_slope_diagnostics_only=slope_diagnostics,opened_short_candidates=len(opens),actual_entry_fills=entry_fill_count,source_bindings=len(json.loads((path/'input_manifest.json').read_text())),cold_start_warmup_evidence=warmup_first,checks=checks,source_files_sha256=before)

def main():
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--arm',choices=['A','C'],required=True);ap.add_argument('--attempt',default='001');args=ap.parse_args();p=LINE/'outputs'/f'stage006_{args.arm}_attempt{args.attempt}';result=audit(p);result.update(status='PASS_WITH_LIMITATIONS',P0=0,P1=0,P2=0,production_qualified=False)
 out=LINE/'stages'/f'stage006_independent_{args.arm}_results.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x))+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['source_files_sha256','range_prefix_proofs']},ensure_ascii=False,default=str))
if __name__=='__main__':main()
