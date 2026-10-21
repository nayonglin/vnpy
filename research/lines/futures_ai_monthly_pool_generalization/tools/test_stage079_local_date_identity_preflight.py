import unittest
import pandas as pd
from stage079_local_date_identity_preflight import window_metrics

def frame(times,prices=None):
 if prices is None:prices=[100.]*len(times)
 return pd.DataFrame({'bar_datetime':pd.to_datetime(times),**{k:prices for k in ['open','high','low','close']}})
class DateIdentityPreflightTests(unittest.TestCase):
 def test_zero_window_is_absent_not_ohlc_conflict(self):
  x=window_metrics(frame(['2022-05-10 09:00']), '2022-05-09','2022-05-06',dict(open=100,high=100,low=100,close=100));self.assertEqual(x['broad']['rows'],0);self.assertIsNone(x['broad']['target_daily_ohlc_match'])
 def test_friday_night_belongs_broad_monday_window(self):
  x=window_metrics(frame(['2022-05-06 21:00','2022-05-07 02:29','2022-05-09 09:00']), '2022-05-09','2022-05-06',dict(open=100,high=100,low=100,close=100));self.assertEqual(x['broad']['rows'],3);self.assertEqual(x['day']['rows'],1)
 def test_endpoint15_is_broad_but_not_day(self):
  x=window_metrics(frame(['2022-05-09 14:59','2022-05-09 15:00','2022-05-09 15:01']), '2022-05-09','2022-05-06',dict(open=100,high=100,low=100,close=100));self.assertEqual(x['broad']['rows'],2);self.assertEqual(x['day']['rows'],1)
 def test_aggregate_sorted_without_fixing_missing_grid(self):
  x=window_metrics(frame(['2022-05-09 14:59','2022-05-09 09:00'],[101,100]),'2022-05-09','2022-05-06',dict(open=100,high=101,low=100,close=101));self.assertTrue(x['broad']['target_daily_ohlc_match']);self.assertEqual(x['broad']['rows'],2)
 def test_extra_other_date_does_not_change_aggregate(self):
  x=window_metrics(frame(['2022-05-06 14:59','2022-05-09 09:00'],[999,100]),'2022-05-09','2022-05-06',dict(open=100,high=100,low=100,close=100));self.assertTrue(x['broad']['target_daily_ohlc_match'])
 def test_invalid_prices_not_silently_aggregated(self):
  x=window_metrics(frame(['2022-05-09 09:00'],[float('nan')]),'2022-05-09','2022-05-06',dict(open=100,high=100,low=100,close=100));self.assertIsNone(x['broad']['aggregate_ohlc']);self.assertEqual(x['broad']['invalid_ohlc_rows'],1)
 def test_matching_ohlc_is_not_session_qualification(self):
  x=window_metrics(frame(['2022-05-09 09:00']), '2022-05-09','2022-05-06',dict(open=100,high=100,low=100,close=100));self.assertNotIn('qualified',str(x))
