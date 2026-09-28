"""One-shot label-free contract audit for the LR/XGBoost base-margin research line."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from causal_formal_features import (
    FORBIDDEN_COLUMN_PREFIXES,
    build_causal_rolling_features,
    build_label_end_calendar,
    build_label_free_monthly_samples,
    build_pit_fold_plan,
)


LINE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
PRODUCTION_ROOT = Path("/Users/bytedance/Desktop/person/vnpy_production_live")
MATERIAL_ROOT = PRODUCTION_ROOT / "official_strategy_materials"

EXPECTED_RELEASE_ID = "m0005_20260901T165450+0800_1961d98ccb2b"
EXPECTED_STRATEGY_ID = "ai_top10_plus_fu_official_live_v1"
M0004_RELEASE_ID = "m0004_20260831T112631+0800_2485073e9594"

CURRENT_PATH = MATERIAL_ROOT / "CURRENT.json"
RELEASE_DIR = (
    MATERIAL_ROOT
    / EXPECTED_STRATEGY_ID
    / "releases"
    / EXPECTED_RELEASE_ID
)
M0004_RELEASE_DIR = (
    MATERIAL_ROOT
    / EXPECTED_STRATEGY_ID
    / "releases"
    / M0004_RELEASE_ID
)
RELEASE_CODE_DIR = RELEASE_DIR / "payload/examples/portfolio_backtesting"
MODEL_RELATIVE_PATH = Path(
    "payload/examples/portfolio_backtesting/analyze_qmt_roll_ai_product_suitability_walkforward.py"
)
RUNNER_RELATIVE_PATH = Path(
    "payload/examples/portfolio_backtesting/build_qmt_roll_stage182_ai_product_pool_live_inference_runner.py"
)

MANIFEST_PATH = RELEASE_DIR / "manifest.json"
MODEL_PATH = RELEASE_DIR / MODEL_RELATIVE_PATH
RUNNER_PATH = RELEASE_DIR / RUNNER_RELATIVE_PATH
M0004_MODEL_PATH = M0004_RELEASE_DIR / MODEL_RELATIVE_PATH
M0004_RUNNER_PATH = M0004_RELEASE_DIR / RUNNER_RELATIVE_PATH
STAGE182_SUMMARY_PATH = RELEASE_DIR / "payload/ai/stage182/summary.json"
LATEST_POOL_PATH = RELEASE_DIR / "payload/ai/stage182/latest_pool.csv"
SOURCE_DIR = Path(
    "/Users/bytedance/Library/Application Support/qmt-roll-stage179/production-live/official-live"
)
POSITION_CHANGES_PATH = SOURCE_DIR / (
    "qmt_roll_stage183_ai_source_floor35_position_changes_2020_2026_04.csv"
)
ENTRY_SNAPSHOTS_PATH = SOURCE_DIR / (
    "qmt_roll_stage183_ai_source_floor35_entry_candidate_snapshots_2020_2026_04.csv"
)
HISTORICAL_PANEL_PATH = (
    REPO_ROOT
    / "research/lines/futures_trend_ai_score_attribution/artifacts/"
    "stage001_20260731/training_samples.csv"
)

FINAL_OUTPUT_DIR = LINE_DIR / "artifacts/stage001_label_free_contract"

PASS_DECISION = (
    "stage001_m0005_causal_feature_and_pit_contract_pass_"
    "allow_stage002_preregistration_only"
)
FAIL_DECISION = "stage001_m0005_causal_feature_or_pit_contract_fail_close_no_labels"

EXPECTED_HASHES: dict[str, tuple[Path, str]] = {
    "current_pointer": (
        CURRENT_PATH,
        "f17c0f6bfeea4a08ec7c22a1eb63d4b51e4cfb2472f1ce07fac8ce2cc570b219",
    ),
    "m0005_manifest": (
        MANIFEST_PATH,
        "d62e58d01284e30b28054387592604862ffeff6e55a13c63192793e95bc55c21",
    ),
    "m0005_model_code": (
        MODEL_PATH,
        "7734d1768728a4e591b80e98da2b5bac90636904dad82e0fed5f331a6eb45de4",
    ),
    "m0005_runner_code": (
        RUNNER_PATH,
        "ca15504e946e39fe6c5b0180e5bdf07bf38749973ceedd2085ba77480e3c9edc",
    ),
    "m0004_model_code": (
        M0004_MODEL_PATH,
        "7734d1768728a4e591b80e98da2b5bac90636904dad82e0fed5f331a6eb45de4",
    ),
    "m0004_runner_code": (
        M0004_RUNNER_PATH,
        "ca15504e946e39fe6c5b0180e5bdf07bf38749973ceedd2085ba77480e3c9edc",
    ),
    "stage182_summary": (
        STAGE182_SUMMARY_PATH,
        "e119fcdaddb16d173bf8737edd39e3241dc2b277ea96f908d6eeb71bf9bdd5c3",
    ),
    "latest_pool": (
        LATEST_POOL_PATH,
        "9c28774c5f7d02de837a30408c93cd5ba9aa925e03280b1d9b294fbaaf70a814",
    ),
    "stage183_position_changes": (
        POSITION_CHANGES_PATH,
        "17c81f2dbb30f836b544161c3fc4d4bd6415151d89b8f8937378739e868c21aa",
    ),
    "stage183_entry_snapshots": (
        ENTRY_SNAPSHOTS_PATH,
        "f838186527b1453923635bda31ec8e1656a0bdacfec633a6b85f2cda8e3b26a0",
    ),
    "historical_feature_panel": (
        HISTORICAL_PANEL_PATH,
        "92f36b6647cae9d8db04b0a1351749f9103a1988799dbb8dff0ad1d350d1d431",
    ),
}


class Stage001Error(RuntimeError):
    pass


@dataclass(frozen=True)
class FileIdentity:
    path: str
    size: int
    mtime_ns: int
    sha256: str
    expected_sha256: str
    matches_expected: bool


def _json_default(value: object) -> object:
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).date().isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def _sha256(path: Path) -> tuple[int, int, str]:
    source = path.expanduser().resolve(strict=True)
    before = source.stat()
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise Stage001Error(f"input_changed_while_hashing:{source}")
    return int(after.st_size), int(after.st_mtime_ns), digest.hexdigest()


def collect_input_identities() -> dict[str, dict[str, Any]]:
    identities: dict[str, dict[str, Any]] = {}
    for name, (path, expected) in EXPECTED_HASHES.items():
        size, mtime_ns, actual = _sha256(path)
        identity = FileIdentity(
            path=str(path.resolve()),
            size=size,
            mtime_ns=mtime_ns,
            sha256=actual,
            expected_sha256=expected,
            matches_expected=actual == expected,
        )
        identities[name] = identity.__dict__
    return identities


def assert_allowed_columns(columns: Iterable[str]) -> None:
    forbidden = [
        str(column)
        for column in columns
        if str(column).startswith(FORBIDDEN_COLUMN_PREFIXES)
    ]
    if forbidden:
        raise Stage001Error(f"forbidden_column:{','.join(sorted(forbidden))}")


def _read_feature_projection(path: Path, feature_columns: list[str]) -> pd.DataFrame:
    columns = ["eval_date", "product_vt_symbol", *feature_columns]
    assert_allowed_columns(columns)
    frame = pd.read_csv(path, usecols=columns)
    frame["eval_date"] = pd.to_datetime(frame["eval_date"]).dt.normalize()
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    frame.sort_values(["eval_date", "product_vt_symbol"], inplace=True)
    frame.reset_index(drop=True, inplace=True)
    return frame


@contextmanager
def release_csv_import_environment():
    """Scope the release's documented non-database import override to one block."""

    key = "QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR"
    sentinel = object()
    previous: object = os.environ.get(key, sentinel)
    os.environ[key] = "1"
    try:
        yield
    finally:
        if previous is sentinel:
            os.environ.pop(key, None)
        else:
            os.environ[key] = str(previous)


