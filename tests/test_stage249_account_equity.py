"""Equity conservation across real strategy callbacks and vendor daily accounting.

Run with the same vnpy_portfoliostrategy dependency path as the frozen replay.
Only external mapping readers are replaced: strategy initialization, position
updates, costs, risk refresh, and end-of-day settlement remain real code.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from unittest.mock import patch

import unittest
from math import isclose

PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
sys.path.insert(0, str(PORTFOLIO_DIR))

from vnpy.trader.constant import Direction, Exchange, Interval, Offset
from vnpy.trader.object import BarData, TradeData
from vnpy_portfoliostrategy.backtesting import BacktestingEngine, PortfolioDailyResult
import qmt_roll_portfolio_strategy as strategy_module


CAPITAL = 150_000.0
A = "rb2505.SHFE"
B = "rb2510.SHFE"
C = "cu2505.SHFE"


def make_strategy(*, positions=None, previous=None, rate=0.0, slippage=0.0, engine_class=BacktestingEngine):
    engine = engine_class()
    engine.capital = CAPITAL
    engine.sizes = {A: 10, B: 10, C: 5}
    engine.rates = {symbol: rate for symbol in engine.sizes}
    engine.slippages = {symbol: slippage for symbol in engine.sizes}
    engine.priceticks = {symbol: 1.0 for symbol in engine.sizes}
    metadata = {
        "product_symbols": [],  # Account-only fixture: no strategy entry signals.
        "source_symbol_by_contract": {A: "rb.SHFE", B: "rb.SHFE", C: "cu.SHFE"},
    }
    with (
        patch.object(strategy_module, "load_product_universe_symbols", return_value=[]),
        patch.object(strategy_module, "build_daily_mapping", return_value={}),
        patch.object(strategy_module, "build_contract_metadata", return_value=metadata),
    ):
        strategy = strategy_module.QmtRollPortfolioStrategy(
            engine, "equity-conservation", list(engine.sizes), {"capital_base": CAPITAL}
        )
    engine.strategy = strategy
    strategy.pos_data.update(positions or {})
    strategy.target_data.update(positions or {})
    strategy.last_close_prices.update(previous or {A: 100.0})
    return strategy, engine


def bars_for(date: str, closes: dict[str, float]):
    return {
        vt_symbol: BarData(
            symbol=vt_symbol.split(".")[0], exchange=Exchange.SHFE,
            datetime=datetime.fromisoformat(date), interval=Interval.DAILY,
            open_price=close, high_price=close, low_price=close, close_price=close,
            gateway_name="BACKTESTING",
        )
        for vt_symbol, close in closes.items()
    }


def fill(strategy, engine, symbol, signed_volume, price, *, offset=Offset.OPEN, when=None, trading_date=None):
    trade = TradeData(
        symbol=symbol.split(".")[0], exchange=Exchange.SHFE,
        orderid="fixture", tradeid=str(engine.trade_count + 1),
        direction=Direction.LONG if signed_volume > 0 else Direction.SHORT,
        offset=offset, price=price, volume=abs(signed_volume),
        datetime=when or engine.datetime, gateway_name="BACKTESTING",
    )
    if trading_date is not None:
        trade.trading_date = trading_date
    engine.trade_count += 1
    engine.trades[trade.vt_tradeid] = trade
    strategy.update_trade(trade)
    # Account fixture keeps targets aligned, avoiding unrelated signal orders.
    strategy.target_data[symbol] = strategy.pos_data[symbol]
    return trade


def daily_pnl(engine, bars, previous, start_positions, trades):
    daily = PortfolioDailyResult(engine.datetime.date(), {
        symbol: bar.close_price for symbol, bar in bars.items()
    })
    for trade in trades:
        daily.add_trade(trade)
    daily.calculate_pnl(previous, start_positions, engine.sizes, engine.rates, engine.slippages)
    return daily.net_pnl


TRADE_CASES = [
    ("open-long", 0, [(2, 105, Offset.OPEN)], 100.0),
    ("open-short", 0, [(-2, 105, Offset.OPEN)], -100.0),
    ("close-long", 2, [(-2, 105, Offset.CLOSE)], 100.0),
    ("close-short", -2, [(2, 105, Offset.CLOSE)], -100.0),
    ("add-long", 2, [(1, 105, Offset.OPEN)], 250.0),
    ("reduce-long", 3, [(-1, 105, Offset.CLOSE)], 250.0),
    ("add-short", -2, [(-1, 105, Offset.OPEN)], -250.0),
    ("reduce-short", -3, [(1, 105, Offset.CLOSE)], -250.0),
    ("reverse-short", 2, [(-2, 105, Offset.CLOSE), (-3, 105, Offset.OPEN)], -50.0),
    ("reverse-long", -2, [(2, 105, Offset.CLOSE), (3, 105, Offset.OPEN)], 50.0),
]


def assert_close(actual, expected):
    assert isclose(actual, expected, rel_tol=0.0, abs_tol=1e-8), (actual, expected)


def case_trade_day_uses_inherited_positions_only(initial, trades, want):
    """Using post-fill positions for the holding leg breaks these literal PNLs."""
    strategy, engine = make_strategy(positions={A: initial})
    engine.datetime = datetime(2025, 1, 2)
    engine.bars = bars_for("2025-01-02", {A: 110.0})
    completed = [fill(strategy, engine, A, qty, price, offset=offset) for qty, price, offset in trades]
    assert_close(daily_pnl(engine, engine.bars, {A: 100.0}, {A: initial}, completed), want)
    assert_close(strategy._estimate_equity(engine.bars), CAPITAL + want)
    assert_close(strategy.estimated_equity, CAPITAL + want)
    strategy.on_bars(engine.bars)
    assert_close(strategy.settled_balance, CAPITAL + want)


def test_synthetic_stop_retry_callbacks_preserve_each_intermediate_equity():
    """Synthetic fills share one daily holding baseline, even with prior-night labels."""
    strategy, engine = make_strategy()
    engine.datetime = datetime(2025, 1, 3)
    engine.bars = bars_for("2025-01-03", {A: 110.0})
    completed = []
    for qty, price, offset, stamp, want in [
        (2, 105, Offset.OPEN, "2025-01-02T21:00:00", 100.0),
        (-2, 103, Offset.CLOSE, "2025-01-02T21:01:00", -40.0),
        (2, 106, Offset.OPEN, "2025-01-03T09:00:00", 40.0),
        (-2, 104, Offset.CLOSE, "2025-01-03T09:01:00", -80.0),
    ]:
        completed.append(fill(strategy, engine, A, qty, price, offset=offset,
                              when=datetime.fromisoformat(stamp)))
        assert_close(daily_pnl(engine, engine.bars, {A: 100.0}, {}, completed), want)
        assert_close(strategy._estimate_equity(engine.bars), CAPITAL + want)
        assert_close(strategy.estimated_equity, CAPITAL + want)
    strategy.on_bars(engine.bars)
    assert_close(strategy.settled_balance, CAPITAL - 80.0)


def test_costs_are_deducted_once_and_estimates_are_idempotent():
    strategy, engine = make_strategy(rate=0.001, slippage=0.5)
    engine.datetime = datetime(2025, 1, 2)
    engine.bars = bars_for("2025-01-02", {A: 110.0})
    fill(strategy, engine, A, 2, 105)
    # Gross = 100; commission = 2.1; slippage = 10.
    assert_close(strategy.trade_costs_total, 12.1)
    for _ in range(3):
        assert_close(strategy._estimate_equity(engine.bars), 150_087.9)
    strategy.on_bars(engine.bars)
    assert_close(strategy.settled_balance, 150_087.9)
    assert_close(strategy._estimate_equity(engine.bars), 150_087.9)


def test_multiday_rollover_and_other_product_match_vendor_daily_ledger():
    strategy, engine = make_strategy()
    prior = {A: 100.0}
    positions = {}
    balance = CAPITAL
    scenarios = [
        ("2025-01-02", {A: 110.0, B: 200.0, C: 300.0}, [(A, 2, 105, Offset.OPEN)], 100.0),
        ("2025-01-03", {A: 115.0, B: 205.0, C: 290.0}, [(C, -3, 295, Offset.OPEN)], 175.0),
        ("2025-01-06", {A: 120.0, B: 210.0, C: 280.0},
         [(A, -2, 118, Offset.CLOSE), (B, 2, 208, Offset.OPEN)], 250.0),
        ("2025-01-07", {A: 119.0, B: 207.0, C: 285.0}, [], -135.0),
        ("2025-01-08", {A: 118.0, B: 206.0, C: 282.0},
         [(B, -2, 205, Offset.CLOSE), (C, 3, 284, Offset.CLOSE)], -25.0),
    ]
    for date, closes, spec, want in scenarios:
        engine.datetime = datetime.fromisoformat(date)
        engine.bars = bars_for(date, closes)
        trades = [fill(strategy, engine, symbol, qty, price, offset=offset)
                  for symbol, qty, price, offset in spec]
        assert_close(daily_pnl(engine, engine.bars, prior, positions, trades), want)
        balance += want
        assert_close(strategy._estimate_equity(engine.bars), balance)
        if trades:
            assert_close(strategy.estimated_equity, balance)
        strategy.on_bars(engine.bars)
        assert_close(strategy.settled_balance, balance)
        prior = closes
        positions = dict(strategy.pos_data)
    assert_close(balance, 150_365.0)


def test_temporarily_missing_contract_keeps_last_settlement_price():
    """Dropping a held contract's mark loses its PNL when its bars resume."""
    strategy, engine = make_strategy(positions={A: 2}, previous={A: 100.0, C: 300.0})
    for date, closes, want in [
        ("2025-01-02", {A: 110.0, C: 300.0}, 150_200.0),
        ("2025-01-03", {C: 305.0}, 150_200.0),
        ("2025-01-06", {A: 120.0, C: 305.0}, 150_400.0),
    ]:
        engine.datetime = datetime.fromisoformat(date)
        engine.bars.update(bars_for(date, closes))
        strategy.on_bars(bars_for(date, closes))
        assert_close(strategy.settled_balance, want)


