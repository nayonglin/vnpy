from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage038_akshare_option_history_coverage_audit as s038


class Stage038AkshareOptionHistoryCoverageAuditTest(unittest.TestCase):
    def test_single_successful_probe_is_sample_ok_not_continuous(self) -> None:
        probe = {
            "target_product": "MA.CZCE",
            "exchange": "CZCE",
            "function_name": "option_hist_czce",
            "probe_year": 2024,
            "status": "ok",
            "rows": 220,
            "has_iv_column": True,
            "has_oi_column": True,
            "has_publish_timestamp": False,
        }

        classified = s038.classify_probe_outcome(probe)

        self.assertEqual(classified["probe_status"], "sample_ok_not_continuous")
        self.assertFalse(classified["schema_ready_probe"])
        self.assertFalse(classified["rule_candidate_allowed"])
        self.assertIn("single_or_sparse_year_probe", classified["blocking_reasons"])
        self.assertIn("missing_publish_timestamp", classified["blocking_reasons"])

    def test_product_coverage_requires_min_years_and_pit_timestamp(self) -> None:
        probes = pd.DataFrame(
            [
                s038.classify_probe_outcome(
                    {
                        "target_product": "MA.CZCE",
                        "exchange": "CZCE",
                        "probe_year": 2021,
                        "status": "ok",
                        "rows": 120,
                        "has_iv_column": True,
                        "has_oi_column": True,
                        "has_publish_timestamp": False,
                    }
                ),
                s038.classify_probe_outcome(
                    {
                        "target_product": "MA.CZCE",
                        "exchange": "CZCE",
                        "probe_year": 2024,
                        "status": "ok",
                        "rows": 220,
                        "has_iv_column": True,
                        "has_oi_column": True,
                        "has_publish_timestamp": False,
                    }
                ),
            ]
        )

        coverage = s038.summarize_product_coverage(probes, min_years_hit=3)
        row = coverage[coverage["target_product"].eq("MA.CZCE")].iloc[0]

        self.assertEqual(row["ok_year_count"], 2)
        self.assertEqual(row["coverage_status"], "sample_years_ok_not_pit_continuous")
        self.assertFalse(bool(row["schema_ready_product"]))
        self.assertIn("less_than_min_years_hit", row["blocking_reasons"])
        self.assertIn("no_publish_timestamp_in_successful_probes", row["blocking_reasons"])

    def test_dce_single_failure_keeps_alternative_probe_status(self) -> None:
        probe = {
            "target_product": "jm.DCE",
            "exchange": "DCE",
            "function_name": "option_hist_dce",
            "probe_year": 2024,
            "status": "error",
            "rows": 0,
            "error_type": "JSONDecodeError",
            "error_message": "Expecting value: line 1 column 1 (char 0)",
        }

        classified = s038.classify_probe_outcome(probe)

        self.assertEqual(classified["probe_status"], "endpoint_or_date_probe_failed_needs_alternative_probe")
        self.assertFalse(classified["schema_ready_probe"])
        self.assertFalse(classified["rule_candidate_allowed"])
        self.assertIn("dce_probe_failed_not_exchange_wide_rejection", classified["blocking_reasons"])

    def test_decision_stays_data_contract_when_no_product_is_schema_ready(self) -> None:
        product_coverage = pd.DataFrame(
            [
                {
                    "target_product": "MA.CZCE",
                    "exchange": "CZCE",
                    "schema_ready_product": False,
                    "coverage_status": "sample_years_ok_not_pit_continuous",
                },
                {
                    "target_product": "jm.DCE",
                    "exchange": "DCE",
                    "schema_ready_product": False,
                    "coverage_status": "no_successful_probe_yet",
                },
            ]
        )
        exchange_coverage = s038.summarize_exchange_coverage(product_coverage)
        probes = pd.DataFrame(
            [
                {
                    "target_product": "MA.CZCE",
                    "exchange": "CZCE",
                    "status": "ok",
                    "rows": 100,
                    "probe_status": "sample_ok_not_continuous",
                }
            ]
        )

        decision = s038.make_stage038_decision(product_coverage, exchange_coverage, probes)

        self.assertEqual(decision["decision"], "stage038_akshare_option_history_not_continuous_keep_data_contract")
        self.assertEqual(decision["schema_ready_product_count"], 0)
        self.assertEqual(decision["immediate_strategy_candidate_count"], 0)
        self.assertFalse(decision["strategy_rule_created"])
        self.assertFalse(decision["true_engine"])
        self.assertFalse(decision["order_api_called"])
        self.assertFalse(decision["ctp_connected"])


if __name__ == "__main__":
    unittest.main()
