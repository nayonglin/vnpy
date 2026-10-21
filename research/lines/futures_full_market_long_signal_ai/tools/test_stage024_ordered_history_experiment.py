"""Five behavioral fixtures; never loads market data or starts annual fits."""
import importlib.util
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

SPEC = importlib.util.spec_from_file_location('stage024', Path(__file__).with_name('stage024_ordered_history_experiment.py'))
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class FixedInformationBehavior(unittest.TestCase):
    def test_training_requires_mature_labels_and_excludes_entire_family_group(self):
        # A missing maturity clause would incorrectly admit b; splitting by product would admit d.
        families = [next(f'x{i}' for i in range(20) if m.family_group(f'x{i}') == group) for group in (0, 1)]
        f = pd.DataFrame(dict(event_id=list('abcde'), feature_ready=[1,1,1,1,0], label_identified=[1,1,0,1,1],
            u_date=['2019-01-01']*5, label_known_date=['2019-01-02','2020-01-02','','2019-01-02','2019-01-02'],
            family_id=[families[1],families[1],families[1],families[0],families[1]]))
        self.assertEqual(m.training_slice(f, '2020-01-02', 0).event_id.tolist(), ['a'])

    def test_channel_pooling_and_tuple_bag_keep_weighted_permutation_geometry(self):
        # Lag-specific scaling or sorting channels independently breaks the checked multiset/norm.
        s = np.zeros((2,11)); s[:,0] = [0,4]
        q = np.zeros((2,20,4)); q[0,:,:] = [0,1,2,3]; q[1,:,:] = [4,5,6,7]
        q[0,0] = [2,3,4,5]; q[0,1] = [-2,-1,0,1]
        scalers = m.fit_scalers(s, q, np.array([1.,3.]))
        self.assertAlmostEqual(scalers['S']['mean'][0], 3.)
        self.assertAlmostEqual(scalers['S']['var'][0], 3.)
        np.testing.assert_allclose(scalers['block']['mean'], [3,4,5,6], rtol=0, atol=1e-14)
        np.testing.assert_allclose(scalers['block']['var'], [3.1]*4, rtol=0, atol=1e-14)
        bag=m.canonical_bag(q)
        self.assertEqual(bag[0,0].tolist(), [-2,-1,0,1])
        self.assertEqual(bag[0,-1].tolist(), [2,3,4,5])
        mean=np.asarray(scalers['block']['mean']); scale=np.asarray(scalers['block']['scale'])
        np.testing.assert_allclose(np.sum(((q-mean)/scale)**2,axis=(1,2)), np.sum(((bag-mean)/scale)**2,axis=(1,2)),atol=1e-12)

    def test_rff_uses_shared_directions_with_active_dimension_bandwidth(self):
        # Using 91 for S or consuming a second RNG stream changes this independent cosine calculation.
        mapping=m.make_mapping()
        rng=np.random.default_rng(20261018); w=rng.normal(size=(91,128)); b=rng.uniform(0,2*np.pi,size=128)
        np.testing.assert_array_equal(mapping['W_base'],w); np.testing.assert_array_equal(mapping['b'],b)
        s=np.arange(22,dtype=float).reshape(2,11)/10
        q=np.arange(160,dtype=float).reshape(2,20,4)/100
        scalers={'S':{'mean':[0.]*11,'scale':[1.]*11},'block':{'mean':[0.]*4,'scale':[1.]*4}}
        head=m.feature_head(s,q,'S',scalers,mapping)
        expected=np.sqrt(2/128)*np.cos(s@(w[:11]/np.sqrt(11))+b)
        np.testing.assert_allclose(head[:,:11],s,atol=0); np.testing.assert_allclose(head[:,11:],expected,atol=1e-14)
        order=m.feature_head(s,q,'ORDER',scalers,mapping)
        expected=np.sqrt(2/128)*np.cos(np.column_stack([s,q.reshape(2,80)])@(w/np.sqrt(91))+b)
        np.testing.assert_allclose(order[:,11:],expected,atol=1e-14)

    def test_same_masks_cancel_ambiguous_interval_and_unknowns_leave_empty_dates(self):
        # Independent marginal subtraction would give a width-5 penalty for the first common mask.
        p=pd.DataFrame(dict(u_date=['2020-01-02']*3+['2020-01-03'],label_identified=[1,1,1,0],
            proxy_lower=[-1.2,-1.2,3.8,np.nan],proxy_upper=[3.8,-1.2,3.8,np.nan],
            pred_ORDER=[1,-1,-1,1],pred_S=[1,1,-1,1],pred_BAG=[-1,-1,1,1]))
        d=m.daily_metrics(p,['2020-01-02','2020-01-03'])
        self.assertAlmostEqual(d.loc['2020-01-02','ORDER_minus_S_lower'],.4)
        self.assertAlmostEqual(d.loc['2020-01-02','ORDER_minus_S_upper'],.4)
        self.assertAlmostEqual(d.loc['2020-01-02','ORDER_minus_BAG_lower'],-5/3)
        self.assertAlmostEqual(d.loc['2020-01-02','ORDER_minus_BAG_upper'],0)
        self.assertTrue(d.loc['2020-01-03'].isna().all())

    def test_saved_coefficients_replay_with_exact_training_ids_and_date_weights(self):
        # Rebuilding a scaler at prediction time or losing coefficient precision breaks this replay.
        n=9; f=pd.DataFrame({name:np.arange(n,dtype=float)/(j+2) for j,name in enumerate(m.OWN)})
        f['event_id']=[f'e{i}' for i in range(n)]; f['u_date']=['2019-01-01']*3+['2019-01-02']*6
        f['label_known_date']=['2019-01-03']*n; f['family_id']='X';f['sequence_index']=np.arange(n)
        f['proxy_lower']=np.array([-1.2,-1.2,3.8,-1.2,.4,3.8,-1.2,-1.2,3.8])
        q=np.arange(n*80,dtype=float).reshape(n,20,4)/200
        mapping=m.make_mapping(); before=m.FIT_CALLS
        rec=m.fit_one(f,q,'ORDER','fixture','2020-01-02',None,mapping)
        self.assertEqual(m.FIT_CALLS-before,1)
        saved=json.loads(json.dumps(rec,allow_nan=False)); pred=m.predict_from_record(saved,f,q,mapping)
        s=f[m.OWN].to_numpy(float); sm=np.array(saved['scalers']['S']['mean']); ss=np.array(saved['scalers']['S']['scale'])
        qm=np.array(saved['scalers']['block']['mean']); qs=np.array(saved['scalers']['block']['scale'])
        z=np.column_stack([(s-sm)/ss,((q-qm)/qs).reshape(n,80)])
        h=np.column_stack([(s-sm)/ss,np.sqrt(2/128)*np.cos(z@(mapping['W_base']/np.sqrt(91))+mapping['b'])])
        expected=h@np.asarray(saved['coef'])+saved['intercept']
        np.testing.assert_allclose(pred,expected,rtol=0,atol=1e-14)
        self.assertEqual(saved['training_ids'],[f'e{i}' for i in range(n)])
        np.testing.assert_allclose(saved['training_weights'],[1.5]*3+[.75]*6,atol=0)
        self.assertEqual(saved['max_label_known_date'],'2019-01-03')


if __name__=='__main__': unittest.main()