def test_engine_new_bars_settles_before_next_days_fill():
    """Exercise vendor matching -> update_trade -> on_bars without manual settlement."""
    strategy, engine = make_strategy()
    strategy.inited = True
    engine.vt_symbols = [A]
    for date, open_price, close_price, direction, offset, target, want in [
        ("2025-01-01", 100.0, 100.0, None, None, 0, 150_000.0),
        ("2025-01-02", 105.0, 110.0, Direction.LONG, Offset.OPEN, 2, 150_100.0),
        ("2025-01-03", 112.0, 115.0, Direction.SHORT, Offset.CLOSE, 0, 150_140.0),
    ]:
        stamp = datetime.fromisoformat(date)
        bar = bars_for(date, {A: close_price})[A]
        bar.open_price = open_price
        bar.low_price = min(open_price, close_price)
        bar.high_price = max(open_price, close_price)
        engine.history_data[(stamp, A)] = bar
        strategy.target_data[A] = target
        if direction is not None:
            engine.send_order(strategy, A, direction, offset, open_price, 2, False, False)
        engine.new_bars(stamp)
        assert_close(strategy.estimated_equity, want)
        assert_close(strategy.settled_balance, want)
    assert engine.trade_count == 2
    assert strategy.pos_data[A] == 0


def case_same_day_close_engine_carries_post_settlement_fills(initial, rate, slippage, rows):
    """SameDayClose fills after on_bars must change the next day's holding baseline."""
    from run_qmt_roll_backtest import SameDayCloseBacktestingEngine
    strategy, engine = make_strategy(positions={A: initial}, rate=rate, slippage=slippage,
                                     engine_class=SameDayCloseBacktestingEngine)
    strategy.inited = True
    engine.vt_symbols = [A]
    prior = {A: 100.0}
    positions = {A: initial}
    balance = CAPITAL
    for day, (close, quantity, offset, want) in enumerate(rows, start=1):
        stamp = datetime(2025, 1, day)
        bar = bars_for(stamp.isoformat(), {A: close})[A]
        engine.history_data[(stamp, A)] = bar
        strategy.target_data[A] = strategy.pos_data[A] + quantity
        previous_count = engine.trade_count
        if quantity:
            engine.send_order(strategy, A, Direction.LONG if quantity > 0 else Direction.SHORT,
                              offset, close, abs(quantity), False, False)
        engine.new_bars(stamp)
        trades = list(engine.trades.values())[previous_count:]
        balance += daily_pnl(engine, engine.bars, prior, positions, trades)
        assert_close(balance, want)
        assert_close(strategy.estimated_equity, want)
        assert_close(strategy.settled_balance, want)
        prior = {A: close}
        positions = dict(strategy.pos_data)


