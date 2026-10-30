"""C-only 23 candidates: 19 exact proof reuses and four fresh reserve100k runs."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor,FIRST_COMPLETED,wait
import argparse,json,subprocess
from stage013_contract import STARTS,FRESH_STARTS,REUSE_STARTS,CANARY,LINE,ROOT,sha,load,atomic_json,validate_freeze,checkpoint_key,make_checkpoint,read_checkpoint,validate_baseline_controls
from stage013_reuse import source_independence,make_reuse_checkpoint,read_reuse_checkpoint

BASE=LINE/'outputs/stage013_multistart';RUNNER=Path(__file__).with_name('run_stage013.py')
def key(start,arm='C'):
 if arm!='C' or start not in STARTS:raise ValueError('stage013_C_only_known_start')
 return start+'|C'
def output_path(start,arm='C'):
 if arm!='C' or start not in FRESH_STARTS:raise ValueError('stage013_fixed4_fresh_C_required')
 return LINE/'outputs'/f"stage013_C_{start.replace('-','')}_attempt001"
def checkpoint_path(start):return BASE/'checkpoints'/f'{start}_C.json'
def stamp():return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
def validate_workers(workers):
 if type(workers) is not int or not 1<=workers<=2:raise ValueError('stage013_workers_must_be_1_to_2')
 return workers

def save_registry(reg):
 reg['updated_at']=stamp();reg['counts']={state:sum(j['status']==state for j in reg['jobs'].values()) for state in ['pending','running','validated','failed']};reg['counts']['total']=len(reg['jobs'])
 reg['counts']['fresh_validated']=sum(j['status']=='validated' and j['method']=='fresh_engine' for j in reg['jobs'].values());reg['counts']['proven_reuse_validated']=sum(j['status']=='validated' and j['method']=='proven_nonbinding_reuse' for j in reg['jobs'].values())
 atomic_json(BASE/'registry.json',reg)

def build_registry(freeze,freeze_sha):
 controls=validate_baseline_controls(freeze);sources=source_independence();regpath=BASE/'registry.json'
 if regpath.exists():
  r=load(regpath)
  if r.get('freeze_sha256')!=freeze_sha or r.get('source_head')!=freeze['source_head'] or r.get('baseline_controls')!=controls or r.get('starts')!=list(STARTS) or r.get('arms')!=['C'] or r.get('cutoff')!=freeze['cutoff']:raise ValueError('stage013_registry_identity_changed')
 else:r=dict(schema='stage013_reserve100k_mixed23_registry_v1',freeze_sha256=freeze_sha,source_head=freeze['source_head'],starts=list(STARTS),arms=['C'],cutoff=freeze['cutoff'],created_at=stamp(),jobs={},baseline_controls=controls,baseline_registry_sha256=freeze['baseline_registry_sha256'],engine_initial_capital=150000.,reserve_initial_capital=100000.,total_initial_capital=250000.,candidate_windows=23,planned_new_replays=4,planned_proven_reuse=19,fresh_starts=list(FRESH_STARTS),reuse_starts=list(REUSE_STARTS),financial_replays_started=0)
 if set(r['jobs'])-{key(s) for s in STARTS}:raise ValueError('stage013_unplanned_registry_jobs')
 for start in STARTS:
  k=key(start);cp=checkpoint_path(start);old=controls[k]
  if r['jobs'].get(k,{}).get('status')=='failed':raise ValueError('stage013_failed_attempt_requires_review')
  if start in REUSE_STARTS:
   checked=read_reuse_checkpoint(cp,freeze,freeze_sha,start,old,sources) if cp.exists() else make_reuse_checkpoint(cp,freeze,freeze_sha,start,old,sources)
   r['jobs'][k]={**checked,'status':'validated','checkpoint':str(cp),'baseline_control':old}
  else:
   p=output_path(start)
   if cp.exists():
    checked=read_checkpoint(cp,freeze,freeze_sha,'C',start)
    if Path(checked['path']).resolve()!=p.resolve() or checked.get('reused') is not False:raise ValueError('stage013_fresh_checkpoint_path_changed')
    r['jobs'][k]={**checked,'status':'validated','checkpoint':str(cp),'baseline_control':old}
   elif p.exists():raise ValueError('stage013_existing_attempt_without_verified_checkpoint:'+str(p))
   else:r['jobs'][k]=dict(path=str(p),source_path=str(p),arm='C',start=start,end=freeze['cutoff'],method='fresh_engine',reused=False,status='pending',checkpoint=str(cp),checkpoint_key=checkpoint_key(freeze,freeze_sha,'C',start),baseline_control=old)
 save_registry(r);return r

def approval_valid(path,freeze_sha):
 a=load(path)
 expected={str(checkpoint_path(s).resolve()):sha(checkpoint_path(s)) for s in ['2015-01-01',CANARY]}
 if a.get('accepted') is not True or a.get('canary_start')!=CANARY or a.get('freeze_sha256')!=freeze_sha or a.get('checkpoints_sha256')!=expected:raise ValueError('stage013_independent_canary_and_fullperiod_reuse_acceptance_required')
 return a

def select_pending(reg,mode):
 if any(j.get('status')=='failed' for j in reg['jobs'].values()):raise ValueError('stage013_failed_job_requires_review')
 if mode=='prepare':return []
 if mode=='canary':return [key(CANARY)] if reg['jobs'][key(CANARY)]['status']=='pending' else []
 if mode=='resume':return [key(s) for s in FRESH_STARTS if reg['jobs'][key(s)]['status']=='pending']
 raise ValueError('stage013_unknown_mode')

def launch(start,freeze_path,freeze):
 p=output_path(start);log=BASE/'logs'/f'{start}_C_attempt001.log';log.parent.mkdir(parents=True,exist_ok=True)
 if p.exists() or log.exists():raise ValueError('stage013_immutable_attempt_or_log_exists')
 cmd=[str(ROOT/'.py311/bin/python'),str(RUNNER),'--arm','C','--start',start,'--attempt','001','--data-dir',str(freeze['data_directory']),'--end',freeze['cutoff'],'--freeze',str(freeze_path)]
 with log.open('x') as stream:proc=subprocess.run(cmd,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,check=False)
 return dict(returncode=proc.returncode,path=str(p),log=str(log))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--freeze',type=Path,default=LINE/'stages/stage013_freeze.json');ap.add_argument('--mode',choices=['prepare','canary','resume'],default='prepare');ap.add_argument('--workers',type=int,default=2);ap.add_argument('--canary-approval',type=Path,default=LINE/'stages/stage013_canary_independent_review.json');args=ap.parse_args()
 validate_workers(args.workers);freeze_path=args.freeze.resolve();freeze,freeze_sha=validate_freeze(freeze_path)
 if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=freeze['source_head']:raise ValueError('stage013_actual_HEAD_not_frozen')
 BASE.mkdir(parents=True,exist_ok=True);reg=build_registry(freeze,freeze_sha)
 if args.mode=='prepare':print(json.dumps(dict(mode='prepare',counts=reg['counts'],registry=str(BASE/'registry.json'))));return
 if args.mode=='resume':
  approval_valid(args.canary_approval,freeze_sha)
  if reg['jobs'][key(CANARY)]['status']!='validated':raise ValueError('stage013_canary_incomplete')
 pending=select_pending(reg,args.mode);active={};failed=False
 with ThreadPoolExecutor(max_workers=args.workers) as pool:
  while pending or active:
   while pending and len(active)<args.workers and not failed:
    k=pending.pop(0);job=reg['jobs'][k];job.update(status='running',started_at=stamp());reg['financial_replays_started']+=1;save_registry(reg);active[pool.submit(launch,job['start'],freeze_path,freeze)]=k
    print(json.dumps(dict(event='started',key=k,counts=reg['counts'])),flush=True)
   if not active:break
   completed,_=wait(active,return_when=FIRST_COMPLETED)
   for future in completed:
    k=active.pop(future);job=reg['jobs'][k]
    try:
     result=future.result()
     if result['returncode']!=0:raise RuntimeError('runner_exit_'+str(result['returncode'])+':'+result['log'])
     validate_freeze(freeze_path);checked=make_checkpoint(result['path'],job['checkpoint'],freeze,freeze_sha,'C',job['start']);reg['jobs'][k]={**checked,'status':'validated','checkpoint':job['checkpoint'],'baseline_control':reg['baseline_controls'][k],'log':result['log']}
    except BaseException as exc:failed=True;job.update(status='failed',error=repr(exc),failed_at=stamp())
    save_registry(reg);print(json.dumps(dict(event='completed' if reg['jobs'][k]['status']=='validated' else 'failed',key=k,counts=reg['counts'],error=reg['jobs'][k].get('error'))),flush=True)
 reg['mode_completed']=args.mode;reg['financial_engine_batch_complete']=reg['counts']['validated']==23 and reg['counts']['fresh_validated']==4 and reg['counts']['proven_reuse_validated']==19 and not failed;save_registry(reg)
 if failed:raise RuntimeError('stage013_failed_attempt_preserved_dispatch_stopped')
 print(json.dumps(dict(mode=args.mode,counts=reg['counts'],financial_engine_batch_complete=reg['financial_engine_batch_complete'],registry=str(BASE/'registry.json'))))
if __name__=='__main__':main()
