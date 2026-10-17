import importlib
import unittest

try:
    clean = importlib.import_module('stage266_clean_daily')
except ModuleNotFoundError:
    clean = None


class CleanDailyContractTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(clean, 'Stage266 cleaner has not been implemented')

    def row(self, **changes):
        result = dict(open=100., high=110., low=90., close=105., volume=20., close_oi=40., open_oi=None)
        result.update(changes)
        return result

    def test_zero_volume_flat_vendor_candle_is_not_traded_history(self):
        self.assertEqual(clean.row_issue(self.row(volume=0)), 'no_trade')

    def test_positive_volume_close_outside_range_is_rejected(self):
        self.assertEqual(clean.row_issue(self.row(close=120)), 'invalid_ohlc')

    def test_missing_open_oi_is_not_imputed_or_legacy_eligible(self):
        result = clean.canonical_values(self.row(), .5, .5)
        self.assertIsNone(result['open_oi'])
        self.assertFalse(result['legacy108_row_usable'])
        self.assertEqual(result['close_oi'], 20.)
        self.assertEqual(result['open_oi_status'], 'missing_not_imputed')

    def test_real_observed_zero_open_oi_is_not_missing(self):
        result = clean.canonical_values(self.row(open_oi=0), .5, .5)
        self.assertEqual(result['open_oi'], 0.)
        self.assertTrue(result['legacy108_row_usable'])

    def test_unknown_or_fractional_contract_quantity_is_not_accepted(self):
        with self.assertRaises(ValueError):
            clean.canonical_values(self.row(), None, None)
        with self.assertRaises(ValueError):
            clean.canonical_values(self.row(volume=3), .5, .5)

    def test_identity_is_unique_by_lifetime_not_czce_short_name(self):
        index = {'CZCE.CF505': [
            dict(contract_epoch_id='CZCE.CF.201505', listed_date='2014-05-19', delisted_date='2015-05-15'),
            dict(contract_epoch_id='CZCE.CF.202505', listed_date='2024-05-17', delisted_date='2025-05-16')]}
        self.assertEqual(clean.resolve_alias(index, 'CZCE.CF505', '2015-01-05'), 'CZCE.CF.201505')
        self.assertEqual(clean.resolve_alias(index, 'CZCE.CF505', '2025-01-06'), 'CZCE.CF.202505')
        with self.assertRaises(ValueError):
            clean.resolve_alias(index, 'CZCE.CF505', '2020-01-06')

    def test_source_priority_replaces_whole_bar_and_never_mixes_fields(self):
        old = {'priority': 100, 'open': 100, 'close': 105, 'open_oi': None, 'source_id': 'rq'}
        new = {'priority': 300, 'open': 102, 'close': 106, 'open_oi': 30, 'source_id': 'tq'}
        self.assertEqual(clean.pick_source(old, new), new)
        self.assertEqual(clean.pick_source(new, old), new)

    def test_quantity_conflict_exclusion_keeps_the_full_delivery_year(self):
        metadata = {'CF1505': {'contract_epoch_id': 'CZCE.CF.201505'},
                    'CF2505': {'contract_epoch_id': 'CZCE.CF.202505'}}
        result = clean.conflict_keys([{'rq_symbol': 'CF1505', 'date': '2015-01-05'}], metadata)
        self.assertEqual(result, {('CZCE.CF.201505', '2015-01-05')})


if __name__ == '__main__':
    unittest.main()
