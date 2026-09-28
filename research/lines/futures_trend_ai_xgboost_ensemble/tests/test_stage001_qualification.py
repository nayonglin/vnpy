from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/stage001_xgboost_qualification.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stage001_xgboost_qualification", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_walk_forward_split_keeps_label_gap_and_minimum_history() -> None:
    module = load_module()
    dates = pd.date_range("2020-01-31", periods=36, freq="ME")
    frame = pd.DataFrame(
        {
            "eval_date": np.repeat(dates, 2),
            "product_vt_symbol": ["a", "b"] * len(dates),
        }
    )

    splits = module.build_monthly_splits(frame, min_train_months=24, label_gap_days=92)

    assert splits
    for split in splits:
        assert split.train_dates.max() <= split.test_date - pd.Timedelta(days=92)
        assert len(split.train_dates) >= 24
        assert split.test_date not in set(split.train_dates)


def test_frozen_feature_code_loads_with_explicit_verified_universe() -> None:
    module = load_module()
    products = ["AP.CZCE", "au.SHFE"]

    frozen = module._load_frozen_model_code(products)

    assert frozen.VT_SYMBOLS == products


def test_percentile_fusion_is_month_local_and_high_score_first() -> None:
    module = load_module()
    frame = pd.DataFrame(
        {
            "eval_date": pd.to_datetime(["2026-01-31"] * 4 + ["2026-02-28"] * 4),
            "product_vt_symbol": ["a", "b", "c", "d"] * 2,
            "score_a": [0.9, 0.8, 0.05, 0.2, 0.1, 0.2, 0.3, 0.4],
            "score_b": [0.1, 0.8, 0.9, 0.2, 0.1, 0.2, 0.3, 0.4],
        }
    )

    result = module.add_rank_fusion(frame, "score_a", "score_b", weight_a=0.5)

    january = result[result.eval_date.eq(pd.Timestamp("2026-01-31"))].set_index("product_vt_symbol")
    assert january.loc["b", "score_fused"] > january.loc["a", "score_fused"]
    assert january.loc["b", "score_fused"] > january.loc["c", "score_fused"]
    february = result[result.eval_date.eq(pd.Timestamp("2026-02-28"))].sort_values("score_fused", ascending=False)
    assert february.product_vt_symbol.tolist() == ["d", "c", "b", "a"]


def test_topn_turnover_ignores_first_month_and_counts_replacements() -> None:
    module = load_module()
    selected = {
        pd.Timestamp("2026-01-31"): ("a", "b"),
        pd.Timestamp("2026-02-28"): ("a", "c"),
        pd.Timestamp("2026-03-31"): ("c", "d"),
    }

    assert module.mean_topn_turnover(selected) == 0.5


def test_promotion_requires_every_predeclared_gate() -> None:
    module = load_module()
    passing = {
        "identity_pass": True,
        "determinism_pass": True,
        "oos_months": 48,
        "a_mean_rank_ic": 0.10,
        "c_mean_rank_ic": 0.12,
        "a_median_rank_ic": 0.08,
        "c_median_rank_ic": 0.08,
        "a_top10_mean_future_pnl": 100.0,
        "c_top10_mean_future_pnl": 101.0,
        "a_top10_p10_future_pnl": -50.0,
        "c_top10_p10_future_pnl": -49.0,
        "a_top10_top_half_rate": 0.60,
        "c_top10_top_half_rate": 0.60,
        "a_top10_turnover": 0.20,
        "c_top10_turnover": 0.21,
        "yearly_c_wins": 3,
        "worst_year_rank_ic_delta": -0.02,
    }

    decision = module.evaluate_promotion_gates(passing)
    assert decision["passed"] is True
    assert all(decision["gates"].values())

    failing = dict(passing, c_top10_p10_future_pnl=-51.0)
    decision = module.evaluate_promotion_gates(failing)
    assert decision["passed"] is False
    assert decision["gates"]["top10_p10_future_pnl_noninferior"] is False


def test_rank_only_fusion_does_not_report_probability_log_loss() -> None:
    module = load_module()
    actual = pd.Series([0, 0, 1, 1])
    rank_score = pd.Series([0.25, 0.50, 0.75, 1.00])

    metrics = module.probability_metrics(actual, rank_score, is_probability=False)

    assert metrics["roc_auc"] == 1.0
    assert metrics["log_loss"] is None
