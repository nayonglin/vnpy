from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from vnpy.trader.utility import ArrayManager

from qmt_range_reversion_portfolio_strategy import QmtRangeReversionPortfolioStrategy
from qmt_roll_portfolio_strategy import DailyEntryContext


class QmtRangeReversionDirectedPortfolioStrategy(QmtRangeReversionPortfolioStrategy):
    """Range reversion strategy with per-product direction hints.

    This keeps the range-reversion research line isolated from the stage78 trend
    strategy while allowing product-specific long/short eligibility.
    """

    range_direction_hints_path: str = ""
    range_direction_hints_required: bool = True
    range_reversion_rsi_band_filter_enabled: bool = True
    range_soft_rsi_long_min: float = 25.0
    range_soft_rsi_short_max: float = 75.0
    range_use_product_continuous_signal: bool = False

    parameters: list[str] = QmtRangeReversionPortfolioStrategy.parameters + [
        "range_direction_hints_path",
        "range_direction_hints_required",
        "range_reversion_rsi_band_filter_enabled",
        "range_soft_rsi_long_min",
        "range_soft_rsi_short_max",
        "range_use_product_continuous_signal",
    ]

    def __init__(self, strategy_engine, strategy_name: str, vt_symbols: list[str], setting: dict) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.range_direction_hint_by_product: dict[str, str] = self._load_range_direction_hints()
        self.contract_ams = self.ams
        am_size_floor = max(int(self.array_manager_size_floor or 140), 1)
        am_size = max(int(self.ma_extra_long) + int(self.donchian_entry_period) + 20, am_size_floor)
        self.product_ams: dict[str, ArrayManager] = {
            product_vt: ArrayManager(am_size) for product_vt in self.product_symbols
        }

    def on_bars(self, bars) -> None:
        if not self.range_use_product_continuous_signal or not bars:
            super().on_bars(bars)
            return

        current_date = next(iter(bars.values())).datetime.strftime("%Y-%m-%d")
        mapping_today = self.daily_mapping.get(current_date, {})
        temporary_ams = dict(self.contract_ams)
        for product_vt, target_contract in mapping_today.items():
            product_am = self.product_ams.get(product_vt)
            if product_am is not None and target_contract in temporary_ams:
                temporary_ams[target_contract] = product_am

        original_ams = self.ams
        self.ams = temporary_ams
        try:
            super().on_bars(bars)
        finally:
            self.ams = original_ams

    def _load_range_direction_hints(self) -> dict[str, str]:
        path_text = str(self.range_direction_hints_path or "").strip()
        if not path_text:
            return {}

        path = Path(path_text).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"range direction hints file not found: {path}")

        df = pd.read_csv(path)
        required_columns = {"product_vt_symbol", "direction_hint"}
        missing = required_columns - set(df.columns)
        if missing:
            raise ValueError(f"range direction hints missing columns {sorted(missing)}: {path}")

        if "eligible" in df.columns:
            df = df[pd.to_numeric(df["eligible"], errors="coerce").fillna(0).astype(int) == 1].copy()

        hints: dict[str, str] = {}
        for row in df.itertuples(index=False):
            product = str(getattr(row, "product_vt_symbol", "") or "").strip()
            direction = str(getattr(row, "direction_hint", "") or "").strip().lower()
            if not product:
                continue
            if direction not in {"long", "short", "both"}:
                raise ValueError(f"invalid direction_hint for {product}: {direction}")
            hints[product] = direction
        return hints

    def _plan_flat_entry_candidates(self, day_contexts: list[DailyEntryContext]) -> dict[str, dict[str, Any]]:
        for context in day_contexts:
            context.signal_data = self._apply_direction_hint_filter(context.product_vt_symbol, context.signal_data)
        return super()._plan_flat_entry_candidates(day_contexts)

    def _apply_direction_hint_filter(self, product_vt_symbol: str, signal_data: dict[str, Any]) -> dict[str, Any]:
        result = dict(signal_data)
        raw_signal = str(result.get("signal", "") or "")
        hint = self.range_direction_hint_by_product.get(product_vt_symbol, "")
        blocked_reason = ""

        if self.range_direction_hints_required and not hint:
            blocked_reason = "missing_direction_hint"
        elif raw_signal.startswith("long") and hint == "short":
            blocked_reason = "long_blocked_by_direction_hint"
        elif raw_signal.startswith("short") and hint == "long":
            blocked_reason = "short_blocked_by_direction_hint"

        if not blocked_reason and self.range_reversion_rsi_band_filter_enabled and raw_signal:
            rsi_value = float(result.get("rsi_value", float("nan")))
            if raw_signal.startswith("long") and rsi_value < float(self.range_soft_rsi_long_min):
                blocked_reason = "long_rsi_too_extreme"
            elif raw_signal.startswith("short") and rsi_value > float(self.range_soft_rsi_short_max):
                blocked_reason = "short_rsi_too_extreme"

        result["raw_signal_before_direction_hint"] = raw_signal
        result["range_direction_hint"] = hint
        result["range_direction_filter_blocked"] = int(bool(blocked_reason))
        result["range_direction_filter_reason"] = blocked_reason
        if blocked_reason:
            result["signal"] = ""
        return result
