"""Two finite read-only bridges for the unchanged376 shared-input interface.

No collection, raw archive replay, indicator append, inference or state update.
Actual357 restoration remains conditional on361 artifacts and362/363 acceptance.
"""
from __future__ import annotations
from copy import deepcopy
from functools import lru_cache
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import numpy as np

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
SCOPE = LINE/'outputs/stage381_resume_shared_input_wiring_scope/scope.json'
SCOPE_SHA = '793e44a108da1ba442aa4fa14892604aec8b03ed65fe3f0366fb3dfe10d1b587'
SOURCE_SHA = {
    'stage368_initialize_paper_reference.py': 'c5f3dbadb18237eb6d72b47020262b5e298e75a5c18b5e3114baf84674f555f2',
    'stage376_shared_frozen_profiles.py': '0a9edeb45907f9542299b4afee9a718c94b373c16e41349ce0c43d588a0ca910',
    'stage357_daily_collect_compose.py': '65d18a5c39e8df5442eafc2f5e2fd782f9bb492743339dc6cb5b013c91877e87',
    'stage339_incremental_snapshot.py': '25ac52ec822abb70249830bf0cbf2e040803f2d3972c9beabfdc3c4a13cfb89b',
}


@lru_cache(maxsize=1)
def profiles():
    for name, wanted in SOURCE_SHA.items():
        if hashlib.sha256((TOOLS/name).read_bytes()).hexdigest() != wanted:
            raise ValueError('unchanged original source required: '+name)
    spec = importlib.util.spec_from_file_location('stage382_original376', TOOLS/'stage376_shared_frozen_profiles.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json(binding):
    return profiles()._json(binding)


def _journal_object(path, identity, receipt):
    """Open only an existing321 stream; verify its index and one bound object."""
    p = profiles()
    path = Path(path)
    if (path.is_symlink() or (path/'objects').is_symlink()
            or any(not f.is_file() or f.is_symlink() for f in (path/'policy_identity.json',path/'journal.jsonl'))
            or not (path/'objects').is_dir()):
        raise ValueError('existing journal policy/index/objects required; never create or repair')
    journal = p.components().journal.ForwardJournal(path, identity)
    with journal.index.open(encoding='utf-8') as stream:
        entries = journal._read_index(stream)
    if receipt not in entries:
        raise ValueError('receipt absent from original321 journal')
    raw = (journal.objects/(receipt['payload_sha256']+'.json')).read_bytes()
    codec = p.components().journal
    if codec._digest(raw) != receipt['payload_sha256']:
        raise ValueError('original321 payload SHA mismatch')
    value = json.loads(raw)
    if codec._canonical(value) != raw:
        raise ValueError('original321 canonical payload required')
    return journal, value


def load_baseline_context(manifest_binding):
    """370 original accounts/journal/T0/T_init, in the unchanged376 shape."""
    p, h = profiles(), profiles().helper()
    manifest = _json(manifest_binding)
    if manifest['schema'] != 'stage368_initialization_manifest_v1' or manifest['status'] != 'initialized_inactive' or manifest['active'] is not False:
        raise ValueError('original370 inactive initialization manifest required')
    envelope_b = manifest['initialization_envelope']
    envelope = _json(envelope_b)
    if envelope['schema'] != 'stage368_paper_initialization_envelope_v1':
        raise ValueError('original368 envelope required')
    for key in ('T0','T_init','state_files','source_bundle','reference','kernel_sources','status','active'):
        if envelope[key] != manifest[key]:
            raise ValueError('370 manifest/envelope mismatch: '+key)
    bundle = _json(envelope['source_bundle'])
    if bundle['schema'] != 'stage368_initialization_source_bundle_v1' or bundle['reference'] != envelope['reference']:
        raise ValueError('original368 source bundle/reference required')
    inputs = bundle['frozen_inputs']
    model, scaler, contract = (_json(inputs[k]) for k in ('model','scaler','clock_contract'))
    profile = p.make_profile(model, scaler, inputs['model'], inputs['scaler'],
        frozen_at=envelope['T0'], candidate=p.BASELINE, clock_contract=contract)
    identity = profile['policy_identity']
    if (model['cutoff'] != '2023-01-01' or identity != envelope['policy_identity']
            or identity != _json(manifest['policy_identity'])
            or identity != _json(envelope['reference']['policy_identity'])):
        raise ValueError('original baseline policy/model/scaler/T0 changed')
    for name, sha in identity['source_sha256'].items():
        item = bundle['frozen_sources'][name]
        h._bound(item)
        if item['sha256'] != sha:
            raise ValueError('original baseline source changed')
    freeze = _json(envelope['reference']['freeze_event'])
    if (freeze['schema'] != 'stage359_research_reference_freeze_v1'
            or freeze['receipt']['kind'] != 'research_reference_freeze'
            or freeze['receipt']['recorded_at'] != envelope['T0'] or freeze['clock_contract'] != inputs['clock_contract']):
        raise ValueError('original T0 freeze binding changed')
    if set(envelope['kernel_sources']) != set(h.KERNEL_SHA):
        raise ValueError('original pure kernel set required')
    for name,item in envelope['kernel_sources'].items():
        h._bound(item)
        if item['sha256'] != h.KERNEL_SHA[name]:
            raise ValueError('original pure kernel changed')
    kernel = h._load(Path(envelope['kernel_sources']['stage131_contract_choice_kernel.py']['path']), 'stage382_original131')
    states = {s:_json(item)['state'] for s,item in envelope['state_files'].items()}
    journal, payload = _journal_object(Path(envelope_b['path']).parent/'model_journal', identity, envelope['event'])
    for key,wanted in (('states',states),('state_files',envelope['state_files']),('frozen_inputs',inputs),
                       ('policy_identity',identity),('T0',envelope['T0'])):
        if payload[key] != wanted:
            raise ValueError('original initialization object mismatch: '+key)
    context = dict(profile=profile, states=states, journal=journal, kernel=kernel,
        T_init=envelope['T_init'], initialization_event=envelope['event'], initialization_envelope=envelope_b)
    p.validate_context(context)
    return context


def restore_composed(manifest_binding):
    """Restore357 persisted final states once, without append or model scoring.

    The returned object has its own explicit recovery identity. It is not a
    byte reconstruction of357's unpersisted in-memory adapter diagnostics.
    """
    p, h, c = profiles(), profiles().helper(), profiles().components().caller
    core = c._components().core
    manifest = _json(manifest_binding)
    if (manifest['schema'] != 'stage357_daily_collect_compose_manifest_v1'
            or manifest['status'] != 'completed_observation' or manifest['mode'] != 'observe_only'
            or manifest['target_u'] != p.TARGET_U or manifest['active'] is not False
            or manifest['new_fit'] != 0 or manifest['new_cash'] != 0):
        raise ValueError('completed finite357 observe-only manifest required')
    bundle = _json(manifest['source_bundle'])
    sources = {Path(b['path']).name:b for b in bundle['sources']}
    expected = dict(SOURCE_SHA, **{n:h.binding(TOOLS/n)['sha256'] for n in h.CALLER_FILES})
    for name in ('stage376_shared_frozen_profiles.py','stage368_initialize_paper_reference.py'):
        expected.pop(name)
    for name,sha in expected.items():
        h._bound(sources[name])
        if sources[name]['sha256'] != sha:
            raise ValueError('original357 persisted schema source changed')
    inp, artifacts = manifest['inputs'], manifest['artifacts']
    saved = _json(artifacts['result'])['result']
    receipt = saved['input_receipt']
    if receipt['kind'] != 'input_snapshot' or saved['policy_identity']['frozen_at'] != manifest['T0']:
        raise ValueError('original357 input receipt/policy required')
    _, provenance = _journal_object(Path(manifest_binding['path']).parent/'model_journal',saved['policy_identity'],receipt)
    original = dict(inputs=inp,capture=artifacts['capture'])
    source_receipt = provenance['source_receipt']
    if (provenance['development_only'] is not True or provenance['u_date'] != p.TARGET_U
            or provenance['version'] != original or source_receipt['source_receipt'] != original
            or source_receipt['schema'] != 'stage339_incremental_source_receipt_v1'
            or source_receipt['status'] != 'completed' or source_receipt['u_date'] != p.TARGET_U
            or source_receipt['u_index'] != provenance['u_index']):
        raise ValueError('original321 input provenance/batch mismatch')
    a = np.load(io.BytesIO(h._bound(inp['source_calendar'])),allow_pickle=False)
    dates = ([str(int(v))[:4]+'-'+str(int(v))[4:6]+'-'+str(int(v))[6:8] for v in a]
             if a.dtype.kind in 'iu' else a.astype('datetime64[D]').astype(str).tolist())
    products = sorted(r['product_id'] for r in csv.DictReader(io.StringIO(h._bound(inp['roster']).decode('utf-8-sig'))))
    if len(products) != 98 or len(set(products)) != 98 or len({v.removesuffix('_F') for v in products}) != 95:
        raise ValueError('complete original98-product/95-family domain required')
    u, dc = provenance['u_index'], deepcopy(provenance['D_context'])
    core._calendar(dates,u,dc)
    calendar = _json(inp['calendar338'])
    if dates[u] != p.TARGET_U or calendar['days'].get(p.TARGET_U) is not True or (dc['confirmed'] and calendar['days'].get(dc['D_date']) is not True):
        raise ValueError('original source calendar confirmation differs')
    economics = _json(inp['economics331'])
    for epoch,value in _json(inp['economics344']).items():
        if epoch in economics and economics[epoch] != value:
            raise ValueError('original331/344 economics conflict; no overwrite')
        economics[epoch] = value
    inventory, warmup = _json(artifacts['epoch_inventory']), _json(artifacts['warmup_state'])
    adapter = h._load(TOOLS/'stage339_incremental_snapshot.py','stage382_original339')
    epochs, states = {}, {}
    for row in inventory:
        epoch, last = row['epoch'], row['last_index']
        if epoch in epochs or adapter._epoch_product(epoch) != row['product_id'] or row['product_id'] not in products:
            raise ValueError('complete inventory identity mismatch/duplicate')
        if last is not None and (isinstance(last,bool) or not isinstance(last,int) or not 0 <= last <= u):
            raise ValueError('inventory index exceeds final checkpoint')
        if row['last_date'] != (dates[last] if last is not None else None) or row['has_current_bar'] is not (last == u):
            raise ValueError('final inventory date/current mismatch')
        epochs[epoch] = row
    for epoch,value in warmup.items():
        state = core.WilderState.from_dict(value)
        if epoch not in epochs or state.last_seen != epochs[epoch]['last_index']:
            raise ValueError('final state/inventory mismatch')
        days = [r['day'] for r in state.history]
        if days != sorted(set(days)) or (days and days[-1] != state.last_seen) or (state.last_seen is not None and not days):
            raise ValueError('final bounded state history mismatch')
        states[epoch] = state
    if any(row['has_current_bar'] and epoch not in states for epoch,row in epochs.items()):
        raise ValueError('current inventory epoch lacks final state')
    arrays = {e:states[e].to_series() if e in states else core.WilderState().to_series() for e in epochs}
    forward = {e:states[e] if e in states and states[e].last_seen == u else arrays[e] for e in epochs}
    canonical = _json(artifacts['canonical_overlay'])
    current = {e for e,s in states.items() if s.last_seen == u}
    if ({r['contract_epoch_id'] for r in canonical} != current or len(canonical) != len(current)
            or any(r['trade_date'] != p.TARGET_U for r in canonical)
            or manifest['canonical_rows'] != len(canonical)
            or source_receipt['counts']['appended_rows'] != len(canonical)):
        raise ValueError('canonical overlay/final current inventory mismatch')
    if _json(artifacts['current_economics']) != {r['contract_epoch_id']:economics.get(r['contract_epoch_id'],{}) for r in canonical}:
        raise ValueError('current economics subset differs from full original merge')
    domains, contract = _json(artifacts['clock_domains']), _json(inp['clock_contract'])
    clock = deepcopy(provenance['clock'])
    if (domains['schema'] != 'stage357_dual_clock_domains_v1' or domains['policy'] != contract
            or domains['u_date'] != p.TARGET_U or domains['D_date'] != '2026-10-21'
            or domains['before_score'] is not True or domains['score_or_winner_used'] is not False):
        raise ValueError('complete original pre-score double clock domain required')
    for group,key in (('input_completion','source_completed_at'),('execution_deadline','D_open_at')):
        domain = domains[group]
        if domain[key] != clock[key] or (domain['unknown_epochs'] and domain[key] is not None):
            raise ValueError('original domain aggregate/unknown clock mismatch')
    continuation = _json(artifacts['continuation_evidence'])
    if any(r['epoch'] not in warmup or r['final_state'] != warmup[r['epoch']] for r in continuation):
        raise ValueError('persisted continuation/final state mismatch')
    snapshot = dict(schema=adapter.SCHEMA, development_only=True,frozen_at=None,
        u_date=p.TARGET_U,u_index=u,dates=dates,products=products,economics=economics,
        series_by_epoch=forward,warmup_state=deepcopy(warmup),market=adapter.SnapshotMarket(arrays,dates),
        D_context=dc,clock=clock,source=provenance['source'],version=provenance['version'],
        source_receipt=source_receipt,received_at=provenance['claimed_adapter_received_at'],completed_at=None,
        incremental_audit=deepcopy(source_receipt['counts']),_inventory=inventory,_continuation_evidence=continuation)
    observations = core.build_u_observations(forward,u,dates,economics,products,D_context=dc)
    if c._hash(observations) != c._hash(saved['observations']):
        raise ValueError('restored observations/raw26 differ from persisted357 evidence')
    return dict(snapshot=snapshot,canonical_rows=canonical,normalization_audit=_json(artifacts['normalization_audit']),
        prescore_observations=observations,clock_domains=domains,
        normalization_receipt=deepcopy(source_receipt['normalization_receipt']),
        restoration=dict(schema='stage382_persisted357_final_state_restore_v1',manifest=manifest_binding,
            original_input_receipt=receipt,observations_sha256=c._hash(observations),
            original_confirmed_calendar=calendar,
            unpersisted_adapter_diagnostics_omitted=['_row_dispositions','unsupported_catalog','product_states'],
            actual_acceptance_required='361 terminal +362 review +363 acceptance;376 process_pair remains unchanged'))


def prepare(output):
    """Bind the finite381 scope and small sources; no actual context loading."""
    p, h = profiles(), profiles().helper()
    scope = dict(path=str(SCOPE),bytes=4174,sha256=SCOPE_SHA)
    _json(scope)
    out = Path(output)
    if out.exists():
        raise FileExistsError('fresh382 preparation required')
    bundle = dict(schema='stage382_readonly_shared_input_bridges_v1',scope=scope,
        sources={n:h.binding(TOOLS/n) for n in (*SOURCE_SHA,*h.CALLER_FILES,*h.KERNEL_SHA,
            'stage382_shared_input_restore.py','test_stage382_shared_input_restore.py')},
        actual_context_materializations=0,actual_input_restores=0,new_state=0,journal_append=0,model_inference=0,
        actual361_restore_qualified=False)
    out.mkdir(parents=True)
    return h.write(out/'source_bundle.json',bundle)
