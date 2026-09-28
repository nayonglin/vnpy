import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


PATH = Path(__file__).resolve().parents[1] / "tools/stage002_unfilled_trace.py"


def module():
    assert PATH.exists(), "trace implementation missing"
    spec = importlib.util.spec_from_file_location("unfilled_trace_test", PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_trace_preserves_inherited_method_and_return_value():
    m = module()
    class Parent:
        def on_bars(self, bars):
            self.calls += 1
            return 17
    class Strategy(Parent):
        pass
    strategy = Strategy()
    strategy.calls = 0
    strategy.strategy_engine = SimpleNamespace(datetime="2020-05-11 00:00:00", limit_orders={}, active_limit_orders={})
    strategy.states = {}
    strategy.target_data = {}
    strategy.pos_data = {}
    rows = []
    restore = m.install_trace(Strategy, rows)
    assert strategy.on_bars({}) == 17
    assert strategy.calls == 1
    assert len(rows) == 2
    restore()
    assert "on_bars" not in Strategy.__dict__
    assert strategy.on_bars({}) == 17
    assert len(rows) == 2


def test_trace_does_not_swallow_errors_and_ignores_other_dates():
    m = module()
    class Strategy:
        def on_bars(self, bars):
            raise ValueError("original")
    original = Strategy.on_bars
    s = Strategy()
    s.strategy_engine = SimpleNamespace(datetime="2020-04-01")
    rows = []
    restore = m.install_trace(Strategy, rows)
    try:
        s.on_bars({})
        assert False, "expected original error"
    except ValueError as exc:
        assert str(exc) == "original"
    finally:
        restore()
    assert rows == []
    assert Strategy.on_bars is original


def test_worker_configuration_does_not_import_site_packages_before_bootstrap():
    code = ("import runpy; m=runpy.run_path(" + repr(str(PATH)) + "); "
            "m['configured']([]); print('stdlib_bootstrap_ready')")
    result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "stdlib_bootstrap_ready" in result.stdout
