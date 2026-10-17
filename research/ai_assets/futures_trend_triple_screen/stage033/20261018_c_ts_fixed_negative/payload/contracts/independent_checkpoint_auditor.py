"""Stage033 independent C_TS attempt2 audit with an owned checkpoint boundary.

Economic algorithms are frozen Stage030 functions, never strategy replay.
Actual execution remains blocked until the final reviewed Stage031 SHA/schema
is pinned; --self-test touches only small synthetic identity records.
"""
from __future__ import annotations

import argparse
import ast
from datetime import date, datetime
import gzip
import hashlib
import io
import importlib.util
import json
import math
from pathlib import Path
import pickle
import tempfile

import pandas as pd

LINE=Path(__file__).resolve().parents[1]
ROOT=LINE.parents[2]
SOURCE=LINE/'outputs/stage031_ordered_account/C_TS'
OUT=LINE/'outputs/stage033_independent_account_review'
BASE=LINE/'tools/stage030_independent_ordered_account_review.py'
BASE_SHA='3fe153c379b95b67aa1f083381b55786c1afb85efd5896f035d91c4eb55dac15'
RUNNER=LINE/'tools/stage031_run_ordered_checkpoint.py'
# Exact implementation supplied by root; any execution-review change must be
# explicitly repinned before an actual account can pass this boundary.
FROZEN_RUNNER_SHA='3af932bdbde9ae607c507ff8630dde0a0b03f190ca88be94fa43ce5910b0b860'
FROZEN_PAYLOAD_SCHEMA='stage031_raw_account_checkpoint_v1'
FROZEN_MODULES={'stage028_ordered_strategy.py':'d4f870355796c98625031f233dfba31f97db10422c894076acf436279f141c48',
 'stage028_ordered_engine.py':'f7d7450495bb09407dc85ce6fe73fd700b2732a2e57dc8f6185abf199967af23'}
PARENT_RUNNER_SHA='c05924175609c09ce0a44b451bcc97497be2b30012cb9c971886217c4960c6af'
PROTOCOL=LINE/'stages/20261018_0302_stage031_export_checkpoint_fix.md'
ENGINE_VALIDATION=dict(engine_returned=True,actual_settings_equal_accepted_A=True,
    parameters_equal_accepted_A=True,actual_daily_dates_equal_accepted_A0=True,
    captured_bar_failures=0,strict_minute_missing_bars=0,
    all_consumed_inputs_unchanged_during_run=True,frozen_correctness_code_unchanged=True,
    historical_shared_signal_input_empty=True)
PAYLOAD_KEYS={'combined','frames','capture','actual_trade_identities','ordered','actual',
    'parameters','spec','preflight','input_fingerprints','run_context','engine_completed_at',
    'engine_elapsed_seconds','wait_audit','resolver_audit','qualification_audit','schema'}
DAILY_BROKER_MULTIPLIER=1.10
MARGIN_SOURCE=ROOT/'examples/portfolio_backtesting/analyze_qmt_roll_stage403_stage079_xsmom_execution_margin_audit.py'


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb')as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    return h.hexdigest()


