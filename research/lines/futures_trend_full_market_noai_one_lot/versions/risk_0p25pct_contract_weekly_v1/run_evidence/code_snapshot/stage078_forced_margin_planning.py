"""Separate forced-margin planning from physical positions and OPEN intentions.

The native forced-deleverage loop and its economic settings remain unchanged.
Only that loop sees margin after already planned CLOSEs.  Unfilled OPENs are
cancelled whole before any native Close event or provisional realized PNL.
"""
from dataclasses import asdict, is_dataclass
import json
import math

from vnpy.trader.constant import Offset
from stage074_pending_close_quantity import _whole_quantity


def _archive(value):
    return asdict(value) if is_dataclass(value) else dict(value) if isinstance(value, dict) else None


class ForcedMarginIntentMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stage078_intent_cancellations = []
        self.forced_margin_pending_open_cancel_count = 0
        self.forced_margin_pending_open_cancel_volume = 0

    def _reset_intrabar_reservations(self):
        result = super()._reset_intrabar_reservations()
        self._stage078_intent_reservations = {}
        return result

    def _reserve_intrabar_entry(self, product_vt_symbol, sizing_snapshot, volume, *, count_active_position):
        before = float(self.pending_margin_reservation)
        cluster = self._risk_cluster_for_symbol(product_vt_symbol)
        cluster_before = float(self.pending_cluster_margin_reservation.get(cluster, 0.))
        result = super()._reserve_intrabar_entry(product_vt_symbol, sizing_snapshot, volume,
                                               count_active_position=count_active_position)
        state = self.states[product_vt_symbol]
        ledger = getattr(self, '_stage078_intent_reservations', None)
        if ledger is None:
            ledger = self._stage078_intent_reservations = {}
        row = ledger.setdefault(state.contract_vt_symbol, dict(margin=0., cluster=cluster, cluster_margin=0.))
        row['margin'] += float(self.pending_margin_reservation) - before
        row['cluster_margin'] += float(self.pending_cluster_margin_reservation.get(cluster, 0.)) - cluster_before
        return result

    def _stage078_mark(self, vt_symbol, bars):
        bar = bars.get(vt_symbol) or getattr(self.strategy_engine, 'bars', {}).get(vt_symbol)
        if bar is None:
            raise RuntimeError('stage078_margin_mark_missing:' + vt_symbol)
        now = getattr(self.strategy_engine, 'datetime', None)
        if now is not None and bar.datetime.date() > now.date():
            raise RuntimeError('stage078_future_margin_mark:' + vt_symbol)
        price = float(bar.close_price)
        if not math.isfinite(price) or price <= 0:
            raise RuntimeError('stage078_invalid_margin_mark:' + vt_symbol)
        margin_per_contract = price * self.get_size(vt_symbol) * self._margin_ratio_for_symbol(vt_symbol)
        if not math.isfinite(margin_per_contract) or margin_per_contract <= 0:
            raise RuntimeError('stage078_invalid_margin_per_contract:' + vt_symbol)
        return bar, margin_per_contract

    def _stage078_intents(self, bars):
        rows = []
        for state in self.states.values():
            layers = [layer for layer in state.layers if not layer.entry_price_synced]
            if not layers:
                continue
            vt = state.contract_vt_symbol
            if not vt or state.direction not in ('long', 'short'):
                raise RuntimeError('stage078_unbound_open_intent')
            bar, margin_per_contract = self._stage078_mark(vt, bars)
            volume = sum(_whole_quantity(layer.volume, 'open_intent_quantity') for layer in layers)
            if not volume or any(layer.direction != state.direction for layer in layers):
                raise RuntimeError('stage078_invalid_open_intent')
            actual, pending_close = self._pending_close_quantity(vt)
            if abs(actual) > pending_close and state.direction != ('long' if actual > 0 else 'short'):
                raise RuntimeError('stage078_open_intent_conflicts_with_actual_position')
            unrealized = sum((float(bar.close_price) - layer.entry_price) * self.get_size(vt) * layer.volume
                             * (1 if layer.direction == 'long' else -1) for layer in layers)
            rows.append(dict(state=state, vt_symbol=vt, layers=layers, bar=bar, volume=volume,
                             margin=volume * margin_per_contract, unrealized_pnl=unrealized))
        priority = str(self.forced_margin_deleverage_priority or 'largest_margin').strip().lower()
        if priority == 'largest_unrealized_loss':
            rows.sort(key=lambda row: (float(row['unrealized_pnl']), -float(row['margin'])))
        elif priority == 'largest_volume':
            rows.sort(key=lambda row: (-int(row['volume']), -float(row['margin'])))
        else:
            rows.sort(key=lambda row: (-float(row['margin']), float(row['unrealized_pnl'])))
        return rows

    def _stage078_projected_margin(self, bars):
        total = 0.
        actual_symbols = {vt for vt, qty in self.pos_data.items() if qty}
        actual_symbols.update(self.pending_close_lots)
        for vt in actual_symbols:
            actual, pending = self._pending_close_quantity(vt)
            remaining = abs(actual) - pending
            if remaining:
                _, margin_per_contract = self._stage078_mark(vt, bars)
                total += remaining * margin_per_contract
        total += sum(row['margin'] for row in self._stage078_intents(bars))
        return total

    def _estimate_margin_usage(self, bars):
        if getattr(self, '_stage078_forced_planning_active', False):
            return self._stage078_projected_margin(bars)
        return super()._estimate_margin_usage(bars)

    def _stage078_cancel_intent(self, candidate, bars, *, ratio_before, equity, broker_multiplier):
        state, vt, layers = candidate['state'], candidate['vt_symbol'], candidate['layers']
        actual, pending_close = self._pending_close_quantity(vt)
        retained = [layer for layer in state.layers if layer.entry_price_synced]
        retained_quantity = sum(_whole_quantity(layer.volume, 'retained_layer_quantity') for layer in retained)
        if retained_quantity != abs(actual) - pending_close:
            raise RuntimeError('stage078_synced_layers_actual_pending_mismatch')
        receipt_archive = [_archive(getattr(layer, 'stage068_signal_risk_budget', None)) for layer in layers]
        weekly_archive = [_archive(getattr(layer, 'stage059_weekly_authorization', None)) for layer in layers]
        cancelled_orders = []
        for key, order in list(self.strategy_engine.active_limit_orders.items()):
            if order.vt_symbol == vt and order.offset == Offset.OPEN:
                self.cancel_order(key)
                cancelled_orders.append(key)
        state.layers[:] = retained
        if not retained:
            state.reset()
        self.set_target(vt, retained_quantity if actual > 0 else -retained_quantity)
        self.execution_price_overrides.pop(vt, None)
        self.pending_active_products.discard(state.product_vt_symbol)
        reason = 'forced_margin_cancel_unfilled_open_intent'
        for direction in {layer.direction for layer in layers}:
            for index in self.pending_entry_diagnostics.pop((vt, direction), []):
                self.entry_risk_diagnostics[index]['stage078_open_cancelled_reason'] = reason
        reservation = getattr(self, '_stage078_intent_reservations', {}).pop(vt, None)
        released = 0.
        if reservation is not None:
            released = min(float(self.pending_margin_reservation), reservation['margin'])
            self.pending_margin_reservation = max(0., float(self.pending_margin_reservation) - released)
            cluster = reservation['cluster']
            self.pending_cluster_margin_reservation[cluster] = max(0.,
                float(self.pending_cluster_margin_reservation.get(cluster, 0.)) - reservation['cluster_margin'])
        if not hasattr(self, 'stage078_intent_cancellations'):
            self.stage078_intent_cancellations = []
            self.forced_margin_pending_open_cancel_count = 0
            self.forced_margin_pending_open_cancel_volume = 0
        self.forced_margin_pending_open_cancel_count += 1
        self.forced_margin_pending_open_cancel_volume += candidate['volume']
        cancellation_time = self.strategy_engine.datetime
        self.stage078_intent_cancellations.append(dict(
            datetime=cancellation_time, date=cancellation_time.date().isoformat(), quote_datetime=candidate['bar'].datetime,
            vt_symbol=vt, product_vt_symbol=state.product_vt_symbol,
            direction=layers[0].direction, volume=candidate['volume'], reason=reason,
            priority=str(self.forced_margin_deleverage_priority or 'largest_margin'),
            ratio_before=ratio_before, ratio_after=self._stage078_projected_margin(bars) * broker_multiplier / equity,
            released_pending_margin=released, actual_position=actual, pending_close_quantity=pending_close,
            cancelled_orders=cancelled_orders, risk_receipts=receipt_archive, weekly_authorizations=weekly_archive,
            receipt_json=json.dumps(receipt_archive, sort_keys=True, allow_nan=False),
            weekly_authorization_json=json.dumps(weekly_archive, sort_keys=True, allow_nan=False)))

    def _forced_margin_deleverage_candidates(self, bars):
        rows = super()._forced_margin_deleverage_candidates(bars)
        result = []
        for row in rows:
            state = row['state']
            if any(not layer.entry_price_synced for layer in state.layers):
                continue
            actual, pending_close = self._pending_close_quantity(state.contract_vt_symbol)
            if row['volume'] != abs(actual) - pending_close or state.direction != ('long' if actual > 0 else 'short'):
                raise RuntimeError('stage078_forced_candidate_not_actual_remaining_layers')
            result.append(row)
        return result

    def _process_forced_margin_deleverage(self, bars):
        if not self.enable_forced_margin_deleverage or not bars:
            return super()._process_forced_margin_deleverage(bars)
        trigger = max(0., float(self.forced_margin_deleverage_trigger_ratio or 0.))
        target = min(max(0., float(self.forced_margin_deleverage_target_ratio or 0.)), trigger)
        multiplier = max(0., float(self.forced_margin_deleverage_broker_multiplier or 1.))
        if trigger <= 0 or target <= 0 or multiplier <= 0:
            return super()._process_forced_margin_deleverage(bars)
        equity = max(1e-9, float(self.estimated_equity or self.base_capital))
        previous = getattr(self, '_stage078_forced_planning_active', False)
        self._stage078_forced_planning_active = True
        try:
            ratio = self._estimate_margin_usage(bars) * multiplier / equity
            if ratio > trigger + 1e-12:
                self.forced_margin_deleverage_max_observed_ratio = max(self.forced_margin_deleverage_max_observed_ratio, ratio)
                while ratio > target + 1e-12:
                    intents = self._stage078_intents(bars)
                    if not intents:
                        break
                    self._stage078_cancel_intent(intents[0], bars, ratio_before=ratio, equity=equity, broker_multiplier=multiplier)
                    ratio = self._estimate_margin_usage(bars) * multiplier / equity
            return super()._process_forced_margin_deleverage(bars)
        finally:
            self._stage078_forced_planning_active = previous
