from __future__ import annotations

import copy
import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples/portfolio_backtesting"))
from qmt_roll_official_live_execution_ledger import append_broker_callback_event_once
from qmt_roll_official_live_execution_ledger import (
    append_pre_api_slot_no_side_effect_terminal, intent_fingerprint, read_execution_ledger,
    recover_expired_spool_lease, reserve_execution_ledger_intent,
)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def make_query_bundle(raw_rows, *, start=1000, first_reqid=10, connection="restarted"):
    account = {"BrokerID": "broker", "InvestorID": "account"}
    queries = {}
    for index, (name, data_rows) in enumerate(raw_rows.items()):
        reqid = first_reqid + index
        callbacks = [{"reqid": reqid, "last": False, "error": {}, "data": data,
                      "received_monotonic_ns": start + index * 10 + 1} for data in data_rows]
        callbacks.append({"reqid": reqid, "last": True, "error": {}, "data": {},
                          "received_monotonic_ns": start + index * 10 + 2})
        queries[name] = {"reqid": reqid, "request": dict(account), "request_ret": 0, "callbacks": callbacks,
                         "started_monotonic_ns": start + index * 10}
    events = {"event_order_count": 0, "event_trade_count": 0, "event_position_count": 0}
    native = {"send_order_api_called_count": 0, "cancel_order_api_called_count": 0,
              "order_api_called_count": 0, "order_api_evidence_complete": 1}
    return {"service_generation": "service", "connection_generation": connection,
            "trading_day_before": "2026-09-08", "trading_day_after": "2026-09-08",
            "started_monotonic_ns": start, "completed_monotonic_ns": start + 80,
            "deadline_monotonic_ns": start + 100,
            "max_window_ns": 100,
            "event_watermark_before": dict(events), "event_watermark_after": dict(events),
            "native_api_watermark_before": dict(native), "native_api_watermark_after": dict(native),
            "query_watermark_before": {"reqid": first_reqid - 1},
            "query_watermark_after": {"reqid": first_reqid + len(queries) - 1}, "queries": queries}


