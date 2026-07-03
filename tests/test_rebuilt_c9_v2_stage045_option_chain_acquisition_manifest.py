from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage045_option_chain_acquisition_manifest as s045


class Stage045OptionChainAcquisitionManifestTest(unittest.TestCase):
    def test_target_manifest_includes_jd_and_current_ai_pool_products(self) -> None:
        manifest = s045.build_target_product_manifest()

        products = set(manifest["target_product"].astype(str))

        self.assertIn("jd.DCE", products)
        self.assertIn("SA.CZCE", products)
        self.assertIn("FG.CZCE", products)
        self.assertIn("SM.CZCE", products)
        self.assertTrue(manifest["required_if_listed"].astype(bool).all())
        self.assertTrue((manifest["requested_start_date"] == "2018-01-01").all())
        self.assertTrue((manifest["requested_end_date"] == "2026-06-30").all())

    def test_complete_vendor_option_chain_schema_is_accepted_for_readonly_signal_audit(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "quote_datetime": "2026-06-16 15:00:00",
                    "publish_datetime": "2026-06-16 15:01:00",
                    "underlying_product": "jd.DCE",
                    "underlying_symbol": "jd2609.DCE",
                    "option_symbol": "jd2609-C-3600.DCE",
                    "exchange": "DCE",
                    "expiry_date": "2026-08-07",
                    "strike": 3600,
                    "option_type": "C",
                    "underlying_price": 3550.0,
                    "settlement": 120.0,
                    "bid_price": 118.0,
                    "ask_price": 122.0,
                    "implied_volatility": 0.22,
                    "delta": 0.45,
                    "open_interest": 1000,
                    "volume": 200,
                    "source_system": "authorized_vendor",
                    "source_file_hash": "abc123",
                }
            ]
        )

        result = s045.validate_option_chain_schema(frame)

        self.assertTrue(result["schema_complete"])
        self.assertTrue(result["pit_rule_audit_allowed"])
        self.assertTrue(result["has_iv"])
        self.assertTrue(result["has_delta"])
        self.assertTrue(result["has_open_interest"])
        self.assertTrue(result["has_volume"])
        self.assertTrue(result["has_publish_or_receive_time"])

    def test_schema_missing_pit_timestamp_or_hash_is_blocked(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "quote_datetime": "2026-06-16 15:00:00",
                    "underlying_product": "jd.DCE",
                    "underlying_symbol": "jd2609.DCE",
                    "option_symbol": "jd2609-C-3600.DCE",
                    "exchange": "DCE",
                    "expiry_date": "2026-08-07",
                    "strike": 3600,
                    "option_type": "C",
                    "underlying_price": 3550.0,
                    "implied_volatility": 0.22,
                    "delta": 0.45,
                    "open_interest": 1000,
                    "volume": 200,
                    "source_system": "authorized_vendor",
                }
            ]
        )

        result = s045.validate_option_chain_schema(frame)

        self.assertFalse(result["schema_complete"])
        self.assertFalse(result["pit_rule_audit_allowed"])
        self.assertIn("missing_publish_or_receive_time", result["blocking_reasons"])
        self.assertIn("missing_source_hash", result["blocking_reasons"])

    def test_non_option_probe_artifact_is_not_schema_candidate(self) -> None:
        row = s045.classify_option_chain_path(
            Path("research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage038/probe_results.csv"),
            1000,
        )

        self.assertEqual(row["asset_kind"], "research_or_probe_artifact")
        self.assertFalse(row["schema_validation_required"])
        self.assertFalse(row["pit_rule_audit_allowed"])
        self.assertIn("not_vendor_option_chain_history", row["blocking_reason"])

    def test_decision_without_accepted_option_chain_stays_data_first(self) -> None:
        readiness = pd.DataFrame(
            [
                {
                    "path": "research/lines/a/outputs/stage038/probe.csv",
                    "asset_kind": "research_or_probe_artifact",
                    "schema_complete": False,
                    "pit_rule_audit_allowed": False,
                    "accepted_option_chain_dataset": False,
                }
            ]
        )
        manifest = s045.build_target_product_manifest()

        decision = s045.make_stage045_decision(readiness, manifest)

        self.assertEqual(decision["decision"], "stage045_option_chain_acquisition_manifest_data_first_no_accepted_dataset")
        self.assertEqual(decision["accepted_option_chain_dataset_count"], 0)
        self.assertGreaterEqual(decision["target_product_count"], 14)
        self.assertEqual(decision["immediate_strategy_candidate_count"], 0)
        self.assertFalse(decision["strategy_rule_created"])
        self.assertFalse(decision["true_engine"])
        self.assertFalse(decision["order_api_called"])
        self.assertFalse(decision["ctp_connected"])


if __name__ == "__main__":
    unittest.main()
