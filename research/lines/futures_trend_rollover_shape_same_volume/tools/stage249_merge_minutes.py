"""仅将完整、源证据已验收的Stage249分钟补丁原子合入研究cache。

必须显式给出期望cache SHA；原文件先备份，保留全部旧时间戳和原有列。
仅替换明确补丁键的OHLCV/OI、来源，新增键按自然日补bar_date。
不调用策略引擎，不改基线、不连接行情、CTP或账户。
"""
from __future__ import annotations
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
from typing import Any
from stage249_prepare_replay import VALUES,sha256,verify_patch


def merge_frames(base:Any,patch:Any) -> tuple[Any,dict[str,Any]]:
    import pandas as pd
    keys=['vt_symbol','bar_datetime'];base=base.copy();patch=patch.copy();columns=list(base.columns)
    for frame in [base,patch]:
        frame['bar_datetime']=pd.to_datetime(frame.bar_datetime,errors='raise')
        if frame.duplicated(keys).any():raise ValueError('duplicate_minute_key')
    if patch.empty:raise ValueError('empty_patch')
    old_index=pd.MultiIndex.from_frame(base[keys]);new_index=pd.MultiIndex.from_frame(patch[keys])
    overlap=old_index.intersection(new_index);added=new_index.difference(old_index)
    old_values=base.set_index(keys);new_values=patch.set_index(keys)
    changed={column:int((old_values.loc[overlap,column].astype(float)!=new_values.loc[overlap,column].astype(float)).sum()) for column in VALUES}
    for column in VALUES+(['minute_source'] if 'minute_source' in columns else []):
        old_values.loc[overlap,column]=new_values.loc[overlap,column]
    fresh=new_values.loc[added].reset_index()
    if 'bar_date' in columns:fresh['bar_date']=fresh.bar_datetime.dt.strftime('%Y-%m-%d')
    if 'tq_symbol' in columns:fresh['tq_symbol']=fresh.vt_symbol.map(lambda value:'.'.join(str(value).split('.')[::-1]))
    for column in columns:
        if column not in fresh:fresh[column]=float('nan')
    merged=pd.concat([old_values.reset_index()[columns],fresh[columns]],ignore_index=True)
    merged=merged.sort_values(keys).reset_index(drop=True)
    final_index=pd.MultiIndex.from_frame(merged[keys]);removed=len(old_index.difference(final_index))
    if removed or merged.duplicated(keys).any():raise ValueError('merge_timestamp_invariant_failed')
    return merged,{'base_rows':len(base),'patch_rows':len(patch),'merged_rows':len(merged),
                  'replaced_rows':len(overlap),'new_timestamps':len(added),'removed_timestamps':removed,'changed_values':changed}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache',type=Path,required=True)
    parser.add_argument('--expected-cache-sha256',required=True)
    parser.add_argument('--patch-manifest',type=Path,action='append',required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();cache=args.cache.resolve();before=sha256(cache)
    if before!=args.expected_cache_sha256:raise ValueError('cache_sha256_changed_before_merge')
    import pandas as pd
    sources=[];frames=[];manifests=[]
    for manifest_path in args.patch_manifest:
        manifest=json.loads(manifest_path.read_text())
        if manifest.get('status')!='complete' or manifest.get('errors'):raise ValueError('patch_manifest_not_complete')
        manifests.append({'path':str(manifest_path.resolve()),'sha256':sha256(manifest_path)})
        for record in manifest['patches']:
            parquet=Path(record['parquet']);proof_path=Path(record['proof'])
            if sha256(proof_path)!=record['proof_sha256']:raise ValueError('patch_proof_changed_after_audit')
            proof=verify_patch(parquet,proof_path)
            if proof['sha256']!=record['sha256']:raise ValueError('patch_changed_after_audit')
            if sha256(Path(record['raw_path']))!=record['raw_sha256']:raise ValueError('raw_changed_after_audit')
            frames.append(pd.read_parquet(parquet));sources.append(record)
    patch=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    merged,stats=merge_frames(pd.read_csv(cache,encoding='utf-8-sig'),patch)
    out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    backup=out/f'cache_before_{before}.csv'
    if not backup.exists():shutil.copy2(cache,backup)
    if sha256(backup)!=before:raise ValueError('backup_sha256_mismatch')
    temporary=cache.with_suffix(f'.stage249.{os.getpid()}.tmp.csv')
    merged.to_csv(temporary,index=False,encoding='utf-8-sig')
    if sha256(cache)!=before:
        temporary.unlink();raise ValueError('cache_changed_during_merge')
    os.replace(temporary,cache)
    report={'status':'completed','completed_at':datetime.now().astimezone().isoformat(),'cache':str(cache),
        'before_sha256':before,'after_sha256':sha256(cache),'backup':str(backup),'statistics':stats,
        'source_manifests':manifests,'source_patches':sources,
        'policy':'Replace only explicit timestamp keys; retain all old timestamps and cache columns; bar_date remains natural date.'}
    (out/'merge_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({key:value for key,value in report.items() if key!='source_patches'},ensure_ascii=False))
    return 0

if __name__=='__main__':raise SystemExit(main())
