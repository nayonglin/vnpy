from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage041_broker_replay_readiness as s041


class Stage041BrokerReplayReadinessTest(unittest.TestCase):
    def test_protected_live_log_is_never_schema_candidate(self) -> None:
        row = s041.classify_replay_path(Path("official_live/ctp/session_daemon/execution_ledger_20260702.jsonl"), 2048)

        self.assertEqual(row["asset_kind"], "protected_live_execution_log")
        self.assertTrue(row["protected_live_log"])
        self.assertFalse(row["schema_validation_required"])
        self.assertFalse(row["rule_candidate_allowed"])
        self.assertIn("protected_live_log_not_signal_source", row["blocking_reason"])

    def test_research_trade_events_are_not_same_source_replay(self) -> None:
        row = s041.classify_replay_path(
            Path("research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage028/trade_events.csv.gz"),
            4096,
        )

        self.assertEqual(row["asset_kind"], "research_or_backtest_artifact")
        self.assertFalse(row["schema_validation_required"])
        self.assertFalse(row["rule_candidate_allowed"])
        self.assertIn("research_backtest_artifact_not_production_replay", row["blocking_reason"])

    def test_candidate_schema_requires_signal_order_fill_position_fields(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "signal_time": "2026-06-16 20:55:00",
                    "order_time": "2026-06-16 20:55:02",
                    "fill_time": "2026-06-16 20:55:04",
                    "position_time": "2026-06-16 20:55:05",
                    "signal_id": "sig-1",
                    "order_id": "ord-1",
                    "trade_id": "trd-1",
                    "vt_symbol": "rb2610.SHFE",
                    "direction": "short",
                    "offset": "open",
                    "order_volume": 1,
                    "fill_volume": 1,
                    "order_price": 3200.0,
                    "fill_price": 3201.0,
                    "position_after": -1,
                }
            ]
        )

        result = s041.validate_replay_schema(frame)

        self.assertTrue(result["schema_complete"])
        self.assertTrue(result["has_signal_fields"])
        self.assertTrue(result["has_order_fields"])
        self.assertTrue(result["has_fill_fields"])
        self.assertTrue(result["has_position_fields"])
        self.assertFalse(result["has_time_order_violation"])

    def test_time_order_violation_blocks_candidate(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "signal_time": "2026-06-16 20:55:10",
                    "order_time": "2026-06-16 20:55:02",
                    "fill_time": "2026-06-16 20:55:04",
                    "position_time": "2026-06-16 20:55:05",
                    "signal_id": "sig-1",
                    "order_id": "ord-1",
                    "trade_id": "trd-1",
                    "vt_symbol": "rb2610.SHFE",
                    "direction": "short",
                    "offset": "open",
                    "order_volume": 1,
                    "fill_volume": 1,
                    "order_price": 3200.0,
                    "fill_price": 3201.0,
                    "position_after": -1,
                }
            ]
        )

        result = s041.validate_replay_schema(frame)

        self.assertTrue(result["schema_complete"])
        self.assertTrue(result["has_time_order_violation"])
        self.assertFalse(result["replay_ready"])
        self.assertIn("time_order_violation", result["blocking_reasons"])

    def test_decision_blocks_strategy_without_accepted_replay(self) -> None:
        readiness = pd.DataFrame(
            [
                {
                    "path": "external_data/broker_replay/sample.csv",
                    "asset_kind": "potential_same_source_replay_schema_candidate",
                    "schema_complete": True,
                    "replay_ready": False,
                    "accepted_same_source_replay": False,
                    "coverage_day_count": 1,
                    "rule_candidate_allowed": False,
                }
            ]
        )

        decision = s041.make_stage041_decision(readiness)

        self.assertEqual(decision["decision"], "stage041_broker_replay_no_accepted_same_source_dataset")
        self.assertEqual(decision["accepted_same_source_replay_count"], 0)
        self.assertEqual(decision["immediate_strategy_candidate_count"], 0)
        self.assertFalse(decision["strategy_rule_created"])
        self.assertFalse(decision["true_engine"])
        self.assertFalse(decision["order_api_called"])
        self.assertFalse(decision["ctp_connected"])


if __name__ == "__main__":
    unittest.main()
