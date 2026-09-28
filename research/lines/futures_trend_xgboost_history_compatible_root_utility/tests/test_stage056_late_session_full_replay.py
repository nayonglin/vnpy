from contextlib import contextmanager
import importlib.util
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/stage056_late_session_full_replay.py'


def module():
    assert TOOL.exists(), 'late-session full replay is not implemented'
    spec = importlib.util.spec_from_file_location('test056', TOOL)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def test_cold_configuration_binds_new_stage_without_loading_sensitive_modules():
    m = module(); code = '\n'.join([
        'import runpy,sys', f'm=runpy.run_path({str(TOOL)!r}); r=m["adapted"]()',
        'r.configured(123,m["MODEL_SHA"])',
        'assert r.STAGE=="stage056_late_session_full_replay"',
        'assert not ({"numpy","pandas","xgboost","vnpy"} & set(sys.modules))'])
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('method', ['catalog', 'freeze_inputs', 'run_parent'])
def test_nonfixed_model_sha_rejected_before_any_new_output(tmp_path, method):
    runner = module().adapted(); runner.OUTPUT = tmp_path / 'output'; runner.FREEZE = tmp_path / 'freeze.json'
    with pytest.raises(RuntimeError, match='training_summary'):
        getattr(runner, method)('0' * 64)
    assert not runner.OUTPUT.exists() and not runner.FREEZE.exists()


def prepared():
    m = module(); fixture = m.load('stage049_holding_full_replay').load('stage047_current_holding_policy')
    spec = importlib.util.spec_from_file_location('fixture056', ROOT / 'tests/test_stage049_holding_full_replay.py')
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    f, strategy, guard, old_provider = value.prepared()
    class Provider:
        def __init__(self): self.rows = []
        def features(self, row):
            self.rows.append(row.copy())
            return {'directional_late_return_30m': -.05, 'late_volume_fraction_30m': .2}
        def __call__(self, intent, day): return old_provider(intent, day)
    source = Provider(); original = guard.predict_holding
    def predict(day, product, features):
        assert len(features) == 11 and features['directional_late_return_30m'] == -.05
        return original(day, product, features)
    guard.predict_holding = predict
    return f, strategy, guard, source


def test_original_close_gate_uses_current_source_and_restores_methods():
    runner = module().adapted(); fixture, strategy, guard, source = prepared(); old_load = runner.load
    methods = (fixture.Strategy.on_bars, fixture.Strategy.update_trade, fixture.Engine._resolve_trade_price)
    with runner.install_holding(fixture.Strategy, fixture.Engine, guard, source) as state:
        strategy.on_bars(strategy.strategy_engine.bars)
        assert len(source.rows) == len(state['policy'].decisions) == len(state['gate']['intents']) == 1
        assert len(state['policy'].decisions[0]['features']) == 11
    assert state['methods_restored'] is True and runner.load is old_load
    assert methods == (fixture.Strategy.on_bars, fixture.Strategy.update_trade, fixture.Engine._resolve_trade_price)


def test_source_failure_is_preserved_and_does_not_silently_hold():
    runner = module().adapted(); fixture, strategy, guard, source = prepared(); old_load = runner.load
    def denied(row): raise RuntimeError('unqualified_current_minutes')
    source.features = denied
    with runner.install_holding(fixture.Strategy, fixture.Engine, guard, source) as state:
        with pytest.raises(RuntimeError, match='unqualified_current_minutes'): strategy.on_bars(strategy.strategy_engine.bars)
        assert 'unqualified_current_minutes' in state['callback_failure']
        assert not state['gate']['intents']
    assert state['methods_restored'] is True and runner.load is old_load


def test_new_tools_contracts_and_original_dependencies_are_bound(monkeypatch):
    top = module(); m = top.adapted(); current = m.load('stage042_holding_labels')
    _, prior = current.adapted().configured()
    monkeypatch.setattr(prior, 'validate_frozen_input_contract', lambda *args: None)
    monkeypatch.setattr(prior, 'validate_current_input_manifest', lambda *args: None)
    monkeypatch.setattr(current, 'adapted', lambda: SimpleNamespace(configured=lambda: (None, prior)))
    monkeypatch.setattr(m, 'catalog', lambda sha: ({}, {}, {'files': []}))
    monkeypatch.setattr(m.load('stage044_holding_training'), 'check_versions', lambda spec: None)
    paths = set(m.collect_inputs(top.MODEL_SHA).values())
    for name in ('stage054_late_session_consumption', 'stage055_current_late_session', 'stage056_late_session_full_replay',
            'stage052_late_session_features', 'stage049_holding_full_replay', 'stage049b_holding_full_replay'):
        assert ROOT / 'tools' / (name + '.py') in paths
        assert ROOT / 'tests' / ('test_' + name + '.py') in paths
    assert top.CONTRACT in paths and all(p.is_file() for p in paths)


def test_parent_feature_and_action_audits_use_the_same_source_instance(monkeypatch):
    top = module(); runner = top.adapted(); seen = []
    source = object()
    guard = SimpleNamespace(predict_holding=object(), counters={}, xgboost_receipt=lambda: {'decision_count': 3})
    @contextmanager
    def managed(): yield guard
    network = managed()
    policy = SimpleNamespace(validate_transcript=lambda states, decisions, books, predict:
        seen.append(('features', states, decisions, books, predict)) or {'decision_count': 3, 'exit_count': 1})
    monkeypatch.setattr(top.load('stage055_current_late_session'), 'bind_policy', lambda p: policy if p is source else None)
    trace = {'states': ['current_state'], 'decisions': ['current_decision']}
    result = top.audit_policy(trace, {'current_day': 'book'}, source, network, managed())
    assert result == {'decision_count': 3, 'exit_count': 1}
    assert seen == [('features', ['current_state'], ['current_decision'], {'current_day': 'book'}, guard.predict_holding)]
