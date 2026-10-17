import importlib
import io
import pickle
import unittest


class InventoryBoundaries(unittest.TestCase):
    def subject(self):
        try:
            return importlib.import_module('stage265_rqalpha_inventory')
        except ModuleNotFoundError:
            self.fail('RQAlpha raw inventory boundary reader not implemented')

    def test_metadata_unpickler_refuses_global_execution(self):
        subject = self.subject()
        class Unexpected:
            def __reduce__(self):
                return eval, ('1+1',)
        with self.assertRaises(pickle.UnpicklingError):
            subject.PrimitivesOnly(io.BytesIO(pickle.dumps(Unexpected()))).load()
        expected = [{'exchange': 'CZCE', 'listed_date': '2014-05-19', 'multiplier': 5.0}]
        self.assertEqual(subject.PrimitivesOnly(io.BytesIO(pickle.dumps(expected, protocol=2))).load(), expected)

    def test_zero_volume_positive_flat_vendor_candle_is_not_a_trade(self):
        subject = self.subject()
        self.assertEqual(subject.observation_status(6160, 6160, 6160, 6160, 0, 7366), 'no_trade_zero_volume')
        self.assertEqual(subject.observation_status(10, 12, 9, 11, 4, 7), 'valid_traded_ohlc')
        self.assertEqual(subject.observation_status(10, 12, 9, 13, 4, 7), 'invalid_traded_ohlc')

    def test_calendar_day_accepts_midnight_source_and_rejects_future_clock_alias(self):
        subject = self.subject()
        self.assertEqual(subject.source_day(20150515000000), '2015-05-15')
        self.assertEqual(subject.source_day(20150515), '2015-05-15')
        for value in [20150515000100, 20150230000000, 0]:
            with self.assertRaises(ValueError):
                subject.source_day(value)

    def test_real_contract_identity_uses_metadata_year_and_preserves_legacy_product(self):
        subject = self.subject()
        old = {'order_book_id': 'ME1505', 'exchange': 'CZCE', 'underlying_symbol': 'ME', 'maturity_date': '2015-05-15'}
        self.assertEqual(subject.contract_id(old), 'CZCE.ME.201505')
        later = dict(old, order_book_id='MA2505', underlying_symbol='MA', maturity_date='2025-05-15')
        self.assertEqual(subject.contract_id(later), 'CZCE.MA.202505')
        with self.assertRaises(ValueError):
            subject.contract_id(dict(old, maturity_date='0000-00-00'))

    def test_retired_continuous_code_with_nonzero_maturity_still_is_not_a_contract(self):
        subject = self.subject()
        with self.assertRaises(ValueError):
            subject.contract_id({'order_book_id': 'ME888', 'exchange': 'CZCE', 'underlying_symbol': 'ME', 'maturity_date': '2015-05-15'})

    def test_monthly_average_future_keeps_contract_month_distinct_from_last_trade_month(self):
        subject = self.subject()
        self.assertEqual(subject.contract_id({'order_book_id': 'L2602F', 'exchange': 'DCE', 'underlying_symbol': 'L_F', 'maturity_date': '2026-01-30'}), 'DCE.L_F.202602')

    def test_ordinary_crude_contract_month_is_not_replaced_by_previous_month_expiry(self):
        subject = self.subject()
        self.assertEqual(subject.contract_id({'order_book_id': 'SC2701', 'exchange': 'INE', 'underlying_symbol': 'SC', 'maturity_date': '2026-12-31'}), 'INE.SC.202701')


if __name__ == '__main__':
    unittest.main()
