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

    risk_ratio_of_total_assets: float = 0.01
    streak_risk_multipliers: str = "1.0,1.0,1.0,0.5"
    boll_window: int = 26
    boll_dev: float = 2.0
    boll_entry_mode: str = "breakout"
    entry_tr_multiplier: float = 0.5
    previous_day_stop_enabled: bool = True
    exit_on_boll_middle_touch: bool = False
    max_holding_days: int = 0
    range_filter_enabled: bool = False
    range_filter_lookback: int = 120
    range_filter_min_observations: int = 60
    range_max_bandwidth_quantile: float = 0.60
    range_max_ma_spread_quantile: float = 0.70
    reversal_rsi_filter_enabled: bool = False
    reversal_rsi_long_max: float = 35.0
    reversal_rsi_short_min: float = 65.0
    reverse_signal_direction: bool = False
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
        "boll_entry_mode",
        "entry_tr_multiplier",
        "previous_day_stop_enabled",
        "exit_on_boll_middle_touch",
        "max_holding_days",
        "range_filter_enabled",
        "range_filter_lookback",
        "range_filter_min_observations",
        "range_max_bandwidth_quantile",
        "range_max_ma_spread_quantile",
        "reversal_rsi_filter_enabled",
        "reversal_rsi_long_max",
        "reversal_rsi_short_min",
        "reverse_signal_direction",
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
        rsi_value = float(am.rsi(int(self.rsi_length)))

        entry_mode = str(self.boll_entry_mode or "breakout").strip().lower()
        if entry_mode in {"reentry", "reentry_confirmed", "inside_reentry", "reentry_reversal_bar"}:
            trigger_upper = close_y > upper_y and close_t <= upper_t
            trigger_lower = close_y < lower_y and close_t >= lower_t
        else:
            trigger_upper = close_y <= upper_y and close_t > upper_t
            trigger_lower = close_y >= lower_y and close_t < lower_t
        if entry_mode == "reentry_reversal_bar":
            trigger_upper = trigger_upper and close_t < close_y
            trigger_lower = trigger_lower and close_t > close_y

        signal = ""
        if self.reverse_signal_direction:
            if trigger_upper and not bullish_alignment and self.long_entry_enabled:
                signal = "long_reversal"
            elif trigger_lower and not bearish_alignment and self.short_entry_enabled:
                signal = "short_reversal"
        else:
            if trigger_upper and not bullish_alignment and self.short_entry_enabled:
                signal = "short_reversal"
            elif trigger_lower and not bearish_alignment and self.long_entry_enabled:
                signal = "long_reversal"

        if signal == "short_reversal" and self.block_short_when_all_ma_rising and all_ma_rising:
            signal = ""
        elif signal == "long_reversal" and self.block_long_when_all_ma_falling and all_ma_falling:
            signal = ""

        if signal and self.reversal_rsi_filter_enabled:
            if pd.isna(rsi_value):
                signal = ""
            elif signal == "long_reversal" and rsi_value > float(self.reversal_rsi_long_max):
                signal = ""
            elif signal == "short_reversal" and rsi_value < float(self.reversal_rsi_short_min):
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
            rsi_value,
        )

    def _passes_entry_filters(self, signal: str, history: pd.DataFrame) -> bool:
        if not super()._passes_entry_filters(signal, history):
            return False
        if self.range_filter_enabled and not self._passes_range_regime_filter(history):
            return False
        return True

    def _passes_range_regime_filter(self, history: pd.DataFrame) -> bool:
        if history.empty or "close" not in history:
            return False

        close = pd.to_numeric(history["close"], errors="coerce").astype("float64")
        middle = close.rolling(int(self.boll_window)).mean()
        std = close.rolling(int(self.boll_window)).std(ddof=0)
        upper = middle + float(self.boll_dev) * std
        lower = middle - float(self.boll_dev) * std
        middle_denominator = middle.abs().where(middle.abs() > 1e-12)
        bandwidth = (upper - lower).abs() / middle_denominator

        ma_frame = pd.concat(
            [
                close.rolling(int(self.ma_short)).mean(),
                close.rolling(int(self.ma_mid)).mean(),
                close.rolling(int(self.ma_long)).mean(),
                close.rolling(int(self.ma_extra_long)).mean(),
            ],
            axis=1,
        )
        close_denominator = close.abs().where(close.abs() > 1e-12)
        ma_spread = (ma_frame.max(axis=1) - ma_frame.min(axis=1)).abs() / close_denominator

        lookback = max(
            int(self.range_filter_lookback or 0),
            int(self.boll_window) * 2,
            int(self.ma_extra_long) * 2,
        )
        min_observations = max(20, int(self.range_filter_min_observations or 0))
        bandwidth_sample = bandwidth.dropna().tail(lookback)
        ma_spread_sample = ma_spread.dropna().tail(lookback)
        if len(bandwidth_sample) < min_observations or len(ma_spread_sample) < min_observations:
            return False

        bandwidth_now = float(bandwidth_sample.iloc[-1])
        ma_spread_now = float(ma_spread_sample.iloc[-1])
        bandwidth_q = max(0.0, min(1.0, float(self.range_max_bandwidth_quantile)))
        ma_spread_q = max(0.0, min(1.0, float(self.range_max_ma_spread_quantile)))
        bandwidth_limit = float(bandwidth_sample.quantile(bandwidth_q))
        ma_spread_limit = float(ma_spread_sample.quantile(ma_spread_q))
        return bandwidth_now <= bandwidth_limit and ma_spread_now <= ma_spread_limit

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

    def _process_layer_stops(self, state: ProductState, bar: BarData) -> str:
        stop_reason = super()._process_layer_stops(state, bar)
        if stop_reason or not state.layers:
            return stop_reason

        middle_exit_reason = self._process_boll_middle_exit(state, bar)
        if middle_exit_reason:
            return middle_exit_reason

        time_exit_reason = self._process_max_holding_exit(state, bar)
        if time_exit_reason:
            return time_exit_reason

        return ""

    def _process_boll_middle_exit(self, state: ProductState, bar: BarData) -> str:
        if not self.exit_on_boll_middle_touch or not state.contract_vt_symbol:
            return ""

        am = self.ams.get(state.contract_vt_symbol)
        if am is None or not am.inited:
            return ""

        history = self._build_history_df(am)
        if len(history) < max(int(self.boll_window), 1):
            return ""

        middle = history["close"].rolling(int(self.boll_window)).mean()
        middle_value = float(middle.iloc[-1]) if not pd.isna(middle.iloc[-1]) else float("nan")
        if pd.isna(middle_value):
            return ""

        close_price = float(bar.close_price)
        if state.direction == "long" and close_price >= middle_value:
            self._close_all_layers_and_set_flat_target(
                state,
                close_price,
                exit_reason="long_boll_middle_exit",
            )
            return "long_boll_middle_exit"
        if state.direction == "short" and close_price <= middle_value:
            self._close_all_layers_and_set_flat_target(
                state,
                close_price,
                exit_reason="short_boll_middle_exit",
            )
            return "short_boll_middle_exit"
        return ""

    def _process_max_holding_exit(self, state: ProductState, bar: BarData) -> str:
        max_days = int(self.max_holding_days or 0)
        if max_days <= 0 or not state.layers or state.bars_since_entry < max_days:
            return ""

        exit_reason = f"{state.direction}_boll_time_exit"
        self._close_all_layers_and_set_flat_target(
            state,
            float(bar.close_price),
            exit_reason=exit_reason,
        )
        return exit_reason

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
