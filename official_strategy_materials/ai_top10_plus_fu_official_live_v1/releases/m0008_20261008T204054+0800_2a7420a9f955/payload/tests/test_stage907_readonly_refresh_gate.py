from __future__ import annotations

from pathlib import Path
import os
import sys


os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import run_qmt_roll_stage907_official_live_readonly_refresh_gate as stage907


def _summary() -> dict[str, object]:
    return {
        "send_order_api_attempted_count": 0,
        "cancel_order_api_attempted_count": 0,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "native_mutation_api_attempted_count": 0,
        "native_mutation_api_called_count": 0,
        "order_api_attempted_count": 0,
        "order_api_called_count": 0,
    }


def test_authoritative_readonly_order_api_evidence_requires_exact_zero_ints() -> None:
    evidence = stage907._readonly_order_api_evidence(_summary())

    assert evidence["complete"] is True
    assert evidence["missing_fields"] == []
    assert evidence["nonzero_fields"] == []


def test_authoritative_readonly_order_api_evidence_fails_closed() -> None:
    missing = _summary()
    missing.pop("send_order_api_called_count")
    malformed = _summary()
    malformed["cancel_order_api_called_count"] = False
    attempted = _summary()
    attempted["send_order_api_attempted_count"] = 1

    missing_result = stage907._readonly_order_api_evidence(missing)
    malformed_result = stage907._readonly_order_api_evidence(malformed)
    attempted_result = stage907._readonly_order_api_evidence(attempted)

    assert missing_result["complete"] is False
    assert "send_order_api_called_count" in missing_result["missing_fields"]
    assert malformed_result["complete"] is False
    assert "cancel_order_api_called_count" in malformed_result["missing_fields"]
    assert attempted_result["complete"] is False
    assert "send_order_api_attempted_count" in attempted_result["nonzero_fields"]


def test_readonly_snapshot_evidence_requires_new_complete_bundle() -> None:
    summary = {
        "generated_at": "2026-07-19T09:00:02+08:00",
        "invocation_id": "invocation-1",
        "query_generation_uuid": "new-generation",
        "broker_query_bundle": {
            "generation_uuid": "new-generation",
            "complete": True,
        },
    }

    evidence = stage907._readonly_snapshot_evidence(
        summary,
        previous_generation="old-generation",
        command_started_at="2026-07-19 09:00:01",
        refresh_attempted=True,
        expected_invocation_id="invocation-1",
        command_stdout_summary=summary,
    )

    assert evidence["complete"] is True
    assert evidence["missing_fields"] == []


def test_readonly_snapshot_evidence_rejects_stale_or_incomplete_bundle() -> None:
    stale = {
        "generated_at": "2026-07-19T09:00:00+08:00",
        "invocation_id": "invocation-1",
        "query_generation_uuid": "same-generation",
        "broker_query_bundle": {
            "generation_uuid": "same-generation",
            "complete": False,
        },
    }

    evidence = stage907._readonly_snapshot_evidence(
        stale,
        previous_generation="same-generation",
        command_started_at="2026-07-19 09:00:01",
        refresh_attempted=True,
        expected_invocation_id="invocation-1",
        command_stdout_summary=stale,
    )

    assert evidence["complete"] is False
    assert "broker_query_bundle.complete" in evidence["missing_fields"]
    assert "query_generation_uuid_not_new" in evidence["missing_fields"]
    assert "summary_generated_before_command_start" in evidence["missing_fields"]


def test_readonly_snapshot_evidence_requires_exact_command_invocation_binding() -> None:
    summary = {
        "generated_at": "2026-07-19T09:00:02+08:00",
        "invocation_id": "other-writer",
        "query_generation_uuid": "new-generation",
        "broker_query_bundle": {
            "generation_uuid": "new-generation",
            "complete": True,
        },
    }

    evidence = stage907._readonly_snapshot_evidence(
        summary,
        previous_generation="old-generation",
        command_started_at="2026-07-19 09:00:01",
        refresh_attempted=True,
        expected_invocation_id="this-command",
        command_stdout_summary=summary,
    )

    assert evidence["complete"] is False
    assert "invocation_id_mismatch" in evidence["missing_fields"]


def test_readonly_snapshot_evidence_rejects_different_subprocess_stdout_payload() -> None:
    summary = {
        "generated_at": "2026-07-19T09:00:02+08:00",
        "invocation_id": "this-command",
        "query_generation_uuid": "new-generation",
        "broker_query_bundle": {
            "generation_uuid": "new-generation",
            "complete": True,
        },
    }
    stdout_summary = {**summary, "status": "different-payload"}

    evidence = stage907._readonly_snapshot_evidence(
        summary,
        previous_generation="old-generation",
        command_started_at="2026-07-19 09:00:01",
        refresh_attempted=True,
        expected_invocation_id="this-command",
        command_stdout_summary=stdout_summary,
    )

    assert evidence["complete"] is False
    assert "stage174_stdout_file_payload_mismatch" in evidence["missing_fields"]


def test_stage174_stdout_parser_and_command_bind_same_invocation() -> None:
    payload = {"invocation_id": "this-command", "status": "ready"}
    parsed = stage907._extract_stage174_stdout_summary(
        f"{stage907.json.dumps(payload, indent=2)}\nsummary json: /tmp/summary.json\n"
    )
    command, sanitized = stage907._production_live_command(30, "this-command")

    assert parsed == payload
    assert command[:2] == ["bash", "-lc"]
    assert "--invocation-id this-command" in sanitized

    _, reconnect_command = stage907._production_live_command(
        30, "this-command", observe_reconnect=True
    )
    assert "--observe-reconnect" in reconnect_command
