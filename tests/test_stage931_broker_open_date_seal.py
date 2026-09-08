from __future__ import annotations

import copy
from dataclasses import asdict
import hashlib
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
from vnpy.trader.constant import Status
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
    closing = baseline_fault in {"close_authorized", "close_authorization_missing", "close_authorization_revoked"}
    authorized = closing or baseline_fault in {"authorized", "authorization_missing", "authorization_revoked"}
    vt_symbol = f"{symbol}.{exchange}"
    for query in inputs["query_bundle"]["queries"].values():
        for callback in query["callbacks"]:
            if callback["data"]:
                callback["data"].update(InstrumentID=symbol, ExchangeID=exchange)
    paths = ExecutorServicePaths.for_spool(spool_path=tmp_path / "spool", ledger_path=tmp_path / "ledger")
    runtime = resolve_runtime_profile(profile=ExecutionRuntimeProfile.SIMNOW, order_scope=OrderScope.TEST,
                                      repo_root=Path(__file__).resolve().parents[1], output_root=tmp_path / "runtime")
    if closing:
        from qmt_roll_official_live_broker_open_date_seal import build_open_date_seals

        for row in inputs["execution_ledger_rows"]:
            append_execution_ledger_event(row, paths.ledger_path)
        for seal in build_open_date_seals(**inputs):
            append_execution_ledger_event(seal, paths.ledger_path)
        for name in ("order_before", "trades", "order_after"):
            inputs["query_bundle"]["queries"][name]["callbacks"] = [{"data": {}, "error": {}, "last": True}]
        inputs["query_bundle"]["queries"]["position_details"]["callbacks"][0]["data"]["TradingDay"] = "20260909"
        inputs["query_bundle"]["queries"]["positions"]["callbacks"][0]["data"].update(
            TradingDay="20260909", PositionDate="2", TodayPosition=0, YdPosition=2, LongFrozen=0, ShortFrozen=0, UseMargin=1000)

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
            self.flat = not restarting and not closing
            if closing:
                self.day = "20260909"
            self.native_calls = 0
            self.login_status = True
            self.contract_inited = True

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
            if authorized:
                self.gateway.on_account(SimpleNamespace(accountid="account", vt_accountid="CTP.account", balance=500000,
                                                        available=500000, frozen=0, gateway_name="CTP"))
            return 0

        def reqQryMaxOrderVolume(self, request, reqid):
            self.calls.append(("max_volume", reqid))
            self.onRspQryMaxOrderVolume({**request, "MaxVolume": 100}, {}, reqid, True)
            return 0

        def reqOrderInsert(self, request, reqid):
            if authorized:
                import sqlite3
                from qmt_roll_official_live_execution_ledger import _record_checksum

                durable = read_execution_ledger(paths.ledger_path)
                assert all(row["record_checksum"] == _record_checksum(row) for row in durable)
                current_intent_id = "authorized-close" if closing else "authorized-open"
                current = [row for row in durable if row.get("intent_id") == current_intent_id]
                native, = [row for row in current if row["event_type"] == "native_order_identity_persisted_before_insert"]
                reserved, = [row for row in current if row["event_type"] == "reserved"]
                slot, = [row for row in current if row["event_type"] == "api_slot_reserved"]
                assert native["reservation_record_checksum"] == reserved["record_checksum"]
                assert native["intent_id"] == reserved["intent_id"] == slot["intent_id"] == current_intent_id
                assert native["source"] == reserved["intent_payload"]["source"] == "stage901_pending_order"
                assert native["intent_fingerprint"] == reserved["intent_fingerprint"] == slot["intent_fingerprint"]
                assert native["spool_lease_token"] == reserved["spool_lease_token"] == slot["spool_lease_token"]
                assert native["intent_payload_sha256"] == reserved["intent_payload_sha256"] == slot["intent_payload_sha256"]
                assert slot["api_slot_type"] == "send_order" and slot["api_slot_reserved"] == 1
                assert native["req_order_insert_reqid"] == reqid and native["vt_orderid"] == ("CTP.1_2_4" if closing else "CTP.1_2_3")
                assert native["native_api_called"] == 0 and self.native_calls == 0
                with sqlite3.connect(f"file:{paths.spool_path}?mode=ro", uri=True) as observer:
                    observer.row_factory = sqlite3.Row
                    persisted = dict(observer.execute("SELECT * FROM intents WHERE intent_id=?", (current_intent_id,)).fetchone())
                assert persisted["state"] == "sending" and persisted["ledger_disposition"] == slot["api_slot_batch_id"]
                assert persisted["lease_token"] == native["spool_lease_token"]
                assert persisted["payload_sha256"] == native["intent_payload_sha256"]
                context = state["intent_contexts"][current_intent_id]
                assert time.monotonic() < context["hard_deadline_monotonic"]
                if closing:
                    batch, = [row for row in current if row["event_type"] == "physical_batch_lock_acquired"]
                    assert state["active_physical_batch"]["batch_id"] == batch["physical_batch_id"]
                    assert context["row"]["intent_role"] == native["intent_role"] == "c9_full_position_close"
                    assert context["row"]["broker_close_sizing"]["shadow_volume"] == 4
                    assert context["row"]["broker_close_sizing"]["volume"] == 2
                    assert context["open_funds_gate"]["broker_close_sizing_gate"]["yesterday_volume"] == 2
                    assert (request["VolumeTotalOriginal"], request["LimitPrice"], request["Direction"], request["CombOffsetFlag"], request["TimeCondition"]) == (2, 1937, "1", "1", "3")
                    assert not any(name in {"funds", "max_volume"} for name, _ in self.calls)
                else:
                    assert state["active_physical_batch"]["batch_id"] == native["physical_batch_id"]
                    assert native["flat_baseline_event"]["proof"] == context["open_date_flat_proof"]
                    assert (request["VolumeTotalOriginal"], request["LimitPrice"]) == (4, 1948)
            self.native_calls += 1
            return 0

        def onRtnTrade(self, raw):
            self.gateway.on_trade(SimpleNamespace(vt_symbol=vt_symbol, symbol=symbol, exchange=stage931.Exchange(exchange),
                tradeid=raw["TradeID"], vt_tradeid=f"CTP.{raw['TradeID']}",
                vt_orderid="CTP.1_2_4" if closing else "CTP.1_2_3", orderid="1_2_4" if closing else "1_2_3",
                gateway_name="CTP",
                direction=stage931.Direction.SHORT if closing else stage931.Direction.LONG,
                offset=stage931.Offset.CLOSE if closing else stage931.Offset.OPEN, price=raw["Price"], volume=raw["Volume"],
                datetime=datetime.fromisoformat("2026-09-08T21:30:00+08:00" if closing else "2026-09-07T21:30:00+08:00")))

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

        def on_log(self, data):
            self.events.emit(stage931.EVENT_LOG, data)

        def on_account(self, data):
            self.events.emit(stage931.EVENT_ACCOUNT, data)

    class Engine:
        def __init__(self, events):
            self.gateway = Gateway(events)

        def add_gateway(self, cls):
            return self.gateway

        def close(self):
            pass

        def get_contract(self, name):
            assert name == vt_symbol
            return SimpleNamespace(vt_symbol=vt_symbol, symbol=symbol, exchange=stage931.Exchange(exchange),
                                   gateway_name="CTP", pricetick=1, size=30)

        def subscribe(self, request, gateway_name):
            assert gateway_name == "CTP"
            self.gateway.on_tick(SimpleNamespace(vt_symbol=vt_symbol, symbol=symbol, exchange=stage931.Exchange(exchange),
                gateway_name="CTP", datetime=stage931.datetime.now(), last_price=1943, bid_price_1=1942, ask_price_1=1943,
                bid_volume_1=100, ask_volume_1=100, limit_down=1800, limit_up=2100))

        def get_tick(self, name):
            return None

        def send_order(self, request, gateway_name):
            assert authorized and gateway_name == "CTP"
            assert (request.vt_symbol, request.direction, request.offset, request.type, request.price, request.volume) == (
                (vt_symbol, stage931.Direction.SHORT, stage931.Offset.CLOSE, stage931.OrderType.LIMIT, 1937, 2) if closing
                else (vt_symbol, stage931.Direction.LONG, stage931.Offset.OPEN, stage931.OrderType.FAK, 1948, 4))
            assert request.reference == ("Stage905PhaseD:authorized-close" if closing else "Stage905PhaseD:authorized-open")
            api = self.gateway.td_api
            api.reqid += 1
            raw = {"BrokerID": "broker", "InvestorID": "account", "UserID": "account", "InstrumentID": symbol, "ExchangeID": exchange,
                   "OrderRef": "4" if closing else "3", "Direction": "1" if closing else "0", "CombOffsetFlag": "1" if closing else "0", "CombHedgeFlag": "1",
                   "LimitPrice": request.price, "VolumeTotalOriginal": request.volume,
                   "OrderPriceType": "2", "TimeCondition": "3" if closing else "1", "VolumeCondition": "1"}
            assert api.reqOrderInsert(raw, api.reqid) == 0
            api.flat = closing
            trade = {"BrokerID": "broker", "InvestorID": "account", "ExchangeID": exchange, "InstrumentID": symbol,
                "OrderSysID": "SYS2", "TradeID": "T2", "Direction": "1", "OffsetFlag": "1", "HedgeFlag": "1",
                "Price": request.price, "Volume": 2, "TradeDate": "20260908", "TradingDay": "20260909", "TradeTime": "21:30:00"} if closing else inputs["query_bundle"]["queries"]["trades"]["callbacks"][0]["data"]
            api.onRtnTrade(trade)
            vt_orderid = "CTP.1_2_4" if closing else "CTP.1_2_3"
            self.gateway.on_order(SimpleNamespace(vt_symbol=vt_symbol, vt_orderid=vt_orderid, gateway_name="CTP",
                direction=request.direction, offset=request.offset, price=request.price,
                volume=request.volume, traded=2, status=Status.ALLTRADED if closing else Status.CANCELLED, reference=request.reference))
            return vt_orderid

        def get_order(self, orderid):
            return SimpleNamespace(vt_symbol=vt_symbol, vt_orderid=orderid, direction="short" if closing else "long",
                offset="close" if closing else "open", volume=2 if closing else 4, traded=2,
                status=Status.ALLTRADED if closing else Status.CANCELLED,
                reference="Stage905PhaseD:authorized-close" if closing else "Stage905PhaseD:authorized-open")

    package = ModuleType("vnpy_ctp")
    package.CtpGateway = Gateway
    gateway_package = ModuleType("vnpy_ctp.gateway")
    gateway_package.ctp_gateway = SimpleNamespace(CtpTdApi=Api)
    monkeypatch.setitem(sys.modules, "vnpy_ctp", package)
    monkeypatch.setitem(sys.modules, "vnpy_ctp.gateway", gateway_package)
    monkeypatch.setattr(stage931, "EventEngine", Events)
    monkeypatch.setattr(stage931, "MainEngine", Engine)
    def connect_fake(main_engine, gateway, event_engine):
        for message in ("交易服务器连接成功", "交易服务器授权验证成功", "交易服务器登录成功"):
            gateway.on_log(SimpleNamespace(msg=message))
        gateway.td_api.onRspSettlementInfoConfirm({"BrokerID": "broker", "InvestorID": "account"}, {}, 1, True)

    monkeypatch.setattr(stage931, "_connect_ctp_without_timer_queries", connect_fake if authorized else lambda *args: None)
    if not authorized:
        monkeypatch.setattr(stage931, "_wait_for_ctp_readiness", lambda *args, **kwargs: (True, [], {}, stage931.CtpReadinessState(account_required=True)))
    monkeypatch.setattr(stage931, "CTP_QUERY_INTERVAL_SECONDS", 0)
    session = stage931._build_stage179_warm_ctp_session(SimpleNamespace(target_date="2026-09-09" if closing else "2026-09-08", connect_wait_seconds=4 if authorized else 0,
        final_order_query_wait_seconds=8, fill_wait_seconds=0, close_retry_after_cancel_seconds=30, final_reprice_tick_wait_seconds=1), runtime, paths)
    closure = dict(zip(session._send_order.__code__.co_freevars, [cell.cell_contents for cell in session._send_order.__closure__]))
    state = closure["state"]
    if authorized:
        startup = session._connect_startup_bundle

        def observed_startup():
            result = startup()
            assert result["ready"], result
            return result

        session._connect_startup_bundle = observed_startup
        session.connect()
    else:
        state["connection_generation"] = "original"
        assert session._connect_startup_bundle()["ready"]
    try:
        if authorized:
            _exercise_authorized_intent(session, state, paths, runtime, inputs, monkeypatch, baseline_fault)
            return
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
        owner.update(position_cycle_id="cycle", position_cycle_no=0,
                     state_generation="epoch:0", intent_role="c9_initial_open", intent_id="intent",
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
                 "position_cycle_id": owner["position_cycle_id"], "position_cycle_no": owner["position_cycle_no"],
                 "state_generation": owner["state_generation"],
                 "account_fingerprint": inputs["account_fingerprint"], "target_date": "2026-09-09"}
        payload = {"broker_close_sizing": audit, "vt_symbol": vt_symbol, "direction": "short", "offset": "close",
                   "volume": 2, "price": 1948, "intent_role": "c9_full_position_close",
                   "root_position_id": owner["root_position_id"], "position_epoch_id": owner["position_epoch_id"],
                   "position_cycle_id": owner["position_cycle_id"], "position_cycle_no": owner["position_cycle_no"],
                   "state_generation": owner["state_generation"]}
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


