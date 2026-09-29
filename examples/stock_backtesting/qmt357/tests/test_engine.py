"""Independent, hand-computable cash-account and next-open execution cases."""
from __future__ import annotations

import importlib.util
from datetime import datetime

import pandas as pd
import pytest


def test_engine_implementation_available():
    assert importlib.util.find_spec('examples.stock_backtesting.qmt357.engine') is not None


@pytest.fixture
def api():
    # Missing implementation must be a test failure, not a collection error.
    name = 'examples.stock_backtesting.qmt357.engine'
    assert importlib.util.find_spec(name) is not None, 'stock cash engine not implemented'
    from examples.stock_backtesting.qmt357.engine import StockBacktestingEngine
    from examples.stock_backtesting.qmt357.config import BacktestSettings
    from vnpy_portfoliostrategy.template import StrategyTemplate
    return StockBacktestingEngine, BacktestSettings, StrategyTemplate


def panel(prices=(10, 11, 12, 13), **changes):
    rows = []
    for i, price in enumerate(prices):
        row = dict(date=pd.Timestamp('2024-01-02') + pd.Timedelta(days=i),
                   vt_symbol='600000.SSE', open=price, high=price + .5,
                   low=price - .5, close=price, volume=100000,
                   adj_factor=1., limit_up=30., limit_down=1.,
                   is_st=False, is_member=True, cash_dividend=0., split_ratio=1.)
        for key, values in changes.items():
            row[key] = values[i]
        rows.append(row)
    return pd.DataFrame(rows)


def make_engine(api, frame, *, sell_on=None, capital=10000, **settings):
    Engine, Settings, Template = api

    class Once(Template):
        def on_init(self):
            pass

        def on_bars(self, bars):
            dt = self.strategy_engine.datetime
            if dt.day == 2:
                self.buy('600000.SSE', 10., 1000)
            if sell_on == dt.day:
                self.sell('600000.SSE', .01, self.get_pos('600000.SSE'))

    costs = dict(commission_rate=0., minimum_commission=0., stamp_duty_rate=0., slippage_per_share=0.)
    costs.update(settings)
    cfg = Settings(capital=capital, **costs)
    engine = Engine(cfg)
    engine.set_panel(frame, datetime(2024, 1, 2), datetime(2024, 1, 5))
    engine.add_strategy(Once, {})
    return engine


def test_next_open_and_daily_cap_cash_not_double_charged(api):
    engine = make_engine(api, panel())
    engine.run_backtesting()
    trades = list(engine.trades.values())
    assert len(trades) == 1
    assert trades[0].datetime.day == 3
    assert trades[0].price == 11
    # 30% of 10,000 = 3,000, rounded down to 200 shares at next open 11.
    assert trades[0].volume == 200
    assert engine.cash == 7800
    assert engine.calculate_result().iloc[-1].equity == 10400


def test_exit_is_next_day_and_actual_fill_updates_position(api):
    engine = make_engine(api, panel(), sell_on=3)
    engine.run_backtesting()
    assert [t.datetime.day for t in engine.trades.values()] == [3, 4]
    assert engine.cash == 10200
    assert not engine.holdings
    assert engine.round_trips[0]['net_pnl'] == 200


@pytest.mark.parametrize('changes', [
    {'volume': [100000, 0, 100000, 100000]},
    {'limit_up': [30, 11, 30, 30]},
    {'is_st': [False, True, False, False]},
    {'is_member': [True, False, True, True]},
])
def test_untradeable_open_cancels_buy_without_fake_fill(api, changes):
    engine = make_engine(api, panel(**changes))
    engine.run_backtesting()
    assert not engine.trades
    assert engine.cash == 10000
    assert engine.calculate_result().equity.tolist() == [10000] * 4


def test_missing_bar_does_not_fill_from_cached_close(api):
    frame = panel()
    index = frame.copy()
    index['vt_symbol'] = '000300.SSE'
    frame = pd.concat([frame[frame.date.dt.day != 3], index])
    engine = make_engine(api, frame)
    engine.run_backtesting()
    assert not engine.trades


def test_limit_down_sell_remains_pending_until_tradeable(api):
    engine = make_engine(api, panel(limit_down=[1, 1, 12, 1]), sell_on=3)
    engine.run_backtesting()
    trades = list(engine.trades.values())
    assert len(trades) == 2
    assert trades[-1].datetime.day == 5
    assert engine.cash == 10400


def test_dividend_is_credited_and_split_does_not_create_loss(api):
    engine = make_engine(api, panel(prices=[10, 10, 4.5, 4.5],
        adj_factor=[1, 1, 2.2, 2.2], cash_dividend=[0, 0, 1, 0],
        split_ratio=[1, 1, 2, 1]))
    engine.run_backtesting()
    assert engine.cash == 7300  # 7,000 after buy, plus 300 dividend.
    assert engine.holdings['600000.SSE'].shares == 600
    assert engine.calculate_result().iloc[-1].equity == 10000


