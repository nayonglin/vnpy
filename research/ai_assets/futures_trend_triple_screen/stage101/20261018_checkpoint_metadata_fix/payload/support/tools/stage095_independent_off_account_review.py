"""One-arm independent OFF account arithmetic; never run an account or model.

--schema-check is stdlib-only and opens no account. --audit requires root's
SHA-bound actual tool-terminal record before opening the exact arm checkpoint.
Source/data qualifications authored by this reviewer are inherited from external
078/081/094 reviews, never independently re-signed here.
"""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from datetime import datetime
import gzip
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import sys
from types import ModuleType, SimpleNamespace

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE.parents[2]
TOOLS = LINE / 'tools'
ACCOUNTS = LINE / 'outputs/stage099_pairwise_off_account'
OUT = LINE / 'outputs/stage095_off_financial_audit'
SCOPE = 'offline_full_2020_2026_shared_pairwise_off_native_vs_stage035_package'
PINS = {
    'stage001_independent_review.py': '4a821421d3975108b210adc65de7165d59510a93a1adffc420d6eacdc2cd4e0f',
    'stage001_compare.py': '7f62e2f08cf34267bfe1bfa55f709348b66c23f9ab246aa5e76c6c6056cc975c',
    'stage022_run_c0_qualified_wait.py': 'aaa0cc50c7c817c885afd6eb3630b28f714da21486a1ec2dfb8fbeb39437582c',
    'stage030_independent_ordered_account_review.py': '3fe153c379b95b67aa1f083381b55786c1afb85efd5896f035d91c4eb55dac15',
    'stage031_run_ordered_checkpoint.py': '3af932bdbde9ae607c507ff8630dde0a0b03f190ca88be94fa43ce5910b0b860',
    'stage033_independent_checkpoint_account_review.py': '940ab1180392c7ca3a6cceef15b3bb33f3d37d6510c48f86b9e7c109b7205cbf',
    'stage038_independent_b_ts_account_review.py': 'e9d651be9467c04241809a86c1046881cbe8e9def7c55b1c41bf7c79f0603dd7',
    'stage065_account_checkpoint.py': 'ff2790a36d8b66d8de7e854c6daf3bd6efd7f275d474f4374883ead66e21fe99',
    'stage065_pairwise_off_policy.py': 'edaa018cebe288245197dcb8b4bfba76e2a1c1691cf24c7de369a91bc62a639f',
    'stage065_run_pairwise_off.py': '1717f2ef30d098f4e503906c032f9b6ddac7aa9b968ae072b60b32b86b0725fb',
    'stage035_b_ts_strategy.py': 'fc357eb4a44a384d816acaff5fadaa99d91dfc7f8ec8fbd22954c9ca3837b09e',
    'stage035_b_ts_pricing.py': 'd45e8a5b4b7503a33c137df7decbd56947c2d1df77b7c73c5e7524326ae1018f',
}
OFF = {
    'enable_selection_pairwise_v2': False,
    'enable_selection_pairwise_v2_catastrophic_veto': False,
    'enable_selection_pairwise_v2_catastrophic_hard_filter': False,
    'enable_selection_pairwise_v2_volume_tilt': False,
    'selection_pairwise_volume_tilt_strength': 0.0,
    'selection_pairwise_volume_tilt_long_strength': 0.0,
    'selection_pairwise_volume_tilt_short_strength': 0.0,
    'incremental_margin_budget_gate_protected_selection_rank': 0,
}
INHERITED = {
    'source859': ('stage078_source859_isolation_independent_review', '66d9e68b45081901f6cadaa9a85033a8507bcbed72ddaf505eb57a7742cbf80b'),
    'accepted061': ('stage081_accepted_wait_dataset_review', '8cca4707388f9b957b77117f11370183b98f89c7a810e550d4f7a753d782daaf'),
    'data_scope': ('stage094_off_data_scope_fix_independent_review', '48bc517989da434e22db70fbb7d603ff09c7f52581f67c868cb0ca736aae2684'),
}
CLASSES = {
    'A_OFF': dict(strategy_module='analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine',
        strategy_name='QmtRollPortfolioStrategyStage847C9StopRetry',
        engine_module='analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine', engine_name='Stage847StopRetryEngine'),
    'B_OFF': dict(strategy_module='stage035_b_ts_strategy', strategy_name='Stage035IndependentB_TS',
        engine_module='stage028_ordered_engine', engine_name='Stage028OrderedStage847StopRetryEngine'),
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''): h.update(block)
    return h.hexdigest()


def regular(path):
    path = Path(path).absolute()
    assert not any(p.is_symlink() for p in (path, *path.parents)), ('symlink', str(path))
    assert path.is_file(), ('missing regular file', str(path))
    return path


def read(path): return json.loads(regular(path).read_text())
def canonical(value): return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream: stream.write(canonical(value))


def family_metadata(arm):
    return dict(repaired_checkpoint_family='stage099_checkpoint_metadata_fix_v1',
        global_financial_attempts_before_family=9, global_arm_attempt={'A_OFF':2,'B_OFF':1}[arm],
        prior_A_OFF_checkpoint_failure=dict(path=str(LINE/'outputs/stage096_A_OFF_actual_failure/actual_tool_terminal.json'),
            sha256='8eb4dfbfd675102a01ad4f6cf7b3aa8cfb814e590f00a396935a088d753fb085'))


