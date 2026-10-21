"""One fixed EMA_LIMIT account; export-only dispatch precedes numerical imports."""
from __future__ import annotations
from contextlib import contextmanager,ExitStack,redirect_stdout,redirect_stderr
from dataclasses import dataclass,asdict
from datetime import datetime,date
import argparse
import csv
import io
import json
import math
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
from copy import deepcopy
import sys

import stage140_ema_checkpoint as checkpoint
from stage140_ema_checkpoint import BoundAsset,EmaRun

LINE=Path(__file__).resolve().parents[1]
ACCOUNT_ROOT=LINE/'outputs/stage140_ema_account/EMA_LIMIT'


def _bound_ref(row):
    path=Path(row['path'])
    bound=BoundAsset(path,row['sha256'],row.get('bytes',path.stat().st_size))
    return bound,checkpoint.read_asset(bound)


def read_ema_features(manifest:BoundAsset,review:BoundAsset):
    """Thin scalar reader; no indicator build or market loader is called."""
    m=json.loads(checkpoint.read_asset(manifest));r=json.loads(checkpoint.read_asset(review))
    if (m.get('schema')!='stage142_accepted127_scalar_features_v1'
        or r.get('schema')!='stage142_fixed_ema_feature_generation_handoff_v1'
        or r.get('fixed_model_generated_and_checked')is not True or r.get('feature_math_changes')is not False
        or r.get('feature_manifest_path')!=str(manifest.path) or r.get('feature_manifest_sha256')!=manifest.sha256
        or r.get('features_sha256')!=m['features']['sha256'] or r.get('features_path')!=m['features']['path']):
        raise ValueError('ema_fixed_feature_handoff_identity')
    if m.get('load_bound_daily_csv_calls')!=1 or m.get('build_ema_rows_calls')!=1 or m.get('financial_ready')is not False:
        raise ValueError('ema_fixed_feature_build_scope')
    bindings={manifest.path:manifest,review.path:review}
    def ref(row):
        bound,raw=_bound_ref(row);bindings[bound.path]=bound;return bound,raw
    _,qualification_raw=ref(m['daily_source_qualification'])
    qualification=json.loads(qualification_raw)
    if (qualification.get('schema')!='stage142_independent_daily_source_qualification_v1'
        or qualification.get('independent_review')is not True or qualification.get('qualified_research_data')is not True
        or qualification.get('p0_findings')!=0 or qualification.get('p1_findings')!=0):raise ValueError('ema_daily_source_unqualified')
    if (r.get('daily_source_qualification_sha256')!=m['daily_source_qualification']['sha256']
        or r.get('fixed_model_sha256')!=m['model_sha256']):raise ValueError('ema_feature_qualification_binding')
    for item in (m['candidate_manifest'],m['model_independent_review']):ref(item)
    _,calendar_raw=ref(m['calendar'])
    calendar=[date.fromisoformat(x['date']).isoformat()for x in csv.DictReader(io.StringIO(calendar_raw.decode('utf-8-sig')))]
    if calendar!=sorted(set(calendar))or len(calendar)!=m['calendar']['count']:raise ValueError('ema_feature_calendar_identity')
    next_day={u:calendar[i+1]if i+1<len(calendar)else None for i,u in enumerate(calendar)}
    ref(dict(path=m['model_path'],sha256=m['model_sha256']))
    rules=m['execution_tick_rules']
    for path,sha in ((rules['rule_source'],rules['rule_sha256']),(rules['parameters_path'],rules['parameters_sha256'])):
        ref(dict(path=path,sha256=sha))
    for path,item in qualification['source_bindings'].items():
        if not isinstance(item,str) or len(item)!=64 or any(c not in '0123456789abcdef' for c in item):
            raise ValueError('ema_daily_qualification_binding_type')
        bound=checkpoint.asset(path)
        if bound.sha256!=item:raise ValueError('ema_daily_qualification_source_changed')
        bindings[bound.path]=bound
    sources=m['source_bindings']
    for source in sources.values():
        ref(dict(path=source['source_path'],sha256=source['source_sha256']))
        if source['qualifier_sha256']!=m['daily_source_qualification']['sha256'] or source['price_basis']!='real_contract_unadjusted':
            raise ValueError('ema_feature_real_contract_source')
    _,raw=ref(m['features']);rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    if len(rows)!=m['features']['rows'] or (rows and list(rows[0])!=m['features']['columns']):raise ValueError('ema_feature_table_scope')
    def boolean(value):
        if value not in ('True','False'):raise ValueError('ema_feature_strict_bool')
        return value=='True'
    class FeatureLookup(dict):pass
    lookup=FeatureLookup();lookup.bound_assets=tuple(bindings.values())
    qualified_keys={name:{tuple(key)for key in value['qualified_keys']}for name,value in sources.items()}
    counts=('positive_down_count','positive_up_count','valid_ema_count')
    numbers=('ema','ema_prev','mean_down','mean_up','execution_tick','configured_tick')
    for row in rows:
        key=(date.fromisoformat(row['asof']).isoformat(),row['contract'])
        if key in lookup or '.'not in key[1] or row['source_ref']not in sources or row['execution_rule_ref']!='execution_tick_rules':
            raise ValueError('ema_feature_duplicate_or_reference')
        if (key[1],key[0])not in qualified_keys[row['source_ref']]:raise ValueError('ema_feature_outside_qualified_keys')
        item=dict(row);item['ready']=boolean(row['ready']);item['execution_tick_order_usable']=boolean(row['execution_tick_order_usable'])
        for name in numbers:
            value=float(row[name])if row[name]else None
            if value is not None and (not math.isfinite(value)or value<0):raise ValueError('ema_feature_nonfinite_or_negative')
            item[name]=value
        for name in counts:
            value=int(row[name])
            if value<0 or str(value)!=row[name]:raise ValueError('ema_feature_invalid_count')
            item[name]=value
        if item['ready'] and (any(item[k]is None for k in ('ema','ema_prev')) or item['valid_ema_count']<26):
            raise ValueError('ema_ready_feature_missing')
        for side in ('down','up'):
            count=item['positive_'+side+'_count'];mean=item['mean_'+side]
            if (count==0 and mean is not None) or (count>0 and (mean is None or mean<=0)):
                raise ValueError('ema_positive_only_mean_contract')
        execution=date.fromisoformat(row['execution_day']).isoformat()if row['execution_day']else None
        known=date.fromisoformat(row['execution_tick_known_asof']).isoformat()
        if item['execution_tick_order_usable'] and (not execution or execution<=key[0]or known>key[0]or not item['execution_tick']):
            raise ValueError('ema_execution_tick_asof_identity')
        if key[0]not in next_day or execution!=next_day[key[0]]:raise ValueError('ema_execution_next_real_calendar_day')
        item['execution_day']=execution
        if not item['execution_tick_order_usable']:item['execution_tick']=None
        # All rows refer to one shared source object; do not duplicate full key lists.
        item['source_bindings']=sources
        lookup[key]=item
    return lookup


