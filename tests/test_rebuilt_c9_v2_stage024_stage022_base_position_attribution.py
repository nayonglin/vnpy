from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage024_stage022_base_position_attribution as s024


class Stage024Stage022BasePositionAttributionTest(unittest.TestCase):
    def test_prepare_positions_infers_product_and_direction(self) -> None:
        raw = pd.DataFrame(
            [
                {
                    "requested_start_month": "2022-07",
                    "date": "2022-07-18",
                    "vt_symbol": "rb2210.SHFE",
                    "start_pos": -2,
                    "end_pos": -1,
                    "pos_change": 1,
                    "trade_count": 1,
                    "holding_pnl": -100.0,
                    "trading_pnl": 10.0,
                    "commission": 0.5,
                    "slippage": 1.0,
                    "net_pnl": -91.5,
                },
                {
                    "requested_start_month": "2022-07",
                    "date": "2022-07-18",
                    "vt_symbol": "fu2209.SHFE",
                    "start_pos": 0,
                    "end_pos": 3,
                    "pos_change": 3,
                    "trade_count": 1,
                    "holding_pnl": 0.0,
                    "trading_pnl": -30.0,
                    "commission": 0.5,
                    "slippage": 1.0,
                    "net_pnl": -31.5,
                },
            ]
        )

        prepared = s024.prepare_positions(raw)

        by_symbol = {row["vt_symbol"]: row for row in prepared.to_dict("records")}
        self.assertEqual(by_symbol["rb2210.SHFE"]["product"], "rb.SHFE")
        self.assertEqual(by_symbol["rb2210.SHFE"]["direction"], "short")
        self.assertEqual(by_symbol["fu2209.SHFE"]["product"], "fu.SHFE")
        self.assertEqual(by_symbol["fu2209.SHFE"]["direction"], "long")

    def test_attribute_window_positions_separates_existing_and_new_positions(self) -> None:
        positions = pd.DataFrame(
            [
                {
                    "requested_start_month": "2022-07",
                    "date": "2022-07-15",
                    "vt_symbol": "rb2210.SHFE",
                    "start_pos": -2,
                    "end_pos": -2,
                    "pos_change": 0,
                    "trade_count": 0,
                    "holding_pnl": 0.0,
                    "trading_pnl": 0.0,
                    "commission": 0.0,
                    "slippage": 0.0,
                    "net_pnl": 0.0,
                },
                {
                    "requested_start_month": "2022-07",
                    "date": "2022-07-18",
                    "vt_symbol": "rb2210.SHFE",
                    "start_pos": -2,
                    "end_pos": -2,
                    "pos_change": 0,
                    "trade_count": 0,
                    "holding_pnl": -100.0,
                    "trading_pnl": 0.0,
                    "commission": 0.0,
                    "slippage": 0.0,
                    "net_pnl": -100.0,
                },
                {
                    "requested_start_month": "2022-07",
                    "date": "2022-07-18",
                    "vt_symbol": "fu2209.SHFE",
                    "start_pos": 0,
                    "end_pos": 1,
                    "pos_change": 1,
                    "trade_count": 1,
                    "holding_pnl": 0.0,
                    "trading_pnl": -30.0,
                    "commission": 0.5,
                    "slippage": 1.0,
                    "net_pnl": -31.5,
                },
            ]
        )
        window = pd.Series(
            {
                "source_start_month": "2022-07",
                "start_date": "2022-07-15",
                "end_date": "2022-07-18",
                "return_pct": -10.0,
            }
        )

        detail = s024.attribute_window_positions(positions, window, selected_rank=1)

        by_bucket = {
            row["source_bucket"]: row
            for row in detail.sort_values("source_bucket").to_dict("records")
        }
        self.assertAlmostEqual(by_bucket["existing_at_window_start"]["net_pnl"], -100.0)
        self.assertAlmostEqual(by_bucket["opened_or_traded_after_window_start"]["net_pnl"], -31.5)
        self.assertEqual(by_bucket["existing_at_window_start"]["product"], "rb.SHFE")
        self.assertEqual(by_bucket["opened_or_traded_after_window_start"]["product"], "fu.SHFE")

    def test_window_validation_reconciles_position_net_pnl_to_stage023_base_net_pnl(self) -> None:
        focus = pd.DataFrame(
            [
                {
                    "source_start_month": "2022-07",
                    "start_date": "2022-07-15",
                    "end_date": "2022-07-18",
                    "return_pct": -10.0,
                }
            ]
        )
        positions = pd.DataFrame(
            [
                {
                    "requested_start_month": "2022-07",
                    "date": "2022-07-18",
                    "vt_symbol": "rb2210.SHFE",
                    "start_pos": -1,
                    "end_pos": -1,
                    "pos_change": 0,
                    "trade_count": 0,
                    "holding_pnl": -100.0,
                    "trading_pnl": 0.0,
                    "commission": 0.0,
                    "slippage": 0.0,
                    "net_pnl": -100.0,
                }
            ]
        )
        stage023 = pd.DataFrame(
            [
                {
                    "source_start_month": "2022-07",
                    "start_date": "2022-07-15",
                    "end_date": "2022-07-18",
                    "base_net_pnl_in_window": -100.0,
                }
            ]
        )

        validation = s024.build_window_validation(focus, positions, stage023)

        self.assertEqual(len(validation), 1)
        self.assertAlmostEqual(float(validation.iloc[0]["position_net_pnl"]), -100.0)
        self.assertAlmostEqual(float(validation.iloc[0]["base_net_pnl_abs_diff"]), 0.0)


if __name__ == "__main__":
    unittest.main()
