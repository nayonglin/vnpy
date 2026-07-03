from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage013_guarded_quality_add_risk_proxy as s013


class Stage013GuardedQualityAddRiskProxyTest(unittest.TestCase):
    def test_select_guarded_quality_events_keeps_only_risk_multiplier_below_2(self) -> None:
        lots = pd.DataFrame(
            [
                {"risk_multiplier": 1.0, "realized_pnl": 100.0},
                {"risk_multiplier": 2.0, "realized_pnl": 200.0},
                {"risk_multiplier": None, "realized_pnl": 300.0},
            ]
        )

        selected = s013.select_guarded_quality_events(lots)

        self.assertEqual(len(selected), 1)
        self.assertEqual(float(selected.iloc[0]["realized_pnl"]), 100.0)

    def test_build_guarded_lot_deltas_recomputes_stage013_delta(self) -> None:
        lots = pd.DataFrame(
            [
                {
                    "risk_multiplier": 1.0,
                    "realized_pnl": 400.0,
                    "stage010_proxy_delta_pnl": 100.0,
                }
            ]
        )

        guarded, audit = s013.build_guarded_lot_deltas(lots)

        self.assertEqual(audit["stage010_selected_lot_count"], 1)
        self.assertEqual(audit["stage013_guarded_lot_count"], 1)
        self.assertEqual(guarded.iloc[0]["stage013_selector"], s013.SELECTOR_NAME)
        self.assertAlmostEqual(float(guarded.iloc[0]["stage013_proxy_delta_pnl"]), 100.0)

    def test_proxy_curve_applies_guarded_delta_on_exit_date(self) -> None:
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
                    "stage013_proxy_delta_pnl": 25.0,
                }
            ]
        )

        proxy, unmatched = s013.build_proxy_curves(curves, lot_deltas)

        self.assertEqual(unmatched, 0)
        self.assertEqual(float(proxy.loc[1, "stage013_guarded_account_equity"]), 151025.0)


if __name__ == "__main__":
    unittest.main()
