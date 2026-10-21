"""Finite new-version empty initialization and accepted same-composed interface.

No receiver, serializer/restorer, training or historical runner. Actual root
initialization uses fixed378 scope and a prepared source binding, not a new auth
system. The shared-input interface awaits actual361/362/363 handoff evidence.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
SCOPE = LINE/'outputs/stage378_latest_model_initialization_decision/scope.json'
SCOPE_SHA = 'ac56dba9fbfc9732f49d333c9414cffbb51e78e1114348f73ef9102e01098f0c'
ACTUAL = SCOPE.parent/'actual_run1'
REFERENCE = LINE/'outputs/stage359_local_reference_actual/actual_run1'
CANDIDATE = 'PURE52_LATEST_MATURE_20261020'
BASELINE = 'PURE52_MAIN2023_VOLUNTARY_RESELECT_NARROW'
TARGET_U = '2026-10-20'
ACCEPTANCE_SCHEMA = 'stage376_same_composed_acceptance_v1'
EXPLANATION = ('Metadata-only legacy320/156 API mapping: cutoff2023 is engine_fold_tag; '
    'actual training cutoff and source artifacts remain separately bound. No numeric change.')


@lru_cache(maxsize=1)
def helper():
    spec = importlib.util.spec_from_file_location('stage376_pure368', TOOLS/'stage368_initialize_paper_reference.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def components():
    caller = helper()._load(TOOLS/'stage325_forward_caller.py', 'stage376_original325')
    return SimpleNamespace(caller=caller, paper=caller._components().paper,
                           journal=caller._components().journal)


def _json(item):
    return json.loads(helper()._bound(item))


def _assets():
    h = helper()
    closure = _json(h.binding(REFERENCE/'closure_manifest.json'))
    def asset(name):
        rows = [x for x in closure['artifacts'] if Path(x['logical_name']).name == name]
        if len(rows) != 1:
            raise ValueError('unique frozen359 small asset required: '+name)
        return {k: rows[0][k] for k in ('path', 'bytes', 'sha256')}
    return asset


def prepare(output):
    """Small bindings only; no accounts, calendar array or future scores."""
    h = helper()
    out = Path(output)
    if out.exists():
        raise FileExistsError('fresh preparation required')
    scope_b = dict(path=str(SCOPE), bytes=3560, sha256=SCOPE_SHA)
    scope = _json(scope_b)
    if scope['schema'] != 'stage378_finite_latest_model_forward_wiring_scope_v1':
        raise ValueError('fixed378 scope required')
    frozen = _json(scope['frozen_version'])
    event = _json(frozen['freeze_event'])
    if (event['receipt']['kind'] != 'research_reference_freeze'
            or event['receipt']['recorded_at'] != frozen['T1']
            or event['model'] != frozen['model'] or event['scaler'] != frozen['scaler']):
        raise ValueError('real375 model freeze binding differs')
    asset = _assets()
    original_identity = _json(h.binding(REFERENCE/'policy_identity.json'))
    sources = {name:h.binding(TOOLS/name) for name in (*h.CALLER_FILES,
        'stage368_initialize_paper_reference.py', 'stage376_shared_frozen_profiles.py',
        'test_stage376_shared_frozen_profiles.py')}
    for name in h.CALLER_FILES:
        if sources[name]['sha256'] != original_identity['source_sha256'][name]:
            raise ValueError('unchanged original325 source guard: '+name)
    kernels = {name:h.binding(TOOLS/name) for name in h.KERNEL_SHA}
    if any(kernels[n]['sha256'] != sha for n, sha in h.KERNEL_SHA.items()):
        raise ValueError('unchanged pure kernel required')
    bundle = dict(schema='stage376_finite_preparation_v1', scope=scope_b,
        frozen_version=scope['frozen_version'], freeze_event=frozen['freeze_event'],
        model=frozen['model'], scaler=frozen['scaler'], T1=frozen['T1'],
        sources=sources, kernel_sources=kernels, parameters=scope['parameters'],
        frozen_inputs={name:asset(file) for name,file in (
            ('clock_contract','clock_contract.json'), ('source_calendar','trading_dates.npy'))},
        runtime=h._runtime(), actual_initializations=0, future_scoring=0,
        actual_compact_restore_ready=False)
    # Verify only small model/scaler/contract bytes; do not load source_calendar.
    for item in (frozen['model'], frozen['scaler'], bundle['frozen_inputs']['clock_contract']):
        h._bound(item)
    out.mkdir(parents=True)
    result = dict(bundle=h.write(out/'source_bundle.json', bundle),
                  actual_initializations=0, future_scoring=0, restore_ready=False)
    h.write(out/'prepare_result.json', result)
    return result


def make_profile(model, scaler, model_binding, scaler_binding, *, frozen_at, candidate, clock_contract):
    if _json(model_binding) != model or _json(scaler_binding) != scaler:
        raise ValueError('actual source artifact contents differ')
    actual = model.get('cutoff')
    if actual != scaler.get('cutoff') or actual not in ('2023-01-01', '2026-10-20'):
        raise ValueError('one declared actual training cutoff required')
    engine_model, engine_scaler = deepcopy(model), deepcopy(scaler)
    if actual != '2023-01-01':
        for view, source in ((engine_model, model_binding), (engine_scaler, scaler_binding)):
            view.update(cutoff='2023-01-01', actual_training_cutoff=actual,
                source_artifact_sha256=source['sha256'], engine_compatibility_mapping=EXPLANATION)
    identity = components().caller.make_policy_identity(engine_model, engine_scaler, frozen_at=frozen_at)
    return dict(schema='stage376_explicit_model_profile_v1', candidate=candidate,
        actual_training_cutoff=actual, T_model=frozen_at, model=model_binding, scaler=scaler_binding,
        actual_model=deepcopy(model), actual_scaler=deepcopy(scaler),
        engine_model=engine_model, engine_scaler=engine_scaler, policy_identity=identity,
        engine_fold_tag='2023-01-01', legacy_engine_policy=identity['policy'],
        compatibility_explanation=EXPLANATION, clock_contract=deepcopy(clock_contract))


def _initialize_profile(profile, output, kernel):
    """Pure-kernel synthetic fixture seam; public actual path is initialize()."""
    h, c = helper(), components()
    out = Path(output)
    if out.exists():
        raise FileExistsError('never overwrite/reset initialized states')
    out.mkdir(parents=True)
    journal = c.journal.ForwardJournal(out/'model_journal', profile['policy_identity'])
    states = {s:c.paper.new_state(scenario=s,
        account_id=profile['candidate'].lower()+'_'+s+'_u20', start_u=5290, base_kernel=kernel)
        for s in ('base', 'stress')}
    for state in states.values():
        state['caller_policy_sha256'] = journal.policy_hash
    state_files = {s:h.write(out/(s+'_state.json'), json.loads(c.paper.export_state(state)))
                   for s,state in states.items()}
    event = journal.append('paper_state_initialized', dict(profile=profile, states=states,
        state_files=state_files, initial_each=1000000., start_u=5290, target_u=TARGET_U,
        active=False, no_funded_proposal=True), key='latest-model/independent-empty-u20')
    envelope = dict(schema='stage376_latest_empty_initialization_v1', profile=profile,
        T_init=event['recorded_at'], event=event, state_files=state_files,
        journal_path=str(journal.path), active=False, no_funded_proposal=True)
    envelope_binding = h.write(out/'initialization_envelope.json', envelope)
    return dict(profile=profile, states=states, journal=journal, kernel=kernel,
        T_init=event['recorded_at'], initialization_event=event,
        initialization_envelope=envelope_binding)


def initialize(prepared_bundle, output):
    """Root once, fixed378 scope; no model inference or funded proposal."""
    h = helper()
    out = Path(output).resolve()
    if out != ACTUAL or out.exists():
        raise ValueError('only fresh fixed378 actual_run1 is allowed')
    bundle = _json(prepared_bundle)
    if bundle['scope'] != dict(path=str(SCOPE), bytes=3560, sha256=SCOPE_SHA):
        raise ValueError('fixed378 preparation required')
    scope = _json(bundle['scope'])
    if h._time(datetime.now(timezone.utc).isoformat()) >= h._time(scope['initialization_deadline']):
        raise ValueError('initialization deadline passed; retain gap')
    for name, item in bundle['sources'].items():
        if item != h.binding(TOOLS/name):
            raise ValueError('prepared source changed: '+name)
    if set(bundle['kernel_sources']) != set(h.KERNEL_SHA):
        raise ValueError('exact pure kernel sources required')
    for name, item in bundle['kernel_sources'].items():
        if item != h.binding(TOOLS/name) or item['sha256'] != h.KERNEL_SHA[name]:
            raise ValueError('unchanged original pure kernel required: '+name)
    asset = _assets()
    if bundle['frozen_inputs'] != {name:asset(file) for name,file in (
            ('clock_contract','clock_contract.json'), ('source_calendar','trading_dates.npy'))}:
        raise ValueError('original frozen calendar/clock binding changed')
    frozen = _json(scope['frozen_version'])
    if any(bundle[k] != frozen[k] for k in ('model', 'scaler', 'T1')):
        raise ValueError('375 source/profile mismatch')
    import io
    import numpy as np
    calendar = np.load(io.BytesIO(h._bound(bundle['frozen_inputs']['source_calendar'])), allow_pickle=False)
    if str(int(calendar[5290])) != '20261020':
        raise ValueError('fixed start_u calendar mismatch')
    profile = make_profile(_json(frozen['model']), _json(frozen['scaler']), frozen['model'], frozen['scaler'],
        frozen_at=frozen['T1'], candidate=CANDIDATE,
        clock_contract=_json(bundle['frozen_inputs']['clock_contract']))
    # Pure131 imports only its unchanged070/042 definitions, never runner calls.
    kernel = h._load(Path(bundle['kernel_sources']['stage131_contract_choice_kernel.py']['path']), 'stage376_pure131')
    context = _initialize_profile(profile, out, kernel)
    event = context['initialization_event']
    status = ('initialized_inactive' if h._time(frozen['T1']) < h._time(event['recorded_at'])
              < h._time(scope['initialization_deadline']) else 'initialization_clock_invalid')
    result = dict(schema='stage376_latest_empty_initialization_result_v1', status=status,
        active=False, T1=frozen['T1'], T_init=context['T_init'], candidate=CANDIDATE,
        initialization_envelope=context['initialization_envelope'], prepared_bundle=prepared_bundle,
        counts=dict(new_state_calls=2, financial_D=0, seal_u=0, model_inference=0, fit=0, cash=0),
        actual_compact_restore_ready=False)
    h.write(out/'result.json', result)
    return result


def validate_context(context):
    c, profile = components(), context['profile']
    expected_profile = make_profile(_json(profile['model']), _json(profile['scaler']),
        profile['model'], profile['scaler'], frozen_at=profile['T_model'],
        candidate=profile['candidate'], clock_contract=profile['clock_contract'])
    if profile != expected_profile:
        raise ValueError('profile differs from original source artifacts')
    expected = c.caller.make_policy_identity(profile['engine_model'], profile['engine_scaler'], frozen_at=profile['T_model'])
    if expected != profile['policy_identity']:
        raise ValueError('profile engine/source identity changed')
    wanted = hashlib.sha256(c.caller._bytes(expected)+b'\n').hexdigest()
    if context['journal'].policy_hash != wanted:
        raise ValueError('journal belongs to another frozen policy')
    if set(context['states']) != {'base', 'stress'}:
        raise ValueError('separate own base/stress states required')
    ids = set()
    for scenario, state in context['states'].items():
        c.paper._validate(state, context['kernel'])
        if state.get('caller_policy_sha256') != wanted:
            raise ValueError('state belongs to another frozen policy')
        if state['scenario'] != scenario or state['ledger']['scenario'] != scenario:
            raise ValueError('scenario crossed')
        ids.add(state['account_id'])
    if len(ids) != 2:
        raise ValueError('scenario account IDs crossed')
    event = context['initialization_event']
    if (event['kind'] != 'paper_state_initialized' or event['policy_sha256'] != wanted
            or event['recorded_at'] != context['T_init']):
        raise ValueError('own actual initialization receipt required')


def load_context(envelope_binding):
    """Restore only small already-created376 states; no new initialization."""
    h, c = helper(), components()
    value = _json(envelope_binding)
    if value['schema'] != 'stage376_latest_empty_initialization_v1':
        raise ValueError('376 own initialization envelope required')
    if not Path(value['journal_path']).is_dir():
        raise ValueError('existing own execution journal required')
    context = dict(profile=value['profile'], T_init=value['T_init'],
        initialization_event=value['event'], initialization_envelope=envelope_binding,
        states={s:_json(item)['state'] for s,item in value['state_files'].items()},
        journal=c.journal.ForwardJournal(value['journal_path'], value['profile']['policy_identity']),
        kernel=h._load(TOOLS/'stage131_contract_choice_kernel.py', 'stage376_restore_pure131'))
    validate_context(context)
    return context


def _series_identity(value):
    if hasattr(value, 'to_dict'):
        return value.to_dict()
    return {key:getattr(value, key) for key in ('days', 'values', 'valid', 'N', 'low20', 'run')}


def composed_identity(composed):
    """Fingerprint known339 in-memory fields; not a persistence/restoration format."""
    snapshot = composed['snapshot']
    encoded = {key:value for key,value in snapshot.items() if key not in ('series_by_epoch', 'market')}
    encoded['series_by_epoch'] = {e:_series_identity(v) for e,v in snapshot['series_by_epoch'].items()}
    encoded['market'] = dict(dates=snapshot['market'].dates,
        series={e:_series_identity(v) for e,v in snapshot['market'].series.items()})
    return components().caller._hash(dict(snapshot=encoded,
        **{key:value for key,value in composed.items() if key != 'snapshot'}))


def process_pair(composed, acceptance_binding, contexts):
    """One accepted in-memory composed, own325 journals/states; no collection."""
    c, h = components(), helper()
    acceptance = _json(acceptance_binding)
    same = composed_identity(composed)
    if (acceptance.get('schema') != ACCEPTANCE_SCHEMA or acceptance.get('accepted_by') != 'root'
            or acceptance.get('status') != 'accepted' or acceptance.get('target_u') != TARGET_U
            or any(acceptance.get(k) is not True for k in ('completed361', 'passed362', 'accepted363'))
            or acceptance.get('composed_identity') != same
            or acceptance.get('clock_domains_sha256') != c.caller._hash(composed['clock_domains'])):
        raise ValueError('root accepted same-composed binding required')
    if set(acceptance.get('evidence', {})) != {'terminal361', 'review362', 'decision363'}:
        raise ValueError('361 terminal/362 review/363 acceptance bindings required')
    for item in acceptance['evidence'].values():
        _json(item)
    domains, snapshot = composed['clock_domains'], composed['snapshot']
    if (snapshot['u_date'] != TARGET_U or snapshot['u_index'] != 5290
            or domains.get('before_score') is not True or domains.get('score_or_winner_used') is not False
            or domains['u_date'] != TARGET_U or domains['D_date'] != '2026-10-21'):
        raise ValueError('finite u20 complete pre-score clock domains required')
    clock = snapshot['clock']
    for group, key in (('input_completion', 'source_completed_at'), ('execution_deadline', 'D_open_at')):
        if domains[group][key] != clock[key] or (domains[group]['unknown_epochs'] and clock[key] is not None):
            raise ValueError('unknown/domain aggregate must be retained')
    accepted = deepcopy(snapshot)
    accepted.update(development_only=False, accepted_future_lineage=dict(
        original_development_only=snapshot.get('development_only'), acceptance=acceptance_binding,
        composed_identity=same, clock_domains=deepcopy(domains)))
    results = {}
    for name, context in contexts.items():
        validate_context(context)
        profile, journal = context['profile'], context['journal']
        if domains['policy'] != profile['clock_contract']:
            raise ValueError('complete frozen double-domain policy required')
        receipt = journal.append('accepted_composed_input', dict(acceptance=acceptance_binding,
            composed_identity=same, clock_domains=domains, profile_candidate=profile['candidate']),
            key='accepted-composed/'+str(uuid4()))
        gate = c.journal.evaluate_clock(frozen_at=profile['T_model'],
            source_completed_at=clock['source_completed_at'], received_at=receipt['recorded_at'],
            decision_sealed_at=None, D_open_at=clock['D_open_at'])
        reason = None if gate['status'] == 'decision_not_sealed' else gate['status']
        if clock['source_completed_at'] is not None and h._time(context['T_init']) >= h._time(clock['source_completed_at']):
            reason = 'initialization_not_before_source_completion'
        required = set()
        for state in context['states'].values():
            for row in list(state['ledger']['positions'].values())+state['pending']:
                epoch = row.get('epoch', row.get('reference_epoch'))
                if not epoch:
                    reason = 'own_state_execution_dependency_unknown'
                else:
                    required.add(epoch)
        if not required.issubset(set(domains['input_completion']['epochs']) & set(domains['execution_deadline']['epochs'])):
            reason = 'own_state_execution_dependency_clock_unknown'
        if reason:
            gap = journal.append('state_gap', dict(reason=reason, active=False,
                own_T_init=context['T_init'], clock=gate, accepted_composed_identity=same,
                retained_states_sha256=c.caller._hash(context['states'])),
                key='accepted-input-gap/'+receipt['entry_hash'])
            result = dict(status='state_gap', active=False, gap_reason=reason,
                states=deepcopy(context['states']), clock=gate, classification_receipt=gap)
        else:
            result = c.caller.process_snapshot(accepted, model=profile['engine_model'],
                scaler=profile['engine_scaler'], journal=journal, policy_identity=profile['policy_identity'],
                mode='future', states=context['states'], base_kernel=context['kernel'])
        results[name] = dict(status=result['status'], active=result['active'], states=result['states'],
            profile=profile, engine_fold_tag='2023-01-01', actual_training_cutoff=profile['actual_training_cutoff'],
            accepted_composed_identity=same, acceptance=acceptance_binding, result=result)
        if composed_identity(composed) != same:
            raise ValueError('same composed object mutated during profile processing')
    return dict(schema='stage376_shared_input_profile_results_v1', profiles=results,
        accepted_composed_identity=same, acceptance=acceptance_binding,
        engine_cutoff_fields_are_legacy_tags=True, no_new_market_requests=True,
        actual_compact_restore_ready=False)
