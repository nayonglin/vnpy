import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/stage054_late_session_consumption.py'
EXTRA = ['directional_late_return_30m', 'late_volume_fraction_30m']


def load(path):
    assert path.exists(), 'late-session model consumption is not implemented'
    spec = importlib.util.spec_from_file_location('test054_' + path.stem, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True))


def identity(path):
    return {'path': str(path.resolve()), 'size': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


@pytest.fixture
def campaign(tmp_path):
    models = load(ROOT / 'tools/stage044_holding_models.py')
    panel = load(ROOT / 'tools/stage040_holding_panel.py')
    base = json.loads((ROOT / 'artifacts/stage040_holding_panel/model_spec.json').read_text())
    spec = copy.deepcopy(base); spec['features'] += EXTRA
    jobs = [{'observation_id': f'obs-{i}', 'root_id': f'root-{i % 155}',
        'product_vt_symbol': 'sp.SHFE', 'vt_symbol': 'sp2606.SHFE', 'status': 'mature',
        'date': f"{'2026-06' if i % 155 < 60 else '2020-01'}-{2 + i // 155:02}",
        'end_date': '2026-07-31' if i % 155 < 60 else '2026-08-28'} for i in range(1002)]
    data = pd.DataFrame([{**job, 'label_status': 'verified', 'label_end_date': job['end_date'],
        **{key: i / 1002 for key in spec['features']},
        'return_marginal': -1 - i / 1002, 'drawdown_marginal': -2 - i / 1002} for i, job in enumerate(jobs)])
    months, index = [], {}
    for month in pd.period_range('2020-01', '2026-08', freq='M'):
        cutoff = str(month) + '-01'; selected = panel.training_selection(jobs, cutoff)
        count = len({jobs[int(key.split('-')[1])]['root_id'] for key, _ in selected})
        months.append({'cutoff': cutoff, 'mature_roots': count, 'observation_count': len(selected),
            'minimum_roots_met': count >= 60, 'weights': [[key, weight] for key, weight in selected]})
        bundle = models.fit_month(data, cutoff, spec)
        sha = models.save_bundle(bundle, tmp_path / 'models' / cutoff, spec)
        index[cutoff] = {key: bundle[key] for key in ('status', 'train_count', 'root_count', 'fit_count', 'train_frame_sha256')}
        index[cutoff]['metadata_sha256'] = sha
    source = tmp_path / 'sources'; write(source / 'base.json', base); write(source / 'candidate.json', spec)
    (source / 'features.csv').write_text('synthetic_source\n')
    feature_summary = {'stage': 'stage052_late_session_features', 'status': 'features_qualified_no_models',
        'all_observations_qualified': True, 'observation_count': 1002, 'qualified_count': 1002,
        'failed_count': 0, 'feature_count': 11, 'outputs': {
            'candidate_spec.json': identity(source / 'candidate.json'),
            'observation_late_features.csv': identity(source / 'features.csv')}}
    write(source / 'summary.json', feature_summary)
    dataset = {key: '1' * 64 for key in ('snapshot_sha256', 'dataset_sha256', 'file_contract_sha256', 'combined_dataset_sha256')}
    dataset.update(model_spec_sha256=identity(source / 'base.json')['sha256'],
        late_feature_summary_sha256=identity(source / 'summary.json')['sha256'],
        late_feature_table_sha256=identity(source / 'features.csv')['sha256'],
        candidate_spec_sha256=identity(source / 'candidate.json')['sha256'])
    manifest = {'spec': spec, 'versions': spec['versions'], 'evidence': spec['evidence'], 'months': months,
        'dataset_identity': dataset, 'source_identities': {str(p): identity(p) for p in source.iterdir()}}
    write(tmp_path / 'input_manifest.json', manifest); write(tmp_path / 'model_index.json', index)
    pd.DataFrame([{key: job[key] for key in ('observation_id', 'root_id', 'date', 'product_vt_symbol', 'vt_symbol')}
        | {'cutoff': job['date'][:7] + '-01', 'status': 'untrained', 'exit': False,
           'return_marginal': None, 'drawdown_marginal': None} for job in jobs]).to_csv(
        tmp_path / 'baseline_observation_predictions.csv', index=False)
    summary = {'stage': 'stage053_late_session_training', 'status': 'passed', 'month_count': 80,
        'trained_month_count': 1, 'historical_model_fit_count': 2, 'baseline_observation_count': 1002,
        'baseline_predicted_exit_count': 0, 'saved_prediction_mismatch_count': 0, 'feature_count': 11,
        'parent_implementation': 'stage044_holding_training',
        'late_feature_summary_sha256': dataset['late_feature_summary_sha256'],
        'new_strategy_replay_count': 0, 'network_attempt_count': 0, 'reviewer_count': 0, 'evidence': spec['evidence']}
    state = {'root': tmp_path, 'spec': spec, 'jobs': jobs, 'months': months, 'summary': summary,
        'bundle': bundle, 'models': models}
    seal(state); return state


def seal(state):
    root = state['root']
    state['summary']['output_identities'] = {name: identity(root / name) for name in
        ('input_manifest.json', 'model_index.json', 'baseline_observation_predictions.csv')}
    write(root / 'summary.json', state['summary']); state['sha'] = identity(root / 'summary.json')['sha256']


def catalog(state):
    return load(TOOL).load_catalog(state['root'], state['spec'], state['sha'], state['jobs'], state['months'])


def test_catalog_preserves_all_eight_dataset_bindings_without_native_calls(campaign, monkeypatch):
    import xgboost

    def denied(*args, **kwargs):
        raise AssertionError('catalog may not load or fit or predict')
    for name in ('load_model', 'fit', 'predict'):
        monkeypatch.setattr(xgboost.XGBRegressor, name, denied)
    registry, spec, evidence = catalog(campaign)
    assert len(registry) == 80 and len(spec['features']) == 11
    assert evidence['model_file_count'] == 2 and len(evidence['dataset_identity']) == 8
    assert json.loads((campaign['root'] / 'summary.json').read_text())['stage'] == 'stage053_late_session_training'


@pytest.mark.parametrize('change', ['old_stage', 'wrong_feature_count', 'wrong_parent', 'dataset_missing',
    'extra_dataset_key', 'wrong_candidate', 'wrong_base', 'wrong_table', 'wrong_summary', 'wrong_weights', 'native_changed'])
def test_extended_and_original_catalog_guards_reject_resealed_corruption(campaign, change):
    root = campaign['root']; manifest = json.loads((root / 'input_manifest.json').read_text())
    if change == 'old_stage': campaign['summary']['stage'] = 'stage044_holding_training'
    elif change == 'wrong_feature_count': campaign['summary']['feature_count'] = 9
    elif change == 'wrong_parent': campaign['summary']['parent_implementation'] = 'other'
    elif change == 'dataset_missing': del manifest['dataset_identity']['combined_dataset_sha256']
    elif change == 'extra_dataset_key': manifest['dataset_identity']['ignored'] = '2' * 64
    elif change.startswith('wrong_') and change != 'wrong_weights':
        key = {'wrong_candidate': 'candidate_spec_sha256', 'wrong_base': 'model_spec_sha256',
            'wrong_table': 'late_feature_table_sha256', 'wrong_summary': 'late_feature_summary_sha256'}[change]
        manifest['dataset_identity'][key] = '2' * 64
    elif change == 'wrong_weights': manifest['months'][-1]['weights'][0][1] = 1.
    else: (root / 'models/2026-08-01/return_marginal.ubj').write_bytes(b'corrupt')
    write(root / 'input_manifest.json', manifest); seal(campaign)
    with pytest.raises(RuntimeError): catalog(campaign)


def guard_setup(campaign):
    baseline = load(ROOT.parent / 'futures_trend_xgboost_formal_signal_marginal_utility_v4/tools/stage003_frozen_baseline_event_qualification.py')
    p = baseline.load_runner().load_metadata_preflight_module().load_preflight_module()
    registry, spec, _ = catalog(campaign)
    guard = load(TOOL).holding_guard_class(p, baseline)((campaign['root'],), registry=registry, spec=spec)
    return p, guard


def test_eleven_current_inputs_native_roundtrip_and_no_month_reload(campaign):
    p, guard = guard_setup(campaign); features = {key: .2 for key in campaign['spec']['features']}
    expected = campaign['models'].predict_decision(campaign['bundle'], '2026-08-04', 'sp.SHFE', features, campaign['spec'])
    with p.NetworkBlock(), guard:
        assert guard.predict_holding('2026-08-04', 'sp.SHFE', features) == expected
        assert guard.predict_holding('2026-08-05', 'sp.SHFE', features) == expected
    assert expected['exit'] is True and guard.xgboost_receipt()['native_model_load_count'] == 2
    assert not any(guard.counters.values())


@pytest.mark.parametrize('path', ['stage052_late_session_features/observation_late_features.csv',
    'stage053_late_session_training/baseline_observation_predictions.csv', 'stage043_label_collection/forbidden.csv'])
def test_new_A_tables_and_existing_labels_are_denied(campaign, path):
    p, guard = guard_setup(campaign)
    with pytest.raises(p.ImportPreflightError):
        with guard: (ROOT / 'artifacts' / path).read_bytes()
    assert guard.counters['label_value_read_count'] == 1


@pytest.mark.parametrize('change', ['missing_late', 'extra_label', 'bool_value', 'bad_volume_share'])
@pytest.mark.parametrize('route', ['holding', 'event'])
def test_exact_eleven_input_schema_and_domains_are_required(campaign, change, route):
    _, guard = guard_setup(campaign); features = {key: .2 for key in campaign['spec']['features']}
    if change == 'missing_late': del features[EXTRA[0]]
    elif change == 'extra_label': features['return_marginal'] = .1
    elif change == 'bool_value': features[EXTRA[0]] = True
    else: features[EXTRA[1]] = 1.1
    with pytest.raises(RuntimeError):
        with guard:
            if route == 'holding': guard.predict_holding('2026-08-04', 'sp.SHFE', features)
            else: guard.predict_event({**features, 'decision_date': '2026-08-04', 'product_vt_symbol': 'sp.SHFE'})
    assert guard.decision_count == 0


def test_bootstrap_import_has_no_sensitive_modules():
    import subprocess
    import sys

    assert TOOL.exists(), 'late-session model consumption is not implemented'
    code = f'import runpy,sys; runpy.run_path({str(TOOL)!r}); assert not ({{"numpy","pandas","xgboost","vnpy"}} & set(sys.modules))'
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
