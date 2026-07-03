from __future__ import annotations

from pathlib import Path
import sys
import unittest

import pandas as pd


TOOLS_DIR = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_optimization"
    / "tools"
)
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


from stage071_stage070_remaining_left_tail_attribution import (  # noqa: E402
    TARGET_VARIANT,
    attach_stage070_deltas_to_window_entries,
    select_target_worst_windows,
    summarize_delta_coverage,
)


class RebuiltC9Stage071RemainingLeftTailAttributionTest(unittest.TestCase):
    def test_select_target_worst_windows_keeps_target_variant_and_orders_by_return(self) -> None:
        worst = pd.DataFrame(
            [
                {
                    "variant": TARGET_VARIANT,
                    "source_start_month": "2022-07",
                    "start_date": "2022-07-19",
                    "end_date": "2023-07-24",
                    "return_pct": -34.0,
                },
                {
                    "variant": "stage013_engine",
                    "source_start_month": "2022-07",
                    "start_date": "2022-07-15",
                    "end_date": "2023-07-17",
                    "return_pct": -45.0,
                },
                {
                    "variant": TARGET_VARIANT,
                    "source_start_month": "2022-07",
                    "start_date": "2022-07-15",
                    "end_date": "2023-07-17",
                    "return_pct": -44.1,
                },
            ]
        )

        selected = select_target_worst_windows(worst, top_n=2)

        self.assertEqual(selected["variant"].tolist(), [TARGET_VARIANT, TARGET_VARIANT])
        self.assertEqual(selected["stage071_window_rank"].tolist(), [1, 2])
        self.assertEqual(selected["window_start_date"].dt.strftime("%Y-%m-%d").tolist(), ["2022-07-15", "2022-07-19"])

    def test_attach_stage070_deltas_uses_only_target_variant_and_exit_inside_window(self) -> None:
        windows = pd.DataFrame(
            [
                {
                    "stage071_window_rank": 1,
                    "source_start_month": "2022-07",
                    "window_start_date": pd.Timestamp("2022-07-15"),
                    "window_end_date": pd.Timestamp("2023-07-17"),
                    "return_pct": -44.1,
                }
            ]
        )
        closed_lots = pd.DataFrame(
            [
                {
                    "requested_start_month": "2022-07",
                    "lot_id": "inside-selected",
                    "open_trade_id": "A",
                    "entry_date": "2022-07-20",
                    "exit_date": "2023-07-10",
                    "realized_pnl": -1000.0,
                },
                {
                    "requested_start_month": "2022-07",
                    "lot_id": "outside-exit",
                    "open_trade_id": "B",
                    "entry_date": "2022-07-20",
                    "exit_date": "2023-07-18",
                    "realized_pnl": -500.0,
                },
                {
                    "requested_start_month": "2022-07",
                    "lot_id": "before-start",
                    "open_trade_id": "C",
                    "entry_date": "2022-07-14",
                    "exit_date": "2023-07-10",
                    "realized_pnl": -300.0,
                },
            ]
        )
        lot_deltas = pd.DataFrame(
            [
                {
                    "candidate_variant": TARGET_VARIANT,
                    "requested_start_month": "2022-07",
                    "lot_id": "inside-selected",
                    "exit_date": "2023-07-10",
                    "stage070_proxy_delta_pnl": -250.0,
                },
                {
                    "candidate_variant": "full_market_ai_top8_and_ai_rank_1_6",
                    "requested_start_month": "2022-07",
                    "lot_id": "inside-selected",
                    "exit_date": "2023-07-10",
                    "stage070_proxy_delta_pnl": -999.0,
                },
                {
                    "candidate_variant": TARGET_VARIANT,
                    "requested_start_month": "2022-07",
                    "lot_id": "outside-exit",
                    "exit_date": "2023-07-18",
                    "stage070_proxy_delta_pnl": -125.0,
                },
            ]
        )

        entries = attach_stage070_deltas_to_window_entries(closed_lots, lot_deltas, windows)

        self.assertEqual(entries["lot_id"].tolist(), ["inside-selected"])
        self.assertAlmostEqual(float(entries["stage071_base_realized_pnl"].sum()), -1000.0)
        self.assertAlmostEqual(float(entries["stage071_stage070_delta_pnl"].sum()), -250.0)
        self.assertAlmostEqual(float(entries["stage071_candidate_realized_pnl"].sum()), -1250.0)

    def test_summarize_delta_coverage_separates_selected_from_unselected_loss(self) -> None:
        entries = pd.DataFrame(
            [
                {
                    "stage071_window_rank": 1,
                    "stage071_stage070_selected": True,
                    "stage071_base_realized_pnl": -1000.0,
                    "stage071_stage070_delta_pnl": -250.0,
                    "stage071_candidate_realized_pnl": -1250.0,
                },
                {
                    "stage071_window_rank": 1,
                    "stage071_stage070_selected": False,
                    "stage071_base_realized_pnl": -3000.0,
                    "stage071_stage070_delta_pnl": 0.0,
                    "stage071_candidate_realized_pnl": -3000.0,
                },
                {
                    "stage071_window_rank": 1,
                    "stage071_stage070_selected": False,
                    "stage071_base_realized_pnl": 500.0,
                    "stage071_stage070_delta_pnl": 0.0,
                    "stage071_candidate_realized_pnl": 500.0,
                },
            ]
        )

        summary = summarize_delta_coverage(entries)
        row = summary.iloc[0]

        self.assertEqual(int(row["entry_count"]), 3)
        self.assertAlmostEqual(float(row["base_total_pnl"]), -3500.0)
        self.assertAlmostEqual(float(row["candidate_total_pnl"]), -3750.0)
        self.assertAlmostEqual(float(row["selected_delta_pnl"]), -250.0)
        self.assertAlmostEqual(float(row["unselected_loss_abs_share_pct"]), 75.0)


if __name__ == "__main__":
    unittest.main()
