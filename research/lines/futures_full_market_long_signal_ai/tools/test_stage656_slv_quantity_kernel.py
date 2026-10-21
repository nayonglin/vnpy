"""Only new frozen653 behaviors, all synthetic; no historical files."""
import importlib.util
import math
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

PATH=Path(__file__).with_name('stage656_slv_quantity_kernel.py')
def kernel(test):
    test.assertTrue(PATH.exists(), 'new frozen653 behavior is not implemented')
    spec=importlib.util.spec_from_file_location('slv656_kernel_test',PATH);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def row(date,shares,nav,i):
    return dict(date=date,source_sheet='Historical',source_row_1based=str(i),as_of_literal=date,shares_outstanding_literal=str(shares) if shares is not None else '--',shares_outstanding_parsed=str(shares) if shares is not None else '',missing_state='observed_numeric' if shares is not None else 'missing_literal_double_dash',nav_per_share_literal=str(nav),ex_dividends_literal='--')

class Frozen653Behavior(unittest.TestCase):
    def test_clock_counts_full_weekdays_with_DST_not_exchange_sessions(self):
        k=kernel(self)
        self.assertEqual(k.assumed_available_at('2024-03-08').isoformat(),'2024-03-13T00:00:00-04:00')
        self.assertEqual(k.assumed_available_at('2024-11-04').isoformat(),'2024-11-07T00:00:00-05:00')
        # Monday Christmas still counts as a weekday; no NYSE holiday claim.
        self.assertEqual(k.assumed_available_at('2023-12-22').date().isoformat(),'2023-12-27')

    def test_adjacent_original_missing_weekend_clears_latest_pair(self):
        k=kernel(self);src=[row('2024-03-09',None,11,2),row('2024-03-08',110,11,3),row('2024-03-07',100,10,4),row('2024-03-06',90,9,5)]
        pairs=k.build_source_pairs(src);mapping=k.map_source_to_calendar(pairs,['2024-03-12','2024-03-13'])
        self.assertEqual(len(pairs),4);self.assertEqual(pairs.date.tolist(),['2024-03-06','2024-03-07','2024-03-08','2024-03-09'])
        self.assertTrue(mapping.iloc[0].pair_valid);self.assertEqual(mapping.iloc[0].source_date,'2024-03-07')
        self.assertFalse(mapping.iloc[1].pair_valid);self.assertEqual(mapping.iloc[1].source_date,'2024-03-09')
        self.assertEqual(pairs.iloc[-1].previous_date,'2024-03-08')
        self.assertAlmostEqual(pairs.iloc[2].P,math.log(1.1));self.assertTrue(math.isnan(pairs.iloc[3].P))

    def test_source_weights_nested_scale_and_intercept_ridge_hand_equation(self):
        k=kernel(self)
        t=pd.DataFrame(dict(Ahat=[-1.,0.,1.,2.,3.],P=[.1,.1,-.2,-.2,-.2],Q=[.3,.3,-.4,-.4,-.4],sample_weight=[1.,3.,2.,1.,1.],source_id=['a','a','b','b','b'],pair_valid=[True]*5,net_R_stress=[1.,2.,-1.,4.,2.]))
        calls=[];heads=k.fit_heads(t,'main','2020-01-01',calls.append)
        w=np.array([.25,.75,.5,.25,.25]);self.assertEqual(calls,['B','C']);self.assertAlmostEqual(w.sum(),2.)
        np.testing.assert_allclose(k.source_group_weights(t.sample_weight,t.source_id),w)
        raw=np.column_stack([t.Ahat,t.P,t.Ahat*t.P,t.Q,t.Ahat*t.Q]);mean=np.average(raw,axis=0,weights=w);scale=np.sqrt(np.average((raw-mean)**2,axis=0,weights=w));scale[scale==0]=1
        for arm,n in [('B',3),('C',5)]:
            h=heads[arm];z=np.column_stack([np.ones(5),(raw[:,:n]-mean[:n])/scale[:n]]);G=z.T@(w[:,None]*z);rhs=z.T@(w*(t.net_R_stress-t.Ahat));pen=np.diag([0.]+[1.]*n);beta=np.linalg.solve(G+pen,rhs)
            np.testing.assert_allclose(h['feature_mean'],mean[:n],rtol=0,atol=1e-15);np.testing.assert_allclose(h['feature_scale'],scale[:n],rtol=0,atol=1e-15);np.testing.assert_allclose([h['intercept']]+h['coef'],beta,rtol=1e-12,atol=1e-12)
            self.assertAlmostEqual(h['weight_sum'],2.);self.assertEqual(h['source_groups'],2)
        self.assertEqual(heads['B']['feature_mean'],heads['C']['feature_mean'][:3]);self.assertEqual(heads['B']['feature_scale'],heads['C']['feature_scale'][:3])

    def test_invalid_prediction_is_bitwise_A_and_active_state_interactions_apply(self):
        k=kernel(self);base=np.array([-0.,2.,3.]);head=dict(feature_mean=[0.]*5,feature_scale=[1.]*5,feature_names=['Ahat','P','Ahat*P','Q','Ahat*Q'],intercept=1.,coef=[1.,2.,3.,4.,5.])
        score=k.predict_scores(base,np.array([np.nan,.1,.2]),np.array([np.nan,.2,.3]),[False,True,False],head)
        self.assertEqual(score[0].view(np.uint64),base[0].view(np.uint64));self.assertEqual(score[2],base[2]);self.assertAlmostEqual(score[1],2+1+2+.2+.6+.8+2.)

    def test_identical_unknown_difference_zero_different_unknown_stays_unknown_and_shared_indices(self):
        k=kernel(self)
        cs=[]
        for arm,chosen in [('A',['x','x','']),('B',['x','','']),('C',['x','z',''])]:
            for j,c in enumerate(chosen):cs.append(dict(scope='main',cutoff='2020-01-01',arm=arm,event_id=f'm{j}',product_id='p',family_id='f',u_date='2020-01-02' if j<2 else '2020-01-03',u_index=0 if j<2 else 1,selected=bool(c),chosen_action_id=c))
        forward=pd.DataFrame([dict(scope='main',cutoff='2020-01-01',action_id=a,u_index=0,u_date='2020-01-02',u_action_eligible=1,score=1.,B_score=1.,C_score=1.,label_state='unknown',participation_state='unknown',net_R_stress=np.nan,label_known_date='') for a in ['x','z']])
        mapping=pd.DataFrame([dict(u_index=j,u_date=d,source_id='s'+str(j),source_date=d,pair_valid=True) for j,d in enumerate(['2020-01-02','2020-01-03'])])
        r=k.policy_statistics(pd.DataFrame(cs),forward,mapping,['2020-01-02','2020-01-03'])
        groups=r['group_stats'];a=groups[(groups.scope=='main')&(groups.era=='early')].set_index('source_id')
        self.assertEqual(a.loc['s0','C_minus_B_identified'],1);self.assertEqual(a.loc['s0','C_minus_B_unknown'],1);self.assertEqual(a.loc['s0','C_minus_B_mean'],0.)
        self.assertEqual(a.loc['s1','C_mean'],0.);self.assertEqual(r['indices']['early'].shape,(2000,2));self.assertTrue(np.all((r['indices']['early']>=0)&(r['indices']['early']<2)))
        self.assertEqual(r['grids']['early'],['s0','s1']);self.assertFalse(r['gate']['passed'])

if __name__=='__main__':unittest.main()
