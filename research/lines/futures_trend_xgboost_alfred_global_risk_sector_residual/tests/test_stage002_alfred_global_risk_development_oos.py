from __future__ import annotations

import hashlib
import json
import multiprocessing
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage002_alfred_global_risk_development_oos as stage002


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _passing_metrics() -> dict[str, object]:
    return {
        "current_release_id": stage002.EXPECTED_RELEASE_ID,
        "current_strategy_id": stage002.EXPECTED_STRATEGY_ID,
        "input_identity_mismatch_count": 0,
        "authorization_valid": True,
        "stage001_manifest_valid": True,
        "formal_feature_contract_match": True,
        "fold_count": 50,
        "prediction_rows": 900,
        "minimum_products_per_test_month": 18,
        "maximum_products_per_test_month": 18,
        "formal_feature_count": 108,
        "state_feature_count": 15,
        "logistic_fit_count": 50,
        "scaler_fit_count": 50,
        "standalone_xgboost_fit_count": 100,
        "residual_xgboost_fit_count": 100,
        "xgboost_fit_count": 200,
        "state_panel_row_count": 1386,
        "state_panel_join_missing_rows": 0,
        "state_panel_duplicate_key_rows": 0,
        "state_feature_modified_cell_count": 0,
        "label_generated_row_count": 1386,
        "label_generated_missing_key_count": 0,
        "label_generated_extra_key_count": 0,
        "pit_violation_rows": 0,
        "pit_violation_folds": 0,
        "sealed_holdout_rows": 0,
        "fixed_fu_model_rows": 0,
        "nonfinite_output_cells": 0,
        "nonpositive_score_std_months_a": 0,
        "nonpositive_score_std_months_b": 0,
        "nonpositive_score_std_months_c": 0,
        "repeat_prediction_max_abs_error_b": 0.0,
        "repeat_prediction_max_abs_error_c": 0.0,
        "xgboost_split_nodes_b": 200,
        "xgboost_split_nodes_c": 180,
        "xgboost_folds_with_splits_b": 50,
        "xgboost_folds_with_splits_c": 50,
        "median_abs_correction_c": 0.08,
        "max_abs_correction_c": 0.4,
        "weighted_logloss_a": 0.65,
        "weighted_logloss_b": 0.67,
        "weighted_logloss_c": 0.64,
        "mean_monthly_rank_ic_a": 0.02,
        "mean_monthly_rank_ic_b": 0.01,
        "mean_monthly_rank_ic_c": 0.04,
        "changed_months": 10,
        "changed_years": 4,
        "sum_return_delta": 100.0,
        "sum_drawdown_improvement": 50.0,
        "leave_best_return_delta": 20.0,
        "leave_best_drawdown_improvement": 10.0,
        "joint_positive_ratio": 0.6,
        "minimum_year_return_delta": 1.0,
        "minimum_year_drawdown_improvement": 1.0,
        "label_value_rows_read": 1386,
        "development_oos_label_rows_used": 900,
        "oos_path_missing_rows": 0,
        "oos_path_label_sum_mismatch_rows": 0,
        "oos_path_label_sum_max_abs_error": 0.0,
        "oos_path_label_end_mismatch_rows": 0,
        "true_engine_run_count": 0,
        "ctp_connection_count": 0,
        "order_api_call_count": 0,
        "production_write_count": 0,
    }


def test_fit_standalone_xgboost_is_deterministic_and_splits() -> None:
    rng = np.random.default_rng(42)
    x_train = rng.normal(size=(320, 4))
    y_train = (x_train[:, 0] + 0.9 * x_train[:, 1] > 0).astype(int)
    x_test = rng.normal(size=(40, 4))

    result = stage002.fit_standalone_xgboost(
        x_train=x_train,
        y_train=y_train,
        sample_weight=np.ones(len(y_train)),
        x_test=x_test,
    )

    assert result.repeat_max_abs_error == 0.0
    assert result.split_nodes > 0
    assert np.isfinite(result.probability).all()


