"""Train the frozen Stage016 dual-regressor selector on development labels only."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple

import numpy as np
import pandas as pd
import sklearn
import xgboost
from xgboost import XGBRegressor


LINE = Path(__file__).resolve().parents[1]
OUT = LINE / "artifacts/stage016_frozen_dual_regressor_training"
CONTRACT_PATH = OUT / "training_contract.json"
PREREGISTRATION_PATH = (
    LINE / "stages/20260902_0644_stage016_frozen_dual_regressor_preregistration.md"
)
EXPECTED_CONTRACT_SHA256 = "beac6e6a4947043e1250c989e91d196c3edd4446cc6db043b67f91db92d90e6e"
EXPECTED_PREREGISTRATION_SHA256 = (
    "ab56e31be4a49e45bea778ccbafb58bed5d2cd580480adff08f43b3edf47a8d8"
)
FEATURE_PANEL_PATH = (
    LINE
    / "artifacts/stage014_prelabel_feature_contract/prelabel_feature_panel.csv"
)
STAGE014_CONTRACT_PATH = (
    LINE / "artifacts/stage014_prelabel_feature_contract/feature_contract.json"
)
STAGE015_CAMPAIGN = (
    LINE
    / "artifacts/stage015_development_label_batch/"
    "campaign_20260902T021241+0800_98656"
)
DEVELOPMENT_LABELS_PATH = STAGE015_CAMPAIGN / "development_labels.csv"
RECONCILIATION_PATH = STAGE015_CAMPAIGN / "reconciliation.csv"
STAGE015_REVIEW_PATH = (
    LINE / "reviews/20260902_stage015_full_development_labels_independent_review.md"
)
TEST_PATH = LINE / "tests/test_stage016_frozen_dual_regressor_training.py"
FINAL_PRERUN_REVIEW_PATH = (
    LINE / "reviews/20260902_stage016_prerun_rereview.md"
)
RUN_AUTHORIZATION_PATH = OUT / "run_authorization.json"
RESULT_DIR = OUT / "frozen_run"

MODEL_FEATURE_COLUMNS = [
    "formal_probability_delta_vs_rank10",
    "formal_rank_distance",
    "pnl120_z_delta_vs_rank10",
    "pnl60_z_delta_vs_rank10",
    "sharpe60_z_delta_vs_rank10",
    "positive_day60_z_delta_vs_rank10",
    "opened60_z_delta_vs_rank10",
    "slippage60_z_delta_vs_rank10",
    "drawdown60_z_delta_vs_rank10",
]
RELATIVE_LABEL_COLUMNS = [
    "return_delta",
    "drawdown_improvement",
    "net_pnl_delta",
    "slippage_delta",
    "trade_count_delta",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file_identities(
    paths: dict[str, Path], expected_sha256: dict[str, str]
) -> dict[str, dict[str, Any]]:
    if set(paths) != set(expected_sha256):
        raise RuntimeError("frozen_input_identity_key_mismatch")
    identities: dict[str, dict[str, Any]] = {}
    for key, path in paths.items():
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
            raise RuntimeError(f"frozen_input_changed_while_hashing:{key}")
        if digest != expected_sha256[key]:
            raise RuntimeError(f"frozen_input_sha_mismatch:{key}")
        identities[key] = {
            "path": str(path),
            "size": int(after.st_size),
            "sha256": digest,
            "device": int(after.st_dev),
            "inode": int(after.st_ino),
            "mtime_ns": int(after.st_mtime_ns),
            "ctime_ns": int(after.st_ctime_ns),
        }
    return identities


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
        raise RuntimeError("stage016_training_contract_sha_drift")
    if preregistration_sha != EXPECTED_PREREGISTRATION_SHA256:
        raise RuntimeError("stage016_preregistration_sha_drift")
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if contract.get("contract_status") != "frozen_before_development_label_values_read":
        raise RuntimeError("stage016_contract_status_invalid")
    if list(contract.get("features", [])) != MODEL_FEATURE_COLUMNS:
        raise RuntimeError("stage016_contract_feature_order_drift")
    if contract.get("parameter_scan_allowed") is not False:
        raise RuntimeError("stage016_parameter_scan_not_forbidden")
    if contract.get("label_based_feature_selection_allowed") is not False:
        raise RuntimeError("stage016_label_feature_selection_not_forbidden")
    if contract.get("sealed_holdout", {}).get("label_values_read_allowed") is not False:
        raise RuntimeError("stage016_holdout_not_sealed")
    actual_runtime = _runtime_versions()
    expected_runtime = contract["runtime_versions"]
    runtime_match = actual_runtime == expected_runtime
    if not runtime_match:
        raise RuntimeError(
            f"stage016_runtime_version_drift:{actual_runtime}:{expected_runtime}"
        )
    return contract, {
        "contract_path": str(CONTRACT_PATH),
        "contract_sha256": contract_sha,
        "preregistration_path": str(PREREGISTRATION_PATH),
        "preregistration_sha256": preregistration_sha,
        "runtime_versions": actual_runtime,
        "runtime_versions_match": runtime_match,
    }


def _authorization_bound_paths() -> dict[str, Path]:
    return {
        "runner": Path(__file__).resolve(),
        "tests": TEST_PATH,
        "contract": CONTRACT_PATH,
        "preregistration": PREREGISTRATION_PATH,
        "review": FINAL_PRERUN_REVIEW_PATH,
    }


def load_run_authorization(
    *,
    authorization_path: Path = RUN_AUTHORIZATION_PATH,
    bound_paths: dict[str, Path] | None = None,
    expected_authorization_sha256: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not expected_authorization_sha256:
        raise RuntimeError("stage016_run_authorization_sha_required")
    authorization_identity = verify_file_identities(
        {"authorization": authorization_path},
        {"authorization": expected_authorization_sha256},
    )["authorization"]
    manifest = json.loads(authorization_path.read_text(encoding="utf-8"))
    if manifest.get("line_id") != "futures_trend_ai_xgboost_ensemble":
        raise RuntimeError("stage016_run_authorization_line_mismatch")
    if manifest.get("stage") != "Stage016":
        raise RuntimeError("stage016_run_authorization_stage_mismatch")
    if manifest.get("decision") != "ALLOW_FROZEN_STAGE016_RUN":
        raise RuntimeError("stage016_run_not_authorized")
    paths = bound_paths or _authorization_bound_paths()
    expected_names = {"runner", "tests", "contract", "preregistration", "review"}
    if set(paths) != expected_names or set(manifest.get("bound_files", {})) != expected_names:
        raise RuntimeError("stage016_run_authorization_bound_file_keys")
    expected_hashes: dict[str, str] = {}
    for name, path in paths.items():
        entry = manifest["bound_files"][name]
        if Path(entry["path"]).resolve() != path.resolve():
            raise RuntimeError(f"stage016_run_authorization_path_mismatch:{name}")
        expected_hashes[name] = str(entry["sha256"])
    identities = verify_file_identities(paths, expected_hashes)
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
        raise RuntimeError("stage016_run_authorization_changed")
    return current_manifest, current_audit


def _normalize_date_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        result[column] = pd.to_datetime(
            result[column], errors="raise"
        ).dt.date.astype(str)
    return result


def build_joined_development_panel(
    feature_frame: pd.DataFrame,
    label_frame: pd.DataFrame,
    reconciliation_frame: pd.DataFrame,
    contract: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if list(contract.get("features", [])) != MODEL_FEATURE_COLUMNS:
        raise RuntimeError("frozen_feature_contract_mismatch")
    split = contract["development_split"]
    rows_per_month = int(split["rows_per_month"])
    expected_months = int(split["month_count"])
    expected_rows = rows_per_month * expected_months
    expected_ranks = list(range(10, 10 + rows_per_month))

    feature_required = {
        "eval_date",
        "next_eval_date",
        "product_vt_symbol",
        "score_rank",
        "split",
        "label_values_read_allowed",
        *MODEL_FEATURE_COLUMNS,
    }
    label_required = {
        "job_id",
        "job_type",
        "eval_date",
        "next_eval_date",
        "product_vt_symbol",
        "candidate_rank",
        *RELATIVE_LABEL_COLUMNS,
    }
    reconciliation_required = {
        "job_id",
        "eval_date",
        "candidate_rank",
        "base_equity_delta",
    }
    if missing := sorted(feature_required - set(feature_frame.columns)):
        raise RuntimeError(f"development_feature_columns_missing:{missing}")
    if missing := sorted(label_required - set(label_frame.columns)):
        raise RuntimeError(f"development_label_columns_missing:{missing}")
    if missing := sorted(reconciliation_required - set(reconciliation_frame.columns)):
        raise RuntimeError(f"development_reconciliation_columns_missing:{missing}")

    features = _normalize_date_columns(
        feature_frame, ["eval_date", "next_eval_date"]
    )
    features = features[features["split"].astype(str).eq("development")].copy()
    allowed = features["label_values_read_allowed"].map(
        lambda value: value is True or str(value).strip().lower() == "true"
    )
    if not allowed.all():
        raise RuntimeError("development_feature_label_read_not_allowed")
    features["candidate_rank"] = pd.to_numeric(
        features.pop("score_rank"), errors="raise"
    ).astype(int)
    feature_values = features[MODEL_FEATURE_COLUMNS].apply(
        pd.to_numeric, errors="raise"
    )
    probability = feature_values["formal_probability_delta_vs_rank10"].to_numpy(float)
    if np.isinf(probability).any():
        raise RuntimeError("development_probability_feature_infinite")
    other_feature_values = feature_values[
        [
            column
            for column in MODEL_FEATURE_COLUMNS
            if column != "formal_probability_delta_vs_rank10"
        ]
    ].to_numpy(float)
    if not np.isfinite(other_feature_values).all():
        raise RuntimeError("development_model_feature_nonfinite")
    features[MODEL_FEATURE_COLUMNS] = feature_values

    labels = _normalize_date_columns(label_frame, ["eval_date", "next_eval_date"])
    if not labels["job_type"].astype(str).eq("main").all():
        raise RuntimeError("development_labels_include_non_main_job")
    labels["candidate_rank"] = pd.to_numeric(
        labels["candidate_rank"], errors="raise"
    ).astype(int)
    holdout_start = pd.Timestamp(contract["sealed_holdout"]["first_eval_date"])
    sealed_holdout_rows = int(
        (pd.to_datetime(labels["eval_date"]) >= holdout_start).sum()
    )
    if sealed_holdout_rows:
        raise RuntimeError("sealed_holdout_label_rows_present")

    reconciliation = _normalize_date_columns(reconciliation_frame, ["eval_date"])
    reconciliation["candidate_rank"] = pd.to_numeric(
        reconciliation["candidate_rank"], errors="raise"
    ).astype(int)
    error_columns = [
        column for column in reconciliation.columns if column.endswith("_error")
    ]
    if not error_columns:
        raise RuntimeError("reconciliation_error_columns_missing")
    reconciliation_numeric = reconciliation[
        ["base_equity_delta", *error_columns]
    ].apply(pd.to_numeric, errors="raise")
    reconciliation_values = reconciliation_numeric.to_numpy(dtype="float64")
    if not np.isfinite(reconciliation_values).all():
        raise RuntimeError("development_reconciliation_nonfinite")
    reconciliation_max = float(
        np.max(np.abs(reconciliation_values), initial=0.0)
    )
    if not np.isfinite(reconciliation_max) or reconciliation_max > 1e-9:
        raise RuntimeError(f"development_reconciliation_failed:{reconciliation_max}")

    key_columns = [
        "eval_date",
        "next_eval_date",
        "product_vt_symbol",
        "candidate_rank",
    ]
    for name, frame in (("feature", features), ("label", labels)):
        if frame.duplicated(key_columns).any():
            raise RuntimeError(f"development_{name}_key_duplicate")
    if labels["job_id"].duplicated().any():
        raise RuntimeError("development_label_job_id_duplicate")
    if reconciliation.duplicated(["job_id", "eval_date", "candidate_rank"]).any():
        raise RuntimeError("development_reconciliation_key_duplicate")

    panel = features.merge(
        labels,
        on=key_columns,
        how="inner",
        validate="one_to_one",
        suffixes=("", "_label"),
    )
    panel = panel.merge(
        reconciliation[["job_id", "eval_date", "candidate_rank"]],
        on=["job_id", "eval_date", "candidate_rank"],
        how="inner",
        validate="one_to_one",
    )
    if len(panel) != expected_rows or len(features) != expected_rows or len(labels) != expected_rows:
        raise RuntimeError(
            f"development_join_shape:{len(features)}:{len(labels)}:{len(panel)}:{expected_rows}"
        )
    eval_dates = sorted(panel["eval_date"].unique())
    if (
        len(eval_dates) != expected_months
        or eval_dates[0] != split["first_eval_date"]
        or eval_dates[-1] != split["last_eval_date"]
    ):
        raise RuntimeError("development_month_boundary_shape")
    monthly_ranks = panel.groupby("eval_date")["candidate_rank"].apply(
        lambda values: sorted(values.tolist())
    )
    if not monthly_ranks.map(lambda values: values == expected_ranks).all():
        raise RuntimeError("development_month_rank_shape")

    relative = panel[RELATIVE_LABEL_COLUMNS].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(relative.to_numpy(dtype="float64")).all():
        raise RuntimeError("development_relative_label_nonfinite")
    panel[RELATIVE_LABEL_COLUMNS] = relative
    rank10 = panel["candidate_rank"].eq(10)
    rank10_max = float(
        np.nanmax(np.abs(panel.loc[rank10, RELATIVE_LABEL_COLUMNS].to_numpy(float)))
    )
    if not np.isfinite(rank10_max) or rank10_max > 1e-12:
        raise RuntimeError(f"rank10_relative_label_not_zero:{rank10_max}")

    panel.sort_values(["eval_date", "candidate_rank"], kind="mergesort", inplace=True)
    panel.reset_index(drop=True, inplace=True)
    audit = {
        "rows": int(len(panel)),
        "development_months": int(len(eval_dates)),
        "rows_per_month": rows_per_month,
        "first_eval_date": eval_dates[0],
        "last_eval_date": eval_dates[-1],
        "rank10_relative_label_max_abs": rank10_max,
        "reconciliation_max_abs_error": reconciliation_max,
        "sealed_holdout_label_rows": sealed_holdout_rows,
    }
    return panel, audit
MONTH_SELECTION_COLUMNS = {
    "eval_date",
    "product_vt_symbol",
    "candidate_rank",
    "predicted_return_delta",
    "predicted_drawdown_improvement",
}


class PitFold(NamedTuple):
    train_dates: pd.DatetimeIndex
    test_date: pd.Timestamp
    train_indices: pd.Index
    test_indices: pd.Index
    train_label_end_max: pd.Timestamp


def build_pit_folds(
    frame: pd.DataFrame,
    *,
    min_train_months: int,
    rows_per_month: int,
) -> list[PitFold]:
    required = {
        "eval_date",
        "next_eval_date",
        "product_vt_symbol",
        "candidate_rank",
    }
    if missing := sorted(required - set(frame.columns)):
        raise RuntimeError(f"pit_columns_missing:{missing}")
    panel = frame.copy()
    panel["eval_date"] = pd.to_datetime(
        panel["eval_date"], errors="raise"
    ).dt.normalize()
    panel["next_eval_date"] = pd.to_datetime(
        panel["next_eval_date"], errors="raise"
    ).dt.normalize()
    panel["candidate_rank"] = pd.to_numeric(
        panel["candidate_rank"], errors="raise"
    ).astype(int)
    if panel.duplicated(["eval_date", "candidate_rank"]).any():
        raise RuntimeError("pit_month_rank_duplicate")
    month_sizes = panel.groupby("eval_date").size()
    if not month_sizes.eq(rows_per_month).all():
        raise RuntimeError("pit_month_row_count")
    next_counts = panel.groupby("eval_date")["next_eval_date"].nunique(dropna=False)
    if not next_counts.eq(1).all():
        raise RuntimeError("month_next_eval_date_not_unique")
    month_label_end = panel.groupby("eval_date")["next_eval_date"].first()
    if (month_label_end.index >= pd.DatetimeIndex(month_label_end.to_numpy())).any():
        raise RuntimeError("pit_label_end_not_after_eval_date")

    dates = pd.DatetimeIndex(sorted(panel["eval_date"].unique()))
    folds: list[PitFold] = []
    for test_date in dates:
        prior = dates[dates < test_date]
        eligible = pd.DatetimeIndex(
            [date for date in prior if month_label_end.loc[date] <= test_date]
        )
        if len(eligible) < min_train_months:
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


def score_and_select_month(month: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    if missing := sorted(MONTH_SELECTION_COLUMNS - set(month.columns)):
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
    for column in ("predicted_return_delta", "predicted_drawdown_improvement"):
        scored[column] = pd.to_numeric(scored[column], errors="raise").astype(float)
    if not np.isfinite(
        scored[
            ["predicted_return_delta", "predicted_drawdown_improvement"]
        ].to_numpy(float)
    ).all():
        raise RuntimeError("selection_prediction_nonfinite")
    scored["return_percentile"] = scored["predicted_return_delta"].rank(
        method="average", ascending=True, pct=True
    )
    scored["drawdown_percentile"] = scored[
        "predicted_drawdown_improvement"
    ].rank(method="average", ascending=True, pct=True)
    scored["dual_head_score"] = (
        scored["return_percentile"] + scored["drawdown_percentile"]
    ) / 2.0
    ordered = scored.sort_values(
        [
            "dual_head_score",
            "predicted_return_delta",
            "predicted_drawdown_improvement",
            "candidate_rank",
            "product_vt_symbol",
        ],
        ascending=[False, False, False, True, True],
        kind="mergesort",
    )
    arm_a = baseline.iloc[0]
    arm_b = ordered.iloc[0]
    gate = bool(
        float(arm_b["predicted_return_delta"]) > 0.0
        and float(arm_b["predicted_drawdown_improvement"]) > 0.0
    )
    arm_c = arm_b if gate else arm_a
    selection = {
        "eval_date": str(arm_a["eval_date"]),
        "arm_a_product_vt_symbol": str(arm_a["product_vt_symbol"]),
        "arm_a_candidate_rank": int(arm_a["candidate_rank"]),
        "arm_b_product_vt_symbol": str(arm_b["product_vt_symbol"]),
        "arm_b_candidate_rank": int(arm_b["candidate_rank"]),
        "arm_b_predicted_return_delta": float(arm_b["predicted_return_delta"]),
        "arm_b_predicted_drawdown_improvement": float(
            arm_b["predicted_drawdown_improvement"]
        ),
        "arm_b_dual_head_score": float(arm_b["dual_head_score"]),
        "arm_c_product_vt_symbol": str(arm_c["product_vt_symbol"]),
        "arm_c_candidate_rank": int(arm_c["candidate_rank"]),
        "arm_c_replaced": bool(gate and int(arm_b["candidate_rank"]) != 10),
    }
    return scored, selection


def evaluate_effect_qualification(
    monthly_selections: pd.DataFrame,
    contract: dict[str, Any],
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
    frame["eval_date"] = pd.to_datetime(
        frame["eval_date"], errors="raise"
    ).dt.normalize()
    if frame["eval_date"].duplicated().any():
        raise RuntimeError("qualification_eval_date_duplicate")
    expected_months = int(contract["development_split"]["oos_fold_count"])
    if len(frame) != expected_months:
        raise RuntimeError(f"qualification_month_count:{len(frame)}:{expected_months}")
    frame["arm_c_candidate_rank"] = pd.to_numeric(
        frame["arm_c_candidate_rank"], errors="raise"
    ).astype(int)
    frame["arm_c_replaced"] = frame["arm_c_replaced"].astype(bool)
    if not frame["arm_c_replaced"].eq(frame["arm_c_candidate_rank"].ne(10)).all():
        raise RuntimeError("qualification_replacement_flag_mismatch")
    return_values = pd.to_numeric(
        frame["arm_c_realized_return_delta"], errors="raise"
    ).astype(float)
    drawdown_values = pd.to_numeric(
        frame["arm_c_realized_drawdown_improvement"], errors="raise"
    ).astype(float)
    if not np.isfinite(return_values).all() or not np.isfinite(drawdown_values).all():
        raise RuntimeError("qualification_nonfinite_effect")

    active = frame["arm_c_replaced"]
    replacement_months = int(active.sum())
    replacement_years = sorted(frame.loc[active, "eval_date"].dt.year.unique().tolist())
    total_return = float(return_values.sum())
    total_drawdown = float(drawdown_values.sum())
    leave_best_return = float(total_return - return_values.max())
    leave_best_drawdown = float(total_drawdown - drawdown_values.max())
    years = frame["eval_date"].dt.year
    yearly_return = {
        int(year): float(return_values[years.eq(year)].sum())
        for year in sorted(years.unique())
    }
    yearly_drawdown = {
        int(year): float(drawdown_values[years.eq(year)].sum())
        for year in sorted(years.unique())
    }
    if replacement_months:
        active_joint_positive_rate = float(
            (
                return_values[active].gt(0.0)
                & drawdown_values[active].gt(0.0)
            ).mean()
        )
    else:
        active_joint_positive_rate = 0.0

    thresholds = contract["qualification"]
    required_years = [int(year) for year in thresholds["required_c_replacement_years"]]
    yearly_return_nonnegative = all(
        yearly_return.get(year, float("-inf"))
        >= float(thresholds["minimum_each_year_return_delta_inclusive"])
        for year in required_years
    )
    yearly_drawdown_nonnegative = all(
        yearly_drawdown.get(year, float("-inf"))
        >= float(thresholds["minimum_each_year_drawdown_improvement_inclusive"])
        for year in required_years
    )
    gates = {
        "minimum_replacement_months": replacement_months
        >= int(thresholds["minimum_c_replacement_months"]),
        "required_replacement_years": set(required_years).issubset(replacement_years),
        "total_return_delta_positive": total_return
        > float(thresholds["minimum_total_return_delta_exclusive"]),
        "total_drawdown_improvement_positive": total_drawdown
        > float(thresholds["minimum_total_drawdown_improvement_exclusive"]),
        "leave_best_out_return_delta_positive": leave_best_return
        > float(thresholds["minimum_leave_best_out_return_delta_exclusive"]),
        "leave_best_out_drawdown_improvement_positive": leave_best_drawdown
        > float(
            thresholds["minimum_leave_best_out_drawdown_improvement_exclusive"]
        ),
        "each_year_return_delta_nonnegative": yearly_return_nonnegative,
        "each_year_drawdown_improvement_nonnegative": yearly_drawdown_nonnegative,
        "active_joint_positive_rate": active_joint_positive_rate
        >= float(thresholds["minimum_active_joint_positive_rate_inclusive"]),
    }
    return {
        "passed": bool(all(gates.values())),
        "gates": {key: bool(value) for key, value in gates.items()},
        "oos_months": int(len(frame)),
        "replacement_months": replacement_months,
        "replacement_years": replacement_years,
        "total_return_delta": total_return,
        "total_drawdown_improvement": total_drawdown,
        "leave_best_out_return_delta": leave_best_return,
        "leave_best_out_drawdown_improvement": leave_best_drawdown,
        "yearly_return_delta": yearly_return,
        "yearly_drawdown_improvement": yearly_drawdown,
        "active_joint_positive_rate": active_joint_positive_rate,
    }


def stage016_decision(*, technical_pass: bool, effect_pass: bool) -> str:
    if not technical_pass:
        return "stage016_contract_or_pit_invalid_stop"
    if not effect_pass:
        return "stage016_development_oos_proxy_fail_stop_no_holdout"
    return "stage016_development_oos_proxy_pass_allow_true_engine_ac"


def resolve_stage016_outcome(
    *,
    technical: dict[str, Any],
    monthly_selections: pd.DataFrame,
    contract: dict[str, Any],
    effect_evaluator: Any = None,
) -> tuple[dict[str, Any] | None, str]:
    if not bool(technical.get("passed")):
        return None, stage016_decision(technical_pass=False, effect_pass=False)
    evaluator = effect_evaluator or evaluate_effect_qualification
    effect = evaluator(monthly_selections, contract)
    return effect, stage016_decision(
        technical_pass=True, effect_pass=bool(effect["passed"])
    )


def fit_repeated_regressor(
    train_features: pd.DataFrame,
    train_target: np.ndarray | pd.Series,
    predict_features: pd.DataFrame,
    *,
    params: dict[str, Any],
    maximum_prediction_abs_difference: float,
) -> dict[str, Any]:
    if list(train_features.columns) != list(predict_features.columns):
        raise RuntimeError("xgboost_feature_order_mismatch")
    if len(train_features) != len(train_target) or not len(train_features):
        raise RuntimeError("xgboost_train_shape")
    target = np.asarray(train_target, dtype="float64")
    if not np.isfinite(target).all():
        raise RuntimeError("xgboost_target_nonfinite")
    models: list[XGBRegressor] = []
    predictions: list[np.ndarray] = []
    raw_models: list[bytes] = []
    for _ in range(2):
        model = XGBRegressor(**params)
        model.fit(train_features, target, verbose=False)
        prediction = np.asarray(model.predict(predict_features), dtype="float64")
        if not np.isfinite(prediction).all():
            raise RuntimeError("xgboost_prediction_nonfinite")
        raw = bytes(model.get_booster().save_raw(raw_format="ubj"))
        models.append(model)
        predictions.append(prediction)
        raw_models.append(raw)
    max_difference = float(
        np.max(np.abs(predictions[0] - predictions[1]), initial=0.0)
    )
    model_hashes = [hashlib.sha256(raw).hexdigest() for raw in raw_models]
    if max_difference > maximum_prediction_abs_difference:
        raise RuntimeError(f"xgboost_prediction_nondeterministic:{max_difference}")
    if model_hashes[0] != model_hashes[1]:
        raise RuntimeError("xgboost_model_bytes_nondeterministic")
    return {
        "model": models[0],
        "predictions": predictions[0],
        "prediction_max_abs_difference": max_difference,
        "model_raw": raw_models[0],
        "repeat_model_raw": raw_models[1],
        "model_sha256": model_hashes[0],
        "repeat_model_sha256": model_hashes[1],
    }


def train_oos_dual_regressors(
    panel: pd.DataFrame,
    folds: list[PitFold],
    contract: dict[str, Any],
) -> dict[str, Any]:
    features = list(contract["features"])
    if features != MODEL_FEATURE_COLUMNS:
        raise RuntimeError("training_feature_contract_mismatch")
    if list(contract["targets"]) != ["return_delta", "drawdown_improvement"]:
        raise RuntimeError("training_target_contract_mismatch")
    params = dict(contract["xgb_regressor_parameters"])
    tolerance = float(
        contract["determinism"]["maximum_prediction_abs_difference"]
    )
    prediction_frames: list[pd.DataFrame] = []
    selections: list[dict[str, Any]] = []
    fold_rows: list[dict[str, Any]] = []
    model_payloads: dict[str, bytes] = {}

    for fold in folds:
        train = panel.loc[fold.train_indices].copy()
        test = panel.loc[fold.test_indices].copy()
        if pd.to_datetime(test["eval_date"]).dt.normalize().nunique() != 1:
            raise RuntimeError("fold_test_month_shape")
        pit_invalid = pd.to_datetime(train["next_eval_date"]).dt.normalize().gt(
            fold.test_date
        ) | pd.to_datetime(train["eval_date"]).dt.normalize().ge(fold.test_date)
        pit_violation_rows = int(pit_invalid.sum())
        if pit_violation_rows:
            raise RuntimeError(f"fold_pit_violation:{fold.test_date.date()}")

        fitted: dict[str, dict[str, Any]] = {}
        for target in ("return_delta", "drawdown_improvement"):
            fitted[target] = fit_repeated_regressor(
                train.loc[:, features],
                train[target],
                test.loc[:, features],
                params=params,
                maximum_prediction_abs_difference=tolerance,
            )
            model_name = f"{fold.test_date:%Y%m%d}_{target}.ubj"
            model_payloads[model_name] = fitted[target]["model_raw"]

        month = test.copy()
        month["predicted_return_delta"] = fitted["return_delta"]["predictions"]
        month["predicted_drawdown_improvement"] = fitted[
            "drawdown_improvement"
        ]["predictions"]
        scored, selection = score_and_select_month(month)
        scored["train_months"] = len(fold.train_dates)
        scored["train_rows"] = len(train)
        scored["train_label_end_max"] = fold.train_label_end_max.date().isoformat()
        prediction_frames.append(scored)

        def selected_row(rank: int) -> pd.Series:
            selected = scored[scored["candidate_rank"].eq(rank)]
            if len(selected) != 1:
                raise RuntimeError(f"selected_rank_shape:{rank}")
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
                "return_prediction_repeat_max_abs_difference": fitted["return_delta"][
                    "prediction_max_abs_difference"
                ],
                "drawdown_prediction_repeat_max_abs_difference": fitted[
                    "drawdown_improvement"
                ]["prediction_max_abs_difference"],
                "return_model_sha256": fitted["return_delta"]["model_sha256"],
                "return_repeat_model_sha256": fitted["return_delta"][
                    "repeat_model_sha256"
                ],
                "drawdown_model_sha256": fitted["drawdown_improvement"][
                    "model_sha256"
                ],
                "drawdown_repeat_model_sha256": fitted["drawdown_improvement"][
                    "repeat_model_sha256"
                ],
            }
        )

    predictions = pd.concat(prediction_frames, ignore_index=True)
    predictions.sort_values(["eval_date", "candidate_rank"], kind="mergesort", inplace=True)
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
    }


def evaluate_technical_qualification(
    *,
    input_audit: dict[str, Any],
    panel_audit: dict[str, Any],
    folds: list[PitFold],
    training_result: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    split = contract["development_split"]
    fold_count = int(split["oos_fold_count"])
    rows_per_month = int(split["rows_per_month"])
    minimum_train_months = int(split["minimum_train_months"])
    predictions = training_result["predictions"]
    monthly = training_result["monthly_selections"]
    fold_audit = training_result["fold_audit"]
    tolerance = float(
        contract["determinism"]["maximum_prediction_abs_difference"]
    )

    test_dates = [fold.test_date.date().isoformat() for fold in folds]
    expected_train_months = list(
        range(minimum_train_months, minimum_train_months + fold_count)
    )
    observed_train_months = (
        fold_audit["train_months"].astype(int).tolist()
        if "train_months" in fold_audit
        else []
    )
    pit_fold_violations = sum(
        int(fold.train_label_end_max > fold.test_date)
        or int(max(fold.train_dates) >= fold.test_date)
        for fold in folds
    )
    audit_pit_rows = (
        int(pd.to_numeric(fold_audit["pit_violation_rows"], errors="raise").sum())
        if "pit_violation_rows" in fold_audit
        else -1
    )
    prediction_repeat_columns = [
        "return_prediction_repeat_max_abs_difference",
        "drawdown_prediction_repeat_max_abs_difference",
    ]
    prediction_repeat_max = float(
        fold_audit[prediction_repeat_columns]
        .apply(pd.to_numeric, errors="raise")
        .to_numpy(float)
        .max(initial=0.0)
    )
    model_hash_match = bool(
        fold_audit["return_model_sha256"].eq(
            fold_audit["return_repeat_model_sha256"]
        ).all()
        and fold_audit["drawdown_model_sha256"].eq(
            fold_audit["drawdown_repeat_model_sha256"]
        ).all()
    )

    arm_c_gate_exact = True
    for row in monthly.itertuples(index=False):
        gate = bool(
            float(row.arm_b_predicted_return_delta) > 0.0
            and float(row.arm_b_predicted_drawdown_improvement) > 0.0
        )
        expected_c_rank = int(row.arm_b_candidate_rank) if gate else 10
        expected_replaced = expected_c_rank != 10
        if (
            int(row.arm_c_candidate_rank) != expected_c_rank
            or bool(row.arm_c_replaced) != expected_replaced
        ):
            arm_c_gate_exact = False
            break

    selection_recomputed = True
    if not predictions.empty:
        recomputed: dict[str, dict[str, Any]] = {}
        for eval_date, month in predictions.groupby("eval_date", sort=True):
            try:
                _, selection = score_and_select_month(month)
            except RuntimeError:
                selection_recomputed = False
                break
            recomputed[str(eval_date)] = selection
        if selection_recomputed:
            for row in monthly.itertuples(index=False):
                expected = recomputed.get(str(row.eval_date))
                if expected is None or any(
                    int(getattr(row, key)) != int(expected[key])
                    for key in (
                        "arm_a_candidate_rank",
                        "arm_b_candidate_rank",
                        "arm_c_candidate_rank",
                    )
                ):
                    selection_recomputed = False
                    break

    gates = {
        "all_input_identities_verified": bool(
            input_audit.get("all_input_identities_verified")
        ),
        "runtime_versions_match": bool(input_audit.get("runtime_versions_match")),
        "stage014_contract_match": bool(input_audit.get("stage014_contract_match")),
        "development_panel_integrity": bool(
            int(panel_audit.get("sealed_holdout_label_rows", -1)) == 0
            and float(panel_audit.get("rank10_relative_label_max_abs", float("inf")))
            <= 1e-12
            and float(panel_audit.get("reconciliation_max_abs_error", float("inf")))
            <= 1e-9
        ),
        "fold_count_and_test_boundaries": bool(
            len(folds) == fold_count
            and len(fold_audit) == fold_count
            and len(test_dates) == fold_count
            and test_dates[0] == split["first_test_eval_date"]
            and test_dates[-1] == split["last_test_eval_date"]
        ),
        "expanding_train_month_counts": observed_train_months
        == expected_train_months,
        "test_rows_per_fold": bool(
            len(fold_audit) == fold_count
            and fold_audit["test_rows"].astype(int).eq(rows_per_month).all()
        ),
        "pit_violations_zero": bool(
            pit_fold_violations == 0 and audit_pit_rows == 0
        ),
        "prediction_panel_shape": bool(
            len(predictions) == fold_count * rows_per_month
            and predictions["eval_date"].nunique() == fold_count
            and predictions.groupby("eval_date").size().eq(rows_per_month).all()
        ),
        "monthly_selection_shape": bool(
            len(monthly) == fold_count and monthly["eval_date"].nunique() == fold_count
        ),
        "two_models_per_fold": len(training_result["model_payloads"])
        == 2 * fold_count,
        "prediction_determinism": prediction_repeat_max <= tolerance,
        "model_byte_determinism": model_hash_match,
        "arm_a_rank10_exact": bool(monthly["arm_a_candidate_rank"].astype(int).eq(10).all()),
        "arm_c_prediction_gate_exact": arm_c_gate_exact,
        "arm_selection_recomputed": selection_recomputed,
    }
    return {
        "passed": bool(all(gates.values())),
        "gates": {key: bool(value) for key, value in gates.items()},
        "fold_count": len(folds),
        "prediction_rows": int(len(predictions)),
        "monthly_selection_rows": int(len(monthly)),
        "model_count": int(len(training_result["model_payloads"])),
        "pit_violation_rows": audit_pit_rows,
        "pit_violation_folds": int(pit_fold_violations),
        "prediction_repeat_max_abs_difference": prediction_repeat_max,
    }


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
) -> dict[str, dict[str, Any]]:
    if result_dir.exists():
        raise RuntimeError(f"stage016_result_already_exists:{result_dir}")
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
        models_dir.mkdir()
        for name, frame in csv_frames.items():
            if Path(name).name != name:
                raise RuntimeError(f"stage016_invalid_csv_name:{name}")
            frame.to_csv(partial / name, index=False, lineterminator="\n")
        for name, payload in json_payloads.items():
            if Path(name).name != name:
                raise RuntimeError(f"stage016_invalid_json_name:{name}")
            (partial / name).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        for name, payload in text_payloads.items():
            if Path(name).name != name:
                raise RuntimeError(f"stage016_invalid_text_name:{name}")
            (partial / name).write_text(payload, encoding="utf-8")
        for name, payload in model_payloads.items():
            if Path(name).name != name:
                raise RuntimeError(f"stage016_invalid_model_name:{name}")
            (models_dir / name).write_bytes(payload)

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
                    "stage": "Stage016",
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
        for directory in (models_dir, partial):
            _fsync_directory(directory)
        os.rename(partial, result_dir)
        renamed = True
        _fsync_directory(result_dir.parent)
        published: dict[str, dict[str, Any]] = {}
        for path in sorted(
            candidate for candidate in result_dir.rglob("*") if candidate.is_file()
        ):
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
                    f"stage016_post_rename_publish_uncertain:{result_dir}"
                ) from quarantine_error
            try:
                _fsync_directory(result_dir.parent)
            except OSError:
                pass
            raise RuntimeError(
                f"stage016_post_rename_publish_quarantined:{quarantine}"
            ) from error
        raise


def _input_paths() -> dict[str, Path]:
    return {
        "feature_panel": FEATURE_PANEL_PATH,
        "feature_contract": STAGE014_CONTRACT_PATH,
        "development_labels": DEVELOPMENT_LABELS_PATH,
        "reconciliation": RECONCILIATION_PATH,
        "stage015_review": STAGE015_REVIEW_PATH,
    }


def _validate_stage014_contract(
    stage014: dict[str, Any], contract: dict[str, Any]
) -> None:
    if stage014.get("formal_release_id") != contract["formal_release_id"]:
        raise RuntimeError("stage014_formal_release_mismatch")
    if list(stage014.get("model_features", [])) != list(contract["features"]):
        raise RuntimeError("stage014_model_features_mismatch")
    planned = stage014.get("planned_models", {})
    if planned.get("return_delta_model") != "XGBRegressor":
        raise RuntimeError("stage014_return_model_mismatch")
    if planned.get("drawdown_improvement_model") != "XGBRegressor":
        raise RuntimeError("stage014_drawdown_model_mismatch")
    if planned.get("parameters") != contract["xgb_regressor_parameters"]:
        raise RuntimeError("stage014_xgboost_parameters_mismatch")
    if planned.get("parameter_scan_allowed") is not False:
        raise RuntimeError("stage014_parameter_scan_contract_mismatch")
    if planned.get("label_based_feature_selection_allowed") is not False:
        raise RuntimeError("stage014_feature_selection_contract_mismatch")
    split = stage014.get("split", {})
    expected = contract["development_split"]
    if (
        int(split.get("development_months", -1)) != int(expected["month_count"])
        or split.get("sealed_holdout_start")
        != contract["sealed_holdout"]["first_eval_date"]
        or split.get("sealed_holdout_end")
        != contract["sealed_holdout"]["last_eval_date"]
        or split.get("holdout_label_values_read_allowed_before_model_freeze")
        is not False
    ):
        raise RuntimeError("stage014_split_contract_mismatch")


def _build_report(
    *,
    decision: str,
    technical: dict[str, Any],
    effect: dict[str, Any] | None,
) -> str:
    technical_gate_lines = "\n".join(
        f"- `{name}`: `{value}`" for name, value in technical["gates"].items()
    )
    if effect is None:
        return (
            "# Stage016 冻结双XGBoost技术失败审计\n\n"
            f"- 决策：`{decision}`。\n"
            "- 技术门未通过，效果评价未执行。\n"
            "- 未发布OOS预测、月度选择、模型或任何真实效果值。\n"
            "- 未读取sealed holdout标签、未修改生产目录、未连接CTP、未调用订单API。\n\n"
            "## 技术门\n\n"
            f"{technical_gate_lines}\n\n"
            "## 反思\n\n"
            "- 过拟合判断：本次不形成效果结论；技术错误修复前禁止观察或推断development效果。\n"
            "- 继续价值：只有修复实现错误、重新独立审查并保持预注册合同不变后，才允许重跑。\n"
        )
    effect_gate_lines = "\n".join(
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
    return (
        "# Stage016 冻结双XGBoost development OOS评估\n\n"
        f"- 决策：`{decision}`。\n"
        f"- 技术门：`{technical['passed']}`；效果门：`{effect['passed']}`。\n"
        "- A为线上逻辑回归正式rank10；C保留正式Top9，只在XGBoost同一候选的两项目标预测均为正时替换第10席。\n"
        "- 本阶段未读取sealed holdout标签、未修改生产目录、未连接CTP、未调用订单API。\n\n"
        "## Development OOS结果\n\n"
        f"- OOS月份：`{effect['oos_months']}`；C实际替换：`{effect['replacement_months']}`；替换年份：`{effect['replacement_years']}`。\n"
        f"- 账户边际收益增量合计：`{effect['total_return_delta']:.12g}`；剔除最好月：`{effect['leave_best_out_return_delta']:.12g}`。\n"
        f"- 账户边际回撤改善合计：`{effect['total_drawdown_improvement']:.12g}`；剔除最好月：`{effect['leave_best_out_drawdown_improvement']:.12g}`。\n"
        f"- 分年收益增量：`{yearly_return}`。\n"
        f"- 分年回撤改善：`{yearly_drawdown}`。\n"
        f"- 实际替换月双目标联合命中率：`{effect['active_joint_positive_rate']:.6%}`。\n\n"
        "上述数值是15个月互斥账户边际标签的资格代理，不是可复利策略曲线；本阶段不发布期末权益、总收益、组合最大回撤、Sharpe、总滑点、总交易次数或胜率。\n\n"
        "## 技术门\n\n"
        f"{technical_gate_lines}\n\n"
        "## 效果门\n\n"
        f"{effect_gate_lines}\n\n"
        "## 反思\n\n"
        "- 过拟合风险：高。只有15个development OOS月，但规则、参数和门槛均在读取标签前冻结，本次没有扫描或结果后修改。\n"
        "- 继续价值：只有全部效果门通过时，才值得把OOS月选择冻结后进入一次development真实账户引擎A/C；失败则停止当前形状且不读取holdout。\n"
    )


def main() -> None:
    if RESULT_DIR.exists():
        raise RuntimeError(f"stage016_result_already_exists:{RESULT_DIR}")
    authorization_sha = os.environ.get("STAGE016_RUN_AUTHORIZATION_SHA256")
    authorization, authorization_audit_before = load_run_authorization(
        expected_authorization_sha256=authorization_sha
    )
    contract, contract_audit = load_frozen_contract()
    input_paths = _input_paths()
    input_identities_before = verify_file_identities(
        input_paths, contract["input_sha256"]
    )
    stage014_contract = json.loads(
        STAGE014_CONTRACT_PATH.read_text(encoding="utf-8")
    )
    _validate_stage014_contract(stage014_contract, contract)
    input_audit = {
        **contract_audit,
        "all_input_identities_verified": True,
        "stage014_contract_match": True,
        "input_identities": input_identities_before,
    }

    feature_frame = pd.read_csv(FEATURE_PANEL_PATH, encoding="utf-8-sig")
    label_frame = pd.read_csv(DEVELOPMENT_LABELS_PATH, float_precision="round_trip")
    reconciliation_frame = pd.read_csv(
        RECONCILIATION_PATH, float_precision="round_trip"
    )
    panel, panel_audit = build_joined_development_panel(
        feature_frame, label_frame, reconciliation_frame, contract
    )
    split = contract["development_split"]
    folds = build_pit_folds(
        panel,
        min_train_months=int(split["minimum_train_months"]),
        rows_per_month=int(split["rows_per_month"]),
    )
    training_result = train_oos_dual_regressors(panel, folds, contract)
    input_identities_after = verify_file_identities(
        input_paths, contract["input_sha256"]
    )
    if input_identities_before != input_identities_after:
        raise RuntimeError("stage016_input_identity_changed_during_training")
    contract_after, contract_audit_after = load_frozen_contract()
    if contract != contract_after or contract_audit != contract_audit_after:
        raise RuntimeError("stage016_contract_changed_during_training")
    authorization_after, authorization_audit_after = require_stable_run_authorization(
        before_manifest=authorization,
        before_audit=authorization_audit_before,
        expected_authorization_sha256=authorization_sha
    )

    technical = evaluate_technical_qualification(
        input_audit=input_audit,
        panel_audit=panel_audit,
        folds=folds,
        training_result=training_result,
        contract=contract,
    )
    effect, decision_name = resolve_stage016_outcome(
        technical=technical,
        monthly_selections=training_result["monthly_selections"],
        contract=contract,
    )
    authorization_final, authorization_audit_final = require_stable_run_authorization(
        before_manifest=authorization,
        before_audit=authorization_audit_before,
        expected_authorization_sha256=authorization_sha,
    )
    if authorization_after != authorization_final or authorization_audit_after != authorization_audit_final:
        raise RuntimeError("stage016_run_authorization_changed_during_effect_evaluation")
    input_identities_final = verify_file_identities(
        input_paths, contract["input_sha256"]
    )
    if input_identities_before != input_identities_final:
        raise RuntimeError("stage016_input_identity_changed_during_effect_evaluation")
    contract_final, contract_audit_final = load_frozen_contract()
    if contract != contract_final or contract_audit != contract_audit_final:
        raise RuntimeError("stage016_contract_changed_during_effect_evaluation")

    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    runner_identity = {
        "path": str(Path(__file__).resolve()),
        "sha256": _sha256(Path(__file__).resolve()),
    }
    tests_identity = {"path": str(TEST_PATH), "sha256": _sha256(TEST_PATH)}
    model_manifest = {
        name: {
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        for name, payload in sorted(training_result["model_payloads"].items())
    }
    decision_payload = {
        "line_id": "futures_trend_ai_xgboost_ensemble",
        "stage": "Stage016",
        "generated_at": generated_at,
        "decision": decision_name,
        "passed": bool(technical["passed"] and effect and effect["passed"]),
        "technical_passed": bool(technical["passed"]),
        "effect_evaluated": effect is not None,
        "effect_passed": None if effect is None else bool(effect["passed"]),
        "allows_development_true_engine_ac": bool(
            technical["passed"] and effect and effect["passed"]
        ),
        "allows_sealed_holdout_labels": False,
        "allows_production_change": False,
        "sealed_holdout_label_values_read": False,
        "trains_model": True,
        "parameter_scan_count": 0,
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
        "trained_model_count": len(model_manifest),
        "models_published": effect is not None,
        "effect_evaluated": effect is not None,
        "sealed_holdout_label_values_read": False,
        "production_modified": False,
        "ctp_connected": False,
        "order_api_called_count": 0,
    }
    report = _build_report(
        decision=decision_name, technical=technical, effect=effect
    )
    csv_frames = {"fold_audit.csv": training_result["fold_audit"]}
    json_payloads = {
        "input_audit.json": input_audit,
        "panel_audit.json": panel_audit,
        "technical_qualification.json": technical,
        "decision.json": decision_payload,
        "run_receipt.json": run_receipt,
    }
    published_models: dict[str, bytes] = {}
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
                "model_manifest.json": model_manifest,
            }
        )
        published_models = training_result["model_payloads"]
    output_identities = publish_artifact_bundle(
        RESULT_DIR,
        csv_frames=csv_frames,
        json_payloads=json_payloads,
        text_payloads={"report.md": report},
        model_payloads=published_models,
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
