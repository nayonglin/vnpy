"""Private operator attestations. No CTP, bank, SMTP or order connection APIs.

An immutable file and a reference are NOT cash credit. The existing runtime
actor consumes the verified record and commits funds/runtime together.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime,timedelta
import fcntl,getpass,hashlib,json,os,stat,uuid
from pathlib import Path
import qmt_roll_weekly19_funding as funds

MODE='operator_manual_v1'
def _now():return datetime.now(funds.SHANGHAI)
class ManualCashError(ValueError):pass
class ManualReferenceConflict(ManualCashError):pass

def _require(value,reason):
 if not value:raise ManualCashError(reason)

def assert_manual_mode(backend):
 from qmt_roll_weekly19_official_config import EXECUTION_POLICY
 from qmt_roll_weekly19_local_backend import LocalEvidenceBackend
 _require(isinstance(backend,LocalEvidenceBackend),'manual_cash_real_local_backend_required')
 _require(not backend.preview,'manual_cash_preview_cannot_publish')
 _require(EXECUTION_POLICY.get('cash_verification_mode')==MODE and backend.config.get('cash_verification_mode')==MODE,
  'manual_cash_immutable_policy_mode_mismatch')

@contextmanager
def _parent(path):
 path=Path(path)
 _require(path.is_absolute()and '..'not in path.parts,'manual_cash_absolute_private_path_required')
 directory=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
 try:
  for part in path.parts[1:-1]:
   child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory);os.close(directory);directory=child
  info=os.fstat(directory)
  _require(info.st_uid==os.geteuid()and stat.S_IMODE(info.st_mode)==0o700,'manual_cash_private_parent_required')
  yield directory
 finally:os.close(directory)

def _private(fd):
 info=os.fstat(fd)
 _require(stat.S_ISREG(info.st_mode)and info.st_uid==os.geteuid()and info.st_nlink==1 and stat.S_IMODE(info.st_mode)==0o600,
  'manual_cash_private_regular_file_required')

def _read(directory,name):
 fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=directory)
 with os.fdopen(fd,'rb')as stream:
  _private(stream.fileno());raw=stream.read(1_000_001)
 _require(len(raw)<=1_000_000,'manual_cash_record_oversized')
 return raw

def _reference_shape(reference):
 _require(isinstance(reference,dict)and set(reference)=={'path','sha256'},'manual_cash_reference_fields_invalid')
 _require(isinstance(reference['path'],str)and bool(reference['path'])and len(reference['path'])<=4096,'manual_cash_reference_path_invalid')
 funds._sha(reference['sha256'])

def load_private_manual_review(reference):
 _reference_shape(reference)
 path=Path(reference['path'])
 from qmt_roll_weekly19_context_update import _assert_visible_parent
 with _parent(path)as directory:
  _assert_visible_parent(path,directory);raw=_read(directory,path.name);_assert_visible_parent(path,directory)
 _require(hashlib.sha256(raw).hexdigest()==funds._sha(reference['sha256']),'manual_cash_record_sha_mismatch')
 result=dict(raw_payload=raw.decode('utf-8'),raw_sha256=reference['sha256'])
 raw=funds._parse(result,'weekly19.operator-cash-review.v1','operator_manual')
 funds._text(raw.get('record_id'),'record_id')
 return result

def _record_path(backend,record_id):
 root=Path(backend.config['manual_cash_review_root'])
 _require(root.is_absolute()and not root.is_relative_to(backend.repo),'manual_cash_records_must_be_outside_checkout')
 return root/('operator-cash-'+funds._hash([backend.config['account_key'],backend.config['material_release_id'],record_id])+'.json')

def _freeze(path,raw):
 from qmt_roll_weekly19_context_update import _assert_visible_parent
 with _parent(path)as directory:
  _assert_visible_parent(path,directory)
  try:
   existing=_read(directory,path.name)
  except FileNotFoundError:existing=None
  if existing is not None:
   _require(existing==raw,'manual_cash_record_id_content_conflict');os.fsync(directory);_assert_visible_parent(path,directory);return
  name='.'+path.name+'.'+uuid.uuid4().hex+'.pending'
  fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory)
  try:
   with os.fdopen(fd,'wb')as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
   _assert_visible_parent(path,directory)
   try:os.link(name,path.name,src_dir_fd=directory,dst_dir_fd=directory,follow_symlinks=False)
   except FileExistsError:_require(_read(directory,path.name)==raw,'manual_cash_record_id_content_conflict')
  finally:
   os.unlink(name,dir_fd=directory)
  os.fsync(directory);_assert_visible_parent(path,directory)

def _append_reference(context_file,expected,reference):
 from qmt_roll_weekly19_controller import immutable_context_digest
 from qmt_roll_weekly19_context_update import _assert_visible_parent
 from qmt_roll_weekly19_pipeline_state import unique
 path=Path(context_file)
 with _parent(path)as directory:
  name='.'+path.name+'.lock'
  for _ in range(8):
   try:lock=os.open(name,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory)
   except FileExistsError:
    try:lock=os.open(name,os.O_RDWR|os.O_NOFOLLOW,dir_fd=directory)
    except FileNotFoundError:continue
   break
  else:raise ManualCashError('manual_cash_context_lock_race')
  try:
   _private(lock);fcntl.flock(lock,fcntl.LOCK_EX);_assert_visible_parent(path,directory)
   current=json.loads(_read(directory,path.name),object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in()).throw(ManualCashError('manual_cash_nonfinite_context')))
   if immutable_context_digest(current)!=immutable_context_digest(expected):raise ManualReferenceConflict('manual_cash_context_immutable_fields_changed')
   sources=current.setdefault('cash_sources',{});_require(isinstance(sources,dict),'manual_cash_sources_object_required')
   references=sources.setdefault('manual_reviews',[])
   _require(isinstance(references,list),'manual_cash_reference_list_required')
   for item in references:_reference_shape(item)
   load_private_manual_review(reference)
   if reference in references:
    # A previous replace may be visible despite a failed directory fsync.
    # Retry that exact durability barrier before reporting publication success.
    os.fsync(directory);_assert_visible_parent(path,directory);load_private_manual_review(reference)
    return
   _require(not any(row.get('path')==reference['path']for row in references),'manual_cash_reference_path_conflict')
   references.append(deepcopy(reference));payload=funds._canonical(current)
   temp='.'+path.name+'.'+uuid.uuid4().hex+'.pending'
   fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory)
   try:
    with os.fdopen(fd,'wb')as stream:stream.write(payload);stream.flush();os.fsync(stream.fileno())
    _assert_visible_parent(path,directory);os.replace(temp,path.name,src_dir_fd=directory,dst_dir_fd=directory);os.fsync(directory);_assert_visible_parent(path,directory)
    load_private_manual_review(reference)
   finally:
    try:os.unlink(temp,dir_fd=directory)
    except FileNotFoundError:pass
  finally:os.close(lock)

def _calendar(backend):
 if backend._market_cache is not None:return backend._market_cache['calendar']
 from qmt_roll_weekly19_data import _hashes,_calendar
 market=backend.config['market_data'];_hashes(Path(market['asset_root']),market['expected_hashes'])
 return _calendar(market['forward_calendar'],[],backend.config['target_date'],market['expected_hashes'])[0]

def _live_inputs(backend,now):
 from qmt_roll_weekly19_pipeline_state import PipelineStateStore
 import qmt_roll_weekly19_broker_evidence as broker
 assert_manual_mode(backend);backend.require_production()
 backend._refresh_cash_sources()
 bundle=PipelineStateStore(backend.config['state_path'],backend.config['account_key'],backend.config['material_release_id']).read()
 _require(bundle is not None and bundle.get('runtime_mode')=='production','manual_cash_production_pipeline_state_required')
 evidence=backend.config['broker']
 snapshot=broker.load_broker_snapshot(evidence['summary_path'],evidence['manifest_path'],**backend._broker_policy(now))
 _require(snapshot.get('source_qualified')is True,'manual_cash_fresh_ctp_source_not_admitted')
 return bundle['funding'],snapshot,_calendar(backend)

def manual_cash_status(backend,*,now):
 assert_manual_mode(backend);state,snapshot,_=_live_inputs(backend,now)
 current=funds._broker(snapshot['account'],state,now)
 reason=None
 try:funds._cashflow_match(state,current)
 except funds.FundingError as exc:reason=str(exc)
 if state['cashflow_checkpoint']is None:reason='initial_real_cash_observation_required'
 return dict(status='manual_cash_review_pending'if reason else'manual_cash_counters_reconciled',
  source_kind='operator_manual',cash_verification_mode=MODE,account_key=state['account_key'],material_release_id=state['material_release_id'],
  funding_revision=state['revision'],current_trading_day=current['trading_day'],
  checkpoint_trading_day=(state['cashflow_checkpoint']or{}).get('trading_day'),
  reserve_remaining_fen=state['reserve_remaining_fen'],confirmed_topup_fen=state['confirmed_topup_fen'],
  pending_reason=reason,requests=[{key:row[key]for key in('request_id','amount_fen','confirmed_fen','status','expires_at')}for row in state['requests'].values()],
  production_qualified=False,broker_automatically_verified=False,funding_consumed=False)

def prepare_operator_review(backend,review_input,*,operator_id,review_id,now):
 assert_manual_mode(backend)
 _require(isinstance(review_input,dict)and set(review_input)=={'topups','closed_days','expected_reserve_remaining_fen','notes'},'manual_cash_review_input_fields_invalid')
 _require(isinstance(review_input['topups'],list)and len(review_input['topups'])<=1000
  and isinstance(review_input['closed_days'],list)and len(review_input['closed_days'])<=1000,'manual_cash_review_input_lists_invalid')
 funds._text(review_input['notes'],'notes');funds._text(operator_id,'operator_id');funds._text(review_id,'review_id')
 _require(funds._integer(review_input['expected_reserve_remaining_fen'])<=funds.INITIAL_FEN,'manual_cash_offsite_reserve_invalid')
 for row in review_input['topups']:
  _require(isinstance(row,dict)and set(row)=={'request_id','receipt_id','amount_fen','occurred_at','trading_day'},'manual_cash_topup_input_fields_invalid')
  funds._sha(row['request_id']);funds._text(row['receipt_id'],'receipt_id');funds._time(row['occurred_at']);funds._day(row['trading_day'])
  _require(funds._integer(row['amount_fen'],1)<=funds.INITIAL_FEN,'manual_cash_topup_amount_invalid')
 for row in review_input['closed_days']:
  _require(isinstance(row,dict)and set(row)=={'trading_day','final_deposit_fen','final_withdraw_fen','closed_at','statement_reference','cashflows_complete'},'manual_cash_closed_day_input_fields_invalid')
  funds._day(row['trading_day']);funds._integer(row['final_deposit_fen']);funds._integer(row['final_withdraw_fen'])
  funds._time(row['closed_at']);funds._text(row['statement_reference'],'statement_reference')
  _require(row['cashflows_complete']is True,'manual_cash_closed_day_incomplete')
 state,snapshot,calendar=_live_inputs(backend,now);now=funds._time(now)
 input_sha=funds._hash(review_input);path=_record_path(backend,funds._text(review_id,'review_id'))
 try:
  with _parent(path)as directory:existing=_read(directory,path.name)
 except FileNotFoundError:existing=None
 if existing is not None:
  envelope=dict(raw_payload=existing.decode('utf-8'),raw_sha256=hashlib.sha256(existing).hexdigest())
  raw=funds._parse(envelope,'weekly19.operator-cash-review.v1','operator_manual')
  _require(raw['record_id']==review_id and raw['operator_id']==operator_id and raw.get('operator_input_sha256')==input_sha,'manual_cash_review_id_content_conflict')
  funds.apply_operator_cash_review(state,envelope,snapshot['account'],now,trading_calendar=calendar)
  return envelope
 raw=dict(schema='weekly19.operator-cash-review.v1',source_kind='operator_manual',record_id=review_id,operator_id=funds._text(operator_id,'operator_id'),
  os_uid=os.geteuid(),os_user=getpass.getuser(),assertion=funds.OPERATOR_CASH_ASSERTION,notes=review_input['notes'],created_at=now.isoformat(),
  expires_at=(now+timedelta(seconds=funds.OPERATOR_REVIEW_SECONDS)).isoformat(),account_key=state['account_key'],material_release_id=state['material_release_id'],
  before_funding_revision=state['revision'],before_funding_sha256=funds._hash(state),before_checkpoint=deepcopy(state['cashflow_checkpoint']),
  before_checkpoint_sha256=funds._hash(state['cashflow_checkpoint']),reserve_remaining_fen_before=state['reserve_remaining_fen'],confirmed_topup_fen_before=state['confirmed_topup_fen'],
  reviewed_account=deepcopy(snapshot['account']),topups=[],closed_days=deepcopy(review_input['closed_days']),
  expected_reserve_remaining_fen=review_input['expected_reserve_remaining_fen'],no_unlisted_cashflows=True,broker_automatically_verified=False,production_qualified=False,
  operator_input_sha256=input_sha)
 for row in review_input['topups']:
  _require(isinstance(row,dict)and set(row)=={'request_id','receipt_id','amount_fen','occurred_at','trading_day'},'manual_cash_topup_input_fields_invalid')
  request=state['requests'].get(row['request_id']);_require(request is not None,'manual_cash_original_request_unknown')
  raw['topups'].append(dict(row,**{key:deepcopy(request[key])for key in('admitted_entry_ids','target_week_end','source_sha256')}))
 payload=funds._canonical(raw).decode('utf-8');envelope=dict(raw_payload=payload,raw_sha256=hashlib.sha256(payload.encode()).hexdigest())
 funds.apply_operator_cash_review(state,envelope,snapshot['account'],now,trading_calendar=calendar)
 return envelope

def write_and_publish_operator_review(backend,envelope):
 assert_manual_mode(backend)
 raw=funds._parse(envelope,'weekly19.operator-cash-review.v1','operator_manual')
 now=_now();state,snapshot,calendar=_live_inputs(backend,now)
 # A source/race failure writes no reference. The actor revalidates the exact
 # before-state again when consuming; this command never mutates that state.
 funds.apply_operator_cash_review(state,envelope,snapshot['account'],now,trading_calendar=calendar)
 path=_record_path(backend,raw['record_id']);_freeze(path,envelope['raw_payload'].encode('utf-8'))
 reference=dict(path=str(path),sha256=envelope['raw_sha256'])
 result=dict(status='record_written_pending_actor_consumption',reference=reference,reference_published=True,funding_consumed=False,
  consumption_status='not_confirmed_by_this_command',source_kind='operator_manual',broker_automatically_verified=False,production_qualified=False)
 try:_append_reference(backend.context_file,backend.config,reference)
 except ManualCashError:
  result.update(status='record_written_reference_not_published',reference_published=False,pending_reason='manual_cash_context_changed_retry_original_record')
 except (OSError,ValueError):
  result.update(status='record_written_reference_publication_unconfirmed',reference_published=None,pending_reason='manual_cash_reference_durability_unconfirmed')
 return result
