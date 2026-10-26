"""Stage029 fixed weekly-close technical exits, isolated from daily account risk.

The parent daily loop, actual-price sizing, rollover, ledger and safety wrappers
remain intact. Only completed-week price inputs and technical-exit gates change.
No price or wrong-direction stop is repaired to rescue a replay.
"""
from copy import copy
from datetime import datetime
import math
import pandas as pd
from stage018_short_case2 import short_case2_weekly_strategy_class

LOCKED_CONTRACT = {
    'enable_rsi_partial_exit': False,
    'enable_add_position': False,
    'enable_donchian_add_position': False,
    'enable_post_entry_quality_add': False,
    'reverse_on_opposite_signal': False,
    'exit_on_alignment_break': False,
    'rollover_shape_history_mode': 'target_contract_only',
}


def _day(value):
    return pd.Timestamp(value).strftime('%Y-%m-%d')


def week_close_exit_strategy_class(base, weeks):
    wrapped = short_case2_weekly_strategy_class(base, weeks)

    class WeekCloseExitStrategy(wrapped):
        research_short_case2_enabled = False
        research_week_close_exits_enabled = True

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            for key, value in LOCKED_CONTRACT.items():
                setattr(self, key, value)
            self.weekly_stop_audit = []
            self.initial_stop_audit = []
            self.weekly_stop_guard_failures = []
            self.reconciliation_rebuilt_layer_count = 0

        def _week_stop_fail(self, reason, **details):
            row = dict(reason=reason, **details)
            self.weekly_stop_guard_failures.append(row)
            raise ValueError(reason + ':' + str(details.get('vt_symbol', '')))

        def _require_week_stop_contract(self):
            changed = {key: getattr(self, key, None) for key, value in LOCKED_CONTRACT.items()
                       if getattr(self, key, None) != value}
            if changed:
                self._week_stop_fail('locked_contract_changed', changed=changed)

        def on_bars(self, bars):
            self._require_week_stop_contract()
            return super().on_bars(bars)

        def _can_open_short_signal(self, signal):
            return signal == 'short_case1a'

        def _completed_week_context(self, bar, purpose, fresh_only=False):
            symbol = str(bar.vt_symbol)
            day = _day(bar.datetime)
            requested = getattr(self, 'current_bar_date', None)
            if requested is not None and _day(requested) != day:
                self._week_stop_fail('technical_bar_date_mismatch', vt_symbol=symbol,
                    date=_day(requested), bar_date=day, purpose=purpose)
            am = self.ams.get(symbol)
            inner = getattr(am, 'inner', None)
            completed = getattr(am, 'completed', [])
            if inner is None or int(inner.count) <= 0 or not completed:
                self._week_stop_fail('completed_week_missing', vt_symbol=symbol, date=day, purpose=purpose)
            latest = completed[-1]
            end = str(latest['week_end'])
            if end > day:
                self._week_stop_fail('completed_week_in_future', vt_symbol=symbol, date=day, week_end=end)
            for field in ['open', 'high', 'low', 'close', 'volume', 'open_interest']:
                value = float(latest[field])
                tail = float(getattr(inner, field + '_array')[-1])
                if not math.isfinite(value) or not math.isfinite(tail) or value != tail:
                    self._week_stop_fail('completed_week_inner_mismatch', vt_symbol=symbol,
                        date=day, week_end=end, field=field, completed=value, inner=tail)
            prices = [float(latest[field]) for field in ['open', 'high', 'low', 'close']]
            op, hi, lo, cl = prices
            if not (min(prices) > 0 and hi >= max(op, lo, cl) and lo <= min(op, hi, cl)
                    and float(latest['volume']) > 0):
                self._week_stop_fail('completed_week_invalid_ohlcv', vt_symbol=symbol, date=day, week_end=end)
            fresh = bool(am.fresh and end == day)
            weekly = copy(bar)
            weekly.datetime = datetime.fromisoformat(end)
            for source, target in [('open', 'open_price'), ('high', 'high_price'),
                                   ('low', 'low_price'), ('close', 'close_price'),
                                   ('volume', 'volume'), ('open_interest', 'open_interest')]:
                setattr(weekly, target, float(latest[source]))
            row = dict(date=day, vt_symbol=symbol, purpose=purpose, week_end=end,
                fresh=fresh, weekly_close=cl, weekly_high=hi, weekly_low=lo,
                plan_reference_close=float(bar.close_price),
                inner_count=int(inner.count))
            if fresh_only and not fresh:
                self.weekly_stop_audit.append({**row, 'action': 'skip_not_fresh_week'})
                return None
            return weekly, am, row

        def _entry_stop_price(self, direction, bar, history, use_day_extreme):
            weekly, am, context = self._completed_week_context(bar, 'initial_stop')
            weekly_history = self._build_history_df(am)
            stop = float(super()._entry_stop_price(direction, weekly, weekly_history, use_day_extreme))
            reference = float(bar.close_price)
            valid = bool(math.isfinite(stop) and stop > 0 and math.isfinite(reference) and
                ((direction == 'long' and stop < reference) or
                 (direction == 'short' and stop > reference)))
            self.initial_stop_audit.append({**context, 'direction': direction,
                'stop_price': stop, 'direction_valid': valid,
                'use_day_extreme': bool(use_day_extreme)})
            if not valid:
                self._week_stop_fail('initial_stop_wrong_direction', vt_symbol=str(bar.vt_symbol),
                    date=context['date'], week_end=context['week_end'], direction=direction,
                    stop_price=stop, plan_reference_close=reference, direction_valid=False)
            return stop

        def _open_position(self, state, contract_vt_symbol, direction, volume, bar,
                           signal, history, signal_data, sizing_snapshot=None):
            if str(bar.vt_symbol) != str(contract_vt_symbol):
                self._week_stop_fail('initial_stop_contract_mismatch', vt_symbol=str(bar.vt_symbol))
            expected = self._entry_stop_price(direction, bar, history, True)
            if sizing_snapshot is None:
                sizing_snapshot = self._calculate_entry_sizing(contract_vt_symbol, direction,
                    bar, history, signal_data)
            supplied = float(sizing_snapshot['stop_price'])
            if not math.isclose(supplied, expected, rel_tol=1e-12, abs_tol=1e-12):
                self._week_stop_fail('initial_stop_snapshot_mismatch', vt_symbol=contract_vt_symbol,
                    expected_stop=expected, supplied_stop=supplied)
            weekly, _, _ = self._completed_week_context(bar, 'open_initial_extrema')
            result = super()._open_position(state, contract_vt_symbol, direction, volume,
                bar, signal, history, signal_data, sizing_snapshot=sizing_snapshot)
            for layer in state.layers:
                layer.highest_price = float(weekly.high_price)
                layer.lowest_price = float(weekly.low_price)
            return result

        def _update_dynamic_stops(self, state, bar, history):
            if not state.layers:
                return
            context = self._completed_week_context(bar, 'dynamic_stops', fresh_only=True)
            if context is None:
                return
            weekly, am, row = context
            before = [dict(stop=layer.stop_price, highest=layer.highest_price,
                lowest=layer.lowest_price, max_profit_pct=layer.max_profit_pct) for layer in state.layers]
            result = super()._update_dynamic_stops(state, weekly, self._build_history_df(am))
            after = [dict(stop=layer.stop_price, highest=layer.highest_price,
                lowest=layer.lowest_price, max_profit_pct=layer.max_profit_pct) for layer in state.layers]
            self.weekly_stop_audit.append({**row, 'action': 'update_dynamic_stops',
                'before': before, 'after': after})
            return result

        def _process_prev2day_stop(self, state, bar, history):
            if not self.enable_prev2day_stop or not state.layers:
                return ''
            context = self._completed_week_context(bar, 'prev2week_stop', fresh_only=True)
            if context is None:
                return ''
            weekly, am, row = context
            # completed is append-only across native-symbol epochs; inner.count
            # bounds this list to the currently accepted physical epoch.
            current_epoch = am.completed[-min(int(am.inner.count), len(am.completed)):]
            entry_day = _day(state.entry_date)
            age = sum(str(item['week_end']) > entry_day for item in current_epoch)
            self.weekly_stop_audit.append({**row, 'action': 'prev2week_age',
                'accepted_post_entry_weeks': age, 'entry_date': state.entry_date})
            if age < 2:
                return ''
            daily_age = state.bars_since_entry
            entry_identity = (state.contract_vt_symbol, state.entry_date)
            try:
                state.bars_since_entry = age
                return super()._process_prev2day_stop(state, weekly, self._build_history_df(am))
            finally:
                # A triggered exit resets the state; never restore old age into it.
                if state.layers and (state.contract_vt_symbol, state.entry_date) == entry_identity:
                    state.bars_since_entry = daily_age

        def _process_layer_stops(self, state, bar):
            if not state.layers:
                return ''
            context = self._completed_week_context(bar, 'layer_stops', fresh_only=True)
            if context is None:
                return ''
            return super()._process_layer_stops(state, context[0])

        def _stop_triggered(self, direction, bar, stop_price):
            # Also gates the MA20 path embedded directly in the daily on_bars.
            context = self._completed_week_context(bar, 'close_confirmation', fresh_only=True)
            if context is None:
                return False
            weekly, _, row = context
            triggered = bool(super()._stop_triggered(direction, weekly, stop_price))
            self.weekly_stop_audit.append({**row, 'action': 'close_confirmation',
                'direction': direction, 'stop_price': float(stop_price), 'triggered': triggered})
            return triggered

        def _stop_execution_price(self, direction, bar, stop_price):
            context = self._completed_week_context(bar, 'technical_exit_price', fresh_only=True)
            if context is None:
                self._week_stop_fail('technical_exit_without_fresh_week', vt_symbol=str(bar.vt_symbol), date=_day(bar.datetime))
            return float(super()._stop_execution_price(direction, context[0], stop_price))

        def _reconcile_state_with_position(self, state, current_pos, bar):
            rebuilding = bool(current_pos and not state.layers)
            result = super()._reconcile_state_with_position(state, current_pos, bar)
            if rebuilding and state.layers:
                count = len(state.layers)
                self.reconciliation_rebuilt_layer_count += count
                self.weekly_stop_audit.append(dict(date=_day(bar.datetime), vt_symbol=str(bar.vt_symbol),
                    action='reconciliation_rebuilt_layer', rebuilt_layers=count))
            return result

    return WeekCloseExitStrategy


