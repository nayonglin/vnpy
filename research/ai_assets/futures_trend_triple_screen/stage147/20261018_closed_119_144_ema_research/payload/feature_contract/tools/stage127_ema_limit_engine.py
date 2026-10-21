"""Stage124 limit approximation and scoped native execution adapter.

The scanner assumes its caller qualified the complete D session and confirmed
single-sided volume units. Total minute volume is only a necessary condition
for the all-or-none research approximation; it proves no queue allocation.
Imports remain lazy and this module contains no account runner or PnL model.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR
import heapq
import math
from types import SimpleNamespace
from typing import Any, Mapping
from zoneinfo import ZoneInfo

MECHANISM_ID = "stage124_ema_limit_v1"
_POLICIES = {"primary", "pessimistic"}


def _moment(value):
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    stamp = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if stamp.tzinfo is not None:
        stamp = stamp.astimezone(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None)
    return stamp


def _day(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return _moment(value).date()


def _number(value, *, name, positive=False):
    if isinstance(value, bool) or type(value).__name__ == "bool_":
        raise ValueError("ema_limit_invalid_" + name)
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("ema_limit_invalid_" + name) from exc
    if not math.isfinite(result) or (result <= 0 if positive else result < 0):
        raise ValueError("ema_limit_invalid_" + name)
    return result


def _rounded(value, tick, rounding):
    return float((Decimal(str(value)) / Decimal(str(tick))).to_integral_value(rounding=rounding)
                 * Decimal(str(tick)))


def _legal_tick(value, tick):
    units = Decimal(str(value)) / Decimal(str(tick))
    return units == units.to_integral_value()


def _safe(value):
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        return _safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def limit_context(item: Mapping, frame, *, tick: float, policy: str = "primary") -> dict | None:
    """Scan a qualified D frame without sizing, state changes or raw mutation.

    D can include u's natural-date night session. Optional ``trading_date``
    labels are respected; a physical minute after D can never confirm a fill.
    """
    if policy not in _POLICIES:
        raise ValueError("ema_limit_unknown_policy")
    if item.get("mechanism_id") != MECHANISM_ID or item.get("order_type") != "limit":
        raise ValueError("ema_limit_identity_or_order_type")
    direction = item["direction"]
    if isinstance(direction, bool) or direction not in (1, -1):
        raise ValueError("ema_limit_invalid_direction")
    quantity = item["plan"]["volume"]
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        raise ValueError("ema_limit_invalid_frozen_quantity")
    limit = _number(item["limit_price"], name="limit_price", positive=True)
    tick = _number(tick, name="execution_tick", positive=True)
    if Decimal(str(item["execution_tick"])) != Decimal(str(tick)) or not _legal_tick(limit, tick):
        raise ValueError("ema_limit_frozen_execution_tick_mismatch")
    if Decimal(str(item["trigger"])) != Decimal(str(limit)):
        raise ValueError("ema_limit_qualification_trigger_mismatch")
    signal_day, execution_day = _day(item["signal_day"]), _day(item["execution_day"])
    if execution_day <= signal_day:
        raise ValueError("ema_limit_invalid_day_order")
    required = {"bar_datetime", "open", "high", "low", "close", "volume"}
    if not required.issubset(frame.columns):
        raise ValueError("ema_limit_minute_columns_missing")

    # Validate every eligible D minute before choosing any fill, including
    # invalid volume after an otherwise early eligible minute.
    rows = []
    prior = None
    for _, raw in frame.iterrows():
        stamp = _moment(raw["bar_datetime"])
        if stamp.date() > execution_day or ("trading_date" in frame.columns
                                            and _day(raw["trading_date"]) != execution_day):
            continue
        if stamp.date() < signal_day or (prior is not None and stamp <= prior):
            raise ValueError("ema_limit_invalid_minute_clock")
        prior = stamp
        values = {name: _number(raw[name], name=name, positive=True)
                  for name in ("open", "high", "low", "close")}
        values["volume"] = _number(raw["volume"], name="volume")
        if (values["low"] > min(values["open"], values["close"])
                or values["high"] < max(values["open"], values["close"])):
            raise ValueError("ema_limit_invalid_ohlc")
        rows.append(dict(bar_datetime=stamp, **values))

    def eligible(row):
        extreme = Decimal(str(row["low" if direction == 1 else "high"]))
        boundary = Decimal(str(limit)) - direction * Decimal(str(tick))
        penetrated = extreme <= boundary if direction == 1 else extreme >= boundary
        return penetrated and math.floor(row["volume"]) >= quantity

    observed = next((index for index, row in enumerate(rows) if eligible(row)), None)
    if observed is None:
        return None
    index = observed
    if policy == "pessimistic":
        index += 1
        if index >= len(rows) or not eligible(rows[index]):
            return None
    row = rows[index]
    if policy == "pessimistic":
        price = (_rounded(min(limit, row["high"]), tick, ROUND_FLOOR) if direction == 1
                 else _rounded(max(limit, row["low"]), tick, ROUND_CEILING))
        intrabar, note = True, "next_real_minute_worst_reachable_limit_tick"
    else:
        improved_open = (Decimal(str(row["open"])) <= Decimal(str(limit)) - Decimal(str(tick))
                         if direction == 1 else
                         Decimal(str(row["open"])) >= Decimal(str(limit)) + Decimal(str(tick)))
        price = (_rounded(row["open"], tick, ROUND_CEILING if direction == 1 else ROUND_FLOOR)
                 if improved_open else limit)
        intrabar = not improved_open
        note = "legal_open_improvement" if improved_open else "intrabar_limit"
    if (price <= 0 or not _legal_tick(price, tick) or direction * (price - limit) > 0
            or price < row["low"] or price > row["high"]):
        raise ValueError("ema_limit_unreachable_fill")
    stamp = row["bar_datetime"]
    return dict(price=price, fill_price=price, source="stage127_ema_limit_initial_" + policy,
                proxy=dict(proxy_price=price, proxy_bar_count=1,
                           proxy_first_time=stamp.isoformat(), proxy_last_time=stamp.isoformat()),
                execution_datetime=stamp, trading_date=execution_day,
                execution_time_source="ema_limit_minute", anchor_coverage_status="complete",
                expected_session_start=rows[0]["bar_datetime"].isoformat(), corrected_legacy_proxy=False,
                legacy_proxy_time="", legacy_proxy_price=0.0, fill_note=note,
                mechanism_id=MECHANISM_ID, intent_id=str(item["intent_id"]),
                epoch_id=str(item["epoch_id"]), setup_id=str(item["setup_id"]),
                signal_day=signal_day.isoformat(), execution_day=execution_day.isoformat(),
                direction=direction, limit_price=limit, trigger=limit, execution_tick=tick,
                quantity=quantity, intrabar=intrabar, policy=policy, order_type="limit",
                observed_datetime=rows[observed]["bar_datetime"],
                entry_minute=dict(row), raw_minute_close=row["close"],
                minute_volume=row["volume"], queue_allocation_proven=False,
                fill_assumption="strict_one_tick_and_total_volume_all_or_none")


def entry_minute_view(frame, *, entry_time, fill_price: float, direction: int, intrabar: bool):
    """Return a private frame, masking only the entry minute's favorable side."""
    if isinstance(direction, bool) or direction not in (1, -1):
        raise ValueError("ema_limit_invalid_direction")
    price = _number(fill_price, name="fill_price", positive=True)
    result = frame.copy(deep=True)
    selected = result["bar_datetime"].map(_moment).eq(_moment(entry_time))
    if int(selected.sum()) != 1:
        raise ValueError("ema_limit_entry_minute_not_unique")
    if intrabar:
        result.loc[selected, "open"] = price
        if direction == 1:
            result.loc[selected, "high"] = price
            result.loc[selected, "close"] = result.loc[selected, "close"].clip(upper=price)
        else:
            result.loc[selected, "low"] = price
            result.loc[selected, "close"] = result.loc[selected, "close"].clip(lower=price)
    return result


