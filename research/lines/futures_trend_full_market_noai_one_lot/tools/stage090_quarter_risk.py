"""Fixed 0.25% marked-total-equity currency risk, cooperative native quantity gates.

This research policy replaces native currency min/max, risk-mode ratios and risk
money multipliers. It does not revive a quantity rejected by native gates. Opens
are all-or-none against a frozen signal receipt and the causal opening equity.
"""
from dataclasses import asdict, dataclass, is_dataclass
from decimal import Decimal, ROUND_FLOOR
import json
import math
from numbers import Real
from pathlib import Path

import pandas as pd
from vnpy.trader.constant import Direction, Offset
from stage003_candidate import FullMarketNoAIOneLot, candidate_overrides as baseline_overrides

RISK_FRACTION = .0025
UNBOUNDED_POSITION_SIZE = 2147483647  # technical integer sentinel, not an economic cap
ACTIVE_CURRENCY_FORMULA = 'finite_positive_estimated_equity * 0.0025; no floor/cap/multiplier/free-balance fallback'


def number(value):
    if isinstance(value, bool):
        return float('nan')
    try:
        return float(value)
    except (ValueError, TypeError, OverflowError):
        return float('nan')


def fractional_budget(equity):
    equity = number(equity)
    return float(Decimal(str(equity)) * Decimal('0.0025')) if math.isfinite(equity) and equity > 0 else 0.


def whole_contracts(budget, risk_per_contract):
    budget, risk = number(budget), number(risk_per_contract)
    if not all(math.isfinite(v) and v > 0 for v in (budget, risk)):
        return 0
    return int((Decimal(str(budget)) / Decimal(str(risk))).to_integral_value(rounding=ROUND_FLOOR))


def _positive_integer(value):
    n = number(value)
    return math.isfinite(n) and n > 0 and n == int(n)


def candidate_overrides(universe_path: Path, product_count=93):
    if not _positive_integer(product_count):
        raise ValueError('product_count_must_be_positive_integer')
    return {**baseline_overrides(universe_path), 'fixed_size': 0, 'min_position_size': 1,
            'max_position_size': UNBOUNDED_POSITION_SIZE, 'max_concurrent_positions': int(product_count),
            'stage068_risk_fraction': RISK_FRACTION}


@dataclass(frozen=True)
class FractionalSignalRiskReceipt:
    snapshot_id: str
    contract_vt_symbol: str
    product_vt_symbol: str
    direction: str
    signal: str
    signal_datetime: str
    entry_context: str
    signal_equity: float
    risk_fraction: float
    target_risk_amount: float
    risk_per_contract: float
    stop_price: float
    authorized_volume: int


def _audit_json(snapshot):
    # A corrupted authorization must be rejected, not crash while recording why.
    safe = {k: None if isinstance(v, Real) and not math.isfinite(float(v)) else v
            for k, v in snapshot.items()}
    return json.dumps(safe, sort_keys=True, allow_nan=False, default=str)


def _receipt_dict(receipt):
    if is_dataclass(receipt):
        return asdict(receipt)
    return dict(receipt) if isinstance(receipt, dict) else {}


def _valid_receipt(value):
    try:
        return (bool(value['snapshot_id']) and value['risk_fraction'] == RISK_FRACTION
                and fractional_budget(value['signal_equity']) > 0
                and value['target_risk_amount'] == fractional_budget(value['signal_equity'])
                and _positive_integer(value['authorized_volume'])
                and whole_contracts(value['target_risk_amount'], value['risk_per_contract']) >= value['authorized_volume']
                and value['direction'] in ('long', 'short')
                and math.isfinite(number(value['stop_price'])) and number(value['stop_price']) > 0)
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


