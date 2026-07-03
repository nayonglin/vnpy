from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage010_quality_add_risk_proxy as s010


class Stage010QualityAddRiskProxyTest(unittest.TestCase):
    def test_select_quality_events_uses_rank_and_selected_volume_only(self) -> None:
        events = pd.DataFrame(
            [
                {"ai_product_pool_rank": 1, "selected_volume": 2, "realized_pnl": 100.0},
                {"ai_product_pool_rank": 8, "selected_volume": 1, "realized_pnl": 200.0},
                {"ai_product_pool_rank": 9, "selected_volume": 3, "realized_pnl": 300.0},
            ]
        )

        selected = s010.select_stage010_quality_events(events)

        self.assertEqual(len(selected), 1)
        self.assertEqual(float(selected.iloc[0]["realized_pnl"]), 100.0)

    def test_proxy_curve_applies_quality_delta_on_exit_date(self) -> None:
        curves = pd.DataFrame(
            [
                {"requested_start_month": "2020-01", "date": "2020-01-10", "account_equity": 150000.0},
                {"requested_start_month": "2020-01", "date": "2020-01-15", "account_equity": 151000.0},
            ]
        )
        lot_deltas = pd.DataFrame(
            [
                {
                    "requested_start_month": "2020-01",
                    "exit_date": pd.Timestamp("2020-01-15"),
                    "stage010_proxy_delta_pnl": 25.0,
                }
            ]
        )

        proxy, unmatched = s010.build_proxy_curves(curves, lot_deltas)

        self.assertEqual(unmatched, 0)
        self.assertEqual(float(proxy.loc[1, "stage010_account_equity"]), 151025.0)


if __name__ == "__main__":
    unittest.main()