def test_unexplained_adjustment_change_while_held_fails(api):
    engine = make_engine(api, panel(adj_factor=[1, 1, 2, 2]))
    with pytest.raises(ValueError, match='corporate'):
        engine.run_backtesting()


def test_dividend_and_split_on_suspended_day_do_not_fill_or_disappear(api):
    frame = panel(prices=(10., 10., 4.5, 5.), volume=[100000, 100000, 0, 100000],
        adj_factor=[1., 1., 2.222222, 2.222222],
        cash_dividend=[0., 0., 1., 0.], split_ratio=[1., 1., 2., 1.])
    engine = make_engine(api, frame, sell_on=3)
    engine.run_backtesting()
    # Jan 3 buys 300 shares for 3,000; Jan 4 credits 300 and splits to 600.
    # Suspended ex-date cannot sell. Jan 5 finally exits 600 shares at 5.
    assert [(t.datetime.day, t.volume) for t in engine.trades.values()] == [(3, 300), (5, 600)]
    assert engine.cash == 10300.
    assert engine.round_trips[0]['net_pnl'] == 300.
    halt = next(row for row in engine.position_coverage if row['date'] == '2024-01-04')
    assert halt['is_suspended'] and halt['stale_sessions'] == 1
    assert halt['shares'] == 600
    assert halt['market_value'] == 2700.
    assert engine.calculate_result().loc[pd.Timestamp('2024-01-04').date(), 'equity'] == 10000.


def test_initial_drawdown_uses_initial_capital(api):
    engine = make_engine(api, panel(prices=[10, 10, 9, 9]))
    engine.run_backtesting()
    stats = engine.calculate_statistics()
    assert stats['end_equity'] == 9700
    assert stats['max_drawdown_pct'] == pytest.approx(-3)


def test_t_plus_one_rejects_a_same_day_sell(api):
    engine = make_engine(api, panel())
    engine.run_backtesting()
    from vnpy.trader.constant import Direction, Offset
    engine.datetime = datetime(2024, 1, 3)
    engine.strategy.trading = True
    # Force an already queued sell to be evaluated on the acquisition date.
    ids = engine.send_order(engine.strategy, '600000.SSE', Direction.SHORT,
                            Offset.CLOSE, .01, 200, False, False)
    engine.limit_orders[ids[0]].datetime = datetime(2024, 1, 2)
    engine.current_rows = {'600000.SSE': panel().iloc[1].to_dict()}
    engine.cross_limit_order()
    assert len(engine.trades) == 1
    assert engine.holdings['600000.SSE'].shares == 200


def test_commission_minimum_stamp_and_slippage_reconcile_cash(api):
    engine = make_engine(api, panel(prices=[10, 10, 12, 12]), sell_on=3,
                         minimum_commission=5, stamp_duty_rate=.001, slippage_per_share=.01)
    engine.run_backtesting()
    # 300 shares would exceed the 3,000 budget after fees, so only 200 fill.
    assert engine.executions[0]['shares'] == 200
    assert engine.executions[0]['price'] == 10.01
    assert engine.executions[1]['price'] == 11.99
    # 10,000 - (2,002+5) + (2,398-5-2.398).
    assert engine.cash == pytest.approx(10383.602)
    assert engine.round_trips[0]['net_pnl'] == pytest.approx(383.602)
    assert engine.calculate_statistics()['total_slippage'] == 4


def test_zero_trades_still_produces_complete_daily_equity(api):
    engine = make_engine(api, panel(), capital=100)
    engine.run_backtesting()
    assert not engine.trades
    assert engine.calculate_statistics()['total_return_pct'] == 0
    assert engine.calculate_statistics()['win_rate_pct'] is None
    assert len(engine.calculate_result()) == 4


def test_held_missing_prices_are_reported_not_silently_current(api):
    frame = panel()
    index = frame.copy()
    index['vt_symbol'] = '000300.SSE'
    # Buy on Jan 3, then keep the holding with two missing stock sessions.
    engine = make_engine(api, pd.concat([frame[frame.date.dt.day <= 3], index]))
    engine.run_backtesting()
    stats = engine.calculate_statistics()
    assert stats['stale_holding_days'] == 2
    assert stats['max_stale_calendar_days'] == 2
    assert stats['end_stale_market_value'] == 2200
    audit = engine.position_coverage[-1]
    assert audit['last_quote_date'] == '2024-01-03'
    assert audit['has_bar'] is False
    assert audit['stale_sessions'] == 2
    assert engine.calculate_result().iloc[-1].equity == 10000


def test_suspended_held_prices_are_distinguished_from_missing(api):
    engine = make_engine(api, panel(volume=[100000, 100000, 0, 100000]))
    engine.run_backtesting()
    audit = engine.position_coverage[1]
    assert audit['has_bar'] is True
    assert audit['is_suspended'] is True
    assert audit['stale_sessions'] == 1
    assert engine.calculate_statistics()['end_stale_market_value'] == 0
