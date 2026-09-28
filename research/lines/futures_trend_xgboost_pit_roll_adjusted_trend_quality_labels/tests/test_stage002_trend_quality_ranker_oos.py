from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage002_trend_quality_ranker_oos as stage002


def _prediction_payload() -> tuple[pd.DataFrame, dict[str, object], dict[str, str]]:
    predictions = pd.DataFrame(
        {
            "query_date": pd.to_datetime(["2024-02-29", "2024-02-29"]),
            "product_vt_symbol": ["a.EX", "b.EX"],
            "xgb_score": [0.2, 0.1],
        }
    )
    selection = {
        "test_eval_date": pd.Timestamp("2024-02-29"),
        "anchor_product": "a.EX",
        "challenger_product": "b.EX",
        "selected_product": "a.EX",
        "replaced": False,
    }
    hashes = {"primary": "1" * 64, "repeat": "1" * 64}
    return predictions, selection, hashes


def test_pre_effect_seal_is_exclusive_and_detects_tampering(tmp_path: Path) -> None:
    predictions, selection, hashes = _prediction_payload()

    seal = stage002.write_pre_effect_seal(
        tmp_path,
        test_eval_date=pd.Timestamp("2024-02-29"),
        model_hashes=hashes,
        predictions=predictions,
        selection=selection,
        test_label_rows_read_before_seal=0,
    )

    verified = stage002.verify_pre_effect_seal(
        seal,
        model_hashes=hashes,
        predictions=predictions,
        selection=selection,
    )
    assert verified["test_label_rows_read_before_seal"] == 0
    with pytest.raises(stage002.Stage002Error, match="pre_effect_seal_exists"):
        stage002.write_pre_effect_seal(
            tmp_path,
            test_eval_date=pd.Timestamp("2024-02-29"),
            model_hashes=hashes,
            predictions=predictions,
            selection=selection,
            test_label_rows_read_before_seal=0,
        )
    tampered = predictions.copy()
    tampered.loc[0, "xgb_score"] = 9.0
    with pytest.raises(stage002.Stage002Error, match="pre_effect_seal_mismatch"):
        stage002.verify_pre_effect_seal(
            seal,
            model_hashes=hashes,
            predictions=tampered,
            selection=selection,
        )


def _passing_technical() -> dict[str, object]:
    return {
        "input_identity_stable": True,
        "authorization_valid": True,
        "upstream_bundles_verified": True,
        "label_rows": 55226,
        "label_qids": 1046,
        "fixed_label_rows_excluded": 1046,
        "fixed_path_rows_excluded": 1046,
        "fixed_feature_rows_excluded": 1067,
        "fixed_formal_scoring_rows": 0,
        "relevance_level_failure_count": 0,
        "feature_label_missing_rows": 0,
        "forbidden_feature_count": 0,
        "formal_score_value_read_count": 0,
        "fold_count": 37,
        "fit_call_count": 74,
        "future_train_qid_count": 0,
        "final_train_qid_count": 1045,
        "final_train_row_count": 55168,
        "estimator_audit_passed": True,
        "repeat_prediction_max_abs_difference": 0.0,
        "repeat_model_hash_mismatch_count": 0,
        "constant_prediction_fold_count": 0,
        "zero_split_fold_count": 0,
        "prediction_row_count": 2000,
        "seal_count": 37,
        "verified_seal_count": 37,
        "model_file_identity_mismatch_count": 0,
        "test_label_rows_read_before_seal": 0,
        "effect_fold_count": 36,
        "effect_qids_opened": 36,
        "effect_label_rows_opened": 1940,
        "inference_fold_count": 1,
        "strategy_backtest_runs": 0,
        "sealed_holdout_rows": 0,
        "ctp_connection_count": 0,
        "order_api_called_count": 0,
        "production_files_written": 0,
    }


def test_technical_assessment_requires_every_frozen_counter() -> None:
    assert stage002.assess_technical_gates(_passing_technical())["passed"] is True

    for field, value in _passing_technical().items():
        failed = _passing_technical()
        failed[field] = False if value is True else (1 if value == 0 else 0)
        assert stage002.assess_technical_gates(failed)["passed"] is False, field


def test_execution_event_is_exclusive_and_records_authorization_sha(
    tmp_path: Path,
) -> None:
    event_path = tmp_path / "execution_event.json"

    stage002.create_execution_event(
        event_path,
        authorization_sha256="a" * 64,
        nonce="nonce-1",
    )

    payload = json.loads(event_path.read_text("utf-8"))
    assert payload["authorization_sha256"] == "a" * 64
    assert payload["nonce"] == "nonce-1"
    assert payload["status"] == "started"
    with pytest.raises(stage002.Stage002Error, match="execution_event_exists"):
        stage002.create_execution_event(
            event_path,
            authorization_sha256="a" * 64,
            nonce="nonce-1",
        )


