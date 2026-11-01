"""Qualify only existing minute caches by exact daily OHLCVOI and complete buckets."""
from pathlib import Path
from collections import defaultdict,Counter
import hashlib,json,sqlite3
import numpy as np
import pandas as pd
D=Path(__file__).resolve().parent;R=json.loads((D/'Stage020_review_preflight.json').read_text());OLD=Path('/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian');DATA=OLD/'research/lines/futures_weekly_short_ma_slope_gate/outputs/data_stage014_20261030/data_approved';END='2026-10-30';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();columns=['vt_symbol','bar_datetime','trading_day','open','high','low','close','volume','close_oi']
physical=pd.read_csv(DATA/'physical_epoch_daily.csv');mapping=pd.read_csv(DATA/'mapping.csv');frames=defaultdict(list);pins={};seen=set();source_inventory=[];symbols=sorted(set(x['vt_symbol']for x in R['rounds']));parse_issues=[]
for item in R['local_minute_search']['candidate_files']:
 p=Path(item['path']);h=sha(p);assert h==item['sha256'];pins[str(p)]=h
 if h in seen:continue
 seen.add(h);f=pd.read_csv(p);source_inventory.append({'path':str(p),'sha256':h,'raw_rows':len(f)})
 if item['target']not in symbols:parse_issues.append({'path':str(p),'reason':'bundle_needs_explicit_admission_not_used'});continue
 assert set(f.vt_symbol)=={item['target']}
 f['bar_datetime']=pd.to_datetime(f.bar_datetime,errors='raise');frames[item['target']].append(f[['vt_symbol','bar_datetime','open','high','low','close','volume','close_oi']].copy())
# Known approved sqlite minute table is an additional explicit source, not a fetch.
sqlite=DATA/'daily.sqlite';pins[str(sqlite)]=sha(sqlite)
with sqlite3.connect('file:'+str(sqlite)+'?mode=ro',uri=True)as con:
 f=pd.read_sql_query("SELECT symbol,exchange,datetime,open_price AS open,high_price AS high,low_price AS low,close_price AS close,volume,open_interest AS close_oi FROM dbbardata WHERE interval='1m' AND datetime>='2025-01-01' AND datetime<'2026-10-31' ORDER BY datetime",con)
 f['vt_symbol']=f.symbol+'.'+f.exchange;f['bar_datetime']=pd.to_datetime(f.datetime,errors='raise')
 for sym,g in f.groupby('vt_symbol'):
  if sym in symbols:frames[sym].append(g[['vt_symbol','bar_datetime','open','high','low','close','volume','close_oi']].copy())
 source_inventory.append({'path':str(sqlite),'sha256':pins[str(sqlite)],'queried_interval':'1m','query_start':'2025-01-01','query_end_exclusive':'2026-10-31','queried_rows':len(f),'selected_target_rows':int(f.vt_symbol.isin(symbols).sum())})
