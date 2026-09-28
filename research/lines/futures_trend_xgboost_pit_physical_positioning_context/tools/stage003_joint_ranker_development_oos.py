"""Frozen Stage003 joint-ranker runner and fail-closed execution primitives."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
import os
import platform
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Mapping, Protocol

import numpy as np
import pandas as pd
import sklearn
import xgboost


LINE_DIR = Path(__file__).resolve().parents[1]
RESEARCH_LINES_DIR = LINE_DIR.parent
CONTRACT_PATH = LINE_DIR / "contracts/stage003_joint_ranker_development_oos_training_contract.json"
AUTHORIZATION_PATH = LINE_DIR / "authorizations/stage003_joint_ranker_development_oos_authorization.json"
STAGE002_OUT = LINE_DIR / "artifacts/stage002_physical_features"
STAGE002_FEATURE_PANEL_PATH = STAGE002_OUT / "model_eligible_feature_panel.csv"
STAGE002_MONTH_ELIGIBILITY_PATH = STAGE002_OUT / "month_eligibility.csv"
STAGE002_SUMMARY_PATH = STAGE002_OUT / "stage002_summary.json"
STAGE002_MANIFEST_PATH = STAGE002_OUT / "artifact_manifest.json"
UPSTREAM_LINE_DIR = RESEARCH_LINES_DIR / "futures_trend_xgboost_pit_curve_account_labels"
STAGE003_METADATA_OUT = UPSTREAM_LINE_DIR / "artifacts/stage003_account_label_plan"
FULL_FEATURE_SPLIT_PATH = STAGE003_METADATA_OUT / "full_feature_split.csv"
DEVELOPMENT_JOBS_PATH = STAGE003_METADATA_OUT / "development_jobs.csv"
STAGE003_METADATA_SUMMARY_PATH = STAGE003_METADATA_OUT / "stage003_summary.json"
STAGE005_CAMPAIGN_DIR = (
    UPSTREAM_LINE_DIR
    / "artifacts/stage005_development_label_batch/campaigns/"
    "campaign_20260902T214308+0800_13888"
)
STAGE005_DECISION_PATH = STAGE005_CAMPAIGN_DIR / "decision.json"
DEVELOPMENT_LABELS_AGGREGATE_PATH = STAGE005_CAMPAIGN_DIR / "development_labels.csv"
RECONCILIATION_AGGREGATE_PATH = STAGE005_CAMPAIGN_DIR / "reconciliation.csv"
STAGE005_MANIFEST_PATH = STAGE005_CAMPAIGN_DIR / "artifact_manifest.json"
LABEL_ROOT = STAGE005_CAMPAIGN_DIR / "job_outputs"
STAGE005_POSTRUN_REVIEW_PATH = (
    UPSTREAM_LINE_DIR / "reviews/20260903_stage005_postrun_independent_review.md"
)
STAGE005_POSTRUN_DECISION_PATH = (
    UPSTREAM_LINE_DIR / "reviews/20260903_stage005_postrun_review_decision.json"
)
RUNTIME_IDENTITY_PATH = (
    UPSTREAM_LINE_DIR
    / "artifacts/stage006_dual_ranker_development_oos/runtime_identity.json"
)

MODEL_FEATURES: Final = [
    "formal_probability_delta_vs_rank10",
    "basis_dom_rate_delta_vs_rank10",
    "basis_near_rate_delta_vs_rank10",
    "member_net_position_ratio_delta_vs_rank10",
    "member_net_position_change_ratio_delta_vs_rank10",
    "member_turnover_pressure_ratio_delta_vs_rank10",
]
PHYSICAL_FEATURES: Final = MODEL_FEATURES[1:]
FULL_SPLIT_ALLOWED_COLUMNS: Final = [
    "eval_date",
    "next_eval_date",
    "product_vt_symbol",
    "a_rank",
    "split",
    "pit_logistic_probability",
]
METADATA_JOIN_KEYS: Final = ["eval_date", "product_vt_symbol", "a_rank"]
PROBABILITY_DELTA_ABSOLUTE_TOLERANCE: Final = 1e-12
FROZEN_INPUT_SHA_KEYS: Final = [
    "development_jobs",
    "development_labels_aggregate",
    "full_feature_split",
    "reconciliation_aggregate",
    "runtime_identity",
    "stage002_feature_panel",
    "stage002_manifest",
    "stage002_month_eligibility",
    "stage002_summary",
    "stage003_metadata_summary",
    "stage005_decision",
    "stage005_manifest",
    "stage005_postrun_decision",
    "stage005_postrun_review",
]
JOB_ALLOWED_COLUMNS: Final = [
    "eval_date",
    "next_eval_date",
    "product_vt_symbol",
    "candidate_rank",
    "split",
    "job_type",
    "job_id",
    "eligibility_key",
    "eligibility_sha256",
]
DEVELOPMENT_LABEL_HEADER: Final = [
    "job_id",
    "job_type",
    "eval_date",
    "next_eval_date",
    "product_vt_symbol",
    "candidate_rank",
    "base_equity",
    "end_equity",
    "future_return",
    "future_max_drawdown",
    "future_net_pnl",
    "future_slippage",
    "future_trade_count",
    "future_trading_days",
]
RECONCILIATION_HEADER: Final = [
    "job_id",
    "eval_date",
    "candidate_rank",
    "base_equity_delta",
    "end_equity_delta_vs_net_pnl_delta_error",
    "return_delta",
    "drawdown_improvement",
    "net_pnl_delta",
    "slippage_delta",
    "trade_count_delta",
    "end_equity_vs_net_pnl_error",
    "curve_net_pnl_error",
    "curve_slippage_error",
    "combined_net_pnl_error",
    "combined_slippage_error",
    "curve_trade_count_error",
    "combined_trade_count_error",
    "trade_rows_error",
]
LABEL_VALUE_COLUMNS: Final = [
    "base_equity",
    "end_equity",
    "future_return",
    "future_max_drawdown",
    "future_net_pnl",
    "future_slippage",
    "future_trade_count",
    "future_trading_days",
]
LABEL_METADATA_COLUMNS: Final = [
    "eval_date",
    "next_eval_date",
    "product_vt_symbol",
    "a_rank",
    "split",
    "job_type",
    "job_id",
    "eligibility_key",
    "eligibility_sha256",
]
MODEL_PARAMS: Final = {
    "objective": "rank:ndcg",
    "eval_metric": "ndcg",
    "n_estimators": 32,
    "max_depth": 2,
    "learning_rate": 0.03,
    "min_child_weight": 1,
    "gamma": 0,
    "subsample": 1,
    "colsample_bytree": 1,
    "reg_alpha": 0,
    "reg_lambda": 5,
    "tree_method": "hist",
    "lambdarank_pair_method": "mean",
    "lambdarank_num_pair_per_sample": 1,
    "lambdarank_normalization": True,
    "lambdarank_score_normalization": True,
    "ndcg_exp_gain": False,
    "random_state": 42,
    "n_jobs": 1,
}
BOUND_FILE_KEYS: Final = [
    "stage003_original_preregistration",
    "stage003_remediation_preregistration",
    "stage003_initial_review",
    "stage003_initial_review_decision",
    "stage003_rereview",
    "stage003_rereview_decision",
    "stage003_probability_gap_review",
    "stage003_probability_gap_review_decision",
    "stage003_probability_remediation_preregistration",
    "stage003_probability_remediation_rereview",
    "stage003_probability_remediation_rereview_decision",
    "stage003_full_split_sha_gap_review",
    "stage003_full_split_sha_gap_review_decision",
    "stage003_full_split_sha_remediation_preregistration",
    "stage003_full_split_sha_remediation_rereview",
    "stage003_full_split_sha_remediation_rereview_decision",
    "stage003_final_implementation_block_review",
    "stage003_final_implementation_block_review_decision",
    "stage003_final_implementation_remediation_preregistration",
    "training_contract",
    "runner",
    "test_contract",
    "test_state_machine",
    "test_adversarial",
    "runtime_identity",
    "final_implementation_review",
    "final_implementation_review_decision",
]
AUTHORIZATION_KEYS: Final = {
    "decision",
    "scope",
    "nonce",
    "bound_files",
    "result_dir",
    "consumption_receipt_path",
}
RECEIPT_KEYS: Final = {
    "decision",
    "scope",
    "nonce",
    "authorization_path",
    "authorization_sha256",
    "bound_files_identity_sha256",
    "result_dir",
}
ACTIVE_SEAL_KEYS: Final = {
    "seal_type",
    "eval_date",
    "label_read_count_before_seal",
    "primary_model_sha256",
    "repeat_model_sha256",
    "fold_input_sha256",
    "prediction_sha256",
    "selection_sha256",
}
FALLBACK_SEAL_KEYS: Final = {
    "seal_type",
    "eval_date",
    "reason",
    "arm_a",
    "arm_b",
    "arm_c",
    "label_read_count_before_seal",
    "label_read_count_after_seal",
}
FOLD_INPUT_KEYS: Final = {
    "eval_date",
    "feature_order",
    "qid",
    "group_boundaries",
    "ordered_training_job_identities",
    "ordered_test_keys",
}
PREDICTION_KEYS: Final = {"eval_date", "ordered_rows"}
PREDICTION_ROW_KEYS: Final = {
    "eval_date",
    "product_vt_symbol",
    "a_rank",
    "pit_logistic_probability",
    "primary_xgb_score",
    "repeat_xgb_score",
    "lr_percentile",
    "xgb_percentile",
    "ensemble_score",
}
SELECTION_KEYS: Final = {"eval_date", "arm_a", "arm_b", "arm_c", "tie_break_trace"}
ARM_KEYS: Final = {"a_rank", "product_vt_symbol"}
EFFECT_GATE_KEYS: Final = [
    "replacement_count_and_year_coverage",
    "replacement_product_diversity",
    "total_return_delta_positive",
    "total_drawdown_improvement_positive",
    "leave_best_out_return_delta_positive",
    "leave_best_out_drawdown_improvement_positive",
    "each_year_return_delta_nonnegative",
    "each_year_drawdown_improvement_nonnegative",
    "joint_positive_replacement_rate",
    "median_replacement_return_delta_nonnegative",
    "median_replacement_drawdown_improvement_nonnegative",
]
TECHNICAL_GATE_KEYS: Final = [
    "machine_contract_exact",
    "authorization_and_inputs_three_point_exact",
    "runtime_identity_three_point_exact",
    "metadata_and_fold_plan_exact",
    "feature_order_and_values_exact",
    "estimator_class_and_params_exact",
    "fit_count_exact",
    "repeat_predictions_exact",
    "repeat_model_bytes_exact",
    "test_predictions_nondegenerate",
    "physical_feature_splits_exact",
    "active_and_fallback_seals_exact",
    "selection_recomputed_before_effect_open",
    "label_access_state_machine_exact",
    "holdout_and_execution_scope_zero",
]
FINAL_IMPLEMENTATION_ALLOW_DECISION: Final = (
    "ALLOW_STAGE003_ONE_TIME_RUN_AUTHORIZATION_REQUEST"
)
GOVERNANCE_DECISION_PAIRS: Final = [
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
        FINAL_IMPLEMENTATION_ALLOW_DECISION,
    ),
]
CHECKPOINT_NAMES: Final = [
    "before_training",
    "after_all_models",
    "after_effect_evaluation",
]
EVENT_TYPES: Final = {
    "active_seal_verified",
    "aggregate_header_verified",
    "artifact_created",
    "ctp_connection",
    "effect_evaluation",
    "early_stopping_run",
    "eligibility_file_verified",
    "fallback_seal_verified",
    "fit_completed",
    "fit_started",
    "label_file_read",
    "order_api_call",
    "prediction_completed",
    "production_write",
    "search_operation",
    "selection_created",
    "selection_recomputed",
    "training_label_used",
    "training_entrypoint_started",
    "true_engine_run",
    "unexpected_command",
}
STATIC_SCOPE_COUNT_KEYS: Final = [
    "parameter_searches",
    "feature_searches",
    "seed_searches",
    "early_stopping_runs",
    "true_engine_runs",
    "production_writes",
    "ctp_connections",
    "order_api_calls",
    "unexpected_commands",
]
STATIC_ALLOWED_IMPORT_DECLARATIONS: Final = {
    "from:__future__:annotations:",
    "from:datetime:datetime:",
    "from:pathlib:Path:",
    "from:typing:Any:",
    "from:typing:Final:",
    "from:typing:Mapping:",
    "from:typing:Protocol:",
    "import:ast:",
    "import:csv:",
    "import:hashlib:",
    "import:json:",
    "import:math:",
    "import:numpy:np",
    "import:os:",
    "import:pandas:pd",
    "import:platform:",
    "import:re:",
    "import:sklearn:",
    "import:sys:",
    "import:xgboost:",
}
STATIC_ALLOWED_OS_CALLS: Final = {
    "os.close",
    "os.fsync",
    "os.link",
    "os.mkdir",
    "os.open",
    "os.rename",
    "os.write",
}
EXECUTION_SCOPE_COUNTS: Final = {
    "authorized_training_entrypoint_invocations": 1,
    "primary_fit_calls": 13,
    "repeat_fit_calls": 13,
    "total_fit_calls": 26,
    "parameter_searches": 0,
    "feature_searches": 0,
    "seed_searches": 0,
    "early_stopping_runs": 0,
    "extra_fit_calls": 0,
    "rerun_selection_runs": 0,
    "holdout_predictions": 0,
    "holdout_label_reads_or_generations": 0,
    "true_engine_runs": 0,
    "production_writes": 0,
    "ctp_connections": 0,
    "order_api_calls": 0,
    "unexpected_commands": 0,
    "unexpected_artifacts": 0,
}
LOWER_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


class Stage003Error(RuntimeError):
    """Base Stage003 failure."""


class Stage003AuthorizationError(Stage003Error):
    """Authorization identity or one-shot consumption failure."""


class Stage003SealError(Stage003Error):
    """Pre-effect payload or seal validation failure."""


class LabelStore(Protocol):
    def load(self, job_ids: list[str]) -> list[dict[str, Any]]: ...


class ExecutionEventLedger:
    """Append-only in-memory evidence for controlled Stage003 operations."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    def record(self, event_type: str, **details: Any) -> int:
        if event_type not in EVENT_TYPES or any(
            key in {"sequence", "event_type"} for key in details
        ):
            raise Stage003Error(f"event_invalid:{event_type}")
        event = {
            "sequence": len(self._events) + 1,
            "event_type": event_type,
            **details,
        }
        _canonical_json_bytes(event, newline=False)
        self._events.append(event)
        return int(event["sequence"])

    def events(self) -> list[dict[str, Any]]:
        return json.loads(
            _canonical_json_bytes(self._events, newline=False).decode("utf-8")
        )


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_identity(path: Path, *, expected_sha256: str, name: str) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise Stage003Error(f"frozen_input_path_invalid:{name}")
    before = path.stat()
    digest = _sha256_file(path)
    after = path.stat()
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
        raise Stage003Error(f"frozen_input_changed_while_hashing:{name}")
    if digest != expected_sha256:
        raise Stage003Error(f"frozen_input_sha256_mismatch:{name}")
    return {
        "path": str(path.resolve()),
        "size": int(after.st_size),
        "sha256": digest,
        "device": int(after.st_dev),
        "inode": int(after.st_ino),
        "mtime_ns": int(after.st_mtime_ns),
        "ctime_ns": int(after.st_ctime_ns),
    }


def _verify_file_identities(
    paths: Mapping[str, Path], expected_sha256: Mapping[str, str]
) -> dict[str, dict[str, Any]]:
    if set(paths) != set(expected_sha256):
        raise Stage003Error("frozen_input_identity_keys_mismatch")
    return {
        name: _file_identity(path, expected_sha256=expected_sha256[name], name=name)
        for name, path in paths.items()
    }


def _verify_csv_identity_and_header_only(
    path: Path, *, expected_sha256: str, expected_header: list[str]
) -> dict[str, Any]:
    identity = _file_identity(
        path, expected_sha256=expected_sha256, name=Path(path).name
    )
    try:
        with Path(path).open("rb") as stream:
            header_bytes = stream.readline()
        header_text = header_bytes.decode("utf-8-sig").rstrip("\r\n")
        header = next(csv.reader([header_text]))
    except (OSError, UnicodeDecodeError, csv.Error, StopIteration) as exc:
        raise Stage003Error(f"aggregate_header_invalid:{Path(path).name}") from exc
    if header != expected_header:
        raise Stage003Error(f"aggregate_header_mismatch:{Path(path).name}")
    return {**identity, "header": header, "data_rows_parsed": 0}


def _frozen_data_paths() -> dict[str, Path]:
    return {
        "stage002_feature_panel": STAGE002_FEATURE_PANEL_PATH,
        "stage002_month_eligibility": STAGE002_MONTH_ELIGIBILITY_PATH,
        "stage002_summary": STAGE002_SUMMARY_PATH,
        "stage002_manifest": STAGE002_MANIFEST_PATH,
        "full_feature_split": FULL_FEATURE_SPLIT_PATH,
        "development_jobs": DEVELOPMENT_JOBS_PATH,
        "stage003_metadata_summary": STAGE003_METADATA_SUMMARY_PATH,
        "stage005_decision": STAGE005_DECISION_PATH,
        "stage005_manifest": STAGE005_MANIFEST_PATH,
        "stage005_postrun_review": STAGE005_POSTRUN_REVIEW_PATH,
        "stage005_postrun_decision": STAGE005_POSTRUN_DECISION_PATH,
        "runtime_identity": RUNTIME_IDENTITY_PATH,
    }


def _validate_input_sha256_contract(contract: Mapping[str, Any]) -> dict[str, str]:
    hashes = contract.get("input_sha256")
    if (
        not isinstance(hashes, dict)
        or set(hashes) != set(FROZEN_INPUT_SHA_KEYS)
        or contract.get("input_sha256_format") != "^[0-9a-f]{64}$"
    ):
        raise Stage003Error("input_hash_contract_invalid")
    validated: dict[str, str] = {}
    for name in FROZEN_INPUT_SHA_KEYS:
        value = hashes.get(name)
        if not isinstance(value, str) or LOWER_HEX_64.fullmatch(value) is None:
            raise Stage003Error("input_hash_contract_invalid")
        validated[name] = value
    return validated


def _verify_frozen_data_inputs(contract: Mapping[str, Any]) -> dict[str, Any]:
    hashes = _validate_input_sha256_contract(contract)
    paths = _frozen_data_paths()
    expected = {name: hashes[name] for name in paths}
    identities = _verify_file_identities(paths, expected)
    development_labels = _verify_csv_identity_and_header_only(
        DEVELOPMENT_LABELS_AGGREGATE_PATH,
        expected_sha256=hashes["development_labels_aggregate"],
        expected_header=DEVELOPMENT_LABEL_HEADER,
    )
    reconciliation = _verify_csv_identity_and_header_only(
        RECONCILIATION_AGGREGATE_PATH,
        expected_sha256=hashes["reconciliation_aggregate"],
        expected_header=RECONCILIATION_HEADER,
    )

    stage002 = _load_json(STAGE002_SUMMARY_PATH)
    if (
        stage002.get("decision")
        != "stage002_physical_features_pass_ready_for_training_contract_preregistration"
        or stage002.get("technical_gate_pass") is not True
        or int(stage002.get("technical_gate_pass_count", -1)) != 15
        or int(stage002.get("model_eligible_rows", -1)) != 218
        or int(stage002.get("active_months", -1)) != 35
        or stage002.get("model_features") != MODEL_FEATURES
        or int(stage002.get("warehouse_feature_count", -1)) != 0
        or int(stage002.get("model_fit_count", -1)) != 0
        or stage002.get("label_values_read") is not False
    ):
        raise Stage003Error("stage002_summary_not_eligible")
    stage002_manifest = _load_json(STAGE002_MANIFEST_PATH)
    if (
        not isinstance(stage002_manifest, dict)
        or stage002_manifest.get("model_eligible_feature_panel.csv")
        != hashes.get("stage002_feature_panel")
        or stage002_manifest.get("month_eligibility.csv")
        != hashes.get("stage002_month_eligibility")
        or stage002_manifest.get("stage002_summary.json")
        != hashes.get("stage002_summary")
    ):
        raise Stage003Error("stage002_manifest_not_eligible")
    stage003 = _load_json(STAGE003_METADATA_SUMMARY_PATH)
    if (
        stage003.get("all_structural_gates_passed") is not True
        or int(stage003.get("development_main_jobs", -1)) != 266
        or int(stage003.get("a2_sentinel_jobs", -1)) != 4
        or int(stage003.get("sealed_holdout_jobs_created", -1)) != 0
        or stage003.get("label_values_read") is not False
    ):
        raise Stage003Error("stage003_metadata_summary_not_eligible")
    stage005 = _load_json(STAGE005_DECISION_PATH)
    scope_counts = stage005.get("execution_scope_counts")
    if (
        stage005.get("decision")
        != "stage005_development_account_labels_complete_allow_stage006_training_preregistration"
        or stage005.get("passed") is not True
        or stage005.get("job_counts") != {"A2_sentinel": 4, "main": 266, "total": 270}
        or int(stage005.get("sealed_holdout_label_count", -1)) != 0
        or int(stage005.get("order_api_called_count", -1)) != 0
        or not isinstance(scope_counts, dict)
        or any(int(value) != 0 for value in scope_counts.values())
    ):
        raise Stage003Error("stage005_decision_not_eligible")
    postrun = _load_json(STAGE005_POSTRUN_DECISION_PATH)
    severity = postrun.get("severity")
    if (
        postrun.get("decision") != "ALLOW_STAGE006_TRAINING_PREREGISTRATION_ONLY"
        or postrun.get("allowed") is not True
        or not isinstance(severity, dict)
        or any(type(severity.get(level)) is not int or severity[level] != 0 for level in ["P0", "P1", "P2"])
    ):
        raise Stage003Error("stage005_postrun_review_not_eligible")
    stable = {
        "file_identities": identities,
        "development_labels_aggregate": development_labels,
        "reconciliation_aggregate": reconciliation,
    }
    return {
        "all_input_identities_verified": True,
        **stable,
        "aggregate_data_rows_parsed": int(
            development_labels["data_rows_parsed"]
            + reconciliation["data_rows_parsed"]
        ),
        "identity_sha256": _sha256_bytes(
            _canonical_json_bytes(stable, newline=False)
        ),
    }


