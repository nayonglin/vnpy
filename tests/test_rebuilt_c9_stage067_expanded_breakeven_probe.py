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


from stage067_breakeven_expanded_daily_probe import (  # noqa: E402
    _stage067_decision_from_metrics,
    _stage067_starts_from_stage042_frame,
)


class RebuiltC9Stage067ExpandedBreakevenProbeTest(unittest.TestCase):
    def test_stage042_probe_starts_are_deduplicated_and_keep_bucket_context(self) -> None:
        source = pd.DataFrame(
            [
                {"requested_start": "2022-04-15", "probe_bucket": "both_negative", "probe_rank": 2},
                {"requested_start": "2022-04-15", "probe_bucket": "duplicate", "probe_rank": 3},
                {"requested_start": "2022-03-30", "probe_bucket": "fixed_by_stage039", "probe_rank": 1},
            ]
        )

        result = _stage067_starts_from_stage042_frame(source)

        self.assertEqual(result["requested_start"].tolist(), ["2022-03-30", "2022-04-15"])
        self.assertEqual(result["stage067_probe_rank"].tolist(), [1, 2])
        self.assertEqual(result["probe_bucket"].tolist(), ["fixed_by_stage039", "both_negative"])
        self.assertTrue(result["requested_end"].eq("2026-06-30").all())

    def test_decision_requires_zero_strict_negative_windows_for_goal_pass(self) -> None:
        metrics = {
            "baseline_strict_negative_window_count": 81351,
            "candidate_strict_negative_window_count": 69937,
            "baseline_strict_min_return_pct": -37.7,
            "candidate_strict_min_return_pct": -36.5,
            "retention_rows": 32,
            "retention_pass_count": 32,
        }

        decision = _stage067_decision_from_metrics(metrics)

        self.assertEqual(decision["decision"], "stage067_expanded_improves_left_tail_not_goal")
        self.assertFalse(decision["goal_pass"])
        self.assertTrue(decision["retention_ok"])

    def test_decision_passes_only_when_left_tail_is_cleared_and_retention_holds(self) -> None:
        metrics = {
            "baseline_strict_negative_window_count": 81351,
            "candidate_strict_negative_window_count": 0,
            "baseline_strict_min_return_pct": -37.7,
            "candidate_strict_min_return_pct": 0.5,
            "retention_rows": 32,
            "retention_pass_count": 32,
        }

        decision = _stage067_decision_from_metrics(metrics)

        self.assertEqual(decision["decision"], "stage067_expanded_goal_pass_candidate")
        self.assertTrue(decision["goal_pass"])
        self.assertTrue(decision["retention_ok"])


if __name__ == "__main__":
    unittest.main()