SAME_CLOSE_CASES = [
    ("same-close-long", 0, 0.0, 0.0, [
        (100.0, 2, Offset.OPEN, 150_000.0), (110.0, 0, None, 150_200.0),
        (115.0, -2, Offset.CLOSE, 150_300.0), (120.0, 0, None, 150_300.0),
    ]),
    ("same-close-short", 0, 0.0, 0.0, [
        (100.0, -2, Offset.OPEN, 150_000.0), (110.0, 0, None, 149_800.0),
        (105.0, 2, Offset.CLOSE, 149_900.0), (120.0, 0, None, 149_900.0),
    ]),
    ("same-close-inherited-long-close", 2, 0.0, 0.0, [
        (105.0, -2, Offset.CLOSE, 150_100.0), (110.0, 0, None, 150_100.0),
    ]),
    ("same-close-inherited-short-close", -2, 0.0, 0.0, [
        (105.0, 2, Offset.CLOSE, 149_900.0), (110.0, 0, None, 149_900.0),
    ]),
    ("same-close-costs-once", 0, 0.001, 0.5, [
        (100.0, 2, Offset.OPEN, 149_988.0), (110.0, 0, None, 150_188.0),
        (115.0, -2, Offset.CLOSE, 150_275.7), (120.0, 0, None, 150_275.7),
    ]),
]