@dataclass
class PreparedEma:
    profile:dict
    engine_class:type
    metadata:dict
    preflight:dict
    recorder:object
    s901:object
    holder:dict
    layers:dict
    start:object
    end:object
    reference_settings:dict
    reference_parameters:dict
    reference_shared:Path
    runtime_temporary:object


def delta_input_recorder(recorder):
    """Use031's exact explicit-format binding for the accepted delta closure."""
    from stage031_run_ordered_checkpoint import bind_input
    return SimpleNamespace(extra=recorder.extra,files=recorder.files,
        record=lambda path:bind_input(recorder,path))


def prepare_ema(*,feature_manifest:BoundAsset,feature_review:BoundAsset,delta159_manifest:BoundAsset,delta159_review:BoundAsset)->PreparedEma:
    """Explicit full-input preparation; never called by finite integration tests."""
    import stage022_run_c0_qualified_wait as prior
    import stage031_run_ordered_checkpoint as shared
    import stage065_run_pairwise_off as original
    temporary=tempfile.TemporaryDirectory(prefix='ema-prepare-')
    signal_dir=LINE/'outputs/stage140_ema_account/shared_empty_signal_inputs'
    saved=prior.OUTPUT
    try:prior.OUTPUT=Path(temporary.name);prior.configure_runtime(signal_dir)
    finally:prior.OUTPUT=saved
    import pandas as pd
    import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
    import stage002_local_minute_overlay as minutes
    import stage016_source859_qualification as correction
    import stage021_blocking_data_gate as gate
    import stage061_accepted_wait_delta as accepted
    from stage127_ema_limit_strategy import build_ema_account_profile
    from stage065_pairwise_off_policy import OFF_SETTINGS,check_settings_delta,disabled_pairwise_preflight
    from qmt_backtest_runtime_guard import assert_stage196_database_sentinels
    from qmt_roll_official_baseline_identity import assert_official_checkout_matches_active_material
    from vnpy.trader.constant import Offset,Direction
    assert_stage196_database_sentinels()
    identity=asdict(assert_official_checkout_matches_active_material(prior.ROOT))
    if identity!=prior.IDENTITY:raise ValueError('ema_active_parameter_identity_changed')
    for name,sha in prior.ACCEPTED_CODE.items():
        if checkpoint.asset(prior.ROOT/name).sha256!=sha:raise ValueError('ema_frozen_correctness_source_changed:'+name)
    if checkpoint.asset(prior.SOURCE001).sha256!=prior.SOURCE001_SHA:raise ValueError('ema_source001_changed')
    isolation=original._bound_json(original.ISOLATION_REVIEW,original.ISOLATION_REVIEW_SHA)
    if isolation.get('code_usable_for_caller_integration')is not True or isolation.get('p0_findings')!=0 or isolation.get('p1_findings')!=0:
        raise ValueError('ema_source859_isolation_not_accepted')
    stack=prior.read_data_stack(original.STACK,original.STACK_SHA)
    days,A0_audit,A0_paths=shared.read_reused_A0()
    if len(days)!=1641:raise ValueError('ema_reference_calendar_not_1641')
    recorder=prior.InputRecorder(json.loads((prior.OLD/'input_manifest.json').read_bytes()))
    paths=set(A0_paths)|{original.STACK,original.ISOLATION_REVIEW,prior.SOURCE001,prior.SOURCE_PROTOCOL,prior.FEATURES,
        feature_manifest.path,feature_review.path,delta159_manifest.path,delta159_review.path}
    paths.update(Path(p)for p in stack['source_fingerprints'])
    paths.update(LINE.joinpath('tools').glob('*.py'))
    for stage in (124,126,127,132,135,137,139,140,141,142,143,144,145,146,148,149,150):
        paths.update((LINE/'stages').glob('*stage'+str(stage)+'_*'))
    recorder.extra.update(paths);sys.addaudithook(recorder.audit);recorder.enabled=True
    try:
        for path in paths:shared.bind_input(recorder,path)
        parts=[]
        for layer in stack['overlays']:
            part=minutes.normal_times(pd.read_csv(layer['path']));part['qualified_stack_layer']=layer['stage'];parts.append(part)
        overlay=pd.concat(parts,ignore_index=True,sort=False)
        if overlay.duplicated(['vt_symbol','bar_datetime']).any():raise ValueError('ema_stack_key_overlap')
        c=stack['outer_correction'];qualified=correction.read_qualified_delta(c['summary_path'],c['summary_sha256'],c['review_path'],c['review_sha256'])
        anchor_data,anchor_keys,anchor_audit=shared.read_reused_anchor(gate,recorder)
        delta190=accepted.load_accepted_delta(original.DELTA,original.DELTA_SHA,original.DELTA_REVIEW,original.DELTA_REVIEW_SHA,
            base_stack=original.STACK,base_stack_sha256=original.STACK_SHA,inherited_anchor_inputs=anchor_audit['deliveries'],recorder=recorder)
        delta159=accepted.load_accepted_delta(delta159_manifest.path,delta159_manifest.sha256,delta159_review.path,delta159_review.sha256,
            base_stack=original.STACK,base_stack_sha256=original.STACK_SHA,inherited_anchor_inputs=anchor_audit['deliveries'],recorder=delta_input_recorder(recorder))
        if (delta159.manifest.get('builder')!='stage135_accepted_off_wait_delta.py' or delta159.manifest['accepted_deliveries']!=159
            or delta159.manifest['accepted_keys']!=36391 or delta159.manifest.get('fixture_only')is not False):raise ValueError('ema_new159_identity')
        completed=frozenset(qualified.allowed_keys)|delta190.full_keys|delta190.anchor_keys|frozenset(anchor_keys)
        metadata=s901.s513._metadata();start,end=pd.Timestamp(prior.START),pd.Timestamp(prior.END)
        lookup=read_ema_features(feature_manifest,feature_review)
        for bound in lookup.bound_assets:shared.bind_input(recorder,bound.path,bound.sha256)
        weekly=prior.WeeklyLookup.read(prior.FEATURES);fi,next_days,feature_audit,feature_paths=shared.read_ordered_features()
        for path in feature_paths:shared.bind_input(recorder,path)
        holder={};formal=prior.capture_formal_profile(s901,metadata,start,end)
        profile,engine=build_ema_account_profile(formal,s901.s847.QmtRollPortfolioStrategyStage847C9StopRetry,
            s901.s847.Stage847StopRetryEngine,weekly=weekly,fi=fi,next_days=next_days,ema_lookup=lookup,
            qualify=shared.build_qualification_callback(holder,Offset,Direction))
        settings=s901.s847.s827.s772._build_setting(metadata=metadata,spec=profile['spec'],
            base_c3_overrides=dict(s901.s513._c3_overrides(start.to_pydatetime())),start=start)
        old_settings=json.loads((prior.OLD/'actual_strategy_settings.json').read_bytes())[0]['actual']
        reference=json.loads((prior.OLD/'effective_parameters.json').read_bytes());reference['spec']['overrides'].update(OFF_SETTINGS)
        reference_shared=Path(old_settings['supply_demand_signal_path']).parent
        requested={k:v for k,v in settings.items()if k not in ('account_capital','c3_capital')}
        checked=check_settings_delta(old_settings,requested,requested,shared=signal_dir,reference_shared=reference_shared)
        normal=lambda x:prior.normalize_reference(prior.json_safe(x),signal_dir,reference_shared)
        if normal(original._parameters(profile['spec'],metadata))!=normal(reference):raise ValueError('ema_parameters_not_exact_OFF')
        extra_tools=prior.ROOT/'research/lines/futures_trend_rollover_shape_same_volume/tools'
        if str(extra_tools)not in sys.path:sys.path.insert(0,str(extra_tools))
        from stage249_historical_replay import audit_historical_ai_pool
        ai=audit_historical_ai_pool(s901.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,s901._required_ai_eval_dates(start,end))
        relative=str(Path(s901.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH).relative_to(prior.ROOT))
        if ai['eligibility_sha256']!=recorder.accepted[relative]:raise ValueError('ema_monthly_pool_changed')
        for module in tuple(sys.modules.values()):
            filename=getattr(module,'__file__',None)
            if filename:
                path=Path(filename).resolve()
                if path.suffix=='.py'and path.is_file()and(path.is_relative_to(prior.PROJECT)or path.is_relative_to(prior.VENDOR)or path.parent==LINE/'tools'):
                    shared.bind_input(recorder,path)
        bindings={group:{p:dict(sha256=v['sha256'],bytes=v['bytes'])for p,v in recorder.files.items()
            if (Path(p).suffix=='.py')==(group=='source_bindings')}for group in ('source_bindings','data_bindings')}
        assets={k:dict(path=str(v.path),sha256=v.sha256,bytes=v.bytes)for k,v in locals().copy().items()
            if k in ('feature_manifest','feature_review','delta159_manifest','delta159_review')}
        preflight=dict(schema=checkpoint.PREFLIGHT_SCHEMA,status='prepared_pending_independent_review_no_financial_authorization',
            account_id=checkpoint.ACCOUNT_ID,mechanism_id=checkpoint.MECHANISM_ID,attempt=1,fixture_only=False,financial_ready=False,
            account_root=str(ACCOUNT_ROOT),capital=150000,period=[prior.START,prior.END],reference_calendar=days,
            reference_calendar_scope='full_2020_2026',**bindings,ema_assets=assets,active_parameter_identity=identity,
            requested_settings_check=checked,disabled_pairwise=disabled_pairwise_preflight(),
            account_classes=dict(strategy_module=profile['strategy_cls'].__module__,strategy_name=profile['strategy_cls'].__name__,
                engine_module=engine.__module__,engine_name=engine.__name__),reused_A0=A0_audit,reused_anchor=anchor_audit,
            ai_pool_audit=ai,ordered_feature_cache=feature_audit,strict_minutes=True,wait_seconds_max=1800,whole_run_seconds_max=7200,
            execution_policy='primary',volume_assumption='V>=q; source-level lot inference; no queue allocation proof',production_qualified=False)
        layers=dict(overlay=overlay,qualified=qualified,anchor_data=anchor_data,anchor_keys=anchor_keys,
            delta190=delta190,delta159=delta159,completed_keys=completed,demand=pd.read_csv(stack['demand_path']),
            calendar=pd.DatetimeIndex(pd.to_datetime(pd.read_csv(minutes.MAPPING,usecols=['date']).date).drop_duplicates().sort_values()))
        # The last demand/calendar reads also belong to the preflight closure.
        for group in ('source_bindings','data_bindings'):
            preflight[group]={p:dict(sha256=v['sha256'],bytes=v['bytes'])for p,v in recorder.files.items()if(Path(p).suffix=='.py')==(group=='source_bindings')}
        return PreparedEma(profile,engine,metadata,preflight,recorder,s901,holder,layers,start,end,old_settings,reference,reference_shared,temporary)
    except BaseException:recorder.enabled=False;temporary.cleanup();raise


