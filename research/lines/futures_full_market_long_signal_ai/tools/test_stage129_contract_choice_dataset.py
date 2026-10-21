"""Stage129 semantic boundaries only; tiny arrays, no native I/O or old suite."""
from datetime import date, timedelta
import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

TOOLS = Path(__file__).parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(module, count=26, months=('203001',), changes=None, missing=()):
    changes = changes or {}
    dates = [(date(2020, 1, 1) + timedelta(days=k)).isoformat() for k in range(count)]
    records = []
    epochs = ['SHFE.A.' + month for month in months]
    for z, epoch in enumerate(epochs):
        for k, day in enumerate(dates):
            if (epoch, k) in missing:
                continue
            values = changes.get((epoch, k), (100 + z + .1*k, 101 + z + .1*k, 99 + z + .1*k, 100 + z + .1*k))
            records.append(dict(contract_epoch_id=epoch, trade_date=day, open=values[0], high=values[1],
                                low=values[2], close=values[3], volume=1000., quality_status='accepted'))
    market = module.ref.Market.from_records(records, dates)
    mothers = pd.DataFrame([dict(sequence_index=k, event_id='m'+str(k), product_id='SHFE.A', family_id='SHFE.A',
                                u_date=day, u_index=k, reference_epoch=epochs[0]) for k, day in enumerate(dates)])
    econ = {epoch: dict(economics_status='exact_epoch_metadata_snapshot', contract_multiplier=10., round_lot=1.,
                       tick_size=None, vendor_margin_rate=.2, listed_date='2019-01-01',
                       known_lifecycle_exit_boundary='2030-01-01', future_info_scope='product_default_snapshot') for epoch in epochs}
    return mothers, market, dates, econ


