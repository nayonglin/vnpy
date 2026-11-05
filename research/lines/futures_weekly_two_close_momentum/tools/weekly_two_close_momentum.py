"""Independent, single-physical-contract weekly momentum replay."""
from __future__ import annotations

import argparse
import csv
from collections import deque
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import astuple, dataclass, fields, replace
from datetime import date
from decimal import Decimal
from pathlib import Path
import sys


@dataclass(frozen=True)
class WeeklyBar:
    contract: str
    first_day: date
    week_end: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal

    def __post_init__(self):
        prices = (self.open, self.high, self.low, self.close)
        if not self.contract or not (
            self.first_day <= self.week_end
            and self.first_day.isocalendar()[:2] == self.week_end.isocalendar()[:2]
        ):
            raise ValueError("contract and chronological trading dates in one week required")
        if not all(price.is_finite() and price > 0 for price in prices) or not (
            self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high
        ):
            raise ValueError(f"invalid weekly OHLC on {self.week_end}")


@dataclass(frozen=True)
class Event:
    contract: str
    event: str
    action: str
    trading_day: date
    signal_day: date
    volume: int
    price: Decimal | None
    stop_price: Decimal


def weekly_action(
    position: int, current: WeeklyBar, previous: WeeklyBar, older: WeeklyBar | None,
    *, two_close_entry: bool = False,
) -> tuple[str, Decimal] | None:
    if position == 1 and current.close <= previous.low:
        return "close_long", previous.low
    if position == -1 and current.close >= previous.high:
        return "close_short", previous.high
    if position == 0:
        if previous.close < current.close and (two_close_entry or (older and older.close < previous.close)):
            return "open_long", current.low
        if previous.close > current.close and (two_close_entry or (older and older.close > previous.close)):
            return "open_short", current.high
    return None


MA_PERIODS = (5, 10, 20)


def weekly_ma_slopes(
    history: Sequence[WeeklyBar | None], periods: tuple[int, ...] = MA_PERIODS,
) -> tuple[Decimal, ...] | None:
    """Adjacent completed-week SMA differences, oldest to latest input."""
    required = max(periods) + 1
    lookback = history[-required:]
    if len(lookback) != required or any(bar is None for bar in lookback):
        return None
    closes = [bar.close for bar in lookback]
    return tuple((closes[-1] - closes[-period - 1]) / period for period in periods)


def blocks_entry(action: str, slopes: tuple[Decimal, ...] | None) -> bool:
    if slopes is None:
        return False
    if action == "open_short":
        return all(slope > 0 for slope in slopes)
    if action == "open_long":
        return all(slope < 0 for slope in slopes)
    return False


def replay(bars: Iterable[WeeklyBar], *, two_close_entry: bool = False) -> Iterator[Event]:
    """Evaluate completed weeks and execute earlier signals at subsequent opens."""
    older = previous = None
    pending = None
    position = 0
    history = deque(maxlen=max(MA_PERIODS) + 1)

    for current in bars:
        if previous is not None:
            if current.contract != previous.contract:
                raise ValueError("one physical contract required per replay")
            if current.first_day.isocalendar()[:2] <= previous.week_end.isocalendar()[:2]:
                raise ValueError("weekly bars must be strictly ordered and unique")

        if pending is not None:
            if pending.action == "open_long":
                position = 1
            elif pending.action == "open_short":
                position = -1
            else:
                position = 0
            yield replace(pending, event="fill", trading_day=current.first_day, price=current.open)
            pending = None

        history.append(current)
        decision = None
        if previous is not None:
            decision = weekly_action(position, current, previous, older, two_close_entry=two_close_entry)
        if decision is not None:
            action, stop = decision
            if position or not blocks_entry(action, weekly_ma_slopes(list(history))):
                pending = Event(
                    current.contract, "signal", action, current.week_end, current.week_end, 1, None, stop,
                )
                yield pending
        older, previous = previous, current


def read_bars(path: Path) -> Iterator[WeeklyBar]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        required = {field.name for field in fields(WeeklyBar)}
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError(f"required CSV columns: {', '.join(sorted(required))}")
        for row in reader:
            yield WeeklyBar(
                row["contract"].strip(),
                date.fromisoformat(row["first_day"]),
                date.fromisoformat(row["week_end"]),
                *(Decimal(row[name]) for name in ("open", "high", "low", "close")),
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("weekly_csv", type=Path, help="Ordered completed weekly bars for one physical contract.")
    parser.add_argument("--two-close-entry", action="store_true")
    args = parser.parse_args()
    events = list(replay(read_bars(args.weekly_csv), two_close_entry=args.two_close_entry))
    writer = csv.writer(sys.stdout)
    writer.writerow(field.name for field in fields(Event))
    writer.writerows(astuple(event) for event in events)


if __name__ == "__main__":
    main()
