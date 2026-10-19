"""Keep native planned position reductions distinct from unfilled CLOSEs.

Place this mixin first in the research strategy MRO.  Native partial exits
decrease layers when they queue a close, before the broker position changes.
Consequently remaining layers plus pending close lots must equal the actual
position.  No alpha, sizing, exit trigger, or execution timing changes here.
"""
from math import isfinite


def _whole_quantity(value, label):
    if isinstance(value, bool):
        raise RuntimeError(f"stage074_{label}_not_integer")
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise RuntimeError(f"stage074_{label}_not_integer") from exc
    if not isfinite(numeric) or numeric < 0 or not numeric.is_integer():
        raise RuntimeError(f"stage074_{label}_not_integer")
    return int(numeric)


class PendingCloseQuantityMixin:
    def _pending_close_quantity(self, vt_symbol, current_pos=None):
        actual = self.get_pos(vt_symbol) if current_pos is None else current_pos
        if isinstance(actual, bool):
            raise RuntimeError("stage074_actual_position_not_integer")
        try:
            numeric = float(actual)
        except (TypeError, ValueError, OverflowError) as exc:
            raise RuntimeError("stage074_actual_position_not_integer") from exc
        if not isfinite(numeric) or not numeric.is_integer():
            raise RuntimeError("stage074_actual_position_not_integer")
        actual = int(numeric)
        direction = "long" if actual > 0 else "short" if actual < 0 else ""
        pending = 0
        for lot in self.pending_close_lots.get(vt_symbol, []):
            quantity = _whole_quantity(lot["volume"], "pending_close_quantity")
            if not quantity or lot["direction"] != direction:
                raise RuntimeError("stage074_pending_close_direction_or_quantity")
            pending += quantity
        if pending > abs(actual):
            raise RuntimeError("stage074_pending_close_exceeds_actual_position")
        return actual, pending

    def _reconcile_state_with_position(self, state, current_pos, bar):
        vt_symbol = state.contract_vt_symbol or bar.vt_symbol
        actual, pending = self._pending_close_quantity(vt_symbol, current_pos)
        if pending:
            remaining = abs(actual) - pending
            layer_quantity = sum(_whole_quantity(layer.volume, "layer_quantity") for layer in state.layers)
            direction = "long" if actual > 0 else "short"
            if layer_quantity != remaining or any(layer.direction != direction for layer in state.layers):
                raise RuntimeError("stage074_remaining_layers_pending_close_mismatch")
            self.set_target(vt_symbol, remaining if actual > 0 else -remaining)
            return
        return super()._reconcile_state_with_position(state, current_pos, bar)

    def _queue_pending_close_lot(self, vt_symbol, layer, exit_price, volume):
        quantity = _whole_quantity(volume, "requested_close_quantity")
        if not quantity:
            return
        actual, pending = self._pending_close_quantity(vt_symbol)
        direction = "long" if actual > 0 else "short" if actual < 0 else ""
        if layer.direction != direction:
            raise RuntimeError("stage074_requested_close_direction_mismatch")
        if quantity > abs(actual) - pending:
            raise RuntimeError("stage074_requested_close_exceeds_uncommitted_position")
        # Native _reduce_position_to_target queues BEFORE decreasing its layer.
        # The layer invariant belongs at reconcile boundaries, not in this hook.
        return super()._queue_pending_close_lot(vt_symbol, layer, exit_price, quantity)
