from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage029_next_route_eligibility_audit as s029


class Stage029NextRouteEligibilityAuditTest(unittest.TestCase):
    def test_proxy_improvement_followed_by_daily_failure_is_rejected(self) -> None:
        route = {
            "route_id": "contract_oi_share_ge50",
            "family": "external_pit",
            "evidence_state": "proxy_improved_but_daily_probe_failed",
            "proxy_negative_delta": -78_813,
            "daily_probe_worst_return_delta_pp": -7.2241,
            "known_refuted": 1,
            "param_rescue_forbidden": 1,
        }

        classified = s029.classify_route(route)

        self.assertEqual(classified["route_status"], "rejected_no_param_rescue")
        self.assertEqual(classified["priority_score"], 0)
        self.assertIn("daily_probe_failed", classified["exclusion_reasons"])
        self.assertEqual(classified["recommended_next_action"], "do_not_continue_this_route")

    def test_new_pit_source_without_local_history_requires_data_acquisition_not_strategy(self) -> None:
        route = {
            "route_id": "options_iv_skew_or_orderflow",
            "family": "new_external_pit",
            "evidence_state": "no_local_history",
            "local_history_available": 0,
            "known_refuted": 0,
            "param_rescue_forbidden": 0,
        }

        classified = s029.classify_route(route)

        self.assertEqual(classified["route_status"], "needs_data_acquisition")
        self.assertGreater(classified["priority_score"], 0)
        self.assertEqual(classified["recommended_next_action"], "acquire_or_build_pit_history_before_any_rule")

    def test_decision_blocks_all_parameter_rescue_when_no_route_is_eligible(self) -> None:
        routes = pd.DataFrame(
            [
                s029.classify_route(
                    {
                        "route_id": "xsmom12_not_opposed",
                        "family": "xsmom_confirmation",
                        "evidence_state": "true_engine_failed",
                        "known_refuted": 1,
                        "param_rescue_forbidden": 1,
                    }
                ),
                s029.classify_route(
                    {
                        "route_id": "full_market_top8_cap",
                        "family": "ai_budget_cap",
                        "evidence_state": "true_engine_failed",
                        "known_refuted": 1,
                        "param_rescue_forbidden": 1,
                    }
                ),
            ]
        )

        decision = s029.make_route_decision(routes)

        self.assertEqual(decision["decision"], "stage029_no_local_unrefuted_route_need_new_pit_or_independent_sleeve")
        self.assertEqual(decision["immediate_strategy_candidate_count"], 0)
        self.assertFalse(decision["parameter_rescue_allowed"])


if __name__ == "__main__":
    unittest.main()
