"""报告日期必须以交易日归属，避免夜盘进入错误月份。"""
import unittest
import pandas as pd
from stage249_historical_replay import attach_trading_dates


class ReportDateTests(unittest.TestCase):
    def test_weekend_and_month_boundary_keep_physical_clock(self):
        trades = pd.DataFrame([{"trade_id": "B.1", "datetime": "2026-07-31 21:00:00+08:00", "date": "2026-07-31"}])
        clock = pd.DataFrame([{"trade_id": "B.1", "trading_date": "2026-08-03"}])
        actual = attach_trading_dates(trades, clock)
        self.assertEqual(actual.iloc[0]["date"], "2026-08-03")
        self.assertEqual(actual.iloc[0]["natural_date"], "2026-07-31")
        self.assertEqual(actual.iloc[0]["datetime"], trades.iloc[0]["datetime"])
        self.assertEqual(trades.iloc[0]["date"], "2026-07-31")

    def test_missing_or_duplicate_trade_identity_fails_closed(self):
        trades = pd.DataFrame([{"trade_id": "B.1", "datetime": "2020-01-01", "date": "2020-01-01"}])
        one = pd.DataFrame([{"trade_id": "B.1", "trading_date": "2020-01-02"}])
        wrong = one.copy(); wrong["trade_id"] = "B.2"
        for clock in [wrong, pd.concat([one, one])]:
            with self.assertRaisesRegex(ValueError, "trade_clock_identity_mismatch"):
                attach_trading_dates(trades, clock)


if __name__ == "__main__":
    unittest.main()
