from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/frozen_xgboost_fusion.py"
SPEC = importlib.util.spec_from_file_location("frozen_xgboost_fusion", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
fusion = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = fusion
SPEC.loader.exec_module(fusion)


def test_add_fixed_rank_fusion_uses_monthly_percentiles() -> None:
    frame = pd.DataFrame(
        {
            "eval_date": pd.to_datetime(["2022-01-31"] * 3),
            "product_vt_symbol": ["a", "b", "c"],
            "score_a": [0.9, 0.6, 0.1],
            "score_b": [0.1, 0.7, 0.8],
        }
    )

    result = fusion.add_fixed_rank_fusion(frame, "score_a", "score_b")

    assert result["score_a_percentile"].tolist() == pytest.approx([1.0, 2 / 3, 1 / 3])
    assert result["score_b_percentile"].tolist() == pytest.approx([1 / 3, 2 / 3, 1.0])
    assert result[fusion.FUSION_SCORE_COLUMN].tolist() == pytest.approx([2 / 3, 2 / 3, 2 / 3])


def test_selected_future_path_drawdown_aggregates_products_before_drawdown() -> None:
    dates = pd.bdate_range("2022-01-03", periods=4)
    daily = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "product_vt_symbol": ["a"] * 4 + ["b"] * 4,
            "net_pnl": [0.0, 10.0, -20.0, 5.0, 0.0, 0.0, -10.0, 10.0],
        }
    )

    value = fusion.selected_future_path_drawdown(
        daily,
        eval_date=dates[0],
        products=["a", "b"],
        horizon=3,
    )

    assert value == pytest.approx(-30.0)


def test_xgboost_training_is_deterministic() -> None:
    train = pd.DataFrame(
        {
            "x_sum_20d": [-3.0, -2.0, -1.0, 1.0, 2.0, 3.0] * 8,
            "y_mean_60d": [0.0, 1.0, 0.5, 0.5, 1.0, 0.0] * 8,
            fusion.TARGET_COLUMN: [0, 0, 0, 1, 1, 1] * 8,
            fusion.WEIGHT_COLUMN: [0.2] * 48,
        }
    )
    first = fusion.fit_xgboost(train, ["x_sum_20d", "y_mean_60d"])
    second = fusion.fit_xgboost(train, ["x_sum_20d", "y_mean_60d"])

    p1 = fusion.predict_xgboost(first, train, ["x_sum_20d", "y_mean_60d"])
    p2 = fusion.predict_xgboost(second, train, ["x_sum_20d", "y_mean_60d"])

    assert np.array_equal(p1, p2)
    assert fusion.booster_dump_sha256(first) == fusion.booster_dump_sha256(second)


def test_effect_gates_require_return_and_drawdown_together() -> None:
    summary = {
        "a_mean_rank_ic": 0.01,
        "c_mean_rank_ic": 0.02,
        "a_median_rank_ic": 0.00,
        "c_median_rank_ic": 0.01,
        "a_top10_mean_future_pnl": 100.0,
        "c_top10_mean_future_pnl": 110.0,
        "a_top10_p10_future_pnl": -50.0,
        "c_top10_p10_future_pnl": -40.0,
        "a_top10_target_rate": 0.50,
        "c_top10_target_rate": 0.52,
        "a_mean_path_drawdown": -100.0,
        "c_mean_path_drawdown": -90.0,
        "a_p10_path_drawdown": -200.0,
        "c_p10_path_drawdown": -180.0,
        "a_turnover": 0.20,
        "c_turnover": 0.21,
        "yearly_c_rank_ic_wins": 3,
        "worst_year_rank_ic_delta": -0.02,
    }

    gates = fusion.evaluate_c_effect_gates(summary)

    assert all(gates.values())
    summary["c_mean_path_drawdown"] = -110.0
    assert not fusion.evaluate_c_effect_gates(summary)["mean_path_drawdown_strictly_better"]

