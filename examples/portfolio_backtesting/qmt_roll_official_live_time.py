from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
import time


class Clock(Protocol):
    """Injectable wall/monotonic clock used by the live execution pipeline."""

    def epoch_ns(self) -> int:
        """Return Unix epoch time in nanoseconds."""

    def monotonic_ns(self) -> int:
        """Return process-local monotonic time in nanoseconds."""

    def sleep(self, seconds: float) -> None:
        """Sleep for the requested duration."""


@dataclass(frozen=True, slots=True)
class SystemClock:
    def epoch_ns(self) -> int:
        return time.time_ns()

    def monotonic_ns(self) -> int:
        return time.monotonic_ns()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


def utc_iso_from_epoch_ns(epoch_ns: int) -> str:
    """Format one epoch sample as an aware UTC timestamp without resampling."""

    seconds, nanoseconds = divmod(int(epoch_ns), 1_000_000_000)
    instant = datetime.fromtimestamp(seconds, tz=timezone.utc)
    return f"{instant:%Y-%m-%dT%H:%M:%S}.{nanoseconds:09d}Z"
