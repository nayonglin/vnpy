from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from daily_ranker_contract import (
    LIQUIDITY_FEATURES,
    MODEL_FEATURES,
    RAW_FEATURES,
    ContractError,
    build_base_query_panel,
    build_contract_bar_table,
    build_formal_scoring_plan,
    build_label_plan,
    build_mapped_product_history,
    build_purged_fold_plan,
    build_ranked_model_features,
    compute_raw_features,
)


LINE_ID = "futures_trend_xgboost_pit_full_market_daily_ranker"
PASS_DECISION = (
    "stage001_daily_ranker_contract_pass_allow_stage002_preregistration_only"
)
FAIL_DECISION = "stage001_daily_ranker_contract_fail_close_no_labels"

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
DEFAULT_OUTPUT_DIR = LINE_DIR / "artifacts/stage001_daily_ranker_contract"

DEFAULT_INPUT_PATHS = {
    "source_manifest": SOURCE_DIR / "artifact_manifest.json",
    "source_summary": SOURCE_DIR / "stage002_summary.json",
    "bars": SOURCE_DIR / "normalised_daily_bars.csv.gz",
    "mapping": SOURCE_DIR / "pit_main_contract_mapping.csv.gz",
    "catalog": SOURCE_DIR / "asof_contract_catalog.csv.gz",
    "metadata": SOURCE_DIR / "invariant_product_metadata.csv",
    "coverage": SOURCE_DIR / "coverage_by_eval_product.csv.gz",
    "monthly": SOURCE_DIR / "monthly_coverage.csv",
    "formal_ranking": FORMAL_RANKING,
}
DEFAULT_EXPECTED_SHA256 = {
    "source_manifest": "e3894cd20114182e9b3a9e986ed5e0310fe264de06368b5efe1b5efb6903681a",
    "source_summary": "67dcdb174bf7e253e100138eff1ec0b644c6a7cc68c0806f71aff10c66f00939",
    "bars": "f2cf98dbfde2e18031697d598c3147c0ee8f15d3feb6ab935b92bc44a919ece4",
    "mapping": "1b9059e42161a71aaacd7d6367cbe4c7cd95eb944a1f463baf360aa038fec34d",
    "catalog": "c733e5d85bab4349efb9bd25e2afdd689562718ffd608bff9a4f11964ab13bfc",
    "metadata": "23141510dc4b82f397db07f61d5bfce0cfe0621858f135f49c3044360dd46174",
    "coverage": "6b8a55f44aa9422653fd01eea667fcede59bedab9b2ef8e6cceba31e636cb30d",
    "monthly": "dbd394954d92ef041dcc00f88c6ed90df62e7b2b3578fb6cabaafb848d1c2047",
    "formal_ranking": "b2cb417b6c57a7679ae43a1e564c1e79683ca9644b3434cb6a3bfc9e039fcfc0",
}

FORBIDDEN_LABEL_TOKENS = (
    "close",
    "return",
    "target",
    "relevance",
    "pnl",
    "score",
)
FORBIDDEN_MODEL_FEATURE_TOKENS = (
    "product",
    "exchange",
    "year",
    "month",
    "formal",
    "future",
    "label",
    "target",
    "return",
    "score",
)


class Stage001Error(RuntimeError):
    pass


