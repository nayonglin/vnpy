"""C-only mixed23 pure-audit supervisor:14 induction reuse +9 fresh."""
from pathlib import Path
import argparse,fcntl,hashlib,json,os,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';STAGES=LINE/'stages';BASE=LINE/'outputs/stage012_multistart';OUT=STAGES/'stage012_independent_receipts';AUDITOR=Path(__file__).with_name('stage012_independent_window.py');CANARY='2016-06-01'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def load(p):return json.loads(Path(p).read_text())
def emit(**x):print(json.dumps(x,ensure_ascii=False),flush=True)
def validate(r,cp,start,freeze_sha,auditor_sha):
 if [r.get(k) for k in ['status','requested_start','arm','freeze_sha256','auditor_source_sha256']]!=['PASS_WITH_LIMITATIONS',start,'C',freeze_sha,auditor_sha]:raise AssertionError('mixed_independent_receipt_identity')
 snap=cp['files_sha256'] if cp['method']=='fresh_engine' else cp['source_files_sha256']
 if r['method']!=cp['method'] or r['path']!=cp['path'] or r['source_files_sha256']!=snap or any(r.get(k)!=0 for k in ['P0','P1','P2','failures']):raise AssertionError('mixed_receipt_output_or_findings')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--freeze',type=Path,default=STAGES/'stage012_freeze.json');ap.add_argument('--workers',type=int,choices=[1,2],default=2);ap.add_argument('--follow',action='store_true');ap.add_argument('--canary-only',action='store_true');a=ap.parse_args();f=load(a.freeze);fsha=sha(a.freeze);asha=sha(AUDITOR);starts=['2015-01-01',CANARY] if a.canary_only else f['starts'];OUT.mkdir(parents=True,exist_ok=True);lock=(STAGES/'stage012_independent_stream.lock').open('a+')
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise RuntimeError('independent_supervisor_or_children_already_running')
 running={};seen=set();last=None;emit(event='STAGE012_INDEPENDENT_STARTED',pid=os.getpid(),planned=len(starts),workers=a.workers,auditor_sha256=asha,freeze_sha256=fsha)
 while True:
  if sha(a.freeze)!=fsha or sha(AUDITOR)!=asha:raise AssertionError('review_source_or_freeze_changed')
  if not (BASE/'registry.json').exists():
   if a.follow:time.sleep(2);continue
   emit(event='WAITING_FOR_REGISTRY');return
  reg=load(BASE/'registry.json')
  if reg['freeze_sha256']!=fsha or reg['source_head']!=f['source_head']:raise AssertionError('registry_not_frozen_identity')
  for start,j in list(running.items()):
   code=j['process'].poll()
   if code is None:continue
   j['log'].close();del running[start]
   if code:raise RuntimeError('INDEPENDENT_AUDIT_FAILED_log_preserved:'+str(j['logpath']))
   cp=load(j['checkpoint']);r=load(j['pending']);validate(r,cp,start,fsha,asha)
   if sha(j['checkpoint'])!=j['cp_sha'] or j['output'].exists():raise AssertionError('checkpoint_changed_or_refuse_receipt_overwrite')
   os.rename(j['pending'],j['output']);seen.add(start);emit(event='STAGE012_INDEPENDENT_WINDOW_PASS',start=start,method=r['method'],receipt=str(j['output']),sha256=sha(j['output']),real_PnL=r['real_net_pnl'])
  for start in starts:
   output=OUT/f'{start}_C.json';cp_path=BASE/'checkpoints'/f'{start}_C.json'
   if output.exists() and start not in seen:validate(load(output),load(cp_path),start,fsha,asha);seen.add(start)
   if start in seen or start in running or len(running)>=a.workers:continue
   job=reg['jobs'][start+'|C']
   if job['status']!='validated':continue
   cp=load(cp_path)
   if cp['start']!=start or cp['arm']!='C' or cp['freeze_sha256']!=fsha or cp['source_head']!=f['source_head'] or cp['path']!=job['path']:raise AssertionError('checkpoint_registry_scope')
   n=1
   while (OUT/f'{start}_C_attempt{n:03d}.log').exists():n+=1
   logpath=OUT/f'{start}_C_attempt{n:03d}.log';pending=OUT/f'{start}_C_attempt{n:03d}.pending';stream=logpath.open('x');cmd=[sys.executable,str(AUDITOR),'--path',cp['path'],'--start',start,'--freeze',str(a.freeze),'--checkpoint',str(cp_path),'--output',str(pending)];process=subprocess.Popen(cmd,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,pass_fds=(lock.fileno(),));running[start]=dict(process=process,log=stream,logpath=logpath,pending=pending,output=output,checkpoint=cp_path,cp_sha=sha(cp_path));emit(event='STAGE012_AUDIT_STARTED',start=start,method=cp['method'],pid=process.pid)
  progress=(len(seen),len(running))
  if progress!=last:emit(event='STAGE012_AUDIT_PROGRESS',complete=progress[0],running=progress[1],planned=len(starts));last=progress
  if len(seen)==len(starts):
   if a.canary_only:
    out=STAGES/'stage012_canary_independent_review.json'
    if out.exists():raise ValueError('immutable_canary_gate_exists')
    out.write_text(json.dumps(dict(schema='stage012_independent_canary_and_reuse_v1',accepted=True,status='PASS_WITH_LIMITATIONS',P0=0,P1=0,P2=0,canary_start=CANARY,freeze_sha256=fsha,source_head=f['source_head'],checkpoints_sha256={str(BASE/'checkpoints'/f'{s}_C.json'):sha(BASE/'checkpoints'/f'{s}_C.json') for s in starts},receipts_sha256={str(OUT/f'{s}_C.json'):sha(OUT/f'{s}_C.json') for s in starts},scope='2015full proved-nonbinding reuse and earliest-binding2016June genuine engine independently accepted; remaining8 fixed fresh runs may proceed',financial_replays=0,market_downloads=0,production_accesses=0,promotion_decision='NO_PROMOTION'),ensure_ascii=False,indent=2)+'\n');emit(event='STAGE012_CANARY_GATE_ACCEPTED',path=str(out),sha256=sha(out))
   emit(event='STAGE012_ALL_INDEPENDENT_COMPLETE',complete=len(seen));return
  if not running and not a.follow:emit(event='STAGE012_DRAINED',complete=len(seen));return
  time.sleep(2)
if __name__=='__main__':main()
