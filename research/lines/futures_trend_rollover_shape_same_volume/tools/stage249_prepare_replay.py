"""Stage249 交易日分段任务与分钟补丁验收；只读数据，不下载或运行引擎。

plan: --repo-root ROOT --coverage CSV --output-dir OUT [--cache CSV]
coverage 必须有 vt_symbol 及 trading_day/entry_date；推荐引擎实际访问 trading_day。
若使用旧 Stage246 entry_date，它仅是预填任务，不证明修复后交易路径覆盖。
分段区间为上海本地无时区分钟起始标签，左闭右开，24:00 表示次日00:00。

日历规则来自 Stage246 交易所原始资料审计：普通相邻日与周五至周一有夜盘，
节前长间隔无夜盘；2020-02-03..2020-05-05 暂停夜盘，05-06晚恢复。
https://www.shfe.com.cn/services/calenderandholidays/tradinghours/
https://www.csrc.gov.cn/csrc/c100028/c1000838/content.shtml
夜盘归属下一交易日，凌晨归属其前一晚同一会话，而非自然日所属交易日。
"""
from __future__ import annotations
import argparse
import csv
from datetime import date, datetime, time, timedelta
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping

NIGHT_TO_23 = {'rb','hc','fu','ru','sp','jm','MA','OI','CF','FG','SA','SH'}
NIGHT_TO_01 = {'cu'}
NIGHT_TO_0230 = {'au'}
DAY_ONLY = {'AP','SM','si','lc','lh'}
ALL_PRODUCTS = NIGHT_TO_23 | NIGHT_TO_01 | NIGHT_TO_0230 | DAY_ONLY
TASK_COLUMNS = ['vt_symbol','trading_day','natural_date','start','end_exclusive','session']
VALUES = ['open','high','low','close','volume','open_oi','close_oi']
CACHE_NAME = 'qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_stage861_stage860_full_visual_atlas_v1.csv'


def sha256(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def product_of(symbol: str) -> str:
    match=re.fullmatch(r'([A-Za-z]+)[0-9]+\.(SHFE|DCE|CZCE|GFEX)',symbol)
    if not match or match.group(1) not in ALL_PRODUCTS:raise ValueError(f'unsupported_product:{symbol}')
    return match.group(1)


def tasks_for_trade_day(symbol: str, trading_day: str, calendar: Any) -> list[dict[str,str]]:
    product=product_of(symbol);target=date.fromisoformat(str(trading_day))
    dates=sorted({date.fromisoformat(str(day)[:10]) for day in calendar})
    if target not in dates:raise ValueError('target_not_in_trading_calendar')
    preceding=[day for day in dates if day<target]
    if not preceding:raise ValueError('preceding_trading_day_unavailable')
    previous=preceding[-1]; gap=(target-previous).days
    active=gap==1 or (previous.weekday()==4 and target.weekday()==0 and gap==3)
    active=active and not date(2020,2,3)<=previous<date(2020,5,6)
    tasks=[]
    def add(day:date,start:str,end:str,session:str):
        tasks.append(dict(vt_symbol=symbol,trading_day=target.isoformat(),natural_date=day.isoformat(),
                          start=start,end_exclusive=end,session=session))
    if active and product not in DAY_ONLY:
        add(previous,'21:00','23:00' if product in NIGHT_TO_23 else '24:00','night')
        if product in NIGHT_TO_01|NIGHT_TO_0230:
            add(previous+timedelta(days=1),'00:00','01:00' if product in NIGHT_TO_01 else '02:30','early')
    for start,end in [('09:00','10:15'),('10:30','11:30'),('13:30','15:00')]:
        add(target,start,end,'day')
    return tasks


def task_moments(task: Mapping[str,Any]) -> set[datetime]:
    day=date.fromisoformat(str(task['natural_date']))
    start=str(task['start']);end=str(task['end_exclusive'])
    if not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]',start):raise ValueError('invalid_start_time')
    if end!='24:00' and not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]',end):raise ValueError('invalid_end_time')
    first=datetime.combine(day,time.fromisoformat(start))
    last=datetime.combine(day+timedelta(days=1),time()) if end=='24:00' else datetime.combine(day,time.fromisoformat(end))
    if last<=first:raise ValueError('empty_or_reversed_segment')
    return {first+timedelta(minutes=i) for i in range(int((last-first).total_seconds()/60))}