def make_seal_inputs(*, prior_safe_retry=False, prior_recovery=False):
    account = {"BrokerID": "broker", "InvestorID": "account"}
    identity = {**account, "ExchangeID": "CZCE", "InstrumentID": "SH611"}
    owner = {"target_date": "2026-09-08", "root_position_id": "root", "position_epoch_id": "epoch",
             "vt_symbol": "SH611.CZCE", "source": "stage901_pending_order", "direction": "long", "offset": "open"}
    fingerprint = hashlib.sha256(b"broker\0account").hexdigest()
    owner.update(intent_id="intent-id", intent_payload_sha256="a" * 64,
                 spool_lease_owner="lease-owner", spool_lease_token="lease-token", intent_kind="open",
                 position_cycle_id="cycle", intent_role="initial_open")
    request = {"child_order_index": 0, "child_order_count": 1, "symbol": "SH611", "exchange": "CZCE",
               "direction": "long", "offset": "open", "type": "FAK", "volume": 4, "price": 1948,
               "reference": "Stage905PhaseD:intent"}
    owner["intent_fingerprint"] = intent_fingerprint(owner["target_date"], owner, request)[0]
    proof = make_query_bundle({"order_before": [], "positions": [], "order_after": []}, start=100, first_reqid=1, connection="original")
    baseline = {"event_type": "broker_open_flat_baseline", "version": "ctp_owned_open_flat_baseline_v1",
                "physical_batch_id": "batch", "account_fingerprint": fingerprint, **owner,
                "physical_requests": [request], "service_generation": "service", "connection_generation": "original",
                "trading_day": "2026-09-08", "proof": proof, "proof_sha256": digest(proof)}
    native = {"event_type": "native_order_identity_persisted_before_insert", **owner,
              "broker_callback_key": "native", "physical_batch_id": "batch", "flat_baseline_event": baseline,
              "flat_baseline_sha256": digest(baseline), "front_id": "1", "session_id": "2", "order_ref": "3",
              "vt_orderid": "CTP.1_2_3", "req_order_insert_reqid": 4, "child_order_index": 0, "child_order_count": 1,
              "service_generation": "service", "connection_generation": "original", "price": 1948, "volume": 4,
              "account_fingerprint": fingerprint, "native_insert_monotonic_ns": 190,
              "query_watermark": {"reqid": 3},
              "event_watermark": copy.deepcopy(proof["event_watermark_after"]),
              "native_api_watermark": copy.deepcopy(proof["native_api_watermark_after"])}
    fill = {"event_type": "filled_or_part_filled", **owner, "broker_callback_key": "fill",
            "vt_orderid": "CTP.1_2_3", "tradeid": "T1", "vt_tradeid": "CTP.T1", "trade_fill_key": "ctp:CZCE:T1",
            "volume": 2, "trade_volume_delta": 2, "price": 1948, "fill_price_source": "event_trade_weighted_avg",
            "broker_trade_at": "2026-09-07T21:30:00+08:00"}
    with tempfile.TemporaryDirectory() as directory:
        ledger_path = Path(directory) / "ledger.ndjson"
        reserve_args = {"target_date": owner["target_date"], "row": owner, "order_request": request,
                        "close_retry_after_cancel_seconds": 30, "path": ledger_path}
        if prior_safe_retry or prior_recovery:
            prior = reserve_execution_ledger_intent(**reserve_args, base_event={**owner, "spool_lease_token": "old-lease"})
            assert prior["reserved"]
            if prior_recovery:
                recovered = recover_expired_spool_lease(**reserve_args, spool_lease_owner="lease-owner", spool_lease_token="old-lease")
                assert recovered.disposition == "requeue_pre_send"
            else:
                terminal = append_pre_api_slot_no_side_effect_terminal(
                    **{name: prior["latest_ledger_event"][name] for name in
                       ("target_date", "intent_id", "intent_payload_sha256", "intent_kind", "intent_fingerprint", "spool_lease_owner", "spool_lease_token")},
                    reservation_record_checksum=prior["latest_ledger_event"]["record_checksum"],
                    blockers=["authorization_expired"], blocked_phase="pre_api_slot", path=ledger_path)
                assert terminal["appended"]
        reserved = reserve_execution_ledger_intent(**reserve_args, base_event=owner)
        assert reserved["reserved"] and reserved["intent_fingerprint"] == owner["intent_fingerprint"]
        history = read_execution_ledger(ledger_path)
        native["reservation_record_checksum"] = reserved["latest_ledger_event"]["record_checksum"]
        ledger = [append_broker_callback_event_once(event, ledger_path)["ledger_event"] for event in (native, fill)]
        ledger.extend(history)
    order = {**identity, "FrontID": 1, "SessionID": 2, "OrderRef": "3", "OrderSysID": "SYS1",
             "Direction": "0", "CombOffsetFlag": "0", "CombHedgeFlag": "1", "OrderStatus": "5",
             "VolumeTotalOriginal": 4, "VolumeTraded": 2, "VolumeTotal": 2, "LimitPrice": 1948,
             "TradingDay": "20260908"}
    trade = {**identity, "OrderSysID": "SYS1", "TradeID": "T1", "TradeDate": "20260907", "TradeTime": "21:30:00",
             "TradingDay": "20260908", "Direction": "0", "OffsetFlag": "0", "HedgeFlag": "1", "Price": 1948, "Volume": 2,
             "OrderRef": "3"}
    detail = {**identity, "TradeID": "T1", "OpenDate": "20260908", "TradingDay": "20260908",
              "Direction": "0", "HedgeFlag": "1", "OpenPrice": 1948, "Volume": 2, "TradeType": "0",
              "InvestUnitID": "", "CombInstrumentID": "", "SpecPosiType": "#"}
    position = {**identity, "PosiDirection": "2", "HedgeFlag": "1", "PositionDate": "1",
                "Position": 2, "TodayPosition": 2, "TradingDay": "20260908"}
    bundle = make_query_bundle({"order_before": [order], "trades": [trade], "position_details": [detail],
                                "positions": [position], "order_after": [copy.deepcopy(order)]})
    return {"execution_ledger_rows": ledger, "native_order_event": ledger[0], "flat_baseline_event": baseline,
            "query_bundle": bundle, "account_fingerprint": fingerprint}


def module():
    return importlib.import_module("qmt_roll_official_live_broker_open_date_seal")


