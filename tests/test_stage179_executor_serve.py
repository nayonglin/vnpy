from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import contextmanager
import json
import os
import subprocess
import time
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

from qmt_roll_official_live_execution_service import (  # noqa: E402
    ExecutionResult,
    ExecutorAlreadyRunningError,
    ExecutorServicePaths,
    publish_readiness,
    revoke_readiness,
    serve_executor,
    singleton_executor_lock,
)
from qmt_roll_official_live_runtime_profile import (  # noqa: E402
    ExecutionRuntimeProfile,
    OrderScope,
    resolve_runtime_profile,
)
from qmt_roll_official_live_submit_authorization import (  # noqa: E402
    publish_submit_authorization,
    revoke_submit_authorization,
    submit_authorization_path,
)
import run_qmt_roll_stage931_official_live_ctp_submit_adapter as stage931  # noqa: E402
import qmt_roll_official_live_execution_service as execution_service  # noqa: E402


class FakeClock:
    def __init__(self) -> None:
        self.epoch_ns = 1_000_000_000_000
        self.monotonic_ns = 10_000_000_000

    def time_ns(self) -> int:
        return self.epoch_ns

    def monotonic(self) -> float:
        return self.monotonic_ns / 1_000_000_000

    def advance(self, seconds: float) -> None:
        delta = int(seconds * 1_000_000_000)
        self.epoch_ns += delta
        self.monotonic_ns += delta


class FakeSpool:
    def __init__(self, intent_ids: list[str], clock: FakeClock) -> None:
        self.clock = clock
        self.ready = [
            SimpleNamespace(
                intent=SimpleNamespace(
                    intent_id=intent_id,
                    payload_sha256=(intent_id[0] if intent_id else "a") * 64,
                    target_date="2026-07-18",
                    deadline_epoch_ns=clock.epoch_ns + 25_000_000_000,
                    deadline_monotonic_ns=clock.monotonic_ns + 25_000_000_000,
                    clock_domain_id="fake-boot",
                    intent_kind="open",
                ),
                lease_token=f"lease-{intent_id}",
            )
            for intent_id in intent_ids
        ]
        self.transitions: list[tuple[str, str]] = []
        self.last_lease_kwargs: dict[str, Any] = {}
        self.recovery_calls = 0

    def recover_expired(self, **_: Any) -> list[str]:
        self.recovery_calls += 1
        return []

    def expire_due(self, **_: Any) -> None:
        return None

    def lease_next(self, **kwargs: Any) -> Any:
        self.last_lease_kwargs = dict(kwargs)
        return self.ready.pop(0) if self.ready else None

    def mark_sending(self, lease: Any, **_: Any) -> None:
        self.transitions.append((lease.intent.intent_id, "sending"))

    def mark_result(self, lease: Any, result: ExecutionResult, **_: Any) -> None:
        self.transitions.append((lease.intent.intent_id, result.disposition))


class DelayedFakeSpool(FakeSpool):
    def __init__(self, intent_ids: list[str], clock: FakeClock) -> None:
        super().__init__(intent_ids, clock)
        self.lease_calls = 0

    def lease_next(self, **kwargs: Any) -> Any:
        self.lease_calls += 1
        if self.lease_calls == 1:
            return None
        return super().lease_next(**kwargs)


class SlowLeaseFakeSpool(FakeSpool):
    def lease_next(self, **kwargs: Any) -> Any:
        self.clock.advance(0.6)
        return super().lease_next(**kwargs)


class FakeWarmSession:
    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.connect_calls = 0
        self.fresh_bundle_calls = 0
        self.api_slot_calls = 0
        self.send_calls = 0
        self.close_calls = 0
        self.transport_failures = 0
        self.events: list[str] = []
        self.connection_generation = ""
        self._lease: Any = None
        self.pre_lease_blocker_values: list[str] = []
        self.pre_lease_authorized_values: dict[str, str] | None = None
        self.pre_lease_calls = 0

    def connect(self) -> None:
        self.connect_calls += 1
        self.connection_generation = f"connection-{self.connect_calls}"
        self._lease = stage931.TdReadinessLease(
            service_generation="service-1",
            connection_generation=self.connection_generation,
            runtime_profile="simnow",
            official_version="official-test",
            capital=200_000.0,
            issued_epoch_ns=self.clock.epoch_ns,
            expires_epoch_ns=self.clock.epoch_ns + 3_000_000_000,
            last_complete_startup_bundle_epoch_ns=self.clock.epoch_ns,
        )

    def readiness_lease(self, *, now_epoch_ns: int) -> Any:
        if self._lease is None or now_epoch_ns >= self._lease.expires_epoch_ns:
            raise RuntimeError("readiness_lease_expired")
        return self._lease

    def transport_blockers(self) -> list[str]:
        return (
            ["stage179_ctp_transport_generation_invalidated"]
            if self.transport_failures > 0
            else []
        )

    def pre_lease_blockers(self) -> list[str]:
        self.pre_lease_calls += 1
        return list(self.pre_lease_blocker_values)

    def pre_lease_authorized_intents(self) -> dict[str, str] | None:
        return self.pre_lease_authorized_values

    def reconnect(self) -> None:
        self.transport_failures = max(0, self.transport_failures - 1)
        self.close()
        self.connect()

    def execute_spool_lease(
        self,
        *,
        lease: Any,
        hard_deadline_monotonic: float,
        api_slot_durable: Any = None,
    ) -> ExecutionResult:
        self.fresh_bundle_calls += 1
        if self.clock.monotonic() >= hard_deadline_monotonic:
            return ExecutionResult.blocked(
                lease.intent.intent_id,
                "stage179_execution_deadline_exceeded:fresh_bundle",
            )
        self.api_slot_calls += 1
        self.events.append("api_slot_durable")
        if api_slot_durable is not None and not api_slot_durable(
            f"slot-{lease.intent.intent_id}"
        ):
            return ExecutionResult(
                intent_id=lease.intent.intent_id,
                disposition="side_effect_unknown",
                ledger_fingerprint=f"fp-{lease.intent.intent_id}",
                api_slot_batch_id=f"slot-{lease.intent.intent_id}",
                blockers=("stage179_spool_sending_cas_lost_after_api_slot",),
                send_order_call_count=0,
                cancel_order_call_count=0,
            )
        self.send_calls += 1
        self.events.append("broker_send")
        return ExecutionResult(
            intent_id=lease.intent.intent_id,
            disposition="sent",
            ledger_fingerprint=f"fp-{lease.intent.intent_id}",
            api_slot_batch_id=f"slot-{lease.intent.intent_id}",
            blockers=(),
            send_order_call_count=1,
            cancel_order_call_count=0,
        )

    def close(self) -> None:
        self.close_calls += 1
        self._lease = None


