from __future__ import annotations

import importlib.util
import hashlib
import inspect
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


LINE_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = LINE_DIR / "tools/stage003_joint_ranker_development_oos.py"
CONTRACT_PATH = LINE_DIR / "contracts/stage003_joint_ranker_development_oos_training_contract.json"
SPEC = importlib.util.spec_from_file_location("stage003_joint_ranker_development_oos", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_machine_contract_freezes_single_joint_ranker_and_zero_arg_entrypoints() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    assert list(inspect.signature(module.run_stage003).parameters) == []
    assert list(inspect.signature(module.main).parameters) == []
    assert contract["model_features"] == module.MODEL_FEATURES
    assert contract["model"]["class"] == "xgboost.XGBRanker"
    assert contract["model"]["params"] == module.MODEL_PARAMS
    assert contract["model"]["fit_count"] == 26
    assert contract["folds"]["active_fold_count"] == 13
    assert contract["folds"]["fallback_month_count"] == 4
    assert contract["label_access"]["unique_job_label_rows"] == 153
    assert contract["label_access"]["holdout_label_rows_read"] == 0
    assert contract["effect_gate_keys"] == module.EFFECT_GATE_KEYS


def test_probability_projection_contract_and_authorization_chain_are_exact() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    assert contract["input_projection"]["full_feature_split_allowed_columns"] == (
        module.FULL_SPLIT_ALLOWED_COLUMNS
    )
    assert contract["input_projection"]["join_keys"] == module.METADATA_JOIN_KEYS
    assert contract["input_projection"]["probability_delta_absolute_tolerance"] == 1e-12
    assert contract["input_projection"]["feature_rows"] == 218
    assert contract["input_projection"]["split_projection_rows"] == 374
    assert contract["input_projection"]["right_only_source_rows"] == 156
    assert contract["input_projection"]["right_only_source_keys_sha256"] == (
        "b23dea181667fd436a1b9ab55b8e141b0e3fadd378610da3aa8e4e07b644aa41"
    )
    assert len(contract["authorization"]["bound_file_keys"]) == 27
    assert contract["authorization"]["bound_file_keys"] == module.BOUND_FILE_KEYS
    assert set(contract["authorization"]["bound_file_paths"]) == set(module.BOUND_FILE_KEYS)


def _synthetic_probability_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    features = pd.DataFrame(
        [
            {
                "eval_date": "2024-01-31",
                "product_vt_symbol": "MA.CZCE",
                "a_rank": 10,
                **{feature: 0.0 for feature in module.MODEL_FEATURES},
            },
            {
                "eval_date": "2024-01-31",
                "product_vt_symbol": "rb.SHFE",
                "a_rank": 11,
                **{
                    feature: (0.1 if feature == "formal_probability_delta_vs_rank10" else 0.01)
                    for feature in module.MODEL_FEATURES
                },
            },
            {
                "eval_date": "2024-02-29",
                "product_vt_symbol": "au.SHFE",
                "a_rank": 10,
                **{feature: 0.0 for feature in module.MODEL_FEATURES},
            },
            {
                "eval_date": "2024-02-29",
                "product_vt_symbol": "cu.SHFE",
                "a_rank": 11,
                **{
                    feature: (-0.2 if feature == "formal_probability_delta_vs_rank10" else -0.01)
                    for feature in module.MODEL_FEATURES
                },
            },
        ]
    )
    split = pd.DataFrame(
        [
            ["2024-01-31", "2024-02-29", "MA.CZCE", 10, "development", 0.4],
            ["2024-01-31", "2024-02-29", "rb.SHFE", 11, "development", 0.5],
            ["2024-02-29", "2024-03-29", "au.SHFE", 10, "sealed_account_label_holdout", 0.7],
            ["2024-02-29", "2024-03-29", "cu.SHFE", 11, "sealed_account_label_holdout", 0.5],
        ],
        columns=module.FULL_SPLIT_ALLOWED_COLUMNS,
    )
    return features, split


def test_raw_probability_projection_is_one_to_one_and_delta_consistent() -> None:
    features, split = _synthetic_probability_inputs()

    panel, audit = module._join_raw_probability_projection(features, split)

    assert len(panel) == 4
    assert panel["pit_logistic_probability"].tolist() == [0.4, 0.5, 0.7, 0.5]
    assert audit == {
        "feature_rows": 4,
        "joined_rows": 4,
        "missing_join_rows": 0,
        "extra_join_rows": 0,
        "right_only_source_rows": 0,
        "right_only_source_keys_sha256": hashlib.sha256(b"[]").hexdigest(),
        "feature_duplicate_keys": 0,
        "split_duplicate_keys": 0,
        "probability_nonfinite_rows": 0,
        "probability_out_of_range_rows": 0,
        "rank10_rows": 2,
        "probability_delta_max_abs_error": pytest.approx(0.0),
    }
    matrix = module._extract_ranker_matrix(panel, module.MODEL_FEATURES)
    assert list(matrix.columns) == module.MODEL_FEATURES
    assert np.isfinite(matrix.to_numpy()).all()


def test_actual_frozen_probability_projection_has_expected_no_label_shape() -> None:
    features = pd.read_csv(
        LINE_DIR / "artifacts/stage002_physical_features/model_eligible_feature_panel.csv"
    )
    split = pd.read_csv(
        LINE_DIR.parents[0]
        / "futures_trend_xgboost_pit_curve_account_labels/artifacts/"
        "stage003_account_label_plan/full_feature_split.csv",
        usecols=module.FULL_SPLIT_ALLOWED_COLUMNS,
    )

    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    panel, audit = module._join_raw_probability_projection(
        features,
        split,
        projection_contract=contract["input_projection"],
    )

    assert len(panel) == 218
    assert panel.groupby("split", sort=True).size().to_dict() == {
        "development": 153,
        "sealed_account_label_holdout": 65,
    }
    assert panel.groupby("split", sort=True)["eval_date"].nunique().to_dict() == {
        "development": 26,
        "sealed_account_label_holdout": 9,
    }
    assert audit["missing_join_rows"] == 0
    assert audit["extra_join_rows"] == 0
    assert audit["right_only_source_rows"] == 156
    assert audit["right_only_source_keys_sha256"] == (
        "b23dea181667fd436a1b9ab55b8e141b0e3fadd378610da3aa8e4e07b644aa41"
    )
    assert audit["probability_delta_max_abs_error"] <= 1e-12


def test_actual_frozen_metadata_builds_exact_active_and_fallback_fold_plan() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    features = pd.read_csv(module.STAGE002_FEATURE_PANEL_PATH)
    split = pd.read_csv(
        module.FULL_FEATURE_SPLIT_PATH,
        usecols=module.FULL_SPLIT_ALLOWED_COLUMNS,
    )
    jobs = pd.read_csv(
        module.DEVELOPMENT_JOBS_PATH,
        usecols=module.JOB_ALLOWED_COLUMNS,
    )

    state = module._build_frozen_metadata_state(features, split, jobs, contract)

    assert state["audit"]["development_rows"] == 153
    assert state["audit"]["development_active_months"] == 26
    assert state["audit"]["holdout_feature_rows"] == 65
    assert state["audit"]["holdout_active_months"] == 9
    assert state["audit"]["initial_training_rows"] == 62
    assert state["audit"]["initial_training_qids"] == 13
    assert state["audit"]["a2_jobs_used"] == 0
    assert [fold["test_eval_date"] for fold in state["active_folds"]] == contract[
        "folds"
    ]["active_test_dates"]
    assert [fold["train_rows"] for fold in state["active_folds"]] == contract[
        "folds"
    ]["training_rows"]
    assert [fold["train_qids"] for fold in state["active_folds"]] == contract[
        "folds"
    ]["training_qids"]
    assert [fold["test_rows"] for fold in state["active_folds"]] == contract[
        "folds"
    ]["test_rows"]
    assert state["fallback_months"]["eval_date"].tolist() == contract["folds"][
        "fallback_test_dates"
    ]
    assert state["oos_calendar_dates"] == sorted(
        contract["folds"]["active_test_dates"]
        + contract["folds"]["fallback_test_dates"]
    )
    forbidden = {
        "label_values_read_allowed",
        "account_label_qid",
        "role",
        "window_id",
        "pit_logistic_probability",
    }
    for fold in state["active_folds"]:
        assert not forbidden.intersection(fold["ranker_feature_order"])
        assert fold["ranker_feature_order"] == module.MODEL_FEATURES


def test_full_machine_contract_structure_and_current_runtime_are_exact() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    audit = module._validate_machine_contract(contract)
    runtime = module._verify_frozen_runtime_identity(contract)

    assert audit["model_feature_order_exact"] is True
    assert audit["model_params_exact"] is True
    assert audit["authorization_bound_file_count"] == 27
    assert runtime["xgboost_version"] == "3.2.0"
    assert runtime["python_version"] == "3.11.15"


def test_ranker_fold_preparation_binds_qid_features_jobs_and_test_keys() -> None:
    train_rows = []
    label_rows = []
    for month_index, (eval_date, next_eval_date) in enumerate(
        [("2023-05-31", "2023-06-30"), ("2023-06-30", "2023-07-31")]
    ):
        for offset, product in enumerate(["MA.CZCE", "rb.SHFE", "au.SHFE"]):
            rank = 10 + offset
            job_id = f"m{month_index}_r{rank}"
            train_rows.append(
                {
                    "eval_date": eval_date,
                    "next_eval_date": next_eval_date,
                    "product_vt_symbol": product,
                    "a_rank": rank,
                    "job_id": job_id,
                    "eligibility_key": job_id,
                    "eligibility_sha256": "a" * 64,
                    **{
                        feature: (0.0 if rank == 10 else float(offset + month_index + 1))
                        for feature in module.MODEL_FEATURES
                    },
                }
            )
            label_rows.append(
                {
                    "eval_date": eval_date,
                    "next_eval_date": next_eval_date,
                    "product_vt_symbol": product,
                    "a_rank": rank,
                    "job_id": job_id,
                    "return_delta": [0.0, 0.2, 0.1][offset],
                    "drawdown_improvement": [0.0, 0.1, 0.2][offset],
                }
            )
    test = pd.DataFrame(
        [
            {
                "eval_date": "2023-07-31",
                "next_eval_date": "2023-08-31",
                "product_vt_symbol": product,
                "a_rank": rank,
                "pit_logistic_probability": probability,
                **{
                    feature: (0.0 if rank == 10 else float(rank - 10))
                    for feature in module.MODEL_FEATURES
                },
            }
            for rank, product, probability in [
                (10, "MA.CZCE", 0.6),
                (11, "rb.SHFE", 0.5),
                (12, "au.SHFE", 0.4),
            ]
        ]
    )

    prepared = module._prepare_ranker_fold(
        train_panel=pd.DataFrame(train_rows),
        test_panel=test,
        opened_labels=pd.DataFrame(label_rows),
        test_eval_date="2023-07-31",
    )

    assert list(prepared["train_matrix"].columns) == module.MODEL_FEATURES
    assert list(prepared["test_matrix"].columns) == module.MODEL_FEATURES
    assert prepared["qid"] == [0, 0, 0, 1, 1, 1]
    assert prepared["fold_input"]["group_boundaries"] == [0, 3, 6]
    assert prepared["fold_input"]["qid"] == prepared["qid"]
    assert prepared["fold_input"]["feature_order"] == module.MODEL_FEATURES
    assert [row["job_id"] for row in prepared["fold_input"]["ordered_training_job_identities"]] == [
        "m0_r10",
        "m0_r11",
        "m0_r12",
        "m1_r10",
        "m1_r11",
        "m1_r12",
    ]
    assert prepared["fold_input"]["ordered_test_keys"] == [
        {"eval_date": "2023-07-31", "product_vt_symbol": "MA.CZCE", "a_rank": 10},
        {"eval_date": "2023-07-31", "product_vt_symbol": "rb.SHFE", "a_rank": 11},
        {"eval_date": "2023-07-31", "product_vt_symbol": "au.SHFE", "a_rank": 12},
    ]
    assert prepared["target"].tolist() == [0, 1, 1, 0, 1, 1]


def test_effect_sequence_contains_all_active_and_fallback_months_with_exact_zero_fallbacks() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    active = [
        {
            "eval_date": date,
            "arm_c_replaced": index % 2 == 0,
            "arm_c_product_vt_symbol": "rb.SHFE",
            "return_delta": 0.1 if index % 2 == 0 else 0.0,
            "drawdown_improvement": 0.05 if index % 2 == 0 else 0.0,
            "seal_type": "active_model_fold",
        }
        for index, date in enumerate(contract["folds"]["active_test_dates"])
    ]
    fallback = [
        module._fallback_effect_row(
            date, {"a_rank": 10, "product_vt_symbol": "MA.CZCE"}
        )
        for date in contract["folds"]["fallback_test_dates"]
    ]

    sequence = module._assemble_effect_sequence(active, fallback, contract)

    assert len(sequence) == 17
    assert sequence["eval_date"].tolist() == sorted(
        contract["folds"]["active_test_dates"]
        + contract["folds"]["fallback_test_dates"]
    )
    fallback_rows = sequence[sequence["seal_type"].eq("fallback_fold")]
    assert len(fallback_rows) == 4
    assert fallback_rows["arm_c_replaced"].eq(False).all()  # noqa: E712
    assert fallback_rows["return_delta"].eq(0.0).all()
    assert fallback_rows["drawdown_improvement"].eq(0.0).all()


def test_fit_helper_and_production_entrypoint_are_frozen_and_not_stubbed() -> None:
    fit_signature = inspect.signature(module._fit_repeated_ranker)
    fit_source = inspect.getsource(module._fit_repeated_ranker)
    run_source = inspect.getsource(module.run_stage003)

    assert list(fit_signature.parameters) == [
        "train_matrix",
        "target",
        "qid_values",
        "test_matrix",
        "model_params",
        "ranker_factory",
        "event_ledger",
        "eval_date",
    ]
    assert "for _ in range(2)" in fit_source
    assert ".fit(" in fit_source
    assert "qid=qid" in fit_source
    assert "verbose=False" in fit_source
    assert "save_raw(raw_format=\"ubj\")" in fit_source
    assert "early_stopping" not in fit_source
    assert "stage003_execution_not_yet_implemented" not in run_source
    assert "_validate_authorization_from_paths" in run_source
    assert "_persist_validated_authorization" in run_source
    assert "xgboost.XGBRanker" in run_source
    assert "os.environ" not in run_source


def test_governance_decisions_bind_reviews_and_require_zero_blocking_severity(
    tmp_path: Path,
) -> None:
    pairs = [
        (
            "stage003_rereview",
            "stage003_rereview_decision",
            "ALLOW_STAGE003_TDD_IMPLEMENTATION_ONLY",
        ),
        (
            "stage003_probability_remediation_rereview",
            "stage003_probability_remediation_rereview_decision",
            "ALLOW_STAGE003_TDD_IMPLEMENTATION_AFTER_PROBABILITY_REMEDIATION_ONLY",
        ),
        (
            "stage003_full_split_sha_remediation_rereview",
            "stage003_full_split_sha_remediation_rereview_decision",
            "ALLOW_STAGE003_TDD_IMPLEMENTATION_AFTER_SHA_REMEDIATION_ONLY",
        ),
        (
            "final_implementation_review",
            "final_implementation_review_decision",
            module.FINAL_IMPLEMENTATION_ALLOW_DECISION,
        ),
    ]
    paths: dict[str, str] = {}
    for review_key, decision_key, expected_decision in pairs:
        review_path = tmp_path / f"{review_key}.md"
        review_path.write_text(f"# {review_key}\n", encoding="utf-8")
        decision_path = tmp_path / f"{decision_key}.json"
        decision_path.write_text(
            json.dumps(
                {
                    "decision": expected_decision,
                    "allowed": True,
                    "severity": {"P0": 0, "P1": 0, "P2": 0, "P3": 1},
                    "review_path": str(review_path.resolve()),
                    "review_sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
                }
            ),
            encoding="utf-8",
        )
        paths[review_key] = str(review_path.resolve())
        paths[decision_key] = str(decision_path.resolve())
    contract = {"authorization": {"bound_file_paths": paths}}

    audit = module._validate_governance_decisions(contract)

    assert audit["passed"] is True
    assert set(audit["decisions"]) == {pair[1] for pair in pairs}
    assert all(item["blocking_severity_zero"] is True for item in audit["decisions"].values())

    final_path = Path(paths["final_implementation_review_decision"])
    final = json.loads(final_path.read_text(encoding="utf-8"))
    final["severity"]["P2"] = 1
    final_path.write_text(json.dumps(final), encoding="utf-8")
    with pytest.raises(module.Stage003Error, match="governance_decision_not_eligible"):
        module._validate_governance_decisions(contract)


def test_checkpoint_stability_requires_three_named_identical_snapshots() -> None:
    names = [
        "before_training",
        "after_all_models",
        "after_effect_evaluation",
    ]
    checkpoints = [
        {
            "checkpoint": name,
            "authorization_and_inputs_identity_sha256": "a" * 64,
            "runtime_identity_sha256": "b" * 64,
        }
        for name in names
    ]

    audit = module._build_checkpoint_stability_audit(checkpoints)

    assert audit["passed"] is True
    assert audit["checkpoint_count"] == 3
    assert audit["checkpoint_names_exact"] is True
    assert audit["authorization_and_inputs_exact"] is True
    assert audit["runtime_identity_exact"] is True

    checkpoints[1] = {
        **checkpoints[1],
        "authorization_and_inputs_identity_sha256": "c" * 64,
    }
    assert module._build_checkpoint_stability_audit(checkpoints)["passed"] is False


def test_pre_effect_readiness_uses_two_real_snapshots_and_all_other_gates() -> None:
    gates = {name: True for name in module.TECHNICAL_GATE_KEYS}
    gates["authorization_and_inputs_three_point_exact"] = False
    gates["runtime_identity_three_point_exact"] = False
    technical = {"gates": gates}
    first = {
        "checkpoint": "before_training",
        "authorization_and_inputs_identity_sha256": "a" * 64,
        "runtime_identity_sha256": "b" * 64,
    }
    second = {**first, "checkpoint": "after_all_models"}

    assert module._pre_effect_technical_ready(technical, first, second) is True

    second["runtime_identity_sha256"] = "c" * 64
    assert module._pre_effect_technical_ready(technical, first, second) is False
    second = {**first, "checkpoint": "after_all_models"}
    gates["physical_feature_splits_exact"] = False
    assert module._pre_effect_technical_ready(technical, first, second) is False


def test_joint_relevance_is_monthwise_dense_rank_maximin() -> None:
    labels = pd.DataFrame(
        [
            {"eval_date": "2024-01-31", "a_rank": 10, "return_delta": 0.0, "drawdown_improvement": 0.0},
            {"eval_date": "2024-01-31", "a_rank": 11, "return_delta": 0.2, "drawdown_improvement": 0.05},
            {"eval_date": "2024-01-31", "a_rank": 12, "return_delta": 0.1, "drawdown_improvement": 0.15},
            {"eval_date": "2024-02-29", "a_rank": 10, "return_delta": 0.0, "drawdown_improvement": 0.0},
            {"eval_date": "2024-02-29", "a_rank": 11, "return_delta": -0.1, "drawdown_improvement": 0.2},
            {"eval_date": "2024-02-29", "a_rank": 12, "return_delta": 0.2, "drawdown_improvement": 0.1},
        ]
    )

    result = module._build_joint_relevance(labels)

    january = result[result["eval_date"].eq(pd.Timestamp("2024-01-31"))]
    assert january["return_relevance"].tolist() == [0, 2, 1]
    assert january["drawdown_relevance"].tolist() == [0, 1, 2]
    assert january["joint_relevance"].tolist() == [0, 1, 1]
    assert result["joint_relevance"].map(type).eq(int).all()


def test_lr_xgb_percentile_fusion_selects_challenger_without_raw_score_addition() -> None:
    rows = pd.DataFrame(
        [
            {"eval_date": "2024-01-31", "product_vt_symbol": "MA.CZCE", "a_rank": 10, "pit_logistic_probability": 0.90, "primary_xgb_score": 0.0, "repeat_xgb_score": 0.0},
            {"eval_date": "2024-01-31", "product_vt_symbol": "rb.SHFE", "a_rank": 11, "pit_logistic_probability": 0.80, "primary_xgb_score": 2.0, "repeat_xgb_score": 2.0},
            {"eval_date": "2024-01-31", "product_vt_symbol": "au.SHFE", "a_rank": 12, "pit_logistic_probability": 0.70, "primary_xgb_score": 1.0, "repeat_xgb_score": 1.0},
        ]
    )

    prediction = module._build_prediction_payload("2024-01-31", rows)
    selection = module._build_selection_payload(prediction)

    assert selection["arm_a"] == {"a_rank": 10, "product_vt_symbol": "MA.CZCE"}
    assert selection["arm_b"] == {"a_rank": 11, "product_vt_symbol": "rb.SHFE"}
    assert selection["arm_c"] == {"a_rank": 11, "product_vt_symbol": "rb.SHFE"}
    challenger = next(
        row for row in prediction["ordered_rows"] if row["product_vt_symbol"] == "rb.SHFE"
    )
    assert challenger["lr_percentile"] == 2 / 3
    assert challenger["xgb_percentile"] == 1.0
    assert challenger["ensemble_score"] == (2 / 3 + 1.0) / 2


def test_empty_replacement_metrics_are_null_and_all_gate_values_are_native_bool() -> None:
    rows = pd.DataFrame(
        [
            {"eval_date": "2023-12-29", "arm_c_replaced": False, "arm_c_product_vt_symbol": "MA.CZCE", "return_delta": 0.0, "drawdown_improvement": 0.0},
            {"eval_date": "2024-02-29", "arm_c_replaced": False, "arm_c_product_vt_symbol": "rb.SHFE", "return_delta": 0.0, "drawdown_improvement": 0.0},
        ]
    )

    result = module._evaluate_effects(rows)

    assert result["metrics"]["median_replacement_return_delta"] is None
    assert result["metrics"]["median_replacement_drawdown_improvement"] is None
    assert result["gates"]["median_replacement_return_delta_nonnegative"] is False
    assert result["gates"]["median_replacement_drawdown_improvement_nonnegative"] is False
    assert list(result["gates"]) == module.EFFECT_GATE_KEYS
    assert all(type(value) is bool for value in result["gates"].values())
    assert result["effect_gate_pass"] is False
