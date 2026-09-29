"""Behavioral checks for the committed oscillation strategy's tiered stop."""
from datetime import date, datetime

import pandas as pd
import pytest

from examples.stock_backtesting.qmt357.engine import Holding
from examples.stock_backtesting.qmt357_commit4ac255e.config import BacktestSettings


SYMBOL = '600000.SSE'


def risk_engine(*, buy=100., stop=98., close=100., high=150.,
                limit_up=200., limit_down=1.):
    from examples.stock_backtesting.qmt357_commit4ac255e.engine import Commit4ac255eEngine
    from examples.stock_backtesting.qmt357_commit4ac255e.strategy import Commit4ac255eStrategy
    engine = Commit4ac255eEngine(BacktestSettings())
    engine.datetime = datetime(2024, 1, 3)
    engine.vt_symbols = [SYMBOL]
    engine.priceticks = {SYMBOL: .01}
    engine.add_strategy(Commit4ac255eStrategy, {})
    engine.strategy.trading = True
    engine.holdings[SYMBOL] = Holding(100, buy, date(2024, 1, 2),
                                      buy * 100, stop, buy * 1.45, 1.)
    engine.current_rows[SYMBOL] = dict(close=close, high=high,
        limit_up=limit_up, limit_down=limit_down)
    return engine


def observe(engine, close, *, high=200., limit_up=200., limit_down=1.):
    engine.current_rows[SYMBOL].update(close=close, high=high,
        limit_up=limit_up, limit_down=limit_down)
    engine.strategy.on_bars({SYMBOL: object()})
    return engine.holdings[SYMBOL].stop_loss


@pytest.mark.parametrize(('peak', 'expected'), [
    (109.99, 100.), (110., 103.), (120., 106.),
    (130., 110.), (140., 115.),
])
def test_exact_peak_boundaries_set_source_tiers(peak, expected):
    # A wrong comparison or stop multiplier must change the actual holding stop.
    engine = risk_engine(close=peak)
    assert observe(engine, peak) == pytest.approx(expected)
    assert engine.strategy.trail_log[-1]['peak'] == pytest.approx(peak)


def test_strict_positive_profit_and_close_not_bar_high():
    engine = risk_engine(close=100., high=150.)
    assert observe(engine, 100., high=150.) == 98.
    assert engine.strategy.trail_log[-1]['peak'] == 100.
    assert observe(engine, 101., high=150.) == 100.
    assert engine.strategy.trail_log[-1]['observed_close'] == 101.
    assert engine.strategy.trail_log[-1]['peak'] == 101.


def test_warmup_does_not_update_existing_holding_stop_or_trail_log():
    engine = risk_engine(close=140.)
    engine.strategy.trading = False
    assert observe(engine, 140.) == 98.
    assert engine.strategy.trail_log == []


def test_trail_log_uses_trade_symbol_key():
    engine = risk_engine(close=110.)
    observe(engine, 110.)
    assert engine.strategy.trail_log[-1]['vt_symbol'] == SYMBOL