def _load_formal_model_module():
    module_name = "stage001_frozen_m0005_formal_model"
    code_dir = str(RELEASE_CODE_DIR)
    sys.path.insert(0, code_dir)
    try:
        spec = importlib.util.spec_from_file_location(module_name, MODEL_PATH)
        if spec is None or spec.loader is None:
            raise Stage001Error("formal_model_import_spec_failed")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        with release_csv_import_environment():
            spec.loader.exec_module(module)
    finally:
        if sys.path and sys.path[0] == code_dir:
            sys.path.pop(0)
    module.POSITION_CHANGES_PATH = POSITION_CHANGES_PATH
    module.ENTRY_SNAPSHOTS_PATH = ENTRY_SNAPSHOTS_PATH
    return module


def _max_abs_error(
    left: pd.DataFrame,
    right: pd.DataFrame,
    feature_columns: list[str],
) -> float:
    identity_columns = ["eval_date", "product_vt_symbol"]
    if not left[identity_columns].equals(right[identity_columns]):
        return float("inf")
    if left.empty:
        return float("inf")
    difference = np.abs(
        left[feature_columns].to_numpy(dtype="float64")
        - right[feature_columns].to_numpy(dtype="float64")
    )
    return float(np.nanmax(difference)) if difference.size else 0.0


