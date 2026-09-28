import importlib.util
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'tools/stage044_holding_training.py'
SPEC = json.loads((ROOT / 'artifacts/stage040_holding_panel/model_spec.json').read_text())
SNAPSHOT = ROOT / 'artifacts/stage043_label_collection/20260906_120837_593205/summary.json'
SNAPSHOT_SHA = '45bc2fe636c2da5f7bd3d223767e20ba77652cb1d700fed52bf2fc138af62ba4'


def module():
    assert PATH.exists(), 'holding training campaign missing'
    spec = importlib.util.spec_from_file_location('holding_training_test', PATH)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def complete_summary():
    return {'stage': 'stage043_label_collection', 'status': 'passed', 'training_ready': True,
        'verified': 1002, 'planned': 1002, 'pending': 0, 'inherited_verified': 14, 'canonical_verified': 988,
        'fully_verified_roots': 155, 'roots_with_any_verified_observation': 155, 'total_observed_mature_roots': 155,
        'original_root_inventory': 276, 'unobserved_censored_roots_preserved_in_plan': 2,
        'unresolved_current_job_ids': []}


@pytest.mark.parametrize('patch', [
    {'training_ready': False}, {'verified': 1001}, {'pending': 1}, {'canonical_verified': 987},
    {'inherited_verified': 15}, {'fully_verified_roots': 154}, {'original_root_inventory': 274},
    {'unobserved_censored_roots_preserved_in_plan': 0}, {'unresolved_current_job_ids': ['x']},
    {'status': 'failed'}, {'stage': 'stage041c_label_collection'},
])
def test_incomplete_or_wrong_snapshot_cannot_enter_training(patch):
    m = module(); valid = complete_summary(); m.require_complete_summary(valid)
    with pytest.raises(RuntimeError, match='incomplete'):
        m.require_complete_summary({**valid, **patch})


def test_real_partial_snapshot_rejected_before_lock_fit_or_output(tmp_path, monkeypatch):
    m = module(); monkeypatch.setattr(m, 'OUTPUT', tmp_path / 'must-not-exist')
    with pytest.raises(RuntimeError, match='incomplete'):
        m.run_campaign(SNAPSHOT, SNAPSHOT_SHA)
    assert not m.OUTPUT.exists()


def test_changed_snapshot_hash_rejected_before_output(tmp_path, monkeypatch):
    m = module(); monkeypatch.setattr(m, 'OUTPUT', tmp_path / 'must-not-exist')
    with pytest.raises(RuntimeError, match='snapshot_changed'):
        m.run_campaign(SNAPSHOT, '0' * 64)
    assert not m.OUTPUT.exists()


def synthetic():
    data = pd.DataFrame([{'observation_id': f'synthetic-{i}', 'root_id': f'root-{i}',
        'date': '2020-01-02' if i < 70 else '2020-03-02',
        'label_end_date': '2020-01-03' if i < 70 else '2020-04-03', 'label_status': 'verified',
        'product_vt_symbol': 'rb.SHFE', 'vt_symbol': 'rb2005.SHFE',
        'return_marginal': i / 100 - 0.3, 'drawdown_marginal': 0.1 - i / 500}
        for i in range(71)])
    for i, feature in enumerate(SPEC['features']):
        data[feature] = np.sin(np.arange(71) + i)
    months = [{'cutoff': '2020-01-01', 'mature_roots': 0, 'observation_count': 0,
               'minimum_roots_met': False, 'weights': []}]
    for cutoff in ('2020-02-01', '2020-03-01'):
        months.append({'cutoff': cutoff, 'mature_roots': 70, 'observation_count': 70,
            'minimum_roots_met': True, 'weights': [[f'synthetic-{i}', 1.0] for i in range(70)]})
    return data, months


