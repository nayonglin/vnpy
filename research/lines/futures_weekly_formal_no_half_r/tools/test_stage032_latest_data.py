"""Stage032 additive daily data gates: real fixtures, no network or strategy."""
from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util
import json
import sqlite3
import unittest

import pandas as pd

MODULE = Path(__file__).with_name('stage032_latest_data.py')


def load():
    spec = importlib.util.spec_from_file_location('stage032_latest_data', MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AvailabilityTests(unittest.TestCase):
    def test_daily_data_tool_exists(self):
        self.assertTrue(MODULE.is_file(), 'immutable additive daily tool missing')


@unittest.skipUnless(MODULE.is_file(), 'implementation not present yet')
class DailyAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.m = load()
        self.epoch = dict(vt_symbol='SH701.CZCE', contract_epoch_id='CZCE.SH.202701',
                          contract_yyyymm='202701', listed_date='2026-01-01',
                          delisted_date='2027-01-31', lifecycle_status='known_vendor_listing_delisting')
        self.row = dict(vt_symbol='SH701.CZCE', date='2026-10-28', open=10, high=12,
                        low=9, close=11, volume=7, close_oi=3, duration=86400,
                        source_path='/tmp/proof.csv', source_sha256='a'*64,
                        source_locator='{"date":"2026-10-28"}', source_id='test_Tq_daily_close_oi')

    def test_real_close_oi_and_explicit_epoch_are_preserved(self):
        accepted, rejected = self.m.admit_rows([self.row], [self.epoch], {'2026-10-27', '2026-10-28'})
        self.assertEqual(rejected, [])
        self.assertEqual(accepted[0]['close_oi'], 3.0)
        self.assertEqual(accepted[0]['contract_epoch_id'], 'CZCE.SH.202701')

    def test_zero_volume_is_classification_only_and_never_a_bar(self):
        accepted, rejected = self.m.admit_rows([{**self.row, 'volume': 0}], [self.epoch], {'2026-10-28'})
        self.assertEqual(accepted, [])
        self.assertEqual(rejected[0]['classification'], 'raw_zero_or_invalid_not_bar')

    def test_nonfinite_prices_and_impossible_ohlc_are_rejected(self):
        for patch in [{'close': float('nan')}, {'high': 10}, {'close_oi': -1}, {'low': 0}]:
            with self.subTest(patch=patch):
                accepted, rejected = self.m.admit_rows([{**self.row, **patch}], [self.epoch], {'2026-10-28'})
                self.assertEqual(accepted, [])
                self.assertEqual(len(rejected), 1)

    def test_future_forming_and_old_dates_cannot_be_admitted(self):
        for day in ['2026-10-26', '2026-10-29']:
            with self.assertRaisesRegex(ValueError, 'outside_predeclared_append_days'):
                self.m.admit_rows([{**self.row, 'date': day}], [self.epoch], {'2026-10-27', '2026-10-28'})

    def test_intraday_rows_cannot_masquerade_as_daily(self):
        with self.assertRaisesRegex(ValueError, 'not_real_daily'):
            self.m.admit_rows([{**self.row, 'duration': 60}], [self.epoch], {'2026-10-28'})

    def test_same_native_symbol_in_two_eligible_epochs_fails(self):
        with self.assertRaisesRegex(ValueError, 'physical_identity_not_unique'):
            self.m.admit_rows([self.row], [self.epoch, dict(self.epoch)], {'2026-10-28'})

    def test_epoch_month_and_lifecycle_mismatch_fail(self):
        for patch in [{'contract_epoch_id': 'CZCE.SH.201701'}, {'listed_date': '2026-10-29'}]:
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                self.m.admit_rows([self.row], [{**self.epoch, **patch}], {'2026-10-28'})

    def test_duplicate_physical_day_fails_instead_of_last_wins(self):
        with self.assertRaisesRegex(ValueError, 'duplicate_new_daily'):
            self.m.admit_rows([self.row, dict(self.row)], [self.epoch], {'2026-10-28'})

    def test_provenance_and_same_day_close_oi_are_required(self):
        for key in ['source_path', 'source_sha256', 'source_locator', 'close_oi']:
            row = dict(self.row); row.pop(key)
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.m.admit_rows([row], [self.epoch], {'2026-10-28'})


@unittest.skipUnless(MODULE.is_file(), 'implementation not present yet')
class MappingAndAppendTests(unittest.TestCase):
    def setUp(self):
        self.m = load()

    def test_mapping_requires_every_declared_product_day_once(self):
        products = ['SH.CZCE', 'cu.SHFE']
        rows = [dict(date=d, continuous_symbol_vt=p, main_contract_vt=s)
                for d in ['2026-10-27', '2026-10-28']
                for p, s in [('SH.CZCE', 'SH701.CZCE'), ('cu.SHFE', 'cu2612.SHFE')]]
        self.m.validate_mapping(pd.DataFrame(rows), products, ['2026-10-27', '2026-10-28'])
        for bad in [rows[:-1], rows+[rows[0]], rows+[{**rows[0], 'continuous_symbol_vt': 'jd.DCE'}]]:
            with self.assertRaises(ValueError):
                self.m.validate_mapping(pd.DataFrame(bad), products, ['2026-10-27', '2026-10-28'])

    def test_missing_required_held_or_execution_day_blocks_data_ready(self):
        with self.assertRaisesRegex(ValueError, 'required_physical_daily_missing'):
            self.m.require_daily_keys([dict(vt_symbol='SH701.CZCE', date='2026-10-28')],
                                      {('SH701.CZCE', '2026-10-28'), ('SH611.CZCE', '2026-10-28')})

    def test_additive_sqlite_preserves_all_old_fields_and_overview(self):
        with TemporaryDirectory() as tmp:
            base, new = Path(tmp)/'old.sqlite', Path(tmp)/'new.sqlite'
            with sqlite3.connect(base) as db:
                db.executescript('CREATE TABLE dbbardata (symbol TEXT,exchange TEXT,datetime TEXT,interval TEXT,volume REAL,turnover REAL,open_interest REAL,open_price REAL,high_price REAL,low_price REAL,close_price REAL);CREATE TABLE dbbaroverview(symbol TEXT,exchange TEXT,interval TEXT,count INTEGER,start TEXT,end TEXT);')
                db.execute("INSERT INTO dbbardata VALUES('SH701','CZCE','2026-10-26 00:00:00','d',13,17,19,20,22,18,21)")
            before = base.read_bytes()
            rows = [dict(vt_symbol='SH701.CZCE', date='2026-10-28', open=30,high=32,low=29,close=31,volume=23,close_oi=27)]
            proof = self.m.append_sqlite(base, new, rows)
            self.assertTrue(proof['old_database_all_rows_preserved'])
            self.assertEqual(base.read_bytes(), before)
            with sqlite3.connect(new) as db:
                self.assertEqual(db.execute("select turnover,open_interest,close_price from dbbardata where datetime='2026-10-26 00:00:00'").fetchone(), (17.0,19.0,21.0))
                self.assertEqual(db.execute("select open_interest,volume from dbbardata where datetime='2026-10-28 00:00:00'").fetchone(), (27.0,23.0))
                self.assertEqual(db.execute('select count,start,end from dbbaroverview').fetchone(), (2,'2026-10-26 00:00:00','2026-10-28 00:00:00'))

    def test_sqlite_refuses_existing_key_and_existing_snapshot(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'base.sqlite'
            with sqlite3.connect(p) as db:
                db.executescript('CREATE TABLE dbbardata (symbol TEXT,exchange TEXT,datetime TEXT,interval TEXT,volume REAL,turnover REAL,open_interest REAL,open_price REAL,high_price REAL,low_price REAL,close_price REAL);CREATE TABLE dbbaroverview(symbol TEXT,exchange TEXT,interval TEXT,count INTEGER,start TEXT,end TEXT);')
                db.execute("INSERT INTO dbbardata VALUES('SH701','CZCE','2026-10-28 00:00:00','d',1,0,2,3,4,2,3)")
            row=dict(vt_symbol='SH701.CZCE',date='2026-10-28',open=3,high=4,low=2,close=3,volume=1,close_oi=2)
            with self.assertRaisesRegex(ValueError,'new_key_already_in_database'):
                self.m.append_sqlite(p,Path(tmp)/'new.sqlite',[row])
            with self.assertRaisesRegex(ValueError,'immutable_snapshot_exists'):
                self.m.append_sqlite(p,p,[row])


if __name__ == '__main__':
    unittest.main()
