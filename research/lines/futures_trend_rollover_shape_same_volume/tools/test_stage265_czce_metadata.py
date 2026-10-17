"""Metadata identities must cross representation changes without inventing history."""
import unittest
import stage265_czce_metadata as metadata


class MetadataIdentityTests(unittest.TestCase):
    def test_three_and_four_digit_codes_bind_to_reported_delivery_year(self):
        first = metadata.normalize_metadata_code("SM1501.CZC", "2014-08-08", "2015-01-16")
        second = metadata.normalize_metadata_code("SM501.CZC", "2014-08-08", "2015-01-16")
        self.assertEqual(first["identity_key"], ("SM.CZCE", "201501"))
        self.assertEqual(first["identity_key"], second["identity_key"])
        self.assertEqual(metadata.normalize_metadata_code("SM607.CZC", "2015-07-15", "2016-07-14")["identity_key"], ("SM.CZCE", "201607"))

    def test_inconsistent_delivery_date_or_code_does_not_silently_change_identity(self):
        for code, issue, expiry in [("SM1501.CZC", "2024-08-08", "2025-01-16"),
                                     ("SM1501.CZC", "2014-08-08", "2015-02-16"),
                                     ("SM1501.CZC", "2015-01-17", "2015-01-16")]:
            with self.subTest(code=code, expiry=expiry), self.assertRaises(ValueError):
                metadata.normalize_metadata_code(code, issue, expiry)

    def test_old_me_is_not_relabelled_ma(self):
        actual = metadata.normalize_metadata_code("ME1505.CZC", "2014-05-16", "2015-05-15")
        self.assertEqual(actual["identity_key"], ("ME.CZCE", "201505"))

    def test_calendar_upper_bound_proves_short_history_without_filling_holidays(self):
        actual = metadata.history_upper_bound("2017-12-22", "2017-12-25")
        self.assertEqual(actual["calendar_day_upper_bound_through_first_main"], 4)
        self.assertTrue(actual["AM120_impossible_even_with_daily_bars"])
        self.assertEqual(metadata.history_upper_bound("2019-12-06", "2019-12-06")["calendar_day_upper_bound_through_first_main"], 1)
        self.assertIsNone(metadata.history_upper_bound("unknown", "2019-12-06")["AM120_impossible_even_with_daily_bars"])


if __name__ == "__main__":
    unittest.main()
