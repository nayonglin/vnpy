"""Generic recovery must stay inside an actual request and preserve old rights."""
import copy
import json
from pathlib import Path
import unittest
import pandas as pd

try:
    import stage051_generic_exact_daily_recovery as module
except ImportError:
    module = None


class GenericDailyRecoveryTests(unittest.TestCase):
    def test_actual_scope_subset_and_existing_reference_cannot_be_overridden(self):
        self.assertIsNotNone(module, 'generic daily recovery is missing')
        request=json.loads((module.request_provider.REQUEST_ROOT/'request_2359178d438e2191ff3691ebb97a82f41be5c81f8fa3ecd279e5b0a631e9093a/request.json').read_text())
        calendar=pd.DatetimeIndex(pd.to_datetime(pd.read_csv(module.MAPPING,usecols=['date']).date.unique())).sort_values()
        selected=module.select_requirements(request,['SM009.CZCE'],calendar)
        self.assertEqual([(x['vt_symbol'],x['requirement_kind'])for x in selected],[('SM009.CZCE','full_session')])
        with self.assertRaises(ValueError):module.select_requirements(request,['SM005.CZCE'],calendar)
        changed=copy.deepcopy(request);changed['requirements'][0]['required_timestamps']=changed['requirements'][0]['required_timestamps'][:1]
        with self.assertRaises(ValueError):module.select_requirements(changed,['SM009.CZCE'],calendar)
        key=('SM009.CZCE','2020-04-15')
        for csv_exists,approved,rejected in [(True,set(),set()),(False,{key},set()),(False,set(),{key})]:
            with self.assertRaises(ValueError):module.require_missing_reference(key,csv_exists,approved,rejected)

    def test_exact_DB_six_fields_and_real_successor_are_required(self):
        self.assertIsNotNone(module, 'generic daily recovery is missing')
        targets=module.database_targets([dict(vt_symbol='SM009.CZCE',execution_trade_date='2020-04-15',requirement_kind='full_session')])
        row=targets.iloc[0]
        snapshot=pd.DataFrame([dict(id=i,datetime=int(pd.Timestamp(day,tz='Asia/Shanghai').value),
            **{f:float(row[f])for f in ['open','high','low','close','volume']},open_oi=float(row.open_interest),close_oi=float(row.open_interest)+1.)
            for i,day in [(10,'2020-04-15'),(11,'2020-04-16')]])
        good,_=module.qualify_daily_snapshot('SM009.CZCE',snapshot,targets)
        self.assertEqual(len(good),1)
        bad,audit=module.qualify_daily_snapshot('SM009.CZCE',snapshot.iloc[:1],targets)
        self.assertTrue(bad.empty);self.assertEqual(audit.iloc[0].reason,'no_forward_successor')
        swapped=snapshot.copy();swapped.loc[0,['open_oi','close_oi']]=[float(row.open_interest)+1.,float(row.open_interest)]
        bad,audit=module.qualify_daily_snapshot('SM009.CZCE',swapped,targets)
        self.assertTrue(bad.empty);self.assertEqual(audit.iloc[0].mismatch_fields,'open_oi')


if __name__=='__main__':unittest.main()
