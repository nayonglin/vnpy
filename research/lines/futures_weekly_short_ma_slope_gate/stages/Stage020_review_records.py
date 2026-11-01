"""Independent arithmetic check of every Stage020 candle/MA/marker; no renderer import."""
from pathlib import Path
import hashlib,json,re
import numpy as np
import pandas as pd
D=Path(__file__).resolve().parent;A=D.parent/'artifacts/stage020_2026_ytd_recap';DATA=Path('/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/outputs/data_stage014_20261030/data_approved');checks=0;ma_values=0;candle_values=0
load=lambda p:json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb')as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def ok(v,k):
 global checks;checks+=1
 if not v:raise AssertionError(k)
def near(a,b,k,nullable=False):
 aa=np.asarray(a,dtype=float);bb=np.asarray(b,dtype=float);ok(aa.shape==bb.shape and np.allclose(aa,bb,rtol=0,atol=1e-6,equal_nan=nullable),k)
def compare_series(payload,ref,key):
 global ma_values,candle_values
 for c in ['open','high','low','close','volume']:
  near(payload[c],ref[c],key+':'+c);candle_values+=len(ref)
 for n in [5,10,20,40]:
  near(payload['ma'+str(n)],ref['ma'+str(n)],key+':MA'+str(n),nullable=True);ma_values+=len(ref)
def with_ma(f):
 f=f.copy()
 for n in [5,10,20,40]:f['ma'+str(n)]=f.close.rolling(n,min_periods=n).mean()
 return f
def group_candles(f,key):
 return f.groupby(key,sort=True).agg(date_start=('date','min'),date_end=('date','max'),open=('open','first'),high=('high','max'),low=('low','min'),close=('close','last'),volume=('volume','sum'),day_count=('date','size')).reset_index()