@dataclass(frozen=True)
class ExpectedCounts:
    base_query_count: int = 1067
    base_row_count: int = 57528
    base_width_min: int = 49
    base_width_median: float = 53.0
    base_width_max: int = 61
    first_query_date: str = "2022-01-28"
    last_query_date: str = "2026-06-30"
    raw_feature_count: int = 17
    model_feature_count: int = 19
    volume_ratio_missing: int = 420
    open_interest_ratio_missing: int = 80
    minimum_nonzero_cross_section_qids: int = 1000
    label_query_count: int = 1046
    label_row_count: int = 52484
    label_width_min: int = 30
    label_width_median: float = 50.0
    label_width_max: int = 60
    rejected_label_rows: int = 5044
    action_months: int = 48
    formal_anchor_rows: int = 48
    challenger_rows: int = 1771
    minimum_challengers_per_month: int = 34
    fold_count: int = 37
    effect_evaluable_folds: int = 36
    inference_only_folds: int = 1
    minimum_train_qids: int = 261
    maximum_train_qids: int = 1045
    first_fold: str = "2023-03-31"
    last_fold: str = "2026-06-30"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_input_identities(
    input_paths: Mapping[str, Path] = DEFAULT_INPUT_PATHS,
    expected_sha256: Mapping[str, str] = DEFAULT_EXPECTED_SHA256,
) -> dict[str, dict[str, object]]:
    if set(input_paths) != set(expected_sha256):
        raise Stage001Error("input_identity_key_mismatch")
    identities: dict[str, dict[str, object]] = {}
    for name in sorted(input_paths):
        path = Path(input_paths[name]).resolve()
        if not path.is_file():
            raise Stage001Error(f"input_missing:{name}:{path}")
        actual_sha256 = sha256_file(path)
        if actual_sha256 != expected_sha256[name]:
            raise Stage001Error(f"input_sha256_drift:{name}")
        stat = path.stat()
        identities[name] = {
            "path": str(path),
            "sha256": actual_sha256,
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
        }
    return identities


def assert_line_local_output(line_dir: Path, candidate: Path) -> Path:
    root = Path(line_dir).resolve()
    path = Path(candidate).resolve()
    if path == root or not path.is_relative_to(root):
        raise Stage001Error(f"output_outside_line:{path}")
    return path


def _same(value: object, expected: object) -> bool:
    if isinstance(expected, float):
        try:
            return bool(np.isclose(float(value), expected, rtol=0.0, atol=1e-12))
        except (TypeError, ValueError):
            return False
    return value == expected


def assess_gates(
    observed: Mapping[str, object],
    *,
    expected_counts: ExpectedCounts = ExpectedCounts(),
) -> dict[str, object]:
    expected = asdict(expected_counts)
    input_identity_gate = all(
        bool(observed.get(field, False))
        for field in (
            "source_manifest_valid",
            "formal_rank10_identity_valid",
            "input_identity_stable",
        )
    )
    query_gate = all(
        _same(observed.get(field), expected[field])
        for field in (
            "base_query_count",
            "base_row_count",
            "base_width_min",
            "base_width_median",
            "base_width_max",
            "first_query_date",
            "last_query_date",
        )
    )
    feature_gate = all(
        [
            _same(observed.get("raw_feature_count"), expected["raw_feature_count"]),
            _same(
                observed.get("model_feature_count"),
                expected["model_feature_count"],
            ),
            int(observed.get("unexpected_nonfinite_feature_count", -1)) == 0,
            _same(
                observed.get("volume_ratio_missing"),
                expected["volume_ratio_missing"],
            ),
            _same(
                observed.get("open_interest_ratio_missing"),
                expected["open_interest_ratio_missing"],
            ),
            int(observed.get("source_date_violation_count", -1)) == 0,
            int(observed.get("future_feature_rows_used", -1)) == 0,
            int(observed.get("minimum_nonzero_cross_section_qids", -1))
            >= expected_counts.minimum_nonzero_cross_section_qids,
            int(observed.get("missing_flag_mismatch_count", -1)) == 0,
            int(observed.get("forbidden_model_feature_count", -1)) == 0,
        ]
    )
    label_plan_gate = all(
        [
            _same(
                observed.get("label_query_count"), expected["label_query_count"]
            ),
            _same(observed.get("label_row_count"), expected["label_row_count"]),
            _same(observed.get("label_width_min"), expected["label_width_min"]),
            _same(
                observed.get("label_width_median"),
                expected["label_width_median"],
            ),
            _same(observed.get("label_width_max"), expected["label_width_max"]),
            _same(
                observed.get("rejected_label_rows"),
                expected["rejected_label_rows"],
            ),
            int(observed.get("label_forbidden_column_count", -1)) == 0,
            int(observed.get("label_identity_violation_count", -1)) == 0,
        ]
    )
    formal_scoring_fold_gate = all(
        [
            _same(observed.get("action_months"), expected["action_months"]),
            _same(
                observed.get("formal_anchor_rows"),
                expected["formal_anchor_rows"],
            ),
            _same(observed.get("challenger_rows"), expected["challenger_rows"]),
            int(observed.get("minimum_challengers_per_month", -1))
            >= expected_counts.minimum_challengers_per_month,
            int(observed.get("formal_month_violation_count", -1)) == 0,
            _same(observed.get("fold_count"), expected["fold_count"]),
            _same(
                observed.get("effect_evaluable_folds"),
                expected["effect_evaluable_folds"],
            ),
            _same(
                observed.get("inference_only_folds"),
                expected["inference_only_folds"],
            ),
            _same(
                observed.get("minimum_train_qids"), expected["minimum_train_qids"]
            ),
            _same(
                observed.get("maximum_train_qids"), expected["maximum_train_qids"]
            ),
            _same(observed.get("first_fold"), expected["first_fold"]),
            _same(observed.get("last_fold"), expected["last_fold"]),
            int(observed.get("future_train_qid_count", -1)) == 0,
            int(observed.get("future_label_rows_used", -1)) == 0,
            int(observed.get("sealed_holdout_rows", -1)) == 0,
        ]
    )
    zero_side_effect_gate = all(
        int(observed.get(field, -1)) == 0
        for field in (
            "future_close_value_reads",
            "future_return_calculations",
            "label_value_reads",
            "model_fit_count",
            "model_predict_count",
            "strategy_backtest_runs",
            "ctp_connection_count",
            "order_api_called_count",
            "production_files_written",
        )
    )
    gates = {
        "input_identity_gate": bool(input_identity_gate),
        "query_gate": bool(query_gate),
        "feature_gate": bool(feature_gate),
        "label_plan_gate": bool(label_plan_gate),
        "formal_scoring_fold_gate": bool(formal_scoring_fold_gate),
        "zero_side_effect_gate": bool(zero_side_effect_gate),
    }
    all_passed = all(gates.values())
    return {
        **dict(observed),
        "expected_counts": expected,
        "gates": gates,
        "all_gates_passed": all_passed,
        "decision": PASS_DECISION if all_passed else FAIL_DECISION,
    }


