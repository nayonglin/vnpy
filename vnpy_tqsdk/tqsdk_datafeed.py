from __future__ import annotations

from datetime import datetime
from collections.abc import Callable
import re
import traceback

from pandas import DataFrame
from tqsdk import TqApi, TqAuth

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.datafeed import BaseDatafeed
from vnpy.trader.object import BarData, HistoryRequest
from vnpy.trader.setting import SETTINGS
from vnpy.trader.utility import ZoneInfo


INTERVAL_VT2TQ: dict[Interval, int] = {
    Interval.MINUTE: 60,
    Interval.HOUR: 60 * 60,
    Interval.DAILY: 60 * 60 * 24,
}

FUTURES_EXCHANGES: set[Exchange] = {
    Exchange.CFFEX,
    Exchange.SHFE,
    Exchange.CZCE,
    Exchange.DCE,
    Exchange.INE,
    Exchange.GFEX,
}

CONTINUOUS_MAIN_SUFFIXES: set[str] = {"88", "888"}
CONTINUOUS_INDEX_SUFFIXES: set[str] = {"99", "889"}

CHINA_TZ = ZoneInfo("Asia/Shanghai")


class TqsdkDatafeed(BaseDatafeed):
    """TqSdk datafeed with support for futures dominant symbols."""

    def __init__(self) -> None:
        self.username: str = SETTINGS["datafeed.username"]
        self.password: str = SETTINGS["datafeed.password"]

    def init(self, output: Callable = print) -> bool:
        if not self.username:
            output("TqSdk数据服务初始化失败：`datafeed.username` 为空，请填写快期账户。")
            return False

        if not self.password:
            output("TqSdk数据服务初始化失败：`datafeed.password` 为空，请填写快期账户密码。")
            return False

        return True

    def query_bar_history(
        self,
        req: HistoryRequest,
        output: Callable = print,
    ) -> list[BarData] | None:
        """Query bar history from TqSdk."""
        if not self.init(output):
            return []

        interval: int | None = INTERVAL_VT2TQ.get(req.interval, None)
        if not interval:
            output(f"TqSdk查询K线数据失败：不支持的时间周期 {req.interval.value}")
            return []

        tq_symbol: str = to_tq_symbol(req)
        api: TqApi | None = None

        try:
            api = TqApi(auth=TqAuth(self.username, self.password))
            data_length: int = estimate_data_length(req, interval)
            df: DataFrame = api.get_kline_serial(
                symbol=tq_symbol,
                duration_seconds=interval,
                data_length=data_length,
            )
        except Exception:
            output(traceback.format_exc())
            return []
        finally:
            if api is not None:
                api.close()

        bars: list[BarData] = []
        if df is None or df.empty:
            return bars

        for row in df.itertuples():
            dt: datetime = datetime.fromtimestamp(row.datetime / 1_000_000_000, tz=CHINA_TZ)  # type: ignore[attr-defined]
            if dt < req.start.replace(tzinfo=CHINA_TZ) or dt > req.end.replace(tzinfo=CHINA_TZ):
                continue
            bar: BarData = BarData(
                symbol=req.symbol,
                exchange=req.exchange,
                interval=req.interval,
                datetime=dt,
                open_price=row.open,
                high_price=row.high,
                low_price=row.low,
                close_price=row.close,
                volume=row.volume,
                open_interest=getattr(row, "open_oi", 0),
                gateway_name="TQ",
            )
            bars.append(bar)

        return bars


def to_tq_symbol(req: HistoryRequest) -> str:
    symbol: str = req.symbol
    exchange: Exchange = req.exchange

    if exchange in FUTURES_EXCHANGES:
        product, suffix = split_symbol_suffix(symbol)

        if product and not suffix:
            return f"KQ.m@{exchange.value}.{normalize_product(product, exchange)}"

        if suffix in CONTINUOUS_MAIN_SUFFIXES:
            return f"KQ.m@{exchange.value}.{normalize_product(product, exchange)}"

        if suffix in CONTINUOUS_INDEX_SUFFIXES:
            return f"KQ.i@{exchange.value}.{normalize_product(product, exchange)}"

    normalized_symbol: str = normalize_contract_symbol(symbol, exchange)
    return f"{exchange.value}.{normalized_symbol}"


def split_symbol_suffix(symbol: str) -> tuple[str, str]:
    match = re.fullmatch(r"([A-Za-z]+)([0-9A-Za-z]*)", symbol)
    if not match:
        return symbol, ""
    return match.group(1), match.group(2)


def normalize_product(product: str, exchange: Exchange) -> str:
    if exchange in {Exchange.CZCE, Exchange.CFFEX}:
        return product.upper()
    return product.lower()


def normalize_contract_symbol(symbol: str, exchange: Exchange) -> str:
    if exchange in {Exchange.CZCE, Exchange.CFFEX}:
        return symbol.upper()
    return symbol.lower()


def estimate_data_length(req: HistoryRequest, interval_seconds: int) -> int:
    span_seconds: float = max((req.end - req.start).total_seconds(), interval_seconds)
    estimated: int = int(span_seconds // interval_seconds) + 300
    return min(max(estimated, 500), 10000)
