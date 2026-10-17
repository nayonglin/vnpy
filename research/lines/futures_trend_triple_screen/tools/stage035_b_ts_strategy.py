"""Independent B first signal over the frozen ordered execution/holding path.

Only the initial flat candidate domain, its known trigger budget, and B audit
identity change. Stage028 continues to own activation, lifetime holding bars,
and the native same-minute stop/retry delegation.
"""
from __future__ import annotations

from copy import copy, deepcopy
from datetime import datetime
import math

from stage027_ordered_state import OrderedSetupMachine
from stage028_ordered_strategy import build_ordered_strategy
from stage035_b_ts_pricing import build_trigger_priced_base, finalize_b_plan_batch


B_SIGNALS = ("long_triple_screen", "short_triple_screen")


def _budget_fields(sizing):
    return {key: deepcopy(value) for key, value in sizing.items() if key.startswith("b_ts_")}


def build_b_strategy(native_base, weekly_lookup, fi_lookup, next_days):
    """Return B_TS, retaining the shared native holding/conditional machinery."""
    priced = build_trigger_priced_base(native_base)
    shared = build_ordered_strategy(priced, weekly_lookup, fi_lookup, next_days, arm="C_TS")

    class BResearch(shared):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.ts_machine = OrderedSetupMachine("B_TS")
            self.ts_trigger_by_key = {}
            self.b_ts_final_budget_audit = []
            self._b_ts_observations = {}
            self._b_ts_decisions = {}

        def _can_open_short_signal(self, signal):
            if signal == "short_triple_screen":
                return True
            return super()._can_open_short_signal(signal)

        def _ts_observe_close(self, plans, contexts):
            """Observe every product once before planning; never inherit C fallback."""
            if self._ts_observed:
                return
            self._ts_observed = True
            self._b_ts_observations = {}
            self._b_ts_decisions = {}
            day, bars = self._ts_close_day, self._ts_close_bars
            # Native daily consumers reread this same context after the planner.
            # Clear flat native signals even on warmup/unknown/rejected days.
            for context in contexts.values():
                if not context.current_pos:
                    context.signal_data = dict(context.signal_data)
                    context.signal_data["signal"] = ""
            if day is None or day < "2020-01-01":
                return
            mapping = self.daily_mapping.get(day, {})
            for product in self.product_symbols:
                target = mapping.get(product, "")
                target_bar = bars.get(target) if target else None
                context = contexts.get(product)
                filter_reason = ""
                if not target:
                    observation = self.ts_machine.cancel(product, day, "target_mapping_missing")
                elif target_bar is None or target_bar.datetime.date().isoformat() != day:
                    observation = self.ts_machine.cancel(product, day, "target_real_bar_missing")
                else:
                    high, low, tick = (float(target_bar.high_price), float(target_bar.low_price),
                                       float(self.get_pricetick(target)))
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
                            native_signal=None)
                intent = observation["intent"]
                executable_context = (context is not None and not context.current_pos
                    and context.target_contract == target)
                if intent is not None:
                    if not executable_context:
                        filter_reason = "no_executable_context"
                    elif not self._passes_entry_filters(intent["native_signal"], context.history):
                        filter_reason = "generic_entry_filters"
                    else:
                        signal = str(intent["native_signal"])
                        context.signal_data["signal"] = signal
                        context.signal_data["risk_mode"] = (
                            self._volume_open_interest_risk_mode(context.history)
                            or self._open_interest_risk_mode(context.history) or "regular")
                        direction = "long" if intent["direction"] == 1 else "short"
                        self.ts_trigger_by_key[(day, target, direction)] = float(intent["trigger"])
                decision = dict(
                    arm="B_TS", date=day, signal_day=day, execution_day=next_days.get(day),
                    product=product, contract=target, native_status=None, native_volume=0,
                    candidate_status=None, decision=observation["decision"], baseline_fallback=False,
                    cancel_reason=observation["cancel_reason"], setup_id=observation["setup_id"],
                    setup_day=observation["setup_day"], intent_id=intent["intent_id"] if intent else None,
                    signal=intent["native_signal"] if intent else "", filter_reason=filter_reason,
                    direction=("long" if intent["direction"] == 1 else "short") if intent else "",
                    signal_close=float(target_bar.close_price) if target_bar is not None else None,
                    b_ts_trigger=float(intent["trigger"]) if intent else None)
                self._b_ts_observations[product] = observation
                self._b_ts_decisions[product] = decision
                self.ts_decision_audit.append(decision)

        def _plan_flat_entry_candidates(self, day_contexts):
            contexts = {context.product_vt_symbol: context for context in day_contexts}
            self._ts_observe_close({}, contexts)
            # B owns the before-planner observation. Jump over Stage028's C
            # override so it cannot perform a post-planner state transition.
            plans = super(shared, self)._plan_flat_entry_candidates(day_contexts)
            batch_audit = finalize_b_plan_batch(self, plans)
            self.b_ts_final_budget_audit.extend(batch_audit)
            ranks = {product: index for index, product in enumerate(plans, start=1)}
            for product, plan in plans.items():
                observation = self._b_ts_observations.get(product)
                decision = self._b_ts_decisions.get(product)
                if observation is None or decision is None:
                    continue
                sizing = plan["sizing"]
                quantity = int(plan.get("volume") or 0)
                status = str(plan.get("candidate_status") or "")
                decision.update(native_status=status, native_volume=quantity,
                    candidate_status=status, signal=str(plan.get("signal") or ""),
                    risk_mode=str(sizing.get("risk_mode") or "regular"),
                    selection_pairwise_score=plan.get("selection_pairwise_score"),
                    selection_pairwise_rank=plan.get("selection_pairwise_rank"),
                    skip_reason=str(plan.get("skip_reason") or ""),
                    **_budget_fields(sizing))
                intent = observation["intent"]
                if status != "opened" or quantity <= 0:
                    continue
                if intent is None or plan.get("signal") != intent["native_signal"]:
                    raise ValueError("b_ts_native_signal_leaked_into_initial_plan")
                context = contexts[product]
                rank = int(plan.get("selection_pairwise_rank") or ranks[product])
                frozen = dict(sizing=deepcopy(sizing), volume=quantity,
                    target_contract=context.target_contract, target_bar=copy(context.target_bar),
                    history=deepcopy(context.history), signal_data=deepcopy(context.signal_data),
                    direction=str(plan["direction"]), signal=str(plan["signal"]),
                    rank=rank, signal_close=float(context.target_bar.close_price),
                    trigger=float(intent["trigger"]), **_budget_fields(sizing))
                self.ts_pending_intents.append({**intent, "rank": rank, "plan": frozen})
                plan["candidate_status"] = "conditional_pending"
                plan["skip_reason"] = "triple_screen_pending_real_trigger"
                decision.update(candidate_status=plan["candidate_status"], skip_reason=plan["skip_reason"])
            return plans

        def _record_entry_candidate_snapshot(self, **fields):
            # Stage028 reserves once here, after the native product loop's old
            # holding/add paths, using final sizing.selected_volume.
            snapshots = getattr(self, "entry_candidate_snapshots", [])
            before = len(snapshots)
            result = super()._record_entry_candidate_snapshot(**fields)
            if fields["entry_context"] == "flat_entry" and fields["signal"] in B_SIGNALS:
                sizing = fields["sizing_snapshot"]
                key = (fields["bar"].datetime.date().isoformat(), fields["contract_vt_symbol"], fields["direction"])
                trigger = float(self.ts_trigger_by_key[key])
                if len(snapshots) != before + 1:
                    raise ValueError("b_ts_candidate_snapshot_missing")
                snapshots[-1].update(_budget_fields(sizing), arm="B_TS",
                    signal_close=float(fields["bar"].close_price), b_ts_trigger=trigger,
                    planned_entry_price=trigger, stop_distance=abs(trigger-float(sizing["stop_price"])),
                    risk_per_contract=float(sizing["risk_per_contract"]),
                    margin_per_contract=float(sizing["margin_per_contract"]))
            return result

        def ts_commit_fill(self, item, execution_day, order_id, context):
            # The shared method owns the sole on_fill call and lifetime entry
            # registration; replace only its closed-over C audit identity.
            result = super().ts_commit_fill(item, execution_day, order_id, context)
            self.ts_fill_audit[-1].update(_budget_fields(item["plan"]["sizing"]), arm="B_TS")
            return result

    BResearch.__name__ = "Stage035IndependentB_TS"
    return BResearch
