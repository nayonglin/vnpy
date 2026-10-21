"""Finite Stage052 contract tests; the sole real estimator fit is synthetic."""
from pathlib import Path
import importlib.util
import json
import os
import tempfile
import unittest

import numpy as np
import pandas as pd

SOURCE = Path(__file__).with_name('stage053_maturity_information_fit.py')


def load_subject():
    if not SOURCE.exists():
        return None
    spec = importlib.util.spec_from_file_location('stage053_subject', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = load_subject()


def row(event, family='X.A', u='2019-12-20', known='2019-12-24', entry=1, exit=3, **kw):
    d = dict(event_id=event, product_id=family, family_id=family, u_date=u,
             u_index=0, reference_epoch=family + '.fixture', entry_index=entry, exit_index=exit,
             entry_date='2019-12-23', exit_date=known, label_known_date=known,
             label_state='closed_complete_bar_model', net_R_stress=1.,
             label_history_ready20=1, q_aligned=2., q_shuffled=4.)
    for col in (m.COMMON if m else ['r1_atr']):
        d[col] = 1.
    d.update(kw)
    return d


class FixedSyntheticEstimator:
    """Only replace expensive estimation; maturity/design/action/output stay real."""
    def fit(self, x, y, sample_weight):
        if x.shape[1] != 53 or not np.isfinite(x).all():
            raise AssertionError('bad design passed to estimator')
        self._baseline_prediction = np.array([[np.average(y, weights=sample_weight)]])
        self._predictors = []
        self.n_features_in_ = x.shape[1]
        self.n_iter_ = 0
        return self

    def predict(self, x):
        return np.full(len(x), self._baseline_prediction.item())


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(m, 'Stage053 implementation is missing')

    def test_strict_maturity_and_held_family_excludes_F_as_one_family(self):
        f = pd.DataFrame([
            row('ok'), row('equal', known='2020-01-01'),
            row('future', u='2020-01-01'), row('unknown', label_state='held_unknown', net_R_stress=np.nan),
            row('F', product_id='X.A_F'), row('other', family='X.B')])
        self.assertEqual(m.training_slice(f, '2020-01-01').event_id.tolist(), ['F', 'ok', 'other'])
        held = m.family_group('X.A')
        train = m.training_slice(f, '2020-01-01', held)
        self.assertFalse(train.family_id.eq('X.A').any())
        self.assertNotIn('equal', train.event_id.tolist())

    def test_uniqueness_is_family_inclusive_and_then_date_equal(self):
        # A [1,3] and A_F [2,2]: c=(1,2,1), U=(5/6,1/2).
        # B [2,2] is another family: U=1. Same-u final weights 15/16,9/16;
        # other-u gets 3/2, so mean=1 and each date sum=3/2.
        f = pd.DataFrame([row('a'), row('af', product_id='X.A_F', entry=2, exit=2),
                          row('b', family='X.B', u='2019-12-21', entry=2, exit=2)])
        got = m.training_weights(f)
        np.testing.assert_allclose(got['uniqueness'], [5/6, 1/2, 1.], atol=1e-15)
        np.testing.assert_allclose(got['sample_weight'], [15/16, 9/16, 3/2], atol=1e-15)

    def test_training_scaler_finite_weighted_pool_and_future_poison(self):
        x = np.ones((2, 26)); x[:, 0] = [1., 3.]; x[:, 1] = [np.nan, 5.]
        w = np.array([1., 3.])
        s = m.fit_scalers(x, [0., 2.], [4., np.nan], w)
        self.assertAlmostEqual(s['common']['mean'][0], 2.5)
        self.assertAlmostEqual(s['common']['var'][0], .75)
        self.assertEqual(s['common']['mean'][1], 5.)
        self.assertAlmostEqual(s['q']['mean'], 2.)  # weights .5,1.5,.5 => mean2
        self.assertAlmostEqual(s['q']['var'], 1.6)
        f = pd.DataFrame([row('train'), row('future', u='2025-01-01', known='2025-01-02', r1_atr=1e100, q_aligned=-1e100)])
        before = m.cell_preprocessing(m.training_slice(f, '2020-01-01'))
        f.loc[1, 'r1_atr'] = -1e200
        after = m.cell_preprocessing(m.training_slice(f, '2020-01-01'))
        self.assertEqual(before[1], after[1])

    def test_missing_does_not_drop_rows_all_arms_have_53_slots(self):
        f = pd.DataFrame([row('missing', r1_atr=np.nan, q_aligned=np.nan, q_shuffled=np.nan),
                          row('finite', r1_atr=3., q_aligned=2., q_shuffled=4.)])
        _, scaler = m.cell_preprocessing(f)
        designs = [m.design_matrix(f, arm, scaler) for arm in m.ARMS]
        for design in designs:
            self.assertEqual(design.shape, (2, 53))
            self.assertTrue(np.isfinite(design).all())
            self.assertEqual(design[0, 26], 1.)
        for design in designs[1:]:
            np.testing.assert_array_equal(design[:, :52], designs[0][:, :52])
        self.assertEqual(designs[1][0, 52], 0.)
        self.assertTrue(np.all(designs[0][:, 52] == -3.))

    def test_action_uses_only_ready_and_score_no_future_labels(self):
        f = pd.DataFrame([row('unknown', label_state='held_unknown', net_R_stress=np.nan),
                          row('cancel', label_state='known_nonparticipation'),
                          row('notready', label_history_ready20=0), row('zero'), row('nan')])
        got = m.prediction_frame(f, [1., 2., 10., 0., np.nan], 'main', 'ALIGNED', '2020-01-01')
        self.assertEqual(got.selected.tolist(), [1, 1, 0, 0, 0])
        self.assertEqual(len(got), 5)
        self.assertNotIn('label_state', got)

    def test_forward_blocks_no_2019_and_matrix_keeps_unknown_missing(self):
        rows = []
        # Both fixed family groups must have pre2020 mature evidence.
        families = ['X.A', 'X.B', 'X.C', 'X.D']
        for j, family in enumerate(families):
            rows.append(row(f'train{j}', family=family))
            for year in (2020, 2023, 2026):
                rows.append(row(f'{family}{year}', family=family, u=f'{year}-01-02',
                                known=f'{year}-01-03', u_index=year,
                                label_state='held_unknown', net_R_stress=np.nan, r1_atr=np.nan))
        f = pd.DataFrame(rows)
        with tempfile.TemporaryDirectory() as td:
            result = m.run_matrix(f, Path(td), estimator_factory=FixedSyntheticEstimator,
                                  execution_kind='synthetic_fixture')
            self.assertEqual(result['fit_calls_started'], 27)
            self.assertEqual(result['fit_calls_completed'], 27)
            self.assertEqual(result['actual_fit_calls_completed'], 0)
            for scope in ('main', 'holdout_combined'):
                p = pd.read_csv(result['predictions'][scope]['path'])
                self.assertEqual(len(p), 36)
                self.assertFalse(p.duplicated(['event_id', 'arm']).any())
                self.assertTrue(p.u_date.ge('2020-01-01').all())
                self.assertTrue(p.cutoff.le(p.u_date).all())
                self.assertEqual(int(p.selected.sum()), 36)
                self.assertEqual(set(p.scope), {'main'} if scope == 'main' else {'holdout_0', 'holdout_1'})

    @unittest.skipUnless(os.environ.get('STAGE053_RUN_ONE_REAL_FIXTURE') == '1',
                         'one real fixture already characterized at preflight; default never refits')
    def test_one_small_real_fit_portable_leaf_values_include_learning_rate(self):
        # This catches an accidental second shrinkage or lost baseline in export.
        x = np.zeros((240, 53)); x[:, 0] = np.arange(240)
        y = np.r_[np.zeros(120), np.full(120, 4.)]
        model = m.make_estimator()
        model.fit(x, y, sample_weight=np.ones(240))
        exported = m.portable_model(model)
        scores = np.full(len(x), exported['baseline'])
        for tree in exported['trees']:
            for i, sample in enumerate(x):
                k = 0
                while not tree[k]['is_leaf']:
                    node = tree[k]
                    k = node['left'] if sample[node['feature_idx']] <= node['num_threshold'] else node['right']
                scores[i] += tree[k]['value']
        np.testing.assert_allclose(scores, model.predict(x), rtol=0, atol=1e-12)
        self.assertGreater(np.ptp(scores), 3.)


if __name__ == '__main__':
    unittest.main()
