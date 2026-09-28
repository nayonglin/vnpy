from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/market_context_features.py"
SPEC = importlib.util.spec_from_file_location("market_context_features", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


DATES = pd.date_range("2024-01-02", periods=4, freq="D")


def _ranked() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "eval_date": ["2024-01-05"] * 5,
            "product_vt_symbol": ["t1.X", "t2.X", "b.X", "c.X", "d.X"],
            "window_id": ["wf_01"] * 5,
            "pit_logistic_probability": [0.9, 0.8, 0.7, 0.6, 0.5],
            "a_rank": [1, 2, 3, 4, 5],
            "role": ["top9", "top9", "a_rank10", "challenger", "challenger"],
        }
    )


def _coverage() -> pd.DataFrame:
    frame = _ranked().copy()
    frame["valid_return_count"] = 4
    frame["required_return_count"] = 4
    frame["window_complete"] = True
    frame["context_eligible"] = frame["role"].isin(["a_rank10", "challenger"])
    return frame


def _months() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "eval_date": ["2024-01-05"],
            "window_id": ["wf_01"],
            "window_start": ["2024-01-02"],
            "window_end": ["2024-01-05"],
            "window_date_count": [4],
            "overlay_active": [True],
        }
    )


def _returns(*, omit: tuple[str, pd.Timestamp] | None = None) -> pd.DataFrame:
    h = [-0.01, 0.01, -0.02, 0.02]
    values = {
        "t1.X": h,
        "t2.X": h,
        "b.X": h,
        "c.X": [0.01, -0.01, 0.02, -0.02],
        "d.X": [-0.03, 0.02, -0.01, 0.04],
    }
    rows: list[dict[str, object]] = []
    for product, product_values in values.items():
        for return_date, value in zip(DATES, product_values, strict=True):
            if omit == (product, return_date):
                continue
            rows.append(
                {
                    "product_vt_symbol": product,
                    "selection_date": return_date - pd.Timedelta(days=1),
                    "return_date": return_date,
                    "selected_contract_vt": f"{product.split('.')[0]}2401.X",
                    "product_return": value,
                    "status": "ok",
                    "fallback_used": False,
                    "cross_contract_price_used": False,
                }
            )
    rows.append(
        {
            "product_vt_symbol": "c.X",
            "selection_date": pd.Timestamp("2024-01-05"),
            "return_date": pd.Timestamp("2024-01-06"),
            "selected_contract_vt": "c2401.X",
            "product_return": 99.0,
            "status": "ok",
            "fallback_used": False,
            "cross_contract_price_used": False,
        }
    )
    return pd.DataFrame(rows)


def test_feature_formula_has_exact_anchor_zero_and_hand_checked_candidate_signs() -> None:
    features, audit = module.build_market_context_features(
        _ranked(),
        _coverage(),
        _months(),
        _returns(),
        window_days=4,
        top_rank_count=2,
        minimum_downside_days=2,
    )
    by_product = features.set_index("product_vt_symbol")
    feature_columns = list(module.FEATURE_COLUMNS)

    assert by_product.loc["b.X", feature_columns].tolist() == [0.0] * 6
    candidate = by_product.loc["c.X"]
    assert candidate["candidate_top9_corr_120d_delta_vs_rank10"] == pytest.approx(-2.0)
    assert candidate["candidate_top9_downside_corr_120d_delta_vs_rank10"] == pytest.approx(-2.0)
    assert candidate["candidate_volatility_120d_log_ratio_vs_rank10"] == pytest.approx(0.0)
    assert candidate["candidate_downside_deviation_120d_log_ratio_vs_rank10"] == pytest.approx(0.0)
    assert candidate[
        "top9_plus_candidate_compound_drawdown_improvement_120d_vs_rank10"
    ] > 0.0
    assert candidate["top9_plus_candidate_sharpe_improvement_120d_vs_rank10"] == pytest.approx(0.0)
    assert audit.loc[0, "window_end"] == pd.Timestamp("2024-01-05")
    assert audit.loc[0, "future_return_rows_used"] == 0
    assert audit.loc[0, "downside_day_count"] == 2


def test_missing_required_top_return_fails_instead_of_imputing() -> None:
    with pytest.raises(module.MarketContextFeatureError, match="required_return_missing"):
        module.build_market_context_features(
            _ranked(),
            _coverage(),
            _months(),
            _returns(omit=("t1.X", pd.Timestamp("2024-01-04"))),
            window_days=4,
            top_rank_count=2,
            minimum_downside_days=2,
        )


def test_feature_assessment_rejects_a_nonzero_anchor_row() -> None:
    features, audit = module.build_market_context_features(
        _ranked(),
        _coverage(),
        _months(),
        _returns(),
        window_days=4,
        top_rank_count=2,
        minimum_downside_days=2,
    )
    broken = features.copy()
    broken.loc[broken["role"].eq("a_rank10"), module.FEATURE_COLUMNS[0]] = 0.5
    summary = module.assess_feature_contract(
        broken,
        audit,
        accepted_window_ids=["wf_01"],
        expected_rows=3,
        expected_months=1,
        expected_anchor_rows=1,
        expected_challenger_rows=2,
        expected_min_rows_per_month=3,
        expected_max_rows_per_month=3,
        window_days=4,
        minimum_downside_days=2,
        minimum_unique_challenger_values=1,
    )

    assert summary["decision"] == "stage002_market_context_features_fail_stop_no_ranker"
    assert summary["gates"]["anchor_features_exact_zero"] is False
    assert summary["all_gates_passed"] is False

