from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from full_market_one_slot_features import (
    MODEL_FEATURES,
    PAIRWISE_FEATURES,
    RAW_FEATURES,
    FeatureBundle,
    FeatureConfig,
    FeatureError,
    audit_trailing_coverage,
    build_feature_bundle,
    build_product_return_history,
    compute_curve_features,
)


LINE_ID = "futures_trend_xgboost_pit_full_market_one_slot_ensemble"
PASS_DECISION = (
    "stage001_full_market_feature_contract_pass_allow_label_proxy_preregistration_only"
)
FAIL_DECISION = "stage001_full_market_feature_contract_fail_close_no_labels"

LINE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
SOURCE_DIR = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_full_market_source_rebuild/"
    "artifacts/stage002_endofday_source_rebuild"
)
FORMAL_RANKING = (
    REPO_ROOT
    / "research/lines/futures_trend_ai_xgboost_ensemble/"
    "artifacts/stage009_formal_full_ranking_recovery/formal_full_ranking.csv"
)
DEFAULT_OUTPUT_DIR = LINE_DIR / "artifacts/stage001_feature_qualification"

DEFAULT_INPUT_PATHS = {
    "source_manifest": SOURCE_DIR / "artifact_manifest.json",
    "bars": SOURCE_DIR / "normalised_daily_bars.csv.gz",
    "mapping": SOURCE_DIR / "pit_main_contract_mapping.csv.gz",
    "catalog": SOURCE_DIR / "asof_contract_catalog.csv.gz",
    "metadata": SOURCE_DIR / "invariant_product_metadata.csv",
    "coverage": SOURCE_DIR / "coverage_by_eval_product.csv.gz",
    "monthly": SOURCE_DIR / "monthly_coverage.csv",
    "source_summary": SOURCE_DIR / "stage002_summary.json",
    "formal_ranking": FORMAL_RANKING,
}
DEFAULT_EXPECTED_SHA256 = {
    "source_manifest": "e3894cd20114182e9b3a9e986ed5e0310fe264de06368b5efe1b5efb6903681a",
    "bars": "f2cf98dbfde2e18031697d598c3147c0ee8f15d3feb6ab935b92bc44a919ece4",
    "mapping": "1b9059e42161a71aaacd7d6367cbe4c7cd95eb944a1f463baf360aa038fec34d",
    "catalog": "c733e5d85bab4349efb9bd25e2afdd689562718ffd608bff9a4f11964ab13bfc",
    "metadata": "23141510dc4b82f397db07f61d5bfce0cfe0621858f135f49c3044360dd46174",
    "coverage": "6b8a55f44aa9422653fd01eea667fcede59bedab9b2ef8e6cceba31e636cb30d",
    "monthly": "dbd394954d92ef041dcc00f88c6ed90df62e7b2b3578fb6cabaafb848d1c2047",
    "source_summary": "67dcdb174bf7e253e100138eff1ec0b644c6a7cc68c0806f71aff10c66f00939",
    "formal_ranking": "b2cb417b6c57a7679ae43a1e564c1e79683ca9644b3434cb6a3bfc9e039fcfc0",
}

FORBIDDEN_LABEL_COLUMNS = {
    "joint_win",
    "return_delta",
    "drawdown_improvement",
    "future_return",
    "future_drawdown",
    "label",
    "target",
}


class Stage001Error(RuntimeError):
    pass


@dataclass(frozen=True)
class ExpectedCounts:
    action_months: int = 48
    feature_rows: int = 1819
    anchor_rows: int = 48
    challenger_rows: int = 1771
    label_months: int = 47
    label_tasks: int = 1729
    active_folds: int = 23
    effect_evaluable_folds: int = 22
    inference_only_folds: int = 1
    minimum_train_months: int = 24
    maximum_train_months: int = 46
    first_fold: str | None = "2024-06-28"
    last_fold: str | None = "2026-06-30"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_line_local_output(line_dir: Path, candidate: Path) -> Path:
    root = Path(line_dir).resolve()
    path = Path(candidate).resolve()
    if path == root or not path.is_relative_to(root):
        raise Stage001Error(f"output_outside_line:{path}")
    return path


