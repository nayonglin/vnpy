"""只读核验多shard已完成分钟补丁：任务、补丁SHA、原始快照SHA及逐值闭环。

输出patch_manifest.json与missing_segment_tasks.csv；不合并Stage861、不运行引擎。
可在下载中运行：只读取原子写成的proof，未完成任务明确计为incomplete。
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
from typing import Any
from stage249_prepare_replay import (TASK_COLUMNS,VALUES,read_tasks,normalize_tasks,sha256,
    verify_patch,extract_fragments,validate_serial_bounds,task_moments)


def task_key(task: dict[str,str]) -> tuple[str,...]:
    return tuple(task[column] for column in TASK_COLUMNS)


def audit_patches(tasks: list[dict[str,str]],root: Path) -> dict[str,Any]:
    import pandas as pd
    expected={task_key(t):t for t in normalize_tasks(tasks)}
    completed={};patches=[];errors=[];rows=0
    for proof_path in sorted(root.rglob('*_proof.json')):
        parquet=proof_path.with_name(proof_path.name.replace('_proof.json','.parquet'))
        try:
            proof=verify_patch(parquet,proof_path);source=proof['source']
            if source.get('kind')!='tqsdk_completed_snapshot':raise ValueError('source_not_completed_snapshot')
            raw_path=Path(source['raw_path'])
            if sha256(raw_path)!=source['source_sha256']:raise ValueError('raw_sha256_mismatch')
            raw=pd.read_parquet(raw_path);raw['bar_datetime']=pd.to_datetime(raw.bar_datetime)
            for task in proof['tasks']:
                key=task_key(task)
                if key not in expected:raise ValueError('unrequested_task')
                if key in completed:raise ValueError('duplicate_task')
                symbol_raw=raw.loc[raw.vt_symbol.eq(task['vt_symbol'])]
                bounds=source['serial_bounds'][task['vt_symbol']]
                first=symbol_raw.bar_datetime.min().to_pydatetime();last=symbol_raw.bar_datetime.max().to_pydatetime()
                if first!=datetime.fromisoformat(bounds['earliest']) or last!=datetime.fromisoformat(bounds['latest']) or len(symbol_raw)!=bounds['rows']:
                    raise ValueError('raw_bounds_metadata_mismatch')
                fragment=symbol_raw.loc[symbol_raw.bar_datetime.isin(task_moments(task))].sort_values('bar_datetime')
                validate_serial_bounds(fragment,task,datetime.fromisoformat(source['snapshot_at']),earliest=first,latest=last)
            selected=extract_fragments(raw,proof['tasks']);patch=pd.read_parquet(parquet)
            patch=patch.sort_values(['vt_symbol','bar_datetime']).reset_index(drop=True)
            if len(selected)!=len(patch) or not selected.bar_datetime.equals(patch.bar_datetime):raise ValueError('raw_patch_timestamp_mismatch')
            if any(not selected[col].astype(float).equals(patch[col].astype(float)) for col in VALUES):raise ValueError('raw_patch_value_mismatch')
            for task in proof['tasks']:completed[task_key(task)]=str(proof_path)
            patches.append({'parquet':str(parquet.resolve()),'proof':str(proof_path.resolve()),
                'sha256':proof['sha256'],'proof_sha256':sha256(proof_path),'raw_path':str(raw_path.resolve()),
                'raw_sha256':source['source_sha256'],'rows':proof['rows'],'segments':len(proof['tasks'])})
            rows+=len(patch)
        except (OSError,ValueError,KeyError,TypeError) as error:
            errors.append(f'{proof_path}:{str(error)}')
    missing=[task for key,task in expected.items() if key not in completed]
    return {'status':'failed' if errors else 'incomplete' if missing else 'complete',
            'expected_segments':len(expected),'completed_segments':len(completed),'missing_segments':len(missing),
            'rows':rows,'patches':patches,'missing_tasks':missing,'errors':errors,'order_api_calls':0,'cancel_api_calls':0}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tasks',type=Path,required=True);parser.add_argument('--patch-root',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();report=audit_patches(read_tasks(args.tasks),args.patch_root)
    report.update(tasks_path=str(args.tasks.resolve()),tasks_sha256=sha256(args.tasks),patch_root=str(args.patch_root.resolve()))
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/'patch_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    with (args.output_dir/'missing_segment_tasks.csv').open('w',newline='',encoding='utf-8-sig') as handle:
        writer=csv.DictWriter(handle,fieldnames=TASK_COLUMNS);writer.writeheader();writer.writerows(report['missing_tasks'])
    print(json.dumps({k:v for k,v in report.items() if k not in {'patches','missing_tasks'}},ensure_ascii=False))
    return 0 if report['status']=='complete' else 1

if __name__=='__main__':raise SystemExit(main())
