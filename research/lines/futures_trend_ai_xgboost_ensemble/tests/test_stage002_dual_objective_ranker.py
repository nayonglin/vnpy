from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/stage002_dual_objective_ranker.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stage002_dual_objective_ranker", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_forward_path_metrics_exclude_current_day_and_start_from_zero() -> None:
    module = load_module()
    values = np.array([100.0, 10.0, -20.0, 5.0, 7.0])

    future_sum, future_drawdown = module.forward_path_metrics(values, horizon=3)

    assert future_sum[0] == -5.0
    assert future_drawdown[0] == -20.0
    assert future_sum[1] == -8.0
    assert future_drawdown[1] == -20.0
    assert np.isnan(future_sum[2]) and np.isnan(future_drawdown[2])


def test_dual_objective_labels_are_month_local_integer_relevance() -> None:
    module = load_module()
    frame = pd.DataFrame(
        {
            "eval_date": pd.to_datetime(["2026-01-31"] * 4 + ["2026-02-28"] * 4),
            "product_vt_symbol": ["a", "b", "c", "d"] * 2,
            "future_net_pnl_60d": [100.0, 80.0, 20.0, -10.0, 1.0, 2.0, 3.0, 4.0],
            "future_max_drawdown_60d": [-100.0, -5.0, -10.0, 0.0, -4.0, -3.0, -2.0, -1.0],
        }
    )

    result = module.add_dual_objective_labels(frame)

    for _, month in result.groupby("eval_date"):
        assert sorted(month["dual_relevance_60d"].tolist()) == [0, 1, 2, 3]
        assert month["future_dual_utility_60d"].between(0.25, 1.0).all()
    january = result[result.eval_date.eq(pd.Timestamp("2026-01-31"))].set_index("product_vt_symbol")
    assert january.loc["b", "future_dual_utility_60d"] > january.loc["a", "future_dual_utility_60d"]
    assert january.loc["b", "future_dual_utility_60d"] > january.loc["d", "future_dual_utility_60d"]


def test_ranker_training_arrays_keep_month_groups_contiguous() -> None:
    module = load_module()
    frame = pd.DataFrame(
        {
            "eval_date": pd.to_datetime(["2026-02-28", "2026-01-31", "2026-02-28", "2026-01-31"]),
            "product_vt_symbol": ["b", "b", "a", "a"],
            "dual_relevance_60d": [1, 0, 0, 1],
            "f1": [4.0, 2.0, 3.0, 1.0],
        }
    )

    ordered, x, y, qid = module.ranker_training_arrays(frame, ["f1"])

    assert ordered[["eval_date", "product_vt_symbol"]].values.tolist() == [
        [pd.Timestamp("2026-01-31"), "a"],
        [pd.Timestamp("2026-01-31"), "b"],
        [pd.Timestamp("2026-02-28"), "a"],
        [pd.Timestamp("2026-02-28"), "b"],
    ]
    assert x["f1"].tolist() == [1.0, 2.0, 3.0, 4.0]
    assert y.tolist() == [1, 0, 0, 1]
    assert qid.tolist() == [0, 0, 1, 1]


def test_portfolio_forward_metrics_aggregate_selected_product_paths() -> None:
    module = load_module()
    dates = pd.date_range("2026-01-01", periods=5, freq="D")
    daily = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "product_vt_symbol": ["a"] * 5 + ["b"] * 5,
            "net_pnl": [99.0, 10.0, -20.0, 5.0, 8.0, 99.0, -5.0, -5.0, 20.0, 1.0],
        }
    )

    result = module.portfolio_forward_metrics(
        daily,
        eval_date=pd.Timestamp("2026-01-01"),
        products=("a", "b"),
        horizon=3,
    )

    assert result["future_net_pnl"] == 5.0
    assert result["future_max_drawdown"] == -25.0
    assert result["trading_days"] == 3


def test_candidate_gate_requires_both_return_and_drawdown_improvement() -> None:
    module = load_module()
    passing = {
        "identity_pass": True,
        "determinism_pass": True,
        "path_parity_pass": True,
        "oos_months": 49,
        "a_mean_dual_rank_ic": 0.01,
        "candidate_mean_dual_rank_ic": 0.02,
        "a_median_dual_rank_ic": 0.00,
        "candidate_median_dual_rank_ic": 0.01,
        "a_top10_mean_future_pnl": 100.0,
        "candidate_top10_mean_future_pnl": 101.0,
        "a_top10_p10_future_pnl": -50.0,
        "candidate_top10_p10_future_pnl": -49.0,
        "a_top10_mean_future_drawdown": -40.0,
        "candidate_top10_mean_future_drawdown": -39.0,
        "a_top10_p10_future_drawdown": -80.0,
        "candidate_top10_p10_future_drawdown": -79.0,
        "a_top10_turnover": 0.20,
        "candidate_top10_turnover": 0.21,
        "yearly_candidate_wins": 3,
        "worst_year_dual_rank_ic_delta": -0.02,
    }

    decision = module.evaluate_candidate_gates(passing)
    assert decision["passed"] is True

    decision = module.evaluate_candidate_gates(
        dict(passing, candidate_top10_mean_future_drawdown=-41.0)
    )
    assert decision["passed"] is False
    assert decision["gates"]["top10_mean_future_drawdown_strictly_better"] is False


def test_fixed_ranker_configuration_targets_top10_without_scan() -> None:
    module = load_module()

    assert module.XGBRANKER_PARAMS["objective"] == "rank:ndcg"
    assert module.XGBRANKER_PARAMS["eval_metric"] == "ndcg@10"
    assert module.XGBRANKER_PARAMS["lambdarank_pair_method"] == "topk"
    assert module.XGBRANKER_PARAMS["lambdarank_num_pair_per_sample"] == 10
    assert module.DUAL_PNL_WEIGHT == module.DUAL_DRAWDOWN_WEIGHT == 0.5
