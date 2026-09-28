from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


TOOL_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

from full_market_one_slot_features import (  # noqa: E402
    CONTEXT_FEATURES,
    MODEL_FEATURES,
    PAIRWISE_FEATURES,
    RAW_CURVE_FEATURES,
    RAW_PATH_FEATURES,
    FeatureConfig,
    FeatureError,
    audit_trailing_coverage,
    build_fold_plan,
    build_label_plan,
    build_pairwise_features,
    build_product_return_history,
    compute_curve_features,
    compute_trailing_features,
)


def test_same_contract_return_splicing_does_not_treat_roll_gap_as_return() -> None:
    mapping = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "continuous_symbol_vt": ["p.EX", "p.EX", "p.EX"],
            "main_contract_vt": ["p2401.EX", "p2401.EX", "p2402.EX"],
        }
    )
    bars = pd.DataFrame(
        {
            "datetime": [
                "2023-12-29",
                "2024-01-01",
                "2024-01-02",
                "2024-01-02",
                "2024-01-03",
            ],
            "symbol": ["p2401", "p2401", "p2401", "p2402", "p2402"],
            "exchange": ["EX"] * 5,
            "interval": ["d"] * 5,
            "close_price": [90.0, 100.0, 110.0, 200.0, 202.0],
            "volume": [10.0, 11.0, 12.0, 20.0, 21.0],
            "open_interest": [30.0, 31.0, 32.0, 40.0, 41.0],
        }
    )

    result = build_product_return_history(mapping, bars)

    roll_day = result[result["date"].eq(pd.Timestamp("2024-01-03"))].iloc[0]
    assert roll_day["main_contract_vt"] == "p2402.EX"
    assert roll_day["log_return"] == pytest.approx(np.log(202.0 / 200.0))
    assert roll_day["log_return"] != pytest.approx(np.log(202.0 / 110.0))


def test_unresolved_mapping_rows_are_excluded_before_contract_merge() -> None:
    mapping = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-02", "2024-01-02"],
            "continuous_symbol_vt": ["missing1.EX", "missing2.EX", "p.EX"],
            "main_contract_vt": [None, None, "p2401.EX"],
        }
    )
    bars = pd.DataFrame(
        {
            "datetime": ["2024-01-01", "2024-01-02"],
            "symbol": ["p2401", "p2401"],
            "exchange": ["EX", "EX"],
            "interval": ["d", "d"],
            "close_price": [100.0, 101.0],
            "volume": [10.0, 11.0],
            "open_interest": [20.0, 21.0],
        }
    )

    result = build_product_return_history(mapping, bars)

    assert result["product_vt_symbol"].tolist() == ["p.EX"]
    assert result.iloc[0]["log_return"] == pytest.approx(np.log(101.0 / 100.0))


def _constant_return_history(eval_date: str) -> pd.DataFrame:
    dates = pd.bdate_range(end=eval_date, periods=252)
    volume = np.full(252, 100.0)
    volume[-20:] = 200.0
    open_interest = np.full(252, 200.0)
    open_interest[-20:] = 300.0
    return pd.DataFrame(
        {
            "date": dates,
            "product_vt_symbol": "p.EX",
            "main_contract_vt": "p2401.EX",
            "close_price": 100.0,
            "volume": volume,
            "open_interest": open_interest,
            "log_return": 0.01,
        }
    )


