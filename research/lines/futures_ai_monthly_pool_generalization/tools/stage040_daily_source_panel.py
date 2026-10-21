"""Daily asof representative/frozen-signal inputs. No fills, labels or model fit."""
import argparse
from datetime import datetime
import hashlib
import json
import math
import multiprocessing as mp
from pathlib import Path
import sqlite3
import time
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import talib
from stage008_monthly_raw_matrix import frozen_signal_host, signal_fields, strict_history
from stage012_c2_reference_frontier import frozen_initial_stop_host

LINE=Path(__file__).resolve().parents[1]
ROOT=LINE.parents[2]
PRIOR=ROOT/'research/lines/futures_trend_rollover_shape_same_volume/outputs'
OUT=LINE/'outputs/stage040_daily_source_panel'
DB=PRIOR/'stage266_clean_daily/clean_daily.sqlite'
CALFILE=PRIOR/'stage265_deep_daily/rqalpha/trading_dates.npy'
COLS=['exchange','product','product_vt_symbol','eval_date','monthly_average_F','reference_epoch','input_ready','input_status','open','high','low','close','volume','close_oi','source_id','feature_start','raw_signal','bullish_alignment','bearish_alignment','breakout','risk_mode','rsi6','ma_long_prev_value','fresh_direction_allowed','fresh_after_hardblocks','hardblock_status','hardblock','shock_reason','range_reason','signal_direction','signal_stop']
_FRAMES={};_CAL=[];_HOST=None;_STOP=None

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def now():return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()

def select_representatives(frame):
    f=frame.loc[np.isfinite(frame.volume)&frame.volume.gt(0)].copy()
    if f.duplicated(['trade_date','contract_epoch_id']).any():raise ValueError('duplicate_representative_key')
    f=f.sort_values(['trade_date','volume','close_oi','contract_epoch_id'],ascending=[True,False,False,True],na_position='last')
    return {r['trade_date']:r for r in f.drop_duplicates('trade_date').to_dict('records')}

def history_status(indices,values,asof_index):
    if asof_index<40:return 'insufficient_calendar_history'
    if len(indices)!=41 or not np.array_equal(indices,np.arange(asof_index-40,asof_index+1)):
        return 'missing_exact_epoch_calendar_bar'
    p=values[:,:4]
    if not np.isfinite(p).all() or (p<=0).any():return 'invalid_OHLC'
    if (p[:,1]<np.maximum(p[:,0],p[:,3])).any() or (p[:,2]>np.minimum(p[:,0],p[:,3])).any() or (p[:,2]>p[:,1]).any():return 'invalid_OHLC_geometry'
    if not np.isfinite(values[:,4:]).all() or (values[:,4]<=0).any() or (values[:,5]<0).any():return 'unknown_or_invalid_volume_oi'
    return 'frozen_AM41_input_ready'

def daily_fields(host,history,stophost):
    close=history.close.to_numpy(float)
    frame=history.copy();frame['open_interest']=frame.close_oi
    rsi=float(talib.RSI(close,timeperiod=int(host.rsi_length))[-1])
    if not math.isfinite(rsi):raise ValueError('nonfinite_RSI')
    am=SimpleNamespace(close_array=close,rsi=lambda length:float(talib.RSI(close,timeperiod=length)[-1]))
    raw=host._generate_signal(am,frame)
    signal=str(raw['signal']);direction='long' if signal.startswith('long') else 'short' if signal.startswith('short') else ''
    allowed=bool(direction=='long' or (direction=='short' and host._can_open_short_signal(signal)))
    result=dict(raw_signal=signal,bullish_alignment=bool(raw['bullish_alignment']),bearish_alignment=bool(raw['bearish_alignment']),
                breakout=raw['breakout'],risk_mode=raw['risk_mode'],rsi6=rsi,ma_long_prev_value=float(close[-21:-1].mean()),
                fresh_direction_allowed=allowed,fresh_after_hardblocks=False,hardblock_status='not_evaluated_no_fresh_direction',
                hardblock=None,shock_reason=None,range_reason=None,signal_direction=direction,signal_stop=None)
    if direction and stophost is not None:
        bar=SimpleNamespace(**{k+'_price':float(frame[k].iloc[-1]) for k in ['open','high','low','close']})
        result['signal_stop']=float(stophost._entry_stop_price(direction,bar,frame,use_day_extreme=True))
    if allowed:
        shock=host._long_signal_atr_shock_snapshot(direction,frame,'flat_entry')
        spread=host._long_signal_range_atr_snapshot(direction,frame,'flat_entry')
        known=all(np.isfinite(s[key]) and s[key]>0 for s,key in [(shock,'long_signal_atr_shock_atr'),(spread,'long_signal_range_prior_atr')])
        blocked=bool(shock['long_signal_atr_shock_blocked'] or spread['long_signal_range_atr_condition_met']) if known else None
        result.update(hardblock_status='known' if known else 'unknown',hardblock=blocked,
                      shock_reason=shock['long_signal_atr_shock_reason'],range_reason=spread['long_signal_range_atr_reason'],
                      fresh_after_hardblocks=bool(known and not blocked))
    return result

