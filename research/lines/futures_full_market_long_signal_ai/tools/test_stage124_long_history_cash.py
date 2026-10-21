"""Fixed long-history wrapper boundaries; synthetic frames and zero actual replay."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

PATH = Path(__file__).with_name('stage124_long_history_cash.py')


def module():
    if not PATH.exists():
        return None
    spec = importlib.util.spec_from_file_location('test124_target', PATH)
    target = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(target)
    return target


class LongHistoryCash(unittest.TestCase):
    def setUp(self):
        self.m = module()
        self.assertIsNotNone(self.m, 'Stage124 implementation is missing')

    def points(self):
        return [dict(window=w, cost=c,
            return_percentage_point_difference=1. if (w, c) == ('primary_2020', 'stress') else 0.,
            drawdown_percentage_point_difference=0., ci95_low=.001, active_total_return_pct=1.,
            reference_total_return_pct=1., identification='observed_cash_comparison')
            for w in ('primary_2020', 'cold_2023') for c in ('base', 'stress')]

    def held(self):
        return {'groups': {g: dict(nominal_pass=True, status='supported', unknown_differential_selected_events=0)
                          for g in ('holdout_0', 'holdout_1')}}

    def test_missing_history_and_future_unknown_do_not_remove_main_action(self):
        labels = pd.DataFrame([dict(event_id='e', product_id='P.X', family_id='P.X', u_date='2020-01-02', u_index=1,
            reference_epoch='P.X2001', label_history_ready20=1, N_u=1., low20_u=90., u_close=100., history_run=20,
            lifecycle_index=99, label_state='open_right_censored')])
        pred = labels[['event_id', 'product_id', 'family_id', 'u_date', 'u_index', 'reference_epoch']].copy()
        pred = pred.assign(scope='main', policy='NARROW', arm='LONG_HISTORY', cutoff='2020-01-01', score=1.,
                           history_ready20=1, selected=1, external_missing=1)
        result = self.m.make_signals(labels, pred, 'LONG_HISTORY')
        self.assertEqual(result.potential.tolist(), [1])
        self.assertEqual(result.external_missing.tolist(), [1])
        pred['scope'] = 'holdout_0'
        with self.assertRaisesRegex(ValueError, 'main'):
            self.m.make_signals(labels, pred, 'LONG_HISTORY')

    def test_missing_is_shared_and_both_complete_arms_required(self):
        pred = pd.DataFrame(dict(event_id=['a', 'b', 'a', 'b'], arm=['CONTROL', 'CONTROL', 'LONG_HISTORY', 'LONG_HISTORY'],
                                 external_missing=[1, 0, 1, 0]))
        self.m.validate_shared_missing(pred)
        for bad in (pred.iloc[:-1], pd.concat([pred, pred.iloc[:1]]), pred.assign(arm='NFC')):
            with self.assertRaises(ValueError):
                self.m.validate_shared_missing(bad)
        pred.loc[3, 'external_missing'] = 1
        with self.assertRaisesRegex(ValueError, 'shared'):
            self.m.validate_shared_missing(pred)

    def test_primary_stress_strict_other_three_nonnegative(self):
        pts = self.points()
        self.assertEqual(self.m.continuation_gate(pts, self.held(), False, wealth_positive=True)['status'],
                         'supported_research_model_only')
        pts[1]['return_percentage_point_difference'] = 0.
        self.assertEqual(self.m.continuation_gate(pts, self.held(), False, wealth_positive=True)['status'], 'unsupported')

    def test_primary_stress_ci_must_be_strict_positive_finite(self):
        for value in (0., -.001, None, float('nan')):
            pts = self.points()
            pts[1]['ci95_low'] = value
            gate = self.m.continuation_gate(pts, self.held(), False, wealth_positive=True)
            self.assertEqual(gate['status'], 'unsupported')
            self.assertFalse(gate['cash_nominal_pass'])

    def test_relative_edge_cannot_hide_long_history_loss_or_insolvency(self):
        pts = self.points()
        pts[0]['active_total_return_pct'] = 0.
        gate = self.m.continuation_gate(pts, self.held(), False, wealth_positive=True)
        self.assertFalse(gate['LONG_HISTORY_own_returns_positive_in_all_four'])
        self.assertFalse(gate['cash_nominal_pass'])
        self.assertEqual(self.m.continuation_gate(self.points(), self.held(), False, wealth_positive=False)['status'], 'unsupported')

    def test_unknown_cannot_replace_nominal_failure_or_invent_unfilled_cash_exposure(self):
        pts, held = self.points(), self.held()
        self.assertEqual(self.m.continuation_gate(pts, held, False, wealth_positive=True, signal_unknown_main=True)['status'],
                         'supported_research_model_only')
        held['groups']['holdout_0']['unknown_differential_selected_events'] = 1
        self.assertEqual(self.m.continuation_gate(pts, held, False, wealth_positive=True)['status'],
                         'unknown_differential_held_outcome')
        pts[-1]['drawdown_percentage_point_difference'] = -1.
        self.assertEqual(self.m.continuation_gate(pts, held, True, wealth_positive=True)['status'], 'unsupported')

    def test_empty_reference_drawdown_and_absent_held_do_not_pass(self):
        pts = self.points()
        for p in pts:
            p['drawdown_percentage_point_difference'] = None
        self.assertEqual(self.m.continuation_gate(pts, self.held(), False, wealth_positive=True)['status'],
                         'unknown_empty_reference_DD')
        with self.assertRaisesRegex(ValueError, 'held'):
            self.m.continuation_gate(self.points(), {}, False, wealth_positive=True)
        self.assertEqual(self.m.ref.NATIVE_QUERIES, 0)

    def test_bootstrap_rejects_wrong_calendar_or_noninteger_indices(self):
        for indices in (np.zeros((2, 2), dtype=int), np.zeros((2, 3), dtype=float), np.full((2, 3), 3)):
            with self.assertRaisesRegex(ValueError, 'bootstrap'):
                self.m.paired_statistics(pd.DataFrame(index=range(3)), pd.DataFrame(index=range(3)), indices)


if __name__ == '__main__':
    unittest.main()