def test_night_partial_terminal_real_ledger_round_trip():
    inputs = make_seal_inputs()
    original = copy.deepcopy(inputs)
    seals = module().build_open_date_seals(**inputs)
    proof = module().validate_open_date_seal(json.loads(json.dumps(seals[0])), inputs["execution_ledger_rows"][1], inputs["account_fingerprint"])
    assert proof["broker_open_date"] == "2026-09-08"
    assert proof["broker_trade_date"] == "2026-09-07"
    assert proof["broker_trading_day"] == "2026-09-08"
    assert proof["broker_trade_metadata_source"] == "ctp_query_open_date_seal_v1"
    assert inputs == original
    assert seals == module().build_open_date_seals(**inputs)


@pytest.mark.parametrize("mutation", ["native", "checksum", "baseline", "last", "reqid", "account", "day", "watermark", "deadline", "manual", "detail_qty", "active", "multi"])
def test_unprovable_evidence_rejected(mutation):
    inputs = make_seal_inputs()
    queries = inputs["query_bundle"]["queries"]
    if mutation == "native":
        inputs["execution_ledger_rows"].pop(0)
    elif mutation == "checksum":
        inputs["native_order_event"]["root_position_id"] = "other"
    elif mutation == "baseline":
        inputs["flat_baseline_event"]["proof"]["queries"]["positions"]["callbacks"][0]["data"] = {"Position": 1}
    elif mutation == "last":
        queries["position_details"]["callbacks"].pop()
    elif mutation == "reqid":
        queries["trades"]["callbacks"][0]["reqid"] += 1
    elif mutation == "account":
        queries["position_details"]["callbacks"][0]["data"]["InvestorID"] = "manual"
    elif mutation == "day":
        queries["trades"]["callbacks"][0]["data"]["TradingDay"] = "20260907"
    elif mutation == "watermark":
        inputs["query_bundle"]["event_watermark_after"]["event_trade_count"] = 1
    elif mutation == "deadline":
        inputs["query_bundle"]["completed_monotonic_ns"] = 9999
    elif mutation == "manual":
        queries["position_details"]["callbacks"][0]["data"]["TradeID"] = "MANUAL"
    elif mutation == "detail_qty":
        queries["position_details"]["callbacks"][0]["data"]["Volume"] = 1
    elif mutation == "active":
        for name in ("order_before", "order_after"):
            queries[name]["callbacks"][0]["data"]["OrderStatus"] = "1"
    elif mutation == "multi":
        inputs["flat_baseline_event"]["physical_requests"] *= 2
    if mutation in {"baseline", "multi"}:
        resign_inputs(inputs)
    with pytest.raises(ValueError, match="broker_open_date_seal"):
        module().build_open_date_seals(**inputs)


def test_mutated_seal_and_canonical_fill_rejected():
    inputs = make_seal_inputs()
    seal = module().build_open_date_seals(**inputs)[0]
    seal["broker_open_date"] = "2026-09-07"
    with pytest.raises(ValueError):
        module().validate_open_date_seal(seal, inputs["execution_ledger_rows"][1], inputs["account_fingerprint"])


def test_existing_seal_reused_despite_new_query_reqids():
    inputs = make_seal_inputs()
    seal = module().build_open_date_seals(**inputs)[0]
    with tempfile.TemporaryDirectory() as directory:
        saved = append_broker_callback_event_once(seal, Path(directory) / "ledger")["ledger_event"]
    inputs["execution_ledger_rows"].append(saved)
    shift_bundle(inputs["query_bundle"], time_delta=1000, reqid_delta=100)
    assert module().build_open_date_seals(**inputs) == [saved]


def resign_inputs(inputs):
    baseline = inputs["flat_baseline_event"]
    baseline["proof_sha256"] = digest(baseline["proof"])
    native = inputs["native_order_event"]
    native["flat_baseline_event"] = copy.deepcopy(baseline)
    native["flat_baseline_sha256"] = digest(baseline)
    for row in inputs["execution_ledger_rows"]:
        row["record_checksum"] = digest({key: value for key, value in row.items() if key != "record_checksum"})
    reservations = [row for row in inputs["execution_ledger_rows"] if row.get("event_type") == "reserved"
                    and row.get("spool_lease_token") == native["spool_lease_token"]]
    if len(reservations) == 1:
        native["reservation_record_checksum"] = reservations[0]["record_checksum"]
        native["record_checksum"] = digest({key: value for key, value in native.items() if key != "record_checksum"})


