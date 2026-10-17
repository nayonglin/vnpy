"""Inventory all real futures in the frozen public daily bundle, read-only.

Raw data is retained. Zero-volume vendor flat candles never count as traded
observations; no strategy, main database, orders, or model is run here.
"""
from __future__ import annotations
from collections import Counter, defaultdict
import csv
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
import pickle
import re

LINE = Path(__file__).resolve().parents[1]
BASE = LINE / 'outputs/stage265_deep_daily/rqalpha'
ASOF, TARGET_START = 20260930, 20100101
EXCHANGES = {'SHFE', 'INE', 'DCE', 'CZCE', 'CFFEX', 'GFEX'}


class PrimitivesOnly(pickle.Unpickler):
    def find_class(self, module, name):
        raise pickle.UnpicklingError('metadata global execution forbidden')

    def persistent_load(self, pid):
        raise pickle.UnpicklingError('metadata persistent references forbidden')


def source_day(value):
    number = int(value)
    if number >= 100000000:
        if number % 1000000:
            raise ValueError('daily source timestamp is not midnight')
        number //= 1000000
    if len(str(number)) != 8:
        raise ValueError('invalid daily date encoding')
    text = str(number)
    return date.fromisoformat(f'{text[:4]}-{text[4:6]}-{text[6:]}').isoformat()


def contract_id(item):
    maturity = date.fromisoformat(item['maturity_date'])
    exchange, product = item['exchange'], item['underlying_symbol']
    if exchange not in EXCHANGES or not product:
        raise ValueError('unsupported future identity')
    match = re.fullmatch(r'([A-Z]+)([0-9]{4})(F?)', item.get('order_book_id', ''))
    if not match:
        raise ValueError('continuous or unresolved contract code')
    prefix, digits, suffix = match.groups()
    if product != prefix + ('_F' if suffix else ''):
        raise ValueError('metadata product and source code disagree')
    month = int(digits[-2:])
    years = [year for year in range(maturity.year - 1, maturity.year + 2) if year % 100 == int(digits[:2])]
    if not years or not 1 <= month <= 12:
        raise ValueError('contract year or month unresolved')
    year = min(years, key=lambda candidate: abs(candidate - maturity.year))
    # Contract month comes from the exchange code. Last trade/maturity can be
    # in the previous month (e.g. SC, FU and monthly-average futures).
    return f'{exchange}.{product}.{year:04d}{month:02d}'