def test_fit_base_margin_residual_is_deterministic_and_bounded() -> None:
    rng = np.random.default_rng(7)
    x_train = rng.normal(size=(320, 4))
    y_train = (0.6 * x_train[:, 0] + x_train[:, 2] > 0).astype(int)
    x_test = rng.normal(size=(40, 4))
    train_margin = 0.3 * x_train[:, 0]
    test_margin = 0.3 * x_test[:, 0]

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


def test_join_state_features_is_one_to_one_and_preserves_values() -> None:
    formal = pd.DataFrame(
        {
            "eval_date": pd.to_datetime(["2024-01-31", "2024-01-31"]),
            "product_vt_symbol": ["a.TEST", "b.TEST"],
            "target": [0, 1],
        }
    )
    state = pd.DataFrame(
        {
            "eval_date": pd.to_datetime(["2024-01-31", "2024-01-31"]),
            "product_vt_symbol": ["b.TEST", "a.TEST"],
            "state_1": [2.0, 1.0],
            "state_2": [4.0, 3.0],
        }
    )

    joined, audit = stage002.join_state_features(
        formal,
        state,
        ["state_1", "state_2"],
    )

    assert joined["product_vt_symbol"].tolist() == ["a.TEST", "b.TEST"]
    assert joined[["state_1", "state_2"]].to_numpy().tolist() == [
        [1.0, 3.0],
        [2.0, 4.0],
    ]
    assert audit == {
        "state_panel_join_missing_rows": 0,
        "state_panel_duplicate_key_rows": 0,
        "state_feature_modified_cell_count": 0,
    }


def test_join_state_features_rejects_missing_or_duplicate_keys() -> None:
    formal = pd.DataFrame(
        {
            "eval_date": [pd.Timestamp("2024-01-31")],
            "product_vt_symbol": ["a.TEST"],
        }
    )
    missing = pd.DataFrame(
        columns=["eval_date", "product_vt_symbol", "state_1"]
    )
    with pytest.raises(stage002.Stage002Error, match="state_panel_join_missing"):
        stage002.join_state_features(formal, missing, ["state_1"])

    duplicate = pd.DataFrame(
        {
            "eval_date": [pd.Timestamp("2024-01-31")] * 2,
            "product_vt_symbol": ["a.TEST"] * 2,
            "state_1": [1.0, 1.0],
        }
    )
    with pytest.raises(stage002.Stage002Error, match="state_panel_duplicate_key"):
        stage002.join_state_features(formal, duplicate, ["state_1"])


def test_select_frozen_feature_rows_excludes_unregistered_keys() -> None:
    featured = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2024-01-31", "2024-01-31", "2024-02-29"]
            ),
            "product_vt_symbol": ["a.TEST", "b.TEST", "a.TEST"],
            "feature": [1.0, 2.0, 999.0],
        }
    )
    frozen_keys = pd.DataFrame(
        {
            "eval_date": pd.to_datetime(["2024-01-31", "2024-01-31"]),
            "product_vt_symbol": ["a.TEST", "b.TEST"],
        }
    )

    selected = stage002.select_frozen_feature_rows(featured, frozen_keys)

    assert selected[["date", "product_vt_symbol"]].to_dict("records") == [
        {"date": pd.Timestamp("2024-01-31"), "product_vt_symbol": "a.TEST"},
        {"date": pd.Timestamp("2024-01-31"), "product_vt_symbol": "b.TEST"},
    ]
    assert selected["feature"].tolist() == [1.0, 2.0]


def test_select_frozen_feature_rows_rejects_missing_key() -> None:
    featured = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-31")],
            "product_vt_symbol": ["a.TEST"],
            "feature": [1.0],
        }
    )
    frozen_keys = pd.DataFrame(
        {
            "eval_date": [pd.Timestamp("2024-01-31")],
            "product_vt_symbol": ["missing.TEST"],
        }
    )

    with pytest.raises(stage002.Stage002Error, match="frozen_feature_key_missing"):
        stage002.select_frozen_feature_rows(featured, frozen_keys)


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


