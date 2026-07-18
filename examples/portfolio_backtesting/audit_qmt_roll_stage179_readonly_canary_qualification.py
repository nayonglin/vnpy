from __future__ import annotations

import argparse
from datetime import date, datetime
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


def _strict_int(value: Any) -> int | None:
    return value if type(value) is int else None


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _append_unique(rows: list[str], value: str) -> None:
    if value not in rows:
        rows.append(value)


def _disconnect_reconnect_proof_valid(record: Mapping[str, Any]) -> bool:
    revoked = _strict_int(record.get("readiness_revoked_epoch_ns"))
    restored = _strict_int(record.get("readiness_restored_epoch_ns"))
    old_generation = _clean(record.get("old_connection_generation"))
    new_generation = _clean(record.get("new_connection_generation"))
    return bool(
        record.get("disconnect_observed") == 1
        and record.get("reconnect_observed") == 1
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
        and record.get("disconnect_send_order_api_called_count") == 0
        and record.get("disconnect_cancel_order_api_called_count") == 0
    )


def _record_blockers(
    record: Mapping[str, Any],
    *,
    expected_manifest_sha256: str,
    expected_source_commit: str,
) -> list[str]:
    session_id = _clean(record.get("session_id")) or "missing-session-id"
    blockers: list[str] = []

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
        "release_manifest_sha256": expected_manifest_sha256,
        "release_source_commit": expected_source_commit,
        "stage914_exit_code": 0,
        "stage914_preflight_status": "production_readonly_preflight_passed",
        "stage914_blocking_failure_count": 0,
        "stage907_refresh_status": "readonly_refresh_completed_snapshot_ready",
        "stage907_readonly_status_after": "readonly_snapshots_received",
        "session_completed": 1,
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
        record.get("disconnect_observed") == 1
        or record.get("reconnect_observed") == 1
    ) and not _disconnect_reconnect_proof_valid(record):
        blockers.append(f"{session_id}:disconnect_reconnect_evidence_invalid")

    timestamp_fields = (
        "scheduled_start_epoch_ns",
        "daemon_started_epoch_ns",
        "first_market_tick_ingress_epoch_ns",
        "first_market_tick_durable_epoch_ns",
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
    ingress_value = timestamps.get("first_market_tick_ingress_epoch_ns")
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
            <= market_open_epoch_ns + 60_000_000_000
        ):
            blockers.append(f"{session_id}:first_market_tick_window_mismatch")
    if len(timestamps) == len(timestamp_fields):
        scheduled = timestamps["scheduled_start_epoch_ns"]
        daemon = timestamps["daemon_started_epoch_ns"]
        ingress = timestamps["first_market_tick_ingress_epoch_ns"]
        durable = timestamps["first_market_tick_durable_epoch_ns"]
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


def _argument_value(arguments: list[Any], flag: str) -> str:
    try:
        index = arguments.index(flag)
    except ValueError:
        return ""
    return _clean(arguments[index + 1]) if index + 1 < len(arguments) else ""


