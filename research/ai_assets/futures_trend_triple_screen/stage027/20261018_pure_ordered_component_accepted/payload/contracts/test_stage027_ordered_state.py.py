"""Contract tests for the pure Stage027 indicator and setup machine."""
import json
import unittest

from stage027_ordered_state import OrderedSetupMachine, force_index_rows


def bar(day, close, volume=100, contract="rb2605.SHFE"):
    return dict(date=day, vt_symbol=contract, close=close, volume=volume)


def close(machine, day="2026-01-06", next_day="2026-01-07", **changes):
    args = dict(product="rb.SHFE", contract="rb2605.SHFE", day=day,
                next_day=next_day, high=101.0, low=99.0, tick=1.0,
                weekly_ready=True, weekly_direction=1, weekly_asof="2026-01-02",
                fi_ready=True, fi2=-1.0, eligible=True, position_open=False,
                native_signal=None)
    args.update(changes)
    return machine.on_close(**args)


class OrderedStateContractTests(unittest.TestCase):
    def test_01_force_seed_recursion_and_prefix_invariance(self):
        calendar = ["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]
        rows = [bar(calendar[0], 10, 100), bar(calendar[1], 11, 200),
                bar(calendar[2], 9, 300), bar(calendar[3], 12, 400)]
        result = force_index_rows(reversed(rows), calendar)
        self.assertEqual([r["raw_force"] for r in result], [None, 200.0, -600.0, 1200.0])
        self.assertEqual([r["ready"] for r in result], [False, False, True, True])
        self.assertEqual([r["fi2"] for r in result[:3]], [None, None, -200.0])
        self.assertAlmostEqual(result[3]["fi2"], 2200.0 / 3.0)
        self.assertEqual(result[0]["previous_date"], None)
        self.assertEqual(result[1]["previous_date"], calendar[0])
        self.assertEqual(set(result[0]), {"date", "vt_symbol", "raw_force", "fi2", "ready", "reason", "previous_date"})
        extended = rows + [bar(calendar[4], 5000, 1000000)]
        self.assertEqual(force_index_rows(extended, calendar)[:4], result)
        extended[-1] = bar(calendar[4], 1, 1)
        self.assertEqual(force_index_rows(extended, calendar)[:4], result)
        self.assertEqual(force_index_rows(rows[:3], calendar[:3]), result[:3])
        json.dumps(result, allow_nan=False)

    def test_02_real_calendar_gap_zero_invalid_and_contract_warmup(self):
        calendar = ["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07",
                    "2026-01-08", "2026-01-09", "2026-01-12", "2026-01-13",
                    "2026-01-14", "2026-01-15", "2026-01-16"]
        indices = [0, 1, 2, 4, 5, 6, 7, 8, 9, 10]
        rows = [bar(calendar[i], 100 + i, 0 if i == 7 else 100) for i in indices]
        rows += [bar(calendar[i], 200 - i, 30, "rb2610.SHFE") for i in range(3)]
        result = force_index_rows(rows, calendar)
        first = [r for r in result if r["vt_symbol"] == "rb2605.SHFE"]
        second = [r for r in result if r["vt_symbol"] == "rb2610.SHFE"]
        self.assertEqual([r["ready"] for r in first], [False, False, True, False, False, True, False, False, False, True])
        self.assertEqual(first[3]["reason"], "calendar_gap")
        self.assertEqual(first[3]["raw_force"], None)
        self.assertEqual(first[3]["previous_date"], "2026-01-06")
        self.assertEqual(first[6]["reason"], "invalid_volume")
        self.assertEqual(second[2]["fi2"], -30.0)
        for invalid in [float("nan"), float("inf"), 0, -1]:
            with self.subTest(invalid_close=invalid):
                bad = force_index_rows([bar(calendar[0], invalid), bar(calendar[1], 100)], calendar)
                self.assertEqual(bad[0]["reason"], "invalid_close")
                self.assertIsNone(bad[1]["raw_force"])
                json.dumps(bad, allow_nan=False)

    def test_03_c_requires_earlier_setup_and_b_can_emit_same_close(self):
        c = OrderedSetupMachine("C_TS")
        same_day = close(c, native_signal="long_case1a")
        self.assertIsNone(same_day["intent"])
        self.assertEqual(same_day["setup_day"], "2026-01-06")
        no_signal = close(c, "2026-01-07", "2026-01-08", fi2=-4)
        self.assertIsNone(no_signal["intent"])
        later = close(c, "2026-01-08", "2026-01-09", fi2=4, native_signal="long_case1a")
        self.assertEqual(later["decision"], "intent")
        self.assertEqual(later["setup_id"], same_day["setup_id"])
        self.assertEqual(later["intent"]["setup_day"], "2026-01-06")
        self.assertEqual(later["intent"]["signal_day"], "2026-01-08")
        self.assertEqual(later["intent"]["execution_day"], "2026-01-09")
        self.assertEqual(later["intent"]["native_signal"], "long_case1a")
        b = close(OrderedSetupMachine("B_TS"))
        self.assertEqual(b["intent"]["setup_day"], b["intent"]["signal_day"])
        self.assertEqual(b["intent"]["native_signal"], "long_triple_screen")
        self.assertEqual(set(b), {"decision", "setup_id", "setup_day", "intent", "baseline_fallback", "cancel_reason"})
        self.assertEqual(set(b["intent"]), {"arm", "intent_id", "product", "contract", "epoch_id", "setup_id", "setup_day", "signal_day", "execution_day", "direction", "trigger", "weekly_asof", "native_signal"})
        forbidden = {"volume", "capital", "pnl", "quantity", "profit", "loss"}
        self.assertFalse(forbidden.intersection(b["intent"]))
        json.dumps(later, allow_nan=False)

    def test_04_week_ai_position_and_epoch_cancel_old_setup(self):
        cases = [({"eligible": False}, "ineligible"),
                 ({"position_open": True}, "position_open"),
                 ({"weekly_direction": 0}, "weekly_neutral"),
                 ({"weekly_direction": -1, "fi2": -1, "native_signal": "short_case1a"}, "weekly_direction_changed"),
                 ({"contract": "rb2610.SHFE", "fi2": 1}, "epoch_changed")]
        for changes, reason in cases:
            with self.subTest(reason=reason):
                c = OrderedSetupMachine("C_TS")
                prepared = close(c)
                changed = close(c, "2026-01-07", "2026-01-08", **changes)
                self.assertIsNone(changed["setup_id"])
                self.assertIsNone(changed["intent"])
                self.assertEqual(changed["cancel_reason"], reason)
                self.assertFalse(changed["baseline_fallback"])
                self.assertIsNotNone(prepared["setup_id"])
        c = OrderedSetupMachine("C_TS")
        close(c)
        new_epoch = close(c, "2026-01-07", "2026-01-08", contract="rb2610.SHFE", native_signal="long_case1a")
        self.assertEqual(new_epoch["setup_day"], "2026-01-07")
        self.assertIsNone(new_epoch["intent"])
        next_signal = close(c, "2026-01-08", "2026-01-09", contract="rb2610.SHFE", fi2=1, native_signal="long_case1a")
        self.assertEqual(next_signal["intent"]["setup_id"], new_epoch["setup_id"])
        for arm in ["B_TS", "C_TS"]:
            with self.subTest(missing_target_arm=arm):
                machine = OrderedSetupMachine(arm)
                close(machine)
                missing = machine.cancel("rb.SHFE", "2026-01-07", "target_real_bar_missing")
                self.assertFalse(missing["baseline_fallback"])
                self.assertEqual(missing["cancel_reason"], "target_real_bar_missing")
                self.assertIsNone(missing["setup_id"])
                with self.assertRaises(ValueError):
                    close(machine, "2026-01-07", "2026-01-08")
                after = close(machine, "2026-01-08", "2026-01-09", fi2=1, native_signal="long_case1a")
                self.assertIsNone(after["setup_id"])
                self.assertIsNone(after["intent"])
        fresh = OrderedSetupMachine("C_TS")
        self.assertIsNone(fresh.cancel("rb.SHFE", "2026-01-06", "target_mapping_missing")["intent"])
        with self.assertRaises(ValueError):
            close(fresh)

    def test_05_unknown_wait_or_fallback_never_forces_intent(self):
        for unknown in [{"weekly_ready": False, "weekly_asof": None, "weekly_direction": None},
                        {"fi_ready": False, "fi2": None}]:
            for arm in ["B_TS", "C_TS"]:
                with self.subTest(arm=arm, unknown=unknown):
                    machine = OrderedSetupMachine(arm)
                    previous = close(machine)
                    result = close(machine, "2026-01-07", "2026-01-08", native_signal="long_case1a", **unknown)
                    self.assertIsNone(result["intent"])
                    self.assertIsNone(result["setup_id"])
                    self.assertEqual(result["baseline_fallback"], arm == "C_TS")
                    self.assertEqual(result["decision"], "baseline_fallback" if arm == "C_TS" else "waiting")
                    if previous["intent"]:
                        with self.assertRaises(ValueError):
                            machine.on_fill(previous["intent"]["intent_id"], "2026-01-07")
        neutral = close(OrderedSetupMachine("C_TS"), weekly_direction=0, native_signal="long_case1a")
        self.assertFalse(neutral["baseline_fallback"])
        self.assertIsNone(neutral["intent"])
        # Known hard restrictions take precedence even when an indicator is unknown.
        for unknown in [{"weekly_ready": False, "weekly_asof": None, "weekly_direction": None},
                        {"fi_ready": False, "fi2": None}]:
            for hard_state, reason in [({"eligible": False}, "ineligible"),
                                       ({"position_open": True}, "position_open")]:
                for arm in ["B_TS", "C_TS"]:
                    with self.subTest(unknown=unknown, hard_state=hard_state, arm=arm):
                        result = close(OrderedSetupMachine(arm), **unknown, **hard_state)
                        self.assertEqual(result["decision"], "blocked")
                        self.assertFalse(result["baseline_fallback"])
                        self.assertIsNone(result["intent"])
                        self.assertIsNone(result["setup_id"])
                        self.assertEqual(result["cancel_reason"], reason)

    def test_06_one_day_intent_expiry_and_no_old_c_signal_reuse(self):
        b = OrderedSetupMachine("B_TS")
        first = close(b)
        second = close(b, "2026-01-07", "2026-01-08", fi2=1)
        self.assertEqual(first["setup_id"], second["setup_id"])
        self.assertNotEqual(first["intent"]["intent_id"], second["intent"]["intent_id"])
        with self.assertRaises(ValueError):
            b.on_fill(first["intent"]["intent_id"], "2026-01-07")
        c = OrderedSetupMachine("C_TS")
        close(c)
        signal = close(c, "2026-01-07", "2026-01-08", fi2=1, native_signal="long_case1a")
        following = close(c, "2026-01-08", "2026-01-09", fi2=1)
        self.assertIsNone(following["intent"])
        self.assertEqual(following["setup_id"], signal["setup_id"])
        self.assertEqual(following["cancel_reason"], "intent_expired")
        with self.assertRaises(ValueError):
            c.on_fill(signal["intent"]["intent_id"], "2026-01-08")
        terminal = close(c, "2026-01-09", None, fi2=1, native_signal="long_case1a")
        self.assertIsNone(terminal["intent"])

    def test_07_only_matching_unique_execution_fill_consumes_setup(self):
        b = OrderedSetupMachine("B_TS")
        initial = close(b)
        identity = initial["intent"]["intent_id"]
        with self.assertRaises(ValueError):
            b.on_fill("wrong", "2026-01-07")
        for day in ["2026-01-06", "2026-01-08"]:
            with self.subTest(wrong_day=day), self.assertRaises(ValueError):
                b.on_fill(identity, day)
        filled = b.on_fill(identity, "2026-01-07")
        self.assertTrue(filled["consumed"])
        self.assertEqual(filled["setup_id"], initial["setup_id"])
        with self.assertRaises(ValueError):
            b.on_fill(identity, "2026-01-07")
        next_close = close(b, "2026-01-07", "2026-01-08", fi2=1)
        self.assertIsNone(next_close["setup_id"])
        self.assertIsNone(next_close["intent"])
        # Another product cannot expire this product's valid frozen intent.
        other = OrderedSetupMachine("B_TS")
        rb = close(other)
        close(other, product="cu.SHFE", contract="cu2605.SHFE")
        self.assertTrue(other.on_fill(rb["intent"]["intent_id"], "2026-01-07")["consumed"])

    def test_08_tick_mirrors_determinism_and_invalid_inputs(self):
        long_result = close(OrderedSetupMachine("B_TS"), high=100.01, low=99, tick=0.2)
        short_result = close(OrderedSetupMachine("B_TS"), high=101, low=100.09, tick=0.2, weekly_direction=-1, fi2=1)
        self.assertEqual(long_result["intent"]["trigger"], 100.4)
        self.assertEqual(short_result["intent"]["trigger"], 99.8)
        self.assertEqual(short_result["intent"]["native_signal"], "short_triple_screen")
        floating = close(OrderedSetupMachine("B_TS"), high=1.1, low=1, tick=0.1)
        self.assertEqual(floating["intent"]["trigger"], 1.2)
        for low in [1, 2]:
            with self.subTest(nonpositive_short_trigger_low=low):
                invalid_trigger = close(OrderedSetupMachine("B_TS"), high=3, low=low,
                                        tick=2, weekly_direction=-1, fi2=1)
                self.assertEqual(invalid_trigger["decision"], "blocked")
                self.assertIsNone(invalid_trigger["intent"])
                self.assertFalse(invalid_trigger["baseline_fallback"])
                self.assertEqual(invalid_trigger["cancel_reason"], "invalid_trigger")
        self.assertEqual(long_result, close(OrderedSetupMachine("B_TS"), high=100.01, low=99, tick=0.2))
        for bad in ["A0", "", None]:
            with self.subTest(arm=bad), self.assertRaises(ValueError):
                OrderedSetupMachine(bad)
        invalid = [{"tick": 0}, {"tick": float("nan")}, {"high": 98, "low": 99},
                   {"low": float("inf")}, {"weekly_direction": 2},
                   {"weekly_asof": "2026-01-05"}, {"fi2": float("nan")},
                   {"next_day": "2026-01-06"}, {"native_signal": {"signal": "long_case1a"}}]
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                close(OrderedSetupMachine("B_TS"), **changes)
        b = OrderedSetupMachine("B_TS")
        initial = close(b)
        with self.assertRaises(ValueError):
            close(b)
        self.assertTrue(b.on_fill(initial["intent"]["intent_id"], "2026-01-07")["consumed"])
        for rows, calendar in [([bar("2026-01-06", 10)] * 2, ["2026-01-06"]),
                               ([bar("2026-01-06", 10)], ["2026-01-05"]),
                               ([], ["2026-01-06", "2026-01-06"])]:
            with self.subTest(rows=rows, calendar=calendar), self.assertRaises(ValueError):
                force_index_rows(rows, calendar)


if __name__ == "__main__":
    unittest.main()
