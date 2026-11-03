"""Bounded next-trading-day-open execution for the research reversal."""
from copy import copy
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from vnpy.trader.constant import Direction, Offset

from weekly19_frozen.base830 import QmtRollPortfolioStrategyStage830C2Broker10MarginCap
from weekly19_frozen.qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
from weekly_stop_reversal import (
    CloseFill, EntryAnchor, ReversePosition, StopSignal, WeeklyBar,
    WEEKLY_STOP_REASONS, advance_protection, plan_reversal,
)

TAG = "weekly19_stop_reversal"
SHANGHAI = ZoneInfo("Asia/Shanghai")


def event_time(trading_day):
    # Synthetic event clock. Separate trading days prove order; no wall-clock
    # hour or matching-engine queue is inferred from a daily bar.
    return datetime.combine(trading_day, time(), SHANGHAI)


def open_equity(balance, starting_positions, prior_marks, marks, fills, sizes):
    equity = balance + sum(
        volume * (marks[symbol] - prior_marks[symbol]) * sizes[symbol]
        for symbol, volume in starting_positions.items() if volume
    )
    for fill in fills:
        side = 1 if fill["side"] == "long" else -1
        equity += side * fill["volume"] * (marks[fill["symbol"]] - fill["price"]) * sizes[fill["symbol"]]
        equity -= fill["commission"] + fill["slippage"]
    return equity


def _week(row):
    return WeeklyBar(date.fromisoformat(str(row["week_end"])), row["high"], row["low"], row["close"])


def _owned(state):
    return bool(state and state.layers and state.layers[0].signal == TAG)


def _nominal_ratio(strategy, risk_mode):
    fields = {
        "regular": "risk_ratio_of_total_assets",
        "ma_cross_breakout": "risk_ratio_ma_cross_breakout",
        "volume_open_interest_surge": "risk_ratio_volume_open_interest_surge",
        "open_interest_surge": "risk_ratio_open_interest_surge",
        "open_interest_decline": "risk_ratio_open_interest_decline",
        "breakout": "risk_ratio_breakout",
    }
    return getattr(strategy, fields[risk_mode])


