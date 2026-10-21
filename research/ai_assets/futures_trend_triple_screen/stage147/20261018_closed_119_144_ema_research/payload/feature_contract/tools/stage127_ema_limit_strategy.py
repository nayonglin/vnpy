"""Independent Stage124 initial limit adapter over frozen native accounting.

No runner, model access, readiness writer or financial qualification is provided.
Only flat initial entry price/state change; ordinary holding/roll paths delegate.
"""
from __future__ import annotations
from collections.abc import Mapping
from copy import copy, deepcopy
from dataclasses import replace
from datetime import datetime
import hashlib
import inspect
import math
from pathlib import Path

from stage027_ordered_state import _finite
from stage028_ordered_strategy import build_ordered_strategy, _local_datetime
from stage035_b_ts_pricing import _calculate_trigger_priced_entry, _number, _integer, QMT_SOURCE_SHA256
from stage127_ema_limit_model import MECHANISM_ID, EmaLimitSetupMachine, limit_quote

EMA_SIGNALS = ("long_triple_screen", "short_triple_screen")


def _budget_fields(sizing):
    return {key: deepcopy(value) for key,value in sizing.items() if key.startswith("ema_limit_")}


def _is_limit_flat(signal_data, entry_context):
    return entry_context == "flat_entry" and signal_data.get("signal") in EMA_SIGNALS


def build_limit_priced_base(native_base: type) -> type:
    qmt = next((base for base in native_base.__mro__ if base.__name__ == "QmtRollPortfolioStrategy"
                and base.__module__ == "qmt_roll_portfolio_strategy"), None)
    if qmt is None or hashlib.sha256(Path(inspect.getsourcefile(qmt)).read_bytes()).hexdigest() != QMT_SOURCE_SHA256:
        raise ValueError("ema_limit_unsupported_native_source")

    class LimitPricingQmt(qmt):
        def _calculate_entry_sizing(self, vt_symbol, direction, bar, history, signal_data,
                risk_mode_override=None, entry_context="flat_entry", apply_env_gate=True,
                active_positions_before=None, correlation_snapshot=None):
            if not _is_limit_flat(signal_data, entry_context):
                return super()._calculate_entry_sizing(vt_symbol,direction,bar,history,signal_data,
                    risk_mode_override=risk_mode_override,entry_context=entry_context,apply_env_gate=apply_env_gate,
                    active_positions_before=active_positions_before,correlation_snapshot=correlation_snapshot)
            if self.fixed_size != 0:
                raise ValueError("ema_limit_fixed_size_not_qualified")
            price=float(self.ema_limit_price_by_key[(bar.datetime.date().isoformat(),vt_symbol,direction)])
            stop=float(self._entry_stop_price(direction,bar,history,use_day_extreme=True))
            sign=1 if direction == "long" else -1
            if not all(math.isfinite(x) and x>0 for x in (price,stop)) or sign*(price-stop)<=0:
                return dict(selected_volume=0,ema_limit_reject_reason="invalid_stop_side",stop_price=stop,
                    risk_per_contract=0.,margin_per_contract=0.,risk_mode=signal_data.get("risk_mode","regular"))
            return _calculate_trigger_priced_entry(self,vt_symbol,direction,bar,history,signal_data,
                price,risk_mode_override=risk_mode_override,entry_context=entry_context,apply_env_gate=apply_env_gate,
                active_positions_before=active_positions_before,correlation_snapshot=correlation_snapshot)

    class LimitPricedBase(native_base, LimitPricingQmt):
        def _calculate_entry_sizing(self, vt_symbol, direction, bar, history, signal_data,
                risk_mode_override=None, entry_context="flat_entry", apply_env_gate=True,
                active_positions_before=None, correlation_snapshot=None):
            sizing=super()._calculate_entry_sizing(vt_symbol,direction,bar,history,signal_data,
                risk_mode_override=risk_mode_override,entry_context=entry_context,apply_env_gate=apply_env_gate,
                active_positions_before=active_positions_before,correlation_snapshot=correlation_snapshot)
            if _is_limit_flat(signal_data,entry_context):
                sizing.update(ema_limit_budget_equity_u=float(self.estimated_equity or sizing.get("sizing_equity") or self.base_capital),
                    ema_limit_signal_day=bar.datetime.date().isoformat(),
                    ema_limit_trigger_price=float(self.ema_limit_price_by_key[(bar.datetime.date().isoformat(),vt_symbol,direction)]),
                    ema_limit_contract_size=self.get_size(vt_symbol),ema_limit_pricetick=self.get_pricetick(vt_symbol),
                    ema_limit_min_position_size=self.min_position_size,ema_limit_max_position_size=self.max_position_size)
            return sizing
    return LimitPricedBase


