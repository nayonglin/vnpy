from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage002_base_margin_development_oos as stage002


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _passing_metrics() -> dict[str, object]:
    return {
        "input_identity_mismatch_count": 0,
        "authorization_valid": True,
        "stage001_manifest_valid": True,
        "fold_count": 50,
        "prediction_rows": 900,
        "minimum_products_per_test_month": 18,
        "maximum_products_per_test_month": 18,
        "feature_count": 108,
        "logistic_fit_count": 50,
        "scaler_fit_count": 50,
        "xgboost_fit_count": 100,
        "pit_violation_rows": 0,
        "pit_violation_folds": 0,
        "sealed_holdout_rows": 0,
        "fixed_fu_model_rows": 0,
        "nonfinite_output_cells": 0,
        "nonpositive_score_std_months_a": 0,
        "nonpositive_score_std_months_b": 0,
        "repeat_prediction_max_abs_error": 0.0,
        "xgboost_split_nodes": 400,
        "xgboost_folds_with_splits": 50,
        "median_abs_correction": 0.08,
        "max_abs_correction": 0.4,
        "weighted_logloss_a": 0.65,
        "weighted_logloss_b": 0.64,
        "mean_monthly_rank_ic_a": 0.02,
        "mean_monthly_rank_ic_b": 0.04,
        "changed_months": 10,
        "changed_years": 4,
        "sum_return_delta": 100.0,
        "sum_drawdown_improvement": 50.0,
        "leave_best_return_delta": 20.0,
        "leave_best_drawdown_improvement": 10.0,
        "joint_positive_ratio": 0.6,
        "minimum_year_return_delta": 1.0,
        "minimum_year_drawdown_improvement": 1.0,
        "true_engine_run_count": 0,
        "ctp_connection_count": 0,
        "order_api_call_count": 0,
        "production_write_count": 0,
    }


def test_fit_base_margin_residual_is_deterministic_and_splits() -> None:
    rng = np.random.default_rng(42)
    x_train = rng.normal(size=(240, 4))
    y_train = (x_train[:, 0] + 0.8 * x_train[:, 1] * x_train[:, 2] > 0).astype(int)
    x_test = rng.normal(size=(40, 4))
    train_margin = 0.4 * x_train[:, 0]
    test_margin = 0.4 * x_test[:, 0]

    result = stage002.fit_base_margin_residual(
        x_train=x_train,
        y_train=y_train,
        sample_weight=np.ones(len(y_train)),
        train_margin=train_margin,
        x_test=x_test,
        test_margin=test_margin,
    )

    assert result.repeat_max_abs_error == 0.0
    assert result.split_nodes > 0
    assert np.isfinite(result.probability).all()
    assert np.isfinite(result.raw_correction).all()
    assert np.max(np.abs(result.raw_correction)) > 0.0


def test_future_path_uses_exactly_next_n_trading_days() -> None:
    dates = pd.bdate_range("2024-01-02", periods=70)
    daily = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "product_vt_symbol": ["a.DCE"] * 70 + ["b.DCE"] * 70,
            "net_pnl": list(range(70)) + list(range(100, 170)),
        }
    )

    paths = stage002.build_future_path_table(
        daily,
        eval_dates=[dates[0]],
        horizon=60,
    )

    a_path = paths[paths["product_vt_symbol"].eq("a.DCE")]
    assert len(a_path) == 60
    assert a_path["date"].iloc[0] == dates[1]
    assert a_path["date"].iloc[-1] == dates[60]
    assert dates[0] not in set(a_path["date"])
    assert dates[61] not in set(a_path["date"])


def test_path_metrics_include_zero_as_initial_high_water() -> None:
    metrics = stage002.path_metrics(np.asarray([-10.0, 20.0, -5.0]))

    assert metrics["total_net_pnl"] == pytest.approx(5.0)
    assert metrics["max_drawdown"] == pytest.approx(-10.0)


def test_stable_top_n_breaks_score_ties_by_product() -> None:
    frame = pd.DataFrame(
        {
            "product_vt_symbol": ["c.TEST", "a.TEST", "b.TEST"],
            "score": [0.5, 0.5, 0.4],
        }
    )

    selected = stage002.stable_top_n(frame, score_column="score", top_n=2)

    assert selected == ["a.TEST", "c.TEST"]


