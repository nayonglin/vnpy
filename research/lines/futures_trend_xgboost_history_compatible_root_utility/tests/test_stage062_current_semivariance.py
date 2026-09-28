import copy
import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/stage062_current_semivariance.py'
EXTRA = ['favorable_semivariance_5m', 'adverse_semivariance_5m']


def load(name, folder='tools'):
    path = ROOT / folder / (name + '.py')
    assert path.exists(), 'current semivariance source is not implemented'
    spec = importlib.util.spec_from_file_location('test062_' + name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def test_raw_current_day_matches_literal_formula_and_direction_swap(tmp_path):
    config, row, _ = load('test_stage055_current_late_session', 'tests').setup_source(tmp_path)
    source = load('stage062_current_semivariance').SemivarianceSource(**config)
    values = source.features(row)
    expected = (math.log(102.) - math.log(101.)) ** 2 + (math.log(119.) - math.log(102.)) ** 2
    assert values == {EXTRA[0]: pytest.approx(expected, abs=1e-16), EXTRA[1]: 0.}
    row['actual_positions']['jm2105.DCE'] = -3
    assert source.features(row) == {EXTRA[0]: 0., EXTRA[1]: values[EXTRA[0]]}
    receipt = source.receipt(); assert receipt['feature_request_count'] == 2 and receipt['request_count'] == 0
    first = receipt['feature_records'][0]
    assert first['sample_count'] == 8 and first['day_minute_count'] == 40 and first['segment_count'] == 3
    assert first['first_minute'] == '2021-01-08T21:00:00' and first['asof_close'] == '2021-01-11T15:00:00'
    assert receipt['A_observation_table_used'] is False and receipt['source_global_coverage_complete'] is False
    assert source({'decision_date': row['date'], 'vt_symbol': 'jm2105.DCE', 'volume': 2}, '2021-01-12')['price'] == 103.
    source.verify_used_inputs()


@pytest.mark.parametrize('change', ['unknown_contract', 'bad_date', 'bad_snapshot', 'guard', 'parity',
    'zero_quantity', 'multiple_positions', 'future_bar', 'missing_minute', 'initial_zero'])
def test_source_failure_aborts_not_default_hold(tmp_path, change):
    config, row, _ = load('test_stage055_current_late_session', 'tests').setup_source(tmp_path)
    source = load('stage062_current_semivariance').SemivarianceSource(**config)
    if change == 'unknown_contract': row['actual_positions'] = {'jm9999.DCE': 2}
    elif change == 'bad_date': row['date'] = '2021-01-09'
    elif change == 'bad_snapshot': row['bar']['close_price'] += 1
    elif change == 'guard': source.guards.add(('jm2105.DCE', row['date']))
    elif change == 'zero_quantity': row['actual_positions']['jm2105.DCE'] = 0
    elif change == 'multiple_positions': row['actual_positions']['jm2109.DCE'] = 1
    elif change == 'future_bar': row['bar']['datetime'] = '2021-01-12T00:00:00'
    else:
        source._load_contract('jm2105.DCE'); frame, expected, parity = source.contracts['jm2105.DCE']
        if change == 'parity': parity[row['date']] = False
        elif change == 'initial_zero': frame.loc[frame.bar_date.eq(row['date']).idxmax(), 'volume'] = 0.
        else: source.contracts['jm2105.DCE'] = (frame.drop(frame.index[frame.bar_date.eq(row['date'])][0]), expected, parity)
    with pytest.raises((RuntimeError, ValueError)): source.features(row)
    assert not source.feature_records


def test_worker_and_parent_current_features_reconstruct_and_detect_tampering(tmp_path, monkeypatch):
    config, row, book = load('test_stage055_current_late_session', 'tests').setup_source(tmp_path)
    m = load('stage062_current_semivariance'); source = m.SemivarianceSource(**config); policy_module = m.bind_policy(source)
    monkeypatch.setattr(policy_module.load('stage033_holding_observer'), 'snapshot', lambda *args: [copy.deepcopy(row)])
    monkeypatch.setattr(policy_module.load('stage042_canonical_inventory'), 'current_inventory', lambda *args: copy.deepcopy(book))
    seen = []
    def predict(day, product, features):
        seen.append(features.copy())
        return {'cutoff': '2021-01-01', 'status': 'predicted', 'exit': True, 'return_marginal': -.1, 'drawdown_marginal': -.2}
    policy = policy_module.HoldingPolicy(SimpleNamespace(predict_holding=predict))
    assert list(policy(SimpleNamespace(estimated_equity=150000), {})) == [(row, book)]
    assert len(seen[0]) == 11 and seen[0][EXTRA[0]] > 0 and seen[0][EXTRA[1]] == 0
    parent = m.SemivarianceSource(**config)
    audit = m.bind_policy(parent).validate_transcript(policy.states, policy.decisions, {row['date']: book}, predict)
    assert audit['decision_count'] == 1 and parent.receipt() == source.receipt()
    policy.decisions[0]['features'][EXTRA[0]] += .01
    with pytest.raises(ValueError, match='transcript_mismatch'):
        m.bind_policy(m.SemivarianceSource(**config)).validate_transcript(policy.states, policy.decisions, {row['date']: book}, predict)


def test_cached_source_drift_and_ineligible_state(tmp_path):
    config, row, book = load('test_stage055_current_late_session', 'tests').setup_source(tmp_path)
    m = load('stage062_current_semivariance'); source = m.SemivarianceSource(**config); policy = m.bind_policy(source)
    row['active_orders'] = [{}]; row['state_status'] = policy.load('stage033_holding_observer').classify(row)
    def denied(*args): raise AssertionError('ineligible prediction')
    assert policy.decision(row, book, 150000., denied) is None
    assert not source.feature_records
    source.features(row)
    with (config['cache'] / 'minutes.csv').open('a') as stream: stream.write('\n')
    with pytest.raises(RuntimeError, match='changed'): source.verify_used_inputs()


def test_cold_os_sandbox_current_minutes_drive_frozen_native_interface(tmp_path):
    import json
    import subprocess
    import sys
    import pandas as pd

    config, row, book = load('test_stage055_current_late_session', 'tests').setup_source(tmp_path)
    models = load('stage044_holding_models')
    spec = json.loads((ROOT / 'artifacts/stage059_realized_semivariance_features/candidate_spec.json').read_text())
    data = pd.DataFrame([{**{key: i / 60 for key in spec['features']}, 'observation_id': f'synth-{i}',
        'root_id': f'root-{i}', 'date': '2020-01-02', 'label_end_date': '2020-01-03', 'label_status': 'verified',
        'product_vt_symbol': 'jm.DCE', 'vt_symbol': 'jm2105.DCE',
        'return_marginal': -1 - i / 100, 'drawdown_marginal': -2 - i / 100} for i in range(60)])
    bundle = models.fit_month(data, '2021-01-01', spec); directory = tmp_path / 'models/2021-01-01'
    sha = models.save_bundle(bundle, directory, spec)
    top = load('stage063_semivariance_full_replay'); runner = top.adapted()
    _, _, core = runner.configured(123, top.MODEL_SHA)
    p = core.load_metadata_preflight_module().load_preflight_module()
    paths = p.prepare_worker_root(tmp_path / 'cold'); p.write_sandbox_profile(paths['profile'], paths['worker_root'])
    setup = {key: str(value) if isinstance(value, Path) else value for key, value in config.items()}
    code = '\n'.join(['import runpy,sys,json; from pathlib import Path; from types import SimpleNamespace',
        f'top=runpy.run_path({str(ROOT / "tools/stage063_semivariance_full_replay.py")!r}); m=top["adapted"]()',
        'batch,base,runner=m.configured(123,top["MODEL_SHA"])',
        'p=runner.load_metadata_preflight_module().load_preflight_module()',
        f'p._validate_worker_bootstrap(Path({str(paths["runtime"])!r}))',
        f'p.prove_external_write_denied(Path({str(tmp_path / "outside_probe")!r}))',
        'sys.path.extend([str(p.python_site_packages()),str(m.WORKSPACE)])',
        'source_module=top["load"]("stage062_current_semivariance")',
        'factory=top["load"]("stage061_semivariance_consumption").holding_guard_class',
        f'guard=factory(p,base.load_stage003())((Path({str(paths["worker_root"])!r}),),registry={{"2021-01-01":{{"root":{str(directory)!r},"metadata_sha256":{sha!r}}}}},spec={spec!r})',
        'guard.assert_no_sensitive_modules_loaded()',
        'with p.NetworkBlock(),guard:',
        f' source=source_module.SemivarianceSource(**{setup!r})',
        f' result=source_module.bind_policy(source).decision({row!r},{book!r},150000.,guard.predict_holding)',
        ' source.verify_used_inputs()',
        'assert result["prediction"]["exit"] is True and len(result["features"])==11',
        'assert result["features"]["favorable_semivariance_5m"]>0 and result["features"]["adverse_semivariance_5m"]==0',
        'assert source.receipt()["feature_request_count"]==1 and source.request_count==0',
        'assert not any(guard.counters.values()) and guard.formal_replay_call_count==0',
        'print(json.dumps(guard.xgboost_receipt()))'])
    result = subprocess.run(['/usr/bin/sandbox-exec', '-f', str(paths['profile']), str(Path(sys.executable).resolve()),
        '-I', '-S', '-B', '-c', code], cwd=paths['runtime'], env=p.expected_worker_environment(paths['runtime']),
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['native_model_load_count'] == 2
