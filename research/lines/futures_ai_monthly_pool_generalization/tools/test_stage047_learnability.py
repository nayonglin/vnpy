import unittest
import numpy as np
import pandas as pd
from stage047_learnability import pair_bounds, loss_bounds, split_year, test_gate


class LearnabilityTests(unittest.TestCase):
    def test_unknown_label_bounds_and_paired_tightness(self):
        y=np.array([1.,0.,np.nan]);p=np.array([.8,.3,.8]);q=np.array([.5,.5,.5])
        lo,hi=loss_bounds(y,p,'brier')
        np.testing.assert_allclose(lo,[.04,.09,.04]);np.testing.assert_allclose(hi,[.04,.09,.64])
        lo,hi=pair_bounds(y,p,q,'brier')
        np.testing.assert_allclose(lo,[.21,.16,-.39]);np.testing.assert_allclose(hi,[.21,.16,.21])
        same=pair_bounds(y,p,p,'logloss');np.testing.assert_array_equal(same[0],[0,0,0]);np.testing.assert_array_equal(same[1],[0,0,0])

    def test_strict_purge_uses_label_date_not_panel_row_gap(self):
        f=pd.DataFrame(dict(eval_date=pd.to_datetime(['2019-01-31','2019-11-29','2019-12-31','2020-01-31','2020-02-28']),
                            label_end=pd.to_datetime(['2019-04-30','2020-01-01','2020-03-31','2020-04-30','2020-05-29']),
                            asof_member=True,point_target_identified=[True,True,True,False,True]))
        train,test=split_year(f,2020)
        self.assertEqual(list(train.index),[0]);self.assertEqual(list(test.index),[3,4])

    def test_unknown_rows_retained_in_test_and_do_not_pass_class_floor(self):
        days=pd.date_range('2020-01-31',periods=12,freq='ME')
        f=pd.DataFrame(dict(eval_date=days,maturity_clock_reached=True,asof_member=True,
                            robust_target=[None]*12,product_vt_symbol='A'))
        g=test_gate(f,2020)
        self.assertEqual(g['mature_months'],12);self.assertFalse(g['engineering_floor_pass'])

    def test_invalid_probability_or_targets_rejected(self):
        with self.assertRaises(ValueError):loss_bounds(np.array([2.]),np.array([.5]),'brier')
        with self.assertRaises(ValueError):loss_bounds(np.array([np.nan]),np.array([np.nan]),'brier')


if __name__=='__main__':unittest.main()
