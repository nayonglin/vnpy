"""Preserve a reviewed local reference, then timestamp it with real Stage321.

No registration to Git, account state, scoring, API or production activation.
The local hash chain is reproducibility evidence, not external attestation.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[3]
POLICY = 'PURE52_MAIN2023_VOLUNTARY_RESELECT_NARROW'


def binding(path):
    p = Path(path).resolve()
    raw = p.read_bytes()
    return dict(path=str(p), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def write(path, value):
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                      allow_nan=False)+'\n').encode()
    with Path(path).open('xb') as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    Path(path).chmod(0o444)
    return dict(path=str(Path(path).resolve()), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def load_source(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def freeze(inventory_path, output):
    out = Path(output).resolve()
    if out.exists():
        raise FileExistsError('new local reference directory required; never replace a freeze')
    inventory_raw = Path(inventory_path).read_bytes()
    inv = json.loads(inventory_raw)
    if inv.get('closure_complete') is not True:
        raise ValueError('reviewed complete dependency inventory required')
    # Preflight each entity once. Keep the same bytes for the copy; a mutable
    # checkout cannot change the source between verification and preservation.
    captured, names = [], set()
    for asset in inv['assets']:
        name = Path(asset['logical_name'])
        p = Path(asset['path'])
        if (not asset.get('reproducibility_required') or name.is_absolute()
                or '..' in name.parts or name.as_posix() in names
                or p.is_symlink() or p.resolve() != (ROOT/name).resolve()
                or not p.is_file() or not p.resolve().is_relative_to(ROOT)
                or any(v in name.parts for v in ('.vntrader', '.git', '.aws'))
                or p.suffix.lower() in ('.env', '.sqlite', '.db', '.npz', '.h5')):
            raise ValueError('required regular local payload with unique repo-relative name expected')
        raw = p.read_bytes()
        if len(raw) != asset['bytes'] or hashlib.sha256(raw).hexdigest() != asset['sha256']:
            raise ValueError('dependency bytes differ from reviewed inventory: '+str(name))
        names.add(name.as_posix())
        captured.append((asset, name, raw))
    def named(filename):
        matches = [(a, n, r) for a, n, r in captured if n.name == filename]
        if len(matches) != 1:
            raise ValueError('unique dependency required: '+filename)
        return matches[0]
    clock_a, clock_name, clock_raw = named('clock_contract.json')
    clock = json.loads(clock_raw)
    if (clock.get('schema') != 'stage356_causal_clock_domain_policy_v1'
            or clock.get('version') != 'pure52_input_vs_execution_v1'
            or clock.get('frozen_at') is not None):
        raise ValueError('reviewed pre-T0 clock contract required')
    for file in ('stage320_causal_forward_core.py', 'stage321_forward_journal.py',
                 'stage322_continuous_paper_state.py', 'stage325_forward_caller.py'):
        named(file)
    model_matches = [(a, n, r) for a, n, r in captured if a['role'] == 'model_artifact']
    if len(model_matches) != 1:
        raise ValueError('single portable model required')
    _, model_name, model_raw = model_matches[0]
    scaler_matches = [(a, n, r) for a, n, r in captured if n.name == 'scaler.json']
    if len(scaler_matches) != 1:
        raise ValueError('single scaler required')
    model, scaler = json.loads(model_raw), json.loads(scaler_matches[0][2])
    out.mkdir(parents=True)
    artifacts = []
    for asset, name, raw in captured:
        dest = out/'payload'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('xb') as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        dest.chmod(0o444)
        artifacts.append(dict(asset, source_path=asset['path'], path=str(dest),
                              payload_relative_path=str(Path('payload')/name), copied=True))
    inventory_copy = out/'inventory.json'
    with inventory_copy.open('xb') as f:
        f.write(inventory_raw)
    inventory_copy.chmod(0o444)
    freezer = out/'freezer_source.py'
    with freezer.open('xb') as f:
        f.write(Path(__file__).read_bytes())
    freezer.chmod(0o444)
    manifest = dict(schema='stage359_local_research_closure_v1',
        line_id='futures_full_market_long_signal_ai', policy=POLICY, artifacts=artifacts,
        inventory=binding(inventory_copy), freezer_source=binding(freezer),
        external_entity_references_not_payload=inv.get('external_entity_references_not_payload', []),
        runtime=inv['runtime'], source_provenance=inv.get('source_provenance', {}),
        scope='local unfunded reference; incremental inference dependency closure only',
        private_configuration_in_payload=False, cross_machine_runtime_qualified=False,
        prepared_at=datetime.now(timezone.utc).isoformat(), active=False, states=None,
        limitation='local filesystem owner can replace files; no external publication attestation')
    manifest_binding = write(out/'closure_manifest.json', manifest)
    clock_binding = dict(path=str(out/'payload'/clock_name), bytes=clock_a['bytes'], sha256=clock_a['sha256'])
    journal_name = named('stage321_forward_journal.py')[1]
    caller_name = named('stage325_forward_caller.py')[1]
    journal_module = load_source(out/'payload'/journal_name, 'stage359_real321')
    caller = load_source(out/'payload'/caller_name, 'stage359_frozen325')
    untimed_identity = caller.make_policy_identity(model, scaler, frozen_at=None)
    journal = journal_module.ForwardJournal(out/'freeze_journal', dict(
        schema='stage359_reference_freeze_identity_v1', reference=untimed_identity,
        closure_manifest=manifest_binding, clock_contract=clock_binding))
    receipt = journal.append('research_reference_freeze', dict(
        closure_manifest=manifest_binding, clock_contract=clock_binding,
        reference=untimed_identity, active=False, states=None), key='reference_freeze_once')
    envelope = dict(schema='stage359_research_reference_freeze_v1', receipt=receipt,
        closure_manifest=manifest_binding, clock_contract=clock_binding,
        journal_path=str(journal.path), boundary='local research only; no first-publication/account attestation')
    event_binding = write(out/'freeze_event.json', envelope)
    identity = caller.make_policy_identity(model, scaler, frozen_at=receipt['recorded_at'])
    identity_binding = write(out/'policy_identity.json', identity)
    result = dict(schema='stage359_local_reference_result_v1', status='frozen_unfunded_reference',
        T0=receipt['recorded_at'], closure_manifest=manifest_binding, freeze_event=event_binding,
        clock_contract=clock_binding, policy_identity=identity_binding,
        asset_count=len(artifacts), asset_bytes=sum(a['bytes'] for a in artifacts),
        active=False, states=None, new_fit=0, new_cash=0, model_inference=0,
        market_API=0, Git_operations=0, ready_for_forward_clock_check=True,
        alpha_qualification=False, account_qualification=False)
    write(out/'result.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(freeze(args.inventory, args.output), ensure_ascii=False))
