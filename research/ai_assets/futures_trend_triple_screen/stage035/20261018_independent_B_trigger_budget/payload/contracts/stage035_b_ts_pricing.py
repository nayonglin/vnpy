"""B-only trigger-price sizing and non-recycling final allocator budget.

The sizing algorithm below is a static copy of the SHA-bound qmt method. Its
three entry-price expressions alone use entry_estimate. Original bars, history,
stop dispatch, risk recipe and gate order are retained. This is research only.
"""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import inspect
import math
from pathlib import Path
from typing import Any

QMT_SOURCE_SHA256 = "6d6aa534715200c40a5743697114f73080111d609b29980d924dcb1d362792e9"
B_SIGNALS = {"long_triple_screen", "short_triple_screen"}


def _is_b_flat(signal_data, entry_context):
    return entry_context == "flat_entry" and str(signal_data.get("signal", "")) in B_SIGNALS


def _number(fields, key, *, positive=False):
    try:
        value = float(fields[key])
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"b_ts_budget_invalid:{key}") from error
    if not math.isfinite(value) or (value <= 0 if positive else value < 0):
        raise ValueError(f"b_ts_budget_invalid:{key}")
    return value


def _integer(fields, key, *, positive=False):
    value = _number(fields, key, positive=positive)
    if int(value) != value:
        raise ValueError(f"b_ts_budget_invalid:{key}")
    return int(value)


def _trigger_for(strategy, vt_symbol, direction, bar, signal_data):
    if str(signal_data["signal"]) != direction + "_triple_screen":
        raise ValueError("b_ts_trigger_direction_mismatch")
    day = bar.datetime.date().isoformat()
    key = (day, vt_symbol, direction)
    triggers = getattr(strategy, "ts_trigger_by_key", {})
    if key not in triggers:
        raise ValueError(f"b_ts_trigger_missing:{key}")
    try:
        trigger = float(triggers[key])
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"b_ts_trigger_invalid:{key}") from error
    if not math.isfinite(trigger) or trigger <= 0:
        raise ValueError(f"b_ts_trigger_invalid:{key}")
    return trigger


def _snapshot_b_sizing(strategy, sizing, vt_symbol, direction, bar, signal_data):
    # Same fallback as Stage830, after it returns; no account mutation intervenes.
    equity = float(getattr(strategy, "estimated_equity", 0.0) or sizing.get("sizing_equity") or strategy.base_capital or 0.0)
    sizing.update(b_ts_budget_equity_u=equity,
        b_ts_signal_day=bar.datetime.date().isoformat(),
        b_ts_trigger_price=_trigger_for(strategy, vt_symbol, direction, bar, signal_data),
        b_ts_contract_size=strategy.get_size(vt_symbol),
        b_ts_pricetick=strategy.get_pricetick(vt_symbol),
        b_ts_min_position_size=strategy.min_position_size,
        b_ts_max_position_size=strategy.max_position_size)
    sizing["b_ts_trigger"] = sizing["b_ts_trigger_price"]
    for key in ("b_ts_budget_equity_u", "risk_per_contract", "margin_per_contract", "b_ts_contract_size", "b_ts_pricetick"):
        _number(sizing, key, positive=True)
    for key in ("risk_amount", "limited_balance", "single_trade_capital_limit", "reserved_margin_before"):
        _number(sizing, key)
    return sizing


