from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import run_qmt_roll_stage930_official_live_c9_session_daemon as stage930  # noqa: E402


class _Process:
    def __init__(self, pid: int = 401) -> None:
        self.pid = pid

    def poll(self) -> None:
        return None


class Stage930PersistentAuthorizationTest(unittest.TestCase):
    def test_initial_open_authorization_is_limited_to_exchange_open_windows(
        self,
    ) -> None:
        def stamp(value: str) -> int:
            local = datetime.fromisoformat(value).astimezone()
            return int(local.timestamp() * 1_000_000_000)

        cases = (
            ("2026-07-21T08:59:59+08:00", False, ""),
            ("2026-07-21T09:00:00+08:00", True, "day_open"),
            ("2026-07-21T09:04:59.999999+08:00", True, "day_open"),
            ("2026-07-21T09:05:00+08:00", False, ""),
            ("2026-07-21T20:59:59+08:00", False, ""),
            ("2026-07-21T21:00:00+08:00", True, "night_open"),
            ("2026-07-21T21:04:59.999999+08:00", True, "night_open"),
            ("2026-07-21T21:05:00+08:00", False, ""),
            ("2026-07-19T21:00:00+08:00", False, ""),
        )
        for value, expected_allowed, expected_label in cases:
            with self.subTest(value=value):
                allowed, expires_epoch_ns, label = (
                    stage930._initial_open_authorization_window(stamp(value))
                )
                self.assertEqual(expected_allowed, allowed)
                if expected_allowed:
                    self.assertEqual(expected_label, label)
                    self.assertGreater(expires_epoch_ns, stamp(value))
                else:
                    self.assertEqual(0, expires_epoch_ns)

    def args(self, root: str) -> SimpleNamespace:
        return SimpleNamespace(
            mode="live-real",
            submit_mode="live-real",
            stage179_execution_mode="warm",
            runtime_profile="simnow",
            stage179_runtime_root=root,
            target_date="2026-07-21",
            detector_mode="persistent",
            detector_poll_seconds=0.05,
            detector_batch_size=1024,
            detector_max_restarts=3,
            detector_restart_backoff_seconds=2.0,
            max_snapshot_age_seconds=60,
            fast_tick_age_seconds=3.0,
            vt_symbol=["JM609.DCE"],
        )

    @staticmethod
    def candidate(
        *,
        source: str,
        role: str,
        kind: str,
        suffix: str,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            intent_id=f"intent-{suffix}",
            payload_sha256=hashlib.sha256(suffix.encode("utf-8")).hexdigest(),
            intent_kind=kind,
            intent_role=role,
            trace_id=f"trace-{suffix}",
            target_date="2026-07-21",
            source=source,
            vt_symbol="JM609.DCE",
            state_generation=f"epoch-{suffix}:0",
            position_epoch_id=f"epoch-{suffix}",
            root_position_id=f"root-{suffix}",
            position_cycle_id=f"cycle-{suffix}",
            spool_sequence=1,
            state_revision=0,
            deadline_epoch_ns=time.time_ns() + 20_000_000_000,
            deadline_monotonic_ns=time.monotonic_ns() + 20_000_000_000,
            clock_domain_id="test-clock",
        )

    @staticmethod
    def snapshot(candidate: SimpleNamespace) -> SimpleNamespace:
        return SimpleNamespace(
            candidate=candidate,
            inflight_count=0,
            ready_close_count=int(candidate.intent_kind == "close"),
            ready_open_count=int(candidate.intent_kind == "open"),
            snapshot_digest="1" * 64,
            cursor_digest="2" * 64,
        )

    @staticmethod
    def stage902(now: str) -> dict[str, object]:
        return {
            "model_tag": "stage902_official_live_phase_d_readiness_gate_v1",
            "generated_at": now,
            "target_date": "2026-07-21",
            "execution_profile": "c9-15w",
            "official_live_version": stage930.OFFICIAL_LIVE_VERSION,
            "capital": 150000,
            "capital_label": "15w",
            "order_api_called_count": 0,
            "allow_reduce_close": 1,
            "blocking_failure_count_for_reduce_close": 0,
            "allow_new_open": 1,
            "blocking_failure_count": 0,
            "ready_for_phase_d_real": 1,
        }

    @staticmethod
    def stage927(now: str) -> dict[str, object]:
        scope_inputs = {
            "schema_version": stage930.STAGE927_SCOPE_CAPABILITY_SCHEMA_VERSION,
        }
        scope_capabilities = {
            name: {
                "permit_field": permit_field,
                "permitted": 1,
            }
            for name, permit_field in stage930._STAGE927_SCOPE_PERMIT_FIELDS.items()
        }
        scope_evidence_digest = stage930._canonical_json_digest(
            {
                "scope_evidence_inputs": scope_inputs,
                "scope_capabilities": scope_capabilities,
            }
        )
        return {
            "model_tag": "stage927_official_live_real_submit_arming_gate_v1",
            "generated_at": now,
            "target_date": "2026-07-21",
            "execution_profile": "c9-15w",
            "official_live_version": stage930.OFFICIAL_LIVE_VERSION,
            "capital": 150000,
            "capital_label": "15w",
            "order_api_called_count": 0,
            "env_real_submit_enabled": 1,
            "confirm_live_real_ok": 1,
            "scope_capability_schema_version": (
                stage930.STAGE927_SCOPE_CAPABILITY_SCHEMA_VERSION
            ),
            "scope_evidence_inputs": scope_inputs,
            "scope_capabilities": scope_capabilities,
            "scope_evidence_digest": scope_evidence_digest,
            "reduce_close_submit_permitted": 1,
            "retry_open_submit_permitted": 1,
            "initial_open_submit_permitted": 1,
        }

    def test_detector_and_executor_share_exact_runtime_spool(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args = self.args(directory)
            runtime = stage930._stage179_runtime(args)
            process = _Process()
            with (
                patch.object(stage930, "_revoke_detector_heartbeat"),
                patch.object(stage930, "_managed_popen", return_value=process) as popen,
            ):
                returned = stage930._start_detector(
                    args,
                    {"command_log": Path(directory) / "commands.log"},
                    target_date="2026-07-21",
                    instance_id="detector-1",
                )

            self.assertIs(returned, process)
            command = popen.call_args.args[0]
            spool_index = command.index("--spool-path") + 1
            self.assertEqual(str(runtime.spool_path), command[spool_index])

    def test_three_exact_lanes_publish_and_wake_same_warm_executor(self) -> None:
        cases = (
            (
                "stage904_c9_intraday_close",
                "c9_initial_stop_close",
                "close",
                "close",
                "persistent_intraday_fast",
                "reduce_close_only",
            ),
            (
                "stage904_c9_intraday_retry_open",
                "c9_retry_open_once",
                "open",
                "retry",
                "persistent_intraday_fast",
                "retry_open_only",
            ),
            (
                "stage901_pending_order",
                "c9_initial_open",
                "open",
                "initial",
                "session_initial_open",
                "initial_open_only",
            ),
        )
        for source, role, kind, suffix, expected_lane, expected_scope in cases:
            with self.subTest(expected_lane=expected_lane, scope=expected_scope):
                with tempfile.TemporaryDirectory() as directory:
                    args = self.args(directory)
                    runtime = stage930._stage179_runtime(args)
                    stage930._STAGE931_SERVICE_RUNTIME = runtime
                    runtime.spool_path.parent.mkdir(parents=True, exist_ok=True)
                    runtime.spool_path.touch()
                    process = _Process()
                    args._detector_supervisor = {
                        "enabled": 1,
                        "process": process,
                        "instance_id": "detector-1",
                        "restart_count": 0,
                        "max_restarts": 3,
                        "next_restart_monotonic": 0.0,
                        "last_exit_code": None,
                        "last_start_error": "",
                        "blockers": [],
                        "target_date": "2026-07-21",
                    }
                    heartbeat_path = Path(directory) / "detector-heartbeat.json"
                    heartbeat = {
                        "model_tag": "stage941_official_live_c9_detector_v1",
                        "detector_instance_id": "detector-1",
                        "owner_pid": process.pid,
                        "parent_pid": os.getpid(),
                        "generated_epoch_ns": time.time_ns(),
                        "ready": True,
                        "stopped": False,
                        "target_date": "2026-07-21",
                        "consumer_id": "stage941",
                        "spool_path": str(runtime.spool_path.resolve()),
                        "ready_count": 1,
                        "blocked_count": 0,
                        "expired_count": 0,
                        "send_order_api_called_count": 0,
                        "cancel_order_api_called_count": 0,
                    }
                    heartbeat_path.write_text(json.dumps(heartbeat), encoding="utf-8")
                    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    evidence = {
                        str(stage930._stage902_summary_path("2026-07-21")): self.stage902(now_text),
                        str(stage930._stage927_summary_path("2026-07-21")): self.stage927(now_text),
                    }
                    candidate = self.candidate(
                        source=source,
                        role=role,
                        kind=kind,
                        suffix=suffix,
                    )
                    snapshot = self.snapshot(candidate)
                    tick_stream = {
                        "refresh_status": "tick_stream_ready",
                        "transport_ready": 1,
                        "stream_ready": 1,
                        "all_symbols_ready": 1,
                        "heartbeat_pid_matches_process": 1,
                        "symbol_tick_freshness": {
                            "blocked_new_risk_symbols": [],
                        },
                        "summary": {
                            "generated_epoch_ns": time.time_ns(),
                            "symbol_tick_watermarks": {
                                "JM609.DCE": {
                                    "ingress_epoch_ns": time.time_ns(),
                                },
                            },
                        },
                    }
                    readiness = {
                        "status": "ready",
                        "service_generation": "service-1",
                        "connection_generation": "connection-1",
                        "runtime_profile": "simnow",
                        "order_scope": "test",
                        "expires_epoch_ns": time.time_ns() + 30_000_000_000,
                    }
                    service_status = {
                        "submit_status": "warm_executor_ready",
                        "readiness": readiness,
                        "summary": {
                            "send_order_api_called_count": 0,
                            "cancel_order_api_called_count": 0,
                            "order_api_called_count": 0,
                        },
                    }

                    def read_json(path: Path) -> dict[str, object]:
                        if Path(path) == heartbeat_path:
                            return heartbeat
                        return evidence.get(str(path), {})

                    try:
                        with (
                            patch.object(stage930, "STAGE941_HEARTBEAT_PATH", heartbeat_path),
                            patch.object(stage930, "_read_json", side_effect=read_json),
                            patch.object(stage930, "_spool_authorization_snapshot", return_value=snapshot),
                            patch.object(stage930, "authorization_snapshots_match", return_value=True),
                            patch.object(stage930, "_managed_tick_stream_status", return_value=tick_stream),
                            patch.object(stage930, "_status_stage931_service", return_value=service_status),
                            patch.object(stage930, "_wake_stage931_service", return_value=True) as wake,
                            patch.object(
                                stage930,
                                "_initial_open_authorization_window",
                                return_value=(
                                    True,
                                    time.time_ns() + 60_000_000_000,
                                    "test_open",
                                ),
                            ),
                        ):
                            result = stage930._persistent_detector_fast_lane_status(
                                args,
                                "2026-07-21",
                                {"command_log": Path(directory) / "commands.log"},
                            )
                    finally:
                        stage930._STAGE931_SERVICE_RUNTIME = None

                    authorization = result["stage931"]["submit_authorization"]
                    self.assertEqual(1, authorization["authorized"], result)
                    self.assertEqual(expected_lane, authorization["authorization_lane"])
                    self.assertEqual(expected_scope, authorization["intent_scope"])
                    self.assertEqual("persistent_detector_submit_authorized", result["fast_lane_status"])
                    wake.assert_called_once()

    def test_busy_executor_lock_preserves_existing_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args = self.args(directory)
            runtime = stage930._stage179_runtime(args)
            stage930._STAGE931_SERVICE_RUNTIME = runtime
            try:
                from qmt_roll_official_live_authorization_lock import (
                    SubmitAuthorizationLockBusyError,
                )

                with patch.object(
                    stage930,
                    "exclusive_submit_authorization_lock",
                    side_effect=SubmitAuthorizationLockBusyError(
                        "stage179_submit_authorization_lock_busy"
                    ),
                ):
                    result = stage930._revoke_stage931_submit_authorization(
                        args,
                        "test-refresh",
                    )
            finally:
                stage930._STAGE931_SERVICE_RUNTIME = None

        self.assertEqual(0, result["revoked"])
        self.assertEqual(1, result["preserved"])


if __name__ == "__main__":
    unittest.main()
