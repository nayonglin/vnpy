"""Causal input behaviors for Stage034, without training or economic outcome tests."""
from __future__ import annotations

from datetime import date, timedelta
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

PATH = Path(__file__).with_name('stage034_peer_alignment_dataset.py')
if PATH.exists():
    SPEC = importlib.util.spec_from_file_location('stage034', PATH)
    MOD = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MOD)
else:
    MOD = None


def group(name):
    return int(hashlib.sha256(name.encode()).hexdigest(), 16) % 2


def fixture(days=26):
    calendar = [(date(2025, 1, 1)+timedelta(days=j)).isoformat() for j in range(days)]
    families = ['SHFE.a', 'DCE.b', 'CZCE.c', 'INE.d', 'GFEX.e', 'CFFEX.f']
    rows = []
    for f, family in enumerate(families):
        for j, u in enumerate(calendar):
            rows.append(dict(event_id=family+'|'+u, family_id=family, product_id=family,
                u_date=u, feature_ready=1, label_identified=0 if j == days-1 else 1,
                r1_atr=float(np.sin(j*.8+f*.3)+.2*np.cos(j*.19+f))))
    return pd.DataFrame(rows), calendar


class PeerContextTests(unittest.TestCase):
    def implementation(self):
        self.assertIsNotNone(MOD, 'Stage034 causal peer context is not implemented')
        return MOD

    def test_future_prefix_cannot_change_past_contexts(self):
        # Including u/future shocks in rho or choosing future-valid rows breaks this comparison.
        m = self.implementation(); frame, cal = fixture()
        cutoff = cal[23]; prefix = frame.loc[frame.u_date.le(cutoff)].copy()
        before, ids, _, _ = m.build_contexts(prefix, cal)
        poison = frame.copy(); poison.loc[poison.u_date.gt(cutoff), 'r1_atr'] = 1e9
        poison.loc[poison.u_date.gt(cutoff), 'label_identified'] = 0
        after, all_ids, _, _ = m.build_contexts(poison, cal)
        where = {event: i for i, event in enumerate(all_ids)}
        for scope in m.SCOPES:
            np.testing.assert_array_equal(before[scope], after[scope][[where[event] for event in ids]])

    def test_own_and_F_shock_excluded_but_query_history_is_used(self):
        m = self.implementation(); frame, cal = fixture(); own = 'SHFE.a'; u = cal[23]
        duplicate = frame.loc[frame.family_id.eq(own)].copy()
        duplicate['event_id'] += '|F'; duplicate['product_id'] += '_F'
        frame = pd.concat([frame, duplicate], ignore_index=True)
        base, ids, _, _ = m.build_contexts(frame, cal); at = ids.index(own+'|'+u)
        changed = frame.copy()
        changed.loc[changed.family_id.eq(own) & changed.u_date.eq(cal[22]), 'r1_atr'] = 1e8
        own_shock, _, _, _ = m.build_contexts(changed, cal)
        for scope in m.SCOPES:
            np.testing.assert_array_equal(base[scope][at], own_shock[scope][at])
        changed = frame.copy()
        changed.loc[changed.family_id.eq(own) & changed.u_date.isin(cal[2:22]), 'r1_atr'] *= -1
        own_history, _, _, _ = m.build_contexts(changed, cal)
        self.assertFalse(np.isclose(base['main'][at, 7], own_history['main'][at, 7]))

    def test_held_family_counterfactual_cannot_pollute_train_context_or_market4(self):
        m = self.implementation(); frame, cal = fixture()
        held = 0; target = next(f for f in frame.family_id.unique() if group(f) != held)
        changed = frame.copy(); held_rows = changed.family_id.map(group).eq(held)
        changed.loc[held_rows, 'r1_atr'] = np.arange(int(held_rows.sum()))*.7+100
        before, ids, _, _ = m.build_contexts(frame, cal)
        after, _, _, _ = m.build_contexts(changed, cal)
        indices = [i for i, event in enumerate(ids) if event.startswith(target+'|')]
        np.testing.assert_array_equal(before['holdout_0'][indices], after['holdout_0'][indices])
        self.assertFalse(np.array_equal(before['main'][indices], after['main'][indices]))

    def test_missing_constant_and_new_listing_keep_ready_unknown_rows(self):
        m = self.implementation(); frame, cal = fixture(); frame.loc[frame.family_id.eq('SHFE.a'), 'r1_atr'] = 2.
        frame = frame.loc[~(frame.family_id.eq('DCE.b') & frame.u_date.ne(cal[23]))].copy()
        frame.loc[frame.u_date.eq(cal[23]), 'label_identified'] = 0
        frame.loc[frame.family_id.eq('CZCE.c') & frame.u_date.eq(cal[22]), 'feature_ready'] = 0
        contexts, ids, counts, states = m.build_contexts(frame, cal)
        self.assertEqual(ids, frame.loc[frame.feature_ready.eq(1), 'event_id'].tolist())
        for family in ('SHFE.a', 'DCE.b'):
            at = ids.index(family+'|'+cal[23])
            self.assertEqual(contexts['main'][at, 6], 1.)
            self.assertEqual(contexts['main'][at, 4], 0.)
            self.assertEqual(contexts['main'][at, 7], 0.)
        self.assertGreater(counts['ready_unknown_label'], 0)
        for values in contexts.values(): self.assertTrue(np.isfinite(values).all())
        self.assertEqual(states['main'][ids.index('SHFE.a|'+cal[23])], 'query_constant')
        self.assertEqual(states['main'][ids.index('DCE.b|'+cal[23])], 'query_history_missing')

    def test_null_preserves_peer_values_and_one_peer_has_no_difference(self):
        m = self.implementation()
        names = ['DCE.b', 'SHFE.a']; values = np.array([-3., 2.])
        order = m.hash_permutation(names, '2026-01-01', 'SHFE.x')
        # SHA order was hand-fixed before implementation: SHFE.a precedes DCE.b.
        np.testing.assert_array_equal(order, [1, 0])
        np.testing.assert_array_equal(np.sort(values[order]), [-3., 2.])
        frame, cal = fixture(); frame = frame.loc[frame.family_id.isin(['SHFE.a', 'DCE.b'])]
        ctx, ids, _, _ = m.build_contexts(frame, cal)
        at = ids.index('SHFE.a|'+cal[23])
        self.assertEqual(ctx['main'][at, 4], 1.)
        self.assertEqual(ctx['main'][at, 7], ctx['main'][at, 8])

    def test_main_distribution_and_original_ready_id_storage_contract(self):
        m = self.implementation()
        rows = [dict(event_id=name, family_id=family, product_id=family, u_date=u,
            feature_ready=ready, label_identified=known, r1_atr=value)
            for name, family, u, ready, known, value in [
                ('query', 'SHFE.x', '2026-01-02', 1, 0, 1.),
                ('own', 'SHFE.x', '2026-01-01', 1, 1, 999.),
                ('own_F', 'SHFE.x', '2026-01-01', 1, 1, -999.),
                ('p1', 'DCE.a', '2026-01-01', 1, 0, -2.),
                ('unready', 'DCE.z', '2026-01-01', 0, 0, 888.),
                ('p2', 'CZCE.b', '2026-01-01', 1, 1, 0.),
                ('p3', 'INE.c', '2026-01-01', 1, 1, 4.)]]
        frame = pd.DataFrame(rows); cal = ['2026-01-01', '2026-01-02']
        ctx, ids, _, _ = m.build_contexts(frame, cal)
        np.testing.assert_allclose(ctx['main'][0, :4], [0., 1/3, 3., 0.])
        self.assertEqual(ids, ['query', 'own', 'own_F', 'p1', 'p2', 'p3'])
        with tempfile.TemporaryDirectory() as tmp:
            arrays, identity = m.save_arrays(Path(tmp), ctx, ids)
            with np.load(arrays, allow_pickle=False) as saved:
                self.assertEqual(saved.files, ['main', 'holdout_0', 'holdout_1'])
                for name in saved.files:
                    self.assertEqual(saved[name].dtype.str, '<f8')
                    self.assertEqual(saved[name].shape, (6, 9))
            stored = pd.read_csv(identity)
            self.assertEqual(stored.columns.tolist(), ['sequence_index', 'event_id'])
            self.assertEqual(stored.event_id.tolist(), ids)


if __name__ == '__main__':
    unittest.main(verbosity=2)
