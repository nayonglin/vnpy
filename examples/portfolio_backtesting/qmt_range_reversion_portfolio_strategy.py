from __future__ import annotations

from typing import Any

import pandas as pd

from vnpy.trader.object import BarData
from vnpy.trader.utility import ArrayManager

from qmt_boll_reversal_portfolio_strategy import QmtBollReversalPortfolioStrategy
from qmt_roll_portfolio_strategy import ProductState


class QmtRangeReversionPortfolioStrategy(QmtBollReversalPortfolioStrategy):
    """
    Range reversion futures strategy without Bollinger-band entry signals.

    Entry is based on:
    - low trend strength by ADX
    - location near the Donchian channel edge
    - RSI extreme
    - one-bar reversal confirmation
    """

    author: str = "GPT-5.4"

    channel_window: int = 20
    adx_filter_enabled: bool = True
    adx_window: int = 14
    adx_max: float = 25.0
    range_position_long_max: float = 0.25
    range_position_short_min: float = 0.75
    range_rsi_long_max: float = 35.0
    range_rsi_short_min: float = 65.0
    range_entry_mode: str = "hard"
    range_score_threshold: float = 3.0
    range_soft_adx_max: float = 32.0
    range_soft_position_long_max: float = 0.35
    range_soft_position_short_min: float = 0.65
    range_soft_rsi_long_max: float = 45.0
    range_soft_rsi_short_min: float = 55.0
    range_signal_style: str = "reversion"
    range_efficiency_filter_enabled: bool = False
    range_efficiency_window: int = 20
    range_efficiency_max: float = 0.35
    range_intraday_stop_enabled: bool = False
    range_intraday_stop_gap_open_enabled: bool = True
    exit_on_channel_middle_touch: bool = True
    range_previous_day_stop_long_enabled: bool = True
    range_previous_day_stop_short_enabled: bool = True

    parameters: list[str] = QmtBollReversalPortfolioStrategy.parameters + [
        "channel_window",
        "adx_filter_enabled",
        "adx_window",
        "adx_max",
        "range_position_long_max",
        "range_position_short_min",
        "range_rsi_long_max",
        "range_rsi_short_min",
        "range_entry_mode",
        "range_score_threshold",
        "range_soft_adx_max",
        "range_soft_position_long_max",
        "range_soft_position_short_min",
        "range_soft_rsi_long_max",
        "range_soft_rsi_short_min",
        "range_signal_style",
        "range_efficiency_filter_enabled",
        "range_efficiency_window",
        "range_efficiency_max",
        "range_intraday_stop_enabled",
        "range_intraday_stop_gap_open_enabled",
        "exit_on_channel_middle_touch",
        "range_previous_day_stop_long_enabled",
        "range_previous_day_stop_short_enabled",
    ]

    def _generate_signal(self, am: ArrayManager, history: pd.DataFrame) -> dict[str, Any]:
        close = pd.Series(am.close_array, dtype="float64")
        high = pd.Series(am.high_array, dtype="float64")
        low = pd.Series(am.low_array, dtype="float64")

        ma_short = close.rolling(self.ma_short).mean()
        ma_mid = close.rolling(self.ma_mid).mean()
        ma_long = close.rolling(self.ma_long).mean()
        ma_extra_long = close.rolling(self.ma_extra_long).mean()

        channel_window = max(2, int(self.channel_window))
        channel_high = high.rolling(channel_window).max()
        channel_low = low.rolling(channel_window).min()
        channel_width = channel_high - channel_low
        rsi_value = float(am.rsi(int(self.rsi_length)))
        adx = self._rolling_adx(high, low, close, int(self.adx_window))
        entry_mode = str(self.range_entry_mode or "hard").strip().lower()
        use_score_entry = entry_mode in {"score", "scoring", "soft", "soft_score"}
        efficiency_window = max(2, int(self.range_efficiency_window))
        path_length = close.diff().abs().rolling(efficiency_window).sum()
        if len(close) > efficiency_window:
            range_efficiency = abs(float(close.iloc[-1]) - float(close.iloc[-efficiency_window - 1]))
            range_efficiency /= max(float(path_length.iloc[-1]), 1e-12)
        else:
            range_efficiency = float("nan")

        required_values = [
            ma_short.iloc[-1],
            ma_mid.iloc[-1],
            ma_long.iloc[-1],
            ma_extra_long.iloc[-1],
            ma_short.iloc[-2],
            ma_mid.iloc[-2],
            ma_long.iloc[-2],
            ma_extra_long.iloc[-2],
            channel_high.iloc[-1],
            channel_low.iloc[-1],
            channel_width.iloc[-1],
            close.iloc[-1],
            close.iloc[-2],
            rsi_value,
        ]
        if self.adx_filter_enabled or use_score_entry:
            required_values.append(adx.iloc[-1])
        if self.range_efficiency_filter_enabled:
            required_values.append(range_efficiency)
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
                float("nan"),
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

        close_t = float(close.iloc[-1])
        close_y = float(close.iloc[-2])
        width_t = max(float(channel_width.iloc[-1]), 1e-12)
        range_position = (close_t - float(channel_low.iloc[-1])) / width_t
        adx_t = float(adx.iloc[-1]) if self.adx_filter_enabled or use_score_entry else 0.0
        signal_style = str(self.range_signal_style or "reversion").strip().lower()
        use_continuation_signal = signal_style in {"continuation", "breakout", "momentum"}
        range_regime_ok = (
            not self.range_efficiency_filter_enabled
            or range_efficiency <= float(self.range_efficiency_max)
        )

        if use_score_entry:
            low_trend_strength = (not self.adx_filter_enabled) or adx_t <= float(self.range_soft_adx_max)
            long_score = float(low_trend_strength)
            short_score = float(low_trend_strength)

            if use_continuation_signal:
                long_score += float(range_position >= float(self.range_soft_position_short_min))
                long_score += float(rsi_value >= float(self.range_soft_rsi_short_min))
                long_score += float(close_t > close_y)

                short_score += float(range_position <= float(self.range_soft_position_long_max))
                short_score += float(rsi_value <= float(self.range_soft_rsi_long_max))
                short_score += float(close_t < close_y)
            else:
                long_score += float(range_position <= float(self.range_soft_position_long_max))
                long_score += float(rsi_value <= float(self.range_soft_rsi_long_max))
                long_score += float(close_t > close_y)

                short_score += float(range_position >= float(self.range_soft_position_short_min))
                short_score += float(rsi_value >= float(self.range_soft_rsi_short_min))
                short_score += float(close_t < close_y)

            score_threshold = float(self.range_score_threshold)
            long_setup = (
                self.long_entry_enabled
                and range_regime_ok
                and not bearish_alignment
                and long_score >= score_threshold
            )
            short_setup = (
                self.short_entry_enabled
                and range_regime_ok
                and not bullish_alignment
                and short_score >= score_threshold
            )
        else:
            low_trend_strength = (not self.adx_filter_enabled) or adx_t <= float(self.adx_max)
            if use_continuation_signal:
                long_setup = (
                    self.long_entry_enabled
                    and range_regime_ok
                    and low_trend_strength
                    and range_position >= float(self.range_position_short_min)
                    and rsi_value >= float(self.range_rsi_short_min)
                    and close_t > close_y
                    and not bearish_alignment
                )
                short_setup = (
                    self.short_entry_enabled
                    and range_regime_ok
                    and low_trend_strength
                    and range_position <= float(self.range_position_long_max)
                    and rsi_value <= float(self.range_rsi_long_max)
                    and close_t < close_y
                    and not bullish_alignment
                )
            else:
                long_setup = (
                    self.long_entry_enabled
                    and range_regime_ok
                    and low_trend_strength
                    and range_position <= float(self.range_position_long_max)
                    and rsi_value <= float(self.range_rsi_long_max)
                    and close_t > close_y
                    and not bearish_alignment
                )
                short_setup = (
                    self.short_entry_enabled
                    and range_regime_ok
                    and low_trend_strength
                    and range_position >= float(self.range_position_short_min)
                    and rsi_value >= float(self.range_rsi_short_min)
                    and close_t < close_y
                    and not bullish_alignment
                )

        signal = ""
        if short_setup and long_setup:
            long_edge = max(0.0, float(self.range_soft_position_long_max) - range_position)
            long_edge += max(0.0, float(self.range_soft_rsi_long_max) - rsi_value) / 100.0
            short_edge = max(0.0, range_position - float(self.range_soft_position_short_min))
            short_edge += max(0.0, rsi_value - float(self.range_soft_rsi_short_min)) / 100.0
            if short_edge > long_edge:
                signal = "short_reversal"
            elif long_edge > short_edge:
                signal = "long_reversal"
        elif short_setup:
            signal = "short_reversal"
        elif long_setup:
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
            rsi_value,
        )

    def _stop_triggered(self, direction: str, bar: BarData, stop_price: float) -> bool:
        if not self.range_intraday_stop_enabled:
            return super()._stop_triggered(direction, bar, stop_price)

        if stop_price <= 0:
            return False
        if direction == "long":
            return float(bar.low_price) <= stop_price
        return float(bar.high_price) >= stop_price

    def _stop_execution_price(self, direction: str, bar: BarData, stop_price: float) -> float:
        if not self.range_intraday_stop_enabled:
            return super()._stop_execution_price(direction, bar, stop_price)

        open_price = float(getattr(bar, "open_price", bar.close_price))
        if pd.isna(open_price) or open_price <= 0:
            open_price = float(bar.close_price)

        if self.range_intraday_stop_gap_open_enabled:
            if direction == "long" and open_price <= stop_price:
                return open_price
            if direction == "short" and open_price >= stop_price:
                return open_price
        return float(stop_price)

    def _update_dynamic_stops(self, state: ProductState, bar: BarData, history: pd.DataFrame) -> None:
        for layer in state.layers:
            self._update_layer_metrics(layer, bar)

        if not self.previous_day_stop_enabled or len(history) < 2:
            return

        prev_day = history.iloc[-2]
        if state.direction == "long":
            if not self.range_previous_day_stop_long_enabled:
                return
            stop_price = float(prev_day["low"])
            for layer in state.layers:
                layer.stop_price = max(layer.stop_price, stop_price)
        else:
            if not self.range_previous_day_stop_short_enabled:
                return
            stop_price = float(prev_day["high"])
            for layer in state.layers:
                layer.stop_price = min(layer.stop_price, stop_price)

    def _process_boll_middle_exit(self, state: ProductState, bar: BarData) -> str:
        if not self.exit_on_channel_middle_touch or not state.contract_vt_symbol:
            return ""

        am = self.ams.get(state.contract_vt_symbol)
        if am is None or not am.inited:
            return ""

        history = self._build_history_df(am)
        window = max(2, int(self.channel_window))
        if len(history) < window:
            return ""

        channel_high = history["high"].rolling(window).max()
        channel_low = history["low"].rolling(window).min()
        middle_value = float(((channel_high + channel_low) / 2.0).iloc[-1])
        if pd.isna(middle_value):
            return ""

        close_price = float(bar.close_price)
        if state.direction == "long" and close_price >= middle_value:
            self._close_all_layers_and_set_flat_target(
                state,
                close_price,
                exit_reason="long_channel_middle_exit",
            )
            return "long_channel_middle_exit"
        if state.direction == "short" and close_price <= middle_value:
            self._close_all_layers_and_set_flat_target(
                state,
                close_price,
                exit_reason="short_channel_middle_exit",
            )
            return "short_channel_middle_exit"
        return ""

    @staticmethod
    def _rolling_adx(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        window: int,
    ) -> pd.Series:
        window = max(2, int(window))
        high = high.astype("float64")
        low = low.astype("float64")
        close = close.astype("float64")

        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = up_move.where((up_move > down_move) & (up_move > 0.0), 0.0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0.0), 0.0)

        prev_close = close.shift(1)
        true_range = pd.concat(
            [
                high - low,
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        tr_sum = true_range.rolling(window).sum()
        plus_di = 100.0 * plus_dm.rolling(window).sum() / tr_sum
        minus_di = 100.0 * minus_dm.rolling(window).sum() / tr_sum
        dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        return dx.rolling(window).mean()
