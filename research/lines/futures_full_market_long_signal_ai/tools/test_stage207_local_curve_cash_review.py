"""Only new independent CI/strict204 gate semantics, no engine or historical I/O."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

spec=importlib.util.spec_from_file_location('cash_review207',Path(__file__).with_name('stage207_local_curve_cash_review.py'))
review=importlib.util.module_from_spec(spec);spec.loader.exec_module(review)

class CashReviewFixtures(unittest.TestCase):
    def test_actual_and_financial_terminal_schema_branches_reject_replay(self):
        verify=getattr(review,'verify_terminal_schemas',None)
        self.assertIsNotNone(verify,'separate actual/financial terminal schema adapter required')
        common=dict(status='completed',exit_code=0,cash_accounts_started=4,new_cash_accounts=4,
            raw_ledgers_checkpointed=4,actual_model_fit_calls=0,native_source_queries=0,new_labels=0)
        actual=dict(common,old_control_cash_replays=0,old_baseline_replays=0)
        financial=dict(common,old_control_book_replays=0)
        verify(actual,financial)
        for left,right in [(dict(actual,old_control_cash_replays=1),financial),
                           (actual,dict(financial,old_control_book_replays=1))]:
            with self.assertRaises(AssertionError):verify(left,right)

    def test_saved_false_boolean_and_same_original_indices_paired_log(self):
        active=pd.DataFrame(dict(equity=[1100000.,1210000.],ever_insolvent=['False','False']))
        control=pd.DataFrame(dict(equity=[1000000.,1000000.],ever_insolvent=['False','False']))
        stats,dist=review.paired(active,control,np.tile([1,0],(2000,1)))
        np.testing.assert_allclose(dist,np.log(1.1),rtol=1e-13,atol=1e-13)
        self.assertAlmostEqual(stats['ci95_low'],np.log(1.1))
        active.loc[1,'ever_insolvent']='True'
        self.assertIsNone(review.paired(active,control,np.tile([1,0],(2000,1)))[0]['ci95_low'])

    def test_each_CI_and_held_failure_cannot_be_overridden_by_cash(self):
        points={(w,c):dict(active_total_return_pct=10.,return_percentage_point_difference=1.,
            drawdown_percentage_point_difference=1.,ci95_low=.001) for w in review.WINDOWS for c in review.COSTS}
        held={s:dict(known_u_equal_mean_increment_R=.01,unknown_differential_selected_events=0,nominal_pass=True)
            for s in ('holdout_0','holdout_1')}
        self.assertTrue(review.gate(points,held,False,False,True)['nominal_pass'])
        points[('cold_2023','base')]['ci95_low']=0.
        self.assertFalse(review.gate(points,held,False,False,True)['all_four_daily_log_CI_lower_positive'])
        points[('cold_2023','base')]['ci95_low']=.001
        held['holdout_1'].update(known_u_equal_mean_increment_R=-.0008,nominal_pass=False)
        held['holdout_0'].update(unknown_differential_selected_events=7,nominal_pass=False)
        result=review.gate(points,held,False,False,True)
        self.assertTrue(result['cash_nominal_pass']);self.assertFalse(result['nominal_pass'])
        self.assertFalse(result['held_known_strictly_positive_all_two']);self.assertTrue(result['held_signal_unknown'])

if __name__=='__main__':unittest.main()