def normalize_tasks(rows: Any) -> list[dict[str,str]]:
    if not isinstance(rows,list) or not rows:raise ValueError('empty_tasks')
    result=[];occupied=set()
    for row in rows:
        task={key:str(row.get(key,'')).strip() for key in TASK_COLUMNS}
        if not task['vt_symbol']:task['vt_symbol']=str(row.get('symbol','')).strip()
        product_of(task['vt_symbol']); date.fromisoformat(task['trading_day'])
        moments=task_moments(task)
        if date.fromisoformat(task['natural_date'])>date.fromisoformat(task['trading_day']):
            raise ValueError('natural_date_after_trading_day')
        keys={(task['vt_symbol'],moment) for moment in moments}
        if keys & occupied:raise ValueError('duplicate_or_overlapping_tasks')
        occupied.update(keys);result.append(task)
    return sorted(result,key=lambda t:(t['natural_date'],t['vt_symbol'],t['start']))


def read_tasks(path: Path) -> list[dict[str,str]]:
    if path.suffix.lower()=='.json':
        payload=json.loads(path.read_text(encoding='utf-8-sig'))
        rows=payload['tasks'] if isinstance(payload,dict) else payload
    else:
        with path.open(encoding='utf-8-sig',newline='') as handle:rows=list(csv.DictReader(handle))
    return normalize_tasks(rows)


def validate_fragment(frame: Any, task: Mapping[str,Any]) -> dict[str,Any]:
    import numpy as np
    import pandas as pd
    if frame.empty or not {'vt_symbol','bar_datetime',*VALUES}.issubset(frame.columns):raise ValueError('fragment_columns_or_rows_missing')
    if set(frame.vt_symbol.astype(str))!={task['vt_symbol']}:raise ValueError('fragment_symbol_mismatch')
    moments=pd.to_datetime(frame.bar_datetime,errors='coerce')
    if moments.isna().any() or moments.dt.tz is not None:raise ValueError('fragment_datetime_invalid')
    if moments.duplicated().any() or not moments.is_monotonic_increasing:raise ValueError('fragment_duplicate_or_unsorted')
    if {value.to_pydatetime() for value in moments}!=task_moments(task):raise ValueError('fragment_minute_grid_mismatch')
    values=frame[VALUES].apply(pd.to_numeric,errors='coerce')
    if not np.isfinite(values.to_numpy()).all():raise ValueError('fragment_nonfinite_values')
    prices=values[['open','high','low','close']]
    if not (prices>0).all().all() or not (values[['volume','open_oi','close_oi']]>=0).all().all():raise ValueError('fragment_values_out_of_range')
    if not values.high.ge(prices.max(axis=1)).all() or not values.low.le(prices.min(axis=1)).all():raise ValueError('fragment_invalid_ohlc')
    return {**task,'rows':len(frame),'first_minute':str(moments.min()),'last_minute':str(moments.max()),'status':'complete'}


def extract_fragments(frame: Any, tasks: list[dict[str,str]]) -> Any:
    import pandas as pd
    frame=frame.copy();frame['bar_datetime']=pd.to_datetime(frame['bar_datetime'],errors='coerce')
    pieces=[]
    for task in tasks:
        selected=frame.loc[frame.vt_symbol.astype(str).eq(task['vt_symbol']) & frame.bar_datetime.isin(task_moments(task))].copy()
        selected=selected.sort_values('bar_datetime')
        validate_fragment(selected,task)
        selected['bar_date']=task['natural_date'];selected['trading_day']=task['trading_day']
        selected['minute_source']='stage249_completed_trading_day_fragment'
        pieces.append(selected[['vt_symbol','bar_datetime','bar_date','trading_day',*VALUES,'minute_source']])
    joined=pd.concat(pieces,ignore_index=True).sort_values(['vt_symbol','bar_datetime']).reset_index(drop=True)
    if joined.duplicated(['vt_symbol','bar_datetime']).any():raise ValueError('patch_duplicate_minute')
    return joined


def validate_serial_bounds(frame: Any, task: Mapping[str,Any], snapshot: datetime, *, earliest: datetime, latest: datetime) -> None:
    moments=task_moments(task)
    if earliest.tzinfo is not None or latest.tzinfo is not None or snapshot.tzinfo is not None:raise ValueError('serial_timezone_invalid')
    if not earliest<min(moments) or latest<max(moments) or latest>=snapshot:raise ValueError('serial_snapshot_bounds_invalid')
    if max(moments)+timedelta(minutes=1)>snapshot:raise ValueError('fragment_not_completed_at_snapshot')
    validate_fragment(frame,task)


