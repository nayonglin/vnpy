"""Local weekly19 evidence backend. Loading JSON never grants a capability.

Production jobs first validate the existing immutable release/qualification/
activation chain. Broker capture origins are independently admitted by the
provider. This module does not submit orders or initiate a bank transfer.
"""
from copy import deepcopy
from datetime import datetime
import hashlib,json,os
from dataclasses import asdict
from pathlib import Path
import stat,subprocess
import uuid
from qmt_roll_official_execution_profile import WEEKLY19_15W_R150K_PROFILE as PROFILE
from qmt_roll_weekly19_pipeline_state import unique
import qmt_roll_weekly19_broker_evidence as broker
import qmt_roll_weekly19_funding as funds

PRODUCTION_DEPLOY_ROOT=Path.home()/'Desktop/person/vnpy_production_live'
class LocalBackendError(ValueError):pass

def private_json(path):
 path=Path(path)
 if not path.is_absolute()or '..'in path.parts:raise LocalBackendError('weekly19_private_absolute_path_required')
 directory=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
 try:
  for part in path.parts[1:-1]:
   child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory);os.close(directory);directory=child
  fd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=directory)
  with os.fdopen(fd,'rb')as f:
   st=os.fstat(f.fileno())
   if not stat.S_ISREG(st.st_mode)or st.st_uid!=os.geteuid()or st.st_nlink!=1 or stat.S_IMODE(st.st_mode)!=0o600:raise LocalBackendError('weekly19_private_file_required')
   raw=f.read(64_000_001)
 finally:os.close(directory)
 if len(raw)>64_000_000:raise LocalBackendError('weekly19_private_json_oversized')
 return json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in()).throw(LocalBackendError('weekly19_nonfinite_json')))

