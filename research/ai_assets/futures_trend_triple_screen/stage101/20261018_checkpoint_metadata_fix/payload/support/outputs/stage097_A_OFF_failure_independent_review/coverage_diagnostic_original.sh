.py311/bin/python - <<'PY'
from pathlib import Path
from datetime import datetime
import ast,gzip,hashlib,io,json,os,pickle,sys
line=Path('/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen');root=line.parents[2];tools=line/'tools';out=line/'outputs/stage097_A_OFF_failure_independent_review';out.mkdir(parents=True,exist_ok=False)
a=line/'outputs/stage065_pairwise_off_account/A_OFF'
pins={'run_failure.json':'6a21416440f3f3441599435ebf55c1ae688006d865d5683a537fea5af2c3d082','failure_capture.pkl.gz':'443216dc4e7b3b2550f97aeafee33c9f4376a94aa1513ad3f8e19f5c71cfd96f','run_context.json':'46126a8af641d76e47978bd10d5aba9b7a5f8072af24ef7f0f781b0f7f1db7f7','preflight_used.json':'4612f307b30e6917d227d624cdbf35c9ff74238a73cd1d0bd7a8267a53d92bf5'}
def regular(p):
 assert p.is_file()and not any(x.is_symlink()for x in (p,*p.parents));return p.read_bytes()
raws={n:regular(a/n)for n in pins}
assert all(hashlib.sha256(raws[n]).hexdigest()==h for n,h in pins.items())
context=json.loads(raws['run_context.json']);preflight=json.loads(raws['preflight_used.json']);failure=json.loads(raws['run_failure.json'])
assert context['run_id']==failure['run_id']=='982636a096884e7e9610b1ad49eb1ae1'
assert context['preflight_sha256']==pins['preflight_used.json']
unpickler_path=tools/'stage033_independent_checkpoint_account_review.py';unpickler_raw=regular(unpickler_path)
assert hashlib.sha256(unpickler_raw).hexdigest()=='940ab1180392c7ca3a6cceef15b3bb33f3d37d6510c48f86b9e7c109b7205cbf'
node=next(n for n in ast.parse(unpickler_raw).body if isinstance(n,ast.ClassDef)and n.name=='OwnedAccountUnpickler')
namespace={'pickle':pickle};exec(compile(ast.Module(body=[node],type_ignores=[]),str(unpickler_path),'exec'),namespace)
frozen=Path('/Users/mac/Documents/Codex/fian-research-20261014/.py311/lib/python3.11/site-packages');assert frozen.is_dir()
assert not any(n in sys.modules for n in ['numpy','pandas','sklearn','joblib'])
os.environ.update(TZ='Asia/Shanghai',QT_QPA_PLATFORM='offscreen',OPENBLAS_NUM_THREADS='1');sys.path[:0]=[str(tools),str(frozen)]
import numpy as np
import pandas as pd
assert all(Path(m.__file__).resolve().is_relative_to(frozen)for m in [np,pd])
# Exactly one unpickle, with the frozen local allowlist, after SHA/ownership checks.
payload=namespace['OwnedAccountUnpickler'](io.BytesIO(gzip.decompress(raws['failure_capture.pkl.gz']))).load()
assert payload['schema']=='stage065_partial_failure_capture_v1'and payload['partial']is True
assert payload['run_context']==context
partial=payload['capture'];capture=partial['capture'];assert partial['ordered']is None
forbidden={'engine','strategy','history','history_data','minute_cache','stage827_minute_by_symbol'}
def forbidden_paths(value,path):
 rows=[]
 if isinstance(value,dict):
  for k,v in value.items():
   if k in forbidden:rows.append(dict(path=path+[k],type=type(v).__name__,value=v if isinstance(v,(str,int,float,bool))or v is None else '<non-scalar>'))
   rows+=forbidden_paths(v,path+[k])
 elif isinstance(value,(list,tuple)):
  for i,v in enumerate(value):rows+=forbidden_paths(v,path+[i])
 return rows

def coverage(value):
 if isinstance(value,dict):return dict(type='dict',count=len(value),keys=list(value)if len(value)<30 else '<large metadata mapping>')
 if isinstance(value,(list,tuple)):
  fields=sorted(set().union(*(set(x)for x in value if isinstance(x,dict))))
  return dict(type=type(value).__name__,rows=len(value),fields=fields)
 if isinstance(value,pd.DataFrame):return dict(type='DataFrame',rows=len(value),columns=list(map(str,value.columns)))
 return dict(type=type(value).__name__,value=value if value is None or isinstance(value,(str,bool))else '<scalar not reported>')
