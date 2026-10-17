"""Stage251 实际入场后缀/普通成交首分钟的只读来源验收与最小任务计划。

复用冻结 Stage249 日历 helper 和数据验收器；显式允许关闭 0.5R 后空 entry。
仅写指定输出目录，不下载、不启动引擎、不修改分钟缓存或旧 proof。
"""
from __future__ import annotations

import argparse
import csv
from datetime import timedelta
import importlib.util
import json
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from stage249_prepare_replay import CACHE_NAME, TASK_COLUMNS, normalize_tasks, read_calendar, sha256, task_moments
from stage249_validate_cache_sources import validate_sources
from stage249_download_minute_batches import group_task_batches


def load_session_helper(path: Path) -> Callable:
    spec = importlib.util.spec_from_file_location('stage251_frozen_session_helper', path)
    if spec is None or spec.loader is None:
        raise ValueError('session_helper_unavailable')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.session_minutes


def local_time(value: Any) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if pd.isna(stamp):
        raise ValueError('invalid_request_time')
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert('Asia/Shanghai').tz_localize(None)
    return stamp


def read_request_rows(path: Path, required: set[str], *, allow_empty: bool = False) -> list[dict]:
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        if not required.issubset(reader.fieldnames or []):
            if allow_empty and not rows and not reader.fieldnames:
                return []
            raise ValueError(f'request_columns_missing:{path.name}')
    return rows


def minute_tasks(symbol: str, trading_day: str, moments: Any) -> list[dict[str, str]]:
    groups: list[list[pd.Timestamp]] = []
    for stamp in sorted({local_time(value) for value in moments}):
        if not groups or stamp.date() != groups[-1][-1].date() or stamp - groups[-1][-1] != timedelta(minutes=1):
            groups.append([])
        groups[-1].append(stamp)
    result = []
    for group in groups:
        start = group[0]
        end = group[-1] + timedelta(minutes=1)
        result.append({'vt_symbol':symbol, 'trading_day':trading_day,
                       'natural_date':start.strftime('%Y-%m-%d'), 'start':start.strftime('%H:%M'),
                       'end_exclusive':'24:00' if end.date() != start.date() else end.strftime('%H:%M'),
                       'session':'night' if start.hour >= 21 else 'early' if start.hour < 3 else 'day'})
    return result


def union_tasks(tasks: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str], set] = {}
    for task in tasks:
        grouped.setdefault((task['vt_symbol'],task['trading_day']),set()).update(task_moments(task))
    merged = [task for (symbol, day), moments in sorted(grouped.items()) for task in minute_tasks(symbol, day, moments)]
    return normalize_tasks(merged) if merged else []


def build_tasks(entries: list[dict], anchors: list[dict], calendar: Any, session: Callable,
                *, allow_empty_entry: bool = False) -> dict[str, Any]:
    if not entries and not allow_empty_entry:
        raise ValueError('empty_entry_requires_explicit_allowance')
    starts: dict[tuple[str,str], pd.Timestamp] = {}
    for row in entries:
        key = (row['vt_symbol'],row['trading_date'])
        start = local_time(row['requested_start'])
        grid = pd.DatetimeIndex(session(*key, calendar))
        if start not in grid:
            raise ValueError(f'entry_start_outside_session:{key}')
        if len(grid[grid >= start]) != int(row['expected_bar_count']):
            raise ValueError(f'entry_count_mismatch:{key}')
        starts[key] = min(start, starts.get(key, start))
    entry_tasks = []
    for (symbol,day), start in sorted(starts.items()):
        grid = pd.DatetimeIndex(session(symbol,day,calendar))
        entry_tasks.extend(minute_tasks(symbol,day,grid[grid >= start]))
    anchor_tasks = []
    for row in anchors:
        symbol,day = row['vt_symbol'],row['trading_date']
        grid = pd.DatetimeIndex(session(symbol,day,calendar))
        if len(grid) == 0 or local_time(row['expected_start']) != grid[0]:
            raise ValueError(f'anchor_start_mismatch:{symbol}:{day}')
        anchor_tasks.extend(minute_tasks(symbol,day,[grid[0]]))
    return {'entry_tasks':union_tasks(entry_tasks),'anchor_tasks':union_tasks(anchor_tasks),
            'entry_request_rows':len(entries),'entry_keys':len(starts),'anchor_request_rows':len(anchors),
            'allow_empty_entry':allow_empty_entry}


def validate_optional(cache: Path, tasks: list[dict], legacy: Path, patch_roots: list[Path]) -> dict:
    if tasks:
        return validate_sources(cache,tasks,legacy,patch_roots)
    return {'status':'complete','segments':0,'source_proven_segments':0,'missing_segments':0,
            'counts':{},'cache':str(cache.resolve()),'cache_sha256':sha256(cache),
            'empty_reason':'no_actual_requests','errors':[],'rows':[],'missing_tasks':[]}


