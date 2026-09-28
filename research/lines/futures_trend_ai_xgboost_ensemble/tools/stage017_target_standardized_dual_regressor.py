"""Evaluate the frozen Stage017 target-standardized XGBoost hypothesis."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import platform
import shutil
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
import xgboost
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor


LINE = Path(__file__).resolve().parents[1]
OUT = LINE / "artifacts/stage017_target_standardized_dual_regressor"
CONTRACT_PATH = OUT / "training_contract.json"
PREREGISTRATION_PATH = (
    LINE / "stages/20260902_0743_stage017_target_unit_invariance_preregistration.md"
)
EXPECTED_CONTRACT_SHA256 = (
    "d7af14a69f636b56bb1f63ccd9d511a2925a1e20c6b5a98acf09edaf1572a013"
)
EXPECTED_PREREGISTRATION_SHA256 = (
    "bface574b2b6c3ef84067dcf08ee834dd74efa02376d5b9a44e231d218569fc5"
)
STAGE016_RUNNER_PATH = LINE / "tools/stage016_frozen_dual_regressor_training.py"
EXPECTED_STAGE016_RUNNER_SHA256 = (
    "b78bd1cb5e7b49ce49bff683a38f4d34656a6d88ac147fdd25bf285b38543847"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_stage016_runner_before_import() -> None:
    before = STAGE016_RUNNER_PATH.stat()
    digest = _sha256(STAGE016_RUNNER_PATH)
    after = STAGE016_RUNNER_PATH.stat()
    before_identity = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    after_identity = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if before_identity != after_identity:
        raise RuntimeError("stage017_stage016_runner_changed_while_hashing")
    if digest != EXPECTED_STAGE016_RUNNER_SHA256:
        raise RuntimeError("stage017_stage016_runner_sha_drift")


def _load_stage016():
    _verify_stage016_runner_before_import()
    spec = importlib.util.spec_from_file_location("stage016_for_stage017", STAGE016_RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable_to_load_stage016:{STAGE016_RUNNER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


s16 = _load_stage016()
MODEL_FEATURE_COLUMNS = list(s16.MODEL_FEATURE_COLUMNS)
FEATURE_PANEL_PATH = s16.FEATURE_PANEL_PATH
STAGE014_CONTRACT_PATH = s16.STAGE014_CONTRACT_PATH
DEVELOPMENT_LABELS_PATH = s16.DEVELOPMENT_LABELS_PATH
RECONCILIATION_PATH = s16.RECONCILIATION_PATH
STAGE015_REVIEW_PATH = s16.STAGE015_REVIEW_PATH
STAGE016_RESULT_DIR = s16.RESULT_DIR
STAGE016_DECISION_PATH = STAGE016_RESULT_DIR / "decision.json"
STAGE016_ARTIFACT_MANIFEST_PATH = STAGE016_RESULT_DIR / "artifact_manifest.json"
STAGE016_POSTRUN_REVIEW_PATH = (
    LINE / "reviews/20260902_stage016_postrun_independent_review.md"
)
TEST_PATH = LINE / "tests/test_stage017_target_standardized_dual_regressor.py"
FINAL_PRERUN_REVIEW_PATH = LINE / "reviews/20260902_stage017_prerun_review.md"
RUN_AUTHORIZATION_PATH = OUT / "run_authorization.json"
RESULT_DIR = OUT / "frozen_run"


def _runtime_versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scikit_learn": sklearn.__version__,
        "xgboost": xgboost.__version__,
    }


def load_frozen_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    contract_sha = _sha256(CONTRACT_PATH)
    preregistration_sha = _sha256(PREREGISTRATION_PATH)
    if contract_sha != EXPECTED_CONTRACT_SHA256:
        raise RuntimeError("stage017_training_contract_sha_drift")
    if preregistration_sha != EXPECTED_PREREGISTRATION_SHA256:
        raise RuntimeError("stage017_preregistration_sha_drift")
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if (
        contract.get("contract_status")
        != "frozen_before_stage017_target_standardized_oos_run"
    ):
        raise RuntimeError("stage017_contract_status_invalid")
    if list(contract.get("features", [])) != MODEL_FEATURE_COLUMNS:
        raise RuntimeError("stage017_contract_feature_order_drift")
    if list(contract.get("targets", [])) != [
        "return_delta",
        "drawdown_improvement",
    ]:
        raise RuntimeError("stage017_contract_targets_drift")
    transform = contract.get("target_transform", {})
    required_transform = {
        "class": "sklearn.preprocessing.StandardScaler",
        "with_mean": True,
        "with_std": True,
        "fit_scope": "each_target_each_fold_training_rows_only",
        "prediction_inverse_transform": True,
        "minimum_scale_exclusive": 0.0,
        "unit_invariance_probe_multiplier": 100.0,
        "unit_invariance_max_abs_difference": 1e-12,
    }
    if transform != required_transform:
        raise RuntimeError("stage017_target_transform_contract_drift")
    if contract.get("parameter_scan_allowed") is not False:
        raise RuntimeError("stage017_parameter_scan_not_forbidden")
    if contract.get("alternative_target_transform_allowed") is not False:
        raise RuntimeError("stage017_alternative_transform_not_forbidden")
    if contract.get("label_based_feature_selection_allowed") is not False:
        raise RuntimeError("stage017_label_feature_selection_not_forbidden")
    if contract.get("sealed_holdout", {}).get("label_values_read_allowed") is not False:
        raise RuntimeError("stage017_holdout_not_sealed")

    stage016_contract, stage016_audit = s16.load_frozen_contract()
    if contract.get("formal_release_id") != stage016_contract.get("formal_release_id"):
        raise RuntimeError("stage017_stage016_release_mismatch")
    if contract["features"] != stage016_contract["features"]:
        raise RuntimeError("stage017_stage016_features_mismatch")
    if contract["targets"] != stage016_contract["targets"]:
        raise RuntimeError("stage017_stage016_targets_mismatch")
    if (
        contract["xgb_regressor_parameters"]
        != stage016_contract["xgb_regressor_parameters"]
    ):
        raise RuntimeError("stage017_stage016_parameters_mismatch")
    if contract["development_split"] != stage016_contract["development_split"]:
        raise RuntimeError("stage017_stage016_split_mismatch")
    unchanged_selector_keys = {
        "within_month_rank_method",
        "return_percentile_weight",
        "drawdown_percentile_weight",
        "tie_break_order",
        "arm_a",
        "arm_b",
    }
    if any(
        contract["selector"].get(key) != stage016_contract["selector"].get(key)
        for key in unchanged_selector_keys
    ) or (
        contract["selector"].get("arm_c")
        != "arm_b_only_if_both_inverse_transformed_predictions_gt_zero_else_arm_a"
    ):
        raise RuntimeError("stage017_stage016_selector_mismatch")
    if contract["qualification"] != stage016_contract["qualification"]:
        raise RuntimeError("stage017_stage016_qualification_mismatch")

    actual_runtime = _runtime_versions()
    expected_runtime = contract["runtime_versions"]
    runtime_match = actual_runtime == expected_runtime
    if not runtime_match:
        raise RuntimeError(
            f"stage017_runtime_version_drift:{actual_runtime}:{expected_runtime}"
        )
    return contract, {
        "contract_path": str(CONTRACT_PATH),
        "contract_sha256": contract_sha,
        "preregistration_path": str(PREREGISTRATION_PATH),
        "preregistration_sha256": preregistration_sha,
        "runtime_versions": actual_runtime,
        "runtime_versions_match": runtime_match,
        "stage016_contract_match": True,
        "stage016_contract_audit": stage016_audit,
    }


def _authorization_bound_paths() -> dict[str, Path]:
    return {
        "runner": Path(__file__).resolve(),
        "tests": TEST_PATH,
        "contract": CONTRACT_PATH,
        "preregistration": PREREGISTRATION_PATH,
        "review": FINAL_PRERUN_REVIEW_PATH,
        "stage016_postrun_review": STAGE016_POSTRUN_REVIEW_PATH,
    }


def load_run_authorization(
    *,
    authorization_path: Path = RUN_AUTHORIZATION_PATH,
    bound_paths: dict[str, Path] | None = None,
    expected_authorization_sha256: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not expected_authorization_sha256:
        raise RuntimeError("stage017_run_authorization_sha_required")
    authorization_identity = s16.verify_file_identities(
        {"authorization": authorization_path},
        {"authorization": expected_authorization_sha256},
    )["authorization"]
    manifest = json.loads(authorization_path.read_text(encoding="utf-8"))
    if manifest.get("line_id") != "futures_trend_ai_xgboost_ensemble":
        raise RuntimeError("stage017_run_authorization_line_mismatch")
    if manifest.get("stage") != "Stage017":
        raise RuntimeError("stage017_run_authorization_stage_mismatch")
    if manifest.get("decision") != "ALLOW_FROZEN_STAGE017_RUN":
        raise RuntimeError("stage017_run_not_authorized")
    paths = bound_paths or _authorization_bound_paths()
    expected_names = {
        "runner",
        "tests",
        "contract",
        "preregistration",
        "review",
        "stage016_postrun_review",
    }
    if set(paths) != expected_names or set(manifest.get("bound_files", {})) != expected_names:
        raise RuntimeError("stage017_run_authorization_bound_file_keys")
    expected_hashes: dict[str, str] = {}
    for name, path in paths.items():
        entry = manifest["bound_files"][name]
        if Path(entry["path"]).resolve() != path.resolve():
            raise RuntimeError(f"stage017_run_authorization_path_mismatch:{name}")
        expected_hashes[name] = str(entry["sha256"])
    identities = s16.verify_file_identities(paths, expected_hashes)
    return manifest, {
        "authorization_path": str(authorization_path),
        "authorization_sha256": authorization_identity["sha256"],
        "authorization_identity": authorization_identity,
        "bound_file_identities": identities,
    }


def require_stable_run_authorization(
    *,
    before_manifest: dict[str, Any],
    before_audit: dict[str, Any],
    authorization_path: Path = RUN_AUTHORIZATION_PATH,
    bound_paths: dict[str, Path] | None = None,
    expected_authorization_sha256: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    current_manifest, current_audit = load_run_authorization(
        authorization_path=authorization_path,
        bound_paths=bound_paths,
        expected_authorization_sha256=expected_authorization_sha256,
    )
    if current_manifest != before_manifest or current_audit != before_audit:
        raise RuntimeError("stage017_run_authorization_changed")
    return current_manifest, current_audit


def fit_repeated_standardized_regressor(
    train_features: pd.DataFrame,
    train_target: np.ndarray | pd.Series,
    predict_features: pd.DataFrame,
    *,
    params: dict[str, Any],
    unit_probe_multiplier: float,
    unit_invariance_tolerance: float,
    prediction_tolerance: float,
) -> dict[str, Any]:
    if list(train_features.columns) != list(predict_features.columns):
        raise RuntimeError("stage017_feature_order_mismatch")
    target = np.asarray(train_target, dtype="float64").reshape(-1, 1)
    if len(target) != len(train_features) or not len(target):
        raise RuntimeError("stage017_train_shape")
    if not np.isfinite(target).all():
        raise RuntimeError("stage017_target_nonfinite")
    if not np.isfinite(unit_probe_multiplier) or unit_probe_multiplier <= 0.0:
        raise RuntimeError("stage017_unit_probe_multiplier_invalid")

    base_scaler = StandardScaler(with_mean=True, with_std=True).fit(target)
    if (
        not np.isfinite(base_scaler.mean_[0])
        or not np.isfinite(base_scaler.var_[0])
        or not np.isfinite(base_scaler.scale_[0])
        or float(base_scaler.var_[0]) <= 0.0
        or float(base_scaler.scale_[0]) <= 0.0
    ):
        raise RuntimeError("stage017_target_scaler_invalid")
    scaled_target = base_scaler.transform(target).ravel()
    probe_scaler = StandardScaler(with_mean=True, with_std=True).fit(
        target * unit_probe_multiplier
    )
    probe_scaled = probe_scaler.transform(target * unit_probe_multiplier).ravel()
    unit_difference = float(
        np.max(np.abs(scaled_target - probe_scaled), initial=0.0)
    )
    if unit_difference > unit_invariance_tolerance:
        raise RuntimeError(f"stage017_target_unit_invariance_failed:{unit_difference}")

    models: list[XGBRegressor] = []
    scalers: list[StandardScaler] = []
    standardized_predictions: list[np.ndarray] = []
    inverse_predictions: list[np.ndarray] = []
    raw_models: list[bytes] = []
    for _ in range(2):
        scaler = StandardScaler(with_mean=True, with_std=True).fit(target)
        scale = float(scaler.scale_[0])
        mean = float(scaler.mean_[0])
        variance = float(scaler.var_[0])
        if (
            not np.isfinite(mean)
            or not np.isfinite(scale)
            or not np.isfinite(variance)
            or variance <= 0.0
            or scale <= 0.0
        ):
            raise RuntimeError("stage017_target_scaler_invalid")
        transformed = scaler.transform(target).ravel()
        model = XGBRegressor(**params)
        model.fit(train_features, transformed, verbose=False)
        prediction_z = np.asarray(model.predict(predict_features), dtype="float64")
        if not np.isfinite(prediction_z).all():
            raise RuntimeError("stage017_standardized_prediction_nonfinite")
        prediction = scaler.inverse_transform(prediction_z.reshape(-1, 1)).ravel()
        if not np.isfinite(prediction).all():
            raise RuntimeError("stage017_inverse_prediction_nonfinite")
        models.append(model)
        scalers.append(scaler)
        standardized_predictions.append(prediction_z)
        inverse_predictions.append(prediction)
        raw_models.append(bytes(model.get_booster().save_raw(raw_format="ubj")))

    standardized_difference = float(
        np.max(
            np.abs(standardized_predictions[0] - standardized_predictions[1]),
            initial=0.0,
        )
    )
    inverse_difference = float(
        np.max(np.abs(inverse_predictions[0] - inverse_predictions[1]), initial=0.0)
    )
    if standardized_difference > prediction_tolerance:
        raise RuntimeError(
            f"stage017_standardized_prediction_nondeterministic:{standardized_difference}"
        )
    if inverse_difference > prediction_tolerance:
        raise RuntimeError(f"stage017_inverse_prediction_nondeterministic:{inverse_difference}")
    hashes = [hashlib.sha256(payload).hexdigest() for payload in raw_models]
    if hashes[0] != hashes[1]:
        raise RuntimeError("stage017_model_bytes_nondeterministic")
    if (
        not np.array_equal(scalers[0].mean_, scalers[1].mean_)
        or not np.array_equal(scalers[0].scale_, scalers[1].scale_)
        or not np.array_equal(scalers[0].var_, scalers[1].var_)
    ):
        raise RuntimeError("stage017_scaler_nondeterministic")

    tree_frame = models[0].get_booster().trees_to_dataframe()
    split_nodes = int(tree_frame["Feature"].ne("Leaf").sum())
    leaf_nodes = int(tree_frame["Feature"].eq("Leaf").sum())
    tree_count = int(tree_frame["Tree"].nunique())
    scaler_payloads = [
        {
            "class": "sklearn.preprocessing.StandardScaler",
            "with_mean": True,
            "with_std": True,
            "train_rows": int(len(target)),
            "mean": float(scaler.mean_[0]),
            "scale": float(scaler.scale_[0]),
            "var": float(scaler.var_[0]),
            "train_target_mean": float(np.mean(target)),
            "train_target_population_std": float(np.std(target, ddof=0)),
            "unit_probe_multiplier": float(unit_probe_multiplier),
            "unit_invariance_max_abs_difference": unit_difference,
        }
        for scaler in scalers
    ]
    scaler_bytes = [
        (
            json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        for payload in scaler_payloads
    ]
    scaler_hashes = [
        hashlib.sha256(payload).hexdigest() for payload in scaler_bytes
    ]
    if scaler_bytes[0] != scaler_bytes[1] or scaler_hashes[0] != scaler_hashes[1]:
        raise RuntimeError("stage017_scaler_bytes_nondeterministic")
    return {
        "model": models[0],
        "predictions_standardized": standardized_predictions[0],
        "predictions": inverse_predictions[0],
        "standardized_prediction_max_abs_difference": standardized_difference,
        "inverse_prediction_max_abs_difference": inverse_difference,
        "unit_invariance_max_abs_difference": unit_difference,
        "model_raw": raw_models[0],
        "repeat_model_raw": raw_models[1],
        "model_sha256": hashes[0],
        "repeat_model_sha256": hashes[1],
        "scaler_payload": scaler_payloads[0],
        "scaler_raw": scaler_bytes[0],
        "repeat_scaler_raw": scaler_bytes[1],
        "scaler_sha256": scaler_hashes[0],
        "repeat_scaler_sha256": scaler_hashes[1],
        "scaler_mean": float(scalers[0].mean_[0]),
        "scaler_scale": float(scalers[0].scale_[0]),
        "tree_count": tree_count,
        "split_nodes": split_nodes,
        "leaf_nodes": leaf_nodes,
    }


def train_oos_standardized_dual_regressors(
    panel: pd.DataFrame,
    folds: list[Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    features = list(contract["features"])
    if features != MODEL_FEATURE_COLUMNS:
        raise RuntimeError("stage017_training_feature_contract_mismatch")
    if list(contract["targets"]) != ["return_delta", "drawdown_improvement"]:
        raise RuntimeError("stage017_training_target_contract_mismatch")
    params = dict(contract["xgb_regressor_parameters"])
    transform = contract["target_transform"]
    determinism = contract["determinism"]
    prediction_tolerance = min(
        float(determinism["maximum_standardized_prediction_abs_difference"]),
        float(determinism["maximum_inverse_prediction_abs_difference"]),
    )

    prediction_frames: list[pd.DataFrame] = []
    selections: list[dict[str, Any]] = []
    fold_rows: list[dict[str, Any]] = []
    model_payloads: dict[str, bytes] = {}
    scaler_payloads: dict[str, bytes] = {}
    for fold in folds:
        train = panel.loc[fold.train_indices].copy()
        test = panel.loc[fold.test_indices].copy()
        pit_invalid = pd.to_datetime(train["next_eval_date"]).dt.normalize().gt(
            fold.test_date
        ) | pd.to_datetime(train["eval_date"]).dt.normalize().ge(fold.test_date)
        pit_violation_rows = int(pit_invalid.sum())
        if pit_violation_rows:
            raise RuntimeError(f"stage017_fold_pit_violation:{fold.test_date.date()}")

        fitted: dict[str, dict[str, Any]] = {}
        for target in ("return_delta", "drawdown_improvement"):
            fitted[target] = fit_repeated_standardized_regressor(
                train.loc[:, features],
                train[target],
                test.loc[:, features],
                params=params,
                unit_probe_multiplier=float(
                    transform["unit_invariance_probe_multiplier"]
                ),
                unit_invariance_tolerance=float(
                    transform["unit_invariance_max_abs_difference"]
                ),
                prediction_tolerance=prediction_tolerance,
            )
            stem = f"{fold.test_date:%Y%m%d}_{target}"
            model_payloads[f"{stem}.ubj"] = fitted[target]["model_raw"]
            scaler_payloads[f"{stem}_scaler.json"] = fitted[target]["scaler_raw"]

        month = test.copy()
        month["predicted_return_delta_standardized"] = fitted["return_delta"][
            "predictions_standardized"
        ]
        month["predicted_drawdown_improvement_standardized"] = fitted[
            "drawdown_improvement"
        ]["predictions_standardized"]
        month["predicted_return_delta"] = fitted["return_delta"]["predictions"]
        month["predicted_drawdown_improvement"] = fitted[
            "drawdown_improvement"
        ]["predictions"]
        scored, selection = s16.score_and_select_month(month)
        scored["train_months"] = len(fold.train_dates)
        scored["train_rows"] = len(train)
        scored["train_label_end_max"] = fold.train_label_end_max.date().isoformat()
        prediction_frames.append(scored)

        def selected_row(rank: int) -> pd.Series:
            selected = scored[scored["candidate_rank"].eq(rank)]
            if len(selected) != 1:
                raise RuntimeError(f"stage017_selected_rank_shape:{rank}")
            return selected.iloc[0]

        arm_a = selected_row(int(selection["arm_a_candidate_rank"]))
        arm_b = selected_row(int(selection["arm_b_candidate_rank"]))
        arm_c = selected_row(int(selection["arm_c_candidate_rank"]))
        for arm_name, row in (("arm_a", arm_a), ("arm_b", arm_b), ("arm_c", arm_c)):
            selection[f"{arm_name}_realized_return_delta"] = float(row["return_delta"])
            selection[f"{arm_name}_realized_drawdown_improvement"] = float(
                row["drawdown_improvement"]
            )
            for optional in ("net_pnl_delta", "slippage_delta", "trade_count_delta"):
                if optional in row.index:
                    selection[f"{arm_name}_realized_{optional}"] = float(row[optional])
        selection["train_months"] = len(fold.train_dates)
        selection["train_rows"] = len(train)
        selection["train_label_end_max"] = fold.train_label_end_max.date().isoformat()
        selections.append(selection)

        return_fit = fitted["return_delta"]
        drawdown_fit = fitted["drawdown_improvement"]
        fold_rows.append(
            {
                "test_eval_date": fold.test_date.date().isoformat(),
                "train_months": len(fold.train_dates),
                "train_rows": len(train),
                "test_rows": len(test),
                "train_eval_date_min": min(fold.train_dates).date().isoformat(),
                "train_eval_date_max": max(fold.train_dates).date().isoformat(),
                "train_label_end_max": fold.train_label_end_max.date().isoformat(),
                "pit_violation_rows": pit_violation_rows,
                "return_prediction_repeat_max_abs_difference": return_fit[
                    "inverse_prediction_max_abs_difference"
                ],
                "drawdown_prediction_repeat_max_abs_difference": drawdown_fit[
                    "inverse_prediction_max_abs_difference"
                ],
                "return_standardized_prediction_repeat_max_abs_difference": return_fit[
                    "standardized_prediction_max_abs_difference"
                ],
                "drawdown_standardized_prediction_repeat_max_abs_difference": drawdown_fit[
                    "standardized_prediction_max_abs_difference"
                ],
                "unit_invariance_max_abs_difference": max(
                    return_fit["unit_invariance_max_abs_difference"],
                    drawdown_fit["unit_invariance_max_abs_difference"],
                ),
                "return_model_sha256": return_fit["model_sha256"],
                "return_repeat_model_sha256": return_fit["repeat_model_sha256"],
                "drawdown_model_sha256": drawdown_fit["model_sha256"],
                "drawdown_repeat_model_sha256": drawdown_fit[
                    "repeat_model_sha256"
                ],
                "return_scaler_sha256": return_fit["scaler_sha256"],
                "return_repeat_scaler_sha256": return_fit[
                    "repeat_scaler_sha256"
                ],
                "drawdown_scaler_sha256": drawdown_fit["scaler_sha256"],
                "drawdown_repeat_scaler_sha256": drawdown_fit[
                    "repeat_scaler_sha256"
                ],
                "return_scaler_mean": return_fit["scaler_mean"],
                "return_scaler_scale": return_fit["scaler_scale"],
                "drawdown_scaler_mean": drawdown_fit["scaler_mean"],
                "drawdown_scaler_scale": drawdown_fit["scaler_scale"],
                "return_tree_count": return_fit["tree_count"],
                "drawdown_tree_count": drawdown_fit["tree_count"],
                "return_split_nodes": return_fit["split_nodes"],
                "drawdown_split_nodes": drawdown_fit["split_nodes"],
                "split_nodes_total": return_fit["split_nodes"]
                + drawdown_fit["split_nodes"],
                "return_leaf_nodes": return_fit["leaf_nodes"],
                "drawdown_leaf_nodes": drawdown_fit["leaf_nodes"],
            }
        )

    predictions = pd.concat(prediction_frames, ignore_index=True).sort_values(
        ["eval_date", "candidate_rank"], kind="mergesort"
    )
    predictions.reset_index(drop=True, inplace=True)
    monthly = pd.DataFrame(selections).sort_values("eval_date", kind="mergesort")
    monthly.reset_index(drop=True, inplace=True)
    fold_audit = pd.DataFrame(fold_rows).sort_values(
        "test_eval_date", kind="mergesort"
    )
    fold_audit.reset_index(drop=True, inplace=True)
    return {
        "predictions": predictions,
        "monthly_selections": monthly,
        "fold_audit": fold_audit,
        "model_payloads": model_payloads,
        "scaler_payloads": scaler_payloads,
    }


def evaluate_technical_qualification(
    *,
    input_audit: dict[str, Any],
    panel_audit: dict[str, Any],
    folds: list[Any],
    training_result: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    compatibility_contract = dict(contract)
    compatibility_contract["determinism"] = {
        "maximum_prediction_abs_difference": float(
            contract["determinism"][
                "maximum_inverse_prediction_abs_difference"
            ]
        )
    }
    base = s16.evaluate_technical_qualification(
        input_audit=input_audit,
        panel_audit=panel_audit,
        folds=folds,
        training_result=training_result,
        contract=compatibility_contract,
    )
    fold_audit = training_result["fold_audit"]
    scalers = training_result.get("scaler_payloads", {})
    models = training_result.get("model_payloads", {})
    fold_count = int(contract["development_split"]["oos_fold_count"])
    unit_tolerance = float(
        contract["target_transform"]["unit_invariance_max_abs_difference"]
    )
    standardized_tolerance = float(
        contract["determinism"][
            "maximum_standardized_prediction_abs_difference"
        ]
    )

    standardized_columns = [
        "return_standardized_prediction_repeat_max_abs_difference",
        "drawdown_standardized_prediction_repeat_max_abs_difference",
    ]
    standardized_max = float(
        fold_audit[standardized_columns]
        .apply(pd.to_numeric, errors="raise")
        .to_numpy(float)
        .max(initial=0.0)
    )
    unit_max = float(
        pd.to_numeric(
            fold_audit["unit_invariance_max_abs_difference"], errors="raise"
        ).max()
    )

    expected_scalers: dict[str, tuple[Any, str]] = {}
    for row in fold_audit.itertuples(index=False):
        date_stem = str(row.test_eval_date).replace("-", "")
        for target in ("return_delta", "drawdown_improvement"):
            expected_scalers[f"{date_stem}_{target}_scaler.json"] = (row, target)
    scaler_names_exact = set(scalers) == set(expected_scalers)
    scaler_metadata_valid = scaler_names_exact
    scaler_hash_determinism = scaler_names_exact
    if scaler_names_exact:
        for name, (row, target) in expected_scalers.items():
            try:
                raw = scalers[name]
                payload = json.loads(raw.decode("utf-8"))
                prefix = "return" if target == "return_delta" else "drawdown"
                actual_hash = hashlib.sha256(raw).hexdigest()
                expected_hash = str(getattr(row, f"{prefix}_scaler_sha256"))
                repeat_hash = str(
                    getattr(row, f"{prefix}_repeat_scaler_sha256")
                )
                mean = float(payload["mean"])
                scale = float(payload["scale"])
                variance = float(payload["var"])
                target_mean = float(payload["train_target_mean"])
                target_std = float(payload["train_target_population_std"])
                scaler_metadata_valid = scaler_metadata_valid and bool(
                    payload["class"]
                    == "sklearn.preprocessing.StandardScaler"
                    and payload["with_mean"] is True
                    and payload["with_std"] is True
                    and int(payload["train_rows"]) == int(row.train_rows)
                    and np.isfinite([mean, scale, variance, target_mean, target_std]).all()
                    and scale > 0.0
                    and variance > 0.0
                    and target_std > 0.0
                    and np.isclose(mean, target_mean, rtol=0.0, atol=1e-15)
                    and np.isclose(scale, target_std, rtol=1e-12, atol=1e-15)
                    and np.isclose(scale * scale, variance, rtol=1e-12, atol=1e-15)
                    and float(payload["unit_probe_multiplier"])
                    == float(
                        contract["target_transform"][
                            "unit_invariance_probe_multiplier"
                        ]
                    )
                    and float(payload["unit_invariance_max_abs_difference"])
                    <= unit_tolerance
                    and actual_hash == expected_hash
                )
                scaler_hash_determinism = scaler_hash_determinism and bool(
                    actual_hash == repeat_hash
                )
            except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
                scaler_metadata_valid = False
                scaler_hash_determinism = False

    expected_models = {
        name.removesuffix("_scaler.json") + ".ubj" for name in expected_scalers
    }
    model_scaler_names_aligned = set(models) == expected_models
    structure_columns = [
        "return_tree_count",
        "drawdown_tree_count",
        "return_split_nodes",
        "drawdown_split_nodes",
        "return_leaf_nodes",
        "drawdown_leaf_nodes",
    ]
    structure = fold_audit[structure_columns].apply(pd.to_numeric, errors="raise")
    expected_trees = int(contract["xgb_regressor_parameters"]["n_estimators"])
    tree_structure_recorded = bool(
        structure[["return_tree_count", "drawdown_tree_count"]]
        .eq(expected_trees)
        .all()
        .all()
        and structure[["return_split_nodes", "drawdown_split_nodes"]]
        .ge(0)
        .all()
        .all()
        and structure[["return_leaf_nodes", "drawdown_leaf_nodes"]]
        .gt(0)
        .all()
        .all()
    )

    gates = dict(base["gates"])
    gates.update(
        {
            "stage016_dependency_match": bool(
                input_audit.get("stage016_dependency_match")
            ),
            "two_scalers_per_fold": len(scalers) == 2 * fold_count,
            "model_scaler_names_aligned": model_scaler_names_aligned,
            "target_scaler_train_scope_and_metadata": scaler_metadata_valid,
            "target_scaler_byte_determinism": scaler_hash_determinism,
            "target_unit_invariance": unit_max <= unit_tolerance,
            "standardized_prediction_determinism": standardized_max
            <= standardized_tolerance,
            "tree_structure_recorded": tree_structure_recorded,
        }
    )
    return {
        **{key: value for key, value in base.items() if key not in {"passed", "gates"}},
        "passed": bool(all(gates.values())),
        "gates": {key: bool(value) for key, value in gates.items()},
        "scaler_count": int(len(scalers)),
        "standardized_prediction_repeat_max_abs_difference": standardized_max,
        "unit_invariance_max_abs_difference": unit_max,
        "split_nodes_total": int(
            pd.to_numeric(fold_audit["split_nodes_total"], errors="raise").sum()
        ),
        "split_nodes_is_effect_gate": False,
    }


def stage017_decision(*, technical_pass: bool, effect_pass: bool) -> str:
    if not technical_pass:
        return "stage017_contract_or_unit_transform_invalid_stop"
    if not effect_pass:
        return "stage017_target_standardized_oos_fail_stop_feature_label_family"
    return "stage017_target_standardized_oos_pass_allow_development_true_engine_ac"


def resolve_stage017_outcome(
    *,
    technical: dict[str, Any],
    monthly_selections: pd.DataFrame,
    contract: dict[str, Any],
    effect_evaluator: Any = None,
) -> tuple[dict[str, Any] | None, str]:
    if not bool(technical.get("passed")):
        return None, stage017_decision(technical_pass=False, effect_pass=False)
    evaluator = effect_evaluator or s16.evaluate_effect_qualification
    effect = evaluator(monthly_selections, contract)
    return effect, stage017_decision(
        technical_pass=True, effect_pass=bool(effect["passed"])
    )


def _fsync_file(path: Path) -> None:
    with path.open("rb") as stream:
        os.fsync(stream.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def publish_artifact_bundle(
    result_dir: Path,
    *,
    csv_frames: dict[str, pd.DataFrame],
    json_payloads: dict[str, Any],
    text_payloads: dict[str, str],
    model_payloads: dict[str, bytes],
    scaler_payloads: dict[str, bytes],
) -> dict[str, dict[str, Any]]:
    if result_dir.exists():
        raise RuntimeError(f"stage017_result_already_exists:{result_dir}")
    result_dir.parent.mkdir(parents=True, exist_ok=True)
    partial = Path(
        tempfile.mkdtemp(
            prefix=f".{result_dir.name}.partial.{os.getpid()}.",
            dir=result_dir.parent,
        )
    )
    renamed = False
    try:
        models_dir = partial / "models"
        scalers_dir = partial / "scalers"
        models_dir.mkdir()
        scalers_dir.mkdir()
        for name, frame in csv_frames.items():
            if Path(name).name != name:
                raise RuntimeError(f"stage017_invalid_csv_name:{name}")
            frame.to_csv(partial / name, index=False, lineterminator="\n")
        for name, payload in json_payloads.items():
            if Path(name).name != name:
                raise RuntimeError(f"stage017_invalid_json_name:{name}")
            (partial / name).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
        for name, payload in text_payloads.items():
            if Path(name).name != name:
                raise RuntimeError(f"stage017_invalid_text_name:{name}")
            (partial / name).write_text(payload, encoding="utf-8")
        for name, payload in model_payloads.items():
            if Path(name).name != name:
                raise RuntimeError(f"stage017_invalid_model_name:{name}")
            (models_dir / name).write_bytes(payload)
        for name, payload in scaler_payloads.items():
            if Path(name).name != name:
                raise RuntimeError(f"stage017_invalid_scaler_name:{name}")
            (scalers_dir / name).write_bytes(payload)

        artifact_identities: dict[str, dict[str, Any]] = {}
        for path in sorted(candidate for candidate in partial.rglob("*") if candidate.is_file()):
            relative = path.relative_to(partial).as_posix()
            _fsync_file(path)
            artifact_identities[relative] = {
                "size": int(path.stat().st_size),
                "sha256": _sha256(path),
            }
        manifest_path = partial / "artifact_manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "stage": "Stage017",
                    "manifest_semantics": "all_bundle_files_except_this_manifest",
                    "artifacts": artifact_identities,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        _fsync_file(manifest_path)
        for directory in (models_dir, scalers_dir, partial):
            _fsync_directory(directory)
        os.rename(partial, result_dir)
        renamed = True
        _fsync_directory(result_dir.parent)
        published: dict[str, dict[str, Any]] = {}
        for path in sorted(candidate for candidate in result_dir.rglob("*") if candidate.is_file()):
            relative = path.relative_to(result_dir).as_posix()
            published[relative] = {
                "size": int(path.stat().st_size),
                "sha256": _sha256(path),
            }
        return published
    except BaseException as error:
        if partial.exists():
            shutil.rmtree(partial)
        if renamed and result_dir.exists():
            quarantine = result_dir.parent / (
                f".{result_dir.name}.quarantined.{os.getpid()}.{time.time_ns()}"
            )
            try:
                os.rename(result_dir, quarantine)
            except BaseException as quarantine_error:
                raise RuntimeError(
                    f"stage017_post_rename_publish_uncertain:{result_dir}"
                ) from quarantine_error
            try:
                _fsync_directory(result_dir.parent)
            except OSError:
                pass
            raise RuntimeError(
                f"stage017_post_rename_publish_quarantined:{quarantine}"
            ) from error
        raise


def _input_paths() -> dict[str, Path]:
    return {
        "feature_panel": FEATURE_PANEL_PATH,
        "feature_contract": STAGE014_CONTRACT_PATH,
        "development_labels": DEVELOPMENT_LABELS_PATH,
        "reconciliation": RECONCILIATION_PATH,
        "stage015_review": STAGE015_REVIEW_PATH,
        "stage016_decision": STAGE016_DECISION_PATH,
        "stage016_artifact_manifest": STAGE016_ARTIFACT_MANIFEST_PATH,
        "stage016_postrun_review": STAGE016_POSTRUN_REVIEW_PATH,
        "stage016_runner": STAGE016_RUNNER_PATH,
    }


def _validate_upstream_contracts(contract: dict[str, Any]) -> None:
    stage014 = json.loads(STAGE014_CONTRACT_PATH.read_text(encoding="utf-8"))
    s16._validate_stage014_contract(stage014, contract)
    decision = json.loads(STAGE016_DECISION_PATH.read_text(encoding="utf-8"))
    expected_decision_fields = {
        "line_id": "futures_trend_ai_xgboost_ensemble",
        "stage": "Stage016",
        "decision": "stage016_development_oos_proxy_fail_stop_no_holdout",
        "passed": False,
        "technical_passed": True,
        "effect_evaluated": True,
        "effect_passed": False,
        "allows_development_true_engine_ac": False,
        "allows_sealed_holdout_labels": False,
        "allows_production_change": False,
        "sealed_holdout_label_values_read": False,
    }
    if any(decision.get(key) != value for key, value in expected_decision_fields.items()):
        raise RuntimeError("stage017_stage016_decision_semantics_mismatch")
    artifact_manifest = json.loads(
        STAGE016_ARTIFACT_MANIFEST_PATH.read_text(encoding="utf-8")
    )
    if artifact_manifest.get("stage") != "Stage016" or not isinstance(
        artifact_manifest.get("artifacts"), dict
    ):
        raise RuntimeError("stage017_stage016_artifact_manifest_invalid")
    review = STAGE016_POSTRUN_REVIEW_PATH.read_text(encoding="utf-8")
    required_review_text = (
        "stage016_development_oos_proxy_fail_stop_no_holdout",
        "P0=0 / P1=0 / P2=0",
        "若仍探索XGBoost，只能另立具有新结构性理由的假设",
    )
    if any(text not in review for text in required_review_text):
        raise RuntimeError("stage017_stage016_postrun_review_invalid")


def _model_manifest(training_result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    fold_by_date = {
        str(row.test_eval_date).replace("-", ""): row
        for row in training_result["fold_audit"].itertuples(index=False)
    }
    manifest: dict[str, dict[str, Any]] = {}
    for name, payload in sorted(training_result["model_payloads"].items()):
        date_stem, target = name.removesuffix(".ubj").split("_", maxsplit=1)
        row = fold_by_date[date_stem]
        prefix = "return" if target == "return_delta" else "drawdown"
        manifest[name] = {
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "tree_count": int(getattr(row, f"{prefix}_tree_count")),
            "split_nodes": int(getattr(row, f"{prefix}_split_nodes")),
            "leaf_nodes": int(getattr(row, f"{prefix}_leaf_nodes")),
        }
    return manifest


def _scaler_manifest(training_result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    manifest: dict[str, dict[str, Any]] = {}
    for name, payload in sorted(training_result["scaler_payloads"].items()):
        metadata = json.loads(payload.decode("utf-8"))
        manifest[name] = {
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            **metadata,
        }
    return manifest


def _build_report(
    *,
    decision: str,
    technical: dict[str, Any],
    effect: dict[str, Any] | None,
) -> str:
    technical_lines = "\n".join(
        f"- `{name}`: `{value}`" for name, value in technical["gates"].items()
    )
    structure_line = (
        f"- 模型分裂节点合计：`{technical['split_nodes_total']}`；"
        "该值仅作结构诊断，不是效果门。\n"
    )
    if effect is None:
        return (
            "# Stage017 目标标准化双XGBoost技术失败审计\n\n"
            f"- 决策：`{decision}`。\n"
            "- 技术门未通过，效果评价未执行。\n"
            "- 未发布OOS预测、月度选择、模型、scaler或任何真实效果值。\n"
            "- 未读取sealed holdout标签、未修改生产目录、未连接CTP、未调用订单API。\n\n"
            f"{structure_line}\n"
            "## 技术门\n\n"
            f"{technical_lines}\n\n"
            "## 反思\n\n"
            "- 过拟合判断：本次不形成效果结论；修复实现错误前禁止观察development效果。\n"
            "- 继续价值：仅允许修复合同实现错误并重新独立审查；不得改变冻结研究规格。\n"
        )
    effect_lines = "\n".join(
        f"- `{name}`: `{value}`" for name, value in effect["gates"].items()
    )
    yearly_return = ", ".join(
        f"{year}={value:.12g}"
        for year, value in effect["yearly_return_delta"].items()
    )
    yearly_drawdown = ", ".join(
        f"{year}={value:.12g}"
        for year, value in effect["yearly_drawdown_improvement"].items()
    )
    continue_line = (
        "- 继续价值：九项效果门全过，仅允许进入一次development真实账户引擎A/C；仍不授权holdout或上线。\n"
        if effect["passed"]
        else "- 继续价值：当前九特征/账户边际标签XGBoost族到此停止，不再更换scaler、损失、树参数、阈值、rank、年份或品种，也不读取holdout。\n"
    )
    return (
        "# Stage017 目标标准化双XGBoost development OOS评估\n\n"
        f"- 决策：`{decision}`。\n"
        f"- 技术门：`{technical['passed']}`；效果门：`{effect['passed']}`。\n"
        "- 唯一结构变化是每折、每目标仅用训练标签拟合StandardScaler；XGBoost参数、九特征、PIT、selector和九项效果门均与Stage016保持一致。\n"
        "- A为线上逻辑回归正式rank10；C仅在XGBoost同一候选的两项逆变换预测均为正时替换第10席。\n"
        "- 未读取sealed holdout标签、未修改生产目录、未连接CTP、未调用订单API。\n\n"
        "## Development OOS结果\n\n"
        f"- OOS月份：`{effect['oos_months']}`；C实际替换：`{effect['replacement_months']}`；替换年份：`{effect['replacement_years']}`。\n"
        f"- 账户边际收益增量合计：`{effect['total_return_delta']:.12g}`；剔除最好月：`{effect['leave_best_out_return_delta']:.12g}`。\n"
        f"- 账户边际回撤改善合计：`{effect['total_drawdown_improvement']:.12g}`；剔除最好月：`{effect['leave_best_out_drawdown_improvement']:.12g}`。\n"
        f"- 分年收益增量：{yearly_return}。\n"
        f"- 分年回撤改善：{yearly_drawdown}。\n"
        f"- 实际替换月双目标联合命中率：`{effect['active_joint_positive_rate']:.6%}`。\n"
        f"{structure_line}\n"
        "这些数值是15个月互斥账户边际标签的资格代理，不是可复利策略曲线；本阶段不发布期末权益、总收益、组合最大回撤、Sharpe、总滑点、总交易次数或胜率。\n\n"
        "## 技术门\n\n"
        f"{technical_lines}\n\n"
        "## 效果门\n\n"
        f"{effect_lines}\n\n"
        "## 反思\n\n"
        "- 过拟合风险：高。Stage016结果已知，但Stage017只验证预注册的单位不变性结构，未扫描参数、transformer、特征或门槛。\n"
        f"{continue_line}"
    )


def main() -> None:
    if RESULT_DIR.exists():
        raise RuntimeError(f"stage017_result_already_exists:{RESULT_DIR}")
    authorization_sha = os.environ.get("STAGE017_RUN_AUTHORIZATION_SHA256")
    authorization, authorization_audit_before = load_run_authorization(
        expected_authorization_sha256=authorization_sha
    )
    contract, contract_audit = load_frozen_contract()
    input_paths = _input_paths()
    input_identities_before = s16.verify_file_identities(
        input_paths, contract["input_sha256"]
    )
    _validate_upstream_contracts(contract)
    input_audit = {
        **contract_audit,
        "all_input_identities_verified": True,
        "stage014_contract_match": True,
        "stage016_dependency_match": True,
        "input_identities": input_identities_before,
    }

    feature_frame = pd.read_csv(FEATURE_PANEL_PATH, encoding="utf-8-sig")
    label_frame = pd.read_csv(DEVELOPMENT_LABELS_PATH, float_precision="round_trip")
    reconciliation_frame = pd.read_csv(
        RECONCILIATION_PATH, float_precision="round_trip"
    )
    panel, panel_audit = s16.build_joined_development_panel(
        feature_frame, label_frame, reconciliation_frame, contract
    )
    split = contract["development_split"]
    folds = s16.build_pit_folds(
        panel,
        min_train_months=int(split["minimum_train_months"]),
        rows_per_month=int(split["rows_per_month"]),
    )
    training_result = train_oos_standardized_dual_regressors(
        panel, folds, contract
    )

    input_identities_after = s16.verify_file_identities(
        input_paths, contract["input_sha256"]
    )
    if input_identities_before != input_identities_after:
        raise RuntimeError("stage017_input_identity_changed_during_training")
    contract_after, contract_audit_after = load_frozen_contract()
    if contract != contract_after or contract_audit != contract_audit_after:
        raise RuntimeError("stage017_contract_changed_during_training")
    authorization_after, authorization_audit_after = require_stable_run_authorization(
        before_manifest=authorization,
        before_audit=authorization_audit_before,
        expected_authorization_sha256=authorization_sha,
    )

    technical = evaluate_technical_qualification(
        input_audit=input_audit,
        panel_audit=panel_audit,
        folds=folds,
        training_result=training_result,
        contract=contract,
    )
    effect, decision_name = resolve_stage017_outcome(
        technical=technical,
        monthly_selections=training_result["monthly_selections"],
        contract=contract,
    )
    authorization_final, authorization_audit_final = require_stable_run_authorization(
        before_manifest=authorization,
        before_audit=authorization_audit_before,
        expected_authorization_sha256=authorization_sha,
    )
    if (
        authorization_after != authorization_final
        or authorization_audit_after != authorization_audit_final
    ):
        raise RuntimeError(
            "stage017_run_authorization_changed_during_effect_evaluation"
        )
    input_identities_final = s16.verify_file_identities(
        input_paths, contract["input_sha256"]
    )
    if input_identities_before != input_identities_final:
        raise RuntimeError(
            "stage017_input_identity_changed_during_effect_evaluation"
        )
    contract_final, contract_audit_final = load_frozen_contract()
    if contract != contract_final or contract_audit != contract_audit_final:
        raise RuntimeError("stage017_contract_changed_during_effect_evaluation")

    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    runner_identity = {
        "path": str(Path(__file__).resolve()),
        "sha256": _sha256(Path(__file__).resolve()),
    }
    tests_identity = {"path": str(TEST_PATH), "sha256": _sha256(TEST_PATH)}
    models = _model_manifest(training_result)
    scalers = _scaler_manifest(training_result)
    decision_payload = {
        "line_id": "futures_trend_ai_xgboost_ensemble",
        "stage": "Stage017",
        "generated_at": generated_at,
        "decision": decision_name,
        "passed": bool(technical["passed"] and effect and effect["passed"]),
        "technical_passed": bool(technical["passed"]),
        "effect_evaluated": effect is not None,
        "effect_passed": None if effect is None else bool(effect["passed"]),
        "allows_development_true_engine_ac": bool(
            technical["passed"] and effect and effect["passed"]
        ),
        "stops_current_feature_label_family": bool(
            technical["passed"] and effect is not None and not effect["passed"]
        ),
        "allows_sealed_holdout_labels": False,
        "allows_production_change": False,
        "sealed_holdout_label_values_read": False,
        "trains_model": True,
        "parameter_scan_count": 0,
        "target_transform_scan_count": 0,
        "ctp_connected": False,
        "order_api_called_count": 0,
    }
    run_receipt = {
        "generated_at": generated_at,
        "contract": contract_audit,
        "run_authorization": authorization_audit_before,
        "run_authorization_stable": True,
        "runner": runner_identity,
        "tests": tests_identity,
        "input_identities_before": input_identities_before,
        "input_identities_after": input_identities_after,
        "input_identities_final": input_identities_final,
        "input_identity_stable": True,
        "panel_audit": panel_audit,
        "trained_model_count": len(models),
        "fitted_scaler_count": len(scalers),
        "models_and_scalers_published": effect is not None,
        "effect_evaluated": effect is not None,
        "sealed_holdout_label_values_read": False,
        "production_modified": False,
        "ctp_connected": False,
        "order_api_called_count": 0,
    }
    csv_frames = {"fold_audit.csv": training_result["fold_audit"]}
    json_payloads = {
        "input_audit.json": input_audit,
        "panel_audit.json": panel_audit,
        "technical_qualification.json": technical,
        "decision.json": decision_payload,
        "run_receipt.json": run_receipt,
    }
    published_models: dict[str, bytes] = {}
    published_scalers: dict[str, bytes] = {}
    if effect is not None:
        csv_frames.update(
            {
                "oos_predictions.csv": training_result["predictions"],
                "monthly_arm_selections.csv": training_result[
                    "monthly_selections"
                ],
            }
        )
        json_payloads.update(
            {
                "effect_qualification.json": effect,
                "model_manifest.json": models,
                "scaler_manifest.json": scalers,
            }
        )
        published_models = training_result["model_payloads"]
        published_scalers = training_result["scaler_payloads"]
    output_identities = publish_artifact_bundle(
        RESULT_DIR,
        csv_frames=csv_frames,
        json_payloads=json_payloads,
        text_payloads={
            "report.md": _build_report(
                decision=decision_name,
                technical=technical,
                effect=effect,
            )
        },
        model_payloads=published_models,
        scaler_payloads=published_scalers,
    )
    print(
        json.dumps(
            {
                "decision": decision_name,
                "technical_passed": technical["passed"],
                "effect_passed": None if effect is None else effect["passed"],
                "result_dir": str(RESULT_DIR),
                "published_files": len(output_identities),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
