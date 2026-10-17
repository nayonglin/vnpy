"""Focused contracts: no account engine, causal real bars, exact demand keys."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import stage005_potential_signal_demand as module
except ImportError:
    module = None


class PotentialSignalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if module is not None:
            cls.runtime = module.load_runtime()

    def api(self):
        self.assertIsNotNone(module, "potential signal enumeration implementation is absent")
        return module

    def fixture(self, periods=45):
        self.api()
        pd = self.runtime["pd"]
        dates = pd.bdate_range("2020-01-06", periods=periods)
        rows = [dict(vt_symbol="rb2010.SHFE", datetime=d, open_price=100.+i,
                     high_price=101.+i, low_price=99.+i, close_price=100.+i,
                     volume=100., turnover=10000., open_interest=200.)
                for i, d in enumerate(dates)]
        mapping = {d.strftime("%Y-%m-%d"): {"rb.SHFE": "rb2010.SHFE"} for d in dates}
        strategy = module.make_indicator_object({"research_exact_array_manager_size": 41})
        strategy._generate_signal = lambda am, history: {"signal": "long_probe", "risk_mode": "regular"}
        return pd.DataFrame(rows), mapping, strategy

    def enumerate(self, frame, mapping, strategy):
        return module.enumerate_signals(frame, mapping, ["rb2010.SHFE"], strategy,
            start="2020-01-01", end="2026-10-14")

    def test_41_observation_boundary_and_non_main_history_are_preserved(self):
        frame, mapping, strategy = self.fixture()
        # Contract only becomes main after it has already accumulated 40 real bars.
        for d in list(mapping)[:40]:
            mapping[d] = {}
        events, diagnostics = self.enumerate(frame, mapping, strategy)
        self.assertEqual(events.iloc[0].signal_date, frame.iloc[40].datetime.strftime("%Y-%m-%d"))
        self.assertEqual(events.iloc[0].am_count, 41)
        self.assertEqual(events.iloc[0].history_first_close, 100.)
        self.assertEqual(events.iloc[0].history_last_close, 140.)
        self.assertEqual(diagnostics["am_final_counts"]["rb2010.SHFE"], 45)

    def test_missing_target_real_bar_never_uses_carry(self):
        frame, mapping, strategy = self.fixture()
        missing_day = frame.iloc[42].datetime
        frame.loc[42, "vt_symbol"] = "hc2010.SHFE"  # Global batch exists, target rb does not.
        events, diagnostics = module.enumerate_signals(frame, mapping,
            ["rb2010.SHFE", "hc2010.SHFE"], strategy, start="2020-01-01", end="2026-10-14")
        self.assertNotIn(missing_day.strftime("%Y-%m-%d"), set(events.signal_date))
        self.assertEqual(diagnostics["reasons"]["target_real_bar_missing"], 1)

    def test_orders_keep_signal_contract_and_use_next_global_batch(self):
        frame, mapping, strategy = self.fixture(44)
        signal_day = frame.iloc[40].datetime.strftime("%Y-%m-%d")
        next_day = frame.iloc[41].datetime.strftime("%Y-%m-%d")
        mapping[next_day] = {"rb.SHFE": "rb2101.SHFE"}
        events, _ = module.enumerate_signals(frame, mapping, ["rb2010.SHFE", "rb2101.SHFE"],
            strategy, start="2020-01-01", end="2026-10-14")
        event = events.loc[events.signal_date.eq(signal_day)].iloc[0]
        self.assertEqual(event.vt_symbol, "rb2010.SHFE")
        self.assertEqual(event.execution_trade_date, next_day)
        self.assertEqual(events.iloc[-1].event_status, "terminal_pending")

    def test_appending_future_bars_never_changes_earlier_potential_signals(self):
        frame, mapping, strategy = self.fixture(50)
        earlier, _ = self.enumerate(frame.iloc[:46], mapping, strategy)
        later, _ = self.enumerate(frame, mapping, strategy)
        # The final pending row gains its future execution date; prior rows cannot change.
        pd = self.runtime["pd"]
        compare = earlier.iloc[:-1]
        pd.testing.assert_frame_equal(compare, later.loc[later.signal_date.isin(compare.signal_date)].reset_index(drop=True))

    def test_weekly_unknown_falls_back_and_neutral_or_opposed_blocks(self):
        self.api()
        self.assertTrue(module.weekly_allows("long_case1a", False, 0))
        self.assertTrue(module.weekly_allows("long_case1a", True, 1))
        self.assertFalse(module.weekly_allows("long_case1a", True, -1))
        self.assertFalse(module.weekly_allows("short_case1a", True, 0))

    def test_duplicate_daily_contract_key_is_rejected(self):
        frame, mapping, strategy = self.fixture()
        pd = self.runtime["pd"]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.enumerate(pd.concat([frame, frame.iloc[[0]]], ignore_index=True), mapping, strategy)

    def test_friday_night_is_monday_session_and_missing_coverage_join_fails(self):
        self.api()
        pd = self.runtime["pd"]
        calendar = pd.to_datetime(["2020-05-15", "2020-05-18"])
        demand = pd.DataFrame([dict(vt_symbol="rb2010.SHFE", product_vt_symbol="rb.SHFE",
            execution_trade_date="2020-05-18", c0_allowed=True)])
        coverage = pd.DataFrame([dict(vt_symbol="rb2010.SHFE", date="2020-05-18",
            expected_minutes=345, available_minutes=345, missing_minutes=0, anchor_present=1,
            complete=1, local_candidate_paths=3)])
        sessions = module.join_session_coverage(demand, coverage, calendar)
        self.assertEqual(sessions.iloc[0].session_start, "2020-05-15T21:00:00")
        self.assertEqual(sessions.iloc[0].expected_minutes, 345)
        with self.assertRaisesRegex(ValueError, "coverage_join_missing"):
            module.join_session_coverage(demand, coverage.iloc[:0], calendar)

    def test_original_method_is_reused_without_strategy_initialization(self):
        self.api()
        cls = self.runtime["Strategy"]
        object_ = module.make_indicator_object({"ma_short": 5})
        self.assertIs(type(object_), cls)
        self.assertIs(object_._generate_signal.__func__, cls._generate_signal)
        self.assertFalse(hasattr(object_, "strategy_engine"))
        self.assertFalse(hasattr(object_, "states"))


if __name__ == "__main__":
    unittest.main()
