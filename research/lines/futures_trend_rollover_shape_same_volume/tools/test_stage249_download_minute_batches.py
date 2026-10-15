"""14自然日10000根补数的任务边界回归，不连接网络。"""
from pathlib import Path
from datetime import datetime
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from stage249_prepare_replay import task_moments

class BatchTests(unittest.TestCase):
    def module(self):
        path=Path(__file__).with_name('stage249_download_minute_batches.py')
        self.assertTrue(path.is_file(),'14-day batch module required')
        import stage249_download_minute_batches as m
        return m

    def tasks(self):
        return [{'vt_symbol':symbol,'trading_day':day,'natural_date':day,
                 'start':'09:00','end_exclusive':'09:01','session':'day'}
                for symbol,day in [('fu2009.SHFE','2020-06-01'),('au2012.SHFE','2020-06-14'),('cu2012.SHFE','2020-06-15')]]

    def test_batch_includes_14_calendar_dates_but_never_fifteenth(self):
        m=self.module();batches=m.group_task_batches(self.tasks())
        self.assertEqual([len(b) for b in batches],[2,1])
        self.assertEqual({t['natural_date'] for t in batches[0]},{'2020-06-01','2020-06-14'})
        self.assertEqual(sum(len(b) for b in batches),3)

    def test_snapshot_uses_latest_natural_date_next_day_0800(self):
        m=self.module();snapshot,length=m.snapshot_spec(self.tasks()[:2])
        self.assertEqual(snapshot,datetime(2020,6,15,8));self.assertEqual(length,10000)

    def test_more_than_14_day_snapshot_fails_closed(self):
        m=self.module()
        with self.assertRaisesRegex(ValueError,'14'):m.snapshot_spec(self.tasks())

if __name__=='__main__':unittest.main()