def _current_runtime_identity() -> dict[str, Any]:
    executable = Path(sys.executable).resolve()
    xgboost_init = Path(xgboost.__file__).resolve()
    xgboost_library = Path(xgboost.core._LIB._name).resolve()
    files = {
        "python_executable": executable,
        "xgboost_init": xgboost_init,
        "xgboost_shared_library": xgboost_library,
    }
    return {
        "file_identities": {
            name: {
                "path": str(path),
                "sha256": _sha256_file(path),
                "size": int(path.stat().st_size),
            }
            for name, path in files.items()
        },
        "mac_ver": platform.mac_ver()[0],
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "platform_machine": platform.machine(),
        "platform_release": platform.release(),
        "platform_system": platform.system(),
        "platform_version": platform.version(),
        "python_executable": str(executable),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "scikit_learn_version": sklearn.__version__,
        "xgboost_build_info": xgboost.build_info(),
        "xgboost_version": xgboost.__version__,
    }


def _verify_frozen_runtime_identity(contract: Mapping[str, Any]) -> dict[str, Any]:
    hashes = _validate_input_sha256_contract(contract)
    _file_identity(
        RUNTIME_IDENTITY_PATH,
        expected_sha256=hashes["runtime_identity"],
        name="runtime_identity",
    )
    expected = _load_json(RUNTIME_IDENTITY_PATH)
    current = _current_runtime_identity()
    if expected != current:
        raise Stage003Error("runtime_identity_mismatch")
    return dict(expected)


def _validate_machine_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(contract, dict):
        raise Stage003Error("machine_contract_invalid")
    _validate_input_sha256_contract(contract)
    model = contract.get("model")
    folds = contract.get("folds")
    authorization = contract.get("authorization")
    projection = contract.get("input_projection")
    label_access = contract.get("label_access")
    if not all(
        isinstance(value, dict)
        for value in [model, folds, authorization, projection, label_access]
    ):
        raise Stage003Error("machine_contract_invalid")
    if (
        contract.get("model_features") != MODEL_FEATURES
        or model.get("class") != "xgboost.XGBRanker"
        or model.get("params") != MODEL_PARAMS
        or type(model.get("fit_count")) is not int
        or model.get("fit_count") != 26
        or contract.get("effect_gate_keys") != EFFECT_GATE_KEYS
        or set(contract.get("receipt_exact_keys", [])) != RECEIPT_KEYS
        or len(contract.get("receipt_exact_keys", [])) != len(RECEIPT_KEYS)
        or set(contract.get("seal", {}).get("active_exact_keys", []))
        != ACTIVE_SEAL_KEYS
        or len(contract.get("seal", {}).get("active_exact_keys", []))
        != len(ACTIVE_SEAL_KEYS)
        or set(contract.get("seal", {}).get("fallback_exact_keys", []))
        != FALLBACK_SEAL_KEYS
        or len(contract.get("seal", {}).get("fallback_exact_keys", []))
        != len(FALLBACK_SEAL_KEYS)
    ):
        raise Stage003Error("machine_contract_frozen_logic_mismatch")
    if (
        authorization.get("bound_file_keys") != BOUND_FILE_KEYS
        or set(authorization.get("bound_file_paths", {})) != set(BOUND_FILE_KEYS)
        or len(BOUND_FILE_KEYS) != 27
        or projection.get("full_feature_split_allowed_columns")
        != FULL_SPLIT_ALLOWED_COLUMNS
        or projection.get("join_keys") != METADATA_JOIN_KEYS
        or projection.get("probability_delta_absolute_tolerance")
        != PROBABILITY_DELTA_ABSOLUTE_TOLERANCE
        or projection.get("feature_rows") != 218
        or projection.get("split_projection_rows") != 374
        or projection.get("right_only_source_rows") != 156
        or projection.get("right_only_source_keys_sha256")
        != "b23dea181667fd436a1b9ab55b8e141b0e3fadd378610da3aa8e4e07b644aa41"
        or "pit_logistic_probability" in MODEL_FEATURES
    ):
        raise Stage003Error("machine_contract_governance_mismatch")
    if (
        folds.get("active_fold_count") != 13
        or folds.get("fallback_month_count") != 4
        or len(folds.get("active_test_dates", [])) != 13
        or len(folds.get("fallback_test_dates", [])) != 4
        or sum(folds.get("test_rows", [])) != 91
        or folds.get("initial_training_qids") != 13
        or folds.get("initial_training_rows") != 62
        or label_access
        != {
            "aggregate_data_rows_parsed": 0,
            "holdout_label_rows_read": 0,
            "initial_job_label_rows": 62,
            "other_development_main_label_rows_read": 0,
            "test_job_label_rows": 91,
            "unique_job_label_rows": 153,
        }
    ):
        raise Stage003Error("machine_contract_sample_mismatch")
    return {
        "model_feature_order_exact": True,
        "model_params_exact": True,
        "authorization_bound_file_count": len(BOUND_FILE_KEYS),
        "active_fold_count": 13,
        "fallback_month_count": 4,
        "holdout_label_rows_read": 0,
    }


def _validate_governance_decisions(contract: Mapping[str, Any]) -> dict[str, Any]:
    authorization = contract.get("authorization")
    paths = authorization.get("bound_file_paths") if isinstance(authorization, dict) else None
    if not isinstance(paths, dict):
        raise Stage003Error("governance_bound_paths_invalid")
    decisions: dict[str, dict[str, Any]] = {}
    for review_key, decision_key, expected_decision in GOVERNANCE_DECISION_PAIRS:
        review_text = paths.get(review_key)
        decision_text = paths.get(decision_key)
        if not isinstance(review_text, str) or not isinstance(decision_text, str):
            raise Stage003Error(f"governance_bound_path_missing:{decision_key}")
        review_path = Path(review_text)
        decision_path = Path(decision_text)
        if (
            not review_path.is_absolute()
            or not decision_path.is_absolute()
            or not review_path.is_file()
            or not decision_path.is_file()
            or review_path.is_symlink()
            or decision_path.is_symlink()
            or str(review_path.resolve()) != review_text
            or str(decision_path.resolve()) != decision_text
        ):
            raise Stage003Error(f"governance_path_invalid:{decision_key}")
        payload = _load_json(decision_path)
        severity = payload.get("severity") if isinstance(payload, dict) else None
        blocking_zero = bool(
            isinstance(severity, dict)
            and all(
                type(severity.get(level)) is int and severity[level] == 0
                for level in ["P0", "P1", "P2"]
            )
        )
        review_sha256 = _sha256_file(review_path)
        eligible = bool(
            isinstance(payload, dict)
            and payload.get("decision") == expected_decision
            and payload.get("allowed") is True
            and blocking_zero
            and payload.get("review_path") == review_text
            and payload.get("review_sha256") == review_sha256
        )
        if not eligible:
            raise Stage003Error(f"governance_decision_not_eligible:{decision_key}")
        decisions[decision_key] = {
            "decision": expected_decision,
            "allowed": True,
            "blocking_severity_zero": True,
            "decision_path": decision_text,
            "decision_sha256": _sha256_file(decision_path),
            "review_path": review_text,
            "review_sha256": review_sha256,
        }
    return {"passed": True, "decisions": decisions}


