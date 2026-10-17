from pathlib import Path
import subprocess, json, hashlib, datetime
ROOT=Path('/Users/mac/Desktop/fian')
LINE=ROOT/'research/lines/futures_trend_triple_screen'
DRIVER=LINE/'tools/stage044_qualified_wait_driver.py'
RESOLVER=LINE/'tools/stage052_generic_daily_source_resolver.py'
BINDINGS=LINE/'outputs/stage044_root_bindings/providers_v2.json'
OUT=LINE/'outputs/stage056_root_batch_chain'
OUT.mkdir(exist_ok=False)
FIXED={DRIVER:'1a27fa40efab481330bed6d3ac8714ddbd414a785d84200578001a8fcc7c5445',RESOLVER:'5b2772c700f0ddabb5536df4be1bfe1f70e07d8fea43400abfa74c66ae727b78',BINDINGS:'24078404996b534bfc4486c04cc0fa54b4eaea475e8661ef6e22c3d0cad98a04'}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for p,s in FIXED.items():
 if sha(p)!=s: raise SystemExit('frozen source drift: '+str(p))
(OUT/'controller_source.py').write_bytes(Path(__file__).read_bytes())
identity={'schema':'stage056_same_live_engine_batch_chain_v1','started_at':datetime.datetime.now().astimezone().isoformat(),'engine_pid':21822,'financial_runs_started':0,'first_batch':21,'last_batch':40,'max_new_provider_connections_per_batch':4,'frozen_sources':{str(p):s for p,s in FIXED.items()},'original_financial_deadline_unchanged':True,'events':[]}
for n in range(21,41):
 batch=f'batch{n:03d}'
 for p,s in FIXED.items():
  if sha(p)!=s: raise SystemExit('frozen source drift: '+str(p))
 manifest=LINE/f'outputs/stage044_qualified_wait_driver/{batch}/manifest.json'
 prepare=[str(ROOT/'.py311/bin/python'),str(DRIVER),'--prepare','--batch-id',batch,'--engine-pid','21822','--provider-bindings',str(BINDINGS),'--resolver',str(RESOLVER),'--resolver-sha256',FIXED[RESOLVER],'--max-providers','4','--budget-seconds','3600']
 p=subprocess.run(prepare,cwd=ROOT,capture_output=True,text=True)
 (OUT/f'{batch}_prepare.stdout').write_text(p.stdout)
 (OUT/f'{batch}_prepare.stderr').write_text(p.stderr)
 event={'batch':batch,'prepare_exit_code':p.returncode,'prepare_terminal_observed':True}
 identity['events'].append(event)
 if p.returncode:
  identity['status']='stopped_prepare_failure';(OUT/'journal.json').write_text(json.dumps(identity,ensure_ascii=False,indent=2)+'\n');print(json.dumps(event),flush=True);raise SystemExit(p.returncode)
 event['manifest_sha256']=sha(manifest)
 (OUT/'journal.json').write_text(json.dumps(identity,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'batch':batch,'status':'prepared_same_engine'}),flush=True)
 p=subprocess.run([str(ROOT/'.py311/bin/python'),str(DRIVER),'--run','--manifest',str(manifest),'--source-sha256',FIXED[DRIVER]],cwd=ROOT,capture_output=True,text=True)
 (OUT/f'{batch}_run.stdout').write_text(p.stdout)
 (OUT/f'{batch}_run.stderr').write_text(p.stderr)
 event.update(run_exit_code=p.returncode,run_terminal_observed=True)
 journal=manifest.parent/'journal.json'
 data=json.loads(journal.read_text()) if journal.exists() else {}
 event.update(driver_status=data.get('status'),journal_sha256=sha(journal) if journal.exists() else None,provider_connections=data.get('provider_connections'))
 identity['status']='continuing_same_engine' if p.returncode==0 and data.get('status')=='paused_provider_batch_limit' else 'stopped_driver_terminal'
 (OUT/'journal.json').write_text(json.dumps(identity,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(event),flush=True)
 if identity['status']!='continuing_same_engine':raise SystemExit(p.returncode)
identity['status']='bounded_chain_limit_reached'
(OUT/'journal.json').write_text(json.dumps(identity,ensure_ascii=False,indent=2)+'\n')