def test_prior_night_fill_does_not_roll_next_day_holding_baseline():
    """The engine trading day, not the prior-night physical timestamp, owns a fill."""
    for explicit_trading_day in (False, True):
        strategy, engine = make_strategy()
        engine.datetime = datetime(2025, 1, 2)
        engine.bars = bars_for("2025-01-02", {A: 100.0})
        strategy.on_bars(engine.bars)
        engine.datetime = datetime(2025, 1, 3)
        engine.bars = bars_for("2025-01-03", {A: 110.0})
        fill(strategy, engine, A, 2, 105, when=datetime(2025, 1, 2, 21),
             trading_date=engine.datetime.date() if explicit_trading_day else None)
        assert_close(strategy._estimate_equity(engine.bars), 150_100.0)
        strategy.on_bars(engine.bars)
        assert_close(strategy.settled_balance, 150_100.0)
        engine.datetime = datetime(2025, 1, 6)
        engine.bars = bars_for("2025-01-06", {A: 115.0})
        strategy.on_bars(engine.bars)
        assert_close(strategy.settled_balance, 150_200.0)


def load_tests(loader, standard_tests, pattern):
    suite = unittest.TestSuite()
    from functools import partial
    for name, initial, trades, want in TRADE_CASES:
        case = partial(case_trade_day_uses_inherited_positions_only, initial, trades, want)
        case.__name__ = name
        suite.addTest(unittest.FunctionTestCase(case, description=name))
    for name, initial, rate, slippage, rows in SAME_CLOSE_CASES:
        case = partial(case_same_day_close_engine_carries_post_settlement_fills, initial, rate, slippage, rows)
        case.__name__ = name
        suite.addTest(unittest.FunctionTestCase(case, description=name))
    for function in (
        test_synthetic_stop_retry_callbacks_preserve_each_intermediate_equity,
        test_costs_are_deducted_once_and_estimates_are_idempotent,
        test_multiday_rollover_and_other_product_match_vendor_daily_ledger,
        test_temporarily_missing_contract_keeps_last_settlement_price,
        test_engine_new_bars_settles_before_next_days_fill,
        test_prior_night_fill_does_not_roll_next_day_holding_baseline,
    ):
        suite.addTest(unittest.FunctionTestCase(function))
    return suite


class ParametrizedEquityTests(unittest.TestCase):
    pass


def _case_method(function, arguments):
    def method(self):
        function(*arguments)
    return method


for _name, *_arguments in TRADE_CASES:
    setattr(ParametrizedEquityTests, 'test_' + _name.replace('-', '_'),
            _case_method(case_trade_day_uses_inherited_positions_only, _arguments))
for _name, *_arguments in SAME_CLOSE_CASES:
    setattr(ParametrizedEquityTests, 'test_' + _name.replace('-', '_'),
            _case_method(case_same_day_close_engine_carries_post_settlement_fills, _arguments))


if __name__ == "__main__":
    unittest.main()
