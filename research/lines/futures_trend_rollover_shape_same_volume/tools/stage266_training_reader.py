"""Read-only Stage266 research adapter. This module is not a production loader.

All dates and delivery months must be explicit. Missing opening open interest is
never filled, and a row compatibility flag does not certify a 120/60 sample.
"""
from __future__ import annotations

import argparse
import calendar
from collections.abc import Iterable, Mapping
from contextlib import closing
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3

import numpy as np
import pandas as pd


EXCHANGES = frozenset({'CZCE', 'DCE', 'SHFE', 'INE', 'CFFEX', 'GFEX'})
NUMERIC_FIELDS = ('open', 'high', 'low', 'close', 'volume', 'open_oi', 'close_oi')
REQUIRED_COLUMNS = frozenset({
    'contract_epoch_id', 'trade_date', *NUMERIC_FIELDS, 'open_interest',
    'open_oi_status', 'exchange', 'product', 'contract_yyyymm', 'source_symbol',
    'source_id', 'quality_status', 'train_eligible',
})
ROW_FLAG_COLUMNS = ('legacy108_row_usable', 'legacy108_usable')
# Snapshot of qmt_universe.PRODUCT_SPECS, never an automatic all-market expansion.
LEGACY18 = frozenset({('GFEX', 'LC'), ('SHFE', 'AU'), ('SHFE', 'CU'),
    ('CZCE', 'MA'), ('CZCE', 'OI'), ('CZCE', 'AP'), ('CZCE', 'SM'), ('CZCE', 'SA'),
    ('SHFE', 'RB'), ('DCE', 'JM'), ('SHFE', 'HC'), ('CZCE', 'CF'), ('CZCE', 'FG'),
    ('CZCE', 'SH'), ('GFEX', 'SI'), ('SHFE', 'RU'), ('DCE', 'LH'), ('SHFE', 'SP')})


class TrainingDataError(ValueError):
    """The explicit research data contract could not be verified."""


