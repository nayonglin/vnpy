"""Four independent tiny contracts; no market I/O, estimator.fit or old suite."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

path=Path(__file__).with_name('stage239_K_target_review.py')
review=None
if path.exists():
    spec=importlib.util.spec_from_file_location('tiny239',path)
    review=importlib.util.module_from_spec(spec);spec.loader.exec_module(review)


class ReviewContracts(unittest.TestCase):
    def test_copy_parser_and_exact_sameC_reject_missing_or_late_target(self):
        self.assertIsNotNone(review,'independent reviewer has not been implemented')
        binding={'path':'/synthetic/156/manifest.json','bytes':12,'sha256':'synthetic'}
        legacy={'schema':'stage156_voluntary_choices_manifest_v1'}
        accepted={'schema':'stage158_voluntary_independent_review_v1','completed':True,
                  'C':0,'I':0,'M':0,'research_arithmetic_accepted':True,'inputs':{'choice_manifest':binding}}
        terminal={'schema':'stage156_terminal_v1','status':'completed','exit_code':0}
        try:completed=review.control_completed('COMMON52_main',legacy,accepted,binding,terminal)
        except KeyError:completed=False
        self.assertTrue(completed,'accepted156/158 completion evidence does not require a manifest status field')
        a=pd.DataFrame({'net_R_stress':['0.12345678901234567','2',''],
            'timing_state':['closed_before_K','closed_after_K','unknown_after_K'],
            'primary_domain':[1,1,1],'K_stress_known':[1,1,1],
            'K_stress_net_R':['0.12345678901234567','7','9']})
        old,new=review.target_arrays(a)
        self.assertEqual(new[0],old[0]);self.assertEqual(new[1],7);self.assertTrue(np.isnan(old[2]))
        support={'sequence_index':np.array([0,1]),'admissible_mask':np.array([True,True]),
                 'old_weight':np.array([1.,2.]),'new_weight':np.array([1.5,3.])}
        ids,w=review.support_contract(np.array([0,1]),np.array([1,1]),
            ['2019-01-02','2019-02-02'],['2019-01-02','2019-02-01'],[1,1],
            [new[0],new[1]],['after_all_source_close']*2,support,'2020-01-01')
        np.testing.assert_array_equal(ids,[0,1]);np.testing.assert_array_equal(w,[1.5,3.])
        with self.assertRaises(ValueError):
            review.support_contract(np.array([0,1,2]),np.ones(3),['2019-01-02']*3,
                ['2019-01-02']*3,[1]*3,[1.]*3,['after_all_source_close']*3,support,'2020-01-01')
        with self.assertRaises(ValueError):
            review.support_contract(np.array([0,1]),np.array([1,1]),['2019-01-02']*2,
                ['2019-01-02','2020-01-02'],[1,1],[1.,2.],['after_all_source_close']*2,support,'2020-01-01')

    def test_policy_zero_sameunknown_and_distinctunknown_stay_separate(self):
        self.assertIsNotNone(review,'independent reviewer has not been implemented')
        labels={'cancel':{'primary_domain':1,'policy_reward_known':1,'policy_known_date':'2021-01-04',
            'policy_known_phase':'after_all_source_close','K_stress_known':0},
            'unknown':{'primary_domain':1,'policy_reward_known':0,'K_stress_known':0},
            'good':{'primary_domain':1,'policy_reward_known':0,'K_stress_known':1,
                    'K_stress_known_date':'2021-01-05','K_stress_known_phase':'after_all_source_close','K_stress_net_R':3.}}
        self.assertEqual(review.policy_value('',labels),0.)
        self.assertEqual(review.policy_value('cancel',labels),0.)
        self.assertEqual(review.contrast('unknown','unknown',labels),(0.,False,True))
        self.assertEqual(review.contrast('good','unknown',labels),(None,True,False))
        self.assertEqual(review.contrast('good','cancel',labels),(3.,False,False))
        with self.assertRaises(ValueError):review.policy_value('absent',labels)

    def test_cutoff_is_u_date_and_one_unknown_rejects_all_eight_cells(self):
        self.assertIsNotNone(review,'independent reviewer has not been implemented')
        events=[]
        for control in ('DOMAIN52','COMMON52'):
            for scope in ('holdout_0','holdout_1'):
                for day in ('2022-12-30','2023-01-03'):
                    events.append(dict(control=control,scope=scope,u_date=day,family_id='X',
                        delta_R=2.,unknown=False,same_unresolved=False,candidate_selected=1,control_selected=1))
        result,daily=review.held_cells(events)
        self.assertTrue(result['all_eight_pass']);self.assertEqual(len(daily),8)
        self.assertIn('holdout_0/2020-01-01',result['groups']['DOMAIN52'])
        events[-1].update(delta_R=None,unknown=True)
        result,_=review.held_cells(events)
        self.assertFalse(result['all_eight_pass'])
        self.assertEqual(result['groups']['COMMON52']['holdout_1/2023-01-01']['unknown_differential_selected_events'],1)

    def test_rhs_delta_preserves_unpenalized_intercept_and_detects_wrong_beta(self):
        self.assertIsNotNone(review,'independent reviewer has not been implemented')
        H=np.array([[3.,2.],[2.,2.]])
        rhs=np.array([3.,3.])
        h,new_rhs=review.delta_equations(H,rhs,np.array([[1.]]),np.array([2.]),np.array([1.]),np.array([4.]))
        np.testing.assert_array_equal(h,H);np.testing.assert_array_equal(new_rhs,[9.,9.])
        beta=np.linalg.solve(h,new_rhs)
        review.verify_solution(h,new_rhs,beta)
        with self.assertRaises(AssertionError):review.verify_solution(h,new_rhs,beta+np.array([.1,0.]))


if __name__=='__main__':unittest.main()