def test_authorized_spool_factory_to_seal_and_next_day_close(tmp_path, monkeypatch):
    test_warm_factory_frozen_flat_funds_gap_native_trade_worker(tmp_path, monkeypatch, "CZCE", "SH611", False, "authorized")


@pytest.mark.parametrize("fault", ["authorization_missing", "authorization_revoked"])
def test_authorized_spool_lease_rejects_lost_authorization_before_native(tmp_path, monkeypatch, fault):
    test_warm_factory_frozen_flat_funds_gap_native_trade_worker(tmp_path, monkeypatch, "CZCE", "SH611", False, fault)


@pytest.mark.parametrize("mode", ["close_authorized", "close_authorization_missing", "close_authorization_revoked"])
def test_normal_full_close_authorized_spool_to_native(tmp_path, monkeypatch, mode):
    test_warm_factory_frozen_flat_funds_gap_native_trade_worker(tmp_path, monkeypatch, "CZCE", "SH611", False, mode)


def _exercise_authorized_intent(session, state, paths, runtime, inputs, monkeypatch, authorization_mode):
    from qmt_roll_official_execution_profile import C9_15W_PROFILE
    from qmt_roll_official_live_broker_sizing import size_open_intent
    import qmt_roll_official_live_intent_spool as spool
    from qmt_roll_official_live_execution_service import SQLiteIntentSpool
    from qmt_roll_official_live_submit_authorization import publish_submit_authorization, revoke_submit_authorization, submit_authorization_path
    from test_official_live_intent_spool import OfficialLiveIntentSpoolTest
    from test_stage931_broker_sizing_gate import sizing_row
    closing = authorization_mode.startswith("close_")
    authorization_mode = authorization_mode.removeprefix("close_")
    target_date = "2026-09-09" if closing else "2026-09-08"
    if closing:
        until = time.monotonic() + 10
        while state["open_date_seal_workers"] and time.monotonic() < until:
            time.sleep(0.01)
        assert not state["open_date_seal_workers"]
        state["td_api"].calls.clear()
    historical_ledger = read_execution_ledger(paths.ledger_path)

    class SessionClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 8 if closing else 7, 21, 30, tzinfo=tz)

    monkeypatch.setattr(stage931, "datetime", SessionClock)
    epoch = time.time_ns()
    monotonic_ns = time.monotonic_ns()
    fixture = OfficialLiveIntentSpoolTest()
    intent = fixture.intent("authorized-open", deadline_epoch_ns=epoch + 25_000_000_000, position_epoch_id="epoch")
    trace = json.loads(intent["trace_json"])
    trace["vt_symbol"] = "SH611.CZCE"
    delta = monotonic_ns - epoch

    def rebase(value):
        if isinstance(value, dict):
            return {name: item + delta if "monotonic" in name and isinstance(item, int) else rebase(item) for name, item in value.items()}
        if isinstance(value, list):
            return [rebase(item) for item in value]
        return value

    intent["trace_json"] = json.dumps(rebase(trace))
    root = stage931.generate_root_position_id(target_date="2026-09-08", vt_symbol="SH611.CZCE", direction="long")
    cycle = stage931.generate_position_cycle_id(root_position_id=root, cycle_no=0)
    broker_inputs = sizing_row()["broker_sizing_inputs"]
    broker_inputs["signal"]["risk_ratio"] = 0.004
    broker_inputs["account"].update(equity=500000, available=500000, margin=0, frozen=0, product_margin={},
        account_fingerprint=inputs["account_fingerprint"], generated_at=datetime.now().astimezone().isoformat())
    audit = size_open_intent(**broker_inputs)
    assert audit["volume"] == 4, audit
    payload = json.loads(intent["spool_payload_json"])
    payload.update(target_date="2026-09-08", source="stage901_pending_order", vt_symbol="SH611.CZCE", direction="long", action_id="",
        root_position_id=root, position_cycle_id=cycle, position_cycle_no=0, intent_role="c9_initial_open", planned_volume=4,
        limit_price=1948, pricetick=1, protection_ticks=1, strategy_initial_stop_price=1933,
        ingress_epoch_ns=epoch, ingress_monotonic_ns=monotonic_ns,
        deadline_monotonic_ns=monotonic_ns + 25_000_000_000, execution_profile="c9-15w",
        broker_sizing=audit, broker_sizing_inputs=broker_inputs, official_live_version=C9_15W_PROFILE.official_version,
        capital=C9_15W_PROFILE.capital, capital_label=C9_15W_PROFILE.capital_label)
    payload["order_request"] = {**{name: payload[name] for name in (
        "intent_id", "action_id", "source", "target_date", "execution_profile", "official_live_version", "capital", "capital_label",
        "root_position_id", "position_epoch_id", "position_cycle_id", "position_cycle_no", "intent_role")},
        "symbol": "SH611", "exchange": "CZCE", "vt_symbol": "SH611.CZCE", "direction": "多",
        "offset": "开", "type": "FAK", "volume": 4, "price": 1948, "reference": "Stage905PhaseD:authorized-open",
        "broker_sizing": audit, "broker_sizing_inputs": broker_inputs, "strategy_initial_stop_price": 1933,
        "gateway_name": "CTP", "physical_tif_policy_version": "stage179_open_fak_v1"}
    if closing:
        from qmt_roll_official_live_broker_close_sizing import size_full_close_intent

        pending = {"vt_symbol": "SH611.CZCE", "direction": "short", "offset": "close", "volume": 4,
                   "traded": 0, "target_date": target_date, "price": 1937}
        cohort = stage931._canonical_evidence_sha256(pending)
        pending["cohort_id"] = cohort
        close_audit = size_full_close_intent(intent={**pending, "planned_volume": 4},
            pending_orders=stage931.pd.DataFrame([pending]),
            current_positions=stage931.pd.DataFrame([{"vt_symbol": "SH611.CZCE", "direction": "long", "date": target_date, "end_pos": 4}]),
            official_summary={"cohort_id": cohort, "analysis_end": target_date, "pending_orders": [pending]},
            broker_positions=stage931.pd.DataFrame([{"vt_symbol": "SH611.CZCE", "direction": "long", "volume": 2, "frozen": 0}]),
            execution_ledger_rows=historical_ledger, require_broker_trade_coverage=False)
        close_audit["account_fingerprint"] = inputs["account_fingerprint"]
        assert close_audit["volume"] == close_audit["owned_net_volume"] == 2 and close_audit["shadow_volume"] == 4
        payload.update(intent_id="authorized-close", target_date="2026-09-09", offset="close", direction="short",
                       intent_role="c9_full_position_close", planned_volume=2, limit_price=1937, strategy_initial_stop_price="",
                       broker_close_sizing=close_audit, shadow_planned_volume=4)
        payload.pop("broker_sizing")
        payload.pop("broker_sizing_inputs")
        payload["order_request"].update(intent_id="authorized-close", target_date="2026-09-09", offset="平", direction="空",
            intent_role="c9_full_position_close", volume=2, price=1937, type="限价", physical_tif_policy_version="stage179_limit_gfd_v1",
            reference="Stage905PhaseD:authorized-close", strategy_initial_stop_price="", broker_close_sizing=close_audit)
        payload["order_request"].pop("broker_sizing")
        payload["order_request"].pop("broker_sizing_inputs")
        for name in ("root_position_id", "position_cycle_id", "position_cycle_no", "position_epoch_id", "state_generation"):
            payload[name] = close_audit[name]
            payload["order_request"][name] = close_audit[name]
        payload.pop("strategy_initial_stop_price", None)
        payload["order_request"].pop("strategy_initial_stop_price", None)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    intent.update(payload)
    intent.update(spool_payload_json=encoded, payload_sha256=hashlib.sha256(encoded.encode()).hexdigest())
    connection = spool.open_spool(paths.spool_path)
    adapter = SQLiteIntentSpool(connection, ledger_path=paths.ledger_path)
    try:
        spool.commit_detector_batch(connection, consumer_id="stage941", expected_cursor=None, next_cursor=fixture.cursor(1),
            intents=[intent], now_epoch_ns=time.time_ns(), now_monotonic_ns=time.monotonic_ns(), clock_domain_id="boot-a")
        spool.record_trace_observation(connection, intent_id=intent["intent_id"], stage="spool_committed",
            epoch_ns=time.time_ns(), monotonic_ns=time.monotonic_ns(), clock_domain_id="boot-a")
        snapshot = spool.snapshot_authorizable_intents(connection, now_epoch_ns=time.time_ns(), now_monotonic_ns=time.monotonic_ns(), clock_domain_id="boot-a")
        assert snapshot.candidate is not None
        candidate = asdict(snapshot.candidate)
        auth_path = submit_authorization_path(runtime.output_root)

        def publish():
            now = time.time_ns()
            expires = min(now + 20_000_000_000, candidate["deadline_epoch_ns"])
            controller_evidence = {
                "target_date": target_date,
                "controller_status": (
                    "persistent_intraday_fast_ready"
                    if closing
                    else "phase_d_controller_live_real_ready_no_submit_step"
                ),
                "expires_epoch_ns": expires,
            }
            if not closing:
                controller_evidence.update(
                    stage905_executor_status="executor_dry_run_ready",
                    stage905_blocked_count=0,
                    stage905_ready_count=1,
                )
            stage927_evidence = {
                (
                    "reduce_close_submit_permitted"
                    if closing
                    else "real_submit_permitted"
                ): 1,
                "expires_epoch_ns": expires,
            }
            return publish_submit_authorization(path=auth_path, target_date=target_date, execution_profile="c9-15w",
                runtime_profile="simnow", order_scope="test", service_generation=session.service_generation,
                connection_generation=session.connection_generation, cycle_id="stage236-offline" if closing else "stage235-offline",
                authorization_lane="persistent_intraday_fast" if closing else "slow_controller",
                intent_scope="reduce_close_only" if closing else "all",
                authorized_intents=[candidate], issued_epoch_ns=now, expires_epoch_ns=expires,
                controller_evidence=controller_evidence,
                stage927_evidence=stage927_evidence,
                broker_gate_evidence={"status": "ready", "service_generation": session.service_generation,
                    "connection_generation": session.connection_generation, "expires_epoch_ns": expires},
                tick_watermark_evidence={"all_symbols_ready": 1, "expires_epoch_ns": expires}, spool_path=paths.spool_path,
                spool_snapshot_digest=snapshot.snapshot_digest, cursor_digest=snapshot.cursor_digest,
                stage902_evidence_digest=stage931._canonical_evidence_sha256({"allow_new_open": 1}),
                stage927_evidence_digest=stage931._canonical_evidence_sha256(stage927_evidence))

        api = state["td_api"]
        send_errors = []
        original_send = session._send_order

        def observed_send(lease):
            try:
                return original_send(lease)
            except Exception as error:
                send_errors.append(str(error))
                send_errors.append(repr(error.__cause__))
                raise

        session._send_order = observed_send
        assert "stage179_submit_authorization_missing" in session.pre_lease_blockers()
        assert api.native_calls == 0
        publish()
        with session.lease_execution_guard():
            authorized = session.pre_lease_authorized_intents()
            assert authorized == {candidate["intent_id"]: candidate["payload_sha256"]}
            lease = spool.lease_next(connection, owner_id=session.service_generation, now_epoch_ns=time.time_ns(),
                now_monotonic_ns=time.monotonic_ns(), clock_domain_id="boot-a", lease_seconds=30, authorized_intents=authorized)
            assert lease is not None and session.post_lease_blockers(lease) == []
            slot_callbacks = []

            def durable_slot(batch_id):
                slot_callbacks.append(batch_id)
                transitioned = adapter.mark_sending(lease, now_epoch_ns=time.time_ns(),
                    now_monotonic_ns=time.monotonic_ns(), clock_domain_id="boot-a", ledger_disposition=batch_id)
                return transitioned.state == "sending"

            if authorization_mode == "authorization_missing":
                auth_path.unlink()
            elif authorization_mode == "authorization_revoked":
                revoke_submit_authorization(auth_path, reason="stage235-offline-revocation", revoked_epoch_ns=time.time_ns())
            result = session.execute_spool_lease(lease=lease,
                hard_deadline_monotonic=time.monotonic() + 18, api_slot_durable=durable_slot)
            if authorization_mode != "authorized":
                expected = "stage179_submit_authorization_missing" if authorization_mode == "authorization_missing" else "stage179_submit_authorization_not_authorized"
                assert expected in result.blockers, result.blockers
                assert result.send_order_call_count == result.cancel_order_call_count == api.native_calls == 0
                assert not slot_callbacks and session.api_slot_call_count == 0
                assert read_execution_ledger(paths.ledger_path) == historical_ledger
                assert connection.execute("SELECT state FROM intents WHERE intent_id=?", (lease.intent.intent_id,)).fetchone()[0] == "leased"
                return
            assert result.disposition == "sent", "\n".join([*result.blockers, *send_errors])
            assert result.send_order_call_count == 1 and result.cancel_order_call_count == 0
            assert slot_callbacks == [result.api_slot_batch_id]
            assert adapter.mark_result(lease, result, now_epoch_ns=time.time_ns(), now_monotonic_ns=time.monotonic_ns(),
                                       clock_domain_id="boot-a").state == "sent"
        assert api.native_calls == 1
        if closing:
            current = [row for row in read_execution_ledger(paths.ledger_path) if row.get("intent_id") == "authorized-close"]
            native, = [row for row in current if row["event_type"] == "native_order_identity_persisted_before_insert"]
            fill, = [row for row in current if row["event_type"] == "filled_or_part_filled"]
            assert native["source"] == fill["source"] == "stage901_pending_order"
            assert stage931._normalize_offset_text(native["offset"]) == fill["offset"] == "close"
            for name in ("root_position_id", "position_epoch_id", "position_cycle_id", "position_cycle_no"):
                assert native[name] == fill[name] == close_audit[name]
            assert native["spool_lease_token"] == fill["spool_lease_token"] == lease.lease_token
            assert native["volume"] == fill["volume"] == 2 and fill["tradeid"] == "T2"
            assert native["order_type"] == stage931.OrderType.LIMIT.value and native["intent_role"] == "c9_full_position_close"
            assert not any(row["event_type"] == "broker_position_open_date_sealed" for row in current)
            assert [name for name, _ in api.calls] == ["order_before", "positions", "order_after", "position_details", "trades", "order_before", "positions", "order_after"]
            assert not any(row["event_type"] == "broker_trade_callback_unbound" for row in current)
            return
        until = time.monotonic() + 10
        while state["open_date_seal_workers"] and time.monotonic() < until:
            time.sleep(0.02)
        ledger = read_execution_ledger(paths.ledger_path)
        assert not state["open_date_seal_pending"], state["open_date_seal_pending"]
        native, = [row for row in ledger if row["event_type"] == "native_order_identity_persisted_before_insert"]
        fill, = [row for row in ledger if row["event_type"] == "filled_or_part_filled"]
        seal, = [row for row in ledger if row["event_type"] == "broker_position_open_date_sealed"]
        assert fill["volume"] == 2 and native["volume"] == payload["order_request"]["volume"] == audit["volume"] == 4
        assert fill["tradeid"] == "T1" and fill["fill_price_source"] == "event_trade_weighted_avg"
        assert fill["source"] == native["source"] == "stage901_pending_order"
        for row in (native, fill, seal):
            assert row["root_position_id"] == root and row["position_epoch_id"] == "epoch"
            assert row["vt_symbol"] == "SH611.CZCE" and row["vt_orderid"] == "CTP.1_2_3"
            assert row["intent_fingerprint"] == result.ledger_fingerprint
        assert seal["broker_trade_metadata_source"] == "ctp_query_open_date_seal_v1"
        assert seal["broker_trade_date"] == "2026-09-07" and seal["broker_open_date"] == seal["broker_trading_day"] == "2026-09-08"
        assert "broker_open_date" not in fill and "broker_trading_day" not in fill
        assert native["req_order_insert_reqid"] > native["flat_baseline_event"]["proof"]["queries"]["order_after"]["reqid"] + 1
        _assert_authorized_next_day_close(state, paths, inputs, root)
    finally:
        connection.close()


