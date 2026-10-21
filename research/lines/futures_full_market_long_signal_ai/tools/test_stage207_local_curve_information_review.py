"""Only independent new equation ordering and held unknown semantics; no actual I/O."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

spec=importlib.util.spec_from_file_location('review207',Path(__file__).with_name('stage207_local_curve_information_review.py'))
review=importlib.util.module_from_spec(spec); spec.loader.exec_module(review)

class ReviewFixtures(unittest.TestCase):
    def test_new_q_row_and_intercept_mapping_match_direct_weighted_equations(self):
        raw=np.arange(130,dtype=float).reshape(5,26)/100.; raw[2,3]=np.nan
        q=np.array([-2.,0.,np.nan,1.,3.]); w=np.array([1.,2.,3.,4.,5.]); y=np.array([3.,-1.,2.,0.,4.])
        scaler=dict(mean=[0.]*26,scale=[1.]*26); qs=review.q_stats(q,w)
        finite=np.isfinite(raw); base=np.column_stack((np.where(finite,raw,0.),(~finite).astype(float)))
        known=np.isfinite(q); zq=np.zeros(5); zq[known]=(q[known]-qs['mean'])/qs['scale']
        old=np.column_stack((base,np.ones(5))); lhs=old.T@(w[:,None]*old); lhs[np.arange(52),np.arange(52)]+=1
        row,rhsq=review.q_equations(raw,q,w,y,scaler,qs)
        actual,actual_rhs=review.inherited_equations(lhs,old.T@(w*y),row,rhsq)
        direct=np.column_stack((base,zq,np.ones(5))); expected=direct.T@(w[:,None]*direct)
        expected[np.arange(53),np.arange(53)]+=1
        np.testing.assert_allclose(actual,expected,rtol=1e-13,atol=1e-13)
        np.testing.assert_allclose(actual_rhs,direct.T@(w*y),rtol=1e-13,atol=1e-13)
        self.assertEqual(actual[53,53],w.sum())
        self.assertEqual(zq[2],0.)

    def test_same_unknown_zero_disclosed_distinct_unknown_not_filled_zero(self):
        actions=pd.DataFrame([
            dict(action_id='shared',label_state='open',participation_state='observed',net_R_stress=np.nan,label_known_date=''),
            dict(action_id='unresolved',label_state='open',participation_state='observed',net_R_stress=np.nan,label_known_date=''),
            dict(action_id='win',label_state='closed_complete_bar_model',participation_state='observed',net_R_stress=2.,label_known_date='2025-01-03')])
        def row(seq,f,u,chosen): return dict(sequence_index=seq,family_id=f,u_index=u,
            u_date='2025-01-0'+str(u),selected=int(bool(chosen)),chosen_action_id=chosen)
        control=[row(0,'f1',1,'shared'),row(1,'f2',1,'unresolved'),row(2,'f3',2,''),row(3,'f1',1,'')]
        candidate=[row(0,'f1',1,'shared'),row(1,'f2',1,'win'),row(2,'f3',2,'win'),row(3,'f1',1,'')]
        result,days=review.held_diagnostic(control,candidate,actions)
        self.assertEqual(result['full_family_u'],3); self.assertEqual(result['known_increment_family_u'],2)
        self.assertEqual(result['unknown_differential_selected_events'],1)
        self.assertEqual(result['common_unresolved_same_action'],1)
        self.assertEqual(result['known_u_equal_mean_increment_R'],1.)
        self.assertFalse(result['nominal_pass']); self.assertEqual(days.unknown_family_u.tolist(),[1,0])

if __name__=='__main__': unittest.main()
