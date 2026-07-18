from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
import sys
import unittest
from zoneinfo import ZoneInfo


PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

from audit_qmt_roll_stage179_readonly_canary_qualification import (  # noqa: E402
    build_readonly_session_evidence,
    evaluate_readonly_qualification,
)


MANIFEST_SHA256 = "a" * 64
SOURCE_COMMIT = "b" * 40


def session_record(index: int, *, session_kind: str) -> dict[str, object]:
    session_date = f"2026-07-{20 + index:02d}"
    scheduled = datetime(
        2026,
        7,
        20 + index,
        8 if session_kind == "day" else 20,
        55,
        tzinfo=ZoneInfo("Asia/Shanghai"),
    )
    scheduled_epoch_ns = int(scheduled.timestamp() * 1_000_000_000)
    ingress = scheduled_epoch_ns + 300_000_000_000
    return {
        "session_id": f"session-{index}",
        "session_date": session_date,
        "session_kind": session_kind,
        "session_completed": 1,
        "launchd_label": (
            "local.qmt-roll.official-live.20w.stage372-day-session"
            if session_kind == "day"
            else "local.qmt-roll.official-live.20w.stage372-night-session"
        ),
        "launchd_start_hour": 8 if session_kind == "day" else 20,
        "launchd_start_minute": 55,
        "execution_profile": "stage372-20w",
        "official_live_version": "official_live_stage372_20w_recovery_sleeve",
        "capital": 200_000,
        "capital_label": "20w",
        "runtime_profile": "production-readonly",
        "mode": "dry-run",
        "submit_mode": "disabled",
        "plist_execution_profile": "stage372-20w",
        "plist_runtime_profile": "production-readonly",
        "plist_mode": "dry-run",
        "plist_submit_mode": "disabled",
        "release_manifest_sha256": MANIFEST_SHA256,
        "release_source_commit": SOURCE_COMMIT,
        "stage914_exit_code": 0,
        "stage914_preflight_status": "production_readonly_preflight_passed",
        "stage914_blocking_failure_count": 0,
        "stage907_refresh_status": "readonly_refresh_completed_snapshot_ready",
        "stage907_readonly_status_after": "readonly_snapshots_received",
        "stage907_position_snapshot_state_after": "confirmed_flat",
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "order_api_called_count": 0,
        "order_api_evidence_complete": 1,
        "order_api_evidence_missing_fields": [],
        "scheduled_start_epoch_ns": scheduled_epoch_ns,
        "daemon_started_epoch_ns": scheduled_epoch_ns + 5_000_000_000,
        "first_market_tick_ingress_epoch_ns": ingress,
        "first_market_tick_durable_epoch_ns": ingress + 100_000_000,
        "cycle_started_epoch_ns": ingress + 1_000_000,
        "cycle_finished_epoch_ns": ingress + 300_000_000,
        "disconnect_observed": int(index == 4),
        "reconnect_observed": int(index == 4),
        "disconnect_evidence_id": "disconnect-session-4" if index == 4 else "",
        "disconnect_session_id": "session-4" if index == 4 else "",
        "disconnect_runtime_profile": "production-readonly" if index == 4 else "",
        "disconnect_execution_profile": "stage372-20w" if index == 4 else "",
        "old_connection_generation": "connection-old" if index == 4 else "",
        "new_connection_generation": "connection-new" if index == 4 else "",
        "readiness_revoked_epoch_ns": ingress + 400_000_000 if index == 4 else None,
        "readiness_restored_epoch_ns": ingress + 500_000_000 if index == 4 else None,
        "disconnect_send_order_api_called_count": 0 if index == 4 else None,
        "disconnect_cancel_order_api_called_count": 0 if index == 4 else None,
    }


