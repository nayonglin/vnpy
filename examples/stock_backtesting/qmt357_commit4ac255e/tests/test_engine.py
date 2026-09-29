"""The new engine retains stock fills and rescales peak only on explicit actions."""
from datetime import date, datetime

import pytest

from examples.stock_backtesting.qmt357.engine import Holding
from examples.stock_backtesting.qmt357_commit4ac255e.config import BacktestSettings


SYMBOL = '600000.SSE'


def holding_engine():
    from examples.stock_backtesting.qmt357_commit4ac255e.engine import Commit4ac255eEngine
    from examples.stock_backtesting.qmt357_commit4ac255e.strategy import Commit4ac255eStrategy
    engine = Commit4ac255eEngine(BacktestSettings())
    engine.datetime = datetime(2024, 1, 3)
    engine.vt_symbols = [SYMBOL]
    engine.priceticks = {SYMBOL: .01}
    engine.add_strategy(Commit4ac255eStrategy, {})
    engine.strategy.trading = True
    engine.holdings[SYMBOL] = Holding(100, 100., date(2024, 1, 2),
                                      10000., 115., 145., 1.)
    engine.last_prices[SYMBOL] = 100.
    engine.highest_closes[SYMBOL] = 140.
    return engine


def test_explicit_dividend_and_split_rescale_peak_with_cost_basis():
    engine = holding_engine()
    engine.current_rows[SYMBOL] = dict(adj_factor=2., cash_dividend=2., split_ratio=2.)
    engine._corporate_actions()
    holding = engine.holdings[SYMBOL]
    assert (holding.shares, holding.buy_price, holding.stop_loss) == (200, 49., 56.5)
    assert engine.highest_closes[SYMBOL] == 69.
    assert engine.cash == 300200.


def test_unexplained_factor_change_remains_fail_closed():
    engine = holding_engine()
    engine.current_rows[SYMBOL] = dict(adj_factor=2., cash_dividend=0., split_ratio=1.)
    with pytest.raises(ValueError, match='Unexplained corporate action'):
        engine._corporate_actions()
    assert engine.highest_closes[SYMBOL] == 140.


def test_sell_fills_next_open_and_clears_peak_for_reentry():
    engine = holding_engine()
    engine.current_rows[SYMBOL] = dict(open=111., volume=100000,
        limit_up=200., limit_down=1., is_st=False, is_member=True)
    engine.strategy.sell(SYMBOL, 110., 100)
    engine.datetime = datetime(2024, 1, 4)
    engine.cross_limit_order()
    assert [x['price'] for x in engine.executions] == [pytest.approx(110.99)]
    assert not engine.holdings
    assert SYMBOL not in engine.highest_closes