def _write_json(path: Path, value: object) -> None:
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


def publish_bundle(
    frames: Mapping[str, pd.DataFrame],
    documents: Mapping[str, object],
    *,
    line_dir: Path,
    final_dir: Path,
    input_identities: Mapping[str, object],
) -> None:
    final_path = assert_line_local_output(line_dir, final_dir)
    if final_path.exists():
        raise Stage001Error(f"final_output_exists:{final_path}")
    final_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = final_path.parent / f".stage001.tmp.{uuid.uuid4().hex}"
    assert_line_local_output(line_dir, temp_path)
    temp_path.mkdir()
    try:
        names = set(frames).union(documents)
        if len(names) != len(frames) + len(documents):
            raise Stage001Error("duplicate_output_name")
        for name, frame in frames.items():
            if not name.endswith((".csv", ".csv.gz")):
                raise Stage001Error(f"invalid_frame_output_name:{name}")
            _write_csv(frame, temp_path / name)
        for name, value in documents.items():
            path = temp_path / name
            if name.endswith(".json"):
                _write_json(path, value)
            elif name.endswith(".md") and isinstance(value, str):
                path.write_text(value, encoding="utf-8")
            else:
                raise Stage001Error(f"invalid_document_output:{name}")
        artifact_names = sorted(path.name for path in temp_path.iterdir())
        manifest = {
            "artifacts": {
                name: {
                    "sha256": sha256_file(temp_path / name),
                    "size": int((temp_path / name).stat().st_size),
                }
                for name in artifact_names
            },
            "input_identities": dict(input_identities),
        }
        _write_json(temp_path / "artifact_manifest.json", manifest)
        verification = verify_published_bundle(temp_path)
        if not verification["verified"]:
            raise Stage001Error(
                "temporary_manifest_verification_failed:"
                + ",".join(verification["errors"])
            )
        os.replace(temp_path, final_path)
    except Exception:
        shutil.rmtree(temp_path, ignore_errors=True)
        raise


