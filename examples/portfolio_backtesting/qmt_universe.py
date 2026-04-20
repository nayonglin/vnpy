from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from vnpy.trader.constant import Exchange


PRELOAD_START_DT: datetime = datetime(2019, 6, 1)
START_DT: datetime = datetime(2020, 1, 1)
END_DT: datetime = datetime(2026, 4, 30)


@dataclass(frozen=True)
class ProductSpec:
    product: str
    exchange: Exchange
    size: int
    pricetick: float
    slippage: float
    margin_ratio: float

    @property
    def vt_symbol(self) -> str:
        return f"{self.product}.{self.exchange.value}"

    @property
    def tq_cont_symbol(self) -> str:
        return f"KQ.m@{self.exchange.value}.{self.product}"


PRODUCT_SPECS: list[ProductSpec] = [
    ProductSpec("lc", Exchange.GFEX, 1, 50.0, 50.0, 0.12),
    ProductSpec("SM", Exchange.CZCE, 5, 2.0, 2.0, 0.12),
    ProductSpec("SA", Exchange.CZCE, 20, 1.0, 1.0, 0.12),
    ProductSpec("rb", Exchange.SHFE, 10, 1.0, 1.0, 0.10),
    ProductSpec("jm", Exchange.DCE, 60, 0.5, 1.0, 0.20),
    # ProductSpec("a", Exchange.DCE, 10, 1.0, 1.0, 0.10),  # Temporarily excluded from the universe.
    ProductSpec("hc", Exchange.SHFE, 10, 1.0, 1.0, 0.10),
    # ProductSpec("j", Exchange.DCE, 100, 0.5, 1.0, 0.20),  # Temporarily excluded from the universe.
    ProductSpec("CF", Exchange.CZCE, 5, 5.0, 5.0, 0.12),
    ProductSpec("FG", Exchange.CZCE, 20, 1.0, 1.0, 0.12),
    ProductSpec("SH", Exchange.CZCE, 30, 1.0, 1.0, 0.12),
    ProductSpec("si", Exchange.GFEX, 5, 5.0, 5.0, 0.12),
    ProductSpec("ru", Exchange.SHFE, 10, 5.0, 5.0, 0.12),
    ProductSpec("lh", Exchange.DCE, 16, 5.0, 5.0, 0.12),
    ProductSpec("sp", Exchange.SHFE, 10, 2.0, 2.0, 0.10),
    # ProductSpec("al", Exchange.SHFE, 5, 5.0, 5.0, 0.10),  # Temporarily excluded from the universe.
]


VT_SYMBOLS: list[str] = [spec.vt_symbol for spec in PRODUCT_SPECS]
RATES: dict[str, float] = {spec.vt_symbol: 0.0 for spec in PRODUCT_SPECS}
SLIPPAGES: dict[str, float] = {spec.vt_symbol: spec.slippage for spec in PRODUCT_SPECS}
SIZES: dict[str, int] = {spec.vt_symbol: spec.size for spec in PRODUCT_SPECS}
PRICETICKS: dict[str, float] = {spec.vt_symbol: spec.pricetick for spec in PRODUCT_SPECS}
MARGIN_RATIOS: dict[str, float] = {spec.vt_symbol: spec.margin_ratio for spec in PRODUCT_SPECS}