def verify_input_identities(
    input_paths: Mapping[str, Path],
    expected_sha256: Mapping[str, str],
) -> dict[str, dict[str, Any]]:
    if set(input_paths) != set(expected_sha256):
        raise Stage001Error("input_identity_key_mismatch")
    identities: dict[str, dict[str, Any]] = {}
    for name in sorted(input_paths):
        path = Path(input_paths[name]).resolve()
        if not path.is_file():
            raise Stage001Error(f"input_missing:{name}:{path}")
        actual = sha256_file(path)
        if actual != expected_sha256[name]:
            raise Stage001Error(f"input_sha256_drift:{name}")
        identities[name] = {
            "path": str(path),
            "sha256": actual,
            "size": path.stat().st_size,
        }
    return identities


def _load_inputs(input_paths: Mapping[str, Path]) -> dict[str, Any]:
    return {
        "source_manifest": json.loads(
            Path(input_paths["source_manifest"]).read_text(encoding="utf-8")
        ),
        "bars": pd.read_csv(input_paths["bars"], encoding="utf-8-sig"),
        "mapping": pd.read_csv(input_paths["mapping"], encoding="utf-8-sig"),
        "catalog": pd.read_csv(input_paths["catalog"], encoding="utf-8-sig"),
        "metadata": pd.read_csv(input_paths["metadata"], encoding="utf-8-sig"),
        "coverage": pd.read_csv(input_paths["coverage"], encoding="utf-8-sig"),
        "monthly": pd.read_csv(input_paths["monthly"], encoding="utf-8-sig"),
        "source_summary": json.loads(
            Path(input_paths["source_summary"]).read_text(encoding="utf-8")
        ),
        "formal_ranking": pd.read_csv(
            input_paths["formal_ranking"], encoding="utf-8-sig"
        ),
    }


def _validate_frozen_inputs(inputs: Mapping[str, Any]) -> None:
    summary = inputs["source_summary"]
    if not summary.get("all_gates_passed"):
        raise Stage001Error("source_summary_not_passed")
    if summary.get("label_values_read") is not False:
        raise Stage001Error("source_summary_label_read")
    if summary.get("model_fit_count") != 0 or summary.get("model_predict_count") != 0:
        raise Stage001Error("source_summary_model_operation")

    manifest = inputs["source_manifest"]
    artifacts = manifest.get("artifacts", {})
    source_artifact_names = {
        "normalised_bars": "bars",
        "mapping": "mapping",
        "catalog": "catalog",
        "metadata": "metadata",
        "coverage": "coverage",
        "monthly_coverage": "monthly",
        "summary": "source_summary",
    }
    for artifact_name, input_name in source_artifact_names.items():
        identity = artifacts.get(artifact_name, {})
        if identity.get("sha256") != DEFAULT_EXPECTED_SHA256[input_name]:
            raise Stage001Error(f"source_manifest_artifact_drift:{artifact_name}")

    coverage = inputs["coverage"].copy()
    monthly = inputs["monthly"].copy()
    ranking = inputs["formal_ranking"].copy()
    metadata = inputs["metadata"].copy()
    for frame in [coverage, monthly, ranking]:
        frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="raise").dt.normalize()
    action_dates = set(monthly.loc[monthly["action_ready"].astype(bool), "eval_date"])
    action_coverage = coverage[coverage["eval_date"].isin(action_dates)]
    anchors = action_coverage[
        action_coverage["is_formal_replacement_product"].astype(bool)
    ][["eval_date", "product_vt_symbol"]].sort_values("eval_date")
    rank10 = ranking[
        ranking["eval_date"].isin(action_dates)
        & pd.to_numeric(ranking["score_rank"], errors="coerce").eq(10)
    ][["eval_date", "product_vt_symbol"]].sort_values("eval_date")
    if len(anchors) != len(action_dates) or len(rank10) != len(action_dates):
        raise Stage001Error("formal_rank10_month_count_mismatch")
    if anchors.reset_index(drop=True).to_dict("records") != rank10.reset_index(
        drop=True
    ).to_dict("records"):
        raise Stage001Error("formal_rank10_identity_mismatch")

    eligible_products = set(
        action_coverage.loc[
            action_coverage["eligible"].astype(bool), "product_vt_symbol"
        ].astype(str)
    )
    metadata_products = set(metadata["vt_symbol"].astype(str))
    if not eligible_products.issubset(metadata_products):
        raise Stage001Error("eligible_product_missing_metadata")
    if (
        action_coverage["fallback_used"].astype(bool).any()
        or pd.to_numeric(
            action_coverage["future_mapping_rows_used"], errors="coerce"
        ).fillna(1).sum()
        != 0
        or pd.to_numeric(
            action_coverage["future_bar_rows_used"], errors="coerce"
        ).fillna(1).sum()
        != 0
        or pd.to_numeric(action_coverage["label_rows_read"], errors="coerce")
        .fillna(1)
        .sum()
        != 0
    ):
        raise Stage001Error("source_pit_counter_nonzero")


