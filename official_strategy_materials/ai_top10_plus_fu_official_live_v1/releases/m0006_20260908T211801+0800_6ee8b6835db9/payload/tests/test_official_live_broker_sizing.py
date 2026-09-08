from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples/portfolio_backtesting"))


def calculator():
    module = importlib.import_module("qmt_roll_official_live_broker_sizing")
    return module.size_open_intent


def account(**changes):
    return {
        "equity": 186670.0,
        "available": 140110.0,
        "margin": 46560.0,
        "frozen": 0.0,
        "product_margin": {"OTHER.CZCE": 46560.0},
        "generation_uuid": "test-generation",
        "account_fingerprint": "test-account",
        "generated_at": "2026-09-08T09:00:00+08:00",
        **changes,
    }


def signal(**changes):
    return {
        "risk_ratio": 0.018,
        "risk_multiplier": 1.0,
        "directional_30d_risk_boost_multiplier": 1.0,
        "margin_ratio": 0.12,
        "size": 30,
        "stop_price": 1933.0,
        "entry_price": 1948.0,
        "risk_cluster_cap_enabled": 1,
        "risk_cluster_cap_ratio": 0.25,
        "risk_cluster_name": "SH.CZCE",
        **changes,
    }


def intent(**changes):
    return {
        "vt_symbol": "SH611.CZCE",
        "direction": "long",
        "offset": "open",
        "planned_volume": 4,
        "limit_price": 1948.0,
        "strategy_initial_stop_price": 1933.0,
        "intent_role": "c9_initial_open",
        **changes,
    }


def policy(**changes):
    return {
        "max_capital_usage_ratio": 0.9,
        "max_single_trade_capital_usage_ratio": 0.7,
        "min_risk_per_trade": 1000.0,
        "max_risk_per_trade": 50000000.0,
        "min_position_size": 1,
        "max_position_size": 50000,
        "max_concurrent_positions": 4,
        "sizing_equity_cap": 1000000.0,
        **changes,
    }


def sized(*, funds=None, risk=None, order=None, settings=None):
    return calculator()(
        intent=order or intent(),
        signal=risk or signal(),
        account=funds or account(),
        policy=settings or policy(),
        pricetick=1.0,
    )


def test_risk_cluster_cannot_be_changed_to_bypass_actual_product_occupancy():
    with pytest.raises(ValueError, match="cluster_product_mismatch"):
        sized(risk=signal(risk_cluster_name="SA.CZCE"))


def test_reproduces_sh_arithmetic_without_shadow_account_inputs():
    result = sized(risk=signal(estimated_equity=99999999, limited_balance=99999999))
    assert result["volume"] == 4
    assert result["limited_balance"] == 121443
    assert result["risk_budget"] == pytest.approx(2185.974)
    assert result["risk_per_contract"] == 450
    assert result["actual_risk"] == 1800


@pytest.mark.parametrize("equity, expected", [(100000, 3), (300000, 10)])
def test_changes_size_with_real_equity_not_shadow_four_lots(equity, expected):
    result = sized(funds=account(equity=equity, available=equity, margin=0, product_margin={}))
    assert result["volume"] == expected


def test_real_margin_and_frozen_funds_reduce_budget_without_double_subtracting_available():
    result = sized(funds=account(equity=150000, margin=50000, frozen=10000, available=90000))
    assert result["limited_balance"] == 75000
    assert result["volume"] == 3


def test_no_available_money_never_forces_minimum_risk_or_one_lot():
    result = sized(funds=account(available=0))
    assert result["volume"] == 0


def test_preserves_risk_floor_and_single_product_cap():
    result = sized(funds=account(equity=100000, available=100000, margin=0, product_margin={}), risk=signal(risk_ratio=0.001))
    assert result["risk_budget"] == 1000
    assert result["volume"] == 2
    capped = sized(funds=account(product_margin={"SH.CZCE": 42000}))
    assert capped["volume"] == 0


def test_account_position_count_cap_uses_real_products():
    result = sized(funds=account(product_margin={"A.DCE": 100, "B.DCE": 100, "C.DCE": 100, "D.DCE": 100}))
    assert result["volume"] == 0


def test_retry_cannot_expand_original_lots_or_risk_budget():
    result = sized(
        funds=account(equity=300000, available=300000, margin=0, product_margin={}),
        order=intent(intent_role="c9_retry_open_once", planned_volume=2, root_entry_volume=2,
                     root_entry_price=1948.0, root_initial_stop_price=1933.0),
    )
    assert result["volume"] == 2
    assert result["actual_risk"] <= 900


def test_retry_missing_root_risk_fails_closed():
    with pytest.raises(ValueError, match="retry"):
        sized(order=intent(intent_role="c9_retry_open_once"))


def test_short_uses_adverse_stop_and_full_r_not_half_r():
    result = sized(order=intent(direction="short", strategy_initial_stop_price=1963), risk=signal(stop_price=1963))
    assert result["volume"] == 4
    assert result["risk_per_contract"] == 450


@pytest.mark.parametrize("field,value", [("equity", float("nan")), ("equity", 0), ("margin", -1), ("available", float("inf")), ("frozen", None)])
def test_invalid_broker_numbers_fail_closed(field, value):
    with pytest.raises(ValueError):
        sized(funds=account(**{field: value}))


@pytest.mark.parametrize("risk", [signal(risk_ratio=float("nan")), signal(risk_multiplier=-1), signal(stop_price=1950), signal(size=0), signal(margin_ratio=0)])
def test_invalid_signal_risk_fails_closed(risk):
    with pytest.raises(ValueError):
        sized(risk=risk)


def test_account_derived_shadow_discount_is_not_silently_reused():
    with pytest.raises(ValueError, match="unsupported"):
        sized(risk=signal(portfolio_drawdown_gate_enabled=1))


def test_sizing_never_changes_source_objects():
    funds, risk, order = account(), signal(), intent()
    import copy
    original = copy.deepcopy((funds, risk, order))
    calculator()(intent=order, signal=risk, account=funds, policy=policy(), pricetick=1)
    assert (funds, risk, order) == original


def test_preserves_existing_signal_volume_discounts():
    result = sized(risk=signal(same_direction_correlation_gate_enabled=1, same_direction_correlation_gate_weight=0.5))
    assert result["volume"] == 2
    result = sized(risk=signal(env_gate_enabled=1, env_gate_weight=0))
    assert result["volume"] == 0


def test_finite_inputs_cannot_overflow_derived_risk_budget():
    with pytest.raises(ValueError):
        sized(risk=signal(risk_multiplier=1e308))