def verify_published_bundle(
    final_dir: Path,
    *,
    verify_inputs: bool = False,
) -> dict[str, object]:
    final_path = Path(final_dir).resolve()
    manifest_path = final_path / "artifact_manifest.json"
    if not manifest_path.is_file():
        return {"verified": False, "errors": ["manifest_missing"]}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    artifacts = manifest.get("artifacts", {})
    expected_files = set(artifacts).union({"artifact_manifest.json"})
    actual_files = {path.name for path in final_path.iterdir() if path.is_file()}
    for extra in sorted(actual_files.difference(expected_files)):
        errors.append(f"unmanifested_artifact:{extra}")
    for missing in sorted(expected_files.difference(actual_files)):
        errors.append(f"artifact_missing:{missing}")
    for name, expected in artifacts.items():
        path = final_path / name
        if not path.is_file():
            continue
        if path.stat().st_size != expected.get("size"):
            errors.append(f"artifact_size_mismatch:{name}")
        if sha256_file(path) != expected.get("sha256"):
            errors.append(f"artifact_sha256_mismatch:{name}")
    if verify_inputs:
        for name, expected in manifest.get("input_identities", {}).items():
            path_text = expected.get("path")
            if not path_text:
                errors.append(f"input_path_missing:{name}")
                continue
            path = Path(path_text)
            if not path.is_file():
                errors.append(f"input_missing:{name}")
                continue
            stat = path.stat()
            if stat.st_size != expected.get("size"):
                errors.append(f"input_size_mismatch:{name}")
            if stat.st_mtime_ns != expected.get("mtime_ns"):
                errors.append(f"input_mtime_mismatch:{name}")
            if sha256_file(path) != expected.get("sha256"):
                errors.append(f"input_sha256_mismatch:{name}")
    return {
        "verified": not errors,
        "errors": errors,
        "artifact_count": len(artifacts),
        "input_count": len(manifest.get("input_identities", {})),
    }


def _load_inputs(input_paths: Mapping[str, Path]) -> dict[str, object]:
    return {
        "source_manifest": json.loads(
            Path(input_paths["source_manifest"]).read_text(encoding="utf-8")
        ),
        "source_summary": json.loads(
            Path(input_paths["source_summary"]).read_text(encoding="utf-8")
        ),
        "bars": pd.read_csv(input_paths["bars"], encoding="utf-8-sig"),
        "mapping": pd.read_csv(input_paths["mapping"], encoding="utf-8-sig"),
        "catalog": pd.read_csv(input_paths["catalog"], encoding="utf-8-sig"),
        "metadata": pd.read_csv(input_paths["metadata"], encoding="utf-8-sig"),
        "coverage": pd.read_csv(
            input_paths["coverage"],
            encoding="utf-8-sig",
            usecols=[
                "eval_date",
                "product_vt_symbol",
                "eligible",
                "is_formal_replacement_product",
                "is_pool_outside_challenger",
                "fallback_used",
                "future_mapping_rows_used",
                "future_bar_rows_used",
                "label_rows_read",
            ],
        ),
        "monthly": pd.read_csv(
            input_paths["monthly"],
            encoding="utf-8-sig",
            usecols=["eval_date", "action_ready"],
        ),
        "formal_ranking": pd.read_csv(
            input_paths["formal_ranking"],
            encoding="utf-8-sig",
            usecols=["eval_date", "product_vt_symbol", "score_rank", "score_type"],
        ),
    }