def _safe_bool(value: Any) -> bool:
    return bool(value) if value is not pd.NA else False


def _build_action_set(inputs: Mapping[str, Any]) -> pd.DataFrame:
    coverage = inputs["coverage"].copy()
    monthly = inputs["monthly"].copy()
    coverage["eval_date"] = pd.to_datetime(
        coverage["eval_date"], errors="raise"
    ).dt.normalize()
    monthly["eval_date"] = pd.to_datetime(
        monthly["eval_date"], errors="raise"
    ).dt.normalize()
    action_dates = monthly.loc[monthly["action_ready"].astype(bool), ["eval_date"]]
    action_set = coverage.merge(action_dates, on="eval_date", how="inner")
    selected = action_set["eligible"].astype(bool) & (
        action_set["is_formal_replacement_product"].astype(bool)
        | action_set["is_pool_outside_challenger"].astype(bool)
    )
    return action_set.loc[
        selected,
        [
            "eval_date",
            "product_vt_symbol",
            "is_formal_replacement_product",
            "is_pool_outside_challenger",
        ],
    ].reset_index(drop=True)


def _coverage_failure_summary(
    failures: pd.DataFrame,
    action_set: pd.DataFrame,
    *,
    curve_rows: int,
    curve_error: str | None,
    expected_counts: ExpectedCounts,
    config: FeatureConfig,
    identities_before: Mapping[str, Any],
    identities_after: Mapping[str, Any],
) -> dict[str, Any]:
    action_months = int(action_set["eval_date"].nunique())
    anchor_rows = int(
        action_set["is_formal_replacement_product"].astype(bool).sum()
    )
    challenger_rows = int(
        action_set["is_pool_outside_challenger"].astype(bool).sum()
    )
    failure_types = {
        str(name): int(count)
        for name, count in failures["issue"].value_counts().sort_index().items()
    }
    failed_action_rows = int(
        failures[["eval_date", "product_vt_symbol"]].drop_duplicates().shape[0]
    )
    gates = {
        "input_identity_stable": identities_before == identities_after,
        "action_month_count_exact": action_months == expected_counts.action_months,
        "action_row_count_exact": len(action_set) == expected_counts.feature_rows,
        "anchor_row_count_exact": anchor_rows == expected_counts.anchor_rows,
        "challenger_row_count_exact": challenger_rows
        == expected_counts.challenger_rows,
        "trailing_window_coverage_pass": failures.empty,
        "curve_feature_coverage_pass": curve_error is None
        and curve_rows == expected_counts.feature_rows,
        "label_values_read_zero": True,
        "model_operations_zero": True,
        "backtest_order_production_operations_zero": True,
    }
    return {
        "line_id": LINE_ID,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "evidence_scope": "label_free_pit_feature_qualification_failure_only",
        "decision": FAIL_DECISION,
        "all_gates_passed": False,
        "gates": gates,
        "expected_counts": asdict(expected_counts),
        "action_months": action_months,
        "action_rows": int(len(action_set)),
        "feature_rows": 0,
        "raw_feature_rows": 0,
        "anchor_rows": anchor_rows,
        "challenger_rows": challenger_rows,
        "curve_rows_qualified": int(curve_rows),
        "curve_error": curve_error,
        "qualification_failure_count": int(len(failures)),
        "failed_action_rows": failed_action_rows,
        "failure_types": failure_types,
        "label_months": 0,
        "label_tasks": 0,
        "active_folds": 0,
        "effect_evaluable_folds": 0,
        "inference_only_folds": 0,
        "minimum_train_months": 0,
        "maximum_train_months": 0,
        "label_columns_read": [],
        "label_values_read": False,
        "future_mapping_rows_used": 0,
        "future_bar_rows_used": 0,
        "future_label_rows_used": 0,
        "fallback_rows": 0,
        "model_fit_count": 0,
        "model_predict_count": 0,
        "strategy_backtest_runs": 0,
        "ctp_connected": False,
        "order_api_called_count": 0,
        "production_files_written": 0,
        "sealed_holdout_rows": 0,
        "independent_reviewer_required": False,
        "independent_reviewer_reason": "no_backtest_results_produced",
        "input_identity_stable": identities_before == identities_after,
        "input_identities_before": dict(identities_before),
        "input_identities_after": dict(identities_after),
        "feature_config": asdict(config),
        "implementation_identities": {
            "feature_core": sha256_file(
                LINE_DIR / "tools/full_market_one_slot_features.py"
            ),
            "stage001_runner": sha256_file(Path(__file__)),
        },
    }