def save_patch(folder: Path, tasks: list[dict[str,str]], frame: Any, source: dict[str,Any]) -> dict[str,str]:
    tasks=normalize_tasks(tasks);joined=extract_fragments(frame,tasks)
    identity=hashlib.sha256(json.dumps(tasks,sort_keys=True).encode()).hexdigest()[:20]
    folder.mkdir(parents=True,exist_ok=True)
    parquet=folder/f'{identity}.parquet';proof_path=folder/f'{identity}_proof.json'
    temp=folder/f'{identity}.{os.getpid()}.tmp.parquet';joined.to_parquet(temp,index=False);os.replace(temp,parquet)
    checks=[]
    for task in tasks:
        selected=joined.loc[joined.vt_symbol.eq(task['vt_symbol']) & joined.bar_datetime.isin(task_moments(task))]
        checks.append(validate_fragment(selected,task))
    proof={'status':'complete','rows':len(joined),'sha256':sha256(parquet),'tasks':tasks,'segments':checks,
           'source':source,'order_api_calls':0,'cancel_api_calls':0,'created_at':datetime.now().astimezone().isoformat()}
    temporary=proof_path.with_suffix(f'.{os.getpid()}.tmp');temporary.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');os.replace(temporary,proof_path)
    return {'parquet':str(parquet),'proof':str(proof_path)}


def verify_patch(parquet: Path, proof_path: Path) -> dict[str,Any]:
    import pandas as pd
    proof=json.loads(proof_path.read_text())
    if proof.get('status')!='complete' or sha256(parquet)!=proof.get('sha256'):raise ValueError('patch_sha256_or_status_invalid')
    tasks=normalize_tasks(proof.get('tasks'));frame=pd.read_parquet(parquet)
    selected=extract_fragments(frame,tasks)
    if len(selected)!=len(frame) or len(frame)!=proof.get('rows'):raise ValueError('patch_extra_or_missing_rows')
    if list(frame.trading_day.astype(str))!=list(selected.trading_day.astype(str)) or list(frame.bar_date.astype(str))!=list(selected.bar_date.astype(str)):
        raise ValueError('patch_day_labels_invalid')
    return proof


def read_calendar(root: Path) -> list[str]:
    with sqlite3.connect(f'file:{root / ".vntrader/database.db"}?mode=ro',uri=True) as db:
        return [row[0] for row in db.execute("select distinct substr(datetime,1,10) from dbbardata where interval='d' order by 1")]


def audit_cache(cache: Path,tasks: list[dict[str,str]],accepted_minute_dir: Path | None = None) -> tuple[list[dict[str,Any]],list[dict[str,str]]]:
    import pandas as pd
    symbols={t['vt_symbol'] for t in tasks};frames=[]
    for chunk in pd.read_csv(cache,usecols=['vt_symbol','bar_datetime',*VALUES],chunksize=100000):
        selected=chunk.loc[chunk.vt_symbol.isin(symbols)]
        if len(selected):frames.append(selected)
    data=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame(columns=['vt_symbol','bar_datetime',*VALUES])
    data['bar_datetime']=pd.to_datetime(data.bar_datetime,errors='coerce')
    groups={symbol:frame for symbol,frame in data.groupby('vt_symbol')}
    records=[];missing=[];accepted_cache={}
    for task in tasks:
        frame=groups.get(task['vt_symbol'],data.iloc[:0]); selected=frame.loc[frame.bar_datetime.isin(task_moments(task))].sort_values('bar_datetime')
        try:record=validate_fragment(selected,task)
        except ValueError as error:
            record={**task,'rows':len(selected),'expected_rows':len(task_moments(task)),'status':'missing_or_invalid','reason':str(error)}
            missing.append(task)
        if accepted_minute_dir is not None:
            day=task['natural_date']
            if day not in accepted_cache:
                path=accepted_minute_dir/f"{day.replace('-','')}.parquet"
                proof_path=accepted_minute_dir/f"{day.replace('-','')}_proof.json"
                try:
                    proof=json.loads(proof_path.read_text())
                    if sha256(path)!=proof.get('sha256'):raise ValueError('accepted_source_hash_mismatch')
                    accepted=pd.read_parquet(path);accepted['bar_datetime']=pd.to_datetime(accepted.bar_datetime)
                    accepted_cache[day]=(accepted,proof,str(path))
                except (OSError,ValueError,KeyError):accepted_cache[day]=None
            source=accepted_cache[day]
            status='accepted_source_missing_or_invalid'
            if source is not None:
                accepted,proof,path=source
                expected=accepted.loc[accepted.vt_symbol.eq(task['vt_symbol']) & accepted.bar_datetime.isin(task_moments(task))].sort_values('bar_datetime')
                try:
                    bound=proof['raw_serial_ranges'][task['vt_symbol']]
                    if task['vt_symbol'] not in proof['all_cached_symbols']:raise ValueError('symbol_unproven')
                    validate_serial_bounds(expected,task,datetime.fromisoformat(proof['snapshot_at']),
                        earliest=datetime.fromisoformat(bound['earliest']),latest=datetime.fromisoformat(bound['latest']))
                    # Exact equality is intentional: both are the same downloaded OHLCV/OI source.
                    left=selected[['bar_datetime',*VALUES]].reset_index(drop=True)
                    right=expected[['bar_datetime',*VALUES]].reset_index(drop=True)
                    same=len(left)==len(right) and left.bar_datetime.equals(right.bar_datetime)
                    same=same and all(left[col].astype(float).equals(right[col].astype(float)) for col in VALUES)
                    status='accepted_identical' if same else 'accepted_values_differ'
                    record['accepted_source']=path;record['accepted_source_sha256']=proof['sha256']
                except (ValueError,KeyError,TypeError):status='accepted_source_segment_invalid'
            record['source_status']=status
            if status!='accepted_identical' and task not in missing:missing.append(task)
        else:record['source_status']='structural_only_not_completed_source_proof'
        records.append(record)
    return records,missing


