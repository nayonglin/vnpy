"""Open-interest source semantics and completion are mandatory contracts."""
import unittest
import pandas as pd

try:
    import stage008_oi_requalification as module
except ImportError:
    module=None


class RequalificationTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(module,'Stage008 is not implemented')
        self.aggregate=dict(open=3500.,high=3502.,low=3499.,close=3501.,volume=3.,open_oi=100.,close_oi=91.)
        self.database=dict(open=3500.,high=3502.,low=3499.,close=3501.,volume=3.,open_interest=100.)

    def test_database_open_interest_matches_open_oi_even_when_close_oi_differs(self):
        checks=module.field_checks(self.aggregate,self.aggregate,self.database)
        self.assertTrue(all(row['matches']for row in checks))
        check=next(row for row in checks if row['source']=='database'and row['source_field']=='open_interest')
        self.assertEqual(check['aggregate_field'],'open_oi')
        self.assertFalse(any(row['source']=='database'and row['aggregate_field']=='close_oi'for row in checks))

    def test_wrong_database_price_volume_or_open_oi_is_rejected(self):
        for field in ['open','volume','open_interest']:
            with self.subTest(field=field):
                bad={**self.database,field:self.database[field]+1}
                self.assertFalse(all(row['matches']for row in module.field_checks(self.aggregate,self.aggregate,bad)))

    def test_absent_successor_evidence_cannot_qualify_last_bar(self):
        expected=pd.date_range('2020-08-11 21:00',periods=3,freq='min')
        evidence=pd.DataFrame([dict(vt_symbol='rb2010.SHFE',bar_datetime=stamp.isoformat(),
            successor_time=(stamp+pd.Timedelta(minutes=1)).isoformat(),method='observed_later_serial_kline',completed=True)
            for stamp in expected])
        self.assertTrue(module.completion_check(evidence,expected)['accepted'])
        self.assertFalse(module.completion_check(evidence.iloc[:-1],expected)['accepted'])
        evidence.loc[2,'successor_time']=expected[-1].isoformat()
        self.assertFalse(module.completion_check(evidence,expected)['accepted'])


if __name__=='__main__':unittest.main()
