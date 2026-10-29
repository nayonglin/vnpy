from pathlib import Path
from collections import Counter
import json,hashlib,math,re,ast
import pandas as pd
ROOT=Path(__file__).resolve().parents[4];L=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';O=L/'outputs/stage003_blocked_recap';D=L/'outputs/data_stage001_20261029/data_approved'
checks=0

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for c in iter(lambda:f.read(8*1024*1024),b''):h.update(c)
 return h.hexdigest()
def ok(v,label):
 global checks;checks+=1
 if not v:raise AssertionError(label)
def near(a,b,label):ok(math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-7),label)
expected=json.loads((L/'stages/stage003_independent_expected.json').read_text());truth={tuple(r['key']):r for r in expected['events']};records=json.loads((O/'records.json').read_text());summary=json.loads((O/'summary.json').read_text());man=pd.read_csv(O/'chart_manifest.csv');delivery=json.loads((O/'delivery_manifest.json').read_text());source=json.loads((O/'source_hashes.json').read_text());before={str(p):sha(p) for p in O.iterdir() if p.is_file()}
for p,h in source.items():ok(Path(p).is_file() and sha(p)==h,'source_binding:'+p)
for p,h in delivery['files_sha256'].items():ok(sha(O/p)==h,'output_binding:'+p)
for stage in ['001','002']:
 m=json.loads((L/f'stages/stage{stage}_delivery_manifest.json').read_text())['files_sha256'];ok(all(Path(p).is_file() and sha(p)==h for p,h in m.items()),'old_frozen_'+stage)
