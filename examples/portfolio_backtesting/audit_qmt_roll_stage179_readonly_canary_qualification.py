from __future__ import annotations

import argparse
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

from qmt_roll_official_live_release_manifest import (
    load_and_validate_release_manifest,
)


EXPECTED_EXECUTION_PROFILE = "stage372-20w"
EXPECTED_OFFICIAL_VERSION = "official_live_stage372_20w_recovery_sleeve"
EXPECTED_CAPITAL = 200_000
EXPECTED_CAPITAL_LABEL = "20w"
EXPECTED_RUNTIME_PROFILE = "production-readonly"
EXPECTED_MODE = "dry-run"
EXPECTED_SUBMIT_MODE = "disabled"
INGRESS_DURABLE_HARD_DEADLINE_NS = 1_000_000_000
LAUNCHD_START_HARD_DEADLINE_NS = 60_000_000_000
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
CANONICAL_PLISTS = {
    "day": "examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.20w.stage372-day-session.plist",
    "night": "examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.20w.stage372-night-session.plist",
}
# Stage174 currently publishes a one-shot order/trade/position reconnect
# diagnostic, not a full current-generation settlement/account/contract
# readiness transition.  Keep qualification fail-closed until that producer
# is implemented and independently reviewed.
AUTHORITATIVE_RECONNECT_PROOF_ENABLED = False


def _strict_int(value: Any) -> int | None:
    return value if type(value) is int else None


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _append_unique(rows: list[str], value: str) -> None:
    if value not in rows:
        rows.append(value)


