from __future__ import annotations

import json
import hashlib
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
import sys

import pandas as pd
import pytest


TOOL_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import stage005a_runtime_identity_remediation as module  # noqa: E402


def test_worker_command_reenters_stage005a_wrapper() -> None:
    command = module.worker_command(
        Path("/private/tmp/stage005a-campaign"), "20220128_R10"
    )

    assert command[0] == sys.executable
    assert command[1] == "-B"
    assert Path(command[2]).resolve() == Path(module.__file__).resolve()
    assert command[3:] == [
        "--worker",
        "20220128_R10",
        "--campaign-dir",
        "/private/tmp/stage005a-campaign",
    ]


def test_parent_environment_is_installed_before_runtime_module_import(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(module, "TMP_ROOT", tmp_path)
    monkeypatch.delenv("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", raising=False)
    monkeypatch.delenv("MPLCONFIGDIR", raising=False)

    environment = module._install_parent_environment()

    assert environment["QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR"] == "1"
    assert environment["MPLCONFIGDIR"] == str(
        (tmp_path / "orchestrator/mplconfig").resolve()
    )
    assert environment["TMPDIR"] == str(
        (tmp_path / "orchestrator/tmp").resolve()
    )
    assert Path(environment["MPLCONFIGDIR"]).is_dir()
    assert Path(environment["TMPDIR"]).is_dir()


def test_worker_entry_preserves_injected_job_scoped_environment(
    tmp_path: Path, monkeypatch
) -> None:
    job_id = module.SMOKE_JOB_IDS[0]
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
    monkeypatch.setattr(module, "_verify_smoke_authorization", lambda: {})
    monkeypatch.setattr(module, "_configure_stage004", lambda: None)
    monkeypatch.setattr(module, "_runtime_receipt_gate", lambda: {})
    monkeypatch.setattr(module, "_campaign_target", lambda path: campaign)
    monkeypatch.setattr(
        module,
        "_execution_plan_gate",
        lambda path: {"job_ids": list(module.SMOKE_JOB_IDS)},
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

    monkeypatch.setattr(module, "_load_legacy_stage015", lambda: FakeLegacy())
    monkeypatch.setattr(module, "_campaign_identity_gate", lambda legacy, path: {})

    module.run_worker(job_id, campaign)

    assert observed == {
        "job_id": job_id,
        "tmpdir": str(tmpdir),
        "mplconfigdir": str(mplconfig),
    }


def test_worker_environment_gate_rejects_orchestrator_paths(
    tmp_path: Path, monkeypatch
) -> None:
    campaign = tmp_path / "campaign_001"
    orchestrator = tmp_path / "orchestrator"
    monkeypatch.setattr(module, "TMP_ROOT", tmp_path)
    monkeypatch.setenv("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
    monkeypatch.setenv("TMPDIR", str(orchestrator / "tmp"))
    monkeypatch.setenv("MPLCONFIGDIR", str(orchestrator / "mplconfig"))

    with pytest.raises(module.Stage005AError, match="worker_environment_invalid"):
        module._worker_environment_gate(campaign, module.SMOKE_JOB_IDS[0])


def test_runtime_binding_values_point_only_to_v2_frozen_inputs() -> None:
    bindings = module._runtime_binding_values()

    assert bindings["RUNTIME_ROOT"] == module.RUNTIME_ROOT
    assert bindings["RUNTIME_DATABASE"] == module.RUNTIME_DATABASE
    assert bindings["PRODUCTION_DATABASE"] == module.FROZEN_SOURCE_DATABASE
    assert bindings["RUNTIME_RECEIPT"] == module.RUNTIME_RECEIPT
    assert bindings["EXPECTED_DATABASE_SHA256"] == module.EXPECTED_DATABASE_SHA256
    assert module.FROZEN_MAPPING.is_relative_to(module.RUNTIME_ROOT)
    assert module.FROZEN_MINUTE_BARS.is_relative_to(module.RUNTIME_ROOT)
    assert module.FROZEN_CONTRACT_METADATA.is_relative_to(module.RUNTIME_ROOT)

    fake = SimpleNamespace()
    module._apply_runtime_bindings(fake)
    assert fake.RUNTIME_ROOT == module.RUNTIME_ROOT
    assert fake.PRODUCTION_DATABASE == module.FROZEN_SOURCE_DATABASE
    assert fake.CAMPAIGN_ROOT == module.CAMPAIGN_ROOT


def test_smoke_scope_is_derived_and_rejects_model_or_order_evidence(
    tmp_path: Path,
) -> None:
    jobs = pd.DataFrame(
        [
            {
                "job_id": job_id,
                "eval_date": "2022-01-28",
                "split": "development",
                "job_type": "main",
            }
            for job_id in module.SMOKE_JOB_IDS
        ]
    )
    jobs.to_csv(tmp_path / "jobs.csv", index=False)
    (tmp_path / "logs").mkdir()
    (tmp_path / "job_outputs").mkdir()
    for job_id in module.SMOKE_JOB_IDS:
        output = tmp_path / "job_outputs" / job_id
        output.mkdir()
        (output / "label.json").write_text("{}\n", encoding="utf-8")
    commands = [module.worker_command(tmp_path, job_id) for job_id in module.SMOKE_JOB_IDS]
    (tmp_path / "execution_plan.json").write_text(
        json.dumps({"worker_commands": commands}) + "\n", encoding="utf-8"
    )
    log_path = tmp_path / "logs/20220128_R10_1.log"
    log_path.write_text(
        "worker completed\n", encoding="utf-8"
    )

    passed = module._smoke_scope_audit(tmp_path)
    assert passed["passed"] is True
    assert passed["counts"]["model_artifact_count"] == 0
    assert passed["counts"]["order_log_event_count"] == 0

    hidden = tmp_path / "sealed_holdout_labels.csv"
    hidden.write_text("label\n", encoding="utf-8")
    unknown = module._smoke_scope_audit(tmp_path)
    assert unknown["passed"] is False
    assert unknown["counts"]["unexpected_artifact_count"] == 1
    hidden.unlink()

    (tmp_path / "job_outputs/20220128_R10/model.ubj").write_text(
        "model\n", encoding="utf-8"
    )
    log_path.write_text(
        "fit model\nsend order\n", encoding="utf-8"
    )
    failed = module._smoke_scope_audit(tmp_path)
    assert failed["passed"] is False
    assert failed["counts"]["model_artifact_count"] == 1
    assert failed["counts"]["model_training_log_event_count"] == 1
    assert failed["counts"]["order_log_event_count"] == 1


def test_campaign_target_rejects_root_escape_and_abandoned_campaign(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "campaigns"
    root.mkdir()
    valid = root / "campaign_001"
    valid.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setattr(module, "CAMPAIGN_ROOT", root)

    assert module._campaign_target(valid) == valid.resolve()
    with pytest.raises(module.Stage005AError, match="outside_root"):
        module._campaign_target(outside)

    (valid / "ABANDONED.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(module.Stage005AError, match="abandoned"):
        module._campaign_target(valid)


def test_execution_plan_gate_binds_authorization_and_stage005a_commands(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "campaigns"
    campaign = root / "campaign_001"
    campaign.mkdir(parents=True)
    authorization = tmp_path / "authorization.json"
    authorization.write_text("authorized\n", encoding="utf-8")
    pd.DataFrame([{"job_id": value} for value in module.SMOKE_JOB_IDS]).to_csv(
        campaign / "jobs.csv", index=False
    )
    plan = {
        "decision": "stage005a_fixed_four_job_smoke_plan",
        "job_ids": list(module.SMOKE_JOB_IDS),
        "worker_commands": [
            module.worker_command(campaign, job_id)
            for job_id in module.SMOKE_JOB_IDS
        ],
        "authorization_sha256": hashlib.sha256(
            authorization.read_bytes()
        ).hexdigest(),
        "cross_campaign_reuse": False,
    }
    (campaign / "execution_plan.json").write_text(
        json.dumps(plan) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(module, "CAMPAIGN_ROOT", root)
    monkeypatch.setattr(module, "RUN_AUTHORIZATION", authorization)

    assert module._execution_plan_gate(campaign)["job_ids"] == list(
        module.SMOKE_JOB_IDS
    )

    plan["worker_commands"][0][2] = str(module.stage004.__file__)
    (campaign / "execution_plan.json").write_text(
        json.dumps(plan) + "\n", encoding="utf-8"
    )
    with pytest.raises(module.Stage005AError, match="execution_plan_drift"):
        module._execution_plan_gate(campaign)


def test_stage005a_authorization_rejects_structured_block(
    tmp_path: Path, monkeypatch
) -> None:
    review = tmp_path / "review.md"
    review.write_text("BLOCK; mentions ALLOW_STAGE005A_SMOKE\n", encoding="utf-8")
    decision = tmp_path / "decision.json"
    decision.write_text(
        json.dumps(
            {
                "decision": "BLOCK_STAGE005A_SMOKE",
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
    monkeypatch.setattr(module, "PRERUN_REVIEW_DECISION", decision)
    monkeypatch.setattr(module, "RUN_AUTHORIZATION", authorization)

    with pytest.raises(module.Stage005AError, match="not_allowing_smoke"):
        module._verify_smoke_authorization()


def test_snapshot_directory_initialization_failure_rolls_back_new_roots(
    tmp_path: Path, monkeypatch
) -> None:
    base = tmp_path / "artifacts"
    runtime = tmp_path / "runtime"
    frozen = runtime / "frozen_inputs"
    monkeypatch.setattr(module, "BASE_OUT", base)
    monkeypatch.setattr(module, "RUNTIME_ROOT", runtime)
    monkeypatch.setattr(module, "FROZEN_INPUT_DIR", frozen)
    monkeypatch.setattr(module, "RUNTIME_RECEIPT", base / "runtime_receipt.json")
    monkeypatch.setattr(module, "_verify_smoke_authorization", lambda: {})
    monkeypatch.setattr(module, "_verify_source_contract", lambda: {})
    monkeypatch.setattr(module.stage004, "_production_identity", lambda: {})
    monkeypatch.setattr(
        module.shutil,
        "disk_usage",
        lambda path: SimpleNamespace(free=module.MINIMUM_FREE_BYTES * 2),
    )
    original_mkdir = Path.mkdir

    def fail_frozen_mkdir(path: Path, *args, **kwargs) -> None:
        if path == frozen:
            raise OSError("injected frozen directory failure")
        original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_frozen_mkdir)

    with pytest.raises(OSError, match="injected"):
        module.prepare_runtime_snapshot()

    assert not base.exists()
    assert not runtime.exists()


def test_real_legacy_loader_resolves_frozen_market_inputs(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "mplconfig"))
    monkeypatch.setenv("TMPDIR", str(tmp_path / "tmp"))
    (tmp_path / "mplconfig").mkdir()
    (tmp_path / "tmp").mkdir()
    for name, value in module._runtime_binding_values().items():
        monkeypatch.setattr(module.stage004, name, value)
    legacy = module._patch_legacy_for_frozen_inputs(
        module._ORIGINAL_LOAD_LEGACY()
    )

    _live, _s513, _s827, s901 = (
        legacy._load_stage004()._load_production_modules()
    )

    assert Path(s901.ALL_FUTURES_MAPPING_PATH) == module.FROZEN_MAPPING
    assert Path(s901.s861.FULL_MINUTE_BARS_PATH) == module.FROZEN_MINUTE_BARS
    import contract_metadata

    assert (
        Path(contract_metadata.ALL_FUTURES_CONTRACT_METADATA_PATH)
        == module.FROZEN_CONTRACT_METADATA
    )
