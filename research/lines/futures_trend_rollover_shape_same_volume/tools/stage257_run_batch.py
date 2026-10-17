"""Manifest-bound Stage257 batches; complete and audit full windows before rolling."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def write_json(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    temporary.replace(path)


def valid_checkpoint(directory,marker,run_id,manifest_sha):
    hashes=marker.get('artifact_sha256',{})
    return bool(marker.get('account_id')==run_id and marker.get('manifest_sha256')==manifest_sha
        and marker.get('returncode')==0 and {'metrics.json','stage257_account_provenance.json'}<=hashes.keys()
        and all((directory/name).is_file() and sha(directory/name)==value for name,value in hashes.items()))


def valid_audit(audit,manifest_sha):
    return audit.get('experiment_manifest_sha256')==manifest_sha and audit.get('status') in {'PASS','PASS_DIAGNOSTIC','PASS_DIAGNOSTIC_GAPS','PASS_STRICT'}


def phase_ids(manifest,phase):
    windows={w['window_id']:w for w in manifest['windows']}
    ids=[key for key,a in manifest['accounts'].items() if phase=='all' or
         ((windows[a['window_id']]['group'] in {'historical_full','ai_primary'})==(phase=='full'))]
    order={'ai_fair':0,'legacy_ai':1,'common_pre_ai':2,'random_monthly':3,'turnover_matched':4}
    return sorted(ids,key=lambda key:(order[manifest['accounts'][key]['kind']],key))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment',type=Path,required=True)
    parser.add_argument('--phase',choices=['full','rolling','all'],default='all')
    parser.add_argument('--accounts',nargs='+')
    parser.add_argument('--workers',type=int,choices=[1,2,3,4,5],default=3)
    parser.add_argument('--review-every',type=int,default=12)
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    out=args.experiment.resolve();manifest_path=out/'experiment_manifest.json'
    frozen=manifest_path.read_bytes();manifest=json.loads(frozen);digest=sha(manifest_path)
    ids=args.accounts or phase_ids(manifest,args.phase)
    if len(ids)!=len(set(ids)) or set(ids)-manifest['accounts'].keys():raise ValueError('unknown_or_duplicate_accounts')
    if args.review_every<1:raise ValueError('invalid_review_batch_size')
    runner=Path(__file__).with_name('stage257_run_account.py')
    reviewer=Path(__file__).with_name('stage257_review_accounts.py')
    runtime=json.loads(Path(manifest['runtime_overlay_path']).read_text())
    environment=dict(os.environ,PYTHONPATH=runtime['PYTHONPATH'],PYTHONDONTWRITEBYTECODE='1',
                     MPLCONFIGDIR='/private/tmp/stage257_mpl',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    batch_id=datetime.now().strftime('%Y%m%d_%H%M%S');lock=threading.Lock()
    logpath=out/'logs'/f'batch_{batch_id}.jsonl';progress_path=out/'logs'/f'batch_{batch_id}_progress.json'
    def emit(record):
        record=dict(record,timestamp=datetime.now().astimezone().isoformat())
        with lock:
            with logpath.open('a') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
            print(json.dumps(record,ensure_ascii=False),flush=True)
    def command(run_id):
        info=manifest['accounts'][run_id]
        return [sys.executable,str(runner),'--experiment',str(out),'--account-id',run_id,
                '--output',info['output'],'--baseline-root',manifest['baseline_root']]
    def checkpoint(run_id):
        directory=Path(manifest['accounts'][run_id]['output']);marker=directory/'batch_completion.json'
        return marker.is_file() and valid_checkpoint(directory,json.loads(marker.read_text()),run_id,digest)
    def accepted(run_id):
        audit=out/'independent_reviews/accounts'/f'{run_id}.json'
        if not checkpoint(run_id) or not audit.is_file():return False
        review=json.loads(audit.read_text())
        return valid_audit(review,digest) and all((Path(manifest['accounts'][run_id]['output'])/name).is_file()
            and sha(Path(manifest['accounts'][run_id]['output'])/name)==value for name,value in review.get('source_hashes',{}).items())
    def full_gate():
        missing=[key for key in phase_ids(manifest,'full') if not accepted(key)]
        if missing:raise RuntimeError('full_windows_not_complete_and_audited:'+str(len(missing))+':'+','.join(missing[:3]))
    def one(run_id):
        directory=Path(manifest['accounts'][run_id]['output']);marker=directory/'batch_completion.json'
        if checkpoint(run_id):return {'account_id':run_id,'status':'already_completed'}
        if directory.exists() and any(directory.iterdir()):raise RuntimeError('partial_or_changed_output_preserved:'+run_id)
        if manifest_path.read_bytes()!=frozen:raise RuntimeError('manifest_changed')
        begin=time.monotonic();emit({'account_id':run_id,'status':'started'})
        with (out/'logs'/f'{run_id}.log').open('w') as log:
            result=subprocess.run(command(run_id),cwd=manifest['root'],env=environment,stdout=log,stderr=subprocess.STDOUT)
        directory.mkdir(exist_ok=True)
        names=['metrics.json','stage257_account_provenance.json','actual_strategy_settings.json','effective_parameters.json','daily.csv','trades.csv','positions.csv','run_provenance.json']
        ok=result.returncode==0 and all((directory/name).is_file() for name in names)
        record={'account_id':run_id,'returncode':result.returncode if not result.returncode==0 or ok else 90,
                'elapsed_seconds':round(time.monotonic()-begin,3),'manifest_sha256':digest,
                'status':'completed' if ok else 'failed_preserved','command':command(run_id),
                'artifact_sha256':{name:sha(directory/name) for name in names if (directory/name).is_file()}}
        write_json(marker,record)
        return record
    if args.dry_run:
        print(json.dumps({'manifest_sha256':digest,'requested':len(ids),'full':len(set(ids)&set(phase_ids(manifest,'full'))),
                          'rolling':len(set(ids)&set(phase_ids(manifest,'rolling'))),'first_commands':[command(k) for k in ids[:3]]},ensure_ascii=False))
        return
    registration=out/'independent_reviews/registration.json'
    if not registration.is_file() or not valid_audit(json.loads(registration.read_text()),digest):raise RuntimeError('registration_not_passed')
    results=[];full=set(phase_ids(manifest,'full'))
    phases=[[k for k in ids if k in full],[k for k in ids if k not in full]]
    for phase_number,phase in enumerate(phases):
        if not phase:continue
        if phase_number:full_gate()
        for offset in range(0,len(phase),args.review_every):
            subset=phase[offset:offset+args.review_every];batch=[]
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures={executor.submit(one,k):k for k in subset}
                for future in as_completed(futures):
                    try:record=future.result()
                    except Exception as exc:record={'account_id':futures[future],'status':'orchestration_error','error':repr(exc)}
                    batch.append(record);results.append(record);emit(record)
                    write_json(progress_path,{'manifest_sha256':digest,'requested':len(ids),'returned':len(results),'results':results})
            if not all(x['status'] in {'completed','already_completed'} for x in batch):raise RuntimeError('batch_failed_preserved')
            review_command=[sys.executable,str(reviewer),'--experiment',str(out),'--account',*subset]
            with (out/'logs'/f'audit_{batch_id}_{phase_number}_{offset}.log').open('w') as log:
                review=subprocess.run(review_command,cwd=manifest['root'],env=environment,stdout=log,stderr=subprocess.STDOUT)
            if review.returncode or not all(accepted(k) for k in subset):raise RuntimeError('independent_batch_audit_failed')
            emit({'status':'batch_independently_audited','accounts':subset})
    summary={'manifest_sha256':digest,'requested':len(ids),'workers':args.workers,'results':results,'all_success':True,'all_independently_audited':True}
    write_json(out/'logs'/f'batch_{batch_id}_summary.json',summary)
    emit({'status':'all_requested_complete_and_audited','count':len(ids)})


if __name__=='__main__':main()
