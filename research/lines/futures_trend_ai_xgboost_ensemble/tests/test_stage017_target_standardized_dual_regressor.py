from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools/stage017_target_standardized_dual_regressor.py"
)


def load_module():
    assert MODULE_PATH.exists(), "Stage017 target-standardized runner is not implemented"
    spec = importlib.util.spec_from_file_location(
        "stage017_target_standardized_dual_regressor", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _params() -> dict:
    return {
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


def test_standardized_fit_is_unit_invariant_deterministic_and_splits() -> None:
    module = load_module()
    random = np.random.default_rng(42)
    features = pd.DataFrame(
        random.normal(size=(180, len(module.MODEL_FEATURE_COLUMNS))),
        columns=module.MODEL_FEATURE_COLUMNS,
    )
    features.iloc[::17, 0] = np.nan
    target = 0.001 * (
        features.fillna(0.0).iloc[:, 0]
        + 0.5 * features.fillna(0.0).iloc[:, 1]
    ).to_numpy()

    fitted = module.fit_repeated_standardized_regressor(
        features.iloc[:-9],
        target[:-9],
        features.iloc[-9:],
        params=_params(),
        unit_probe_multiplier=100.0,
        unit_invariance_tolerance=1e-12,
        prediction_tolerance=1e-12,
    )

    assert fitted["unit_invariance_max_abs_difference"] <= 1e-12
    assert fitted["standardized_prediction_max_abs_difference"] == 0.0
    assert fitted["inverse_prediction_max_abs_difference"] == 0.0
    assert fitted["model_sha256"] == fitted["repeat_model_sha256"]
    assert fitted["scaler_sha256"] == fitted["repeat_scaler_sha256"]
    assert fitted["scaler_raw"] == fitted["repeat_scaler_raw"]
    assert fitted["scaler_scale"] > 0.0
    assert fitted["split_nodes"] > 0
    assert len(fitted["predictions"]) == 9

    scaled_unit = module.fit_repeated_standardized_regressor(
        features.iloc[:-9],
        target[:-9] * 100.0,
        features.iloc[-9:],
        params=_params(),
        unit_probe_multiplier=100.0,
        unit_invariance_tolerance=1e-12,
        prediction_tolerance=1e-12,
    )
    assert scaled_unit["model_sha256"] == fitted["model_sha256"]
    assert np.array_equal(
        scaled_unit["predictions_standardized"],
        fitted["predictions_standardized"],
    )
    assert np.max(
        np.abs(scaled_unit["predictions"] / 100.0 - fitted["predictions"])
    ) <= 1e-12


def test_standardized_fit_rejects_zero_variance_target() -> None:
    module = load_module()
    features = pd.DataFrame(
        np.arange(180 * len(module.MODEL_FEATURE_COLUMNS), dtype=float).reshape(
            180, len(module.MODEL_FEATURE_COLUMNS)
        ),
        columns=module.MODEL_FEATURE_COLUMNS,
    )

    with pytest.raises(RuntimeError, match="stage017_target_scaler_invalid"):
        module.fit_repeated_standardized_regressor(
            features.iloc[:-9],
            np.zeros(171),
            features.iloc[-9:],
            params=_params(),
            unit_probe_multiplier=100.0,
            unit_invariance_tolerance=1e-12,
            prediction_tolerance=1e-12,
        )


def test_standardized_walk_forward_emits_models_scalers_and_frozen_selections() -> None:
    module = load_module()
    dates = pd.date_range("2022-01-31", periods=16, freq="ME")
    rows = []
    random = np.random.default_rng(7)
    for month_index, eval_date in enumerate(dates[:-1]):
        for rank in range(10, 19):
            row = {
                "eval_date": eval_date.date().isoformat(),
                "next_eval_date": dates[month_index + 1].date().isoformat(),
                "product_vt_symbol": f"r{rank}.TEST",
                "candidate_rank": rank,
            }
            for feature_index, column in enumerate(module.MODEL_FEATURE_COLUMNS):
                row[column] = (
                    float(rank - 10)
                    + feature_index * 0.01
                    + random.normal(0.0, 0.01)
                )
            row["return_delta"] = float(rank - 10) * 0.01
            row["drawdown_improvement"] = float(rank - 10) * 0.005
            row["net_pnl_delta"] = row["return_delta"] * 100.0
            row["slippage_delta"] = 0.0
            row["trade_count_delta"] = 0.0
            rows.append(row)
    panel = pd.DataFrame(rows)
    panel.loc[::7, module.MODEL_FEATURE_COLUMNS[0]] = np.nan
    folds = module.s16.build_pit_folds(
        panel, min_train_months=12, rows_per_month=9
    )
    contract = {
        "features": module.MODEL_FEATURE_COLUMNS,
        "targets": ["return_delta", "drawdown_improvement"],
        "development_split": {
            "rows_per_month": 9,
            "oos_fold_count": 3,
            "minimum_train_months": 12,
            "first_test_eval_date": "2023-01-31",
            "last_test_eval_date": "2023-03-31",
        },
        "xgb_regressor_parameters": _params(),
        "target_transform": {
            "unit_invariance_probe_multiplier": 100.0,
            "unit_invariance_max_abs_difference": 1e-12,
        },
        "determinism": {
            "maximum_standardized_prediction_abs_difference": 1e-12,
            "maximum_inverse_prediction_abs_difference": 1e-12,
        },
    }

    result = module.train_oos_standardized_dual_regressors(panel, folds, contract)

    assert len(result["predictions"]) == 27
    assert len(result["monthly_selections"]) == 3
    assert len(result["fold_audit"]) == 3
    assert len(result["model_payloads"]) == 6
    assert len(result["scaler_payloads"]) == 6
    assert result["fold_audit"]["train_months"].tolist() == [12, 13, 14]
    assert result["fold_audit"]["pit_violation_rows"].sum() == 0
    assert result["fold_audit"]["unit_invariance_max_abs_difference"].max() <= 1e-12
    assert result["fold_audit"]["split_nodes_total"].sum() > 0
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
            "stage016_dependency_match": True,
        },
        panel_audit={
            "sealed_holdout_label_rows": 0,
            "rank10_relative_label_max_abs": 0.0,
            "reconciliation_max_abs_error": 0.0,
        },
        folds=folds,
        training_result=result,
        contract=contract,
    )
    assert technical["passed"] is True
    assert all(technical["gates"].values())

    # Tree structure is diagnostic only; zero splits must not silently become an effect gate.
    result["fold_audit"].loc[:, [
        "return_split_nodes",
        "drawdown_split_nodes",
        "split_nodes_total",
    ]] = 0
    diagnostic_only = module.evaluate_technical_qualification(
        input_audit={
            "all_input_identities_verified": True,
            "runtime_versions_match": True,
            "stage014_contract_match": True,
            "stage016_dependency_match": True,
        },
        panel_audit={
            "sealed_holdout_label_rows": 0,
            "rank10_relative_label_max_abs": 0.0,
            "reconciliation_max_abs_error": 0.0,
        },
        folds=folds,
        training_result=result,
        contract=contract,
    )
    assert diagnostic_only["passed"] is True


