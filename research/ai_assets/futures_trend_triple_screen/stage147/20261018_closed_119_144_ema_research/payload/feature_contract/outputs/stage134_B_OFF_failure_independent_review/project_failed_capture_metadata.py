from pathlib import Path
from datetime import datetime,timezone,timedelta
from collections import Counter
import ast,gzip,hashlib,io,json,pickle,sys
B=Path('/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen');OUT=B/'outputs/stage134_B_OFF_failure_independent_review';OUT.mkdir(exist_ok=True)
T=B/'outputs/stage133_B_OFF_actual_failure/actual_tool_terminal.json'
bindings={}
def read(p,h=None):
 p=Path(p);assert p.is_absolute()and p.is_file()and not any(x.is_symlink()for x in (p,*p.parents));raw=p.read_bytes();assert raw==p.read_bytes()
 actual=hashlib.sha256(raw).hexdigest()
 if h:assert actual==h,(str(p),actual,h)
 bindings[str(p)]=dict(sha256=actual,bytes=len(raw));return raw
def js(p,h=None):return json.loads(read(p,h))
terminal=js(T,'8d287ff4d22277c63ed89034fcf553560de10cf9ffb10c8e7b4a6834e9859172')
assert terminal['actual_terminal_observed']is True and terminal['exit_code']==1 and terminal['tool_session_id']==47648 and terminal['tool_terminal_chunk_id']=='4e198d'
raws={n:read(row['path'],row['sha256'])for n,row in terminal['objects'].items()}
context=json.loads(raws['run_context.json']);preflight=json.loads(raws['preflight_used.json']);failure=json.loads(raws['run_failure.json'])
assert terminal['run_id']==context['run_id']==failure['run_id']=='81ffc8f704ce4c5eb701e97e0397b12a'
assert context['arm']==failure['arm']==terminal['arm']=='B_OFF'and context['preflight_sha256']==terminal['objects']['preflight_used.json']['sha256']
assert context['started_at']==terminal['started_at']and preflight['source_head']==terminal['source_commit']
assert failure==terminal['failure']and failure['failure_capture_sha256']==terminal['objects']['failure_capture.pkl.gz']['sha256']
owner_path=B/'outputs/stage087_off_data_scope/B_OFF/81ffc8f704ce4c5eb701e97e0397b12a/owner.json';owner=js(owner_path,'ce61dcf3cbe0696cfbc12f1ebcf0f12436ee0dfb84662623e91fce36ec957efb')
assert owner['run_id']==context['run_id']and owner['run_context_sha256']==terminal['objects']['run_context.json']['sha256']and owner['preflight_sha256']==terminal['objects']['preflight_used.json']['sha256']
assert all(not(Path(terminal['owner_root'])/name).exists()for name in terminal['no_complete_outputs'])
# Narrow local source identity checks; no market input hashes or loaders.
for name in ['stage065_run_pairwise_off.py','stage065_account_checkpoint.py','stage022_run_c0_qualified_wait.py','stage061_accepted_wait_delta.py']:
 p=B/'tools'/name;row=context['source_bindings'][str(p)];raw=read(p,row['sha256']);assert len(raw)==row['bytes']
