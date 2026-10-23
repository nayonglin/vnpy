"""Fixed original19 weekly 3MA MACD ablation; existing strategy bytes stay frozen."""
import numpy as np
import pandas as pd
import talib
from stage008_three_ma import three_ma_weekly_strategy_class,_observed_history


def no_macd_weekly_strategy_class(base,weeks):
    wrapped=three_ma_weekly_strategy_class(base,weeks)
    class NoMacdThreeMaWeeklyIndicatorsStrategy(wrapped):
        research_macd_disabled=True
        research_macd_call_attempts=0
        def _calculate_macd(self,close):
            self.research_macd_call_attempts+=1
            raise RuntimeError('MACD calculation forbidden in declared no-MACD model')

        def _generate_signal(self, am, history):
            history = _observed_history(am, history)
            if len(history) < max(self.ma_short, self.ma_mid, self.ma_long) + 1:
                return self._signal_result(
                    '', False, False, float('nan'), float('nan'),
                    float('nan'), float('nan'), 'regular', False,
                )
            close = pd.Series(history['close'].to_numpy(dtype='float64'))
            ma_short = close.rolling(self.ma_short).mean()
            ma_mid = close.rolling(self.ma_mid).mean()
            ma_long = close.rolling(self.ma_long).mean()
            # am.rsi() would still consume the unused zero prefix before count=41.
            rsi_value = float(talib.RSI(close.to_numpy(), timeperiod=self.rsi_length)[-1])

            breakout_up = False
            breakout_down = False
            if len(history) >= self.donchian_entry_period + 1:
                entry_source = history.iloc[:-1].tail(self.donchian_entry_period)
                upper = float(entry_source['high'].max())
                lower = float(entry_source['low'].min())
                close_last = float(history['close'].iloc[-1])
                breakout_up = close_last > upper
                breakout_down = close_last < lower

            required_values = [
                ma_short.iloc[-1], ma_mid.iloc[-1], ma_long.iloc[-1],
                ma_short.iloc[-2], ma_mid.iloc[-2], ma_long.iloc[-2],
            ]
            if any(pd.isna(value) for value in required_values):
                return self._signal_result(
                    '', False, False, float('nan'), float('nan'),
                    float('nan'), float('nan'), 'regular', False,
                )

            short_y, short_t = float(ma_short.iloc[-2]), float(ma_short.iloc[-1])
            mid_y, mid_t = float(ma_mid.iloc[-2]), float(ma_mid.iloc[-1])
            long_y, long_t = float(ma_long.iloc[-2]), float(ma_long.iloc[-1])
            golden_5_10 = short_y <= mid_y and short_t > mid_t
            death_5_10 = short_y >= mid_y and short_t < mid_t
            golden_10_20 = mid_y <= long_y and mid_t > long_t
            death_10_20 = mid_y >= long_y and mid_t < long_t
            bullish_alignment = short_t > mid_t > long_t
            bearish_alignment = short_t < mid_t < long_t
            allow_long = True
            allow_short = True
            if self.enable_rsi_filter:
                allow_long = allow_long and rsi_value <= self.rsi_long_max
                allow_short = allow_short and rsi_value >= self.rsi_short_min

            signal = ''
            risk_mode = 'regular'
            breakout = False
            if (golden_5_10 or death_5_10) and not (golden_10_20 or death_10_20):
                if golden_5_10 and bullish_alignment and allow_long:
                    signal, breakout = 'long_case1a', breakout_up
                elif death_5_10 and bearish_alignment and allow_short:
                    signal, breakout = 'short_case1a', breakout_down
            elif golden_10_20 or death_10_20:
                if golden_10_20 and bullish_alignment and allow_long:
                    signal, breakout = 'long_case2', breakout_up
                elif death_10_20 and bearish_alignment and allow_short:
                    signal, breakout = 'short_case2', breakout_down

            if signal and not self._passes_entry_filters(signal, history):
                signal, risk_mode, breakout = '', 'regular', False
            if signal:
                volume_oi_risk_mode = self._volume_open_interest_risk_mode(history)
                if volume_oi_risk_mode:
                    risk_mode = volume_oi_risk_mode
                else:
                    open_interest_risk_mode = self._open_interest_risk_mode(history)
                    if open_interest_risk_mode:
                        risk_mode = open_interest_risk_mode
            # Keep alignment/RSI available for daily risk management without
            # replaying the same week's crossover as another fresh signal.
            if not am.fresh:
                signal, breakout = '', False
            return self._signal_result(
                signal, bullish_alignment, bearish_alignment,
                float(ma_mid.iloc[-1]), float(ma_long.iloc[-1]),
                float(ma_long.iloc[-2]), float(ma_mid.iloc[-2]),
                risk_mode, breakout, rsi_value,
            )

        def _rollover_shape_continuation_snapshot(self, old_direction, history):
            close = pd.to_numeric(history.get('close', pd.Series(dtype='float64')), errors='coerce')
            close = close.replace([np.inf, -np.inf], np.nan).dropna().astype('float64')
            required_bar_count = max(self.ma_short, self.ma_mid, self.ma_long)
            snapshot = dict(
                observed_bar_count=int(len(close)), required_bar_count=int(required_bar_count),
                bullish_alignment=0, bearish_alignment=0,
                ma_short_value=float('nan'), ma_mid_value=float('nan'),
                ma_long_value=float('nan'),
                # Schema compatibility only; no MA40 is read or calculated.
                ma_extra_long_value=float('nan'),
                macd_hist=float('nan'), allowed=0, reason='insufficient_indicator_history',
            )
            if len(close) < required_bar_count:
                return snapshot
            ma_short = float(close.tail(self.ma_short).mean())
            ma_mid = float(close.tail(self.ma_mid).mean())
            ma_long = float(close.tail(self.ma_long).mean())
            if not all(np.isfinite(value) for value in [ma_short, ma_mid, ma_long]):
                snapshot['reason'] = 'non_finite_indicator'
                return snapshot
            bullish_alignment = ma_short > ma_mid > ma_long
            bearish_alignment = ma_short < ma_mid < ma_long
            snapshot.update(
                bullish_alignment=int(bullish_alignment), bearish_alignment=int(bearish_alignment),
                ma_short_value=ma_short, ma_mid_value=ma_mid, ma_long_value=ma_long,
            )
            if old_direction == 'long':
                allowed = bool(self.long_entry_enabled and bullish_alignment)
            elif old_direction == 'short':
                allowed = bool(self.short_entry_enabled and bearish_alignment)
            else:
                snapshot['reason'] = 'unsupported_direction'
                return snapshot
            snapshot['allowed'] = int(allowed)
            snapshot['reason'] = 'shape_aligned' if allowed else 'shape_not_aligned'
            return snapshot

        def _rollover_reopen_allowed(self,old_direction,history,signal_data):
            bullish_alignment=bool(signal_data.get('bullish_alignment'))
            bearish_alignment=bool(signal_data.get('bearish_alignment'))
            synthetic_signal='long_rollover' if old_direction=='long' else 'short_rollover'
            if old_direction=='long':
                allowed=bool(self.long_entry_enabled and bullish_alignment)
            else:
                allowed=bool(self.short_entry_enabled and bearish_alignment)
            if not allowed:return False
            return self._passes_entry_filters(synthetic_signal,history)
    return NoMacdThreeMaWeeklyIndicatorsStrategy
