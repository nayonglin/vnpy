"""Private market-generation pointer CAS; never changes strategy material or cash."""
from copy import deepcopy
import fcntl,hashlib,json,os,stat,uuid
from pathlib import Path

class ContextUpdateError(ValueError):pass

def _canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def _require(value,reason):
 if not value:raise ContextUpdateError(reason)

def _assert_visible_parent(path,pinned):
 visible=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
 try:
  for part in path.parts[1:-1]:
   child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=visible);os.close(visible);visible=child
  a=os.fstat(visible);b=os.fstat(pinned)
  _require((a.st_dev,a.st_ino)==(b.st_dev,b.st_ino),'weekly19_context_parent_identity_changed')
 finally:os.close(visible)

def advance_market_context(path,*,expected,new_market,target_date):
 from qmt_roll_weekly19_pipeline_state import unique
 path=Path(path)
 _require(path.is_absolute()and '..'not in path.parts,'weekly19_context_absolute_path_required')
 directory=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
 try:
  for part in path.parts[1:-1]:
   child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory);os.close(directory);directory=child
  info=os.fstat(directory)
  _require(info.st_uid==os.geteuid()and stat.S_IMODE(info.st_mode)==0o700,'weekly19_context_private_parent_required')
  lock_name='.'+path.name+'.lock'
  for _ in range(8):
   try:fd=os.open(lock_name,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory)
   except FileExistsError:
    try:fd=os.open(lock_name,os.O_RDWR|os.O_NOFOLLOW,dir_fd=directory)
    except FileNotFoundError:continue
   break
  else:raise ContextUpdateError('weekly19_context_lock_creation_race')
  try:
   info=os.fstat(fd)
   _require(stat.S_ISREG(info.st_mode)and info.st_uid==os.geteuid()and info.st_nlink==1 and stat.S_IMODE(info.st_mode)==0o600,'weekly19_context_private_lock_required')
   fcntl.flock(fd,fcntl.LOCK_EX)
   _assert_visible_parent(path,directory)
   current_fd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=directory)
   with os.fdopen(current_fd,'rb')as stream:
    info=os.fstat(stream.fileno())
    _require(stat.S_ISREG(info.st_mode)and info.st_uid==os.geteuid()and info.st_nlink==1 and stat.S_IMODE(info.st_mode)==0o600,'weekly19_context_private_file_required')
    contents=stream.read(64_000_001)
   _require(len(contents)<=64_000_000,'weekly19_context_oversized')
   current=json.loads(contents,object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in()).throw(ContextUpdateError('weekly19_context_nonfinite')))
   _assert_visible_parent(path,directory)
   for key in ('schema','execution_profile','account_key','material_release_id','cold_start_date','state_path'):
    _require(current.get(key)==expected.get(key),'weekly19_context_identity_changed:'+key)
   _require(current.get('market_data')==expected.get('market_data'),'weekly19_context_market_generation_changed')
   _require(not current.get('target_date')or current['target_date']<=target_date,'weekly19_context_target_rollback')
   updated=deepcopy(current);updated['market_data']=deepcopy(new_market);updated['target_date']=target_date
   raw=_canonical(updated);_require(len(raw)<=64_000_000,'weekly19_context_oversized')
   name='.'+path.name+'.'+uuid.uuid4().hex+'.pending';written=False
   try:
    temp=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory)
    with os.fdopen(temp,'wb')as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    # The directory FD pins the checked private parent through replacement.
    _assert_visible_parent(path,directory)
    os.replace(name,path.name,src_dir_fd=directory,dst_dir_fd=directory);written=True;os.fsync(directory)
    _assert_visible_parent(path,directory)
   finally:
    if not written:
     try:os.unlink(name,dir_fd=directory)
     except FileNotFoundError:pass
   return updated
  finally:os.close(fd)
 finally:os.close(directory)

