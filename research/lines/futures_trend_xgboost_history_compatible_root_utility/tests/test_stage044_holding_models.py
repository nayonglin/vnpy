import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'tools/stage044_holding_models.py'
SPEC = json.loads((ROOT / 'artifacts/stage040_holding_panel/model_spec.json').read_text())


def module():
    assert PATH.exists(), 'holding model implementation missing'
    spec = importlib.util.spec_from_file_location('holding_models_test', PATH)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def sample(roots=60, copies=1):
    data = pd.DataFrame([{'observation_id': f'synthetic-{root}-{day}', 'root_id': f'root-{root}',
        'date': f'2020-01-{day + 2:02d}', 'label_end_date': '2020-01-30', 'label_status': 'verified',
        'product_vt_symbol': 'rb.SHFE', 'vt_symbol': 'rb2005.SHFE',
        'return_marginal': root / 100 - 0.2, 'drawdown_marginal': root / 200 - 0.1}
        for root in range(roots) for day in range(copies)])
    for i, feature in enumerate(SPEC['features']):
        data[feature] = np.sin(np.arange(len(data)) + i)
    return data


class RecordingRegressor:
    def __init__(self, **parameters):
        self.parameters = parameters

    def fit(self, features, target, *, sample_weight):
        self.features = features.copy()
        self.target = np.asarray(target).copy()
        self.weights = np.asarray(sample_weight).copy()
        return self

    def predict(self, features):
        self.current = features.copy()
        return features['portfolio_drawdown'].to_numpy()


def forbidden(**parameters):
    raise AssertionError('must not construct estimator')


def test_sixty_observations_of_thirty_roots_do_not_meet_root_gate():
    data = sample(30, 2)
    result = module().fit_month(data, '2020-02-01', SPEC, forbidden)
    assert result['train_count'] == 60 and result['root_count'] == 30
    assert result['status'] == 'untrained' and result['fit_count'] == 0


def test_root_weights_sum_to_one_and_mature_date_is_strictly_past():
    data = sample(3, 2)
    data.loc[data.root_id.eq('root-1'), 'label_end_date'] = '2020-02-01'
    data.loc[data.root_id.eq('root-2'), 'label_end_date'] = '2020-02-02'
    train = module().training_rows(data, '2020-02-01', SPEC)
    assert train.observation_id.tolist() == ['synthetic-0-0', 'synthetic-0-1']
    assert train.sample_weight.tolist() == [0.5, 0.5]


def test_weighted_moments_do_not_overweight_longer_roots_or_read_future_targets():
    data = sample()
    duplicate = data.iloc[[0]].copy()
    duplicate['observation_id'] = 'synthetic-extra'; duplicate['date'] = '2020-01-03'
    data = pd.concat([data, duplicate], ignore_index=True)
    data[SPEC['targets']] = 0.0
    data.loc[data.root_id.eq('root-0'), SPEC['targets']] = [2.0, -2.0]
    future = sample(1); future['observation_id'] = 'future'; future['root_id'] = 'future-root'
    future['label_end_date'] = '2020-02-01'; future[SPEC['targets']] = 1e9
    data = pd.concat([data, future], ignore_index=True)
    bundle = module().fit_month(data, '2020-02-01', SPEC, RecordingRegressor)
    assert bundle['root_count'] == 60 and bundle['train_count'] == 61 and bundle['fit_count'] == 2
    assert 'future' not in bundle['train_observation_ids']
    assert sum(bundle['train_weights']) == 60
    for target, sign in [('return_marginal', 1), ('drawdown_marginal', -1)]:
        head = bundle['heads'][target]
        assert head['mean'] == pytest.approx(sign / 30)
        assert head['std'] == pytest.approx(np.sqrt(59) / 30)
        model = head['estimator']
        assert model.parameters == SPEC['estimator'] and list(model.features.columns) == SPEC['features']
        assert model.weights.tolist() == [0.5] + [1.0] * 59 + [0.5]
        assert model.target[0] == pytest.approx(sign * np.sqrt(59))
        assert model.target[1] == pytest.approx(-sign / np.sqrt(59))


@pytest.mark.parametrize('patch', [
    {'observation_id': 'synthetic-1-0'}, {'root_id': ''}, {'label_status': 'pending'},
    {'product_vt_symbol': 'fu.SHFE'}, {'return_marginal': np.inf}, {'portfolio_drawdown': np.nan},
    {'label_end_date': '2020-01-02'}, {'date': '2020-1-2'}, {'label_end_date': '2020-02-30'},
])
def test_invalid_training_rows_are_rejected(patch):
    data = sample()
    for key, value in patch.items():
        data.loc[0, key] = value
    with pytest.raises((RuntimeError, ValueError)):
        module().training_rows(data, '2020-02-01', SPEC)


def test_conflicting_root_end_or_duplicate_root_day_is_rejected():
    m = module()
    for column, value in [('label_end_date', '2020-01-29'), ('date', '2020-01-02')]:
        data = sample(60, 2); data.loc[1, column] = value
        with pytest.raises((RuntimeError, ValueError)):
            m.training_rows(data, '2020-02-01', SPEC)


