from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage037_option_iv_skew_source_readiness as s037


class Stage037OptionIvSkewSourceReadinessTest(unittest.TestCase):
    def test_calc_only_source_is_not_historical_pit_chain(self) -> None:
        source = {
            "source_id": "tqsdk_tafunc",
            "source_type": "sdk_calc",
            "calc_iv_available": 1,
            "historical_chain_available": 0,
            "pit_timestamp_available": 0,
            "target_products_with_listed_option": 0,
            "target_products_total": 10,
            "probe_success_count": 0,
        }

        classified = s037.classify_option_source(source)

        self.assertEqual(classified["source_status"], "compute_only_no_pit_history")
        self.assertFalse(classified["schema_ready_for_signal_audit"])
        self.assertFalse(classified["rule_candidate_allowed"])
        self.assertIn("no_historical_chain", classified["blocking_reasons"])

    def test_partial_public_probe_cannot_be_promoted_to_rule_data(self) -> None:
        source = {
            "source_id": "akshare_exchange_option_daily",
            "source_type": "public_endpoint",
            "calc_iv_available": 1,
            "historical_chain_available": 1,
            "pit_timestamp_available": 0,
            "target_products_with_listed_option": 3,
            "target_products_total": 11,
            "probe_success_count": 2,
            "probe_error_count": 1,
            "continuous_years_ready": 0,
        }

        classified = s037.classify_option_source(source)

        self.assertEqual(classified["source_status"], "partial_public_endpoint_probe_no_rule")
        self.assertFalse(classified["schema_ready_for_signal_audit"])
        self.assertFalse(classified["rule_candidate_allowed"])
        self.assertIn("incomplete_target_product_coverage", classified["blocking_reasons"])
        self.assertIn("no_continuous_2018_2026_history", classified["blocking_reasons"])

    def test_target_product_coverage_marks_jd_as_no_listed_option(self) -> None:
        coverage = s037.build_target_product_option_coverage()
        jd = coverage[coverage["target_product"].eq("jd.DCE")].iloc[0]

        self.assertFalse(bool(jd["has_listed_option"]))
        self.assertEqual(jd["option_symbol_name"], "")
        self.assertIn("no_listed_commodity_option", jd["coverage_blocking_reason"])

    def test_decision_disables_strategy_when_sources_are_not_schema_ready(self) -> None:
        sources = pd.DataFrame(
            [
                s037.classify_option_source(
                    {
                        "source_id": "tqsdk_tafunc",
                        "source_type": "sdk_calc",
                        "calc_iv_available": 1,
                        "historical_chain_available": 0,
                        "pit_timestamp_available": 0,
                        "target_products_with_listed_option": 0,
                        "target_products_total": 10,
                        "probe_success_count": 0,
                    }
                ),
                s037.classify_option_source(
                    {
                        "source_id": "akshare_exchange_option_daily",
                        "source_type": "public_endpoint",
                        "calc_iv_available": 1,
                        "historical_chain_available": 1,
                        "pit_timestamp_available": 0,
                        "target_products_with_listed_option": 3,
                        "target_products_total": 11,
                        "probe_success_count": 1,
                        "continuous_years_ready": 0,
                    }
                ),
            ]
        )
        coverage = s037.build_target_product_option_coverage()

        decision = s037.make_option_readiness_decision(sources, coverage)

        self.assertEqual(decision["decision"], "stage037_option_iv_skew_sources_not_rule_ready_data_contract_required")
        self.assertEqual(decision["immediate_strategy_candidate_count"], 0)
        self.assertFalse(decision["strategy_rule_created"])
        self.assertFalse(decision["true_engine"])
        self.assertFalse(decision["order_api_called"])
        self.assertFalse(decision["ctp_connected"])


if __name__ == "__main__":
    unittest.main()
