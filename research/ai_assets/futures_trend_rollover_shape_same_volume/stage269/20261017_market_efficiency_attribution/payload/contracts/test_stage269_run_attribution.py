import unittest
import numpy as np
import pandas as pd

from stage269_run_attribution import mask_period, sensitivity_table, parse_calendar


class OrchestrationTest(unittest.TestCase):
    def test_integer_calendar_is_yyyymmdd_not_nanoseconds(self):
        dates=parse_calendar(np.array([20200102,20200103]))
        self.assertEqual(str(dates[0].date()),'2020-01-02')
    def test_cross_year_labels_excluded_without_compressing_calendar(self):
        f = pd.DataFrame({'date': pd.to_datetime(['2024-12-20','2025-01-02','2025-02-01']),
            'label_end': pd.to_datetime(['2025-01-20','2025-02-02','2025-03-01']),
            'regime':['high','low','mid'], 'future20_return':[.1,.2,.3]})
        out = mask_period(f, '2025-01-01','2025-12-31')
        self.assertEqual(len(out),3)
        self.assertTrue(pd.isna(out.loc[0,'regime']))
        self.assertEqual(out.loc[1,'regime'],'low')

    def test_excluded_year_crossing_is_not_left_in_leave_year_out(self):
        f = pd.DataFrame({'date':pd.to_datetime(['2024-12-20','2026-01-02']),
            'label_end':pd.to_datetime(['2025-01-20','2026-02-01']),
            'regime':['high','low'], 'future20_return':[.1,.2]})
        out = mask_period(f, exclude_year=2025)
        self.assertTrue(pd.isna(out.loc[0,'regime']))
        self.assertEqual(out.loc[1,'regime'],'low')

    def test_auxiliary_cannot_bypass_main_gate(self):
        f = pd.DataFrame({'date':pd.date_range('2025-01-01',periods=3),
            'gate_pass':[False,True,True], 'regime':['high','low','high'],
            'future20_return':[99.,-.1,.1], 'outside_pool_er60':[.9,.1,.3]})
        out = sensitivity_table(f)
        row = next(x for x in out if x['metric']=='outside_pool_er60')
        self.assertEqual(row['n'],2)
        self.assertAlmostEqual(row['pearson_future20'],1.)


if __name__=='__main__':
    unittest.main()