def check_family(document, arm):
    expected=family_metadata(arm)
    for key,value in expected.items():
        assert document.get(key)==value, ('repaired run family lineage missing',key)
        if type(value) is int: assert type(document[key]) is int, key
    return expected


def terminal_schema(e, arm):
    """Metadata only; must succeed before any account or numerical import."""
    assert e.get('schema') == 'stage095_off_actual_completion_v1'
    assert e.get('issued_by') == 'root' and e.get('actual_terminal_observed') is True
    assert type(e.get('exit_code')) is int and e['exit_code'] == 0
    assert e.get('arm') == arm and e.get('attempt') == 1 and e.get('fixture_only') is False
    assert e.get('reference_calendar_scope') == 'full_2020_2026'
    check_family(e,arm)
    assert e.get('tool_session_id') and e.get('tool_terminal_chunk_id') and e.get('run_id')
    assert e.get('owner_root') == str(ACCOUNTS/arm)
    assert e.get('runner084_source_path') == str(TOOLS/'stage065_run_pairwise_off.py')
    assert e.get('runner084_source_sha256') == PINS['stage065_run_pairwise_off.py']
    assert e.get('checkpoint_writer') == 'stage065_account_checkpoint.py'
    assert e.get('checkpoint_writer_source_sha256') == PINS['stage065_account_checkpoint.py']
    for key in ('summary_sha256', 'raw_checkpoint_sha256', 'raw_manifest_sha256', 'validation_seal_sha256',
                'seal_receipt_sha256', 'run_context_sha256'):
        assert re.fullmatch('[a-f0-9]{64}', str(e.get(key, ''))), key
    export = Path(e['export_source'])
    assert export == ACCOUNTS/arm or (export.parent == ACCOUNTS/arm/'exports' and re.fullmatch(r'export_[0-9]{3,4}', export.name))
    return export


def source(name):
    path = TOOLS/name
    assert sha(regular(path)) == PINS[name], ('frozen source changed', name)
    return path.read_text()


def module(name):
    source(name)
    spec = importlib.util.spec_from_file_location('stage095_'+name[:-3], TOOLS/name)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


def pure_functions(name, names, namespace):
    tree = ast.parse(source(name))
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    assert {n.name for n in nodes} == set(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(TOOLS/name), 'exec'), namespace)
    return namespace


def adapter_fragments():
    """Three finite source projections, also compiled by stdlib schema check."""
    text=source('stage001_independent_review.py')
    start=text.index('    active, root_by_order, closed, retry_rows, rollover_rows =')
    end=text.index('    # The gate audit must refer',start)
    a='def scalar(t,candidates,rollover,p,d,parameters):\n'+text[start:end]+'    return closed_frame,episodes,active,retry_rows,rollover_rows,open_net,cycle_residual\n'
    def function(name,key):
        text=source(name)
        node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==key)
        return '\n'.join(text.splitlines()[node.lineno-1:node.end_lineno])
    budget=function('stage038_independent_b_ts_account_review.py','audit_b_budget_rows')
    before="rank=integer(row,'rank',True)";assert budget.count(before)==1
    budget=budget.replace(before,"rank=integer(row,'rank');assert rank==0,'OFF actual AI rank must be zero'")
    ordered=function('stage030_independent_ordered_account_review.py','ordered_evidence')
    before="row['setup_day']<row['signal_day']";assert ordered.count(before)==1
    ordered=ordered.replace(before,"row['setup_day']<=row['signal_day']")
    return {'A0_episode_block':a,'OFF_zero_rank':budget,'B_same_close_setup':ordered}


def runtime():
    """Frozen numerical paths only; no producer bootstrap, model smoke or engine."""
    frozen = Path('/Users/mac/Documents/Codex/fian-research-20261014/.py311/lib/python3.11/site-packages')
    assert frozen.is_dir() and not any(n in sys.modules for n in ('numpy', 'pandas', 'sklearn', 'scipy', 'joblib'))
    os.environ.update(TZ='Asia/Shanghai', QT_QPA_PLATFORM='offscreen', OPENBLAS_NUM_THREADS='1')
    sys.path[:0] = [str(TOOLS), str(frozen)]
    import numpy as np
    import pandas as pd
    assert all(Path(m.__file__).resolve().is_relative_to(frozen) for m in (np, pd))
    return np, pd


