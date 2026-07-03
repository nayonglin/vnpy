from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage050_jd_true_carry_data_manifest as s050


class Stage050JdTrueCarryDataManifestTest(unittest.TestCase):
    def test_minute_gap_manifest_uses_contract_date_span_from_price_frame(self) -> None:
        missing = pd.DataFrame(
            {
                "contract_vt": ["jd2405.DCE", "cu2607.SHFE"],
                "product_vt_symbol": ["jd.DCE", "cu.SHFE"],
                "minute_file_ready": [False, False],
            }
        )
        product_returns = pd.DataFrame(
            {
                "date": ["2024-03-01", "2024-03-04", "2026-06-01"],
                "product_vt_symbol": ["jd.DCE", "jd.DCE", "cu.SHFE"],
                "main_contract_vt": ["jd2405.DCE", "jd2405.DCE", "cu2607.SHFE"],
            }
        )

        manifest = s050.build_minute_gap_manifest(missing, product_returns)

        jd = manifest[manifest["contract_vt"].eq("jd2405.DCE")].iloc[0]
        self.assertEqual(jd["request_start_date"], "2024-03-01")
        self.assertEqual(jd["request_end_date"], "2024-03-04")
        self.assertEqual(jd["required_bar_interval"], "1m")
        self.assertEqual(jd["preferred_source"], "tqsdk_or_vendor_historical_minute")

    def test_contract_spec_manifest_requires_daily_margin_series_for_jd(self) -> None:
        contract_specs = pd.DataFrame(
            {
                "product_vt_symbol": ["jd.DCE"],
                "size": [10.0],
                "slippage": [1.0],
                "price_tick": [1.0],
                "margin_ratio": [0.0],
                "exact_spec_ready": [False],
                "blocking_reason": ["missing_margin_ratio"],
            }
        )

        manifest = s050.build_contract_spec_manifest(contract_specs)

        row = manifest.iloc[0]
        self.assertEqual(row["product_vt_symbol"], "jd.DCE")
        self.assertEqual(row["static_spec_status"], "size_tick_ready_from_dce_contract")
        self.assertEqual(row["required_margin_granularity"], "contract_daily")
        self.assertIn("margin_ratio", row["required_fields"])

    def test_decision_is_data_first_and_never_strategy_candidate(self) -> None:
        minute_manifest = pd.DataFrame([{"contract_vt": "jd2405.DCE"}])
        spec_manifest = pd.DataFrame([{"product_vt_symbol": "jd.DCE"}])

        decision = s050.make_stage050_decision(minute_manifest, spec_manifest)

        self.assertEqual(decision["decision"], "stage050_jd_true_carry_data_manifest_ready_no_strategy_candidate")
        self.assertEqual(decision["minute_gap_contract_count"], 1)
        self.assertEqual(decision["contract_spec_request_count"], 1)
        self.assertFalse(decision["ready_for_true_ledger_replay"])
        self.assertFalse(decision["strategy_rule_created"])
        self.assertFalse(decision["order_api_called"])
        self.assertFalse(decision["ctp_connected"])


if __name__ == "__main__":
    unittest.main()
