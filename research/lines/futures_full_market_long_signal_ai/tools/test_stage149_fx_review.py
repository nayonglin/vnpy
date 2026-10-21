"""Finite independent audit fixtures; no accepted data, fitting, SQL or cash."""
import importlib.util
import io
from pathlib import Path
import unittest
import zipfile

import numpy as np
import pandas as pd


class IndependentFXReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).with_name('stage149_fx_review.py')
        if not path.exists():
            raise AssertionError('independent FX reviewer is not implemented')
        spec = importlib.util.spec_from_file_location('fx149_fixture', path)
        cls.r = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.r)

    def test_raw_zip_ratio_adjacent_clock_and_missing_not_skipped(self):
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, 'w') as archive:
            archive.writestr('eurofxref-hist.csv', 'Date, USD, CNY,\n2020-01-07, 2, 16,\n2020-01-06, 2, 14,\n2020-01-03, 2, N/A,\n2020-01-02, 2, 12,\n')
        rows = self.r.archive_rows(raw.getvalue())
        self.assertEqual(rows[0]['S'], 6.)
        projected = self.r.project(rows, ['2020-01-07', '2020-01-08', '2020-01-09'])
        self.assertEqual(projected.iloc[0].n_date, '2020-01-06')
        self.assertTrue(projected.iloc[:2].q.isna().all())
        self.assertTrue(projected.fx_missing.eq(1).all())
        self.assertEqual(projected.iloc[1].assigned_time, '2020-01-08T08:00:00+08:00')
        self.assertEqual(projected.iloc[1].decision_time, '2020-01-08T15:00:00+08:00')

    def test_weighted_q_stats_and_normal_equations_detect_modified_score(self):
        q = np.array([1., 2., 4.]); w = np.array([1., 2., 1.])
        stats = self.r.q_stats(q, w)
        self.assertAlmostEqual(stats['mean'], 2.25)
        self.assertAlmostEqual(stats['var'], 1.1875)
        common = np.zeros((3, 26)); scaler = {'common':{'mean':[0.]*26, 'scale':[1.]*26}}
        X = self.r.design54(common, q, scaler, stats)
        self.assertEqual(X.shape, (3, 54))
        self.assertTrue((X[:, 52] == 0).all())
        lhs, rhs = self.r.normal_equations(X, np.array([0., 1., 2.]), w)
        self.assertEqual(lhs.shape, (55, 55))
        self.assertEqual(lhs[-1, -1], 4.)
        with self.assertRaises(AssertionError):
            self.r.compare([1.01], [1.], 'changed-score')
        with self.assertRaises(AssertionError):
            self.r.q_stats([2., 2.], [1., 1.])

    def test_selection_keeps_full_eligible_domain_and_fixed_family_priority(self):
        frame = pd.DataFrame([
            dict(product_id='P', family_id='F', u_date='2020-01-01', actual_epoch='P.2', action_id='a', mother_sequence_index=0, u_action_eligible=1, score=1.),
            dict(product_id='P', family_id='F', u_date='2020-01-01', actual_epoch='P.1', action_id='b', mother_sequence_index=0, u_action_eligible=1, score=1.),
            dict(product_id='P_F', family_id='F', u_date='2020-01-01', actual_epoch='Q.1', action_id='c', mother_sequence_index=1, u_action_eligible=1, score=100.),
            dict(product_id='Z', family_id='Z', u_date='2020-01-01', actual_epoch='Z.1', action_id='d', mother_sequence_index=2, u_action_eligible=0, score=1000.),
        ])
        chosen, proposals = self.r.choose(frame)
        self.assertEqual(chosen, {('F', '2020-01-01'):'b'})
        self.assertEqual(set(proposals), {0, 1})

    def test_shared_unknown_cancels_but_distinct_unknown_stays_unknown(self):
        labels = {'x':dict(label_state='missing', participation_state='unknown'),
                  'y':dict(label_state='closed_complete_bar_model', participation_state='observed', label_known_date='2020-01-02', net_R_stress=3.)}
        self.assertEqual(self.r.increment('x', 'x', labels, '2020-01-03'), (0., False, True))
        self.assertEqual(self.r.increment('x', 'y', labels, '2020-01-03'), (None, True, False))
        self.assertEqual(self.r.increment('', 'y', labels, '2020-01-03'), (3., False, False))

    def test_held_reuses_aliased_control_and_keeps_common_unknown(self):
        base=dict(scope='holdout_0',u_date='2020-01-02',u_index=10)
        control=pd.DataFrame([dict(base,arm='CONTROL_REUSED',family_id='X',chosen_action_id='x',selected=1),
                              dict(base,arm='CONTROL_REUSED',family_id='Y',chosen_action_id='',selected=0)])
        fx=pd.DataFrame([dict(base,arm='FX',family_id='X',chosen_action_id='x',selected=1),
                         dict(base,arm='FX',family_id='Y',chosen_action_id='y',selected=1)])
        actions=pd.DataFrame([dict(action_id='x',label_state='missing',participation_state='unknown',label_known_date='',net_R_stress=np.nan),
                              dict(action_id='y',label_state='closed_complete_bar_model',participation_state='observed',label_known_date='2020-01-03',net_R_stress=3.)])
        groups,daily,family=self.r.held_result(fx,control,actions,'2020-01-04')
        self.assertEqual(groups['holdout_0']['full_family_u'],2)
        self.assertEqual(groups['holdout_0']['common_unresolved_same_action'],1)
        self.assertAlmostEqual(groups['holdout_0']['known_u_equal_mean_increment_R'],1.5)
        self.assertEqual(len(family),2)
        self.assertEqual(len(daily),1)

    def test_paired_ci_reuses_exact_indices_and_gate_requires_strict_primary_dd(self):
        indices = np.array([[0, 1], [1, 0]], dtype=int)
        point, values = self.r.paired([.2, .4], [.1, .1], indices)
        np.testing.assert_allclose(values, [.2, .2])
        self.assertAlmostEqual(point['ci95_low'], .2)
        points = {(w,c):dict(active_total_return_pct=2., return_percentage_point_difference=1., drawdown_percentage_point_difference=0., ci95_low=.1, identification='observed_cash_comparison') for w in self.r.WINDOWS for c in self.r.COSTS}
        held = {'groups':{s:dict(nominal_pass=True, unknown_differential_selected_events=0, status='supported') for s in ('holdout_0','holdout_1')}}
        self.assertFalse(self.r.fixed_gate(points, held, False, True, False)['cash_nominal_pass'])
        points[('primary_2020','stress')]['drawdown_percentage_point_difference'] = .1
        self.assertTrue(self.r.fixed_gate(points, held, False, True, False)['nominal_pass'])
        self.assertFalse(self.r.fixed_gate(points, held, False, True, True)['nominal_pass'])


if __name__ == '__main__':
    unittest.main()
