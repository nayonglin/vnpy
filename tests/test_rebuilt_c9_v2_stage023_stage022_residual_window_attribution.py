from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage023_stage022_residual_window_attribution as s023


class Stage023Stage022ResidualWindowAttributionTest(unittest.TestCase):
    def test_select_focus_windows_keeps_target_negative_windows_only(self) -> None:
        worst = pd.DataFrame(
            [
                {
                    "variant": s023.TARGET_VARIANT,
                    "source_start_month": "2022-07",
                    "start_date": "2022-07-15",
                    "end_date": "2023-07-17",
                    "return_pct": -40.5,
                },
                {
                    "variant": "stage022_stage013_guarded_quality",
                    "source_start_month": "2022-07",
                    "start_date": "2022-07-15",
                    "end_date": "2023-07-17",
                    "return_pct": -40.6,
                },
                {
                    "variant": s023.TARGET_VARIANT,
                    "source_start_month": "2024-01",
                    "start_date": "2024-01-02",
                    "end_date": "2025-01-03",
                    "return_pct": 1.0,
                },
            ]
        )

        focus = s023.select_focus_windows(worst, top_n=10)

        self.assertEqual(len(focus), 1)
        self.assertEqual(focus.iloc[0]["source_start_month"], "2022-07")
        self.assertEqual(focus.iloc[0]["variant"], s023.TARGET_VARIANT)

    def test_attribute_focus_window_reconciles_daily_components_to_equity_delta(self) -> None:
        window = pd.Series(
            {
                "variant": s023.TARGET_VARIANT,
                "source_start_month": "2022-07",
                "start_date": "2022-07-15",
                "end_date": "2022-07-19",
                "return_pct": -25.0,
                "period_calendar_days": 369,
                "period_trading_days": 2,
            }
        )
        curves = pd.DataFrame(
            [
                {
                    "condition": s023.TARGET_CONDITION,
                    "requested_start_month": "2022-07",
                    "date": "2022-07-15",
                    "account_equity": 200000.0,
                    "net_pnl": 0.0,
                    "stage022_daily_delta": 0.0,
                    "stage022_cum_delta": 1000.0,
                },
                {
                    "condition": s023.TARGET_CONDITION,
                    "requested_start_month": "2022-07",
                    "date": "2022-07-18",
                    "account_equity": 185000.0,
                    "net_pnl": -20000.0,
                    "stage022_daily_delta": 5000.0,
                    "stage022_cum_delta": 6000.0,
                },
                {
                    "condition": s023.TARGET_CONDITION,
                    "requested_start_month": "2022-07",
                    "date": "2022-07-19",
                    "account_equity": 170000.0,
                    "net_pnl": -10000.0,
                    "stage022_daily_delta": -5000.0,
                    "stage022_cum_delta": 1000.0,
                },
            ]
        )
        lot_deltas = pd.DataFrame(
            [
                {
                    "condition": "stage013_guarded_quality_xsmom12_not_opposed",
                    "requested_start_month": "2022-07",
                    "exit_date": "2022-07-18",
                    "product": "SM.CZCE",
                    "direction": "short",
                    "realized_pnl": 20000.0,
                    "stage022_proxy_delta_pnl": 5000.0,
                },
                {
                    "condition": "stage013_guarded_quality_xsmom12_not_opposed",
                    "requested_start_month": "2022-07",
                    "exit_date": "2022-07-19",
                    "product": "fu.SHFE",
                    "direction": "long",
                    "realized_pnl": -20000.0,
                    "stage022_proxy_delta_pnl": -5000.0,
                },
            ]
        )

        row = s023.attribute_focus_window(window, curves, lot_deltas)

        self.assertAlmostEqual(row["variant_equity_delta"], -30000.0)
        self.assertAlmostEqual(row["base_net_pnl_in_window"], -30000.0)
        self.assertAlmostEqual(row["stage022_delta_in_window"], 0.0)
        self.assertAlmostEqual(row["component_reconciliation_abs_diff"], 0.0)
        self.assertEqual(row["stage022_component_effect"], "neutral")

    def test_attribute_focus_window_marks_proxy_drag_when_delta_is_negative(self) -> None:
        window = pd.Series(
            {
                "variant": s023.TARGET_VARIANT,
                "source_start_month": "2022-07",
                "start_date": "2022-07-15",
                "end_date": "2022-07-18",
                "return_pct": -10.0,
            }
        )
        curves = pd.DataFrame(
            [
                {
                    "condition": s023.TARGET_CONDITION,
                    "requested_start_month": "2022-07",
                    "date": "2022-07-15",
                    "account_equity": 100000.0,
                    "net_pnl": 0.0,
                    "stage022_daily_delta": 0.0,
                },
                {
                    "condition": s023.TARGET_CONDITION,
                    "requested_start_month": "2022-07",
                    "date": "2022-07-18",
                    "account_equity": 90000.0,
                    "net_pnl": -8000.0,
                    "stage022_daily_delta": -2000.0,
                },
            ]
        )
        lot_deltas = pd.DataFrame(
            [
                {
                    "condition": "stage013_guarded_quality_xsmom12_not_opposed",
                    "requested_start_month": "2022-07",
                    "exit_date": "2022-07-18",
                    "product": "fu.SHFE",
                    "direction": "long",
                    "realized_pnl": -8000.0,
                    "stage022_proxy_delta_pnl": -2000.0,
                }
            ]
        )

        row = s023.attribute_focus_window(window, curves, lot_deltas)

        self.assertEqual(row["stage022_component_effect"], "dragged")
        self.assertAlmostEqual(row["stage022_delta_to_loss_abs_pct"], -20.0)
        self.assertEqual(row["selected_lot_count"], 1)


if __name__ == "__main__":
    unittest.main()