def assert_session_contract(tasks: list[dict[str,str]],calendar: Any,helper_path: Path) -> None:
    spec=importlib.util.spec_from_file_location('stage249_execution_session_contract',helper_path)
    if spec is None or spec.loader is None:raise ValueError('session_contract_helper_unavailable')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    grouped={}
    for task in tasks:grouped.setdefault((task['vt_symbol'],task['trading_day']),set()).update(task_moments(task))
    for (symbol,day),expected in grouped.items():
        observed={value.to_pydatetime() if hasattr(value,'to_pydatetime') else value
                  for value in module.session_minutes(symbol,day,calendar)}
        if expected!=observed:raise ValueError(f'session_contract_mismatch:{symbol}:{day}')


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root',required=True,type=Path)
    parser.add_argument('--coverage',required=True,type=Path)
    parser.add_argument('--output-dir',required=True,type=Path)
    parser.add_argument('--cache',type=Path)
    parser.add_argument('--accepted-minute-dir',type=Path,help='Stage246已验收entry_minute_download，要求源SHA和逐值一致')
    parser.add_argument('--execution-helper',type=Path,help='修复工作区qmt_roll_intraday_execution.py；默认repo-root下同名helper')
    args=parser.parse_args();calendar=read_calendar(args.repo_root.resolve())
    with args.coverage.open(encoding='utf-8-sig',newline='') as handle:rows=list(csv.DictReader(handle))
    keys=set()
    for row in rows:
        day=row.get('trading_day') or row.get('trading_date') or row.get('entry_date')
        if not day or not row.get('vt_symbol'):raise ValueError('coverage_missing_symbol_or_trading_day')
        keys.add((row['vt_symbol'],day[:10]))
    tasks=normalize_tasks([task for symbol,day in sorted(keys) for task in tasks_for_trade_day(symbol,day,calendar)])
    out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    cache=args.cache or args.repo_root/'examples/portfolio_backtesting/backtest_outputs'/CACHE_NAME
    helper=args.execution_helper or args.repo_root/'examples/portfolio_backtesting/qmt_roll_intraday_execution.py'
    if helper.is_file():assert_session_contract(tasks,calendar,helper)
    elif args.execution_helper:raise ValueError('session_contract_helper_missing')
    checks,missing=audit_cache(cache,tasks,accepted_minute_dir=args.accepted_minute_dir)
    for name,values in [('all_segment_tasks.csv',tasks),('missing_segment_tasks.csv',missing)]:
        with (out/name).open('w',newline='',encoding='utf-8-sig') as handle:
            writer=csv.DictWriter(handle,fieldnames=TASK_COLUMNS);writer.writeheader();writer.writerows(values)
    summary={'status':'complete' if not missing else 'incomplete','coverage':str(args.coverage.resolve()),
             'coverage_sha256':sha256(args.coverage),'cache':str(cache.resolve()),'cache_sha256':sha256(cache),
             'execution_helper':str(helper.resolve()) if helper.is_file() else None,
             'execution_helper_sha256':sha256(helper) if helper.is_file() else None,
             'accepted_minute_dir':str(args.accepted_minute_dir.resolve()) if args.accepted_minute_dir else None,
             'calendar_database':str((args.repo_root/'.vntrader/database.db').resolve()),
             'calendar_sha256':hashlib.sha256(json.dumps(calendar).encode()).hexdigest(),
             'calendar_first':calendar[0],'calendar_last':calendar[-1], 'keys':len(keys),'segments':len(tasks),
             'missing_segments':len(missing),'required_minutes':sum(len(task_moments(t)) for t in tasks),
             'rows':checks,'limitation':'Supplied keys only; actual corrected engine access closure is required.'}
    (out/'coverage_plan.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='rows'},ensure_ascii=False))
    return 0

if __name__=='__main__':raise SystemExit(main())
