"""Pure causal FI2 and ordered preparation state; no account or execution model.

FI2 uses the first two raw Forces' mean and then alpha=2/3. Indicators are
computed independently for each real contract. Public dates are ISO dates and
all returned values are JSON serializable. An intent is a one-day condition,
never evidence of a trade; only an explicit matching fill consumes a setup.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import hashlib
import json
import math


def _day(value, name):
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError(f"invalid_{name}")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid_{name}") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"invalid_{name}")
    return value


def _text(value, name):
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"invalid_{name}")
    return value


def _finite(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _positive(value, name):
    number = _finite(value)
    if number is None or number <= 0:
        raise ValueError(f"invalid_{name}")
    return number


def _identity(kind, *values):
    payload = json.dumps([kind, *values], ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return f"{kind}_" + hashlib.sha256(payload.encode()).hexdigest()


def force_index_rows(rows, calendar):
    """Return per-contract FI2 rows, rejecting duplicate/off-calendar keys.

    ``previous_date`` is the prior actually observed row for that contract,
    including an invalid row. Missing calendar days or invalid inputs discard
    prior indicator state. A valid gap-day bar is the new first close.
    """
    days = [_day(day, "calendar_date") for day in calendar]
    if len(days) != len(set(days)):
        raise ValueError("duplicate_calendar_date")
    calendar_index = {day: index for index, day in enumerate(sorted(days))}
    grouped = {}
    seen = set()
    for row in rows:
        try:
            day = _day(row["date"], "date")
            contract = _text(row["vt_symbol"], "vt_symbol")
            close, volume = _finite(row["close"]), _finite(row["volume"])
        except (KeyError, TypeError) as exc:
            raise ValueError("invalid_force_row") from exc
        if day not in calendar_index:
            raise ValueError(f"noncalendar_date:{day}")
        key = (contract, day)
        if key in seen:
            raise ValueError(f"duplicate_contract_date:{contract}:{day}")
        seen.add(key)
        grouped.setdefault(contract, []).append((day, close, volume))

    output = []
    for contract in sorted(grouped):
        previous_day = previous_index = previous_close = first_force = fi2 = None
        for day, close, volume in sorted(grouped[contract]):
            index = calendar_index[day]
            gap = previous_index is not None and index != previous_index + 1
            raw_force = current_fi2 = None
            ready = False
            if gap:
                previous_close = first_force = fi2 = None
            if close is None or close <= 0:
                reason = "invalid_close"
                previous_close = first_force = fi2 = None
            elif volume is None or volume <= 0:
                reason = "invalid_volume"
                previous_close = first_force = fi2 = None
            elif previous_close is None:
                previous_close = close
                reason = "calendar_gap" if gap else "warmup_close"
            else:
                raw_force = (close - previous_close) * volume
                if not math.isfinite(raw_force):
                    raise ValueError(f"nonfinite_raw_force:{contract}:{day}")
                previous_close = close
                if fi2 is None and first_force is None:
                    first_force = raw_force
                    reason = "warmup_force"
                else:
                    fi2 = (first_force / 2 + raw_force / 2 if fi2 is None
                           else (2 / 3) * raw_force + (1 / 3) * fi2)
                    if not math.isfinite(fi2):
                        raise ValueError(f"nonfinite_fi2:{contract}:{day}")
                    current_fi2 = fi2
                    ready = True
                    reason = "ready"
            output.append(dict(date=day, vt_symbol=contract, raw_force=raw_force,
                               fi2=current_fi2, ready=ready, reason=reason,
                               previous_date=previous_day))
            previous_day, previous_index = day, index
    return output


@dataclass
class _Product:
    day: str
    contract: str | None = None
    epoch_id: str | None = None
    direction: int | None = None
    setup: dict | None = None
    intent: dict | None = None


class OrderedSetupMachine:
    """Maintain independent product state for exactly one B_TS or C_TS arm."""

    def __init__(self, arm):
        if arm not in ("B_TS", "C_TS"):
            raise ValueError("invalid_arm")
        self.arm = arm
        self._products = {}

    @staticmethod
    def _result(state, decision, *, baseline_fallback=False, cancel_reason=None):
        return dict(decision=decision,
                    setup_id=state.setup["setup_id"] if state.setup else None,
                    setup_day=state.setup["setup_day"] if state.setup else None,
                    intent=dict(state.intent) if state.intent else None,
                    baseline_fallback=baseline_fallback, cancel_reason=cancel_reason)

    def cancel(self, product, day, reason):
        """Record a missing-observation boundary without inventing an OHLC bar.

        A missing real target/bar is not indicator unknown and never authorizes
        C's baseline fallback. The next close must be later than this boundary.
        """
        product = _text(product, "product")
        day = _day(day, "day")
        reason = _text(reason, "reason")
        state = self._products.get(product)
        if state is not None and day <= state.day:
            raise ValueError("nonincreasing_product_day")
        if state is None:
            state = _Product(day=day)
            self._products[product] = state
        state.day = day
        state.direction = state.setup = state.intent = None
        return self._result(state, "blocked", cancel_reason=reason)

    def on_close(self, *, product, contract, day, next_day, high, low, tick,
                 weekly_ready, weekly_direction, weekly_asof, fi_ready, fi2,
                 eligible, position_open, native_signal):
        """Observe only u's known close and freeze any intent for supplied D.

        ``native_signal`` is the original str label or None; only current
        long*/short* labels can qualify C. No prior native signal is remembered.
        Validation completes before state mutation, so a rejected call cannot
        expire an otherwise valid frozen intent.
        """
        product = _text(product, "product")
        contract = _text(contract, "contract")
        day = _day(day, "day")
        next_day = _day(next_day, "next_day") if next_day is not None else None
        if next_day is not None and next_day <= day:
            raise ValueError("next_day_not_later")
        high, low, tick = _positive(high, "high"), _positive(low, "low"), _positive(tick, "tick")
        if high < low:
            raise ValueError("high_below_low")
        for name, value in (("weekly_ready", weekly_ready), ("fi_ready", fi_ready),
                            ("eligible", eligible), ("position_open", position_open)):
            if not isinstance(value, bool):
                raise ValueError(f"invalid_{name}")
        if weekly_ready:
            if isinstance(weekly_direction, bool) or weekly_direction not in (-1, 0, 1):
                raise ValueError("invalid_weekly_direction")
            direction = int(weekly_direction)
            weekly_asof = _day(weekly_asof, "weekly_asof")
            if date.fromisoformat(weekly_asof).isocalendar()[:2] >= date.fromisoformat(day).isocalendar()[:2]:
                raise ValueError("weekly_asof_not_previous_completed_week")
        else:
            direction, weekly_asof = None, None
        if fi_ready:
            fi2 = _finite(fi2)
            if fi2 is None:
                raise ValueError("invalid_fi2")
        if native_signal is not None and not isinstance(native_signal, str):
            raise ValueError("invalid_native_signal")
        native_direction = (1 if native_signal and native_signal.startswith("long") else
                            -1 if native_signal and native_signal.startswith("short") else 0)
        state = self._products.get(product)
        if state is not None and day <= state.day:
            raise ValueError("nonincreasing_product_day")

        if state is None:
            state = _Product(day=day)
            self._products[product] = state
        epoch_changed = state.contract is not None and state.contract != contract
        direction_changed = state.direction is not None and state.direction != direction
        expired = state.intent is not None
        state.intent = None
        if state.contract != contract:
            state.epoch_id = _identity("epoch", product, contract, day)
        state.day, state.contract, state.direction = day, contract, direction
        cancel_reason = "intent_expired" if expired else None
        if epoch_changed:
            state.setup = None
            cancel_reason = "epoch_changed"
        if direction_changed:
            state.setup = None
            cancel_reason = "weekly_direction_changed"
        # Known hard restrictions dominate indicator-unknown fallback.
        if position_open or not eligible:
            state.setup = None
            return self._result(state, "blocked", cancel_reason="position_open" if position_open else "ineligible")
        # Missing indicator qualification clears preparation in both arms.
        # This is deliberately conservative: B must observe a new inverse FI.
        if not weekly_ready or not fi_ready:
            state.setup = None
            reason = "weekly_unknown" if not weekly_ready else "fi_unknown"
            fallback = self.arm == "C_TS"
            return self._result(state, "baseline_fallback" if fallback else "waiting",
                                baseline_fallback=fallback, cancel_reason=reason)
        if direction == 0:
            state.setup = None
            return self._result(state, "blocked", cancel_reason="weekly_neutral")

        if state.setup is None and fi2 * direction < 0:
            state.setup = dict(setup_id=_identity("setup", self.arm, product, state.epoch_id, day, direction),
                               setup_day=day)
        qualifies = (state.setup is not None and next_day is not None and
                     (self.arm == "B_TS" or
                      (native_direction == direction and state.setup["setup_day"] < day)))
        if not qualifies:
            return self._result(state, "waiting", cancel_reason=cancel_reason)

        tick_decimal = Decimal(str(tick))
        raw_trigger = Decimal(str(high if direction == 1 else low)) + direction * tick_decimal
        trigger = float((raw_trigger / tick_decimal).to_integral_value(
            rounding=ROUND_CEILING if direction == 1 else ROUND_FLOOR) * tick_decimal)
        if not math.isfinite(trigger):
            raise ValueError("nonfinite_trigger")
        if trigger <= 0:
            return self._result(state, "blocked", cancel_reason="invalid_trigger")
        label = ("long_triple_screen" if direction == 1 else "short_triple_screen") if self.arm == "B_TS" else native_signal
        identity = _identity("intent", self.arm, product, contract, state.epoch_id,
                             state.setup["setup_id"], day, next_day, direction, trigger,
                             weekly_asof, label)
        state.intent = dict(arm=self.arm, intent_id=identity, product=product,
                            contract=contract, epoch_id=state.epoch_id,
                            setup_id=state.setup["setup_id"], setup_day=state.setup["setup_day"],
                            signal_day=day, execution_day=next_day, direction=direction,
                            trigger=trigger, weekly_asof=weekly_asof, native_signal=label)
        return self._result(state, "intent", cancel_reason=cancel_reason)

    def on_fill(self, intent_id, execution_day):
        """Consume preparation only for a current intent filled on its sole D."""
        intent_id = _text(intent_id, "intent_id")
        execution_day = _day(execution_day, "execution_day")
        state = next((state for state in self._products.values()
                      if state.intent and state.intent["intent_id"] == intent_id), None)
        if state is None:
            raise ValueError("unknown_or_expired_intent")
        if execution_day != state.intent["execution_day"]:
            raise ValueError("fill_outside_execution_day")
        receipt = dict(intent_id=intent_id, execution_day=execution_day,
                       setup_id=state.setup["setup_id"], consumed=True)
        state.setup = state.intent = None
        return receipt
