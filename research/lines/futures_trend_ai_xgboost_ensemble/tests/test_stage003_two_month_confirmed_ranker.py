from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/stage003_two_month_confirmed_ranker.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stage003_two_month_confirmed_ranker", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample_predictions() -> pd.DataFrame:
    products = ["a", "b", "c", "d", "e"]
    rows = []
    inputs = [
        ("2026-01-31", [5, 4, 3, 2, 1], [5, 4, 3, 2, 1]),
        ("2026-02-28", [3, 2, 1, 4, 5], [1, 4, 3, 5, 2]),
        ("2026-03-31", [1, 2, 3, 4, 5], [5, 1, 4, 3, 2]),
    ]
    for date, logistic_scores, fused_scores in inputs:
        for product, logistic, fused in zip(products, logistic_scores, fused_scores):
            rows.append(
                {
                    "eval_date": pd.Timestamp(date),
                    "product_vt_symbol": product,
                    "score_logistic": float(logistic),
                    "score_fused": float(fused),
                }
            )
    return pd.DataFrame(rows)


def test_first_month_is_exact_logistic_order() -> None:
    module = load_module()

    result = module.add_two_month_confirmed_scores(sample_predictions(), top_n=3)
    first = result[result.eval_date.eq(pd.Timestamp("2026-01-31"))].sort_values(
        "score_two_month_confirmed", ascending=False
    )

    assert first.product_vt_symbol.tolist() == ["a", "b", "c", "d", "e"]
    assert first.head(3).confirmed_by_two_months.eq(False).all()


def test_second_month_uses_only_consecutive_raw_members_then_logistic_fill() -> None:
    module = load_module()

    result = module.add_two_month_confirmed_scores(sample_predictions(), top_n=3)
    second = result[result.eval_date.eq(pd.Timestamp("2026-02-28"))].sort_values(
        "score_two_month_confirmed", ascending=False
    )

    assert second.head(3).product_vt_symbol.tolist() == ["b", "c", "e"]
    assert second[second.confirmed_by_two_months].product_vt_symbol.tolist() == ["b", "c"]
    assert second.confirmed_count.iloc[0] == 2


def test_confirmation_uses_immediately_previous_raw_pool_not_previous_output() -> None:
    module = load_module()

    result = module.add_two_month_confirmed_scores(sample_predictions(), top_n=3)
    third = result[result.eval_date.eq(pd.Timestamp("2026-03-31"))].sort_values(
        "score_two_month_confirmed", ascending=False
    )

    # February raw C top3 is d,b,c; March raw C top3 is a,c,d.
    assert third[third.confirmed_by_two_months].product_vt_symbol.tolist() == ["c", "d"]
    assert third.head(3).product_vt_symbol.tolist() == ["c", "d", "e"]


def test_candidate_pool_is_unique_and_fixed_width_each_month() -> None:
    module = load_module()

    result = module.add_two_month_confirmed_scores(sample_predictions(), top_n=3)
    for _, month in result.groupby("eval_date"):
        selected = month.nlargest(3, "score_two_month_confirmed")
        assert len(selected) == 3
        assert selected.product_vt_symbol.nunique() == 3

