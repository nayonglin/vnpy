import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def load(name, folder='tools'):
    spec = importlib.util.spec_from_file_location('identity048_' + name, ROOT / folder / (name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def identity(path):
    path = Path(path); raw = path.read_bytes()
    return {'path': str(path.resolve()), 'size': len(raw), 'mtime_ns': path.stat().st_mtime_ns,
            'sha256': hashlib.sha256(raw).hexdigest()}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


@pytest.fixture
def complete(tmp_path, monkeypatch):
    m = load('stage044_holding_training')
    prior = load('test_stage044_holding_training', 'tests')
    root = tmp_path / 'line'; panel = root / 'artifacts/stage040_holding_panel'
    current = SimpleNamespace(OUTPUT=root / 'artifacts/stage042_holding_labels',
        LEGACY=root / 'artifacts/stage041b_holding_labels', SNAPSHOT=root / 'inherited',
        FREEZE=root / 'stages/stage042_input_freeze.json')
    snapshot = root / 'artifacts/stage043_label_collection/complete/summary.json'
    jobs = [{'observation_id': f'obs-{i:04}', 'root_id': f'root-{i % 155:03}',
             'date': '2020-01-02', 'end_date': '2020-01-03', 'status': 'mature',
             'product_vt_symbol': 'rb.SHFE', 'vt_symbol': 'rb2005.SHFE'} for i in range(1002)]
    plan = {'jobs': jobs, 'roots': [{'status': 'mature'} for _ in range(274)] +
            [{'status': 'right_censored_open'} for _ in range(2)]}
    inherited = {job['observation_id'] for job in jobs[:14]}
    labels = {job['observation_id']: {**job, 'status': 'passed',
        'marginal': {target: 0. for target in prior.SPEC['targets']}} for job in jobs}
    features = pd.DataFrame([{key: job[key] for key in ('observation_id', 'date', 'product_vt_symbol', 'vt_symbol')}
        | {key: 0. for key in prior.SPEC['features']} for job in jobs])
    panel.mkdir(parents=True); features.to_csv(panel / 'features.csv', index=False)
    months = [{'cutoff': value.strftime('%Y-%m-01')} for value in pd.period_range('2020-01', '2026-08', freq='M')]
    for name, value in [('summary', {}), ('jobs', plan), ('model_spec', prior.SPEC), ('monthly_inventory', months)]:
        write_json(panel / (name + '.json'), value)
    paths = [current.FREEZE, current.OUTPUT / 'input_manifest.json', current.SNAPSHOT / 'summary.json',
        current.LEGACY / 'input_manifest.json', root / 'stages/stage041b_input_freeze.json']
    for path in paths:
        write_json(path, {'file_contract_sha256': 'a' * 64})
    paths += list(panel.iterdir())
    for job in jobs:
        owner = current.LEGACY if job['observation_id'] in inherited else current.OUTPUT
        for name in ('label', 'receipt', 'archive_receipt', 'exit_audit'):
            path = owner / 'jobs' / job['observation_id'] / (name + '.json')
            write_json(path, labels[job['observation_id']] if name == 'label' else {})
            paths.append(path)
    data, ready = load('stage043_label_collection').assemble(jobs, features, labels, inherited)
    assert ready
    snapshot.parent.mkdir(parents=True)
    data.to_csv(snapshot.parent / 'observations.csv', index=False, float_format='%.17g')
    (snapshot.parent / 'counterfactual_metrics.csv').write_text('unused_in_row_loader\n')
    summary = {**prior.complete_summary(), 'file_contract_sha256': 'a' * 64,
        'source_identities': {str(path): identity(path) for path in paths},
        'outputs': {name: identity(snapshot.parent / name) for name in ('observations.csv', 'counterfactual_metrics.csv')}}
    write_json(snapshot, summary)
    runner = SimpleNamespace(_file_identity=identity, validate_frozen_input_contract=lambda *args: None,
                             validate_current_input_manifest=lambda *args: None)
    adapted = SimpleNamespace(PANEL=panel, configured=lambda: (None, runner), verify_panel=lambda *args: None,
                              read_plan=lambda: plan)
    current.adapted = lambda: adapted; current.inherited_ids = lambda: inherited
    monkeypatch.setattr(m, 'ROOT', root)
    monkeypatch.setattr(m, 'load', lambda name: current if name == 'stage042_holding_labels' else load(name))
    return m, snapshot, identity(snapshot)['sha256'], runner, adapted


def test_complete_loader_preserves_standard_mtime_identity(complete):
    m, snapshot, digest, _, _ = complete
    data, spec, months, dataset, paths, runner, manifest, bound = m.load_verified_snapshot(snapshot, digest)
    assert len(data) == 1002 and len(months) == 80
    assert bound[str(snapshot)] == identity(snapshot)
    assert dataset['snapshot_sha256'] == digest and snapshot in paths


@pytest.mark.parametrize('when', ['before_identity', 'after_identity'])
def test_snapshot_replaced_during_loading_is_rejected(complete, when):
    m, snapshot, digest, runner, adapted = complete
    if when == 'before_identity':
        original = runner._file_identity
        def replaced(path):
            if Path(path) == snapshot:
                snapshot.write_text(snapshot.read_text() + ' ')
            return original(path)
        runner._file_identity = replaced
    else:
        original = adapted.read_plan
        def replaced():
            snapshot.write_text(snapshot.read_text() + ' ')
            return original()
        adapted.read_plan = replaced
    with pytest.raises(RuntimeError, match='snapshot_changed|source_drift'):
        m.load_verified_snapshot(snapshot, digest)
