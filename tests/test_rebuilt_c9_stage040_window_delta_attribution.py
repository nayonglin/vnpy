import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
sys.path.insert(0, str(TOOLS))

from stage040_stage039_negative_window_delta_attribution import (  # noqa: E402
    _classify_window_effect,
    _ret_pct,
    _select_top_windows,
)


class Stage040WindowDeltaAttributionTest(unittest.TestCase):
    def test_classifies_added_negative_window_and_delta_path(self) -> None:
        row = _classify_window_effect(
            source_start_month="2022-07",
            start_date=pd.Timestamp("2022-07-15"),
            end_date=pd.Timestamp("2023-07-17"),
            stage013_start_equity=288510.0,
            stage013_end_equity=162160.0,
            stage039_start_equity=288510.0,
            stage039_end_equity=161161.25,
        )

        self.assertEqual(row["window_class"], "both_negative")
        self.assertAlmostEqual(row["stage039_in_window_delta"], -998.75)
        self.assertEqual(row["stage039_absolute_end_ge_stage013"], 0)

    def test_flags_denominator_effect_when_absolute_equity_is_higher(self) -> None:
        row = _classify_window_effect(
            source_start_month="2021-01",
            start_date=pd.Timestamp("2022-01-01"),
            end_date=pd.Timestamp("2023-01-01"),
            stage013_start_equity=100.0,
            stage013_end_equity=101.0,
            stage039_start_equity=130.0,
            stage039_end_equity=129.0,
        )

        self.assertEqual(row["window_class"], "added_negative_by_stage039")
        self.assertEqual(row["stage039_absolute_end_ge_stage013"], 1)
        self.assertEqual(row["stage039_added_negative_denominator_effect"], 1)

    def test_return_percent_handles_zero_start_equity(self) -> None:
        self.assertTrue(pd.isna(_ret_pct(0.0, 10.0)))

    def test_top_window_selection_keeps_each_window_class(self) -> None:
        windows = pd.DataFrame(
            [
                {"window_class": "added_negative_by_stage039", "stage039_return_pct": -2.0, "stage013_return_pct": 0.1},
                {"window_class": "added_negative_by_stage039", "stage039_return_pct": -1.0, "stage013_return_pct": 0.2},
                {"window_class": "both_negative", "stage039_return_pct": -40.0, "stage013_return_pct": -39.0},
                {"window_class": "fixed_by_stage039", "stage039_return_pct": 1.0, "stage013_return_pct": -3.0},
            ]
        )

        selected = _select_top_windows(windows, per_class_limit=1)

        self.assertEqual(
            set(selected["window_class"]),
            {"added_negative_by_stage039", "both_negative", "fixed_by_stage039"},
        )
        added = selected[selected["window_class"].eq("added_negative_by_stage039")].iloc[0]
        self.assertEqual(float(added["stage039_return_pct"]), -2.0)


if __name__ == "__main__":
    unittest.main()
