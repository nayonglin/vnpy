from __future__ import annotations

import copy
import hashlib
import importlib
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples/portfolio_backtesting"))
from qmt_roll_official_live_execution_ledger import intent_fingerprint


def inputs():
    account = hashlib.sha256(b"9999\x00000123").hexdigest()
    request = {"symbol": "SH611", "exchange": "CZCE", "direction": "long", "offset": "open", "volume": 2, "price": 1948}
    payload = {"intent_id": "first", "target_date": "2026-09-07", "vt_symbol": "SH611.CZCE",
               "direction": "long", "offset": "open", "planned_volume": 2, "order_request": request,
               "root_position_id": "root", "position_cycle_id": "root:0", "intent_role": "c9_initial_open",
               "broker_sizing": {"account_fingerprint": account}}
    fingerprint, normalized = intent_fingerprint("2026-09-07", payload, request)
    context = {"intent_id": "first", "target_date": "2026-09-07", "intent_fingerprint": fingerprint,
               "spool_lease_owner": "executor", "spool_lease_token": "lease-1", "intent_payload": normalized}
    ledger = [{**context, "event_type": "reserved"},
              {**context, "event_type": "native_order_identity_persisted_before_insert", "vt_orderid": "CTP.1_2_3"},
              {**context, "event_type": "send_order_returned", "vt_orderid": "CTP.1_2_3"}]
    sent = {"intent_id": "first", "target_date": "2026-09-07", "intent_kind": "open", "state": "sent",
            "lease_owner": "executor", "lease_token": "lease-1", "updated_epoch_ns": 1788832800000000000,
            "payload": payload}
    snapshot = {"complete": True, "generation_uuid": "generation-new", "account_fingerprint": account,
                "generated_at": "2026-09-08T10:00:30+08:00", "query_started_at": "2026-09-08T10:00:10+08:00",
                "orders": [{"vt_orderid": "CTP.1_2_3", "vt_symbol": "SH611.CZCE", "direction": "long", "offset": "open",
                            "status": "全部成交", "volume": "2", "traded": "2", "broker_id": "9999", "account_id": "000123",
                            "query_generation_uuid": "generation-new"}], "positions": [], "trades": []}
    return {"sent_intent": sent, "broker_snapshot": snapshot, "execution_ledger_rows": ledger,
            "now": datetime.fromisoformat("2026-09-08T10:00:40+08:00")}


def evaluate(values):
    module = importlib.import_module("qmt_roll_official_live_broker_open_queue")
    return module.evaluate_sent_open_budget_release(**values)


def test_helper_exists():
    assert importlib.util.find_spec("qmt_roll_official_live_broker_open_queue") is not None


@pytest.mark.parametrize("audit", [None, {}, "", {"account_fingerprint": "wrong"}])
def test_existing_invalid_sizing_cannot_fall_back_to_legacy_account(audit):
    module = importlib.import_module("qmt_roll_official_live_broker_open_queue")
    values = inputs()
    values["sent_intent"]["payload"]["account_fingerprint"] = values["broker_snapshot"]["account_fingerprint"]
    values["sent_intent"]["payload"]["broker_sizing"] = audit
    with pytest.raises(ValueError):
        module.build_sent_open_reconciliation_proof(**values)


@pytest.mark.parametrize("status,traded", [("全部成交", "2"), ("已撤销", "0"), ("拒单", "0"), ("cancelled", "1"), ("ALL_TRADED", "2")])
def test_terminal_order_releases_only_budget_without_mutating_inputs(status, traded):
    values = inputs()
    values["broker_snapshot"]["orders"][0].update(status=status, traded=traded)
    before = copy.deepcopy(values)
    result = evaluate(values)
    assert result["budget_released"] is True
    assert result["blocker"] == ""
    assert result["vt_orderids"] == ["CTP.1_2_3"]
    assert values == before
    assert values["sent_intent"]["state"] == "sent"


@pytest.mark.parametrize("started", ["2026-09-08T10:00:00+08:00", "2026-09-08T09:59:59+08:00", "", "2026-09-08T10:00:10"])
def test_all_queries_must_start_strictly_after_sent_update(started):
    values = inputs()
    values["broker_snapshot"]["query_started_at"] = started
    result = evaluate(values)
    assert not result["budget_released"]
    assert result["blocker"]


@pytest.mark.parametrize("state", ["ready", "sending", "side_effect_unknown", "reconciled", "blocked"])
def test_never_releases_other_states(state):
    values = inputs()
    values["sent_intent"]["state"] = state
    assert not evaluate(values)["budget_released"]


