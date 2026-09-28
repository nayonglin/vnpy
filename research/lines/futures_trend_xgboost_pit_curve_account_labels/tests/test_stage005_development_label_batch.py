from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
import hashlib
import json
import sys

import pandas as pd
import pytest


TOOL_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import stage005_development_label_batch as module  # noqa: E402


def test_stage005_uses_stage005a_v2_frozen_runtime_inputs() -> None:
    assert module.RUNTIME_ROOT == module.runtime_v2.RUNTIME_ROOT
    assert module.RUNTIME_DATABASE == module.runtime_v2.RUNTIME_DATABASE
    assert module.RUNTIME_SETTING == module.runtime_v2.RUNTIME_SETTING
    assert module.PRODUCTION_DATABASE == module.runtime_v2.FROZEN_SOURCE_DATABASE
    assert module.EXPECTED_DATABASE_SHA256 == module.runtime_v2.EXPECTED_DATABASE_SHA256
    assert module.FROZEN_MAPPING == module.runtime_v2.FROZEN_MAPPING
    assert module.FROZEN_MINUTE_BARS == module.runtime_v2.FROZEN_MINUTE_BARS
    assert module.FROZEN_CONTRACT_METADATA == module.runtime_v2.FROZEN_CONTRACT_METADATA


def test_stage005_static_inputs_bind_successful_v2_smoke_and_postrun_review() -> None:
    paths = module._static_paths()

    assert paths["stage005a_runtime_receipt"] == module.runtime_v2.RUNTIME_RECEIPT
    assert paths["stage005a_smoke_receipt"] == module.STAGE005A_SMOKE_RECEIPT
    assert paths["stage005a_scope_audit"] == module.STAGE005A_SCOPE_AUDIT
    assert paths["stage005a_postrun_review"] == module.STAGE005A_POSTRUN_REVIEW
    assert (
        paths["stage005a_postrun_review_decision"]
        == module.STAGE005A_POSTRUN_REVIEW_DECISION
    )