def _validate_frozen_inputs(inputs: Mapping[str, object]) -> tuple[bool, bool]:
    summary = inputs["source_summary"]
    manifest = inputs["source_manifest"]
    if not isinstance(summary, dict) or not isinstance(manifest, dict):
        raise Stage001Error("source_metadata_invalid")
    if not summary.get("all_gates_passed"):
        raise Stage001Error("source_summary_not_passed")
    for field in (
        "label_values_read",
        "model_fit_count",
        "model_predict_count",
        "strategy_backtest_runs",
        "order_api_called_count",
        "production_files_written",
    ):
        expected = False if field == "label_values_read" else 0
        if summary.get(field) != expected:
            raise Stage001Error(f"source_side_effect_counter_nonzero:{field}")
    source_artifact_names = {
        "normalised_bars": "bars",
        "mapping": "mapping",
        "catalog": "catalog",
        "metadata": "metadata",
        "coverage": "coverage",
        "monthly_coverage": "monthly",
        "summary": "source_summary",
    }
    artifacts = manifest.get("artifacts", {})
    for artifact_name, input_name in source_artifact_names.items():
        if artifacts.get(artifact_name, {}).get("sha256") != DEFAULT_EXPECTED_SHA256[
            input_name
        ]:
            raise Stage001Error(f"source_manifest_artifact_drift:{artifact_name}")

    coverage = inputs["coverage"].copy()
    monthly = inputs["monthly"].copy()
    ranking = inputs["formal_ranking"].copy()
    assert isinstance(coverage, pd.DataFrame)
    assert isinstance(monthly, pd.DataFrame)
    assert isinstance(ranking, pd.DataFrame)
    for frame in (coverage, monthly, ranking):
        frame["eval_date"] = pd.to_datetime(
            frame["eval_date"], errors="raise"
        ).dt.normalize()
    if (
        coverage["fallback_used"].astype(bool).any()
        or pd.to_numeric(coverage["future_mapping_rows_used"], errors="coerce")
        .fillna(1)
        .ne(0)
        .any()
        or pd.to_numeric(coverage["future_bar_rows_used"], errors="coerce")
        .fillna(1)
        .ne(0)
        .any()
        or pd.to_numeric(coverage["label_rows_read"], errors="coerce")
        .fillna(1)
        .ne(0)
        .any()
    ):
        raise Stage001Error("source_pit_counter_nonzero")
    action_dates = set(
        monthly.loc[monthly["action_ready"].astype(bool), "eval_date"]
    )
    anchors = coverage[
        coverage["eval_date"].isin(action_dates)
        & coverage["eligible"].astype(bool)
        & coverage["is_formal_replacement_product"].astype(bool)
    ][["eval_date", "product_vt_symbol"]].sort_values("eval_date")
    rank10 = ranking[
        ranking["eval_date"].isin(action_dates)
        & pd.to_numeric(ranking["score_rank"], errors="coerce").eq(10)
    ][["eval_date", "product_vt_symbol"]].sort_values("eval_date")
    formal_valid = (
        len(anchors) == len(action_dates)
        and len(rank10) == len(action_dates)
        and anchors.reset_index(drop=True).to_dict("records")
        == rank10.reset_index(drop=True).to_dict("records")
    )
    if not formal_valid:
        raise Stage001Error("formal_rank10_identity_mismatch")
    return True, formal_valid


def _group_stats(frame: pd.DataFrame, date_column: str) -> dict[str, object]:
    widths = frame.groupby(date_column, sort=True).size()
    if widths.empty:
        return {
            "query_count": 0,
            "row_count": 0,
            "width_min": 0,
            "width_median": 0.0,
            "width_max": 0,
            "first_date": None,
            "last_date": None,
        }
    return {
        "query_count": int(len(widths)),
        "row_count": int(len(frame)),
        "width_min": int(widths.min()),
        "width_median": float(widths.median()),
        "width_max": int(widths.max()),
        "first_date": pd.Timestamp(widths.index.min()).date().isoformat(),
        "last_date": pd.Timestamp(widths.index.max()).date().isoformat(),
    }


