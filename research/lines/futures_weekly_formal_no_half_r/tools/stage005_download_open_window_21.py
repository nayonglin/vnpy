"""按明确分段任务获取已完成分钟补丁；不改缓存、不调用交易方法。

默认只展示计划；离线源用 --source-parquet。真实行情读取需显式 --download。
--tasks 接受CSV/JSON：vt_symbol,trading_day,natural_date,start,end_exclusive,session。
--download --credential-settings PATH [--timeout 150]；凭据与异常正文均不输出。
每个自然日快照截至次日08:00，TqSim + TqBacktest读取1000根历史序列；
请求片段必须完整且原序列早于请求起点，所有原序列bar必须早于快照。
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timedelta
import gc
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any
from stage249_prepare_replay import (read_tasks,task_moments,extract_fragments,validate_serial_bounds,
    save_patch,verify_patch,sha256,VALUES)


def task_identity(tasks:list[dict[str,str]]) -> str:
    return hashlib.sha256(json.dumps(tasks,sort_keys=True).encode()).hexdigest()[:20]


def download_open_window_21(tasks:list[dict[str,str]],credentials:dict[str,str],timeout:float,*,data_length:int=1000) -> tuple[Any,dict[str,Any]]:
    import pandas as pd
    from tqsdk import TqApi,TqAuth,TqBacktest,TqSim
    days=sorted({t['natural_date'] for t in tasks})
    if not days or (datetime.fromisoformat(days[-1])-datetime.fromisoformat(days[0])).days>=14:raise ValueError('snapshot_span_exceeds_14_days')
    if data_length not in {1000,10000} or (len(days)>1 and data_length!=10000):raise ValueError('multi_day_snapshot_requires_10000_bars')
    day=days[-1]
    desired=datetime.fromisoformat(days[0])+timedelta(days=21,hours=8)
    captured_at=datetime.now()
    snapshot=min(desired,captured_at.replace(second=0,microsecond=0)-timedelta(minutes=2))
    data_length=10000
    if snapshot<=datetime.fromisoformat(day):raise ValueError('requested_minute_not_completed')
    symbols=sorted({t['vt_symbol'] for t in tasks});api=None;serials={};frames=[];bounds={}
    started=time.monotonic();was_gc_enabled=gc.isenabled()
    try:
        gc.disable()
        api=TqApi(TqSim(),backtest=TqBacktest(start_dt=snapshot,end_dt=snapshot+timedelta(days=21)),
                  auth=TqAuth(credentials['datafeed.username'],credentials['datafeed.password']),disable_print=True)
        async def subscribe():
            for symbol in symbols:
                contract,exchange=symbol.split('.')
                serials[symbol]=api.get_kline_serial(f'{exchange}.{contract}',60,data_length=data_length)
        api.create_task(subscribe())
        while time.monotonic()-started<timeout:
            if len(serials)==len(symbols) and all(api.is_serial_ready(s) for s in serials.values()):break
            api.wait_update(deadline=time.time()+5)
        for symbol in symbols:
            serial=serials.get(symbol)
            if serial is None or not api.is_serial_ready(serial):raise ValueError('serial_not_ready')
            frame=serial.copy();frame=frame.loc[(frame.id>=0)&(frame.datetime>0)].copy()
            frame['bar_datetime']=pd.to_datetime(frame.datetime,unit='ns',utc=True).dt.tz_convert('Asia/Shanghai').dt.tz_localize(None)
            frame['vt_symbol']=symbol
            frame=frame.loc[frame.bar_datetime+pd.Timedelta(minutes=1)<=snapshot]
            frame=frame[['vt_symbol','bar_datetime',*VALUES]].sort_values('bar_datetime').reset_index(drop=True)
            if frame.empty:raise ValueError('serial_empty')
            first=frame.bar_datetime.min().to_pydatetime();last=frame.bar_datetime.max().to_pydatetime()
            for task in [t for t in tasks if t['vt_symbol']==symbol]:
                selected=frame.loc[frame.bar_datetime.isin(task_moments(task))]
                validate_serial_bounds(selected,task,snapshot,earliest=first,latest=last)
            frames.append(frame);bounds[symbol]={'earliest':str(first),'latest':str(last),'rows':len(frame)}
        raw=pd.concat(frames,ignore_index=True)
        return raw,{'kind':'tqsdk_completed_snapshot','snapshot_at':snapshot.isoformat(),'serial_bounds':bounds,
                    'serial_length':data_length,'timezone':'Asia/Shanghai','captured_at':captured_at.isoformat(),'prefetch_policy':'data_only_real_completed_21_calendar_day_window_no_account_or_prices_simulated','order_api_calls':0,'cancel_api_calls':0}
    finally:
        if api is not None:api.close()
        serials.clear();api=None;gc.collect()
        if was_gc_enabled:gc.enable()

