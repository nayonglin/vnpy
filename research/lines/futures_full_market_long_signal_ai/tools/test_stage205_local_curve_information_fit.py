"""Only new53 train-statistic, imputation and gate semantics; zero physical fit."""
import importlib.util
import io
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

spec=importlib.util.spec_from_file_location('fixture_stage205',Path(__file__).with_name('stage205_local_curve_information_fit.py'))
fit=importlib.util.module_from_spec(spec); spec.loader.exec_module(fit)


class NewCurve53Fixtures(unittest.TestCase):
    def test_cached_17g_roundtrip_preserves_accepted_labels_and_weights_exactly(self):
        rng=np.random.default_rng(204)
        # Source labels first use the unchanged original130 pd.to_numeric path.
        labels=pd.to_numeric(pd.Series(rng.normal(size=1000).astype(str))).to_numpy(float)
        weights=pd.to_numeric(pd.Series(rng.uniform(.1,3.,size=1000).astype(str))).to_numpy(float)
        original=pd.DataFrame({field:np.arange(1000) for field in fit.NUMERIC})
        original['net_R_stress']=labels; original['sample_weight']=weights
        original['action_id']=['action_'+str(i) for i in range(1000)]
        text=original.to_csv(index=False,float_format='%.17g')
        cached=pd.read_csv(io.StringIO(text),dtype=str,keep_default_na=False,float_precision='round_trip')
        restored=fit.parse_cached_numeric(cached)
        np.testing.assert_array_equal(restored.net_R_stress.to_numpy(),labels)
        np.testing.assert_array_equal(restored.sample_weight.to_numpy(),weights)
        for field in fit.NUMERIC:
            np.testing.assert_array_equal(restored[field].to_numpy(),original[field].to_numpy())
        np.testing.assert_array_equal(restored.action_id.to_numpy(),original.action_id.to_numpy())

    def test_weighted_finite_train_only_not_future_or_missing_mass(self):
        all_q=np.array([-2.,0.,np.nan,99999.])
        train=np.array([0,1,2]); weights=np.array([1.,3.,900.])
        stats=fit.q_statistics(all_q[train],weights)
        self.assertTrue(stats['ready'])
        self.assertEqual(stats['mean'],-.5); self.assertEqual(stats['var'],.75)
        self.assertEqual(stats['finite_weight_sum'],4.)
        self.assertEqual(stats['missing_weight_sum'],900.)
        self.assertEqual(stats['finite_count'],2)
        self.assertFalse(fit.q_statistics(np.array([2.,2.,np.nan]),weights)['ready'])
        self.assertFalse(fit.q_statistics(np.array([np.nan]*3),weights)['ready'])

    def test_exact53_common_unchanged_missing_q_and_mean_q_both_zero(self):
        old,_=fit.helpers()
        common=np.zeros((4,26)); common[1,0]=np.nan
        scaler={'common':{'mean':[0.]*26,'scale':[1.]*26}}
        train_q=np.array([-2.,0.,np.nan]); stats=fit.q_statistics(train_q,np.array([1.,3.,900.]))
        q=np.array([-2.,np.nan,-.5,0.]); design=fit.design53(common,q,scaler,stats)
        self.assertEqual(design.shape,(4,53))
        np.testing.assert_array_equal(design[:,:52],old.design(common,scaler))
        self.assertEqual(design[1,52],0.); self.assertEqual(design[2,52],0.)
        self.assertEqual(design[0,52],(-2.+.5)/np.sqrt(.75))
        self.assertEqual(design[1,26],1.)  # Only accepted COMMON missing slots exist.
        self.assertTrue(np.isfinite(design).all())

    def test_all_six_strict_direction_models_before_forward_side_effect(self):
        records=[dict(scope=s,cutoff=c,q_coefficient=-.01) for s in fit.SCOPES for c in fit.CUTOFFS]
        calls=[]
        gate,value=fit.gated_forward(records,lambda:calls.append('predict_and_select') or 17)
        self.assertTrue(gate['passed']); self.assertEqual(value,17); self.assertEqual(len(calls),1)
        for rejected in (0.,.01,float('nan'),float('inf'),None):
            changed=[dict(r) for r in records]; changed[-1]['q_coefficient']=rejected
            before=len(calls)
            gate,value=fit.gated_forward(changed,lambda:calls.append('forbidden'))
            self.assertFalse(gate['passed']); self.assertIsNone(value); self.assertEqual(len(calls),before)
        for changed in (records[:5],records[:5]+[records[0]]):
            gate,value=fit.gated_forward(changed,lambda:self.fail('incomplete fit set forecast'))
            self.assertFalse(gate['passed']); self.assertIsNone(value)


if __name__=='__main__': unittest.main()
