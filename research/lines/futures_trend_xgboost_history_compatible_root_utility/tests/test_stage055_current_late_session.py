import copy
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
from types import SimpleNamespace

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/stage055_current_late_session.py'


def load(name, folder='tools'):
    path = ROOT / folder / (name + '.py')
    assert path.exists(), 'current late-session provider is not implemented'
    spec = importlib.util.spec_from_file_location('test055_' + name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def setup_source(tmp_path):
    fixture = load('test_stage046_dynamic_exit_source', 'tests')
    config = fixture.make_source(tmp_path); cache = config['cache']
    bars = pd.read_csv(cache / 'minutes.csv'); chunks = [bars]
    for day in fixture.DAYS:
        chunks.append(pd.DataFrame({'vt_symbol': fixture.SYMBOL,
            'bar_datetime': pd.date_range(day + ' 14:30:00', periods=30, freq='min'),
            'bar_date': day, 'open': 110., 'high': 120., 'low': 109., 'close': 119., 'volume': 10.}))
    bars = pd.concat(chunks, ignore_index=True)
    bars['bar_datetime'] = pd.to_datetime(bars.bar_datetime)
    bars = bars.sort_values('bar_datetime').reset_index(drop=True)
    bars.to_csv(cache / 'minutes.csv', index=False)
    bars[['vt_symbol', 'bar_datetime', 'bar_date']].to_csv(cache / 'expected.csv.gz', index=False, compression='gzip')
    reference = bars.groupby('bar_date', sort=True).agg(open=('open', 'first'), high=('high', 'max'),
        low=('low', 'min'), close=('close', 'last'), volume=('volume', 'sum')).reset_index()
    reference.to_csv(cache / 'daily.csv', index=False)
    original = Path(config['files']['source_database']['path'])
    with sqlite3.connect(original) as connection:
        for row in reference.to_dict('records'):
            connection.execute('UPDATE dbbardata SET open_price=?,high_price=?,low_price=?,close_price=?,volume=? WHERE datetime=?',
                [row[key] for key in ('open', 'high', 'low', 'close', 'volume')] + [row['bar_date'] + ' 00:00:00'])
    shutil.copyfile(original, config['database'])
    manifest = json.loads((cache / 'manifest.json').read_text()); entry = manifest['files'][0]
    entry['rows'] = len(bars)
    for name, key in [('minutes.csv', 'sha256'), ('expected.csv.gz', 'expected_minutes_sha256'), ('daily.csv', 'daily_reference_sha256')]:
        entry[key] = fixture.identity(cache / name)['sha256']
    fixture.write(cache / 'manifest.json', manifest)
    config['files'] = {'source_database': fixture.identity(original)} | {p.name: fixture.identity(p) for p in cache.iterdir()}
    config['expected_source_sha256'] = fixture.identity(cache / 'manifest.json')['sha256']
    row, book = load('test_stage047_current_holding_policy', 'tests').sample(day='2021-01-11')
    row.update(state_contract=fixture.SYMBOL, actual_positions={fixture.SYMBOL: 2}, targets={fixture.SYMBOL: 2})
    row['bar']['vt_symbol'] = fixture.SYMBOL
    ref = reference.set_index('bar_date').loc[row['date']]
    row['bar'].update({key + '_price': float(ref[key]) for key in ('open', 'high', 'low', 'close')})
    row['bar']['volume'] = float(ref.volume)
    return config, row, {fixture.SYMBOL: next(iter(book.values()))}


def test_current_raw_minutes_and_trading_day_volume_are_not_A_lookup(tmp_path):
    config, row, _ = setup_source(tmp_path); source = load('stage055_current_late_session').LateSessionSource(**config)
    values = source.features(row)
    assert values == {'directional_late_return_30m': pytest.approx(119 / 110 - 1), 'late_volume_fraction_30m': .75}
    row['actual_positions']['jm2105.DCE'] = -3
    assert source.features(row)['directional_late_return_30m'] == pytest.approx(-(119 / 110 - 1))
    receipt = source.receipt()
    assert receipt['feature_request_count'] == 2 and receipt['request_count'] == 0
    assert receipt['feature_records'][0]['first_minute'] == '2021-01-08T21:00:00'
    assert receipt['feature_records'][0]['asof_close'] == '2021-01-11T15:00:00'
    assert receipt['A_observation_table_used'] is False
    source.verify_used_inputs()


def test_feature_and_exit_sources_share_identity_without_sharing_action_counts(tmp_path):
    config, row, _ = setup_source(tmp_path); source = load('stage055_current_late_session').LateSessionSource(**config)
    source.features(row)
    quote = source({'decision_date': row['date'], 'vt_symbol': 'jm2105.DCE', 'volume': 2}, '2021-01-12')
    assert quote['price'] == 103. and quote['first_time'] == '2021-01-11T21:00:00'
    assert source.receipt()['feature_request_count'] == source.receipt()['request_count'] == 1


@pytest.mark.parametrize('change', ['unknown_contract', 'bad_date', 'bad_snapshot', 'guard', 'parity', 'zero_quantity', 'multiple_positions', 'future_bar'])
def test_invalid_current_state_fails_instead_of_defaulting_to_hold(tmp_path, change):
    config, row, _ = setup_source(tmp_path); source = load('stage055_current_late_session').LateSessionSource(**config)
    if change == 'unknown_contract': row['actual_positions'] = {'jm9999.DCE': 2}
    elif change == 'bad_date': row['date'] = '2021-01-09'
    elif change == 'bad_snapshot': row['bar']['close_price'] += 1
    elif change == 'guard': source.guards.add(('jm2105.DCE', row['date']))
    elif change == 'parity':
        source._load_contract('jm2105.DCE'); source.contracts['jm2105.DCE'][2][row['date']] = False
    elif change == 'zero_quantity': row['actual_positions']['jm2105.DCE'] = 0
    elif change == 'multiple_positions': row['actual_positions']['jm2109.DCE'] = 1
    else: row['bar']['datetime'] = '2021-01-12T00:00:00'
    with pytest.raises((RuntimeError, ValueError)):
        source.features(row)


def test_cached_feature_source_drift_is_rejected(tmp_path):
    config, row, _ = setup_source(tmp_path); source = load('stage055_current_late_session').LateSessionSource(**config)
    source.features(row)
    with (config['cache'] / 'minutes.csv').open('a') as stream: stream.write('\n')
    with pytest.raises(RuntimeError, match='changed'): source.verify_used_inputs()


def test_policy_and_parent_recalculate_all_eleven_inputs_from_current_state(tmp_path, monkeypatch):
    config, row, book = setup_source(tmp_path); module = load('stage055_current_late_session')
    source = module.LateSessionSource(**config); policy_module = module.bind_policy(source)
    monkeypatch.setattr(policy_module.load('stage033_holding_observer'), 'snapshot', lambda strategy, bars: [copy.deepcopy(row)])
    monkeypatch.setattr(policy_module.load('stage042_canonical_inventory'), 'current_inventory', lambda strategy: copy.deepcopy(book))
    seen = []
    def predict(day, product, features):
        seen.append(copy.deepcopy(features))
        return {'cutoff': '2021-01-01', 'status': 'predicted', 'exit': True, 'return_marginal': -.1, 'drawdown_marginal': -.2}
    policy = policy_module.HoldingPolicy(SimpleNamespace(predict_holding=predict))
    assert list(policy(SimpleNamespace(estimated_equity=150000), {})) == [(row, book)]
    assert len(seen[0]) == 11 and seen[0]['late_volume_fraction_30m'] == .75
    assert seen[0]['directional_unrealized_return'] == pytest.approx(.19)
    parent = module.LateSessionSource(**config)
    audit = module.bind_policy(parent).validate_transcript(policy.states, policy.decisions, {row['date']: book}, predict)
    assert audit['decision_count'] == 1 and parent.receipt() == source.receipt()
    policy.decisions[0]['features']['late_volume_fraction_30m'] = .5
    with pytest.raises(ValueError, match='transcript_mismatch'):
        module.bind_policy(module.LateSessionSource(**config)).validate_transcript(policy.states, policy.decisions, {row['date']: book}, predict)


def test_non_eligible_state_does_not_request_minutes_or_predict(tmp_path):
    config, row, book = setup_source(tmp_path); source = load('stage055_current_late_session').LateSessionSource(**config)
    row['active_orders'] = [{}]
    policy = load('stage055_current_late_session').bind_policy(source)
    row['state_status'] = policy.load('stage033_holding_observer').classify(row)
    def denied(*args): raise AssertionError('ineligible state predicted')
    assert policy.decision(row, book, 150000., denied) is None
    assert source.receipt()['feature_request_count'] == 0


def test_bootstrap_import_is_cold_safe():
    import subprocess
    import sys

    assert TOOL.exists(), 'current late-session provider is not implemented'
    code = f'import runpy,sys; runpy.run_path({str(TOOL)!r}); assert not ({{"numpy","pandas","xgboost","vnpy"}} & set(sys.modules))'
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_cold_os_sandbox_raw_current_minutes_drive_registered_eleven_input_models(tmp_path):
    import subprocess
    import sys

    config, row, book = setup_source(tmp_path)
    models = load('stage044_holding_models')
    spec = json.loads((ROOT / 'artifacts/stage052_late_session_features/candidate_spec.json').read_text())
    data = pd.DataFrame([{**{key: i / 60 for key in spec['features']}, 'observation_id': f'synth-{i}',
        'root_id': f'root-{i}', 'date': '2020-01-02', 'label_end_date': '2020-01-03', 'label_status': 'verified',
        'product_vt_symbol': 'jm.DCE', 'vt_symbol': 'jm2105.DCE',
        'return_marginal': -1 - i / 100, 'drawdown_marginal': -2 - i / 100} for i in range(60)])
    bundle = models.fit_month(data, '2021-01-01', spec); directory = tmp_path / 'models/2021-01-01'
    sha = models.save_bundle(bundle, directory, spec)
    module = load('stage054_late_session_consumption'); parent = module.load('stage049_holding_full_replay')
    _, base, runner = parent.configured(123, '1' * 64)
    p = runner.load_metadata_preflight_module().load_preflight_module()
    paths = p.prepare_worker_root(tmp_path / 'cold'); p.write_sandbox_profile(paths['profile'], paths['worker_root'])
    setup = {k: str(v) if isinstance(v, Path) else v for k, v in config.items()}
    code = '\n'.join([
        'import runpy,sys,json; from pathlib import Path; from types import SimpleNamespace',
        f'm=SimpleNamespace(**runpy.run_path({str(ROOT / "tools/stage049_holding_full_replay.py")!r}))',
        "batch,base,runner=m.configured(123,'" + '1' * 64 + "')",
        'p=runner.load_metadata_preflight_module().load_preflight_module()',
        f'p._validate_worker_bootstrap(Path({str(paths["runtime"])!r}))',
        f'p.prove_external_write_denied(Path({str(tmp_path / "outside_probe")!r}))',
        'sys.path.extend([str(p.python_site_packages()),str(m.WORKSPACE)])',
        f'late=SimpleNamespace(**runpy.run_path({str(TOOL)!r}))',
        "factory=m.load('stage054_late_session_consumption').holding_guard_class",
        f'guard=factory(p,base.load_stage003())((Path({str(paths["worker_root"])!r}),),registry={{"2021-01-01":{{"root":{str(directory)!r},"metadata_sha256":{sha!r}}}}},spec={spec!r})',
        'guard.assert_no_sensitive_modules_loaded()',
        'with p.NetworkBlock(),guard:',
        f' source=late.LateSessionSource(**{setup!r})',
        f' result=late.bind_policy(source).decision({row!r},{book!r},150000.,guard.predict_holding)',
        ' source.verify_used_inputs()',
        'assert result["prediction"]["exit"] is True and len(result["features"])==11',
        'assert result["features"]["late_volume_fraction_30m"]==.75',
        'assert source.receipt()["feature_request_count"]==1 and source.request_count==0',
        'assert not any(guard.counters.values()) and guard.formal_replay_call_count==0',
        'print(json.dumps(guard.xgboost_receipt()))'])
    result = subprocess.run(['/usr/bin/sandbox-exec', '-f', str(paths['profile']), str(Path(sys.executable).resolve()),
        '-I', '-S', '-B', '-c', code], cwd=paths['runtime'], env=p.expected_worker_environment(paths['runtime']),
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['native_model_load_count'] == 2