def build_ema_engine(native_engine: type, *, qualify, policy: str = "primary") -> type:
    """Return the native engine with only EMA initial entries added to its heap."""
    if not callable(qualify):
        raise TypeError("ema_limit_qualification_callable_required")
    if policy not in _POLICIES:
        raise ValueError("ema_limit_unknown_policy")
    import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847
    execution, Offset = s847.s827.execution, s847.s827.Offset

    class EmaLimitEngine(native_engine):
        def _ema_limit_audit(self, item, status, **updates):
            if not hasattr(self, "ema_limit_execution_audit"):
                self.ema_limit_execution_audit = []
            sizing, quantity = item["plan"]["sizing"], item["plan"]["volume"]
            row = {key: item.get(key) for key in (
                "mechanism_id", "intent_id", "epoch_id", "setup_id", "setup_day", "product", "contract",
                "signal_day", "execution_day", "direction", "limit_price", "execution_tick", "rank")}
            row.update(status=status, quantity=quantity, policy=policy, fill_price=None,
                       forecast_risk_amount=float(sizing["risk_per_contract"]) * quantity,
                       forecast_margin_amount=float(sizing["margin_per_contract"]) * quantity,
                       actual_risk_amount=None, actual_margin_amount=None,
                       resource_reservation_released=False, **updates)
            row = _safe(row)
            self.ema_limit_execution_audit.append(row)
            return row

        def _ema_limit_context(self, item, actual_bar):
            plan, symbol = item["plan"], str(item["contract"])
            if (str(plan["target_contract"]) != symbol
                    or plan["direction"] != ("long" if item["direction"] == 1 else "short")
                    or _day(plan["target_bar"].datetime) != _day(item["signal_day"])):
                raise ValueError("ema_limit_frozen_plan_identity_mismatch")
            if qualify(self, item, actual_bar) is not None:
                raise ValueError("ema_limit_qualification_must_return_none")
            trading_day = execution.local_timestamp(self.datetime).normalize()
            grid = execution.session_minutes(symbol, trading_day, self.strategy.available_trade_dates)
            session = execution.entry_session(self.strategy, SimpleNamespace(vt_symbol=symbol,
                trading_date=trading_day.date(), datetime=self.datetime, execution_datetime=grid[0]))
            if len(session) != len(grid) or set(session["bar_datetime"]) != set(grid):
                raise ValueError("ema_limit_incomplete_session")
            tick = execution.effective_pricetick(symbol, trading_day, self.priceticks[symbol])
            context = limit_context(item, session, tick=tick, policy=policy)
            if context is None:
                return None
            sizing, quantity, price = plan["sizing"], plan["volume"], context["price"]
            stop = _number(sizing["stop_price"], name="stop_price", positive=True)
            if item["direction"] * (float(item["limit_price"]) - stop) <= 0:
                raise ValueError("ema_limit_invalid_frozen_stop_side")
            size = float(self.sizes[symbol])
            signed_risk = item["direction"] * (price - stop)
            risk = (max(signed_risk * size, max(float(self.priceticks[symbol]) * size, 1.0))
                    if signed_risk > 0 else None)
            forecast_risk = float(sizing["risk_per_contract"]) * quantity
            forecast_margin = float(sizing["margin_per_contract"]) * quantity
            actual_margin = price * size * float(sizing["margin_ratio"]) * quantity
            context.update(stop_price=stop, signed_risk_price=signed_risk,
                stop_side_valid=signed_risk > 0, invalid_stop_side_gap=signed_risk <= 0,
                actual_risk_price=signed_risk if signed_risk > 0 else None,
                actual_risk_per_contract=risk, actual_risk_amount=risk * quantity if risk is not None else None,
                forecast_risk_amount=forecast_risk, forecast_margin_amount=forecast_margin,
                actual_margin_amount=actual_margin,
                actual_minus_forecast_risk_amount=risk * quantity - forecast_risk if risk is not None else None,
                actual_minus_forecast_margin_amount=actual_margin - forecast_margin,
                actual_to_forecast_risk_ratio=risk * quantity / forecast_risk
                    if risk is not None and forecast_risk > 0 else None,
                actual_to_forecast_margin_ratio=actual_margin / forecast_margin if forecast_margin > 0 else None)
            return context

        def _ema_limit_fill(self, item, actual_bar, context, audit):
            self.strategy.ts_activate_intent(item, float(context["price"]))
            send = self.strategy.buy if item["direction"] == 1 else self.strategy.short
            order_ids = send(str(item["contract"]), float(context["price"]), item["plan"]["volume"])
            if len(order_ids) != 1:
                raise ValueError("ema_limit_expected_one_native_open_order")
            order_id = order_ids[0]
            order = self.active_limit_orders.get(order_id)
            if order is None or order.offset != Offset.OPEN:
                raise ValueError("ema_limit_native_open_order_missing")
            order.datetime = item["plan"]["target_bar"].datetime
            run_id = item.get("run_id") or getattr(self.strategy, "ema_limit_run_id", None)
            context.update(native_order_id=str(order_id), run_id=run_id,
                           economic_mother_id=f"{MECHANISM_ID}/{run_id}/{item['intent_id']}/{order_id}"
                           if run_id else None)
            # Diagnostic/update_trade and risk hooks execute inside _fill_order;
            # all signed-risk/identity metadata must already be visible to them.
            if not hasattr(self.strategy, "ema_limit_order_contexts"):
                self.strategy.ema_limit_order_contexts = {}
            if not hasattr(self.strategy, "ts_conditional_orders"):
                self.strategy.ts_conditional_orders = {}
            self.strategy.ema_limit_order_contexts[order_id] = context
            self.strategy.ts_conditional_orders[order_id] = context
            self._stage827_order_contexts[order_id] = context
            prior_count = self.trade_count
            self._fill_order(order, actual_bar)
            if self.trade_count != prior_count + 1 or order_id in self.active_limit_orders:
                raise ValueError("ema_limit_native_fill_not_completed")
            self.strategy.ts_commit_fill(item, context["execution_day"], order_id, context)
            audit.update(_safe({key: value for key, value in context.items() if key != "proxy"}))
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
                today = _day(self.datetime)
                current = []
                for item in pending:
                    target = _day(item["execution_day"])
                    if target < today:
                        self._ema_limit_audit(item, "expired_past_day")
                        consumed.add(id(item))
                    elif target == today:
                        current.append(item)
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
                        raise ValueError("ema_limit_invalid_frozen_rank")
                    actual_bar = self.bars.get(str(item["contract"]))
                    if actual_bar is None:
                        raise ValueError("ema_limit_execution_daily_bar_missing")
                    context = self._ema_limit_context(item, actual_bar)
                    consumed.add(id(item))
                    if context is None:
                        self._ema_limit_audit(item, "expired_unfilled")
                        continue
                    audit = self._ema_limit_audit(item, "limit_queued")
                    heapq.heappush(self._stage827_execution_queue, (
                        context["execution_datetime"], self._stage827_queue_serial,
                        "ema_limit", item, (actual_bar, context, audit)))
                    self._stage827_queue_serial += 1
                while self._stage827_execution_queue:
                    _, _, kind, item, payload = heapq.heappop(self._stage827_execution_queue)
                    if kind == "ordinary":
                        if item.vt_orderid in self.active_limit_orders:
                            self._fill_order(item, payload)
                    elif kind == "ema_limit":
                        actual_bar, context, audit = payload
                        self._ema_limit_fill(item, actual_bar, context, audit)
                    else:
                        open_trade, event = payload
                        self._fill_synthetic_intraday_close(item, open_trade, event)
                self.strategy.ts_pending_intents[:] = [
                    item for item in self.strategy.ts_pending_intents if id(item) not in consumed]
            except Exception as exc:
                self.intraday_execution_failure = f"{type(exc).__name__}: {exc!r}"
                raise
            finally:
                self._stage827_execution_queue = None
                self._stage827_order_contexts = {}

    EmaLimitEngine.__name__ = "Stage127EmaLimit" + native_engine.__name__
    return EmaLimitEngine