def make_product(key):
    started=time.perf_counter();exchange,product=key
    destination=OUT/'checkpoints'/f'{exchange}_{product}.sqlite'
    if destination.exists():raise ValueError('checkpoint_already_exists')
    f=_FRAMES.get(key)
    representatives={} if f is None else select_representatives(f)
    date_indices={d:i for i,d in enumerate(_CAL)}
    epochs={}
    if f is not None:
        for epoch,g in f.groupby('contract_epoch_id',sort=False):
            g=g.sort_values('trade_date')
            indices=np.array([date_indices.get(day,-100000) for day in g.trade_date],dtype=int)
            values=g[['open','high','low','close','volume','close_oi']].to_numpy(float)
            epochs[epoch]=(indices,values,{d:i for i,d in enumerate(g.trade_date)})
    rows=[]
    for i,day in enumerate(_CAL):
        row={k:None for k in COLS}
        row.update(exchange=exchange,product=product,product_vt_symbol=product+'.'+exchange,eval_date=day,
                   monthly_average_F=product.endswith('_F'),reference_epoch='',input_ready=False,input_status='no_asof_observation')
        representative=representatives.get(day)
        if representative is not None:
            epoch=representative['contract_epoch_id'];row['reference_epoch']=epoch
            row.update({k:representative[k] for k in ['open','high','low','close','volume','close_oi','source_id']})
            indices,values,positions=epochs[epoch];j=positions[day];a=max(0,j-40);window=values[a:j+1]
            status=history_status(indices[a:j+1],window,i);row['input_status']=status
            if status=='frozen_AM41_input_ready':
                history=pd.DataFrame(window,columns=['open','high','low','close','volume','close_oi'])
                row.update(daily_fields(_HOST,history,_STOP),input_ready=True,feature_start=_CAL[i-40])
        rows.append(row)
    result=pd.DataFrame(rows,columns=COLS)
    with sqlite3.connect(destination) as c:
        result.to_sql('panel',c,index=False,if_exists='fail')
    receipt=dict(exchange=exchange,product=product,rows=len(rows),representatives=int(result.reference_epoch.ne('').sum()),
                 input_ready=int(result.input_ready.sum()),fresh=int(result.fresh_after_hardblocks.fillna(False).sum()),
                 elapsed_seconds=time.perf_counter()-started,path=str(destination),sha256=sha(destination))
    (destination.with_suffix('.json')).write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

