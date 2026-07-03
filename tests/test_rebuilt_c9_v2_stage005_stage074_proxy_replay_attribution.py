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

import stage005_stage074_proxy_replay_attribution as s005


class Stage005Stage074ProxyReplayAttributionTest(unittest.TestCase):
    def test_build_stage070_daily_components_reconstructs_proxy_equity(self) -> None:
        base = pd.DataFrame(
            {
                "requested_start_month": ["2021-07"] * 3,
                "date": pd.to_datetime(["2021-01-01", "2021-01-02", "2021-01-03"]),
                "account_equity": [100.0, 90.0, 80.0],
                "net_pnl": [0.0, -10.0, -10.0],
                "holding_pnl": [0.0, -8.0, -6.0],
                "trading_pnl": [0.0, -2.0, -4.0],
                "commission": [0.0, 0.1, 0.2],
                "slippage": [0.0, 0.4, 0.3],
            }
        )
        lots = pd.DataFrame(
            {
                "candidate_variant": [s005.TARGET_VARIANT],
                "requested_start_month": ["2021-07"],
                "exit_date": ["2021-01-03"],
                "product": ["jm.DCE"],
                "direction": ["long"],
                "stage070_proxy_delta_pnl": [-5.0],
            }
        )

        components = s005.build_stage070_daily_components(base, lots)

        self.assertEqual(components["stage070_equity"].tolist(), [100.0, 90.0, 75.0])
        self.assertEqual(components["stage070_daily_delta"].tolist(), [0.0, -10.0, -15.0])
        self.assertEqual(components["proxy_delta_pnl"].tolist(), [0.0, 0.0, -5.0])

    def test_attribute_stage074_window_applies_ramp_to_base_and_proxy_parts(self) -> None:
        components = pd.DataFrame(
            {
                "requested_start_month": ["2021-07"] * 3,
                "date": pd.to_datetime(["2021-01-01", "2021-01-02", "2021-01-03"]),
                "base_net_pnl": [0.0, -10.0, -10.0],
                "base_holding_pnl": [0.0, -8.0, -6.0],
                "base_trading_pnl": [0.0, -2.0, -4.0],
                "base_commission": [0.0, 0.1, 0.2],
                "base_slippage": [0.0, 0.4, 0.3],
                "proxy_delta_pnl": [0.0, 0.0, -5.0],
                "stage070_daily_delta": [0.0, -10.0, -15.0],
                "stage070_equity": [100.0, 90.0, 75.0],
            }
        )
        window = pd.Series(
            {
                "source_start_month": "2021-07",
                "start_date": "2021-01-01",
                "end_date": "2021-01-03",
                "oracle_return_pct": -20.0,
            }
        )

        row = s005.attribute_stage074_window(
            components,
            window,
            selected_rank=1,
            ramp_floor=0.5,
            ramp_trading_days=2,
        )

        self.assertAlmostEqual(row["stage074_adjusted_net_pnl"], -20.0)
        self.assertAlmostEqual(row["stage074_base_holding_pnl"], -10.0)
        self.assertAlmostEqual(row["stage074_base_trading_pnl"], -5.0)
        self.assertAlmostEqual(row["stage074_proxy_delta_pnl"], -5.0)
        self.assertAlmostEqual(row["base_holding_loss_share_pct"], 50.0)
        self.assertAlmostEqual(row["base_trading_loss_share_pct"], 25.0)
        self.assertAlmostEqual(row["proxy_delta_loss_share_pct"], 25.0)

    def test_summarize_lot_attribution_scales_proxy_delta_by_exit_date_ramp(self) -> None:
        lots = pd.DataFrame(
            {
                "candidate_variant": [s005.TARGET_VARIANT, s005.TARGET_VARIANT],
                "requested_start_month": ["2021-07", "2021-07"],
                "exit_date": ["2021-01-02", "2021-01-03"],
                "product": ["jm.DCE", "rb.SHFE"],
                "direction": ["long", "short"],
                "stage070_proxy_delta_pnl": [-10.0, 20.0],
            }
        )
        window = pd.Series({"source_start_month": "2021-07", "start_date": "2021-01-01", "end_date": "2021-01-03"})
        ramp_by_date = {
            pd.Timestamp("2021-01-02"): 0.5,
            pd.Timestamp("2021-01-03"): 1.0,
        }

        summary = s005.summarize_lot_attribution(lots, window, selected_rank=1, ramp_by_date=ramp_by_date)

        self.assertEqual(len(summary), 2)
        jm = summary[summary["product"].eq("jm.DCE")].iloc[0]
        rb = summary[summary["product"].eq("rb.SHFE")].iloc[0]
        self.assertAlmostEqual(jm["stage074_scaled_proxy_delta_pnl"], -5.0)
        self.assertAlmostEqual(rb["stage074_scaled_proxy_delta_pnl"], 20.0)


if __name__ == "__main__":
    unittest.main()
