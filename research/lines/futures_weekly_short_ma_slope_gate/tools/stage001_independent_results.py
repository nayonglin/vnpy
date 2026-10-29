"""Independent reviewer: reconstruct cash/positions/weekly inputs, never run a strategy."""
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
 ok(pre['daily_addon_enabled'] is False and pre['universe_product_count']==19 and pre['ready_need']==21 and pre['storage_capacity']==41 and pre['start']=='2020-01-01' and pre['end']=='2026-10-29','contract')
 ok([actual[x] for x in ['ma_short','ma_mid','ma_long']]==[5,10,20],'MAperiods')
 for x in ['enable_stage847_half_r_stop_retry','enable_stage827_intraday_c2_stop','enable_rsi_partial_exit','enable_add_position','enable_donchian_add_position','enable_post_entry_quality_add','selection_pairwise_enabled','enable_selection_pairwise']:
  if x in actual:ok(actual[x] is False,'disabled:'+x)
 daily=pd.read_csv(path/'daily.csv');fills=pd.read_csv(path/'trades.csv');clock=pd.read_csv(path/'execution_clock.csv');anchors=pd.read_csv(path/'execution_anchor_requests.csv');dates=daily.date.astype(str).str[:10].tolist();calendar=sorted(pd.read_csv(DATA/'mapping.csv').date.unique())
 ok(dates==[d for d in calendar if '2020-01-01'<=d<='2026-10-29'],'full_calendar')
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
 decisions=json.loads((path/'short_ma_slope_decisions.json').read_text());candidates=pd.read_csv(path/'entry_candidates.csv');blocked=0
 for r in decisions:
  vals=r['source_week_closes'];ds=r['source_week_ends'];ok(len(vals)==len(ds)==11 and ds[-1]==r['signal_date'],'fresh_slope_sources');epochs=set()
  for d,v in zip(ds,vals):
   w=weeklookup[(r['vt_symbol'],d)];close(w.close,v,'decision_week_close');epochs.add(w.contract_epoch_id)
  ok(len(epochs)==1,'decision_epoch');m5c=sum(vals[-5:])/5;m5p=sum(vals[-6:-1])/5;m10c=sum(vals[-10:])/10;m10p=sum(vals[-11:-1])/10
  for k,v in [('ma5_current',m5c),('ma5_previous',m5p),('ma10_current',m10c),('ma10_previous',m10p),('ma5_delta',m5c-m5p),('ma10_delta',m10c-m10p)]:close(r[k],v,'MA_recompute:'+k)
  # Integer/decimal prices are exact enough; recorded rolling arithmetic is compared numerically.
  expected=(m5c>m5p or m10c>m10p);ok(expected==r['would_block'],'OR_slope');enabled=pre['arm']=='C';ok(r['enabled']==enabled,'decision_flag');applied=enabled and expected and r['selected_volume_before']>0;ok(applied==r['applied_block'],'applied_rule')
  close(r['selected_volume_after'],0 if applied else r['selected_volume_before'],'decision_volume')
  rows=candidates.loc[candidates.date.astype(str).str[:10].eq(r['signal_date'])&candidates.contract_vt_symbol.eq(r['vt_symbol'])&candidates.direction.eq('short')&candidates.entry_context.eq('flat_entry')]
  ok(len(rows)>=1,'decision_candidate_exists')
  if applied:
   blocked+=1;ok(rows.selected_volume.eq(0).all() and rows.candidate_status.ne('opened').all(),'blocked_candidate_no_open')
 # Every actual native short-entry candidate must have a nonblocked proof; rollover excluded explicitly.
 opens=candidates.loc[candidates.direction.eq('short')&candidates.candidate_status.eq('opened')]
 for r in opens.itertuples():
  rr=[q for q in decisions if q['vt_symbol']==r.contract_vt_symbol and q['signal_date']==str(r.date)[:10]];ok(bool(rr),'opened_short_has_decision');ok(not any(q['applied_block'] for q in rr),'opened_short_not_blocked')
 ok(before=={str(p):sha(p) for p in path.iterdir() if p.is_file()},'attempt_unchanged')
 return dict(path=str(path),metrics=metrics,position_financial_rows=len(pos),weekly_bar_count=len(weekly),decision_count=len(decisions),blocked_decisions=blocked,opened_short_candidates=len(opens),actual_entry_fills=entry_fill_count,source_bindings=len(json.loads((path/'input_manifest.json').read_text())),checks=checks,source_files_sha256=before)

def main():
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--arm',choices=['A','C'],required=True);ap.add_argument('--attempt',default='001');args=ap.parse_args();p=LINE/'outputs'/f'stage001_{args.arm}_attempt{args.attempt}';result=audit(p);result.update(status='PASS_WITH_LIMITATIONS',P0=0,P1=0,P2=0,production_qualified=False)
 out=LINE/'stages'/f'stage001_independent_{args.arm}_results.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x))+'\n');print(json.dumps({k:v for k,v in result.items() if k!='source_files_sha256'},ensure_ascii=False,default=str))
if __name__=='__main__':main()
