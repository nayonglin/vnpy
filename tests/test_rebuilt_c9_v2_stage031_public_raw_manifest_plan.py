from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage031_public_raw_manifest_plan_audit as s031


class Stage031PublicRawManifestPlanAuditTest(unittest.TestCase):
    def test_batch_plan_assigns_source_dates_without_creating_signal(self) -> None:
        manifest = pd.DataFrame(
            [
                {"source_id": "czce_member_rank", "target_date": "20200102", "needed_products": "OI|MA"},
                {"source_id": "czce_member_rank", "target_date": "20200103", "needed_products": "OI"},
                {"source_id": "czce_warehouse", "target_date": "20200102", "needed_products": "MA"},
            ]
        )

        plan = s031.build_batch_plan(manifest, batch_size=2)

        self.assertEqual(len(plan), 3)
        self.assertEqual(plan["batch_id"].nunique(), 2)
        self.assertIn("source_date_key", plan.columns)
        self.assertFalse(plan["strategy_rule_created"].any())
        self.assertFalse(plan["true_engine_allowed"].any())

    def test_scope_gate_marks_preentry_manifest_as_engineering_not_strategy(self) -> None:
        source_summary = pd.DataFrame(
            [
                {
                    "source_id": "czce_member_rank",
                    "planned_raw_date_count": 731,
                    "probe_parsed_count": 9,
                    "preentry_manifest_ready": 1,
                    "full_raw_download_done": 0,
                },
                {
                    "source_id": "gfex_warehouse",
                    "planned_raw_date_count": 42,
                    "probe_parsed_count": 16,
                    "preentry_manifest_ready": 1,
                    "full_raw_download_done": 0,
                },
            ]
        )

        gate = s031.build_scope_gate(source_summary)

        self.assertEqual(set(gate["route_status"]), {"ready_for_batch_download_not_signal"})
        self.assertFalse(gate["signal_audit_allowed"].any())
        self.assertTrue(gate["batch_download_plan_allowed"].all())
        self.assertIn("not_full_history", ",".join(gate["blocking_reasons"]))

    def test_decision_requires_batches_before_any_signal_audit(self) -> None:
        batch_plan = pd.DataFrame(
            [
                {"source_id": "czce_member_rank", "target_date": "20200102", "batch_id": 1},
                {"source_id": "czce_member_rank", "target_date": "20200103", "batch_id": 1},
                {"source_id": "czce_warehouse", "target_date": "20200102", "batch_id": 2},
            ]
        )
        gate = pd.DataFrame(
            [
                {"source_id": "czce_member_rank", "batch_download_plan_allowed": True, "signal_audit_allowed": False},
                {"source_id": "czce_warehouse", "batch_download_plan_allowed": True, "signal_audit_allowed": False},
            ]
        )

        decision = s031.make_manifest_plan_decision(batch_plan, gate)

        self.assertEqual(decision["decision"], "stage031_public_raw_manifest_batch_plan_ready_no_strategy_candidate")
        self.assertEqual(decision["batch_count"], 2)
        self.assertEqual(decision["immediate_strategy_candidate_count"], 0)
        self.assertFalse(decision["true_engine"])
        self.assertFalse(decision["order_api_called"])


if __name__ == "__main__":
    unittest.main()
