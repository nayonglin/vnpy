from __future__ import annotations

import os
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd


os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import run_qmt_roll_stage905_official_live_executor_dry_run as stage905
import run_qmt_roll_stage904_official_live_c9_intraday_monitor as stage904
import qmt_roll_official_live_intent_spool as intent_spool
from qmt_roll_official_live_tick_types import DurableTickCursor
from qmt_roll_official_live_trace import ClockStamp, LatencyTrace
from qmt_roll_official_live_time import utc_iso_from_epoch_ns


class _FakeClock:
    def __init__(self, *, epoch_ns: int, monotonic_ns: int, domain: str = "test-boot") -> None:
        self._epoch_ns = epoch_ns
        self._monotonic_ns = monotonic_ns
        self._domain = domain

    def epoch_ns(self) -> int:
        return self._epoch_ns

    def monotonic_ns(self) -> int:
        return self._monotonic_ns

    def sleep(self, seconds: float) -> None:
        raise AssertionError(f"unexpected_sleep:{seconds}")

    def clock_domain_id(self) -> str:
        return self._domain


class _CountingClock(_FakeClock):
    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.epoch_calls = 0
        self.monotonic_calls = 0

    def epoch_ns(self) -> int:
        self.epoch_calls += 1
        return super().epoch_ns()

    def monotonic_ns(self) -> int:
        self.monotonic_calls += 1
        return super().monotonic_ns()