def read(path):return json.loads(Path(path).read_text())
def write(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def json_projection(value):
    if isinstance(value,dict):return {str(k):json_projection(v)for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [json_projection(v)for v in value]
    if isinstance(value,(date,datetime,Path)):return str(value)
    if hasattr(value,'item'):return json_projection(value.item())
    if isinstance(value,float)and not math.isfinite(value):return None
    return value
def missing(value):return value is None or str(value).strip()==''or bool(pd.isna(value))
def stamp(value):
    assert not missing(value),'missing explicit actual identity'
    value=pd.Timestamp(value);assert not pd.isna(value)
    return value.tz_convert('Asia/Shanghai').tz_localize(None)if value.tzinfo else value


def baseline_module():
    assert digest(BASE)==BASE_SHA,'frozen Stage030 audit algorithm changed'
    spec=importlib.util.spec_from_file_location('stage033_frozen_stage030',BASE)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class OwnedAccountUnpickler(pickle.Unpickler):
    """A frozen local account snapshot cannot import strategy/native modules."""
    def find_class(self,module,name):
        allowed=(module in{'builtins','datetime','collections','pathlib','zoneinfo','numpy','pandas'} or
            module.startswith(('pandas.','numpy.','pytz.')))
        assert allowed,('non-account pickle class rejected before import',module,name)
        return super().find_class(module,name)


def checkpoint_binding(source,evidence):
    """No unpickling occurs until exact local ownership and external SHA pins pass."""
    assert FROZEN_RUNNER_SHA and FROZEN_PAYLOAD_SCHEMA,'final_stage031_schema_and_reviewed_source_not_yet_pinned'
    assert source==SOURCE.resolve()and SOURCE.absolute()==SOURCE.resolve()and not SOURCE.is_symlink()
    folder=source/'checkpoint'
    paths=[folder/'raw_account.pkl.gz',folder/'raw_manifest.json',folder/'validation_seal.json',source/'run_context.json',source/'runner_used.py']
    assert not folder.is_symlink()
    for path in paths:
        assert path.is_file()and not path.is_symlink()and path.resolve().parent in(folder.resolve(),source)
    manifest,seal,context=map(read,paths[1:4])
    assert manifest['schema']=='stage031_raw_checkpoint_manifest_v1'
    assert seal['schema']=='stage031_engine_validation_seal_v1'and context['schema']=='stage031_run_context_v1'
    assert manifest['raw_filename']=='raw_account.pkl.gz'and manifest['account_exports_only']is True
    assert manifest['output_directory']==context['output_directory']==str(source)
    assert manifest['writer']=='stage031_run_ordered_checkpoint.py'
    assert manifest['parent_runner_sha256']==context['parent_runner_sha256']==PARENT_RUNNER_SHA
    assert manifest['strategy_engine_sha256']==context['strategy_engine_sha256']==FROZEN_MODULES
    for row in(manifest,seal,context):
        assert row['arm']=='C_TS'and row['attempt']==2 and row['production_qualified']is False
        assert row['run_id']==context['run_id']and bool(row['run_id'])
    assert digest(paths[4])==digest(RUNNER)==manifest['writer_source_sha256']==seal['writer_source_sha256']==context['writer_source_sha256']==FROZEN_RUNNER_SHA
    assert digest(paths[1])==seal['manifest_sha256']and digest(paths[3])==manifest['run_context_sha256']
    assert all(seal['validation'].get(k)==v for k,v in ENGINE_VALIDATION.items())
    assert seal['status']=='engine_snapshot_validated_not_independent_economic_review'
    assert manifest['status']=='raw_evidence_not_validation_or_performance_pass'
    assert evidence['runner_sha256']==FROZEN_RUNNER_SHA
    assert evidence['checkpoint_sha256']==manifest['raw_sha256']==seal['raw_sha256']
    assert evidence['validation_seal_sha256']==digest(paths[2])
    raw=paths[0].read_bytes()
    assert hashlib.sha256(raw).hexdigest()==manifest['raw_sha256']and len(raw)==manifest['raw_bytes']
    # A checkpoint generated by the exact reviewed local runner is loaded once.
    # Final payload schema must contain only account exports and builtin/pandas
    # objects. No engine, strategy, minute cache or external pickle is accepted.
    payload=OwnedAccountUnpickler(io.BytesIO(gzip.decompress(raw))).load()
    assert payload['schema']==FROZEN_PAYLOAD_SCHEMA and payload['run_context']==context
    assert set(payload)==PAYLOAD_KEYS,('unexpected final checkpoint payload keys',set(payload)^PAYLOAD_KEYS)
    assert isinstance(payload['combined'],pd.DataFrame)and isinstance(payload['frames'],dict)
    assert all(isinstance(frame,pd.DataFrame)for frame in payload['frames'].values())
    assert set(payload['capture'])=={'usage','equity','trades','minute_requests','anchor_requests','failures','weekly_gate'}
    assert payload['capture']['failures']==[]
    assert isinstance(payload['spec'],dict)and payload['spec']==payload['parameters']['spec']
    return payload,dict(manifest=manifest,seal=seal,raw_sha256=manifest['raw_sha256'],
        manifest_sha256=digest(paths[1]),seal_sha256=digest(paths[2]),
        run_context_sha256=digest(paths[3]),raw_loaded_once=True,foreign_pickle_loaded=False)


def identity_audit(raw_usage,identities,exported_clock,exported_usage):
    """Compare sparse producer evidence with explicit real TradeData identity."""
    raw=pd.DataFrame(raw_usage);truth=pd.DataFrame(identities)
    clock=exported_clock.copy();normalized=exported_usage.copy()
    for frame in(raw,truth,clock,normalized):assert frame.trade_id.is_unique and len(frame)>0
    keys=set(truth.trade_id)
    assert all(set(frame.trade_id)==keys for frame in(raw,clock,normalized))
    raw=raw.set_index('trade_id');truth=truth.set_index('trade_id');clock=clock.set_index('trade_id');normalized=normalized.set_index('trade_id')
    synthetic_count=0;missing_raw_signal=0;links=[]
    for trade_id,row in truth.iterrows():
        assert not missing(row.signal_order_id)
        signal=stamp(row.signal_datetime);executed=stamp(row.execution_datetime)
        assert signal<=executed
        episode=row.intraday_episode_id;synthetic=not missing(episode)
        if synthetic:
            synthetic_count+=1;assert episode in truth.index and episode!=trade_id
            parent=truth.loc[episode]
            assert parent.offset in('开','Open')and parent.vt_symbol==row.vt_symbol
            assert str(parent.trading_date)[:10]==str(row.trading_date)[:10]
            assert stamp(parent.execution_datetime)<=executed
            assert stamp(parent.signal_datetime)==signal and str(parent.signal_order_id)==str(row.signal_order_id)
            assert 'intraday_episode_id'in raw and str(raw.loc[trade_id,'intraday_episode_id'])==str(episode)
            links.append(dict(trade_id=trade_id,parent_actual_trade_id=episode,signal_order_id=row.signal_order_id))
        else:
            assert 'intraday_episode_id'not in raw or missing(raw.loc[trade_id,'intraday_episode_id'])
        for field in('signal_datetime','signal_order_id'):
            original=raw.loc[trade_id,field]if field in raw else None
            if missing(original):
                assert synthetic,('ordinary raw identity missing',trade_id,field)
                if field=='signal_datetime':missing_raw_signal+=1
            elif field=='signal_datetime':assert stamp(original)==signal
            else:assert str(original)==str(row.signal_order_id)
            for exported in(clock,normalized):
                value=exported.loc[trade_id,field]
                assert stamp(value)==signal if field=='signal_datetime'else str(value)==str(row.signal_order_id)
        for exported in(clock,normalized):
            assert stamp(exported.loc[trade_id,'execution_datetime'])==executed
            ev=exported.loc[trade_id,'intraday_episode_id']
            assert (missing(ev)and not synthetic)or str(ev)==str(episode)
        for field in('vt_symbol','direction','offset','price','volume'):
            value=clock.loc[trade_id,field]
            if field in('direction','offset'):
                enums={'Long':'多','Short':'空','Open':'开','Close':'平','Close Today':'平今','Close Yesterday':'平昨'}
                assert enums.get(row[field],row[field])==value,('actual clock enum mismatch',trade_id,field)
            elif field in('price','volume'):assert float(value)==float(row[field]),('actual clock number mismatch',trade_id,field)
            else:assert str(value)==str(row[field]),('actual clock identity mismatch',trade_id,field)
    return dict(actual_trade_identity_rows=len(truth),synthetic_rows=synthetic_count,
        raw_synthetic_signal_datetime_missing_rows=missing_raw_signal,normalized_identity_conflicts=0,
        identity_source='actual_TradeData_explicit',actual_parent_links=links)


def serialized_csv_sha(frame,decorate=False):
    """Compare a raw table to its actual CSV without materializing CSV text."""
    view=frame.copy(deep=False)
    if view.empty and not len(view.columns):view=pd.DataFrame(columns=['date','vt_symbol','event','reason'])
    if decorate:
        view['research_arm']='C_TS';view['production_qualified']=False
    class Hasher:
        def __init__(self):self.hash=hashlib.sha256(b'\xef\xbb\xbf')
        def write(self,text):self.hash.update(text.encode('utf-8'));return len(text)
    writer=Hasher();view.to_csv(writer,index=False)
    return writer.hash.hexdigest()


def raw_export_equivalence(base,source,payload,bindings,prov,summary):
    """Full saved account data must be the source of every exported economics."""
    assert payload['input_fingerprints']==prov['input_fingerprints']
    final_preflight=json_projection(payload['preflight']);initial_preflight=read(source/'preflight_used.json')
    initial_inputs=initial_preflight['input_fingerprints'];final_inputs=final_preflight['input_fingerprints']
    assert all(path in final_inputs and final_inputs[path]==value for path,value in initial_inputs.items())
    assert {k:v for k,v in final_preflight.items()if k!='input_fingerprints'}=={k:v for k,v in initial_preflight.items()if k!='input_fingerprints'}
    assert final_inputs==payload['input_fingerprints']
    bindings['preflight_input_growth']=dict(initial_entries=len(initial_inputs),final_entries=len(final_inputs),
        added_entries=len(set(final_inputs)-set(initial_inputs)),changed_initial_entries=0,
        all_other_preflight_fields_equal_after_JSON_projection=True,
        cause='preflight input_fingerprints references the actual recorder.files object; preflight_used was saved before the 110 run-time reads, raw checkpoint contains the completed recorder map')
    assert base.normalize(payload['actual'])==base.normalize(read(source/'actual_strategy_settings.json'))
    assert base.normalize(payload['parameters'])==base.normalize(read(source/'effective_parameters.json'))
    assert prov['checkpoint']['manifest']==bindings['manifest']and prov['checkpoint']['seal']==bindings['seal']
    assert prov['checkpoint']['seal_sha256']==bindings['seal_sha256']
    assert summary['checkpoint_raw_sha256']==bindings['raw_sha256']
    assert prov['result_origin']==summary['result_origin']=='same_engine_sealed_account_snapshot'
    assert prov['exporter_source_sha256']==FROZEN_RUNNER_SHA
    assert prov['attempt']==summary['attempt']==2 and prov['alpha_changed_from_Stage028']is False
    success=read(source/'export_success.json')
    assert success['source']==str(source)and success['summary_sha256']==digest(source/'summary.json')
    assert success['raw_sha256']==bindings['raw_sha256']and success['run_id']==bindings['manifest']['run_id']
    verified={}
    assert serialized_csv_sha(payload['combined'])==digest(source/'daily.csv')
    verified['daily.csv']='exact raw combined CSV serialization'
    for name,frame in payload['frames'].items():
        if name=='trades':continue
        assert serialized_csv_sha(frame,decorate=True)==digest(source/(name+'.csv')),('raw frame export differs',name)
        verified[name+'.csv']='exact raw frame CSV serialization'
    assert serialized_csv_sha(pd.DataFrame(payload['capture']['equity']))==digest(source/'internal_equity_daily.csv')
    assert serialized_csv_sha(pd.DataFrame(payload['actual_trade_identities']))==digest(source/'actual_trade_identities.csv')
    clock=base.csv(source/'execution_clock.csv');usage=base.csv(source/'execution_proxy_usage.csv')
    assert clock.signal_identity_source.eq('actual_TradeData_explicit').all()
    assert usage.signal_identity_source.eq('actual_TradeData_explicit_after_producer_consistency_check').all()
    raw_usage=pd.DataFrame(payload['capture']['usage'])
    expected_usage=raw_usage.copy();clock_index=clock.set_index('trade_id')
    for field in('signal_datetime','signal_order_id','intraday_episode_id'):
        expected_usage[field]=expected_usage.trade_id.map(clock_index[field])
    expected_usage['signal_identity_source']='actual_TradeData_explicit_after_producer_consistency_check'
    assert serialized_csv_sha(expected_usage)==digest(source/'execution_proxy_usage.csv'),'raw usage nonidentity fields changed during export'
    identity=identity_audit(payload['capture']['usage'],payload['actual_trade_identities'],clock,usage)
    # Raw account trades must retain the exact actual native fields; decoration
    # can only normalize enum strings, attach proven trading dates/exit reasons.
    raw=payload['frames']['trades'].copy();trades=base.csv(source/'trades.csv')
    assert raw.trade_id.is_unique and set(raw.trade_id)==set(trades.trade_id)==set(clock.trade_id)
    raw=raw.set_index('trade_id');trades=trades.set_index('trade_id');clock=clock.set_index('trade_id')
    enums={'Long':'多','Short':'空','Open':'开','Close':'平','Close Today':'平今','Close Yesterday':'平昨'}
    for trade_id,row in raw.iterrows():
        exported=trades.loc[trade_id]
        for field in('order_id','vt_symbol','price','volume','signed_volume'):
            assert float(row[field])==float(exported[field])if field in('price','volume','signed_volume')else str(row[field])==str(exported[field])
        for field in('direction','offset'):assert enums.get(row[field],row[field])==exported[field]
        assert stamp(row['datetime'])==stamp(exported['datetime'])
        assert exported['date']==exported['trading_date']==clock.loc[trade_id,'trading_date']
    bindings['raw_to_export_tables']=verified;bindings['actual_identity_review']=identity
    return bindings


def use_raw_positions_once(base,payload):
    """Reuse the original inventory arithmetic with the already verified raw table.

    Its exported CSV is hash-equivalent above, so there is no second parsing
    pass through the large positions file and no account-engine recomputation.
    """
    original=base.audit_inventory
    def wrapped(source,d,trades,parameters,settings):
        reader=pd.read_csv
        frame=payload['frames']['positions'].copy(deep=False)
        frame['date']=frame.date.astype(str).str[:10]
        outside=frame.loc[~frame.date.isin(d.date)]
        assert outside.date.lt('2020-01-01').all(),'positions outside account calendar are not pure prior warmup'
        zero_fields=[x for x in('start_pos','end_pos','pos_change','trade_count','turnover','commission','slippage',
            'holding_pnl','trading_pnl','total_pnl','net_pnl')if x in frame]
        assert (outside[zero_fields].to_numpy(dtype=float)==0).all(),'nonzero warmup account entries cannot be excluded'
        base._stage033_checkpoint_review['positions_zero_warmup_rows_excluded']=len(outside)
        frame=frame.loc[frame.date.isin(d.date)]
        def checkpoint_reader(path,*args,**kwargs):
            if Path(path).resolve()==(source/'positions.csv').resolve():
                columns=kwargs['usecols'];size=kwargs['chunksize']
                def chunks():
                    for start in range(0,len(frame),size):
                        chunk=frame.iloc[start:start+size][columns].copy()
                        chunk['date']=chunk.date.astype(str).str[:10]
                        yield chunk
                return chunks()
            return reader(path,*args,**kwargs)
        pd.read_csv=checkpoint_reader
        # Stage030's fresh inventory helper named this input after the native
        # admission gate. The established seven-gate DAILY report actually
        # uses Stage403 broker10=1.10; native Stage830 admission remains 1.65.
        reporting_settings=dict(settings,stage830_broker_margin_multiplier=DAILY_BROKER_MULTIPLIER)
        base._stage033_checkpoint_review['margin_definitions']=dict(daily_broker10_reporting_multiplier=DAILY_BROKER_MULTIPLIER,
            native_stage830_admission_multiplier=settings['stage830_broker_margin_multiplier'],
            full_minute_PIT_portfolio_peak_established=False)
        try:return original(source,d,trades,parameters,reporting_settings)
        finally:pd.read_csv=reader
    base.audit_inventory=wrapped


def supplementary_risk_and_holding_review(base,result):
    """Small exported-ledger diagnostics; never replay or load market minutes."""
    daily=base.csv(SOURCE/'daily.csv')
    equity=base.csv(OUT/'independent_equity.csv').independent_equity
    ratio=daily.c3_margin_exact*1.65/equity*100
    result['additional_165_daily_margin_diagnostic']=dict(
        multiplier=1.65,max_margin_to_equity_pct=float(ratio.max()),
        days_over_100pct=int((ratio>100+1e-9).sum()),days_over_90pct=int((ratio>90+1e-9).sum()),
        definition='independently verified daily exchange margin x 1.65 / independently rebuilt close equity',
        replaces_original_seven_gates=False,is_full_minute_PIT_peak=False,
        native_fill_time_budget_rechecked=False)
    pd.DataFrame(dict(date=daily.date,margin_165_daily=daily.c3_margin_exact*1.65,
        independent_close_equity=equity,margin_to_equity_pct=ratio)).to_csv(OUT/'additional_165_daily_margin.csv',index=False)
    trades=base.csv(SOURCE/'trades.csv');fills=base.csv(SOURCE/'ordered_fill_audit.csv')
    minutes=base.csv(SOURCE/'minute_scan_requests.csv');survivors=[]
    for row in fills.to_dict('records'):
        quantity=trades.loc[trades.vt_symbol.eq(row['contract'])&trades.date.le(row['execution_day']),'signed_volume'].sum()
        if abs(quantity)<1e-9:continue
        requests=minutes.loc[minutes.vt_symbol.eq(row['contract'])&minutes.trading_date.eq(row['execution_day'])&
            minutes.requested_start.map(stamp).eq(stamp(row['execution_datetime']))]
        # For an entry after the session opening, these two calls are the
        # original entry-day scan and the holding-only D-close suffix read.
        minimum=3 if stamp(row['execution_datetime'])==stamp(requests.session_start.iloc[0])else 2
        assert len(requests)>=minimum,('no distinct conditional holding suffix request',row['intent_id'])
        survivors.append(dict(intent_id=row['intent_id'],contract=row['contract'],execution_day=row['execution_day'],
            entry_datetime=row['execution_datetime'],same_start_suffix_requests=len(requests),minimum_required=minimum))
    pd.DataFrame(survivors).to_csv(OUT/'conditional_holding_suffix_request_links.csv',index=False)
    result['holding_causality_review']=dict(conditional_entries_surviving_to_day_close=len(survivors),
        all_have_additional_exact_entry_suffix_request=True,
        first_intrabar_open_policy='frozen d4f870 strategy copies minute frame and changes only entry minute open to actual fill; restores original in finally',
        full_day_market_history_environment_retained=True,
        evidence_boundary='dynamic exact suffix request multiplicity plus frozen implementation and previously passed causal fixtures; raw minute OHLC not reaggregated by this financial reviewer')


def provenance_audit(base,source,exit_path,hashes):
    """Exact Stage031 source guard, plus all original financial provenance gates."""
    evidence=read(exit_path)
    assert evidence.get('exit_code')==0 and evidence.get('terminal_observed')is True
    assert evidence.get('source')==str(source)and evidence.get('summary_sha256')==hashes['summary.json']
    assert not(source/'run_failure.json').exists()
    prov=read(source/'run_provenance.json');summary=read(source/'summary.json');pre=read(source/'preflight_used.json')
    for row in(prov,summary):
        assert row['arm']=='C_TS'and row['status']=='completed_pending_independent_review'
        assert row['result_scope']==base.SCOPE and row['production_qualified']is False and row['financial_replays']==1
    for key in('all_consumed_inputs_unchanged_during_run','strict_minutes','actual_settings_equal_accepted_A',
        'parameters_equal_accepted_A','actual_daily_dates_equal_accepted_A0','original_u_close_quantity_and_stop_frozen'):
        assert prov[key]is True,key
    for key in('fill_time_broker_budget_rechecked','actual_gap_risk_bounded_by_u_gate'):assert prov[key]is False,key
    assert prov['captured_bar_failure_count']==0 and prov['broker_connections']==0 and prov['order_api_count']==0 and prov['cancel_api_count']==0
    assert summary['strict_minutes']['missing_bar_count']==0 and summary['strict_minutes']['captured_bar_failures']==0
    manifest=read(source/'input_manifest.json');assert manifest==prov['input_fingerprints']==summary['input_fingerprints']
    checked={}
    margin_ast=ast.parse(MARGIN_SOURCE.read_text())
    values=[ast.literal_eval(node.value)for node in margin_ast.body if isinstance(node,ast.Assign)and any(isinstance(target,ast.Name)and target.id=='BROKER10_MULTIPLIER'for target in node.targets)]
    assert values==[DAILY_BROKER_MULTIPLIER]
    assert manifest[str(MARGIN_SOURCE)]['sha256']==digest(MARGIN_SOURCE)
    checked[str(MARGIN_SOURCE)]=digest(MARGIN_SOURCE)
    for name,key in {'runner_used.py':'source_adapter_sha256','protocol_used.md':'protocol_sha256',
        'holding_contract_used.md':'holding_contract_sha256','data_stack_manifest.json':'data_stack_sha256'}.items():
        assert hashes[name]==prov[key];checked[name]=hashes[name]
    assert hashes['runner_used.py']==digest(RUNNER)==FROZEN_RUNNER_SHA
    assert hashes['protocol_used.md']==digest(PROTOCOL)
    assert hashes['entry_contract_used.md']==prov['entry_contract_sha256']==digest(LINE/'stages/20261018_0234_stage028_conditional_execution_contract.md')
    assert prov['source_modules_sha256']==FROZEN_MODULES
    for name,value in FROZEN_MODULES.items():
        assert hashes[name]==digest(LINE/'tools'/name)==value;checked[name]=value
    for path,value in prov['correctness_code_sha256'].items():assert digest(ROOT/path)==value;checked[path]=value
    stack=read(source/'data_stack_manifest.json')
    assert stack['full_excludes_remaining_source859']is True and stack['anchor859_only_stage010_canonical_first_key']is True
    path=Path(stack['gate_review_path']);assert digest(path)==stack['gate_review_sha256'];checked[str(path)]=stack['gate_review_sha256']
    outer=stack['outer_correction'];path=Path(outer['review_path'])
    assert digest(path)==outer['review_sha256'];review016=read(path)
    assert review016['qualified_research_source859_delta']is True and not review016.get('p0_findings',0)and not review016.get('p1_findings',0)
    checked[str(path)]=outer['review_sha256']
    wait=read(source/'qualified_wait_audit.json')
    assert wait['initial_qualification']['scope']=='inherited_accepted_baseline_plus_usage_limited859_not_global_price_recertification'
    assert wait['initial_qualification']['anchor_only_rights']>=wait['initial_qualification']['appended_anchor_keys']
    for row in wait['gate']:
        if row['event']=='data_qualified_appended':
            assert row['old_keys_changed']==0;path=Path(row['receipt_path']);assert digest(path)==row['receipt_sha256'];checked[str(path)]=row['receipt_sha256']
    baseline=prov['reused_A0'];assert digest(base.A0_REVIEW)==base.A0_REVIEW_SHA==baseline['review_sha256']
    accepted=read(base.A0_REVIEW);assert 'A0_attempt2'in accepted['financial_accounts_reviewed']
    assert accepted['remaining_implementation_p0']==accepted['remaining_implementation_p1']==0
    for name,value in baseline['artifact_sha256'].items():assert digest(base.A0/name)==value;checked[str(base.A0/name)]=value
    assert base.normalize(read(source/'effective_parameters.json'))==base.normalize(read(base.A0/'effective_parameters.json'))
    actual=read(source/'actual_strategy_settings.json');reference=read(base.A0/'actual_strategy_settings.json')
    assert len(actual)==1 and actual[0]['supply_demand_signal_rows']==0
    assert base.normalize(actual[0]['actual'])==base.normalize(reference[0]['actual'])
    assert pre['parameters_equal_accepted_A']is True and pre['requested_settings_equal_accepted_A']is True
    payload,bindings=checkpoint_binding(source,evidence)
    bindings=raw_export_equivalence(base,source,payload,bindings,prov,summary)
    base._stage033_checkpoint_review=bindings
    use_raw_positions_once(base,payload)
    return prov,actual[0]['actual'],checked


def self_test():
    base=baseline_module();base.self_test()
    truth=[dict(trade_id='T1',vt_symbol='x.SHFE',direction='多',offset='开',price=100.,volume=1.,
        execution_datetime='2020-01-02T09:00',trading_date='2020-01-02',signal_datetime='2020-01-01T00:00',signal_order_id='O1',intraday_episode_id=None),
        dict(trade_id='T2',vt_symbol='x.SHFE',direction='空',offset='平',price=99.,volume=1.,
        execution_datetime='2020-01-02T09:01',trading_date='2020-01-02',signal_datetime='2020-01-01T00:00',signal_order_id='O1',intraday_episode_id='T1')]
    raw=[dict(truth[0]),dict(trade_id='T2',intraday_episode_id='T1')]
    clock=pd.DataFrame(truth).fillna('');usage=clock.copy()
    report=identity_audit(raw,truth,clock,usage)
    assert report['raw_synthetic_signal_datetime_missing_rows']==1 and report['synthetic_rows']==1
    broken=usage.copy();broken.loc[1,'signal_order_id']='FAKE'
    try:identity_audit(raw,truth,clock,broken)
    except AssertionError:pass
    else:raise AssertionError('normalized fake identity accepted')
    broken_truth=[dict(x)for x in truth];broken_truth[1]['intraday_episode_id']='FOREIGN'
    try:identity_audit(raw,broken_truth,clock,usage)
    except AssertionError:pass
    else:raise AssertionError('foreign mother accepted')
    # Exact serialization verification is a structural fixture, never account PnL.
    frame=pd.DataFrame({'date':['2020-01-02'],'x':[.1]})
    with tempfile.TemporaryDirectory(prefix='stage033_fixture_')as tmp:
        path=Path(tmp)/'table.csv';frame.to_csv(path,index=False,encoding='utf-8-sig')
        assert serialized_csv_sha(frame)==digest(path)
    try:OwnedAccountUnpickler(io.BytesIO(pickle.dumps(Path('/tmp/fixture')))).load()
    except AssertionError:raise AssertionError('builtin account path unexpectedly rejected')
    restored=OwnedAccountUnpickler(io.BytesIO(pickle.dumps({'combined':frame,'x':datetime(2020,1,2)}))).load()
    pd.testing.assert_frame_equal(restored['combined'],frame,check_exact=True)
    assert digest(RUNNER)==FROZEN_RUNNER_SHA
    return dict(status='final_031_schema_bound_finite_nonfinancial_identity_fixtures_passed',
        inherited_030_fixtures=3,new_identity_fixtures=3,financial_replays=0,partial_PnL_computed=False,
        baseline_algorithm_sha256=BASE_SHA,wrapper_sha256=digest(__file__),source_scope=str(SOURCE.resolve()))


def main():
    parser=argparse.ArgumentParser(description=__doc__);actions=parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--self-test',action='store_true');actions.add_argument('--completion-evidence',type=Path)
    args=parser.parse_args()
    if args.self_test:result=self_test()
    else:
        assert FROZEN_RUNNER_SHA and FROZEN_PAYLOAD_SCHEMA,'final_stage031_schema_and_reviewed_source_not_yet_pinned'
        base=baseline_module();base.SOURCE=SOURCE;base.OUT=OUT
        base.NAMES+=['actual_trade_identities.csv','entry_contract_used.md','run_context.json','export_success.json']
        base.audit_provenance=lambda source,evidence,hashes:provenance_audit(base,source,evidence,hashes)
        result=base.run(args.completion_evidence)
        result.update(stage='Stage033',attempt=2,baseline_algorithm_sha256=BASE_SHA,
            wrapper_sha256=digest(__file__),review_script_sha256=digest(__file__),
            checkpoint_review=base._stage033_checkpoint_review,
            exact_runner_sha256=FROZEN_RUNNER_SHA,source_scope='Stage031 C_TS attempt2 only')
        supplementary_risk_and_holding_review(base,result)
        write(OUT/'account_checks.json',result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
