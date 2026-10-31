"""Weekly19 orchestration; strategy/cash state is committed before delivery.

A process-local backend admits real sources and owns external transports. JSON
configuration cannot inject functions or assert qualification. Preview uses the
same runtime but cannot publish an intent or send SMTP. Component output is not
itself a production-qualification receipt.
"""
from copy import deepcopy
from datetime import date,datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import qmt_roll_weekly19_funding as funds
from qmt_roll_weekly19_pipeline_state import PipelineStateStore,digest
from qmt_roll_weekly19_runtime import build_weekly19_runtime,DEFAULT_SETTINGS_ASSET
from qmt_roll_weekly19_friday_report import build_friday_report,FridayMailOutbox
from qmt_roll_weekly19_friday_advice import refresh_friday_advice

SHANGHAI=ZoneInfo('Asia/Shanghai')
JOBS={'postclose-precompute','postclose-report','health','monthly-ai-pool','day-close-readonly'}
class Weekly19PipelineError(ValueError):pass

def _parts(context):
 now=context.get('now')or datetime.now(SHANGHAI)
 if not isinstance(now,datetime)or now.tzinfo is None:raise Weekly19PipelineError('weekly19_aware_clock_required')
 preview=context.get('preview',False)
 if type(preview)is not bool:raise Weekly19PipelineError('weekly19_preview_boolean_required')
 backend=context['backend']
 if not preview:backend.require_production()
 return backend,now,preview

def pipeline_store(context):
 return PipelineStateStore(Path(context['state_path']),context['account_key'],context['material_release_id'])

def _initial(context):
 return dict(schema='weekly19.pipeline-state.v1',revision=0,account_key=context['account_key'],
  material_release_id=context['material_release_id'],decision_state=None,runtime_mode='preview'if context.get('preview',False)else'production',funding=funds.initial_state(context['account_key'],
  context['material_release_id'],context['cold_start_date']),runtime=None,decision=None)

def _load(backend,context,now):
 target=date.fromisoformat(context['target_date']).isoformat()
 if target>now.astimezone(SHANGHAI).date().isoformat():raise Weekly19PipelineError('weekly19_future_completed_date')
 data=backend.load_inputs(target,now);receipt=data['receipt']
 if (receipt.get('schema')!='weekly19.data-receipt.v1'or receipt.get('complete')is not True
  or receipt.get('material_release_id')!=context['material_release_id']or receipt.get('trading_date')!=target):raise Weekly19PipelineError('weekly19_input_receipt_mismatch')
 if target not in data['bars_by_day']:raise Weekly19PipelineError('weekly19_completed_bars_missing')
 return target,data

def _assert_completed_history_sequence(bundle,data,target):
 previous=bundle['runtime']['input_cursor']if bundle.get('runtime')is not None else None
 cold=bundle['funding']['cold_start_date']
 missing=[day for day in data['calendar']if day<target and (day>previous if previous is not None else day>=cold)]
 if missing:raise Weekly19PipelineError('weekly19_completed_history_gap_requires_explicit_recovery:'+missing[0]+':'+missing[-1])

def _runtime(bundle,data,now,events=()):
 obj=build_weekly19_runtime(DEFAULT_SETTINGS_ASSET,data['metadata'],data['calendar'],data['physical_epoch_daily'],
  data['broker_snapshot'],bundle['runtime'],bundle['funding'],clock=lambda:now,recovery_events=events)
 if bundle['runtime']is None:
  cold=bundle['funding']['cold_start_date']
  obj.warmup([data['bars_by_day'][day]for day in sorted(data['bars_by_day'])if day<cold])
 return obj

def _apply_events(obj,events):
 # A terminal query order can include fills not yet applied locally. Apply raw
 # actual fills first; only then release a completed/cancelled reservation.
 for event in sorted(events,key=lambda row:0 if row['kind']=='fill'else 1):
  if event['kind']=='fill':obj.apply_broker_fill(event['envelope'],event['signal_identity'])
  elif event['kind']=='order':obj.apply_order_update(event['envelope'])
  else:raise Weekly19PipelineError('weekly19_execution_event_kind_invalid')

