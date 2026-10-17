"""C_TS research adapter: freeze native allocation, activate only at real fill.

This factory leaves the upstream portfolio implementation and ordered setup
machine unchanged.  It carries no alternative sizing or daily fill model.
"""
from __future__ import annotations

from copy import copy, deepcopy
from datetime import datetime
import math
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from stage027_ordered_state import OrderedSetupMachine


def _local_datetime(value):
    """Minute frames use naive Shanghai timestamps, as the original engine."""
    moment = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if moment.tzinfo is not None:
        moment = moment.astimezone(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None)
    return moment


def build_ordered_strategy(base, weekly_lookup, fi_lookup, next_days, arm="C_TS"):
    """Return the isolated C_TS strategy class around the accepted native base."""
    if arm != "C_TS":
        raise ValueError("unsupported_ordered_execution_arm")

    class OrderedResearch(base):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.ts_machine = OrderedSetupMachine(arm)
            self.ts_pending_intents = []
            self.ts_decision_audit = []
            self.ts_fill_audit = []
            self.ts_conditional_orders = {}
            self._ts_conditional_entries = {}
            self._ts_close_bars = None
            self._ts_close_day = None
            self._ts_observed = False

        def on_bars(self, bars):
            if not bars:
                return super().on_bars(bars)
            day = next(iter(bars.values())).datetime.date().isoformat()
            self.ts_pending_intents = []
            self._ts_close_bars, self._ts_close_day = bars, day
            self._ts_observed = False
            try:
                # The native method alone updates AMs, estimates the account,
                # allocates the full native batch, and processes existing lots.
                result = super().on_bars(bars)
                if not self._ts_observed:
                    self._ts_observe_close({}, {})
                return result
            finally:
                self._ts_close_bars = self._ts_close_day = None

        def _plan_flat_entry_candidates(self, day_contexts):
            plans = super()._plan_flat_entry_candidates(day_contexts)
            contexts = {context.product_vt_symbol: context for context in day_contexts}
            self._ts_observe_close(plans, contexts)
            return plans

        def _build_daily_env_gate_snapshot(self, day_contexts):
            # Environment, AM/history, and signals all retain the complete D
            # close.  Only the following holding-management loop gets a bar
            # covering this lot's lifetime rather than its pre-entry history.
            snapshot = super()._build_daily_env_gate_snapshot(day_contexts)
            for context in day_contexts:
                if not context.current_pos:
                    continue
                day = context.target_bar.datetime.date().isoformat()
                entry = self._ts_conditional_entries.get((context.product_vt_symbol, day))
                if entry is None or entry["contract"] != context.target_contract:
                    continue
                # Reuse the canonical session/coverage/price validator rather
                # than silently aggregating whatever minutes happen to exist.
                import qmt_roll_intraday_execution as execution
                trade = SimpleNamespace(vt_symbol=entry["contract"],
                    datetime=datetime.fromisoformat(day), trading_date=day,
                    execution_datetime=entry["execution_datetime"])
                frame = execution.entry_session(self, trade)
                if self.minute_scan_requests[-1]["missing_bar_count"]:
                    raise ValueError("intraday_minute_coverage:conditional_holding_post_entry")
                if frame.empty:
                    raise ValueError("conditional_holding_post_entry_minutes_missing")
                lifetime_bar = copy(context.target_bar)
                lifetime_bar.open_price = entry["fill_price"]
                lifetime_bar.high_price = max(entry["fill_price"], float(frame["high"].max()))
                lifetime_bar.low_price = min(entry["fill_price"], float(frame["low"].min()))
                context.target_bar = lifetime_bar
                if context.actual_bar is not None and context.actual_bar.vt_symbol == entry["contract"]:
                    context.actual_bar = copy(lifetime_bar)
            return snapshot

        def _ts_actual_position(self, product, target_contract, bars):
            state = self.states[product]
            # Include every known contract for this product, not only the new
            # mapped contract: an existing old-contract lot is a hard block.
            position_bars = dict(bars)
            for contract, source in self.source_symbol_by_contract.items():
                if source == product:
                    position_bars.setdefault(contract, None)
            _, position, _ = self._resolve_actual_position(state, target_contract, position_bars)
            return int(position)

        def _ts_observe_close(self, plans, contexts):
            if self._ts_observed:
                return
            self._ts_observed = True
            day, bars = self._ts_close_day, self._ts_close_bars
            # 2019 is an indicator warmup only.  Preparation starts with an
            # empty machine on the first actual 2020 close.
            if day is None or day < "2020-01-01":
                return
            mapping = self.daily_mapping.get(day, {})
            ranks = {product: index for index, product in enumerate(plans, start=1)}
            for product in self.product_symbols:
                target = mapping.get(product, "")
                target_bar = bars.get(target) if target else None
                plan = plans.get(product)
                native_status = str(plan.get("candidate_status", "")) if plan else None
                quantity = int(plan.get("volume") or 0) if plan else 0
                native_selected = native_status == "opened" and quantity > 0
                if not target:
                    observation = self.ts_machine.cancel(product, day, "target_mapping_missing")
                elif target_bar is None or target_bar.datetime.date().isoformat() != day:
                    observation = self.ts_machine.cancel(product, day, "target_real_bar_missing")
                else:
                    high, low = float(target_bar.high_price), float(target_bar.low_price)
                    tick = float(self.get_pricetick(target))
                    if not all(math.isfinite(value) and value > 0 for value in (high, low, tick)) or high < low:
                        observation = self.ts_machine.cancel(product, day, "target_real_bar_invalid")
                    else:
                        name, exchange = product.rsplit(".", 1)
                        weekly = weekly_lookup.get(day, f"{exchange}.{name}".upper())
                        force = fi_lookup.get((day, target), {"ready": False, "fi2": None})
                        eligible, _ = self._ai_product_pool_entry_allowed(product, datetime.fromisoformat(day))
                        observation = self.ts_machine.on_close(
                            product=product, contract=target, day=day, next_day=next_days.get(day),
                            high=high, low=low, tick=tick,
                            weekly_ready=bool(weekly["ready"]), weekly_direction=weekly["direction"],
                            weekly_asof=weekly.get("weekly_asof"), fi_ready=bool(force["ready"]),
                            fi2=force.get("fi2"), eligible=bool(eligible),
                            position_open=self._ts_actual_position(product, target, bars) != 0,
                            native_signal=str(plan["signal"]) if native_selected else None)
                intent = observation["intent"]
                if native_selected:
                    if intent is not None:
                        context = contexts[product]
                        rank = int(plan.get("selection_pairwise_rank") or ranks[product])
                        frozen = dict(sizing=deepcopy(plan["sizing"]), volume=quantity,
                            target_contract=target, target_bar=copy(context.target_bar),
                            history=deepcopy(context.history), signal_data=deepcopy(context.signal_data),
                            direction=str(plan["direction"]), signal=str(plan["signal"]))
                        self.ts_pending_intents.append({**intent, "rank": rank, "plan": frozen})
                        plan["candidate_status"] = "conditional_pending"
                        plan["skip_reason"] = "triple_screen_pending_real_trigger"
                    elif not observation["baseline_fallback"]:
                        plan["candidate_status"] = "filtered"
                        plan["skip_reason"] = "triple_screen_" + str(
                            observation["cancel_reason"] or observation["decision"])
                self.ts_decision_audit.append(dict(
                    arm=arm, date=day, signal_day=day, execution_day=next_days.get(day),
                    product=product, contract=target, native_status=native_status,
                    native_volume=quantity, candidate_status=plan["candidate_status"] if plan else None,
                    decision=observation["decision"], baseline_fallback=observation["baseline_fallback"],
                    cancel_reason=observation["cancel_reason"], setup_id=observation["setup_id"],
                    setup_day=observation["setup_day"], intent_id=intent["intent_id"] if intent else None))

        def _record_entry_candidate_snapshot(self, **fields):
            result = super()._record_entry_candidate_snapshot(**fields)
            if fields["candidate_status"] == "conditional_pending":
                # Reserve at the original product-loop location.  Reserving at
                # batch-planning time would change earlier existing-lot adds.
                sizing = fields["sizing_snapshot"]
                self._reserve_intrabar_entry(fields["product_vt_symbol"], sizing,
                    int(sizing["selected_volume"]), count_active_position=True)
            return result

        def ts_activate_intent(self, item, fill_price):
            plan = item["plan"]
            quantity = int(plan["volume"])
            fill_price = float(fill_price)
            if quantity <= 0:
                raise ValueError("conditional_nonpositive_quantity")
            if not math.isfinite(fill_price) or fill_price <= 0:
                raise ValueError("conditional_invalid_fill_price")
            product, target = item["product"], plan["target_contract"]
            if self._ts_actual_position(product, target, {}):
                raise ValueError("conditional_product_not_flat")
            state = self.states[product]
            self._open_position(state, target, plan["direction"], quantity,
                plan["target_bar"], plan["signal"], plan["history"], plan["signal_data"],
                sizing_snapshot=plan["sizing"])
            for layer in state.layers:
                layer.highest_price = layer.lowest_price = fill_price
            self._apply_state_target(state)

        def ts_commit_fill(self, item, execution_day, order_id, context):
            receipt = self.ts_machine.on_fill(item["intent_id"], execution_day)
            key = (item["product"], execution_day)
            entry = dict(contract=item["contract"], signal_day=item["signal_day"],
                execution_datetime=_local_datetime(context["execution_datetime"]),
                fill_price=float(context["fill_price"]))
            if key not in self._ts_conditional_entries or (
                    entry["execution_datetime"] < self._ts_conditional_entries[key]["execution_datetime"]):
                self._ts_conditional_entries[key] = entry
            self.ts_fill_audit.append(dict(
                arm=arm, intent_id=item["intent_id"], setup_id=receipt["setup_id"],
                product=item["product"], contract=item["contract"], signal_day=item["signal_day"],
                execution_day=execution_day, order_id=str(order_id),
                volume=int(item["plan"]["volume"]), trigger=float(item["trigger"]),
                stop_price=float(item["plan"]["sizing"]["stop_price"]),
                **{key: context.get(key) for key in (
                    "execution_datetime", "fill_price", "intrabar", "actual_risk_amount",
                    "forecast_risk_amount", "actual_margin_amount", "forecast_margin_amount")}))

        def stage827_intraday_exit_after_open_trade(self, trade):
            metadata = self.ts_conditional_orders.get(getattr(trade, "vt_orderid", ""))
            if metadata is None:
                metadata = self.ts_conditional_orders.get(getattr(trade, "orderid", ""))
            if not metadata or not metadata["intrabar"]:
                return super().stage827_intraday_exit_after_open_trade(trade)
            original = self.stage827_minute_by_symbol
            frame = original[trade.vt_symbol].copy(deep=True)
            stamp = _local_datetime(metadata["execution_datetime"])
            selected = frame["bar_datetime"] == stamp
            if sum(selected) != 1:
                raise ValueError("conditional_entry_minute_not_unique")
            frame.loc[selected, "open"] = float(metadata["fill_price"])
            self.stage827_minute_by_symbol = {**original, trade.vt_symbol: frame}
            try:
                return super().stage827_intraday_exit_after_open_trade(trade)
            finally:
                self.stage827_minute_by_symbol = original

    OrderedResearch.__name__ = "Stage028OrderedC_TS"
    return OrderedResearch
