from __future__ import annotations

from copy import copy
from dataclasses import replace
import heapq
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from vnpy.trader.constant import Direction, Interval, Offset
from vnpy.trader.object import BarData, TradeData
from vnpy_portfoliostrategy.backtesting import Status

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772
import analyze_qmt_roll_stage778_stage777_2022_drawdown_forensics as s778
import analyze_qmt_roll_stage804_stage777_long_tighter_initial_stop_yearly as s804
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import analyze_qmt_roll_stage826_stage819_intraday_ac_overlay as s826
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg
import qmt_roll_intraday_execution as execution


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage827"
MODEL_TAG = "stage827_stage819_intraday_c2_engine_ac_v1"
OUTPUT_PREFIX = "qmt_roll_stage827_stage819_intraday_c2_engine_ac"

START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-05-29")
CAPITAL = stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_CAPITAL
STOP_R = 1.0
CONFIRM_R = 1.0

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curve_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
INTRADAY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_events_{MODEL_TAG}.csv"
CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

_GLOBAL_MINUTE_BY_SYMBOL: dict[str, pd.DataFrame] = {}


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s825._safe_float(value, default=default)


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


class Stage827IntradayC2Engine(s778.s653.s517.s506.s502.ConfirmedDailyNextRealOpenEngine):
    def _stage827_order_context(self, order: Any, bar: BarData) -> dict[str, Any]:
        legacy_price, legacy_source, legacy_proxy = self._resolve_trade_price(order, bar)
        proxy = dict(legacy_proxy)
        trading_date = execution.local_timestamp(self.datetime).normalize()
        grid = execution.session_minutes(str(order.vt_symbol), trading_date, self.strategy.available_trade_dates)
        expected_start = grid[0]
        raw_time = proxy.get("proxy_first_time")
        legacy_time = execution.local_timestamp(raw_time) if raw_time is not None and str(raw_time) and not pd.isna(raw_time) else None
        frame = self.strategy.stage827_minute_by_symbol.get(str(order.vt_symbol), pd.DataFrame())
        opening = frame.loc[frame["bar_datetime"].map(execution.local_timestamp).eq(expected_start)] if not frame.empty else frame
        if len(opening) > 1:
            raise ValueError(f"intraday_duplicate_open_anchor:{order.vt_symbol}:{expected_start}")
        present = not opening.empty
        corrected = False
        if present:
            item = opening.iloc[0]
            values = [float(item[name]) for name in ("open", "high", "low", "close")]
            opening_price, high, low, close = values
            if not all(np.isfinite(value) and value > 0 for value in values) or low > min(opening_price, close) or high < max(opening_price, close):
                raise ValueError(f"intraday_invalid_open_anchor:{order.vt_symbol}:{expected_start}")
            trade_price, timestamp = opening_price, expected_start
            corrected = legacy_time != expected_start or abs(float(legacy_price)-trade_price) > 1e-8
            price_source = "canonical_session_first_minute_open"
            timing_source = "canonical_session_first_minute"
            proxy.update(proxy_price=trade_price, proxy_first_time=timestamp.isoformat(),
                         proxy_last_time=timestamp.isoformat(), proxy_bar_count=1)
        else:
            # Diagnostic runs may expose unresolved legacy execution, but never
            # promote it to a verified first session minute. Strict runs stop.
            trade_price = float(legacy_price)
            timestamp = legacy_time if legacy_time in grid else expected_start
            price_source = legacy_source
            timing_source = "unverified_legacy_proxy" if legacy_time is not None else "unverified_daily_open"
        request = {
            "vt_symbol": str(order.vt_symbol), "trading_date": trading_date.date().isoformat(),
            "expected_start": expected_start.isoformat(), "actual_time": timestamp.isoformat() if present else "",
            "anchor_present": present, "source": price_source, "price": trade_price,
            "corrected_legacy_proxy": corrected, "legacy_time": legacy_time.isoformat() if legacy_time is not None else "",
            "legacy_price": float(legacy_price), "legacy_source": str(legacy_source),
            "coverage_status": "complete" if present else "incomplete",
            "order_id": str(order.vt_orderid), "offset": str(order.offset.value),
        }
        if not hasattr(self, "execution_anchor_requests"):
            self.execution_anchor_requests = []
        self.execution_anchor_requests.append(request)
        if not present and getattr(self.strategy, "stage827_require_complete_minutes", True):
            raise ValueError(f"intraday_open_anchor_missing:{order.vt_symbol}:{trading_date.date()}:{expected_start}")
        return {"price": trade_price, "source": price_source, "proxy": proxy,
                "execution_datetime": timestamp, "trading_date": trading_date.date(),
                "execution_time_source": timing_source, "anchor_coverage_status": request["coverage_status"],
                "expected_session_start": expected_start.isoformat(), "corrected_legacy_proxy": corrected,
                "legacy_proxy_time": request["legacy_time"], "legacy_proxy_price": float(legacy_price)}

    def cross_delayed_orders(self) -> None:
        # One chronological queue across ordinary fills and synthetic actions.
        # Stable serials resolve equal timestamps without consulting P&L.
        self._stage827_execution_queue: list[tuple[Any, ...]] = []
        self._stage827_queue_serial = 0
        self._stage827_order_contexts = {}
        try:
            for order in list(self.active_limit_orders.values()):
                bar = self.bars.get(order.vt_symbol)
                if bar is None:
                    continue
                context = self._stage827_order_context(order, bar)
                self._stage827_order_contexts[order.vt_orderid] = context
                heapq.heappush(self._stage827_execution_queue,
                              (context["execution_datetime"], self._stage827_queue_serial, "ordinary", order, bar))
                self._stage827_queue_serial += 1
            while self._stage827_execution_queue:
                _, _, kind, order, payload = heapq.heappop(self._stage827_execution_queue)
                if kind == "ordinary":
                    if order.vt_orderid in self.active_limit_orders:
                        self._fill_order(order, payload)
                else:
                    open_trade, event = payload
                    self._fill_synthetic_intraday_close(order, open_trade, event)
        except Exception as exc:
            self.intraday_execution_failure = f"{type(exc).__name__}: {exc!r}"
            raise
        finally:
            self._stage827_execution_queue = None
            self._stage827_order_contexts = {}

    def run_backtesting(self) -> None:
        super().run_backtesting()
        # vn.py catches errors inside the daily loop.  Never report a partial
        # fail-closed replay as a completed backtest merely because it returned.
        if getattr(self, "intraday_execution_failure", ""):
            raise RuntimeError(self.intraday_execution_failure)

    def _fill_order(self, order: Any, bar: BarData) -> None:
        context = getattr(self, "_stage827_order_contexts", {}).get(order.vt_orderid)
        if context is None:
            context = self._stage827_order_context(order, bar)
        trade_price, price_source, proxy = context["price"], context["source"], context["proxy"]
        if trade_price <= 0 or float(order.price) <= 0:
            return
        if order.status == Status.SUBMITTING:
            order.status = Status.NOTTRADED
            self.strategy.update_order(order)
        order.traded = order.volume
        order.status = Status.ALLTRADED
        self.strategy.update_order(order)
        self.active_limit_orders.pop(order.vt_orderid, None)
        self.trade_count += 1
        trade = TradeData(
            symbol=order.symbol, exchange=order.exchange, orderid=order.orderid,
            tradeid=str(self.trade_count), direction=order.direction, offset=order.offset,
            price=trade_price, volume=order.volume,
            datetime=self._stage827_physical_datetime(context["execution_datetime"]),
            gateway_name=self.gateway_name,
        )
        trade.trading_date = context["trading_date"]
        trade.execution_datetime = trade.datetime
        trade.signal_datetime = order.datetime
        trade.signal_order_id = order.vt_orderid
        self.strategy.update_trade(trade)
        self.trades[trade.vt_tradeid] = trade
        self.source_counter[price_source] += 1
        self.trade_usage_rows.append({
            "trade_id": trade.vt_tradeid, "orderid": str(order.orderid),
            "signal_date": s778.s653.s517.s506.s501._naive_date(order.datetime),
            "fill_date": pd.Timestamp(trade.trading_date), "trading_date": trade.trading_date.isoformat(),
            "execution_datetime": execution.local_timestamp(trade.datetime).isoformat(),
            "execution_time_source": context["execution_time_source"],
            "anchor_coverage_status": context["anchor_coverage_status"],
            "expected_session_start": context["expected_session_start"],
            "corrected_legacy_proxy": context["corrected_legacy_proxy"],
            "legacy_proxy_time": context["legacy_proxy_time"], "legacy_proxy_price": context["legacy_proxy_price"],
            "signal_datetime": execution.local_timestamp(order.datetime).isoformat(),
            "signal_order_id": order.vt_orderid,
            "vt_symbol": str(order.vt_symbol),
            "direction": s778.s653.s517.s506.s501._direction_text(order.direction),
            "offset": s778.s653.s517.s506.s501._offset_text(order.offset),
            "order_price": float(order.price), "trade_price": float(trade_price),
            "price_delta": float(trade_price) - float(order.price), "order_volume": float(order.volume),
            "price_source": price_source, "proxy_bar_count": proxy.get("proxy_bar_count", np.nan),
            "proxy_first_time": proxy.get("proxy_first_time", ""), "proxy_last_time": proxy.get("proxy_last_time", ""),
            "execution_policy": execution.EXECUTION_POLICY,
            "effective_tick": execution.effective_pricetick(order.vt_symbol, trade.trading_date, self.priceticks[order.vt_symbol]),
            "tick_basis": execution.pricetick_basis(order.vt_symbol),
        })
        if order.offset == Offset.OPEN:
            hook = getattr(self.strategy, "stage827_intraday_exit_after_open_trade", None)
            event = hook(trade) if callable(hook) else None
            if event:
                sequence = self._stage827_event_sequence(event)
                queue = getattr(self, "_stage827_execution_queue", None)
                if queue is None:
                    self._fill_synthetic_intraday_close(order, trade, event)
                else:
                    for index, item in enumerate(sequence):
                        isolated = {**event, "synthetic_trades": [item], "_sequence_index": index,
                                    "_sequence_final": index == len(sequence)-1}
                        heapq.heappush(queue, (execution.local_timestamp(item["time"]), self._stage827_queue_serial,
                                              "synthetic", order, (trade, isolated)))
                        self._stage827_queue_serial += 1

    def _stage827_physical_datetime(self, value: Any) -> datetime:
        timestamp = execution.local_timestamp(value)
        timezone = pd.Timestamp(self.datetime).tzinfo
        return (timestamp.tz_localize(timezone) if timezone is not None else timestamp).to_pydatetime()

    @staticmethod
    def _stage827_event_sequence(event: dict[str, Any]) -> list[dict[str, Any]]:
        sequence = event.get("synthetic_trades")
        if isinstance(sequence, list) and sequence:
            return sequence
        return [{"action": "close", "source": event.get("exit_reason", "stage827_intraday_c2_1r_stop"),
                 "price": event.get("fill_price", event["stop_price"]), "trigger_price": event["stop_price"],
                 "execution_note": event.get("fill_note", ""), "volume": event["volume"], "time": event["hit_time"]}]

    def _fill_synthetic_intraday_close(self, order: Any, open_trade: TradeData, exit_event: dict[str, Any]) -> None:
        sequence = self._stage827_event_sequence(exit_event)
        for index, item in enumerate(sequence):
            price, volume = float(item["price"]), int(item["volume"])
            if price <= 0 or volume <= 0:
                raise ValueError("intraday_invalid_synthetic_trade")
            opening = item["action"] == "open"
            direction = open_trade.direction if opening else Direction.SHORT if open_trade.direction == Direction.LONG else Direction.LONG
            offset = Offset.OPEN if opening else Offset.CLOSE
            timestamp = self._stage827_physical_datetime(item["time"])
            if execution.local_timestamp(timestamp) < execution.local_timestamp(getattr(open_trade, "execution_datetime", open_trade.datetime)):
                raise ValueError("intraday_synthetic_before_open")
            final = bool(exit_event.get("_sequence_final", index == len(sequence)-1))
            finalize = getattr(self.strategy, "_stage827_finalize_intraday_action", None)
            if callable(finalize):
                finalize(exit_event, item, final=final)
            serial = int(exit_event.get("_sequence_index", index)) + 1
            source = str(item["source"])
            self.trade_count += 1
            trade = TradeData(symbol=order.symbol, exchange=order.exchange,
                orderid=f"{order.orderid}.intraday.{serial}", tradeid=str(self.trade_count),
                direction=direction, offset=offset, price=price, volume=volume,
                datetime=timestamp, gateway_name=self.gateway_name)
            trade.trading_date = _normalize_date(exit_event.get("trading_date", getattr(open_trade, "trading_date", self.datetime))).date()
            trade.execution_datetime = timestamp
            trade.intraday_episode_id = open_trade.vt_tradeid
            trade.signal_datetime = order.datetime
            trade.signal_order_id = order.vt_orderid
            trade.exit_reason = "" if opening else source
            self.strategy.update_trade(trade)
            self.trades[trade.vt_tradeid] = trade
            self.source_counter[source] += 1
            self.trade_usage_rows.append({
                "trade_id": trade.vt_tradeid, "orderid": str(trade.orderid),
                "signal_date": s778.s653.s517.s506.s501._naive_date(order.datetime),
                "fill_date": pd.Timestamp(trade.trading_date), "trading_date": trade.trading_date.isoformat(),
                "execution_datetime": execution.local_timestamp(timestamp).isoformat(),
                "execution_time_source": "trigger_minute", "vt_symbol": str(order.vt_symbol),
                "direction": s778.s653.s517.s506.s501._direction_text(direction),
                "offset": "Open" if opening else "Close", "order_price": float(item.get("trigger_price", price)),
                "trade_price": price, "price_delta": price-float(item.get("trigger_price", price)),
                "order_volume": float(volume), "price_source": source, "proxy_bar_count": 1,
                "proxy_first_time": item["time"], "proxy_last_time": item["time"],
                "execution_note": item.get("execution_note", ""), "execution_policy": execution.EXECUTION_POLICY,
                "effective_tick": execution.effective_pricetick(order.vt_symbol, trade.trading_date, self.priceticks[order.vt_symbol]),
                "tick_basis": execution.pricetick_basis(order.vt_symbol),
                "intraday_episode_id": open_trade.vt_tradeid,
            })

    def calculate_result(self):
        # Upstream daily accounting uses datetime.date().  Use accounting copies
        # so a Friday/Saturday execution is booked to its Monday trading date,
        # while the canonical trade tape retains physical timestamps.
        physical_trades = self.trades
        accounting_trades = {}
        for key, trade in physical_trades.items():
            accounting = copy(trade)
            accounting.datetime = _normalize_date(getattr(trade, "trading_date", trade.datetime)).to_pydatetime()
            accounting_trades[key] = accounting
        self.trades = accounting_trades
        try:
            return super().calculate_result()
        finally:
            self.trades = physical_trades


