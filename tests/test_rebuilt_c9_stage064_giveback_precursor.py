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


from stage064_giveback_precursor_exit_audit import (  # noqa: E402
    STRONG_CAPTURE_PCT,
    TARGET_ARCHETYPE,
    _classify_stage064_tradeoff,
    _stage064_condition_masks,
    _stage064_decision,
    _summarize_condition_capture,
)


class RebuiltC9Stage064GivebackPrecursorTest(unittest.TestCase):
    def test_condition_masks_separate_preentry_from_path_diagnostics(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "selected_volume": 5,
                    "selected_volume_gt1": 1,
                    "ai_rank": 7,
                    "oi_confirmed": 1,
                    "full_market_ai_top8": 0,
                    "mfe_r": 1.4,
                    "mae_r": 2.2,
                    "days_to_mfe": 1,
                    "days_to_mae": 4,
                },
                {
                    "selected_volume": 1,
                    "selected_volume_gt1": 0,
                    "ai_rank": 2,
                    "oi_confirmed": 0,
                    "full_market_ai_top8": 1,
                    "mfe_r": 0.7,
                    "mae_r": 1.1,
                    "days_to_mfe": 3,
                    "days_to_mae": 2,
                },
            ]
        )

        masks = _stage064_condition_masks(frame, include_path_conditions=True)

        self.assertEqual(masks["selected_volume_gt1"][0], "pre_entry")
        self.assertEqual(masks["path_mfe_ge1"][0], "path_after_entry")
        self.assertTrue(bool(masks["selected_volume_gt1"][1].iloc[0]))
        self.assertTrue(bool(masks["path_mfe_ge1"][1].iloc[0]))
        self.assertTrue(bool(masks["path_mfe_before_mae"][1].iloc[0]))
        self.assertFalse(bool(masks["path_mfe_ge1"][1].iloc[1]))

    def test_capture_summary_uses_giveback_loss_abs_not_row_count(self) -> None:
        pressure = pd.DataFrame(
            [
                {"path_archetype": TARGET_ARCHETYPE, "loss_abs": 80.0, "realized_pnl": -80.0, "selected_volume": 5},
                {"path_archetype": TARGET_ARCHETYPE, "loss_abs": 20.0, "realized_pnl": -20.0, "selected_volume": 1},
                {"path_archetype": "winner", "loss_abs": 0.0, "realized_pnl": 60.0, "selected_volume": 4},
            ]
        )
        conditions = {
            "large_only": ("pre_entry", pd.Series([True, False, True])),
            "all_target": ("path_after_entry", pd.Series([True, True, False])),
        }

        summary = _summarize_condition_capture(
            pressure,
            conditions,
            target_archetype=TARGET_ARCHETYPE,
        ).set_index("condition")

        self.assertEqual(summary.loc["large_only", "target_count"], 1)
        self.assertEqual(summary.loc["large_only", "target_loss_capture_pct"], 80.0)
        self.assertEqual(summary.loc["all_target", "target_loss_capture_pct"], 100.0)

    def test_tradeoff_treats_path_capture_as_diagnostic_not_preentry_candidate(self) -> None:
        self.assertEqual(
            _classify_stage064_tradeoff("path_after_entry", 100.0, None),
            "path_only_exit_diagnostic",
        )
        self.assertEqual(
            _classify_stage064_tradeoff("pre_entry", STRONG_CAPTURE_PCT, 1000.0),
            "right_tail_collision",
        )
        self.assertEqual(
            _classify_stage064_tradeoff("pre_entry", STRONG_CAPTURE_PCT, -1000.0),
            "pre_entry_negative_full_pnl_candidate",
        )

    def test_decision_does_not_promote_when_only_path_conditions_capture(self) -> None:
        tradeoff = pd.DataFrame(
            [
                {
                    "condition": "path_mfe_ge1",
                    "feature_timing": "path_after_entry",
                    "target_loss_capture_pct": 100.0,
                    "full_pnl_sum": float("nan"),
                    "tradeoff_class": "path_only_exit_diagnostic",
                },
                {
                    "condition": "selected_volume_gt1",
                    "feature_timing": "pre_entry",
                    "target_loss_capture_pct": 90.0,
                    "full_pnl_sum": 100000.0,
                    "tradeoff_class": "right_tail_collision",
                },
            ]
        )
        target_lots = pd.DataFrame({"realized_pnl": [-140.0], "loss_abs": [140.0]})

        decision = _stage064_decision(tradeoff, target_lots)

        self.assertEqual(
            decision["decision"],
            "stage064_giveback_no_clean_preentry_candidate_keep_exit_diagnostic",
        )
        self.assertEqual(decision["best_condition"], "selected_volume_gt1")


if __name__ == "__main__":
    unittest.main()
