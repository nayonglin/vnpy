"""Stage249最多14自然日的独立合约10000根完成快照补数。

默认只读计划；--download显式启用TqSim行情，最多1会话。每合约独立serial，
快照为批次最后自然日次日08:00；原始序列与每个请求片段逐个做边界/完整网格
验收。任何失败立即停止；不重试、不合并缓存、不执行交易。
TqSdk官方get_kline_serial最大长度10000：
https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html
"""
from __future__ import annotations
import argparse
from datetime import datetime,timedelta
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any
from stage249_prepare_replay import read_tasks,normalize_tasks,save_patch,verify_patch,sha256,task_moments
from stage249_download_minutes import download_snapshot,task_identity


def group_task_batches(tasks:list[dict[str,str]]) -> list[list[dict[str,str]]]:
    tasks=normalize_tasks(tasks);batches=[];current=[];start=None
    for task in tasks:
        day=datetime.fromisoformat(task['natural_date'])
        if start is None or (day-start).days>=14:
            if current:batches.append(current)
            current=[];start=day
        current.append(task)
    if current:batches.append(current)
    return batches


def snapshot_spec(tasks:list[dict[str,str]]) -> tuple[datetime,int]:
    dates=sorted({datetime.fromisoformat(t['natural_date']) for t in tasks})
    if not dates or (dates[-1]-dates[0]).days>=14:raise ValueError('snapshot_span_exceeds_14_days')
    return dates[-1]+timedelta(days=1,hours=8),10000


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tasks',type=Path,required=True);parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--download',action='store_true');parser.add_argument('--credential-settings',type=Path)
    parser.add_argument('--limit-batches',type=int,default=0);parser.add_argument('--timeout',type=float,default=150)
    args=parser.parse_args();tasks=read_tasks(args.tasks);batches=group_task_batches(tasks)
    if not args.download:
        print(json.dumps({'status':'plan_only','segments':len(tasks),'natural_dates':len({t['natural_date'] for t in tasks}),
                          'batches':len(batches),'batch_segments':[len(batch) for batch in batches],'serial_length':10000}));return 0
    if not args.credential_settings:parser.error('--download requires --credential-settings')
    if args.limit_batches<0 or args.timeout<=0:parser.error('invalid limit or timeout')
    out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True);os.umask(0o077)
    os.environ['TZ']='Asia/Shanghai'
    if hasattr(time,'tzset'):time.tzset()
    credentials=json.loads(args.credential_settings.read_text());patches=[];failures=[];completed=0
    selected=batches[:args.limit_batches] if args.limit_batches else batches
    for batch in selected:
        snapshot,length=snapshot_spec(batch);identity=task_identity(batch)
        folder=out/'patches';parquet=folder/f'{identity}.parquet';proof_path=folder/f'{identity}_proof.json'
        try:
            if parquet.is_file() and proof_path.is_file():
                existing=verify_patch(parquet,proof_path)
                if sha256(Path(existing['source']['raw_path']))!=existing['source']['source_sha256']:raise ValueError('cached_raw_source_sha256_mismatch')
                patch={'parquet':str(parquet),'proof':str(proof_path)}
            else:
                raw,source=download_snapshot(batch,credentials,args.timeout,data_length=length)
                if source['snapshot_at']!=snapshot.isoformat():raise ValueError('snapshot_mismatch')
                raw_folder=out/'raw';raw_folder.mkdir(exist_ok=True)
                raw_path=raw_folder/f'{batch[0]["natural_date"]}_{batch[-1]["natural_date"]}_{identity}.parquet'
                temp=raw_path.with_suffix(f'.{os.getpid()}.tmp.parquet');raw.to_parquet(temp,index=False);os.replace(temp,raw_path)
                source.update(raw_path=str(raw_path),source_sha256=sha256(raw_path),batch_natural_dates=sorted({t['natural_date'] for t in batch}))
                patch=save_patch(folder,batch,raw,source)
            patches.append(patch);completed+=len(batch)
            print(f'{batch[0]["natural_date"]}..{batch[-1]["natural_date"]}: complete segments={len(batch)}',flush=True)
        except Exception as error:
            failures.append({'batch_id':identity,'error_type':type(error).__name__})
            print(f'batch {identity}: failed error_type={type(error).__name__}',flush=True)
        progress={'status':'complete' if completed==len(tasks) and not failures else 'partial',
            'tasks_path':str(args.tasks.resolve()),'tasks_sha256':sha256(args.tasks),'segments':len(tasks),'completed_segments':completed,
            'total_batches':len(batches),'selected_batches':len(selected),'patches':patches,'failures':failures,
            'serial_length':10000,'order_api_calls':0,'cancel_api_calls':0}
        temp=out/f'progress.{os.getpid()}.tmp';temp.write_text(json.dumps(progress,ensure_ascii=False,indent=2)+'\n');os.replace(temp,out/'progress.json')
        if failures:break
    return 0 if completed==len(tasks) and not failures else 1

if __name__=='__main__':raise SystemExit(main())