@pytest.mark.parametrize("change", [
    {"status": "part_traded"}, {"status": "unknown"}, {"account_id": "123"},
    {"query_generation_uuid": "old"}, {"vt_symbol": "SA611.CZCE"}, {"offset": "close"},
    {"direction": "short"}, {"volume": "nan"}, {"traded": "NaN"}, {"traded": "3"},
    {"status": "全部成交", "traded": "1"},
])
def test_bad_or_unbound_broker_order_blocks(change):
    values = inputs()
    values["broker_snapshot"]["orders"][0].update(change)
    assert not evaluate(values)["budget_released"]


@pytest.mark.parametrize("field,value", [("intent_fingerprint", "wrong"), ("spool_lease_token", "wrong"), ("target_date", "2026-09-06")])
def test_durable_send_binding_cannot_be_borrowed(field, value):
    values = inputs()
    for event in values["execution_ledger_rows"][1:]:
        event[field] = value
    assert not evaluate(values)["budget_released"]


def test_missing_reservation_or_send_or_order_blocks():
    for key in ("reservation", "send", "order"):
        values = inputs()
        if key == "reservation":
            values["execution_ledger_rows"].pop(0)
        elif key == "send":
            values["execution_ledger_rows"] = values["execution_ledger_rows"][:1]
        else:
            values["broker_snapshot"]["orders"] = []
        assert not evaluate(values)["budget_released"]


def test_every_physical_order_must_be_present_and_terminal():
    values = inputs()
    values["execution_ledger_rows"].append({**values["execution_ledger_rows"][-1], "vt_orderid": "CTP.1_2_4"})
    assert not evaluate(values)["budget_released"]
    values["broker_snapshot"]["orders"].append({**values["broker_snapshot"]["orders"][0], "vt_orderid": "CTP.1_2_4", "status": "未成交"})
    assert not evaluate(values)["budget_released"]
    values["broker_snapshot"]["orders"][-1].update(status="已撤销", traded="0")
    assert evaluate(values)["budget_released"]


def test_duplicate_order_rows_are_not_terminal_proof():
    values = inputs()
    values["broker_snapshot"]["orders"] *= 2
    assert not evaluate(values)["budget_released"]


@pytest.mark.parametrize("change", [{"complete": False}, {"account_fingerprint": "a" * 64}, {"generated_at": "2026-09-08T09:00:00+08:00"}, {"query_started_at": "2026-09-08T10:01:00+08:00"}])
def test_snapshot_must_be_fresh_complete_and_same_account(change):
    values = inputs()
    values["broker_snapshot"].update(change)
    assert not evaluate(values)["budget_released"]


def test_ledger_integrity_error_blocks():
    values = inputs()
    values["execution_ledger_rows"].append({"event_type": "ledger_checksum_error"})
    assert not evaluate(values)["budget_released"]


def test_missing_original_sizing_account_cannot_use_new_account():
    values = inputs()
    values["sent_intent"]["payload"].pop("broker_sizing")
    assert not evaluate(values)["budget_released"]


def test_terminal_ledger_event_does_not_replace_fresh_broker_order():
    values = inputs()
    values["execution_ledger_rows"].append({**values["execution_ledger_rows"][-1],
        "event_type": "broker_order_query_terminal_observed", "fill_price_reconciliation_pending": 0})
    values["broker_snapshot"]["orders"] = []
    assert not evaluate(values)["budget_released"]


def test_nanosecond_watermark_is_not_rounded_down():
    values = inputs()
    values["sent_intent"]["updated_epoch_ns"] += 10_000_000_001
    assert evaluate(values)["blocker"] == "broker_sizing_sent_snapshot_precedes_sent"


def test_symbol_and_direction_enum_case_normalization():
    values = inputs()
    values["broker_snapshot"]["orders"][0].update(vt_symbol="sh611.czce", direction="Direction.LONG", offset="Offset.OPEN")
    assert evaluate(values)["budget_released"]


def test_pending_open_still_blocks_when_a_different_sent_open_is_released():
    values = inputs()
    assert evaluate(values)["budget_released"]
    values["sent_intent"]["state"] = "side_effect_unknown"
    assert not evaluate(values)["budget_released"]


def test_missing_retained_lease_blocks():
    values = inputs()
    values["sent_intent"]["lease_token"] = ""
    assert not evaluate(values)["budget_released"]