@contextmanager
def ema_minute_scope(s901,*,overlay,qualified,anchor_data,anchor_keys,delta190,delta159,completed_keys,isolation_audit):
    import stage002_local_minute_overlay as minutes
    import stage016_source859_qualification as correction
    import stage031_run_ordered_checkpoint as shared
    import stage061_accepted_wait_delta as accepted
    import stage071_source859_isolation as isolation
    with ExitStack()as stack:
        stack.enter_context(minutes.temporary_minute_overlay(s901,overlay))
        stack.enter_context(correction.temporary_qualified_minute_delta(s901,qualified))
        a=stack.enter_context(shared.temporary_reused_anchor(s901,anchor_data,anchor_keys))
        old=stack.enter_context(accepted.temporary_accepted_wait_delta(s901,delta190))
        stack.enter_context(isolation.temporary_source859_isolation(s901,completed_keys,isolation_audit))
        new=stack.enter_context(accepted.temporary_accepted_wait_delta(s901,delta159))
        yield dict(anchor=a,delta190=old,delta159=new)


def compose_ema_rights(full,anchor,added,anchor_keys,delta190,delta159):
    import stage031_run_ordered_checkpoint as shared
    import stage061_accepted_wait_delta as accepted
    full,anchor=shared.ordered_predicates(full,anchor,added['anchor'],anchor_keys)
    full,anchor=accepted.compose_qualification(full,anchor,added['delta190'],delta190)
    return accepted.compose_qualification(full,anchor,added['delta159'],delta159)


