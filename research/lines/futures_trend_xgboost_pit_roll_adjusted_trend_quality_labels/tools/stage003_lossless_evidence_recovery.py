from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
from xgboost import XGBRanker

import stage002_trend_quality_ranker_oos as stage002


publisher = stage002.publisher
core = stage002.core
PUBLISHER_SOURCE_PATH = Path(str(publisher.__file__)).resolve()
LINE_DIR = Path(__file__).resolve().parents[1]
LINE_ID = stage002.LINE_ID
STAGE = "stage003_lossless_evidence_recovery"

TECHNICAL_FAIL_DECISION = (
    "stage003_lossless_evidence_recovery_fail_close_no_effect_claim"
)
EFFECT_FAIL_DECISION = (
    "stage003_lossless_evidence_recovery_effect_fail_stop_no_true_engine"
)
PASS_DECISION = (
    "stage003_lossless_evidence_recovery_pass_allow_true_engine_ac_"
    "preregistration_only"
)

STAGE002_DIR = stage002.DEFAULT_OUTPUT_DIR
STAGE002_MANIFEST_SHA256 = (
    "a20fa63a1c95a9d37fdc0485ddebd9e5ff403e36d4349d79b04e81e87143e904"
)
STAGE002_EVENT_SHA256 = (
    "1c93af925041026d69ac238fdd72f69c06af0a5e5748fdcf11b46b31e69ad65c"
)
DEFAULT_OUTPUT_DIR = LINE_DIR / "artifacts/stage003_lossless_evidence_recovery"
DEFAULT_AUTHORIZATION_PATH = (
    LINE_DIR / "stages/20260905_stage003_execution_authorization.json"
)
DEFAULT_EXECUTION_EVENT_PATH = LINE_DIR / "artifacts/stage003_execution_event.json"
PREREGISTRATION_PATH = (
    LINE_DIR
    / "stages/20260905_0421_stage003_lossless_evidence_recovery_"
    "preregistration.md"
)
PLAN_PATH = LINE_DIR / "plans/20260905_stage003_lossless_evidence_recovery.md"
INDEPENDENT_REVIEW_PATH = (
    LINE_DIR / "reviews/20260905_stage003_prerun_independent_review.md"
)

DEFAULT_INPUT_PATHS = {
    "stage002_manifest": STAGE002_DIR / "artifact_manifest.json",
    "stage002_execution_event": stage002.DEFAULT_EXECUTION_EVENT_PATH,
    "stage002_authorization": stage002.DEFAULT_AUTHORIZATION_PATH,
    **stage002.DEFAULT_INPUT_PATHS,
}
DEFAULT_EXPECTED_SHA256 = {
    "stage002_manifest": STAGE002_MANIFEST_SHA256,
    "stage002_execution_event": STAGE002_EVENT_SHA256,
    "stage002_authorization": (
        "5734c30781cdd0d9bb7097310057234d77ee2305c21cf557282b1c11558b24e1"
    ),
    **stage002.DEFAULT_EXPECTED_SHA256,
}

AUTHORIZATION_SCOPE = {
    "allowed": [
        "read_frozen_stage002_bundle_and_research_inputs",
        "load_frozen_xgboost_models_74_times",
        "predict_with_frozen_xgboost_models_74_times",
        "write_line_local_lossless_recovery_evidence_and_reports",
        "read_development_oos_labels_after_all_model_and_seal_checks",
    ],
    "prohibited": [
        "model_fit_or_retraining",
        "strategy_backtest",
        "sealed_holdout_access",
        "ctp_connection",
        "order_api",
        "production_write",
    ],
}

RECOVERY_CONTRACT = {
    "stage002_manifest_sha256": STAGE002_MANIFEST_SHA256,
    "stage002_decision": stage002.TECHNICAL_FAIL_DECISION,
    "stage002_error": "pre_effect_seal_mismatch",
    "fold_count": 37,
    "model_file_count": 74,
    "seal_count": 37,
    "access_event_count": 36,
    "prediction_row_count": 2_000,
    "effect_label_row_count": 1_940,
    "model_fit_count": 0,
    "model_load_count": 74,
    "model_predict_count": 74,
    "encoding": "python_float_hex_round_trip",
}


