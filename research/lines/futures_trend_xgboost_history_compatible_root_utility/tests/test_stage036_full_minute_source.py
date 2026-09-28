import importlib.util
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/stage036_full_minute_source.py'


def module():
    assert TOOL.exists(), 'full minute source audit missing'
    spec = importlib.util.spec_from_file_location('test_source036', TOOL)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def minutes(start='2021-01-08 21:00:00', day='2021-01-11', volume=10):
    return pd.DataFrame({
        'vt_symbol': 'jm2105.DCE', 'bar_datetime': pd.date_range(start, periods=5, freq='min'),
        'bar_date': day, 'open': 100., 'high': 101., 'low': 99., 'close': 100., 'volume': volume,
    })


def expected(frame):
    return frame[['vt_symbol', 'bar_datetime', 'bar_date']].copy()


def parity():
    return {'2021-01-08': True, '2021-01-11': True}


def test_exact_clock_and_trading_date_verified_without_mutating_source():
    m = module(); frame = minutes(); original = frame.copy(deep=True)
    actual = m.normalize(frame, expected(frame), 'jm2105.DCE')
    pd.testing.assert_frame_equal(actual, original)
    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize('fault', ['symbol', 'trading_day', 'duplicate', 'missing', 'nan', 'ohlc', 'volume'])
def test_bad_minute_source_hard_fails(fault):
    m = module(); frame = minutes(); clock = expected(frame)
    if fault == 'symbol': frame.loc[0, 'vt_symbol'] = 'jm2101.DCE'
    elif fault == 'trading_day': frame.loc[0, 'bar_date'] = '2021-01-08'
    elif fault == 'duplicate': frame = pd.concat([frame, frame.iloc[:1]])
    elif fault == 'missing': frame = frame.iloc[1:]
    elif fault == 'nan': frame.loc[0, 'open'] = float('nan')
    elif fault == 'ohlc': frame.loc[0, 'low'] = 102.
    else: frame.loc[0, 'volume'] = -1.
    with pytest.raises(ValueError): m.normalize(frame, clock, 'jm2105.DCE')


def test_positive_volume_daily_aggregate_excludes_zero_volume_carry_price():
    m = module(); frame = minutes()
    frame.loc[0, ['open', 'high', 'low', 'close', 'volume']] = [200, 200, 200, 200, 0]
    values, status = m.aggregate_day(frame)
    assert status == 'positive_volume'
    assert values == {'open': 100., 'high': 101., 'low': 99., 'close': 100., 'volume': 40.}


def test_zero_trade_day_requires_flat_unchanged_price():
    m = module(); frame = minutes(volume=0)
    assert m.aggregate_day(frame)[1] == 'untraded_nonflat'
    frame[['open', 'high', 'low', 'close']] = 100.
    assert m.aggregate_day(frame)[1] == 'untraded_flat'


def test_missing_and_divergent_daily_values_not_treated_as_compatible():
    m = module(); values = {'open': 100., 'high': 101., 'low': 99., 'close': 100., 'volume': 40.}
    assert m.same_values(values, values)
    assert not m.same_values(values, None)
    assert not m.same_values(values, {**values, 'close': 100.01})
    assert not m.same_values(values, {**values, 'volume': 40.00000001})


def test_friday_night_clock_compatible_with_monday_day_label():
    m = module(); frame = minutes()
    result = m.qualify(frame, expected(frame), '2021-01-08', '2021-01-11', True, 2, parity(), set())
    assert result['status'] == 'source_proxy_qualified_not_execution'
    assert result['first_time'] == '2021-01-08T21:00:00'


def test_zero_volume_night_cannot_switch_to_day():
    m = module(); frame = pd.concat([minutes(volume=0), minutes('2021-01-11 09:00:00')])
    result = m.qualify(frame, expected(frame), '2021-01-08', '2021-01-11', True, 2, parity(), set())
    assert result['status'] == 'first_bar_volume_insufficient' and result['window'] == 'night'


def test_holiday_without_expected_night_can_use_day():
    m = module(); frame = minutes('2021-01-11 09:00:00')
    assert m.qualify(frame, expected(frame), '2021-01-08', '2021-01-11', True, 2, parity(), set())['status'] == 'source_proxy_qualified_not_execution'


def test_product_proxy_cannot_skip_an_earlier_expected_night():
    m = module(); frame = pd.concat([minutes(), minutes('2021-01-11 09:00:00')])
    result = m.qualify(frame, expected(frame), '2021-01-08', '2021-01-11', False, 2, parity(), set())
    assert result['status'] == 'expected_open_mismatch'


@pytest.mark.parametrize('which', ['2021-01-08', '2021-01-11'])
def test_required_daily_parity_and_guard_are_not_inherited_from_other_strategy(which):
    m = module(); frame = minutes(); check = parity(); check[which] = False
    assert m.qualify(frame, expected(frame), '2021-01-08', '2021-01-11', True, 2, check, set())['status'] == 'required_daily_parity_failed'
    assert m.qualify(frame, expected(frame), '2021-01-08', '2021-01-11', True, 2, parity(), {which})['status'] == 'source_guard_day'


def test_missing_first_minute_is_not_later_open():
    m = module(); frame = minutes(); clock = expected(frame)
    result = m.qualify(frame.iloc[1:], clock, '2021-01-08', '2021-01-11', True, 2, parity(), set())
    assert result['status'] == 'window_clock_incomplete'


def test_source_paths_cannot_escape_input_tree(tmp_path):
    m = module()
    with pytest.raises(ValueError): m.safe_path(tmp_path, '../outside.csv')


def test_source_manifest_duplicate_contract_not_silently_overwritten():
    m = module(); value = {'vt_symbol': 'jm2105.DCE'}
    with pytest.raises(ValueError): m.unique_entries({'files': [value, value]})


def test_readonly_database_loader_uses_exact_contract_and_daily_interval(tmp_path):
    import sqlite3
    m = module(); path = tmp_path / 'daily.db'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE dbbardata (symbol TEXT, exchange TEXT, datetime TEXT, interval TEXT, open_price REAL, high_price REAL, low_price REAL, close_price REAL, volume REAL)')
        connection.executemany('INSERT INTO dbbardata VALUES (?,?,?,?,?,?,?,?,?)', [
            ('jm2105', 'DCE', '2021-01-11 00:00:00', 'd', 100, 101, 99, 100, 50),
            ('jm2105', 'DCE', '2021-01-11 09:00:00', '1m', 500, 501, 499, 500, 1),
            ('jm2101', 'DCE', '2021-01-11 00:00:00', 'd', 1000, 1001, 999, 1000, 50),
        ])
    before = path.read_bytes()
    with m.readonly_database(path) as connection:
        data = m.daily_reference(connection, 'jm2105.DCE')
        with pytest.raises(sqlite3.OperationalError): connection.execute('DELETE FROM dbbardata')
    assert data['2021-01-11']['open'] == 100 and len(data) == 1
    assert before == path.read_bytes()
