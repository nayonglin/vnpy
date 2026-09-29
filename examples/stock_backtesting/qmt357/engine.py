"""vn.py portfolio engine with a stock-only cash ledger and next-open intents.

Orders created through StrategyTemplate.buy/sell are market-on-next-open
intents, not intraday limit orders. No broker, database or datafeed is opened.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import math

import numpy as np
import pandas as pd
from vnpy.trader.constant import Direction, Exchange, Interval, Offset, Status
from vnpy.trader.object import BarData, TradeData
from vnpy_portfoliostrategy.backtesting import BacktestingEngine

from .config import BacktestSettings, INDEX_SYMBOL


@dataclass
class Holding:
    shares: int
    buy_price: float
    buy_date: date
    entry_cost: float
    stop_loss: float
    stop_profit: float
    adj_factor: float
    dividends: float = 0.


class StockBacktestingEngine(BacktestingEngine):
    def __init__(self, settings: BacktestSettings):
        super().__init__()
        self.settings = settings
        self.capital = self.cash = settings.capital
        self.holdings: dict[str, Holding] = {}
        self.last_prices: dict[str, float] = {}
        self.last_quote_dates: dict[str, date] = {}
        self.last_quote_sessions: dict[str, int] = {}
        self.position_coverage: list[dict] = []
        self.current_rows: dict[str, dict] = {}
        self.order_budgets: dict[str, float] = {}
        self.order_reasons: dict[str, str] = {}
        self.executions: list[dict] = []
        self.rejections: list[dict] = []
        self.round_trips: list[dict] = []
        self.equity_rows: list[dict] = []
        self.opening_used = 0.
        self.opening_limit = settings.capital * settings.day_position_size
        self._has_run = False

    def set_panel(self, panel: pd.DataFrame, start: datetime, end: datetime):
        self.panel = panel.copy().sort_values(['date', 'vt_symbol'])
        self.panel['date'] = pd.to_datetime(self.panel['date']).dt.normalize()
        if start > end or self.panel.duplicated(['date', 'vt_symbol']).any():
            raise ValueError('Invalid date range or duplicated bars')
        self.start, self.end = start, end
        self.vt_symbols = sorted(self.panel.vt_symbol.unique())
        self.priceticks = dict.fromkeys(self.vt_symbols, .01)
        self.interval = Interval.DAILY

    def equity(self) -> float:
        return self.cash + sum(h.shares * self.last_prices[s] for s, h in self.holdings.items())

    def fee(self, notional: float, is_buy: bool) -> float:
        return max(self.settings.minimum_commission, notional * self.settings.commission_rate) + (
            0. if is_buy else notional * self.settings.stamp_duty_rate)

    def send_order(self, strategy, vt_symbol, direction, offset, price, volume, lock=False, net=False):
        if vt_symbol == INDEX_SYMBOL or volume <= 0:
            return []
        if (direction, offset) not in [(Direction.LONG, Offset.OPEN), (Direction.SHORT, Offset.CLOSE)]:
            raise ValueError('Stock backtest permits long-only buy/sell orders')
        return super().send_order(strategy, vt_symbol, direction, offset, price, volume, lock, net)

    def _blocked(self, order, reason: str, cancel: bool):
        self.rejections.append(dict(date=self.datetime.isoformat(), vt_orderid=order.vt_orderid,
                                    vt_symbol=order.vt_symbol, reason=reason))
        if cancel:
            self.cancel_order(self.strategy, order.vt_orderid)

    def _corporate_actions(self):
        for symbol, holding in self.holdings.items():
            row = self.current_rows.get(symbol)
            if row is None:
                continue
            factor = float(row['adj_factor'])
            dividend = float(row.get('cash_dividend', 0.))
            split = float(row.get('split_ratio', 1.))
            if not math.isclose(factor, holding.adj_factor, rel_tol=1e-9) and dividend == 0 and split == 1:
                raise ValueError(f'Unexplained corporate action for {symbol} on {self.datetime.date()}')
            if dividend or split != 1:
                shares = holding.shares * split
                if not math.isclose(shares, round(shares), abs_tol=1e-6):
                    raise ValueError(f'Fractional corporate action shares unsupported: {symbol}')
                credit = holding.shares * dividend
                self.cash += credit
                holding.dividends += credit
                holding.shares = int(round(shares))
                holding.buy_price = (holding.buy_price - dividend) / split
                holding.stop_loss = (holding.stop_loss - dividend) / split
                holding.stop_profit = (holding.stop_profit - dividend) / split
                self.last_prices[symbol] = (self.last_prices[symbol] - dividend) / split
                self.strategy.pos_data[symbol] = holding.shares
                # Pending closes must sell the post-action number of shares.
                for order in self.active_limit_orders.values():
                    if order.vt_symbol == symbol and order.direction == Direction.SHORT:
                        order.volume = holding.shares
            holding.adj_factor = factor

    def cross_limit_order(self):
        # Free sale cash first. Purchase-day restrictions still apply.
        orders = sorted(self.active_limit_orders.values(), key=lambda o: o.direction == Direction.LONG)
        for order in list(orders):
            if order.datetime.date() >= self.datetime.date():
                continue
            buy = order.direction == Direction.LONG
            row = self.current_rows.get(order.vt_symbol)
            if row is None or row['volume'] <= 0:
                self._blocked(order, 'missing_or_suspended', buy)
                continue
            if buy and (row['is_st'] or not row['is_member']):
                self._blocked(order, 'not_eligible_at_execution', True)
                continue
            opened = float(row['open'])
            if (buy and opened >= row['limit_up'] - 1e-8) or (not buy and opened <= row['limit_down'] + 1e-8):
                self._blocked(order, 'open_at_price_limit', buy)
                continue
            slip = self.settings.slippage_per_share
            price = opened + (slip if buy else -slip)
            if price > row['limit_up'] or price < row['limit_down'] or price <= 0:
                self._blocked(order, 'slippage_outside_price_limit', buy)
                continue
            holding = self.holdings.get(order.vt_symbol)
            if buy:
                if holding or len(self.holdings) >= self.settings.max_positions:
                    self._blocked(order, 'position_limit_or_existing', True)
                    continue
                # Both fee and principal fit the remaining daily and cash budgets.
                budget = min(self.cash * (1 - self.settings.cash_buffer),
                             self.opening_limit - self.opening_used,
                             self.order_budgets.get(order.vt_orderid, math.inf))
                shares = min(int(order.volume) // 100 * 100, max(0, int(budget / price / 100) * 100))
                while shares > 0 and shares * price + self.fee(shares * price, True) > budget + 1e-8:
                    shares -= 100
                if shares == 0:
                    self._blocked(order, 'insufficient_cash_or_daily_budget', True)
                    continue
            else:
                if holding is None:
                    self._blocked(order, 'no_holding', True)
                    continue
                if holding.buy_date >= self.datetime.date():
                    self._blocked(order, 't_plus_one', False)
                    continue
                shares = min(holding.shares, int(order.volume))
                # This strategy only has full-position exits; no ambiguous PnL allocation.
                if shares != holding.shares:
                    raise ValueError('Partial stock exits are not supported in the 357 migration')
            notional = price * shares
            fee = self.fee(notional, buy)
            if buy:
                self.cash -= notional + fee
                self.opening_used += notional + fee
                self.holdings[order.vt_symbol] = Holding(
                    shares, price, self.datetime.date(), notional + fee,
                    price * (1 - self.settings.stop_loss_pct),
                    price * (1 + self.settings.stop_profit_pct), float(row['adj_factor']))
            else:
                self.cash += notional - fee
                self.round_trips.append(dict(vt_symbol=order.vt_symbol,
                    entry_date=str(holding.buy_date), exit_date=str(self.datetime.date()),
                    entry_cost=holding.entry_cost, proceeds=notional - fee,
                    dividends=holding.dividends,
                    net_pnl=notional - fee + holding.dividends - holding.entry_cost))
                del self.holdings[order.vt_symbol]
            order.traded = shares
            order.status = Status.ALLTRADED if shares == order.volume else Status.CANCELLED
            self.active_limit_orders.pop(order.vt_orderid, None)
            self.strategy.update_order(order)
            self.trade_count += 1
            trade = TradeData(symbol=order.symbol, exchange=order.exchange, orderid=order.orderid,
                tradeid=str(self.trade_count), direction=order.direction, offset=order.offset,
                price=price, volume=shares, datetime=self.datetime, gateway_name=self.gateway_name)
            self.trades[trade.vt_tradeid] = trade
            self.strategy.update_trade(trade)
            self.executions.append(dict(date=self.datetime.isoformat(), vt_symbol=trade.vt_symbol,
                direction='buy' if buy else 'sell', price=price, shares=shares,
                turnover=notional, commission=fee, slippage=slip * shares,
                signal_date=order.datetime.isoformat(), reason=self.order_reasons.get(order.vt_orderid, ''),
                cash_after=self.cash))
            if self.cash < -1e-6:
                raise AssertionError('Stock account cash became negative')

    def run_backtesting(self):
        if self._has_run:
            raise ValueError('Create a fresh stock engine for each backtest')
        self._has_run = True
        self.strategy.on_init()
        previous_equity = self.capital
        started = False
        for session, (timestamp, day) in enumerate(self.panel.groupby('date', sort=True)):
            self.datetime = timestamp.to_pydatetime()
            if self.datetime > self.end:
                break
            self.current_rows = {r['vt_symbol']: r for r in day.to_dict('records')}
            active = self.datetime >= self.start
            if active and not started:
                self.strategy.inited = self.strategy.trading = True
                self.strategy.on_start()
                started = True
            self.opening_used = 0.
            self.opening_limit = previous_equity * self.settings.day_position_size
            before = len(self.executions)
            if active:
                self._corporate_actions()
                self.cross_limit_order()
            bars = {}
            for symbol, row in self.current_rows.items():
                code, exchange = symbol.split('.')
                bars[symbol] = BarData(symbol=code, exchange=Exchange(exchange),
                    datetime=self.datetime, interval=Interval.DAILY, volume=float(row['volume']),
                    open_price=float(row['open']), high_price=float(row['high']),
                    low_price=float(row['low']), close_price=float(row['close']), gateway_name='LOCAL_STOCK')
                self.last_prices[symbol] = float(row['close'])
                if row['volume'] > 0:
                    self.last_quote_dates[symbol] = timestamp.date()
                    self.last_quote_sessions[symbol] = session
            self.bars = bars  # Only observed bars, never synthetic tradable bars.
            self.strategy.on_bars(bars)
            if active:
                stale_market_value = 0.
                for symbol, holding in self.holdings.items():
                    row = self.current_rows.get(symbol)
                    stale = session - self.last_quote_sessions[symbol]
                    market_value = holding.shares * self.last_prices[symbol]
                    self.position_coverage.append(dict(date=str(timestamp.date()), vt_symbol=symbol,
                        shares=holding.shares, mark_price=self.last_prices[symbol], market_value=market_value,
                        has_bar=row is not None, is_suspended=row is not None and row['volume'] <= 0,
                        last_quote_date=str(self.last_quote_dates[symbol]), stale_sessions=stale,
                        stale_calendar_days=(timestamp.date() - self.last_quote_dates[symbol]).days))
                    if stale:
                        stale_market_value += market_value
                equity = self.equity()
                executions = self.executions[before:]
                self.equity_rows.append(dict(date=timestamp.date(), cash=self.cash,
                    market_value=equity - self.cash, equity=equity, balance=equity,
                    net_pnl=equity - previous_equity, position_count=len(self.holdings),
                    stale_market_value=stale_market_value,
                    trade_count=len(executions),
                    commission=sum(t['commission'] for t in executions),
                    slippage=sum(t['slippage'] for t in executions),
                    turnover=sum(t['turnover'] for t in executions)))
                previous_equity = equity
        self.strategy.on_stop()
        self.strategy.trading = False
        if not self.equity_rows:
            raise ValueError('No sessions within the requested backtest interval')
        # Never fill final-day intents beyond the dataset end.
        for order in list(self.active_limit_orders.values()):
            self._blocked(order, 'end_of_data_unfilled', True)

    def calculate_result(self):
        result = pd.DataFrame(self.equity_rows).set_index('date')
        previous = result.equity.shift(1, fill_value=self.capital)
        result['return'] = result.equity / previous - 1
        peak = result.equity.cummax().clip(lower=self.capital)
        result['drawdown_pct'] = (result.equity / peak - 1) * 100
        self.daily_df = result
        return result

    def calculate_statistics(self, df=None, output=False):
        df = self.calculate_result() if df is None else df
        returns = df['return']
        std = returns.std(ddof=0)
        wins = sum(t['net_pnl'] > 0 for t in self.round_trips)
        return dict(end_equity=float(df.equity.iloc[-1]),
            total_return_pct=float((df.equity.iloc[-1] / self.capital - 1) * 100),
            max_drawdown_pct=float(df.drawdown_pct.min()),
            sharpe=float(returns.mean() / std * np.sqrt(self.settings.annual_days)) if std > 0 else 0.,
            total_slippage=float(df.slippage.sum()), total_commission=float(df.commission.sum()),
            total_trade_count=len(self.trades), closed_round_trips=len(self.round_trips),
            win_rate_pct=100 * wins / len(self.round_trips) if self.round_trips else None,
            open_positions=len(self.holdings), trading_days=len(df),
            stale_holding_days=sum(x['stale_sessions'] > 0 for x in self.position_coverage),
            max_stale_calendar_days=max((x['stale_calendar_days'] for x in self.position_coverage), default=0),
            end_stale_market_value=float(df.stale_market_value.iloc[-1]))
