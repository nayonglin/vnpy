from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database
from vnpy.trader.object import HistoryRequest

from main_contract_mapping import build_contract_metadata
from qmt_universe import END_DT, PRELOAD_START_DT


LOCAL_TQSDK_PATH: Path = PROJECT_ROOT / "vnpy_tqsdk" / "tqsdk_datafeed.py"
spec = importlib.util.spec_from_file_location("local_vnpy_tqsdk_datafeed", LOCAL_TQSDK_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
TqsdkDatafeed = module.TqsdkDatafeed


def split_vt_symbol(vt_symbol: str) -> tuple[str, Exchange]:
    symbol, exchange = vt_symbol.split(".", 1)
    return symbol, Exchange(exchange)


def main() -> None:
    metadata = build_contract_metadata()
    vt_symbols: list[str] = metadata["vt_symbols"]

    datafeed = TqsdkDatafeed()
    database = get_database()

    for vt_symbol in vt_symbols:
        symbol, exchange = split_vt_symbol(vt_symbol)
        req = HistoryRequest(
            symbol=symbol,
            exchange=exchange,
            interval=Interval.DAILY,
            start=PRELOAD_START_DT,
            end=END_DT,
        )
        bars = datafeed.query_bar_history(req)
        count: int = len(bars) if bars else 0
        print(f"{vt_symbol} fetched: {count}")

        if not bars:
            continue

        database.save_bar_data(bars)
        print(f"{vt_symbol} saved: {count}")


if __name__ == "__main__":
    main()
