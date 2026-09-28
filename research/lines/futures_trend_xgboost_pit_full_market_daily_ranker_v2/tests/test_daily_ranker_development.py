from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import daily_ranker_development as development


def test_generate_label_values_reads_only_planned_fixed_contract_closes() -> None:
    plan = pd.DataFrame(
        {
            "query_date": ["2024-01-02", "2024-01-02"],
            "product_vt_symbol": ["a.EX", "b.EX"],
            "main_contract_vt": ["A01.EX", "B01.EX"],
            "entry_date": ["2024-01-03", "2024-01-03"],
            "label_end": ["2024-01-31", "2024-01-31"],
            "label_value_read": [False, False],
        }
    )
    prices = pd.DataFrame(
        {
            "date": [
                "2024-01-03",
                "2024-01-31",
                "2024-01-03",
                "2024-01-31",
            ],
            "contract_vt_symbol": ["A01.EX", "A01.EX", "B01.EX", "B01.EX"],
            "close_price": [100.0, 110.0, 200.0, 180.0],
        }
    )

    labels, audit = development.generate_label_values(plan, prices)

    assert labels.set_index("product_vt_symbol").loc[
        "a.EX", "forward_log_return"
    ] == pytest.approx(np.log(1.1))
    assert labels.set_index("product_vt_symbol").loc[
        "b.EX", "forward_log_return"
    ] == pytest.approx(np.log(0.9))
    assert audit == {
        "label_rows": 2,
        "close_value_reads": 4,
        "future_return_calculations": 2,
        "missing_price_rows": 0,
    }


def test_generate_label_values_rejects_missing_or_extra_price_identity() -> None:
    plan = pd.DataFrame(
        {
            "query_date": ["2024-01-02"],
            "product_vt_symbol": ["a.EX"],
            "main_contract_vt": ["A01.EX"],
            "entry_date": ["2024-01-03"],
            "label_end": ["2024-01-31"],
        }
    )
    missing = pd.DataFrame(
        {
            "date": ["2024-01-03"],
            "contract_vt_symbol": ["A01.EX"],
            "close_price": [100.0],
        }
    )
    with pytest.raises(development.DevelopmentError, match="label_price_missing"):
        development.generate_label_values(plan, missing)

    extra = missing.assign(volume=100)
    with pytest.raises(development.DevelopmentError, match="price_columns_invalid"):
        development.generate_label_values(plan, extra)


def test_add_relevance_builds_five_stable_levels_per_daily_qid() -> None:
    products = [f"p{index:02d}.EX" for index in range(10)]
    labels = pd.DataFrame(
        {
            "query_date": ["2024-01-02"] * 10,
            "product_vt_symbol": products,
            "forward_log_return": [0.0, 0.0, *np.arange(2, 10, dtype=float)],
        }
    )

    result = development.add_cross_sectional_relevance(labels)

    assert result.sort_values("product_vt_symbol")["relevance"].tolist() == [
        0,
        0,
        1,
        1,
        2,
        2,
        3,
        3,
        4,
        4,
    ]
    assert result["relevance"].dtype.kind in "iu"


def test_ranker_arrays_sort_qids_and_preserve_frozen_feature_order() -> None:
    frame = pd.DataFrame(
        {
            "query_date": ["2024-01-03", "2024-01-02", "2024-01-03", "2024-01-02"],
            "product_vt_symbol": ["b.EX", "b.EX", "a.EX", "a.EX"],
            "f1": [4.0, 2.0, 3.0, 1.0],
            "f2": [40.0, 20.0, 30.0, 10.0],
            "relevance": [4, 1, 3, 0],
        }
    )

    ordered, features, target, qid = development.build_ranker_arrays(
        frame, ["f2", "f1"]
    )

    assert ordered[["query_date", "product_vt_symbol"]].to_dict("records") == [
        {"query_date": pd.Timestamp("2024-01-02"), "product_vt_symbol": "a.EX"},
        {"query_date": pd.Timestamp("2024-01-02"), "product_vt_symbol": "b.EX"},
        {"query_date": pd.Timestamp("2024-01-03"), "product_vt_symbol": "a.EX"},
        {"query_date": pd.Timestamp("2024-01-03"), "product_vt_symbol": "b.EX"},
    ]
    assert features.columns.tolist() == ["f2", "f1"]
    assert target.tolist() == [0, 1, 3, 4]
    assert qid.tolist() == [0, 0, 1, 1]


def test_select_one_slot_requires_strict_challenger_score_advantage() -> None:
    scored = pd.DataFrame(
        {
            "test_eval_date": ["2024-01-31"] * 4,
            "product_vt_symbol": ["anchor.EX", "a.EX", "b.EX", "c.EX"],
            "role": ["formal_rank10", "challenger", "challenger", "challenger"],
            "xgb_score": [0.5, 0.4, 0.6, 0.6],
        }
    )

    selection = development.select_one_slot(scored)

    assert selection["challenger_product"] == "b.EX"
    assert selection["selected_product"] == "b.EX"
    assert selection["replaced"] is True

    tied = scored.copy()
    tied.loc[tied["role"].eq("challenger"), "xgb_score"] = [0.4, 0.5, 0.5]
    no_replace = development.select_one_slot(tied)
    assert no_replace["selected_product"] == "anchor.EX"
    assert no_replace["replaced"] is False


def test_effect_metrics_use_positive_c_minus_a_drawdown_direction() -> None:
    monthly = pd.DataFrame(
        {
            "test_eval_date": pd.to_datetime(
                ["2023-01-31", "2023-02-28", "2024-01-31", "2025-01-31"]
            ),
            "replaced": [True, True, True, True],
            "a_return": [0.10, -0.20, 0.05, -0.10],
            "c_return": [0.15, -0.05, 0.07, -0.02],
        }
    )

    result = development.compute_effect_metrics(monthly)

    assert result["sum_return_delta"] == pytest.approx(0.30)
    assert result["replacement_positive_rate"] == pytest.approx(1.0)
    assert result["leave_best_month_out_return_delta"] == pytest.approx(0.15)
    assert result["drawdown_improvement"] > 0
    assert result["positive_year_count"] == 3


def test_effect_gate_requires_all_seven_preregistered_conditions() -> None:
    passing = {
        "replacement_count": 12,
        "replacement_positive_rate": 0.6,
        "replacement_median_return_delta": 0.01,
        "sum_return_delta": 0.1,
        "leave_best_month_out_return_delta": 0.02,
        "drawdown_improvement": 0.01,
        "positive_year_count": 3,
    }

    assert development.assess_effect_gates(passing)["passed"] is True
    for field in passing:
        failed = dict(passing)
        failed[field] = 0
        assert development.assess_effect_gates(failed)["passed"] is False


def test_real_xgboost_runtime_is_deterministic_and_preserves_feature_order() -> None:
    rng = np.random.default_rng(42)
    feature_columns = [f"feature_{index}" for index in range(19)]
    train = pd.DataFrame(
        rng.normal(size=(200, len(feature_columns))), columns=feature_columns
    )
    target = np.tile(np.arange(20) * 5 // 20, 10)
    qid = np.repeat(np.arange(10), 20)
    predict = pd.DataFrame(
        rng.normal(size=(20, len(feature_columns))), columns=feature_columns
    )

    result = development.fit_repeated_ranker(
        train,
        target,
        qid,
        predict,
    )

    assert result["prediction_repeat_max_abs_difference"] == 0.0
    assert result["primary_model_sha256"] == result["repeat_model_sha256"]
    assert result["unique_prediction_count"] >= 2
    assert result["split_count"] >= 1