def test_monthly_effects_use_selected_product_aggregate_path() -> None:
    eval_date = pd.Timestamp("2024-01-31")
    predictions = pd.DataFrame(
        {
            "eval_date": [eval_date] * 3,
            "product_vt_symbol": ["a.TEST", "b.TEST", "c.TEST"],
            "score_a": [0.9, 0.8, 0.1],
            "score_b": [0.9, 0.1, 0.8],
        }
    )
    paths = pd.DataFrame(
        {
            "eval_date": [eval_date] * 6,
            "product_vt_symbol": ["a.TEST", "a.TEST", "b.TEST", "b.TEST", "c.TEST", "c.TEST"],
            "path_step": [1, 2, 1, 2, 1, 2],
            "net_pnl": [1.0, 1.0, 5.0, -11.0, 2.0, 1.0],
        }
    )

    effects, selections = stage002.build_monthly_effects(
        predictions,
        paths,
        top_n=2,
    )

    row = effects.iloc[0]
    assert row["changed"] is True or bool(row["changed"])
    assert row["return_delta"] == pytest.approx(9.0)
    assert row["drawdown_improvement"] == pytest.approx(10.0)
    assert selections.query("arm == 'A'")["product_vt_symbol"].tolist() == ["a.TEST", "b.TEST"]
    assert selections.query("arm == 'B'")["product_vt_symbol"].tolist() == ["a.TEST", "c.TEST"]


def test_effect_summary_computes_leave_best_and_yearly_minima() -> None:
    effects = pd.DataFrame(
        {
            "eval_date": pd.to_datetime(["2023-01-31", "2023-02-28", "2024-01-31"]),
            "changed": [True, True, True],
            "return_delta": [5.0, 4.0, 3.0],
            "drawdown_improvement": [2.0, 3.0, 4.0],
        }
    )

    summary, yearly = stage002.summarize_effects(effects)

    assert summary["sum_return_delta"] == pytest.approx(12.0)
    assert summary["leave_best_return_delta"] == pytest.approx(7.0)
    assert summary["sum_drawdown_improvement"] == pytest.approx(9.0)
    assert summary["leave_best_drawdown_improvement"] == pytest.approx(5.0)
    assert summary["joint_positive_ratio"] == pytest.approx(1.0)
    assert summary["changed_years"] == 2
    assert yearly["return_delta"].min() == pytest.approx(3.0)


def test_gate_assessment_accepts_only_joint_robust_improvement() -> None:
    result = stage002.assess_gates(_passing_metrics())

    assert result["all_gates_passed"] is True
    assert result["decision"] == stage002.PASS_DECISION
    assert result["failures"] == []


@pytest.mark.parametrize(
    ("field", "value", "failure"),
    [
        ("repeat_prediction_max_abs_error", 1e-12, "deterministic_repeat"),
        ("weighted_logloss_b", 0.66, "model_quality_increment"),
        ("sum_drawdown_improvement", -1.0, "joint_return_drawdown_effect"),
        ("leave_best_return_delta", 0.0, "leave_best_robustness"),
        ("minimum_year_return_delta", -1.0, "yearly_robustness"),
        ("changed_months", 7, "minimum_action_coverage"),
    ],
)
def test_gate_assessment_fails_closed(field: str, value: object, failure: str) -> None:
    metrics = _passing_metrics()
    metrics[field] = value

    result = stage002.assess_gates(metrics)

    assert result["all_gates_passed"] is False
    assert failure in result["failures"]
    assert result["decision"] == stage002.FAIL_DECISION


def test_authorization_receipt_binds_files_and_detects_mutation(tmp_path: Path) -> None:
    bound = tmp_path / "bound.txt"
    bound.write_text("frozen\n", encoding="utf-8")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "authorized": True,
                "authorization_scope": "single_stage002_development_oos",
                "allowed_run_count": 1,
                "bindings": {
                    "bound": {"path": str(bound), "sha256": _sha256(bound)},
                },
            }
        ),
        encoding="utf-8",
    )

    assert stage002.validate_authorization_receipt(receipt)["valid"] is True

    bound.write_text("changed\n", encoding="utf-8")
    result = stage002.validate_authorization_receipt(receipt)
    assert result["valid"] is False
    assert "binding_sha256_mismatch:bound" in result["errors"]
