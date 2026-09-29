import importlib.util
from datetime import timedelta

import pandas as pd
import pytest


def fixture_panel(market_down_at_exit=False):
    closes = [100., 101.] * 28 + [101., 101., 96., 103., 120., 119.]
    rows = []
    dates = pd.bdate_range('2024-01-02', periods=len(closes))
    for i, price in enumerate(closes):
        opened = 102. if i == 58 else 104. if i == 60 else price
        rows.append(dict(date=dates[i], vt_symbol='600000.SSE', open=opened,
            high=max(opened, price) + 1, low=min(opened, price) - 1,
            close=price, volume=100000, adj_factor=1., limit_up=200., limit_down=1.,
            is_st=False, is_member=True, cash_dividend=0., split_ratio=1.))
        index_price = 1000 + i if not (market_down_at_exit and i == 60) else 1000
        rows.append(dict(date=dates[i], vt_symbol='000300.SSE', open=index_price,
            high=index_price, low=index_price, close=index_price, volume=100000,
            adj_factor=1., limit_up=float('nan'), limit_down=float('nan'),
            is_st=False, is_member=False, cash_dividend=0., split_ratio=1.))
    return pd.DataFrame(rows), dates


def test_real_strategy_signal_to_next_open_round_trip():
    assert importlib.util.find_spec('examples.stock_backtesting.qmt357.strategy') is not None
    from examples.stock_backtesting.qmt357.strategy import Qmt357StockStrategy
    from examples.stock_backtesting.qmt357.engine import StockBacktestingEngine
    from examples.stock_backtesting.qmt357.config import BacktestSettings
    frame, dates = fixture_panel(market_down_at_exit=True)
    engine = StockBacktestingEngine(BacktestSettings(capital=100000,
        commission_rate=0, minimum_commission=0, stamp_duty_rate=0, slippage_per_share=0))
    engine.set_panel(frame, dates[59].to_pydatetime(), dates[-1].to_pydatetime())
    engine.add_strategy(Qmt357StockStrategy, {})
    engine.run_backtesting()
    assert [x['direction'] for x in engine.executions] == ['buy', 'sell']
    assert [x['price'] for x in engine.executions] == [104, 119]
    assert [x['shares'] for x in engine.executions] == [200, 200]
    assert engine.executions[0]['signal_date'].startswith(str(dates[59].date()))
    assert engine.executions[0]['date'].startswith(str(dates[60].date()))
    assert engine.cash == 103000
    assert engine.calculate_statistics()['win_rate_pct'] == 100
    assert engine.strategy.signal_log[0]['condition_count'] == 3


def test_market_filter_blocks_entry_without_changing_stock_signal():
    assert importlib.util.find_spec('examples.stock_backtesting.qmt357.strategy') is not None
    from examples.stock_backtesting.qmt357.strategy import Qmt357StockStrategy
    from examples.stock_backtesting.qmt357.engine import StockBacktestingEngine
    from examples.stock_backtesting.qmt357.config import BacktestSettings
    frame, dates = fixture_panel()
    frame.loc[frame.vt_symbol == '000300.SSE', ['open', 'high', 'low', 'close']] = 1000
    engine = StockBacktestingEngine(BacktestSettings())
    engine.set_panel(frame, dates[59].to_pydatetime(), dates[-1].to_pydatetime())
    engine.add_strategy(Qmt357StockStrategy, {})
    engine.run_backtesting()
    assert not engine.trades


def test_future_bars_do_not_change_prior_orders():
    assert importlib.util.find_spec('examples.stock_backtesting.qmt357.strategy') is not None
    from examples.stock_backtesting.qmt357.strategy import Qmt357StockStrategy
    from examples.stock_backtesting.qmt357.engine import StockBacktestingEngine
    from examples.stock_backtesting.qmt357.config import BacktestSettings
    frame, dates = fixture_panel()
    outputs = []
    for altered in [False, True]:
        copy = frame.copy()
        if altered:
            copy.loc[(copy.date == dates[-1]) & (copy.vt_symbol == '600000.SSE'), ['open','high','low','close']] = 150
        engine = StockBacktestingEngine(BacktestSettings())
        engine.set_panel(copy, dates[59].to_pydatetime(), dates[-1].to_pydatetime())
        engine.add_strategy(Qmt357StockStrategy, {})
        engine.run_backtesting()
        outputs.append(engine.executions[0])
    assert outputs[0] == outputs[1]


def risk_engine(close, *, stop_loss=90., limit_up=200., limit_down=1.):
    """Exercise real strategy/order handling without a return-producing replay."""
    from datetime import date, datetime
    from examples.stock_backtesting.qmt357.strategy import Qmt357StockStrategy
    from examples.stock_backtesting.qmt357.engine import StockBacktestingEngine, Holding
    from examples.stock_backtesting.qmt357.config import BacktestSettings
    symbol = '600000.SSE'
    engine = StockBacktestingEngine(BacktestSettings())
    engine.datetime = datetime(2024, 1, 3)
    engine.vt_symbols = [symbol]
    engine.priceticks = {symbol: .01}
    engine.add_strategy(Qmt357StockStrategy, {})
    engine.strategy.trading = True
    engine.holdings[symbol] = Holding(100, 100., date(2024, 1, 2), 10000., stop_loss, 200., 1.)
    engine.current_rows[symbol] = dict(close=close, limit_up=limit_up, limit_down=limit_down)
    engine.strategy.on_bars({symbol: object()})
    return engine


@pytest.mark.parametrize('old_stop', [98., 108.])
def test_upper_limit_protection_matches_source_three_percent_rule(old_stop):
    engine = risk_engine(110., stop_loss=old_stop, limit_up=110.)
    # Source 357.py:1318 overwrites with max(buy*1.01, current*0.97).
    assert engine.holdings['600000.SSE'].stop_loss == pytest.approx(106.7)
    assert not engine.active_limit_orders


def test_profitable_lower_limit_resets_protection_to_buy_price_like_source():
    engine = risk_engine(110., stop_loss=108., limit_down=110.)
    assert engine.holdings['600000.SSE'].stop_loss == 100.
    assert not engine.active_limit_orders


def test_current_exit_uses_old_stop_even_when_lower_limit_protection_is_reset():
    # Source snapshots stop_loss before changing pos_data; the reset applies next check.
    engine = risk_engine(105., stop_loss=108., limit_down=105.)
    assert engine.holdings['600000.SSE'].stop_loss == 100.
    assert len(engine.active_limit_orders) == 1
    assert list(engine.order_reasons.values()) == ['stop_loss']


@pytest.mark.parametrize('close', [100., 99., 95.])
def test_lower_limit_extra_exit_does_not_fire_until_loss_exceeds_five_percent(close):
    engine = risk_engine(close, limit_down=close)
    assert not engine.active_limit_orders


def test_lower_limit_extra_exit_fires_for_loss_strictly_beyond_five_percent():
    engine = risk_engine(94., limit_down=94.)
    assert len(engine.active_limit_orders) == 1
    assert list(engine.order_reasons.values()) == ['limit_down_risk']
