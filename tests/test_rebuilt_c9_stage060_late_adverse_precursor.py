from __future__ import annotations

from pathlib import Path
import sys
import unittest

import pandas as pd


TOOLS_DIR = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_optimization"
    / "tools"
)
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


from stage060_late_adverse_precursor_audit import (  # noqa: E402
    _classify_condition_tradeoff,
    _summarize_condition_capture,
    _summarize_full_sample_collision,
)


class RebuiltC9Stage060LateAdversePrecursorTest(unittest.TestCase):
    def test_classify_condition_tradeoff_separates_path_facts_and_preentry_candidates(self) -> None:
        self.assertEqual(
            _classify_condition_tradeoff(
                feature_timing="path_after_entry",
                target_loss_capture_pct=100.0,
                full_pnl_sum=-1000.0,
            ),
            "path_only_diagnostic",
        )
        self.assertEqual(
            _classify_condition_tradeoff(
                feature_timing="pre_entry",
                target_loss_capture_pct=85.0,
                full_pnl_sum=-1000.0,
            ),
            "pre_entry_negative_full_pnl_candidate",
        )
        self.assertEqual(
            _classify_condition_tradeoff(
                feature_timing="pre_entry",
                target_loss_capture_pct=85.0,
                full_pnl_sum=5000.0,
            ),
            "right_tail_collision",
        )
        self.assertEqual(
            _classify_condition_tradeoff(
                feature_timing="pre_entry",
                target_loss_capture_pct=25.0,
                full_pnl_sum=-1000.0,
            ),
            "weak_or_broad",
        )

    def test_summarize_condition_capture_tracks_late_loss_capture(self) -> None:
        pressure = pd.DataFrame(
            [
                {
                    "path_archetype": "late_adverse_no_edge",
                    "loss_abs": 1000.0,
                    "realized_pnl": -1000.0,
                    "selected_volume": 5,
                },
                {
                    "path_archetype": "early_adverse_no_edge",
                    "loss_abs": 500.0,
                    "realized_pnl": -500.0,
                    "selected_volume": 1,
                },
                {
                    "path_archetype": "winner",
                    "loss_abs": 0.0,
                    "realized_pnl": 1200.0,
                    "selected_volume": 2,
                },
            ]
        )
        conditions = {
            "target_only": ("pre_entry", pd.Series([True, False, False], index=pressure.index)),
            "all_rows": ("pre_entry", pd.Series([True, True, True], index=pressure.index)),
        }

        summary = _summarize_condition_capture(pressure, conditions, target_archetype="late_adverse_no_edge")
        by_condition = summary.set_index("condition")

        self.assertEqual(int(by_condition.loc["target_only", "target_count"]), 1)
        self.assertAlmostEqual(float(by_condition.loc["target_only", "target_loss_capture_pct"]), 100.0)
        self.assertAlmostEqual(float(by_condition.loc["all_rows", "pressure_pnl_sum"]), -300.0)
        self.assertAlmostEqual(float(by_condition.loc["all_rows", "selected_volume_sum"]), 8.0)

    def test_summarize_full_sample_collision_tracks_positive_and_negative_pnl(self) -> None:
        full = pd.DataFrame(
            [
                {"realized_pnl": 1000.0, "selected_volume": 3},
                {"realized_pnl": -400.0, "selected_volume": 2},
                {"realized_pnl": 200.0, "selected_volume": 1},
            ]
        )
        conditions = {
            "first_two": ("pre_entry", pd.Series([True, True, False], index=full.index)),
        }

        summary = _summarize_full_sample_collision(full, conditions)
        row = summary.iloc[0]

        self.assertEqual(row["condition"], "first_two")
        self.assertAlmostEqual(float(row["full_pnl_sum"]), 600.0)
        self.assertAlmostEqual(float(row["full_positive_pnl_sum"]), 1000.0)
        self.assertAlmostEqual(float(row["full_negative_pnl_sum"]), -400.0)
        self.assertAlmostEqual(float(row["full_selected_volume_sum"]), 5.0)


if __name__ == "__main__":
    unittest.main()