def assess_bundle(
    bundle: FeatureBundle,
    *,
    expected_counts: ExpectedCounts = ExpectedCounts(),
) -> dict[str, Any]:
    raw = bundle.raw_features
    model = bundle.model_features
    labels = bundle.label_plan
    folds = bundle.fold_plan
    diagnostics = bundle.diagnostics
    anchors = model[model["role"].eq("formal_rank10")]
    challengers = model[model["role"].eq("challenger")]

    action_months = int(model["eval_date"].nunique())
    label_months = int(labels["eval_date"].nunique()) if not labels.empty else 0
    effect_folds = (
        int(folds["effect_evaluable"].astype(bool).sum()) if not folds.empty else 0
    )
    inference_folds = (
        int(folds["inference_only"].astype(bool).sum()) if not folds.empty else 0
    )
    train_month_min = (
        int(pd.to_numeric(folds["train_month_count"]).min()) if not folds.empty else 0
    )
    train_month_max = (
        int(pd.to_numeric(folds["train_month_count"]).max()) if not folds.empty else 0
    )

    raw_finite = (
        set(RAW_FEATURES).issubset(raw.columns)
        and np.isfinite(raw[RAW_FEATURES].to_numpy(float)).all()
    )
    model_finite = (
        set(MODEL_FEATURES).issubset(model.columns)
        and np.isfinite(model[MODEL_FEATURES].to_numpy(float)).all()
    )
    anchor_zero = (
        set(PAIRWISE_FEATURES).issubset(anchors.columns)
        and np.array_equal(
            anchors[PAIRWISE_FEATURES].to_numpy(float),
            np.zeros((len(anchors), len(PAIRWISE_FEATURES))),
        )
    )
    future_rows_zero = all(
        column in raw.columns
        and pd.to_numeric(raw[column], errors="coerce").fillna(1).eq(0).all()
        for column in ["future_bar_rows_used", "future_curve_rows_used"]
    )
    source_dates_pit = all(
        column in raw.columns
        and pd.to_datetime(raw[column], errors="coerce")
        .le(pd.to_datetime(raw["eval_date"], errors="coerce"))
        .all()
        for column in ["maximum_source_date_used", "maximum_curve_source_date_used"]
    )
    diagnostics_exact = (
        set(diagnostics.get("feature", pd.Series(dtype=str)))
        == set(PAIRWISE_FEATURES)
        and len(diagnostics) == len(PAIRWISE_FEATURES)
        and (
            pd.to_numeric(
                diagnostics.get(
                    "nonzero_cross_section_months", pd.Series(dtype=float)
                ),
                errors="coerce",
            )
            >= pd.to_numeric(
                diagnostics.get(
                    "minimum_required_nonzero_months", pd.Series(dtype=float)
                ),
                errors="coerce",
            )
        ).all()
    )
    label_contract = (
        not FORBIDDEN_LABEL_COLUMNS.intersection(labels.columns)
        and "label_values_read" in labels.columns
        and labels["label_values_read"].eq(False).all()  # noqa: E712
        and "role" in labels.columns
        and labels["role"].eq("challenger").all()
    )
    fold_strict = (
        not folds.empty
        and pd.to_datetime(folds["maximum_train_label_end"], errors="coerce")
        .lt(pd.to_datetime(folds["test_eval_date"], errors="coerce"))
        .all()
        and pd.to_numeric(folds["future_label_rows_used"], errors="coerce")
        .fillna(1)
        .eq(0)
        .all()
        and pd.to_numeric(folds["sealed_holdout_rows"], errors="coerce")
        .fillna(1)
        .eq(0)
        .all()
    )
    first_fold_ok = expected_counts.first_fold is None or (
        not folds.empty
        and pd.Timestamp(folds["test_eval_date"].min())
        == pd.Timestamp(expected_counts.first_fold)
    )
    last_fold_ok = expected_counts.last_fold is None or (
        not folds.empty
        and pd.Timestamp(folds["test_eval_date"].max())
        == pd.Timestamp(expected_counts.last_fold)
    )

    gates = {
        "action_month_count_exact": action_months == expected_counts.action_months,
        "raw_and_model_row_count_exact": len(raw)
        == len(model)
        == expected_counts.feature_rows,
        "anchor_row_count_exact": len(anchors) == expected_counts.anchor_rows,
        "challenger_row_count_exact": len(challengers)
        == expected_counts.challenger_rows,
        "raw_features_finite": bool(raw_finite),
        "model_features_finite": bool(model_finite),
        "anchor_pairwise_exact_zero": bool(anchor_zero),
        "future_rows_zero": bool(future_rows_zero),
        "source_dates_at_or_before_eval": bool(source_dates_pit),
        "cross_section_diagnostics_pass": bool(diagnostics_exact),
        "label_contract_value_free": bool(label_contract),
        "label_month_count_exact": label_months == expected_counts.label_months,
        "label_task_count_exact": len(labels) == expected_counts.label_tasks,
        "active_fold_count_exact": len(folds) == expected_counts.active_folds,
        "effect_fold_count_exact": effect_folds
        == expected_counts.effect_evaluable_folds,
        "inference_fold_count_exact": inference_folds
        == expected_counts.inference_only_folds,
        "train_month_range_exact": train_month_min
        == expected_counts.minimum_train_months
        and train_month_max == expected_counts.maximum_train_months,
        "fold_label_end_strictly_before_test": bool(fold_strict),
        "first_fold_exact": bool(first_fold_ok),
        "last_fold_exact": bool(last_fold_ok),
    }
    all_passed = all(_safe_bool(value) for value in gates.values())
    return {
        "line_id": LINE_ID,
        "evidence_scope": "label_free_pit_feature_and_fold_qualification_only",
        "decision": PASS_DECISION if all_passed else FAIL_DECISION,
        "all_gates_passed": all_passed,
        "gates": gates,
        "expected_counts": asdict(expected_counts),
        "action_months": action_months,
        "feature_rows": int(len(model)),
        "raw_feature_rows": int(len(raw)),
        "anchor_rows": int(len(anchors)),
        "challenger_rows": int(len(challengers)),
        "label_months": label_months,
        "label_tasks": int(len(labels)),
        "active_folds": int(len(folds)),
        "effect_evaluable_folds": effect_folds,
        "inference_only_folds": inference_folds,
        "minimum_train_months": train_month_min,
        "maximum_train_months": train_month_max,
        "label_columns_read": [],
        "label_values_read": False,
        "future_mapping_rows_used": 0,
        "future_bar_rows_used": 0,
        "future_label_rows_used": 0,
        "fallback_rows": 0,
        "model_fit_count": 0,
        "model_predict_count": 0,
        "strategy_backtest_runs": 0,
        "ctp_connected": False,
        "order_api_called_count": 0,
        "production_files_written": 0,
        "sealed_holdout_rows": 0,
        "independent_reviewer_required": False,
        "independent_reviewer_reason": "no_backtest_results_produced",
    }


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    if path.suffix == ".gz":
        frame.to_csv(
            path,
            index=False,
            encoding="utf-8",
            compression={"method": "gzip", "compresslevel": 9, "mtime": 0},
        )
    else:
        frame.to_csv(path, index=False, encoding="utf-8")


