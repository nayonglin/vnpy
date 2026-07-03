import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
sys.path.insert(0, str(TOOLS))

from stage041_selected_daily_cold_start_probe import (  # noqa: E402
    _audit_curve_from_actual_start,
    _select_probe_start_dates,
)


class Stage041DailyColdStartProbeTest(unittest.TestCase):
    def test_audit_curve_uses_actual_start_only(self) -> None:
        curve = pd.DataFrame(
            [
                {"date": "2022-07-15", "equity": 150000.0},
                {"date": "2023-07-14", "equity": 170000.0},
                {"date": "2023-07-17", "equity": 140000.0},
                {"date": "2024-07-15", "equity": 180000.0},
            ]
        )

        row = _audit_curve_from_actual_start("2022-07-15", "toy", curve)

        self.assertEqual(row["window_count"], 2)
        self.assertEqual(row["negative_count"], 1)
        self.assertAlmostEqual(row["min_return_pct"], -6.6666666667)
        self.assertEqual(row["worst_end_date"], "2023-07-17")

    def test_probe_start_selection_prioritizes_unique_both_negative_then_added_absolute_worse(self) -> None:
        top_windows = pd.DataFrame(
            [
                {
                    "window_class": "both_negative",
                    "start_date": "2022-07-15",
                    "stage039_return_pct": -44.0,
                    "stage039_absolute_end_ge_stage013": 0,
                },
                {
                    "window_class": "both_negative",
                    "start_date": "2022-07-15",
                    "stage039_return_pct": -43.0,
                    "stage039_absolute_end_ge_stage013": 0,
                },
                {
                    "window_class": "added_negative_by_stage039",
                    "start_date": "2024-01-02",
                    "stage039_return_pct": -0.1,
                    "stage039_absolute_end_ge_stage013": 0,
                },
            ]
        )

        starts = _select_probe_start_dates(top_windows, limit=2)

        self.assertEqual(starts, [pd.Timestamp("2022-07-15"), pd.Timestamp("2024-01-02")])


if __name__ == "__main__":
    unittest.main()
