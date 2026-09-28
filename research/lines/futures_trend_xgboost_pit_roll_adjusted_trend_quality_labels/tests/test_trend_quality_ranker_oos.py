from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import trend_quality_ranker_oos as ranker


def test_ai_universe_labels_exclude_fixed_fu_and_recompute_relevance() -> None:
    products = [ranker.FIXED_PRODUCT, *[f"p{index:02d}.EX" for index in range(10)]]
    labels = pd.DataFrame(
        {
            "query_date": ["2024-01-31"] * len(products),
            "product_vt_symbol": products,
            "future_trend_capture_quality": np.arange(len(products), dtype=float),
            "future_abs_log_return": np.arange(len(products), dtype=float) + 1,
            "future_oriented_max_drawdown": np.full(len(products), -0.1),
            "trend_quality_relevance": np.full(len(products), 4),
        }
    )

    result, audit = ranker.prepare_ai_universe_labels(
        labels, minimum_qid_width=5
    )

    assert ranker.FIXED_PRODUCT not in set(result["product_vt_symbol"])
    assert audit["fixed_product_rows_excluded"] == 1
    assert audit["ai_label_rows"] == 10
    assert result["trend_quality_relevance"].nunique() == 5
    assert result.sort_values("future_trend_capture_quality")[
        "trend_quality_relevance"
    ].tolist() == [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]


def test_consensus_selector_replaces_only_on_top10_disagreement() -> None:
    products = [f"p{index:02d}.EX" for index in range(12)]
    full = pd.DataFrame(
        {
            "query_date": ["2024-01-31"] * 12,
            "product_vt_symbol": products,
            "xgb_score": np.arange(12, 0, -1, dtype=float),
        }
    )
    scoring = pd.DataFrame(
        {
            "test_eval_date": ["2024-01-31"] * 3,
            "product_vt_symbol": ["p10.EX", "p03.EX", "p11.EX"],
            "role": ["formal_rank10", "challenger", "challenger"],
        }
    )

    selection = ranker.select_consensus_one_slot(full, scoring, top_k=10)

    assert selection["anchor_product"] == "p10.EX"
    assert selection["anchor_xgb_rank"] == 11
    assert selection["challenger_product"] == "p03.EX"
    assert selection["challenger_xgb_rank"] == 4
    assert selection["selected_product"] == "p03.EX"
    assert selection["replaced"] is True
    assert selection["replacement_reason"] == "xgb_top10_disagrees"

    retained_scoring = scoring.copy()
    retained_scoring.loc[0, "product_vt_symbol"] = "p02.EX"
    retained = ranker.select_consensus_one_slot(full, retained_scoring, top_k=10)
    assert retained["selected_product"] == "p02.EX"
    assert retained["replaced"] is False
    assert retained["replacement_reason"] == "anchor_in_xgb_top10"


def test_consensus_selector_uses_product_order_for_score_ties() -> None:
    full = pd.DataFrame(
        {
            "query_date": ["2024-01-31"] * 4,
            "product_vt_symbol": ["anchor.EX", "b.EX", "a.EX", "other.EX"],
            "xgb_score": [0.0, 1.0, 1.0, 2.0],
        }
    )
    scoring = pd.DataFrame(
        {
            "test_eval_date": ["2024-01-31"] * 3,
            "product_vt_symbol": ["anchor.EX", "b.EX", "a.EX"],
            "role": ["formal_rank10", "challenger", "challenger"],
        }
    )

    selected = ranker.select_consensus_one_slot(full, scoring, top_k=3)

    assert selected["challenger_product"] == "a.EX"
    assert selected["challenger_xgb_rank"] == 2


def test_consensus_selector_rejects_fixed_fu_in_ai_universe() -> None:
    full = pd.DataFrame(
        {
            "query_date": ["2024-01-31"] * 3,
            "product_vt_symbol": [ranker.FIXED_PRODUCT, "anchor.EX", "c.EX"],
            "xgb_score": [2.0, 1.0, 0.0],
        }
    )
    scoring = pd.DataFrame(
        {
            "test_eval_date": ["2024-01-31"] * 2,
            "product_vt_symbol": ["anchor.EX", "c.EX"],
            "role": ["formal_rank10", "challenger"],
        }
    )

    with pytest.raises(ranker.TrendQualityRankerError, match="fixed_product"):
        ranker.select_consensus_one_slot(full, scoring, top_k=2)


