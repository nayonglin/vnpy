"""Frozen Stage011 source/data admission and new-run checkpoints.

Original Stage009 reserve checkpoints are read using their original freeze.
Stage011 runs retain that ledger schema and receive a separate risk-delta proof.
"""
from pathlib import Path
import hashlib,json
import stage009_contract as baseline
from stage009_contract import ROOT,LINE,STARTS,CUTOFF,ENGINE_CAPITAL,RESERVE_CAPITAL,TOTAL_CAPITAL,IDENTITY_KEYS,sha,load,atomic_json,snapshot_dir,metric_close,reserve_daily_bridge,total_metric_frame,validate_reserve_snapshots,validate_event_daily_anchors,validate_reserve_checks
from stage011_risk import NEW_RISK,accept_uniform_risk

BASELINE_IDENTITIES=('baseline_freeze','baseline_registry','baseline_delivery_manifest','baseline_reporting_manifest')
DATA_FILES=dict(daily_sqlite_sha256='daily.sqlite',mapping_sha256='mapping.csv',physical_epoch_daily_sha256='physical_epoch_daily.csv',receipt_sha256='receipt.json')


def validate_start(start):
 if start not in STARTS:raise ValueError('stage011_start_not_in_frozen23')
 return start


def required_financial_sources():
 tools=LINE/'tools';stages=LINE/'stages'
 return [tools/name for name in ['run_stage011.py','stage011_risk.py','stage011_contract.py','stage011_coordinator.py','test_stage011_runner.py','test_stage011_risk.py','test_stage011_contract.py','test_stage011_coordinator.py']]+[stages/name for name in ['20261030_stage011_uniform_risk_design.md','20261030_stage011_implementation_plan.md']]


def validate_data_identity(freeze):
 directory=Path(freeze['data_directory']).resolve()
 for key,name in DATA_FILES.items():
  if sha(directory/name)!=freeze['data_identity'][key]:raise ValueError('stage011_frozen_data_changed:'+name)


def validate_freeze(path):
 p=Path(path).resolve();f=load(p)
 if f.get('schema')!='stage011_frozen_uniform_risk_23starts_v1' or f.get('starts')!=list(STARTS) or f.get('arms')!=['A','C'] or f.get('cutoff')!=CUTOFF:raise ValueError('stage011_window_or_schema_mismatch')
 head=f.get('source_head','')
 if len(head)!=40 or any(c not in '0123456789abcdef' for c in head):raise ValueError('stage011_frozen_head_required')
 for key,value in [('engine_initial_capital',ENGINE_CAPITAL),('reserve_initial_capital',RESERVE_CAPITAL),('total_initial_capital',TOTAL_CAPITAL),('planned_arm_windows',46),('planned_financial_replays',46),('baseline_arm_windows',46),('max_workers',2),('canary_start','2015-01-01')]:
  if f.get(key)!=value:raise ValueError('stage011_frozen_scope_changed:'+key)
 if f.get('risk_overrides')!=NEW_RISK:raise ValueError('stage011_exact_three_uniform_risk_overrides_required')
 expected={'baseline_freeze':LINE/'stages/stage009_freeze.json','baseline_registry':LINE/'outputs/stage009_multistart/registry.json','baseline_delivery_manifest':LINE/'stages/stage009_delivery_manifest.json','baseline_reporting_manifest':LINE/'stages/stage010_delivery_manifest.json'}
 for prefix in BASELINE_IDENTITIES:
  if Path(f.get(prefix,'')).resolve()!=expected[prefix].resolve() or not f.get(prefix+'_sha256') or sha(f[prefix])!=f[prefix+'_sha256']:raise ValueError('stage011_baseline_identity_changed:'+prefix)
 old,old_sha=baseline.validate_freeze(f['baseline_freeze'])
 if old_sha!=f['baseline_freeze_sha256'] or f.get('data_identity')!=old['data_identity'] or set(f.get('data_identity',{}))!=IDENTITY_KEYS or Path(f.get('data_directory','')).resolve()!=Path(old['data_directory']).resolve():raise ValueError('stage011_baseline_data_identity_mismatch')
 sources=f.get('source_files_sha256',{})
 if not isinstance(sources,dict) or not sources:raise ValueError('stage011_financial_sources_required')
 resolved={str((Path(k) if Path(k).is_absolute() else ROOT/k).resolve()):v for k,v in sources.items()}
 if not {str(q.resolve()) for q in required_financial_sources()}<=set(resolved):raise ValueError('stage011_required_financial_source_missing')
 for name,h in old['source_files_sha256'].items():
  q=Path(name);q=q if q.is_absolute() else ROOT/q
  if resolved.get(str(q.resolve()))!=h:raise ValueError('stage011_inherited_financial_source_missing_or_changed:'+str(q))
 for name,h in resolved.items():
  if not Path(name).is_file() or sha(name)!=h:raise ValueError('stage011_frozen_source_changed:'+name)
 validate_data_identity(f)
 return f,sha(p)