def finalize_ema_plan_batch(strategy, plans):
    """Clamp only originally admitted EMA plans, using pre-clamp gross prefixes.

    All validation completes before any plan mutation. Rank and skipped plans
    never change; these bookkeeping prefixes do not create real reservations.
    """
    values = list(plans.values()) if isinstance(plans, Mapping) else list(plans)
    admitted = [(index, plan) for index, plan in enumerate(values)
        if plan.get("signal") in EMA_SIGNALS and plan.get("candidate_status") == "opened"
        and _integer(plan, "volume") > 0]
    admitted.sort(key=lambda item: (int(item[1].get("selection_pairwise_rank") or 0) or math.inf, item[0]))
    gross = 0.0
    by_cluster = {}
    updates = []
    for _, plan in admitted:
        sizing = plan["sizing"]
        a = _integer(plan, "volume", positive=True)
        if _integer(sizing, "selected_volume") != a:
            raise ValueError("ema_limit_budget_volume_mismatch")
        R = _number(sizing, "risk_amount")
        rho = _number(sizing, "risk_per_contract", positive=True)
        margin = _number(sizing, "margin_per_contract", positive=True)
        T = _number(sizing, "ema_limit_trigger_price", positive=True)
        S = _number(sizing, "stop_price", positive=True)
        size = _number(sizing, "ema_limit_contract_size", positive=True)
        tick = _number(sizing, "ema_limit_pricetick", positive=True)
        margin_ratio = _number(sizing, "margin_ratio", positive=True)
        if (1 if plan["direction"] == "long" else -1) * (T-S) <= 0:
            raise ValueError("ema_limit_invalid_stop_side")
        if not math.isclose(rho, max((T-S if plan["direction"] == "long" else S-T)*size, max(tick*size, 1.0))) or not math.isclose(margin, T*size*margin_ratio):
            raise ValueError("ema_limit_budget_trigger_pricing_mismatch")
        L = _number(sizing, "limited_balance")
        K = _number(sizing, "single_trade_capital_limit")
        E = _number(sizing, "ema_limit_budget_equity_u", positive=True)
        B = _number(sizing, "reserved_margin_before")
        minimum = _integer(sizing, "ema_limit_min_position_size", positive=True)
        maximum = _integer(sizing, "ema_limit_max_position_size", positive=True)
        if minimum > maximum:
            raise ValueError("ema_limit_budget_position_bounds_invalid")
        n_risk, n_margin_original, n_single = int(R // rho), int(L // margin), int(K // margin)
        for key, expected in (("contracts_by_risk", n_risk), ("contracts_by_margin", n_margin_original),
                ("contracts_by_single_trade_cap", n_single)):
            if _integer(sizing, key) != expected:
                raise ValueError(f"ema_limit_budget_contract_count_mismatch:{key}")
        n_margin = int(max(0., L-gross) // margin)
        cluster = str(sizing.get("risk_cluster_name", ""))
        cluster_gross = by_cluster.get(cluster, 0.0)
        broker_on = _integer(sizing, "stage830_broker10_margin_cap_enabled")
        cluster_on = _integer(sizing, "risk_cluster_cap_enabled")
        if broker_on not in (0, 1) or cluster_on not in (0, 1):
            raise ValueError("ema_limit_budget_gate_enabled_invalid")
        broker_cap = broker_multiplier = n_broker = None
        cluster_cap = cluster_reserved = n_cluster = None
        bounds = [a, n_risk, n_margin, n_single, maximum]
        if broker_on:
            broker_cap = _number(sizing, "stage830_broker10_margin_cap_ratio", positive=True)
            broker_multiplier = _number(sizing, "stage830_broker_margin_multiplier", positive=True)
            n_broker = int(max(0., E*broker_cap/broker_multiplier-B-gross) // margin)
            bounds.append(n_broker)
        if cluster_on:
            if not cluster:
                raise ValueError("ema_limit_budget_cluster_missing")
            cluster_cap = _number(sizing, "risk_cluster_cap_amount")
            cluster_reserved = _number(sizing, "risk_cluster_reserved_margin_before")
            n_cluster = int(max(0., cluster_cap-cluster_reserved-cluster_gross) // margin)
            bounds.append(n_cluster)
        q = max(0, min(bounds))
        if 0 < q < minimum:
            q = 0
        reason = "ema_limit_final_budget_zero" if q == 0 else ("ema_limit_final_budget_reduce" if q < a else "within_ema_limit_final_budget")
        fields = dict(volume_before=a, volume_after=q, gross_margin_before=gross,
            gross_cluster_margin_before=cluster_gross, contracts_by_risk=n_risk,
            contracts_by_margin=n_margin, contracts_by_single=n_single, contracts_by_broker=n_broker,
            contracts_by_cluster=n_cluster, max_position_size=maximum, min_position_size=minimum,
            trigger=T, stop_price=S, risk_per_contract=rho, margin_per_contract=margin,
            contract_size=size, pricetick=tick, margin_ratio=margin_ratio, risk_amount=R,
            limited_balance=L, single_trade_capital_limit=K, equity_u=E,
            reserved_margin_before=B, broker_enabled=broker_on, broker_cap_ratio=broker_cap,
            broker_margin_multiplier=broker_multiplier, cluster_enabled=cluster_on,
            cluster_name=cluster, cluster_cap_amount=cluster_cap, cluster_reserved_margin_before=cluster_reserved,
            original_rank=plan.get("selection_pairwise_rank", 0), reason=reason,
            predicted_risk_T=q*rho, predicted_margin_T=q*margin)
        audit = {"mechanism_id": MECHANISM_ID, "signal_day": sizing["ema_limit_signal_day"],
            "product_vt_symbol": plan.get("product_vt_symbol", ""),
            "contract_vt_symbol": plan.get("target_contract", plan.get("contract_vt_symbol", "")),
            "direction": plan["direction"],
            **{"ema_limit_final_budget_"+key: value for key, value in fields.items()}}
        updates.append((plan, q, audit))
        gross += a*margin
        by_cluster[cluster] = cluster_gross+a*margin
    for plan, q, audit in updates:
        plan["volume"] = plan["sizing"]["selected_volume"] = q
        plan["sizing"].update({key: value for key, value in audit.items() if key.startswith("ema_limit_")})
        if q == 0:
            plan.update(candidate_status="filtered", skip_reason="ema_limit_final_budget_zero")
    return [audit for _, _, audit in updates]


def build_ema_strategy(native_base: type, *, weekly, fi, next_days, ema_lookup) -> type:
    priced = build_limit_priced_base(native_base)
    shared = build_ordered_strategy(priced, weekly, fi, next_days)

    class EmaLimitResearch(shared):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.ts_machine = EmaLimitSetupMachine()
            self.ema_limit_price_by_key = {}
            self.ema_limit_order_contexts = {}
            self.ema_limit_final_budget_audit = []
            self._ema_observations = {}
            self._ema_decisions = {}

        def _can_open_short_signal(self, signal):
            return True if signal == "short_triple_screen" else super()._can_open_short_signal(signal)

        def _ts_observe_close(self, plans, contexts):
            if self._ts_observed:
                return
            self._ts_observed = True
            self._ema_observations, self._ema_decisions = {}, {}
            day, bars = self._ts_close_day, self._ts_close_bars
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
                    result = self.ts_machine.cancel(product,day,"target_mapping_missing")
                elif target_bar is None or target_bar.datetime.date().isoformat() != day:
                    result = self.ts_machine.cancel(product,day,"target_real_bar_missing")
                else:
                    high,low,tick = float(target_bar.high_price),float(target_bar.low_price),float(self.get_pricetick(target))
                    if not all(math.isfinite(x) and x>0 for x in (high,low,tick)) or high<low:
                        result = self.ts_machine.cancel(product,day,"target_real_bar_invalid")
                    else:
                        name,exchange = product.rsplit(".",1)
                        week = weekly.get(day,f"{exchange}.{name}".upper())
                        force = fi.get((day,target),dict(ready=False,fi2=None))
                        eligible,_ = self._ai_product_pool_entry_allowed(product,datetime.fromisoformat(day))
                        observation = dict(product=product,contract=target,day=day,next_day=next_days.get(day),
                            high=high,low=low,tick=tick,weekly_ready=bool(week["ready"]),
                            weekly_direction=week["direction"],weekly_asof=week.get("weekly_asof"),
                            fi_ready=bool(force["ready"]),fi2=force.get("fi2"),eligible=bool(eligible),
                            position_open=self._ts_actual_position(product,target,bars)!=0,native_signal=None)
                        feature = ema_lookup.get((day,target))
                        # Execution tick must be delivered with the u-qualified feature;
                        # configured risk/cost tick is never used as a replacement.
                        quote = (limit_quote(feature,direction=week["direction"],
                                    execution_tick=feature.get("execution_tick"))
                                 if feature is not None and week["ready"] and week["direction"] in (-1,1)
                                 else None)
                        result = self.ts_machine.on_close(observation,quote)
                intent = result["intent"]
                signal = ("long_triple_screen" if intent["direction"]==1 else "short_triple_screen") if intent else ""
                if intent:
                    if context is None or context.current_pos or context.target_contract!=target:
                        filter_reason="no_executable_context"
                    elif not self._passes_entry_filters(signal,context.history):
                        filter_reason="generic_entry_filters"
                    else:
                        context.signal_data["signal"]=signal
                        context.signal_data["risk_mode"]=(self._volume_open_interest_risk_mode(context.history)
                            or self._open_interest_risk_mode(context.history) or "regular")
                        self.ema_limit_price_by_key[(day,target,"long" if intent["direction"]==1 else "short")]=intent["limit_price"]
                decision=dict(mechanism_id=MECHANISM_ID,date=day,product=product,contract=target,
                    decision=result["decision"],cancel_reason=result["cancel_reason"],
                    setup_id=result["setup_id"],intent_id=intent["intent_id"] if intent else None,
                    filter_reason=filter_reason,signal=signal,selection_pairwise_rank=0)
                self._ema_observations[product],self._ema_decisions[product]=result,decision
                self.ts_decision_audit.append(decision)

        def _plan_flat_entry_candidates(self, day_contexts):
            contexts={context.product_vt_symbol:context for context in day_contexts}
            self._ts_observe_close({},contexts)
            plans=super(shared,self)._plan_flat_entry_candidates(day_contexts)
            self.ema_limit_final_budget_audit.extend(finalize_ema_plan_batch(self,plans))
            ranks={product:i for i,product in enumerate(plans,1)}
            for product,plan in plans.items():
                observation=self._ema_observations.get(product)
                decision=self._ema_decisions.get(product)
                if observation is None or decision is None:
                    continue
                sizing=plan["sizing"]
                quantity=int(plan.get("volume") or 0)
                decision.update(candidate_status=plan.get("candidate_status"),volume=quantity,
                    selection_pairwise_rank=plan.get("selection_pairwise_rank"),**_budget_fields(sizing))
                if plan.get("candidate_status")!="opened" or quantity<=0:
                    continue
                intent=observation["intent"]
                if intent is None or plan["signal"] not in EMA_SIGNALS:
                    raise ValueError("ema_limit_native_initial_signal_leaked")
                context=contexts[product]
                rank=int(plan.get("selection_pairwise_rank") or ranks[product])
                frozen=dict(sizing=deepcopy(sizing),volume=quantity,target_contract=context.target_contract,
                    target_bar=copy(context.target_bar),history=deepcopy(context.history),
                    signal_data=deepcopy(context.signal_data),direction=plan["direction"],signal=plan["signal"],
                    rank=rank,signal_close=float(context.target_bar.close_price),trigger=intent["limit_price"],
                    **_budget_fields(sizing))
                self.ts_pending_intents.append({**intent,"rank":rank,"plan":frozen})
                plan.update(candidate_status="conditional_pending",skip_reason="ema_limit_pending_day")
            return plans

        def _record_entry_candidate_snapshot(self, **fields):
            result=super()._record_entry_candidate_snapshot(**fields)
            if fields["entry_context"]=="flat_entry" and fields["signal"] in EMA_SIGNALS:
                sizing=fields["sizing_snapshot"]
                snapshots=self.entry_candidate_snapshots
                if snapshots:
                    snapshots[-1].update(_budget_fields(sizing),mechanism_id=MECHANISM_ID,
                        planned_entry_price=sizing["ema_limit_trigger_price"],
                        stop_distance=(1 if fields["direction"]=="long" else -1)*
                            (sizing["ema_limit_trigger_price"]-float(sizing["stop_price"])))
            return result

        def ts_commit_fill(self,item,execution_day,order_id,context):
            receipt=self.ts_machine.on_fill(item["intent_id"],str(execution_day))
            key=(item["product"],str(execution_day))
            entry=dict(contract=item["contract"],signal_day=item["signal_day"],
                execution_datetime=_local_datetime(context["execution_datetime"]),
                fill_price=float(context["fill_price"]),context=context)
            if key not in self._ts_conditional_entries or entry["execution_datetime"]<self._ts_conditional_entries[key]["execution_datetime"]:
                self._ts_conditional_entries[key]=entry
            self.ts_fill_audit.append(dict(mechanism_id=MECHANISM_ID,intent_id=item["intent_id"],
                setup_id=receipt["setup_id"],product=item["product"],contract=item["contract"],
                signal_day=item["signal_day"],execution_day=str(execution_day),order_id=str(order_id),
                volume=item["plan"]["volume"],economic_mother_id=context.get("economic_mother_id"),
                **{key:context.get(key) for key in ("signed_risk_price","actual_risk_amount",
                    "actual_margin_amount","forecast_risk_amount","forecast_margin_amount")}))

        def _ema_context(self,trade):
            for key in (getattr(trade,"signal_order_id",None),getattr(trade,"vt_orderid",None),
                        getattr(trade,"orderid",None)):
                context=self.ema_limit_order_contexts.get(key)
                if context and context.get("mechanism_id")==MECHANISM_ID:
                    return context
            return None

        def update_trade(self,trade):
            # Native synthetic CLOSE/retry objects keep the original signal ID
            # but do not copy arbitrary context. Bind identity only, then execute
            # precisely one unchanged native economic update for every fill.
            context=self._ema_context(trade)
            if context is not None:
                trade.research_mechanism=MECHANISM_ID
                trade.economic_mother_id=context.get("economic_mother_id")
                trade.ema_limit_intent_id=context["intent_id"]
                trade.ema_limit_setup_id=context["setup_id"]
            return super().update_trade(trade)

        def _sync_entry_risk_diagnostic(self,trade):
            context=self._ema_context(trade)
            if context is None or not context["invalid_stop_side_gap"]:
                return super()._sync_entry_risk_diagnostic(trade)
            if getattr(trade,"intraday_episode_id",""):
                return
            import qmt_roll_intraday_execution as execution
            direction="long" if context["direction"]==1 else "short"
            key=(trade.vt_symbol,direction)
            pending=self.pending_entry_diagnostics.get(key,[])
            remaining=int(trade.volume)
            for index in reversed(list(pending)):
                row=self.entry_risk_diagnostics[index]
                if execution.local_timestamp(row["datetime"])!=execution.local_timestamp(trade.signal_datetime):
                    continue
                matched=min(remaining,int(row["volume"])-int(row.get("actual_filled_volume") or 0))
                if matched<=0:
                    continue
                if matched!=int(row["volume"]):
                    raise ValueError("ema_limit_unqualified_partial_gap_fill")
                row.update(actual_filled_volume=matched,filled_entry_price=float(trade.price),
                    entry_price=float(trade.price),stop_distance=None,risk_per_contract=None,
                    actual_risk_amount=None,ema_limit_signed_risk_price=context["signed_risk_price"],
                    ema_limit_gap_reason="invalid_stop_side_gap",mechanism_id=MECHANISM_ID,
                    economic_mother_id=context.get("economic_mother_id"),
                    actual_margin_amount=context["actual_margin_amount"],
                    margin_per_contract=context["actual_margin_amount"]/matched,
                    projected_total_margin_after=float(row["total_margin_in_use_before"])+context["actual_margin_amount"],
                    signal_order_id=trade.signal_order_id)
                pending.remove(index)
                remaining-=matched
                if remaining==0:
                    break
            if remaining:
                raise ValueError("ema_limit_gap_diagnostic_unmatched")
            if not pending:
                self.pending_entry_diagnostics.pop(key,None)

        def stage827_intraday_exit_after_open_trade(self,trade):
            context=self._ema_context(trade)
            if context is None:
                return super().stage827_intraday_exit_after_open_trade(trade)
            from decimal import Decimal,ROUND_CEILING,ROUND_FLOOR
            import qmt_roll_intraday_execution as execution
            from stage127_ema_limit_engine import entry_minute_view
            if context["invalid_stop_side_gap"]:
                state=self._find_state_by_contract(trade.vt_symbol)
                if state is None or not state.layers:
                    raise ValueError("ema_limit_gap_missing_native_layers")
                direction=context["direction"]
                minute=context["entry_minute"]
                adverse=minute["low" if direction==1 else "high"]
                tick=Decimal(str(context["execution_tick"]))
                price=float((Decimal(str(adverse))/tick).to_integral_value(
                    rounding=ROUND_FLOOR if direction==1 else ROUND_CEILING)*tick)
                if price<=0 or price<minute["low"] or price>minute["high"]:
                    raise ValueError("ema_limit_gap_proxy_unreachable")
                stamp=_local_datetime(context["execution_datetime"]).isoformat()
                quantity=int(trade.volume)
                event=dict(vt_symbol=trade.vt_symbol,product_vt_symbol=state.product_vt_symbol,
                    trading_date=context["execution_day"],execution_datetime=trade.execution_datetime,
                    candidate_layer_ids=[self._stage827_layer_identity(layer) for layer in state.layers],
                    candidate_indexes=list(range(len(state.layers))),volume=quantity,stop_price=None,
                    risk_price=None,signed_risk_price=context["signed_risk_price"],
                    exit_reason="invalid_stop_side_gap",final_state="flat_no_reentry",
                    mechanism_id=MECHANISM_ID,economic_mother_id=context.get("economic_mother_id"),
                    protection_instruction="immediate",execution_proxy="entry_minute_adverse_extreme",
                    synthetic_trades=[dict(action="close",source="invalid_stop_side_gap",price=price,
                        trigger_price=price,execution_note="immediate_instruction_minute_worst_proxy",
                        volume=quantity,time=stamp)])
                context["protection_event"]=event
                return event
            original=self.stage827_minute_by_symbol
            private=entry_minute_view(original[trade.vt_symbol],entry_time=context["execution_datetime"],
                fill_price=context["fill_price"],direction=context["direction"],intrabar=context["intrabar"])
            self.stage827_minute_by_symbol={**original,trade.vt_symbol:private}
            try:
                # Bypass only OrderedResearch's open-only temporary view. The
                # original 847 guard, half-R and retry scanner run unchanged.
                return super(shared,self).stage827_intraday_exit_after_open_trade(trade)
            finally:
                self.stage827_minute_by_symbol=original

        def _build_daily_env_gate_snapshot(self,day_contexts):
            # The environment/technical consumers see raw completed D first.
            snapshot=super(shared,self)._build_daily_env_gate_snapshot(day_contexts)
            import qmt_roll_intraday_execution as execution
            from types import SimpleNamespace
            from stage127_ema_limit_engine import entry_minute_view
            for daily in day_contexts:
                if not daily.current_pos:
                    continue
                day=daily.target_bar.datetime.date().isoformat()
                entry=self._ts_conditional_entries.get((daily.product_vt_symbol,day))
                if entry is None or entry["contract"]!=daily.target_contract:
                    continue
                context=entry["context"]
                frame=execution.entry_session(self,SimpleNamespace(vt_symbol=entry["contract"],
                    datetime=datetime.fromisoformat(day),trading_date=day,
                    execution_datetime=entry["execution_datetime"]))
                if frame.empty or self.minute_scan_requests[-1]["missing_bar_count"]:
                    raise ValueError("ema_limit_holding_minutes_incomplete")
                private=entry_minute_view(frame,entry_time=entry["execution_datetime"],
                    fill_price=entry["fill_price"],direction=context["direction"],intrabar=context["intrabar"])
                lifetime=copy(daily.target_bar)
                lifetime.open_price=entry["fill_price"]
                lifetime.high_price=max(entry["fill_price"],float(private.high.max()))
                lifetime.low_price=min(entry["fill_price"],float(private.low.min()))
                lifetime.close_price=float(private.iloc[-1]["close"])
                daily.target_bar=lifetime
                if daily.actual_bar is not None and daily.actual_bar.vt_symbol==entry["contract"]:
                    daily.actual_bar=copy(lifetime)
            return snapshot

    EmaLimitResearch.__name__="Stage127IndependentEmaLimit"
    return EmaLimitResearch


def build_ema_account_profile(formal: Mapping,native_strategy: type,native_engine: type,*,
                              weekly,fi,next_days,ema_lookup,qualify) -> tuple[dict,type]:
    from stage065_pairwise_off_policy import OFF_SETTINGS
    from stage127_ema_limit_engine import build_ema_engine
    profile=dict(formal)
    profile["spec"]=replace(formal["spec"],overrides={**formal["spec"].overrides,**OFF_SETTINGS})
    profile["strategy_cls"]=build_ema_strategy(native_strategy,weekly=weekly,fi=fi,
        next_days=next_days,ema_lookup=ema_lookup)
    profile.update(research_mechanism=MECHANISM_ID,financial_ready=False)
    return profile,build_ema_engine(native_engine,qualify=qualify)

