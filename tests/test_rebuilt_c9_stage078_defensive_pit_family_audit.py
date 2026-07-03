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


from stage078_defensive_pit_family_audit import (  # noqa: E402
    build_stage078_conditions,
    summarize_defensive_conditions,
)


class Stage078DefensivePitFamilyAuditTest(unittest.TestCase):
    def test_build_stage078_conditions_normalizes_existing_pit_fields(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "ai_rank": 7,
                    "ai_rank_1_6": False,
                    "full_market_ai_top8": False,
                    "oi_confirmed": "1",
                    "selected_volume_gt1": 1,
                    "drawdown_abs_pct": 22.0,
                    "loss_streak_ge2": True,
                    "active_positions_ge3": False,
                    "same_direction_correlation_max_corr": 0.71,
                }
            ]
        )

        conditions = {condition.name: condition for condition in build_stage078_conditions(frame)}

        self.assertTrue(bool(conditions["not_full_market_ai_top8"].mask.iloc[0]))
        self.assertTrue(bool(conditions["not_ai_rank_1_6"].mask.iloc[0]))
        self.assertTrue(bool(conditions["oi_confirmed"].mask.iloc[0]))
        self.assertTrue(bool(conditions["selected_volume_gt1"].mask.iloc[0]))
        self.assertTrue(bool(conditions["drawdown_abs_ge20"].mask.iloc[0]))
        self.assertTrue(bool(conditions["loss_streak_ge2"].mask.iloc[0]))
        self.assertTrue(bool(conditions["same_direction_corr_ge70"].mask.iloc[0]))

    def test_summarize_defensive_conditions_promotes_clean_negative_global_condition(self) -> None:
        feature_matrix = pd.DataFrame(
            [
                {"entry_date": "2022-01-03", "realized_pnl": -1000.0, "oi_confirmed": True},
                {"entry_date": "2023-01-03", "realized_pnl": -2000.0, "oi_confirmed": True},
                {"entry_date": "2024-01-03", "realized_pnl": -500.0, "oi_confirmed": True},
                {"entry_date": "2025-01-03", "realized_pnl": 5000.0, "oi_confirmed": False},
            ]
        )
        window_entries = pd.DataFrame(
            [
                {"stage071_base_loss_abs": 1000.0, "oi_confirmed": True},
                {"stage071_base_loss_abs": 2000.0, "oi_confirmed": True},
                {"stage071_base_loss_abs": 1000.0, "oi_confirmed": False},
            ]
        )

        summary = summarize_defensive_conditions(
            feature_matrix,
            window_entries,
            refuted_conditions=set(),
            min_global_count=3,
            min_year_count=3,
            min_worst_loss_capture_pct=50.0,
            max_global_total_pnl=0.0,
            max_oos_positive_fold_count=1,
            max_positive_pnl_collision_pct=25.0,
        )

        row = summary[summary["condition"].eq("oi_confirmed")].iloc[0]
        self.assertAlmostEqual(float(row["worst_loss_capture_pct"]), 75.0)
        self.assertAlmostEqual(float(row["global_total_pnl"]), -3500.0)
        self.assertTrue(bool(row["stage078_defensive_candidate"]))

    def test_summarize_defensive_conditions_blocks_prior_refuted_shape(self) -> None:
        feature_matrix = pd.DataFrame(
            [
                {"entry_date": "2022-01-03", "realized_pnl": -1000.0, "oi_confirmed": True},
                {"entry_date": "2023-01-03", "realized_pnl": -2000.0, "oi_confirmed": True},
                {"entry_date": "2024-01-03", "realized_pnl": -500.0, "oi_confirmed": True},
                {"entry_date": "2025-01-03", "realized_pnl": 5000.0, "oi_confirmed": False},
            ]
        )
        window_entries = pd.DataFrame(
            [
                {"stage071_base_loss_abs": 1000.0, "oi_confirmed": True},
                {"stage071_base_loss_abs": 2000.0, "oi_confirmed": True},
                {"stage071_base_loss_abs": 1000.0, "oi_confirmed": False},
            ]
        )

        summary = summarize_defensive_conditions(
            feature_matrix,
            window_entries,
            refuted_conditions={"oi_confirmed"},
            min_global_count=3,
            min_year_count=3,
            min_worst_loss_capture_pct=50.0,
            max_global_total_pnl=0.0,
            max_oos_positive_fold_count=1,
            max_positive_pnl_collision_pct=25.0,
        )

        row = summary[summary["condition"].eq("oi_confirmed")].iloc[0]
        self.assertTrue(bool(row["prior_refuted_or_insufficient"]))
        self.assertFalse(bool(row["stage078_defensive_candidate"]))


if __name__ == "__main__":
    unittest.main()
