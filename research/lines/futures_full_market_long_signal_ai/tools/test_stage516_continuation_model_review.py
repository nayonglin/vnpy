"""Independent synthetic scientific checks; no historical payload access."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np


P = Path(__file__).with_name('stage516_continuation_model_review.py')
if P.exists():
    S = importlib.util.spec_from_file_location('stage516_independent', P)
    M = importlib.util.module_from_spec(S)
    S.loader.exec_module(M)
else:
    M = None


class IndependentContinuationReviewTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(M, 'independent reviewer has not been implemented')

    def test_features_use_fixed_risk_and_true_calendar_horizon(self):
        # Replacing fixed R0 with current N, or sample-end with target date,
        # must break this mathematical fixture.
        raw = np.array([[110., 98., 105., 110., 108., 10., 2., 4.]])
        got = M.review_features(raw, np.array([100]), np.array([110]), np.array([102]))
        np.testing.assert_allclose(got, [[6., 2.5, 1., 5., 4., 2.]])

    def test_quote_diff_includes_only_sell_fee_and_knownness(self):
        # Double-counted slippage or an imputed unknown payoff must fail.
        q = np.array([[10., 111., 5., 109., 3., 111., 5., 109., 3.]])
        got = M.review_targets(q, np.array([2.]), np.array([[True]*4]))
        np.testing.assert_allclose(got, [[.9, .9]])
        got = M.review_targets(q, np.array([2.]), np.array([[True, False, True, True]]))
        self.assertTrue(np.isnan(got[0, 0]))
        self.assertAlmostEqual(got[0, 1], .9)

    def test_mass_is_equal_dates_then_families_then_paths(self):
        got = M.review_weights(np.array([1, 1, 1, 2]), np.array([0, 0, 1, 0]))
        np.testing.assert_allclose(got, [.125, .125, .25, .5])
        self.assertAlmostEqual(got.sum(), 1.)

    def test_strict_cutoff_and_family_held_exclusion(self):
        a = dict(u_day=np.array([1, 1, 1, 1, 1]),
                 t_day=np.array([3, 3, 10, 3, 3]),
                 k_day=np.array([2, 10, 2, 2, 2]),
                 baseline_day=np.array([4, 4, 4, 4, 4]),
                 voluntary_day=np.array([4, 4, 4, 10, 4]),
                 entry_supported=np.ones(5, bool),
                 y_stress=np.ones(5), family_hash=np.array([0, 0, 0, 0, 1]))
        np.testing.assert_array_equal(M.review_mask(a, 10, 1), [True, False, False, False, False])
        a['y_stress'][0] = np.nan
        self.assertEqual(M.review_mask(a, 10, 1).sum(), 0)

    def test_scaler_uses_observed_conditional_weights_missing_flags_raw(self):
        x = np.array([[1., np.nan, 5., np.nan, 0., 3.],
                      [3., 8., 5., np.nan, 0., 3.]])
        mu, sd = M.review_scaler(x, np.array([.25, .75]))
        np.testing.assert_allclose(mu, [2.5, 8., 5., 0., 0., 3.])
        np.testing.assert_allclose(sd, [np.sqrt(.75), 1., 1., 1., 1., 1.])
        d = M.review_design(x, mu, sd)
        self.assertEqual(d.shape, (2, 13))
        self.assertEqual(d[0, 2], 0.)
        self.assertEqual(d[0, 8], 1.)
        self.assertEqual(d[1, 8], 0.)
        np.testing.assert_array_equal(d[:, 10], [1, 1])

    def test_ridge_penalty_does_not_shrink_intercept(self):
        d = np.array([[1., -1.], [1., 1.]])
        y = np.array([1., 5.])
        b, *_ = M.review_solve(d, y, np.array([.5, .5]))
        np.testing.assert_allclose(b, [3., 1.], atol=1e-12)

    def test_prediction_uses_current_date_and_first_request_is_latched(self):
        from datetime import date
        a = dict(mean=np.zeros(6), scale=np.ones(6), coef=np.r_[1., np.zeros(12)])
        b = dict(mean=np.zeros(6), scale=np.ones(6), coef=np.r_[-1., np.zeros(12)])
        models = {'2020-01-01': a, '2023-01-01': b}
        days = np.array([date(2019, 12, 31).toordinal(),
                         date(2022, 12, 30).toordinal(),
                         date(2023, 1, 3).toordinal()])
        p = M.review_predictions(np.zeros((3, 6)), days, models)
        self.assertTrue(np.isnan(p[0]))
        np.testing.assert_array_equal(p[1:], [1., -1.])
        requests = M.review_first_requests(np.array([4, 4, 4, 5, 5]),
                                          np.array([np.nan, -1., -2., 0., 1.]))
        self.assertEqual(requests, {4: 1})

    def test_terminal_unknown_is_distinct_from_same_observed_path(self):
        import csv
        from datetime import date
        import gzip
        import io
        q = 'observed_research_quote'
        anchors = {str(seq): dict(action_id='a'+str(seq), participation_state='entered',
            terminal_state='closed_complete_bar_model' if seq == 30 else 'open_right_censored',
            available_at='2025-01-10' if seq == 30 else '',
            base_terminal_SELL_quote_state=q if seq == 30 else '',
            stress_terminal_SELL_quote_state=q if seq == 30 else '') for seq in (10, 20, 30)}
        rows = []
        for seq in (10, 20, 30):
            request = seq == 20
            known = seq == 30
            anchor = anchors[str(seq)]
            row = dict(scope='main', action_sequence=seq, action_id=anchor['action_id'],
                family_id='X', product_id='X', u_date='2025-01-01',
                baseline_participation_state=anchor['participation_state'],
                baseline_terminal_state=anchor['terminal_state'], baseline_available_at=anchor['available_at'],
                request_state='first_negative_request' if request else 'hold_original_unit_policy',
                request_t_index=123 if request else '', request_t_date='2025-01-03' if request else '',
                prediction=-1 if request else '', observed_asof_same_path_zero=not request,
                hold_terminal_delta_exact_zero=known)
            for cost in ('base', 'stress'):
                row[cost+'_known_delta_R'] = 0 if known else ''
                row[cost+'_delta_state'] = 'known_terminal_increment' if known else 'terminal_increment_unknown'
            rows.append(row)
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
        raw = gzip.compress(stream.getvalue().encode())
        a = dict(sequence=np.array([20]), t_index=np.array([123]),
                 t_day=np.array([date(2025, 1, 3).toordinal()]))
        report = dict(scope='main', selected_A_entries=3, requested_exits=1, held_all_else=2)
        for cost in ('base', 'stress'):
            report.update({cost+'_known_changed_units': 0, cost+'_unknown_changed_units': 1,
                cost+'_unknown_differential_selected_events': 2,
                cost+'_known_changed_mean_delta_R': None, cost+'_known_u_equal_mean_increment_R': 0.})
        result = M.review_selected_units('main', np.array([-1.]), a, np.full((1, 2), np.nan),
            {}, anchors, {'selected_unit_policy_main': {}}, {'selected_unit_policies': [report]},
            lambda b, role: raw)
        self.assertEqual(result['stress_unknown_differential_selected_events'], 2)
        self.assertEqual(result['stress_known_u_equal_mean_increment_R'], 0.)


if __name__ == '__main__':
    unittest.main()
