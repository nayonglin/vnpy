import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/stage038_execution_source.py'


def module():
    assert TOOL.exists(), 'execution source audit missing'
    spec = importlib.util.spec_from_file_location('test_source038', TOOL)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def legacy(tmp_path, frames=(), seed_rows=()):
    m = module()
    seed = tmp_path / 'seed.csv'
    pd.DataFrame(seed_rows, columns=['trade_id', 'date', 'next_trade_date', 'vt_symbol',
                 'same_last5_vwap', 'preferred_real_open_proxy', 'preferred_real_open_proxy_type']).to_csv(seed, index=False)
    roots = []
    for index, frame in enumerate(frames):
        root = tmp_path / str(index)
        (root / 'DCE').mkdir(parents=True)
        frame.to_csv(root / 'DCE/jm2005_minute_backtest.csv', index=False)
        roots.append(root)
    return m, m.make_legacy(raw_roots=roots, seed_path=seed)


def bars(time='2020-01-10 21:00:00', price=101., volume=50.):
    return pd.DataFrame({'bar_datetime': pd.date_range(time, periods=5, freq='min'),
                         'open': price, 'close': price, 'volume': volume})


def resolve(value, daily=99., order_price=98.):
    order = SimpleNamespace(vt_symbol='jm2005.DCE', datetime=pd.Timestamp('2020-01-10'), price=order_price)
    return value.resolve(order, pd.Timestamp('2020-01-13'), daily)


def test_extract_does_not_execute_module_top_level():
    m = module()
    namespace = {}
    fn = m.extract_function('raise RuntimeError("must not run")\ndef target(x):\n    return x + 1\n', 'target', namespace)
    assert fn(2) == 3


@pytest.mark.parametrize('source', ['def other(): pass', 'def target(): pass\ndef target(): pass'])
def test_missing_or_duplicate_definition_rejected(source):
    with pytest.raises(ValueError, match='source_function_inventory'):
        module().extract_function(source, 'target', {})


def test_seed_precedes_raw(tmp_path):
    _, value = legacy(tmp_path, [bars()], [[1, '2020-01-10', '2020-01-13', 'jm2005.DCE', '', 123., 'fixture']])
    assert resolve(value)[:2] == (123., 'stage149_fixture')


def test_night_window_precedes_day(tmp_path):
    _, value = legacy(tmp_path, [pd.concat([bars(), bars('2020-01-13 09:00:00', 111.)])])
    assert resolve(value)[:2] == (101., 'raw_night_2100_2105_first_open')


def test_missing_night_uses_day_in_original_logic(tmp_path):
    _, value = legacy(tmp_path, [bars('2020-01-13 09:00:00', 111.)])
    assert resolve(value)[:2] == (111., 'raw_day_0900_0905_first_open')


@pytest.mark.parametrize('daily,price', [(99., 99.), (0., 98.)])
def test_original_daily_and_order_fallback_preserved(tmp_path, daily, price):
    _, value = legacy(tmp_path)
    assert resolve(value, daily) == (price, 'fallback_daily_next_open', {})


def test_original_zero_volume_price_is_not_changed_to_liquidity_gate(tmp_path):
    _, value = legacy(tmp_path, [bars(volume=0.)])
    assert resolve(value)[0] == 101.


def test_last_raw_root_wins_duplicate_even_if_older_name(tmp_path):
    _, value = legacy(tmp_path, [bars(price=111.), bars(price=222.)])
    assert resolve(value)[0] == 222.


def test_raw_frame_cache_does_not_change_resolution(tmp_path):
    _, value = legacy(tmp_path, [bars()])
    assert resolve(value) == resolve(value)
    assert len(value.raw_cache) == 1


def test_conflicting_observed_order_identity_rejected():
    m = module()
    a = {'active_orders': [{'order_id': 'BACKTESTING.1', 'volume': 2}]}
    b = {'active_orders': [{'order_id': 'BACKTESTING.1', 'volume': 3}]}
    assert m.order_inventory([a, a])['BACKTESTING.1']['volume'] == 2
    with pytest.raises(ValueError, match='conflicting_observed_order'):
        m.order_inventory([a, b])


def test_unmatched_normal_trade_is_not_inferred_from_previous_day():
    m = module()
    assert m.trade_origin('BACKTESTING.5', {}) == 'missing_observed_order'
    assert m.trade_origin('BACKTESTING.5.stage847_c9.1', {}) == 'synthetic_intraday'
    assert m.trade_origin('BACKTESTING.5.unknown', {}) == 'missing_observed_order'


def test_original_rebalance_and_delayed_fill_order_are_preserved():
    m = module()
    assert m.execution_boundaries() == {
        'delayed_fill_before_strategy': True,
        'ordinary_rebalance_before_forced_margin': True,
        'rebalance_cancels_all_first': True,
        'open_fill_calls_intraday_before_next_order': True,
        'globally_chronological_minute_engine': False,
    }


@pytest.mark.parametrize('change,status', [({}, 'matched'), ({'volume': 3}, 'order_identity_mismatch'),
                         ({'price': 222.}, 'price_or_time_mismatch'),
                         ({'date': '2020-01-10'}, 'price_or_time_mismatch')])
def test_frozen_trade_identity_price_and_time_are_separate_gates(tmp_path, change, status):
    m, value = legacy(tmp_path, [bars()])
    assert hasattr(m, 'audit_trade'), 'single trade audit missing'
    order = {'order_id': 'BACKTESTING.1', 'vt_symbol': 'jm2005.DCE', 'datetime': '2020-01-10',
             'direction': 'Direction.LONG', 'offset': 'Offset.OPEN', 'volume': 2, 'price': 100.}
    trade = {'trade_id': 'BACKTESTING.1', 'order_id': 'BACKTESTING.1', 'date': '2020-01-13',
             'vt_symbol': 'jm2005.DCE', 'direction': '\u591a', 'offset': '\u5f00', 'volume': 2, 'price': 101., **change}
    result = m.audit_trade(trade, {'BACKTESTING.1': order}, value,
                           {('jm2005.DCE', trade['date']): 99.})
    assert result['status'] == status


def test_missing_daily_bar_is_not_filled_with_order_price(tmp_path):
    m, value = legacy(tmp_path)
    assert hasattr(m, 'audit_trade'), 'single trade audit missing'
    order = {'vt_symbol': 'jm2005.DCE', 'datetime': '2020-01-10', 'direction': 'Direction.LONG',
             'offset': 'Offset.OPEN', 'volume': 2, 'price': 100.}
    trade = {'trade_id': 'BACKTESTING.1', 'order_id': 'BACKTESTING.1', 'date': '2020-01-13',
             'vt_symbol': 'jm2005.DCE', 'direction': '\u591a', 'offset': '\u5f00', 'volume': 2, 'price': 101.}
    assert m.audit_trade(trade, {'BACKTESTING.1': order}, value, {})['status'] == 'daily_bar_missing'
