from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage003_lossless_evidence_recovery as stage003


def test_prediction_hex_round_trip_is_bit_exact() -> None:
    frame = pd.DataFrame(
        {
            "query_date": pd.to_datetime(["2024-01-31"] * 4),
            "product_vt_symbol": ["a.EX", "b.EX", "c.EX", "d.EX"],
            "xgb_score": [0.1, -0.0, np.nextafter(1.0, 2.0), -3.25],
            "train_qid_count": [10] * 4,
            "train_row_count": [500] * 4,
        }
    )

    encoded = stage003.encode_predictions_hex(frame)
    decoded = stage003.decode_predictions_hex(encoded)

    assert encoded.columns.tolist() == [
        "query_date",
        "product_vt_symbol",
        "xgb_score_hex",
        "train_qid_count",
        "train_row_count",
    ]
    assert np.array_equal(
        frame["xgb_score"].to_numpy(dtype="float64").view("uint64"),
        decoded["xgb_score"].to_numpy(dtype="float64").view("uint64"),
    )
    pd.testing.assert_frame_equal(frame, decoded)


def test_stage002_control_evidence_requires_exact_failed_run_identity() -> None:
    summary = {
        "decision": stage003.stage002.TECHNICAL_FAIL_DECISION,
        "error": "pre_effect_seal_mismatch",
        "failure_phase": "fold_completed",
        "authorization_nonce": "nonce-1",
        "seal_count": 37,
        "model_file_count": 74,
    }
    event = {
        "status": "completed",
        "decision": stage003.stage002.TECHNICAL_FAIL_DECISION,
        "nonce": "nonce-1",
        "final_manifest_sha256": "a" * 64,
    }

    result = stage003.validate_stage002_control_evidence(
        summary,
        event,
        manifest_sha256="a" * 64,
        manifest_artifact_count=159,
        manifest_model_count=74,
        manifest_seal_count=37,
        manifest_access_event_count=36,
    )

    assert result["passed"] is True
    broken = dict(event)
    broken["nonce"] = "wrong"
    with pytest.raises(stage003.Stage003Error, match="nonce"):
        stage003.validate_stage002_control_evidence(
            summary,
            broken,
            manifest_sha256="a" * 64,
            manifest_artifact_count=159,
            manifest_model_count=74,
            manifest_seal_count=37,
            manifest_access_event_count=36,
        )


def test_access_events_require_opened_rows_and_matching_seals(tmp_path: Path) -> None:
    seals = tmp_path / "pre_effect_seals"
    events = tmp_path / "effect_access_events"
    seals.mkdir()
    events.mkdir()
    seal = seals / "2024-01-31.json"
    seal.write_text("{}\n", encoding="utf-8")
    seal_sha = stage003.publisher.sha256_file(seal)
    stage003._write_json(
        events / "2024-01-31.json",
        {
            "test_eval_date": "2024-01-31",
            "status": "opened",
            "expected_row_count": 50,
            "opened_row_count": 50,
            "seal_sha256": seal_sha,
            "opened_labels_sha256": "b" * 64,
        },
    )

    result = stage003.validate_access_events(events, seals)

    assert result == {
        "access_event_count": 1,
        "opened_access_event_count": 1,
        "access_event_row_count": 50,
        "access_event_mismatch_count": 0,
    }
    payload = stage003._read_json(events / "2024-01-31.json")
    payload.pop("opened_labels_sha256")
    stage003._write_json(events / "2024-01-31.json", payload)
    with pytest.raises(stage003.Stage003Error, match="access_event"):
        stage003.validate_access_events(events, seals)
    payload["opened_labels_sha256"] = "b" * 64
    payload["opened_row_count"] = 49
    stage003._write_json(events / "2024-01-31.json", payload)
    with pytest.raises(stage003.Stage003Error, match="access_event"):
        stage003.validate_access_events(events, seals)


def _passing_technical() -> dict[str, object]:
    return {
        "input_identity_stable": True,
        "stage002_bundle_verified": True,
        "stage002_control_evidence_valid": True,
        "stage002_authorization_valid": True,
        "fold_count": 37,
        "model_file_count": 74,
        "seal_count": 37,
        "access_event_count": 36,
        "opened_access_event_count": 36,
        "access_event_row_count": 1940,
        "access_event_mismatch_count": 0,
        "model_fit_count": 0,
        "model_load_count": 74,
        "model_predict_count": 74,
        "model_file_identity_mismatch_count": 0,
        "repeat_prediction_bit_mismatch_fold_count": 0,
        "prediction_seal_match_count": 37,
        "selection_seal_match_count": 37,
        "lossless_prediction_row_count": 2000,
        "lossless_prediction_bit_mismatch_count": 0,
        "lossless_seal_replay_count": 37,
        "label_rows": 55226,
        "label_qids": 1046,
        "final_train_row_count": 55168,
        "final_train_qid_count": 1045,
        "effect_label_rows": 1940,
        "strategy_backtest_runs": 0,
        "sealed_holdout_rows": 0,
        "ctp_connection_count": 0,
        "order_api_called_count": 0,
        "production_files_written": 0,
    }


