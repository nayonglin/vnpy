from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage011_stage010_remaining_left_tail_attribution as s011


class Stage011Stage010RemainingLeftTailAttributionTest(unittest.TestCase):
    def test_focus_windows_keep_stage010_negative_windows_only(self) -> None:
        worst = pd.DataFrame(
            [
                {
                    "variant": "stage010_quality_add_risk_proxy",
                    "source_start_month": "2022-07",
                    "start_date": "2022-07-15",
                    "end_date": "2023-07-17",
                    "return_pct": -41.0,
                },
                {
                    "variant": "stage013_engine",
                    "source_start_month": "2022-07",
                    "start_date": "2022-07-15",
                    "end_date": "2023-07-17",
                    "return_pct": -43.0,
                },
                {
                    "variant": "stage010_quality_add_risk_proxy",
                    "source_start_month": "2024-01",
                    "start_date": "2024-01-02",
                    "end_date": "2025-01-03",
                    "return_pct": 1.0,
                },
            ]
        )

        focus = s011.select_focus_windows(worst, top_n=10)

        self.assertEqual(len(focus), 1)
        self.assertEqual(focus.iloc[0]["source_start_month"], "2022-07")

    def test_window_attribution_splits_base_delta_and_proxy_delta(self) -> None:
        window = pd.Series(
            {
                "source_start_month": "2022-07",
                "start_date": "2022-07-15",
                "end_date": "2023-07-17",
                "return_pct": -10.0,
            }
        )
        curves = pd.DataFrame(
            [
                {
                    "requested_start_month": "2022-07",
                    "date": "2022-07-15",
                    "account_equity": 200000.0,
                    "stage010_account_equity": 210000.0,
                    "stage010_cum_delta": 10000.0,
                },
                {
                    "requested_start_month": "2022-07",
                    "date": "2023-07-17",
                    "account_equity": 150000.0,
                    "stage010_account_equity": 180000.0,
                    "stage010_cum_delta": 30000.0,
                },
            ]
        )
        lot_deltas = pd.DataFrame(
            [
                {
                    "requested_start_month": "2022-07",
                    "exit_date": "2023-01-01",
                    "product": "SM.CZCE",
                    "direction": "short",
                    "realized_pnl": 80000.0,
                    "stage010_proxy_delta_pnl": 20000.0,
                }
            ]
        )
        quality_events = pd.DataFrame(
            [
                {
                    "requested_start_month": "2022-07",
                    "exit_date": "2023-01-01",
                    "product": "SM.CZCE",
                    "direction": "short",
                    "realized_pnl": 80000.0,
                },
                {
                    "requested_start_month": "2022-07",
                    "exit_date": "2023-02-01",
                    "product": "cu.SHFE",
                    "direction": "long",
                    "realized_pnl": -10000.0,
                },
            ]
        )

        row = s011.attribute_focus_window(window, curves, lot_deltas, quality_events)

        self.assertAlmostEqual(row["base_equity_delta"], -50000.0)
        self.assertAlmostEqual(row["proxy_delta_in_window"], 20000.0)
        self.assertAlmostEqual(row["stage010_equity_delta"], -30000.0)
        self.assertAlmostEqual(row["selected_closed_lot_pnl"], 80000.0)
        self.assertAlmostEqual(row["unselected_quality_event_pnl"], -10000.0)
        self.assertAlmostEqual(row["base_delta_minus_quality_event_pnl"], -120000.0)


if __name__ == "__main__":
    unittest.main()
