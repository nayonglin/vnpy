from __future__ import annotations

from typing import Any

import pandas as pd

from vnpy.trader.constant import Direction, Interval
from vnpy.trader.object import BarData
from vnpy.trader.utility import ArrayManager

from qmt_roll_portfolio_strategy import PositionLayer, ProductState, QmtRollPortfolioStrategy


class QmtBollReversalPortfolioStrategy(QmtRollPortfolioStrategy):
    """
    Mean-reversion futures strategy based on Bollinger band breakouts.

    Entry:
    - Short when close breaks above upper Bollinger band and MAs are not in bullish alignment
    - Long when close breaks below lower Bollinger band and MAs are not in bearish alignment

    Exit:
    - Initial stop uses signal-bar true range: high + 0.5 * TR for short, low - 0.5 * TR for long
    - After entry, trailing stop moves to previous day's high/low and is evaluated intraday
    """

    author: str = "GPT-5.4"

    boll_window: int = 26
    boll_dev: float = 2.0
    entry_tr_multiplier: float = 0.5
    previous_day_stop_enabled: bool = True
    block_short_when_all_ma_rising: bool = True
    block_long_when_all_ma_falling: bool = True

    long_entry_enabled: bool = True
    short_entry_enabled: bool = True
    exit_on_alignment_break: bool = False
    enable_ma_trend_stop: bool = False
    rollover_reopen_enabled: bool = True
    reverse_on_opposite_signal: bool = False
    enable_prev2day_stop: bool = False
    enable_rsi_partial_exit: bool = False
    trailing_stop_enabled: bool = False
    trailing_stop_pct: float = 0.0
    atr_2x_mid_stop_enabled: bool = False

    enable_add_position: bool = False
    ma5_extreme_filter_enabled: bool = False
    ma5_angle_reversal_filter_enabled: bool = False
    short_ma5_slope_filter_enabled: bool = False
    wick_chop_filter_enabled: bool = False
    enable_donchian_add_position: bool = False

    parameters: list[str] = QmtRollPortfolioStrategy.parameters + [
        "boll_window",
        "boll_dev",
        "entry_tr_multiplier",
        "previous_day_stop_enabled",
        "block_short_when_all_ma_rising",
        "block_long_when_all_ma_falling",
    ]

    def on_init(self) -> None:
        self.write_log("Boll reversal portfolio strategy initialized")
        self.load_bars(self.warmup_days, interval=Interval.DAILY)

    def on_start(self) -> None:
        self.write_log("Boll reversal portfolio strategy started")

    def on_stop(self) -> None:
        self.write_log("Boll reversal portfolio strategy stopped")

    def calculate_price(self, vt_symbol: str, direction: Direction, reference: float) -> float:
        override_price: float | None = self.execution_price_overrides.get(vt_symbol)
        if override_price is not None and override_price > 0:
            return override_price

        pricetick: float = self.get_pricetick(vt_symbol)
        if direction == Direction.LONG:
            return reference + self.tick_add * pricetick
        return reference - self.tick_add * pricetick

    def _can_open_short_signal(self, signal: str) -> bool:
        return signal == "short_reversal"

    def _rollover_reopen_allowed(
        self,
        old_direction: str,
        history: pd.DataFrame,
        signal_data: dict[str, Any],
    ) -> bool:
        return old_direction in {"long", "short"}

    def _generate_signal(self, am: ArrayManager, history: pd.DataFrame) -> dict[str, Any]:
        close = pd.Series(am.close_array, dtype="float64")
        ma_short = close.rolling(self.ma_short).mean()
        ma_mid = close.rolling(self.ma_mid).mean()
        ma_long = close.rolling(self.ma_long).mean()
        ma_extra_long = close.rolling(self.ma_extra_long).mean()

        middle = close.rolling(self.boll_window).mean()
        std = close.rolling(self.boll_window).std(ddof=0)
        upper = middle + self.boll_dev * std
        lower = middle - self.boll_dev * std

        required_values = [
            ma_short.iloc[-1],
            ma_mid.iloc[-1],
            ma_long.iloc[-1],
            ma_extra_long.iloc[-1],
            ma_mid.iloc[-2],
            ma_long.iloc[-2],
            upper.iloc[-1],
            upper.iloc[-2],
            lower.iloc[-1],
            lower.iloc[-2],
            close.iloc[-1],
            close.iloc[-2],
        ]
        if any(pd.isna(value) for value in required_values):
            return self._signal_result(
                "",
                False,
                False,
                float("nan"),
                float("nan"),
                float("nan"),
                float("nan"),
                "regular",
                False,
            )

        short_t = float(ma_short.iloc[-1])
        mid_t = float(ma_mid.iloc[-1])
        long_t = float(ma_long.iloc[-1])
        extra_t = float(ma_extra_long.iloc[-1])
        short_y = float(ma_short.iloc[-2])
        mid_y = float(ma_mid.iloc[-2])
        long_y = float(ma_long.iloc[-2])
        extra_y = float(ma_extra_long.iloc[-2])

        bullish_alignment = short_t > mid_t > long_t > extra_t
        bearish_alignment = short_t < mid_t < long_t < extra_t
        all_ma_rising = short_t > short_y and mid_t > mid_y and long_t > long_y and extra_t > extra_y
        all_ma_falling = short_t < short_y and mid_t < mid_y and long_t < long_y and extra_t < extra_y

        close_y = float(close.iloc[-2])
        close_t = float(close.iloc[-1])
        upper_y = float(upper.iloc[-2])
        upper_t = float(upper.iloc[-1])
        lower_y = float(lower.iloc[-2])
        lower_t = float(lower.iloc[-1])

        breakout_upper = close_y <= upper_y and close_t > upper_t
        breakout_lower = close_y >= lower_y and close_t < lower_t

        signal = ""
        if breakout_upper and not bullish_alignment and self.short_entry_enabled:
            signal = "short_reversal"
        elif breakout_lower and not bearish_alignment and self.long_entry_enabled:
            signal = "long_reversal"

        if signal == "short_reversal" and self.block_short_when_all_ma_rising and all_ma_rising:
            signal = ""
        elif signal == "long_reversal" and self.block_long_when_all_ma_falling and all_ma_falling:
            signal = ""

        if signal and not self._passes_entry_filters(signal, history):
            signal = ""

        return self._signal_result(
            signal,
            bullish_alignment,
            bearish_alignment,
            float(ma_mid.iloc[-1]),
            float(ma_long.iloc[-1]),
            float(ma_long.iloc[-2]),
            float(ma_mid.iloc[-2]),
            "regular",
            bool(signal),
            float("nan"),
        )

    def _entry_stop_price(self, direction: str, bar: BarData, history: pd.DataFrame, use_day_extreme: bool) -> float:
        true_range: float = self._signal_bar_true_range(bar, history)
        stop_buffer: float = self.entry_tr_multiplier * true_range

        if direction == "long":
            return float(bar.low_price) - stop_buffer
        return float(bar.high_price) + stop_buffer

    def _update_dynamic_stops(self, state: ProductState, bar: BarData, history: pd.DataFrame) -> None:
        for layer in state.layers:
            self._update_layer_metrics(layer, bar)

        if not self.previous_day_stop_enabled or len(history) < 2:
            return

        prev_day = history.iloc[-2]
        if state.direction == "long":
            stop_price = float(prev_day["low"])
            for layer in state.layers:
                layer.stop_price = max(layer.stop_price, stop_price)
        else:
            stop_price = float(prev_day["high"])
            for layer in state.layers:
                layer.stop_price = min(layer.stop_price, stop_price)

    def _update_layer_metrics(self, layer: PositionLayer, bar: BarData) -> None:
        close_price: float = float(bar.close_price)
        layer.highest_price = max(layer.highest_price, float(bar.high_price))
        layer.lowest_price = min(layer.lowest_price, float(bar.low_price))

        if layer.direction == "long":
            pnl_pct = (close_price - layer.entry_price) / layer.entry_price if layer.entry_price else 0.0
        else:
            pnl_pct = (layer.entry_price - close_price) / layer.entry_price if layer.entry_price else 0.0
        layer.max_profit_pct = max(layer.max_profit_pct, pnl_pct)

    def _signal_bar_true_range(self, bar: BarData, history: pd.DataFrame) -> float:
        high_price: float = float(bar.high_price)
        low_price: float = float(bar.low_price)

        prev_close: float = float(bar.close_price)
        if len(history) >= 2:
            prev_close = float(history["close"].iloc[-2])

        true_range = max(
            high_price - low_price,
            abs(high_price - prev_close),
            abs(low_price - prev_close),
        )
        return max(true_range, float(self.get_pricetick(bar.vt_symbol)))
