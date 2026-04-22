from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from vnpy.trader.constant import Exchange


PRELOAD_START_DT: datetime = datetime(2019, 6, 1)
START_DT: datetime = datetime(2020, 1, 1)
END_DT: datetime = datetime(2026, 4, 30)
PREPARED_PRODUCT_METADATA_PATH: Path = (
    Path(__file__).resolve().parent / "backtest_outputs" / "tqsdk_all_futures_contract_metadata.csv"
)


def _clean_float(value: object) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    if pd.isna(result):
        return 0.0
    return result


def _load_prepared_product_metadata() -> dict[str, dict[str, float]]:
    if not PREPARED_PRODUCT_METADATA_PATH.exists():
        return {}

    df = pd.read_csv(PREPARED_PRODUCT_METADATA_PATH)
    if df.empty:
        return {}

    if "symbol_kind" in df.columns:
        df = df[df["symbol_kind"] == "product_cont"].copy()

    if df.empty:
        return {}

    metadata: dict[str, dict[str, float]] = {}
    for row in df.itertuples(index=False):
        vt_symbol = str(row.vt_symbol)
        metadata[vt_symbol] = {
            "size": _clean_float(getattr(row, "volume_multiple", 0.0)),
            "pricetick": _clean_float(getattr(row, "price_tick", 0.0)),
            "margin_ratio": _clean_float(getattr(row, "margin_ratio", 0.0)),
        }
    return metadata


PREPARED_PRODUCT_METADATA: dict[str, dict[str, float]] = _load_prepared_product_metadata()


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

    def _prepared_value(self, field: str) -> float:
        values = PREPARED_PRODUCT_METADATA.get(self.vt_symbol, {})
        return _clean_float(values.get(field, 0.0))

    @property
    def resolved_size(self) -> int:
        if self.size > 0:
            return self.size
        return int(round(self._prepared_value("size")))

    @property
    def resolved_pricetick(self) -> float:
        if self.pricetick > 0:
            return self.pricetick
        return self._prepared_value("pricetick")

    @property
    def resolved_margin_ratio(self) -> float:
        if self.margin_ratio > 0:
            return self.margin_ratio
        return self._prepared_value("margin_ratio")

    @property
    def resolved_slippage(self) -> float:
        if self.slippage > 0:
            return self.slippage
        return self.resolved_pricetick


PRODUCT_SPECS: list[ProductSpec] = [
    ProductSpec("lc", Exchange.GFEX, 1, 50.0, 50.0, 0.12),
    ProductSpec("au", Exchange.SHFE, 1000, 0.02, 0.02, 0.10),
    ProductSpec("cu", Exchange.SHFE, 5, 10.0, 10.0, 0.12),
    ProductSpec("MA", Exchange.CZCE, 10, 1.0, 1.0, 0.12),
    ProductSpec("OI", Exchange.CZCE, 10, 1.0, 1.0, 0.12),
    ProductSpec("AP", Exchange.CZCE, 10, 1.0, 1.0, 0.12),
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
SLIPPAGES: dict[str, float] = {spec.vt_symbol: spec.resolved_slippage for spec in PRODUCT_SPECS}
SIZES: dict[str, int] = {spec.vt_symbol: spec.resolved_size for spec in PRODUCT_SPECS}
PRICETICKS: dict[str, float] = {spec.vt_symbol: spec.resolved_pricetick for spec in PRODUCT_SPECS}
MARGIN_RATIOS: dict[str, float] = {spec.vt_symbol: spec.resolved_margin_ratio for spec in PRODUCT_SPECS}