def test_stage017_decision_and_technical_failure_short_circuit() -> None:
    module = load_module()
    assert (
        module.stage017_decision(technical_pass=False, effect_pass=False)
        == "stage017_contract_or_unit_transform_invalid_stop"
    )
    assert (
        module.stage017_decision(technical_pass=True, effect_pass=False)
        == "stage017_target_standardized_oos_fail_stop_feature_label_family"
    )
    assert (
        module.stage017_decision(technical_pass=True, effect_pass=True)
        == "stage017_target_standardized_oos_pass_allow_development_true_engine_ac"
    )
    calls = []

    def forbidden_effect(*_args, **_kwargs):
        calls.append(True)
        raise AssertionError("effect evaluator must not be called")

    effect, decision = module.resolve_stage017_outcome(
        technical={"passed": False},
        monthly_selections=pd.DataFrame(),
        contract={},
        effect_evaluator=forbidden_effect,
    )
    assert calls == []
    assert effect is None
    assert decision == "stage017_contract_or_unit_transform_invalid_stop"


def test_frozen_contract_runtime_and_stage016_dependency_match() -> None:
    module = load_module()

    contract, audit = module.load_frozen_contract()

    assert contract["contract_status"] == "frozen_before_stage017_target_standardized_oos_run"
    assert contract["features"] == module.MODEL_FEATURE_COLUMNS
    assert contract["target_transform"]["class"] == "sklearn.preprocessing.StandardScaler"
    assert audit["contract_sha256"] == module.EXPECTED_CONTRACT_SHA256
    assert audit["preregistration_sha256"] == module.EXPECTED_PREREGISTRATION_SHA256
    assert audit["runtime_versions_match"] is True
    assert audit["stage016_contract_match"] is True


