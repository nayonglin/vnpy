from __future__ import annotations

import json
import os
from dataclasses import FrozenInstanceError
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
import uuid


PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

from qmt_roll_official_live_time import SystemClock, utc_iso_from_epoch_ns
from qmt_roll_official_live_tick_stream import TickStreamPipeline
from qmt_roll_official_live_trace import (
    ClockStamp,
    LatencyTrace,
    SLA_BUDGETS,
    TraceStage,
    TraceValidationError,
    deadline_disposition,
    deterministic_trace_id,
    disposition_for_trace,
    evaluate_sla,
)


class VirtualClock:
    def __init__(
        self,
        *,
        epoch_ns: int = 1_800_000_000_000_000_000,
        monotonic_ns: int = 10_000_000_000,
        domain_id: str = "boot-a",
    ) -> None:
        self.epoch = epoch_ns
        self.monotonic = monotonic_ns
        self.domain = domain_id

    def epoch_ns(self) -> int:
        return self.epoch

    def monotonic_ns(self) -> int:
        return self.monotonic

    def sleep(self, seconds: float) -> None:
        delta = int(seconds * 1_000_000_000)
        self.advance(delta)

    def clock_domain_id(self) -> str:
        return self.domain

    def advance(self, nanoseconds: int) -> None:
        self.epoch += nanoseconds
        self.monotonic += nanoseconds


class OfficialLiveTraceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = VirtualClock()

    def ingress_row(self, **updates: object) -> dict[str, object]:
        row: dict[str, object] = {
            "feed_session_id": "feed-a",
            "ingress_sequence": 7,
            "symbol_sequence": 3,
            "vt_symbol": "JM609.DCE",
            "ingress_epoch_ns": self.clock.epoch_ns(),
            "ingress_monotonic_ns": self.clock.monotonic_ns(),
            "received_at_utc": utc_iso_from_epoch_ns(self.clock.epoch_ns()),
            "clock_domain_id": self.clock.clock_domain_id(),
            "trace_id": "stage179-tick/feed-a/7",
        }
        row.update(updates)
        return row

    def trace(self) -> LatencyTrace:
        return LatencyTrace.from_ingress_row(self.ingress_row(), clock=self.clock)

    def stamp_at(
        self,
        elapsed_ns: int,
        *,
        domain_id: str = "boot-a",
    ) -> ClockStamp:
        epoch_ns = 1_800_000_000_000_000_000 + elapsed_ns
        return ClockStamp(
            epoch_ns=epoch_ns,
            monotonic_ns=10_000_000_000 + elapsed_ns,
            clock_domain_id=domain_id,
            utc_iso=utc_iso_from_epoch_ns(epoch_ns),
        )

    def budget(self, name: str):
        return next(item for item in SLA_BUDGETS if item.name == name)

    def test_virtual_clock_expires_at_exact_25_second_boundary(self) -> None:
        self.assertEqual("ready", deadline_disposition(24_999_999_999, "open"))
        self.assertEqual("expired", deadline_disposition(25_000_000_000, "open"))
        self.assertEqual("blocked", deadline_disposition(25_000_000_000, "close"))

    def test_trace_deadlines_are_exact_and_either_clock_reaching_them_is_late(
        self,
    ) -> None:
        trace = self.trace()
        ingress = trace.stamps[TraceStage.GATEWAY_INGRESS.value]
        self.assertEqual(ingress.epoch_ns + 25_000_000_000, trace.deadline_epoch_ns)
        self.assertEqual(
            ingress.monotonic_ns + 25_000_000_000,
            trace.deadline_monotonic_ns,
        )

        both_before = ClockStamp(
            epoch_ns=trace.deadline_epoch_ns - 1,
            monotonic_ns=trace.deadline_monotonic_ns - 1,
            clock_domain_id=ingress.clock_domain_id,
            utc_iso=utc_iso_from_epoch_ns(trace.deadline_epoch_ns - 1),
        )
        epoch_exact_monotonic_before = ClockStamp(
            epoch_ns=trace.deadline_epoch_ns,
            monotonic_ns=trace.deadline_monotonic_ns - 1,
            clock_domain_id=ingress.clock_domain_id,
            utc_iso=utc_iso_from_epoch_ns(trace.deadline_epoch_ns),
        )
        epoch_before_monotonic_exact = ClockStamp(
            epoch_ns=trace.deadline_epoch_ns - 1,
            monotonic_ns=trace.deadline_monotonic_ns,
            clock_domain_id=ingress.clock_domain_id,
            utc_iso=utc_iso_from_epoch_ns(trace.deadline_epoch_ns - 1),
        )

        self.assertEqual(
            "ready",
            disposition_for_trace(trace, now=both_before, intent_kind="open"),
        )
        self.assertEqual(
            "expired",
            disposition_for_trace(
                trace,
                now=epoch_exact_monotonic_before,
                intent_kind="open",
            ),
        )
        self.assertEqual(
            "blocked",
            disposition_for_trace(
                trace,
                now=epoch_before_monotonic_exact,
                intent_kind="close",
            ),
        )

    def test_missing_required_stamp_is_ineligible_not_pass(self) -> None:
        result = evaluate_sla(
            self.trace(),
            self.budget("ingress_to_journal_durable"),
        )

        self.assertEqual("missing_timestamp", result.status)
        self.assertFalse(result.eligible)
        self.assertFalse(result.passed)
        self.assertTrue(result.applicable)

    def test_trace_round_trip_preserves_integer_nanoseconds_and_source_identity(
        self,
    ) -> None:
        original = self.trace()
        original = original.record_stamp(
            TraceStage.JOURNAL_DURABLE,
            self.stamp_at(500_000_000),
        )

        restored = LatencyTrace.from_json(original.to_json())

        self.assertIsInstance(
            restored.stamps[TraceStage.GATEWAY_INGRESS.value].epoch_ns,
            int,
        )
        self.assertEqual(original, restored)
        self.assertEqual("stage179-tick/feed-a/7", restored.source_tick_trace_id)
        self.assertEqual(5, uuid.UUID(restored.trace_id).version)

    def test_real_stage608_ingress_row_carries_clock_domain_and_builds_trace(self) -> None:
        pipeline = TickStreamPipeline(
            feed_session_id="feed-real-interface",
            journal_segment_path=Path("unused.ndjson"),
            clock=self.clock,
            queue_capacity=2,
            max_buffer_ticks=2,
        )
        tick = SimpleNamespace(
            vt_symbol="JM609.DCE",
            symbol="JM609",
            exchange=SimpleNamespace(value="DCE"),
            datetime=None,
            last_price=1245.5,
            bid_price_1=1245.0,
            ask_price_1=1245.5,
            bid_volume_1=1,
            ask_volume_1=1,
            limit_up=1400.0,
            limit_down=1100.0,
        )

        row = pipeline.capture_ingress(tick).tick_row
        trace = LatencyTrace.from_ingress_row(row, clock=self.clock)

        self.assertEqual("boot-a", row["clock_domain_id"])
        self.assertEqual(row["ingress_sequence"], trace.ingress_sequence)

    def test_clock_domain_change_fails_closed(self) -> None:
        trace = self.trace()
        changed_domain = self.stamp_at(1_000_000_000, domain_id="boot-b")

        self.assertEqual(
            "expired",
            disposition_for_trace(trace, now=changed_domain, intent_kind="open"),
        )
        self.assertEqual(
            "blocked",
            disposition_for_trace(trace, now=changed_domain, intent_kind="close"),
        )

    def test_system_clock_domain_is_stable_across_exec_processes(self) -> None:
        parent_domain = SystemClock().clock_domain_id()
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            [str(PORTFOLIO_DIR), env.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep)
        child_domain = subprocess.check_output(
            [
                sys.executable,
                "-c",
                (
                    "from qmt_roll_official_live_time import SystemClock;"
                    "print(SystemClock().clock_domain_id())"
                ),
            ],
            env=env,
            text=True,
        ).strip()

        self.assertTrue(parent_domain)
        self.assertEqual(parent_domain, child_domain)

    def test_deterministic_trace_id_is_uuid5_over_feed_and_ingress(self) -> None:
        first = deterministic_trace_id("feed-a", 7)
        second = deterministic_trace_id("feed-a", 7)

        self.assertEqual(first, second)
        self.assertEqual("5a171996-b5c5-5c21-92c6-37c2f0698aab", first)
        self.assertEqual(5, uuid.UUID(first).version)
        self.assertNotEqual(first, deterministic_trace_id("feed-a", 8))

    def test_identical_repeated_stamp_is_idempotent_but_conflict_raises(self) -> None:
        trace = self.trace()
        stamp = self.stamp_at(500_000_000)

        trace = trace.record_stamp(TraceStage.JOURNAL_DURABLE, stamp)
        repeated = trace.record_stamp(TraceStage.JOURNAL_DURABLE, stamp)
        self.assertIs(trace, repeated)
        self.assertEqual(2, len(trace.stamps))

        with self.assertRaisesRegex(TraceValidationError, "stamp_conflict"):
            trace.record_stamp(
                TraceStage.JOURNAL_DURABLE,
                self.stamp_at(500_000_001),
            )

    def test_independent_callback_stamps_may_arrive_out_of_recording_order(self) -> None:
        trace = self.trace()
        trace = trace.record_stamp(
            TraceStage.JOURNAL_DURABLE,
            self.stamp_at(500_000_000),
        )
        trace = trace.record_stamp(
            TraceStage.EVENT_HANDLER_OBSERVED,
            self.stamp_at(100_000_000),
        )

        self.assertEqual(
            100_000_000,
            trace.stamps[TraceStage.EVENT_HANDLER_OBSERVED.value].monotonic_ns
            - trace.stamps[TraceStage.GATEWAY_INGRESS.value].monotonic_ns,
        )

    def test_negative_cursor_naive_utc_and_legacy_trace_tamper_are_rejected(self) -> None:
        with self.assertRaises(TraceValidationError):
            LatencyTrace.from_ingress_row(
                self.ingress_row(ingress_sequence=-1),
                clock=self.clock,
            )
        with self.assertRaises(TraceValidationError):
            ClockStamp(
                epoch_ns=self.clock.epoch_ns(),
                monotonic_ns=self.clock.monotonic_ns(),
                clock_domain_id="boot-a",
                utc_iso="2027-01-15T08:00:00",
            )
        with self.assertRaisesRegex(TraceValidationError, "source_tick_trace_id"):
            LatencyTrace.from_ingress_row(
                self.ingress_row(trace_id="stage179-tick/other/7"),
                clock=self.clock,
            )

    def test_ingress_clock_domain_must_be_persisted_and_match_current_boot(self) -> None:
        missing_domain = self.ingress_row()
        del missing_domain["clock_domain_id"]
        with self.assertRaisesRegex(TraceValidationError, "ingress_clock_domain_id"):
            LatencyTrace.from_ingress_row(missing_domain, clock=self.clock)
        with self.assertRaisesRegex(TraceValidationError, "ingress_clock_domain_mismatch"):
            LatencyTrace.from_ingress_row(
                self.ingress_row(clock_domain_id="boot-old"),
                clock=self.clock,
            )

    def test_tampered_deadline_or_monotonic_rollback_raises(self) -> None:
        trace = self.trace()
        payload = trace.to_dict()
        payload["deadline_epoch_ns"] += 1

        with self.assertRaisesRegex(TraceValidationError, "deadline"):
            LatencyTrace.from_dict(payload)
        with self.assertRaisesRegex(TraceValidationError, "monotonic_rollback"):
            trace.record_stamp(
                TraceStage.JOURNAL_DURABLE,
                self.stamp_at(-1),
            )

    def test_duplicate_json_members_fail_closed_at_any_depth(self) -> None:
        payload = self.trace().to_json()
        duplicate_top = payload.replace(
            '"schema_version":1',
            '"schema_version":999,"schema_version":1',
            1,
        )
        duplicate_nested = payload.replace(
            '"epoch_ns":1800000000000000000',
            '"epoch_ns":1,"epoch_ns":1800000000000000000',
            1,
        )

        for candidate in (duplicate_top, duplicate_nested):
            with self.subTest(candidate=candidate[:80]):
                with self.assertRaisesRegex(TraceValidationError, "duplicate"):
                    LatencyTrace.from_json(candidate)

    def test_cross_boot_epoch_rollback_is_rejected_but_forward_epoch_is_auditable(self) -> None:
        trace = self.trace()
        ingress = trace.stamps[TraceStage.GATEWAY_INGRESS.value]
        with self.assertRaisesRegex(TraceValidationError, "cross_domain_epoch_rollback"):
            trace.record_stamp(
                TraceStage.JOURNAL_DURABLE,
                ClockStamp(
                    epoch_ns=ingress.epoch_ns - 1,
                    monotonic_ns=1,
                    clock_domain_id="boot-b",
                    utc_iso=utc_iso_from_epoch_ns(ingress.epoch_ns - 1),
                ),
            )

        forward = trace.record_stamp(
            TraceStage.JOURNAL_DURABLE,
            ClockStamp(
                epoch_ns=ingress.epoch_ns + 2_000_000_000,
                monotonic_ns=1,
                clock_domain_id="boot-b",
                utc_iso=utc_iso_from_epoch_ns(ingress.epoch_ns + 2_000_000_000),
            ),
        )
        result = evaluate_sla(
            forward,
            self.budget("ingress_to_journal_durable"),
        )
        self.assertEqual("clock_domain_mismatch", result.status)
        self.assertFalse(result.eligible)
        self.assertEqual(2_000_000_000, result.audit_epoch_latency_ns)

    def test_exact_approved_sla_budgets_and_required_intermediates(self) -> None:
        actual = {
            item.name: (
                item.slo_ns,
                item.hard_limit_ns,
                tuple(stage.value for stage in item.required_intermediate_stages),
            )
            for item in SLA_BUDGETS
        }
        self.assertEqual(
            {
                "ingress_to_journal_durable": (500_000_000, 1_000_000_000, ()),
                "journal_durable_to_stage904": (500_000_000, 1_000_000_000, ()),
                "stage904_to_spool": (
                    250_000_000,
                    500_000_000,
                    ("stage905_intent_ready",),
                ),
                "spool_to_executor_dequeue": (100_000_000, 500_000_000, ()),
                "dequeue_to_send_order": (
                    15_000_000_000,
                    20_000_000_000,
                    ("broker_bundle_ready",),
                ),
                "ingress_to_send_order": (
                    17_000_000_000,
                    25_000_000_000,
                    (
                        "journal_durable",
                        "stage904_detected",
                        "stage905_intent_ready",
                        "spool_committed",
                        "executor_dequeued",
                        "broker_bundle_ready",
                    ),
                ),
                "send_order_to_first_ack": (2_000_000_000, 3_000_000_000, ()),
                "send_order_to_first_fill": (5_000_000_000, 8_000_000_000, ()),
                "cancel_to_terminal": (8_000_000_000, 10_000_000_000, ()),
                "fill_to_ledger_durable": (500_000_000, 2_000_000_000, ()),
            },
            actual,
        )

    def test_required_intermediate_missing_cannot_make_endpoint_only_trace_pass(
        self,
    ) -> None:
        trace = self.trace()
        trace = trace.record_stamp(
            TraceStage.STAGE904_DETECTED,
            self.stamp_at(100_000_000),
        )
        trace = trace.record_stamp(
            TraceStage.SPOOL_COMMITTED,
            self.stamp_at(200_000_000),
        )

        result = evaluate_sla(trace, self.budget("stage904_to_spool"))

        self.assertEqual("missing_timestamp", result.status)
        self.assertFalse(result.eligible)
        self.assertFalse(result.passed)

    def test_conditional_fill_and_cancel_segments_are_not_applicable(self) -> None:
        trace = self.trace()

        for budget_name in (
            "send_order_to_first_fill",
            "cancel_to_terminal",
            "fill_to_ledger_durable",
        ):
            with self.subTest(budget_name=budget_name):
                result = evaluate_sla(trace, self.budget(budget_name))
                self.assertEqual("not_applicable", result.status)
                self.assertFalse(result.applicable)
                self.assertFalse(result.eligible)
                self.assertFalse(result.passed)

    def test_conditional_downstream_evidence_without_activation_is_missing(self) -> None:
        cases = (
            ("cancel_to_terminal", TraceStage.CANCEL_TERMINAL, "cancel_requested"),
            ("fill_to_ledger_durable", TraceStage.LEDGER_DURABLE, "first_fill"),
        )
        for budget_name, downstream_stage, missing_stage in cases:
            with self.subTest(budget_name=budget_name):
                trace = self.trace().record_stamp(
                    downstream_stage,
                    self.stamp_at(1_000_000_000),
                )
                result = evaluate_sla(trace, self.budget(budget_name))
                self.assertEqual("missing_timestamp", result.status)
                self.assertTrue(result.applicable)
                self.assertFalse(result.eligible)
                self.assertEqual((missing_stage,), result.missing_stages)

    def test_slo_and_hard_limit_boundaries_use_integer_nanoseconds(self) -> None:
        at_slo = self.trace()
        at_slo = at_slo.record_stamp(
            TraceStage.JOURNAL_DURABLE,
            self.stamp_at(500_000_000),
        )
        after_slo = self.trace()
        after_slo = after_slo.record_stamp(
            TraceStage.JOURNAL_DURABLE,
            self.stamp_at(500_000_001),
        )
        at_hard = self.trace()
        at_hard = at_hard.record_stamp(
            TraceStage.JOURNAL_DURABLE,
            self.stamp_at(1_000_000_000),
        )
        budget = self.budget("ingress_to_journal_durable")

        self.assertEqual("passed", evaluate_sla(at_slo, budget).status)
        after_slo_result = evaluate_sla(after_slo, budget)
        self.assertEqual("slo_exceeded", after_slo_result.status)
        self.assertFalse(after_slo_result.passed)
        self.assertFalse(after_slo_result.slo_met)
        self.assertEqual("hard_limit_exceeded", evaluate_sla(at_hard, budget).status)

    def test_sla_uses_same_domain_monotonic_when_wall_epoch_rolls_back(self) -> None:
        trace = self.trace()
        ingress = trace.stamps[TraceStage.GATEWAY_INGRESS.value]
        rolled_back_epoch = ingress.epoch_ns - 1_000_000_000
        trace = trace.record_stamp(
            TraceStage.JOURNAL_DURABLE,
            ClockStamp(
                epoch_ns=rolled_back_epoch,
                monotonic_ns=ingress.monotonic_ns + 500_000_000,
                clock_domain_id=ingress.clock_domain_id,
                utc_iso=utc_iso_from_epoch_ns(rolled_back_epoch),
            ),
        )

        result = evaluate_sla(
            trace,
            self.budget("ingress_to_journal_durable"),
        )
        self.assertEqual("passed", result.status)
        self.assertEqual(500_000_000, result.latency_ns)

    def test_trace_is_immutable_and_stamp_updates_are_copy_on_write(self) -> None:
        original = self.trace()
        updated = original.record_stamp(
            TraceStage.JOURNAL_DURABLE,
            self.stamp_at(500_000_000),
        )

        self.assertNotIn(TraceStage.JOURNAL_DURABLE.value, original.stamps)
        self.assertIn(TraceStage.JOURNAL_DURABLE.value, updated.stamps)
        with self.assertRaises(TypeError):
            original.stamps[TraceStage.JOURNAL_DURABLE.value] = self.stamp_at(1)
        with self.assertRaises(FrozenInstanceError):
            original.deadline_epoch_ns += 1

    def test_serialized_nanoseconds_reject_bool_float_and_unknown_stage(self) -> None:
        payload = json.loads(self.trace().to_json())
        payload["ingress_sequence"] = True
        with self.assertRaises(TraceValidationError):
            LatencyTrace.from_dict(payload)

        trace = self.trace()
        with self.assertRaises(TraceValidationError):
            trace.record_stamp("unknown_stage", self.stamp_at(1))

    def test_budget_copies_mutable_required_stage_input(self) -> None:
        from qmt_roll_official_live_trace import SlaBudget

        stages = [TraceStage.STAGE905_INTENT_READY]
        budget = SlaBudget(
            "copy-required-stages",
            TraceStage.STAGE904_DETECTED,
            TraceStage.SPOOL_COMMITTED,
            1,
            2,
            required_intermediate_stages=stages,
        )
        stages.clear()

        self.assertEqual(
            (TraceStage.STAGE905_INTENT_READY,),
            budget.required_intermediate_stages,
        )

    def test_pathological_json_numbers_raise_trace_validation_error(self) -> None:
        payload = self.trace().to_json()
        huge_integer = "9" * 5000
        malformed = payload.replace(
            '"ingress_sequence":7',
            f'"ingress_sequence":{huge_integer}',
            1,
        )
        with self.assertRaises(TraceValidationError):
            LatencyTrace.from_json(malformed)

        decoded = json.loads(payload)
        ingress = decoded["stamps"][TraceStage.GATEWAY_INGRESS.value]
        ingress["epoch_ns"] = 10**30
        ingress["utc_iso"] = "9999-12-31T23:59:59.999999999Z"
        with self.assertRaises(TraceValidationError):
            LatencyTrace.from_dict(decoded)


if __name__ == "__main__":
    unittest.main()