def test_synthetic_monthly_campaign_uses_native_models_and_all_observations(tmp_path):
    m = module(); data, months = synthetic()
    index, predictions = m.fit_schedule(data, SPEC, months, tmp_path)
    assert list(index) == ['2020-01-01', '2020-02-01', '2020-03-01']
    assert index['2020-01-01']['status'] == 'untrained' and index['2020-01-01']['fit_count'] == 0
    assert index['2020-02-01']['root_count'] == 70 and index['2020-02-01']['fit_count'] == 2
    assert len(predictions) == 71 and predictions.observation_id.nunique() == 71
    assert predictions.iloc[:70].status.eq('untrained').all()
    assert predictions.iloc[70]['status'] == 'predicted'
    assert not list((tmp_path / 'models/2020-01-01').glob('*.ubj'))
    assert len(list((tmp_path / 'models').glob('*/*.ubj'))) == 4


@pytest.mark.parametrize('patch', [{'mature_roots': 71}, {'observation_count': 71},
    {'minimum_roots_met': False}, {'weights': [['synthetic-0', 70.0]]}, {'cutoff': '2020-02-02'}])
def test_frozen_month_plan_mismatch_rejected_before_any_fit_or_model_files(tmp_path, patch):
    m = module(); data, months = synthetic(); months[1].update(patch)
    with pytest.raises((RuntimeError, ValueError)):
        m.fit_schedule(data, SPEC, months, tmp_path)
    assert not list(tmp_path.iterdir())


def test_snapshot_rows_must_match_features_targets_and_source_owner():
    m = module(); data, _ = synthetic(); data = data.iloc[:2].copy()
    features = data[['observation_id', 'date', 'product_vt_symbol', 'vt_symbol', *SPEC['features']]].copy()
    jobs = [{'observation_id': row.observation_id, 'root_id': row.root_id, 'date': row.date,
        'end_date': row.label_end_date} for row in data.itertuples()]
    labels = {job['observation_id']: {**job, 'status': 'passed',
        'marginal': {target: float(data.iloc[i][target]) for target in SPEC['targets']}} for i, job in enumerate(jobs)}
    expected = features.copy()
    expected['root_id'] = data.root_id.to_numpy(); expected['label_end_date'] = data.label_end_date.to_numpy()
    expected['label_status'] = 'verified'
    for target in SPEC['targets']:
        expected[target] = data[target].to_numpy()
    expected['label_source_stage'] = ['stage041b_holding_labels', 'stage042_holding_labels']
    m.reconcile_snapshot_rows(expected, jobs, features, labels, {'synthetic-0'})
    for column, value in [('return_marginal', 100), ('portfolio_drawdown', 100),
                           ('label_source_stage', 'stage042_holding_labels')]:
        changed = expected.copy(); changed.loc[0, column] = value
        with pytest.raises((AssertionError, RuntimeError, ValueError)):
            m.reconcile_snapshot_rows(changed, jobs, features, labels, {'synthetic-0'})


def test_dependency_drift_rejected_and_existing_versions_match():
    m = module(); assert m.check_versions(SPEC) == SPEC['versions']
    changed = {**SPEC, 'versions': {**SPEC['versions'], 'xgboost': '0.0.0'}}
    with pytest.raises(RuntimeError, match='version_changed'):
        m.check_versions(changed)


def test_source_drift_after_snapshot_loading_cannot_become_new_approved_input(tmp_path, monkeypatch):
    m = module(); source = tmp_path / 'bound-input.json'; source.write_text('approved')
    def identity(path):
        path = Path(path); raw = path.read_bytes()
        return {'path': str(path), 'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    expected = {str(source): identity(source)}
    runner = SimpleNamespace(_file_identity=identity)
    monkeypatch.setattr(m, 'OUTPUT', tmp_path / 'must-not-exist')
    monkeypatch.setattr(m, 'load_verified_snapshot', lambda *args: (None, SPEC, [], {}, {source}, runner, {}, expected))
    source.write_text('changed after snapshot loading')
    with pytest.raises(RuntimeError, match='source_drift'):
        m.run_campaign(SNAPSHOT, SNAPSHOT_SHA)
    assert not m.OUTPUT.exists()
