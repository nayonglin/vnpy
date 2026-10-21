"""New tiny fixtures only: no real input reads and no estimator.fit calls."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

MODULE = Path(__file__).with_name('stage456_con4_fit_select.py')
_MOD = None


def subject():
    global _MOD
    if _MOD is None:
        assert MODULE.is_file(), 'Stage456 implementation is not present yet'
        spec = importlib.util.spec_from_file_location('fixture456', MODULE)
        _MOD = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_MOD)
    return _MOD


class Con4Fixture(unittest.TestCase):
    def test_single_scalar_preserves_all_52_columns_and_missing_is_neutral(self):
        s = subject()
        raw = np.arange(78, dtype=float).reshape(3, 26)
        raw[0, 2] = np.nan
        scaler = {'common': {'mean': [2.] * 26, 'scale': [3.] * 26}}
        q = np.array([-.5, .5, np.nan])
        stat = s.q_statistics(q, np.array([1., 3., 7.]))
        x = s.design53(raw, q, scaler, stat)
        expected = s.original().design(raw, scaler)
        self.assertEqual(x.shape, (3, 53))
        np.testing.assert_array_equal(x[:, :52], expected)
        self.assertEqual(stat['mean'], .25)
        self.assertAlmostEqual(stat['var'], .1875)
        self.assertEqual(x[2, 52], 0.)
        self.assertTrue(np.isfinite(x).all())
        self.assertFalse(s.q_statistics(np.array([np.nan, np.nan]), np.ones(2))['ready'])

    def test_source_acceptance_blocks_every_unaccepted_or_partial_source(self):
        s = subject()
        cells = [{'scope': a, 'cutoff': b, 'passed': True}
                 for a in s.SCOPES for b in s.CUTOFFS]
        src = {'status': 'completed', 'protocol_sha256': s.PROTOCOL_SHA,
               'all_support_passed': True, 'sixfold_source_support': cells}
        review = {'status': 'completed', 'core_blockers': 0, 'all_support_passed': True}
        auth = {'source_support_accepted_by_root': True}
        s.require_source_support(src, review, auth)
        for changed in [dict(src, all_support_passed=False),
                        dict(src, sixfold_source_support=cells[:-1])]:
            with self.assertRaises(ValueError):
                s.require_source_support(changed, review, auth)
        with self.assertRaises(ValueError):
            s.require_source_support(src, review, {})

    def test_source_parent_projection_rejects_bad_identity_and_keeps_unknown(self):
        s = subject()
        q = np.array([.1, np.nan, -.2])
        result = s.project_q(q, np.array([2, 0, 1]))
        np.testing.assert_array_equal(result, np.array([-.2, .1, np.nan]))
        for bad in [np.array([-1]), np.array([3]), np.array([.5])]:
            with self.assertRaises(ValueError):
                s.project_q(q, bad)

    def test_ridge_equations_penalize_53_columns_but_not_intercept(self):
        s = subject()
        x = np.zeros((2, 53)); x[:, 52] = [1., 2.]
        lhs, rhs = s.ridge_system(x, np.array([2., 4.]), np.array([1., 3.]))
        self.assertEqual(lhs.shape, (54, 54))
        self.assertEqual(lhs[0, 0], 1.)
        self.assertEqual(lhs[52, 52], 14.)
        self.assertEqual(lhs[53, 53], 4.)
        self.assertEqual(lhs[52, 53], 7.)
        self.assertEqual(rhs[52], 26.)
        self.assertEqual(rhs[53], 14.)

    def test_held_scope_uses_full_K_selection_without_mutating_scores(self):
        s = subject()
        calendar = ['2020-01-02', '2020-01-03', '2020-01-06']
        mother = dict(sequence_index=0, event_id='m0', product_id='DCE.C',
                      family_id='DCE.C', u_date='2020-01-02', u_index=0,
                      reference_epoch='DCE.C.202003')
        row = dict(sequence_index=0, action_id='a0', mother_sequence_index=0,
                   mother_event_id='m0', product_id='DCE.C', family_id='DCE.C',
                   u_date='2020-01-02', u_index=0, reference_epoch='DCE.C.202003',
                   anchor_epoch='DCE.C.202003', u_action_eligible=1, score=1.,
                   scope='holdout_0', cutoff='2020-01-01')
        result = s.select_scope([mother], iter([row]), 'holdout_0', calendar)
        self.assertEqual(result['choices'][0]['chosen_action_id'], 'a0')
        self.assertEqual(result['choices'][0]['scope'], 'holdout_0')
        self.assertEqual(row['scope'], 'holdout_0')
        with self.assertRaises(ValueError):
            s.select_scope([mother], iter([dict(row, scope='main')]), 'holdout_0', calendar)

    def test_training_parse_keeps_original_ieee_values_and_holdout_exclusion(self):
        s = subject()
        family = next('DCE.' + str(i) for i in range(20)
                      if s.original().family_group('DCE.' + str(i)) == 1)
        exact = '0.10000000000000002'
        row = dict(sequence_index='2', action_id='a2', product_id=family, family_id=family,
                   u_date='2019-01-02', u_index='1', reference_epoch=family+'.201905',
                   u_action_eligible='1', label_known_date='2019-01-03',
                   label_state='closed_complete_bar_model', net_R_stress=exact,
                   sample_weight=exact, mother_sequence_index='1', mother_event_id='m1')
        train = s.validate_training(pd.DataFrame([row]), 'holdout_0', '2020-01-01', 1)
        self.assertEqual(train.net_R_stress.to_numpy().view('uint64')[0],
                         np.array([float(exact)]).view('uint64')[0])
        self.assertEqual(train.sample_weight.to_numpy().view('uint64')[0],
                         np.array([float(exact)]).view('uint64')[0])
        with self.assertRaises(ValueError):
            s.validate_training(pd.DataFrame([row]), 'holdout_1', '2020-01-01', 1)


if __name__ == '__main__':
    unittest.main()
