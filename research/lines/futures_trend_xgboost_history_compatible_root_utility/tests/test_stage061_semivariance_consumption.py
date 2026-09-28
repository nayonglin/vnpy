import copy
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/stage061_semivariance_consumption.py'
EXTRA = ['favorable_semivariance_5m', 'adverse_semivariance_5m']


def load(path):
    assert path.exists(), 'semivariance consumption is not implemented'
    spec = importlib.util.spec_from_file_location('test061_' + path.stem, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


@pytest.fixture
def campaign(tmp_path):
    helper = load(ROOT / 'tests/test_stage054_late_session_consumption.py')
    helper.EXTRA = EXTRA
    state = helper.campaign.__wrapped__(tmp_path)
    source = tmp_path / 'sources'; manifest_path = tmp_path / 'input_manifest.json'
    features = json.loads((source / 'summary.json').read_text())
    features['stage'] = 'stage059_realized_semivariance_features'
    features['outputs']['observation_semivariance_features.csv'] = features['outputs'].pop('observation_late_features.csv')
    helper.write(source / 'summary.json', features)
    manifest = json.loads(manifest_path.read_text()); dataset = manifest['dataset_identity']
    dataset['semivariance_feature_summary_sha256'] = helper.identity(source / 'summary.json')['sha256']
    dataset['semivariance_feature_table_sha256'] = dataset.pop('late_feature_table_sha256')
    del dataset['late_feature_summary_sha256']
    manifest['source_identities'][str(source / 'summary.json')] = helper.identity(source / 'summary.json')
    helper.write(manifest_path, manifest)
    state['summary']['stage'] = 'stage060_semivariance_training'
    state['summary']['semivariance_feature_summary_sha256'] = dataset['semivariance_feature_summary_sha256']
    del state['summary']['late_feature_summary_sha256']
    helper.seal(state)
    return state


def catalog(state):
    return load(TOOL).load_catalog(state['root'], state['spec'], state['sha'], state['jobs'], state['months'])


def test_catalog_keeps_all_new_bindings_without_fit_load_or_predict(campaign, monkeypatch):
    import xgboost
    def denied(*args, **kwargs): raise AssertionError('catalog native call')
    for name in ('fit', 'load_model', 'predict'):
        monkeypatch.setattr(xgboost.XGBRegressor, name, denied)
    registry, spec, evidence = catalog(campaign)
    assert len(registry) == 80 and spec['features'][-2:] == EXTRA
    assert len(evidence['dataset_identity']) == 8 and evidence['model_file_count'] == 2
    assert evidence['stage'] == 'stage060_semivariance_training'


@pytest.mark.parametrize('change', ['old_stage', 'feature_count', 'parent', 'source_summary', 'table', 'base', 'candidate',
    'weights', 'missing_binding', 'extra_binding', 'native'])
def test_catalog_rejects_resealed_wrong_new_or_original_identity(campaign, change):
    helper = load(ROOT / 'tests/test_stage054_late_session_consumption.py')
    path = campaign['root'] / 'input_manifest.json'; manifest = json.loads(path.read_text())
    if change == 'old_stage': campaign['summary']['stage'] = 'stage053_late_session_training'
    elif change == 'feature_count': campaign['summary']['feature_count'] = 9
    elif change == 'parent': campaign['summary']['parent_implementation'] = 'other'
    elif change == 'weights': manifest['months'][-1]['weights'][0][1] = 1.
    elif change == 'missing_binding': del manifest['dataset_identity']['combined_dataset_sha256']
    elif change == 'extra_binding': manifest['dataset_identity']['ignored'] = '2' * 64
    elif change == 'native': (campaign['root'] / 'models/2026-08-01/return_marginal.ubj').write_bytes(b'corrupt')
    else:
        key = {'source_summary': 'semivariance_feature_summary_sha256', 'table': 'semivariance_feature_table_sha256',
            'base': 'model_spec_sha256', 'candidate': 'candidate_spec_sha256'}[change]
        manifest['dataset_identity'][key] = '2' * 64
    helper.write(path, manifest); helper.seal(campaign)
    with pytest.raises(RuntimeError): catalog(campaign)


def guard_setup(campaign):
    baseline = load(ROOT.parent / 'futures_trend_xgboost_formal_signal_marginal_utility_v4/tools/stage003_frozen_baseline_event_qualification.py')
    p = baseline.load_runner().load_metadata_preflight_module().load_preflight_module()
    registry, spec, _ = catalog(campaign)
    guard = load(TOOL).holding_guard_class(p, baseline)((campaign['root'],), registry=registry, spec=spec)
    return p, guard


def test_native_predictions_allow_real_zero_variance_and_cache_month(campaign):
    p, guard = guard_setup(campaign); values = {key: .2 for key in campaign['spec']['features']}
    values.update({key: 0. for key in EXTRA})
    expected = campaign['models'].predict_decision(campaign['bundle'], '2026-08-04', 'sp.SHFE', values, campaign['spec'])
    with p.NetworkBlock(), guard:
        assert guard.predict_holding('2026-08-04', 'sp.SHFE', values) == expected
        assert guard.predict_holding('2026-08-05', 'sp.SHFE', values) == expected
    assert guard.xgboost_receipt()['native_model_load_count'] == 2
    assert not any(guard.counters.values())


@pytest.mark.parametrize('path', ['stage059_realized_semivariance_features/observation_semivariance_features.csv',
    'stage059_realized_semivariance_features/sampled_prices.csv',
    'stage060_semivariance_training/baseline_observation_predictions.csv',
    'stage053_late_session_training/baseline_observation_predictions.csv', 'stage043_label_collection/forbidden.csv'])
def test_A_tables_and_labels_are_blocked(campaign, path):
    p, guard = guard_setup(campaign)
    with pytest.raises(p.ImportPreflightError):
        with guard: (ROOT / 'artifacts' / path).read_bytes()
    assert guard.counters['label_value_read_count'] == 1


@pytest.mark.parametrize('change', ['negative', 'nan', 'bool', 'missing', 'old_late', 'extra_label'])
@pytest.mark.parametrize('route', ['holding', 'event'])
def test_strict_current_feature_domain(campaign, change, route):
    _, guard = guard_setup(campaign); values = {key: .2 for key in campaign['spec']['features']}
    if change in {'negative', 'nan', 'bool'}:
        values[EXTRA[0]] = {'negative': -1., 'nan': float('nan'), 'bool': True}[change]
    elif change == 'missing': del values[EXTRA[0]]
    elif change == 'old_late': values['directional_late_return_30m'] = values.pop(EXTRA[0])
    else: values['return_marginal'] = -.1
    with pytest.raises(RuntimeError):
        with guard:
            if route == 'holding': guard.predict_holding('2026-08-04', 'sp.SHFE', values)
            else: guard.predict_event({**values, 'decision_date': '2026-08-04', 'product_vt_symbol': 'sp.SHFE'})
    assert guard.decision_count == 0
