"""Behavior tests for Stage023 frozen historical representation, not model outcomes."""
from __future__ import annotations

from datetime import date, timedelta
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

PATH = Path(__file__).with_name('stage023_ordered_history_dataset.py')
if PATH.exists():
    SPEC = importlib.util.spec_from_file_location('stage023', PATH)
    MOD = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(MOD)
else:
    MOD = None


def bars():
    values = []
    for j in range(22):
        close = 100. + j
        values.append(dict(contract_epoch_id='SHFE.x.202601', exchange='SHFE', product='x',
            contract_yyyymm=202601, trade_date=(date(2025, 1, 1)+timedelta(days=j)).isoformat(),
            open=close-.5, high=close+1, low=close-1, close=close,
            volume=10.+j, quality_status='accepted'))
    return values


class SequenceTests(unittest.TestCase):
    def implementation(self):
        self.assertIsNotNone(MOD, 'Stage023 historical representation is not implemented')
        return MOD

    def test_formula_uses_previous_twenty_volume_and_flat_location(self):
        # Mutating the denominator to current twenty volumes changes the literal expected ratio.
        m = self.implementation(); w = bars()[:21]
        w[-1].update(open=120., high=120., low=120., close=120.)
        out, atr, summary = m.window_representation(w, [r['trade_date'] for r in w])
        # First 19 TRs are 2, final TR is 1; ATR=39/20. V0..19 mean=19.5.
        self.assertAlmostEqual(atr, 1.95)
        np.testing.assert_allclose(out[0], [1/1.95, 2/1.95, .5, math.log(11/19.5)])
        np.testing.assert_allclose(out[-1], [1/1.95, 0., .5, math.log(30/19.5)])
        self.assertEqual(out.dtype, np.dtype('float64'))
        self.assertEqual(len(summary), 11)

    def test_window_rejects_cross_epoch_short_and_source_calendar_gap(self):
        # Accepting any of these creates observations absent from the frozen ready cohort.
        m = self.implementation(); w = bars()[:21]; cal = [r['trade_date'] for r in bars()]
        for kind in ('short', 'cross_epoch', 'calendar_gap'):
            bad = [dict(r) for r in w]
            if kind == 'short': bad = bad[1:]
            elif kind == 'cross_epoch': bad[0]['contract_epoch_id'] = 'SHFE.x.202512'
            else: bad[10]['trade_date'] = '2024-12-31'
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                m.window_representation(bad, cal)

    def test_build_only_reads_u_window_and_preserves_unknown_ready(self):
        # Reading D or filtering on label_identified changes the same causal row or deletes unknowns.
        m = self.implementation(); source = bars(); cal = [r['trade_date'] for r in source]
        _, atr, summary = m.window_representation(source[:21], cal)
        rows = []
        for name, ready, known in [('unknown', 1, 0), ('known', 1, 1), ('unready', 0, 0)]:
            row = dict(event_id=name, reference_epoch='SHFE.x.202601', product_id='SHFE.x',
                u_date=source[20]['trade_date'], feature_ready=ready, label_identified=known,
                atr20=atr, **dict(zip(m.OWN_FEATURES, summary)))
            rows.append(row)
        parent = pd.DataFrame(rows)
        first, ids, counts = m.build_sequences(parent, cal, iter(source), scope_end=cal[-1])
        poison = [dict(r) for r in source]; poison[-1].update(open=None, high=None, low=None, close=None, volume=None)
        second, ids2, counts2 = m.build_sequences(parent, cal, iter(poison), scope_end=cal[-1])
        np.testing.assert_array_equal(first, second)
        self.assertEqual(ids, ['unknown', 'known']); self.assertEqual(ids2, ids)
        self.assertEqual(first.shape, (2, 20, 4))
        self.assertEqual(counts['ready_unknown_label'], 1)
        self.assertEqual(counts['parent_rows'], 3)

    def test_parent_summary_conflict_fails_instead_of_silently_changing_input(self):
        m = self.implementation(); source = bars(); cal = [r['trade_date'] for r in source]
        _, atr, summary = m.window_representation(source[:21], cal)
        row = dict(event_id='conflict', reference_epoch='SHFE.x.202601', product_id='SHFE.x',
            u_date=cal[20], feature_ready=1, label_identified=0, atr20=atr,
            **dict(zip(m.OWN_FEATURES, summary)))
        row['r1_atr'] += .01
        with self.assertRaises(ValueError):
            m.build_sequences(pd.DataFrame([row]), cal, iter(source), scope_end=cal[-1])

    def test_storage_is_quantized_little_endian_ordered_only(self):
        # Saving unquantized f64 or unrelated inputs violates the actual consumer contract.
        m = self.implementation()
        x = np.arange(160, dtype=np.float64).reshape(2, 20, 4)/7
        with tempfile.TemporaryDirectory() as temp:
            sequence, identities = m.save_arrays(Path(temp), x, ['b', 'a'])
            with np.load(sequence, allow_pickle=False) as data:
                self.assertEqual(data.files, ['ordered'])
                self.assertEqual(data['ordered'].dtype.str, '<f4')
                np.testing.assert_array_equal(data['ordered'], x.astype('<f4'))
            records = pd.read_csv(identities)
            self.assertEqual(records.columns.tolist(), ['sequence_index', 'event_id'])
            self.assertEqual(records.event_id.tolist(), ['b', 'a'])

    def test_canonical_bag_moves_complete_tuples_after_storage_quantization(self):
        # Independently sorting channels fabricates bars; adding index ties retains forbidden age.
        m = self.implementation()
        row = np.array([[2, 10, .1, 3], [-1, 20, .9, 4], [2, 8, .7, 9]], dtype='<f4')
        bag = m.canonical_bag(row[None, :, :])[0]
        np.testing.assert_array_equal(bag, np.array([[-1, 20, .9, 4], [2, 8, .7, 9], [2, 10, .1, 3]], dtype='<f4'))
        np.testing.assert_array_equal(m.canonical_bag(row[::-1][None, :, :])[0], bag)


if __name__ == '__main__':
    unittest.main(verbosity=2)
