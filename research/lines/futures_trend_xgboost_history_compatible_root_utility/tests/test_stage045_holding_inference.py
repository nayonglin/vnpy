import importlib.util
import json
import socket
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/stage045_holding_inference.py'


def load(path):
    spec = importlib.util.spec_from_file_location('inference_test045_' + path.stem, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


@pytest.fixture
def setup(tmp_path):
    models = load(ROOT / 'tools/stage044_holding_models.py')
    baseline = load(ROOT.parent / 'futures_trend_xgboost_formal_signal_marginal_utility_v4/tools/stage003_frozen_baseline_event_qualification.py')
    spec = json.loads((ROOT / 'artifacts/stage040_holding_panel/model_spec.json').read_text())
    data = pd.DataFrame([{**{key: i / 60 for key in spec['features']}, 'observation_id': f'observation-{i}',
        'root_id': f'root-{i}', 'date': '2020-01-02', 'label_end_date': '2020-01-03', 'label_status': 'verified',
        'product_vt_symbol': 'sp.SHFE', 'vt_symbol': 'sp2006.SHFE',
        'return_marginal': -1 - i / 100, 'drawdown_marginal': -2 - i / 100} for i in range(60)])
    registry = {}
    for cutoff in ('2020-01-01', '2020-03-01'):
        bundle = models.fit_month(data, cutoff, spec)
        directory = tmp_path / 'models' / cutoff
        sha = models.save_bundle(bundle, directory, spec)
        registry[cutoff] = {'root': directory, 'metadata_sha256': sha}
    preflight = baseline.load_runner().load_metadata_preflight_module().load_preflight_module()
    features = {key: .2 for key in spec['features']}
    return {'models': models, 'baseline': baseline, 'preflight': preflight, 'features': features,
        'spec': spec, 'registry': registry, 'data': data, 'bundle': bundle, 'tmp_path': tmp_path}


def make_guard(setup):
    assert TOOL.exists(), 'holding inference adapter is not implemented'
    cls = load(TOOL).holding_guard_class(setup['preflight'], setup['baseline'])
    return cls((setup['tmp_path'],), registry=setup['registry'], spec=setup['spec'])


def test_current_holding_prediction_matches_roundtrip_and_loads_month_once(setup):
    guard = make_guard(setup)
    expected = setup['models'].predict_decision(setup['bundle'], '2020-03-04', 'sp.SHFE', setup['features'], setup['spec'])
    with setup['preflight'].NetworkBlock(), guard:
        assert guard.predict_holding('2020-03-04', 'sp.SHFE', setup['features']) == expected
        assert guard.predict_holding('2020-03-04', 'sp.SHFE', setup['features']) == expected
    receipt = guard.xgboost_receipt()
    assert expected['exit'] is True and not any(guard.counters.values())
    assert receipt['loaded_months'] == ['2020-03-01'] and receipt['native_model_load_count'] == 2
    assert receipt['decision_count'] == 2 and receipt['prediction_calls']['xgboost.core.inplace_predict'] == 4


def test_untrained_and_fixed_fu_do_not_load_native_models(setup):
    guard = make_guard(setup)
    with guard:
        assert guard.predict_holding('2020-01-15', 'sp.SHFE', setup['features'])['status'] == 'untrained'
        assert guard.predict_holding('2020-03-15', 'fu.SHFE', setup['features'])['status'] == 'fixed_fu'
    assert guard.xgboost_receipt()['native_model_load_count'] == 0


@pytest.mark.parametrize('change', ['missing', 'extra_future_label', 'observation_id', 'nan', 'bad_date', 'missing_month'])
def test_holding_input_is_current_complete_and_month_specific(setup, change):
    guard = make_guard(setup); features = setup['features'].copy(); day = '2020-03-04'
    if change == 'missing':
        del features[next(iter(features))]
    elif change in {'extra_future_label', 'observation_id'}:
        features[change] = 1.
    elif change == 'nan':
        features[next(iter(features))] = float('nan')
    elif change == 'bad_date':
        day = '20200304'
    else:
        day = '2020-04-04'
    with pytest.raises(RuntimeError):
        with guard:
            guard.predict_holding(day, 'sp.SHFE', features)
    assert guard.decision_count == 0


@pytest.mark.parametrize('name', ['metadata.json', 'return_marginal.ubj'])
def test_changed_model_cannot_be_used(setup, name):
    guard = make_guard(setup)
    with (setup['registry']['2020-03-01']['root'] / name).open('ab') as stream:
        stream.write(b'changed')
    with pytest.raises(RuntimeError, match='changed'):
        with guard:
            guard.predict_holding('2020-03-04', 'sp.SHFE', setup['features'])


@pytest.mark.parametrize('directory', ['stage040_holding_panel', 'stage041_holding_labels', 'stage041b_holding_labels',
    'stage042_holding_labels', 'stage041c_label_collection', 'stage043_label_collection',
    'stage044_holding_training/baseline_observation_predictions.csv'])
def test_holding_label_and_original_prediction_reads_are_denied(setup, directory):
    guard = make_guard(setup)
    path = ROOT / 'artifacts' / directory
    if path.suffix != '.csv':
        path /= 'forbidden.json'
    with pytest.raises(setup['preflight'].ImportPreflightError, match='holding_label'):
        with guard:
            path.read_bytes()
    assert guard.counters['label_value_read_count'] == 1


@pytest.mark.parametrize('operation', ['holding_fit_untrained', 'holding_fit_trained', 'xgb_fit', 'native_train',
    'native_save', 'direct_predict', 'other_load', 'set_param', 'ctp', 'network', 'outside_write', 'lr_predict'])
def test_existing_native_and_baseline_guards_and_new_training_gate_remain(setup, operation):
    import xgboost as xgb
    import joblib

    guard = make_guard(setup); p = setup['preflight']
    with pytest.raises(p.ImportPreflightError):
        with p.NetworkBlock(), guard:
            guard.predict_holding('2020-03-04', 'sp.SHFE', setup['features'])
            estimator = guard.bundles['2020-03-01']['heads']['return_marginal']['estimator']
            if operation.startswith('holding_fit'):
                setup['models'].fit_month(setup['data'], '2020-01-01' if operation.endswith('untrained') else '2020-03-01', setup['spec'])
            elif operation == 'xgb_fit':
                estimator.fit(pd.DataFrame([setup['features']]), [0])
            elif operation == 'native_train':
                xgb.core._LIB.XGBoosterUpdateOneIter(None, 0, None)
            elif operation == 'native_save':
                xgb.core._LIB.XGBoosterSaveModel(None, b'forbidden.ubj')
            elif operation == 'direct_predict':
                estimator.predict(pd.DataFrame([setup['features']]))
            elif operation == 'other_load':
                xgb.XGBRegressor().load_model(setup['registry']['2020-03-01']['root'] / 'return_marginal.ubj')
            elif operation == 'set_param':
                estimator.get_booster().set_param({'base_score': 10})
            elif operation == 'ctp':
                __import__('vnpy_ctp')
            elif operation == 'network':
                socket.create_connection(('example.com', 443))
            elif operation == 'outside_write':
                (setup['tmp_path'].parent / 'stage045_forbidden.txt').write_text('denied')
            else:
                joblib.load(setup['baseline'].MODEL).predict_proba([[0] * 19])
    if operation.startswith('holding_fit'):
        assert guard.counters['model_fit_count'] == 1


def test_profile_and_native_functions_restored_after_failure(setup):
    import sys
    import xgboost

    guard = make_guard(setup)
    profile = sys.getprofile(); native = xgboost.core._LIB.XGBoosterUpdateOneIter
    with pytest.raises(setup['preflight'].ImportPreflightError):
        with guard:
            setup['models'].fit_month(setup['data'], '2020-01-01', setup['spec'])
    assert sys.getprofile() is profile and xgboost.core._LIB.XGBoosterUpdateOneIter is native


def test_cold_os_sandbox_accepts_only_registered_holding_inference(setup):
    import subprocess
    import sys

    guard = make_guard(setup); p = setup['preflight']; tmp = setup['tmp_path']
    paths = p.prepare_worker_root(tmp / 'cold_worker')
    p.write_sandbox_profile(paths['profile'], paths['worker_root'])
    registry = {key: {**value, 'root': str(value['root'])} for key, value in setup['registry'].items()}
    code = '\n'.join([
        'import runpy,sys,json; from pathlib import Path; from types import SimpleNamespace',
        f"baseline=SimpleNamespace(**runpy.run_path({setup['baseline'].__file__!r}))",
        'p=baseline.load_runner().load_metadata_preflight_module().load_preflight_module()',
        f"p._validate_worker_bootstrap(Path({str(paths['runtime'])!r}))",
        f"p.prove_external_write_denied(Path({str(tmp / 'outside_probe')!r}))",
        'sys.path.extend([str(p.python_site_packages())])',
        f"factory=runpy.run_path({str(TOOL)!r})['holding_guard_class']",
        f"guard=factory(p,baseline)((Path({str(paths['worker_root'])!r}),),registry={registry!r},spec={setup['spec']!r})",
        'guard.assert_no_sensitive_modules_loaded()',
        'with p.NetworkBlock(),guard:',
        f" result=guard.predict_holding('2020-03-04','sp.SHFE',{setup['features']!r})",
        "assert result['exit'] is True and guard.decision_count==1 and not any(guard.counters.values())",
        'print(json.dumps(guard.xgboost_receipt()))'])
    result = subprocess.run(['/usr/bin/sandbox-exec', '-f', str(paths['profile']), str(Path(sys.executable).resolve()),
        '-I', '-S', '-B', '-c', code], cwd=paths['runtime'], env=p.expected_worker_environment(paths['runtime']),
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['native_model_load_count'] == 2
    assert not (tmp / 'outside_probe').exists()