def build_trigger_priced_base(native_base):
    """Insert PricingQmt below real 772 while leaving the 830/804 wrappers first."""
    qmt = next((base for base in native_base.__mro__
        if base.__name__ == "QmtRollPortfolioStrategy" and base.__module__ == "qmt_roll_portfolio_strategy"), None)
    if qmt is None:
        raise ValueError("b_ts_native_base_unsupported")
    source = Path(inspect.getsourcefile(qmt))
    if hashlib.sha256(source.read_bytes()).hexdigest() != QMT_SOURCE_SHA256:
        raise ValueError("b_ts_qmt_source_sha_mismatch")

    class PricingQmt(qmt):
        def _calculate_entry_sizing(self, vt_symbol, direction, bar, history, signal_data,
                risk_mode_override=None, entry_context="flat_entry", apply_env_gate=True,
                active_positions_before=None, correlation_snapshot=None):
            if not _is_b_flat(signal_data, entry_context):
                return super()._calculate_entry_sizing(vt_symbol, direction, bar, history, signal_data,
                    risk_mode_override=risk_mode_override, entry_context=entry_context,
                    apply_env_gate=apply_env_gate, active_positions_before=active_positions_before,
                    correlation_snapshot=correlation_snapshot)
            if self.fixed_size != 0:
                raise ValueError("b_ts_fixed_size_not_qualified")
            trigger = _trigger_for(self, vt_symbol, direction, bar, signal_data)
            sizing = _calculate_trigger_priced_entry(self, vt_symbol, direction, bar, history,
                signal_data, trigger, risk_mode_override=risk_mode_override,
                entry_context=entry_context, apply_env_gate=apply_env_gate,
                active_positions_before=active_positions_before, correlation_snapshot=correlation_snapshot)
            for key in ("risk_per_contract", "margin_per_contract"):
                _number(sizing, key, positive=True)
            return sizing

    class TriggerPricedBase(native_base, PricingQmt):
        def _calculate_entry_sizing(self, vt_symbol, direction, bar, history, signal_data,
                risk_mode_override=None, entry_context="flat_entry", apply_env_gate=True,
                active_positions_before=None, correlation_snapshot=None):
            sizing = super()._calculate_entry_sizing(vt_symbol, direction, bar, history, signal_data,
                risk_mode_override=risk_mode_override, entry_context=entry_context,
                apply_env_gate=apply_env_gate, active_positions_before=active_positions_before,
                correlation_snapshot=correlation_snapshot)
            if _is_b_flat(signal_data, entry_context):
                sizing = _snapshot_b_sizing(self, sizing, vt_symbol, direction, bar, signal_data)
            return sizing

    chain = [base.__name__ for base in TriggerPricedBase.__mro__]
    expected = ["QmtRollPortfolioStrategyStage847C9StopRetry", "QmtRollPortfolioStrategyStage830C2Broker10MarginCap",
        "QmtRollPortfolioStrategyStage827C2", "QmtRollPortfolioStrategyLongTighterInitialStop",
        "QmtRollPortfolioStrategyExactAm", "PricingQmt", "QmtRollPortfolioStrategy"]
    if [name for name in chain if name in expected] != expected:
        raise ValueError("b_ts_pricing_mro_mismatch")
    return TriggerPricedBase