def pilot(frames,calendar,host,stop):
    old=pd.read_csv(LINE/'outputs/stage008_monthly_raw_matrix/monthly_raw_signal_matrix.csv',dtype=str,keep_default_na=False)
    ready=old.loc[old.input_ready.eq('True')]
    # Fixed deterministic strata before any daily-panel results: all raw classes and uniform calendar coverage.
    chosen=pd.concat([ready.groupby('raw_signal',sort=True).head(2),ready.iloc[np.linspace(0,len(ready)-1,60,dtype=int)]]).drop_duplicates(['product_vt_symbol','eval_date'])
    checks=[];start=time.perf_counter()
    for r in chosen.to_dict('records'):
        frame=frames[r['exchange'],r['product']]
        representative=select_representatives(frame.loc[frame.trade_date.eq(r['eval_date'])])[r['eval_date']]
        assert representative['contract_epoch_id']==r['reference_epoch']
        ep=frame.loc[frame.contract_epoch_id.eq(r['reference_epoch'])].copy()
        history=strict_history(ep,pd.DatetimeIndex(calendar),r['eval_date'])
        actual=daily_fields(host,history,stop)
        for key in ['raw_signal','fresh_direction_allowed','fresh_after_hardblocks','bullish_alignment','bearish_alignment']:
            assert str(actual[key])==r[key],(r['product_vt_symbol'],r['eval_date'],key,actual[key],r[key])
        assert math.isclose(actual['rsi6'],float(r['rsi6']),rel_tol=0,abs_tol=1e-10)
        # Literal daily-exit previous MA20 and frozen initial-stop formula cross-check.
        assert math.isclose(actual['ma_long_prev_value'],float(history.close.iloc[-21:-1].mean()),rel_tol=0,abs_tol=1e-10)
        if actual['signal_direction']:
            b=history.iloc[-1];literal=max(float(b.close)*.98,float(b.low)) if actual['signal_direction']=='long' else min(float(b.high),float(b.close)*1.02,float(history.high.iloc[-3:].max()))
            assert math.isclose(actual['signal_stop'],literal,rel_tol=0,abs_tol=1e-10)
        checks.append(dict(product=r['product_vt_symbol'],day=r['eval_date'],epoch=r['reference_epoch'],raw_signal=actual['raw_signal'],fresh=actual['fresh_after_hardblocks']))
    return dict(rows=len(checks),source_ready_total=len(ready),checks=checks,elapsed_seconds=time.perf_counter()-start,status='passed_before_full_construction')

