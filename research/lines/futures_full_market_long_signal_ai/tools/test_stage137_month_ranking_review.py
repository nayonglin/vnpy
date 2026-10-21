"""Finite increment-only fixtures; no actual score, native source, fit or book."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))


class MonthRankingReviewBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = TOOLS / 'stage137_month_ranking_review.py'
        assert path.exists(), '137 independent increment reviewer is missing'
        spec = importlib.util.spec_from_file_location('review137', path)
        cls.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.m)

    def rows(self):
        return pd.DataFrame([
            dict(action_id='a', actual_epoch='X.P.202001', product_id='X.P', u_date='2020-01-02', u_volume=800., u_action_eligible=1, score=1.),
            dict(action_id='b', actual_epoch='X.P.202002', product_id='X.P', u_date='2020-01-02', u_volume=500., u_action_eligible=1, score=2.),
            dict(action_id='c', actual_epoch='X.P.202003', product_id='X.P', u_date='2020-01-02', u_volume=9999., u_action_eligible=1, score=-1.),
        ])

    def test_pool_and_keys_are_positive_and_scope_independent(self):
        rows = self.rows()
        self.assertEqual(self.m.select_control(rows, 'MAX_VOLUME_POS')[0], 'a')
        for seed in range(20):
            control = f'RANDOM_POS_{seed:02d}'
            a = self.m.select_control(rows.assign(scope='main', cost='base'), control)
            b = self.m.select_control(rows.assign(scope='holdout_0', cost='stress'), control)
            self.assertEqual(a, b)
            self.assertIn(a[0], {'a', 'b'})
        expected = {'version':'stage134_positive_month_rank_v1', 'seed':0, 'product_id':'X.P', 'u_date':'2020-01-02', 'actual_epoch':'X.P.202001'}
        import hashlib
        key = hashlib.sha256(json.dumps(expected, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(self.m.random_key(0, rows.iloc[0]), key)

    def test_exact_coefficients_cancel_singleton_common_unknown(self):
        labels = {'a':dict(participation_state='unresolved', label_state='unresolved')}
        r = self.m.linear_contrast({'a':1}, {'a':1}, labels, '2026-10-16')
        self.assertEqual(r['value'], 0.)
        self.assertFalse(r['unknown'])
        self.assertEqual(r['common_unknown_actions'], 1)
        self.assertEqual(r['positive_unknown_mass'], 0.)
        r = self.m.linear_contrast({'a':1}, {'a':self.m.Fraction(1,3), 'b':self.m.Fraction(2,3)},
                                  dict(labels, b=dict(participation_state='known_nonparticipation')), '2026-10-16')
        self.assertIsNone(r['value'])
        self.assertAlmostEqual(r['positive_unknown_mass'], 2/3)

    def test_equal_u_aggregation_does_not_weight_busy_dates(self):
        rows = pd.DataFrame(dict(u_date=['d1','d1','d2'], value=[2.,4.,8.], unknown=[False]*3))
        s = self.m.equal_u_summary(rows)
        self.assertEqual(s['mean'], 5.5)
        self.assertEqual(s['source_u_count'], 2)
        rows.loc[0, 'unknown'] = True
        rows.loc[0, 'value'] = np.nan
        self.assertIsNone(self.m.equal_u_summary(rows)['mean'])

    def test_materialization_preserves_unselected_parent_state_and_order(self):
        parents = pd.DataFrame([
            dict(event_id='p0', selected=0, selection_state='all_negative', chosen_action_id='', anchor_epoch='near', reference_epoch='near', proposed_action_id='old0'),
            dict(event_id='p1', selected=1, selection_state='selected', chosen_action_id='a', anchor_epoch='near', reference_epoch='near', proposed_action_id='a')])
        overrides = pd.DataFrame([dict(event_id='p1', chosen_action_id='b', chosen_epoch='far', chosen_action_sequence_index=7, score=2.)])
        materialized = self.m.materialize_parents(parents, overrides)
        self.assertEqual(materialized.event_id.tolist(), ['p0','p1'])
        pd.testing.assert_series_equal(materialized.iloc[0].reindex(parents.columns), parents.iloc[0], check_names=False)
        self.assertTrue(materialized.iloc[0].reindex(['chosen_epoch', 'chosen_action_sequence_index', 'score']).isna().all())
        self.assertEqual(materialized.iloc[1].chosen_action_id, 'b')
        self.assertEqual(materialized.iloc[1].proposed_action_id, 'b')
        self.assertEqual(materialized.iloc[1].anchor_epoch, 'near')
        self.assertEqual(materialized.iloc[1].reference_epoch, 'near')
        with self.assertRaises(AssertionError):
            self.m.materialize_parents(parents, pd.concat([overrides, overrides]))

    def test_fixed_random_mean_keeps_unavailable_seed_unidentified(self):
        ai = np.array([.1,.2]); seeds = [np.zeros(2) for _ in range(20)]
        indices = np.array([[0,1],[1,0]], dtype=int)
        point, distribution = self.m.paired_comparison(ai, seeds, indices, financial_unknown=True)
        self.assertAlmostEqual(point['mean_daily_log_difference'], .15)
        self.assertTrue(point['financial_unknown'])
        seeds[19] = None
        point, distribution = self.m.paired_comparison(ai, seeds, indices, financial_unknown=False)
        self.assertEqual(point['status'], 'survival_failure_no_log_repair')
        self.assertIsNone(point['ci95_low'])
        self.assertTrue(np.isnan(distribution).all())

    def test_cash_context_restores_globals_after_failure(self):
        review = types.SimpleNamespace(ACTIVE_POSITIONS='old', CASH_HELPER='prior', review_capped_budgets=lambda:None)
        helper = types.SimpleNamespace(review_budgets='original')
        with self.assertRaises(RuntimeError):
            with self.m.cash_context(review, helper, 'positions'):
                self.assertIs(review.CASH_HELPER, helper)
                self.assertEqual(review.ACTIVE_POSITIONS, 'positions')
                self.assertIs(helper.review_budgets, review.review_capped_budgets)
                raise RuntimeError('fixture')
        self.assertEqual(review.ACTIVE_POSITIONS, 'old')
        self.assertEqual(review.CASH_HELPER, 'prior')
        self.assertEqual(helper.review_budgets, 'original')

    def test_numeric_bool_and_empty_null_meanings_do_not_depend_on_csv_dtype(self):
        import stage102_cash_diagnostics as diag
        self.m.assert_fields(dict(qty='2', known='True', value=''), dict(qty=2, known=True, value=None), diag, 'fixture')
        with self.assertRaises(AssertionError):
            self.m.assert_fields(dict(qty='3'), dict(qty=2), diag, 'fixture')

    def test_real136_bridge_reads_native_arrays_and_rejects_invalid_row(self):
        import stage132_contract_choice_review as review
        spec = importlib.util.spec_from_file_location('fixture_bridge136', TOOLS/'stage136_month_ranking_cash.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        store = review.NativeBars(['2020-01-01','2020-01-02'])
        store.series['e'] = dict(days=np.array([0,1]), values=np.array([[10.,11.,9.,10.,400.],[0.,11.,9.,10.,0.]]),
            accepted=np.array([True,False]), valid=np.array([True,False]), N=np.array([2.,np.nan]),
            low20=np.array([8.,np.nan]), run=np.array([20,0]))
        result = self.m.bridge_check(module, store, review)
        self.assertEqual(result['cached_native_rows_checked'], 2)
        adapter = module.CachedMarket(store)
        self.assertIsNone(adapter.bar('e', 1))
        self.assertEqual(adapter.indicator('e', 1)['run_length'], 0)
        store.series['e']['values'][0,3] = 10.5
        self.assertEqual(adapter.bar('e', 0)['close'], 10.5)


if __name__ == '__main__':
    unittest.main()
