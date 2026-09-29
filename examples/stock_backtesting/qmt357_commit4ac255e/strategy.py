"""Committed oscillation stop tiers on the independent 357 stock entry path."""
from __future__ import annotations

from examples.stock_backtesting.qmt357.strategy import Qmt357StockStrategy


class Commit4ac255eStrategy(Qmt357StockStrategy):
    def __init__(self, strategy_engine, strategy_name, vt_symbols, setting):
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.trail_log: list[dict] = []

    def on_bars(self, bars):
        if not self.trading:
            super().on_bars(bars)
            return
        engine = self.strategy_engine
        pending = {o.vt_symbol for o in engine.active_limit_orders.values()}
        for symbol, holding in list(engine.holdings.items()):
            if symbol not in bars or symbol in pending:
                continue
            row = engine.current_rows[symbol]
            close = float(row['close'])
            buy = holding.buy_price
            peak = max(engine.highest_closes.get(symbol, buy), close)
            engine.highest_closes[symbol] = peak
            old_stop = holding.stop_loss
            if close > buy:
                max_profit = (peak - buy) / buy
                if max_profit >= .40:
                    proposed = buy * 1.15
                elif max_profit >= .30:
                    proposed = buy * 1.10
                elif max_profit >= .20:
                    proposed = buy * 1.06
                elif max_profit >= .10:
                    proposed = buy * 1.03
                else:
                    proposed = buy
                if proposed > holding.stop_loss:
                    holding.stop_loss = proposed
            self.trail_log.append(dict(date=engine.datetime.isoformat(), vt_symbol=symbol,
                buy_price=buy, observed_close=close, peak=peak,
                old_stop=old_stop, new_stop=holding.stop_loss))
        super().on_bars(bars)
