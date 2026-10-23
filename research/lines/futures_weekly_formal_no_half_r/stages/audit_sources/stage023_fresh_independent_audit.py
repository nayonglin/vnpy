from pathlib import Path
import json,hashlib,sqlite3,math,re,ast
from collections import defaultdict,deque,Counter
import pandas as pd,numpy as np
ROOT=Path('/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian');LINE=ROOT/'research/lines/futures_weekly_formal_no_half_r'
CAP=150000.
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def close(a,b,label):
 if not math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-5):raise AssertionError((label,a,b))
def arm_audit(arm,data,attempt='001'):
 p=LINE/'outputs'/f'{arm}_attempt{attempt}';j=lambda name:json.loads((p/(name+'.json')).read_text());c=lambda name:pd.read_csv(p/(name+'.csv'),low_memory=False)
 term=j('terminal');assert term['status']=='completed_pending_independent_review' and term['error'] is None,term
 metrics=j('metrics');pref=j('preflight');actual=j('actual_strategy_settings');effective=j('effective_parameters');assert len(actual)==1 and actual[0]['strategy_class']=='HistoricalSafetyStrategy'
 old=json.loads((LINE/'outputs/M_attempt001/actual_strategy_settings.json').read_text())[0]
 for k in ['setting','actual']:
  a=actual[0][k].copy();b=old[k].copy()
  for name in ['trade_start_date','mapping_csv_path']:
   if name in a:a[name]=b[name]
  assert a==b,('params',k,{x:(a.get(x),b.get(x)) for x in set(a)|set(b) if a.get(x)!=b.get(x)})
 eff_old=json.loads((LINE/'outputs/M_attempt001/effective_parameters.json').read_text());eff_copy=json.loads(json.dumps(effective));eff_copy['spec']['overrides']['mapping_csv_path']=eff_old['spec']['overrides']['mapping_csv_path'];assert eff_copy==eff_old
 for f in ['macd_acceptance','short_case2_acceptance','no_position_cap_acceptance','ai_selection_acceptance','historical_safety_acceptance','bar_open_acceptance']:assert j(f)['accepted'] is True,(arm,f)
 dq=j('data_quality');assert all(not dq[k] for k in ['held_or_traded_daily_gaps','held_or_traded_zero_volume','captured_bar_failures'])
 read=j('data_read_counts');assert all(read[k]==0 for k in ['minute_reads','proxy_reads','ai_selection_model_load_attempts'])
 daily=c('daily');daily['date']=pd.to_datetime(daily.date).dt.strftime('%Y-%m-%d');assert not daily.date.duplicated().any()
 start='2015-01-01' if arm=='N' else '2020-01-01';end='2026-10-23';calendar=sorted(pd.read_csv(data/'mapping.csv').date.astype(str).unique());wanted=[x for x in calendar if start<=x<=end];assert daily.date.tolist()==wanted
 equity=daily.account_equity.to_numpy(float);assert np.isfinite(equity).all() and min(equity)>0
 close(np.max(np.abs(CAP+daily.net_pnl.cumsum().to_numpy()-equity)),0,'dailyconservation')
 peak=np.maximum.accumulate(np.r_[CAP,equity])[1:];dd=(equity/peak-1)*100;r=equity/np.r_[CAP,equity[:-1]]-1;sharpe=np.mean(r)/np.std(r,ddof=1)*252**.5
 close(equity[-1],metrics['end_equity'],'end');close((equity[-1]/CAP-1)*100,metrics['total_return_pct'],'ret');close(min(dd),metrics['max_dd_pct'],'DD');close(sharpe,metrics['sharpe'],'sharpe')
 trades=c('trades');assert trades.trade_id.is_unique;trades['order']=trades.trade_id.str.split('.').str[-1].astype(int);trades=trades.sort_values('order');assert trades.order.tolist()==list(range(1,len(trades)+1))
 pos=c('positions');pos['date']=pd.to_datetime(pos.date).dt.strftime('%Y-%m-%d');last=pos[pos.date.eq(end)];terminal={r.vt_symbol:float(r.end_pos) for r in last.itertuples() if r.end_pos};marks=dict(zip(last.vt_symbol,last.close_price));close(pos.net_pnl.sum(),daily.net_pnl.sum(),'positiondaily')
 clock=c('execution_clock');assert clock.trade_id.is_unique and set(clock.trade_id)==set(trades.trade_id)
 joined=trades.merge(clock[['trade_id','trading_date','price','volume','vt_symbol']],on='trade_id',validate='one_to_one',suffixes=('','_clock'))
 for f in ['price','volume']:assert np.allclose(joined[f],joined[f+'_clock'])
 for f in ['vt_symbol','trading_date']:assert joined[f].tolist()==joined[f+'_clock'].tolist()
 epochs=pd.read_csv(data/'physical_epoch_daily.csv',usecols=['vt_symbol','date','contract_epoch_id']);lookup=epochs.set_index(['vt_symbol','date']).contract_epoch_id.to_dict();assert len(lookup)==len(epochs)
 with sqlite3.connect('file:'+str(data/'daily.sqlite')+'?mode=ro',uri=True) as db:
  raw=pd.read_sql_query("select symbol||'.'||exchange vt_symbol,substr(datetime,1,10) date,open_price,high_price,low_price,close_price,volume,open_interest from dbbardata where interval='d'",db)
 raw=raw[raw.vt_symbol.str.replace(r'\d+(?=\.)','',regex=True).isin(pref['universe_products']) & raw.vt_symbol.str.contains(r'\d{3,4}\.')];assert not raw.duplicated(['vt_symbol','date']).any();bar=raw.set_index(['vt_symbol','date']).to_dict('index')
 required=pos[(pos.start_pos.ne(0)|pos.end_pos.ne(0)|pos.trade_count.ne(0))]
 for rr in required.itertuples():
  bb=bar[(rr.vt_symbol,rr.date)];assert bb['volume']>0;close(rr.close_price,bb['close_price'],'heldmark')
 for rr in joined.itertuples():
  key=(rr.vt_symbol,str(rr.trading_date)[:10]);assert key in lookup;bb=bar[key];close(rr.price,bb['open_price'],'fillopen');assert bb['volume']>0
 anchors=c('execution_anchor_requests');ndays={day:calendar[i+1] for i,day in enumerate(calendar[:-1])}
 for rr in anchors.itertuples():
  assert ndays[str(rr.signal_date)[:10]]==str(rr.trading_date)[:10]
  bb=bar[(rr.vt_symbol,str(rr.trading_date)[:10])];close(rr.price,bb['open_price'],'anchoropen');assert bb['volume']>0
 inv=defaultdict(deque);netpos=defaultdict(float);cash=slips=fees=0.;segments=[];max_products=0;max_time=None
 for rr in trades.itertuples():
  s=rr.vt_symbol;price=float(rr.price);q=float(rr.volume);sign=1 if str(rr.direction) in ['多','long'] else -1;assert rr.direction in ['多','空','long','short'];close(rr.signed_volume,sign*q,'signed');size=float(effective['sizes'][s]);slip=float(effective['slippages'][s])*size;fee=float(effective['rates'][s])*size*price;slips+=q*slip;fees+=q*fee;cash-=sign*q*price*size+q*(slip+fee)
  if rr.offset in ['开','open']:
   assert not inv[s] or inv[s][0]['sign']==sign;inv[s].append(dict(sign=sign,q=q,p=price,cost=slip+fee,trade_id=rr.trade_id))
  else:
   assert rr.offset in ['平','平今','平昨','close','closetoday','closeyesterday'];left=q
   while left>1e-8:
    assert inv[s] and inv[s][0]['sign']==-sign,('unmatched close',rr.trade_id)
    v=inv[s][0];x=min(left,v['q']);pnl=v['sign']*(price-v['p'])*size*x-x*(v['cost']+slip+fee);segments.append(dict(vt_symbol=s,entry=v['trade_id'],exit=rr.trade_id,volume=x,pnl=pnl));v['q']-=x;left-=x
    if v['q']<1e-8:inv[s].popleft()
  netpos[s]+=q*sign;active={re.sub(r'\d+(?=\.)','',symbol) for symbol,value in netpos.items() if abs(value)>1e-8}
  if len(active)>max_products:max_products=len(active);max_time=dict(trade_id=rr.trade_id,trading_date=rr.trading_date,datetime=rr.datetime)
 # Independently reconstruct chronological modeled-clock product overlap.
 timeline=trades.copy();timeline['_utc']=pd.to_datetime(timeline.datetime,utc=True);timeline=timeline.sort_values(['_utc','order'],kind='stable');timeline_inv=defaultdict(float);engine_sequence_max_products=max_products;max_products=0;max_time=None
 for rr in timeline.itertuples():
  timeline_inv[rr.vt_symbol]+=float(rr.signed_volume)
  active={re.sub(r'\d+(?=\.)','',symbol) for symbol,value in timeline_inv.items() if abs(value)>1e-8}
  if len(active)>max_products:max_products=len(active);max_time=dict(trade_id=rr.trade_id,trading_date=rr.trading_date,datetime=rr.datetime)
 final={s:v for s,v in netpos.items() if abs(v)>1e-8};assert final==terminal,(final,terminal)
 mtm=opennet=0.
 for s,queue in inv.items():
  if not queue:continue
  mark=float(marks[s]);size=float(effective['sizes'][s])
  for v in queue:mtm+=v['sign']*v['q']*mark*size;opennet+=v['sign']*v['q']*(mark-v['p'])*size-v['q']*v['cost']
 totalnet=cash+mtm;closed=sum(x['pnl'] for x in segments);close(totalnet,equity[-1]-CAP,'cashmark');close(closed+opennet,totalnet,'FIFO');close(slips,daily.slippage.sum(),'slip');close(fees,daily.commission.sum(),'fee');close(len(trades),daily.trade_count.sum(),'fills');close(len(trades),metrics['total_trade_count'],'metricfills')
 wins=[x['pnl'] for x in segments if x['pnl']>1e-8];losses=[x['pnl'] for x in segments if x['pnl']< -1e-8];flat=len(segments)-len(wins)-len(losses)
 a=actual[0]['actual'];mult=float(a['stage830_broker_margin_multiplier']);close(mult,1.65,'actualmult');close(a['forced_margin_deleverage_broker_multiplier'],mult,'deleveragemult')
 margin=daily.total_margin_exact/daily.account_equity*mult*100;legacy=daily.total_margin_exact/daily.account_equity*1.10*100;close(np.max(np.abs(legacy-daily.broker10_margin_to_equity_pct)),0,'legacy1.10')
 nonzero=pos[pos.end_pos.ne(0)].copy();nonzero['product']=nonzero.vt_symbol.str.replace(r'\d+(?=\.)','',regex=True);daycounts=nonzero.groupby('date').product.nunique()
 candidates=c('entry_candidates');counts=candidates.groupby(['candidate_status','skip_reason'],dropna=False).size().reset_index(name='count').fillna('').to_dict('records')
 annual=[];start_eq=CAP
 for year,g in daily.groupby(daily.date.str[:4],sort=True):
  ee=float(g.account_equity.iloc[-1]);close(ee-start_eq,g.net_pnl.sum(),'annual');annual.append(dict(year=year,start=start_eq,end=ee,pnl=ee-start_eq,return_pct=(ee/start_eq-1)*100,trade_count=int(g.trade_count.sum())));start_eq=ee
 epochs_events=j('historical_epoch_transitions');assert not j('historical_epoch_failures')
 assert all(e['accepted'] and e['gap_days']>366 and e['old_position']==e['old_target']==e['old_layer_count']==0 and not e['old_active_order_ids'] for e in epochs_events)
 weekly=c('weekly_bars')
 for rr in weekly.itertuples():
  days=ast.literal_eval(rr.source_days);keys={lookup[(rr.vt_symbol,d)] for d in days};assert keys=={rr.contract_epoch_id}
 # Structural/no-trade keys can classify coverage but never authorize source consumption.
 classifier_checks={}
 for classification_file in ['known_no_trade_main.csv','structural_unavailable_main.csv']:
  classified=pd.read_csv(data/classification_file);forbidden=set(zip(classified.vt_symbol,classified.date));assert not forbidden&set(lookup)
  assert not any((rr.vt_symbol,rr.date) in forbidden for rr in required.itertuples())
  assert not any((rr.vt_symbol,str(rr.trading_date)[:10]) in forbidden for rr in trades.itertuples())
  assert not any((rr.vt_symbol,str(rr.trading_date)[:10]) in forbidden or (rr.vt_symbol,str(rr.signal_date)[:10]) in forbidden for rr in anchors.itertuples())
  assert not any((rr.contract_vt_symbol,str(rr.date)[:10]) in forbidden for rr in candidates.itertuples())
  assert not any(any((rr.vt_symbol,day) in forbidden for day in ast.literal_eval(rr.source_days)) for rr in weekly.itertuples())
  classifier_checks[classification_file]=dict(keys=len(classified),bar_candidate_order_fill_held_week_source_touches=0)
 old_fu_candidates=candidates[candidates.contract_vt_symbol.str.startswith('fu')&candidates.date.astype(str).lt('2018-07-16')]
 old_fu_fills=trades[trades.vt_symbol.str.startswith('fu')&trades.trading_date.astype(str).lt('2018-07-16')]
 old_fu_holdings=required[required.vt_symbol.str.startswith('fu')&required.date.lt('2018-07-16')]
 assert old_fu_candidates.empty and old_fu_fills.empty and old_fu_holdings.empty
 # Match the unique actual entry-order attribution without borrowing report helpers.
 er=c('entry_risk');ids=er.signal_order_id.fillna('').astype(str).str.strip();mapped=er[ids.ne('')].copy();mapped['order_id']=ids[ids.ne('')];opens=trades[trades.offset.isin(['开','open'])];assert mapped.order_id.is_unique and set(mapped.order_id)==set(opens.order_id)
 entry_join=opens.merge(mapped[['order_id','contract_vt_symbol','signal','entry_context','date']],on='order_id',validate='one_to_one',suffixes=('','_plan'));assert entry_join.vt_symbol.eq(entry_join.contract_vt_symbol).all()
 allowed={'long_case1a','long_case2','short_case1a','short_case2'};assert set(entry_join.loc[entry_join.entry_context.eq('flat_entry'),'signal']).issubset(allowed);assert entry_join.loc[entry_join.entry_context.eq('rollover_reopen'),'signal'].eq('rollover_reopen').all();assert set(entry_join.entry_context).issubset({'flat_entry','rollover_reopen'})
 # Explicit excluded FU date must not be read as a valid canonical bar or source week.
 assert ('fu1905.SHFE','2018-05-09') not in lookup
 assert not any(rr.vt_symbol=='fu1905.SHFE' and '2018-05-09' in str(rr.source_days) for rr in weekly.itertuples())
 post=j('postflight');assert post['inputs_unchanged'] and not post['mismatches']
 inp=j('input_manifest');bad=[path for path,d in inp.items() if sha(path)!=d];assert not bad,bad
 return dict(arm=arm,path=str(p),trading_days=len(daily),actual_start=daily.date.iloc[0],actual_end=daily.date.iloc[-1],end_equity=float(equity[-1]),return_pct=float((equity[-1]/CAP-1)*100),max_dd_pct=float(min(dd)),sharpe=float(sharpe),fills=len(trades),open_fills=int(trades.offset.isin(['开','open']).sum()),close_fills=int((~trades.offset.isin(['开','open'])).sum()),closed_segments=len(segments),wins=len(wins),losses=len(losses),flat=flat,winrate_pct=len(wins)/len(segments)*100,average_win=float(np.mean(wins)),average_loss_abs=-float(np.mean(losses)),payoff=float(np.mean(wins)/-np.mean(losses)),profit_factor=sum(wins)/-sum(losses),closed_net=closed,open_net=opennet,total_net=totalnet,slippage=slips,commission=fees,terminal=terminal,max_daily_products=int(daycounts.max()),days_over4=int((daycounts>4).sum()),max_after_fill_products=max_products,max_after_fill_first=max_time,engine_sequence_max_products=engine_sequence_max_products,actual_margin_multiplier=mult,margin_avg_pct=float(margin.mean()),margin_peak_pct=float(margin.max()),margin_peak_date=daily.loc[margin.idxmax(),'date'],margin_over100_days=int((margin>100).sum()),candidates=counts,annual=annual,epoch_transitions=len(epochs_events),target_cleanup=len(c('historical_target_cleanup')),input_count=len(inp),input_hashes_verified=True,classification_checks=classifier_checks,old_fu_pre20180716_candidates_fills_holdings=[len(old_fu_candidates),len(old_fu_fills),len(old_fu_holdings)],actual_open_fills_by_signal=entry_join.signal.value_counts().to_dict(),unfilled_entry_plan_rows=int(ids.eq('').sum()))
if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--data-dir',type=Path,required=True);ap.add_argument('--arms',nargs='+',default=['N','P']);ap.add_argument('--N-attempt',default='002');ap.add_argument('--P-attempt',default='001');args=ap.parse_args();result={a:arm_audit(a,args.data_dir,getattr(args,a+'_attempt')) for a in args.arms};print(json.dumps(result,ensure_ascii=False,indent=2))
