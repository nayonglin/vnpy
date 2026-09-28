from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import platform
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
import xgboost
from xgboost import XGBRanker

import stage001_roll_adjusted_trend_quality_labels as stage001
import trend_quality_ranker_oos as core


LINE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
V1_TOOLS = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/tools"
)
if str(V1_TOOLS) not in sys.path:
    sys.path.insert(0, str(V1_TOOLS))

import stage001_daily_ranker_contract as v1_stage


publisher = stage001.publisher
LINE_ID = "futures_trend_xgboost_pit_roll_adjusted_trend_quality_labels"
STAGE = "stage002_trend_quality_ranker_oos"
TECHNICAL_FAIL_DECISION = (
    "stage002_trend_quality_ranker_contract_or_pit_invalid_stop_no_effect_claim"
)
EFFECT_FAIL_DECISION = (
    "stage002_trend_quality_ranker_oos_fail_stop_no_true_engine"
)
PASS_DECISION = (
    "stage002_trend_quality_ranker_oos_pass_allow_true_engine_ac_"
    "preregistration_only"
)
V2_PASS_DECISION = (
    "stage001_daily_ranker_v2_contract_pass_allow_stage002_"
    "preregistration_only"
)

STAGE001_DIR = LINE_DIR / "artifacts/stage001_roll_adjusted_trend_quality_labels"
EXPIRY_DIR = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_expiry_safe_roll_mapping/"
    "artifacts/stage001_expiry_safe_roll_mapping"
)
V1_DIR = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/"
    "artifacts/stage001_daily_ranker_contract"
)
V2_DIR = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_full_market_daily_ranker_v2/"
    "artifacts/stage001_v2_contract_requalification"
)
DEFAULT_OUTPUT_DIR = LINE_DIR / "artifacts/stage002_trend_quality_ranker_oos"
DEFAULT_AUTHORIZATION_PATH = (
    LINE_DIR / "stages/20260905_stage002_execution_authorization.json"
)
DEFAULT_EXECUTION_EVENT_PATH = LINE_DIR / "artifacts/stage002_execution_event.json"
PREREGISTRATION_PATH = (
    LINE_DIR
    / "stages/20260905_0319_stage002_trend_quality_ranker_oos_"
    "preregistration.md"
)
PLAN_PATH = LINE_DIR / "plans/20260905_stage002_trend_quality_ranker_oos.md"
EXTERNAL_RANKER_CORE_PATH = Path(
    inspect.getsourcefile(core.fit_repeated_ranker) or ""
).resolve()
EXTERNAL_FEATURE_CONTRACT_PATH = V1_TOOLS / "daily_ranker_contract.py"
XGBOOST_SKLEARN_SOURCE_PATH = Path(
    inspect.getsourcefile(XGBRanker) or ""
).resolve()
XGBOOST_NATIVE_LIBRARY_PATH = Path(xgboost.core._LIB._name).resolve()

DEFAULT_INPUT_PATHS = {
    "stage001_manifest": STAGE001_DIR / "artifact_manifest.json",
    "stage001_summary": STAGE001_DIR / "summary.json",
    "path_labels": STAGE001_DIR / "path_labels.csv.gz",
    "expiry_manifest": EXPIRY_DIR / "artifact_manifest.json",
    "expiry_summary": EXPIRY_DIR / "summary.json",
    "expiry_paths": EXPIRY_DIR / "expiry_safe_paths.csv.gz",
    "v1_manifest": V1_DIR / "artifact_manifest.json",
    "v1_summary": V1_DIR / "summary.json",
    "model_features": V1_DIR / "model_feature_panel.csv.gz",
    "formal_scoring": V1_DIR / "formal_scoring_plan.csv",
    "fold_plan": V1_DIR / "fold_plan.csv",
    "v2_manifest": V2_DIR / "artifact_manifest.json",
    "v2_summary": V2_DIR / "summary.json",
}
DEFAULT_EXPECTED_SHA256 = {
    "stage001_manifest": "284c55459ecd77f68cb4f0721659312ca9422cd720d7d48605ab0c918ac6f7a2",
    "stage001_summary": "387b3876fd334817f9be6b53239656a588b3e344d5ca832237ca8ab7fde42c52",
    "path_labels": "b6e40cfcafdca42de5500480f1680e167c7a862ca573501a3af1ede3a4cc054d",
    "expiry_manifest": "9f768fc6de7ccd3eb240c29f0444249bd333356d756b137197dc78e4f5f44d76",
    "expiry_summary": "6f994dd88896781a7f1af9e9760890540445dc8539a6349ae416b82bcf37283f",
    "expiry_paths": "a3f2c1249085b872372f8f0aca2d1cbaf77ecb8a7bc04056f9118f077c16748e",
    "v1_manifest": "0ec63c32cf8fbe33a85bed16d20a94aaeb7d2ee9a5906670819e91d3671e702a",
    "v1_summary": "926414442f4e1d6210cf41aeeb2ac480378823b5a705cc877a125380bbec0a11",
    "model_features": "1e4ebb1942dc066eb1164dc82e7e0412fe10d433e57aa5b8b8ab3b71822344ac",
    "formal_scoring": "ed83264188655939cb1289d75f480174be3bdcc50e7ed2a9daf0731a48a73ed2",
    "fold_plan": "3c9514e7fe10b36a775cd8c9bfd16641d493cc8a64209319780326ba0f9fbb32",
    "v2_manifest": "7428e753607ff44b39f0e3510e29493ec96b4163a35fa261791da7d819b27b79",
    "v2_summary": "a25817cbbd6da47dde8d711adf35ef70cc37422476060a2e652db37aaed7536d",
}

AUTHORIZATION_SCOPE = {
    "allowed": [
        "read_frozen_research_inputs",
        "fit_fixed_xgboost_ranker_74_times",
        "write_line_local_models_predictions_seals_and_reports",
        "open_development_oos_labels_only_after_matching_seal",
    ],
    "prohibited": [
        "strategy_backtest",
        "sealed_holdout_access",
        "ctp_connection",
        "order_api",
        "production_write",
    ],
}
SELECTOR_CONTRACT = {
    "type": "formal_lr_xgb_top10_consensus_one_slot",
    "xgb_top_k": 10,
    "max_replacements_per_month": 1,
    "formal_top9_unchanged": True,
    "fixed_fu_unchanged": True,
    "excluded_fixed_product": core.FIXED_PRODUCT,
}


class Stage002Error(RuntimeError):
    pass