def schema_check():
    """Dispatch/guard boundaries only; never claim fixture economic acceptance."""
    for name in PINS: source(name)
    base = dict(schema='stage095_off_actual_completion_v1', issued_by='root', actual_terminal_observed=True,
        exit_code=0, arm='A_OFF', attempt=1, fixture_only=False, reference_calendar_scope='full_2020_2026',
        tool_session_id='schema_only_not_actual', tool_terminal_chunk_id='schema_only_not_actual', run_id='schema_only',
        owner_root=str(ACCOUNTS/'A_OFF'), export_source=str(ACCOUNTS/'A_OFF'),
        runner084_source_path=str(TOOLS/'stage065_run_pairwise_off.py'), runner084_source_sha256=PINS['stage065_run_pairwise_off.py'],
        checkpoint_writer='stage065_account_checkpoint.py', checkpoint_writer_source_sha256=PINS['stage065_account_checkpoint.py'],
        **family_metadata('A_OFF'),
        **{k:'0'*64 for k in ('summary_sha256','raw_checkpoint_sha256','raw_manifest_sha256','validation_seal_sha256','seal_receipt_sha256','run_context_sha256')})
    terminal_schema(base, 'A_OFF')
    rejected = []
    for label, changed in [('fixture', dict(base, fixture_only=True)), ('live', dict(base, actual_terminal_observed=False)),
                           ('wrong_arm', dict(base, arm='B_OFF')), ('tiny', dict(base, reference_calendar_scope='tiny_fixture'))]:
        try: terminal_schema(changed, 'A_OFF')
        except (AssertionError, ValueError): rejected.append(label)
        else: raise AssertionError(('schema accepted invalid boundary', label))
    # Compile exact pure adapters without importing their numerical modules.
    for label,text in adapter_fragments().items():compile(text,label,'exec')
    return dict(status='stdlib_schema_dispatch_only_passed_not_financial_review', rejected=rejected,
        account_outputs_accessed=False, financial_replays=0, model_loads=0, network_calls=0,
        review_script_sha256=sha(__file__))


def bind_checkpoint(e, arm, cp):
    """Use frozen ownership checks, then a separately restricted account unpickler."""
    owner = ACCOUNTS/arm
    assert e['run_context_sha256'] == sha(regular(owner/'run_context.json'))
    context = read(owner/'run_context.json')
    assert context['run_id'] == e['run_id'] and context['fixture_only'] is False
    _, context, preflight, manifest, manifest_raw, raw = cp._raw_envelope(owner, arm)
    assert manifest['status'] == 'raw_evidence_not_validation_or_performance_pass'
    assert manifest['raw_sha256'] == e['raw_checkpoint_sha256']
    assert hashlib.sha256(manifest_raw).hexdigest() == e['raw_manifest_sha256']
    assert context['writer_source_sha256'] == PINS['stage065_account_checkpoint.py']
    assert context['source_bindings'][e['runner084_source_path']]['sha256'] == e['runner084_source_sha256']
    for name in ('validation_seal.json', 'seal_receipt.json'):
        key = 'validation_seal_sha256' if name.startswith('validation') else 'seal_receipt_sha256'
        assert sha(regular(owner/'checkpoint'/name)) == e[key]
    seal = read(owner/'checkpoint/validation_seal.json'); receipt = read(owner/'checkpoint/seal_receipt.json')
    assert receipt == dict(schema='stage065_seal_receipt_v1', arm=arm, run_id=context['run_id'], seal_sha256=e['validation_seal_sha256'])
    for key, value in dict(schema='stage065_engine_validation_seal_v1', status='engine_snapshot_validated_not_independent_economic_review',
        run_id=context['run_id'], arm=arm, attempt=1, raw_sha256=e['raw_checkpoint_sha256'], manifest_sha256=e['raw_manifest_sha256'],
        writer_source_sha256=context['writer_source_sha256'], fixture_only=False,
        reference_calendar_scope='full_2020_2026', production_qualified=False).items(): assert seal.get(key) == value, key
    cp._validation(seal['validation'], context, preflight)
    assert preflight['arm'] == arm and preflight['attempt'] == 1 and preflight['account_classes'] == CLASSES[arm]
    assert preflight['capital'] == 150000 and preflight['period'] == ['2020-01-01','2026-10-14']
    days = preflight['reference_calendar']
    assert len(days) == 1641 and days == sorted(set(days)) and days[0] == '2020-01-02' and days[-1] == '2026-10-14'
    readiness = preflight['execution_readiness']; rd = read(readiness['path'])
    assert sha(readiness['path']) == readiness['sha256'] and rd == readiness['document']
    assert rd['schema'] == 'stage065_pairwise_off_execution_readiness_v1' and rd['issued_by'] == 'root'
    assert rd['arm'] == arm and rd['financial_execution_authorized'] is True and rd['independent_integration_accepted'] is True
    assert rd['period']==preflight['period'] and rd['capital']==150000
    assert rd['limits_decision']==dict(action='inherit_original_limits',wait_seconds=1800,run_seconds=7200)
    assert check_family(rd,arm)==check_family(e,arm)
    parent=rd['prior_A_OFF_checkpoint_failure']
    assert sha(regular(parent['path']))==parent['sha256']
    for group in ('source_bindings','data_bindings'): assert rd[group] == preflight[group]
    # These are inherited external qualifications, not self-review of 071/087.
    inherited = {}
    for key, (folder, expected) in INHERITED.items():
        path = LINE/'outputs'/folder/'review_receipt.json'; report = read(path)
        assert sha(path) == expected and report['independent_review'] is True
        assert report['p0_findings'] == report['p1_findings'] == 0
        inherited[key] = dict(path=str(path), sha256=expected, independently_reaudited_here=False)
    assert preflight['source859_isolation_review_sha256'] == INHERITED['source859'][1]
    assert preflight['accepted_wait_delta_review_sha256'] == INHERITED['accepted061'][1]
    scope_review = preflight['data_scope_binding']['review']
    assert rd['data_scope_review']==scope_review
    # 094 remains historical inheritance. The new family's independently
    # reviewed sources are externally bound by the actual root readiness.
    review_path=regular(scope_review['path']);review_raw=review_path.read_bytes()
    assert hashlib.sha256(review_raw).hexdigest()==scope_review['sha256']
    current_review=json.loads(review_raw)
    assert current_review['independent_review'] is True
    assert current_review['p0_findings']==current_review['p1_findings']==0
    expected_scope={str(TOOLS/name):preflight['source_bindings'][str(TOOLS/name)]
        for name in ('stage087_off_data_scope.py','stage087_off_data_provider.py')}
    assert current_review['source_bindings']==expected_scope
    for name,binding in expected_scope.items():
        path=regular(name)
        assert sha(path)==binding['sha256'] and path.stat().st_size==binding['bytes']
    inherited['current_data_scope']=dict(path=str(review_path),sha256=scope_review['sha256'],
        source_bindings=expected_scope,independently_reaudited_here=False)
    return raw, context, preflight, manifest, seal, inherited