def test_authorization_binds_all_resolved_model_dependencies() -> None:
    paths = stage002._implementation_paths()

    assert {
        "external_ranker_core",
        "external_feature_contract",
        "xgboost_sklearn_source",
        "xgboost_native_library",
    }.issubset(paths)
    assert all(path.is_file() for path in paths.values())
    assert paths["external_ranker_core"].name == "daily_ranker_development.py"
    assert paths["external_feature_contract"].name == "daily_ranker_contract.py"
    assert paths["xgboost_native_library"].name == "libxgboost.dylib"


def test_upstream_validation_accepts_historical_v1_fail_only_via_v2_correction() -> None:
    summaries = {
        "stage001": {
            "decision": stage002.stage001.PASS_DECISION,
            "all_gates_passed": True,
        },
        "expiry": {
            "decision": stage002.stage001.UPSTREAM_PASS_DECISION,
            "all_gates_passed": True,
        },
        "v1": {
            "decision": stage002.v1_stage.FAIL_DECISION,
            "all_gates_passed": False,
        },
        "v2": {
            "decision": stage002.V2_PASS_DECISION,
            "all_gates_passed": True,
            "corrected_contract_decision": stage002.v1_stage.PASS_DECISION,
        },
    }

    stage002._validate_upstream_summaries(summaries)

    broken = {name: dict(value) for name, value in summaries.items()}
    broken["v2"]["corrected_contract_decision"] = "wrong"
    with pytest.raises(stage002.Stage002Error, match="v2_correction"):
        stage002._validate_upstream_summaries(broken)