pins[str(DATA/'mapping.csv')]=sha(DATA/'mapping.csv');pins[str(DATA/'physical_epoch_daily.csv')]=sha(DATA/'physical_epoch_daily.csv')
qualified=[];days=[];symbol_stats=[];floatcols=['open','high','low','close','volume','close_oi']
for sym in symbols:
 rs=[x for x in R['rounds']if x['vt_symbol']==sym];epochids={x['physical_epoch_id']for x in rs};assert len(epochids)==1;epochid=next(iter(epochids));epoch=physical.loc[physical.vt_symbol.eq(sym)&physical.contract_epoch_id.eq(epochid)].set_index('date').sort_index();native,ex=sym.split('.');product=''.join(x for x in native if x.isalpha());calendar=sorted(set(mapping.loc[mapping['product'].str.lower().eq(product.lower())&mapping.exchange.eq(ex),'date']));cal=pd.DatetimeIndex(calendar);wanted=set()
 for r in rs:
  i=calendar.index(r['entry_trading_date']);j=calendar.index(r['exit_trading_date']);wanted.update(d for d in calendar[max(i-5,0):j+6]if d in epoch.index and d<=END)
 if not frames[sym]:
  for day in sorted(wanted):days.append(dict(vt_symbol=sym,trading_day=day,status='rejected',reasons=['no_cached_minutes'],raw_rows=0))
  symbol_stats.append(dict(vt_symbol=sym,raw_rows=0,wanted_days=len(wanted),accepted_days=0));continue
 frame=pd.concat(frames[sym],ignore_index=True);raw_rows=len(frame);valid=np.isfinite(frame[floatcols].to_numpy()).all(axis=1)&frame[['open','high','low','close']].gt(0).all(axis=1)&frame.volume.ge(0)&frame.close_oi.ge(0)&frame.high.ge(frame[['open','close','low']].max(axis=1))&frame.low.le(frame[['open','close','high']].min(axis=1));frame['_valid']=valid
 # Use the next product trading day for >=18:00. Overnight Sat/Sun naturally advances to Monday via authoritative calendar.
 boundary=frame.bar_datetime.dt.normalize()+pd.to_timedelta(frame.bar_datetime.dt.hour.ge(18).astype(int),unit='D');idx=cal.searchsorted(pd.DatetimeIndex(boundary),side='left');mask=idx<len(cal);frame=frame.loc[mask].copy();frame['trading_day']=[str(cal[i].date())for i in idx[mask]];frame=frame.loc[frame.trading_day.isin(wanted)].sort_values('bar_datetime');conflicts=set()
 for stamp,g in frame.groupby('bar_datetime',sort=False):
  if len(g)>1 and not np.allclose(g[floatcols].to_numpy(),g[floatcols].iloc[0].to_numpy(),rtol=0,atol=1e-9):conflicts.add(stamp)
 frame=frame.drop_duplicates('bar_datetime',keep='first');accepted=0
 for day in sorted(wanted):
  g=frame.loc[frame.trading_day.eq(day)].sort_values('bar_datetime');reasons=[];differences={};bars=[]
  if g.empty:reasons.append('no_cached_minutes')
  else:
   if not g._valid.all():reasons.append('invalid_native_OHLCVOI')
   if any(t in conflicts for t in g.bar_datetime):reasons.append('conflicting_duplicate_minutes')
   if not g.bar_datetime.dt.second.eq(0).all()or not g.bar_datetime.dt.microsecond.eq(0).all():reasons.append('non_minute_boundary')
   actual={'open':float(g.open.iloc[0]),'high':float(g.high.max()),'low':float(g.low.min()),'close':float(g.close.iloc[-1]),'volume':float(g.volume.sum()),'close_oi':float(g.close_oi.iloc[-1])}
   for col in floatcols:
    expected=float(epoch.loc[day,col]);delta=actual[col]-expected
    if not np.isclose(actual[col],expected,rtol=0,atol=1e-7):differences[col]={'minute_aggregate':actual[col],'approved_daily':expected,'delta':delta}
   if differences:reasons.append('daily_OHLCVOI_mismatch')
   for bucket,b in g.groupby(g.bar_datetime.dt.floor('15min'),sort=True):
    expected=pd.date_range(bucket,periods=15,freq='min')
    if b.bar_datetime.tolist()!=expected.tolist():reasons.append('incomplete_15minute_bucket');break
    bars.append(dict(vt_symbol=sym,bar_datetime=str(bucket),trading_day=day,open=float(b.open.iloc[0]),high=float(b.high.max()),low=float(b.low.min()),close=float(b.close.iloc[-1]),volume=float(b.volume.sum()),close_oi=float(b.close_oi.iloc[-1])))
  status='rejected'if reasons else'accepted'
  if status=='accepted':accepted+=1;qualified.extend(bars)
  days.append(dict(vt_symbol=sym,trading_day=day,status=status,reasons=sorted(set(reasons)),raw_rows=len(g),native_first=None if g.empty else str(g.bar_datetime.iloc[0]),native_last=None if g.empty else str(g.bar_datetime.iloc[-1]),daily_differences=differences))
 symbol_stats.append(dict(vt_symbol=sym,physical_epoch_id=epochid,raw_rows=raw_rows,unique_wanted_rows=len(frame),conflicting_timestamps=len(conflicts),wanted_days=len(wanted),accepted_days=accepted))
out=pd.DataFrame(qualified,columns=columns).sort_values(['vt_symbol','bar_datetime'])if qualified else pd.DataFrame(columns=columns);csv=D/'Stage020_review_qualified_15m.csv';out.to_csv(csv,index=False)
for p,h in pins.items():assert sha(p)==h,p
result=dict(schema='Stage020.independent-known-minute-qualification.v1',accepted=True,status='PASS_WITH_LIMITATIONS',failures=[],admission_rule='Existing source only. Exact entry physical epoch, authoritative product day mapping (>=18:00 advance to next completed trading day), conflict-free native minute keys, finite valid OHLCVOI, entire-day aggregate equal approved daily OHLCVOI, every nonempty wallclock15-minute bucket contains all15native minutes. No padding/repair or daily replacement by partial data.',requested_context='Each round entry-5 to final-exit+5 actual product trading dates, bounded by exact physical epoch and completed cutoff',input_files_sha256=pins,source_inventory=source_inventory,scope_parse_issues=parse_issues,qualified_csv=str(csv),qualified_csv_sha256=sha(csv),qualified_bars=len(out),qualified_days=sum(x['status']=='accepted'for x in days),rejected_days=sum(x['status']=='rejected'for x in days),rejection_reason_counts=dict(Counter(z for d in days for z in d['reasons'])),per_symbol=symbol_stats,per_day=days,financial_replays=0,downloads=0,production_accesses=0,statement='This qualifies only specified local minute dates. Absence/rejection is not a claim that no other cache exists globally.')
p=D/'Stage020_review_minute_qualification.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'qualified_days':result['qualified_days'],'qualified_bars':len(out),'rejected_days':result['rejected_days'],'reasons':result['rejection_reason_counts'],'receipt_sha256':sha(p),'csv_sha256':sha(csv)}))
