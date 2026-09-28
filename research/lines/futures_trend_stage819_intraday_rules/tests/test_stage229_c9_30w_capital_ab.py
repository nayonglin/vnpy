from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "stage229_c9_30w_capital_ab.py"
)


def _load_stage229():
    if not MODULE_PATH.exists():
        pytest.fail("Stage229 capital A/C implementation is missing")
    spec = importlib.util.spec_from_file_location("stage229_c9_30w_capital_ab", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_candidate_overrides_change_only_the_two_strategy_capital_fields() -> None:
    stage229 = _load_stage229()
    live = {
        "account_capital": 150_000.0,
        "c3_capital": 150_000.0,
        "risk_multiplier": 0.8,
        "enable_stage847_half_r_stop_retry": True,
        "ai_product_pool_eligibility_path": "/frozen/official.csv",
    }

    candidate = stage229.build_capital_overrides(live, 300_000.0)

    assert candidate == {
        "account_capital": 300_000.0,
        "c3_capital": 300_000.0,
        "risk_multiplier": 0.8,
        "enable_stage847_half_r_stop_retry": True,
        "ai_product_pool_eligibility_path": "/frozen/official.csv",
    }
    assert stage229.changed_keys(live, candidate) == {
        "account_capital",
        "c3_capital",
    }


def test_capital_contract_rejects_noncapital_drift() -> None:
    stage229 = _load_stage229()
    live = {
        "account_capital": 150_000.0,
        "c3_capital": 150_000.0,
        "risk_multiplier": 0.8,
    }
    candidate = {
        "account_capital": 300_000.0,
        "c3_capital": 300_000.0,
        "risk_multiplier": 0.7,
    }

    with pytest.raises(ValueError, match="noncapital_override_drift"):
        stage229.assert_capital_only_contract(live, candidate)


def test_curve_normalization_makes_equal_percentage_paths_comparable() -> None:
    stage229 = _load_stage229()
    daily_15w = pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "account_equity": [150_000.0, 180_000.0, 165_000.0],
        }
    )
    daily_30w = pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "account_equity": [300_000.0, 360_000.0, 330_000.0],
        }
    )

    curve_15w = stage229.add_curve_fields(daily_15w, 150_000.0, "A_15w")
    curve_30w = stage229.add_curve_fields(daily_30w, 300_000.0, "C_30w")

    assert curve_15w["normalized_nav"].tolist() == pytest.approx([1.0, 1.2, 1.1])
    assert curve_30w["normalized_nav"].tolist() == pytest.approx([1.0, 1.2, 1.1])
    assert curve_15w["drawdown_pct"].tolist() == pytest.approx([0.0, 0.0, -8.3333333333])
    assert curve_30w["drawdown_pct"].tolist() == pytest.approx([0.0, 0.0, -8.3333333333])


@dataclass(frozen=True)
class _CapitalSpec:
    variant: str
    label: str
    account_capital: float
    c3_capital: float
    risk_multiplier: float
    note: str


def test_replace_capital_spec_keeps_risk_sizing_parameters_unchanged() -> None:
    stage229 = _load_stage229()
    source = _CapitalSpec(
        variant="live15w",
        label="live",
        account_capital=150_000.0,
        c3_capital=150_000.0,
        risk_multiplier=0.8,
        note="official",
    )

    candidate = stage229.replace_capital_spec(
        source,
        target_capital=300_000.0,
        variant="candidate30w",
        label="candidate",
        note_suffix="capital-only A/C",
    )

    assert candidate == _CapitalSpec(
        variant="candidate30w",
        label="candidate",
        account_capital=300_000.0,
        c3_capital=300_000.0,
        risk_multiplier=0.8,
        note="official | capital-only A/C",
    )


def test_decision_fails_closed_when_30w_adds_a_broker100_failure() -> None:
    stage229 = _load_stage229()
    full = pd.DataFrame(
        [
            {"arm": "A_15w", "sharpe": 1.50, "max_dd_pct": -40.0, "days_over_100pct": 0},
            {"arm": "C_30w", "sharpe": 1.48, "max_dd_pct": -38.0, "days_over_100pct": 1},
        ]
    )
    starts = pd.DataFrame(
        [
            {"arm": "A_15w", "positive_return": 1, "dd50_pass": 1},
            {"arm": "C_30w", "positive_return": 1, "dd50_pass": 1},
        ]
    )

    decision = stage229.evaluate_candidate(full, starts)

    assert decision["decision"] == "reject_30w_capital_scaling"
    assert "candidate_broker100_failure" in decision["failed_gates"]


def test_decision_rejects_additional_start_year_broker100_failures() -> None:
    stage229 = _load_stage229()
    full = pd.DataFrame(
        [
            {"arm": "A_15w", "sharpe": 1.50, "max_dd_pct": -40.0, "days_over_100pct": 0},
            {"arm": "C_30w", "sharpe": 1.48, "max_dd_pct": -38.0, "days_over_100pct": 0},
        ]
    )
    starts = pd.DataFrame(
        [
            {"arm": "A_15w", "positive_return": 1, "dd50_pass": 1, "broker10_100_pass": 1},
            {"arm": "A_15w", "positive_return": 1, "dd50_pass": 1, "broker10_100_pass": 1},
            {"arm": "C_30w", "positive_return": 1, "dd50_pass": 1, "broker10_100_pass": 1},
            {"arm": "C_30w", "positive_return": 1, "dd50_pass": 1, "broker10_100_pass": 0},
        ]
    )

    decision = stage229.evaluate_candidate(full, starts)

    assert decision["decision"] == "reject_30w_capital_scaling"
    assert "candidate_more_broker100_start_year_failures" in decision["failed_gates"]


def test_decision_rejects_candidate_that_crosses_dd40_limit() -> None:
    stage229 = _load_stage229()
    full = pd.DataFrame(
        [
            {"arm": "A_15w", "sharpe": 1.50, "max_dd_pct": -39.9, "days_over_100pct": 0},
            {"arm": "C_30w", "sharpe": 1.48, "max_dd_pct": -41.2, "days_over_100pct": 0},
        ]
    )
    starts = pd.DataFrame()

    decision = stage229.evaluate_candidate(full, starts)

    assert decision["decision"] == "reject_30w_capital_scaling"
    assert "candidate_dd40_failure" in decision["failed_gates"]
