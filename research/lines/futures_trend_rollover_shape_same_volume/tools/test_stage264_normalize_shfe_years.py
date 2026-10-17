"""Meaningful identity, placeholder, conflict and point-in-time boundaries."""
from datetime import date, timedelta
from pathlib import Path
import sqlite3
import tempfile
import unittest

import stage264_normalize_shfe_years as subject


MANIFEST = {"contract_epoch_id": "rb1505.SHFE@201505", "vt_symbol": "rb1505.SHFE",
            "product": "rb.SHFE", "contract_yyyymm": "201505", "first_main_date": "2015-01-05",
            "first_main_date_in_scope": "2015-01-05", "list_date": "unknown"}


def raw(**changes):
    row = dict(instrument="rb1505", date="20150105", open=10, high=12, low=9, close=11,
               volume=4, open_interest=7)
    row.update(changes)
    return row


def bar(day, **changes):
    row = dict(contract_epoch_id="rb1505.SHFE@201505", vt_symbol="rb1505.SHFE", product="rb.SHFE",
               date=day, open=10.0, high=12.0, low=9.0, close=11.0, volume=4.0,
               open_interest=7.0, source_year=int(day[:4]), raw_member="sample.xls", row=4)
    row.update(changes)
    return row


class AnnualRowBoundaryTests(unittest.TestCase):
    def test_real_xls_group_blanks_continue_only_until_footer(self):
        header = ["合约", "日期", "前收盘", "前结算", "开盘价", "最高价", "最低价", "收盘价",
                  "结算价", "涨跌1", "涨跌2", "成交量", "成交金额", "持仓量", ""]
        rows = [["所内合约行情报表"], ["日期：20150101-20151231"], header,
                ["rb1505", "20150105", 0, 0, 10, 12, 9, 11, 10, 0, 0, 4, 0, 7, ""],
                ["", "20150106", 0, 0, 10, 12, 9, 11, 10, 0, 0, 0, 0, 7, ""],
                ["注：", "3、 成交量持仓量单位为手，双边计算"],
                ["", "20150107", 0, 0, 10, 12, 9, 11, 10, 0, 0, 4, 0, 7, ""]]
        actual, metadata = subject.sheet_records(rows)
        self.assertEqual([(r["instrument"], r["date"], r["row"]) for r in actual],
                         [("rb1505", "20150105", 4), ("rb1505", "20150106", 5)])
        self.assertEqual(actual[0]["open_interest"], 7)
        self.assertEqual(metadata["header_row"], 3)

    def test_date_year_and_delivery_identity_cannot_relabel_2025_as_2015(self):
        actual = subject.normalize_record(raw(), 2015, "sample.xls", {MANIFEST["vt_symbol"]: MANIFEST})
        self.assertEqual((actual["date"], actual["contract_epoch_id"]), ("2015-01-05", "rb1505.SHFE@201505"))
        for changed, year, why in [(raw(date="20250105"), 2015, "source_year_mismatch"),
                                   (raw(date="20250105"), 2025, "delivery_epoch_mismatch"),
                                   (raw(date="20150601"), 2015, "after_delivery_month"),
                                   (raw(date="20150230"), 2015, "invalid_date"),
                                   (raw(instrument="rb0"), 2015, "not_real_contract")]:
            with self.subTest(raw=changed), self.assertRaisesRegex(ValueError, why):
                subject.normalize_record(changed, year, "sample.xls", {MANIFEST["vt_symbol"]: MANIFEST})

    def test_zero_no_trade_prices_nonfinite_and_negative_units_never_become_bars(self):
        for changed, why in [(raw(open=0, high=0, low=0, close=0, volume=0), "zero_price_no_trade_placeholder"),
                             (raw(open="", high="", low="", close=11, volume=0), "no_trade_missing_ohlc_placeholder"),
                             (raw(open=0), "nonpositive_ohlc"),
                             (raw(close=float("nan")), "nonfinite_numeric"),
                             (raw(high=float("inf")), "nonfinite_numeric"),
                             (raw(low=11.5), "inconsistent_ohlc"),
                             (raw(volume=-1), "negative_volume_or_open_interest"),
                             (raw(open_interest=-1), "negative_volume_or_open_interest")]:
            with self.subTest(raw=changed), self.assertRaisesRegex(ValueError, why):
                subject.normalize_record(changed, 2015, "sample.xls", {MANIFEST["vt_symbol"]: MANIFEST})

    def test_conflicting_duplicate_removes_all_versions_identical_duplicate_counts_once(self):
        records = [bar("2015-01-02"), bar("2015-01-02", row=5),
                   bar("2015-01-05"), bar("2015-01-05", close=10.5, row=6)]
        accepted, rejected, info = subject.resolve_duplicates(records)
        self.assertEqual([r["date"] for r in accepted], ["2015-01-02"])
        self.assertEqual(len(rejected), 2)
        self.assertEqual({r["reason"] for r in rejected}, {"conflicting_duplicate"})
        self.assertEqual(info["identical_duplicate_extra_rows"], 1)
        self.assertEqual(info["conflicting_duplicate_keys"], 1)


