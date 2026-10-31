from __future__ import annotations

from functools import lru_cache
import math
import re
from pathlib import Path
from typing import Any, Mapping


SIZING_VERSION = "c9_broker_account_risk_budget_v1"


def _number(values: Mapping[str, Any], key: str, *, positive: bool = False) -> float:
    value = values.get(key)
    if isinstance(value, bool):
        raise ValueError(f"broker_sizing_invalid_{key}")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"broker_sizing_invalid_{key}") from exc
    if not math.isfinite(number) or number < 0 or (positive and number == 0):
        raise ValueError(f"broker_sizing_invalid_{key}")
    return number


@lru_cache(maxsize=1)
def official_sizing_policy() -> dict[str, Any]:
    from qmt_roll_official_candidate_stage847_c9_config import (
        _build_official_candidate_stage847_c9_overrides,
    )
    from qmt_roll_official_stage037_ruleset_config import apply_stage037_ruleset
    from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy

    overrides = apply_stage037_ruleset(
        _build_official_candidate_stage847_c9_overrides(Path("unused"), Path("unused"))
    )
    names = (
        "max_capital_usage_ratio", "max_single_trade_capital_usage_ratio",
        "min_risk_per_trade", "max_risk_per_trade", "min_position_size",
        "max_position_size", "max_concurrent_positions", "sizing_equity_cap",
    )
    return {name: overrides.get(name, getattr(QmtRollPortfolioStrategy, name)) for name in names}


