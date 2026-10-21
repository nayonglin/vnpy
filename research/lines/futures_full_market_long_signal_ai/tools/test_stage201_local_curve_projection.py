"""Small Stage201 geometry fixtures; no old dataset, model, labels or SQL."""
import importlib.util
import math
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

SOURCE = Path(__file__).with_name('stage201_local_curve_projection.py')


def tiny(months=('203001', '203003', '203006'), prices=(100., 120., 160.)):
    mothers = pd.DataFrame([dict(sequence_index=k, event_id='m'+str(k),
        product_id=p, family_id=p, u_date='2029-12-10', u_index=5,
        reference_epoch='SHFE.A.203001' if k == 0 else '')
        for k, p in enumerate(('SHFE.A', 'DCE.S'))])
    actions = pd.DataFrame([dict(sequence_index=k, action_id='a'+str(k),
        mother_sequence_index=0, mother_event_id='m0', actual_epoch='SHFE.A.'+month,
        product_id='SHFE.A', family_id='SHFE.A', u_date='2029-12-10',
        u_index=5, u_close=price) for k, (month, price) in enumerate(zip(months, prices))])
    return actions, mothers


class Stage201Geometry(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.exists(), 'Stage201 implementation absent')
        spec = importlib.util.spec_from_file_location('stage201', SOURCE)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_unequal_month_chord_and_complete_identity_with_nochild(self):
        a, m = tiny()
        p, mothers, anchors = self.module.project(a, m)
        self.assertAlmostEqual(p.q_raw.iloc[1], math.log(120)-.6*math.log(100)-.4*math.log(160), places=14)
        self.assertEqual(p.loc[1, ['lower_epoch', 'upper_epoch', 'lower_month_gap', 'upper_month_gap']].tolist(),
                         ['SHFE.A.203001', 'SHFE.A.203006', 2, 3])
        pd.testing.assert_frame_equal(p[a.columns.drop('u_close')], a.drop(columns='u_close'))
        pd.testing.assert_frame_equal(mothers[m.columns], m)
        self.assertEqual(mothers.child_count.tolist(), [3, 0])
        self.assertEqual(mothers.projection_status.tolist(), ['source_ready_some', 'no_child'])
        self.assertEqual(anchors[0]['sequence_index'], 1)
        self.assertEqual(anchors[0]['query_price'], 120.)
        broken = a.copy(); broken.loc[1, 'mother_event_id'] = 'wrong'
        with self.assertRaises(ValueError):
            self.module.project(broken, m)

    def test_log_affine_zero_and_common_unit_invariance(self):
        a, m = tiny(prices=tuple(np.exp([1., 1.4, 2.])))
        p, _, _ = self.module.project(a, m)
        self.assertAlmostEqual(p.q_raw.iloc[1], 0., places=14)
        a.u_close *= 17.3
        changed, _, _ = self.module.project(a, m)
        np.testing.assert_allclose(changed.q_raw, p.q_raw, atol=1e-14, rtol=0, equal_nan=True)

    def test_endpoints_missing_price_expired_month_and_duplicate_whole_group(self):
        a, m = tiny()
        p, _, _ = self.module.project(a, m)
        self.assertTrue(np.isnan(p.q_raw.iloc[[0, 2]]).all())
        self.assertEqual(p.projection_status.iloc[[0, 2]].tolist(), ['no_lower_neighbor', 'no_upper_neighbor'])
        for value in (0., -1., np.nan, np.inf):
            bad = a.copy(); bad.loc[1, 'u_close'] = value
            p, _, _ = self.module.project(bad, m)
            self.assertTrue(p.q_raw.isna().all())
            self.assertEqual(p.projection_status.iloc[1], 'nonpositive_or_nonfinite_quote')
        bad = a.copy(); bad.loc[1, 'actual_epoch'] = 'SHFE.A.202912'
        p, _, _ = self.module.project(bad, m)
        self.assertEqual(p.projection_status.iloc[1], 'nominal_month_not_after_u')
        bad = a.copy(); bad.loc[2, 'actual_epoch'] = bad.loc[1, 'actual_epoch']
        p, mothers, _ = self.module.project(bad, m)
        self.assertEqual(p.projection_status.unique().tolist(), ['duplicate_nominal_month'])
        self.assertTrue(p.q_raw.isna().all())
        self.assertEqual(mothers.projection_status.iloc[0], 'duplicate_nominal_month')

    def test_same_existing_curve_summaries_but_different_local_shape(self):
        # Query is month 2. Month 3 is a peer and its whole price history is
        # rescaled, leaving its current/previous return and query own history intact.
        history = np.arange(80., 102.)[:, None] + np.arange(4.)[None, :]
        before = history.copy(); after = history.copy(); after[:, 2] *= 2.
        def original_maturity_summary(h):
            current, previous = h[-1], h[-2]
            peers = np.array([0, 2, 3]); returns = np.log(current[peers]/previous[peers])
            tau = np.array([1., 2., 3., 4.])/12.
            return np.array([3., np.ptp(tau[peers]), returns.mean(), returns.std(ddof=0),
                returns.min(), returns.max(), math.log(current[1]/current[0]),
                math.log(previous[1]/previous[0]), tau[1]-tau[0]])
        np.testing.assert_array_equal(after[:, 1], before[:, 1])
        np.testing.assert_array_equal(original_maturity_summary(after), original_maturity_summary(before))
        a, m = tiny(('203001', '203002', '203003', '203004'), before[-1])
        p, _, _ = self.module.project(a, m)
        a.u_close = after[-1]
        changed, _, _ = self.module.project(a, m)
        self.assertAlmostEqual(changed.q_raw.iloc[1]-p.q_raw.iloc[1], -.5*math.log(2.), places=14)
        # Same query history => same own11, N/C and query cost/low20 fields;
        # all three peer returns and their tenor support stay exactly unchanged.
        # These facts plus the recomputed nine maturity values preserve COMMON26.


if __name__ == '__main__':
    unittest.main()
