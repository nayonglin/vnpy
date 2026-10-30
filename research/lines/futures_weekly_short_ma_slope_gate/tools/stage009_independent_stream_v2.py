"""Two-worker pure-audit supervisor; locked original auditor; no finance.

Global flock is inherited by children: a dead supervisor cannot cause a second
supervisor to duplicate a still-live audit. Child output uses an attempt-specific
pending receipt; only a successfully validated complete receipt is published by
an atomic rename. Prior logs/receipts are never modified.
"""
from pathlib import Path
import argparse,fcntl,json,os,subprocess,sys,time
from stage009_independent_stream import sha,L,ROOT,BASE,OUT,AUDITOR
LOCKED='63e9ba6821b3b4c377ed7b67ca035b4daa4fc9ddd8bb824141047f280e237ac9'

def emit(**kw):print(json.dumps(kw,ensure_ascii=False),flush=True)
def validate_receipt(r,start,arm,cp,freeze_sha):
 if (r.get('status'),r.get('requested_start'),r.get('arm'),r.get('freeze_sha256'),r.get('auditor_source_sha256'))!=('PASS_WITH_LIMITATIONS',start,arm,freeze_sha,LOCKED):raise ValueError('receipt_identity')
 if any(r.get(k)!=0 for k in ['P0','P1','P2','failures']):raise ValueError('receipt_findings')
 if r['path']!=cp['path'] or r['source_files_sha256']!=cp['files_sha256']:raise ValueError('receipt_source_snapshot')
def verify_snapshot(cp):
 for p,h in cp['files_sha256'].items():
  if not Path(p).is_file() or sha(p)!=h:raise ValueError('checkpoint_output_drift:'+p)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--freeze',type=Path,default=L/'stages/stage009_freeze.json');ap.add_argument('--workers',type=int,choices=[1,2],default=2);ap.add_argument('--follow',action='store_true');ap.add_argument('--predecessor-pid',type=int,default=12876);ap.add_argument('--stop-dispatch-file',type=Path,default=L/'stages/stage009_independent_stream_v2.stop');args=ap.parse_args()
 try:os.kill(args.predecessor_pid,0)
 except ProcessLookupError:pass
 else:raise RuntimeError('predecessor_still_exists_no_concurrent_supervisor')
 if sha(AUDITOR)!=LOCKED:raise ValueError('locked_auditor_drift')
 OUT.mkdir(parents=True,exist_ok=True);lock=(L/'stages/stage009_independent_stream_v2.lock').open('a+')
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise RuntimeError('another_supervisor_or_orphan_audit_holds_global_lock')
 f=json.loads(args.freeze.read_text());freeze_sha=sha(args.freeze);keys=[(s,a) for s in f['starts'] for a in ['A','C']];running={};seen=set();last_progress=None
 emit(event='V2_STARTED',pid=os.getpid(),workers=args.workers,predecessor_absent=args.predecessor_pid,auditor_sha256=LOCKED,stop_dispatch_file=str(args.stop_dispatch_file))
 while True:
  if sha(args.freeze)!=freeze_sha or sha(AUDITOR)!=LOCKED:raise ValueError('frozen_source_drift')
  reg=json.loads((BASE/'registry.json').read_text())
  if reg['freeze_sha256']!=freeze_sha or reg['source_head']!=f['source_head'] or reg.get('counts',{}).get('failed',0):raise ValueError('registry_identity_or_financial_failure')
  for key,job in list(running.items()):
   code=job['process'].poll()
   if code is None:continue
   job['log'].close();del running[key]
   if code:raise RuntimeError('AUDIT_FAILED_preserved_log:'+str(job['log_path']))
   r=json.loads(job['pending'].read_text());cp=json.loads(job['cp_path'].read_text())
   if sha(job['cp_path'])!=job['cp_sha']:raise ValueError('checkpoint_changed_during_review')
   validate_receipt(r,*key,cp,freeze_sha)
   if job['out'].exists():raise ValueError('refuse_receipt_overwrite')
   os.rename(job['pending'],job['out']);seen.add(key)
   emit(event='INDEPENDENT_AUDIT_PASS_V2',start=key[0],arm=key[1],receipt=str(job['out']),receipt_sha256=sha(job['out']),raw_checks=r['raw_core_checks'],funding_checks=r['funding_checks'])
  for start,arm in keys:
   key=(start,arm);out=OUT/f'{start}_{arm}.json';cp_path=BASE/'checkpoints'/f'{start}_{arm}.json'
   if out.exists() and key not in seen:
    cp=json.loads(cp_path.read_text());validate_receipt(json.loads(out.read_text()),start,arm,cp,freeze_sha);verify_snapshot(cp);seen.add(key)
   if key in seen or key in running or len(running)>=args.workers or args.stop_dispatch_file.exists():continue
   job=reg['jobs'][start+'|'+arm]
   if job['status']!='validated':continue
   cp=json.loads(cp_path.read_text())
   if cp['freeze_sha256']!=freeze_sha or cp['arm']!=arm or cp['start']!=start or cp['end']!=f['cutoff'] or job['path']!=cp['path'] or Path(job['checkpoint']).resolve()!=cp_path.resolve():raise ValueError('checkpoint_registry_scope')
   verify_snapshot(cp)
   # A source must exist for the frozen C raw-auditor interface; C does not
   # require the A audit to have completed, only its immutable checkpoint.
   acp=BASE/'checkpoints'/f'{start}_A.json'
   if arm=='C' and not acp.exists():continue
   prefix=f'{start}_{arm}.stream_v2_attempt';pending=None
   for old in sorted(OUT.glob(prefix+'*.pending')):
    try:r=json.loads(old.read_text());validate_receipt(r,start,arm,cp,freeze_sha)
    except (ValueError,KeyError,TypeError):continue
    os.rename(old,out);seen.add(key);emit(event='RECOVERED_COMPLETED_PENDING_RECEIPT',receipt=str(out),receipt_sha256=sha(out));break
   if key in seen:continue
   number=1
   while (OUT/f'{prefix}{number:03d}.log').exists() or (OUT/f'{prefix}{number:03d}.pending').exists():number+=1
   logpath=OUT/f'{prefix}{number:03d}.log';pending=OUT/f'{prefix}{number:03d}.pending';log=logpath.open('x')
   cmd=[sys.executable,str(AUDITOR),'--path',cp['path'],'--arm',arm,'--start',start,'--end',f['cutoff'],'--freeze',str(args.freeze),'--output',str(pending)]
   if arm=='C':cmd+=['--control',json.loads(acp.read_text())['path']]
   process=subprocess.Popen(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,pass_fds=(lock.fileno(),))
   running[key]=dict(process=process,log=log,log_path=logpath,pending=pending,out=out,cp_path=cp_path,cp_sha=sha(cp_path))
   emit(event='AUDIT_STARTED_V2',start=start,arm=arm,pid=process.pid,log=str(logpath),pending_receipt=str(pending))
  progress=(len(seen),len(running),args.stop_dispatch_file.exists())
  if progress!=last_progress:emit(event='V2_PROGRESS',complete=progress[0],running=progress[1],planned=len(keys),dispatch_stopped=progress[2]);last_progress=progress
  if len(seen)==len(keys):emit(event='V2_COMPLETE',complete=len(seen),planned=len(keys));return
  if not running and (args.stop_dispatch_file.exists() or not args.follow):emit(event='V2_DRAINED',complete=len(seen));return
  time.sleep(3)
if __name__=='__main__':main()