def test_three_real_signals_share_ninety_percent_daily_budget_and_fill_next_open():
    from examples.stock_backtesting.qmt357_commit4ac255e.engine import Commit4ac255eEngine
    from examples.stock_backtesting.qmt357_commit4ac255e.strategy import Commit4ac255eStrategy
    closes = [100., 101.] * 28 + [101., 101., 96., 103., 120.]
    dates = pd.bdate_range('2024-01-02', periods=len(closes))
    rows = []
    for i, close in enumerate(closes):
        for symbol in ('600000.SSE', '600001.SSE', '600002.SSE', '600003.SSE'):
            opened = 102. if i == 58 else 104. if i == 60 else close
            rows.append(dict(date=dates[i], vt_symbol=symbol, open=opened,
                high=max(opened, close) + 1, low=min(opened, close) - 1,
                close=close, volume=100000, adj_factor=1., limit_up=200.,
                limit_down=1., is_st=False, is_member=True,
                cash_dividend=0., split_ratio=1.))
        index = 1000. + i
        rows.append(dict(date=dates[i], vt_symbol='000300.SSE', open=index,
            high=index, low=index, close=index, volume=100000,
            adj_factor=1., limit_up=float('nan'), limit_down=float('nan'),
            is_st=False, is_member=False, cash_dividend=0., split_ratio=1.))
    engine = Commit4ac255eEngine(BacktestSettings(commission_rate=0.,
        minimum_commission=0., stamp_duty_rate=0., slippage_per_share=0.))
    engine.set_panel(pd.DataFrame(rows), dates[59].to_pydatetime(), dates[60].to_pydatetime())
    engine.add_strategy(Commit4ac255eStrategy, {})
    engine.run_backtesting()
    buys = [x for x in engine.executions if x['direction'] == 'buy']
    assert [x['vt_symbol'] for x in buys] == ['600000.SSE', '600001.SSE', '600002.SSE']
    assert [x['shares'] for x in buys] == [900, 900, 700]
    assert [x['budget'] for x in engine.strategy.signal_log] == [96000., 96000., 78000.]
    assert all(x['signal_date'].startswith(str(dates[59].date())) for x in buys)
    assert all(x['date'].startswith(str(dates[60].date())) for x in buys)
    assert sum(x['turnover'] for x in buys) == 260000.
    assert sum(x['turnover'] for x in buys) <= 270000.
    assert engine.cash == 40000.


def test_peak_tier_survives_retracement_and_exit_uses_raised_stop():
    engine = risk_engine(close=140.)
    assert observe(engine, 140.) == pytest.approx(115.)
    assert observe(engine, 110.) == pytest.approx(115.)
    assert engine.strategy.trail_log[-1]['peak'] == 140.
    assert list(engine.order_reasons.values()) == ['stop_loss']


def test_at_or_below_buy_does_not_reapply_tier_after_special_reset():
    engine = risk_engine(close=130.)
    assert observe(engine, 130.) == pytest.approx(110.)
    engine.holdings[SYMBOL].stop_loss = 90.
    assert observe(engine, 100.) == 90.
    assert engine.strategy.trail_log[-1]['old_stop'] == 90.
    assert engine.strategy.trail_log[-1]['new_stop'] == 90.


def test_pending_sell_skips_trail_check_and_new_holding_resets_peak():
    engine = risk_engine(close=140.)
    observe(engine, 140.)
    engine.strategy.sell(SYMBOL, 110., 100)
    count = len(engine.strategy.trail_log)
    observe(engine, 105.)
    assert len(engine.strategy.trail_log) == count
    engine.active_limit_orders.clear()
    del engine.holdings[SYMBOL]
    engine.cross_limit_order()
    engine.holdings[SYMBOL] = Holding(100, 105., date(2024, 1, 3),
                                      10500., 102.9, 152.25, 1.)
    assert observe(engine, 106., high=200.) == 105.
    assert engine.strategy.trail_log[-1]['peak'] == 106.


def test_upper_limit_protection_can_lower_stored_stop_but_not_current_snapshot():
    engine = risk_engine(close=140., limit_up=140.)
    assert observe(engine, 140., limit_up=140.) == pytest.approx(135.8)
    assert engine.strategy.trail_log[-1]['new_stop'] == pytest.approx(115.)
    assert not engine.active_limit_orders


def test_lower_limit_reset_follows_trail_but_current_exit_uses_trail_snapshot():
    engine = risk_engine(close=110., limit_down=110.)
    engine.highest_closes[SYMBOL] = 140.
    assert observe(engine, 110., limit_down=110.) == 100.
    assert engine.strategy.trail_log[-1]['new_stop'] == pytest.approx(115.)
    assert list(engine.order_reasons.values()) == ['stop_loss']
