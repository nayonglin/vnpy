from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pandas as pd


TOOL_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import development_label_batch as module  # noqa: E402


def test_parent_environment_is_explicit_for_every_orchestrator_entry(
    tmp_path: Path,
) -> None:
    environment = module.parent_environment(
        {"PATH": "/usr/bin", "QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR": "0"},
        tmp_path,
    )

    assert environment["QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR"] == "1"
    assert environment["MPLCONFIGDIR"] == str(
        (tmp_path / "orchestrator/mplconfig").resolve()
    )
    assert environment["TMPDIR"] == str((tmp_path / "orchestrator/tmp").resolve())
    assert environment["PATH"] == "/usr/bin"


def test_monthly_predecision_raw_files_recompute_every_receipt_hash(
    tmp_path: Path,
) -> None:
    payloads = {
        name: pd.DataFrame(
            {
                "date": [pd.Timestamp("2022-01-28")],
                "value": [index + 0.25],
            }
        )
        for index, name in enumerate(module.PREDECISION_NAMES)
    }
    hashes = module.write_predecision_evidence(payloads, tmp_path)
    receipts = [
        {"predecision_sha256": dict(hashes)},
        {"predecision_sha256": dict(hashes)},
    ]

    audit = module.validate_predecision_evidence(tmp_path, receipts)

    assert audit["passed"] is True
    assert audit["file_count"] == 5
    assert audit["receipt_count"] == 2
    assert set(audit["files"]) == set(module.PREDECISION_NAMES)

    (tmp_path / "curve.csv").write_text("changed\n", encoding="utf-8")
    failed = module.validate_predecision_evidence(tmp_path, receipts)
    assert failed["passed"] is False
    assert failed["files"]["curve"]["raw_file_matches_receipts"] is False


def test_money_reconciliation_quantizes_each_operand_before_subtraction() -> None:
    end_equity = 5_504_348.800000001
    base_equity = 4_740_258.799999999
    future_net_pnl = 764_090.0000000005

    raw_error = end_equity - base_equity - future_net_pnl
    quantized_error = module.quantized_money_reconciliation_error(
        additions=[end_equity],
        subtractions=[base_equity, future_net_pnl],
    )

    assert abs(raw_error) > 1e-9
    assert quantized_error == 0.0
    assert str(module.MONEY_QUANTUM) == "0.000001"


def test_money_series_quantizes_each_row_before_sum() -> None:
    values = [0.0000006, 0.0000006]

    per_row = module.quantized_money_sum(values)
    after_float_sum = module.quantized_money_reconciliation_error(
        additions=[sum(values)], subtractions=[]
    )

    assert per_row == 0.000002
    assert after_float_sum == 0.000001


