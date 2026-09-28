from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage001_daily_ranker_contract as stage001


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expected() -> stage001.ExpectedCounts:
    return stage001.ExpectedCounts(
        base_query_count=4,
        base_row_count=12,
        base_width_min=3,
        base_width_median=3.0,
        base_width_max=3,
        first_query_date="2024-01-02",
        last_query_date="2024-01-05",
        volume_ratio_missing=2,
        open_interest_ratio_missing=1,
        label_query_count=3,
        label_row_count=9,
        label_width_min=3,
        label_width_median=3.0,
        label_width_max=3,
        rejected_label_rows=3,
        action_months=2,
        formal_anchor_rows=2,
        challenger_rows=4,
        minimum_challengers_per_month=2,
        fold_count=2,
        effect_evaluable_folds=1,
        inference_only_folds=1,
        minimum_train_qids=2,
        maximum_train_qids=3,
        first_fold="2024-01-31",
        last_fold="2024-02-29",
        minimum_nonzero_cross_section_qids=3,
    )


def _passing_observed() -> dict[str, object]:
    return {
        "source_manifest_valid": True,
        "formal_rank10_identity_valid": True,
        "input_identity_stable": True,
        "base_query_count": 4,
        "base_row_count": 12,
        "base_width_min": 3,
        "base_width_median": 3.0,
        "base_width_max": 3,
        "first_query_date": "2024-01-02",
        "last_query_date": "2024-01-05",
        "raw_feature_count": 17,
        "model_feature_count": 19,
        "unexpected_nonfinite_feature_count": 0,
        "volume_ratio_missing": 2,
        "open_interest_ratio_missing": 1,
        "source_date_violation_count": 0,
        "future_feature_rows_used": 0,
        "minimum_nonzero_cross_section_qids": 3,
        "missing_flag_mismatch_count": 0,
        "forbidden_model_feature_count": 0,
        "label_query_count": 3,
        "label_row_count": 9,
        "label_width_min": 3,
        "label_width_median": 3.0,
        "label_width_max": 3,
        "rejected_label_rows": 3,
        "label_forbidden_column_count": 0,
        "label_identity_violation_count": 0,
        "action_months": 2,
        "formal_anchor_rows": 2,
        "challenger_rows": 4,
        "minimum_challengers_per_month": 2,
        "formal_month_violation_count": 0,
        "fold_count": 2,
        "effect_evaluable_folds": 1,
        "inference_only_folds": 1,
        "minimum_train_qids": 2,
        "maximum_train_qids": 3,
        "first_fold": "2024-01-31",
        "last_fold": "2024-02-29",
        "future_train_qid_count": 0,
        "future_label_rows_used": 0,
        "sealed_holdout_rows": 0,
        "future_close_value_reads": 0,
        "future_return_calculations": 0,
        "label_value_reads": 0,
        "model_fit_count": 0,
        "model_predict_count": 0,
        "strategy_backtest_runs": 0,
        "ctp_connection_count": 0,
        "order_api_called_count": 0,
        "production_files_written": 0,
    }


def test_collect_input_identities_binds_sha_size_mtime_and_detects_drift(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.csv"
    second = tmp_path / "second.json"
    first.write_text("a,b\n1,2\n", encoding="utf-8")
    second.write_text('{"ok": true}\n', encoding="utf-8")
    paths = {"first": first, "second": second}
    expected = {name: _sha256(path) for name, path in paths.items()}

    before = stage001.collect_input_identities(paths, expected)
    after = stage001.collect_input_identities(paths, expected)

    assert before == after
    assert set(before["first"]) == {"path", "sha256", "size", "mtime_ns"}
    first.write_text("a,b\n1,3\n", encoding="utf-8")
    with pytest.raises(stage001.Stage001Error, match="input_sha256_drift:first"):
        stage001.collect_input_identities(paths, expected)


def test_assess_gates_accepts_only_the_exact_label_free_contract() -> None:
    result = stage001.assess_gates(_passing_observed(), expected_counts=_expected())

    assert result["all_gates_passed"] is True
    assert result["decision"] == stage001.PASS_DECISION
    assert all(result["gates"].values())


@pytest.mark.parametrize(
    ("field", "value", "failed_gate"),
    [
        ("input_identity_stable", False, "input_identity_gate"),
        ("base_row_count", 11, "query_gate"),
        ("model_feature_count", 18, "feature_gate"),
        ("label_forbidden_column_count", 1, "label_plan_gate"),
        ("future_train_qid_count", 1, "formal_scoring_fold_gate"),
        ("model_fit_count", 1, "zero_side_effect_gate"),
    ],
)
def test_assess_gates_fail_closes_each_gate_family(
    field: str,
    value: object,
    failed_gate: str,
) -> None:
    observed = _passing_observed()
    observed[field] = value

    result = stage001.assess_gates(observed, expected_counts=_expected())

    assert result["all_gates_passed"] is False
    assert result["decision"] == stage001.FAIL_DECISION
    assert result["gates"][failed_gate] is False


def test_publish_bundle_is_atomic_manifested_and_refuses_existing_final(
    tmp_path: Path,
) -> None:
    line_dir = tmp_path / "line"
    final_dir = line_dir / "artifacts" / "stage001"
    line_dir.mkdir()
    frames = {
        "raw_feature_panel.csv.gz": pd.DataFrame({"query_date": ["2024-01-02"]}),
        "fold_plan.csv": pd.DataFrame({"test_eval_date": ["2024-01-31"]}),
    }
    documents = {
        "summary.json": {"decision": stage001.PASS_DECISION},
        "report.md": "# fixture\n",
    }

    stage001.publish_bundle(
        frames,
        documents,
        line_dir=line_dir,
        final_dir=final_dir,
        input_identities={"fixture": {"sha256": "1" * 64}},
    )

    assert final_dir.is_dir()
    assert not list(final_dir.parent.glob(".stage001.tmp.*"))
    verification = stage001.verify_published_bundle(final_dir)
    assert verification["verified"] is True
    manifest = json.loads((final_dir / "artifact_manifest.json").read_text("utf-8"))
    assert set(manifest["artifacts"]) == {
        "fold_plan.csv",
        "raw_feature_panel.csv.gz",
        "report.md",
        "summary.json",
    }
    with pytest.raises(stage001.Stage001Error, match="final_output_exists"):
        stage001.publish_bundle(
            frames,
            documents,
            line_dir=line_dir,
            final_dir=final_dir,
            input_identities={},
        )


def test_expected_counts_defaults_are_frozen_to_preregistration() -> None:
    expected = stage001.ExpectedCounts()

    assert expected.base_query_count == 1067
    assert expected.base_row_count == 57528
    assert expected.label_query_count == 1046
    assert expected.label_row_count == 52484
    assert expected.fold_count == 37
    assert expected.effect_evaluable_folds == 36
    assert expected.inference_only_folds == 1
    assert replace(expected).raw_feature_count == 17