@contextmanager
def capture_ema(engine_class:type,run:EmaRun):
    import stage031_run_ordered_checkpoint as shared
    names=('add_strategy','new_bars','calculate_result')
    originals={n:(n in engine_class.__dict__,getattr(engine_class,n))for n in names}
    evidence=dict(decision=[],fill=[],execution=[],budget=[],pending=[],actual_trade_identities=[])
    seen=[]
    def remember(engine):
        if not seen:seen.append(engine)
        elif seen[0]is not engine:raise ValueError('ema_multiple_engines')
    def collect(engine):
        strategy=getattr(engine,'strategy',None)
        evidence.update(decision=[dict(x)for x in getattr(strategy,'ts_decision_audit',[])],
            fill=[dict(x)for x in getattr(strategy,'ts_fill_audit',[])],
            execution=[dict(x)for x in getattr(engine,'ema_limit_execution_audit',[])],
            budget=[dict(x)for x in getattr(strategy,'ema_limit_final_budget_audit',[])])
        pending=[]
        for item in getattr(strategy,'ts_pending_intents',[]):
            row=shared.pending_intent_snapshot(item)
            row.update({k:item.get(k)for k in ('mechanism_id','order_type','limit_price','execution_tick','run_id')})
            row['frozen_plan']['sizing'].update({k:v for k,v in item.get('plan',{}).get('sizing',{}).items()
                if k.startswith('ema_limit_')and(v is None or isinstance(v,(str,bool,int,float)))})
            pending.append(row)
        evidence['pending']=pending
        evidence['actual_trade_identities']=shared.actual_trade_identities(engine.get_all_trades())
        for row,trade in zip(evidence['actual_trade_identities'],engine.get_all_trades()):
            row.update(research_mechanism=getattr(trade,'research_mechanism',None),economic_mother_id=getattr(trade,'economic_mother_id',None))
    def add(engine,*args,**kwargs):
        remember(engine);result=originals['add_strategy'][1](engine,*args,**kwargs)
        if engine.get_all_trades():raise ValueError('ema_run_id_injected_after_trade')
        engine.strategy.ema_limit_run_id=run.run_id
        from stage065_pairwise_off_policy import check_effective_off_policy
        check_effective_off_policy(engine.strategy)
        return result
    def bars(engine,*args,**kwargs):
        remember(engine)
        if getattr(engine.strategy,'ema_limit_run_id',None)!=run.run_id:raise ValueError('ema_run_id_missing_before_bar')
        return originals['new_bars'][1](engine,*args,**kwargs)
    def calculate(engine,*args,**kwargs):
        remember(engine)
        try:return originals['calculate_result'][1](engine,*args,**kwargs)
        finally:collect(engine)
    engine_class.add_strategy=add;engine_class.new_bars=bars;engine_class.calculate_result=calculate
    try:yield evidence
    finally:
        if seen:collect(seen[0])
        for name,(local,original)in originals.items():
            if local:setattr(engine_class,name,original)
            else:delattr(engine_class,name)


