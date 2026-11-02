"""One runtime actor and the existing warm execution service for a session.

External callbacks supply qualified private data/source bridges, never a new
sender. Publication and final-risk work share the actor lock; history is not
rebuilt at every poll or API boundary. This module never claims qualification.
"""
from __future__ import annotations
from collections import OrderedDict
from copy import deepcopy
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
from threading import Event, Lock, RLock, Thread
import time

from qmt_roll_official_execution_profile import WEEKLY19_15W_R150K_PROFILE as PROFILE
from qmt_roll_official_live_authorization_lock import exclusive_submit_authorization_lock, submit_authorization_lock_path, SubmitAuthorizationLockBusyError
from qmt_roll_official_live_submit_authorization import submit_authorization_path,revoke_submit_authorization
from qmt_roll_official_live_intent_spool import open_spool,read_detector_cursor,expire_due_intents,SpoolConflictError,notify_executor,wakeup_socket_path,_blocked_close_has_safe_zero_native_proof
from qmt_roll_official_live_time import SystemClock
from qmt_roll_weekly19_controller import Weekly19ControllerAuthority,publish_weekly19_controller_authorization
from qmt_roll_weekly19_quote_spool import prepare_weekly19_quote_intent,commit_weekly19_quote_batch

class Weekly19ExecutionServiceError(ValueError): pass

def _require(condition,reason):
 if not condition:raise Weekly19ExecutionServiceError(reason)