def _report(summary: Mapping[str, Any]) -> str:
    gate_lines = "\n".join(
        f"- `{name}`：{'通过' if passed else '失败'}"
        for name, passed in summary["gates"].items()
    )
    return (
        "# Stage001 全市场PIT特征资格审计\n\n"
        f"- 决策：`{summary['decision']}`\n"
        f"- action-ready月份：{summary['action_months']}\n"
        f"- 特征行：{summary['feature_rows']}\n"
        f"- rank10锚点/候选：{summary['anchor_rows']}/{summary['challenger_rows']}\n"
        f"- 标签计划月份/任务：{summary['label_months']}/{summary['label_tasks']}\n"
        f"- active/effect/inference折：{summary['active_folds']}/"
        f"{summary['effect_evaluable_folds']}/{summary['inference_only_folds']}\n"
        "- 标签值、模型拟合、策略回测、CTP、订单和生产写入：全部为0\n\n"
        "## 门禁\n\n"
        f"{gate_lines}\n"
    )


def publish_bundle(
    bundle: FeatureBundle,
    summary: Mapping[str, Any],
    *,
    line_dir: Path,
    final_dir: Path,
    input_identities: Mapping[str, Any],
) -> None:
    final_path = assert_line_local_output(line_dir, final_dir)
    temp_path = final_path.with_name("stage001.tmp")
    assert_line_local_output(line_dir, temp_path)
    if final_path.exists():
        raise Stage001Error(f"final_output_exists:{final_path}")
    if temp_path.exists():
        raise Stage001Error(f"temporary_output_exists:{temp_path}")
    final_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.mkdir()

    artifact_frames = {
        "raw_product_features.csv.gz": bundle.raw_features,
        "model_feature_panel.csv.gz": bundle.model_features,
        "label_plan.csv.gz": bundle.label_plan,
        "fold_plan.csv": bundle.fold_plan,
        "feature_diagnostics.csv": bundle.diagnostics,
    }
    for name, frame in artifact_frames.items():
        _write_csv(frame, temp_path / name)
    _write_json(temp_path / "stage001_summary.json", dict(summary))
    _write_json(temp_path / "input_identities.json", dict(input_identities))
    (temp_path / "report.md").write_text(_report(summary), encoding="utf-8")

    artifact_names = sorted(path.name for path in temp_path.iterdir() if path.is_file())
    manifest = {
        "artifacts": {
            name: {
                "sha256": sha256_file(temp_path / name),
                "size": (temp_path / name).stat().st_size,
            }
            for name in artifact_names
        },
        "input_identities": dict(input_identities),
    }
    _write_json(temp_path / "artifact_manifest.json", manifest)
    for name, identity in manifest["artifacts"].items():
        if sha256_file(temp_path / name) != identity["sha256"]:
            raise Stage001Error(f"temporary_manifest_mismatch:{name}")
    os.replace(temp_path, final_path)


