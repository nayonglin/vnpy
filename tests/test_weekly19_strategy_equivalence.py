"""Source/behavior equivalence for original frozen classes, no financial replay."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tests.test_weekly19_runtime import build, broker, fixture, receipt, runtime, SYMBOL


class EquivalenceTests(unittest.TestCase):
    def test_all_original_class_and_method_asts_are_identical_after_import_relocation(self):
        manifest = runtime.verify_frozen_sources()
        count = 0
        for name, record in manifest['files'].items():
            tree = ast.parse((runtime.HERE/'weekly19_frozen'/name).read_text())
            found = {}
            def walk(nodes, prefix=''):
                for node in nodes:
                    if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                        key = prefix + node.name
                        found[key] = hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
                        walk(node.body, key + '.')
            walk(tree.body)
            for key, digest in record['methods'].items():
                with self.subTest(module=name, method=key):
                    self.assertEqual(found[key], digest)
                count += 1
        self.assertGreaterEqual(count, 565)

    def test_frozen_source_mismatch_is_rejected_before_constructing_any_strategy(self):
        original = runtime._filehash
        def altered(path):
            return 'f'*64 if Path(path).name == 'base827.py' else original(path)
        with patch.object(runtime, '_filehash', altered):
            with self.assertRaisesRegex(runtime.RuntimeContractError, 'frozen_source_hash_mismatch:base827'):
                build()

    def test_literal_weekly_crossover_matches_original_C_case2_and_protection(self):
        obj, bars = build()
        obj.warmup([bars[d] for d in sorted(bars) if d<'2026-10-30'])
        # Same completed-week input delivered directly to the original function;
        # no runtime day/account/funding wrapper participates in the reference.
        ref_am = runtime._decode(runtime._encode(obj.strategy.ams[SYMBOL]))
        ref_am.update_bar(bars['2026-10-30'][SYMBOL])
        original = next(c.__dict__['_generate_signal'] for c in type(obj.strategy).__mro__
                        if c.__name__ == 'NoMacdThreeMaWeeklyIndicatorsStrategy')
        reference = original(obj.strategy, ref_am, obj.strategy._build_history_df(ref_am))
        self.assertEqual(reference['signal'], 'long_case2')
        self.assertTrue(reference['bullish_alignment'])
        decision = obj.process_completed_day('2026-10-30', bars['2026-10-30'], receipt(), broker(), obj.confirmed_cash_state)
        self.assertTrue(decision['funding_admitted_ids'])
        candidates = obj.strategy.entry_candidate_snapshots
        self.assertEqual(candidates[-1]['signal'], reference['signal'])
        state = obj.strategy.states['rb.SHFE']
        self.assertEqual(state.layers[0].stop_price, 100.5)
        self.assertEqual(state.layers[0].highest_price, 101.5)
        self.assertEqual(state.layers[0].lowest_price, 100.5)
        self.assertEqual(obj.strategy.research_macd_call_attempts, 0)
        self.assertEqual(obj.strategy.short_ma_slope_decisions, [])
        self.assertEqual(obj.strategy.long_ma_slope_decisions, [])

    def test_short_bottom20_uses_entire_physical_epoch_and_includes_signal_day(self):
        from weekly19_frozen.stage005_short_bottom20 import RangeHistory
        _, frame, _, _ = fixture()
        table = RangeHistory(frame)
        row = table.snapshot(SYMBOL, '2026-10-30', 101.0)
        self.assertEqual(row['range_low'], 99.5)
        self.assertEqual(row['range_high'], 101.5)
        self.assertEqual(row['history_start'], '2026-05-04')
        self.assertEqual(row['history_end'], '2026-10-30')
        self.assertEqual(row['threshold_price'], 99.9)
        self.assertFalse(row['would_block'])
        flat = frame.iloc[-1:].copy()
        flat[['open','high','low','close']] = 101.0
        self.assertTrue(RangeHistory(flat).snapshot(SYMBOL, '2026-10-30', 101.0)['would_block'])

    def test_intraday_touch_cannot_trigger_weekly_price_protection(self):
        obj, bars = build()
        obj.warmup([bars[d] for d in sorted(bars) if d<'2026-10-30'])
        am = obj.strategy.ams[SYMBOL]
        # Thursday low breaches a hypothetical stop, but this is not fresh week.
        obj.strategy.current_bar_date = bars['2026-10-29'][SYMBOL].datetime
        am.fresh = False
        self.assertFalse(obj.strategy._stop_triggered('long', bars['2026-10-29'][SYMBOL], 200.0))

    def test_future_calendar_recognizes_a_holiday_week_without_future_prices(self):
        from weekly19_frozen.weekly_adapter import completed_weeks
        weeks = completed_weeks(['2026-10-26','2026-10-27','2026-10-28','2026-10-29','2026-11-02'])
        self.assertEqual(weeks[(2026,44)][-1], '2026-10-29')
        terminal = completed_weeks(['2026-10-26','2026-10-27','2026-10-28','2026-10-29'])
        self.assertNotIn((2026,44), terminal)
