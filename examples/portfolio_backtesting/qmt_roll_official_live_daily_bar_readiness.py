"""Require a valid target-day bar for every unchanged Static18+fu product."""
from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path
import re
import sqlite3
from typing import Any

# The existing official Static18 universe plus its fixed fu satellite.  This is
# coverage validation; eligibility and strategy ranking remain separate gates.
OFFICIAL_LIVE_DAILY_PRODUCTS = (
    'AP.CZCE', 'CF.CZCE', 'FG.CZCE', 'MA.CZCE', 'OI.CZCE', 'SA.CZCE',
    'SH.CZCE', 'SM.CZCE', 'jm.DCE', 'lh.DCE', 'lc.GFEX', 'si.GFEX',
    'au.SHFE', 'cu.SHFE', 'fu.SHFE', 'hc.SHFE', 'rb.SHFE', 'ru.SHFE', 'sp.SHFE',
)


class DailyBarReadinessError(ValueError):
    pass


def validate_target_daily_bars(
    *, database_path: Path | str, mapping_path: Path | str, target_date: str,
) -> dict[str, Any]:
    try:
        if date.fromisoformat(target_date).isoformat() != target_date:
            raise ValueError('noncanonical')
    except (ValueError, TypeError) as exc:
        raise DailyBarReadinessError('target_daily_date_invalid') from exc
    required = set(OFFICIAL_LIVE_DAILY_PRODUCTS)
    contracts: dict[str, str] = {}
    try:
        with Path(mapping_path).open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            if not {'date', 'continuous_symbol_vt', 'main_contract_vt'}.issubset(reader.fieldnames or []):
                raise DailyBarReadinessError('target_mapping_columns_invalid')
            for row in reader:
                product = row.get('continuous_symbol_vt', '')
                if row.get('date', '')[:10] != target_date or product not in required:
                    continue
                if product in contracts:
                    raise DailyBarReadinessError('target_duplicate_mapping:' + product)
                contract = row.get('main_contract_vt', '')
                name, exchange = product.split('.')
                if not re.fullmatch(re.escape(name) + r'\d{3,4}\.' + re.escape(exchange), contract):
                    raise DailyBarReadinessError('target_mapping_contract_invalid:' + product)
                contracts[product] = contract
    except (OSError, csv.Error) as exc:
        raise DailyBarReadinessError('target_mapping_unreadable') from exc
    if set(contracts) != required:
        missing = ','.join(sorted(required - set(contracts)))
        raise DailyBarReadinessError('target_mapping_incomplete:' + missing)
    database = Path(database_path).resolve(strict=True)
    try:
        with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as connection:
            connection.execute('BEGIN')
            for product, contract in sorted(contracts.items()):
                symbol, exchange = contract.split('.')
                rows = connection.execute(
                    "SELECT open_price,high_price,low_price,close_price,volume,open_interest "
                    "FROM dbbardata WHERE symbol=? AND exchange=? AND interval='d' "
                    "AND datetime>=? AND datetime<?",
                    (symbol, exchange, target_date, target_date + '~'),
                ).fetchall()
                if len(rows) != 1:
                    raise DailyBarReadinessError('target_daily_bar_missing_or_duplicate:' + product)
                try:
                    o, h, l, c, volume, oi = map(float, rows[0])
                    valid = all(math.isfinite(x) for x in (o,h,l,c,volume,oi)) and min(o,h,l,c) > 0 and min(volume,oi) >= 0 and l <= min(o,c) <= max(o,c) <= h
                except (TypeError, ValueError):
                    valid = False
                if not valid:
                    raise DailyBarReadinessError('target_daily_bar_invalid:' + product)
    except sqlite3.Error as exc:
        raise DailyBarReadinessError('target_daily_database_unreadable') from exc
    return {'target_date': target_date, 'complete_product_count': len(contracts),
            'contracts': contracts, 'coverage_status': 'complete'}