def _build_observed_summary(
    *,
    base_panel: pd.DataFrame,
    raw_features: pd.DataFrame,
    model_features: pd.DataFrame,
    label_plan: pd.DataFrame,
    rejected_label_plan: pd.DataFrame,
    formal_scoring_plan: pd.DataFrame,
    fold_plan: pd.DataFrame,
    source_manifest_valid: bool,
    formal_rank10_identity_valid: bool,
    input_identity_stable: bool,
    mapping_diagnostics: Mapping[str, int],
) -> dict[str, object]:
    base_stats = _group_stats(base_panel, "query_date")
    label_stats = _group_stats(label_plan, "query_date")
    non_liquidity = [
        feature for feature in RAW_FEATURES if feature not in LIQUIDITY_FEATURES
    ]
    unexpected_nonfinite = int(
        (~np.isfinite(raw_features[non_liquidity].to_numpy(float))).sum()
        + (~np.isfinite(model_features[MODEL_FEATURES].to_numpy(float))).sum()
    )
    source_date_violations = 0
    for column in ("maximum_path_source_date", "maximum_curve_source_date"):
        source_date_violations += int(
            pd.to_datetime(raw_features[column], errors="coerce")
            .gt(pd.to_datetime(raw_features["query_date"], errors="coerce"))
            .sum()
        )
    future_feature_rows = int(
        pd.to_numeric(raw_features["future_path_rows_used"], errors="coerce")
        .fillna(1)
        .sum()
        + pd.to_numeric(raw_features["future_curve_rows_used"], errors="coerce")
        .fillna(1)
        .sum()
    )
    nonzero_qids = []
    for feature in (f"{name}_rank" for name in RAW_FEATURES):
        standard_deviation = model_features.groupby("query_date", sort=False)[
            feature
        ].std(ddof=0)
        nonzero_qids.append(int(standard_deviation.gt(0).sum()))
    missing_flag_mismatch = 0
    for raw_name, flag_name in LIQUIDITY_FEATURES.items():
        missing_flag_mismatch += int(
            (
                raw_features[raw_name].isna().to_numpy()
                != model_features[flag_name].astype(bool).to_numpy()
            ).sum()
        )
    forbidden_model_features = sum(
        any(token in feature.lower() for token in FORBIDDEN_MODEL_FEATURE_TOKENS)
        for feature in MODEL_FEATURES
    )
    forbidden_label_columns = sum(
        any(token in column.lower() for token in FORBIDDEN_LABEL_TOKENS)
        for column in label_plan.columns
    )
    label_identity_violations = int(
        label_plan["entry_date"].ge(label_plan["label_end"]).sum()
        + label_plan["label_value_read"].astype(bool).sum()
    )
    role_counts = formal_scoring_plan["role"].value_counts()
    formal_by_month = formal_scoring_plan[
        formal_scoring_plan["role"].eq("formal_rank10")
    ].groupby("test_eval_date").size()
    challengers_by_month = formal_scoring_plan[
        formal_scoring_plan["role"].eq("challenger")
    ].groupby("test_eval_date").size()
    all_months = pd.Index(formal_scoring_plan["test_eval_date"].unique())
    formal_month_violations = int(
        formal_by_month.reindex(all_months, fill_value=0).ne(1).sum()
    )
    future_train = int(
        pd.to_datetime(fold_plan["maximum_train_label_end"], errors="coerce")
        .ge(pd.to_datetime(fold_plan["test_eval_date"], errors="coerce"))
        .sum()
    )
    return {
        "line_id": LINE_ID,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "evidence_scope": "label_free_pit_daily_ranker_contract_only",
        "source_manifest_valid": source_manifest_valid,
        "formal_rank10_identity_valid": formal_rank10_identity_valid,
        "input_identity_stable": input_identity_stable,
        "base_query_count": base_stats["query_count"],
        "base_row_count": base_stats["row_count"],
        "base_width_min": base_stats["width_min"],
        "base_width_median": base_stats["width_median"],
        "base_width_max": base_stats["width_max"],
        "first_query_date": base_stats["first_date"],
        "last_query_date": base_stats["last_date"],
        "raw_feature_count": len(RAW_FEATURES),
        "model_feature_count": len(MODEL_FEATURES),
        "unexpected_nonfinite_feature_count": unexpected_nonfinite,
        "volume_ratio_missing": int(raw_features["volume_ratio_20_60"].isna().sum()),
        "open_interest_ratio_missing": int(
            raw_features["open_interest_ratio_20_60"].isna().sum()
        ),
        "source_date_violation_count": source_date_violations,
        "future_feature_rows_used": future_feature_rows,
        "minimum_nonzero_cross_section_qids": min(nonzero_qids),
        "missing_flag_mismatch_count": missing_flag_mismatch,
        "forbidden_model_feature_count": forbidden_model_features,
        "label_query_count": label_stats["query_count"],
        "label_row_count": label_stats["row_count"],
        "label_width_min": label_stats["width_min"],
        "label_width_median": label_stats["width_median"],
        "label_width_max": label_stats["width_max"],
        "rejected_label_rows": int(len(rejected_label_plan)),
        "label_forbidden_column_count": forbidden_label_columns,
        "label_identity_violation_count": label_identity_violations,
        "action_months": int(formal_scoring_plan["test_eval_date"].nunique()),
        "formal_anchor_rows": int(role_counts.get("formal_rank10", 0)),
        "challenger_rows": int(role_counts.get("challenger", 0)),
        "minimum_challengers_per_month": int(challengers_by_month.min()),
        "formal_month_violation_count": formal_month_violations,
        "fold_count": int(len(fold_plan)),
        "effect_evaluable_folds": int(
            fold_plan["effect_evaluable"].astype(bool).sum()
        ),
        "inference_only_folds": int(fold_plan["inference_only"].astype(bool).sum()),
        "minimum_train_qids": int(fold_plan["train_qid_count"].min()),
        "maximum_train_qids": int(fold_plan["train_qid_count"].max()),
        "first_fold": pd.Timestamp(fold_plan["test_eval_date"].min())
        .date()
        .isoformat(),
        "last_fold": pd.Timestamp(fold_plan["test_eval_date"].max())
        .date()
        .isoformat(),
        "future_train_qid_count": future_train,
        "future_label_rows_used": int(
            pd.to_numeric(fold_plan["future_label_rows_used"], errors="coerce")
            .fillna(1)
            .sum()
        ),
        "sealed_holdout_rows": int(
            pd.to_numeric(fold_plan["sealed_holdout_rows"], errors="coerce")
            .fillna(1)
            .sum()
        ),
        "mapping_rows": int(mapping_diagnostics["mapping_rows"]),
        "resolved_mapping_rows": int(mapping_diagnostics["resolved_mapping_rows"]),
        "unresolved_mapping_rows": int(
            mapping_diagnostics["unresolved_mapping_rows"]
        ),
        "future_close_value_reads": 0,
        "future_return_calculations": 0,
        "label_value_reads": int(label_plan["label_value_read"].astype(bool).sum()),
        "model_fit_count": 0,
        "model_predict_count": 0,
        "strategy_backtest_runs": 0,
        "ctp_connection_count": 0,
        "order_api_called_count": 0,
        "production_files_written": 0,
        "independent_reviewer_required": False,
        "independent_reviewer_reason": "no_backtest_result_produced",
    }


