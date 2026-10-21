"""Synthetic Stage496 checks only; no historical source or financial input reads."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd


class IdentityResidual(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p=Path(__file__).with_name('stage496_member_identity_residual.py')
        spec=importlib.util.spec_from_file_location('new496',p)
        cls.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.m)

    def vector(self,name,qty):
        return dict(member_id='',member_name=name,qty_state='valid',qty=qty,rank=1,source_row=0)

    def test_identity_permutation_changes_signed_not_anonymous(self):
        a=self.m.disclosed_observation('SHFE',[self.vector('甲',8),self.vector('乙',2)],
            [self.vector('甲',2),self.vector('乙',8)])
        b=self.m.disclosed_observation('SHFE',[self.vector('乙',8),self.vector('甲',2)],
            [self.vector('乙',2),self.vector('甲',8)])
        vocab=self.m.train_vocabulary([a,b]);za,ba=self.m.encode_observations([a],vocab);zb,bb=self.m.encode_observations([b],vocab)
        self.assertTrue(np.array_equal(ba,bb));self.assertTrue(np.allclose(za,-zb))
        self.assertEqual(a['signed_total'],b['signed_total'])
        self.assertEqual(self.m.member_token('SHFE','甲','123'),self.m.member_token('SHFE','甲','999'))
        self.assertNotEqual(self.m.member_token('SHFE','','123'),self.m.member_token('SHFE','123',''))
        self.assertNotEqual(self.m.member_token('SHFE','甲',''),self.m.member_token('INE','甲',''))

    def test_oov_and_unavailable_share_fallback(self):
        seen=self.m.disclosed_observation('SHFE',[self.vector('甲',8)],[self.vector('乙',2)])
        unseen=self.m.disclosed_observation('SHFE',[self.vector('新甲',8)],[self.vector('新乙',2)])
        vocab=self.m.train_vocabulary([seen]);z,b=self.m.encode_observations([unseen],vocab)
        self.assertTrue(np.array_equal(z,np.zeros((1,2))));self.assertEqual(b.shape,(1,2))
        head=dict(vocabulary=vocab,coef_B=[1,0],coef_C=[2,-2])
        score,states=self.m.apply_head(np.array([4.,5.,6.]),[seen,unseen,None],head,'C_MEMBER_IDENTITY')
        self.assertEqual(score[1],6.);self.assertEqual(score[2],6.)
        self.assertEqual(states[-1],'source_missing_fallback_A')
        with self.assertRaises(ValueError):self.m.disclosed_observation('SHFE',[],[])

    def test_sumzero_ridge_and_df_bound(self):
        observations=[self.m.disclosed_observation('SHFE',[self.vector('甲',k),self.vector('乙',10-k)],
            [self.vector('丙',3),self.vector('丁',7)]) for k in [1,3,6,9]]
        vocab=self.m.train_vocabulary(observations);z,b=self.m.encode_observations(observations,vocab);w=np.array([1,2,3,4.])/10
        head=self.m.fit_residual_heads(z,b,np.array([-.4,1.2,-.7,1.]),w)
        beta=np.array(head['coef_C']);self.assertAlmostEqual(beta.sum(),0.,places=12)
        self.assertLessEqual(head['identity_df'],1.+1e-12);self.assertLessEqual(head['identity_trace_gram'],1.+1e-12)
        residual=np.array([-.4,1.2,-.7,1.])-b@head['coef_B'];P=np.array(head['null_basis'])@np.array(head['null_basis']).T
        self.assertTrue(np.allclose(P@(z.T@(w*(z@beta-residual))+beta),0.,atol=1e-12))
        self.assertEqual(head['weight_sum'],1.)

    def test_support_rejects_only_anonymous_direction(self):
        z=np.array([[.1,-.1],[-.2,.2],[.1,-.1]])
        b=np.column_stack([np.ones(3),z[:,0]])
        result=self.m.identity_support(z,b,np.ones(3)/3)
        self.assertFalse(result['ready']);self.assertEqual(result['reason'],'no_identity_direction_beyond_B')
        b=np.column_stack([np.ones(3),np.zeros(3)])
        result=self.m.identity_support(z,b,np.ones(3)/3)
        self.assertTrue(result['ready'])

    def test_strict_train_identity_maturity_and_holdout(self):
        f=pd.DataFrame(dict(u_date=['2019-01-01']*4+['2020-01-01'],
            label_known_date=['2019-12-31','2020-01-01','','2019-12-31','2020-01-02'],
            label_state=['closed_complete_bar_model']*5,net_R_stress=[1.]*5,u_action_eligible=[1,1,1,0,1],
            source_observed=[True]*5,pre_domain=[True]*5,family_id=['a']*5))
        self.assertEqual(self.m.training_slice(f,'2020-01-01','main').index.tolist(),[0])
        f.loc[0,'family_id']='held';g=self.m.family_group('held')
        self.assertTrue(self.m.training_slice(f,'2020-01-01','holdout_'+str(g)).empty)

    def test_nochild_product_is_kept_in_policy_but_not_required_in_actions(self):
        canonical={'x':'x','x_F':'x','never_listed':'never_listed'}
        report=self.m.validate_action_domain(7,4,{'x'},{'x'},canonical,expected_rows=7,expected_forward=4)
        self.assertEqual(report['observed_child_products'],1)
        self.assertEqual(report['canonical_policy_products'],3)
        self.assertEqual(report['policy_products_without_observed_children'],['never_listed','x_F'])
        with self.assertRaises(ValueError):self.m.validate_action_domain(7,4,{'foreign'},{'foreign'},canonical,expected_rows=7,expected_forward=4)
        with self.assertRaises(ValueError):self.m.validate_action_domain(6,4,{'x'},{'x'},canonical,expected_rows=7,expected_forward=4)

    def test_complete_policy_keeps_missing_and_nochild_mothers(self):
        f=pd.DataFrame(dict(sequence_index=[10,11,12],event_id=['a','b','c'],product_id=['x','x_F','z'],family_id=['x','x','z'],
            u_date=['2020-01-02']*3,u_index=[1,1,1],reference_epoch=['x.202003','','z.202003']))
        calendar=['2020-01-01','2020-01-02','2020-01-03','2020-02-03']
        row=dict(sequence_index='5',action_id='action:5',mother_sequence_index='10',mother_event_id='a',product_id='x',family_id='x',
            u_date='2020-01-02',u_index='1',reference_epoch='x.202003',anchor_epoch='x.202003',u_action_eligible='1',score='2.5',scope='main',cutoff='2020-01-01')
        acc=self.m.h().ChoiceAccumulator(f,calendar,'main');acc.observe(row);picked=acc.finish('C_MEMBER_IDENTITY')
        self.assertEqual(len(picked),3);self.assertEqual(picked.selected.tolist(),[1,0,0])
        self.assertEqual(picked.selection_state.tolist(),['selected','no_observed_children','no_observed_children'])

    def test_exact_predecessor_not_last_success_and_no_alias(self):
        calendar=['2020-01-01','2020-01-02','2020-01-03'];lookup={('2020-01-01','SHFE.CU.202003'):{'x':1}}
        self.assertEqual(self.m.lookup_exact('2020-01-02',1,'SHFE.CU.202003',calendar,lookup),{'x':1})
        self.assertIsNone(self.m.lookup_exact('2020-01-03',2,'SHFE.CU.202003',calendar,lookup))
        self.assertIsNone(self.m.lookup_exact('2020-01-02',1,'SHFE.CU_F.202003',calendar,lookup))
        with self.assertRaises(ValueError):self.m.lookup_exact('2020-01-03',1,'SHFE.CU.202003',calendar,lookup)


if __name__=='__main__':unittest.main()