class ComparisonAndPITTests(unittest.TestCase):
    def test_unit_audit_separates_previous_close_oi_clock_from_same_day_scaling(self):
        official = [bar("2015-01-02", open_interest=14), bar("2015-01-05", volume=8, open_interest=16),
                    bar("2015-01-06", volume=8, open_interest=17)]
        differences = [dict(contract_epoch_id="rb1505.SHFE@201505", vt_symbol="rb1505.SHFE", date="2015-01-05",
                            official_volume=8, existing_volume=4, official_open_interest=16, existing_open_interest=7),
                       dict(contract_epoch_id="rb1505.SHFE@201505", vt_symbol="rb1505.SHFE", date="2015-01-06",
                            official_volume=8, existing_volume=8, official_open_interest=17, existing_open_interest=16)]
        result = subject.unit_diagnostics(official, differences)
        self.assertEqual(result["classification_counts"], {"volume_2x_and_previous_close_oi_2x_existing": 1, "other_difference": 1})
        self.assertEqual(result["by_year_product"][0]["year"], "2015")
        self.assertEqual(result["by_year_product"][0]["same_day_oi_ratio_counts"], {"16/7": 1, "17/16": 1})

    def test_all_six_fields_are_compared_without_replacing_either_source(self):
        official = [bar("2015-01-05", volume=8), bar("2015-01-06")]
        existing = [bar("2015-01-05", volume=4)]
        annotated, differences, info = subject.compare_existing(official, existing)
        self.assertEqual((annotated[0]["volume"], existing[0]["volume"]), (8, 4))
        self.assertTrue(annotated[0]["matches_existing_ohlc"])
        self.assertFalse(annotated[0]["matches_existing_volume"])
        self.assertTrue(annotated[0]["matches_existing_open_interest"])
        self.assertEqual(annotated[0]["overlap_status"], "different_existing")
        self.assertEqual(annotated[1]["overlap_status"], "new_date")
        self.assertEqual(differences[0]["different_fields"], "volume")
        self.assertEqual(info["overlap_days"], 1)

    def test_future_days_never_make_first_main_warmup_ready_and_conflict_isolated(self):
        existing = [bar((date(2014, 12, 31) - timedelta(days=n)).isoformat()) for n in range(118)]
        official = [bar("2015-01-02"), bar("2015-01-05"), bar("2015-02-01")]
        result = subject.contract_report(MANIFEST, official, existing, {"2015-01-05", "2015-01-06"})
        self.assertEqual(result["existing_valid_pre_main_days"], 118)
        self.assertEqual(result["official_new_pre_main_days"], 1)
        self.assertEqual(result["union_valid_pre_main_days"], 119)
        self.assertEqual(result["union_valid_through_first_main_days"], 120)
        self.assertFalse(result["AM120_ready_before"])
        self.assertTrue(result["AM120_coverage_ready_after"])
        self.assertEqual(result["main_days_in_scope_missing_after"], ["2015-01-06"])
        self.assertEqual(result["list_date"], "unknown")
        isolated = subject.contract_report(MANIFEST, official + [bar("2014-12-31", close=10.5)], existing,
                                           {"2015-01-05", "2015-01-06"})
        self.assertEqual(isolated["union_nonconflicting_through_first_main_days"], 119)
        self.assertFalse(isolated["AM120_nonconflicting_ready_after"])

    def test_existing_database_read_is_epoch_bound_and_does_not_mutate_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.db"
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE dbbardata(symbol TEXT,exchange TEXT,interval TEXT,datetime TEXT,open_price REAL,high_price REAL,low_price REAL,close_price REAL,volume REAL,open_interest REAL)")
            connection.executemany("INSERT INTO dbbardata VALUES ('rb1505','SHFE','d',?,10,12,9,11,4,7)",
                                   [("2015-01-05 00:00:00",), ("2025-01-05 00:00:00",)])
            connection.commit()
            connection.close()
            before = path.read_bytes()
            groups, _ = subject.read_existing(path, [MANIFEST])
            self.assertEqual([r["date"] for r in groups[MANIFEST["contract_epoch_id"]]], ["2015-01-05"])
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