def write_tasks(path: Path, tasks: list[dict]) -> None:
    with path.open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=TASK_COLUMNS)
        writer.writeheader();writer.writerows(tasks)


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root',required=True,type=Path)
    parser.add_argument('--run-dir',required=True,type=Path)
    parser.add_argument('--source-summary',required=True,type=Path)
    parser.add_argument('--legacy-minute-dir',required=True,type=Path)
    parser.add_argument('--output-dir',required=True,type=Path)
    parser.add_argument('--cache',type=Path)
    parser.add_argument('--patch-root',type=Path,action='append',default=[])
    parser.add_argument('--allow-empty-entry',action='store_true')
    parser.add_argument('--allow-cache-change',action='store_true',help='仅候选合入前验源；不声称候选缓存是本次已消费输入')
    args=parser.parse_args()
    cache=args.cache or args.repo_root/'examples/portfolio_backtesting/backtest_outputs'/CACHE_NAME
    helper=args.repo_root/'examples/portfolio_backtesting/qmt_roll_intraday_execution.py'
    entry_path=args.run_dir/'minute_scan_requests.csv';anchor_path=args.run_dir/'execution_anchor_requests.csv'
    provenance_path=args.run_dir/'run_provenance.json'
    inputs=[entry_path,anchor_path,helper,provenance_path,args.source_summary,
            args.repo_root/'.vntrader/database.db',Path(__file__).resolve()]
    input_hashes={str(path.resolve()):sha256(path) for path in inputs}
    cache_before=sha256(cache)
    provenance=json.loads(provenance_path.read_text())
    run_cache_matches=provenance['minute_input_sha256']==cache_before
    if not run_cache_matches and not args.allow_cache_change:
        raise ValueError('cache_differs_from_run_provenance')
    source=json.loads(args.source_summary.read_text())
    if source['status']!='complete':
        raise ValueError('source_summary_not_complete')
    roots=[Path(path) for path in source['patch_roots']]+args.patch_root
    entries=read_request_rows(entry_path,{'vt_symbol','trading_date','requested_start','expected_bar_count'},allow_empty=args.allow_empty_entry)
    anchors=read_request_rows(anchor_path,{'vt_symbol','trading_date','expected_start'})
    plan=build_tasks(entries,anchors,read_calendar(args.repo_root),load_session_helper(helper),allow_empty_entry=args.allow_empty_entry)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    reports={}
    for kind in ['entry','anchor']:
        tasks=plan[f'{kind}_tasks']
        write_tasks(args.output_dir/f'{kind}_all_segment_tasks.csv',tasks)
        reports[kind]=validate_optional(cache,tasks,args.legacy_minute_dir,roots)
        (args.output_dir/f'{kind}_source_validation.json').write_text(json.dumps(reports[kind],ensure_ascii=False,indent=2)+'\n')
    errors=[error for report in reports.values() for error in report['errors']]
    if any(sha256(path)!=input_hashes[str(path.resolve())] for path in inputs):errors.append('request_or_source_inputs_changed')
    if sha256(cache)!=cache_before:errors.append('cache_changed_during_validation')
    missing=union_tasks([task for report in reports.values() for task in report['missing_tasks']])
    write_tasks(args.output_dir/'additional_segment_tasks.csv',missing)
    summary={key:value for key,value in plan.items() if not key.endswith('_tasks')}
    summary.update(status='failed' if errors else 'incomplete' if missing else 'complete',
                   cache=str(cache.resolve()),cache_sha256=cache_before,run_cache_sha256=provenance['minute_input_sha256'],
                   run_input_cache_matches_current=run_cache_matches,actual_consumed_identity_bound=run_cache_matches,
                   input_sha256=input_hashes,patch_roots=[str(path.resolve()) for path in roots],
                   source_reports={kind:{k:v for k,v in report.items() if k not in {'rows','missing_tasks'}} for kind,report in reports.items()},
                   actual_union_minutes=sum(len(task_moments(task)) for task in union_tasks(plan['entry_tasks']+plan['anchor_tasks'])),
                   additional_segments=len(missing),additional_minutes=sum(len(task_moments(task)) for task in missing),
                   additional_batches=len(group_task_batches(missing)) if missing else 0,errors=errors,
                   network_sessions=0,order_api_calls=0,cancel_api_calls=0)
    (args.output_dir/'data_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in {'source_reports','input_sha256','patch_roots'}},ensure_ascii=False))
    return 0 if summary['status']=='complete' else 1


if __name__=='__main__':
    raise SystemExit(main())
