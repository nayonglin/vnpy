from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock


os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import run_ctp_stage174_readonly_probe as stage174


class _TrackingRLock:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.thread_ids: set[int] = set()
        self.acquire_count = 0

    def __enter__(self) -> "_TrackingRLock":
        self.acquire()
        return self

    def __exit__(self, *_args: object) -> None:
        self.release()

    def acquire(self) -> bool:
        self.thread_ids.add(threading.get_ident())
        self.acquire_count += 1
        return self._lock.acquire()

    def release(self) -> None:
        self._lock.release()


class Stage174ReadonlyQueryBundleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.generation = "11111111-2222-4333-8444-555555555555"
        self.module = SimpleNamespace(
            EXCHANGE_CTP2VT={"DCE": "DCE"},
            DIRECTION_CTP2VT={"1": "short", "0": "long"},
            OFFSET_CTP2VT={"0": "open", "1": "close"},
            STATUS_CTP2VT={"0": "all_traded"},
        )

    def raw_order(self, **overrides: object) -> dict:
        row = {
            "BrokerID": "9999",
            "InvestorID": "00001234",
            "TradingDay": "20260713",
            "InstrumentID": "JM609",
            "ExchangeID": "DCE",
            "Direction": "1",
            "CombOffsetFlag": "0",
            "LimitPrice": 1246.0,
            "VolumeTotalOriginal": 1,
            "VolumeTraded": 1,
            "OrderStatus": "0",
            "FrontID": 11,
            "SessionID": 22,
            "OrderRef": "33",
            "OrderSysID": "  SYS-1  ",
            "InsertDate": "20260713",
            "InsertTime": "09:00:00",
        }
        row.update(overrides)
        return row

    def raw_trade(self, **overrides: object) -> dict:
        row = {
            "BrokerID": "9999",
            "InvestorID": "00001234",
            "TradingDay": "20260713",
            "TradeDate": "20260713",
            "TradeTime": "09:00:01",
            "InstrumentID": "JM609",
            "ExchangeID": "DCE",
            "Direction": "1",
            "OffsetFlag": "0",
            "Price": 1246.0,
            "Volume": 1,
            "TradeID": "T-1",
            "OrderSysID": "SYS-1",
        }
        row.update(overrides)
        return row

    def raw_position(self, **overrides: object) -> dict:
        row = {
            "BrokerID": "9999",
            "InvestorID": "00001234",
            "TradingDay": "20260713",
            "InstrumentID": "JM609",
            "ExchangeID": "DCE",
            "PosiDirection": "1",
            "Position": 1,
            "TodayPosition": 1,
            "YdPosition": 0,
            "PositionProfit": 12.5,
            "LongFrozen": 0,
            "ShortFrozen": 0,
        }
        row.update(overrides)
        return row

    def test_reqid_bound_last_and_zero_error_are_required(self) -> None:
        callbacks = [
            {"reqid": 99, "has_data": True, "last": True, "error_id": 0, "received_at": "2026-07-13T09:00:00+08:00"},
            {"reqid": 101, "has_data": True, "last": False, "error_id": 0, "received_at": "2026-07-13T09:00:02+08:00"},
            {"reqid": 101, "has_data": False, "last": True, "error_id": 0, "received_at": "2026-07-13T09:00:03+08:00"},
        ]

        state = stage174._query_callback_state(
            callbacks,
            expected_reqid=101,
            request_return_code=0,
            request_sent_at="2026-07-13T09:00:01+08:00",
        )

        self.assertTrue(state["complete"])
        self.assertEqual(2, state["callback_count"])
        self.assertEqual(1, state["data_callback_count"])

        callbacks[-1]["error_id"] = 7
        failed = stage174._query_callback_state(
            callbacks,
            expected_reqid=101,
            request_return_code=0,
            request_sent_at="2026-07-13T09:00:01+08:00",
        )
        self.assertFalse(failed["complete"])
        self.assertEqual(1, failed["error_rows"])

    def test_trade_joins_queried_order_sysid_to_stable_vt_orderid(self) -> None:
        orders, trades, status = stage174._normalize_query_bundle_rows(
            [self.raw_order()],
            [self.raw_trade()],
            generation_uuid=self.generation,
            ctp_gateway_module=self.module,
        )

        self.assertEqual("CTP.11_22_33", orders[0]["vt_orderid"])
        self.assertEqual("CTP.11_22_33", trades[0]["vt_orderid"])
        self.assertEqual("joined_unique_order_sys_id", trades[0]["order_mapping_status"])
        self.assertTrue(trades[0]["broker_trade_identity"].endswith(":T-1"))
        self.assertTrue(status["trade_order_join_complete"])
        self.assertTrue(status["trade_identity_complete"])

    def test_missing_order_sysid_mapping_fails_bundle_join(self) -> None:
        _, trades, status = stage174._normalize_query_bundle_rows(
            [self.raw_order()],
            [self.raw_trade(OrderSysID="missing")],
            generation_uuid=self.generation,
            ctp_gateway_module=self.module,
        )

        self.assertEqual("", trades[0]["vt_orderid"])
        self.assertEqual(0, trades[0]["order_mapping_complete"])
        self.assertFalse(status["trade_order_join_complete"])

    def test_ambiguous_order_sysid_mapping_fails_closed(self) -> None:
        duplicate = self.raw_order(FrontID=44, SessionID=55, OrderRef="66")
        _, trades, status = stage174._normalize_query_bundle_rows(
            [self.raw_order(), duplicate],
            [self.raw_trade()],
            generation_uuid=self.generation,
            ctp_gateway_module=self.module,
        )

        self.assertEqual("", trades[0]["vt_orderid"])
        self.assertFalse(status["trade_order_join_complete"])

    def test_atomic_csv_hash_binds_exact_published_bytes(self) -> None:
        rows = [{"query_generation_uuid": self.generation, "value": 1}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "orders.csv"
            frame = stage174._atomic_write_df(path, rows)
            first = stage174._sha256_path(path)
            stage174._atomic_write_df(path, rows + [{"query_generation_uuid": self.generation, "value": 2}])
            second = stage174._sha256_path(path)

        self.assertEqual(1, len(frame))
        self.assertEqual(64, len(first))
        self.assertNotEqual(first, second)

    def test_account_fingerprint_preserves_leading_zero_identity(self) -> None:
        first = stage174._account_fingerprint("9999", "00001234")
        second = stage174._account_fingerprint("9999", "1234")

        self.assertEqual(64, len(first))
        self.assertNotEqual(first, second)

    def test_positions_are_aggregated_from_only_the_bound_generation(self) -> None:
        positions, status = stage174._normalize_queried_positions(
            [self.raw_position(), self.raw_position(Position=2, TodayPosition=0, YdPosition=2)],
            generation_uuid=self.generation,
            broker_trading_day="20260713",
            ctp_gateway_module=self.module,
        )

        self.assertEqual(1, len(positions))
        self.assertEqual(3.0, positions[0]["volume"])
        self.assertEqual(2, positions[0]["source_row_count"])
        self.assertEqual(self.generation, positions[0]["query_generation_uuid"])
        self.assertEqual("00001234", positions[0]["account_id"])
        self.assertTrue(status["position_normalization_complete"])
        self.assertEqual(2, status["position_raw_row_count"])
        self.assertEqual(1, status["position_normalized_row_count"])

    def test_position_without_stable_exchange_identity_fails_closed(self) -> None:
        positions, status = stage174._normalize_queried_positions(
            [self.raw_position(ExchangeID="")],
            generation_uuid=self.generation,
            broker_trading_day="20260713",
            ctp_gateway_module=self.module,
        )

        self.assertEqual([], positions)
        self.assertFalse(status["position_normalization_complete"])
        self.assertEqual(1, status["position_invalid_row_count"])

    def test_readonly_order_firewall_blocks_gateway_and_td_api_calls(self) -> None:
        calls: list[str] = []

        class FakeGateway:
            def send_order(self, *args: object, **kwargs: object) -> str:
                calls.append("gateway_send")
                return "sent"

            def cancel_order(self, *args: object, **kwargs: object) -> str:
                calls.append("gateway_cancel")
                return "cancelled"

        class FakeTdApi:
            def send_order(self, *args: object, **kwargs: object) -> str:
                calls.append("td_send")
                return "sent"

            def cancel_order(self, *args: object, **kwargs: object) -> str:
                calls.append("td_cancel")
                return "cancelled"

            def reqOrderInsert(self, *args: object, **kwargs: object) -> int:
                calls.append("native_order_insert")
                return 0

            def reqOrderAction(self, *args: object, **kwargs: object) -> int:
                calls.append("native_order_action")
                return 0

        counters = stage174._new_order_api_counters()
        originals = stage174._install_readonly_order_api_firewall(
            FakeGateway,
            FakeTdApi,
            counters,
        )
        try:
            for instance, method_name in (
                (FakeGateway(), "send_order"),
                (FakeGateway(), "cancel_order"),
                (FakeTdApi(), "send_order"),
                (FakeTdApi(), "cancel_order"),
            ):
                with self.assertRaisesRegex(RuntimeError, "readonly_order_api_blocked"):
                    getattr(instance, method_name)(object())
            for method_name in ("reqOrderInsert", "reqOrderAction"):
                with self.assertRaisesRegex(
                    RuntimeError, "readonly_native_ctp_mutation_blocked"
                ):
                    getattr(FakeTdApi(), method_name)({}, 1)
        finally:
            stage174._restore_readonly_order_api_firewall(
                FakeGateway,
                FakeTdApi,
                originals,
            )

        self.assertEqual([], calls)
        self.assertEqual(2, counters["send_order_api_attempted_count"])
        self.assertEqual(2, counters["cancel_order_api_attempted_count"])
        self.assertEqual(0, counters["send_order_api_called_count"])
        self.assertEqual(0, counters["cancel_order_api_called_count"])
        self.assertEqual(2, counters["native_mutation_api_attempted_count"])
        self.assertEqual(0, counters["native_mutation_api_called_count"])
        self.assertEqual("sent", FakeGateway().send_order(object()))
        self.assertEqual("cancelled", FakeTdApi().cancel_order(object()))
        self.assertEqual(0, FakeTdApi().reqOrderInsert({}, 1))

    def test_bound_firewall_wrapper_cannot_mutate_frozen_evidence_window(self) -> None:
        calls: list[str] = []

        class FakeGateway:
            def send_order(self, *args: object, **kwargs: object) -> str:
                calls.append("gateway_send")
                return "sent"

            def cancel_order(self, *args: object, **kwargs: object) -> None:
                calls.append("gateway_cancel")

        class FakeTdApi(FakeGateway):
            pass

        counters = stage174._new_order_api_counters()
        state_lock = threading.RLock()
        evidence_window = stage174._new_order_api_evidence_window()
        originals = stage174._install_readonly_order_api_firewall(
            FakeGateway,
            FakeTdApi,
            counters,
            state_lock,
            evidence_window,
        )
        bound_wrapper = FakeTdApi().send_order
        stage174._restore_readonly_order_api_firewall(
            FakeGateway, FakeTdApi, originals
        )
        closed = stage174._close_order_api_evidence_window(
            state_lock, evidence_window
        )
        frozen_counters = dict(counters)

        with self.assertRaisesRegex(
            RuntimeError, "readonly_order_api_blocked_after_evidence_window"
        ):
            bound_wrapper(object())

        self.assertEqual([], calls)
        self.assertEqual(frozen_counters, counters)
        self.assertEqual(1, closed["closed"])
        self.assertIs(type(closed["closed_epoch_ns"]), int)

    def test_dry_run_publishes_exact_zero_order_api_counters(self) -> None:
        result = stage174._run_probe(connect=False, wait_seconds=1)

        for field in (
            "send_order_api_attempted_count",
            "cancel_order_api_attempted_count",
            "send_order_api_called_count",
            "cancel_order_api_called_count",
            "native_mutation_api_attempted_count",
            "native_mutation_api_called_count",
            "order_api_attempted_count",
            "order_api_called_count",
        ):
            self.assertIs(type(result[field]), int)
            self.assertEqual(0, result[field])

    def test_native_ctp_mutation_firewall_covers_every_non_readonly_surface(self) -> None:
        from vnpy_ctp.gateway.ctp_gateway import CtpTdApi

        allowed_session_or_readonly_requests = {
            "reqAuthenticate",
            "reqGenUserCaptcha",
            "reqGenUserText",
            "reqQueryBankAccountMoneyByFuture",
            "reqQueryCFMMCTradingAccountToken",
            "reqSettlementInfoConfirm",
            "reqUserAuthMethod",
            "reqUserLogin",
            "reqUserLoginWithCaptcha",
            "reqUserLoginWithOTP",
            "reqUserLoginWithText",
            "reqUserLogout",
        }
        non_query_requests = {
            name
            for name in dir(CtpTdApi)
            if name.startswith("req") and not name.startswith("reqQry")
        }
        mutation_surfaces = (
            non_query_requests - allowed_session_or_readonly_requests
        )

        self.assertEqual(
            set(stage174.NATIVE_CTP_MUTATION_METHODS), mutation_surfaces
        )

    def test_reconnect_proof_requires_fresh_queries_on_new_generation(self) -> None:
        lifecycle = {
            "disconnect_observed": 1,
            "reconnect_observed": 1,
            "old_connection_generation": "old",
            "new_connection_generation": "new",
            "readiness_revoked_epoch_ns": 10,
        }
        queries = {
            name: {"connection_generation": "new"}
            for name in ("orders", "trades", "positions")
        }

        proof = stage174._finalize_connection_lifecycle(
            lifecycle,
            query_requests=queries,
            query_bundle_complete=True,
            order_api_counters=stage174._new_order_api_counters(),
            restored_epoch_ns=20,
        )
        stale = stage174._finalize_connection_lifecycle(
            lifecycle,
            query_requests={**queries, "positions": {"connection_generation": "old"}},
            query_bundle_complete=True,
            order_api_counters=stage174._new_order_api_counters(),
            restored_epoch_ns=20,
        )

        self.assertEqual(1, proof["one_shot_query_proof_complete"])
        self.assertEqual(0, proof["proof_complete"])
        self.assertIn(
            "authoritative_current_generation_readiness_transition_missing",
            proof["proof_blockers"],
        )
        self.assertIsNone(proof["readiness_restored_epoch_ns"])
        self.assertEqual(0, stale["proof_complete"])
        self.assertIsNone(stale["readiness_restored_epoch_ns"])

    def test_authoritative_reconnect_requires_full_snapshot_and_real_readiness_transition(self) -> None:
        lifecycle = {
            "model_tag": "stage174_ctp_connection_lifecycle_v2",
            "disconnect_observed": 1,
            "reconnect_observed": 1,
            "old_connection_generation": "old",
            "new_connection_generation": "new",
            "current_connection_generation": "new",
            "readiness_generation_before_disconnect": "old",
            "readiness_generation": "new",
            "readiness_was_ready_before_disconnect": 1,
            "readiness_revoked_epoch_ns": 10,
            "reconnect_connected_epoch_ns": 15,
            "readiness_restored_epoch_ns": 20,
            "snapshot_connection_generations": {
                name: "new"
                for name in (
                    "settlement",
                    "account",
                    "contracts",
                    "orders",
                    "trades",
                    "positions",
                )
            },
        }
        queries = {
            name: {"connection_generation": "new"}
            for name in ("orders", "trades", "positions")
        }

        proof = stage174._finalize_connection_lifecycle(
            lifecycle,
            query_requests=queries,
            query_bundle_complete=True,
            order_api_counters=stage174._new_order_api_counters(),
            restored_epoch_ns=999,
        )

        self.assertEqual(1, proof["authoritative_readiness_transition_complete"])
        self.assertEqual(1, proof["full_snapshot_generation_complete"])
        self.assertEqual(1, proof["proof_complete"])
        self.assertEqual(20, proof["readiness_restored_epoch_ns"])
        self.assertTrue(proof["disconnect_evidence_id"])

    def test_authoritative_reconnect_fails_without_contract_snapshot_on_new_generation(self) -> None:
        lifecycle = {
            "model_tag": "stage174_ctp_connection_lifecycle_v2",
            "disconnect_observed": 1,
            "reconnect_observed": 1,
            "old_connection_generation": "old",
            "new_connection_generation": "new",
            "current_connection_generation": "new",
            "readiness_generation_before_disconnect": "old",
            "readiness_generation": "new",
            "readiness_was_ready_before_disconnect": 1,
            "readiness_revoked_epoch_ns": 10,
            "reconnect_connected_epoch_ns": 15,
            "readiness_restored_epoch_ns": 20,
            "snapshot_connection_generations": {
                "settlement": "new",
                "account": "new",
                "contracts": "old",
                "orders": "new",
                "trades": "new",
                "positions": "new",
            },
        }
        queries = {
            name: {"connection_generation": "new"}
            for name in ("orders", "trades", "positions")
        }

        proof = stage174._finalize_connection_lifecycle(
            lifecycle,
            query_requests=queries,
            query_bundle_complete=True,
            order_api_counters=stage174._new_order_api_counters(),
            restored_epoch_ns=999,
        )

        self.assertEqual(0, proof["full_snapshot_generation_complete"])
        self.assertEqual(0, proof["proof_complete"])
        self.assertIn("full_current_generation_snapshot_missing", proof["proof_blockers"])

    def test_authoritative_reconnect_fails_when_disconnect_happened_before_ready(self) -> None:
        lifecycle = {
            "model_tag": "stage174_ctp_connection_lifecycle_v2",
            "disconnect_observed": 1,
            "reconnect_observed": 1,
            "old_connection_generation": "old",
            "new_connection_generation": "new",
            "current_connection_generation": "new",
            "readiness_generation_before_disconnect": "",
            "readiness_generation": "new",
            "readiness_was_ready_before_disconnect": 0,
            "readiness_revoked_epoch_ns": 10,
            "reconnect_connected_epoch_ns": 15,
            "readiness_restored_epoch_ns": 20,
            "snapshot_connection_generations": {
                name: "new"
                for name in (
                    "settlement",
                    "account",
                    "contracts",
                    "orders",
                    "trades",
                    "positions",
                )
            },
        }
        queries = {
            name: {"connection_generation": "new"}
            for name in ("orders", "trades", "positions")
        }

        proof = stage174._finalize_connection_lifecycle(
            lifecycle,
            query_requests=queries,
            query_bundle_complete=True,
            order_api_counters=stage174._new_order_api_counters(),
            restored_epoch_ns=999,
        )

        self.assertEqual(0, proof["authoritative_readiness_transition_complete"])
        self.assertEqual(0, proof["proof_complete"])
        self.assertIn("authoritative_readiness_transition_missing", proof["proof_blockers"])

    def test_runtime_lifecycle_helpers_revoke_and_restore_full_snapshot_readiness(self) -> None:
        lifecycle = stage174._new_connection_lifecycle()
        stage174._record_front_connected(
            lifecycle, generation="old", epoch_ns=5
        )
        stage174._record_snapshot_readiness(
            lifecycle,
            generation="old",
            snapshot_generations={
                name: "old" for name in stage174.FULL_READINESS_SNAPSHOT_COMPONENTS
            },
            epoch_ns=8,
        )
        stage174._record_front_disconnected(
            lifecycle, reason=4097, epoch_ns=10
        )
        stage174._record_front_connected(
            lifecycle, generation="new", epoch_ns=15
        )
        stage174._record_snapshot_readiness(
            lifecycle,
            generation="new",
            snapshot_generations={
                name: "new" for name in stage174.FULL_READINESS_SNAPSHOT_COMPONENTS
            },
            epoch_ns=20,
        )

        self.assertEqual("stage174_ctp_connection_lifecycle_v2", lifecycle["model_tag"])
        self.assertEqual("old", lifecycle["readiness_generation_before_disconnect"])
        self.assertEqual(1, lifecycle["readiness_was_ready_before_disconnect"])
        self.assertEqual(10, lifecycle["readiness_revoked_epoch_ns"])
        self.assertEqual(15, lifecycle["reconnect_connected_epoch_ns"])
        self.assertEqual("new", lifecycle["readiness_generation"])
        self.assertEqual(20, lifecycle["readiness_restored_epoch_ns"])

    def test_runtime_lifecycle_does_not_claim_revocation_before_first_readiness(self) -> None:
        lifecycle = stage174._new_connection_lifecycle()
        stage174._record_front_connected(
            lifecycle, generation="old", epoch_ns=5
        )
        stage174._record_front_disconnected(
            lifecycle, reason=4097, epoch_ns=10
        )

        self.assertEqual(0, lifecycle["readiness_was_ready_before_disconnect"])
        self.assertEqual("", lifecycle["readiness_generation_before_disconnect"])
        self.assertIsNone(lifecycle["readiness_revoked_epoch_ns"])

    def test_mocked_ctp_slow_callbacks_rebuild_full_snapshot_after_reconnect(self) -> None:
        import vnpy_ctp
        from vnpy_ctp.gateway import ctp_gateway as ctp_gateway_module

        timers: list[threading.Timer] = []
        state_lock = _TrackingRLock()

        class FakeEventEngine:
            def register(self, *args: object) -> None:
                return None

            def unregister(self, *args: object) -> None:
                return None

        class FakeTdApi:
            def __init__(self) -> None:
                self.reqid = 0
                self.login_status = False
                self.contract_inited = False
                self.brokerid = "9999"
                self.userid = "00001234"
                self.contract_query_count = 0
                self.position_query_count = 0

            def _later(self, delay: float, callback: object) -> None:
                timer = threading.Timer(delay, callback)
                timer.daemon = True
                timers.append(timer)
                timer.start()

            def onFrontConnected(self) -> None:
                self.login_status = True
                self.reqid += 1
                reqid = self.reqid
                self.reqSettlementInfoConfirm({}, reqid)
                self.onRspSettlementInfoConfirm({}, {"ErrorID": 0}, reqid, True)

            def onFrontDisconnected(self, reason: int) -> None:
                self.login_status = False

            def reqSettlementInfoConfirm(self, request: dict, reqid: int) -> int:
                return 0

            def onRspSettlementInfoConfirm(
                self, data: dict, error: dict, reqid: int, last: bool
            ) -> None:
                return None

            def onRspQryOrder(
                self, data: dict, error: dict, reqid: int, last: bool
            ) -> None:
                return None

            def onRspQryTrade(
                self, data: dict, error: dict, reqid: int, last: bool
            ) -> None:
                return None

            def onRspQryInvestorPosition(
                self, data: dict, error: dict, reqid: int, last: bool
            ) -> None:
                return None

            def onRspQryTradingAccount(
                self, data: dict, error: dict, reqid: int, last: bool
            ) -> None:
                return None

            def onRspQryInstrument(
                self, data: dict, error: dict, reqid: int, last: bool
            ) -> None:
                if last:
                    self.contract_inited = True

            def reqQryOrder(self, request: dict, reqid: int) -> int:
                self._later(
                    0.01,
                    lambda: self.onRspQryOrder(
                        {}, {"ErrorID": 0}, reqid, True
                    ),
                )
                return 0

            def reqQryTrade(self, request: dict, reqid: int) -> int:
                self._later(
                    0.01,
                    lambda: self.onRspQryTrade(
                        {}, {"ErrorID": 0}, reqid, True
                    ),
                )
                return 0

            def reqQryInvestorPosition(self, request: dict, reqid: int) -> int:
                self.position_query_count += 1
                self._later(
                    3.2 if self.position_query_count == 1 else 0.05,
                    lambda: self.onRspQryInvestorPosition(
                        {}, {"ErrorID": 0}, reqid, True
                    ),
                )
                return 0

            def reqQryTradingAccount(self, request: dict, reqid: int) -> int:
                data = {
                    "BrokerID": "9999",
                    "InvestorID": "00001234",
                    "AccountID": "00001234",
                }
                self._later(
                    0.01,
                    lambda: self.onRspQryTradingAccount(
                        data, {"ErrorID": 0}, reqid, True
                    ),
                )
                return 0

            def reqQryInstrument(self, request: dict, reqid: int) -> int:
                self.contract_query_count += 1
                query_count = self.contract_query_count
                data = {"InstrumentID": "JM9999", "ProductClass": "1"}
                self._later(
                    0.01,
                    lambda: self.onRspQryInstrument(
                        data, {"ErrorID": 0}, reqid, True
                    ),
                )
                if query_count == 1:
                    self._later(0.08, lambda: self.onFrontDisconnected(4097))
                    self._later(0.10, self.onFrontConnected)
                return 0

            def getTradingDay(self) -> str:
                return "20260719"

            def send_order(self, *args: object, **kwargs: object) -> str:
                return ""

            def cancel_order(self, *args: object, **kwargs: object) -> None:
                return None

        class FakeGateway:
            def __init__(self) -> None:
                self.td_api = FakeTdApi()

            def process_timer_event(self, event: object) -> None:
                return None

            def send_order(self, *args: object, **kwargs: object) -> str:
                return ""

            def cancel_order(self, *args: object, **kwargs: object) -> None:
                return None

        class FakeMainEngine:
            def __init__(self, event_engine: object) -> None:
                self.gateway: FakeGateway | None = None

            def add_gateway(self, gateway_class: type) -> None:
                self.gateway = gateway_class()

            def connect(self, setting: dict, gateway_name: str) -> None:
                assert self.gateway is not None
                self.gateway.td_api.onFrontConnected()

            def get_gateway(self, gateway_name: str) -> FakeGateway:
                assert self.gateway is not None
                return self.gateway

            def close(self) -> None:
                assert self.gateway is not None
                self.gateway.td_api.onFrontDisconnected(0)

        env = {
            "CTP_USERID": "00001234",
            "CTP_PASSWORD": "secret",
            "CTP_BROKERID": "9999",
            "CTP_TD_ADDRESS": "tcp://127.0.0.1:1",
            "CTP_MD_ADDRESS": "tcp://127.0.0.1:2",
            "CTP_APPID": "app",
            "CTP_AUTH_CODE": "auth",
            "CTP_PRODUCT_INFO": "",
        }
        with (
            mock.patch.object(stage174, "EventEngine", FakeEventEngine),
            mock.patch.object(stage174, "MainEngine", FakeMainEngine),
            mock.patch.object(vnpy_ctp, "CtpGateway", FakeGateway),
            mock.patch.object(ctp_gateway_module, "CtpTdApi", FakeTdApi),
            mock.patch.object(
                stage174,
                "_gateway_import_status",
                return_value={"ctp_gateway_import_available": True},
            ),
            mock.patch.object(stage174, "_required_env_missing", return_value=[]),
            mock.patch.object(stage174, "_debug_report", return_value=None),
            mock.patch.object(
                stage174,
                "_new_probe_state_lock",
                return_value=state_lock,
            ),
            mock.patch.dict(os.environ, env, clear=False),
        ):
            result = stage174._run_probe(
                connect=True,
                wait_seconds=8,
                observe_reconnect=True,
                query_flow_gap_seconds=0.001,
            )

        for timer in timers:
            timer.join(timeout=0.5)
        lifecycle = result["connection_lifecycle"]
        self.assertEqual(1, lifecycle["proof_complete"])
        self.assertEqual(1, lifecycle["full_snapshot_generation_complete"])
        self.assertEqual(1, lifecycle["authoritative_readiness_transition_complete"])
        self.assertNotEqual(
            lifecycle["old_connection_generation"],
            lifecycle["new_connection_generation"],
        )
        self.assertTrue(result["broker_query_bundle"]["complete"])
        self.assertEqual(0, result["order_api_called_count"])
        self.assertEqual(0, result["native_mutation_api_called_count"])
        self.assertEqual(
            "threading_rlock_v1", lifecycle["state_synchronization"]
        )
        self.assertGreater(state_lock.acquire_count, 0)
        self.assertGreaterEqual(len(state_lock.thread_ids), 2)


if __name__ == "__main__":
    unittest.main()
