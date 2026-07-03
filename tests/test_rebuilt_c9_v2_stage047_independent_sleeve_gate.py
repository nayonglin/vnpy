from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage047_independent_sleeve_gate as s047


class Stage047IndependentSleeveGateTest(unittest.TestCase):
    def test_historical_xsmom_true_carry_is_rebuild_priority_not_promotion(self) -> None:
        candidate = {
            "candidate_id": "historical_stage208_xsmom_true_carry",
            "structure_family": "independent_xsmom_carry_sleeve",
            "evidence_scope": "historical_different_baseline",
            "true_engine_current_rebuild": False,
            "historical_true_engine": True,
            "materiality_score": 2,
            "right_tail_preserved": True,
            "current_dense_goal_pass": False,
            "current_artifacts_available": False,
            "known_current_refuted": False,
            "param_rescue_forbidden": False,
            "source_paths": "research/lines/futures_trend_drawdown30_preserve_return/stages/20260601_1809_stage208_xsmom_true_carry_replay.md",
        }

        result = s047.evaluate_candidate(candidate)

        self.assertEqual(result["gate_status"], "rebuild_priority")
        self.assertFalse(result["promote_now"])
        self.assertTrue(result["needs_current_rebuild"])
        self.assertIn("historical_different_baseline", result["blocking_reasons"])
        self.assertIn("current_artifacts_missing_or_not_current", result["blocking_reasons"])

    def test_current_true_engine_failure_is_rejected_even_if_proxy_was_frontier(self) -> None:
        candidate = {
            "candidate_id": "stage022_028_xsmom_confirmation",
            "structure_family": "xsmom_confirmation_add_risk",
            "evidence_scope": "current_rebuilt_c9",
            "true_engine_current_rebuild": True,
            "historical_true_engine": False,
            "materiality_score": 1,
            "right_tail_preserved": False,
            "current_dense_goal_pass": False,
            "current_artifacts_available": True,
            "known_current_refuted": True,
            "param_rescue_forbidden": True,
            "source_paths": "stage022,stage028",
        }

        result = s047.evaluate_candidate(candidate)

        self.assertEqual(result["gate_status"], "rejected_no_param_rescue")
        self.assertFalse(result["promote_now"])
        self.assertFalse(result["needs_current_rebuild"])
        self.assertIn("current_true_engine_refuted", result["blocking_reasons"])
        self.assertIn("parameter_rescue_forbidden", result["blocking_reasons"])

    def test_only_current_true_engine_goal_pass_can_promote(self) -> None:
        candidate = {
            "candidate_id": "synthetic_pass",
            "structure_family": "independent_sleeve",
            "evidence_scope": "current_rebuilt_c9",
            "true_engine_current_rebuild": True,
            "historical_true_engine": True,
            "materiality_score": 2,
            "right_tail_preserved": True,
            "current_dense_goal_pass": True,
            "current_artifacts_available": True,
            "known_current_refuted": False,
            "param_rescue_forbidden": False,
            "source_paths": "synthetic",
        }

        result = s047.evaluate_candidate(candidate)

        self.assertEqual(result["gate_status"], "promotion_candidate")
        self.assertTrue(result["promote_now"])
        self.assertFalse(result["needs_current_rebuild"])
        self.assertEqual(result["blocking_reasons"], "")

    def test_stage047_decision_has_no_promotion_and_names_next_rebuild_route(self) -> None:
        frame = pd.DataFrame(
            [
                s047.evaluate_candidate(s047.build_candidate_inventory()[0]),
                s047.evaluate_candidate(s047.build_candidate_inventory()[1]),
            ]
        )

        decision = s047.make_stage047_decision(frame)

        self.assertEqual(decision["decision"], "stage047_independent_sleeve_no_current_promotion_rebuild_xsmom_first")
        self.assertEqual(decision["promotion_candidate_count"], 0)
        self.assertGreaterEqual(decision["rebuild_priority_count"], 1)
        self.assertEqual(decision["immediate_strategy_candidate_count"], 0)
        self.assertFalse(decision["strategy_rule_created"])
        self.assertFalse(decision["order_api_called"])
        self.assertFalse(decision["ctp_connected"])
        self.assertIn("historical_stage208_xsmom_true_carry", decision["best_next_rebuild_route"])


if __name__ == "__main__":
    unittest.main()
