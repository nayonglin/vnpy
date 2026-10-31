from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd
from . import base804 as s804
from . import qmt_roll_intraday_execution as execution
from copy import copy
from vnpy.trader.constant import Direction
from vnpy.trader.object import TradeData
STOP_R=1.0
CONFIRM_R=1.0
_GLOBAL_MINUTE_BY_SYMBOL={}


def _direction_sign(direction: str) -> float:
    return 1.0 if direction == "long" else -1.0

def _normalize_date(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts.normalize()

class QmtRollPortfolioStrategyStage827C2(s804.QmtRollPortfolioStrategyLongTighterInitialStop):
    enable_stage827_intraday_c2_stop: bool = False
    stage827_require_complete_minutes: bool = True
    stage827_intraday_c2_stop_r: float = STOP_R
    stage827_intraday_c2_confirm_r: float = CONFIRM_R

    parameters = s804.QmtRollPortfolioStrategyLongTighterInitialStop.parameters + [
        "enable_stage827_intraday_c2_stop",
        "stage827_intraday_c2_stop_r",
        "stage827_intraday_c2_confirm_r",
    ]
    variables = s804.QmtRollPortfolioStrategyLongTighterInitialStop.variables + [
        "stage827_intraday_c2_stop_count",
    ]

    def __init__(self, strategy_engine, strategy_name: str, vt_symbols: list[str], setting: dict) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage827_minute_by_symbol = _GLOBAL_MINUTE_BY_SYMBOL
        self.stage827_intraday_c2_events: list[dict[str, Any]] = []
        self.stage827_intraday_c2_stop_count: int = 0
        self.minute_scan_requests: list[dict[str, Any]] = []

    def stage827_intraday_exit_after_open_trade(self, trade: TradeData) -> dict[str, Any] | None:
        if not self.enable_stage827_intraday_c2_stop:
            return None
        state = self._find_state_by_contract(trade.vt_symbol)
        if state is None or not state.layers:
            return None

        position_direction = "long" if trade.direction == Direction.LONG else "short"
        if state.direction != position_direction:
            return None

        entry_day = execution.entry_session(self, trade)
        if entry_day.empty:
            return None

        entry_price = float(trade.price)
        if entry_price <= 0:
            return None

        candidate_indexes: list[int] = []
        risk_prices: list[float] = []
        for index, layer in enumerate(state.layers):
            if layer.direction != position_direction:
                continue
            candidate_indexes.append(index)
            risk_prices.append(abs(entry_price - float(layer.stop_price)))

        if not candidate_indexes:
            return None
        risk_price = max(risk_prices) if risk_prices else 0.0
        min_risk = max(float(self.get_pricetick(trade.vt_symbol)), 1e-9)
        fill_tick = execution.effective_pricetick(trade.vt_symbol, getattr(trade, "trading_date", trade.datetime), min_risk)
        if not np.isfinite(risk_price) or risk_price < min_risk:
            return None

        sign = _direction_sign(position_direction)
        stop_price = entry_price - sign * float(self.stage827_intraday_c2_stop_r) * risk_price
        confirm_price = entry_price + sign * float(self.stage827_intraday_c2_confirm_r) * risk_price
        hit_index, hit_note = execution.first_stop(
            entry_day, stop_price, confirm_price, long=position_direction == "long"
        )
        if hit_index < 0:
            return None
        hit_bar = entry_day.iloc[hit_index]
        hit_time = pd.Timestamp(hit_bar["bar_datetime"]).isoformat()
        fill_price, fill_note = execution.stop_fill(
            hit_bar, stop_price, fill_tick, buy=position_direction == "short"
        )

        contract_vt_symbol = state.contract_vt_symbol
        product_vt_symbol = state.product_vt_symbol
        close_volume = sum(state.layers[index].volume for index in candidate_indexes)
        if close_volume <= 0:
            return None
        exit_reason = "stage827_intraday_c2_1r_stop"
        self.stage827_intraday_c2_stop_count += 1
        event = {
            "datetime": _normalize_date(getattr(trade, "trading_date", trade.datetime)),
            "trading_date": str(getattr(trade, "trading_date", _normalize_date(trade.datetime).date())),
            "execution_datetime": getattr(trade, "execution_datetime", trade.datetime),
            "trade_id": trade.vt_tradeid,
            "vt_symbol": trade.vt_symbol,
            "product_vt_symbol": product_vt_symbol,
            "direction": position_direction,
            "entry_price": entry_price,
            "stop_price": stop_price,
            "fill_price": fill_price,
            "fill_note": fill_note,
            "candidate_indexes": candidate_indexes,
            "candidate_layer_ids": [self._stage827_layer_identity(state.layers[index]) for index in candidate_indexes],
            "effective_tick": fill_tick,
            "tick_basis": execution.pricetick_basis(trade.vt_symbol),
            "execution_policy": execution.EXECUTION_POLICY,
            "confirm_price": confirm_price,
            "risk_price": risk_price,
            "volume": close_volume,
            "hit_time": hit_time,
            "note": hit_note,
            "exit_reason": exit_reason,
        }
        self.stage827_intraday_c2_events.append(event)
        return event

    def _sync_open_trade(self, trade: TradeData) -> None:
        # Synthetic re-entry is applied to the bound episode by finalize; it must
        # never consume an ordinary order's pending layers or change their age.
        if getattr(trade, "intraday_episode_id", ""):
            return
        signal_time = getattr(trade, "signal_datetime", None)
        if signal_time is None:
            accounting_trade = copy(trade)
            accounting_trade.datetime = _normalize_date(getattr(trade, "trading_date", trade.datetime)).to_pydatetime()
            return super()._sync_open_trade(accounting_trade)
        state = self._find_state_by_contract(trade.vt_symbol)
        direction = "long" if trade.direction == Direction.LONG else "short"
        signal_date = execution.local_timestamp(signal_time).date()
        if state is None or state.direction != direction:
            raise ValueError(f"intraday_unmatched_open_fill:{trade.vt_tradeid}")
        remaining = int(trade.volume)
        candidates = [layer for layer in reversed(state.layers)
                      if layer.direction == direction and execution.local_timestamp(layer.entry_date).date() == signal_date
                      and not layer.entry_price_synced]
        if sum(int(layer.volume) for layer in candidates) < remaining:
            raise ValueError(f"intraday_unmatched_open_fill:{trade.vt_tradeid}")
        for layer in candidates:
            if remaining <= 0:
                break
            matched = min(remaining, int(layer.volume))
            filled = layer
            if matched < layer.volume:
                filled = copy(layer)
                filled.volume = matched
                filled._stage827_layer_id = ""
                layer.volume -= matched
                state.layers.insert(next(index for index, item in enumerate(state.layers) if item is layer) + 1, filled)
            filled.entry_price = float(trade.price)
            filled.entry_price_synced = True
            filled._stage827_signal_order_id = str(getattr(trade, "signal_order_id", trade.vt_orderid))
            self._stage827_layer_identity(filled)
            remaining -= matched

    def _sync_entry_risk_diagnostic(self, trade: TradeData) -> None:
        if getattr(trade, "intraday_episode_id", ""):
            return
        signal_time = getattr(trade, "signal_datetime", None)
        if signal_time is None:
            return super()._sync_entry_risk_diagnostic(trade)
        direction = "long" if trade.direction == Direction.LONG else "short"
        key = (trade.vt_symbol, direction)
        pending = self.pending_entry_diagnostics.get(key, [])
        remaining = int(trade.volume)
        for diagnostic_index in reversed(list(pending)):
            if remaining <= 0:
                break
            row = self.entry_risk_diagnostics[diagnostic_index]
            if execution.local_timestamp(row["datetime"]) != execution.local_timestamp(signal_time):
                continue
            planned = int(row["volume"])
            previous = int(row.get("actual_filled_volume") or 0)
            matched = min(remaining, max(0, planned - previous))
            if not matched:
                continue
            cumulative = previous + matched
            prior_turnover = float(row.get("filled_entry_price") or 0.0) * previous
            average = (prior_turnover + float(trade.price) * matched) / cumulative
            size, margin_ratio = int(row["size"]), float(row["margin_ratio"])
            minimum_risk = max(float(self.get_pricetick(trade.vt_symbol)) * size, 1.0)
            fill_risk = max(abs(float(trade.price) - float(row["stop_price"])) * size, minimum_risk)
            previous_risk = float(row.get("actual_risk_amount") or 0.0) if previous else 0.0
            row.update(actual_filled_volume=cumulative, filled_entry_price=average, entry_price=average,
                       stop_distance=abs(average-float(row["stop_price"])),
                       actual_risk_amount=previous_risk + fill_risk * matched,
                       margin_per_contract=average * size * margin_ratio,
                       actual_margin_amount=average * size * margin_ratio * cumulative,
                       signal_order_id=str(getattr(trade, "signal_order_id", trade.vt_orderid)))
            row["risk_per_contract"] = row["actual_risk_amount"] / cumulative
            row["projected_total_margin_after"] = float(row["total_margin_in_use_before"]) + row["actual_margin_amount"]
            remaining -= matched
            if cumulative == planned:
                pending.remove(diagnostic_index)
        if not pending:
            self.pending_entry_diagnostics.pop(key, None)

    def _stage827_layer_identity(self, layer: Any) -> str:
        identity = getattr(layer, "_stage827_layer_id", "")
        if not identity:
            self._stage827_layer_serial = int(getattr(self, "_stage827_layer_serial", 0)) + 1
            identity = f"layer-{self._stage827_layer_serial}"
            layer._stage827_layer_id = identity
        return identity

    def _stage827_finalize_intraday_action(self, event: dict[str, Any], item: dict[str, Any], *, final: bool) -> None:
        state = self._find_state_by_contract(str(event["vt_symbol"]))
        if state is None or not state.layers:
            raise ValueError("intraday_stale_episode:missing_state")
        identities = event.get("candidate_layer_ids")
        if identities is not None:
            wanted = set(identities)
            indexes = [index for index, layer in enumerate(state.layers)
                       if self._stage827_layer_identity(layer) in wanted]
            if len(indexes) != len(identities) or sum(int(state.layers[index].volume) for index in indexes) != int(event["volume"]):
                raise ValueError("intraday_stale_episode:layer_or_volume_changed")
        else:
            indexes = list(event.get("candidate_indexes", range(len(state.layers))))
        if str(item.get("action")) == "open":
            # A reclaim is a stop-entry trigger, not a guaranteed original price.
            for index in indexes:
                state.layers[index].entry_price = float(item["price"])
                state.layers[index].entry_price_synced = True
        if not final or event.get("final_state") == "open_after_reentry":
            return
        price = float(item["price"])
        reason = str(item.get("source") or event["exit_reason"])
        if len(indexes) == len(state.layers):
            self._close_all_layers_and_set_flat_target(
                state, price, execution_price_override=price, exit_reason=reason,
            )
        else:
            self._record_trade_event(
                bar=getattr(self.strategy_engine, "bars", {}).get(str(event["vt_symbol"])),
                contract_vt_symbol=str(event["vt_symbol"]),
                product_vt_symbol=state.product_vt_symbol,
                position_direction=state.direction, offset="Close", reason=reason,
                volume=int(item["volume"]), price=price,
            )
            self._close_layers(state, indexes, price, exit_reason=reason)
            self._apply_state_target(state, execution_price_override=price)