def test_effect_open_is_persisted_before_downstream_metric_work(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "staging"
    (staging / "models").mkdir(parents=True)
    labels = pd.DataFrame(
        {
            "query_date": ["2024-02-29", "2024-02-29"],
            "product_vt_symbol": ["a.EX", "b.EX"],
            "future_trend_capture_quality": [0.1, 0.2],
            "future_abs_log_return": [0.2, 0.3],
            "future_oriented_max_drawdown": [-0.1, -0.1],
            "trend_quality_relevance": [2, 4],
        }
    )
    paths = labels[["query_date", "product_vt_symbol"]].assign(
        label_end="2024-03-29"
    )
    store = stage002.core.PhaseGatedTrendQualityStore(labels, paths)
    predictions, selection, hashes = _prediction_payload()
    seal = stage002.write_pre_effect_seal(
        staging / "pre_effect_seals",
        test_eval_date=pd.Timestamp("2024-02-29"),
        model_hashes=hashes,
        predictions=predictions,
        selection=selection,
        test_label_rows_read_before_seal=0,
    )
    frames: list[pd.DataFrame] = []

    opened = stage002._open_and_persist_effect_qid(
        staging,
        label_store=store,
        test_date=pd.Timestamp("2024-02-29"),
        seal_path=seal,
        model_hashes=hashes,
        predictions=predictions,
        selection=selection,
        last_completed_fold=None,
        effect_rows=0,
        effect_label_frames=frames,
    )

    assert len(opened) == 2
    audit = json.loads((staging / "label_access_audit.json").read_text("utf-8"))
    assert audit["opened_effect_qids"] == 1
    assert audit["unique_effect_label_rows_opened"] == 2
    persisted = pd.read_csv(staging / "opened_effect_labels.csv.gz")
    assert len(persisted) == 2


def test_final_seal_replay_verifies_models_predictions_and_selection(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "staging"
    models = staging / "models"
    seals = staging / "pre_effect_seals"
    staging.mkdir()
    models.mkdir()
    predictions, selection, _ = _prediction_payload()
    payload = b"same-model"
    model_hash = stage002._sha256_bytes(payload)
    hashes = {"primary": model_hash, "repeat": model_hash}
    (models / "2024-02-29_primary.ubj").write_bytes(payload)
    (models / "2024-02-29_repeat.ubj").write_bytes(payload)
    seal = stage002.write_pre_effect_seal(
        seals,
        test_eval_date=pd.Timestamp("2024-02-29"),
        model_hashes=hashes,
        predictions=predictions,
        selection=selection,
        test_label_rows_read_before_seal=0,
    )
    fold_audits = [
        {
            "test_eval_date": pd.Timestamp("2024-02-29"),
            "primary_model_sha256": model_hash,
            "repeat_model_sha256": model_hash,
            "pre_effect_seal_sha256": stage002.publisher.sha256_file(seal),
        }
    ]
    stage002._write_csv(predictions, staging / "predictions.csv.gz")
    stage002._write_csv(pd.DataFrame([selection]), staging / "monthly_selections.csv")
    stage002._write_csv(pd.DataFrame(fold_audits), staging / "fold_audit.csv")

    result = stage002.verify_all_pre_effect_seals(staging)

    assert result == {
        "verified_seal_count": 1,
        "model_file_identity_mismatch_count": 0,
    }
    (models / "2024-02-29_primary.ubj").write_bytes(b"tampered")
    with pytest.raises(stage002.Stage002Error, match="model_file_identity"):
        stage002.verify_all_pre_effect_seals(staging)
    (models / "2024-02-29_primary.ubj").write_bytes(payload)
    persisted_predictions = pd.read_csv(staging / "predictions.csv.gz")
    persisted_predictions.loc[0, "xgb_score"] = 9.0
    stage002._write_csv(persisted_predictions, staging / "predictions.csv.gz")
    with pytest.raises(stage002.Stage002Error, match="pre_effect_seal_mismatch"):
        stage002.verify_all_pre_effect_seals(staging)


def _authorization_fixture() -> dict[str, object]:
    return {
        "line_id": stage002.LINE_ID,
        "stage": stage002.STAGE,
        "authorized": True,
        "nonce": "fixture-nonce",
    }


def test_event_is_consumed_before_input_loading_and_load_failure_is_manifested(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    line_dir = tmp_path / "line"
    output_dir = line_dir / "artifacts" / "final"
    event_path = line_dir / "artifacts" / "event.json"
    authorization_path = line_dir / "stages" / "authorization.json"
    authorization_path.parent.mkdir(parents=True)
    authorization_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        stage002,
        "verify_authorization",
        lambda *_args, **_kwargs: _authorization_fixture(),
    )

    def fail_loading(_paths: object) -> dict[str, object]:
        assert event_path.is_file()
        raise stage002.Stage002Error("fixture_load_failure")

    monkeypatch.setattr(stage002, "_load_inputs", fail_loading)

    summary = stage002.run_stage002(
        line_dir=line_dir,
        output_dir=output_dir,
        authorization_path=authorization_path,
        execution_event_path=event_path,
        input_paths={},
        expected_sha256={},
    )

    assert summary["decision"] == stage002.TECHNICAL_FAIL_DECISION
    assert summary["failure_phase"] == "before_progress_initialization"
    assert stage002.verify_published_bundle(output_dir)["verified"] is True
    event = json.loads(event_path.read_text("utf-8"))
    assert event["status"] == "completed"


def test_partial_failure_bundle_preserves_models_seals_and_label_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    line_dir = tmp_path / "line"
    output_dir = line_dir / "artifacts" / "final"
    event_path = line_dir / "artifacts" / "event.json"
    authorization_path = line_dir / "stages" / "authorization.json"
    authorization_path.parent.mkdir(parents=True)
    authorization_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        stage002,
        "verify_authorization",
        lambda *_args, **_kwargs: _authorization_fixture(),
    )
    monkeypatch.setattr(stage002, "_load_inputs", lambda _paths: {})

    def fail_after_partial_evidence(
        staging: Path, **_kwargs: object
    ) -> dict[str, object]:
        (staging / "models").mkdir(parents=True)
        (staging / "pre_effect_seals").mkdir()
        (staging / "models" / "fold_primary.ubj").write_bytes(b"model")
        (staging / "pre_effect_seals" / "2024-03-29.json").write_text(
            "{}\n", encoding="utf-8"
        )
        stage002._write_json(
            staging / "label_access_audit.json",
            {"unique_effect_label_rows_opened": 55, "opened_effect_qids": 1},
        )
        stage002._write_json(
            staging / "run_progress.json",
            {
                "phase": "effect_labels_opened",
                "current_test_date": "2024-03-29",
                "last_completed_fold": "2024-02-29",
            },
        )
        raise stage002.Stage002Error("fixture_partial_failure")

    monkeypatch.setattr(stage002, "_execute_stage002", fail_after_partial_evidence)

    summary = stage002.run_stage002(
        line_dir=line_dir,
        output_dir=output_dir,
        authorization_path=authorization_path,
        execution_event_path=event_path,
        input_paths={},
        expected_sha256={},
    )

    assert summary["effect"]["not_opened"] is False
    assert summary["effect"]["partial_effect_label_rows_opened"] == 55
    assert summary["last_completed_fold"] == "2024-02-29"
    assert (output_dir / "models" / "fold_primary.ubj").is_file()
    assert (output_dir / "pre_effect_seals" / "2024-03-29.json").is_file()
    assert stage002.verify_published_bundle(output_dir)["verified"] is True