def settings_review(payload, pd):
    actual = payload['actual']; assert len(actual) == 1 and actual[0]['supply_demand_signal_rows'] == 0
    row = actual[0]; settings = row['actual']
    requested = {k:v for k,v in row['setting'].items() if k not in row['non_strategy_fields']}
    assert requested == settings
    for key, value in OFF.items():
        assert settings[key] == value and (not isinstance(value, bool) or settings[key] is value), key
        assert payload['parameters']['spec']['overrides'][key] == value
    effective = payload['effective_off_policy']; assert len(effective) == 1
    assert effective[0]['status'] == 'passed_effective_pairwise_off'
    ev = effective[0]['effective']
    for key, value in OFF.items(): assert ev[key] == value and (not isinstance(value, bool) or ev[key] is value)
    assert ev['selection_pairwise_runtime'] is ev['ai_path_damage_runtime'] is None
    assert ev['enable_ai_path_damage_risk_discount'] is False and ev['stage827_require_complete_minutes'] is True
    assert ev['enable_ai_product_pool_filter'] is True
    assert ev['ai_product_pool_eligibility_path'] == settings['ai_product_pool_eligibility_path']
    # Compact original settings/parameters only; never load old account curves.
    ref = ROOT/'research/lines/futures_trend_rollover_shape_same_volume/outputs/stage251_half_r_ab/A_final3'
    fingerprints = payload['input_fingerprints']
    for name in ('actual_strategy_settings.json','effective_parameters.json'):
        path = ref/name; assert sha(regular(path)) == fingerprints[str(path)]['sha256']
    reference = read(ref/'actual_strategy_settings.json')[0]['actual']
    expected = read(ref/'effective_parameters.json'); expected['spec']['overrides'].update(OFF)
    defaults = payload['preflight']['requested_settings_check']['declared_defaults_used']
    assert set(defaults).issubset(OFF)
    reference = {**defaults, **reference, **OFF}
    normal = pure_functions('stage022_run_c0_qualified_wait.py', ['normalize_reference'], {})['normalize_reference']
    shared = ACCOUNTS/'shared_empty_signal_inputs'; old_shared = Path(reference['supply_demand_signal_path']).parent
    assert normal(settings, shared, old_shared) == normal(reference, shared, old_shared)
    assert normal(payload['parameters'], shared, old_shared) == normal(expected, shared, old_shared)
    ranks = 0
    for frame in [payload['frames']['entry_candidates'], pd.DataFrame((payload['ordered'] or {}).get('decision', []))]:
        if 'selection_pairwise_rank' not in frame: assert frame.empty; continue
        values = pd.to_numeric(frame.selection_pairwise_rank, errors='raise').fillna(0)
        assert values.eq(0).all(), 'actual pairwise rank survived OFF'; ranks += len(values)
        if 'selection_pairwise_score' in frame:
            scores = pd.to_numeric(frame.selection_pairwise_score, errors='raise').fillna(0)
            assert scores.eq(0).all(), 'actual pairwise score survived OFF'
    return settings, dict(eight_keys_exact=True, actual_pairwise_rank_zero_rows=ranks,
        pairwise_runtime_absent=True, monthly_AI_eligibility_retained=True,
        compact_reference_settings_parameters_checked=True, old_account_PnL_read=False)


