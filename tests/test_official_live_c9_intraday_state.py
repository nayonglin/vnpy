from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
sys.path.insert(0, str(MODULE_DIR))

import qmt_roll_official_live_c9_intraday_state as c9  # noqa: E402
from qmt_roll_official_live_time import utc_iso_from_epoch_ns  # noqa: E402
from qmt_roll_official_live_trace import LatencyTrace  # noqa: E402


class TraceClock:
    def clock_domain_id(self) -> str:
        return "boot-test"


class C9IntradayStateTest(unittest.TestCase):
    def make_state(self, *, direction: str = "short") -> dict:
        original_stop = 110.0 if direction == "short" else 90.0
        return c9.new_state(
            target_date="2026-07-13",
            vt_symbol="JM2609.DCE",
            direction=direction,
            position_epoch_id="broker-fill-001",
            entry_filled_at="2026-07-13T21:00:01+08:00",
            entry_price=100.0,
            original_stop_price=original_stop,
            volume=1,
        )

    def tick(
        self,
        at: str,
        seq: int,
        price: float,
        *,
        feed: str = "feed-a",
        bid: float | None = None,
        ask: float | None = None,
    ) -> dict:
        ingress_epoch_ns = 1_784_000_000_000_000_000 + seq
        ingress_monotonic_ns = 900_000_000 + seq
        trace = LatencyTrace.from_ingress_row(
            {
                "feed_session_id": feed,
                "ingress_sequence": seq,
                "symbol_sequence": seq,
                "vt_symbol": "JM2609.DCE",
                "ingress_epoch_ns": ingress_epoch_ns,
                "ingress_monotonic_ns": ingress_monotonic_ns,
                "received_at_utc": utc_iso_from_epoch_ns(ingress_epoch_ns),
                "clock_domain_id": "boot-test",
                "trace_id": f"stage179-tick/{feed}/{seq}",
            },
            clock=TraceClock(),
        )
        trace_id = trace.trace_id
        deadline_epoch_ns = trace.deadline_epoch_ns
        deadline_monotonic_ns = trace.deadline_monotonic_ns
        return {
            "vt_symbol": "JM2609.DCE",
            "received_at": at,
            "feed_session_id": feed,
            "seq": seq,
            "trace_json": trace.to_json(),
            "trace_id": trace_id,
            "source_feed_session_id": feed,
            "source_ingress_sequence": seq,
            "source_symbol_sequence": seq,
            "ingress_epoch_ns": ingress_epoch_ns,
            "ingress_monotonic_ns": ingress_monotonic_ns,
            "deadline_epoch_ns": deadline_epoch_ns,
            "deadline_monotonic_ns": deadline_monotonic_ns,
            "durable_cursor_feed_session_id": feed,
            "durable_cursor_ingress_sequence": seq,
            "durable_cursor_journal_byte_offset": seq * 100,
            "durable_cursor_journal_schema": "stage179_framed_v1",
            "last_price": price,
            "bid_price_1": price if bid is None else bid,
            "ask_price_1": price if ask is None else ask,
        }

    def latch_initial_stop(self) -> dict:
        return c9.consume_tick(
            self.make_state(),
            self.tick("2026-07-13T21:00:10+08:00", 1, 106.0),
        )

    def arm_retry(self) -> dict:
        return c9.arm_retry_after_close(
            self.latch_initial_stop(),
            close_fill_at="2026-07-13T21:00:11+08:00",
            broker_flat_at="2026-07-13T21:00:12+08:00",
        )

    def test_generation_and_ids_are_stable_and_distinct(self) -> None:
        initial = c9.generation_for_action(attempt_no=0, action="close")
        retry_open = c9.generation_for_action(attempt_no=1, action="open")
        retry_close = c9.generation_for_action(attempt_no=1, action="close")
        self.assertEqual(c9.C9_ACTION_ROOT, initial["root"])
        self.assertEqual(c9.INITIAL_ACTION_CYCLE, initial["cycle"])
        self.assertEqual(c9.RETRY_ACTION_CYCLE, retry_open["cycle"])
        self.assertNotEqual(retry_open["role"], retry_close["role"])

        kwargs = dict(
            target_date="2026-07-13",
            vt_symbol="JM2609.DCE",
            direction="short",
        )
        first = c9.generate_action_id(**kwargs, attempt_no=0, action="close")
        self.assertEqual(
            first,
            c9.generate_action_id(**kwargs, attempt_no=0, action="close"),
        )
        self.assertEqual(
            first,
            c9.generate_action_id(**kwargs, attempt_no=0, action=" CLOSE "),
        )
        self.assertNotEqual(
            first,
            c9.generate_action_id(**kwargs, attempt_no=1, action="close"),
        )

        root = c9.generate_root_position_id(**kwargs)
        self.assertEqual(root, c9.generate_root_position_id(**kwargs))
        self.assertEqual(
            f"{root}:cycle0",
            c9.generate_position_cycle_id(root_position_id=root, cycle_no=0),
        )
        self.assertEqual(
            f"{root}:cycle1",
            c9.generate_position_cycle_id(root_position_id=root, cycle_no=1),
        )

        state = self.make_state()
        self.assertEqual(root, state["root_position_id"])
        self.assertEqual(f"{root}:cycle0", state["position_cycle_id"])
        self.assertEqual(105.0, state["c9_stop_price"])
        self.assertEqual(95.0, state["c9_progress_price"])

        epoch_kwargs = dict(
            target_date="2026-07-13",
            vt_symbol="jm2609.dce",
            direction="sell",
            fill_identity="trade-1",
        )
        self.assertEqual(
            c9.generate_position_epoch_id(
                **epoch_kwargs,
                entry_filled_at="2026-07-13 21:00:01",
            ),
            c9.generate_position_epoch_id(
                **epoch_kwargs,
                entry_filled_at="2026-07-13T21:00:01+08:00",
            ),
        )

    def test_ticks_are_ordered_idempotent_and_pre_fill_is_ignored(self) -> None:
        state = self.make_state()
        ticks = [
            self.tick("2026-07-13T21:00:03+08:00", 3, 99.0),
            self.tick("2026-07-13T21:00:00+08:00", 1, 106.0),
            self.tick("2026-07-13T21:00:02+08:00", 2, 99.0),
        ]
        state = c9.consume_ticks(state, ticks)
        self.assertEqual(c9.PHASE_INITIAL_ARMED, state["phase"])
        self.assertEqual(1, state["counters"]["ignored_before_entry_ticks"])
        self.assertEqual(2, state["counters"]["accepted_ticks"])

        revision = state["revision"]
        replayed = c9.consume_tick(state, ticks[-1])
        self.assertEqual(state, replayed)
        self.assertEqual(revision, replayed["revision"])

    def test_global_feed_sequence_jump_is_not_a_per_symbol_gap(self) -> None:
        state = c9.consume_tick(
            self.make_state(),
            self.tick("2026-07-13T21:00:02+08:00", 1, 100.0),
        )
        state = c9.consume_tick(
            state,
            self.tick("2026-07-13T21:00:03+08:00", 100, 94.0),
        )
        self.assertFalse(state["feed_gap_latched"])
        self.assertEqual(c9.PHASE_INITIAL_PROGRESS_LATCHED, state["phase"])

    def test_same_feed_sequence_wins_over_clock_rollback_for_adverse_tick(self) -> None:
        state = c9.consume_tick(
            self.make_state(),
            self.tick("2026-07-13T21:00:05+08:00", 1, 100.0),
        )
        state = c9.consume_tick(
            state,
            self.tick("2026-07-13T21:00:04+08:00", 2, 106.0),
        )
        self.assertTrue(state["feed_gap_latched"])
        self.assertEqual(
            "tick_received_at_regressed_with_sequence_advance",
            state["feed_gap_reason"],
        )
        self.assertEqual(c9.PHASE_INITIAL_STOP_LATCHED, state["phase"])
        self.assertEqual(2, state["last_seq_by_feed"]["feed-a"])

    def test_sequence_advancing_malformed_time_latches_gap(self) -> None:
        state = c9.consume_tick(
            self.make_state(),
            self.tick("2026-07-13T21:00:05+08:00", 1, 100.0),
        )
        state = c9.consume_tick(state, self.tick("not-a-time", 2, 94.0))
        self.assertTrue(state["feed_gap_latched"])
        self.assertEqual(
            "invalid_tick_received_at_with_sequence_advance",
            state["feed_gap_reason"],
        )
        self.assertEqual(c9.PHASE_INITIAL_ARMED, state["phase"])
        self.assertEqual(1, state["counters"]["tick_time_errors"])

    def test_naive_china_time_and_explicit_plus_eight_share_one_timeline(self) -> None:
        state = c9.new_state(
            target_date="2026-07-13",
            vt_symbol="JM2609.DCE",
            direction="short",
            position_epoch_id="broker-fill-001",
            entry_filled_at="2026-07-13 21:00:01",
            entry_price=100.0,
            original_stop_price=110.0,
            volume=1,
        )
        state = c9.consume_tick(
            state,
            self.tick("2026-07-13T21:00:02+08:00", 1, 106.0),
        )
        self.assertEqual(c9.PHASE_INITIAL_STOP_LATCHED, state["phase"])

    def test_progress_first_permanently_disables_initial_stop_after_restart(self) -> None:
        state = c9.consume_tick(
            self.make_state(),
            self.tick("2026-07-13T21:00:02+08:00", 1, 94.0),
        )
        self.assertEqual(c9.PHASE_INITIAL_PROGRESS_LATCHED, state["phase"])
        restored = c9.loads_state(c9.dumps_state(state))
        self.assertIsNone(c9.get_pending_action(restored))
        self.assertFalse(restored["retry_fresh_tick_required"])
        restored = c9.consume_tick(
            restored,
            self.tick("2026-07-13T21:00:03+08:00", 2, 106.0),
        )
        self.assertEqual(c9.PHASE_INITIAL_PROGRESS_LATCHED, restored["phase"])
        self.assertIsNone(c9.get_pending_action(restored))

    def test_same_tick_dual_cross_is_stop_first(self) -> None:
        state = c9.consume_tick(
            self.make_state(),
            self.tick(
                "2026-07-13T21:00:02+08:00",
                1,
                100.0,
                bid=94.0,
                ask=106.0,
            ),
        )
        self.assertEqual(c9.PHASE_INITIAL_STOP_LATCHED, state["phase"])
        action = c9.get_pending_action(state)
        self.assertEqual("close", action["action"])
        self.assertEqual(c9.INITIAL_STOP_ACTION_ROLE, action["role"])

    def test_wide_spread_quote_cannot_waive_initial_stop_without_trade_progress(self) -> None:
        state = c9.consume_tick(
            self.make_state(),
            self.tick(
                "2026-07-13T21:00:02+08:00",
                1,
                100.0,
                bid=94.0,
                ask=101.0,
            ),
        )

        self.assertEqual(c9.PHASE_INITIAL_ARMED, state["phase"])
        self.assertIsNone(c9.get_pending_action(state))

    def test_retry_reclaim_still_uses_executable_quote(self) -> None:
        state = self.arm_retry()
        state = c9.consume_tick(
            state,
            self.tick(
                "2026-07-13T21:00:13+08:00",
                2,
                101.0,
                bid=94.0,
                ask=101.0,
            ),
        )

        self.assertEqual(c9.PHASE_RETRY_RECLAIM_LATCHED, state["phase"])
        self.assertEqual(94.0, state["retry_reclaim_latched_price"])

    def test_stop_latch_and_action_id_survive_restart_and_later_ticks(self) -> None:
        state = self.latch_initial_stop()
        action_id = c9.get_pending_action(state)["action_id"]
        restored = c9.loads_state(json.dumps(state))
        self.assertEqual(action_id, c9.get_pending_action(restored)["action_id"])

        restored = c9.consume_tick(
            restored,
            self.tick("2026-07-13T21:00:11+08:00", 2, 99.0),
        )
        self.assertEqual(c9.PHASE_INITIAL_STOP_LATCHED, restored["phase"])
        self.assertEqual(action_id, c9.get_pending_action(restored)["action_id"])

    def test_trigger_cursor_trace_and_state_generation_survive_restart_and_later_ticks(
        self,
    ) -> None:
        trigger = self.tick("2026-07-13T21:00:10+08:00", 7, 106.0)
        trigger.update(
            {
                "trace_json": '{"trace_id":"trace-7"}',
                "trace_id": "trace-7",
                "source_feed_session_id": "feed-a",
                "source_ingress_sequence": 17,
                "source_symbol_sequence": 7,
                "ingress_epoch_ns": 1_784_000_000_000_000_000,
                "ingress_monotonic_ns": 900_000_000,
                "deadline_epoch_ns": 1_784_000_025_000_000_000,
                "deadline_monotonic_ns": 25_900_000_000,
                "durable_cursor_feed_session_id": "feed-a",
                "durable_cursor_ingress_sequence": 17,
                "durable_cursor_journal_byte_offset": 4096,
                "durable_cursor_journal_schema": "stage179_framed_v1",
            }
        )
        state = c9.consume_tick(self.make_state(), trigger)
        first = c9.get_pending_action(state)
        expected = {
            "trace_json": '{"trace_id":"trace-7"}',
            "trace_id": "trace-7",
            "source_feed_session_id": "feed-a",
            "source_ingress_sequence": 17,
            "source_symbol_sequence": 7,
            "ingress_epoch_ns": 1_784_000_000_000_000_000,
            "ingress_monotonic_ns": 900_000_000,
            "deadline_epoch_ns": 1_784_000_025_000_000_000,
            "deadline_monotonic_ns": 25_900_000_000,
            "durable_cursor_feed_session_id": "feed-a",
            "durable_cursor_ingress_sequence": 17,
            "durable_cursor_journal_byte_offset": 4096,
            "durable_cursor_journal_schema": "stage179_framed_v1",
        }
        self.assertEqual(expected, {key: first[key] for key in expected})
        self.assertEqual(
            f"{state['position_epoch_id']}:{state['revision']}",
            first["state_generation"],
        )

        restored = c9.loads_state(c9.dumps_state(state))
        restored = c9.consume_tick(
            restored,
            self.tick("2026-07-13T21:00:11+08:00", 8, 99.0),
        )
        later = c9.get_pending_action(restored)

        self.assertGreater(restored["revision"], state["revision"])
        self.assertEqual(first["state_generation"], later["state_generation"])
        self.assertEqual(expected, {key: later[key] for key in expected})

    def test_legacy_pending_action_locks_generation_before_later_tick(self) -> None:
        legacy = self.latch_initial_stop()
        legacy.pop("initial_stop_trigger_provenance", None)
        first_generation = c9.get_pending_action(legacy)["state_generation"]

        loaded = c9.loads_state(c9.dumps_state(legacy))
        self.assertEqual(
            first_generation,
            c9.get_pending_action(loaded)["state_generation"],
        )
        self.assertIsNotNone(loaded["initial_stop_trigger_provenance"])

        volume_refreshed = c9.update_current_position_volume(legacy, volume=2)
        self.assertEqual(
            first_generation,
            c9.get_pending_action(volume_refreshed)["state_generation"],
        )

        gapped = c9.mark_feed_gap(
            legacy,
            detected_at="2026-07-13T21:00:10.500000+08:00",
            reason="legacy_generation_regression",
        )
        self.assertEqual(
            first_generation,
            c9.get_pending_action(gapped)["state_generation"],
        )

        migrated = c9.consume_tick(
            legacy,
            self.tick("2026-07-13T21:00:11+08:00", 2, 99.0),
        )

        self.assertEqual(
            first_generation,
            c9.get_pending_action(migrated)["state_generation"],
        )
        self.assertIsNotNone(migrated["initial_stop_trigger_provenance"])

    def test_legacy_retry_reclaim_without_trace_cursor_cannot_reopen(self) -> None:
        state = self.arm_retry()
        state = c9.consume_tick(
            state,
            self.tick("2026-07-13T21:00:13+08:00", 2, 99.0),
        )
        self.assertEqual(c9.PHASE_RETRY_RECLAIM_LATCHED, state["phase"])
        state.pop("retry_reclaim_trigger_provenance", None)

        restarted = c9.loads_state(c9.dumps_state(state))
        restarted = c9.consume_tick(
            restarted,
            self.tick("2026-07-13T21:00:14+08:00", 3, 99.0),
        )

        self.assertIsNone(c9.get_pending_action(restarted))
        self.assertIn(
            "retry_open_trigger_provenance",
            restarted["trigger_provenance_blocker"],
        )

    def test_retry_open_trigger_provenance_tamper_matrix_fails_closed(self) -> None:
        state = self.arm_retry()
        state = c9.consume_tick(
            state,
            self.tick("2026-07-13T21:00:13+08:00", 2, 99.0),
        )
        self.assertEqual("open", c9.get_pending_action(state)["action"])

        def tamper_trace_symbol(provenance: dict) -> None:
            payload = json.loads(provenance["trace_json"])
            payload["vt_symbol"] = "OTHER.DCE"
            provenance["trace_json"] = json.dumps(payload)

        def tamper_trace_and_outer_symbol_sequence(provenance: dict) -> None:
            payload = json.loads(provenance["trace_json"])
            payload["symbol_sequence"] = 999
            provenance["trace_json"] = json.dumps(payload)
            provenance["source_symbol_sequence"] = 999

        cases = {
            "source_symbol_sequence": lambda item: item.update(
                {"source_symbol_sequence": 999}
            ),
            "cursor_schema": lambda item: item.update(
                {"durable_cursor_journal_schema": "evil"}
            ),
            "ingress_epoch": lambda item: item.update(
                {"ingress_epoch_ns": item["ingress_epoch_ns"] + 1}
            ),
            "trace_vt_symbol": tamper_trace_symbol,
            "trace_and_outer_symbol_sequence": (
                tamper_trace_and_outer_symbol_sequence
            ),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                candidate = json.loads(json.dumps(state))
                mutate(candidate["retry_reclaim_trigger_provenance"])
                candidate = c9.consume_tick(
                    candidate,
                    self.tick("2026-07-13T21:00:14+08:00", 3, 99.0),
                )
                self.assertIsNone(c9.get_pending_action(candidate))
                self.assertTrue(candidate["trigger_provenance_blocker"])

    def test_partial_tick_latches_gap_but_adverse_side_can_still_close(self) -> None:
        state = c9.consume_tick(
            self.make_state(),
            {
                "vt_symbol": "JM2609.DCE",
                "received_at": "2026-07-13T21:00:02+08:00",
                "feed_session_id": "feed-a",
                "seq": 1,
                "ask_price_1": 106.0,
            },
        )
        self.assertTrue(state["feed_gap_latched"])
        self.assertEqual(c9.PHASE_INITIAL_STOP_LATCHED, state["phase"])
        self.assertEqual("close", c9.get_pending_action(state)["action"])

    def test_nonfinite_prices_are_rejected_or_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            c9.new_state(
                target_date="2026-07-13",
                vt_symbol="JM2609.DCE",
                direction="short",
                position_epoch_id="broker-fill-001",
                entry_filled_at="2026-07-13 21:00:01",
                entry_price=100.0,
                original_stop_price=math.nan,
                volume=1,
            )
        state = c9.consume_tick(
            self.make_state(),
            self.tick("2026-07-13T21:00:02+08:00", 1, math.inf),
        )
        self.assertTrue(state["feed_gap_latched"])
        self.assertEqual(c9.PHASE_INITIAL_ARMED, state["phase"])
        self.assertEqual(1, state["counters"]["unusable_tick_envelopes"])

    def test_retry_uses_strict_max_cutoff_and_never_late_opens_unfavorably(self) -> None:
        state = self.arm_retry()
        self.assertEqual(1, state["position_cycle_no"])
        self.assertTrue(state["position_cycle_id"].endswith(":cycle1"))
        state = c9.consume_tick(
            state,
            self.tick("2026-07-13T21:00:11.500000+08:00", 2, 99.0),
        )
        self.assertEqual(c9.PHASE_RETRY_WAIT, state["phase"])
        self.assertEqual(
            1, state["counters"]["ignored_before_retry_cutoff_ticks"]
        )

        state = c9.consume_tick(
            state,
            self.tick("2026-07-13T21:00:13+08:00", 3, 99.0),
        )
        self.assertEqual(c9.PHASE_RETRY_RECLAIM_LATCHED, state["phase"])
        action_id = c9.get_pending_action(state)["action_id"]
        action = c9.get_pending_action(state)
        self.assertEqual(state["root_position_id"], action["root_position_id"])
        self.assertEqual(state["position_cycle_id"], action["position_cycle_id"])
        self.assertEqual(c9.RETRY_OPEN_ACTION_ROLE, action["intent_role"])

        restored = c9.loads_state(c9.dumps_state(state))
        self.assertIsNone(c9.get_pending_action(restored))
        self.assertTrue(restored["retry_fresh_tick_required"])
        restored = c9.consume_tick(
            restored,
            self.tick("2026-07-13T21:00:14+08:00", 4, 101.0),
        )
        self.assertEqual(c9.PHASE_RETRY_RECLAIM_LATCHED, restored["phase"])
        self.assertIsNone(c9.get_pending_action(restored))
        self.assertEqual(action_id, restored["retry_action_id"])

        restored = c9.consume_tick(
            restored,
            self.tick("2026-07-13T21:00:15+08:00", 5, 99.0),
        )
        self.assertEqual(action_id, c9.get_pending_action(restored)["action_id"])

    def test_feed_gap_blocks_progress_but_still_allows_risk_close(self) -> None:
        state = c9.mark_feed_gap(
            self.make_state(),
            detected_at="2026-07-13T21:00:01.500000+08:00",
            reason="seq_gap",
        )
        state = c9.consume_tick(
            state,
            self.tick("2026-07-13T21:00:02+08:00", 1, 94.0),
        )
        self.assertEqual(c9.PHASE_INITIAL_ARMED, state["phase"])
        self.assertEqual(1, state["counters"]["progress_blocked_by_feed_gap"])

        state = c9.consume_tick(
            state,
            self.tick("2026-07-13T21:00:03+08:00", 2, 106.0),
        )
        self.assertEqual(c9.PHASE_INITIAL_STOP_LATCHED, state["phase"])
        self.assertEqual("close", c9.get_pending_action(state)["action"])

    def test_feed_gap_forbids_retry_open_even_when_reclaimed(self) -> None:
        state = c9.mark_feed_gap(
            self.arm_retry(),
            detected_at="2026-07-13T21:00:12.500000+08:00",
            reason="feed_reconnect",
        )
        state = c9.consume_tick(
            state,
            self.tick("2026-07-13T21:00:13+08:00", 2, 99.0),
        )
        self.assertEqual(c9.PHASE_RETRY_WAIT, state["phase"])
        self.assertIsNone(c9.get_pending_action(state))
        self.assertEqual(
            1, state["counters"]["retry_reclaim_blocked_by_feed_gap"]
        )

    def test_retry_stop_is_risk_reducing_and_durable_even_after_gap(self) -> None:
        state = self.arm_retry()
        state = c9.consume_tick(
            state,
            self.tick("2026-07-13T21:00:13+08:00", 2, 99.0),
        )
        state = c9.mark_retry_filled(
            state,
            retry_fill_at="2026-07-13T21:00:14+08:00",
            retry_fill_price=99.0,
        )
        state = c9.mark_feed_gap(
            state,
            detected_at="2026-07-13T21:00:14.500000+08:00",
            reason="feed_gap_after_retry_fill",
        )
        state = c9.consume_tick(
            state,
            self.tick("2026-07-13T21:00:15+08:00", 3, 106.0),
        )
        self.assertEqual(c9.PHASE_RETRY_STOP_LATCHED, state["phase"])
        action = c9.get_pending_action(c9.loads_state(c9.dumps_state(state)))
        self.assertEqual("close", action["action"])
        self.assertEqual(c9.RETRY_STOP_ACTION_ROLE, action["role"])
        self.assertEqual(c9.RETRY_ACTION_CYCLE, action["cycle"])

    def test_partial_retry_fill_immediately_arms_stop_for_filled_volume(self) -> None:
        state = c9.new_state(
            target_date="2026-07-13",
            vt_symbol="JM2609.DCE",
            direction="short",
            position_epoch_id="partial-retry-epoch",
            entry_filled_at="2026-07-13T21:00:01+08:00",
            entry_price=100.0,
            original_stop_price=110.0,
            volume=2,
        )
        state = c9.consume_tick(
            state,
            self.tick("2026-07-13T21:00:10+08:00", 1, 106.0),
        )
        state = c9.arm_retry_after_close(
            state,
            close_fill_at="2026-07-13T21:00:11+08:00",
            broker_flat_at="2026-07-13T21:00:12+08:00",
        )
        state = c9.consume_tick(
            state,
            self.tick("2026-07-13T21:00:13+08:00", 2, 99.0),
        )
        state = c9.mark_retry_filled(
            state,
            retry_fill_at="2026-07-13T21:00:14+08:00",
            retry_fill_price=99.0,
            retry_fill_volume=1,
        )
        self.assertEqual(c9.PHASE_RETRY_OPEN, state["phase"])
        self.assertEqual(1, state["retry_filled_volume"])
        state = c9.consume_tick(
            state,
            self.tick("2026-07-13T21:00:15+08:00", 3, 106.0),
        )
        action = c9.get_pending_action(state)
        self.assertEqual(c9.PHASE_RETRY_STOP_LATCHED, state["phase"])
        self.assertEqual(1, action["volume"])

    def test_action_identity_is_bound_to_position_epoch(self) -> None:
        first = self.latch_initial_stop()
        second = c9.new_state(
            target_date="2026-07-13",
            vt_symbol="JM2609.DCE",
            direction="short",
            position_epoch_id="broker-fill-002",
            entry_filled_at="2026-07-13T21:00:20+08:00",
            entry_price=100.0,
            original_stop_price=110.0,
            volume=1,
        )
        second = c9.consume_tick(
            second,
            self.tick("2026-07-13T21:00:21+08:00", 1, 106.0),
        )
        self.assertNotEqual(
            c9.get_pending_action(first)["action_id"],
            c9.get_pending_action(second)["action_id"],
        )

    def test_public_state_is_json_friendly_and_input_is_not_mutated(self) -> None:
        state = self.make_state(direction="long")
        original = c9.dumps_state(state)
        next_state = c9.consume_tick(
            state,
            self.tick("2026-07-13T21:00:02+08:00", 1, 103.0),
        )
        self.assertEqual(original, c9.dumps_state(state))
        self.assertNotEqual(state["revision"], next_state["revision"])
        self.assertEqual(next_state, json.loads(c9.dumps_state(next_state)))


if __name__ == "__main__":
    unittest.main()