def _record_digest(record: Mapping[str, Any]) -> str:
    core = {
        key: value
        for key, value in record.items()
        if key != "capture_record_sha256"
    }
    encoded = json.dumps(
        core,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _mapping_digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _stage903_summary_from_stage930(
    stage930_summary: Mapping[str, Any],
) -> Mapping[str, Any]:
    cycle = stage930_summary.get("readonly_qualification_cycle")
    if not isinstance(cycle, Mapping):
        cycle = stage930_summary.get("latest_cycle")
    if not isinstance(cycle, Mapping):
        return {}
    stage903 = cycle.get("stage903")
    if not isinstance(stage903, Mapping):
        return {}
    summary = stage903.get("summary")
    return summary if isinstance(summary, Mapping) else {}


def _disconnect_projection(
    lifecycle: Mapping[str, Any],
    *,
    session_id: str,
    runtime_profile: Any,
    execution_profile: Any,
) -> dict[str, Any]:
    proof_complete = _strict_int(lifecycle.get("proof_complete")) == 1
    return {
        "disconnect_lifecycle_model_tag": lifecycle.get("model_tag", ""),
        "disconnect_authoritative_readiness_transition_complete": lifecycle.get(
            "authoritative_readiness_transition_complete", 0
        ),
        "disconnect_full_snapshot_generation_complete": lifecycle.get(
            "full_snapshot_generation_complete", 0
        ),
        "disconnect_observed": lifecycle.get("disconnect_observed", 0),
        "reconnect_observed": lifecycle.get("reconnect_observed", 0),
        "disconnect_evidence_id": lifecycle.get("disconnect_evidence_id", ""),
        "disconnect_session_id": session_id if proof_complete else "",
        "disconnect_runtime_profile": runtime_profile if proof_complete else "",
        "disconnect_execution_profile": execution_profile if proof_complete else "",
        "old_connection_generation": lifecycle.get("old_connection_generation", ""),
        "new_connection_generation": lifecycle.get("new_connection_generation", ""),
        "readiness_revoked_epoch_ns": lifecycle.get("readiness_revoked_epoch_ns"),
        "readiness_restored_epoch_ns": lifecycle.get("readiness_restored_epoch_ns"),
        "disconnect_send_order_api_called_count": lifecycle.get(
            "send_order_api_called_count"
        ),
        "disconnect_cancel_order_api_called_count": lifecycle.get(
            "cancel_order_api_called_count"
        ),
    }


def _disconnect_reconnect_proof_valid(record: Mapping[str, Any]) -> bool:
    if not AUTHORITATIVE_RECONNECT_PROOF_ENABLED:
        return False
    revoked = _strict_int(record.get("readiness_revoked_epoch_ns"))
    restored = _strict_int(record.get("readiness_restored_epoch_ns"))
    old_generation = _clean(record.get("old_connection_generation"))
    new_generation = _clean(record.get("new_connection_generation"))
    return bool(
        record.get("disconnect_lifecycle_model_tag")
        == "stage174_ctp_connection_lifecycle_v2"
        and _strict_int(
            record.get("disconnect_authoritative_readiness_transition_complete")
        )
        == 1
        and _strict_int(
            record.get("disconnect_full_snapshot_generation_complete")
        )
        == 1
        and _strict_int(record.get("disconnect_observed")) == 1
        and _strict_int(record.get("reconnect_observed")) == 1
        and _clean(record.get("disconnect_evidence_id"))
        and _clean(record.get("disconnect_session_id"))
        == _clean(record.get("session_id"))
        and record.get("disconnect_runtime_profile")
        == EXPECTED_RUNTIME_PROFILE
        and record.get("disconnect_execution_profile")
        == EXPECTED_EXECUTION_PROFILE
        and old_generation
        and new_generation
        and old_generation != new_generation
        and revoked is not None
        and restored is not None
        and 0 < revoked < restored
        and _strict_int(record.get("disconnect_send_order_api_called_count")) == 0
        and _strict_int(record.get("disconnect_cancel_order_api_called_count")) == 0
    )


def _record_blockers(
    record: Mapping[str, Any],
    *,
    expected_manifest_sha256: str,
    expected_source_commit: str,
) -> list[str]:
    session_id = _clean(record.get("session_id")) or "missing-session-id"
    blockers: list[str] = []

    if record.get("capture_schema_version") != 2:
        blockers.append(f"{session_id}:capture_schema_version_mismatch")
    source_summary_sha256 = _clean(record.get("stage930_summary_sha256"))
    if len(source_summary_sha256) != 64 or any(
        char not in "0123456789abcdef" for char in source_summary_sha256
    ):
        blockers.append(f"{session_id}:stage930_summary_sha256_invalid")
    try:
        record_digest = _record_digest(record)
    except (TypeError, ValueError):
        record_digest = ""
    if _clean(record.get("capture_record_sha256")) != record_digest:
        blockers.append(f"{session_id}:capture_record_sha256_mismatch")
    source_payload = record.get("stage930_summary_payload")
    if not isinstance(source_payload, Mapping):
        blockers.append(f"{session_id}:stage930_summary_payload_missing")
    else:
        try:
            payload_digest = _mapping_digest(source_payload)
        except (TypeError, ValueError):
            payload_digest = ""
        if _clean(record.get("stage930_summary_payload_sha256")) != payload_digest:
            blockers.append(f"{session_id}:stage930_summary_payload_sha256_mismatch")
        for field in (
            "execution_profile",
            "official_live_version",
            "capital",
            "capital_label",
            "runtime_profile",
            "mode",
            "submit_mode",
            "send_order_api_called_count",
            "cancel_order_api_called_count",
            "order_api_called_count",
            "order_api_evidence_complete",
            "order_api_evidence_missing_fields",
            "daemon_started_epoch_ns",
            "open_minute_tick_ingress_epoch_ns",
            "open_minute_tick_durable_epoch_ns",
        ):
            if record.get(field) != source_payload.get(field):
                blockers.append(f"{session_id}:stage930_payload_{field}_mismatch")
        payload_run_id = _clean(source_payload.get("run_id"))
        payload_daemon_epoch_ns = _strict_int(
            source_payload.get("daemon_started_epoch_ns")
        )
        session_kind = _clean(record.get("session_kind"))
        if (
            not payload_run_id
            or payload_daemon_epoch_ns is None
            or payload_daemon_epoch_ns <= 0
            or session_kind not in CANONICAL_PLISTS
        ):
            blockers.append(f"{session_id}:stage930_payload_session_identity_invalid")
        else:
            payload_started_at = datetime.fromtimestamp(
                payload_daemon_epoch_ns // 1_000_000_000,
                tz=SHANGHAI_TZ,
            )
            expected_session_date = payload_started_at.date().isoformat()
            expected_session_id = payload_run_id
            expected_hour = 8 if session_kind == "day" else 20
            expected_scheduled_epoch_ns = int(
                datetime(
                    payload_started_at.year,
                    payload_started_at.month,
                    payload_started_at.day,
                    expected_hour,
                    55,
                    tzinfo=SHANGHAI_TZ,
                ).timestamp()
            ) * 1_000_000_000
            if session_id != expected_session_id:
                blockers.append(f"{session_id}:session_id_not_derived_from_stage930")
            if record.get("session_date") != expected_session_date:
                blockers.append(f"{session_id}:session_date_not_derived_from_stage930")
            if record.get("scheduled_start_epoch_ns") != expected_scheduled_epoch_ns:
                blockers.append(
                    f"{session_id}:scheduled_start_not_derived_from_stage930"
                )
        expected_completed = int(
            _clean(source_payload.get("daemon_status")).startswith(
                "daemon_completed_"
            )
        )
        if record.get("session_completed") != expected_completed:
            blockers.append(f"{session_id}:session_completed_projection_mismatch")
        for record_field, payload_field in (
            ("cycle_started_epoch_ns", "open_minute_tick_cycle_started_epoch_ns"),
            ("cycle_finished_epoch_ns", "open_minute_tick_cycle_finished_epoch_ns"),
        ):
            if record.get(record_field) != source_payload.get(payload_field):
                blockers.append(
                    f"{session_id}:stage930_payload_{record_field}_mismatch"
                )
        provenance = source_payload.get("launchd_provenance")
        if not isinstance(provenance, Mapping):
            provenance = {}
        provenance_projection = {
            "launchd_provenance_complete": provenance.get("complete"),
            "launchd_xpc_service_name": provenance.get("xpc_service_name"),
            "launchd_process_pid": provenance.get("pid"),
            "launchd_parent_pid": provenance.get("parent_pid"),
            "launchctl_print_exit_code": provenance.get(
                "launchctl_print_exit_code"
            ),
            "launchctl_job_pid": provenance.get("launchctl_job_pid"),
        }
        for field, expected in provenance_projection.items():
            if record.get(field) != expected:
                blockers.append(f"{session_id}:{field}_projection_mismatch")
        if provenance.get("daemon_started_epoch_ns") != source_payload.get(
            "daemon_started_epoch_ns"
        ):
            blockers.append(f"{session_id}:launchd_provenance_epoch_mismatch")
        source_stage903 = _stage903_summary_from_stage930(source_payload)
        for field in (
            "stage914_exit_code",
            "stage914_preflight_status",
            "stage914_blocking_failure_count",
            "stage907_refresh_status",
            "stage907_readonly_status_after",
            "stage907_position_snapshot_state_after",
        ):
            if record.get(field) != source_stage903.get(field):
                blockers.append(f"{session_id}:stage903_{field}_projection_mismatch")
        lifecycle = source_stage903.get("stage907_connection_lifecycle")
        if not isinstance(lifecycle, Mapping):
            lifecycle = {}
        expected_disconnect = _disconnect_projection(
            lifecycle,
            session_id=session_id,
            runtime_profile=source_payload.get("runtime_profile"),
            execution_profile=source_payload.get("execution_profile"),
        )
        for field, expected in expected_disconnect.items():
            if record.get(field) != expected:
                blockers.append(f"{session_id}:{field}_projection_mismatch")

    expected_values = {
        "execution_profile": EXPECTED_EXECUTION_PROFILE,
        "official_live_version": EXPECTED_OFFICIAL_VERSION,
        "capital": EXPECTED_CAPITAL,
        "capital_label": EXPECTED_CAPITAL_LABEL,
        "runtime_profile": EXPECTED_RUNTIME_PROFILE,
        "mode": EXPECTED_MODE,
        "submit_mode": EXPECTED_SUBMIT_MODE,
        "plist_execution_profile": EXPECTED_EXECUTION_PROFILE,
        "plist_runtime_profile": EXPECTED_RUNTIME_PROFILE,
        "plist_mode": EXPECTED_MODE,
        "plist_submit_mode": EXPECTED_SUBMIT_MODE,
        "launchd_plist_relative_path": CANONICAL_PLISTS.get(
            _clean(record.get("session_kind")), ""
        ),
        "release_manifest_sha256": expected_manifest_sha256,
        "release_source_commit": expected_source_commit,
        "stage914_exit_code": 0,
        "stage914_preflight_status": "production_readonly_preflight_passed",
        "stage914_blocking_failure_count": 0,
        "stage907_refresh_status": "readonly_refresh_completed_snapshot_ready",
        "stage907_readonly_status_after": "readonly_snapshots_received",
        "session_completed": 1,
        "launchd_provenance_complete": 1,
    }
    for field, expected in expected_values.items():
        if field not in record:
            blockers.append(f"{session_id}:missing_{field}")
        elif record.get(field) != expected:
            blockers.append(f"{session_id}:{field}_mismatch")

    if record.get("stage907_position_snapshot_state_after") not in {
        "confirmed_flat",
        "positions_received",
    }:
        blockers.append(f"{session_id}:position_snapshot_not_ready")

    session_kind = record.get("session_kind")
    if session_kind not in {"day", "night"}:
        blockers.append(f"{session_id}:session_kind_invalid")
    label = _clean(record.get("launchd_label"))
    expected_label = (
        f"local.qmt-roll.official-live.20w.stage372-{session_kind}-session"
        if session_kind in {"day", "night"}
        else ""
    )
    if label != expected_label:
        blockers.append(f"{session_id}:launchd_label_mismatch")
    if record.get("launchd_xpc_service_name") != expected_label:
        blockers.append(f"{session_id}:launchd_xpc_service_name_mismatch")
    if _strict_int(record.get("launchd_parent_pid")) != 1:
        blockers.append(f"{session_id}:launchd_parent_pid_mismatch")
    process_pid = _strict_int(record.get("launchd_process_pid"))
    if process_pid is None or process_pid <= 1:
        blockers.append(f"{session_id}:launchd_process_pid_invalid")
    if _strict_int(record.get("launchctl_print_exit_code")) != 0:
        blockers.append(f"{session_id}:launchctl_print_failed")
    if _strict_int(record.get("launchctl_job_pid")) != process_pid:
        blockers.append(f"{session_id}:launchctl_job_pid_mismatch")
    plist_sha256 = _clean(record.get("launchd_plist_sha256"))
    if len(plist_sha256) != 64 or any(
        char not in "0123456789abcdef" for char in plist_sha256
    ):
        blockers.append(f"{session_id}:launchd_plist_sha256_invalid")
    if _clean(record.get("manifest_launchd_plist_sha256")) != plist_sha256:
        blockers.append(f"{session_id}:manifest_launchd_plist_sha256_mismatch")
    expected_hour = 8 if session_kind == "day" else 20 if session_kind == "night" else None
    if (
        record.get("launchd_start_hour") != expected_hour
        or record.get("launchd_start_minute") != 55
    ):
        blockers.append(f"{session_id}:launchd_schedule_mismatch")

    for field in (
        "send_order_api_called_count",
        "cancel_order_api_called_count",
        "order_api_called_count",
    ):
        if field not in record:
            blockers.append(f"{session_id}:missing_{field}")
        elif _strict_int(record.get(field)) is None:
            blockers.append(f"{session_id}:{field}_invalid")
        elif record.get(field) != 0:
            blockers.append(f"{session_id}:{field}_nonzero")
    if (
        record.get("order_api_evidence_complete") != 1
        or record.get("order_api_evidence_missing_fields") != []
    ):
        blockers.append(f"{session_id}:order_api_evidence_incomplete")
    if (
        _strict_int(record.get("disconnect_observed")) == 1
        or _strict_int(record.get("reconnect_observed")) == 1
    ) and not _disconnect_reconnect_proof_valid(record):
        blockers.append(f"{session_id}:disconnect_reconnect_evidence_invalid")

    timestamp_fields = (
        "scheduled_start_epoch_ns",
        "daemon_started_epoch_ns",
        "open_minute_tick_ingress_epoch_ns",
        "open_minute_tick_durable_epoch_ns",
        "cycle_started_epoch_ns",
        "cycle_finished_epoch_ns",
    )
    timestamps: dict[str, int] = {}
    for field in timestamp_fields:
        value = _strict_int(record.get(field))
        if value is None or value <= 0:
            blockers.append(f"{session_id}:missing_{field}")
        else:
            timestamps[field] = value
    session_date = _clean(record.get("session_date"))
    scheduled_identity_valid = False
    parsed_date_value: date | None = None
    scheduled_value = timestamps.get("scheduled_start_epoch_ns")
    if scheduled_value is not None:
        try:
            parsed_date = date.fromisoformat(session_date)
            parsed_date_value = parsed_date
            scheduled_at = datetime.fromtimestamp(
                scheduled_value // 1_000_000_000,
                tz=SHANGHAI_TZ,
            )
            scheduled_identity_valid = bool(
                parsed_date.isoformat() == session_date
                and scheduled_at.date() == parsed_date
                and scheduled_at.hour == expected_hour
                and scheduled_at.minute == 55
                and scheduled_at.second == 0
                and scheduled_value % 1_000_000_000 == 0
            )
        except (ValueError, OSError, OverflowError):
            scheduled_identity_valid = False
    if not scheduled_identity_valid:
        blockers.append(f"{session_id}:scheduled_start_identity_mismatch")
    ingress_value = timestamps.get("open_minute_tick_ingress_epoch_ns")
    if (
        parsed_date_value is not None
        and ingress_value is not None
        and session_kind in {"day", "night"}
    ):
        market_open = datetime(
            parsed_date_value.year,
            parsed_date_value.month,
            parsed_date_value.day,
            9 if session_kind == "day" else 21,
            0,
            tzinfo=SHANGHAI_TZ,
        )
        market_open_epoch_ns = int(market_open.timestamp()) * 1_000_000_000
        if not (
            market_open_epoch_ns
            <= ingress_value
            < market_open_epoch_ns + 60_000_000_000
        ):
            blockers.append(f"{session_id}:open_minute_tick_window_mismatch")
    if len(timestamps) == len(timestamp_fields):
        scheduled = timestamps["scheduled_start_epoch_ns"]
        daemon = timestamps["daemon_started_epoch_ns"]
        ingress = timestamps["open_minute_tick_ingress_epoch_ns"]
        durable = timestamps["open_minute_tick_durable_epoch_ns"]
        cycle_started = timestamps["cycle_started_epoch_ns"]
        cycle_finished = timestamps["cycle_finished_epoch_ns"]
        if not (
            scheduled <= daemon <= ingress <= durable
            and scheduled <= daemon <= cycle_started <= cycle_finished
        ):
            blockers.append(f"{session_id}:timestamp_order_invalid")
        if daemon - scheduled > LAUNCHD_START_HARD_DEADLINE_NS:
            blockers.append(f"{session_id}:launchd_start_hard_deadline_exceeded")
        if durable - ingress > INGRESS_DURABLE_HARD_DEADLINE_NS:
            blockers.append(f"{session_id}:ingress_durable_hard_deadline_exceeded")
    return blockers


def evaluate_readonly_qualification(
    records: Iterable[Mapping[str, Any]],
    *,
    expected_manifest_sha256: str,
    expected_source_commit: str,
    required_session_count: int = 5,
) -> dict[str, Any]:
    rows = [dict(record) for record in records]
    blockers: list[str] = []
    seen: set[str] = set()
    seen_stage930_file_hashes: set[str] = set()
    seen_stage930_payload_hashes: set[str] = set()
    qualified_session_count = 0
    kinds: set[str] = set()
    disconnect_reconnect_proof_count = 0

    if type(required_session_count) is not int or required_session_count <= 0:
        raise ValueError("required_session_count_must_be_positive_int")
    for record in rows:
        session_id = _clean(record.get("session_id"))
        if not session_id:
            _append_unique(blockers, "missing_session_id")
        elif session_id in seen:
            _append_unique(blockers, f"duplicate_session_id:{session_id}")
        else:
            seen.add(session_id)
        for field, seen_hashes in (
            ("stage930_summary_sha256", seen_stage930_file_hashes),
            ("stage930_summary_payload_sha256", seen_stage930_payload_hashes),
        ):
            value = _clean(record.get(field))
            if not value:
                continue
            if value in seen_hashes:
                _append_unique(blockers, f"duplicate_{field}:{value}")
            else:
                seen_hashes.add(value)
        row_blockers = _record_blockers(
            record,
            expected_manifest_sha256=expected_manifest_sha256,
            expected_source_commit=expected_source_commit,
        )
        for blocker in row_blockers:
            _append_unique(blockers, blocker)
        if not row_blockers:
            qualified_session_count += 1
        if record.get("session_kind") in {"day", "night"}:
            kinds.add(str(record["session_kind"]))
        if _disconnect_reconnect_proof_valid(record):
            disconnect_reconnect_proof_count += 1

    if len(seen) < required_session_count:
        _append_unique(
            blockers,
            f"qualified_unique_session_count_below_required:{len(seen)}<{required_session_count}",
        )
    if not {"day", "night"}.issubset(kinds):
        _append_unique(blockers, "day_night_session_coverage_incomplete")
    if disconnect_reconnect_proof_count < 1:
        _append_unique(blockers, "disconnect_reconnect_proof_missing")

    return {
        "qualification_status": "qualified" if not blockers else "blocked",
        "required_session_count": required_session_count,
        "observed_record_count": len(rows),
        "unique_session_count": len(seen),
        "unique_stage930_summary_count": len(seen_stage930_file_hashes),
        "unique_stage930_payload_count": len(seen_stage930_payload_hashes),
        "qualified_session_count": qualified_session_count,
        "session_kinds": sorted(kinds),
        "disconnect_reconnect_proof_count": disconnect_reconnect_proof_count,
        "send_order_api_called_count": sum(
            value
            for value in (
                _strict_int(record.get("send_order_api_called_count"))
                for record in rows
            )
            if value is not None
        ),
        "cancel_order_api_called_count": sum(
            value
            for value in (
                _strict_int(record.get("cancel_order_api_called_count"))
                for record in rows
            )
            if value is not None
        ),
        "blockers": blockers,
    }


def _single_argument_value(arguments: list[Any], flag: str) -> str:
    indexes = [index for index, value in enumerate(arguments) if value == flag]
    if len(indexes) != 1:
        return ""
    index = indexes[0]
    return _clean(arguments[index + 1]) if index + 1 < len(arguments) else ""


def build_readonly_session_evidence(
    *,
    stage930_summary: Mapping[str, Any],
    launchd_plist: Mapping[str, Any],
    validated_manifest: Mapping[str, Any],
    launchd_plist_relative_path: str,
    launchd_plist_sha256: str,
    stage930_summary_sha256: str,
    session_kind: str,
) -> dict[str, Any]:
    stage903_summary = _stage903_summary_from_stage930(stage930_summary)
    arguments = launchd_plist.get("ProgramArguments")
    if not isinstance(arguments, list):
        arguments = []
    calendar = launchd_plist.get("StartCalendarInterval")
    if not isinstance(calendar, Mapping):
        calendar = {}
    first_tick = _strict_int(
        stage930_summary.get("open_minute_tick_ingress_epoch_ns")
    )
    durable = _strict_int(
        stage930_summary.get("open_minute_tick_durable_epoch_ns")
    )
    disconnect = stage903_summary.get("stage907_connection_lifecycle")
    if not isinstance(disconnect, Mapping):
        disconnect = {}
    daemon_started_epoch_ns = _strict_int(
        stage930_summary.get("daemon_started_epoch_ns")
    )
    run_id = _clean(stage930_summary.get("run_id"))
    if daemon_started_epoch_ns is None or daemon_started_epoch_ns <= 0 or not run_id:
        raise ValueError("stage930_session_identity_missing")
    started_at = datetime.fromtimestamp(
        daemon_started_epoch_ns // 1_000_000_000,
        tz=SHANGHAI_TZ,
    )
    session_date = started_at.date().isoformat()
    expected_hour = 8 if session_kind == "day" else 20
    scheduled_start_epoch_ns = int(
        datetime(
            started_at.year,
            started_at.month,
            started_at.day,
            expected_hour,
            55,
            tzinfo=SHANGHAI_TZ,
        ).timestamp()
    ) * 1_000_000_000
    session_id = run_id
    disconnect_projection = _disconnect_projection(
        disconnect,
        session_id=session_id,
        runtime_profile=stage930_summary.get("runtime_profile"),
        execution_profile=stage930_summary.get("execution_profile"),
    )
    launchd_provenance = stage930_summary.get("launchd_provenance")
    if not isinstance(launchd_provenance, Mapping):
        launchd_provenance = {}
    record = {
        "capture_schema_version": 2,
        "stage930_summary_sha256": _clean(stage930_summary_sha256),
        "stage930_summary_payload": dict(stage930_summary),
        "stage930_summary_payload_sha256": _mapping_digest(stage930_summary),
        "session_id": session_id,
        "session_date": session_date,
        "session_kind": _clean(session_kind),
        "session_completed": int(
            _clean(stage930_summary.get("daemon_status")).startswith("daemon_completed_")
        ),
        "launchd_label": _clean(launchd_plist.get("Label")),
        "launchd_start_hour": calendar.get("Hour"),
        "launchd_start_minute": calendar.get("Minute"),
        "launchd_plist_relative_path": _clean(launchd_plist_relative_path),
        "launchd_plist_sha256": _clean(launchd_plist_sha256),
        "manifest_launchd_plist_sha256": _clean(launchd_plist_sha256),
        "launchd_provenance_complete": launchd_provenance.get("complete"),
        "launchd_xpc_service_name": launchd_provenance.get(
            "xpc_service_name"
        ),
        "launchd_process_pid": launchd_provenance.get("pid"),
        "launchd_parent_pid": launchd_provenance.get("parent_pid"),
        "launchctl_print_exit_code": launchd_provenance.get(
            "launchctl_print_exit_code"
        ),
        "launchctl_job_pid": launchd_provenance.get("launchctl_job_pid"),
        "execution_profile": stage930_summary.get("execution_profile"),
        "official_live_version": stage930_summary.get("official_live_version"),
        "capital": stage930_summary.get("capital"),
        "capital_label": stage930_summary.get("capital_label"),
        "runtime_profile": stage930_summary.get("runtime_profile"),
        "mode": stage930_summary.get("mode"),
        "submit_mode": stage930_summary.get("submit_mode"),
        "plist_execution_profile": _single_argument_value(
            arguments, "--execution-profile"
        ),
        "plist_runtime_profile": _single_argument_value(
            arguments, "--runtime-profile"
        ),
        "plist_mode": _single_argument_value(arguments, "--mode"),
        "plist_submit_mode": _single_argument_value(arguments, "--submit-mode"),
        "release_manifest_sha256": validated_manifest.get("manifest_sha256"),
        "release_source_commit": validated_manifest.get("source_commit"),
        "stage914_exit_code": stage903_summary.get("stage914_exit_code"),
        "stage914_preflight_status": stage903_summary.get("stage914_preflight_status"),
        "stage914_blocking_failure_count": stage903_summary.get("stage914_blocking_failure_count"),
        "stage907_refresh_status": stage903_summary.get("stage907_refresh_status"),
        "stage907_readonly_status_after": stage903_summary.get("stage907_readonly_status_after"),
        "stage907_position_snapshot_state_after": stage903_summary.get("stage907_position_snapshot_state_after"),
        "send_order_api_called_count": stage930_summary.get("send_order_api_called_count"),
        "cancel_order_api_called_count": stage930_summary.get("cancel_order_api_called_count"),
        "order_api_called_count": stage930_summary.get("order_api_called_count"),
        "order_api_evidence_complete": stage930_summary.get(
            "order_api_evidence_complete"
        ),
        "order_api_evidence_missing_fields": stage930_summary.get(
            "order_api_evidence_missing_fields"
        ),
        "scheduled_start_epoch_ns": scheduled_start_epoch_ns,
        "daemon_started_epoch_ns": stage930_summary.get("daemon_started_epoch_ns"),
        "open_minute_tick_ingress_epoch_ns": first_tick,
        "open_minute_tick_durable_epoch_ns": durable,
        "cycle_started_epoch_ns": stage930_summary.get(
            "open_minute_tick_cycle_started_epoch_ns"
        ),
        "cycle_finished_epoch_ns": stage930_summary.get(
            "open_minute_tick_cycle_finished_epoch_ns"
        ),
        **disconnect_projection,
    }
    record["capture_record_sha256"] = _record_digest(record)
    return record


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path}")
    return value


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_canonical_plist(
    *,
    supplied_path: Path,
    repo_root: Path,
    validated_manifest: Mapping[str, Any],
) -> tuple[str, str, str]:
    if supplied_path.is_symlink():
        raise ValueError("launchd_plist_not_canonical_for_session_kind")
    resolved_supplied = supplied_path.resolve(strict=True)
    matched = [
        (kind, relative)
        for kind, relative in CANONICAL_PLISTS.items()
        if (repo_root / relative).resolve(strict=True) == resolved_supplied
    ]
    if len(matched) != 1:
        raise ValueError("launchd_plist_not_canonical_for_session_kind")
    session_kind, relative = matched[0]
    canonical = (repo_root / relative).resolve(strict=True)
    digest = _sha256_path(canonical)
    rows = validated_manifest.get("critical_files")
    if not isinstance(rows, list):
        raise ValueError("release_manifest_critical_files_missing")
    matches = [
        row
        for row in rows
        if isinstance(row, Mapping) and row.get("path") == relative
    ]
    if len(matches) != 1 or matches[0].get("sha256") != digest:
        raise ValueError("launchd_plist_not_bound_to_release_manifest")
    return session_kind, relative, digest