def shift_bundle(bundle, *, time_delta=0, reqid_delta=0):
    for field in ("started_monotonic_ns", "completed_monotonic_ns", "deadline_monotonic_ns"):
        bundle[field] += time_delta
    for field in ("query_watermark_before", "query_watermark_after"):
        bundle[field]["reqid"] += reqid_delta
    for query in bundle["queries"].values():
        query["reqid"] += reqid_delta
        query["started_monotonic_ns"] += time_delta
        for callback in query["callbacks"]:
            callback["reqid"] += reqid_delta
            callback["received_monotonic_ns"] += time_delta


def raw(inputs, name):
    return inputs["query_bundle"]["queries"][name]["callbacks"][0]["data"]


@pytest.mark.parametrize("mutation", [
    "filtered_flat", "filtered_orders", "unknown_request_field", "missing_events", "missing_native",
    "incomplete_native", "native_changed", "native_total", "late_query_start", "overlapping_queries",
    "missing_query_start", "reverse_same_connection", "long_window", "native_before_flat", "native_event_gap",
    "native_api_gap", "future_trade", "ancient_open_date", "stale_position_day", "position_date",
    "duplicate_position", "canonical_account", "native_account", "lease", "missing_lease", "order_ref",
    "linked_conflict", "missing_linked", "linked_lease", "terminal_zero_conflict", "terminal_full_conflict",
    "remaining_volume", "missing_remaining", "native_already_in_flat", "missing_position_day",
    "missing_window", "oversized_window", "window_exceeded", "native_reqid_gap", "native_query_reversed",
])
def test_resigned_semantic_conflicts_fail_builder_and_replay(mutation):
    inputs = make_seal_inputs()
    original = module().build_open_date_seals(**inputs)[0]
    bundle = inputs["query_bundle"]
    queries = bundle["queries"]
    native = inputs["native_order_event"]
    if mutation == "filtered_flat":
        inputs["flat_baseline_event"]["proof"]["queries"]["positions"]["request"]["InstrumentID"] = "OTHER"
    elif mutation == "filtered_orders":
        queries["order_before"]["request"]["OrderSysID"] = "SYS1"
    elif mutation == "unknown_request_field":
        queries["positions"]["request"]["UnrecognizedFilter"] = ""
    elif mutation == "missing_events":
        bundle["event_watermark_before"] = bundle["event_watermark_after"] = {"ignored": 0}
    elif mutation == "missing_native":
        bundle.pop("native_api_watermark_before")
    elif mutation == "incomplete_native":
        for field in ("native_api_watermark_before", "native_api_watermark_after"):
            bundle[field]["order_api_evidence_complete"] = 0
    elif mutation == "native_changed":
        bundle["native_api_watermark_after"].update(send_order_api_called_count=1, order_api_called_count=1)
    elif mutation == "native_total":
        for field in ("native_api_watermark_before", "native_api_watermark_after"):
            bundle[field]["order_api_called_count"] = 1
    elif mutation == "late_query_start":
        queries["trades"]["started_monotonic_ns"] = queries["trades"]["callbacks"][0]["received_monotonic_ns"] + 1
    elif mutation == "overlapping_queries":
        queries["trades"]["started_monotonic_ns"] = bundle["started_monotonic_ns"]
    elif mutation == "missing_query_start":
        queries["trades"].pop("started_monotonic_ns")
    elif mutation == "reverse_same_connection":
        bundle["connection_generation"] = "original"
        shift_bundle(bundle, time_delta=-999)
    elif mutation == "long_window":
        bundle["completed_monotonic_ns"] += 86400 * 10**9
        bundle["deadline_monotonic_ns"] = bundle["completed_monotonic_ns"]
    elif mutation == "missing_window":
        bundle.pop("max_window_ns")
    elif mutation == "oversized_window":
        bundle["max_window_ns"] = 8_000_000_001
    elif mutation == "window_exceeded":
        bundle["max_window_ns"] = 1
    elif mutation == "native_before_flat":
        native["native_insert_monotonic_ns"] = 1
    elif mutation == "native_event_gap":
        native["event_watermark"]["event_trade_count"] += 1
    elif mutation == "native_api_gap":
        native["native_api_watermark"].update(send_order_api_called_count=1, order_api_called_count=1)
    elif mutation == "native_reqid_gap":
        native["req_order_insert_reqid"] = 7
    elif mutation == "native_query_reversed":
        native["query_watermark"]["reqid"] = 1
        native["req_order_insert_reqid"] = 2
    elif mutation == "future_trade":
        raw(inputs, "trades")["TradeDate"] = "20270907"
        inputs["execution_ledger_rows"][1]["broker_trade_at"] = "2027-09-07T21:30:00+08:00"
    elif mutation == "ancient_open_date":
        raw(inputs, "position_details")["OpenDate"] = "20000101"
    elif mutation == "stale_position_day":
        raw(inputs, "positions")["TradingDay"] = "20260907"
    elif mutation == "position_date":
        raw(inputs, "positions")["PositionDate"] = "invalid"
    elif mutation == "duplicate_position":
        raw(inputs, "positions").update(Position=1, TodayPosition=1)
        queries["positions"]["callbacks"].insert(0, copy.deepcopy(queries["positions"]["callbacks"][0]))
    elif mutation == "canonical_account":
        inputs["execution_ledger_rows"][1]["account_fingerprint"] = "f" * 64
    elif mutation == "native_account":
        native["account_fingerprint"] = "f" * 64
    elif mutation == "lease":
        inputs["execution_ledger_rows"][1]["spool_lease_token"] = "other"
    elif mutation == "missing_lease":
        inputs["execution_ledger_rows"][1].pop("spool_lease_token")
    elif mutation == "order_ref":
        raw(inputs, "trades")["OrderRef"] = "other"
    elif mutation == "linked_conflict":
        inputs["execution_ledger_rows"][2]["intent_payload"]["root_position_id"] = "other"
    elif mutation == "missing_linked":
        inputs["execution_ledger_rows"].pop(2)
    elif mutation == "linked_lease":
        inputs["execution_ledger_rows"][2]["spool_lease_token"] = "other"
    elif mutation in {"terminal_zero_conflict", "terminal_full_conflict"}:
        for name in ("order_before", "order_after"):
            raw(inputs, name)["OrderStatus"] = "4" if mutation == "terminal_zero_conflict" else "0"
    elif mutation == "remaining_volume":
        for name in ("order_before", "order_after"):
            raw(inputs, name)["VolumeTotal"] = 0
    elif mutation == "missing_remaining":
        for name in ("order_before", "order_after"):
            raw(inputs, name).pop("VolumeTotal")
    elif mutation == "native_already_in_flat":
        for name in ("order_before", "order_after"):
            target = inputs["flat_baseline_event"]["proof"]["queries"][name]
            target["callbacks"].insert(0, {**copy.deepcopy(target["callbacks"][0]), "last": False,
                                          "data": copy.deepcopy(raw(inputs, name))})
    elif mutation == "missing_position_day":
        raw(inputs, "positions").pop("TradingDay")
    resign_inputs(inputs)
    if mutation == "linked_lease":
        native["reservation_record_checksum"] = inputs["execution_ledger_rows"][2]["record_checksum"]
        native["record_checksum"] = digest({key: value for key, value in native.items() if key != "record_checksum"})
    evidence = original["evidence"]
    evidence.update(native_order_events=[copy.deepcopy(native)], flat_baseline_event=copy.deepcopy(inputs["flat_baseline_event"]),
                    canonical_fills=[copy.deepcopy(inputs["execution_ledger_rows"][1])],
                    linked_intent_events=copy.deepcopy(inputs["execution_ledger_rows"][2:]), query_bundle=copy.deepcopy(bundle))
    if "reservation_history" in evidence:
        evidence["reservation_history"] = copy.deepcopy(inputs["execution_ledger_rows"])
    original["proof_sha256"] = digest({key: value for key, value in original.items() if key != "proof_sha256"})
    with pytest.raises(ValueError, match="broker_open_date_seal") as caught:
        module().build_open_date_seals(**inputs)
    assert "digest" not in str(caught.value) and "checksum" not in str(caught.value)
    assert "seal_replay_mismatch" not in str(caught.value)
    with pytest.raises(ValueError, match="broker_open_date_seal") as caught:
        module().validate_open_date_seal(original, inputs["execution_ledger_rows"][1], inputs["account_fingerprint"])
    assert "digest" not in str(caught.value) and "checksum" not in str(caught.value)