def execute_ema(prepared:PreparedEma,*,readiness:BoundAsset)->dict:
    import pandas as pd
    import stage022_run_c0_qualified_wait as prior
    import stage031_run_ordered_checkpoint as shared
    import stage065_run_pairwise_off as original
    import stage021_blocking_data_gate as gate021
    from stage065_pairwise_off_policy import check_settings_delta,check_effective_off_policy
    signed=json.loads(checkpoint.read_asset(readiness))
    run=checkpoint.start_run(preflight=prepared.preflight,readiness=readiness,
        started_at=datetime.now().astimezone().isoformat(),global_attempt=signed['global_attempt'])
    if run.fixture_only:raise ValueError('ema_execute_real_refuses_fixture')
    began=time.monotonic();recorder=prepared.recorder;recorder.enabled=True
    capture={};ema={};actual=[];wait=[];resolver_audit=[];isolation=[];phase='engine_not_returned';raw=None
    resolver=prior.FileWaitResolver(run.output/'data_wait',recorder,resolver_audit,began)
    layers={k:v for k,v in prepared.layers.items()if k not in ('demand','calendar')}
    try:
        with (run.output/'engine.log').open('x',buffering=1)as log,redirect_stdout(log),redirect_stderr(log),ExitStack()as scopes:
            scopes.enter_context(prior.whole_run_budget())
            added=scopes.enter_context(ema_minute_scope(prepared.s901,**layers,isolation_audit=isolation))
            actual=scopes.enter_context(prior.capture_actual_settings(prepared.engine_class))
            capture=scopes.enter_context(prior.capture_engine(prepared.engine_class))
            ema=scopes.enter_context(capture_ema(prepared.engine_class,run))
            minute_audit=prepared.s901._ensure_c9_minute_bars(prepared.metadata)
            full,anchor,qualification=prior.inherited_qualification_predicates(prepared.s901._FULL_MINUTE_BY_SYMBOL_CACHE,
                prepared.layers['qualified'].allowed_keys,prepared.layers['demand'],prepared.layers['calendar'])
            full,anchor=compose_ema_rights(full,anchor,added,prepared.layers['anchor_keys'],prepared.layers['delta190'],prepared.layers['delta159'])
            gate=scopes.enter_context(gate021.qualified_wait_scope(prepared.engine_class,resolver,wait,
                qualified_existing_keys=full,qualified_anchor_existing_keys=anchor))
            prepared.holder['gate']=gate
            try:
                combined,frames,spec=original.run_profile_once(prepared.s901,prepared.profile,prepared.metadata,
                    engine_class=prepared.engine_class,start=prepared.start,end=prepared.end,minute_audit=minute_audit)
                parameters=original._parameters(spec,prepared.metadata)
                context,_=checkpoint.load_context(run,verify_sources=False)
                raw=checkpoint.save_raw(run,dict(combined=combined,frames=frames,capture=capture,
                    actual_trade_identities=ema['actual_trade_identities'],ema={k:ema[k]for k in ('decision','fill','execution','budget','pending')},
                    actual=actual,parameters=parameters,spec=asdict(spec),preflight=prepared.preflight,run_context=context,
                    input_fingerprints=dict(recorder.files),wait_audit=wait,resolver_audit=resolver_audit,
                    qualification_audit=qualification,isolation_audit=isolation,engine_elapsed_seconds=time.monotonic()-began))
                phase='post_raw_validation'
            finally:prepared.holder.pop('gate',None)
        if len(actual)!=1 or actual[0]['supply_demand_signal_rows']!=0:raise ValueError('ema_actual_strategy_not_unique')
        requested={k:v for k,v in actual[0]['setting'].items()if k not in actual[0]['non_strategy_fields']}
        shared_dir=LINE/'outputs/stage140_ema_account/shared_empty_signal_inputs'
        check_settings_delta(prepared.reference_settings,requested,actual[0]['actual'],shared=shared_dir,reference_shared=prepared.reference_shared)
        normal=lambda v:prior.normalize_reference(prior.json_safe(v),shared_dir,prepared.reference_shared)
        if normal(parameters)!=normal(prepared.reference_parameters):raise ValueError('ema_effective_parameters_drift')
        dates=pd.to_datetime(combined.date).dt.strftime('%Y-%m-%d').tolist()
        shared.validate_daily_calendar(dates,prepared.preflight['reference_calendar'])
        if len(dates)!=1641 or capture['failures']:raise ValueError('ema_actual_calendar_or_bar_failure')
        scans=pd.DataFrame(capture['minute_requests'])
        if not scans.empty and pd.to_numeric(scans.missing_bar_count,errors='raise').sum()!=0:raise ValueError('ema_missing_strict_minutes')
        recorder.verify()
        if any(shared_dir.iterdir()):raise ValueError('ema_shared_inputs_not_empty')
        for bindings in (prepared.preflight['source_bindings'],prepared.preflight['data_bindings']):checkpoint._verify_bindings(bindings)
        validation=dict(checkpoint.VALIDATION,actual_daily_count=len(dates),fixture_only=False)
        checkpoint.seal_raw(run,raw,validation);phase='pure_export'
        return checkpoint.export_sealed(run,run.output/'exports/export_001')
    except BaseException as error:
        recorder.enabled=False
        checkpoint.save_failure(run,dict(capture=capture,ema={k:ema.get(k,[])for k in ('decision','fill','execution','budget','pending')},
            actual=actual,wait_audit=wait,resolver_audit=resolver_audit,raw_saved=raw is not None),repr(error),phase)
        raise
    finally:recorder.enabled=False


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True);group.add_argument('--run',action='store_true');group.add_argument('--export-only',action='store_true')
    for name in ('preflight','preflight-sha256','readiness','readiness-sha256','run-context','run-context-sha256','destination'):
        parser.add_argument('--'+name)
    parser.add_argument('--global-attempt',type=int)
    args=parser.parse_args(argv)
    if args.export_only:
        bound=checkpoint.asset(args.run_context)
        if bound.sha256!=args.run_context_sha256:raise ValueError('ema_export_context_changed')
        run=checkpoint.run_from_context(bound)
        # Runtime only selects accepted numerical libraries; no prepare/native/model.
        import stage022_run_c0_qualified_wait as runtime
        with tempfile.TemporaryDirectory(prefix='ema-export-')as tmp:
            previous=runtime.OUTPUT
            try:runtime.OUTPUT=Path(tmp);runtime.configure_runtime(Path(tmp)/'shared')
            finally:runtime.OUTPUT=previous
            return checkpoint.export_sealed(run,Path(args.destination))
    raw=checkpoint.regular(args.preflight).read_bytes()
    if checkpoint.asset(args.preflight).sha256!=args.preflight_sha256:raise ValueError('ema_preflight_changed')
    preflight=json.loads(raw)
    if preflight.get('fixture_only')is not False:raise ValueError('ema_real_cli_refuses_fixture')
    assets=preflight['ema_assets'];prepared=prepare_ema(**{k:BoundAsset(Path(v['path']),v['sha256'],v['bytes'])for k,v in assets.items()})
    if checkpoint.json_bytes(prepared.preflight)!=raw:raise ValueError('ema_prepared_inputs_drift')
    readiness=checkpoint.asset(args.readiness)
    if readiness.sha256!=args.readiness_sha256:raise ValueError('ema_readiness_changed')
    if json.loads(checkpoint.read_asset(readiness))['global_attempt']!=args.global_attempt:raise ValueError('ema_global_attempt_mismatch')
    return execute_ema(prepared,readiness=readiness)


if __name__=='__main__':main()
