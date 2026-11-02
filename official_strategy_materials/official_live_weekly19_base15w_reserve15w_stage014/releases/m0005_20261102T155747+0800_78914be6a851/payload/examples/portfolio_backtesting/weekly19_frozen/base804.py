from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd
from . import base772 as s772


class QmtRollPortfolioStrategyLongTighterInitialStop(s772.QmtRollPortfolioStrategyExactAm):
    """Research-only wrapper: for long entries, use the tighter initial stop; shorts stay inherited."""

    long_tighter_initial_stop: bool = True
    parameters = [
        *s772.QmtRollPortfolioStrategyExactAm.parameters,
        "long_tighter_initial_stop",
    ]

    def _entry_stop_price(self, direction: str, bar: Any, history: pd.DataFrame, use_day_extreme: bool) -> float:
        if not bool(self.long_tighter_initial_stop):
            return super()._entry_stop_price(direction, bar, history, use_day_extreme)
        if direction != "long" or not use_day_extreme:
            return super()._entry_stop_price(direction, bar, history, use_day_extreme)

        close_price = float(bar.close_price)
        low_price = float(bar.low_price)
        basic_long = close_price * (1 - self.stop_loss_pct)
        day_drop_ratio = (close_price - low_price) / close_price if close_price > 0 else 0.0
        old_stop = basic_long if day_drop_ratio < self.stop_loss_pct else low_price
        new_stop = max(basic_long, low_price)

        if abs(new_stop - old_stop) > 1e-9:
            diagnostics = getattr(self, "trade_event_diagnostics", None)
            if diagnostics is not None:
                dt_value = getattr(bar, "datetime", "")
                try:
                    date_text = str(pd.Timestamp(dt_value).date())
                except Exception:
                    date_text = str(dt_value)
                diagnostics.append(
                    {
                        "datetime": date_text,
                        "date": date_text,
                        "vt_symbol": getattr(bar, "vt_symbol", ""),
                        "product_vt_symbol": self._product_vt_symbol(getattr(bar, "vt_symbol", "")),
                        "position_direction": "long",
                        "direction": "long",
                        "offset": "RiskSizing",
                        "reason": "long_tighter_initial_stop_adjust",
                        "volume": 0,
                        "price": close_price,
                        "old_stop": old_stop,
                        "new_stop": new_stop,
                        "old_stop_distance": close_price - old_stop,
                        "new_stop_distance": close_price - new_stop,
                        "old_stop_distance_pct": (close_price - old_stop) / close_price if close_price > 0 else np.nan,
                        "new_stop_distance_pct": (close_price - new_stop) / close_price if close_price > 0 else np.nan,
                        "signal_low": low_price,
                        "signal_close": close_price,
                        "stop_loss_pct": self.stop_loss_pct,
                        "old_case": "basic_min_distance" if day_drop_ratio < self.stop_loss_pct else "day_low",
                    }
                )
        return new_stop
