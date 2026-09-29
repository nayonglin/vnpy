"""QMT 357 alpha adapted to vn.py's portfolio StrategyTemplate."""
from collections import defaultdict, deque

import pandas as pd
from vnpy_portfoliostrategy.template import StrategyTemplate

from .config import INDEX_SYMBOL
from .signals import SignalSettings, evaluate_signal, market_allows_entry


class Qmt357StockStrategy(StrategyTemplate):
    author = 'QMT 357 migration'

    def __init__(self, strategy_engine, strategy_name, vt_symbols, setting):
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.signal_settings = SignalSettings()
        self.history = defaultdict(lambda: deque(maxlen=self.signal_settings.lookback))
        self.signal_log = []
        self.gate_log = []

    def on_init(self):
        # Engine streams the explicit warmup interval before start; no database access.
        pass

    def on_bars(self, bars):
        engine = self.strategy_engine
        cfg = engine.settings
        for symbol, row in engine.current_rows.items():
            self.history[symbol].append(row.copy())
        if not self.trading:
            return

        pending = {o.vt_symbol for o in engine.active_limit_orders.values()}
        # Risk exits remain active even on a falling-index day.
        for symbol, holding in list(engine.holdings.items()):
            if symbol not in bars or symbol in pending:
                continue
            row = engine.current_rows[symbol]
            close = row['close']
            # Source 357.py snapshots thresholds before special limit protection;
            # protection changes persist for the next check, not this exit test.
            stop_loss, stop_profit = holding.stop_loss, holding.stop_profit
            profit = (close - holding.buy_price) / holding.buy_price
            reason = ''
            if close >= row['limit_up'] * .995 and profit >= cfg.stop_profit_pct * .8:
                holding.stop_loss = max(holding.buy_price * 1.01, close * .97)
            if close <= row['limit_down'] * 1.005:
                if profit > 0:
                    holding.stop_loss = holding.buy_price
                elif profit < -.05:
                    reason = 'limit_down_risk'
            if close <= stop_loss:
                reason = 'stop_loss'
            elif close >= stop_profit:
                reason = 'take_profit'
            if reason:
                for oid in self.sell(symbol, close, holding.shares):
                    engine.order_reasons[oid] = reason

        allowed = INDEX_SYMBOL in bars and market_allows_entry(
            [row['close'] for row in self.history[INDEX_SYMBOL]])
        self.gate_log.append(dict(date=engine.datetime.isoformat(), allowed=allowed))
        if not allowed:
            return
        available_slots = cfg.max_positions - len(engine.holdings)
        if available_slots <= 0:
            return
        candidates = []
        for symbol in sorted(bars):
            row = engine.current_rows[symbol]
            if (symbol == INDEX_SYMBOL or symbol in engine.holdings or symbol in pending
                    or symbol.startswith(('300', '688')) or row['is_st']
                    or not row['is_member'] or row['volume'] <= 0):
                continue
            frame = pd.DataFrame(self.history[symbol])
            # Reconstruct each past bar on the signal date's adjustment basis.
            scale = frame.adj_factor / float(frame.adj_factor.iloc[-1])
            for field in ['open', 'high', 'low', 'close']:
                frame[field] = frame[field] * scale
            result = evaluate_signal(frame, self.signal_settings)
            if result is not None and result['eligible']:
                candidates.append((symbol, result))
        candidates.sort(key=lambda item: (-item[1]['score'], item[0]))
        equity = engine.equity()
        daily_remaining = equity * cfg.day_position_size
        cash_remaining = engine.cash * (1 - cfg.cash_buffer)
        for symbol, result in candidates[:available_slots]:
            raw_close = engine.current_rows[symbol]['close']
            budget = min(equity * cfg.position_size, daily_remaining, cash_remaining)
            shares = int(max(0., budget) / raw_close / 100) * 100
            if shares == 0:
                continue
            ids = self.buy(symbol, raw_close, shares)
            for oid in ids:
                engine.order_budgets[oid] = budget
                engine.order_reasons[oid] = 'qmt357_reversal'
            if ids:
                self.signal_log.append(dict(date=engine.datetime.isoformat(), vt_symbol=symbol,
                    **result, raw_close=float(raw_close), budget=float(budget)))
                # Reserve once; actual ledger changes only after an executed fill.
                daily_remaining -= budget
                cash_remaining -= budget
