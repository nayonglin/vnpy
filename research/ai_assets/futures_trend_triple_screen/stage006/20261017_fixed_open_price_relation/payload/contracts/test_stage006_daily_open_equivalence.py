"""Only exact real bars and original physical session starts can be equivalent."""
import sqlite3
import unittest
import pandas as pd

try:
    import stage006_daily_open_equivalence as module
except ImportError:
    module = None


class DailyOpenEquivalenceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(module, 'Stage006 audit has not been implemented')
        self.db = sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE dbbardata (symbol TEXT,exchange TEXT,datetime TEXT,interval TEXT,open_price REAL)')
        self.calendar = pd.to_datetime(['2020-05-15', '2020-05-18'])
        self.event = dict(vt_symbol='rb2010.SHFE', trading_date='2020-05-18',
            expected_start='2020-05-15T21:00:00', actual_time='2020-05-15T21:00:00',
            anchor_present='True', source='canonical_session_first_minute_open',
            price='3500', order_id='BACKTESTING.1', offset='Open')

    def tearDown(self):
        if hasattr(self, 'db'):
            self.db.close()

    def add(self, symbol='rb2010', exchange='SHFE', day='2020-05-18', interval='d', opening=3500):
        self.db.execute('INSERT INTO dbbardata VALUES (?,?,?,?,?)',
            (symbol, exchange, day + ' 00:00:00', interval, opening))

    def test_query_requires_exact_contract_exchange_interval_and_trading_date(self):
        self.add(); self.add(symbol='rb2011', opening=9999); self.add(exchange='DCE', opening=9999)
        self.add(day='2020-05-15', opening=9999); self.add(interval='1m', opening=9999)
        rows = module.lookup_real_daily_open(self.db, 'rb2010.SHFE', '2020-05-18')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['open_price'], 3500)

    def test_missing_and_duplicate_real_bars_cannot_be_equivalent(self):
        result = module.check_event(self.event, [], self.calendar, 'Long')
        self.assertEqual(result['daily_status'], 'missing_real_daily_bar')
        self.assertFalse(result['equivalent'])
        self.add(); self.add()
        rows = module.lookup_real_daily_open(self.db, 'rb2010.SHFE', '2020-05-18')
        result = module.check_event(self.event, rows, self.calendar, 'Long')
        self.assertEqual(result['daily_status'], 'duplicate_real_daily_bars')
        self.assertFalse(result['equivalent'])

    def test_price_mismatch_and_invalid_price_are_preserved(self):
        self.add(opening=3501)
        rows = module.lookup_real_daily_open(self.db, 'rb2010.SHFE', '2020-05-18')
        result = module.check_event(self.event, rows, self.calendar, 'Long')
        self.assertEqual(result['absolute_price_difference'], 1)
        self.assertFalse(result['price_tolerance_match'])
        self.assertFalse(result['equivalent'])
        result = module.check_event({**self.event, 'price':'nan'}, rows, self.calendar, 'Long')
        self.assertFalse(result['anchor_price_valid'])
        self.assertFalse(result['equivalent'])

    def test_friday_night_is_monday_session_and_monday_natural_0900_is_rejected(self):
        self.add()
        rows = module.lookup_real_daily_open(self.db, 'rb2010.SHFE', '2020-05-18')
        result = module.check_event(self.event, rows, self.calendar, 'Long')
        self.assertEqual(result['helper_session_start'], '2020-05-15T21:00:00')
        self.assertTrue(result['equivalent'])
        result = module.check_event({**self.event, 'actual_time':'2020-05-18T09:00:00'}, rows, self.calendar, 'Long')
        self.assertFalse(result['physical_time_match'])
        self.assertFalse(result['equivalent'])

    def test_direction_join_is_exact_and_missing_stays_unknown(self):
        orders = pd.DataFrame([
            dict(order_id='BACKTESTING.1',vt_symbol='rb2010.SHFE',trading_date='2020-05-18',offset='开',direction='多'),
            dict(order_id='BACKTESTING.1',vt_symbol='rb2011.SHFE',trading_date='2020-05-18',offset='开',direction='空'),
        ])
        self.assertEqual(module.event_direction(self.event, orders), ('Long', 'exact_order_fields'))
        self.assertEqual(module.event_direction({**self.event,'order_id':'BACKTESTING.2'}, orders), ('unknown', 'no_exact_order_fields'))


if __name__ == '__main__':
    unittest.main()
