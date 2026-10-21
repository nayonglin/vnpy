"""Root-controlled first six fits/twelve books after independent precision repair; original stopped sequence preserved."""
from pathlib import Path
from datetime import datetime, timezone
import argparse,hashlib,json,os,subprocess,time,traceback
ROOT=Path('/Users/mac/Desktop/fian')
LINE=ROOT/'research/lines/futures_full_market_long_signal_ai'
HERE=Path(__file__).resolve().parent
OUT=HERE/'orchestration_precision_once'
PYTHON=ROOT/'.py311/bin/python'
PROTOCOL=HERE/'protocol.json'
PROTOCOL_SHA='ff1ecad21420681e8e1e8645be3da51172d35d4e24ef506ee3f88d2ed5e20158'
REVIEW=LINE/'outputs/stage063_eia_event_independent_review/precision_source_preflight.json'
REVIEW_SHA='e1c1af267c37aee1b4b8eaf7ba489a5326247952648d9aca1fbc5bac95bb2c7c'
EXPECTED={
 'stage060_eia_report_import.py':'f40f1b07007d283b950187d05f144ec9954c125433eb130165285e1bac07d45e',
 'test_stage060_eia_report_import.py':'3d404e97baacb700851474cda0960094e067d4985be7417847e3c2e0db263750',
 'stage061_eia_event_fit.py':'7d61a8b5c309ad24881d9d36d0ffffe7f2ae39af4750b7d4130dbb316857503d',
 'test_stage061_eia_event_fit.py':'1ae5502ffaaf3f16b3c59ed563f49327fd65daa09727fc270bb7caf431974ae6',
 'stage062_eia_event_cash_compare.py':'2885b980dac69e503c2f14c51d1f42c4a17e05b0c80cfd0d8af7a01dc5fec32a',
 'test_stage062_eia_event_cash_compare.py':'89a744ea4cce5afe225f0772dd36714c8bca87db024a295c94991856292f82e9',
 'stage065_eia_precision_recovery.py':'3f9334595653cd825e4d7d2841db0492b6c0b77226645811e459877068e9c30e',
 'test_stage065_eia_precision_recovery.py':'170bb5123d3c4484ff03f1c6890914fe39d8e68bbc3bf7dafc28bbbfe8c4fdd6'}
SOURCE_DIR=LINE/'outputs/stage065_eia_precision_recovery'
SOURCE_MANIFEST=SOURCE_DIR/'manifest.json'
SOURCE_TERMINAL=SOURCE_DIR/'actual_terminal.json'
FIT_DIR=LINE/'outputs/stage061_eia_event_fit/experiment'
CASH_DIR=LINE/'outputs/stage062_eia_event_cash_compare/experiment'
PREFLIGHT_DIR=LINE/'outputs/stage061_eia_event_fit/source_preflight'
def now():return datetime.now(timezone.utc).isoformat()
def binding(path):
 path=Path(path).resolve();raw=path.read_bytes()
 return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read(path):
 for attempt in range(3):
  try:return json.loads(Path(path).read_text())
  except (json.JSONDecodeError,FileNotFoundError):
   if attempt==2:raise
   time.sleep(.2)
