from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage033_public_raw_numeric_binding_readiness_audit as s033


class Stage033PublicRawNumericBindingReadinessAuditTest(unittest.TestCase):
    def test_build_binding_rows_requires_seed_ready_and_matching_hash(self) -> None:
        seed_index = pd.DataFrame(
            [
                {
                    "source_id": "czce_member_rank",
                    "target_date": "20200102",
                    "upstream_raw_file": "raw/a.xls",
                    "upstream_sha256": "abc",
                    "seed_rehydrate_ready": True,
                }
            ]
        )
        numeric_rows = pd.DataFrame(
            [
                {
                    "source_id": "czce_member_rank",
                    "target_date": "20200102",
                    "raw_file": "raw/a.xls",
                    "sha256": "abc",
                    "product_present_state": "present",
                    "numeric_feature_ready": 1,
                    "present_numeric_ready": 1,
                    "right_tail_top10": 0,
                    "strategy_rule_allowed": 0,
                    "true_engine_allowed": 0,
                    "field_parse_status": "parsed_ok",
                }
            ]
        )

        rows = s033.build_binding_rows(seed_index, numeric_rows)

        self.assertEqual(len(rows), 1)
        self.assertTrue(bool(rows.loc[0, "seed_link_ready"]))
        self.assertTrue(bool(rows.loc[0, "numeric_binding_ready"]))
        self.assertEqual(rows.loc[0, "binding_blocking_reasons"], "")

    def test_build_binding_rows_blocks_numeric_row_without_seed_provenance(self) -> None:
        seed_index = pd.DataFrame(
            [
                {
                    "source_id": "czce_warehouse",
                    "target_date": "20200102",
                    "upstream_raw_file": "raw/w.xls",
                    "upstream_sha256": "expected",
                    "seed_rehydrate_ready": True,
                }
            ]
        )
        numeric_rows = pd.DataFrame(
            [
                {
                    "source_id": "czce_warehouse",
                    "target_date": "20200102",
                    "raw_file": "raw/w.xls",
                    "sha256": "changed",
                    "product_present_state": "present",
                    "numeric_feature_ready": 1,
                    "present_numeric_ready": 1,
                    "right_tail_top10": 0,
                    "strategy_rule_allowed": 0,
                    "true_engine_allowed": 0,
                    "field_parse_status": "parsed_ok",
                },
                {
                    "source_id": "gfex_warehouse",
                    "target_date": "20240102",
                    "raw_file": "raw/g.json",
                    "sha256": "missing",
                    "product_present_state": "present",
                    "numeric_feature_ready": 1,
                    "present_numeric_ready": 1,
                    "right_tail_top10": 0,
                    "strategy_rule_allowed": 0,
                    "true_engine_allowed": 0,
                    "field_parse_status": "parsed_ok",
                },
            ]
        )

        rows = s033.build_binding_rows(seed_index, numeric_rows)

        self.assertEqual(int(rows["numeric_binding_ready"].sum()), 0)
        self.assertIn("seed_sha256_mismatch", ",".join(rows["binding_blocking_reasons"]))
        self.assertIn("seed_missing", ",".join(rows["binding_blocking_reasons"]))

    def test_decision_allows_only_readonly_signal_audit_when_numeric_and_right_tail_ready(self) -> None:
        binding_rows = pd.DataFrame(
            [
                {
                    "source_id": "czce_member_rank",
                    "target_date": "20200102",
                    "product_present_state": "present",
                    "numeric_binding_ready": True,
                    "present_numeric_ready": 1,
                    "right_tail_top10": 1,
                    "strategy_rule_allowed": 0,
                    "true_engine_allowed": 0,
                    "field_parse_status": "parsed_ok",
                },
                {
                    "source_id": "czce_warehouse",
                    "target_date": "20200102",
                    "product_present_state": "present",
                    "numeric_binding_ready": True,
                    "present_numeric_ready": 1,
                    "right_tail_top10": 0,
                    "strategy_rule_allowed": 0,
                    "true_engine_allowed": 0,
                    "field_parse_status": "parsed_ok",
                },
            ]
        )
        lot_summary = pd.DataFrame(
            [
                {"lot_id": "1", "right_tail_top10": 1, "all_present_numeric_ready": 1},
                {"lot_id": "2", "right_tail_top10": 0, "all_present_numeric_ready": 1},
            ]
        )

        decision = s033.make_numeric_binding_decision(binding_rows, lot_summary)

        self.assertEqual(decision["decision"], "stage033_public_raw_numeric_binding_ready_for_readonly_signal_audit_no_rule")
        self.assertTrue(decision["read_only_signal_audit_allowed_next"])
        self.assertEqual(decision["immediate_strategy_candidate_count"], 0)
        self.assertFalse(decision["strategy_rule_created"])
        self.assertFalse(decision["true_engine"])
        self.assertFalse(decision["order_api_called"])


if __name__ == "__main__":
    unittest.main()
