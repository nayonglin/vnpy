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


from stage059_trade_path_excursion_audit import (  # noqa: E402
    _classify_path_archetype,
    _mae_timing_bucket,
    _summarize_path_archetypes,
)


class RebuiltC9Stage059TradePathExcursionTest(unittest.TestCase):
    def test_mae_timing_bucket_handles_missing_and_ranges(self) -> None:
        self.assertEqual(_mae_timing_bucket(None), "missing")
        self.assertEqual(_mae_timing_bucket(0), "day0")
        self.assertEqual(_mae_timing_bucket(3), "day1_3")
        self.assertEqual(_mae_timing_bucket(10), "day4_10")
        self.assertEqual(_mae_timing_bucket(30), "day11_30")
        self.assertEqual(_mae_timing_bucket(31), "day31_plus")

    def test_classify_path_archetype_separates_early_adverse_and_giveback(self) -> None:
        early = pd.Series({"realized_pnl": -1000.0, "days_to_mae": 2, "mfe_r": 0.4, "mae_r": 2.5})
        giveback = pd.Series({"realized_pnl": -1000.0, "days_to_mae": 12, "mfe_r": 1.5, "mae_r": 2.0})
        winner = pd.Series({"realized_pnl": 1000.0, "days_to_mae": 1, "mfe_r": 2.0, "mae_r": 0.5})

        self.assertEqual(_classify_path_archetype(early), "early_adverse_no_edge")
        self.assertEqual(_classify_path_archetype(giveback), "gave_back_favorable_excursion")
        self.assertEqual(_classify_path_archetype(winner), "winner")

    def test_summarize_path_archetypes_tracks_loss_abs_and_selected_volume(self) -> None:
        lots = pd.DataFrame(
            [
                {
                    "path_archetype": "early_adverse_no_edge",
                    "realized_pnl": -1000.0,
                    "selected_volume": 5,
                    "mfe_r": 0.4,
                    "mae_r": 2.5,
                },
                {
                    "path_archetype": "early_adverse_no_edge",
                    "realized_pnl": -500.0,
                    "selected_volume": 1,
                    "mfe_r": 0.2,
                    "mae_r": 1.5,
                },
                {
                    "path_archetype": "winner",
                    "realized_pnl": 1200.0,
                    "selected_volume": 2,
                    "mfe_r": 3.0,
                    "mae_r": 0.4,
                },
            ]
        )

        summary = _summarize_path_archetypes(lots, group_columns=["path_archetype"])
        by_type = summary.set_index("path_archetype")

        self.assertEqual(int(by_type.loc["early_adverse_no_edge", "lot_count"]), 2)
        self.assertAlmostEqual(float(by_type.loc["early_adverse_no_edge", "loss_abs_sum"]), 1500.0)
        self.assertAlmostEqual(float(by_type.loc["early_adverse_no_edge", "selected_volume_sum"]), 6.0)
        self.assertAlmostEqual(float(by_type.loc["winner", "realized_pnl_sum"]), 1200.0)


if __name__ == "__main__":
    unittest.main()
