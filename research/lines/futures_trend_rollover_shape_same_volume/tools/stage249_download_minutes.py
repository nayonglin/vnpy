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


def download_snapshot(tasks:list[dict[str,str]],credentials:dict[str,str],timeout:float,*,data_length:int=1000) -> tuple[Any,dict[str,Any]]:
    import pandas as pd
    from tqsdk import TqApi,TqAuth,TqBacktest,TqSim
    days=sorted({t['natural_date'] for t in tasks})
    if not days or (datetime.fromisoformat(days[-1])-datetime.fromisoformat(days[0])).days>=14:raise ValueError('snapshot_span_exceeds_14_days')
    if data_length not in {1000,10000} or (len(days)>1 and data_length!=10000):raise ValueError('multi_day_snapshot_requires_10000_bars')
    day=days[-1];snapshot=datetime.fromisoformat(day)+timedelta(days=1,hours=8)
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
            frame=frame[['vt_symbol','bar_datetime',*VALUES]].sort_values('bar_datetime').reset_index(drop=True)
            if frame.empty:raise ValueError('serial_empty')
            first=frame.bar_datetime.min().to_pydatetime();last=frame.bar_datetime.max().to_pydatetime()
            for task in [t for t in tasks if t['vt_symbol']==symbol]:
                selected=frame.loc[frame.bar_datetime.isin(task_moments(task))]
                validate_serial_bounds(selected,task,snapshot,earliest=first,latest=last)
            frames.append(frame);bounds[symbol]={'earliest':str(first),'latest':str(last),'rows':len(frame)}
        raw=pd.concat(frames,ignore_index=True)
        return raw,{'kind':'tqsdk_completed_snapshot','snapshot_at':snapshot.isoformat(),'serial_bounds':bounds,
                    'serial_length':data_length,'timezone':'Asia/Shanghai','order_api_calls':0,'cancel_api_calls':0}
    finally:
        if api is not None:api.close()
        serials.clear();api=None;gc.collect()
        if was_gc_enabled:gc.enable()


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tasks',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    source=parser.add_mutually_exclusive_group()
    source.add_argument('--source-parquet',type=Path)
    source.add_argument('--download',action='store_true')
    parser.add_argument('--credential-settings',type=Path)
    parser.add_argument('--timeout',type=float,default=150.0)
    parser.add_argument('--limit',type=int,default=0,help='最多自然日批次；范围未闭合时status=partial')
    args=parser.parse_args();tasks=read_tasks(args.tasks)
    if not args.download and args.source_parquet is None:
        print(json.dumps({'status':'plan_only','segments':len(tasks),
                          'natural_dates':len({t['natural_date'] for t in tasks}),
                          'expected_rows':sum(len(task_moments(t)) for t in tasks)}));return 0
    if args.download and not args.credential_settings:parser.error('--download requires --credential-settings')
    if args.limit<0 or args.timeout<=0:parser.error('limit must be >=0 and timeout must be >0')
    os.umask(0o077);os.environ['TZ']='Asia/Shanghai'
    if hasattr(time,'tzset'):time.tzset()
    import pandas as pd
    by_day=defaultdict(list)
    for task in tasks:by_day[task['natural_date']].append(task)
    days=sorted(by_day)
    if args.limit:days=days[:args.limit]
    out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    credentials=json.loads(args.credential_settings.read_text()) if args.download else None
    offline=pd.read_parquet(args.source_parquet) if args.source_parquet else None
    offline_sha=sha256(args.source_parquet) if args.source_parquet else None
    patches=[];failures=[];completed=0
    for day in days:
        day_tasks=by_day[day];identity=task_identity(day_tasks)
        destination=out/'patches';parquet=destination/f'{identity}.parquet';proof=destination/f'{identity}_proof.json'
        try:
            if parquet.is_file() and proof.is_file():
                existing=verify_patch(parquet,proof)
                source_record=existing.get('source',{})
                expected_source_sha=offline_sha if offline is not None else sha256(Path(source_record['raw_path']))
                if expected_source_sha!=source_record.get('source_sha256'):raise ValueError('cached_raw_source_sha256_mismatch')
                patch={'parquet':str(parquet),'proof':str(proof)}
            elif offline is not None:
                patch=save_patch(destination,day_tasks,offline,{'kind':'offline_parquet',
                    'raw_path':str(args.source_parquet.resolve()),'source_sha256':offline_sha})
            else:
                raw,source_record=download_snapshot(day_tasks,credentials,args.timeout)
                raw_folder=out/'raw';raw_folder.mkdir(exist_ok=True)
                raw_path=raw_folder/f'{day}_{identity}.parquet'
                temporary=raw_path.with_suffix(f'.{os.getpid()}.tmp.parquet');raw.to_parquet(temporary,index=False);os.replace(temporary,raw_path)
                source_record.update(raw_path=str(raw_path),source_sha256=sha256(raw_path))
                patch=save_patch(destination,day_tasks,raw,source_record)
            patches.append(patch);completed+=len(day_tasks)
            print(f'{day}: complete segments={len(day_tasks)}',flush=True)
        except Exception as error:
            # SDK error messages may contain credentials; record only type.
            failures.append({'natural_date':day,'error_type':type(error).__name__,'segments':len(day_tasks)})
            print(f'{day}: failed error_type={type(error).__name__}',flush=True)
        progress={'status':'complete' if completed==len(tasks) and not failures else 'partial',
                  'tasks_path':str(args.tasks.resolve()),'tasks_sha256':sha256(args.tasks),'segments':len(tasks),
                  'completed_segments':completed,'patches':patches,'failures':failures,
                  'selected_days':days,'download_enabled':args.download,'order_api_calls':0,'cancel_api_calls':0}
        temporary=out/f'progress.{os.getpid()}.tmp';temporary.write_text(json.dumps(progress,ensure_ascii=False,indent=2)+'\n');os.replace(temporary,out/'progress.json')
        if failures:break  # Stop on the first failure; no automatic retry or repeated login attempts.
    return 0 if completed==len(tasks) and not failures else 1

if __name__=='__main__':raise SystemExit(main())
