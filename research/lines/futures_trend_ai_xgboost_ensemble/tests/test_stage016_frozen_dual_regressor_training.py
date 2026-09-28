from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools/stage016_frozen_dual_regressor_training.py"
)


def load_module():
    assert MODULE_PATH.exists(), "Stage016 frozen dual regressor is not implemented"
    spec = importlib.util.spec_from_file_location(
        "stage016_frozen_dual_regressor_training", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_month_selector_uses_equal_percentile_fusion_and_frozen_tie_breaks() -> None:
    module = load_module()
    month = pd.DataFrame(
        {
            "eval_date": ["2024-04-30"] * 4,
            "product_vt_symbol": ["r10.TEST", "r11.TEST", "r12.TEST", "r13.TEST"],
            "candidate_rank": [10, 11, 12, 13],
            "predicted_return_delta": [0.0, 0.8, 0.4, 0.6],
            "predicted_drawdown_improvement": [0.0, 0.2, 0.6, 0.4],
        }
    )

    scored, selection = module.score_and_select_month(month)

    assert scored["return_percentile"].between(0.0, 1.0, inclusive="right").all()
    assert scored["drawdown_percentile"].between(0.0, 1.0, inclusive="right").all()
    assert selection["arm_a_candidate_rank"] == 10
    # R11/R12/R13 have the same fused rank. Predicted return is the first tie-break.
    assert selection["arm_b_candidate_rank"] == 11
    assert selection["arm_c_candidate_rank"] == 11
    assert selection["arm_c_replaced"] is True


def test_month_selector_falls_back_to_rank10_unless_both_predictions_are_positive() -> None:
    module = load_module()
    month = pd.DataFrame(
        {
            "eval_date": ["2024-05-31"] * 3,
            "product_vt_symbol": ["r10.TEST", "r11.TEST", "r12.TEST"],
            "candidate_rank": [10, 11, 12],
            "predicted_return_delta": [0.0, 0.5, 0.2],
            "predicted_drawdown_improvement": [0.0, -0.1, -0.2],
        }
    )

    _, selection = module.score_and_select_month(month)

    assert selection["arm_b_candidate_rank"] == 11
    assert selection["arm_c_candidate_rank"] == 10
    assert selection["arm_c_replaced"] is False


def _synthetic_month_panel(months: int = 6) -> pd.DataFrame:
    dates = pd.date_range("2022-01-31", periods=months + 1, freq="ME")
    rows = []
    for index, eval_date in enumerate(dates[:-1]):
        for rank in (10, 11):
            rows.append(
                {
                    "eval_date": eval_date.date().isoformat(),
                    "next_eval_date": dates[index + 1].date().isoformat(),
                    "product_vt_symbol": f"r{rank}.TEST",
                    "candidate_rank": rank,
                }
            )
    return pd.DataFrame(rows)


def test_pit_folds_use_only_fully_available_prior_month_labels() -> None:
    module = load_module()
    panel = _synthetic_month_panel()

    folds = module.build_pit_folds(
        panel, min_train_months=3, rows_per_month=2
    )

    assert len(folds) == 3
    assert [len(fold.train_dates) for fold in folds] == [3, 4, 5]
    assert [len(fold.train_indices) for fold in folds] == [6, 8, 10]
    assert [len(fold.test_indices) for fold in folds] == [2, 2, 2]
    assert all(fold.train_label_end_max <= fold.test_date for fold in folds)
    assert all(max(fold.train_dates) < fold.test_date for fold in folds)


def test_pit_folds_reject_inconsistent_label_end_inside_a_month() -> None:
    module = load_module()
    panel = _synthetic_month_panel()
    panel.loc[1, "next_eval_date"] = "2022-12-30"

    with pytest.raises(RuntimeError, match="month_next_eval_date_not_unique"):
        module.build_pit_folds(panel, min_train_months=3, rows_per_month=2)


def test_input_identity_is_checked_before_parsing(tmp_path: Path) -> None:
    module = load_module()
    labels = tmp_path / "labels.csv"
    labels.write_bytes(b"header\n")
    expected = hashlib.sha256(labels.read_bytes()).hexdigest()

    result = module.verify_file_identities(
        {"development_labels": labels}, {"development_labels": expected}
    )
    assert result["development_labels"]["sha256"] == expected

    labels.write_bytes(b"changed\n")
    with pytest.raises(RuntimeError, match="frozen_input_sha_mismatch:development_labels"):
        module.verify_file_identities(
            {"development_labels": labels}, {"development_labels": expected}
        )


def _synthetic_join_inputs(module):
    dates = pd.date_range("2022-01-31", periods=5, freq="ME")
    feature_rows = []
    label_rows = []
    reconciliation_rows = []
    for month_index, eval_date in enumerate(dates[:-1]):
        next_eval_date = dates[month_index + 1]
        for rank in (10, 11):
            common = {
                "eval_date": eval_date.date().isoformat(),
                "next_eval_date": next_eval_date.date().isoformat(),
                "product_vt_symbol": f"r{rank}.TEST",
            }
            feature_row = {
                **common,
                "score_rank": rank,
                "score_type": "ai_probability_top19_plus_fixed_fu",
                "split": "development",
                "label_values_read_allowed": True,
            }
            feature_row.update(
                {column: float(rank - 10) for column in module.MODEL_FEATURE_COLUMNS}
            )
            feature_rows.append(feature_row)
            relative = float(rank - 10)
            label_rows.append(
                {
                    "job_id": f"{eval_date:%Y%m%d}_R{rank}",
                    "job_type": "main",
                    **common,
                    "candidate_rank": rank,
                    "base_equity": 100.0,
                    "end_equity": 100.0 + relative,
                    "future_return": relative / 100.0,
                    "future_max_drawdown": -relative / 100.0,
                    "future_net_pnl": relative,
                    "future_slippage": relative,
                    "future_trade_count": relative,
                    "future_trading_days": 20,
                    "return_delta": relative / 100.0,
                    "drawdown_improvement": relative / 100.0,
                    "net_pnl_delta": relative,
                    "slippage_delta": relative,
                    "trade_count_delta": relative,
                }
            )
            reconciliation_rows.append(
                {
                    "job_id": f"{eval_date:%Y%m%d}_R{rank}",
                    "eval_date": eval_date.date().isoformat(),
                    "candidate_rank": rank,
                    "base_equity_delta": 0.0,
                    "end_equity_vs_net_pnl_delta_error": 0.0,
                    "return_vs_equity_delta_error": 0.0,
                    "target_curve_net_pnl_error": 0.0,
                    "target_curve_slippage_error": 0.0,
                    "target_curve_trade_count_error": 0.0,
                    "target_combined_net_pnl_error": 0.0,
                    "target_combined_slippage_error": 0.0,
                    "target_combined_trade_count_error": 0.0,
                    "target_trade_rows_error": 0.0,
                }
            )
    contract = {
        "features": module.MODEL_FEATURE_COLUMNS,
        "development_split": {
            "month_count": 4,
            "first_eval_date": "2022-01-31",
            "last_eval_date": "2022-04-30",
            "rows_per_month": 2,
        },
        "sealed_holdout": {
            "first_eval_date": "2022-05-31",
            "last_eval_date": "2023-04-28",
            "label_values_read_allowed": False,
        },
    }
    return (
        pd.DataFrame(feature_rows),
        pd.DataFrame(label_rows),
        pd.DataFrame(reconciliation_rows),
        contract,
    )


def test_joined_panel_enforces_shape_reconciliation_and_rank10_zero_baseline() -> None:
    module = load_module()
    features, labels, reconciliation, contract = _synthetic_join_inputs(module)

    panel, audit = module.build_joined_development_panel(
        features, labels, reconciliation, contract
    )

    assert len(panel) == 8
    assert audit["development_months"] == 4
    assert audit["rows"] == 8
    assert audit["reconciliation_max_abs_error"] == 0.0
    assert audit["sealed_holdout_label_rows"] == 0

    labels.loc[labels["candidate_rank"].eq(10), "return_delta"] = 0.001
    with pytest.raises(RuntimeError, match="rank10_relative_label_not_zero"):
        module.build_joined_development_panel(
            features, labels, reconciliation, contract
        )


def test_joined_panel_rejects_nonfinite_labels_and_reconciliation() -> None:
    module = load_module()
    features, labels, reconciliation, contract = _synthetic_join_inputs(module)
    reconciliation.loc[0, "target_curve_net_pnl_error"] = np.nan
    with pytest.raises(RuntimeError, match="development_reconciliation_nonfinite"):
        module.build_joined_development_panel(
            features, labels, reconciliation, contract
        )

    features, labels, reconciliation, contract = _synthetic_join_inputs(module)
    labels.loc[labels["candidate_rank"].eq(11).idxmax(), "return_delta"] = np.inf
    with pytest.raises(RuntimeError, match="development_relative_label_nonfinite"):
        module.build_joined_development_panel(
            features, labels, reconciliation, contract
        )


@pytest.mark.parametrize("bad_value", [np.nan, np.inf, -np.inf])
def test_month_selector_rejects_nonfinite_predictions(bad_value: float) -> None:
    module = load_module()
    month = pd.DataFrame(
        {
            "eval_date": ["2024-04-30", "2024-04-30"],
            "product_vt_symbol": ["r10.TEST", "r11.TEST"],
            "candidate_rank": [10, 11],
            "predicted_return_delta": [0.0, bad_value],
            "predicted_drawdown_improvement": [0.0, 0.1],
        }
    )

    with pytest.raises(RuntimeError, match="selection_prediction_nonfinite"):
        module.score_and_select_month(month)


def test_joined_panel_explicitly_rejects_holdout_label_injection() -> None:
    module = load_module()
    features, labels, reconciliation, contract = _synthetic_join_inputs(module)
    labels.loc[0, "eval_date"] = contract["sealed_holdout"]["first_eval_date"]

    with pytest.raises(RuntimeError, match="sealed_holdout_label_rows_present"):
        module.build_joined_development_panel(
            features, labels, reconciliation, contract
        )


def _qualification_contract() -> dict:
    return {
        "development_split": {"oos_fold_count": 15},
        "qualification": {
            "minimum_c_replacement_months": 4,
            "required_c_replacement_years": [2024, 2025],
            "minimum_total_return_delta_exclusive": 0.0,
            "minimum_total_drawdown_improvement_exclusive": 0.0,
            "minimum_leave_best_out_return_delta_exclusive": 0.0,
            "minimum_leave_best_out_drawdown_improvement_exclusive": 0.0,
            "minimum_each_year_return_delta_inclusive": 0.0,
            "minimum_each_year_drawdown_improvement_inclusive": 0.0,
            "minimum_active_joint_positive_rate_inclusive": 0.5,
        },
    }


def _qualification_rows() -> pd.DataFrame:
    dates = pd.date_range("2024-04-30", periods=15, freq="ME")
    rows = []
    active_indices = {0, 1, 9, 10}
    for index, eval_date in enumerate(dates):
        active = index in active_indices
        rows.append(
            {
                "eval_date": eval_date.date().isoformat(),
                "arm_c_candidate_rank": 11 if active else 10,
                "arm_c_replaced": active,
                "arm_c_realized_return_delta": 0.02 if active else 0.0,
                "arm_c_realized_drawdown_improvement": 0.01 if active else 0.0,
            }
        )
    return pd.DataFrame(rows)


def test_effect_qualification_passes_only_when_all_frozen_gates_pass() -> None:
    module = load_module()

    result = module.evaluate_effect_qualification(
        _qualification_rows(), _qualification_contract()
    )

    assert result["passed"] is True
    assert result["replacement_months"] == 4
    assert result["replacement_years"] == [2024, 2025]
    assert result["active_joint_positive_rate"] == 1.0
    assert all(result["gates"].values())


def test_effect_qualification_rejects_one_month_outlier_dependence() -> None:
    module = load_module()
    rows = _qualification_rows()
    active = rows.index[rows["arm_c_replaced"]]
    rows.loc[active, "arm_c_realized_return_delta"] = [1.0, -0.2, -0.2, -0.2]

    result = module.evaluate_effect_qualification(rows, _qualification_contract())

    assert result["total_return_delta"] > 0.0
    assert result["leave_best_out_return_delta"] < 0.0
    assert result["gates"]["leave_best_out_return_delta_positive"] is False
    assert result["passed"] is False


def test_stage016_decision_distinguishes_technical_and_effect_failures() -> None:
    module = load_module()

    assert (
        module.stage016_decision(technical_pass=False, effect_pass=False)
        == "stage016_contract_or_pit_invalid_stop"
    )
    assert (
        module.stage016_decision(technical_pass=True, effect_pass=False)
        == "stage016_development_oos_proxy_fail_stop_no_holdout"
    )
    assert (
        module.stage016_decision(technical_pass=True, effect_pass=True)
        == "stage016_development_oos_proxy_pass_allow_true_engine_ac"
    )


def test_effect_evaluation_is_not_called_when_technical_gate_fails() -> None:
    module = load_module()
    calls = []

    def forbidden_effect_evaluator(*_args, **_kwargs):
        calls.append(True)
        raise AssertionError("effect evaluator must not be called")

    effect, decision = module.resolve_stage016_outcome(
        technical={"passed": False},
        monthly_selections=pd.DataFrame(
            {
                "arm_c_realized_return_delta": [999.0],
                "arm_c_realized_drawdown_improvement": [999.0],
            }
        ),
        contract={},
        effect_evaluator=forbidden_effect_evaluator,
    )

    assert calls == []
    assert effect is None
    assert decision == "stage016_contract_or_pit_invalid_stop"


def test_technical_failure_report_contains_no_effect_values() -> None:
    module = load_module()

    report = module._build_report(
        decision="stage016_contract_or_pit_invalid_stop",
        technical={"passed": False, "gates": {"pit_violations_zero": False}},
        effect=None,
    )

    assert "技术门未通过，效果评价未执行" in report
    assert "账户边际收益增量合计" not in report
    assert "账户边际回撤改善合计" not in report
    assert "联合命中率" not in report


def test_repeated_xgboost_fit_has_identical_predictions_and_model_bytes() -> None:
    module = load_module()
    random = np.random.default_rng(42)
    features = pd.DataFrame(
        random.normal(size=(180, len(module.MODEL_FEATURE_COLUMNS))),
        columns=module.MODEL_FEATURE_COLUMNS,
    )
    features.iloc[::17, 0] = np.nan
    target = features.fillna(0.0).iloc[:, :3].sum(axis=1).to_numpy()
    predict_frame = features.iloc[-9:].copy()
    params = {
        "objective": "reg:squarederror",
        "eval_metric": "rmse",
        "n_estimators": 16,
        "max_depth": 2,
        "learning_rate": 0.03,
        "min_child_weight": 12.0,
        "gamma": 0.1,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 1.0,
        "reg_lambda": 10.0,
        "tree_method": "hist",
        "random_state": 42,
        "n_jobs": 1,
    }

    fitted = module.fit_repeated_regressor(
        features,
        target,
        predict_frame,
        params=params,
        maximum_prediction_abs_difference=1e-12,
    )

    assert fitted["prediction_max_abs_difference"] == 0.0
    assert fitted["model_sha256"] == fitted["repeat_model_sha256"]
    assert len(fitted["predictions"]) == 9
    assert fitted["model_raw"] == fitted["repeat_model_raw"]


def test_dual_regressor_walk_forward_emits_one_selection_per_fold() -> None:
    module = load_module()
    panel = _synthetic_month_panel(months=6)
    random = np.random.default_rng(7)
    for feature_index, column in enumerate(module.MODEL_FEATURE_COLUMNS):
        panel[column] = (
            panel["candidate_rank"].sub(10).astype(float)
            + feature_index * 0.01
            + random.normal(0.0, 0.01, len(panel))
        )
    panel.loc[::7, module.MODEL_FEATURE_COLUMNS[0]] = np.nan
    panel["return_delta"] = panel["candidate_rank"].sub(10).astype(float) * 0.01
    panel["drawdown_improvement"] = (
        panel["candidate_rank"].sub(10).astype(float) * 0.005
    )
    panel["net_pnl_delta"] = panel["return_delta"] * 100.0
    panel["slippage_delta"] = 0.0
    panel["trade_count_delta"] = 0.0
    folds = module.build_pit_folds(
        panel, min_train_months=3, rows_per_month=2
    )
    contract = {
        "features": module.MODEL_FEATURE_COLUMNS,
        "targets": ["return_delta", "drawdown_improvement"],
        "development_split": {
            "rows_per_month": 2,
            "oos_fold_count": 3,
            "minimum_train_months": 3,
            "first_test_eval_date": "2022-04-30",
            "last_test_eval_date": "2022-06-30",
        },
        "xgb_regressor_parameters": {
            "objective": "reg:squarederror",
            "eval_metric": "rmse",
            "n_estimators": 4,
            "max_depth": 2,
            "learning_rate": 0.03,
            "min_child_weight": 1.0,
            "gamma": 0.0,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "reg_alpha": 1.0,
            "reg_lambda": 10.0,
            "tree_method": "hist",
            "random_state": 42,
            "n_jobs": 1,
        },
        "determinism": {"maximum_prediction_abs_difference": 1e-12},
    }

    result = module.train_oos_dual_regressors(panel, folds, contract)

    assert len(result["predictions"]) == 6
    assert len(result["monthly_selections"]) == 3
    assert len(result["fold_audit"]) == 3
    assert len(result["model_payloads"]) == 6
    assert result["fold_audit"]["train_months"].tolist() == [3, 4, 5]
    assert result["fold_audit"]["pit_violation_rows"].sum() == 0
    for row in result["monthly_selections"].itertuples(index=False):
        if row.arm_c_replaced:
            assert row.arm_b_predicted_return_delta > 0.0
            assert row.arm_b_predicted_drawdown_improvement > 0.0
            assert row.arm_c_candidate_rank == row.arm_b_candidate_rank
        else:
            assert row.arm_c_candidate_rank == 10

    technical = module.evaluate_technical_qualification(
        input_audit={
            "all_input_identities_verified": True,
            "runtime_versions_match": True,
            "stage014_contract_match": True,
        },
        panel_audit={
            "rows": 12,
            "development_months": 6,
            "rows_per_month": 2,
            "rank10_relative_label_max_abs": 0.0,
            "reconciliation_max_abs_error": 0.0,
            "sealed_holdout_label_rows": 0,
        },
        folds=folds,
        training_result=result,
        contract=contract,
    )
    assert technical["passed"] is True
    assert all(technical["gates"].values())


def test_technical_qualification_rejects_c_gate_bypass() -> None:
    module = load_module()
    monthly = pd.DataFrame(
        {
            "eval_date": ["2024-04-30"],
            "arm_a_candidate_rank": [10],
            "arm_b_candidate_rank": [11],
            "arm_b_predicted_return_delta": [-0.1],
            "arm_b_predicted_drawdown_improvement": [0.2],
            "arm_c_candidate_rank": [11],
            "arm_c_replaced": [True],
        }
    )
    fold = module.PitFold(
        train_dates=pd.DatetimeIndex(pd.to_datetime(["2024-01-31"])),
        test_date=pd.Timestamp("2024-04-30"),
        train_indices=pd.Index([0]),
        test_indices=pd.Index([1]),
        train_label_end_max=pd.Timestamp("2024-04-30"),
    )
    training_result = {
        "predictions": pd.DataFrame(
            {"eval_date": ["2024-04-30"], "candidate_rank": [10]}
        ),
        "monthly_selections": monthly,
        "fold_audit": pd.DataFrame(
            {
                "test_eval_date": ["2024-04-30"],
                "train_months": [1],
                "test_rows": [1],
                "pit_violation_rows": [0],
                "return_prediction_repeat_max_abs_difference": [0.0],
                "drawdown_prediction_repeat_max_abs_difference": [0.0],
                "return_model_sha256": ["a"],
                "return_repeat_model_sha256": ["a"],
                "drawdown_model_sha256": ["b"],
                "drawdown_repeat_model_sha256": ["b"],
            }
        ),
        "model_payloads": {"return.ubj": b"a", "drawdown.ubj": b"b"},
    }
    contract = {
        "development_split": {
            "rows_per_month": 1,
            "oos_fold_count": 1,
            "minimum_train_months": 1,
            "first_test_eval_date": "2024-04-30",
            "last_test_eval_date": "2024-04-30",
        },
        "determinism": {"maximum_prediction_abs_difference": 1e-12},
    }

    technical = module.evaluate_technical_qualification(
        input_audit={
            "all_input_identities_verified": True,
            "runtime_versions_match": True,
            "stage014_contract_match": True,
        },
        panel_audit={
            "rows": 2,
            "development_months": 2,
            "rows_per_month": 1,
            "rank10_relative_label_max_abs": 0.0,
            "reconciliation_max_abs_error": 0.0,
            "sealed_holdout_label_rows": 0,
        },
        folds=[fold],
        training_result=training_result,
        contract=contract,
    )

    assert technical["gates"]["arm_c_prediction_gate_exact"] is False
    assert technical["passed"] is False


def test_frozen_contract_and_runtime_match_preregistered_identities() -> None:
    module = load_module()

    contract, audit = module.load_frozen_contract()

    assert contract["contract_status"] == "frozen_before_development_label_values_read"
    assert contract["features"] == module.MODEL_FEATURE_COLUMNS
    assert audit["contract_sha256"] == module.EXPECTED_CONTRACT_SHA256
    assert audit["preregistration_sha256"] == module.EXPECTED_PREREGISTRATION_SHA256
    assert audit["runtime_versions_match"] is True


def test_run_authorization_binds_review_runner_tests_and_contract(tmp_path: Path) -> None:
    module = load_module()
    bound_paths = {}
    for name in ("runner", "tests", "contract", "preregistration", "review"):
        path = tmp_path / f"{name}.txt"
        path.write_text(name, encoding="utf-8")
        bound_paths[name] = path
    manifest = {
        "line_id": "futures_trend_ai_xgboost_ensemble",
        "stage": "Stage016",
        "decision": "ALLOW_FROZEN_STAGE016_RUN",
        "bound_files": {
            name: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for name, path in bound_paths.items()
        },
    }
    authorization_path = tmp_path / "run_authorization.json"
    authorization_path.write_text(
        json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
    )
    authorization_sha = hashlib.sha256(authorization_path.read_bytes()).hexdigest()

    loaded, audit = module.load_run_authorization(
        authorization_path=authorization_path,
        bound_paths=bound_paths,
        expected_authorization_sha256=authorization_sha,
    )

    assert loaded == manifest
    assert audit["authorization_sha256"] == authorization_sha
    assert set(audit["bound_file_identities"]) == set(bound_paths)

    bound_paths["runner"].write_text("changed", encoding="utf-8")
    with pytest.raises(RuntimeError, match="frozen_input_sha_mismatch:runner"):
        module.load_run_authorization(
            authorization_path=authorization_path,
            bound_paths=bound_paths,
            expected_authorization_sha256=authorization_sha,
        )


def test_authorization_change_during_effect_evaluation_is_detected(tmp_path: Path) -> None:
    module = load_module()
    bound_paths = {}
    for name in ("runner", "tests", "contract", "preregistration", "review"):
        path = tmp_path / f"{name}.txt"
        path.write_text(name, encoding="utf-8")
        bound_paths[name] = path
    manifest = {
        "line_id": "futures_trend_ai_xgboost_ensemble",
        "stage": "Stage016",
        "decision": "ALLOW_FROZEN_STAGE016_RUN",
        "bound_files": {
            name: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for name, path in bound_paths.items()
        },
    }
    authorization_path = tmp_path / "run_authorization.json"
    authorization_path.write_text(
        json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
    )
    authorization_sha = hashlib.sha256(authorization_path.read_bytes()).hexdigest()
    before_manifest, before_audit = module.load_run_authorization(
        authorization_path=authorization_path,
        bound_paths=bound_paths,
        expected_authorization_sha256=authorization_sha,
    )

    def mutating_effect_evaluator(_monthly, _contract):
        bound_paths["runner"].write_text("changed during effect", encoding="utf-8")
        return {"passed": False}

    module.resolve_stage016_outcome(
        technical={"passed": True},
        monthly_selections=pd.DataFrame(),
        contract={},
        effect_evaluator=mutating_effect_evaluator,
    )
    with pytest.raises(RuntimeError, match="frozen_input_sha_mismatch:runner"):
        module.require_stable_run_authorization(
            before_manifest=before_manifest,
            before_audit=before_audit,
            authorization_path=authorization_path,
            bound_paths=bound_paths,
            expected_authorization_sha256=authorization_sha,
        )


def test_artifact_bundle_is_atomic_and_cannot_be_overwritten(tmp_path: Path) -> None:
    module = load_module()
    result_dir = tmp_path / "frozen_run"

    identities = module.publish_artifact_bundle(
        result_dir,
        csv_frames={"rows.csv": pd.DataFrame({"a": [1], "b": [2.0]})},
        json_payloads={"decision.json": {"passed": True}},
        text_payloads={"report.md": "# report\n"},
        model_payloads={"20240430_return_delta.ubj": b"model"},
    )

    assert result_dir.is_dir()
    assert (result_dir / "rows.csv").read_text(encoding="utf-8") == "a,b\n1,2.0\n"
    assert (result_dir / "models/20240430_return_delta.ubj").read_bytes() == b"model"
    assert set(identities) == {
        "artifact_manifest.json",
        "decision.json",
        "models/20240430_return_delta.ubj",
        "report.md",
        "rows.csv",
    }
    artifact_manifest = json.loads(
        (result_dir / "artifact_manifest.json").read_text(encoding="utf-8")
    )
    assert set(artifact_manifest["artifacts"]) == {
        "decision.json",
        "models/20240430_return_delta.ubj",
        "report.md",
        "rows.csv",
    }
    with pytest.raises(RuntimeError, match="stage016_result_already_exists"):
        module.publish_artifact_bundle(
            result_dir,
            csv_frames={},
            json_payloads={},
            text_payloads={},
            model_payloads={},
        )


def test_artifact_bundle_rename_failure_leaves_no_partial_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    result_dir = tmp_path / "frozen_run"

    def fail_rename(_source, _target):
        raise OSError("injected rename failure")

    monkeypatch.setattr(module.os, "rename", fail_rename)
    with pytest.raises(OSError, match="injected rename failure"):
        module.publish_artifact_bundle(
            result_dir,
            csv_frames={"rows.csv": pd.DataFrame({"a": [1]})},
            json_payloads={},
            text_payloads={},
            model_payloads={},
        )

    assert not result_dir.exists()
    assert list(tmp_path.glob(".frozen_run.partial.*")) == []


def test_artifact_bundle_post_rename_failure_is_quarantined(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    result_dir = tmp_path / "frozen_run"
    original_fsync_directory = module._fsync_directory

    def fail_parent_fsync(path: Path) -> None:
        if Path(path) == tmp_path and result_dir.exists():
            raise OSError("injected post-rename fsync failure")
        original_fsync_directory(path)

    monkeypatch.setattr(module, "_fsync_directory", fail_parent_fsync)
    with pytest.raises(RuntimeError, match="stage016_post_rename_publish_quarantined"):
        module.publish_artifact_bundle(
            result_dir,
            csv_frames={"rows.csv": pd.DataFrame({"a": [1]})},
            json_payloads={},
            text_payloads={},
            model_payloads={},
        )

    assert not result_dir.exists()
    quarantines = list(tmp_path.glob(".frozen_run.quarantined.*"))
    assert len(quarantines) == 1
    assert (quarantines[0] / "artifact_manifest.json").is_file()
