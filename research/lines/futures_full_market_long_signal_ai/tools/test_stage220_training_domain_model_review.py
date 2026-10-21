"""Only the new review equation/mask methods; no historical I/O or fit."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np

spec=importlib.util.spec_from_file_location('model_review220',Path(__file__).with_name('stage220_training_domain_model_review.py'))
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class ReviewMethods(unittest.TestCase):
    def test_excluded_52_plus_intercept_loss_matches_direct_retained_equations(self):
        raw=np.arange(5*26,dtype=float).reshape(5,26)/20.;raw[1,2]=np.nan
        scaler={'common':{'mean':[.2]*26,'scale':[2.]*26}}
        x=r.design(raw,scaler);z=np.column_stack((x,np.ones(5)))
        w=np.array([.7,1.2,.3,2.1,.5]);y=np.array([1.,-.2,.3,2.,-1.])
        keep=np.array([True,False,True,False,True]);P=np.diag(np.r_[np.ones(52),0.]);factor=w.sum()/w[keep].sum()
        h0=z.T@(w[:,None]*z)+P;rhs0=z.T@(w*y)
        h,b=r.inherited_equations(h0,rhs0,z[~keep],w[~keep],y[~keep],factor)
        nw=w[keep]*factor
        np.testing.assert_allclose(h,z[keep].T@(nw[:,None]*z[keep])+P,rtol=1e-13,atol=1e-13)
        np.testing.assert_allclose(b,z[keep].T@(nw*y[keep]),rtol=1e-13,atol=1e-13)
        self.assertEqual(h.shape,(53,53));self.assertAlmostEqual(h[-1,-1],w.sum())

    def test_independent_nominal_boundary_mask_without_producer_helpers(self):
        c=['2019-02-27','2019-02-28','2019-03-04','2019-03-05']
        mask=r.training_mask([0,1,2,3],['DCE.a.201904','DCE.a.201904','DCE.a.201905','DCE.a.201902'],c)
        np.testing.assert_array_equal(mask,[True,False,True,False])
        with self.assertRaisesRegex(AssertionError,'unknown source successor'):
            r.training_mask([3],['DCE.a.201905'],c)

if __name__=='__main__':unittest.main()