def test_run_authorization_binds_stage017_and_stage016_dependency(tmp_path: Path) -> None:
    module = load_module()
    names = {
        "runner",
        "tests",
        "contract",
        "preregistration",
        "review",
        "stage016_postrun_review",
    }
    bound_paths = {}
    for name in names:
        path = tmp_path / f"{name}.txt"
        path.write_text(name, encoding="utf-8")
        bound_paths[name] = path
    manifest = {
        "line_id": "futures_trend_ai_xgboost_ensemble",
        "stage": "Stage017",
        "decision": "ALLOW_FROZEN_STAGE017_RUN",
        "bound_files": {
            name: {
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
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
    assert set(audit["bound_file_identities"]) == names
    bound_paths["stage016_postrun_review"].write_text("changed", encoding="utf-8")
    with pytest.raises(
        RuntimeError, match="frozen_input_sha_mismatch:stage016_postrun_review"
    ):
        module.load_run_authorization(
            authorization_path=authorization_path,
            bound_paths=bound_paths,
            expected_authorization_sha256=authorization_sha,
        )


def test_artifact_bundle_is_atomic_and_keeps_scalers_separate(tmp_path: Path) -> None:
    module = load_module()
    result_dir = tmp_path / "frozen_run"

    identities = module.publish_artifact_bundle(
        result_dir,
        csv_frames={"rows.csv": pd.DataFrame({"a": [1]})},
        json_payloads={"decision.json": {"passed": True}},
        text_payloads={"report.md": "# report\n"},
        model_payloads={"20240430_return_delta.ubj": b"model"},
        scaler_payloads={"20240430_return_delta_scaler.json": b"{}\n"},
    )

    assert (result_dir / "models/20240430_return_delta.ubj").read_bytes() == b"model"
    assert (
        result_dir / "scalers/20240430_return_delta_scaler.json"
    ).read_bytes() == b"{}\n"
    manifest = json.loads(
        (result_dir / "artifact_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["stage"] == "Stage017"
    assert "scalers/20240430_return_delta_scaler.json" in manifest["artifacts"]
    assert set(identities) == set(manifest["artifacts"]) | {"artifact_manifest.json"}
    with pytest.raises(RuntimeError, match="stage017_result_already_exists"):
        module.publish_artifact_bundle(
            result_dir,
            csv_frames={},
            json_payloads={},
            text_payloads={},
            model_payloads={},
            scaler_payloads={},
        )


def test_post_rename_publish_failure_is_quarantined(
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
    with pytest.raises(RuntimeError, match="stage017_post_rename_publish_quarantined"):
        module.publish_artifact_bundle(
            result_dir,
            csv_frames={"rows.csv": pd.DataFrame({"a": [1]})},
            json_payloads={},
            text_payloads={},
            model_payloads={},
            scaler_payloads={},
        )

    assert not result_dir.exists()
    quarantines = list(tmp_path.glob(".frozen_run.quarantined.*"))
    assert len(quarantines) == 1


def test_main_rechecks_identities_three_times_and_short_circuits_effect_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = load_module()
    result_dir = tmp_path / "frozen_run"
    input_path = tmp_path / "input.txt"
    input_path.write_text("frozen", encoding="utf-8")
    contract = {
        "input_sha256": {"input": "frozen-sha"},
        "development_split": {"minimum_train_months": 1, "rows_per_month": 1},
    }
    contract_audit = {"runtime_versions_match": True}
    authorization = {"decision": "ALLOW_FROZEN_STAGE017_RUN"}
    authorization_audit = {"authorization_sha256": "authorization-sha"}
    calls = {"contract": 0, "authorization": 0, "inputs": 0}
    published = {}

    def frozen_contract():
        calls["contract"] += 1
        return contract, contract_audit

    def initial_authorization(**_kwargs):
        calls["authorization"] += 1
        return authorization, authorization_audit

    def stable_authorization(**_kwargs):
        calls["authorization"] += 1
        return authorization, authorization_audit

    def verify_inputs(_paths, _expected):
        calls["inputs"] += 1
        return {"input": {"path": str(input_path), "sha256": "frozen-sha"}}

    def capture_publish(_result_dir, **kwargs):
        published.update(kwargs)
        return {}

    training_result = {
        "predictions": pd.DataFrame(),
        "monthly_selections": pd.DataFrame(),
        "fold_audit": pd.DataFrame(),
        "model_payloads": {},
        "scaler_payloads": {},
    }
    technical = {
        "passed": False,
        "gates": {"target_unit_invariance": False},
        "split_nodes_total": 0,
    }
    monkeypatch.setattr(module, "RESULT_DIR", result_dir)
    monkeypatch.setattr(module, "load_frozen_contract", frozen_contract)
    monkeypatch.setattr(module, "load_run_authorization", initial_authorization)
    monkeypatch.setattr(
        module, "require_stable_run_authorization", stable_authorization
    )
    monkeypatch.setattr(module, "_input_paths", lambda: {"input": input_path})
    monkeypatch.setattr(module, "_validate_upstream_contracts", lambda _contract: None)
    monkeypatch.setattr(module.s16, "verify_file_identities", verify_inputs)
    monkeypatch.setattr(module.pd, "read_csv", lambda *_args, **_kwargs: pd.DataFrame())
    monkeypatch.setattr(
        module.s16,
        "build_joined_development_panel",
        lambda *_args, **_kwargs: (pd.DataFrame(), {"sealed_holdout_label_rows": 0}),
    )
    monkeypatch.setattr(module.s16, "build_pit_folds", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        module,
        "train_oos_standardized_dual_regressors",
        lambda *_args, **_kwargs: training_result,
    )
    monkeypatch.setattr(
        module, "evaluate_technical_qualification", lambda **_kwargs: technical
    )
    monkeypatch.setattr(module, "publish_artifact_bundle", capture_publish)
    monkeypatch.setenv("STAGE017_RUN_AUTHORIZATION_SHA256", "authorization-sha")

    module.main()

    assert calls == {"contract": 3, "authorization": 3, "inputs": 3}
    assert set(published["csv_frames"]) == {"fold_audit.csv"}
    assert "effect_qualification.json" not in published["json_payloads"]
    assert published["model_payloads"] == {}
    assert published["scaler_payloads"] == {}
    assert "账户边际收益增量合计" not in published["text_payloads"]["report.md"]
    assert "stage017_contract_or_unit_transform_invalid_stop" in capsys.readouterr().out
