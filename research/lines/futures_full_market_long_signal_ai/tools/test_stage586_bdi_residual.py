import math
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
import stage586_bdi_core as core

def row(date, price):
    return dict(symbol='BDI',name='original',opendate=date,price=str(price),zde='unused',zdf='unused')
def contract(conflicts=()):
    return dict(bad_year_indices=[],weekend_indices=[],conflict_indices=list(conflicts))

class Frozen585Boundaries(unittest.TestCase):
    def test_last_candidate_conflict_never_falls_back(self):
        months,macro,quality=core.project_source([row('2019-10-30',90),row('2019-10-31',100)],contract([1]),['2019-11-01'],'2019-11-20')
        m=months.set_index('reference_month').loc['2019-10']
        self.assertEqual(m.endpoint_raw_index,1);self.assertEqual(m.endpoint_state,'frozen_conflict');self.assertTrue(pd.isna(m.g))
        self.assertEqual(macro.macro_available.tolist(),[0])

    def test_missing_month_clears_old_and_partial_future_never_consumed(self):
        rows=[row('2019-10-31',100),row('2020-01-31',120),row('2020-03-16',130)]
        months,m,_=core.project_source(rows,contract(),['2020-01-31','2020-02-03','2020-03-02','2020-03-16'],'2020-03-16')
        self.assertEqual(m.reference_month.tolist(),['2019-12','2020-01','2020-02','2020-02'])
        self.assertEqual(m.macro_available.tolist(),[0,1,0,0]);self.assertAlmostEqual(m.iloc[1].g,math.log(1.2))
        self.assertEqual(months.iloc[-1].endpoint_state,'incomplete_calendar_month')

    def test_three_calendar_months_not_three_observations(self):
        _,m,_=core.project_source([row('2019-09-30',50),row('2019-10-31',100),row('2020-01-31',120)],contract(),['2020-02-03'],'2020-02-10')
        self.assertAlmostEqual(m.iloc[0].g,math.log(1.2));self.assertEqual(m.iloc[0].base_month,'2019-10')

    def test_known_regime_boundaries_are_not_adjusted(self):
        rows=[row('2009-04-30',100),row('2009-07-31',120),row('2017-12-29',150),row('2018-03-30',160)]
        _,m,_=core.project_source(rows,contract(),['2009-08-03','2018-04-02'],'2018-04-10')
        self.assertEqual(m.macro_available.tolist(),[0,0]);self.assertEqual(m.reason.tolist(),['cross_regime','cross_regime'])

    def test_bad_year_and_weekend_preserved_not_repaired(self):
        rows=[row('0023-06-02',919),row('2020-01-25',100),row('2020-01-31',120)]
        c=contract();c['bad_year_indices']=[0];c['weekend_indices']=[1]
        months,_,q=core.project_source(rows,c,['2020-02-03'],'2020-02-10')
        self.assertEqual(q['quarantined_indices'],[0,1]);self.assertEqual(months.iloc[0].endpoint_raw_index,2)

    def test_scaler_uses_only_known_mature_train_original_weights(self):
        t=pd.DataFrame(dict(sequence_index=[0,1,2],action_id=['a','b','c'],family_id=['x']*3,u_date=['2019-01-02','2019-02-01','2019-03-01'],u_index=[0,1,2],u_action_eligible=[1]*3,label_state=['closed_complete_bar_model']*3,label_known_date=['2019-03-04']*3,net_R_stress=[2,4,100],sample_weight=[1,3,100],Ahat=[1,1,0]))
        m=pd.DataFrame(dict(u_index=[0,1,2],u_date=t.u_date,macro_available=[1,1,0],reference_month=['2018-12','2019-01','2019-02'],g=[1.,3.,999.]))
        stats,monthly=core.training_statistics(t,m,'2020-01-01')
        self.assertEqual(stats['known_rows'],2);self.assertEqual(stats['original_known_weight_sum'],4.)
        self.assertAlmostEqual(stats['feature_mean'],2.5);self.assertAlmostEqual(stats['feature_scale'],math.sqrt(.75))
        self.assertAlmostEqual(stats['normalized_weight_sum'],1.);self.assertEqual(stats['M'],2)
        self.assertAlmostEqual(stats['rhs'][0],2.5)

    def test_missing_fallback_is_bitwise_A(self):
        b=np.array([-0.,1.]);got=core.apply_delta(b,[100.,2.],[False,True])
        self.assertEqual(got[0].view(np.uint64),b[0].view(np.uint64));self.assertEqual(got[1],3.)

    def test_all_six_preflight_precedes_any_solve(self):
        records=[dict(scope=str(i),cutoff='2020',support_pass=i!=5) for i in range(6)]
        with patch('numpy.linalg.solve') as solve:
            with self.assertRaises(ValueError):core.fit_models(records)
            solve.assert_not_called()

if __name__=='__main__':unittest.main()
