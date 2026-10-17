"""用冻结 vendor 的真实吞异常路径验证离线研究入口必须失败。"""
import importlib.util
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location('stage249_replay', Path(__file__).with_name('stage249_historical_replay.py'))
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)
from vnpy_portfoliostrategy.backtesting import BacktestingEngine


class FailureGateTests(unittest.TestCase):
    def make_engine(self, phase, exception):
        class ProbeEngine(BacktestingEngine):
            def new_bars(self, dt):
                self.datetime = dt
                if (phase == 'init' and not self.strategy.trading) or (phase == 'trading' and self.strategy.trading):
                    raise exception
        engine = object.__new__(ProbeEngine)
        engine.strategy = SimpleNamespace(on_init=lambda: None, on_start=lambda: None,
                                          trading=False, estimated_equity=150000, settled_balance=150000)
        engine.dts = {datetime(2026, 10, 13), datetime(2026, 10, 14)}
        engine.datetime = None
        engine.days = 0
        engine.messages = []
        engine.output = engine.messages.append
        return engine

    def assert_blocked(self, phase, exception):
        engine = self.make_engine(phase, exception)
        cls = type(engine)
        original = cls.new_bars
        with self.assertRaisesRegex(RuntimeError, 'backtest_bar_failed') as caught:
            with replay.capture_execution_proxy_usage(cls):
                engine.run_backtesting()
                if phase == 'trading':
                    self.assertEqual(engine.datetime, datetime(2026, 10, 14))
        self.assertIs(caught.exception.__cause__, exception)
        self.assertIs(cls.new_bars, original)
        self.assertNotIn('calculate_result', cls.__dict__)
        self.assertTrue(any('Traceback' in str(message) for message in engine.messages))

    def test_last_day_swallowed_failure_is_not_success(self):
        self.assert_blocked('trading', ValueError('last_day_failure'))

    def test_empty_exception_is_not_success(self):
        self.assert_blocked('trading', AssertionError())

    def test_warmup_swallowed_failure_is_not_success(self):
        self.assert_blocked('init', ValueError('warmup_failure'))

    def test_success_restores_methods(self):
        engine = self.make_engine('none', None)
        cls = type(engine)
        original = cls.new_bars
        with replay.capture_execution_proxy_usage(cls) as captured:
            engine.run_backtesting()
        self.assertIs(cls.new_bars, original)
        self.assertNotIn('calculate_result', cls.__dict__)
        self.assertEqual(len(captured['equity']), 1)


if __name__ == '__main__':
    unittest.main()