def test_restart_does_not_compare_old_monotonic_clock():
    inputs = make_seal_inputs()
    shift_bundle(inputs["query_bundle"], time_delta=-999)
    seals = module().build_open_date_seals(**inputs)
    assert module().validate_open_date_seal(seals[0], inputs["execution_ledger_rows"][1], inputs["account_fingerprint"])


def test_readonly_account_and_margin_queries_between_flat_and_native():
    inputs = make_seal_inputs()
    native = inputs["native_order_event"]
    native["query_watermark"]["reqid"] = 6
    native["req_order_insert_reqid"] = 7
    bundle = inputs["query_bundle"]
    bundle["connection_generation"] = "original"
    for field in ("native_api_watermark_before", "native_api_watermark_after"):
        bundle[field].update(send_order_api_called_count=1, order_api_called_count=1)
    resign_inputs(inputs)
    assert module().build_open_date_seals(**inputs)


def test_conflicting_open_date_cannot_hide_behind_new_query_identity():
    inputs = make_seal_inputs()
    seal = module().build_open_date_seals(**inputs)[0]
    with tempfile.TemporaryDirectory() as directory:
        inputs["execution_ledger_rows"].append(append_broker_callback_event_once(seal, Path(directory) / "ledger")["ledger_event"])
    shift_bundle(inputs["query_bundle"], time_delta=1000, reqid_delta=100)
    raw(inputs, "position_details")["OpenDate"] = "20260907"
    with pytest.raises(ValueError, match="existing_seal_conflict"):
        module().build_open_date_seals(**inputs)