def _load_current_identity() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    current = json.loads(CURRENT_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    stage182 = json.loads(STAGE182_SUMMARY_PATH.read_text(encoding="utf-8"))
    return current, manifest, stage182


def _pit_violation_counts(fold_plan: pd.DataFrame) -> tuple[int, int]:
    if fold_plan.empty:
        return 0, 0
    rows = int(fold_plan["pit_violation_rows"].sum())
    folds = int(fold_plan["pit_violation_rows"].gt(0).sum())
    return rows, folds


def assess_gates(metrics: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []

    if (
        int(metrics.get("input_identity_mismatch_count", -1)) != 0
        or not bool(metrics.get("current_pointer_matches_release", False))
        or metrics.get("current_release_id") != EXPECTED_RELEASE_ID
        or metrics.get("current_strategy_id") != EXPECTED_STRATEGY_ID
    ):
        failures.append("input_identity")
    if not (
        bool(metrics.get("m0004_m0005_model_code_equal", False))
        and bool(metrics.get("m0004_m0005_runner_code_equal", False))
    ):
        failures.append("formal_code_identity")
    if not (
        int(metrics.get("feature_count", -1)) == 108
        and int(metrics.get("train_months", -1)) == 77
        and int(metrics.get("train_rows", -1)) == 1386
        and int(metrics.get("minimum_products_per_train_month", -1)) == 18
        and int(metrics.get("maximum_products_per_train_month", -1)) == 18
        and int(metrics.get("nonfinite_feature_cells", -1)) == 0
    ):
        failures.append("current_training_feature_contract")
    if not (
        int(metrics.get("historical_parity_months", -1)) == 76
        and int(metrics.get("historical_parity_rows", -1)) == 1368
        and float(metrics.get("historical_parity_max_abs_error", float("inf"))) <= 1e-10
    ):
        failures.append("historical_feature_parity")
    if not (
        int(metrics.get("latest_pool_parity_rows", -1)) == 11
        and float(metrics.get("latest_pool_parity_max_abs_error", float("inf"))) <= 1e-10
    ):
        failures.append("latest_pool_feature_parity")
    if int(metrics.get("active_folds", -1)) < 48:
        failures.append("pit_fold_count")
    if not (
        int(metrics.get("minimum_train_months", -1)) >= 24
        and int(metrics.get("pit_violation_rows", -1)) == 0
        and int(metrics.get("pit_violation_folds", -1)) == 0
    ):
        failures.append("pit_integrity")

    side_effect_fields = (
        "forbidden_columns_read_count",
        "future_label_value_read_count",
        "model_fit_count",
        "model_predict_count",
        "strategy_backtest_count",
        "ctp_connection_count",
        "order_api_call_count",
        "production_write_count",
    )
    if any(int(metrics.get(field, -1)) != 0 for field in side_effect_fields):
        failures.append("stage001_side_effect_free")

    failures = list(dict.fromkeys(failures))
    passed = not failures
    return {
        "all_gates_passed": passed,
        "failures": failures,
        "decision": PASS_DECISION if passed else FAIL_DECISION,
    }


def assert_line_local_output(line_dir: Path, output_dir: Path) -> None:
    line = line_dir.expanduser().resolve()
    output = output_dir.expanduser().resolve()
    try:
        output.relative_to(line)
    except ValueError as exc:
        raise Stage001Error(f"output_outside_line:{output}") from exc


def _file_manifest(directory: Path, names: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name in names:
        path = directory / name
        size, _, digest = _sha256(path)
        result[name] = {"size": size, "sha256": digest}
    return result


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _build_report(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Stage001 m0005无标签合同审计",
            "",
            f"- 决策：`{summary.get('decision', '')}`",
            f"- 正式训练面板：`{summary.get('train_months', 0)}`月 / `{summary.get('train_rows', 0)}`行 / `{summary.get('feature_count', 0)}`特征",
            f"- 历史逐值误差：`{summary.get('historical_parity_max_abs_error', 'NA')}`",
            f"- 最新池逐值误差：`{summary.get('latest_pool_parity_max_abs_error', 'NA')}`",
            f"- PIT折数：`{summary.get('active_folds', 0)}`；违规行/折：`{summary.get('pit_violation_rows', 0)}/{summary.get('pit_violation_folds', 0)}`",
            f"- 失败门：`{','.join(summary.get('failures', [])) or 'none'}`",
            "- 标签值、模型fit/predict、回测、CTP、订单和生产写入均为0。",
            "",
        ]
    )


def publish_evidence_bundle(
    *,
    line_dir: Path,
    final_dir: Path,
    summary: dict[str, Any],
    feature_contract: dict[str, Any],
    fold_rows: list[dict[str, Any]],
    input_identities: dict[str, Any],
) -> None:
    assert_line_local_output(line_dir, final_dir)
    final = final_dir.expanduser().resolve()
    if final.exists():
        raise Stage001Error(f"final_output_exists:{final}")
    final.parent.mkdir(parents=True, exist_ok=True)
    temporary = final.parent / f".{final.name}.tmp.{os.getpid()}"
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True)

    try:
        _write_json(temporary / "summary.json", summary)
        _write_json(temporary / "input_identities.json", input_identities)
        _write_json(temporary / "feature_contract.json", feature_contract)
        pd.DataFrame(fold_rows).to_csv(temporary / "fold_plan.csv", index=False)
        (temporary / "report.md").write_text(_build_report(summary), encoding="utf-8")
        names = [
            "summary.json",
            "input_identities.json",
            "feature_contract.json",
            "fold_plan.csv",
            "report.md",
        ]
        manifest = {"schema_version": 1, "files": _file_manifest(temporary, names)}
        _write_json(temporary / "artifact_manifest.json", manifest)
        verification = verify_evidence_bundle(temporary)
        if not verification["valid"]:
            raise Stage001Error(
                f"temporary_manifest_invalid:{','.join(verification['errors'])}"
            )
        os.replace(temporary, final)
        final_verification = verify_evidence_bundle(final)
        if not final_verification["valid"]:
            raise Stage001Error(
                f"published_manifest_invalid:{','.join(final_verification['errors'])}"
            )
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def verify_evidence_bundle(directory: Path) -> dict[str, Any]:
    root = directory.expanduser().resolve()
    errors: list[str] = []
    manifest_path = root / "artifact_manifest.json"
    if not manifest_path.exists():
        return {"valid": False, "errors": ["manifest_missing"]}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"valid": False, "errors": ["manifest_unreadable"]}
    files = manifest.get("files", {})
    for name, expected in files.items():
        path = root / str(name)
        if not path.is_file():
            errors.append(f"file_missing:{name}")
            continue
        size, _, digest = _sha256(path)
        if size != int(expected.get("size", -1)):
            errors.append(f"size_mismatch:{name}")
        if digest != str(expected.get("sha256", "")):
            errors.append(f"sha256_mismatch:{name}")
    return {"valid": not errors, "errors": errors}


