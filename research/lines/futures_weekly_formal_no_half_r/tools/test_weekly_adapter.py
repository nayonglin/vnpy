from copy import copy
from datetime import datetime
from types import SimpleNamespace
import unittest
try:
    from weekly_adapter import WeeklyArrayManager, weekly_strategy_class, completed_weeks
except ImportError:
    WeeklyArrayManager=weekly_strategy_class=completed_weeks=None
class AM:
    def __init__(self,size=41):self.size=size;self.rows=[];self.count=0;self.inited=False
    def update_bar(self,b):self.rows.append(copy(b));self.count+=1;self.inited=self.count>=self.size

def bar(day,close=110,volume=10):
    return SimpleNamespace(datetime=datetime.fromisoformat(day),open_price=100.,high_price=120.,low_price=90.,close_price=float(close),volume=float(volume),turnover=1000.,open_interest=float(close))
class WeeklyTests(unittest.TestCase):
    def manager(self,days):
        self.assertIsNotNone(WeeklyArrayManager,'weekly adapter not implemented')
        return WeeklyArrayManager(AM(),completed_weeks(days))
    def test_no_partial_week_or_lookahead(self):
        m=self.manager(['2020-01-06','2020-01-07','2020-01-08','2020-01-09','2020-01-10','2020-01-13'])
        for d in ['2020-01-06','2020-01-07','2020-01-08','2020-01-09']:m.update_bar(bar(d))
        self.assertEqual(m.count,0)
        m.update_bar(bar('2020-01-10',115));self.assertEqual(m.count,1)
        self.assertEqual(m.inner.rows[0].volume,50);self.assertEqual(m.inner.rows[0].open_interest,115)
        m.update_bar(bar('2020-01-13',999));self.assertEqual(m.count,1);self.assertFalse(m.fresh)
    def test_holiday_week_closes_only_at_declared_last_session(self):
        m=self.manager(['2020-01-20','2020-01-21','2020-01-22','2020-01-23','2020-02-03'])
        for d in ['2020-01-20','2020-01-21','2020-01-22','2020-01-23']:m.update_bar(bar(d))
        self.assertEqual(m.count,1)
    def test_trailing_thursday_never_treated_as_finished_week(self):
        m=self.manager(['2026-10-19','2026-10-20','2026-10-21','2026-10-22'])
        for d in ['2026-10-19','2026-10-20','2026-10-21','2026-10-22']:m.update_bar(bar(d))
        self.assertEqual(m.count,0)
    def test_missing_contract_session_rejects_week(self):
        days=['2020-01-06','2020-01-07','2020-01-08','2020-01-09','2020-01-10']
        m=self.manager(days)
        for d in [days[0],*days[2:]]:m.update_bar(bar(d))
        self.assertEqual(m.count,0);self.assertEqual(len(m.rejected),1)
    def test_zero_volume_carry_does_not_count_as_real_session(self):
        m=self.manager(['2020-01-10'])
        m.update_bar(bar('2020-01-10',volume=0));self.assertEqual(m.count,0)
    def test_ready_threshold_remains_41_weeks(self):
        from datetime import timedelta
        days=[(datetime(2020,1,10)+timedelta(weeks=i)).strftime('%Y-%m-%d') for i in range(41)]
        m=self.manager(days)
        for d in days[:40]:m.update_bar(bar(d))
        self.assertFalse(m.inited);m.update_bar(bar(days[-1]));self.assertTrue(m.inited)
    def test_week_cross_signal_not_reemitted_on_nonclose_day(self):
        self.assertIsNotNone(weekly_strategy_class)
        class Base:
            def __init__(self):self.ams={}
            def _generate_signal(self,am,history):return dict(signal='long_case1a',breakout=True,bullish_alignment=True)
        strategy=weekly_strategy_class(Base,{})()
        a=SimpleNamespace(fresh=False)
        self.assertEqual(strategy._generate_signal(a,None)['signal'],'')
        a.fresh=True;self.assertEqual(strategy._generate_signal(a,None)['signal'],'long_case1a')
if __name__=='__main__':unittest.main()