@pytest.mark.parametrize("open_date", ["20260907", "20260908"])
def test_independent_open_date_within_raw_date_bounds(open_date):
    inputs = make_seal_inputs()
    raw(inputs, "position_details")["OpenDate"] = open_date
    assert module().build_open_date_seals(**inputs)[0]["broker_open_date"] in {"2026-09-07", "2026-09-08"}


@pytest.mark.parametrize("symbol", ["SH611.CZCE", "sh611.czce", "", None, " ", 7])
@pytest.mark.parametrize("reuse", [False, True])
def test_durable_seal_conflict_blocks_build_and_reuse(symbol, reuse):
    inputs = make_seal_inputs()
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "ledger"
        if reuse:
            seal = module().build_open_date_seals(**inputs)[0]
            inputs["execution_ledger_rows"].append(append_broker_callback_event_once(seal, path)["ledger_event"])
        conflict = {"event_type": "broker_position_open_date_seal_conflict", "vt_symbol": symbol, "broker_callback_key": "conflict",
                    "target_date": "2026-09-08"}
        inputs["execution_ledger_rows"].append(append_broker_callback_event_once(conflict, path)["ledger_event"])
    with pytest.raises(ValueError, match="conflict"):
        module().build_open_date_seals(**inputs)


def test_existing_seal_requires_its_original_native_in_actual_ledger():
    inputs = make_seal_inputs()
    seal = module().build_open_date_seals(**inputs)[0]
    with tempfile.TemporaryDirectory() as directory:
        saved = append_broker_callback_event_once(seal, Path(directory) / "ledger")["ledger_event"]
    inputs["native_order_event"]["query_watermark"]["reqid"] = 6
    inputs["native_order_event"]["req_order_insert_reqid"] = 7
    resign_inputs(inputs)
    inputs["execution_ledger_rows"].append(saved)
    with pytest.raises(ValueError, match="seal_evidence_not_in_ledger"):
        module().build_open_date_seals(**inputs)


@pytest.mark.parametrize("exchange", ["CZCE", "SHFE", "INE"])
def test_single_child_multiple_distinct_fills_cover_gross(exchange):
    inputs = make_seal_inputs()
    native = inputs["native_order_event"]
    symbol = "SH611" if exchange == "CZCE" else "cu2609" if exchange == "SHFE" else "sc2609"
    vt_symbol = f"{symbol}.{exchange}"
    for row in inputs["execution_ledger_rows"]:
        row["vt_symbol"] = vt_symbol
        if row.get("intent_payload"):
            row["intent_payload"]["vt_symbol"] = vt_symbol
            row["intent_payload"].update(symbol=symbol, exchange=exchange)
    baseline = inputs["flat_baseline_event"]
    baseline["vt_symbol"] = vt_symbol
    baseline["physical_requests"][0].update(symbol=symbol, exchange=exchange)
    fill = inputs["execution_ledger_rows"][1]
    fill["trade_fill_key"] = f"ctp:{exchange}:T1"
    second = copy.deepcopy(fill)
    second.update(tradeid="T2", vt_tradeid="CTP.T2", trade_fill_key=f"ctp:{exchange}:T2", broker_callback_key="fill2",
                  volume=1, trade_volume_delta=1)
    inputs["execution_ledger_rows"].append(second)
    queries = inputs["query_bundle"]["queries"]
    for query in queries.values():
        for callback in query["callbacks"]:
            if callback["data"]:
                callback["data"].update(ExchangeID=exchange, InstrumentID=symbol)
    for name in ("trades", "position_details"):
        callback = copy.deepcopy(queries[name]["callbacks"][0])
        callback["data"].update(TradeID="T2", Volume=1)
        queries[name]["callbacks"].insert(1, callback)
    for name in ("order_before", "order_after"):
        raw(inputs, name).update(VolumeTraded=3, VolumeTotal=1)
    raw(inputs, "positions").update(Position=3, TodayPosition=3)
    payload = next(row["intent_payload"] for row in inputs["execution_ledger_rows"] if row.get("event_type") == "reserved")
    new_fingerprint = intent_fingerprint(payload["target_date"], payload, payload)[0]
    for row in inputs["execution_ledger_rows"]:
        row["intent_fingerprint"] = new_fingerprint
    baseline["intent_fingerprint"] = new_fingerprint
    resign_inputs(inputs)
    seals = module().build_open_date_seals(**inputs)
    assert len(seals) == 2
    assert sum(seal["volume"] for seal in seals) == 3
    for seal in seals:
        canonical = next(row for row in inputs["execution_ledger_rows"] if row.get("tradeid") == seal["tradeid"])
        assert module().validate_open_date_seal(seal, canonical, inputs["account_fingerprint"])


