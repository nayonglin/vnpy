import unittest
import pandas as pd
from stage060_data_expansion_comparison import compare_predictions


class ComparisonTests(unittest.TestCase):
    def fixture(self):
        old=pd.DataFrame(dict(eval_date=['2024-01-31']*2,product_vt_symbol=['A','B'],expanded_probability=[.5,.5]))
        new=old.copy();new['expanded_probability']=[.8,.8]
        targets=old[['eval_date','product_vt_symbol']].copy();targets['robust_target']=[1.,None];targets['maturity_clock_reached']=True
        return old,new,targets

    def test_full_unknown_denominator_in_paired_bounds(self):
        old,new,targets=self.fixture();_,m=compare_predictions(old,new,targets)
        self.assertEqual(int(m.iloc[0].N),2);self.assertEqual(int(m.iloc[0].known),1)
        self.assertAlmostEqual(m.iloc[0].brier_improvement_lower,-.09)
        self.assertAlmostEqual(m.iloc[0].brier_improvement_upper,.21)

    def test_missing_or_duplicate_predictions_rejected(self):
        old,new,targets=self.fixture()
        with self.assertRaises(ValueError):compare_predictions(old,new.iloc[:1],targets)
        with self.assertRaises(ValueError):compare_predictions(pd.concat([old,old.iloc[:1]]),new,targets)


if __name__=='__main__':unittest.main()
