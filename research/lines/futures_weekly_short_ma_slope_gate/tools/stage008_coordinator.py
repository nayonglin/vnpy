"""Bounded independent-process orchestration with verified per-run checkpoints.

prepare validates the four frozen reused runs. canary runs June2015 A/C only.
resume requires a frozen independent canary acceptance and schedules the rest.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor,FIRST_COMPLETED,wait
import argparse,json,subprocess,sys
from stage008_contract import STARTS,LINE,ROOT,sha,load,atomic_json,validate_freeze,checkpoint_key,make_checkpoint,read_checkpoint
BASE=LINE/'outputs/stage008_multistart';RUNNER=Path(__file__).with_name('run_stage008.py')
REUSE_KEYS={'2015-01-01|A','2015-01-01|C','2020-01-01|A','2020-01-01|C'}
CANARY='2015-06-01'
def key(start,arm):return start+'|'+arm
def output_path(start,arm):return LINE/'outputs'/f"stage008_{arm}_{start.replace('-','')}_attempt001"
def checkpoint_path(start,arm):return BASE/'checkpoints'/f"{start}_{arm}.json"
def stamp():return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
def validate_reuse(freeze):
 reuse=freeze.get('reuse_runs',{})
 if set(reuse)!=REUSE_KEYS:raise ValueError('stage008_exact_four_reuse_runs_required')
 deliveries=freeze.get('reused_delivery_sha256',{})
 if not deliveries:raise ValueError('stage008_reused_delivery_hashes_required')
 for p,h in deliveries.items():
  if sha(p)!=h:raise ValueError('stage008_reused_delivery_changed:'+p)
 return reuse

def build_registry(freeze,freeze_sha):
 reuse=validate_reuse(freeze);regpath=BASE/'registry.json'
 if regpath.exists():
  r=load(regpath)
  if r.get('freeze_sha256')!=freeze_sha or r.get('source_head')!=freeze['source_head']:raise ValueError('stage008_registry_freeze_mismatch')
 else:r=dict(schema='stage008_independent23_registry_v1',freeze_sha256=freeze_sha,source_head=freeze['source_head'],cutoff=freeze['cutoff'],starts=list(STARTS),arms=['A','C'],created_at=stamp(),jobs={},financial_replays_started=0)
 expected={key(s,a) for s in STARTS for a in ['A','C']}
 if set(r['jobs'])-expected:raise ValueError('stage008_unplanned_registry_jobs')
 for start in STARTS:
  for arm in ['A','C']:
   k=key(start,arm);cp=checkpoint_path(start,arm);isreuse=k in reuse;p=Path(reuse[k]) if isreuse else output_path(start,arm)
   prior=r['jobs'].get(k,{})
   if cp.exists():
    checked=read_checkpoint(cp,freeze,freeze_sha,arm,start)
    if Path(checked['path']).resolve()!=p.resolve() or checked['reused'] is not isreuse:raise ValueError('stage008_checkpoint_source_path_mismatch')
    r['jobs'][k]={**checked,'status':'validated','checkpoint':str(cp)}
   elif isreuse:
    checked=make_checkpoint(p,cp,freeze,freeze_sha,arm,start,reused=True);r['jobs'][k]={**checked,'status':'validated','checkpoint':str(cp)}
   elif p.exists():raise ValueError('stage008_existing_attempt_without_verified_checkpoint:'+str(p))
   else:r['jobs'][k]=dict(path=str(p),arm=arm,start=start,end=freeze['cutoff'],reused=False,status='pending',checkpoint=str(cp),checkpoint_key=checkpoint_key(freeze,freeze_sha,arm,start))
 save_registry(r);return r

def save_registry(reg):
 reg['updated_at']=stamp();reg['counts']={state:sum(j['status']==state for j in reg['jobs'].values()) for state in ['pending','running','validated','failed']};reg['counts']['total']=len(reg['jobs']);atomic_json(BASE/'registry.json',reg)
def approval_valid(path,freeze_sha):
 a=load(path)
 if a.get('accepted') is not True or a.get('canary_start')!=CANARY or a.get('freeze_sha256')!=freeze_sha:raise ValueError('stage008_independent_canary_acceptance_required')
 expected={str(checkpoint_path(CANARY,arm).resolve()):sha(checkpoint_path(CANARY,arm)) for arm in ['A','C']}
 if a.get('checkpoints_sha256')!=expected:raise ValueError('stage008_canary_approval_checkpoint_binding_required')
 return a

def launch(start,arm,freeze_path,freeze):
 p=output_path(start,arm)
 if p.exists():raise ValueError('stage008_attempt_already_exists:'+str(p))
 log=BASE/'logs'/f"{start}_{arm}_attempt001.log";log.parent.mkdir(parents=True,exist_ok=True)
 if log.exists():raise ValueError('stage008_log_already_exists:'+str(log))
 cmd=[str(ROOT/'.py311/bin/python'),str(RUNNER),'--arm',arm,'--start',start,'--attempt','001','--data-dir',str(freeze['data_directory']),'--end',freeze['cutoff'],'--freeze',str(freeze_path)]
 with log.open('x') as stream:
  proc=subprocess.run(cmd,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,check=False)
 return dict(returncode=proc.returncode,log=str(log),path=str(p))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--freeze',type=Path,default=LINE/'stages/stage008_freeze.json');ap.add_argument('--mode',choices=['prepare','canary','resume'],default='prepare');ap.add_argument('--workers',type=int,default=3);ap.add_argument('--canary-approval',type=Path,default=LINE/'stages/stage008_canary_independent_review.json');args=ap.parse_args()
 if not 1<=args.workers<=3:raise ValueError('stage008_workers_must_be_1_to_3')
 freeze_path=args.freeze.resolve();freeze,freeze_sha=validate_freeze(freeze_path)
 if not Path(freeze.get('data_directory','')).is_dir():raise ValueError('stage008_data_directory_required')
 BASE.mkdir(parents=True,exist_ok=True);reg=build_registry(freeze,freeze_sha)
 if args.mode=='prepare':print(json.dumps(dict(mode=args.mode,counts=reg['counts'],planned_new_replays=42,canary_start=CANARY,registry=str(BASE/'registry.json'))));return
 if args.mode=='resume':
  approval_valid(args.canary_approval,freeze_sha)
  for arm in ['A','C']:
   j=reg['jobs'][key(CANARY,arm)]
   if j['status']!='validated':raise ValueError('stage008_canary_not_complete')
   read_checkpoint(j['checkpoint'],freeze,freeze_sha,arm,CANARY)
 if args.mode=='canary':pending=[key(CANARY,a) for a in ['A','C'] if reg['jobs'][key(CANARY,a)]['status']=='pending']
 else:pending=[key(s,a) for s in STARTS for a in ['A','C'] if reg['jobs'][key(s,a)]['status']=='pending']
 if any(j['status']=='failed' for j in reg['jobs'].values()):raise ValueError('stage008_failed_job_requires_review')
 active={};failed=False
 with ThreadPoolExecutor(max_workers=args.workers) as pool:
  while pending or active:
   while pending and len(active)<args.workers and not failed:
    k=pending.pop(0);job=reg['jobs'][k];job['status']='running';job['started_at']=stamp();reg['financial_replays_started']+=1;save_registry(reg);active[pool.submit(launch,job['start'],job['arm'],freeze_path,freeze)]=k
    print(json.dumps(dict(event='started',key=k,counts=reg['counts'])),flush=True)
   if not active:break
   completed,_=wait(active,return_when=FIRST_COMPLETED)
   for future in completed:
    k=active.pop(future);job=reg['jobs'][k]
    try:
     result=future.result()
     if result['returncode']!=0:raise RuntimeError('runner_exit_'+str(result['returncode'])+':'+result['log'])
     validate_freeze(freeze_path)
     checked=make_checkpoint(result['path'],job['checkpoint'],freeze,freeze_sha,job['arm'],job['start']);reg['jobs'][k]={**checked,'status':'validated','checkpoint':job['checkpoint'],'log':result['log']}
    except BaseException as exc:
     failed=True;job.update(status='failed',error=repr(exc),failed_at=stamp())
    save_registry(reg);print(json.dumps(dict(event='completed' if reg['jobs'][k]['status']=='validated' else 'failed',key=k,counts=reg['counts'],error=reg['jobs'][k].get('error'))),flush=True)
 reg['mode_completed']=args.mode;reg['financial_engine_batch_complete']=reg['counts']['validated']==46 and not failed;save_registry(reg)
 if failed:raise RuntimeError('stage008_batch_failed_preserved_attempt_no_further_dispatch')
 print(json.dumps(dict(mode=args.mode,counts=reg['counts'],financial_engine_batch_complete=reg['financial_engine_batch_complete'],registry=str(BASE/'registry.json'))))
if __name__=='__main__':main()