class LocalEvidenceBackend:
 def __init__(self,config,*,repo_root,release_manifest,activation_receipt,qualification_evidence,preview=False):
  if (not isinstance(config,dict)or config.get('schema')!='weekly19.live-context.v1'
   or config.get('execution_profile')!=PROFILE.profile_key):raise LocalBackendError('weekly19_context_profile_or_schema_invalid')
  if any(k in config for k in ('backend','qualified','production_qualified','sender','context_provider')):raise LocalBackendError('weekly19_context_capability_injection_forbidden')
  self.config=deepcopy(config);self.repo=Path(repo_root).resolve(strict=True);self.preview=preview
  self.release_manifest=Path(release_manifest);self.activation_receipt=Path(activation_receipt);self.qualification_evidence=Path(qualification_evidence)
  self._last_inputs=None;self._gate=None;self.external_action_started=False;self.cash_source_blocker=None
  self._market_cache=None;self._market_cache_key=None;self._market_cache_stats=None
  self._service=None;self._bridge=None;self._session_owner_closed=False;self._session_context_invalidated=None
 def require_production(self):
  if self.preview:raise LocalBackendError('preview_backend_cannot_be_production')
  if self.repo!=PRODUCTION_DEPLOY_ROOT.resolve(strict=False):raise LocalBackendError('weekly19_stable_production_root_required')
  # Check all real artifacts before loading account secrets or building a gateway.
  for label,path in [('release_manifest',self.release_manifest),('activation_receipt',self.activation_receipt),('production_qualification',self.qualification_evidence)]:
   if not path.is_file():raise LocalBackendError('weekly19_missing_'+label)
  from qmt_roll_official_baseline_identity import assert_official_checkout_matches_active_material
  identity=asdict(assert_official_checkout_matches_active_material(self.repo))
  if identity.get('strategy_version')!=PROFILE.official_version or identity.get('ruleset_version')!=PROFILE.ruleset_version:raise LocalBackendError('weekly19_active_material_mismatch')
  from qmt_roll_official_live_release_manifest import load_and_validate_release_manifest
  from build_qmt_roll_stage179_release_manifest import load_and_validate_production_qualification_evidence
  from run_qmt_roll_stage914_official_live_ctp_runtime_preflight import validate_stage179_activation_receipt
  head=subprocess.run(['git','rev-parse','--verify','HEAD^{commit}'],cwd=self.repo,capture_output=True,text=True,check=True,timeout=10).stdout.strip()
  manifest=load_and_validate_release_manifest(self.release_manifest,repo_root=self.repo,
   expected_official_version=PROFILE.official_version,expected_capital=PROFILE.capital,expected_capital_label=PROFILE.capital_label,
   expected_execution_profile=PROFILE.profile_key,required_runtime_profile='production-live',current_commit=head)
  evidence=load_and_validate_production_qualification_evidence(self.qualification_evidence,repo_root=self.repo,
   source_commit=manifest['source_commit'],execution_profile=PROFILE.profile_key,official_version=PROFILE.official_version,
   capital=PROFILE.capital,capital_label=PROFILE.capital_label,
   critical_files=[r['path']for r in manifest['critical_files']],manifest_created_at_utc=manifest['created_at_utc'])
  if manifest.get('strategy_semantics_qualification',{}).get('evidence_id')!=evidence['evidence_sha256']:raise LocalBackendError('weekly19_qualification_manifest_mismatch')
  blockers=validate_stage179_activation_receipt(self.activation_receipt,manifest_sha256=manifest['manifest_sha256'],
   official_version=PROFILE.official_version,capital=PROFILE.capital,capital_label=PROFILE.capital_label)
  if blockers:raise LocalBackendError('weekly19_activation_receipt_invalid')
  if identity.get('material_release_id')!=self.config['material_release_id']:raise LocalBackendError('weekly19_context_release_mismatch')
  from qmt_roll_weekly19_manual_cash import assert_manual_mode
  assert_manual_mode(self)
  self._gate=dict(manifest=manifest,qualification=evidence,identity=identity,production_source_commit=head)
  return deepcopy(self._gate)
 def _broker_policy(self,now):
  policy=deepcopy(self.config['broker']['policy'])
  # These identities are not configurable aliases.
  for key in ('expected_account_key','material_release_id','execution_profile','now','require_production_qualification'):
   if key in policy:raise LocalBackendError('weekly19_broker_policy_identity_override')
  policy.update(expected_account_key=self.config['account_key'],material_release_id=self.config['material_release_id'],
   execution_profile=PROFILE.profile_key,now=now,require_production_qualification=not self.preview)
  return policy
 def refresh_readonly(self,now):
  if self.preview:raise LocalBackendError('preview_cannot_refresh_ctp')
  self.require_production();policy=self._broker_policy(now);reference=policy.get('capture_authority_registry')
  broker.load_capture_authority_registry(reference,expected_account_key=self.config['account_key'],material_release_id=self.config['material_release_id'],
   execution_profile=PROFILE.profile_key,trusted_source_hashes=policy['trusted_source_hashes'],now=now)
  from qmt_roll_official_live_phase_d_config import PHASE_D_READONLY_REFRESH_CONFIRM_TEXT,PHASE_D_READONLY_REFRESH_ENV
  capture_dir=Path(self.config['broker']['private_capture_dir'])
  if not capture_dir.is_dir()or capture_dir.is_symlink()or capture_dir.stat().st_mode&0o777!=0o700:raise LocalBackendError('weekly19_private_capture_directory_required')
  argv=[str(self.repo/'.py311/bin/python'),str(self.repo/'examples/portfolio_backtesting/run_qmt_roll_stage907_official_live_readonly_refresh_gate.py'),
   '--mode','refresh','--env-profile','production-live','--wait-seconds','30','--confirm-readonly-refresh',PHASE_D_READONLY_REFRESH_CONFIRM_TEXT,
   '--email-policy','never','--weekly19-material-release-id',self.config['material_release_id'],'--weekly19-execution-profile',PROFILE.profile_key,
   '--weekly19-private-capture-dir',str(capture_dir),'--weekly19-capture-authority-registry',reference['path'],'--weekly19-capture-authority-sha256',reference['sha256']]
  env=dict(os.environ);env[PHASE_D_READONLY_REFRESH_ENV]='1';self.external_action_started=True
  result=subprocess.run(argv,cwd=self.repo,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180,check=False)
  # Native logs are private. Do not return them to UI/mail or assume they prove
  # API zero; the provider verifies the complete source-bound counter window.
  if result.returncode!=0:raise LocalBackendError('weekly19_readonly_refresh_process_failed')
  evidence=self.config['broker'];snapshot=broker.load_broker_snapshot(evidence['summary_path'],evidence['manifest_path'],**self._broker_policy(datetime.now().astimezone()))
  if snapshot.get('source_qualified')is not True:raise LocalBackendError('weekly19_refreshed_source_not_admitted')
  return dict(status='readonly_source_refreshed',source_qualified=True)
 def resolve_target_date(self,now):
  from qmt_roll_weekly19_context_update import resolve_completed_target
  return resolve_completed_target(self,now)
 def refresh_market_data(self,target_date,now):
  from qmt_roll_weekly19_context_update import refresh_market_data
  return refresh_market_data(self,target_date,now)
 def _market_stats(self,market):
  root=Path(market['asset_root']);paths=[root]
  for name in market['expected_hashes']:
   if Path(name).name!=name or name in ('','.','..'):raise LocalBackendError('weekly19_market_asset_name_invalid')
   paths.append(root/name)
  result=[]
  for path in paths:
   st=path.lstat()
   if stat.S_ISLNK(st.st_mode):raise LocalBackendError('weekly19_market_symlink_forbidden')
   result.append((str(path),st.st_dev,st.st_ino,st.st_mode,st.st_uid,st.st_nlink,st.st_size,st.st_mtime_ns,st.st_ctime_ns))
  return tuple(result)
 def load_inputs(self,target_date,now):
  if not self.preview:self.require_production()
  from qmt_roll_weekly19_data import load_weekly19_inputs
  from qmt_roll_weekly19_pipeline_state import digest
  market=self.config['market_data'];key=digest(dict(target_date=target_date,market=market));stats=self._market_stats(market)
  if self._market_cache_key!=key or stats!=self._market_cache_stats:
   data=load_weekly19_inputs(Path(market['asset_root']),material_release_id=self.config['material_release_id'],
    target_date=target_date,forward_calendar=market['forward_calendar'],expected_hashes=market['expected_hashes'])
   if self._market_stats(market)!=stats:raise LocalBackendError('weekly19_market_changed_during_admission')
   self._market_cache=data;self._market_cache_key=key;self._market_cache_stats=stats
  # Cached market objects belong to one immutable admitted generation. Raw
  # account/positions/orders are always reloaded and freshly source-verified.
  evidence=self.config['broker'];snapshot=broker.load_broker_snapshot(evidence['summary_path'],evidence['manifest_path'],**self._broker_policy(now))
  data=dict(self._market_cache,broker_snapshot=snapshot);self._last_inputs=data;return data
 def session_provider(self,row,transport_context,now):
  from qmt_roll_weekly19_session_clock import resolve_weekly19_session
  from qmt_roll_weekly19_warm_evidence import load_warm_broker_snapshot
  policy=self._broker_policy(now)
  if getattr(self,'controller_authority',None)is not None:
   self.controller_authority.assert_current(now);policy['capture_authority_capability']=self.controller_authority.capture_authority
  snapshot=load_warm_broker_snapshot(transport_context,**policy)
  raw=funds._parse(snapshot['account'],'weekly19.ctp-account.v1','ctp_account_callback')
  if self._market_cache is None:raise LocalBackendError('weekly19_market_generation_not_admitted')
  return resolve_weekly19_session(now=now,broker_trading_date=raw['trading_day'],calendar=self._market_cache['calendar'])
 def validate_initial_account(self,snapshot,now,*,allow_carry_in=False):
  self.require_production()
  from qmt_roll_weekly19_startup import load_startup_authorization,assert_startup_snapshot
  policy=load_startup_authorization(self.config)
  if policy is not None:
   if not allow_carry_in:raise LocalBackendError('weekly19_explicit_existing_account_initializer_required')
   assert_startup_snapshot(policy,snapshot,account_key=self.config['account_key'],material_release_id=self.config['material_release_id'],now=now)
   return
  account=broker.read_account_snapshot(snapshot['account'],expected_account_key=self.config['account_key'],material_release_id=self.config['material_release_id'],now=now)
  positions=funds._parse(snapshot['positions'],'weekly19.ctp-positions.v1','ctp_position_query')['positions']
  orders=funds._parse(snapshot['orders'],'weekly19.ctp-orders.v1','ctp_order_query')['orders']
  if account['equity_fen']!=funds.INITIAL_FEN or positions or any(r['status']not in {'filled','cancelled','rejected'}for r in orders):raise LocalBackendError('weekly19_initial_real_150k_flat_account_required')
 def bootstrap_existing_account(self,bundle,data,now):
  self.require_production()
  from qmt_roll_weekly19_startup import load_startup_authorization,build_initial_carry_in_seed
  from qmt_roll_weekly19_runtime import bootstrap_weekly19_runtime,DEFAULT_SETTINGS_ASSET
  policy=load_startup_authorization(self.config)
  if policy is None:raise LocalBackendError('weekly19_explicit_existing_account_policy_required')
  if bundle['runtime']is not None or bundle['decision']is not None:raise LocalBackendError('weekly19_existing_account_bootstrap_first_state_only')
  evidence=self.config['broker']
  raw=broker.load_broker_carry_in_positions(evidence['summary_path'],evidence['manifest_path'],**self._broker_policy(now))
  seed=build_initial_carry_in_seed(policy,data,raw,now)
  completed=policy['authorization']['completed_day']
  return bootstrap_weekly19_runtime(DEFAULT_SETTINGS_ASSET,data['metadata'],data['calendar'],data['physical_epoch_daily'],
   data['broker_snapshot'],bundle['funding'],carry_in_seed=seed,
   warmup_batches=[data['bars_by_day'][day]for day in sorted(data['bars_by_day'])if day<=completed],clock=lambda:now)
 def reconcile_cash(self,state,snapshot,now):
  if getattr(self,'context_file',None)is not None:self._refresh_cash_sources()
  funds.validate_state(state);original=deepcopy(state);updated=deepcopy(state);self.cash_source_blocker=None
  sources=self.config.get('cash_sources',{})
  current=funds._broker(snapshot['account'],updated,now);checkpoint=updated['cashflow_checkpoint']
  mode=self.config.get('cash_verification_mode','broker_automatic_v1'if self.preview else None)
  if mode=='operator_manual_v1':
   from qmt_roll_weekly19_manual_cash import assert_manual_mode,load_private_manual_review,_calendar,ManualCashError
   try:
    if not self.preview:assert_manual_mode(self)
    if not isinstance(sources,dict):raise ManualCashError('manual_cash_sources_object_required')
    references=sources.get('manual_reviews',[])
    if not isinstance(references,list)or len(references)>1000:raise ManualCashError('manual_cash_reference_list_invalid')
    if checkpoint is None:
     if references:raise ManualCashError('initial_real_cash_observation_required_before_manual_review')
     from qmt_roll_weekly19_startup import load_startup_authorization
     policy=load_startup_authorization(self.config)
     options={}if policy is None else dict(opening_equity_mode='operator_existing_account_v1',operator_decision_id=policy['operator_decision_id'])
     return funds.begin_cash_observation(updated,snapshot['account'],now,**options)
    # Load EVERY reference before changing even the candidate state. A later
    # invalid reference cannot be hidden by a successful earlier review.
    records={}
    for reference in references:
     record=load_private_manual_review(reference)
     raw=funds._parse(record,'weekly19.operator-cash-review.v1','operator_manual')
     prior=records.setdefault(raw['record_id'],record)
     if prior!=record:raise ManualCashError('manual_cash_review_id_content_conflict')
    new=[key for key in records if key not in updated.get('manual_cash_reviews',{})]
    if len(new)>1:raise ManualCashError('one_new_manual_review_per_actor_commit_required')
    calendar=_calendar(self)if records else None
    for record in records.values():
     updated=funds.apply_operator_cash_review(updated,record,snapshot['account'],now,trading_calendar=calendar)
    funds._cashflow_match(updated,current)
    return updated
   except (ValueError,OSError)as exc:
    reason=str(exc)if isinstance(exc,(funds.FundingError,ManualCashError))else type(exc).__name__
    self.cash_source_blocker='manual_cash_review_pending:'+reason
    return original
  if mode!='broker_automatic_v1'or not self.preview:
   self.cash_source_blocker='manual_cash_review_pending:immutable_cash_verification_mode_not_configured'
   return original
  if checkpoint is None:
   return funds.begin_cash_observation(updated,snapshot['account'],now)
  try:
   if checkpoint['trading_day']!=current['trading_day']:
    row=sources.get('day_close')
    if row is None:raise broker.BrokerEvidenceError('accepted_cashflow_source_missing:final_broker_day_close_statement')
    proof=broker.load_cashflow_day_close(private_json(row['statement_path']),state=updated,now=now)
    updated=funds.reconcile_trading_day(updated,private_json(row['closing_account_path']),snapshot['account'],now,continuity_receipt=proof)
   for row in sources.get('deposits',[]):
    proof=broker.load_bank_cashflow_receipt(private_json(row['raw_source_path']),state=updated,request_id=row['request_id'],bank_serial=row['bank_serial'],now=now,
     require_production_qualification=not self.preview,capture_authority_registry=self.config['broker']['policy'].get('capture_authority_registry'),
     capture_authority_receipt=row.get('authority_receipt'))
    updated=funds.confirm_topup(updated,row['request_id'],proof,snapshot['account'],now)
  except (ValueError,OSError)as exc:
   # Account/positions and the saved strategy layers were independently
   # validated. Missing cash provenance blocks NEW exposure; it must not throw
   # away an otherwise valid actual-position close/reduce decision.
   reason=str(exc)if isinstance(exc,funds.FundingError)else type(exc).__name__
   self.cash_source_blocker='cashflow_reconciliation_required:'+reason
   return original
  return updated
 def read_execution_events(self,decision,now):
  evidence=self.config['broker'];rows=self._execution_rows()
  if not rows:return []
  policy=self._broker_policy(now)
  fills=broker.load_broker_fills(evidence['summary_path'],evidence['manifest_path'],rows,**policy)
  orders=broker.load_broker_order_updates(evidence['summary_path'],evidence['manifest_path'],rows,**policy)
  def events(raws,kind):
   result=[]
   for envelope in raws:
    raw=json.loads(envelope['raw_payload']);result.append(dict(kind=kind,envelope=envelope,signal_identity=raw.get('signal_identity')))
   return result
  return events(fills,'fill')+events(orders,'order')
 def _execution_rows(self):
  path=self.config.get('execution_ledger_path')
  if not path:raise LocalBackendError('weekly19_private_execution_ledger_required')
  return broker.load_execution_order_intent_bindings(Path(path),expected_account_key=self.config['account_key'],
   material_release_id=self.config['material_release_id'],execution_profile=PROFILE.profile_key)
 def complete_postclose(self,bundle,data,now):
  from qmt_roll_weekly19_daily_receipt import build_weekly19_daily_receipt,write_weekly19_daily_receipt
  if self.preview:return None
  gate=self.require_production();manifest=gate['manifest']
  receipt=build_weekly19_daily_receipt(bundle=bundle,data=data,source_commit=manifest['source_commit'],manifest_sha256=manifest['manifest_sha256'],generated_at=now)
  write_weekly19_daily_receipt(Path(self.config['daily_receipt_path']),receipt)
  return receipt
 def send_mail(self,report):
  self.require_production()
  if report.get('preview')or report['material_release_id']!=self.config['material_release_id']:raise LocalBackendError('weekly19_mail_identity_invalid')
  event={'weekly19.friday-report.v1':'weekly19_friday_signal_funding','weekly19.daily-risk-report.v1':'weekly19_daily_risk'}.get(report.get('schema'))
  if event is None:raise LocalBackendError('weekly19_mail_schema_invalid')
  from qmt_roll_official_live_email_notify import send_official_live_email_notification
  return send_official_live_email_notification(subject=report['subject'],body=report['body'],event_type=event,
   severity='warning'if report['blockers']else'info',metadata=dict(material_release_id=report['material_release_id'],report_sha256=report['report_sha256']),
   env_file=self.repo/'examples/portfolio_backtesting/official_live_email.local.env')
 def _refresh_cash_sources(self):
  from qmt_roll_weekly19_controller import assert_immutable_context,immutable_context_digest
  path=getattr(self,'context_file',None)
  if path is None:raise LocalBackendError('weekly19_session_private_context_file_required')
  if self._session_context_invalidated:raise LocalBackendError(self._session_context_invalidated)
  try:current=assert_immutable_context(path,immutable_context_digest(self.config))
  except Exception as exc:
   self._session_context_invalidated='weekly19_context_immutable_fields_changed:'+type(exc).__name__
   authority=getattr(self,'controller_authority',None)
   if authority is not None:authority.invalidate(self._session_context_invalidated)
   raise
  # These are unadmitted references. reconcile_cash still validates each raw
  # source and its capture authority; merely adding a path never credits cash.
  self.config['cash_sources']=deepcopy(current.get('cash_sources',{}))
 def prepare_session(self,target_date,now):
  """Read source/calendar/receipt evidence before any read-only connection."""
  self.require_production();self._refresh_cash_sources();self._session_args(target_date);self._execution_rows()
  from qmt_roll_weekly19_controller import load_weekly19_controller_authority
  from qmt_roll_weekly19_data import _hashes,_calendar
  market=self.config['market_data'];root=Path(market['asset_root']);_hashes(root,market['expected_hashes'])
  calendar,_=_calendar(market['forward_calendar'],[],target_date,market['expected_hashes'])
  self.controller_authority=load_weekly19_controller_authority(backend=self,daily_receipt_path=self.config['daily_receipt_path'],
   context_file=self.context_file,target_date=target_date,now=now)
  self.controller_authority.assert_current(now)
  return calendar
 def _session_args(self,target_date):
  from run_qmt_roll_stage931_official_live_ctp_submit_adapter import parse_args
  from qmt_roll_official_live_runtime_profile import resolve_runtime_profile
  from qmt_roll_official_live_phase_d_config import PHASE_D_CONFIRM_TEXT,STAGE179_ACTIVATION_CONFIRM_TEXT
  path=Path(self.config['execution_ledger_path'])
  if not path.is_absolute():raise LocalBackendError('weekly19_private_execution_ledger_required')
  runtime=resolve_runtime_profile(profile='production-live',order_scope='live',repo_root=self.repo,output_root=path.parent.parent)
  if path!=runtime.ledger_path or self.activation_receipt!=runtime.activation_receipt_path:
   raise LocalBackendError('weekly19_session_runtime_paths_mismatch')
  # Use the original parser and original serve gates. In particular no submit
  # environment flags, gateway factories or sender callbacks come from JSON.
  return parse_args(['--command','serve','--stage179-warm-executor','--mode','live-real',
   '--execution-profile',PROFILE.profile_key,'--runtime-profile','production-live','--order-scope','live',
   '--target-date',target_date,'--confirm-live-real',PHASE_D_CONFIRM_TEXT,
   '--stage179-release-manifest',str(self.release_manifest),'--stage179-activation-receipt',str(self.activation_receipt),
   '--stage179-runtime-root',str(runtime.output_root),'--confirm-stage179-activation',STAGE179_ACTIVATION_CONFIRM_TEXT])
 def _execution_result(self,result):
  result=dict(result)
  # The pure controller invokes zero APIs; the concurrently running original
  # executor can invoke real APIs. Do not mislabel its unknown count as zero.
  if 'order_api_called_count'in result:result['controller_publication_order_api_called_count']=result.pop('order_api_called_count')
  result.update(order_api_called_count=None,send_order_api_called_count=None,cancel_order_api_called_count=None,
   order_api_evidence_complete=False,production_qualified=False)
  return result
 def publish_execution(self,*,runtime,bundle,data,now):
  if self._session_owner_closed:raise LocalBackendError('weekly19_session_owner_closed')
  if self._service is not None:
   if self._service.runtime_actor is not runtime:raise LocalBackendError('weekly19_service_actor_replacement_forbidden')
   self._refresh_cash_sources();self.controller_authority.assert_current(now)
   return self._execution_result(self._service.publish(runtime=runtime,bundle=self._bridge.last_bundle,data=self._bridge.data,now=now))
  self.require_production()
  if bundle.get('runtime_mode')!='production':raise LocalBackendError('weekly19_session_production_bundle_required')
  from qmt_roll_weekly19_runtime import Runtime
  from qmt_roll_weekly19_pipeline_state import PipelineStateStore,digest
  from qmt_roll_weekly19_controller import load_weekly19_controller_authority
  from qmt_roll_weekly19_session_bridge import build_weekly19_session_service
  from qmt_roll_official_live_time import SystemClock
  self._refresh_cash_sources()
  if (not isinstance(runtime,Runtime)or runtime.account!=self.config['account_key']or runtime.release!=self.config['material_release_id']
   or runtime.export_state()['state_sha256']!=bundle.get('runtime',{}).get('state_sha256')):
   raise LocalBackendError('weekly19_session_actor_bundle_identity_mismatch')
  decision=bundle.get('decision')or{};target=decision.get('trading_date')
  if not target or target!=self.config['target_date']or target!=data['receipt']['trading_date']:
   raise LocalBackendError('weekly19_session_completed_target_mismatch')
  if self._market_cache is None or digest(self._market_cache['receipt'])!=digest(data['receipt']):
   raise LocalBackendError('weekly19_session_admitted_market_generation_required')
  store=PipelineStateStore(self.config['state_path'],runtime.account,runtime.release)
  if digest(store.read())!=digest(bundle):raise LocalBackendError('weekly19_session_durable_bundle_changed')
  self._execution_rows()  # Preserve the provider's typed private-ledger origin.
  authority=getattr(self,'controller_authority',None)
  if authority is None:
   authority=load_weekly19_controller_authority(backend=self,daily_receipt_path=self.config['daily_receipt_path'],
    context_file=self.context_file,target_date=target,now=now)
  authority.assert_current(now);self.controller_authority=authority
  args=self._session_args(target)
  service,bridge=build_weekly19_session_service(args,runtime_actor=runtime,bundle=bundle,data=data,authority=authority,
   state_store=store,clock=SystemClock(),private_root=Path(self.config['broker']['private_capture_dir'])/'execution-session',
   execution_ledger_path=Path(self.config['execution_ledger_path']),reconcile_cash=self.reconcile_cash,
   session_provider=self.session_provider,require_production_qualification=True)
  deadline=getattr(self,'session_deadline',None)
  if deadline is not None:
   if not isinstance(deadline,datetime)or deadline.tzinfo is None:raise LocalBackendError('weekly19_session_deadline_aware_required')
   service.bind_deadline(int(deadline.timestamp()*1_000_000_000))
  self._service=service;self._bridge=bridge
  # A source-qualified attempt may now reach the original run_serve connection
  # gates. Counts become unknown until actual native ingress proves them.
  self.external_action_started=True
  return self._execution_result(service.publish(runtime=runtime,bundle=bundle,data=data,now=now))
 def execution_session_cycle(self,*,target_date,now):
  if self._session_owner_closed:raise LocalBackendError('weekly19_session_owner_closed')
  if self._service is None:raise LocalBackendError('weekly19_session_owner_missing')
  self._refresh_cash_sources();self.controller_authority.assert_current(now)
  if target_date!=self.controller_authority.bindings['target_cutoff_date']:
   raise LocalBackendError('weekly19_session_new_market_generation_requires_new_owner')
  result=self.publish_execution(runtime=self._service.runtime_actor,bundle=self._bridge.last_bundle,data=self._bridge.data,now=now)
  from qmt_roll_weekly19_pipeline_state import digest
  with self._service.actor_lock:state_sha=digest(self._bridge.last_bundle)
  return dict(status='session_cycle',execution=result,state_sha256=state_sha,production_qualified=False)
 def close_session(self):
  if self._session_owner_closed or self._service is None:return dict(status='stopped',production_qualified=False)
  result=self._service.stop()
  if result.get('status')!='stopped':return result
  self._bridge.close();self._session_owner_closed=True
  return dict(status='stopped',production_qualified=False)