def test_execution_scope_audit_derives_zero_counts_from_files_and_commands(
    tmp_path: Path,
) -> None:
    jobs = pd.DataFrame(
        [
            {
                "job_id": "20220128_R10",
                "eval_date": "2022-01-28",
                "split": "development",
                "job_type": "main",
            }
        ]
    )
    label = tmp_path / "job_outputs/20220128_R10/label.json"
    label.parent.mkdir(parents=True)
    label.write_text("{}\n", encoding="utf-8")

    audit = module.build_execution_scope_audit(
        jobs=jobs,
        output_job_ids={"20220128_R10"},
        worker_commands=[
            ["python", "stage005_development_label_batch.py", "--worker", "20220128_R10"]
        ],
        expected_worker_commands={
            (
                "python",
                "stage005_development_label_batch.py",
                "--worker",
                "20220128_R10",
            )
        },
        artifact_paths=[label],
        allowed_artifact_paths={label.resolve()},
        log_texts=["worker completed"],
        holdout_dates={"2025-01-31"},
    )

    assert audit["passed"] is True
    assert audit["counts"] == {
        "holdout_job_count": 0,
        "holdout_output_count": 0,
        "holdout_label_count": 0,
        "model_training_command_count": 0,
        "model_artifact_count": 0,
        "model_training_log_event_count": 0,
        "ctp_connect_command_count": 0,
        "ctp_connect_log_event_count": 0,
        "order_command_count": 0,
        "order_log_event_count": 0,
        "unknown_output_job_count": 0,
        "unexpected_artifact_count": 0,
        "unexpected_worker_command_count": 0,
    }

    hidden_holdout = tmp_path / "job_outputs/20250131_R10/label.json"
    hidden_holdout.parent.mkdir(parents=True)
    hidden_holdout.write_text("{}\n", encoding="utf-8")
    hidden_model = tmp_path / "job_outputs/20220128_R10/ranker.json"
    hidden_model.write_text("{}\n", encoding="utf-8")
    failed = module.build_execution_scope_audit(
        jobs=pd.concat(
            [
                jobs,
                pd.DataFrame(
                    [
                        {
                            "job_id": "20250131_R10",
                            "eval_date": "2025-01-31",
                            "split": "sealed_account_label_holdout",
                            "job_type": "main",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        ),
        output_job_ids={"20220128_R10", "20250131_R10"},
        worker_commands=[["python", "runner.py", "send_order"]],
        expected_worker_commands={
            (
                "python",
                "stage005_development_label_batch.py",
                "--worker",
                "20220128_R10",
            )
        },
        artifact_paths=[label, hidden_holdout, hidden_model],
        allowed_artifact_paths={label.resolve()},
        log_texts=["CTP connected\nfit model\nsend order"],
        holdout_dates={"2025-01-31"},
    )
    assert failed["passed"] is False
    assert failed["counts"]["holdout_job_count"] == 1
    assert failed["counts"]["holdout_label_count"] == 1
    assert failed["counts"]["model_artifact_count"] == 1
    assert failed["counts"]["model_training_log_event_count"] == 1
    assert failed["counts"]["ctp_connect_log_event_count"] == 1
    assert failed["counts"]["order_command_count"] == 1
    assert failed["counts"]["order_log_event_count"] == 1
    assert failed["counts"]["unexpected_artifact_count"] == 2
    assert failed["counts"]["unexpected_worker_command_count"] == 1


def test_attempt_receipts_preserve_failed_run_and_same_campaign_resume(
    tmp_path: Path,
) -> None:
    first_start = module.write_attempt_start(
        tmp_path,
        attempt_id="attempt_001",
        campaign_contract_sha256="a" * 64,
        completed_job_ids=["J1"],
        pending_job_ids=["J2", "J3"],
        worker_commands=[["python", "runner.py", "--worker", "J2"]],
    )
    first_end = module.write_attempt_end(
        tmp_path,
        attempt_id="attempt_001",
        status="failed",
        completed_job_ids=["J1", "J2"],
        error="RuntimeError:transient",
    )
    second_start = module.write_attempt_start(
        tmp_path,
        attempt_id="attempt_002",
        campaign_contract_sha256="a" * 64,
        completed_job_ids=["J1", "J2"],
        pending_job_ids=["J3"],
        worker_commands=[["python", "runner.py", "--worker", "J3"]],
    )

    assert first_start["same_campaign_revalidated_job_count"] == 1
    assert first_end["status"] == "failed"
    assert first_end["error"] == "RuntimeError:transient"
    assert second_start["same_campaign_revalidated_job_count"] == 2
    assert sorted((tmp_path / "attempts").glob("*.json")) == [
        tmp_path / "attempts/attempt_001_end.json",
        tmp_path / "attempts/attempt_001_start.json",
        tmp_path / "attempts/attempt_002_start.json",
    ]

    try:
        module.write_attempt_start(
            tmp_path,
            attempt_id="attempt_002",
            campaign_contract_sha256="a" * 64,
            completed_job_ids=[],
            pending_job_ids=[],
            worker_commands=[],
        )
    except FileExistsError:
        pass
    else:
        raise AssertionError("attempt receipts must be append-only")


def test_run_authorization_binds_every_reviewed_file_by_sha(tmp_path: Path) -> None:
    bindings = {}
    for name in ("runner", "core", "tests", "preregistration", "review"):
        path = tmp_path / f"{name}.txt"
        path.write_text(f"{name}\n", encoding="utf-8")
        bindings[name] = path
    authorization = {
        "decision": "ALLOW_STAGE005_BATCH",
        "bindings": {
            name: {
                "path": str(path.resolve()),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for name, path in bindings.items()
        },
    }
    authorization_path = tmp_path / "run_authorization.json"
    authorization_path.write_text(
        json.dumps(authorization, sort_keys=True) + "\n", encoding="utf-8"
    )

    audit = module.validate_run_authorization(authorization_path, bindings)
    assert audit["passed"] is True
    assert audit["decision"] == "ALLOW_STAGE005_BATCH"

    bindings["runner"].write_text("changed\n", encoding="utf-8")
    failed = module.validate_run_authorization(authorization_path, bindings)
    assert failed["passed"] is False
    assert failed["bindings"]["runner"]["sha256_matches"] is False

    bindings["runner"].write_text("runner\n", encoding="utf-8")
    custom_payload = json.loads(authorization_path.read_text(encoding="utf-8"))
    custom_payload["decision"] = "ALLOW_STAGE005A_SMOKE"
    authorization_path.write_text(
        json.dumps(custom_payload, sort_keys=True) + "\n", encoding="utf-8"
    )
    custom = module.validate_run_authorization(
        authorization_path,
        bindings,
        expected_decision="ALLOW_STAGE005A_SMOKE",
    )
    assert custom["decision"] == "ALLOW_STAGE005A_SMOKE"


def test_run_authorization_rejects_unlimited_scope_for_stage005(
    tmp_path: Path,
) -> None:
    runner = tmp_path / "runner.py"
    runner.write_text("pass\n", encoding="utf-8")
    bindings = {"runner": runner}
    authorization_path = tmp_path / "run_authorization.json"
    payload = {
        "decision": "ALLOW_STAGE005_BATCH",
        "scope": "unlimited_campaigns",
        "campaign_nonce": "a" * 64,
        "bindings": {
            "runner": {
                "path": str(runner.resolve()),
                "sha256": hashlib.sha256(runner.read_bytes()).hexdigest(),
            }
        },
    }
    authorization_path.write_text(
        json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8"
    )

    rejected = module.validate_run_authorization(
        authorization_path,
        bindings,
        expected_scope="one_new_stage005_campaign_only",
        require_campaign_nonce=True,
    )

    assert rejected["passed"] is False
    assert rejected["scope_matches"] is False
    assert rejected["campaign_nonce_valid"] is True

    payload["scope"] = "one_new_stage005_campaign_only"
    authorization_path.write_text(
        json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8"
    )
    accepted = module.validate_run_authorization(
        authorization_path,
        bindings,
        expected_scope="one_new_stage005_campaign_only",
        require_campaign_nonce=True,
    )
    assert accepted["passed"] is True
    assert accepted["campaign_nonce"] == "a" * 64


def test_structured_review_gate_rejects_block_even_if_notes_say_allow(
    tmp_path: Path,
) -> None:
    review = tmp_path / "review.md"
    review.write_text("BLOCK review; text mentions ALLOW_STAGE005_BATCH\n", encoding="utf-8")
    decision_path = tmp_path / "review_decision.json"
    decision_path.write_text(
        json.dumps(
            {
                "decision": "BLOCK_STAGE005_BATCH",
                "severity": {"P0": 0, "P1": 5, "P2": 2, "P3": 0},
                "review_path": str(review.resolve()),
                "review_sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
                "notes": "ALLOW_STAGE005_BATCH appears only in explanatory text",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    blocked = module.validate_structured_review_decision(decision_path, review)
    assert blocked["passed"] is False
    assert blocked["decision"] == "BLOCK_STAGE005_BATCH"

    payload = json.loads(decision_path.read_text(encoding="utf-8"))
    payload["decision"] = "ALLOW_STAGE005_BATCH"
    payload["severity"] = {"P0": 0, "P1": 0, "P2": 1, "P3": 0}
    decision_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    allowed = module.validate_structured_review_decision(decision_path, review)
    assert allowed["passed"] is True

    payload["decision"] = "ALLOW_STAGE005A_SMOKE"
    decision_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    custom = module.validate_structured_review_decision(
        decision_path,
        review,
        expected_decision="ALLOW_STAGE005A_SMOKE",
    )
    assert custom["passed"] is True

    payload["severity"] = {
        "P0": False,
        "P1": False,
        "P2": False,
        "P3": False,
    }
    decision_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    boolean_severity = module.validate_structured_review_decision(
        decision_path,
        review,
        expected_decision="ALLOW_STAGE005A_SMOKE",
    )
    assert boolean_severity["passed"] is False
    assert boolean_severity["severity_shape_exact"] is False