class Stage905C9CycleIntentTest(unittest.TestCase):
    def _traced_action(
        self,
        *,
        monitor_action: str,
        action_id: str,
        ingress_epoch_ns: int = 1_784_000_000_000_000_000,
        ingress_monotonic_ns: int = 7_000_000_000,
        sequence: int = 11,
    ) -> dict[str, object]:
        clock = _FakeClock(
            epoch_ns=ingress_epoch_ns,
            monotonic_ns=ingress_monotonic_ns,
        )
        trace = LatencyTrace.from_ingress_row(
            {
                "trace_id": f"stage179-tick/feed-a/{sequence}",
                "feed_session_id": "feed-a",
                "ingress_sequence": sequence,
                "symbol_sequence": 7,
                "vt_symbol": "JM609.DCE",
                "ingress_epoch_ns": ingress_epoch_ns,
                "ingress_monotonic_ns": ingress_monotonic_ns,
                "clock_domain_id": clock.clock_domain_id(),
                "received_at_utc": utc_iso_from_epoch_ns(ingress_epoch_ns),
            },
            clock=clock,
        )
        trace = trace.record_stamp(
            "stage904_detected",
            ClockStamp(
                epoch_ns=ingress_epoch_ns,
                monotonic_ns=ingress_monotonic_ns,
                clock_domain_id=clock.clock_domain_id(),
                utc_iso=utc_iso_from_epoch_ns(ingress_epoch_ns),
            ),
        )
        offset = "open" if monitor_action == "retry_open_dry_run" else "close"
        return {
            "monitor_action": monitor_action,
            "target_date": "2026-07-13",
            "monitor_run_id": "run-001",
            "action_id": action_id,
            "vt_symbol": "JM609.DCE",
            "direction": "short",
            "volume": 2,
            "stage847_retry_trigger_price": 1245.5,
            "stage847_stop_price": 1251.5,
            "live_bid_price_1": 1251.0,
            "live_ask_price_1": 1251.5,
            "root_position_id": "root",
            "position_cycle_id": "root:cycle1",
            "position_cycle_no": 1,
            "position_epoch_id": "epoch-001",
            "intent_role": (
                "c9_retry_open_once"
                if offset == "open"
                else "c9_retry_failed_stop_close"
            ),
            "manual_intervention_required": 0,
            "trace_json": trace.to_json(),
            "trace_id": trace.trace_id,
            "source_feed_session_id": trace.feed_session_id,
            "source_ingress_sequence": trace.ingress_sequence,
            "source_symbol_sequence": trace.symbol_sequence,
            "ingress_epoch_ns": ingress_epoch_ns,
            "ingress_monotonic_ns": ingress_monotonic_ns,
            "deadline_epoch_ns": trace.deadline_epoch_ns,
            "deadline_monotonic_ns": trace.deadline_monotonic_ns,
            "durable_cursor_feed_session_id": "feed-a",
            "durable_cursor_ingress_sequence": 12,
            "durable_cursor_journal_byte_offset": 8192,
            "durable_cursor_journal_schema": "stage179_framed_v1",
            "state_generation": "epoch-001:9",
        }

    def _snapshots(
        self,
        *,
        pending_orders: pd.DataFrame | None = None,
        positions: pd.DataFrame | None = None,
        stage260_executable: int = 0,
        stage902_blocking: int = 0,
    ) -> object:
        return stage905.Stage905SnapshotInputs(
            pending_orders=(
                pd.DataFrame() if pending_orders is None else pending_orders
            ),
            contracts=pd.DataFrame(
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
            positions=(
                pd.DataFrame(
                    [
                        {
                            "vt_symbol": "JM609.DCE",
                            "direction": "short",
                            "volume": 2,
                            "frozen": 0,
                        }
                    ]
                )
                if positions is None
                else positions
            ),
            orders=pd.DataFrame(),
            stage902_summary={
                "blocking_failure_count": stage902_blocking,
                "blocking_failure_count_for_reduce_close": 0,
                "allow_new_open": int(stage902_blocking == 0),
                "allow_reduce_close": 1,
            },
            stage260_summary={"executable_count": stage260_executable},
            execution_ledger_rows=(),
        )

    def _stage904_summary(
        self,
        generated_at: str,
        *,
        action_count: int = 1,
        close_count: int = 0,
        retry_count: int = 1,
        cursor_sequence: int = 12,
        cursor_offset: int = 8192,
    ) -> dict[str, object]:
        return {
            "model_tag": stage905.STAGE904_MODEL_TAG,
            "generated_at": generated_at,
            "target_date": "2026-07-13",
            "monitor_run_id": "run-001",
            "monitor_status": "intraday_monitor_blocked",
            "action_count": action_count,
            "close_dry_run_count": close_count,
            "retry_open_dry_run_count": retry_count,
            "retry_watch_count": 0,
            "blocked_count": 0,
            "order_api_called_count": 0,
            "durable_batch_cursor": {
                "feed_session_id": "feed-a",
                "ingress_sequence": cursor_sequence,
                "journal_byte_offset": cursor_offset,
                "journal_schema": "stage179_framed_v1",
            },
        }

    def test_stage904_trace_deadline_and_state_generation_are_preserved(self) -> None:
        action = self._traced_action(
            monitor_action="retry_open_dry_run",
            action_id="retry-action",
        )

        intent = stage905._stage904_intents(pd.DataFrame([action]))[0]

        for field_name in (
            "trace_json",
            "trace_id",
            "source_feed_session_id",
            "source_ingress_sequence",
            "source_symbol_sequence",
            "ingress_epoch_ns",
            "ingress_monotonic_ns",
            "deadline_epoch_ns",
            "deadline_monotonic_ns",
            "durable_cursor_feed_session_id",
            "durable_cursor_ingress_sequence",
            "durable_cursor_journal_byte_offset",
            "durable_cursor_journal_schema",
            "state_generation",
        ):
            self.assertEqual(action[field_name], intent[field_name], field_name)

    def test_virtual_deadline_marks_open_expired_and_close_blocked(self) -> None:
        ingress_epoch_ns = 1_784_000_000_000_000_000
        ingress_monotonic_ns = 7_000_000_000
        actions = pd.DataFrame(
            [
                self._traced_action(
                    monitor_action="retry_open_dry_run",
                    action_id="retry-action",
                    ingress_epoch_ns=ingress_epoch_ns,
                    ingress_monotonic_ns=ingress_monotonic_ns,
                ),
                self._traced_action(
                    monitor_action="close_dry_run",
                    action_id="close-action",
                    ingress_epoch_ns=ingress_epoch_ns,
                    ingress_monotonic_ns=ingress_monotonic_ns,
                ),
            ]
        )
        deadline_clock = _FakeClock(
            epoch_ns=ingress_epoch_ns + 25_000_000_000,
            monotonic_ns=ingress_monotonic_ns + 25_000_000_000,
        )
        generated_at = datetime.fromtimestamp(
            deadline_clock.epoch_ns() / 1_000_000_000
        ).strftime("%Y-%m-%d %H:%M:%S")

        result = stage905.run_executor_dry_run(
            "2026-07-13",
            stage904_actions=actions,
            stage904_summary=self._stage904_summary(
                generated_at,
                action_count=2,
                close_count=1,
                retry_count=1,
            ),
            snapshots=self._snapshots(),
            include_stage901_pending=False,
            clock=deadline_clock,
            write_compat_outputs=False,
        )

        by_offset = result.intents.set_index("offset")
        self.assertEqual("expired", by_offset.loc["open", "executor_status"])
        self.assertEqual("blocked", by_offset.loc["close", "executor_status"])
        self.assertIn("deadline_expired_close_critical", by_offset.loc["close", "executor_reason"])
        self.assertEqual(0, result.summary["send_order_api_called_count"])
        self.assertEqual(0, result.summary["cancel_order_api_called_count"])
        self.assertEqual(0, result.summary["order_api_called_count"])

    def test_in_memory_stage904_result_does_not_read_stage904_files(self) -> None:
        action = self._traced_action(
            monitor_action="retry_open_dry_run",
            action_id="retry-action",
        )
        now_clock = _FakeClock(
            epoch_ns=int(action["ingress_epoch_ns"]) + 1_000_000_000,
            monotonic_ns=int(action["ingress_monotonic_ns"]) + 1_000_000_000,
        )
        generated_at = datetime.fromtimestamp(
            now_clock.epoch_ns() / 1_000_000_000
        ).strftime("%Y-%m-%d %H:%M:%S")

        with patch.object(stage905, "_read_csv_maybe", side_effect=AssertionError("file read")), patch.object(
            stage905, "_read_json", side_effect=AssertionError("json read")
        ), patch.object(
            stage905, "read_execution_ledger", side_effect=AssertionError("ledger read")
        ), patch.object(
            stage905, "_atomic_write_df", side_effect=AssertionError("file write")
        ), patch.object(
            stage905, "_atomic_write_text", side_effect=AssertionError("file write")
        ):
            result = stage905.run_executor_dry_run(
                "2026-07-13",
                stage904_actions=pd.DataFrame([action]),
                stage904_summary=self._stage904_summary(generated_at),
                snapshots=self._snapshots(),
                include_stage901_pending=False,
                clock=now_clock,
                write_compat_outputs=False,
            )

        self.assertEqual(0, result.summary["send_order_api_called_count"])

    def test_stage904_run_result_is_consumed_directly(self) -> None:
        action = self._traced_action(
            monitor_action="retry_open_dry_run",
            action_id="retry-action",
        )
        clock = _FakeClock(
            epoch_ns=int(action["ingress_epoch_ns"]) + 1_000_000_000,
            monotonic_ns=int(action["ingress_monotonic_ns"]) + 1_000_000_000,
        )
        generated_at = datetime.fromtimestamp(
            clock.epoch_ns() / 1_000_000_000
        ).strftime("%Y-%m-%d %H:%M:%S")
        stage904_result = stage904.Stage904RunResult(
            target_date="2026-07-13",
            monitor_run_id="run-001",
            actions=pd.DataFrame([action]),
            summary={
                **self._stage904_summary(generated_at),
                "monitor_status": "intraday_monitor_retry_open_dry_run",
            },
            paths={},
        )

        result = stage905.run_executor_dry_run(
            "2026-07-13",
            stage904_actions=stage904_result,
            snapshots=self._snapshots(positions=pd.DataFrame()),
            include_stage901_pending=False,
            clock=clock,
            write_compat_outputs=False,
        )

        self.assertEqual(1, len(result.intents))
        self.assertEqual("retry-action", result.intents.iloc[0]["intent_id"])
        self.assertEqual(0, result.summary["send_order_api_called_count"])

    def test_builder_samples_one_clock_stamp_for_the_entire_batch(self) -> None:
        action = self._traced_action(
            monitor_action="retry_open_dry_run",
            action_id="retry-action",
        )
        clock = _CountingClock(
            epoch_ns=int(action["ingress_epoch_ns"]) + 1_000_000_000,
            monotonic_ns=int(action["ingress_monotonic_ns"]) + 1_000_000_000,
        )
        generated_at = datetime.fromtimestamp(
            int(action["ingress_epoch_ns"]) / 1_000_000_000 + 1
        ).strftime("%Y-%m-%d %H:%M:%S")

        result = stage905.run_executor_dry_run(
            "2026-07-13",
            stage904_actions=pd.DataFrame(
                [
                    action,
                    self._traced_action(
                        monitor_action="close_dry_run",
                        action_id="close-action",
                    ),
                ]
            ),
            stage904_summary={
                **self._stage904_summary(
                    generated_at,
                    action_count=2,
                    close_count=1,
                    retry_count=1,
                ),
                "monitor_status": "intraday_monitor_retry_open_dry_run",
            },
            snapshots=self._snapshots(positions=pd.DataFrame()),
            include_stage901_pending=False,
            clock=clock,
            write_compat_outputs=False,
        )

        self.assertEqual(2, len(result.intents))
        self.assertEqual(1, clock.epoch_calls)
        self.assertEqual(1, clock.monotonic_calls)

    def test_in_memory_target_date_mismatch_is_rejected_before_build(self) -> None:
        action = self._traced_action(
            monitor_action="retry_open_dry_run",
            action_id="retry-action",
        )
        with self.assertRaisesRegex(ValueError, "stage904_in_memory_target_date_mismatch"):
            stage905.run_executor_dry_run(
                "2026-07-14",
                stage904_actions=pd.DataFrame([action]),
                stage904_summary=self._stage904_summary("2026-07-13 21:00:01"),
                snapshots=self._snapshots(),
                include_stage901_pending=False,
                write_compat_outputs=False,
            )

    def test_in_memory_stage904_actions_and_summary_are_atomic_inputs(self) -> None:
        action = self._traced_action(
            monitor_action="retry_open_dry_run",
            action_id="retry-action",
        )
        with patch.object(stage905, "_read_json", side_effect=AssertionError("mixed disk read")):
            with self.assertRaisesRegex(ValueError, "stage904_in_memory_inputs_must_be_paired"):
                stage905.run_executor_dry_run(
                    "2026-07-13",
                    stage904_actions=pd.DataFrame([action]),
                    snapshots=self._snapshots(),
                    include_stage901_pending=False,
                    write_compat_outputs=False,
                )

    def test_empty_action_batch_still_surfaces_summary_contract_blockers(self) -> None:
        result = stage905.run_executor_dry_run(
            "2026-07-13",
            stage904_actions=pd.DataFrame(columns=["monitor_action"]),
            stage904_summary={
                **self._stage904_summary(
                    "2026-07-13 21:00:01",
                    action_count=1,
                    retry_count=0,
                ),
            },
            snapshots=self._snapshots(),
            include_stage901_pending=False,
            write_compat_outputs=False,
        )

        self.assertTrue(result.intents.empty)
        self.assertEqual("executor_dry_run_blocked", result.summary["executor_status"])
        self.assertGreater(result.summary["input_blocker_count"], 0)
        self.assertEqual(0, result.summary["send_order_api_called_count"])

    def test_empty_action_batch_rejects_malformed_nonempty_cursor(self) -> None:
        result = stage905.run_executor_dry_run(
            "2026-07-13",
            stage904_actions=pd.DataFrame(columns=["monitor_action"]),
            stage904_summary={
                **self._stage904_summary(
                    "2026-07-13 21:00:01",
                    action_count=0,
                    retry_count=0,
                ),
                "durable_batch_cursor": {
                    "feed_session_id": "feed-a",
                    "journal_schema": "bad",
                },
            },
            snapshots=self._snapshots(),
            include_stage901_pending=False,
            write_compat_outputs=False,
        )

        self.assertTrue(result.intents.empty)
        self.assertEqual("executor_dry_run_blocked", result.summary["executor_status"])
        self.assertIn(
            "stage904_summary_durable_batch_cursor_fields_invalid",
            result.summary["input_blockers"],
        )

    def test_exact_int_provenance_survives_mixed_stage901_rows(self) -> None:
        exact_offset = 2**53 + 123
        action = self._traced_action(
            monitor_action="retry_open_dry_run",
            action_id="retry-action",
        )
        action["durable_cursor_journal_byte_offset"] = exact_offset
        clock = _FakeClock(
            epoch_ns=int(action["ingress_epoch_ns"]) + 1_000_000_000,
            monotonic_ns=int(action["ingress_monotonic_ns"]) + 1_000_000_000,
        )
        generated_at = datetime.fromtimestamp(
            clock.epoch_ns() / 1_000_000_000
        ).strftime("%Y-%m-%d %H:%M:%S")
        pending = pd.DataFrame(
            [
                {
                    "vt_symbol": "I609.DCE",
                    "direction": "short",
                    "offset": "open",
                    "volume": 1,
                    "price": 800.0,
                    "status": "pending",
                }
            ]
        )

        result = stage905.run_executor_dry_run(
            "2026-07-13",
            stage904_actions=pd.DataFrame([action]),
            stage904_summary={
                **self._stage904_summary(
                    generated_at,
                    cursor_offset=exact_offset,
                ),
                "monitor_status": "intraday_monitor_retry_open_dry_run",
            },
            snapshots=self._snapshots(
                pending_orders=pending,
                positions=pd.DataFrame(),
            ),
            clock=clock,
            write_compat_outputs=False,
        )

        retry = result.intents[
            result.intents["source"].eq("stage904_c9_intraday_retry_open")
        ].iloc[0]
        self.assertIs(type(retry["ingress_epoch_ns"]), int)
        self.assertIs(type(retry["deadline_epoch_ns"]), int)
        self.assertIs(type(retry["durable_cursor_journal_byte_offset"]), int)
        self.assertEqual(exact_offset, retry["durable_cursor_journal_byte_offset"])

    def test_one_nanosecond_before_deadline_remains_ready(self) -> None:
        action = self._traced_action(
            monitor_action="retry_open_dry_run",
            action_id="retry-action",
        )
        clock = _FakeClock(
            epoch_ns=int(action["deadline_epoch_ns"]) - 1,
            monotonic_ns=int(action["deadline_monotonic_ns"]) - 1,
        )
        generated_at = datetime.fromtimestamp(
            clock.epoch_ns() / 1_000_000_000
        ).strftime("%Y-%m-%d %H:%M:%S")

        result = stage905.run_executor_dry_run(
            "2026-07-13",
            stage904_actions=pd.DataFrame([action]),
            stage904_summary={
                **self._stage904_summary(generated_at),
                "monitor_status": "intraday_monitor_retry_open_dry_run",
            },
            snapshots=self._snapshots(positions=pd.DataFrame()),
            include_stage901_pending=False,
            clock=clock,
            write_compat_outputs=False,
        )

        intent = result.intents.iloc[0]
        self.assertEqual("dry_run_order_request_payload_ready", intent["executor_status"])
        self.assertTrue(stage905.json.loads(intent["order_request_json"]))

    def test_trace_outer_tamper_fails_closed_with_empty_payload(self) -> None:
        action = self._traced_action(
            monitor_action="retry_open_dry_run",
            action_id="retry-action",
        )
        action["deadline_epoch_ns"] = int(action["deadline_epoch_ns"]) + 1
        clock = _FakeClock(
            epoch_ns=int(action["ingress_epoch_ns"]) + 1_000_000_000,
            monotonic_ns=int(action["ingress_monotonic_ns"]) + 1_000_000_000,
        )
        generated_at = datetime.fromtimestamp(
            clock.epoch_ns() / 1_000_000_000
        ).strftime("%Y-%m-%d %H:%M:%S")

        result = stage905.run_executor_dry_run(
            "2026-07-13",
            stage904_actions=pd.DataFrame([action]),
            stage904_summary={
                **self._stage904_summary(generated_at),
                "monitor_status": "intraday_monitor_retry_open_dry_run",
            },
            snapshots=self._snapshots(positions=pd.DataFrame()),
            include_stage901_pending=False,
            clock=clock,
            write_compat_outputs=False,
        )

        intent = result.intents.iloc[0]
        self.assertEqual("blocked", intent["executor_status"])
        self.assertIn("stage904_trace_invalid", intent["executor_reason"])
        self.assertEqual({}, stage905.json.loads(intent["order_request_json"]))

    def test_summary_cursor_count_and_state_generation_tamper_fail_closed(self) -> None:
        base = self._traced_action(
            monitor_action="retry_open_dry_run",
            action_id="retry-action",
        )
        clock = _FakeClock(
            epoch_ns=int(base["ingress_epoch_ns"]) + 1_000_000_000,
            monotonic_ns=int(base["ingress_monotonic_ns"]) + 1_000_000_000,
        )
        generated_at = datetime.fromtimestamp(
            clock.epoch_ns() / 1_000_000_000
        ).strftime("%Y-%m-%d %H:%M:%S")
        cases = {
            "state_generation": (
                {**base, "state_generation": "other-epoch:999"},
                self._stage904_summary(generated_at),
            ),
            "action_cursor_offset": (
                {
                    **base,
                    "durable_cursor_journal_byte_offset": 2**53 + 999,
                },
                self._stage904_summary(generated_at),
            ),
            "summary_cursor_identity": (
                base,
                {
                    **self._stage904_summary(generated_at),
                    "durable_batch_cursor": {
                        "feed_session_id": "wrong-feed",
                        "ingress_sequence": 999,
                        "journal_byte_offset": 999,
                        "journal_schema": "stage179_framed_v1",
                    },
                },
            ),
            "summary_action_count": (
                base,
                {
                    **self._stage904_summary(generated_at),
                    "action_count": 0,
                },
            ),
        }

        for label, (action, summary) in cases.items():
            with self.subTest(label=label):
                result = stage905.run_executor_dry_run(
                    "2026-07-13",
                    stage904_actions=pd.DataFrame([action]),
                    stage904_summary={
                        **summary,
                        "monitor_status": "intraday_monitor_retry_open_dry_run",
                    },
                    snapshots=self._snapshots(positions=pd.DataFrame()),
                    include_stage901_pending=False,
                    clock=clock,
                    write_compat_outputs=False,
                )
                intent = result.intents.iloc[0]
                self.assertEqual("blocked", intent["executor_status"])
                self.assertEqual({}, stage905.json.loads(intent["order_request_json"]))

    def test_later_summary_cursor_can_cover_replayed_trigger_cursor(self) -> None:
        action = self._traced_action(
            monitor_action="retry_open_dry_run",
            action_id="retry-action",
        )
        clock = _FakeClock(
            epoch_ns=int(action["ingress_epoch_ns"]) + 1_000_000_000,
            monotonic_ns=int(action["ingress_monotonic_ns"]) + 1_000_000_000,
        )
        generated_at = datetime.fromtimestamp(
            clock.epoch_ns() / 1_000_000_000
        ).strftime("%Y-%m-%d %H:%M:%S")

        result = stage905.run_executor_dry_run(
            "2026-07-13",
            stage904_actions=pd.DataFrame([action]),
            stage904_summary={
                **self._stage904_summary(
                    generated_at,
                    cursor_sequence=20,
                    cursor_offset=16384,
                ),
                "monitor_status": "intraday_monitor_retry_open_dry_run",
            },
            snapshots=self._snapshots(positions=pd.DataFrame()),
            include_stage901_pending=False,
            clock=clock,
            write_compat_outputs=False,
        )

        self.assertEqual(
            "dry_run_order_request_payload_ready",
            result.intents.iloc[0]["executor_status"],
        )

    def test_expired_replay_hash_ignores_observed_summary_age(self) -> None:
        action = self._traced_action(
            monitor_action="retry_open_dry_run",
            action_id="retry-action",
        )
        generated_at = datetime.fromtimestamp(
            int(action["ingress_epoch_ns"]) / 1_000_000_000
        ).strftime("%Y-%m-%d %H:%M:%S")
        summary = {
            **self._stage904_summary(generated_at),
            "monitor_status": "intraday_monitor_retry_open_dry_run",
        }

        results = []
        for elapsed_seconds in (31, 32):
            clock = _FakeClock(
                epoch_ns=int(action["ingress_epoch_ns"]) + elapsed_seconds * 1_000_000_000,
                monotonic_ns=int(action["ingress_monotonic_ns"]) + elapsed_seconds * 1_000_000_000,
            )
            results.append(
                stage905.run_executor_dry_run(
                    "2026-07-13",
                    stage904_actions=pd.DataFrame([action]),
                    stage904_summary=summary,
                    snapshots=self._snapshots(positions=pd.DataFrame()),
                    include_stage901_pending=False,
                    clock=clock,
                    write_compat_outputs=False,
                ).intents.iloc[0]
            )

        self.assertEqual("expired", results[0]["executor_status"])
        self.assertEqual("expired", results[1]["executor_status"])
        self.assertNotEqual(results[0]["executor_reason"], results[1]["executor_reason"])
        self.assertEqual(results[0]["payload_sha256"], results[1]["payload_sha256"])

    def test_stable_payload_hash_excludes_run_and_check_times(self) -> None:
        base = self._traced_action(
            monitor_action="retry_open_dry_run",
            action_id="retry-action",
        )
        first = stage905._stage904_intents(pd.DataFrame([base]))[0]
        second = {
            **first,
            "monitor_run_id": "run-999",
            "generated_at": "2099-01-01 00:00:00",
            "checked_at": "2099-01-01 00:00:01",
            "stage904_summary_generated_at": "2099-01-01 00:00:02",
        }

        self.assertEqual(
            stage905._stable_payload_sha256(first),
            stage905._stable_payload_sha256(dict(reversed(list(second.items())))),
        )
        self.assertNotEqual(
            stage905._stable_payload_sha256(first),
            stage905._stable_payload_sha256({**second, "planned_volume": 3}),
        )

    def test_final_payload_hash_excludes_monitor_run_id(self) -> None:
        action = self._traced_action(
            monitor_action="retry_open_dry_run",
            action_id="retry-action",
        )
        clock = _FakeClock(
            epoch_ns=int(action["ingress_epoch_ns"]) + 1_000_000_000,
            monotonic_ns=int(action["ingress_monotonic_ns"]) + 1_000_000_000,
        )
        generated_at = datetime.fromtimestamp(
            clock.epoch_ns() / 1_000_000_000
        ).strftime("%Y-%m-%d %H:%M:%S")

        first = stage905.run_executor_dry_run(
            "2026-07-13",
            stage904_actions=pd.DataFrame([action]),
            stage904_summary={
                **self._stage904_summary(generated_at),
                "monitor_status": "intraday_monitor_retry_open_dry_run",
            },
            snapshots=self._snapshots(positions=pd.DataFrame()),
            include_stage901_pending=False,
            clock=clock,
            write_compat_outputs=False,
        )
        replay_action = {**action, "monitor_run_id": "run-999"}
        replay = stage905.run_executor_dry_run(
            "2026-07-13",
            stage904_actions=pd.DataFrame([replay_action]),
            stage904_summary={
                **self._stage904_summary(generated_at),
                "monitor_run_id": "run-999",
                "monitor_status": "intraday_monitor_retry_open_dry_run",
            },
            snapshots=self._snapshots(positions=pd.DataFrame()),
            include_stage901_pending=False,
            clock=clock,
            write_compat_outputs=False,
        )

        self.assertEqual(
            first.intents.iloc[0]["payload_sha256"],
            replay.intents.iloc[0]["payload_sha256"],
        )

        first_intent = first.intents.iloc[0]
        spool_payload_json = first_intent["spool_payload_json"]
        self.assertEqual(
            hashlib.sha256(spool_payload_json.encode("utf-8")).hexdigest(),
            first_intent["payload_sha256"],
        )
        self.assertNotIn("trace_json", json.loads(spool_payload_json))

        with tempfile.TemporaryDirectory() as tempdir:
            connection = intent_spool.open_spool(
                Path(tempdir) / "stage905-integration.sqlite3"
            )
            try:
                cursor = DurableTickCursor(
                    feed_session_id=first_intent[
                        "durable_cursor_feed_session_id"
                    ],
                    ingress_sequence=int(
                        first_intent["durable_cursor_ingress_sequence"]
                    ),
                    journal_byte_offset=int(
                        first_intent["durable_cursor_journal_byte_offset"]
                    ),
                )
                committed = intent_spool.commit_detector_batch(
                    connection,
                    consumer_id="stage941",
                    expected_cursor=None,
                    next_cursor=cursor,
                    intents=[dict(first_intent)],
                    now_epoch_ns=clock.epoch_ns(),
                    now_monotonic_ns=clock.monotonic_ns(),
                    clock_domain_id=clock.clock_domain_id(),
                )
                self.assertEqual(1, committed.inserted_count)
            finally:
                connection.close()

    def test_business_payload_hash_ignores_trace_observation_but_not_order_data(self) -> None:
        base = {
            "intent_id": "retry-action",
            "trace_id": "trace-retry-action",
            "trace_json": '{"stage905_intent_ready":{"epoch_ns":1}}',
            "planned_volume": 1,
            "limit_price": 1245.5,
        }

        self.assertEqual(
            stage905._stable_payload_sha256(base),
            stage905._stable_payload_sha256(
                {
                    **base,
                    "trace_json": '{"stage905_intent_ready":{"epoch_ns":2}}',
                }
            ),
        )
        self.assertNotEqual(
            stage905._stable_payload_sha256(base),
            stage905._stable_payload_sha256({**base, "planned_volume": 2}),
        )

    def test_business_payload_hash_rejects_lossy_string_coercion(self) -> None:
        with self.assertRaisesRegex(ValueError, "json_type_unsupported"):
            stage905._stable_payload_sha256({"intent_id": "x", "value": object()})

    def test_invalid_exchange_fails_closed_instead_of_raising(self) -> None:
        intent = {
            "intent_id": "bad-exchange",
            "target_date": "2026-07-13",
            "source": "stage901_pending_order",
            "vt_symbol": "JM609.BAD",
            "direction": "short",
            "offset": "open",
            "planned_volume": 1,
            "limit_price": 1245.5,
        }

        checked = stage905._validate_intent(
            intent,
            contracts=pd.DataFrame(
                [
                    {
                        "vt_symbol": "JM609.BAD",
                        "pricetick": 0.5,
                        "min_volume": 1,
                        "max_volume": 100,
                    }
                ]
            ),
            positions=pd.DataFrame(),
            orders=pd.DataFrame(),
            stage902_summary={
                "blocking_failure_count": 0,
                "blocking_failure_count_for_reduce_close": 0,
                "allow_new_open": 1,
                "allow_reduce_close": 1,
            },
            stage904_summary={},
            stage260_summary={"executable_count": 1},
            mode="dry-run",
        )

        self.assertEqual("blocked", checked["executor_status"])
        self.assertIn("invalid_exchange", checked["executor_reason"])
        self.assertEqual({}, stage905.json.loads(checked["order_request_json"]))

    def test_manual_position_matching_stage901_open_is_not_duplicated(self) -> None:
        checked = stage905._validate_intent(
            {
                "intent_id": "planned-si-open",
                "target_date": "2026-08-18",
                "source": "stage901_pending_order",
                "intent_role": "c9_initial_open",
                "vt_symbol": "SI2609.GFEX",
                "direction": "long",
                "offset": "open",
                "planned_volume": 6,
                "limit_price": 8590.0,
            },
            contracts=pd.DataFrame(
                [
                    {
                        "vt_symbol": "SI2609.GFEX",
                        "pricetick": 5.0,
                        "min_volume": 1,
                        "max_volume": 100,
                        "gateway_name": "CTP",
                    }
                ]
            ),
            positions=pd.DataFrame(
                [
                    {
                        "vt_symbol": "SI2609.GFEX",
                        "direction": "long",
                        "volume": 6,
                        "frozen": 0,
                    }
                ]
            ),
            orders=pd.DataFrame(),
            stage902_summary={
                "blocking_failure_count": 0,
                "blocking_failure_count_for_reduce_close": 0,
                "allow_new_open": 1,
                "allow_reduce_close": 1,
            },
            stage904_summary={},
            stage260_summary={"executable_count": 1},
            mode="dry-run",
        )

        self.assertEqual(
            "skipped_existing_broker_position",
            checked["executor_status"],
        )
        self.assertIn(
            "stage901_open_already_present_in_broker_position:6.0",
            checked["executor_reason"],
        )
        self.assertEqual({}, stage905.json.loads(checked["order_request_json"]))

    def test_stage901_normal_close_can_exit_matching_manual_position(self) -> None:
        checked = stage905._validate_intent(
            {
                "intent_id": "planned-si-close",
                "target_date": "2026-08-19",
                "source": "stage901_pending_order",
                "vt_symbol": "SI2609.GFEX",
                "direction": "short",
                "offset": "close",
                "planned_volume": 6,
                "limit_price": 8500.0,
            },
            contracts=pd.DataFrame(
                [
                    {
                        "vt_symbol": "SI2609.GFEX",
                        "pricetick": 5.0,
                        "min_volume": 1,
                        "max_volume": 100,
                        "gateway_name": "CTP",
                    }
                ]
            ),
            positions=pd.DataFrame(
                [
                    {
                        "vt_symbol": "SI2609.GFEX",
                        "direction": "long",
                        "volume": 6,
                        "frozen": 0,
                    }
                ]
            ),
            orders=pd.DataFrame(),
            stage902_summary={
                "blocking_failure_count": 0,
                "blocking_failure_count_for_reduce_close": 0,
                "allow_new_open": 1,
                "allow_reduce_close": 1,
            },
            stage904_summary={},
            stage260_summary={"executable_count": 1},
            mode="dry-run",
        )

        self.assertEqual(
            "dry_run_order_request_payload_ready",
            checked["executor_status"],
        )
        request = stage905.json.loads(checked["order_request_json"])
        self.assertEqual("SI2609", request["symbol"])
        self.assertEqual("空", request["direction"])
        self.assertEqual("平", request["offset"])
        self.assertEqual(6, request["volume"])

    def test_local_20_lot_cap_is_disabled_but_contract_max_still_blocks(self) -> None:
        intent = {
            "intent_id": "pending-open-volume",
            "target_date": "2026-08-10",
            "source": "stage901_pending_order",
            "vt_symbol": "JM609.DCE",
            "direction": "short",
            "offset": "open",
            "planned_volume": 21,
            "limit_price": 1245.5,
        }
        common = {
            "contracts": pd.DataFrame(
                [{
                    "vt_symbol": "JM609.DCE",
                    "pricetick": 0.5,
                    "min_volume": 1,
                    "max_volume": 100,
                    "gateway_name": "CTP",
                }]
            ),
            "positions": pd.DataFrame(),
            "orders": pd.DataFrame(),
            "stage902_summary": {
                "blocking_failure_count": 0,
                "blocking_failure_count_for_reduce_close": 0,
                "allow_new_open": 1,
                "allow_reduce_close": 1,
            },
            "stage904_summary": {},
            "stage260_summary": {"executable_count": 1},
            "mode": "dry-run",
        }

        ready = stage905._validate_intent(intent, **common)
        contract_blocked = stage905._validate_intent(
            {**intent, "planned_volume": 101},
            **common,
        )

        self.assertEqual("dry_run_order_request_payload_ready", ready["executor_status"])
        self.assertNotIn("volume_above_phase_d_limit", ready["executor_reason"])
        self.assertEqual("blocked", contract_blocked["executor_status"])
        self.assertIn("volume_above_contract_max", contract_blocked["executor_reason"])

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
        self.assertEqual(row["target_date"], "2026-07-13")
        self.assertEqual(row["intent_role"], "c9_initial_open")
        self.assertTrue(row["root_position_id"].startswith("c9root-"))
        self.assertTrue(row["position_cycle_id"].endswith(":cycle0"))
        self.assertEqual(row["position_cycle_no"], 0)
        self.assertTrue(row["position_epoch_id"].startswith("c9pos-"))

    def test_pending_identity_is_row_order_stable_date_scoped_and_preallocates_epoch(self) -> None:
        pending = pd.DataFrame(
            [
                {
                    "vt_symbol": "JM609.DCE",
                    "direction": "short",
                    "offset": "open",
                    "volume": 2,
                    "price": 1245.5,
                    "stop_price": 1258.0,
                },
                {
                    "vt_symbol": "RB610.SHFE",
                    "direction": "long",
                    "offset": "open",
                    "volume": 1,
                    "price": 3300.0,
                    "stop_price": 3250.0,
                },
            ]
        )

        first = stage905._pending_order_intents(pending, "2026-07-13")
        reordered = stage905._pending_order_intents(
            pending.iloc[::-1].reset_index(drop=True),
            "2026-07-13",
        )
        next_date = stage905._pending_order_intents(pending, "2026-07-14")

        first_ids = {row["vt_symbol"]: row["intent_id"] for row in first}
        self.assertEqual(
            first_ids,
            {row["vt_symbol"]: row["intent_id"] for row in reordered},
        )
        self.assertNotEqual(first_ids["JM609.DCE"], next_date[0]["intent_id"])
        self.assertTrue(first_ids["JM609.DCE"].startswith("STAGE905-PENDING-"))
        self.assertEqual(
            "preallocated_stage901_pending_order",
            first[0]["position_epoch_source"],
        )
        self.assertEqual(
            f"{first[0]['position_epoch_id']}:0",
            first[0]["state_generation"],
        )

    def test_traced_pending_open_requires_exact_symbol_and_commits_real_spool(self) -> None:
        action = self._traced_action(
            monitor_action="retry_open_dry_run",
            action_id="unused-action-id",
        )
        provenance = {
            key: action[key]
            for key in stage905.STAGE904_PROVENANCE_FIELDS
            if key in action and key != "state_generation"
        }
        provenance["vt_symbol"] = "JM609.DCE"
        pending = pd.DataFrame(
            [
                {
                    "vt_symbol": "JM609.DCE",
                    "direction": "short",
                    "offset": "open",
                    "volume": 2,
                    "price": 1245.5,
                    "stop_price": 1258.0,
                },
                {
                    "vt_symbol": "RB610.SHFE",
                    "direction": "long",
                    "offset": "open",
                    "volume": 1,
                    "price": 3300.0,
                    "stop_price": 3250.0,
                },
            ]
        )
        clock = _FakeClock(
            epoch_ns=int(action["ingress_epoch_ns"]) + 1_000_000_000,
            monotonic_ns=int(action["ingress_monotonic_ns"]) + 1_000_000_000,
        )
        generated_at = datetime.fromtimestamp(
            clock.epoch_ns() / 1_000_000_000
        ).strftime("%Y-%m-%d %H:%M:%S")
        result = stage905.run_executor_dry_run(
            "2026-07-13",
            stage904_actions=pd.DataFrame(),
            stage904_summary=self._stage904_summary(
                generated_at,
                action_count=0,
                retry_count=0,
            ),
            snapshots=self._snapshots(
                pending_orders=pending,
                positions=pd.DataFrame(),
                stage260_executable=1,
            ),
            pending_initial_open_provenance={"JM609.DCE": provenance},
            clock=clock,
            write_compat_outputs=False,
        )

        self.assertEqual(["JM609.DCE"], result.intents["vt_symbol"].tolist())
        intent = dict(result.intents.iloc[0])
        self.assertEqual("dry_run_order_request_payload_ready", intent["executor_status"])
        trace = LatencyTrace.from_json(intent["trace_json"])
        self.assertIn("stage905_intent_ready", trace.stamps)
        self.assertNotIn("trace_json", json.loads(intent["spool_payload_json"]))
        with tempfile.TemporaryDirectory() as tempdir:
            connection = intent_spool.open_spool(Path(tempdir) / "pending.sqlite3")
            try:
                committed = intent_spool.commit_detector_batch(
                    connection,
                    consumer_id="stage941",
                    expected_cursor=None,
                    next_cursor=DurableTickCursor("feed-a", 12, 8192),
                    intents=[intent],
                    now_epoch_ns=clock.epoch_ns(),
                    now_monotonic_ns=clock.monotonic_ns(),
                    clock_domain_id=clock.clock_domain_id(),
                )
                self.assertEqual(1, committed.inserted_count)
            finally:
                connection.close()

    def test_traced_pending_open_deadline_expiry_fails_closed(self) -> None:
        action = self._traced_action(
            monitor_action="retry_open_dry_run",
            action_id="unused-action-id",
        )
        provenance = {
            key: action[key]
            for key in stage905.STAGE904_PROVENANCE_FIELDS
            if key in action and key != "state_generation"
        }
        provenance["vt_symbol"] = "JM609.DCE"
        clock = _FakeClock(
            epoch_ns=int(action["deadline_epoch_ns"]),
            monotonic_ns=int(action["deadline_monotonic_ns"]),
        )
        generated_at = datetime.fromtimestamp(
            clock.epoch_ns() / 1_000_000_000
        ).strftime("%Y-%m-%d %H:%M:%S")
        result = stage905.run_executor_dry_run(
            "2026-07-13",
            stage904_actions=pd.DataFrame(),
            stage904_summary=self._stage904_summary(
                generated_at,
                action_count=0,
                retry_count=0,
            ),
            snapshots=self._snapshots(
                pending_orders=pd.DataFrame(
                    [{"vt_symbol": "JM609.DCE", "direction": "short", "offset": "open", "volume": 2, "price": 1245.5, "stop_price": 1258.0}]
                ),
                positions=pd.DataFrame(),
                stage260_executable=1,
            ),
            pending_initial_open_provenance={"JM609.DCE": provenance},
            clock=clock,
            write_compat_outputs=False,
        )

        self.assertEqual("expired", result.intents.iloc[0]["executor_status"])

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

    def test_capability_migration_blocks_never_create_open_intents_but_close_only_survives(
        self,
    ) -> None:
        common = {
            "target_date": "2026-07-13",
            "vt_symbol": "JM609.DCE",
            "direction": "short",
            "volume": 2,
            "stage847_stop_price": 1251.75,
            "root_position_id": "root",
            "position_cycle_id": "root:cycle1",
            "position_cycle_no": 1,
            "position_epoch_id": "epoch-001",
            "manual_intervention_required": 1,
            "risk_alert_level": "P1",
            "migration_blocker": "state_risk_transition_capability_provenance_missing",
        }
        actions = pd.DataFrame(
            [
                {
                    **common,
                    "monitor_action": "block",
                    "action_id": "stale-open-action-must-not-survive",
                    "intent_role": "c9_retry_open_once",
                },
                {
                    **common,
                    "monitor_action": "retry_block",
                    "action_id": "another-stale-open-action",
                    "intent_role": "c9_retry_open_once",
                },
                {
                    **common,
                    "monitor_action": "retry_open_dry_run",
                    "action_id": "manual-open-must-block",
                    "intent_role": "c9_retry_open_once",
                    "stage847_retry_trigger_price": 1245.5,
                },
                {
                    **common,
                    "monitor_action": "close_dry_run",
                    "action_id": "migration-close-only",
                    "intent_role": "c9_retry_failed_stop_close",
                },
            ]
        )

        intents = stage905._stage904_intents(actions)

        self.assertEqual(2, len(intents))
        close = next(row for row in intents if row["offset"] == "close")
        retry = next(row for row in intents if row["offset"] == "open")
        self.assertEqual("migration-close-only", close["intent_id"])
        self.assertEqual(1, close["manual_intervention_required"])
        self.assertEqual("manual-open-must-block", retry["intent_id"])
        self.assertEqual(1, retry["manual_intervention_required"])
        self.assertEqual("P1", retry["risk_alert_level"])
        self.assertIn("capability_provenance", retry["migration_blocker"])

    def test_retry_open_requires_authoritative_retry_summary_and_no_migration_blocker(
        self,
    ) -> None:
        action = {
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
            "manual_intervention_required": 0,
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
            "positions": pd.DataFrame(),
            "orders": pd.DataFrame(),
            "stage902_summary": {
                "blocking_failure_count": 0,
                "blocking_failure_count_for_reduce_close": 0,
                "allow_new_open": 1,
                "allow_reduce_close": 1,
            },
            "stage260_summary": {"executable_count": 0},
            "mode": "dry-run",
        }
        summary = {
            "model_tag": stage905.STAGE904_MODEL_TAG,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "target_date": "2026-07-13",
            "monitor_run_id": "run-001",
            "monitor_status": "intraday_monitor_retry_open_dry_run",
        }
        ready = stage905._validate_intent(
            intent,
            stage904_summary=summary,
            **common,
        )
        blocked_summary = stage905._validate_intent(
            intent,
            stage904_summary={
                **summary,
                "monitor_status": "intraday_monitor_blocked",
            },
            **common,
        )
        manual_intent = {
            **intent,
            "manual_intervention_required": 1,
            "risk_alert_level": "P1",
            "migration_blocker": "state_risk_transition_capability_provenance_missing",
        }
        blocked_manual = stage905._validate_intent(
            manual_intent,
            stage904_summary=summary,
            **common,
        )
        blocked_missing_id = stage905._validate_intent(
            {**intent, "intent_id": "", "action_id": ""},
            stage904_summary=summary,
            **common,
        )
        blocked_wrong_role = stage905._validate_intent(
            {**intent, "intent_role": "c9_initial_stop_close"},
            stage904_summary=summary,
            **common,
        )

        self.assertEqual(
            "dry_run_order_request_payload_ready", ready["executor_status"]
        )
        payload = stage905.json.loads(ready["order_request_json"])
        self.assertEqual("retry-action", payload["intent_id"])
        self.assertEqual("stage904_c9_intraday_retry_open", payload["source"])
        self.assertEqual("2026-07-13", payload["target_date"])
        self.assertEqual("FAK", payload["type"])
        self.assertEqual("stage179_open_fak_v1", payload["physical_tif_policy_version"])
        self.assertEqual(0, payload["manual_intervention_required"])
        self.assertEqual("blocked", blocked_summary["executor_status"])
        self.assertIn(
            "stage904_summary_not_authoritative_for_retry_open",
            blocked_summary["executor_reason"],
        )
        self.assertEqual("blocked", blocked_manual["executor_status"])
        self.assertIn(
            "stage904_manual_migration_blocker",
            blocked_manual["executor_reason"],
        )
        self.assertIn(
            "stage904_action_id_missing", blocked_missing_id["executor_reason"]
        )
        self.assertIn(
            "stage904_retry_open_intent_role_mismatch",
            blocked_wrong_role["executor_reason"],
        )

    def test_retry_open_missing_source_role_is_not_synthesized(self) -> None:
        action = {
            "monitor_action": "retry_open_dry_run",
            "target_date": "2026-07-13",
            "monitor_run_id": "run-001",
            "action_id": "retry-action",
            "vt_symbol": "JM609.DCE",
            "direction": "short",
            "volume": 1,
            "stage847_retry_trigger_price": 1245.5,
            "stage847_stop_price": 1251.75,
            "root_position_id": "root",
            "position_cycle_id": "root:cycle1",
            "position_cycle_no": 1,
            "position_epoch_id": "epoch-001",
            "manual_intervention_required": 0,
        }
        intent = stage905._stage904_intents(pd.DataFrame([action]))[0]

        self.assertEqual("", intent.get("intent_role", ""))
        checked = stage905._validate_intent(
            intent,
            contracts=pd.DataFrame(
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
            positions=pd.DataFrame(),
            orders=pd.DataFrame(),
            stage902_summary={
                "blocking_failure_count": 0,
                "blocking_failure_count_for_reduce_close": 0,
                "allow_new_open": 1,
                "allow_reduce_close": 1,
            },
            stage904_summary={
                "model_tag": stage905.STAGE904_MODEL_TAG,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "target_date": "2026-07-13",
                "monitor_run_id": "run-001",
                "monitor_status": "intraday_monitor_retry_open_dry_run",
            },
            stage260_summary={"executable_count": 0},
            mode="dry-run",
        )
        self.assertEqual("blocked", checked["executor_status"])
        self.assertIn(
            "stage904_retry_open_intent_role_mismatch",
            checked["executor_reason"],
        )

    def test_retry_open_noncanonical_manual_flag_fails_closed(self) -> None:
        action = {
            "monitor_action": "retry_open_dry_run",
            "target_date": "2026-07-13",
            "monitor_run_id": "run-001",
            "action_id": "retry-action",
            "vt_symbol": "JM609.DCE",
            "direction": "short",
            "volume": 1,
            "stage847_retry_trigger_price": 1245.5,
            "stage847_stop_price": 1251.75,
            "root_position_id": "root",
            "position_cycle_id": "root:cycle1",
            "position_cycle_no": 1,
            "position_epoch_id": "epoch-001",
            "intent_role": "c9_retry_open_once",
            "manual_intervention_required": "true",
        }
        intent = stage905._stage904_intents(pd.DataFrame([action]))[0]
        self.assertEqual("true", intent["manual_intervention_required"])

        checked = stage905._validate_intent(
            intent,
            contracts=pd.DataFrame(
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
            positions=pd.DataFrame(),
            orders=pd.DataFrame(),
            stage902_summary={
                "blocking_failure_count": 0,
                "blocking_failure_count_for_reduce_close": 0,
                "allow_new_open": 1,
                "allow_reduce_close": 1,
            },
            stage904_summary={
                "model_tag": stage905.STAGE904_MODEL_TAG,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "target_date": "2026-07-13",
                "monitor_run_id": "run-001",
                "monitor_status": "intraday_monitor_retry_open_dry_run",
            },
            stage260_summary={"executable_count": 0},
            mode="dry-run",
        )
        self.assertEqual("blocked", checked["executor_status"])
        self.assertIn(
            "stage904_manual_intervention_required_invalid",
            checked["executor_reason"],
        )

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
