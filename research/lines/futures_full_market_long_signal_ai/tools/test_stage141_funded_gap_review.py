"""Seven finite independent boundaries. No accepted data, author import or replay."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stage141_funded_gap_review as review


def episode():
    return dict(root_id='r', event_id='a', mother_event_id='p', family_id='f',
                product_id='f', epoch='e', initial_qty=5, qty=3, risk_per_lot=20.,
                realized_gross=80., entry_fees=10., exit_fees=4., unrealized=90.,
                ever_stale='False', stale='False', entry_date='2023-01-02',
                last_mark=103., entry_fill=100., multiplier=10.)


def fills():
    return [dict(root_id='r', event_id='a', epoch='e', date='2023-01-02', side='BUY',
                 qty=5, risk_per_lot=20., fee=10., realized_gross=0., slippage=7.,
                 fill_price=100., reference_price=99.9, reason='new_entry'),
            dict(root_id='r', event_id='a', epoch='e', date='2023-01-03', side='SELL',
                 qty=2, risk_per_lot=20., fee=4., realized_gross=80., slippage=3.,
                 fill_price=104., reference_price=104.1, reason='reduce')]


class FundedGapReviewTests(unittest.TestCase):
    def test_open_partial_reduction_is_fill_net_plus_terminal_mark(self):
        got = review.root_accounting(episode(), fills(), closed=False)
        self.assertEqual(got['C'], 156.)
        self.assertEqual(got['F'], 100.)
        self.assertEqual(got['Y'], 1.56)
        self.assertEqual(got['gross_realized'], 80.)
        self.assertEqual(got['negative_fee'], -14.)
        self.assertEqual(got['unrealized'], 90.)

    def test_corrupt_root_buy_and_double_charged_fee_are_rejected(self):
        for field, value in [('initial_qty', 6), ('risk_per_lot', 0), ('risk_per_lot', 1e308),
                             ('entry_fees', 17), ('realized_gross', 81)]:
            row = episode(); row[field] = value
            with self.subTest(field=field), self.assertRaises(AssertionError):
                review.root_accounting(row, fills(), closed=False)
        bad = fills(); bad.append(copy.deepcopy(bad[0]))
        with self.assertRaises(AssertionError):
            review.root_accounting(episode(), bad, closed=False)
        for sell, remain in [(-1, 6), (2.5, 2.5)]:
            row = episode(); row['qty'] = remain
            bad = fills(); bad[-1]['qty'] = sell
            with self.assertRaises(AssertionError):
                review.root_accounting(row, bad, closed=False)

    def test_both_entered_uses_risk_and_symmetric_exact_bridge(self):
        got = review.pair_math(60., 20., 20., 10., True, True, False)
        self.assertEqual(got['category'], 'both_entered_different_action')
        self.assertEqual(got['risk_component'], 25.)
        self.assertEqual(got['unit_component'], 15.)
        self.assertEqual(got['participation_component'], 0.)
        self.assertEqual(got['delta_CNY'], 40.)
        same = review.pair_math(60., 20., 20., 10., True, True, True)
        self.assertEqual(same['category'], 'both_entered_same_action')
        self.assertEqual(same['unit_component'], 15.)

    def test_no_entry_has_null_units_and_signed_participation(self):
        only_a = review.pair_math(-7., 0., 2., None, True, False, True)
        self.assertEqual(only_a['participation_component'], -7.)
        self.assertIsNone(only_a['Y_control'])
        only_b = review.pair_math(0., 8., None, 2., False, True, False)
        self.assertEqual(only_b['participation_component'], -8.)
        neither = review.pair_math(0., 0., None, None, False, False, True)
        self.assertEqual(neither['category'], 'neither_entered')
        self.assertIsNone(neither['Y_AI'])
        with self.assertRaises(AssertionError):
            review.pair_math(1., 0., None, None, False, False, True)

    def test_full_grid_rejects_ex_post_intersection_and_keeps_prestart(self):
        keys = [('a', 'p0'), ('a', 'p1'), ('b', 'p0'), ('b', 'p1')]
        review.complete_grid(keys, ['a', 'b'], ['p0', 'p1'])
        with self.assertRaises(AssertionError):
            review.complete_grid(keys[:-1], ['a', 'b'], ['p0', 'p1'])
        with self.assertRaises(AssertionError):
            review.complete_grid(keys + [keys[0]], ['a', 'b'], ['p0', 'p1'])
        self.assertTrue(review.opportunity(9, 10, 15))
        self.assertTrue(review.opportunity(14, 10, 15))
        self.assertFalse(review.opportunity(8, 10, 15))
        self.assertFalse(review.opportunity(15, 10, 15))
        self.assertEqual(review.calendar_dates([20221230, 20230103]), ['2022-12-30', '2023-01-03'])

    def test_normalized_path_is_diagnostic_and_false_string_is_false(self):
        import pandas as pd
        row, fs = episode(), fills()
        other, other_fs = copy.deepcopy(row), copy.deepcopy(fs)
        for name in ('initial_qty', 'qty', 'realized_gross', 'entry_fees', 'exit_fees', 'unrealized'):
            other[name] *= 2
        for f in other_fs:
            for name in ('qty', 'fee', 'realized_gross', 'slippage'):
                f[name] *= 2
        self.assertEqual(review.normalized_path(row, fs, False), review.normalized_path(other, other_fs, False))
        other_fs[-1]['reason'] = 'different_exit'
        self.assertNotEqual(review.normalized_path(row, fs, False), review.normalized_path(other, other_fs, False))
        precision_fills = fills()
        precision_fills[-1]['reference_price'] = '15821.592949406415'
        raw_csv = pd.DataFrame(precision_fills).to_csv(index=False).encode()
        projected = review.signature_projection(raw_csv, compression=None).to_dict('records')
        self.assertEqual(projected[-1]['reference_price'], 15821.592949406417)
        self.assertNotEqual(review.digest(review.normalized_path(row, precision_fills, False)),
                            review.digest(review.normalized_path(row, projected, False)))
        self.assertFalse(review.flag('False'))
        self.assertTrue(review.flag('1'))
        with self.assertRaises(AssertionError):
            review.flag('unknown')

    def test_random_mean_is_20_pair_cny_not_median_or_mean_units(self):
        rows = [dict(control_id=f'RANDOM_POS_{i:02d}', delta_CNY=float(i),
                     risk_component=float(i)/2, unit_component=float(i)/4,
                     participation_component=float(i)/4) for i in range(20)]
        rows[-1].update(delta_CNY=119., risk_component=59.5, unit_component=29.75,
                        participation_component=29.75)
        got = review.mean20(rows)
        self.assertEqual(got['delta_CNY'], 14.5)
        self.assertEqual(got['risk_component'] + got['unit_component'] + got['participation_component'], 14.5)
        with self.assertRaises(AssertionError):
            review.mean20(rows[:-1])

    def test_signed_aggregation_keeps_cancellation_before_random_mean(self):
        import pandas as pd
        rows = []
        for control in ['RANDOM_POS_00', 'RANDOM_POS_01']:
            for value in [30., -20.]:
                rows.append(dict(control_id=control, window='w', cost='c', delta_CNY=value,
                                 risk_component=value, unit_component=0., participation_component=0.,
                                 gross_realized_difference=value, negative_fee_difference=0., unrealized_difference=0.))
        got = review.rollup(pd.DataFrame(rows), [])
        self.assertEqual(got.positive_delta_CNY.tolist(), [30., 30.])
        self.assertEqual(got.negative_delta_CNY.tolist(), [-20., -20.])
        self.assertEqual(got.delta_CNY.tolist(), [10., 10.])


if __name__ == '__main__':
    unittest.main()
