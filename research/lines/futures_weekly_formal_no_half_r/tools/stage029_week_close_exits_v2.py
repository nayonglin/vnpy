"""Predeclared v2: reject only a finite positive weekly stop on the wrong side.

Frozen v1 price formulas and hard admission gates remain intact. A rejected
candidate never reaches budget sizing, target mutation or margin reservation.
"""
from copy import deepcopy
import math
import pandas as pd
from stage029_week_close_exits import (
    week_close_exit_strategy_class as _v1_factory,
    audit_week_close_exits as _v1_audit,
    _day,
)


def _direction(value):
    value = str(getattr(value, 'value', value)).lower()
    return {'多': 'long', 'direction.long': 'long', '空': 'short',
            'direction.short': 'short'}.get(value, value)


def _is_open(value):
    return str(getattr(value, 'value', value)).lower() in {'open', 'offset.open', '开'}


def week_close_exit_strategy_class(base, weeks):
    wrapped = _v1_factory(base, weeks)
    formal_entry_stop = base._entry_stop_price

    class WeekCloseExitStrategyV2(wrapped):
        research_invalid_weekly_stop_admission_version = 2

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.invalid_weekly_stop_rejections = []

        def on_bars(self, bars):
            try:
                return super().on_bars(bars)
            except Exception as exc:
                # vn.py catches daily callbacks; preserve their original cause
                # for the strict engine's post-loop failure check, then rethrow.
                self.strategy_engine.intraday_execution_failure = f'{type(exc).__name__}: {exc!r}'
                raise

        def _weekly_initial_stop_qualification(self, vt_symbol, direction, bar):
            if str(vt_symbol) != str(bar.vt_symbol):
                self._week_stop_fail('initial_stop_contract_mismatch', vt_symbol=str(vt_symbol))
            if direction not in {'long', 'short'}:
                self._week_stop_fail('unknown_weekly_stop_direction', vt_symbol=str(vt_symbol), direction=direction)
            reference = float(bar.close_price)
            if not math.isfinite(reference) or reference <= 0:
                self._week_stop_fail('invalid_plan_reference_price', vt_symbol=str(vt_symbol),
                    date=_day(bar.datetime), plan_reference_close=reference)
            weekly, am, context = self._completed_week_context(bar, 'initial_stop_qualification_v2')
            # Stage804's formula logs a sizing adjustment. Qualification must
            # not duplicate that log before the original valid sizing call.
            has_diagnostics = hasattr(self, 'trade_event_diagnostics')
            diagnostics = getattr(self, 'trade_event_diagnostics', None)
            try:
                if has_diagnostics:
                    self.trade_event_diagnostics = None
                stop = float(formal_entry_stop(self, direction, weekly, self._build_history_df(am), True))
            finally:
                if has_diagnostics:
                    self.trade_event_diagnostics = diagnostics
            if not math.isfinite(stop) or stop <= 0:
                self._week_stop_fail('invalid_weekly_initial_stop', vt_symbol=str(vt_symbol),
                    date=context['date'], week_end=context['week_end'], stop_price=stop)
            valid = stop < reference if direction == 'long' else stop > reference
            return stop, valid, context

        def _admission_ownership_snapshot(self, vt_symbol):
            return dict(target=self.get_target(vt_symbol),
                pending_margin_reservation=float(self.pending_margin_reservation),
                pending_cluster_margin_reservation=deepcopy(self.pending_cluster_margin_reservation),
                pending_active_products=sorted(self.pending_active_products))

        def _calculate_entry_sizing(self, vt_symbol, direction, bar, history, signal_data,
                risk_mode_override=None, entry_context='flat_entry', apply_env_gate=True,
                active_positions_before=None, correlation_snapshot=None):
            before = self._admission_ownership_snapshot(vt_symbol)
            stop, valid, context = self._weekly_initial_stop_qualification(vt_symbol, direction, bar)
            if valid:
                # Return the parent's whole result unchanged, including every
                # capital, broker, correlation, heat, environment and risk gate.
                return super()._calculate_entry_sizing(vt_symbol, direction, bar, history, signal_data,
                    risk_mode_override=risk_mode_override, entry_context=entry_context,
                    apply_env_gate=apply_env_gate, active_positions_before=active_positions_before,
                    correlation_snapshot=correlation_snapshot)
            reference = float(bar.close_price)
            size = int(self.get_size(vt_symbol))
            margin_ratio = float(self._margin_ratio_for_symbol(vt_symbol))
            if size <= 0 or not math.isfinite(margin_ratio) or margin_ratio <= 0:
                self._week_stop_fail('invalid_rejection_contract_metadata', vt_symbol=str(vt_symbol))
            snapshot = dict(
                risk_mode=risk_mode_override or str(signal_data.get('risk_mode', 'regular')),
                entry_context=entry_context, selected_volume=0, stop_price=stop,
                plan_reference_close=reference, weekly_stop_week_end=context['week_end'],
                signed_stop_distance=(reference-stop if direction=='long' else stop-reference),
                direction_valid=False, sizing_method='invalid_weekly_stop_rejection_v2',
                rejection_reason='invalid_weekly_stop_direction', budget_evaluation='not_evaluated',
                budget_not_evaluated_fields=['risk_amount', 'margin_capacity', 'single_trade_cap',
                    'cluster_cap', 'heat_gate', 'env_gate', 'incremental_margin_budget', 'recovery_sleeve'],
                risk_ratio=None, risk_amount=None, risk_amount_before_directional_30d_boost=None,
                limited_balance=None, allowed_capital=None, single_trade_capital_limit=None,
                free_capital=None, reserved_margin_before=self._reserved_margin_in_use(),
                risk_per_contract=0.0, risk_per_contract_evaluation='not_evaluated',
                margin_ratio=margin_ratio, margin_per_contract=reference*size*margin_ratio,
                contracts_by_risk=None, contracts_by_margin=None, contracts_by_single_trade_cap=None,
                risk_multiplier=None, effective_capital_usage_ratio=None,
                effective_max_concurrent_positions=self.max_concurrent_positions,
                sizing_equity=None, effective_sizing_equity_cap=None,
                incremental_margin_budget_gate_passed=None,
                rollover_reopen_drawdown_guard_passed=None,
            )
            after = self._admission_ownership_snapshot(vt_symbol)
            rejection = {**context, 'signal_date': context['date'], 'direction': direction,
                'entry_context': entry_context, 'signal': str(signal_data.get('signal', '')),
                'stop_price': stop, 'selected_volume': 0, 'direction_valid': False,
                'reason': 'invalid_weekly_stop_direction', 'budget_evaluation': 'not_evaluated',
                'ownership_before': before, 'ownership_after': after,
                'new_target_added': after['target'] != before['target'],
                'new_reservation_added': after != before, 'sizing_snapshot': deepcopy(snapshot)}
            self.invalid_weekly_stop_rejections.append(rejection)
            return snapshot

    return WeekCloseExitStrategyV2


