from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd
from . import base827 as s827
from . import base830 as s830
STOP_RETRY_R=0.5
MAX_RETRIES=1


class QmtRollPortfolioStrategyStage847C9StopRetry(s830.QmtRollPortfolioStrategyStage830C2Broker10MarginCap):
    enable_stage847_half_r_stop_retry: bool = False
    stage847_stop_retry_r: float = STOP_RETRY_R
    stage847_max_retries: int = MAX_RETRIES

    parameters = s830.QmtRollPortfolioStrategyStage830C2Broker10MarginCap.parameters + [
        "enable_stage847_half_r_stop_retry",
        "stage847_stop_retry_r",
        "stage847_max_retries",
    ]
    variables = s830.QmtRollPortfolioStrategyStage830C2Broker10MarginCap.variables + [
        "stage847_stop_retry_event_count",
    ]

    def __init__(self, strategy_engine, strategy_name: str, vt_symbols: list[str], setting: dict) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage847_stop_retry_events: list[dict[str, Any]] = []
        self.stage847_stop_retry_event_count: int = 0

    def stage827_intraday_exit_after_open_trade(self, trade: s827.TradeData) -> dict[str, Any] | None:
        if self.enable_stage847_half_r_stop_retry:
            event = self._stage847_stop_retry_event_after_open_trade(trade)
            if event:
                return event
        return super().stage827_intraday_exit_after_open_trade(trade)

    def _stage847_stop_retry_event_after_open_trade(self, trade: s827.TradeData) -> dict[str, Any] | None:
        state = self._find_state_by_contract(trade.vt_symbol)
        if state is None or not state.layers:
            return None

        position_direction = "long" if trade.direction == s827.Direction.LONG else "short"
        if state.direction != position_direction:
            return None

        entry_day = s827.execution.entry_session(self, trade)
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
        fill_tick = s827.execution.effective_pricetick(trade.vt_symbol, getattr(trade, "trading_date", trade.datetime), min_risk)
        if not np.isfinite(risk_price) or risk_price < min_risk:
            return None

        sign = s827._direction_sign(position_direction)
        stop_price = entry_price - sign * float(self.stage847_stop_retry_r) * risk_price
        progress_price = entry_price + sign * float(self.stage847_stop_retry_r) * risk_price
        first_stop_idx, first_note = s827.execution.first_stop(
            entry_day, stop_price, progress_price, long=position_direction == "long"
        )
        if first_stop_idx < 0:
            return None
        first_bar = entry_day.iloc[first_stop_idx]
        first_stop_time = pd.Timestamp(first_bar["bar_datetime"]).isoformat()
        first_fill, first_fill_note = s827.execution.stop_fill(
            first_bar, stop_price, fill_tick, buy=position_direction == "short"
        )
        reentry_idx = -1
        reentry_time = ""
        reentry_fill = entry_price
        reentry_note = ""
        max_retries = max(0, int(self.stage847_max_retries))
        # A retry order is armed after the first stop bar.  There is no evidence
        # that a same-bar reclaim occurred after that initial stop.
        if max_retries > 0:
            for idx in range(first_stop_idx + 1, len(entry_day)):
                item = entry_day.iloc[idx]
                reclaimed = float(item["high"]) >= entry_price if position_direction == "long" else float(item["low"]) <= entry_price
                if reclaimed:
                    reentry_idx = idx
                    reentry_time = pd.Timestamp(item["bar_datetime"]).isoformat()
                    reentry_fill, reentry_note = s827.execution.stop_fill(
                        item, entry_price, fill_tick, buy=position_direction == "long"
                    )
                    break
        retry_failed_idx = -1
        retry_failed_time = ""
        retry_fill = stop_price
        retry_note = ""
        if reentry_idx >= 0:
            # After an intrabar reclaim, assume the adverse extreme can follow.
            # Its pre-reclaim open cannot be used as the subsequent stop fill.
            for idx in range(reentry_idx, len(entry_day)):
                item = entry_day.iloc[idx]
                hit = float(item["low"]) <= stop_price if position_direction == "long" else float(item["high"]) >= stop_price
                if hit:
                    retry_failed_idx = idx
                    retry_failed_time = pd.Timestamp(item["bar_datetime"]).isoformat()
                    retry_fill, retry_note = s827.execution.stop_fill(
                        item, stop_price, fill_tick, buy=position_direction == "short",
                        use_open=idx != reentry_idx,
                    )
                    if idx == reentry_idx:
                        retry_note = "same_bar_reclaim_then_conservative_stop_" + retry_note
                    break

        contract_vt_symbol = state.contract_vt_symbol
        product_vt_symbol = state.product_vt_symbol
        close_volume = sum(state.layers[index].volume for index in candidate_indexes)
        if close_volume <= 0:
            return None

        synthetic_trades: list[dict[str, Any]] = [
            {
                "action": "close",
                "source": "stage847_intraday_05r_initial_stop",
                "price": first_fill,
                "trigger_price": stop_price,
                "execution_note": first_fill_note,
                "volume": close_volume,
                "time": first_stop_time,
            }
        ]
        final_state = "flat_no_reentry"
        exit_reason = "stage847_intraday_05r_stop_no_reentry"
        final_exit_price = first_fill

        if reentry_idx >= 0:
            synthetic_trades.append(
                {
                    "action": "open",
                    "source": "stage847_intraday_reentry_at_original_entry",
                    "price": reentry_fill,
                    "trigger_price": entry_price,
                    "execution_note": reentry_note,
                    "volume": close_volume,
                    "time": reentry_time,
                }
            )
            final_state = "open_after_reentry"
            exit_reason = "stage847_intraday_05r_stop_reentry_open"
            final_exit_price = np.nan
            if retry_failed_idx >= 0:
                synthetic_trades.append(
                    {
                        "action": "close",
                        "source": "stage847_intraday_retry_failed_05r_stop",
                        "price": retry_fill,
                        "trigger_price": stop_price,
                        "execution_note": retry_note,
                        "volume": close_volume,
                        "time": retry_failed_time,
                    }
                )
                final_state = "flat_retry_failed"
                exit_reason = "stage847_intraday_retry_failed_05r_stop"
                final_exit_price = retry_fill

        self.stage847_stop_retry_event_count += 1
        event = {
            "datetime": s827._normalize_date(getattr(trade, "trading_date", trade.datetime)),
            "trading_date": str(getattr(trade, "trading_date", s827._normalize_date(trade.datetime).date())),
            "execution_datetime": getattr(trade, "execution_datetime", trade.datetime),
            "candidate_indexes": candidate_indexes,
            "candidate_layer_ids": [self._stage827_layer_identity(state.layers[index]) for index in candidate_indexes],
            "effective_tick": fill_tick,
            "tick_basis": s827.execution.pricetick_basis(trade.vt_symbol),
            "execution_policy": s827.execution.EXECUTION_POLICY,
            "trade_id": trade.vt_tradeid,
            "vt_symbol": trade.vt_symbol,
            "product_vt_symbol": product_vt_symbol,
            "direction": position_direction,
            "entry_price": entry_price,
            "stop_price": stop_price,
            "progress_price": progress_price,
            "risk_price": risk_price,
            "stop_r": float(self.stage847_stop_retry_r),
            "max_retries": max_retries,
            "volume": close_volume,
            "first_stop_time": first_stop_time,
            "first_stop_bar_index": first_stop_idx,
            "reentry_time": reentry_time,
            "reentry_bar_index": reentry_idx,
            "retry_failed_time": retry_failed_time,
            "retry_failed_bar_index": retry_failed_idx,
            "retry_reentered": int(reentry_idx >= 0),
            "retry_failed": int(retry_failed_idx >= 0),
            "final_state": final_state,
            "final_exit_price": final_exit_price,
            "note": first_note,
            "exit_reason": exit_reason,
            "synthetic_trades": synthetic_trades,
        }
        self.stage847_stop_retry_events.append(event)
        return event