def _profile(metadata: dict[str, Any], *, enabled: bool) -> dict[str, Any]:
    profile = s825._profile(metadata)
    spec = profile["spec"]
    suffix = "c2_engine" if enabled else "baseline"
    capital = replace(
        spec.capital,
        variant=f"stage827_stage819_{suffix}_2018",
        label=f"Stage827 Stage819 {suffix} 2018 start",
        note=(
            f"{spec.capital.note} | Stage827 isolated strategy subclass. "
            "C2 intraday first-1R stop is enabled only for the C arm."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_stage827_intraday_c2_stop": bool(enabled),
        "stage827_intraday_c2_stop_r": STOP_R,
        "stage827_intraday_c2_confirm_r": CONFIRM_R,
    }
    result = dict(profile)
    result["profile"] = f"stage827_stage819_{suffix}"
    result["strategy_cls"] = QmtRollPortfolioStrategyStage827C2
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=result["profile"])
    return result


def _run_profile(profile: dict[str, Any], metadata: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    spec = replace(profile["spec"])
    original_start = s778.s653.s517.START_DT
    original_end = s778.s653.s517.END_DT
    original_preload = s778.s653.s517.PRELOAD_START_DT
    try:
        s778.s653.s517.START_DT = START.to_pydatetime()
        s778.s653.s517.END_DT = END.to_pydatetime()
        s778.s653.s517.PRELOAD_START_DT = s772._preload_for_start(START).to_pydatetime()

        s778.s653.s517.assert_stage196_database_sentinels()
        s778.s653.s517.s506._patch_stage506_raw_roots()
        preload_start = max(
            s778.s653.s517.PRELOAD_START_DT,
            s778.s653.s517.START_DT - pd.Timedelta(days=365).to_pytimedelta(),
        )
        _, open_map = s778.s653.s517.s506.s501._seed_proxy_maps()
        engine = Stage827IntradayC2Engine(open_map)
        engine.output = lambda msg: None
        engine.set_parameters(
            vt_symbols=metadata["vt_symbols"],
            interval=Interval.DAILY,
            start=preload_start,
            end=s778.s653.s517.END_DT,
            rates=metadata["rates"],
            slippages=metadata["slippages"],
            sizes=metadata["sizes"],
            priceticks=metadata["priceticks"],
            capital=spec.capital.c3_capital,
        )
        setting = s772._build_setting(
            metadata=metadata,
            spec=spec,
            base_c3_overrides=dict(s513._c3_overrides(START.to_pydatetime())),
            start=START,
        )
        engine.add_strategy(profile["strategy_cls"], setting)
        engine.load_data()
        engine.run_backtesting()
        daily_df = engine.calculate_result()
        if daily_df is None or daily_df.empty:
            raise RuntimeError(f"empty daily result: {profile['profile']}")

        daily = daily_df.copy()
        daily = daily.loc[(daily.index >= START.date()) & (daily.index <= END.date())].reset_index()
        daily.rename(columns={"index": "date"}, inplace=True)
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
        for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
            daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
        daily["variant"] = spec.capital.variant
        daily["combo_variant"] = spec.capital.variant
        daily["label"] = spec.capital.label
        daily["risk_multiplier"] = spec.capital.risk_multiplier
        daily["note"] = spec.capital.note

        positions = s778.build_positions_df(engine)
        if not positions.empty:
            positions["variant"] = spec.capital.variant
            positions["combo_variant"] = spec.capital.variant
            positions["label"] = spec.capital.label
            positions["risk_multiplier"] = spec.capital.risk_multiplier
            margin_daily, _ = s513._position_margin(positions, metadata)
        else:
            margin_daily = pd.DataFrame(
                columns=["variant", "combo_variant", "date", "c3_margin_exact", "c3_active_contracts", "c3_active_products"]
            )
        combined = s772._combine_daily(daily, margin_daily, spec)
        strategy = getattr(engine, "strategy", None)
        frames = {
            "trades": s778.build_trades_df(engine),
            "positions": positions,
            "entry_risk": s778.build_entry_risk_diagnostics_df(engine),
            "entry_candidates": s778.build_entry_candidate_snapshots_df(engine),
            "trade_events": pd.DataFrame(getattr(strategy, "trade_event_diagnostics", []) if strategy else []),
            "intraday_events": pd.DataFrame(getattr(strategy, "stage827_intraday_c2_events", []) if strategy else []),
        }
        for frame in frames.values():
            if frame.empty:
                continue
            frame["profile"] = profile["profile"]
            frame["start_month"] = START.strftime("%Y-%m")
            frame["variant"] = spec.capital.variant
        return combined, frames
    finally:
        s778.s653.s517.START_DT = original_start
        s778.s653.s517.END_DT = original_end
        s778.s653.s517.PRELOAD_START_DT = original_preload


def _metric(profile: dict[str, Any], combined: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary, curve = s804._metric_from_combined(profile, combined, START)
    summary["arm"] = profile["profile"]
    curve["arm"] = profile["profile"]
    return summary, curve


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    base = summary[summary["arm"].str.endswith("baseline")].iloc[0]
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        rows.append(
            {
                "arm": row["arm"],
                "end_equity": row["end_equity"],
                "end_equity_delta_vs_A": row["end_equity"] - base["end_equity"],
                "total_return_pct": row["total_return_pct"],
                "max_dd_pct": row["max_dd_pct"],
                "max_dd_delta_vs_A": row["max_dd_pct"] - base["max_dd_pct"],
                "sharpe": row["sharpe"],
                "sharpe_delta_vs_A": row["sharpe"] - base["sharpe"],
                "total_slippage": row["total_slippage"],
                "total_slippage_delta_vs_A": row["total_slippage"] - base["total_slippage"],
                "total_trade_count": row["total_trade_count"],
                "total_trade_count_delta_vs_A": row["total_trade_count"] - base["total_trade_count"],
                "win_rate_pct": row["nonzero_daily_win_rate_pct"],
            }
        )
    return pd.DataFrame(rows)


def _write_report(summary: pd.DataFrame, comparison: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> None:
    intraday = frames.get("intraday_events", pd.DataFrame())
    c_closed = frames.get("closed_lots", pd.DataFrame())
    intraday_by_year = pd.DataFrame()
    if not intraday.empty:
        data = intraday.copy()
        data["datetime"] = pd.to_datetime(data["datetime"], errors="coerce")
        data["year"] = data["datetime"].dt.year
        intraday_by_year = (
            data.groupby("year", dropna=False)
            .agg(events=("vt_symbol", "size"), products=("product_vt_symbol", "nunique"), volume=("volume", "sum"))
            .reset_index()
        )

    lines = [
        "# Stage827 Stage819 C2组合引擎A/C",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        f"- 区间：`{START.date()}` 到 `{END.date()}`",
        "- 阶段性质：隔离 subclass + 自定义 engine 的完整组合回放尝试；不改正式策略文件、不连接 CTP、不调用下单。",
        "",
        "## 规则语义",
        "",
        "- A：Stage819 原始候选，使用同一 subclass 但关闭 C2。",
        "- C：开仓成交后，用入场日分钟K判断 `1R` 逆向止损是否先于 `1R` 顺向确认；若是，则同日合成平仓成交，更新组合持仓、资金和后续信号路径。",
        "- 同一根分钟K同时触发止损和确认，按保守口径记为止损先发生。",
        "",
        "## Result",
        "",
        _md_table(comparison, max_rows=10),
        "",
        "## Intraday Stop Events By Year",
        "",
        _md_table(intraday_by_year, max_rows=30),
        "",
        "## Closed Lots Snapshot",
        "",
        _md_table(
            c_closed[["lot_id", "vt_symbol", "direction", "entry_date", "exit_date", "realized_pnl", "exit_reason", "signal"]].head(20)
            if not c_closed.empty
            else pd.DataFrame(),
            max_rows=20,
        ),
        "",
        "## Judgment",
        "",
        "- 本阶段比 Stage826 更接近真实组合路径，因为 C2 平仓会影响后续持仓、资金、保证金和信号再入场。",
        "- 若 C 提高收益但恶化回撤，不能晋级；下一步应先归因二阶风险，而不是调参数救结果。",
        "- 仍需谨慎：当前 engine 是日线引擎内合成同日分钟止损成交，不是完整分钟bar组合引擎。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    global _GLOBAL_MINUTE_BY_SYMBOL
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s825._load_minute_bars(vt_symbols)
    _GLOBAL_MINUTE_BY_SYMBOL = s825._minute_groups(minute_bars)

    profiles = [_profile(metadata, enabled=False), _profile(metadata, enabled=True)]
    summaries: list[pd.DataFrame] = []
    curves: list[pd.DataFrame] = []
    merged_frames: dict[str, list[pd.DataFrame]] = {
        "trades": [],
        "entry_risk": [],
        "entry_candidates": [],
        "trade_events": [],
        "intraday_events": [],
    }
    closed_frames: list[pd.DataFrame] = []

    for profile in profiles:
        combined, frames = _run_profile(profile, metadata)
        summary, curve = _metric(profile, combined)
        summaries.append(summary)
        curves.append(curve)
        for key in merged_frames:
            frame = frames.get(key, pd.DataFrame())
            if not frame.empty:
                merged_frames[key].append(frame)
        trades = frames.get("trades", pd.DataFrame()).copy()
        entry_risk = frames.get("entry_risk", pd.DataFrame()).copy()
        entry_candidates = frames.get("entry_candidates", pd.DataFrame()).copy()
        closed = s719._build_closed_lots(trades, entry_risk, entry_candidates, metadata)
        if not closed.empty:
            closed["arm"] = profile["profile"]
            closed["variant"] = profile["spec"].capital.variant
            closed_frames.append(closed)

    summary = pd.concat(summaries, ignore_index=True, sort=False)
    curve = pd.concat(curves, ignore_index=True, sort=False)
    comparison = _comparison(summary)
    output_frames = {
        key: pd.concat(value, ignore_index=True, sort=False) if value else pd.DataFrame()
        for key, value in merged_frames.items()
    }
    output_frames["closed_lots"] = pd.concat(closed_frames, ignore_index=True, sort=False) if closed_frames else pd.DataFrame()

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVE_PATH, index=False, encoding="utf-8-sig")
    output_frames["trades"].to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    output_frames["entry_risk"].to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    output_frames["entry_candidates"].to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    output_frames["trade_events"].to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    output_frames["intraday_events"].to_csv(INTRADAY_EVENTS_PATH, index=False, encoding="utf-8-sig")
    output_frames["closed_lots"].to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    _write_report(summary, comparison, output_frames)

    c_row = comparison[comparison["arm"].str.endswith("c2_engine")].iloc[0].to_dict()
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "formal_ab_triggered": False,
        "rules": {
            "C2_engine": {
                "stop_r": STOP_R,
                "confirm_r": CONFIRM_R,
                "same_bar_policy": "conservative_stop_first",
            }
        },
        "comparison": comparison.to_dict("records"),
        "intraday_event_count": int(len(output_frames["intraday_events"])),
        "decision": "engine_ac_research_only_not_promoted",
        "candidate_result": c_row,
        "overfit_reflection": (
            "C2 is still frozen at 1R/1R. The engine replay increases evidence quality, but minute coverage and "
            "synthetic same-day close semantics still require more validation before promotion."
        ),
        "continue_value": (
            "Continue if C2 beats A in this engine path; next validation should be monthly starts and cost stress, not threshold tuning."
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curve": str(CURVE_PATH),
            "trades": str(TRADES_PATH),
            "entry_risk": str(ENTRY_RISK_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "trade_events": str(TRADE_EVENTS_PATH),
            "intraday_events": str(INTRADAY_EVENTS_PATH),
            "closed_lots": str(CLOSED_LOTS_PATH),
            "report": str(REPORT_PATH),
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("comparison")
    print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()
