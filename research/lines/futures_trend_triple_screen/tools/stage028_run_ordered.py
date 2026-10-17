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
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import stage022_run_c0_qualified_wait as prior

ROOT, LINE = prior.ROOT, prior.LINE
OUTPUT = LINE/'outputs/stage028_ordered_account'
PROTOCOL = LINE/'stages/20261018_0234_stage028_conditional_execution_contract.md'
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
            accepted_stage251_match=False,explicit_stage028_input=True)
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
    capture=dict(decision=[],fill=[],execution=[],pending=[])
    seen=[]
    def collect(engine):
        strategy=getattr(engine,'strategy',None)
        capture['decision']=[dict(row)for row in getattr(strategy,'ts_decision_audit',[])]
        capture['fill']=[dict(row)for row in getattr(strategy,'ts_fill_audit',[])]
        capture['execution']=[dict(row)for row in getattr(engine,'ts_execution_audit',[])]
        capture['pending']=[pending_intent_snapshot(row)for row in getattr(strategy,'ts_pending_intents',[])]
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
    if sha256(ANCHOR_RECEIPT)!=ANCHOR_RECEIPT_SHA:raise ValueError('reused_anchor_receipt_changed')
    request=json.loads(ANCHOR_REQUEST.read_text())
    if request.get('request_sha256')!=ANCHOR_REQUEST_ID or wait_gate.request_sha256(request)!=ANCHOR_REQUEST_ID:
        raise ValueError('reused_anchor_request_changed')
    receipt=json.loads(ANCHOR_RECEIPT.read_text())
    if receipt.get('request_path')!=str(ANCHOR_REQUEST)or receipt.get('request_file_sha256')!=sha256(ANCHOR_REQUEST):
        raise ValueError('reused_anchor_request_file_not_review_bound')
    bind_input(recorder,ANCHOR_RECEIPT,ANCHOR_RECEIPT_SHA)
    for path,digest in receipt['source_fingerprints'].items():bind_input(recorder,path,digest)
    data,full,anchors,audit=wait_gate._read_delivery(request,wait_gate.QualifiedDelivery(ANCHOR_RECEIPT,ANCHOR_RECEIPT_SHA))
    expected={('cu2609.SHFE',wait_gate.pd.Timestamp('2026-08-13T21:00:00'))}
    if full or anchors!=expected or len(data)!=1:raise ValueError('reused_anchor_rights_would_expand')
    return data,anchors,dict(audit,request_path=str(ANCHOR_REQUEST),request_sha256=ANCHOR_REQUEST_ID,
        qualification='one_exact_anchor_only_not_full_session',financial_replays=0,network_calls=0)


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


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm',choices=['C_TS'],default='C_TS')
    parser.add_argument('--data-stack-manifest',type=Path,default=prior.STACK_PATH)
    parser.add_argument('--data-stack-sha256',default=STACK_SHA)
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--preflight',action='store_true');action.add_argument('--run',action='store_true')
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
    recorder.extra.update(feature_paths|A0_paths|{Path(__file__).resolve(),PROTOCOL,PLAN,HOLDING_CONTRACT,
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
    preflight=dict(status='passed_offline_preflight_no_financial_replay',arm=arm,result_scope=RESULT_SCOPE,
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
        data_adapter='Stage022 accepted stack; Stage016 usage-limited source859; one reviewed anchor; Stage021 same-engine full conditional wait',
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
    capture={};ordered={};actual=[];wait_audit=[];resolver_audit=[];qualification_audit={}
    resolver=prior.FileWaitResolver(output/'data_wait',recorder,resolver_audit,began)
    try:
        for source,name in ((Path(__file__),'runner_used.py'),(PROTOCOL,'protocol_used.md'),(PLAN,'plan_used.md'),
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
                    try:combined,frames,spec=s901._run_live_c9(metadata,pd.Timestamp(prior.START),pd.Timestamp(prior.END))
                    finally:holder.pop('gate',None)
        write_ordered_audits(output,capture,ordered,wait_audit,resolver_audit,qualification_audit)
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
        clock=prior.canonical_trade_enums(pd.DataFrame(capture['trades']))
        trades=prior.canonical_trade_enums(frames['trades']);usage=pd.DataFrame(capture['usage'])
        if trades.empty:raise ValueError('no_trades_not_a_successful_candidate')
        if len(usage)!=len(trades)or usage.trade_id.duplicated().any()or set(usage.trade_id)!=set(trades.trade_id):raise ValueError('execution_usage_not_one_to_one')
        for field in('signal_datetime','signal_order_id'):
            if field not in usage:raise ValueError(f'execution_clock_identity_missing:{field}')
            clock[field]=clock.trade_id.map(usage.set_index('trade_id')[field])
            if clock[field].isna().any():raise ValueError(f'execution_clock_identity_unmapped:{field}')
        sources=clock.trade_id.map(usage.set_index('trade_id').price_source).fillna('')
        synthetic=clock.offset.ne('开')&sources.str.startswith('stage')
        clock.loc[synthetic,'exit_reason']=sources[synthetic]
        frames['trades']=prior.attach_trading_dates(trades,clock)
        for name,frame in frames.items():
            if frame.empty and not len(frame.columns):frame=pd.DataFrame(columns=['date','vt_symbol','event','reason'])
            frame=frame.copy();frame['research_arm']=arm;frame['production_qualified']=False
            frame.to_csv(output/f'{name}.csv',index=False,encoding='utf-8-sig')
        combined.to_csv(output/'daily.csv',index=False,encoding='utf-8-sig')
        clock.to_csv(output/'execution_clock.csv',index=False,encoding='utf-8-sig')
        usage.to_csv(output/'execution_proxy_usage.csv',index=False,encoding='utf-8-sig')
        pd.DataFrame(capture['equity']).to_csv(output/'internal_equity_daily.csv',index=False,encoding='utf-8-sig')
        stats=s901.s650._metrics(combined,spec.capital,1.0)
        stats.update(result_scope=RESULT_SCOPE,production_qualified=False)
        counts=dict(decision_rows=len(ordered['decision']),decision_counts=dict(Counter(str(row.get('decision',''))for row in ordered['decision'])),
            fill_audit_rows=len(ordered['fill']),execution_audit_rows=len(ordered['execution']),pending_intents=len(ordered['pending']))
        minute_summary=dict(strict_required=True,request_rows=len(minutes),captured_bar_failures=0,
            coverage_status_counts=dict(Counter(minutes.get('coverage_status',[]))),missing_bar_count=missing)
        provenance=dict(status='completed_pending_independent_review',arm=arm,started_at=started,completed_at=datetime.now().astimezone(),
            elapsed_seconds=time.monotonic()-began,result_scope=RESULT_SCOPE,production_qualified=False,
            correctness_code_sha256=prior.ACCEPTED_CODE,active_parameter_identity=identity,
            input_fingerprints=recorder.files,all_consumed_inputs_unchanged_during_run=True,
            minute_input_sha256=prior.EXPECTED_MINUTE,weekly_feature_sha256=prior.EXPECTED_FEATURES,ordered_feature_cache=feature_audit,
            protocol_sha256=sha256(PROTOCOL),holding_contract_sha256=sha256(HOLDING_CONTRACT),source_adapter_sha256=sha256(output/'runner_used.py'),data_stack_sha256=STACK_SHA,
            source_modules_sha256={name:sha256(output/name)for name in('stage028_ordered_strategy.py','stage028_ordered_engine.py')},
            execution_contract=EXECUTION_CONTRACT,only_candidate_delta='ordered weekly permission, earlier FI2 preparation, new native signal and next-real-day first-minute breakout initial entry; unknown baseline fallback; entry-day holding contexts use post-entry OHLC while AM/history/environment retain full completed day',
            original_u_close_quantity_and_stop_frozen=True,fill_time_broker_budget_rechecked=False,actual_gap_risk_bounded_by_u_gate=False,
            data_adapter_changed=True,alpha_changed_from_C0=True,strict_minutes=True,captured_bar_failure_count=0,
            actual_settings_equal_accepted_A=True,parameters_equal_accepted_A=True,actual_daily_dates_equal_accepted_A0=True,
            reused_A0=A0_audit,reused_anchor=anchor_audit,vendor_swallowed_bar_exception_guard=True,
            source_head=preflight['runtime']['source_head'],runtime=preflight['runtime'],model_runtime_smoke=model_smoke,
            local_minute_overlay=minute_overlay,financial_replays=1,broker_connections=0,order_api_count=0,cancel_api_count=0)
        for name,payload in (('actual_strategy_settings.json',actual),('effective_parameters.json',parameters),('input_manifest.json',recorder.files),
                             ('run_provenance.json',provenance),('metrics.json',stats)):
            write_json(output/name,payload)
        summary=dict(status=provenance['status'],arm=arm,result_scope=RESULT_SCOPE,statistics=stats,ordered_counts=counts,
            strict_minutes=minute_summary,actual_settings=actual,input_fingerprints=recorder.files,ordered_feature_cache=feature_audit,
            reused_A0=A0_audit,execution_contract=EXECUTION_CONTRACT,financial_replays=1,production_qualified=False,
            output_directory=str(output),model_runtime_smoke=model_smoke,broker_connections=0,order_api_calls=0,cancel_api_calls=0)
        write_json(output/'summary.json',summary)
        print(json.dumps(json_safe(dict(status=summary['status'],arm=arm,statistics=stats,ordered_counts=counts)),ensure_ascii=False))
    except BaseException as error:
        recorder.enabled=False
        audit_export_error=''
        try:write_ordered_audits(output,capture,ordered,wait_audit,resolver_audit,qualification_audit)
        except Exception as audit_error:audit_export_error=repr(audit_error)
        write_json(output/'run_failure.json',dict(audit_export_error=audit_export_error,status='failed_closed_no_accepted_performance',arm=arm,result_scope=RESULT_SCOPE,
            error=repr(error),started_at=started,failed_at=datetime.now().astimezone(),financial_replay_attempts=1,production_qualified=False,
            input_fingerprints=recorder.files,captured_bar_failures=capture.get('failures',[]),actual_settings=actual,
            minute_requests=capture.get('minute_requests',[]),ordered_audits=ordered,local_minute_overlay=minute_overlay,
            qualified_wait_gate_audit=wait_audit,resolver_audit=resolver_audit,initial_qualification=qualification_audit,
            ordered_feature_cache=feature_audit,reused_A0=A0_audit,reused_anchor=anchor_audit,data_stack_sha256=STACK_SHA,
            execution_contract=EXECUTION_CONTRACT,order_api_count=0,cancel_api_count=0))
        raise


if __name__=='__main__':main()
