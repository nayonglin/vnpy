"""59 independent fresh C/R150 accounts, single canary and immutable checkpoints."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor,FIRST_COMPLETED,wait
import argparse,json,shutil,subprocess
from stage014_contract import STARTS,LINE,ROOT,sha,load,atomic_json,validate_freeze,checkpoint_key,make_checkpoint,read_checkpoint

BASE=LINE/'outputs/stage014_multistart';RUNNER=Path(__file__).with_name('run_stage014.py');CANARY='2015-01-01'
def key(start):return start+'|C'
def output_path(start):return LINE/'outputs'/f"stage014_C_{start.replace('-','')}_attempt001"
def checkpoint_path(start):return BASE/'checkpoints'/f'{start}_C.json'
def stamp():return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
def validate_workers(workers):
 if type(workers) is not int or not 1<=workers<=2:raise ValueError('stage014_workers_must_be_1_to_2')
 return workers
def disk_gate(path,freeze,jobs_remaining=1):
 p=Path(path)
 while not p.exists():p=p.parent
 free=int(shutil.disk_usage(p).free);required=int(freeze['min_free_disk_bytes'])+int(freeze['estimated_bytes_per_run'])*max(0,int(jobs_remaining))
 if free<required:raise ValueError(f'stage014_insufficient_disk_space:free={free}:required={required}')
 return dict(accepted=True,free_bytes=free,required_bytes=required,jobs_budgeted=int(jobs_remaining))
def save_registry(r):
 r['updated_at']=stamp();r['counts']={state:sum(j['status']==state for j in r['jobs'].values()) for state in ['pending','running','validated','failed']};r['counts']['total']=len(r['jobs']);atomic_json(BASE/'registry.json',r)
def build_registry(freeze,freeze_sha):
 path=BASE/'registry.json'
 if path.exists():
  r=load(path)
  if r.get('freeze_sha256')!=freeze_sha or r.get('source_head')!=freeze['source_head'] or r.get('starts')!=list(STARTS) or r.get('cutoff')!=freeze['cutoff'] or r.get('arms')!=['C']:raise ValueError('stage014_registry_identity_changed')
 else:r=dict(schema='stage014_five_starts_R150_registry_v1',freeze_sha256=freeze_sha,source_head=freeze['source_head'],starts=list(STARTS),arms=['C'],cutoff=freeze['cutoff'],engine_initial_capital=150000.,reserve_initial_capital=150000.,total_initial_capital=300000.,planned_financial_replays=59,planned_reused_runs=0,created_at=stamp(),jobs={},financial_replays_started=0)
 if set(r['jobs'])-{key(s) for s in STARTS}:raise ValueError('stage014_unplanned_registry_jobs')
 for start in STARTS:
  k=key(start);p=output_path(start);cp=checkpoint_path(start)
  if r['jobs'].get(k,{}).get('status')=='failed':raise ValueError('stage014_failed_job_requires_review_preserve_attempt')
  if cp.exists():
   checked=read_checkpoint(cp,freeze,freeze_sha,'C',start)
   if Path(checked['path']).resolve()!=p.resolve() or checked.get('reused') is not False:raise ValueError('stage014_fresh_checkpoint_wrong_path')
   r['jobs'][k]={**checked,'status':'validated','checkpoint':str(cp)}
  elif p.exists():raise ValueError('stage014_existing_attempt_without_checkpoint:'+str(p))
  else:r['jobs'][k]=dict(path=str(p),source_path=str(p),start=start,arm='C',end=freeze['cutoff'],method='fresh_engine',reused=False,status='pending',checkpoint=str(cp),checkpoint_key=checkpoint_key(freeze,freeze_sha,'C',start))
 save_registry(r);return r
def approval_valid(path,freeze_sha):
 a=load(path);expected={str(checkpoint_path(CANARY).resolve()):sha(checkpoint_path(CANARY))}
 if a.get('accepted') is not True or a.get('canary_start')!=CANARY or a.get('freeze_sha256')!=freeze_sha or a.get('checkpoints_sha256')!=expected or a.get('prefix_through_2026_10_29_unchanged') is not True:raise ValueError('stage014_independent_canary_prefix_acceptance_required')
 return a
def select_pending(r,mode):
 if any(j.get('status')=='failed' for j in r['jobs'].values()):raise ValueError('stage014_failed_job_requires_review')
 if mode=='prepare':return []
 if mode=='canary':return [key(CANARY)] if r['jobs'][key(CANARY)]['status']=='pending' else []
 if mode=='resume':return [key(s) for s in STARTS if r['jobs'][key(s)]['status']=='pending']
 raise ValueError('stage014_unknown_mode')
def launch(start,freeze_path,freeze):
 disk_gate(BASE,freeze,1);p=output_path(start);log=BASE/'logs'/f'{start}_C_attempt001.log';log.parent.mkdir(parents=True,exist_ok=True)
 if p.exists() or log.exists():raise ValueError('stage014_immutable_attempt_or_log_exists')
 cmd=[str(ROOT/'.py311/bin/python'),str(RUNNER),'--arm','C','--start',start,'--attempt','001','--data-dir',str(freeze['data_directory']),'--end',freeze['cutoff'],'--freeze',str(freeze_path)]
 with log.open('x') as stream:proc=subprocess.run(cmd,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,check=False)
 return dict(returncode=proc.returncode,path=str(p),log=str(log))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--freeze',type=Path,default=LINE/'stages/stage014_freeze.json');ap.add_argument('--mode',choices=['prepare','canary','resume'],default='prepare');ap.add_argument('--workers',type=int,default=2);ap.add_argument('--canary-approval',type=Path,default=LINE/'stages/stage014_canary_independent_review.json');args=ap.parse_args()
 validate_workers(args.workers);freeze_path=args.freeze.resolve();freeze,freeze_sha=validate_freeze(freeze_path)
 if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=freeze['source_head']:raise ValueError('stage014_actual_HEAD_not_frozen')
 disk_gate(BASE,freeze,59);BASE.mkdir(parents=True,exist_ok=True);reg=build_registry(freeze,freeze_sha)
 if args.mode=='prepare':print(json.dumps(dict(mode='prepare',counts=reg['counts'],registry=str(BASE/'registry.json'))));return
 if args.mode=='resume':
  approval_valid(args.canary_approval,freeze_sha)
  if reg['jobs'][key(CANARY)]['status']!='validated':raise ValueError('stage014_canary_not_complete')
 pending=select_pending(reg,args.mode);active={};failed=False
 with ThreadPoolExecutor(max_workers=args.workers) as pool:
  while pending or active:
   while pending and len(active)<args.workers and not failed:
    disk_gate(BASE,freeze,len(pending));k=pending.pop(0);job=reg['jobs'][k];job.update(status='running',started_at=stamp());reg['financial_replays_started']+=1;save_registry(reg);active[pool.submit(launch,job['start'],freeze_path,freeze)]=k
    print(json.dumps(dict(event='started',key=k,counts=reg['counts'])),flush=True)
   if not active:break
   completed,_=wait(active,return_when=FIRST_COMPLETED)
   for future in completed:
    k=active.pop(future);job=reg['jobs'][k]
    try:
     result=future.result()
     if result['returncode']!=0:raise RuntimeError('runner_exit_'+str(result['returncode'])+':'+result['log'])
     validate_freeze(freeze_path);checked=make_checkpoint(result['path'],job['checkpoint'],freeze,freeze_sha,'C',job['start']);reg['jobs'][k]={**checked,'status':'validated','checkpoint':job['checkpoint'],'log':result['log']}
    except BaseException as exc:failed=True;job.update(status='failed',error=repr(exc),failed_at=stamp())
    save_registry(reg);print(json.dumps(dict(event='completed' if reg['jobs'][k]['status']=='validated' else 'failed',key=k,counts=reg['counts'],error=reg['jobs'][k].get('error'))),flush=True)
 reg['mode_completed']=args.mode;reg['financial_engine_batch_complete']=reg['counts']['validated']==59 and not failed;save_registry(reg)
 if failed:raise RuntimeError('stage014_failed_attempt_preserved_dispatch_stopped')
 print(json.dumps(dict(mode=args.mode,counts=reg['counts'],financial_engine_batch_complete=reg['financial_engine_batch_complete'],registry=str(BASE/'registry.json'))))
if __name__=='__main__':main()
