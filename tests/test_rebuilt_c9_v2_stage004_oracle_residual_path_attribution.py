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

import stage004_oracle_residual_path_attribution as s004


class Stage004OracleResidualPathAttributionTest(unittest.TestCase):
    def test_attribute_window_splits_daily_pnl_and_account_pressure(self) -> None:
        curve = pd.DataFrame(
            {
                "requested_start_month": ["2021-07"] * 4,
                "date": pd.to_datetime(["2021-10-01", "2021-10-02", "2021-10-03", "2021-10-04"]),
                "account_equity": [100.0, 92.0, 88.0, 80.0],
                "net_pnl": [0.0, -8.0, -4.0, -8.0],
                "holding_pnl": [0.0, -7.0, -3.0, -7.0],
                "trading_pnl": [0.0, -1.0, -1.0, -1.0],
                "commission": [0.0, 0.2, 0.1, 0.2],
                "slippage": [0.0, 0.3, 0.2, 0.3],
                "broker10_margin_to_equity_pct": [10.0, 85.0, 90.0, 50.0],
                "c3_active_products": [1, 4, 5, 2],
                "drawdown_pct": [0.0, -8.0, -12.0, -20.0],
            }
        )
        window = pd.Series(
            {
                "source_start_month": "2021-07",
                "start_date": "2021-10-01",
                "end_date": "2021-10-04",
                "oracle_return_pct": -20.0,
            }
        )

        row = s004.attribute_window(curve, window, selected_rank=1)

        self.assertEqual(row["window_id"], "001_2021-07_2021-10-01_2021-10-04")
        self.assertAlmostEqual(row["equity_change"], -20.0)
        self.assertAlmostEqual(row["net_pnl"], -20.0)
        self.assertAlmostEqual(row["holding_pnl"], -17.0)
        self.assertAlmostEqual(row["trading_pnl"], -3.0)
        self.assertAlmostEqual(row["holding_loss_share_pct"], 85.0)
        self.assertEqual(row["dominant_loss_driver"], "holding_pnl_dominant")
        self.assertEqual(row["broker10_pressure_flag"], 1)
        self.assertEqual(row["active4_pressure_flag"], 1)

    def test_summarize_attributions_identifies_holding_dominance(self) -> None:
        attrs = pd.DataFrame(
            [
                {"net_pnl": -20.0, "holding_pnl": -17.0, "trading_pnl": -3.0, "commission": 0.5, "slippage": 0.8},
                {"net_pnl": -10.0, "holding_pnl": -8.0, "trading_pnl": -2.0, "commission": 0.3, "slippage": 0.4},
            ]
        )

        summary = s004.summarize_attributions(attrs)

        self.assertEqual(summary["window_count"], 2)
        self.assertAlmostEqual(summary["net_pnl"], -30.0)
        self.assertAlmostEqual(summary["holding_loss_share_pct"], 83.33333333333334)
        self.assertEqual(summary["dominant_loss_driver"], "holding_pnl_dominant")

    def test_make_decision_routes_holding_dominance_to_position_replay(self) -> None:
        summary = {
            "window_count": 100,
            "holding_loss_share_pct": 78.0,
            "trading_loss_share_pct": 22.0,
            "broker10_pressure_window_count": 12,
            "active4_pressure_window_count": 70,
        }

        decision = s004.make_decision(summary)

        self.assertEqual(decision["decision"], "stage004_holding_path_dominant_need_position_replay")
        self.assertEqual(decision["position_replay_recommended"], 1)


if __name__ == "__main__":
    unittest.main()

