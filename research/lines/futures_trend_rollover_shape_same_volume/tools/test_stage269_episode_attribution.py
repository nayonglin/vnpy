"""Synthetic joins and censoring tests for Stage269 episode descriptions."""

from __future__ import annotations

import importlib
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

try:
    ep = importlib.import_module("stage269_episode_attribution")
except ModuleNotFoundError:
    ep = None


class EpisodeContractTests(unittest.TestCase):
    def function(self, name):
        function = getattr(ep, name, None)
        self.assertTrue(callable(function), f"missing episode behavior: {name}")
        return function

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        (self.base / "statistics_audit").mkdir()
        self.calendar = pd.to_datetime(["2024-01-05", "2024-01-08", "2024-01-09", "2024-01-10", "2024-01-11"])
        self.market = pd.DataFrame({"date": self.calendar, "market_er60": [.1, .2, .3, .4, .5], "regime": ["low", "mid", "high", "high", "high"]})
        closed = pd.DataFrame({"root_id": [1, 2], "entry_date": ["2024-01-08", "2024-01-09"], "exit_date": ["2024-01-09", "2024-01-10"], "net_pnl": [30., 0.], "cost": [2., 1.], "cycle_count": [2, 1]})
        opened = pd.DataFrame({"root_id": [3], "closed_cycle_pnl": [-10.], "remaining_cycle_net_mtm": [4.], "net_mtm": [-6.]})
        cycles = pd.DataFrame({
            "root_id": [1, 1, 2, 3], "first_id": [1, 11, 2, 3],
            "first_trade_id": ["T1", "T11", "T2", "T3"], "is_retry": [False, True, False, False],
            "entry_date": ["2024-01-08", "2024-01-08", "2024-01-09", "2024-01-10"],
            "signal_date": ["2024-01-05", "2024-01-05", "2024-01-08", "2024-01-09"],
            "opened_volume": [2., 2., 3., 4.], "product": ["a.DCE"] * 4,
            "direction": ["long"] * 4, "net_pnl": [-10., 40., 0., -10.],
        })
        positions = pd.DataFrame({
            "root_id": [3], "first_id": [33], "first_trade_id": ["T33"], "is_retry": [True],
            "entry_date": ["2024-01-10"], "signal_date": ["2024-01-09"], "opened_volume": [4.],
            "product": ["a.DCE"], "direction": ["long"], "net_mtm": [4.],
        })
        trades = pd.DataFrame({
            "trade_id": ["T1", "T11", "T2", "T3", "T33"],
            "order_id": ["O4", "O11", "O2", "O3", "O33"], "volume": [2., 2., 3., 4., 4.],
            "datetime": ["2024-01-05 21:00:00+08:00", "2024-01-05 22:00:00+08:00", "2024-01-08 21:00:00+08:00", "2024-01-09 21:00:00+08:00", "2024-01-10 10:00:00+08:00"],
            "trading_date": ["2024-01-08", "2024-01-08", "2024-01-09", "2024-01-10", "2024-01-10"],
        })
        # The decoy T1 risk would be selected by the trade-id-as-order-id bug.
        risks = pd.DataFrame({"signal_order_id": ["O4", "T1", "O3"], "risk_per_contract": [10., 999., 5.], "actual_risk_amount": [20., 1998., 20.]})
        events = pd.DataFrame({"trade_id": ["T1", "T22", "T3"], "first_stop_time": ["2024-01-05T22:00:00", "2024-01-08T22:00:00", "2024-01-10T09:00:00"]})
        links = pd.DataFrame({"root_id": [1, 3], "retry_id": [11, 33], "order_id": ["O11", "O33"]})
        for rel, frame in {
            "statistics_audit/complete_episodes.csv": closed, "statistics_audit/open_episodes.csv": opened,
            "statistics_audit/complete_cycles.csv": cycles, "statistics_audit/open_positions.csv": positions,
            "trades.csv": trades, "entry_risk.csv": risks, "stop_retry_events.csv": events,
            "statistics_audit/retry_links.csv": links,
        }.items():
            frame.to_csv(self.base / rel, index=False)

    def table(self):
        return self.function("build_episode_table")(self.base, self.market, self.calendar)

    def test_first_actual_fill_risk_joins_through_order_id(self):
        out = self.table().set_index("root_id")
        self.assertEqual(out.loc[1, "first_trade_id"], "T1")
        self.assertEqual(out.loc[1, "signal_order_id"], "O4")
        self.assertEqual(out.loc[1, "initial_risk"], 20)
        self.assertEqual(out.loc[1, "net_R"], 1.5)
        self.assertTrue(out.loc[1, "actual_risk_matches"])

    def test_entry_state_uses_previous_source_trading_day_across_weekend_and_night(self):
        out = self.table().set_index("root_id")
        self.assertEqual(out.loc[1, "entry_date"], pd.Timestamp("2024-01-08"))
        self.assertEqual(out.loc[1, "date"], pd.Timestamp("2024-01-08"))
        self.assertEqual(out.loc[1, "asof_date"], pd.Timestamp("2024-01-05"))
        self.assertEqual(out.loc[1, "regime"], "low")
        self.assertEqual(out.loc[1, "market_er60"], .1)

    def test_unmatched_risk_is_missing_not_zero_R(self):
        out = self.table().set_index("root_id")
        self.assertTrue(out.loc[2, "risk_unmatched"])
        self.assertEqual(out.loc[2, "risk_status"], "risk_order_unmatched")
        self.assertTrue(pd.isna(out.loc[2, "initial_risk"]))
        self.assertTrue(pd.isna(out.loc[2, "net_R"]))
        self.assertEqual(out.loc[2, "net_pnl"], 0)

    def test_open_episode_uses_initial_closed_cycle_and_stays_censored(self):
        out = self.table().set_index("root_id")
        self.assertEqual(len(out), 3)
        self.assertEqual(out.loc[3, "first_trade_id"], "T3")
        self.assertEqual(out.loc[3, "initial_risk"], 20)
        self.assertTrue(out.loc[3, "is_open"])
        self.assertFalse(out.loc[3, "is_closed"])
        self.assertEqual(out.loc[3, "open_net_mtm"], -6)
        self.assertTrue(pd.isna(out.loc[3, "net_R"]))
        self.assertTrue(pd.isna(out.loc[3, "net_pnl"]))
        self.assertAlmostEqual(out.loc[3, "open_R"], -.3)

    def test_retry_pnl_excludes_initial_stop_loss_and_counts_open_retry_only_once(self):
        out = self.table().set_index("root_id")
        self.assertTrue(out.loc[1, "half_r_stop"])
        self.assertTrue(out.loc[1, "has_retry"])
        self.assertEqual(out.loc[1, "retry_pnl"], 40)
        self.assertEqual(out.loc[3, "retry_closed_pnl"], 0)
        self.assertEqual(out.loc[3, "retry_open_mtm"], 4)
        self.assertEqual(out.loc[3, "retry_pnl"], 4)
        self.assertFalse(out.loc[2, "half_r_stop"])
        self.assertFalse(out.loc[2, "has_retry"])

    def test_missing_market_state_is_explicit_unclassified(self):
        self.market = self.market[self.market.date.ne(pd.Timestamp("2024-01-08"))]
        out = self.table().set_index("root_id")
        self.assertEqual(out.loc[2, "regime"], "unclassified")
        self.assertTrue(pd.isna(out.loc[2, "market_er60"]))

    def test_duplicate_risk_order_fails_instead_of_selecting_an_arbitrary_risk(self):
        path = self.base / "entry_risk.csv"
        risk = pd.read_csv(path)
        pd.concat([risk, risk.iloc[[0]]], ignore_index=True).to_csv(path, index=False)
        with self.assertRaises(ValueError):
            self.table()

    def test_group_statistics_keep_open_mtm_out_of_closed_win_probability(self):
        out = self.function("episode_group_stats")(self.table()).set_index("regime")
        self.assertEqual(out.loc["low", "nclosed"], 1)
        self.assertEqual(out.loc["low", "closednetpnl"], 30)
        self.assertEqual(out.loc["low", "winprob"], 1)
        self.assertEqual(out.loc["low", "meanR"], 1.5)
        self.assertEqual(out.loc["low", "retryPNL"], 40)
        self.assertEqual(out.loc["mid", "winprob"], 0)
        self.assertEqual(out.loc["mid", "risk_unmatched"], 1)
        self.assertTrue(pd.isna(out.loc["mid", "meanR"]))
        self.assertEqual(out.loc["high", "nclosed"], 0)
        self.assertEqual(out.loc["high", "nopen"], 1)
        self.assertEqual(out.loc["high", "openMTM"], -6)
        self.assertTrue(pd.isna(out.loc["high", "winprob"]))

    def test_episode_bootstrap_draws_source_days_jointly_including_zero_episode_days(self):
        calendar = pd.bdate_range("2024-01-01", periods=10)
        table = pd.DataFrame({
            "date": calendar[[1, 1, 3, 7, 7, 8]],
            "regime": ["low", "low", "low", "high", "high", "high"],
            "is_closed": [True] * 6, "net_R": [-1., 1., 0., -1., 3., 4.],
            "net_pnl": [-10., 10., 0., -10., 30., 40.],
        })
        result = self.function("episode_effect_with_bootstrap")(table, calendar, block=60, repeats=99, seed=7)
        self.assertEqual(result["n_calendar"], 10)
        self.assertAlmostEqual(result["mean_R_difference"], 2.)
        self.assertAlmostEqual(result["closed_win_probability_difference"], 1 / 3)
        from stage269_statistics import stationary_indexes
        rdiff, pdiff = [], []
        for idx in stationary_indexes(10, 60, 99, 7):
            weights = pd.Series(np.bincount(idx, minlength=10), index=calendar)
            w = table["date"].map(weights).to_numpy()
            low, high = table.regime.eq("low").to_numpy(), table.regime.eq("high").to_numpy()
            if w[low].sum() and w[high].sum():
                rdiff.append(np.average(table.loc[high, "net_R"], weights=w[high]) - np.average(table.loc[low, "net_R"], weights=w[low]))
                pdiff.append(np.average(table.loc[high, "net_pnl"].gt(0), weights=w[high]) - np.average(table.loc[low, "net_pnl"].gt(0), weights=w[low]))
        np.testing.assert_allclose(result["mean_R_ci"], np.quantile(rdiff, [.025, .975]))
        np.testing.assert_allclose(result["win_probability_ci"], np.quantile(pdiff, [.025, .975]))
        self.assertEqual(result["bootstrap_valid_R_repeats"], len(rdiff))


if __name__ == "__main__":
    unittest.main()
