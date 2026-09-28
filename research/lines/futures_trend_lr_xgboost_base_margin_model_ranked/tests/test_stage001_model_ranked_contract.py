from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage001_model_ranked_contract as stage001


def _published_pool(*, fixed_feature_value: float = np.nan, fixed_model_rank: float = np.nan) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for rank in range(1, 11):
        rows.append(
            {
                "eval_date": "2026-08-31",
                "product_vt_symbol": f"p{rank}.TEST",
                "selection_role": "model_ranked",
                "model_ai_rank": float(rank),
                "feature_a": float(rank),
                "feature_b": float(rank * 2),
            }
        )
    rows.append(
        {
            "eval_date": "2026-08-31",
            "product_vt_symbol": "fu.SHFE",
            "selection_role": "fixed_fu",
            "model_ai_rank": fixed_model_rank,
            "feature_a": fixed_feature_value,
            "feature_b": np.nan,
        }
    )
    return pd.DataFrame(rows)


def _passing_metrics() -> dict[str, object]:
    return {
        "input_identity_mismatch_count": 0,
        "predecessor_final_read_count": 0,
        "current_release_id": stage001.EXPECTED_RELEASE_ID,
        "current_strategy_id": stage001.EXPECTED_STRATEGY_ID,
        "current_pointer_matches_release": True,
        "m0004_m0005_model_code_equal": True,
        "m0004_m0005_runner_code_equal": True,
        "official_ranked_product_count": 10,
        "official_total_product_count": 11,
        "official_fixed_product": "fu.SHFE",
        "feature_count": 108,
        "train_months": 77,
        "train_rows": 1386,
        "minimum_products_per_train_month": 18,
        "maximum_products_per_train_month": 18,
        "nonfinite_feature_cells": 0,
        "historical_parity_months": 76,
        "historical_parity_rows": 1368,
        "historical_parity_max_abs_error": 0.0,
        "latest_pool_rows": 11,
        "latest_model_ranked_rows": 10,
        "latest_fixed_fu_rows": 1,
        "latest_fixed_product_match": True,
        "latest_model_ranked_contains_fixed_product_count": 0,
        "latest_model_ranked_complete_feature_rows": 10,
        "latest_fixed_fu_nonnull_feature_cells": 0,
        "latest_fixed_fu_nonnull_model_rank_rows": 0,
        "latest_model_ranked_parity_rows": 10,
        "latest_model_ranked_parity_max_abs_error": 0.0,
        "label_calendar_rows": 77,
        "label_calendar_missing_end_rows": 0,
        "active_folds": 50,
        "effect_evaluable_folds": 50,
        "minimum_train_months": 24,
        "maximum_train_months": 74,
        "pit_violation_rows": 0,
        "pit_violation_folds": 0,
        "forbidden_columns_read_count": 0,
        "future_label_value_read_count": 0,
        "model_fit_count": 0,
        "model_predict_count": 0,
        "strategy_backtest_count": 0,
        "ctp_connection_count": 0,
        "order_api_call_count": 0,
        "production_write_count": 0,
    }


def test_classify_published_pool_separates_model_rows_and_fixed_fu() -> None:
    model_rows, metrics = stage001.classify_published_pool(
        _published_pool(),
        ["feature_a", "feature_b"],
    )

    assert len(model_rows) == 10
    assert model_rows["selection_role"].eq("model_ranked").all()
    assert metrics == {
        "latest_pool_rows": 11,
        "latest_model_ranked_rows": 10,
        "latest_fixed_fu_rows": 1,
        "latest_fixed_product_match": True,
        "latest_model_ranked_contains_fixed_product_count": 0,
        "latest_model_ranked_complete_feature_rows": 10,
        "latest_fixed_fu_nonnull_feature_cells": 0,
        "latest_fixed_fu_nonnull_model_rank_rows": 0,
    }


@pytest.mark.parametrize(
    ("fixed_feature_value", "fixed_model_rank", "field", "expected"),
    [
        (1.0, np.nan, "latest_fixed_fu_nonnull_feature_cells", 1),
        (np.nan, 11.0, "latest_fixed_fu_nonnull_model_rank_rows", 1),
    ],
)
def test_classify_published_pool_exposes_fixed_fu_model_leakage(
    fixed_feature_value: float,
    fixed_model_rank: float,
    field: str,
    expected: int,
) -> None:
    _, metrics = stage001.classify_published_pool(
        _published_pool(
            fixed_feature_value=fixed_feature_value,
            fixed_model_rank=fixed_model_rank,
        ),
        ["feature_a", "feature_b"],
    )

    assert metrics[field] == expected


def test_gate_assessment_accepts_exact_model_publication_boundary() -> None:
    result = stage001.assess_gates(_passing_metrics())

    assert result["all_gates_passed"] is True
    assert result["failures"] == []
    assert result["decision"] == stage001.PASS_DECISION


@pytest.mark.parametrize(
    ("field", "value", "failure"),
    [
        ("official_ranked_product_count", 11, "official_policy_boundary"),
        ("latest_fixed_fu_nonnull_feature_cells", 1, "fixed_fu_non_model_boundary"),
        ("latest_model_ranked_parity_rows", 9, "latest_model_ranked_feature_parity"),
        ("active_folds", 49, "pit_fold_contract"),
        ("predecessor_final_read_count", 1, "predecessor_final_isolation"),
    ],
)
def test_gate_assessment_fails_closed(field: str, value: object, failure: str) -> None:
    metrics = _passing_metrics()
    metrics[field] = value

    result = stage001.assess_gates(metrics)

    assert result["all_gates_passed"] is False
    assert failure in result["failures"]
    assert result["decision"] == stage001.FAIL_DECISION


def test_read_path_rejects_predecessor_final() -> None:
    forbidden = stage001.PREDECESSOR_FINAL_DIR / "summary.json"

    with pytest.raises(stage001.Stage001Error, match="predecessor_final_read_forbidden"):
        stage001.assert_read_path_allowed(forbidden)


def test_read_path_allows_frozen_predecessor_tool() -> None:
    stage001.assert_read_path_allowed(stage001.PREDECESSOR_CAUSAL_TOOL)
