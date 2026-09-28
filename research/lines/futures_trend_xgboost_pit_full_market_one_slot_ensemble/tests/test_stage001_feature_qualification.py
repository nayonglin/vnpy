from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


TOOL_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

from full_market_one_slot_features import (  # noqa: E402
    MODEL_FEATURES,
    PAIRWISE_FEATURES,
    RAW_FEATURES,
    FeatureBundle,
)
from stage001_feature_qualification import (  # noqa: E402
    ExpectedCounts,
    Stage001Error,
    assess_bundle,
    assert_line_local_output,
    publish_bundle,
    publish_failure_evidence,
    run_stage001,
    verify_published_bundle,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expected() -> ExpectedCounts:
    return ExpectedCounts(
        action_months=2,
        feature_rows=6,
        anchor_rows=2,
        challenger_rows=4,
        label_months=1,
        label_tasks=2,
        active_folds=1,
        effect_evaluable_folds=1,
        inference_only_folds=0,
        minimum_train_months=1,
        maximum_train_months=1,
        first_fold=None,
        last_fold=None,
    )


def _valid_bundle() -> FeatureBundle:
    eval_dates = pd.to_datetime(["2024-01-31", "2024-02-29"])
    raw_rows: list[dict[str, object]] = []
    model_rows: list[dict[str, object]] = []
    for eval_date in eval_dates:
        for index, (product, role) in enumerate(
            [
                ("anchor.EX", "formal_rank10"),
                ("low.EX", "challenger"),
                ("high.EX", "challenger"),
            ]
        ):
            raw_row: dict[str, object] = {
                "eval_date": eval_date,
                "product_vt_symbol": product,
                "maximum_source_date_used": eval_date,
                "future_bar_rows_used": 0,
                "maximum_curve_source_date_used": eval_date,
                "future_curve_rows_used": 0,
            }
            for feature_index, feature in enumerate(RAW_FEATURES, start=1):
                raw_row[feature] = float(index + feature_index)
            raw_rows.append(raw_row)

            model_row = {
                **raw_row,
                "role": role,
                "is_formal_replacement_product": role == "formal_rank10",
                "is_pool_outside_challenger": role == "challenger",
            }
            for feature_index, feature in enumerate(PAIRWISE_FEATURES, start=1):
                model_row[feature] = (
                    0.0 if role == "formal_rank10" else float(index * feature_index)
                )
            model_row["market_median_abs_momentum_126"] = 1.0
            model_row["market_median_realized_vol_63"] = 1.0
            model_rows.append(model_row)

    label_plan = pd.DataFrame(
        {
            "eval_date": [eval_dates[0], eval_dates[0]],
            "next_eval_date": [eval_dates[1], eval_dates[1]],
            "product_vt_symbol": ["low.EX", "high.EX"],
            "formal_replacement_product": ["anchor.EX", "anchor.EX"],
            "role": ["challenger", "challenger"],
            "label_values_read": [False, False],
        }
    )
    fold_plan = pd.DataFrame(
        {
            "test_eval_date": [eval_dates[1]],
            "train_month_count": [1],
            "train_task_count": [2],
            "minimum_train_eval_date": [eval_dates[0]],
            "maximum_train_eval_date": [eval_dates[0]],
            "minimum_train_label_end": [eval_dates[0]],
            "maximum_train_label_end": [eval_dates[0]],
            "effect_evaluable": [True],
            "inference_only": [False],
            "future_label_rows_used": [0],
            "sealed_holdout_rows": [0],
        }
    )
    diagnostics = pd.DataFrame(
        {
            "feature": PAIRWISE_FEATURES,
            "month_count": 2,
            "nonzero_cross_section_months": 2,
            "minimum_required_nonzero_months": 2,
        }
    )
    return FeatureBundle(
        raw_features=pd.DataFrame(raw_rows),
        model_features=pd.DataFrame(model_rows),
        label_plan=label_plan,
        fold_plan=fold_plan,
        diagnostics=diagnostics,
    )


def test_stage001_requires_explicit_authorization(tmp_path: Path) -> None:
    line_dir = tmp_path / "line"
    with pytest.raises(Stage001Error, match="authorization_required"):
        run_stage001(
            authorized=False,
            line_dir=line_dir,
            output_dir=line_dir / "artifacts" / "stage001",
            input_paths={},
            expected_sha256={},
            expected_counts=_expected(),
        )


def test_output_path_must_stay_inside_line(tmp_path: Path) -> None:
    line_dir = tmp_path / "line"
    with pytest.raises(Stage001Error, match="output_outside_line"):
        assert_line_local_output(line_dir, tmp_path / "elsewhere")


@pytest.mark.parametrize(
    "mutation",
    ["future_row", "anchor_nonzero", "label_column", "row_count"],
)
def test_assessment_rejects_contract_violation(mutation: str) -> None:
    bundle = _valid_bundle()
    if mutation == "future_row":
        bundle.raw_features.loc[0, "future_bar_rows_used"] = 1
    elif mutation == "anchor_nonzero":
        anchor_index = bundle.model_features.index[
            bundle.model_features["role"].eq("formal_rank10")
        ][0]
        bundle.model_features.loc[anchor_index, PAIRWISE_FEATURES[0]] = 0.1
    elif mutation == "label_column":
        bundle.label_plan["joint_win"] = 1
    elif mutation == "row_count":
        bundle.model_features.drop(bundle.model_features.index[-1], inplace=True)

    summary = assess_bundle(bundle, expected_counts=_expected())

    assert summary["all_gates_passed"] is False
    assert summary["decision"] == "stage001_full_market_feature_contract_fail_close_no_labels"


def test_assessment_accepts_exact_label_free_bundle() -> None:
    summary = assess_bundle(_valid_bundle(), expected_counts=_expected())

    assert summary["all_gates_passed"] is True
    assert summary["label_values_read"] is False
    assert summary["model_fit_count"] == 0
    assert summary["model_predict_count"] == 0
    assert summary["strategy_backtest_runs"] == 0
    assert summary["order_api_called_count"] == 0
    assert summary["production_files_written"] == 0


def test_publish_is_atomic_manifested_and_refuses_existing_final(tmp_path: Path) -> None:
    line_dir = tmp_path / "line"
    final_dir = line_dir / "artifacts" / "stage001"
    line_dir.mkdir()
    bundle = _valid_bundle()
    summary = assess_bundle(bundle, expected_counts=_expected())

    publish_bundle(
        bundle,
        summary,
        line_dir=line_dir,
        final_dir=final_dir,
        input_identities={"fixture": {"path": "fixture.csv", "sha256": "1" * 64}},
    )

    assert final_dir.is_dir()
    assert not final_dir.with_name("stage001.tmp").exists()
    verification = verify_published_bundle(final_dir)
    assert verification["verified"] is True
    manifest = json.loads((final_dir / "artifact_manifest.json").read_text("utf-8"))
    for name, identity in manifest["artifacts"].items():
        assert identity["sha256"] == _sha256(final_dir / name)
    with pytest.raises(Stage001Error, match="final_output_exists"):
        publish_bundle(
            bundle,
            summary,
            line_dir=line_dir,
            final_dir=final_dir,
            input_identities={},
        )


def test_model_feature_contract_remains_finite_and_identity_free() -> None:
    bundle = _valid_bundle()

    assert np.isfinite(bundle.model_features[MODEL_FEATURES].to_numpy(float)).all()
    assert not {"exchange", "product_id", "exchange_id"}.intersection(MODEL_FEATURES)


def test_failure_evidence_is_published_without_feature_or_label_outputs(
    tmp_path: Path,
) -> None:
    line_dir = tmp_path / "line"
    final_dir = line_dir / "artifacts" / "stage001"
    line_dir.mkdir()
    failures = pd.DataFrame(
        {
            "eval_date": [pd.Timestamp("2024-01-31")],
            "product_vt_symbol": ["p.EX"],
            "issue": ["volume_window_coverage_below_minimum"],
            "window": [20],
            "available_count": [20],
            "valid_count": [17],
            "required_count": [18],
        }
    )
    summary = {
        "decision": "stage001_full_market_feature_contract_fail_close_no_labels",
        "all_gates_passed": False,
        "gates": {"trailing_window_coverage_pass": False},
        "action_months": 1,
        "feature_rows": 0,
        "anchor_rows": 0,
        "challenger_rows": 0,
        "label_months": 0,
        "label_tasks": 0,
        "active_folds": 0,
        "effect_evaluable_folds": 0,
        "inference_only_folds": 0,
    }

    publish_failure_evidence(
        failures,
        summary,
        line_dir=line_dir,
        final_dir=final_dir,
        input_identities={},
    )

    assert (final_dir / "qualification_failures.csv").is_file()
    assert not (final_dir / "model_feature_panel.csv.gz").exists()
    assert not (final_dir / "label_plan.csv.gz").exists()
    assert verify_published_bundle(final_dir)["verified"] is True