def observation_status(op, hi, lo, cl, volume, oi):
    if math.isfinite(volume) and volume == 0:
        return 'no_trade_zero_volume'
    if not math.isfinite(volume) or volume < 0 or not math.isfinite(oi) or oi < 0:
        return 'invalid_quantity'
    if all(math.isfinite(x) and x > 0 for x in (op, hi, lo, cl)) and lo <= min(op, cl) <= max(op, cl) <= hi:
        return 'valid_traded_ohlc'
    return 'invalid_traded_ohlc'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    import h5py
    import numpy as np
    with (BASE / 'instruments.pk').open('rb') as stream:
        metadata = PrimitivesOnly(stream).load()
    futures = {x['order_book_id']: x for x in metadata if x.get('type') == 'Future'}
    calendars = np.load(BASE / 'trading_dates.npy', allow_pickle=False)
    calendar_set = set(int(x) for x in calendars)
    inventory, bad_rows, excluded = [], [], []
    by_exchange, by_product = defaultdict(Counter), defaultdict(Counter)
    required = {'datetime', 'open', 'high', 'low', 'close', 'volume', 'open_interest'}
    with h5py.File(BASE / 'futures.h5', 'r') as store:
        datasets = set(store)
        for source_symbol in sorted(datasets | set(futures)):
            item = futures.get(source_symbol)
            if not item:
                excluded.append({'source_symbol': source_symbol, 'reason': 'missing_future_metadata'})
                continue
            try:
                identity = contract_id(item)
            except (ValueError, KeyError, TypeError):
                excluded.append({'source_symbol': source_symbol, 'reason': 'continuous_or_unresolved_maturity'})
                continue
            row = {'contract_id': identity, 'source_symbol': source_symbol,
                'exchange': item['exchange'], 'product': item['underlying_symbol'],
                'source_trading_code': item.get('trading_code'), 'listed_date': item.get('listed_date'),
                'delisted_date': item.get('de_listed_date'), 'maturity_date': item.get('maturity_date'),
                'dataset_exists': source_symbol in datasets, 'raw_rows': 0,
                'valid_traded_ohlc': 0, 'no_trade_zero_volume': 0, 'invalid_traded_ohlc': 0,
                'invalid_quantity': 0, 'invalid_date_or_time': 0, 'duplicate_dates': 0,
                'before_metadata_listing': 0, 'after_metadata_delisting': 0,
                'expected_target_raw_observations': 0, 'missing_target_raw_observations': 0,
                'first_date': None, 'last_date': None}
            actual_dates = set()
            if source_symbol in datasets:
                dataset = store[source_symbol]
                if not required <= set(dataset.dtype.names or []):
                    raise ValueError(f'missing required source fields: {source_symbol}')
                records = dataset[:]
                row['raw_rows'] = len(records)
                seen = set()
                listed = str(item.get('listed_date', '0000-00-00'))
                ended = str(item.get('de_listed_date', '9999-12-31'))
                for record in records:
                    try:
                        day = source_day(record['datetime'])
                        ymd = int(day.replace('-', ''))
                        if ymd not in calendar_set:
                            raise ValueError('not in vendor trading calendar')
                    except ValueError:
                        row['invalid_date_or_time'] += 1
                        continue
                    row['duplicate_dates'] += day in seen
                    seen.add(day)
                    actual_dates.add(ymd)
                    row['before_metadata_listing'] += day < listed
                    row['after_metadata_delisting'] += day > ended
                    status = observation_status(*[float(record[x]) for x in ['open', 'high', 'low', 'close', 'volume', 'open_interest']])
                    row[status] += 1
                    if status in {'invalid_traded_ohlc', 'invalid_quantity'}:
                        bad_rows.append({'contract_id': identity, 'source_symbol': source_symbol,
                            'exchange': row['exchange'], 'product': row['product'], 'date': day,
                            **{key: float(record[key]) for key in ['open', 'high', 'low', 'close', 'volume', 'open_interest']}, 'reason': status})
                if seen:
                    row['first_date'], row['last_date'] = min(seen), max(seen)
            try:
                listed_ymd = int(date.fromisoformat(item['listed_date']).strftime('%Y%m%d'))
                ended_ymd = int(date.fromisoformat(item['de_listed_date']).strftime('%Y%m%d'))
                lo, hi = max(TARGET_START, listed_ymd), min(ASOF, ended_ymd)
                expected = {int(x) for x in calendars if lo <= x <= hi}
                row['expected_target_raw_observations'] = len(expected)
                row['missing_target_raw_observations'] = len(expected - actual_dates)
                row['missing_target_raw_examples'] = '|'.join(str(x) for x in sorted(expected - actual_dates)[:5])
                row['target_lifetime_status'] = 'in_target' if expected else 'outside_target_lifetime'
            except (KeyError, ValueError, TypeError):
                row['target_lifetime_status'] = 'metadata_dates_unknown'
                row['missing_target_raw_examples'] = ''
            inventory.append(row)
            for group in [by_exchange[row['exchange']], by_product[row['exchange'] + '.' + row['product']]]:
                group['real_contracts'] += 1
                group['datasets'] += int(row['dataset_exists'])
                for key in ['raw_rows', 'valid_traded_ohlc', 'no_trade_zero_volume', 'invalid_traded_ohlc', 'invalid_quantity', 'missing_target_raw_observations', 'before_metadata_listing']:
                    group[key] += row[key]
    def write_csv(name, rows, columns):
        with (BASE / name).open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, lineterminator='\n')
            writer.writeheader()
            writer.writerows(rows)
    write_csv('full_market_contract_inventory.csv', inventory, list(inventory[0]))
    write_csv('invalid_traded_observations.csv', bad_rows, ['contract_id', 'source_symbol', 'exchange', 'product', 'date', 'open', 'high', 'low', 'close', 'volume', 'open_interest', 'reason'])
    write_csv('excluded_continuous_or_unresolved.csv', excluded, ['source_symbol', 'reason'])
    (BASE / 'futures_metadata.json').write_text(json.dumps(list(futures.values()), ensure_ascii=False, indent=2))
    summary = {'generated_at': datetime.now().astimezone().isoformat(), 'scope': 'all six Chinese futures exchanges; all real delivery contracts; raw bundle native units',
        'target_start': '2010-01-01', 'bundle_cutoff': '2026-09-30', 'h5_total_datasets': len(datasets),
        'future_metadata_records': len(futures), 'real_metadata_contracts': len(inventory),
        'real_contracts_with_dataset': sum(r['dataset_exists'] for r in inventory),
        'excluded_continuous_or_unresolved': len(excluded), 'product_codes': sorted(by_product),
        'products_by_exchange': {e: sorted(p.split('.', 1)[1] for p in by_product if p.startswith(e + '.')) for e in sorted(EXCHANGES)},
        'by_exchange': dict(by_exchange), 'by_product': dict(by_product),
        'missing_in_target_contracts': sum(r['missing_target_raw_observations'] > 0 for r in inventory),
        'missing_dataset_in_target_contracts': sum(not r['dataset_exists'] and r['expected_target_raw_observations'] > 0 for r in inventory),
        'data_quality_contract': {'volume_zero': 'retain vendor raw; never count as a genuine traded candle or AM120 history',
            'invalid_traded_ohlc': 'quarantine; no field repair or forward fill',
            'metadata_listing': 'vendor metadata can disagree with earlier official bars; record, do not silently delete or infer exact exchange listing',
            'unit_conversion': 'none; source volume and close OI retained; must bind an explicit research semantics contract before training',
            'pit': 'current ex-post archive, not proof of contemporaneous as-of publication bytes'},
        'input_sha256': {p: sha(BASE / p) for p in ['futures.h5', 'instruments.pk', 'trading_dates.npy']},
        'safety': {'main_database_writes': 0, 'financial_backtests': 0, 'model_fits': 0, 'order_api_calls': 0}}
    (BASE / 'full_market_inventory_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k not in ['by_product', 'product_codes', 'products_by_exchange']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
