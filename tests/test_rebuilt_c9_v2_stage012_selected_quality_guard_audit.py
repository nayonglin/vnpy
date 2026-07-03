from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage012_selected_quality_guard_audit as s012


class Stage012SelectedQualityGuardAuditTest(unittest.TestCase):
    def test_focus_membership_uses_source_and_exit_date_only(self) -> None:
        lots = pd.DataFrame(
            [
                {
                    "lot_id": "inside",
                    "requested_start_month": "2022-07",
                    "entry_date": "2021-01-01",
                    "exit_date": "2023-01-03",
                    "realized_pnl": -1000.0,
                    "active_positions_before": 3,
                },
                {
                    "lot_id": "wrong_source",
                    "requested_start_month": "2021-07",
                    "entry_date": "2022-08-01",
                    "exit_date": "2023-01-03",
                    "realized_pnl": -1000.0,
                    "active_positions_before": 3,
                },
                {
                    "lot_id": "outside_exit",
                    "requested_start_month": "2022-07",
                    "entry_date": "2023-01-01",
                    "exit_date": "2024-01-03",
                    "realized_pnl": -1000.0,
                    "active_positions_before": 3,
                },
            ]
        )
        focus = pd.DataFrame(
            [
                {
                    "source_start_month": "2022-07",
                    "start_date": "2022-07-15",
                    "end_date": "2023-07-17",
                }
            ]
        )

        tagged = s012.mark_focus_membership(lots, focus)

        self.assertEqual(tagged.loc[tagged["lot_id"].eq("inside"), "stage011_focus_window_hit"].iloc[0], 1)
        self.assertEqual(tagged.loc[tagged["lot_id"].eq("wrong_source"), "stage011_focus_window_hit"].iloc[0], 0)
        self.assertEqual(tagged.loc[tagged["lot_id"].eq("outside_exit"), "stage011_focus_window_hit"].iloc[0], 0)

    def test_guard_summary_can_flag_stable_non_product_guard(self) -> None:
        lots = pd.DataFrame(
            [
                {
                    "lot_id": "bad_focus",
                    "requested_start_month": "2022-07",
                    "entry_date": "2023-01-01",
                    "exit_date": "2023-01-03",
                    "entry_year": 2023,
                    "realized_pnl": -1000.0,
                    "active_positions_before": 3,
                    "portfolio_drawdown_abs_pct": 4.0,
                },
                {
                    "lot_id": "bad_outside",
                    "requested_start_month": "2020-01",
                    "entry_date": "2020-02-01",
                    "exit_date": "2020-02-03",
                    "entry_year": 2020,
                    "realized_pnl": -500.0,
                    "active_positions_before": 3,
                    "portfolio_drawdown_abs_pct": 6.0,
                },
                {
                    "lot_id": "good_focus_1",
                    "requested_start_month": "2022-07",
                    "entry_date": "2022-08-01",
                    "exit_date": "2023-02-01",
                    "entry_year": 2022,
                    "realized_pnl": 4000.0,
                    "active_positions_before": 1,
                    "portfolio_drawdown_abs_pct": 5.0,
                },
                {
                    "lot_id": "good_focus_2",
                    "requested_start_month": "2022-07",
                    "entry_date": "2023-04-01",
                    "exit_date": "2023-05-01",
                    "entry_year": 2023,
                    "realized_pnl": 2000.0,
                    "active_positions_before": 0,
                    "portfolio_drawdown_abs_pct": 5.0,
                },
                {
                    "lot_id": "good_outside",
                    "requested_start_month": "2024-01",
                    "entry_date": "2024-03-01",
                    "exit_date": "2024-03-10",
                    "entry_year": 2024,
                    "realized_pnl": 1000.0,
                    "active_positions_before": 2,
                    "portfolio_drawdown_abs_pct": 5.0,
                },
            ]
        )
        focus = pd.DataFrame(
            [
                {
                    "source_start_month": "2022-07",
                    "start_date": "2022-07-15",
                    "end_date": "2023-07-17",
                }
            ]
        )

        summary, _ = s012.build_guard_summary(
            lots,
            focus,
            min_retained_count=3,
            min_year_count=2,
            min_retained_total_pnl_share_pct=80.0,
        )
        row = summary[summary["guard_name"].eq("exclude_active_positions_ge3")].iloc[0]

        self.assertNotIn("product", summary.columns)
        self.assertNotIn("direction", summary.columns)
        self.assertEqual(int(row["excluded_count"]), 2)
        self.assertAlmostEqual(float(row["excluded_total_pnl"]), -1500.0)
        self.assertAlmostEqual(float(row["retained_total_pnl"]), 7000.0)
        self.assertAlmostEqual(float(row["focus_proxy_delta_before_guard"]), 1250.0)
        self.assertAlmostEqual(float(row["focus_proxy_delta_after_guard"]), 1500.0)
        self.assertAlmostEqual(float(row["focus_proxy_delta_improvement"]), 250.0)
        self.assertEqual(bool(row["candidate_for_true_engine_audit"]), True)

    def test_focus_proxy_delta_weights_overlapping_focus_windows(self) -> None:
        lots = pd.DataFrame(
            [
                {
                    "lot_id": "bad_focus",
                    "requested_start_month": "2022-07",
                    "entry_date": "2023-01-01",
                    "exit_date": "2023-01-03",
                    "entry_year": 2023,
                    "realized_pnl": -1000.0,
                    "stage010_proxy_delta_pnl": -250.0,
                    "active_positions_before": 3,
                },
                {
                    "lot_id": "good_focus",
                    "requested_start_month": "2022-07",
                    "entry_date": "2023-02-01",
                    "exit_date": "2023-02-03",
                    "entry_year": 2023,
                    "realized_pnl": 2000.0,
                    "stage010_proxy_delta_pnl": 500.0,
                    "active_positions_before": 1,
                },
            ]
        )
        focus = pd.DataFrame(
            [
                {
                    "source_start_month": "2022-07",
                    "start_date": "2022-07-15",
                    "end_date": "2023-07-17",
                },
                {
                    "source_start_month": "2022-07",
                    "start_date": "2022-08-01",
                    "end_date": "2023-07-17",
                },
            ]
        )

        tagged = s012.mark_focus_membership(lots, focus)
        summary, _ = s012.build_guard_summary(
            tagged,
            focus,
            min_retained_count=1,
            min_year_count=1,
            min_retained_total_pnl_share_pct=80.0,
        )
        row = summary[summary["guard_name"].eq("exclude_active_positions_ge3")].iloc[0]

        self.assertEqual(int(tagged.loc[tagged["lot_id"].eq("bad_focus"), "stage011_focus_window_hit_count"].iloc[0]), 2)
        self.assertAlmostEqual(float(row["focus_proxy_delta_before_guard"]), 500.0)
        self.assertAlmostEqual(float(row["focus_proxy_delta_after_guard"]), 1000.0)
        self.assertAlmostEqual(float(row["focus_proxy_delta_improvement"]), 500.0)


if __name__ == "__main__":
    unittest.main()
