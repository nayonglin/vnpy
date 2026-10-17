"""Identity and actual-bar boundaries for the read-only Stage264 manifest."""
import csv
from pathlib import Path
import sqlite3
import tempfile
import unittest

import stage264_build_daily_manifest as manifest


class IdentityTests(unittest.TestCase):
    def test_three_digit_code_is_bound_to_its_date_and_delivery_year(self):
        self.assertEqual(manifest.contract_identity("CF505.CZCE", "2014-11-12")["contract_yyyymm"], "201505")
        self.assertEqual(manifest.contract_identity("CF505.CZCE", "2024-11-12")["contract_yyyymm"], "202505")
        self.assertEqual(manifest.contract_identity("AP001.CZCE", "2019-09-18")["contract_epoch_id"], "AP001.CZCE@202001")

    def test_invalid_month_continuous_code_and_remote_delivery_fail_closed(self):
        for vt, day in [("CF513.CZCE", "2015-01-05"), ("CF.CZCE", "2015-01-05"),
                        ("CF505.CZCE", "2016-01-05"), ("rb1505.SHFE", "2025-01-05")]:
            with self.subTest(vt=vt, day=day), self.assertRaises(ValueError):
                manifest.contract_identity(vt, day)

    def test_vendor_codes_use_full_delivery_identity_without_asserting_catalog_existence(self):
        actual = manifest.contract_identity("CF505.CZCE", "2014-11-12")
        self.assertEqual(actual["rqdata_order_book_id"], "CF1505")
        self.assertEqual(actual["tushare_ts_code"], "CF1505.ZCE")
        self.assertEqual(actual["tq_yymm_alias_candidate"], "CZCE.CF1505")
        self.assertEqual(actual["tq_yymm_alias_status"], "unverified_alias_not_officially_documented")

    def test_legacy_methanol_vendor_identity_requires_metadata_instead_of_auto_renaming(self):
        legacy = manifest.contract_identity("MA505.CZCE", "2014-11-12")
        self.assertEqual(legacy["vt_symbol"], "MA505.CZCE")
        self.assertEqual(legacy["rqdata_order_book_id"], "unknown")
        self.assertEqual(legacy["rqdata_normalized_format_candidate"], "MA1505")
        self.assertEqual(legacy["rqdata_historical_alias_candidate"], "ME1505")
        modern = manifest.contract_identity("MA509.CZCE", "2015-04-01")
        self.assertEqual(modern["rqdata_order_book_id"], "MA1509")
        self.assertEqual(modern["rqdata_historical_alias_candidate"], "none_documented")


class ActualBarTests(unittest.TestCase):
    def test_reused_code_cannot_lend_old_bars_or_future_bars_to_warmup(self):
        rows = [dict(datetime=d + " 00:00:00", open_price=10, high_price=11, low_price=9, close_price=10)
                for d in ["2014-11-11", "2014-11-12", "2015-01-05", "2024-11-11", "2024-11-12"]]
        actual = manifest.summarize_bars(rows, "CF505.CZCE", "201505", "2014-11-12", "2015-01-05")
        self.assertEqual(actual["history_count_before_first_main"], 1)
        self.assertEqual(actual["history_count_through_first_main"], 2)
        self.assertEqual(actual["source_scope_history_count_through_first_main_in_scope"], 1)
        self.assertEqual(actual["same_epoch_valid_daily_count"], 3)
        self.assertEqual(actual["same_epoch_existing_last_date"], "2015-01-05")
        self.assertEqual(actual["needed_bars_lower_bound"], 118)

    def test_duplicate_days_and_invalid_ohlc_do_not_count_as_usable_history(self):
        rows = [dict(datetime=d, open_price=10, high_price=11, low_price=9, close_price=close)
                for d, close in [("2015-01-05 00:00:00", 10), ("2015-01-05 15:00:00", 10),
                                 ("2015-01-06 00:00:00", -1), ("2015-01-07 00:00:00", 10)]]
        actual = manifest.summarize_bars(rows, "CF505.CZCE", "201505", "2015-01-07", "2015-01-07")
        self.assertEqual(actual["same_epoch_valid_daily_count"], 1)
        self.assertEqual(actual["same_epoch_duplicate_days"], 1)
        self.assertEqual(actual["same_epoch_invalid_ohlc_rows"], 1)

    def test_global_first_main_is_not_clipped_to_research_start_and_database_is_readonly(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            mapping = base / "mapping.csv"
            fields = ["date", "product", "exchange", "continuous_symbol_vt", "main_contract_vt", "main_contract_tq"]
            with mapping.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                for day, vt, tq in [("2014-11-12", "CF505.CZCE", "CZCE.CF505"),
                                    ("2015-01-05", "CF505.CZCE", "CZCE.CF505"),
                                    ("2015-01-06", "", ""),
                                    ("2015-01-07", "CF505.CZCE", "CZCE.CF505"),
                                    ("2024-11-12", "CF505.CZCE", "CZCE.CF505")]:
                    writer.writerow(dict(date=day, product="CF", exchange="CZCE", continuous_symbol_vt="CF.CZCE",
                                         main_contract_vt=vt, main_contract_tq=tq))
            database = base / "database.db"
            connection = sqlite3.connect(database)
            connection.execute("CREATE TABLE dbbardata(symbol TEXT, exchange TEXT, interval TEXT, datetime TEXT, open_price REAL, high_price REAL, low_price REAL, close_price REAL)")
            connection.executemany("INSERT INTO dbbardata VALUES ('CF505','CZCE','d',?,10,11,9,10)",
                                   [("2014-11-11 00:00:00",), ("2015-01-05 00:00:00",), ("2024-11-11 00:00:00",)])
            connection.commit()
            connection.close()
            before = database.read_bytes()
            contracts, days = manifest.build_manifest(mapping, database, {"CF.CZCE"})
            self.assertEqual(database.read_bytes(), before)
            self.assertEqual(len(contracts), 1)
            self.assertEqual(len(days), 2)
            self.assertTrue(days[0]["coverage_ok"])
            self.assertEqual(days[1]["actual_daily_bar_rows"], 0)
            self.assertFalse(days[1]["coverage_ok"])
            self.assertEqual(contracts[0]["first_main_date"], "2014-11-12")
            self.assertEqual(contracts[0]["first_main_date_in_scope"], "2015-01-05")
            self.assertEqual(contracts[0]["list_date"], "unknown")
            self.assertEqual(contracts[0]["full_lifetime_download_start"], "unknown")
            self.assertEqual(contracts[0]["download_status"], "pending_metadata_and_vendor_probe")


if __name__ == "__main__":
    unittest.main()
