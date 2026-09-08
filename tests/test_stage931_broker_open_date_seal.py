from __future__ import annotations

import copy
import json
from datetime import datetime
import os
from pathlib import Path
import sys
import threading
import time
from types import ModuleType, SimpleNamespace

import pytest

os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples/portfolio_backtesting"))
import run_qmt_roll_stage931_official_live_ctp_submit_adapter as stage931
from qmt_roll_official_live_execution_ledger import append_broker_callback_event_once, append_execution_ledger_event, read_execution_ledger, reserve_execution_ledger_intent
from test_official_live_broker_open_date_seal import make_seal_inputs
from test_stage931_ctp_readiness import _InstrumentableCallbackApi


class SealApi(_InstrumentableCallbackApi):
    brokerid = "broker"
    userid = "account"
    frontid = 9
    sessionid = 10
    reqid = 20

    def __init__(self, inputs):
        self.inputs = inputs
        self.calls = []
        self.order_count = 0
        self.day = "20260908"

    def getTradingDay(self):
        return self.day

    def emit(self, name, callback, reqid):
        self.calls.append((name, reqid))
        for item in self.inputs["query_bundle"]["queries"][name]["callbacks"]:
            callback(copy.deepcopy(item["data"]), copy.deepcopy(item["error"]), reqid, item["last"])
        return 0

    def reqQryOrder(self, request, reqid):
        self.order_count += 1
        return self.emit("order_before" if self.order_count % 2 else "order_after", self.onRspQryOrder, reqid)

    def reqQryTrade(self, request, reqid):
        return self.emit("trades", self.onRspQryTrade, reqid)

    def reqQryInvestorPositionDetail(self, request, reqid):
        return self.emit("position_details", self.onRspQryInvestorPositionDetail, reqid)

    def reqQryInvestorPosition(self, request, reqid):
        return self.emit("positions", self.onRspQryInvestorPosition, reqid)


def setup_state(tmp_path):
    inputs = make_seal_inputs()
    path = tmp_path / "ledger"
    for row in inputs["execution_ledger_rows"]:
        append_execution_ledger_event(row, path)
    api = SealApi(inputs)
    rows = {name: [] for name in ("orders", "trades", "positions", "accounts", "settlement_callbacks",
                                 "position_query_callbacks", "order_query_callbacks", "trade_query_callbacks")}
    rows["_execution_event_ingress_counts"] = {"order": 0, "trade": 0, "position": 0}
    state = {"td_api": api, "rows": rows, "ctp_query_lock": threading.RLock(),
             "execution_event_ingress_lock": threading.RLock(), "connection_generation": "restarted",
             "service_generation": "service", "transport_generation_invalidated": False,
             "open_date_seal_pending": {}, "main_engine": object()}
    return inputs, path, api, state


def test_raw_query_producer_partial_terminal_and_restart_reuse(tmp_path, monkeypatch):
    inputs, path, api, state = setup_state(tmp_path)
    monkeypatch.setattr(stage931, "CTP_QUERY_INTERVAL_SECONDS", 0)
    state["open_date_seal_pending"]["CTP.1_2_3"] = "pending"
    with stage931._instrument_ctp_readiness_callbacks(SealApi, state["rows"]):
        result = stage931._seal_owned_open_order(state, path, "CTP.1_2_3", max_wait_seconds=10)
        assert result["confirmed"], result
        assert [name for name, _ in api.calls] == ["order_before", "trades", "position_details", "positions", "order_after"]
        assert not state["open_date_seal_pending"]
        saved = [row for row in read_execution_ledger(path) if row["event_type"] == "broker_position_open_date_sealed"]
        assert len(saved) == 1 and saved[0]["broker_open_date"] == "2026-09-08"
        api.calls.clear()
        api.day = "20260909"
        assert stage931._seal_owned_open_order(state, path, "CTP.1_2_3", max_wait_seconds=10)["confirmed"]
        assert api.calls == []


def test_failed_seal_blocks_only_new_open_risk(tmp_path, monkeypatch):
    inputs, path, api, state = setup_state(tmp_path)
    api.day = "20260909"
    monkeypatch.setattr(stage931, "CTP_QUERY_INTERVAL_SECONDS", 0)
    with stage931._instrument_ctp_readiness_callbacks(SealApi, state["rows"]):
        result = stage931._seal_owned_open_order(state, path, "CTP.1_2_3", max_wait_seconds=10)
    assert not result["confirmed"]
    assert stage931._open_date_risk_blockers(state, "open")
    assert stage931._open_date_risk_blockers(state, "close") == []


