import unittest
from stage011_bar_open_audit import audit_bar_open_records

class BarOpenAuditTests(unittest.TestCase):
    def setUp(self):
        self.row=dict(open=3500.,high=3550.,low=3480.,close=3530.,volume=10000.)
        self.trade=dict(trade_id='1',vt_symbol='rb2010.SHFE',trading_date='2020-08-10',execution_datetime='2020-08-07 21:00:00+08:00',price=3500.,volume=2.)
        self.calendar=['2020-08-07','2020-08-10']
    def audit(self,trades=None,anchors=None,rows=None,reads=None):
        return audit_bar_open_records([self.trade] if trades is None else trades,anchors or [],lambda symbol,day: [self.row] if rows is None else rows,self.calendar,reads or dict(minute_reads=0,proxy_reads=0))
    def test_exact_unadjusted_daily_open_and_model_clock_pass(self):
        self.assertTrue(self.audit()['accepted'])
    def test_wrong_fill_price_rejects(self):
        trade={**self.trade,'price':3501.};r=self.audit([trade]);self.assertFalse(r['accepted']);self.assertEqual(r['daily_price_mismatch_count'],1)
    def test_zero_daily_volume_rejects(self):
        self.assertFalse(self.audit(rows=[{**self.row,'volume':0.}])['accepted'])
    def test_missing_or_duplicate_daily_row_rejects(self):
        for rows in ([],[self.row,self.row]):
            with self.subTest(rows=len(rows)):self.assertFalse(self.audit(rows=rows)['accepted'])
    def test_invalid_daily_ohlc_rejects(self):
        self.assertFalse(self.audit(rows=[{**self.row,'high':3499.}])['accepted'])
    def test_any_minute_or_proxy_read_rejects(self):
        for reads in (dict(minute_reads=1,proxy_reads=0),dict(minute_reads=0,proxy_reads=1)):
            with self.subTest(reads=reads):self.assertFalse(self.audit(reads=reads)['accepted'])
    def test_unfilled_anchor_request_is_also_reconciled(self):
        request=dict(vt_symbol='rb2010.SHFE',trading_date='2020-08-10',price=3501.,actual_time='2020-08-07 21:00',expected_start='2020-08-07 21:00')
        self.assertFalse(self.audit(trades=[],anchors=[request])['accepted'])
    def test_wrong_model_clock_rejects(self):
        self.assertFalse(self.audit([{**self.trade,'execution_datetime':'2020-08-10 09:00+08:00'}])['accepted'])
    def test_empty_ledger_does_not_fabricate_execution(self):
        r=self.audit(trades=[]);self.assertTrue(r['accepted']);self.assertEqual(r['trade_count'],0)
if __name__=='__main__':unittest.main()
