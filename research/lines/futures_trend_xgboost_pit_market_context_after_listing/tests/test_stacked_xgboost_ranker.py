from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/stacked_xgboost_ranker.py"
SPEC = importlib.util.spec_from_file_location("stacked_xgboost_ranker", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _feature_panel(dates: list[str]) -> pd.DataFrame:
    rows = []
    for date in dates:
        for product, a_rank in [("b.X", 3), ("c.X", 4), ("d.X", 5)]:
            row = {
                "eval_date": date,
                "product_vt_symbol": product,
                "window_id": "wf_01",
                "a_rank": a_rank,
                "role": "a_rank10" if product == "b.X" else "challenger",
                "pit_logistic_probability": {"b.X": 0.7, "c.X": 0.6, "d.X": 0.5}[product],
            }
            row.update({feature: float(a_rank - 3) for feature in module.FEATURE_COLUMNS})
            rows.append(row)
    return pd.DataFrame(rows)


def test_dense_relevance_preserves_ties_and_higher_future_pnl_is_higher() -> None:
    features = _feature_panel(["2024-01-31"])
    labels = pd.DataFrame(
        {
            "eval_date": ["2024-01-31"] * 3,
            "product_vt_symbol": ["b.X", "c.X", "d.X"],
            "future_net_pnl_60d": [0.0, 10.0, 10.0],
            "future_label_end_date": ["2024-03-01"] * 3,
            "full_horizon_label": [True] * 3,
        }
    )

    joined = module.attach_relevance_labels(features, labels)

    assert joined.set_index("product_vt_symbol")["rank_relevance"].to_dict() == {
        "b.X": 0,
        "c.X": 1,
        "d.X": 1,
    }


def test_walk_forward_uses_only_groups_whose_label_end_precedes_test_month() -> None:
    dates = ["2024-01-31", "2024-02-29", "2024-03-31", "2024-04-30"]
    panel = _feature_panel(dates)
    label_end = {
        "2024-01-31": "2024-03-01",
        "2024-02-29": "2024-03-15",
        "2024-03-31": "2024-05-15",
        "2024-04-30": "2024-06-15",
    }
    labels = pd.DataFrame(
        [
            {
                "eval_date": date,
                "product_vt_symbol": product,
                "future_net_pnl_60d": pnl,
                "future_label_end_date": label_end[date],
                "full_horizon_label": True,
            }
            for date in dates
            for product, pnl in [("b.X", -1.0), ("c.X", 1.0), ("d.X", 0.0)]
        ]
    )
    joined = module.attach_relevance_labels(panel, labels)

    folds = module.build_stacked_walk_forward_folds(
        joined,
        minimum_train_months=2,
        minimum_train_rows=6,
    )

    assert [fold.test_date for fold in folds] == [pd.Timestamp("2024-03-31"), pd.Timestamp("2024-04-30")]
    assert folds[0].train_dates == (
        pd.Timestamp("2024-01-31"),
        pd.Timestamp("2024-02-29"),
    )
    assert folds[0].train_label_end_max == pd.Timestamp("2024-03-15")
    assert folds[0].train_label_end_max < folds[0].test_date


def test_candidate_selection_breaks_equal_ranker_scores_by_a_rank_then_symbol() -> None:
    month = pd.DataFrame(
        {
            "product_vt_symbol": ["d.X", "c.X", "b.X"],
            "a_rank": [5, 4, 3],
            "ranker_score": [1.0, 1.0, 0.5],
        }
    )

    selected = module.select_b_candidate(month)

    assert selected == "c.X"


def test_forward_drawdown_ignores_eval_day_and_requires_complete_future_rows() -> None:
    rows = []
    for product, values in {
        "a.X": [-0.99, -0.10, 0.05, 0.00],
        "b.X": [-0.99, -0.10, 0.05, 0.00],
    }.items():
        for date, value in zip(
            pd.to_datetime(["2024-01-31", "2024-02-01", "2024-02-02", "2024-02-03"]),
            values,
            strict=True,
        ):
            rows.append(
                {
                    "product_vt_symbol": product,
                    "selection_date": date - pd.Timedelta(days=1),
                    "return_date": date,
                    "selected_contract_vt": f"{product.split('.')[0]}2401.X",
                    "product_return": value,
                    "status": "ok",
                    "fallback_used": False,
                    "cross_contract_price_used": False,
                }
            )
    returns = pd.DataFrame(rows)

    drawdown = module.future_equal_weight_drawdown(
        returns,
        eval_date=pd.Timestamp("2024-01-31"),
        products=["a.X", "b.X"],
        horizon=3,
    )

    assert drawdown == pytest.approx(-0.10)


def test_effect_gate_requires_both_future_pnl_and_market_drawdown_improvement() -> None:
    passing = {
        "replacement_months": 5,
        "a_mean_rank_ic": -0.1,
        "b_mean_rank_ic": 0.1,
        "a_median_rank_ic": -0.1,
        "b_median_rank_ic": 0.0,
        "a_mean_future_pnl": 10.0,
        "c_mean_future_pnl": 12.0,
        "median_future_pnl_delta": 1.0,
        "a_p10_future_pnl": -5.0,
        "c_p10_future_pnl": -4.0,
        "positive_future_pnl_delta_rate": 0.60,
        "yearly_future_pnl_delta": {"2024": 1.0, "2025": 2.0},
        "leave_best_month_future_pnl_delta": 1.0,
        "a_mean_market_drawdown": -0.20,
        "c_mean_market_drawdown": -0.10,
        "a_p10_market_drawdown": -0.30,
        "c_p10_market_drawdown": -0.20,
        "yearly_mean_market_drawdown_delta": {"2024": 0.01, "2025": 0.02},
    }

    assert all(module.evaluate_effect_gates(passing, minimum_replacement_months=4).values())
    failing = dict(passing, c_mean_market_drawdown=-0.25)
    assert module.evaluate_effect_gates(failing, minimum_replacement_months=4)[
        "mean_market_drawdown_strictly_better"
    ] is False

