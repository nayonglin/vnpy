"""Independent CSV weekly reconstruction; no Runtime/on_bars/order/CTP code."""
from pathlib import Path
from datetime import date
import hashlib,json,math
import pandas as pd
ROOT=Path(__file__).resolve().parents[4];D=Path(__file__).resolve().parent
OLD=Path('/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate')
A=OLD/'outputs/data_stage014_20261030/data_approved';C=OLD/'outputs/data_stage014_20261030/raw/fresh_calendar.csv';TARGET='2026-10-30'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
report_path=D/'Stage018_signal_scope_20261030_result.json';report=json.loads(report_path.read_text());report_sha=sha(report_path)
settings=json.loads((ROOT/'examples/portfolio_backtesting/weekly19_assets/actual_settings.json').read_text())['settings']
assert not settings['enable_rsi_filter'] and not settings['ma5_angle_reversal_filter_enabled']
assert settings['ma_short']==5 and settings['ma_mid']==10 and settings['ma_long']==20
pins={n:sha(A/n)for n in report['source_hashes_before']};assert pins==report['source_hashes_before']==report['source_hashes_after'];assert sha(C)==report['calendar_sha256_before']==report['calendar_sha256_after']
mapping=pd.read_csv(A/'mapping.csv',usecols=['date','product','exchange','main_contract_vt'],dtype=str)
calendar=sorted(set(mapping.date)|set(pd.read_csv(C,usecols=['date'],dtype=str).date));assert calendar[-1]=='2026-11-02'
expected={}
for day in calendar:expected.setdefault(date.fromisoformat(day).isocalendar()[:2],[]).append(day)
assert expected[date.fromisoformat(TARGET).isocalendar()[:2]][-1]==TARGET
physical=pd.read_csv(A/'physical_epoch_daily.csv',usecols=['vt_symbol','date','contract_epoch_id','open','high','low','close','volume','close_oi'])
assert len(physical)==392382 and physical.date.max()==TARGET
current=mapping.loc[mapping.date.eq(TARGET)].copy();assert len(current)==19 and current.main_contract_vt.nunique()==19
actual={v['vt_symbol']:v for v in report['products']};assert len(actual)==19
results=[]
for row in current.to_dict('records'):
 symbol=row['main_contract_vt'];frame=physical.loc[physical.vt_symbol.eq(symbol)&physical.date.le(TARGET)].copy().sort_values('date');target=frame.loc[frame.date.eq(TARGET)].iloc[0];epoch=target.contract_epoch_id;frame=frame.loc[frame.contract_epoch_id.eq(epoch)]
 assert not frame.duplicated('date').any()
 frame['week']=frame.date.map(lambda d:date.fromisoformat(d).isocalendar()[:2]);weeks=[]
 for key,group in frame.groupby('week',sort=True):
  wanted=expected[key]
  if group.date.tolist()!=wanted:continue
  if wanted[-1]>TARGET:continue
  weeks.append(dict(date=wanted[-1],open=float(group.open.iloc[0]),high=float(group.high.max()),low=float(group.low.min()),close=float(group.close.iloc[-1]),volume=float(group.volume.sum()),close_oi=float(group.close_oi.iloc[-1])))
 history=pd.DataFrame(weeks).tail(41).reset_index(drop=True);assert len(history)>=21 and history.date.iloc[-1]==TARGET
 close=history.close;ma={p:close.rolling(p).mean()for p in (5,10,20)};s,m,l=ma[5],ma[10],ma[20]
 golden5=s.iloc[-2]<=m.iloc[-2]and s.iloc[-1]>m.iloc[-1];death5=s.iloc[-2]>=m.iloc[-2]and s.iloc[-1]<m.iloc[-1];golden10=m.iloc[-2]<=l.iloc[-2]and m.iloc[-1]>l.iloc[-1];death10=m.iloc[-2]>=l.iloc[-2]and m.iloc[-1]<l.iloc[-1]
 bull=bool(s.iloc[-1]>m.iloc[-1]>l.iloc[-1]);bear=bool(s.iloc[-1]<m.iloc[-1]<l.iloc[-1]);signal=''
 if (golden5 or death5)and not(golden10 or death10):
  if golden5 and bull:signal='long_case1a'
  elif death5 and bear:signal='short_case1a'
 elif golden10 or death10:
  if golden10 and bull:signal='long_case2'
  elif death10 and bear:signal='short_case2'
 raw_signal=signal;filters=[]
 if signal:
  long=signal.startswith('long');recent=s.iloc[-3:]
  if settings['ma5_extreme_filter_enabled']:
   block=(recent.iloc[-2]>recent.iloc[-1]and recent.iloc[-3]>recent.iloc[-2])if long else(recent.iloc[-2]<recent.iloc[-1]and recent.iloc[-3]<recent.iloc[-2])
   if block:filters.append('ma5_extreme')
  if not long and settings['short_ma5_slope_filter_enabled'] and s.iloc[-1]>s.iloc[-2]:filters.append('legacy_short_ma5_slope')
  simple=len(history)>=25 and ((bull and l.iloc[-1]>l.iloc[-4]and close.iloc[-1]>l.iloc[-1])if long else(bear and l.iloc[-1]<l.iloc[-4]and close.iloc[-1]<l.iloc[-1]))
  if settings['wick_chop_filter_enabled']and not simple:
   tail=history.tail(settings['wick_chop_filter_lookback']);body=(tail.close-tail.open).abs();upper=tail.high-tail[['open','close']].max(axis=1);lower=tail[['open','close']].min(axis=1)-tail.low
   if len(tail)>=settings['wick_chop_filter_lookback']and int(((upper>body)|(lower>body)).sum())>settings['wick_chop_filter_max_days']:filters.append('wick_chop')
  if filters:signal=''
 observed=actual[symbol];assert observed['physical_epoch_id']==epoch and observed['has_actual_bar']and observed['fresh_completed_week']and observed['weekly_inited'];assert observed['completed_week_end']==TARGET
 for key,value in [('close',target.close),('volume',target.volume),('close_oi',target.close_oi)]:assert math.isclose(observed[key],float(value),rel_tol=0,abs_tol=1e-9),(symbol,key)
 sd=observed['signal_data'];assert sd['signal']==signal,(symbol,raw_signal,filters,sd)
 assert sd['bullish_alignment']==bull and sd['bearish_alignment']==bear
 for key,value in [('ma_mid_value',m.iloc[-1]),('ma_mid_prev_value',m.iloc[-2]),('ma_long_value',l.iloc[-1]),('ma_long_prev_value',l.iloc[-2])]:assert math.isclose(sd[key],float(value),rel_tol=0,abs_tol=1e-8),(symbol,key,sd[key],value)
 native=signal in ('long_case1a','long_case2','short_case1a');assert observed['native_entry_signal']==native
 results.append(dict(product=row['product']+'.'+row['exchange'],vt_symbol=symbol,epoch=epoch,complete_weeks_in_buffer=len(history),raw_cross_signal=raw_signal,filters=filters,final_signal=signal,native_entry_signal=native,ma5=float(s.iloc[-1]),ma10=float(m.iloc[-1]),ma20=float(l.iloc[-1])))