class FractionalRiskSizingMixin:
    stage068_risk_fraction = RISK_FRACTION
    parameters = FullMarketNoAIOneLot.parameters + ['stage068_risk_fraction']

    def _assert_stage068_policy(self):
        if (self.fixed_size != 0 or self.max_position_size != UNBOUNDED_POSITION_SIZE
                or self.min_position_size != 1 or self.stage068_risk_fraction != RISK_FRACTION):
            raise ValueError('stage068_requires_fixed_quarter_percent_native_sizing_without_one_lot_cap')
        if any(c.__name__ == 'NativeRiskBudgetSizingMixin' for c in type(self).__mro__):
            raise ValueError('legacy_one_lot_mixin_in_fractional_mro')

    def _risk_amount_from_ratio(self, risk_ratio, limited_balance, risk_multiplier_override=None):
        stack = getattr(self, '_stage068_equity_stack', [])
        return fractional_budget(stack[-1] if stack else getattr(self, 'estimated_equity', None))

    def _portfolio_overheat_cooldown_fields(self, entry_context):
        fields = dict(super()._portfolio_overheat_cooldown_fields(entry_context))
        fields['stage068_raw_overheat_scale'] = fields['portfolio_overheat_cooldown_scale']
        fields['portfolio_overheat_cooldown_scale'] = 1.
        return fields

    def _directional_30d_risk_boost_snapshot(self, direction, history):
        fields = dict(super()._directional_30d_risk_boost_snapshot(direction, history))
        fields['stage068_raw_directional_multiplier'] = fields['directional_30d_risk_boost_multiplier']
        fields['directional_30d_risk_boost_multiplier'] = 1.
        return fields

    def _calculate_entry_sizing(self, vt_symbol, direction, bar, history, signal_data,
            risk_mode_override=None, entry_context='flat_entry', apply_env_gate=True,
            active_positions_before=None, correlation_snapshot=None):
        self._assert_stage068_policy()
        equity = number(getattr(self, 'estimated_equity', None))
        budget = fractional_budget(equity)
        if not hasattr(self, '_stage068_equity_stack'):
            self._stage068_equity_stack = []
        self._stage068_equity_stack.append(equity)
        try:
            if budget <= 0:
                # Native sizing has ``equity or base_capital`` fallbacks and int
                # conversion of non-finite capital; reject before either can act.
                sizing = dict(selected_volume=0, contracts_by_risk=0, risk_amount=0.,
                    risk_ratio=RISK_FRACTION, risk_multiplier=1., sizing_equity=0.,
                    limited_balance=0., allowed_capital=0., free_capital=0.,
                    single_trade_capital_limit=0., reserved_margin_before=0.,
                    stop_price=number(bar.close_price), risk_per_contract=0.,
                    sizing_method='risk_budget', risk_mode=risk_mode_override or signal_data.get('risk_mode','regular'),
                    entry_context=entry_context, stage068_rejection='invalid_or_nonpositive_marked_total_equity')
            else:
                sizing = dict(super()._calculate_entry_sizing(vt_symbol, direction, bar, history, signal_data,
                    risk_mode_override=risk_mode_override, entry_context=entry_context, apply_env_gate=apply_env_gate,
                    active_positions_before=active_positions_before, correlation_snapshot=correlation_snapshot))
        finally:
            self._stage068_equity_stack.pop()
        before = max(0, int(sizing.get('selected_volume') or 0))
        raw_multiplier = sizing.get('risk_multiplier')
        if budget > 0 and sizing.get('risk_amount') != budget:
            raise RuntimeError('native_currency_formula_changed_after_fractional_budget_hook')
        sizing.update(selected_volume=min(before, whole_contracts(budget, sizing.get('risk_per_contract'))),
            risk_amount=budget, risk_ratio=RISK_FRACTION, risk_multiplier=1.,
            stage068_raw_risk_multiplier=raw_multiplier, stage068_signal_equity=equity if math.isfinite(equity) else None,
            stage068_risk_fraction=RISK_FRACTION, stage068_active_currency_formula=ACTIVE_CURRENCY_FORMULA,
            stage068_native_selected_volume=before, stage068_contract_vt_symbol=vt_symbol,
            stage068_direction=direction, stage068_signal_datetime=bar.datetime.isoformat())
        return sizing

    def _open_position(self, state, contract_vt_symbol, direction, volume, bar, signal,
                       history, signal_data, sizing_snapshot=None):
        self._assert_stage068_policy()
        if not _positive_integer(volume):
            return
        sizing = sizing_snapshot if sizing_snapshot is not None else self._calculate_entry_sizing(
            contract_vt_symbol, direction, bar, history, signal_data)
        try:
            bound = (sizing['stage068_contract_vt_symbol'] == contract_vt_symbol
                     and sizing['stage068_direction'] == direction
                     and sizing['stage068_signal_datetime'] == bar.datetime.isoformat()
                     and self.source_symbol_by_contract[contract_vt_symbol] == state.product_vt_symbol
                     and sizing['risk_amount'] == fractional_budget(sizing['stage068_signal_equity'])
                     and sizing['risk_amount'] > 0 and int(volume) <= int(sizing['selected_volume'])
                     and int(volume) <= whole_contracts(sizing['risk_amount'], sizing['risk_per_contract']))
        except (KeyError, TypeError, ValueError, OverflowError):
            bound = False
        if not bound:
            return
        sequence = int(getattr(self, '_stage068_sequence', 0)) + 1
        receipt = FractionalSignalRiskReceipt(
            snapshot_id=f'{self.strategy_name}:{contract_vt_symbol}:{direction}:{sequence}',
            contract_vt_symbol=contract_vt_symbol, product_vt_symbol=state.product_vt_symbol,
            direction=direction, signal=signal, signal_datetime=bar.datetime.isoformat(),
            entry_context=str(sizing['entry_context']), signal_equity=float(sizing['stage068_signal_equity']),
            risk_fraction=RISK_FRACTION, target_risk_amount=float(sizing['risk_amount']),
            risk_per_contract=float(sizing['risk_per_contract']), stop_price=float(sizing['stop_price']), authorized_volume=int(volume))
        if not _valid_receipt(asdict(receipt)):
            return
        result = super()._open_position(state, contract_vt_symbol, direction, int(volume), bar, signal,
                                       history, signal_data, sizing_snapshot=sizing)
        created = [x for x in state.layers if not x.entry_price_synced]
        if len(created) != 1 or int(created[0].volume) != int(volume):
            raise RuntimeError('fractional_pending_layer_identity_ambiguous')
        created[0].stage068_signal_risk_budget = receipt
        self._stage068_sequence = sequence
        return result


