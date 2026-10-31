"""Atomic private bundle for runtime, confirmed cash and source-bound decision.

Persist before making an email/spool side effect. The checksum detects corruption;
this local store never attests a broker origin or production qualification.
"""
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import uuid
import qmt_roll_weekly19_funding as funds
from qmt_roll_weekly19_funding_store import FundingStore

MAX_STATE_BYTES=64_000_000
class PipelineStateError(ValueError):pass

def canonical(value):
 return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def unique(pairs):
 out={}
 for key,value in pairs:
  if key in out:raise PipelineStateError('pipeline_duplicate_key')
  out[key]=value
 return out

class PipelineStateStore:
 def __init__(self,path,account_key,material_release_id):
  self.path=Path(path);self.account=account_key;self.release=material_release_id
  if not self.path.is_absolute()or '..'in self.path.parts or self.path.name in ('','.','..'):raise PipelineStateError('pipeline_absolute_path_required')
  funds._sha(account_key)
  if not material_release_id:raise PipelineStateError('pipeline_release_required')
 @staticmethod
 def _file(fd):
  st=os.fstat(fd)
  if not stat.S_ISREG(st.st_mode)or st.st_uid!=os.geteuid()or st.st_nlink!=1 or stat.S_IMODE(st.st_mode)!=0o600:raise PipelineStateError('pipeline_private_file_required')
 @contextmanager
 def _locked(self):
  directory=None;lock=None
  try:
   directory=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
   for part in self.path.parent.parts[1:]:
    child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory);os.close(directory);directory=child
   st=os.fstat(directory)
   if st.st_uid!=os.geteuid()or stat.S_IMODE(st.st_mode)!=0o700:raise PipelineStateError('pipeline_private_directory_required')
   for _ in range(8):
    try:lock=os.open(self.path.name+'.lock',os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory);break
    except FileExistsError:
     try:lock=os.open(self.path.name+'.lock',os.O_RDWR|os.O_NOFOLLOW,dir_fd=directory);break
     except FileNotFoundError:continue
    except FileNotFoundError:continue
   if lock is None:raise PipelineStateError('pipeline_lock_race_exhausted')
   self._file(lock);fcntl.flock(lock,fcntl.LOCK_EX);yield directory
  finally:
   if lock is not None:os.close(lock)
   if directory is not None:os.close(directory)
 def _validate(self,value):
  if (not isinstance(value,dict)or value.get('schema')!='weekly19.pipeline-state.v1'
   or value.get('account_key')!=self.account or value.get('material_release_id')!=self.release
   or type(value.get('revision'))is not int or value['revision']<0):raise PipelineStateError('pipeline_state_identity_invalid')
  if value.get('runtime_mode','preview')not in {'preview','production'}:raise PipelineStateError('pipeline_runtime_mode_invalid')
  f=value['funding'];funds.validate_state(f)
  if f['account_key']!=self.account or f['material_release_id']!=self.release:raise PipelineStateError('pipeline_cash_identity_invalid')
  rt=value.get('runtime');origin=value.get('decision_state');decision=value.get('decision')
  decoded=self._runtime_state(rt,f)if rt is not None else None
  if decision is None:
   if origin is not None:raise PipelineStateError('pipeline_orphan_decision_state')
  else:
   if rt is None or origin is None:raise PipelineStateError('pipeline_decision_origin_required')
   from qmt_roll_weekly19_runtime import _decode
   origin_cash=_decode(origin.get('runtime',{})).get('confirmed_cash_state')
   original=self._runtime_state(origin,origin_cash)
   if not FundingStore._same_identity(origin_cash,f):raise PipelineStateError('pipeline_funding_identity_change')
   if origin_cash['revision']>f['revision']:raise PipelineStateError('pipeline_origin_cash_revision_future')
   FundingStore._forward_ledger(origin_cash,f)
   if (not isinstance(decision,dict)or decision.get('schema')!='weekly19.runtime-decision.v1'
    or decision.get('account_fingerprint')!=self.account or decision.get('material_release_id')!=self.release
    or decision.get('after_state_sha256')!=origin.get('state_sha256')
    or decision.get('confirmed_cash_state')!=origin_cash
    or decision.get('data_receipt_sha256')!=original.get('current_receipt_hash')
    or original.get('days',{}).get(decision.get('trading_date'),{}).get('decision')!=decision
    or origin['revision']>rt['revision']):raise PipelineStateError('pipeline_decision_binding_invalid')
 def _runtime_state(self,rt,cash):
  from qmt_roll_weekly19_runtime import _state_digest,_decode
  if (not isinstance(rt,dict)or rt.get('schema')!='weekly19.runtime-state.v1'
   or rt.get('account_key')!=self.account or rt.get('material_release_id')!=self.release
   or rt.get('production_qualified')is not False
   or rt.get('state_sha256')!=_state_digest({k:v for k,v in rt.items()if k!='state_sha256'})):
   raise PipelineStateError('pipeline_runtime_identity_or_digest_invalid')
  decoded=_decode(rt.get('runtime',{}));funds.validate_state(cash)
  if (decoded.get('confirmed_cash_state')!=cash or decoded.get('revision')!=rt.get('revision')
   or decoded.get('position_identities')!=rt.get('position_identities')
   or type(rt.get('revision'))is not int or rt['revision']<0):raise PipelineStateError('pipeline_runtime_cash_or_revision_invalid')
  return decoded

 def _read(self,directory):
  try:fd=os.open(self.path.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=directory)
  except FileNotFoundError:return None
  with os.fdopen(fd,'rb')as f:
   self._file(f.fileno());raw=f.read(MAX_STATE_BYTES+1)
  if len(raw)>MAX_STATE_BYTES:raise PipelineStateError('pipeline_state_oversized')
  try:
   rec=json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in()).throw(PipelineStateError('pipeline_nonfinite_json')))
   if rec['schema']!='weekly19.pipeline-store.v1'or rec['state_sha256']!=digest(rec['state']):raise PipelineStateError('pipeline_checksum_invalid')
   self._validate(rec['state']);return rec['state']
  except (KeyError,TypeError,UnicodeError,json.JSONDecodeError)as e:raise PipelineStateError('pipeline_state_invalid')from e
 def _write(self,directory,value):
  self._validate(value);temp='.'+uuid.uuid4().hex+'.tmp'
  payload=canonical(dict(schema='weekly19.pipeline-store.v1',state_sha256=digest(value),state=value))
  if len(payload)>MAX_STATE_BYTES:raise PipelineStateError('pipeline_state_oversized')
  fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory)
  try:
   with os.fdopen(fd,'wb')as f:f.write(payload);f.flush();os.fsync(f.fileno())
   os.replace(temp,self.path.name,src_dir_fd=directory,dst_dir_fd=directory);os.fsync(directory)
  finally:
   try:os.unlink(temp,dir_fd=directory)
   except FileNotFoundError:pass
 def read(self):
  with self._locked()as directory:return deepcopy(self._read(directory))
 def initialize(self,value):
  with self._locked()as directory:
   if self._read(directory)is not None:raise PipelineStateError('pipeline_state_exists')
   if value.get('revision')!=0:raise PipelineStateError('pipeline_initial_revision_required')
   self._write(directory,value);return deepcopy(value)
 def transact(self,transform):
  with self._locked()as directory:
   current=self._read(directory)
   if current is None:raise PipelineStateError('pipeline_initialization_required')
   following=transform(deepcopy(current));self._validate(following)
   if following==current:return deepcopy(current)
   if following.get('runtime_mode','preview')!=current.get('runtime_mode','preview'):raise PipelineStateError('pipeline_runtime_mode_immutable')
   if following['revision']!=current['revision']:raise PipelineStateError('pipeline_revision_owned_by_store')
   if not FundingStore._same_identity(current['funding'],following['funding']):raise PipelineStateError('pipeline_funding_identity_change')
   FundingStore._forward_ledger(current['funding'],following['funding'])
   if following['funding']['revision']<current['funding']['revision']or (following['funding']!=current['funding']and following['funding']['revision']==current['funding']['revision']):raise PipelineStateError('pipeline_funding_revision_rollback')
   following=deepcopy(following);following['revision']+=1;self._write(directory,following);return deepcopy(following)
