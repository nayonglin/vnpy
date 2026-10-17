"""Fixed A_OFF/B_OFF preparation, one-account dispatch and sealed-only recovery.

Import/CLI dispatch are stdlib-only. No financial run is authorized by this
module or its finite fixtures: --run requires a separately pinned root readiness.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack,contextmanager,redirect_stderr,redirect_stdout
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
LINE=ROOT/'research/lines/futures_trend_triple_screen'
OUTPUT=LINE/'outputs/stage065_pairwise_off_account'
PLAN=LINE/'stages/20261018_0546_stage062_pairwise_off_implementation_plan.md'
STACK=LINE/'outputs/stage022_qualified_wait/data_stack_manifest.json'
STACK_SHA='2b650761fbf2bc30aa0046147b7e369a2a0a10a68ee6b520204dde8d4d7226a0'
DELTA=LINE/'outputs/stage061_accepted_wait_delta/ccc4a13cbc8e4691af41a16916c659f2/manifest.json'
DELTA_SHA='48bc356b8723c4ae7104f7055ad8480de31fffb7fca6f115b537152eafc7900f'
DELTA_REVIEW=LINE/'outputs/stage081_accepted_wait_dataset_review/review_receipt.json'
DELTA_REVIEW_SHA='8cca4707388f9b957b77117f11370183b98f89c7a810e550d4f7a753d782daaf'
ISOLATION_REVIEW=LINE/'outputs/stage078_source859_isolation_independent_review/review_receipt.json'
ISOLATION_REVIEW_SHA='66d9e68b45081901f6cadaa9a85033a8507bcbed72ddaf505eb57a7742cbf80b'
TERMINAL_BINDINGS={
 'terminal_evidence':(LINE/'outputs/stage063_b_ts_actual_failure/actual_tool_terminal.json',
     '8f556fb6b76c27f28db7ff7799643bda5c7e934c844a29546545efe10d21981b'),
 'original_B_run_failure':(LINE/'outputs/stage036_b_ts_account/B_TS/run_failure.json',
     'f39f9d60b3e975263b0ee9411b70b766a9a8c4a3f12d068b9c35650888928536'),
 'conflict_review':(LINE/'outputs/stage064_b_ts_failure_independent_review/review_receipt.json',
     '916edbc472fb49dcb9e1fbcde396b0b555a82b1468622b1db526a98c1bee9963'),
}
FROZEN={
 'stage022_run_c0_qualified_wait.py':'aaa0cc50c7c817c885afd6eb3630b28f714da21486a1ec2dfb8fbeb39437582c',
 'stage031_run_ordered_checkpoint.py':'3af932bdbde9ae607c507ff8630dde0a0b03f190ca88be94fa43ce5910b0b860',
 'stage065_pairwise_off_policy.py':'edaa018cebe288245197dcb8b4bfba76e2a1c1691cf24c7de369a91bc62a639f',
 'stage065_account_checkpoint.py':'7e5a265a23b8fce871c895292e0738831604eefb9a341f7a83bd0320a68cf15b',
 'stage061_accepted_wait_delta.py':'3570427b8d1543a7fc7dc14e3fb17978f394fb4864b809e85d75fa6609b5a73a',
 'stage071_source859_isolation.py':'12580b91d0e264ac4f63807679742cbbc67c8cb03e66dd42343cf9b72c26fe27',
 'stage028_ordered_strategy.py':'d4f870355796c98625031f233dfba31f97db10422c894076acf436279f141c48',
 'stage028_ordered_engine.py':'f7d7450495bb09407dc85ce6fe73fd700b2732a2e57dc8f6185abf199967af23',
 'stage035_b_ts_strategy.py':'fc357eb4a44a384d816acaff5fadaa99d91dfc7f8ec8fbd22954c9ca3837b09e',
 'stage035_b_ts_pricing.py':'d45e8a5b4b7503a33c137df7decbd56947c2d1df77b7c73c5e7524326ae1018f',
}


def _bound_json(path,digest):
    from stage065_account_checkpoint import _read_regular
    raw=_read_regular(Path(path))
    if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('runner_bound_json_sha_mismatch:'+str(path))
    return json.loads(raw)


def _configure_runtime():
    import stage022_run_c0_qualified_wait as prior
    from stage065_account_checkpoint import _no_links
    _no_links(OUTPUT)
    previous=prior.OUTPUT
    try:
        prior.OUTPUT=OUTPUT
        prior.configure_runtime(OUTPUT/'shared_empty_signal_inputs')
    finally:prior.OUTPUT=previous


def build_account_profile(formal,arm,native_strategy,native_engine,**dependencies):
    from stage065_pairwise_off_policy import make_off_profile,select_account_classes
    strategy,engine=select_account_classes(arm,native_strategy,native_engine,**dependencies)
    profile=make_off_profile(formal,arm)
    profile['strategy_cls']=strategy
    return profile,engine


def run_profile_once(s901,profile,metadata,*,engine_class,start,end,minute_audit):
    from stage031_run_ordered_checkpoint import replace_engine_class
    module=s901.s847
    previous=(module.START,module.END,module.s827._GLOBAL_MINUTE_BY_SYMBOL)
    try:
        module.START=start.normalize();module.END=end.normalize()
        with replace_engine_class(module,engine_class):
            combined,frames=module._run_profile(profile,metadata)
    finally:
        module.START,module.END,module.s827._GLOBAL_MINUTE_BY_SYMBOL=previous
    spec=profile['spec']
    combined['account_capital']=spec.capital.account_capital
    combined['c3_capital']=spec.capital.c3_capital
    combined['profile']=spec.profile
    for frame in frames.values():
        if not frame.empty:
            frame['account_capital']=spec.capital.account_capital
            frame['c3_capital']=spec.capital.c3_capital
            frame['profile']=spec.profile
    for name in ('forced_margin_deleverage_count','forced_margin_deleverage_closed_volume',
            'forced_margin_deleverage_ratio','forced_margin_deleverage_max_observed_ratio'):combined[name]=0
    combined['minute_source']=minute_audit['source']
    combined['minute_loaded_symbol_count']=minute_audit['loaded_symbol_count']
    return combined,frames,spec


def _fixed_inputs(args):
    for path,expected in ((args.data_stack_manifest,STACK),(args.accepted_wait_delta_manifest,DELTA)):
        if Path(path).absolute()!=expected or Path(path).is_symlink():raise ValueError('runner_requires_fixed_data_owner')
    if (args.data_stack_sha256,args.accepted_wait_delta_sha256,args.accepted_wait_delta_review_sha256)!=(
        STACK_SHA,DELTA_SHA,DELTA_REVIEW_SHA):raise ValueError('runner_requires_frozen_data_hashes')


def _readiness(args):
    if args.execution_readiness is None or args.execution_readiness_sha256 is None:
        raise ValueError('root_execution_readiness_required_no_financial_authorization')
    value=_bound_json(args.execution_readiness,args.execution_readiness_sha256)
    if (value.get('schema')!='stage065_pairwise_off_execution_readiness_v1'
        or value.get('arm')!=args.arm or value.get('issued_by')!='root'
        or value.get('financial_execution_authorized') is not True
        or value.get('independent_integration_accepted') is not True
        or value.get('period')!=['2020-01-01','2026-10-14'] or value.get('capital')!=150000
        or value.get('limits_decision')!=dict(action='inherit_original_limits',wait_seconds=1800,run_seconds=7200)
        or value.get('data_stack_sha256')!=STACK_SHA or value.get('accepted_wait_delta_sha256')!=DELTA_SHA
        or value.get('accepted_wait_delta_review_sha256')!=DELTA_REVIEW_SHA
        or value.get('original_B_status')!='failed_no_complete_performance'
        or value.get('A0_reference_status')!='restricted_fixed_pairwise_counterfactual'):
        raise ValueError('root_execution_readiness_contract_not_met')
    for name,(path,digest) in TERMINAL_BINDINGS.items():
        if value.get(name)!={'path':str(path),'sha256':digest}:
            raise ValueError('root_readiness_original_terminal_binding_missing:'+name)
    for name in (*TERMINAL_BINDINGS,'conflict_resolution','integration_review'):
        row=value.get(name,{})
        if not row.get('path') or not row.get('sha256'):raise ValueError('root_readiness_evidence_missing:'+name)
        _bound_json(row['path'],row['sha256'])
    return dict(document=value,path=str(Path(args.execution_readiness).absolute()),sha256=args.execution_readiness_sha256)


def _parameters(spec,metadata):
    return dict(spec=asdict(spec),contract_sizes=metadata['sizes'],rates=metadata['rates'],
        slippages=metadata['slippages'],priceticks=metadata['priceticks'])


def prepare_account(args):
    """Real full-input preparation. Finite tests must never call this function."""
    _fixed_inputs(args)
    import stage022_run_c0_qualified_wait as prior
    import stage031_run_ordered_checkpoint as shared
    import stage065_account_checkpoint as checkpoint
    from stage065_pairwise_off_policy import OFF_SETTINGS,check_settings_delta,disabled_pairwise_preflight
    for name,digest in FROZEN.items():
        if prior.sha256(Path(__file__).with_name(name))!=digest:raise ValueError('frozen_OFF_source_changed:'+name)
    for name,digest in prior.ACCEPTED_CODE.items():
        if prior.sha256(ROOT/name)!=digest:raise ValueError('accepted_correctness_code_changed:'+name)
    if prior.sha256(prior.SOURCE001)!=prior.SOURCE001_SHA:raise ValueError('source001_changed')
    # Pin the isolation review before importing or using its source wrapper.
    isolation=_bound_json(ISOLATION_REVIEW,ISOLATION_REVIEW_SHA)
    if (isolation.get('source_sha256')!=FROZEN['stage071_source859_isolation.py']
        or isolation.get('p0_findings')!=0 or isolation.get('p1_findings')!=0
        or isolation.get('code_usable_for_caller_integration') is not True):raise ValueError('isolation_not_independently_accepted')
    stack=prior.read_data_stack(args.data_stack_manifest,STACK_SHA)
    reference_days,A0_audit,A0_paths=shared.read_reused_A0()
    if len(reference_days)!=1641:raise ValueError('reference_calendar_not_1641')
    accepted=json.loads((prior.OLD/'input_manifest.json').read_text())
    recorder=prior.InputRecorder(accepted)
    recorder.extra.update(Path(path).resolve() for path in stack['source_fingerprints'])
    recorder.extra.update(A0_paths|{Path(__file__).resolve(),Path(__file__).with_name('test_stage065_pairwise_off_integration.py'),
        PLAN,STACK,DELTA,DELTA_REVIEW,ISOLATION_REVIEW,
        prior.SOURCE001,prior.SOURCE_PROTOCOL,prior.DESIGN/'source_stage001_original.py',prior.DESIGN/'source_diff.patch'})
    for path in checkpoint.REQUIRED_SOURCES:recorder.extra.add(path)
    sys.addaudithook(recorder.audit);recorder.enabled=True
    try:
        for path in list(recorder.extra):shared.bind_input(recorder,path)
        import pandas as pd
        import vnpy_portfoliostrategy
        from vnpy.trader.constant import Offset,Direction
        import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
        import stage002_local_minute_overlay as minutes
        import stage016_source859_qualification as source016
        import stage021_blocking_data_gate as gate021
        import stage061_accepted_wait_delta as accepted061
        import stage071_source859_isolation as isolation071
        parts=[]
        for layer in stack['overlays']:
            frame=minutes.normal_times(pd.read_csv(layer['path']));frame['qualified_stack_layer']=layer['stage'];parts.append(frame)
        overlay=pd.concat(parts,ignore_index=True,sort=False)
        if overlay.duplicated(['vt_symbol','bar_datetime']).any():raise ValueError('data_stack_append_key_overlap')
        correction=stack['outer_correction']
        qualified=source016.read_qualified_delta(correction['summary_path'],correction['summary_sha256'],correction['review_path'],correction['review_sha256'])
        anchor_data,anchor_keys,anchor_audit=shared.read_reused_anchor(gate021,recorder)
        delta=accepted061.load_accepted_delta(DELTA,DELTA_SHA,DELTA_REVIEW,DELTA_REVIEW_SHA,
            base_stack=STACK,base_stack_sha256=STACK_SHA,inherited_anchor_inputs=anchor_audit['deliveries'],recorder=recorder)
        completed_keys=frozenset(qualified.allowed_keys)|delta.full_keys|delta.anchor_keys|frozenset(anchor_keys)
        demand=pd.read_csv(stack['demand_path'])
        calendar=pd.DatetimeIndex(pd.to_datetime(pd.read_csv(minutes.MAPPING,usecols=['date']).date).drop_duplicates().sort_values())
        from qmt_backtest_runtime_guard import assert_stage196_database_sentinels
        from qmt_roll_official_baseline_identity import assert_official_checkout_matches_active_material
        from qmt_roll_official_strategy_material_resolver import (load_active_material_release,
            assert_runtime_materials_match_checkout,verify_material_file,ActiveMaterialError)
        identity=asdict(assert_official_checkout_matches_active_material(ROOT))
        if identity!=prior.IDENTITY:raise ValueError('formal_parameter_identity_changed')
        active=load_active_material_release(ROOT/'official_strategy_materials/CURRENT.json',repo_root=ROOT)
        drift=''
        try:assert_runtime_materials_match_checkout(active)
        except ActiveMaterialError as error:drift=str(error)
        for row in active.manifest['files']:
            name=str(row.get('source_path',''))
            if row.get('role') not in ('runtime_code','strategy_config','operational_config') or name.startswith('promotion_source:') or name in {*prior.ACCEPTED_CODE,'skills/futures-live-execution-sop/SKILL.md'}:continue
            verify_material_file(ROOT/name,row)
        assert_stage196_database_sentinels()
        if not Path(vnpy_portfoliostrategy.__file__).resolve().is_relative_to(prior.VENDOR):raise ValueError('portfolio_vendor_changed')
        if prior.sha256(s901.s861.FULL_MINUTE_BARS_PATH)!=prior.EXPECTED_MINUTE:raise ValueError('accepted_minute_cache_changed')
        recorder.record(s901.s861.FULL_MINUTE_BARS_PATH)
        metadata=s901.s513._metadata()
        start,end=pd.Timestamp(prior.START),pd.Timestamp(prior.END)
        external=Path(s901.s513._c3_overrides(start.to_pydatetime())['supply_demand_signal_path'])
        signal_dir=OUTPUT/'shared_empty_signal_inputs'
        if external.parent!=signal_dir or external.exists() or any(signal_dir.iterdir()):raise ValueError('historical_shared_signal_input_not_empty')
        sys.path.insert(0,str(ROOT/'research/lines/futures_trend_rollover_shape_same_volume/tools'))
        from stage249_historical_replay import audit_historical_ai_pool
        ai_path=s901.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH
        ai_audit=audit_historical_ai_pool(ai_path,s901._required_ai_eval_dates(start,end))
        if ai_audit['eligibility_sha256']!=accepted[str(Path(ai_path).relative_to(ROOT))]:raise ValueError('historical_ai_changed')
        formal=prior.capture_formal_profile(s901,metadata,start,end)
        reference=json.loads((prior.OLD/'effective_parameters.json').read_text())
        old_settings=json.loads((prior.OLD/'actual_strategy_settings.json').read_text())[0]['actual']
        reference_shared=Path(old_settings['supply_demand_signal_path']).parent
        normal=lambda value:prior.normalize_reference(prior.json_safe(value),signal_dir,reference_shared)
        if normal(_parameters(formal['spec'],metadata))!=normal(reference):raise ValueError('formal_parameters_drift_from_accepted_A')
        weekly=fi=next_days=None;feature_audit=None
        if args.arm=='B_OFF':
            if prior.sha256(prior.FEATURES)!=prior.EXPECTED_FEATURES:raise ValueError('weekly_features_changed')
            weekly=prior.WeeklyLookup.read(prior.FEATURES)
            fi,next_days,feature_audit,feature_paths=shared.read_ordered_features()
            for path in feature_paths:shared.bind_input(recorder,path)
        holder={}
        qualify=shared.build_qualification_callback(holder,Offset,Direction) if args.arm=='B_OFF' else None
        profile,engine_class=build_account_profile(formal,args.arm,s901.s847.QmtRollPortfolioStrategyStage847C9StopRetry,
            s901.s847.Stage847StopRetryEngine,weekly=weekly,fi=fi,next_days=next_days,qualify=qualify)
        if profile['spec'].capital.account_capital!=150000 or profile['spec'].capital.c3_capital!=150000:
            raise ValueError('OFF_capital_must_remain_150000')
        settings=s901.s847.s827.s772._build_setting(metadata=metadata,spec=profile['spec'],
            base_c3_overrides=dict(s901.s513._c3_overrides(start.to_pydatetime())),start=start)
        engine_fields={k:v for k,v in settings.items() if k in ('account_capital','c3_capital')}
        if any(v!=150000 for v in engine_fields.values()):raise ValueError('OFF_engine_capital_metadata_drift')
        requested={k:v for k,v in settings.items() if k not in engine_fields}
        requested_check=check_settings_delta(old_settings,requested,requested,shared=signal_dir,reference_shared=reference_shared)
        expected=deepcopy(reference);expected['spec']['overrides'].update(OFF_SETTINGS)
        if normal(_parameters(profile['spec'],metadata))!=normal(expected):raise ValueError('OFF_parameters_not_exact_eight_key_projection')
        for module in list(sys.modules.values()):
            filename=getattr(module,'__file__',None)
            if not filename:continue
            path=Path(filename).resolve()
            if path.suffix=='.py' and path.is_file() and (path.is_relative_to(prior.PROJECT) or path.is_relative_to(prior.VENDOR) or path.parent==Path(__file__).parent):shared.bind_input(recorder,path)
        sources={name:dict(sha256=row['sha256'],bytes=row['bytes']) for name,row in recorder.files.items() if Path(name).suffix=='.py'}
        data={name:dict(sha256=row['sha256'],bytes=row['bytes']) for name,row in recorder.files.items() if Path(name).suffix!='.py'}
        classes=dict(strategy_module=profile['strategy_cls'].__module__,strategy_name=profile['strategy_cls'].__name__,
            engine_module=engine_class.__module__,engine_name=engine_class.__name__)
        preflight=dict(status='prepared_pending_independent_review_no_financial_authorization',financial_ready=False,
            arm=args.arm,attempt=1,fixture_only=False,reference_calendar_scope='full_2020_2026',reference_calendar=reference_days,
            source_bindings=sources,data_bindings=data,account_classes=classes,disabled_pairwise=disabled_pairwise_preflight(),
            active_parameter_identity=identity,runtime_material_drift=drift,requested_settings_check=requested_check,
            capital=150000,period=[prior.START,prior.END],strict_minutes=True,ordered_feature_cache=feature_audit,
            reused_A0=A0_audit,reused_anchor=anchor_audit,accepted_wait_delta_manifest=str(DELTA),accepted_wait_delta_sha256=DELTA_SHA,
            accepted_wait_delta_review=str(DELTA_REVIEW),accepted_wait_delta_review_sha256=DELTA_REVIEW_SHA,
            source859_isolation_review_sha256=ISOLATION_REVIEW_SHA,completed_value_proof_keys=len(completed_keys),
            metadata_products=metadata['product_symbols'],metadata_products_sha256=hashlib.sha256(json.dumps(metadata['product_symbols']).encode()).hexdigest(),
            ai_pool_audit=ai_audit,data_stack_sha256=STACK_SHA,wait_seconds_max=1800,whole_run_seconds_max=7200,
            source_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),financial_replays=0,production_qualified=False)
        readiness=getattr(args,'readiness_document',None)
        if readiness is not None:
            for name in ('source_bindings','data_bindings'):
                if readiness['document'].get(name)!=preflight[name]:raise ValueError('root_readiness_prepared_binding_drift:'+name)
            preflight['execution_readiness']=readiness
        return dict(args=args,s901=s901,profile=profile,engine_class=engine_class,metadata=metadata,preflight=preflight,
            recorder=recorder,start=start,end=end,stack=stack,overlay=overlay,qualified=qualified,delta=delta,
            completed_keys=completed_keys,anchor_data=anchor_data,anchor_keys=anchor_keys,demand=demand,calendar=calendar,
            holder=holder,reference_settings=old_settings,reference_parameters=expected,reference_shared=reference_shared,
            readiness=readiness)
    except BaseException:
        recorder.enabled=False
        raise


@contextmanager
def _capture_effective(engine_class):
    from stage065_pairwise_off_policy import check_effective_off_policy
    local='add_strategy' in engine_class.__dict__;original=engine_class.add_strategy;values=[]
    def add(engine,strategy,settings):
        result=original(engine,strategy,settings)
        values.append(check_effective_off_policy(engine.strategy))
        return result
    engine_class.add_strategy=add
    try:yield values
    finally:
        if local:engine_class.add_strategy=original
        else:delattr(engine_class,'add_strategy')


def execute_account(prepared):
    import pandas as pd
    import stage022_run_c0_qualified_wait as prior
    import stage031_run_ordered_checkpoint as shared
    import stage065_account_checkpoint as checkpoint
    import stage002_local_minute_overlay as minutes
    import stage016_source859_qualification as source016
    import stage021_blocking_data_gate as gate021
    import stage061_accepted_wait_delta as accepted061
    import stage071_source859_isolation as isolation071
    from stage065_pairwise_off_policy import check_settings_delta
    if prepared.get('readiness') is None:raise ValueError('root_execution_readiness_required')
    arm=prepared['args'].arm;output=OUTPUT/arm;s901=prepared['s901'];engine=prepared['engine_class']
    prior.reserve_attempt(output)
    started=datetime.now().astimezone();began=time.monotonic()
    try:
        context=checkpoint.new_run_context(output,arm=arm,preflight=prepared['preflight'],started_at=str(started))
    except BaseException as error:
        prepared['recorder'].enabled=False
        prior.atomic_json(output/'run_failure.json',dict(status='failed_before_engine_context',partial=True,
            arm=arm,attempt=1,error=repr(error),financial_replays=0,production_qualified=False))
        raise
    recorder=prepared['recorder'];raw_manifest=None;phase='engine_not_returned'
    capture={};ordered_capture={};actual=[];effective=[];wait_audit=[];resolver_audit=[];isolation_audit=[];qualification_audit={}
    resolver=prior.FileWaitResolver(output/'data_wait',recorder,resolver_audit,began)
    try:
        with (output/'engine.log').open('w',buffering=1) as log,redirect_stdout(log),redirect_stderr(log),ExitStack() as scopes:
            scopes.enter_context(prior.whole_run_budget())
            scopes.enter_context(minutes.temporary_minute_overlay(s901,prepared['overlay']))
            scopes.enter_context(source016.temporary_qualified_minute_delta(s901,prepared['qualified']))
            added_anchor=scopes.enter_context(shared.temporary_reused_anchor(s901,prepared['anchor_data'],prepared['anchor_keys']))
            added_delta=scopes.enter_context(accepted061.temporary_accepted_wait_delta(s901,prepared['delta']))
            scopes.enter_context(isolation071.temporary_source859_isolation(s901,prepared['completed_keys'],isolation_audit))
            actual=scopes.enter_context(prior.capture_actual_settings(engine))
            effective=scopes.enter_context(_capture_effective(engine))
            capture=scopes.enter_context(prior.capture_engine(engine))
            ordered_capture=scopes.enter_context(shared.capture_ordered_engine(engine))
            minute_audit=s901._ensure_c9_minute_bars(prepared['metadata'])
            full,anchor,qualification_audit=prior.inherited_qualification_predicates(s901._FULL_MINUTE_BY_SYMBOL_CACHE,
                prepared['qualified'].allowed_keys,prepared['demand'],prepared['calendar'])
            full,anchor=shared.ordered_predicates(full,anchor,added_anchor,prepared['anchor_keys'])
            full,anchor=accepted061.compose_qualification(full,anchor,added_delta,prepared['delta'])
            qualification_audit.update(source859_isolation=deepcopy(isolation_audit),accepted_wait_delta_sha256=DELTA_SHA,
                exact_anchor_keys=len(prepared['anchor_keys']),accepted_wait_full_keys=len(prepared['delta'].full_keys))
            gate=scopes.enter_context(gate021.qualified_wait_scope(engine,resolver,wait_audit,
                qualified_existing_keys=full,qualified_anchor_existing_keys=anchor))
            if arm=='B_OFF':prepared['holder']['gate']=gate
            try:
                combined,frames,spec=run_profile_once(s901,prepared['profile'],prepared['metadata'],engine_class=engine,
                    start=prepared['start'],end=prepared['end'],minute_audit=minute_audit)
                ordered=None if arm=='A_OFF' else {k:ordered_capture[k] for k in ('decision','fill','execution','pending')}
                parameters=_parameters(spec,prepared['metadata'])
                raw_manifest=checkpoint.save_raw_checkpoint(output,dict(combined=combined,frames=frames,capture=capture,
                    actual_trade_identities=ordered_capture['actual_trade_identities'],ordered=ordered,actual=actual,parameters=parameters,
                    spec=asdict(spec),preflight=prepared['preflight'],input_fingerprints=dict(recorder.files),run_context=context,
                    engine_elapsed_seconds=time.monotonic()-began,wait_audit=wait_audit,resolver_audit=resolver_audit,
                    qualification_audit=qualification_audit,effective_off_policy=effective))
                phase='post_engine_validation'
            finally:prepared['holder'].pop('gate',None)
        if len(actual)!=1 or actual[0]['supply_demand_signal_rows']!=0 or len(effective)!=1:raise ValueError('unexpected_actual_strategy_or_model_policy')
        requested={k:v for k,v in actual[0]['setting'].items() if k not in actual[0]['non_strategy_fields']}
        check_settings_delta(prepared['reference_settings'],requested,actual[0]['actual'],
            shared=OUTPUT/'shared_empty_signal_inputs',reference_shared=prepared['reference_shared'])
        normal=lambda value:prior.normalize_reference(prior.json_safe(value),OUTPUT/'shared_empty_signal_inputs',prepared['reference_shared'])
        if normal(parameters)!=normal(prepared['reference_parameters']):raise ValueError('OFF_actual_parameters_drift')
        dates=pd.to_datetime(combined.date).dt.strftime('%Y-%m-%d').tolist()
        shared.validate_daily_calendar(dates,prepared['preflight']['reference_calendar'])
        if len(dates)!=1641:raise ValueError('OFF_actual_daily_count_not_1641')
        if capture['failures']:raise ValueError('OFF_captured_bar_failures')
        missing=int(pd.to_numeric(pd.DataFrame(capture['minute_requests']).get('missing_bar_count',pd.Series(dtype=float)),errors='raise').fillna(0).sum())
        if missing:raise ValueError('OFF_strict_minutes_incomplete')
        recorder.verify()
        if any((OUTPUT/'shared_empty_signal_inputs').iterdir()):raise ValueError('OFF_shared_input_written')
        for name,binding in prepared['preflight']['source_bindings'].items():
            if prior.sha256(name)!=binding['sha256']:raise ValueError('OFF_source_changed:'+name)
        validation=dict(checkpoint.ENGINE_VALIDATION,fixture_only=False,reference_calendar_scope='full_2020_2026',actual_daily_count=len(dates))
        checkpoint.seal_checkpoint(output,raw_manifest,validation)
        phase='pure_export'
        summary=checkpoint.export_checkpoint(output,output,arm=arm,export_only=False)
        checkpoint.write_comparison_if_ready(OUTPUT)
        return summary
    except BaseException as error:
        recorder.enabled=False
        partial=dict(capture=capture,ordered=None if arm=='A_OFF' else {k:ordered_capture.get(k,[]) for k in ('decision','fill','execution','pending')},
            actual=actual,effective_off_policy=effective,wait_audit=wait_audit,resolver_audit=resolver_audit,
            qualification_audit=qualification_audit,isolation_audit=isolation_audit,input_fingerprints=dict(recorder.files),failure_phase=phase)
        if raw_manifest is None:checkpoint.save_failure_capture(output,partial,error=repr(error))
        else:prior.atomic_json(output/'run_failure.json',dict(status='failed_closed_no_accepted_performance',arm=arm,attempt=1,
            run_id=context['run_id'],error=repr(error),failed_at=str(datetime.now().astimezone()),failure_phase=phase,
            raw_checkpoint=raw_manifest,validation_seal_exists=(output/'checkpoint/validation_seal.json').is_file(),
            partial=False,audits=partial,financial_replays=1,production_qualified=False))
        raise
    finally:recorder.enabled=False


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm',choices=('A_OFF','B_OFF'),required=True)
    actions=parser.add_mutually_exclusive_group(required=True)
    for action in ('preflight','run','export-only'):actions.add_argument('--'+action,action='store_true')
    parser.add_argument('--data-stack-manifest',type=Path,default=STACK)
    parser.add_argument('--data-stack-sha256',default=STACK_SHA)
    parser.add_argument('--accepted-wait-delta-manifest',type=Path,default=DELTA)
    parser.add_argument('--accepted-wait-delta-sha256',default=DELTA_SHA)
    parser.add_argument('--accepted-wait-delta-review-sha256',default=DELTA_REVIEW_SHA)
    parser.add_argument('--execution-readiness',type=Path)
    parser.add_argument('--execution-readiness-sha256')
    args=parser.parse_args(argv)
    # Dispatch BEFORE any data/native imports; a sealed export needs no prepare.
    if args.export_only:
        _configure_runtime()
        from stage065_account_checkpoint import reserve_export_destination,export_checkpoint
        output=OUTPUT/args.arm;destination=reserve_export_destination(output,arm=args.arm)
        result=export_checkpoint(output,destination,arm=args.arm,export_only=True)
        print(json.dumps(dict(status=result['status'],arm=args.arm,source=str(destination),financial_replays_this_process=0)))
        return 0
    _fixed_inputs(args)
    if args.run:
        if (OUTPUT/args.arm).exists():raise FileExistsError('existing_account_refusing_repeat')
        args.readiness_document=_readiness(args)
    _configure_runtime()
    prepared=prepare_account(args)
    if args.preflight:
        try:
            prepared['recorder'].verify()
            import stage022_run_c0_qualified_wait as prior
            prior.atomic_json(OUTPUT/'preflight'/f'{args.arm}.json',prepared['preflight'])
            print(json.dumps(dict(status=prepared['preflight']['status'],arm=args.arm,financial_ready=False,financial_replays=0)))
            return 0
        finally:prepared['recorder'].enabled=False
    result=execute_account(prepared)
    print(json.dumps(dict(status=result['status'],arm=args.arm,statistics=result['statistics'])))
    return 0


if __name__=='__main__':raise SystemExit(main())