def _write_new_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(dict(payload), handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            raise FileExistsError(f"evidence_output_already_exists:{path}")
        os.link(temporary, path)
        os.chmod(path, 0o444)
        parent_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        temporary.unlink(missing_ok=True)


def _current_commit(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD^{commit}"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError("current_commit_unavailable")
    return result.stdout.strip()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture and qualify Stage372 Stage179 production-readonly canary evidence."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture = subparsers.add_parser("capture")
    capture.add_argument("--stage930-summary", type=Path, required=True)
    capture.add_argument("--launchd-plist", type=Path, required=True)
    capture.add_argument("--release-manifest", type=Path, required=True)
    capture.add_argument("--repo-root", type=Path, required=True)
    capture.add_argument("--output", type=Path, required=True)
    qualify = subparsers.add_parser("qualify")
    qualify.add_argument("--session-evidence", type=Path, action="append", required=True)
    qualify.add_argument("--expected-manifest-sha256", required=True)
    qualify.add_argument("--expected-source-commit", required=True)
    qualify.add_argument("--required-session-count", type=int, default=5)
    qualify.add_argument("--output", type=Path, required=True)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    if args.command == "capture":
        summary = _read_json(args.stage930_summary)
        with args.launchd_plist.open("rb") as handle:
            plist = plistlib.load(handle)
        manifest = load_and_validate_release_manifest(
            args.release_manifest,
            repo_root=args.repo_root,
            expected_official_version=EXPECTED_OFFICIAL_VERSION,
            expected_capital=EXPECTED_CAPITAL,
            expected_capital_label=EXPECTED_CAPITAL_LABEL,
            expected_execution_profile=EXPECTED_EXECUTION_PROFILE,
            required_runtime_profile=EXPECTED_RUNTIME_PROFILE,
            current_commit=_current_commit(args.repo_root),
        )
        session_kind, plist_relative_path, plist_sha256 = _validate_canonical_plist(
            supplied_path=args.launchd_plist,
            repo_root=args.repo_root.resolve(strict=True),
            validated_manifest=manifest,
        )
        payload = build_readonly_session_evidence(
            stage930_summary=summary,
            launchd_plist=plist,
            validated_manifest=manifest,
            launchd_plist_relative_path=plist_relative_path,
            launchd_plist_sha256=plist_sha256,
            stage930_summary_sha256=_sha256_path(args.stage930_summary),
            session_kind=session_kind,
        )
    else:
        payload = evaluate_readonly_qualification(
            [_read_json(path) for path in args.session_evidence],
            expected_manifest_sha256=args.expected_manifest_sha256,
            expected_source_commit=args.expected_source_commit,
            required_session_count=args.required_session_count,
        )
    _write_new_json(args.output, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0 if payload.get("qualification_status", "qualified") == "qualified" else 2)


if __name__ == "__main__":
    main()
