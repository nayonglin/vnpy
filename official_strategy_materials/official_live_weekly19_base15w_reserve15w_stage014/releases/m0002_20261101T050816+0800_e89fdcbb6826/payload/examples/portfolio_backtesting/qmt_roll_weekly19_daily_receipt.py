"""Daily immutable-source / mutable-market receipt for the fixed19 route.

No C9 AI eligibility, old shadow CSV or intraday detector is a dependency.
The source-bound decision snapshot is stable after later real fills.
"""
from datetime import datetime,timezone
import fcntl,hashlib,json,os
from pathlib import Path
from qmt_roll_official_execution_profile import WEEKLY19_15W_R150K_PROFILE as PROFILE
from qmt_roll_weekly19_pipeline_state import digest,PipelineStateStore
from qmt_roll_weekly19_friday_report import FridayMailOutbox

class Weekly19DailyReceiptError(ValueError):pass

def build_weekly19_daily_receipt(*,bundle,data,source_commit,manifest_sha256,generated_at):
 from qmt_roll_weekly19_funding import _sha,_time
 _sha(manifest_sha256);at=_time(generated_at)
 if len(source_commit)!=40 or any(c not in '0123456789abcdef'for c in source_commit):raise Weekly19DailyReceiptError('weekly19_receipt_source_commit_invalid')
 decision=bundle.get('decision');origin=bundle.get('decision_state');inner=data['receipt']
 if not decision or not origin:raise Weekly19DailyReceiptError('weekly19_receipt_decision_missing')
 target=decision['trading_date'];calendar=data['calendar'];following=next((d for d in sorted(set(calendar))if d>target),None)
 if (inner.get('schema')!='weekly19.data-receipt.v1'or inner.get('complete')is not True
  or inner.get('trading_date')!=target or inner.get('material_release_id')!=bundle['material_release_id']
  or decision.get('data_receipt_sha256')!=digest(inner)or decision.get('after_state_sha256')!=origin.get('state_sha256')
  or not following):raise Weekly19DailyReceiptError('weekly19_receipt_market_or_origin_mismatch')
 body=dict(schema='weekly19.production-daily-data-receipt.v1',execution_profile=PROFILE.profile_key,
  official_version=PROFILE.official_version,ruleset_version=PROFILE.ruleset_version,
  material_release_id=bundle['material_release_id'],account_key=bundle['account_key'],source_commit=source_commit,
  manifest_sha256=manifest_sha256,target_cutoff_date=target,generated_at_utc=at.astimezone(timezone.utc).isoformat(),
  data_receipt=inner,data_inventory=dict(semantic_freshness=dict(next_trading_session_date=following)),
  decision_sha256=digest(decision),decision_origin_state_sha256=origin['state_sha256'],
  writer_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
  production_qualified=False)
 return dict(body,receipt_sha256=digest(body))

def write_weekly19_daily_receipt(path,payload):
 if payload.get('schema')!='weekly19.production-daily-data-receipt.v1'or payload.get('receipt_sha256')!=digest({k:v for k,v in payload.items()if k!='receipt_sha256'}):raise Weekly19DailyReceiptError('weekly19_receipt_payload_invalid')
 path=Path(path);box=FridayMailOutbox(path.parent);directory=box._directory();lock=None
 try:
  lock=box._open('.weekly19-daily-receipt.lock',os.O_RDWR,directory,True);fcntl.flock(lock,fcntl.LOCK_EX)
  try:
   fd=box._open(path.name,os.O_RDONLY,directory)
   with os.fdopen(fd,'rb')as f:previous=json.load(f)
   if previous.get('material_release_id')==payload['material_release_id']and previous.get('target_cutoff_date','')>payload['target_cutoff_date']:raise Weekly19DailyReceiptError('weekly19_receipt_target_rollback')
  except ValueError as e:
   if not isinstance(e.__cause__,FileNotFoundError):raise
  box._write(path.name,payload,directory)
 finally:
  if lock is not None:os.close(lock)
  os.close(directory)

def load_and_validate_weekly19_daily_receipt(path,*,context_file,source_commit,manifest_sha256,target_date,now=None):
 from qmt_roll_weekly19_local_backend import private_json
 from qmt_roll_weekly19_data import load_weekly19_inputs
 now=now or datetime.now(timezone.utc);cfg=private_json(context_file);payload=private_json(path)
 if cfg['execution_profile']!=PROFILE.profile_key:raise Weekly19DailyReceiptError('weekly19_receipt_context_profile_invalid')
 state=PipelineStateStore(Path(cfg['state_path']),cfg['account_key'],cfg['material_release_id']).read()
 if state is None or state.get('runtime_mode')!='production':raise Weekly19DailyReceiptError('weekly19_receipt_live_state_missing')
 market=cfg['market_data'];data=load_weekly19_inputs(Path(market['asset_root']),material_release_id=cfg['material_release_id'],target_date=target_date,
  forward_calendar=market['forward_calendar'],expected_hashes=market['expected_hashes'])
 expected=build_weekly19_daily_receipt(bundle=state,data=data,source_commit=source_commit,manifest_sha256=manifest_sha256,generated_at=payload['generated_at_utc'])
 if payload!=expected or target_date!=payload['target_cutoff_date']:raise Weekly19DailyReceiptError('weekly19_daily_receipt_source_or_state_mismatch')
 if datetime.fromisoformat(payload['generated_at_utc'])>now:raise Weekly19DailyReceiptError('weekly19_receipt_future_generation')
 return payload
