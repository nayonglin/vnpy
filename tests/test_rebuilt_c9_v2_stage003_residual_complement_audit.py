from __future__ import annotations

from pathlib import Path
import sys
import unittest

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = (
    PROJECT_DIR
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_v2_optimization"
    / "tools"
)
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage003_residual_complement_audit as s003


class Stage003ResidualComplementAuditTest(unittest.TestCase):
    def test_build_aligned_panel_uses_stage074_target_variant_only(self) -> None:
        stage052 = pd.DataFrame(
            {
                "requested_start_month": ["2020-01", "2020-01"],
                "date": ["2020-01-01", "2020-01-03"],
                "account_equity": [100.0, 90.0],
                "stage052_account_equity": [100.0, 102.0],
            }
        )
        stage074 = pd.DataFrame(
            {
                "variant": [
                    "ignored_variant",
                    s003.STAGE074_TARGET_VARIANT,
                    s003.STAGE074_TARGET_VARIANT,
                ],
                "requested_start_month": ["2020-01", "2020-01", "2020-01"],
                "date": ["2020-01-01", "2020-01-01", "2020-01-03"],
                "equity": [1.0, 100.0, 95.0],
            }
        )

        panel = s003.build_aligned_panel(stage052, stage074)

        self.assertEqual(list(panel.columns), ["requested_start_month", "date", "base", "stage052", "stage074"])
        self.assertEqual(len(panel), 2)
        self.assertEqual(panel["stage074"].tolist(), [100.0, 95.0])

    def test_audit_group_counts_same_window_complementarity(self) -> None:
        panel = pd.DataFrame(
            {
                "requested_start_month": ["2020-01"] * 3,
                "date": pd.to_datetime(["2020-01-01", "2020-01-03", "2020-01-04"]),
                "base": [100.0, 90.0, 80.0],
                "stage052": [100.0, 101.0, 95.0],
                "stage074": [100.0, 98.0, 103.0],
            }
        )

        summary, worst, clusters = s003.audit_group(
            "2020-01",
            panel,
            objective_start_min=pd.Timestamp("2020-01-01"),
            objective_start_max=pd.Timestamp("2020-01-01"),
            min_period_calendar_days=2,
            worst_limit=10,
        )

        self.assertEqual(summary["window_count"], 2)
        self.assertEqual(summary["base_negative_count"], 2)
        self.assertEqual(summary["stage052_negative_count"], 1)
        self.assertEqual(summary["stage074_negative_count"], 1)
        self.assertEqual(summary["oracle_negative_count"], 0)
        self.assertEqual(summary["base_negative_stage052_fixed_count"], 1)
        self.assertEqual(summary["base_negative_stage074_fixed_count"], 1)
        self.assertEqual(summary["base_negative_either_fixed_count"], 2)
        self.assertEqual(summary["base_negative_neither_fixed_count"], 0)
        self.assertTrue(worst.empty)
        self.assertEqual(int(clusters.iloc[0]["base_negative_count"]), 2)

    def test_decision_rejects_when_oracle_upper_bound_still_has_negative_windows(self) -> None:
        source_summary = pd.DataFrame(
            [
                {
                    "source_start_month": "2020-01",
                    "window_count": 10,
                    "base_negative_count": 4,
                    "stage052_negative_count": 3,
                    "stage074_negative_count": 2,
                    "oracle_negative_count": 1,
                    "oracle_min_return_pct": -1.5,
                }
            ]
        )

        decision = s003.make_decision(source_summary)

        self.assertEqual(decision["decision"], "stage003_oracle_upper_bound_still_fails_not_enough")
        self.assertEqual(decision["oracle_negative_count"], 1)
        self.assertEqual(decision["window_count"], 10)
        self.assertEqual(decision["best_case_strict_goal_pass"], 0)


if __name__ == "__main__":
    unittest.main()