def _report(context,backend,bundle,data,now,preview):
 if now.astimezone(SHANGHAI).weekday()!=4:return None
 decision=deepcopy(bundle.get('decision'))
 if not decision:raise Weekly19PipelineError('completed_decision_missing')
 if digest(data['receipt'])!=decision['data_receipt_sha256']:raise Weekly19PipelineError('report_original_data_receipt_mismatch')
 advice=bundle.get('friday_advice')
 if advice is None:raise Weekly19PipelineError('committed_friday_advice_missing')
 checked=refresh_friday_advice(bundle,data['broker_snapshot']['account'],now)
 if (checked['status']!=advice['status']or checked['recommendation']!=advice['recommendation']
  or checked.get('advice_id')!=advice.get('advice_id')or checked.get('funding')!=bundle['funding']):raise Weekly19PipelineError('committed_friday_advice_not_current')
 report=build_friday_report(funding_state=bundle['funding'],broker_account=data['broker_snapshot']['account'],
  recommendation=advice['recommendation'],friday_advice=advice,
  decision=decision,data_receipt=dict(status='ready',material_release_id=context['material_release_id'],
  target_date=decision['trading_date'],sha256=decision['data_receipt_sha256']),now=now,preview=preview,blocking_reasons=([backend.cash_source_blocker]if getattr(backend,'cash_source_blocker',None)else()))
 if preview:return report
 result=FridayMailOutbox(context['mail_outbox']).deliver(report,backend.send_mail)
 return dict(report,delivery=result)

def _refresh_advice(bundle,obj,data,now):
 if now.astimezone(SHANGHAI).weekday()!=4:return bundle
 # Advice is an outer operational record. The original strategy decision and
 # complete decision_state remain immutable, including holiday Thursdays.
 bundle['runtime']=obj.export_state();bundle['funding']=deepcopy(obj.confirmed_cash_state)
 advice=refresh_friday_advice(bundle,data['broker_snapshot']['account'],now)
 if advice['funding']!=bundle['funding']:
  obj.reconcile_broker_snapshot(data['broker_snapshot'],advice['funding'])
  bundle['runtime']=obj.export_state();bundle['funding']=deepcopy(obj.confirmed_cash_state)
 previous=bundle.get('friday_advice')
 if not(previous and previous.get('advice_id')==advice.get('advice_id')and previous.get('broker_account_raw_sha256')==advice.get('broker_account_raw_sha256')and previous.get('status')==advice['status']):
  bundle['friday_advice']=advice
 return bundle