def _static_runner_scope_audit(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise Stage003Error("static_scope_runner_path_invalid")
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        raise Stage003Error("static_scope_runner_parse_invalid") from exc

    def dotted_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            prefix = dotted_name(node.value)
            return f"{prefix}.{node.attr}" if prefix else node.attr
        return ""

    counts = {name: 0 for name in STATIC_SCOPE_COUNT_KEYS}
    forbidden_imports: list[str] = []
    forbidden_references: list[str] = []
    fit_call_sites: list[dict[str, Any]] = []
    import_declarations: list[str] = []
    import_aliases: dict[str, str] = {}

    def resolve_name(name: str) -> str:
        root, separator, suffix = name.partition(".")
        canonical_root = import_aliases.get(root, root)
        return f"{canonical_root}.{suffix}" if separator else canonical_root

    class ScopeVisitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.function_stack: list[str] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.function_stack.append(node.name)
            self.generic_visit(node)
            self.function_stack.pop()

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.function_stack.append(node.name)
            self.generic_visit(node)
            self.function_stack.pop()

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                import_declarations.append(
                    f"import:{alias.name}:{alias.asname or ''}"
                )
                import_aliases[alias.asname or alias.name.split(".", 1)[0]] = alias.name
                root = alias.name.split(".", 1)[0]
                if root in {"subprocess"}:
                    forbidden_imports.append(alias.name)
                    counts["unexpected_commands"] += 1
            self.generic_visit(node)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            module = node.module or ""
            root = module.split(".", 1)[0]
            for alias in node.names:
                import_declarations.append(
                    f"from:{module}:{alias.name}:{alias.asname or ''}"
                )
                import_aliases[alias.asname or alias.name] = f"{module}.{alias.name}"
            if root in {"subprocess"}:
                forbidden_imports.append(module)
                counts["unexpected_commands"] += 1
            self.generic_visit(node)

        def visit_Attribute(self, node: ast.Attribute) -> None:
            name = resolve_name(dotted_name(node))
            if name in {"os.environ", "sys.argv"}:
                forbidden_references.append(name)
                counts["unexpected_commands"] += 1
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            name = resolve_name(dotted_name(node.func))
            lowered = name.lower()
            terminal = lowered.rsplit(".", 1)[-1]
            if name.endswith(".fit") or name == "fit":
                fit_call_sites.append(
                    {
                        "function": self.function_stack[-1]
                        if self.function_stack
                        else "<module>",
                        "line": int(node.lineno),
                        "call": name,
                    }
                )
            if (
                lowered.startswith("subprocess.")
                or lowered.startswith("asyncio.create_subprocess")
                or lowered
                in {
                    "os.system",
                    "os.popen",
                    "os.spawnl",
                    "os.spawnle",
                    "os.spawnlp",
                    "os.spawnlpe",
                    "os.spawnv",
                    "os.spawnve",
                    "os.spawnvp",
                    "os.spawnvpe",
                }
                or terminal in {"popen"}
            ):
                counts["unexpected_commands"] += 1
            if lowered.startswith("os.") and lowered not in STATIC_ALLOWED_OS_CALLS:
                counts["unexpected_commands"] += 1
            if lowered in {"__import__", "eval", "exec", "compile"}:
                counts["unexpected_commands"] += 1
            if terminal in {
                "send_order",
                "cancel_order",
                "order_insert",
                "order_action",
            }:
                counts["order_api_calls"] += 1
            if "ctp" in lowered and terminal in {"connect", "login", "authenticate"}:
                counts["ctp_connections"] += 1
            if any(token in lowered for token in ["run_backtest", "run_backtesting", "true_engine"]):
                counts["true_engine_runs"] += 1
            if any(
                token in lowered
                for token in ["gridsearch", "randomizedsearch", "optuna", "hyperopt"]
            ):
                counts["parameter_searches"] += 1
            if any(
                token in lowered
                for token in ["selectkbest", "recursive_feature", "feature_search"]
            ):
                counts["feature_searches"] += 1
            if any(token in lowered for token in ["seed_search", "search_seed"]):
                counts["seed_searches"] += 1
            if any(keyword.arg == "early_stopping_rounds" for keyword in node.keywords):
                counts["early_stopping_runs"] += 1
            if any(
                token in lowered
                for token in ["publish_production", "activate_live", "write_production"]
            ):
                counts["production_writes"] += 1
            self.generic_visit(node)

    ScopeVisitor().visit(tree)
    import_surface_exact = bool(
        set(import_declarations) == STATIC_ALLOWED_IMPORT_DECLARATIONS
        and len(import_declarations) == len(STATIC_ALLOWED_IMPORT_DECLARATIONS)
    )
    fit_site_exact = bool(
        len(fit_call_sites) == 1
        and fit_call_sites[0]["function"] == "_fit_repeated_ranker"
    )
    passed = bool(
        fit_site_exact
        and import_surface_exact
        and not forbidden_imports
        and not forbidden_references
        and all(value == 0 for value in counts.values())
    )
    return {
        "passed": passed,
        "runner_path": str(path.resolve()),
        "runner_sha256": _sha256_file(path),
        "fit_call_site_count": int(len(fit_call_sites)),
        "fit_call_sites": fit_call_sites,
        "import_surface_exact": import_surface_exact,
        "import_declarations": sorted(import_declarations),
        "missing_import_declarations": sorted(
            STATIC_ALLOWED_IMPORT_DECLARATIONS - set(import_declarations)
        ),
        "unexpected_import_declarations": sorted(
            set(import_declarations) - STATIC_ALLOWED_IMPORT_DECLARATIONS
        ),
        "forbidden_imports": sorted(forbidden_imports),
        "forbidden_references": sorted(forbidden_references),
        "counts": counts,
    }


def _canonical_json_bytes(value: Any, *, newline: bool = True) -> bytes:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return payload + (b"\n" if newline else b"")


def _load_json(path: Path, error_type: type[Stage003Error] = Stage003Error) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise error_type(f"json_invalid:{path}") from exc


def _require_exact_keys(
    value: Any,
    expected: set[str],
    name: str,
    error_type: type[Stage003Error],
) -> Mapping[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise error_type(f"{name}_keys_invalid")
    return value


def _require_string(value: Any, name: str, error_type: type[Stage003Error]) -> str:
    if not isinstance(value, str):
        raise error_type(f"{name}_type_invalid")
    return value


def _require_int(value: Any, name: str, error_type: type[Stage003Error]) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise error_type(f"{name}_type_invalid")
    return value


def _require_hex(value: Any, name: str, error_type: type[Stage003Error]) -> str:
    text = _require_string(value, name, error_type)
    if LOWER_HEX_64.fullmatch(text) is None:
        raise error_type(f"{name}_hex_invalid")
    return text


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_file(path: Path) -> None:
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_exclusive(path: Path, payload: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise Stage003AuthorizationError(f"already_exists:{path}") from exc
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_directory(path.parent)


def _atomic_link_publish(path: Path, payload: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.parent / f".{path.name}.{_sha256_bytes(payload)[:16]}.tmp"
    if path.exists() or temp_path.exists():
        raise Stage003SealError(f"already_exists:{path}")
    try:
        descriptor = os.open(str(temp_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.link(temp_path, path)
        _fsync_directory(path.parent)
        temp_path.unlink()
        _fsync_directory(path.parent)
    except FileExistsError as exc:
        if temp_path.exists():
            temp_path.unlink()
        raise Stage003SealError(f"already_exists:{path}") from exc


def _resolved_file(path_text: Any, name: str) -> Path:
    text = _require_string(path_text, name, Stage003AuthorizationError)
    path = Path(text)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise Stage003AuthorizationError(f"bound_path_invalid:{name}")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise Stage003AuthorizationError(f"bound_path_invalid:{name}") from exc
    if str(resolved) != text:
        raise Stage003AuthorizationError(f"bound_path_invalid:{name}")
    return resolved


def _validate_authorization_from_paths(
    authorization_path: Path, contract_path: Path
) -> dict[str, Any]:
    contract = _load_json(contract_path, Stage003AuthorizationError)
    auth_contract = contract.get("authorization")
    if not isinstance(auth_contract, dict):
        raise Stage003AuthorizationError("authorization_contract_invalid")
    expected_auth_path = _require_string(
        auth_contract.get("path"), "authorization_contract_path", Stage003AuthorizationError
    )
    try:
        actual_auth_path = str(Path(authorization_path).resolve(strict=True))
    except OSError as exc:
        raise Stage003AuthorizationError("authorization_path_invalid") from exc
    if actual_auth_path != expected_auth_path or Path(authorization_path).is_symlink():
        raise Stage003AuthorizationError("authorization_path_invalid")

    authorization = _require_exact_keys(
        _load_json(authorization_path, Stage003AuthorizationError),
        AUTHORIZATION_KEYS,
        "authorization_top_level",
        Stage003AuthorizationError,
    )
    decision = _require_string(
        authorization["decision"], "decision", Stage003AuthorizationError
    )
    scope = _require_string(authorization["scope"], "scope", Stage003AuthorizationError)
    nonce = _require_string(authorization["nonce"], "nonce", Stage003AuthorizationError)
    if decision != auth_contract.get("decision"):
        raise Stage003AuthorizationError("decision_invalid")
    if scope != auth_contract.get("scope"):
        raise Stage003AuthorizationError("scope_invalid")
    if LOWER_HEX_64.fullmatch(nonce) is None:
        raise Stage003AuthorizationError("nonce_invalid")

    receipt_path_text = _require_string(
        authorization["consumption_receipt_path"],
        "consumption_receipt_path",
        Stage003AuthorizationError,
    )
    result_dir_text = _require_string(
        authorization["result_dir"], "result_dir", Stage003AuthorizationError
    )
    if receipt_path_text != auth_contract.get("consumption_receipt_path"):
        raise Stage003AuthorizationError("consumption_receipt_path_invalid")
    if result_dir_text != auth_contract.get("result_dir"):
        raise Stage003AuthorizationError("result_dir_invalid")
    receipt_path = Path(receipt_path_text)
    result_dir = Path(result_dir_text)
    temp_result_dir = Path(
        _require_string(
            auth_contract.get("temp_result_dir"),
            "temp_result_dir",
            Stage003AuthorizationError,
        )
    )
    for path in [receipt_path, result_dir, temp_result_dir]:
        if not path.is_absolute() or str(path.parent.resolve(strict=True) / path.name) != str(path):
            raise Stage003AuthorizationError(f"canonical_output_path_invalid:{path.name}")

    expected_keys = auth_contract.get("bound_file_keys")
    expected_paths = auth_contract.get("bound_file_paths")
    if (
        expected_keys != BOUND_FILE_KEYS
        or not isinstance(expected_paths, dict)
        or set(expected_paths) != set(BOUND_FILE_KEYS)
    ):
        raise Stage003AuthorizationError("bound_contract_invalid")
    bound_files = authorization["bound_files"]
    if not isinstance(bound_files, dict) or list(sorted(bound_files)) != sorted(BOUND_FILE_KEYS):
        raise Stage003AuthorizationError("bound_file_keys_invalid")
    normalized: dict[str, dict[str, str]] = {}
    for key in BOUND_FILE_KEYS:
        identity = _require_exact_keys(
            bound_files[key], {"path", "sha256"}, f"bound_file_{key}", Stage003AuthorizationError
        )
        path_text = identity["path"]
        if path_text != expected_paths.get(key):
            raise Stage003AuthorizationError(f"bound_path_invalid:{key}")
        path = _resolved_file(path_text, key)
        digest = _require_hex(
            identity["sha256"], f"bound_sha256_{key}", Stage003AuthorizationError
        )
        if _sha256_file(path) != digest:
            raise Stage003AuthorizationError(f"bound_sha256_drift:{key}")
        normalized[key] = {"path": str(path), "sha256": digest}

    for path, name in [
        (receipt_path, "consumption_receipt"),
        (result_dir, "result_dir"),
        (temp_result_dir, "temp_result_dir"),
    ]:
        if path.exists():
            raise Stage003AuthorizationError(f"already_exists:{name}")

    bound_digest = _sha256_bytes(_canonical_json_bytes(normalized, newline=False))
    receipt = {
        "decision": "STAGE003_AUTHORIZATION_CONSUMED",
        "scope": scope,
        "nonce": nonce,
        "authorization_path": actual_auth_path,
        "authorization_sha256": _sha256_file(Path(authorization_path)),
        "bound_files_identity_sha256": bound_digest,
        "result_dir": result_dir_text,
    }
    return {
        "contract": contract,
        "authorization": dict(authorization),
        "receipt": receipt,
        "receipt_path": receipt_path,
        "result_dir": result_dir,
        "temp_result_dir": temp_result_dir,
        "bound_files": normalized,
    }


def _persist_validated_authorization(validated: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "contract",
        "authorization",
        "receipt",
        "receipt_path",
        "result_dir",
        "temp_result_dir",
        "bound_files",
    }
    if not isinstance(validated, Mapping) or set(validated) != required:
        raise Stage003AuthorizationError("validated_authorization_shape_invalid")
    receipt_path = validated["receipt_path"]
    if not isinstance(receipt_path, Path):
        raise Stage003AuthorizationError("validated_receipt_path_invalid")
    receipt = _require_exact_keys(
        validated["receipt"], RECEIPT_KEYS, "validated_receipt", Stage003AuthorizationError
    )
    for name, value in receipt.items():
        _require_string(value, f"receipt_{name}", Stage003AuthorizationError)
    if receipt["decision"] != "STAGE003_AUTHORIZATION_CONSUMED":
        raise Stage003AuthorizationError("validated_receipt_decision_invalid")
    _require_hex(
        receipt["authorization_sha256"],
        "authorization_sha256",
        Stage003AuthorizationError,
    )
    _require_hex(
        receipt["bound_files_identity_sha256"],
        "bound_files_identity_sha256",
        Stage003AuthorizationError,
    )
    _write_exclusive(receipt_path, _canonical_json_bytes(receipt))
    persisted = _require_exact_keys(
        _load_json(receipt_path, Stage003AuthorizationError),
        RECEIPT_KEYS,
        "receipt",
        Stage003AuthorizationError,
    )
    if dict(persisted) != receipt:
        raise Stage003AuthorizationError("receipt_reverification_failed")
    _require_hex(persisted["authorization_sha256"], "authorization_sha256", Stage003AuthorizationError)
    _require_hex(
        persisted["bound_files_identity_sha256"],
        "bound_files_identity_sha256",
        Stage003AuthorizationError,
    )
    if receipt_path.read_bytes() != _canonical_json_bytes(receipt):
        raise Stage003AuthorizationError("receipt_bytes_reverification_failed")
    return dict(receipt)


def _consume_authorization_from_paths(
    authorization_path: Path, contract_path: Path
) -> dict[str, Any]:
    return _persist_validated_authorization(
        _validate_authorization_from_paths(authorization_path, contract_path)
    )


def _capture_execution_checkpoint(
    checkpoint: str,
    validated: Mapping[str, Any],
    *,
    receipt_required: bool,
    staging_required: bool,
    event_ledger: ExecutionEventLedger,
) -> dict[str, Any]:
    if checkpoint not in CHECKPOINT_NAMES:
        raise Stage003Error(f"checkpoint_name_invalid:{checkpoint}")
    receipt = validated.get("receipt")
    bound_files = validated.get("bound_files")
    receipt_path = validated.get("receipt_path")
    result_dir = validated.get("result_dir")
    staging_dir = validated.get("temp_result_dir")
    if (
        not isinstance(receipt, Mapping)
        or not isinstance(bound_files, Mapping)
        or not isinstance(receipt_path, Path)
        or not isinstance(result_dir, Path)
        or not isinstance(staging_dir, Path)
    ):
        raise Stage003Error("checkpoint_validated_authorization_invalid")
    if not isinstance(event_ledger, ExecutionEventLedger):
        raise Stage003Error("checkpoint_event_ledger_invalid")

    authorization_path = Path(str(receipt.get("authorization_path", "")))
    authorization_sha256 = _require_hex(
        receipt.get("authorization_sha256"),
        "checkpoint_authorization_sha256",
        Stage003Error,
    )
    authorization_identity = _file_identity(
        authorization_path,
        expected_sha256=authorization_sha256,
        name="authorization",
    )
    if _load_json(authorization_path) != validated.get("authorization"):
        raise Stage003Error("checkpoint_authorization_payload_drift")

    if set(bound_files) != set(BOUND_FILE_KEYS):
        raise Stage003Error("checkpoint_bound_file_keys_invalid")
    bound_identity_audit: dict[str, dict[str, Any]] = {}
    normalized_bound_files: dict[str, dict[str, str]] = {}
    for name in BOUND_FILE_KEYS:
        entry = bound_files[name]
        if not isinstance(entry, Mapping) or set(entry) != {"path", "sha256"}:
            raise Stage003Error(f"checkpoint_bound_file_identity_invalid:{name}")
        path_text = entry.get("path")
        digest = entry.get("sha256")
        if not isinstance(path_text, str):
            raise Stage003Error(f"checkpoint_bound_file_path_invalid:{name}")
        expected_sha256 = _require_hex(
            digest, f"checkpoint_bound_file_sha256_{name}", Stage003Error
        )
        path = Path(path_text)
        if not path.is_absolute() or str(path.resolve(strict=True)) != path_text:
            raise Stage003Error(f"checkpoint_bound_file_path_invalid:{name}")
        bound_identity_audit[name] = _file_identity(
            path, expected_sha256=expected_sha256, name=f"bound_{name}"
        )
        normalized_bound_files[name] = {
            "path": path_text,
            "sha256": expected_sha256,
        }
    bound_digest = _sha256_bytes(
        _canonical_json_bytes(normalized_bound_files, newline=False)
    )
    if bound_digest != receipt.get("bound_files_identity_sha256"):
        raise Stage003Error("checkpoint_bound_file_digest_drift")

    if receipt_required:
        persisted_receipt = _require_exact_keys(
            _load_json(receipt_path), RECEIPT_KEYS, "checkpoint_receipt", Stage003Error
        )
        if dict(persisted_receipt) != dict(receipt):
            raise Stage003Error("checkpoint_receipt_payload_drift")
        if receipt_path.read_bytes() != _canonical_json_bytes(receipt):
            raise Stage003Error("checkpoint_receipt_bytes_drift")
    elif receipt_path.exists():
        raise Stage003Error("checkpoint_receipt_exists_before_consumption")
    if result_dir.exists():
        raise Stage003Error("checkpoint_result_dir_exists_before_publish")
    if staging_required:
        if not staging_dir.is_dir() or staging_dir.is_symlink():
            raise Stage003Error("checkpoint_staging_dir_invalid")
    elif staging_dir.exists():
        raise Stage003Error("checkpoint_staging_exists_before_consumption")

    contract_path = Path(normalized_bound_files["training_contract"]["path"])
    contract = _load_json(contract_path)
    if contract != validated.get("contract"):
        raise Stage003Error("checkpoint_machine_contract_payload_drift")
    machine_contract_audit = _validate_machine_contract(contract)
    governance_audit = _validate_governance_decisions(contract)
    input_identity_audit = _verify_frozen_data_inputs(contract)
    for source in ["development_labels_aggregate", "reconciliation_aggregate"]:
        event_ledger.record(
            "aggregate_header_verified",
            checkpoint=checkpoint,
            source=source,
            data_rows_parsed=int(input_identity_audit[source]["data_rows_parsed"]),
            sha256=str(input_identity_audit[source]["sha256"]),
        )
    runtime_identity = _verify_frozen_runtime_identity(contract)
    static_scope_audit = _static_runner_scope_audit(
        Path(normalized_bound_files["runner"]["path"])
    )
    if static_scope_audit["passed"] is not True:
        raise Stage003Error("static_runner_scope_not_eligible")
    authorization_and_inputs_identity = {
        "authorization_sha256": authorization_sha256,
        "bound_files_identity_sha256": bound_digest,
        "bound_file_sha256": {
            name: normalized_bound_files[name]["sha256"] for name in BOUND_FILE_KEYS
        },
        "frozen_input_identity_sha256": input_identity_audit["identity_sha256"],
        "governance_decision_sha256": {
            name: item["decision_sha256"]
            for name, item in governance_audit["decisions"].items()
        },
        "machine_contract_sha256": normalized_bound_files["training_contract"][
            "sha256"
        ],
        "static_scope_audit_sha256": _sha256_bytes(
            _canonical_json_bytes(static_scope_audit, newline=False)
        ),
    }
    return {
        "checkpoint": checkpoint,
        "authorization_and_inputs_identity_sha256": _sha256_bytes(
            _canonical_json_bytes(authorization_and_inputs_identity, newline=False)
        ),
        "runtime_identity_sha256": _sha256_bytes(
            _canonical_json_bytes(runtime_identity, newline=False)
        ),
        "authorization_and_inputs_identity": authorization_and_inputs_identity,
        "authorization_identity": authorization_identity,
        "bound_file_identity_audit": bound_identity_audit,
        "input_identity_audit": input_identity_audit,
        "runtime_identity": runtime_identity,
        "machine_contract_audit": machine_contract_audit,
        "governance_audit": governance_audit,
        "static_scope_audit": static_scope_audit,
    }


def _build_checkpoint_stability_audit(
    checkpoints: list[Mapping[str, Any]],
) -> dict[str, Any]:
    entries: list[dict[str, str]] = []
    for checkpoint in checkpoints:
        if not isinstance(checkpoint, Mapping):
            raise Stage003Error("checkpoint_entry_invalid")
        name = checkpoint.get("checkpoint")
        authorization_digest = checkpoint.get(
            "authorization_and_inputs_identity_sha256"
        )
        runtime_digest = checkpoint.get("runtime_identity_sha256")
        if (
            not isinstance(name, str)
            or not isinstance(authorization_digest, str)
            or LOWER_HEX_64.fullmatch(authorization_digest) is None
            or not isinstance(runtime_digest, str)
            or LOWER_HEX_64.fullmatch(runtime_digest) is None
        ):
            raise Stage003Error("checkpoint_entry_invalid")
        entries.append(
            {
                "checkpoint": name,
                "authorization_and_inputs_identity_sha256": authorization_digest,
                "runtime_identity_sha256": runtime_digest,
            }
        )
    names_exact = [entry["checkpoint"] for entry in entries] == CHECKPOINT_NAMES
    authorization_exact = bool(
        len(entries) == 3
        and len(
            {
                entry["authorization_and_inputs_identity_sha256"] for entry in entries
            }
        )
        == 1
    )
    runtime_exact = bool(
        len(entries) == 3
        and len({entry["runtime_identity_sha256"] for entry in entries}) == 1
    )
    return {
        "passed": bool(names_exact and authorization_exact and runtime_exact),
        "checkpoint_count": int(len(entries)),
        "checkpoint_names_exact": bool(names_exact),
        "authorization_and_inputs_exact": authorization_exact,
        "runtime_identity_exact": runtime_exact,
        "entries": entries,
    }


def _normalize_iso_dates(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        try:
            result[column] = (
                pd.to_datetime(result[column], errors="raise")
                .dt.normalize()
                .dt.strftime("%Y-%m-%d")
            )
        except (TypeError, ValueError) as exc:
            raise Stage003Error(f"metadata_date_invalid:{column}") from exc
    return result


def _strict_integer_rank(series: pd.Series, name: str) -> pd.Series:
    if pd.api.types.is_bool_dtype(series.dtype) or not pd.api.types.is_numeric_dtype(
        series.dtype
    ):
        raise Stage003Error(f"{name}_type_invalid")
    values = series.to_numpy(dtype="float64")
    if not np.isfinite(values).all() or not np.equal(values, np.floor(values)).all():
        raise Stage003Error(f"{name}_type_invalid")
    return pd.Series(values.astype("int64"), index=series.index, name=series.name)


def _join_raw_probability_projection(
    feature_frame: pd.DataFrame,
    split_projection: pd.DataFrame,
    *,
    projection_contract: Mapping[str, Any] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    feature_required = {"eval_date", "product_vt_symbol", "a_rank", *MODEL_FEATURES}
    if missing := sorted(feature_required - set(feature_frame.columns)):
        raise Stage003Error(f"feature_columns_missing:{missing}")
    if set(split_projection.columns) != set(FULL_SPLIT_ALLOWED_COLUMNS) or len(
        split_projection.columns
    ) != len(FULL_SPLIT_ALLOWED_COLUMNS):
        raise Stage003Error("projection_columns_invalid")

    features = _normalize_iso_dates(feature_frame, ["eval_date"])
    split = _normalize_iso_dates(
        split_projection[FULL_SPLIT_ALLOWED_COLUMNS], ["eval_date", "next_eval_date"]
    )
    features["a_rank"] = _strict_integer_rank(features["a_rank"], "feature_a_rank")
    split["a_rank"] = _strict_integer_rank(split["a_rank"], "split_a_rank")
    features["product_vt_symbol"] = features["product_vt_symbol"].astype(str)
    split["product_vt_symbol"] = split["product_vt_symbol"].astype(str)

    feature_duplicate_keys = int(features.duplicated(METADATA_JOIN_KEYS).sum())
    split_duplicate_keys = int(split.duplicated(METADATA_JOIN_KEYS).sum())
    if feature_duplicate_keys:
        raise Stage003Error("feature_key_duplicate")
    if split_duplicate_keys:
        raise Stage003Error("split_key_duplicate")

    feature_keys = {
        (str(row.eval_date), str(row.product_vt_symbol), int(row.a_rank))
        for row in features[METADATA_JOIN_KEYS].itertuples(index=False)
    }
    split_keys = {
        (str(row.eval_date), str(row.product_vt_symbol), int(row.a_rank))
        for row in split[METADATA_JOIN_KEYS].itertuples(index=False)
    }
    if feature_keys - split_keys:
        raise Stage003Error("projection_join_missing")
    right_only_keys = sorted(split_keys - feature_keys)
    right_only_rows = [
        {
            "eval_date": eval_date,
            "product_vt_symbol": product_vt_symbol,
            "a_rank": a_rank,
        }
        for eval_date, product_vt_symbol, a_rank in right_only_keys
    ]
    right_only_sha256 = _sha256_bytes(
        _canonical_json_bytes(right_only_rows, newline=False)
    )
    if projection_contract is None:
        expected_feature_rows = len(features)
        expected_split_rows = len(features)
        expected_right_only_rows = 0
        expected_right_only_sha256 = _sha256_bytes(b"[]")
    else:
        if not isinstance(projection_contract, Mapping):
            raise Stage003Error("projection_contract_invalid")
        expected_feature_rows = projection_contract.get("feature_rows")
        expected_split_rows = projection_contract.get("split_projection_rows")
        expected_right_only_rows = projection_contract.get("right_only_source_rows")
        expected_right_only_sha256 = projection_contract.get(
            "right_only_source_keys_sha256"
        )
        if (
            type(expected_feature_rows) is not int
            or type(expected_split_rows) is not int
            or type(expected_right_only_rows) is not int
            or not isinstance(expected_right_only_sha256, str)
            or LOWER_HEX_64.fullmatch(expected_right_only_sha256) is None
        ):
            raise Stage003Error("projection_contract_invalid")
    if (
        len(right_only_rows) != expected_right_only_rows
        or right_only_sha256 != expected_right_only_sha256
    ):
        raise Stage003Error("projection_right_only_source_invalid")
    if len(features) != expected_feature_rows or len(split) != expected_split_rows:
        raise Stage003Error("projection_source_shape_invalid")

    probability = split["pit_logistic_probability"]
    if pd.api.types.is_bool_dtype(probability.dtype) or not pd.api.types.is_numeric_dtype(
        probability.dtype
    ):
        raise Stage003Error("probability_type_or_finite_invalid")
    probability_values = probability.to_numpy(dtype="float64")
    probability_nonfinite_rows = int((~np.isfinite(probability_values)).sum())
    if probability_nonfinite_rows:
        raise Stage003Error("probability_type_or_finite_invalid")
    probability_out_of_range_rows = int(
        ((probability_values < 0.0) | (probability_values > 1.0)).sum()
    )
    if probability_out_of_range_rows:
        raise Stage003Error("probability_out_of_range")
    split["pit_logistic_probability"] = probability_values

    joined = features.merge(
        split,
        on=METADATA_JOIN_KEYS,
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    missing_join_rows = int(joined["_merge"].ne("both").sum())
    extra_join_rows = int(max(0, len(joined) - len(features)))
    if missing_join_rows:
        raise Stage003Error("projection_join_missing")
    if extra_join_rows:
        raise Stage003Error("projection_join_extra")
    joined.drop(columns=["_merge"], inplace=True)

    anchors = joined[joined["a_rank"].eq(10)]
    month_anchor_counts = anchors.groupby("eval_date", sort=False).size()
    if (
        len(anchors) != joined["eval_date"].nunique()
        or not month_anchor_counts.eq(1).all()
    ):
        raise Stage003Error("probability_rank10_anchor_invalid")
    anchor_probability = anchors.set_index("eval_date")["pit_logistic_probability"]
    joined["_raw_probability_delta"] = joined["pit_logistic_probability"] - joined[
        "eval_date"
    ].map(anchor_probability)
    formal_delta = joined["formal_probability_delta_vs_rank10"]
    if pd.api.types.is_bool_dtype(formal_delta.dtype) or not pd.api.types.is_numeric_dtype(
        formal_delta.dtype
    ):
        raise Stage003Error("formal_probability_delta_invalid")
    formal_values = formal_delta.to_numpy(dtype="float64")
    if not np.isfinite(formal_values).all():
        raise Stage003Error("formal_probability_delta_invalid")
    rank10_formal = joined.loc[
        joined["a_rank"].eq(10), "formal_probability_delta_vs_rank10"
    ].to_numpy(dtype="float64")
    rank10_raw = joined.loc[
        joined["a_rank"].eq(10), "_raw_probability_delta"
    ].to_numpy(dtype="float64")
    if not np.equal(rank10_formal, 0.0).all() or not np.equal(rank10_raw, 0.0).all():
        raise Stage003Error("probability_rank10_delta_not_zero")
    errors = np.abs(joined["_raw_probability_delta"].to_numpy() - formal_values)
    max_error = float(errors.max(initial=0.0))
    if max_error > PROBABILITY_DELTA_ABSOLUTE_TOLERANCE:
        raise Stage003Error("probability_delta_mismatch")
    joined.drop(columns=["_raw_probability_delta"], inplace=True)
    joined.sort_values(METADATA_JOIN_KEYS, kind="mergesort", inplace=True)
    joined.reset_index(drop=True, inplace=True)
    return joined, {
        "feature_rows": int(len(features)),
        "joined_rows": int(len(joined)),
        "missing_join_rows": missing_join_rows,
        "extra_join_rows": extra_join_rows,
        "right_only_source_rows": int(len(right_only_rows)),
        "right_only_source_keys_sha256": right_only_sha256,
        "feature_duplicate_keys": feature_duplicate_keys,
        "split_duplicate_keys": split_duplicate_keys,
        "probability_nonfinite_rows": probability_nonfinite_rows,
        "probability_out_of_range_rows": probability_out_of_range_rows,
        "rank10_rows": int(len(anchors)),
        "probability_delta_max_abs_error": max_error,
    }


def _extract_ranker_matrix(
    frame: pd.DataFrame, feature_order: list[str]
) -> pd.DataFrame:
    if feature_order != MODEL_FEATURES:
        raise Stage003Error("ranker_feature_order_invalid")
    if any(feature not in frame.columns for feature in MODEL_FEATURES):
        raise Stage003Error("ranker_feature_columns_missing")
    for feature in MODEL_FEATURES:
        series = frame[feature]
        if pd.api.types.is_bool_dtype(series.dtype) or not pd.api.types.is_numeric_dtype(
            series.dtype
        ):
            raise Stage003Error(f"ranker_feature_type_invalid:{feature}")
    matrix = frame[MODEL_FEATURES].astype("float64")
    if not np.isfinite(matrix.to_numpy()).all():
        raise Stage003Error("ranker_feature_nonfinite")
    return matrix


def _ordered_fold_rows(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.sort_values(
        ["eval_date", "a_rank", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)


def _group_boundaries(ordered: pd.DataFrame) -> tuple[list[int], list[int]]:
    qid = pd.factorize(ordered["eval_date"], sort=True)[0].astype("int64").tolist()
    if qid and (qid[0] != 0 or any(right < left for left, right in zip(qid, qid[1:]))):
        raise Stage003Error("qid_not_sorted_contiguous")
    group_sizes = ordered.groupby("eval_date", sort=True).size().astype(int).tolist()
    boundaries = [0]
    for size in group_sizes:
        boundaries.append(boundaries[-1] + size)
    return qid, boundaries


def _build_frozen_metadata_state(
    feature_frame: pd.DataFrame,
    split_projection: pd.DataFrame,
    jobs_projection: pd.DataFrame,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    if set(jobs_projection.columns) != set(JOB_ALLOWED_COLUMNS) or len(
        jobs_projection.columns
    ) != len(JOB_ALLOWED_COLUMNS):
        raise Stage003Error("job_projection_columns_invalid")
    panel, projection_audit = _join_raw_probability_projection(
        feature_frame,
        split_projection,
        projection_contract=contract.get("input_projection"),
    )
    jobs = _normalize_iso_dates(
        jobs_projection[JOB_ALLOWED_COLUMNS], ["eval_date", "next_eval_date"]
    )
    jobs["candidate_rank"] = _strict_integer_rank(
        jobs["candidate_rank"], "job_candidate_rank"
    )
    jobs["product_vt_symbol"] = jobs["product_vt_symbol"].astype(str)
    jobs["job_id"] = jobs["job_id"].astype(str)
    jobs["eligibility_key"] = jobs["eligibility_key"].astype(str)
    jobs["eligibility_sha256"] = jobs["eligibility_sha256"].astype(str)
    if jobs["job_id"].duplicated().any():
        raise Stage003Error("job_id_duplicate")
    if not jobs["split"].astype(str).eq("development").all():
        raise Stage003Error("job_split_invalid")
    if not jobs["job_type"].astype(str).isin(["main", "A2_sentinel"]).all():
        raise Stage003Error("job_type_invalid")
    if not jobs["eligibility_sha256"].map(
        lambda value: LOWER_HEX_64.fullmatch(value) is not None
    ).all():
        raise Stage003Error("job_eligibility_sha256_invalid")

    development = panel[panel["split"].astype(str).eq("development")].copy()
    holdout = panel[
        panel["split"].astype(str).eq("sealed_account_label_holdout")
    ].copy()
    if len(development) != 153 or development["eval_date"].nunique() != 26:
        raise Stage003Error("development_feature_shape_invalid")
    if len(holdout) != 65 or holdout["eval_date"].nunique() != 9:
        raise Stage003Error("holdout_feature_shape_invalid")
    if len(panel) != len(development) + len(holdout):
        raise Stage003Error("feature_split_value_invalid")

    main_jobs = jobs[jobs["job_type"].eq("main")].copy()
    a2_jobs = jobs[jobs["job_type"].eq("A2_sentinel")].copy()
    if len(main_jobs) != 266 or len(a2_jobs) != 4:
        raise Stage003Error("development_job_shape_invalid")
    main_jobs.rename(columns={"candidate_rank": "a_rank"}, inplace=True)
    job_join_keys = [*METADATA_JOIN_KEYS, "next_eval_date"]
    if main_jobs.duplicated(job_join_keys).any():
        raise Stage003Error("main_job_key_duplicate")
    development = development.merge(
        main_jobs[
            [
                *job_join_keys,
                "job_type",
                "job_id",
                "eligibility_key",
                "eligibility_sha256",
            ]
        ],
        on=job_join_keys,
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    if len(development) != 153 or development["_merge"].ne("both").any():
        raise Stage003Error("development_job_join_invalid")
    development.drop(columns=["_merge"], inplace=True)
    if not development["job_type"].eq("main").all():
        raise Stage003Error("a2_job_entered_model_panel")
    development = _ordered_fold_rows(development)
    holdout = _ordered_fold_rows(holdout)

    fold_contract = contract.get("folds")
    if not isinstance(fold_contract, dict):
        raise Stage003Error("fold_contract_invalid")
    active_dates = list(fold_contract.get("active_test_dates", []))
    fallback_dates = list(fold_contract.get("fallback_test_dates", []))
    if len(active_dates) != 13 or len(fallback_dates) != 4:
        raise Stage003Error("fold_contract_invalid")
    initial = development[development["eval_date"].lt(active_dates[0])].copy()
    if len(initial) != 62 or initial["eval_date"].nunique() != 13:
        raise Stage003Error("initial_training_shape_invalid")

    active_folds: list[dict[str, Any]] = []
    for index, test_date in enumerate(active_dates):
        train = development[
            development["eval_date"].lt(test_date)
            & development["next_eval_date"].le(test_date)
        ].copy()
        test = development[development["eval_date"].eq(test_date)].copy()
        train = _ordered_fold_rows(train)
        test = _ordered_fold_rows(test)
        qid, boundaries = _group_boundaries(train)
        train_qids = int(train["eval_date"].nunique())
        if (
            len(train) != int(fold_contract["training_rows"][index])
            or train_qids != int(fold_contract["training_qids"][index])
            or len(test) != int(fold_contract["test_rows"][index])
            or test["a_rank"].eq(10).sum() != 1
            or len(test) < 3
            or train["eval_date"].ge(test_date).any()
            or train["next_eval_date"].gt(test_date).any()
        ):
            raise Stage003Error(f"active_fold_shape_or_pit_invalid:{test_date}")
        active_folds.append(
            {
                "test_eval_date": test_date,
                "train_rows": int(len(train)),
                "train_qids": train_qids,
                "test_rows": int(len(test)),
                "train_panel": train,
                "test_panel": test,
                "qid": qid,
                "group_boundaries": boundaries,
                "ranker_feature_order": list(MODEL_FEATURES),
                "train_label_end_max": str(train["next_eval_date"].max()),
            }
        )

    fallback_source = split_projection[FULL_SPLIT_ALLOWED_COLUMNS].copy()
    fallback_source = _normalize_iso_dates(
        fallback_source, ["eval_date", "next_eval_date"]
    )
    fallback_source["a_rank"] = _strict_integer_rank(
        fallback_source["a_rank"], "fallback_a_rank"
    )
    fallback = fallback_source[
        fallback_source["split"].astype(str).eq("development")
        & fallback_source["eval_date"].isin(fallback_dates)
        & fallback_source["a_rank"].eq(10)
    ].copy()
    fallback["_date_order"] = pd.Categorical(
        fallback["eval_date"], categories=fallback_dates, ordered=True
    )
    fallback.sort_values("_date_order", kind="mergesort", inplace=True)
    fallback.drop(columns=["_date_order"], inplace=True)
    fallback.reset_index(drop=True, inplace=True)
    if len(fallback) != 4 or fallback["eval_date"].tolist() != fallback_dates:
        raise Stage003Error("fallback_month_shape_invalid")
    if set(active_dates) & set(fallback_dates):
        raise Stage003Error("active_fallback_overlap")
    oos_calendar_dates = sorted([*active_dates, *fallback_dates])
    if oos_calendar_dates[0] != "2023-07-31" or oos_calendar_dates[-1] != "2024-11-29":
        raise Stage003Error("oos_calendar_boundary_invalid")
    return {
        "development_panel": development,
        "holdout_panel": holdout,
        "initial_training_panel": _ordered_fold_rows(initial),
        "active_folds": active_folds,
        "fallback_months": fallback,
        "oos_calendar_dates": oos_calendar_dates,
        "main_jobs": main_jobs,
        "a2_jobs": a2_jobs,
        "audit": {
            **projection_audit,
            "development_rows": int(len(development)),
            "development_active_months": int(development["eval_date"].nunique()),
            "holdout_feature_rows": int(len(holdout)),
            "holdout_active_months": int(holdout["eval_date"].nunique()),
            "initial_training_rows": int(len(initial)),
            "initial_training_qids": int(initial["eval_date"].nunique()),
            "active_fold_count": int(len(active_folds)),
            "fallback_month_count": int(len(fallback)),
            "a2_jobs_total": int(len(a2_jobs)),
            "a2_jobs_used": 0,
            "holdout_prediction_rows": 0,
            "pit_violation_rows": 0,
        },
    }


class PhaseGatedJobLabelStore:
    def __init__(
        self,
        *,
        metadata: pd.DataFrame,
        label_root: Path,
        manifest_files: Mapping[str, Mapping[str, Any]],
        initial_dates: list[str],
        test_dates: list[str],
        event_ledger: ExecutionEventLedger | None = None,
        other_development_main_job_ids: set[str] | None = None,
        a2_job_ids: set[str] | None = None,
    ) -> None:
        if missing := sorted(set(LABEL_METADATA_COLUMNS) - set(metadata.columns)):
            raise Stage003Error(f"label_metadata_columns_missing:{missing}")
        frame = _normalize_iso_dates(
            metadata[LABEL_METADATA_COLUMNS], ["eval_date", "next_eval_date"]
        )
        frame["a_rank"] = _strict_integer_rank(frame["a_rank"], "label_a_rank")
        for column in [
            "product_vt_symbol",
            "split",
            "job_type",
            "job_id",
            "eligibility_key",
            "eligibility_sha256",
        ]:
            if not frame[column].map(lambda value: isinstance(value, str)).all():
                raise Stage003Error(f"label_metadata_type_invalid:{column}")
        if not frame["split"].eq("development").all() or not frame["job_type"].eq(
            "main"
        ).all():
            raise Stage003Error("label_metadata_scope_invalid")
        if not frame["eligibility_key"].map(
            lambda value: Path(value).name == value and value not in {"", ".", ".."}
        ).all():
            raise Stage003Error("label_metadata_eligibility_key_invalid")
        if frame["job_id"].duplicated().any() or frame.duplicated(
            METADATA_JOIN_KEYS
        ).any():
            raise Stage003Error("label_metadata_key_duplicate")
        if not frame["eligibility_sha256"].map(
            lambda value: LOWER_HEX_64.fullmatch(value) is not None
        ).all():
            raise Stage003Error("label_metadata_eligibility_sha256_invalid")
        self.metadata = _ordered_fold_rows(frame)
        self.label_root = Path(label_root)
        self.manifest_files = dict(manifest_files)
        self.event_ledger = event_ledger or ExecutionEventLedger()
        self.initial_dates = [
            pd.Timestamp(value).date().isoformat() for value in initial_dates
        ]
        self.test_dates = [pd.Timestamp(value).date().isoformat() for value in test_dates]
        if set(self.initial_dates) & set(self.test_dates):
            raise Stage003Error("label_phase_date_overlap")
        expected_dates = set(self.initial_dates) | set(self.test_dates)
        if set(self.metadata["eval_date"]) != expected_dates:
            raise Stage003Error("label_metadata_date_scope_invalid")
        self.expected_job_ids = {
            eval_date: self.metadata.loc[
                self.metadata["eval_date"].eq(eval_date), "job_id"
            ].tolist()
            for eval_date in [*self.initial_dates, *self.test_dates]
        }
        if any(not job_ids for job_ids in self.expected_job_ids.values()):
            raise Stage003Error("label_metadata_month_empty")
        self.allowed_job_ids = set(self.metadata["job_id"])
        self.other_development_main_job_ids = set(
            other_development_main_job_ids or set()
        )
        self.a2_job_ids = set(a2_job_ids or set())
        if (
            self.allowed_job_ids & self.other_development_main_job_ids
            or self.allowed_job_ids & self.a2_job_ids
            or self.other_development_main_job_ids & self.a2_job_ids
        ):
            raise Stage003Error("label_job_scope_sets_overlap")
        self._opened: dict[str, pd.DataFrame] = {}
        self._opened_job_ids: set[str] = set()
        self._initial_opened = False
        self._initial_rows = 0
        self._test_rows_after_seal = 0

    def _verify_eligibility_identity(self, identity: pd.Series) -> Path:
        eligibility_key = str(identity["eligibility_key"])
        expected_sha256 = str(identity["eligibility_sha256"])
        relative = f"eligibility/{eligibility_key}.csv"
        manifest_identity = self.manifest_files.get(relative)
        if (
            not isinstance(manifest_identity, Mapping)
            or set(manifest_identity) != {"size", "sha256"}
            or type(manifest_identity.get("size")) is not int
            or manifest_identity["size"] < 0
            or manifest_identity.get("sha256") != expected_sha256
        ):
            raise Stage003Error(
                f"eligibility_manifest_identity_invalid:{eligibility_key}"
            )
        path = self.label_root.parent / "eligibility" / f"{eligibility_key}.csv"
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size != manifest_identity["size"]
            or _sha256_file(path) != expected_sha256
        ):
            raise Stage003Error(f"eligibility_identity_mismatch:{eligibility_key}")
        self.event_ledger.record(
            "eligibility_file_verified",
            eval_date=str(identity["eval_date"]),
            job_id=str(identity["job_id"]),
            eligibility_key=eligibility_key,
            eligibility_sha256=expected_sha256,
        )
        return path

    def _verify_label_identity(self, job_id: str) -> Path:
        relative = f"job_outputs/{job_id}/label.json"
        identity = self.manifest_files.get(relative)
        if not isinstance(identity, Mapping) or set(identity) != {"size", "sha256"}:
            raise Stage003Error(f"label_manifest_identity_invalid:{job_id}")
        size = identity.get("size")
        digest = identity.get("sha256")
        if (
            type(size) is not int
            or size < 0
            or not isinstance(digest, str)
            or LOWER_HEX_64.fullmatch(digest) is None
        ):
            raise Stage003Error(f"label_manifest_identity_invalid:{job_id}")
        path = self.label_root / job_id / "label.json"
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size != size
            or _sha256_file(path) != digest
        ):
            raise Stage003Error(f"label_identity_mismatch:{job_id}")
        return path

    def _load_exact_month(
        self, eval_date: str, job_ids: list[str], *, phase: str
    ) -> pd.DataFrame:
        expected = self.expected_job_ids.get(eval_date)
        if expected is None or job_ids != expected:
            raise Stage003Error("test_label_job_ids_invalid")
        if len(job_ids) != len(set(job_ids)) or set(job_ids) & self._opened_job_ids:
            raise Stage003Error(f"test_label_month_already_opened:{eval_date}")
        metadata = self.metadata[self.metadata["eval_date"].eq(eval_date)].copy()
        metadata_by_job = metadata.set_index("job_id", drop=False)
        for job_id in job_ids:
            self._verify_eligibility_identity(metadata_by_job.loc[job_id])
        paths = {job_id: self._verify_label_identity(job_id) for job_id in job_ids}
        rows: list[dict[str, Any]] = []
        for job_id in job_ids:
            identity = metadata_by_job.loc[job_id]
            self.event_ledger.record(
                "label_file_read",
                phase=phase,
                eval_date=str(identity["eval_date"]),
                next_eval_date=str(identity["next_eval_date"]),
                product_vt_symbol=str(identity["product_vt_symbol"]),
                a_rank=int(identity["a_rank"]),
                job_id=job_id,
                job_type=str(identity["job_type"]),
                split=str(identity["split"]),
            )
            payload = _load_json(paths[job_id])
            if not isinstance(payload, dict) or set(payload) != set(LABEL_VALUE_COLUMNS):
                raise Stage003Error(f"label_payload_keys_invalid:{job_id}")
            values: dict[str, float] = {}
            for name in LABEL_VALUE_COLUMNS:
                value = payload[name]
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise Stage003Error(f"label_payload_value_invalid:{job_id}:{name}")
                numeric = float(value)
                if not math.isfinite(numeric):
                    raise Stage003Error(f"label_payload_value_invalid:{job_id}:{name}")
                values[name] = numeric
            rows.append(
                {
                    "eval_date": str(identity["eval_date"]),
                    "next_eval_date": str(identity["next_eval_date"]),
                    "product_vt_symbol": str(identity["product_vt_symbol"]),
                    "a_rank": int(identity["a_rank"]),
                    "split": str(identity["split"]),
                    "job_type": str(identity["job_type"]),
                    "job_id": job_id,
                    "eligibility_key": str(identity["eligibility_key"]),
                    "eligibility_sha256": str(identity["eligibility_sha256"]),
                    **values,
                }
            )
        result = _ordered_fold_rows(pd.DataFrame(rows))
        anchor = result[result["a_rank"].eq(10)]
        if len(anchor) != 1:
            raise Stage003Error(f"label_rank10_anchor_invalid:{eval_date}")
        base_equity = float(anchor.iloc[0]["base_equity"])
        if not np.equal(result["base_equity"].to_numpy(dtype="float64"), base_equity).all():
            raise Stage003Error(f"label_base_equity_mismatch:{eval_date}")
        result["return_delta"] = result["future_return"] - float(
            anchor.iloc[0]["future_return"]
        )
        result["drawdown_improvement"] = result["future_max_drawdown"] - float(
            anchor.iloc[0]["future_max_drawdown"]
        )
        result.loc[result["a_rank"].eq(10), ["return_delta", "drawdown_improvement"]] = 0.0
        if not np.isfinite(
            result[["return_delta", "drawdown_improvement"]].to_numpy(dtype="float64")
        ).all():
            raise Stage003Error(f"label_delta_nonfinite:{eval_date}")
        self._opened[eval_date] = result
        self._opened_job_ids.update(job_ids)
        return result.copy()

    def open_initial_labels(self) -> pd.DataFrame:
        if self._initial_opened or self._opened:
            raise Stage003Error("initial_labels_already_opened")
        frames = []
        for eval_date in self.initial_dates:
            frame = self._load_exact_month(
                eval_date,
                self.expected_job_ids[eval_date],
                phase="initial_mature_open",
            )
            frames.append(frame)
            self._initial_rows += len(frame)
        self._initial_opened = True
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def load(self, job_ids: list[str]) -> list[dict[str, Any]]:
        if not self._initial_opened:
            raise Stage003Error("initial_labels_not_opened")
        if not isinstance(job_ids, list) or any(
            not isinstance(job_id, str) for job_id in job_ids
        ):
            raise Stage003Error("test_label_job_ids_invalid")
        matching_dates = [
            eval_date
            for eval_date in self.test_dates
            if self.expected_job_ids[eval_date] == job_ids
        ]
        if len(matching_dates) != 1:
            raise Stage003Error("test_label_job_ids_invalid")
        eval_date = matching_dates[0]
        if eval_date in self._opened:
            raise Stage003Error(f"test_label_month_already_opened:{eval_date}")
        has_prior_seal = any(
            event["event_type"] == "active_seal_verified"
            and event.get("eval_date") == eval_date
            for event in self.event_ledger.events()
        )
        if not has_prior_seal:
            raise Stage003Error(f"test_label_seal_not_verified:{eval_date}")
        frame = self._load_exact_month(eval_date, job_ids, phase="effect_open")
        self._test_rows_after_seal += len(frame)
        return frame.to_dict(orient="records")

    def opened_labels(self) -> pd.DataFrame:
        frames = [self._opened[date] for date in sorted(self._opened)]
        return pd.concat(frames, ignore_index=True).copy() if frames else pd.DataFrame()

    def final_audit(self) -> dict[str, int]:
        events = self.event_ledger.events()
        label_events = [
            event for event in events if event["event_type"] == "label_file_read"
        ]
        initial_events = [
            event
            for event in label_events
            if event.get("phase") == "initial_mature_open"
        ]
        test_events = [
            event for event in label_events if event.get("phase") == "effect_open"
        ]
        seal_before_failures = sum(
            not any(
                candidate["event_type"] == "active_seal_verified"
                and candidate.get("eval_date") == event.get("eval_date")
                and int(candidate["sequence"]) < int(event["sequence"])
                for candidate in events
            )
            for event in test_events
        )
        other_development = sum(
            event.get("split") == "development"
            and event.get("job_type") == "main"
            and (
                event.get("job_id") in self.other_development_main_job_ids
                or event.get("job_id") not in self.allowed_job_ids
            )
            for event in label_events
        )
        a2_reads = sum(
            event.get("job_type") == "A2_sentinel"
            or event.get("job_id") in self.a2_job_ids
            for event in label_events
        )
        holdout_reads = sum(
            event.get("split") == "sealed_account_label_holdout"
            for event in label_events
        )
        training_events = [
            event
            for event in events
            if event["event_type"] == "training_label_used"
        ]
        same_fold_training = sum(
            str(event.get("label_eval_date", ""))
            >= str(event.get("test_eval_date", ""))
            or str(event.get("label_next_eval_date", ""))
            > str(event.get("test_eval_date", ""))
            for event in training_events
        )
        preselection_test_reads = sum(
            not any(
                candidate["event_type"] == "selection_created"
                and candidate.get("eval_date") == event.get("eval_date")
                and int(candidate["sequence"]) < int(event["sequence"])
                for candidate in events
            )
            for event in test_events
        )
        aggregate_rows_parsed = {
            source: sum(
                int(event.get("data_rows_parsed", -1))
                for event in events
                if event["event_type"] == "aggregate_header_verified"
                and event.get("source") == source
            )
            for source in ["development_labels_aggregate", "reconciliation_aggregate"]
        }
        return {
            "aggregate_development_label_data_rows_parsed": int(
                aggregate_rows_parsed["development_labels_aggregate"]
            ),
            "aggregate_reconciliation_data_rows_parsed": int(
                aggregate_rows_parsed["reconciliation_aggregate"]
            ),
            "initial_mature_label_rows_opened": int(len(initial_events)),
            "oos_test_label_rows_opened_before_own_pre_effect_seal": int(
                seal_before_failures
            ),
            "oos_test_label_rows_opened_after_own_pre_effect_seal": int(
                len(test_events) - seal_before_failures
            ),
            "unique_job_label_rows_opened": int(
                len({str(event.get("job_id")) for event in label_events})
            ),
            "other_development_main_label_rows_read": int(other_development),
            "a2_label_rows_read": int(a2_reads),
            "sealed_holdout_label_rows_read": int(holdout_reads),
            "same_fold_test_label_rows_used_for_training": int(
                same_fold_training
            ),
            "test_label_rows_used_for_preprocessing_or_selection": int(
                preselection_test_reads
            ),
        }


def _build_joint_relevance(labels: pd.DataFrame) -> pd.DataFrame:
    required = {"eval_date", "a_rank", "return_delta", "drawdown_improvement"}
    if not required.issubset(labels.columns):
        raise Stage003Error("joint_relevance_columns_missing")
    result = labels.copy()
    result["eval_date"] = pd.to_datetime(result["eval_date"], errors="coerce").dt.normalize()
    for column in ["return_delta", "drawdown_improvement"]:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    if result[["eval_date", "return_delta", "drawdown_improvement"]].isna().any().any():
        raise Stage003Error("joint_relevance_values_invalid")
    result["return_relevance"] = (
        result.groupby("eval_date", sort=False)["return_delta"]
        .rank(method="dense", ascending=True)
        .astype(int)
        - 1
    )
    result["drawdown_relevance"] = (
        result.groupby("eval_date", sort=False)["drawdown_improvement"]
        .rank(method="dense", ascending=True)
        .astype(int)
        - 1
    )
    result["joint_relevance"] = result[
        ["return_relevance", "drawdown_relevance"]
    ].min(axis=1).astype(int)
    for eval_date, group in result.groupby("eval_date", sort=False):
        if group["joint_relevance"].nunique() < 2:
            raise Stage003Error(f"joint_relevance_degenerate:{pd.Timestamp(eval_date).date()}")
    return result


def _prepare_ranker_fold(
    *,
    train_panel: pd.DataFrame,
    test_panel: pd.DataFrame,
    opened_labels: pd.DataFrame,
    test_eval_date: str,
) -> dict[str, Any]:
    train = _normalize_iso_dates(
        train_panel, ["eval_date", "next_eval_date"]
    )
    test = _normalize_iso_dates(test_panel, ["eval_date", "next_eval_date"])
    labels = _normalize_iso_dates(
        opened_labels, ["eval_date", "next_eval_date"]
    )
    train["a_rank"] = _strict_integer_rank(train["a_rank"], "train_a_rank")
    test["a_rank"] = _strict_integer_rank(test["a_rank"], "test_a_rank")
    labels["a_rank"] = _strict_integer_rank(labels["a_rank"], "label_a_rank")
    train = _ordered_fold_rows(train)
    test = _ordered_fold_rows(test)
    if test.empty or not test["eval_date"].eq(test_eval_date).all():
        raise Stage003Error("fold_test_date_invalid")
    if train["eval_date"].ge(test_eval_date).any() or train["next_eval_date"].gt(
        test_eval_date
    ).any():
        raise Stage003Error("fold_training_pit_violation")
    join_keys = [
        "eval_date",
        "next_eval_date",
        "product_vt_symbol",
        "a_rank",
        "job_id",
    ]
    if train.duplicated(join_keys).any() or labels.duplicated(join_keys).any():
        raise Stage003Error("fold_label_join_duplicate")
    required_label_columns = {*join_keys, "return_delta", "drawdown_improvement"}
    if missing := sorted(required_label_columns - set(labels.columns)):
        raise Stage003Error(f"fold_label_columns_missing:{missing}")
    labeled = train.merge(
        labels[[*join_keys, "return_delta", "drawdown_improvement"]],
        on=join_keys,
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    if len(labeled) != len(train) or labeled["_merge"].ne("both").any():
        raise Stage003Error("fold_training_labels_not_open")
    labeled.drop(columns=["_merge"], inplace=True)
    labeled = _ordered_fold_rows(_build_joint_relevance(labeled))
    train_matrix = _extract_ranker_matrix(labeled, MODEL_FEATURES).reset_index(drop=True)
    test_matrix = _extract_ranker_matrix(test, MODEL_FEATURES).reset_index(drop=True)
    qid, boundaries = _group_boundaries(labeled)
    target = labeled["joint_relevance"].astype("int64").reset_index(drop=True)
    if (target < 0).any() or not all(type(value) is int for value in target.tolist()):
        raise Stage003Error("fold_target_invalid")
    training_identities = [
        {
            "job_id": str(row.job_id),
            "eval_date": str(row.eval_date),
            "next_eval_date": str(row.next_eval_date),
            "product_vt_symbol": str(row.product_vt_symbol),
            "a_rank": int(row.a_rank),
        }
        for row in labeled.itertuples(index=False)
    ]
    test_keys = [
        {
            "eval_date": str(row.eval_date),
            "product_vt_symbol": str(row.product_vt_symbol),
            "a_rank": int(row.a_rank),
        }
        for row in test.itertuples(index=False)
    ]
    fold_input = {
        "eval_date": test_eval_date,
        "feature_order": list(MODEL_FEATURES),
        "qid": qid,
        "group_boundaries": boundaries,
        "ordered_training_job_identities": training_identities,
        "ordered_test_keys": test_keys,
    }
    _validate_fold_input(fold_input, test_eval_date)
    return {
        "ordered_training": labeled,
        "ordered_test": test,
        "train_matrix": train_matrix,
        "test_matrix": test_matrix,
        "target": target,
        "qid": qid,
        "fold_input": fold_input,
    }


def _fit_repeated_ranker(
    train_matrix: pd.DataFrame,
    target: pd.Series | np.ndarray,
    qid_values: list[int] | np.ndarray,
    test_matrix: pd.DataFrame,
    *,
    model_params: Mapping[str, Any],
    ranker_factory: Any,
    event_ledger: ExecutionEventLedger,
    eval_date: str,
) -> dict[str, Any]:
    if list(train_matrix.columns) != MODEL_FEATURES or list(test_matrix.columns) != MODEL_FEATURES:
        raise Stage003Error("fit_feature_order_invalid")
    if dict(model_params) != MODEL_PARAMS:
        raise Stage003Error("fit_model_params_invalid")
    train_values = train_matrix.to_numpy(dtype="float64")
    test_values = test_matrix.to_numpy(dtype="float64")
    if (
        not len(train_matrix)
        or not len(test_matrix)
        or not np.isfinite(train_values).all()
        or not np.isfinite(test_values).all()
    ):
        raise Stage003Error("fit_matrix_invalid")
    y = np.asarray(target)
    qid = np.asarray(qid_values)
    if (
        y.dtype.kind not in "iu"
        or qid.dtype.kind not in "iu"
        or len(y) != len(train_matrix)
        or len(qid) != len(train_matrix)
        or (y < 0).any()
        or (len(qid) and (qid[0] != 0 or np.any(np.diff(qid) < 0)))
    ):
        raise Stage003Error("fit_target_or_qid_invalid")
    for group in np.unique(qid):
        if len(np.unique(y[qid == group])) < 2:
            raise Stage003Error(f"fit_target_group_degenerate:{int(group)}")

    predictions: list[np.ndarray] = []
    model_bytes: list[bytes] = []
    primary_feature_usage: dict[str, float] | None = None
    if not isinstance(event_ledger, ExecutionEventLedger):
        raise Stage003Error("fit_event_ledger_invalid")
    params_sha256 = _sha256_bytes(
        _canonical_json_bytes(dict(model_params), newline=False)
    )
    for _ in range(2):
        fit_index = len(predictions)
        fit_role = "primary" if fit_index == 0 else "repeat"
        event_ledger.record(
            "fit_started",
            eval_date=eval_date,
            fit_role=fit_role,
            params_sha256=params_sha256,
        )
        model = ranker_factory(**dict(model_params))
        model.fit(train_matrix, y.astype("int64"), qid=qid.astype("int64"), verbose=False)
        prediction = np.asarray(model.predict(test_matrix), dtype="float64")
        if prediction.shape != (len(test_matrix),) or not np.isfinite(prediction).all():
            raise Stage003Error("fit_prediction_invalid")
        booster = model.get_booster()
        raw = bytes(booster.save_raw(raw_format="ubj"))
        if not raw:
            raise Stage003Error("fit_model_bytes_empty")
        model_sha256 = _sha256_bytes(raw)
        event_ledger.record(
            "fit_completed",
            eval_date=eval_date,
            fit_role=fit_role,
            params_sha256=params_sha256,
            model_sha256=model_sha256,
        )
        event_ledger.record(
            "prediction_completed",
            eval_date=eval_date,
            fit_role=fit_role,
            prediction_rows=int(len(prediction)),
            split="development",
        )
        if primary_feature_usage is None:
            usage = booster.get_score(importance_type="weight")
            primary_feature_usage = {
                str(feature): float(count) for feature, count in usage.items()
            }
        predictions.append(prediction)
        model_bytes.append(raw)
    difference = float(
        np.max(np.abs(predictions[0] - predictions[1]), initial=0.0)
    )
    if difference > 1e-12:
        raise Stage003Error(f"fit_prediction_nondeterministic:{difference}")
    if model_bytes[0] != model_bytes[1]:
        raise Stage003Error("fit_model_bytes_nondeterministic")
    if len(np.unique(predictions[0])) < 2:
        raise Stage003Error("fit_prediction_degenerate")
    return {
        "predictions": predictions[0],
        "repeat_predictions": predictions[1],
        "prediction_repeat_max_abs_difference": difference,
        "primary_model_bytes": model_bytes[0],
        "repeat_model_bytes": model_bytes[1],
        "primary_model_sha256": _sha256_bytes(model_bytes[0]),
        "repeat_model_sha256": _sha256_bytes(model_bytes[1]),
        "primary_feature_usage": primary_feature_usage or {},
        "fit_call_count": 2,
        "factory_is_exact_xgboost_ranker": ranker_factory is xgboost.XGBRanker,
    }


def _prediction_frame_for_test(
    rows: list[tuple[str, int, float, float, float]], eval_date: str
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "eval_date": eval_date,
                "product_vt_symbol": product,
                "a_rank": rank,
                "pit_logistic_probability": probability,
                "primary_xgb_score": primary,
                "repeat_xgb_score": repeat,
            }
            for product, rank, probability, primary, repeat in rows
        ]
    )


def _build_prediction_payload(eval_date: str, rows: pd.DataFrame) -> dict[str, Any]:
    required = [
        "eval_date",
        "product_vt_symbol",
        "a_rank",
        "pit_logistic_probability",
        "primary_xgb_score",
        "repeat_xgb_score",
    ]
    if not set(required).issubset(rows.columns):
        raise Stage003SealError("prediction_columns_missing")
    frame = rows[required].copy()
    frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    for column in ["pit_logistic_probability", "primary_xgb_score", "repeat_xgb_score"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame.isna().any().any() or not np.isfinite(
        frame[["pit_logistic_probability", "primary_xgb_score", "repeat_xgb_score"]].to_numpy()
    ).all():
        raise Stage003SealError("prediction_values_invalid")
    if not frame["eval_date"].eq(eval_date).all():
        raise Stage003SealError("prediction_eval_date_invalid")
    if float((frame["primary_xgb_score"] - frame["repeat_xgb_score"]).abs().max()) > 1e-12:
        raise Stage003SealError("repeat_prediction_mismatch")
    if frame["primary_xgb_score"].nunique() < 2:
        raise Stage003SealError("prediction_degenerate")
    frame["lr_percentile"] = frame["pit_logistic_probability"].rank(
        method="average", ascending=True, pct=True
    )
    frame["xgb_percentile"] = frame["primary_xgb_score"].rank(
        method="average", ascending=True, pct=True
    )
    frame["ensemble_score"] = (frame["lr_percentile"] + frame["xgb_percentile"]) / 2.0
    frame = frame.sort_values(["a_rank", "product_vt_symbol"], kind="mergesort")
    ordered_rows = []
    for record in frame.to_dict(orient="records"):
        ordered_rows.append(
            {
                "eval_date": str(record["eval_date"]),
                "product_vt_symbol": str(record["product_vt_symbol"]),
                "a_rank": int(record["a_rank"]),
                "pit_logistic_probability": float(record["pit_logistic_probability"]),
                "primary_xgb_score": float(record["primary_xgb_score"]),
                "repeat_xgb_score": float(record["repeat_xgb_score"]),
                "lr_percentile": float(record["lr_percentile"]),
                "xgb_percentile": float(record["xgb_percentile"]),
                "ensemble_score": float(record["ensemble_score"]),
            }
        )
    return {"eval_date": eval_date, "ordered_rows": ordered_rows}


def _arm(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "a_rank": int(record["a_rank"]),
        "product_vt_symbol": str(record["product_vt_symbol"]),
    }


def _build_selection_payload(prediction: Mapping[str, Any]) -> dict[str, Any]:
    payload = _require_exact_keys(
        prediction, PREDICTION_KEYS, "prediction", Stage003SealError
    )
    rows = payload["ordered_rows"]
    if not isinstance(rows, list) or not rows:
        raise Stage003SealError("prediction_rows_invalid")
    for row in rows:
        _require_exact_keys(row, PREDICTION_ROW_KEYS, "prediction_row", Stage003SealError)
    anchors = [row for row in rows if row["a_rank"] == 10]
    if len(anchors) != 1:
        raise Stage003SealError("selection_rank10_invalid")
    b_order = sorted(
        rows,
        key=lambda row: (
            -float(row["xgb_percentile"]),
            -float(row["pit_logistic_probability"]),
            int(row["a_rank"]),
            str(row["product_vt_symbol"]),
        ),
    )
    c_order = sorted(
        rows,
        key=lambda row: (
            -float(row["ensemble_score"]),
            -float(row["pit_logistic_probability"]),
            int(row["a_rank"]),
            str(row["product_vt_symbol"]),
        ),
    )
    return {
        "eval_date": str(payload["eval_date"]),
        "arm_a": _arm(anchors[0]),
        "arm_b": _arm(b_order[0]),
        "arm_c": _arm(c_order[0]),
        "tie_break_trace": {
            "arm_b_order": [_arm(row) for row in b_order],
            "arm_c_order": [_arm(row) for row in c_order],
        },
    }


def _validate_fold_input(fold_input: Any, eval_date: str) -> Mapping[str, Any]:
    payload = _require_exact_keys(
        fold_input, FOLD_INPUT_KEYS, "fold_input", Stage003SealError
    )
    if payload["eval_date"] != eval_date or payload["feature_order"] != MODEL_FEATURES:
        raise Stage003SealError("fold_input_identity_invalid")
    for name in ["qid", "group_boundaries"]:
        values = payload[name]
        if not isinstance(values, list) or any(
            isinstance(value, bool) or not isinstance(value, int) for value in values
        ):
            raise Stage003SealError(f"fold_input_{name}_invalid")
    training_identities = payload["ordered_training_job_identities"]
    test_keys = payload["ordered_test_keys"]
    if not isinstance(training_identities, list) or not isinstance(test_keys, list):
        raise Stage003SealError("fold_input_rows_invalid")
    training_keys = {
        "job_id",
        "eval_date",
        "next_eval_date",
        "product_vt_symbol",
        "a_rank",
    }
    test_key_fields = {"eval_date", "product_vt_symbol", "a_rank"}
    for row in training_identities:
        item = _require_exact_keys(
            row, training_keys, "training_job_identity", Stage003SealError
        )
        for name in ["job_id", "eval_date", "next_eval_date", "product_vt_symbol"]:
            _require_string(
                item[name], f"training_identity_{name}", Stage003SealError
            )
        _require_int(item["a_rank"], "training_identity_a_rank", Stage003SealError)
    for row in test_keys:
        item = _require_exact_keys(row, test_key_fields, "test_key", Stage003SealError)
        for name in ["eval_date", "product_vt_symbol"]:
            _require_string(item[name], f"test_key_{name}", Stage003SealError)
        _require_int(item["a_rank"], "test_key_a_rank", Stage003SealError)
        if item["eval_date"] != eval_date:
            raise Stage003SealError("test_key_eval_date_invalid")
    qid = payload["qid"]
    boundaries = payload["group_boundaries"]
    if (
        len(qid) != len(training_identities)
        or not boundaries
        or boundaries[0] != 0
        or boundaries[-1] != len(qid)
        or any(right <= left for left, right in zip(boundaries, boundaries[1:]))
        or any(right < left for left, right in zip(qid, qid[1:]))
    ):
        raise Stage003SealError("fold_input_group_structure_invalid")
    return payload


def _persist_active_fold(
    root: Path,
    eval_date: str,
    *,
    primary_model_bytes: bytes,
    repeat_model_bytes: bytes,
    fold_input: Mapping[str, Any],
    prediction: Mapping[str, Any],
    selection: Mapping[str, Any],
    label_read_count_before_seal: int,
) -> dict[str, Any]:
    if _require_int(
        label_read_count_before_seal, "label_read_count_before_seal", Stage003SealError
    ) != 0:
        raise Stage003SealError("label_read_before_seal_nonzero")
    if not primary_model_bytes or primary_model_bytes != repeat_model_bytes:
        raise Stage003SealError("model_bytes_mismatch")
    _validate_fold_input(fold_input, eval_date)
    rebuilt_selection = _build_selection_payload(prediction)
    if _canonical_json_bytes(rebuilt_selection) != _canonical_json_bytes(selection):
        raise Stage003SealError("selection_not_recomputable")
    root = Path(root)
    paths = {
        "primary_model": root / f"models/{eval_date}_primary.ubj",
        "repeat_model": root / f"models/{eval_date}_repeat.ubj",
        "fold_input": root / f"fold_inputs/{eval_date}.json",
        "prediction": root / f"predictions/{eval_date}.json",
        "selection": root / f"selections/{eval_date}.json",
    }
    payloads = {
        "primary_model": bytes(primary_model_bytes),
        "repeat_model": bytes(repeat_model_bytes),
        "fold_input": _canonical_json_bytes(fold_input),
        "prediction": _canonical_json_bytes(prediction),
        "selection": _canonical_json_bytes(selection),
    }
    for name in ["primary_model", "repeat_model", "fold_input", "prediction", "selection"]:
        _atomic_link_publish(paths[name], payloads[name])
    seal = {
        "seal_type": "active_model_fold",
        "eval_date": eval_date,
        "label_read_count_before_seal": 0,
        "primary_model_sha256": _sha256_bytes(payloads["primary_model"]),
        "repeat_model_sha256": _sha256_bytes(payloads["repeat_model"]),
        "fold_input_sha256": _sha256_bytes(payloads["fold_input"]),
        "prediction_sha256": _sha256_bytes(payloads["prediction"]),
        "selection_sha256": _sha256_bytes(payloads["selection"]),
    }
    _atomic_link_publish(
        root / f"pre_effect_seals/{eval_date}.json", _canonical_json_bytes(seal)
    )
    return seal


def _verify_active_fold(
    root: Path, eval_date: str, expected_fold_input: Mapping[str, Any]
) -> dict[str, Any]:
    root = Path(root)
    seal_path = root / f"pre_effect_seals/{eval_date}.json"
    seal = _require_exact_keys(
        _load_json(seal_path, Stage003SealError),
        ACTIVE_SEAL_KEYS,
        "active_seal",
        Stage003SealError,
    )
    if seal["seal_type"] != "active_model_fold" or seal["eval_date"] != eval_date:
        raise Stage003SealError("active_seal_identity_invalid")
    if _require_int(
        seal["label_read_count_before_seal"],
        "label_read_count_before_seal",
        Stage003SealError,
    ) != 0:
        raise Stage003SealError("active_seal_label_count_invalid")
    paths = {
        "primary_model": root / f"models/{eval_date}_primary.ubj",
        "repeat_model": root / f"models/{eval_date}_repeat.ubj",
        "fold_input": root / f"fold_inputs/{eval_date}.json",
        "prediction": root / f"predictions/{eval_date}.json",
        "selection": root / f"selections/{eval_date}.json",
    }
    digest_keys = {
        "primary_model": "primary_model_sha256",
        "repeat_model": "repeat_model_sha256",
        "fold_input": "fold_input_sha256",
        "prediction": "prediction_sha256",
        "selection": "selection_sha256",
    }
    payload_bytes: dict[str, bytes] = {}
    for name, path in paths.items():
        try:
            payload_bytes[name] = path.read_bytes()
        except OSError as exc:
            raise Stage003SealError(f"active_payload_missing:{name}") from exc
        expected_digest = _require_hex(
            seal[digest_keys[name]], digest_keys[name], Stage003SealError
        )
        if _sha256_bytes(payload_bytes[name]) != expected_digest:
            raise Stage003SealError(f"active_payload_sha256_mismatch:{name}")
    if payload_bytes["primary_model"] != payload_bytes["repeat_model"]:
        raise Stage003SealError("active_model_bytes_not_repeat_exact")

    fold_input = json.loads(payload_bytes["fold_input"].decode("utf-8"))
    _validate_fold_input(fold_input, eval_date)
    if _canonical_json_bytes(fold_input) != payload_bytes["fold_input"]:
        raise Stage003SealError("fold_input_not_canonical")
    if _canonical_json_bytes(fold_input) != _canonical_json_bytes(expected_fold_input):
        raise Stage003SealError("fold_input_state_mismatch")

    prediction = _require_exact_keys(
        json.loads(payload_bytes["prediction"].decode("utf-8")),
        PREDICTION_KEYS,
        "prediction",
        Stage003SealError,
    )
    rows = prediction["ordered_rows"]
    if not isinstance(rows, list):
        raise Stage003SealError("prediction_rows_invalid")
    raw_frame = pd.DataFrame(
        [
            {
                key: row[key]
                for key in [
                    "eval_date",
                    "product_vt_symbol",
                    "a_rank",
                    "pit_logistic_probability",
                    "primary_xgb_score",
                    "repeat_xgb_score",
                ]
            }
            for row in rows
            if _require_exact_keys(
                row, PREDICTION_ROW_KEYS, "prediction_row", Stage003SealError
            )
        ]
    )
    rebuilt_prediction = _build_prediction_payload(eval_date, raw_frame)
    if _canonical_json_bytes(rebuilt_prediction) != payload_bytes["prediction"]:
        raise Stage003SealError("prediction_not_recomputable")
    expected_test_keys = fold_input["ordered_test_keys"]
    prediction_test_keys = [
        {
            "eval_date": row["eval_date"],
            "product_vt_symbol": row["product_vt_symbol"],
            "a_rank": row["a_rank"],
        }
        for row in rebuilt_prediction["ordered_rows"]
    ]
    if prediction_test_keys != expected_test_keys:
        raise Stage003SealError("prediction_test_keys_mismatch")

    selection = _require_exact_keys(
        json.loads(payload_bytes["selection"].decode("utf-8")),
        SELECTION_KEYS,
        "selection",
        Stage003SealError,
    )
    rebuilt_selection = _build_selection_payload(rebuilt_prediction)
    if _canonical_json_bytes(selection) != payload_bytes["selection"]:
        raise Stage003SealError("selection_not_canonical")
    if _canonical_json_bytes(rebuilt_selection) != payload_bytes["selection"]:
        raise Stage003SealError("selection_not_recomputable")
    return {
        "seal": dict(seal),
        "fold_input": fold_input,
        "prediction": rebuilt_prediction,
        "selection": rebuilt_selection,
    }


def _effect_open(
    root: Path,
    eval_date: str,
    *,
    expected_fold_input: Mapping[str, Any],
    label_store: LabelStore,
    job_ids: list[str],
) -> dict[str, Any]:
    verified = _verify_active_fold(root, eval_date, expected_fold_input)
    ledger = getattr(label_store, "event_ledger", None)
    if isinstance(ledger, ExecutionEventLedger):
        if not any(
            event["event_type"] == "selection_created"
            and event.get("eval_date") == eval_date
            for event in ledger.events()
        ):
            ledger.record(
                "selection_created",
                eval_date=eval_date,
                selection_sha256=verified["seal"]["selection_sha256"],
            )
        ledger.record(
            "active_seal_verified",
            eval_date=eval_date,
            seal_sha256=_sha256_file(
                Path(root) / f"pre_effect_seals/{eval_date}.json"
            ),
        )
        ledger.record(
            "selection_recomputed",
            eval_date=eval_date,
            selection_sha256=verified["seal"]["selection_sha256"],
        )
    labels = label_store.load(job_ids)
    return {**verified, "labels": labels}


def _validate_arm(value: Any, name: str) -> Mapping[str, Any]:
    arm = _require_exact_keys(value, ARM_KEYS, name, Stage003SealError)
    _require_string(arm["product_vt_symbol"], f"{name}_product", Stage003SealError)
    _require_int(arm["a_rank"], f"{name}_rank", Stage003SealError)
    return arm


def _persist_fallback_seal(root: Path, eval_date: str, arm: Mapping[str, Any]) -> dict[str, Any]:
    validated_arm = dict(_validate_arm(arm, "fallback_arm"))
    if validated_arm["a_rank"] != 10:
        raise Stage003SealError("fallback_arm_not_rank10")
    seal = {
        "seal_type": "fallback_fold",
        "eval_date": eval_date,
        "reason": "fallback_no_complete_physical_evidence",
        "arm_a": validated_arm,
        "arm_b": validated_arm,
        "arm_c": validated_arm,
        "label_read_count_before_seal": 0,
        "label_read_count_after_seal": 0,
    }
    _atomic_link_publish(
        Path(root) / f"pre_effect_seals/{eval_date}.json", _canonical_json_bytes(seal)
    )
    return seal


def _verify_fallback_seal(
    root: Path, eval_date: str, expected_arm: Mapping[str, Any]
) -> dict[str, Any]:
    path = Path(root) / f"pre_effect_seals/{eval_date}.json"
    seal = _require_exact_keys(
        _load_json(path, Stage003SealError),
        FALLBACK_SEAL_KEYS,
        "fallback_seal",
        Stage003SealError,
    )
    if (
        seal["seal_type"] != "fallback_fold"
        or seal["eval_date"] != eval_date
        or seal["reason"] != "fallback_no_complete_physical_evidence"
    ):
        raise Stage003SealError("fallback_seal_identity_invalid")
    expected = dict(_validate_arm(expected_arm, "expected_fallback_arm"))
    for key in ["arm_a", "arm_b", "arm_c"]:
        if dict(_validate_arm(seal[key], key)) != expected:
            raise Stage003SealError("fallback_arm_mismatch")
    for key in ["label_read_count_before_seal", "label_read_count_after_seal"]:
        if _require_int(seal[key], key, Stage003SealError) != 0:
            raise Stage003SealError("fallback_label_count_invalid")
    if _canonical_json_bytes(seal) != path.read_bytes():
        raise Stage003SealError("fallback_seal_not_canonical")
    return dict(seal)


def _fallback_effect_row(eval_date: str, arm: Mapping[str, Any]) -> dict[str, Any]:
    validated = dict(_validate_arm(arm, "fallback_effect_arm"))
    if validated["a_rank"] != 10:
        raise Stage003Error("fallback_effect_arm_not_rank10")
    return {
        "eval_date": eval_date,
        "seal_type": "fallback_fold",
        "arm_a_product_vt_symbol": validated["product_vt_symbol"],
        "arm_a_a_rank": 10,
        "arm_b_product_vt_symbol": validated["product_vt_symbol"],
        "arm_b_a_rank": 10,
        "arm_c_product_vt_symbol": validated["product_vt_symbol"],
        "arm_c_a_rank": 10,
        "arm_c_replaced": False,
        "return_delta": 0.0,
        "drawdown_improvement": 0.0,
    }


def _active_effect_row(
    eval_date: str,
    selection: Mapping[str, Any],
    labels: list[Mapping[str, Any]],
) -> dict[str, Any]:
    selected = _require_exact_keys(
        selection, SELECTION_KEYS, "effect_selection", Stage003Error
    )
    if selected["eval_date"] != eval_date:
        raise Stage003Error("effect_selection_date_invalid")
    arms = {
        name: dict(_validate_arm(selected[name], f"effect_{name}"))
        for name in ["arm_a", "arm_b", "arm_c"]
    }
    if not isinstance(labels, list) or not labels:
        raise Stage003Error("effect_labels_invalid")
    frame = pd.DataFrame([dict(row) for row in labels])
    required = {
        "eval_date",
        "product_vt_symbol",
        "a_rank",
        "return_delta",
        "drawdown_improvement",
    }
    if missing := sorted(required - set(frame.columns)):
        raise Stage003Error(f"effect_label_columns_missing:{missing}")
    frame = _normalize_iso_dates(frame, ["eval_date"])
    frame["a_rank"] = _strict_integer_rank(frame["a_rank"], "effect_label_a_rank")
    if not frame["eval_date"].eq(eval_date).all() or frame.duplicated(
        ["eval_date", "product_vt_symbol", "a_rank"]
    ).any():
        raise Stage003Error("effect_label_identity_invalid")

    realized: dict[str, dict[str, Any]] = {}
    for name, arm in arms.items():
        match = frame[
            frame["a_rank"].eq(arm["a_rank"])
            & frame["product_vt_symbol"].astype(str).eq(arm["product_vt_symbol"])
        ]
        if len(match) != 1:
            raise Stage003Error(f"effect_arm_label_missing:{name}")
        row = match.iloc[0]
        return_delta = float(row["return_delta"])
        drawdown = float(row["drawdown_improvement"])
        if not math.isfinite(return_delta) or not math.isfinite(drawdown):
            raise Stage003Error(f"effect_arm_label_nonfinite:{name}")
        realized[name] = {
            **arm,
            "return_delta": return_delta,
            "drawdown_improvement": drawdown,
        }
    if arms["arm_a"]["a_rank"] != 10:
        raise Stage003Error("effect_arm_a_not_rank10")
    replaced = arms["arm_c"] != arms["arm_a"]
    c_return = realized["arm_c"]["return_delta"] if replaced else 0.0
    c_drawdown = realized["arm_c"]["drawdown_improvement"] if replaced else 0.0
    return {
        "eval_date": eval_date,
        "seal_type": "active_model_fold",
        "arm_a_product_vt_symbol": arms["arm_a"]["product_vt_symbol"],
        "arm_a_a_rank": arms["arm_a"]["a_rank"],
        "arm_b_product_vt_symbol": arms["arm_b"]["product_vt_symbol"],
        "arm_b_a_rank": arms["arm_b"]["a_rank"],
        "arm_b_return_delta": realized["arm_b"]["return_delta"],
        "arm_b_drawdown_improvement": realized["arm_b"]["drawdown_improvement"],
        "arm_c_product_vt_symbol": arms["arm_c"]["product_vt_symbol"],
        "arm_c_a_rank": arms["arm_c"]["a_rank"],
        "arm_c_replaced": bool(replaced),
        "return_delta": float(c_return),
        "drawdown_improvement": float(c_drawdown),
    }


def _assemble_effect_sequence(
    active_rows: list[Mapping[str, Any]],
    fallback_rows: list[Mapping[str, Any]],
    contract: Mapping[str, Any],
) -> pd.DataFrame:
    required = {
        "eval_date",
        "seal_type",
        "arm_c_replaced",
        "arm_c_product_vt_symbol",
        "return_delta",
        "drawdown_improvement",
    }
    rows = [dict(row) for row in [*active_rows, *fallback_rows]]
    if any(not required.issubset(row) for row in rows):
        raise Stage003Error("effect_sequence_columns_invalid")
    frame = pd.DataFrame(rows)
    frame = _normalize_iso_dates(frame, ["eval_date"])
    if frame["eval_date"].duplicated().any():
        raise Stage003Error("effect_sequence_duplicate")
    expected_active = list(contract["folds"]["active_test_dates"])
    expected_fallback = list(contract["folds"]["fallback_test_dates"])
    expected_dates = sorted([*expected_active, *expected_fallback])
    if sorted(frame["eval_date"].tolist()) != expected_dates or len(frame) != len(
        expected_dates
    ):
        raise Stage003Error("effect_sequence_shape_invalid")
    if not frame["arm_c_replaced"].map(lambda value: type(value) is bool).all():
        raise Stage003Error("effect_sequence_replaced_type_invalid")
    for column in ["return_delta", "drawdown_improvement"]:
        values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype="float64")
        if not np.isfinite(values).all():
            raise Stage003Error("effect_sequence_value_invalid")
        frame[column] = values
    fallback = frame[frame["eval_date"].isin(expected_fallback)]
    active = frame[frame["eval_date"].isin(expected_active)]
    if (
        len(fallback) != int(contract["folds"]["fallback_month_count"])
        or not fallback["seal_type"].eq("fallback_fold").all()
        or fallback["arm_c_replaced"].any()
        or not fallback["return_delta"].eq(0.0).all()
        or not fallback["drawdown_improvement"].eq(0.0).all()
    ):
        raise Stage003Error("fallback_effect_nonzero_or_invalid")
    if len(active) != int(contract["folds"]["active_fold_count"]) or not active[
        "seal_type"
    ].eq("active_model_fold").all():
        raise Stage003Error("effect_sequence_active_invalid")
    frame.sort_values("eval_date", kind="mergesort", inplace=True)
    frame.reset_index(drop=True, inplace=True)
    return frame


def _run_frozen_training(
    *,
    state: Mapping[str, Any],
    label_store: PhaseGatedJobLabelStore,
    contract: Mapping[str, Any],
    staging_dir: Path,
    ranker_factory: Any,
    event_ledger: ExecutionEventLedger,
) -> dict[str, Any]:
    fold_contract = contract.get("folds")
    model_contract = contract.get("model")
    if not isinstance(fold_contract, Mapping) or not isinstance(model_contract, Mapping):
        raise Stage003Error("training_contract_shape_invalid")
    if (
        not isinstance(event_ledger, ExecutionEventLedger)
        or label_store.event_ledger is not event_ledger
    ):
        raise Stage003Error("training_event_ledger_invalid")
    staging_dir = Path(staging_dir)
    if not staging_dir.is_dir() or staging_dir.is_symlink() or any(staging_dir.iterdir()):
        raise Stage003Error("training_staging_dir_invalid")
    active_dates = list(fold_contract.get("active_test_dates", []))
    fallback_dates = list(fold_contract.get("fallback_test_dates", []))
    active_folds = state.get("active_folds")
    fallback_months = state.get("fallback_months")
    calendar_dates = state.get("oos_calendar_dates")
    if (
        not isinstance(active_folds, list)
        or not isinstance(fallback_months, pd.DataFrame)
        or not isinstance(calendar_dates, list)
    ):
        raise Stage003Error("training_state_shape_invalid")
    active_by_date = {
        str(fold.get("test_eval_date")): fold
        for fold in active_folds
        if isinstance(fold, Mapping)
    }
    if set(active_by_date) != set(active_dates) or len(active_by_date) != len(active_dates):
        raise Stage003Error("training_active_fold_identity_invalid")
    if fallback_months.empty or fallback_months["eval_date"].duplicated().any():
        raise Stage003Error("training_fallback_identity_invalid")
    fallback_by_date = {
        str(row.eval_date): row for row in fallback_months.itertuples(index=False)
    }
    if set(fallback_by_date) != set(fallback_dates):
        raise Stage003Error("training_fallback_identity_invalid")
    expected_calendar = sorted([*active_dates, *fallback_dates])
    if calendar_dates != expected_calendar:
        raise Stage003Error("training_calendar_invalid")

    initial_labels = label_store.open_initial_labels()
    if (
        len(initial_labels) != int(fold_contract.get("initial_training_rows", -1))
        or initial_labels["eval_date"].nunique()
        != int(fold_contract.get("initial_training_qids", -1))
    ):
        raise Stage003Error("training_initial_label_shape_invalid")

    fold_audit_rows: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    active_effect_rows: list[dict[str, Any]] = []
    fallback_effect_rows: list[dict[str, Any]] = []
    feature_usage_by_model: dict[str, dict[str, float]] = {}
    model_manifest: dict[str, dict[str, Any]] = {}
    active_seal_count = 0
    fallback_seal_count = 0
    selection_recomputed_count = 0
    fit_call_count = 0
    factory_exact = True

    for eval_date in calendar_dates:
        if eval_date in fallback_by_date:
            fallback = fallback_by_date[eval_date]
            arm = {
                "a_rank": int(fallback.a_rank),
                "product_vt_symbol": str(fallback.product_vt_symbol),
            }
            _persist_fallback_seal(staging_dir, eval_date, arm)
            _verify_fallback_seal(staging_dir, eval_date, arm)
            relative = f"pre_effect_seals/{eval_date}.json"
            event_ledger.record(
                "artifact_created",
                phase="pre_effect",
                relative_path=relative,
                sha256=_sha256_file(staging_dir / relative),
            )
            event_ledger.record(
                "fallback_seal_verified",
                eval_date=eval_date,
                seal_sha256=_sha256_file(staging_dir / relative),
            )
            fallback_effect_rows.append(_fallback_effect_row(eval_date, arm))
            fallback_seal_count += 1
            continue

        fold = active_by_date[eval_date]
        fold_index = active_dates.index(eval_date)
        if (
            int(fold.get("train_rows", -1))
            != int(fold_contract["training_rows"][fold_index])
            or int(fold.get("train_qids", -1))
            != int(fold_contract["training_qids"][fold_index])
            or int(fold.get("test_rows", -1))
            != int(fold_contract["test_rows"][fold_index])
            or fold.get("ranker_feature_order") != MODEL_FEATURES
        ):
            raise Stage003Error(f"training_fold_contract_mismatch:{eval_date}")
        opened_labels = label_store.opened_labels()
        if len(opened_labels) != int(fold["train_rows"]):
            raise Stage003Error(f"training_open_label_shape_invalid:{eval_date}")
        prepared = _prepare_ranker_fold(
            train_panel=fold["train_panel"],
            test_panel=fold["test_panel"],
            opened_labels=opened_labels,
            test_eval_date=eval_date,
        )
        for identity in prepared["fold_input"]["ordered_training_job_identities"]:
            event_ledger.record(
                "training_label_used",
                test_eval_date=eval_date,
                label_eval_date=identity["eval_date"],
                label_next_eval_date=identity["next_eval_date"],
                job_id=identity["job_id"],
            )
        fit = _fit_repeated_ranker(
            prepared["train_matrix"],
            prepared["target"],
            prepared["qid"],
            prepared["test_matrix"],
            model_params=model_contract.get("params", {}),
            ranker_factory=ranker_factory,
            event_ledger=event_ledger,
            eval_date=eval_date,
        )
        fit_call_count += int(fit["fit_call_count"])
        factory_exact = bool(factory_exact and fit["factory_is_exact_xgboost_ranker"])

        raw_prediction = prepared["ordered_test"][
            [
                "eval_date",
                "product_vt_symbol",
                "a_rank",
                "pit_logistic_probability",
            ]
        ].copy()
        raw_prediction["primary_xgb_score"] = fit["predictions"]
        raw_prediction["repeat_xgb_score"] = fit["repeat_predictions"]
        prediction = _build_prediction_payload(eval_date, raw_prediction)
        selection = _build_selection_payload(prediction)
        event_ledger.record(
            "selection_created",
            eval_date=eval_date,
            selection_sha256=_sha256_bytes(_canonical_json_bytes(selection)),
        )
        seal = _persist_active_fold(
            staging_dir,
            eval_date,
            primary_model_bytes=fit["primary_model_bytes"],
            repeat_model_bytes=fit["repeat_model_bytes"],
            fold_input=prepared["fold_input"],
            prediction=prediction,
            selection=selection,
            label_read_count_before_seal=0,
        )
        for relative in [
            f"models/{eval_date}_primary.ubj",
            f"models/{eval_date}_repeat.ubj",
            f"fold_inputs/{eval_date}.json",
            f"predictions/{eval_date}.json",
            f"selections/{eval_date}.json",
            f"pre_effect_seals/{eval_date}.json",
        ]:
            event_ledger.record(
                "artifact_created",
                phase="pre_effect",
                relative_path=relative,
                sha256=_sha256_file(staging_dir / relative),
            )
        effect_open = _effect_open(
            staging_dir,
            eval_date,
            expected_fold_input=prepared["fold_input"],
            label_store=label_store,
            job_ids=prepared["ordered_test"]["job_id"].astype(str).tolist(),
        )
        active_effect_rows.append(
            _active_effect_row(
                eval_date,
                effect_open["selection"],
                effect_open["labels"],
            )
        )
        active_seal_count += 1
        selection_recomputed_count += 1
        feature_usage = {
            str(name): float(value)
            for name, value in fit["primary_feature_usage"].items()
        }
        feature_usage_by_model[eval_date] = feature_usage
        model_manifest[eval_date] = {
            "primary_model_sha256": fit["primary_model_sha256"],
            "repeat_model_sha256": fit["repeat_model_sha256"],
            "model_bytes_equal": bool(
                fit["primary_model_sha256"] == fit["repeat_model_sha256"]
            ),
            "primary_model_size": int(len(fit["primary_model_bytes"])),
            "repeat_model_size": int(len(fit["repeat_model_bytes"])),
        }
        prediction_rows.extend(prediction["ordered_rows"])
        selection_rows.append(
            {
                "eval_date": eval_date,
                "arm_a_product_vt_symbol": selection["arm_a"]["product_vt_symbol"],
                "arm_a_a_rank": selection["arm_a"]["a_rank"],
                "arm_b_product_vt_symbol": selection["arm_b"]["product_vt_symbol"],
                "arm_b_a_rank": selection["arm_b"]["a_rank"],
                "arm_c_product_vt_symbol": selection["arm_c"]["product_vt_symbol"],
                "arm_c_a_rank": selection["arm_c"]["a_rank"],
                "arm_c_replaced": bool(selection["arm_c"] != selection["arm_a"]),
            }
        )
        fold_audit_rows.append(
            {
                "eval_date": eval_date,
                "train_rows": int(len(prepared["ordered_training"])),
                "train_qids": int(len(set(prepared["qid"]))),
                "test_rows": int(len(prepared["ordered_test"])),
                "train_label_end_max": str(fold["train_label_end_max"]),
                "feature_order_exact": bool(
                    prepared["fold_input"]["feature_order"] == MODEL_FEATURES
                ),
                "factory_is_exact_xgboost_ranker": bool(
                    fit["factory_is_exact_xgboost_ranker"]
                ),
                "prediction_repeat_max_abs_difference": float(
                    fit["prediction_repeat_max_abs_difference"]
                ),
                "primary_model_sha256": seal["primary_model_sha256"],
                "repeat_model_sha256": seal["repeat_model_sha256"],
                "test_unique_scores": int(len(np.unique(fit["predictions"]))),
                "physical_feature_split_count": int(
                    len(set(feature_usage) & set(PHYSICAL_FEATURES))
                ),
            }
        )

    fold_audit = pd.DataFrame(fold_audit_rows).sort_values(
        "eval_date", kind="mergesort"
    ).reset_index(drop=True)
    ordered_predictions = pd.DataFrame(prediction_rows).sort_values(
        ["eval_date", "a_rank", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)
    monthly_selections = pd.DataFrame(selection_rows).sort_values(
        "eval_date", kind="mergesort"
    ).reset_index(drop=True)
    effect_sequence = _assemble_effect_sequence(
        active_effect_rows, fallback_effect_rows, contract
    )
    label_access_audit = label_store.final_audit()
    physical_split_audit = _physical_split_audit(
        feature_usage_by_model, active_dates
    )
    expected_files = {
        relative
        for eval_date in active_dates
        for relative in [
            f"models/{eval_date}_primary.ubj",
            f"models/{eval_date}_repeat.ubj",
            f"fold_inputs/{eval_date}.json",
            f"predictions/{eval_date}.json",
            f"selections/{eval_date}.json",
            f"pre_effect_seals/{eval_date}.json",
        ]
    }
    expected_files.update(
        f"pre_effect_seals/{eval_date}.json" for eval_date in fallback_dates
    )
    actual_files = {
        path.relative_to(staging_dir).as_posix()
        for path in staging_dir.rglob("*")
        if path.is_file()
    }
    observed_files = {
        str(event.get("relative_path"))
        for event in event_ledger.events()
        if event["event_type"] == "artifact_created"
        and event.get("phase") == "pre_effect"
    }
    prepublication_artifact_audit = {
        "passed": bool(
            actual_files == expected_files and observed_files == expected_files
        ),
        "expected_file_count": int(len(expected_files)),
        "actual_file_count": int(len(actual_files)),
        "missing_files": sorted(expected_files - actual_files),
        "unexpected_files": sorted(actual_files - expected_files),
        "unobserved_files": sorted(expected_files - observed_files),
        "unexpected_observed_files": sorted(observed_files - expected_files),
    }
    return {
        "fold_audit": fold_audit,
        "ordered_oos_predictions": ordered_predictions,
        "monthly_selections": monthly_selections,
        "effect_sequence": effect_sequence,
        "feature_usage_by_model": feature_usage_by_model,
        "physical_split_audit": physical_split_audit,
        "model_manifest": {
            "model_class": model_contract.get("class"),
            "model_params": dict(model_contract.get("params", {})),
            "primary_model_count": int(active_seal_count),
            "repeat_model_count": int(active_seal_count),
            "models": model_manifest,
        },
        "estimator_audit": {
            "class_exact": bool(
                factory_exact and model_contract.get("class") == "xgboost.XGBRanker"
            ),
            "params_exact": bool(dict(model_contract.get("params", {})) == MODEL_PARAMS),
        },
        "label_access_audit": label_access_audit,
        "fit_call_count": int(fit_call_count),
        "active_seal_count": int(active_seal_count),
        "fallback_seal_count": int(fallback_seal_count),
        "selection_recomputed_before_effect_open_count": int(
            selection_recomputed_count
        ),
        "prepublication_artifact_audit": prepublication_artifact_audit,
    }


def _physical_split_audit(
    feature_usage_by_model: Mapping[str, Mapping[str, Any]],
    active_dates: list[str],
) -> dict[str, Any]:
    if set(feature_usage_by_model) != set(active_dates) or len(
        feature_usage_by_model
    ) != len(active_dates):
        raise Stage003Error("physical_split_model_keys_invalid")
    per_model: dict[str, list[str]] = {}
    union: set[str] = set()
    for eval_date in active_dates:
        usage = feature_usage_by_model[eval_date]
        if not isinstance(usage, Mapping) or any(
            feature not in MODEL_FEATURES
            or isinstance(count, bool)
            or not isinstance(count, (int, float))
            or not math.isfinite(float(count))
            or float(count) <= 0.0
            for feature, count in usage.items()
        ):
            raise Stage003Error(f"physical_split_usage_invalid:{eval_date}")
        physical = sorted(set(usage) & set(PHYSICAL_FEATURES))
        per_model[eval_date] = physical
        union.update(physical)
    models_with_physical = sum(bool(features) for features in per_model.values())
    return {
        "passed": bool(
            models_with_physical == len(active_dates) and len(union) >= 3
        ),
        "model_count": int(len(active_dates)),
        "models_with_physical_split": int(models_with_physical),
        "distinct_physical_features_used": int(len(union)),
        "physical_features_used": sorted(union),
        "per_model_physical_features": per_model,
    }


def _evaluate_effects(effect_rows: pd.DataFrame) -> dict[str, Any]:
    required = {
        "eval_date",
        "arm_c_replaced",
        "arm_c_product_vt_symbol",
        "return_delta",
        "drawdown_improvement",
    }
    if not required.issubset(effect_rows.columns):
        raise Stage003Error("effect_columns_missing")
    frame = effect_rows.copy()
    frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="coerce").dt.normalize()
    frame["return_delta"] = pd.to_numeric(frame["return_delta"], errors="coerce")
    frame["drawdown_improvement"] = pd.to_numeric(
        frame["drawdown_improvement"], errors="coerce"
    )
    if frame[["eval_date", "return_delta", "drawdown_improvement"]].isna().any().any():
        raise Stage003Error("effect_values_invalid")
    frame["arm_c_replaced"] = frame["arm_c_replaced"].map(
        lambda value: value if type(value) is bool else None
    )
    if frame["arm_c_replaced"].isna().any():
        raise Stage003Error("effect_replaced_type_invalid")
    replacements = frame[frame["arm_c_replaced"]].copy()
    total_return = float(frame["return_delta"].sum())
    total_drawdown = float(frame["drawdown_improvement"].sum())
    leave_best_return = float(total_return - frame["return_delta"].max()) if len(frame) else 0.0
    leave_best_drawdown = (
        float(total_drawdown - frame["drawdown_improvement"].max()) if len(frame) else 0.0
    )
    yearly_return = {
        str(year): float(
            frame.loc[frame["eval_date"].dt.year.eq(year), "return_delta"].sum()
        )
        for year in [2023, 2024]
    }
    yearly_drawdown = {
        str(year): float(
            frame.loc[
                frame["eval_date"].dt.year.eq(year), "drawdown_improvement"
            ].sum()
        )
        for year in [2023, 2024]
    }
    if replacements.empty:
        joint_rate = None
        median_return = None
        median_drawdown = None
    else:
        joint_rate = float(
            (
                replacements["return_delta"].gt(0)
                & replacements["drawdown_improvement"].gt(0)
            ).mean()
        )
        median_return = float(replacements["return_delta"].median())
        median_drawdown = float(replacements["drawdown_improvement"].median())
    replacement_years = set(replacements["eval_date"].dt.year.astype(int))
    replacement_products = int(replacements["arm_c_product_vt_symbol"].nunique())
    gates = {
        "replacement_count_and_year_coverage": bool(
            len(replacements) >= 5 and {2023, 2024}.issubset(replacement_years)
        ),
        "replacement_product_diversity": bool(replacement_products >= 3),
        "total_return_delta_positive": bool(total_return > 0.0),
        "total_drawdown_improvement_positive": bool(total_drawdown > 0.0),
        "leave_best_out_return_delta_positive": bool(leave_best_return > 0.0),
        "leave_best_out_drawdown_improvement_positive": bool(leave_best_drawdown > 0.0),
        "each_year_return_delta_nonnegative": bool(
            all(value >= 0.0 for value in yearly_return.values())
        ),
        "each_year_drawdown_improvement_nonnegative": bool(
            all(value >= 0.0 for value in yearly_drawdown.values())
        ),
        "joint_positive_replacement_rate": bool(
            joint_rate is not None and joint_rate >= 0.60
        ),
        "median_replacement_return_delta_nonnegative": bool(
            median_return is not None and median_return >= 0.0
        ),
        "median_replacement_drawdown_improvement_nonnegative": bool(
            median_drawdown is not None and median_drawdown >= 0.0
        ),
    }
    if list(gates) != EFFECT_GATE_KEYS or not all(type(value) is bool for value in gates.values()):
        raise Stage003Error("effect_gate_schema_invalid")
    metrics = {
        "replacement_count": int(len(replacements)),
        "replacement_product_count": replacement_products,
        "total_return_delta": total_return,
        "total_drawdown_improvement": total_drawdown,
        "leave_best_out_return_delta": leave_best_return,
        "leave_best_out_drawdown_improvement": leave_best_drawdown,
        "yearly_return_delta": yearly_return,
        "yearly_drawdown_improvement": yearly_drawdown,
        "joint_positive_replacement_rate": joint_rate,
        "median_replacement_return_delta": median_return,
        "median_replacement_drawdown_improvement": median_drawdown,
    }
    for value in metrics.values():
        if isinstance(value, float) and not math.isfinite(value):
            raise Stage003Error("effect_metric_nonfinite")
    return {
        "metrics": metrics,
        "gates": gates,
        "effect_gate_pass": bool(all(value is True for value in gates.values())),
    }


def _build_execution_scope_audit(
    training: Mapping[str, Any],
    *,
    event_ledger: ExecutionEventLedger,
    static_scope_audit: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(event_ledger, ExecutionEventLedger):
        raise Stage003Error("execution_scope_event_ledger_invalid")
    static_counts = static_scope_audit.get("counts")
    if (
        not isinstance(static_counts, Mapping)
        or set(static_counts) != set(STATIC_SCOPE_COUNT_KEYS)
        or any(type(static_counts.get(name)) is not int for name in STATIC_SCOPE_COUNT_KEYS)
        or any(int(static_counts[name]) < 0 for name in STATIC_SCOPE_COUNT_KEYS)
    ):
        raise Stage003Error("execution_scope_static_audit_invalid")
    artifact_audit = training.get("prepublication_artifact_audit")
    artifact_list_keys = [
        "missing_files",
        "unexpected_files",
        "unobserved_files",
        "unexpected_observed_files",
    ]
    if (
        not isinstance(artifact_audit, Mapping)
        or any(not isinstance(artifact_audit.get(name, []), list) for name in artifact_list_keys)
    ):
        raise Stage003Error("execution_scope_artifact_audit_invalid")

    events = event_ledger.events()
    fit_started = [event for event in events if event["event_type"] == "fit_started"]
    fit_completed = [
        event for event in events if event["event_type"] == "fit_completed"
    ]
    primary_fits = [
        event for event in fit_completed if event.get("fit_role") == "primary"
    ]
    repeat_fits = [
        event for event in fit_completed if event.get("fit_role") == "repeat"
    ]
    invalid_fit_roles = [
        event
        for event in [*fit_started, *fit_completed]
        if event.get("fit_role") not in {"primary", "repeat"}
    ]
    started_identities = sorted(
        (
            str(event.get("eval_date")),
            str(event.get("fit_role")),
            str(event.get("params_sha256")),
        )
        for event in fit_started
    )
    completed_identities = sorted(
        (
            str(event.get("eval_date")),
            str(event.get("fit_role")),
            str(event.get("params_sha256")),
        )
        for event in fit_completed
    )

    search_events = [
        event for event in events if event["event_type"] == "search_operation"
    ]
    runtime_search_counts = {
        name: sum(event.get("search_type") == search_type for event in search_events)
        for name, search_type in [
            ("parameter_searches", "parameter"),
            ("feature_searches", "feature"),
            ("seed_searches", "seed"),
        ]
    }
    unknown_search_events = sum(
        event.get("search_type") not in {"parameter", "feature", "seed"}
        for event in search_events
    )
    runtime_event_types = {
        "early_stopping_runs": "early_stopping_run",
        "true_engine_runs": "true_engine_run",
        "production_writes": "production_write",
        "ctp_connections": "ctp_connection",
        "order_api_calls": "order_api_call",
        "unexpected_commands": "unexpected_command",
    }
    runtime_scope_counts = {
        **runtime_search_counts,
        **{
            name: sum(event["event_type"] == event_type for event in events)
            for name, event_type in runtime_event_types.items()
        },
    }

    selection_events = [
        event for event in events if event["event_type"] == "selection_created"
    ]
    selection_recomputed_events = [
        event for event in events if event["event_type"] == "selection_recomputed"
    ]
    selection_counts_by_date: dict[str, int] = {}
    for event in selection_events:
        eval_date = str(event.get("eval_date"))
        selection_counts_by_date[eval_date] = selection_counts_by_date.get(eval_date, 0) + 1
    duplicate_selection_runs = sum(
        max(count - 1, 0) for count in selection_counts_by_date.values()
    )
    rerun_selection_runs = max(
        duplicate_selection_runs,
        len(selection_events) - int(EXECUTION_SCOPE_COUNTS["primary_fit_calls"]),
        0,
    )

    holdout_prediction_rows = sum(
        int(event.get("prediction_rows", 0))
        for event in events
        if event["event_type"] == "prediction_completed"
        and event.get("split") == "sealed_account_label_holdout"
    )
    holdout_label_reads = sum(
        event["event_type"] == "label_file_read"
        and event.get("split") == "sealed_account_label_holdout"
        for event in events
    )
    unexpected_artifacts = set(artifact_audit.get("unexpected_files", [])) | set(
        artifact_audit.get("unexpected_observed_files", [])
    )

    counts = {
        "authorized_training_entrypoint_invocations": sum(
            event["event_type"] == "training_entrypoint_started" for event in events
        ),
        "primary_fit_calls": len(primary_fits),
        "repeat_fit_calls": len(repeat_fits),
        "total_fit_calls": len(fit_completed),
        "parameter_searches": int(static_counts["parameter_searches"])
        + int(runtime_scope_counts["parameter_searches"]),
        "feature_searches": int(static_counts["feature_searches"])
        + int(runtime_scope_counts["feature_searches"]),
        "seed_searches": int(static_counts["seed_searches"])
        + int(runtime_scope_counts["seed_searches"]),
        "early_stopping_runs": int(static_counts["early_stopping_runs"])
        + int(runtime_scope_counts["early_stopping_runs"]),
        "extra_fit_calls": max(
            len(fit_completed) - int(EXECUTION_SCOPE_COUNTS["total_fit_calls"]), 0
        ),
        "rerun_selection_runs": int(rerun_selection_runs),
        "holdout_predictions": int(holdout_prediction_rows),
        "holdout_label_reads_or_generations": int(holdout_label_reads),
        "true_engine_runs": int(static_counts["true_engine_runs"])
        + int(runtime_scope_counts["true_engine_runs"]),
        "production_writes": int(static_counts["production_writes"])
        + int(runtime_scope_counts["production_writes"]),
        "ctp_connections": int(static_counts["ctp_connections"])
        + int(runtime_scope_counts["ctp_connections"]),
        "order_api_calls": int(static_counts["order_api_calls"])
        + int(runtime_scope_counts["order_api_calls"]),
        "unexpected_commands": int(static_counts["unexpected_commands"])
        + int(runtime_scope_counts["unexpected_commands"]),
        "unexpected_artifacts": int(len(unexpected_artifacts)),
    }
    expected_active = int(EXECUTION_SCOPE_COUNTS["primary_fit_calls"])
    development_predictions = [
        event
        for event in events
        if event["event_type"] == "prediction_completed"
        and event.get("split") == "development"
    ]
    fit_lifecycle_exact = bool(
        not invalid_fit_roles
        and started_identities == completed_identities
        and len(fit_started) == int(EXECUTION_SCOPE_COUNTS["total_fit_calls"])
    )
    event_evidence_exact = bool(
        len(selection_events) == expected_active
        and len(selection_counts_by_date) == expected_active
        and len(selection_recomputed_events) == expected_active
        and {
            str(event.get("eval_date")) for event in selection_recomputed_events
        }
        == set(selection_counts_by_date)
        and len(development_predictions)
        == int(EXECUTION_SCOPE_COUNTS["total_fit_calls"])
        and fit_lifecycle_exact
    )
    training_summary_consistent = bool(
        int(training.get("fit_call_count", -1)) == len(fit_completed)
        and int(training.get("active_seal_count", -1)) == len(primary_fits)
        and int(training.get("active_seal_count", -1))
        == sum(event["event_type"] == "active_seal_verified" for event in events)
        and int(training.get("fallback_seal_count", -1))
        == sum(event["event_type"] == "fallback_seal_verified" for event in events)
        and int(training.get("selection_recomputed_before_effect_open_count", -1))
        == len(selection_recomputed_events)
    )
    artifact_evidence_exact = bool(
        artifact_audit.get("passed") is True
        and all(not artifact_audit.get(name, []) for name in artifact_list_keys)
        and int(artifact_audit.get("actual_file_count", -1))
        == int(artifact_audit.get("expected_file_count", -2))
    )
    passed = bool(
        counts == EXECUTION_SCOPE_COUNTS
        and static_scope_audit.get("passed") is True
        and artifact_evidence_exact
        and unknown_search_events == 0
        and event_evidence_exact
        and training_summary_consistent
    )
    return {
        "passed": passed,
        "counts": counts,
        "expected": dict(EXECUTION_SCOPE_COUNTS),
        "event_evidence": {
            "event_count": int(len(events)),
            "event_ledger_sha256": _sha256_bytes(
                _canonical_json_bytes(events, newline=False)
            ),
            "fit_lifecycle_exact": fit_lifecycle_exact,
            "selection_and_prediction_events_exact": event_evidence_exact,
            "training_summary_consistent": training_summary_consistent,
            "artifact_evidence_exact": artifact_evidence_exact,
            "unknown_search_event_count": int(unknown_search_events),
        },
        "runtime_scope_counts": runtime_scope_counts,
        "static_scope_audit": dict(static_scope_audit),
        "prepublication_artifact_audit": dict(artifact_audit),
    }


def _build_technical_qualification(
    *,
    contract: Mapping[str, Any],
    contract_audit: Mapping[str, Any],
    governance_audit: Mapping[str, Any],
    metadata_audit: Mapping[str, Any],
    training: Mapping[str, Any],
    checkpoint_stability: Mapping[str, Any],
    execution_scope: Mapping[str, Any],
) -> dict[str, Any]:
    folds = contract["folds"]
    fold_audit = training["fold_audit"]
    label_audit = training["label_access_audit"]
    expected_label_audit = {
        "aggregate_development_label_data_rows_parsed": 0,
        "aggregate_reconciliation_data_rows_parsed": 0,
        "initial_mature_label_rows_opened": int(
            contract["label_access"]["initial_job_label_rows"]
        ),
        "oos_test_label_rows_opened_before_own_pre_effect_seal": 0,
        "oos_test_label_rows_opened_after_own_pre_effect_seal": int(
            contract["label_access"]["test_job_label_rows"]
        ),
        "unique_job_label_rows_opened": int(
            contract["label_access"]["unique_job_label_rows"]
        ),
        "other_development_main_label_rows_read": int(
            contract["label_access"]["other_development_main_label_rows_read"]
        ),
        "a2_label_rows_read": 0,
        "sealed_holdout_label_rows_read": int(
            contract["label_access"]["holdout_label_rows_read"]
        ),
        "same_fold_test_label_rows_used_for_training": 0,
        "test_label_rows_used_for_preprocessing_or_selection": 0,
    }
    dates_exact = bool(
        fold_audit["eval_date"].astype(str).tolist()
        == list(folds["active_test_dates"])
    )
    fold_shapes_exact = bool(
        dates_exact
        and fold_audit["train_rows"].astype(int).tolist()
        == list(folds["training_rows"])
        and fold_audit["train_qids"].astype(int).tolist()
        == list(folds["training_qids"])
        and fold_audit["test_rows"].astype(int).tolist()
        == list(folds["test_rows"])
    )
    metadata_exact = bool(
        int(metadata_audit.get("development_rows", -1)) == 153
        and int(metadata_audit.get("development_active_months", -1)) == 26
        and int(metadata_audit.get("holdout_feature_rows", -1)) == 65
        and int(metadata_audit.get("holdout_active_months", -1)) == 9
        and int(metadata_audit.get("initial_training_rows", -1)) == 62
        and int(metadata_audit.get("initial_training_qids", -1)) == 13
        and int(metadata_audit.get("active_fold_count", -1)) == 13
        and int(metadata_audit.get("fallback_month_count", -1)) == 4
        and int(metadata_audit.get("a2_jobs_used", -1)) == 0
        and int(metadata_audit.get("pit_violation_rows", -1)) == 0
        and fold_shapes_exact
    )
    repeat_max = float(
        pd.to_numeric(
            fold_audit["prediction_repeat_max_abs_difference"], errors="raise"
        ).max()
    )
    model_bytes_exact = bool(
        fold_audit["primary_model_sha256"].eq(
            fold_audit["repeat_model_sha256"]
        ).all()
    )
    estimator = training["estimator_audit"]
    physical = training["physical_split_audit"]
    gates = {
        "machine_contract_exact": bool(
            contract_audit.get("model_feature_order_exact") is True
            and contract_audit.get("model_params_exact") is True
            and governance_audit.get("passed") is True
        ),
        "authorization_and_inputs_three_point_exact": bool(
            checkpoint_stability.get("passed") is True
            and checkpoint_stability.get("authorization_and_inputs_exact") is True
        ),
        "runtime_identity_three_point_exact": bool(
            checkpoint_stability.get("passed") is True
            and checkpoint_stability.get("runtime_identity_exact") is True
        ),
        "metadata_and_fold_plan_exact": metadata_exact,
        "feature_order_and_values_exact": bool(
            int(metadata_audit.get("probability_nonfinite_rows", -1)) == 0
            and int(metadata_audit.get("probability_out_of_range_rows", -1)) == 0
            and float(metadata_audit.get("probability_delta_max_abs_error", math.inf))
            <= PROBABILITY_DELTA_ABSOLUTE_TOLERANCE
            and fold_audit["feature_order_exact"].map(lambda value: value is True).all()
        ),
        "estimator_class_and_params_exact": bool(
            estimator.get("class_exact") is True
            and estimator.get("params_exact") is True
        ),
        "fit_count_exact": bool(
            int(training.get("fit_call_count", -1))
            == int(contract["model"]["fit_count"])
            and int(execution_scope.get("counts", {}).get("total_fit_calls", -1))
            == int(contract["model"]["fit_count"])
        ),
        "repeat_predictions_exact": bool(repeat_max <= 1e-12),
        "repeat_model_bytes_exact": model_bytes_exact,
        "test_predictions_nondegenerate": bool(
            fold_audit["test_unique_scores"].astype(int).ge(2).all()
        ),
        "physical_feature_splits_exact": bool(physical.get("passed") is True),
        "active_and_fallback_seals_exact": bool(
            int(training.get("active_seal_count", -1))
            == int(folds["active_fold_count"])
            and int(training.get("fallback_seal_count", -1))
            == int(folds["fallback_month_count"])
        ),
        "selection_recomputed_before_effect_open": bool(
            int(training.get("selection_recomputed_before_effect_open_count", -1))
            == int(folds["active_fold_count"])
        ),
        "label_access_state_machine_exact": bool(label_audit == expected_label_audit),
        "holdout_and_execution_scope_zero": bool(
            execution_scope.get("passed") is True
            and int(metadata_audit.get("holdout_prediction_rows", -1)) == 0
            and int(label_audit.get("sealed_holdout_label_rows_read", -1)) == 0
        ),
    }
    if list(gates) != TECHNICAL_GATE_KEYS or not all(
        type(value) is bool for value in gates.values()
    ):
        raise Stage003Error("technical_gate_schema_invalid")
    return {
        "passed": bool(all(value is True for value in gates.values())),
        "gates": gates,
        "gate_pass_count": int(sum(gates.values())),
        "gate_count": int(len(gates)),
        "prediction_repeat_max_abs_difference": repeat_max,
        "expected_label_access_audit": expected_label_audit,
    }


def _pre_effect_technical_ready(
    technical: Mapping[str, Any],
    first: Mapping[str, Any],
    second: Mapping[str, Any],
) -> bool:
    gates = technical.get("gates")
    if (
        not isinstance(gates, Mapping)
        or list(gates) != TECHNICAL_GATE_KEYS
        or any(type(value) is not bool for value in gates.values())
        or first.get("checkpoint") != "before_training"
        or second.get("checkpoint") != "after_all_models"
    ):
        raise Stage003Error("pre_effect_technical_input_invalid")
    deferred = {
        "authorization_and_inputs_three_point_exact",
        "runtime_identity_three_point_exact",
    }
    other_gates_pass = all(
        value is True for name, value in gates.items() if name not in deferred
    )
    authorization_two_point_exact = bool(
        first.get("authorization_and_inputs_identity_sha256")
        == second.get("authorization_and_inputs_identity_sha256")
    )
    runtime_two_point_exact = bool(
        first.get("runtime_identity_sha256") == second.get("runtime_identity_sha256")
    )
    return bool(
        other_gates_pass
        and authorization_two_point_exact
        and runtime_two_point_exact
    )


def _stage003_decision(
    contract: Mapping[str, Any], *, technical_pass: bool, effect_pass: bool
) -> str:
    if not technical_pass:
        return str(contract["decisions"]["technical_fail"])
    if effect_pass:
        return str(contract["decisions"]["effect_pass"])
    return str(contract["decisions"]["effect_fail"])


def _stage003_report(
    *,
    decision: str,
    technical: Mapping[str, Any],
    effect: Mapping[str, Any] | None,
    execution_scope: Mapping[str, Any],
    label_access_audit: Mapping[str, Any],
) -> str:
    effect_pass = None if effect is None else bool(effect.get("effect_gate_pass"))
    counts = execution_scope.get("counts")
    if not isinstance(counts, Mapping):
        raise Stage003Error("stage003_report_scope_invalid")
    return "\n".join(
        [
            "# Stage003 冻结 development OOS 实验",
            "",
            f"- 决策：`{decision}`",
            f"- 技术门：`{technical.get('gate_pass_count')}/{technical.get('gate_count')}`",
            f"- 效果门通过：`{effect_pass}`",
            "- Holdout预测/标签读取："
            f"`{int(counts.get('holdout_predictions', -1))}/"
            f"{int(label_access_audit.get('sealed_holdout_label_rows_read', -1))}`",
            "- 真实引擎/生产写入/CTP/订单："
            f"`{int(counts.get('true_engine_runs', -1))}/"
            f"{int(counts.get('production_writes', -1))}/"
            f"{int(counts.get('ctp_connections', -1))}/"
            f"{int(counts.get('order_api_calls', -1))}`",
            "- 本结果只评价冻结development账户边际代理，不代表正式策略收益。",
            "",
        ]
    )


def _expected_result_relative_files(
    contract: Mapping[str, Any], *, technical_pass: bool
) -> set[str]:
    folds = contract.get("folds")
    if not isinstance(folds, Mapping) or type(technical_pass) is not bool:
        raise Stage003Error("final_artifact_contract_invalid")
    active_dates = folds.get("active_test_dates")
    fallback_dates = folds.get("fallback_test_dates")
    if (
        not isinstance(active_dates, list)
        or not isinstance(fallback_dates, list)
        or len(active_dates) != int(folds.get("active_fold_count", -1))
        or len(fallback_dates) != int(folds.get("fallback_month_count", -1))
    ):
        raise Stage003Error("final_artifact_contract_invalid")
    files = {
        relative
        for eval_date in active_dates
        for relative in [
            f"models/{eval_date}_primary.ubj",
            f"models/{eval_date}_repeat.ubj",
            f"fold_inputs/{eval_date}.json",
            f"predictions/{eval_date}.json",
            f"selections/{eval_date}.json",
            f"pre_effect_seals/{eval_date}.json",
        ]
    }
    files.update(f"pre_effect_seals/{eval_date}.json" for eval_date in fallback_dates)
    files.update(
        {
            "authorization_consumption.json",
            "checkpoint_stability_audit.json",
            "decision.json",
            "event_ledger.json",
            "execution_scope_audit.json",
            "feature_usage_audit.json",
            "final_artifact_contract.json",
            "fold_audit.csv",
            "governance_audit.json",
            "input_identity_audit.json",
            "label_access_audit.json",
            "machine_contract.json",
            "metadata_audit.json",
            "model_manifest.json",
            "report.md",
            "run_receipt.json",
            "runtime_identity_audit.json",
            "stage003_summary.json",
            "static_scope_audit.json",
            "technical_qualification.json",
        }
    )
    if technical_pass:
        files.update(
            {
                "effect_qualification.json",
                "effect_sequence.csv",
                "monthly_arm_selections.csv",
                "ordered_oos_predictions.csv",
            }
        )
    return files


def _validate_expected_result_files(expected_relative_files: set[str]) -> set[str]:
    if not isinstance(expected_relative_files, set) or not expected_relative_files:
        raise Stage003Error("final_artifact_contract_invalid")
    normalized: set[str] = set()
    for relative in expected_relative_files:
        if not isinstance(relative, str):
            raise Stage003Error("final_artifact_contract_invalid")
        path = Path(relative)
        if (
            not relative
            or relative == "artifact_manifest.json"
            or path.is_absolute()
            or path.as_posix() != relative
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise Stage003Error("final_artifact_contract_invalid")
        normalized.add(relative)
    if normalized != expected_relative_files:
        raise Stage003Error("final_artifact_contract_invalid")
    return normalized


def _result_file_identities(root: Path) -> dict[str, dict[str, Any]]:
    identities: dict[str, dict[str, Any]] = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_symlink():
            raise Stage003Error("result_artifact_symlink_invalid")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative == "artifact_manifest.json":
            continue
        identities[relative] = {
            "size": int(path.stat().st_size),
            "sha256": _sha256_file(path),
        }
    return identities


def _publish_result_bundle(
    staging_dir: Path,
    result_dir: Path,
    *,
    csv_frames: Mapping[str, pd.DataFrame],
    json_payloads: Mapping[str, Any],
    text_payloads: Mapping[str, str],
    expected_relative_files: set[str],
) -> dict[str, Any]:
    staging_dir = Path(staging_dir)
    result_dir = Path(result_dir)
    if result_dir.exists():
        raise Stage003Error(f"result_already_exists:{result_dir}")
    if not staging_dir.is_dir() or staging_dir.is_symlink():
        raise Stage003Error(f"staging_result_invalid:{staging_dir}")
    expected_files = _validate_expected_result_files(expected_relative_files)
    for collection in [csv_frames, json_payloads, text_payloads]:
        for name in collection:
            if Path(name).name != name or name == "artifact_manifest.json":
                raise Stage003Error(f"result_artifact_name_invalid:{name}")
            if (staging_dir / name).exists():
                raise Stage003Error(f"result_artifact_already_exists:{name}")
    for name, frame in csv_frames.items():
        if not isinstance(frame, pd.DataFrame):
            raise Stage003Error(f"result_csv_invalid:{name}")
        frame.to_csv(staging_dir / name, index=False, lineterminator="\n")
    for name, payload in json_payloads.items():
        (staging_dir / name).write_bytes(_canonical_json_bytes(payload))
    for name, payload in text_payloads.items():
        if not isinstance(payload, str):
            raise Stage003Error(f"result_text_invalid:{name}")
        (staging_dir / name).write_text(payload, encoding="utf-8")

    if (staging_dir / "artifact_manifest.json").exists():
        raise Stage003Error("result_manifest_preexists")
    artifacts = _result_file_identities(staging_dir)
    if set(artifacts) != expected_files:
        raise Stage003Error(
            "final_artifact_set_mismatch:"
            f"missing={sorted(expected_files - set(artifacts))}:"
            f"unexpected={sorted(set(artifacts) - expected_files)}"
        )
    for relative in sorted(artifacts):
        _fsync_file(staging_dir / relative)
    manifest = {
        "stage": "Stage003",
        "manifest_semantics": "all_result_files_except_manifest",
        "artifacts": artifacts,
    }
    manifest_path = staging_dir / "artifact_manifest.json"
    manifest_path.write_bytes(_canonical_json_bytes(manifest))
    _fsync_file(manifest_path)
    directories = sorted(
        [staging_dir, *(path for path in staging_dir.rglob("*") if path.is_dir())],
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for directory in directories:
        _fsync_directory(directory)
    result_dir.parent.mkdir(parents=True, exist_ok=True)
    os.rename(staging_dir, result_dir)
    _fsync_directory(result_dir.parent)
    persisted = _load_json(result_dir / "artifact_manifest.json")
    if persisted != manifest:
        raise Stage003Error("result_manifest_reverification_failed")
    published_artifacts = _result_file_identities(result_dir)
    if set(published_artifacts) != expected_files or published_artifacts != artifacts:
        raise Stage003Error("result_artifact_reverification_failed")
    return manifest


def run_stage003() -> dict[str, Any]:
    """Run the single authorization-bound Stage003 development OOS experiment."""
    validated = _validate_authorization_from_paths(AUTHORIZATION_PATH, CONTRACT_PATH)
    event_ledger = ExecutionEventLedger()
    first = _capture_execution_checkpoint(
        "before_training",
        validated,
        receipt_required=False,
        staging_required=False,
        event_ledger=event_ledger,
    )
    contract = validated["contract"]
    started_at = datetime.now().astimezone()
    receipt = _persist_validated_authorization(validated)
    staging_dir = validated["temp_result_dir"]
    result_dir = validated["result_dir"]
    os.mkdir(staging_dir, 0o700)
    _fsync_directory(staging_dir.parent)
    event_ledger.record(
        "training_entrypoint_started",
        entrypoint="run_stage003",
        authorization_sha256=str(receipt["authorization_sha256"]),
        bound_files_identity_sha256=str(receipt["bound_files_identity_sha256"]),
    )

    feature_frame = pd.read_csv(STAGE002_FEATURE_PANEL_PATH)
    split_projection = pd.read_csv(
        FULL_FEATURE_SPLIT_PATH,
        usecols=FULL_SPLIT_ALLOWED_COLUMNS,
    )
    jobs_projection = pd.read_csv(
        DEVELOPMENT_JOBS_PATH,
        usecols=JOB_ALLOWED_COLUMNS,
    )
    state = _build_frozen_metadata_state(
        feature_frame,
        split_projection,
        jobs_projection,
        contract,
    )
    stage005_manifest = _load_json(STAGE005_MANIFEST_PATH)
    manifest_files = (
        stage005_manifest.get("files")
        if isinstance(stage005_manifest, dict)
        else None
    )
    if (
        not isinstance(stage005_manifest, dict)
        or set(stage005_manifest) != {
            "campaign_id",
            "file_count_excluding_manifest",
            "files",
        }
        or type(stage005_manifest.get("file_count_excluding_manifest")) is not int
        or not isinstance(manifest_files, dict)
        or stage005_manifest["file_count_excluding_manifest"] != len(manifest_files)
    ):
        raise Stage003Error("stage005_manifest_shape_invalid")
    initial_dates = sorted(
        state["initial_training_panel"]["eval_date"].astype(str).unique().tolist()
    )
    active_dates = list(contract["folds"]["active_test_dates"])
    development_job_ids = set(state["development_panel"]["job_id"].astype(str))
    other_development_main_job_ids = set(
        state["main_jobs"]["job_id"].astype(str)
    ) - development_job_ids
    label_store = PhaseGatedJobLabelStore(
        metadata=state["development_panel"],
        label_root=LABEL_ROOT,
        manifest_files=manifest_files,
        initial_dates=initial_dates,
        test_dates=active_dates,
        event_ledger=event_ledger,
        other_development_main_job_ids=other_development_main_job_ids,
        a2_job_ids=set(state["a2_jobs"]["job_id"].astype(str)),
    )
    training = _run_frozen_training(
        state=state,
        label_store=label_store,
        contract=contract,
        staging_dir=staging_dir,
        ranker_factory=xgboost.XGBRanker,
        event_ledger=event_ledger,
    )
    second = _capture_execution_checkpoint(
        "after_all_models",
        validated,
        receipt_required=True,
        staging_required=True,
        event_ledger=event_ledger,
    )
    training["label_access_audit"] = label_store.final_audit()
    execution_scope = _build_execution_scope_audit(
        training,
        event_ledger=event_ledger,
        static_scope_audit=first["static_scope_audit"],
    )
    pre_effect_stability = _build_checkpoint_stability_audit([first, second])
    technical = _build_technical_qualification(
        contract=contract,
        contract_audit=first["machine_contract_audit"],
        governance_audit=first["governance_audit"],
        metadata_audit=state["audit"],
        training=training,
        checkpoint_stability=pre_effect_stability,
        execution_scope=execution_scope,
    )

    checkpoints = [first, second]
    effect: dict[str, Any] | None = None
    if _pre_effect_technical_ready(technical, first, second):
        effect = _evaluate_effects(training["effect_sequence"])
        event_ledger.record(
            "effect_evaluation",
            evaluated_months=int(len(training["effect_sequence"])),
            effect_gate_pass=bool(effect["effect_gate_pass"]),
        )
        third = _capture_execution_checkpoint(
            "after_effect_evaluation",
            validated,
            receipt_required=True,
            staging_required=True,
            event_ledger=event_ledger,
        )
        checkpoints.append(third)
    checkpoint_stability = _build_checkpoint_stability_audit(checkpoints)
    training["label_access_audit"] = label_store.final_audit()
    execution_scope = _build_execution_scope_audit(
        training,
        event_ledger=event_ledger,
        static_scope_audit=first["static_scope_audit"],
    )
    technical = _build_technical_qualification(
        contract=contract,
        contract_audit=first["machine_contract_audit"],
        governance_audit=first["governance_audit"],
        metadata_audit=state["audit"],
        training=training,
        checkpoint_stability=checkpoint_stability,
        execution_scope=execution_scope,
    )
    if technical["passed"] is not True:
        effect = None
    decision = _stage003_decision(
        contract,
        technical_pass=technical["passed"] is True,
        effect_pass=bool(effect and effect["effect_gate_pass"] is True),
    )
    completed_at = datetime.now().astimezone()
    decision_payload = {
        "line_id": "futures_trend_xgboost_pit_physical_positioning_context",
        "stage": "Stage003",
        "decision": decision,
        "technical_pass": bool(technical["passed"]),
        "effect_pass": None
        if effect is None
        else bool(effect["effect_gate_pass"]),
        "holdout_prediction_rows": int(
            execution_scope["counts"]["holdout_predictions"]
        ),
        "holdout_label_rows_read": int(
            training["label_access_audit"]["sealed_holdout_label_rows_read"]
        ),
        "true_engine_runs": int(execution_scope["counts"]["true_engine_runs"]),
        "production_writes": int(execution_scope["counts"]["production_writes"]),
        "ctp_connections": int(execution_scope["counts"]["ctp_connections"]),
        "order_api_calls": int(execution_scope["counts"]["order_api_calls"]),
    }
    run_receipt = {
        "line_id": decision_payload["line_id"],
        "stage": "Stage003",
        "started_at": started_at.isoformat(timespec="seconds"),
        "completed_at": completed_at.isoformat(timespec="seconds"),
        "duration_seconds": float((completed_at - started_at).total_seconds()),
        "authorization_consumption": receipt,
        "checkpoint_count": int(len(checkpoints)),
        "decision": decision,
    }
    summary = {
        "decision": decision,
        "technical_gate_pass": bool(technical["passed"]),
        "technical_gate_pass_count": int(technical["gate_pass_count"]),
        "technical_gate_count": int(technical["gate_count"]),
        "effect_gate_pass": None
        if effect is None
        else bool(effect["effect_gate_pass"]),
        "effect_gate_pass_count": None
        if effect is None
        else int(sum(effect["gates"].values())),
        "effect_gate_count": None if effect is None else len(EFFECT_GATE_KEYS),
        "development_feature_rows": int(state["audit"]["development_rows"]),
        "sealed_holdout_feature_rows": int(state["audit"]["holdout_feature_rows"]),
        "active_fold_count": int(training["active_seal_count"]),
        "fallback_month_count": int(training["fallback_seal_count"]),
        "fit_call_count": int(training["fit_call_count"]),
        "opened_unique_job_label_rows": int(
            training["label_access_audit"]["unique_job_label_rows_opened"]
        ),
        "aggregate_label_data_rows_parsed": int(
            training["label_access_audit"][
                "aggregate_development_label_data_rows_parsed"
            ]
            + training["label_access_audit"][
                "aggregate_reconciliation_data_rows_parsed"
            ]
        ),
        "holdout_predictions": int(
            execution_scope["counts"]["holdout_predictions"]
        ),
        "holdout_label_rows_read": int(
            training["label_access_audit"]["sealed_holdout_label_rows_read"]
        ),
        "true_engine_runs": int(execution_scope["counts"]["true_engine_runs"]),
        "production_writes": int(execution_scope["counts"]["production_writes"]),
        "ctp_connections": int(execution_scope["counts"]["ctp_connections"]),
        "order_api_calls": int(execution_scope["counts"]["order_api_calls"]),
    }
    json_payloads: dict[str, Any] = {
        "authorization_consumption.json": receipt,
        "checkpoint_stability_audit.json": checkpoint_stability,
        "decision.json": decision_payload,
        "event_ledger.json": event_ledger.events(),
        "execution_scope_audit.json": execution_scope,
        "feature_usage_audit.json": {
            "feature_usage_by_model": training["feature_usage_by_model"],
            "physical_split_audit": training["physical_split_audit"],
        },
        "governance_audit.json": first["governance_audit"],
        "input_identity_audit.json": {
            "checkpoints": [
                {
                    "checkpoint": item["checkpoint"],
                    "input_identity_audit": item["input_identity_audit"],
                }
                for item in checkpoints
            ]
        },
        "label_access_audit.json": training["label_access_audit"],
        "machine_contract.json": contract,
        "metadata_audit.json": state["audit"],
        "model_manifest.json": training["model_manifest"],
        "run_receipt.json": run_receipt,
        "runtime_identity_audit.json": {
            "passed": bool(checkpoint_stability["runtime_identity_exact"]),
            "checkpoints": [
                {
                    "checkpoint": item["checkpoint"],
                    "runtime_identity_sha256": item["runtime_identity_sha256"],
                    "runtime_identity": item["runtime_identity"],
                }
                for item in checkpoints
            ],
        },
        "stage003_summary.json": summary,
        "static_scope_audit.json": first["static_scope_audit"],
        "technical_qualification.json": technical,
    }
    csv_frames: dict[str, pd.DataFrame] = {
        "fold_audit.csv": training["fold_audit"],
    }
    if technical["passed"] is True:
        if effect is None:
            raise Stage003Error("effect_missing_after_technical_pass")
        json_payloads["effect_qualification.json"] = effect
        csv_frames.update(
            {
                "effect_sequence.csv": training["effect_sequence"],
                "monthly_arm_selections.csv": training["monthly_selections"],
                "ordered_oos_predictions.csv": training[
                    "ordered_oos_predictions"
                ],
            }
        )
    expected_relative_files = _expected_result_relative_files(
        contract, technical_pass=bool(technical["passed"])
    )
    json_payloads["final_artifact_contract.json"] = {
        "artifact_manifest_semantics": "all_result_files_except_manifest",
        "expected_file_count_excluding_manifest": int(len(expected_relative_files)),
        "expected_relative_files": sorted(expected_relative_files),
    }
    manifest = _publish_result_bundle(
        staging_dir,
        result_dir,
        csv_frames=csv_frames,
        json_payloads=json_payloads,
        text_payloads={
            "report.md": _stage003_report(
                decision=decision,
                technical=technical,
                effect=effect,
                execution_scope=execution_scope,
                label_access_audit=training["label_access_audit"],
            )
        },
        expected_relative_files=expected_relative_files,
    )
    return {
        "decision": decision,
        "technical_pass": bool(technical["passed"]),
        "effect_pass": None
        if effect is None
        else bool(effect["effect_gate_pass"]),
        "result_dir": str(result_dir.resolve()),
        "published_artifact_count": int(len(manifest["artifacts"]) + 1),
    }


def main() -> None:
    print(json.dumps(run_stage003(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