def refresh_market_data(backend,target_date,now):
 """Update only after a real broker-held set and an immutable base are admitted."""
 from qmt_roll_weekly19_data import _hashes,_day
 from qmt_roll_weekly19_data_update import update_weekly19_assets,TqReadOnlyBackend
 import qmt_roll_weekly19_broker_evidence as broker
 import qmt_roll_weekly19_funding as funds
 backend.require_production()
 _require(not backend.preview,'preview_market_update_forbidden')
 market=deepcopy(backend.config['market_data']);root=Path(market['asset_root'])
 # Verify all five base pins before trusting its cutoff or opening a market feed.
 _hashes(root,market['expected_hashes'])
 receipt=json.loads((root/'receipt.json').read_text())
 end=_day(receipt['date_end']);target=_day(target_date)
 if target<=end:return dict(status='already_covered',target_date=target,asset_cutoff=end,market_order_calls=0)
 _require(getattr(backend,'context_file',None)is not None,'weekly19_private_context_path_required')
 evidence=backend.config['broker']
 snapshot=broker.load_broker_snapshot(evidence['summary_path'],evidence['manifest_path'],**backend._broker_policy(now))
 # The provider has checked complete same-generation raw queries. Never pass an
 # assumed-flat set, and never interpret the configured portfolio as real held.
 positions=funds._parse(snapshot['positions'],'weekly19.ctp-positions.v1','ctp_position_query')['positions']
 held=sorted({row['vt_symbol']for row in positions if row['volume']>0})
 backend.external_action_started=True
 result=update_weekly19_assets(root,backend.config['market_generation_root'],material_release_id=backend.config['material_release_id'],
  target_date=target,held_contracts=held,expected_hashes=market['expected_hashes'],backend=TqReadOnlyBackend(),now=now)
 _require(result['target_date']==target and result.get('market_order_calls')==0,'weekly19_market_update_result_invalid')
 new_market=dict(market,asset_root=result['asset_root'],expected_hashes=result['source_hashes'],
  forward_calendar=str(Path(result['asset_root'])/'forward_calendar.csv'))
 updated=advance_market_context(backend.context_file,expected=backend.config,new_market=new_market,target_date=target)
 backend.config=updated;backend._market_cache=None;backend._market_cache_key=None;backend._market_cache_stats=None
 return dict(status='generation_advanced',target_date=target,source_manifest_sha256=result['source_manifest_sha256'],
  source_hashes=result['source_hashes'],market_order_calls=0,production_qualified=False)

def resolve_completed_target(backend,now):
 """Resolve from an explicitly pinned forward calendar, never weekdays alone."""
 from datetime import datetime,date
 from zoneinfo import ZoneInfo
 from qmt_roll_weekly19_data import _hashes,_sha,_day
 import pandas as pd
 _require(isinstance(now,datetime)and now.tzinfo is not None,'weekly19_target_aware_clock_required')
 market=backend.config['market_data'];root=Path(market['asset_root']);_hashes(root,market['expected_hashes'])
 value=market['forward_calendar']
 if isinstance(value,(str,Path)):
  path=Path(value)
  _require(path.is_absolute()and not path.is_symlink(),'weekly19_target_calendar_absolute_regular_required')
  expected=market['expected_hashes'].get('forward_calendar')or market['expected_hashes'].get(path.name)
  _require(expected is not None and _sha(path)==expected,'weekly19_target_calendar_sha_mismatch')
  frame=pd.read_csv(path,dtype=str);_require('date'in frame,'weekly19_target_calendar_date_required');days=frame.date.tolist()
 else:
  _require(isinstance(value,list),'weekly19_target_calendar_required');days=value
 days=[_day(day)for day in days];_require(len(days)==len(set(days)),'weekly19_target_calendar_duplicate')
 at=now.astimezone(ZoneInfo('Asia/Shanghai'));today=at.date().isoformat()
 _require(any(day>today for day in days),'weekly19_target_forward_calendar_coverage_expired')
 available=[day for day in days if day<today or day==today and (at.hour,at.minute)>=(15,0)]
 _require(bool(available),'weekly19_target_completed_calendar_day_missing')
 return max(available)