def raw_exports(payload, export, arm, cp, a33, pd):
    hashes = {}
    def table(name, frame):
        frame = frame.copy(deep=False)
        if frame.empty and not len(frame.columns): frame = pd.DataFrame(columns=['date','vt_symbol','event','reason'])
        frame = frame.copy(deep=False); frame['research_arm'] = arm; frame['production_qualified'] = False
        expected = a33.serialized_csv_sha(frame)
        assert sha(regular(export/name)) == expected, ('raw/export table mismatch', name)
        hashes[name] = expected
    pure = pure_functions('stage022_run_c0_qualified_wait.py', ['canonical_trade_enums','attach_trading_dates'], {})
    clock_env = dict(prior=SimpleNamespace(**pure))
    clock_fn = pure_functions('stage031_run_ordered_checkpoint.py', ['build_execution_clock'], clock_env)['build_execution_clock']
    clock, usage = clock_fn(payload['capture'], payload['actual_trade_identities'])
    sources = clock.trade_id.map(usage.set_index('trade_id').price_source).fillna('')
    synthetic = clock.offset.ne('开') & sources.str.startswith('stage')
    clock.loc[synthetic, 'exit_reason'] = sources[synthetic]
    trades = pure['attach_trading_dates'](pure['canonical_trade_enums'](payload['frames']['trades']), clock)
    for name, frame in payload['frames'].items(): table(name+'.csv', trades if name == 'trades' else frame)
    for name, frame in [('daily.csv',payload['combined']), ('execution_clock.csv',clock),
        ('execution_proxy_usage.csv',usage), ('actual_trade_identities.csv',pd.DataFrame(payload['actual_trade_identities'])),
        ('internal_equity_daily.csv',pd.DataFrame(payload['capture']['equity'])),
        ('minute_scan_requests.csv',pd.DataFrame(payload['capture']['minute_requests'])),
        ('execution_anchor_requests.csv',pd.DataFrame(payload['capture']['anchor_requests']))]: table(name, frame)
    if arm == 'A_OFF':
        assert payload['ordered'] is None
        assert not any((export/name).exists() for name in ('ordered_gate_audit.csv','ordered_fill_audit.csv',
            'ordered_execution_audit.csv','ordered_pending_intents.csv','ordered_audits.json'))
    else:
        assert set(payload['ordered']) == {'decision','fill','execution','pending'}
        for key, name in [('decision','ordered_gate_audit.csv'),('fill','ordered_fill_audit.csv'),
            ('execution','ordered_execution_audit.csv'),('pending','ordered_pending_intents.csv')]: table(name,pd.DataFrame(payload['ordered'][key]))
        assert read(export/'ordered_audits.json') == a33.json_projection(payload['ordered'])
    for name, expected in [('actual_strategy_settings.json',payload['actual']), ('effective_parameters.json',payload['parameters']),
        ('input_manifest.json',payload['input_fingerprints']), ('effective_off_policy.json',payload['preflight']['disabled_pairwise']),
        ('qualified_wait_audit.json',dict(gate=payload['wait_audit'],resolver=payload['resolver_audit'],initial_qualification=payload['qualification_audit']))]:
        assert read(export/name) == a33.json_projection(expected); hashes[name] = sha(export/name)
    identity = a33.identity_audit(payload['capture']['usage'],payload['actual_trade_identities'],clock,usage)
    return trades, usage, clock, hashes, identity


def a_mothers(t, candidates, rollover, p, d, parameters, pd):
    """Exact accepted Stage001 A0 scalar episode block, not B candidates."""
    code=adapter_fragments()['A0_episode_block']
    env = dict(pd=pd); exec(compile(code, 'frozen_A0_episode_block', 'exec'),env)
    return env['scalar'](t,candidates,rollover,p,d,parameters)