def test_trailing_features_are_fixed_window_and_ignore_future_rows() -> None:
    eval_date = "2024-12-31"
    history = _constant_return_history(eval_date)
    history_with_future = pd.concat(
        [
            history,
            pd.DataFrame(
                {
                    "date": [pd.Timestamp("2025-01-02")],
                    "product_vt_symbol": ["p.EX"],
                    "main_contract_vt": ["p2401.EX"],
                    "close_price": [9999.0],
                    "volume": [9999.0],
                    "open_interest": [9999.0],
                    "log_return": [100.0],
                }
            ),
        ],
        ignore_index=True,
    )
    action_rows = pd.DataFrame(
        {"eval_date": [eval_date], "product_vt_symbol": ["p.EX"]}
    )

    result = compute_trailing_features(
        history_with_future, action_rows, config=FeatureConfig()
    )

    row = result.iloc[0]
    assert row["momentum_21"] == pytest.approx(0.21)
    assert row["momentum_63"] == pytest.approx(0.63)
    assert row["momentum_126"] == pytest.approx(1.26)
    assert row["momentum_252"] == pytest.approx(2.52)
    assert row["trend_efficiency_63"] == pytest.approx(1.0)
    assert row["trend_efficiency_126"] == pytest.approx(1.0)
    assert row["realized_vol_21"] == pytest.approx(0.0, abs=1e-12)
    assert row["realized_vol_63"] == pytest.approx(0.0, abs=1e-12)
    assert row["volume_ratio_20_60"] == pytest.approx(np.log(1.5))
    assert row["open_interest_ratio_20_60"] == pytest.approx(
        np.log(300.0 / (700.0 / 3.0))
    )
    assert row["maximum_source_date_used"] == pd.Timestamp(eval_date)
    assert row["future_bar_rows_used"] == 0
    assert np.isfinite(result[RAW_PATH_FEATURES].to_numpy(float)).all()


def test_trailing_features_fail_when_a_window_has_less_than_ninety_percent_returns() -> None:
    history = _constant_return_history("2024-12-31")
    history.loc[history.index[-21:-18], "log_return"] = np.nan
    action_rows = pd.DataFrame(
        {"eval_date": ["2024-12-31"], "product_vt_symbol": ["p.EX"]}
    )

    with pytest.raises(FeatureError, match="return_window_coverage_below_minimum"):
        compute_trailing_features(history, action_rows, config=FeatureConfig())

    failures = audit_trailing_coverage(
        history, action_rows, config=FeatureConfig()
    )
    assert failures[
        ["eval_date", "product_vt_symbol", "issue", "window", "valid_count", "required_count"]
    ].to_dict("records") == [
        {
            "eval_date": pd.Timestamp("2024-12-31"),
            "product_vt_symbol": "p.EX",
            "issue": "return_window_coverage_below_minimum",
            "window": 21,
            "valid_count": 18,
            "required_count": 19,
        }
    ]


def test_curve_features_use_ordered_maturities_and_hand_checked_hhi() -> None:
    eval_date = "2024-01-31"
    bars = pd.DataFrame(
        {
            "datetime": [eval_date, eval_date],
            "symbol": ["p2402", "p2404"],
            "exchange": ["EX", "EX"],
            "interval": ["d", "d"],
            "close_price": [100.0, 90.0],
            "volume": [75.0, 25.0],
            "open_interest": [50.0, 50.0],
        }
    )
    catalog = pd.DataFrame(
        {
            "vt_symbol": ["p2402.EX", "p2404.EX"],
            "product_vt_symbol": ["p.EX", "p.EX"],
            "delivery_year": [2024, 2024],
            "delivery_month": [2, 4],
        }
    )
    action_rows = pd.DataFrame(
        {"eval_date": [eval_date], "product_vt_symbol": ["p.EX"]}
    )

    result = compute_curve_features(bars, catalog, action_rows)

    row = result.iloc[0]
    expected_slope = np.log(100.0 / 90.0) * 6.0
    assert row["front_next_basis_annualized"] == pytest.approx(expected_slope)
    assert row["full_curve_backwardation_slope"] == pytest.approx(expected_slope)
    assert row["volume_hhi"] == pytest.approx(0.75**2 + 0.25**2)
    assert row["open_interest_hhi"] == pytest.approx(0.5)
    assert row["curve_contract_count"] == 2
    assert np.isfinite(result[RAW_CURVE_FEATURES].to_numpy(float)).all()


def _raw_feature_rows(eval_date: str) -> pd.DataFrame:
    products = ["low.EX", "anchor.EX", "high.EX"]
    rows = []
    for value, product in zip([1.0, 2.0, 3.0], products, strict=True):
        row = {
            "eval_date": pd.Timestamp(eval_date),
            "product_vt_symbol": product,
        }
        for feature in [*RAW_PATH_FEATURES, *RAW_CURVE_FEATURES]:
            row[feature] = value
        rows.append(row)
    return pd.DataFrame(rows)