def test_account_level_queries_allow_only_declared_empty_optional_fields():
    inputs = make_seal_inputs()
    for bundle in (inputs["flat_baseline_event"]["proof"], inputs["query_bundle"]):
        for query in bundle["queries"].values():
            query["request"].update(InstrumentID="", ExchangeID="", InvestUnitID="")
    resign_inputs(inputs)
    assert module().build_open_date_seals(**inputs)


@pytest.mark.parametrize("mutation", ["volume", "missing_intent_id", "missing_payload_sha", "missing_kind", "native_reservation_ref"])
def test_real_reservation_identity_and_fingerprint_are_verified(mutation):
    inputs = make_seal_inputs()
    seal = module().build_open_date_seals(**inputs)[0]
    linked = inputs["execution_ledger_rows"][2]
    if mutation == "volume":
        linked["intent_payload"]["volume"] = 1
    elif mutation == "native_reservation_ref":
        pass
    else:
        linked.pop({"missing_intent_id": "intent_id", "missing_payload_sha": "intent_payload_sha256", "missing_kind": "intent_kind"}[mutation])
    resign_inputs(inputs)
    if mutation == "native_reservation_ref":
        inputs["native_order_event"]["reservation_record_checksum"] = "f" * 64
        inputs["native_order_event"]["record_checksum"] = digest({key: value for key, value in inputs["native_order_event"].items() if key != "record_checksum"})
    with pytest.raises(ValueError, match="broker_open_date_seal"):
        module().build_open_date_seals(**inputs)
    history = module().collect_open_date_reservation_history(inputs["execution_ledger_rows"], inputs["native_order_event"])
    seal["evidence"].update(native_order_events=[copy.deepcopy(inputs["native_order_event"])],
                            linked_intent_events=[copy.deepcopy(row) for row in history if isinstance(row.get("intent_payload"), dict)],
                            reservation_history=history)
    seal["proof_sha256"] = digest({key: value for key, value in seal.items() if key != "proof_sha256"})
    with pytest.raises(ValueError, match="broker_open_date_seal"):
        module().validate_open_date_seal(seal, inputs["execution_ledger_rows"][1], inputs["account_fingerprint"])


@pytest.mark.parametrize("recovery", [False, True])
def test_real_safe_terminal_then_new_lease_can_seal_and_restart(recovery):
    inputs = make_seal_inputs(prior_safe_retry=not recovery, prior_recovery=recovery)
    reservations = [row for row in inputs["execution_ledger_rows"] if row.get("event_type") == "reserved"]
    assert len(reservations) == 2 and reservations[0]["intent_fingerprint"] == reservations[1]["intent_fingerprint"]
    seals = module().build_open_date_seals(**inputs)
    seal = json.loads(json.dumps(seals[0]))
    assert seal["evidence"]["reservation_history"]
    assert reservations[0] in seal["evidence"]["reservation_history"]
    assert module().validate_open_date_seal(seal, inputs["execution_ledger_rows"][1], inputs["account_fingerprint"])