def _select_context_rows(frames, rejection):
    context = rejection['entry_context']
    if context in {'flat_entry', 'env_probe'}:
        name = 'entry_candidates'
        frame = frames.get(name)
        required = {'date', 'contract_vt_symbol', 'direction', 'entry_context', 'candidate_status', 'selected_volume'}
        symbol_column = 'contract_vt_symbol'
    elif context == 'rollover_reopen':
        name = 'rollover_shape_same_volume'
        frame = frames.get(name)
        required = {'date', 'target_contract_vt_symbol', 'direction', 'final_volume', 'status'}
        symbol_column = 'target_contract_vt_symbol'
    else:
        raise ValueError('rejection_evidence_unknown_entry_context:' + context)
    if not isinstance(frame, pd.DataFrame) or not required.issubset(frame.columns):
        raise ValueError('rejection_evidence_missing:' + name)
    mask = (frame['date'].map(_day).eq(rejection['signal_date']) &
        frame[symbol_column].astype(str).eq(rejection['vt_symbol']) &
        frame['direction'].map(_direction).eq(rejection['direction']))
    if 'entry_context' in required:
        mask &= frame['entry_context'].astype(str).eq('flat_entry' if context=='env_probe' else context)
    selected = frame.loc[mask]
    if selected.empty:
        raise ValueError('rejection_evidence_missing:' + name + ':' + rejection['signal_date'])
    if context in {'flat_entry', 'env_probe'}:
        opened = (selected['candidate_status'].astype(str).eq('opened') |
            pd.to_numeric(selected['selected_volume'], errors='raise').ne(0))
    else:
        opened = (selected['status'].astype(str).eq('targeted') |
            pd.to_numeric(selected['final_volume'], errors='raise').ne(0))
        if 'selected_volume_before_exact_gate' in selected:
            opened |= pd.to_numeric(selected['selected_volume_before_exact_gate'], errors='raise').ne(0)
    if opened.any():
        raise ValueError('rejected_candidate_opened:' + name)
    return len(selected)