def test_stage005_worker_entry_preserves_injected_job_environment(
    tmp_path: Path, monkeypatch
) -> None:
    job_id = "20220128_R10"
    campaign = tmp_path / "campaign_001"
    run_root = tmp_path / campaign.name / job_id / "run_001"
    tmpdir = run_root / "tmp"
    mplconfig = run_root / "mplconfig"
    tmpdir.mkdir(parents=True)
    mplconfig.mkdir()
    monkeypatch.setattr(module, "TMP_ROOT", tmp_path)
    monkeypatch.setenv("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
    monkeypatch.setenv("TMPDIR", str(tmpdir))
    monkeypatch.setenv("MPLCONFIGDIR", str(mplconfig))
    monkeypatch.setattr(
        module,
        "_install_parent_environment",
        lambda: (_ for _ in ()).throw(AssertionError("worker clobbered env")),
    )
    monkeypatch.setattr(module, "_verify_run_authorization", lambda: {})
    monkeypatch.setattr(module, "_v2_runtime_gate", lambda: {})
    monkeypatch.setattr(module, "_campaign_target", lambda path: campaign)
    monkeypatch.setattr(
        module, "_authorization_campaign_gate", lambda authorization, path: {}
    )
    observed: dict[str, str] = {}

    class FakeLegacy:
        @staticmethod
        def _exclusive_lock(path):
            return nullcontext()

        @staticmethod
        def _run_worker(selected_job_id, target):
            observed["job_id"] = selected_job_id
            observed["tmpdir"] = module.os.environ["TMPDIR"]
            observed["mplconfigdir"] = module.os.environ["MPLCONFIGDIR"]

    monkeypatch.setattr(module, "_configure_legacy", lambda: FakeLegacy())

    module.run_worker(job_id, campaign)

    assert observed == {
        "job_id": job_id,
        "tmpdir": str(tmpdir),
        "mplconfigdir": str(mplconfig),
    }


def test_stage005_worker_environment_gate_rejects_orchestrator_paths(
    tmp_path: Path, monkeypatch
) -> None:
    campaign = tmp_path / "campaign_001"
    orchestrator = tmp_path / "orchestrator"
    monkeypatch.setattr(module, "TMP_ROOT", tmp_path)
    monkeypatch.setenv("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
    monkeypatch.setenv("TMPDIR", str(orchestrator / "tmp"))
    monkeypatch.setenv("MPLCONFIGDIR", str(orchestrator / "mplconfig"))

    with pytest.raises(module.Stage005Error, match="worker_environment_invalid"):
        module._worker_environment_gate(campaign, "20220128_R10")


def test_worker_command_uses_stage005_entry_for_evidence_capture() -> None:
    command = module.worker_command(Path("/private/tmp/campaign"), "20220128_R10")

    assert command[0] == sys.executable
    assert command[1] == "-B"
    assert Path(command[2]).resolve() == Path(module.__file__).resolve()
    assert command[3:] == [
        "--worker",
        "20220128_R10",
        "--campaign-dir",
        "/private/tmp/campaign",
    ]


class _FakeLegacy:
    @staticmethod
    def _period_rows(
        frame: pd.DataFrame, *, through: pd.Timestamp
    ) -> pd.DataFrame:
        return frame.loc[frame["date"].le(through)].reset_index(drop=True)

    @staticmethod
    def _canonical_payload(frame: pd.DataFrame) -> pd.DataFrame:
        return frame.drop(columns=["runtime_id"], errors="ignore").reset_index(
            drop=True
        )

    @staticmethod
    def _validate_completed_job(
        campaign_dir: Path, job: pd.Series, campaign_contract: str
    ) -> bool:
        return campaign_contract == "a" * 64


def test_predecision_capture_persists_only_rows_available_by_eval_date(
    tmp_path: Path,
) -> None:
    payloads = {
        name: pd.DataFrame(
            {
                "date": [pd.Timestamp("2022-01-28"), pd.Timestamp("2022-02-01")],
                "value": [index, index + 10],
                "runtime_id": ["A", "B"],
            }
        )
        for index, name in enumerate(module.PREDECISION_NAMES)
    }
    expected = module.expected_predecision_signatures(
        _FakeLegacy,
        payloads,
        pd.Timestamp("2022-01-28"),
    )

    actual = module.persist_predecision_evidence(
        _FakeLegacy,
        payloads,
        pd.Timestamp("2022-01-28"),
        tmp_path,
        expected,
    )

    assert actual == expected
    for name in module.PREDECISION_NAMES:
        stored = pd.read_csv(tmp_path / f"{name}.csv")
        assert len(stored) == 1
        assert "runtime_id" not in stored


def test_frozen_stage005_jobs_and_holdout_are_disjoint() -> None:
    jobs = module._jobs_contract()

    assert len(jobs) == 270
    assert int(jobs["job_type"].eq("main").sum()) == 266
    assert int(jobs["job_type"].eq("A2_sentinel").sum()) == 4
    assert jobs["eval_date"].nunique() == 35
    assert set(jobs["split"]) == {"development"}
    assert len(module._holdout_dates()) == 12
    assert set(jobs["eval_date"].astype(str)).isdisjoint(module._holdout_dates())


def test_stage005_static_inputs_remain_byte_frozen() -> None:
    identities = module._verify_static_inputs()

    assert set(identities) == set(module.EXPECTED_STATIC_SHA256)
    assert all(len(value["sha256"]) == 64 for value in identities.values())


def test_attempt_gate_covers_active_validation_and_requires_final_end(
    tmp_path: Path,
) -> None:
    module.batch_core.write_attempt_start(
        tmp_path,
        attempt_id="attempt_001",
        campaign_contract_sha256="a" * 64,
        completed_job_ids=[],
        pending_job_ids=["J1"],
        worker_commands=[["python", "runner.py", "--worker", "J1"]],
    )
    module.batch_core.write_attempt_end(
        tmp_path,
        attempt_id="attempt_001",
        status="failed",
        completed_job_ids=[],
        error="failed",
    )
    module.batch_core.write_attempt_start(
        tmp_path,
        attempt_id="attempt_002",
        campaign_contract_sha256="a" * 64,
        completed_job_ids=["J1"],
        pending_job_ids=[],
        worker_commands=[],
    )

    active = module._attempt_receipt_gate(
        tmp_path, active_attempt_id="attempt_002"
    )
    assert active["passed"] is True
    assert active["mode"] == "active_validation"
    assert module._attempt_receipt_gate(tmp_path)["passed"] is False

    module.batch_core.write_attempt_end(
        tmp_path,
        attempt_id="attempt_002",
        status="complete",
        completed_job_ids=["J1"],
        error=None,
    )
    final = module._attempt_receipt_gate(tmp_path)
    assert final["passed"] is True
    assert final["mode"] == "finalized"


def test_attempt_gate_rejects_post_completion_failure_receipt(
    tmp_path: Path,
) -> None:
    module.batch_core.write_attempt_start(
        tmp_path,
        attempt_id="attempt_001",
        campaign_contract_sha256="a" * 64,
        completed_job_ids=["J1"],
        pending_job_ids=[],
        worker_commands=[],
    )
    module.batch_core.write_attempt_end(
        tmp_path,
        attempt_id="attempt_001",
        status="complete",
        completed_job_ids=["J1"],
        error=None,
    )
    (tmp_path / "attempts/attempt_001_post_failure.json").write_text(
        json.dumps({"attempt_id": "attempt_001", "error": "manifest failed"})
        + "\n",
        encoding="utf-8",
    )

    audit = module._attempt_receipt_gate(tmp_path)

    assert audit["passed"] is False
    assert audit["post_failure_count"] == 1


def test_attempt_gate_uses_sequence_not_pid_lexical_order(
    tmp_path: Path,
) -> None:
    older = "attempt_20260902T203000+0800_99999_100"
    newer = "attempt_20260902T203000+0800_00001_200"
    module.batch_core.write_attempt_start(
        tmp_path,
        attempt_id=older,
        campaign_contract_sha256="a" * 64,
        completed_job_ids=[],
        pending_job_ids=["J1"],
        worker_commands=[],
    )
    module.batch_core.write_attempt_end(
        tmp_path,
        attempt_id=older,
        status="complete",
        completed_job_ids=["J1"],
        error=None,
    )
    module.batch_core.write_attempt_start(
        tmp_path,
        attempt_id=newer,
        campaign_contract_sha256="a" * 64,
        completed_job_ids=["J1"],
        pending_job_ids=[],
        worker_commands=[],
    )
    module.batch_core.write_attempt_end(
        tmp_path,
        attempt_id=newer,
        status="failed",
        completed_job_ids=["J1"],
        error="newer attempt failed",
    )

    audit = module._attempt_receipt_gate(tmp_path)

    assert audit["passed"] is False
    assert audit["latest_attempt_id"] == newer
    assert audit["final_status"] == "failed"
    assert audit["statuses"] == ["complete", "failed"]


def test_attempt_gate_rejects_malformed_complete_end_receipt(
    tmp_path: Path,
) -> None:
    attempt_id = "attempt_001"
    module.batch_core.write_attempt_start(
        tmp_path,
        attempt_id=attempt_id,
        campaign_contract_sha256="a" * 64,
        completed_job_ids=[],
        pending_job_ids=["J1"],
        worker_commands=[],
    )
    module.batch_core.write_attempt_end(
        tmp_path,
        attempt_id=attempt_id,
        status="complete",
        completed_job_ids=["J1"],
        error=None,
    )
    end_path = tmp_path / "attempts/attempt_001_end.json"
    payload = json.loads(end_path.read_text(encoding="utf-8"))
    payload["completed_job_count_after"] = 999
    payload["error"] = "complete must not carry an error"
    end_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    audit = module._attempt_receipt_gate(tmp_path)

    assert audit["passed"] is False
    assert audit["receipt_shape_valid"] is False


def test_attempt_gate_rejects_non_integer_counts_and_empty_commands(
    tmp_path: Path,
) -> None:
    cases = (
        ("start", "same_campaign_revalidated_job_count", True),
        ("start", "pending_job_count", 1.0),
        ("end", "completed_job_count_after", 2.0),
        ("start", "worker_commands", [[]]),
    )
    for index, (phase, field, value) in enumerate(cases):
        campaign = tmp_path / f"case_{index}"
        attempt_id = "attempt_001"
        module.batch_core.write_attempt_start(
            campaign,
            attempt_id=attempt_id,
            campaign_contract_sha256="a" * 64,
            completed_job_ids=["J0"],
            pending_job_ids=["J1"],
            worker_commands=[["python", "runner.py"]],
        )
        module.batch_core.write_attempt_end(
            campaign,
            attempt_id=attempt_id,
            status="complete",
            completed_job_ids=["J0", "J1"],
            error=None,
        )
        path = campaign / "attempts" / f"{attempt_id}_{phase}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload[field] = value
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

        audit = module._attempt_receipt_gate(campaign)

        assert audit["passed"] is False, (phase, field, value)
        assert audit["receipt_shape_valid"] is False


def test_stage005_authorization_is_consumed_for_exactly_one_campaign(
    tmp_path: Path, monkeypatch
) -> None:
    consumption = tmp_path / "authorization_consumption.json"
    monkeypatch.setattr(module, "AUTHORIZATION_CONSUMPTION", consumption)
    authorization = {
        "authorization_sha256": "b" * 64,
        "campaign_nonce": "a" * 64,
        "scope": "one_new_stage005_campaign_only",
    }

    assert module._authorization_unconsumed_gate(authorization)["passed"] is True
    receipt = module._consume_campaign_authorization(
        authorization, "campaign_001"
    )
    assert receipt["campaign_id"] == "campaign_001"
    assert module._authorization_campaign_gate(
        authorization, tmp_path / "campaign_001"
    )["passed"] is True

    with pytest.raises(FileExistsError, match="append_only_receipt_exists"):
        module._consume_campaign_authorization(authorization, "campaign_002")
    with pytest.raises(module.Stage005Error, match="consumption_mismatch"):
        module._authorization_campaign_gate(
            authorization, tmp_path / "campaign_002"
        )


def test_quantized_money_delta_quantizes_each_operand_first() -> None:
    assert module._quantized_money_delta(0.0000006, 0.0) == 0.000001
    assert module._quantized_money_delta(0.0, 0.0000006) == -0.000001


def test_complete_attempt_keeps_receipt_active_until_aggregate_finishes(
    tmp_path: Path, monkeypatch
) -> None:
    module.batch_core.write_attempt_start(
        tmp_path,
        attempt_id="attempt_001",
        campaign_contract_sha256="a" * 64,
        completed_job_ids=["J1"],
        pending_job_ids=[],
        worker_commands=[],
    )
    observed: list[str] = []

    def fake_aggregate(legacy, campaign_dir, identity, *, active_attempt_id):
        assert active_attempt_id == "attempt_001"
        assert not (campaign_dir / "attempts/attempt_001_end.json").exists()
        observed.append("aggregate")
        return {"passed": True}

    def fake_finalize(campaign_dir, attempt_id):
        assert attempt_id == "attempt_001"
        end = json.loads(
            (campaign_dir / "attempts/attempt_001_end.json").read_text(
                encoding="utf-8"
            )
        )
        assert end["status"] == "complete"
        observed.append("finalize")
        return {"passed": True}

    monkeypatch.setattr(module, "aggregate_campaign", fake_aggregate)
    monkeypatch.setattr(module, "_finalize_completed_attempt", fake_finalize)

    result = module._complete_attempt_with_aggregate(
        object(),
        tmp_path,
        {"file_contract_sha256": "a" * 64},
        attempt_id="attempt_001",
        completed_job_ids=["J1"],
    )

    assert result == {"passed": True}
    assert observed == ["aggregate", "finalize"]


def test_validate_only_creates_a_zero_worker_command_attempt(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "attempts").mkdir()
    pd.DataFrame([{"job_id": "J1"}]).to_csv(
        tmp_path / "jobs.csv", index=False
    )
    identity = {"file_contract_sha256": "a" * 64}
    monkeypatch.setattr(module, "_install_parent_environment", lambda: {})
    monkeypatch.setattr(module, "_configure_legacy", lambda: object())
    monkeypatch.setattr(module, "_campaign_target", lambda path: path)
    monkeypatch.setattr(
        module, "_resume_identity_gate", lambda legacy, path: identity
    )
    monkeypatch.setattr(
        module,
        "_completed_job_ids",
        lambda legacy, path, jobs, contract: {"J1"},
    )

    def fake_complete(
        legacy,
        campaign_dir,
        identity_before,
        *,
        attempt_id,
        completed_job_ids,
    ):
        start = json.loads(
            next((campaign_dir / "attempts").glob("*_start.json")).read_text(
                encoding="utf-8"
            )
        )
        assert start["pending_job_ids_before"] == []
        assert start["worker_commands"] == []
        assert completed_job_ids == ["J1"]
        return {"passed": True, "attempt_id": attempt_id}

    monkeypatch.setattr(module, "_complete_attempt_with_aggregate", fake_complete)

    result = module.validate_campaign(tmp_path)

    assert result["passed"] is True


def test_runner_authorization_rejects_structured_block_decision(
    tmp_path: Path, monkeypatch
) -> None:
    review = tmp_path / "review.md"
    review.write_text(
        "BLOCK_STAGE005_BATCH; explanatory text: ALLOW_STAGE005_BATCH\n",
        encoding="utf-8",
    )
    review_decision = tmp_path / "review_decision.json"
    review_decision.write_text(
        json.dumps(
            {
                "decision": "BLOCK_STAGE005_BATCH",
                "severity": {"P0": 0, "P1": 1, "P2": 0, "P3": 0},
                "review_path": str(review.resolve()),
                "review_sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    authorization = tmp_path / "authorization.json"
    authorization.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(module, "PRERUN_REVIEW", review)
    monkeypatch.setattr(module, "PRERUN_REVIEW_DECISION", review_decision)
    monkeypatch.setattr(module, "RUN_AUTHORIZATION", authorization)

    with pytest.raises(module.Stage005Error, match="not_allowing_batch"):
        module._verify_run_authorization()


def test_final_scope_fields_are_derived_from_observed_counts() -> None:
    fields = module._decision_scope_fields(
        {
            "holdout_label_count": 2,
            "model_training_command_count": 1,
            "model_artifact_count": 3,
            "model_training_log_event_count": 1,
            "ctp_connect_command_count": 0,
            "ctp_connect_log_event_count": 1,
            "order_command_count": 2,
            "order_log_event_count": 3,
        }
    )

    assert fields == {
        "trains_model": True,
        "sealed_holdout_label_count": 2,
        "order_api_called_count": 5,
        "ctp_connected": True,
    }


def test_completed_rank10_job_requires_intact_predecision_evidence(
    tmp_path: Path,
) -> None:
    job = pd.Series(
        {
            "job_id": "20220128_R10",
            "job_type": "main",
            "candidate_rank": 10,
        }
    )
    output = tmp_path / "job_outputs/20220128_R10"
    payloads = {
        name: pd.DataFrame({"date": ["2022-01-28"], "value": [index]})
        for index, name in enumerate(module.PREDECISION_NAMES)
    }
    hashes = module.batch_core.write_predecision_evidence(
        payloads, output / "predecision"
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "worker_receipt.json").write_text(
        module.json.dumps({"predecision_sha256": hashes}) + "\n",
        encoding="utf-8",
    )

    assert module._validate_completed_stage005_job(
        _FakeLegacy, tmp_path, job, "a" * 64
    )

    (output / "predecision/curve.csv").write_text("corrupt\n", encoding="utf-8")
    assert not module._validate_completed_stage005_job(
        _FakeLegacy, tmp_path, job, "a" * 64
    )
