"""Bounded synthetic fixtures only; never reads real training inputs."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

SOURCE = Path(__file__).with_name('stage167_member_concentration_fit.py')
if SOURCE.exists():
    spec = importlib.util.spec_from_file_location('stage167', SOURCE)
    fit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fit)
else:
    fit = None


class ConcentrationTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(fit, 'Stage167 implementation is missing')

    def test_weighted_q_uses_only_observations_control_final_slot_is_zero(self):
        # Catches using all weights for q moments or standardizing raw control0.
        q = np.array([0., 2., np.nan])
        stat = fit.q_statistics(q, np.array([1., 3., 100.]))
        self.assertEqual(stat['finite_count'], 2)
        self.assertEqual(stat['mean'], 1.5)
        self.assertEqual(stat['var'], .75)
        self.assertAlmostEqual(stat['scale'], np.sqrt(.75))
        common = dict(common=dict(mean=[0.]*26, scale=[1.]*26))
        a = fit.design54(np.zeros((3,26)), q, common, stat, 'CONTROL54')
        b = fit.design54(np.zeros((3,26)), q, common, stat, 'CONCENTRATION54')
        np.testing.assert_array_equal(a[:, :53], b[:, :53])
        np.testing.assert_array_equal(a[:, 52], [0,0,1])
        np.testing.assert_array_equal(a[:, 53], [0,0,0])
        np.testing.assert_allclose(b[:,53], [-1.5/np.sqrt(.75), .5/np.sqrt(.75), 0])

    def test_any_bad_fold_makes_global_preflight_no_go(self):
        # Catches fitting early folds before discovering a later zero variance.
        good = fit.q_statistics(np.array([0.,1.]), np.ones(2))
        bad = fit.q_statistics(np.array([2.,2.,np.nan]), np.ones(3))
        preflight = fit.global_preflight([dict(scope=str(i), cutoff='2020', q_statistics=good) for i in range(5)] +
                                        [dict(scope='last', cutoff='2023', q_statistics=bad)])
        self.assertFalse(preflight['ready'])
        self.assertEqual(preflight['fit_calls_authorized'], 0)
        self.assertIn('nonpositive_q_variance', preflight['failures'][0]['reason'])
        absent = fit.q_statistics(np.array([np.nan]), np.ones(1))
        self.assertEqual(absent['reason'], 'no_finite_q')

    def test_projection_keeps_true_zero_missing_and_parent_child_ids(self):
        # Catches dropping missing-q actions or aligning on unrelated mother IDs.
        a = pd.DataFrame([dict(action_sequence_index=0, action_id='child0', actual_epoch='SHFE.CU.202005',
                               u_date='2020-01-02', u_index=0, product_id='SHFE.CU', family_id='CU', mother_sequence_index=9,
                               mother_event_id='parent9'),
                          dict(action_sequence_index=1, action_id='child1', actual_epoch='DCE.L_F.202005',
                               u_date='2020-01-02', u_index=0, product_id='DCE.L_F', family_id='L', mother_sequence_index=10,
                               mother_event_id='parent10')])
        p = a.copy();p['scalar_primary']=['0',''];p['missing']=['False','True'];p['projection_status']=['observed','exact_scope_not_disclosed']
        q = fit.align_projection(a, p)
        self.assertEqual(len(q), 2)
        self.assertEqual(q[0], 0)
        self.assertTrue(np.isnan(q[1]))
        p.loc[1,'action_id']='wrong'
        with self.assertRaisesRegex(ValueError, 'projection_identity'):
            fit.align_projection(a, p)

    def test_complete_child_pool_k_filter_reselects_and_retains_noobs_held_scope(self):
        # Catches post-veto of the high scorer and failure to alias held scope.
        cal = ['2020-01-02','2020-01-03','2020-02-03','2020-03-02']
        parents = pd.DataFrame([dict(sequence_index=9,event_id='p9',product_id='SHFE.CU',family_id='CU',u_date=cal[0],u_index=0,reference_epoch='SHFE.CU.202002'),
                                dict(sequence_index=10,event_id='p10',product_id='DCE.S',family_id='S',u_date=cal[0],u_index=0,reference_epoch='')])
        scores = pd.DataFrame([dict(sequence_index=i,action_id='a'+str(i),mother_sequence_index=9,mother_event_id='p9',product_id='SHFE.CU',family_id='CU',u_date=cal[0],u_index=0,reference_epoch=e,anchor_epoch='SHFE.CU.202002',u_action_eligible=1,score=s,scope='holdout_1',cutoff='2020-01-01')
                               for i,e,s in [(0,'SHFE.CU.202002',10.),(1,'SHFE.CU.202004',2.)]])
        choices,bounds,summary=fit.choose_scope(parents,scores,'holdout_1','CONCENTRATION54',cal)
        self.assertEqual(len(choices),2)
        self.assertEqual(choices.iloc[0].chosen_action_id,'a1')
        self.assertEqual(choices.iloc[0].scope,'holdout_1')
        self.assertEqual(choices.iloc[1].selection_state,'no_observed_children')
        self.assertEqual(set(bounds),{'SHFE.CU.202002','SHFE.CU.202004'})

    def test_tie_and_ordinary_f_priority_are_preserved_per_arm(self):
        # Catches mixing arm pools or letting high-scored F beat ordinary priority.
        cal=['2020-01-02','2020-01-03','2020-02-03']
        parents=pd.DataFrame([dict(sequence_index=j,event_id='p'+str(j),product_id=p,family_id='L',u_date=cal[0],u_index=0,reference_epoch=p+'.202004')
                              for j,p in [(1,'DCE.L'),(2,'DCE.L_F')]])
        children=[]
        for i,j,p,e,s in [(1,1,'DCE.L','DCE.L.202005',2),(2,1,'DCE.L','DCE.L.202004',2),(3,2,'DCE.L_F','DCE.L_F.202004',10)]:
            children.append(dict(sequence_index=i,action_id='a'+str(i),mother_sequence_index=j,mother_event_id='p'+str(j),product_id=p,family_id='L',u_date=cal[0],u_index=0,reference_epoch=e,anchor_epoch=p+'.202004',u_action_eligible=1,score=s,scope='main',cutoff='2020-01-01'))
        out,_,_=fit.choose_scope(parents,pd.DataFrame(children),'main','CONTROL54',cal)
        self.assertEqual(out.iloc[0].chosen_action_id,'a2')
        self.assertEqual(out.iloc[1].selection_state,'family_priority_suppressed')
        self.assertTrue(out.arm.eq('CONTROL54').all())

    def test_tiny_two_arm_ridge_and_normal_equations_have_expected_coefficient(self):
        # Catches penalizing the intercept or changing ridge dimension/alpha.
        y=np.array([-1.,1.]);w=np.ones(2);zero=np.zeros((2,54));x=zero.copy();x[:,53]=[-1,1]
        _, control, eq0=fit.fit_arrays(zero,y,w)
        completed=[]
        _, concentration, eq=fit.fit_arrays(x,y,w,on_completed=lambda: completed.append('done'))
        self.assertEqual(completed,['done'])
        np.testing.assert_allclose(control['coef'], np.zeros(54), atol=1e-14)
        self.assertAlmostEqual(concentration['coef'][53],2/3)
        self.assertAlmostEqual(concentration['intercept'],0)
        self.assertEqual(eq['lhs'].shape,(55,55))
        np.testing.assert_allclose(eq['lhs']@eq['coefficient_with_intercept'],eq['rhs'],atol=1e-12)

    def test_product_major_parents_restore_original_order_across_cutoffs(self):
        # Catches publishing cutoff-major [0,2,1,3] instead of original order.
        order = getattr(fit,'restore_parent_order',None)
        self.assertTrue(callable(order), 'cross-cutoff parent order restoration is missing')
        frame=pd.DataFrame([dict(arm=arm,sequence_index=i,event_id='p'+str(i),selected=i%2)
                            for arm in ('CONTROL54','CONCENTRATION54') for i in (0,2,1,3)])
        out=order(frame)
        for arm in ('CONTROL54','CONCENTRATION54'):
            part=out.loc[out.arm.eq(arm)]
            self.assertEqual(part.event_id.tolist(),['p0','p1','p2','p3'])
            self.assertEqual(part.selected.tolist(),[0,1,0,1])


if __name__ == '__main__':
    unittest.main()