def run(workers=4):
    global _FRAMES,_CAL,_HOST,_STOP
    if OUT.exists():raise ValueError('immutable_output_exists')
    OUT.mkdir();(OUT/'checkpoints').mkdir()
    begin=now();timer=time.perf_counter();before=DB.stat()
    _HOST,frozen=frozen_signal_host();_STOP,stopbinding=frozen_initial_stop_host()
    dates=pd.to_datetime(np.load(CALFILE,allow_pickle=False).astype(str),format='%Y%m%d')
    _CAL=[str(d.date()) for d in dates if pd.Timestamp('2010-01-01')<=d<=pd.Timestamp('2026-10-16')]
    with sqlite3.connect(DB.resolve().as_uri()+'?mode=ro',uri=True) as c:
        c.execute('PRAGMA query_only=ON')
        catalog=pd.read_sql_query('SELECT DISTINCT exchange,product FROM contracts ORDER BY exchange,product',c)
        data=pd.read_sql_query('SELECT exchange,product,contract_epoch_id,trade_date,open,high,low,close,volume,close_oi,source_id FROM daily_bars ORDER BY exchange,product,contract_epoch_id,trade_date',c)
    _FRAMES={key:g for key,g in data.groupby(['exchange','product'],sort=False)}
    probe=pilot(_FRAMES,_CAL,_HOST,_STOP)
    (OUT/'pilot.json').write_text(json.dumps(probe,ensure_ascii=False,indent=2)+'\n')
    keys=list(catalog.itertuples(index=False,name=None));receipts=[]
    print(json.dumps(dict(stage='pilot_passed',rows=probe['rows'],seconds=round(probe['elapsed_seconds'],2),products=len(keys),workers=workers)),flush=True)
    with mp.get_context('fork').Pool(processes=min(4,max(1,workers))) as pool:
        for receipt in pool.imap_unordered(make_product,keys,chunksize=1):
            receipts.append(receipt)
            if len(receipts)%10==0:print(json.dumps(dict(checkpoints=len(receipts),total=len(keys),elapsed_seconds=round(time.perf_counter()-timer,1))),flush=True)
    panel=OUT/'daily_source_panel.sqlite'
    with sqlite3.connect(panel) as c:
        first=True
        for receipt in sorted(receipts,key=lambda r:(r['exchange'],r['product'])):
            c.execute('ATTACH DATABASE ? AS shard',(receipt['path'],))
            if first:
                c.execute('CREATE TABLE panel AS SELECT * FROM shard.panel WHERE 0');first=False
            c.execute('INSERT INTO panel SELECT * FROM shard.panel');c.commit();c.execute('DETACH DATABASE shard')
        c.execute('CREATE UNIQUE INDEX panel_product_day ON panel(exchange,product,eval_date)')
        c.execute('CREATE INDEX panel_epoch_day ON panel(reference_epoch,eval_date)')
        counts=pd.read_sql_query('SELECT monthly_average_F,input_status,count(*) AS rows FROM panel GROUP BY monthly_average_F,input_status',c)
        counts.to_csv(OUT/'status_counts.csv',index=False)
        old=pd.read_csv(LINE/'outputs/stage008_monthly_raw_matrix/monthly_raw_signal_matrix.csv',dtype=str,keep_default_na=False)
        mismatches=[];matched=0
        for r in old.loc[old.input_ready.eq('True')].to_dict('records'):
            got=c.execute('SELECT reference_epoch,input_ready,raw_signal,fresh_direction_allowed,fresh_after_hardblocks,rsi6 FROM panel WHERE exchange=? AND product=? AND eval_date=?',(r['exchange'],r['product'],r['eval_date'])).fetchone()
            good=got is not None and got[:2]==(r['reference_epoch'],1) and got[2]==r['raw_signal'] and bool(got[3])==(r['fresh_direction_allowed']=='True') and bool(got[4])==(r['fresh_after_hardblocks']=='True') and math.isclose(got[5],float(r['rsi6']),rel_tol=0,abs_tol=1e-10)
            if good:matched+=1
            else:mismatches.append(dict(product=r['product_vt_symbol'],day=r['eval_date'],got=got))
        comparison=dict(old_ready_rows=8998,matched=matched,mismatches=mismatches)
        (OUT/'stage008_comparison.json').write_text(json.dumps(comparison,ensure_ascii=False,indent=2)+'\n')
        if mismatches or matched!=8998:raise ValueError('stage008_ready_regression_mismatch')
    after=DB.stat();assert (before.st_size,before.st_mtime_ns,before.st_ino)==(after.st_size,after.st_mtime_ns,after.st_ino)
    bindings=dict(source_db=dict(path=str(DB),bytes=before.st_size,mtime_ns=before.st_mtime_ns,inode=before.st_ino,full_db_sha_rehashed=False),
                  calendar_sha256=sha(CALFILE),script_sha256=sha(Path(__file__)),tests_sha256=sha(Path(__file__).with_name('test_stage040_daily_source_panel.py')),
                  stage008_matrix_sha256=sha(LINE/'outputs/stage008_monthly_raw_matrix/monthly_raw_signal_matrix.csv'),frozen=frozen,initial_stop_binding=stopbinding,checkpoints=receipts)
    (OUT/'bindings.json').write_text(json.dumps(bindings,ensure_ascii=False,indent=2)+'\n')
    summary=dict(started_at=begin,completed_at=now(),elapsed_seconds=time.perf_counter()-timer,products=len(keys),calendar_days=len(_CAL),rows=len(keys)*len(_CAL),
                 source_daily_rows=len(data),representatives=sum(r['representatives'] for r in receipts),input_ready=sum(r['input_ready'] for r in receipts),fresh=sum(r['fresh'] for r in receipts),
                 pilot_rows=probe['rows'],stage008_matched=matched,panel_sha256=sha(panel),database_unchanged=True,workers=min(4,max(1,workers)),
                 financial_backtests=0,model_fits=0,labels=0,downloads=0,orders=0,production_modified=False,training_half_r_enabled=False,C2_disabled=False,
                 scope='daily asof representative input panel only; not held-contract daily input or continuous financial source',
                 limits=['all 98 catalog domains retained on every common source day; _F separated, not removed','common inherited calendar not exchange-specific historical PIT',
                         'no future coverage representative substitution','strict same-epoch41; no splicing or imputation','non-fresh skipped shock/range explicitly not evaluated; all ready RSI/previousMA20 retained',
                         'source prices/metadata truth and historical tradability not certified','no execution/C2 qualification or economics labels generated'])
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=4);args=parser.parse_args();run(args.workers)
