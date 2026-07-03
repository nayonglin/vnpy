from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage046_broker_replay_import_manifest as s046


class Stage046BrokerReplayImportManifestTest(unittest.TestCase):
    def test_request_manifest_requires_signal_order_fill_position_chain(self) -> None:
        manifest = s046.build_replay_request_manifest()

        required_fields = set(manifest["required_field"].astype(str))

        for field in {
            "signal_time",
            "signal_id",
            "plan_id",
            "order_time",
            "order_id",
            "vt_orderid",
            "vt_symbol",
            "order_status",
            "direction",
            "offset",
            "requested_volume",
            "order_price",
            "fill_time",
            "trade_id",
            "fill_price",
            "fill_volume",
            "commission",
            "slippage",
            "position_time",
            "position_after",
            "account_equity",
            "source_system",
            "source_file_hash",
        }:
            self.assertIn(field, required_fields)

        self.assertTrue(manifest["required"].astype(bool).all())
        self.assertIn("broker_execution_report", set(manifest["source_layer"].astype(str)))
        self.assertIn("strategy_signal", set(manifest["source_layer"].astype(str)))

    def test_complete_same_source_replay_schema_is_accepted_for_execution_calibration(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "session_id": "20260616_night",
                    "strategy_version": "official_live_stage847_c9_15w_stage819_05r_stop_retry_once",
                    "signal_time": "2026-06-16 20:54:00",
                    "signal_id": "sig-001",
                    "plan_id": "plan-001",
                    "order_time": "2026-06-16 20:55:02",
                    "order_id": "broker-order-001",
                    "vt_orderid": "CTP.001",
                    "vt_symbol": "jd2609.DCE",
                    "order_status": "ALLTRADED",
                    "direction": "LONG",
                    "offset": "OPEN",
                    "requested_volume": 2,
                    "order_price": 3510.0,
                    "fill_time": "2026-06-16 20:55:03",
                    "trade_id": "trade-001",
                    "fill_price": 3511.0,
                    "fill_volume": 2,
                    "commission": 12.6,
                    "slippage": 20.0,
                    "position_time": "2026-06-16 20:55:04",
                    "position_after": 2,
                    "account_equity": 150320.0,
                    "source_system": "broker_export",
                    "source_file_hash": "abc123",
                }
            ]
        )

        result = s046.validate_replay_schema(frame)

        self.assertTrue(result["schema_complete"])
        self.assertTrue(result["execution_calibration_allowed"])
        self.assertTrue(result["accepted_same_source_replay"])
        self.assertTrue(result["has_signal_to_position_chain"])
        self.assertFalse(result["has_time_order_violation"])

    def test_replay_schema_blocks_missing_position_or_hash_and_time_inversion(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "session_id": "20260616_night",
                    "strategy_version": "official_live_stage847_c9_15w_stage819_05r_stop_retry_once",
                    "signal_time": "2026-06-16 20:55:05",
                    "signal_id": "sig-001",
                    "plan_id": "plan-001",
                    "order_time": "2026-06-16 20:55:02",
                    "order_id": "broker-order-001",
                    "vt_orderid": "CTP.001",
                    "vt_symbol": "jd2609.DCE",
                    "order_status": "ALLTRADED",
                    "direction": "LONG",
                    "offset": "OPEN",
                    "requested_volume": 2,
                    "order_price": 3510.0,
                    "fill_time": "2026-06-16 20:55:03",
                    "trade_id": "trade-001",
                    "fill_price": 3511.0,
                    "fill_volume": 2,
                    "commission": 12.6,
                    "slippage": 20.0,
                    "account_equity": 150320.0,
                    "source_system": "broker_export",
                }
            ]
        )

        result = s046.validate_replay_schema(frame)

        self.assertFalse(result["schema_complete"])
        self.assertFalse(result["execution_calibration_allowed"])
        self.assertFalse(result["accepted_same_source_replay"])
        self.assertTrue(result["has_time_order_violation"])
        self.assertIn("missing_position_time", result["blocking_reasons"])
        self.assertIn("missing_position_after", result["blocking_reasons"])
        self.assertIn("missing_source_hash", result["blocking_reasons"])
        self.assertIn("time_order_violation", result["blocking_reasons"])

    def test_protected_live_log_is_preserved_but_not_schema_candidate(self) -> None:
        row = s046.classify_replay_import_path(
            Path("official_live/ctp/simnow/readonly/reconcile/session_daemon/execution_ledger/events.jsonl"),
            2048,
        )

        self.assertEqual(row["asset_kind"], "protected_live_evidence_log")
        self.assertTrue(row["preserve_by_default"])
        self.assertFalse(row["schema_validation_required"])
        self.assertFalse(row["execution_calibration_allowed"])
        self.assertIn("preserve_live_or_evidence_log", row["blocking_reason"])

    def test_decision_without_accepted_replay_stays_data_first(self) -> None:
        readiness = pd.DataFrame(
            [
                {
                    "path": "research/lines/a/outputs/stage041/trade_events.csv",
                    "asset_kind": "research_or_backtest_artifact",
                    "schema_complete": False,
                    "execution_calibration_allowed": False,
                    "accepted_same_source_replay": False,
                }
            ]
        )
        manifest = s046.build_replay_request_manifest()

        decision = s046.make_stage046_decision(readiness, manifest)

        self.assertEqual(decision["decision"], "stage046_broker_replay_import_manifest_data_first_no_accepted_dataset")
        self.assertEqual(decision["accepted_same_source_replay_count"], 0)
        self.assertEqual(decision["immediate_strategy_candidate_count"], 0)
        self.assertFalse(decision["strategy_rule_created"])
        self.assertFalse(decision["true_engine"])
        self.assertFalse(decision["order_api_called"])
        self.assertFalse(decision["ctp_connected"])


if __name__ == "__main__":
    unittest.main()
