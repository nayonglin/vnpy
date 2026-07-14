from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "stage001_fu_sc_t1_beta_gate.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stage001_fu_sc_t1_beta_gate", TOOL_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FuScT1BetaGateTest(unittest.TestCase):
    def test_contract_selection_uses_prior_oi_and_same_contract_prices(self) -> None:
        module = load_module()
        bars = pd.DataFrame(
            [
                ["fu2201", "SHFE", "2022-01-03", 100.0, 100.0],
                ["fu2202", "SHFE", "2022-01-03", 200.0, 80.0],
                ["fu2201", "SHFE", "2022-01-04", 110.0, 10.0],
                ["fu2202", "SHFE", "2022-01-04", 240.0, 1000.0],
                ["fu2201", "SHFE", "2022-01-05", 121.0, 10.0],
                ["fu2202", "SHFE", "2022-01-05", 252.0, 1000.0],
            ],
            columns=["symbol", "exchange", "date", "close", "open_interest"],
        )
        ledger, audit = module.build_t1_product_returns(bars, "fu.SHFE")

        first = ledger.iloc[0]
        self.assertEqual(first["selected_symbol"], "fu2201")
        self.assertAlmostEqual(first["return"], 0.10)
        second = ledger.iloc[1]
        self.assertEqual(second["selected_symbol"], "fu2202")
        self.assertAlmostEqual(second["return"], 0.05)
        self.assertEqual(audit["selection_date_not_before_return_date"], 0)

    def test_event_history_excludes_entry_date_and_requires_fixed_windows(self) -> None:
        module = load_module()
        dates = pd.bdate_range("2021-01-01", periods=127)
        sc_return = np.linspace(-0.02, 0.02, len(dates))
        panel = pd.DataFrame(
            {
                "return_date": dates,
                "fu_selection_date": dates - pd.offsets.BDay(1),
                "fu_selected_symbol": "fu2201",
                "fu_return": sc_return * 1.5,
                "sc_selection_date": dates - pd.offsets.BDay(1),
                "sc_selected_symbol": "sc2201",
                "sc_return": sc_return,
                "fu_selection_is_t1": 1,
                "sc_selection_is_t1": 1,
            }
        )
        events = pd.DataFrame(
            [
                {
                    "event_id": "event",
                    "vt_symbol": "fu2205.SHFE",
                    "entry_date": dates[-1],
                    "directions": "long",
                    "total_original_risk_amount": 1000.0,
                }
            ]
        )
        ledger = module.build_event_beta_ledger(events, panel)
        row = ledger.iloc[0]

        self.assertEqual(row["history_count"], 126)
        self.assertLess(pd.Timestamp(row["history_last_date"]), dates[-1])
        self.assertEqual(row["full126_count"], 126)
        self.assertEqual(row["early63_count"], 63)
        self.assertEqual(row["late63_count"], 63)
        self.assertAlmostEqual(row["full126_beta"], 1.5, places=12)
        self.assertAlmostEqual(row["full126_correlation"], 1.0, places=12)
        self.assertEqual(row["event_beta_pass"], 1)

    def test_missing_selected_contract_does_not_fall_through_to_second_choice(self) -> None:
        module = load_module()
        bars = pd.DataFrame(
            [
                ["sc2201", "INE", "2022-01-03", 100.0, 100.0],
                ["sc2202", "INE", "2022-01-03", 200.0, 80.0],
                ["sc2202", "INE", "2022-01-04", 210.0, 100.0],
            ],
            columns=["symbol", "exchange", "date", "close", "open_interest"],
        )
        ledger, _ = module.build_t1_product_returns(bars, "sc.INE")

        self.assertEqual(ledger.iloc[0]["selected_symbol"], "sc2201")
        self.assertEqual(ledger.iloc[0]["status"], "selected_contract_missing_on_return_date")
        self.assertTrue(pd.isna(ledger.iloc[0]["return"]))


if __name__ == "__main__":
    unittest.main()

