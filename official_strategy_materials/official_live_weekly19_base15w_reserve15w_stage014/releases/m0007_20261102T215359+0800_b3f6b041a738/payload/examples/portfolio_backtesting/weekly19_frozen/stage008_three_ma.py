"""Stage008: MA5/10/20 completed weeks; 41-bar storage and 21-bar readiness.

This isolated adapter removes MA40 decisions only.  MACD, RSI, all inherited
risk modules and execution stay in the formal base.  An unknown signal-method
MRO is rejected rather than silently bypassing another module's entry filter.
"""
import numpy as np
import pandas as pd
import talib

from .qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
from .weekly_adapter import WeeklyArrayManager


class ThreeMaWeeklyArrayManager(WeeklyArrayManager):
    ready_need = 21

    def __init__(self, inner, weeks):
        if int(inner.size) != 41:
            raise ValueError('stage008_storage_capacity_must_remain_41')
        super().__init__(inner, weeks)

    @property
    def inited(self):
        return int(self.inner.count) >= self.ready_need


def _observed_history(am, history):
    count = min(max(0, int(getattr(am, 'count', 0) or 0)), len(history))
    return history.tail(count).reset_index(drop=True)


def three_ma_weekly_strategy_class(base, weeks):
    if getattr(base, '_generate_signal', None) is not QmtRollPortfolioStrategy._generate_signal:
        raise ValueError('stage008_unknown_generate_signal_mro')

    class ThreeMaWeeklyIndicatorsStrategy(base):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.ams = {
                symbol: ThreeMaWeeklyArrayManager(am, weeks)
                for symbol, am in self.ams.items()
            }
            self.weekly_readiness = []

        def on_bars(self, bars):
            result = super().on_bars(bars)
            day = next(iter(bars.values())).datetime.strftime('%Y-%m-%d') if bars else ''
            if day >= '2020-01-01':
                targets = self.daily_mapping.get(day, {})
                self.weekly_readiness.append(dict(
                    date=day,
                    mapped_products=len(targets),
                    ready_target_contracts=sum(
                        bool(self.ams.get(symbol) and self.ams[symbol].inited)
                        for symbol in targets.values()
                    ),
                    newly_completed_targets=sum(
                        bool(self.ams.get(symbol) and self.ams[symbol].fresh)
                        for symbol in targets.values()
                    ),
                ))
            return result

        def _build_history_df(self, am):
            return _observed_history(am, super()._build_history_df(am))

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
            dif, dea, hist = self._calculate_macd(close)

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
                dif.iloc[-1], dif.iloc[-2], dea.iloc[-1], dea.iloc[-2], hist.iloc[-1],
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
            macd_hist_t = float(hist.iloc[-1])
            macd_golden = float(dif.iloc[-2]) <= float(dea.iloc[-2]) and float(dif.iloc[-1]) > float(dea.iloc[-1])
            macd_death = float(dif.iloc[-2]) >= float(dea.iloc[-2]) and float(dif.iloc[-1]) < float(dea.iloc[-1])
            allow_long = macd_hist_t > 0
            allow_short = macd_hist_t < 0
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
            else:
                if macd_golden and bullish_alignment and allow_long:
                    signal, breakout = 'long_case3', breakout_up
                elif macd_death and bearish_alignment and allow_short:
                    signal, breakout = 'short_case3', breakout_down

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

        def _is_simple_ma_trend(self, market_data_df, direction, slope_lookback=3):
            try:
                if market_data_df is None:
                    return False
                need = int(self.ma_long) + int(slope_lookback) + 2
                if len(market_data_df) < need:
                    return False
                close = market_data_df['close']
                close_last = float(close.iloc[-1])
                ma_short = float(close.rolling(int(self.ma_short)).mean().iloc[-1])
                ma_mid = float(close.rolling(int(self.ma_mid)).mean().iloc[-1])
                ma_long = float(close.rolling(int(self.ma_long)).mean().iloc[-1])
                ma_long_prev = float(close.rolling(int(self.ma_long)).mean().iloc[-1-int(slope_lookback)])
                if direction == 'long':
                    return ma_short > ma_mid > ma_long and ma_long > ma_long_prev and close_last > ma_long
                if direction == 'short':
                    return ma_short < ma_mid < ma_long and ma_long < ma_long_prev and close_last < ma_long
                return False
            except Exception:
                return False

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
            _, _, hist = self._calculate_macd(close)
            macd_hist = float(hist.iloc[-1]) if not hist.empty else float('nan')
            if not all(np.isfinite(value) for value in [ma_short, ma_mid, ma_long, macd_hist]):
                snapshot['reason'] = 'non_finite_indicator'
                return snapshot
            bullish_alignment = ma_short > ma_mid > ma_long
            bearish_alignment = ma_short < ma_mid < ma_long
            snapshot.update(
                bullish_alignment=int(bullish_alignment), bearish_alignment=int(bearish_alignment),
                ma_short_value=ma_short, ma_mid_value=ma_mid, ma_long_value=ma_long,
                macd_hist=macd_hist,
            )
            if old_direction == 'long':
                allowed = bool(self.long_entry_enabled and bullish_alignment and macd_hist > 0)
            elif old_direction == 'short':
                allowed = bool(self.short_entry_enabled and bearish_alignment and macd_hist < 0)
            else:
                snapshot['reason'] = 'unsupported_direction'
                return snapshot
            snapshot['allowed'] = int(allowed)
            snapshot['reason'] = 'shape_and_macd_aligned' if allowed else 'shape_or_macd_not_aligned'
            return snapshot

    return ThreeMaWeeklyIndicatorsStrategy