def _assert_authorized_next_day_close(state, paths, inputs, root):
    from qmt_roll_official_live_broker_close_sizing import size_full_close_intent
    from qmt_roll_official_live_broker_position_ownership import validate_position_detail_ownership

    ledger = [json.loads(line) for line in paths.ledger_path.read_text().splitlines()]
    assert ledger == read_execution_ledger(paths.ledger_path)
    api, rows = state["td_api"], state["rows"]
    api.day = "20260909"
    for name in ("order_before", "trades", "order_after"):
        inputs["query_bundle"]["queries"][name]["callbacks"] = [{"data": {}, "error": {}, "last": True}]
    detail = inputs["query_bundle"]["queries"]["position_details"]["callbacks"][0]["data"]
    detail["TradingDay"] = "20260909"
    position = inputs["query_bundle"]["queries"]["positions"]["callbacks"][0]["data"]
    position.update(TradingDay="20260909", PositionDate="2", TodayPosition=0, YdPosition=2,
                    LongFrozen=0, ShortFrozen=0, UseMargin=1000)
    proof = validate_position_detail_ownership(execution_ledger_rows=ledger, position_detail_rows=[detail],
        vt_symbol="SH611.CZCE", position_direction="long", broker_gross_volume=2,
        account_fingerprint=inputs["account_fingerprint"], trading_day="2026-09-09")
    assert proof["root_position_id"] == root and proof["position_epoch_id"] == "epoch"
    assert proof["owned_net_volume"] == proof["detail_volume"] == proof["yesterday_volume"] == 2
    assert proof["today_volume"] == 0
    pending = {"vt_symbol": "SH611.CZCE", "direction": "short", "offset": "close", "volume": 4,
               "traded": 0, "target_date": "2026-09-09"}
    cohort = stage931._canonical_evidence_sha256(pending)
    pending["cohort_id"] = cohort
    audit = size_full_close_intent(intent={**pending, "planned_volume": 4},
        pending_orders=stage931.pd.DataFrame([pending]),
        current_positions=stage931.pd.DataFrame([{"vt_symbol": "SH611.CZCE", "direction": "long", "date": "2026-09-09", "end_pos": 4}]),
        official_summary={"cohort_id": cohort, "analysis_end": "2026-09-09", "pending_orders": [pending]},
        broker_positions=stage931.pd.DataFrame([{"vt_symbol": "SH611.CZCE", "direction": "long", "volume": 2, "frozen": 0}]),
        execution_ledger_rows=ledger, broker_trade_rows=[])
    audit["account_fingerprint"] = inputs["account_fingerprint"]
    assert audit["volume"] == audit["owned_net_volume"] == 2 and audit["shadow_volume"] == 4
    payload = {
        "broker_close_sizing": audit,
        "vt_symbol": "SH611.CZCE",
        "direction": "short",
        "offset": "close",
        "volume": 2,
        "price": 1948,
        "intent_role": "c9_full_position_close",
        **{
            name: audit[name]
            for name in (
                "root_position_id",
                "position_epoch_id",
                "position_cycle_id",
                "position_cycle_no",
                "state_generation",
            )
        },
    }
    close_row = {**payload, "target_date": "2026-09-09", "planned_volume": 2, "pricetick": 1,
                 "source": "stage901_pending_order", "execution_profile": "c9-15w", "order_request": copy.deepcopy(payload)}
    request = stage931.OrderRequest(symbol="SH611", exchange=stage931.Exchange.CZCE, direction=stage931.Direction.SHORT,
        offset=stage931.Offset.CLOSE, type=stage931.OrderType.LIMIT, volume=2, price=1948)
    snapshot = stage931._final_pre_send_snapshot_epoch(api, rows, max_wait_seconds=8, readiness_state=state["readiness_state"])
    assert snapshot["confirmed"], snapshot
    reprice = stage931._post_snapshot_final_reprice(state["main_engine"], rows, close_row, request,
        max_tick_age_seconds=30, q2_completed_monotonic=snapshot["q2_completed_monotonic"], tick_wait_seconds=1)
    assert not stage931._final_reprice_blockers(reprice), reprice
    api.calls.clear()
    gate = stage931._post_reprice_final_state_gate(state["main_engine"], api, rows, close_row, request,
        initial_snapshot=snapshot, initial_reprice_result=reprice, max_tick_age_seconds=30,
        max_wait_seconds=8, hard_deadline_monotonic=time.monotonic() + 8,
        readiness_state=state["readiness_state"], query_lock=state["ctp_query_lock"], ledger_path=paths.ledger_path)
    assert gate["confirmed"], gate
    assert [name for name, _ in api.calls] == ["position_details", "trades", "order_before", "positions", "order_after"]
    assert rows["_resized_close_proof"]["today_volume"] == 0 and rows["_resized_close_proof"]["yesterday_volume"] == 2
    assert request.volume == 2 and api.native_calls == 1
