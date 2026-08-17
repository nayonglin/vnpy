from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import contextmanager, redirect_stderr
from io import StringIO
import json
import os
import subprocess
import threading
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

    def test_warm_builder_binds_one_ingress_lock_to_state_and_instrumentation_rows(
        self,
    ) -> None:
        session = stage931._build_stage179_warm_ctp_session(
            SimpleNamespace(target_date="2026-07-18"),
            self.runtime,
            self.paths,
        )
        closure = {
            name: cell.cell_contents
            for name, cell in zip(
                session._send_order.__code__.co_freevars,
                session._send_order.__closure__ or (),
            )
        }
        state = closure["state"]

        self.assertIs(
            state["execution_event_ingress_lock"],
            state["rows"]["_execution_event_ingress_lock"],
        )

    def _run_strict_physical_batch_case(
        self,
        requests: list[Any],
        *,
        reqid_jump: int = 1,
        external_event: str = "",
        own_trade_after_first: bool = False,
        mutate_after_first: str = "",
    ) -> dict[str, Any]:
        args = SimpleNamespace(
            target_date="2026-07-18",
            fill_wait_seconds=0.0,
            final_order_query_wait_seconds=0.0,
            post_cancel_wait_seconds=0.0,
            max_stage904_age_seconds=30,
        )
        session = stage931._build_stage179_warm_ctp_session(
            args, self.runtime, self.paths
        )
        closure = {
            name: cell.cell_contents
            for name, cell in zip(
                session._send_order.__code__.co_freevars,
                session._send_order.__closure__ or (),
            )
        }
        state = closure["state"]

        class FakeTdApi:
            reqid = 700
            brokerid = "fake-broker"
            userid = "fake-user"
            login_status = True
            contract_inited = True

        td_api = FakeTdApi()
        state["td_api"] = td_api
        state["readiness_state"] = stage931.CtpReadinessState(
            account_required=True
        )
        state["connection_generation"] = "connection-1"
        state["transport_generation_invalidated"] = False
        rows = state["rows"]
        rows["_ctp_last_query_monotonic"] = 12.5
        rows["_execution_event_ingress_counts"] = {
            "order": 0,
            "trade": 0,
            "position": 0,
        }
        rows["orders"].clear()
        rows["trades"].clear()
        rows["account_query_callbacks"].clear()
        rows["max_order_volume_query_callbacks"].clear()
        baseline = stage931._execution_event_watermark(rows)
        open_funds_gate: dict[str, Any] = {}
        if any(request.offset == stage931.Offset.OPEN for request in requests):
            empty_sha = stage931._canonical_evidence_sha256([])
            open_funds_gate = {
                "confirmed": True,
                "status": "confirmed",
                "request_bundle_sha256": stage931._canonical_evidence_sha256(
                    stage931._physical_request_bundle(requests)
                ),
                "event_watermark": dict(baseline),
                "query_watermark": {
                    "broker_id": td_api.brokerid,
                    "investor_id": td_api.userid,
                    "td_reqid_after": td_api.reqid,
                    "ctp_last_query_monotonic": 12.5,
                    "account_reqid": -1,
                    "max_volume_reqids": [],
                    "account_callback_count": 0,
                    "max_volume_callback_count": 0,
                    "account_callbacks_sha256": empty_sha,
                    "max_volume_callbacks_sha256": empty_sha,
                },
            }
        intent_kind = (
            "open"
            if any(request.offset == stage931.Offset.OPEN for request in requests)
            else "close"
        )
        intent_id = f"strict-batch-{intent_kind}"
        state["intent_contexts"][intent_id] = {
            "requests": list(requests),
            "request": requests[0],
            "row": {},
            "fingerprint": f"fingerprint-{intent_kind}",
            "final_watermark": dict(baseline),
            "open_funds_gate": open_funds_gate,
            "physical_batch_query_watermark": (
                stage931._physical_batch_query_watermark(td_api, rows)
            ),
            "hard_deadline_monotonic": time.monotonic() + 60.0,
        }
        state["authorization_pin"] = {
            "record": {"state_revision": 3},
            "authorization_lane": "all",
            "intent_scope": "all",
        }
        lease = SimpleNamespace(
            intent=SimpleNamespace(
                intent_id=intent_id,
                payload_sha256="a" * 64,
                target_date="2026-07-18",
                intent_kind=intent_kind,
                vt_symbol=requests[0].vt_symbol,
                source="",
                trace_id="trace-1",
                spool_sequence=1,
                state_revision=4,
                state="leased",
                state_generation="epoch-1:0",
                position_epoch_id="epoch-1",
                deadline_epoch_ns=time.time_ns() + 60_000_000_000,
                lease_owner=session.service_generation,
                payload={
                    "intent_role": "test",
                    "root_position_id": "root-1",
                    "position_cycle_id": "cycle-1",
                },
            ),
            lease_token="lease-1",
        )
        kill_blockers: list[str] = []
        ledger_events: list[dict[str, Any]] = []
        broker_events: list[dict[str, Any]] = []
        lock_probe_acquired: list[bool] = []

        class FakeMainEngine:
            def __init__(self) -> None:
                self.send_attempts = 0
                self.native_calls = 0
                self.native_gate_blockers: list[str] = []
                self.native_prices: list[float] = []

            @staticmethod
            def native_request(request: Any, order_ref: str) -> dict[str, Any]:
                direction = {
                    stage931.Direction.LONG: stage931.CTP_DIRECTION_BUY,
                    stage931.Direction.SHORT: stage931.CTP_DIRECTION_SELL,
                }[request.direction]
                offset = {
                    stage931.Offset.OPEN: stage931.CTP_OFFSET_OPEN,
                    stage931.Offset.CLOSE: stage931.CTP_OFFSET_CLOSE,
                    stage931.Offset.CLOSETODAY: (
                        stage931.CTP_OFFSET_CLOSE_TODAY
                    ),
                    stage931.Offset.CLOSEYESTERDAY: (
                        stage931.CTP_OFFSET_CLOSE_YESTERDAY
                    ),
                }[request.offset]
                order_type = {
                    stage931.OrderType.LIMIT: ("2", "3", "1"),
                    stage931.OrderType.FAK: ("2", "1", "1"),
                }[request.type]
                return {
                    "BrokerID": td_api.brokerid,
                    "InvestorID": td_api.userid,
                    "UserID": td_api.userid,
                    "InstrumentID": request.symbol,
                    "ExchangeID": request.exchange.value,
                    "Direction": direction,
                    "CombOffsetFlag": offset,
                    "CombHedgeFlag": stage931.CTP_HEDGE_SPECULATION,
                    "OrderPriceType": order_type[0],
                    "TimeCondition": order_type[1],
                    "VolumeCondition": order_type[2],
                    "VolumeTotalOriginal": int(request.volume),
                    "LimitPrice": float(request.price),
                    "OrderRef": order_ref,
                }

            @staticmethod
            def append_ingress(kind: str, row: dict[str, Any]) -> None:
                rows[f"{kind}s"].append(row)
                rows["_execution_event_ingress_counts"][kind] += 1

            def send_order(self, request: Any, _gateway: str) -> str:
                self.send_attempts += 1
                td_api.reqid += reqid_jump
                native_request = self.native_request(
                    request, str(self.send_attempts)
                )
                native_gate = state["native_dynamic_gate"]
                blockers = list(
                    native_gate(td_api, native_request, td_api.reqid)
                )
                if blockers:
                    self.native_gate_blockers = blockers
                    raise stage931.BrokerSendBatchError(
                        "fake_native_gate_blocked:" + ";".join(blockers),
                        send_order_call_count=self.native_calls,
                    )
                vt_orderid = f"CTP.1_2_{self.send_attempts}"
                child_context = state["native_child_context"]
                batch = state["active_physical_batch"]
                batch["owned_children"][vt_orderid] = {
                    "child_order_id": child_context["child_order_id"],
                    "child_order_index": child_context["child_order_index"],
                    "native_reqid": td_api.reqid,
                    "vt_orderid": vt_orderid,
                    "request": request,
                    "trade_identities": {},
                }
                state["order_contexts"][vt_orderid] = child_context
                state["native_insert_identity"] = {
                    "vt_orderid": vt_orderid
                }
                rows["order_insert_requests"].append(
                    {
                        "reqid": td_api.reqid,
                        "request_ret": 0,
                        "exception": "",
                    }
                )
                self.native_calls += 1
                self.native_prices.append(float(request.price))
                self.append_ingress(
                    "order",
                    {
                        "gateway_name": "CTP",
                        "vt_orderid": vt_orderid,
                        "vt_symbol": request.vt_symbol,
                        "direction": request.direction.value,
                        "offset": request.offset.value,
                        "reference": request.reference,
                        "volume": float(request.volume),
                        "price": float(request.price),
                        "traded": 0.0,
                        "status": "submitting",
                        "_stage179_callback_persistence_confirmed": 1,
                    },
                )
                if self.send_attempts == 1 and own_trade_after_first:
                    self.append_ingress(
                        "trade",
                        {
                            "gateway_name": "CTP",
                            "vt_orderid": vt_orderid,
                            "vt_tradeid": "CTP.trade-1",
                            "vt_symbol": request.vt_symbol,
                            "direction": request.direction.value,
                            "offset": request.offset.value,
                            "volume": float(request.volume),
                            "price": float(request.price),
                            "_stage179_callback_persistence_confirmed": 1,
                        },
                    )
                if self.send_attempts == 1 and external_event:
                    if external_event == "position":
                        rows["position_events_unscoped"].append(
                            {
                                "gateway_name": "CTP",
                                "vt_symbol": request.vt_symbol,
                                "direction": request.direction.value,
                                "volume": float(request.volume),
                            }
                        )
                        rows["_execution_event_ingress_counts"][
                            "position"
                        ] += 1
                        external = None
                    else:
                        external = {
                            "gateway_name": "CTP",
                            "vt_orderid": "CTP.external",
                            "vt_symbol": request.vt_symbol,
                            "direction": request.direction.value,
                            "offset": request.offset.value,
                            "volume": 1.0,
                            "price": float(request.price),
                            "_stage179_callback_persistence_confirmed": 1,
                        }
                    if external_event == "order" and external is not None:
                        external.update(
                            {
                                "reference": "external",
                                "traded": 0.0,
                                "status": "submitting",
                            }
                        )
                    elif external_event == "trade" and external is not None:
                        external["vt_tradeid"] = "CTP.external-trade"
                    if external is not None:
                        self.append_ingress(external_event, external)
                if self.send_attempts == 1 and len(requests) > 1:
                    def probe_lock() -> None:
                        acquired = state["ctp_query_lock"].acquire(
                            blocking=False
                        )
                        lock_probe_acquired.append(acquired)
                        if acquired:
                            state["ctp_query_lock"].release()

                    probe = threading.Thread(target=probe_lock)
                    probe.start()
                    probe.join(timeout=2.0)
                if self.send_attempts == 1:
                    if mutate_after_first == "revoke":
                        state["authorization_pin"] = None
                    elif mutate_after_first == "kill":
                        kill_blockers.append("kill_switch_active")
                    elif mutate_after_first == "disconnect":
                        state["transport_generation_invalidated"] = True
                return vt_orderid

        engine = FakeMainEngine()
        state["main_engine"] = engine

        class NoStartThread:
            def __init__(self, **_kwargs: Any) -> None:
                pass

            def start(self) -> None:
                return None

        result: Any = None
        error: BaseException | None = None
        with (
            patch.object(
                stage931,
                "validate_submit_authorization",
                return_value=[],
            ),
            patch.object(
                stage931,
                "_kill_switch_blockers",
                side_effect=lambda: list(kill_blockers),
            ),
            patch.object(
                stage931,
                "_current_phase_d_sessions",
                return_value=[{"role": "market_and_execution"}],
            ),
            patch.object(
                stage931, "_continuous_submit_blockers", return_value=[]
            ),
            patch.object(
                stage931, "_final_ctp_transport_blockers", return_value=[]
            ),
            patch.object(stage931, "read_execution_ledger", return_value=[]),
            patch.object(
                stage931,
                "append_execution_ledger_event",
                side_effect=lambda event, **_kwargs: (
                    ledger_events.append(dict(event))
                    or {"appended": True}
                ),
            ),
            patch.object(
                stage931,
                "append_broker_callback_event_once",
                side_effect=lambda event, *_args, **_kwargs: (
                    broker_events.append(dict(event))
                    or {"appended": True}
                ),
            ),
            patch.object(stage931, "Thread", NoStartThread),
        ):
            try:
                result = session._send_order(lease)
            except BaseException as exc:
                error = exc
        return {
            "result": result,
            "error": error,
            "engine": engine,
            "td_api": td_api,
            "state": state,
            "ledger_events": ledger_events,
            "broker_events": broker_events,
            "lock_probe_acquired": lock_probe_acquired,
        }

    def test_single_open_native_reqid_accepts_exact_plus_one_and_rejects_jump(self) -> None:
        request = stage931.OrderRequest(
            symbol="jm2609",
            exchange=stage931.Exchange.DCE,
            direction=stage931.Direction.SHORT,
            type=stage931.OrderType.FAK,
            volume=1,
            price=1200.5,
            offset=stage931.Offset.OPEN,
            reference="Stage905PhaseD:strict-batch-open",
        )

        accepted = self._run_strict_physical_batch_case([request])
        self.assertIsNone(accepted["error"])
        self.assertEqual(1, accepted["engine"].send_attempts)
        self.assertEqual(1, accepted["engine"].native_calls)
        self.assertEqual(701, accepted["td_api"].reqid)
        self.assertEqual(
            ("CTP.1_2_1",), accepted["result"].order_ids
        )

        jumped = self._run_strict_physical_batch_case(
            [request], reqid_jump=2
        )
        self.assertIsInstance(
            jumped["error"], stage931.BrokerSendBatchError
        )
        self.assertEqual(1, jumped["engine"].send_attempts)
        self.assertEqual(0, jumped["engine"].native_calls)
        self.assertEqual(702, jumped["td_api"].reqid)
        self.assertTrue(
            any(
                "physical_batch_td_reqid_not_exact_owned_sequence"
                in blocker
                for blocker in jumped["engine"].native_gate_blockers
            ),
            jumped["engine"].native_gate_blockers,
        )

    def test_shfe_ine_two_close_children_share_price_and_batch_lock(self) -> None:
        for exchange, symbol in (
            (stage931.Exchange.SHFE, "rb2610"),
            (stage931.Exchange.INE, "sc2610"),
        ):
            with self.subTest(exchange=exchange.value):
                price = 3200.5
                requests = [
                    stage931.OrderRequest(
                        symbol=symbol,
                        exchange=exchange,
                        direction=stage931.Direction.SHORT,
                        type=stage931.OrderType.LIMIT,
                        volume=1,
                        price=price,
                        offset=offset,
                        reference="Stage905PhaseD:strict-batch-close",
                    )
                    for offset in (
                        stage931.Offset.CLOSETODAY,
                        stage931.Offset.CLOSEYESTERDAY,
                    )
                ]
                observed = self._run_strict_physical_batch_case(requests)

                self.assertIsNone(observed["error"])
                self.assertEqual(2, observed["engine"].native_calls)
                self.assertEqual(
                    [price, price], observed["engine"].native_prices
                )
                self.assertEqual([False], observed["lock_probe_acquired"])
                attributed_orders = [
                    event
                    for event in observed["broker_events"]
                    if event.get("event_type")
                    == "physical_batch_event_attributed"
                    and event.get("callback_kind") == "order"
                ]
                self.assertEqual(2, len(attributed_orders))
                self.assertEqual(
                    {0, 1},
                    {
                        event["child_order_index"]
                        for event in attributed_orders
                    },
                )

    def test_external_execution_event_between_children_blocks_second_native(self) -> None:
        for external_kind in ("order", "trade", "position"):
            with self.subTest(external_kind=external_kind):
                requests = [
                    stage931.OrderRequest(
                        symbol="rb2610",
                        exchange=stage931.Exchange.SHFE,
                        direction=stage931.Direction.SHORT,
                        type=stage931.OrderType.LIMIT,
                        volume=1,
                        price=3200.0,
                        offset=offset,
                        reference="Stage905PhaseD:strict-batch-close",
                    )
                    for offset in (
                        stage931.Offset.CLOSETODAY,
                        stage931.Offset.CLOSEYESTERDAY,
                    )
                ]
                observed = self._run_strict_physical_batch_case(
                    requests, external_event=external_kind
                )

                self.assertIsInstance(
                    observed["error"], stage931.BrokerSendBatchError
                )
                self.assertEqual(1, observed["engine"].native_calls)
                self.assertEqual(1, observed["engine"].send_attempts)
                blocked = [
                    event
                    for event in observed["ledger_events"]
                    if event.get("event_type")
                    == "submit_authorization_blocked_before_child_send"
                ]
                self.assertEqual(1, len(blocked))
                expected_blocker = (
                    "physical_batch_external_position_event"
                    if external_kind == "position"
                    else "physical_batch_external_event_unbound"
                )
                self.assertTrue(
                    any(
                        expected_blocker in blocker
                        for blocker in blocked[0]["blockers"]
                    ),
                    blocked[0]["blockers"],
                )
                self.assertEqual(1, blocked[0]["reconciliation_required"])

    def test_exactly_attributed_batch_fill_allows_second_close_child(self) -> None:
        requests = [
            stage931.OrderRequest(
                symbol="rb2610",
                exchange=stage931.Exchange.SHFE,
                direction=stage931.Direction.SHORT,
                type=stage931.OrderType.LIMIT,
                volume=1,
                price=3200.0,
                offset=offset,
                reference="Stage905PhaseD:strict-batch-close",
            )
            for offset in (
                stage931.Offset.CLOSETODAY,
                stage931.Offset.CLOSEYESTERDAY,
            )
        ]
        observed = self._run_strict_physical_batch_case(
            requests, own_trade_after_first=True
        )

        self.assertIsNone(observed["error"])
        self.assertEqual(2, observed["engine"].native_calls)
        attributed_trades = [
            event
            for event in observed["broker_events"]
            if event.get("event_type")
            == "physical_batch_event_attributed"
            and event.get("callback_kind") == "trade"
        ]
        self.assertEqual(1, len(attributed_trades))
        self.assertEqual(0, attributed_trades[0]["child_order_index"])

    def test_revoke_kill_or_disconnect_between_children_blocks_second_native(self) -> None:
        expected_blockers = {
            "revoke": "stage179_submit_authorization_pin_missing",
            "kill": "kill_switch_active_before_child_send",
            "disconnect": "stage179_ctp_transport_generation_invalidated",
        }
        for mutation, expected in expected_blockers.items():
            with self.subTest(mutation=mutation):
                requests = [
                    stage931.OrderRequest(
                        symbol="rb2610",
                        exchange=stage931.Exchange.SHFE,
                        direction=stage931.Direction.SHORT,
                        type=stage931.OrderType.LIMIT,
                        volume=1,
                        price=3200.0,
                        offset=offset,
                        reference="Stage905PhaseD:strict-batch-close",
                    )
                    for offset in (
                        stage931.Offset.CLOSETODAY,
                        stage931.Offset.CLOSEYESTERDAY,
                    )
                ]
                observed = self._run_strict_physical_batch_case(
                    requests, mutate_after_first=mutation
                )

                self.assertIsInstance(
                    observed["error"], stage931.BrokerSendBatchError
                )
                self.assertEqual(1, observed["engine"].native_calls)
                self.assertEqual(1, observed["engine"].send_attempts)
                blocked = [
                    event
                    for event in observed["ledger_events"]
                    if event.get("event_type")
                    == "submit_authorization_blocked_before_child_send"
                ]
                self.assertEqual(1, len(blocked))
                self.assertIn(expected, blocked[0]["blockers"])
                self.assertEqual(1, blocked[0]["reconciliation_required"])

    def test_warm_pre_api_block_closes_exact_close_attempt_without_side_effect(self) -> None:
        events: list[dict[str, Any]] = []
        lease = SimpleNamespace(
            intent=SimpleNamespace(
                target_date="2026-07-18",
                intent_id="close-1",
                payload_sha256="a" * 64,
                intent_kind="close",
                vt_symbol="JM609.DCE",
                lease_owner="service-1",
            ),
            lease_token="spool-lease-1",
        )
        context = {
            "fingerprint": "fingerprint-1",
            "reservation_record_checksum": "b" * 64,
            "close_submit_attempt_no": 2,
            "close_attempt_lease_token": "ledger-lease-2",
        }

        with patch.object(
            stage931,
            "append_pre_api_slot_no_side_effect_terminal",
            side_effect=lambda **event: events.append(dict(event)) or {
                "appended": True
            },
        ):
            stage931._append_stage179_warm_pre_send_safe_terminal(
                lease=lease,
                context=context,
                blockers=["authorization_expired"],
                ledger_path=self.paths.ledger_path,
            )

        self.assertEqual(1, len(events))
        event = events[0]
        self.assertEqual("close", event["intent_kind"])
        self.assertEqual("b" * 64, event["reservation_record_checksum"])
        self.assertEqual("spool-lease-1", event["spool_lease_token"])
        self.assertEqual(2, event["base_event"]["close_submit_attempt_no"])
        self.assertEqual(
            "ledger-lease-2",
            event["base_event"]["close_attempt_lease_token"],
        )

    def test_warm_pre_api_open_block_uses_same_auditable_safe_terminal(self) -> None:
        events: list[dict[str, Any]] = []
        lease = SimpleNamespace(
            intent=SimpleNamespace(
                target_date="2026-07-18",
                intent_id="open-1",
                payload_sha256="c" * 64,
                intent_kind="open",
                vt_symbol="JM609.DCE",
                lease_owner="service-1",
            ),
            lease_token="spool-lease-open",
        )
        with patch.object(
            stage931,
            "append_pre_api_slot_no_side_effect_terminal",
            side_effect=lambda **event: events.append(dict(event)) or {
                "appended": True
            },
        ):
            stage931._append_stage179_warm_pre_send_safe_terminal(
                lease=lease,
                context={
                    "fingerprint": "open-fingerprint",
                    "reservation_record_checksum": "d" * 64,
                },
                blockers=["final_watermark_changed"],
                ledger_path=self.paths.ledger_path,
            )

        self.assertEqual("open", events[0]["intent_kind"])
        self.assertNotIn("close_submit_attempt_no", events[0]["base_event"])
        self.assertNotIn("close_attempt_lease_token", events[0]["base_event"])
        self.assertEqual(["final_watermark_changed"], events[0]["blockers"])

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

    def test_lease_execution_guard_covers_lease_send_and_durable_result(self) -> None:
        events: list[str] = []

        class GuardedSession(FakeWarmSession):
            def __init__(self, clock: FakeClock) -> None:
                super().__init__(clock)
                self.guard_depth = 0

            @contextmanager
            def lease_execution_guard(self) -> Any:
                events.append("guard_enter")
                self.guard_depth += 1
                try:
                    yield
                finally:
                    self.guard_depth -= 1
                    events.append("guard_exit")

            def pre_lease_blockers(self) -> list[str]:
                self.assert_guarded("pre_lease")
                return super().pre_lease_blockers()

            def pre_lease_authorized_intents(self) -> dict[str, str] | None:
                self.assert_guarded("authorized_map")
                return super().pre_lease_authorized_intents()

            def execute_spool_lease(self, **kwargs: Any) -> ExecutionResult:
                self.assert_guarded("execute")
                return super().execute_spool_lease(**kwargs)

            def assert_guarded(self, phase: str) -> None:
                if self.guard_depth != 1:
                    raise AssertionError(f"guard_missing:{phase}")
                events.append(phase)

        session = GuardedSession(self.clock)

        class GuardedSpool(FakeSpool):
            def lease_next(self, **kwargs: Any) -> Any:
                session.assert_guarded("lease")
                return super().lease_next(**kwargs)

            def mark_sending(self, lease: Any, **kwargs: Any) -> Any:
                session.assert_guarded("mark_sending")
                return super().mark_sending(lease, **kwargs)

            def mark_result(
                self,
                lease: Any,
                result: ExecutionResult,
                **kwargs: Any,
            ) -> None:
                session.assert_guarded("mark_result")
                super().mark_result(lease, result, **kwargs)

        spool = GuardedSpool(["intent-1"], self.clock)
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
            [
                "guard_enter",
                "pre_lease",
                "authorized_map",
                "lease",
                "execute",
                "mark_sending",
                "mark_result",
                "guard_exit",
            ],
            events,
        )
        self.assertEqual(0, session.guard_depth)

    def test_lease_execution_guard_releases_on_empty_lease_and_exception(self) -> None:
        class GuardedSession(FakeWarmSession):
            def __init__(self, clock: FakeClock) -> None:
                super().__init__(clock)
                self.guard_depth = 0
                self.guard_exits = 0

            @contextmanager
            def lease_execution_guard(self) -> Any:
                self.guard_depth += 1
                try:
                    yield
                finally:
                    self.guard_depth -= 1
                    self.guard_exits += 1

        empty_session = GuardedSession(self.clock)

        class EmptySpool(FakeSpool):
            def __init__(self, clock: FakeClock) -> None:
                super().__init__([], clock)
                self.lease_calls = 0

            def lease_next(self, **kwargs: Any) -> Any:
                self.lease_calls += 1
                return None

        empty_spool = EmptySpool(self.clock)
        serve_executor(
            paths=self.paths,
            spool=empty_spool,
            backend_factory=lambda: empty_session,
            runtime=self.runtime,
            stop_requested=lambda: empty_spool.lease_calls >= 1,
            epoch_ns=self.clock.time_ns,
            monotonic=self.clock.monotonic,
            monotonic_ns=lambda: self.clock.monotonic_ns,
            sleeper=lambda _: None,
        )
        self.assertEqual(0, empty_session.guard_depth)
        self.assertEqual(1, empty_session.guard_exits)

        blocked_session = GuardedSession(self.clock)
        blocked_session.pre_lease_blocker_values = [
            "stage179_submit_authorization_missing"
        ]
        blocked_spool = FakeSpool(["intent-blocked"], self.clock)
        serve_executor(
            paths=self.paths,
            spool=blocked_spool,
            backend_factory=lambda: blocked_session,
            runtime=self.runtime,
            stop_requested=lambda: blocked_session.pre_lease_calls >= 1,
            epoch_ns=self.clock.time_ns,
            monotonic=self.clock.monotonic,
            monotonic_ns=lambda: self.clock.monotonic_ns,
            sleeper=lambda _: None,
        )
        self.assertEqual(0, blocked_session.guard_depth)
        self.assertEqual(1, blocked_session.guard_exits)
        self.assertEqual([], blocked_spool.transitions)

        failing_session = GuardedSession(self.clock)

        class FailingSpool(FakeSpool):
            def mark_result(
                self,
                lease: Any,
                result: ExecutionResult,
                **kwargs: Any,
            ) -> None:
                raise RuntimeError("durable_result_failed")

        failing_spool = FailingSpool(["intent-2"], self.clock)
        with self.assertRaisesRegex(RuntimeError, "durable_result_failed"):
            serve_executor(
                paths=self.paths,
                spool=failing_spool,
                backend_factory=lambda: failing_session,
                runtime=self.runtime,
                stop_requested=lambda: not failing_spool.ready,
                epoch_ns=self.clock.time_ns,
                monotonic=self.clock.monotonic,
                monotonic_ns=lambda: self.clock.monotonic_ns,
                sleeper=lambda _: None,
            )
        self.assertEqual(0, failing_session.guard_depth)
        self.assertEqual(1, failing_session.guard_exits)

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
        intent_deadline_ns = authorization_now_ns + 60_000_000_000
        publish_submit_authorization(
            path=authorization_path,
            target_date="2026-07-18",
            execution_profile="c9-15w",
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
                    "vt_symbol": "JM609.DCE",
                    "source": "stage904_c9_intraday_close",
                    "intent_role": "c9_initial_stop_close",
                    "trace_id": "trace-1",
                    "spool_sequence": 7,
                    "state_revision": 3,
                    "state_generation": "epoch-1:0",
                    "position_epoch_id": "epoch-1",
                    "root_position_id": "root-1",
                    "position_cycle_id": "cycle-1",
                    "deadline_epoch_ns": intent_deadline_ns,
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
            spool_path=self.paths.spool_path,
            spool_snapshot_digest="b" * 64,
            cursor_digest="c" * 64,
            stage902_evidence_digest="d" * 64,
            stage927_evidence_digest="e" * 64,
        )

        class FakeMainEngine:
            def __init__(self) -> None:
                self.calls = 0

            def send_order(self, _request: Any, _gateway: str) -> str:
                self.calls += 1
                state["native_insert_identity"] = {
                    "vt_orderid": f"CTP.order-{self.calls}"
                }
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
                source="stage904_c9_intraday_close",
                trace_id="trace-1",
                spool_sequence=7,
                state_revision=4,
                state="leased",
                state_generation="epoch-1:0",
                position_epoch_id="epoch-1",
                deadline_epoch_ns=intent_deadline_ns,
                lease_owner=session.service_generation,
                payload={
                    "intent_role": "c9_initial_stop_close",
                    "root_position_id": "root-1",
                    "position_cycle_id": "cycle-1",
                },
            ),
            lease_token="lease-1",
        )
        ledger_events: list[dict[str, Any]] = []
        with session.lease_execution_guard():
            self.assertEqual([], session.pre_lease_blockers())
            self.assertEqual(
                {"intent-1": "a" * 64},
                session.pre_lease_authorized_intents(),
            )
            self.assertEqual([], session.post_lease_blockers(lease))
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

    def test_cancel_takeover_query_missing_retries_without_external_callback(self) -> None:
        args = SimpleNamespace(
            target_date="2026-07-18",
            fill_wait_seconds=0.0,
            final_order_query_wait_seconds=0.0,
            post_cancel_wait_seconds=0.0,
        )
        session = stage931._build_stage179_warm_ctp_session(
            args,
            self.runtime,
            self.paths,
        )
        closure = {
            name: cell.cell_contents
            for name, cell in zip(
                session._send_order.__code__.co_freevars,
                session._send_order.__closure__ or (),
            )
        }
        state = closure["state"]
        schedule_residual_cancel = closure["schedule_residual_cancel"]
        state["connection_generation"] = "connection-1"
        state["main_engine"] = object()
        state["td_api"] = object()
        vt_orderid = "CTP.1_2_3"
        state["rows"]["orders"].append(
            {
                "vt_orderid": vt_orderid,
                "status": "not traded",
                "traded": 0,
            }
        )
        request = stage931.OrderRequest(
            symbol="JM2609",
            exchange=stage931.Exchange.DCE,
            direction=stage931.Direction.SHORT,
            type=stage931.OrderType.LIMIT,
            volume=1,
            price=1200.0,
            offset=stage931.Offset.CLOSE,
            reference="test-cancel-retry",
        )
        child_context = {
            "target_date": "2026-07-18",
            "intent_id": "intent-cancel-retry",
            "fingerprint": "fingerprint-cancel-retry",
            "child_order_id": "child-1",
            "request": request,
            "connection_generation": "connection-1",
            "service_generation": session.service_generation,
        }
        query_calls: list[str] = []
        exhausted = stage931.Event()
        ledger_events: list[dict[str, Any]] = []

        def query_without_owned_order(*_: Any, **__: Any) -> dict[str, Any]:
            query_calls.append("order")
            return {"confirmed": True, "orders": [], "blockers": [], "reqid": 7}

        def append_event(event: dict[str, Any], **_: Any) -> dict[str, Any]:
            ledger_events.append(dict(event))
            if event.get("event_type") == "cancel_reconciliation_retry_exhausted":
                exhausted.set()
            return dict(event)

        prior_duty = {
            "cancel_duty_state": "reserved",
            "cancel_duty_generation": 1,
            "cancel_duty_owner_id": "other-worker",
        }
        with (
            patch.object(
                stage931,
                "advance_cancel_duty_state",
                return_value={
                    "advanced": False,
                    "blocker": "cancel_duty_owner_lease_active",
                    "ledger_event": prior_duty,
                },
            ),
            patch.object(
                stage931,
                "_final_order_query_epoch",
                side_effect=query_without_owned_order,
            ),
            patch.object(
                stage931,
                "append_execution_ledger_event",
                side_effect=append_event,
            ),
            patch.object(stage931, "revoke_readiness") as revoke,
        ):
            schedule_residual_cancel(vt_orderid, child_context)
            self.assertTrue(exhausted.wait(2.0))

        self.assertEqual(["order", "order"], query_calls)
        self.assertTrue(state["transport_generation_invalidated"])
        self.assertIn(
            "stage179_ctp_transport_generation_invalidated",
            session.transport_blockers(),
        )
        self.assertIn(
            f"stage179_cancel_reconciliation_retry_exhausted:{vt_orderid}",
            list(state["reconciliation_blockers"]),
        )
        revoke.assert_called_once_with(
            self.paths.readiness_path,
            service_generation=session.service_generation,
            reason=f"cancel_reconciliation_retry_exhausted:{vt_orderid}",
        )
        self.assertEqual(
            1,
            sum(
                event.get("event_type")
                == "cancel_reconciliation_retry_exhausted"
                for event in ledger_events
            ),
        )

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

    def test_pre_api_block_after_reserve_returns_retryable_only_after_atomic_terminal(self) -> None:
        terminal_calls: list[tuple[list[str], str]] = []
        session = stage931.CtpExecutionSession.for_callbacks(
            runtime=self.runtime,
            service_generation="service-1",
            official_version="official-test",
            capital=200_000.0,
            readiness_ttl_seconds=30.0,
            connect_startup_bundle=lambda: {"ready": True},
            disconnect_transport=lambda: None,
            fresh_bundle=lambda *_: {"ledger_fingerprint": "fingerprint-1"},
            pre_api_slot_blockers=lambda *_: ["authorization_expired"],
            pre_api_slot_safe_terminal=lambda _lease, blockers, phase: (
                terminal_calls.append((list(blockers), phase))
                or {"appended": True, "blocker": ""}
            ),
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

        self.assertEqual("no_side_effect_retryable", result.disposition)
        self.assertEqual("fingerprint-1", result.ledger_fingerprint)
        self.assertEqual([(["authorization_expired"], "pre_api_slot")], terminal_calls)
        self.assertEqual(0, session.api_slot_call_count)
        self.assertEqual(0, session.send_order_call_count)

    def test_disconnect_during_api_slot_reservation_blocks_send(self) -> None:
        disconnected = {"value": False}
        terminal_calls: list[tuple[str, list[str], str]] = []

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
            post_api_slot_safe_terminal=(
                lambda _lease, batch_id, blockers, phase: (
                    terminal_calls.append((batch_id, blockers, phase))
                    or {"appended": True}
                )
            ),
            epoch_ns=self.clock.time_ns,
            monotonic=self.clock.monotonic,
        )
        session.connect()

        result = session.execute_spool_lease(
            lease=SimpleNamespace(intent=SimpleNamespace(intent_id="intent-1")),
            hard_deadline_monotonic=self.clock.monotonic() + 20.0,
        )

        self.assertEqual("post_slot_no_native_retryable", result.disposition)
        self.assertEqual(0, result.send_order_call_count)
        self.assertEqual(0, session.send_order_call_count)
        self.assertEqual("slot-1", terminal_calls[0][0])

    def test_deadline_after_api_slot_uses_zero_native_safe_terminal(self) -> None:
        terminal_calls: list[tuple[str, list[str], str]] = []

        def reserve(_lease: Any) -> str:
            self.clock.advance(21.0)
            return "slot-deadline"

        session = stage931.CtpExecutionSession.for_callbacks(
            runtime=self.runtime,
            service_generation="service-1",
            official_version="official-test",
            capital=200_000.0,
            readiness_ttl_seconds=30.0,
            connect_startup_bundle=lambda: {"ready": True},
            disconnect_transport=lambda: None,
            fresh_bundle=lambda *_: (),
            reserve_api_slot=reserve,
            send_order=lambda *_: self.fail("native send must remain zero"),
            post_api_slot_safe_terminal=(
                lambda _lease, batch_id, blockers, phase: (
                    terminal_calls.append((batch_id, blockers, phase))
                    or {"appended": True}
                )
            ),
            epoch_ns=self.clock.time_ns,
            monotonic=self.clock.monotonic,
        )
        session.connect()
        result = session.execute_spool_lease(
            lease=SimpleNamespace(intent=SimpleNamespace(intent_id="intent-1")),
            hard_deadline_monotonic=self.clock.monotonic() + 20.0,
        )
        self.assertEqual("post_slot_no_native_retryable", result.disposition)
        self.assertEqual(0, session.send_order_call_count)
        self.assertEqual("pre_send_order_deadline", terminal_calls[0][2])

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

    def test_legacy_live_real_cli_is_rejected_before_dispatch(self) -> None:
        argv = [
            "--target-date",
            "2026-07-18",
            "--mode",
            "live-real",
        ]
        with patch.object(stage931, "run_once", return_value={}) as run_once:
            with patch.object(stage931, "run_serve") as run_serve:
                with self.assertRaises(SystemExit):
                    stage931.main(argv)

        run_once.assert_not_called()
        run_serve.assert_not_called()

    def test_warm_flag_cannot_reenable_one_shot_live_real(self) -> None:
        argv = [
            "--command",
            "once",
            "--target-date",
            "2026-07-18",
            "--stage179-warm-executor",
            "--mode",
            "live-real",
            "--runtime-profile",
            "production-live",
            "--order-scope",
            "live",
        ]
        stderr = StringIO()
        with patch.object(stage931, "run_once", return_value={}) as run_once:
            with patch.object(stage931, "run_serve") as run_serve:
                with patch.object(
                    stage931, "_build_stage179_warm_ctp_session"
                ) as build_ctp:
                    with redirect_stderr(stderr):
                        with self.assertRaisesRegex(SystemExit, "^2$"):
                            stage931.main(argv)

        run_once.assert_not_called()
        run_serve.assert_not_called()
        build_ctp.assert_not_called()
        self.assertIn(
            "error: --command=once does not permit --mode=live-real; "
            "production submission requires --command=serve",
            stderr.getvalue(),
        )

    def test_import_level_one_shot_live_real_stops_before_any_ctp_construction(self) -> None:
        args = SimpleNamespace(mode="live-real")
        with patch.object(stage931, "EventEngine") as event_engine:
            with patch.object(stage931, "MainEngine") as main_engine:
                with patch.object(
                    stage931, "_build_stage179_warm_ctp_session"
                ) as build_ctp:
                    with self.assertRaisesRegex(
                        stage931.RuntimeProfileError,
                        "^stage931_once_live_real_disabled_use_command_serve$",
                    ):
                        stage931.run_once(args)

        event_engine.assert_not_called()
        main_engine.assert_not_called()
        build_ctp.assert_not_called()

    def test_import_level_production_live_one_shot_cannot_bypass_serve(self) -> None:
        args = SimpleNamespace(
            command="once",
            mode="live-real",
            runtime_profile="production-live",
            order_scope="live",
            stage179_warm_executor=True,
        )
        with patch.object(stage931, "EventEngine") as event_engine:
            with patch.object(stage931, "MainEngine") as main_engine:
                with patch.object(
                    stage931, "_build_stage179_warm_ctp_session"
                ) as build_ctp:
                    with patch.object(
                        stage931, "reserve_execution_api_slots"
                    ) as reserve_slots:
                        with self.assertRaisesRegex(
                            stage931.RuntimeProfileError,
                            "^stage931_once_live_real_disabled_use_command_serve$",
                        ):
                            stage931.run_once(args)

        event_engine.assert_not_called()
        main_engine.assert_not_called()
        build_ctp.assert_not_called()
        reserve_slots.assert_not_called()

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

    def test_warm_production_live_policy_blocker_stops_before_ctp(self) -> None:
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
            blockers=("production_live_execution_profile_not_current_official",),
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
                        "production_live_execution_profile_not_current_official",
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
            "type": "FAK",
            "physical_tif_policy_version": "stage179_open_fak_v1",
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
