from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage044_orderflow_depth_contract as s044


class Stage044OrderflowDepthContractTest(unittest.TestCase):
    def test_research_trade_event_is_not_orderflow_depth_candidate(self) -> None:
        row = s044.classify_orderflow_path(
            Path("research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage041/trade_events.csv"),
            4096,
        )

        self.assertEqual(row["asset_kind"], "research_or_backtest_artifact")
        self.assertFalse(row["schema_validation_required"])
        self.assertFalse(row["rule_candidate_allowed"])
        self.assertIn("not_orderflow_depth_source", row["blocking_reason"])

    def test_minute_ohlcv_cache_is_not_depth_data(self) -> None:
        row = s044.classify_orderflow_path(Path("downloaded_futures/full_minute_bars.csv.gz"), 10_000)

        self.assertEqual(row["asset_kind"], "minute_ohlcv_or_bar_cache")
        self.assertFalse(row["schema_validation_required"])
        self.assertIn("bars_do_not_contain_book_queue", row["blocking_reason"])

    def test_mbp10_schema_requires_event_time_symbol_depth_prices_sizes_and_source(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "ts_event": "2026-06-16 21:00:00.100",
                    "ts_recv": "2026-06-16 21:00:00.120",
                    "vt_symbol": "rb2610.SHFE",
                    "bid_px_00": 3100,
                    "ask_px_00": 3101,
                    "bid_sz_00": 100,
                    "ask_sz_00": 120,
                    "bid_px_09": 3091,
                    "ask_px_09": 3110,
                    "bid_sz_09": 30,
                    "ask_sz_09": 22,
                    "source_system": "authorized_vendor",
                    "source_file_hash": "abc123",
                }
            ]
        )

        result = s044.validate_orderflow_schema(frame)

        self.assertEqual(result["schema_family"], "mbp10")
        self.assertTrue(result["schema_complete"])
        self.assertTrue(result["has_event_time"])
        self.assertTrue(result["has_receive_or_publish_time"])
        self.assertTrue(result["has_symbol"])
        self.assertGreaterEqual(result["max_book_level_detected"], 10)
        self.assertTrue(result["has_source_hash"])
        self.assertTrue(result["pit_rule_audit_allowed"])

    def test_mbo_schema_requires_order_identity_and_action_fields(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "ts_event": "2026-06-16 21:00:00.100",
                    "ts_recv": "2026-06-16 21:00:00.120",
                    "instrument_id": "rb2610.SHFE",
                    "order_id": 123,
                    "action": "add",
                    "side": "bid",
                    "price": 3100,
                    "size": 10,
                    "source_system": "authorized_vendor",
                    "source_file_hash": "abc123",
                }
            ]
        )

        result = s044.validate_orderflow_schema(frame)

        self.assertEqual(result["schema_family"], "mbo")
        self.assertTrue(result["schema_complete"])
        self.assertTrue(result["has_order_identity"])
        self.assertTrue(result["has_action"])
        self.assertTrue(result["pit_rule_audit_allowed"])

    def test_schema_without_receive_time_or_source_hash_is_blocked(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "ts_event": "2026-06-16 21:00:00.100",
                    "vt_symbol": "rb2610.SHFE",
                    "bid_px_00": 3100,
                    "ask_px_00": 3101,
                    "bid_sz_00": 100,
                    "ask_sz_00": 120,
                    "bid_px_09": 3091,
                    "ask_px_09": 3110,
                    "bid_sz_09": 30,
                    "ask_sz_09": 22,
                }
            ]
        )

        result = s044.validate_orderflow_schema(frame)

        self.assertFalse(result["schema_complete"])
        self.assertFalse(result["pit_rule_audit_allowed"])
        self.assertIn("missing_receive_or_publish_time", result["blocking_reasons"])
        self.assertIn("missing_source_hash", result["blocking_reasons"])

    def test_stage_decision_without_accepted_depth_data_stays_data_first(self) -> None:
        readiness = pd.DataFrame(
            [
                {
                    "path": "downloaded_futures/full_minute_bars.csv.gz",
                    "asset_kind": "minute_ohlcv_or_bar_cache",
                    "schema_complete": False,
                    "pit_rule_audit_allowed": False,
                    "accepted_orderflow_dataset": False,
                }
            ]
        )

        decision = s044.make_stage044_decision(readiness)

        self.assertEqual(decision["decision"], "stage044_orderflow_depth_no_accepted_dataset_data_contract_only")
        self.assertEqual(decision["accepted_orderflow_dataset_count"], 0)
        self.assertEqual(decision["immediate_strategy_candidate_count"], 0)
        self.assertFalse(decision["strategy_rule_created"])
        self.assertFalse(decision["true_engine"])
        self.assertFalse(decision["order_api_called"])
        self.assertFalse(decision["ctp_connected"])


if __name__ == "__main__":
    unittest.main()