def _positive_contexts(frames, day, symbol, direction):
    contexts = set()
    candidates = frames.get('entry_candidates')
    if isinstance(candidates, pd.DataFrame) and not candidates.empty:
        required = {'date', 'contract_vt_symbol', 'direction', 'entry_context', 'candidate_status'}
        if not required.issubset(candidates.columns):
            raise ValueError('rejection_execution_context_schema_missing')
        rows = candidates.loc[candidates['date'].map(_day).eq(day) &
            candidates['contract_vt_symbol'].astype(str).eq(symbol) &
            candidates['direction'].map(_direction).eq(direction) &
            candidates['candidate_status'].astype(str).eq('opened')]
        contexts.update(rows['entry_context'].astype(str))
    roll = frames.get('rollover_shape_same_volume')
    if isinstance(roll, pd.DataFrame) and not roll.empty:
        required = {'date', 'target_contract_vt_symbol', 'direction', 'final_volume', 'status'}
        if not required.issubset(roll.columns):
            raise ValueError('rejection_execution_context_schema_missing')
        rows = roll.loc[roll['date'].map(_day).eq(day) &
            roll['target_contract_vt_symbol'].astype(str).eq(symbol) &
            roll['direction'].map(_direction).eq(direction) &
            pd.to_numeric(roll['final_volume'], errors='raise').gt(0) & roll['status'].eq('targeted')]
        if not rows.empty:
            contexts.add('rollover_reopen')
    return contexts


def audit_week_close_exits(strategy, frames=None):
    result = _v1_audit(strategy, frames)
    rejects = strategy.invalid_weekly_stop_rejections
    frames = {} if frames is None else frames
    matches = 0
    for rejection in rejects:
        stop, reference = float(rejection['stop_price']), float(rejection['plan_reference_close'])
        direction = rejection['direction']
        wrong_side = ((direction=='long' and stop>=reference) or
                      (direction=='short' and stop<=reference))
        if (not math.isfinite(stop) or stop<=0 or not math.isfinite(reference) or reference<=0
                or not wrong_side or rejection['week_end']>rejection['signal_date']):
            raise ValueError('invalid_weekly_stop_rejection_receipt')
        snapshot = rejection['sizing_snapshot']
        if (snapshot['stop_price']!=stop or snapshot['selected_volume']!=0 or
                snapshot['plan_reference_close']!=reference or snapshot['budget_evaluation']!='not_evaluated'):
            raise ValueError('invalid_weekly_stop_rejection_snapshot')
        if (rejection['selected_volume'] != 0 or rejection['direction_valid'] or
                rejection['budget_evaluation'] != 'not_evaluated'):
            raise ValueError('invalid_weekly_stop_rejection_receipt')
        if rejection['ownership_before'] != rejection['ownership_after'] or rejection['new_target_added'] or rejection['new_reservation_added']:
            raise ValueError('rejected_candidate_mutated_ownership')
        matches += _select_context_rows(frames, rejection)
    if rejects:
        trades, anchors = frames.get('trades'), frames.get('execution_anchor_requests')
        if not isinstance(trades, pd.DataFrame) or not isinstance(anchors, pd.DataFrame):
            raise ValueError('rejection_execution_evidence_missing')
        if not trades.empty:
            if not {'order_id', 'vt_symbol', 'direction', 'offset', 'volume'}.issubset(trades.columns):
                raise ValueError('rejection_execution_trade_schema_missing')
            if not {'order_id', 'signal_date', 'vt_symbol', 'offset'}.issubset(anchors.columns):
                raise ValueError('rejection_execution_anchor_missing')
            open_trades = trades.loc[trades['offset'].map(_is_open) &
                pd.to_numeric(trades['volume'], errors='raise').gt(0)]
            for trade in open_trades.to_dict('records'):
                symbol, direction = str(trade['vt_symbol']), _direction(trade['direction'])
                relevant = [r for r in rejects if r['vt_symbol']==symbol and r['direction']==direction]
                if not relevant:
                    continue
                order_anchors = anchors.loc[anchors['order_id'].astype(str).eq(str(trade['order_id'])) &
                    anchors['vt_symbol'].astype(str).eq(symbol) & anchors['offset'].map(_is_open)]
                days = set(order_anchors['signal_date'].map(_day))
                if len(days) != 1:
                    raise ValueError('rejection_execution_anchor_missing:' + str(trade['order_id']))
                signal_day = next(iter(days))
                matching = [r for r in relevant if r['signal_date']==signal_day]
                if not matching:
                    continue
                contexts = _positive_contexts(frames, signal_day, symbol, direction)
                rejected_contexts = {'flat_entry' if r['entry_context']=='env_probe' else r['entry_context'] for r in matching}
                if not contexts or contexts & rejected_contexts:
                    raise ValueError('rejected_candidate_open_fill:' + str(trade['order_id']))
                if len(contexts) != 1:
                    raise ValueError('rejection_execution_context_ambiguous:' + str(trade['order_id']))
    return {**result, 'admission_version': 2, 'invalid_weekly_stop_rejection_count': len(rejects),
        'rejection_context_match_count': matches, 'rejected_candidate_open_fill_count': 0,
        'rejection_match_scope': 'signal_date_contract_direction_entry_context'}
