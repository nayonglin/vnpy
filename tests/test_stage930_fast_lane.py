from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import call, patch
import json
import os
import plistlib
import signal
import subprocess
import sys
import tempfile
import time
import unittest

import pandas as pd


os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import run_qmt_roll_stage930_official_live_c9_session_daemon as stage930
import run_qmt_roll_stage929_official_live_15w_timed_cycle as stage929
import run_qmt_roll_stage904_official_live_c9_intraday_monitor as stage904
import run_ctp_stage608_readonly_tick_snapshot_probe as stage608
from qmt_roll_official_live_submit_authorization import (  # noqa: E402
    validate_submit_authorization,
)


class _ShortLivedController:
    def __init__(self, *_args, **_kwargs) -> None:
        self.returncode = 0
        self.poll_count = 0
        self.pid = 999999

    def poll(self) -> int | None:
        self.poll_count += 1
        return None if self.poll_count == 1 else 0


class _TickStreamProcess:
    def __init__(self, pid: int, exit_code: int | None) -> None:
        self.pid = pid
        self.exit_code = exit_code

    def poll(self) -> int | None:
        return self.exit_code


class _LongLivedController:
    def __init__(self) -> None:
        self.pid = 888888
        self.returncode: int | None = None
        self.wait_called = False
        self.wait_count = 0

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        self.wait_called = True
        self.wait_count += 1
        if self.wait_count == 1:
            raise subprocess.TimeoutExpired("fake-stage931", timeout or 0)
        self.returncode = -9
        return self.returncode


