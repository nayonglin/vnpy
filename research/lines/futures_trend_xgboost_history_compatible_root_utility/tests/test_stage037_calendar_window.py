import importlib.util
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/stage037_calendar_window.py'


def module():
    assert TOOL.exists(), 'calendar window adapter missing'
    spec = importlib.util.spec_from_file_location('test_calendar037', TOOL)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def data(symbol='SH405.CZCE', time='2024-03-26 21:00:00', volume=50):
    return pd.DataFrame({'vt_symbol': symbol, 'bar_datetime': pd.date_range(time, periods=5, freq='min'),
                         'bar_date': '2024-03-27', 'open': 100., 'high': 101., 'low': 99.,
                         'close': 100., 'volume': volume})


def evaluate(m, actual, legal=None):
    legal = actual if legal is None else legal
    return m.qualify_from_clock(actual, legal[['vt_symbol', 'bar_datetime', 'bar_date']],
                                '2024-03-26', '2024-03-27', 38,
                                {'2024-03-26': True, '2024-03-27': True}, set())


@pytest.mark.parametrize('symbol', ['SH405.CZCE', 'jm2405.DCE', 'rb2405.SHFE'])
def test_same_calendar_rule_for_every_product_without_product_id_branch(symbol):
    m = module(); frame = pd.concat([data(symbol), data(symbol, '2024-03-27 09:00:00')])
    result = evaluate(m, frame)
    assert result['status'] == 'source_proxy_qualified_not_execution'
    assert result['first_time'] == '2024-03-26T21:00:00'


def test_day_only_calendar_uses_nine_am():
    m = module(); result = evaluate(m, data(time='2024-03-27 09:00:00'))
    assert result['status'] == 'source_proxy_qualified_not_execution' and result['window'] == 'day'


def test_zero_volume_first_night_kept_as_failure():
    m = module(); frame = pd.concat([data(volume=0), data(time='2024-03-27 09:00:00')])
    assert evaluate(m, frame)['status'] == 'first_bar_volume_insufficient'


def test_expected_night_with_missing_actual_data_cannot_fall_back_to_day():
    m = module(); day = data(time='2024-03-27 09:00:00'); legal = pd.concat([data(), day])
    assert evaluate(m, day, legal)['status'] != 'source_proxy_qualified_not_execution'


def test_missing_expected_clock_does_not_invent_open():
    m = module(); frame = data()
    assert evaluate(m, frame, frame.iloc[:0])['status'] == 'expected_next_window_missing'


def test_unknown_clock_anchor_is_not_rounded_or_moved():
    m = module(); result = evaluate(m, data(time='2024-03-27 09:30:00'))
    assert result['status'] == 'unsupported_expected_anchor'


def test_later_day_values_cannot_change_chosen_window():
    m = module(); frame = data()
    before = evaluate(m, frame)
    future = data(time='2024-03-28 09:00:00').assign(bar_date='2024-03-28', open=9999., high=9999., low=9999., close=9999.)
    assert evaluate(m, pd.concat([frame, future])) == before