class Stage003Error(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage003Error(f"json_root_not_object:{path}")
    return value


def _write_json(path: Path, value: object) -> None:
    stage002._write_json(Path(path), value)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    stage002._write_csv(frame, Path(path))


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(Path(directory), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def encode_predictions_hex(predictions: pd.DataFrame) -> pd.DataFrame:
    required = [
        "query_date",
        "product_vt_symbol",
        "xgb_score",
        "train_qid_count",
        "train_row_count",
    ]
    if list(predictions.columns) != required:
        raise Stage003Error("lossless_prediction_columns_invalid")
    result = predictions.copy()
    scores = pd.to_numeric(result.pop("xgb_score"), errors="coerce").astype(
        "float64"
    )
    if not np.isfinite(scores.to_numpy(dtype="float64")).all():
        raise Stage003Error("lossless_prediction_nonfinite")
    result.insert(
        2,
        "xgb_score_hex",
        [float(value).hex() for value in scores.to_numpy(dtype="float64")],
    )
    return result


def decode_predictions_hex(encoded: pd.DataFrame) -> pd.DataFrame:
    required = [
        "query_date",
        "product_vt_symbol",
        "xgb_score_hex",
        "train_qid_count",
        "train_row_count",
    ]
    if list(encoded.columns) != required:
        raise Stage003Error("lossless_prediction_hex_columns_invalid")
    result = encoded.copy()
    try:
        scores = np.asarray(
            [float.fromhex(str(value)) for value in result.pop("xgb_score_hex")],
            dtype="float64",
        )
    except ValueError as error:
        raise Stage003Error("lossless_prediction_hex_invalid") from error
    if not np.isfinite(scores).all():
        raise Stage003Error("lossless_prediction_hex_nonfinite")
    result["query_date"] = pd.to_datetime(
        result["query_date"], errors="raise"
    ).dt.normalize()
    result["product_vt_symbol"] = result["product_vt_symbol"].astype(str)
    for column in ("train_qid_count", "train_row_count"):
        result[column] = pd.to_numeric(result[column], errors="raise").astype(
            "int64"
        )
    result.insert(2, "xgb_score", scores)
    return result


def validate_stage002_control_evidence(
    summary: Mapping[str, object],
    event: Mapping[str, object],
    *,
    manifest_sha256: str,
    manifest_artifact_count: int,
    manifest_model_count: int,
    manifest_seal_count: int,
    manifest_access_event_count: int,
) -> dict[str, object]:
    nonce = str(summary.get("authorization_nonce", ""))
    checks = {
        "decision": summary.get("decision") == stage002.TECHNICAL_FAIL_DECISION,
        "error": summary.get("error") == "pre_effect_seal_mismatch",
        "failure_phase": summary.get("failure_phase") == "fold_completed",
        "summary_nonce": bool(nonce),
        "summary_model_count": int(summary.get("model_file_count", -1)) == 74,
        "summary_seal_count": int(summary.get("seal_count", -1)) == 37,
        "event_status": event.get("status") == "completed",
        "event_decision": event.get("decision")
        == stage002.TECHNICAL_FAIL_DECISION,
        "event_nonce": event.get("nonce") == nonce,
        "event_manifest": event.get("final_manifest_sha256")
        == manifest_sha256,
        "manifest_artifact_count": int(manifest_artifact_count) == 159,
        "manifest_model_count": int(manifest_model_count) == 74,
        "manifest_seal_count": int(manifest_seal_count) == 37,
        "manifest_access_event_count": int(manifest_access_event_count) == 36,
    }
    failures = [name for name, passed in checks.items() if not passed]
    if failures:
        raise Stage003Error("stage002_control_evidence_invalid:" + ",".join(failures))
    return {"passed": True, "checks": checks, "authorization_nonce": nonce}


def validate_access_events(
    events_dir: Path, seals_dir: Path
) -> dict[str, int]:
    event_paths = sorted(Path(events_dir).glob("*.json"))
    opened = 0
    rows = 0
    mismatch_count = 0
    seen_dates: set[str] = set()
    for event_path in event_paths:
        event = _read_json(event_path)
        date_name = str(event.get("test_eval_date", ""))
        seal_path = Path(seals_dir) / f"{date_name}.json"
        opened_labels_sha = str(event.get("opened_labels_sha256", ""))
        valid = (
            bool(date_name)
            and event_path.stem == date_name
            and date_name not in seen_dates
            and event.get("status") == "opened"
            and int(event.get("expected_row_count", -1)) > 0
            and int(event.get("opened_row_count", -2))
            == int(event.get("expected_row_count", -1))
            and seal_path.is_file()
            and event.get("seal_sha256") == publisher.sha256_file(seal_path)
            and len(opened_labels_sha) == 64
            and all(character in "0123456789abcdef" for character in opened_labels_sha)
        )
        if not valid:
            mismatch_count += 1
        else:
            opened += 1
            rows += int(event["opened_row_count"])
            seen_dates.add(date_name)
    if mismatch_count:
        raise Stage003Error(f"access_event_invalid:{mismatch_count}")
    return {
        "access_event_count": int(len(event_paths)),
        "opened_access_event_count": int(opened),
        "access_event_row_count": int(rows),
        "access_event_mismatch_count": int(mismatch_count),
    }


def assess_recovery_technical_gates(
    observed: Mapping[str, object],
) -> dict[str, object]:
    expected: dict[str, object] = {
        "input_identity_stable": True,
        "stage002_bundle_verified": True,
        "stage002_control_evidence_valid": True,
        "stage002_authorization_valid": True,
        "fold_count": 37,
        "model_file_count": 74,
        "seal_count": 37,
        "access_event_count": 36,
        "opened_access_event_count": 36,
        "access_event_row_count": 1_940,
        "access_event_mismatch_count": 0,
        "model_fit_count": 0,
        "model_load_count": 74,
        "model_predict_count": 74,
        "model_file_identity_mismatch_count": 0,
        "repeat_prediction_bit_mismatch_fold_count": 0,
        "prediction_seal_match_count": 37,
        "selection_seal_match_count": 37,
        "lossless_prediction_row_count": 2_000,
        "lossless_prediction_bit_mismatch_count": 0,
        "lossless_seal_replay_count": 37,
        "label_rows": 55_226,
        "label_qids": 1_046,
        "final_train_row_count": 55_168,
        "final_train_qid_count": 1_045,
        "effect_label_rows": 1_940,
        "strategy_backtest_runs": 0,
        "sealed_holdout_rows": 0,
        "ctp_connection_count": 0,
        "order_api_called_count": 0,
        "production_files_written": 0,
    }
    gates = {
        f"{name}_exact": (
            observed.get(name) is value
            if isinstance(value, bool)
            else observed.get(name) == value
        )
        for name, value in expected.items()
    }
    return {"passed": all(gates.values()), "gates": gates}


def _implementation_paths() -> dict[str, Path]:
    return {
        "runner": Path(__file__),
        "runner_tests": (
            LINE_DIR / "tests/test_stage003_lossless_evidence_recovery.py"
        ),
        "preregistration": PREREGISTRATION_PATH,
        "plan": PLAN_PATH,
        "independent_prerun_review": INDEPENDENT_REVIEW_PATH,
        "publisher_source": PUBLISHER_SOURCE_PATH,
        "stage002_core": LINE_DIR / "tools/trend_quality_ranker_oos.py",
        "stage002_runner": LINE_DIR / "tools/stage002_trend_quality_ranker_oos.py",
        "external_ranker_core": stage002.EXTERNAL_RANKER_CORE_PATH,
        "external_feature_contract": stage002.EXTERNAL_FEATURE_CONTRACT_PATH,
        "xgboost_sklearn_source": stage002.XGBOOST_SKLEARN_SOURCE_PATH,
        "xgboost_native_library": stage002.XGBOOST_NATIVE_LIBRARY_PATH,
    }


def _runtime_identity() -> dict[str, str]:
    return stage002._runtime_identity()


def build_authorization(
    input_identities: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    implementation_paths = _implementation_paths()
    missing = [name for name, path in implementation_paths.items() if not path.is_file()]
    if missing:
        raise Stage003Error("authorization_implementation_missing:" + ",".join(missing))
    return {
        "authorization_basis": (
            "用户明确表示后续研究操作默认授权，不再逐次确认；"
            "生产、CTP、订单仍禁止"
        ),
        "authorization_type": "user_standing_research_authorization",
        "authorized": True,
        "authorized_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "line_id": LINE_ID,
        "stage": STAGE,
        "nonce": str(uuid.uuid4()),
        "input_sha256": {
            name: identity["sha256"] for name, identity in input_identities.items()
        },
        "implementation_sha256": {
            name: publisher.sha256_file(path)
            for name, path in implementation_paths.items()
        },
        "runtime": _runtime_identity(),
        "scope": AUTHORIZATION_SCOPE,
        "recovery_contract": RECOVERY_CONTRACT,
    }


def verify_authorization(
    authorization_path: Path,
    input_identities: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    path = Path(authorization_path)
    if not path.is_file():
        raise Stage003Error(f"authorization_missing:{path}")
    receipt = _read_json(path)
    if (
        receipt.get("line_id") != LINE_ID
        or receipt.get("stage") != STAGE
        or receipt.get("authorized") is not True
        or not receipt.get("nonce")
    ):
        raise Stage003Error("authorization_header_invalid")
    expected_inputs = {
        name: identity["sha256"] for name, identity in input_identities.items()
    }
    if receipt.get("input_sha256") != expected_inputs:
        raise Stage003Error("authorization_input_binding_invalid")
    expected_implementation = {
        name: publisher.sha256_file(path)
        for name, path in _implementation_paths().items()
    }
    if receipt.get("implementation_sha256") != expected_implementation:
        raise Stage003Error("authorization_implementation_binding_invalid")
    if receipt.get("runtime") != _runtime_identity():
        raise Stage003Error("authorization_runtime_binding_invalid")
    if receipt.get("scope") != AUTHORIZATION_SCOPE:
        raise Stage003Error("authorization_scope_invalid")
    if receipt.get("recovery_contract") != RECOVERY_CONTRACT:
        raise Stage003Error("authorization_recovery_contract_invalid")
    return receipt


def _write_new_json(path: Path, value: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("xb") as handle:
            handle.write(stage002._canonical_json_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(target.parent)
    except FileExistsError as error:
        raise Stage003Error(f"exclusive_output_exists:{target}") from error


def _write_atomic_json(path: Path, value: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp.{uuid.uuid4().hex}")
    with temporary.open("xb") as handle:
        handle.write(stage002._canonical_json_bytes(value))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)
    _fsync_directory(target.parent)


def create_execution_event(
    event_path: Path,
    *,
    authorization_sha256: str,
    nonce: str,
) -> None:
    _write_new_json(
        event_path,
        {
            "line_id": LINE_ID,
            "stage": STAGE,
            "status": "started",
            "created_at": datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
            "authorization_sha256": authorization_sha256,
            "nonce": nonce,
        },
    )


def _complete_execution_event(
    event_path: Path,
    *,
    decision: str,
    final_manifest_sha256: str,
) -> None:
    path = Path(event_path)
    payload = _read_json(path)
    payload.update(
        {
            "status": "completed",
            "completed_at": datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
            "decision": decision,
            "final_manifest_sha256": final_manifest_sha256,
        }
    )
    temporary = path.with_name(f".{path.name}.tmp.{uuid.uuid4().hex}")
    with temporary.open("xb") as handle:
        handle.write(stage002._canonical_json_bytes(payload))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    _fsync_directory(path.parent)


def _stage002_manifest_counts(manifest: Mapping[str, object]) -> dict[str, int]:
    artifacts = manifest.get("artifacts", {})
    if not isinstance(artifacts, dict):
        raise Stage003Error("stage002_manifest_artifacts_invalid")
    names = list(artifacts)
    return {
        "artifact_count": int(len(names)),
        "model_count": int(
            sum(name.startswith("models/") and name.endswith(".ubj") for name in names)
        ),
        "seal_count": int(
            sum(
                name.startswith("pre_effect_seals/")
                and name.endswith(".json")
                for name in names
            )
        ),
        "access_event_count": int(
            sum(
                name.startswith("effect_access_events/")
                and name.endswith(".json")
                for name in names
            )
        ),
    }


def _verify_stage002_bundle(
    input_identities: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    verification = stage002.verify_published_bundle(
        STAGE002_DIR, verify_inputs=True
    )
    if not verification.get("verified"):
        raise Stage003Error(
            "stage002_bundle_invalid:"
            + ",".join(str(value) for value in verification.get("errors", []))
        )
    manifest_path = STAGE002_DIR / "artifact_manifest.json"
    manifest_sha = publisher.sha256_file(manifest_path)
    if manifest_sha != STAGE002_MANIFEST_SHA256:
        raise Stage003Error("stage002_manifest_identity_invalid")
    manifest = _read_json(manifest_path)
    counts = _stage002_manifest_counts(manifest)
    summary = _read_json(STAGE002_DIR / "summary.json")
    event = _read_json(stage002.DEFAULT_EXECUTION_EVENT_PATH)
    control = validate_stage002_control_evidence(
        summary,
        event,
        manifest_sha256=manifest_sha,
        manifest_artifact_count=counts["artifact_count"],
        manifest_model_count=counts["model_count"],
        manifest_seal_count=counts["seal_count"],
        manifest_access_event_count=counts["access_event_count"],
    )
    original_identities = {
        name: input_identities[name] for name in stage002.DEFAULT_INPUT_PATHS
    }
    if manifest.get("input_identities") != original_identities:
        raise Stage003Error("stage002_manifest_input_identity_invalid")
    bundled_authorization = _read_json(
        STAGE002_DIR / "authorization_receipt.json"
    )
    external_authorization = _read_json(stage002.DEFAULT_AUTHORIZATION_PATH)
    if bundled_authorization != external_authorization:
        raise Stage003Error("stage002_authorization_receipt_content_invalid")
    verified_authorization = stage002.verify_authorization(
        STAGE002_DIR / "authorization_receipt.json", original_identities
    )
    if (
        event.get("authorization_sha256")
        != publisher.sha256_file(stage002.DEFAULT_AUTHORIZATION_PATH)
        or verified_authorization.get("nonce") != control["authorization_nonce"]
    ):
        raise Stage003Error("stage002_authorization_event_binding_invalid")
    return {
        "stage002_bundle_verified": True,
        "stage002_control_evidence_valid": True,
        "stage002_authorization_valid": True,
        "stage002_verification": verification,
        "stage002_control": control,
        "stage002_manifest_counts": counts,
        "stage002_authorization_nonce": control["authorization_nonce"],
    }


def _load_replay_frames(
    input_paths: Mapping[str, Path],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    fold_audit = pd.read_csv(
        STAGE002_DIR / "fold_audit.csv", parse_dates=["test_eval_date"]
    )
    fold_plan = pd.read_csv(input_paths["fold_plan"])
    model_features = pd.read_csv(input_paths["model_features"])
    formal_scoring = pd.read_csv(input_paths["formal_scoring"])
    fold_plan["test_eval_date"] = pd.to_datetime(
        fold_plan["test_eval_date"], errors="raise"
    ).dt.normalize()
    fold_plan["effect_evaluable"] = stage002._parse_bool(
        fold_plan["effect_evaluable"], "effect_evaluable"
    )
    fold_plan["inference_only"] = stage002._parse_bool(
        fold_plan["inference_only"], "inference_only"
    )
    fold_audit["test_eval_date"] = pd.to_datetime(
        fold_audit["test_eval_date"], errors="raise"
    ).dt.normalize()
    model_features["query_date"] = pd.to_datetime(
        model_features["query_date"], errors="raise"
    ).dt.normalize()
    formal_scoring["test_eval_date"] = pd.to_datetime(
        formal_scoring["test_eval_date"], errors="raise"
    ).dt.normalize()
    model_features["product_vt_symbol"] = model_features[
        "product_vt_symbol"
    ].astype(str)
    formal_scoring["product_vt_symbol"] = formal_scoring[
        "product_vt_symbol"
    ].astype(str)
    model_features = model_features.loc[
        ~model_features["product_vt_symbol"].eq(core.FIXED_PRODUCT)
    ].copy()
    if formal_scoring["product_vt_symbol"].eq(core.FIXED_PRODUCT).any():
        raise Stage003Error("fixed_product_in_formal_scoring")
    if fold_audit.duplicated("test_eval_date").any() or fold_plan.duplicated(
        "test_eval_date"
    ).any():
        raise Stage003Error("replay_fold_date_duplicate")
    if set(fold_audit["test_eval_date"]) != set(fold_plan["test_eval_date"]):
        raise Stage003Error("replay_fold_date_set_mismatch")
    return fold_audit, fold_plan, model_features, formal_scoring


def _prediction_bits_equal(left: np.ndarray, right: np.ndarray) -> bool:
    a = np.asarray(left, dtype="float64")
    b = np.asarray(right, dtype="float64")
    return bool(a.shape == b.shape and np.array_equal(a.view("uint64"), b.view("uint64")))


def _selection_payload_by_date(
    selections: Sequence[Mapping[str, object]],
) -> dict[pd.Timestamp, Mapping[str, object]]:
    result: dict[pd.Timestamp, Mapping[str, object]] = {}
    for selection in selections:
        date = pd.Timestamp(selection["test_eval_date"]).normalize()
        if date in result:
            raise Stage003Error("replay_selection_date_duplicate")
        result[date] = selection
    return result


def _reconstruct_predictions_and_selections(
    staging: Path,
    *,
    fold_audit: pd.DataFrame,
    fold_plan: pd.DataFrame,
    model_features: pd.DataFrame,
    formal_scoring: pd.DataFrame,
) -> dict[str, object]:
    plan_by_date = fold_plan.set_index("test_eval_date")
    prediction_frames: list[pd.DataFrame] = []
    selections: list[dict[str, object]] = []
    replay_rows: list[dict[str, object]] = []
    model_load_count = 0
    model_predict_count = 0
    model_identity_mismatches = 0
    repeat_bit_mismatch_folds = 0
    prediction_seal_matches = 0
    selection_seal_matches = 0

    ordered_audit = fold_audit.sort_values("test_eval_date", kind="mergesort")
    for audit in ordered_audit.to_dict("records"):
        test_date = pd.Timestamp(audit["test_eval_date"]).normalize()
        date_name = f"{test_date:%Y-%m-%d}"
        if test_date not in plan_by_date.index:
            raise Stage003Error(f"replay_fold_plan_missing:{date_name}")
        plan = plan_by_date.loc[test_date]
        for column in ("effect_evaluable", "inference_only"):
            audit_value = str(audit[column]).strip().lower() == "true"
            if audit_value != bool(plan[column]):
                raise Stage003Error(f"replay_fold_flag_mismatch:{date_name}:{column}")

        test_features = model_features.loc[
            model_features["query_date"].eq(test_date)
        ].sort_values("product_vt_symbol", kind="mergesort")
        if test_features.empty:
            raise Stage003Error(f"replay_test_features_missing:{date_name}")
        if int(audit["test_row_count"]) != len(test_features):
            raise Stage003Error(f"replay_test_row_count_mismatch:{date_name}")
        test_scoring = formal_scoring.loc[
            formal_scoring["test_eval_date"].eq(test_date)
        ].copy()
        if test_scoring.empty:
            raise Stage003Error(f"replay_test_scoring_missing:{date_name}")
        predict_x = test_features[list(core.MODEL_FEATURES)].apply(
            pd.to_numeric, errors="coerce"
        ).astype(float)
        if not np.isfinite(predict_x.to_numpy(dtype="float64")).all():
            raise Stage003Error(f"replay_feature_nonfinite:{date_name}")

        fold_predictions: dict[str, np.ndarray] = {}
        model_hashes: dict[str, str] = {}
        for role in ("primary", "repeat"):
            model_path = STAGE002_DIR / "models" / f"{date_name}_{role}.ubj"
            expected_hash = str(audit[f"{role}_model_sha256"])
            actual_hash = publisher.sha256_file(model_path)
            if actual_hash != expected_hash:
                model_identity_mismatches += 1
                raise Stage003Error(
                    f"replay_model_identity_mismatch:{date_name}:{role}"
                )
            model = XGBRanker()
            model.load_model(model_path)
            model_load_count += 1
            if model.get_booster().feature_names != list(core.MODEL_FEATURES):
                raise Stage003Error(
                    f"replay_model_feature_order_mismatch:{date_name}:{role}"
                )
            values = np.asarray(model.predict(predict_x), dtype="float64")
            model_predict_count += 1
            if not np.isfinite(values).all():
                raise Stage003Error(f"replay_prediction_nonfinite:{date_name}:{role}")
            fold_predictions[role] = values
            model_hashes[role] = actual_hash
        bit_equal = _prediction_bits_equal(
            fold_predictions["primary"], fold_predictions["repeat"]
        )
        if not bit_equal:
            repeat_bit_mismatch_folds += 1

        predicted = test_features[["query_date", "product_vt_symbol"]].copy()
        predicted["xgb_score"] = fold_predictions["primary"]
        predicted["train_qid_count"] = int(audit["train_qid_count"])
        predicted["train_row_count"] = int(audit["train_row_count"])
        selection = core.select_consensus_one_slot(
            predicted,
            test_scoring,
            top_k=int(stage002.SELECTOR_CONTRACT["xgb_top_k"]),
        )
        selection["effect_evaluable"] = bool(plan["effect_evaluable"])
        selection["inference_only"] = bool(plan["inference_only"])
        selection["train_qid_count"] = int(audit["train_qid_count"])

        seal_path = STAGE002_DIR / "pre_effect_seals" / f"{date_name}.json"
        if publisher.sha256_file(seal_path) != str(audit["pre_effect_seal_sha256"]):
            raise Stage003Error(f"replay_seal_identity_mismatch:{date_name}")
        actual_seal = _read_json(seal_path)
        expected_seal = stage002._seal_expected_payload(
            test_eval_date=test_date,
            model_hashes=model_hashes,
            predictions=predicted,
            selection=selection,
            test_label_rows_read_before_seal=0,
        )
        prediction_match = (
            actual_seal.get("predictions_sha256")
            == expected_seal["predictions_sha256"]
        )
        selection_match = (
            actual_seal.get("selection_sha256")
            == expected_seal["selection_sha256"]
        )
        if prediction_match:
            prediction_seal_matches += 1
        if selection_match:
            selection_seal_matches += 1
        if actual_seal != expected_seal:
            raise Stage003Error(f"replay_pre_effect_seal_mismatch:{date_name}")

        prediction_frames.append(predicted)
        selections.append(selection)
        replay_rows.append(
            {
                "test_eval_date": test_date,
                "test_row_count": int(len(predicted)),
                "primary_model_sha256": model_hashes["primary"],
                "repeat_model_sha256": model_hashes["repeat"],
                "repeat_prediction_bit_exact": bit_equal,
                "prediction_seal_match": prediction_match,
                "selection_seal_match": selection_match,
                "pre_effect_seal_sha256": publisher.sha256_file(seal_path),
            }
        )

    predictions = pd.concat(prediction_frames, ignore_index=True)
    encoded = encode_predictions_hex(predictions)
    encoded_path = staging / "reconstructed_predictions_hex.csv.gz"
    _write_csv(encoded, encoded_path)
    decoded = decode_predictions_hex(pd.read_csv(encoded_path))
    source_scores = predictions["xgb_score"].to_numpy(dtype="float64")
    decoded_scores = decoded["xgb_score"].to_numpy(dtype="float64")
    score_mismatch = int(
        np.count_nonzero(source_scores.view("uint64") != decoded_scores.view("uint64"))
    )
    non_score_columns = [
        "query_date",
        "product_vt_symbol",
        "train_qid_count",
        "train_row_count",
    ]
    if not predictions[non_score_columns].reset_index(drop=True).equals(
        decoded[non_score_columns].reset_index(drop=True)
    ):
        raise Stage003Error("lossless_prediction_non_score_round_trip_mismatch")
    if score_mismatch:
        raise Stage003Error(f"lossless_prediction_bit_mismatch:{score_mismatch}")

    persisted_selection_payload = json.loads(
        stage002._canonical_json_bytes({"selections": selections})
    )
    _write_json(staging / "reconstructed_selections.json", persisted_selection_payload)
    persisted_selections = _read_json(staging / "reconstructed_selections.json").get(
        "selections"
    )
    if not isinstance(persisted_selections, list):
        raise Stage003Error("persisted_selection_payload_invalid")
    persisted_by_date = _selection_payload_by_date(persisted_selections)
    decoded_dates = decoded["query_date"].dt.normalize()
    audit_by_date = ordered_audit.set_index("test_eval_date")
    lossless_seal_replays = 0
    for test_date, selection in persisted_by_date.items():
        if test_date not in audit_by_date.index:
            raise Stage003Error("lossless_seal_replay_audit_missing")
        audit = audit_by_date.loc[test_date]
        date_name = f"{test_date:%Y-%m-%d}"
        fold_predictions_frame = decoded.loc[decoded_dates.eq(test_date)].copy()
        stage002.verify_pre_effect_seal(
            STAGE002_DIR / "pre_effect_seals" / f"{date_name}.json",
            model_hashes={
                "primary": str(audit["primary_model_sha256"]),
                "repeat": str(audit["repeat_model_sha256"]),
            },
            predictions=fold_predictions_frame,
            selection=selection,
        )
        lossless_seal_replays += 1

    replay_audit = pd.DataFrame(replay_rows).sort_values(
        "test_eval_date", kind="mergesort"
    )
    _write_csv(replay_audit, staging / "fold_replay_audit.csv")
    return {
        "predictions": predictions,
        "selections": selections,
        "fold_replay_audit": replay_audit,
        "fold_count": int(len(replay_audit)),
        "model_file_count": int(
            len(list((STAGE002_DIR / "models").glob("*.ubj")))
        ),
        "seal_count": int(
            len(list((STAGE002_DIR / "pre_effect_seals").glob("*.json")))
        ),
        "model_fit_count": 0,
        "model_load_count": int(model_load_count),
        "model_predict_count": int(model_predict_count),
        "model_file_identity_mismatch_count": int(model_identity_mismatches),
        "repeat_prediction_bit_mismatch_fold_count": int(
            repeat_bit_mismatch_folds
        ),
        "prediction_seal_match_count": int(prediction_seal_matches),
        "selection_seal_match_count": int(selection_seal_matches),
        "lossless_prediction_row_count": int(len(decoded)),
        "lossless_prediction_bit_mismatch_count": int(score_mismatch),
        "lossless_seal_replay_count": int(lossless_seal_replays),
    }


def _assert_pre_label_recovery_gates(observed: Mapping[str, object]) -> None:
    expected = {
        "input_identity_stable": True,
        "stage002_bundle_verified": True,
        "stage002_control_evidence_valid": True,
        "stage002_authorization_valid": True,
        "fold_count": 37,
        "model_file_count": 74,
        "seal_count": 37,
        "access_event_count": 36,
        "opened_access_event_count": 36,
        "access_event_row_count": 1_940,
        "access_event_mismatch_count": 0,
        "model_fit_count": 0,
        "model_load_count": 74,
        "model_predict_count": 74,
        "model_file_identity_mismatch_count": 0,
        "repeat_prediction_bit_mismatch_fold_count": 0,
        "prediction_seal_match_count": 37,
        "selection_seal_match_count": 37,
        "lossless_prediction_row_count": 2_000,
        "lossless_prediction_bit_mismatch_count": 0,
        "lossless_seal_replay_count": 37,
    }
    failures = [
        name for name, value in expected.items() if observed.get(name) != value
    ]
    if failures:
        raise Stage003Error(
            "pre_label_recovery_gate_failed:" + ",".join(failures)
        )


def _load_and_evaluate_effect_labels(
    *,
    staging: Path,
    input_paths: Mapping[str, Path],
    fold_plan: pd.DataFrame,
    predictions: pd.DataFrame,
    selections: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    raw_labels = pd.read_csv(input_paths["path_labels"])
    labels, label_audit = core.prepare_ai_universe_labels(raw_labels)
    paths = pd.read_csv(
        input_paths["expiry_paths"],
        usecols=["query_date", "product_vt_symbol", "label_end"],
    )
    paths["query_date"] = pd.to_datetime(
        paths["query_date"], errors="raise"
    ).dt.normalize()
    paths["label_end"] = pd.to_datetime(
        paths["label_end"], errors="raise"
    ).dt.normalize()
    paths["product_vt_symbol"] = paths["product_vt_symbol"].astype(str)
    paths = paths.loc[
        ~paths["product_vt_symbol"].eq(core.FIXED_PRODUCT)
    ].copy()
    label_store = core.PhaseGatedTrendQualityStore(labels, paths)

    ordered_folds = fold_plan.sort_values("test_eval_date", kind="mergesort")
    final_test_date = pd.Timestamp(ordered_folds.iloc[-1]["test_eval_date"])
    final_training = label_store.open_training_labels(final_test_date)
    final_train_qids = int(final_training["query_date"].nunique())
    final_train_rows = int(len(final_training))

    prediction_dates = predictions["query_date"].dt.normalize()
    selections_by_date = _selection_payload_by_date(selections)
    event_paths = sorted(
        (STAGE002_DIR / "effect_access_events").glob("*.json")
    )
    events_by_date = {
        pd.Timestamp(event_path.stem).normalize(): _read_json(event_path)
        for event_path in event_paths
    }
    rank_rows: list[dict[str, object]] = []
    effect_rows: list[dict[str, object]] = []
    effect_label_rows = 0
    effect_qids_opened = 0
    opened_label_sha_mismatch_count = 0
    for fold in ordered_folds.itertuples(index=False):
        if not bool(fold.effect_evaluable):
            continue
        test_date = pd.Timestamp(fold.test_eval_date).normalize()
        if test_date not in events_by_date:
            raise Stage003Error(f"effect_access_event_missing:{test_date.date()}")
        event = events_by_date[test_date]
        label_store.authorize_effect_qid(test_date)
        test_labels = _open_effect_qid_with_progress(
            staging,
            label_store=label_store,
            test_date=test_date,
            effect_label_rows=effect_label_rows,
            effect_qids_opened=effect_qids_opened,
        )
        effect_label_rows += int(len(test_labels))
        effect_qids_opened += 1
        if len(test_labels) != int(event["opened_row_count"]):
            raise Stage003Error(f"effect_label_row_count_mismatch:{test_date.date()}")
        if stage002._frame_sha256(test_labels) != event.get(
            "opened_labels_sha256"
        ):
            opened_label_sha_mismatch_count += 1
            raise Stage003Error(f"effect_label_identity_mismatch:{test_date.date()}")
        predicted = predictions.loc[prediction_dates.eq(test_date)].copy()
        if predicted.empty or test_date not in selections_by_date:
            raise Stage003Error(f"effect_replay_payload_missing:{test_date.date()}")
        scored_labels = predicted.merge(
            test_labels,
            on=["query_date", "product_vt_symbol"],
            how="inner",
            validate="one_to_one",
        )
        if len(scored_labels) != len(test_labels):
            raise Stage003Error(f"effect_prediction_join_mismatch:{test_date.date()}")
        rank_rows.append(core.compute_month_rank_metrics(scored_labels, k=10))
        effect_rows.append(
            core.build_effect_row(selections_by_date[test_date], test_labels)
        )

    predictive_monthly = pd.DataFrame(rank_rows).sort_values(
        "test_eval_date", kind="mergesort"
    )
    effect_monthly = pd.DataFrame(effect_rows).sort_values(
        "test_eval_date", kind="mergesort"
    )
    return {
        "predictive_monthly": predictive_monthly,
        "effect_monthly": effect_monthly,
        "label_rows": int(label_audit["ai_label_rows"]),
        "label_qids": int(label_audit["ai_label_qids"]),
        "final_train_row_count": final_train_rows,
        "final_train_qid_count": final_train_qids,
        "effect_label_rows": int(effect_label_rows),
        "opened_label_sha_mismatch_count": int(
            opened_label_sha_mismatch_count
        ),
        "label_access_audit": label_store.audit(),
        "ai_universe_label_audit": label_audit,
    }


def _write_progress(
    staging: Path,
    *,
    phase: str,
    effect_labels_opened: bool,
    effect_label_rows: int = 0,
    effect_qids_opened: int = 0,
    current_test_date: pd.Timestamp | None = None,
) -> None:
    _write_atomic_json(
        staging / "run_progress.json",
        {
            "phase": phase,
            "effect_labels_opened": bool(effect_labels_opened),
            "effect_label_rows": int(effect_label_rows),
            "effect_qids_opened": int(effect_qids_opened),
            "current_test_date": (
                pd.Timestamp(current_test_date).date().isoformat()
                if current_test_date is not None
                else None
            ),
            "updated_at": datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
        },
    )


def _open_effect_qid_with_progress(
    staging: Path,
    *,
    label_store: core.PhaseGatedTrendQualityStore,
    test_date: pd.Timestamp,
    effect_label_rows: int,
    effect_qids_opened: int,
) -> pd.DataFrame:
    expected_rows = int(label_store.qid_row_count(test_date))
    if expected_rows < 1:
        raise Stage003Error(f"effect_qid_empty:{pd.Timestamp(test_date).date()}")
    conservative_rows = int(effect_label_rows) + expected_rows
    conservative_qids = int(effect_qids_opened) + 1
    _write_progress(
        staging,
        phase="effect_label_qid_opening",
        effect_labels_opened=True,
        effect_label_rows=conservative_rows,
        effect_qids_opened=conservative_qids,
        current_test_date=test_date,
    )
    opened = label_store.open_effect_qid(test_date)
    _write_progress(
        staging,
        phase="effect_label_qid_opened",
        effect_labels_opened=True,
        effect_label_rows=int(effect_label_rows) + int(len(opened)),
        effect_qids_opened=conservative_qids,
        current_test_date=test_date,
    )
    return opened


def _report(summary: Mapping[str, object]) -> str:
    predictive = summary.get("predictive_metrics", {})
    effect = summary.get("effect_metrics", {})
    return (
        "# Stage003 XGBRanker 无拟合证据恢复结果\n\n"
        f"- 决策：`{summary['decision']}`\n"
        f"- 技术恢复门：{'通过' if summary.get('technical', {}).get('passed') else '失败'}\n"
        f"- 全截面预测门：{'通过' if summary.get('predictive', {}).get('passed') else '失败或未开放'}\n"
        f"- A/C 路径代理门：{'通过' if summary.get('effect', {}).get('passed') else '失败或未开放'}\n"
        f"- model fit/load/predict：{summary.get('model_fit_count', 0)}/"
        f"{summary.get('model_load_count', 0)}/{summary.get('model_predict_count', 0)}\n"
        f"- seal 原始重建/无损回读：{summary.get('prediction_seal_match_count', 0)}/"
        f"{summary.get('lossless_seal_replay_count', 0)}\n"
        f"- mean Rank IC：{predictive.get('mean_rank_ic', 'NA')}\n"
        f"- replacement：{effect.get('replacement_count', 0)}\n"
        f"- 质量差值总和：{effect.get('sum_quality_delta', 'NA')}\n"
        f"- 幅度差值总和：{effect.get('sum_abs_log_return_delta', 'NA')}\n"
        f"- 路径回撤代理差值总和："
        f"{effect.get('sum_oriented_max_drawdown_delta', 'NA')}\n"
        "- 本阶段没有重新训练，也不是策略撮合回测；代理值不代表收益或账户最大回撤。\n"
        "- strategy backtest、sealed holdout、CTP、订单和生产写入：全部为0。\n"
    )


def _execute_stage003(
    staging: Path,
    *,
    input_paths: Mapping[str, Path],
    expected_sha256: Mapping[str, str],
    identities_before: Mapping[str, Mapping[str, object]],
    authorization: Mapping[str, object],
) -> dict[str, object]:
    staging.mkdir(parents=True)
    _write_progress(
        staging,
        phase="initialized",
        effect_labels_opened=False,
    )
    stage002_evidence = _verify_stage002_bundle(identities_before)
    fold_audit, fold_plan, model_features, formal_scoring = _load_replay_frames(
        input_paths
    )
    replay = _reconstruct_predictions_and_selections(
        staging,
        fold_audit=fold_audit,
        fold_plan=fold_plan,
        model_features=model_features,
        formal_scoring=formal_scoring,
    )
    access = validate_access_events(
        STAGE002_DIR / "effect_access_events",
        STAGE002_DIR / "pre_effect_seals",
    )
    identities_mid = publisher.collect_input_identities(
        input_paths, expected_sha256
    )
    observed: dict[str, object] = {
        "input_identity_stable": identities_mid == identities_before,
        **{
            name: stage002_evidence[name]
            for name in (
                "stage002_bundle_verified",
                "stage002_control_evidence_valid",
                "stage002_authorization_valid",
            )
        },
        **{
            name: replay[name]
            for name in (
                "fold_count",
                "model_file_count",
                "seal_count",
                "model_fit_count",
                "model_load_count",
                "model_predict_count",
                "model_file_identity_mismatch_count",
                "repeat_prediction_bit_mismatch_fold_count",
                "prediction_seal_match_count",
                "selection_seal_match_count",
                "lossless_prediction_row_count",
                "lossless_prediction_bit_mismatch_count",
                "lossless_seal_replay_count",
            )
        },
        **access,
        "strategy_backtest_runs": 0,
        "sealed_holdout_rows": 0,
        "ctp_connection_count": 0,
        "order_api_called_count": 0,
        "production_files_written": 0,
    }
    _assert_pre_label_recovery_gates(observed)
    _write_progress(
        staging,
        phase="all_model_and_seal_checks_passed",
        effect_labels_opened=False,
    )

    evaluation = _load_and_evaluate_effect_labels(
        staging=staging,
        input_paths=input_paths,
        fold_plan=fold_plan,
        predictions=replay["predictions"],
        selections=replay["selections"],
    )
    _write_progress(
        staging,
        phase="effect_labels_replayed",
        effect_labels_opened=True,
        effect_label_rows=int(evaluation["effect_label_rows"]),
        effect_qids_opened=36,
    )
    identities_after = publisher.collect_input_identities(
        input_paths, expected_sha256
    )
    observed["input_identity_stable"] = bool(
        identities_mid == identities_before == identities_after
    )
    for name in (
        "label_rows",
        "label_qids",
        "final_train_row_count",
        "final_train_qid_count",
        "effect_label_rows",
    ):
        observed[name] = evaluation[name]
    if int(evaluation["opened_label_sha_mismatch_count"]):
        raise Stage003Error("opened_effect_label_identity_mismatch")
    technical = assess_recovery_technical_gates(observed)
    if not technical["passed"]:
        failed = [
            name for name, passed in technical["gates"].items() if not passed
        ]
        raise Stage003Error("recovery_technical_gate_failed:" + ",".join(failed))

    predictive_monthly = evaluation["predictive_monthly"]
    effect_monthly = evaluation["effect_monthly"]
    predictive_metrics = core.compute_predictive_metrics(predictive_monthly)
    predictive = core.assess_predictive_gates(predictive_metrics)
    effect_metrics = core.compute_effect_metrics(effect_monthly)
    effect = core.assess_effect_gates(effect_metrics)
    decision = (
        PASS_DECISION
        if predictive["passed"] and effect["passed"]
        else EFFECT_FAIL_DECISION
    )
    summary = {
        "line_id": LINE_ID,
        "stage": STAGE,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": decision,
        "all_gates_passed": bool(
            technical["passed"] and predictive["passed"] and effect["passed"]
        ),
        "technical": technical,
        "predictive": predictive,
        "effect": effect,
        "predictive_metrics": predictive_metrics,
        "effect_metrics": effect_metrics,
        **observed,
        "opened_label_sha_mismatch_count": int(
            evaluation["opened_label_sha_mismatch_count"]
        ),
        "label_access_audit": evaluation["label_access_audit"],
        "ai_universe_label_audit": evaluation["ai_universe_label_audit"],
        "stage002_evidence": stage002_evidence,
        "authorization_nonce": authorization["nonce"],
        "input_identities_before": identities_before,
        "input_identities_mid": identities_mid,
        "input_identities_after": identities_after,
        "development_oos_only": True,
        "model_retraining_performed": False,
        "stage002_lossy_metric_csv_consumed": False,
        "proxy_metrics_are_not_strategy_pnl_or_account_drawdown": True,
        "independent_reviewer_required": True,
    }
    _write_csv(predictive_monthly, staging / "predictive_monthly.csv")
    _write_csv(effect_monthly, staging / "effect_monthly.csv")
    _write_json(staging / "summary.json", summary)
    _write_json(staging / "input_identities.json", identities_before)
    _write_json(staging / "authorization_receipt.json", authorization)
    (staging / "report.md").write_text(_report(summary), encoding="utf-8")
    _write_progress(
        staging,
        phase="completed",
        effect_labels_opened=True,
        effect_label_rows=int(evaluation["effect_label_rows"]),
        effect_qids_opened=36,
    )
    return summary


def _publish_failure(
    staging: Path,
    *,
    error: Exception,
    input_identities: Mapping[str, object],
    authorization: Mapping[str, object],
) -> dict[str, object]:
    staging.mkdir(parents=True, exist_ok=True)
    progress = (
        _read_json(staging / "run_progress.json")
        if (staging / "run_progress.json").is_file()
        else {}
    )
    labels_opened = bool(progress.get("effect_labels_opened", False))
    summary = {
        "line_id": LINE_ID,
        "stage": STAGE,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": TECHNICAL_FAIL_DECISION,
        "all_gates_passed": False,
        "technical": {"passed": False, "gates": {}},
        "predictive": {
            "passed": False,
            "not_opened": not labels_opened,
            "gates": {},
        },
        "effect": {
            "passed": False,
            "not_opened": not labels_opened,
            "effect_label_rows_opened": int(progress.get("effect_label_rows", 0)),
            "effect_qids_opened": int(progress.get("effect_qids_opened", 0)),
            "gates": {},
        },
        "error_type": type(error).__name__,
        "error": str(error),
        "failure_phase": progress.get("phase", "before_progress_initialization"),
        "partial_artifacts_preserved": True,
        "model_fit_count": 0,
        "strategy_backtest_runs": 0,
        "sealed_holdout_rows": 0,
        "ctp_connection_count": 0,
        "order_api_called_count": 0,
        "production_files_written": 0,
        "authorization_nonce": authorization.get("nonce"),
        "independent_reviewer_required": True,
    }
    _write_json(staging / "summary.json", summary)
    _write_json(staging / "input_identities.json", input_identities)
    _write_json(staging / "authorization_receipt.json", authorization)
    (staging / "report.md").write_text(_report(summary), encoding="utf-8")
    return summary


def _atomic_publish(staging: Path, final_dir: Path) -> None:
    if final_dir.exists():
        raise Stage003Error(f"final_output_exists:{final_dir}")
    os.replace(staging, final_dir)


def verify_published_bundle(
    final_dir: Path, *, verify_inputs: bool = False
) -> dict[str, object]:
    return stage002.verify_published_bundle(
        Path(final_dir), verify_inputs=verify_inputs
    )


def write_stage003_authorization(
    *,
    authorization_path: Path = DEFAULT_AUTHORIZATION_PATH,
    input_paths: Mapping[str, Path] = DEFAULT_INPUT_PATHS,
    expected_sha256: Mapping[str, str] = DEFAULT_EXPECTED_SHA256,
) -> dict[str, object]:
    identities = publisher.collect_input_identities(input_paths, expected_sha256)
    _verify_stage002_bundle(identities)
    receipt = build_authorization(identities)
    _write_new_json(authorization_path, receipt)
    verify_authorization(authorization_path, identities)
    return receipt


def run_stage003(
    *,
    line_dir: Path = LINE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    authorization_path: Path = DEFAULT_AUTHORIZATION_PATH,
    execution_event_path: Path = DEFAULT_EXECUTION_EVENT_PATH,
    input_paths: Mapping[str, Path] = DEFAULT_INPUT_PATHS,
    expected_sha256: Mapping[str, str] = DEFAULT_EXPECTED_SHA256,
) -> dict[str, object]:
    final_path = publisher.assert_line_local_output(line_dir, output_dir)
    event_path = publisher.assert_line_local_output(line_dir, execution_event_path)
    if final_path.exists():
        raise Stage003Error(f"final_output_exists:{final_path}")
    identities_before = publisher.collect_input_identities(
        input_paths, expected_sha256
    )
    authorization = verify_authorization(authorization_path, identities_before)
    create_execution_event(
        event_path,
        authorization_sha256=publisher.sha256_file(authorization_path),
        nonce=str(authorization["nonce"]),
    )
    final_path.parent.mkdir(parents=True, exist_ok=True)
    staging = final_path.parent / f".stage003.tmp.{uuid.uuid4().hex}"
    try:
        summary = _execute_stage003(
            staging,
            input_paths=input_paths,
            expected_sha256=expected_sha256,
            identities_before=identities_before,
            authorization=authorization,
        )
        stage002._build_manifest(staging, identities_before)
        verification = verify_published_bundle(staging)
        if not verification.get("verified"):
            raise Stage003Error(
                "staging_manifest_invalid:"
                + ",".join(str(value) for value in verification.get("errors", []))
            )
        _atomic_publish(staging, final_path)
        final_verification = verify_published_bundle(
            final_path, verify_inputs=True
        )
        if not final_verification.get("verified"):
            raise Stage003Error(
                "final_manifest_invalid:"
                + ",".join(
                    str(value) for value in final_verification.get("errors", [])
                )
            )
    except Exception as primary_error:
        if final_path.exists() and not staging.exists():
            os.replace(final_path, staging)
        summary = _publish_failure(
            staging,
            error=primary_error,
            input_identities=identities_before,
            authorization=authorization,
        )
        try:
            stage002._build_manifest(staging, identities_before)
            failure_verification = verify_published_bundle(staging)
            if not failure_verification.get("verified"):
                raise Stage003Error(
                    "failure_staging_manifest_invalid:"
                    + ",".join(
                        str(value)
                        for value in failure_verification.get("errors", [])
                    )
                )
            _atomic_publish(staging, final_path)
            final_verification = verify_published_bundle(
                final_path, verify_inputs=True
            )
            if not final_verification.get("verified"):
                raise Stage003Error(
                    "failure_final_manifest_invalid:"
                    + ",".join(
                        str(value)
                        for value in final_verification.get("errors", [])
                    )
                )
        except Exception as terminal_error:
            _complete_execution_event(
                event_path,
                decision=TECHNICAL_FAIL_DECISION,
                final_manifest_sha256="",
            )
            raise Stage003Error(
                f"terminal_failure_bundle_error:{type(terminal_error).__name__}:"
                f"{terminal_error}"
            ) from terminal_error
    manifest_sha = publisher.sha256_file(final_path / "artifact_manifest.json")
    _complete_execution_event(
        event_path,
        decision=str(summary["decision"]),
        final_manifest_sha256=manifest_sha,
    )
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage003 no-training lossless XGBRanker evidence recovery"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--authorize", action="store_true")
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        if args.authorize:
            receipt = write_stage003_authorization()
            print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
            return 0
        if args.verify_only:
            result = verify_published_bundle(
                DEFAULT_OUTPUT_DIR, verify_inputs=True
            )
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0 if result.get("verified") else 1
        summary = run_stage003()
    except Exception as error:
        print(
            json.dumps(
                {"error": f"{type(error).__name__}:{error}"},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    print(
        json.dumps(
            summary,
            ensure_ascii=False,
            sort_keys=True,
            default=stage002._json_default,
        )
    )
    return 0 if summary["decision"] == PASS_DECISION else 2


if __name__ == "__main__":
    raise SystemExit(main())
