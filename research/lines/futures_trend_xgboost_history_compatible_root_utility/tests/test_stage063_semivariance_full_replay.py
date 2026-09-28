import importlib.util
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/stage063_semivariance_full_replay.py'


def module():
    assert TOOL.exists(), 'semivariance full replay is not implemented'
    spec = importlib.util.spec_from_file_location('test063', TOOL)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


@pytest.mark.parametrize('name', ['stage061_semivariance_consumption', 'stage062_current_semivariance', 'stage063_semivariance_full_replay'])
def test_bootstrap_is_cold_safe(name):
    module(); path = ROOT / 'tools' / (name + '.py')
    code = '\n'.join(['import runpy,sys', f'm=runpy.run_path({str(path)!r})',
        'if "adapted" in m: r=m["adapted"](); r.configured(123,m["MODEL_SHA"]); assert r.STAGE=="stage063_semivariance_full_replay"',
        'assert not ({"numpy","pandas","xgboost","vnpy"} & set(sys.modules))'])
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('method', ['catalog', 'freeze_inputs', 'run_parent'])
def test_only_fixed_semivariance_model_is_accepted(tmp_path, method):
    m = module().adapted(); m.OUTPUT = tmp_path / 'output'; m.FREEZE = tmp_path / 'freeze.json'
    with pytest.raises(RuntimeError, match='training_summary'): getattr(m, method)('0' * 64)
    assert not m.OUTPUT.exists() and not m.FREEZE.exists()


def test_original_close_gate_receives_current_semivariance_and_restores(tmp_path):
    m = module().adapted()
    spec = importlib.util.spec_from_file_location('fixture063', ROOT / 'tests/test_stage049_holding_full_replay.py')
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    fixture, strategy, guard, old_source = helper.prepared()
    class Source:
        def features(self, row): return {'favorable_semivariance_5m': .02, 'adverse_semivariance_5m': .01}
        def __call__(self, intent, day): return old_source(intent, day)
    original = guard.predict_holding
    def predict(day, product, features):
        assert len(features) == 11 and features['adverse_semivariance_5m'] == .01
        return original(day, product, features)
    guard.predict_holding = predict; old_load = m.load
    with m.install_holding(fixture.Strategy, fixture.Engine, guard, Source()) as state:
        strategy.on_bars(strategy.strategy_engine.bars)
        assert len(state['policy'].decisions) == len(state['gate']['intents']) == 1
    assert state['methods_restored'] is True and m.load is old_load


def test_new_dependencies_and_inherited_implementation_are_bound(monkeypatch):
    top = module(); m = top.adapted(); current = m.load('stage042_holding_labels')
    _, prior = current.adapted().configured()
    monkeypatch.setattr(prior, 'validate_frozen_input_contract', lambda *args: None)
    monkeypatch.setattr(prior, 'validate_current_input_manifest', lambda *args: None)
    monkeypatch.setattr(current, 'adapted', lambda: SimpleNamespace(configured=lambda: (None, prior)))
    monkeypatch.setattr(m, 'catalog', lambda sha: ({}, {}, {'files': []}))
    monkeypatch.setattr(m.load('stage044_holding_training'), 'check_versions', lambda spec: None)
    paths = set(m.collect_inputs(top.MODEL_SHA).values())
    for name in ('stage059_realized_semivariance_features', 'stage061_semivariance_consumption',
        'stage062_current_semivariance', 'stage063_semivariance_full_replay', 'stage056_late_session_full_replay',
        'stage049b_holding_full_replay', 'stage049_holding_full_replay'):
        assert ROOT / 'tools' / (name + '.py') in paths
        assert ROOT / 'tests' / ('test_' + name + '.py') in paths
    assert top.CONTRACT in paths and all(path.is_file() for path in paths)
    assert m.MODEL_OUTPUT == ROOT / 'artifacts/stage060_semivariance_training'
    assert Path(m.__file__) == TOOL and m.FREEZE.name == 'stage063_input_freeze.json'