class Stage179ReadonlyCanaryQualificationTest(unittest.TestCase):
    def qualify(self, records: list[dict[str, object]]) -> dict[str, object]:
        return evaluate_readonly_qualification(
            records,
            expected_manifest_sha256=MANIFEST_SHA256,
            expected_source_commit=SOURCE_COMMIT,
            required_session_count=5,
        )

    def test_missing_explicit_order_counter_fails_closed(self) -> None:
        records = [session_record(index, session_kind="day" if index < 2 else "night") for index in range(5)]
        records[0].pop("send_order_api_called_count")

        result = self.qualify(records)

        self.assertEqual("blocked", result["qualification_status"])
        self.assertIn(
            "session-0:missing_send_order_api_called_count",
            result["blockers"],
        )

    def test_incomplete_order_counter_provenance_fails_closed(self) -> None:
        records = [session_record(index, session_kind="day" if index < 2 else "night") for index in range(5)]
        records[0]["order_api_evidence_complete"] = 0
        records[0]["order_api_evidence_missing_fields"] = [
            "stage903.summary.send_order_api_called_count"
        ]

        result = self.qualify(records)

        self.assertIn("session-0:order_api_evidence_incomplete", result["blockers"])

    def test_capture_binds_daemon_controller_plist_and_manifest(self) -> None:
        source = session_record(0, session_kind="night")
        summary = {
            "daemon_status": "daemon_completed_duration",
            "daemon_started_epoch_ns": source["daemon_started_epoch_ns"],
            "execution_profile": source["execution_profile"],
            "official_live_version": source["official_live_version"],
            "capital": source["capital"],
            "capital_label": source["capital_label"],
            "runtime_profile": source["runtime_profile"],
            "mode": source["mode"],
            "submit_mode": source["submit_mode"],
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
            "order_api_called_count": 0,
            "order_api_evidence_complete": 1,
            "order_api_evidence_missing_fields": [],
            "first_market_tick_ingress_epoch_ns": source["first_market_tick_ingress_epoch_ns"],
            "first_market_tick_durable_epoch_ns": source["first_market_tick_durable_epoch_ns"],
            "first_market_tick_cycle_started_epoch_ns": source["cycle_started_epoch_ns"],
            "first_market_tick_cycle_finished_epoch_ns": source["cycle_finished_epoch_ns"],
            "latest_cycle": {
                "stage903": {
                    "summary": {
                        "stage914_exit_code": 0,
                        "stage914_preflight_status": "production_readonly_preflight_passed",
                        "stage914_blocking_failure_count": 0,
                        "stage907_refresh_status": "readonly_refresh_completed_snapshot_ready",
                        "stage907_readonly_status_after": "readonly_snapshots_received",
                        "stage907_position_snapshot_state_after": "confirmed_flat",
                    }
                }
            },
        }
        plist = {
            "Label": source["launchd_label"],
            "StartCalendarInterval": {"Hour": 20, "Minute": 55},
            "ProgramArguments": [
                "python",
                "daemon.py",
                "--mode",
                "dry-run",
                "--submit-mode",
                "disabled",
                "--execution-profile",
                "stage372-20w",
                "--runtime-profile",
                "production-readonly",
            ],
        }

        captured = build_readonly_session_evidence(
            stage930_summary=summary,
            launchd_plist=plist,
            validated_manifest={
                "manifest_sha256": MANIFEST_SHA256,
                "source_commit": SOURCE_COMMIT,
            },
            session_id="session-0",
            session_date=str(source["session_date"]),
            session_kind="night",
            scheduled_start_epoch_ns=int(source["scheduled_start_epoch_ns"]),
        )

        self.assertEqual(source, captured)

    def test_five_day_night_sessions_and_reconnect_qualify(self) -> None:
        records = [session_record(index, session_kind="day" if index < 2 else "night") for index in range(5)]

        result = self.qualify(records)

        self.assertEqual("qualified", result["qualification_status"])
        self.assertEqual([], result["blockers"])
        self.assertEqual(5, result["qualified_session_count"])
        self.assertEqual(["day", "night"], result["session_kinds"])
        self.assertEqual(1, result["disconnect_reconnect_proof_count"])

    def test_disconnect_booleans_without_generation_evidence_do_not_qualify(self) -> None:
        records = [session_record(index, session_kind="day" if index < 2 else "night") for index in range(5)]
        records[4]["disconnect_evidence_id"] = ""
        records[4]["old_connection_generation"] = "same"
        records[4]["new_connection_generation"] = "same"

        result = self.qualify(records)

        self.assertIn("session-4:disconnect_reconnect_evidence_invalid", result["blockers"])
        self.assertIn("disconnect_reconnect_proof_missing", result["blockers"])

    def test_disconnect_evidence_must_bind_same_session_and_profile(self) -> None:
        records = [session_record(index, session_kind="day" if index < 2 else "night") for index in range(5)]
        records[4]["disconnect_runtime_profile"] = "simnow"

        result = self.qualify(records)

        self.assertIn("session-4:disconnect_reconnect_evidence_invalid", result["blockers"])

    def test_duplicate_session_and_nonzero_cancel_fail(self) -> None:
        records = [session_record(index, session_kind="day" if index < 2 else "night") for index in range(5)]
        duplicate = deepcopy(records[-1])
        duplicate["cancel_order_api_called_count"] = 1
        duplicate["order_api_called_count"] = 1
        records.append(duplicate)

        result = self.qualify(records)

        self.assertEqual("blocked", result["qualification_status"])
        self.assertIn("duplicate_session_id:session-4", result["blockers"])
        self.assertIn("session-4:cancel_order_api_called_count_nonzero", result["blockers"])

    def test_launchd_schedule_must_be_exact_0855_or_2055(self) -> None:
        records = [session_record(index, session_kind="day" if index < 2 else "night") for index in range(5)]
        records[0]["launchd_start_minute"] = 56

        result = self.qualify(records)

        self.assertIn("session-0:launchd_schedule_mismatch", result["blockers"])

    def test_daemon_and_plist_runtime_identity_must_both_match(self) -> None:
        records = [session_record(index, session_kind="day" if index < 2 else "night") for index in range(5)]
        records[0]["plist_runtime_profile"] = "offline"

        result = self.qualify(records)

        self.assertIn("session-0:plist_runtime_profile_mismatch", result["blockers"])

    def test_scheduled_epoch_must_match_session_date_and_plist_time(self) -> None:
        records = [session_record(index, session_kind="day" if index < 2 else "night") for index in range(5)]
        records[0]["scheduled_start_epoch_ns"] = (
            int(records[0]["scheduled_start_epoch_ns"]) + 60_000_000_000
        )

        result = self.qualify(records)

        self.assertIn("session-0:scheduled_start_identity_mismatch", result["blockers"])

    def test_first_tick_must_arrive_in_first_minute_after_market_open(self) -> None:
        records = [session_record(index, session_kind="day" if index < 2 else "night") for index in range(5)]
        records[0]["first_market_tick_ingress_epoch_ns"] = (
            int(records[0]["first_market_tick_ingress_epoch_ns"])
            - 1_000_000_000
        )

        result = self.qualify(records)

        self.assertIn("session-0:first_market_tick_window_mismatch", result["blockers"])

    def test_missing_or_late_timestamps_fail_readonly_e2e_gate(self) -> None:
        records = [session_record(index, session_kind="day" if index < 2 else "night") for index in range(5)]
        records[0].pop("first_market_tick_ingress_epoch_ns")
        records[1]["first_market_tick_durable_epoch_ns"] = (
            int(records[1]["first_market_tick_ingress_epoch_ns"])
            + 1_000_000_001
        )

        result = self.qualify(records)

        self.assertEqual("blocked", result["qualification_status"])
        self.assertIn(
            "session-0:missing_first_market_tick_ingress_epoch_ns",
            result["blockers"],
        )
        self.assertIn("session-1:ingress_durable_hard_deadline_exceeded", result["blockers"])


if __name__ == "__main__":
    unittest.main()
