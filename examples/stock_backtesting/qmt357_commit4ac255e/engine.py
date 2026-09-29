"""Stock cash engine for the 4ac255e oscillation variant."""
from __future__ import annotations

from datetime import date

from examples.stock_backtesting.qmt357.engine import StockBacktestingEngine


class Commit4ac255eEngine(StockBacktestingEngine):
    def __init__(self, settings, unsupported_actions=()):
        super().__init__(settings)
        self.highest_closes: dict[str, float] = {}
        self.unsupported_actions = {}
        for event in unsupported_actions:
            key = (date.fromisoformat(event['date']), event['vt_symbol'])
            if key in self.unsupported_actions or not event.get('reason'):
                raise ValueError('Invalid unsupported corporate-action metadata')
            self.unsupported_actions[key] = event['reason']

    def _corporate_actions(self):
        # A provider's total share-capital multiplier can be present yet not
        # describe an ordinary holder's entitlement (e.g. restructuring).
        # Reject before ANY cash/share mutation; never turn it into free shares.
        for (day, symbol), reason in self.unsupported_actions.items():
            if day == self.datetime.date() and symbol in self.holdings:
                raise ValueError(f'Unsupported corporate action for {symbol} on {day}: {reason}')
        adjustments = {}
        for symbol, holding in self.holdings.items():
            row = self.current_rows.get(symbol)
            if row is None:
                continue
            dividend = float(row.get('cash_dividend', 0.))
            split = float(row.get('split_ratio', 1.))
            if dividend or split != 1.:
                adjustments[symbol] = (self.highest_closes.get(symbol, holding.buy_price),
                                       dividend, split)
        super()._corporate_actions()
        for symbol, (peak, dividend, split) in adjustments.items():
            self.highest_closes[symbol] = (peak - dividend) / split

    def cross_limit_order(self):
        super().cross_limit_order()
        for symbol in list(self.highest_closes):
            if symbol not in self.holdings:
                del self.highest_closes[symbol]
        for symbol, holding in self.holdings.items():
            self.highest_closes.setdefault(symbol, holding.buy_price)