def _day(value, name='date') -> pd.Timestamp:
    if isinstance(value, str) and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise TrainingDataError(f'{name} must use YYYY-MM-DD')
    if not isinstance(value, (str, date, datetime, pd.Timestamp, np.datetime64)):
        raise TrainingDataError(f'{name} must be an explicit calendar date')
    try:
        result = pd.Timestamp(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TrainingDataError(f'invalid {name}: {value!r}') from exc
    if pd.isna(result) or result.tzinfo is not None or result != result.normalize():
        raise TrainingDataError(f'{name} must be a timezone-free date at midnight')
    return result


def _identity(contract_epoch_id=None, exchange=None, product=None, contract_yyyymm=None):
    if contract_epoch_id is not None:
        match = re.fullmatch(r'([A-Za-z]+)\.([A-Za-z]+(?:_F)?)\.(\d{6})', str(contract_epoch_id))
        if not match:
            raise TrainingDataError('identity must be EXCHANGE.PRODUCT.YYYYMM')
        ex, prod, month = match.groups()
        ex, prod = ex.upper(), prod.upper()
        for supplied, found, name in [(exchange, ex, 'exchange'), (product, prod, 'product'),
                                       (contract_yyyymm, month, 'contract_yyyymm')]:
            if supplied is not None and str(supplied).upper() != found:
                raise TrainingDataError(f'conflicting {name} selector')
    else:
        if exchange is None or product is None or contract_yyyymm is None:
            raise TrainingDataError('explicit exchange, product and YYYYMM are required')
        ex, prod, month = str(exchange).upper(), str(product).upper(), str(contract_yyyymm)
    if ex not in EXCHANGES or not re.fullmatch(r'[A-Z]+(?:_F)?', prod):
        raise TrainingDataError('invalid exchange or product')
    if not re.fullmatch(r'\d{6}', month) or not 1 <= int(month[-2:]) <= 12 or int(month[:4]) < 1900:
        raise TrainingDataError('invalid delivery YYYYMM')
    if prod.endswith('_F') and (ex != 'DCE' or prod not in {'L_F', 'PP_F', 'V_F'}):
        raise TrainingDataError('unsupported monthly-average contract family')
    return f'{ex}.{prod}.{month}', ex, prod, month


def _table_name(table):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', table):
        raise TrainingDataError('unsafe SQLite table name')
    return '"' + table + '"'


def _row_issues(frame: pd.DataFrame) -> pd.Series:
    """Recheck source flags and values; no reliance on DataFrame attrs."""
    missing = REQUIRED_COLUMNS - set(frame.columns)
    flags = [c for c in ROW_FLAG_COLUMNS if c in frame]
    if missing or not flags:
        raise TrainingDataError(f'missing required columns: {sorted(missing)}; row flag required')
    issues = [[] for _ in range(len(frame))]

    def add(mask, message):
        for i in np.flatnonzero(np.asarray(mask, dtype=bool)):
            issues[i].append(message)

    for field in NUMERIC_FIELDS:
        add(~np.isfinite(frame[field].to_numpy(dtype=float)), f'{field}_missing_or_nonfinite')
    ohlc = frame[['open', 'high', 'low', 'close']]
    geometry = ((ohlc > 0).all(axis=1) &
                (frame.low <= frame[['open', 'close']].min(axis=1)) &
                (frame.high >= frame[['open', 'close']].max(axis=1)) &
                (frame.high >= frame.low))
    add(~geometry, 'invalid_ohlc')
    add(~(frame.volume > 0), 'nonpositive_volume')
    add(frame.open_oi < 0, 'negative_open_oi')
    add(frame.close_oi < 0, 'negative_close_oi')
    add(frame.open_oi_status != 'source_observed', 'open_oi_not_source_observed')
    add(frame.quality_status != 'accepted', 'quality_not_accepted')
    add(~frame.train_eligible.eq(1), 'stored_train_eligible_false')
    for flag in flags:
        add(~frame[flag].eq(1), f'stored_{flag}_false')
    return pd.Series([';'.join(x) for x in issues], index=frame.index, dtype='object')


def load_contract_bars(
    db_path, *, candidate_date, contract_epoch_id=None, exchange=None, product=None,
    contract_yyyymm=None, start_date=None, open_oi_policy='mark_unusable', table='daily_bars',
) -> pd.DataFrame:
    """Load one exact delivery month, bounded before any row checks.

    ``strict`` checks every row in this explicit bounded query. To use a complete
    recent window despite older missing opening OI, load in ``mark_unusable`` mode
    and call ``require_legacy108_window`` with an explicit trading calendar.
    """
    epoch, ex, prod, month = _identity(contract_epoch_id, exchange, product, contract_yyyymm)
    candidate = _day(candidate_date, 'candidate_date')
    first = _day(start_date, 'start_date') if start_date is not None else None
    if first is not None and first > candidate:
        raise TrainingDataError('start_date is after candidate_date')
    if open_oi_policy not in {'strict', 'mark_unusable'}:
        raise TrainingDataError('open_oi_policy must be strict or mark_unusable')
    quoted = _table_name(table)
    path = Path(db_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    # mode=ro forbids creation/writes and observes WAL state; immutable=1 would not.
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        columns = {row[1] for row in db.execute(f'PRAGMA table_info({quoted})')}
        if not REQUIRED_COLUMNS <= columns or not columns.intersection(ROW_FLAG_COLUMNS):
            raise TrainingDataError(f'incompatible {table} schema; missing {sorted(REQUIRED_COLUMNS-columns)}')
        conditions = ['contract_epoch_id = ?', 'trade_date <= ?']
        params = [epoch, candidate.date().isoformat()]
        if first is not None:
            conditions.append('trade_date >= ?')
            params.append(first.date().isoformat())
        frame = pd.read_sql_query(f'SELECT * FROM {quoted} WHERE ' + ' AND '.join(conditions) +
                                  ' ORDER BY trade_date', db, params=params)
    if not frame.empty:
        try:
            frame['date'] = pd.to_datetime(frame.trade_date, format='%Y-%m-%d', errors='raise')
        except (TypeError, ValueError) as exc:
            raise TrainingDataError('invalid trade_date in clean store') from exc
        if not frame.trade_date.eq(frame.date.dt.strftime('%Y-%m-%d')).all():
            raise TrainingDataError('trade_date is not canonical YYYY-MM-DD')
        if frame.date.duplicated().any():
            raise TrainingDataError('duplicate contract-date rows; no keep-last policy')
        if not (frame.exchange.eq(ex) & frame['product'].eq(prod) &
                frame.contract_yyyymm.astype(str).eq(month)).all():
            raise TrainingDataError('stored identity disagrees with the selected contract epoch')
    else:
        frame['date'] = pd.Series([], dtype='datetime64[ns]')
    for field in (*NUMERIC_FIELDS, 'open_interest'):
        try:
            frame[field] = pd.to_numeric(frame[field], errors='raise').astype(float)
        except (TypeError, ValueError) as exc:
            raise TrainingDataError(f'nonnumeric {field}') from exc
    alias_equal = frame.open_interest.eq(frame.close_oi) | (frame.open_interest.isna() & frame.close_oi.isna())
    if not alias_equal.all():
        raise TrainingDataError('open_interest alias must equal close_oi')
    if all(c in frame for c in ROW_FLAG_COLUMNS) and not frame[ROW_FLAG_COLUMNS[0]].eq(frame[ROW_FLAG_COLUMNS[1]]).all():
        raise TrainingDataError('stored legacy108 row flags disagree')
    frame['reader_row_issues'] = _row_issues(frame)
    compatible = frame.reader_row_issues.eq('')
    frame['legacy108_usable'] = compatible
    frame['legacy108_row_usable'] = compatible
    frame.attrs.update(contract_epoch_id=epoch, candidate_date=candidate.date().isoformat(),
                       start_date=None if first is None else first.date().isoformat(),
                       open_oi_policy=open_oi_policy, legacy108_window_qualified=False,
                       qualification_scope='row_fields_only_no_label_maturity_or_PIT_certification',
                       data_access='sqlite_read_only')
    if open_oi_policy == 'strict' and not compatible.all():
        bad = frame.loc[~compatible, ['trade_date', 'reader_row_issues']].head(5).to_dict('records')
        raise TrainingDataError(f'bounded query is not legacy108 field complete: {bad}')
    return frame.reset_index(drop=True)


def _calendar(expected_trade_dates: Iterable) -> pd.DatetimeIndex:
    values = pd.DatetimeIndex([_day(x, 'expected_trade_date') for x in expected_trade_dates])
    if values.has_duplicates or not values.is_monotonic_increasing:
        raise TrainingDataError('expected trading dates must be unique and increasing')
    return values


def qualify_legacy108_window(frame, *, candidate_date, expected_trade_dates, window_rows=120):
    """Check the last N expected dates, never the last N available observations.

    This is only the feature-field window gate. Label maturity (usually 60 later
    source trading dates), PIT tradability and the model split remain separate.
    """
    if isinstance(window_rows, bool) or not isinstance(window_rows, int) or window_rows < 1:
        raise TrainingDataError('window_rows must be a positive integer')
    candidate = _day(candidate_date, 'candidate_date')
    cal = _calendar(expected_trade_dates)
    cal = cal[cal <= candidate]
    expected = cal[-window_rows:]
    if 'date' not in frame or 'contract_epoch_id' not in frame:
        raise TrainingDataError('window requires a research reader DataFrame')
    dates = pd.DatetimeIndex([_day(x, 'frame date') for x in frame.date])
    future = int((dates > candidate).sum())
    bounded = frame.loc[dates <= candidate].copy()
    if bounded.contract_epoch_id.nunique() > 1 or bounded.date.duplicated().any():
        raise TrainingDataError('a window must contain one epoch and unique dates')
    issues = _row_issues(bounded)
    usable_dates = pd.DatetimeIndex(bounded.loc[issues.eq(''), 'date'])
    observed_dates = pd.DatetimeIndex(bounded.date)
    missing = expected.difference(observed_dates)
    bad = expected.intersection(observed_dates).difference(usable_dates)
    unexpected = (observed_dates[(observed_dates >= expected[0]) & (observed_dates <= expected[-1])]
                  .difference(expected)) if len(expected) else pd.DatetimeIndex([])
    reasons = []
    if candidate not in cal:
        reasons.append('candidate_not_in_expected_trading_calendar')
    if len(expected) < window_rows:
        reasons.append('insufficient_expected_history')
    if len(missing):
        reasons.append('missing_expected_observations')
    if len(bad):
        reasons.append('incomplete_legacy108_fields')
    if len(unexpected):
        reasons.append('observations_outside_expected_calendar')
    return dict(eligible=not reasons, reasons=reasons, window_rows=window_rows,
                expected_rows=len(expected), observed_rows=int(expected.isin(observed_dates).sum()),
                usable_rows=int(expected.isin(usable_dates).sum()),
                candidate_date=candidate.date().isoformat(),
                window_start=expected[0].date().isoformat() if len(expected) else None,
                window_end=expected[-1].date().isoformat() if len(expected) else None,
                missing_dates=missing.strftime('%Y-%m-%d').tolist(),
                unusable_dates=bad.strftime('%Y-%m-%d').tolist(),
                unexpected_observation_dates=unexpected.strftime('%Y-%m-%d').tolist(),
                future_rows_excluded=future,
                label_maturity_checked=False, point_in_time_tradability_checked=False)


def require_legacy108_window(frame, *, candidate_date, expected_trade_dates, window_rows=120):
    report = qualify_legacy108_window(frame, candidate_date=candidate_date,
                                      expected_trade_dates=expected_trade_dates, window_rows=window_rows)
    if not report['eligible']:
        raise TrainingDataError(f'legacy108 feature window not qualified: {report}')
    result = frame.loc[(frame.date >= report['window_start']) &
                       (frame.date <= report['window_end'])].copy().reset_index(drop=True)
    result.attrs.update(frame.attrs)
    result.attrs.update(candidate_date=report['candidate_date'], legacy108_window_qualified=True,
                        feature_window_qualification=report)
    return result


def _mapping_symbol(symbol, convention, anchor):
    pattern = (r'([A-Za-z]+)\.([A-Za-z]+)(\d{3,4})(F?)' if convention == 'tq' else
               r'([A-Za-z]+)(\d{3,4})(F?)\.([A-Za-z]+)')
    match = re.fullmatch(pattern, symbol)
    if not match:
        raise TrainingDataError(f'not a real mapped contract: {symbol}')
    if convention == 'tq':
        ex, prod, digits, suffix = match.groups()
    else:
        prod, digits, suffix, ex = match.groups()
    ex, prod = ex.upper(), prod.upper()
    if len(digits) == 3 and ex != 'CZCE':
        raise TrainingDataError('three-digit delivery code outside CZCE')
    month = int(digits[-2:])
    if not 1 <= month <= 12:
        raise TrainingDataError('invalid mapped delivery month')
    modulus = 10 if len(digits) == 3 else 100
    residue = int(digits[:-2])
    candidates = []
    for year in range(anchor.year-1, anchor.year+4):
        if year % modulus == residue:
            distance = (date(year, month, calendar.monthrange(year, month)[1]) - anchor.date()).days
            if -20 <= distance <= 3*366:
                candidates.append((distance < 0, abs(distance), year))
    if not candidates:
        raise TrainingDataError('mapped contract cannot be resolved near its own trade date')
    year = min(candidates)[2]
    if suffix:
        prod += '_F'
    return _identity(exchange=ex, product=prod, contract_yyyymm=f'{year:04d}{month:02d}')


def mapping_identity(row: Mapping) -> dict:
    """Resolve existing TQ/VT mapping on its own row date; never rename old codes."""
    anchor = _day(row['date'], 'mapping date')
    identities = []
    for column, convention in [('main_contract_vt', 'vt'), ('main_contract_tq', 'tq')]:
        symbol = row.get(column)
        if symbol is not None and not pd.isna(symbol) and str(symbol).strip():
            identities.append(_mapping_symbol(str(symbol).strip(), convention, anchor))
    if not identities:
        raise TrainingDataError('mapping row has no main contract')
    if len(set(x[0] for x in identities)) != 1:
        raise TrainingDataError('TQ and VT mapped delivery months disagree')
    epoch, ex, prod, month = identities[0]
    if str(row.get('exchange', '')).upper() != ex or str(row.get('product', '')).upper() != prod:
        raise TrainingDataError('mapping product/exchange differs from its contract; no legacy aliasing')
    return dict(contract_epoch_id=epoch, exchange=ex, product=prod, contract_yyyymm=month,
                mapping_date=anchor.date().isoformat(),
                identity_status='resolved_from_mapping_row_date_not_official_listing_proof')


def audit_mapping_availability(
    db_path, mapping: pd.DataFrame, *, candidate_date, expected_trade_dates,
    window_rows=120, start_date=None, products=None,
):
    """Census existing mappings against exact epochs; does not generate labels.

    Missing product-date mappings remain explicit grid rows. Feature availability
    checks the mapped contract's history, not a synthetic continuous price series.
    This function does not broaden the existing 18-product pool by default.
    """
    if isinstance(window_rows, bool) or not isinstance(window_rows, int) or window_rows < 1:
        raise TrainingDataError('window_rows must be a positive integer')
    candidate = _day(candidate_date, 'candidate_date')
    first = _day(start_date, 'start_date') if start_date is not None else None
    if first is not None and first > candidate:
        raise TrainingDataError('start_date is after candidate_date')
    cal = _calendar(expected_trade_dates)
    cal = cal[cal <= candidate]
    if candidate not in cal:
        raise TrainingDataError('audit candidate must occur in the explicit trading calendar')
    required = {'date', 'product', 'exchange', 'main_contract_vt', 'main_contract_tq'}
    if not required <= set(mapping):
        raise TrainingDataError(f'mapping missing columns: {sorted(required-set(mapping))}')
    pool = LEGACY18 if products is None else frozenset((str(ex).upper(), str(prod).upper()) for ex, prod in products)
    for ex, prod in pool:
        _identity(exchange=ex, product=prod, contract_yyyymm='202501')
    scope = cal if first is None else cal[cal >= first]
    selected = mapping.copy()
    selected['date'] = selected.date.map(lambda x: _day(x, 'mapping date'))
    selected['exchange'] = selected.exchange.str.upper()
    selected['product'] = selected['product'].str.upper()
    selected = selected.loc[(selected.date <= candidate) &
                            pd.MultiIndex.from_frame(selected[['exchange', 'product']]).isin(pool)]
    if selected.duplicated(['date', 'exchange', 'product']).any():
        raise TrainingDataError('duplicate mapping product-date rows; no keep-last policy')
    outside_calendar = int((~selected.date.isin(cal)).sum())
    records = {(r['date'], r['exchange'], r['product']): r for r in selected.to_dict('records')}
    rows = []
    for day in scope:
        for ex, prod in sorted(pool):
            mapped = records.get((day, ex, prod))
            result = dict(date=day.date().isoformat(), exchange=ex, product=prod,
                          contract_epoch_id='', mapping_status='missing_mapping', mapped_identity=False,
                          observed_clean_row=False, legacy108_row_usable=False,
                          legacy108_feature_window_ok=False)
            if mapped is not None:
                try:
                    identity = mapping_identity(mapped)
                    result.update(contract_epoch_id=identity['contract_epoch_id'],
                                  mapping_status='resolved', mapped_identity=True)
                except TrainingDataError as exc:
                    empty = all(pd.isna(mapped.get(c)) or not str(mapped.get(c, '')).strip()
                                for c in ['main_contract_vt', 'main_contract_tq'])
                    if not empty:
                        result['mapping_status'] = f'unresolved:{exc}'
            rows.append(result)
    details = pd.DataFrame(rows, columns=['date', 'exchange', 'product', 'contract_epoch_id',
        'mapping_status', 'mapped_identity', 'observed_clean_row', 'legacy108_row_usable',
        'legacy108_feature_window_ok'])
    for epoch, group in details.loc[details.mapped_identity].groupby('contract_epoch_id', sort=True):
        bars = load_contract_bars(db_path, contract_epoch_id=epoch, candidate_date=candidate)
        flags = bars.set_index('date').legacy108_usable.reindex(cal, fill_value=False)
        observed = pd.Series(True, index=bars.date).reindex(cal, fill_value=False)
        # Root clean data forbids noncalendar dates. Fail closed for any altered store.
        unexpected = pd.DatetimeIndex(bars.date).difference(cal)
        complete = flags.astype(int).rolling(window_rows, min_periods=window_rows).sum().eq(window_rows)
        if len(unexpected):
            positions = cal.searchsorted(unexpected)
            for position in positions:
                complete.iloc[position:min(len(cal), position+window_rows)] = False
        days = pd.DatetimeIndex(group.date)
        details.loc[group.index, 'observed_clean_row'] = observed.reindex(days).to_numpy()
        details.loc[group.index, 'legacy108_row_usable'] = flags.reindex(days).to_numpy()
        details.loc[group.index, 'legacy108_feature_window_ok'] = complete.reindex(days).to_numpy()
    def counts(group):
        def span(column):
            days = group.loc[group[column], 'date']
            return dict(first=days.min() if len(days) else None, last=days.max() if len(days) else None)
        return dict(calendar_product_rows=len(group), mapped_identity_rows=int(group.mapped_identity.sum()),
                    missing_mapping_rows=int(group.mapping_status.eq('missing_mapping').sum()),
                    unresolved_mapping_rows=int(group.mapping_status.str.startswith('unresolved:').sum()),
                    observed_clean_rows=int(group.observed_clean_row.sum()),
                    legacy108_field_complete_rows=int(group.legacy108_row_usable.sum()),
                    legacy108_feature_window_rows=int(group.legacy108_feature_window_ok.sum()),
                    mapped_dates=span('mapped_identity'), clean_observed_dates=span('observed_clean_row'),
                    legacy108_field_complete_dates=span('legacy108_row_usable'),
                    legacy108_feature_window_dates=span('legacy108_feature_window_ok'))
    report = dict(schema_version=1, **counts(details), candidate_date=candidate.date().isoformat(),
                  start_date=scope[0].date().isoformat() if len(scope) else None,
                  window_rows=window_rows, calendar_days=len(scope), product_count=len(pool),
                  distinct_resolved_epochs=int(details.loc[details.mapped_identity, 'contract_epoch_id'].nunique()),
                  mapping_rows_outside_expected_calendar=outside_calendar,
                  label_maturity_or_training_samples_certified=False,
                  label_horizon_policy='60 later source trading dates; not computed by this field audit',
                  identity_policy='mapping own trade date plus exact YYYYMM; no product aliases',
                  product_scope='existing_18_pool' if products is None else 'explicit_product_subset',
                  latest_scope_date=dict(date=scope[-1].date().isoformat() if len(scope) else None,
                                         **counts(details.loc[details.date.eq(scope[-1].date().isoformat())]) if len(scope) else {}),
                  per_year={year: counts(group) for year, group in details.groupby(details.date.str[:4], sort=True)},
                  per_product={f'{ex}.{prod}': counts(group) for (ex, prod), group in details.groupby(['exchange', 'product'], sort=True)})
    return report, details


def _load_calendar_file(path):
    path = Path(path)
    if path.suffix == '.npy':
        values = np.load(path, allow_pickle=False)
        if values.ndim != 1:
            raise TrainingDataError('calendar array must have one dimension')
        if np.issubdtype(values.dtype, np.integer):
            # RQ dates use YYYYMMDD integers, not UNIX timestamps.
            return [datetime.strptime(str(int(x)), '%Y%m%d').date() for x in values]
        if np.issubdtype(values.dtype, np.datetime64):
            return values.tolist() if values.dtype == 'datetime64[D]' else list(values)
        raise TrainingDataError('calendar .npy must use explicit YYYYMMDD integers or datetime64')
    frame = pd.read_csv(path)
    if 'date' not in frame:
        raise TrainingDataError('calendar CSV requires a date column')
    return frame.date.tolist()


def apply_deletions_to_availability(
    details, deleted_keys, *, candidate_date, expected_trade_dates, window_rows=120,
):
    """Invalidate a frozen census using exact deleted keys; no database access.

    This only removes eligibility. It cannot promote any row or repair a gap.
    The rolling gate follows source-calendar positions, not observed-row counts.
    """
    if isinstance(window_rows, bool) or not isinstance(window_rows, int) or window_rows < 1:
        raise TrainingDataError('window_rows must be a positive integer')
    candidate = _day(candidate_date, 'candidate_date')
    cal = _calendar(expected_trade_dates)
    cal = cal[cal <= candidate]
    flags = ['observed_clean_row', 'legacy108_row_usable', 'legacy108_feature_window_ok']
    required = {'date', 'contract_epoch_id', *flags}
    if not required <= set(details) or not {'contract_epoch_id', 'trade_date'} <= set(deleted_keys):
        raise TrainingDataError('availability or deletion keys lack required columns')
    dates = details.date.map(lambda x: _day(x, 'availability date'))
    future_rows = int((dates > candidate).sum())
    result = details.loc[dates <= candidate].copy()
    if result.duplicated(['date', 'contract_epoch_id']).any():
        # Missing mappings use an empty epoch and may share the same date.
        mapped = result.loc[result.contract_epoch_id.fillna('').ne('')]
        if mapped.duplicated(['date', 'contract_epoch_id']).any():
            raise TrainingDataError('duplicate mapped availability keys')
    for flag in flags:
        if not result[flag].isin([True, False]).all():
            raise TrainingDataError(f'availability {flag} must be boolean')
        result[flag] = result[flag].astype(bool)
    day_index = pd.DatetimeIndex(result.date.map(lambda x: _day(x, 'availability date')))
    if not day_index.isin(cal).all():
        raise TrainingDataError('availability date is outside the explicit source calendar')
    delta = deleted_keys[['contract_epoch_id', 'trade_date']].copy()
    delta['contract_epoch_id'] = delta.contract_epoch_id.map(lambda x: _identity(x)[0])
    delta['trade_date'] = delta.trade_date.map(lambda x: _day(x, 'deleted trade_date').date().isoformat())
    if delta.duplicated().any():
        raise TrainingDataError('duplicate deletion keys')
    exact = set(map(tuple, delta.to_numpy()))
    day_hit = pd.Series([(str(epoch), day.date().isoformat()) in exact
                        for epoch, day in zip(result.contract_epoch_id, day_index)], index=result.index)
    window_hit = pd.Series(False, index=result.index)
    for epoch, group in delta.groupby('contract_epoch_id', sort=True):
        positions = result.index[result.contract_epoch_id.eq(epoch)]
        if not len(positions):
            continue
        deleted_days = pd.DatetimeIndex(group.trade_date)
        affected = pd.Series(cal.isin(deleted_days), index=cal).astype(int).rolling(window_rows, min_periods=1).sum().gt(0)
        candidate_days = pd.DatetimeIndex(result.loc[positions, 'date'])
        window_hit.loc[positions] = affected.reindex(candidate_days).to_numpy()
    result['delta_invalidated_clean_row'] = day_hit & result.observed_clean_row
    result['delta_invalidated_feature_window'] = window_hit & result.legacy108_feature_window_ok
    result['delta_window_contains_deleted_observation'] = window_hit
    report = dict(deleted_unique_keys=len(delta), clean_rows_invalidated=int(result.delta_invalidated_clean_row.sum()),
                  field_complete_rows_invalidated=int((day_hit & result.legacy108_row_usable).sum()),
                  strict_windows_invalidated=int(result.delta_invalidated_feature_window.sum()),
                  future_rows_excluded=future_rows, candidate_date=candidate.date().isoformat(),
                  window_rows=window_rows, database_access=False, promotions_performed=0)
    result.loc[day_hit, ['observed_clean_row', 'legacy108_row_usable']] = False
    result.loc[window_hit, 'legacy108_feature_window_ok'] = False
    return result, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    audit = sub.add_parser('audit-mapping', help='Census existing 18-pool mappings; no model or label generation')
    audit.add_argument('--db', required=True)
    audit.add_argument('--mapping', required=True)
    audit.add_argument('--calendar', required=True)
    audit.add_argument('--candidate-date', required=True)
    audit.add_argument('--start-date')
    audit.add_argument('--window-rows', type=int, default=120)
    audit.add_argument('--output', help='Explicit new JSON path; details go to matching .csv.gz')
    args = parser.parse_args(argv)
    output = Path(args.output).expanduser().resolve() if args.output else None
    if output is not None and (output.exists() or output.with_suffix('.csv.gz').exists()):
        raise FileExistsError('audit outputs exist; choose a new path')
    inputs = dict(database=Path(args.db).resolve(), mapping=Path(args.mapping).resolve(),
                  calendar=Path(args.calendar).resolve())
    def fingerprints():
        values = {}
        for key, path in inputs.items():
            with path.open('rb') as stream:
                values[key] = hashlib.file_digest(stream, 'sha256').hexdigest()
        return values
    before = fingerprints()
    report, details = audit_mapping_availability(args.db, pd.read_csv(args.mapping),
        candidate_date=args.candidate_date, expected_trade_dates=_load_calendar_file(args.calendar),
        window_rows=args.window_rows, start_date=args.start_date)
    after = fingerprints()
    if before != after:
        raise TrainingDataError('audit inputs changed during read; no stable snapshot report emitted')
    report['inputs'] = {key: str(path) for key, path in inputs.items()}
    report['input_sha256'] = before
    report['input_bytes_unchanged_after_audit'] = True
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        details.to_csv(output.with_suffix('.csv.gz'), index=False, compression='gzip')
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
