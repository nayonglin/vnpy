from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage016_minute_microstructure_pit_audit as s016


class Stage016MinuteMicrostructurePitAuditTest(unittest.TestCase):
    def test_build_daily_microstructure_features_summarizes_single_day_path(self) -> None:
        minute_bars = pd.DataFrame(
            [
                {
                    "vt_symbol": "rb2405.SHFE",
                    "bar_datetime": "2024-01-02 09:00:00",
                    "bar_date": "2024-01-02",
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.0,
                    "volume": 10.0,
                    "open_oi": 1000.0,
                    "close_oi": 1005.0,
                },
                {
                    "vt_symbol": "rb2405.SHFE",
                    "bar_datetime": "2024-01-02 09:01:00",
                    "bar_date": "2024-01-02",
                    "open": 100.0,
                    "high": 104.0,
                    "low": 99.0,
                    "close": 104.0,
                    "volume": 15.0,
                    "open_oi": 1005.0,
                    "close_oi": 1010.0,
                },
                {
                    "vt_symbol": "rb2405.SHFE",
                    "bar_datetime": "2024-01-02 09:02:00",
                    "bar_date": "2024-01-02",
                    "open": 104.0,
                    "high": 105.0,
                    "low": 103.0,
                    "close": 102.0,
                    "volume": 20.0,
                    "open_oi": 1010.0,
                    "close_oi": 1020.0,
                },
            ]
        )

        daily = s016.build_daily_microstructure_features(minute_bars)

        self.assertEqual(len(daily), 1)
        row = daily.iloc[0]
        self.assertEqual(int(row["prior_bar_count"]), 3)
        self.assertAlmostEqual(row["prior_day_return_pct"], 2.0)
        self.assertAlmostEqual(row["prior_intraday_range_pct"], 6.0)
        self.assertAlmostEqual(row["prior_path_abs_return_pct"], 6.0)
        self.assertAlmostEqual(row["prior_efficiency_ratio"], 1.0 / 3.0)
        self.assertAlmostEqual(row["prior_close_location"], 0.5)
        self.assertAlmostEqual(row["prior_oi_change_pct"], 2.0)

    def test_attach_prior_microstructure_features_never_uses_entry_date_bars(self) -> None:
        daily = pd.DataFrame(
            [
                {
                    "vt_symbol": "rb2405.SHFE",
                    "prior_bar_date": pd.Timestamp("2024-01-02"),
                    "prior_bar_count": 100,
                    "prior_day_return_pct": 1.0,
                    "prior_intraday_range_pct": 2.0,
                    "prior_path_abs_return_pct": 3.0,
                    "prior_efficiency_ratio": 0.3,
                    "prior_close_location": 0.8,
                    "prior_oi_change_pct": 4.0,
                    "prior_volume_sum": 1000.0,
                },
                {
                    "vt_symbol": "rb2405.SHFE",
                    "prior_bar_date": pd.Timestamp("2024-01-03"),
                    "prior_bar_count": 100,
                    "prior_day_return_pct": -9.0,
                    "prior_intraday_range_pct": 9.0,
                    "prior_path_abs_return_pct": 9.0,
                    "prior_efficiency_ratio": 1.0,
                    "prior_close_location": 0.1,
                    "prior_oi_change_pct": -9.0,
                    "prior_volume_sum": 2000.0,
                },
            ]
        )
        events = pd.DataFrame(
            [
                {
                    "lot_id": 1,
                    "vt_symbol": "rb2405.SHFE",
                    "entry_date": "2024-01-03",
                    "direction": "long",
                    "realized_pnl": 10.0,
                }
            ]
        )

        joined = s016.attach_prior_microstructure_features(events, daily)

        self.assertEqual(joined.loc[0, "prior_bar_date"], pd.Timestamp("2024-01-02"))
        self.assertAlmostEqual(joined.loc[0, "prior_signal_return_pct"], 1.0)
        self.assertAlmostEqual(joined.loc[0, "prior_signal_close_location"], 0.8)
        self.assertEqual(int(joined.loc[0, "prior_lag_calendar_days"]), 1)


if __name__ == "__main__":
    unittest.main()