def reversal_strategy(base):
    class ReversalStrategy(base):
        _reverse_sizing = None

        def _close_all_layers_and_set_flat_target(
            self, state, exit_price, execution_price_override=None, exit_reason=None,
            profit_giveback_context=False,
        ):
            engine = self.strategy_engine
            symbol = state.contract_vt_symbol
            if (
                not _owned(state) and state.direction in {"long", "short"}
                and self.get_pos(symbol)
                and exit_reason in {f"{state.direction}_{reason}" for reason in WEEKLY_STOP_REASONS}
            ):
                signal_day = str(self.current_bar_date.date())
                scheduled = engine.next_day.get(signal_day)
                if scheduled:
                    bar = engine.bars[symbol]
                    weekly, _, _ = self._completed_week_context(bar, TAG, fresh_only=True)
                    epoch = engine.epoch_lookup[(symbol, signal_day)]
                    position_id = f"{symbol}:{state.entry_date}:{signal_day}"
                    engine.stop_signals[(symbol, signal_day)] = (
                        state.product_vt_symbol, state.risk_mode,
                        StopSignal(
                            position_id, symbol, epoch, state.direction, exit_reason,
                            WeeklyBar(date.fromisoformat(signal_day), weekly.high_price, weekly.low_price, weekly.close_price),
                            date.fromisoformat(scheduled), _nominal_ratio(self, state.risk_mode),
                        ),
                    )
            return super()._close_all_layers_and_set_flat_target(
                state, exit_price, execution_price_override, exit_reason, profit_giveback_context,
            )

        def _update_dynamic_stops(self, state, bar, history):
            if not _owned(state):
                return super()._update_dynamic_stops(state, bar, history)

        def _process_layer_stops(self, state, bar):
            return "" if _owned(state) else super()._process_layer_stops(state, bar)

        def _stop_triggered(self, direction, bar, stop_price):
            if _owned(self._find_state_by_contract(bar.vt_symbol)):
                return False  # The inherited inline MA path must not close this sleeve.
            return super()._stop_triggered(direction, bar, stop_price)

        def _process_prev2day_stop(self, state, bar, history):
            if not _owned(state):
                return super()._process_prev2day_stop(state, bar, history)
            context = self._completed_week_context(bar, TAG, fresh_only=True)
            if context is None:
                return ""
            weekly, am, _ = context
            layer = state.layers[0]
            position = ReversePosition(state.direction, layer.stop_price, date.fromisoformat(state.entry_date))
            epoch = am.completed[-min(int(am.inner.count), len(am.completed)):]
            stop, triggered = advance_protection(position, tuple(_week(row) for row in epoch[-3:]))
            layer.stop_price = float(stop)
            if not triggered:
                return ""
            reason = f"{state.direction}_{TAG}_stop"
            self._close_all_layers_and_set_flat_target(
                state, weekly.close_price, execution_price_override=weekly.close_price, exit_reason=reason,
            )
            return reason

        def _handle_rollover(self, state, target_contract, bars):
            if not _owned(state):
                return super()._handle_rollover(state, target_contract, bars)
            # Preserve the formal close on roll. No raw price stop is carried
            # between contracts with different price bases.
            reopen = self.rollover_reopen_enabled
            self.rollover_reopen_enabled = False
            try:
                return super()._handle_rollover(state, target_contract, bars)
            finally:
                self.rollover_reopen_enabled = reopen

        def _entry_stop_price(self, direction, bar, history, use_day_extreme):
            if self._reverse_sizing is not None:
                return self._reverse_sizing
            return super()._entry_stop_price(direction, bar, history, use_day_extreme)

        def _risk_amount_from_ratio(self, risk_ratio, limited_balance, risk_multiplier_override=None):
            if self._reverse_sizing is not None:
                multiplier = self._current_streak_multiplier() if risk_multiplier_override is None else risk_multiplier_override
                return max(0.0, min(self.max_risk_per_trade, self.estimated_equity * risk_ratio) * multiplier)
            return super()._risk_amount_from_ratio(risk_ratio, limited_balance, risk_multiplier_override)

        def reverse_sizing(self, signal, mode, direction, anchor_bar, marks, equity):
            symbol = signal.symbol
            stop = signal.signal_week.low if direction == "long" else signal.signal_week.high
            am = self.ams[symbol]
            history = self._build_history_df(am)
            self.estimated_equity = equity
            self.total_margin_in_use = self._estimate_margin_usage(marks)
            self.cluster_margin_usage = self._estimate_margin_usage_by_cluster(marks)
            self.cluster_unrealized_pnl = self._estimate_unrealized_pnl_by_cluster(marks)
            self._refresh_risk_cluster_heat_pressure_snapshot()
            self._reset_intrabar_reservations()
            if self._count_active_positions() >= self._effective_max_concurrent_positions("flat_entry"):
                return None
            self._reverse_sizing = float(stop)
            try:
                sizing = QmtRollPortfolioStrategyStage830C2Broker10MarginCap._calculate_entry_sizing(
                    self, symbol, direction, anchor_bar, history, {"signal": TAG, "risk_mode": mode},
                    active_positions_before=self._count_active_positions(),
                )
            finally:
                self._reverse_sizing = None
            if float(sizing["risk_ratio"]) != float(signal.opening_risk_ratio):
                raise ValueError("original nominal risk ratio drift")
            return sizing, history

        def stage_reverse_position(self, state, plan, mode, bar, sizing, history):
            QmtRollPortfolioStrategy._open_position(
                self, state, plan.symbol, plan.direction, plan.volume, bar,
                TAG, history, {"signal": TAG, "risk_mode": mode}, sizing_snapshot=sizing,
            )
            self._apply_state_target(state)

    return ReversalStrategy