def finalize_b_plan_batch(strategy, plans):
    """Clamp only originally admitted B plans, using pre-clamp gross prefixes.

    All validation completes before any plan mutation. Rank and skipped plans
    never change; these bookkeeping prefixes do not create real reservations.
    """
    values = list(plans.values()) if isinstance(plans, Mapping) else list(plans)
    admitted = [(index, plan) for index, plan in enumerate(values)
        if plan.get("signal") in B_SIGNALS and plan.get("candidate_status") == "opened"
        and _integer(plan, "volume") > 0]
    admitted.sort(key=lambda item: (int(item[1].get("selection_pairwise_rank") or 0) or math.inf, item[0]))
    gross = 0.0
    by_cluster = {}
    updates = []
    for _, plan in admitted:
        sizing = plan["sizing"]
        a = _integer(plan, "volume", positive=True)
        if _integer(sizing, "selected_volume") != a:
            raise ValueError("b_ts_budget_volume_mismatch")
        R = _number(sizing, "risk_amount")
        rho = _number(sizing, "risk_per_contract", positive=True)
        margin = _number(sizing, "margin_per_contract", positive=True)
        T = _number(sizing, "b_ts_trigger_price", positive=True)
        S = _number(sizing, "stop_price", positive=True)
        size = _number(sizing, "b_ts_contract_size", positive=True)
        tick = _number(sizing, "b_ts_pricetick", positive=True)
        margin_ratio = _number(sizing, "margin_ratio", positive=True)
        if not math.isclose(rho, max(abs(T-S)*size, max(tick*size, 1.0))) or not math.isclose(margin, T*size*margin_ratio):
            raise ValueError("b_ts_budget_trigger_pricing_mismatch")
        L = _number(sizing, "limited_balance")
        K = _number(sizing, "single_trade_capital_limit")
        E = _number(sizing, "b_ts_budget_equity_u", positive=True)
        B = _number(sizing, "reserved_margin_before")
        minimum = _integer(sizing, "b_ts_min_position_size", positive=True)
        maximum = _integer(sizing, "b_ts_max_position_size", positive=True)
        if minimum > maximum:
            raise ValueError("b_ts_budget_position_bounds_invalid")
        n_risk, n_margin_original, n_single = int(R // rho), int(L // margin), int(K // margin)
        for key, expected in (("contracts_by_risk", n_risk), ("contracts_by_margin", n_margin_original),
                ("contracts_by_single_trade_cap", n_single)):
            if _integer(sizing, key) != expected:
                raise ValueError(f"b_ts_budget_contract_count_mismatch:{key}")
        n_margin = int(max(0., L-gross) // margin)
        cluster = str(sizing.get("risk_cluster_name", ""))
        cluster_gross = by_cluster.get(cluster, 0.0)
        broker_on = _integer(sizing, "stage830_broker10_margin_cap_enabled")
        cluster_on = _integer(sizing, "risk_cluster_cap_enabled")
        if broker_on not in (0, 1) or cluster_on not in (0, 1):
            raise ValueError("b_ts_budget_gate_enabled_invalid")
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
                raise ValueError("b_ts_budget_cluster_missing")
            cluster_cap = _number(sizing, "risk_cluster_cap_amount")
            cluster_reserved = _number(sizing, "risk_cluster_reserved_margin_before")
            n_cluster = int(max(0., cluster_cap-cluster_reserved-cluster_gross) // margin)
            bounds.append(n_cluster)
        q = max(0, min(bounds))
        if 0 < q < minimum:
            q = 0
        reason = "b_ts_final_budget_zero" if q == 0 else ("b_ts_final_budget_reduce" if q < a else "within_b_ts_final_budget")
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
        audit = {"arm": "B_TS", "signal_day": sizing["b_ts_signal_day"],
            "product_vt_symbol": plan.get("product_vt_symbol", ""),
            "contract_vt_symbol": plan.get("target_contract", plan.get("contract_vt_symbol", "")),
            "direction": plan["direction"],
            **{"b_ts_final_budget_"+key: value for key, value in fields.items()}}
        updates.append((plan, q, audit))
        gross += a*margin
        by_cluster[cluster] = cluster_gross+a*margin
    for plan, q, audit in updates:
        plan["volume"] = plan["sizing"]["selected_volume"] = q
        plan["sizing"].update({key: value for key, value in audit.items() if key.startswith("b_ts_")})
        if q == 0:
            plan.update(candidate_status="filtered", skip_reason="b_ts_final_budget_zero")
    return [audit for _, _, audit in updates]


def _calculate_trigger_priced_entry(
    self,
    vt_symbol: str,
    direction: str,
    bar: BarData,
    history: pd.DataFrame,
    signal_data: dict[str, Any],
    entry_estimate: float,
    risk_mode_override: str | None = None,
    entry_context: str = "flat_entry",
    apply_env_gate: bool = True,
    active_positions_before: int | None = None,
    correlation_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    import pandas as pd

    signal = str(signal_data.get("signal", ""))
    recovery_fields = self._entry_structure_recovery_fields(
        signal=signal,
        direction=direction,
        entry_context=entry_context,
        rsi_value=signal_data.get("rsi_value"),
        history=history,
        active_positions_before=active_positions_before,
        correlation_snapshot=correlation_snapshot,
    )
    effective_risk_multiplier = float(
        recovery_fields.get(
            "streak_entry_structure_risk_recovery_effective_multiplier",
            self._current_streak_multiplier(),
        )
    )
    product_vt_symbol = self.source_symbol_by_contract.get(vt_symbol, self._product_vt_symbol(vt_symbol))
    failure_memory_fields = self._failure_memory_micro_sizing_fields(
        product_vt_symbol=product_vt_symbol,
        direction=direction,
        entry_context=entry_context,
        asof=pd.Timestamp(bar.datetime).normalize(),
        base_multiplier=effective_risk_multiplier,
    )
    effective_risk_multiplier = float(
        failure_memory_fields.get(
            "failure_memory_micro_sizing_effective_multiplier",
            effective_risk_multiplier,
        )
        or effective_risk_multiplier
    )
    oi_price_confirm_fields = self._oi_price_confirm_risk_restore_fields(
        history=history,
        direction=direction,
        entry_context=entry_context,
        base_multiplier=effective_risk_multiplier,
    )
    effective_risk_multiplier = float(
        oi_price_confirm_fields.get(
            "oi_price_confirm_risk_restore_effective_multiplier",
            effective_risk_multiplier,
        )
        or effective_risk_multiplier
    )
    overheat_cooldown_fields = self._portfolio_overheat_cooldown_fields(entry_context)
    overheat_cooldown_scale = float(overheat_cooldown_fields["portfolio_overheat_cooldown_scale"])
    directional_30d_risk_boost_fields = self._directional_30d_risk_boost_snapshot(direction, history)
    long_signal_atr_shock_fields = self._long_signal_atr_shock_snapshot(
        direction,
        history,
        entry_context,
    )
    long_signal_range_atr_fields = self._long_signal_range_atr_snapshot(
        direction,
        history,
        entry_context,
    )
    sizing_equity_fields = self._sizing_equity_snapshot()
    if self.fixed_size > 0:
        price: float = entry_estimate
        stop_price: float = self._entry_stop_price(direction, bar, history, use_day_extreme=True)
        size: int = self.get_size(vt_symbol)
        margin_ratio: float = self._margin_ratio_for_symbol(vt_symbol)
        risk_per_contract: float = max(abs(price - stop_price) * size, max(float(self.get_pricetick(vt_symbol)) * size, 1.0))
        margin_per_contract: float = price * size * margin_ratio
        allowed_capital: float = self._allowed_capital(entry_context)
        single_trade_capital_limit: float = self._single_trade_capital_limit()
        free_capital: float = self._free_capital_after_reservations()
        limited_balance: float = self._limited_available_balance(entry_context)
        contracts_by_single_trade_cap: int | None = (
            int(single_trade_capital_limit // margin_per_contract) if margin_per_contract > 0 else None
        )
        volume: int = min(
            int(self.fixed_size),
            int(contracts_by_single_trade_cap or 0),
            self.max_position_size,
        )
        cluster_cap_fields = self._risk_cluster_cap_fields(vt_symbol, volume, margin_per_contract)
        volume = int(cluster_cap_fields["risk_cluster_selected_volume"])
        heat_gate_fields = self._apply_risk_cluster_heat_gate_to_volume(
            vt_symbol,
            volume,
            margin_per_contract,
            entry_context,
        )
        volume = int(heat_gate_fields["risk_cluster_heat_gate_selected_volume"])
        volume = self._portfolio_overheat_cooldown_adjust_volume(volume, entry_context)
        if 0 < volume < self.min_position_size:
            volume = 0
        env_gate_fields = self._apply_env_gate_to_volume(
            volume,
            entry_context=entry_context,
            apply_env_gate=apply_env_gate,
        )
        incremental_gate_fields: dict[str, Any] = {}
        if entry_context != "flat_entry":
            adjusted_volume, incremental_gate_fields = self._incremental_margin_budget_gate_adjust_volume(
                selected_volume=int(env_gate_fields["selected_volume"]),
                margin_per_contract=margin_per_contract,
                entry_context=entry_context,
            )
            env_gate_fields["selected_volume"] = adjusted_volume
        sizing_result: dict[str, Any] = {
            "risk_mode": risk_mode_override or str(signal_data.get("risk_mode", "regular")),
            "entry_context": entry_context,
            "risk_ratio": None,
            "risk_amount": None,
            "limited_balance": limited_balance,
            "allowed_capital": allowed_capital,
            "single_trade_capital_limit": single_trade_capital_limit,
            "free_capital": free_capital,
            "reserved_margin_before": self._reserved_margin_in_use(),
            "stop_price": stop_price,
            "risk_per_contract": risk_per_contract,
            "margin_ratio": margin_ratio,
            "margin_per_contract": margin_per_contract,
            "contracts_by_risk": None,
            "contracts_by_margin": None,
            "contracts_by_single_trade_cap": contracts_by_single_trade_cap,
            "risk_multiplier": effective_risk_multiplier,
            "sizing_method": "fixed_size",
            "effective_capital_usage_ratio": self._effective_capital_usage_ratio(entry_context),
            "effective_max_concurrent_positions": self._effective_max_concurrent_positions(entry_context),
            **sizing_equity_fields,
            **recovery_fields,
            **failure_memory_fields,
            **oi_price_confirm_fields,
            **overheat_cooldown_fields,
            **directional_30d_risk_boost_fields,
            **cluster_cap_fields,
            **heat_gate_fields,
            **env_gate_fields,
            **incremental_gate_fields,
        }
        sizing_result.update(self._recovery_sleeve_fields(sizing_result, bar, entry_context, direction, history))
        sizing_result = self._apply_long_signal_atr_shock_to_sizing(
            sizing_result,
            long_signal_atr_shock_fields,
            vt_symbol=vt_symbol,
            direction=direction,
            bar=bar,
            entry_context=entry_context,
        )
        return self._apply_long_signal_range_atr_to_sizing(
            sizing_result,
            long_signal_range_atr_fields,
            vt_symbol=vt_symbol,
            direction=direction,
            bar=bar,
            entry_context=entry_context,
        )

    limited_balance: float = self._limited_available_balance(entry_context)
    allowed_capital: float = self._allowed_capital(entry_context)
    single_trade_capital_limit: float = self._single_trade_capital_limit()
    free_capital: float = self._free_capital_after_reservations()
    risk_mode: str = risk_mode_override or str(signal_data.get("risk_mode", "regular"))
    if risk_mode == "ma_cross_breakout":
        risk_ratio: float = self.risk_ratio_ma_cross_breakout
    elif risk_mode == "volume_open_interest_surge":
        risk_ratio = self.risk_ratio_volume_open_interest_surge
    elif risk_mode == "open_interest_surge":
        risk_ratio = self.risk_ratio_open_interest_surge
    elif risk_mode == "open_interest_decline":
        risk_ratio = self.risk_ratio_open_interest_decline
    elif risk_mode == "breakout":
        risk_ratio = self.risk_ratio_breakout
    else:
        risk_ratio = self.risk_ratio_of_total_assets

    risk_amount: float = self._risk_amount_from_ratio(
        risk_ratio,
        limited_balance,
        risk_multiplier_override=effective_risk_multiplier,
    )
    risk_amount *= max(0.0, overheat_cooldown_scale)
    risk_amount_before_directional_30d_boost = risk_amount
    risk_amount *= float(directional_30d_risk_boost_fields["directional_30d_risk_boost_multiplier"])
    stop_price: float = self._entry_stop_price(direction, bar, history, use_day_extreme=True)
    size: int = self.get_size(vt_symbol)
    risk_per_contract: float = abs(entry_estimate - stop_price) * size

    min_risk: float = max(float(self.get_pricetick(vt_symbol)) * size, 1.0)
    risk_per_contract = max(risk_per_contract, min_risk)

    contracts_by_risk: int = int(risk_amount // risk_per_contract) if risk_per_contract > 0 else 0
    margin_ratio: float = self._margin_ratio_for_symbol(vt_symbol)
    margin_per_contract: float = entry_estimate * size * margin_ratio
    contracts_by_margin: int = int(limited_balance // margin_per_contract) if margin_per_contract > 0 else 0
    contracts_by_single_trade_cap: int = (
        int(single_trade_capital_limit // margin_per_contract) if margin_per_contract > 0 else 0
    )

    volume: int = min(
        contracts_by_risk,
        contracts_by_margin,
        contracts_by_single_trade_cap,
        self.max_position_size,
    )
    cluster_cap_fields = self._risk_cluster_cap_fields(vt_symbol, volume, margin_per_contract)
    volume = int(cluster_cap_fields["risk_cluster_selected_volume"])
    heat_gate_fields = self._apply_risk_cluster_heat_gate_to_volume(
        vt_symbol,
        volume,
        margin_per_contract,
        entry_context,
    )
    volume = int(heat_gate_fields["risk_cluster_heat_gate_selected_volume"])
    if 0 < volume < self.min_position_size:
        volume = 0
    env_gate_fields = self._apply_env_gate_to_volume(
        volume,
        entry_context=entry_context,
        apply_env_gate=apply_env_gate,
    )
    incremental_gate_fields = {}
    if entry_context != "flat_entry":
        adjusted_volume, incremental_gate_fields = self._incremental_margin_budget_gate_adjust_volume(
            selected_volume=int(env_gate_fields["selected_volume"]),
            margin_per_contract=margin_per_contract,
            entry_context=entry_context,
        )
        env_gate_fields["selected_volume"] = adjusted_volume

    sizing_result = {
        "risk_mode": risk_mode,
        "entry_context": entry_context,
        "risk_ratio": risk_ratio,
        "risk_amount": risk_amount,
        "risk_amount_before_directional_30d_boost": risk_amount_before_directional_30d_boost,
        "limited_balance": limited_balance,
        "allowed_capital": allowed_capital,
        "single_trade_capital_limit": single_trade_capital_limit,
        "free_capital": free_capital,
        "reserved_margin_before": self._reserved_margin_in_use(),
        "stop_price": stop_price,
        "risk_per_contract": risk_per_contract,
        "margin_ratio": margin_ratio,
        "margin_per_contract": margin_per_contract,
        "contracts_by_risk": contracts_by_risk,
        "contracts_by_margin": contracts_by_margin,
        "contracts_by_single_trade_cap": contracts_by_single_trade_cap,
        "risk_multiplier": effective_risk_multiplier,
        "sizing_method": "risk_budget",
        "effective_capital_usage_ratio": self._effective_capital_usage_ratio(entry_context),
        "effective_max_concurrent_positions": self._effective_max_concurrent_positions(entry_context),
        **sizing_equity_fields,
        **recovery_fields,
        **failure_memory_fields,
        **oi_price_confirm_fields,
        **overheat_cooldown_fields,
        **directional_30d_risk_boost_fields,
        **cluster_cap_fields,
        **heat_gate_fields,
        **env_gate_fields,
        **incremental_gate_fields,
    }
    sizing_result.update(self._recovery_sleeve_fields(sizing_result, bar, entry_context, direction, history))
    sizing_result = self._apply_long_signal_atr_shock_to_sizing(
        sizing_result,
        long_signal_atr_shock_fields,
        vt_symbol=vt_symbol,
        direction=direction,
        bar=bar,
        entry_context=entry_context,
    )
    return self._apply_long_signal_range_atr_to_sizing(
        sizing_result,
        long_signal_range_atr_fields,
        vt_symbol=vt_symbol,
        direction=direction,
        bar=bar,
        entry_context=entry_context,
    )