def test_recovery_technical_gate_requires_every_preregistered_counter() -> None:
    assert stage003.assess_recovery_technical_gates(_passing_technical())[
        "passed"
    ] is True

    for field, value in _passing_technical().items():
        failed = _passing_technical()
        failed[field] = False if value is True else (1 if value == 0 else 0)
        assert stage003.assess_recovery_technical_gates(failed)["passed"] is False, field


def test_recovery_runner_source_has_no_fit_call() -> None:
    source = Path(stage003.__file__).read_text(encoding="utf-8")
    assert ".fit(" not in source


def test_authorization_explicitly_binds_publisher_source() -> None:
    paths = stage003._implementation_paths()
    assert paths["publisher_source"] == stage003.PUBLISHER_SOURCE_PATH
    assert paths["publisher_source"].name == "stage001_daily_ranker_contract.py"
    assert paths["publisher_source"].is_file()


def test_progress_write_is_atomic_and_directory_synced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    replace_calls: list[tuple[Path, Path]] = []
    file_fsync_calls: list[int] = []
    directory_fsync_calls: list[Path] = []
    original_replace = stage003.os.replace
    original_fsync = stage003.os.fsync

    def tracked_replace(source: Path, target: Path) -> None:
        replace_calls.append((Path(source), Path(target)))
        original_replace(source, target)

    def tracked_fsync(descriptor: int) -> None:
        file_fsync_calls.append(descriptor)
        original_fsync(descriptor)

    monkeypatch.setattr(stage003.os, "replace", tracked_replace)
    monkeypatch.setattr(stage003.os, "fsync", tracked_fsync)
    monkeypatch.setattr(
        stage003,
        "_fsync_directory",
        lambda directory: directory_fsync_calls.append(Path(directory)),
    )

    stage003._write_progress(
        tmp_path,
        phase="test",
        effect_labels_opened=True,
        effect_label_rows=7,
        effect_qids_opened=1,
    )

    target = tmp_path / "run_progress.json"
    assert target.is_file()
    assert len(replace_calls) == 1
    assert replace_calls[0][1] == target
    assert replace_calls[0][0].name.startswith(".run_progress.json.tmp.")
    assert file_fsync_calls
    assert directory_fsync_calls == [tmp_path]
    assert not list(tmp_path.glob(".run_progress.json.tmp.*"))


def test_effect_open_failure_is_conservatively_persisted(tmp_path: Path) -> None:
    class FailingStore:
        @staticmethod
        def qid_row_count(test_date: pd.Timestamp) -> int:
            return 7

        @staticmethod
        def open_effect_qid(test_date: pd.Timestamp) -> pd.DataFrame:
            raise RuntimeError("injected_open_failure")

    test_date = pd.Timestamp("2024-01-31")
    with pytest.raises(RuntimeError, match="injected_open_failure"):
        stage003._open_effect_qid_with_progress(
            tmp_path,
            label_store=FailingStore(),
            test_date=test_date,
            effect_label_rows=50,
            effect_qids_opened=1,
        )

    progress = stage003._read_json(tmp_path / "run_progress.json")
    assert progress["phase"] == "effect_label_qid_opening"
    assert progress["effect_labels_opened"] is True
    assert progress["effect_label_rows"] == 57
    assert progress["effect_qids_opened"] == 2
    assert progress["current_test_date"] == "2024-01-31"


def test_frozen_stage002_models_and_seals_replay_losslessly(tmp_path: Path) -> None:
    identities = stage003.publisher.collect_input_identities(
        stage003.DEFAULT_INPUT_PATHS,
        stage003.DEFAULT_EXPECTED_SHA256,
    )
    evidence = stage003._verify_stage002_bundle(identities)
    fold_audit, fold_plan, features, scoring = stage003._load_replay_frames(
        stage003.DEFAULT_INPUT_PATHS
    )

    replay = stage003._reconstruct_predictions_and_selections(
        tmp_path,
        fold_audit=fold_audit,
        fold_plan=fold_plan,
        model_features=features,
        formal_scoring=scoring,
    )

    assert evidence["stage002_bundle_verified"] is True
    assert replay["fold_count"] == 37
    assert replay["model_fit_count"] == 0
    assert replay["model_load_count"] == 74
    assert replay["model_predict_count"] == 74
    assert replay["repeat_prediction_bit_mismatch_fold_count"] == 0
    assert replay["prediction_seal_match_count"] == 37
    assert replay["selection_seal_match_count"] == 37
    assert replay["lossless_prediction_row_count"] == 2_000
    assert replay["lossless_prediction_bit_mismatch_count"] == 0
    assert replay["lossless_seal_replay_count"] == 37
