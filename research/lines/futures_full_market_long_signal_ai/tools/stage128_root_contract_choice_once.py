"""Root single execution sequence for frozen128, no retries or old financial runs."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,importlib.util,json,os,subprocess,sys,time
L=Path(__file__).resolve().parents[1];T=L/'tools';R=L/'outputs/stage128_contract_choice_protocol/root_actual_sequence'
P=L/'outputs/stage128_contract_choice_protocol/protocol.json';SHA='bbd24a6e352fe0fbc77f710eeee18918cc1b4670749339e4f3ae67632095efe0'
def b(path):
 path=Path(path).resolve();h=hashlib.sha256();size=0
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk);size+=len(chunk)
 return dict(path=str(path),bytes=size,sha256=h.hexdigest())
def save(p,v):
 with Path(p).open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def module(n):
 spec=importlib.util.spec_from_file_location('root128_'+n,T/(n+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
 if R.exists():raise FileExistsError('root sequence already exists; no automatic retry')
 if b(P)['sha256']!=SHA:raise ValueError('protocol mismatch')
 R.mkdir();clock=time.monotonic();began=datetime.now(timezone.utc).isoformat();status='failed';error=None;completed=[]
 code_names=dict(dataset='stage129_contract_choice_dataset',fit='stage130_contract_choice_fit',cash='stage131_contract_choice_cash')
 modules={k:module(n) for k,n in code_names.items()};sources={k:m.source_bundle() for k,m in modules.items()}
 save(R/'frozen_sources.json',sources);save(R/'actual_started.json',dict(status='started',started_at=began,pid=os.getpid(),python=sys.executable,protocol=b(P),script=b(__file__),source_bundles=sources,automatic_retry=False))
 def phase(stage,inputs):
  if modules[stage].source_bundle()!=sources[stage]:raise ValueError('source changed before '+stage)
  output=L/'outputs'/code_names[stage]/'actual_run1'
  auth=dict(schema='stage128_exact_root_authorization_v1',authorized_by='root',stage=stage,exact_source_authorized=True,protocol_sha256=SHA,source_bundle=sources[stage],output=str(output),input_bindings=inputs)
  ap=R/(stage+'_authorization.json');save(ap,auth)
  with (R/'phase_events.jsonl').open('a') as f:f.write(json.dumps(dict(stage=stage,event='started',at=datetime.now(timezone.utc).isoformat(),output=str(output)))+'\n');f.flush()
  cmd=[sys.executable,str(T/(code_names[stage]+'.py')),'--protocol',str(P),'--protocol-sha256',SHA,'--authorization',str(ap),'--authorization-sha256',b(ap)['sha256'],'--output',str(output)]
  print(json.dumps(dict(phase=stage,event='started',output=str(output))),flush=True)
  with (R/(stage+'.log')).open('x') as log:
   proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
   for line in proc.stdout:log.write(line);log.flush();print(line,end='',flush=True)
   code=proc.wait()
  if code:raise RuntimeError(stage+' exit '+str(code)+'; preserved run, no retry')
  manifest=json.loads((output/'manifest.json').read_text())
  if manifest.get('status')!='completed':raise ValueError(stage+' did not complete')
  completed.append(stage)
  with (R/'phase_events.jsonl').open('a') as f:f.write(json.dumps(dict(stage=stage,event='completed',at=datetime.now(timezone.utc).isoformat(),manifest=b(output/'manifest.json')))+'\n');f.flush()
  return manifest,b(output/'manifest.json')
 try:
  protocol=json.loads(P.read_text());ds,db=phase('dataset',{})
  fi,fb=phase('fit',dict(dataset_manifest=db,actions=ds['actions'],common=ds['common'],mothers=ds['mothers'],dataset_terminal=ds['terminal']))
  ca,cb=phase('cash',dict(market_protocol=protocol['inputs']['market_protocol'],dataset_manifest=db,fit_manifest=fb,actions=ds['actions'],mothers=ds['mothers'],choices_main=fi['choices_main'],held_diagnostic=fi['held_diagnostic']))
  save(R/'completed_manifests.json',dict(dataset=db,fit=fb,cash=cb));status='completed'
 except BaseException as exc:error=type(exc).__name__+': '+str(exc);raise
 finally:
  save(R/'actual_terminal.json',dict(status=status,exit_code=0 if status=='completed' else 1,error=error,completed_phases=completed,started_at=began,finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-clock,automatic_retry=False,independent_review_pending=True,goal_complete=False))
if __name__=='__main__':main()
