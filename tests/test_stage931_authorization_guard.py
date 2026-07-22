from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

from qmt_roll_official_live_execution_service import ExecutorServicePaths  # noqa: E402
from qmt_roll_official_live_runtime_profile import (  # noqa: E402
    ExecutionRuntimeProfile,
    OrderScope,
    resolve_runtime_profile,
)
from qmt_roll_official_live_submit_authorization import (  # noqa: E402
    publish_submit_authorization,
    submit_authorization_path,
)
import run_qmt_roll_stage931_official_live_ctp_submit_adapter as stage931  # noqa: E402


class Stage931AuthorizationGuardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        root = Path(self.tempdir.name)
        self.paths = ExecutorServicePaths.for_spool(
            spool_path=root / "state" / "intent_spool.sqlite3",
            ledger_path=root / "state" / "ledger.ndjson",
        )
        self.runtime = resolve_runtime_profile(
            profile=ExecutionRuntimeProfile.SIMNOW,
            order_scope=OrderScope.TEST,
            repo_root=ROOT,
            output_root=root / "runtime",
        )

    @staticmethod
    def _session_state(session: stage931.CtpExecutionSession) -> dict[str, object]:
        return next(
            cell.cell_contents
            for cell in session._send_order.__closure__ or ()
            if isinstance(cell.cell_contents, dict)
            and "intent_contexts" in cell.cell_contents
        )

    def _post_native_failure_harness(
        self,
    ) -> tuple[
        stage931.CtpExecutionSession,
        dict[str, object],
        SimpleNamespace,
        list[str],
    ]:
        session = stage931._build_stage179_warm_ctp_session(
            SimpleNamespace(target_date="2026-07-18", fill_wait_seconds=0),
            self.runtime,
            self.paths,
        )
        state = self._session_state(session)
        intent_id = "post-native-open-1"
        payload_sha256 = "a" * 64
        request = stage931.OrderRequest(
            symbol="JM609",
            exchange=stage931.Exchange.DCE,
            direction=stage931.Direction.SHORT,
            type=stage931.OrderType.FAK,
            volume=1,
            price=1245.5,
            offset=stage931.Offset.OPEN,
            reference="Stage905PhaseD:post-native-open-1",
        )
        lease = SimpleNamespace(
            intent=SimpleNamespace(
                intent_id=intent_id,
                payload_sha256=payload_sha256,
                intent_kind="open",
                source="stage901_pending_order",
                trace_id="trace-1",
                spool_sequence=1,
                state_revision=1,
                state="leased",
                state_generation="epoch-1:0",
                position_epoch_id="epoch-1",
                target_date="2026-07-18",
                deadline_epoch_ns=time.time_ns() + 60_000_000_000,
                lease_owner=session.service_generation,
                vt_symbol="JM609.DCE",
                payload={
                    "intent_role": "c9_initial_open",
                    "root_position_id": "root-1",
                    "position_cycle_id": "root-1:cycle0",
                },
            ),
            lease_token="lease-1",
        )
        state["authorization_pin"] = {
            "record": {"state_revision": 0},
            "record_digest": "f" * 64,
            "authorization_lane": "open",
            "intent_scope": "all",
            "spool_snapshot_digest": "b" * 64,
            "cursor_digest": "c" * 64,
            "stage902_evidence_digest": "d" * 64,
            "stage927_evidence_digest": "e" * 64,
        }
        state["intent_contexts"][intent_id] = {
            "requests": [request],
            "row": {},
            "fingerprint": "fingerprint-1",
        }
        native_calls: list[str] = []

        def send_order(_request: object, gateway_name: str) -> str:
            native_calls.append(gateway_name)
            state["native_insert_identity"] = {"vt_orderid": "CTP.1"}
            return "CTP.1"

        state["main_engine"] = SimpleNamespace(send_order=send_order)
        return session, state, lease, native_calls

    def _assert_post_native_failure_counted(
        self,
        session: stage931.CtpExecutionSession,
        lease: SimpleNamespace,
        native_calls: list[str],
    ) -> None:
        with self.assertRaises(stage931.BrokerSendBatchError) as raised:
            session._send_order(lease)

        self.assertEqual(["CTP"], native_calls)
        self.assertGreaterEqual(raised.exception.send_order_call_count, 1)
        self.assertIn(
            "stage179_post_native_processing_failed",
            str(raised.exception),
        )

    def test_post_native_audit_folding_exception_is_not_retryable_as_no_native(
        self,
    ) -> None:
        session, state, lease, native_calls = (
            self._post_native_failure_harness()
        )
        with (
            patch.object(stage931, "validate_submit_authorization", return_value=[]),
            patch.object(stage931, "append_execution_ledger_event"),
            patch.object(
                stage931,
                "_req_order_insert_audit_since",
                side_effect=RuntimeError("audit-fold-failed"),
            ),
        ):
            self._assert_post_native_failure_counted(
                session, lease, native_calls
            )
        self.assertEqual(["CTP.1"], sorted(state["reconciliation_pending_order_ids"]))

    def test_post_native_failure_is_side_effect_unknown_not_no_native_retry(
        self,
    ) -> None:
        raw_session, state, lease, native_calls = (
            self._post_native_failure_harness()
        )
        accounting_session = stage931.CtpExecutionSession.for_callbacks(
            runtime=self.runtime,
            service_generation="accounting-service-1",
            official_version="official-test",
            capital=150_000.0,
            readiness_ttl_seconds=30.0,
            connect_startup_bundle=lambda: {"ready": True},
            disconnect_transport=lambda: None,
            fresh_bundle=lambda *_: (),
            reserve_api_slot=lambda *_: "batch-slot-1",
            send_order=raw_session._send_order,
        )
        accounting_session.connect()

        with (
            patch.object(stage931, "validate_submit_authorization", return_value=[]),
            patch.object(stage931, "append_execution_ledger_event"),
            patch.object(
                stage931,
                "_req_order_insert_audit_since",
                side_effect=RuntimeError("audit-fold-failed"),
            ),
        ):
            result = accounting_session.execute_spool_lease(
                lease=lease,
                hard_deadline_monotonic=time.monotonic() + 20.0,
                api_slot_durable=lambda _: True,
            )

        self.assertEqual(["CTP"], native_calls)
        self.assertEqual("side_effect_unknown", result.disposition)
        self.assertNotEqual("no_side_effect_retryable", result.disposition)
        self.assertEqual(1, result.send_order_call_count)
        self.assertEqual(1, accounting_session.send_order_call_count)
        self.assertEqual(["CTP.1"], sorted(state["reconciliation_pending_order_ids"]))

    def test_post_native_callback_rebind_exception_is_not_retryable_as_no_native(
        self,
    ) -> None:
        session, state, lease, native_calls = (
            self._post_native_failure_harness()
        )
        state["rows"]["orders"].append({"vt_orderid": "CTP.1"})
        with (
            patch.object(stage931, "validate_submit_authorization", return_value=[]),
            patch.object(stage931, "append_execution_ledger_event"),
            patch.object(
                stage931,
                "_persist_stage179_warm_broker_callback",
                side_effect=RuntimeError("callback-rebind-failed"),
            ),
        ):
            self._assert_post_native_failure_counted(
                session, lease, native_calls
            )
        self.assertEqual(["CTP.1"], sorted(state["reconciliation_pending_order_ids"]))

    def test_post_native_cancel_schedule_exception_is_not_retryable_as_no_native(
        self,
    ) -> None:
        session, state, lease, native_calls = (
            self._post_native_failure_harness()
        )
        with (
            patch.object(stage931, "validate_submit_authorization", return_value=[]),
            patch.object(stage931, "append_execution_ledger_event"),
            patch.object(
                stage931.Thread,
                "start",
                side_effect=RuntimeError("cancel-schedule-failed"),
            ),
        ):
            self._assert_post_native_failure_counted(
                session, lease, native_calls
            )
        self.assertEqual(["CTP.1"], sorted(state["reconciliation_pending_order_ids"]))

    def test_exact_pin_survives_admission_ttl_but_not_revision_or_guard(self) -> None:
        args = SimpleNamespace(target_date="2026-07-18")
        session = stage931._build_stage179_warm_ctp_session(
            args,
            self.runtime,
            self.paths,
        )
        state = self._session_state(session)
        state["connection_generation"] = "connection-1"
        issued_ns = time.time_ns()
        expires_ns = issued_ns + 30_000_000_000
        deadline_ns = issued_ns + 60_000_000_000
        authorization_path = submit_authorization_path(
            self.runtime.output_root
        )
        publish_submit_authorization(
            path=authorization_path,
            target_date="2026-07-18",
            execution_profile="c9-15w",
            runtime_profile="simnow",
            order_scope="test",
            service_generation=session.service_generation,
            connection_generation="connection-1",
            cycle_id="cycle-auth-1",
            intent_scope="all",
            authorized_intents=[
                {
                    "intent_id": "initial-open-1",
                    "payload_sha256": "a" * 64,
                    "intent_kind": "open",
                    "source": "stage901_pending_order",
                    "intent_role": "c9_initial_open",
                    "trace_id": "trace-1",
                    "spool_sequence": 11,
                    "state_revision": 5,
                    "state_generation": "epoch-1:0",
                    "position_epoch_id": "epoch-1",
                    "root_position_id": "root-1",
                    "position_cycle_id": "root-1:cycle0",
                    "deadline_epoch_ns": deadline_ns,
                }
            ],
            issued_epoch_ns=issued_ns,
            expires_epoch_ns=expires_ns,
            controller_evidence={
                "target_date": "2026-07-18",
                "controller_status": (
                    "phase_d_controller_live_real_ready_no_submit_step"
                ),
                "stage905_executor_status": "executor_dry_run_ready",
                "stage905_blocked_count": 0,
                "stage905_ready_count": 1,
                "expires_epoch_ns": expires_ns,
            },
            stage927_evidence={
                "real_submit_permitted": 1,
                "expires_epoch_ns": expires_ns,
            },
            broker_gate_evidence={
                "status": "ready",
                "service_generation": session.service_generation,
                "connection_generation": "connection-1",
                "expires_epoch_ns": expires_ns,
            },
            tick_watermark_evidence={
                "all_symbols_ready": 1,
                "expires_epoch_ns": expires_ns,
            },
            spool_path=self.paths.spool_path,
            spool_snapshot_digest="b" * 64,
            cursor_digest="c" * 64,
            stage902_evidence_digest="d" * 64,
            stage927_evidence_digest="e" * 64,
        )
        lease = SimpleNamespace(
            intent=SimpleNamespace(
                intent_id="initial-open-1",
                payload_sha256="a" * 64,
                intent_kind="open",
                source="stage901_pending_order",
                trace_id="trace-1",
                spool_sequence=11,
                state_revision=6,
                state="leased",
                state_generation="epoch-1:0",
                position_epoch_id="epoch-1",
                target_date="2026-07-18",
                deadline_epoch_ns=deadline_ns,
                lease_owner=session.service_generation,
                payload={
                    "intent_role": "c9_initial_open",
                    "root_position_id": "root-1",
                    "position_cycle_id": "root-1:cycle0",
                },
            ),
            lease_token="lease-1",
        )

        with session.lease_execution_guard():
            self.assertEqual([], session.pre_lease_blockers())
            self.assertEqual(
                {"initial-open-1": "a" * 64},
                session.pre_lease_authorized_intents(),
            )
            self.assertEqual([], session.post_lease_blockers(lease))
            wrong_revision = SimpleNamespace(
                intent=SimpleNamespace(
                    **vars(lease.intent) | {"state_revision": 7}
                ),
                lease_token="lease-2",
            )
            self.assertIn(
                "stage179_submit_authorization_leased_state_revision_mismatch",
                session.post_lease_blockers(wrong_revision),
            )
            with patch.object(
                stage931.time,
                "time_ns",
                return_value=expires_ns + 1,
            ):
                self.assertEqual([], session.post_lease_blockers(lease))

        self.assertEqual(
            ["stage179_submit_authorization_pin_missing"],
            session.post_lease_blockers(lease),
        )

    def test_traced_stage901_open_allows_generic_provenance_only(self) -> None:
        target_date = "2026-07-18"
        vt_symbol = "JM609.DCE"
        root_position_id = stage931.generate_root_position_id(
            target_date=target_date,
            vt_symbol=vt_symbol,
            direction="short",
        )
        position_cycle_id = stage931.generate_position_cycle_id(
            root_position_id=root_position_id,
            cycle_no=0,
        )
        generic_provenance = {
            "trace_json": json.dumps({"trace_id": "trace-1"}),
            "trace_id": "trace-1",
            "source_feed_session_id": "feed-1",
            "source_ingress_sequence": 1,
            "source_symbol_sequence": 1,
            "ingress_epoch_ns": 1_000_000_000,
            "ingress_monotonic_ns": 2_000_000_000,
            "deadline_epoch_ns": 26_000_000_000,
            "deadline_monotonic_ns": 27_000_000_000,
            "durable_cursor_feed_session_id": "feed-1",
            "durable_cursor_ingress_sequence": 1,
            "durable_cursor_journal_byte_offset": 128,
            "durable_cursor_journal_schema": "framed-v1",
            "state_generation": "epoch-1:0",
        }
        payload = {
            "intent_id": "STAGE905-PENDING-TRACE",
            "target_date": target_date,
            "source": "stage901_pending_order",
            "symbol": "JM609",
            "exchange": "DCE",
            "direction": stage931.Direction.SHORT.value,
            "type": stage931.OrderType.FAK.value,
            "physical_tif_policy_version": "stage179_open_fak_v1",
            "volume": 1,
            "price": 1245.5,
            "offset": stage931.Offset.OPEN.value,
            "reference": "Stage905PhaseD:STAGE905-PENDING-TRACE",
            "gateway_name": "CTP",
            "vt_symbol": vt_symbol,
            "root_position_id": root_position_id,
            "position_cycle_id": position_cycle_id,
            "position_cycle_no": 0,
            "position_epoch_id": "epoch-1",
            "intent_role": "c9_initial_open",
            **generic_provenance,
        }
        row = {
            "intent_id": payload["intent_id"],
            "target_date": target_date,
            "source": payload["source"],
            "symbol": payload["symbol"],
            "exchange": payload["exchange"],
            "direction": "short",
            "offset": "open",
            "planned_volume": 1,
            "order_request_price": 1245.5,
            "order_request_volume": 1,
            "vt_symbol": vt_symbol,
            "root_position_id": root_position_id,
            "position_cycle_id": position_cycle_id,
            "position_cycle_no": 0,
            "position_epoch_id": "epoch-1",
            "intent_role": "c9_initial_open",
            "executor_status": "dry_run_order_request_payload_ready",
            "order_request_json": json.dumps(payload, sort_keys=True),
            **generic_provenance,
        }

        self.assertEqual(
            [],
            stage931._stage905_ready_intent_artifact_blockers(
                pd.DataFrame([row])
            ),
        )
        contaminated_payload = {**payload, "action_id": "stage904-action"}
        contaminated_row = {
            **row,
            "action_id": "stage904-action",
            "order_request_json": json.dumps(
                contaminated_payload,
                sort_keys=True,
            ),
        }
        blockers = stage931._stage905_ready_intent_artifact_blockers(
            pd.DataFrame([contaminated_row])
        )
        self.assertTrue(
            any(
                blocker.startswith(
                    "stage905_initial_open_stage904_lineage_forbidden:"
                    "STAGE905-PENDING-TRACE:"
                )
                and "action_id" in blocker
                for blocker in blockers
            ),
            blockers,
        )


if __name__ == "__main__":
    unittest.main()