unpickler_path=B/'tools/stage033_independent_checkpoint_account_review.py';code=read(unpickler_path,'940ab1180392c7ca3a6cceef15b3bb33f3d37d6510c48f86b9e7c109b7205cbf')
node=next(x for x in ast.parse(code).body if isinstance(x,ast.ClassDef)and x.name=='OwnedAccountUnpickler');ns={'pickle':pickle};exec(compile(ast.Module(body=[node],type_ignores=[]),str(unpickler_path),'exec'),ns)
sys.dont_write_bytecode=True;sys.path.insert(0,str(B/'tools'))
import stage022_run_c0_qualified_wait as runtime
runtime.OUTPUT=OUT/'runtime_route'
runtime.configure_runtime(OUT/'empty_shared')
import numpy as np
import pandas as pd
assert all(Path(m.__file__).resolve().is_relative_to(runtime.FROZEN_SITE)for m in [np,pd])
payload=ns['OwnedAccountUnpickler'](io.BytesIO(gzip.decompress(raws['failure_capture.pkl.gz']))).load()
assert payload['schema']=='stage065_partial_failure_capture_v1'and payload['partial']is True and payload['run_context']==context
partial=payload['capture'];assert isinstance(partial,dict)
wait=partial['wait_audit'];resolver=partial['resolver_audit'];inputs=partial['input_fingerprints']
assert isinstance(wait,list)and isinstance(resolver,list)and isinstance(inputs,dict)
snapshot=dict(schema='stage134_audit_only_projection_of_stage065_failed_capture_v1',audit_only=True,new_data_qualification=False,financial_qualified=False,
 provenance=dict(capture_field='payload.capture',wait_audit_field='payload.capture.wait_audit',resolver_audit_field='payload.capture.resolver_audit',input_fingerprints_field='payload.capture.input_fingerprints',one_owned_unpickle=True),
 owner=dict(arm='B_OFF',run_id=context['run_id'],attempt=context['attempt'],output_directory=context['output_directory']),
 upstream_bindings=dict(actual_terminal=dict(path=str(T),**bindings[str(T)]),**{n:terminal['objects'][n]for n in ['run_context.json','preflight_used.json','run_failure.json','failure_capture.pkl.gz']},original_065_schema='stage065_partial_failure_capture_v1',owner=dict(path=str(owner_path),**bindings[str(owner_path)]),source_bindings=context['source_bindings']),
 wait_audit=wait,resolver_audit=resolver,input_fingerprints=inputs)
def safe(v):
 if isinstance(v,dict):return {str(k):safe(x)for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [safe(x)for x in v]
 if isinstance(v,(str,int,float,bool))or v is None:return v
 if isinstance(v,(datetime,Path)):return str(v)
 if hasattr(v,'item'):return safe(v.item())
 raise TypeError(type(v).__name__)
snapshot=safe(snapshot)
(OUT/'audit_only_snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
gates=Counter(x.get('event')for x in wait);statuses=Counter(x.get('status')for x in resolver)
diagnostic=dict(schema='stage134_failed_capture_metadata_diagnostic_v1',checked_at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),terminal_binding=bindings[str(T)],bound_objects=bindings,run_id=context['run_id'],arm=context['arm'],context_schema=context['schema'],failure_status=failure['status'],error=failure['error'],failure_phase=partial.get('failure_phase'),payload_top_keys=list(payload),partial_top_keys=list(partial),capture_table_names=list(partial.get('capture',{})),capture_failure_records=partial.get('capture',{}).get('failures',[]),missing_complete_outputs=terminal['no_complete_outputs'],combined_present='combined'in partial,frames_present='frames'in partial,wait_count=len(wait),gate_event_counts=dict(gates),resolver_count=len(resolver),resolver_status_counts=dict(statuses),wait_first_event=wait[0]if wait else None,wait_last_event=wait[-1]if wait else None,resolver_first_record=resolver[0]if resolver else None,resolver_last_record=resolver[-1]if resolver else None,input_fingerprints_count=len(inputs),one_owned_unpickle=True,financial_tables_not_inspected=True,partial_PnL_output_or_computation=False,engine_strategy_constructed=False,market_model_or_network_called=False,forbidden_modules_loaded=[n for n in ['tqsdk','sklearn','joblib','vnpy','vnpy_portfoliostrategy','stage065_run_pairwise_off']if n in sys.modules])
assert not diagnostic['forbidden_modules_loaded']
(OUT/'capture_metadata_diagnostic.json').write_text(json.dumps(safe(diagnostic),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print(json.dumps({k:v for k,v in diagnostic.items()if k not in ['bound_objects','wait_first_event','resolver_first_record','capture_failure_records']},ensure_ascii=False,indent=2,default=str))
print(json.dumps({'failure_record_fields':[list(x)for x in diagnostic['capture_failure_records']]},ensure_ascii=False))

