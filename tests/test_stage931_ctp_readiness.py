from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import run_qmt_roll_stage931_official_live_ctp_submit_adapter as stage931


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.hook: Callable[[], None] = lambda: None

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds
        self.hook()


class FakeTdApi:
    def __init__(
        self,
        clock: FakeClock,
        *,
        contract_inited: bool = True,
        account_returns: list[int] | None = None,
        position_returns: list[int] | None = None,
    ) -> None:
        self.clock = clock
        self.login_status = True
        self.contract_inited = contract_inited
        self.reqid = 10
        self.brokerid = "fake-broker"
        self.userid = "fake-user"
        self.account_returns = list(account_returns or [0])
        self.position_returns = list(position_returns or [0])
        self.calls: list[dict[str, Any]] = []

    def _next_ret(self, values: list[int]) -> int:
        return values.pop(0) if values else 0

    def reqQryTradingAccount(self, request: dict[str, Any], reqid: int) -> int:
        ret = self._next_ret(self.account_returns)
        self.calls.append({"kind": "account", "reqid": reqid, "at": self.clock.now, "ret": ret})
        return ret

    def reqQryInvestorPosition(self, request: dict[str, Any], reqid: int) -> int:
        ret = self._next_ret(self.position_returns)
        self.calls.append({"kind": "position", "reqid": reqid, "at": self.clock.now, "ret": ret})
        return ret


def _base_rows() -> dict[str, list[dict[str, Any]]]:
    return {
        "logs": [
            {"msg": "交易服务器连接成功"},
            {"msg": "交易服务器授权验证成功"},
            {"msg": "交易服务器登录成功"},
        ],
        "settlement_callbacks": [
            {"reqid": 3, "last": True, "has_data": True, "error_id": 0, "error_msg": ""}
        ],
        "account_query_callbacks": [],
        "position_query_callbacks": [],
        "order_query_callbacks": [],
        "accounts": [],
        "positions": [],
        "orders": [],
        "trades": [],
    }


def _install_success_callback_hook(
    clock: FakeClock,
    td_api: FakeTdApi,
    rows: dict[str, list[dict[str, Any]]],
    *,
    position_has_data: bool = True,
) -> None:
    injected: set[tuple[str, int]] = set()

    def hook() -> None:
        for call in list(td_api.calls):
            key = (str(call["kind"]), int(call["reqid"]))
            if call["ret"] != 0 or key in injected or clock.now - float(call["at"]) < 0.1:
                continue
            injected.add(key)
            if call["kind"] == "account":
                rows["account_query_callbacks"].append(
                    {
                        "reqid": call["reqid"],
                        "last": True,
                        "has_data": True,
                        "account_id": "fake-account",
                        "error_id": 0,
                    }
                )
                rows["accounts"].append({"accountid": "fake-account"})
            else:
                rows["position_query_callbacks"].append(
                    {
                        "reqid": call["reqid"],
                        "last": True,
                        "has_data": position_has_data,
                        "error_id": 0,
                    }
                )
                if position_has_data:
                    rows["positions"].append({"vt_symbol": "jm2609.DCE", "volume": 2})

    clock.hook = hook


def _raw_order(
    *,
    status: str = "0",
    traded: int = 1,
    volume: int = 1,
    order_sys_id: str = "sys-1",
    front_id: int = 99,
    session_id: int = 777,
    order_ref: str = "9001",
) -> dict[str, Any]:
    return {
        "BrokerID": "fake-broker",
        "InvestorID": "fake-user",
        "InstrumentID": "JM2609",
        "ExchangeID": "DCE",
        "OrderRef": order_ref,
        "OrderSysID": order_sys_id,
        "FrontID": front_id,
        "SessionID": session_id,
        "OrderStatus": status,
        "Direction": "1",
        "CombOffsetFlag": "0",
        "VolumeTotalOriginal": volume,
        "VolumeTraded": traded,
    }


def _raw_position(*, volume: int = 1, direction: str = "3") -> dict[str, Any]:
    return {
        "BrokerID": "fake-broker",
        "InvestorID": "fake-user",
        "InstrumentID": "JM2609",
        "ExchangeID": "DCE",
        "PosiDirection": direction,
        "Position": volume,
        "TodayPosition": volume,
        "YdPosition": 0,
        "LongFrozen": 0,
        "ShortFrozen": 0,
    }


