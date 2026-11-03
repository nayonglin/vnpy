"""Weekly19 research decisions for completed weeks and ordered execution events."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

WEEKLY_STOP_REASONS = ("prev2day_stop", "base_stop", "ma_stop")


@dataclass(frozen=True)
class WeeklyBar:
    day: date
    high: Decimal
    low: Decimal
    close: Decimal

    def __post_init__(self):
        high, low, close = (Decimal(str(x)) for x in (self.high, self.low, self.close))
        if not all(x.is_finite() for x in (high, low, close)) or not 0 < low <= close <= high:
            raise ValueError("invalid completed week prices")
        object.__setattr__(self, "high", high)
        object.__setattr__(self, "low", low)
        object.__setattr__(self, "close", close)


@dataclass(frozen=True)
class StopSignal:
    position_id: str
    symbol: str
    epoch: str
    direction: str
    reason: str
    signal_week: WeeklyBar
    scheduled_close_day: date
    opening_risk_ratio: Decimal
    is_reverse_position: bool = False


@dataclass(frozen=True)
class CloseFill:
    position_id: str
    timestamp: datetime
    trading_day: date
    remaining_volume: int


@dataclass(frozen=True)
class EntryAnchor:
    """An admitted post-flat quote and contemporaneous account capacity.

    The replay adapter supplies the executable side price, after-close equity
    and final hard-risk lot cap. It owns quote, portfolio and fill provenance.
    """

    symbol: str
    epoch: str
    timestamp: datetime
    trading_day: date
    price: Decimal
    equity: Decimal
    risk_multiplier: Decimal
    contract_size: int
    volume_cap: int
    price_tick: Decimal


@dataclass(frozen=True)
class ReversePlan:
    parent_position_id: str
    symbol: str
    direction: str
    reference_price: Decimal
    initial_stop: Decimal
    risk_budget: Decimal
    volume: int


@dataclass(frozen=True)
class ReversePosition:
    direction: str
    current_stop: Decimal
    entry_day: date


def _trade_week(day: date) -> tuple[int, int]:
    return day.isocalendar()[:2]


def plan_reversal(signal: StopSignal, fill: CloseFill, anchor: EntryAnchor) -> ReversePlan | None:
    """Return a single eligible plan; the adapter owns one-shot consumption."""
    if signal.direction not in ("long", "short"):
        raise ValueError("invalid original direction")
    if signal.is_reverse_position or signal.reason not in {
        f"{signal.direction}_{reason}" for reason in WEEKLY_STOP_REASONS
    }:
        return None
    if fill.position_id != signal.position_id or fill.remaining_volume != 0:
        return None
    if (anchor.symbol, anchor.epoch) != (signal.symbol, signal.epoch):
        return None
    if fill.timestamp.utcoffset() is None or anchor.timestamp.utcoffset() is None:
        raise ValueError("execution timestamps require timezone offsets")
    scheduled_week = _trade_week(signal.scheduled_close_day)
    if not (
        signal.signal_week.day < signal.scheduled_close_day <= fill.trading_day <= anchor.trading_day
        and _trade_week(fill.trading_day) == _trade_week(anchor.trading_day) == scheduled_week
        and fill.timestamp < anchor.timestamp
    ):
        return None

    price, equity, ratio, multiplier, tick = (
        Decimal(str(x))
        for x in (anchor.price, anchor.equity, signal.opening_risk_ratio, anchor.risk_multiplier, anchor.price_tick)
    )
    if (
        not all(x.is_finite() and x > 0 for x in (price, equity, ratio, multiplier, tick))
        or type(anchor.contract_size) is not int or anchor.contract_size <= 0
        or type(anchor.volume_cap) is not int or anchor.volume_cap <= 0
    ):
        return None
    if signal.direction == "long":
        direction, stop = "short", signal.signal_week.high
        distance = stop - price
    else:
        direction, stop = "long", signal.signal_week.low
        distance = price - stop
    if distance <= 0:
        return None

    budget = equity * ratio * multiplier
    risk_per_lot = max(distance * anchor.contract_size, tick * anchor.contract_size, Decimal(1))
    volume = min(anchor.volume_cap, int(budget // risk_per_lot))
    if volume <= 0:
        return None
    return ReversePlan(signal.position_id, signal.symbol, direction, price, stop, budget, volume)


def advance_protection(
    position: ReversePosition, completed_weeks: tuple[WeeklyBar, ...],
) -> tuple[Decimal, bool]:
    """Check one fresh completed week against initial/two-week protection.

    The replay adapter supplies the physical contract's ordered weekly history
    ending at the fresh evaluation week, proves that evaluation follows entry
    even when both share a trading date, and persists the returned stop.
    """
    if position.direction not in ("long", "short"):
        raise ValueError("invalid reversal direction")
    stop = Decimal(str(position.current_stop))
    if not stop.is_finite() or stop <= 0:
        raise ValueError("invalid reversal protection price")
    if not completed_weeks:
        return stop, False
    if any(
        _trade_week(before.day) >= _trade_week(after.day)
        for before, after in zip(completed_weeks, completed_weeks[1:])
    ):
        raise ValueError("completed weeks must be ordered and unique")

    current = completed_weeks[-1]
    if current.day < position.entry_day:
        return stop, False
    prior = completed_weeks[-3:-1]
    can_move = len(prior) == 2 and prior[-1].day > position.entry_day
    if position.direction == "long":
        if can_move:
            stop = max(stop, min(bar.low for bar in prior))
        return stop, current.close <= stop

    if can_move:
        stop = min(stop, max(bar.high for bar in prior))
    return stop, current.close >= stop
