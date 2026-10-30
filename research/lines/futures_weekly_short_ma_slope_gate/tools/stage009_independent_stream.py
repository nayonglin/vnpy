"""Stage009 registry-validated-only sequential dual-wallet audit; no financial engine."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,time
L=Path(__file__).resolve().parents[1];ROOT=L.parents[2];BASE=L/'outputs/stage009_multistart';OUT=L/'stages/stage009_independent_receipts';AUDITOR=Path(__file__).with_name('stage009_independent_window.py')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8388608),b''):h.update(b)
 return h.hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--freeze',type=Path,default=L/'stages/stage009_freeze.json');ap.add_argument('--phase',choices=['canary','all'],required=True);ap.add_argument('--follow',action='store_true');args=ap.parse_args();f=json.loads(args.freeze.read_text());freeze_sha=sha(args.freeze);OUT.mkdir(parents=True,exist_ok=True)
 keys=[(s,a) for s in f['starts'] for a in ['A','C']]
 if args.phase=='canary':keys=[('2015-01-01',a) for a in ['A','C']]
 seen_receipts=set()
 while True:
  progress=False;done=0;regpath=BASE/'registry.json';registry=json.loads(regpath.read_text()) if regpath.exists() else {}
  if registry and (registry.get('freeze_sha256')!=freeze_sha or registry.get('source_head')!=f['source_head']):raise ValueError('registry_wrong_freeze_or_head')
  for start,arm in keys:
   cp=BASE/'checkpoints'/f'{start}_{arm}.json';out=OUT/f'{start}_{arm}.json'
   if out.exists():
    r=json.loads(out.read_text())
    if r.get('freeze_sha256')!=freeze_sha or r.get('arm')!=arm or r.get('requested_start')!=start or r.get('status')!='PASS_WITH_LIMITATIONS':raise ValueError('independent_receipt_wrong_contract:'+str(out))
    # Reuse requires this exact original checkpoint and every output byte unchanged.
    if cp.exists():
     c=json.loads(cp.read_text())
     if r['source_files_sha256']!=c['files_sha256']:raise ValueError('independent_receipt_vs_checkpoint_snapshot_changed:'+str(cp))
     if str(out) not in seen_receipts:
      for name,digest in c['files_sha256'].items():
       if not Path(name).is_file() or sha(name)!=digest:raise ValueError('reused_independent_receipt_output_drift:'+name)
      seen_receipts.add(str(out))
    done+=1;continue
   if not cp.exists():continue
   job=registry.get('jobs',{}).get(start+'|'+arm,{})
   if job.get('status')!='validated':continue
   if Path(job.get('checkpoint','')).resolve()!=cp.resolve():raise ValueError('registry_checkpoint_path_mismatch')
   c=json.loads(cp.read_text());path=Path(c['path']);
   if Path(job['path']).resolve()!=path.resolve():raise ValueError('registry_attempt_path_mismatch')
   Acp=BASE/'checkpoints'/f'{start}_A.json'
   if arm=='C' and not Acp.exists():continue
   before=sha(cp)
   if c['freeze_sha256']!=freeze_sha or c['arm']!=arm or c['start']!=start or c['end']!=f['cutoff']:raise ValueError('checkpoint_wrong_contract:'+str(cp))
   for name,digest in c['files_sha256'].items():
    if not Path(name).is_file() or sha(name)!=digest:raise ValueError('checkpoint_output_drift:'+name)
   cmd=[sys.executable,str(AUDITOR),'--path',str(path),'--arm',arm,'--start',start,'--end',f['cutoff'],'--freeze',str(args.freeze),'--output',str(out)]
   if arm=='C':cmd+=['--control',json.loads(Acp.read_text())['path']]
   log=OUT/f'{start}_{arm}.log'
   if log.exists():raise ValueError('preserved_failed_review_log_requires_explicit_review:'+str(log))
   with log.open('x') as stream:p=subprocess.run(cmd,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
   if p.returncode:
    print(json.dumps(dict(event='INDEPENDENT_AUDIT_FAILED',start=start,arm=arm,log=str(log),exit=p.returncode)),flush=True);raise RuntimeError('independent_window_failed')
   r=json.loads(out.read_text())
   if before!=sha(cp) or r['source_files_sha256']!=c['files_sha256']:raise ValueError('checkpoint_changed_during_independent_audit')
   seen_receipts.add(str(out));done+=1;progress=True;print(json.dumps(dict(event='INDEPENDENT_AUDIT_PASS',start=start,arm=arm,raw_checks=r['raw_core_checks'],funding_checks=r['funding_checks'],end_equity=r['metrics']['end_equity'],sharpe=r['metrics']['sharpe'],receipt=str(out),receipt_sha256=sha(out))),flush=True)
  if sha(args.freeze)!=freeze_sha:raise ValueError('freeze_changed')
  registry=BASE/'registry.json'
  if registry.exists() and json.loads(registry.read_text()).get('counts',{}).get('failed',0):raise ValueError('financial_registry_failed_no_silent_omission')
  print(json.dumps(dict(event='INDEPENDENT_STREAM_PROGRESS',phase=args.phase,complete=done,planned=len(keys))),flush=True)
  if done==len(keys) or not args.follow:return
  if not progress:time.sleep(15)
if __name__=='__main__':main()