def build_readonly_session_evidence(
    *,
    stage930_summary: Mapping[str, Any],
    launchd_plist: Mapping[str, Any],
    validated_manifest: Mapping[str, Any],
    session_id: str,
    session_date: str,
    session_kind: str,
    scheduled_start_epoch_ns: int,
    first_market_tick_ingress_epoch_ns: int | None = None,
    first_market_tick_durable_epoch_ns: int | None = None,
    disconnect_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    cycle = stage930_summary.get("readonly_qualification_cycle")
    if not isinstance(cycle, Mapping):
        cycle = stage930_summary.get("latest_cycle")
    if not isinstance(cycle, Mapping):
        cycle = {}
    stage903 = cycle.get("stage903")
    stage903_summary = (
        stage903.get("summary")
        if isinstance(stage903, Mapping) and isinstance(stage903.get("summary"), Mapping)
        else {}
    )
    arguments = launchd_plist.get("ProgramArguments")
    if not isinstance(arguments, list):
        arguments = []
    calendar = launchd_plist.get("StartCalendarInterval")
    if not isinstance(calendar, Mapping):
        calendar = {}
    first_tick = (
        first_market_tick_ingress_epoch_ns
        if first_market_tick_ingress_epoch_ns is not None
        else _strict_int(stage930_summary.get("first_market_tick_ingress_epoch_ns"))
    )
    durable = (
        first_market_tick_durable_epoch_ns
        if first_market_tick_durable_epoch_ns is not None
        else _strict_int(
            stage930_summary.get("first_market_tick_durable_epoch_ns")
        )
    )
    disconnect = dict(disconnect_evidence or {})
    return {
        "session_id": _clean(session_id),
        "session_date": _clean(session_date),
        "session_kind": _clean(session_kind),
        "session_completed": int(
            _clean(stage930_summary.get("daemon_status")).startswith("daemon_completed_")
        ),
        "launchd_label": _clean(launchd_plist.get("Label")),
        "launchd_start_hour": calendar.get("Hour"),
        "launchd_start_minute": calendar.get("Minute"),
        "execution_profile": stage930_summary.get("execution_profile"),
        "official_live_version": stage930_summary.get("official_live_version"),
        "capital": stage930_summary.get("capital"),
        "capital_label": stage930_summary.get("capital_label"),
        "runtime_profile": stage930_summary.get("runtime_profile"),
        "mode": stage930_summary.get("mode"),
        "submit_mode": stage930_summary.get("submit_mode"),
        "plist_execution_profile": _argument_value(
            arguments, "--execution-profile"
        ),
        "plist_runtime_profile": _argument_value(
            arguments, "--runtime-profile"
        ),
        "plist_mode": _argument_value(arguments, "--mode"),
        "plist_submit_mode": _argument_value(arguments, "--submit-mode"),
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
        "first_market_tick_ingress_epoch_ns": first_tick,
        "first_market_tick_durable_epoch_ns": durable,
        "cycle_started_epoch_ns": stage930_summary.get(
            "first_market_tick_cycle_started_epoch_ns"
        ),
        "cycle_finished_epoch_ns": stage930_summary.get(
            "first_market_tick_cycle_finished_epoch_ns"
        ),
        "disconnect_observed": disconnect.get("disconnect_observed", 0),
        "reconnect_observed": disconnect.get("reconnect_observed", 0),
        "disconnect_evidence_id": disconnect.get("disconnect_evidence_id", ""),
        "disconnect_session_id": disconnect.get("session_id", ""),
        "disconnect_runtime_profile": disconnect.get("runtime_profile", ""),
        "disconnect_execution_profile": disconnect.get(
            "execution_profile", ""
        ),
        "old_connection_generation": disconnect.get("old_connection_generation", ""),
        "new_connection_generation": disconnect.get("new_connection_generation", ""),
        "readiness_revoked_epoch_ns": disconnect.get("readiness_revoked_epoch_ns"),
        "readiness_restored_epoch_ns": disconnect.get("readiness_restored_epoch_ns"),
        "disconnect_send_order_api_called_count": disconnect.get(
            "send_order_api_called_count"
        ),
        "disconnect_cancel_order_api_called_count": disconnect.get(
            "cancel_order_api_called_count"
        ),
    }


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path}")
    return value


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
    capture.add_argument("--session-id", required=True)
    capture.add_argument("--session-date", required=True)
    capture.add_argument("--session-kind", choices=["day", "night"], required=True)
    capture.add_argument("--scheduled-start-epoch-ns", type=int, required=True)
    capture.add_argument("--first-market-tick-ingress-epoch-ns", type=int)
    capture.add_argument("--first-market-tick-durable-epoch-ns", type=int)
    capture.add_argument("--disconnect-evidence", type=Path)
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
        payload = build_readonly_session_evidence(
            stage930_summary=summary,
            launchd_plist=plist,
            validated_manifest=manifest,
            session_id=args.session_id,
            session_date=args.session_date,
            session_kind=args.session_kind,
            scheduled_start_epoch_ns=args.scheduled_start_epoch_ns,
            first_market_tick_ingress_epoch_ns=args.first_market_tick_ingress_epoch_ns,
            first_market_tick_durable_epoch_ns=args.first_market_tick_durable_epoch_ns,
            disconnect_evidence=(
                _read_json(args.disconnect_evidence)
                if args.disconnect_evidence
                else None
            ),
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