records=load(A/'records.json');pre=load(D/'Stage020_review_preflight.json');expected={r['entry_trade_id']:r for r in pre['rounds']};physical=pd.read_csv(DATA/'physical_epoch_daily.csv');physical['date']=pd.to_datetime(physical.date);mapping=pd.read_csv(DATA/'mapping.csv');mapping['date']=pd.to_datetime(mapping.date);mins=pd.read_csv(D/'Stage020_review_qualified_15m_warmup.csv');mins['bar_datetime']=pd.to_datetime(mins.bar_datetime);mins['trading_day']=pd.to_datetime(mins.trading_day);rows=[];seen=set()
ok(len(records)==18,'all18records');ok(len(expected)==18,'all18expected')
for record in records:
 m=record['meta'];key=m['open_trade_id'];e=expected[key];ok(key not in seen,'unique_episode');seen.add(key);sym=m['vt_symbol'];ok(sym==e['vt_symbol']and m['close_trade_id']==e['exit_trade_id'],'both_fill_identity');ok(m['entry_date']==e['entry_trading_date']and m['exit_date']==e['exit_trading_date'],'marker_trading_dates');near([m['entry_price'],m['entry_marker_price'],m['exit_price'],m['exit_marker_price'],m['weighted_exit_price'],m['volume'],m['realized_pnl']],[e['entry_price'],e['entry_price'],e['exit_price'],e['exit_price'],e['exit_price'],e['volume'],e['net_pnl']],'source_fill_markers_volume_net');ok(m['direction']==e['direction'],'source_direction');near(m['price_change_pct'],100*(e['exit_price']/e['entry_price']-1),'raw_underlying_price_change_no_direction_flip');ok(m['r_multiple']is None,'R_not_fabricated');ok(m['result_type']==('profit'if e['net_pnl']>0 else'loss'),'net_result_type');ok(m['context_fallback_dates']==[]and m['source_switch_x']==[],'no_main_proxy');ok(m['entry_source']==m['exit_source']==sym,'exact_source_endpoints')
 symnative,ex=sym.split('.');prod=''.join(c for c in symnative if c.isalpha());cal=pd.DatetimeIndex(sorted(set(mapping.loc[mapping['product'].str.lower().eq(prod.lower())&mapping.exchange.eq(ex)&mapping.date.le(pd.Timestamp('2026-10-30')),'date'])));calpositions={d:i for i,d in enumerate(cal)};entry=pd.Timestamp(m['entry_date']);exit_=pd.Timestamp(m['exit_date']);i,j=calpositions[entry],calpositions[exit_];dstart=max(0,i-300);dend=min(len(cal),j+51);visible=set(cal[dstart:dend]);wstart=cal[dstart].to_period('W-FRI');wend=cal[dend-1].to_period('W-FRI');full=physical.loc[physical.vt_symbol.eq(sym)&physical.contract_epoch_id.eq(e['physical_epoch_id'])&physical.date.isin(cal)].sort_values('date').reset_index(drop=True);full['position']=np.arange(len(full))+.5;full['trading_day_index']=full.date.map(calpositions);full=with_ma(full);vis=full.loc[full.date.isin(visible)];got=record['daily'];ok(got['date']==vis.date.dt.strftime('%Y-%m-%d').tolist(),'daily_requested_real_window');ok(set(got['source'])=={sym},'all_daily_exact_epoch');compare_series(got,vis,'daily:'+key);near(got['x'],vis.position,'daily_axis_real_history');bydate=full.set_index('date');near([m['entry_x'],m['exit_x']],[bydate.loc[entry,'position'],bydate.loc[exit_,'position']],'same_shared_marker_x')
 # Aggregate independently from physical daily, not canonical outputs/functions.
 for period in ['weekly','monthly','day10','day30']:
  f=full.copy()
  if period=='weekly':f['bucket']=f.date.dt.to_period('W-FRI').astype(str)
  elif period=='monthly':f['bucket']=f.date.dt.to_period('M').astype(str)
  else:f['bucket']=f.trading_day_index.astype(int)//(10 if period=='day10'else 30)
  agg=with_ma(group_candles(f,'bucket'))
  if period=='weekly':agg=agg.loc[agg.date_start.dt.to_period('W-FRI').ge(wstart)&agg.date_end.dt.to_period('W-FRI').le(wend)];labels=agg.bucket.astype(str).tolist()
  elif period=='monthly':agg=agg.loc[(pd.PeriodIndex(agg.bucket,freq='M')>=entry.to_period('M')-10)&(pd.PeriodIndex(agg.bucket,freq='M')<=exit_.to_period('M')+10)];labels=agg.bucket.astype(str).tolist()
  else:
   n=10 if period=='day10'else 30;labels=[f'{row.date_start.date()}~{row.date_end.date()} {row.day_count}/{n}日'for row in agg.itertuples()]
  ok(record[period]['label']==labels,'period_labels_calendar_buckets:'+period+key);compare_series(record[period],agg,period+':'+key);xs=[];widths=[]
  for row in agg.itertuples():
   positions=full.loc[full.date.between(row.date_start,row.date_end),'position'];xs.append(float(positions.mean()));widths.append(float(len(positions)*.78))
  near(record[period]['x'],xs,'shared_period_midpoint:'+period+key);near(record[period]['width'],widths,'shared_period_width:'+period+key)
 # Only admitted complete source days; hidden warmup may precede visible window.
 allmins=mins.loc[mins.vt_symbol.eq(sym)].sort_values('bar_datetime').copy();wanted=set(cal[max(0,i-5):min(len(cal),j+6)]);visiblemins=allmins.loc[allmins.trading_day.isin(wanted)&allmins.trading_day.isin(set(vis.date))].copy();intraday=record['intraday'];ok(intraday['datetime']==visiblemins.bar_datetime.dt.strftime('%Y-%m-%d %H:%M').tolist(),'visible_minute_exact_keys');ok(intraday['trading_day']==visiblemins.trading_day.dt.strftime('%Y-%m-%d').tolist(),'minute_product_trading_day');ok(set(intraday['source'])<={sym},'all_minute_exact_source')
 for c in ['open','high','low','close','volume']:near(intraday[c],visiblemins[c],'minute_source_value:'+c)
 missing=sorted(d.strftime('%Y-%m-%d')for d in wanted-set(visiblemins.trading_day));ok(m['missing_15m_dates']==missing,'honest_missing_complete_minutes');ok(set(m['daily_from_15m_dates'])==set(visiblemins.trading_day.dt.strftime('%Y-%m-%d')),'only_matched_full_days_daily_override')
 # Reset each rolling series after any missing authoritative product trading day.
 if len(allmins):
  dayidx=allmins.trading_day.map(calpositions);segments=dayidx.diff().gt(1).cumsum();computed=pd.concat([with_ma(g)for _,g in allmins.groupby(segments,sort=False)]).sort_values('bar_datetime');computed=computed.set_index('bar_datetime');ref=computed.loc[visiblemins.bar_datetime]
 else:ref=with_ma(allmins)
 for n in [5,10,20,40]:near(intraday['ma'+str(n)],ref['ma'+str(n)],'minute_hidden_warmup_segmented_MA:'+str(n),nullable=True);ma_values+=len(ref)
 x=[]
 for day,g in visiblemins.groupby('trading_day',sort=True):x.extend(float(bydate.loc[day,'position'])-.5+(np.arange(len(g))+.5)/len(g))
 near(intraday['x'],x,'minute_axis_within_true_trading_day')
 rows.append(dict(entry_id=key,exit_id=m['close_trade_id'],net_pnl=m['realized_pnl'],daily_bars=len(vis),intraday_bars=len(visiblemins),missing_intraday_days=len(missing),period_bars={p:len(record[p]['x'])for p in ['day30','day10','monthly','weekly','daily','intraday']}))
ok(seen==set(expected),'all18_expected_used');near(sum(r['net_pnl']for r in rows),22380,'net22380_aftercost');ok(sum(r['net_pnl']>0 for r in rows)==8 and sum(r['net_pnl']<0 for r in rows)==10,'8win10loss')
out=dict(schema='Stage020.independent-record-arithmetic.v1',accepted=True,status='PASS_WITH_LIMITATIONS',failures=[],checks=checks,candle_values_compared=candle_values,ma_values_compared=ma_values,rounds=rows,records_sha256=sha(A/'records.json'),summary_sha256=sha(A/'summary.json'),chart_manifest_sha256=sha(A/'chart_manifest.csv'),html_sha256=sha(A/'index.html'),expected_source_receipt_sha256=sha(D/'Stage020_review_preflight.json'),qualified_minutes_sha256=sha(D/'Stage020_review_qualified_15m_warmup.csv'),financial_replays=0,downloads=0,production_accesses=0)
p=D/'Stage020_review_records_result.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'accepted':True,'checks':checks,'candles':candle_values,'MA_values':ma_values,'receipt_sha256':sha(p)}))
