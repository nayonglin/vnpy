"""Data-only预取：参数、无账户副作用和候选日期边界。"""
from datetime import datetime
from types import SimpleNamespace
import unittest
import pandas as pd
from stage005_signal_anchor_plan import build_pure_reader, next_day_task, scan_raw_candidates

class ExampleSignals:
    parameters=['threshold','enabled']
    threshold=99
    enabled=False
    def __init__(self,*a,**kw):raise AssertionError('constructor must never run')
    def _build_history_df(self,am):return pd.DataFrame({'close':[am.value]})
    def _generate_signal(self,am,history):return {'signal':'long_case1a' if self.enabled and am.value>self.threshold else ''}
    def on_bars(self,*a):raise AssertionError('execution forbidden')

class PlanTests(unittest.TestCase):
    def test_effective_setting_not_class_default(self):
        reader,params=build_pure_reader(ExampleSignals,{'threshold':3,'enabled':True})
        self.assertEqual(params,{'threshold':3,'enabled':True})
        self.assertEqual(reader._generate_signal(SimpleNamespace(value=4),None)['signal'],'long_case1a')
        self.assertNotIn('states',reader.__dict__)
        with self.assertRaisesRegex(RuntimeError,'data_only'):getattr(reader,'states')
        with self.assertRaisesRegex(RuntimeError,'data_only'):reader.on_bars({})
        with self.assertRaisesRegex(RuntimeError,'read_only'):reader.threshold=5
    def test_next_actual_exchange_date_and_canonical_minute(self):
        def anchor(symbol,day,calendar):
            self.assertEqual(symbol,'al2601.SHFE');return pd.Timestamp('2026-10-09 21:00')
        t=next_day_task('al2601.SHFE','2026-10-09',['2026-10-09','2026-10-12'],anchor)
        self.assertEqual(t,{'vt_symbol':'al2601.SHFE','trading_day':'2026-10-12','natural_date':'2026-10-09','start':'21:00','end_exclusive':'21:01','session':'night'})
        self.assertIsNone(next_day_task('al2601.SHFE','2026-10-12',['2026-10-09','2026-10-12'],anchor))
    def test_scan_requires_real_same_day_target_fresh_and_inited(self):
        class AM:
            fresh=False;inited=False;value=0;count=0
            def update_bar(self,bar):
                self.value=bar.close_price;self.count+=1
                self.inited=self.count>=2;self.fresh=bar.datetime.day in [5,12]
        reader,_=build_pure_reader(ExampleSignals,{'threshold':3,'enabled':True})
        bars=[SimpleNamespace(datetime=datetime(2026,6,d),close_price=4) for d in [4,5,8,12]]
        rows=list(scan_raw_candidates('a2609.DCE',bars,AM(),reader,{'2026-06-04':'a2609.DCE','2026-06-05':'a2609.DCE','2026-06-08':'a2609.DCE','2026-06-12':'a2611.DCE'},'2026-01-01','2026-10-22'))
        self.assertEqual([r['signal_date'] for r in rows],['2026-06-05'])
        self.assertEqual(rows[0]['observed_weeks'],2)
    def test_unrecognized_setting_cannot_silently_override(self):
        with self.assertRaisesRegex(ValueError,'unknown_setting'):
            build_pure_reader(ExampleSignals,{'threshold':3,'typo_enabled':True})

if __name__=='__main__':unittest.main()
