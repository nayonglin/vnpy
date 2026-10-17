import importlib.util
from pathlib import Path
import unittest

import pandas as pd

spec=importlib.util.spec_from_file_location('stage012_provider_batch',Path(__file__).with_name('stage012_provider_batch.py'))
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def serial(times, closes=None):
    stamps=pd.DatetimeIndex(times).tz_localize('Asia/Shanghai').tz_convert('UTC').asi8
    closes=closes or [100.0]*len(stamps)
    return pd.DataFrame([dict(datetime=int(t),open=c,high=c+1,low=c-1,close=c,volume=10,open_oi=20,close_oi=21) for t,c in zip(stamps,closes)])


class CollectorTests(unittest.TestCase):
    def test_forming_last_bar_never_accepted(self):
        c=module.BatchCollector({'rb2010.SHFE':['2020-08-11 21:00','2020-08-11 21:01']})
        c.observe('rb2010.SHFE',serial(['2020-08-11 21:00','2020-08-11 21:01']))
        self.assertEqual(len(c.records),1)
        raw,evidence=c.frames()
        self.assertEqual(raw.bar_datetime.iloc[0],'2020-08-11T21:00:00')
        self.assertEqual(evidence.successor_time.iloc[0],'2020-08-11T21:01:00')

    def test_independent_symbols_keep_nonoverlapping_times(self):
        c=module.BatchCollector({'rb2010.SHFE':['2020-08-11 21:00'],'AP010.CZCE':['2020-08-12 09:00']})
        c.observe('rb2010.SHFE',serial(['2020-08-11 21:00','2020-08-11 21:01']))
        c.observe('AP010.CZCE',serial(['2020-08-12 09:00','2020-08-12 09:01']))
        self.assertEqual(len(c.records),2)
        self.assertEqual(set(c.frames()[0].vt_symbol),{'rb2010.SHFE','AP010.CZCE'})

    def test_initial_snapshot_keeps_earlier_completed_history(self):
        c=module.BatchCollector({'rb2010.SHFE':['2020-08-11 21:00']})
        c.observe('rb2010.SHFE',serial(pd.date_range('2020-08-11 21:00',periods=5,freq='min')))
        self.assertEqual(len(c.records),1)

    def test_conflicting_completed_row_rejected_and_gap_successor_allowed(self):
        c=module.BatchCollector({'rb2010.SHFE':['2020-08-12 14:59']})
        c.observe('rb2010.SHFE',serial(['2020-08-12 14:59','2020-08-12 21:00']))
        with self.assertRaisesRegex(ValueError,'conflicting_completed_bar'):
            c.observe('rb2010.SHFE',serial(['2020-08-12 14:59','2020-08-12 21:00'],[101.0,100.0]))


if __name__=='__main__':unittest.main()
