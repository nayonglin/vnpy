import csv
import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/stage045_holding_catalog.py'


def load(path):
    spec = importlib.util.spec_from_file_location('test045_' + path.stem, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True))


def identity(path):
    raw = path.read_bytes()
    return {'path': str(path.resolve()), 'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


@pytest.fixture
def campaign(tmp_path):
    models = load(ROOT / 'tools/stage044_holding_models.py')
    panel = load(ROOT / 'tools/stage040_holding_panel.py')
    base = models.load('stage006_monthly_models')
    spec = json.loads((ROOT / 'artifacts/stage040_holding_panel/model_spec.json').read_text())
    jobs = []
    for i in range(1002):
        selected = i % 155 < 60
        jobs.append({'observation_id': f'observation-{i}', 'root_id': f'root-{i % 155}',
            'product_vt_symbol': 'sp.SHFE', 'vt_symbol': 'sp2606.SHFE', 'status': 'mature',
            'date': f"{'2026-06' if selected else '2020-01'}-{2 + i // 155:02}",
            'end_date': '2026-07-31' if selected else '2026-08-28'})
    data = pd.DataFrame([{**job, 'label_status': 'verified', 'label_end_date': job['end_date'],
        **{key: i / 1002 for key in spec['features']},
        'return_marginal': -1 - i / 1002, 'drawdown_marginal': -2.} for i, job in enumerate(jobs)])
    months, index = [], {}
    cutoffs = [str(v) + '-01' for v in pd.period_range('2020-01', '2026-08', freq='M')]
    for cutoff in cutoffs:
        selected = panel.training_selection(jobs, cutoff)
        count = len({jobs[int(key.split('-')[1])]['root_id'] for key, _ in selected})
        months.append({'cutoff': cutoff, 'mature_roots': count, 'observation_count': len(selected),
            'minimum_roots_met': count >= 60, 'weights': [[key, weight] for key, weight in selected]})
        if cutoff == '2026-08-01':
            bundle = models.fit_month(data, cutoff, spec)
        else:
            bundle = {'cutoff': cutoff, 'status': 'untrained', 'train_count': 0, 'root_count': 0,
                'train_observation_ids': [], 'train_root_ids': [], 'train_weights': [],
                'train_frame_sha256': '0' * 64, 'spec_sha256': base.spec_digest(spec),
                'max_train_date': None, 'max_train_end': None, 'heads': {}, 'fit_count': 0}
        sha = models.save_bundle(bundle, tmp_path / 'models' / cutoff, spec)
        index[cutoff] = {key: bundle[key] for key in ('status', 'train_count', 'root_count', 'fit_count', 'train_frame_sha256')}
        index[cutoff]['metadata_sha256'] = sha
    source = tmp_path / 'synthetic_source.json'
    write(source, {'synthetic': True})
    dataset = {key: '1' * 64 for key in ('snapshot_sha256', 'dataset_sha256', 'model_spec_sha256', 'file_contract_sha256')}
    manifest = {'spec': spec, 'versions': spec['versions'], 'evidence': spec['evidence'], 'months': months,
        'dataset_identity': dataset, 'source_identities': {str(source): identity(source)}}
    write(tmp_path / 'input_manifest.json', manifest)
    write(tmp_path / 'model_index.json', index)
    predictions = [{key: job[key] for key in ('observation_id', 'root_id', 'date', 'product_vt_symbol', 'vt_symbol')}
        | {'cutoff': job['date'][:7] + '-01', 'status': 'untrained', 'exit': False,
           'return_marginal': None, 'drawdown_marginal': None} for job in jobs]
    pd.DataFrame(predictions).to_csv(tmp_path / 'baseline_observation_predictions.csv', index=False)
    summary = {'stage': 'stage044_holding_training', 'status': 'passed', 'month_count': 80,
        'trained_month_count': 1, 'historical_model_fit_count': 1, 'baseline_observation_count': 1002,
        'baseline_predicted_exit_count': 0, 'saved_prediction_mismatch_count': 0,
        'new_strategy_replay_count': 0, 'network_attempt_count': 0, 'reviewer_count': 0, 'evidence': spec['evidence']}
    state = {'root': tmp_path, 'spec': spec, 'jobs': jobs, 'months': months, 'summary': summary}
    seal(state)
    return state


def seal(state):
    root = state['root']
    state['summary']['output_identities'] = {name: identity(root / name) for name in
        ('input_manifest.json', 'model_index.json', 'baseline_observation_predictions.csv')}
    write(root / 'summary.json', state['summary'])
    state['sha'] = identity(root / 'summary.json')['sha256']


def catalog(state):
    assert TOOL.exists(), 'holding model catalog adapter is not implemented'
    return load(TOOL).load_catalog(state['root'], state['spec'], state['sha'], state['jobs'], state['months'])


def test_complete_catalog_binds_native_models_without_loading_them(campaign, monkeypatch):
    import xgboost

    def denied(*args, **kwargs):
        raise AssertionError('catalog must not load, fit or predict native models')
    for name in ('load_model', 'fit', 'predict'):
        monkeypatch.setattr(xgboost.XGBRegressor, name, denied)
    registry, spec, evidence = catalog(campaign)
    assert len(registry) == evidence['metadata_count'] == 80
    assert evidence['model_file_count'] == 1
    assert evidence['summary_sha256'] == campaign['sha'] and spec == campaign['spec']
    assert campaign['root'] / 'models/2026-08-01/return_marginal.ubj' in evidence['files']


@pytest.mark.parametrize('name', ['summary.json', 'input_manifest.json', 'model_index.json',
    'baseline_observation_predictions.csv', 'synthetic_source.json', 'models/2026-08-01/metadata.json',
    'models/2026-08-01/return_marginal.ubj'])
def test_any_bound_file_change_is_rejected(campaign, name):
    with (campaign['root'] / name).open('ab') as stream:
        stream.write(b' ')
    with pytest.raises(RuntimeError, match='changed'):
        catalog(campaign)


@pytest.mark.parametrize('change', ['failure', 'missing_month', 'extra_month', 'wrong_count', 'wrong_spec',
    'wrong_plan', 'wrong_observation', 'wrong_root', 'wrong_weights', 'wrong_max_date', 'symlink'])
def test_identity_and_calendar_gates_are_not_just_self_reported_counts(campaign, change):
    root = campaign['root']
    index = json.loads((root / 'model_index.json').read_text())
    manifest = json.loads((root / 'input_manifest.json').read_text())
    metadata_path = root / 'models/2026-08-01/metadata.json'
    meta = json.loads(metadata_path.read_text())
    if change == 'failure':
        write(root / 'failure.json', {})
    elif change == 'missing_month':
        del index['2020-01-01']
    elif change == 'extra_month':
        index['2026-09-01'] = index['2026-08-01']
    elif change == 'wrong_count':
        campaign['summary']['historical_model_fit_count'] += 1
    elif change == 'wrong_spec':
        manifest['spec']['estimator']['n_estimators'] += 1
    elif change == 'wrong_plan':
        manifest['months'][-1]['weights'][0][1] = .5
    elif change == 'wrong_observation':
        meta['train_observation_ids'][0] = 'other-observation'
    elif change == 'wrong_root':
        meta['train_root_ids'] = ['renamed-' + key for key in meta['train_root_ids']]
    elif change == 'wrong_weights':
        meta['train_weights'][0] = 1.
    elif change == 'wrong_max_date':
        meta['max_train_date'] = '2026-06-29'
    elif change == 'symlink':
        native = metadata_path.parent / 'return_marginal.ubj'
        raw = native.read_bytes(); native.unlink()
        other = root / 'other.ubj'; other.write_bytes(raw); native.symlink_to(other)
    write(metadata_path, meta)
    index['2026-08-01']['metadata_sha256'] = identity(metadata_path)['sha256']
    write(root / 'model_index.json', index); write(root / 'input_manifest.json', manifest); seal(campaign)
    with pytest.raises(RuntimeError):
        catalog(campaign)


@pytest.mark.parametrize('change', ['duplicate', 'wrong_product', 'wrong_month', 'untrained_value', 'untrained_exit', 'nonfinite'])
def test_original_prediction_inventory_is_verified_not_used_as_live_decisions(campaign, change):
    path = campaign['root'] / 'baseline_observation_predictions.csv'
    with path.open() as stream:
        reader = csv.DictReader(stream); fields = reader.fieldnames; rows = list(reader)
    if change == 'duplicate':
        rows[0] = rows[1].copy()
    elif change == 'wrong_product':
        rows[0]['product_vt_symbol'] = 'fu.SHFE'
    elif change == 'wrong_month':
        rows[0]['cutoff'] = '2026-08-01'
    elif change == 'untrained_value':
        rows[0]['return_marginal'] = '-1'
    elif change == 'untrained_exit':
        rows[0]['exit'] = 'True'
    else:
        rows[0]['return_marginal'] = 'nan'
    with path.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    seal(campaign)
    with pytest.raises(RuntimeError):
        catalog(campaign)


def test_no_historical_catalog_exists_until_training_is_complete():
    assert TOOL.exists(), 'holding model catalog adapter is not implemented'
    with pytest.raises(RuntimeError, match='not_complete'):
        load(TOOL).load_catalog(ROOT / 'artifacts/stage044_holding_training', {}, '0' * 64, [], [])


def prediction_fixture(tmp_path, return_value, drawdown_value, action):
    job = {'observation_id': 'synthetic', 'root_id': 'root', 'date': '2020-03-04',
        'product_vt_symbol': 'sp.SHFE', 'vt_symbol': 'sp2006.SHFE'}
    row = {**job, 'cutoff': '2020-03-01', 'status': 'predicted', 'exit': str(action),
        'return_marginal': return_value, 'drawdown_marginal': drawdown_value}
    path = tmp_path / 'predictions.csv'
    with path.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row)); writer.writeheader(); writer.writerow(row)
    return path, [job], {'2020-03-01': {'status': 'trained'}}, {'baseline_predicted_exit_count': int(action)}


@pytest.mark.parametrize('values,action', [((-1, -2), True), ((-1, 0), False), ((-1, 2), False),
    ((0, -2), False), ((1, -2), False)])
def test_trained_prediction_action_is_strictly_both_negative(tmp_path, values, action):
    module = load(TOOL)
    module.verify_predictions(*prediction_fixture(tmp_path, *values, action))
    with pytest.raises(RuntimeError, match='prediction_action'):
        module.verify_predictions(*prediction_fixture(tmp_path, *values, not action))


@pytest.mark.parametrize('value', ['nan', 'inf', '-inf'])
def test_trained_prediction_nonfinite_values_are_rejected(tmp_path, value):
    with pytest.raises(RuntimeError, match='prediction_nonfinite'):
        load(TOOL).verify_predictions(*prediction_fixture(tmp_path, value, -1, False))
