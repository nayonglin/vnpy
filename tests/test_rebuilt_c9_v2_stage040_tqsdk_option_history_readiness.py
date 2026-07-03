from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage040_tqsdk_option_history_readiness as s040


class Stage040TqSdkOptionHistoryReadinessTest(unittest.TestCase):
    def test_credential_detection_redacts_all_secret_values(self) -> None:
        env = {
            "TQSDK_ACCOUNT": "paper_user",
            "TQSDK_PASSWORD": "super-secret",
            "TQ_USERNAME": "",
            "TQ_PASSWORD": "alternate-secret",
        }

        audit = s040.detect_tqsdk_credentials(env=env, env_file_paths=[])
        serialized = audit.to_json(force_ascii=False)

        self.assertIn("TQSDK_ACCOUNT", set(audit["credential_key"]))
        self.assertIn("TQSDK_PASSWORD", set(audit["credential_key"]))
        self.assertNotIn("paper_user", serialized)
        self.assertNotIn("super-secret", serialized)
        self.assertNotIn("alternate-secret", serialized)
        present = audit[audit["credential_key"].eq("TQSDK_PASSWORD")].iloc[0]
        self.assertTrue(bool(present["present"]))
        self.assertEqual(present["redacted_value"], "<present>")

    def test_no_credentials_keeps_tqsdk_installed_but_not_download_ready(self) -> None:
        module_info = {
            "module_importable": True,
            "module_version": "3.10.1",
            "has_tqapi": True,
            "has_tqauth": True,
            "has_tqsim": True,
            "has_data_downloader": True,
        }
        credential_audit = s040.detect_tqsdk_credentials(env={}, env_file_paths=[])

        readiness = s040.classify_tqsdk_readiness(
            module_info=module_info,
            credential_audit=credential_audit,
            permission_probe={"network_probe_enabled": False, "permission_probe_status": "skipped_no_credentials"},
        )

        self.assertEqual(readiness["readiness_status"], "installed_but_credentials_missing_no_download_probe")
        self.assertFalse(readiness["schema_ready_source"])
        self.assertFalse(readiness["rule_candidate_allowed"])
        self.assertIn("tqauth_credentials_missing", readiness["blocking_reasons"])

    def test_credentials_present_still_requires_professional_permission_probe(self) -> None:
        module_info = {
            "module_importable": True,
            "module_version": "3.10.1",
            "has_tqapi": True,
            "has_tqauth": True,
            "has_tqsim": True,
            "has_data_downloader": True,
        }
        credential_audit = s040.detect_tqsdk_credentials(
            env={"TQSDK_ACCOUNT": "paper_user", "TQSDK_PASSWORD": "super-secret"},
            env_file_paths=[],
        )

        readiness = s040.classify_tqsdk_readiness(
            module_info=module_info,
            credential_audit=credential_audit,
            permission_probe={"network_probe_enabled": False, "permission_probe_status": "skipped_by_default"},
        )

        self.assertEqual(readiness["readiness_status"], "credentials_present_permission_unverified")
        self.assertFalse(readiness["schema_ready_source"])
        self.assertFalse(readiness["rule_candidate_allowed"])
        self.assertIn("professional_downloader_permission_unverified", readiness["blocking_reasons"])

    def test_decision_requires_schema_ready_source_before_any_strategy_use(self) -> None:
        readiness = pd.DataFrame(
            [
                {
                    "source_name": "tqsdk_data_downloader",
                    "readiness_status": "credentials_present_permission_unverified",
                    "schema_ready_source": False,
                    "rule_candidate_allowed": False,
                }
            ]
        )

        decision = s040.make_stage040_decision(readiness)

        self.assertEqual(decision["decision"], "stage040_tqsdk_option_history_not_ready_credentials_or_permission_required")
        self.assertEqual(decision["schema_ready_source_count"], 0)
        self.assertEqual(decision["immediate_strategy_candidate_count"], 0)
        self.assertFalse(decision["strategy_rule_created"])
        self.assertFalse(decision["true_engine"])
        self.assertFalse(decision["order_api_called"])
        self.assertFalse(decision["ctp_connected"])

    def test_data_contract_keeps_option_chain_as_data_engineering_not_signal(self) -> None:
        contract = s040.build_data_contract()
        row = contract[contract["contract_id"].eq("tqsdk_commodity_option_chain_history")].iloc[0]

        self.assertIn("TqAuth", row["required_access"])
        self.assertIn("professional", row["required_access"].lower())
        self.assertIn("publish_or_exchange_timestamp", row["required_pit_checks"])
        self.assertIn("continuous_calendar_by_product", row["required_pit_checks"])
        self.assertIn("do_not_use_installed_module_or_credentials_as_signal", row["forbidden_shortcut"])


if __name__ == "__main__":
    unittest.main()