def test_future_path_rejects_product_gap_in_global_calendar() -> None:
    dates = pd.bdate_range("2024-01-02", periods=70)
    a_dates = dates.delete(5)
    daily = pd.DataFrame(
        {
            "date": list(a_dates) + list(dates),
            "product_vt_symbol": ["a.DCE"] * len(a_dates) + ["b.DCE"] * len(dates),
            "net_pnl": [1.0] * (len(a_dates) + len(dates)),
        }
    )

    with pytest.raises(ValueError, match="future_path_global_date_missing"):
        stage002.build_future_path_table(
            daily,
            eval_dates=[dates[0]],
            horizon=60,
        )


def test_frozen_label_table_only_builds_registered_product_months() -> None:
    dates = pd.bdate_range("2024-01-02", periods=5)
    daily = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "product_vt_symbol": ["a.TEST"] * 5 + ["b.TEST"] * 5,
            "net_pnl": [0.0, 1.0, 2.0, 99.0, 99.0]
            + [0.0, 10.0, 20.0, 99.0, 99.0],
        }
    )
    frozen_keys = pd.DataFrame(
        {
            "eval_date": [dates[0]],
            "product_vt_symbol": ["a.TEST"],
        }
    )

    labels = stage002.build_frozen_label_table(
        daily,
        frozen_keys,
        horizon=2,
    )

    assert labels.to_dict("records") == [
        {
            "eval_date": dates[0],
            "product_vt_symbol": "a.TEST",
            "future_net_pnl_60d": 3.0,
            "label_end": dates[2],
        }
    ]


def test_path_metrics_include_zero_as_initial_high_water() -> None:
    metrics = stage002.path_metrics(np.asarray([-10.0, 20.0, -5.0]))

    assert metrics["total_net_pnl"] == pytest.approx(5.0)
    assert metrics["max_drawdown"] == pytest.approx(-10.0)


def test_stable_top_n_breaks_score_ties_by_product() -> None:
    frame = pd.DataFrame(
        {
            "product_vt_symbol": ["c.TEST", "a.TEST", "b.TEST"],
            "score_c": [0.5, 0.5, 0.4],
        }
    )

    selected = stage002.stable_top_n(frame, score_column="score_c", top_n=2)

    assert selected == ["a.TEST", "c.TEST"]


