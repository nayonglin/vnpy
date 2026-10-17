import importlib.util
from pathlib import Path
import unittest

import pandas as pd

path=Path(__file__).with_name('stage019_normal_latest_batch.py')
spec=importlib.util.spec_from_file_location('stage019_normal_latest_batch',path)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def serial(times):
    stamps=pd.DatetimeIndex(times).tz_localize('Asia/Shanghai').tz_convert('UTC').asi8
    return pd.DataFrame([dict(datetime=int(t),open=100,high=101,low=99,close=100,
        volume=10,open_oi=20,close_oi=21)for t in stamps])


class LatestBatchTests(unittest.TestCase):
    def test_capacity_reserves_next_business_day_instead_of_stale_daily_end(self):
        calendar=pd.bdate_range('2026-09-01','2026-10-14')
        estimate=module.capacity_bound('rb2701.SHFE','2026-10-14',calendar,'2026-10-18')
        self.assertEqual(estimate['planning_endpoint'],'2026-10-19')
        self.assertEqual(estimate['session_count_upper'],4)
        self.assertEqual(estimate['bars_upper'],4*345+2)
        expired=module.capacity_bound('si2609.GFEX','2026-09-29',calendar,'2026-10-18')
        self.assertEqual(expired['planning_endpoint'],'2026-09-30')
        self.assertEqual(expired['bars_upper'],2*225+2)

    def test_selection_uses_full_count_then_anchor_count_then_code(self):
        candidates=[]
        for symbol,full,anchor in [('a',1,10),('b',2,0),('c',1,10)]:
            candidates.extend(dict(vt_symbol=symbol,original_requirement_kind='full_session')for _ in range(full))
            candidates.extend(dict(vt_symbol=symbol,original_requirement_kind='anchor')for _ in range(anchor))
        chosen,ranking=module.select_contracts(candidates,limit=2)
        self.assertEqual(chosen,['b','a'])
        self.assertEqual([r['vt_symbol']for r in ranking],['b','a','c'])

    def test_aggregate_preserves_more_than_old_20000_budget(self):
        times=pd.date_range('2026-01-01',periods=9000,freq='min')
        c=module.LatestCollector({str(i):times for i in range(3)})
        self.assertEqual(c.target_count,27000)
        self.assertEqual(len(c.collectors),3)
        with self.assertRaisesRegex(ValueError,'per_symbol'):
            module.LatestCollector({'a':pd.date_range('2026-01-01',periods=10001,freq='min')})
        with self.assertRaisesRegex(ValueError,'duplicate'):
            module.LatestCollector({'a':[times[0],times[0]]})
        with self.assertRaisesRegex(ValueError,'global'):
            module.LatestCollector({str(i):times for i in range(9)})

    def test_false_wait_keeps_same_api_and_initial_snapshot_keeps_old_target(self):
        wanted={'a':['2026-10-14 09:00'],'b':['2026-10-14 09:00']}
        c=module.LatestCollector(wanted)
        serials={s:serial(pd.date_range('2026-10-14 09:00',periods=3,freq='min'))for s in wanted}
        class FakeApi:
            def __init__(self):self.updates=0
            def is_serial_ready(self,frame):return self.updates>=1 if frame is serials['a']else self.updates>=2
            def wait_update(self,deadline):self.updates+=1;return self.updates!=1
        api=FakeApi()
        result=module.collect_initial_snapshots(api,serials,c,0,clock=lambda:0)
        self.assertEqual(result['status'],'all_initial_snapshots_observed')
        self.assertEqual(result['false_waits'],1)
        raw,evidence=c.frames()
        self.assertEqual(len(raw),2)
        self.assertEqual(set(evidence.successor_time),{'2026-10-14T09:01:00'})


if __name__=='__main__':unittest.main()
