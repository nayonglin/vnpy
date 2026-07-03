from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage027_non_crowding_frontier_audit as s027


class Stage027NonCrowdingFrontierAuditTest(unittest.TestCase):
    def test_goal_table_summary_preserves_core_target_metrics(self) -> None:
        goal = pd.DataFrame(
            [
                {
                    "variant": "candidate",
                    "all_gt1y_window_count": 1000,
                    "all_gt1y_negative_count": 90,
                    "all_gt1y_min_return_pct": -12.5,
                    "to_final_negative_count": 0,
                    "to_final_min_return_pct": 24.0,
                    "retention_80pct_pass_count": 10,
                    "retention_rows": 11,
                    "min_retention": 0.91,
                    "median_total_return_pct": 180.0,
                    "worst_max_drawdown_pct": -34.0,
                    "objective_pass": 0,
                }
            ]
        )

        row = s027.summarize_variant_goal_table(
            goal,
            variant="candidate",
            stage="StageX",
            structure_family="xsmom_confirmation",
            evidence_tier="proxy",
            decision="not_promoted",
            note="unit-test",
        )

        self.assertEqual(row["stage"], "StageX")
        self.assertEqual(row["structure_family"], "xsmom_confirmation")
        self.assertEqual(row["evidence_tier"], "proxy")
        self.assertEqual(row["all_gt1y_negative_count"], 90)
        self.assertAlmostEqual(row["all_gt1y_min_return_pct"], -12.5)
        self.assertEqual(row["to_final_negative_count"], 0)
        self.assertAlmostEqual(row["min_retention"], 0.91)
        self.assertEqual(row["objective_pass"], 0)

    def test_classification_rejects_parameter_rescue_after_goal_gap(self) -> None:
        row = {
            "stage": "Stage026",
            "structure_family": "ai_quality_add_risk",
            "evidence_tier": "true_engine",
            "all_gt1y_negative_count": 394_418,
            "all_gt1y_min_return_pct": -43.79,
            "to_final_negative_count": 24,
            "min_retention": 0.71,
            "objective_pass": 0,
            "parameter_rescue_allowed": 0,
        }

        classified = s027.classify_frontier_row(row, baseline_negative_count=330_947)

        self.assertEqual(classified["frontier_status"], "reject")
        self.assertIn("left_tail_worse", classified["failure_reasons"])
        self.assertIn("to_final_negative", classified["failure_reasons"])
        self.assertIn("no_parameter_rescue", classified["failure_reasons"])

    def test_classification_requires_worst_return_not_to_deteriorate(self) -> None:
        row = {
            "stage": "Stage021",
            "structure_family": "independent_sleeve",
            "evidence_tier": "curve_proxy",
            "all_gt1y_negative_count": 267_868,
            "all_gt1y_min_return_pct": -54.86,
            "to_final_negative_count": 0,
            "min_retention": 1.0,
            "objective_pass": 0,
            "parameter_rescue_allowed": 0,
        }

        classified = s027.classify_frontier_row(
            row,
            baseline_negative_count=330_947,
            baseline_min_return_pct=-43.79,
        )

        self.assertEqual(classified["frontier_status"], "diagnostic_only")
        self.assertIn("worst_return_worse", classified["failure_reasons"])

    def test_goal_aggregate_retention_uses_ratio_not_binary_pass_column(self) -> None:
        goal = pd.DataFrame(
            [
                {
                    "variant": "candidate",
                    "audit_scope": "all_trading_end_dates_gt_1y",
                    "window_count": 10,
                    "negative_count": 2,
                    "min_return_pct": -5.0,
                },
                {
                    "variant": "candidate",
                    "audit_scope": "start_to_2026_06_30_only",
                    "window_count": 3,
                    "negative_count": 0,
                    "min_return_pct": 20.0,
                },
            ]
        )
        retention = pd.DataFrame(
            [
                {
                    "requested_start_month": "2020-01",
                    "candidate_vs_base_return_ratio": 0.91,
                    "passes_80pct_retention_vs_base": 1,
                },
                {
                    "requested_start_month": "2026-01",
                    "candidate_vs_base_return_ratio": 0.73,
                    "passes_80pct_retention_vs_base": 0,
                },
            ]
        )

        row = s027.summarize_goal_aggregate(
            goal,
            variant="candidate",
            stage="StageX",
            structure_family="account_layer",
            evidence_tier="proxy",
            decision="not_promoted",
            note="unit-test",
            retention=retention,
        )

        self.assertEqual(row["retention_80pct_pass_count"], 1)
        self.assertEqual(row["retention_rows"], 2)
        self.assertAlmostEqual(row["min_retention"], 0.73)

    def test_decision_prefers_structure_frontier_without_promoting_any_candidate(self) -> None:
        frontier = pd.DataFrame(
            [
                {
                    "stage": "Stage021",
                    "variant": "xsmom_overlay",
                    "structure_family": "independent_sleeve",
                    "evidence_tier": "curve_proxy",
                    "all_gt1y_negative_count": 267_868,
                    "all_gt1y_min_return_pct": -54.86,
                    "to_final_negative_count": 0,
                    "min_retention": 1.00,
                    "objective_pass": 0,
                    "parameter_rescue_allowed": 0,
                },
                {
                    "stage": "Stage022",
                    "variant": "xsmom_confirmation",
                    "structure_family": "xsmom_confirmation",
                    "evidence_tier": "closed_lot_proxy",
                    "all_gt1y_negative_count": 231_382,
                    "all_gt1y_min_return_pct": -40.53,
                    "to_final_negative_count": 0,
                    "min_retention": 1.08,
                    "objective_pass": 0,
                    "parameter_rescue_allowed": 0,
                },
                {
                    "stage": "Stage026",
                    "variant": "cool_quality_add_risk",
                    "structure_family": "ai_quality_add_risk",
                    "evidence_tier": "true_engine",
                    "all_gt1y_negative_count": 394_418,
                    "all_gt1y_min_return_pct": -43.79,
                    "to_final_negative_count": 24,
                    "min_retention": 0.71,
                    "objective_pass": 0,
                    "parameter_rescue_allowed": 0,
                },
            ]
        )

        decision = s027.make_frontier_decision(frontier, baseline_negative_count=330_947)

        self.assertEqual(decision["decision"], "stage027_no_candidate_promoted_use_frontier_for_next_hypothesis")
        self.assertEqual(decision["promoted_candidate_count"], 0)
        self.assertEqual(decision["frontier_signal_count"], 1)
        self.assertEqual(decision["best_next_direction"], "xsmom_confirmation_true_engine_or_new_pit_source")
        self.assertEqual(decision["parameter_rescue_allowed"], False)


if __name__ == "__main__":
    unittest.main()