def reversal_engine(base):
    class ReversalEngine(base):
        def __init__(self, *args):
            super().__init__(*args)
            self.stop_signals = {}
            self.pending_reverse = {}
            self.reversal_decisions = []

        def fill_at_open(self, order, bar):
            symbol = order.vt_symbol
            state = self.strategy._find_state_by_contract(symbol)
            reverse_owned = _owned(state) or self.open_sleeve.get(symbol) == TAG
            trade = super().fill_at_open(order, bar)
            if order.offset == Offset.OPEN:
                self.open_sleeve[symbol] = TAG if reverse_owned else "native"
            self.fills[-1]["sleeve"] = self.open_sleeve.get(symbol, "native")
            if order.offset == Offset.CLOSE and not self.strategy.get_pos(symbol):
                self.open_sleeve.pop(symbol, None)
                item = self.stop_signals.pop((symbol, str(order.datetime.date())), None)
                if item:
                    product, mode, signal = item
                    if self.fills[-1]["reason"] != signal.reason:
                        raise ValueError("stop signal/fill reason mismatch")
                    day = self.datetime.date()
                    self.pending_reverse[signal.position_id] = (
                        product, mode, signal, CloseFill(signal.position_id, event_time(day), day, 0),
                        self.fills[-1]["trade_id"],
                    )
            return trade

        def cross_limit_order(self):
            strategy = self.strategy
            balance = strategy.settled_balance
            positions = dict(strategy.equity_start_positions)
            prior = strategy.last_close_prices
            first_fill = len(self.fills)
            super().cross_limit_order()
            day = self.datetime.date()
            eligible = [
                (key, item) for key, item in self.pending_reverse.items() if item[3].trading_day < day
            ]
            if not eligible:
                return

            marks = {}
            for symbol, bar in self.bars.items():
                marked = copy(bar)
                current = self.history_data.get((self.datetime, symbol))
                marked.close_price = (
                    float(current.open_price) if current and current.volume > 0
                    else float(prior[symbol]) if symbol in prior else float(bar.close_price)
                )
                marks[symbol] = marked
            prices = {symbol: mark.close_price for symbol, mark in marks.items()}

            for key, (product, mode, signal, close, close_trade_id) in eligible:
                del self.pending_reverse[key]
                symbol = signal.symbol
                real = self.history_data.get((self.datetime, symbol))
                row = dict(position_id=key, symbol=symbol, product=product, signal_reason=signal.reason,
                           signal_day=str(signal.signal_week.day), close_trade_id=close_trade_id,
                           close_day=str(close.trading_day), decision_day=str(day))
                self.reversal_decisions.append(row)
                state = strategy.states[product]
                if day.isocalendar()[:2] != signal.scheduled_close_day.isocalendar()[:2]:
                    row["status"] = "execution_week_expired"
                    continue
                last_known_day = str(strategy.current_bar_date.date())
                known_main = strategy.daily_mapping.get(last_known_day, {}).get(product)
                if known_main != symbol or state.layers or self.strategy.get_pos(symbol):
                    row["status"] = "competing_position_or_rollover"
                    continue
                if (real is None or real.volume <= 0 or real.open_price <= 0 or real.high_price == real.low_price
                    or self.epoch_lookup.get((symbol, str(day))) != signal.epoch):
                    row["status"] = "no_admitted_open_proxy"
                    continue
                equity = open_equity(balance, positions, prior, prices, self.fills[first_fill:], self.sizes)
                direction = "long" if signal.direction == "short" else "short"
                bar = copy(real)
                bar.high_price = bar.low_price = bar.close_price = float(real.open_price)
                price = bar.close_price
                stop = signal.signal_week.low if direction == "long" else signal.signal_week.high
                row.update(price=price, equity=equity, direction=direction, initial_stop=str(stop))
                if equity <= 0 or (price <= stop if direction == "long" else price >= stop):
                    row["status"] = "invalid_risk_distance_or_equity"
                    continue
                decision = strategy.reverse_sizing(signal, mode, direction, bar, marks, equity)
                if decision is None:
                    row["status"] = "position_cap"
                    continue
                sizing, history = decision
                multiplier = sizing["risk_amount"] / equity / float(signal.opening_risk_ratio)
                plan = plan_reversal(signal, close, EntryAnchor(
                    symbol, signal.epoch, event_time(day), day, price, equity, multiplier,
                    self.sizes[symbol], int(sizing["selected_volume"]), self.priceticks[symbol],
                ))
                if plan is None:
                    row["status"] = "zero_risk_or_capacity"
                    continue
                strategy.stage_reverse_position(state, plan, mode, bar, sizing, history)
                ids = self.send_order(
                    strategy, symbol, Direction.LONG if direction == "long" else Direction.SHORT,
                    Offset.OPEN, price, plan.volume, False, False,
                )
                [order_id] = ids
                trade = self.fill_at_open(self.active_limit_orders[order_id], real)
                row.update(status="filled", open_trade_id=trade.vt_tradeid, volume=plan.volume,
                           nominal_risk=float(signal.opening_risk_ratio), risk_amount=sizing["risk_amount"],
                           selected_volume=sizing["selected_volume"])

    return ReversalEngine
