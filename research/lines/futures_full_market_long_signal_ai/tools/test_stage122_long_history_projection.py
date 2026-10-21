"""Finite semantic cases: previous representative, gaps, leap boundary and true zero."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
SOURCE=Path(__file__).with_name('stage122_long_history_projection.py')
def load():
    if not SOURCE.exists():return None
    s=importlib.util.spec_from_file_location('test122',SOURCE);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class FakeMarket:
    def __init__(self,records):self.records=records
    def bar(self,epoch,k):
        close=self.records.get((epoch,k))
        return None if close is None else dict(open=close,high=close,low=close,close=close,volume=1.)
def fixture(m,days,refs,prices):
    rows=[dict(sequence_index=i,event_id='e'+str(i),product_id='X.A',family_id='X.A',u_date=d,u_index=10+3*i,reference_epoch=refs[i]) for i,d in enumerate(days)]
    f=pd.DataFrame(rows)
    economics={e:dict(economics_status='exact_epoch_metadata_snapshot',contract_multiplier=1.,round_lot=1) for e in set(refs) if e}
    return f,FakeMarket(prices),economics
class LongHistoryProjection(unittest.TestCase):
    def setUp(self):self.m=load();self.assertIsNotNone(self.m,'Stage122 projection source absent')
    def test_leap_calendar_and_previous_representative_not_current_or_reindexed(self):
        days=['2019-02-28','2019-03-01','2020-02-28','2020-02-29']
        f,market,e=fixture(self.m,days,['old','new','new','later'],{('old',10):100,('old',13):110,('new',13):1000,('new',16):1200,('new',19):1200,('later',19):9999})
        p,a=self.m.project_mother(f,market,e)
        self.assertEqual(self.m.lower_boundary('2020-02-29'),'2019-02-28')
        self.assertEqual(a.prev_u_index.tolist(),[-1,10,13,16]);self.assertEqual(a.prev_reference_epoch.tolist(),['','old','new','new'])
        self.assertAlmostEqual(p.iloc[-1].external_scalar_raw,.32);self.assertEqual(p.iloc[-1].valid_factor_days,3)
        self.assertEqual(p.iloc[-1].external_missing,0)
    def test_gap_is_not_skipped_and_early_start_missing(self):
        days=['2018-01-01','2019-01-01','2019-06-01','2020-01-01']
        f,market,e=fixture(self.m,days,['e']*4,{('e',10):100,('e',13):100,('e',19):100})
        p,a=self.m.project_mother(f,market,e)
        self.assertEqual(p.iloc[0].missing_reason,'insufficient_calendar_history')
        self.assertEqual(p.iloc[-1].missing_reason,'missing_required_daily_factor');self.assertTrue(np.isnan(p.iloc[-1].external_scalar_raw))
        self.assertEqual(p.iloc[-1].missing_factor_days,2)
    def test_zero_observed_and_unqualified_economic_pair_missing(self):
        days=['2019-01-01','2019-06-01','2020-01-01']
        f,market,e=fixture(self.m,days,['e']*3,{('e',10):100,('e',13):100,('e',16):100})
        p,a=self.m.project_mother(f,market,e);self.assertEqual(p.iloc[-1].external_scalar_raw,0.);self.assertEqual(p.iloc[-1].external_observed,1)
        e['e']['economics_status']='unqualified';p,a=self.m.project_mother(f,market,e)
        self.assertEqual(a.iloc[1].factor_state,'unqualified_epoch_economics');self.assertEqual(p.iloc[-1].external_missing,1)
if __name__=='__main__':unittest.main()
