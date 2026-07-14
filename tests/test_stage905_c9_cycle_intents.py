from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest

import pandas as pd


os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import run_qmt_roll_stage905_official_live_executor_dry_run as stage905


class Stage905C9CycleIntentTest(unittest.TestCase):
    def test_pending_initial_open_gets_complete_v2_identity(self) -> None:
        rows = stage905._pending_order_intents(
            pd.DataFrame(
                [
                    {
                        "vt_symbol": "JM609.DCE",
                        "direction": "short",
                        "offset": "open",
                        "volume": 2,
                        "price": 1245.5,
                        "stop_price": 1258.0,
                        "status": "pending",
                        "vt_orderid": "BACKTESTING.5",
                        "datetime": "2026-07-13 21:00:00+08:00",
                    }
                ]
            ),
            "2026-07-13",
        )
        row = rows[0]
        self.assertEqual(row["intent_role"], "c9_initial_open")
        self.assertTrue(row["root_position_id"].startswith("c9root-"))
        self.assertTrue(row["position_cycle_id"].endswith(":cycle0"))
        self.assertEqual(row["position_cycle_no"], 0)
        self.assertTrue(row["position_epoch_id"].startswith("c9pos-"))

    def test_stage904_close_and_retry_metadata_are_preserved(self) -> None:
        actions = pd.DataFrame(
            [
                {
                    "monitor_action": "close_dry_run",
                    "target_date": "2026-07-13",
                    "monitor_run_id": "run-001",
                    "action_id": "close-action",
                    "vt_symbol": "JM609.DCE",
                    "direction": "short",
                    "volume": 2,
                    "stage847_stop_price": 1251.75,
                    "root_position_id": "root",
                    "position_cycle_id": "root:cycle1",
                    "position_cycle_no": 1,
                    "position_epoch_id": "epoch-001",
                    "intent_role": "c9_retry_failed_stop_close",
                    "strategy_entry_price": 1245.5,
                    "strategy_stop_price": 1251.75,
                },
                {
                    "monitor_action": "retry_open_dry_run",
                    "target_date": "2026-07-13",
                    "monitor_run_id": "run-001",
                    "action_id": "retry-action",
                    "vt_symbol": "JM609.DCE",
                    "direction": "short",
                    "volume": 2,
                    "stage847_retry_trigger_price": 1245.5,
                    "stage847_stop_price": 1251.75,
                    "root_position_id": "root",
                    "position_cycle_id": "root:cycle1",
                    "position_cycle_no": 1,
                    "position_epoch_id": "epoch-001",
                    "intent_role": "c9_retry_open_once",
                    "strategy_entry_price": 1245.5,
                    "strategy_stop_price": 1251.75,
                },
            ]
        )
        intents = stage905._stage904_intents(actions)
        close = next(row for row in intents if row["offset"] == "close")
        retry = next(row for row in intents if row["offset"] == "open")
        self.assertEqual(close["intent_id"], "close-action")
        self.assertEqual(close["intent_role"], "c9_retry_failed_stop_close")
        self.assertEqual(close["position_cycle_id"], "root:cycle1")
        self.assertEqual(close["position_epoch_id"], "epoch-001")
        self.assertEqual(close["monitor_run_id"], "run-001")
        self.assertEqual(retry["intent_id"], "retry-action")
        self.assertEqual(retry["intent_role"], "c9_retry_open_once")
        self.assertEqual(retry["strategy_stop_price"], 1251.75)

    def test_stage904_action_requires_fresh_matching_final_summary(self) -> None:
        action = {
            "monitor_action": "close_dry_run",
            "target_date": "2026-07-13",
            "monitor_run_id": "run-001",
            "action_id": "close-action",
            "vt_symbol": "JM609.DCE",
            "direction": "short",
            "volume": 2,
            "stage847_stop_price": 1251.5,
            "live_ask_price_1": 1252.0,
            "root_position_id": "root",
            "position_cycle_id": "root:cycle0",
            "position_cycle_no": 0,
            "position_epoch_id": "epoch-001",
            "intent_role": "c9_initial_stop_close",
        }
        intent = stage905._stage904_intents(pd.DataFrame([action]))[0]
        common = {
            "contracts": pd.DataFrame(
                [
                    {
                        "vt_symbol": "JM609.DCE",
                        "pricetick": 0.5,
                        "min_volume": 1,
                        "max_volume": 100,
                        "gateway_name": "CTP",
                    }
                ]
            ),
            "positions": pd.DataFrame(
                [{"vt_symbol": "JM609.DCE", "direction": "short", "volume": 2, "frozen": 0}]
            ),
            "orders": pd.DataFrame(),
            "stage902_summary": {
                "blocking_failure_count": 0,
                "blocking_failure_count_for_reduce_close": 0,
                "allow_new_open": 0,
                "allow_reduce_close": 1,
            },
            "stage260_summary": {"executable_count": 0},
            "mode": "dry-run",
        }
        fresh_summary = {
            "model_tag": stage905.STAGE904_MODEL_TAG,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "target_date": "2026-07-13",
            "monitor_status": "intraday_monitor_close_dry_run",
            "monitor_run_id": "run-001",
        }
        ready = stage905._validate_intent(intent, stage904_summary=fresh_summary, **common)
        stale = stage905._validate_intent(
            intent,
            stage904_summary={
                **fresh_summary,
                "generated_at": (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S"),
                "monitor_run_id": "other-run",
            },
            **common,
        )

        self.assertEqual(ready["executor_status"], "dry_run_order_request_payload_ready")
        self.assertEqual(stale["executor_status"], "blocked")
        self.assertIn("stage904_summary_stale_or_missing", stale["executor_reason"])
        self.assertIn("stage904_monitor_run_id_mismatch", stale["executor_reason"])

    def test_close_dedupe_prevents_overclose_and_prefers_latest_cycle(self) -> None:
        intents = [
            {
                "source": "stage904_c9_intraday_close",
                "vt_symbol": "JM609.DCE",
                "direction": "long",
                "offset": "close",
                "planned_volume": 2,
                "position_cycle_id": "root:cycle0",
                "position_cycle_no": 0,
                "intent_role": "c9_initial_stop_close",
            },
            {
                "source": "stage904_c9_intraday_close",
                "vt_symbol": "JM609.DCE",
                "direction": "long",
                "offset": "close",
                "planned_volume": 2,
                "position_cycle_id": "root:cycle1",
                "position_cycle_no": 1,
                "intent_role": "c9_retry_failed_stop_close",
            },
        ]
        deduped = stage905._dedupe_intents(intents)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["position_cycle_id"], "root:cycle1")


if __name__ == "__main__":
    unittest.main()
