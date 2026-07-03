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

import stage006_stage013_base_holding_position_attribution as s006


class Stage006Stage013BaseHoldingPositionAttributionTest(unittest.TestCase):
    def test_attribute_window_positions_splits_existing_and_new_positions_with_ramp(self) -> None:
        positions = pd.DataFrame(
            {
                "requested_start_month": ["2021-07"] * 5,
                "date": pd.to_datetime(
                    ["2021-01-01", "2021-01-02", "2021-01-03", "2021-01-02", "2021-01-03"]
                ),
                "vt_symbol": ["rb2205.SHFE", "rb2205.SHFE", "rb2205.SHFE", "jm2205.DCE", "jm2205.DCE"],
                "start_pos": [0.0, 1.0, 1.0, 0.0, -1.0],
                "end_pos": [1.0, 1.0, 1.0, -1.0, -1.0],
                "pos_change": [1.0, 0.0, 0.0, -1.0, 0.0],
                "trade_count": [1.0, 0.0, 0.0, 1.0, 0.0],
                "holding_pnl": [0.0, -10.0, -20.0, 0.0, -6.0],
                "trading_pnl": [0.0, 0.0, 0.0, -2.0, 0.0],
                "commission": [0.0, 0.0, 0.0, 0.5, 0.0],
                "slippage": [0.0, 0.0, 0.0, 1.0, 0.0],
                "net_pnl": [0.0, -10.0, -20.0, -3.5, -6.0],
            }
        )
        window = pd.Series(
            {
                "source_start_month": "2021-07",
                "start_date": "2021-01-01",
                "end_date": "2021-01-03",
            }
        )

        detail = s006.attribute_window_positions(
            positions,
            window,
            selected_rank=1,
            ramp_floor=0.5,
            ramp_trading_days=2,
        )

        existing = detail[detail["source_bucket"].eq("existing_at_window_start")].iloc[0]
        opened = detail[detail["source_bucket"].eq("opened_or_traded_after_window_start")].iloc[0]
        self.assertEqual(existing["product"], "rb.SHFE")
        self.assertEqual(existing["direction"], "long")
        self.assertAlmostEqual(existing["stage074_scaled_holding_pnl"], -25.0)
        self.assertEqual(opened["product"], "jm.DCE")
        self.assertEqual(opened["direction"], "short")
        self.assertAlmostEqual(opened["stage074_scaled_holding_pnl"], -6.0)
        self.assertAlmostEqual(opened["stage074_scaled_trading_pnl"], -1.0)
        self.assertAlmostEqual(opened["stage074_scaled_cost"], 0.75)

    def test_summarize_position_detail_identifies_holding_dominance(self) -> None:
        detail = pd.DataFrame(
            [
                {
                    "product": "rb.SHFE",
                    "direction": "long",
                    "source_bucket": "existing_at_window_start",
                    "stage074_scaled_holding_pnl": -25.0,
                    "stage074_scaled_trading_pnl": 0.0,
                    "stage074_scaled_cost": 0.0,
                    "stage074_scaled_net_pnl": -25.0,
                    "window_id": "001_a",
                    "source_start_month": "2021-07",
                },
                {
                    "product": "jm.DCE",
                    "direction": "short",
                    "source_bucket": "opened_or_traded_after_window_start",
                    "stage074_scaled_holding_pnl": -6.0,
                    "stage074_scaled_trading_pnl": -1.0,
                    "stage074_scaled_cost": 0.75,
                    "stage074_scaled_net_pnl": -7.75,
                    "window_id": "001_a",
                    "source_start_month": "2021-07",
                },
            ]
        )

        summary = s006.summarize_position_detail(detail)

        self.assertEqual(summary["row_count"], 2)
        self.assertAlmostEqual(summary["holding_loss_share_pct"], 94.65648854961832)
        self.assertEqual(summary["dominant_loss_driver"], "position_holding_pnl_dominant")


if __name__ == "__main__":
    unittest.main()
