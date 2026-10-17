"""Completion, local clock and strict quality boundaries without a provider."""
import unittest
import pandas as pd

try:
    import stage007_tqsdk_stream_probe as module
except ImportError:
    module = None


class StreamProbeTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(module, 'Stage007 is not implemented')
        self.expected = pd.date_range('2020-08-11 21:00', periods=3, freq='min')

    def serial(self, count):
        return pd.DataFrame([dict(datetime=int(stamp.tz_localize('Asia/Shanghai').tz_convert('UTC').value),
            open=3500,high=3502,low=3499,close=3501,volume=1,open_oi=100,close_oi=100)
            for stamp in pd.date_range(self.expected[0],periods=count,freq='min')])

    def test_nanoseconds_are_utc_then_shanghai_not_naively_local(self):
        stamp = pd.Timestamp('2020-08-11 13:00',tz='UTC').value
        self.assertEqual(module.tq_local_time(stamp),pd.Timestamp('2020-08-11 21:00'))

    def test_final_forming_bar_requires_observed_successor(self):
        collector=module.CompletedCollector(self.expected)
        collector.observe(self.serial(3))
        self.assertEqual(len(collector.records),2)
        self.assertNotIn(self.expected[-1],collector.records)
        collector.observe(self.serial(4))
        self.assertEqual(len(collector.records),3)
        self.assertEqual(collector.evidence[self.expected[-1]]['successor_time'],'2020-08-11T21:03:00')

    def test_conflicting_completed_bar_is_rejected(self):
        collector=module.CompletedCollector(self.expected)
        collector.observe(self.serial(4))
        changed=self.serial(4);changed.loc[0,'high']=3503
        with self.assertRaisesRegex(ValueError,'conflicting_completed_bar'):
            collector.observe(changed)

    def test_missing_or_illegal_bar_cannot_pass_daily_crosscheck(self):
        collector=module.CompletedCollector(self.expected)
        collector.observe(self.serial(4))
        daily=dict(open=3500,high=3502,low=3499,close=3501,volume=3,open_oi=100,close_oi=100)
        self.assertTrue(module.validate_target(collector,self.expected,daily,daily)['accepted'])
        missing=module.CompletedCollector(self.expected);missing.observe(self.serial(3))
        self.assertFalse(module.validate_target(missing,self.expected,daily,daily)['accepted'])
        collector.records[self.expected[0]]['high']=3498
        self.assertFalse(module.validate_target(collector,self.expected,daily,daily)['accepted'])

    def test_exception_receipt_does_not_include_raw_text_or_credentials(self):
        value=module.safe_error(PermissionError('account SecretUser password SecretPass permission denied'))
        self.assertEqual(value['category'],'permission_rejected')
        self.assertNotIn('Secret',str(value))


if __name__=='__main__':unittest.main()