tables={k:coverage(v)for k,v in capture.items()}
trade_ids=[str(x['trade_id'])for x in capture.get('trades',[])];usage_ids=[str(x.get('trade_id',''))for x in capture.get('usage',[])]
identity_fields=['trade_id','vt_symbol','direction','offset','price','volume','execution_datetime','trading_date','signal_datetime','signal_order_id','intraday_episode_id']
trade_fields=set().union(*(set(x)for x in capture.get('trades',[])))
usage_fields=set().union(*(set(x)for x in capture.get('usage',[])))
dates=[str(x['date'])[:10]for x in capture.get('equity',[])];wanted=list(preflight['reference_calendar'])
cpraw=regular(tools/'stage065_account_checkpoint.py');assert hashlib.sha256(cpraw).hexdigest()=='7e5a265a23b8fce871c895292e0738831604eefb9a341f7a83bd0320a68cf15b'
import stage065_account_checkpoint as cp
try:cp._account_only(preflight)
except ValueError as err:guard_error=str(err)
else:raise AssertionError('actual metadata no longer reproduces the guard failure')
core_names=['stage065_run_pairwise_off.py','stage065_account_checkpoint.py','stage031_run_ordered_checkpoint.py','stage022_run_c0_qualified_wait.py','stage065_pairwise_off_policy.py']
source_checks={}
for name in core_names:
 p=tools/name;row=context['source_bindings'][str(p)];snap=context['source_snapshots'][str(p)];snapshot=a/snap['snapshot'];current_raw=regular(p);saved_raw=regular(snapshot)
 assert hashlib.sha256(current_raw).hexdigest()==hashlib.sha256(saved_raw).hexdigest()==row['sha256']and len(current_raw)==len(saved_raw)==row['bytes']
 source_checks[str(p)]=dict(**row,snapshot=snap['snapshot'],current_and_snapshot_verified=True)
required=next(n.value for n in ast.walk(ast.parse(cpraw))if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='required'for t in n.targets))
required_keys=set(ast.literal_eval(required))
expected_frames=['trades','positions','entry_risk','entry_candidates','trade_events','intraday_events','c2_events','stop_retry_events','rollover_shape_same_volume','rollover_delay','long_signal_atr_shock','long_signal_range_atr','pending_orders']
report=dict(schema='stage097_failure_capture_coverage_diagnostic_v1',one_owned_unpickle=True,unpickler_source_sha256=hashlib.sha256(unpickler_raw).hexdigest(),frozen_runtime=str(frozen),
 owner=dict(arm=context['arm'],attempt=context['attempt'],run_id=context['run_id'],started_at=context['started_at'],output_directory=context['output_directory'],source_head=preflight['source_head']),
 bound_artifact_sha256=pins,core_source_checks=source_checks,payload_top_keys=list(payload),partial_keys=list(partial),capture_tables=tables,
 failure_phase=partial.get('failure_phase'),ordered_is_none=partial['ordered']is None,
 actual_settings_capture_count=len(partial.get('actual',[])),effective_policy_capture_count=len(partial.get('effective_off_policy',[])),wait_audit_rows=len(partial.get('wait_audit',[])),resolver_audit_rows=len(partial.get('resolver_audit',[])),
 forbidden_metadata_paths=forbidden_paths(preflight,['payload','preflight']),forbidden_partial_paths=forbidden_paths(partial,['failure_capture','capture']),metadata_guard_error=guard_error,
 identity_coverage=dict(captured_trade_rows=len(trade_ids),unique_trade_ids=len(set(trade_ids)),usage_rows=len(usage_ids),unique_usage_trade_ids=len(set(usage_ids)),trade_usage_id_sets_equal=set(trade_ids)==set(usage_ids),actual_trade_identities_field_present='actual_trade_identities'in partial,actual_identity_fields_absent_from_capture_trades=sorted(set(identity_fields)-trade_fields),actual_identity_fields_absent_from_capture_usage=sorted(set(identity_fields)-usage_fields)),
 equity_calendar_coverage=dict(rows=len(dates),unique_dates=len(set(dates)),first=min(dates)if dates else None,last=max(dates)if dates else None,reference_count=len(wanted),exact_reference_sequence=dates==wanted,missing_reference_dates=len(set(wanted)-set(dates)),extra_dates=len(set(dates)-set(wanted))),
 required_raw_fields_absent_from_partial=sorted(required_keys-set(partial)),outer_run_context_available=True,preflight_available_as_separately_pinned_JSON=True,
 combined_present='combined'in partial,frames_present='frames'in partial,expected_returned_frame_names=expected_frames,
 files_present=[str(p.relative_to(a))for p in sorted(a.rglob('*'))if p.is_file()and not p.is_relative_to(a/'sources')],
 source_data_counts=dict(source_bindings=len(context['source_bindings']),data_bindings=len(preflight['data_bindings']),full_market_data_hashes_performed=0),
 forbidden_new_modules_loaded=[n for n in ['tqsdk','sklearn','joblib','vnpy','vnpy_portfoliostrategy','stage065_run_pairwise_off']if n in sys.modules],
 financial_curve_or_metrics_computed=False,engine_or_strategy_constructed=False,source_or_market_loader_called=False,network_calls=0,model_calls=0,restoration_performed=False)
assert not report['forbidden_new_modules_loaded']
(out/'coverage_diagnostic.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))
PY