def test_monthly_effects_compare_candidate_c_to_formal_a() -> None:
    eval_date = pd.Timestamp("2024-01-31")
    predictions = pd.DataFrame(
        {
            "eval_date": [eval_date] * 3,
            "product_vt_symbol": ["a.TEST", "b.TEST", "c.TEST"],
            "score_a": [0.9, 0.8, 0.1],
            "score_c": [0.9, 0.1, 0.8],
        }
    )
    paths = pd.DataFrame(
        {
            "eval_date": [eval_date] * 6,
            "product_vt_symbol": [
                "a.TEST",
                "a.TEST",
                "b.TEST",
                "b.TEST",
                "c.TEST",
                "c.TEST",
            ],
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
    assert bool(row["changed"])
    assert row["return_delta"] == pytest.approx(9.0)
    assert row["drawdown_improvement"] == pytest.approx(10.0)
    assert selections.query("arm == 'A'")["product_vt_symbol"].tolist() == [
        "a.TEST",
        "b.TEST",
    ]
    assert selections.query("arm == 'C'")["product_vt_symbol"].tolist() == [
        "a.TEST",
        "c.TEST",
    ]


def test_effect_summary_computes_leave_best_and_yearly_minima() -> None:
    effects = pd.DataFrame(
        {
            "eval_date": pd.to_datetime(
                ["2023-01-31", "2023-02-28", "2024-01-31"]
            ),
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


def test_pit_audit_counts_missing_label_end_as_violation() -> None:
    fold_plan = pd.DataFrame(
        {
            "test_eval_date": [pd.Timestamp("2024-04-30")],
            "train_eval_dates": ["2024-01-31,2024-02-29"],
        }
    )
    label_calendar = pd.DataFrame(
        {
            "eval_date": pd.to_datetime(["2024-01-31", "2024-02-29"]),
            "label_end": [pd.Timestamp("2024-04-01"), pd.NaT],
        }
    )

    assert stage002._pit_audit(fold_plan, label_calendar) == (1, 1)


def test_oos_path_audit_binds_label_sum_and_fold_label_end() -> None:
    predictions = pd.DataFrame(
        {
            "eval_date": [pd.Timestamp("2024-01-31")],
            "product_vt_symbol": ["a.TEST"],
            "future_net_pnl_60d": [3.0],
        }
    )
    future_paths = pd.DataFrame(
        {
            "eval_date": [pd.Timestamp("2024-01-31")] * 2,
            "product_vt_symbol": ["a.TEST"] * 2,
            "date": pd.to_datetime(["2024-02-01", "2024-02-02"]),
            "path_step": [1, 2],
            "net_pnl": [1.0, 2.0],
        }
    )
    fold_plan = pd.DataFrame(
        {
            "test_eval_date": [pd.Timestamp("2024-01-31")],
            "test_label_end": [pd.Timestamp("2024-02-02")],
        }
    )

    audit = stage002.audit_oos_path_consistency(
        predictions,
        future_paths,
        fold_plan,
        tolerance=1e-12,
    )

    assert audit == {
        "oos_path_missing_rows": 0,
        "oos_path_label_sum_mismatch_rows": 0,
        "oos_path_label_sum_max_abs_error": 0.0,
        "oos_path_label_end_mismatch_rows": 0,
    }


def test_oos_path_audit_detects_sum_and_label_end_mismatch() -> None:
    predictions = pd.DataFrame(
        {
            "eval_date": [pd.Timestamp("2024-01-31")],
            "product_vt_symbol": ["a.TEST"],
            "future_net_pnl_60d": [4.0],
        }
    )
    future_paths = pd.DataFrame(
        {
            "eval_date": [pd.Timestamp("2024-01-31")],
            "product_vt_symbol": ["a.TEST"],
            "date": [pd.Timestamp("2024-02-02")],
            "path_step": [1],
            "net_pnl": [3.0],
        }
    )
    fold_plan = pd.DataFrame(
        {
            "test_eval_date": [pd.Timestamp("2024-01-31")],
            "test_label_end": [pd.Timestamp("2024-02-01")],
        }
    )

    audit = stage002.audit_oos_path_consistency(
        predictions,
        future_paths,
        fold_plan,
        tolerance=1e-12,
    )

    assert audit["oos_path_label_sum_mismatch_rows"] == 1
    assert audit["oos_path_label_sum_max_abs_error"] == pytest.approx(1.0)
    assert audit["oos_path_label_end_mismatch_rows"] == 1


def test_gate_assessment_accepts_only_joint_robust_c_improvement() -> None:
    result = stage002.assess_gates(_passing_metrics())

    assert result["all_gates_passed"] is True
    assert result["decision"] == stage002.PASS_DECISION
    assert result["failures"] == []


@pytest.mark.parametrize(
    ("field", "value", "failure"),
    [
        ("repeat_prediction_max_abs_error_b", 1e-12, "deterministic_repeat"),
        ("current_release_id", "wrong", "identity_authorization"),
        ("formal_feature_contract_match", False, "identity_authorization"),
        ("label_generated_extra_key_count", 1, "label_scope_contract"),
        ("oos_path_label_sum_mismatch_rows", 1, "path_label_consistency"),
        ("xgboost_folds_with_splits_c", 49, "xgboost_non_degenerate"),
        ("weighted_logloss_c", 0.66, "candidate_quality_increment"),
        ("sum_drawdown_improvement", -1.0, "joint_return_drawdown_effect"),
        ("leave_best_return_delta", 0.0, "leave_best_robustness"),
        ("minimum_year_return_delta", -1.0, "yearly_robustness"),
        ("changed_months", 7, "minimum_action_coverage"),
    ],
)
def test_gate_assessment_fails_closed(
    field: str,
    value: object,
    failure: str,
) -> None:
    metrics = _passing_metrics()
    metrics[field] = value

    result = stage002.assess_gates(metrics)

    assert result["all_gates_passed"] is False
    assert failure in result["failures"]
    assert result["decision"] == stage002.FAIL_DECISION


def test_authorization_receipt_binds_files_and_detects_mutation(
    tmp_path: Path,
) -> None:
    bound = tmp_path / "bound.txt"
    bound.write_text("frozen\n", encoding="utf-8")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "authorized": True,
                "authorization_scope": "single_stage002_alfred_development_oos",
                "allowed_run_count": 1,
                "authorization_nonce": "33e91c86-9046-44a5-8f21-235f3e4af5a4",
                "bindings": {
                    "bound": {"path": str(bound), "sha256": _sha256(bound)},
                },
            }
        ),
        encoding="utf-8",
    )

    validation = stage002.validate_authorization_receipt(receipt)
    assert validation["valid"] is True
    assert validation["receipt_sha256"] == _sha256(receipt)

    bound.write_text("changed\n", encoding="utf-8")
    result = stage002.validate_authorization_receipt(receipt)
    assert result["valid"] is False
    assert "binding_sha256_mismatch:bound" in result["errors"]


def test_authorization_receipt_requires_uuid_nonce(tmp_path: Path) -> None:
    bound = tmp_path / "bound.txt"
    bound.write_text("frozen\n", encoding="utf-8")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "authorized": True,
                "authorization_scope": "single_stage002_alfred_development_oos",
                "allowed_run_count": 1,
                "bindings": {
                    "bound": {"path": str(bound), "sha256": _sha256(bound)},
                },
            }
        ),
        encoding="utf-8",
    )

    result = stage002.validate_authorization_receipt(receipt)

    assert result["valid"] is False
    assert "authorization_nonce_invalid" in result["errors"]


