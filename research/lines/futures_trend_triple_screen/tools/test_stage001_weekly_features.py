"""Synthetic causal and missing-data contracts for the fixed weekly screen."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from stage001_weekly_features import build_weekly_features
except ImportError:
    build_weekly_features = None


def fixture(weeks=85, start="2022-01-03"):
    calendar = pd.bdate_range(start, periods=weeks * 5)
    f = pd.DataFrame({"date": calendar, "product_id": "SHFE.CU",
                      "r": 0.001 + np.arange(len(calendar)) * 0.000002,
                      "reference_epoch": "SHFE.CU.202312"})
    return f, calendar


class WeeklyScreenContract(unittest.TestCase):
    def build(self, frame, calendar, products=("SHFE.CU",)):
        self.assertIsNotNone(build_weekly_features, "weekly screen feature implementation is absent")
        return build_weekly_features(frame, calendar, products=products)

    def test_35_complete_weeks_are_required_and_only_next_week_can_use_them(self):
        f, cal = fixture()
        out = self.build(f, cal).set_index("date")
        self.assertFalse(out.loc[cal[174], "weekly_ready"])
        row = out.loc[cal[175]]
        self.assertTrue(row.weekly_ready)
        self.assertEqual(row.weekly_asof, cal[174])
        self.assertEqual(row.weekly_complete_weeks, 35)
        self.assertEqual(row.weekly_direction, 1)

    def test_appending_future_and_current_week_values_cannot_repaint_prior_dates(self):
        f, cal = fixture()
        end = 202  # Wednesday, well past warmup.
        past = self.build(f.iloc[:end + 1], cal)
        changed = f.copy()
        changed.loc[end + 1:, "r"] = -0.3
        longer = self.build(changed, cal)
        pd.testing.assert_frame_equal(past, longer.loc[longer.date.le(cal[end])].reset_index(drop=True))

    def test_missing_return_restarts_warmup_instead_of_forward_filling(self):
        f, cal = fixture(90)
        f.loc[201, "r"] = np.nan  # One missing day invalidates all of week 41.
        out = self.build(f, cal).set_index("date")
        self.assertTrue(out.loc[cal[200], "weekly_ready"])  # Current week not consumed yet.
        self.assertFalse(out.loc[cal[205], "weekly_ready"])
        self.assertEqual(out.loc[cal[205], "reason"], "missing_previous_week_returns")
        self.assertFalse(out.loc[cal[379], "weekly_ready"])
        self.assertTrue(out.loc[cal[380], "weekly_ready"])
        self.assertEqual(out.loc[cal[380], "weekly_complete_weeks"], 35)

    def test_zero_slope_is_ready_but_not_a_direction(self):
        f, cal = fixture()
        f["r"] = 0.0
        row = self.build(f, cal).iloc[175]
        self.assertTrue(row.weekly_ready)
        self.assertEqual(row.weekly_hist, 0.0)
        self.assertEqual(row.weekly_hist_prev, 0.0)
        self.assertEqual(row.weekly_direction, 0)
        self.assertEqual(row.reason, "flat_weekly_histogram")

    def test_histogram_matches_independent_scalar_ema_recurrence(self):
        f, cal = fixture()
        prices = 100.0 * np.exp(f.r.to_numpy().reshape(-1, 5).sum(axis=1).cumsum())
        fast = slow = signal = None
        histograms = []
        signal_count = 0
        for n, price in enumerate(prices, start=1):
            fast = price if fast is None else fast + 2/13 * (price-fast)
            slow = price if slow is None else slow + 2/27 * (price-slow)
            if n < 26:
                histograms.append(np.nan)
                continue
            macd = fast-slow
            signal = macd if signal is None else signal + 2/10 * (macd-signal)
            signal_count += 1
            histograms.append(macd-signal if signal_count >= 9 else np.nan)
        row = self.build(f, cal).iloc[175]
        self.assertAlmostEqual(row.weekly_hist, histograms[34], places=11)
        self.assertAlmostEqual(row.weekly_hist_prev, histograms[33], places=11)

    def test_short_holiday_week_and_iso_year_use_actual_source_calendar(self):
        f, cal = fixture(start="2021-05-10")
        holiday = pd.to_datetime(["2021-12-30", "2021-12-31"])
        cal = cal.difference(holiday)
        f = f.loc[f.date.isin(cal)].reset_index(drop=True)
        out = self.build(f, cal).set_index("date")
        self.assertTrue(out.loc[pd.Timestamp("2022-01-10"), "weekly_ready"])
        self.assertEqual(out.loc[pd.Timestamp("2022-01-03"), "weekly_asof"], pd.Timestamp("2021-12-29"))

    def test_partial_source_week_at_start_is_not_a_complete_week(self):
        f, cal = fixture()
        out = self.build(f.iloc[2:], cal).set_index("date")
        self.assertFalse(out.loc[cal[175], "weekly_ready"])
        self.assertTrue(out.loc[cal[180], "weekly_ready"])

    def test_contract_change_has_no_price_gap_when_same_contract_returns_match(self):
        f, cal = fixture()
        changed = f.copy()
        changed.loc[200:, "reference_epoch"] = "SHFE.CU.202412"
        pd.testing.assert_frame_equal(self.build(f, cal), self.build(changed, cal))

    def test_integer_calendar_is_parsed_as_yyyymmdd(self):
        f, cal = fixture()
        ints = cal.strftime("%Y%m%d").astype("int64").to_numpy()
        pd.testing.assert_frame_equal(self.build(f, cal), self.build(f, ints))

    def test_duplicate_product_date_is_rejected(self):
        f, cal = fixture()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.build(pd.concat([f, f.iloc[[0]]], ignore_index=True), cal)

    def test_missing_product_is_unknown_rather_than_a_synthetic_short(self):
        f, cal = fixture()
        out = self.build(f, cal, products=("SHFE.CU", "GFEX.LC"))
        missing = out.loc[out.product_id.eq("GFEX.LC")]
        self.assertFalse(missing.weekly_ready.any())
        self.assertTrue(missing.weekly_direction.eq(0).all())
        self.assertTrue(missing.reason.eq("missing_product_returns").all())


if __name__ == "__main__":
    unittest.main()