def publish_failure_evidence(
    failures: pd.DataFrame,
    summary: Mapping[str, Any],
    *,
    line_dir: Path,
    final_dir: Path,
    input_identities: Mapping[str, Any],
) -> None:
    final_path = assert_line_local_output(line_dir, final_dir)
    temp_path = final_path.with_name("stage001.tmp")
    assert_line_local_output(line_dir, temp_path)
    if final_path.exists():
        raise Stage001Error(f"final_output_exists:{final_path}")
    if temp_path.exists():
        raise Stage001Error(f"temporary_output_exists:{temp_path}")
    final_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.mkdir()

    _write_csv(failures, temp_path / "qualification_failures.csv")
    _write_json(temp_path / "stage001_summary.json", dict(summary))
    _write_json(temp_path / "input_identities.json", dict(input_identities))
    (temp_path / "report.md").write_text(_report(summary), encoding="utf-8")
    artifact_names = sorted(path.name for path in temp_path.iterdir() if path.is_file())
    manifest = {
        "artifacts": {
            name: {
                "sha256": sha256_file(temp_path / name),
                "size": (temp_path / name).stat().st_size,
            }
            for name in artifact_names
        },
        "input_identities": dict(input_identities),
    }
    _write_json(temp_path / "artifact_manifest.json", manifest)
    for name, identity in manifest["artifacts"].items():
        if sha256_file(temp_path / name) != identity["sha256"]:
            raise Stage001Error(f"temporary_manifest_mismatch:{name}")
    os.replace(temp_path, final_path)


def verify_published_bundle(
    final_dir: Path,
    *,
    verify_inputs: bool = False,
) -> dict[str, Any]:
    final_path = Path(final_dir).resolve()
    manifest_path = final_path / "artifact_manifest.json"
    errors: list[str] = []
    if not manifest_path.is_file():
        return {"verified": False, "errors": ["manifest_missing"]}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, expected in manifest.get("artifacts", {}).items():
        path = final_path / name
        if not path.is_file():
            errors.append(f"artifact_missing:{name}")
            continue
        if path.stat().st_size != expected.get("size"):
            errors.append(f"artifact_size_mismatch:{name}")
        if sha256_file(path) != expected.get("sha256"):
            errors.append(f"artifact_sha256_mismatch:{name}")
    if verify_inputs:
        for name, expected in manifest.get("input_identities", {}).items():
            path = Path(expected.get("path", ""))
            if not path.is_file():
                errors.append(f"input_missing:{name}")
                continue
            if path.stat().st_size != expected.get("size"):
                errors.append(f"input_size_mismatch:{name}")
            if sha256_file(path) != expected.get("sha256"):
                errors.append(f"input_sha256_mismatch:{name}")
    return {
        "verified": not errors,
        "errors": errors,
        "artifact_count": len(manifest.get("artifacts", {})),
        "input_count": len(manifest.get("input_identities", {})),
    }