class FakeSnapshotTdApi:
    """Synchronous CTP callback fake for deterministic snapshot races."""

    def __init__(
        self,
        clock: FakeClock,
        *,
        order_responses: list[dict[str, Any]],
        position_responses: list[dict[str, Any]],
    ) -> None:
        self.clock = clock
        self.reqid = 50
        self.brokerid = "fake-broker"
        self.userid = "fake-user"
        self.login_status = True
        self.contract_inited = True
        self.order_responses = list(order_responses)
        self.position_responses = list(position_responses)
        self.calls: list[dict[str, Any]] = []
        self.forwarded: list[tuple[str, int, bool]] = []

    def onRspSettlementInfoConfirm(
        self, data: dict, error: dict, reqid: int, last: bool
    ) -> None:
        return None

    def onRspQryTradingAccount(
        self, data: dict, error: dict, reqid: int, last: bool
    ) -> None:
        return None

    def onRspQryInvestorPosition(
        self, data: dict, error: dict, reqid: int, last: bool
    ) -> None:
        self.forwarded.append(("position", reqid, last))

    def onRspQryOrder(
        self, data: dict, error: dict, reqid: int, last: bool
    ) -> None:
        self.forwarded.append(("order", reqid, last))

    def _respond(
        self,
        kind: str,
        responses: list[dict[str, Any]],
        reqid: int,
    ) -> int:
        response = responses.pop(0) if responses else {"callbacks": []}
        request_ret = int(response.get("ret", 0))
        self.calls.append(
            {
                "kind": kind,
                "reqid": reqid,
                "at": self.clock.now,
                "ret": request_ret,
            }
        )
        if request_ret != 0:
            return request_ret
        for callback in response.get("callbacks", []):
            callback_reqid = reqid + int(callback.get("reqid_delta", 0))
            data = callback.get("data", {})
            error = callback.get("error", {})
            last = bool(callback.get("last", True))
            if kind == "order":
                self.onRspQryOrder(data, error, callback_reqid, last)
            else:
                self.onRspQryInvestorPosition(
                    data, error, callback_reqid, last
                )
        return request_ret

    def reqQryOrder(self, request: dict[str, Any], reqid: int) -> int:
        return self._respond("order", self.order_responses, reqid)

    def reqQryInvestorPosition(
        self, request: dict[str, Any], reqid: int
    ) -> int:
        return self._respond("position", self.position_responses, reqid)


def _callback(
    data: dict[str, Any] | None = None,
    *,
    error_id: int = 0,
    reqid_delta: int = 0,
    last: bool = True,
) -> dict[str, Any]:
    return {
        "data": {} if data is None else data,
        "error": {} if error_id == 0 else {"ErrorID": error_id, "ErrorMsg": "bad"},
        "reqid_delta": reqid_delta,
        "last": last,
    }


def _open_request() -> stage931.OrderRequest:
    return stage931.OrderRequest(
        symbol="JM2609",
        exchange=stage931.Exchange.DCE,
        direction=stage931.Direction.SHORT,
        type=stage931.OrderType.LIMIT,
        volume=1,
        price=1200.0,
        offset=stage931.Offset.OPEN,
        reference="test-final-snapshot",
    )