@pytest.mark.parametrize("mutation", ["missing_terminal", "wrong_terminal_lease", "slot_after_terminal", "native_after_terminal",
                                      "conflicting_terminal", "old_fill_wrong_fingerprint"])
def test_historical_lease_without_exact_zero_side_effect_proof_blocks(mutation):
    inputs = make_seal_inputs(prior_safe_retry=True)
    rows = inputs["execution_ledger_rows"]
    terminal = next(row for row in rows if row.get("event_type") == "pre_api_slot_no_side_effect_safe_terminal")
    if mutation == "missing_terminal":
        rows.remove(terminal)
    elif mutation == "wrong_terminal_lease":
        terminal["spool_lease_token"] = "wrong"
        terminal["record_checksum"] = digest({key: value for key, value in terminal.items() if key != "record_checksum"})
    elif mutation == "conflicting_terminal":
        bad = copy.deepcopy(terminal)
        bad["send_order_call_count"] = 1
        bad["record_checksum"] = digest({key: value for key, value in bad.items() if key != "record_checksum"})
        rows.insert(rows.index(terminal) + 1, bad)
    elif mutation == "old_fill_wrong_fingerprint":
        bad = copy.deepcopy(inputs["execution_ledger_rows"][1])
        bad.update(spool_lease_token="old-lease", intent_fingerprint="f" * 64, vt_orderid="CTP.old", tradeid="OLD")
        bad["record_checksum"] = digest({key: value for key, value in bad.items() if key != "record_checksum"})
        rows.append(bad)
    else:
        prior = next(row for row in rows if row.get("event_type") == "reserved" and row.get("spool_lease_token") == "old-lease")
        effect = {**prior, "event_type": "api_slot_reserved" if mutation == "slot_after_terminal" else "native_order_identity_persisted_before_insert"}
        effect["record_checksum"] = digest({key: value for key, value in effect.items() if key != "record_checksum"})
        rows.append(effect)
    with pytest.raises(ValueError, match="broker_open_date_seal"):
        module().build_open_date_seals(**inputs)


def test_reprice_does_not_change_reserved_fingerprint():
    inputs = make_seal_inputs()
    inputs["flat_baseline_event"]["physical_requests"][0]["price"] = 1950
    inputs["native_order_event"]["price"] = 1950
    for name in ("order_before", "order_after"):
        raw(inputs, name)["LimitPrice"] = 1950
    resign_inputs(inputs)
    assert inputs["execution_ledger_rows"][2]["intent_payload"]["limit_price"] == 1948
    assert module().build_open_date_seals(**inputs)


def test_history_collection_ignores_later_normal_audits():
    inputs = make_seal_inputs(prior_safe_retry=True)
    collect = module().collect_open_date_reservation_history
    original = collect(inputs["execution_ledger_rows"], inputs["native_order_event"])
    for kind in ("reconciled", "broker_trade_ownership_metadata"):
        row = {**inputs["native_order_event"], "event_type": kind, "broker_callback_key": kind}
        row["record_checksum"] = digest({key: value for key, value in row.items() if key != "record_checksum"})
        inputs["execution_ledger_rows"].append(row)
    assert collect(inputs["execution_ledger_rows"], inputs["native_order_event"]) == original
    assert module().build_open_date_seals(**inputs)


def test_identical_duplicate_durable_rows_do_not_create_new_history_or_fills():
    inputs = make_seal_inputs(prior_safe_retry=True)
    original = module().build_open_date_seals(**inputs)
    inputs["execution_ledger_rows"] += copy.deepcopy(inputs["execution_ledger_rows"])
    assert module().build_open_date_seals(**inputs) == original


def test_current_reservation_cannot_be_both_safe_terminal_and_sent():
    inputs = make_seal_inputs(prior_safe_retry=True)
    terminal = copy.deepcopy(next(row for row in inputs["execution_ledger_rows"] if row.get("event_type") == "pre_api_slot_no_side_effect_safe_terminal"))
    terminal["spool_lease_token"] = inputs["native_order_event"]["spool_lease_token"]
    terminal["reservation_record_checksum"] = inputs["native_order_event"]["reservation_record_checksum"]
    terminal["record_checksum"] = digest({key: value for key, value in terminal.items() if key != "record_checksum"})
    inputs["execution_ledger_rows"].append(terminal)
    with pytest.raises(ValueError, match="current_reservation_safe_terminal"):
        module().build_open_date_seals(**inputs)
