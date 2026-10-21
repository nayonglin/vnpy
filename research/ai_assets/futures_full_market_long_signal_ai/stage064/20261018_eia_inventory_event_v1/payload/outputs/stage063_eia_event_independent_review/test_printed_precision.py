"""Targeted independent precision tests only; no author module or full source run."""
from pathlib import Path
import unittest
from source_checks import parse_saved_stock

RAW=Path(__file__).resolve().parents[1]/'stage060_eia_report_import/excluded_raw_sources'


class PrintedPrecision(unittest.TestCase):
    def test_three_decimal_report_retains_official_difference(self):
        raw=(RAW/'eia_wpsr_2020_02_26.csv').read_bytes()
        got=parse_saved_stock(raw,'2020-02-21')
        # Printed levels imply -2.115 million; official unrounded difference is -2.114.
        self.assertEqual(got['Distillate Fuel Oil']['delta'],-2114.)
        self.assertEqual(got['Distillate Fuel Oil']['current'],138472.)

    def test_one_decimal_report_uses_its_own_printed_quantum(self):
        raw=(RAW/'eia_wpsr_2016_10_19.csv').read_bytes()
        got=parse_saved_stock(raw,'2016-10-14')
        self.assertEqual(got['Commercial (Excluding SPR)']['delta'],-5200.)
        self.assertEqual(got['Distillate Fuel Oil']['delta'],-1200.)

    def test_outside_printed_bound_remains_rejected(self):
        raw=(RAW/'eia_wpsr_2020_02_26.csv').read_bytes().replace(b'"-2.114"',b'"-2.100"')
        with self.assertRaises(AssertionError):parse_saved_stock(raw,'2020-02-21')

    def test_wrong_statistics_week_remains_rejected(self):
        raw=(RAW/'eia_wpsr_2020_02_26.csv').read_bytes()
        with self.assertRaises(AssertionError):parse_saved_stock(raw,'2020-02-28')


if __name__=='__main__':unittest.main(verbosity=2)