def audit(e, evidence_path, evidence_sha, export):
    for name in PINS: source(name)
    np, pd = runtime(); cp = module('stage065_account_checkpoint.py')
    raw, context, preflight, manifest, seal, inherited = bind_checkpoint(e,e['arm'],cp)
    a33 = module('stage033_independent_checkpoint_account_review.py')
    payload = a33.OwnedAccountUnpickler(io.BytesIO(gzip.decompress(raw))).load()
    assert payload['schema'] == 'stage065_raw_account_checkpoint_v1'
    assert payload['run_context'] == context and payload['preflight'] == preflight
    assert math.isfinite(float(payload['engine_elapsed_seconds'])) and 0<float(payload['engine_elapsed_seconds'])<=7200
    assert isinstance(payload['combined'],pd.DataFrame) and all(isinstance(v,pd.DataFrame) for v in payload['frames'].values())
    assert payload['capture']['failures'] == [] and payload['spec'] == payload['parameters']['spec']
    arm=e['arm']; output=OUT/arm/context['run_id']; assert not output.exists()
    output.mkdir(parents=True)
    try:
        settings, off_checks = settings_review(payload,pd)
        assert sha(regular(export/'summary.json')) == e['summary_sha256']
        summary=read(export/'summary.json'); prov=read(export/'run_provenance.json'); success=read(ACCOUNTS/arm/'export_success.json')
        assert success == dict(status='completed_pending_independent_review',source=str(export),summary_sha256=e['summary_sha256'],
            raw_sha256=e['raw_checkpoint_sha256'],run_id=context['run_id'],arm=arm,fixture_only=False)
        for doc in (summary,prov):
            assert doc['arm']==arm and doc['run_id']==context['run_id'] and doc['attempt']==1
            assert doc['status']=='completed_pending_independent_review' and doc['fixture_only'] is False
            assert doc['result_scope']==SCOPE and doc['reference_calendar_scope']=='full_2020_2026'
            assert doc['ordered_applicable'] is (arm=='B_OFF') and doc['signal_machine_arm']==('B_TS' if arm=='B_OFF' else None)
            assert doc['account_classes']==CLASSES[arm] and doc['financial_replays']==1 and doc['production_qualified'] is False
            assert doc['source_bindings']==context['source_bindings'] and doc['data_bindings_sha256']==context['data_bindings_sha256']
            assert doc['disabled_pairwise']==preflight['disabled_pairwise']
            assert doc['checkpoint']==dict(manifest=manifest,seal=seal,seal_sha256=e['validation_seal_sha256'])
            assert doc['financial_replays_this_export_process']==(0 if doc['export_only'] else 1)
        assert summary['statistics']==read(export/'metrics.json') and summary['checkpoint_raw_sha256']==e['raw_checkpoint_sha256']
        t,u,clock,hashes,identity=raw_exports(payload,export,arm,cp,a33,pd)
        base=module('stage030_independent_ordered_account_review.py')
        d=payload['combined'].copy(); d['date']=pd.to_datetime(d.date).dt.strftime('%Y-%m-%d')
        assert d.date.tolist()==preflight['reference_calendar'] and d.account_capital.eq(150000).all()
        assert t.date.eq(t.trading_date).all() and t.trade_id.is_unique
        joined=t.merge(clock,on='trade_id',suffixes=('','_clock'),validate='one_to_one')
        assert len(joined)==len(t)==len(clock)
        for key in ('trading_date','vt_symbol','direction','offset'):
            assert joined[key].eq(joined[key+'_clock']).all(), ('actual TradeData/frames conflict',key)
        for key in ('price','volume'):
            assert joined[key].eq(joined[key+'_clock']).all(), ('actual TradeData/frames value conflict',key)
        t=t.merge(u[['trade_id','signal_date','price_source','execution_datetime','signal_order_id']],on='trade_id',validate='one_to_one')
        t['fill_number']=t.trade_id.str.rsplit('.',n=1).str[-1].astype(int);t=t.sort_values('fill_number').reset_index(drop=True)
        assert t.fill_number.tolist()==list(range(1,len(t)+1))
        times=[base.stamp(x) for x in t.execution_datetime]; assert times==sorted(times)
        assert all(base.stamp(x).date().isoformat()<=day for x,day in zip(t.execution_datetime,t.date))
        assert (pd.to_numeric(t.volume)>0).all() and np.equal(t.volume,np.round(t.volume)).all()
        base.close(t.signed_volume,t.volume*t.direction.map({'多':1,'空':-1}),'actual signed direction')
        params=payload['parameters']; sizes=t.vt_symbol.map(params['contract_sizes']).astype(float)
        t['independent_slippage']=t.volume*sizes*t.vt_symbol.map(params['slippages']).astype(float)
        t['independent_commission']=t.volume*sizes*t.price*t.vt_symbol.map(params['rates']).astype(float)
        t['independent_cash']=-t.signed_volume*sizes*t.price-t.independent_slippage-t.independent_commission
        base._stage033_checkpoint_review={}; a33.use_raw_positions_once(base,payload)
        marks,last_marks,residuals,position_rows=base.audit_inventory(export,d,t,params,settings)
        cash=t.groupby('date').independent_cash.sum().reindex(d.date,fill_value=0).cumsum().to_numpy()
        equity=150000+cash+marks
        residuals['cashflow_equity']=base.close(equity,d.account_equity,'cashflow equity')
        residuals['daily_pnl_equity']=base.close(150000+d.net_pnl.cumsum(),d.account_equity,'pnl cumulative equity')
        internal=pd.DataFrame(payload['capture']['equity']); internal['date']=internal.date.astype(str).str[:10]
        internal=d.merge(internal,on='date',validate='one_to_one'); assert len(internal)==len(d)
        residuals['internal_equity']=base.close(internal.account_equity,internal.estimated_equity,'internal equity')
        for field in ('slippage','commission'):
            residuals[field]=base.close(t.groupby('date')['independent_'+field].sum().reindex(d.date,fill_value=0),d[field],'daily '+field)
        base.close(t.groupby('date').size().reindex(d.date,fill_value=0),d.trade_count,'daily fill count')
        metrics=base.reconstruct_metrics(d,t,150000)
        for key,value in metrics.items():
            if key!='total_commission': base.close(value,summary['statistics'][key],'reported metric '+key,atol=1e-7)
        candidates=base.csv(export/'entry_candidates.csv');rollover=base.csv(export/'rollover_shape_same_volume.csv')
        minutes=base.csv(export/'minute_scan_requests.csv')
        assert minutes.missing_bar_count.eq(0).all() and minutes.coverage_status.eq('complete').all()
        base.close(minutes.expected_bar_count,minutes.actual_bar_count,'complete minute counts')
        assert minutes.requested_start.map(base.stamp).eq(minutes.actual_first_time.map(base.stamp)).all()
        b_checks=None; ordered_stats=None
        if arm=='A_OFF':
            p=payload['frames']['positions'][['date','vt_symbol','close_price']].copy();p['date']=p.date.astype(str).str[:10]
            cycles,episodes,active,retries,rolls,open_mtm,cycle_residual=a_mothers(t,candidates,rollover,p,d,params,pd)
            residuals['cycles_and_open_mtm']=float(cycle_residual)
        else:
            b=module('stage038_independent_b_ts_account_review.py')
            # Exact one-line OFF identity adapter: zero AI rank, original serial.
            fragments=adapter_fragments()
            exec(compile(fragments['OFF_zero_rank'],'stage095_OFF_rank_identity_adapter','exec'),b.__dict__)
            b_checks=b.b_artifact_review(a33,payload)
            b_checks.pop('model_domain_limit')
            b_checks['rank_definition']='actual AI original_rank=0; gross prefix ordered by original stable serial; pending ordinal is not an AI rank'
            for item in payload['ordered']['pending']:
                assert type(item['rank']) is int and item['rank']>0 and item['plan']['rank']==item['rank']
            b_checks['pending_ordinal_source']='frozen035 ranks insertion-order plan products; no ordinal substituted for pairwise original_rank'
            # B permits setup and preparation on the same close, per frozen035.
            exec(compile(fragments['B_same_close_setup'],'stage095_B_setup_identity_adapter','exec'),base.__dict__)
            fills,ordered_stats=base.ordered_evidence(export,t,candidates,params,minutes,d)
            cycles,episodes,active,retries,rolls,mothers=base.reconstruct_episodes(t,candidates,fills,rollover)
            open_mtm=sum(v['net_cash']+v['quantity']*last_marks[sym]*params['contract_sizes'][sym] for sym,v in active.items())
            residuals['cycles_and_open_mtm']=base.close(cycles.net_cash.sum()+open_mtm,d.net_pnl.sum(),'cycles plus open mtm')
        # Both A0 and B retry roots require the same actual earlier opening.
        for link in retries:
            retry=t.loc[t.trade_id.eq(link['retry_fill'])].iloc[0]
            original=t.loc[t.order_id.eq(link['parent_order']) & t.offset.eq('开')]
            assert len(original)==1 and original.iloc[0].vt_symbol==retry.vt_symbol and original.iloc[0].date==retry.date
            assert base.stamp(original.iloc[0].execution_datetime)<base.stamp(retry.execution_datetime)
        for link in rolls:
            opening=t.loc[t.trade_id.eq(link['fill'])].iloc[0]
            closes=t.loc[t.vt_symbol.eq(link['source_contract']) & t.offset.ne('开') & t.date.eq(opening.date) & t.signal_date.eq(link['signal_date'])]
            assert len(closes) and closes.volume.sum()+1e-9>=opening.volume
            assert all(base.stamp(value)<=base.stamp(opening.execution_datetime) for value in closes.execution_datetime)
        ratio=d.c3_margin_exact*1.65/equity*100
        diagnostic=dict(multiplier=1.65,max_margin_to_equity_pct=float(ratio.max()),
            days_over_100pct=int((ratio>100+1e-9).sum()),days_over_90pct=int((ratio>90+1e-9).sum()),
            replaces_original_seven_gates=False,is_full_minute_PIT_peak=False,native_fill_time_budget_rechecked=False)
        for name,frame in [('independent_cycles.csv',cycles),('independent_mother_order_episodes.csv',episodes),
            ('independent_retry_links.csv',pd.DataFrame(retries)),('independent_rollover_open_links.csv',pd.DataFrame(rolls)),
            ('independent_equity.csv',pd.DataFrame(dict(date=d.date,independent_equity=equity,reported_equity=d.account_equity))),
            ('additional_165_daily_margin.csv',pd.DataFrame(dict(date=d.date,margin_165=d.c3_margin_exact*1.65,equity=equity,ratio_pct=ratio)))]:
            frame.to_csv(output/name,index=False)
        for name,expected in hashes.items(): assert sha(export/name)==expected, ('export changed during review',name)
        assert sha(evidence_path)==evidence_sha and sha(ACCOUNTS/arm/'checkpoint/raw_account.pkl.gz')==e['raw_checkpoint_sha256']
        result=dict(schema='stage095_independent_off_account_review_v1', independent_review=True,
            status='accepted_independent_cash_inventory_costs_identity_and_OFF_account', reviewed_at=datetime.now().astimezone().isoformat(),
            arm=arm,attempt=1,run_id=context['run_id'],owner_root=str(ACCOUNTS/arm),export_source=str(export),
            **check_family(e,arm),prior_A_OFF_status='failed_no_complete_performance_NA',
            completion_evidence_path=str(evidence_path),completion_evidence_sha256=evidence_sha,review_script_sha256=sha(__file__),
            raw_checkpoint_sha256=e['raw_checkpoint_sha256'],source_bindings=context['source_bindings'],export_hashes=hashes,
            actual_daily_dates=1641,reference_calendar=preflight['reference_calendar'],reconstructed_metrics=metrics,
            residuals=residuals,positions_rows_streamed_once=position_rows,identity=identity,OFF_policy=off_checks,
            ordered_applicable=arm=='B_OFF',signal_machine_arm='B_TS' if arm=='B_OFF' else None,
            B_artifacts=b_checks,ordered_execution=ordered_stats,closed_contract_cycles=len(cycles),
            complete_mother_order_episodes=len(episodes),mother_order_episode_wins=int(episodes.net_pnl.gt(1e-6).sum()),
            mother_order_episode_win_rate_pct=float(episodes.net_pnl.gt(1e-6).mean()*100) if len(episodes) else None,
            confirmed_retry_parent_links=len(retries),confirmed_rollover_reopen_links=len(rolls),end_open_contracts=len(active),
            end_open_net_mtm=float(open_mtm),daily_reporting_margin_multiplier=1.10,additional_165_daily_margin_diagnostic=diagnostic,
            inherited_external_data_qualification_reviews=inherited,financial_replays=0,model_loads=0,model_fits=0,network_calls=0,
            p0_findings=0,p1_findings=0,p2_findings=0,fixture_only=False,original_goal_achieved=False,promotion_allowed=False,production_qualified=False,
            limits=['daily close margin only; intraminute portfolio peak not established','single historical path; no OOS/multicycle or cost-pressure pass',
                'data qualification inherited from external078/081/094, not self-review of071/087','win denominator excludes every still-open mother; all costs charged once per actual fill'])
        write(output/'account_checks.json',a33.json_projection(result)); return result,output/'account_checks.json'
    except BaseException as error:
        write(output/'audit_failure.json',dict(schema='stage095_independent_off_account_audit_failure_v1',arm=arm,
            run_id=context['run_id'],status='blocked_no_accepted_economic_result',error=repr(error),
            completion_evidence_path=str(evidence_path),completion_evidence_sha256=evidence_sha,financial_replays=0,production_qualified=False))
        raise


