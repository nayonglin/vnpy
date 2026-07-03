from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage042_cashflow_boundary_audit as s042


class Stage042CashflowBoundaryAuditTest(unittest.TestCase):
    def test_research_cash_output_is_not_actual_cashflow_ledger(self) -> None:
        row = s042.classify_cashflow_path(
            Path("research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage036/profit_lock_transfer_events.csv"),
            2048,
        )

        self.assertEqual(row["asset_kind"], "research_or_backtest_cash_artifact")
        self.assertFalse(row["schema_validation_required"])
        self.assertFalse(row["strategy_objective_credit_allowed"])
        self.assertIn("research_artifact_not_actual_cashflow_ledger", row["blocking_reason"])

    def test_external_account_statement_path_is_schema_candidate_only(self) -> None:
        row = s042.classify_cashflow_path(Path("external_data/account_statements/cash_ledger_2026.csv"), 4096)

        self.assertEqual(row["asset_kind"], "potential_actual_cashflow_ledger")
        self.assertTrue(row["schema_validation_required"])
        self.assertFalse(row["strategy_objective_credit_allowed"])
        self.assertFalse(row["rule_candidate_allowed"])

    def test_cashflow_schema_requires_external_flow_identity_and_equity_fields(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "date": "2026-06-16",
                    "broker_account": "acct",
                    "cash_flow_id": "cf-1",
                    "flow_type": "deposit",
                    "cash_flow_amount": 50_000,
                    "account_equity_before": 150_000,
                    "account_equity_after": 200_000,
                    "source_system": "broker_statement",
                }
            ]
        )

        result = s042.validate_cashflow_schema(frame)

        self.assertTrue(result["schema_complete"])
        self.assertTrue(result["has_cashflow_identity"])
        self.assertTrue(result["has_equity_fields"])
        self.assertFalse(result["cashflow_sign_violation"])
        self.assertFalse(result["strategy_objective_credit_allowed"])
        self.assertTrue(result["account_layer_audit_allowed"])

    def test_cashflow_sign_violation_blocks_account_layer_audit(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "date": "2026-06-16",
                    "broker_account": "acct",
                    "cash_flow_id": "cf-1",
                    "flow_type": "deposit",
                    "cash_flow_amount": -50_000,
                    "account_equity_before": 150_000,
                    "account_equity_after": 100_000,
                    "source_system": "broker_statement",
                }
            ]
        )

        result = s042.validate_cashflow_schema(frame)

        self.assertTrue(result["schema_complete"])
        self.assertTrue(result["cashflow_sign_violation"])
        self.assertFalse(result["account_layer_audit_allowed"])
        self.assertIn("cashflow_sign_violation", result["blocking_reasons"])

    def test_external_cashflows_never_get_strategy_goal_credit(self) -> None:
        decision = s042.classify_cashflow_objective_credit(
            uses_external_cashflow=True,
            return_metric="money_weighted_return",
        )

        self.assertFalse(decision["strategy_objective_credit_allowed"])
        self.assertTrue(decision["account_experience_metric_allowed"])
        self.assertIn("external_cashflow_cannot_prove_strategy_return", decision["blocking_reasons"])

    def test_stage_decision_without_actual_ledger_stays_readonly(self) -> None:
        readiness = pd.DataFrame(
            [
                {
                    "path": "research/lines/a/outputs/cash_events.csv",
                    "asset_kind": "research_or_backtest_cash_artifact",
                    "schema_complete": False,
                    "actual_cashflow_ledger_accepted": False,
                    "account_layer_audit_allowed": False,
                    "strategy_objective_credit_allowed": False,
                }
            ]
        )

        decision = s042.make_stage042_decision(readiness)

        self.assertEqual(decision["decision"], "stage042_cashflow_no_accepted_actual_cash_ledger")
        self.assertEqual(decision["accepted_cashflow_ledger_count"], 0)
        self.assertEqual(decision["immediate_strategy_candidate_count"], 0)
        self.assertFalse(decision["strategy_rule_created"])
        self.assertFalse(decision["true_engine"])
        self.assertFalse(decision["order_api_called"])
        self.assertFalse(decision["ctp_connected"])


if __name__ == "__main__":
    unittest.main()