def test_pairwise_features_anchor_at_zero_without_identity_model_features() -> None:
    eval_date = "2024-01-31"
    raw = _raw_feature_rows(eval_date)
    coverage = pd.DataFrame(
        {
            "eval_date": [eval_date] * 3,
            "product_vt_symbol": ["low.EX", "anchor.EX", "high.EX"],
            "eligible": [True, True, True],
            "is_formal_replacement_product": [False, True, False],
            "is_pool_outside_challenger": [True, False, True],
        }
    )
    monthly = pd.DataFrame({"eval_date": [eval_date], "action_ready": [True]})

    result = build_pairwise_features(raw, coverage, monthly)

    anchor = result[result["role"].eq("formal_rank10")].iloc[0]
    low = result[result["product_vt_symbol"].eq("low.EX")].iloc[0]
    high = result[result["product_vt_symbol"].eq("high.EX")].iloc[0]
    assert np.array_equal(anchor[PAIRWISE_FEATURES].to_numpy(float), np.zeros(14))
    assert low[PAIRWISE_FEATURES[0]] == pytest.approx(-1.0 / 3.0)
    assert high[PAIRWISE_FEATURES[0]] == pytest.approx(1.0 / 3.0)
    assert anchor["market_median_abs_momentum_126"] == pytest.approx(2.0)
    assert anchor["market_median_realized_vol_63"] == pytest.approx(2.0)
    assert len(MODEL_FEATURES) == 16
    assert set(CONTEXT_FEATURES).issubset(MODEL_FEATURES)
    assert not {"product_vt_symbol", "exchange", "product_id"}.intersection(
        MODEL_FEATURES
    )


def test_label_plan_contains_candidates_and_dates_but_no_label_values() -> None:
    eval_dates = pd.to_datetime(
        ["2024-01-31", "2024-02-29", "2024-03-29", "2024-04-30", "2024-05-31"]
    )
    rows = []
    for eval_date in eval_dates:
        rows.extend(
            [
                {
                    "eval_date": eval_date,
                    "product_vt_symbol": "anchor.EX",
                    "role": "formal_rank10",
                },
                {
                    "eval_date": eval_date,
                    "product_vt_symbol": "candidate.EX",
                    "role": "challenger",
                },
            ]
        )
    model_features = pd.DataFrame(rows)

    plan = build_label_plan(model_features, list(eval_dates))

    assert len(plan) == 4
    assert plan["role"].eq("challenger").all()
    assert plan["label_values_read"].eq(False).all()  # noqa: E712
    assert plan.iloc[0]["next_eval_date"] == pd.Timestamp("2024-02-29")
    forbidden = {
        "joint_win",
        "return_delta",
        "drawdown_improvement",
        "future_return",
        "future_drawdown",
    }
    assert not forbidden.intersection(plan.columns)


def test_fold_plan_uses_only_labels_ending_strictly_before_test_month() -> None:
    eval_dates = pd.to_datetime(
        ["2024-01-31", "2024-02-29", "2024-03-29", "2024-04-30", "2024-05-31"]
    )
    model_rows = []
    for eval_date in eval_dates:
        model_rows.extend(
            [
                {
                    "eval_date": eval_date,
                    "product_vt_symbol": "anchor.EX",
                    "role": "formal_rank10",
                },
                {
                    "eval_date": eval_date,
                    "product_vt_symbol": "candidate.EX",
                    "role": "challenger",
                },
            ]
        )
    model_features = pd.DataFrame(model_rows)
    label_plan = build_label_plan(model_features, list(eval_dates))

    folds = build_fold_plan(
        model_features,
        label_plan,
        minimum_train_months=2,
    )

    assert folds["test_eval_date"].tolist() == [
        pd.Timestamp("2024-04-30"),
        pd.Timestamp("2024-05-31"),
    ]
    april = folds.iloc[0]
    may = folds.iloc[1]
    assert april["train_month_count"] == 2
    assert april["maximum_train_label_end"] == pd.Timestamp("2024-03-29")
    assert april["maximum_train_label_end"] < april["test_eval_date"]
    assert bool(april["effect_evaluable"]) is True
    assert may["train_month_count"] == 3
    assert may["maximum_train_label_end"] == pd.Timestamp("2024-04-30")
    assert bool(may["inference_only"]) is True
