from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd
from .qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
from vnpy.trader.utility import ArrayManager


class QmtRollPortfolioStrategyExactAm(QmtRollPortfolioStrategy):
    """Research-only wrapper that replaces ArrayManager size after normal init."""

    research_exact_array_manager_size: int = 0
    parameters = [
        *QmtRollPortfolioStrategy.parameters,
        "research_exact_array_manager_size",
    ]

    def __init__(self, strategy_engine: Any, strategy_name: str, vt_symbols: list[str], setting: dict[str, Any]) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        exact_size = int(self.research_exact_array_manager_size or 0)
        if exact_size > 0:
            self.ams = {vt_symbol: ArrayManager(exact_size) for vt_symbol in self.vt_symbols}
