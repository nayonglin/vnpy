from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage030_new_pit_source_readiness_audit as s030


class Stage030NewPitSourceReadinessAuditTest(unittest.TestCase):
    def test_orderflow_route_with_zero_rule_coverage_requires_external_data(self) -> None:
        route = {
            "route_id": "authorized_orderflow_depth_mbo",
            "family": "microstructure_orderflow",
            "local_rule_coverage_count": 0,
            "required_decision_count": 219,
            "authorized_history_available": 0,
            "right_tail_guard_passed": 0,
            "stage_refs": "Stage103,Stage262",
        }

        classified = s030.classify_new_pit_route(route)

        self.assertEqual(classified["route_status"], "external_data_required")
        self.assertFalse(classified["rule_candidate_allowed"])
        self.assertIn("rule_coverage_zero", classified["blocking_reasons"])
        self.assertEqual(classified["recommended_next_action"], "acquire_authorized_history_before_strategy_rule")

    def test_options_iv_skew_with_sdk_but_no_historical_chain_needs_history_first(self) -> None:
        route = {
            "route_id": "options_iv_skew",
            "family": "options_volatility",
            "sdk_calc_available": 1,
            "local_historical_rows": 0,
            "local_contract_history_available": 0,
            "authorized_history_available": 0,
            "stage_refs": "TqSdk option docs",
        }

        classified = s030.classify_new_pit_route(route)

        self.assertEqual(classified["route_status"], "needs_pit_history_acquisition")
        self.assertFalse(classified["rule_candidate_allowed"])
        self.assertIn("no_historical_option_chain", classified["blocking_reasons"])
        self.assertEqual(classified["recommended_next_action"], "build_pit_option_chain_history_before_signal_audit")

    def test_decision_disables_true_engine_when_no_route_is_rule_ready(self) -> None:
        classified_routes = pd.DataFrame(
            [
                s030.classify_new_pit_route(
                    {
                        "route_id": "authorized_orderflow_depth_mbo",
                        "family": "microstructure_orderflow",
                        "local_rule_coverage_count": 0,
                        "required_decision_count": 219,
                        "authorized_history_available": 0,
                        "right_tail_guard_passed": 0,
                    }
                ),
                s030.classify_new_pit_route(
                    {
                        "route_id": "options_iv_skew",
                        "family": "options_volatility",
                        "sdk_calc_available": 1,
                        "local_historical_rows": 0,
                        "local_contract_history_available": 0,
                        "authorized_history_available": 0,
                    }
                ),
            ]
        )

        decision = s030.make_readiness_decision(classified_routes)

        self.assertEqual(decision["decision"], "stage030_new_pit_routes_data_first_no_strategy_candidate")
        self.assertEqual(decision["immediate_strategy_candidate_count"], 0)
        self.assertTrue(decision["acquisition_manifest_required"])
        self.assertFalse(decision["true_engine"])
        self.assertFalse(decision["order_api_called"])


if __name__ == "__main__":
    unittest.main()