def run_weekly19_support_job(job,*,context):
 if job not in JOBS:raise Weekly19PipelineError('weekly19_unknown_support_job')
 if job=='monthly-ai-pool':return dict(status='disabled_for_fixed19',reason='fixed_19_universe_ai_off',production_qualified=False)
 backend,now,preview=_parts(context);store=pipeline_store(context)
 if job=='health':
  bundle=store.read()
  return dict(status='ready_state'if bundle else'not_initialized',revision=None if bundle is None else bundle['revision'],
   state_sha256=None if bundle is None else digest(bundle),production_qualified=False)
 if context['target_date']<context['cold_start_date']:
  return dict(status='skipped_before_weekly19_cold_start',target_date=context['target_date'],production_qualified=False)
 if not preview and job in {'postclose-precompute','day-close-readonly'}and hasattr(backend,'refresh_readonly'):
  backend.refresh_readonly(now);now=datetime.now(SHANGHAI)
 if not preview and job=='postclose-precompute'and hasattr(backend,'refresh_market_data'):
  backend.refresh_market_data(context['target_date'],now);now=datetime.now(SHANGHAI)
 target,data=_load(backend,context,now)
 existing=store.read()
 if existing is not None and not preview and existing.get('runtime_mode')!='production':raise Weekly19PipelineError('preview_state_cannot_become_production')
 if job=='postclose-report':
  if existing is None or existing['decision']is None or existing['decision']['trading_date']!=target:
   return dict(status='blocked',blockers=['completed_decision_missing'],production_qualified=False)
  if now.astimezone(SHANGHAI).weekday()==4:
   def refresh(bundle):
    cash=backend.reconcile_cash(bundle['funding'],data['broker_snapshot'],now);bundle['funding']=cash
    obj=_runtime(bundle,data,now,backend.read_execution_events(bundle['decision'],now))
    return _refresh_advice(bundle,obj,data,now)
   existing=store.transact(refresh)
  report=_report(context,backend,existing,data,now,preview)
  return dict(status='preview_complete'if preview else'report_complete',mail=report,production_qualified=False)
 if existing is None:
  if not preview:backend.validate_initial_account(data['broker_snapshot'],now)
  store.initialize(_initial(context))
 def advance(bundle):
  if job=='postclose-precompute':_assert_completed_history_sequence(bundle,data,target)
  cash=backend.reconcile_cash(bundle['funding'],data['broker_snapshot'],now)
  funds.validate_state(cash);bundle['funding']=cash
  obj=_runtime(bundle,data,now,backend.read_execution_events(bundle['decision'],now))
  if job=='postclose-precompute':
   decision=obj.process_completed_day(target,data['bars_by_day'][target],data['receipt'],data['broker_snapshot'],cash)
   bundle['decision']=decision
   if bundle.get('decision_state')is None or bundle['decision_state']['state_sha256']!=decision['after_state_sha256']:
    if obj.export_state()['state_sha256']!=decision['after_state_sha256']:raise Weekly19PipelineError('decision_origin_state_missing')
    bundle['decision_state']=obj.export_state()
  else:
   obj.reconcile_broker_snapshot(data['broker_snapshot'],cash)
  bundle['runtime']=obj.export_state();bundle['funding']=deepcopy(obj.confirmed_cash_state)
  return _refresh_advice(bundle,obj,data,now)if job=='postclose-precompute'else bundle
 bundle=store.transact(advance)
 if job=='postclose-precompute'and hasattr(backend,'complete_postclose'):backend.complete_postclose(bundle,data,now)
 report=_report(context,backend,bundle,data,now,preview)if job=='postclose-precompute'else None
 return dict(status='preview_complete'if preview else'completed',job=job,target_date=target,
  revision=bundle['revision'],state_sha256=digest(bundle),decision_sha256=digest(bundle['decision']),
  mail=report,production_qualified=False)

def run_weekly19_session_cycle(*,context):
 backend=context.get('backend')
 if not context.get('preview',False)and getattr(backend,'_service',None)is not None:
  now=context.get('now')or datetime.now(SHANGHAI)
  if now.tzinfo is None or now.utcoffset()is None:raise Weekly19PipelineError('aware_now_required')
  return backend.execution_session_cycle(target_date=context['target_date'],now=now)
 backend,now,preview=_parts(context);target,data=_load(backend,context,now);store=pipeline_store(context)
 if target<context['cold_start_date']:return dict(status='skipped_before_weekly19_cold_start',production_qualified=False)
 existing=store.read()
 if existing is None:return dict(status='blocked',blockers=['completed_decision_missing'],production_qualified=False)
 if not preview and existing.get('runtime_mode')!='production':raise Weekly19PipelineError('preview_state_cannot_become_production')
 runtime_holder={}
 def reconcile(bundle):
  cash=backend.reconcile_cash(bundle['funding'],data['broker_snapshot'],now);bundle['funding']=cash
  obj=_runtime(bundle,data,now,backend.read_execution_events(bundle['decision'],now))
  obj.reconcile_broker_snapshot(data['broker_snapshot'],cash,quote_snapshot=backend.quote_snapshot(now)if hasattr(backend,'quote_snapshot')else None)
  bundle['runtime']=obj.export_state();bundle['funding']=deepcopy(obj.confirmed_cash_state);runtime_holder['runtime']=obj;return bundle
 bundle=store.transact(reconcile)
 if preview:return dict(status='preview_no_execution',state_sha256=digest(bundle),production_qualified=False)
 if not bundle['decision']or bundle['decision']['trading_date']!=target:return dict(status='blocked',blockers=['completed_decision_missing'],production_qualified=False)
 # This backend must use the real journal→quote-spool→controller→931 contract;
 # a producer decision alone is never an authorized execution record.
 result=backend.publish_execution(runtime=runtime_holder['runtime'],bundle=deepcopy(bundle),data=data,now=now)
 return dict(status='session_cycle',execution=result,state_sha256=digest(bundle),production_qualified=False)
