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

import stage002_goal_geometry_gap_audit as s002


class Stage002GoalGeometryGapAuditTest(unittest.TestCase):
    def test_summarize_goal_aggregate_weights_windows_and_preserves_final_scope(self) -> None:
        aggregate = pd.DataFrame(
            [
                {
                    "variant": "A",
                    "source_start_month": "2020-01",
                    "audit_scope": "all_trading_end_dates_gt_1y",
                    "window_count": 10,
                    "negative_count": 2,
                    "min_return_pct": -10.0,
                    "mean_return_pct": 20.0,
                },
                {
                    "variant": "A",
                    "source_start_month": "2020-07",
                    "audit_scope": "all_trading_end_dates_gt_1y",
                    "window_count": 30,
                    "negative_count": 3,
                    "min_return_pct": -4.0,
                    "mean_return_pct": 40.0,
                },
                {
                    "variant": "A",
                    "source_start_month": "2020-01",
                    "audit_scope": "start_to_2026_06_30_only",
                    "window_count": 2,
                    "negative_count": 0,
                    "min_return_pct": 8.0,
                    "mean_return_pct": 12.0,
                },
            ]
        )

        row = s002.summarize_goal_aggregate(
            "StageX",
            "stage_x",
            aggregate,
            retention_lookup={"A": {"retention_pass_count": 2, "retention_rows": 2}},
        )[0]

        self.assertEqual(row["candidate_id"], "StageX:A")
        self.assertEqual(row["all_gt1y_window_count"], 40)
        self.assertEqual(row["all_gt1y_negative_count"], 5)
        self.assertEqual(row["all_gt1y_negative_rate_pct"], 12.5)
        self.assertEqual(row["all_gt1y_min_return_pct"], -10.0)
        self.assertEqual(row["all_gt1y_mean_return_pct"], 35.0)
        self.assertEqual(row["to_final_negative_count"], 0)
        self.assertEqual(row["to_final_min_return_pct"], 8.0)
        self.assertEqual(row["retention_pass_count"], 2)
        self.assertEqual(row["retention_rows"], 2)
        self.assertEqual(row["strict_goal_pass"], 0)
        self.assertEqual(row["terminal_goal_pass"], 1)
        self.assertEqual(row["retention_goal_pass"], 1)

    def test_cluster_worst_windows_keeps_candidate_identity_and_calendar_buckets(self) -> None:
        worst = pd.DataFrame(
            [
                {
                    "variant": "A",
                    "source_start_month": "2022-07",
                    "start_date": "2022-07-15",
                    "end_date": "2023-07-17",
                    "return_pct": -44.0,
                },
                {
                    "variant": "A",
                    "source_start_month": "2022-07",
                    "start_date": "2022-07-20",
                    "end_date": "2023-07-24",
                    "return_pct": -40.0,
                },
                {
                    "variant": "B",
                    "source_start_month": "2021-01",
                    "start_date": "2021-03-01",
                    "end_date": "2022-04-01",
                    "return_pct": -20.0,
                },
            ]
        )

        clusters = s002.cluster_worst_windows("StageY", "stage_y", worst)

        a_cluster = clusters[clusters["candidate_id"].eq("StageY:A")].iloc[0]
        self.assertEqual(a_cluster["start_year_month"], "2022-07")
        self.assertEqual(a_cluster["end_year_month"], "2023-07")
        self.assertEqual(a_cluster["worst_window_rows"], 2)
        self.assertEqual(a_cluster["min_return_pct"], -44.0)

        b_cluster = clusters[clusters["candidate_id"].eq("StageY:B")].iloc[0]
        self.assertEqual(b_cluster["start_year_month"], "2021-03")
        self.assertEqual(b_cluster["end_year_month"], "2022-04")
        self.assertEqual(b_cluster["source_start_month"], "2021-01")

    def test_make_decision_requires_strict_zero_negative_and_full_retention(self) -> None:
        metrics = pd.DataFrame(
            [
                {
                    "candidate_id": "A",
                    "all_gt1y_negative_count": 3,
                    "all_gt1y_min_return_pct": -5.0,
                    "retention_goal_pass": 1,
                },
                {
                    "candidate_id": "B",
                    "all_gt1y_negative_count": 0,
                    "all_gt1y_min_return_pct": 1.0,
                    "retention_goal_pass": 0,
                },
            ]
        )

        decision = s002.make_decision(metrics)

        self.assertEqual(decision["decision"], "stage002_goal_not_met_path_gap_map_ready")
        self.assertEqual(decision["candidate_count"], 2)
        self.assertEqual(decision["strict_goal_pass_count"], 0)
        self.assertEqual(decision["best_by_negative_count"]["candidate_id"], "B")
        self.assertEqual(decision["best_by_min_return"]["candidate_id"], "B")


if __name__ == "__main__":
    unittest.main()
