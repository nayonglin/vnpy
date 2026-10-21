"""Sign two empty research states with real321; never execute market/cash logic.

prepare writes only source bindings and an unauthorized root template.
initialize is a separate explicit root action. No future proposal is made here.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import os
from pathlib import Path
import sys

import numpy as np

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
REFERENCE = LINE/'outputs/stage359_local_reference_actual/actual_run1'
SUCCESSOR_SCOPE = LINE/'outputs/stage370_paper_initialization_actual/initialization_scope.json'
SUCCESSOR_SCOPE_SHA = 'fe77bce172b81c19da026e198e56add1b08d65bdbf51ec606d26b8f32b38074d'
POLICY = 'PURE52_MAIN2023_VOLUNTARY_RESELECT_NARROW'
DEADLINE = '2026-10-20T15:15:00+08:00'
TARGET_U = '2026-10-20'
KERNEL_SHA = {
    'stage131_contract_choice_kernel.py': '85205ef9bc309a34283fc0082ac09c53d1f156ca788b8efe6bbd9743f5f430b5',
    'stage070_policy_kernel.py': 'ad000624bd9722b3f1c580d622df2fc190330bac9e3c04011856085d56abcffe',
    'stage042_cross_session_experiment.py': 'ca40a4cf7b761b34f70d973a943723601d0ecf5fc355da3559d5bcbeff36661d',
}
CALLER_FILES = ('stage320_causal_forward_core.py', 'stage321_forward_journal.py',
                'stage322_continuous_paper_state.py', 'stage325_forward_caller.py')
PARAMETERS = dict(target_u=TARGET_U, expected_start_u=5290, initial=1000000.,
    account_ids=dict(base='pure52_main2023_narrow_base_tinit_u20',
                     stress='pure52_main2023_narrow_stress_tinit_u20'),
    policy='NARROW', single_risk=.0025, total_risk=.02, margin_cap=.25,
    margin_buffer=1.1, initial_stop_N=.25,
    costs=dict(base=dict(fee_min=2., fee_bps=.0001, slip_bps=.0001, slip_ticks=1, margin_floor=.20),
               stress=dict(fee_min=6., fee_bps=.0003, slip_bps=.0003, slip_ticks=3, margin_floor=.40)))
NEXT_BOUNDARY = ('Initialization only. Future research requires accepted input, T_init strictly '
    'before actual source_completed_at, and a new complete325 proposal receipt strictly before '
    'the full execution-domain D_open. No inherited unfunded seal, start_u jump, reset or backdate.')


def binding(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def _bound(item):
    path = Path(item['path'])
    if path.is_symlink() or not path.is_file():
        raise ValueError('binding requires a regular file')
    raw = path.read_bytes()
    if len(raw) != item['bytes'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
        raise ValueError('binding bytes/SHA mismatch: '+str(path))
    return raw


def _write_raw(path, raw):
    path = Path(path)
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o444)
    return binding(path)


def write(path, value):
    return _write_raw(path, (json.dumps(value, ensure_ascii=False, sort_keys=True,
        indent=2, allow_nan=False)+'\n').encode())


def _load(path, name):
    # Imports of exact pure definitions must not create pycache in frozen359.
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.dont_write_bytecode = previous


def _runtime():
    return dict(python=sys.version, numpy=importlib.metadata.version('numpy'),
                pandas=importlib.metadata.version('pandas'))


def _time(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('timezone required')
    return result.astimezone(timezone.utc)


def prepare(output):
    """Read only small source/reference metadata; no imports or paper states."""
    out = Path(output).resolve()
    if out.exists():
        raise FileExistsError('fresh preparation output required')
    closure = binding(REFERENCE/'closure_manifest.json')
    manifest = json.loads(_bound(closure))
    def asset(filename):
        matches = [v for v in manifest['artifacts'] if Path(v['logical_name']).name == filename]
        if len(matches) != 1:
            raise ValueError('unique frozen359 asset required: '+filename)
        item = {k: matches[0][k] for k in ('path', 'bytes', 'sha256')}
        _bound(item)
        return item
    frozen_sources = {name: asset(name) for name in CALLER_FILES}
    kernels = {name: (binding(TOOLS/name) if name.startswith('stage131_') else asset(name))
               for name in KERNEL_SHA}
    for name, item in kernels.items():
        if item['sha256'] != KERNEL_SHA[name]:
            raise ValueError('accepted pure kernel changed: '+name)
    bundle = dict(schema='stage368_initialization_source_bundle_v1',
        initializer=binding(__file__), runtime=_runtime(), reference_root=str(REFERENCE.resolve()),
        reference=dict(closure_manifest=closure, freeze_event=binding(REFERENCE/'freeze_event.json'),
                       policy_identity=binding(REFERENCE/'policy_identity.json')),
        frozen_sources=frozen_sources, kernel_sources=kernels,
        frozen_inputs=dict(model=asset('portable_model.json'), scaler=asset('scaler.json'),
            clock_contract=asset('clock_contract.json'), source_calendar=asset('trading_dates.npy')))
    out.mkdir(parents=True)
    source = write(out/'source_bundle.json', bundle)
    auth = dict(schema='stage368_paper_initialization_authorization_v1', authorized=False,
        authorized_by='root', source_bundle=source, initialization_deadline=DEADLINE,
        successor_scope=binding(SUCCESSOR_SCOPE),
        parameters=PARAMETERS, mode='empty_research_initialization_only', active=False,
        next_boundary=NEXT_BOUNDARY)
    template = write(out/'root_authorization_template.json', auth)
    return dict(source_bundle=source, authorization_template=template, actual_initializations=0)


def initialize(auth, output):
    """Only two new_state calls and one actual321 event; never seal or advance."""
    out = Path(output).resolve()
    if out.exists():
        raise FileExistsError('fresh initialization output required; never overwrite')
    auth = json.loads(Path(auth).read_bytes()) if isinstance(auth, (str, Path)) else auth
    if (auth.get('schema') != 'stage368_paper_initialization_authorization_v1'
            or auth.get('authorized') is not True or auth.get('authorized_by') != 'root'):
        raise ValueError('explicit root authorization required')
    if (auth.get('parameters') != PARAMETERS or auth.get('initialization_deadline') != DEADLINE
            or auth.get('mode') != 'empty_research_initialization_only'
            or auth.get('active') is not False or auth.get('next_boundary') != NEXT_BOUNDARY):
        raise ValueError('fixed initialization scope/parameters changed')
    if datetime.now(timezone.utc) >= _time(DEADLINE):
        raise ValueError('initialization preflight is not before15:15')
    successor = json.loads(_bound(auth['successor_scope']))
    if (auth['successor_scope']['path'] != str(SUCCESSOR_SCOPE.resolve())
            or auth['successor_scope']['sha256'] != SUCCESSOR_SCOPE_SHA
            or successor.get('schema') != 'stage370_separate_paper_initialization_scope_v1'
            or successor.get('target_u') != TARGET_U
            or successor.get('hard_initialization_deadline') != DEADLINE):
        raise ValueError('root separate successor scope binding changed')
    bundle_raw = _bound(auth['source_bundle'])
    bundle = json.loads(bundle_raw)
    if bundle.get('schema') != 'stage368_initialization_source_bundle_v1':
        raise ValueError('initialization source bundle required')
    if bundle['initializer'] != binding(__file__) or bundle['runtime'] != _runtime():
        raise ValueError('initializer/runtime binding changed')
    if Path(bundle['reference_root']).resolve() != REFERENCE.resolve() or out.is_relative_to(REFERENCE.resolve()):
        raise ValueError('frozen359 reference must remain separate')
    captured = {}
    for group in ('reference', 'frozen_sources', 'kernel_sources', 'frozen_inputs'):
        captured[group] = {name: _bound(item) for name, item in bundle[group].items()}
    for name, expected in KERNEL_SHA.items():
        if bundle['kernel_sources'][name]['sha256'] != expected:
            raise ValueError('accepted pure kernel binding changed')
    freeze = json.loads(captured['reference']['freeze_event'])
    identity = json.loads(captured['reference']['policy_identity'])
    T0 = freeze['receipt']['recorded_at']
    if (freeze.get('schema') != 'stage359_research_reference_freeze_v1'
            or freeze['receipt']['kind'] != 'research_reference_freeze'
            or freeze['closure_manifest'] != bundle['reference']['closure_manifest']
            or freeze['clock_contract'] != bundle['frozen_inputs']['clock_contract']
            or identity.get('policy') != POLICY or identity.get('frozen_at') != T0
            or T0 != '2026-10-19T20:21:56.703789+00:00'
            or successor.get('reference_T0') != T0
            or successor.get('reference_freeze_event') != bundle['reference']['freeze_event']):
        raise ValueError('original359 reference identity mismatch')
    if datetime.now(timezone.utc) <= _time(T0):
        raise ValueError('initialization clock must be after original359 freeze')
    closure = json.loads(captured['reference']['closure_manifest'])
    if closure.get('schema') != 'stage359_local_research_closure_v1' or closure.get('states') is not None or closure.get('active') is not False:
        raise ValueError('original unfunded359 closure required')
    assets = {(v['path'], v['bytes'], v['sha256']) for v in closure['artifacts']}
    for group in ('frozen_sources', 'frozen_inputs'):
        for item in bundle[group].values():
            if (item['path'], item['bytes'], item['sha256']) not in assets:
                raise ValueError('dependency is outside frozen359 closure')
    for name, item in bundle['frozen_sources'].items():
        if identity['source_sha256'].get(name) != item['sha256']:
            raise ValueError('original325 source identity changed')
    dates_array = np.load(io.BytesIO(captured['frozen_inputs']['source_calendar']), allow_pickle=False)
    if dates_array.ndim != 1 or not np.issubdtype(dates_array.dtype, np.integer):
        raise ValueError('bound source calendar must be integer dates')
    dates = [str(int(value)) for value in dates_array]
    if dates != sorted(set(dates)):
        raise ValueError('source calendar must be ordered and unique')
    start_u = dates.index(TARGET_U.replace('-', ''))
    if start_u != PARAMETERS['expected_start_u']:
        raise ValueError('target_u20 source calendar index changed')
    parameters = dict(PARAMETERS, start_u=start_u)
    model = json.loads(captured['frozen_inputs']['model'])
    scaler = json.loads(captured['frozen_inputs']['scaler'])
    caller = _load(bundle['frozen_sources']['stage325_forward_caller.py']['path'], 'stage368_frozen325')
    if caller.make_policy_identity(model, scaler, frozen_at=T0) != identity:
        raise ValueError('original model/scaler/caller identity mismatch')
    journal_module = _load(bundle['frozen_sources']['stage321_forward_journal.py']['path'], 'stage368_real321')
    paper = _load(bundle['frozen_sources']['stage322_continuous_paper_state.py']['path'], 'stage368_frozen322')
    if datetime.now(timezone.utc) >= _time(DEADLINE):
        raise ValueError('initialization preflight elapsed before output creation')
    out.mkdir(parents=True)
    kernel_dir = out/'payload'/'kernel'
    kernel_dir.mkdir(parents=True)
    copied = {name: _write_raw(kernel_dir/name, raw) for name, raw in captured['kernel_sources'].items()}
    initializer_copy = _write_raw(out/'initializer_source.py', _bound(bundle['initializer']))
    kernel = _load(copied['stage131_contract_choice_kernel.py']['path'], 'stage368_pure131')
    observed_constants = {k: getattr(kernel, n) for k, n in (
        ('initial', 'INITIAL'), ('single_risk', 'SINGLE_RISK'), ('total_risk', 'TOTAL_RISK'),
        ('margin_cap', 'MARGIN_CAP'), ('margin_buffer', 'MARGIN_BUFFER'))}
    if (any(observed_constants[k] != PARAMETERS[k] for k in observed_constants)
            or kernel.policy_k('NARROW') != .25 or kernel.ref.SCENARIOS != PARAMETERS['costs']):
        raise ValueError('original kernel parameters/costs changed')
    identity_file = write(out/'policy_identity.json', identity)
    journal = journal_module.ForwardJournal(out/'model_journal', identity)
    states = {}
    for scenario in ('base', 'stress'):
        state = paper.new_state(scenario=scenario, account_id=PARAMETERS['account_ids'][scenario],
            start_u=start_u, base_kernel=kernel, initial=1000000.)
        state['caller_policy_sha256'] = journal.policy_hash
        states[scenario] = state
    state_files = {scenario: write(out/(scenario+'_state.json'), json.loads(paper.export_state(state)))
                   for scenario, state in states.items()}
    scope = write(out/'next_scope.json', dict(schema='stage368_initialization_only_scope_v1',
        active=False, status='awaiting_actual_completed_u20_acceptance', parameters=parameters,
        initialization_deadline=DEADLINE, next_boundary=NEXT_BOUNDARY,
        no_funded_proposal=True, no_market_data_read=True, preserves359_T0=T0,
        preserves360_observe_only_batch=True))
    counts = dict(new_state_calls=2, new_cash=0, seal_u=0, advance_D=0, new_fit=0,
        model_inference=0, market_API=0, SQL=0, market_data_reads=0, source_calendar_loads=1,
        Git=0, orders=0)
    payload = dict(schema='stage368_complete_empty_initialization_v1', active=False,
        T0=T0, reference=bundle['reference'], original_freeze_receipt=freeze['receipt'],
        successor_scope=auth['successor_scope'],
        policy_identity=identity, policy_identity_file=identity_file, parameters=parameters,
        source_bundle=auth['source_bundle'], initializer_source=initializer_copy,
        kernel_sources=bundle['kernel_sources'], copied_kernel_sources=copied,
        frozen_sources=bundle['frozen_sources'], frozen_inputs=bundle['frozen_inputs'],
        runtime=bundle['runtime'], states=states, state_files=state_files, next_scope=scope,
        counts=counts, next_boundary=NEXT_BOUNDARY, no_funded_proposal=True)
    event = journal.append('paper_state_initialized', payload, key='u20/base-stress/initialization-once')
    T_init = event['recorded_at']
    status = 'initialized_inactive' if _time(T_init) < _time(DEADLINE) else 'initialization_late'
    if _time(T_init) <= _time(T0):
        status = 'initialization_clock_invalid'
    envelope = write(out/'initialization_envelope.json', dict(
        schema='stage368_paper_initialization_envelope_v1', status=status, active=False,
        T0=T0, T_init=T_init, event=event, reference=bundle['reference'], parameters=parameters,
        successor_scope=auth['successor_scope'],
        state_files=state_files, policy_identity=identity, next_scope=scope,
        source_bundle=auth['source_bundle'], kernel_sources=copied,
        prospective_start_qualification='pending_actual_source_completed_at',
        before_initialization_deadline=status == 'initialized_inactive', next_boundary=NEXT_BOUNDARY))
    manifest = write(out/'manifest.json', dict(schema='stage368_initialization_manifest_v1',
        status=status, active=False, T0=T0, T_init=T_init, initialization_envelope=envelope,
        state_files=state_files, policy_identity=identity_file, next_scope=scope,
        source_bundle=auth['source_bundle'], initializer_source=initializer_copy,
        kernel_sources=copied, reference=bundle['reference'], successor_scope=auth['successor_scope'],
        parameters=parameters, counts=counts))
    result = dict(schema='stage368_initialization_result_v1', status=status, active=False,
        T0=T0, T_init=T_init, initialization_envelope=envelope, manifest=manifest,
        state_files=state_files, parameters=parameters, counts=counts, no_funded_proposal=True)
    write(out/'result.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--output', required=True)
    init = sub.add_parser('initialize')
    init.add_argument('--authorization', required=True)
    init.add_argument('--output', required=True)
    args = parser.parse_args()
    result = prepare(args.output) if args.command == 'prepare' else initialize(args.authorization, args.output)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