def size_open_intent(
    *,
    intent: Mapping[str, Any],
    signal: Mapping[str, Any],
    account: Mapping[str, Any],
    policy: Mapping[str, Any],
    pricetick: float,
) -> dict[str, Any]:
    if intent.get("offset") != "open":
        raise ValueError("broker_sizing_open_only")
    direction = intent.get("direction")
    if direction not in {"long", "short"}:
        raise ValueError("broker_sizing_direction_invalid")
    for flag in (
        "portfolio_drawdown_gate_enabled", "portfolio_volatility_budget_enabled",
        "dynamic_sizing_equity_soft_cap_enabled", "risk_cluster_heat_gate_enabled",
        "recovery_sleeve_applied", "incremental_margin_budget_gate_reduce_volume_enabled",
    ):
        if flag in signal and _number(signal, flag) != 0:
            raise ValueError(f"broker_sizing_unsupported_{flag}")
    if signal.get("sizing_method", "risk_budget") != "risk_budget":
        raise ValueError("broker_sizing_unsupported_sizing_method")

    equity = _number(account, "equity", positive=True)
    available = _number(account, "available")
    margin = _number(account, "margin")
    frozen = _number(account, "frozen")
    if available > equity:
        raise ValueError("broker_sizing_available_above_equity")
    cap = _number(policy, "sizing_equity_cap")
    sizing_equity = min(equity, cap) if cap else equity
    usage_ratio = _number(policy, "max_capital_usage_ratio", positive=True)
    single_ratio = _number(policy, "max_single_trade_capital_usage_ratio", positive=True)
    if usage_ratio > 1 or single_ratio > 1:
        raise ValueError("broker_sizing_capital_ratio_above_one")
    limited_balance = max(0.0, min(available, sizing_equity * usage_ratio - margin - frozen))
    risk_ratio = _number(signal, "risk_ratio", positive=True)
    if risk_ratio > 1:
        raise ValueError("broker_sizing_risk_ratio_above_one")
    multiplier = _number(signal, "risk_multiplier")
    directional_multiplier = _number(signal, "directional_30d_risk_boost_multiplier")
    minimum_risk = _number(policy, "min_risk_per_trade")
    maximum_risk = _number(policy, "max_risk_per_trade", positive=True)
    if minimum_risk > maximum_risk:
        raise ValueError("broker_sizing_risk_limits_invalid")
    risk_budget = min(maximum_risk, max(minimum_risk, limited_balance * risk_ratio))
    risk_budget *= multiplier * directional_multiplier
    risk_budget = _number({"risk_budget": risk_budget}, "risk_budget")
    if limited_balance == 0:
        risk_budget = 0.0

    entry_price = _number(intent, "limit_price", positive=True)
    stop_price = _number(signal, "stop_price", positive=True)
    original_stop = _number(intent, "strategy_initial_stop_price", positive=True)
    if not math.isclose(stop_price, original_stop, rel_tol=0, abs_tol=1e-8):
        raise ValueError("broker_sizing_signal_stop_mismatch")
    if (direction == "long" and stop_price >= entry_price) or (direction == "short" and stop_price <= entry_price):
        raise ValueError("broker_sizing_stop_not_adverse")
    size = _number(signal, "size", positive=True)
    if not size.is_integer():
        raise ValueError("broker_sizing_contract_size_not_integer")
    tick = _number({"pricetick": pricetick}, "pricetick", positive=True)
    risk_per_contract = max(abs(entry_price - stop_price) * size, tick * size, 1.0)
    margin_ratio = _number(signal, "margin_ratio", positive=True)
    if margin_ratio > 1:
        raise ValueError("broker_sizing_margin_ratio_above_one")
    margin_per_contract = entry_price * size * margin_ratio

    raw_product_margin = account.get("product_margin")
    if not isinstance(raw_product_margin, Mapping):
        raise ValueError("broker_sizing_product_margin_missing")
    product_margin = {}
    for product in raw_product_margin:
        normalized = str(product).upper()
        if normalized in product_margin:
            raise ValueError("broker_sizing_duplicate_product_margin")
        product_margin[normalized] = _number(raw_product_margin, product)
    limits = {
        "contracts_by_risk": int(risk_budget // risk_per_contract),
        "contracts_by_margin": int(limited_balance // margin_per_contract),
        "contracts_by_single_trade_cap": int(sizing_equity * single_ratio // margin_per_contract),
        "contracts_by_position_limit": int(_number(policy, "max_position_size", positive=True)),
    }
    cluster = str(signal.get("risk_cluster_name", "")).upper()
    product_match = re.fullmatch(r"([A-Z]+)[0-9]{3,4}\.([A-Z]+)", str(intent.get("vt_symbol", "")).upper())
    if product_match is None:
        raise ValueError("broker_sizing_product_invalid")
    product = f"{product_match.group(1)}.{product_match.group(2)}"
    if _number(signal, "risk_cluster_cap_enabled"):
        if not cluster or cluster.count(".") != 1:
            raise ValueError("broker_sizing_unsupported_risk_cluster")
        if cluster != product:
            raise ValueError("broker_sizing_cluster_product_mismatch")
        cluster_ratio = _number(signal, "risk_cluster_cap_ratio", positive=True)
        if cluster_ratio > 1:
            raise ValueError("broker_sizing_cluster_ratio_above_one")
        used = float(product_margin.get(cluster, 0))
        limits["contracts_by_cluster_cap"] = int(max(0.0, sizing_equity * cluster_ratio - used) // margin_per_contract)
    max_products = int(_number(policy, "max_concurrent_positions", positive=True))
    held_products = {name for name, used in product_margin.items() if float(used) > 0}
    if len(held_products) >= max_products and product not in held_products:
        limits["contracts_by_account_position_count"] = 0

    if intent.get("intent_role") == "c9_retry_open_once":
        try:
            root_volume = _number(intent, "root_entry_volume", positive=True)
            root_entry = _number(intent, "root_entry_price", positive=True)
            root_stop = _number(intent, "root_initial_stop_price", positive=True)
            retry_volume = _number(intent, "planned_volume", positive=True)
        except ValueError as exc:
            raise ValueError("broker_sizing_retry_root_risk_missing") from exc
        if not root_volume.is_integer() or not retry_volume.is_integer():
            raise ValueError("broker_sizing_retry_volume_invalid")
        root_budget = abs(root_entry - root_stop) * size * root_volume
        limits["contracts_by_retry_root_risk"] = int(root_budget // risk_per_contract)
        limits["contracts_by_retry_root_volume"] = int(min(root_volume, retry_volume))

    volume = min(value for name, value in limits.items() if not name.startswith("contracts_by_retry_"))
    for flag, field in (
        ("env_gate_enabled", "env_gate_weight"),
        ("same_direction_correlation_gate_enabled", "same_direction_correlation_gate_weight"),
    ):
        if flag in signal and _number(signal, flag):
            weight = _number(signal, field)
            if weight > 1:
                raise ValueError(f"broker_sizing_invalid_{field}")
            volume = int(math.floor(volume * weight))
    volume = min(volume, *limits.values())
    if volume < _number(policy, "min_position_size", positive=True):
        volume = 0
    return {
        "version": SIZING_VERSION,
        "volume": volume,
        "shadow_volume": _number(intent, "planned_volume"),
        "equity": equity,
        "sizing_equity": sizing_equity,
        "available": available,
        "margin": margin,
        "frozen": frozen,
        "limited_balance": limited_balance,
        "risk_ratio": risk_ratio,
        "risk_multiplier": multiplier * directional_multiplier,
        "risk_budget": risk_budget,
        "risk_per_contract": risk_per_contract,
        "actual_risk": risk_per_contract * volume,
        "entry_price": entry_price,
        "stop_price": stop_price,
        "size": size,
        "margin_per_contract_estimate": margin_per_contract,
        "margin_ratio_source": "frozen_signal_estimate_final_broker_capacity_gate_required",
        "generation_uuid": str(account.get("generation_uuid", "")),
        "account_fingerprint": str(account.get("account_fingerprint", "")),
        "generated_at": str(account.get("generated_at", "")),
        **limits,
    }
