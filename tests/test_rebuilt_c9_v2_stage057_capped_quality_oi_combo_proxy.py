from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage057_capped_quality_oi_combo_proxy as s057


class Stage057CappedQualityOiComboProxyTest(unittest.TestCase):
    def test_combo_event_deltas_cap_overlap_and_preserve_exit_date(self) -> None:
        events = pd.DataFrame(
            [
                {
                    "module": "a",
                    "event_key": "k1",
                    "requested_start_month": "2020-01",
                    "entry_date": "2020-01-02",
                    "exit_date": "2020-01-03",
                    "vt_symbol": "rb2005.SHFE",
                    "product": "rb.SHFE",
                    "direction": "long",
                    "realized_pnl": 100.0,
                    "add_fraction": 0.35,
                },
                {
                    "module": "b",
                    "event_key": "k1",
                    "requested_start_month": "2020-01",
                    "entry_date": "2020-01-02",
                    "exit_date": "2020-01-03",
                    "vt_symbol": "rb2005.SHFE",
                    "product": "rb.SHFE",
                    "direction": "long",
                    "realized_pnl": 100.0,
                    "add_fraction": 0.30,
                },
            ]
        )
        spec = s057.ComboSpec("combo", ("a", "b"), "sum_cap", 0.50, "test")

        result = s057.build_combo_event_deltas(events, spec)

        self.assertEqual(len(result), 1)
        self.assertEqual(str(result.loc[0, "exit_date"].date()), "2020-01-03")
        self.assertAlmostEqual(float(result.loc[0, "combo_fraction"]), 0.50)
        self.assertAlmostEqual(float(result.loc[0, "combo_delta_pnl"]), 50.0)

    def test_proxy_curves_apply_combo_delta_by_start_and_exit_date(self) -> None:
        base = pd.DataFrame(
            [
                {
                    "variant": "stage013_account_state_pilot_base",
                    "source_type": "true_engine_base",
                    "requested_start_month": "2020-01",
                    "date": pd.Timestamp("2020-01-02"),
                    "equity": 150000.0,
                },
                {
                    "variant": "stage013_account_state_pilot_base",
                    "source_type": "true_engine_base",
                    "requested_start_month": "2020-01",
                    "date": pd.Timestamp("2020-01-03"),
                    "equity": 151000.0,
                },
            ]
        )
        deltas = pd.DataFrame(
            [
                {
                    "variant": "combo",
                    "requested_start_month": "2020-01",
                    "exit_date": pd.Timestamp("2020-01-03"),
                    "combo_delta_pnl": 50.0,
                }
            ]
        )

        curves, unmatched = s057.build_proxy_curves(base, deltas)

        self.assertEqual(unmatched, 0)
        self.assertAlmostEqual(float(curves.loc[curves["date"].eq(pd.Timestamp("2020-01-03")), "equity"].iloc[0]), 151050.0)


if __name__ == "__main__":
    unittest.main()