def audit_week_close_exits(strategy, frames=None):
    """Fail closed on guard receipts, reconstructed daily stops or forbidden events."""
    strategy._require_week_stop_contract()
    if strategy.reconciliation_rebuilt_layer_count:
        raise ValueError('reconciliation_rebuilt_layer')
    if strategy.weekly_stop_guard_failures:
        raise ValueError('weekly_stop_guard_failures')
    if any(not row['direction_valid'] for row in strategy.initial_stop_audit):
        raise ValueError('initial_stop_wrong_direction')
    triggers = [row for row in strategy.weekly_stop_audit if row.get('triggered')]
    if any(not row['fresh'] or row['date'] != row['week_end'] for row in triggers):
        raise ValueError('technical_exit_without_fresh_week')
    frames = {} if frames is None else frames
    forbidden = []
    for name, frame in frames.items():
        if not isinstance(frame, pd.DataFrame):
            continue
        for column in ['reason', 'exit_reason']:
            if column in frame:
                mask = frame[column].fillna('').astype(str).str.contains('rsi_partial_exit', regex=False)
                if mask.any(): forbidden.append(name + ':' + column)
        if 'signal' in frame:
            signal = frame['signal'].fillna('').astype(str)
            if 'offset' in frame:
                offset = frame['offset'].map(lambda value: str(getattr(value, 'value', value)).lower())
                opened = offset.isin({'open', 'offset.open', '开'})
            elif 'candidate_status' in frame:
                opened = frame['candidate_status'].astype(str).eq('opened')
            elif 'is_opened' in frame:
                opened = pd.to_numeric(frame['is_opened'], errors='coerce').eq(1)
            else:
                continue
            if ((signal == 'short_case2') & opened).any(): forbidden.append(name + ':short_case2_open')
    if forbidden:
        raise ValueError('forbidden_week_close_events:' + ','.join(forbidden))
    return dict(accepted=True, initial_stop_contexts=len(strategy.initial_stop_audit),
        weekly_stop_audit_rows=len(strategy.weekly_stop_audit),
        price_technical_trigger_count=len(triggers),
        reconciliation_rebuilt_layer_count=strategy.reconciliation_rebuilt_layer_count,
        weekly_stop_guard_failure_count=len(strategy.weekly_stop_guard_failures),
        rsi_exit_enabled=bool(strategy.enable_rsi_partial_exit),
        short_case2_enabled=bool(strategy.research_short_case2_enabled))