def test_canonical_bindings_reject_wrong_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = tmp_path / "expected.txt"
    wrong = tmp_path / "wrong.txt"
    expected.write_text("same\n", encoding="utf-8")
    wrong.write_text("same\n", encoding="utf-8")
    digest = _sha256(expected)
    monkeypatch.setattr(stage002, "CANONICAL_BINDING_PATHS", {"bound": expected})
    monkeypatch.setattr(stage002, "STATIC_BINDING_HASHES", {"bound": digest})
    receipt = {
        "bindings": {"bound": {"path": str(wrong), "sha256": digest}}
    }

    result = stage002.validate_canonical_bindings(receipt)

    assert result["valid"] is False
    assert "binding_path_mismatch:bound" in result["errors"]


def test_execution_marker_claim_is_atomic_and_non_overwriting(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "execution.json"
    first = {"run_nonce": "a" * 64, "authorization_nonce": "auth-1"}

    stage002.claim_execution_marker(marker, first)

    with pytest.raises(stage002.Stage002Error, match="execution_marker_exists"):
        stage002.claim_execution_marker(
            marker,
            {"run_nonce": "b" * 64, "authorization_nonce": "auth-2"},
        )
    assert json.loads(marker.read_text(encoding="utf-8")) == first


def test_execution_marker_allows_exactly_one_concurrent_process(
    tmp_path: Path,
) -> None:
    context = multiprocessing.get_context("fork")
    start = context.Event()
    results = context.Queue()
    marker = tmp_path / "race-execution.json"

    def compete(run_nonce: str) -> None:
        start.wait()
        try:
            stage002.claim_execution_marker(
                marker,
                {"run_nonce": run_nonce, "authorization_nonce": "auth"},
            )
        except stage002.Stage002Error:
            results.put("exists")
        else:
            results.put("claimed")

    processes = [
        context.Process(target=compete, args=("a" * 64,)),
        context.Process(target=compete, args=("b" * 64,)),
    ]
    for process in processes:
        process.start()
    start.set()
    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0

    outcomes = sorted([results.get(timeout=2), results.get(timeout=2)])
    assert outcomes == ["claimed", "exists"]
    assert json.loads(marker.read_text(encoding="utf-8"))["run_nonce"] in {
        "a" * 64,
        "b" * 64,
    }
