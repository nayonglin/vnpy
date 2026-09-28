"""Run the frozen Stage006 dual-ranker development OOS experiment."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, NamedTuple

import numpy as np
import pandas as pd
import sklearn
import xgboost
from xgboost import XGBRanker


LINE_ID = "futures_trend_xgboost_pit_curve_account_labels"
LINE = Path(__file__).resolve().parents[1]
OUT = LINE / "artifacts/stage006_dual_ranker_development_oos"
CONTRACT_PATH = OUT / "training_contract.json"
RUNTIME_IDENTITY_PATH = OUT / "runtime_identity.json"
PREREGISTRATION_PATH = (
    LINE
    / "stages/20260903_0101_stage006_dual_ranker_development_oos_preregistration.md"
)
REMEDIATION_PATH = (
    LINE / "stages/20260903_0113_stage006_prerun_block_remediation_preregistration.md"
)
PRERUN_REVIEW_PATH = LINE / "reviews/20260903_stage006_prerun_rereview.md"
PRERUN_REVIEW_DECISION_PATH = (
    LINE / "reviews/20260903_stage006_prerun_rereview_decision.json"
)
FINAL_IMPLEMENTATION_REVIEW_PATH = (
    LINE / "reviews/20260903_stage006_final_implementation_rereview.md"
)
TEST_PATH = LINE / "tests/test_stage006_dual_ranker_development_oos.py"
RUN_AUTHORIZATION_PATH = OUT / "run_authorization.json"
AUTHORIZATION_CONSUMPTION_PATH = OUT / "authorization_consumption.json"
RESULT_DIR = OUT / "frozen_run"

EXPECTED_CONTRACT_SHA256 = (
    "543bd677790fd4d28ed429ae743af39a57f94dece26dfa9fae898b318e6b06ac"
)
EXPECTED_PREREGISTRATION_SHA256 = (
    "53c9a6e0caad907d21c4fc4e94052836978dd8f81b74ede4e825d94a2b265525"
)
EXPECTED_RUNTIME_IDENTITY_SHA256 = (
    "f0a469f5a8387ba8171be5b3e2c8c6b0d9fc0e8de7f5b0914e08ef4f327fddbc"
)
EXPECTED_REMEDIATION_SHA256 = (
    "72a1ca52459586b0d46fb03ecad78c02119c505e6152f380a85f71d29959a6b0"
)
EXPECTED_PRERUN_REVIEW_SHA256 = (
    "e021a7a8add52db9722097f21699326d545430a20ee371269d05d6feeb2754d8"
)
EXPECTED_PRERUN_REVIEW_DECISION_SHA256 = (
    "6d2a32ad5ab423821030f280500283923633715f0b4e6f45c5b3aca93c68f5a7"
)

STAGE002_OUT = LINE / "artifacts/stage002_curve_features"
FEATURE_PANEL_PATH = STAGE002_OUT / "candidate_curve_feature_panel.csv"
STAGE002_SUMMARY_PATH = STAGE002_OUT / "stage002_summary.json"
STAGE002_MANIFEST_PATH = STAGE002_OUT / "artifact_manifest.json"
STAGE003_OUT = LINE / "artifacts/stage003_account_label_plan"
FULL_SPLIT_PATH = STAGE003_OUT / "full_feature_split.csv"
DEVELOPMENT_JOBS_PATH = STAGE003_OUT / "development_jobs.csv"
STAGE003_SUMMARY_PATH = STAGE003_OUT / "stage003_summary.json"
STAGE005_CAMPAIGN = (
    LINE
    / "artifacts/stage005_development_label_batch/campaigns/"
    "campaign_20260902T214308+0800_13888"
)
STAGE005_DECISION_PATH = STAGE005_CAMPAIGN / "decision.json"
DEVELOPMENT_LABELS_PATH = STAGE005_CAMPAIGN / "development_labels.csv"
RECONCILIATION_PATH = STAGE005_CAMPAIGN / "reconciliation.csv"
STAGE005_MANIFEST_PATH = STAGE005_CAMPAIGN / "artifact_manifest.json"
LABEL_ROOT = STAGE005_CAMPAIGN / "job_outputs"
STAGE005_POSTRUN_REVIEW_PATH = (
    LINE / "reviews/20260903_stage005_postrun_independent_review.md"
)
STAGE005_POSTRUN_DECISION_PATH = (
    LINE / "reviews/20260903_stage005_postrun_review_decision.json"
)

MODEL_FEATURE_COLUMNS = [
    "formal_probability_delta_vs_rank10",
    "formal_rank_distance",
    "front_next_basis_annualized_delta_vs_rank10",
    "full_curve_backwardation_slope_delta_vs_rank10",
    "full_curve_fit_rmse_delta_vs_rank10",
    "open_interest_hhi_delta_vs_rank10",
    "volume_hhi_delta_vs_rank10",
    "oi_weighted_maturity_days_delta_vs_rank10",
]
LABEL_VALUE_COLUMNS = [
    "base_equity",
    "end_equity",
    "future_return",
    "future_max_drawdown",
    "future_net_pnl",
    "future_slippage",
    "future_trade_count",
    "future_trading_days",
]
DEVELOPMENT_LABEL_HEADER = [
    "job_id",
    "job_type",
    "eval_date",
    "next_eval_date",
    "product_vt_symbol",
    "candidate_rank",
    *LABEL_VALUE_COLUMNS,
]
RECONCILIATION_HEADER = [
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

AUTHORIZATION_BOUND_FILE_NAMES = (
    "runner",
    "tests",
    "preregistration",
    "training_contract",
    "runtime_identity",
    "final_independent_prerun_review",
)
RUN_AUTHORIZATION_SCOPE = (
    "one_frozen_stage006_development_run_only_no_holdout_no_production_no_ctp_no_orders"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def verify_file_identities(
    paths: Mapping[str, Path], expected_sha256: Mapping[str, str]
) -> dict[str, dict[str, Any]]:
    if set(paths) != set(expected_sha256):
        raise RuntimeError("frozen_input_identity_key_mismatch")
    identities: dict[str, dict[str, Any]] = {}
    for name, raw_path in paths.items():
        path = Path(raw_path)
        before = path.stat()
        digest = _sha256(path)
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
            raise RuntimeError(f"frozen_input_changed_while_hashing:{name}")
        if digest != expected_sha256[name]:
            raise RuntimeError(f"frozen_input_sha_mismatch:{name}")
        identities[name] = {
            "path": str(path.resolve()),
            "size": int(after.st_size),
            "sha256": digest,
            "device": int(after.st_dev),
            "inode": int(after.st_ino),
            "mtime_ns": int(after.st_mtime_ns),
            "ctime_ns": int(after.st_ctime_ns),
        }
    return identities


def verify_csv_identity_and_header_only(
    path: Path,
    *,
    expected_sha256: str,
    expected_header: list[str],
) -> dict[str, Any]:
    path = Path(path)
    digest = _sha256(path)
    if digest != expected_sha256:
        raise RuntimeError(f"frozen_input_sha_mismatch:{path.name}")
    with path.open("rb") as stream:
        header_bytes = stream.readline()
    header_text = header_bytes.decode("utf-8-sig").rstrip("\r\n")
    header = next(csv.reader([header_text]))
    if header != expected_header:
        raise RuntimeError(f"aggregate_csv_header_mismatch:{path.name}")
    return {
        "path": str(path.resolve()),
        "size": int(path.stat().st_size),
        "sha256": digest,
        "header": header,
        "data_rows_parsed": 0,
    }


def current_runtime_identity() -> dict[str, Any]:
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
                "sha256": _sha256(path),
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


def load_frozen_runtime_identity() -> dict[str, Any]:
    if _sha256(RUNTIME_IDENTITY_PATH) != EXPECTED_RUNTIME_IDENTITY_SHA256:
        raise RuntimeError("stage006_runtime_identity_sha_drift")
    payload = json.loads(RUNTIME_IDENTITY_PATH.read_text(encoding="utf-8"))
    if current_runtime_identity() != payload:
        raise RuntimeError("stage006_runtime_identity_mismatch")
    return payload


def load_frozen_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    paths = {
        "contract": CONTRACT_PATH,
        "preregistration": PREREGISTRATION_PATH,
        "runtime_identity": RUNTIME_IDENTITY_PATH,
        "remediation": REMEDIATION_PATH,
        "prerun_review": PRERUN_REVIEW_PATH,
        "prerun_review_decision": PRERUN_REVIEW_DECISION_PATH,
    }
    expected = {
        "contract": EXPECTED_CONTRACT_SHA256,
        "preregistration": EXPECTED_PREREGISTRATION_SHA256,
        "runtime_identity": EXPECTED_RUNTIME_IDENTITY_SHA256,
        "remediation": EXPECTED_REMEDIATION_SHA256,
        "prerun_review": EXPECTED_PRERUN_REVIEW_SHA256,
        "prerun_review_decision": EXPECTED_PRERUN_REVIEW_DECISION_SHA256,
    }
    identities = verify_file_identities(paths, expected)
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    decision = json.loads(PRERUN_REVIEW_DECISION_PATH.read_text(encoding="utf-8"))
    if contract.get("contract_version") != 2:
        raise RuntimeError("stage006_contract_version_invalid")
    if contract.get("status") != "prerun_block_remediated_pending_independent_rereview":
        raise RuntimeError("stage006_contract_status_invalid")
    if contract.get("line_id") != LINE_ID or contract.get("stage") != "Stage006":
        raise RuntimeError("stage006_contract_identity_invalid")
    if contract.get("features") != MODEL_FEATURE_COLUMNS:
        raise RuntimeError("stage006_feature_order_drift")
    if decision.get("decision") != "ALLOW_STAGE006_IMPLEMENTATION_ONLY":
        raise RuntimeError("stage006_implementation_not_authorized")
    severity = decision.get("severity", {})
    if any(int(severity.get(level, -1)) != 0 for level in ("P0", "P1", "P2")):
        raise RuntimeError("stage006_prerun_blocking_findings")
    runtime = load_frozen_runtime_identity()
    return contract, {
        "contract_sha256": identities["contract"]["sha256"],
        "preregistration_sha256": identities["preregistration"]["sha256"],
        "runtime_identity_sha256": identities["runtime_identity"]["sha256"],
        "remediation_sha256": identities["remediation"]["sha256"],
        "prerun_review_sha256": identities["prerun_review"]["sha256"],
        "prerun_review_decision_sha256": identities[
            "prerun_review_decision"
        ]["sha256"],
        "runtime_identity": runtime,
    }


def _normalize_date_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        result[column] = (
            pd.to_datetime(result[column], errors="raise")
            .dt.normalize()
            .dt.date.astype(str)
        )
    return result


def _monthly_group_contract(frame: pd.DataFrame) -> bool:
    for _, month in frame.groupby("eval_date", sort=True):
        ranks = sorted(month["candidate_rank"].astype(int).tolist())
        if (
            ranks.count(10) != 1
            or ranks != list(range(10, max(ranks) + 1))
            or max(ranks) > 18
            or month["product_vt_symbol"].astype(str).duplicated().any()
            or month.duplicated(
                ["eval_date", "candidate_rank", "product_vt_symbol"]
            ).any()
        ):
            return False
    return True


def build_development_metadata_panel(
    feature_frame: pd.DataFrame,
    split_frame: pd.DataFrame,
    jobs_frame: pd.DataFrame,
    contract: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    feature_required = {
        "eval_date",
        "product_vt_symbol",
        "a_rank",
        *MODEL_FEATURE_COLUMNS,
    }
    split_required = {
        "eval_date",
        "next_eval_date",
        "product_vt_symbol",
        "a_rank",
        "split",
        "label_values_read_allowed",
        "account_label_qid",
    }
    jobs_required = {
        "eval_date",
        "next_eval_date",
        "product_vt_symbol",
        "candidate_rank",
        "split",
        "job_type",
        "job_id",
    }
    for name, frame, required in (
        ("feature", feature_frame, feature_required),
        ("split", split_frame, split_required),
        ("jobs", jobs_frame, jobs_required),
    ):
        if missing := sorted(required - set(frame.columns)):
            raise RuntimeError(f"metadata_{name}_columns_missing:{missing}")

    features = _normalize_date_columns(feature_frame, ["eval_date"])
    splits = _normalize_date_columns(split_frame, ["eval_date", "next_eval_date"])
    jobs = _normalize_date_columns(jobs_frame, ["eval_date", "next_eval_date"])
    features["candidate_rank"] = pd.to_numeric(
        features.pop("a_rank"), errors="raise"
    ).astype(int)
    splits["candidate_rank"] = pd.to_numeric(
        splits.pop("a_rank"), errors="raise"
    ).astype(int)
    jobs["candidate_rank"] = pd.to_numeric(
        jobs["candidate_rank"], errors="raise"
    ).astype(int)

    key = ["eval_date", "product_vt_symbol", "candidate_rank"]
    if features.duplicated(key).any() or splits.duplicated(key).any():
        raise RuntimeError("monthly_key_or_rank_contract")
    metadata = features.merge(
        splits[
            [
                *key,
                "next_eval_date",
                "split",
                "label_values_read_allowed",
                "account_label_qid",
            ]
        ],
        on=key,
        how="inner",
        validate="one_to_one",
    )
    if len(metadata) != len(features) or len(metadata) != len(splits):
        raise RuntimeError("feature_split_key_mismatch")

    holdout = metadata[
        metadata["split"].astype(str).eq("sealed_account_label_holdout")
    ].copy()
    development = metadata[metadata["split"].astype(str).eq("development")].copy()
    allowed = development["label_values_read_allowed"].map(
        lambda value: value is True or str(value).strip().lower() == "true"
    )
    if not allowed.all():
        raise RuntimeError("development_label_access_metadata_invalid")
    if not holdout.empty:
        denied = holdout["label_values_read_allowed"].map(
            lambda value: value is False or str(value).strip().lower() == "false"
        )
        if not denied.all():
            raise RuntimeError("holdout_label_access_metadata_invalid")

    main_jobs = jobs[
        jobs["job_type"].astype(str).eq("main")
        & jobs["split"].astype(str).eq("development")
    ].copy()
    if main_jobs["job_id"].astype(str).duplicated().any() or main_jobs.duplicated(key).any():
        raise RuntimeError("development_job_key_duplicate")
    development = development.merge(
        main_jobs[[*key, "next_eval_date", "job_id"]],
        on=[*key, "next_eval_date"],
        how="inner",
        validate="one_to_one",
    )
    expected_rows = int(contract["inputs"]["development_labels"]["rows"])
    expected_months = int(contract["inputs"]["development_labels"]["months"])
    expected_holdout_rows = int(contract["pit_split"]["sealed_holdout_feature_rows"])
    expected_holdout_months = int(contract["pit_split"]["sealed_holdout_months"])
    if (
        len(development) != expected_rows
        or len(main_jobs) != expected_rows
        or development["eval_date"].nunique() != expected_months
        or len(holdout) != expected_holdout_rows
        or holdout["eval_date"].nunique() != expected_holdout_months
    ):
        raise RuntimeError("development_metadata_shape")

    values = development[MODEL_FEATURE_COLUMNS].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(values.to_numpy(dtype="float64")).all():
        raise RuntimeError("feature_values_nonfinite")
    development[MODEL_FEATURE_COLUMNS] = values.astype("float64")
    anchors = development[development["candidate_rank"].eq(10)]
    if len(anchors) != expected_months or not np.equal(
        anchors[MODEL_FEATURE_COLUMNS].to_numpy(dtype="float64"), 0.0
    ).all():
        raise RuntimeError("rank10_feature_anchor_not_exact_zero")
    if not _monthly_group_contract(development):
        raise RuntimeError("monthly_key_or_rank_contract")

    development.sort_values(
        ["eval_date", "candidate_rank", "product_vt_symbol"],
        kind="mergesort",
        inplace=True,
    )
    development.reset_index(drop=True, inplace=True)
    return development, {
        "development_rows": int(len(development)),
        "development_months": int(development["eval_date"].nunique()),
        "holdout_feature_rows": int(len(holdout)),
        "holdout_months": int(holdout["eval_date"].nunique()),
        "holdout_prediction_rows": 0,
        "rank10_anchor_rows": int(len(anchors)),
        "all_features_finite": True,
        "monthly_group_contract": True,
    }


class PitFold(NamedTuple):
    train_dates: pd.DatetimeIndex
    test_date: pd.Timestamp
    train_indices: pd.Index
    test_indices: pd.Index
    train_label_end_max: pd.Timestamp


def build_pit_folds(
    frame: pd.DataFrame, *, minimum_train_months: int
) -> list[PitFold]:
    required = {"eval_date", "next_eval_date", "candidate_rank", "job_id"}
    if missing := sorted(required - set(frame.columns)):
        raise RuntimeError(f"pit_columns_missing:{missing}")
    panel = frame.copy()
    panel["eval_date"] = pd.to_datetime(panel["eval_date"], errors="raise").dt.normalize()
    panel["next_eval_date"] = pd.to_datetime(
        panel["next_eval_date"], errors="raise"
    ).dt.normalize()
    if panel.duplicated(["eval_date", "candidate_rank"]).any():
        raise RuntimeError("pit_month_rank_duplicate")
    next_counts = panel.groupby("eval_date")["next_eval_date"].nunique(dropna=False)
    if not next_counts.eq(1).all():
        raise RuntimeError("month_next_eval_date_not_unique")
    month_label_end = panel.groupby("eval_date")["next_eval_date"].first()
    if (month_label_end.index >= pd.DatetimeIndex(month_label_end.to_numpy())).any():
        raise RuntimeError("pit_label_end_not_after_eval_date")

    dates = pd.DatetimeIndex(sorted(panel["eval_date"].unique()))
    folds: list[PitFold] = []
    for test_date in dates:
        eligible = pd.DatetimeIndex(
            [
                date
                for date in dates[dates < test_date]
                if month_label_end.loc[date] <= test_date
            ]
        )
        if len(eligible) < minimum_train_months:
            continue
        train_mask = panel["eval_date"].isin(eligible)
        test_mask = panel["eval_date"].eq(test_date)
        folds.append(
            PitFold(
                train_dates=eligible,
                test_date=pd.Timestamp(test_date),
                train_indices=panel.index[train_mask],
                test_indices=panel.index[test_mask],
                train_label_end_max=pd.Timestamp(month_label_end.loc[eligible].max()),
            )
        )
    return folds


def add_monthly_relevance(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"eval_date", "return_delta", "drawdown_improvement"}
    if missing := sorted(required - set(frame.columns)):
        raise RuntimeError(f"relevance_columns_missing:{missing}")
    result = _normalize_date_columns(frame, ["eval_date"])
    for source, target in (
        ("return_delta", "return_relevance"),
        ("drawdown_improvement", "drawdown_relevance"),
    ):
        values = pd.to_numeric(result[source], errors="raise").astype("float64")
        if not np.isfinite(values).all():
            raise RuntimeError(f"relevance_value_nonfinite:{source}")
        result[source] = values
        result[target] = (
            result.groupby("eval_date")[source]
            .rank(method="dense", ascending=True)
            .astype("int64")
            - 1
        )
        if (result[target] < 0).any():
            raise RuntimeError(f"relevance_negative:{target}")
    return result


def ranker_training_arrays(
    frame: pd.DataFrame,
    feature_columns: list[str],
    relevance_column: str,
) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray]:
    required = {
        "eval_date",
        "candidate_rank",
        "product_vt_symbol",
        relevance_column,
        *feature_columns,
    }
    if missing := sorted(required - set(frame.columns)):
        raise RuntimeError(f"ranker_columns_missing:{missing}")
    ordered = frame.sort_values(
        ["eval_date", "candidate_rank", "product_vt_symbol"],
        kind="mergesort",
    ).reset_index(drop=True)
    x = ordered[feature_columns].apply(pd.to_numeric, errors="raise").astype("float64")
    if not np.isfinite(x.to_numpy()).all():
        raise RuntimeError("ranker_feature_nonfinite")
    y = pd.to_numeric(ordered[relevance_column], errors="raise").to_numpy(
        dtype="int64"
    )
    if (y < 0).any():
        raise RuntimeError("ranker_relevance_negative")
    qid = pd.factorize(ordered["eval_date"], sort=True)[0].astype("int64")
    if len(qid) and (qid[0] != 0 or np.any(np.diff(qid) < 0)):
        raise RuntimeError("ranker_qid_not_sorted_contiguous")
    return ordered, x, y, qid


def score_and_select_month(month: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    required = {
        "eval_date",
        "product_vt_symbol",
        "candidate_rank",
        "raw_return_score",
        "raw_drawdown_score",
    }
    if missing := sorted(required - set(month.columns)):
        raise RuntimeError(f"selection_columns_missing:{missing}")
    if month.empty or month["eval_date"].nunique() != 1:
        raise RuntimeError("selection_requires_one_nonempty_month")
    scored = month.copy()
    scored["candidate_rank"] = pd.to_numeric(
        scored["candidate_rank"], errors="raise"
    ).astype(int)
    if scored["candidate_rank"].duplicated().any():
        raise RuntimeError("selection_candidate_rank_duplicate")
    baseline = scored[scored["candidate_rank"].eq(10)]
    if len(baseline) != 1:
        raise RuntimeError("selection_rank10_baseline_shape")
    for column in ("raw_return_score", "raw_drawdown_score"):
        scored[column] = pd.to_numeric(scored[column], errors="raise").astype(float)
    if not np.isfinite(
        scored[["raw_return_score", "raw_drawdown_score"]].to_numpy()
    ).all():
        raise RuntimeError("selection_score_nonfinite")
    scored["return_percentile"] = scored["raw_return_score"].rank(
        method="average", ascending=True, pct=True
    )
    scored["drawdown_percentile"] = scored["raw_drawdown_score"].rank(
        method="average", ascending=True, pct=True
    )
    scored["dual_ranker_score"] = (
        scored["return_percentile"] + scored["drawdown_percentile"]
    ) / 2.0
    ordered = scored.sort_values(
        [
            "dual_ranker_score",
            "raw_return_score",
            "raw_drawdown_score",
            "candidate_rank",
            "product_vt_symbol",
        ],
        ascending=[False, False, False, True, True],
        kind="mergesort",
    )
    arm_a = baseline.iloc[0]
    arm_b = ordered.iloc[0]
    gate = bool(
        int(arm_b["candidate_rank"]) != 10
        and float(arm_b["raw_return_score"]) > float(arm_a["raw_return_score"])
        and float(arm_b["raw_drawdown_score"])
        > float(arm_a["raw_drawdown_score"])
    )
    arm_c = arm_b if gate else arm_a
    selection = {
        "eval_date": str(arm_a["eval_date"]),
        "arm_a_product_vt_symbol": str(arm_a["product_vt_symbol"]),
        "arm_a_candidate_rank": int(arm_a["candidate_rank"]),
        "arm_b_product_vt_symbol": str(arm_b["product_vt_symbol"]),
        "arm_b_candidate_rank": int(arm_b["candidate_rank"]),
        "arm_b_raw_return_score": float(arm_b["raw_return_score"]),
        "arm_b_raw_drawdown_score": float(arm_b["raw_drawdown_score"]),
        "arm_b_dual_ranker_score": float(arm_b["dual_ranker_score"]),
        "rank10_raw_return_score": float(arm_a["raw_return_score"]),
        "rank10_raw_drawdown_score": float(arm_a["raw_drawdown_score"]),
        "arm_c_product_vt_symbol": str(arm_c["product_vt_symbol"]),
        "arm_c_candidate_rank": int(arm_c["candidate_rank"]),
        "arm_c_replaced": bool(gate),
    }
    return scored, selection


def evaluate_effect_qualification(
    monthly_selections: pd.DataFrame, contract: dict[str, Any]
) -> dict[str, Any]:
    required = {
        "eval_date",
        "arm_c_candidate_rank",
        "arm_c_replaced",
        "arm_c_realized_return_delta",
        "arm_c_realized_drawdown_improvement",
    }
    if missing := sorted(required - set(monthly_selections.columns)):
        raise RuntimeError(f"qualification_columns_missing:{missing}")
    frame = monthly_selections.copy()
    frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="raise").dt.normalize()
    if frame["eval_date"].duplicated().any():
        raise RuntimeError("qualification_eval_date_duplicate")
    expected_months = int(contract["effect_gates"]["sequence_months"])
    if len(frame) != expected_months:
        raise RuntimeError(f"qualification_month_count:{len(frame)}:{expected_months}")
    frame["arm_c_candidate_rank"] = pd.to_numeric(
        frame["arm_c_candidate_rank"], errors="raise"
    ).astype(int)
    frame["arm_c_replaced"] = frame["arm_c_replaced"].astype(bool)
    if not frame["arm_c_replaced"].eq(
        frame["arm_c_candidate_rank"].ne(10)
    ).all():
        raise RuntimeError("qualification_replacement_flag_mismatch")
    returns = pd.to_numeric(
        frame["arm_c_realized_return_delta"], errors="raise"
    ).astype(float)
    drawdowns = pd.to_numeric(
        frame["arm_c_realized_drawdown_improvement"], errors="raise"
    ).astype(float)
    if not np.isfinite(returns).all() or not np.isfinite(drawdowns).all():
        raise RuntimeError("qualification_nonfinite_effect")
    inactive = ~frame["arm_c_replaced"]
    if (returns[inactive] != 0.0).any() or (drawdowns[inactive] != 0.0).any():
        raise RuntimeError("nonreplacement_effect_not_zero")

    active = frame["arm_c_replaced"]
    replacement_months = int(active.sum())
    replacement_years = sorted(
        frame.loc[active, "eval_date"].dt.year.unique().astype(int).tolist()
    )
    total_return = float(returns.sum())
    total_drawdown = float(drawdowns.sum())
    leave_best_return = float(total_return - returns.max())
    leave_best_drawdown = float(total_drawdown - drawdowns.max())
    years = frame["eval_date"].dt.year
    yearly_return = {
        int(year): float(returns[years.eq(year)].sum())
        for year in sorted(years.unique())
    }
    yearly_drawdown = {
        int(year): float(drawdowns[years.eq(year)].sum())
        for year in sorted(years.unique())
    }
    joint_rate = float(
        (returns[active].gt(0.0) & drawdowns[active].gt(0.0)).mean()
    ) if replacement_months else 0.0

    thresholds = contract["effect_gates"]
    required_years = [int(year) for year in thresholds["replacement_years"]["required"]]
    gates = {
        "minimum_replacement_months": replacement_months
        >= int(thresholds["replacement_months"]["threshold"]),
        "required_replacement_years": set(required_years).issubset(replacement_years),
        "total_return_delta_positive": total_return
        > float(thresholds["sum_return_delta"]["threshold"]),
        "total_drawdown_improvement_positive": total_drawdown
        > float(thresholds["sum_drawdown_improvement"]["threshold"]),
        "leave_best_out_return_delta_positive": leave_best_return
        > float(thresholds["return_leave_best_month_out"]["threshold"]),
        "leave_best_out_drawdown_improvement_positive": leave_best_drawdown
        > float(thresholds["drawdown_leave_best_month_out"]["threshold"]),
        "each_year_return_delta_nonnegative": all(
            yearly_return.get(year, float("-inf"))
            >= float(thresholds["each_required_year_return_delta"]["threshold"])
            for year in required_years
        ),
        "each_year_drawdown_improvement_nonnegative": all(
            yearly_drawdown.get(year, float("-inf"))
            >= float(
                thresholds["each_required_year_drawdown_improvement"]["threshold"]
            )
            for year in required_years
        ),
        "active_joint_positive_rate": joint_rate
        >= float(thresholds["replacement_joint_positive_rate"]["threshold"]),
    }
    if len(gates) != int(thresholds["boolean_gate_count"]):
        raise RuntimeError("effect_gate_count_drift")
    return {
        "passed": bool(all(gates.values())),
        "gates": {name: bool(value) for name, value in gates.items()},
        "oos_months": int(len(frame)),
        "replacement_months": replacement_months,
        "replacement_years": replacement_years,
        "total_return_delta": total_return,
        "total_drawdown_improvement": total_drawdown,
        "leave_best_out_return_delta": leave_best_return,
        "leave_best_out_drawdown_improvement": leave_best_drawdown,
        "yearly_return_delta": yearly_return,
        "yearly_drawdown_improvement": yearly_drawdown,
        "active_joint_positive_rate": joint_rate,
    }


def stage006_decision(*, technical_pass: bool, effect_pass: bool) -> str:
    if not technical_pass:
        return "stage006_contract_or_pit_invalid_stop_no_effect_claim"
    if not effect_pass:
        return "stage006_dual_ranker_development_oos_fail_stop_no_true_engine_no_holdout"
    return "stage006_dual_ranker_development_oos_pass_allow_true_engine_ac_preregistration"


def resolve_stage006_outcome(
    *,
    technical: dict[str, Any],
    monthly_selections: pd.DataFrame,
    contract: dict[str, Any],
    effect_evaluator: Callable[[pd.DataFrame, dict[str, Any]], dict[str, Any]] | None = None,
) -> tuple[dict[str, Any] | None, str]:
    if not bool(technical.get("passed")):
        return None, stage006_decision(technical_pass=False, effect_pass=False)
    evaluator = effect_evaluator or evaluate_effect_qualification
    effect = evaluator(monthly_selections, contract)
    return effect, stage006_decision(
        technical_pass=True, effect_pass=bool(effect["passed"])
    )


def fit_repeated_ranker(
    train_features: pd.DataFrame,
    train_target: np.ndarray | pd.Series,
    train_qid: np.ndarray | pd.Series,
    predict_features: pd.DataFrame,
    *,
    params: dict[str, Any],
    tolerance: float,
    ranker_factory: Callable[..., Any] = XGBRanker,
) -> dict[str, Any]:
    if list(train_features.columns) != list(predict_features.columns):
        raise RuntimeError("ranker_feature_order_mismatch")
    if not len(train_features) or len(train_features) != len(train_target):
        raise RuntimeError("ranker_train_shape")
    target = np.asarray(train_target, dtype="int64")
    qid = np.asarray(train_qid, dtype="int64")
    if len(qid) != len(train_features) or (target < 0).any():
        raise RuntimeError("ranker_target_or_qid_shape")
    if len(qid) and (qid[0] != 0 or np.any(np.diff(qid) < 0)):
        raise RuntimeError("ranker_qid_not_sorted_contiguous")
    predictions: list[np.ndarray] = []
    raw_models: list[bytes] = []
    for _ in range(2):
        model = ranker_factory(**params)
        model.fit(train_features, target, qid=qid, verbose=False)
        prediction = np.asarray(model.predict(predict_features), dtype="float64")
        if not np.isfinite(prediction).all():
            raise RuntimeError("ranker_prediction_nonfinite")
        predictions.append(prediction)
        raw_models.append(bytes(model.get_booster().save_raw(raw_format="ubj")))
    max_difference = float(
        np.max(np.abs(predictions[0] - predictions[1]), initial=0.0)
    )
    hashes = [_sha256_bytes(payload) for payload in raw_models]
    if max_difference > tolerance:
        raise RuntimeError(f"ranker_prediction_nondeterministic:{max_difference}")
    if hashes[0] != hashes[1]:
        raise RuntimeError("ranker_model_bytes_nondeterministic")
    if len(np.unique(predictions[0])) < 2:
        raise RuntimeError("ranker_test_prediction_constant")
    return {
        "predictions": predictions[0],
        "prediction_repeat_max_abs_difference": max_difference,
        "model_raw": raw_models[0],
        "repeat_model_raw": raw_models[1],
        "model_sha256": hashes[0],
        "repeat_model_sha256": hashes[1],
    }


def build_estimator_audit(
    ranker_factory: Callable[..., Any], params: Mapping[str, Any]
) -> dict[str, Any]:
    frozen_contract = load_frozen_contract()[0]
    expected_params = frozen_contract["xgboost"]["params"]
    actual_params = dict(params)
    exact_factory = ranker_factory is XGBRanker
    params_exact = actual_params == expected_params
    return {
        "passed": bool(exact_factory and params_exact),
        "factory_is_exact_xgboost_ranker": bool(exact_factory),
        "factory_module": getattr(ranker_factory, "__module__", None),
        "factory_qualname": getattr(ranker_factory, "__qualname__", None),
        "expected_factory_module": XGBRanker.__module__,
        "expected_factory_qualname": XGBRanker.__qualname__,
        "params_exact": bool(params_exact),
        "actual_params": actual_params,
        "expected_params": expected_params,
    }


def _canonical_json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _fsync_file(path: Path) -> None:
    with Path(path).open("rb") as stream:
        os.fsync(stream.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_pre_effect_seal(
    seal_dir: Path,
    *,
    test_eval_date: str,
    model_payloads: Mapping[str, bytes],
    repeat_model_payloads: Mapping[str, bytes],
    predictions: pd.DataFrame,
    selection: Mapping[str, Any],
    test_label_rows_read_before_seal: int,
) -> Path:
    if test_label_rows_read_before_seal != 0:
        raise RuntimeError("test_labels_read_before_pre_effect_seal")
    if set(model_payloads) != {"return", "drawdown"} or set(
        repeat_model_payloads
    ) != {"return", "drawdown"}:
        raise RuntimeError("pre_effect_model_payload_shape")
    seal_dir = Path(seal_dir)
    seal_dir.mkdir(parents=True, exist_ok=True)
    name = f"{pd.Timestamp(test_eval_date).date().isoformat()}.json"
    target = seal_dir / name
    if target.exists():
        raise RuntimeError(f"pre_effect_seal_already_exists:{target}")
    digests = _pre_effect_payload_digests(
        model_payloads=model_payloads,
        repeat_model_payloads=repeat_model_payloads,
        predictions=predictions,
        selection=selection,
    )
    payload = {
        "stage": "Stage006",
        "test_eval_date": pd.Timestamp(test_eval_date).date().isoformat(),
        "test_label_rows_read_before_seal": 0,
        **digests,
    }
    temporary = seal_dir / f".{name}.tmp.{os.getpid()}.{time.time_ns()}"
    temporary.write_bytes(_canonical_json_bytes(payload))
    _fsync_file(temporary)
    os.replace(temporary, target)
    _fsync_file(target)
    _fsync_directory(seal_dir)
    return target


def _pre_effect_payload_digests(
    *,
    model_payloads: Mapping[str, bytes],
    repeat_model_payloads: Mapping[str, bytes],
    predictions: pd.DataFrame,
    selection: Mapping[str, Any],
) -> dict[str, Any]:
    if set(model_payloads) != {"return", "drawdown"} or set(
        repeat_model_payloads
    ) != {"return", "drawdown"}:
        raise RuntimeError("pre_effect_model_payload_shape")
    for group in (model_payloads, repeat_model_payloads):
        if any(not isinstance(payload, bytes) or not payload for payload in group.values()):
            raise RuntimeError("pre_effect_model_payload_invalid")
    prediction_bytes = predictions.to_csv(
        index=False, lineterminator="\n"
    ).encode("utf-8")
    selection_bytes = _canonical_json_bytes(dict(selection))
    return {
        "primary_model_sha256": {
            name: _sha256_bytes(payload)
            for name, payload in sorted(model_payloads.items())
        },
        "repeat_model_sha256": {
            name: _sha256_bytes(payload)
            for name, payload in sorted(repeat_model_payloads.items())
        },
        "ordered_prediction_payload_sha256": _sha256_bytes(prediction_bytes),
        "selection_payload_sha256": _sha256_bytes(selection_bytes),
    }


def verify_pre_effect_seal(
    path: Path,
    expected_eval_date: str,
    *,
    model_payloads: Mapping[str, bytes],
    repeat_model_payloads: Mapping[str, bytes],
    predictions: pd.DataFrame,
    selection: Mapping[str, Any],
) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise RuntimeError(f"pre_effect_seal_missing:{path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = pd.Timestamp(expected_eval_date).date().isoformat()
    digest_keys = {
        "primary_model_sha256",
        "repeat_model_sha256",
        "ordered_prediction_payload_sha256",
        "selection_payload_sha256",
    }
    expected_keys = {
        "stage",
        "test_eval_date",
        "test_label_rows_read_before_seal",
        *digest_keys,
    }
    primary = payload.get("primary_model_sha256", {})
    repeat = payload.get("repeat_model_sha256", {})
    digest_values = [
        *(primary.values() if isinstance(primary, dict) else []),
        *(repeat.values() if isinstance(repeat, dict) else []),
        payload.get("ordered_prediction_payload_sha256"),
        payload.get("selection_payload_sha256"),
    ]
    if (
        set(payload) != expected_keys
        or payload.get("stage") != "Stage006"
        or payload.get("test_eval_date") != expected
        or payload.get("test_label_rows_read_before_seal") != 0
        or not isinstance(primary, dict)
        or not isinstance(repeat, dict)
        or set(primary) != {"return", "drawdown"}
        or set(repeat) != {"return", "drawdown"}
        or any(
            not re.fullmatch(r"[0-9a-f]{64}", str(value))
            for value in digest_values
        )
    ):
        raise RuntimeError("pre_effect_seal_invalid")
    recomputed = _pre_effect_payload_digests(
        model_payloads=model_payloads,
        repeat_model_payloads=repeat_model_payloads,
        predictions=predictions,
        selection=selection,
    )
    if any(payload[name] != recomputed[name] for name in digest_keys):
        raise RuntimeError("pre_effect_payload_sha_mismatch")
    return payload


class PhaseGatedLabelStore:
    def __init__(
        self,
        *,
        jobs: pd.DataFrame,
        label_root: Path,
        manifest_files: Mapping[str, Mapping[str, Any]],
        initial_dates: list[str],
        test_dates: list[str],
    ) -> None:
        required = {
            "eval_date",
            "next_eval_date",
            "product_vt_symbol",
            "candidate_rank",
            "job_type",
            "job_id",
        }
        if missing := sorted(required - set(jobs.columns)):
            raise RuntimeError(f"label_store_job_columns_missing:{missing}")
        normalized = _normalize_date_columns(jobs, ["eval_date", "next_eval_date"])
        normalized["candidate_rank"] = pd.to_numeric(
            normalized["candidate_rank"], errors="raise"
        ).astype(int)
        if not normalized["job_type"].astype(str).eq("main").all():
            raise RuntimeError("label_store_non_main_job")
        if normalized["job_id"].astype(str).duplicated().any():
            raise RuntimeError("label_store_job_id_duplicate")
        self.jobs = normalized.copy()
        self.label_root = Path(label_root)
        self.manifest_files = dict(manifest_files)
        self.initial_dates = [pd.Timestamp(value).date().isoformat() for value in initial_dates]
        self.test_dates = [pd.Timestamp(value).date().isoformat() for value in test_dates]
        if set(self.initial_dates) & set(self.test_dates):
            raise RuntimeError("label_store_phase_date_overlap")
        self.opened: dict[str, pd.DataFrame] = {}
        self.seals: dict[str, dict[str, Any]] = {}
        self.initial_rows = 0
        self.test_rows_after_seal = 0
        self.test_rows_before_seal = 0

    def _load_month(self, eval_date: str) -> pd.DataFrame:
        month = self.jobs[self.jobs["eval_date"].eq(eval_date)].copy()
        if month.empty:
            raise RuntimeError(f"label_store_month_missing:{eval_date}")
        rows: list[dict[str, Any]] = []
        for job in month.sort_values("candidate_rank", kind="mergesort").itertuples(
            index=False
        ):
            relative = f"job_outputs/{job.job_id}/label.json"
            identity = self.manifest_files.get(relative)
            if not isinstance(identity, Mapping):
                raise RuntimeError(f"label_manifest_entry_missing:{job.job_id}")
            path = self.label_root / str(job.job_id) / "label.json"
            if (
                not path.is_file()
                or int(identity.get("size", -1)) != path.stat().st_size
                or str(identity.get("sha256")) != _sha256(path)
            ):
                raise RuntimeError(f"label_identity_mismatch:{job.job_id}")
            payload = json.loads(path.read_text(encoding="utf-8"))
            if set(payload) != set(LABEL_VALUE_COLUMNS):
                raise RuntimeError(f"label_payload_columns:{job.job_id}")
            numeric = {
                name: float(payload[name]) for name in LABEL_VALUE_COLUMNS
            }
            if not np.isfinite(np.fromiter(numeric.values(), dtype="float64")).all():
                raise RuntimeError(f"label_payload_nonfinite:{job.job_id}")
            rows.append(
                {
                    "eval_date": str(job.eval_date),
                    "next_eval_date": str(job.next_eval_date),
                    "product_vt_symbol": str(job.product_vt_symbol),
                    "candidate_rank": int(job.candidate_rank),
                    "job_id": str(job.job_id),
                    **numeric,
                }
            )
        result = pd.DataFrame(rows)
        baseline = result[result["candidate_rank"].eq(10)]
        if len(baseline) != 1:
            raise RuntimeError(f"label_store_rank10_shape:{eval_date}")
        anchor = baseline.iloc[0]
        if not np.equal(result["base_equity"].to_numpy(), anchor["base_equity"]).all():
            raise RuntimeError(f"label_store_base_equity_mismatch:{eval_date}")
        result["return_delta"] = result["future_return"] - float(
            anchor["future_return"]
        )
        result["drawdown_improvement"] = result["future_max_drawdown"] - float(
            anchor["future_max_drawdown"]
        )
        result.loc[result["candidate_rank"].eq(10), [
            "return_delta",
            "drawdown_improvement",
        ]] = 0.0
        return result

    def open_initial_labels(self) -> pd.DataFrame:
        if self.opened:
            raise RuntimeError("initial_labels_already_opened")
        frames = []
        for date in self.initial_dates:
            frame = self._load_month(date)
            self.opened[date] = frame
            self.initial_rows += len(frame)
            frames.append(frame)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def open_test_month(
        self,
        eval_date: str,
        seal_path: Path,
        *,
        model_payloads: Mapping[str, bytes],
        repeat_model_payloads: Mapping[str, bytes],
        predictions: pd.DataFrame,
        selection: Mapping[str, Any],
    ) -> pd.DataFrame:
        date = pd.Timestamp(eval_date).date().isoformat()
        if date not in self.test_dates:
            raise RuntimeError(f"test_label_date_not_authorized:{date}")
        if date in self.opened:
            raise RuntimeError(f"test_label_month_already_opened:{date}")
        if not Path(seal_path).is_file():
            raise RuntimeError(f"pre_effect_seal_missing:{seal_path}")
        seal = verify_pre_effect_seal(
            seal_path,
            date,
            model_payloads=model_payloads,
            repeat_model_payloads=repeat_model_payloads,
            predictions=predictions,
            selection=selection,
        )
        frame = self._load_month(date)
        self.seals[date] = seal
        self.opened[date] = frame
        self.test_rows_after_seal += len(frame)
        return frame

    def opened_labels(self) -> pd.DataFrame:
        frames = [self.opened[date] for date in sorted(self.opened)]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def final_audit(self) -> dict[str, int]:
        return {
            "aggregate_development_label_data_rows_parsed": 0,
            "aggregate_reconciliation_data_rows_parsed": 0,
            "initial_mature_label_rows_opened": int(self.initial_rows),
            "oos_test_label_rows_opened_before_own_pre_effect_seal": int(
                self.test_rows_before_seal
            ),
            "oos_test_label_rows_opened_after_own_pre_effect_seal": int(
                self.test_rows_after_seal
            ),
            "oos_test_label_rows_used_for_same_or_earlier_fold_training": 0,
            "oos_test_label_rows_used_for_preprocessing": 0,
            "oos_test_label_rows_used_for_hyperparameter_tuning": 0,
            "oos_test_label_rows_used_for_candidate_selection": 0,
            "oos_test_label_rows_used_for_tie_break": 0,
            "oos_test_label_rows_used_for_effect_after_seal": int(
                self.test_rows_after_seal
            ),
            "sealed_holdout_feature_prediction_rows": 0,
            "sealed_holdout_label_rows_read": 0,
            "sealed_holdout_label_rows_generated": 0,
            "sealed_holdout_label_rows_used_for_training": 0,
            "sealed_holdout_label_rows_used_for_effect": 0,
        }


def train_sequential_oos(
    *,
    panel: pd.DataFrame,
    folds: list[PitFold],
    label_store: PhaseGatedLabelStore,
    contract: dict[str, Any],
    pre_effect_dir: Path,
    ranker_factory: Callable[..., Any] = XGBRanker,
) -> dict[str, Any]:
    features = list(contract["features"])
    if features != MODEL_FEATURE_COLUMNS:
        raise RuntimeError("training_feature_contract_mismatch")
    params = dict(contract["xgboost"]["params"])
    estimator_audit = build_estimator_audit(ranker_factory, params)
    tolerance = float(contract["xgboost"]["repeat_fit_prediction_tolerance"])
    initial = label_store.open_initial_labels()
    if len(initial) != int(contract["pit_split"]["initial_mature_training_rows"]):
        raise RuntimeError("initial_mature_label_row_count")

    prediction_frames: list[pd.DataFrame] = []
    selections: list[dict[str, Any]] = []
    fold_rows: list[dict[str, Any]] = []
    model_payloads: dict[str, bytes] = {}
    repeat_model_hashes: dict[str, str] = {}
    seal_payloads: dict[str, Any] = {}
    fit_call_count = 0

    for fold in folds:
        test_date = fold.test_date.date().isoformat()
        train_metadata = panel.loc[fold.train_indices].copy()
        test = panel.loc[fold.test_indices].copy()
        train_labels = label_store.opened_labels()
        train_dates = {date.date().isoformat() for date in fold.train_dates}
        train_labels = train_labels[
            train_labels["eval_date"].astype(str).isin(train_dates)
        ].copy()
        join_keys = [
            "eval_date",
            "next_eval_date",
            "product_vt_symbol",
            "candidate_rank",
            "job_id",
        ]
        train = train_metadata.merge(
            train_labels[[*join_keys, "return_delta", "drawdown_improvement"]],
            on=join_keys,
            how="inner",
            validate="one_to_one",
        )
        if len(train) != len(train_metadata):
            raise RuntimeError(f"fold_training_labels_not_open:{test_date}")
        train_eval = pd.to_datetime(train["eval_date"], errors="raise").dt.normalize()
        train_end = pd.to_datetime(train["next_eval_date"], errors="raise").dt.normalize()
        if train_eval.ge(fold.test_date).any() or train_end.gt(fold.test_date).any():
            raise RuntimeError(f"fold_pit_violation:{test_date}")
        labeled = add_monthly_relevance(train)
        test.sort_values(
            ["eval_date", "candidate_rank", "product_vt_symbol"],
            kind="mergesort",
            inplace=True,
        )
        test.reset_index(drop=True, inplace=True)

        fitted: dict[str, dict[str, Any]] = {}
        for head, relevance in (
            ("return", "return_relevance"),
            ("drawdown", "drawdown_relevance"),
        ):
            _, x, y, qid = ranker_training_arrays(labeled, features, relevance)
            fitted[head] = fit_repeated_ranker(
                x,
                y,
                qid,
                test[features],
                params=params,
                tolerance=tolerance,
                ranker_factory=ranker_factory,
            )
            model_name = f"{fold.test_date:%Y%m%d}_{head}_relevance.ubj"
            model_payloads[model_name] = fitted[head]["model_raw"]
            repeat_model_hashes[model_name] = fitted[head]["repeat_model_sha256"]
            fit_call_count += 2

        predicted = test.copy()
        predicted["raw_return_score"] = fitted["return"]["predictions"]
        predicted["raw_drawdown_score"] = fitted["drawdown"]["predictions"]
        scored, selection = score_and_select_month(predicted)
        scored["train_months"] = len(fold.train_dates)
        scored["train_rows"] = len(train)
        scored["train_label_end_max"] = fold.train_label_end_max.date().isoformat()
        prediction_frames.append(scored)
        selection["train_months"] = len(fold.train_dates)
        selection["train_rows"] = len(train)
        selection["train_label_end_max"] = fold.train_label_end_max.date().isoformat()
        selections.append(selection)

        primary = {
            "return": fitted["return"]["model_raw"],
            "drawdown": fitted["drawdown"]["model_raw"],
        }
        repeats = {
            "return": fitted["return"]["repeat_model_raw"],
            "drawdown": fitted["drawdown"]["repeat_model_raw"],
        }
        seal_path = write_pre_effect_seal(
            pre_effect_dir,
            test_eval_date=test_date,
            model_payloads=primary,
            repeat_model_payloads=repeats,
            predictions=scored,
            selection=selection,
            test_label_rows_read_before_seal=0,
        )
        seal_payload = verify_pre_effect_seal(
            seal_path,
            test_date,
            model_payloads=primary,
            repeat_model_payloads=repeats,
            predictions=scored,
            selection=selection,
        )
        seal_payloads[seal_path.name] = seal_payload
        label_store.open_test_month(
            test_date,
            seal_path,
            model_payloads=primary,
            repeat_model_payloads=repeats,
            predictions=scored,
            selection=selection,
        )
        fold_rows.append(
            {
                "test_eval_date": test_date,
                "train_months": len(fold.train_dates),
                "train_rows": len(train),
                "test_rows": len(test),
                "train_eval_date_min": min(fold.train_dates).date().isoformat(),
                "train_eval_date_max": max(fold.train_dates).date().isoformat(),
                "train_label_end_max": fold.train_label_end_max.date().isoformat(),
                "pit_violation_rows": 0,
                "return_prediction_repeat_max_abs_difference": fitted["return"][
                    "prediction_repeat_max_abs_difference"
                ],
                "drawdown_prediction_repeat_max_abs_difference": fitted["drawdown"][
                    "prediction_repeat_max_abs_difference"
                ],
                "return_model_sha256": fitted["return"]["model_sha256"],
                "return_repeat_model_sha256": fitted["return"][
                    "repeat_model_sha256"
                ],
                "drawdown_model_sha256": fitted["drawdown"]["model_sha256"],
                "drawdown_repeat_model_sha256": fitted["drawdown"][
                    "repeat_model_sha256"
                ],
                "return_test_unique_scores": int(
                    len(np.unique(fitted["return"]["predictions"]))
                ),
                "drawdown_test_unique_scores": int(
                    len(np.unique(fitted["drawdown"]["predictions"]))
                ),
                "pre_effect_seal_sha256": _sha256(seal_path),
            }
        )

    predictions = pd.concat(prediction_frames, ignore_index=True)
    predictions.sort_values(
        ["eval_date", "candidate_rank", "product_vt_symbol"],
        kind="mergesort",
        inplace=True,
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
        "repeat_model_hashes": repeat_model_hashes,
        "seal_payloads": seal_payloads,
        "fit_call_count": int(fit_call_count),
        "label_access_audit": label_store.final_audit(),
        "estimator_audit": estimator_audit,
    }


def attach_realized_effects(
    monthly_selections: pd.DataFrame, opened_labels: pd.DataFrame
) -> pd.DataFrame:
    required_selection = {
        "eval_date",
        "arm_a_candidate_rank",
        "arm_b_candidate_rank",
        "arm_c_candidate_rank",
        "arm_c_replaced",
    }
    required_labels = {
        "eval_date",
        "candidate_rank",
        "return_delta",
        "drawdown_improvement",
    }
    if missing := sorted(required_selection - set(monthly_selections.columns)):
        raise RuntimeError(f"realized_selection_columns_missing:{missing}")
    if missing := sorted(required_labels - set(opened_labels.columns)):
        raise RuntimeError(f"realized_label_columns_missing:{missing}")
    labels = _normalize_date_columns(opened_labels, ["eval_date"])
    if labels.duplicated(["eval_date", "candidate_rank"]).any():
        raise RuntimeError("realized_label_key_duplicate")
    result = _normalize_date_columns(monthly_selections, ["eval_date"])
    for index, selection in result.iterrows():
        month = labels[labels["eval_date"].eq(selection["eval_date"])]
        for arm in ("a", "b", "c"):
            rank = int(selection[f"arm_{arm}_candidate_rank"])
            row = month[month["candidate_rank"].astype(int).eq(rank)]
            if len(row) != 1:
                raise RuntimeError(
                    f"realized_selected_rank_shape:{selection['eval_date']}:{rank}"
                )
            result.loc[index, f"arm_{arm}_realized_return_delta"] = float(
                row.iloc[0]["return_delta"]
            )
            result.loc[
                index, f"arm_{arm}_realized_drawdown_improvement"
            ] = float(row.iloc[0]["drawdown_improvement"])
        if not bool(selection["arm_c_replaced"]):
            result.loc[index, "arm_c_realized_return_delta"] = 0.0
            result.loc[index, "arm_c_realized_drawdown_improvement"] = 0.0
    return result


def build_execution_scope_audit(
    training_result: dict[str, Any], contract: dict[str, Any]
) -> dict[str, Any]:
    fold_count = len(training_result["fold_audit"])
    primary_fits = len(training_result["model_payloads"])
    repeat_fits = sum(
        1
        for row in training_result["fold_audit"].itertuples(index=False)
        for _ in (row.return_repeat_model_sha256, row.drawdown_repeat_model_sha256)
    )
    counts = {
        "authorized_training_entrypoint_invocations": 1,
        "primary_fit_calls": int(primary_fits),
        "repeat_fit_calls": int(repeat_fits),
        "total_fit_calls": int(training_result["fit_call_count"]),
        "parameter_searches": 0,
        "early_stopping_runs": 0,
        "extra_fit_calls": 0,
        "holdout_predictions": 0,
        "holdout_label_reads_or_generations": 0,
        "production_writes": 0,
        "ctp_connections": 0,
        "order_api_calls": 0,
        "unexpected_commands": 0,
        "unexpected_artifacts": 0,
    }
    expected = contract["execution_scope"]
    passed = counts == expected and fold_count == int(contract["pit_split"]["test_folds"])
    return {"passed": bool(passed), "counts": counts, "expected": expected}


def evaluate_technical_qualification(
    *,
    input_audit: dict[str, Any],
    panel_audit: dict[str, Any],
    folds: list[PitFold],
    training_result: dict[str, Any],
    contract: dict[str, Any],
    runtime_identities: list[dict[str, Any]],
    execution_scope: dict[str, Any],
) -> dict[str, Any]:
    split = contract["pit_split"]
    expected_folds = int(split["test_folds"])
    minimum = int(split["minimum_train_months"])
    expected_train_months = list(range(minimum, minimum + expected_folds))
    fold_audit = training_result["fold_audit"]
    predictions = training_result["predictions"]
    monthly = training_result["monthly_selections"]
    label_audit = training_result["label_access_audit"]
    expected_label_audit = contract["label_access_state_machine"][
        "required_final_integer_counts"
    ]
    repeat_columns = [
        "return_prediction_repeat_max_abs_difference",
        "drawdown_prediction_repeat_max_abs_difference",
    ]
    repeat_max = float(
        fold_audit[repeat_columns]
        .apply(pd.to_numeric, errors="raise")
        .to_numpy(dtype="float64")
        .max(initial=0.0)
    )
    hash_match = bool(
        fold_audit["return_model_sha256"].eq(
            fold_audit["return_repeat_model_sha256"]
        ).all()
        and fold_audit["drawdown_model_sha256"].eq(
            fold_audit["drawdown_repeat_model_sha256"]
        ).all()
    )
    selection_recomputed = True
    for eval_date, month in predictions.groupby("eval_date", sort=True):
        _, expected = score_and_select_month(month)
        actual = monthly[monthly["eval_date"].astype(str).eq(str(eval_date))]
        if len(actual) != 1 or any(
            int(actual.iloc[0][name]) != int(expected[name])
            for name in (
                "arm_a_candidate_rank",
                "arm_b_candidate_rank",
                "arm_c_candidate_rank",
            )
        ):
            selection_recomputed = False
            break
    test_dates = [fold.test_date.date().isoformat() for fold in folds]
    gates = {
        "all_input_identities_verified": bool(
            input_audit.get("all_input_identities_verified")
        ),
        "development_metadata_integrity": bool(
            panel_audit.get("all_features_finite")
            and panel_audit.get("monthly_group_contract")
            and int(panel_audit.get("holdout_prediction_rows", -1)) == 0
        ),
        "fold_count_and_boundaries": bool(
            len(folds) == expected_folds
            and len(fold_audit) == expected_folds
            and test_dates[0] == split["test_start"]
            and test_dates[-1] == split["test_end"]
        ),
        "expanding_train_month_counts": fold_audit["train_months"].astype(int).tolist()
        == expected_train_months,
        "pit_violations_zero": bool(
            fold_audit["pit_violation_rows"].astype(int).eq(0).all()
            and all(fold.train_label_end_max <= fold.test_date for fold in folds)
        ),
        "prediction_shape": bool(
            len(predictions) == int(split["oos_test_rows"])
            and predictions["eval_date"].nunique() == expected_folds
        ),
        "monthly_selection_shape": bool(
            len(monthly) == expected_folds
            and monthly["eval_date"].nunique() == expected_folds
        ),
        "primary_model_count": len(training_result["model_payloads"])
        == int(contract["xgboost"]["primary_model_count"]),
        "repeat_model_count": len(training_result["repeat_model_hashes"])
        == int(contract["xgboost"]["repeat_model_count"]),
        "fit_call_count": int(training_result["fit_call_count"])
        == int(contract["xgboost"]["total_fit_call_count"]),
        "prediction_determinism": repeat_max
        <= float(contract["xgboost"]["repeat_fit_prediction_tolerance"]),
        "model_byte_determinism": hash_match,
        "test_scores_nonconstant": bool(
            fold_audit["return_test_unique_scores"].astype(int).ge(2).all()
            and fold_audit["drawdown_test_unique_scores"].astype(int).ge(2).all()
        ),
        "frozen_estimator_and_params_exact": bool(
            training_result.get("estimator_audit", {}).get("passed")
        ),
        "pre_effect_seals_complete": len(training_result["seal_payloads"])
        == expected_folds,
        "label_access_state_machine_exact": label_audit == expected_label_audit,
        "runtime_identity_three_point_exact": bool(
            len(runtime_identities) == 3
            and runtime_identities[0] == runtime_identities[1] == runtime_identities[2]
        ),
        "selection_recomputed": selection_recomputed,
        "execution_scope_exact": bool(execution_scope.get("passed")),
    }
    return {
        "passed": bool(all(gates.values())),
        "gates": {name: bool(value) for name, value in gates.items()},
        "fold_count": int(len(folds)),
        "prediction_rows": int(len(predictions)),
        "model_count": int(len(training_result["model_payloads"])),
        "fit_call_count": int(training_result["fit_call_count"]),
        "prediction_repeat_max_abs_difference": repeat_max,
        "label_access_audit": label_audit,
    }


def consume_run_authorization(
    authorization: Mapping[str, Any],
    authorization_audit: Mapping[str, Any],
    *,
    consumption_path: Path = AUTHORIZATION_CONSUMPTION_PATH,
) -> dict[str, Any]:
    consumption_path = Path(consumption_path)
    if consumption_path.exists():
        raise RuntimeError("stage006_authorization_already_consumed")
    nonce = str(authorization.get("run_nonce", ""))
    authorization_sha = str(authorization_audit.get("authorization_sha256", ""))
    if (
        authorization.get("scope") != RUN_AUTHORIZATION_SCOPE
        or not re.fullmatch(r"[0-9a-f]{64}", nonce)
        or not re.fullmatch(r"[0-9a-f]{64}", authorization_sha)
    ):
        raise RuntimeError("stage006_authorization_consumption_input_invalid")
    receipt = {
        "stage": "Stage006",
        "decision": "stage006_authorization_consumed_for_one_development_run",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": RUN_AUTHORIZATION_SCOPE,
        "run_nonce": nonce,
        "authorization_sha256": authorization_sha,
    }
    consumption_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = consumption_path.parent / (
        f".{consumption_path.name}.tmp.{os.getpid()}.{time.time_ns()}"
    )
    temporary.write_bytes(_canonical_json_bytes(receipt))
    _fsync_file(temporary)
    try:
        os.link(temporary, consumption_path)
    except FileExistsError as error:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("stage006_authorization_already_consumed") from error
    temporary.unlink()
    _fsync_file(consumption_path)
    _fsync_directory(consumption_path.parent)
    return receipt


def _authorization_bound_paths() -> dict[str, Path]:
    return {
        "runner": Path(__file__).resolve(),
        "tests": TEST_PATH,
        "preregistration": PREREGISTRATION_PATH,
        "training_contract": CONTRACT_PATH,
        "runtime_identity": RUNTIME_IDENTITY_PATH,
        "final_independent_prerun_review": FINAL_IMPLEMENTATION_REVIEW_PATH,
    }


def load_run_authorization(
    *,
    authorization_path: Path = RUN_AUTHORIZATION_PATH,
    bound_paths: Mapping[str, Path] | None = None,
    expected_authorization_sha256: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not expected_authorization_sha256:
        raise RuntimeError("stage006_run_authorization_sha_required")
    authorization_path = Path(authorization_path)
    identity = verify_file_identities(
        {"authorization": authorization_path},
        {"authorization": expected_authorization_sha256},
    )["authorization"]
    payload = json.loads(authorization_path.read_text(encoding="utf-8"))
    if payload.get("line_id") != LINE_ID or payload.get("stage") != "Stage006":
        raise RuntimeError("stage006_run_authorization_identity_mismatch")
    if payload.get("decision") != "ALLOW_FROZEN_STAGE006_DEVELOPMENT_RUN":
        raise RuntimeError("stage006_run_not_authorized")
    if payload.get("scope") != RUN_AUTHORIZATION_SCOPE:
        raise RuntimeError("stage006_run_authorization_scope_mismatch")
    nonce = str(payload.get("run_nonce", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", nonce):
        raise RuntimeError("stage006_run_nonce_invalid")
    paths = dict(bound_paths or _authorization_bound_paths())
    if set(paths) != set(AUTHORIZATION_BOUND_FILE_NAMES) or set(
        payload.get("bound_files", {})
    ) != set(AUTHORIZATION_BOUND_FILE_NAMES):
        raise RuntimeError("stage006_authorization_bound_file_keys")
    expected: dict[str, str] = {}
    for name, path in paths.items():
        entry = payload["bound_files"][name]
        if Path(entry["path"]).resolve() != Path(path).resolve():
            raise RuntimeError(f"stage006_authorization_path_mismatch:{name}")
        expected[name] = str(entry["sha256"])
    bound_identities = verify_file_identities(paths, expected)
    return payload, {
        "authorization_path": str(authorization_path.resolve()),
        "authorization_sha256": identity["sha256"],
        "run_nonce": nonce,
        "scope": payload["scope"],
        "bound_file_identities": bound_identities,
    }


def _frozen_data_input_paths() -> dict[str, Path]:
    return {
        "feature_panel": FEATURE_PANEL_PATH,
        "stage002_summary": STAGE002_SUMMARY_PATH,
        "stage002_manifest": STAGE002_MANIFEST_PATH,
        "full_feature_split": FULL_SPLIT_PATH,
        "development_jobs": DEVELOPMENT_JOBS_PATH,
        "stage003_summary": STAGE003_SUMMARY_PATH,
        "stage005_decision": STAGE005_DECISION_PATH,
        "stage005_manifest": STAGE005_MANIFEST_PATH,
        "stage005_postrun_review": STAGE005_POSTRUN_REVIEW_PATH,
        "stage005_postrun_decision": STAGE005_POSTRUN_DECISION_PATH,
    }


def _frozen_data_input_hashes(contract: Mapping[str, Any]) -> dict[str, str]:
    inputs = contract["inputs"]
    return {
        "feature_panel": str(inputs["feature_panel"]["sha256"]),
        "stage002_summary": str(inputs["stage002_summary_sha256"]),
        "stage002_manifest": str(inputs["stage002_manifest_sha256"]),
        "full_feature_split": str(inputs["full_feature_split_sha256"]),
        "development_jobs": str(inputs["development_jobs_sha256"]),
        "stage003_summary": str(inputs["stage003_summary_sha256"]),
        "stage005_decision": str(inputs["stage005_decision_sha256"]),
        "stage005_manifest": str(inputs["stage005_manifest_sha256"]),
        "stage005_postrun_review": str(inputs["stage005_postrun_review_sha256"]),
        "stage005_postrun_decision": str(
            inputs["stage005_postrun_decision_sha256"]
        ),
    }


def verify_frozen_stage006_inputs(contract: Mapping[str, Any]) -> dict[str, Any]:
    identities = verify_file_identities(
        _frozen_data_input_paths(), _frozen_data_input_hashes(contract)
    )
    label_csv = verify_csv_identity_and_header_only(
        DEVELOPMENT_LABELS_PATH,
        expected_sha256=str(contract["inputs"]["development_labels"]["sha256"]),
        expected_header=DEVELOPMENT_LABEL_HEADER,
    )
    reconciliation_csv = verify_csv_identity_and_header_only(
        RECONCILIATION_PATH,
        expected_sha256=str(contract["inputs"]["reconciliation"]["sha256"]),
        expected_header=RECONCILIATION_HEADER,
    )
    stage005_decision = json.loads(
        STAGE005_DECISION_PATH.read_text(encoding="utf-8")
    )
    if (
        stage005_decision.get("decision")
        != "stage005_development_account_labels_complete_allow_stage006_training_preregistration"
        or stage005_decision.get("passed") is not True
        or int(stage005_decision.get("sealed_holdout_label_count", -1)) != 0
        or int(stage005_decision.get("order_api_called_count", -1)) != 0
    ):
        raise RuntimeError("stage005_decision_not_eligible_for_stage006")
    stable_payload = {
        "file_identities": identities,
        "development_labels": label_csv,
        "reconciliation": reconciliation_csv,
    }
    return {
        "all_input_identities_verified": True,
        **stable_payload,
        "identity_digest": _sha256_bytes(_canonical_json_bytes(stable_payload)),
        "aggregate_development_label_data_rows_parsed": int(
            label_csv["data_rows_parsed"]
        ),
        "aggregate_reconciliation_data_rows_parsed": int(
            reconciliation_csv["data_rows_parsed"]
        ),
    }


def capture_execution_checkpoint(
    *,
    checkpoint: str,
    expected_authorization_sha256: str,
    authorization_path: Path = RUN_AUTHORIZATION_PATH,
) -> dict[str, Any]:
    authorization, authorization_audit = load_run_authorization(
        authorization_path=authorization_path,
        expected_authorization_sha256=expected_authorization_sha256,
    )
    contract, contract_audit = load_frozen_contract()
    input_audit = verify_frozen_stage006_inputs(contract)
    return {
        "checkpoint": checkpoint,
        "contract": contract,
        "contract_audit": contract_audit,
        "authorization": authorization,
        "authorization_audit": authorization_audit,
        "runtime_identity": contract_audit["runtime_identity"],
        "input_identity_audit": input_audit,
    }


def _checkpoint_identity_payload(checkpoint: Mapping[str, Any]) -> dict[str, Any]:
    contract_audit = checkpoint["contract_audit"]
    authorization_audit = checkpoint["authorization_audit"]
    return {
        "contract_sha256": contract_audit["contract_sha256"],
        "preregistration_sha256": contract_audit.get("preregistration_sha256"),
        "runtime_identity_sha256": contract_audit.get("runtime_identity_sha256"),
        "remediation_sha256": contract_audit.get("remediation_sha256"),
        "prerun_review_sha256": contract_audit.get("prerun_review_sha256"),
        "prerun_review_decision_sha256": contract_audit.get(
            "prerun_review_decision_sha256"
        ),
        "authorization_sha256": authorization_audit["authorization_sha256"],
        "authorization_scope": authorization_audit["scope"],
        "run_nonce": authorization_audit["run_nonce"],
        "authorization_bound_file_identities": authorization_audit[
            "bound_file_identities"
        ],
        "runtime_identity": checkpoint["runtime_identity"],
        "input_identity_digest": checkpoint["input_identity_audit"][
            "identity_digest"
        ],
    }


def build_checkpoint_stability_audit(
    checkpoints: list[Mapping[str, Any]],
) -> dict[str, Any]:
    if not checkpoints:
        raise RuntimeError("stage006_checkpoint_audit_empty")
    entries = []
    for checkpoint in checkpoints:
        payload = _checkpoint_identity_payload(checkpoint)
        entries.append(
            {
                "checkpoint": str(checkpoint["checkpoint"]),
                "identity_digest": _sha256_bytes(_canonical_json_bytes(payload)),
                "runtime_identity": checkpoint["runtime_identity"],
                "input_identity_audit": checkpoint["input_identity_audit"],
            }
        )
    digests = [entry["identity_digest"] for entry in entries]
    passed = bool(
        len(set(digests)) == 1
        and all(
            bool(entry["input_identity_audit"]["all_input_identities_verified"])
            for entry in entries
        )
    )
    return {
        "passed": passed,
        "checkpoint_count": len(entries),
        "all_checkpoint_identities_exact": len(set(digests)) == 1,
        "entries": entries,
    }


def load_stage006_metadata() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    features = pd.read_csv(FEATURE_PANEL_PATH)
    splits = pd.read_csv(FULL_SPLIT_PATH)
    jobs = pd.read_csv(DEVELOPMENT_JOBS_PATH)
    manifest = json.loads(STAGE005_MANIFEST_PATH.read_text(encoding="utf-8"))
    files = manifest.get("files")
    if (
        not isinstance(files, dict)
        or int(manifest.get("file_count_excluding_manifest", -1)) != len(files)
    ):
        raise RuntimeError("stage005_manifest_shape_invalid")
    return features, splits, jobs, manifest


def prepare_stage006_run_data(contract: dict[str, Any]) -> dict[str, Any]:
    features, splits, jobs, manifest = load_stage006_metadata()
    panel, panel_audit = build_development_metadata_panel(
        features, splits, jobs, contract
    )
    minimum = int(contract["pit_split"]["minimum_train_months"])
    folds = build_pit_folds(panel, minimum_train_months=minimum)
    test_dates = [fold.test_date.date().isoformat() for fold in folds]
    all_dates = sorted(panel["eval_date"].astype(str).unique().tolist())
    initial_dates = all_dates[:minimum]
    initial_rows = int(panel["eval_date"].astype(str).isin(initial_dates).sum())
    initial_panel = panel[panel["eval_date"].astype(str).isin(initial_dates)]
    if (
        len(folds) != int(contract["pit_split"]["test_folds"])
        or not test_dates
        or test_dates[0] != str(contract["pit_split"]["test_start"])
        or test_dates[-1] != str(contract["pit_split"]["test_end"])
        or len(initial_dates)
        != int(contract["pit_split"]["initial_mature_training_months"])
        or initial_rows != int(contract["pit_split"]["initial_mature_training_rows"])
        or initial_dates[-1]
        != str(
            contract["label_access_state_machine"]["initial_open"][
                "maximum_eval_date"
            ]
        )
        or max(initial_panel["next_eval_date"].astype(str))
        != str(
            contract["label_access_state_machine"]["initial_open"][
                "maximum_next_eval_date"
            ]
        )
        or [len(fold.train_dates) for fold in folds]
        != list(range(minimum, minimum + len(folds)))
    ):
        raise RuntimeError("stage006_frozen_pit_shape_mismatch")
    main_jobs = jobs[
        jobs["job_type"].astype(str).eq("main")
        & jobs["split"].astype(str).eq("development")
    ].copy()
    label_store = PhaseGatedLabelStore(
        jobs=main_jobs,
        label_root=LABEL_ROOT,
        manifest_files=manifest["files"],
        initial_dates=initial_dates,
        test_dates=test_dates,
    )
    return {
        "panel": panel,
        "panel_audit": panel_audit,
        "folds": folds,
        "label_store": label_store,
        "initial_dates": initial_dates,
        "test_dates": test_dates,
        "stage005_manifest_file_count": len(manifest["files"]),
    }


def publish_artifact_bundle(
    result_dir: Path,
    *,
    csv_frames: Mapping[str, pd.DataFrame],
    json_payloads: Mapping[str, Any],
    text_payloads: Mapping[str, str],
    model_payloads: Mapping[str, bytes],
    seal_payloads: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    result_dir = Path(result_dir)
    if result_dir.exists():
        raise RuntimeError(f"stage006_result_already_exists:{result_dir}")
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
        seals_dir = partial / "pre_effect_seals"
        models_dir.mkdir()
        seals_dir.mkdir()
        for name, frame in csv_frames.items():
            if Path(name).name != name:
                raise RuntimeError(f"stage006_invalid_csv_name:{name}")
            frame.to_csv(partial / name, index=False, lineterminator="\n")
        for name, payload in json_payloads.items():
            if Path(name).name != name:
                raise RuntimeError(f"stage006_invalid_json_name:{name}")
            (partial / name).write_bytes(_canonical_json_bytes(payload))
        for name, payload in text_payloads.items():
            if Path(name).name != name:
                raise RuntimeError(f"stage006_invalid_text_name:{name}")
            (partial / name).write_text(payload, encoding="utf-8")
        for name, payload in model_payloads.items():
            if Path(name).name != name:
                raise RuntimeError(f"stage006_invalid_model_name:{name}")
            (models_dir / name).write_bytes(payload)
        for name, payload in seal_payloads.items():
            if Path(name).name != name:
                raise RuntimeError(f"stage006_invalid_seal_name:{name}")
            (seals_dir / name).write_bytes(_canonical_json_bytes(payload))

        artifacts: dict[str, dict[str, Any]] = {}
        for path in sorted(candidate for candidate in partial.rglob("*") if candidate.is_file()):
            relative = path.relative_to(partial).as_posix()
            _fsync_file(path)
            artifacts[relative] = {
                "size": int(path.stat().st_size),
                "sha256": _sha256(path),
            }
        manifest = partial / "artifact_manifest.json"
        manifest.write_bytes(
            _canonical_json_bytes(
                {
                    "stage": "Stage006",
                    "manifest_semantics": "all_result_bundle_files_except_manifest",
                    "artifacts": artifacts,
                }
            )
        )
        _fsync_file(manifest)
        for directory in (models_dir, seals_dir, partial):
            _fsync_directory(directory)
        os.rename(partial, result_dir)
        renamed = True
        _fsync_directory(result_dir.parent)
        return {
            path.relative_to(result_dir).as_posix(): {
                "size": int(path.stat().st_size),
                "sha256": _sha256(path),
            }
            for path in sorted(
                candidate for candidate in result_dir.rglob("*") if candidate.is_file()
            )
        }
    except BaseException as error:
        if partial.exists():
            shutil.rmtree(partial)
        if renamed and result_dir.exists():
            quarantine = result_dir.parent / (
                f".{result_dir.name}.quarantined.{os.getpid()}.{time.time_ns()}"
            )
            try:
                os.rename(result_dir, quarantine)
                _fsync_directory(result_dir.parent)
            except BaseException as quarantine_error:
                raise RuntimeError(
                    f"stage006_post_rename_publish_uncertain:{result_dir}"
                ) from quarantine_error
            raise RuntimeError(
                f"stage006_post_rename_publish_quarantined:{quarantine}"
            ) from error
        raise


def _model_manifest(training_result: Mapping[str, Any]) -> dict[str, Any]:
    primary = {
        name: {
            "size": len(payload),
            "sha256": _sha256_bytes(payload),
        }
        for name, payload in sorted(training_result["model_payloads"].items())
    }
    repeat = dict(sorted(training_result["repeat_model_hashes"].items()))
    return {
        "stage": "Stage006",
        "primary_model_count": len(primary),
        "repeat_model_count": len(repeat),
        "primary_models": primary,
        "repeat_model_sha256": repeat,
    }


def _stage006_report(
    *,
    decision: str,
    technical: Mapping[str, Any],
    effect: Mapping[str, Any] | None,
) -> str:
    effect_pass = None if effect is None else bool(effect.get("passed"))
    return "\n".join(
        [
            "# Stage006 frozen development OOS run",
            "",
            f"- Decision: `{decision}`",
            f"- Technical qualification: `{bool(technical.get('passed'))}`",
            f"- Effect qualification: `{effect_pass}`",
            "- Holdout labels/predictions: `0/0`",
            "- Production writes, CTP connections, order calls: `0/0/0`",
            "- Parameter search and early stopping: disabled by frozen contract",
            "- Overfit assessment: guarded but still high-risk until an independently reviewed true-engine A/C test passes",
            "",
        ]
    )


def _canonical_stage006_run_paths() -> dict[str, Path]:
    line = Path(__file__).resolve().parents[1]
    out = line / "artifacts/stage006_dual_ranker_development_oos"
    return {
        "authorization": out / "run_authorization.json",
        "consumption": out / "authorization_consumption.json",
        "result": out / "frozen_run",
    }


def run_frozen_stage006(
    *,
    expected_authorization_sha256: str | None,
) -> dict[str, Any]:
    if not expected_authorization_sha256:
        raise RuntimeError("stage006_run_authorization_sha_required")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_authorization_sha256):
        raise RuntimeError("stage006_run_authorization_sha_invalid")
    paths = _canonical_stage006_run_paths()
    authorization_path = paths["authorization"]
    consumption_path = paths["consumption"]
    result_dir = paths["result"]
    if result_dir.exists():
        raise RuntimeError(f"stage006_result_already_exists:{result_dir}")

    started_at = datetime.now().astimezone()
    first = capture_execution_checkpoint(
        checkpoint="before_training",
        expected_authorization_sha256=expected_authorization_sha256,
        authorization_path=authorization_path,
    )
    contract = first["contract"]
    authorization_receipt = consume_run_authorization(
        first["authorization"],
        first["authorization_audit"],
        consumption_path=consumption_path,
    )
    prepared = prepare_stage006_run_data(contract)
    result_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{result_dir.name}.execution.{os.getpid()}.",
            dir=result_dir.parent,
        )
    )
    try:
        training = train_sequential_oos(
            panel=prepared["panel"],
            folds=prepared["folds"],
            label_store=prepared["label_store"],
            contract=contract,
            pre_effect_dir=staging / "pre_effect_seals",
            ranker_factory=XGBRanker,
        )
        second = capture_execution_checkpoint(
            checkpoint="after_all_models",
            expected_authorization_sha256=expected_authorization_sha256,
            authorization_path=authorization_path,
        )
        checkpoints = [first, second]
        stability = build_checkpoint_stability_audit(checkpoints)
        execution_scope = build_execution_scope_audit(training, contract)
        technical_input_audit = {
            "all_input_identities_verified": bool(stability["passed"]),
            "checkpoint_count": int(stability["checkpoint_count"]),
        }
        technical = evaluate_technical_qualification(
            input_audit=technical_input_audit,
            panel_audit=prepared["panel_audit"],
            folds=prepared["folds"],
            training_result=training,
            contract=contract,
            runtime_identities=[
                first["runtime_identity"],
                second["runtime_identity"],
                second["runtime_identity"],
            ],
            execution_scope=execution_scope,
        )

        effect: dict[str, Any] | None = None
        realized: pd.DataFrame | None = None
        if bool(technical.get("passed")):
            realized = attach_realized_effects(
                training["monthly_selections"],
                prepared["label_store"].opened_labels(),
            )
            effect = evaluate_effect_qualification(realized, contract)
            third = capture_execution_checkpoint(
                checkpoint="after_effect_evaluation",
                expected_authorization_sha256=expected_authorization_sha256,
                authorization_path=authorization_path,
            )
            checkpoints.append(third)
            stability = build_checkpoint_stability_audit(checkpoints)
            technical = evaluate_technical_qualification(
                input_audit={
                    "all_input_identities_verified": bool(stability["passed"]),
                    "checkpoint_count": int(stability["checkpoint_count"]),
                },
                panel_audit=prepared["panel_audit"],
                folds=prepared["folds"],
                training_result=training,
                contract=contract,
                runtime_identities=[
                    first["runtime_identity"],
                    second["runtime_identity"],
                    third["runtime_identity"],
                ],
                execution_scope=execution_scope,
            )
            if not bool(technical.get("passed")):
                effect = None
                realized = None

        decision = stage006_decision(
            technical_pass=bool(technical.get("passed")),
            effect_pass=bool(effect and effect.get("passed")),
        )
        completed_at = datetime.now().astimezone()
        decision_payload = {
            "line_id": LINE_ID,
            "stage": "Stage006",
            "decision": decision,
            "technical_pass": bool(technical.get("passed")),
            "effect_pass": None if effect is None else bool(effect.get("passed")),
            "formal_identity": contract["formal_identity"],
            "holdout_prediction_rows": 0,
            "holdout_label_rows_read": 0,
            "production_writes": 0,
            "ctp_connections": 0,
            "order_api_calls": 0,
        }
        runtime_audit = {
            "passed": bool(stability["passed"]),
            "checkpoint_count": len(checkpoints),
            "all_runtime_identities_exact": len(
                {
                    _sha256_bytes(_canonical_json_bytes(item["runtime_identity"]))
                    for item in checkpoints
                }
            )
            == 1,
            "checkpoints": [
                {
                    "checkpoint": item["checkpoint"],
                    "runtime_identity": item["runtime_identity"],
                }
                for item in checkpoints
            ],
        }
        run_receipt = {
            "line_id": LINE_ID,
            "stage": "Stage006",
            "started_at": started_at.isoformat(timespec="seconds"),
            "completed_at": completed_at.isoformat(timespec="seconds"),
            "duration_seconds": (completed_at - started_at).total_seconds(),
            "authorization_consumption": authorization_receipt,
            "authorization_sha256": first["authorization_audit"][
                "authorization_sha256"
            ],
            "run_nonce": first["authorization_audit"]["run_nonce"],
            "checkpoint_count": len(checkpoints),
            "decision": decision,
        }
        json_payloads: dict[str, Any] = {
            "technical_qualification.json": technical,
            "label_access_audit.json": training["label_access_audit"],
            "runtime_identity_audit.json": runtime_audit,
            "input_identity_audit.json": stability,
            "execution_scope_audit.json": execution_scope,
            "decision.json": decision_payload,
            "run_receipt.json": run_receipt,
        }
        csv_frames: dict[str, pd.DataFrame] = {
            "fold_audit.csv": training["fold_audit"],
        }
        model_payloads: Mapping[str, bytes] = {}
        seal_payloads: Mapping[str, Any] = {}
        if bool(technical.get("passed")):
            if effect is None or realized is None:
                raise RuntimeError("stage006_effect_result_missing_after_technical_pass")
            csv_frames.update(
                {
                    "ordered_oos_predictions.csv": training["predictions"],
                    "monthly_arm_selections.csv": realized,
                }
            )
            json_payloads["effect_qualification.json"] = effect
            json_payloads["model_manifest.json"] = _model_manifest(training)
            model_payloads = training["model_payloads"]
            seal_payloads = training["seal_payloads"]

        published = publish_artifact_bundle(
            result_dir,
            csv_frames=csv_frames,
            json_payloads=json_payloads,
            text_payloads={
                "report.md": _stage006_report(
                    decision=decision,
                    technical=technical,
                    effect=effect,
                )
            },
            model_payloads=model_payloads,
            seal_payloads=seal_payloads,
        )
        return {
            "decision": decision,
            "technical_pass": bool(technical.get("passed")),
            "effect_pass": None if effect is None else bool(effect.get("passed")),
            "result_dir": str(result_dir.resolve()),
            "published_artifacts": published,
        }
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main() -> int:
    result = run_frozen_stage006(
        expected_authorization_sha256=os.environ.get(
            "STAGE006_RUN_AUTHORIZATION_SHA256"
        )
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
