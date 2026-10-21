"""Finite new semantic boundaries only; no actual market data or fitting."""
import importlib.util
from pathlib import Path
import unittest

P = Path(__file__).with_name('stage125_long_history_review.py')


class LongHistoryBoundaries(unittest.TestCase):
    def setUp(self):
        self.assertTrue(P.exists(), 'independent 125 implementation absent')
        spec = importlib.util.spec_from_file_location('review125', P)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)

    def test_calendar_year_boundary_is_open_and_leap_safe(self):
        self.assertEqual(self.m.lower_boundary('2020-02-29'), '2019-02-28')
        self.assertEqual(self.m.lower_boundary('2021-03-01'), '2020-03-01')
        dates = ['2019-02-28', '2019-03-01', '2020-02-28', '2020-02-29']
        self.assertEqual(self.m.required_window(dates, 3), [1, 2, 3])

    def test_each_day_uses_previous_representative_same_epoch_both_prices(self):
        days = ['2020-01-02', '2020-01-06', '2020-01-07']
        reps = ['old', 'new', 'new']
        bars = {('old', days[0]): (10, 11, 9, 10, 1, 'accepted'),
                ('old', days[1]): (11, 12, 10, 11, 1, 'accepted'),
                ('new', days[0]): (50, 51, 49, 50, 1, 'accepted'),
                ('new', days[1]): (100, 101, 99, 100, 1, 'accepted'),
                ('new', days[2]): (110, 111, 109, 110, 1, 'accepted')}
        econ = {k: dict(economics_status='exact_epoch_metadata_snapshot', contract_multiplier=10, round_lot=1) for k in reps}
        result = self.m.independent_factors(days, reps, bars, econ)
        self.assertIsNone(result[0]['factor'])
        self.assertAlmostEqual(result[1]['factor'], 1.1)
        self.assertEqual(result[1]['epoch'], 'old')
        self.assertEqual(result[2]['epoch'], 'new')
        self.assertAlmostEqual(result[2]['factor'], 1.1)
        self.assertEqual(result[1]['previous_date'], '2020-01-02')

    def test_missing_pair_economics_or_invalid_full_bar_is_not_rescued(self):
        days = ['2020-01-02', '2020-01-06']
        good = (10, 11, 9, 10, 1, 'accepted')
        econ = {'a': dict(economics_status='exact_epoch_metadata_snapshot', contract_multiplier=10, round_lot=1)}
        for bars, economics in [({('a', days[0]): good}, econ),
                                ({('a', d): good for d in days}, {}),
                                ({('a', days[0]): good, ('a', days[1]): (10, 11, 9, 10, 0, 'accepted')}, econ),
                                ({('a', days[0]): good, ('a', days[1]): (10, 9, 11, 10, 1, 'accepted')}, econ)]:
            self.assertIsNone(self.m.independent_factors(days, ['a', 'a'], bars, economics)[1]['factor'])

    def test_window_is_compounded_complete_and_observed_zero_not_missing(self):
        days = ['2019-01-01', '2019-01-02', '2020-01-01']
        q = self.m.independent_scalars(days, [None, 2., .5])
        self.assertIsNone(q[0]['scalar'])
        self.assertEqual(q[2]['scalar'], 0.)
        self.assertEqual(q[2]['observed'], 1)
        self.assertEqual(q[2]['required_factors'], 2)
        self.assertIsNone(self.m.independent_scalars(days, [None, None, .5])[2]['scalar'])

    def test_typed_summary_metadata_and_fixed_gate(self):
        self.m.np = __import__('numpy')
        import stage102_cash_diagnostics as d
        self.m._fields = d._fields
        row = dict(valuation='research_cash', eligible=False, missing=None, pnl=1.25)
        self.m.check_account_summary_table(row, dict(row, nested={}))
        with self.assertRaises(AssertionError):
            self.m.check_account_summary_table(row, dict(row, valuation='broker_cash'))
        points = {(w, c): dict(return_percentage_point_difference=1. if (w, c) == ('primary_2020', 'stress') else 0., drawdown_percentage_point_difference=0., ci95_low=.001, active_total_return_pct=1., identification='observed_cash_comparison') for w in ('primary_2020', 'cold_2023') for c in ('base', 'stress')}
        held = {'groups': {g: dict(nominal_pass=True, status='supported', unknown_differential_selected_events=0) for g in ('holdout_0', 'holdout_1')}}
        self.assertEqual(self.m.cash_gate(points, held, False, False, True)['status'], 'supported_research_model_only')
        points[('primary_2020', 'stress')]['return_percentage_point_difference'] = 0.
        self.assertEqual(self.m.cash_gate(points, held, False, False, True)['status'], 'unsupported')


if __name__ == '__main__':
    unittest.main()
