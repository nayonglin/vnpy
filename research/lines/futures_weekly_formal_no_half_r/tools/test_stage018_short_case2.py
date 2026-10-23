"""Behavior tests for allowing both 3MA short entry cases; no financial replay."""
from datetime import datetime, timedelta
import unittest
import numpy as np
import pandas as pd
from test_stage008_three_ma import ControlledMacdHarness, bar
from stage014_no_macd import no_macd_weekly_strategy_class
try:
    from stage018_short_case2 import short_case2_weekly_strategy_class
except ImportError:
    short_case2_weekly_strategy_class = None

class ShortCase2Tests(unittest.TestCase):
    def strategy(self):
        self.assertTrue(callable(short_case2_weekly_strategy_class), 'short-case2 implementation missing')
        return short_case2_weekly_strategy_class(ControlledMacdHarness, {})()
    def fill(self, s, close):
        am = s.ams['X.TEST']
        for i, value in enumerate(close):
            am.inner.update_bar(bar((datetime(2019, 1, 1)+timedelta(days=i)).isoformat(), value))
        am.fresh = True
        return am, s._build_history_df(am)
    def history(self, close):
        x = np.asarray(close, dtype=float)
        return pd.DataFrame(dict(open=x, high=x+2, low=x-2, close=x, volume=x*0+1, open_interest=x*0+100))
    def test_generated_10_20_death_cross_becomes_eligible(self):
        close = 400-np.array([200.]*21+[90.]*19+[200.])
        old = no_macd_weekly_strategy_class(ControlledMacdHarness, {})()
        am, h = self.fill(old, close)
        signal = old._generate_signal(am, h)['signal']
        self.assertEqual(signal, 'short_case2')
        self.assertFalse(old._can_open_short_signal(signal))
        s = self.strategy(); am, h = self.fill(s, close)
        result = s._generate_signal(am, h)
        self.assertEqual(result['signal'], signal)
        self.assertTrue(result['bearish_alignment'])
        self.assertTrue(s._can_open_short_signal(result['signal']))
        self.assertEqual(s.research_macd_call_attempts, 0)
    def test_only_two_declared_short_cases_are_eligible(self):
        s = self.strategy()
        for signal in ['short_case1a', 'short_case2']:
            self.assertTrue(s._can_open_short_signal(signal))
        for signal in ['', 'short_case3', 'short_rollover', 'long_case1a', 'long_case2', 'short_case20']:
            self.assertFalse(s._can_open_short_signal(signal))
    def test_native_entry_retains_zero_size_and_direction_guards(self):
        s = self.strategy()
        self.assertTrue(s._is_native_openable_candidate('short_case2', 'short', 1))
        self.assertFalse(s._is_native_openable_candidate('short_case2', 'short', 0))
        s.short_entry_enabled = False
        self.assertFalse(s._is_native_openable_candidate('short_case2', 'short', 1))
        self.assertTrue(s._is_native_openable_candidate('long_case2', 'long', 1))
    def test_ma40_is_not_consumed_in_entries_or_rollover(self):
        s = self.strategy()
        class Poison:
            def __int__(self): raise AssertionError('MA40 consumed')
            def __index__(self): raise AssertionError('MA40 consumed')
            def __float__(self): raise AssertionError('MA40 consumed')
        s.ma_extra_long = Poison()
        close = 400-np.array([200.]*21+[90.]*19+[200.])
        am, h = self.fill(s, close)
        self.assertEqual(s._generate_signal(am, h)['signal'], 'short_case2')
        trend = self.history(200.-np.arange(25))
        self.assertTrue(s._is_simple_ma_trend(trend, 'short', 3))
        roll = s._rollover_shape_continuation_snapshot('short', trend.tail(20))
        self.assertEqual(roll['allowed'], 1)
        self.assertTrue(np.isnan(roll['ma_extra_long_value']))
        self.assertTrue(s._rollover_reopen_allowed('short', trend, dict(bearish_alignment=True)))
    def test_fresh_week_and_other_filters_still_required(self):
        s = self.strategy(); am, h = self.fill(s, 400-np.array([200.]*21+[90.]*19+[200.]))
        am.fresh = False
        self.assertEqual(s._generate_signal(am, h)['signal'], '')
        am.fresh = True; s.filter_allows = False
        self.assertEqual(s._generate_signal(am, h)['signal'], '')
    def test_real_formal_risk_and_exit_methods_are_inherited(self):
        self.assertTrue(callable(short_case2_weekly_strategy_class), 'short-case2 implementation missing')
        from analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine import QmtRollPortfolioStrategyStage847C9StopRetry as Base
        New = short_case2_weekly_strategy_class(Base, {})
        self.assertTrue(New.research_macd_disabled)
        for name in ['_process_rsi_partial_exit', '_entry_stop_price', '_process_layer_stops', '_handle_rollover', '_calculate_entry_sizing', '_passes_entry_filters']:
            self.assertIs(getattr(New, name), getattr(Base, name))
        self.assertEqual(set(k for k in New.__dict__ if callable(New.__dict__[k])), {'_can_open_short_signal'})

if __name__ == '__main__': unittest.main()