def checkpoint_key(freeze,freeze_sha,arm,start):
 validate_start(start)
 if arm not in {'A','C'}:raise ValueError('stage011_unknown_arm')
 identity={k:freeze.get(k) for k in ['source_head','cutoff','engine_initial_capital','reserve_initial_capital','total_initial_capital','risk_overrides','baseline_registry_sha256']}
 return hashlib.sha256(json.dumps(dict(**identity,freeze_sha256=freeze_sha,arm=arm,start=start),sort_keys=True).encode()).hexdigest()


def baseline_job(freeze,arm,start,verify=True):
 validate_start(start)
 if arm not in {'A','C'}:raise ValueError('stage011_unknown_arm')
 if sha(freeze['baseline_registry'])!=freeze['baseline_registry_sha256']:raise ValueError('stage011_baseline_registry_changed')
 registry=load(freeze['baseline_registry']);old=load(freeze['baseline_freeze']);old_sha=sha(freeze['baseline_freeze'])
 if old_sha!=freeze['baseline_freeze_sha256'] or registry.get('freeze_sha256')!=old_sha:raise ValueError('stage011_baseline_freeze_mismatch')
 expected={s+'|'+a for s in STARTS for a in ['A','C']}
 if registry.get('starts')!=list(STARTS) or registry.get('cutoff')!=CUTOFF or set(registry.get('jobs',{}))!=expected or any(j.get('status')!='validated' for j in registry['jobs'].values()):raise ValueError('stage011_exact46_validated_reserve_baselines_required')
 job=registry['jobs'][start+'|'+arm]
 if verify:
  checked=baseline.read_checkpoint(job['checkpoint'],old,old_sha,arm,start)
  if checked['path']!=job['path'] or checked['files_sha256']!=job['files_sha256']:raise ValueError('stage011_baseline_checkpoint_mismatch')
 if Path(job['path']).name!=f"stage009_{arm}_{start.replace('-','')}_attempt001":raise ValueError('stage011_wrong_baseline_run_path')
 return dict(path=job['path'],checkpoint=job['checkpoint'],checkpoint_sha256=sha(job['checkpoint']),files_sha256=job['files_sha256'],arm=arm,start=start,financial_replays=0,reserve_topup_enabled=True)


def validate_baseline_controls(freeze):
 return {s+'|'+a:baseline_job(freeze,a,s) for s in STARTS for a in ['A','C']}


def risk_proof(path,freeze,arm,start,job=None):
 import pandas as pd
 p=Path(path);job=job or baseline_job(freeze,arm,start);old=Path(job['path'])
 result=accept_uniform_risk(load(p/'actual_strategy_settings.json'),load(old/'actual_strategy_settings.json'),load(p/'effective_parameters.json'),load(old/'effective_parameters.json'),pd.read_csv(p/'entry_risk.csv'))
 result.update(baseline_path=str(old),baseline_checkpoint_sha256=job['checkpoint_sha256'],baseline_settings_sha256=sha(old/'actual_strategy_settings.json'),baseline_effective_sha256=sha(old/'effective_parameters.json'),baseline_registry_sha256=freeze['baseline_registry_sha256'])
 return result