def write(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def exact(path,sha):
 value=binding(path);assert value['sha256']==sha,('frozen bytes drifted',str(path));return value
def check_bindings():
 protocol=exact(PROTOCOL,PROTOCOL_SHA);review=exact(REVIEW,REVIEW_SHA);r=read(REVIEW)
 assert not r['critical'] and not r['important'] and r['ready_for_root_controlled_sequence'] is True and r['ready_for_once_offline065_after060_completed'] is True
 assert r['protocol']==protocol
 exact(HERE/'precision_input_amendment.json','46946878f76d2b0a134bf274898868e622c4bded4d021a1add62116f8af3e729')
 assert r['precision_amendment']==binding(HERE/'precision_input_amendment.json')
 sources={name:exact(LINE/'tools'/name,sha) for name,sha in EXPECTED.items()}
 for name,source in sources.items():assert r['sources'][name]==source
 assert not FIT_DIR.exists() and not CASH_DIR.exists() and not PREFLIGHT_DIR.exists(),'refuse duplicate source preflight/fit/cash'
 return dict(protocol=protocol,source_preflight=review,sources=sources)
def event(name,**kwargs):
 value=dict(event=name,at=now(),**kwargs)
 with (OUT/'events.jsonl').open('a') as stream:stream.write(json.dumps(value,ensure_ascii=False)+'\n')
 write(OUT/'latest.json',value);print(json.dumps(value,ensure_ascii=False),flush=True)
def child(phase,args):
 event(phase+'_started',command=[str(PYTHON),*map(str,args)])
 t=time.monotonic();start=now()
 with (OUT/(phase+'_stdout.log')).open('x') as stdout,(OUT/(phase+'_stderr.log')).open('x') as stderr:
  result=subprocess.run([str(PYTHON),*map(str,args)],cwd=ROOT,stdout=stdout,stderr=stderr,check=False)
 receipt=dict(phase=phase,started_at=start,finished_at=now(),elapsed_seconds=time.monotonic()-t,exit_code=result.returncode,command=[str(PYTHON),*map(str,args)])
 write(OUT/(phase+'_process_terminal.json'),receipt);event(phase+'_exited',exit_code=result.returncode,elapsed_seconds=receipt['elapsed_seconds'])
 assert result.returncode==0,('child failed; preserve outputs and do not restart',phase,result.returncode)
def wait_source():
 # No second download or normalization. Launch only after the authorized065 completes.
 terminal=read(SOURCE_TERMINAL);manifest=read(SOURCE_MANIFEST)
 assert terminal['status']=='completed' and terminal['normalization_actual_startups']==1
 assert terminal['source_actual_startups']==0 and terminal['original060_source_actual_startups']==1
 assert terminal['new_http_requests']==terminal['model_fits']==terminal['cash_accounts']==terminal['sql_queries']==0
 assert manifest['status']=='completed' and manifest['producer']=='stage065_eia_precision_recovery' and manifest['normalization_stage']=='stage065'
 assert manifest['input_bindings']['precision_input_amendment']=={**binding(HERE/'precision_input_amendment.json'),'declared_role':'frozen_precision_input_correction_contract'}
 parent=manifest['input_bindings']['original_stage060_manifest'];exact(parent['path'],parent['sha256'])
 parent_manifest=read(parent['path']);assert parent_manifest['status']=='completed'
 parent_terminal=parent_manifest['artifacts']['actual_terminal'];exact(parent_terminal['path'],parent_terminal['sha256'])
 original=read(parent_terminal['path']);assert original['status']=='completed' and original['source_actual_startups']==1
 assert original['model_fits']==original['cash_accounts']==original['sql_queries']==0
 event('completed_precision_source_accepted_for_first_input_gate',source_manifest=binding(SOURCE_MANIFEST),original_source_manifest=parent,new_normalization_calls=0,new_downloads=0)
 return binding(SOURCE_MANIFEST)
def main(check_only=False):
 initial=check_bindings()
 if check_only:
  print(json.dumps(dict(status='bindings_and_review_passed_no_actual_action',**initial),ensure_ascii=False));return
 OUT.mkdir(exist_ok=False)
 started=now();status='failed';error=None;source=None;fit=None;cash=None
 write(OUT/'started.json',dict(status='running',started_at=started,process_id=os.getpid(),root_authorized_controlled_sequence=True,bindings=initial,no_commit_push_production=True))
 event('root_precision_sequence_started_after_completed_source',process_id=os.getpid())
 try:
  source=wait_source();check_bindings()
  args=[LINE/'tools/stage061_eia_event_fit.py','--mode','preflight','--protocol',PROTOCOL,'--protocol-sha256',PROTOCOL_SHA,'--source-manifest',SOURCE_MANIFEST,'--source-manifest-sha256',source['sha256'],'--output',PREFLIGHT_DIR]
  child('source_preflight_zero_fit',args)
  preflight=read(PREFLIGHT_DIR/'preflight_terminal.json');assert preflight['status']=='completed' and preflight['exit_code']==0 and preflight['actual_fit_calls_started']==preflight['actual_fit_calls_completed']==0 and preflight['native_source_queries']==0 and preflight['new_cash_accounts']==0
  diagnostic=read(PREFLIGHT_DIR/'preflight.json');assert diagnostic['mother_rows']==399252 and diagnostic['prediction_rows_per_arm']==161014 and diagnostic['ready_for_root_fit_authorization'] is True
  assert all(row['train_rows']>0 and row['report_cohorts']>0 for row in diagnostic['cutoff_diagnostics'])
  for name,sha in EXPECTED.items():exact(LINE/'tools'/name,sha)
  exact(SOURCE_MANIFEST,source['sha256']);exact(PROTOCOL,PROTOCOL_SHA);exact(REVIEW,REVIEW_SHA)
  auth61=OUT/'authorization061.json'
  write(auth61,dict(kind='stage061_fit_once',authorized=True,fit_calls=6,protocol_sha256=PROTOCOL_SHA,source_import_manifest_sha256=source['sha256'],source_sha256=EXPECTED['stage061_eia_event_fit.py'],root_controlled_by=binding(__file__),implementation_review=initial['source_preflight'],zero_fit_preflight=binding(PREFLIGHT_DIR/'preflight_terminal.json'),no_parameter_changes=True))
  args[args.index('preflight')]='actual';args[args.index(PREFLIGHT_DIR)]=FIT_DIR
  args.extend(['--authorization',auth61,'--authorization-sha256',binding(auth61)['sha256']])
  child('six_fit_once',args)
  ft=read(FIT_DIR/'actual_terminal.json');assert ft['status']=='completed' and ft['exit_code']==0 and ft['actual_fit_calls_started']==ft['actual_fit_calls_completed']==6 and ft['native_source_queries']==0 and ft['new_cash_accounts']==0
  fit=binding(FIT_DIR/'manifest.json');fm=read(FIT_DIR/'manifest.json');assert fm['source_import_manifest']==source and fm['source']['sha256']==EXPECTED['stage061_eia_event_fit.py'] and fm['tests']['sha256']==EXPECTED['test_stage061_eia_event_fit.py']
  assert binding(FIT_DIR/'actual_terminal.json')==fm['terminal']
  for name,sha in EXPECTED.items():exact(LINE/'tools'/name,sha)
  exact(SOURCE_MANIFEST,source['sha256']);exact(PROTOCOL,PROTOCOL_SHA);exact(REVIEW,REVIEW_SHA)
  assert not CASH_DIR.exists(),'refuse duplicate cash sequence'
  auth62=OUT/'authorization062.json'
  write(auth62,dict(kind='stage062_cash_once',authorized=True,cash_accounts=12,native_source_queries=1,protocol_sha256=PROTOCOL_SHA,source_import_manifest_sha256=source['sha256'],fit_manifest_sha256=fit['sha256'],source_sha256=EXPECTED['stage062_eia_event_cash_compare.py'],root_controlled_by=binding(__file__),implementation_review=initial['source_preflight'],no_parameter_changes=True))
  child('twelve_cash_once',[LINE/'tools/stage062_eia_event_cash_compare.py','--protocol',PROTOCOL,'--protocol-sha256',PROTOCOL_SHA,'--fit-manifest',FIT_DIR/'manifest.json','--fit-manifest-sha256',fit['sha256'],'--authorization',auth62,'--authorization-sha256',binding(auth62)['sha256'],'--output',CASH_DIR])
  ct=read(CASH_DIR/'actual_terminal.json');assert ct['status']=='completed' and ct['exit_code']==0 and ct['started_research_cash_accounts']==ct['computed_research_cash_accounts']==ct['completed_research_cash_accounts']==12 and ct['native_source_queries']==1 and ct['actual_model_fit_calls']==0
  cash=binding(CASH_DIR/'manifest.json');cm=read(CASH_DIR/'manifest.json');assert cm['fit_manifest']==fit and cm['source']['sha256']==EXPECTED['stage062_eia_event_cash_compare.py'] and binding(CASH_DIR/'actual_terminal.json')==cm['terminal']
  status='completed_actuals_pending_independent_review'
  event(status,source_manifest=source,fit_manifest=fit,cash_manifest=cash,actual_fits=6,actual_cash_accounts=12,new_native_SQL=1,goal_complete=False)
 except BaseException as exc:
  error=f'{type(exc).__name__}: {exc}';event('stopped_without_automatic_restart',error=error);traceback.print_exc();raise
 finally:
  write(OUT/'terminal.json',dict(status=status,exit_code=0 if status=='completed_actuals_pending_independent_review' else 1,started_at=started,finished_at=now(),error=error,source_manifest=source,fit_manifest=fit,cash_manifest=cash,independent_result_review_required=True,goal_complete=False,production_qualified=False,no_commit_push_production=True))
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--check-bindings',action='store_true');args=parser.parse_args();main(args.check_bindings)