def test_existing_seal_rechecks_current_ledger_reservation_history(tmp_path, monkeypatch):
    inputs, path, api, state = setup_state(tmp_path)
    monkeypatch.setattr(stage931, "CTP_QUERY_INTERVAL_SECONDS", 0)
    with stage931._instrument_ctp_readiness_callbacks(SealApi, state["rows"]):
        assert stage931._seal_owned_open_order(state, path, "CTP.1_2_3", max_wait_seconds=8)["confirmed"]
        reserved = next(row for row in inputs["execution_ledger_rows"] if row["event_type"] == "reserved")
        append_execution_ledger_event({**reserved, "spool_lease_token": "new-dangerous-lease"}, path)
        api.calls.clear()
        result = stage931._seal_owned_open_order(state, path, "CTP.1_2_3", max_wait_seconds=8)
    assert not result["confirmed"]
    assert not api.calls


def test_existing_seal_allows_later_plain_reconciled_audit(tmp_path, monkeypatch):
    inputs, path, api, state = setup_state(tmp_path)
    monkeypatch.setattr(stage931, "CTP_QUERY_INTERVAL_SECONDS", 0)
    with stage931._instrument_ctp_readiness_callbacks(SealApi, state["rows"]):
        assert stage931._seal_owned_open_order(state, path, "CTP.1_2_3", max_wait_seconds=8)["confirmed"]
        append_execution_ledger_event({"event_type": "reconciled", "target_date": "2026-09-08",
            "intent_fingerprint": inputs["native_order_event"]["intent_fingerprint"], "vt_orderid": "CTP.1_2_3"}, path)
        api.day = "20260909"
        api.calls.clear()
        result = stage931._seal_owned_open_order(state, path, "CTP.1_2_3", max_wait_seconds=8)
    assert result["confirmed"] and result["reused"], result
    assert not api.calls


def test_reuse_cannot_clear_poison_received_during_revalidation(tmp_path, monkeypatch):
    import qmt_roll_official_live_broker_open_date_seal as seal_module
    inputs, path, api, state = setup_state(tmp_path)
    monkeypatch.setattr(stage931, "CTP_QUERY_INTERVAL_SECONDS", 0)
    with stage931._instrument_ctp_readiness_callbacks(SealApi, state["rows"]):
        assert stage931._seal_owned_open_order(state, path, "CTP.1_2_3", max_wait_seconds=8)["confirmed"]
        original = seal_module.build_open_date_seals

        def inject(**kwargs):
            result = original(**kwargs)
            api.onRspQryInvestorPositionDetail({}, {}, kwargs["query_bundle"]["queries"]["position_details"]["reqid"], True)
            return result

        monkeypatch.setattr(seal_module, "build_open_date_seals", inject)
        result = stage931._seal_owned_open_order(state, path, "CTP.1_2_3", max_wait_seconds=8)
    assert not result["confirmed"]
    assert state["open_date_seal_pending"]
    assert any(row["event_type"] == "broker_position_open_date_seal_conflict" for row in read_execution_ledger(path))


