"""Only new log target/domain and 52-column boundaries; no real research inputs."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
PATH=Path(__file__).with_name('stage102_target_math.py')

class TargetMathBoundaries(unittest.TestCase):
    def setUp(self):
        self.assertTrue(PATH.exists(), 'independent target implementation missing')
        spec=importlib.util.spec_from_file_location('target102',PATH)
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)

    def test_cost_units_and_same_sign_but_curvature(self):
        r=self.m.targets(np.array([100.,-90.,1.]),np.array([0.,0.,.125]),np.ones(3,bool))
        np.testing.assert_array_equal(r['valid'],True)
        np.testing.assert_allclose(r['a'],[1.,1.,.5],rtol=0,atol=0)
        np.testing.assert_allclose(r['z'],[100.,-90.,.5],rtol=0,atol=0)
        self.assertGreater(r['z'][:2].mean(),0)
        self.assertLess(r['G'][:2].mean(),0)
        self.assertTrue(np.all(np.sign(r['G'])==np.sign(r['z'])))

    def test_exact_domain_boundary_and_invalid_cost_not_clipped(self):
        r=self.m.targets(np.array([-400.,-401.,-399.,1.,1.,1.]),np.array([0.,0.,0.,-1.,np.inf,np.nan]),np.ones(6,bool))
        np.testing.assert_array_equal(r['valid'],[False,False,True,False,False,False])
        self.assertTrue(np.isnan(r['G'][[0,1,3,4,5]]).all())
        self.assertEqual(r['state'][0],'nonpositive_wealth_factor')

    def test_unmature_future_invalid_remains_null_not_predict_mask(self):
        r=self.m.targets(np.array([1.,-1e9,np.nan]),np.array([0.,-1.,np.nan]),np.array([True,False,False]))
        np.testing.assert_array_equal(r['evaluated'],[True,False,False])
        self.assertTrue(np.isnan(r['a'][1:]).all() and np.isnan(r['z'][1:]).all() and np.isnan(r['G'][1:]).all())
        self.assertEqual(r['state'][1],'not_evaluated')

    def test_invalid_y_preserves_defined_a_but_overflow_a_has_null_z(self):
        r=self.m.targets(np.array([np.nan,1.]),np.array([.125,1e308]),np.ones(2,bool))
        self.assertEqual(r['a'][0],.5)
        self.assertEqual(r['a'][1],0.)
        self.assertTrue(np.isnan(r['z']).all() and np.isnan(r['wealth']).all() and np.isnan(r['G']).all())

    def test_head_is_52_and_missing_only_uses_own_common(self):
        raw=np.array([[3.,np.nan]+[0.]*24,[1.,2.]+[0.]*24])
        out=self.m.head52(raw,{'mean':[1.]*26,'scale':[2.]*26})
        self.assertEqual(out.shape,(2,52));self.assertEqual(out[0,0],1.)
        self.assertEqual(out[0,1],0.);self.assertEqual(out[0,27],1.)
        self.assertEqual(out[1,27],0.)

if __name__=='__main__':unittest.main()