def _feature_contract() -> dict[str, object]:
    return {
        "line_id": LINE_ID,
        "stage": "stage001_daily_ranker_contract",
        "raw_features": RAW_FEATURES,
        "model_features": MODEL_FEATURES,
        "ranking": {"method": "average", "pct": True},
        "liquidity_missing_rank": 0.5,
        "label_plan": {
            "entry_offset_global_trading_days": 1,
            "exit_offset_global_trading_days": 21,
            "fixed_contract": True,
            "label_values_allowed": False,
        },
        "fold": {
            "minimum_train_qids": 252,
            "train_condition": "label_end < test_eval_date",
        },
        "future_model_declaration_only": {
            "model": "XGBRanker",
            "objective": "rank:ndcg",
            "eval_metric": "ndcg@10",
            "training_authorized": False,
        },
    }


def _report(summary: Mapping[str, object]) -> str:
    gate_lines = "\n".join(
        f"- `{name}`：{'通过' if passed else '失败'}"
        for name, passed in summary["gates"].items()
    )
    return (
        "# Stage001 PIT全市场日级排序无标签合同\n\n"
        f"- 决策：`{summary['decision']}`\n"
        f"- 基础query/行：{summary['base_query_count']}/{summary['base_row_count']}\n"
        f"- 标签计划query/行：{summary['label_query_count']}/{summary['label_row_count']}\n"
        f"- action月/fold：{summary['action_months']}/{summary['fold_count']}\n"
        f"- effect/inference：{summary['effect_evaluable_folds']}/"
        f"{summary['inference_only_folds']}\n"
        "- 标签值、未来收益、fit、predict、回测、CTP、订单与生产写入：全部为0\n\n"
        "## 门禁\n\n"
        f"{gate_lines}\n"
    )