def validate_run_inputs(path,freeze,job):
 p=Path(path);pre=load(p/'preflight.json');manifest=load(p/'input_manifest.json')
 expected={str((Path(k) if Path(k).is_absolute() else ROOT/k).resolve()):v for k,v in freeze['source_files_sha256'].items()}
 expected.update({str((Path(freeze['data_directory'])/name).resolve()):freeze['data_identity'][key] for key,name in DATA_FILES.items()})
 expected.update({str(Path(freeze[key]).resolve()):freeze[key+'_sha256'] for key in BASELINE_IDENTITIES})
 expected[str(Path(job['checkpoint']).resolve())]=job['checkpoint_sha256'];expected.update(job['files_sha256'])
 if not pre.get('freeze_path') or not pre.get('freeze_sha256'):raise ValueError('stage011_run_freeze_path_required')
 expected[str(Path(pre['freeze_path']).resolve())]=pre['freeze_sha256']
 for name,digest in expected.items():
  if manifest.get(name)!=digest or not Path(name).is_file() or sha(name)!=digest:raise ValueError('stage011_run_input_missing_or_changed:'+name)


def validate_run(path,freeze,arm,start):
 p=Path(path).resolve();info=baseline.validate_run(p,freeze,arm,start)
 pre=load(p/'preflight.json')
 if pre.get('uniform_risk_enabled') is not True or pre.get('risk_overrides')!=NEW_RISK or pre.get('baseline_registry_sha256')!=freeze['baseline_registry_sha256']:raise ValueError('stage011_run_risk_or_baseline_identity_mismatch')
 job=baseline_job(freeze,arm,start);validate_run_inputs(p,freeze,job)
 if load(p/'uniform_risk_acceptance.json')!=risk_proof(p,freeze,arm,start,job):raise ValueError('stage011_uniform_risk_proof_not_actual')
 return {**info,'uniform_risk_overrides':NEW_RISK,'baseline_path':load(p/'uniform_risk_acceptance.json')['baseline_path']}


def validate_run_freeze_identity(path,freeze,freeze_sha,arm,start):
 baseline.validate_run_freeze_identity(path,freeze,freeze_sha,arm,start)


def make_checkpoint(path,checkpoint,freeze,freeze_sha,arm,start):
 if Path(checkpoint).exists():raise ValueError('stage011_checkpoint_already_exists')
 validate_run_freeze_identity(path,freeze,freeze_sha,arm,start)
 info=validate_run(path,freeze,arm,start)
 info.update(schema='stage011_checked_uniform_risk_run_v1',checkpoint_key=checkpoint_key(freeze,freeze_sha,arm,start),freeze_sha256=freeze_sha,source_head=freeze['source_head'],reused=False,files_sha256=snapshot_dir(path))
 atomic_json(checkpoint,info);return info


def read_checkpoint(checkpoint,freeze,freeze_sha,arm,start):
 r=load(checkpoint)
 if r.get('schema')!='stage011_checked_uniform_risk_run_v1' or r.get('reused') is not False or any(r.get(k)!=v for k,v in [('freeze_sha256',freeze_sha),('source_head',freeze['source_head']),('arm',arm),('start',start),('end',freeze['cutoff'])]) or r.get('checkpoint_key')!=checkpoint_key(freeze,freeze_sha,arm,start) or r.get('files_sha256')!=snapshot_dir(r['path']):raise ValueError('stage011_checkpoint_identity_or_output_changed')
 validate_run_freeze_identity(r['path'],freeze,freeze_sha,arm,start);current=validate_run(r['path'],freeze,arm,start)
 for basis in ['metrics','raw_metrics']:
  if any(not metric_close(value,r[basis][key]) for key,value in current[basis].items()):raise ValueError('stage011_checkpoint_metric_changed:'+basis)
 return r
