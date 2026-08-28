from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    PROJECT_DIR
    / "research"
    / "lines"
    / "futures_trend_rollover_shape_same_volume"
    / "tools"
    / "stage049_stage037_vs_current_online_monte_carlo.py"
)
SPEC = importlib.util.spec_from_file_location("stage049_mc", MODULE_PATH)
assert SPEC and SPEC.loader
stage049 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage049)


def test_circular_block_indices_preserve_order_and_wrap() -> None:
    class FixedRng:
        def integers(self, low, high, size, endpoint=False):  # noqa: ANN001, ANN201
            assert low == 0
            assert high == 5
            assert size == (1, 2)
            assert endpoint is False
            return np.array([[4, 2]])

    indices = stage049._circular_block_indices(
        FixedRng(), n_paths=1, n_observations=5, block_length=3
    )
    assert indices.tolist() == [[4, 0, 1, 2, 3]]


def test_paired_simulation_uses_common_indices() -> None:
    returns_a = np.array([0.01, -0.02, 0.03, 0.00, 0.015], dtype=float)
    returns = np.column_stack([returns_a, returns_a])
    simulations, pairs, _ = stage049._simulate_paired(
        returns,
        block_length=3,
        n_simulations=20,
        seed=123,
        collect_paths=False,
    )
    assert len(simulations) == 40
    assert len(pairs) == 20
    assert np.allclose(pairs["C_minus_A_end_nav"], 0.0)
    assert np.allclose(pairs["C_minus_A_max_dd_pct"], 0.0)
    assert np.allclose(pairs["C_minus_A_sharpe"], 0.0)
    assert pairs["C_dd_noninferior_2pp"].all()
    assert pairs["C_sharpe_noninferior_005"].all()


def test_path_metrics_include_initial_nav_in_drawdown_peak() -> None:
    metrics = stage049._path_metrics(np.array([[-0.20, 0.10]], dtype=float))
    assert np.isclose(metrics["max_dd_pct"][0], -20.0)
    assert np.isclose(metrics["min_nav"][0], 0.8)


def test_pair_summary_applies_predeclared_gates() -> None:
    simulations = pd.DataFrame(
        [
            {"method": "block_60", "block_length": 60, "arm": "A", "end_nav": 2.0, "total_return_pct": 100.0, "max_dd_pct": -40.0, "min_nav": 0.8, "sharpe": 1.0, "days_below_initial": 5},
            {"method": "block_60", "block_length": 60, "arm": "C", "end_nav": 2.2, "total_return_pct": 120.0, "max_dd_pct": -38.0, "min_nav": 0.9, "sharpe": 1.1, "days_below_initial": 4},
        ]
    )
    summary = stage049._summarize_simulations(simulations)
    pairs = pd.DataFrame(
        {
            "method": ["block_60"] * 10,
            "block_length": [60] * 10,
            "C_minus_A_end_nav": [0.2] * 10,
            "C_minus_A_return_pct": [20.0] * 10,
            "C_minus_A_max_dd_pct": [2.0] * 10,
            "C_minus_A_sharpe": [0.1] * 10,
            "C_end_nav_above_A": [True] * 10,
            "C_dd_noninferior_2pp": [True] * 10,
            "C_sharpe_noninferior_005": [True] * 10,
        }
    )
    result = stage049._summarize_pairs(pairs, summary).iloc[0]
    assert bool(result["all_gates_pass"])
    assert result["C_return_win_rate_pct"] == 100.0
    assert result["C_prob_dd50_pct"] <= result["A_prob_dd50_pct"]
