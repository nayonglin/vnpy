"""Bind two existing conditional witnesses to daily decisions, never actual fills."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import talib

LINE=Path(__file__).resolve().parents[1]
ROOT=LINE.parents[2]
PRIOR=ROOT/'research/lines/futures_trend_rollover_shape_same_volume/outputs'
OUT=LINE/'outputs/stage028_real_witness_link'


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def select_reference_window(calendar,execution_day,signal_day,lookup):
    if len(calendar)!=len(set(calendar)) or calendar!=sorted(calendar):
        raise ValueError('calendar_not_strict')
    i=calendar.index(execution_day)
    if i<1 or calendar[i-1]!=signal_day:
        raise ValueError('signal_execution_clock')
    if i<40:raise ValueError('insufficient_history')
    requested=calendar[i-40:i+1]
    if any(day not in lookup for day in requested):raise ValueError('history_missing_calendar_day')
    history=[lookup[day] for day in requested]
    next_day=calendar[i+1] if i+1<len(calendar) else None
    next_bar=lookup.get(next_day)
    proxy=None if next_bar is None else dict(trade_date=next_day,daily_open=next_bar['open'],
                                           canonical_anchor_verified=False,is_actual_fill=False)
    return dict(history=history,signal_bar=lookup[signal_day],next_open_proxy=proxy)


def run():
    # The adapter author/reviewer must finish before this actual probe is run.
    from stage026_daily_exit_adapter import decide_daily_exit
    if OUT.exists() and any(OUT.iterdir()):raise ValueError('output_exists_no_overwrite')
    witness=LINE/'outputs/stage014_minute_witness'
    report=json.loads((witness/'summary.json').read_text())
    kernel=ROOT/'examples/portfolio_backtesting/qmt_roll_intraday_execution.py'
    if digest(kernel)!=report['kernel_sha256']:raise ValueError('witness_execution_kernel_changed')
    source=pd.read_csv(witness/'source_audit.csv',keep_default_na=False)
    rows=source.loc[source.status.eq('reference_policy_resolved')].to_dict('records')
    if len(rows)!=2 or {r['event_id'] for r in rows}!={'DCE.JM.202201@2021-09-30','SHFE.AU.202112@2021-07-30'}:
        raise ValueError('predeclared_conditional_witness_set_changed')
    events={e['event_id']:e for e in report['events']}
    for r in rows:
        if digest(witness/r['evidence_file'])!=r['evidence_sha256']:raise ValueError('minute_projection_changed')
    cal_path=PRIOR/'stage265_deep_daily/rqalpha/trading_dates.npy'
    raw=np.load(cal_path,allow_pickle=False)
    calendar=[str(d.date()) for d in pd.to_datetime(raw.astype(str),format='%Y%m%d')]
    wanted=set()
    for r in rows:
        e=events[r['event_id']];i=calendar.index(e['reference_execution_date'])
        wanted.update((e['reference_epoch'],day) for day in calendar[i-40:i+2])
    db=PRIOR/'stage266_clean_daily/clean_daily.sqlite';before=db.stat()
    pairs=sorted(wanted);values=','.join('(?,?)' for _ in pairs)
    query=f'WITH wanted(epoch,day) AS (VALUES {values}) SELECT b.contract_epoch_id,b.trade_date,b.open,b.high,b.low,b.close,b.source_id FROM daily_bars b JOIN wanted w ON b.contract_epoch_id=w.epoch AND b.trade_date=w.day ORDER BY b.contract_epoch_id,b.trade_date'
    with sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True) as connection:
        connection.execute('PRAGMA query_only=ON')
        data=pd.read_sql_query(query,connection,params=[x for p in pairs for x in p])
    after=db.stat()
    if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):
        raise ValueError('input_database_changed')
    if data.duplicated(['contract_epoch_id','trade_date']).any():raise ValueError('duplicate_input_key')
    look={(r['contract_epoch_id'],r['trade_date']):r for r in data.to_dict('records')}
    outputs=[];inputs=[]
    for r in rows:
        e=events[r['event_id']]
        lookup={day:bar for (epoch,day),bar in look.items() if epoch==e['reference_epoch']}
        window=select_reference_window(calendar,e['reference_execution_date'],e['eval_date'],lookup)
        history=[{k:float(bar[k]) for k in ('open','high','low','close')} for bar in window['history']]
        current=history[-1]
        closes=np.array([bar['close'] for bar in history],dtype=float)
        rsi=float(talib.RSI(closes,timeperiod=6)[-1])
        ma_previous=float(closes[-21:-1].mean())
        signal=window['signal_bar']
        state=dict(direction=e['direction'],qty=2,entry_price=e['entry_reference_price'],
                   stop_price=e['stop'],max_profit_pct=0,highest_price=signal['high'],lowest_price=signal['low'],
                   prev2day_stop_price=None,rsi_partial_exit_done=False,bars_since_entry=1,
                   contract=e['native'],target_contract=e['native'],pending_roll=False)
        item=dict(event_id=e['event_id'],epoch=e['reference_epoch'],signal_day=e['eval_date'],
                  execution_day=e['reference_execution_date'],state=state,history=history,bar=current,
                  rsi_value=rsi,ma_long_prev_value=ma_previous,
                  c2_outcome=r['outcome'],next_open_proxy=window['next_open_proxy'],
                  conditional_witness_file=r['evidence_file'],conditional_witness_sha256=r['evidence_sha256'])
        inputs.append(item)
        if r['outcome']=='c2_stop':
            decision=dict(status='reference_c2_flat_no_daily_position',request=None,
                          reference_c2_fill=float(r['reference_fill_price']),is_actual_trade=False)
        elif r['outcome']=='confirmation_disarms_c2':
            decision=decide_daily_exit(state=state,history=history,bar=current,
                                       rsi_value=rsi,ma_long_prev_value=ma_previous)
        else:raise ValueError('unexpected_bound_witness_outcome')
        outputs.append(dict(event_id=e['event_id'],c2_outcome=r['outcome'],daily_decision=decision,
                            next_open_proxy=window['next_open_proxy'],
                            next_open_used_as_actual_fill=False,diagnostic_qty=2,actual_qty_verified=False,
                            actual_trading=False,complete_strategy=False,net_60d_label=False,
                            source_truth_certified=False))
    OUT.mkdir(parents=True,exist_ok=True)
    data.to_csv(OUT/'bound_daily_rows.csv',index=False)
    for name,value in [('inputs.json',inputs),('results.json',outputs)]:
        (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    bindings={str(p.relative_to(ROOT)):digest(p) for p in [Path(__file__),LINE/'tools/stage026_daily_exit_adapter.py',
             witness/'summary.json',witness/'source_audit.csv',cal_path,OUT/'bound_daily_rows.csv',OUT/'inputs.json',OUT/'results.json']}
    summary=dict(issued_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),events=2,
                 source_daily_rows=len(data),history_bars_per_event=41,
                 next_open_proxies_certified_as_fill=0,actual_trades=0,financial_source_replays=0,
                 model_fits=0,net_60d_labels=0,production_changes=0,downloads=0,bindings=bindings,
                 database_stat=dict(path=str(db),bytes=before.st_size,mtime_ns=before.st_mtime_ns,inode=before.st_ino),
                 limits=['two previously selected conditional witnesses only; no source truth or real trade proof',
                         'qty2 diagnostic, not actual or selected training sizing policy',
                         'signal-date age1 conditional on normal immediate next-source-day open',
                         'daily open is proxy only; not executed or fed to actual-fill ledger',
                         'account exits excluded; roll and full source driver absent'])
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(events=outputs,daily_rows=len(data)),ensure_ascii=False))


if __name__=='__main__':run()