class Stage931CtpReadinessTests(unittest.TestCase):
    def test_missing_or_stale_stage174_orders_are_diagnostic_only(self) -> None:
        missing = stage931._readonly_order_snapshot_diagnostic(
            None, max_age_seconds=180
        )
        stale = stage931._readonly_order_snapshot_diagnostic(
            181.0, max_age_seconds=180
        )

        for diagnostic in (missing, stale):
            self.assertEqual(
                diagnostic["readonly_order_snapshot_confirmed"], 0
            )
            self.assertEqual(
                diagnostic["readonly_order_snapshot_authoritative_for_send"],
                0,
            )
            self.assertEqual(
                diagnostic["readonly_order_snapshot_role"],
                "diagnostic_only_final_opo_is_authoritative",
            )

    def test_connect_suppresses_gateway_timer_queries_even_when_connect_would_register(self) -> None:
        class FakeEventEngine:
            def __init__(self) -> None:
                self.handlers: list[tuple[str, object]] = []

            def register(self, event_type: str, handler: object) -> None:
                self.handlers.append((event_type, handler))

            def unregister(self, event_type: str, handler: object) -> None:
                self.handlers = [
                    item for item in self.handlers if item != (event_type, handler)
                ]

        class FakeGateway:
            def __init__(self, event_engine: FakeEventEngine) -> None:
                self.event_engine = event_engine

            def process_timer_event(self, _event: object) -> None:
                return None

            def init_query(self) -> None:
                self.event_engine.register(
                    stage931.EVENT_TIMER, self.process_timer_event
                )

        class FakeMainEngine:
            def __init__(self, gateway: FakeGateway) -> None:
                self.gateway = gateway

            def connect(self, _setting: dict, _gateway_name: str) -> None:
                self.gateway.init_query()

        events = FakeEventEngine()
        gateway = FakeGateway(events)
        main_engine = FakeMainEngine(gateway)

        stage931._connect_ctp_without_timer_queries(main_engine, gateway, events)

        self.assertEqual(events.handlers, [])
        self.assertTrue(callable(gateway.init_query))

    def test_account_callback_requires_last_zero_error_and_account_id(self) -> None:
        reqid = 17
        self.assertFalse(
            stage931._callback_result(
                [{"reqid": reqid, "last": False, "error_id": 0, "account_id": "account"}],
                reqid,
                require_account_id=True,
            )["success"]
        )
        self.assertFalse(
            stage931._callback_result(
                [{"reqid": reqid, "last": True, "error_id": 7, "account_id": "account"}],
                reqid,
                require_account_id=True,
            )["success"]
        )
        self.assertFalse(
            stage931._callback_result(
                [{"reqid": reqid, "last": True, "error_id": 0, "account_id": ""}],
                reqid,
                require_account_id=True,
            )["success"]
        )
        self.assertFalse(
            stage931._callback_result(
                [{"reqid": reqid, "last": True, "account_id": "account"}],
                reqid,
                require_account_id=True,
            )["success"]
        )
        self.assertTrue(
            stage931._callback_result(
                [{"reqid": reqid, "last": True, "error_id": 0, "account_id": "account"}],
                reqid,
                require_account_id=True,
            )["success"]
        )

    def test_settlement_error_fails_before_any_explicit_query(self) -> None:
        clock = FakeClock()
        rows = _base_rows()
        rows["settlement_callbacks"] = [
            {"reqid": 3, "last": True, "has_data": True, "error_id": 9, "error_msg": "rejected"}
        ]
        td_api = FakeTdApi(clock)

        ready, _, blockers, _ = stage931._wait_for_ctp_readiness(
            td_api,
            rows,
            account_required=True,
            max_wait_seconds=5,
            monotonic=clock.monotonic,
            sleeper=clock.sleep,
        )

        self.assertFalse(ready)
        self.assertTrue(any(value.startswith("ctp_settlement_callback_error:") for value in blockers), blockers)
        self.assertEqual(td_api.calls, [])

    def test_state_waits_past_old_eight_second_boundary(self) -> None:
        clock = FakeClock()
        rows = _base_rows()
        td_api = FakeTdApi(clock, contract_inited=False)
        _install_success_callback_hook(clock, td_api, rows)
        callback_hook = clock.hook

        def hook() -> None:
            if clock.now >= 9.0:
                td_api.contract_inited = True
            callback_hook()

        clock.hook = hook
        ready, flags, blockers, state = stage931._wait_for_ctp_readiness(
            td_api,
            rows,
            account_required=True,
            max_wait_seconds=30,
            monotonic=clock.monotonic,
            sleeper=clock.sleep,
        )

        self.assertTrue(ready, blockers)
        self.assertGreater(state.elapsed_seconds, 8.0)
        self.assertLess(state.elapsed_seconds, 30.0)
        self.assertTrue(flags["account_query_success"])
        self.assertTrue(flags["position_query_success"])

    def test_close_only_skips_account_and_accepts_confirmed_flat_snapshot(self) -> None:
        clock = FakeClock()
        rows = _base_rows()
        td_api = FakeTdApi(clock)
        _install_success_callback_hook(clock, td_api, rows, position_has_data=False)

        ready, flags, blockers, _ = stage931._wait_for_ctp_readiness(
            td_api,
            rows,
            account_required=False,
            max_wait_seconds=5,
            monotonic=clock.monotonic,
            sleeper=clock.sleep,
        )

        self.assertTrue(ready, blockers)
        self.assertTrue(flags["position_query_success"])
        self.assertTrue(flags["position_snapshot_processed"])
        self.assertEqual([call for call in td_api.calls if call["kind"] == "account"], [])

    def test_open_requires_account_id_and_processed_account_event(self) -> None:
        clock = FakeClock()
        rows = _base_rows()
        td_api = FakeTdApi(clock)
        injected = False

        def hook() -> None:
            nonlocal injected
            calls = [call for call in td_api.calls if call["kind"] == "account" and call["ret"] == 0]
            if calls and not injected and clock.now - calls[0]["at"] >= 0.1:
                injected = True
                rows["account_query_callbacks"].append(
                    {
                        "reqid": calls[0]["reqid"],
                        "last": True,
                        "has_data": True,
                        "account_id": "",
                        "error_id": 0,
                    }
                )

        clock.hook = hook
        ready, _, blockers, _ = stage931._wait_for_ctp_readiness(
            td_api,
            rows,
            account_required=True,
            max_wait_seconds=2,
            monotonic=clock.monotonic,
            sleeper=clock.sleep,
        )

        self.assertFalse(ready)
        self.assertIn("ctp_account_callback_missing", blockers)
        self.assertEqual(len([call for call in td_api.calls if call["kind"] == "account"]), 1)
        self.assertEqual(len([call for call in td_api.calls if call["kind"] == "position"]), 0)

        clock = FakeClock()
        rows = _base_rows()
        td_api = FakeTdApi(clock)
        injected: set[tuple[str, int]] = set()

        def valid_raw_callbacks_without_account_event() -> None:
            for call in list(td_api.calls):
                key = (call["kind"], call["reqid"])
                if call["ret"] != 0 or key in injected or clock.now - call["at"] < 0.1:
                    continue
                injected.add(key)
                if call["kind"] == "account":
                    rows["account_query_callbacks"].append(
                        {
                            "reqid": call["reqid"],
                            "last": True,
                            "has_data": True,
                            "account_id": "fake-account",
                            "error_id": 0,
                        }
                    )
                else:
                    rows["position_query_callbacks"].append(
                        {
                            "reqid": call["reqid"],
                            "last": True,
                            "has_data": False,
                            "error_id": 0,
                        }
                    )

        clock.hook = valid_raw_callbacks_without_account_event
        ready, _, blockers, _ = stage931._wait_for_ctp_readiness(
            td_api,
            rows,
            account_required=True,
            max_wait_seconds=3,
            monotonic=clock.monotonic,
            sleeper=clock.sleep,
        )

        self.assertFalse(ready)
        self.assertIn("ctp_account_event_not_processed", blockers)

    def test_position_callback_error_fails_closed(self) -> None:
        clock = FakeClock()
        rows = _base_rows()
        td_api = FakeTdApi(clock)
        injected: set[tuple[str, int]] = set()

        def hook() -> None:
            for call in list(td_api.calls):
                key = (call["kind"], call["reqid"])
                if call["ret"] != 0 or key in injected or clock.now - call["at"] < 0.1:
                    continue
                injected.add(key)
                if call["kind"] == "account":
                    rows["account_query_callbacks"].append(
                        {
                            "reqid": call["reqid"],
                            "last": True,
                            "has_data": True,
                            "account_id": "fake-account",
                            "error_id": 0,
                        }
                    )
                    rows["accounts"].append({"accountid": "fake-account"})
                else:
                    rows["position_query_callbacks"].append(
                        {
                            "reqid": call["reqid"],
                            "last": True,
                            "has_data": False,
                            "error_id": 7,
                        }
                    )

        clock.hook = hook
        ready, _, blockers, _ = stage931._wait_for_ctp_readiness(
            td_api,
            rows,
            account_required=True,
            max_wait_seconds=5,
            monotonic=clock.monotonic,
            sleeper=clock.sleep,
        )

        self.assertFalse(ready)
        self.assertTrue(any(value.startswith("ctp_position_query_error:") for value in blockers), blockers)

    def test_nonzero_query_return_is_throttled_before_retry(self) -> None:
        clock = FakeClock()
        rows = _base_rows()
        td_api = FakeTdApi(clock, account_returns=[-2, 0])
        _install_success_callback_hook(clock, td_api, rows)

        ready, _, blockers, _ = stage931._wait_for_ctp_readiness(
            td_api,
            rows,
            account_required=True,
            max_wait_seconds=6,
            monotonic=clock.monotonic,
            sleeper=clock.sleep,
        )

        account_calls = [call for call in td_api.calls if call["kind"] == "account"]
        self.assertTrue(ready, blockers)
        self.assertEqual(len(account_calls), 2)
        self.assertGreaterEqual(account_calls[1]["at"] - account_calls[0]["at"], 1.1 - 1e-9)

    def test_explicit_position_query_starts_a_clean_snapshot_epoch(self) -> None:
        clock = FakeClock()
        rows = _base_rows()
        rows["positions"] = [{"vt_symbol": "stale.DCE", "volume": 99}]
        rows["position_query_callbacks"] = [{"reqid": 3, "last": True, "error_id": 0}]
        td_api = FakeTdApi(clock)
        state = stage931.CtpReadinessState(account_required=False)

        attempt = stage931._issue_ctp_read_query(td_api, state, rows, "position", clock.monotonic())

        self.assertEqual(attempt["request_ret"], 0)
        self.assertEqual(rows["positions"], [])
        self.assertEqual(rows["position_query_callbacks"], [])
        self.assertEqual(rows["_position_query_epoch"]["active_reqid"], attempt["reqid"])
        self.assertIsNone(rows["_position_query_epoch"]["complete_reqid"])

    def test_accepted_query_without_callback_is_not_reissued(self) -> None:
        clock = FakeClock()
        rows = _base_rows()
        td_api = FakeTdApi(clock, account_returns=[0, 0, 0])

        ready, _, blockers, _ = stage931._wait_for_ctp_readiness(
            td_api,
            rows,
            account_required=True,
            max_wait_seconds=2,
            monotonic=clock.monotonic,
            sleeper=clock.sleep,
        )

        self.assertFalse(ready)
        self.assertTrue(any(value.startswith("ctp_readiness_timeout:") for value in blockers), blockers)
        self.assertEqual(len([call for call in td_api.calls if call["kind"] == "account"]), 1)
        self.assertEqual(len([call for call in td_api.calls if call["kind"] == "position"]), 0)

    def test_final_transport_gate_rejects_current_disconnect(self) -> None:
        clock = FakeClock()
        rows = _base_rows()
        td_api = FakeTdApi(clock)
        _install_success_callback_hook(clock, td_api, rows, position_has_data=False)
        ready, _, blockers, state = stage931._wait_for_ctp_readiness(
            td_api,
            rows,
            account_required=False,
            max_wait_seconds=5,
            monotonic=clock.monotonic,
            sleeper=clock.sleep,
        )
        self.assertTrue(ready, blockers)

        td_api.login_status = False
        rows["logs"].append({"msg": "交易服务器连接断开，原因4097"})
        final_blockers = stage931._final_ctp_transport_blockers(td_api, rows, state)

        self.assertIn("ctp_td_disconnected_after_connect", final_blockers)
        self.assertIn("ctp_td_login_live_missing", final_blockers)

    def test_callback_monkeypatches_restore_after_exception(self) -> None:
        class FakeCallbackApi:
            def onRspSettlementInfoConfirm(self, data: dict, error: dict, reqid: int, last: bool) -> str:
                return "settlement"

            def onRspQryTradingAccount(self, data: dict, error: dict, reqid: int, last: bool) -> str:
                return "account"

            def onRspQryInvestorPosition(self, data: dict, error: dict, reqid: int, last: bool) -> str:
                return "position"

            def onRspQryOrder(self, data: dict, error: dict, reqid: int, last: bool) -> str:
                return "order"

            def reqOrderInsert(self, data: dict, reqid: int) -> int:
                return -2

        originals = (
            FakeCallbackApi.onRspSettlementInfoConfirm,
            FakeCallbackApi.onRspQryTradingAccount,
            FakeCallbackApi.onRspQryInvestorPosition,
            FakeCallbackApi.onRspQryOrder,
            FakeCallbackApi.reqOrderInsert,
        )
        rows = _base_rows()

        with self.assertRaisesRegex(RuntimeError, "boom"):
            with stage931._instrument_ctp_readiness_callbacks(FakeCallbackApi, rows):
                self.assertIsNot(FakeCallbackApi.onRspSettlementInfoConfirm, originals[0])
                self.assertIsNot(FakeCallbackApi.onRspQryTradingAccount, originals[1])
                self.assertIsNot(FakeCallbackApi.onRspQryInvestorPosition, originals[2])
                self.assertIsNot(FakeCallbackApi.onRspQryOrder, originals[3])
                self.assertIsNot(FakeCallbackApi.reqOrderInsert, originals[4])
                self.assertEqual(FakeCallbackApi().reqOrderInsert({}, 77), -2)
                self.assertEqual(
                    rows["order_insert_requests"],
                    [
                        {
                            "reqid": 77,
                            "requested_at": rows["order_insert_requests"][0][
                                "requested_at"
                            ],
                            "request_ret": -2,
                            "exception": "",
                        }
                    ],
                )
                raise RuntimeError("boom")

        self.assertIs(FakeCallbackApi.onRspSettlementInfoConfirm, originals[0])
        self.assertIs(FakeCallbackApi.onRspQryTradingAccount, originals[1])
        self.assertIs(FakeCallbackApi.onRspQryInvestorPosition, originals[2])
        self.assertIs(FakeCallbackApi.onRspQryOrder, originals[3])
        self.assertIs(FakeCallbackApi.reqOrderInsert, originals[4])

    def test_position_callbacks_publish_only_complete_active_query_epoch(self) -> None:
        forwarded: list[tuple[str, int, bool]] = []

        class FakeCallbackApi:
            def onRspSettlementInfoConfirm(self, data: dict, error: dict, reqid: int, last: bool) -> None:
                return None

            def onRspQryTradingAccount(self, data: dict, error: dict, reqid: int, last: bool) -> None:
                return None

            def onRspQryInvestorPosition(self, data: dict, error: dict, reqid: int, last: bool) -> None:
                forwarded.append((str(data.get("InstrumentID", "")), reqid, last))

        rows = _base_rows()
        rows["_position_query_epoch"] = {
            "active_reqid": 41,
            "complete_reqid": None,
            "pending_callbacks": [],
        }
        rows["_position_vt_symbol_by_instrument"] = {"JM2609": "JM2609.DCE"}
        api = FakeCallbackApi()
        ok = {"ErrorID": 0, "ErrorMsg": ""}
        with stage931._instrument_ctp_readiness_callbacks(FakeCallbackApi, rows):
            api.onRspQryInvestorPosition(
                {"InstrumentID": "old", "PosiDirection": "3", "Position": 99},
                ok,
                40,
                True,
            )
            api.onRspQryInvestorPosition(
                {"InstrumentID": "jm2609", "PosiDirection": "3", "Position": 2},
                ok,
                41,
                False,
            )
            self.assertEqual(forwarded, [])
            api.onRspQryInvestorPosition({}, ok, 41, True)

        self.assertEqual(forwarded, [("jm2609", 41, False), ("", 41, True)])
        self.assertEqual(rows["_position_query_epoch"]["complete_reqid"], 41)
        self.assertTrue(rows["position_query_callbacks"][0]["ignored_outside_active_epoch"])
        self.assertEqual(len(rows["positions"]), 1)
        self.assertEqual(rows["positions"][0]["vt_symbol"], "JM2609.DCE")
        self.assertEqual(rows["positions"][0]["direction"], "short")
        self.assertEqual(rows["positions"][0]["volume"], 2.0)

        # A later queued EVENT_POSITION has no reqid and is diagnostic only;
        # it cannot mutate the authoritative active-query snapshot.
        rows.setdefault("position_events_unscoped", []).append(
            {"vt_symbol": "JM2609.DCE", "direction": "short", "volume": 99}
        )
        self.assertEqual(rows["positions"][0]["volume"], 2.0)

    def test_error_callbacks_are_recorded_without_forwarding_to_upstream_handlers(self) -> None:
        forwarded: list[str] = []

        class FakeCallbackApi:
            def onRspSettlementInfoConfirm(self, data: dict, error: dict, reqid: int, last: bool) -> None:
                forwarded.append("settlement")

            def onRspQryTradingAccount(self, data: dict, error: dict, reqid: int, last: bool) -> None:
                forwarded.append("account")

            def onRspQryInvestorPosition(self, data: dict, error: dict, reqid: int, last: bool) -> None:
                forwarded.append("position")

        rows = _base_rows()
        rows["settlement_callbacks"] = []
        api = FakeCallbackApi()
        with stage931._instrument_ctp_readiness_callbacks(FakeCallbackApi, rows):
            api.onRspSettlementInfoConfirm({}, {"ErrorID": 1, "ErrorMsg": "bad"}, 1, True)
            api.onRspQryTradingAccount({}, {"ErrorID": 2, "ErrorMsg": "bad"}, 2, True)
            api.onRspQryInvestorPosition({}, {"ErrorID": 3, "ErrorMsg": "bad"}, 3, True)
            api.onRspQryTradingAccount({"AccountID": "fake"}, {}, 4, True)

        self.assertEqual(forwarded, ["account"])
        self.assertEqual(rows["settlement_callbacks"][0]["error_id"], 1)
        self.assertEqual(rows["account_query_callbacks"][0]["error_id"], 2)
        self.assertEqual(rows["position_query_callbacks"][0]["error_id"], 3)
        self.assertEqual(rows["account_query_callbacks"][1]["error_id"], 0)

    def test_empty_error_dict_is_success_for_all_generated_ctp_callbacks(self) -> None:
        forwarded: list[str] = []

        class FakeCallbackApi:
            def onRspSettlementInfoConfirm(self, data: dict, error: dict, reqid: int, last: bool) -> None:
                forwarded.append("settlement")

            def onRspQryTradingAccount(self, data: dict, error: dict, reqid: int, last: bool) -> None:
                forwarded.append("account")

            def onRspQryInvestorPosition(self, data: dict, error: dict, reqid: int, last: bool) -> None:
                forwarded.append("position")

        rows = _base_rows()
        rows["settlement_callbacks"] = []
        rows["_position_query_epoch"] = {
            "active_reqid": 7,
            "complete_reqid": None,
            "pending_callbacks": [],
        }
        rows["_position_vt_symbol_by_instrument"] = {"JM2609": "JM2609.DCE"}
        api = FakeCallbackApi()
        with stage931._instrument_ctp_readiness_callbacks(FakeCallbackApi, rows):
            api.onRspSettlementInfoConfirm({}, {}, 5, True)
            api.onRspQryTradingAccount({"AccountID": "fake"}, {}, 6, True)
            api.onRspQryInvestorPosition(
                {"InstrumentID": "JM2609", "PosiDirection": "3", "Position": 2},
                {},
                7,
                True,
            )

        self.assertEqual(forwarded, ["settlement", "account", "position"])
        self.assertEqual(rows["settlement_callbacks"][0]["error_id"], 0)
        self.assertEqual(rows["account_query_callbacks"][0]["error_id"], 0)
        self.assertEqual(rows["position_query_callbacks"][0]["error_id"], 0)

    def test_final_snapshot_stable_empty_replaces_stale_state_and_honors_global_pacing(self) -> None:
        clock = FakeClock()
        rows = _base_rows()
        legacy_order_file = stage931._readonly_order_snapshot_diagnostic(
            None, max_age_seconds=180
        )
        rows["orders"] = [{"status": "not traded", "vt_orderid": "stale"}]
        rows["positions"] = [
            {"vt_symbol": "JM2609.DCE", "direction": "short", "volume": 99}
        ]
        rows["_ctp_last_query_monotonic"] = 0.0
        td_api = FakeSnapshotTdApi(
            clock,
            order_responses=[
                {"callbacks": [_callback()]},
                {"callbacks": [_callback()]},
            ],
            position_responses=[{"callbacks": [_callback()]}],
        )
        readiness_state = stage931.CtpReadinessState(
            account_required=False,
            expected_position_reqid=11,
        )

        with stage931._instrument_ctp_readiness_callbacks(
            FakeSnapshotTdApi, rows
        ):
            snapshot = stage931._final_pre_send_snapshot_epoch(
                td_api,
                rows,
                max_wait_seconds=5.0,
                readiness_state=readiness_state,
                monotonic=clock.monotonic,
                sleeper=clock.sleep,
            )

        self.assertTrue(snapshot["confirmed"], snapshot["blockers"])
        self.assertIsNotNone(snapshot["q2_completed_monotonic"])
        self.assertGreaterEqual(
            snapshot["q2_completed_monotonic"], td_api.calls[2]["at"]
        )
        self.assertEqual(
            legacy_order_file["readonly_order_snapshot_authoritative_for_send"],
            0,
        )
        self.assertTrue(snapshot["stable"])
        self.assertEqual(rows["positions"], [])
        self.assertEqual(readiness_state.expected_position_reqid, 52)
        self.assertEqual(
            [call["kind"] for call in td_api.calls],
            ["order", "position", "order"],
        )
        self.assertEqual(
            [call["reqid"] for call in td_api.calls], [51, 52, 53]
        )
        self.assertGreaterEqual(td_api.calls[0]["at"], 1.1 - 1e-9)
        self.assertGreaterEqual(
            td_api.calls[1]["at"] - td_api.calls[0]["at"], 1.1 - 1e-9
        )
        self.assertGreaterEqual(
            td_api.calls[2]["at"] - td_api.calls[1]["at"], 1.1 - 1e-9
        )
        blockers = stage931._final_pre_send_blockers(
            rows,
            _open_request(),
            "JM2609.DCE",
            authoritative_active_orders=snapshot["active_orders"],
            order_query_confirmed=snapshot["confirmed"],
        )
        self.assertEqual(blockers, [])
        self.assertEqual(
            stage931._final_ctp_transport_blockers(
                td_api, rows, readiness_state
            ),
            [],
        )

    def test_final_snapshot_stable_historical_terminal_order_passes(self) -> None:
        clock = FakeClock()
        rows = _base_rows()
        historical = _raw_order(status="0", traded=1)
        td_api = FakeSnapshotTdApi(
            clock,
            order_responses=[
                {"callbacks": [_callback(historical)]},
                {"callbacks": [_callback(dict(historical))]},
            ],
            position_responses=[{"callbacks": [_callback()]}],
        )

        with stage931._instrument_ctp_readiness_callbacks(
            FakeSnapshotTdApi, rows
        ):
            snapshot = stage931._final_pre_send_snapshot_epoch(
                td_api,
                rows,
                max_wait_seconds=5.0,
                monotonic=clock.monotonic,
                sleeper=clock.sleep,
            )

        self.assertTrue(snapshot["confirmed"], snapshot["blockers"])
        self.assertEqual(len(snapshot["orders"]), 1)
        self.assertEqual(snapshot["active_orders"], [])

    def test_final_snapshot_blocks_active_order_from_another_session(self) -> None:
        clock = FakeClock()
        rows = _base_rows()
        active = _raw_order(
            status="3",
            traded=0,
            order_sys_id="other-session-order",
            front_id=998,
            session_id=445566,
        )
        td_api = FakeSnapshotTdApi(
            clock,
            order_responses=[
                {"callbacks": [_callback(active)]},
                {"callbacks": [_callback(dict(active))]},
            ],
            position_responses=[{"callbacks": [_callback()]}],
        )

        with stage931._instrument_ctp_readiness_callbacks(
            FakeSnapshotTdApi, rows
        ):
            snapshot = stage931._final_pre_send_snapshot_epoch(
                td_api,
                rows,
                max_wait_seconds=5.0,
                monotonic=clock.monotonic,
                sleeper=clock.sleep,
            )

        self.assertTrue(snapshot["confirmed"], snapshot["blockers"])
        self.assertEqual(len(snapshot["active_orders"]), 1)
        blockers = stage931._final_pre_send_blockers(
            rows,
            _open_request(),
            "JM2609.DCE",
            authoritative_active_orders=snapshot["active_orders"],
            order_query_confirmed=snapshot["confirmed"],
        )
        self.assertIn("final_order_query_active_order_count=1", blockers)

    def test_final_snapshot_blocks_terminal_order_appearing_during_sandwich(self) -> None:
        clock = FakeClock()
        rows = _base_rows()
        td_api = FakeSnapshotTdApi(
            clock,
            order_responses=[
                {"callbacks": [_callback()]},
                {
                    "callbacks": [
                        _callback(_raw_order(status="0", traded=1))
                    ]
                },
            ],
            position_responses=[{"callbacks": [_callback()]}],
        )

        with stage931._instrument_ctp_readiness_callbacks(
            FakeSnapshotTdApi, rows
        ):
            snapshot = stage931._final_pre_send_snapshot_epoch(
                td_api,
                rows,
                max_wait_seconds=5.0,
                monotonic=clock.monotonic,
                sleeper=clock.sleep,
            )

        self.assertFalse(snapshot["confirmed"])
        self.assertIn(
            "final_order_snapshot_changed_during_sandwich",
            snapshot["blockers"],
        )

    def test_final_snapshot_blocks_same_order_changing_from_active_to_terminal(self) -> None:
        clock = FakeClock()
        rows = _base_rows()
        active = _raw_order(status="3", traded=0)
        terminal = _raw_order(status="0", traded=1)
        td_api = FakeSnapshotTdApi(
            clock,
            order_responses=[
                {"callbacks": [_callback(active)]},
                {"callbacks": [_callback(terminal)]},
            ],
            position_responses=[{"callbacks": [_callback()]}],
        )

        with stage931._instrument_ctp_readiness_callbacks(
            FakeSnapshotTdApi, rows
        ):
            snapshot = stage931._final_pre_send_snapshot_epoch(
                td_api,
                rows,
                max_wait_seconds=5.0,
                monotonic=clock.monotonic,
                sleeper=clock.sleep,
            )

        self.assertFalse(snapshot["confirmed"])
        self.assertIn(
            "final_order_snapshot_changed_during_sandwich",
            snapshot["blockers"],
        )
        self.assertEqual(snapshot["canonical_q1"][0]["status_class"], "active")
        self.assertEqual(snapshot["canonical_q2"][0]["status_class"], "terminal")

    def test_final_snapshot_fresh_position_replaces_readiness_flat_and_blocks_open(self) -> None:
        clock = FakeClock()
        rows = _base_rows()
        rows["positions"] = []
        td_api = FakeSnapshotTdApi(
            clock,
            order_responses=[
                {"callbacks": [_callback()]},
                {"callbacks": [_callback()]},
            ],
            position_responses=[
                {"callbacks": [_callback(_raw_position(volume=1))]}
            ],
        )

        with stage931._instrument_ctp_readiness_callbacks(
            FakeSnapshotTdApi, rows
        ):
            snapshot = stage931._final_pre_send_snapshot_epoch(
                td_api,
                rows,
                max_wait_seconds=5.0,
                monotonic=clock.monotonic,
                sleeper=clock.sleep,
            )

        self.assertTrue(snapshot["confirmed"], snapshot["blockers"])
        self.assertEqual(rows["positions"][0]["position_query_reqid"], 52)
        blockers = stage931._final_pre_send_blockers(
            rows,
            _open_request(),
            "JM2609.DCE",
            authoritative_active_orders=snapshot["active_orders"],
            order_query_confirmed=snapshot["confirmed"],
        )
        self.assertIn(
            "final_target_symbol_gross_position_exists_for_open:1.0",
            blockers,
        )

    def test_final_snapshot_wrong_reqid_fails_closed_without_starting_position_query(self) -> None:
        clock = FakeClock()
        rows = _base_rows()
        td_api = FakeSnapshotTdApi(
            clock,
            order_responses=[
                {"callbacks": [_callback(reqid_delta=1)]},
            ],
            position_responses=[{"callbacks": [_callback()]}],
        )

        with stage931._instrument_ctp_readiness_callbacks(
            FakeSnapshotTdApi, rows
        ):
            snapshot = stage931._final_pre_send_snapshot_epoch(
                td_api,
                rows,
                max_wait_seconds=0.5,
                monotonic=clock.monotonic,
                sleeper=clock.sleep,
            )

        self.assertFalse(snapshot["confirmed"])
        self.assertTrue(
            any("final_order_query_timeout" in value for value in snapshot["blockers"]),
            snapshot["blockers"],
        )
        self.assertEqual(snapshot["order_q1"]["ignored_callback_count"], 1)
        self.assertEqual([call["kind"] for call in td_api.calls], ["order"])

    def test_final_snapshot_query_error_fails_closed(self) -> None:
        clock = FakeClock()
        rows = _base_rows()
        td_api = FakeSnapshotTdApi(
            clock,
            order_responses=[
                {"callbacks": [_callback(error_id=7)]},
            ],
            position_responses=[],
        )

        with stage931._instrument_ctp_readiness_callbacks(
            FakeSnapshotTdApi, rows
        ):
            snapshot = stage931._final_pre_send_snapshot_epoch(
                td_api,
                rows,
                max_wait_seconds=1.0,
                monotonic=clock.monotonic,
                sleeper=clock.sleep,
            )

        self.assertFalse(snapshot["confirmed"])
        self.assertTrue(
            any("final_order_query_error_ids=[7]" in value for value in snapshot["blockers"]),
            snapshot["blockers"],
        )

    def test_final_snapshot_position_wrong_reqid_fails_and_clears_readiness_rows(self) -> None:
        clock = FakeClock()
        rows = _base_rows()
        rows["positions"] = [
            {"vt_symbol": "JM2609.DCE", "direction": "short", "volume": 99}
        ]
        td_api = FakeSnapshotTdApi(
            clock,
            order_responses=[{"callbacks": [_callback()]}],
            position_responses=[
                {
                    "callbacks": [
                        _callback(_raw_position(volume=1), reqid_delta=1)
                    ]
                }
            ],
        )

        with stage931._instrument_ctp_readiness_callbacks(
            FakeSnapshotTdApi, rows
        ):
            snapshot = stage931._final_pre_send_snapshot_epoch(
                td_api,
                rows,
                max_wait_seconds=1.5,
                monotonic=clock.monotonic,
                sleeper=clock.sleep,
            )

        self.assertFalse(snapshot["confirmed"])
        self.assertTrue(
            any(
                "final_position_query_timeout" in value
                for value in snapshot["blockers"]
            ),
            snapshot["blockers"],
        )
        self.assertEqual(snapshot["position"]["ignored_callback_count"], 1)
        self.assertEqual(rows["positions"], [])
        self.assertEqual(
            [call["kind"] for call in td_api.calls], ["order", "position"]
        )

    def test_final_snapshot_second_order_timeout_fails_with_bounded_total_budget(self) -> None:
        clock = FakeClock()
        rows = _base_rows()
        td_api = FakeSnapshotTdApi(
            clock,
            order_responses=[
                {"callbacks": [_callback()]},
                {"callbacks": []},
            ],
            position_responses=[{"callbacks": [_callback()]}],
        )

        with stage931._instrument_ctp_readiness_callbacks(
            FakeSnapshotTdApi, rows
        ):
            snapshot = stage931._final_pre_send_snapshot_epoch(
                td_api,
                rows,
                max_wait_seconds=3.0,
                monotonic=clock.monotonic,
                sleeper=clock.sleep,
            )

        self.assertFalse(snapshot["confirmed"])
        self.assertTrue(
            any("final_order_query_timeout" in value for value in snapshot["blockers"]),
            snapshot["blockers"],
        )
        self.assertLessEqual(snapshot["elapsed_seconds"], 3.0 + 1e-9)
        self.assertEqual(
            [call["kind"] for call in td_api.calls],
            ["order", "position", "order"],
        )

    def test_final_snapshot_incomplete_order_identity_fails_closed(self) -> None:
        clock = FakeClock()
        rows = _base_rows()
        incomplete = _raw_order(
            status="3", traded=0, order_sys_id="", front_id=0, session_id=0
        )
        # Zero-valued FrontID/SessionID are present in Python but cannot form a
        # stable cross-session identity; omit them to model the raw CTP defect.
        incomplete.pop("FrontID")
        incomplete.pop("SessionID")
        td_api = FakeSnapshotTdApi(
            clock,
            order_responses=[{"callbacks": [_callback(incomplete)]}],
            position_responses=[],
        )

        with stage931._instrument_ctp_readiness_callbacks(
            FakeSnapshotTdApi, rows
        ):
            snapshot = stage931._final_pre_send_snapshot_epoch(
                td_api,
                rows,
                max_wait_seconds=1.0,
                monotonic=clock.monotonic,
                sleeper=clock.sleep,
            )

        self.assertFalse(snapshot["confirmed"])
        self.assertTrue(
            any(
                "OrderSysID_or_FrontID_SessionID_OrderRef" in value
                for value in snapshot["blockers"]
            ),
            snapshot["blockers"],
        )


if __name__ == "__main__":
    unittest.main()
