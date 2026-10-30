"""Bounded pure-audit supervisor and exact canary gate; no financial engine."""
from pathlib import Path
import argparse,fcntl,hashlib,json,os,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';STAGES=LINE/'stages';BASE=LINE/'outputs/stage011_multistart';OUT=STAGES/'stage011_independent_receipts';AUDITOR=Path(__file__).with_name('stage011_independent_window.py')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def load(p):return json.loads(Path(p).read_text())
def emit(**data):print(json.dumps(data,ensure_ascii=False),flush=True)
def validate(receipt,cp,start,arm,freeze_sha,auditor_sha):
 if [receipt.get(k) for k in ['status','requested_start','arm','freeze_sha256','auditor_source_sha256']]!=['PASS_WITH_LIMITATIONS',start,arm,freeze_sha,auditor_sha]:raise AssertionError('independent_receipt_identity')
 if any(receipt.get(k)!=0 for k in ['P0','P1','P2','failures']) or receipt['source_files_sha256']!=cp['files_sha256'] or receipt['path']!=cp['path']:raise AssertionError('independent_receipt_findings_or_output_binding')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--freeze',type=Path,default=STAGES/'stage011_freeze.json');ap.add_argument('--workers',type=int,choices=[1,2],default=2);ap.add_argument('--follow',action='store_true');ap.add_argument('--canary-only',action='store_true');args=ap.parse_args()
 frozen=load(args.freeze);freeze_sha=sha(args.freeze);auditor_sha=sha(AUDITOR);OUT.mkdir(parents=True,exist_ok=True)
 lock=(STAGES/'stage011_independent_stream.lock').open('a+')
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise RuntimeError('independent_supervisor_or_children_already_running')
 starts=['2015-01-01'] if args.canary_only else frozen['starts'];keys=[(s,a) for s in starts for a in ['A','C']];running={};seen=set();last=None
 emit(event='INDEPENDENT_STREAM_STARTED',pid=os.getpid(),workers=args.workers,planned=len(keys),freeze_sha256=freeze_sha,auditor_sha256=auditor_sha)
 while True:
  if sha(args.freeze)!=freeze_sha or sha(AUDITOR)!=auditor_sha:raise AssertionError('review_source_or_freeze_changed')
  if not (BASE/'registry.json').exists():
   if args.follow:time.sleep(2);continue
   emit(event='INDEPENDENT_STREAM_WAITING_FOR_REGISTRY');return
  reg=load(BASE/'registry.json')
  if reg['freeze_sha256']!=freeze_sha or reg['source_head']!=frozen['source_head']:raise AssertionError('registry_not_frozen_identity')
  for key,job in list(running.items()):
   code=job['process'].poll()
   if code is None:continue
   job['log'].close();del running[key]
   if code:raise RuntimeError('AUDIT_FAILED_log_preserved:'+str(job['logpath']))
   cp=load(job['checkpoint']);r=load(job['pending']);validate(r,cp,*key,freeze_sha,auditor_sha)
   if sha(job['checkpoint'])!=job['checkpoint_sha']:raise AssertionError('checkpoint_changed_during_audit')
   if job['output'].exists():raise AssertionError('refuse_independent_receipt_overwrite')
   os.rename(job['pending'],job['output']);seen.add(key);emit(event='INDEPENDENT_WINDOW_PASS',start=key[0],arm=key[1],receipt=str(job['output']),receipt_sha256=sha(job['output']),real_net_pnl=r['real_net_pnl'],checks=r['raw_core_checks']+r['funding_checks']+r['stage011_checks'])
  for start,arm in keys:
   key=(start,arm);out=OUT/f'{start}_{arm}.json';cp_path=BASE/'checkpoints'/f'{start}_{arm}.json'
   if out.exists() and key not in seen:
    validate(load(out),load(cp_path),start,arm,freeze_sha,auditor_sha);seen.add(key)
   if key in seen or key in running or len(running)>=args.workers:continue
   job=reg['jobs'][start+'|'+arm]
   if job['status']!='validated':continue
   cp=load(cp_path)
   if cp['freeze_sha256']!=freeze_sha or cp['source_head']!=frozen['source_head'] or cp['arm']!=arm or cp['start']!=start or cp['end']!=frozen['cutoff'] or job['path']!=cp['path']:raise AssertionError('checkpoint_registry_identity')
   acp=BASE/'checkpoints'/f'{start}_A.json'
   if arm=='C' and not acp.exists():continue
   number=1
   while (OUT/f'{start}_{arm}_attempt{number:03d}.log').exists():number+=1
   prefix=OUT/f'{start}_{arm}_attempt{number:03d}';logpath=prefix.with_suffix('.log');pending=prefix.with_suffix('.pending');log=logpath.open('x')
   cmd=[sys.executable,str(AUDITOR),'--path',cp['path'],'--arm',arm,'--start',start,'--end',frozen['cutoff'],'--freeze',str(args.freeze),'--output',str(pending)]
   if arm=='C':cmd+=['--control',load(acp)['path']]
   process=subprocess.Popen(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,pass_fds=(lock.fileno(),));running[key]=dict(process=process,log=log,logpath=logpath,pending=pending,output=out,checkpoint=cp_path,checkpoint_sha=sha(cp_path));emit(event='INDEPENDENT_AUDIT_STARTED',start=start,arm=arm,pid=process.pid,log=str(logpath))
  progress=(len(seen),len(running))
  if progress!=last:emit(event='INDEPENDENT_STREAM_PROGRESS',complete=progress[0],running=progress[1],planned=len(keys));last=progress
  if len(seen)==len(keys):
   if args.canary_only:
    gate=STAGES/'stage011_canary_independent_review.json'
    if gate.exists():raise ValueError('immutable_canary_gate_exists')
    gate.write_text(json.dumps(dict(schema='stage011_independent_canary_review_v1',accepted=True,status='PASS_WITH_LIMITATIONS',P0=0,P1=0,P2=0,canary_start='2015-01-01',freeze_sha256=freeze_sha,source_head=frozen['source_head'],checkpoints_sha256={str(BASE/'checkpoints'/f'2015-01-01_{a}.json'):sha(BASE/'checkpoints'/f'2015-01-01_{a}.json') for a in ['A','C']},receipts_sha256={str(OUT/f'2015-01-01_{a}.json'):sha(OUT/f'2015-01-01_{a}.json') for a in ['A','C']},auditor_sha256=auditor_sha,financial_replays=0,market_downloads=0,production_accesses=0,promotion_decision='NO_PROMOTION',scope='Financial/data/parameter/cash-causality acceptance only; economic negatives do not cancel the authorized fixed23 grid and never imply promotion'),ensure_ascii=False,indent=2)+'\n');emit(event='CANARY_INDEPENDENT_ACCEPTED',path=str(gate),sha256=sha(gate))
   emit(event='INDEPENDENT_STREAM_COMPLETE',complete=len(seen),planned=len(keys));return
  if not running and not args.follow:emit(event='INDEPENDENT_STREAM_DRAINED',complete=len(seen));return
  time.sleep(2)
if __name__=='__main__':main()
