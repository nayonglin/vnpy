"""Source-bound weekly controller using the existing exact authorization file.

No order or CTP API is called. A plan, JSON flag or dry-run row alone never
creates an authority. Production loading verifies the actual installed chain.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping

from qmt_roll_official_execution_profile import WEEKLY19_15W_R150K_PROFILE as PROFILE
from qmt_roll_official_live_authorization_lock import exclusive_submit_authorization_lock, submit_authorization_lock_path, SubmitAuthorizationLockBusyError
from qmt_roll_official_live_intent_spool import snapshot_authorizable_intents, authorization_snapshots_match
from qmt_roll_official_live_submit_authorization import publish_submit_authorization, revoke_submit_authorization, validate_submit_authorization
from qmt_roll_weekly19_execution import evaluate_intent

_AUTHORITY_TOKEN = object()
class Weekly19ControllerError(ValueError): pass

def _require(condition, reason):
 if not condition: raise Weekly19ControllerError(reason)

def digest(value):
 return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def _file_digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def _production_head(repo):
 return subprocess.run(['git','rev-parse','--verify','HEAD^{commit}'],cwd=repo,capture_output=True,text=True,check=True,timeout=5).stdout.strip()

def _assert_production_manifest_head(manifest,production_commit):
 _require(manifest['source_commit']==production_commit,'weekly19_controller_production_manifest_source_mismatch')

def _assert_pinned_production_source(repo,production_commit,files):
 _require(all(_file_digest(path)==sha for path,sha in files.items()),'weekly19_controller_source_or_receipt_drift')
 _require(_production_head(repo)==production_commit,'weekly19_controller_production_head_drift')

def immutable_context_digest(value):
 """Only unadmitted cash reference lists are mutable, never authority fields."""
 _require(isinstance(value,dict),'weekly19_context_object_required')
 return digest({key:item for key,item in value.items()if key!='cash_sources'})

def assert_immutable_context(path,expected_digest):
 from qmt_roll_weekly19_local_backend import private_json
 current=private_json(path)
 _require(immutable_context_digest(current)==expected_digest,'weekly19_context_immutable_fields_changed')
 return current

@dataclass(frozen=True)
class Weekly19ControllerAuthority:
 _token: object
 bindings: Mapping[str,Any]
 _source_check: Any
 expires_epoch_ns: int
 broker_policy: Mapping[str,Any]
 capture_authority: Any
 _invalidated: dict = field(default_factory=dict,compare=False,repr=False)
 def invalidate(self,reason):
  self._invalidated.setdefault('reason',str(reason))
 def assert_current(self,now):
  _require(self._token is _AUTHORITY_TOKEN,'weekly19_controller_authority_invalid')
  _require(not self._invalidated,'weekly19_controller_source_authority_invalidated:'+self._invalidated.get('reason',''))
  _require(int(now.timestamp()*1_000_000_000)<self.expires_epoch_ns,'weekly19_controller_source_authority_expired')
  try:self._source_check(now)
  except Exception as exc:
   self.invalidate(str(exc));raise


def load_weekly19_controller_authority(*,backend,daily_receipt_path,context_file,target_date,now):
 """Load a process-local capability from real source/qualification/receipt files."""
 from qmt_roll_weekly19_local_backend import LocalEvidenceBackend
 from qmt_roll_weekly19_daily_receipt import load_and_validate_weekly19_daily_receipt
 from qmt_roll_weekly19_broker_evidence import load_capture_authority_registry
 _require(isinstance(backend,LocalEvidenceBackend) and not backend.preview,'weekly19_real_production_backend_required')
 gate=backend.require_production();manifest=gate['manifest'];qualification=gate['qualification']
 production_commit=_production_head(backend.repo);_assert_production_manifest_head(manifest,production_commit)
 receipt=load_and_validate_weekly19_daily_receipt(daily_receipt_path,context_file=context_file,
  source_commit=manifest['source_commit'],manifest_sha256=manifest['manifest_sha256'],target_date=target_date,now=now)
 policy=backend._broker_policy(now)
 registry=policy.get('capture_authority_registry')
 _require(isinstance(registry,dict),'weekly19_capture_authority_registry_required')
 capability=load_capture_authority_registry(registry,expected_account_key=backend.config['account_key'],
  material_release_id=backend.config['material_release_id'],execution_profile=PROFILE.profile_key,
  trusted_source_hashes=policy['trusted_source_hashes'],now=now)
 context_digest=immutable_context_digest(backend.config)
 assert_immutable_context(context_file,context_digest)
 bindings=dict(execution_profile=PROFILE.profile_key,official_version=PROFILE.official_version,ruleset_version=PROFILE.ruleset_version,
  material_release_id=backend.config['material_release_id'],account_fingerprint=backend.config['account_key'],
  source_commit=manifest['source_commit'],production_source_commit=production_commit,material_source_commit=gate['identity']['source_commit'],manifest_sha256=manifest['manifest_sha256'],qualification_sha256=qualification['evidence_sha256'],
  activation_receipt_sha256=_file_digest(backend.activation_receipt),daily_receipt_sha256=receipt['receipt_sha256'],
  source_data_receipt_sha256=digest(receipt['data_receipt']),decision_origin_state_sha256=receipt['decision_origin_state_sha256'],
  target_cutoff_date=target_date,context_semantic_sha256=context_digest)
 files={str(backend.repo/row['path']):row['sha256'] for row in manifest['critical_files']}
 for path in (backend.release_manifest,backend.activation_receipt,backend.qualification_evidence,Path(daily_receipt_path)):
  files[str(path)]=_file_digest(path)
 required={'examples/portfolio_backtesting/qmt_roll_weekly19_controller.py','examples/portfolio_backtesting/qmt_roll_weekly19_execution_service.py',
  'examples/portfolio_backtesting/qmt_roll_weekly19_execution.py','examples/portfolio_backtesting/qmt_roll_official_live_submit_authorization.py',
  'examples/portfolio_backtesting/run_qmt_roll_stage931_official_live_ctp_submit_adapter.py'}
 required.update('examples/portfolio_backtesting/'+name for name in (
  'qmt_roll_weekly19_session_bridge.py','qmt_roll_weekly19_runtime.py','qmt_roll_weekly19_pipeline_state.py','qmt_roll_weekly19_data.py',
  'qmt_roll_weekly19_data_update.py','qmt_roll_weekly19_quote_spool.py','qmt_roll_weekly19_context_update.py',
  'qmt_roll_weekly19_local_backend.py','qmt_roll_weekly19_live_pipeline.py','qmt_roll_weekly19_daily_receipt.py',
  'qmt_roll_weekly19_funding.py','qmt_roll_weekly19_funding_store.py','qmt_roll_weekly19_manual_cash.py',
  'run_qmt_roll_weekly19_manual_cash.py','qmt_roll_weekly19_warm_evidence.py',
  'qmt_roll_weekly19_broker_evidence.py','qmt_roll_weekly19_friday_advice.py','qmt_roll_weekly19_friday_report.py',
  'qmt_roll_weekly19_official_config.py','qmt_roll_weekly19_session_clock.py','run_qmt_roll_weekly19_live.py'))
 _require(required.issubset({row['path']for row in manifest['critical_files']}),'weekly19_controller_critical_source_closure_missing')
 def source_check(at):
  _assert_pinned_production_source(backend.repo,bindings['production_source_commit'],files)
  assert_immutable_context(context_file,context_digest)
 expiry=now+timedelta(days=1)
 frozen_policy={key:value for key,value in policy.items()if key!='now'}
 return Weekly19ControllerAuthority(_AUTHORITY_TOKEN,deepcopy(bindings),source_check,int(expiry.timestamp()*1_000_000_000),frozen_policy,capability)


def _validate_fresh_source_proof(authority,context,now):
 from qmt_roll_weekly19_warm_evidence import load_warm_broker_snapshot
 policy=dict(authority.broker_policy,now=now,capture_authority_capability=authority.capture_authority,require_production_qualification=True)
 actual=load_warm_broker_snapshot(context['transport_context'],**policy)
 _require(actual.get('source_qualified')is True,'weekly19_controller_broker_source_not_qualified')
 for kind in ('account','positions','orders','trades'):
  _require(actual[kind]['raw_sha256']==context['broker_snapshot'][kind]['raw_sha256'],'weekly19_controller_broker_source_binding_mismatch')


def _spool_snapshot(connection,clock):
 return snapshot_authorizable_intents(connection,now_epoch_ns=clock.epoch_ns(),now_monotonic_ns=clock.monotonic_ns(),
  clock_domain_id=clock.clock_domain_id(),execution_profile=PROFILE.profile_key)


def publish_weekly19_controller_authorization(connection,*,spool_path,authorization_path,authority,
 fresh_context_provider,readiness,clock):
 """Publish exactly one actual ready spool row under the existing flock.

 Evidence names stage902/stage927 are generic protocol slots. Their schemas
 and statuses below are explicitly weekly and never claim legacy 903 passed.
 """
 path=Path(authorization_path);epoch=clock.epoch_ns();now=datetime.fromtimestamp(epoch/1_000_000_000,tz=timezone.utc)
 def blocked(reason):
  revoke_submit_authorization(path,reason=reason,revoked_epoch_ns=clock.epoch_ns())
  return dict(schema='weekly19.controller-publication.v1',status='blocked',blockers=[reason],production_qualified=False,order_api_called_count=0)
 try:
  with exclusive_submit_authorization_lock(submit_authorization_lock_path(path.parent),blocking=False):
   if not isinstance(authority,Weekly19ControllerAuthority)or authority._token is not _AUTHORITY_TOKEN:
    return blocked('weekly19_source_qualification_authority_missing')
   authority.assert_current(now)
   _require(callable(fresh_context_provider),'weekly19_controller_fresh_provider_missing')
   before=_spool_snapshot(connection,clock);candidate=before.candidate
   if candidate is None:
    result=blocked('weekly19_no_exact_ready_candidate');result['status']='no_candidate';return result
   raw=connection.execute('SELECT payload_json FROM intents WHERE intent_id=?',(candidate.intent_id,)).fetchone()
   _require(raw is not None,'weekly19_controller_candidate_disappeared');row=json.loads(raw['payload_json'])
   context=fresh_context_provider(deepcopy(row))
   now=datetime.fromtimestamp(clock.epoch_ns()/1_000_000_000,tz=timezone.utc)
   authority.assert_current(now);_validate_fresh_source_proof(authority,context,now)
   gate=evaluate_intent(row,context,now=now)
   _require(gate['allowed']and gate['volume']==row['planned_volume'],'weekly19_controller_fresh_gate_blocked:'+','.join(gate['blockers']))
   source=dict(authority.bindings)
   for key,actual in (('material_release_id',context['material_release_id']),('account_fingerprint',context['account_fingerprint']),
                      ('target_cutoff_date',context['target_cutoff_date']),('source_data_receipt_sha256',context['data_receipt_sha256'])):
    _require(source.get(key)==actual,'weekly19_controller_source_context_mismatch:'+key)
   # Original-rule sizing can exceed the three-second transport lease TTL.
   # Issue the actual lease after that work, without holding the actor lock.
   readiness=readiness()if callable(readiness)else readiness
   epoch=clock.epoch_ns()
   _require(readiness.get('runtime_profile')=='production-live'and readiness.get('service_kind')=='warm_live_executor'
    and readiness.get('official_version')==PROFILE.official_version and readiness.get('capital')==PROFILE.capital,
    'weekly19_controller_live_readiness_identity_invalid')
   expiry=min(int(readiness['expires_epoch_ns']),candidate.deadline_epoch_ns,authority.expires_epoch_ns)
   _require(type(readiness.get('issued_epoch_ns'))is int and readiness['issued_epoch_ns']<=epoch<expiry,
    'weekly19_controller_broker_readiness_expired')
   bindings=dict(source,planned_intent_id=row['planned_intent_id'],signal_identity_sha256=digest(row['signal_identity']),
    physical_epoch_id=row['physical_epoch_id'],durable_state_sha256=context['durable_state_sha256'],
    funding_state_sha256=digest(context.get('confirmed_cash_state')),broker_snapshot_sha256=digest(context['broker_snapshot']),
    quote_proof_sha256=digest(row['weekly19_quote_proof']),service_generation=readiness['service_generation'],
    connection_generation=readiness['connection_generation'],trading_date=context['trading_date'],
    spool_snapshot_digest=before.snapshot_digest,cursor_digest=before.cursor_digest)
   common=dict(execution_profile=PROFILE.profile_key,bindings=bindings,bindings_sha256=digest(bindings),expires_epoch_ns=expiry)
   control=dict(common,schema='weekly19.controller-evidence.v1',status='weekly19_controller_ready',target_date=candidate.target_date,
    gate_sha256=digest(gate),intent_id=candidate.intent_id,payload_sha256=candidate.payload_sha256)
   arming=dict(common,schema='weekly19.arming-evidence.v1',status='weekly19_arming_ready',intent_id=candidate.intent_id,
    payload_sha256=candidate.payload_sha256,source_qualification_sha256=source['qualification_sha256'])
   broker=dict(common,schema='weekly19.broker-gate.v1',status='ready',service_generation=readiness['service_generation'],
    connection_generation=readiness['connection_generation'],snapshot_sha256=bindings['broker_snapshot_sha256'])
   tick=dict(common,schema='weekly19.quote-gate.v1',candidate_symbol_ready=1,candidate_symbol=candidate.vt_symbol,
    candidate_ingress_epoch_ns=candidate.ingress_epoch_ns,all_symbols_ready=0,quote_proof_sha256=bindings['quote_proof_sha256'])
   after=_spool_snapshot(connection,clock)
   _require(authorization_snapshots_match(before,after),'weekly19_controller_spool_changed_during_gate')
   record=asdict(candidate);record['weekly19_bindings']=bindings
   record['weekly19_bindings_sha256']=digest(bindings)
   payload=publish_submit_authorization(path=path,target_date=candidate.target_date,execution_profile=PROFILE.profile_key,
    runtime_profile='production-live',order_scope='live',service_generation=readiness['service_generation'],connection_generation=readiness['connection_generation'],
    cycle_id='W19CTRL-'+digest(bindings),intent_scope='reduce_close_only'if candidate.intent_kind=='close'else'initial_open_only',
    authorized_intents=[record],issued_epoch_ns=epoch,expires_epoch_ns=expiry,controller_evidence=control,stage927_evidence=arming,
    broker_gate_evidence=broker,tick_watermark_evidence=tick,authorization_lane='slow_controller',spool_path=spool_path,
    spool_snapshot_digest=before.snapshot_digest,cursor_digest=before.cursor_digest,
    stage902_evidence_digest=digest(broker),stage927_evidence_digest=digest(arming))
   failures=validate_submit_authorization(path=path,target_date=candidate.target_date,execution_profile=PROFILE.profile_key,
    runtime_profile='production-live',order_scope='live',service_generation=readiness['service_generation'],connection_generation=readiness['connection_generation'],
    now_epoch_ns=clock.epoch_ns(),intent_id=candidate.intent_id,payload_sha256=candidate.payload_sha256,intent_kind=candidate.intent_kind,
    weekly19_bindings=bindings,
    **{key:getattr(candidate,key) for key in ('vt_symbol','source','intent_role','trace_id','state_generation',
       'position_epoch_id','root_position_id','position_cycle_id','spool_sequence','state_revision','deadline_epoch_ns')})
   _require(not failures,'weekly19_controller_authorization_readback_failed:'+','.join(failures))
   return dict(schema='weekly19.controller-publication.v1',status='published',intent_id=candidate.intent_id,
    record_digest=payload['record_digest'],expires_epoch_ns=expiry,production_qualified=False,order_api_called_count=0)
 except SubmitAuthorizationLockBusyError:
  return dict(schema='weekly19.controller-publication.v1',status='execution_in_progress',production_qualified=False,order_api_called_count=0)
 except Exception as exc:
  with exclusive_submit_authorization_lock(submit_authorization_lock_path(path.parent)):
   return blocked(str(exc))