def test_linear_ndcg_is_tie_aware_and_has_exact_random_expectation() -> None:
    frame = pd.DataFrame(
        {
            "product_vt_symbol": ["a.EX", "b.EX", "c.EX", "d.EX"],
            "xgb_score": [2.0, 2.0, 1.0, 0.0],
            "trend_quality_relevance": [3, 1, 2, 0],
        }
    )

    result = ranker.linear_ndcg_at_k(frame, k=2)

    discounts = 1.0 / np.log2(np.arange(2, 4))
    expected_dcg = 2.0 * discounts.sum()
    ideal_dcg = 3.0 * discounts[0] + 2.0 * discounts[1]
    random_dcg = 1.5 * discounts.sum()
    assert result["ndcg_at_k"] == pytest.approx(expected_dcg / ideal_dcg)
    assert result["random_expected_ndcg_at_k"] == pytest.approx(
        random_dcg / ideal_dcg
    )


def test_month_rank_metrics_use_continuous_quality_and_linear_relevance() -> None:
    frame = pd.DataFrame(
        {
            "query_date": ["2024-01-31"] * 5,
            "product_vt_symbol": [f"p{i}.EX" for i in range(5)],
            "xgb_score": [1, 2, 3, 4, 5],
            "future_trend_capture_quality": [0, 1, 2, 3, 4],
            "trend_quality_relevance": [0, 1, 2, 3, 4],
        }
    )

    result = ranker.compute_month_rank_metrics(frame)

    assert result["rank_ic"] == pytest.approx(1.0)
    assert result["ndcg_at_10"] == pytest.approx(1.0)
    assert result["ndcg_delta_vs_random"] > 0


def test_predictive_metrics_and_gates_require_all_preregistered_conditions() -> None:
    dates = pd.date_range("2023-01-31", periods=36, freq="ME")
    monthly = pd.DataFrame(
        {
            "test_eval_date": dates,
            "rank_ic": [0.1] * 36,
            "ndcg_at_10": [0.8] * 36,
            "random_expected_ndcg_at_10": [0.6] * 36,
        }
    )

    metrics = ranker.compute_predictive_metrics(monthly)
    result = ranker.assess_predictive_gates(metrics)

    assert metrics["effect_month_count"] == 36
    assert metrics["positive_rank_ic_month_count"] == 36
    assert metrics["positive_rank_ic_year_count"] == 3
    assert result["passed"] is True
    for field in (
        "mean_rank_ic",
        "median_rank_ic",
        "positive_rank_ic_month_count",
        "leave_best_month_out_rank_ic_sum",
        "positive_rank_ic_year_count",
        "mean_ndcg_delta_vs_random",
        "ndcg_beats_random_month_count",
    ):
        failed = dict(metrics)
        failed[field] = 0
        assert ranker.assess_predictive_gates(failed)["passed"] is False


def test_effect_metrics_require_quality_return_and_drawdown_proxy_robustness() -> None:
    dates = pd.date_range("2023-03-31", periods=36, freq="ME")
    replaced = np.arange(36) % 3 == 0
    monthly = pd.DataFrame(
        {
            "test_eval_date": dates,
            "replaced": replaced,
            "a_quality": np.zeros(36),
            "c_quality": np.where(replaced, 0.02, 0.0),
            "a_abs_log_return": np.full(36, 0.05),
            "c_abs_log_return": np.where(replaced, 0.06, 0.05),
            "a_oriented_max_drawdown": np.full(36, -0.04),
            "c_oriented_max_drawdown": np.where(replaced, -0.03, -0.04),
        }
    )

    metrics = ranker.compute_effect_metrics(monthly)
    result = ranker.assess_effect_gates(metrics)

    assert metrics["replacement_count"] == 12
    assert metrics["sum_quality_delta"] == pytest.approx(0.24)
    assert metrics["sum_abs_log_return_delta"] == pytest.approx(0.12)
    assert metrics["sum_oriented_max_drawdown_delta"] == pytest.approx(0.12)
    assert result["passed"] is True
    for field in (
        "replacement_count",
        "replacement_quality_positive_rate",
        "replacement_median_quality_delta",
        "sum_quality_delta",
        "leave_best_month_out_quality_delta",
        "positive_quality_year_count",
        "sum_abs_log_return_delta",
        "leave_best_month_out_abs_log_return_delta",
        "sum_oriented_max_drawdown_delta",
        "leave_best_month_out_oriented_max_drawdown_delta",
    ):
        failed = dict(metrics)
        failed[field] = 0
        assert ranker.assess_effect_gates(failed)["passed"] is False


