"""Finite independent semantic counterexamples; no actual fit/cash/input reads."""
import importlib.util
from pathlib import Path
import unittest
import json
import numpy as np
import pandas as pd

SOURCE=Path(__file__).with_name('stage169_member_concentration_review.py')


class ReviewFixtures(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(),'Stage169 independent reviewer missing')
        spec=importlib.util.spec_from_file_location('review169_fixture',SOURCE)
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)

    def test_q_moments_ignore_missing_weights_and_control_is_final_zero(self):
        q=np.array([0.,2.,np.nan]);w=np.array([1.,3.,100.])
        s=self.m.q_statistics(q,w)
        self.assertEqual((s['mean'],s['var'],s['finite_count']),(1.5,.75,2))
        base=np.zeros((3,26));scaler=dict(common=dict(mean=[0.]*26,scale=[1.]*26))
        control=self.m.design54(base,q,scaler,s,'CONTROL54');active=self.m.design54(base,q,scaler,s,'CONCENTRATION54')
        np.testing.assert_array_equal(control[:,:53],active[:,:53])
        np.testing.assert_array_equal(control[:,53],[0.,0.,0.])
        np.testing.assert_array_equal(control[:,52],[0.,0.,1.])
        np.testing.assert_allclose(active[:,53],[-1.5/np.sqrt(.75),.5/np.sqrt(.75),0.])

    def test_maturity_is_strict_and_never_filtered_by_q_or_K(self):
        rows=pd.DataFrame([dict(u_action_eligible=1,label_state='closed_complete_bar_model',u_date='2019-01-01',label_known_date=d,net_R_stress=1.,family_id='F',q=q,K_index=k) for d,q,k in [('2019-12-31',np.nan,0),('2020-01-01',1.,9999),('',2.,9999)]])
        self.assertEqual(self.m.mature_mask(rows,'main','2020-01-01').tolist(),[True,False,False])

    def test_ridge_penalizes_all_features_but_not_intercept_without_refitting(self):
        X=np.zeros((2,54));X[:,53]=[-1.,1.];y=np.array([-1.,1.]);w=np.ones(2)
        lhs,rhs=self.m.normal_equations(X,y,w)
        self.assertEqual((lhs[53,53],lhs[54,54],rhs[53]),(3.,2.,2.))
        beta=np.zeros(55);beta[53]=2/3
        np.testing.assert_allclose(lhs@beta,rhs,atol=1e-14)

    def test_complete_K_choice_reselects_and_retains_empty_parent(self):
        cal=['2020-01-02','2020-01-03','2020-02-03','2020-03-02']
        parents=[dict(sequence_index=9,event_id='p9',product_id='SHFE.CU',family_id='F',u_date=cal[0],u_index=0,reference_epoch='SHFE.CU.202002'),dict(sequence_index=10,event_id='p10',product_id='DCE.S',family_id='S',u_date=cal[0],u_index=0,reference_epoch='')]
        children=[dict(sequence_index=i,action_id='a'+str(i),mother_sequence_index=9,mother_event_id='p9',product_id='SHFE.CU',family_id='F',u_date=cal[0],u_index=0,reference_epoch=e,anchor_epoch='SHFE.CU.202002',u_action_eligible=1,score=s) for i,e,s in [(0,'SHFE.CU.202002',10.),(1,'SHFE.CU.202004',2.)]]
        got=self.m.full_choices(parents,children,cal,'holdout_1','CONTROL54','2020-01-01')
        self.assertEqual([r['chosen_action_id'] for r in got],['a1',''])
        self.assertEqual(got[1]['selection_state'],'no_observed_children')
        self.assertEqual(got[0]['scope'],'holdout_1')

    def test_parent_and_child_projection_identity_are_independent(self):
        actions=pd.DataFrame([dict(action_sequence_index=0,action_id='child',mother_sequence_index=9,mother_event_id='parent',actual_epoch='INE.SC.202611',u_date='2020-01-02',u_index=1,product_id='INE.SC',family_id='INE.SC')])
        projection=actions.copy();projection['scalar_primary']='0';projection['missing']='False'
        self.assertEqual(self.m.align_q(actions,projection).tolist(),[0.])
        projection.loc[0,'mother_event_id']='wrong'
        with self.assertRaises(AssertionError):self.m.align_q(actions,projection)

    def test_same_unresolved_action_is_increment_zero_but_different_unknown_is_not(self):
        labels={'a':dict(label_state='open_right_censored',participation_state='',net_R_stress=np.nan,label_known_date=''),'b':dict(label_state='closed_complete_bar_model',participation_state='',net_R_stress=2.,label_known_date='2020-01-01')}
        self.assertEqual(self.m.increment('a','a',labels,'2026-10-16'),(0.,False,True))
        self.assertEqual(self.m.increment('a','b',labels,'2026-10-16'),(None,True,False))

    def test_global_support_requires_finite_positive_weighted_variance(self):
        self.assertEqual(self.m.q_statistics([np.nan],[1.])['reason'],'no_finite_q')
        self.assertFalse(self.m.q_statistics([0.,0.],[1.,2.])['ready'])
        self.assertTrue(self.m.q_statistics([0.,1.],[1.,2.])['ready'])

    def test_completed_financial_terminal_uses_book_replays_carrier(self):
        terminal=dict(status='completed',cash_accounts_started=8,new_cash_accounts=8,raw_ledgers_checkpointed=8,native_source_queries=0,new_labels=0,old_control_book_replays=0,no_automatic_resume=True)
        self.m.financial_completion(terminal)
        terminal['raw_ledgers_checkpointed']=7
        with self.assertRaises(AssertionError):self.m.financial_completion(terminal)

    def test_choice_disclosure_uses_actual_column_not_boundary_only_flag(self):
        frame=pd.DataFrame(dict(account_deadline_certified=['False'],voluntary_policy_version=['stage155_voluntary_reselect_lead_months_1_v1_not_certified']))
        self.m.selection_disclosure(frame)
        frame.loc[0,'account_deadline_certified']='True'
        with self.assertRaises(AssertionError):self.m.selection_disclosure(frame)

    def test_gate_requires_strict_primary_and_preserves_unknown_held_and_DD(self):
        points={(w,c):dict(active_total_return_pct=1.,return_percentage_point_difference=1.,drawdown_percentage_point_difference=1.,ci95_low=.01) for w in self.m.WINDOWS for c in self.m.COSTS}
        held=dict(groups={g:dict(known_u_equal_mean_increment_R=0.,nominal_pass=True,unknown_differential_selected_events=0,status='supported') for g in ('holdout_0','holdout_1')})
        self.assertTrue(self.m.fixed_gate(points,held,False,True,False)['nominal_pass'])
        held['groups']['holdout_1']['unknown_differential_selected_events']=1
        self.assertEqual(self.m.fixed_gate(points,held,False,True,False)['status'],'unknown_differential_held_outcome')
        points['primary_2020','stress']['return_percentage_point_difference']=0.
        self.assertFalse(self.m.fixed_gate(points,held,False,True,False)['cash_nominal_pass'])
        points['cold_2023','base']['drawdown_percentage_point_difference']=None
        self.assertEqual(self.m.fixed_gate(points,held,False,True,False)['status'],'unknown_control_drawdown')

    def test_vector_complete_selection_agrees_with_independent_rows_and_F_priority(self):
        cal=['2020-01-02','2020-01-03','2020-02-03','2020-03-02']
        parents=[dict(sequence_index=i,event_id='p'+str(i),product_id=p,family_id='SHFE.CU',u_date=cal[0],u_index=0,reference_epoch=p+'.202004') for i,p in [(9,'SHFE.CU'),(2,'SHFE.CU_F')]]
        children=[dict(sequence_index=i,action_id='a'+str(i),mother_sequence_index=p['sequence_index'],mother_event_id=p['event_id'],product_id=p['product_id'],family_id=p['family_id'],u_date=cal[0],u_index=0,reference_epoch=p['reference_epoch'],anchor_epoch=p['reference_epoch'],u_action_eligible=1,score=score) for i,(p,score) in enumerate(zip(parents,[1.,99.]))]
        bounds={a['reference_epoch']:self.m.reuse().deadline(a['reference_epoch'],cal,'2026-10-16') for a in children}
        vector=self.m.vector_choices(pd.DataFrame(parents),pd.DataFrame(children),bounds,cal,'main','CONTROL54','2020-01-01')
        rows=self.m.full_choices(parents,children,cal,'main','CONTROL54','2020-01-01')
        self.assertEqual(vector.chosen_action_id.tolist(),[r['chosen_action_id'] for r in rows])
        self.assertEqual(vector.chosen_action_id.tolist(),['a0',''])

    def test_numpy_nested_union_endpoints_have_identical_decimal_JSON(self):
        intervals=[[np.int64(2),np.int64(7)],[np.int64(11),np.int64(12)]]
        encoded=self.m.interval_json(intervals)
        self.assertEqual(encoded,'[[2,7],[11,12]]')
        self.assertEqual(json.loads(encoded),[[2,7],[11,12]])


if __name__=='__main__':unittest.main()
