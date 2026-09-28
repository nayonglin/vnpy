import copy
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / 'tools/stage060_semivariance_training.py'
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location('test_training060', path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def fixture(m):
    source = m.load('stage059_realized_semivariance_features')
    data = pd.DataFrame({'observation_id': ['a', 'b'], 'root_id': ['r', 's'],
        'date': ['2021-09-06', '2021-09-07'], 'product_vt_symbol': ['aa.X', 'bb.X'], 'vt_symbol': ['aa1.X', 'bb1.X'],
        'return_marginal': [np.nextafter(.1, 1), -.2], 'drawdown_marginal': [.01, -.02],
        'label_end_date': ['2021-09-10', '2021-09-11'], 'label_status': ['verified', 'verified']})
    for name in source.BASE_FEATURES: data[name] = [np.nextafter(.3, 1), .7]
    features = data[list(source.IDS)].copy()
    features['asof_close'] = features.date + 'T15:00:00'
    features['last_minute'] = features.date + 'T14:59:00'
    features['sample_count'] = 45; features['day_minute_count'] = 225
    features['status'] = 'qualified'
    features['favorable_semivariance_5m'] = [.001, .002]
    features['adverse_semivariance_5m'] = [.003, .004]
    features['realized_variance_5m'] = [.004, .006]
    base = {'features': list(source.BASE_FEATURES), 'minimum_mature_roots': 60, 'estimator': {'max_depth': 2}}
    return data, features, base, source.candidate_spec(base)


def test_join_preserves_exact_labels_features_and_order():
    m = module(); assert m is not None, 'semivariance training implementation missing'
    data, features, base, spec = fixture(m); before = data.copy(deep=True)
    result = m.join_features(data, features.iloc[::-1], base, spec)
    pd.testing.assert_frame_equal(result[data.columns], data, check_exact=True)
    pd.testing.assert_frame_equal(data, before, check_exact=True)
    assert result.favorable_semivariance_5m.tolist() == [.001, .002]


@pytest.mark.parametrize('kind', ['missing', 'duplicate', 'root', 'contract', 'date', 'nan', 'negative',
    'asof', 'last_minute', 'count', 'fractional_count', 'zero_count', 'variance', 'status',
    'target_column', 'base_column', 'late_column', 'parameter', 'feature_order'])
def test_join_fails_on_changed_identity_clock_domain_or_spec(kind):
    m = module(); data, features, base, spec = fixture(m)
    if kind == 'missing': features = features.iloc[:1]
    elif kind == 'duplicate': features = pd.concat([features, features.iloc[:1]])
    elif kind == 'root': features.loc[0, 'root_id'] = 'wrong'
    elif kind == 'contract': features.loc[0, 'vt_symbol'] = 'wrong.X'
    elif kind == 'date': features.loc[0, 'date'] = '2021-09-08'
    elif kind == 'nan': features.loc[0, 'favorable_semivariance_5m'] = np.nan
    elif kind == 'negative': features.loc[0, 'favorable_semivariance_5m'] = -.001
    elif kind == 'asof': features.loc[0, 'asof_close'] = '2021-09-07T15:00:00'
    elif kind == 'last_minute': features.loc[0, 'last_minute'] = '2021-09-06T15:00:00'
    elif kind == 'count': features.loc[0, 'sample_count'] = 44
    elif kind == 'fractional_count':
        features['sample_count'] = 45.1; features['day_minute_count'] = 225.5
    elif kind == 'zero_count': features[['sample_count', 'day_minute_count']] = 0
    elif kind == 'variance': features.loc[0, 'realized_variance_5m'] += .01
    elif kind == 'status': features.loc[0, 'status'] = 'failed'
    elif kind == 'target_column': features['return_marginal'] = 0.
    elif kind == 'base_column': features['loss_streak'] = 0.
    elif kind == 'late_column': features['directional_late_return_30m'] = 0.
    elif kind == 'parameter': spec['estimator']['max_depth'] = 3
    elif kind == 'feature_order': spec['features'].reverse()
    with pytest.raises(RuntimeError): m.join_features(data, features, base, spec)


def test_existing_output_blocks_before_label_access(tmp_path, monkeypatch):
    m = module(); monkeypatch.setattr(m, 'OUTPUT', tmp_path)
    monkeypatch.setattr(m, 'load_dataset', lambda *_: pytest.fail('unexpected label read'))
    with pytest.raises(RuntimeError, match='already_exists'): m.run()


def test_training_adapter_preserves_frozen_parent_and_relabels_own_summary(tmp_path, monkeypatch):
    m = module(); monkeypatch.setattr(m, 'OUTPUT', tmp_path)
    parent = m.campaign()
    assert parent.load_verified_snapshot is m.load_dataset and parent.OUTPUT == tmp_path
    original = m.load('stage044_holding_training')
    assert original.OUTPUT == ROOT / 'artifacts/stage044_holding_training'
    assert original.load_verified_snapshot is not m.load_dataset
    payload = {'stage': 'stage044_holding_training', 'status': 'passed'}
    before = copy.deepcopy(payload)
    parent.load('stage004_label_batch').write_json(tmp_path / 'summary.json', payload)
    assert json.loads((tmp_path / 'summary.json').read_text())['stage'] == m.STAGE
    assert payload == before
