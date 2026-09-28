"""Independent label-free audit of the formal model-ranked publication boundary."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


LINE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
PREDECESSOR_LINE = (
    REPO_ROOT / "research/lines/futures_trend_lr_xgboost_base_margin_residual"
)
PREDECESSOR_TOOLS = PREDECESSOR_LINE / "tools"
PREDECESSOR_CAUSAL_TOOL = PREDECESSOR_TOOLS / "causal_formal_features.py"
PREDECESSOR_RUNNER_TOOL = PREDECESSOR_TOOLS / "stage001_label_free_contract.py"
PREDECESSOR_FINAL_DIR = PREDECESSOR_LINE / "artifacts/stage001_label_free_contract"

if str(PREDECESSOR_TOOLS) not in sys.path:
    sys.path.insert(0, str(PREDECESSOR_TOOLS))

import causal_formal_features as causal
import stage001_label_free_contract as base


EXPECTED_RELEASE_ID = base.EXPECTED_RELEASE_ID
EXPECTED_STRATEGY_ID = base.EXPECTED_STRATEGY_ID
EXPECTED_RANKED_COUNT = 10
EXPECTED_TOTAL_COUNT = 11
EXPECTED_FIXED_PRODUCT = "fu.SHFE"

POLICY_PATH = (
    base.RELEASE_DIR
    / "payload/examples/portfolio_backtesting/qmt_roll_official_ai_pool_policy.py"
)
EXPECTED_EXTRA_HASHES: dict[str, tuple[Path, str]] = {
    "official_ai_pool_policy": (
        POLICY_PATH,
        "c68ca17f7088eac0c61f66c01fee1e2b34c973e2307cadf8a2026b9ab95f32a5",
    ),
    "predecessor_causal_tool": (
        PREDECESSOR_CAUSAL_TOOL,
        "930c81fca2de049983c75c7470873e781b086a208993f9817fb04fd3649ef15f",
    ),
    "predecessor_base_runner": (
        PREDECESSOR_RUNNER_TOOL,
        "6f315ecb5ca63f0fbf83495119226c65da397c2a5dbbf7ef8cefa80a9c34c2bd",
    ),
}

FINAL_OUTPUT_DIR = LINE_DIR / "artifacts/stage001_model_ranked_contract"
PASS_DECISION = (
    "stage001_model_ranked_boundary_contract_pass_"
    "allow_stage002_preregistration_only"
)
FAIL_DECISION = "stage001_model_ranked_boundary_contract_fail_close_no_labels"


class Stage001Error(RuntimeError):
    pass


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


def assert_read_path_allowed(path: Path) -> None:
    source = path.expanduser().resolve(strict=False)
    forbidden = PREDECESSOR_FINAL_DIR.resolve(strict=False)
    try:
        source.relative_to(forbidden)
    except ValueError:
        return
    raise Stage001Error(f"predecessor_final_read_forbidden:{source}")


def _assert_paths_allowed(paths: Iterable[Path]) -> None:
    for path in paths:
        assert_read_path_allowed(path)


def _collect_identities() -> dict[str, dict[str, Any]]:
    _assert_paths_allowed(path for path, _ in base.EXPECTED_HASHES.values())
    identities = base.collect_input_identities()
    for name, (path, expected) in EXPECTED_EXTRA_HASHES.items():
        assert_read_path_allowed(path)
        size, mtime_ns, actual = _sha256(path)
        identities[name] = {
            "path": str(path.resolve()),
            "size": size,
            "mtime_ns": mtime_ns,
            "sha256": actual,
            "expected_sha256": expected,
            "matches_expected": actual == expected,
        }
    return identities


def _load_policy_module():
    assert_read_path_allowed(POLICY_PATH)
    spec = importlib.util.spec_from_file_location(
        "stage001_frozen_official_ai_pool_policy",
        POLICY_PATH,
    )
    if spec is None or spec.loader is None:
        raise Stage001Error("official_policy_import_spec_failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def classify_published_pool(
    published: pd.DataFrame,
    feature_columns: list[str],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    required = {
        "eval_date",
        "product_vt_symbol",
        "selection_role",
        "model_ai_rank",
        *feature_columns,
    }
    missing = sorted(required - set(published.columns))
    if missing:
        raise Stage001Error(f"latest_pool_columns_missing:{','.join(missing)}")
    frame = published[list(required)].copy()
    frame["eval_date"] = pd.to_datetime(frame["eval_date"]).dt.normalize()
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    frame["selection_role"] = frame["selection_role"].astype(str)
    model_rows = frame[frame["selection_role"].eq("model_ranked")].copy()
    fixed_rows = frame[frame["selection_role"].eq("fixed_fu")].copy()
    model_rows.sort_values(["eval_date", "product_vt_symbol"], inplace=True)
    model_rows.reset_index(drop=True, inplace=True)
    metrics = {
        "latest_pool_rows": int(len(frame)),
        "latest_model_ranked_rows": int(len(model_rows)),
        "latest_fixed_fu_rows": int(len(fixed_rows)),
        "latest_fixed_product_match": bool(
            len(fixed_rows) == 1
            and fixed_rows["product_vt_symbol"].iloc[0] == EXPECTED_FIXED_PRODUCT
        ),
        "latest_model_ranked_contains_fixed_product_count": int(
            model_rows["product_vt_symbol"].eq(EXPECTED_FIXED_PRODUCT).sum()
        ),
        "latest_model_ranked_complete_feature_rows": int(
            model_rows[feature_columns].notna().all(axis=1).sum()
        ),
        "latest_fixed_fu_nonnull_feature_cells": int(
            fixed_rows[feature_columns].notna().sum().sum()
        ),
        "latest_fixed_fu_nonnull_model_rank_rows": int(
            fixed_rows["model_ai_rank"].notna().sum()
        ),
    }
    return model_rows, metrics


def assess_gates(metrics: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if int(metrics.get("input_identity_mismatch_count", -1)) != 0:
        failures.append("input_identity")
    if int(metrics.get("predecessor_final_read_count", -1)) != 0:
        failures.append("predecessor_final_isolation")
    if not (
        metrics.get("current_release_id") == EXPECTED_RELEASE_ID
        and metrics.get("current_strategy_id") == EXPECTED_STRATEGY_ID
        and bool(metrics.get("current_pointer_matches_release", False))
        and bool(metrics.get("m0004_m0005_model_code_equal", False))
        and bool(metrics.get("m0004_m0005_runner_code_equal", False))
    ):
        failures.append("formal_identity")
    if not (
        int(metrics.get("official_ranked_product_count", -1)) == EXPECTED_RANKED_COUNT
        and int(metrics.get("official_total_product_count", -1)) == EXPECTED_TOTAL_COUNT
        and metrics.get("official_fixed_product") == EXPECTED_FIXED_PRODUCT
    ):
        failures.append("official_policy_boundary")
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
        int(metrics.get("latest_pool_rows", -1)) == EXPECTED_TOTAL_COUNT
        and int(metrics.get("latest_model_ranked_rows", -1)) == EXPECTED_RANKED_COUNT
        and int(metrics.get("latest_fixed_fu_rows", -1)) == 1
        and bool(metrics.get("latest_fixed_product_match", False))
        and int(metrics.get("latest_model_ranked_contains_fixed_product_count", -1)) == 0
        and int(metrics.get("latest_model_ranked_complete_feature_rows", -1))
        == EXPECTED_RANKED_COUNT
    ):
        failures.append("published_pool_ownership")
    if not (
        int(metrics.get("latest_fixed_fu_nonnull_feature_cells", -1)) == 0
        and int(metrics.get("latest_fixed_fu_nonnull_model_rank_rows", -1)) == 0
    ):
        failures.append("fixed_fu_non_model_boundary")
    if not (
        int(metrics.get("latest_model_ranked_parity_rows", -1)) == EXPECTED_RANKED_COUNT
        and float(
            metrics.get("latest_model_ranked_parity_max_abs_error", float("inf"))
        )
        <= 1e-10
    ):
        failures.append("latest_model_ranked_feature_parity")
    if not (
        int(metrics.get("label_calendar_rows", -1)) == 77
        and int(metrics.get("label_calendar_missing_end_rows", -1)) == 0
        and int(metrics.get("active_folds", -1)) == 50
        and int(metrics.get("effect_evaluable_folds", -1)) == 50
        and int(metrics.get("minimum_train_months", -1)) == 24
        and int(metrics.get("maximum_train_months", -1)) == 74
        and int(metrics.get("pit_violation_rows", -1)) == 0
        and int(metrics.get("pit_violation_folds", -1)) == 0
    ):
        failures.append("pit_fold_contract")
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


def _read_latest_pool(feature_columns: list[str]) -> pd.DataFrame:
    path = base.LATEST_POOL_PATH
    assert_read_path_allowed(path)
    columns = [
        "eval_date",
        "product_vt_symbol",
        "selection_role",
        "model_ai_rank",
        *feature_columns,
    ]
    base.assert_allowed_columns(columns)
    return pd.read_csv(path, usecols=columns)


def _pit_violation_counts(fold_plan: pd.DataFrame) -> tuple[int, int]:
    return (
        int(fold_plan["pit_violation_rows"].sum()),
        int(fold_plan["pit_violation_rows"].gt(0).sum()),
    )


def run_stage001() -> tuple[dict[str, Any], dict[str, Any], pd.DataFrame, dict[str, Any]]:
    identities_before = _collect_identities()
    mismatch_count = sum(
        not bool(identity["matches_expected"])
        for identity in identities_before.values()
    )
    if mismatch_count:
        raise Stage001Error(f"input_identity_mismatch:{mismatch_count}")

    current, manifest, stage182 = base._load_current_identity()
    policy = _load_policy_module()
    formal = base._load_formal_model_module()
    daily = formal.build_product_daily()
    featured = causal.build_causal_rolling_features(daily)
    monthly, feature_columns = causal.build_label_free_monthly_samples(
        featured,
        minimum_cross_section=8,
    )
    training_cutoff = pd.Timestamp(stage182["training_label_cutoff"]).normalize()
    train = monthly[monthly["eval_date"] <= training_cutoff].copy()
    train.sort_values(["eval_date", "product_vt_symbol"], inplace=True)
    train.reset_index(drop=True, inplace=True)

    assert_read_path_allowed(base.HISTORICAL_PANEL_PATH)
    historical = base._read_feature_projection(
        base.HISTORICAL_PANEL_PATH,
        feature_columns,
    )
    rebuilt_historical = train[
        train["eval_date"].isin(historical["eval_date"].unique())
    ][["eval_date", "product_vt_symbol", *feature_columns]].copy()
    rebuilt_historical.sort_values(["eval_date", "product_vt_symbol"], inplace=True)
    rebuilt_historical.reset_index(drop=True, inplace=True)
    historical_error = base._max_abs_error(
        rebuilt_historical,
        historical,
        feature_columns,
    )

    published = _read_latest_pool(feature_columns)
    model_rows, publication_metrics = classify_published_pool(
        published,
        feature_columns,
    )
    model_projection = model_rows[
        ["eval_date", "product_vt_symbol", *feature_columns]
    ].copy()
    model_projection.sort_values(["eval_date", "product_vt_symbol"], inplace=True)
    model_projection.reset_index(drop=True, inplace=True)
    rebuilt_latest = monthly.merge(
        model_projection[["eval_date", "product_vt_symbol"]],
        on=["eval_date", "product_vt_symbol"],
        how="inner",
        validate="one_to_one",
    )[["eval_date", "product_vt_symbol", *feature_columns]]
    rebuilt_latest.sort_values(["eval_date", "product_vt_symbol"], inplace=True)
    rebuilt_latest.reset_index(drop=True, inplace=True)
    latest_error = base._max_abs_error(
        rebuilt_latest,
        model_projection,
        feature_columns,
    )

    label_calendar = causal.build_label_end_calendar(
        daily["date"],
        train["eval_date"],
        horizon=60,
    )
    fold_plan = causal.build_pit_fold_plan(
        label_calendar,
        minimum_train_months=24,
    )
    pit_rows, pit_folds = _pit_violation_counts(fold_plan)
    products_per_month = train.groupby("eval_date")["product_vt_symbol"].nunique()
    feature_values = train[feature_columns].to_numpy(dtype="float64")

    identities_after = _collect_identities()
    mismatch_count += sum(
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
        "official_ranked_product_count": int(
            policy.OFFICIAL_AI_RANKED_PRODUCT_COUNT
        ),
        "official_total_product_count": int(policy.OFFICIAL_AI_TOTAL_PRODUCT_COUNT),
        "official_fixed_product": str(policy.OFFICIAL_AI_FIXED_PRODUCT),
        "training_label_cutoff": training_cutoff,
        "feature_count": len(feature_columns),
        "train_months": int(train["eval_date"].nunique()),
        "train_rows": int(len(train)),
        "minimum_products_per_train_month": int(products_per_month.min()),
        "maximum_products_per_train_month": int(products_per_month.max()),
        "nonfinite_feature_cells": int((~np.isfinite(feature_values)).sum()),
        "historical_parity_months": int(historical["eval_date"].nunique()),
        "historical_parity_rows": int(len(historical)),
        "historical_parity_max_abs_error": historical_error,
        **publication_metrics,
        "latest_model_ranked_parity_rows": int(len(model_projection)),
        "latest_model_ranked_parity_max_abs_error": latest_error,
        "latest_pool_parity_max_abs_error": latest_error,
        "label_calendar_rows": int(len(label_calendar)),
        "label_calendar_missing_end_rows": int(label_calendar["label_end"].isna().sum()),
        "active_folds": int(len(fold_plan)),
        "effect_evaluable_folds": int(fold_plan["effect_evaluable"].sum()),
        "minimum_train_months": int(fold_plan["train_months"].min()),
        "maximum_train_months": int(fold_plan["train_months"].max()),
        "pit_violation_rows": pit_rows,
        "pit_violation_folds": pit_folds,
        "predecessor_final_read_count": 0,
        "forbidden_columns_read_count": 0,
        "future_label_value_read_count": 0,
        "model_fit_count": 0,
        "model_predict_count": 0,
        "strategy_backtest_count": 0,
        "ctp_connection_count": 0,
        "order_api_call_count": 0,
        "production_write_count": 0,
        "input_identity_mismatch_count": int(mismatch_count),
    }
    gate_result = assess_gates(metrics)
    summary = {**metrics, **gate_result}
    feature_contract = {
        "feature_count": len(feature_columns),
        "features": feature_columns,
        "model_domain_product_count": 18,
        "published_model_ranked_count": EXPECTED_RANKED_COUNT,
        "published_fixed_product": EXPECTED_FIXED_PRODUCT,
        "published_total_count": EXPECTED_TOTAL_COUNT,
        "future_columns_computed": False,
        "label_values_read": False,
    }
    inputs = {"before": identities_before, "after": identities_after}
    return summary, feature_contract, fold_plan, inputs


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--authorized-label-free-audit", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    if args.verify_only:
        verification = base.verify_evidence_bundle(FINAL_OUTPUT_DIR)
        if not verification["valid"]:
            raise Stage001Error(f"verification_failed:{','.join(verification['errors'])}")
        print(json.dumps(verification, ensure_ascii=False, indent=2))
        return
    if FINAL_OUTPUT_DIR.exists():
        raise Stage001Error(f"final_output_exists:{FINAL_OUTPUT_DIR}")

    summary, feature_contract, fold_plan, identities = run_stage001()
    fold_rows = json.loads(fold_plan.to_json(orient="records", date_format="iso"))
    base.publish_evidence_bundle(
        line_dir=LINE_DIR,
        final_dir=FINAL_OUTPUT_DIR,
        summary=summary,
        feature_contract=feature_contract,
        fold_rows=fold_rows,
        input_identities=identities,
    )
    print(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
            default=base._json_default,
        )
    )


if __name__ == "__main__":
    main()