def test_effect_row_uses_selected_product_and_positive_drawdown_improvement() -> None:
    labels = pd.DataFrame(
        {
            "query_date": ["2024-01-31", "2024-01-31"],
            "product_vt_symbol": ["anchor.EX", "challenger.EX"],
            "future_trend_capture_quality": [0.02, 0.05],
            "future_abs_log_return": [0.08, 0.10],
            "future_oriented_max_drawdown": [-0.06, -0.05],
            "trend_quality_relevance": [2, 4],
        }
    )
    selection = {
        "test_eval_date": "2024-01-31",
        "anchor_product": "anchor.EX",
        "challenger_product": "challenger.EX",
        "selected_product": "challenger.EX",
        "replaced": True,
    }

    row = ranker.build_effect_row(selection, labels)

    assert row["quality_delta"] == pytest.approx(0.03)
    assert row["abs_log_return_delta"] == pytest.approx(0.02)
    assert row["oriented_max_drawdown_delta"] == pytest.approx(0.01)


def test_effect_metrics_reject_nonzero_nonreplacement_delta() -> None:
    monthly = pd.DataFrame(
        {
            "test_eval_date": ["2024-01-31"],
            "replaced": [False],
            "a_quality": [0.1],
            "c_quality": [0.2],
            "a_abs_log_return": [0.1],
            "c_abs_log_return": [0.1],
            "a_oriented_max_drawdown": [-0.1],
            "c_oriented_max_drawdown": [-0.1],
        }
    )

    with pytest.raises(ranker.TrendQualityRankerError, match="nonreplacement"):
        ranker.compute_effect_metrics(monthly)


def test_phase_gated_store_requires_seal_before_test_qid_access() -> None:
    labels = pd.DataFrame(
        {
            "query_date": ["2024-01-31", "2024-02-29"],
            "product_vt_symbol": ["a.EX", "b.EX"],
            "future_trend_capture_quality": [0.1, 0.2],
            "future_abs_log_return": [0.2, 0.3],
            "future_oriented_max_drawdown": [-0.1, -0.1],
            "trend_quality_relevance": [3, 4],
        }
    )
    paths = pd.DataFrame(
        {
            "query_date": ["2024-01-31", "2024-02-29"],
            "product_vt_symbol": ["a.EX", "b.EX"],
            "label_end": ["2024-02-28", "2024-03-29"],
        }
    )
    store = ranker.PhaseGatedTrendQualityStore(labels, paths)

    train = store.open_training_labels(pd.Timestamp("2024-03-01"))
    assert train["product_vt_symbol"].tolist() == ["a.EX"]
    assert store.label_rows_opened_for(pd.Timestamp("2024-02-29")) == 0
    with pytest.raises(ranker.TrendQualityRankerError, match="effect_not_authorized"):
        store.open_effect_qid(pd.Timestamp("2024-02-29"))

    store.authorize_effect_qid(pd.Timestamp("2024-02-29"))
    effect = store.open_effect_qid(pd.Timestamp("2024-02-29"))
    assert effect["product_vt_symbol"].tolist() == ["b.EX"]
    assert store.label_rows_opened_for(pd.Timestamp("2024-02-29")) == 1
    with pytest.raises(ranker.TrendQualityRankerError, match="already_opened"):
        store.open_effect_qid(pd.Timestamp("2024-02-29"))
