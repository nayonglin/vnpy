from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage001_label_free_contract as stage001


def _passing_metrics() -> dict[str, object]:
    return {
        "current_release_id": stage001.EXPECTED_RELEASE_ID,
        "current_strategy_id": stage001.EXPECTED_STRATEGY_ID,
        "current_pointer_matches_release": True,
        "m0004_m0005_model_code_equal": True,
        "m0004_m0005_runner_code_equal": True,
        "feature_count": 108,
        "train_months": 77,
        "train_rows": 1386,
        "minimum_products_per_train_month": 18,
        "maximum_products_per_train_month": 18,
        "nonfinite_feature_cells": 0,
        "historical_parity_months": 76,
        "historical_parity_rows": 1368,
        "historical_parity_max_abs_error": 0.0,
        "latest_pool_parity_rows": 11,
        "latest_pool_parity_max_abs_error": 0.0,
        "active_folds": 50,
        "minimum_train_months": 24,
        "pit_violation_rows": 0,
        "pit_violation_folds": 0,
        "forbidden_columns_read_count": 0,
        "future_label_value_read_count": 0,
        "model_fit_count": 0,
        "model_predict_count": 0,
        "strategy_backtest_count": 0,
        "ctp_connection_count": 0,
        "order_api_call_count": 0,
        "production_write_count": 0,
        "input_identity_mismatch_count": 0,
    }


@pytest.mark.parametrize(
    "column",
    ["future_net_pnl_60d", "target_future_top_half_60d", "sample_weight_future_rank_60d"],
)
def test_csv_projection_rejects_forbidden_columns(column: str) -> None:
    with pytest.raises(stage001.Stage001Error, match="forbidden_column"):
        stage001.assert_allowed_columns(["eval_date", "product_vt_symbol", column])


def test_gate_assessment_accepts_exact_contract() -> None:
    result = stage001.assess_gates(_passing_metrics())

    assert result["all_gates_passed"] is True
    assert result["failures"] == []
    assert result["decision"] == stage001.PASS_DECISION


@pytest.mark.parametrize(
    ("field", "value", "failure"),
    [
        ("historical_parity_max_abs_error", 1e-4, "historical_feature_parity"),
        ("latest_pool_parity_rows", 10, "latest_pool_feature_parity"),
        ("active_folds", 47, "pit_fold_count"),
        ("model_fit_count", 1, "stage001_side_effect_free"),
        ("input_identity_mismatch_count", 1, "input_identity"),
    ],
)
def test_gate_assessment_fails_closed(field: str, value: object, failure: str) -> None:
    metrics = _passing_metrics()
    metrics[field] = value

    result = stage001.assess_gates(metrics)

    assert result["all_gates_passed"] is False
    assert failure in result["failures"]
    assert result["decision"] == stage001.FAIL_DECISION


def test_output_must_be_inside_line(tmp_path: Path) -> None:
    line = tmp_path / "line"
    line.mkdir()

    with pytest.raises(stage001.Stage001Error, match="output_outside_line"):
        stage001.assert_line_local_output(line, tmp_path / "elsewhere")


def test_release_csv_import_override_is_process_local_and_restored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", raising=False)

    with stage001.release_csv_import_environment():
        assert os.environ["QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR"] == "1"

    assert "QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR" not in os.environ


def test_release_csv_import_override_restores_existing_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "original")

    with pytest.raises(RuntimeError, match="boom"):
        with stage001.release_csv_import_environment():
            assert os.environ["QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR"] == "1"
            raise RuntimeError("boom")

    assert os.environ["QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR"] == "original"


def test_publish_refuses_existing_final(tmp_path: Path) -> None:
    line = tmp_path / "line"
    final = line / "artifacts" / "stage001"
    final.mkdir(parents=True)

    with pytest.raises(stage001.Stage001Error, match="final_output_exists"):
        stage001.publish_evidence_bundle(
            line_dir=line,
            final_dir=final,
            summary={"decision": stage001.PASS_DECISION},
            feature_contract={"feature_count": 108},
            fold_rows=[],
            input_identities={},
        )


def test_publish_and_verify_manifest_round_trip(tmp_path: Path) -> None:
    line = tmp_path / "line"
    line.mkdir()
    final = line / "artifacts" / "stage001"

    stage001.publish_evidence_bundle(
        line_dir=line,
        final_dir=final,
        summary={"decision": stage001.PASS_DECISION, "all_gates_passed": True},
        feature_contract={"feature_count": 108, "features": ["x"]},
        fold_rows=[{"test_eval_date": "2024-01-31", "train_months": 24}],
        input_identities={"source": {"sha256": "abc", "size": 1}},
    )

    verification = stage001.verify_evidence_bundle(final)
    manifest = json.loads((final / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert verification["valid"] is True
    assert verification["errors"] == []
    assert sorted(manifest["files"]) == [
        "feature_contract.json",
        "fold_plan.csv",
        "input_identities.json",
        "report.md",
        "summary.json",
    ]
