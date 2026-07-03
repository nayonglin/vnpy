from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage032_public_raw_seed_rehydration_audit as s032


class Stage032PublicRawSeedRehydrationAuditTest(unittest.TestCase):
    def test_build_seed_index_requires_existing_file_and_matching_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "raw" / "czce_member_rank_20200102.xls"
            raw.parent.mkdir(parents=True)
            content = b"raw-bytes"
            raw.write_bytes(content)
            digest = hashlib.sha256(content).hexdigest()
            plan = pd.DataFrame(
                [
                    {
                        "source_id": "czce_member_rank",
                        "target_date": "20200102",
                        "batch_id": 1,
                        "needed_products": "OI",
                    }
                ]
            )
            upstream = pd.DataFrame(
                [
                    {
                        "source_id": "czce_member_rank",
                        "target_date": "20200102",
                        "status": "parsed_ok",
                        "parse_ready": 1,
                        "hash_ready": 1,
                        "sha256": digest,
                        "raw_file": str(raw.relative_to(root)),
                        "content_bytes": len(content),
                        "schema_hash": "schema1",
                        "needed_symbol_hit_all": 1,
                    }
                ]
            )

            index = s032.build_seed_index(plan, upstream, repo_dir=root)

            self.assertEqual(len(index), 1)
            self.assertTrue(bool(index.loc[0, "raw_file_exists"]))
            self.assertTrue(bool(index.loc[0, "sha256_file_match"]))
            self.assertTrue(bool(index.loc[0, "seed_rehydrate_ready"]))
            self.assertEqual(index.loc[0, "asset_mode"], "upstream_reference_no_copy")

    def test_seed_index_marks_missing_or_mismatched_seed_as_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "raw" / "czce_warehouse_20200102.xls"
            raw.parent.mkdir(parents=True)
            raw.write_bytes(b"changed")
            plan = pd.DataFrame(
                [
                    {
                        "source_id": "czce_warehouse",
                        "target_date": "20200102",
                        "batch_id": 1,
                        "needed_products": "MA",
                    },
                    {
                        "source_id": "gfex_warehouse",
                        "target_date": "20240102",
                        "batch_id": 1,
                        "needed_products": "SI",
                    },
                ]
            )
            upstream = pd.DataFrame(
                [
                    {
                        "source_id": "czce_warehouse",
                        "target_date": "20200102",
                        "status": "parsed_ok",
                        "parse_ready": 1,
                        "hash_ready": 1,
                        "sha256": hashlib.sha256(b"original").hexdigest(),
                        "raw_file": str(raw.relative_to(root)),
                        "content_bytes": 7,
                        "schema_hash": "schema2",
                        "needed_symbol_hit_all": 1,
                    }
                ]
            )

            index = s032.build_seed_index(plan, upstream, repo_dir=root)

            self.assertEqual(int(index["seed_rehydrate_ready"].sum()), 0)
            self.assertIn("sha256_mismatch", ",".join(index["seed_blocking_reasons"]))
            self.assertIn("upstream_result_missing", ",".join(index["seed_blocking_reasons"]))

    def test_decision_keeps_verified_seed_as_data_engineering_not_signal(self) -> None:
        index = pd.DataFrame(
            [
                {"source_id": "czce_member_rank", "target_date": "20200102", "seed_rehydrate_ready": True},
                {"source_id": "czce_warehouse", "target_date": "20200102", "seed_rehydrate_ready": True},
                {"source_id": "gfex_warehouse", "target_date": "20240102", "seed_rehydrate_ready": True},
            ]
        )

        decision = s032.make_seed_rehydration_decision(index)

        self.assertEqual(decision["decision"], "stage032_public_raw_seed_verified_ready_for_schema_binding_no_rule")
        self.assertEqual(decision["planned_raw_request_count"], 3)
        self.assertEqual(decision["seed_ready_count"], 3)
        self.assertFalse(decision["strategy_rule_created"])
        self.assertFalse(decision["true_engine"])
        self.assertFalse(decision["order_api_called"])


if __name__ == "__main__":
    unittest.main()
