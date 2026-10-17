"""Fault injection for the independent daily-data acceptance checks."""
import unittest
import csv
import gzip
from pathlib import Path
import sqlite3
import tempfile
import stage266_independent_validate as v


def bar(**changes):
    row = dict(contract_epoch_id="DCE.JM.202701", exchange="DCE", product="JM",
               source_symbol="jm2701", contract_yyyymm="202701", trade_date="2026-09-01",
               open=1729.0, high=1741.0, low=1658.5, close=1694.0, volume=1609673.0,
               close_oi=579033.0, open_interest=579033.0, open_oi=636470.0,
               native_volume=1609673.0, native_close_oi=579033.0, native_open_oi=636470.0,
               volume_factor=1.0, oi_factor=1.0, open_oi_status="source_observed",
               quality_status="accepted", train_eligible=1, legacy108_row_usable=1,
               source_id="tq_recent_sample", source_locator='{"row":2}', priority=400)
    row.update(changes)
    if "contract_epoch_id" not in changes:
        row["contract_epoch_id"] = f"{row['exchange']}.{row['product']}.{row['contract_yyyymm']}"
    return row


class SemanticTests(unittest.TestCase):
    def check(self, row):
        self.assertTrue(callable(getattr(v, "semantic_violations", None)), "independent semantic checks must exist")
        return v.semantic_violations(row, cutoff="2026-10-16")

    def test_unmodified_real_tq_example_passes(self):
        self.assertEqual(self.check(bar()), [])

    def test_positive_flat_zero_volume_cannot_be_training(self):
        self.assertIn("nonpositive_volume_in_accepted", self.check(bar(open=10, high=10, low=10, close=10, volume=0, native_volume=0)))

    def test_invalid_geometry_cannot_be_training(self):
        self.assertIn("invalid_ohlc_geometry", self.check(bar(close=1742)))

    def test_nan_quantity_rejected(self):
        self.assertIn("invalid_close_oi", self.check(bar(close_oi=float("nan"))))

    def test_negative_oi_rejected(self):
        self.assertIn("invalid_close_oi", self.check(bar(close_oi=-1)))

    def test_open_interest_must_alias_closing_not_opening(self):
        self.assertIn("open_interest_not_close_alias", self.check(bar(open_interest=636470)))

    def test_missing_open_oi_is_explicit_and_not_imputed(self):
        self.assertEqual(self.check(bar(open_oi=None, native_open_oi=None, open_oi_status="missing_not_imputed", legacy108_row_usable=0)), [])

    def test_close_oi_cannot_be_copied_into_missing_open_oi(self):
        self.assertIn("missing_open_oi_was_imputed", self.check(bar(open_oi=579033, native_open_oi=None, open_oi_status="missing_not_imputed")))

    def test_observed_open_oi_needs_native_observation(self):
        self.assertIn("observed_open_oi_missing_native", self.check(bar(native_open_oi=None)))

    def test_declared_half_quantity_factor_is_checked(self):
        self.assertEqual(self.check(bar(native_volume=3219346, native_close_oi=1158066, native_open_oi=1272940, volume_factor=.5, oi_factor=.5)), [])
        self.assertIn("volume_factor_mismatch", self.check(bar(volume_factor=.5)))

    def test_future_formed_trade_date_rejected(self):
        self.assertIn("after_cutoff", self.check(bar(trade_date="2026-10-19")))

    def test_contract_month_must_match_full_epoch(self):
        self.assertIn("symbol_delivery_month_mismatch", self.check(bar(contract_yyyymm="201701")))

    def test_czce_three_digit_code_uses_declared_full_epoch(self):
        self.assertEqual(self.check(bar(exchange="CZCE", product="CF", source_symbol="CF701", contract_yyyymm="202701")), [])

    def test_F_suffix_kept_separate_from_product(self):
        self.assertEqual(self.check(bar(product="L_F", source_symbol="l2611F", contract_yyyymm="202611")), [])

    def test_exchange_prefixed_native_symbol_preserves_identity(self):
        self.assertEqual(self.check(bar(source_symbol="DCE.jm2701")), [])

    def test_epoch_id_cannot_disagree_with_delivery_columns(self):
        self.assertIn("contract_epoch_not_canonical_identity", self.check(bar(contract_epoch_id="DCE.JM.201701")))


