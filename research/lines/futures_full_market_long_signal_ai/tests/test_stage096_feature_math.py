"""Three pure reviewer boundaries; no actual inputs, fits, SQL or cash."""
from pathlib import Path
import importlib.util,unittest
import numpy as np

PATH=Path(__file__).resolve().parents[1]/'tools/stage096_feature_math.py'

class FeatureMath(unittest.TestCase):
    def setUp(self):
        self.assertTrue(PATH.exists(),'independent096 feature math missing')
        s=importlib.util.spec_from_file_location('independent096_feature_math',PATH);self.m=importlib.util.module_from_spec(s);s.loader.exec_module(self.m)

    def test_bag_preserves_entire_quantized_tuples_and_is_permutation_invariant(self):
        q=np.arange(2*20*4,dtype=np.float32).reshape(2,20,4)
        q[:,::2,0]*=-1
        bag=self.m.canonical_bag(q)
        for a,b in zip(q,bag):self.assertEqual(sorted(map(tuple,a)),list(map(tuple,b)))
        np.testing.assert_array_equal(self.m.canonical_bag(q[:,::-1]),bag)
        self.assertEqual(bag.dtype,np.float64)

    def test_pooled_weights_and_exact_constant_have_no_position_scaler_or_epsilon(self):
        q=np.arange(2*20*4,dtype=np.float32).reshape(2,20,4);q[:,:,1]=np.float32(.2);w=np.array([1/3,7/3])
        s=self.m.channel_stats(q,w)
        flat=q.astype(float).reshape(-1,4);wp=np.repeat(w/20,20)
        for j in (0,2,3):
            mean=np.average(flat[:,j],weights=wp);var=np.average((flat[:,j]-mean)**2,weights=wp)
            self.assertAlmostEqual(s['mean'][j],mean);self.assertAlmostEqual(s['var'][j],var)
        self.assertEqual(s['mean'][1],float(np.float32(.2)));self.assertEqual(s['var'][1],0.);self.assertEqual(s['scale'][1],1.)
        self.assertEqual(s['finite_count'],[40]*4)
        self.assertEqual(self.m.channel_stats(np.empty((0,20,4)),np.empty(0))['scale'],[1.]*4)

    def test_181_head_same_mapping_background_and_standardized_missing_zero(self):
        x=np.arange(52,dtype=float).reshape(2,26);q=np.ones((1,20,4),dtype=np.float32);idx=np.array([0,-1])
        stats=dict(mean=[5.]*4,var=[4.]*4,scale=[2.]*4,finite_count=[20]*4)
        common=dict(mean=[0.]*26,scale=[1.]*26)
        rng=np.random.default_rng(20261018);w=rng.normal(size=(91,128));b=rng.uniform(0,2*np.pi,size=128)
        W,B=self.m.mapping();np.testing.assert_array_equal(W,w);np.testing.assert_array_equal(B,b)
        order=self.m.head(x,q,idx,common,stats,'ORDER',W,B);bag=self.m.head(x,q,idx,common,stats,'BAG',W,B)
        self.assertEqual(order.shape,(2,181));np.testing.assert_array_equal(order[:,:53],bag[:,:53]);np.testing.assert_array_equal(order[1],bag[1])
        z=np.r_[x[1,:11],np.zeros(80)]
        np.testing.assert_allclose(order[1,53:],np.sqrt(2/128)*np.cos(z@(w/np.sqrt(91))+b))
        self.assertEqual(order[1,52],1.)

if __name__=='__main__':unittest.main()
