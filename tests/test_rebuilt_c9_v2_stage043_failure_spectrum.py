from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage043_failure_spectrum as s043


class Stage043FailureSpectrumTest(unittest.TestCase):
    def test_extract_stage_number_from_output_and_stage_paths(self) -> None:
        self.assertEqual(s043.extract_stage_number("outputs/stage040_tqsdk_option_history_readiness/a.json"), 40)
        self.assertEqual(s043.extract_stage_number("stages/20260702_0936_stage042_cashflow_boundary_audit.md"), 42)
        self.assertIsNone(s043.extract_stage_number("LINE.md"))

    def test_classify_decision_text_separates_rejected_data_and_engineering_states(self) -> None:
        rows = [
            {
                "decision": "stage028_not_promoted_keep_for_attribution",
                "best_next_direction": "",
                "immediate_strategy_candidate_count": 0,
            },
            {
                "decision": "stage040_tqsdk_option_history_not_ready_credentials_or_permission_required",
                "best_next_direction": "obtain_or_configure_tqsdk_professional_credentials_or_switch_vendor_source",
                "immediate_strategy_candidate_count": 0,
            },
            {
                "decision": "stage032_public_raw_seed_verified_ready_for_schema_binding_no_rule",
                "best_next_direction": "schema_binding",
                "immediate_strategy_candidate_count": 0,
            },
            {
                "decision": "stage025_opened_entry_states_have_loss_concentration_candidates_need_true_guard_or_quality_split",
                "best_next_direction": "true_guard",
                "immediate_strategy_candidate_count": 0,
            },
        ]

        classes = [s043.classify_decision(row)["route_class"] for row in rows]

        self.assertEqual(classes[0], "rejected_existing_feature_or_shape")
        self.assertEqual(classes[1], "data_required_or_external_state")
        self.assertEqual(classes[2], "engineering_ready_not_signal")
        self.assertEqual(classes[3], "candidate_needs_true_engine_or_user_approval")

    def test_build_action_queue_prioritizes_new_information_before_account_governance(self) -> None:
        spectrum = pd.DataFrame(
            [
                {"stage_no": 40, "route_class": "data_required_or_external_state", "decision": "stage040_tqsdk_option_history_not_ready_credentials_or_permission_required"},
                {"stage_no": 41, "route_class": "data_required_or_external_state", "decision": "stage041_broker_replay_no_accepted_same_source_dataset"},
                {"stage_no": 42, "route_class": "data_required_or_external_state", "decision": "stage042_cashflow_no_accepted_actual_cash_ledger"},
            ]
        )

        queue = s043.build_route_queue(spectrum)

        self.assertGreaterEqual(len(queue), 5)
        self.assertEqual(queue.iloc[0]["route_id"], "authorized_orderflow_depth_mbo_or_mbp10")
        self.assertEqual(queue.iloc[1]["route_id"], "vendor_option_chain_iv_skew")
        self.assertEqual(queue.iloc[2]["route_id"], "broker_same_source_replay")
        self.assertEqual(queue.iloc[3]["route_id"], "actual_cashflow_ledger_account_governance")
        self.assertTrue(queue.iloc[:4]["requires_external_state"].astype(bool).all())
        self.assertFalse(queue.iloc[:4]["strategy_rule_allowed"].astype(bool).any())

    def test_stage043_decision_blocks_local_rescue_when_no_immediate_candidate_exists(self) -> None:
        spectrum = pd.DataFrame(
            [
                {"route_class": "rejected_existing_feature_or_shape", "immediate_strategy_candidate_count": 0},
                {"route_class": "data_required_or_external_state", "immediate_strategy_candidate_count": 0},
                {"route_class": "engineering_ready_not_signal", "immediate_strategy_candidate_count": 0},
            ]
        )
        queue = s043.build_route_queue(spectrum)

        decision = s043.make_stage043_decision(spectrum, queue)

        self.assertEqual(decision["decision"], "stage043_failure_spectrum_requires_new_data_or_forward_oos_no_local_rescue")
        self.assertEqual(decision["immediate_strategy_candidate_count"], 0)
        self.assertFalse(decision["local_rescue_allowed"])
        self.assertFalse(decision["strategy_rule_created"])
        self.assertFalse(decision["true_engine"])
        self.assertFalse(decision["order_api_called"])
        self.assertFalse(decision["ctp_connected"])


if __name__ == "__main__":
    unittest.main()
