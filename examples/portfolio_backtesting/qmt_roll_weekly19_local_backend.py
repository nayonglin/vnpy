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
from qmt_roll_official_execution_profile import WEEKLY19_15W_R150K_PROFILE as PROFILE
from qmt_roll_weekly19_pipeline_state import unique
import qmt_roll_weekly19_broker_evidence as broker
import qmt_roll_weekly19_funding as funds

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
  self._last_inputs=None;self._gate=None
 def require_production(self):
  if self.preview:raise LocalBackendError('preview_backend_cannot_be_production')
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
  self._gate=dict(manifest=manifest,qualification=evidence,identity=identity)
  return deepcopy(self._gate)
 def _broker_policy(self,now):
  policy=deepcopy(self.config['broker']['policy'])
  # These identities are not configurable aliases.
  for key in ('expected_account_key','material_release_id','execution_profile','now','require_production_qualification'):
   if key in policy:raise LocalBackendError('weekly19_broker_policy_identity_override')
  policy.update(expected_account_key=self.config['account_key'],material_release_id=self.config['material_release_id'],
   execution_profile=PROFILE.profile_key,now=now,require_production_qualification=not self.preview)
  return policy
 def load_inputs(self,target_date,now):
  if not self.preview:self.require_production()
  from qmt_roll_weekly19_data import load_weekly19_inputs
  market=self.config['market_data'];data=load_weekly19_inputs(Path(market['asset_root']),material_release_id=self.config['material_release_id'],
   target_date=target_date,forward_calendar=market['forward_calendar'],expected_hashes=market['expected_hashes'])
  evidence=self.config['broker'];snapshot=broker.load_broker_snapshot(evidence['summary_path'],evidence['manifest_path'],**self._broker_policy(now))
  data['broker_snapshot']=snapshot;self._last_inputs=data;return data
 def validate_initial_account(self,snapshot,now):
  self.require_production()
  account=broker.read_account_snapshot(snapshot['account'],expected_account_key=self.config['account_key'],material_release_id=self.config['material_release_id'],now=now)
  positions=funds._parse(snapshot['positions'],'weekly19.ctp-positions.v1','ctp_position_query')['positions']
  orders=funds._parse(snapshot['orders'],'weekly19.ctp-orders.v1','ctp_order_query')['orders']
  if account['equity_fen']!=funds.INITIAL_FEN or positions or any(r['status']not in {'filled','cancelled','rejected'}for r in orders):raise LocalBackendError('weekly19_initial_real_150k_flat_account_required')
 def reconcile_cash(self,state,snapshot,now):
  updated=deepcopy(state);sources=self.config.get('cash_sources',{})
  current=funds._broker(snapshot['account'],updated,now);checkpoint=updated['cashflow_checkpoint']
  if checkpoint is not None and checkpoint['trading_day']!=current['trading_day']:
   # Missing genuine final statement is a distinct source prerequisite. A later
   # balance or a completed intraday query cannot prove final daily cash flows.
   row=sources.get('day_close')
   if row is None:raise LocalBackendError('accepted_cashflow_source_missing:final_broker_day_close_statement')
   proof=broker.load_cashflow_day_close(private_json(row['statement_path']),state=updated,now=now)
   updated=funds.reconcile_trading_day(updated,private_json(row['closing_account_path']),snapshot['account'],now,continuity_receipt=proof)
  for row in sources.get('deposits',[]):
   proof=broker.load_bank_cashflow_receipt(private_json(row['raw_source_path']),state=updated,request_id=row['request_id'],bank_serial=row['bank_serial'],now=now,
    require_production_qualification=not self.preview)
   updated=funds.confirm_topup(updated,row['request_id'],proof,snapshot['account'],now)
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
  if not path:return []
  # Use the existing execution-ledger verifier, not arbitrary caller rows.
  from qmt_roll_official_live_execution_ledger import read_execution_ledger
  rows=read_execution_ledger(Path(path))
  if any(str(r.get("event_type", "")).startswith("ledger_")and str(r.get("event_type", "")).endswith("_error")for r in rows):raise LocalBackendError("weekly19_execution_ledger_invalid")
  return rows
 def send_mail(self,report):
  self.require_production()
  if report.get('preview')or report['material_release_id']!=self.config['material_release_id']:raise LocalBackendError('weekly19_mail_identity_invalid')
  from qmt_roll_official_live_email_notify import send_official_live_email_notification
  return send_official_live_email_notification(subject=report['subject'],body=report['body'],event_type='weekly19_friday_signal_funding',
   severity='warning'if report['blockers']else'info',metadata=dict(material_release_id=report['material_release_id'],report_sha256=report['report_sha256']),
   env_file=self.repo/'examples/portfolio_backtesting/official_live_email.local.env')
 def publish_execution(self,**_kwargs):
  self.require_production()
  raise LocalBackendError('weekly19_session_controller_binding_not_installed')