def _json_default(value: object) -> object:
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"not_json_serializable:{type(value).__name__}")


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=_json_default,
        )
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _frame_sha256(frame: pd.DataFrame) -> str:
    ordered = frame.copy()
    for column in ordered.columns:
        if pd.api.types.is_datetime64_any_dtype(ordered[column]):
            ordered[column] = ordered[column].dt.strftime("%Y-%m-%dT%H:%M:%S")
    return _sha256_bytes(
        ordered.to_csv(index=False, lineterminator="\n").encode("utf-8")
    )


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(Path(directory), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _seal_expected_payload(
    *,
    test_eval_date: pd.Timestamp,
    model_hashes: Mapping[str, str],
    predictions: pd.DataFrame,
    selection: Mapping[str, object],
    test_label_rows_read_before_seal: int,
) -> dict[str, object]:
    return {
        "stage": STAGE,
        "test_eval_date": pd.Timestamp(test_eval_date).date().isoformat(),
        "model_hashes": dict(sorted(model_hashes.items())),
        "predictions_sha256": _frame_sha256(predictions),
        "selection_sha256": _sha256_bytes(_canonical_json_bytes(dict(selection))),
        "test_label_rows_read_before_seal": int(
            test_label_rows_read_before_seal
        ),
    }


def write_pre_effect_seal(
    seal_dir: Path,
    *,
    test_eval_date: pd.Timestamp,
    model_hashes: Mapping[str, str],
    predictions: pd.DataFrame,
    selection: Mapping[str, object],
    test_label_rows_read_before_seal: int,
) -> Path:
    if test_label_rows_read_before_seal != 0:
        raise Stage002Error("test_label_read_before_seal")
    directory = Path(seal_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{pd.Timestamp(test_eval_date):%Y-%m-%d}.json"
    payload = _seal_expected_payload(
        test_eval_date=test_eval_date,
        model_hashes=model_hashes,
        predictions=predictions,
        selection=selection,
        test_label_rows_read_before_seal=test_label_rows_read_before_seal,
    )
    try:
        with target.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(target.parent)
    except FileExistsError as error:
        raise Stage002Error(f"pre_effect_seal_exists:{target}") from error
    return target


def verify_pre_effect_seal(
    seal_path: Path,
    *,
    model_hashes: Mapping[str, str],
    predictions: pd.DataFrame,
    selection: Mapping[str, object],
) -> dict[str, object]:
    path = Path(seal_path)
    if not path.is_file():
        raise Stage002Error("effect_seal_missing")
    actual = json.loads(path.read_text(encoding="utf-8"))
    expected = _seal_expected_payload(
        test_eval_date=pd.Timestamp(actual["test_eval_date"]),
        model_hashes=model_hashes,
        predictions=predictions,
        selection=selection,
        test_label_rows_read_before_seal=0,
    )
    if actual != expected:
        raise Stage002Error("pre_effect_seal_mismatch")
    return actual


def assess_technical_gates(observed: Mapping[str, object]) -> dict[str, object]:
    gates = {
        "identity_authorization_and_upstream": bool(
            observed.get("input_identity_stable")
        )
        and bool(observed.get("authorization_valid"))
        and bool(observed.get("upstream_bundles_verified")),
        "label_and_feature_contract": int(observed.get("label_rows", -1))
        == 55_226
        and int(observed.get("label_qids", -1)) == 1_046
        and int(observed.get("fixed_label_rows_excluded", -1)) == 1_046
        and int(observed.get("fixed_path_rows_excluded", -1)) == 1_046
        and int(observed.get("fixed_feature_rows_excluded", -1)) == 1_067
        and int(observed.get("fixed_formal_scoring_rows", -1)) == 0
        and int(observed.get("relevance_level_failure_count", -1)) == 0
        and int(observed.get("feature_label_missing_rows", -1)) == 0
        and int(observed.get("forbidden_feature_count", -1)) == 0
        and int(observed.get("formal_score_value_read_count", -1)) == 0,
        "fold_and_estimator_contract": int(observed.get("fold_count", -1)) == 37
        and int(observed.get("fit_call_count", -1)) == 74
        and int(observed.get("future_train_qid_count", -1)) == 0
        and int(observed.get("final_train_qid_count", -1)) == 1_045
        and int(observed.get("final_train_row_count", -1)) == 55_168
        and bool(observed.get("estimator_audit_passed")),
        "determinism_and_model_shape": float(
            observed.get("repeat_prediction_max_abs_difference", np.inf)
        )
        <= 1e-12
        and int(observed.get("repeat_model_hash_mismatch_count", -1)) == 0
        and int(observed.get("constant_prediction_fold_count", -1)) == 0
        and int(observed.get("zero_split_fold_count", -1)) == 0,
        "prediction_and_pre_effect_state_machine": int(
            observed.get("prediction_row_count", -1)
        )
        == 2_000
        and int(observed.get("seal_count", -1)) == 37
        and int(observed.get("verified_seal_count", -1)) == 37
        and int(observed.get("model_file_identity_mismatch_count", -1)) == 0
        and int(observed.get("test_label_rows_read_before_seal", -1)) == 0
        and int(observed.get("effect_fold_count", -1)) == 36
        and int(observed.get("effect_qids_opened", -1)) == 36
        and int(observed.get("effect_label_rows_opened", -1)) == 1_940
        and int(observed.get("inference_fold_count", -1)) == 1,
        "isolated_side_effects": int(observed.get("strategy_backtest_runs", -1))
        == 0
        and int(observed.get("sealed_holdout_rows", -1)) == 0
        and int(observed.get("ctp_connection_count", -1)) == 0
        and int(observed.get("order_api_called_count", -1)) == 0
        and int(observed.get("production_files_written", -1)) == 0,
    }
    return {"passed": all(gates.values()), "gates": gates}


def create_execution_event(
    event_path: Path,
    *,
    authorization_sha256: str,
    nonce: str,
) -> None:
    path = Path(event_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "line_id": LINE_ID,
        "stage": STAGE,
        "status": "started",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "authorization_sha256": authorization_sha256,
        "nonce": nonce,
    }
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(path.parent)
    except FileExistsError as error:
        raise Stage002Error(f"execution_event_exists:{path}") from error


def _complete_execution_event(
    event_path: Path,
    *,
    decision: str,
    final_manifest_sha256: str,
) -> None:
    path = Path(event_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
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
        handle.write(_canonical_json_bytes(payload))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    _fsync_directory(path.parent)


def _implementation_paths() -> dict[str, Path]:
    return {
        "core": LINE_DIR / "tools/trend_quality_ranker_oos.py",
        "runner": Path(__file__),
        "core_tests": LINE_DIR / "tests/test_trend_quality_ranker_oos.py",
        "runner_tests": LINE_DIR / "tests/test_stage002_trend_quality_ranker_oos.py",
        "preregistration": PREREGISTRATION_PATH,
        "plan": PLAN_PATH,
        "initial_independent_review": (
            LINE_DIR / "reviews/20260905_stage002_prerun_independent_review.md"
        ),
        "independent_recheck_pass": (
            LINE_DIR / "reviews/20260905_stage002_prerun_recheck_pass.md"
        ),
        "external_ranker_core": EXTERNAL_RANKER_CORE_PATH,
        "external_feature_contract": EXTERNAL_FEATURE_CONTRACT_PATH,
        "xgboost_sklearn_source": XGBOOST_SKLEARN_SOURCE_PATH,
        "xgboost_native_library": XGBOOST_NATIVE_LIBRARY_PATH,
    }


def _runtime_identity() -> dict[str, str]:
    return {
        "python": (
            f"{sys.version_info.major}.{sys.version_info.minor}."
            f"{sys.version_info.micro}"
        ),
        "xgboost": xgboost.__version__,
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "platform": platform.platform(),
        "machine": platform.machine(),
    }


def verify_authorization(
    authorization_path: Path,
    input_identities: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    path = Path(authorization_path)
    if not path.is_file():
        raise Stage002Error(f"authorization_missing:{path}")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if (
        receipt.get("line_id") != LINE_ID
        or receipt.get("stage") != STAGE
        or receipt.get("authorized") is not True
        or not receipt.get("nonce")
    ):
        raise Stage002Error("authorization_header_invalid")
    expected_inputs = {
        name: identity["sha256"] for name, identity in input_identities.items()
    }
    if receipt.get("input_sha256") != expected_inputs:
        raise Stage002Error("authorization_input_binding_invalid")
    actual_implementation = {
        name: publisher.sha256_file(implementation_path)
        for name, implementation_path in _implementation_paths().items()
    }
    if receipt.get("implementation_sha256") != actual_implementation:
        raise Stage002Error("authorization_implementation_binding_invalid")
    if receipt.get("runtime") != _runtime_identity():
        raise Stage002Error("authorization_runtime_binding_invalid")
    if receipt.get("model_params") != core.MODEL_PARAMS:
        raise Stage002Error("authorization_model_params_invalid")
    if receipt.get("feature_columns") != list(core.MODEL_FEATURES):
        raise Stage002Error("authorization_feature_columns_invalid")
    if receipt.get("selector_contract") != SELECTOR_CONTRACT:
        raise Stage002Error("authorization_selector_contract_invalid")
    if receipt.get("scope") != AUTHORIZATION_SCOPE:
        raise Stage002Error("authorization_scope_invalid")
    return receipt


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_json_bytes(value))


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        frame.to_csv(
            path,
            index=False,
            encoding="utf-8",
            compression={"method": "gzip", "compresslevel": 9, "mtime": 0},
        )
    else:
        frame.to_csv(path, index=False, encoding="utf-8")


def _build_manifest(directory: Path, input_identities: Mapping[str, object]) -> None:
    files = sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.name != "artifact_manifest.json"
    )
    manifest = {
        "artifacts": {
            str(path.relative_to(directory)): {
                "sha256": publisher.sha256_file(path),
                "size": int(path.stat().st_size),
            }
            for path in files
        },
        "input_identities": dict(input_identities),
    }
    _write_json(directory / "artifact_manifest.json", manifest)


def verify_published_bundle(
    final_dir: Path, *, verify_inputs: bool = False
) -> dict[str, object]:
    directory = Path(final_dir).resolve()
    manifest_path = directory / "artifact_manifest.json"
    if not manifest_path.is_file():
        return {"verified": False, "errors": ["manifest_missing"]}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    expected = set(manifest.get("artifacts", {})) | {"artifact_manifest.json"}
    actual = {
        str(path.relative_to(directory))
        for path in directory.rglob("*")
        if path.is_file()
    }
    for name in sorted(actual - expected):
        errors.append(f"unmanifested_artifact:{name}")
    for name in sorted(expected - actual):
        errors.append(f"artifact_missing:{name}")
    for name, identity in manifest.get("artifacts", {}).items():
        artifact_path = directory / name
        if not artifact_path.is_file():
            continue
        if artifact_path.stat().st_size != identity.get("size"):
            errors.append(f"artifact_size_mismatch:{name}")
        if publisher.sha256_file(artifact_path) != identity.get("sha256"):
            errors.append(f"artifact_sha256_mismatch:{name}")
    if verify_inputs:
        for name, identity in manifest.get("input_identities", {}).items():
            input_path = Path(str(identity.get("path", "")))
            if not input_path.is_file():
                errors.append(f"input_missing:{name}")
                continue
            stat = input_path.stat()
            if stat.st_size != identity.get("size"):
                errors.append(f"input_size_mismatch:{name}")
            if stat.st_mtime_ns != identity.get("mtime_ns"):
                errors.append(f"input_mtime_mismatch:{name}")
            if publisher.sha256_file(input_path) != identity.get("sha256"):
                errors.append(f"input_sha256_mismatch:{name}")
    return {
        "verified": not errors,
        "errors": errors,
        "artifact_count": len(manifest.get("artifacts", {})),
        "input_count": len(manifest.get("input_identities", {})),
    }


def _atomic_publish(staging: Path, final_dir: Path) -> None:
    if final_dir.exists():
        raise Stage002Error(f"final_output_exists:{final_dir}")
    os.replace(staging, final_dir)


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage002Error(f"json_root_not_object:{path}")
    return value


def _verify_upstream_bundles() -> dict[str, object]:
    return {
        "stage001": publisher.verify_published_bundle(
            STAGE001_DIR, verify_inputs=False
        ),
        "expiry": publisher.verify_published_bundle(EXPIRY_DIR, verify_inputs=False),
        "v1": v1_stage.verify_published_bundle(V1_DIR, verify_inputs=False),
        "v2": v1_stage.verify_published_bundle(V2_DIR, verify_inputs=False),
    }


def _validate_upstream_summaries(
    summaries: Mapping[str, Mapping[str, object]],
) -> None:
    for name, decision in (
        ("stage001", stage001.PASS_DECISION),
        ("expiry", stage001.UPSTREAM_PASS_DECISION),
    ):
        summary = summaries[name]
        if (
            summary.get("decision") != decision
            or summary.get("all_gates_passed") is not True
        ):
            raise Stage002Error(f"upstream_summary_not_passed:{name}")
    v1_summary = summaries["v1"]
    if (
        v1_summary.get("decision") != v1_stage.FAIL_DECISION
        or v1_summary.get("all_gates_passed") is not False
    ):
        raise Stage002Error("historical_v1_identity_invalid")
    v2_summary = summaries["v2"]
    if (
        v2_summary.get("decision") != V2_PASS_DECISION
        or v2_summary.get("all_gates_passed") is not True
        or v2_summary.get("corrected_contract_decision")
        != v1_stage.PASS_DECISION
    ):
        raise Stage002Error("v2_correction_not_passed")


def _load_inputs(input_paths: Mapping[str, Path]) -> dict[str, object]:
    verifications = _verify_upstream_bundles()
    if not all(bool(value.get("verified")) for value in verifications.values()):
        raise Stage002Error("upstream_bundle_verification_failed")
    summaries = {
        "stage001": _read_json(input_paths["stage001_summary"]),
        "expiry": _read_json(input_paths["expiry_summary"]),
        "v1": _read_json(input_paths["v1_summary"]),
        "v2": _read_json(input_paths["v2_summary"]),
    }
    _validate_upstream_summaries(summaries)
    return {
        "labels": pd.read_csv(input_paths["path_labels"]),
        "paths": pd.read_csv(
            input_paths["expiry_paths"],
            usecols=["query_date", "product_vt_symbol", "label_end"],
        ),
        "model_features": pd.read_csv(input_paths["model_features"]),
        "formal_scoring": pd.read_csv(input_paths["formal_scoring"]),
        "fold_plan": pd.read_csv(input_paths["fold_plan"]),
        "summaries": summaries,
        "upstream_verifications": verifications,
    }


def _parse_bool(series: pd.Series, name: str) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.astype(bool)
    values = series.astype(str).str.strip().str.lower()
    if not values.isin({"true", "false"}).all():
        raise Stage002Error(f"invalid_boolean:{name}")
    return values.eq("true")


def _decision(
    technical_passed: bool,
    predictive_passed: bool,
    effect_passed: bool,
) -> str:
    if not technical_passed:
        return TECHNICAL_FAIL_DECISION
    if predictive_passed and effect_passed:
        return PASS_DECISION
    return EFFECT_FAIL_DECISION


def _report(summary: Mapping[str, object]) -> str:
    predictive = summary.get("predictive_metrics", {})
    effect = summary.get("effect_metrics", {})
    return (
        "# Stage002 趋势质量 XGBRanker 样本外结果\n\n"
        f"- 决策：`{summary['decision']}`\n"
        f"- 技术门：{'通过' if summary.get('technical', {}).get('passed') else '失败'}\n"
        f"- 全截面预测门：{'通过' if summary.get('predictive', {}).get('passed') else '失败或未开放'}\n"
        f"- A/C 路径代理门：{'通过' if summary.get('effect', {}).get('passed') else '失败或未开放'}\n"
        f"- folds/fits：{summary.get('fold_count', 0)}/{summary.get('fit_call_count', 0)}\n"
        f"- mean Rank IC：{predictive.get('mean_rank_ic', 'NA')}\n"
        f"- replacement：{effect.get('replacement_count', 0)}\n"
        f"- 质量差值总和：{effect.get('sum_quality_delta', 'NA')}\n"
        f"- 幅度差值总和：{effect.get('sum_abs_log_return_delta', 'NA')}\n"
        f"- 路径回撤代理差值总和：{effect.get('sum_oriented_max_drawdown_delta', 'NA')}\n"
        "- 本阶段不是策略撮合回测，不代表收益或账户最大回撤改善。\n"
        "- strategy backtest、sealed holdout、CTP、订单和生产写入：全部为0。\n"
    )


def _write_progress_state(
    staging: Path,
    *,
    phase: str,
    current_test_date: pd.Timestamp | None,
    last_completed_fold: pd.Timestamp | None,
    label_store: core.PhaseGatedTrendQualityStore,
    effect_rows: int,
) -> None:
    audit = label_store.audit()
    payload = {
        "phase": phase,
        "current_test_date": (
            pd.Timestamp(current_test_date).date().isoformat()
            if current_test_date is not None
            else None
        ),
        "last_completed_fold": (
            pd.Timestamp(last_completed_fold).date().isoformat()
            if last_completed_fold is not None
            else None
        ),
        "seal_count": len(list((staging / "pre_effect_seals").glob("*.json"))),
        "model_file_count": len(list((staging / "models").glob("*.ubj"))),
        "effect_month_rows_persisted": int(effect_rows),
        "label_access_audit": audit,
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    _write_json(staging / "run_progress.json", payload)
    _write_json(staging / "label_access_audit.json", audit)


def _write_partial_frames(
    staging: Path,
    *,
    prediction_frames: Sequence[pd.DataFrame],
    selections: Sequence[Mapping[str, object]],
    fold_audits: Sequence[Mapping[str, object]],
    rank_rows: Sequence[Mapping[str, object]],
    effect_rows: Sequence[Mapping[str, object]],
    effect_label_frames: Sequence[pd.DataFrame],
) -> None:
    if prediction_frames:
        _write_csv(
            pd.concat(prediction_frames, ignore_index=True),
            staging / "predictions.csv.gz",
        )
    if selections:
        _write_csv(pd.DataFrame(selections), staging / "monthly_selections.csv")
    if fold_audits:
        _write_csv(pd.DataFrame(fold_audits), staging / "fold_audit.csv")
    if rank_rows:
        _write_csv(pd.DataFrame(rank_rows), staging / "predictive_monthly.csv")
    if effect_rows:
        _write_csv(pd.DataFrame(effect_rows), staging / "effect_monthly.csv")
    if effect_label_frames:
        _write_csv(
            pd.concat(effect_label_frames, ignore_index=True),
            staging / "opened_effect_labels.csv.gz",
        )


def _start_effect_access_event(
    staging: Path,
    *,
    test_date: pd.Timestamp,
    expected_row_count: int,
    seal_path: Path,
) -> Path:
    directory = staging / "effect_access_events"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{pd.Timestamp(test_date):%Y-%m-%d}.json"
    payload = {
        "test_eval_date": pd.Timestamp(test_date).date().isoformat(),
        "status": "opening",
        "expected_row_count": int(expected_row_count),
        "seal_sha256": publisher.sha256_file(seal_path),
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    try:
        with target.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(directory)
    except FileExistsError as error:
        raise Stage002Error(f"effect_access_event_exists:{target}") from error
    return target


def _complete_effect_access_event(path: Path, opened: pd.DataFrame) -> None:
    target = Path(path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload.update(
        {
            "status": "opened",
            "opened_row_count": int(len(opened)),
            "opened_labels_sha256": _frame_sha256(opened),
            "completed_at": datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
        }
    )
    temporary = target.with_name(f".{target.name}.tmp.{uuid.uuid4().hex}")
    with temporary.open("xb") as handle:
        handle.write(_canonical_json_bytes(payload))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)
    _fsync_directory(target.parent)


def _open_and_persist_effect_qid(
    staging: Path,
    *,
    label_store: core.PhaseGatedTrendQualityStore,
    test_date: pd.Timestamp,
    seal_path: Path,
    model_hashes: Mapping[str, str],
    predictions: pd.DataFrame,
    selection: Mapping[str, object],
    last_completed_fold: pd.Timestamp | None,
    effect_rows: int,
    effect_label_frames: list[pd.DataFrame],
) -> pd.DataFrame:
    verify_pre_effect_seal(
        seal_path,
        model_hashes=model_hashes,
        predictions=predictions,
        selection=selection,
    )
    label_store.authorize_effect_qid(test_date)
    access_event = _start_effect_access_event(
        staging,
        test_date=test_date,
        expected_row_count=label_store.qid_row_count(test_date),
        seal_path=seal_path,
    )
    opened = label_store.open_effect_qid(test_date)
    _complete_effect_access_event(access_event, opened)
    effect_label_frames.append(opened)
    _write_csv(
        pd.concat(effect_label_frames, ignore_index=True),
        staging / "opened_effect_labels.csv.gz",
    )
    _write_progress_state(
        staging,
        phase="effect_labels_opened",
        current_test_date=test_date,
        last_completed_fold=last_completed_fold,
        label_store=label_store,
        effect_rows=effect_rows,
    )
    return opened


def verify_all_pre_effect_seals(staging: Path) -> dict[str, int]:
    directory = Path(staging)
    models_dir = directory / "models"
    seals_dir = directory / "pre_effect_seals"
    prediction_path = directory / "predictions.csv.gz"
    selection_path = directory / "monthly_selections.csv"
    fold_audit_path = directory / "fold_audit.csv"
    for path in (prediction_path, selection_path, fold_audit_path):
        if not path.is_file():
            raise Stage002Error(f"final_seal_replay_artifact_missing:{path.name}")
    predictions = pd.read_csv(prediction_path, parse_dates=["query_date"])
    selections = pd.read_csv(selection_path, parse_dates=["test_eval_date"])
    fold_audits = pd.read_csv(fold_audit_path, parse_dates=["test_eval_date"])
    prediction_dates = predictions["query_date"].dt.normalize()
    selection_dates = selections["test_eval_date"].dt.normalize()
    audit_dates = fold_audits["test_eval_date"].dt.normalize()
    if selections.duplicated("test_eval_date").any() or fold_audits.duplicated(
        "test_eval_date"
    ).any():
        raise Stage002Error("final_seal_replay_date_duplicate")
    if not (
        set(prediction_dates) == set(selection_dates) == set(audit_dates)
    ):
        raise Stage002Error("final_seal_replay_date_set_mismatch")
    verified = 0
    for audit in fold_audits.to_dict("records"):
        test_date = pd.Timestamp(audit["test_eval_date"]).normalize()
        date_name = f"{test_date:%Y-%m-%d}"
        model_hashes = {
            "primary": str(audit["primary_model_sha256"]),
            "repeat": str(audit["repeat_model_sha256"]),
        }
        for role, expected_hash in model_hashes.items():
            model_path = Path(models_dir) / f"{date_name}_{role}.ubj"
            if not model_path.is_file() or publisher.sha256_file(
                model_path
            ) != expected_hash:
                raise Stage002Error(
                    f"model_file_identity_mismatch:{date_name}:{role}"
                )
        seal_path = Path(seals_dir) / f"{date_name}.json"
        if not seal_path.is_file() or publisher.sha256_file(seal_path) != str(
            audit["pre_effect_seal_sha256"]
        ):
            raise Stage002Error(f"seal_file_identity_mismatch:{date_name}")
        persisted_predictions = predictions.loc[
            prediction_dates.eq(test_date)
        ].copy()
        persisted_selection = selections.loc[
            selection_dates.eq(test_date)
        ]
        if persisted_predictions.empty or len(persisted_selection) != 1:
            raise Stage002Error(f"final_seal_replay_payload_missing:{date_name}")
        selection = persisted_selection.iloc[0].to_dict()
        verify_pre_effect_seal(
            seal_path,
            model_hashes=model_hashes,
            predictions=persisted_predictions,
            selection=selection,
        )
        verified += 1
    return {
        "verified_seal_count": int(verified),
        "model_file_identity_mismatch_count": 0,
    }


def _execute_stage002(
    staging: Path,
    *,
    inputs: Mapping[str, object],
    input_identities: Mapping[str, Mapping[str, object]],
    authorization: Mapping[str, object],
) -> dict[str, object]:
    labels = inputs["labels"].copy()
    paths = inputs["paths"].copy()
    model_features = inputs["model_features"].copy()
    scoring = inputs["formal_scoring"].copy()
    folds = inputs["fold_plan"].copy()
    for frame, columns in (
        (labels, ["query_date"]),
        (paths, ["query_date", "label_end"]),
        (model_features, ["query_date"]),
        (scoring, ["test_eval_date"]),
        (folds, ["test_eval_date", "maximum_train_label_end"]),
    ):
        for column in columns:
            frame[column] = pd.to_datetime(frame[column], errors="raise").dt.normalize()
    folds["effect_evaluable"] = _parse_bool(
        folds["effect_evaluable"], "effect_evaluable"
    )
    folds["inference_only"] = _parse_bool(folds["inference_only"], "inference_only")
    fixed_label_rows_excluded = int(
        labels["product_vt_symbol"].astype(str).eq(core.FIXED_PRODUCT).sum()
    )
    labels, ai_label_audit = core.prepare_ai_universe_labels(labels)
    fixed_path_mask = paths["product_vt_symbol"].astype(str).eq(core.FIXED_PRODUCT)
    fixed_path_rows_excluded = int(fixed_path_mask.sum())
    paths = paths.loc[~fixed_path_mask].copy()
    fixed_feature_mask = model_features["product_vt_symbol"].astype(str).eq(
        core.FIXED_PRODUCT
    )
    fixed_feature_rows_excluded = int(fixed_feature_mask.sum())
    model_features = model_features.loc[~fixed_feature_mask].copy()
    fixed_formal_scoring_rows = int(
        scoring["product_vt_symbol"].astype(str).eq(core.FIXED_PRODUCT).sum()
    )
    if fixed_formal_scoring_rows:
        raise Stage002Error("fixed_product_in_formal_scoring")
    label_store = core.PhaseGatedTrendQualityStore(labels, paths)
    feature_columns = list(core.MODEL_FEATURES)
    forbidden = sorted(
        set(feature_columns)
        & {
            "query_date",
            "product_vt_symbol",
            "main_contract_vt",
            "month",
            "year",
            "formal_score",
            "formal_rank",
            "future_trend_sign",
            *core.LABEL_COLUMNS,
        }
    )
    if list(feature_columns) != list(core.MODEL_FEATURES):
        raise Stage002Error("feature_order_changed")
    feature_label_join = labels[["query_date", "product_vt_symbol"]].merge(
        model_features[["query_date", "product_vt_symbol"]],
        on=["query_date", "product_vt_symbol"],
        how="left",
        indicator=True,
        validate="one_to_one",
    )
    feature_label_missing_rows = int(feature_label_join["_merge"].ne("both").sum())
    formal_score_value_read_count = int(
        scoring["formal_score_value_read"]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin({"true", "1"})
        .sum()
    )
    estimator_audit = core.build_estimator_audit(XGBRanker, core.MODEL_PARAMS)
    if not estimator_audit["passed"]:
        raise Stage002Error("estimator_audit_failed")

    staging.mkdir(parents=True)
    models_dir = staging / "models"
    seals_dir = staging / "pre_effect_seals"
    models_dir.mkdir()
    seals_dir.mkdir()
    prediction_frames: list[pd.DataFrame] = []
    selections: list[dict[str, object]] = []
    fold_audits: list[dict[str, object]] = []
    rank_rows: list[dict[str, object]] = []
    effect_rows: list[dict[str, object]] = []
    effect_label_frames: list[pd.DataFrame] = []
    fit_call_count = 0
    last_completed_fold: pd.Timestamp | None = None
    _write_progress_state(
        staging,
        phase="initialized",
        current_test_date=None,
        last_completed_fold=None,
        label_store=label_store,
        effect_rows=0,
    )

    ordered_folds = folds.sort_values("test_eval_date", kind="mergesort")
    for fold in ordered_folds.itertuples(index=False):
        test_date = pd.Timestamp(fold.test_eval_date).normalize()
        _write_progress_state(
            staging,
            phase="fold_started",
            current_test_date=test_date,
            last_completed_fold=last_completed_fold,
            label_store=label_store,
            effect_rows=len(effect_rows),
        )
        training_labels = label_store.open_training_labels(test_date)
        train_qids = int(training_labels["query_date"].nunique())
        if train_qids != int(fold.train_qid_count):
            raise Stage002Error(
                f"fold_train_qid_count_mismatch:{test_date.date()}:"
                f"{train_qids}:{fold.train_qid_count}"
            )
        train = model_features.merge(
            training_labels[
                [
                    "query_date",
                    "product_vt_symbol",
                    "label_end",
                    "trend_quality_relevance",
                ]
            ],
            on=["query_date", "product_vt_symbol"],
            how="inner",
            validate="one_to_one",
        )
        if len(train) != len(training_labels):
            raise Stage002Error(f"training_feature_join_mismatch:{test_date.date()}")
        if train["label_end"].ge(test_date).any():
            raise Stage002Error(f"future_training_label:{test_date.date()}")
        train = train.rename(columns={"trend_quality_relevance": "relevance"})
        _, train_x, train_y, train_qid = core.build_ranker_arrays(
            train, feature_columns
        )

        test_features = model_features[
            model_features["query_date"].eq(test_date)
        ].sort_values("product_vt_symbol", kind="mergesort")
        if test_features.empty:
            raise Stage002Error(f"test_features_missing:{test_date.date()}")
        test_scoring = scoring[scoring["test_eval_date"].eq(test_date)].copy()
        if test_scoring.empty:
            raise Stage002Error(f"test_scoring_missing:{test_date.date()}")
        if not set(test_scoring["product_vt_symbol"]).issubset(
            set(test_features["product_vt_symbol"])
        ):
            raise Stage002Error(f"test_scoring_feature_missing:{test_date.date()}")
        predict_x = test_features[feature_columns].apply(
            pd.to_numeric, errors="coerce"
        ).astype(float)
        fitted = core.fit_repeated_ranker(
            train_x,
            train_y,
            train_qid,
            predict_x,
            params=core.MODEL_PARAMS,
            tolerance=1e-12,
            ranker_factory=XGBRanker,
        )
        fit_call_count += 2
        date_name = f"{test_date:%Y-%m-%d}"
        primary_path = models_dir / f"{date_name}_primary.ubj"
        repeat_path = models_dir / f"{date_name}_repeat.ubj"
        primary_path.write_bytes(fitted["primary_model_raw"])
        repeat_path.write_bytes(fitted["repeat_model_raw"])
        predicted = test_features[["query_date", "product_vt_symbol"]].copy()
        predicted["xgb_score"] = fitted["predictions"]
        predicted["train_qid_count"] = train_qids
        predicted["train_row_count"] = int(len(train))
        selection = core.select_consensus_one_slot(
            predicted,
            test_scoring,
            top_k=int(SELECTOR_CONTRACT["xgb_top_k"]),
        )
        selection["effect_evaluable"] = bool(fold.effect_evaluable)
        selection["inference_only"] = bool(fold.inference_only)
        selection["train_qid_count"] = train_qids
        model_hashes = {
            "primary": str(fitted["primary_model_sha256"]),
            "repeat": str(fitted["repeat_model_sha256"]),
        }
        before_seal = label_store.label_rows_opened_for(test_date)
        seal_path = write_pre_effect_seal(
            seals_dir,
            test_eval_date=test_date,
            model_hashes=model_hashes,
            predictions=predicted,
            selection=selection,
            test_label_rows_read_before_seal=before_seal,
        )
        _write_progress_state(
            staging,
            phase="pre_effect_sealed",
            current_test_date=test_date,
            last_completed_fold=last_completed_fold,
            label_store=label_store,
            effect_rows=len(effect_rows),
        )
        verify_pre_effect_seal(
            seal_path,
            model_hashes=model_hashes,
            predictions=predicted,
            selection=selection,
        )
        if bool(fold.effect_evaluable):
            test_labels = _open_and_persist_effect_qid(
                staging,
                label_store=label_store,
                test_date=test_date,
                seal_path=seal_path,
                model_hashes=model_hashes,
                predictions=predicted,
                selection=selection,
                last_completed_fold=last_completed_fold,
                effect_rows=len(effect_rows),
                effect_label_frames=effect_label_frames,
            )
            scored_labels = predicted.merge(
                test_labels,
                on=["query_date", "product_vt_symbol"],
                how="inner",
                validate="one_to_one",
            )
            if len(scored_labels) != len(test_labels):
                raise Stage002Error(f"test_prediction_label_join_mismatch:{test_date.date()}")
            rank_rows.append(core.compute_month_rank_metrics(scored_labels, k=10))
            effect_rows.append(core.build_effect_row(selection, test_labels))
        prediction_frames.append(predicted)
        selections.append(selection)
        fold_audits.append(
            {
                "test_eval_date": test_date,
                "train_qid_count": train_qids,
                "train_row_count": int(len(train)),
                "maximum_train_label_end": train["label_end"].max(),
                "test_row_count": int(len(predicted)),
                "effect_evaluable": bool(fold.effect_evaluable),
                "inference_only": bool(fold.inference_only),
                "primary_model_sha256": fitted["primary_model_sha256"],
                "repeat_model_sha256": fitted["repeat_model_sha256"],
                "prediction_repeat_max_abs_difference": fitted[
                    "prediction_repeat_max_abs_difference"
                ],
                "unique_prediction_count": fitted["unique_prediction_count"],
                "split_count": fitted["split_count"],
                "pre_effect_seal_sha256": publisher.sha256_file(seal_path),
                "test_label_rows_read_before_seal": before_seal,
            }
        )
        last_completed_fold = test_date
        _write_partial_frames(
            staging,
            prediction_frames=prediction_frames,
            selections=selections,
            fold_audits=fold_audits,
            rank_rows=rank_rows,
            effect_rows=effect_rows,
            effect_label_frames=effect_label_frames,
        )
        _write_progress_state(
            staging,
            phase="fold_completed",
            current_test_date=test_date,
            last_completed_fold=last_completed_fold,
            label_store=label_store,
            effect_rows=len(effect_rows),
        )

    seal_replay = verify_all_pre_effect_seals(staging)
    predictions = pd.concat(prediction_frames, ignore_index=True)
    monthly_selections = pd.DataFrame(selections).sort_values(
        "test_eval_date", kind="mergesort"
    )
    fold_audit = pd.DataFrame(fold_audits).sort_values(
        "test_eval_date", kind="mergesort"
    )
    predictive_monthly = pd.DataFrame(rank_rows).sort_values(
        "test_eval_date", kind="mergesort"
    )
    effect_monthly = pd.DataFrame(effect_rows).sort_values(
        "test_eval_date", kind="mergesort"
    )
    opened_effect_labels = pd.concat(effect_label_frames, ignore_index=True)
    label_access = label_store.audit()
    observed = {
        "input_identity_stable": True,
        "authorization_valid": True,
        "upstream_bundles_verified": all(
            value.get("verified")
            for value in inputs["upstream_verifications"].values()
        ),
        "label_rows": int(label_access["label_rows"]),
        "label_qids": int(label_access["label_qids"]),
        "fixed_label_rows_excluded": fixed_label_rows_excluded,
        "fixed_path_rows_excluded": fixed_path_rows_excluded,
        "fixed_feature_rows_excluded": fixed_feature_rows_excluded,
        "fixed_formal_scoring_rows": fixed_formal_scoring_rows,
        "relevance_level_failure_count": int(
            ai_label_audit["relevance_level_failure_count"]
        ),
        "feature_label_missing_rows": feature_label_missing_rows,
        "forbidden_feature_count": int(len(forbidden)),
        "formal_score_value_read_count": formal_score_value_read_count,
        "fold_count": int(len(fold_audit)),
        "fit_call_count": int(fit_call_count),
        "future_train_qid_count": int(
            pd.to_datetime(fold_audit["maximum_train_label_end"])
            .ge(pd.to_datetime(fold_audit["test_eval_date"]))
            .sum()
        ),
        "final_train_qid_count": int(fold_audit.iloc[-1]["train_qid_count"]),
        "final_train_row_count": int(fold_audit.iloc[-1]["train_row_count"]),
        "estimator_audit_passed": bool(estimator_audit["passed"]),
        "repeat_prediction_max_abs_difference": float(
            fold_audit["prediction_repeat_max_abs_difference"].max()
        ),
        "repeat_model_hash_mismatch_count": int(
            fold_audit["primary_model_sha256"]
            .ne(fold_audit["repeat_model_sha256"])
            .sum()
        ),
        "constant_prediction_fold_count": int(
            fold_audit["unique_prediction_count"].lt(2).sum()
        ),
        "zero_split_fold_count": int(fold_audit["split_count"].lt(1).sum()),
        "prediction_row_count": int(len(predictions)),
        "seal_count": len(list(seals_dir.glob("*.json"))),
        "verified_seal_count": int(seal_replay["verified_seal_count"]),
        "model_file_identity_mismatch_count": int(
            seal_replay["model_file_identity_mismatch_count"]
        ),
        "test_label_rows_read_before_seal": int(
            fold_audit["test_label_rows_read_before_seal"].sum()
        ),
        "effect_fold_count": int(fold_audit["effect_evaluable"].astype(bool).sum()),
        "effect_qids_opened": int(label_access["opened_effect_qids"]),
        "effect_label_rows_opened": int(
            label_access["unique_effect_label_rows_opened"]
        ),
        "inference_fold_count": int(fold_audit["inference_only"].astype(bool).sum()),
        "strategy_backtest_runs": 0,
        "sealed_holdout_rows": 0,
        "ctp_connection_count": 0,
        "order_api_called_count": 0,
        "production_files_written": 0,
    }
    technical = assess_technical_gates(observed)
    if technical["passed"]:
        predictive_metrics = core.compute_predictive_metrics(predictive_monthly)
        predictive = core.assess_predictive_gates(predictive_metrics)
        effect_metrics = core.compute_effect_metrics(effect_monthly)
        effect = core.assess_effect_gates(effect_metrics)
    else:
        predictive_metrics = {}
        predictive = {"passed": False, "gates": {}, "not_opened": True}
        effect_metrics = {}
        effect = {"passed": False, "gates": {}, "not_opened": True}
    decision = _decision(
        bool(technical["passed"]),
        bool(predictive["passed"]),
        bool(effect["passed"]),
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
        "label_access_audit": label_access,
        "ai_universe_label_audit": ai_label_audit,
        "fixed_product_excluded_from_model_universe": core.FIXED_PRODUCT,
        "estimator_audit": estimator_audit,
        "model_params": core.MODEL_PARAMS,
        "feature_columns": feature_columns,
        "selector_contract": SELECTOR_CONTRACT,
        "authorization_nonce": authorization["nonce"],
        "development_oos_only": True,
        "physical_label_artifact_loaded_before_fit": True,
        "logical_test_label_access_gated_by_seal": True,
        "sealed_holdout_used": False,
        "proxy_metrics_are_not_strategy_pnl_or_account_drawdown": True,
        "independent_reviewer_required": True,
    }
    _write_csv(predictions, staging / "predictions.csv.gz")
    _write_csv(monthly_selections, staging / "monthly_selections.csv")
    _write_csv(fold_audit, staging / "fold_audit.csv")
    _write_csv(predictive_monthly, staging / "predictive_monthly.csv")
    _write_csv(effect_monthly, staging / "effect_monthly.csv")
    _write_csv(opened_effect_labels, staging / "opened_effect_labels.csv.gz")
    _write_json(staging / "summary.json", summary)
    _write_json(staging / "input_identities.json", input_identities)
    _write_json(staging / "authorization_receipt.json", authorization)
    _write_json(staging / "upstream_verification.json", inputs["upstream_verifications"])
    (staging / "report.md").write_text(_report(summary), encoding="utf-8")
    return summary


def _publish_failure(
    staging: Path,
    *,
    error: Exception,
    input_identities: Mapping[str, object],
    authorization: Mapping[str, object],
) -> dict[str, object]:
    staging.mkdir(parents=True, exist_ok=True)
    progress_path = staging / "run_progress.json"
    progress = (
        json.loads(progress_path.read_text(encoding="utf-8"))
        if progress_path.is_file()
        else {}
    )
    label_audit_path = staging / "label_access_audit.json"
    label_audit = (
        json.loads(label_audit_path.read_text(encoding="utf-8"))
        if label_audit_path.is_file()
        else {}
    )
    access_events: list[dict[str, object]] = []
    for event_path in sorted((staging / "effect_access_events").glob("*.json")):
        access_events.append(json.loads(event_path.read_text(encoding="utf-8")))
    event_effect_rows = sum(
        int(event.get("opened_row_count", event.get("expected_row_count", 0)))
        for event in access_events
    )
    effect_rows_opened = max(
        int(label_audit.get("unique_effect_label_rows_opened", 0)),
        int(event_effect_rows),
    )
    summary = {
        "line_id": LINE_ID,
        "stage": STAGE,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": TECHNICAL_FAIL_DECISION,
        "all_gates_passed": False,
        "technical": {"passed": False, "gates": {}},
        "predictive": {"passed": False, "not_opened": True, "gates": {}},
        "effect": {
            "passed": False,
            "not_opened": effect_rows_opened == 0,
            "partial_effect_label_rows_opened": effect_rows_opened,
            "gates": {},
        },
        "error_type": type(error).__name__,
        "error": str(error),
        "failure_phase": progress.get("phase", "before_progress_initialization"),
        "current_test_date": progress.get("current_test_date"),
        "last_completed_fold": progress.get("last_completed_fold"),
        "seal_count": len(list((staging / "pre_effect_seals").glob("*.json"))),
        "model_file_count": len(list((staging / "models").glob("*.ubj"))),
        "label_access_audit": label_audit,
        "effect_access_event_count": int(len(access_events)),
        "effect_access_event_statuses": [
            str(event.get("status")) for event in access_events
        ],
        "partial_artifacts_preserved": True,
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


def run_stage002(
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
        raise Stage002Error(f"final_output_exists:{final_path}")
    identities_before = publisher.collect_input_identities(
        input_paths, expected_sha256
    )
    authorization = verify_authorization(authorization_path, identities_before)
    authorization_sha = publisher.sha256_file(authorization_path)
    create_execution_event(
        event_path,
        authorization_sha256=authorization_sha,
        nonce=str(authorization["nonce"]),
    )
    final_path.parent.mkdir(parents=True, exist_ok=True)
    staging = final_path.parent / f".stage002.tmp.{uuid.uuid4().hex}"
    try:
        inputs = _load_inputs(input_paths)
        summary = _execute_stage002(
            staging,
            inputs=inputs,
            input_identities=identities_before,
            authorization=authorization,
        )
        identities_after = publisher.collect_input_identities(
            input_paths, expected_sha256
        )
        if identities_before != identities_after:
            raise Stage002Error("input_identity_changed_during_run")
        summary["input_identities_before"] = identities_before
        summary["input_identities_after"] = identities_after
        _write_json(staging / "summary.json", summary)
        _build_manifest(staging, identities_before)
        staging_verification = verify_published_bundle(staging)
        if not staging_verification["verified"]:
            raise Stage002Error(
                "staging_manifest_invalid:"
                + ",".join(staging_verification["errors"])
            )
        _atomic_publish(staging, final_path)
        final_verification = verify_published_bundle(final_path, verify_inputs=True)
        if not final_verification["verified"]:
            raise Stage002Error(
                "final_manifest_invalid:" + ",".join(final_verification["errors"])
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
            _build_manifest(staging, identities_before)
            failure_verification = verify_published_bundle(staging)
            if not failure_verification["verified"]:
                raise Stage002Error(
                    "failure_staging_manifest_invalid:"
                    + ",".join(failure_verification["errors"])
                )
            _atomic_publish(staging, final_path)
            final_verification = verify_published_bundle(
                final_path, verify_inputs=True
            )
            if not final_verification["verified"]:
                raise Stage002Error(
                    "failure_final_manifest_invalid:"
                    + ",".join(final_verification["errors"])
                )
        except Exception as terminal_error:
            _complete_execution_event(
                event_path,
                decision=TECHNICAL_FAIL_DECISION,
                final_manifest_sha256="",
            )
            raise Stage002Error(
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
        description="Stage002 trend-quality XGBRanker development OOS"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.verify_only:
        result = verify_published_bundle(DEFAULT_OUTPUT_DIR, verify_inputs=True)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["verified"] else 1
    try:
        summary = run_stage002()
    except (Stage002Error, core.TrendQualityRankerError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, default=_json_default))
    return 0 if summary["decision"] == PASS_DECISION else 2


if __name__ == "__main__":
    raise SystemExit(main())
