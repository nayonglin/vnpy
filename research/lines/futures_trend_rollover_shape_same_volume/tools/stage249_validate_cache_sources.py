"""实际交易日分段所消费cache到已完成原始行情的只读闭环验收。

先核Stage246已验收自然日快照；其余分段必须由完整Stage249补丁源逐值证明。
所有Stage249补丁先独立校验原始快照SHA、边界、完整网格及逐值一致。
只输出报告与缺口任务，不下载、不回测、不改cache。
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
from typing import Any
from stage249_prepare_replay import (VALUES,TASK_COLUMNS,read_tasks,normalize_tasks,audit_cache,
                                    sha256,task_moments,validate_fragment)
from stage249_verify_patches import audit_patches


def validate_sources(cache:Path,tasks:list[dict[str,str]],legacy_dir:Path,patch_roots:list[Path]) -> dict[str,Any]:
    import pandas as pd
    tasks=normalize_tasks(tasks);cache_before=sha256(cache)
    rows,_=audit_cache(cache,tasks,accepted_minute_dir=legacy_dir)
    patches=[];source_errors=[];source_reports=[]
    for root in patch_roots:
        contained=[]
        for path in root.rglob('*_proof.json'):contained.extend(json.loads(path.read_text())['tasks'])
        if not contained:source_errors.append(f'patch_root_empty:{root}');continue
        proof_report=audit_patches(contained,root)
        source_reports.append({key:value for key,value in proof_report.items() if key not in {'patches','missing_tasks'}})
        if proof_report['status']!='complete':source_errors.extend(proof_report['errors'] or [f'patch_root_incomplete:{root}']);continue
        for record in proof_report['patches']:
            frame=pd.read_parquet(record['parquet']);frame['_proof']=record['proof'];patches.append(frame)
    patch=pd.concat(patches,ignore_index=True) if patches else pd.DataFrame(columns=['vt_symbol','bar_datetime',*VALUES,'_proof'])
    patch['bar_datetime']=pd.to_datetime(patch.bar_datetime)
    if patch.duplicated(['vt_symbol','bar_datetime']).any():source_errors.append('duplicate_patch_timestamp_across_roots')
    symbols=set(patch.vt_symbol.astype(str));cache_parts=[]
    for chunk in pd.read_csv(cache,usecols=['vt_symbol','bar_datetime',*VALUES],chunksize=100000):
        selected=chunk.loc[chunk.vt_symbol.astype(str).isin(symbols)]
        if len(selected):cache_parts.append(selected)
    current=pd.concat(cache_parts,ignore_index=True) if cache_parts else pd.DataFrame(columns=['vt_symbol','bar_datetime',*VALUES])
    current['bar_datetime']=pd.to_datetime(current.bar_datetime)
    missing=[]
    for row,task in zip(rows,tasks):
        if row['source_status']=='accepted_identical':
            row['source_status']='stage246_identical';continue
        expected=patch.loc[patch.vt_symbol.eq(task['vt_symbol']) & patch.bar_datetime.isin(task_moments(task))].sort_values('bar_datetime')
        if expected.empty:
            missing.append(task);continue
        selected=current.loc[current.vt_symbol.eq(task['vt_symbol']) & current.bar_datetime.isin(task_moments(task))].sort_values('bar_datetime')
        try:
            validate_fragment(expected,task);validate_fragment(selected,task)
            left=expected.reset_index(drop=True);right=selected.reset_index(drop=True)
            same=left.bar_datetime.equals(right.bar_datetime) and all(left[column].astype(float).equals(right[column].astype(float)) for column in VALUES)
            row['source_status']='stage249_identical' if same else 'stage249_values_differ'
            row['stage249_proofs']=sorted(set(expected['_proof']))
            if not same:missing.append(task)
        except ValueError as error:
            row['source_status']='stage249_segment_invalid';row['reason']=str(error);missing.append(task)
    if sha256(cache)!=cache_before:source_errors.append('cache_changed_during_validation')
    return {'status':'failed' if source_errors else 'incomplete' if missing else 'complete','segments':len(tasks),
            'source_proven_segments':sum(r['source_status'] in {'stage246_identical','stage249_identical'} for r in rows),
            'missing_segments':len(missing),'counts':dict(Counter(r['source_status'] for r in rows)),
            'cache':str(cache.resolve()),'cache_sha256':cache_before,'legacy_dir':str(legacy_dir.resolve()),
            'patch_roots':[str(p.resolve()) for p in patch_roots],'source_reports':source_reports,
            'errors':source_errors,'rows':rows,'missing_tasks':missing}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache',type=Path,required=True);parser.add_argument('--tasks',type=Path,required=True)
    parser.add_argument('--legacy-minute-dir',type=Path,required=True);parser.add_argument('--patch-root',type=Path,action='append',required=True)
    parser.add_argument('--output-dir',type=Path,required=True);args=parser.parse_args()
    report=validate_sources(args.cache,read_tasks(args.tasks),args.legacy_minute_dir,args.patch_root)
    report.update(tasks_path=str(args.tasks.resolve()),tasks_sha256=sha256(args.tasks))
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/'cache_source_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    with (args.output_dir/'missing_segment_tasks.csv').open('w',newline='',encoding='utf-8-sig') as handle:
        writer=csv.DictWriter(handle,fieldnames=TASK_COLUMNS);writer.writeheader();writer.writerows(report['missing_tasks'])
    print(json.dumps({k:v for k,v in report.items() if k not in {'rows','missing_tasks'}},ensure_ascii=False))
    return 0 if report['status']=='complete' else 1

if __name__=='__main__':raise SystemExit(main())