class Stage930FastLaneTest(unittest.TestCase):
    @staticmethod
    def wait_for_path(path: Path, timeout_seconds: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if path.exists():
                return True
            time.sleep(0.02)
        return path.exists()

    def args(self) -> SimpleNamespace:
        return SimpleNamespace(
            mode="dry-run",
            submit_mode="disabled",
            shadow_refresh_mode="plan-only",
            readonly_refresh_mode="plan-only",
            readonly_wait_seconds=1,
            stage251_mode="skip",
            max_snapshot_age_seconds=300,
            controller_timeout_seconds=10,
            confirm_live_real="",
            tick_refresh_mode="stream",
            fast_poll_seconds=1.0,
            fast_tick_age_seconds=10,
            fast_step_timeout_seconds=20,
            vt_symbol=["JM609.DCE"],
            detector_mode="legacy-subprocess",
            detector_poll_seconds=0.05,
            detector_batch_size=1024,
            detector_max_restarts=3,
            detector_restart_backoff_seconds=2.0,
            target_date="2026-07-16",
        )

    def test_parser_defaults_to_legacy_detector_mode(self) -> None:
        args = stage930._build_parser().parse_args([])

        self.assertEqual("legacy-subprocess", args.detector_mode)
        self.assertEqual("legacy-once", args.stage179_execution_mode)
        self.assertEqual("offline", args.runtime_profile)

    def test_tick_ingress_evidence_uses_newest_exact_integer(self) -> None:
        result = stage930._tick_result_ingress_epoch_ns(
            {
                "refresh_status": "tick_stream_ready",
                "transport_ready": 1,
                "stream_ready": 1,
                "all_symbols_ready": 1,
                "heartbeat_pid_matches_process": 1,
                "summary": {
                    "latest_ticks": {
                        "JM609.DCE": {"ingress_epoch_ns": 200},
                        "I609.DCE": {"ingress_epoch_ns": 100},
                        "J609.DCE": {"ingress_epoch_ns": True},
                    }
                }
            }
        )

        self.assertEqual(200, result)

    def test_tick_durable_evidence_requires_exact_heartbeat_epoch(self) -> None:
        self.assertEqual(
            300,
            stage930._tick_result_durable_epoch_ns(
                {"summary": {"generated_epoch_ns": 300}}
            ),
        )
        self.assertIsNone(
            stage930._tick_result_durable_epoch_ns(
                {"summary": {"generated_epoch_ns": True}}
            )
        )

    def test_session_timing_evidence_keeps_first_open_minute_tick_cycle(self) -> None:
        result = stage930._session_timing_evidence(
            [
                {
                    "cycle_started_epoch_ns": 10,
                    "cycle_finished_epoch_ns": 20,
                    "open_minute_tick_ingress_epoch_ns": None,
                    "open_minute_tick_durable_epoch_ns": None,
                },
                {
                    "cycle_started_epoch_ns": 30,
                    "cycle_finished_epoch_ns": 50,
                    "open_minute_tick_ingress_epoch_ns": 40,
                    "open_minute_tick_durable_epoch_ns": 41,
                },
                {
                    "cycle_started_epoch_ns": 60,
                    "cycle_finished_epoch_ns": 80,
                    "open_minute_tick_ingress_epoch_ns": 70,
                    "open_minute_tick_durable_epoch_ns": 71,
                },
            ]
        )

        self.assertEqual(40, result["open_minute_tick_ingress_epoch_ns"])
        self.assertEqual(30, result["open_minute_tick_cycle_started_epoch_ns"])
        self.assertEqual(41, result["open_minute_tick_durable_epoch_ns"])
        self.assertEqual(50, result["open_minute_tick_cycle_finished_epoch_ns"])

    def test_tick_ingress_evidence_requires_ready_bound_heartbeat(self) -> None:
        result = stage930._tick_result_ingress_epoch_ns(
            {
                "refresh_status": "tick_stream_not_ready_fail_closed",
                "transport_ready": 0,
                "stream_ready": 0,
                "all_symbols_ready": 0,
                "heartbeat_pid_matches_process": 1,
                "summary": {
                    "symbol_tick_watermarks": {
                        "JM609.DCE": {"ingress_epoch_ns": 200}
                    }
                },
            }
        )

        self.assertIsNone(result)

    def test_no_submit_prewarm_counters_are_bound_to_readiness(self) -> None:
        evidence = stage930._no_submit_prewarm_order_evidence(
            {
                "service_kind": "no_submit_prewarm",
                "spool_opened": 0,
                "ctp_module_loaded": 0,
                "send_order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
                "order_api_called_count": 0,
            }
        )
        forged = stage930._no_submit_prewarm_order_evidence(
            {
                "service_kind": "no_submit_prewarm",
                "spool_opened": 0,
                "ctp_module_loaded": 0,
                "order_api_called_count": 0,
            }
        )

        self.assertEqual(1, evidence["complete"])
        self.assertEqual(0, evidence["send_order_api_called_count"])
        self.assertEqual(0, forged["complete"])

    def test_readonly_qualification_cycle_keeps_latest_complete_snapshot(self) -> None:
        ready = {
            "cycle_started_epoch_ns": 30,
            "stage903": {
                "summary": {
                    "stage914_exit_code": 0,
                    "stage914_preflight_status": "production_readonly_preflight_passed",
                    "stage914_blocking_failure_count": 0,
                    "stage907_refresh_status": "readonly_refresh_completed_snapshot_ready",
                    "stage907_readonly_status_after": "readonly_snapshots_received",
                    "stage907_position_snapshot_state_after": "confirmed_flat",
                }
            },
        }
        newer_ready = json.loads(json.dumps(ready))
        newer_ready["cycle_started_epoch_ns"] = 40
        outside_session = {
            "cycle_started_epoch_ns": 50,
            "stage903": {
                "summary": {
                    "stage914_exit_code": 0,
                    "stage914_preflight_status": "production_readonly_preflight_passed",
                    "stage914_blocking_failure_count": 0,
                    "stage907_refresh_status": "readonly_refresh_planned",
                }
            },
        }

        result = stage930._readonly_qualification_cycle(
            [ready, newer_ready, outside_session]
        )

        self.assertEqual(40, result["cycle_started_epoch_ns"])

    def test_order_api_evidence_reports_missing_explicit_source_counter(self) -> None:
        missing = stage930._missing_order_api_evidence_fields(
            stage903_result={
                "summary": {"send_order_api_called_count": 0}
            },
            stage927_result={"summary": {}},
            stage931_result={
                "summary": {
                    "send_order_api_called_count": 0,
                    "cancel_order_api_called_count": 0,
                }
            },
            post_submit_reduce_close={
                "summary": {
                    "send_order_api_called_count": 0,
                    "cancel_order_api_called_count": 0,
                }
            },
        )

        self.assertEqual(
            {
                "stage903.summary.cancel_order_api_called_count",
                "stage903.summary.send_order_api_attempted_count",
                "stage903.summary.cancel_order_api_attempted_count",
                "stage903.summary.order_api_evidence_complete",
                "stage931.summary.order_api_evidence_complete",
            },
            set(missing),
        )

    def test_order_api_evidence_rejects_incomplete_fast_lane_provenance(self) -> None:
        complete_summary = {
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
        }
        missing = stage930._missing_order_api_evidence_fields(
            stage903_result={"summary": complete_summary},
            stage927_result={
                "summary": {},
                "fast_lane_run_count": 1,
                "fast_lane_send_order_api_called_count": 0,
                "fast_lane_cancel_order_api_called_count": 0,
                "fast_lane_order_api_evidence_complete": 0,
                "fast_lane_order_api_evidence_missing_fields": [
                    "persistent_detector_order_api_count_invalid"
                ],
            },
            stage931_result={"summary": complete_summary},
            post_submit_reduce_close={"summary": complete_summary},
        )

        self.assertIn(
            "stage927.fast_lane_order_api_evidence_complete",
            missing,
        )

    def test_warm_stage931_service_is_singleton_across_cycle_starts(self) -> None:
        args = self.args()
        args.stage179_execution_mode = "warm"
        args.runtime_profile = "offline"
        args.stage179_runtime_root = ""
        args.release_manifest = ""
        args.activation_receipt = ""
        args.confirm_stage179_activation = ""
        process = _TickStreamProcess(pid=777777, exit_code=None)
        stage930._STAGE931_SERVICE_PROCESS = None
        stage930._STAGE931_SERVICE_RUNTIME = None
        try:
            with patch.object(
                stage930,
                "_managed_popen",
                return_value=process,
            ) as popen:
                first = stage930._start_stage931_service(args)
                second = stage930._start_stage931_service(args)

            self.assertIs(first, process)
            self.assertIs(second, process)
            popen.assert_called_once()
            command = popen.call_args.args[0]
            self.assertIn("serve", command)
            self.assertIn("--stage179-warm-executor", command)
            self.assertIn("offline", command)
        finally:
            stage930._STAGE931_SERVICE_PROCESS = None
            stage930._STAGE931_SERVICE_RUNTIME = None

    def test_warm_no_submit_cycle_never_wakes_or_spawns_legacy_stage931(self) -> None:
        args = self.args()
        args.stage179_execution_mode = "warm"
        args.runtime_profile = "offline"
        args.stage179_runtime_root = ""
        controller = {
            "summary": {
                "target_date": "2026-07-16",
                "stage905_ready_count": 0,
                "send_order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
                "order_api_called_count": 0,
            }
        }
        warm_status = {
            "submit_status": "warm_executor_no_submit_ready",
            "exit_code": 0,
            "summary": {
                "order_api_called_count": 0,
                "send_order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
            },
        }
        with (
            patch.object(stage930, "_start_stage931_service") as start,
            patch.object(stage930, "_market_execution_session_active", return_value=False),
            patch.object(stage930, "_watched_symbols_for_args", return_value=[]),
            patch.object(stage930, "_run_stage903", return_value=controller),
            patch.object(stage930, "_status_stage931_service", return_value=warm_status),
            patch.object(stage930, "_wake_stage931_service", return_value=True) as wake,
            patch.object(stage930, "_revoke_stage931_submit_authorization") as revoke,
            patch.object(stage930, "_publish_stage931_submit_authorization") as publish,
            patch.object(stage930, "_run_stage931") as legacy,
        ):
            cycle = stage930.run_cycle(
                args,
                "2026-07-16",
                {"command_log": Path("unused")},
            )

        start.assert_called_once_with(args)
        wake.assert_not_called()
        publish.assert_not_called()
        self.assertGreaterEqual(revoke.call_count, 1)
        legacy.assert_not_called()
        self.assertEqual("warm_executor_no_submit_ready", cycle["stage931"]["submit_status"])
        self.assertEqual(0, cycle["stage931"]["wake_socket_notified"])
        self.assertEqual("offline", cycle["runtime_profile"])
        self.assertEqual(0, cycle["send_order_api_called_count"])
        self.assertEqual(0, cycle["cancel_order_api_called_count"])
        self.assertIsInstance(cycle["cycle_started_epoch_ns"], int)
        self.assertIsInstance(cycle["cycle_finished_epoch_ns"], int)
        self.assertLessEqual(
            cycle["cycle_started_epoch_ns"],
            cycle["cycle_finished_epoch_ns"],
        )

    def test_warm_live_cycle_publishes_authorization_before_wake(self) -> None:
        args = self.args()
        args.mode = "live-real"
        args.submit_mode = "live-real"
        args.stage179_execution_mode = "warm"
        args.runtime_profile = "simnow"
        args.stage179_runtime_root = ""
        args.ai_pool_preflight_allowed = 1
        controller_summary = {
            "target_date": "2026-07-16",
            "controller_status": "phase_d_controller_live_real_ready_no_submit_step",
            "stage905_executor_status": "executor_dry_run_ready",
            "stage905_blocked_count": 0,
            "stage905_ready_count": 1,
            "stage904_retry_open_dry_run_count": 0,
            "order_api_called_count": 0,
        }
        stage927_summary = {
            "real_submit_permitted": 1,
            "order_api_called_count": 0,
        }
        tick_gate = {
            "refresh_status": "tick_stream_ready",
            "all_symbols_ready": 1,
            "symbol_tick_freshness": {"blocked_new_risk_symbols": []},
        }
        warm_status = {
            "submit_status": "warm_executor_ready",
            "exit_code": 0,
            "readiness": {
                "status": "ready",
                "service_generation": "service-1",
                "connection_generation": "connection-1",
            },
            "summary": {"order_api_called_count": 0},
        }
        events: list[str] = []
        with (
            patch.object(stage930, "_start_stage931_service"),
            patch.object(stage930, "_revoke_stage931_submit_authorization"),
            patch.object(stage930, "_market_execution_session_active", return_value=True),
            patch.object(stage930, "_watched_symbols_for_args", return_value=["JM609.DCE"]),
            patch.object(stage930, "_run_tick_refresh", return_value=tick_gate),
            patch.object(stage930, "_run_stage903", return_value={"summary": controller_summary}),
            patch.object(stage930, "_run_stage927", return_value={"summary": stage927_summary}),
            patch.object(stage930, "_managed_tick_stream_status", return_value=tick_gate),
            patch.object(stage930, "_ready_intents_close_only", return_value=False),
            patch.object(stage930, "_ready_reduce_close_count", return_value=0),
            patch.object(stage930, "_status_stage931_service", return_value=warm_status),
            patch.object(
                stage930,
                "_publish_stage931_submit_authorization",
                side_effect=lambda *_args, **_kwargs: events.append("publish")
                or {"authorized": 1, "cycle_id": "cycle-1"},
            ),
            patch.object(
                stage930,
                "_wake_stage931_service",
                side_effect=lambda *_: events.append("wake") or True,
            ),
            patch.object(stage930, "_run_stage931") as legacy,
        ):
            cycle = stage930.run_cycle(
                args,
                "2026-07-16",
                {"command_log": Path("unused")},
            )

        self.assertEqual(["publish", "wake"], events)
        legacy.assert_not_called()
        self.assertEqual(1, cycle["stage931"]["wake_socket_notified"])
        self.assertEqual(1, cycle["stage931"]["submit_authorization"]["authorized"])

    def test_published_live_authorization_is_self_validating(self) -> None:
        args = self.args()
        args.runtime_profile = "simnow"
        args.poll_seconds = 30
        with tempfile.TemporaryDirectory() as directory:
            args.stage179_runtime_root = directory
            runtime = stage930._stage179_runtime(args)
            stage930._STAGE931_SERVICE_RUNTIME = runtime
            try:
                readiness = {
                    "status": "ready",
                    "service_generation": "service-1",
                    "connection_generation": "connection-1",
                    "runtime_profile": "simnow",
                    "order_scope": "test",
                    "expires_epoch_ns": time.time_ns() + 3_000_000_000,
                }
                controller = {
                    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "target_date": "2026-07-16",
                    "controller_status": "phase_d_controller_live_real_ready_no_submit_step",
                    "stage905_executor_status": "executor_dry_run_ready",
                    "stage905_blocked_count": 0,
                    "stage905_ready_count": 1,
                }
                intents_path = Path(directory) / "stage905-intents.csv"
                pd.DataFrame(
                    [
                        {
                            "intent_id": "approved-intent",
                            "payload_sha256": "a" * 64,
                            "offset": "open",
                            "target_date": "2026-07-16",
                            "executor_status": "dry_run_order_request_payload_ready",
                        }
                    ]
                ).to_csv(intents_path, index=False)
                with patch.object(
                    stage930,
                    "_stage905_intents_path",
                    return_value=intents_path,
                ):
                    result = stage930._publish_stage931_submit_authorization(
                        args,
                        target_date="2026-07-16",
                        controller_summary=controller,
                        stage927_summary={
                            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "real_submit_permitted": 1,
                        },
                        tick_gate={
                            "all_symbols_ready": 1,
                            "summary": {
                                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            },
                        },
                        service_status={
                            "submit_status": "warm_executor_ready",
                            "readiness": readiness,
                        },
                        reduce_close_only=False,
                    )

                blockers = validate_submit_authorization(
                    path=result["authorization_path"],
                    target_date="2026-07-16",
                    execution_profile="c9-15w-historical",
                    runtime_profile="simnow",
                    order_scope="test",
                    service_generation="service-1",
                    connection_generation="connection-1",
                    now_epoch_ns=time.time_ns(),
                    intent_id="approved-intent",
                    payload_sha256="a" * 64,
                    intent_kind="open",
                )
            finally:
                stage930._STAGE931_SERVICE_RUNTIME = None

        self.assertEqual(1, result["authorized"])
        self.assertEqual([], blockers)

    def test_stage930_authorization_excludes_intent_committed_after_publish(self) -> None:
        args = self.args()
        args.runtime_profile = "simnow"
        args.poll_seconds = 30
        with tempfile.TemporaryDirectory() as directory:
            args.stage179_runtime_root = directory
            runtime = stage930._stage179_runtime(args)
            stage930._STAGE931_SERVICE_RUNTIME = runtime
            intents_path = Path(directory) / "stage905-intents.csv"
            pd.DataFrame(
                [
                    {
                        "intent_id": "cycle-approved",
                        "payload_sha256": "a" * 64,
                        "offset": "open",
                        "target_date": "2026-07-16",
                        "executor_status": "dry_run_order_request_payload_ready",
                    }
                ]
            ).to_csv(intents_path, index=False)
            now_ns = time.time_ns()
            try:
                with patch.object(
                    stage930,
                    "_stage905_intents_path",
                    return_value=intents_path,
                ):
                    result = stage930._publish_stage931_submit_authorization(
                        args,
                        target_date="2026-07-16",
                        controller_summary={
                            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "target_date": "2026-07-16",
                            "controller_status": "phase_d_controller_live_real_ready_no_submit_step",
                            "stage905_executor_status": "executor_dry_run_ready",
                            "stage905_blocked_count": 0,
                            "stage905_ready_count": 1,
                        },
                        stage927_summary={
                            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "real_submit_permitted": 1,
                        },
                        tick_gate={
                            "all_symbols_ready": 1,
                            "summary": {
                                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            },
                        },
                        service_status={
                            "submit_status": "warm_executor_ready",
                            "readiness": {
                                "status": "ready",
                                "service_generation": "service-1",
                                "connection_generation": "connection-1",
                                "expires_epoch_ns": now_ns + 3_000_000_000,
                            },
                        },
                        reduce_close_only=False,
                    )
                blocker = validate_submit_authorization(
                    path=result["authorization_path"],
                    target_date="2026-07-16",
                    execution_profile="c9-15w-historical",
                    runtime_profile="simnow",
                    order_scope="test",
                    service_generation="service-1",
                    connection_generation="connection-1",
                    now_epoch_ns=time.time_ns(),
                    intent_id="post-publish-new",
                    payload_sha256="b" * 64,
                    intent_kind="open",
                )
            finally:
                stage930._STAGE931_SERVICE_RUNTIME = None

        self.assertEqual(1, result["authorized"])
        self.assertIn(
            "stage179_submit_authorization_intent_not_authorized",
            blocker,
        )

    def test_stage931_stop_revokes_readiness_before_terminating_child(self) -> None:
        events: list[str] = []
        with tempfile.TemporaryDirectory() as directory:
            runtime = SimpleNamespace(
                readiness_path=Path(directory) / "readiness.json"
            )
            runtime.readiness_path.write_text(
                json.dumps({"service_generation": "service-1"}),
                encoding="utf-8",
            )
            process = _TickStreamProcess(pid=777778, exit_code=None)
            stage930._STAGE931_SERVICE_RUNTIME = runtime
            stage930._STAGE931_SERVICE_PROCESS = process
            with (
                patch.object(
                    stage930,
                    "revoke_readiness",
                    side_effect=lambda *_args, **_kwargs: events.append("revoke"),
                ),
                patch.object(
                    stage930,
                    "_terminate_managed_child",
                    side_effect=lambda *_: events.append("terminate"),
                ),
            ):
                stage930._stop_stage931_service("test")

        self.assertEqual(["revoke", "terminate"], events)
        self.assertIsNone(stage930._STAGE931_SERVICE_PROCESS)

    def test_legacy_empty_target_date_stays_unresolved_for_latest_completed(self) -> None:
        args = stage930._build_parser().parse_args([])

        self.assertEqual("", stage930._startup_target_date(args))

    def test_persistent_mode_requires_explicit_authoritative_target_date(self) -> None:
        args = self.args()
        args.detector_mode = "persistent"
        args.target_date = ""

        blockers = stage930._startup_configuration_blockers(args)

        self.assertIn(
            "persistent_detector_requires_explicit_target_date",
            blockers,
        )

    def test_persistent_mode_with_live_submit_and_warm_simnow_is_reachable(self) -> None:
        args = self.args()
        args.detector_mode = "persistent"
        args.mode = "live-real"
        args.submit_mode = "live-real"
        args.stage179_execution_mode = "warm"
        args.runtime_profile = "simnow"

        blockers = stage930._startup_configuration_blockers(args)

        self.assertEqual([], blockers)

    def test_persistent_no_submit_offline_prewarm_is_reachable(self) -> None:
        args = self.args()
        args.detector_mode = "persistent"
        args.stage179_execution_mode = "warm"
        args.runtime_profile = "offline"

        self.assertEqual([], stage930._startup_configuration_blockers(args))

    def test_persistent_mixed_controller_and_submit_modes_fail_closed(self) -> None:
        args = self.args()
        args.detector_mode = "persistent"
        args.stage179_execution_mode = "warm"
        args.runtime_profile = "simnow"
        args.mode = "dry-run"
        args.submit_mode = "live-real"

        self.assertIn(
            "persistent_detector_controller_submit_mode_mismatch",
            stage930._startup_configuration_blockers(args),
        )

    def test_persistent_mode_never_spawns_stage904_or_stage905_subprocess(self) -> None:
        args = self.args()
        args.detector_mode = "persistent"
        persistent_status = {
            "fast_lane_status": "persistent_detector_ready_no_submit",
            "target_date": "2026-07-16",
            "order_api_called_count": 0,
        }
        with tempfile.TemporaryDirectory() as tmp:
            paths = {"command_log": Path(tmp) / "commands.log"}
            with (
                patch.object(
                    stage930,
                    "_persistent_detector_fast_lane_status",
                    return_value=persistent_status,
                ) as status_reader,
                patch.object(stage930, "_run_command") as run_command,
                patch.object(stage930, "_run_stage931") as stage931_run,
            ):
                result = stage930._run_fast_intraday_lane(
                    args,
                    "2026-07-16",
                    paths,
                )

        self.assertEqual(persistent_status, result)
        status_reader.assert_called_once()
        run_command.assert_not_called()
        stage931_run.assert_not_called()

    def test_runtime_service_start_order_is_tick_detector_then_ai(self) -> None:
        args = self.args()
        args.detector_mode = "persistent"
        events: list[str] = []
        with (
            patch.object(
                stage930,
                "_initialize_tick_stream_supervisor",
                side_effect=lambda *_: events.append("tick") or {"enabled": 1},
            ),
            patch.object(
                stage930,
                "_initialize_detector_supervisor",
                side_effect=lambda *_, **__: events.append("detector") or {"enabled": 1},
            ),
            patch.object(
                stage930,
                "_run_stage935_preflight",
                side_effect=lambda *_: events.append("ai") or {"allowed_to_continue": 1},
            ),
        ):
            stage930._initialize_runtime_services(
                args,
                {"command_log": Path("unused")},
                target_date="2026-07-16",
            )

        self.assertEqual(["tick", "detector", "ai"], events)

    def test_slow_controller_uses_external_intraday_mode_and_runs_fast_lane(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = {"command_log": Path(tmp) / "commands.log"}
            fast_result = {"fast_lane_status": "ok", "order_api_called_count": 0}
            with (
                patch.object(stage930.subprocess, "Popen", _ShortLivedController),
                patch.object(stage930, "_market_execution_session_active", return_value=True),
                patch.object(stage930, "_run_fast_intraday_lane", return_value=fast_result) as fast,
                patch.object(stage930.time, "sleep", return_value=None),
            ):
                result = stage930._run_stage903(self.args(), "2026-07-13", paths)

        command = result["command"]
        self.assertIn("--intraday-execution-mode", command)
        self.assertIn("external", command)
        self.assertIn("--intraday-tick-refresh-mode", command)
        self.assertEqual(result["fast_lane_runs"], [fast_result])
        self.assertEqual(result["fast_lane_order_api_called_count"], 0)
        fast.assert_called_once()

    def test_fast_lane_exception_is_structured_and_does_not_escape(self) -> None:
        args = self.args()
        with tempfile.TemporaryDirectory() as tmp:
            paths = {"command_log": Path(tmp) / "commands.log"}
            with patch.object(
                stage930,
                "_run_fast_intraday_lane",
                side_effect=RuntimeError("bad fast lane"),
            ):
                result = stage930._safe_run_fast_intraday_lane(
                    args,
                    "2026-07-13",
                    paths,
                )

        self.assertEqual(result["fast_lane_status"], "fast_lane_exception_fail_closed")
        self.assertIn("bad fast lane", result["exception"])
        self.assertEqual(result["order_api_called_count"], 0)

    def test_slow_child_is_killed_if_owner_loop_itself_raises(self) -> None:
        args = self.args()
        child = _LongLivedController()
        with tempfile.TemporaryDirectory() as tmp:
            paths = {
                "command_log": Path(tmp) / "commands.log",
                "events_ndjson": Path(tmp) / "events.ndjson",
            }
            with (
                patch.object(stage930.subprocess, "Popen", return_value=child) as popen,
                patch.object(stage930, "_market_execution_session_active", return_value=False),
                patch.object(stage930.time, "sleep", side_effect=RuntimeError("owner loop failed")),
                patch.object(
                    stage930,
                    "_process_group_alive",
                    side_effect=lambda process: process.returncode is None,
                ),
                patch.object(stage930.os, "killpg") as killpg,
            ):
                with self.assertRaisesRegex(RuntimeError, "owner loop failed"):
                    stage930._run_command_with_fast_lane(
                        ["fake"],
                        timeout_seconds=10,
                        log_path=paths["command_log"],
                        label="fake_slow",
                        args=args,
                        target_date="2026-07-13",
                        paths=paths,
                    )

        self.assertEqual(
            killpg.call_args_list,
            [
                call(child.pid, stage930.signal.SIGTERM),
                call(child.pid, stage930.signal.SIGKILL),
            ],
        )
        self.assertTrue(child.wait_called)
        self.assertEqual(popen.call_args.kwargs["process_group"], 0)
        self.assertNotIn("start_new_session", popen.call_args.kwargs)

    def test_managed_guard_preserves_target_stdout_and_returncode(self) -> None:
        code = "import os, sys; print(f'target-pid={os.getpid()}'); sys.exit(7)"
        process = stage930._managed_popen(
            [sys.executable, "-c", code],
            cwd=PORTFOLIO_DIR.parents[1],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        try:
            stdout, _ = process.communicate(timeout=8)
        finally:
            stage930._unregister_active_child(process)

        self.assertEqual(process.returncode, 7, stdout)
        self.assertRegex(stdout, r"^target-pid=\d+\n$")

        killed = stage930._managed_popen(
            [sys.executable, "-c", "import os, signal; os.kill(os.getpid(), signal.SIGKILL)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        try:
            killed.wait(timeout=8)
        finally:
            stage930._unregister_active_child(killed)
        self.assertEqual(killed.returncode, -signal.SIGKILL)

    def test_managed_guard_escalates_to_kill_for_term_ignoring_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target_pid_path = Path(tmp) / "target.pid"
            code = "\n".join(
                [
                    "import os, signal, time",
                    "from pathlib import Path",
                    "signal.signal(signal.SIGTERM, signal.SIG_IGN)",
                    f"Path({str(target_pid_path)!r}).write_text(str(os.getpid()), encoding='utf-8')",
                    "while True: time.sleep(0.1)",
                ]
            )
            process = stage930._managed_popen(
                [sys.executable, "-c", code],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )
            self.assertTrue(self.wait_for_path(target_pid_path), "managed target never started")
            target_pid = int(target_pid_path.read_text(encoding="utf-8"))
            started = time.monotonic()
            stage930._terminate_managed_child(process, term_timeout_seconds=6.0)

        self.assertLess(time.monotonic() - started, 5.0)
        self.assertEqual(process.returncode, -signal.SIGTERM)
        with self.assertRaises(ProcessLookupError):
            os.kill(target_pid, 0)

    def test_shutdown_during_spawn_register_gap_is_deferred_then_cleans_child(self) -> None:
        harness = "\n".join(
            [
                "import signal, subprocess, sys, time",
                f"sys.path.insert(0, {str(PORTFOLIO_DIR)!r})",
                "import run_qmt_roll_stage930_official_live_c9_session_daemon as stage930",
                "real_popen = stage930.subprocess.Popen",
                "holder = {}",
                "def injecting_popen(*args, **kwargs):",
                "    child = real_popen([sys.executable, '-c', 'import time; time.sleep(5)'], process_group=0)",
                "    holder['child'] = child",
                "    stage930._handle_shutdown_signal(signal.SIGTERM, None)",
                "    return child",
                "stage930.subprocess.Popen = injecting_popen",
                "caught = False",
                "try:",
                "    stage930._managed_popen(['ignored'])",
                "except stage930.DaemonShutdownRequested:",
                "    caught = True",
                "finally:",
                "    stage930.subprocess.Popen = real_popen",
                "child = holder['child']",
                "try:",
                "    child.wait(timeout=5)",
                "except subprocess.TimeoutExpired:",
                "    child.kill(); child.wait(timeout=5)",
                "raise SystemExit(0 if caught and child.returncode is not None else 1)",
            ]
        )
        result = subprocess.run(
            [sys.executable, "-c", harness],
            cwd=PORTFOLIO_DIR.parents[1],
            env={**os.environ, "QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR": "1"},
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_sigterm_owner_cleanup_kills_slow_stage931_before_side_effect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            started = root / "stage931_started"
            ledger = root / "fake_execution_ledger.ndjson"
            heartbeat = root / "tick_heartbeat.json"
            command_log = root / "command.log"
            events = root / "events.ndjson"
            grandchild_code = "\n".join(
                [
                    "from pathlib import Path",
                    "import time",
                    "time.sleep(1.0)",
                    f"ledger = Path({str(ledger)!r})",
                    "with ledger.open('a', encoding='utf-8') as handle:",
                    "    handle.write('send_order_side_effect\\n')",
                ]
            )
            child_code = "\n".join(
                [
                    "from pathlib import Path",
                    "import subprocess",
                    "import sys",
                    "import time",
                    f"started = Path({str(started)!r})",
                    f"grandchild_code = {grandchild_code!r}",
                    "subprocess.Popen([sys.executable, '-c', grandchild_code])",
                    "started.write_text('stage931-running', encoding='utf-8')",
                    "time.sleep(5.0)",
                ]
            )
            harness = "\n".join(
                [
                    "from pathlib import Path",
                    "from types import SimpleNamespace",
                    "import signal",
                    "import sys",
                    f"sys.path.insert(0, {str(PORTFOLIO_DIR)!r})",
                    "import run_qmt_roll_stage930_official_live_c9_session_daemon as stage930",
                    f"stage930.TICK_STREAM_HEARTBEAT_PATH = Path({str(heartbeat)!r})",
                    "stage930._market_execution_session_active = lambda: False",
                    "stage930._activate_runtime_ownership()",
                    "exit_code = 0",
                    "try:",
                    "    stage930._run_command_with_fast_lane(",
                    f"        [sys.executable, '-c', {child_code!r}],",
                    "        timeout_seconds=10,",
                    f"        log_path=Path({str(command_log)!r}),",
                    "        label='fake_stage931_submit',",
                    "        args=SimpleNamespace(fast_poll_seconds=1.0),",
                    "        target_date='2026-07-13',",
                    f"        paths={{'command_log': Path({str(command_log)!r}), 'events_ndjson': Path({str(events)!r})}},",
                    "    )",
                    "except stage930.DaemonShutdownRequested as exc:",
                    "    exit_code = 128 + exc.signum",
                    "finally:",
                    "    stage930._shutdown_runtime('test_harness_finally')",
                    "raise SystemExit(exit_code)",
                ]
            )
            env = os.environ.copy()
            env["QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR"] = "1"
            owner = subprocess.Popen(
                [sys.executable, "-c", harness],
                cwd=PORTFOLIO_DIR.parents[1],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.assertTrue(self.wait_for_path(started), "fake Stage931 never started")
            ledger_size_before = ledger.stat().st_size if ledger.exists() else 0
            owner.send_signal(signal.SIGTERM)
            stdout, _ = owner.communicate(timeout=8)
            time.sleep(1.1)

            self.assertEqual(owner.returncode, 128 + signal.SIGTERM, stdout)
            self.assertEqual(ledger.stat().st_size if ledger.exists() else 0, ledger_size_before)
            self.assertFalse(ledger.exists(), stdout)

    def test_sigkill_owner_pipe_eof_kills_stage931_and_grandchild_before_side_effect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            started = root / "stage931_started"
            marker = root / "late_send_order_side_effect"
            grandchild_code = "\n".join(
                [
                    "from pathlib import Path",
                    "import time",
                    "time.sleep(0.8)",
                    f"Path({str(marker)!r}).write_text('send_order', encoding='utf-8')",
                ]
            )
            stage931_code = "\n".join(
                [
                    "from pathlib import Path",
                    "import subprocess, sys, time",
                    f"grandchild_code = {grandchild_code!r}",
                    "subprocess.Popen([sys.executable, '-c', grandchild_code])",
                    f"Path({str(started)!r}).write_text('running', encoding='utf-8')",
                    "time.sleep(5.0)",
                ]
            )
            harness = "\n".join(
                [
                    "import subprocess, sys, time",
                    f"sys.path.insert(0, {str(PORTFOLIO_DIR)!r})",
                    "import run_qmt_roll_stage930_official_live_c9_session_daemon as stage930",
                    "stage930._activate_runtime_ownership()",
                    "process = stage930._managed_popen(",
                    f"    [sys.executable, '-c', {stage931_code!r}],",
                    "    stdout=subprocess.DEVNULL,",
                    "    stderr=subprocess.STDOUT,",
                    ")",
                    "while process.poll() is None:",
                    "    time.sleep(0.1)",
                ]
            )
            owner = subprocess.Popen(
                [sys.executable, "-c", harness],
                cwd=PORTFOLIO_DIR.parents[1],
                env={**os.environ, "QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR": "1"},
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                self.assertTrue(self.wait_for_path(started), "fake Stage931 never started")
                owner.kill()
                stdout, _ = owner.communicate(timeout=8)
                time.sleep(1.0)
            finally:
                if owner.poll() is None:
                    owner.kill()
                    owner.wait(timeout=5)

            self.assertEqual(owner.returncode, -signal.SIGKILL, stdout)
            self.assertFalse(marker.exists(), stdout)

    def test_stale_stream_still_replays_durable_reduce_close_state(self) -> None:
        args = self.args()
        with tempfile.TemporaryDirectory() as tmp:
            paths = {"command_log": Path(tmp) / "commands.log"}
            with (
                patch.object(
                    stage930,
                    "_tick_stream_status",
                    return_value={"stream_ready": 0, "refresh_status": "tick_stream_not_ready_fail_closed"},
                ),
                patch.object(stage930, "_run_command", return_value={"exit_code": 0, "stdout": ""}) as run_command,
                patch.object(stage930, "_read_json", return_value={}),
                patch.object(stage930, "_ready_reduce_close_count", return_value=0),
            ):
                result = stage930._run_fast_intraday_lane(args, "2026-07-13", paths)

        self.assertEqual(result["fast_lane_status"], "fast_lane_monitor_complete")
        self.assertEqual(result["order_api_called_count"], 0)
        self.assertEqual(run_command.call_count, 2)

    def test_stream_mode_never_calls_cold_snapshot_refresh(self) -> None:
        args = self.args()
        with tempfile.TemporaryDirectory() as tmp:
            paths = {"command_log": Path(tmp) / "commands.log"}
            expected = {"refresh_status": "tick_stream_ready", "stream_ready": 1, "order_api_called_count": 0}
            with (
                patch.object(stage930, "_tick_stream_status", return_value=expected) as status,
                patch.object(stage930, "_run_command") as cold_refresh,
            ):
                result = stage930._run_tick_refresh(args, "2026-07-13", ["JM609.DCE"], paths)

        self.assertEqual(result, expected)
        status.assert_called_once_with(["JM609.DCE"], max_tick_age_seconds=10.0)
        cold_refresh.assert_not_called()

    def test_tick_stream_requires_each_watched_symbol_to_be_fresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            heartbeat_path = Path(tmp) / "heartbeat.json"
            now = datetime.now()
            base = {
                "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                "transport_ready": True,
                "stream_ready": True,
                "stopped": False,
            }
            cases = {
                "fresh": (
                    {
                        "JM609.DCE": {
                            "received_at": (now - timedelta(seconds=1)).isoformat(timespec="microseconds"),
                            "stream_sequence": 10,
                        }
                    },
                    1,
                    [],
                ),
                "stalled": (
                    {
                        "JM609.DCE": {
                            "received_at": (now - timedelta(seconds=30)).isoformat(timespec="microseconds"),
                            "stream_sequence": 10,
                        }
                    },
                    0,
                    ["JM609.DCE"],
                ),
                "future": (
                    {
                        "JM609.DCE": {
                            "received_at": (now + timedelta(seconds=4)).isoformat(timespec="microseconds"),
                            "stream_sequence": 10,
                        }
                    },
                    0,
                    ["JM609.DCE"],
                ),
                "missing": ({}, 0, ["JM609.DCE"]),
            }
            with patch.object(stage930, "TICK_STREAM_HEARTBEAT_PATH", heartbeat_path):
                for name, (watermarks, expected_ready, expected_blocked) in cases.items():
                    with self.subTest(name=name):
                        heartbeat_path.write_text(
                            json.dumps({**base, "symbol_tick_watermarks": watermarks}),
                            encoding="utf-8",
                        )
                        result = stage930._tick_stream_status(
                            ["JM609.DCE"],
                            max_tick_age_seconds=10.0,
                        )
                        self.assertEqual(result["all_symbols_ready"], expected_ready)
                        self.assertEqual(
                            result["symbol_tick_freshness"]["blocked_new_risk_symbols"],
                            expected_blocked,
                        )

    def test_guarded_tick_stream_binds_heartbeat_to_stage930_owner_pid(self) -> None:
        now = datetime.now()
        process = _TickStreamProcess(101, None)
        setattr(process, "_stage930_owned_child_guard", True)
        supervisor = {"enabled": 1, "process": process, "restart_count": 0, "max_restarts": 1}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat = root / "heartbeat.json"
            heartbeat.write_text(
                json.dumps(
                    {
                        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                        "transport_ready": True,
                        "stream_ready": True,
                        "stopped": False,
                        "pid": 202,
                        "parent_pid": os.getpid(),
                        "symbol_tick_watermarks": {
                            "JM609.DCE": {
                                "received_at": now.isoformat(timespec="microseconds"),
                                "stream_sequence": 1,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(stage930, "TICK_STREAM_HEARTBEAT_PATH", heartbeat),
                patch.object(stage930, "TICK_STREAM_MANIFEST_PATH", root / "manifest.json"),
                patch.object(stage930, "READONLY_TICKS_PATH", root / "ticks.csv"),
            ):
                result = stage930._tick_stream_status(
                    ["JM609.DCE"],
                    supervisor=supervisor,
                    max_tick_age_seconds=10.0,
                )

        self.assertEqual(result["heartbeat_pid_matches_process"], 1)
        self.assertEqual(result["stream_ready"], 1)
        self.assertEqual(result["tick_stream_supervisor"]["process_is_owned_child_guard"], 1)

    def test_stale_symbol_blocks_new_risk_but_not_reduce_close(self) -> None:
        args = self.args()
        args.mode = "live-real"
        args.submit_mode = "live-real"
        args.ai_pool_preflight_allowed = 1
        controller = {
            "controller_status": "phase_d_controller_live_real_ready_no_submit_step",
            "stage905_executor_status": "executor_dry_run_ready",
            "stage905_blocked_count": 0,
            "stage905_ready_count": 1,
            "stage904_retry_open_dry_run_count": 0,
        }
        stage927 = {"real_submit_permitted": 1}
        tick_result = {
            "all_symbols_ready": 0,
            "symbol_tick_freshness": {"blocked_new_risk_symbols": ["JM609.DCE"]},
        }

        with patch.object(stage930, "_ready_intents_close_only", return_value=False):
            open_blockers = stage930._stage931_submit_blockers(
                args, "2026-07-13", controller, stage927, 1, tick_result
            )
        with patch.object(stage930, "_ready_intents_close_only", return_value=True):
            close_blockers = stage930._stage931_submit_blockers(
                args, "2026-07-13", controller, stage927, 1, tick_result
            )

        self.assertTrue(
            any(item.startswith("tick_stream_symbols_not_fresh_for_new_risk") for item in open_blockers)
        )
        self.assertFalse(
            any(item.startswith("tick_stream_symbols_not_fresh_for_new_risk") for item in close_blockers)
        )

    def test_run_cycle_rechecks_symbol_freshness_immediately_before_stage931(self) -> None:
        args = self.args()
        args.mode = "live-real"
        args.submit_mode = "live-real"
        args.ai_pool_preflight_allowed = 1
        cycle_start_tick = {
            "refresh_status": "tick_stream_ready",
            "all_symbols_ready": 1,
            "symbol_tick_freshness": {"blocked_new_risk_symbols": []},
        }
        pre_submit_tick = {
            "refresh_status": "tick_stream_symbol_freshness_blocked_new_risk",
            "all_symbols_ready": 0,
            "symbol_tick_freshness": {"blocked_new_risk_symbols": ["JM609.DCE"]},
        }
        controller = {
            "summary": {
                "target_date": "2026-07-13",
                "controller_status": "phase_d_controller_live_real_ready_no_submit_step",
                "stage905_executor_status": "executor_dry_run_ready",
                "stage905_blocked_count": 0,
                "stage905_ready_count": 1,
                "stage904_retry_open_dry_run_count": 0,
                "order_api_called_count": 0,
            }
        }
        with (
            patch.object(stage930, "_market_execution_session_active", return_value=True),
            patch.object(stage930, "_watched_symbols_for_args", return_value=["JM609.DCE"]),
            patch.object(stage930, "_run_tick_refresh", return_value=cycle_start_tick),
            patch.object(stage930, "_run_stage903", return_value=controller),
            patch.object(
                stage930,
                "_run_stage927",
                return_value={"summary": {"real_submit_permitted": 1, "order_api_called_count": 0}},
            ),
            patch.object(stage930, "_managed_tick_stream_status", return_value=pre_submit_tick) as gate,
            patch.object(stage930, "_ready_intents_close_only", return_value=False),
            patch.object(stage930, "_ready_reduce_close_count", return_value=0),
            patch.object(stage930, "_run_stage931") as submit,
        ):
            cycle = stage930.run_cycle(
                args,
                "2026-07-13",
                {"command_log": Path("unused"), "events_ndjson": Path("unused")},
            )

        gate.assert_called_once()
        submit.assert_not_called()
        self.assertIs(cycle["pre_submit_tick_gate"], pre_submit_tick)
        self.assertTrue(
            any(
                item.startswith("tick_stream_symbols_not_fresh_for_new_risk")
                for item in cycle["stage931_submit_blockers"]
            )
        )

    def test_between_cycle_wait_keeps_fast_lane_running(self) -> None:
        args = self.args()
        clock = [0.0]

        def monotonic() -> float:
            return clock[0]

        def sleeper(seconds: float) -> None:
            clock[0] += seconds

        with tempfile.TemporaryDirectory() as tmp:
            paths = {
                "command_log": Path(tmp) / "commands.log",
                "events_ndjson": Path(tmp) / "events.ndjson",
            }
            result_row = {"fast_lane_status": "ok", "order_api_called_count": 0}
            with (
                patch.object(stage930, "_market_execution_session_active", return_value=True),
                patch.object(stage930, "_run_fast_intraday_lane", return_value=result_row) as fast,
                patch.object(stage930, "LATEST_EVENT_LOG_PATH", Path(tmp) / "latest_events.ndjson"),
            ):
                result = stage930._run_idle_fast_lane(
                    args,
                    "2026-07-13",
                    paths,
                    wait_seconds=2.5,
                    monotonic=monotonic,
                    sleeper=sleeper,
                )

        self.assertEqual(result["run_count"], 3)
        self.assertEqual(result["order_api_called_count"], 0)
        self.assertEqual(len(result["recent_runs"]), 3)
        self.assertEqual(fast.call_count, 3)

    def test_ai_pool_failure_blocks_open_but_not_reduce_close(self) -> None:
        args = self.args()
        args.mode = "live-real"
        args.submit_mode = "live-real"
        args.ai_pool_preflight_allowed = 0
        controller = {
            "controller_status": "phase_d_controller_live_real_ready_no_submit_step",
            "stage905_executor_status": "executor_dry_run_ready",
            "stage905_blocked_count": 0,
            "stage905_ready_count": 1,
            "stage904_retry_open_dry_run_count": 0,
        }
        stage927 = {"real_submit_permitted": 1}

        with patch.object(stage930, "_ready_intents_close_only", return_value=False):
            open_blockers = stage930._stage931_submit_blockers(args, "2026-07-13", controller, stage927, 1)
        with patch.object(stage930, "_ready_intents_close_only", return_value=True):
            close_blockers = stage930._stage931_submit_blockers(args, "2026-07-13", controller, stage927, 1)

        self.assertIn("ai_pool_preflight_blocked_new_risk_but_reduce_close_remains_allowed", open_blockers)
        self.assertNotIn("ai_pool_preflight_blocked_new_risk_but_reduce_close_remains_allowed", close_blockers)

    def test_dead_tick_stream_child_is_restarted_with_a_bounded_budget(self) -> None:
        args = self.args()
        args.tick_stream_max_restarts = 1
        args.tick_stream_restart_backoff_seconds = 0.0
        dead = _TickStreamProcess(101, 7)
        replacement = _TickStreamProcess(202, None)
        args._tick_stream_supervisor = {
            "enabled": 1,
            "process": dead,
            "restart_count": 0,
            "max_restarts": 1,
            "next_restart_monotonic": 0.0,
            "last_exit_code": None,
            "last_start_error": "",
        }
        with tempfile.TemporaryDirectory() as tmp:
            heartbeat = Path(tmp) / "heartbeat.json"
            heartbeat.write_text('{"transport_ready":true,"stream_ready":true,"pid":101}', encoding="utf-8")
            with (
                patch.object(stage930, "TICK_STREAM_HEARTBEAT_PATH", heartbeat),
                patch.object(stage930, "_start_tick_stream", return_value=replacement) as start,
            ):
                supervisor = stage930._supervise_tick_stream(args, {"command_log": Path("unused")}, monotonic=lambda: 1.0)
            revoked = json.loads(heartbeat.read_text(encoding="utf-8"))

        self.assertIsNotNone(supervisor)
        assert supervisor is not None
        self.assertIs(supervisor["process"], replacement)
        self.assertEqual(supervisor["restart_count"], 1)
        self.assertEqual(supervisor["last_exit_code"], 7)
        self.assertFalse(revoked["transport_ready"])
        self.assertEqual(revoked["supervisor_revocation_reason"], "tick_stream_child_exited:7")
        start.assert_called_once()

        replacement.exit_code = 9
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(stage930, "TICK_STREAM_HEARTBEAT_PATH", Path(tmp) / "heartbeat.json"),
                patch.object(stage930, "_start_tick_stream") as exhausted_start,
            ):
                exhausted = stage930._supervise_tick_stream(args, {"command_log": Path("unused")}, monotonic=lambda: 2.0)
        assert exhausted is not None
        self.assertIsNone(exhausted["process"])
        self.assertEqual(exhausted["restart_count"], 1)
        exhausted_start.assert_not_called()

    def test_persistent_tick_restart_waits_for_clean_detector_drain(self) -> None:
        args = self.args()
        args.detector_mode = "persistent"
        args.tick_stream_max_restarts = 1
        args.tick_stream_restart_backoff_seconds = 0.0
        dead = _TickStreamProcess(101, 7)
        replacement = _TickStreamProcess(202, None)
        args._tick_stream_supervisor = {
            "enabled": 1,
            "process": dead,
            "restart_count": 0,
            "max_restarts": 1,
            "next_restart_monotonic": 0.0,
            "last_exit_code": None,
            "last_start_error": "",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tick_heartbeat = root / "tick-heartbeat.json"
            detector_heartbeat = root / "detector-heartbeat.json"
            terminal = {
                "journal_authority_committed": True,
                "journal_session_state": "clean_stopped",
                "clean_shutdown": True,
                "stopped": True,
                "stream_ready": False,
                "transport_ready": False,
                "writer_alive": False,
                "accepting": False,
                "gap_latched": False,
                "writer_fault": None,
                "dropped_tick_count": 0,
                "queue_depth": 0,
                "feed_session_id": "feed-a",
                "durable_ingress_sequence": 5,
                "last_ingress_sequence": 5,
                "durable_journal_byte_offset": 500,
                "journal_schema": "stage179_framed_v1",
                "journal_segment_path": str(root / "feed-a.ndjson"),
                "heartbeat_revision_uuid": "terminal-a",
            }
            tick_heartbeat.write_text(json.dumps(terminal), encoding="utf-8")
            detector_heartbeat.write_text(
                json.dumps(
                    {
                        "cursor_after": {
                            "feed_session_id": "feed-a",
                            "ingress_sequence": 4,
                            "journal_byte_offset": 400,
                            "journal_schema": "stage179_framed_v1",
                        }
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(stage930, "TICK_STREAM_HEARTBEAT_PATH", tick_heartbeat),
                patch.object(stage930, "STAGE941_HEARTBEAT_PATH", detector_heartbeat),
                patch.object(stage930, "_start_tick_stream", return_value=replacement) as start,
            ):
                waiting = stage930._supervise_tick_stream(
                    args,
                    {"command_log": root / "commands.log"},
                    monotonic=lambda: 1.0,
                )
                assert waiting is not None
                waiting_process = waiting["process"]
                waiting_phase = waiting["restart_phase"]
                detector_heartbeat.write_text(
                    json.dumps(
                        {
                            "cursor_after": {
                                "feed_session_id": "feed-a",
                                "ingress_sequence": 5,
                                "journal_byte_offset": 500,
                                "journal_schema": "stage179_framed_v1",
                            }
                        }
                    ),
                    encoding="utf-8",
                )
                restarted = stage930._supervise_tick_stream(
                    args,
                    {"command_log": root / "commands.log"},
                    monotonic=lambda: 2.0,
                )

        assert restarted is not None
        self.assertIsNone(waiting_process)
        self.assertEqual("awaiting_detector_drain", waiting_phase)
        self.assertIs(restarted["process"], replacement)
        self.assertEqual("running", restarted["restart_phase"])
        start.assert_called_once()

    def test_persistent_tick_restart_blocks_unclean_terminal_feed(self) -> None:
        args = self.args()
        args.detector_mode = "persistent"
        args.tick_stream_max_restarts = 1
        args.tick_stream_restart_backoff_seconds = 0.0
        dead = _TickStreamProcess(101, 7)
        args._tick_stream_supervisor = {
            "enabled": 1,
            "process": dead,
            "restart_count": 0,
            "max_restarts": 1,
            "next_restart_monotonic": 0.0,
            "last_exit_code": None,
            "last_start_error": "",
            "restart_phase": "running",
            "restart_blocker": "",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat = root / "tick-heartbeat.json"
            heartbeat.write_text(
                json.dumps(
                    {
                        "journal_authority_committed": True,
                        "journal_session_state": "unclean_stopped",
                        "clean_shutdown": False,
                        "stopped": True,
                        "stream_ready": False,
                        "transport_ready": False,
                        "writer_alive": False,
                        "accepting": False,
                        "gap_latched": True,
                        "writer_fault": {"kind": "forced_shutdown"},
                        "dropped_tick_count": 0,
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(stage930, "TICK_STREAM_HEARTBEAT_PATH", heartbeat),
                patch.object(stage930, "_start_tick_stream") as start,
            ):
                supervisor = stage930._supervise_tick_stream(
                    args,
                    {"command_log": root / "commands.log"},
                    monotonic=lambda: 1.0,
                )

                again = stage930._supervise_tick_stream(
                    args,
                    {"command_log": root / "commands.log"},
                    monotonic=lambda: 2.0,
                )

        assert supervisor is not None
        assert again is not None
        self.assertIsNone(supervisor["process"])
        self.assertEqual(
            "blocked_unclean_previous_feed",
            supervisor["restart_phase"],
        )
        self.assertIn(
            "terminal_tick_heartbeat_invalid",
            supervisor["restart_blocker"],
        )
        self.assertEqual(0, supervisor["restart_count"])
        self.assertIsNone(again["process"])
        self.assertEqual(
            "blocked_unclean_previous_feed",
            again["restart_phase"],
        )
        self.assertEqual(0, again["restart_count"])
        start.assert_not_called()

    def test_persistent_tick_restart_rejects_terminal_watermark_behind_last_ingress(self) -> None:
        terminal = {
            "journal_authority_committed": True,
            "journal_session_state": "clean_stopped",
            "clean_shutdown": True,
            "stopped": True,
            "stream_ready": False,
            "transport_ready": False,
            "writer_alive": False,
            "accepting": False,
            "gap_latched": False,
            "writer_fault": None,
            "dropped_tick_count": 0,
            "queue_depth": 0,
            "feed_session_id": "feed-a",
            "last_ingress_sequence": 6,
            "durable_ingress_sequence": 5,
            "durable_journal_byte_offset": 500,
            "journal_schema": "stage179_framed_v1",
            "journal_segment_path": "/tmp/feed-a.ndjson",
            "heartbeat_revision_uuid": "terminal-a",
        }

        blocker = stage930._clean_terminal_tick_heartbeat_blocker(terminal)

        self.assertEqual("terminal_tick_heartbeat_not_fully_durable", blocker)

    def test_persistent_tick_restart_accepts_detector_drain_of_clean_empty_feed(self) -> None:
        args = self.args()
        args.detector_mode = "persistent"
        args.tick_stream_max_restarts = 1
        args.tick_stream_restart_backoff_seconds = 0.0
        dead = _TickStreamProcess(101, 0)
        replacement = _TickStreamProcess(202, None)
        args._tick_stream_supervisor = {
            "enabled": 1,
            "process": dead,
            "restart_count": 0,
            "max_restarts": 1,
            "next_restart_monotonic": 0.0,
            "last_exit_code": None,
            "last_start_error": "",
            "restart_phase": "running",
            "restart_blocker": "",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tick_heartbeat = root / "tick-heartbeat.json"
            detector_heartbeat = root / "detector-heartbeat.json"
            terminal = {
                "journal_authority_committed": True,
                "journal_session_state": "clean_stopped",
                "clean_shutdown": True,
                "stopped": True,
                "stream_ready": False,
                "transport_ready": False,
                "writer_alive": False,
                "accepting": False,
                "gap_latched": False,
                "writer_fault": None,
                "dropped_tick_count": 0,
                "queue_depth": 0,
                "feed_session_id": "feed-b",
                "last_ingress_sequence": 0,
                "durable_ingress_sequence": 0,
                "durable_journal_byte_offset": 0,
                "journal_schema": "stage179_framed_v1",
                "journal_segment_path": str(root / "feed-b.ndjson"),
                "heartbeat_revision_uuid": "heartbeat-b-terminal",
                "prior_authoritative_feed_session_id": "feed-a",
                "prior_authoritative_journal_segment_path": str(root / "feed-a.ndjson"),
                "prior_authoritative_heartbeat_revision_uuid": "heartbeat-a-terminal",
                "prior_authoritative_journal_session_state": "clean_stopped",
                "prior_authoritative_clean_shutdown": True,
                "recovery_previous_durable_cursor": {
                    "feed_session_id": "feed-a",
                    "ingress_sequence": 5,
                    "journal_byte_offset": 500,
                    "journal_schema": "stage179_framed_v1",
                },
                "prior_uncommitted_gaps": [],
                "prior_authoritative_empty_feed_sessions": [],
            }
            tick_heartbeat.write_text(json.dumps(terminal), encoding="utf-8")
            detector_heartbeat.write_text(
                json.dumps(
                    {
                        "ready": True,
                        "stopped": False,
                        "cycle_status": "detector_idle_caught_up",
                        "tick_count": 0,
                        "blockers": [],
                        "cursor_after": {
                            "feed_session_id": "feed-a",
                            "ingress_sequence": 5,
                            "journal_byte_offset": 500,
                            "journal_schema": "stage179_framed_v1",
                        },
                        "durable_through": {
                            "feed_session_id": "feed-b",
                            "ingress_sequence": 0,
                            "journal_byte_offset": 0,
                            "journal_schema": "stage179_framed_v1",
                        },
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(stage930, "TICK_STREAM_HEARTBEAT_PATH", tick_heartbeat),
                patch.object(stage930, "STAGE941_HEARTBEAT_PATH", detector_heartbeat),
                patch.object(stage930, "_start_tick_stream", return_value=replacement) as start,
            ):
                supervisor = stage930._supervise_tick_stream(
                    args,
                    {"command_log": root / "commands.log"},
                    monotonic=lambda: 1.0,
                )

        assert supervisor is not None
        self.assertIs(replacement, supervisor["process"])
        self.assertEqual("running", supervisor["restart_phase"])
        self.assertEqual(1, supervisor["restart_count"])
        start.assert_called_once()

    def test_dead_persistent_detector_restarts_with_new_instance_id_once(self) -> None:
        args = self.args()
        args.detector_mode = "persistent"
        args.detector_max_restarts = 1
        args.detector_restart_backoff_seconds = 0.0
        dead = _TickStreamProcess(301, 9)
        replacement = _TickStreamProcess(302, None)
        args._detector_supervisor = {
            "enabled": 1,
            "process": dead,
            "instance_id": "old-instance",
            "restart_count": 0,
            "max_restarts": 1,
            "next_restart_monotonic": 0.0,
            "last_exit_code": None,
            "last_start_error": "",
            "blockers": [],
            "target_date": "2026-07-16",
        }
        with patch.object(
            stage930,
            "_start_detector",
            return_value=replacement,
        ) as start:
            supervisor = stage930._supervise_detector(
                args,
                {"command_log": Path("unused")},
                monotonic=lambda: 1.0,
            )

        assert supervisor is not None
        self.assertIs(supervisor["process"], replacement)
        self.assertEqual(1, supervisor["restart_count"])
        self.assertNotEqual("old-instance", supervisor["instance_id"])
        start.assert_called_once_with(
            args,
            {"command_log": Path("unused")},
            target_date="2026-07-16",
            instance_id=supervisor["instance_id"],
        )

    def test_persistent_detector_rejects_fresh_old_instance_heartbeat(self) -> None:
        args = self.args()
        args.detector_mode = "persistent"
        args._detector_supervisor = {
            "enabled": 1,
            "process": _TickStreamProcess(401, None),
            "instance_id": "new-instance",
            "restart_count": 0,
            "max_restarts": 1,
            "next_restart_monotonic": 0.0,
            "last_exit_code": None,
            "last_start_error": "",
            "blockers": [],
            "target_date": "2026-07-16",
        }
        with tempfile.TemporaryDirectory() as tmp:
            heartbeat = Path(tmp) / "detector-heartbeat.json"
            heartbeat.write_text(
                json.dumps(
                    {
                        "detector_instance_id": "old-instance",
                        "parent_pid": stage930.os.getpid(),
                        "ready": True,
                        "stopped": False,
                        "target_date": "2026-07-16",
                        "send_order_api_called_count": 0,
                        "cancel_order_api_called_count": 0,
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(stage930, "STAGE941_HEARTBEAT_PATH", heartbeat),
                patch.object(
                    stage930,
                    "_managed_tick_stream_status",
                    return_value={"refresh_status": "tick_stream_ready"},
                ),
            ):
                result = stage930._persistent_detector_fast_lane_status(
                    args,
                    "2026-07-16",
                    {"command_log": Path(tmp) / "commands.log"},
                )

        self.assertEqual(
            "persistent_detector_unready_fail_closed",
            result["fast_lane_status"],
        )
        self.assertIn(
            "persistent_detector_heartbeat_instance_mismatch",
            result["blockers"],
        )

    def test_persistent_detector_rejects_alive_process_with_stale_heartbeat(self) -> None:
        args = self.args()
        args.detector_mode = "persistent"
        process = _TickStreamProcess(401, None)
        args._detector_supervisor = {
            "enabled": 1,
            "process": process,
            "instance_id": "instance-a",
            "restart_count": 0,
            "max_restarts": 1,
            "next_restart_monotonic": 0.0,
            "last_exit_code": None,
            "last_start_error": "",
            "blockers": [],
            "target_date": "2026-07-16",
        }
        with tempfile.TemporaryDirectory() as tmp:
            heartbeat = Path(tmp) / "detector-heartbeat.json"
            heartbeat_payload = {
                "model_tag": "stage941_official_live_c9_detector_v1",
                "detector_instance_id": "instance-a",
                "owner_pid": 401,
                "parent_pid": stage930.os.getpid(),
                "generated_epoch_ns": 1,
                "ready": True,
                "stopped": False,
                "target_date": "2026-07-16",
                "consumer_id": "stage941",
                "spool_path": str(stage930.STAGE941_SPOOL_PATH.resolve()),
                "send_order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
            }
            heartbeat.write_text(json.dumps(heartbeat_payload), encoding="utf-8")
            with (
                patch.object(stage930, "STAGE941_HEARTBEAT_PATH", heartbeat),
                patch.object(
                    stage930,
                    "_managed_tick_stream_status",
                    return_value={"refresh_status": "tick_stream_ready"},
                ),
            ):
                result = stage930._persistent_detector_fast_lane_status(
                    args,
                    "2026-07-16",
                    {"command_log": Path(tmp) / "commands.log"},
                )
                heartbeat_payload["generated_epoch_ns"] = (
                    stage930.time.time_ns() + 10_000_000_000
                )
                heartbeat.write_text(
                    json.dumps(heartbeat_payload),
                    encoding="utf-8",
                )
                future = stage930._persistent_detector_fast_lane_status(
                    args,
                    "2026-07-16",
                    {"command_log": Path(tmp) / "commands.log"},
                )
                heartbeat_payload["generated_epoch_ns"] = stage930.time.time_ns()
                heartbeat.write_text(
                    json.dumps(heartbeat_payload),
                    encoding="utf-8",
                )
                ready = stage930._persistent_detector_fast_lane_status(
                    args,
                    "2026-07-16",
                    {"command_log": Path(tmp) / "commands.log"},
                )
                heartbeat_payload["send_order_api_called_count"] = "0"
                heartbeat.write_text(
                    json.dumps(heartbeat_payload),
                    encoding="utf-8",
                )
                malformed_count = stage930._persistent_detector_fast_lane_status(
                    args,
                    "2026-07-16",
                    {"command_log": Path(tmp) / "commands.log"},
                )

        self.assertEqual(
            "persistent_detector_unready_fail_closed",
            result["fast_lane_status"],
        )
        self.assertIn(
            "persistent_detector_heartbeat_stale",
            result["blockers"],
        )
        self.assertIn(
            "persistent_detector_heartbeat_from_future",
            future["blockers"],
        )
        self.assertEqual(
            "persistent_detector_ready_no_submit",
            ready["fast_lane_status"],
        )
        self.assertEqual([], ready["blockers"])
        self.assertIn(
            "persistent_detector_order_api_count_invalid",
            malformed_count["blockers"],
        )

    def test_dead_tick_stream_cannot_reuse_a_fresh_old_heartbeat(self) -> None:
        dead = _TickStreamProcess(303, 9)
        supervisor = {
            "enabled": 1,
            "process": dead,
            "restart_count": 3,
            "max_restarts": 3,
            "last_exit_code": 9,
            "last_start_error": "",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat = root / "heartbeat.json"
            heartbeat.write_text(
                '{"generated_at":"%s","transport_ready":true,"stream_ready":true,"pid":303}'
                % stage930.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                encoding="utf-8",
            )
            with (
                patch.object(stage930, "TICK_STREAM_HEARTBEAT_PATH", heartbeat),
                patch.object(stage930, "TICK_STREAM_MANIFEST_PATH", root / "manifest.json"),
                patch.object(stage930, "READONLY_TICKS_PATH", root / "ticks.csv"),
            ):
                result = stage930._tick_stream_status(["JM609.DCE"], supervisor=supervisor)

        self.assertEqual(result["stream_ready"], 0)
        self.assertEqual(result["refresh_status"], "tick_stream_not_ready_fail_closed")
        self.assertEqual(result["tick_stream_supervisor"]["process_alive"], 0)

    def test_supervisor_revoke_between_h1_h2_invalidates_snapshot_commit(self) -> None:
        """A supervisor write must never look like the child's old commit."""

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tick_path = root / "ticks.csv"
            heartbeat_path = root / "heartbeat.json"
            stage608._publish_tick_snapshot_commit(
                tick_path=tick_path,
                heartbeat_path=heartbeat_path,
                tick_rows=[
                    {
                        "feed_session_id": "feed-a",
                        "stream_sequence": 1,
                        "symbol_stream_sequence": 1,
                        "received_at": datetime.now().isoformat(),
                        "vt_symbol": "JM609.DCE",
                        "last_price": 1245.0,
                    }
                ],
                heartbeat={
                    "feed_session_id": "feed-a",
                    "stream_sequence": 1,
                    "buffered_tick_count": 1,
                    "transport_ready": True,
                    "stream_ready": True,
                },
            )
            read_json = stage904._read_json
            heartbeat_reads = 0

            def revoke_after_h1(path: Path) -> dict:
                nonlocal heartbeat_reads
                payload = read_json(path)
                if Path(path) == heartbeat_path:
                    heartbeat_reads += 1
                    if heartbeat_reads == 1:
                        stage930._revoke_tick_stream_heartbeat(
                            "test_revoke_between_h1_h2"
                        )
                return payload

            with (
                patch.object(stage930, "TICK_STREAM_HEARTBEAT_PATH", heartbeat_path),
                patch.object(stage904, "_read_json", side_effect=revoke_after_h1),
            ):
                frame, observed_heartbeat, error = (
                    stage904._read_committed_tick_snapshot(
                        tick_path,
                        heartbeat_path,
                        attempts=1,
                        retry_seconds=0,
                    )
                )
            persisted = json.loads(heartbeat_path.read_text(encoding="utf-8"))

        self.assertTrue(frame.empty)
        self.assertIn("tick_snapshot_commit_missing", error)
        self.assertEqual(heartbeat_reads, 2)
        self.assertTrue(observed_heartbeat["tick_snapshot_commit_invalidated"])
        self.assertTrue(persisted["tick_snapshot_commit_invalidated"])
        self.assertNotIn("tick_snapshot_commit", persisted)
        self.assertNotIn("tick_snapshot_generation_uuid", persisted)
        self.assertEqual(
            persisted["supervisor_revocation_reason"],
            "test_revoke_between_h1_h2",
        )

    def test_broker_and_durable_positions_extend_watch_until_confirmed_flat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = root / "readonly_summary.json"
            positions = root / "readonly_positions.csv"
            state = root / (
                f"{stage930.STAGE904_PREFIX}_state_20260713_{stage930.STAGE904_MODEL_TAG}.json"
            )
            positions.write_text("vt_symbol,volume\nRB2610.SHFE,2\n", encoding="utf-8")
            state.write_text(
                '{"states":{"root":{"phase":"retry_open","vt_symbol":"JM609.DCE"}}}',
                encoding="utf-8",
            )

            def write_snapshot(snapshot_state: str, rows: int, *, last_seen: bool = True) -> None:
                summary.write_text(
                    '{"generated_at":"%s","status":"readonly_snapshots_received","broker_snapshot":'
                    '{"position_snapshot_state":"%s","position_query_last_seen":%s,'
                    '"position_query_error_rows":0,"position_query_callback_rows":1,'
                    '"position_rows":%d,"nonzero_position_rows":%d}}'
                    % (
                        stage930.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        snapshot_state,
                        str(last_seen).lower(),
                        rows,
                        rows,
                    ),
                    encoding="utf-8",
                )

            write_snapshot("positions_received", 1)
            retained: set[str] = set()
            with (
                patch.object(stage930, "OUTPUT_DIR", root),
                patch.object(stage930, "READONLY_SUMMARY_PATH", summary),
                patch.object(stage930, "READONLY_POSITIONS_PATH", positions),
                patch.object(stage930, "STAGE901_PENDING_ORDERS_PATH", root / "pending.csv"),
                patch.object(stage930, "OFFICIAL_LIVE_SIGNAL_PLAN_PATH", root / "signal.csv"),
                patch.object(stage930, "OFFICIAL_LIVE_CURRENT_POSITIONS_PATH", root / "official.csv"),
            ):
                first = stage930._watched_symbols([], retained_broker_symbols=retained)
                write_snapshot("position_query_error", 0, last_seen=False)
                incomplete = stage930._watched_symbols([], retained_broker_symbols=retained)
                positions.write_text("vt_symbol,volume\n", encoding="utf-8")
                write_snapshot("confirmed_flat", 0)
                flat = stage930._watched_symbols([], retained_broker_symbols=retained)

        self.assertEqual(set(first), {"RB2610.SHFE", "JM609.DCE"})
        self.assertEqual(set(incomplete), {"RB2610.SHFE", "JM609.DCE"})
        self.assertEqual(flat, ["JM609.DCE"])
        self.assertEqual(retained, set())

    def test_latest_summary_report_and_heartbeat_use_atomic_writers(self) -> None:
        summary = {"daemon_status": "daemon_running", "target_date": "2026-07-13", "cycle_count": 1}
        paths = {"summary_json": Path("run.json"), "report_md": Path("run.md")}
        with (
            patch.object(stage930, "_build_report", return_value="report"),
            patch.object(stage930, "_atomic_write_text") as write_text,
            patch.object(stage930, "_atomic_write_json") as write_json,
        ):
            stage930._write_outputs(paths, summary)

        written_text_paths = [call.args[0] for call in write_text.call_args_list]
        self.assertIn(paths["summary_json"], written_text_paths)
        self.assertIn(stage930.LATEST_SUMMARY_PATH, written_text_paths)
        self.assertIn(stage930.LATEST_REPORT_PATH, written_text_paths)
        write_json.assert_called_once()
        self.assertEqual(write_json.call_args.args[0], stage930.LATEST_HEARTBEAT_PATH)

    def test_launchd_session_jobs_keep_direct_python_owner(self) -> None:
        launchd = PORTFOLIO_DIR / "launchd"
        for name in (
            "local.qmt-roll.official-live.15w.c9-night-session.plist",
            "local.qmt-roll.official-live.15w.c9-day-session.plist",
        ):
            with (launchd / name).open("rb") as handle:
                payload = plistlib.load(handle)
                program_arguments = payload["ProgramArguments"]
            self.assertTrue(
                program_arguments[0].endswith(
                    "/.py311/bin/python"
                )
            )
            self.assertTrue(
                program_arguments[1].endswith(
                    "run_qmt_roll_stage930_official_live_c9_session_daemon.py"
                )
            )
            self.assertIs(payload.get("AbandonProcessGroup"), False)
            self.assertEqual(15, payload.get("ExitTimeOut"))
            self.assertEqual("Interactive", payload.get("ProcessType"))

    def test_supervisor_forwards_term_waits_and_never_restarts(self) -> None:
        supervisor = PORTFOLIO_DIR / "run_qmt_roll_stage930_official_live_c9_session_supervisor.sh"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_daemon = root / "fake_daemon.py"
            starts = root / "starts.log"
            terms = root / "terms.log"
            fake_daemon.write_text(
                "\n".join(
                    [
                        "import os, signal, sys, time",
                        "from pathlib import Path",
                        "starts = Path(os.environ['FAKE_STAGE930_STARTS'])",
                        "terms = Path(os.environ['FAKE_STAGE930_TERMS'])",
                        "with starts.open('a', encoding='utf-8') as handle: handle.write('start\\n')",
                        "def stop(signum, frame):",
                        "    with terms.open('a', encoding='utf-8') as handle: handle.write(str(signum) + '\\n')",
                        "    raise SystemExit(128 + signum)",
                        "signal.signal(signal.SIGTERM, stop)",
                        "signal.signal(signal.SIGINT, stop)",
                        "while True: time.sleep(0.1)",
                    ]
                ),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env.update(
                {
                    "STAGE930_PROJECT_DIR": str(root),
                    "STAGE930_REPO_ROOT": str(root),
                    "STAGE930_PYTHON_PATH": sys.executable,
                    "STAGE930_DAEMON_SCRIPT": str(fake_daemon),
                    "STAGE930_LOG_DIR": str(root / "logs"),
                    "STAGE930_SUPERVISOR_MAX_RESTARTS": "5",
                    "STAGE930_SUPERVISOR_RESTART_DELAY_SECONDS": "0.05",
                    "FAKE_STAGE930_STARTS": str(starts),
                    "FAKE_STAGE930_TERMS": str(terms),
                }
            )
            process = subprocess.Popen(
                ["bash", str(supervisor)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            if not self.wait_for_path(starts):
                process.send_signal(signal.SIGTERM)
                stdout, _ = process.communicate(timeout=8)
                self.fail(f"supervisor daemon never started: {stdout}")
            process.send_signal(signal.SIGTERM)
            stdout, _ = process.communicate(timeout=8)
            time.sleep(0.2)

            self.assertEqual(process.returncode, 128 + signal.SIGTERM, stdout)
            self.assertTrue(terms.exists(), stdout)
            self.assertEqual(starts.read_text(encoding="utf-8").splitlines(), ["start"], stdout)
            self.assertIn("no restart", stdout)


class Stage929OwnershipTest(unittest.TestCase):
    @staticmethod
    def args(phase: str) -> SimpleNamespace:
        return SimpleNamespace(
            phase=phase,
            readonly_refresh_mode="auto",
            shadow_refresh_mode="auto",
            readonly_wait_seconds=30,
            max_snapshot_age_seconds=300,
            post_close_reconcile_snapshot_age_seconds=7200,
        )

    def test_evening_report_never_owns_intraday_tick_or_execution_outputs(self) -> None:
        command = stage929._stage903_command(self.args("evening-report"), "2026-07-13")
        self.assertIn("--intraday-tick-refresh-mode", command)
        self.assertEqual(command[command.index("--intraday-tick-refresh-mode") + 1], "skip")
        self.assertIn("--intraday-execution-mode", command)
        self.assertEqual(command[command.index("--intraday-execution-mode") + 1], "external")

    def test_post_close_keeps_independent_non_session_behavior(self) -> None:
        command = stage929._stage903_command(self.args("post-close"), "2026-07-13")
        self.assertNotIn("--intraday-tick-refresh-mode", command)
        self.assertNotIn("--intraday-execution-mode", command)


if __name__ == "__main__":
    unittest.main()
