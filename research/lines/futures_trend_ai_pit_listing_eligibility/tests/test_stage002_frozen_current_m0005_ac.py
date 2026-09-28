from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pandas as pd
import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools/stage002_frozen_current_m0005_ac.py"
)
SPEC = importlib.util.spec_from_file_location("stage002_frozen_current_m0005_ac", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _baseline() -> dict[str, float]:
    return {
        "end_equity": 5_996_631.0,
        "total_return_pct": 3_897.7540,
        "max_dd_pct": -55.370112,
        "sharpe": 1.396723,
        "total_slippage": 759_970.0,
        "total_trade_count": 641.0,
        "nonzero_daily_win_rate_pct": 52.830189,
        "max_broker10_margin_to_equity_pct": 88.3398,
        "days_over_100pct": 0.0,
        "account_survival_pass": 1.0,
    }


def test_formal_baseline_oracle_passes_exact_payload() -> None:
    result = MODULE.evaluate_baseline_oracle(_baseline())
    assert result["passed"] is True
    assert all(result["gates"].values())


def test_formal_baseline_oracle_rejects_metric_drift() -> None:
    payload = _baseline()
    payload["end_equity"] += 1.0
    result = MODULE.evaluate_baseline_oracle(payload)
    assert result["passed"] is False
    assert result["gates"]["end_equity_within_tolerance"] is False


def test_effect_gates_require_both_return_and_drawdown_improvement() -> None:
    baseline = _baseline()
    candidate = dict(baseline)
    candidate.update(
        {
            "end_equity": baseline["end_equity"] + 100.0,
            "total_return_pct": baseline["total_return_pct"] + 1.0,
            "max_dd_pct": baseline["max_dd_pct"] + 0.1,
            "sharpe": baseline["sharpe"],
        }
    )
    result = MODULE.evaluate_fullperiod_gates(
        baseline,
        candidate,
        baseline_repeat_pass=True,
        baseline_oracle_pass=True,
        predecision_path_pass=True,
        identity_pass=True,
        membership_contract_pass=True,
        coverage_pass=True,
    )
    assert result["passed"] is True

    candidate["max_dd_pct"] = baseline["max_dd_pct"] - 0.1
    failed = MODULE.evaluate_fullperiod_gates(
        baseline,
        candidate,
        baseline_repeat_pass=True,
        baseline_oracle_pass=True,
        predecision_path_pass=True,
        identity_pass=True,
        membership_contract_pass=True,
        coverage_pass=True,
    )
    assert failed["passed"] is False
    assert failed["gates"]["max_drawdown_strictly_better"] is False


def test_effect_gates_reject_return_gain_with_sharpe_loss() -> None:
    baseline = _baseline()
    candidate = dict(baseline)
    candidate.update(
        {
            "end_equity": baseline["end_equity"] + 100.0,
            "total_return_pct": baseline["total_return_pct"] + 1.0,
            "max_dd_pct": baseline["max_dd_pct"] + 0.1,
            "sharpe": baseline["sharpe"] - 1e-6,
        }
    )
    result = MODULE.evaluate_fullperiod_gates(
        baseline,
        candidate,
        baseline_repeat_pass=True,
        baseline_oracle_pass=True,
        predecision_path_pass=True,
        identity_pass=True,
        membership_contract_pass=True,
        coverage_pass=True,
    )
    assert result["passed"] is False
    assert result["gates"]["sharpe_noninferior"] is False


def test_predecision_path_gate_compares_curve_and_trades() -> None:
    curves = {
        arm: pd.DataFrame(
            {
                "date": ["2022-01-27", "2022-01-28", "2022-01-31"],
                "account_equity": [100.0, 101.0, 102.0 + (arm == "C")],
                "net_pnl": [0.0, 1.0, 1.0 + (arm == "C")],
            }
        )
        for arm in ("A1", "C")
    }
    trades = {
        "A1": pd.DataFrame({"datetime": ["2022-01-27", "2022-01-31"], "price": [1.0, 2.0]}),
        "C": pd.DataFrame({"datetime": ["2022-01-27", "2022-01-31"], "price": [1.0, 3.0]}),
    }
    result = MODULE.predecision_path_gate(
        curves,
        trades,
        boundary=pd.Timestamp("2022-01-28"),
    )
    assert result["passed"] is True

    curves["C"].loc[0, "account_equity"] = 99.0
    failed = MODULE.predecision_path_gate(
        curves,
        trades,
        boundary=pd.Timestamp("2022-01-28"),
    )
    assert failed["passed"] is False


def test_worker_environment_isolated_by_arm(tmp_path: Path) -> None:
    a = MODULE.worker_environment({}, tmp_path, "A1")
    c = MODULE.worker_environment({}, tmp_path, "C")
    assert a["TMPDIR"] != c["TMPDIR"]
    assert a["MPLCONFIGDIR"] != c["MPLCONFIGDIR"]
    assert a["PYTHONHASHSEED"] == c["PYTHONHASHSEED"] == "0"
    with pytest.raises(ValueError, match="unknown_arm"):
        MODULE.worker_environment({}, tmp_path, "B")


def test_existing_attempt_directory_is_rejected(tmp_path: Path) -> None:
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    with pytest.raises(MODULE.Stage002Error, match="attempt_output_already_exists"):
        MODULE.ensure_attempt_absent(attempt)