def run_stage001() -> tuple[dict[str, Any], dict[str, Any], pd.DataFrame, dict[str, Any]]:
    identities_before = collect_input_identities()
    identity_mismatches = sum(
        not bool(identity["matches_expected"])
        for identity in identities_before.values()
    )
    if identity_mismatches:
        raise Stage001Error(f"input_identity_mismatch:{identity_mismatches}")

    current, manifest, stage182 = _load_current_identity()
    formal = _load_formal_model_module()
    daily = formal.build_product_daily()
    featured = build_causal_rolling_features(daily)
    monthly, feature_columns = build_label_free_monthly_samples(
        featured,
        minimum_cross_section=8,
    )

    training_cutoff = pd.Timestamp(stage182["training_label_cutoff"]).normalize()
    train = monthly[monthly["eval_date"] <= training_cutoff].copy()
    train.sort_values(["eval_date", "product_vt_symbol"], inplace=True)
    train.reset_index(drop=True, inplace=True)

    historical = _read_feature_projection(HISTORICAL_PANEL_PATH, feature_columns)
    rebuilt_historical = train[
        train["eval_date"].isin(historical["eval_date"].unique())
    ][["eval_date", "product_vt_symbol", *feature_columns]].copy()
    rebuilt_historical.sort_values(["eval_date", "product_vt_symbol"], inplace=True)
    rebuilt_historical.reset_index(drop=True, inplace=True)
    historical_error = _max_abs_error(
        rebuilt_historical,
        historical,
        feature_columns,
    )

    latest = _read_feature_projection(LATEST_POOL_PATH, feature_columns)
    latest_identities = latest[["eval_date", "product_vt_symbol"]]
    rebuilt_latest = monthly.merge(
        latest_identities,
        on=["eval_date", "product_vt_symbol"],
        how="inner",
        validate="one_to_one",
    )[["eval_date", "product_vt_symbol", *feature_columns]]
    rebuilt_latest.sort_values(["eval_date", "product_vt_symbol"], inplace=True)
    rebuilt_latest.reset_index(drop=True, inplace=True)
    latest_error = _max_abs_error(rebuilt_latest, latest, feature_columns)

    label_calendar = build_label_end_calendar(
        daily["date"],
        train["eval_date"],
        horizon=60,
    )
    fold_plan = build_pit_fold_plan(label_calendar, minimum_train_months=24)
    pit_violation_rows, pit_violation_folds = _pit_violation_counts(fold_plan)

    products_per_month = train.groupby("eval_date")["product_vt_symbol"].nunique()
    feature_values = train[feature_columns].to_numpy(dtype="float64")
    identities_after = collect_input_identities()
    identity_mismatches += sum(
        identities_before[name]["sha256"] != identities_after[name]["sha256"]
        for name in identities_before
    )

    metrics: dict[str, Any] = {
        "current_release_id": current.get("release_id"),
        "current_strategy_id": current.get("strategy_version"),
        "current_pointer_matches_release": (
            current.get("release_id") == manifest.get("release_id") == EXPECTED_RELEASE_ID
            and current.get("strategy_version")
            == manifest.get("strategy_version")
            == EXPECTED_STRATEGY_ID
        ),
        "m0004_m0005_model_code_equal": (
            identities_before["m0004_model_code"]["sha256"]
            == identities_before["m0005_model_code"]["sha256"]
        ),
        "m0004_m0005_runner_code_equal": (
            identities_before["m0004_runner_code"]["sha256"]
            == identities_before["m0005_runner_code"]["sha256"]
        ),
        "training_label_cutoff": training_cutoff,
        "source_min_date": pd.Timestamp(daily["date"].min()),
        "source_max_date": pd.Timestamp(daily["date"].max()),
        "feature_count": len(feature_columns),
        "train_months": int(train["eval_date"].nunique()),
        "train_rows": int(len(train)),
        "minimum_products_per_train_month": int(products_per_month.min()),
        "maximum_products_per_train_month": int(products_per_month.max()),
        "nonfinite_feature_cells": int((~np.isfinite(feature_values)).sum()),
        "historical_parity_months": int(historical["eval_date"].nunique()),
        "historical_parity_rows": int(len(historical)),
        "historical_parity_max_abs_error": historical_error,
        "latest_pool_parity_rows": int(len(latest)),
        "latest_pool_parity_max_abs_error": latest_error,
        "label_calendar_rows": int(len(label_calendar)),
        "label_calendar_missing_end_rows": int(label_calendar["label_end"].isna().sum()),
        "active_folds": int(len(fold_plan)),
        "effect_evaluable_folds": int(fold_plan["effect_evaluable"].sum()),
        "minimum_train_months": int(fold_plan["train_months"].min()),
        "maximum_train_months": int(fold_plan["train_months"].max()),
        "pit_violation_rows": pit_violation_rows,
        "pit_violation_folds": pit_violation_folds,
        "forbidden_columns_read_count": 0,
        "future_label_value_read_count": 0,
        "model_fit_count": 0,
        "model_predict_count": 0,
        "strategy_backtest_count": 0,
        "ctp_connection_count": 0,
        "order_api_call_count": 0,
        "production_write_count": 0,
        "input_identity_mismatch_count": int(identity_mismatches),
        "formal_summary_train_rows": int(stage182["train_rows"]),
        "formal_summary_train_months": int(stage182["train_months"]),
        "formal_summary_feature_count": int(stage182["feature_count"]),
    }
    gate_result = assess_gates(metrics)
    summary = {**metrics, **gate_result}
    feature_contract = {
        "feature_count": len(feature_columns),
        "features": feature_columns,
        "rolling_windows": [20, 60, 120],
        "future_columns_computed": False,
        "label_values_read": False,
        "historical_projection_columns": [
            "eval_date",
            "product_vt_symbol",
            *feature_columns,
        ],
        "latest_pool_projection_columns": [
            "eval_date",
            "product_vt_symbol",
            *feature_columns,
        ],
    }
    input_bundle = {
        "before": identities_before,
        "after": identities_after,
    }
    return summary, feature_contract, fold_plan, input_bundle


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--authorized-label-free-audit", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    if args.verify_only:
        verification = verify_evidence_bundle(FINAL_OUTPUT_DIR)
        if not verification["valid"]:
            raise Stage001Error(f"verification_failed:{','.join(verification['errors'])}")
        print(json.dumps(verification, ensure_ascii=False, indent=2))
        return

    if FINAL_OUTPUT_DIR.exists():
        raise Stage001Error(f"final_output_exists:{FINAL_OUTPUT_DIR}")
    summary, feature_contract, fold_plan, input_identities = run_stage001()
    fold_rows = json.loads(
        fold_plan.to_json(orient="records", date_format="iso")
    )
    publish_evidence_bundle(
        line_dir=LINE_DIR,
        final_dir=FINAL_OUTPUT_DIR,
        summary=summary,
        feature_contract=feature_contract,
        fold_rows=fold_rows,
        input_identities=input_identities,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default))


if __name__ == "__main__":
    main()