def test_non_month_boundary_rejected():
    with pytest.raises((RuntimeError, ValueError)):
        module().training_rows(sample(), '2020-02-02', SPEC)


def test_constant_targets_do_not_fit_and_zero_is_not_exit():
    m = module(); data = sample(60, 2)
    data[SPEC['targets']] = [-0.1, 0.0]
    bundle = m.fit_month(data, '2020-02-01', SPEC, forbidden)
    assert bundle['status'] == 'trained' and bundle['fit_count'] == 0
    result = m.predict_decision(bundle, '2020-02-03', 'rb.SHFE', {f: 0 for f in SPEC['features']}, SPEC)
    assert result['return_marginal'] == -0.1 and result['drawdown_marginal'] == 0
    assert not result['exit']


def test_current_features_and_strict_double_negative_action():
    m = module(); bundle = m.fit_month(sample(), '2020-02-01', SPEC, RecordingRegressor)
    features = {f: 0.0 for f in SPEC['features']}; features['portfolio_drawdown'] = -4.0
    result = m.predict_decision(bundle, '2020-02-03', 'rb.SHFE', features, SPEC)
    assert result['status'] == 'predicted' and result['exit'] is True
    for target, head in bundle['heads'].items():
        assert head['estimator'].current.iloc[0].to_dict() == features
        assert result[target] == -4.0 * head['std'] + head['mean']


def test_untrained_fixed_fu_missing_and_stale_model_boundaries():
    m = module(); bundle = m.fit_month(sample(59), '2020-02-01', SPEC, forbidden)
    assert not m.predict_decision(bundle, '2020-02-03', 'rb.SHFE', {}, SPEC)['exit']
    assert m.predict_decision(None, '2020-02-03', 'fu.SHFE', {}, SPEC)['status'] == 'fixed_fu'
    with pytest.raises(RuntimeError, match='missing'):
        m.predict_decision(None, '2020-02-03', 'rb.SHFE', {}, SPEC)
    with pytest.raises(RuntimeError, match='month'):
        m.predict_decision(bundle, '2020-03-03', 'rb.SHFE', {}, SPEC)


def test_feature_whitelist_rejects_missing_or_future_feature_at_decision():
    m = module(); bundle = m.fit_month(sample(), '2020-02-01', SPEC, RecordingRegressor)
    features = {f: 0.0 for f in SPEC['features']}
    for invalid in ({}, {**features, 'future_price': 100}):
        with pytest.raises(RuntimeError, match='feature'):
            m.predict_decision(bundle, '2020-02-03', 'rb.SHFE', invalid, SPEC)


def test_native_synthetic_model_roundtrip_and_corruption(tmp_path):
    m = module(); data = sample(70, 2)
    bundle = m.fit_month(data, '2020-02-01', SPEC)
    root = tmp_path / 'model'; sha = m.save_bundle(bundle, root, SPEC)
    restored = m.load_bundle(root, sha, SPEC)
    features = data.iloc[0][SPEC['features']].to_dict()
    assert m.predict_decision(bundle, '2020-02-04', 'rb.SHFE', features, SPEC) == m.predict_decision(restored, '2020-02-04', 'rb.SHFE', features, SPEC)
    assert restored['root_count'] == 70 and restored['train_count'] == 140
    with pytest.raises(FileExistsError):
        m.save_bundle(bundle, root, SPEC)
    (root / 'return_marginal.ubj').write_bytes(b'corrupt')
    with pytest.raises(RuntimeError, match='model_file_changed'):
        m.load_bundle(root, sha, SPEC)


def test_constant_and_untrained_storage_preserve_root_gate(tmp_path):
    m = module()
    for roots in (30, 60):
        data = sample(roots, 2); data[SPEC['targets']] = [-0.1, -0.2]
        bundle = m.fit_month(data, '2020-02-01', SPEC, forbidden)
        root = tmp_path / str(roots); sha = m.save_bundle(bundle, root, SPEC)
        loaded = m.load_bundle(root, sha, SPEC)
        assert loaded['status'] == ('trained' if roots == 60 else 'untrained')
        assert loaded['root_count'] == roots and loaded['train_count'] == roots * 2


def test_metadata_root_weight_or_future_endpoint_tamper_is_rejected(tmp_path):
    m = module(); data = sample(30, 2)
    root = tmp_path / 'model'; m.save_bundle(m.fit_month(data, '2020-02-01', SPEC, forbidden), root, SPEC)
    path = root / 'metadata.json'; original = json.loads(path.read_text())
    for patch in ({'root_count': 60}, {'train_weights': [1.0] * 60}, {'max_train_end': '2020-02-01'}):
        path.write_text(json.dumps({**original, **patch}))
        with pytest.raises(RuntimeError):
            m.load_bundle(root, m.digest(path), SPEC)
