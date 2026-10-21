"""Bounded synthetic semantics only; no accepted inputs are opened."""
import importlib.util
from pathlib import Path
import unittest
import tempfile
import numpy as np
import pandas as pd

SOURCE = Path(__file__).with_name('stage538_sector_residual_fit.py')


def mother(i, product='DCE.L', day='2024-10-01', u=0):
    return dict(sequence_index=i, event_id=f'm{i}', product_id=product,
                family_id=product.removesuffix('_F'), u_date=day, u_index=u,
                reference_epoch=product+'.202505')


def child(i, p, epoch, score, scope='main'):
    return dict(sequence_index=i, action_id=f'a{i}', mother_sequence_index=p['sequence_index'],
                mother_event_id=p['event_id'], product_id=p['product_id'], family_id=p['family_id'],
                u_date=p['u_date'], u_index=p['u_index'], reference_epoch=epoch,
                anchor_epoch=p['reference_epoch'], u_action_eligible=1, score=score,
                scope=scope, cutoff='2023-01-01')


class SectorResidualFixtures(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), 'Stage538 implementation missing')
        s = importlib.util.spec_from_file_location('fixture538', SOURCE)
        self.m = importlib.util.module_from_spec(s); s.loader.exec_module(self.m)

    def test_actual_centered_design_with_unknown_mass_and_df_bound(self):
        # A conditional renormalization or diag(p)-pp' shortcut must fail this.
        f = ['f1', 'f2', 'unknown']; w = np.array([1., 2., 1.]); r = np.array([3., -1., 100.])
        mapping = dict(f1='s1', f2='s2'); sectors = ['s1', 's2', 'cold']
        h = self.m.fit_offset(f, r, w, mapping, sectors)
        p = np.array([.25, .5, 0.]); z = np.array([[.75, -.5, 0], [-.25, .5, 0], [0, 0, 0]])
        q = w / w.sum(); g = z.T @ (q[:, None]*z); b = z.T @ (q*r)
        np.testing.assert_allclose(h['p'], p); np.testing.assert_allclose(h['G'], g)
        np.testing.assert_allclose(h['b'], b)
        np.testing.assert_allclose(h['gamma'], np.linalg.solve(g+np.eye(3), b))
        np.testing.assert_allclose(h['sumwZ'], q @ z)
        self.assertEqual(h['mapped_training_weight'], .75)
        self.assertGreater(h['effective_df'], 0); self.assertLessEqual(h['effective_df'], 1)
        d = self.m.offsets(['f1', 'f2', 'unknown', 'coldfamily'], h, dict(mapping, coldfamily='cold'))
        self.assertEqual(d[2], 0.); self.assertEqual(d[3], 0.)
        self.assertAlmostEqual(h['sumwdelta'], q @ np.r_[d[:2], 0.])
        # Multiplying old weights never changes the candidate's sumw1 fit.
        other = self.m.fit_offset(f, r, w*1000, mapping, sectors)
        np.testing.assert_allclose(h['gamma'], other['gamma'])

    def test_single_warm_group_no_new_intercept_and_unknown_exact_zero(self):
        h = self.m.fit_offset(['x', 'x'], [100., 200.], [1., 1.], {'x':'s'}, ['s', 'cold'])
        self.assertEqual(h['effective_df'], 0.)
        self.assertEqual(self.m.offsets(['x', 'u'], h, {'x':'s'}) .tolist(), [0., 0.])

    def test_same_product_month_offsets_preserve_differences_and_old_negatives(self):
        h = self.m.fit_offset(['x', 'y'], [10., -10.], [1.,1.], {'x':'s','y':'t'}, ['s','t'])
        base = np.array([-0.1, 2.0, -5.0]); d = self.m.offsets(['x']*3, h, {'x':'s'})
        np.testing.assert_allclose(np.diff(base+d), np.diff(base), atol=1e-15)
        self.assertGreater(base[0]+d[0], 0); self.assertLess(base[2]+d[2], 0)

    def test_select_scope_equals_original156_including_K_reselect_and_F(self):
        cal=['2024-11-29','2024-12-02','2025-01-02']; p=mother(0, day=cal[0]); f=mother(1,'DCE.L_F',cal[0])
        rows=[child(0,p,'DCE.L.202501',10,'holdout_1'),child(1,p,'DCE.L.202502',2,'holdout_1'),
              child(2,f,'DCE.L_F.202502',100,'holdout_1')]
        got=self.m.select_scope([p,f], iter(rows), cal, cal[-1], 'holdout_1', 'C')
        alias=[dict(r,scope='main') for r in rows]
        ref=self.m.select156.select_full_pool([p,f],alias,cal,cal[-1],audit_sink=lambda _:None)
        self.assertEqual([r['chosen_action_id'] for r in got['choices']], [r['chosen_action_id'] for r in ref['choices']])
        self.assertEqual(got['choices'][0]['chosen_action_id'],'a1')
        self.assertEqual(got['choices'][1]['selection_state'],'family_priority_suppressed')
        self.assertTrue(all(r['scope']=='holdout_1' and r['arm']=='C' for r in got['choices']))
        with self.assertRaisesRegex(ValueError, 'scope'):
            self.m.select_scope([p], [dict(rows[0],scope='main')],cal,cal[-1],'holdout_1','C')

    def test_diagnostics_same_unknown_zero_distinct_unknown_nan_and_equal_day(self):
        rows=[]
        choices=[('d1','f1',0, {'A':'open','B':'open','C':'open'}),
                 ('d1','f2',0, {'A':'','B':'','C':'win'}),
                 ('d2','f3',1, {'A':'','B':'','C':'otheropen'})]
        for day,fam,u,arms in choices:
            for arm,aid in arms.items():
                rows.append(dict(scope='holdout_0',arm=arm,family_id=fam,u_index=u,u_date=day,
                                 chosen_action_id=aid,selected=int(bool(aid))))
        acts=pd.DataFrame([dict(action_id='open',label_state='open',participation_state='participating',net_R_stress=np.nan,label_known_date=''),
                           dict(action_id='otheropen',label_state='open',participation_state='participating',net_R_stress=np.nan,label_known_date=''),
                           dict(action_id='win',label_state='closed_complete_bar_model',participation_state='participating',net_R_stress=4.,label_known_date='2024-01-01')])
        report,daily,annual,linked=self.m.diagnostics(pd.DataFrame(rows),acts,'2026-10-16')
        ca=report['groups']['holdout_0']['C_minus_A']
        self.assertEqual(ca['common_unresolved_same_action'],1)
        self.assertEqual(ca['unknown_differential_selected_events'],1)
        self.assertEqual(ca['known_u_equal_mean_increment_R'],2.)
        self.assertTrue(daily.loc[daily.u_date.eq('d2') & daily.contrast.eq('C_minus_A'),'delta_R'].isna().all())
        self.assertEqual(len(linked),9)

    def test_nominal_cash_gate_requires_each_contrast_both_groups_and_strict_gain(self):
        def report(values):
            return {'groups':{s:{c:{'known_u_equal_mean_increment_R':values[(s,c)]} for c in self.m.CONTRASTS} for s in ['holdout_0','holdout_1']}}
        v={(s,c):0. for s in ['holdout_0','holdout_1'] for c in self.m.CONTRASTS}
        self.assertFalse(self.m.nominal_cash_gate(report(v)))
        v[('holdout_0','C_minus_A')]=1.;v[('holdout_1','C_minus_B')]=.1
        self.assertTrue(self.m.nominal_cash_gate(report(v)))
        v[('holdout_0','C_minus_B')]=-.001
        self.assertFalse(self.m.nominal_cash_gate(report(v)))

    def test_shared_training_only_uses_original_maturity_no_K_filter_and_own_held(self):
        groups={i:next(f'f{n}' for n in range(100) if self.m.base130.family_group(f'f{n}')==i) for i in [0,1]}
        a=pd.DataFrame([dict(sequence_index=i,u_action_eligible=1,label_state='closed_complete_bar_model',
                            u_date='2019-12-01',label_known_date=('2020-01-01' if i==2 else '2019-12-31'),
                            net_R_stress=1.,family_id=groups[i%2]) for i in range(3)])
        # Predictor/parent rows are needed by the accepted helper; no target values enter the train.
        a=pd.concat([a,pd.DataFrame([dict(sequence_index=3,u_date='2020-01-02',family_id=groups[0])])],ignore_index=True)
        p=pd.DataFrame([dict(u_date='2020-01-02',family_id=groups[0])])
        train,_,_=self.m.base130.fold_slices(a,p,'2020-01-01','2023-01-01','holdout_0')
        self.assertEqual(train.sequence_index.tolist(),[1])

    def test_single_compressed_read_and_npz_preserve_blank_unknown_and_binary_hash(self):
        # Exercise the exact gzip/Pandas wrappers used by actual without any old source.
        with tempfile.TemporaryDirectory(prefix='stage538-fixture-') as tmp:
            path=Path(tmp)/'tiny.csv.gz'
            original=pd.DataFrame(dict(sequence_index=[0,1],known=['2020-01-01',''],value=[1.25,np.nan]))
            bound=self.m.write_frame(path,original)
            got=self.m.read_table_once(bound,['sequence_index','known','value'],['sequence_index','value'])
            self.assertEqual(got.known.tolist(),['2020-01-01',''])
            self.assertEqual(got.sequence_index.tolist(),[0,1]);self.assertTrue(np.isnan(got.value.iloc[1]))
            corrupt=dict(bound,sha256='0'*64)
            with self.assertRaisesRegex(ValueError,'binding'):
                self.m.read_table_once(corrupt,['sequence_index'],['sequence_index'])
            npz=Path(tmp)/'tiny.npz';np.savez_compressed(npz,raw26=np.array([[1.,np.nan]]),sequence_index=np.array([4]))
            arrays=self.m.read_npz_once(self.m.binding(npz))
            self.assertEqual(arrays['sequence_index'].tolist(),[4]);self.assertTrue(np.isnan(arrays['raw26'][0,1]))


if __name__=='__main__': unittest.main()