def assess_fractional_open(*, direction, open_price, stop_price, size, tick, volume, receipt, opening_equity):
    snapshot = _receipt_dict(receipt)
    p, stop, mult, tick = map(number, (open_price, stop_price, size, tick))
    current_budget = fractional_budget(opening_equity)
    signal_budget = number(snapshot.get('target_risk_amount'))
    budget = min(signal_budget, current_budget) if math.isfinite(signal_budget) and signal_budget > 0 else 0.
    reason = ''
    risk = total = float('nan')
    if not _valid_receipt(snapshot):
        reason = 'invalid_fractional_signal_receipt'
    elif not _positive_integer(volume) or int(volume) != snapshot['authorized_volume']:
        reason = 'order_volume_differs_from_signal_authorization'
    elif direction != snapshot['direction'] or direction not in ('long', 'short'):
        reason = 'signal_direction_mismatch'
    elif not all(math.isfinite(x) and x > 0 for x in (p, stop, mult, tick)) or stop != number(snapshot['stop_price']):
        reason = 'invalid_or_changed_frozen_initial_stop'
    elif (direction == 'long' and p <= stop) or (direction == 'short' and p >= stop):
        reason = 'stop_already_crossed_at_open'
    else:
        risk = max(abs(p-stop)*mult, tick*mult, 1.)
        total = float(Decimal(str(risk)) * Decimal(str(int(volume))))
        if budget <= 0:
            reason = 'missing_or_zero_fractional_opening_budget'
        elif int(volume) > whole_contracts(budget, risk):
            reason = 'total_order_risk_exceeds_fractional_budget_at_open'
    return dict(allowed=not reason, reason=reason, risk_per_contract=risk, total_risk=total,
                opening_budget=budget, opening_equity=number(opening_equity), risk_fraction=RISK_FRACTION,
                open_price=p, stop_price=stop, size=mult, pricetick=tick,
                max_affordable_volume=whole_contracts(budget, risk), volume=volume)


class FractionalOpeningRiskMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.open_budget_audit = []

    def _cancel_budget_open(self, order, layer, reason):
        s = self.strategy
        vt = order.vt_symbol
        self.cancel_order(s, order.vt_orderid)
        state = s._find_state_by_contract(vt)
        if state is not None and not s.get_pos(vt) and all(not x.entry_price_synced for x in state.layers):
            product = state.product_vt_symbol
            state.reset()
            s.pending_active_products.discard(product)
        elif state is not None and layer is not None and not layer.entry_price_synced:
            state.layers[:] = [x for x in state.layers if x is not layer]
        s.set_target(vt, int(s.get_pos(vt)))
        direction = 'long' if order.direction == Direction.LONG else 'short'
        for index in s.pending_entry_diagnostics.pop((vt, direction), []):
            s.entry_risk_diagnostics[index]['stage068_open_rejected_reason'] = reason
        self.blocked_open_orders.append(dict(date=str(self.datetime.date()), order_id=order.vt_orderid,
                                             vt_symbol=vt, reason=reason))

    def _fill_order(self, order, bar):
        if order.offset != Offset.OPEN:
            return super()._fill_order(order, bar)
        s = self.strategy
        vt = order.vt_symbol
        direction = 'long' if order.direction == Direction.LONG else 'short'
        state = s._find_state_by_contract(vt)
        layers = [] if state is None or state.direction != direction else [x for x in state.layers if not x.entry_price_synced and x.direction == direction]
        layer = layers[0] if len(layers) == 1 else None
        receipt = getattr(layer, 'stage068_signal_risk_budget', None)
        snapshot = _receipt_dict(receipt)
        meta = self.research_metadata[vt]
        equity = number(self.opening_equity) - number(self.open_execution_costs)
        assessment = assess_fractional_open(direction=direction, open_price=bar.open_price,
            stop_price=getattr(layer, 'stop_price', None), size=meta['size'], tick=meta['pricetick'],
            volume=order.volume, receipt=snapshot, opening_equity=equity)
        try:
            bound = (isinstance(receipt, FractionalSignalRiskReceipt) and layer is not None
                     and snapshot['contract_vt_symbol'] == vt
                     and snapshot['product_vt_symbol'] == state.product_vt_symbol
                     and s.source_symbol_by_contract[vt] == state.product_vt_symbol
                     and snapshot['signal'] == layer.signal and snapshot['direction'] == direction
                     and pd.Timestamp(snapshot['signal_datetime']).date() == pd.Timestamp(layer.entry_date).date()
                     and _positive_integer(layer.volume) and layer.volume == snapshot['authorized_volume'])
        except (KeyError, TypeError, ValueError, OverflowError):
            bound = False
        row = dict(date=str(self.datetime.date()), order_id=order.vt_orderid, vt_symbol=vt,
                   direction=direction, signal_snapshot=_audit_json(snapshot), **assessment)
        if not bound:
            row.update(allowed=False, reason='unbound_fractional_signal_authorization')
        self.open_budget_audit.append(row)
        if not row['allowed']:
            self._cancel_budget_open(order, layer, row['reason'])
            row['filled'] = False
            return
        before = set(self.trades)
        result = super()._fill_order(order, bar)
        added = set(self.trades) - before
        row['filled'] = bool(added)
        if not added:
            row.update(allowed=False, reason='rejected_by_remaining_execution_gate')
            self._cancel_budget_open(order, layer, row['reason'])
        else:
            if len(added) != 1:
                raise RuntimeError('multiple_fills_for_fractional_authorization')
            trade = self.trades[next(iter(added))]
            if float(trade.price) != float(bar.open_price) or int(trade.volume) != snapshot['authorized_volume']:
                raise RuntimeError('actual_fractional_fill_differs_from_authorized_price_or_volume')
            row['trade_id'] = trade.vt_tradeid
            trade.stage068_budget = row['opening_budget']
            trade.stage068_entry_risk = row['total_risk']
            trade.stage068_risk_per_contract = row['risk_per_contract']
            trade.stage068_signal_snapshot = snapshot
        return result
