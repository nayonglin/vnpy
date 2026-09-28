from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/stage004_fullperiod_true_engine.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stage004_fullperiod_true_engine", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample_formal() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    pre_ai_products = [f"pre{i:02d}.X" for i in range(18)]
    for rank, product in enumerate(pre_ai_products, start=1):
        rows.append(
            {
                "strategy": "official",
                "score_type": "static18_pre_ai_boundary",
                "eval_date": "2019-12-31",
                "product_vt_symbol": product,
                "score": 0.0,
                "score_rank": rank,
                "top_n": 18,
            }
        )
    products = [f"p{i:02d}.X" for i in range(18)]
    for eval_date in ("2022-03-31", "2022-04-29", "2022-05-31", "2022-06-30"):
        for rank, product in enumerate(products[:10], start=1):
            rows.append(
                {
                    "strategy": "official",
                    "score_type": "formal_probability",
                    "eval_date": eval_date,
                    "product_vt_symbol": product,
                    "score": float(20 - rank),
                    "score_rank": rank,
                    "top_n": 11,
                }
            )
        rows.append(
            {
                "strategy": "official",
                "score_type": "formal_probability",
                "eval_date": eval_date,
                "product_vt_symbol": "fu.SHFE",
                "score": 9.0,
                "score_rank": 11,
                "top_n": 11,
            }
        )
    return pd.DataFrame(rows)


def sample_predictions() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    products = [f"p{i:02d}.X" for i in range(18)]
    for eval_date, order in (
        ("2022-04-29", products),
        ("2022-05-31", list(reversed(products))),
    ):
        for score, product in enumerate(reversed(order), start=1):
            rows.append(
                {
                    "eval_date": eval_date,
                    "product_vt_symbol": product,
                    "score_two_month_confirmed": float(score),
                }
            )
    return pd.DataFrame(rows)


def test_candidate_changes_only_oos_months_and_keeps_fixed_fu() -> None:
    module = load_module()
    formal = sample_formal()

    candidate, audit = module.build_candidate_eligibility(
        formal,
        sample_predictions(),
        expected_oos_months=2,
    )

    for eval_date in ("2019-12-31", "2022-03-31", "2022-06-30"):
        expected = formal[formal.eval_date.eq(eval_date)].reset_index(drop=True)
        actual = candidate[candidate.eval_date.eq(eval_date)].reset_index(drop=True)
        pd.testing.assert_frame_equal(actual, expected)
    for eval_date in ("2022-04-29", "2022-05-31"):
        month = candidate[candidate.eval_date.eq(eval_date)].sort_values("score_rank")
        assert len(month) == 11
        assert month.product_vt_symbol.nunique() == 11
        assert month.iloc[-1].product_vt_symbol == "fu.SHFE"
        assert month.iloc[-1].score_rank == 11
        assert month.top_n.eq(11).all()
        assert month.score_type.eq(module.CANDIDATE_SCORE_TYPE).all()
    assert audit.source.tolist() == ["formal_preserved", "stage003_oos", "stage003_oos", "formal_preserved"]


def test_candidate_members_follow_confirmed_score_order() -> None:
    module = load_module()

    candidate, _ = module.build_candidate_eligibility(
        sample_formal(),
        sample_predictions(),
        expected_oos_months=2,
    )

    may = candidate[candidate.eval_date.eq("2022-05-31")].sort_values("score_rank")
    assert may.head(10).product_vt_symbol.tolist() == [f"p{i:02d}.X" for i in range(17, 7, -1)]


def test_candidate_rejects_prediction_date_missing_from_formal() -> None:
    module = load_module()
    predictions = sample_predictions().copy()
    predictions.loc[predictions.eval_date.eq("2022-05-31"), "eval_date"] = "2022-07-29"

    with pytest.raises(RuntimeError, match="prediction_dates_not_in_formal"):
        module.build_candidate_eligibility(
            sample_formal(),
            predictions,
            expected_oos_months=2,
        )


def test_baseline_reference_parity_checks_all_frozen_metrics() -> None:
    module = load_module()
    reference = {
        "end_equity": 100.0,
        "total_return_pct": 20.0,
        "max_dd_pct": -10.0,
        "sharpe": 1.2,
        "total_slippage": 30.0,
        "total_trade_count": 40.0,
        "win_rate_pct": 55.0,
        "broker10_peak_margin_to_equity_pct": 90.0,
    }
    actual = {
        **reference,
        "nonzero_daily_win_rate_pct": reference["win_rate_pct"],
        "max_broker10_margin_to_equity_pct": reference["broker10_peak_margin_to_equity_pct"],
    }

    result = module.baseline_reference_parity(actual, reference)

    assert result["passed"] is True
    assert all(result["gates"].values())


def test_fullperiod_gate_requires_both_higher_return_and_better_drawdown() -> None:
    module = load_module()
    baseline = {
        "total_return_pct": 100.0,
        "max_dd_pct": -40.0,
        "sharpe": 1.5,
        "total_slippage": 1000.0,
        "total_trade_count": 100.0,
        "account_survival_pass": 1,
        "max_broker10_margin_to_equity_pct": 95.0,
        "days_over_100pct": 0,
    }
    candidate = {
        **baseline,
        "total_return_pct": 110.0,
        "max_dd_pct": -35.0,
        "sharpe": 1.6,
        "total_slippage": 1040.0,
    }

    passed = module.evaluate_fullperiod_gates(baseline, candidate, baseline_reproduction_pass=True)
    failed = module.evaluate_fullperiod_gates(
        baseline,
        {**candidate, "max_dd_pct": -41.0},
        baseline_reproduction_pass=True,
    )

    assert passed["passed"] is True
    assert failed["passed"] is False
    assert failed["gates"]["max_drawdown_strictly_better"] is False