ok(len(records)==len(man)==35 and len({r['meta']['event_id'] for r in records})==35,'35_unique_records');ok(Counter(r['meta']['direction'] for r in records)=={'long':20,'short':15},'direction20_15');ok(summary['closed_trade_count']==0 and summary['unexecuted_event_count']==35,'nontrades');ok(summary['financial_replays']==summary['market_downloads']==summary['production_accesses']==summary['strategy_changes']==0,'display_only');ok(summary['default_periods']==['day30','daily'],'defaults');ok(summary['intraday_status']=='unavailable_no_download','minute_disclosure')
originalmetrics=json.loads((L/'outputs/stage002_C_attempt001/metrics.json').read_text());ok(summary['frozen_source_metrics']==originalmetrics,'frozen_metrics_no_change');physical=pd.read_csv(D/'physical_epoch_daily.csv');physical.date=pd.to_datetime(physical.date);mapdf=pd.read_csv(D/'mapping.csv');mapdf.date=pd.to_datetime(mapdf.date);calendar={p:sorted(g.date.unique()) for p,g in mapdf.groupby('continuous_symbol_vt')};seen=[];baseline_counts=Counter();aggregate_bars=Counter()
for r in records:
 m=r['meta'];key=(m['signal_date'],m['vt_symbol'],m['direction'],m['signal']);ok(key in truth,'source_key');seen.append(key);t=truth[key];g=m['gate_evidence']
 for field,value in t['gate'].items():ok(g[field]==value,'gate_source:'+field)
 near(m['signal_close'],t['signal_price'],'signal_real_close');ok(m['physical_epoch_id']==t['physical_epoch_id']==g['physical_epoch_id'],'signal_epoch');ok(m['actual_fill'] is False and m['actual_pnl_available'] is False and m['status']=='被拦候选，未成交','event_semantics');ok(not any(k.startswith(('entry_','exit_','weighted_exit')) or k in {'open_trade_id','close_trade_id','holding_calendar_days','lot_id'} for k in m),'no_trade_endpoint_fields')
 for field in ['volume','realized_pnl','r_multiple','lot_count','price_change_pct']:ok(m[field] is None,'no_fake_'+field)
 b=m['baseline_actual'];ok(b['status']==t['baseline_status'],'baseline_status');ok(b['source']==('stage001_C_attempt003' if m['direction']=='long' else 'stage001_A_attempt003'),'baseline_version');ok(b['matching_key']==dict(signal_date=key[0],vt_symbol=key[1],direction=key[2],signal=key[3]),'baseline_four_key');baseline_counts[b['status']]+=1
 if t['baseline_actual_fills']:
  near(b['actual_open_volume'],t['baseline_actual_open_volume'],'baseline_real_volume');ok(set(b['actual_open_trade_ids'])=={x['trade_id'] for x in t['baseline_actual_fills']},'baseline_real_trade_ids');ok(b['actual_open_prices']==[x['price'] for x in t['baseline_actual_fills']],'baseline_real_prices');ok(b['actual_open_date']==t['baseline_actual_fills'][0]['trading_date'],'baseline_real_date')
 else:ok(b['actual_open_volume'] is None and not b['actual_open_trade_ids'],'unopened_honest')
 ep=physical.loc[physical.vt_symbol.eq(m['vt_symbol'])&physical.contract_epoch_id.eq(m['physical_epoch_id'])].sort_values('date').copy();ok(not ep.date.duplicated().any(),'physical_unique');lookup={d.strftime('%Y-%m-%d'):i for i,d in enumerate(ep.date)};daily=r['daily'];ok(daily['date']==sorted(set(daily['date'])) and all(x<= '2026-10-29' for x in daily['date']),'display_dates')
 ok(m['context_fallback_dates']==[] and m['source_switch_x']==[] and set(daily['source'])=={m['vt_symbol']},'exact_only_no_proxy');idx=daily['date'].index(m['signal_date']);near(daily['x'][idx],m['signal_x'],'signal_x');near(daily['close'][idx],m['signal_close'],'marker_y')
 for j,day in enumerate(daily['date']):
  src=ep.iloc[lookup[day]];ok(src.volume>0,'positive_market_bar')
  for fld in ['open','high','low','close','volume']:near(daily[fld][j],src[fld],'daily_market_'+fld)
  for n in [5,10,20,40]:
   value=ep.close.rolling(n).mean().iloc[lookup[day]];shown=daily[f'ma{n}'][j]
   if pd.isna(value):ok(shown is None,'honest_daily_warmup')
   else:near(shown,value,'daily_MA'+str(n))
 # Candle aggregation independently reconciles to raw same-epoch dates.
 for period in ['weekly','monthly','day10','day30']:
  p=r[period];ok(all(len(v)==len(p['x']) for v in p.values()),'period_payload_lengths')
  for j,label in enumerate(p['label']):
   if period=='weekly':mask=ep.date.dt.to_period('W-FRI').astype(str).eq(label)
   elif period=='monthly':mask=ep.date.dt.strftime('%Y-%m').eq(label)
   else:
    start,end=label[:10],label[11:21];mask=ep.date.between(pd.Timestamp(start),pd.Timestamp(end));count=int(label.split(' ')[1].split('/')[0]);ok(int(mask.sum())==count,'period_real_count')
   group=ep.loc[mask];ok(not group.empty,'period_source_exists')
   for fld,value in [('open',group.open.iloc[0]),('high',group.high.max()),('low',group.low.min()),('close',group.close.iloc[-1]),('volume',group.volume.sum())]:near(p[fld][j],value,'aggregate_'+period+'_'+fld)
   aggregate_bars[period]+=1
 # Independently recompute displayed natural-week/month and fixed-calendar
 # MA values from all real same-epoch history, including hidden warmup.
 cal={pd.Timestamp(d):i for i,d in enumerate(calendar[m['product']])}
 for period in ['weekly','monthly','day10','day30']:
  src=ep.copy()
  if period=='weekly':src['group']=src.date.dt.to_period('W-FRI').astype(str)
  elif period=='monthly':src['group']=src.date.dt.strftime('%Y-%m')
  else:src['group']=src.date.map(cal).astype(int)//(10 if period=='day10' else 30)
  aggregated=src.groupby('group',sort=True).agg(close=('close','last'),start=('date','min'),end=('date','max'))
  for n in [5,10,20,40]:
   means=aggregated.close.rolling(n).mean()
   for j,label in enumerate(r[period]['label']):
    keylabel=label if period in ['weekly','monthly'] else cal[pd.Timestamp(label[:10])]//(10 if period=='day10' else 30)
    value=means.loc[keylabel];shown=r[period][f'ma{n}'][j]
    if pd.isna(value):ok(shown is None,'honest_'+period+'_MA_warmup')
    else:near(shown,value,period+'_MA'+str(n))
 for period in ['daily','weekly','monthly','day10','day30']:
  for n in [5,10,20,40]:ok(m['ma_warmup_null_counts'][period][f'ma{n}']==sum(x is None for x in r[period][f'ma{n}']),'warmup_disclosure_count')
 ma=m['strategy_ma'];ok(ma['dates']==[g['previous_week_end'],g['week_end']],'accepted_MA_dates')
 for n in [5,10]:ok(ma[f'ma{n}']==[g[f'ma{n}_previous'],g[f'ma{n}_current']],'accepted_actual_MA_values')
 for date,x in zip(ma['dates'],ma['x']):near(x,daily['x'][daily['date'].index(date)],'accepted_MA_x')
 ok(m['draw_intraday']==0 and r['intraday']['x']==[] and not m['daily_from_15m_dates'],'no_invented_minute');coverage=m['coverage'];ok(coverage['physical_epoch_id']==m['physical_epoch_id'] and coverage['proxy_days']==0,'coverage_epoch');ok(coverage['real_history_rows']==len(ep),'coverage_real_rows');ok(coverage['signal_pre_real_bars']==int(ep.date.lt(pd.Timestamp(m['signal_date'])).sum()) and coverage['signal_post_real_bars']==int(ep.date.gt(pd.Timestamp(m['signal_date'])).sum()),'coverage_real_prepost')
ok(set(seen)==set(truth),'all_35_source_events_exact');ok(dict(baseline_counts)==summary['baseline_matches'] or all(summary['baseline_matches'].get(k,0)==v for k,v in baseline_counts.items()),'baseline_summary_reconciles');ok(before=={str(p):sha(p) for p in O.iterdir() if p.is_file()},'output_bytes_unchanged')
result=dict(status='PASS_WITH_LIMITATIONS',P0=0,P1=0,P2=0,checks=checks,event_count=35,long_count=20,short_count=15,baseline_status_counts=dict(baseline_counts),aggregate_bar_counts=dict(aggregate_bars),canonical_reuse='AST pure-functions loaded from frozen Stage031 adapter; canonical _records/_html, aggregation/candles/axes/linkedzoom retained; candidate semantic hook removes effective trade markers/hold range/metrics.',financial_replays=0,market_downloads=0,production_accesses=0,source_bindings=len(source),output_sha256=before,browser_qa='root agent to validate actual browser visuals and zoom separately')
(L/'stages/stage003_independent_output.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='output_sha256'},ensure_ascii=False))
