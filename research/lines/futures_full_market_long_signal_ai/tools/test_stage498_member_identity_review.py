"""Small independent audit boundaries; no real data or estimator/cash kernel."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd


class IndependentReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p=Path(__file__).with_name('stage498_member_identity_review.py')
        spec=importlib.util.spec_from_file_location('tiny_independent498',p)
        cls.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.m)

    def test_roundtrip_tolerance_and_weight_conservation(self):
        self.m.eq([1.,np.nan],[1.+4e-16,np.nan],'tiny serialization')
        with self.assertRaises(AssertionError):self.m.eq([1.],[1.1],'material mismatch')
        frame=pd.DataFrame(dict(family_id=['A','A','B'],u_date=['2020-01-02']*2+['2020-01-03'],entry_index=[1,1,2],exit_index=[3,3,4]))
        weights,mean1=self.m.independent_weights(frame)
        self.assertTrue(np.allclose(weights,[.25,.25,.5]));self.assertAlmostEqual(weights.sum(),1.)
        self.assertAlmostEqual(mean1.mean(),1.)

    def test_full_mothers_nochild_and_ordinary_F_priority(self):
        calendar=['2020-01-02','2020-01-03','2020-02-03']
        mothers=pd.DataFrame([dict(sequence_index=i,event_id='m'+str(i),product_id=p,family_id=f,u_date=calendar[0],u_index=0,reference_epoch=p+'.202003')
            for i,(p,f) in enumerate([('SHFE.X','SHFE.X'),('SHFE.X_F','SHFE.X'),('DCE.N','DCE.N')])])
        acc=self.m.Choices(mothers,'main',calendar)
        for i in [0,1]:
            p=mothers.iloc[i];row=dict(sequence_index=str(10+i),mother_sequence_index=str(i),mother_event_id=p.event_id,product_id=p.product_id,
                family_id=p.family_id,u_date=p.u_date,u_index='0',reference_epoch=p.reference_epoch,anchor_epoch=p.reference_epoch,
                action_id='a'+str(i),cutoff='2020-01-01',u_action_eligible='1')
            acc.observe(row,.1 if i==0 else 9.)
        result=acc.finish();self.assertEqual(len(result),3)
        self.assertEqual(result.selected.tolist(),[1,0,0]);self.assertEqual(result.selection_state.iloc[2],'no_observed_children')
        self.assertEqual(result.selection_state.iloc[1],'family_priority_suppressed')

    def test_held_same_unknown_cancels_different_unknown_is_not_zero(self):
        base=pd.DataFrame(dict(family_id=['A','B'],u_index=[1,1],u_date=['2020-01-02']*2,selected=[1,1],chosen_action_id=['same','left']))
        other=base.copy();other.loc[1,'chosen_action_id']='right'
        labels=pd.DataFrame(dict(action_id=['same','left','right'],participation_state=['unknown']*3,label_state=['open_at_sample_end']*3,
            label_known_date=['']*3,net_R_stress=[np.nan]*3))
        result,daily=self.m.held_pair(base,other,labels)
        self.assertEqual(result['unknown_differential_selected_events'],1)
        self.assertEqual(result['same_selected_outcome_not_loaded_cancelled'],1)
        self.assertEqual(result['known_increment_family_u'],1)
        self.assertEqual(result['known_u_equal_mean_increment_R'],0.)
        self.assertEqual(result['status'],'unknown');self.assertEqual(daily.unknown_family_u.tolist(),[1])


if __name__=='__main__':unittest.main()
