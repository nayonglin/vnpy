from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage036_profit_lock_survival_audit as s036


class Stage036ProfitLockSurvivalAuditTest(unittest.TestCase):
    def test_month_end_profit_lock_reduces_future_loss_without_changing_transfer_day_total(self) -> None:
        curve = pd.DataFrame(
            [
                {"requested_start_month": "2020-01", "date": "2020-01-30", "account_equity": 150_000.0},
                {"requested_start_month": "2020-01", "date": "2020-01-31", "account_equity": 300_000.0},
                {"requested_start_month": "2020-01", "date": "2020-02-03", "account_equity": 150_000.0},
            ]
        )
        policy = s036.ProfitLockPolicy(
            variant="test_lock",
            threshold_multiple=1.5,
            transfer_fraction=0.5,
            locked_fraction=0.6,
            reserve_fraction=0.4,
        )

        out = s036.apply_profit_lock_policy(curve, policy)

        month_end = out[out["date"].eq(pd.Timestamp("2020-01-31"))].iloc[0]
        after_loss = out[out["date"].eq(pd.Timestamp("2020-02-03"))].iloc[0]
        self.assertAlmostEqual(float(month_end["account_equity"]), 300_000.0)
        self.assertGreater(float(month_end["locked_equity"]), 0.0)
        self.assertGreater(float(month_end["reserve_equity"]), 0.0)
        self.assertGreater(float(after_loss["account_equity"]), 150_000.0)
        self.assertLess(float(after_loss["production_equity"]), 150_000.0)

    def test_profit_lock_does_not_create_strategy_or_engine_candidate_by_itself(self) -> None:
        goal = pd.DataFrame(
            [
                {
                    "variant": "c9_100",
                    "all_gt1y_negative_count": 10,
                    "all_gt1y_min_return_pct": -20.0,
                    "to_final_negative_count": 0,
                    "min_retention": 1.0,
                    "objective_pass": False,
                },
                {
                    "variant": "balanced_tranche_norm10x",
                    "all_gt1y_negative_count": 0,
                    "all_gt1y_min_return_pct": 0.1,
                    "to_final_negative_count": 0,
                    "min_retention": 0.9,
                    "objective_pass": True,
                },
            ]
        )

        decision = s036.make_profit_lock_decision(goal)

        self.assertEqual(decision["decision"], "stage036_profit_lock_survival_has_account_layer_candidate_needs_true_cash_ledger")
        self.assertEqual(decision["immediate_strategy_candidate_count"], 0)
        self.assertTrue(decision["account_layer_candidate_allowed"])
        self.assertFalse(decision["strategy_rule_created"])
        self.assertFalse(decision["true_engine"])
        self.assertFalse(decision["order_api_called"])

    def test_profit_lock_goal_table_requires_zero_negative_windows_and_80pct_retention(self) -> None:
        aggregate = pd.DataFrame(
            [
                {"variant": "c9_100", "audit_scope": "all_trading_end_dates_gt_1y", "negative_count": 5, "window_count": 10, "min_return_pct": -1.0},
                {"variant": "c9_100", "audit_scope": "start_to_2026_06_30_only", "negative_count": 0, "window_count": 2, "min_return_pct": 10.0},
                {"variant": "lock_good", "audit_scope": "all_trading_end_dates_gt_1y", "negative_count": 0, "window_count": 10, "min_return_pct": 0.1},
                {"variant": "lock_good", "audit_scope": "start_to_2026_06_30_only", "negative_count": 0, "window_count": 2, "min_return_pct": 9.0},
                {"variant": "lock_bad_retention", "audit_scope": "all_trading_end_dates_gt_1y", "negative_count": 0, "window_count": 10, "min_return_pct": 0.1},
                {"variant": "lock_bad_retention", "audit_scope": "start_to_2026_06_30_only", "negative_count": 0, "window_count": 2, "min_return_pct": 9.0},
            ]
        )
        retention = pd.DataFrame(
            [
                {"variant": "c9_100", "requested_start_month": "2020-01", "return_retention_vs_c9": 1.0, "passes_80pct_retention": 1},
                {"variant": "lock_good", "requested_start_month": "2020-01", "return_retention_vs_c9": 0.81, "passes_80pct_retention": 1},
                {"variant": "lock_bad_retention", "requested_start_month": "2020-01", "return_retention_vs_c9": 0.79, "passes_80pct_retention": 0},
            ]
        )

        goal = s036.build_goal_table(aggregate, retention)

        self.assertTrue(bool(goal[goal["variant"].eq("lock_good")].iloc[0]["objective_pass"]))
        self.assertFalse(bool(goal[goal["variant"].eq("lock_bad_retention")].iloc[0]["objective_pass"]))


if __name__ == "__main__":
    unittest.main()
