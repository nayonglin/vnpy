"""One fixed C_TS account replay with ordered initial-entry execution.

Bootstrap is deliberately stdlib-only. Stage022 is imported for its accepted
runtime/data/capture helpers; its main and its C0 strategy are never executed.
The research engine retains native u-close q/S and does not re-run that budget
at the conditional fill. Actual gap risk can exceed the original u estimate.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import csv
from dataclasses import asdict
from datetime import date, datetime
import json
import math
import gzip
import hashlib
import os
import pickle
import uuid
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import stage022_run_c0_qualified_wait as prior

ROOT, LINE = prior.ROOT, prior.LINE
OUTPUT = LINE/'outputs/stage031_ordered_account'
PARENT_RUNNER_SHA='c05924175609c09ce0a44b451bcc97497be2b30012cb9c971886217c4960c6af'
FROZEN_MODULES={'stage028_ordered_strategy.py':'d4f870355796c98625031f233dfba31f97db10422c894076acf436279f141c48','stage028_ordered_engine.py':'f7d7450495bb09407dc85ce6fe73fd700b2732a2e57dc8f6185abf199967af23'}
PROTOCOL = LINE/'stages/20261018_0302_stage031_export_checkpoint_fix.md'
ENTRY_CONTRACT = LINE/'stages/20261018_0234_stage028_conditional_execution_contract.md'
PLAN = LINE/'stages/20261018_0234_stage028_conditional_execution_plan.md'
HOLDING_CONTRACT = LINE/'stages/20261018_0242_stage028_entry_day_holding_causality.md'
FEATURE_ROOT = LINE/'outputs/stage027_ordered_features'
FEATURE_REVIEW = LINE/'outputs/stage027_independent_review/review_receipt.json'
FEATURE_REVIEW_SHA = '28beb5a3eafa9dcb7b23e4ad93d7332865533007c0e040c3d21f0ddcc8fa9346'
FEATURE_SUMMARY_SHA = '8089f924ac5b81ead6acefcbb833b5cd93495facae1c5641facc84df61685c63'
FEATURE_MANIFEST_SHA = '426cd031619b42167b150a1c543e367d39f75911612aa5bc101a14da754b3ae8'
FI_SHA = '362b1aea72d72dc60e7ae505f9a999e1344c9b8335994f6b7945cd862620d570'
STACK_SHA = '2b650761fbf2bc30aa0046147b7e369a2a0a10a68ee6b520204dde8d4d7226a0'
CALENDAR = LINE/'outputs/stage005_potential_signal_demand/global_engine_calendar.csv'
A0 = LINE/'outputs/stage001_first_screen/A0_attempt2'
A0_REVIEW = LINE/'outputs/stage001_independent_review/review_receipt.json'
A0_SHA = {
 'daily.csv':'f645bc76c75631c177d56d9e212c017a2589e0dfe0fb82ea8f0a21a593ee3454',
 'summary.json':'a98ffe612837b6e4ecf7cf5e3d25074749929d2b465881597ed9c6e12f074078',
 'metrics.json':'a1f998c3e7434dcefa96e578911ecd9bd3dbb49c629ab94814d9dc25855e3ecb',
 'run_provenance.json':'3a83c4e930522e13a63e165fa7744325ec3feae51fe0ee1c7096624f56346208',
}
A0_REVIEW_SHA = '5317fa98054c7469e0dc983fdb5678c05678bd382f616f1ec4b5bb59c4d4356d'
ANCHOR_REQUEST_ID = 'fe0537d2a88976cee5be621e6ce5c3e5ed1320ce9b4941d8962a0d2677522607'
ANCHOR_REQUEST = LINE/('outputs/stage001_first_screen/C0_attempt3/data_wait/request_'+ANCHOR_REQUEST_ID+'/request.json')
ANCHOR_RECEIPT = LINE/('outputs/stage023_independent_review/request_'+ANCHOR_REQUEST_ID+'/delivery_receipt.json')
ANCHOR_RECEIPT_SHA = '343a33480af2d8d68ccfa6a524a940639353f68f12fb8438f4b4f3e0482cd6b0'
RESULT_SCOPE = 'offline_ordered_initial_entry_C_TS_vs_reused_A0_attempt2'
EXECUTION_CONTRACT = 'native_u_close_fixed_q_and_S; no_D_budget_reallocation; actual_gap_R_and_margin_not_bounded_by_u_gate'
sha256, write_json, json_safe = prior.sha256, prior.write_json, prior.json_safe
ENGINE_VALIDATION=dict(engine_returned=True,actual_settings_equal_accepted_A=True,parameters_equal_accepted_A=True,actual_daily_dates_equal_accepted_A0=True,captured_bar_failures=0,strict_minute_missing_bars=0,all_consumed_inputs_unchanged_during_run=True,frozen_correctness_code_unchanged=True,historical_shared_signal_input_empty=True)


def actual_trade_identities(trades):
    """Capture explicit native identity, without inventing absent signal fields."""
    return [dict(trade_id=t.vt_tradeid,vt_symbol=t.vt_symbol,direction=t.direction.value,offset=t.offset.value,
        price=float(t.price),volume=float(t.volume),execution_datetime=getattr(t,'execution_datetime',t.datetime),
        trading_date=getattr(t,'trading_date',None),signal_datetime=getattr(t,'signal_datetime',None),
        signal_order_id=getattr(t,'signal_order_id',None),intraday_episode_id=getattr(t,'intraday_episode_id',None))for t in trades]


def build_execution_clock(capture,identities):
    """Validate real TradeData identity and real synthetic mother links first."""
    import pandas as pd
    clock=prior.canonical_trade_enums(pd.DataFrame(capture['trades']))
    usage=pd.DataFrame(capture['usage']).copy()
    actual=prior.canonical_trade_enums(pd.DataFrame(identities))
    if any(frame.empty or 'trade_id'not in frame or frame.trade_id.duplicated().any()for frame in(clock,usage,actual)):
        raise ValueError('execution_identity_empty_or_duplicate')
    if set(clock.trade_id)!=set(usage.trade_id)or set(clock.trade_id)!=set(actual.trade_id):
        raise ValueError('execution_identity_not_one_to_one')
    truth=actual.set_index('trade_id',verify_integrity=True)
    raw=usage.set_index('trade_id',verify_integrity=True)
    def missing(value):return value is None or str(value).strip()==''or bool(pd.isna(value))
    def stamp(value):
        if missing(value):raise ValueError('actual_trade_explicit_signal_identity_missing')
        result=pd.Timestamp(value)
        if pd.isna(result):raise ValueError('actual_trade_explicit_signal_identity_missing')
        return result.tz_convert('Asia/Shanghai').tz_localize(None)if result.tzinfo else result
    for trade_id,row in truth.iterrows():
        if missing(row.signal_order_id):raise ValueError('actual_trade_explicit_signal_order_id_missing')
        signal=stamp(row.signal_datetime);executed=stamp(row.execution_datetime)
        if signal>executed:raise ValueError('signal_after_execution')
        observed=clock.loc[clock.trade_id.eq(trade_id)].iloc[0]
        for field in('vt_symbol','direction','offset'):
            if str(observed[field])!=str(row[field]):raise ValueError(f'actual_trade_clock_conflict:{field}')
        if stamp(observed.execution_datetime)!=executed or str(observed.trading_date)[:10]!=str(row.trading_date)[:10]:
            raise ValueError('actual_trade_clock_date_conflict')
        for field in('price','volume'):
            if float(observed[field])!=float(row[field]):raise ValueError(f'actual_trade_clock_conflict:{field}')
        episode=row.intraday_episode_id
        synthetic=not missing(episode)
        if synthetic:
            if episode not in truth.index:raise ValueError('synthetic_actual_parent_missing')
            parent=truth.loc[episode]
            if parent.offset!='开' or parent.vt_symbol!=row.vt_symbol or str(parent.trading_date)[:10]!=str(row.trading_date)[:10]:
                raise ValueError('synthetic_parent_contract_or_day_conflict')
            if stamp(parent.execution_datetime)>executed:raise ValueError('synthetic_before_parent_open')
            if stamp(parent.signal_datetime)!=signal or str(parent.signal_order_id)!=str(row.signal_order_id):
                raise ValueError('synthetic_actual_parent_signal_conflict')
            if 'intraday_episode_id'not in raw or missing(raw.loc[trade_id,'intraday_episode_id'])or str(raw.loc[trade_id,'intraday_episode_id'])!=str(episode):
                raise ValueError('synthetic_usage_parent_conflict')
        for field in('signal_datetime','signal_order_id'):
            value=raw.loc[trade_id,field]if field in raw else None
            if missing(value):
                if not synthetic:raise ValueError(f'ordinary_usage_identity_missing:{field}')
            elif (stamp(value)!=signal if field=='signal_datetime'else str(value)!=str(row.signal_order_id)):
                raise ValueError(f'usage_actual_identity_conflict:{field}')
        if not synthetic and 'intraday_episode_id'in raw and not missing(raw.loc[trade_id,'intraday_episode_id']):
            raise ValueError('usage_unproven_synthetic_parent')
    for field in('signal_datetime','signal_order_id','intraday_episode_id'):
        values=clock.trade_id.map(truth[field])
        clock[field]=values.map(lambda value:''if missing(value)else stamp(value).isoformat())if field=='signal_datetime'else values.fillna('')
        usage[field]=usage.trade_id.map(clock.set_index('trade_id')[field])
    clock['signal_identity_source']='actual_TradeData_explicit'
    usage['signal_identity_source']='actual_TradeData_explicit_after_producer_consistency_check'
    return clock,usage


def owned_output(output):
    output=Path(output)
    expected=OUTPUT/'C_TS'
    if output.resolve()!=expected.resolve()or output.is_symlink():
        raise ValueError('checkpoint_requires_exact_owned_output')
    return output.resolve()


def new_run_context(output,started):
    output=owned_output(output)
    return dict(schema='stage031_run_context_v1',run_id=uuid.uuid4().hex,arm='C_TS',attempt=2,
        output_directory=str(output),started_at=str(started),writer='stage031_run_ordered_checkpoint.py',
        writer_source_sha256=sha256(Path(__file__)),parent_runner_sha256=PARENT_RUNNER_SHA,
        strategy_engine_sha256=FROZEN_MODULES,production_qualified=False)


def fsync_directory(path):
    descriptor=os.open(path,os.O_RDONLY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)


def atomic_checkpoint_json(path,payload):
    prior.atomic_json(path,payload);fsync_directory(Path(path).parent)


def save_raw_checkpoint(output,payload):
    """Only account exports are pickled; no engine, strategy or minute cache."""
    output=owned_output(output);context=json.loads((output/'run_context.json').read_text())
    if payload.get('run_context')!=context:raise ValueError('checkpoint_run_context_mismatch')
    folder=output/'checkpoint';folder.mkdir(exist_ok=False)
    raw=folder/'raw_account.pkl.gz';temporary=folder/'raw_account.pkl.gz.tmp'
    with temporary.open('xb')as handle:
        with gzip.GzipFile(fileobj=handle,mode='wb',mtime=0)as compressed:
            pickle.dump(dict(payload,schema='stage031_raw_account_checkpoint_v1'),compressed,protocol=5)
        handle.flush();os.fsync(handle.fileno())
    os.replace(temporary,raw);fsync_directory(folder)
    manifest=dict(schema='stage031_raw_checkpoint_manifest_v1',status='raw_evidence_not_validation_or_performance_pass',
        raw_filename=raw.name,raw_sha256=sha256(raw),raw_bytes=raw.stat().st_size,
        output_directory=str(output),run_id=context['run_id'],arm='C_TS',attempt=2,
        writer=context['writer'],writer_source_sha256=context['writer_source_sha256'],
        run_context_sha256=sha256(output/'run_context.json'),parent_runner_sha256=PARENT_RUNNER_SHA,
        strategy_engine_sha256=FROZEN_MODULES,account_exports_only=True,production_qualified=False)
    if sha256(output/'runner_used.py')!=manifest['writer_source_sha256']:raise ValueError('checkpoint_writer_snapshot_mismatch')
    atomic_checkpoint_json(folder/'raw_manifest.json',manifest)
    return manifest


def seal_checkpoint(output,manifest,validation):
    output=owned_output(output);folder=output/'checkpoint'
    if json.loads((folder/'raw_manifest.json').read_text())!=manifest or sha256(folder/manifest['raw_filename'])!=manifest['raw_sha256']:
        raise ValueError('checkpoint_changed_before_seal')
    if any(validation.get(key)!=value for key,value in ENGINE_VALIDATION.items()):raise ValueError('engine_not_validated')
    seal=dict(schema='stage031_engine_validation_seal_v1',status='engine_snapshot_validated_not_independent_economic_review',
        run_id=manifest['run_id'],attempt=2,arm='C_TS',raw_sha256=manifest['raw_sha256'],
        manifest_sha256=sha256(folder/'raw_manifest.json'),writer_source_sha256=manifest['writer_source_sha256'],
        validated_at=str(datetime.now().astimezone()),validation=validation,production_qualified=False)
    if(folder/'validation_seal.json').exists():raise FileExistsError('existing_validation_seal')
    atomic_checkpoint_json(folder/'validation_seal.json',seal)
    return seal


def load_sealed_checkpoint(output):
    """Reject external/symlink/mismatched files before any deserialization."""
    output=owned_output(output);folder=output/'checkpoint'
    paths=[folder/'raw_account.pkl.gz',folder/'raw_manifest.json',folder/'validation_seal.json',output/'run_context.json',output/'runner_used.py']
    if not paths[2].is_file():raise ValueError('checkpoint_unsealed')
    if folder.is_symlink()or any(path.is_symlink()or path.resolve().parent not in(folder.resolve(),output)for path in paths):
        raise ValueError('checkpoint_path_not_owned')
    manifest=json.loads(paths[1].read_text());seal=json.loads(paths[2].read_text());context=json.loads(paths[3].read_text())
    if(manifest.get('schema')!='stage031_raw_checkpoint_manifest_v1'or seal.get('schema')!='stage031_engine_validation_seal_v1'or
       context.get('schema')!='stage031_run_context_v1'or manifest.get('raw_filename')!='raw_account.pkl.gz'or
       manifest.get('output_directory')!=str(output)or context.get('output_directory')!=str(output)or
       manifest.get('writer')!='stage031_run_ordered_checkpoint.py'or manifest.get('parent_runner_sha256')!=PARENT_RUNNER_SHA or
       manifest.get('strategy_engine_sha256')!=FROZEN_MODULES or manifest.get('account_exports_only')is not True or
       any(row.get('arm')!='C_TS'or row.get('attempt')!=2 for row in(manifest,seal,context))):
        raise ValueError('checkpoint_manifest_identity_mismatch')
    if not context.get('run_id')or any(row.get('run_id')!=context['run_id']for row in(manifest,seal)):
        raise ValueError('checkpoint_run_id_mismatch')
    if(sha256(paths[1])!=seal.get('manifest_sha256')or sha256(paths[3])!=manifest.get('run_context_sha256')or
       sha256(paths[4])!=manifest.get('writer_source_sha256')or context.get('writer_source_sha256')!=manifest.get('writer_source_sha256')or
       seal.get('writer_source_sha256')!=manifest.get('writer_source_sha256')or seal.get('raw_sha256')!=manifest.get('raw_sha256')or
       any(seal.get('validation',{}).get(key)!=value for key,value in ENGINE_VALIDATION.items())):raise ValueError('checkpoint_binding_sha_mismatch')
    raw=paths[0].read_bytes()
    if hashlib.sha256(raw).hexdigest()!=manifest['raw_sha256']or len(raw)!=manifest['raw_bytes']:
        raise ValueError('checkpoint_raw_sha_mismatch')
    # All checks above precede pickle.loads, and use exactly these pinned bytes.
    payload=pickle.loads(gzip.decompress(raw))
    if payload.get('schema')!='stage031_raw_account_checkpoint_v1'or payload.get('run_context')!=context:
        raise ValueError('checkpoint_payload_identity_mismatch')
    return payload,dict(manifest=manifest,seal=seal,seal_sha256=sha256(paths[2]))


def reserve_export_destination(output):
    output=owned_output(output)
    if(output/'summary.json').exists()or(output/'export_success.json').exists()or any((output/'exports').glob('export_*/summary.json')):
        raise FileExistsError('existing_success_refusing_export_overwrite')
    folder=output/'exports';folder.mkdir(exist_ok=True)
    for index in range(1,10000):
        destination=folder/f'export_{index:03d}'
        try:destination.mkdir()
        except FileExistsError:continue
        return destination
    raise RuntimeError('export_attempt_limit')


def csv_rows(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as handle:
        return list(csv.DictReader(handle))


def bind_input(recorder,path,expected=None):
    path=Path(path).resolve()
    if expected is not None and sha256(path)!=expected:
        raise ValueError(f'ordered_input_fingerprint_changed:{path}')
    recorder.extra.add(path)
    recorder.record(path)
    # Explicit contracts may contain formats outside the old recorder allowlist.
    if str(path)not in recorder.files:
        recorder.files[str(path)]=dict(sha256=sha256(path),bytes=path.stat().st_size,
            accepted_stage251_match=False,explicit_stage031_input=True)
    return path


def read_ordered_features():
    """Read the independently accepted cache; never reconstruct FI or native rows."""
    summary_path=FEATURE_ROOT/'summary.json'
    manifest_path=FEATURE_ROOT/'input_manifest.json'
    for path,digest in ((summary_path,FEATURE_SUMMARY_SHA),(manifest_path,FEATURE_MANIFEST_SHA),
                        (FEATURE_REVIEW,FEATURE_REVIEW_SHA),(FEATURE_ROOT/'fi2_daily.csv',FI_SHA)):
        if sha256(path)!=digest:raise ValueError(f'ordered_feature_identity_changed:{path.name}')
    summary=json.loads(summary_path.read_text())
    manifest=json.loads(manifest_path.read_text())
    review=json.loads(FEATURE_REVIEW.read_text())
    if (review.get('independent_review')is False or not review.get('reviewer') or
        review.get('p0_findings')!=0 or review.get('p1_findings')!=0 or
        review.get('status')!='limited_pure_component_and_real_potential_demand_pass' or
        review.get('source_summary_sha256')!=FEATURE_SUMMARY_SHA or
        review.get('source_input_manifest_sha256')!=FEATURE_MANIFEST_SHA):
        raise ValueError('ordered_feature_independent_review_not_passed')
    if (summary.get('status')!='completed_pure_state_build_pending_independent_review' or
        summary.get('all_consumed_inputs_unchanged')is not True or
        summary.get('full_account_demand_or_fills')is not False or
        summary.get('financial_replays')!=0 or summary.get('state_start')!=prior.START or
        summary.get('end')!=prior.END):raise ValueError('ordered_feature_build_scope_changed')
    paths={summary_path,manifest_path,FEATURE_REVIEW}
    for name,digest in summary['artifacts'].items():
        path=FEATURE_ROOT/name
        if sha256(path)!=digest:raise ValueError(f'ordered_feature_artifact_changed:{name}')
        paths.add(path)
    for name,digest in review['source_files_sha256'].items():
        path=Path(__file__).with_name(name)
        if sha256(path)!=digest or manifest.get(str(path.resolve()))!=digest:
            raise ValueError(f'ordered_feature_source_changed:{name}')
        paths.add(path)
    if summary['artifacts'].get('input_manifest.json')!=FEATURE_MANIFEST_SHA or summary['artifacts'].get('fi2_daily.csv')!=FI_SHA:
        raise ValueError('ordered_feature_artifact_binding_changed')
    if sha256(CALENDAR)!=manifest.get(str(CALENDAR.resolve())):raise ValueError('ordered_real_calendar_changed')
    paths.add(CALENDAR)
    calendar=[date.fromisoformat(row['date']).isoformat()for row in csv_rows(CALENDAR)]
    if calendar!=sorted(set(calendar)) or len(calendar)!=summary['real_calendar_rows']:
        raise ValueError('invalid_ordered_real_calendar')
    next_days={day:calendar[index+1]if index+1<len(calendar)else None for index,day in enumerate(calendar)}
    fi={};ready_count=0
    for row in csv_rows(FEATURE_ROOT/'fi2_daily.csv'):
        day=date.fromisoformat(row['date']).isoformat();symbol=str(row['vt_symbol'])
        key=(day,symbol)
        if key in fi or day not in next_days:raise ValueError('duplicate_or_off_calendar_FI')
        ready=prior.ready_bool(row['ready'])
        value=float(row['fi2'])if str(row['fi2']).strip()else None
        if ready and(value is None or not math.isfinite(value)):raise ValueError('invalid_ready_FI')
        fi[key]=dict(ready=ready,fi2=value,reason=row['reason'],previous_date=row['previous_date'])
        ready_count+=ready
    if len(fi)!=summary['source_daily_rows'] or ready_count!=summary['FI_ready_rows']:
        raise ValueError('ordered_FI_cache_row_identity_changed')
    return fi,next_days,dict(summary_sha256=FEATURE_SUMMARY_SHA,input_manifest_sha256=FEATURE_MANIFEST_SHA,
        FI_sha256=FI_SHA,review_path=str(FEATURE_REVIEW),review_sha256=FEATURE_REVIEW_SHA,
        source_daily_rows=len(fi),FI_ready_rows=ready_count,real_calendar_rows=len(calendar),
        rebuilt_FI=False,rebuilt_native=False,full_account_demand_or_fills=False),paths


def read_reused_A0():
    if sha256(A0_REVIEW)!=A0_REVIEW_SHA:raise ValueError('accepted_A0_review_changed')
    review=json.loads(A0_REVIEW.read_text())
    if ('A0_attempt2'not in review.get('financial_accounts_reviewed',[]) or
        review.get('remaining_implementation_p0')!=0 or review.get('remaining_implementation_p1')!=0):
        raise ValueError('accepted_A0_review_not_passed')
    paths={A0_REVIEW}
    for name,digest in A0_SHA.items():
        path=A0/name
        if sha256(path)!=digest:raise ValueError(f'accepted_A0_artifact_changed:{name}')
        paths.add(path)
    summary=json.loads((A0/'summary.json').read_text())
    if summary.get('arm')!='A0' or summary.get('financial_replays')!=1:
        raise ValueError('accepted_A0_identity_changed')
    dates=[row['date'][:10]for row in csv_rows(A0/'daily.csv')]
    validate_daily_calendar(dates,dates)
    return dates,dict(path=str(A0),financial_replays_this_stage=0,artifact_sha256=A0_SHA,
                      review_path=str(A0_REVIEW),review_sha256=A0_REVIEW_SHA),paths


def validate_daily_calendar(actual,reference):
    actual=[str(value)[:10]for value in actual];reference=[str(value)[:10]for value in reference]
    if not actual or actual!=sorted(set(actual))or actual!=reference:
        raise ValueError('actual_daily_calendar_not_identical_to_accepted_A0')


@contextmanager
def replace_engine_class(module,engine_class):
    original=module.Stage847StopRetryEngine
    module.Stage847StopRetryEngine=engine_class
    try:yield
    finally:module.Stage847StopRetryEngine=original


def pending_intent_snapshot(item):
    """Project frozen intent evidence without native bar/history/state objects."""
    fields=('arm','intent_id','product','contract','epoch_id','setup_id','setup_day',
            'signal_day','execution_day','direction','trigger','weekly_asof','native_signal','rank')
    result={key:json_safe(item[key])for key in fields if key in item}
    plan=item.get('plan',{})
    result['frozen_plan']={key:json_safe(plan[key])for key in('volume','direction','signal','target_contract')if key in plan}
    sizing=plan.get('sizing',{})
    # Sizing snapshots are large; retain scalar q/S, predicted risk/margin and
    # capital observations only. Never traverse native objects through them.
    def scalar(value):
        if value is None or isinstance(value,(str,bool,int,float,date,datetime,Path)):return True
        return hasattr(value,'item')and getattr(value,'ndim',0)==0
    result['frozen_plan']['sizing']={key:json_safe(value)for key,value in sizing.items()
        if scalar(value)and(any(token in key for token in('risk','margin','equity','balance','capital'))or key in('selected_volume','stop_price'))}
    bar=plan.get('target_bar')
    if bar is not None:result['frozen_plan']['signal_bar_datetime']=str(bar.datetime)
    history=plan.get('history')
    if history is not None:result['frozen_plan']['signal_history_rows']=len(history)
    return result


@contextmanager
def capture_ordered_engine(engine_class):
    """Keep audit evidence on both normal completion and a failed bar callback."""
    names=('new_bars','calculate_result')
    originals={name:(name in engine_class.__dict__,getattr(engine_class,name))for name in names}
    capture=dict(decision=[],fill=[],execution=[],pending=[],actual_trade_identities=[])
    seen=[]
    def collect(engine):
        strategy=getattr(engine,'strategy',None)
        capture['decision']=[dict(row)for row in getattr(strategy,'ts_decision_audit',[])]
        capture['fill']=[dict(row)for row in getattr(strategy,'ts_fill_audit',[])]
        capture['execution']=[dict(row)for row in getattr(engine,'ts_execution_audit',[])]
        capture['pending']=[pending_intent_snapshot(row)for row in getattr(strategy,'ts_pending_intents',[])]
        capture['actual_trade_identities']=actual_trade_identities(engine.get_all_trades())
    def new_bars(engine,*args,**kwargs):
        if not seen:seen.append(engine)
        elif seen[0]is not engine:raise ValueError('ordered_capture_multiple_engines')
        return originals['new_bars'][1](engine,*args,**kwargs)
    def calculate(engine,*args,**kwargs):
        if not seen:seen.append(engine)
        try:return originals['calculate_result'][1](engine,*args,**kwargs)
        finally:collect(engine)
    engine_class.new_bars=new_bars;engine_class.calculate_result=calculate
    try:yield capture
    finally:
        if seen:collect(seen[0])
        for name,(local,original)in originals.items():
            if local:setattr(engine_class,name,original)
            else:delattr(engine_class,name)


def build_qualification_callback(holder,Offset,Direction):
    """A full-session intent stub is never registered as a financial order."""
    def qualify(engine,item,bar):
        gate=holder.get('gate')
        if gate is None:raise RuntimeError('ordered_intent_gate_not_bound')
        direction=item.get('direction')
        if direction not in(-1,1)or isinstance(direction,bool):raise ValueError('invalid_ordered_intent_direction')
        volume=item['plan']['volume']
        if isinstance(volume,bool)or not math.isfinite(float(volume))or int(volume)!=float(volume)or int(volume)<=0:
            raise ValueError('invalid_frozen_ordered_intent_volume')
        trigger=float(item['trigger'])
        if not math.isfinite(trigger)or trigger<=0:raise ValueError('invalid_ordered_trigger')
        stub=SimpleNamespace(vt_orderid='TS.INTENT.'+str(item['intent_id']),vt_symbol=str(item['contract']),
            offset=Offset.OPEN,direction=Direction.LONG if direction==1 else Direction.SHORT,
            price=trigger,volume=int(volume),traded=0,status='conditional_not_order')
        gate.ensure(engine,stub,bar)
    return qualify


def read_reused_anchor(wait_gate,recorder):
    specs=[(ANCHOR_REQUEST,ANCHOR_REQUEST_ID,ANCHOR_RECEIPT,ANCHOR_RECEIPT_SHA,
            'cu2609.SHFE','2026-08-13T21:00:00'),
           (LINE/'outputs/stage028_ordered_account/C_TS/data_wait/request_d9bd8bda7ffa8f9e11560ed7ceccdf58fb49fb1dd8c23a00bb448474708f79ff/request.json',
            'd9bd8bda7ffa8f9e11560ed7ceccdf58fb49fb1dd8c23a00bb448474708f79ff',
            LINE/'outputs/stage029_independent_delivery/request_d9bd8bda7ffa8f9e11560ed7ceccdf58fb49fb1dd8c23a00bb448474708f79ff/delivery_receipt.json',
            '09444de4ec525a874b5f03caacfe0742836c3a4f8b4d6ba0aec0eea69d1303fa','OI009.CZCE','2020-07-14T21:00:00')]
    parts=[];rights=set();audits=[]
    for request_path,request_id,receipt_path,receipt_sha,symbol,timestamp in specs:
        if sha256(receipt_path)!=receipt_sha:raise ValueError('reused_anchor_receipt_changed')
        request=json.loads(request_path.read_text());receipt=json.loads(receipt_path.read_text())
        if request.get('request_sha256')!=request_id or wait_gate.request_sha256(request)!=request_id:
            raise ValueError('reused_anchor_request_changed')
        if receipt.get('request_path')!=str(request_path)or receipt.get('request_file_sha256')!=sha256(request_path):
            raise ValueError('reused_anchor_request_file_not_review_bound')
        bind_input(recorder,receipt_path,receipt_sha)
        for path,digest in receipt['source_fingerprints'].items():bind_input(recorder,path,digest)
        data,full,anchors,audit=wait_gate._read_delivery(request,wait_gate.QualifiedDelivery(receipt_path,receipt_sha))
        expected={(symbol,wait_gate.pd.Timestamp(timestamp))}
        if full or anchors!=expected or len(data)!=1 or anchors&rights:raise ValueError('reused_anchor_rights_would_expand')
        parts.append(data);rights.update(anchors)
        audits.append(dict(audit,request_path=str(request_path),request_sha256=request_id,
            qualification='one_exact_anchor_only_not_full_session',financial_replays=0,network_calls=0))
    return wait_gate.pd.concat(parts,ignore_index=True),rights,dict(deliveries=audits,exact_anchor_keys=2,full_session_keys=0,network_calls=0)


@contextmanager
def temporary_reused_anchor(s901,anchor_data,anchor_keys):
    """Append absent reviewed keys, compare old keys exactly, grant no full right."""
    import numpy as np
    import pandas as pd
    import stage002_local_minute_overlay as local_minutes
    original=s901._load_stage861_full_minute_bars
    added_keys=set()
    def load(symbols):
        base=local_minutes.normal_times(original(symbols))
        extra=anchor_data.loc[anchor_data.vt_symbol.astype(str).isin(symbols)].copy()
        if extra.empty:return base
        old=base.set_index(['vt_symbol','bar_datetime'])
        append=[]
        for row in extra.to_dict('records'):
            key=(str(row['vt_symbol']),pd.Timestamp(row['bar_datetime']))
            if key not in anchor_keys:raise ValueError('reused_anchor_data_scope_changed')
            if key in old.index:
                present=old.loc[key,local_minutes.VALUES]
                if getattr(present,'ndim',1)!=1 or not np.array_equal(
                    present.to_numpy(dtype=float),np.asarray([row[name]for name in local_minutes.VALUES],dtype=float)):
                    raise ValueError('reused_anchor_old_value_conflict')
            else:
                row['bar_date']=key[1].normalize()
                row['minute_source']='stage028_independently_qualified_anchor_only'
                append.append(row);added_keys.add(key)
        if append:
            base=pd.concat([base,pd.DataFrame(append)],ignore_index=True,sort=False)
            base=base.sort_values(['vt_symbol','bar_datetime']).reset_index(drop=True)
        if local_minutes.minute_keys(base).has_duplicates:raise ValueError('reused_anchor_duplicate_key')
        return base
    s901._load_stage861_full_minute_bars=load
    try:yield added_keys
    finally:s901._load_stage861_full_minute_bars=original


def ordered_predicates(full,anchor,added_anchor_keys,reused_anchor_keys):
    # Newly appended anchors cannot become full-session rights merely because
    # their source tag is newer than Stage022's explicit source859 exclusion.
    def full_key(symbol,stamp):
        return (str(symbol),stamp)not in added_anchor_keys and full(symbol,stamp)
    def anchor_key(symbol,stamp):
        return (str(symbol),stamp)in reused_anchor_keys or anchor(symbol,stamp)
    return full_key,anchor_key


def write_ordered_audits(output,capture,ordered,wait_audit,resolver_audit,qualification_audit):
    import pandas as pd
    defaults={
        'ordered_gate_audit.csv':(ordered.get('decision',[]),['date','product','decision','cancel_reason']),
        'ordered_fill_audit.csv':(ordered.get('fill',[]),['intent_id','signal_day','execution_day','fill_price','volume']),
        'ordered_execution_audit.csv':(ordered.get('execution',[]),['intent_id','event','execution_datetime']),
        'minute_scan_requests.csv':(capture.get('minute_requests',[]),['vt_symbol','trading_date','coverage_status','missing_bar_count']),
        'execution_anchor_requests.csv':(capture.get('anchor_requests',[]),['vt_symbol','execution_trade_date','expected_start']),
    }
    for name,(rows,fields)in defaults.items():
        frame=pd.DataFrame(rows)if rows else pd.DataFrame(columns=fields)
        frame.to_csv(output/name,index=False,encoding='utf-8-sig')
    write_json(output/'qualified_wait_audit.json',dict(gate=wait_audit,resolver=resolver_audit,initial_qualification=qualification_audit))
    # JSON retains any structured diagnostic fields which CSV cannot represent.
    write_json(output/'ordered_audits.json',ordered)




def export_checkpoint(output,destination,*,metrics_function=None,export_only=False):
    """Pure account-table export from an already sealed same-engine snapshot."""
    import pandas as pd
    output=owned_output(output);destination=Path(destination).resolve()
    if destination!=output and(destination.parent!=output/'exports'or not destination.name.startswith('export_')):
        raise ValueError('export_destination_not_owned')
    if(destination/'summary.json').exists():raise FileExistsError('existing_success_refusing_export_overwrite')
    payload,checkpoint=load_sealed_checkpoint(output)
    combined=payload['combined'];frames={name:frame.copy()for name,frame in payload['frames'].items()}
    capture=payload['capture'];ordered=payload['ordered'];preflight=payload['preflight'];context=payload['run_context']
    if destination!=output:
        for name in('runner_used.py','protocol_used.md','entry_contract_used.md','plan_used.md','holding_contract_used.md',
                     'data_stack_manifest.json','stage028_ordered_strategy.py','stage028_ordered_engine.py','preflight_used.json','run_context.json'):
            (destination/name).write_bytes((output/name).read_bytes())
    write_ordered_audits(destination,capture,ordered,payload.get('wait_audit',[]),payload.get('resolver_audit',[]),payload.get('qualification_audit',{}))
    clock,usage=build_execution_clock(capture,payload['actual_trade_identities'])
    trades=prior.canonical_trade_enums(frames['trades'])
    if trades.empty:raise ValueError('no_trades_not_a_successful_candidate')
    if trades.trade_id.duplicated().any()or set(trades.trade_id)!=set(clock.trade_id):raise ValueError('account_trade_clock_identity_mismatch')
    sources=clock.trade_id.map(usage.set_index('trade_id').price_source).fillna('')
    synthetic=clock.offset.ne('开')&sources.str.startswith('stage')
    clock.loc[synthetic,'exit_reason']=sources[synthetic]
    frames['trades']=prior.attach_trading_dates(trades,clock)
    for name,frame in frames.items():
        if frame.empty and not len(frame.columns):frame=pd.DataFrame(columns=['date','vt_symbol','event','reason'])
        frame=frame.copy();frame['research_arm']='C_TS';frame['production_qualified']=False
        frame.to_csv(destination/f'{name}.csv',index=False,encoding='utf-8-sig')
    combined.to_csv(destination/'daily.csv',index=False,encoding='utf-8-sig')
    clock.to_csv(destination/'execution_clock.csv',index=False,encoding='utf-8-sig')
    usage.to_csv(destination/'execution_proxy_usage.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(capture['equity']).to_csv(destination/'internal_equity_daily.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(payload['actual_trade_identities']).to_csv(destination/'actual_trade_identities.csv',index=False,encoding='utf-8-sig')
    if metrics_function is None:
        import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
        metrics_function=s650._metrics
    stats=metrics_function(combined,SimpleNamespace(**payload['spec']['capital']),1.0)
    stats.update(result_scope=RESULT_SCOPE,production_qualified=False)
    counts=dict(decision_rows=len(ordered['decision']),decision_counts=dict(Counter(str(row.get('decision',''))for row in ordered['decision'])),
        fill_audit_rows=len(ordered['fill']),execution_audit_rows=len(ordered['execution']),pending_intents=len(ordered['pending']))
    minutes=pd.DataFrame(capture['minute_requests'])
    minute_summary=dict(strict_required=True,request_rows=len(minutes),captured_bar_failures=0,
        coverage_status_counts=dict(Counter(minutes.get('coverage_status',[]))),missing_bar_count=0)
    provenance=dict(status='completed_pending_independent_review',arm='C_TS',attempt=2,started_at=context['started_at'],
        completed_at=datetime.now().astimezone(),elapsed_seconds=payload.get('engine_elapsed_seconds'),result_scope=RESULT_SCOPE,production_qualified=False,
        correctness_code_sha256=prior.ACCEPTED_CODE,active_parameter_identity=preflight.get('active_parameter_identity'),
        input_fingerprints=payload['input_fingerprints'],all_consumed_inputs_unchanged_during_run=True,
        minute_input_sha256=prior.EXPECTED_MINUTE,weekly_feature_sha256=prior.EXPECTED_FEATURES,ordered_feature_cache=preflight.get('ordered_feature_cache'),
        protocol_sha256=sha256(output/'protocol_used.md'),entry_contract_sha256=sha256(output/'entry_contract_used.md'),
        holding_contract_sha256=sha256(output/'holding_contract_used.md'),source_adapter_sha256=sha256(output/'runner_used.py'),data_stack_sha256=STACK_SHA,
        source_modules_sha256=FROZEN_MODULES,execution_contract=EXECUTION_CONTRACT,
        only_candidate_delta='unchanged Stage028 ordered entry and post-entry holding view; Stage031 changes actual trade identity export and durable checkpoint only',
        original_u_close_quantity_and_stop_frozen=True,fill_time_broker_budget_rechecked=False,actual_gap_risk_bounded_by_u_gate=False,
        data_adapter_changed=True,alpha_changed_from_C0=True,alpha_changed_from_Stage028=False,strict_minutes=True,captured_bar_failure_count=0,
        actual_settings_equal_accepted_A=True,parameters_equal_accepted_A=True,actual_daily_dates_equal_accepted_A0=True,
        reused_A0=preflight.get('reused_A0'),reused_anchor=preflight.get('reused_anchor'),vendor_swallowed_bar_exception_guard=True,
        source_head=preflight.get('runtime',{}).get('source_head'),runtime=preflight.get('runtime'),model_runtime_smoke=preflight.get('model_runtime_smoke'),
        local_minute_overlay=preflight.get('local_minute_overlay'),financial_replays=1,broker_connections=0,order_api_count=0,cancel_api_count=0,
        checkpoint=checkpoint,export_only=export_only,financial_replays_this_export_process=0 if export_only else 1,
        result_origin='same_engine_sealed_account_snapshot',exporter_source_sha256=sha256(Path(__file__)),exported_at=datetime.now().astimezone())
    for name,value in(('actual_strategy_settings.json',payload['actual']),('effective_parameters.json',payload['parameters']),
                      ('input_manifest.json',payload['input_fingerprints']),('run_provenance.json',provenance),('metrics.json',stats)):
        write_json(destination/name,value)
    summary=dict(status=provenance['status'],arm='C_TS',attempt=2,result_scope=RESULT_SCOPE,statistics=stats,ordered_counts=counts,
        strict_minutes=minute_summary,actual_settings=payload['actual'],input_fingerprints=payload['input_fingerprints'],
        ordered_feature_cache=preflight.get('ordered_feature_cache'),reused_A0=preflight.get('reused_A0'),execution_contract=EXECUTION_CONTRACT,
        financial_replays=1,financial_replays_this_export_process=0 if export_only else 1,production_qualified=False,
        output_directory=str(destination),model_runtime_smoke=preflight.get('model_runtime_smoke'),broker_connections=0,order_api_calls=0,cancel_api_calls=0,
        result_origin='same_engine_sealed_account_snapshot',checkpoint_raw_sha256=checkpoint['manifest']['raw_sha256'])
    write_json(destination/'summary.json',summary)
    atomic_checkpoint_json(output/'export_success.json',dict(status=summary['status'],source=str(destination),
        summary_sha256=sha256(destination/'summary.json'),raw_sha256=checkpoint['manifest']['raw_sha256'],run_id=context['run_id']))
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm',choices=['C_TS'],default='C_TS')
    parser.add_argument('--data-stack-manifest',type=Path,default=prior.STACK_PATH)
    parser.add_argument('--data-stack-sha256',default=STACK_SHA)
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--preflight',action='store_true');action.add_argument('--run',action='store_true')
    action.add_argument('--export-only',action='store_true')
    args=parser.parse_args()
    if args.data_stack_sha256!=STACK_SHA:parser.error('only frozen accepted Stage022 data stack is allowed')
    arm=args.arm;output=OUTPUT/arm;shared=OUTPUT/'shared_empty_signal_inputs'
    if args.run and output.exists():raise FileExistsError(f'existing_ordered_run_refusing_repeat:{output}')
    # configure_runtime must precede importing any numerical or vn.py module.
    previous_output=prior.OUTPUT
    try:
        prior.OUTPUT=OUTPUT
        prior.configure_runtime(shared)
    finally:prior.OUTPUT=previous_output
    if args.export_only:
        destination=reserve_export_destination(output)
        try:
            summary=export_checkpoint(output,destination,export_only=True)
            print(json.dumps(json_safe(dict(status=summary['status'],source=str(destination),financial_replays_this_process=0)),ensure_ascii=False))
        except BaseException as error:
            write_json(destination/'export_failure.json',dict(error=repr(error),failed_at=datetime.now().astimezone(),financial_replays_this_process=0))
            raise
        return
    if sha256(Path(__file__).with_name('stage028_run_ordered.py'))!=PARENT_RUNNER_SHA:raise ValueError('frozen_parent_runner_changed')
    for name,digest in FROZEN_MODULES.items():
        if sha256(Path(__file__).with_name(name))!=digest:raise ValueError(f'frozen_alpha_module_changed:{name}')
    minute_overlay=prior.read_data_stack(args.data_stack_manifest,STACK_SHA)
    if sha256(prior.SOURCE001)!=prior.SOURCE001_SHA:raise ValueError('source001_changed')
    for name,digest in prior.ACCEPTED_CODE.items():
        if sha256(ROOT/name)!=digest:raise ValueError(f'accepted_correctness_code_changed:{name}')
    if sha256(prior.FEATURES)!=prior.EXPECTED_FEATURES:raise ValueError('weekly_features_changed')
    weekly=prior.WeeklyLookup.read(prior.FEATURES)
    fi,next_days,feature_audit,feature_paths=read_ordered_features()
    reference_days,A0_audit,A0_paths=read_reused_A0()
    accepted=json.loads((prior.OLD/'input_manifest.json').read_text())
    recorder=prior.InputRecorder(accepted)
    recorder.extra.update(Path(path).resolve()for path in minute_overlay['source_fingerprints'])
    recorder.extra.update(feature_paths|A0_paths|{Path(__file__).resolve(),PROTOCOL,ENTRY_CONTRACT,PLAN,HOLDING_CONTRACT,Path(__file__).with_name('stage028_run_ordered.py'),
        args.data_stack_manifest.resolve(),prior.SOURCE001,prior.SOURCE_PROTOCOL,
        prior.DESIGN/'source_stage001_original.py',prior.DESIGN/'source_diff.patch'})
    for name in ('stage028_ordered_strategy.py','stage028_ordered_engine.py'):
        recorder.extra.add(Path(__file__).with_name(name))
    sys.addaudithook(recorder.audit);recorder.enabled=True
    for path in list(recorder.extra):bind_input(recorder,path)

    import pandas as pd
    import vnpy_portfoliostrategy
    from vnpy.trader.constant import Offset,Direction
    import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
    import stage002_local_minute_overlay as local_minutes
    import stage016_source859_qualification as qualified_delta
    import stage021_blocking_data_gate as wait_gate
    from stage028_ordered_strategy import build_ordered_strategy
    from stage028_ordered_engine import build_ordered_engine
    overlay_parts=[]
    for item in minute_overlay['overlays']:
        frame=local_minutes.normal_times(pd.read_csv(item['path']))
        frame['qualified_stack_layer']=item['stage'];overlay_parts.append(frame)
    overlay_frame=pd.concat(overlay_parts,ignore_index=True,sort=False);del overlay_parts
    if overlay_frame.duplicated(['vt_symbol','bar_datetime']).any():raise ValueError('data_stack_append_key_overlap')
    correction=minute_overlay['outer_correction']
    qualified=qualified_delta.read_qualified_delta(correction['summary_path'],correction['summary_sha256'],correction['review_path'],correction['review_sha256'])
    reused_anchor,anchor_rights,anchor_audit=read_reused_anchor(wait_gate,recorder)
    demand=pd.read_csv(minute_overlay['demand_path'])
    calendar=pd.DatetimeIndex(pd.to_datetime(pd.read_csv(local_minutes.MAPPING,usecols=['date']).date).drop_duplicates().sort_values())
    from qmt_backtest_runtime_guard import assert_stage196_database_sentinels
    from qmt_roll_official_baseline_identity import assert_official_checkout_matches_active_material
    from qmt_roll_official_strategy_material_resolver import load_active_material_release,assert_runtime_materials_match_checkout,verify_material_file,ActiveMaterialError
    identity=asdict(assert_official_checkout_matches_active_material(ROOT))
    if identity!=prior.IDENTITY:raise ValueError('formal_parameter_identity_changed')
    active=load_active_material_release(ROOT/'official_strategy_materials/CURRENT.json',repo_root=ROOT)
    drift=''
    try:assert_runtime_materials_match_checkout(active)
    except ActiveMaterialError as error:drift=str(error)
    allowed=set(prior.ACCEPTED_CODE)|{'skills/futures-live-execution-sop/SKILL.md'}
    for row in active.manifest['files']:
        name=str(row.get('source_path',''))
        if row.get('role')not in('runtime_code','strategy_config','operational_config')or name.startswith('promotion_source:')or name in allowed:continue
        verify_material_file(ROOT/name,row)
    assert_stage196_database_sentinels()
    if not Path(vnpy_portfoliostrategy.__file__).resolve().is_relative_to(prior.VENDOR):raise ValueError('portfolio_vendor_changed')
    if sha256(s901.s861.FULL_MINUTE_BARS_PATH)!=prior.EXPECTED_MINUTE:raise ValueError('accepted_minute_cache_changed')
    recorder.record(s901.s861.FULL_MINUTE_BARS_PATH)
    metadata=s901.s513._metadata()
    import qmt_roll_ai_selection_pairwise_runtime as pairwise
    model_smoke=prior.model_runtime_smoke(pairwise.DEFAULT_MODEL_PATH,pairwise.DEFAULT_SUMMARY_PATH)
    if s901.build_official_live_strategy_overrides().get('enable_stage847_half_r_stop_retry')is not True:raise ValueError('half_r_must_remain_enabled')
    external=Path(s901.s513._c3_overrides(pd.Timestamp(prior.START).to_pydatetime())['supply_demand_signal_path'])
    if external.parent!=shared or external.exists():raise ValueError('historical_supply_demand_input_mismatch')
    ai_path=s901.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH
    sys.path.insert(0,str(ROOT/'research/lines/futures_trend_rollover_shape_same_volume/tools'))
    from stage249_historical_replay import audit_historical_ai_pool
    ai_audit=audit_historical_ai_pool(ai_path,s901._required_ai_eval_dates(pd.Timestamp(prior.START),pd.Timestamp(prior.END)))
    if ai_audit['eligibility_sha256']!=accepted[str(Path(ai_path).relative_to(ROOT))]:raise ValueError('historical_ai_changed')
    old_settings=json.loads((prior.OLD/'actual_strategy_settings.json').read_text())[0]['actual']
    reference_shared=Path(old_settings['supply_demand_signal_path']).parent
    profile=prior.capture_formal_profile(s901,metadata,pd.Timestamp(prior.START),pd.Timestamp(prior.END))
    predicted_parameters=dict(spec=asdict(profile['spec']),contract_sizes=metadata['sizes'],rates=metadata['rates'],slippages=metadata['slippages'],priceticks=metadata['priceticks'])
    reference=json.loads((prior.OLD/'effective_parameters.json').read_text())
    normal=lambda value:prior.normalize_reference(json_safe(value),shared,reference_shared)
    if normal(predicted_parameters)!=normal(reference):raise ValueError('preflight_effective_parameters_drift_from_accepted_A')
    predicted_settings=s901.s847.s827.s772._build_setting(metadata=metadata,spec=profile['spec'],base_c3_overrides=dict(s901.s513._c3_overrides(pd.Timestamp(prior.START).to_pydatetime())),start=pd.Timestamp(prior.START))
    if normal({key:value for key,value in predicted_settings.items()if key in old_settings})!=normal(old_settings):
        raise ValueError('preflight_requested_settings_drift_from_accepted_A')
    strategy=build_ordered_strategy(s901.s847.QmtRollPortfolioStrategyStage847C9StopRetry,weekly,fi,next_days,arm=arm)
    strategy.stage827_require_complete_minutes=True
    holder={}
    newengine=build_ordered_engine(s901.s847.Stage847StopRetryEngine,build_qualification_callback(holder,Offset,Direction))
    runtime_code={}
    for module in list(sys.modules.values()):
        filename=getattr(module,'__file__',None)
        if not filename:continue
        path=Path(filename).resolve()
        if path.suffix=='.py'and path.is_file()and(path.is_relative_to(prior.PROJECT)or path.is_relative_to(prior.VENDOR)or path.parent==Path(__file__).parent):
            bind_input(recorder,path);runtime_code[str(path)]=recorder.files[str(path)]['sha256']
    preflight=dict(status='passed_offline_preflight_no_financial_replay',arm=arm,attempt=2,result_scope=RESULT_SCOPE,
        stage='Stage031',alpha_changed_from_Stage028=False,parent_runner_sha256=PARENT_RUNNER_SHA,source_modules_sha256=FROZEN_MODULES,
        execution_contract=EXECUTION_CONTRACT,financial_replays=0,production_qualified=False,
        formal_identity_gate='not_passed_for_production',active_parameter_identity=identity,
        runtime_material_drift=drift,accepted_correctness_code=prior.ACCEPTED_CODE,
        input_fingerprints=recorder.files,weekly_feature_sha256=prior.EXPECTED_FEATURES,
        ordered_feature_cache=feature_audit,reused_A0=A0_audit,reused_anchor=anchor_audit,
        minute_sha256=prior.EXPECTED_MINUTE,strict_minutes=True,period=[prior.START,prior.END],capital=150000,
        shared_empty_signal_dir=str(shared),metadata_contract_count=len(metadata['vt_symbols']),
        ai_pool_audit=ai_audit,runtime=dict(python=sys.executable,portfolio=vnpy_portfoliostrategy.__file__,pandas=pd.__version__,
            source_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()),
        parameters_equal_accepted_A=True,requested_settings_equal_accepted_A=True,runtime_code_sha256=runtime_code,
        model_runtime_smoke=model_smoke,local_minute_overlay=minute_overlay,data_stack_sha256=STACK_SHA,
        data_adapter='Stage022 accepted stack; Stage016 usage-limited source859; two reviewed anchor-only keys; Stage021 same-engine full conditional wait',
        wait_seconds_max=prior.WAIT_SECONDS,whole_run_seconds_max=prior.RUN_SECONDS,
        strategy_class=strategy.__name__,engine_class=newengine.__name__,
        broker_connections=0,order_api_calls=0,cancel_api_calls=0)
    if args.preflight:
        recorder.verify()
        folder=OUTPUT/'preflight';folder.mkdir(parents=True,exist_ok=True)
        write_json(folder/'C_TS.json',preflight)
        print(json.dumps({key:preflight[key]for key in('status','arm','financial_replays','production_qualified','strict_minutes','strategy_class','engine_class')}))
        return

    prior.reserve_attempt(output)
    started=datetime.now().astimezone();began=time.monotonic()
    run_context=new_run_context(output,started)
    atomic_checkpoint_json(output/'run_context.json',run_context)
    raw_manifest=None
    capture={};ordered={};actual=[];wait_audit=[];resolver_audit=[];qualification_audit={}
    resolver=prior.FileWaitResolver(output/'data_wait',recorder,resolver_audit,began)
    try:
        for source,name in ((Path(__file__),'runner_used.py'),(PROTOCOL,'protocol_used.md'),(ENTRY_CONTRACT,'entry_contract_used.md'),(PLAN,'plan_used.md'),
                            (HOLDING_CONTRACT,'holding_contract_used.md'),
                            (args.data_stack_manifest,'data_stack_manifest.json')):
            (output/name).write_bytes(source.read_bytes())
            if sha256(output/name)!=sha256(source):raise ValueError(f'run_input_snapshot_failed:{name}')
        for name in('stage028_ordered_strategy.py','stage028_ordered_engine.py'):
            (output/name).write_bytes(Path(__file__).with_name(name).read_bytes())
        write_json(output/'preflight_used.json',preflight)
        with (output/'engine.log').open('w',buffering=1)as log,redirect_stdout(log),redirect_stderr(log):
            with prior.whole_run_budget(),local_minutes.temporary_minute_overlay(s901,overlay_frame),qualified_delta.temporary_qualified_minute_delta(s901,qualified),temporary_reused_anchor(s901,reused_anchor,anchor_rights)as added_anchor_keys,prior.replace_strategy_class(s901.s847,strategy),replace_engine_class(s901.s847,newengine),prior.capture_actual_settings(newengine)as actual,prior.capture_engine(newengine)as capture,capture_ordered_engine(newengine)as ordered:
                s901._ensure_c9_minute_bars(metadata)
                full,anchor,qualification_audit=prior.inherited_qualification_predicates(s901._FULL_MINUTE_BY_SYMBOL_CACHE,qualified.allowed_keys,demand,calendar)
                full,anchor=ordered_predicates(full,anchor,added_anchor_keys,anchor_rights)
                qualification_audit.update(reused_exact_anchor=anchor_audit,appended_anchor_keys=len(added_anchor_keys),anchor_only_rights=len(anchor_rights))
                with wait_gate.qualified_wait_scope(newengine,resolver,wait_audit,qualified_existing_keys=full,qualified_anchor_existing_keys=anchor)as gate:
                    holder['gate']=gate
                    try:
                        combined,frames,spec=s901._run_live_c9(metadata,pd.Timestamp(prior.START),pd.Timestamp(prior.END))
                        parameters=dict(spec=asdict(spec),contract_sizes=metadata['sizes'],rates=metadata['rates'],slippages=metadata['slippages'],priceticks=metadata['priceticks'])
                        raw_manifest=save_raw_checkpoint(output,dict(combined=combined,frames=frames,capture=capture,
                            actual_trade_identities=ordered['actual_trade_identities'],ordered=ordered,actual=actual,parameters=parameters,
                            spec=asdict(spec),preflight=preflight,input_fingerprints=dict(recorder.files),run_context=run_context,
                            engine_completed_at=datetime.now().astimezone(),engine_elapsed_seconds=time.monotonic()-began,
                            wait_audit=wait_audit,resolver_audit=resolver_audit,qualification_audit=qualification_audit))
                    finally:holder.pop('gate',None)
        if len(actual)!=1 or actual[0]['supply_demand_signal_rows']!=0:raise ValueError('unexpected_actual_strategy_or_supply_rows')
        if normal(actual[0]['actual'])!=normal(old_settings):
            write_json(output/'actual_strategy_settings_mismatch.json',dict(actual=actual[0]['actual'],reference=old_settings))
            raise ValueError('actual_settings_drift_from_accepted_A')
        parameters=dict(spec=asdict(spec),contract_sizes=metadata['sizes'],rates=metadata['rates'],slippages=metadata['slippages'],priceticks=metadata['priceticks'])
        if normal(parameters)!=normal(reference):
            write_json(output/'effective_parameters_mismatch.json',parameters)
            raise ValueError('effective_parameters_drift_from_accepted_A')
        validate_daily_calendar(pd.to_datetime(combined.date).dt.strftime('%Y-%m-%d').tolist(),reference_days)
        if capture['failures']:raise ValueError('captured_bar_failures_cannot_report_performance')
        minutes=pd.DataFrame(capture['minute_requests'])
        missing=int(pd.to_numeric(minutes.get('missing_bar_count',pd.Series(dtype=float)),errors='coerce').fillna(0).sum())
        if missing:raise ValueError('strict_minutes_incomplete')
        recorder.verify()
        if any(shared.iterdir()):raise ValueError('historical_shared_signal_input_was_written')
        for name,digest in prior.ACCEPTED_CODE.items():
            if sha256(ROOT/name)!=digest:raise ValueError(f'accepted_correctness_code_changed_during_run:{name}')
        seal_checkpoint(output,raw_manifest,dict(engine_returned=True,actual_settings_equal_accepted_A=True,
            parameters_equal_accepted_A=True,actual_daily_dates_equal_accepted_A0=True,captured_bar_failures=0,
            strict_minute_missing_bars=0,all_consumed_inputs_unchanged_during_run=True,
            frozen_correctness_code_unchanged=True,historical_shared_signal_input_empty=True))
        summary=export_checkpoint(output,output,export_only=False)
        print(json.dumps(json_safe(dict(status=summary['status'],arm=arm,attempt=2,statistics=summary['statistics'])),ensure_ascii=False))
    except BaseException as error:
        recorder.enabled=False
        audit_export_error=''
        try:write_ordered_audits(output,capture,ordered,wait_audit,resolver_audit,qualification_audit)
        except Exception as audit_error:audit_export_error=repr(audit_error)
        write_json(output/'run_failure.json',dict(audit_export_error=audit_export_error,status='failed_closed_no_accepted_performance',arm=arm,attempt=2,result_scope=RESULT_SCOPE,
            run_id=run_context['run_id'],raw_checkpoint=raw_manifest,validation_seal_exists=(output/'checkpoint/validation_seal.json').is_file(),
            error=repr(error),started_at=started,failed_at=datetime.now().astimezone(),financial_replay_attempts=1,production_qualified=False,
            input_fingerprints=recorder.files,captured_bar_failures=capture.get('failures',[]),actual_settings=actual,
            minute_requests=capture.get('minute_requests',[]),ordered_audits=ordered,local_minute_overlay=minute_overlay,
            qualified_wait_gate_audit=wait_audit,resolver_audit=resolver_audit,initial_qualification=qualification_audit,
            ordered_feature_cache=feature_audit,reused_A0=A0_audit,reused_anchor=anchor_audit,data_stack_sha256=STACK_SHA,
            execution_contract=EXECUTION_CONTRACT,order_api_count=0,cancel_api_count=0))
        raise


if __name__=='__main__':main()
