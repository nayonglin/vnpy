from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
sys.path.insert(0, str(MODULE_DIR))

import qmt_roll_official_live_c9_intraday_state as c9  # noqa: E402


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
        return {
            "vt_symbol": "JM2609.DCE",
            "received_at": at,
            "feed_session_id": feed,
            "seq": seq,
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