class Stage129Semantics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load('stage129_contract_choice_dataset')

    def test_capacity_and_unknown_mothers_survive_without_child_fabrication(self):
        m = self.m
        self.assertEqual(m.capacity(199., 1.), (1, 0, 'capacity_below_one_roundtrip'))
        self.assertEqual(m.capacity(200., 1.), (2, 1, 'known_roundtrip_capacity'))
        self.assertEqual(m.capacity(1000., 3.), (9, 3, 'known_roundtrip_capacity'))
        self.assertEqual(m.capacity(1000., np.nan)[2], 'execution_capacity_unknown')
        f = list(fixture(m))
        empty = dict(sequence_index=26, event_id='empty', product_id='DCE.S', family_id='DCE.S', u_date=f[2][-1], u_index=25, reference_epoch='')
        f[0] = pd.concat([f[0], pd.DataFrame([empty])], ignore_index=True)
        a, x, counts = m.build_arrays(*f)
        self.assertEqual(len(f[0]), 27)
        self.assertEqual(counts['mother_rows_without_children'], 1)
        self.assertNotIn('empty', set(a.mother_event_id))
        self.assertEqual(x.shape, (26, 26))
        self.assertTrue(a.action_id.eq(a.event_id).all())
        self.assertEqual(a.iloc[-1].u_action_eligible,1)
        self.assertEqual(a.iloc[-1].label_state,'intent_right_censored')

    def test_prefix_candidate_X_no_future_D_or_future_canonical_filter(self):
        m = self.m
        f = fixture(m, months=('203001', '203002'))
        a, x, _ = m.build_arrays(*f)
        g = list(f)
        g[1] = m.ref.Market({e: m.ref.EpochSeries(s.days[:-1], s.values[:-1], s.valid[:-1]) for e, s in f[1].series.items()}, f[2])
        g[0] = f[0].copy()
        g[0].loc[g[0].u_index.eq(25), 'reference_epoch'] = 'SHFE.A.203002'
        b, y, _ = m.build_arrays(*g)
        use = a.u_index.lt(25)
        v = b.u_index.lt(25)
        self.assertEqual(a.loc[use, 'action_id'].tolist(), b.loc[v, 'action_id'].tolist())
        np.testing.assert_allclose(x[use], y[v], equal_nan=True, rtol=0, atol=0)
        self.assertEqual(b.loc[b.u_index.eq(24), 'label_state'].unique().tolist(), ['entry_execution_unknown'])

    def test_candidate_own_SMA_and_reusable_maturity_exact_049(self):
        m = self.m
        f = fixture(m, months=('203001', '203002', '203003', '203004', '203005'),
                    changes={('SHFE.A.203002', 21): (104., 110., 100., 109.),
                             ('SHFE.A.203002', 24): (104., 110., 100., 109.)})
        a, x, _ = m.build_arrays(*f)
        rows = a.loc[a.u_index.eq(24)].copy()
        self.assertGreater(rows.N_u.nunique(), 1)
        self.assertGreater(np.unique(x[rows.index, 10]).size, 1)
        old = load('stage049_maturity_features')
        for i, row in rows.iterrows():
            single = pd.DataFrame([dict(event_id=row.event_id, product_id=row.product_id, u_date=row.u_date, reference_epoch=row.actual_epoch)])
            expected, _, _ = old.build_features(single, f[1], f[2], f[3])
            np.testing.assert_allclose(x[i, 11:24], expected[m.MATURITY].iloc[0].to_numpy(float), equal_nan=True, rtol=1e-13, atol=1e-13)
        i = rows.loc[rows.actual_epoch.eq('SHFE.A.203002')].index[0]
        own, _, _ = m.own11(f[1].series['SHFE.A.203002'], 24)
        np.testing.assert_allclose(x[i, :11], own, rtol=0, atol=0)
        old_own = load('stage009_day_proxy_dataset')
        window = [dict(zip(('open','high','low','close','volume'), v)) for v in f[1].series['SHFE.A.203002'].values[4:25]]
        np.testing.assert_allclose(own, old_own.own_features(window)[0], rtol=0, atol=0)
        self.assertNotAlmostEqual(own[10]*a.loc[i, 'u_close'], a.loc[i, 'N_u'])
        self.assertAlmostEqual(x[i, 25], (a.loc[i, 'u_close']-a.loc[i, 'low20_u'])/(2*a.loc[i, 'N_u']))

    def test_far_month_anchor_changed_then_latched_request(self):
        m = self.m
        self.assertIsNone(m.anchor_request(None, 'CANON', 'CANON', 10, 100))
        request = m.anchor_request(None, 'CANON', 'OTHER', 10, 100)
        self.assertEqual(request, 'liquidity_reference_changed')
        self.assertEqual(m.anchor_request(request, 'CANON', 'CANON', 11, 100), request)
        self.assertEqual(m.anchor_request(None, 'CANON', None, 10, 100), 'observation_exit_requested')
        f = list(fixture(m, months=('203001', '203002')))
        # Gentle rising bars touch the narrow stop. Raise next bars above the old stop to isolate anchor request.
        for epoch, series in f[1].series.items():
            series.values[20:] = np.array([[110+k, 111+k, 109.9+k, 110.5+k, 1000.] for k in range(6)])
        f[0].loc[f[0].u_index.eq(21), 'reference_epoch'] = 'SHFE.A.203002'
        a, _, _ = m.build_arrays(*f)
        row = a.loc[a.u_index.eq(19)&a.actual_epoch.eq('SHFE.A.203002')].iloc[0]
        self.assertEqual(row.anchor_epoch, 'SHFE.A.203001')
        self.assertEqual(row.exit_index, 22)
        self.assertEqual(row.exit_reason, 'liquidity_reference_changed')

    def test_single_canonical_bounded_regression_to_070_and_invalid_retention(self):
        m = self.m
        f = fixture(m)
        a, _, _ = m.build_arrays(*f)
        original = f[0].copy()
        original['exchange'] = 'SHFE'; original['product'] = 'A'
        original['direction'] = 'long'; original['status'] = 'observed_long_research_opportunity'
        original['planned_execution_date'] = [*f[2][1:], '']
        old = m.old_labels.build_labels(original.drop(columns=['sequence_index', 'family_id', 'u_index']), f[1], f[2], f[3], policy='NARROW')
        for col in ('N_u', 'low20_u', 'entry_index', 'exit_index', 'net_R_stress', 'stress_u_fee_roundtrip_per_lot'):
            np.testing.assert_allclose(a[col].to_numpy(float), old[col].to_numpy(float), equal_nan=True, rtol=1e-13, atol=1e-13)
        self.assertEqual(a.label_state.tolist(), old.label_state.tolist())
        self.assertEqual(a.exit_reason.fillna('').tolist(), old.exit_reason.fillna('').tolist())
        f[1].series['SHFE.A.203001'].valid[24] = False
        b, _, _ = m.build_arrays(*f)
        self.assertEqual(len(a), len(b))
        self.assertEqual(b.loc[b.u_index.eq(24), 'u_action_eligible'].item(), 0)
        self.assertEqual(b.loc[b.u_index.eq(24), 'observation_state'].item(), 'invalid_u_native_bar')

    def test_F_exact_economics_peer_isolation_and_no_anchor_cannot_act(self):
        m = self.m
        f = list(fixture(m, months=('203001','203002','203003','203004')))
        e = 'DCE.L_F.203001'; original = f[1].series['SHFE.A.203001']
        f[1].series[e] = m.ref.EpochSeries(original.days.copy(),original.values.copy(),original.valid.copy())
        f[3][e] = dict(f[3]['SHFE.A.203001'],contract_multiplier=7.,round_lot=3.)
        extra = f[0].copy();extra.sequence_index += len(f[0]); extra.event_id = 'F'+extra.event_id
        extra.product_id='DCE.L_F';extra.family_id='DCE.L';extra.reference_epoch=e
        extra.loc[extra.u_index.eq(24),'reference_epoch']=''
        f[0]=pd.concat([f[0],extra],ignore_index=True)
        a,x,_=m.build_arrays(*f)
        rows=a.loc[a.actual_epoch.eq(e)]
        self.assertTrue(rows.multiplier.eq(7.).all())
        np.testing.assert_array_equal(x[rows.index,12],np.zeros(len(rows)))
        missing=rows.loc[rows.u_index.eq(24)].iloc[0]
        self.assertEqual(missing.u_action_eligible,0)
        self.assertEqual(missing.u_ineligibility_reason,'no_accepted_u_anchor')


if __name__ == '__main__':
    unittest.main()
