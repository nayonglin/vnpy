"""Six bounded synthetic checks; no repository market data are opened."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


class FrozenFomc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=Path(__file__).with_name('stage489_fomc_residual_experiment.py')
        spec=importlib.util.spec_from_file_location('new489',path)
        cls.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.m)

    def test_source_mask_preserves_missing_and_rule_unknown(self):
        f=pd.DataFrame(dict(clean_volume=[10,10,0,10],settlement=[100,100,100,100],
            contract_multiplier=[5,5,5,5],source_numerically_verified=[1,1,1,0],
            FF4=[1,np.nan,1,1],SP500=[-1,-1,-1,-1],rule_state=['unknown']*4))
        mask,L,state=self.m.numeric_mask(f)
        self.assertEqual(mask.tolist(),[True,False,False,False])
        self.assertAlmostEqual(L[0],np.log(5000))
        self.assertEqual(state.tolist(),['numeric_valid_conditional','raw_pair_missing','nonpositive_or_nonfinite_VSM','source_not_numeric_verified'])

    def test_event_center_only_pre_domain_no_label_filter(self):
        f=pd.DataFrame(dict(event_id=['e']*4,family_id=['a','a','b','b'],
            L=[1.,3.,10.,100.],feature_mask=[True]*4,pre_domain=[True,True,True,False],
            label_state=['unknown','unknown','closed','closed']))
        x=self.m.center_events(f)
        self.assertTrue(np.allclose(x.L_centered,[1-6,3-6,10-6,100-6]))
        self.assertEqual(x.event_center.iloc[0],6.)
        w=self.m.equal_event_family_weights(f.iloc[:3])
        self.assertTrue(np.allclose(w,[.75,.75,1.5]))

    def test_normal_solve_free_constant_and_zero_scale(self):
        f=pd.DataFrame(dict(L_centered=[0.,0.,0.],FF4=[2.,2.,2.],SP500=[-1.,-1.,-1.]))
        b=self.m.fit_head(f,np.array([1.,2.,3.]),np.ones(3),'B')
        c=self.m.fit_head(f,np.array([1.,2.,3.]),np.ones(3),'C')
        self.assertTrue(np.array_equal(np.array(b['scaler']['scale']),np.ones(3)))
        self.assertAlmostEqual(b['coef'][0],2.)
        self.assertAlmostEqual(c['coef'][0],2.)
        self.assertTrue(np.allclose(self.m.predict_head(f,c),[2,2,2]))
        self.assertEqual(len(c['coef']),6)

    def test_cutoff_maturity_and_hash_holdout_are_strict(self):
        f=pd.DataFrame(dict(u_date=['2019-01-01']*5+['2020-01-01'],
            label_known_date=['2019-12-31','2020-01-01','','2019-12-31','2019-12-31','2020-01-02'],
            label_state=['closed_complete_bar_model']*6,net_R_stress=[1]*6,
            u_action_eligible=[1,1,1,0,1,1],pre_domain=[True]*6,feature_mask=[True]*6,
            family_id=['a','a','a','a','b','a']))
        x=self.m.training_slice(f,'2020-01-01','main')
        self.assertEqual(x.index.tolist(),[0,4])
        x=self.m.training_slice(f,'2020-01-01','holdout_0')
        self.assertTrue(all(self.m.family_group(v)!=0 for v in x.family_id))

    def test_overlay_exact_fallback_all_rows_kept(self):
        rows=pd.DataFrame(dict(action_id=['a','b','c'],score=[-0.,1.23456789012345,-3.],
            scope=['main']*3,cutoff=['2020-01-01']*3))
        features=pd.DataFrame(dict(action_id=['a','b'],feature_mask=[True,False],
            L_centered=[0.,np.nan],FF4=[0.,0.],SP500=[0.,0.]))
        model={'scaler':{'mean':[0,0,0],'scale':[1,1,1]},'coef':[2,0],'arm':'B'}
        result=self.m.overlay_scores(rows,features,{('main','2020-01-01','B'):model},'B')
        self.assertEqual(len(result),3)
        self.assertEqual(result.score.tolist(),[2.,rows.score.iloc[1],-3.])
        self.assertEqual(result.head_state.tolist(),['applied','field_missing_fallback_A','non_event_fallback_A'])

    def test_forward_identity_keeps_unselected_and_empty_epoch(self):
        f=pd.DataFrame(dict(sequence_index=[10,11,12],event_id=['a','b','c'],
            product_id=['x','x_F','z'],family_id=['x','x','z'],u_date=['2020-01-02']*3,
            u_index=[1,1,1],reference_epoch=['x.202003','','z.202003'],selected=[1,0,0]))
        result=self.m.forward_mothers_from_choices(f,expected=3)
        self.assertEqual(len(result),3);self.assertEqual(result.reference_epoch.iloc[1],'')
        self.assertEqual(result.columns.tolist(),self.m.IDENTITY)
        calendar=['2020-01-01','2020-01-02','2020-01-03','2020-02-03']
        row=dict(sequence_index='5',action_id='action:5',mother_sequence_index='10',mother_event_id='a',
            product_id='x',family_id='x',u_date='2020-01-02',u_index='1',reference_epoch='x.202003',
            anchor_epoch='x.202003',u_action_eligible='1',score='2.5',scope='main',cutoff='2020-01-01')
        acc=self.m.ChoiceAccumulator(result,calendar,'main');acc.observe(row);picked=acc.finish('B_PRE_LIQUIDITY')
        old=self.m.load('stage156_voluntary_choices.py').select_full_pool(result.to_dict('records'),[row],calendar,'2026-10-16')
        self.assertEqual(picked.chosen_action_id.tolist(),[r['chosen_action_id'] for r in old['choices']])
        self.assertEqual(picked.selection_state.tolist(),[r['selection_state'] for r in old['choices']])


if __name__=='__main__':unittest.main()