def compare(paths, shas):
    """Only accepted independent arm receipts; no account, market or model read."""
    assert len(paths)==len(shas)==2
    reports={}
    for path,pin in zip(paths,shas):
        assert sha(regular(path))==pin; row=read(path); arm=row['arm']
        assert arm not in reports and arm in CLASSES
        assert row['schema']=='stage095_independent_off_account_review_v1' and row['independent_review'] is True
        assert row['status']=='accepted_independent_cash_inventory_costs_identity_and_OFF_account'
        assert row['p0_findings']==row['p1_findings']==0 and row['fixture_only'] is False and row['actual_daily_dates']==1641
        assert row['review_script_sha256']==sha(__file__)
        check_family(row,arm)
        reports[arm]=row
    assert set(reports)==set(CLASSES) and reports['A_OFF']['reference_calendar']==reports['B_OFF']['reference_calendar']
    runtime(); cmp=module('stage001_compare.py')
    rows=[dict(arm='A0',status='restricted_fixed_pairwise_counterfactual_057_058_P1s',
        end_equity=2262595.,total_return_pct=1408.396667,max_dd_pct=-48.789850,sharpe=1.367364),
        dict(arm='original_B',status='failed_qualified_delivery_old_value_conflict_NA',end_equity=None,total_return_pct=None,max_dd_pct=None,sharpe=None)]
    rows += [dict(arm=arm,status='independently_reconciled',global_arm_attempt=reports[arm]['global_arm_attempt'],
        **reports[arm]['reconstructed_metrics']) for arm in CLASSES]
    b=reports['B_OFF']['reconstructed_metrics']
    result=dict(schema='stage095_independent_four_row_comparison_v1',rows=rows,
        repaired_checkpoint_family='stage099_checkpoint_metadata_fix_v1',global_financial_attempts_before_family=9,
        prior_A_OFF_checkpoint_failure=family_metadata('A_OFF')['prior_A_OFF_checkpoint_failure'],
        prior_A_OFF_status='failed_no_complete_performance_NA',
        paired_seven_gates=cmp.evaluate_metrics(reports['A_OFF']['reconstructed_metrics'],b),
        B_OFF_vs_restricted_A0_context=dict(higher_return=b['total_return_pct']>1408.396667,lower_drawdown=b['max_dd_pct']>-48.789850,
            strict_PIT_or_fair_common_policy_comparison=False),
        input_receipts=[dict(path=str(p),sha256=s) for p,s in zip(paths,shas)],
        no_goal_claim_from_only_beating_A_OFF=True,original_goal_achieved=False,promotion_allowed=False,production_qualified=False)
    dest=OUT/'comparison'/(reports['A_OFF']['run_id']+'_'+reports['B_OFF']['run_id'])/'comparison.json'
    write(dest,result);return dest


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__); action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--schema-check',action='store_true'); action.add_argument('--audit',action='store_true'); action.add_argument('--compare',action='store_true')
    parser.add_argument('--arm',choices=tuple(CLASSES));parser.add_argument('--completion-evidence',type=Path);parser.add_argument('--completion-evidence-sha256')
    parser.add_argument('--account-review',type=Path,nargs=2);parser.add_argument('--account-review-sha256',nargs=2)
    args=parser.parse_args(argv)
    if args.schema_check: print(json.dumps(schema_check(),ensure_ascii=False));return 0
    if args.compare:
        path=compare(args.account_review,args.account_review_sha256)
        print(json.dumps(dict(status='four_row_comparison_written_no_promotion',path=str(path),sha256=sha(path))));return 0
    assert args.arm and args.completion_evidence and args.completion_evidence_sha256
    path=regular(args.completion_evidence); assert sha(path)==args.completion_evidence_sha256
    evidence=read(path); export=terminal_schema(evidence,args.arm)
    result,dest=audit(evidence,path,args.completion_evidence_sha256,export)
    print(json.dumps(dict(status=result['status'],arm=args.arm,receipt_path=str(dest),receipt_sha256=sha(dest)),ensure_ascii=False));return 0


if __name__=='__main__': raise SystemExit(main())
