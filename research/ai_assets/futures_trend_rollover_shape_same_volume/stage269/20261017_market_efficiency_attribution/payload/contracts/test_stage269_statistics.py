"""Synthetic boundary tests for the frozen Stage268 statistical contract."""

from __future__ import annotations

import importlib
import unittest

import numpy as np
import pandas as pd

try:
    stats = importlib.import_module("stage269_statistics")
except ModuleNotFoundError:
    stats = None


class StatisticsContractTests(unittest.TestCase):
    def function(self, name):
        value = getattr(stats, name, None)
        self.assertTrue(callable(value), f"missing statistical behavior: {name}")
        return value

    @staticmethod
    def daily(n=100):
        return pd.DataFrame({
            "date": pd.bdate_range("2020-01-01", periods=n),
            "account_equity": 150000.0 + np.arange(1, n + 1) * 100.0,
            "net_pnl": np.full(n, 100.0),
            "slippage": np.full(n, 2.0),
        })

    def test_twenty_day_label_excludes_current_day_and_marks_tail(self):
        daily = self.daily(25)
        daily.loc[0, "net_pnl"] = 999999.0
        out = self.function("build_outcomes")(daily)
        self.assertAlmostEqual(out.loc[0, "future20_return"], 2000 / 150100)
        self.assertEqual(out.loc[0, "future20_cash"], 2000)
        self.assertEqual(out.loc[0, "future20_profit"], 1)
        self.assertEqual(out.loc[0, "label_end"], daily.loc[20, "date"])
        self.assertEqual(out["future20_return"].notna().sum(), 5)
        self.assertTrue(out.loc[5:, "future20_profit"].isna().all())
        self.assertTrue(out.loc[5:, "label_status"].eq("immature_tail").all())

    def test_explicit_source_calendar_prevents_shortened_missing_day_label(self):
        daily = self.daily(80)
        calendar = daily["date"]
        out = self.function("build_outcomes")(daily.drop(index=10), calendar=calendar)
        self.assertEqual(len(out), 80)
        self.assertTrue(pd.isna(out.loc[0, "future20_return"]))
        self.assertEqual(out.loc[0, "label_end"], calendar.iloc[20])
        self.assertEqual(out.loc[0, "label_status"], "missing_source_day")
        self.assertFalse(out.loc[10, "source_present"])
        self.assertTrue(pd.notna(out.loc[11, "future20_return"]))
        self.assertTrue(pd.isna(out.loc[69, "past60_vol"]))
        self.assertTrue(pd.notna(out.loc[71, "past60_vol"]))

    def test_interior_missing_equity_or_cash_invalidates_complete_label(self):
        for col in ("account_equity", "net_pnl"):
            with self.subTest(col=col):
                daily = self.daily(35)
                daily.loc[8, col] = np.nan
                out = self.function("build_outcomes")(daily)
                self.assertTrue(pd.isna(out.loc[0, "future20_return"]))
                self.assertTrue(pd.isna(out.loc[0, "future20_profit"]))
                self.assertEqual(out.loc[0, "label_status"], "invalid_label_source")

    def test_zero_return_is_not_discarded_or_treated_as_profit(self):
        daily = self.daily(25)
        daily["account_equity"] = 150000.0
        daily["net_pnl"] = 0.0
        out = self.function("build_outcomes")(daily)
        self.assertEqual(out.loc[0, "future20_return"], 0)
        self.assertEqual(out.loc[0, "future20_profit"], 0)

    def test_past60_uses_initial_capital_and_never_a_small_vol_floor(self):
        daily = self.daily(85)
        daily["account_equity"] = 150000.0
        daily["net_pnl"] = 0.0
        out = self.function("build_outcomes")(daily)
        self.assertEqual(out.loc[59, "past60_return"], 0)
        self.assertEqual(out.loc[59, "past60_vol"], 0)
        self.assertTrue(pd.isna(out.loc[59, "normalized_future20_return"]))
        self.assertTrue(pd.isna(out.loc[58, "past60_vol"]))
        daily.loc[0, "account_equity"] = 151500.0
        out = self.function("build_outcomes")(daily)
        self.assertAlmostEqual(out.loc[59, "past60_vol"], np.std([.01, -1500 / 151500] + [0] * 58, ddof=1))

    def test_normalization_and_extra_slippage_use_frozen_original_path(self):
        out = self.function("build_outcomes")(self.daily())
        self.assertAlmostEqual(out.loc[59, "normalized_future20_return"], out.loc[59, "future20_return"] / (out.loc[59, "past60_vol"] * np.sqrt(20)))
        self.assertEqual(out.loc[0, "future20_slippage"], 40)
        self.assertAlmostEqual(out.loc[0, "future20_return_extra_slippage"], 1960 / 150100)

    def test_constant_compounded_return_roundoff_does_not_create_huge_normalized_label(self):
        daily = self.daily()
        daily["account_equity"] = 150000.0 * np.power(1.01, np.arange(1, 101))
        daily["net_pnl"] = np.diff(np.r_[150000.0, daily["account_equity"]])
        out = self.function("build_outcomes")(daily)
        self.assertTrue(pd.isna(out.loc[59, "normalized_future20_return"]))

    def test_duplicate_or_calendar_outside_source_is_rejected(self):
        fn = self.function("build_outcomes")
        daily = self.daily()
        with self.assertRaises(ValueError):
            fn(pd.concat([daily, daily.iloc[[0]]]))
        with self.assertRaises(ValueError):
            fn(daily, calendar=daily["date"].iloc[1:])

    def test_split_discards_cross_boundary_labels(self):
        out = self.function("build_outcomes")(self.daily(80))
        split = self.function("split_period")(out, out.loc[0, "date"], out.loc[30, "date"])
        self.assertEqual(len(split), 11)
        self.assertEqual(split.index[-1], 10)
        self.assertTrue((split["label_end"] <= out.loc[30, "date"]).all())

    @staticmethod
    def grouped():
        return pd.DataFrame({
            "date": pd.bdate_range("2020-01-01", periods=9),
            "regime": ["low", "low", "low", "mid", "mid", "mid", "high", "high", "high"],
            "future20_return": [-.1, 0., .1, 0., .1, .2, 0., .2, .4],
        })

    def test_group_means_and_probability_include_zero_and_middle(self):
        out = self.function("group_stats")(self.grouped()).set_index("regime")
        self.assertEqual(list(out.index), ["low", "mid", "high"])
        self.assertEqual(out.loc["low", "n"], 3)
        self.assertAlmostEqual(out.loc["low", "mean"], 0)
        self.assertAlmostEqual(out.loc["low", "profit_probability"], 1 / 3)
        self.assertAlmostEqual(out.loc["high", "mean"], .2)
        self.assertAlmostEqual(out.loc["mid", "profit_probability"], 2 / 3)

    def test_stationary_indexes_are_reproducible_joint_circular_and_keep_length(self):
        fn = self.function("stationary_indexes")
        a = fn(19, block=60, repeats=30, seed=42)
        self.assertEqual(a.shape, (30, 19))
        np.testing.assert_array_equal(a, fn(19, block=60, repeats=30, seed=42))
        self.assertTrue(((a >= 0) & (a < 19)).all())
        self.assertGreater(np.mean(a[:, 1:] == (a[:, :-1] + 1) % 19), .9)
        with self.assertRaises(ValueError):
            fn(19, block=0)

    def test_effect_summary_compares_same_twenty_day_labels(self):
        out = self.function("effect_summary")(self.grouped())
        self.assertAlmostEqual(out["return_difference"], .2)
        self.assertAlmostEqual(out["profit_probability_difference"], 1 / 3)
        self.assertEqual(out["n_calendar"], 9)
        self.assertEqual(out["n_low"], 3)
        self.assertEqual(out["n_mid"], 3)

    def test_bootstrap_keeps_missing_days_and_samples_same_rows_for_both_endpoints(self):
        frame = pd.concat([self.grouped()] * 10, ignore_index=True)
        frame.loc[10:60, "future20_return"] = np.nan
        out = self.function("effect_with_bootstrap")(frame, block=60, repeats=99, seed=7)
        self.assertEqual(out["n_calendar"], 90)
        self.assertEqual(out["n_labeled"], 39)
        indexes = self.function("stationary_indexes")(90, block=60, repeats=99, seed=7)
        differences = []
        probabilities = []
        for idx in indexes:
            sample = frame.iloc[idx]
            low = sample.loc[sample.regime.eq("low"), "future20_return"].dropna()
            high = sample.loc[sample.regime.eq("high"), "future20_return"].dropna()
            if len(low) and len(high):
                differences.append(high.mean() - low.mean())
                probabilities.append((high > 0).mean() - (low > 0).mean())
        np.testing.assert_allclose(out["return_ci"], np.quantile(differences, [.025, .975]))
        np.testing.assert_allclose(out["profit_probability_ci"], np.quantile(probabilities, [.025, .975]))
        self.assertEqual(out["bootstrap_valid_repeats"], len(differences))
        self.assertIn("null-centered", out["p_value_method"])

    def test_ols_reports_original_x_units_after_standardization_and_joint_mask(self):
        x = np.array([0., 1., 0., 1., 2., 0., 1., 2.])
        z = np.array([0., 0., 1., 2., 0., 3., 1., 4.]) * 1000000
        frame = pd.DataFrame({"er60_expanding_pct": x, "control": z, "future20_return": .7 + 2 * x - .000003 * z})
        frame.loc[7, "control"] = np.nan
        out = self.function("ols_incremental")(frame, controls=["control"], year_fe=False)
        self.assertEqual(out["n"], 7)
        self.assertAlmostEqual(out["beta"], 2.)
        self.assertAlmostEqual(out["coefficients"]["control"], -.000003)
        self.assertEqual(out["status"], "ok")

    def test_year_fixed_effect_removes_between_year_level(self):
        frame = pd.DataFrame({
            "date": pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03", "2021-01-01", "2021-01-02", "2021-01-03"]),
            "er60_expanding_pct": [0., 1., 2., 3., 4., 5.],
            "future20_return": [0., 2., 4., 16., 18., 20.],
        })
        out = self.function("ols_incremental")(frame)
        self.assertAlmostEqual(out["beta"], 2.)
        self.assertEqual(out["n"], 6)

    def test_collinear_x_is_reported_unidentified_not_minimum_norm_effect(self):
        frame = pd.DataFrame({"er60_expanding_pct": [0., 1., 2., 3.], "control": [0., 2., 4., 6.], "future20_return": [0., 3., 6., 9.]})
        out = self.function("ols_incremental")(frame, controls=["control"], year_fe=False)
        self.assertEqual(out["status"], "rank_deficient")
        self.assertTrue(pd.isna(out["beta"]))

    def test_holm_controls_predeclared_two_endpoint_family(self):
        out = self.function("holm_adjust")([.04, .01])
        np.testing.assert_allclose(out, [.04, .02])


if __name__ == "__main__":
    unittest.main()