def run_stage001(
    *,
    line_dir: Path = LINE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    input_paths: Mapping[str, Path] = DEFAULT_INPUT_PATHS,
    expected_sha256: Mapping[str, str] = DEFAULT_EXPECTED_SHA256,
    expected_counts: ExpectedCounts = ExpectedCounts(),
) -> dict[str, object]:
    final_path = assert_line_local_output(line_dir, output_dir)
    if final_path.exists():
        raise Stage001Error(f"final_output_exists:{final_path}")
    identities_before = collect_input_identities(input_paths, expected_sha256)
    inputs = _load_inputs(input_paths)
    source_manifest_valid, formal_rank10_identity_valid = _validate_frozen_inputs(
        inputs
    )
    contract_bars = build_contract_bar_table(inputs["bars"])
    history, mapping_diagnostics = build_mapped_product_history(
        inputs["mapping"], contract_bars
    )
    base_panel = build_base_query_panel(
        history,
        contract_bars,
        inputs["catalog"],
        inputs["metadata"],
        start=pd.Timestamp("2022-01-28"),
        capital=150_000.0,
        margin_ratio=0.15,
    )
    raw_features = compute_raw_features(
        base_panel,
        history,
        contract_bars,
        inputs["catalog"],
    )
    model_features = build_ranked_model_features(raw_features)
    bar_presence = contract_bars[["date", "contract_vt_symbol"]].copy()
    global_dates = pd.to_datetime(inputs["mapping"]["date"], errors="raise").unique()
    label_plan, rejected_label_plan = build_label_plan(
        base_panel,
        bar_presence,
        inputs["catalog"],
        global_dates,
    )
    formal_scoring = build_formal_scoring_plan(
        base_panel,
        inputs["coverage"],
        inputs["monthly"],
    )
    fold_plan = build_purged_fold_plan(
        label_plan,
        formal_scoring,
        minimum_train_qids=252,
    )
    identities_after = collect_input_identities(input_paths, expected_sha256)
    input_identity_stable = identities_before == identities_after
    observed = _build_observed_summary(
        base_panel=base_panel,
        raw_features=raw_features,
        model_features=model_features,
        label_plan=label_plan,
        rejected_label_plan=rejected_label_plan,
        formal_scoring_plan=formal_scoring,
        fold_plan=fold_plan,
        source_manifest_valid=source_manifest_valid,
        formal_rank10_identity_valid=formal_rank10_identity_valid,
        input_identity_stable=input_identity_stable,
        mapping_diagnostics=mapping_diagnostics,
    )
    summary = assess_gates(observed, expected_counts=expected_counts)
    summary["input_identities_before"] = identities_before
    summary["input_identities_after"] = identities_after
    summary["implementation_identities"] = {
        "contract_core": sha256_file(LINE_DIR / "tools/daily_ranker_contract.py"),
        "stage001_runner": sha256_file(Path(__file__)),
    }

    raw_output_columns = [
        "query_date",
        "product_vt_symbol",
        "main_contract_vt",
        *RAW_FEATURES,
        "maximum_path_source_date",
        "future_path_rows_used",
        "maximum_curve_source_date",
        "future_curve_rows_used",
    ]
    model_output_columns = [
        "query_date",
        "product_vt_symbol",
        "main_contract_vt",
        *MODEL_FEATURES,
    ]
    frames = {
        "raw_feature_panel.csv.gz": raw_features[raw_output_columns],
        "model_feature_panel.csv.gz": model_features[model_output_columns],
        "label_plan.csv.gz": label_plan,
        "rejected_label_plan.csv.gz": rejected_label_plan,
        "formal_scoring_plan.csv": formal_scoring,
        "fold_plan.csv": fold_plan,
    }
    documents = {
        "feature_contract.json": _feature_contract(),
        "input_identities.json": identities_after,
        "summary.json": summary,
        "report.md": _report(summary),
    }
    publish_bundle(
        frames,
        documents,
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage001 label-free PIT full-market daily ranker contract"
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
        summary = run_stage001()
    except (Stage001Error, ContractError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["all_gates_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