class SourceTests(unittest.TestCase):
    def check(self, row, raw, family="tq_recent", close_field="close_oi"):
        self.assertTrue(callable(getattr(v, "source_violations", None)), "independent source comparison must exist")
        return v.source_violations(row, raw, family=family, close_field=close_field, open_field="open_oi")

    def test_same_source_raw_record_matches(self):
        row = bar()
        raw = {k: row[k] for k in ("open", "high", "low", "close", "volume", "open_oi", "close_oi")}
        self.assertEqual(self.check(row, raw), [])

    def test_TQ_open_oi_is_never_the_close_source(self):
        row = bar()
        self.assertIn("forbidden_open_oi_as_close_source", self.check(row, row, close_field="open_oi"))

    def test_legacy_TQ_generic_oi_alias_is_not_proof_of_close_oi(self):
        row = bar()
        self.assertIn("TQ_close_oi_field_must_be_explicit_close_oi", self.check(row, row, family="legacy_tq", close_field="open_interest"))

    def test_one_field_price_blend_detected(self):
        row = bar()
        self.assertIn("source_close_mismatch", self.check(row, {**row, "close": row["close"] + 1}))


class UnitContractTests(unittest.TestCase):
    def units(self):
        return {"rqalpha": {"rules": [
                    {"exchanges": ["DCE"], "start": "2010-01-01", "end": "2019-12-31", "volume_factor": .5, "close_oi_factor": .5},
                    {"exchanges": ["DCE", "CFFEX"], "start": "2020-01-01", "end": "2026-09-30", "volume_factor": 1., "close_oi_factor": 1.},
                    {"exchanges": ["CFFEX"], "start": "2010-01-01", "end": "2019-12-31", "volume_factor": 1., "close_oi_factor": 1.}]},
                "official": {"accepted_regime_factors": {"double": .5}},
                "old_tq": {"volume_factor": 1., "close_oi_factor": 1.}}

    def check(self, family, ex, day, raw=None):
        self.assertTrue(callable(getattr(v, "expected_factors", None)), "frozen unit-contract rule check must exist")
        return v.expected_factors(self.units(), family, ex, day, raw or {})

    def test_pre2020_rq_double_side_and_CFFEX_single(self):
        self.assertEqual(self.check("rqalpha", "DCE", "2019-12-31"), (.5, .5))
        self.assertEqual(self.check("rqalpha", "CFFEX", "2019-12-31"), (1., 1.))

    def test_post2020_and_already_single_old_TQ(self):
        self.assertEqual(self.check("rqalpha", "DCE", "2020-01-02"), (1., 1.))
        self.assertEqual(self.check("old_tq", "DCE", "2019-12-31"), (1., 1.))

    def test_unknown_official_units_never_inferred_from_year(self):
        with self.assertRaises(ValueError):
            self.check("official", "SHFE", "2026-01-05", {"unit_regime": "unknown"})

    def test_no_rule_is_fail_closed(self):
        with self.assertRaises(ValueError):
            self.check("rqalpha", "DCE", "2009-12-31")


class NativeLocatorTests(unittest.TestCase):
    def test_csv_physical_row_two_is_first_data_and_does_not_strip_BOM_column(self):
        with tempfile.TemporaryDirectory() as folder:
            for compressed in (False, True):
                path = Path(folder) / ("raw.csv.gz" if compressed else "raw.csv")
                opener = gzip.open if compressed else Path.open
                with opener(path, "wt", encoding="utf-8-sig", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=["trade_date", "close"])
                    writer.writeheader(); writer.writerows([{"trade_date": "2026-09-01", "close": 1}, {"trade_date": "2026-09-02", "close": 2}])
                source = {"source_id": str(compressed), "family": "old_tq", "path": str(path)}
                reader = v.NativeReader()
                self.assertEqual(reader.get(source, {"row": 2})["trade_date"], "2026-09-01")
                self.assertEqual(reader.get(source, {"row": 3})["close"], "2")
                with self.assertRaises(ValueError):
                    reader.get(source, {"row": 1})

    def test_read_only_connection_forbids_write(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.sqlite"
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE evidence (value INTEGER)")
            before = v.sha(path)
            db = v.read_only_connection(path)
            with self.assertRaises(sqlite3.OperationalError):
                db.execute("INSERT INTO evidence VALUES (1)")
            db.close()
            self.assertEqual(v.sha(path), before)

    def test_official_same_price_wrong_contract_cannot_pass(self):
        row = bar()
        raw = {k: row[k] for k in ("exchange", "product", "contract_yyyymm", "source_symbol")}
        self.assertEqual(v.csv_source_identity_violations(row, raw, "official"), [])
        self.assertIn("official_source_contract_yyyymm_mismatch", v.csv_source_identity_violations(row, {**raw, "contract_yyyymm": "201701"}, "official"))

    def test_recent_TQ_must_be_86400_seconds_and_same_symbol(self):
        row = bar()
        self.assertEqual(v.csv_source_identity_violations(row, {"symbol": "DCE.jm2701", "duration": "86400"}, "recent_tq"), [])
        errors = v.csv_source_identity_violations(row, {"symbol": "DCE.jm2705", "duration": "60"}, "recent_tq")
        self.assertIn("TQ_source_symbol_mismatch", errors)
        self.assertIn("TQ_source_not_daily", errors)


if __name__ == "__main__":
    unittest.main()
