"""One synthetic causal/scorer/selection group; no data, fit, SQL or cash."""
from datetime import date, timedelta
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import numpy as np


class CausalForwardTiny(unittest.TestCase):
    def test_causal_state_fixed_scorer_and_original_selection(self):
        # Catches reseeding Wilder, future-row leakage, refitting/column drift,
        # raw-completeness vetoes, or argmax performed before the original K gate.
        path = Path(__file__).with_name('stage320_causal_forward_core.py')
        self.assertTrue(path.exists(), 'causal forward core has not been implemented')
        spec = importlib.util.spec_from_file_location('stage320_tiny', path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)

        def bar(c=100., volume=1000., oi=10., high=None, low=None):
            return dict(open=c, high=c+1 if high is None else high,
                        low=c-1 if low is None else low, close=c, volume=volume,
                        close_oi=oi, quality_status='accepted')

        dates = [(date(2026, 10, 1)+timedelta(days=i)).isoformat() for i in range(29)]
        with self.subTest('Wilder_seed_then_recurrence_survives_JSON_and_gap'):
            state = m.WilderState()
            for i in range(20):
                state.append(i, bar())
            self.assertEqual(state.to_dict()['N'], 2.)
            state.append(20, bar(high=110., low=90.))
            self.assertEqual(state.to_dict()['N'], 2.9)
            restored = m.WilderState.from_dict(json.loads(json.dumps(state.to_dict(), allow_nan=False)))
            restored.append(21, bar())
            self.assertAlmostEqual(restored.to_dict()['N'], 2.855, places=14)
            restored.append(23, bar())
            self.assertEqual(restored.to_dict()['run'], 1)
            self.assertIsNone(restored.to_dict()['N'])
            invalid = bar(); invalid['quality_status'] = 'rejected'
            restored.append(24, invalid)
            self.assertEqual(restored.to_dict()['run'], 0)
            with self.assertRaises(ValueError):
                restored.append(24, bar())

        names = list(m.COMMON)
        feature_names = names+[v+'_missing' for v in names]
        model = dict(schema='stage130_shared_portable_ridge_v1', scope='main', cutoff='2023-01-01',
                     feature_names=feature_names, coef=[0.]*52, intercept=1.)
        scaler = dict(scope='main', cutoff='2023-01-01', feature_names=feature_names,
                      common=dict(columns=names, mean=[0.]*26, scale=[1.]*26))
        with self.subTest('fixed52_raw_then_missing_order_and_no_allfinite_veto'):
            local_model = dict(model, coef=[3.]+[0.]*25+[7.]+[0.]*25, intercept=-1.)
            local_scaler = dict(scaler, common=dict(columns=names, mean=[1.]+[0.]*25, scale=[2.]+[1.]*25))
            raw = [dict(action_id='finite', raw26=[5.]+[None]*25),
                   dict(action_id='missing', raw26=[None]*26)]
            scores = m.infer_scores(raw, local_model, local_scaler)
            self.assertEqual([r['score'] for r in scores], [5., 6.])
            self.assertEqual(scores[0]['design52'][0], 2.)
            self.assertEqual(scores[1]['design52'][26], 1.)
            with self.assertRaises(ValueError):
                m.infer_scores(raw, local_model, dict(local_scaler, feature_names=feature_names[::-1]))

        epochs = ['SHFE.A.202611', 'SHFE.A.203001', 'SHFE.A.203002',
                  'SHFE.A.203003', 'SHFE.A.203004', 'DCE.L.203001', 'DCE.L_F.203001']
        states = {}
        for epoch in epochs:
            s = m.WilderState()
            for i in range(26):
                c = 105. if epoch.endswith('202611') else 100.
                volume = 2000. if epoch.endswith('202611') else 1000.
                oi = 20. if epoch.endswith('203002') else 10.
                s.append(i, bar(c, volume, oi))
            states[epoch] = s
        econ = {e: dict(economics_status='exact_epoch_metadata_snapshot', contract_multiplier=10.,
                        round_lot=1., tick_size=None, vendor_margin_rate=.2,
                        listed_date='2020-01-01') for e in epochs}
        products = ['SHFE.A', 'DCE.L', 'DCE.L_F', 'DCE.MISSING']
        dc = dict(confirmed=True, D_index=26, D_date=dates[26])
        prefix = {e:s.to_series() for e,s in states.items()}
        obs = m.build_u_observations(prefix, 25, dates, econ, products, D_context=dc)
        with self.subTest('complete_domain_causal_features_and_source_cost_units'):
            self.assertEqual(len(obs['mothers']), 4)
            self.assertEqual(len(obs['candidates']), 7)
            self.assertEqual(obs['references']['SHFE.A'], 'SHFE.A.202611')
            by_epoch = {r['reference_epoch']:r for r in obs['raw_rows']}
            row = by_epoch['SHFE.A.203001']
            self.assertEqual(row['raw26'][12], 4.)  # query excluded only from peer statistics
            self.assertAlmostEqual(row['raw26'][18], np.log(100./105.))  # whole pool front pair
            self.assertAlmostEqual(row['raw26'][24], .315)  # (12 fee+.6 slip)/(2N*10), N=2
            self.assertEqual(row['u_action_eligible'], 1)
            tie_pool = dict(prefix)
            near = prefix['SHFE.A.202611']
            near_valid = near.valid.copy(); near_valid[-1] = False
            tie_pool['SHFE.A.202611'] = SimpleNamespace(**dict(vars(near), valid=near_valid))
            tied = m.build_u_observations(tie_pool, 25, dates, econ, products, D_context=dc)
            self.assertEqual(tied['references']['SHFE.A'], 'SHFE.A.203002')  # equal V, larger close OI
            future = {}
            for e,s in prefix.items():
                future[e] = SimpleNamespace(days=np.r_[s.days, 26, 27],
                    values=np.vstack([s.values, [1., 1.e9, .1, 1.e8, 1.e9], [1., 2., .1, 1., 1.]]),
                    valid=np.r_[s.valid, True, True], N=np.r_[s.N, 1.e9, 1.e8],
                    low20=np.r_[s.low20, .1, .1], run=np.r_[s.run, 999, 1000],
                    close_oi=np.r_[s.close_oi, 1.e9, 1.e9])
            future['GFEX.NEW.203005'] = SimpleNamespace(days=np.array([26]),
                values=np.array([[100.,101.,99.,100.,1000.]]), valid=np.array([True]),
                N=np.array([2.]),low20=np.array([99.]),run=np.array([99]),close_oi=np.array([1.]))
            other = m.build_u_observations(future, 25, dates, econ, products, D_context=dc)
            np.testing.assert_allclose([r['raw26'] for r in obs['raw_rows']],
                                       [r['raw26'] for r in other['raw_rows']], equal_nan=True, rtol=0, atol=0)
            self.assertEqual(obs['references'], other['references'])
            self.assertEqual(obs['statuses'], other['statuses'])
            early = m.WilderState()
            for i in range(20): early.append(i, bar())
            x = m.build_u_observations({'DCE.L.203001':early}, 19, dates, econ, ['DCE.L'],
                                      D_context=dict(confirmed=True, D_index=20, D_date=dates[20]))
            self.assertEqual(x['candidates'][0]['u_action_eligible'], 1)
            self.assertTrue(np.isnan(x['raw_rows'][0]['raw26'][:11]).all())

        with self.subTest('D_K_before_argmax_original_family_priority_and_unknown_retained'):
            scores = m.infer_scores(obs['raw_rows'], model, scaler)
            for r in scores:
                if r['reference_epoch'].endswith('202611'): r['score'] = 100.
                elif r['product_id']=='DCE.L_F': r['score'] = 999.
                else: r['score'] = 2.
            chosen = m.select_u(obs, scores, dates, D_context=dc)
            choices = {r['product_id']:r for r in chosen['choices']}
            self.assertEqual(choices['SHFE.A']['chosen_epoch'], 'SHFE.A.203001')
            self.assertEqual(choices['DCE.L']['selected'], 1)
            self.assertEqual(choices['DCE.L_F']['selected'], 0)
            self.assertEqual(choices['DCE.MISSING']['selected'], 0)
            self.assertEqual(len(chosen['choices']), 4)
            self.assertEqual(chosen['boundaries']['SHFE.A.203001']['K_state'], 'after_calendar_pending')
            self.assertEqual(len(chosen['signals']), 2)
            required = {'N_u','low20_u','u_close','entry_capacity_qty','u_gross_capacity_qty',
                        'anchor_epoch','K_state','K_target_date','source_lifecycle_index','lifecycle_index'}
            self.assertTrue(required.issubset(chosen['signals'][0]))
            pending = m.select_u(obs, scores, dates, D_context=dict(confirmed=False))
            self.assertFalse(any(r['selected'] for r in pending['choices']))
            self.assertTrue(any(r['new_eligible'] is None for r in pending['audit']))
            self.assertEqual(len(pending['choices']), 4)
            obs_unknown = m.build_u_observations(prefix, 25, dates, econ, products,
                                                D_context=dict(confirmed=False))
            with self.assertRaises(ValueError):
                m.select_u(obs_unknown, scores, dates, D_context=dc)
            with self.assertRaises(ValueError):
                m.select_u(obs, scores, dates, D_context=dict(confirmed=True, D_index=27, D_date=dates[27]))


if __name__ == '__main__':
    unittest.main()
