from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.datafeed import get_datafeed
from vnpy.trader.database import get_database
from vnpy.trader.object import HistoryRequest


TARGETS: list[tuple[str, Exchange]] = [
    ("SM", Exchange.CZCE),
    ("SA", Exchange.CZCE),
    ("rb", Exchange.SHFE),
    ("jm", Exchange.DCE),
    ("a", Exchange.DCE),
    ("hc", Exchange.SHFE),
]

START: datetime = datetime(2020, 1, 1)
END: datetime = datetime(2024, 12, 31)


def main() -> None:
    datafeed = get_datafeed()
    database = get_database()

    for symbol, exchange in TARGETS:
        req: HistoryRequest = HistoryRequest(
            symbol=symbol,
            exchange=exchange,
            interval=Interval.DAILY,
            start=START,
            end=END,
        )

        bars = datafeed.query_bar_history(req)
        count: int = len(bars) if bars else 0
        print(f"{symbol}.{exchange.value} fetched: {count}")

        if not bars:
            continue

        database.save_bar_data(bars)
        print(f"{symbol}.{exchange.value} saved: {count}")


if __name__ == "__main__":
    main()
