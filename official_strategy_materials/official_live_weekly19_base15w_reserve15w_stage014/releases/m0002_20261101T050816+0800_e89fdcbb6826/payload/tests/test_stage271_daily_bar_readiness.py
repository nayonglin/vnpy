from pathlib import Path
import csv
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'examples/portfolio_backtesting'))
from qmt_roll_official_live_daily_bar_readiness import (
    OFFICIAL_LIVE_DAILY_PRODUCTS, DailyBarReadinessError, validate_target_daily_bars,
)


class DailyBarReadinessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.mapping = self.root / 'mapping.csv'
        self.database = self.root / 'database.db'
        self.target = '2026-10-19'
        self.rows = []
        with sqlite3.connect(self.database) as conn:
            conn.execute('CREATE TABLE dbbardata(symbol TEXT, exchange TEXT, interval TEXT, datetime TEXT, open_price REAL, high_price REAL, low_price REAL, close_price REAL, volume REAL, open_interest REAL)')
            for product in OFFICIAL_LIVE_DAILY_PRODUCTS:
                name, exchange = product.split('.')
                contract = name + ('701' if exchange == 'CZCE' else '2701')
                self.rows.append({'date': self.target, 'continuous_symbol_vt': product, 'main_contract_vt': contract + '.' + exchange})
                conn.execute('INSERT INTO dbbardata VALUES (?,?,?,?,?,?,?,?,?,?)', (contract, exchange, 'd', self.target + ' 00:00:00', 100, 110, 90, 105, 1000, 2000))
        self.write_mapping()

    def write_mapping(self):
        with self.mapping.open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=['date', 'continuous_symbol_vt', 'main_contract_vt'])
            writer.writeheader()
            writer.writerows(self.rows)

    def check(self):
        return validate_target_daily_bars(database_path=self.database, mapping_path=self.mapping, target_date=self.target)

    def test_all_nineteen_main_contracts_are_current(self):
        result = self.check()
        self.assertEqual(19, result['complete_product_count'])
        self.assertEqual(set(OFFICIAL_LIVE_DAILY_PRODUCTS), set(result['contracts']))

    def test_one_stale_product_blocks_even_when_eighteen_are_current(self):
        with sqlite3.connect(self.database) as conn:
            conn.execute("UPDATE dbbardata SET datetime='2026-10-16 00:00:00' WHERE symbol=?", (self.rows[-1]['main_contract_vt'].split('.')[0],))
        with self.assertRaisesRegex(DailyBarReadinessError, 'daily_bar_missing_or_duplicate'):
            self.check()

    def test_missing_target_mapping_blocks(self):
        self.rows.pop()
        self.write_mapping()
        with self.assertRaisesRegex(DailyBarReadinessError, 'mapping_incomplete'):
            self.check()

    def test_duplicate_mapping_blocks(self):
        self.rows.append(self.rows[0])
        self.write_mapping()
        with self.assertRaisesRegex(DailyBarReadinessError, 'duplicate_mapping'):
            self.check()

    def test_different_product_contract_is_rejected(self):
        self.rows[0]['main_contract_vt'] = 'rb2701.SHFE'
        self.write_mapping()
        with self.assertRaisesRegex(DailyBarReadinessError, 'mapping_contract_invalid'):
            self.check()

    def test_duplicate_daily_bar_blocks(self):
        with sqlite3.connect(self.database) as conn:
            conn.execute('INSERT INTO dbbardata SELECT * FROM dbbardata LIMIT 1')
        with self.assertRaisesRegex(DailyBarReadinessError, 'daily_bar_missing_or_duplicate'):
            self.check()

    def test_bad_prices_volume_and_nulls_block(self):
        for field, value in [('high_price', 99), ('volume', -1), ('open_interest', None), ('close_price', float('inf'))]:
            with self.subTest(field=field):
                with sqlite3.connect(self.database) as conn:
                    conn.execute(f'UPDATE dbbardata SET {field}=? WHERE rowid=1', (value,))
                with self.assertRaisesRegex(DailyBarReadinessError, 'daily_bar_invalid'):
                    self.check()
                with sqlite3.connect(self.database) as conn:
                    conn.execute('UPDATE dbbardata SET high_price=110,volume=1000,open_interest=2000,close_price=105 WHERE rowid=1')

    def test_unknown_products_do_not_replace_required_product(self):
        self.rows[-1]['continuous_symbol_vt'] = 'unknown.SHFE'
        self.write_mapping()
        with self.assertRaisesRegex(DailyBarReadinessError, 'mapping_incomplete'):
            self.check()


if __name__ == '__main__':
    unittest.main()
