from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage039_dce_option_endpoint_forensics as s039


class Stage039DceOptionEndpointForensicsTest(unittest.TestCase):
    def test_legacy_export_payload_uses_zero_based_month_and_option_trade_type(self) -> None:
        payload = s039.build_legacy_export_payload(variety_code="jd", trade_date="20251016")

        self.assertEqual(payload["dayQuotes.variety"], "jd")
        self.assertEqual(payload["dayQuotes.trade_type"], "1")
        self.assertEqual(payload["year"], "2025")
        self.assertEqual(payload["month"], "9")
        self.assertEqual(payload["day"], "16")
        self.assertEqual(payload["exportFlag"], "excel")

    def test_json_endpoint_html_or_empty_response_is_endpoint_failure_not_exchange_rejection(self) -> None:
        probe = {
            "endpoint_family": "akshare_json_dcereport",
            "status": "http_error_non_json",
            "http_status": 412,
            "content_type": "text/html",
            "body_size": 312,
            "parseable_rows": 0,
            "target_product": "jd.DCE",
        }

        classified = s039.classify_endpoint_probe(probe)

        self.assertEqual(classified["probe_status"], "json_endpoint_not_returning_json_needs_alternative_endpoint")
        self.assertFalse(classified["schema_ready_probe"])
        self.assertFalse(classified["rule_candidate_allowed"])
        self.assertIn("dce_json_endpoint_not_json", classified["blocking_reasons"])

    def test_legacy_export_success_is_candidate_but_not_pit_ready(self) -> None:
        probe = {
            "endpoint_family": "legacy_export_form",
            "status": "ok",
            "http_status": 200,
            "content_type": "application/vnd.ms-excel",
            "body_size": 2048,
            "parseable_rows": 12,
            "has_contract_column": True,
            "has_oi_column": True,
            "has_iv_column": False,
            "has_publish_timestamp": False,
            "continuous_audit_passed": False,
        }

        classified = s039.classify_endpoint_probe(probe)

        self.assertEqual(classified["probe_status"], "legacy_export_candidate_not_pit_ready")
        self.assertTrue(classified["endpoint_recovery_candidate"])
        self.assertFalse(classified["schema_ready_probe"])
        self.assertFalse(classified["rule_candidate_allowed"])
        self.assertIn("missing_publish_timestamp", classified["blocking_reasons"])
        self.assertIn("no_continuous_calendar_audit", classified["blocking_reasons"])

    def test_decision_keeps_strategy_disabled_even_with_legacy_export_candidate(self) -> None:
        probes = pd.DataFrame(
            [
                s039.classify_endpoint_probe(
                    {
                        "target_product": "jd.DCE",
                        "endpoint_family": "legacy_export_form",
                        "status": "ok",
                        "http_status": 200,
                        "parseable_rows": 8,
                        "has_contract_column": True,
                        "has_oi_column": True,
                        "has_publish_timestamp": False,
                        "continuous_audit_passed": False,
                    }
                )
            ]
        )

        decision = s039.make_stage039_decision(probes)

        self.assertEqual(decision["decision"], "stage039_dce_legacy_export_candidate_requires_parser_and_pit_calendar")
        self.assertEqual(decision["endpoint_recovery_candidate_count"], 1)
        self.assertEqual(decision["immediate_strategy_candidate_count"], 0)
        self.assertFalse(decision["strategy_rule_created"])
        self.assertFalse(decision["true_engine"])
        self.assertFalse(decision["order_api_called"])
        self.assertFalse(decision["ctp_connected"])


if __name__ == "__main__":
    unittest.main()
