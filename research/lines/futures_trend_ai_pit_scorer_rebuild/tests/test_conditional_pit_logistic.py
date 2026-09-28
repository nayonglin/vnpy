from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/conditional_pit_logistic.py"
SPEC = importlib.util.spec_from_file_location("conditional_pit_logistic", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
model = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = model
SPEC.loader.exec_module(model)


def test_discover_feature_columns_matches_suffix_contract() -> None:
    frame = pd.DataFrame(
        columns=[
            "net_pnl_sum_20d",
            "opened_count_sum_60d",
            "future_bad_60d",
            "target_bad_120d",
            "sample_weight_bad_20d",
            "pit_future_rank_centered_60d",
            "pit_future_rank_pct_60d",
            "pit_target_future_top_half_60d",
            "plain_value",
        ]
    )

    assert model.discover_feature_columns(frame) == [
        "net_pnl_sum_20d",
        "opened_count_sum_60d",
    ]


def test_build_conditional_samples_drops_partial_and_filters_before_target() -> None:
    samples = pd.DataFrame(
        {
            "eval_date": pd.to_datetime(["2020-01-31"] * 4 + ["2020-02-28"] * 4),
            "product_vt_symbol": ["a.DCE", "b.DCE", "c.DCE", "d.DCE"] * 2,
            "future_net_pnl_60d": [40.0, 30.0, 20.0, 10.0, 4.0, 3.0, 2.0, 1.0],
            "target_future_top_half_60d": [1, 1, 0, 0] * 2,
            "feature_sum_20d": np.arange(8, dtype="float64"),
        }
    )
    boundaries = samples[["eval_date", "product_vt_symbol"]].copy()
    boundaries["future_label_end_date"] = pd.Timestamp("2020-05-01")
    boundaries["future_observation_count"] = [60] * 4 + [59] * 4
    boundaries["full_horizon_label"] = [True] * 4 + [False] * 4
    effective = {
        "a.DCE": pd.Timestamp("2020-02-01"),
        "b.DCE": pd.Timestamp("2019-01-01"),
        "c.DCE": pd.Timestamp("2019-01-01"),
        "d.DCE": pd.Timestamp("2019-01-01"),
    }

    clean, audit = model.build_conditional_samples(samples, boundaries, effective)

    assert clean["product_vt_symbol"].tolist() == ["b.DCE", "c.DCE", "d.DCE"]
    assert clean[model.TARGET_COLUMN].tolist() == [1, 1, 0]
    assert clean[model.WEIGHT_COLUMN].tolist() == pytest.approx([0.5, 0.2, 0.2])
    assert audit["partial_horizon_rows_removed"] == 4
    assert audit["unlisted_rows_removed"] == 1


def test_build_fold_contract_uses_strict_label_end_and_drops_small_test() -> None:
    rows = []
    for date, label_end in [
        ("2020-01-31", "2020-02-29"),
        ("2020-02-28", "2020-04-01"),
        ("2020-03-31", "2020-05-01"),
        ("2020-04-30", "2020-06-01"),
    ]:
        for product, target in [("a.DCE", 0), ("b.DCE", 1)]:
            rows.append(
                {
                    "eval_date": date,
                    "product_vt_symbol": product,
                    "future_label_end_date": label_end,
                    model.TARGET_COLUMN: target,
                }
            )
    panel = pd.DataFrame(rows)
    windows = pd.DataFrame(
        {
            "window_id": ["wf_01", "wf_02"],
            "train_start": ["2020-01-01", "2020-01-01"],
            "train_end": ["2020-03-01", "2020-04-01"],
            "test_start": ["2020-03-01", "2020-04-01"],
            "test_end": ["2020-05-01", "2020-05-01"],
        }
    )

    folds, audit = model.build_fold_contracts(
        panel, windows, min_train_rows=2, min_test_rows=3
    )

    assert [fold.window_id for fold in folds] == ["wf_01"]
    assert folds[0].train_dates.tolist() == [pd.Timestamp("2020-01-31")]
    assert folds[0].train_label_end_max < folds[0].test_start
    rejected = audit[audit["accepted"].eq(False)].iloc[0]
    assert rejected["reject_reason"] == "test_rows_below_minimum"


def test_logistic_fit_is_deterministic() -> None:
    frame = pd.DataFrame(
        {
            "x_sum_20d": [-2.0, -1.0, 1.0, 2.0, -1.5, 1.5],
            "y_sum_60d": [0.0, 1.0, 1.0, 0.0, 0.5, 0.5],
            model.TARGET_COLUMN: [0, 0, 1, 1, 0, 1],
            model.WEIGHT_COLUMN: [0.2] * 6,
        }
    )
    test = frame.iloc[[0, 2, 5]].copy()

    first = model.fit_logistic(frame, ["x_sum_20d", "y_sum_60d"])
    second = model.fit_logistic(frame, ["x_sum_20d", "y_sum_60d"])
    p1 = model.predict_probability(first, test, ["x_sum_20d", "y_sum_60d"])
    p2 = model.predict_probability(second, test, ["x_sum_20d", "y_sum_60d"])

    assert np.array_equal(p1, p2)
    assert model.model_state_max_abs_diff(first, second) == pytest.approx(0.0)


def test_stage002_decision_requires_all_technical_gates() -> None:
    gates = {
        "input_identity_stable": True,
        "feature_count_exact": True,
        "valid_folds_ge_7": True,
        "oos_months_ge_40": True,
        "pit_violation_rows_zero": True,
        "unlisted_rows_zero": True,
        "partial_horizon_rows_zero": True,
        "deterministic_predictions": True,
        "deterministic_model_state": True,
        "probabilities_valid": True,
        "monthly_candidate_count_ge_10": True,
        "sealed_holdout_rows_zero": True,
    }

    assert model.stage002_decision(gates) == model.PASS_DECISION
    gates["pit_violation_rows_zero"] = False
    assert model.stage002_decision(gates) == model.FAIL_DECISION
