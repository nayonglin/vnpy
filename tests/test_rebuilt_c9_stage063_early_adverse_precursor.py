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


from stage063_early_adverse_precursor_audit import (  # noqa: E402
    STRONG_CAPTURE_PCT,
    TARGET_ARCHETYPE,
    _classify_stage063_tradeoff,
    _stage063_condition_masks,
    _stage063_decision,
    _summarize_condition_capture,
)


class RebuiltC9Stage063EarlyAdversePrecursorTest(unittest.TestCase):
    def test_condition_masks_are_predeclared_and_point_in_time(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "selected_volume": 6,
                    "selected_volume_gt1": 1,
                    "ai_rank": 5,
                    "oi_confirmed": 1,
                    "full_market_ai_top8": 0,
                    "loss_streak": 2,
                    "loss_streak_ge2": 1,
                    "drawdown_abs_pct": 21.0,
                },
                {
                    "selected_volume": 1,
                    "selected_volume_gt1": 0,
                    "ai_rank": 2,
                    "oi_confirmed": 0,
                    "full_market_ai_top8": 1,
                    "loss_streak": 0,
                    "loss_streak_ge2": 0,
                    "drawdown_abs_pct": 3.0,
                },
            ]
        )

        masks = _stage063_condition_masks(frame, include_path_conditions=False)

        self.assertIn("selected_volume_gt1", masks)
        self.assertIn("selected_volume_ge5", masks)
        self.assertIn("oi_confirmed", masks)
        self.assertIn("not_full_market_ai_top8", masks)
        self.assertIn("loss_streak_ge2", masks)
        self.assertTrue(bool(masks["selected_volume_ge5"][1].iloc[0]))
        self.assertFalse(bool(masks["selected_volume_ge5"][1].iloc[1]))
        self.assertTrue(bool(masks["rank_4_9"][1].iloc[0]))
        self.assertFalse(bool(masks["rank_4_9"][1].iloc[1]))

    def test_capture_summary_uses_target_loss_not_row_count(self) -> None:
        pressure = pd.DataFrame(
            [
                {"path_archetype": TARGET_ARCHETYPE, "loss_abs": 90.0, "realized_pnl": -90.0, "selected_volume": 5},
                {"path_archetype": TARGET_ARCHETYPE, "loss_abs": 10.0, "realized_pnl": -10.0, "selected_volume": 1},
                {"path_archetype": "winner", "loss_abs": 0.0, "realized_pnl": 50.0, "selected_volume": 4},
            ]
        )
        conditions = {
            "large_only": ("pre_entry", pd.Series([True, False, True])),
            "all_target": ("pre_entry", pd.Series([True, True, False])),
        }

        summary = _summarize_condition_capture(
            pressure,
            conditions,
            target_archetype=TARGET_ARCHETYPE,
        ).set_index("condition")

        self.assertEqual(summary.loc["large_only", "target_count"], 1)
        self.assertEqual(summary.loc["large_only", "target_loss_capture_pct"], 90.0)
        self.assertEqual(summary.loc["all_target", "target_loss_capture_pct"], 100.0)

    def test_tradeoff_rejects_broad_positive_full_sample_collision(self) -> None:
        self.assertEqual(
            _classify_stage063_tradeoff("pre_entry", STRONG_CAPTURE_PCT, 1000.0),
            "right_tail_collision",
        )
        self.assertEqual(
            _classify_stage063_tradeoff("pre_entry", STRONG_CAPTURE_PCT - 1.0, -1000.0),
            "partial_negative_but_below_capture",
        )
        self.assertEqual(
            _classify_stage063_tradeoff("pre_entry", STRONG_CAPTURE_PCT, -1000.0),
            "pre_entry_negative_full_pnl_candidate",
        )

    def test_decision_does_not_promote_when_only_positive_full_sample_conditions_capture(self) -> None:
        tradeoff = pd.DataFrame(
            [
                {
                    "condition": "selected_volume_gt1",
                    "feature_timing": "pre_entry",
                    "target_loss_capture_pct": 90.0,
                    "full_pnl_sum": 100000.0,
                    "tradeoff_class": "right_tail_collision",
                },
                {
                    "condition": "oi_confirmed",
                    "feature_timing": "pre_entry",
                    "target_loss_capture_pct": 49.0,
                    "full_pnl_sum": -100000.0,
                    "tradeoff_class": "partial_negative_but_below_capture",
                },
            ]
        )
        target_lots = pd.DataFrame({"realized_pnl": [-200.0], "loss_abs": [200.0]})

        decision = _stage063_decision(tradeoff, target_lots)

        self.assertEqual(decision["decision"], "stage063_early_adverse_no_clean_preentry_candidate_keep_readonly")
        self.assertEqual(decision["best_condition"], "selected_volume_gt1")


if __name__ == "__main__":
    unittest.main()