def test_partial_two_fill_append_recovers_missing_seal(tmp_path, monkeypatch):
    inputs, unused_path, api, state = setup_state(tmp_path)
    path = tmp_path / "two-fill-ledger"
    for row in inputs["execution_ledger_rows"]:
        if row["event_type"] != "filled_or_part_filled":
            append_execution_ledger_event(row, path)
    fill = inputs["execution_ledger_rows"][1]
    for tradeid in ("T1", "T2"):
        append_broker_callback_event_once({**fill, "broker_callback_key": tradeid, "tradeid": tradeid,
            "vt_tradeid": f"CTP.{tradeid}", "trade_fill_key": f"ctp:CZCE:{tradeid}", "volume": 1, "trade_volume_delta": 1}, path)
    for name in ("trades", "position_details"):
        callbacks = api.inputs["query_bundle"]["queries"][name]["callbacks"]
        callbacks[0]["data"]["Volume"] = 1
        second = copy.deepcopy(callbacks[0])
        second["data"]["TradeID"] = "T2"
        callbacks.insert(1, second)
    append = stage931.append_broker_callback_event_once

    def fail_second(event, ledger_path):
        if event.get("event_type") == "broker_position_open_date_sealed" and event.get("tradeid") == "T2":
            return {"blocker": "injected_disk_failure"}
        return append(event, ledger_path)

    monkeypatch.setattr(stage931, "CTP_QUERY_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(stage931, "append_broker_callback_event_once", fail_second)
    with stage931._instrument_ctp_readiness_callbacks(SealApi, state["rows"]):
        first = stage931._seal_owned_open_order(state, path, "CTP.1_2_3", max_wait_seconds=8)
        saved = [row for row in read_execution_ledger(path) if row["event_type"] == "broker_position_open_date_sealed"]
        assert not first["confirmed"] and len(saved) == 1, first
        monkeypatch.setattr(stage931, "append_broker_callback_event_once", append)
        result = stage931._seal_owned_open_order(state, path, "CTP.1_2_3", max_wait_seconds=8)
        assert result["confirmed"], result
    final = [row for row in read_execution_ledger(path) if row["event_type"] == "broker_position_open_date_sealed"]
    assert len(final) == 2 and saved[0] in final


def test_single_open_child_constraint_does_not_change_requests():
    request = stage931.OrderRequest(symbol="SH611", exchange=stage931.Exchange.CZCE,
                                   direction=stage931.Direction.LONG, offset=stage931.Offset.OPEN,
                                   volume=2, price=1948, type=stage931.OrderType.FAK)
    row = {"source": "stage901_pending_order"}
    assert stage931._open_date_preinsert_blockers(row, [request, request])
    assert request.volume == 2
    request.offset = stage931.Offset.CLOSE
    assert stage931._open_date_preinsert_blockers(row, [request, request]) == []


def test_cold_open_rejected_before_send():
    request = stage931.OrderRequest(symbol="SH611", exchange=stage931.Exchange.CZCE,
                                   direction=stage931.Direction.LONG, offset=stage931.Offset.OPEN,
                                   volume=2, price=1948, type=stage931.OrderType.FAK)
    assert stage931._open_date_preinsert_blockers({"source": "stage901_pending_order"}, [request], cold=True)


@pytest.mark.parametrize("event_type", ["broker_trade_callback_unbound", "broker_trade_callback_unidentified",
    "broker_trade_ownership_metadata_conflict", "broker_position_open_date_seal_conflict"])
@pytest.mark.parametrize("symbol", ["sh611.czce", None, "", "  ", 42])
def test_unsealable_history_blocks_open_not_protective_close(tmp_path, event_type, symbol):
    path = tmp_path / "history"
    append_broker_callback_event_once({"event_type": event_type, "vt_symbol": symbol,
        "broker_callback_key": "history", "target_date": "2026-09-08"}, path)
    row = {"source": "stage901_pending_order", "vt_symbol": "SH611.CZCE"}
    assert stage931._open_date_history_blockers(row, "open", read_execution_ledger(path))
    assert stage931._open_date_history_blockers(row, "close", read_execution_ledger(path)) == []


def test_other_symbol_history_does_not_block_target_open(tmp_path):
    path = tmp_path / "history"
    append_broker_callback_event_once({"event_type": "broker_position_open_date_seal_conflict",
        "vt_symbol": "rb2610.SHFE", "broker_callback_key": "history", "target_date": "2026-09-08"}, path)
    assert stage931._open_date_history_blockers({"source": "stage901_pending_order", "vt_symbol": "SH611.CZCE"},
                                              "open", read_execution_ledger(path)) == []


def test_frozen_flat_proof_does_not_absorb_later_rows(tmp_path):
    inputs, path, api, state = setup_state(tmp_path)
    native = inputs["native_order_event"]
    proof = copy.deepcopy(inputs["flat_baseline_event"]["proof"])
    requests = [stage931.OrderRequest(symbol="SH611", exchange=stage931.Exchange.CZCE,
                direction=stage931.Direction.LONG, offset=stage931.Offset.OPEN, volume=4, price=1948,
                type=stage931.OrderType.FAK, reference="Stage905PhaseD:intent")]
    baseline = stage931._make_open_date_flat_baseline(native, requests, proof, "batch", inputs["account_fingerprint"])
    proof["queries"]["positions"]["callbacks"][0]["data"] = {"Position": 99}
    assert baseline["proof"]["queries"]["positions"]["callbacks"][0]["data"] == {}


def test_terminal_zero_fill_clears_only_after_complete_raw_zero_proof(tmp_path, monkeypatch):
    inputs, unused_path, api, state = setup_state(tmp_path)
    path = tmp_path / "zero-ledger"
    append_broker_callback_event_once(inputs["native_order_event"], path)
    for name in ("order_before", "order_after"):
        api.inputs["query_bundle"]["queries"][name]["callbacks"][0]["data"].update(VolumeTraded=0, VolumeTotal=4)
    for name in ("trades", "position_details", "positions"):
        api.inputs["query_bundle"]["queries"][name]["callbacks"] = [api.inputs["query_bundle"]["queries"][name]["callbacks"][-1]]
    monkeypatch.setattr(stage931, "CTP_QUERY_INTERVAL_SECONDS", 0)
    with stage931._instrument_ctp_readiness_callbacks(SealApi, state["rows"]):
        result = stage931._seal_owned_open_order(state, path, "CTP.1_2_3", max_wait_seconds=8)
    assert result["confirmed"] and result["zero_exposure"], result
    assert not state["open_date_seal_pending"]
    assert any(row["event_type"] == "broker_open_zero_exposure_reconciled" for row in read_execution_ledger(path))


def test_before_native_unknown_is_not_zero_exposure(tmp_path, monkeypatch):
    inputs, unused_path, api, state = setup_state(tmp_path)
    path = tmp_path / "unaccepted-ledger"
    append_broker_callback_event_once(inputs["native_order_event"], path)
    for query in api.inputs["query_bundle"]["queries"].values():
        query["callbacks"] = [query["callbacks"][-1]]
    monkeypatch.setattr(stage931, "CTP_QUERY_INTERVAL_SECONDS", 0)
    with stage931._instrument_ctp_readiness_callbacks(SealApi, state["rows"]):
        result = stage931._seal_owned_open_order(state, path, "CTP.1_2_3", max_wait_seconds=8)
    assert not result["confirmed"]
    assert state["open_date_seal_pending"]


@pytest.mark.parametrize("fault", [None, "late", "durable_poison", "fill", "fill_without_event", "connection",
                                  "front", "account", "trading_day", "query", "native", "deadline"])
def test_zero_reuse_revalidates_commit_boundary(tmp_path, monkeypatch, fault):
    inputs, unused_path, api, state = setup_state(tmp_path)
    path = tmp_path / "zero-reuse"
    append_broker_callback_event_once(inputs["native_order_event"], path)
    for name in ("order_before", "order_after"):
        inputs["query_bundle"]["queries"][name]["callbacks"][0]["data"].update(VolumeTraded=0, VolumeTotal=4)
    for name in ("trades", "position_details", "positions"):
        inputs["query_bundle"]["queries"][name]["callbacks"] = [inputs["query_bundle"]["queries"][name]["callbacks"][-1]]
    monkeypatch.setattr(stage931, "CTP_QUERY_INTERVAL_SECONDS", 0)
    original = stage931._validate_open_date_zero_exposure
    clock = time.monotonic

    def inject(native, bundle, fingerprint):
        original(native, bundle, fingerprint)
        if fault == "late":
            api.onRspQryInvestorPositionDetail({}, {}, bundle["queries"]["position_details"]["reqid"], True)
        elif fault == "durable_poison":
            append_execution_ledger_event({"event_type": "broker_position_open_date_seal_conflict", "vt_symbol": native["vt_symbol"],
                                          "target_date": native["target_date"]}, path)
        elif fault in {"fill", "fill_without_event"}:
            append_broker_callback_event_once(inputs["execution_ledger_rows"][1], path)
            if fault == "fill":
                state["rows"]["_execution_event_ingress_counts"]["trade"] += 1
        elif fault == "connection":
            state["connection_generation"] = "changed"
        elif fault == "front":
            api.frontid += 1
        elif fault == "account":
            api.userid = "changed"
        elif fault == "trading_day":
            api.day = "20260909"
        elif fault == "query":
            api.reqid += 1
        elif fault == "native":
            stage931._increment_native_order_api_call_count(state["rows"], "send_order_api_called_count")
        elif fault == "deadline":
            monkeypatch.setattr(stage931.time, "monotonic", lambda: clock() + 20)

    with stage931._instrument_ctp_readiness_callbacks(SealApi, state["rows"]):
        assert stage931._seal_owned_open_order(state, path, "CTP.1_2_3", max_wait_seconds=8)["confirmed"]
        if fault is None:
            api.day = "20260909"
        api.calls.clear()
        monkeypatch.setattr(stage931, "_validate_open_date_zero_exposure", inject)
        result = stage931._seal_owned_open_order(state, path, "CTP.1_2_3", max_wait_seconds=8)
    assert not api.calls
    if fault is None:
        assert result["confirmed"] and result["reused"], result
        assert not state["open_date_seal_pending"]
    else:
        assert not result["confirmed"], result
        assert stage931._open_date_risk_blockers(state, "open")


def test_late_detail_after_builder_poison_is_durable(tmp_path, monkeypatch):
    import qmt_roll_official_live_broker_open_date_seal as seal_module
    inputs, path, api, state = setup_state(tmp_path)
    original = seal_module.build_open_date_seals

    def inject(**kwargs):
        result = original(**kwargs)
        reqid = kwargs["query_bundle"]["queries"]["position_details"]["reqid"]
        api.onRspQryInvestorPositionDetail({}, {}, reqid, True)
        return result

    monkeypatch.setattr(seal_module, "build_open_date_seals", inject)
    monkeypatch.setattr(stage931, "CTP_QUERY_INTERVAL_SECONDS", 0)
    with stage931._instrument_ctp_readiness_callbacks(SealApi, state["rows"]):
        result = stage931._seal_owned_open_order(state, path, "CTP.1_2_3", max_wait_seconds=8)
    assert not result["confirmed"]
    assert any(row["event_type"] == "broker_position_open_date_seal_conflict" for row in read_execution_ledger(path))


def test_append_over_deadline_poison_is_durable(tmp_path, monkeypatch):
    inputs, path, api, state = setup_state(tmp_path)
    original_append = stage931.append_broker_callback_event_once
    original_clock = time.monotonic

    def inject(event, path):
        result = original_append(event, path)
        if event.get("event_type") == "broker_position_open_date_sealed":
            monkeypatch.setattr(stage931.time, "monotonic", lambda: original_clock() + 20)
        return result

    monkeypatch.setattr(stage931, "append_broker_callback_event_once", inject)
    monkeypatch.setattr(stage931, "CTP_QUERY_INTERVAL_SECONDS", 0)
    with stage931._instrument_ctp_readiness_callbacks(SealApi, state["rows"]):
        result = stage931._seal_owned_open_order(state, path, "CTP.1_2_3", max_wait_seconds=8)
    assert not result["confirmed"]
    assert state["open_date_seal_pending"]
    assert any(row["event_type"] == "broker_position_open_date_seal_conflict" for row in read_execution_ledger(path))


@pytest.mark.parametrize("exchange,symbol,recover,baseline_fault", [("CZCE", "SH611", False, None),
    ("SHFE", "rb2610", False, None), ("SHFE", "rb2610", True, None),
    ("CZCE", "SH611", False, "before_native"), ("CZCE", "SH611", False, "after_native")])
def test_warm_factory_frozen_flat_funds_gap_native_trade_worker(tmp_path, monkeypatch, exchange, symbol, recover, baseline_fault):
    from qmt_roll_official_live_execution_service import ExecutorServicePaths
    from qmt_roll_official_live_runtime_profile import ExecutionRuntimeProfile, OrderScope, resolve_runtime_profile
    inputs = make_seal_inputs()
    restarting = False
    vt_symbol = f"{symbol}.{exchange}"
    for query in inputs["query_bundle"]["queries"].values():
        for callback in query["callbacks"]:
            if callback["data"]:
                callback["data"].update(InstrumentID=symbol, ExchangeID=exchange)
    paths = ExecutorServicePaths.for_spool(spool_path=tmp_path / "spool", ledger_path=tmp_path / "ledger")
    runtime = resolve_runtime_profile(profile=ExecutionRuntimeProfile.SIMNOW, order_scope=OrderScope.TEST,
                                      repo_root=Path(__file__).resolve().parents[1], output_root=tmp_path / "runtime")

    class Events:
        def __init__(self):
            self.handlers = {}

        def register(self, kind, handler):
            self.handlers.setdefault(kind, []).append(handler)

        def unregister(self, *args):
            pass

        def emit(self, kind, data):
            for handler in self.handlers.get(kind, []):
                handler(SimpleNamespace(data=data))

    class Api(SealApi):
        frontid = 1
        sessionid = 2

        def __init__(self, gateway):
            super().__init__(inputs)
            self.gateway = gateway
            self.flat = not restarting
            self.native_calls = 0

        def emit(self, name, callback, reqid):
            if self.flat and name in {"order_before", "positions", "order_after"}:
                self.calls.append((name, reqid))
                callback({}, {}, reqid, True)
                return 0
            return super().emit(name, callback, reqid)

        def reqQryTradingAccount(self, request, reqid):
            self.calls.append(("funds", reqid))
            self.onRspQryTradingAccount({"BrokerID": "broker", "AccountID": "account", "CurrencyID": "CNY",
                "Balance": 500000.0, "Available": 500000.0, "CurrMargin": 0.0, "FrozenMargin": 0.0,
                "FrozenCash": 0.0, "FrozenCommission": 0.0}, {}, reqid, True)
            return 0

        def reqQryMaxOrderVolume(self, request, reqid):
            self.calls.append(("max_volume", reqid))
            self.onRspQryMaxOrderVolume({**request, "MaxVolume": 100}, {}, reqid, True)
            return 0

        def reqOrderInsert(self, request, reqid):
            self.native_calls += 1
            return 0

        def onRtnTrade(self, raw):
            self.gateway.on_trade(SimpleNamespace(vt_symbol=vt_symbol, symbol=symbol, exchange=stage931.Exchange(exchange),
                tradeid=raw["TradeID"], vt_tradeid=f"CTP.{raw['TradeID']}", vt_orderid="CTP.1_2_3", orderid="1_2_3",
                direction=stage931.Direction.LONG, offset=stage931.Offset.OPEN, price=raw["Price"], volume=raw["Volume"],
                datetime=datetime.fromisoformat("2026-09-07T21:30:00+08:00")))

    class Gateway:
        def __init__(self, events):
            self.events = events
            self.td_api = Api(self)

        def on_tick(self, data):
            self.events.emit(stage931.EVENT_TICK, data)

        def on_order(self, data):
            self.events.emit(stage931.EVENT_ORDER, data)

        def on_trade(self, data):
            self.events.emit(stage931.EVENT_TRADE, data)

        def on_position(self, data):
            self.events.emit(stage931.EVENT_POSITION, data)

    class Engine:
        def __init__(self, events):
            self.gateway = Gateway(events)

        def add_gateway(self, cls):
            return self.gateway

        def close(self):
            pass

    package = ModuleType("vnpy_ctp")
    package.CtpGateway = Gateway
    gateway_package = ModuleType("vnpy_ctp.gateway")
    gateway_package.ctp_gateway = SimpleNamespace(CtpTdApi=Api)
    monkeypatch.setitem(sys.modules, "vnpy_ctp", package)
    monkeypatch.setitem(sys.modules, "vnpy_ctp.gateway", gateway_package)
    monkeypatch.setattr(stage931, "EventEngine", Events)
    monkeypatch.setattr(stage931, "MainEngine", Engine)
    monkeypatch.setattr(stage931, "_connect_ctp_without_timer_queries", lambda *args: None)
    monkeypatch.setattr(stage931, "_wait_for_ctp_readiness", lambda *args, **kwargs: (True, [], {}, stage931.CtpReadinessState(account_required=True)))
    monkeypatch.setattr(stage931, "CTP_QUERY_INTERVAL_SECONDS", 0)
    session = stage931._build_stage179_warm_ctp_session(SimpleNamespace(target_date="2026-09-08", connect_wait_seconds=0,
        final_order_query_wait_seconds=8, fill_wait_seconds=0), runtime, paths)
    closure = dict(zip(session._send_order.__code__.co_freevars, [cell.cell_contents for cell in session._send_order.__closure__]))
    state = closure["state"]
    state["connection_generation"] = "original"
    assert session._connect_startup_bundle()["ready"]
    try:
        rows, api = state["rows"], state["td_api"]
        rows["_open_date_service_generation"] = session.service_generation
        rows["_open_date_connection_generation"] = "original"
        snapshot = stage931._final_pre_send_snapshot_epoch(api, rows, max_wait_seconds=8)
        assert snapshot["confirmed"], snapshot
        request = stage931.OrderRequest(symbol=symbol, exchange=stage931.Exchange(exchange), direction=stage931.Direction.LONG,
                    offset=stage931.Offset.OPEN, type=stage931.OrderType.FAK, volume=4, price=1948, reference="Stage905PhaseD:intent")
        funds = stage931._final_open_account_funds_query_epoch(api, rows, max_wait_seconds=3)
        assert funds["confirmed"], funds
        groups, blockers = stage931._physical_open_request_groups([request])
        assert not blockers
        capacity = stage931._final_open_max_order_volume_query_epoch(api, rows, groups[0], max_wait_seconds=3)
        assert capacity["confirmed"], capacity
        owner = {name: inputs["native_order_event"][name] for name in
                 ("target_date", "intent_fingerprint", "root_position_id", "position_epoch_id", "vt_symbol", "source", "direction", "offset")}
        owner.update(position_cycle_id="cycle", intent_role="c9_initial_open", intent_id="intent",
                     spool_lease_owner=session.service_generation, spool_lease_token="lease",
                     intent_payload_sha256="a" * 64, intent_kind="open", vt_symbol=vt_symbol)
        reserved = reserve_execution_ledger_intent(target_date="2026-09-08", row=owner,
            order_request={"symbol": symbol, "exchange": exchange, "vt_symbol": vt_symbol, "direction": "long",
                           "offset": "open", "volume": 4, "price": 1948, "reference": request.reference},
            close_retry_after_cancel_seconds=30, path=paths.ledger_path, base_event=owner)
        assert reserved["reserved"], reserved
        owner["intent_fingerprint"] = reserved["intent_fingerprint"]
        native = {**owner, "intent_id": "intent", "service_generation": session.service_generation,
                  "connection_generation": "original", "price": 1948, "volume": 4, "child_order_index": 0, "child_order_count": 1,
                  "child_order_id": "child", "reservation_record_checksum": reserved["latest_ledger_event"]["record_checksum"],
                  "account_fingerprint": inputs["account_fingerprint"]}
        baseline = stage931._make_open_date_flat_baseline(native, [request], snapshot["open_date_envelope"], "batch", inputs["account_fingerprint"])
        native.update(physical_batch_id="batch", flat_baseline_event=baseline, flat_baseline_sha256=stage931._canonical_evidence_sha256(baseline))
        child = {"row": owner, "target_date": "2026-09-08", "intent_id": "intent", "fingerprint": owner["intent_fingerprint"],
                 "request": request, "service_generation": session.service_generation, "connection_generation": "original",
                 "spool_lease_owner": session.service_generation, "spool_lease_token": "lease",
                 "child_order_index": 0, "child_order_count": 1, "child_order_id": "child"}
        state.update(native_insert_context=native, native_child_context=child,
                     active_physical_batch={"batch_id": "batch", "owned_children": {}})

        def native_gate(td_api, raw, reqid):
            assert baseline["proof"]["event_watermark_after"] == stage931._execution_event_watermark(rows)
            assert baseline["proof"]["native_api_watermark_after"] == stage931._native_order_api_count_snapshot(rows)
            assert reqid > baseline["proof"]["query_watermark_after"]["reqid"] + 1
            return []

        state["native_dynamic_gate"] = native_gate
        if baseline_fault == "before_native":
            original_watermark = stage931._execution_event_watermark(rows)
            original_reqid = api.reqid
            api.onRspQryOrder({**inputs["query_bundle"]["queries"]["order_before"]["callbacks"][0]["data"], "OrderStatus": "1"},
                              {}, snapshot["order_q1"]["reqid"], True)
            assert stage931._execution_event_watermark(rows) == original_watermark and api.reqid == original_reqid
            api.reqid += 1
            with pytest.raises(stage931.BrokerSendBatchError, match="flat.*watch"):
                api.reqOrderInsert({"OrderRef": "3"}, api.reqid)
            assert api.native_calls == 0
            assert not any(row["event_type"] == "broker_position_open_date_seal_conflict" for row in read_execution_ledger(paths.ledger_path))
            snapshot = stage931._final_pre_send_snapshot_epoch(api, rows, max_wait_seconds=8)
            assert snapshot["confirmed"], snapshot
            assert stage931._final_open_account_funds_query_epoch(api, rows, max_wait_seconds=3)["confirmed"]
            assert stage931._final_open_max_order_volume_query_epoch(api, rows, groups[0], max_wait_seconds=3)["confirmed"]
            baseline = stage931._make_open_date_flat_baseline(native, [request], snapshot["open_date_envelope"], "batch", inputs["account_fingerprint"])
            native.update(flat_baseline_event=baseline, flat_baseline_sha256=stage931._canonical_evidence_sha256(baseline))
        api.reqid += 1
        assert api.reqOrderInsert({"OrderRef": "3"}, api.reqid) == 0
        assert api.native_calls == 1
        persisted = [row for row in read_execution_ledger(paths.ledger_path) if row["event_type"] == "native_order_identity_persisted_before_insert"][0]
        assert persisted["native_api_watermark"]["send_order_api_called_count"] == 0
        api.flat = False
        api.onRtnTrade(inputs["query_bundle"]["queries"]["trades"]["callbacks"][0]["data"])
        real_seal = stage931._seal_owned_open_order
        if recover:
            monkeypatch.setattr(stage931, "_seal_owned_open_order", lambda *_args, **_kwargs: {"confirmed": False})
        state["gateway"].on_order(SimpleNamespace(vt_symbol=vt_symbol, vt_orderid="CTP.1_2_3", direction="long", offset="open",
                                                  volume=4, traded=2, status="已撤销", reference="Stage905PhaseD:intent"))
        until = time.monotonic() + 10
        while state["open_date_seal_workers"] and time.monotonic() < until:
            time.sleep(0.02)
        if recover:
            assert state["open_date_seal_pending"]
            assert not any(row["event_type"] == "broker_position_open_date_sealed" for row in read_execution_ledger(paths.ledger_path))
            session._disconnect_transport()
            restarting = True
            monkeypatch.setattr(stage931, "_seal_owned_open_order", real_seal)
            session = stage931._build_stage179_warm_ctp_session(SimpleNamespace(target_date="2026-09-08", connect_wait_seconds=0,
                final_order_query_wait_seconds=8, fill_wait_seconds=0), runtime, paths)
            closure = dict(zip(session._send_order.__code__.co_freevars, [cell.cell_contents for cell in session._send_order.__closure__]))
            state = closure["state"]
            state["connection_generation"] = "restarted"
            assert session._connect_startup_bundle()["ready"]
            until = time.monotonic() + 10
            while state["open_date_seal_workers"] and time.monotonic() < until:
                time.sleep(0.02)
            rows, api = state["rows"], state["td_api"]
            assert api.native_calls == 0
        assert not state["open_date_seal_pending"], state["open_date_seal_pending"]
        seals = [row for row in read_execution_ledger(paths.ledger_path) if row["event_type"] == "broker_position_open_date_sealed"]
        assert len(seals) == 1
        assert seals[0]["broker_open_date"] == "2026-09-08"
        assert seals[0]["broker_trade_date"] == "2026-09-07"
        if baseline_fault == "after_native":
            api.onRspQryOrder({**inputs["query_bundle"]["queries"]["order_before"]["callbacks"][0]["data"], "OrderStatus": "1"},
                              {}, snapshot["order_q1"]["reqid"], True)
            assert any(row["event_type"] == "broker_position_open_date_seal_conflict" for row in read_execution_ledger(paths.ledger_path))
            refused = stage931._seal_owned_open_order(state, paths.ledger_path, "CTP.1_2_3", max_wait_seconds=8)
            assert not refused["confirmed"] and state["open_date_seal_pending"]
            return
        persisted_ledger = read_execution_ledger(paths.ledger_path)
        assert persisted_ledger == json.loads("[" + ",".join(paths.ledger_path.read_text().splitlines()) + "]")
        api.day = "20260909"
        for name in ("order_before", "trades", "order_after"):
            inputs["query_bundle"]["queries"][name]["callbacks"] = [
                {"data": {}, "error": {}, "last": True}]
        detail = inputs["query_bundle"]["queries"]["position_details"]["callbacks"][0]["data"]
        detail["TradingDay"] = "20260909"
        position = inputs["query_bundle"]["queries"]["positions"]["callbacks"][0]["data"]
        position.update(TradingDay="20260909", PositionDate="2", TodayPosition=0, YdPosition=2,
                        LongFrozen=0, ShortFrozen=0, UseMargin=1000)
        rows["positions"] = [stage931._raw_ctp_position_row(position, reqid=api.reqid, vt_symbol_by_instrument={})]
        audit = {"mode": "full_close", "volume": 2, "broker_gross_volume": 2, "owned_net_volume": 2,
                 "shadow_volume": 4, "shadow_position_volume": 4, "vt_symbol": vt_symbol, "position_direction": "long",
                 "root_position_id": owner["root_position_id"], "position_epoch_id": owner["position_epoch_id"],
                 "account_fingerprint": inputs["account_fingerprint"], "target_date": "2026-09-09"}
        payload = {"broker_close_sizing": audit, "vt_symbol": vt_symbol, "direction": "short", "offset": "close",
                   "volume": 2, "price": 1948}
        close_row = {**payload, "target_date": "2026-09-09", "planned_volume": 2, "source": "stage901_pending_order",
                     "execution_profile": "c9-15w", "order_request": copy.deepcopy(payload), "order_request_json": json.dumps(payload)}
        close = stage931.OrderRequest(symbol=symbol, exchange=stage931.Exchange(exchange), direction=stage931.Direction.SHORT,
                    offset=stage931.Offset.CLOSE, type=stage931.OrderType.LIMIT, volume=2, price=1948)
        initial = {"canonical_positions": stage931._canonical_position_snapshot(rows["positions"]),
                   "event_watermark_before_q2": stage931._execution_event_watermark(rows),
                   "event_watermark_after_q2": stage931._execution_event_watermark(rows)}
        monkeypatch.setattr(stage931, "_final_ctp_transport_blockers", lambda *_args: [])
        monkeypatch.setattr(stage931, "_post_snapshot_final_reprice", lambda *_args, **_kwargs: {"final_reprice_status": "applied"})
        api.calls.clear()
        native_calls_before_close = api.native_calls
        gate = stage931._post_reprice_final_state_gate(state["main_engine"], api, rows, close_row, close,
            initial_snapshot=initial, initial_reprice_result={"final_reprice_status": "applied"}, max_tick_age_seconds=30,
            max_wait_seconds=8, hard_deadline_monotonic=time.monotonic() + 8,
            readiness_state=stage931.CtpReadinessState(account_required=False),
            query_lock=state["ctp_query_lock"], ledger_path=paths.ledger_path)
        assert gate["confirmed"], gate
        assert [name for name, _ in api.calls] == ["position_details", "trades", "order_before", "positions", "order_after"]
        proof = rows["_resized_close_proof"]
        assert proof["today_volume"] == 0 and proof["yesterday_volume"] == 2
        physical = copy.deepcopy(close)
        if exchange == "SHFE":
            physical.offset = stage931.Offset.CLOSEYESTERDAY
        funds = stage931._final_open_funds_margin_gate(api, rows, [physical], max_wait_seconds=0, intent_row=close_row)
        assert funds["confirmed"], funds
        assert physical.volume == 2 and api.native_calls == native_calls_before_close
        append_execution_ledger_event({"event_type": "broker_position_open_date_seal_conflict" if recover else "broker_trade_callback_unbound",
            "vt_symbol": vt_symbol, "target_date": "2026-09-09"}, paths.ledger_path)
        state["authorization_pin"] = {"record": {"state_revision": 0}}
        monkeypatch.setattr(stage931, "validate_submit_authorization", lambda **_kwargs: [])
        monkeypatch.setattr(stage931, "_kill_switch_blockers", lambda: [])
        open_payload = {"symbol": symbol, "exchange": exchange, "vt_symbol": vt_symbol, "direction": "long",
                        "offset": "open", "type": "FAK", "volume": 4, "price": 1948}
        lease = SimpleNamespace(intent=SimpleNamespace(payload={**owner, "order_request": open_payload}, intent_id="next-open",
            state_revision=1, state="leased", lease_owner=session.service_generation, target_date="2026-09-09"))
        api.calls.clear()
        ledger_before = paths.ledger_path.read_bytes()
        blocked = session._fresh_bundle(lease, time.monotonic() + 8)
        assert any("history_unsealable" in blocker for blocker in blocked["blockers"]), blocked
        assert not api.calls and api.native_calls == native_calls_before_close
        assert paths.ledger_path.read_bytes() == ledger_before
    finally:
        session._disconnect_transport()
