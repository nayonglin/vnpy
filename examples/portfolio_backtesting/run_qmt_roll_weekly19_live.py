#!/usr/bin/env python3
"""Dedicated weekly19 support/session entry; all external action is gated."""
import argparse
from datetime import datetime,timedelta
import json
from pathlib import Path
import time
from zoneinfo import ZoneInfo
from qmt_roll_official_execution_profile import WEEKLY19_15W_R150K_PROFILE as PROFILE
from qmt_roll_weekly19_local_backend import LocalEvidenceBackend,private_json,LocalBackendError
from qmt_roll_weekly19_live_pipeline import run_weekly19_support_job,run_weekly19_session_cycle,initialize_weekly19_existing_account,JOBS

SHANGHAI=ZoneInfo('Asia/Shanghai');ROOT=Path(__file__).resolve().parents[2]

def parser():
 p=argparse.ArgumentParser(description='Weekly19 original risk / real external reserve')
 p.add_argument('--job',choices=sorted(JOBS|{'session','initialize-existing-account'}),required=True)
 p.add_argument('--execution-profile',choices=[PROFILE.profile_key],required=True)
 p.add_argument('--context-file',type=Path,required=True)
 p.add_argument('--release-manifest',type=Path,required=True)
 p.add_argument('--activation-receipt',type=Path,required=True)
 p.add_argument('--production-qualification-evidence',type=Path,required=True)
 p.add_argument('--target-date',default='');p.add_argument('--session',choices=['day','night'])
 p.add_argument('--duration-seconds',type=int,default=3600)
 p.add_argument('--require-current-session-name',action='append',default=[])
 p.add_argument('--preview',action='store_true',help='Private offline preview, never SMTP or spool/CTP')
 return p

def session_end(now,names,calendar):
 """One service lifetime includes the day lunch break and Friday continuation."""
 from qmt_roll_official_live_phase_d_config import build_phase_d_config
 now=now.astimezone(SHANGHAI);day=now.date();allowed={s.name:s for s in build_phase_d_config().sessions if s.role=='market_and_execution'}
 if not names or any(n not in allowed for n in names):raise LocalBackendError('weekly19_execution_session_names_required')
 if now.weekday()>=5 and not(now.weekday()==5 and now.hour<3 and 'late_night'in names):raise LocalBackendError('weekly19_non_trading_weekend')
 night=any(n in {'night','late_night'}for n in names)
 if night and any(n in {'day_am','day_pm'}for n in names):raise LocalBackendError('weekly19_mixed_session_groups')
 start_day=day-timedelta(days=1)if night and now.hour<3 else day
 if start_day.isoformat()not in calendar:raise LocalBackendError('weekly19_session_calendar_day_missing')
 starts=[];ends=[]
 for name in names:
  s=allowed[name];start_hour,start_minute=map(int,s.start.split(':'));starts.append(datetime.combine(start_day,datetime.min.time(),SHANGHAI).replace(hour=start_hour,minute=start_minute))
  hour,minute=map(int,s.end.split(':'));end=datetime.combine(start_day,datetime.min.time(),SHANGHAI).replace(hour=hour,minute=minute)
  if name=='late_night':end+=timedelta(days=1)
  ends.append(end)
 if now<min(starts):raise LocalBackendError('weekly19_session_not_started')
 end=max(ends)
 if end<=now:raise LocalBackendError('weekly19_session_already_closed')
 return end

def run_session(context,*,duration_seconds,names,clock=None,sleep=None,on_cycle=None):
 clock=clock or(lambda:datetime.now(SHANGHAI));sleep=sleep or time.sleep;on_cycle=on_cycle or(lambda _:None)
 if type(duration_seconds)is not int or not 1<=duration_seconds<=24*3600:raise LocalBackendError('weekly19_duration_invalid')
 now=clock();backend=context['backend']
 if not context.get('preview',False):
  backend.require_production()
  calendar=backend.prepare_session(context['target_date'],now)
  session_end(now,names,set(calendar))
  backend.refresh_readonly(now);now=clock()
 data=backend.load_inputs(context['target_date'],now);deadline=min(now+timedelta(seconds=duration_seconds),session_end(now,names,set(data['calendar'])))
 backend.session_deadline=deadline
 cycles=0;last_cycle=None;shutdown=None
 try:
  while clock()<deadline:
   cycle=run_weekly19_session_cycle(context=dict(context,now=clock()));last_cycle=cycle;on_cycle(cycle);cycles+=1
   # Do not monopolize the process on a blocked/no-signal cycle. No wait >1s.
   remaining=(deadline-clock()).total_seconds()
   if remaining>0:sleep(min(1.0,remaining))
 finally:
  if hasattr(backend,'close_session'):shutdown=backend.close_session()
 return dict(status='session_lifetime_completed',cycles=cycles,ends_at=deadline.isoformat(),last_cycle=last_cycle,shutdown=shutdown,production_qualified=False)

def main(argv=None):
 args=parser().parse_args(argv)
 try:
  cfg=private_json(args.context_file)
  backend=LocalEvidenceBackend(cfg,repo_root=ROOT,release_manifest=args.release_manifest,activation_receipt=args.activation_receipt,
   qualification_evidence=args.production_qualification_evidence,preview=args.preview)
  backend.context_file=args.context_file.absolute()
  if args.job=='initialize-existing-account':
   from qmt_roll_weekly19_startup import load_startup_authorization
   policy=load_startup_authorization(cfg)
   if policy is None:raise LocalBackendError('weekly19_explicit_existing_account_policy_required')
   target=args.target_date or policy['authorization']['completed_day']
  else:target=args.target_date or(cfg.get('target_date')if args.job in {'health','monthly-ai-pool'}else backend.resolve_target_date(datetime.now(SHANGHAI)))
  if not target:raise LocalBackendError('weekly19_resolved_target_date_required')
  context=dict(backend=backend,state_path=Path(cfg['state_path']),mail_outbox=Path(cfg['mail_outbox']),
   account_key=cfg['account_key'],material_release_id=cfg['material_release_id'],cold_start_date=cfg['cold_start_date'],target_date=target,preview=args.preview)
  if args.job=='initialize-existing-account':result=initialize_weekly19_existing_account(context=context)
  else:result=run_session(context,duration_seconds=args.duration_seconds,names=args.require_current_session_name)if args.job=='session'else run_weekly19_support_job(args.job,context=context)
  print(json.dumps(result,ensure_ascii=False,sort_keys=True,allow_nan=False));return 0
 except (ValueError,KeyError,OSError,RuntimeError)as exc:
  # Never print raw payload, credentials or the private JSON configuration.
  reason=str(exc)if isinstance(exc,(LocalBackendError,))else type(exc).__name__
  zero=0 if 'backend'not in locals()or not getattr(backend,'external_action_started',False)else None
  print(json.dumps(dict(status='blocked',blockers=[reason],ctp_connection_attempted_count=zero,order_api_called_count=zero,send_order_api_called_count=zero,cancel_order_api_called_count=zero),ensure_ascii=False));return 2
if __name__=='__main__':raise SystemExit(main())
