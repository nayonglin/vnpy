"""Isolated one-day conditional entry adapter over native Stage827 execution.

The factory is intentionally lazy: importing this module does not initialize
the historical numerical/runtime stack. Quantity and admission are frozen by
the signal-close planner; this adapter only determines the executable time and
price, then delegates accounting and the stop/retry episode to native code.
"""
from __future__ import annotations

from datetime import date, datetime
import heapq
import math
from types import SimpleNamespace
from typing import Any


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, "item"):
        return _json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def build_ordered_engine(base_engine, qualify_intent):
    """Return a scoped engine; ``qualify_intent(engine, item, Dbar)`` must return None.

    Qualification is mandatory even for a day on which the stop-entry never
    triggers. The runner owns signed full-session qualification and bounded
    same-engine waiting; a returned flag/receipt cannot bypass that contract.
    """
    if not callable(qualify_intent):
        raise TypeError("stage028_qualification_callable_required")

    import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847

    s827 = s847.s827
    execution = s827.execution

    def day_text(value):
        return execution.local_timestamp(value).date().isoformat()

    class Stage028OrderedEngine(base_engine):
        def _ts_audit(self, item, status, **updates):
            if not hasattr(self, "ts_execution_audit"):
                self.ts_execution_audit = []
            row = {key: item.get(key) for key in (
                "arm", "intent_id", "product", "contract", "epoch_id", "setup_id", "setup_day",
                "signal_day", "execution_day", "direction", "trigger", "weekly_asof", "native_signal", "rank")}
            plan = item.get("plan", {})
            sizing = plan.get("sizing", {})
            volume = plan.get("volume")
            row.update(status=status, quantity=volume,
                       fill_price=None, execution_datetime="", intrabar=False,
                       forecast_risk_amount=float(sizing["risk_per_contract"]) * volume,
                       forecast_margin_amount=float(sizing["margin_per_contract"]) * volume,
                       actual_risk_amount=None, actual_margin_amount=None,
                       untriggered=status == "expired_untriggered", **updates)
            row = _json_safe(row)
            self.ts_execution_audit.append(row)
            return row

        def _ts_conditional_context(self, item, actual_bar):
            plan = item["plan"]
            symbol = str(item["contract"])
            volume = plan["volume"]
            if isinstance(volume, bool) or not isinstance(volume, int) or volume <= 0:
                raise ValueError("stage028_invalid_frozen_quantity")
            direction = item["direction"]
            if direction not in (1, -1) or isinstance(direction, bool):
                raise ValueError("stage028_invalid_direction")
            if str(plan["target_contract"]) != symbol or plan["direction"] != ("long" if direction == 1 else "short"):
                raise ValueError("stage028_frozen_plan_identity_mismatch")
            if day_text(plan["target_bar"].datetime) != day_text(item["signal_day"]):
                raise ValueError("stage028_frozen_signal_bar_mismatch")
            threshold = float(item["trigger"])
            if not math.isfinite(threshold) or threshold <= 0:
                raise ValueError("stage028_invalid_trigger")

            # Do not inspect the minute cache before the runner has qualified
            # the entire D session. This also applies to never-triggered days.
            if qualify_intent(self, item, actual_bar) is not None:
                raise ValueError("stage028_qualification_must_return_none")
            trading_day = execution.local_timestamp(self.datetime).normalize()
            grid = execution.session_minutes(symbol, trading_day, self.strategy.available_trade_dates)
            session = execution.entry_session(self.strategy, SimpleNamespace(
                vt_symbol=symbol, trading_date=trading_day.date(),
                datetime=self.datetime, execution_datetime=grid[0]))
            # Never permit an execution-only diagnostic setting to make this
            # conditional path accept incomplete minutes.
            if len(session) != len(grid) or set(session["bar_datetime"]) != set(grid):
                raise ValueError("stage028_incomplete_conditional_session")

            tick = execution.effective_pricetick(symbol, trading_day, self.priceticks[symbol])
            for _, minute in session.iterrows():
                crossed = float(minute["high"]) >= threshold if direction == 1 else float(minute["low"]) <= threshold
                if not crossed:
                    continue
                price, note = execution.stop_fill(minute, threshold, tick, buy=direction == 1)
                opening_crossed = float(minute["open"]) >= threshold if direction == 1 else float(minute["open"]) <= threshold
                timestamp = execution.local_timestamp(minute["bar_datetime"])
                context = dict(price=price, fill_price=price,
                    source="stage028_conditional_initial_stop_entry",
                    proxy=dict(proxy_price=price, proxy_bar_count=1,
                               proxy_first_time=timestamp.isoformat(), proxy_last_time=timestamp.isoformat()),
                    execution_datetime=timestamp, trading_date=trading_day.date(),
                    execution_time_source="conditional_trigger_minute", anchor_coverage_status="complete",
                    expected_session_start=grid[0].isoformat(), corrected_legacy_proxy=False,
                    legacy_proxy_time="", legacy_proxy_price=0.0, fill_note=note,
                    intent_id=str(item["intent_id"]), setup_id=str(item["setup_id"]),
                    signal_day=day_text(item["signal_day"]), execution_day=trading_day.date().isoformat(),
                    trigger=threshold, quantity=volume, intrabar=not opening_crossed)
                # These are observations, never a second sizing or risk gate.
                sizing = plan["sizing"]
                size = float(self.sizes[symbol])
                stop = float(sizing["stop_price"])
                forecast_risk = float(sizing["risk_per_contract"]) * volume
                forecast_margin = float(sizing["margin_per_contract"]) * volume
                risk_per_contract = max(abs(price - stop) * size, max(float(self.priceticks[symbol]) * size, 1.0))
                actual_risk = risk_per_contract * volume
                actual_margin = price * size * float(sizing["margin_ratio"]) * volume
                context.update(stop_price=stop, actual_risk_price=abs(price - stop),
                    actual_risk_per_contract=risk_per_contract, actual_risk_amount=actual_risk,
                    forecast_risk_amount=forecast_risk, actual_margin_amount=actual_margin,
                    forecast_margin_amount=forecast_margin,
                    actual_minus_forecast_risk_amount=actual_risk - forecast_risk,
                    actual_minus_forecast_margin_amount=actual_margin - forecast_margin,
                    actual_to_forecast_risk_ratio=actual_risk / forecast_risk if forecast_risk > 0 else None,
                    actual_to_forecast_margin_ratio=actual_margin / forecast_margin if forecast_margin > 0 else None)
                return context
            return None

        def _ts_fill_conditional(self, item, actual_bar, context, audit):
            # Activation happens only as this market event leaves the common
            # queue. No signal-close phantom layer or target exists before it.
            self.strategy.ts_activate_intent(item, float(context["price"]))
            send = self.strategy.buy if item["direction"] == 1 else self.strategy.short
            order_ids = send(str(item["contract"]), float(context["price"]), item["plan"]["volume"])
            if len(order_ids) != 1:
                raise ValueError("stage028_expected_one_native_open_order")
            order_id = order_ids[0]
            order = self.active_limit_orders.get(order_id)
            if order is None or order.offset != s827.Offset.OPEN:
                raise ValueError("stage028_native_open_order_missing")
            order.datetime = item["plan"]["target_bar"].datetime
            self._stage827_order_contexts[order_id] = context
            self.strategy.ts_conditional_orders[order_id] = dict(
                intrabar=bool(context["intrabar"]), execution_datetime=context["execution_datetime"],
                fill_price=float(context["price"]))
            prior_count = self.trade_count
            self._fill_order(order, actual_bar)
            if self.trade_count != prior_count + 1 or order_id in self.active_limit_orders:
                raise ValueError("stage028_conditional_native_fill_not_completed")
            self.strategy.ts_commit_fill(item, context["execution_day"], order_id, context)
            audit.update(_json_safe({key: value for key, value in context.items() if key != "proxy"}))
            audit.update(status="filled", order_id=str(order_id))

        def cross_delayed_orders(self):
            pending = list(getattr(self.strategy, "ts_pending_intents", []))
            if not pending:
                return super().cross_delayed_orders()
            self._stage827_execution_queue = []
            self._stage827_queue_serial = 0
            self._stage827_order_contexts = {}
            consumed = set()
            try:
                current_day = day_text(self.datetime)
                current = []
                for item in pending:
                    execution_day = day_text(item["execution_day"])
                    if execution_day < current_day:
                        self._ts_audit(item, "expired_past_day")
                        consumed.add(id(item))
                    elif execution_day == current_day:
                        current.append(item)

                # Preserve ordinary/roll ordering and canonical anchor context.
                for order in list(self.active_limit_orders.values()):
                    actual_bar = self.bars.get(order.vt_symbol)
                    if actual_bar is None:
                        continue
                    context = self._stage827_order_context(order, actual_bar)
                    self._stage827_order_contexts[order.vt_orderid] = context
                    heapq.heappush(self._stage827_execution_queue, (
                        context["execution_datetime"], self._stage827_queue_serial, "ordinary", order, actual_bar))
                    self._stage827_queue_serial += 1

                for item in sorted(current, key=lambda row: (row["rank"], row["product"], row["intent_id"])):
                    if isinstance(item["rank"], bool) or not isinstance(item["rank"], int):
                        raise ValueError("stage028_invalid_frozen_rank")
                    actual_bar = self.bars.get(str(item["contract"]))
                    if actual_bar is None:
                        raise ValueError("stage028_execution_daily_bar_missing")
                    context = self._ts_conditional_context(item, actual_bar)
                    consumed.add(id(item))
                    if context is None:
                        self._ts_audit(item, "expired_untriggered")
                        continue
                    audit = self._ts_audit(item, "triggered_queued")
                    heapq.heappush(self._stage827_execution_queue, (
                        context["execution_datetime"], self._stage827_queue_serial,
                        "conditional", item, (actual_bar, context, audit)))
                    self._stage827_queue_serial += 1

                while self._stage827_execution_queue:
                    _, _, kind, item, payload = heapq.heappop(self._stage827_execution_queue)
                    if kind == "ordinary":
                        if item.vt_orderid in self.active_limit_orders:
                            self._fill_order(item, payload)
                    elif kind == "conditional":
                        actual_bar, context, audit = payload
                        self._ts_fill_conditional(item, actual_bar, context, audit)
                    else:
                        open_trade, event = payload
                        self._fill_synthetic_intraday_close(item, open_trade, event)
                # The machine consumes setup only on fill; removing a spent
                # one-day execution instruction does not consume preparation.
                self.strategy.ts_pending_intents[:] = [
                    item for item in self.strategy.ts_pending_intents if id(item) not in consumed]
            except Exception as exc:
                self.intraday_execution_failure = f"{type(exc).__name__}: {exc!r}"
                raise
            finally:
                self._stage827_execution_queue = None
                self._stage827_order_contexts = {}

    Stage028OrderedEngine.__name__ = "Stage028Ordered" + base_engine.__name__
    return Stage028OrderedEngine
