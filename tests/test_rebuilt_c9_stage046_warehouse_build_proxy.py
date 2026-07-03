import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
sys.path.insert(0, str(TOOLS))

from stage046_warehouse_build_add_risk_proxy import (  # noqa: E402
    _build_proxy_curves,
    select_warehouse_build_lots,
)


class Stage046WarehouseBuildProxyTest(unittest.TestCase):
    def test_selector_uses_only_positive_t1_warehouse_change(self) -> None:
        lots = pd.DataFrame(
            [
                {"external_warehouse_change_20d_sum": 10.0, "realized_pnl": 100.0},
                {"external_warehouse_change_20d_sum": 0.0, "realized_pnl": 200.0},
                {"external_warehouse_change_20d_sum": -5.0, "realized_pnl": 300.0},
                {"external_warehouse_change_20d_sum": None, "realized_pnl": 400.0},
            ]
        )

        selected = select_warehouse_build_lots(lots)

        self.assertEqual(len(selected), 1)
        self.assertEqual(float(selected.iloc[0]["realized_pnl"]), 100.0)

    def test_proxy_curve_applies_exit_date_delta(self) -> None:
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
                    "stage046_proxy_delta_pnl": 250.0,
                }
            ]
        )

        proxy, unmatched = _build_proxy_curves(curves, lot_deltas)

        self.assertEqual(unmatched, 0)
        self.assertEqual(float(proxy.loc[1, "stage046_account_equity"]), 151250.0)
        self.assertEqual(float(proxy.loc[1, "stage046_cum_delta"]), 250.0)


if __name__ == "__main__":
    unittest.main()
