import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
sys.path.insert(0, str(TOOLS))

from stage055_new_entry_signal_budget_audit import (  # noqa: E402
    attach_stage054_windows_to_entries,
    summarize_condition_pnl,
    unique_stage054_windows,
)


class Stage055NewEntrySignalBudgetAuditTest(unittest.TestCase):
    def test_unique_stage054_windows_deduplicates_stage013_and_stage053_variants(self) -> None:
        windows = pd.DataFrame(
            [
                {
                    "requested_start": "2022-04-14",
                    "variant": "stage013_daily_cold_start_engine",
                    "window_start_date": "2022-04-14",
                    "window_end_date": "2023-07-07",
                    "window_return_pct": -36.5,
                },
                {
                    "requested_start": "2022-04-14",
                    "variant": "stage053_daily_cold_start_contract_oi_share_proxy",
                    "window_start_date": "2022-04-14",
                    "window_end_date": "2023-07-07",
                    "window_return_pct": -40.7,
                },
            ]
        )

        unique = unique_stage054_windows(windows)

        self.assertEqual(len(unique), 1)
        self.assertEqual(unique.iloc[0]["requested_start"], "2022-04-14")
        self.assertEqual(int(unique.iloc[0]["stage054_variant_count"]), 2)
        self.assertAlmostEqual(float(unique.iloc[0]["stage054_min_window_return_pct"]), -40.7)

    def test_attach_stage054_windows_uses_strictly_after_window_start(self) -> None:
        entries = pd.DataFrame(
            [
                {
                    "requested_start_month": "2022-04-14",
                    "open_trade_id": "at-start",
                    "entry_date": "2022-04-14",
                    "realized_pnl": -100.0,
                },
                {
                    "requested_start_month": "2022-04-14",
                    "open_trade_id": "inside",
                    "entry_date": "2022-04-15",
                    "realized_pnl": -200.0,
                },
                {
                    "requested_start_month": "2022-04-14",
                    "open_trade_id": "after",
                    "entry_date": "2023-07-08",
                    "realized_pnl": 300.0,
                },
            ]
        )
        windows = unique_stage054_windows(
            pd.DataFrame(
                [
                    {
                        "requested_start": "2022-04-14",
                        "variant": "stage013_daily_cold_start_engine",
                        "window_start_date": "2022-04-14",
                        "window_end_date": "2023-07-07",
                        "window_return_pct": -36.5,
                    }
                ]
            )
        )

        attached = attach_stage054_windows_to_entries(entries, windows)
        by_id = dict(zip(attached["open_trade_id"], attached["inside_stage054_window"]))

        self.assertFalse(bool(by_id["at-start"]))
        self.assertTrue(bool(by_id["inside"]))
        self.assertFalse(bool(by_id["after"]))

    def test_summarize_condition_pnl_reports_negative_condition_contribution(self) -> None:
        entries = pd.DataFrame(
            [
                {
                    "requested_start_month": "2022-04-14",
                    "entry_date": "2022-04-15",
                    "realized_pnl": -100.0,
                    "ai_rank_1_6": True,
                    "account_clean": True,
                    "account_injured": False,
                    "selected_volume_gt1": True,
                },
                {
                    "requested_start_month": "2022-04-14",
                    "entry_date": "2022-04-16",
                    "realized_pnl": 50.0,
                    "ai_rank_1_6": False,
                    "account_clean": False,
                    "account_injured": True,
                    "selected_volume_gt1": False,
                },
            ]
        )

        summary = summarize_condition_pnl(entries)
        all_row = summary[summary["condition"].eq("all_stage054_window_entries")].iloc[0]
        ai_row = summary[summary["condition"].eq("ai_rank_1_6")].iloc[0]

        self.assertEqual(int(all_row["count"]), 2)
        self.assertAlmostEqual(float(all_row["total_pnl"]), -50.0)
        self.assertEqual(int(ai_row["count"]), 1)
        self.assertAlmostEqual(float(ai_row["total_pnl"]), -100.0)
        self.assertAlmostEqual(float(ai_row["loss_rate_pct"]), 100.0)


if __name__ == "__main__":
    unittest.main()
