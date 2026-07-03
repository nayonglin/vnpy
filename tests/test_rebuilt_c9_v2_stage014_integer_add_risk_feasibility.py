from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage014_integer_add_risk_feasibility_audit as s014


class Stage014IntegerAddRiskFeasibilityAuditTest(unittest.TestCase):
    def test_integer_extra_lots_show_floor_and_ceil_rounding_gap(self) -> None:
        lots = pd.DataFrame(
            [
                {"selected_volume": 1, "realized_pnl": 400.0},
                {"selected_volume": 4, "realized_pnl": 400.0},
                {"selected_volume": 8, "realized_pnl": 400.0},
            ]
        )

        result, audit = s014.compute_integer_add_risk_lot_deltas(lots)

        self.assertEqual(result["stage014_floor_extra_lots"].tolist(), [0, 1, 2])
        self.assertEqual(result["stage014_ceil_extra_lots"].tolist(), [1, 1, 2])
        self.assertEqual(result["stage014_floor_proxy_delta_pnl"].tolist(), [0.0, 100.0, 100.0])
        self.assertEqual(result["stage014_ceil_proxy_delta_pnl"].tolist(), [400.0, 100.0, 100.0])
        self.assertEqual(audit["floor_zero_extra_lot_count"], 1)

    def test_integer_proxy_curves_apply_floor_and_ceil_delta_on_exit_date(self) -> None:
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
                    "stage014_floor_proxy_delta_pnl": 0.0,
                    "stage014_ceil_proxy_delta_pnl": 400.0,
                }
            ]
        )

        proxy, unmatched = s014.build_integer_proxy_curves(curves, lot_deltas)

        self.assertEqual(unmatched, 0)
        self.assertEqual(float(proxy.loc[1, "stage014_floor_account_equity"]), 151000.0)
        self.assertEqual(float(proxy.loc[1, "stage014_ceil_account_equity"]), 151400.0)


if __name__ == "__main__":
    unittest.main()
