"""Four meaningful synthetic behaviors; no real data/pilot/model selection."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

spec=importlib.util.spec_from_file_location('s035',Path(__file__).with_name('stage035_peer_alignment_experiment.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class PeerInformationBehavior(unittest.TestCase):
    def test_maturity_family_exclusion_and_scope_specific_context_binding(self):
        # Missing maturity/family filtering or substituting main context for held both fail.
        families=[next(f'x{i}' for i in range(40) if m.family_group(f'x{i}')==g) for g in (0,1)]
        f=pd.DataFrame({c:[0.,0.,0.] for c in m.OWN})
        f['event_id']=['a','b','c'];f['u_date']='2019-01-01';f['feature_ready']=1;f['label_identified']=1
        f['label_known_date']=['2019-01-02','2020-01-02','2019-01-02'];f['family_id']=[families[1],families[1],families[0]];f['sequence_index']=[0,1,2]
        self.assertEqual(m.training_slice(f,'2020-01-02',0).event_id.tolist(),['a'])
        ctx={scope:np.full((3,9),i+1,dtype=float) for i,scope in enumerate(['main','holdout_0','holdout_1'])}
        x=m.raw_design(f,ctx,'holdout_0','ALIGNED')
        np.testing.assert_array_equal(x[:,11:],np.full((3,8),2.))
        with self.assertRaises(ValueError):m.raw_design(f,{'main':ctx['main']},'holdout_0','ALIGNED')

    def test_common18_and_equal_half_pooled_q_scaler_are_shared(self):
        # Per-arm q scaling, unweighted population variance or a nonconstant COMMON q fails.
        common=np.zeros((2,18));common[:,0]=[0,4];qa=np.array([0.,4.]);qs=np.array([2.,8.]);w=np.array([1.,3.])
        scalers=m.fit_scalers(common,qa,qs,w)
        self.assertEqual(scalers['common18']['mean'][0],3.);self.assertEqual(scalers['common18']['var'][0],3.)
        self.assertEqual(scalers['q']['mean'],4.75);self.assertEqual(scalers['q']['var'],7.9375)
        x=np.column_stack([common,np.zeros(2)]);scaled=m.scale_design(x,scalers)
        np.testing.assert_allclose(scaled[:,-1],[-4.75/np.sqrt(7.9375)]*2,atol=1e-14)
        self.assertEqual(scalers['common18']['scale'][1],1.)

    def test_shared_payoff_same_masks_cancel_and_unknown_day_is_nan(self):
        # Independent marginal subtraction incorrectly penalizes the common ambiguous mask.
        f=pd.DataFrame(dict(u_date=['2020-01-02']*3+['2020-01-03'],label_identified=[1,1,1,0],
            proxy_lower=[-1.2,-1.2,3.8,np.nan],proxy_upper=[3.8,-1.2,3.8,np.nan],
            pred_ALIGNED=[1,-1,-1,1],pred_COMMON=[1,1,-1,1],pred_SHUFFLED=[-1,-1,1,1]))
        d=m.daily_metrics(f,['2020-01-02','2020-01-03'])
        self.assertAlmostEqual(d.loc['2020-01-02','ALIGNED_minus_COMMON_lower'],.4)
        self.assertAlmostEqual(d.loc['2020-01-02','ALIGNED_minus_COMMON_upper'],.4)
        self.assertAlmostEqual(d.loc['2020-01-02','ALIGNED_minus_SHUFFLED_lower'],-5/3)
        self.assertTrue(d.loc['2020-01-03'].isna().all())

    def test_saved_coefficients_replay_fixed_19_slot_ridge_with_date_weights(self):
        # Refit scalers on test or use 009/main context in held predictions changes these scores.
        n=9;f=pd.DataFrame({name:np.arange(n,dtype=float)/(j+2) for j,name in enumerate(m.OWN)})
        f['event_id']=[f'e{i}' for i in range(n)];f['u_date']=['2019-01-01']*3+['2019-01-02']*6
        f['label_known_date']='2019-01-03';f['family_id']='X';f['sequence_index']=np.arange(n);f['proxy_lower']=[-1.2,-1.2,3.8,-1.2,.4,3.8,-1.2,-1.2,3.8]
        ctx={s:np.arange(n*9,dtype=float).reshape(n,9)/(i+10) for i,s in enumerate(['main','holdout_0','holdout_1'])}
        before=m.FIT_CALLS;rec=m.fit_one(f,ctx,'holdout_0','ALIGNED','fixture','2020-01-02',None)
        self.assertEqual(m.FIT_CALLS-before,1);self.assertEqual(len(rec['coef']),19)
        pred=m.predict_from_record(rec,f,ctx)
        raw=np.column_stack([f[m.OWN].to_numpy(float),ctx['holdout_0'][:,:7],ctx['holdout_0'][:,7]])
        common=(raw[:,:18]-rec['scalers']['common18']['mean'])/rec['scalers']['common18']['scale']
        q=(raw[:,-1]-rec['scalers']['q']['mean'])/rec['scalers']['q']['scale']
        expected=np.column_stack([common,q])@rec['coef']+rec['intercept']
        np.testing.assert_allclose(pred,expected,rtol=0,atol=1e-14)
        np.testing.assert_array_equal(m.date_weights(f),[1.5]*3+[.75]*6)

if __name__=='__main__':unittest.main()
