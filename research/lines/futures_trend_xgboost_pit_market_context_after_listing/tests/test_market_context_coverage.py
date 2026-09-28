from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/market_context_coverage.py"
SPEC = importlib.util.spec_from_file_location("market_context_coverage", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _scores(eval_date: str = "2024-01-05", window_id: str = "wf_01") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "eval_date": [eval_date] * 5,
            "product_vt_symbol": ["e.X", "b.X", "a.X", "d.X", "c.X"],
            "pit_logistic_probability": [0.10, 0.80, 0.80, 0.20, 0.30],
            "window_id": [window_id] * 5,
        }
    )


def _returns(
    *,
    missing: tuple[str, str] | None = None,
    future_violation: bool = False,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for product in ["a.X", "b.X", "c.X", "d.X", "e.X"]:
        for index, return_date in enumerate(["2024-01-03", "2024-01-04", "2024-01-05"]):
            is_missing = missing == (product, return_date)
            selection_date = pd.Timestamp(return_date) - pd.Timedelta(days=1)
            if future_violation and product == "e.X" and return_date == "2024-01-05":
                selection_date = pd.Timestamp(return_date)
            rows.append(
                {
                    "product_vt_symbol": product,
                    "selection_date": selection_date,
                    "return_date": pd.Timestamp(return_date),
                    "selected_contract_vt": f"{product.split('.')[0]}2401.X",
                    "product_return": np.nan if is_missing else 0.01 * (index + 1),
                    "status": "selected_contract_close_missing" if is_missing else "ok",
                    "fallback_used": False,
                    "cross_contract_price_used": False,
                }
            )
    rows.append(
        {
            "product_vt_symbol": "a.X",
            "selection_date": pd.Timestamp("2024-01-05"),
            "return_date": pd.Timestamp("2024-01-06"),
            "selected_contract_vt": "a2401.X",
            "product_return": 9.99,
            "status": "ok",
            "fallback_used": False,
            "cross_contract_price_used": False,
        }
    )
    return pd.DataFrame(rows)


def test_assign_anchor_roles_uses_probability_then_symbol_tiebreak() -> None:
    ranked = module.assign_anchor_roles(_scores(), top_rank_count=2)

    assert ranked["product_vt_symbol"].tolist() == ["a.X", "b.X", "c.X", "d.X", "e.X"]
    assert ranked["a_rank"].tolist() == [1, 2, 3, 4, 5]
    assert ranked["role"].tolist() == ["top9", "top9", "a_rank10", "challenger", "challenger"]
    assert ranked["window_id"].nunique() == 1


def test_incomplete_challenger_disables_only_that_challenger_not_a_panel() -> None:
    ranked = module.assign_anchor_roles(_scores(), top_rank_count=2)
    coverage, missing, months = module.audit_context_windows(
        ranked,
        _returns(missing=("e.X", "2024-01-04")),
        window_days=3,
        top_rank_count=2,
        minimum_complete_challengers=1,
    )

    assert len(coverage) == 5
    assert set(coverage["product_vt_symbol"]) == {"a.X", "b.X", "c.X", "d.X", "e.X"}
    incomplete = coverage.set_index("product_vt_symbol").loc["e.X"]
    assert bool(incomplete["window_complete"]) is False
    assert bool(incomplete["context_eligible"]) is False
    assert missing[["return_date", "product_vt_symbol"]].to_dict("records") == [
        {"return_date": pd.Timestamp("2024-01-04"), "product_vt_symbol": "e.X"}
    ]
    assert bool(months.loc[0, "overlay_active"]) is True
    assert months.loc[0, "complete_challenger_count"] == 1
    assert months.loc[0, "window_end"] == pd.Timestamp("2024-01-05")
    assert months.loc[0, "future_return_rows_used"] == 0


def test_incomplete_top_product_deactivates_month_without_removing_rows() -> None:
    ranked = module.assign_anchor_roles(_scores(), top_rank_count=2)
    coverage, _, months = module.audit_context_windows(
        ranked,
        _returns(missing=("a.X", "2024-01-04")),
        window_days=3,
        top_rank_count=2,
        minimum_complete_challengers=2,
    )

    assert len(coverage) == 5
    assert months.loc[0, "complete_top_count"] == 1
    assert bool(months.loc[0, "overlay_active"]) is False


def test_assessment_passes_only_when_month_year_fold_and_pit_gates_pass() -> None:
    ranked = module.assign_anchor_roles(_scores(), top_rank_count=2)
    coverage, missing, months = module.audit_context_windows(
        ranked,
        _returns(),
        window_days=3,
        top_rank_count=2,
        minimum_complete_challengers=2,
    )
    summary = module.assess_context_coverage(
        ranked,
        coverage,
        missing,
        months,
        _returns(),
        accepted_window_ids=["wf_01"],
        expected_rows=5,
        expected_months=1,
        expected_min_products=5,
        expected_max_products=5,
        top_rank_count=2,
        expected_top_rows=2,
        expected_anchor_rows=1,
        expected_challenger_rows=2,
        window_days=3,
        minimum_active_months=1,
        minimum_active_months_by_year={2024: 1},
        minimum_active_months_per_fold=1,
        minimum_complete_challengers=2,
    )

    assert summary["decision"] == "stage001_market_context_coverage_pass_ready_for_feature_preregistration"
    assert summary["all_gates_passed"] is True
    assert summary["active_months"] == 1
    assert summary["active_months_by_year"] == {"2024": 1}
    assert summary["active_months_by_fold"] == {"wf_01": 1}


def test_assessment_fails_closed_on_future_selection_date() -> None:
    ranked = module.assign_anchor_roles(_scores(), top_rank_count=2)
    returns = _returns(future_violation=True)
    coverage, missing, months = module.audit_context_windows(
        ranked,
        returns,
        window_days=3,
        top_rank_count=2,
        minimum_complete_challengers=2,
    )
    summary = module.assess_context_coverage(
        ranked,
        coverage,
        missing,
        months,
        returns,
        accepted_window_ids=["wf_01"],
        expected_rows=5,
        expected_months=1,
        expected_min_products=5,
        expected_max_products=5,
        top_rank_count=2,
        expected_top_rows=2,
        expected_anchor_rows=1,
        expected_challenger_rows=2,
        window_days=3,
        minimum_active_months=1,
        minimum_active_months_by_year={2024: 1},
        minimum_active_months_per_fold=1,
        minimum_complete_challengers=2,
    )

    assert summary["decision"] == "stage001_market_context_coverage_fail_stop_no_features"
    assert summary["pit_violation_rows"] == 1
    assert summary["gates"]["pit_violation_rows_zero"] is False
    assert summary["all_gates_passed"] is False