class Stage179ExecutorServeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        root = Path(self.tempdir.name)
        self.paths = ExecutorServicePaths.for_spool(
            spool_path=root / "intent-spool.sqlite3",
            ledger_path=root / "ledger.ndjson",
        )
        self.clock = FakeClock()
        self.runtime = resolve_runtime_profile(
            profile=ExecutionRuntimeProfile.SIMNOW,
            order_scope=OrderScope.TEST,
            repo_root=ROOT,
            output_root=root / "runtime",
        )

    def test_serve_reuses_one_ctp_connection_for_two_intents_but_runs_two_fresh_bundles(self) -> None:
        spool = FakeSpool(["intent-1", "intent-2"], self.clock)
        session = FakeWarmSession(self.clock)

        rc = serve_executor(
            paths=self.paths,
            spool=spool,
            backend_factory=lambda: session,
            runtime=self.runtime,
            stop_requested=lambda: not spool.ready,
            epoch_ns=self.clock.time_ns,
            monotonic=self.clock.monotonic,
            sleeper=lambda _: None,
        )

        self.assertEqual(0, rc)
        self.assertEqual(1, session.connect_calls)
        self.assertEqual(2, session.fresh_bundle_calls)
        self.assertEqual(2, session.api_slot_calls)
        self.assertEqual(2, session.send_calls)
        self.assertGreaterEqual(spool.recovery_calls, 2)
        self.assertEqual(1, session.close_calls)
        self.assertEqual(
            [
                ("intent-1", "sending"),
                ("intent-1", "sent"),
                ("intent-2", "sending"),
                ("intent-2", "sent"),
            ],
            spool.transitions,
        )

    def test_cycle_authorization_blocks_before_spool_lease(self) -> None:
        spool = FakeSpool(["intent-1"], self.clock)
        session = FakeWarmSession(self.clock)
        session.pre_lease_blocker_values = [
            "stage179_submit_authorization_missing"
        ]

        serve_executor(
            paths=self.paths,
            spool=spool,
            backend_factory=lambda: session,
            runtime=self.runtime,
            stop_requested=lambda: session.pre_lease_calls >= 1,
            epoch_ns=self.clock.time_ns,
            monotonic=self.clock.monotonic,
            sleeper=lambda _: None,
        )

        self.assertEqual(1, session.pre_lease_calls)
        self.assertEqual(["intent-1"], [item.intent.intent_id for item in spool.ready])
        self.assertEqual([], spool.transitions)
        self.assertEqual(0, session.send_calls)

    def test_cycle_authorization_allow_list_is_passed_into_atomic_lease(self) -> None:
        spool = FakeSpool(["approved"], self.clock)
        session = FakeWarmSession(self.clock)
        session.pre_lease_authorized_values = {"approved": "a" * 64}

        serve_executor(
            paths=self.paths,
            spool=spool,
            backend_factory=lambda: session,
            runtime=self.runtime,
            stop_requested=lambda: not spool.ready,
            epoch_ns=self.clock.time_ns,
            monotonic=self.clock.monotonic,
            sleeper=lambda _: None,
        )

        self.assertEqual(
            {"approved": "a" * 64},
            spool.last_lease_kwargs["authorized_intents"],
        )

    def test_multi_child_revalidates_authorization_before_every_physical_send(self) -> None:
        args = SimpleNamespace(target_date="2026-07-18")
        session = stage931._build_stage179_warm_ctp_session(
            args,
            self.runtime,
            self.paths,
        )
        state = next(
            cell.cell_contents
            for cell in session._send_order.__closure__ or ()
            if isinstance(cell.cell_contents, dict)
            and "intent_contexts" in cell.cell_contents
        )
        state["connection_generation"] = "connection-1"
        authorization_path = submit_authorization_path(self.runtime.output_root)
        authorization_now_ns = time.time_ns()
        authorization_expires_ns = authorization_now_ns + 30_000_000_000
        publish_submit_authorization(
            path=authorization_path,
            target_date="2026-07-18",
            execution_profile="c9-15w-historical",
            runtime_profile="simnow",
            order_scope="test",
            service_generation=session.service_generation,
            connection_generation="connection-1",
            cycle_id="cycle-1",
            intent_scope="all",
            authorized_intents=[
                {
                    "intent_id": "intent-1",
                    "payload_sha256": "a" * 64,
                    "intent_kind": "close",
                }
            ],
            issued_epoch_ns=authorization_now_ns,
            expires_epoch_ns=authorization_expires_ns,
            controller_evidence={
                "target_date": "2026-07-18",
                "controller_status": "phase_d_controller_live_real_ready_no_submit_step",
                "stage905_executor_status": "executor_dry_run_ready",
                "stage905_blocked_count": 0,
                "stage905_ready_count": 1,
                "expires_epoch_ns": authorization_expires_ns,
            },
            stage927_evidence={
                "real_submit_permitted": 1,
                "expires_epoch_ns": authorization_expires_ns,
            },
            broker_gate_evidence={
                "status": "ready",
                "service_generation": session.service_generation,
                "connection_generation": "connection-1",
                "expires_epoch_ns": authorization_expires_ns,
            },
            tick_watermark_evidence={
                "all_symbols_ready": 1,
                "expires_epoch_ns": authorization_expires_ns,
            },
        )

        class FakeMainEngine:
            def __init__(self) -> None:
                self.calls = 0

            def send_order(self, _request: Any, _gateway: str) -> str:
                self.calls += 1
                revoke_submit_authorization(
                    authorization_path,
                    reason="test_mid_batch_revoke",
                    revoked_epoch_ns=time.time_ns(),
                )
                return f"CTP.order-{self.calls}"

        engine = FakeMainEngine()
        state["main_engine"] = engine
        def request() -> SimpleNamespace:
            return SimpleNamespace(
                offset=SimpleNamespace(value="close"),
                volume=1.0,
            )
        state["intent_contexts"]["intent-1"] = {
            "requests": [request(), request()],
            "fingerprint": "fingerprint-1",
        }
        lease = SimpleNamespace(
            intent=SimpleNamespace(
                intent_id="intent-1",
                payload_sha256="a" * 64,
                target_date="2026-07-18",
                intent_kind="close",
                vt_symbol="JM609.DCE",
                lease_owner="service-1",
            ),
            lease_token="lease-1",
        )
        ledger_events: list[dict[str, Any]] = []
        with patch.object(
            stage931,
            "append_execution_ledger_event",
            side_effect=lambda event, **_: ledger_events.append(dict(event)),
        ):
            with self.assertRaises(stage931.BrokerSendBatchError) as raised:
                session._send_order(lease)

        self.assertEqual(1, raised.exception.send_order_call_count)
        self.assertEqual(1, engine.calls)
        blocked = [
            event
            for event in ledger_events
            if event.get("event_type")
            == "submit_authorization_blocked_before_child_send"
        ]
        self.assertEqual(1, len(blocked))
        self.assertEqual(1, blocked[0]["reconciliation_required"])
        self.assertEqual(1, blocked[0]["send_order_call_count"])

    def test_api_slot_is_durable_before_spool_sending_and_broker_call(self) -> None:
        session = FakeWarmSession(self.clock)

        class OrderedSpool(FakeSpool):
            def mark_sending(self, lease: Any, **kwargs: Any) -> None:
                session.events.append("spool_sending")
                super().mark_sending(lease, **kwargs)

        spool = OrderedSpool(["intent-1"], self.clock)
        serve_executor(
            paths=self.paths,
            spool=spool,
            backend_factory=lambda: session,
            runtime=self.runtime,
            stop_requested=lambda: not spool.ready,
            epoch_ns=self.clock.time_ns,
            monotonic=self.clock.monotonic,
            monotonic_ns=lambda: self.clock.monotonic_ns,
            sleeper=lambda _: None,
        )

        self.assertEqual(
            ["api_slot_durable", "spool_sending", "broker_send"],
            session.events,
        )

    def test_spool_sending_cas_loss_after_api_slot_never_calls_broker(self) -> None:
        session = FakeWarmSession(self.clock)

        class LostCasSpool(FakeSpool):
            def mark_sending(self, lease: Any, **_: Any) -> Any:
                return SimpleNamespace(state="leased")

        spool = LostCasSpool(["intent-1"], self.clock)
        serve_executor(
            paths=self.paths,
            spool=spool,
            backend_factory=lambda: session,
            runtime=self.runtime,
            stop_requested=lambda: not spool.ready,
            epoch_ns=self.clock.time_ns,
            monotonic=self.clock.monotonic,
            monotonic_ns=lambda: self.clock.monotonic_ns,
            sleeper=lambda _: None,
        )

        self.assertEqual(1, session.api_slot_calls)
        self.assertEqual(0, session.send_calls)
        self.assertEqual(
            ("intent-1", "side_effect_unknown"),
            spool.transitions[-1],
        )

    def test_real_spool_cas_exception_after_slot_keeps_service_alive_without_send(self) -> None:
        sent: list[str] = []
        session = stage931.CtpExecutionSession.for_callbacks(
            runtime=self.runtime,
            service_generation="service-1",
            official_version="official-test",
            capital=200_000.0,
            readiness_ttl_seconds=30.0,
            connect_startup_bundle=lambda: {"ready": True},
            disconnect_transport=lambda: None,
            fresh_bundle=lambda *_: (),
            reserve_api_slot=lambda *_: "batch-slot-1",
            send_order=lambda *_: sent.append("send") or "CTP.1",
            epoch_ns=self.clock.time_ns,
            monotonic=self.clock.monotonic,
        )

        class CasErrorSpool(FakeSpool):
            def mark_sending(self, lease: Any, **_: Any) -> Any:
                raise execution_service.SpoolTransitionError("lease CAS lost")

            def mark_result(
                self,
                lease: Any,
                result: ExecutionResult,
                **_: Any,
            ) -> None:
                raise execution_service.SpoolTransitionError("state mismatch")

        spool = CasErrorSpool(["intent-1"], self.clock)
        serve_executor(
            paths=self.paths,
            spool=spool,
            backend_factory=lambda: session,
            runtime=self.runtime,
            stop_requested=lambda: not spool.ready,
            epoch_ns=self.clock.time_ns,
            monotonic=self.clock.monotonic,
            monotonic_ns=lambda: self.clock.monotonic_ns,
            sleeper=lambda _: None,
        )

        self.assertEqual(1, session.api_slot_call_count)
        self.assertEqual([], sent)

    def test_multi_child_batch_slot_sends_each_child_once(self) -> None:
        session = stage931.CtpExecutionSession.for_callbacks(
            runtime=self.runtime,
            service_generation="service-1",
            official_version="official-test",
            capital=200_000.0,
            readiness_ttl_seconds=30.0,
            connect_startup_bundle=lambda: {"ready": True},
            disconnect_transport=lambda: None,
            fresh_bundle=lambda *_: (),
            reserve_api_slot=lambda *_: "batch-slot-1",
            send_order=lambda *_: stage931.BrokerSendBatchResult(
                order_ids=("CTP.1", "CTP.2"),
                send_order_call_count=2,
            ),
            epoch_ns=self.clock.time_ns,
            monotonic=self.clock.monotonic,
        )
        session.connect()
        durable_slots: list[str] = []

        result = session.execute_spool_lease(
            lease=SimpleNamespace(intent=SimpleNamespace(intent_id="intent-1")),
            hard_deadline_monotonic=self.clock.monotonic() + 20.0,
            api_slot_durable=lambda batch_id: not durable_slots.append(batch_id),
        )

        self.assertEqual("sent", result.disposition)
        self.assertEqual(2, result.send_order_call_count)
        self.assertEqual(2, session.send_order_call_count)
        self.assertEqual(["batch-slot-1"], durable_slots)

    def test_multi_child_empty_return_is_unknown_and_does_not_retry(self) -> None:
        session = stage931.CtpExecutionSession.for_callbacks(
            runtime=self.runtime,
            service_generation="service-1",
            official_version="official-test",
            capital=200_000.0,
            readiness_ttl_seconds=30.0,
            connect_startup_bundle=lambda: {"ready": True},
            disconnect_transport=lambda: None,
            fresh_bundle=lambda *_: (),
            reserve_api_slot=lambda *_: "batch-slot-1",
            send_order=lambda *_: stage931.BrokerSendBatchResult(
                order_ids=("CTP.1", ""),
                send_order_call_count=2,
            ),
            epoch_ns=self.clock.time_ns,
            monotonic=self.clock.monotonic,
        )
        session.connect()

        result = session.execute_spool_lease(
            lease=SimpleNamespace(intent=SimpleNamespace(intent_id="intent-1")),
            hard_deadline_monotonic=self.clock.monotonic() + 20.0,
            api_slot_durable=lambda _: True,
        )

        self.assertEqual("side_effect_unknown", result.disposition)
        self.assertEqual(2, result.send_order_call_count)
        self.assertEqual(("stage179_send_order_returned_empty",), result.blockers)

    def test_multi_child_second_send_exception_is_unknown_with_call_count(self) -> None:
        def raise_after_second_call(_lease: Any) -> object:
            raise stage931.BrokerSendBatchError(
                "second child failed",
                send_order_call_count=2,
            )

        session = stage931.CtpExecutionSession.for_callbacks(
            runtime=self.runtime,
            service_generation="service-1",
            official_version="official-test",
            capital=200_000.0,
            readiness_ttl_seconds=30.0,
            connect_startup_bundle=lambda: {"ready": True},
            disconnect_transport=lambda: None,
            fresh_bundle=lambda *_: (),
            reserve_api_slot=lambda *_: "batch-slot-1",
            send_order=raise_after_second_call,
            epoch_ns=self.clock.time_ns,
            monotonic=self.clock.monotonic,
        )
        session.connect()

        result = session.execute_spool_lease(
            lease=SimpleNamespace(intent=SimpleNamespace(intent_id="intent-1")),
            hard_deadline_monotonic=self.clock.monotonic() + 20.0,
            api_slot_durable=lambda _: True,
        )

        self.assertEqual("side_effect_unknown", result.disposition)
        self.assertEqual(2, result.send_order_call_count)
        self.assertEqual(2, session.send_order_call_count)

    def test_socket_loss_is_recovered_by_point_one_second_poll(self) -> None:
        spool = DelayedFakeSpool(["intent-1"], self.clock)
        session = FakeWarmSession(self.clock)
        sleeps: list[float] = []

        @contextmanager
        def missing_socket(_path: Path) -> Any:
            yield None

        def sleep(seconds: float) -> None:
            sleeps.append(seconds)
            self.clock.advance(seconds)

        with patch.object(execution_service, "_wakeup_socket", missing_socket):
            serve_executor(
                paths=self.paths,
                spool=spool,
                backend_factory=lambda: session,
                runtime=self.runtime,
                stop_requested=lambda: not spool.ready,
                epoch_ns=self.clock.time_ns,
                monotonic=self.clock.monotonic,
                monotonic_ns=lambda: self.clock.monotonic_ns,
                sleeper=sleep,
            )

        self.assertEqual([0.1], sleeps)
        self.assertEqual(1, session.send_calls)
        self.assertLessEqual(sum(sleeps), 0.5)

    def test_transport_disconnect_reconnects_before_next_lease_and_changes_generation(self) -> None:
        spool = FakeSpool(["intent-1"], self.clock)
        session = FakeWarmSession(self.clock)
        session.transport_failures = 1

        serve_executor(
            paths=self.paths,
            spool=spool,
            backend_factory=lambda: session,
            runtime=self.runtime,
            stop_requested=lambda: not spool.ready,
            epoch_ns=self.clock.time_ns,
            monotonic=self.clock.monotonic,
            monotonic_ns=lambda: self.clock.monotonic_ns,
            sleeper=lambda _: None,
        )

        self.assertEqual(2, session.connect_calls)
        self.assertEqual("connection-2", session.connection_generation)
        self.assertEqual(1, session.send_calls)

    def test_old_connection_generation_lease_cannot_authorize_send_after_reconnect(self) -> None:
        session = stage931.CtpExecutionSession.for_callbacks(
            runtime=self.runtime,
            service_generation="service-1",
            official_version="official-test",
            capital=200_000.0,
            readiness_ttl_seconds=3.0,
            connect_startup_bundle=lambda: {"ready": True},
            disconnect_transport=lambda: None,
            fresh_bundle=lambda *_: (),
            reserve_api_slot=lambda *_: "slot-1",
            send_order=lambda *_: "order-1",
            epoch_ns=self.clock.time_ns,
            monotonic=self.clock.monotonic,
        )
        session.connect()
        old_lease = session.readiness_lease(now_epoch_ns=self.clock.time_ns())
        session.reconnect()

        result = session.execute_with_readiness(
            readiness=old_lease,
            lease=SimpleNamespace(intent=SimpleNamespace(intent_id="intent-1")),
            hard_deadline_monotonic=self.clock.monotonic() + 20.0,
        )

        self.assertEqual("blocked", result.disposition)
        self.assertEqual(
            ("stage179_readiness_connection_generation_mismatch",),
            result.blockers,
        )
        self.assertEqual(0, result.send_order_call_count)
        self.assertEqual(0, session.api_slot_call_count)

    def test_readiness_lease_expires_and_is_revoked_immediately_on_disconnect(self) -> None:
        revoked: list[str] = []
        session = stage931.CtpExecutionSession.for_callbacks(
            runtime=self.runtime,
            service_generation="service-1",
            official_version="official-test",
            capital=200_000.0,
            readiness_ttl_seconds=3.0,
            connect_startup_bundle=lambda: {"ready": True},
            disconnect_transport=lambda: revoked.append("transport"),
            revoke_readiness=lambda reason: revoked.append(reason),
            fresh_bundle=lambda *_: (),
            reserve_api_slot=lambda *_: "slot-1",
            send_order=lambda *_: "order-1",
            epoch_ns=self.clock.time_ns,
            monotonic=self.clock.monotonic,
        )
        session.connect()
        lease = session.readiness_lease(now_epoch_ns=self.clock.time_ns())
        self.clock.advance(3.0)

        expired = session.execute_with_readiness(
            readiness=lease,
            lease=SimpleNamespace(intent=SimpleNamespace(intent_id="intent-1")),
            hard_deadline_monotonic=self.clock.monotonic() + 20.0,
        )
        session.disconnect()

        self.assertEqual(("stage179_readiness_lease_expired",), expired.blockers)
        self.assertEqual(["ctp_session_disconnected", "transport"], revoked)
        self.assertEqual(["stage179_ctp_transport_not_connected"], session.transport_blockers())

    def test_dequeue_to_send_20s_deadline_is_shared_by_all_query_waits(self) -> None:
        session = stage931.CtpExecutionSession.for_callbacks(
            runtime=self.runtime,
            service_generation="service-1",
            official_version="official-test",
            capital=200_000.0,
            readiness_ttl_seconds=30.0,
            connect_startup_bundle=lambda: {"ready": True},
            disconnect_transport=lambda: None,
            fresh_bundle=lambda *_: self.clock.advance(20.0),
            reserve_api_slot=lambda *_: "slot-1",
            send_order=lambda *_: "order-1",
            epoch_ns=self.clock.time_ns,
            monotonic=self.clock.monotonic,
        )
        session.connect()

        result = session.execute_spool_lease(
            lease=SimpleNamespace(intent=SimpleNamespace(intent_id="intent-1")),
            hard_deadline_monotonic=self.clock.monotonic() + 20.0,
        )

        self.assertEqual("blocked", result.disposition)
        self.assertEqual(
            ("stage179_execution_deadline_exceeded:post_fresh_bundle",),
            result.blockers,
        )
        self.assertEqual(0, session.api_slot_call_count)
        self.assertEqual(0, session.send_order_call_count)

    def test_final_query_reports_shared_absolute_deadline_phase(self) -> None:
        td_api = SimpleNamespace(
            brokerid="fake-broker",
            userid="fake-user",
            reqid=0,
            reqQryOrder=lambda _request, _reqid: 0,
        )
        rows: dict[str, Any] = {
            "order_query_callbacks": [],
        }

        result = stage931._final_order_query_epoch(
            td_api,
            rows,
            max_wait_seconds=8.0,
            hard_deadline_monotonic=self.clock.monotonic() + 0.1,
            monotonic=self.clock.monotonic,
            sleeper=self.clock.advance,
            poll_seconds=0.05,
        )

        self.assertEqual(
            ["stage179_execution_deadline_exceeded:final_order_query"],
            result["blockers"],
        )

    def test_q2_order_trade_position_watermark_change_still_blocks_warm_session(self) -> None:
        session = stage931.CtpExecutionSession.for_callbacks(
            runtime=self.runtime,
            service_generation="service-1",
            official_version="official-test",
            capital=200_000.0,
            readiness_ttl_seconds=30.0,
            connect_startup_bundle=lambda: {"ready": True},
            disconnect_transport=lambda: None,
            fresh_bundle=lambda *_: (),
            pre_api_slot_blockers=lambda *_: [
                "post_final_gate_pre_api_slot_event_trade_watermark_changed"
            ],
            reserve_api_slot=lambda *_: "slot-1",
            send_order=lambda *_: "order-1",
            epoch_ns=self.clock.time_ns,
            monotonic=self.clock.monotonic,
        )
        session.connect()

        result = session.execute_spool_lease(
            lease=SimpleNamespace(intent=SimpleNamespace(intent_id="intent-1")),
            hard_deadline_monotonic=self.clock.monotonic() + 20.0,
        )

        self.assertEqual("blocked", result.disposition)
        self.assertEqual(0, session.api_slot_call_count)
        self.assertEqual(0, session.send_order_call_count)

    def test_disconnect_during_api_slot_reservation_blocks_send(self) -> None:
        disconnected = {"value": False}

        def reserve(_lease: Any) -> str:
            disconnected["value"] = True
            return "slot-1"

        session = stage931.CtpExecutionSession.for_callbacks(
            runtime=self.runtime,
            service_generation="service-1",
            official_version="official-test",
            capital=200_000.0,
            readiness_ttl_seconds=30.0,
            connect_startup_bundle=lambda: {"ready": True},
            disconnect_transport=lambda: None,
            transport_probe=lambda: (
                ["stage179_ctp_transport_generation_invalidated"]
                if disconnected["value"]
                else []
            ),
            fresh_bundle=lambda *_: (),
            reserve_api_slot=reserve,
            send_order=lambda *_: "order-1",
            epoch_ns=self.clock.time_ns,
            monotonic=self.clock.monotonic,
        )
        session.connect()

        result = session.execute_spool_lease(
            lease=SimpleNamespace(intent=SimpleNamespace(intent_id="intent-1")),
            hard_deadline_monotonic=self.clock.monotonic() + 20.0,
        )

        self.assertEqual("side_effect_unknown", result.disposition)
        self.assertEqual(0, result.send_order_call_count)
        self.assertEqual(0, session.send_order_call_count)

    def test_readiness_file_is_atomic_and_singleton_rejects_second_executor(self) -> None:
        readiness = stage931.TdReadinessLease(
            service_generation="service-1",
            connection_generation="connection-1",
            runtime_profile="simnow",
            official_version="official-test",
            capital=200_000.0,
            issued_epoch_ns=self.clock.time_ns(),
            expires_epoch_ns=self.clock.time_ns() + 3_000_000_000,
            last_complete_startup_bundle_epoch_ns=self.clock.time_ns(),
        )
        publish_readiness(self.paths.readiness_path, readiness)
        self.assertIn('"status":"ready"', self.paths.readiness_path.read_text())
        revoke_readiness(
            self.paths.readiness_path,
            service_generation="service-1",
            reason="test",
            revoked_epoch_ns=self.clock.time_ns(),
        )
        self.assertIn('"status":"revoked"', self.paths.readiness_path.read_text())

        with singleton_executor_lock(self.paths.singleton_lock_path):
            with self.assertRaises(ExecutorAlreadyRunningError):
                with singleton_executor_lock(self.paths.singleton_lock_path):
                    pass

    def test_readiness_replace_failure_preserves_previous_generation(self) -> None:
        old = stage931.TdReadinessLease(
            service_generation="service-old",
            connection_generation="connection-old",
            runtime_profile="simnow",
            official_version="official-test",
            capital=200_000.0,
            issued_epoch_ns=self.clock.time_ns(),
            expires_epoch_ns=self.clock.time_ns() + 3_000_000_000,
            last_complete_startup_bundle_epoch_ns=self.clock.time_ns(),
        )
        new = stage931.TdReadinessLease(
            service_generation="service-new",
            connection_generation="connection-new",
            runtime_profile="simnow",
            official_version="official-test",
            capital=200_000.0,
            issued_epoch_ns=self.clock.time_ns(),
            expires_epoch_ns=self.clock.time_ns() + 3_000_000_000,
            last_complete_startup_bundle_epoch_ns=self.clock.time_ns(),
        )
        publish_readiness(self.paths.readiness_path, old)

        with patch.object(execution_service.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaises(OSError):
                publish_readiness(self.paths.readiness_path, new)

        payload = self.paths.readiness_path.read_text(encoding="utf-8")
        self.assertIn('"service_generation":"service-old"', payload)
        self.assertNotIn("service-new", payload)

    def test_absolute_25s_intent_deadline_blocks_before_api_slot_and_send(self) -> None:
        spool = FakeSpool(["intent-1"], self.clock)
        session = FakeWarmSession(self.clock)
        self.clock.advance(25.0)

        serve_executor(
            paths=self.paths,
            spool=spool,
            backend_factory=lambda: session,
            runtime=self.runtime,
            stop_requested=lambda: not spool.ready,
            epoch_ns=self.clock.time_ns,
            monotonic=self.clock.monotonic,
            sleeper=lambda _: None,
        )

        self.assertEqual(0, session.api_slot_calls)
        self.assertEqual(0, session.send_calls)
        self.assertEqual(
            ("intent-1", "expired"),
            spool.transitions[-1],
        )

    def test_half_second_dequeue_sla_blocks_before_fresh_bundle_and_api_slot(self) -> None:
        spool = SlowLeaseFakeSpool(["intent-1"], self.clock)
        session = FakeWarmSession(self.clock)

        serve_executor(
            paths=self.paths,
            spool=spool,
            backend_factory=lambda: session,
            runtime=self.runtime,
            stop_requested=lambda: not spool.ready,
            epoch_ns=self.clock.time_ns,
            monotonic=self.clock.monotonic,
            monotonic_ns=lambda: self.clock.monotonic_ns,
            sleeper=lambda _: None,
        )

        self.assertEqual(0, session.fresh_bundle_calls)
        self.assertEqual(0, session.api_slot_calls)
        self.assertEqual(0, session.send_calls)
        self.assertEqual(("intent-1", "blocked"), spool.transitions[-1])

    def test_existing_one_shot_cli_remains_backward_compatible_without_command_flag(self) -> None:
        args = stage931.parse_args(["--target-date", "2026-07-18"])

        self.assertEqual("once", args.command)
        self.assertEqual("2026-07-18", args.target_date)
        self.assertEqual("dry-run", args.mode)
        self.assertFalse(args.stage179_warm_executor)

    def test_legacy_live_real_dispatch_does_not_enter_warm_service(self) -> None:
        argv = [
            "--target-date",
            "2026-07-18",
            "--mode",
            "live-real",
        ]
        with patch.object(stage931, "run_once", return_value={}) as run_once:
            with patch.object(stage931, "run_serve") as run_serve:
                stage931.main(argv)

        run_once.assert_called_once()
        run_serve.assert_not_called()

    def test_warm_live_real_wrong_profile_fails_before_gate_or_ctp_builder(self) -> None:
        args = stage931.parse_args(
            [
                "--command",
                "serve",
                "--stage179-warm-executor",
                "--mode",
                "live-real",
                "--target-date",
                "2026-07-18",
                "--runtime-profile",
                "offline",
                "--order-scope",
                "none",
            ]
        )
        with patch.object(stage931, "evaluate_stage179_pre_adapter_gate") as gate:
            with patch.object(stage931, "_build_stage179_warm_ctp_session") as builder:
                with self.assertRaisesRegex(
                    stage931.RuntimeProfileError,
                    "runtime_profile_does_not_permit_submit",
                ):
                    stage931.run_serve(args)

        gate.assert_not_called()
        builder.assert_not_called()

    def test_real_cli_no_submit_prewarm_never_opens_spool_or_loads_ctp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime_root = Path(directory) / "runtime"
            runtime = resolve_runtime_profile(
                profile=ExecutionRuntimeProfile.OFFLINE,
                order_scope=OrderScope.NONE,
                repo_root=ROOT,
                output_root=runtime_root,
            )
            command = [
                sys.executable,
                str(
                    PORTFOLIO_DIR
                    / "run_qmt_roll_stage931_official_live_ctp_submit_adapter.py"
                ),
                "--command",
                "serve",
                "--stage179-warm-executor",
                "--mode",
                "dry-run",
                "--runtime-profile",
                "offline",
                "--order-scope",
                "none",
                "--stage179-runtime-root",
                str(runtime_root),
            ]
            environment = dict(os.environ)
            environment["QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR"] = "1"
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.addCleanup(
                lambda: process.kill() if process.poll() is None else None
            )
            deadline = time.monotonic() + 8.0
            status: dict[str, Any] = {}
            while time.monotonic() < deadline:
                try:
                    status = json.loads(
                        runtime.readiness_path.read_text(encoding="utf-8")
                    )
                except (OSError, ValueError):
                    time.sleep(0.05)
                    continue
                if status.get("status") == "prewarm_no_submit":
                    break
                time.sleep(0.05)
            process.terminate()
            stdout, stderr = process.communicate(timeout=8.0)

            self.assertEqual(0, process.returncode, msg=stdout + stderr)
            self.assertEqual("prewarm_no_submit", status.get("status"))
            self.assertEqual(0, status.get("spool_opened"))
            self.assertEqual(0, status.get("ctp_module_loaded"))
            self.assertEqual(0, status.get("order_api_called_count"))
            self.assertFalse(runtime.spool_path.exists())

    def test_warm_dry_run_does_not_import_ctp_or_require_activation_receipt(self) -> None:
        args = stage931.parse_args(
            [
                "--target-date",
                "2026-07-18",
                "--stage179-warm-executor",
                "--runtime-profile",
                "simnow",
                "--order-scope",
                "test",
            ]
        )
        gate_result = SimpleNamespace(
            blockers=(),
            manifest_sha256="a" * 64,
            adapter_created=False,
        )
        imported: list[str] = []
        real_import = __import__

        def guarded_import(name: str, *import_args: Any, **import_kwargs: Any) -> Any:
            if name.startswith("vnpy_ctp"):
                imported.append(name)
                raise AssertionError("dry-run imported vnpy_ctp")
            return real_import(name, *import_args, **import_kwargs)

        with tempfile.TemporaryDirectory() as output:
            with patch.object(stage931, "OUTPUT_DIR", Path(output)):
                with patch.object(stage931, "_stage905_intents", return_value=pd.DataFrame()):
                    with patch.object(stage931, "_read_json", return_value={}):
                        with patch.object(stage931, "_file_age_seconds", return_value=None):
                            with patch.object(stage931, "read_execution_ledger", return_value=[]):
                                with patch.object(
                                    stage931,
                                    "evaluate_stage179_pre_adapter_gate",
                                    return_value=gate_result,
                                ) as gate:
                                    with patch.object(
                                        stage931,
                                        "_send_submit_email",
                                        return_value={"email_status": "test"},
                                    ):
                                        with patch("builtins.__import__", side_effect=guarded_import):
                                            with patch("builtins.print"):
                                                summary = stage931.run_once(args)

        self.assertEqual([], imported)
        self.assertEqual(0, summary["order_api_called_count"])
        self.assertIsNone(
            gate.call_args.kwargs["activation_receipt_path"]
        )

    def test_warm_production_live_correct_profile_still_policy_conflict_blocks_before_ctp(self) -> None:
        args = stage931.parse_args(
            [
                "--command",
                "serve",
                "--stage179-warm-executor",
                "--mode",
                "live-real",
                "--target-date",
                "2026-07-18",
                "--runtime-profile",
                "production-live",
                "--order-scope",
                "live",
                "--confirm-live-real",
                stage931.PHASE_D_CONFIRM_TEXT,
            ]
        )
        gate_result = SimpleNamespace(
            blockers=("operator_policy_conflict_unresolved",),
        )
        armed_environment = {
            stage931.PHASE_D_REAL_ADAPTER_ENV: "1",
            stage931.PHASE_D_REAL_ENABLED_ENV: "1",
            **{key: "test-value" for key in stage931.CTP_ENV_KEYS},
        }
        with patch.object(
            stage931,
            "_load_runtime_env_values",
            return_value=armed_environment,
        ):
            with patch.object(
                stage931,
                "evaluate_stage179_pre_adapter_gate",
                return_value=gate_result,
            ):
                with patch.object(stage931, "_build_stage179_warm_ctp_session") as builder:
                    with self.assertRaisesRegex(
                        stage931.RuntimeProfileError,
                        "operator_policy_conflict_unresolved",
                    ):
                        stage931.run_serve(args)

        builder.assert_not_called()

    def test_simnow_serve_still_requires_explicit_submit_confirmation(self) -> None:
        args = stage931.parse_args(
            [
                "--command",
                "serve",
                "--stage179-warm-executor",
                "--mode",
                "live-real",
                "--target-date",
                "2026-07-18",
                "--runtime-profile",
                "simnow",
                "--order-scope",
                "test",
            ]
        )
        environment = {
            stage931.PHASE_D_REAL_ADAPTER_ENV: "1",
            stage931.PHASE_D_REAL_ENABLED_ENV: "1",
            **{key: "test-value" for key in stage931.CTP_ENV_KEYS},
        }
        with patch.object(
            stage931,
            "_load_runtime_env_values",
            return_value=environment,
        ):
            with patch.object(stage931, "evaluate_stage179_pre_adapter_gate") as gate:
                with patch.object(stage931, "_build_stage179_warm_ctp_session") as builder:
                    with self.assertRaisesRegex(
                        stage931.RuntimeProfileError,
                        "confirm_live_real_missing",
                    ):
                        stage931.run_serve(args)

        gate.assert_not_called()
        builder.assert_not_called()

    def test_canonical_stage905_spool_payload_reconstructs_legacy_validation_columns(self) -> None:
        order_payload = {
            "intent_id": "retry-open-1",
            "source": "stage904_c9_intraday_retry_open",
            "target_date": "2026-07-18",
            "symbol": "JM609",
            "exchange": "DCE",
            "direction": "short",
            "type": "limit",
            "volume": 1,
            "price": 1245.5,
            "offset": "open",
            "reference": "Stage905PhaseD:retry-open-1",
            "vt_symbol": "JM609.DCE",
            "gateway_name": "CTP",
            "action_id": "retry-open-1",
            "root_position_id": "root-1",
            "position_cycle_id": "cycle-1",
            "position_epoch_id": "epoch-1",
            "intent_role": stage931.RETRY_OPEN_ACTION_ROLE,
            "monitor_run_id": "monitor-1",
            "manual_intervention_required": 0,
        }
        canonical_payload = {
            "intent_id": "retry-open-1",
            "source": "stage904_c9_intraday_retry_open",
            "target_date": "2026-07-18",
            "vt_symbol": "JM609.DCE",
            "offset": "open",
            "planned_volume": 1,
            "executor_status": "dry_run_order_request_payload_ready",
            "action_id": "retry-open-1",
            "root_position_id": "root-1",
            "position_cycle_id": "cycle-1",
            "position_epoch_id": "epoch-1",
            "intent_role": stage931.RETRY_OPEN_ACTION_ROLE,
            "monitor_run_id": "monitor-1",
            "manual_intervention_required": 0,
            "order_request": order_payload,
        }
        lease = SimpleNamespace(
            intent=SimpleNamespace(
                intent_id="retry-open-1",
                payload=canonical_payload,
            )
        )

        row, materialized_order = stage931._stage179_spool_lease_row(lease)
        request = stage931._order_request_from_payload(materialized_order)

        self.assertEqual([], stage931._pre_reserved_child_intent_blockers(row, request))
        self.assertEqual(order_payload, json.loads(row["order_request_json"]))

    def test_warm_diagnostic_buffers_remain_bounded_under_long_session_load(self) -> None:
        rows: dict[str, Any] = {
            "ticks": [{"sequence": index} for index in range(10_000)],
            "logs": [{"msg": "startup"}]
            + [{"msg": f"log-{index}"} for index in range(10_000)],
            "orders": [{"sequence": index} for index in range(5_000)],
            "trades": [{"sequence": index} for index in range(5_000)],
            "accounts": [{"sequence": index} for index in range(500)],
            "position_events_unscoped": [
                {"sequence": index} for index in range(5_000)
            ],
            "order_insert_requests": [
                {"sequence": index} for index in range(5_000)
            ],
        }

        stage931._prune_stage179_warm_rows(rows)

        self.assertEqual(4096, len(rows["ticks"]))
        self.assertEqual(10_000 - 1, rows["ticks"][-1]["sequence"])
        self.assertLessEqual(len(rows["logs"]), 128 + 2048)
        self.assertEqual("startup", rows["logs"][0]["msg"])
        self.assertEqual(2048, len(rows["orders"]))
        self.assertEqual(2048, len(rows["trades"]))


if __name__ == "__main__":
    unittest.main()