assert not any(v['native_entry_signal']for v in results);assert report['decision']['intents']==[] and report['entry_candidate_snapshots']==[]
assert report['warmup_invariants']['intents']==0 and report['warmup_invariants']['layers']==0 and report['warmup_invariants']['funding_requests']==0
assert report['on_bars_completed_day_calls']==1 and report['actual_broker_queried']is False and report['production_qualified']is False
assert sha(report_path)==report_sha and {n:sha(A/n)for n in pins}==pins
out=dict(schema='Stage018.independent-signal-raw-reconstruction.v1',accepted=True,status='PASS_OFFLINE_SIGNAL_SCOPE_ONLY',target=TARGET,report_sha256=report_sha,source_files_sha256=pins,calendar_sha256=sha(C),script_sha256=sha(Path(__file__)),products=results,reviewed_products=19,native_entry_signal_count=0,raw_cross_signal_count=sum(bool(v['raw_cross_signal'])for v in results),actual_orders=0,actual_broker_known=False,source_qualified=False,production_qualified=False,financial_replay=False,method='Independent approved CSV current-physical-epoch completed-week OHLCVOI aggregation plus MA5/10/20 crossover and inherited filters; no runtime or strategy functions called',limitations=['150000 E/Available and flat positions are fictional assumptions','No signal as of this completed week does not predict all of next week; existing-position risk and future completed data remain unknown','No formal daily receipt or production activation authority issued'])
p=D/'Stage018_review_signal_raw_result.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=out['status'],products=19,raw_cross=out['raw_cross_signal_count'],native_entry=0,result_sha256=sha(p)),ensure_ascii=False));print(json.dumps(results,ensure_ascii=False))