def run_stage001(
    *,
    authorized: bool,
    line_dir: Path = LINE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    input_paths: Mapping[str, Path] = DEFAULT_INPUT_PATHS,
    expected_sha256: Mapping[str, str] = DEFAULT_EXPECTED_SHA256,
    expected_counts: ExpectedCounts = ExpectedCounts(),
    config: FeatureConfig = FeatureConfig(),
) -> dict[str, Any]:
    if not authorized:
        raise Stage001Error("authorization_required")
    final_path = assert_line_local_output(line_dir, output_dir)
    if final_path.exists():
        raise Stage001Error(f"final_output_exists:{final_path}")
    identities_before = verify_input_identities(input_paths, expected_sha256)
    inputs = _load_inputs(input_paths)
    _validate_frozen_inputs(inputs)
    action_set = _build_action_set(inputs)
    action_rows = action_set[["eval_date", "product_vt_symbol"]]
    history = build_product_return_history(inputs["mapping"], inputs["bars"])
    coverage_failures = audit_trailing_coverage(
        history,
        action_rows,
        config=config,
    )
    if not coverage_failures.empty:
        curve_rows = 0
        curve_error: str | None = None
        try:
            curve_rows = len(
                compute_curve_features(inputs["bars"], inputs["catalog"], action_rows)
            )
        except FeatureError as error:
            curve_error = str(error)
            curve_failure = pd.DataFrame(
                [
                    {
                        "eval_date": pd.NaT,
                        "product_vt_symbol": "",
                        "issue": "curve_feature_qualification_error",
                        "source_column": "curve",
                        "window": 0,
                        "available_count": 0,
                        "valid_count": 0,
                        "required_count": 1,
                        "detail": curve_error,
                    }
                ]
            )
            coverage_failures = pd.concat(
                [coverage_failures, curve_failure], ignore_index=True, sort=False
            )
        identities_after = verify_input_identities(input_paths, expected_sha256)
        if identities_before != identities_after:
            raise Stage001Error("input_identity_changed_during_run")
        summary = _coverage_failure_summary(
            coverage_failures,
            action_set,
            curve_rows=curve_rows,
            curve_error=curve_error,
            expected_counts=expected_counts,
            config=config,
            identities_before=identities_before,
            identities_after=identities_after,
        )
        publish_failure_evidence(
            coverage_failures,
            summary,
            line_dir=line_dir,
            final_dir=final_path,
            input_identities=identities_after,
        )
        verification = verify_published_bundle(final_path, verify_inputs=True)
        if not verification["verified"]:
            raise Stage001Error(
                "published_bundle_verification_failed:"
                + ",".join(verification["errors"])
            )
        return summary
    bundle = build_feature_bundle(
        inputs["coverage"],
        inputs["monthly"],
        inputs["mapping"],
        inputs["bars"],
        inputs["catalog"],
        config=config,
    )
    summary = assess_bundle(bundle, expected_counts=expected_counts)
    identities_after = verify_input_identities(input_paths, expected_sha256)
    if identities_before != identities_after:
        raise Stage001Error("input_identity_changed_during_run")
    summary.update(
        {
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "input_identity_stable": True,
            "input_identities_before": identities_before,
            "input_identities_after": identities_after,
            "feature_config": asdict(config),
            "implementation_identities": {
                "feature_core": sha256_file(
                    LINE_DIR / "tools/full_market_one_slot_features.py"
                ),
                "stage001_runner": sha256_file(Path(__file__)),
            },
        }
    )
    publish_bundle(
        bundle,
        summary,
        line_dir=line_dir,
        final_dir=final_path,
        input_identities=identities_after,
    )
    verification = verify_published_bundle(final_path, verify_inputs=True)
    if not verification["verified"]:
        raise Stage001Error(
            "published_bundle_verification_failed:" + ",".join(verification["errors"])
        )
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage001 label-free feature audit")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--authorized-feature-audit", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.verify_only:
        result = verify_published_bundle(DEFAULT_OUTPUT_DIR, verify_inputs=True)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["verified"] else 1
    summary = run_stage001(authorized=args.authorized_feature_audit)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["all_gates_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