class Weekly19ExecutionService:
 def __init__(self,args,*,authority_provider,fresh_context_provider,event_consumer,native_capture_factory,
              publication_inputs_provider,clock=None,runner=None,refresh_interval_seconds=30):
  _require(args.execution_profile==PROFILE.profile_key and args.runtime_profile=='production-live'and args.order_scope=='live',
    'weekly19_service_canonical_live_profile_required')
  _require(all(callable(fn)for fn in (authority_provider,fresh_context_provider,event_consumer,native_capture_factory,publication_inputs_provider)),
    'weekly19_service_process_local_bridges_required')
  _require(5<=refresh_interval_seconds<=120,'weekly19_service_refresh_interval_invalid')
  self.args=deepcopy(args);self.clock=clock or SystemClock();self.authority_provider=authority_provider
  self.context_provider=fresh_context_provider;self.event_consumer=event_consumer;self.native_factory=native_capture_factory
  self.inputs_provider=publication_inputs_provider;self.runner=runner;self.refresh_seconds=refresh_interval_seconds
  self.actor_lock=RLock();self._publication_lock=Lock();self._actor=None;self._session=None;self._thread=None;self._stop=Event();self._observed=Event()
  self._deadline_epoch_ns=None;self._failure=None;self._authority=None;self._last_refresh_ns=None;self._prepared=OrderedDict()
  self._publication_seen=set()
  root=Path(args.stage179_runtime_root).expanduser().resolve(strict=False)
  self.spool_path=root/'state/intent_spool.sqlite3';self.authorization_path=submit_authorization_path(root)
 @property
 def runtime_actor(self):return self._actor
 @property
 def active(self):return self._thread is not None and self._thread.is_alive()and not self._lifetime_stopped()
 def bind_deadline(self,epoch_ns):
  _require(type(epoch_ns)is int and epoch_ns>self.clock.epoch_ns(),'weekly19_service_deadline_invalid')
  _require(self._deadline_epoch_ns in (None,epoch_ns),'weekly19_service_deadline_replacement_forbidden')
  self._deadline_epoch_ns=epoch_ns
 def _lifetime_stopped(self):
  return self._stop.is_set()or(self._deadline_epoch_ns is not None and self.clock.epoch_ns()>=self._deadline_epoch_ns)
 def bind_actor(self,runtime_actor):
  with self.actor_lock:
   _require(runtime_actor is not None,'weekly19_service_runtime_actor_missing')
   _require(self._actor is None or self._actor is runtime_actor,'weekly19_service_actor_replacement_forbidden')
   self._actor=runtime_actor
 def _now(self):return datetime.fromtimestamp(self.clock.epoch_ns()/1_000_000_000,tz=timezone.utc)
 def _context(self,row,*,transport_context):
  with self.actor_lock:
   return self.context_provider(row,transport_context=transport_context,runtime_actor=self._actor)
 def _event(self,kind,row,original):
  with self.actor_lock:
   return self.event_consumer(kind,row,original,runtime_actor=self._actor)
 def start(self,*,runtime_actor=None):
  if runtime_actor is not None:self.bind_actor(runtime_actor)
  _require(self._actor is not None,'weekly19_service_runtime_actor_missing')
  _require(not self._lifetime_stopped(),'weekly19_service_lifetime_ended')
  if self.active:return dict(status='running',production_qualified=False)
  _require(self._thread is None,'weekly19_service_restart_requires_new_owner')
  authority=self.authority_provider(now=self._now())
  _require(isinstance(authority,Weekly19ControllerAuthority),'weekly19_service_source_authority_required')
  authority.assert_current(self._now());self._authority=authority
  def observe(session):self._session=session;self._observed.set()
  def run():
   try:
    if self.runner is None:
     from run_qmt_roll_stage931_official_live_ctp_submit_adapter import run_serve
     runner=run_serve
    else:runner=self.runner
    runner(self.args,weekly19_context_provider=self._context,weekly19_event_consumer=self._event,
      weekly19_native_capture_factory=self.native_factory,stop_requested=self._lifetime_stopped,backend_observer=observe)
   except BaseException as exc:self._failure=type(exc).__name__+':'+str(exc)
   finally:self._stop.set()
  self._thread=Thread(target=run,name='weekly19-existing-stage931-warm',daemon=False);self._thread.start()
  return dict(status='starting',production_qualified=False)
 def _readiness(self):
  _require(self._session is not None,'weekly19_warm_service_starting')
  probe=getattr(self._session,'transport_blockers',None)
  if callable(probe):_require(not probe(),'weekly19_warm_transport_not_ready')
  pending=self._session.transport_context().get('rows',{}).get('_weekly19_deferred_broker_events',{})
  _require(isinstance(pending,dict)and not pending,'weekly19_durable_broker_events_awaiting_replay')
  raw=self._session.readiness_lease(now_epoch_ns=self.clock.epoch_ns())
  result=asdict(raw)if is_dataclass(raw)else dict(raw)
  if self._deadline_epoch_ns is not None:result['expires_epoch_ns']=min(result['expires_epoch_ns'],self._deadline_epoch_ns)
  return result
 def _refresh_if_due(self):
  current=self.clock.monotonic_ns()
  context=self._session.transport_context()
  receipt=context.get('rows',{}).get('_weekly19_native_receipts',{}).get('account')
  age=None
  if isinstance(receipt,dict):
   try:age=(self._now()-datetime.fromisoformat(receipt['completed_at'])).total_seconds()
   except (ValueError,TypeError,KeyError):pass
  # macOS monotonic time need not advance through host sleep. A real source
  # wall-clock age is always required before skipping read-only refresh.
  if age is not None and 0<=age<self.refresh_seconds:
   if self._last_refresh_ns is None:self._last_refresh_ns=current;return
   if 0<=current-self._last_refresh_ns<self.refresh_seconds*1_000_000_000:return
  # This lock excludes leased physical sends. Querying here cannot invalidate
  # a final API-slot watermark and never needs a synthetic authorization.
  with exclusive_submit_authorization_lock(submit_authorization_lock_path(self.authorization_path.parent),blocking=False):
   revoke_submit_authorization(self.authorization_path,reason='weekly19_prepublication_source_refresh',revoked_epoch_ns=self.clock.epoch_ns())
   result=self._session.refresh_weekly19_context()
   _require(isinstance(result,dict)and result.get('ready')is True,
     'weekly19_prepublication_query_refresh_blocked:'+','.join(result.get('blockers',[])if isinstance(result,dict)else[]))
  self._last_refresh_ns=self.clock.monotonic_ns()
 def _one_publication_intent(self,decision):
  # One original-rule sizing proof per producer cycle. Active deliveries keep
  # their immutable quote; blocked candidates rotate in original plan order so
  # missing funds cannot starve a later risk-reducing action.
  connection=open_spool(self.spool_path)
  try:
   expire_due_intents(connection,now_epoch_ns=self.clock.epoch_ns(),now_monotonic_ns=self.clock.monotonic_ns(),clock_domain_id=self.clock.clock_domain_id())
   delivered=set()
   for prior in connection.execute("SELECT * FROM intents WHERE source IN ('weekly19_pending_order','weekly19_risk_reduce')").fetchall():
    safe_expired=prior['state']=='expired'and(prior['attempt_count']==0 or prior['ledger_disposition']in{'no_side_effect_retryable','post_slot_no_native_retryable'})
    if safe_expired or _blocked_close_has_safe_zero_native_proof(prior):continue
    business=json.loads(prior['payload_json'])
    delivered.add((business.get('planned_intent_id'),business.get('material_release_id'),business.get('account_fingerprint')))
  finally:connection.close()
  candidates=[]
  for intent in decision.get('intents',[]):
   key=(intent.get('planned_intent_id')or intent['intent_id'],intent.get('material_release_id'),intent.get('account_fingerprint'))
   if key not in delivered:candidates.append((key,intent))
  if not candidates:return []
  unseen=[(key,intent)for key,intent in candidates if key not in self._publication_seen]
  if not unseen:self._publication_seen.clear();unseen=candidates
  key,intent=unseen[0];self._publication_seen.add(key)
  return [intent]
 def _prepare_publication(self,*,bundle,data):
  # Take publication inputs AFTER real query refresh and its actor replay.
  at=self._now();transport=self._session.transport_context()
  inputs=self.inputs_provider(runtime_actor=self._actor,bundle=bundle,data=data,now=at,transport_context=transport)
  decision=inputs['decision'];prepared=[];blocked=[]
  from run_qmt_roll_stage905_official_live_executor_dry_run import run_executor_dry_run
  for intent in self._one_publication_intent(decision):
   context=self._context(intent,transport_context=transport)
   single=dict(decision,intents=[intent])
   result=run_executor_dry_run(decision['trading_date'],execution_profile=PROFILE,weekly19_decision=single,
     weekly19_context=context,clock=self.clock,write_compat_outputs=False)
   if result.summary['ready_count']!=1:
    blocked.extend(result.intents.get('executor_reason',[]));continue
   ready=result.intents.iloc[0].to_dict();state=self._actor.execution_state(intent.get('planned_intent_id')or intent['intent_id'])
   item=prepare_weekly19_quote_intent(ready,journal_segment_path=inputs['journal_segment_path'],
     durable_through=inputs['durable_through'],execution_state=state,clock=self.clock)
   previous=self._prepared.get(item['intent_id'])
   if previous is not None:
    for key in ('planned_volume','limit_price','material_release_id','planned_intent_id'):
     _require(previous[key]==item[key],'weekly19_same_delivery_business_conflict')
    _require(previous['weekly19_quote_proof']['durable_state_sha256']==item['weekly19_quote_proof']['durable_state_sha256'],
      'weekly19_durable_revision_did_not_advance')
    item=previous
   else:self._prepared[item['intent_id']]=item
   while len(self._prepared)>128:self._prepared.popitem(last=False)
   prepared.append(item)
  connection=open_spool(self.spool_path)
  try:
   expire_due_intents(connection,now_epoch_ns=self.clock.epoch_ns(),now_monotonic_ns=self.clock.monotonic_ns(),clock_domain_id=self.clock.clock_domain_id())
   missing=[item for item in prepared if connection.execute('SELECT 1 FROM intents WHERE intent_id=?',(item['intent_id'],)).fetchone()is None]
   if missing:
    expected=read_detector_cursor(connection,consumer_id='weekly19')
    try:commit_weekly19_quote_batch(connection,expected_cursor=expected,next_cursor=inputs['durable_through'],intents=missing,
        clock=self.clock,feed_rollover_evidence=inputs.get('feed_rollover_evidence'))
    except SpoolConflictError as exc:
     if 'weekly19_native_signal_already'in str(exc):blocked.append(str(exc))
     else:raise
   return blocked
  finally:connection.close()
 def publish(self,*,runtime,bundle,data,now=None):
  if not self._publication_lock.acquire(blocking=False):
   return dict(status='publication_in_progress',production_qualified=False)
  try:
   self.bind_actor(runtime)
   if self._thread is None:self.start()
   _require(self.active,'weekly19_warm_service_failed:'+(self._failure or 'stopped'))
   self._authority.assert_current(self._now())
   ready=getattr(self._session,'connection_ready',None)
   if self._session is None or (callable(ready)and not ready()):
    return dict(status='warming',blockers=['weekly19_warm_connection_startup_in_progress'],production_qualified=False)
   # Neither lifecycle/counter probes nor a real query may run with actor_lock:
   # their native callbacks must acquire that same lock for durable replay.
   self._refresh_if_due();self._readiness()
   with self.actor_lock:blocked=self._prepare_publication(bundle=bundle,data=data)
   connection=open_spool(self.spool_path)
   try:
    result=publish_weekly19_controller_authorization(connection,spool_path=self.spool_path,authorization_path=self.authorization_path,
     authority=self._authority,fresh_context_provider=lambda row:self._context(row,transport_context=self._session.transport_context()),
     readiness=self._readiness,clock=self.clock)
    if result['status']=='published':notify_executor(wakeup_socket_path(self.spool_path))
    if blocked:result['producer_blockers']=list(blocked)
    return result
   finally:connection.close()
  except SubmitAuthorizationLockBusyError:return dict(status='execution_in_progress',production_qualified=False)
  except Exception as exc:return dict(status='blocked',blockers=[str(exc)],production_qualified=False)
  finally:self._publication_lock.release()
 def stop(self,*,timeout=10,reason='weekly19_session_owner_stopped'):
  self._stop.set()
  if self._thread is not None:self._thread.join(max(0,min(float(timeout),30)))
  if self._thread is not None and self._thread.is_alive():
   return dict(status='stop_pending',blockers=['weekly19_warm_shutdown_in_progress'],production_qualified=False)
  try:
   with exclusive_submit_authorization_lock(submit_authorization_lock_path(self.authorization_path.parent),blocking=False):
    revoke_submit_authorization(self.authorization_path,reason=reason,revoked_epoch_ns=self.clock.epoch_ns())
  except SubmitAuthorizationLockBusyError:return dict(status='stop_pending',blockers=['weekly19_execution_lease_in_progress'],production_qualified=False)
  return dict(status='stopped',production_qualified=False)
