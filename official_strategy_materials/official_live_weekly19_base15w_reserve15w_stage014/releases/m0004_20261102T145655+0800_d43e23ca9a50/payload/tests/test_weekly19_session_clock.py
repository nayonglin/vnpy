import sys,unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'examples/portfolio_backtesting'))
from qmt_roll_weekly19_session_clock import resolve_weekly19_session,Weekly19SessionClockError
TZ=ZoneInfo('Asia/Shanghai');DAYS=['2026-10-29','2026-10-30','2026-11-02','2026-11-03']
class ClockTest(unittest.TestCase):
 def call(self,text,day,calendar=DAYS):return resolve_weekly19_session(now=datetime.fromisoformat(text).replace(tzinfo=TZ),broker_trading_date=day,calendar=calendar)
 def test_friday_night_and_saturday_continuation_use_monday_nominal_day(self):
  a=self.call('2026-10-30T21:01:00','2026-11-02');b=self.call('2026-10-31T01:00:00','2026-11-02')
  self.assertTrue(a['is_open']);self.assertTrue(b['is_open']);self.assertEqual(b['starts_at'][:10],'2026-10-30')
 def test_saturday_night_and_sunday_never_become_market_day(self):
  self.assertFalse(self.call('2026-10-31T21:01:00','2026-11-02')['is_open']);self.assertFalse(self.call('2026-11-01T21:01:00','2026-11-02')['is_open'])
 def test_day_session_requires_actual_calendar_and_broker_day(self):
  self.assertTrue(self.call('2026-11-02T09:01:00','2026-11-02')['is_open'])
  self.assertFalse(self.call('2026-11-02T09:01:00','2026-11-03')['is_open'])
  self.assertFalse(self.call('2026-11-02T09:01:00','2026-11-02',[])['is_open'])
 def test_lunch_and_postclose_are_not_execution_windows(self):
  self.assertFalse(self.call('2026-11-02T12:00:00','2026-11-02')['is_open']);self.assertFalse(self.call('2026-11-02T16:00:00','2026-11-02')['is_open'])
 def test_holiday_next_day_is_calendar_not_weekday_guess(self):
  self.assertTrue(self.call('2026-10-29T21:01:00','2026-11-02',['2026-10-29','2026-11-02'])['is_open'])
  self.assertFalse(self.call('2026-10-29T21:01:00','2026-10-30',['2026-10-29','2026-11-02'])['is_open'])
 def test_naive_clock_is_rejected(self):
  with self.assertRaises(Weekly19SessionClockError):resolve_weekly19_session(now=datetime(2026,11,2),broker_trading_date='2026-11-02',calendar=DAYS)
if __name__=='__main__':unittest.main()
