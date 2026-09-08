from __future__ import annotations

import copy
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples/portfolio_backtesting"))
MODULE = "qmt_roll_official_live_broker_position_ownership"
FINGERPRINT = hashlib.sha256(b"broker\0account").hexdigest()


def fill(**changes):
    return {
        "event_type": "filled_or_part_filled", "source": "stage901_pending_order",
        "vt_symbol": "SH611.CZCE", "direction": "long", "offset": "open",
        "root_position_id": "root-1", "position_epoch_id": "epoch-1",
        "vt_orderid": "CTP.1_2_3", "tradeid": "T1", "vt_tradeid": "CTP.T1",
        "trade_fill_key": "ctp:CZCE:T1", "volume": 4, "trade_volume_delta": 4,
        "price": 1948, "fill_price_source": "event_trade_weighted_avg",
        "broker_trade_at": "2026-09-07T09:30:00+08:00", "target_date": "2026-09-07",
        "broker_trading_day": "20260907", "account_fingerprint": FINGERPRINT,
        **changes,
    }


def detail(**changes):
    return {
        "BrokerID": "broker", "InvestorID": "account", "InstrumentID": "SH611",
        "ExchangeID": "CZCE", "TradeID": "T1", "OpenDate": "20260907",
        "TradingDay": "20260908", "Direction": "0", "Volume": 4, "OpenPrice": 1948,
        "HedgeFlag": "1", "TradeType": "0", "CombInstrumentID": "", "SpecPosiType": "#",
        **changes,
    }


def arguments(**changes):
    return {
        "execution_ledger_rows": [fill()], "position_detail_rows": [detail()],
        "vt_symbol": "SH611.CZCE", "position_direction": "long", "broker_gross_volume": 4,
        "account_fingerprint": FINGERPRINT, "trading_day": "20260908", **changes,
    }


def validate(inputs):
    assert importlib.util.find_spec(MODULE) is not None, "position ownership validator must exist"
    module = importlib.import_module(MODULE)
    before = copy.deepcopy(inputs)
    try:
        return module.validate_position_detail_ownership(**inputs)
    finally:
        assert inputs == before


def seal_inputs(**kwargs):
    from test_official_live_broker_open_date_seal import make_seal_inputs

    inputs = make_seal_inputs(**kwargs)
    rows = inputs["execution_ledger_rows"]
    fills_and_native = {"native_order_identity_persisted_before_insert", "filled_or_part_filled"}
    inputs["execution_ledger_rows"] = [row for row in rows if row.get("event_type") not in fills_and_native] + [
        row for row in rows if row.get("event_type") in fills_and_native
    ]
    return inputs


def ledger_event(inputs, event_type):
    return next(row for row in inputs["execution_ledger_rows"] if row.get("event_type") == event_type)


def sealed_arguments(*, day="20260909", canonical_changes=None, payload_changes=None, **kwargs):
    from test_official_live_broker_open_date_seal import resign_inputs
    from qmt_roll_official_live_broker_open_date_seal import build_open_date_seals

    inputs = seal_inputs(**kwargs)
    canonical = ledger_event(inputs, "filled_or_part_filled")
    if canonical_changes:
        canonical.update(canonical_changes)
    if payload_changes:
        linked = ledger_event(inputs, "reserved")
        linked["intent_payload"].update(payload_changes)
    resign_inputs(inputs)
    seals = build_open_date_seals(**inputs)
    return arguments(execution_ledger_rows=inputs["execution_ledger_rows"] + seals,
                     broker_gross_volume=2, trading_day=day,
                     position_detail_rows=[detail(Volume=2, OpenDate="20260908", TradingDay=day)])


def test_historical_remaining_lots_match_durable_owned_open_fill():
    proof = validate(arguments())
    assert proof["confirmed"] is True
    assert proof["root_position_id"] == "root-1"
    assert proof["position_epoch_id"] == "epoch-1"
    assert proof["owned_net_volume"] == proof["detail_volume"] == 4
    assert proof["account_fingerprint"] == FINGERPRINT
    assert proof["open_trade_bindings"][0]["remaining_volume"] == 4
    assert json.loads(json.dumps(proof, allow_nan=False)) == proof
    assert proof == validate(arguments())


def test_same_day_legacy_record_does_not_require_invented_business_date():
    event = fill(broker_trade_at="2026-09-08T09:30:00+08:00", target_date="2026-09-08")
    del event["broker_trading_day"]
    proof = validate(arguments(execution_ledger_rows=[event], position_detail_rows=[detail(OpenDate="20260908")]))
    assert proof["confirmed"]


def test_old_record_without_broker_trading_day_cannot_be_promoted_to_overnight():
    event = fill()
    del event["broker_trading_day"]
    with pytest.raises(ValueError, match="trading_day"):
        validate(arguments(execution_ledger_rows=[event]))


def test_night_trade_requires_explicit_broker_open_date_when_calendar_date_differs():
    inputs = sealed_arguments()
    assert validate(inputs)["confirmed"]
    inputs["execution_ledger_rows"].pop()
    with pytest.raises(ValueError, match="account|trading_day|open.*(date|fill)|unmatched"):
        validate(inputs)


def test_remaining_volume_requires_owned_close_net_not_only_open_capacity():
    close = fill(tradeid="C1", vt_tradeid="CTP.C1", trade_fill_key="ctp:CZCE:C1",
                 direction="short", offset="close", volume=2, trade_volume_delta=2,
                 vt_orderid="CTP.1_2_4", price=1950)
    inputs = arguments(execution_ledger_rows=[fill(volume=6, trade_volume_delta=6), close])
    assert validate(inputs)["confirmed"]
    inputs["execution_ledger_rows"].pop()
    with pytest.raises(ValueError, match="net"):
        validate(inputs)


def test_close_owner_can_be_carried_only_inside_broker_close_sizing():
    close = fill(tradeid="C1", vt_tradeid="CTP.C1", trade_fill_key="ctp:CZCE:C1",
                 direction="short", offset="close", volume=2, trade_volume_delta=2, price=1950,
                 broker_close_sizing={"root_position_id": "root-1", "position_epoch_id": "epoch-1",
                                      "account_fingerprint": FINGERPRINT})
    for name in ("root_position_id", "position_epoch_id", "account_fingerprint"):
        del close[name]
    assert validate(arguments(execution_ledger_rows=[fill(volume=6, trade_volume_delta=6), close]))["confirmed"]


def test_linked_immutable_payload_supplies_account_and_owner():
    event = fill(intent_fingerprint="fingerprint")
    payload = {name: event.pop(name) for name in ("source", "root_position_id", "position_epoch_id", "account_fingerprint")}
    payload["broker_sizing"] = {"account_fingerprint": payload.pop("account_fingerprint")}
    inputs = arguments(execution_ledger_rows=[{"intent_fingerprint": "fingerprint", "intent_payload": payload}, event])
    assert validate(inputs)["confirmed"]


@pytest.mark.parametrize("changes", [
    {"TradeID": "MANUAL_REOPEN"}, {"BrokerID": "other"}, {"InvestorID": "other"},
    {"OpenPrice": 1949}, {"Volume": 5}, {"Volume": 3}, {"Volume": True}, {"Volume": "4"},
    {"Volume": -1}, {"Volume": 0.5}, {"OpenPrice": float("inf")}, {"OpenPrice": 1e308},
    {"TradingDay": "20260907"}, {"OpenDate": "20260909"}, {"OpenDate": "20260230"},
    {"Direction": "1"}, {"HedgeFlag": "3"}, {"TradeType": "1"},
    {"CombInstrumentID": "SP SH611&SH612"}, {"SpecPosiType": "0"}, {"InvestUnitID": "unit-unknown"},
])
def test_unmatched_or_unsafe_detail_cannot_claim_owned_lots(changes):
    with pytest.raises(ValueError):
        validate(arguments(position_detail_rows=[detail(**changes)]))


@pytest.mark.parametrize("field", ["account_fingerprint", "root_position_id", "position_epoch_id", "vt_orderid", "tradeid"])
def test_missing_durable_owner_identity_fails(field):
    event = fill()
    del event[field]
    with pytest.raises(ValueError):
        validate(arguments(execution_ledger_rows=[event]))


@pytest.mark.parametrize("changes", [
    {"source": "manual"}, {"account_fingerprint": "f" * 64}, {"fill_price_source": "order_traded_without_trade_price"},
    {"trade_fill_key": "aggregate:T1"}, {"vt_tradeid": "CTP.OTHER"},
    {"broker_trading_day": "20260909"}, {"price": 1947}, {"trade_volume_delta": True},
])
def test_unverified_ledger_fill_fails(changes):
    with pytest.raises(ValueError):
        validate(arguments(execution_ledger_rows=[fill(**changes)]))


def test_duplicate_detail_is_not_double_capacity_and_duplicate_fill_is_idempotent():
    with pytest.raises(ValueError, match="duplicate"):
        validate(arguments(position_detail_rows=[detail(Volume=2), detail(Volume=2)]))
    assert validate(arguments(execution_ledger_rows=[fill(), fill()]))["confirmed"]
    with pytest.raises(ValueError, match="conflict"):
        validate(arguments(execution_ledger_rows=[fill(), fill(price=1949)]))


def test_multiple_active_owned_epochs_are_not_one_position():
    second = fill(tradeid="T2", vt_tradeid="CTP.T2", trade_fill_key="ctp:CZCE:T2",
                  root_position_id="root-2", position_epoch_id="epoch-2", volume=2, trade_volume_delta=2)
    with pytest.raises(ValueError, match="epoch"):
        validate(arguments(execution_ledger_rows=[fill(volume=2, trade_volume_delta=2), second],
                           position_detail_rows=[detail(Volume=2), detail(TradeID="T2", Volume=2)]))


def test_old_flat_root_cannot_reclaim_same_quantity_reopened_position():
    close = fill(tradeid="C1", vt_tradeid="CTP.C1", trade_fill_key="ctp:CZCE:C1", offset="close", direction="short")
    new = fill(tradeid="T2", vt_tradeid="CTP.T2", trade_fill_key="ctp:CZCE:T2", root_position_id="root-2", position_epoch_id="epoch-2")
    with pytest.raises(ValueError, match="epoch|root"):
        validate(arguments(execution_ledger_rows=[fill(), close, new]))
    assert validate(arguments(execution_ledger_rows=[fill(), close, new], position_detail_rows=[detail(TradeID="T2")]))["root_position_id"] == "root-2"


def test_unbound_same_symbol_trade_blocks_even_when_lots_match():
    with pytest.raises(ValueError, match="unbound"):
        validate(arguments(execution_ledger_rows=[fill(), {"event_type": "broker_trade_callback_unbound", "vt_symbol": "SH611.CZCE"}]))


def test_detail_zero_rows_do_not_prove_a_positive_position():
    with pytest.raises(ValueError):
        validate(arguments(position_detail_rows=[]))
    with pytest.raises(ValueError):
        validate(arguments(broker_gross_volume=0, position_detail_rows=[]))


def test_short_position_and_multiple_owned_open_fills():
    first = fill(direction="short", volume=2, trade_volume_delta=2)
    second = fill(direction="short", volume=2, trade_volume_delta=2, tradeid="T2", vt_tradeid="CTP.T2", trade_fill_key="ctp:CZCE:T2")
    proof = validate(arguments(position_direction="short", execution_ledger_rows=[first, second],
                               position_detail_rows=[detail(Direction="1", Volume=2), detail(Direction="1", Volume=2, TradeID="T2")]))
    assert len(proof["open_trade_bindings"]) == 2


def test_detail_order_does_not_change_semantic_proof():
    first = fill(volume=2, trade_volume_delta=2)
    second = fill(volume=2, trade_volume_delta=2, tradeid="T2", vt_tradeid="CTP.T2", trade_fill_key="ctp:CZCE:T2")
    inputs = arguments(execution_ledger_rows=[first, second], position_detail_rows=[detail(Volume=2), detail(Volume=2, TradeID="T2")])
    original = validate(inputs)
    inputs["position_detail_rows"].reverse()
    assert validate(inputs)["open_trade_bindings"] == original["open_trade_bindings"]


def test_today_yesterday_split_uses_broker_opening_trading_day():
    proof = validate(sealed_arguments(day="20260908"))
    assert proof["today_volume"] == 2
    assert proof["yesterday_volume"] == 0
    assert proof["trading_day"] == "2026-09-08"
    next_day = validate(sealed_arguments())
    assert next_day["today_volume"] == 0
    assert next_day["yesterday_volume"] == 2


def test_night_natural_open_date_is_today_when_broker_opening_trading_day_is_today():
    event = fill(broker_trade_at="2026-09-07T21:30:00+08:00", broker_trading_day="2026-09-08",
                 broker_trade_date="2026-09-07", broker_hedge_flag="1", broker_trade_metadata_source="ctp_on_rtn_trade")
    proof = validate(arguments(execution_ledger_rows=[event]))
    assert proof["open_trade_bindings"][0]["open_date"] == "2026-09-07"
    assert proof["today_volume"] == 4
    assert proof["yesterday_volume"] == 0
    next_day = validate(arguments(execution_ledger_rows=[event], trading_day="2026-09-09",
                                  position_detail_rows=[detail(TradingDay="20260909")]))
    assert next_day["today_volume"] == 0
    assert next_day["yesterday_volume"] == 4


def test_closed_old_root_stays_zero_with_duplicate_callbacks():
    old_close = fill(offset="close", direction="short", tradeid="C1", vt_tradeid="CTP.C1", trade_fill_key="ctp:CZCE:C1")
    current = fill(root_position_id="root-2", position_epoch_id="epoch-2", tradeid="T2", vt_tradeid="CTP.T2", trade_fill_key="ctp:CZCE:T2")
    inputs = arguments(execution_ledger_rows=[fill(), old_close, old_close, current], position_detail_rows=[detail(TradeID="T2")])
    assert validate(inputs)["owned_net_volume"] == 4
    inputs["execution_ledger_rows"][1]["trade_volume_delta"] = 5
    inputs["execution_ledger_rows"][1]["volume"] = 5
    with pytest.raises(ValueError):
        validate(inputs)


@pytest.mark.parametrize("field", ["root_position_id", "position_epoch_id", "account_fingerprint"])
def test_conflicting_nested_close_owner_is_not_silently_overridden(field):
    event = fill(broker_close_sizing={field: "conflicting"})
    with pytest.raises(ValueError, match="conflict|mismatch"):
        validate(arguments(execution_ledger_rows=[event]))


@pytest.mark.parametrize("changes", [
    {"broker_gross_volume": True}, {"broker_gross_volume": 4.5},
    {"broker_gross_volume": 2 ** 53 + 1}, {"trading_day": "2026-02-30"},
    {"execution_ledger_rows": None}, {"position_detail_rows": None},
    {"vt_symbol": "SH611C2000.CZCE"},
])
def test_invalid_function_inputs_are_rejected(changes):
    with pytest.raises(ValueError):
        validate(arguments(**changes))


def test_non_json_or_nonfinite_evidence_fails_without_io():
    with pytest.raises(ValueError):
        validate(arguments(execution_ledger_rows=[fill(extra={"unsupported"})]))
    with pytest.raises(ValueError):
        validate(arguments(position_detail_rows=[detail(OpenPrice=float("nan"))]))


def test_linked_epoch_conflict_cannot_be_overwritten_by_fill():
    event = fill(intent_fingerprint="fp", intent_payload={"root_position_id": "different"})
    with pytest.raises(ValueError, match="conflict"):
        validate(arguments(execution_ledger_rows=[event]))


def test_unrepresentable_ctp_volume_cannot_match_after_float_rounding():
    volume = 2 ** 53
    with pytest.raises(ValueError):
        validate(arguments(broker_gross_volume=volume + 1,
                           execution_ledger_rows=[fill(volume=volume, trade_volume_delta=volume)],
                           position_detail_rows=[detail(Volume=volume)]))


@pytest.mark.parametrize("metadata", [
    {"broker_trade_date": "2026-09-08"}, {"broker_hedge_flag": "3"},
    {"broker_trade_metadata_source": "guessed_from_target_date"},
])
def test_conflicting_native_metadata_is_not_ignored(metadata):
    with pytest.raises(ValueError, match="metadata|hedge|trade_date"):
        validate(arguments(execution_ledger_rows=[fill(**metadata)]))


def test_native_metadata_matches_without_requiring_accountid():
    event = fill(broker_trade_date="2026-09-07", broker_hedge_flag="1", broker_trade_metadata_source="ctp_on_rtn_trade")
    assert validate(arguments(execution_ledger_rows=[event]))["confirmed"]


def ownership_sidecar(event, **changes):
    return {
        **{name: event[name] for name in ("tradeid", "vt_orderid", "vt_symbol", "direction", "offset", "volume", "price",
                                        "broker_trade_at", "intent_fingerprint", "root_position_id", "position_epoch_id")},
        "event_type": "broker_trade_ownership_metadata", "account_fingerprint": FINGERPRINT,
        "broker_trade_date": "2026-09-07", "broker_trading_day": "2026-09-07",
        "broker_hedge_flag": "1", "broker_trade_metadata_source": "ctp_on_rtn_trade", **changes,
    }


def test_sidecar_enriches_plain_fill_without_changing_canonical_body():
    event = fill(intent_fingerprint="fp")
    metadata = ownership_sidecar(event)
    del event["account_fingerprint"]
    del event["broker_trading_day"]
    proof = validate(arguments(execution_ledger_rows=[event, metadata]))
    assert proof["confirmed"]
    assert proof["yesterday_volume"] == 4
    assert "broker_trading_day" not in event and "account_fingerprint" not in event
    reversed_proof = validate(arguments(execution_ledger_rows=[metadata, event]))
    assert reversed_proof["open_trade_bindings"] == proof["open_trade_bindings"]


@pytest.mark.parametrize("changes", [
    {"account_fingerprint": "f" * 64}, {"broker_trade_at": "2026-09-08T09:30:00+08:00"},
    {"vt_orderid": "CTP.99_99_99"}, {"direction": "short"}, {"offset": "close"},
    {"price": 1949}, {"volume": 3}, {"root_position_id": "root-other"},
    {"position_epoch_id": "epoch-other"}, {"intent_fingerprint": "other-fp"},
    {"broker_trading_day": "2026-09-08"}, {"broker_trade_metadata_source": "guessed"},
])
def test_conflicting_sidecar_is_not_ignored_even_when_fill_has_metadata(changes):
    event = fill(intent_fingerprint="fp")
    with pytest.raises(ValueError, match="sidecar|conflict|mismatch"):
        validate(arguments(execution_ledger_rows=[event, ownership_sidecar(event, **changes)]))


def test_identical_sidecars_are_idempotent_and_conflicting_sidecars_fail():
    event = fill(intent_fingerprint="fp")
    metadata = ownership_sidecar(event)
    assert validate(arguments(execution_ledger_rows=[event, metadata, copy.deepcopy(metadata)]))["owned_net_volume"] == 4
    with pytest.raises(ValueError, match="sidecar|conflict"):
        validate(arguments(execution_ledger_rows=[event, metadata, {**metadata, "broker_trading_day": "2026-09-08"}]))


def test_sidecar_without_canonical_fill_cannot_create_owned_lots():
    with pytest.raises(ValueError):
        validate(arguments(execution_ledger_rows=[ownership_sidecar(fill(intent_fingerprint="fp"))]))


def test_sidecar_attaches_to_close_fill_and_checks_its_existing_epoch():
    opening = fill(volume=6, trade_volume_delta=6, intent_fingerprint="open-fp")
    close = fill(offset="close", direction="short", volume=2, trade_volume_delta=2,
                 tradeid="C1", vt_tradeid="CTP.C1", trade_fill_key="ctp:CZCE:C1", intent_fingerprint="close-fp")
    metadata = ownership_sidecar(close)
    del close["broker_trading_day"]
    assert validate(arguments(execution_ledger_rows=[opening, close, metadata]))["owned_net_volume"] == 4


def test_night_sidecar_restores_business_day_without_changing_open_date():
    event = fill(intent_fingerprint="fp", broker_trade_at="2026-09-07T21:30:00+08:00")
    metadata = ownership_sidecar(event, broker_trading_day="2026-09-08")
    del event["broker_trading_day"]
    proof = validate(arguments(execution_ledger_rows=[event, metadata]))
    assert proof["today_volume"] == 4 and proof["yesterday_volume"] == 0
    assert proof["open_trade_bindings"][0]["open_date"] == "2026-09-07"


def test_sidecar_for_one_fill_does_not_require_sidecar_keys_on_other_direct_fills():
    first = fill(volume=2, trade_volume_delta=2)
    second = fill(tradeid="T2", vt_tradeid="CTP.T2", trade_fill_key="ctp:CZCE:T2",
                  volume=2, trade_volume_delta=2, intent_fingerprint="fp2")
    metadata = ownership_sidecar(second)
    del second["broker_trading_day"]
    assert validate(arguments(execution_ledger_rows=[first, second, metadata],
                              position_detail_rows=[detail(Volume=2), detail(Volume=2, TradeID="T2")]))["confirmed"]


def test_unique_owned_candidate_does_not_authorize_a_trading_day_open_date_alias():
    old = fill(broker_trade_at="2026-09-07T21:30:00+08:00", broker_trading_day="2026-09-08")
    with pytest.raises(ValueError, match="unmatched.*open_date"):
        validate(arguments(execution_ledger_rows=[old], trading_day="2026-09-10",
                           position_detail_rows=[detail(TradeID="T1", OpenDate="20260908", TradingDay="20260910")]))


@pytest.mark.parametrize("symbol", ["SH611.CZCE", None, ""])
def test_conflict_sentinel_revokes_previously_valid_fill_and_metadata(symbol):
    event = fill(intent_fingerprint="fp")
    metadata = ownership_sidecar(event)
    ledger = [event, metadata]
    assert validate(arguments(execution_ledger_rows=ledger))["confirmed"]
    conflict = {"event_type": "broker_trade_ownership_metadata_conflict", "tradeid": "T1"}
    if symbol is not None:
        conflict["vt_symbol"] = symbol
    ledger.append(conflict)
    with pytest.raises(ValueError, match="metadata_conflict"):
        validate(arguments(execution_ledger_rows=ledger))


def test_conflict_sentinel_for_explicit_other_symbol_does_not_revoke_target():
    conflict = {"event_type": "broker_trade_ownership_metadata_conflict", "vt_symbol": "MA609.CZCE"}
    assert validate(arguments(execution_ledger_rows=[fill(), conflict]))["confirmed"]


def test_handwritten_open_date_alias_cannot_replace_a_validated_seal():
    event = fill(broker_trade_at="2026-09-07T21:30:00+08:00", broker_trading_day="20260908",
                 broker_open_date="20260908", broker_trade_metadata_source="ctp_on_rtn_trade")
    with pytest.raises(ValueError, match="open_date.*seal"):
        validate(arguments(execution_ledger_rows=[event], trading_day="20260909",
                           position_detail_rows=[detail(OpenDate="20260908", TradingDay="20260909")]))


@pytest.mark.parametrize("evidence", [None, {}, {"verified": True}])
def test_claimed_verified_seal_cannot_be_ignored_or_trusted(evidence):
    sidecar = {"event_type": "broker_position_open_date_sealed", "vt_symbol": "SH611.CZCE",
               "verified": True, "broker_open_date": "20260907", "evidence": evidence}
    with pytest.raises(ValueError, match="seal"):
        validate(arguments(execution_ledger_rows=[fill(), sidecar]))


def test_query_source_label_without_seal_is_not_a_native_metadata_whitelist():
    with pytest.raises(ValueError, match="metadata_source|seal"):
        validate(arguments(execution_ledger_rows=[fill(broker_trade_metadata_source="ctp_query_open_date_seal_v1")]))


def test_query_seal_recovers_missing_native_metadata_after_json_restart(monkeypatch):
    from qmt_roll_official_live_broker_open_date_seal import validate_open_date_seal

    inputs = json.loads(json.dumps(sealed_arguments()))
    canonical = ledger_event(inputs, "filled_or_part_filled")
    seen = []

    def inspect_raw(sidecar, canonical_fill, account_fingerprint):
        assert canonical_fill == canonical
        assert "broker_open_date" not in canonical_fill
        assert "broker_trading_day" not in canonical_fill
        seen.append(canonical_fill)
        return validate_open_date_seal(sidecar, canonical_fill, account_fingerprint)

    monkeypatch.setattr(importlib.import_module(MODULE), "validate_open_date_seal", inspect_raw)
    proof = validate(inputs)
    assert proof["confirmed"] and len(seen) == 1
    assert proof["yesterday_volume"] == 2
    binding = proof["open_trade_bindings"][0]
    assert binding["open_date_seal_identity"] == inputs["execution_ledger_rows"][-1]["seal_identity"]
    assert binding["broker_trade_metadata_source"] == "ctp_query_open_date_seal_v1"


@pytest.mark.parametrize("event_type", ["native_order_identity_persisted_before_insert", "filled_or_part_filled"])
@pytest.mark.parametrize("mutation", ["absent", "changed", "checksum_removed"])
def test_seal_embedded_native_and_fill_require_identical_actual_ledger_records(event_type, mutation):
    inputs = json.loads(json.dumps(sealed_arguments()))
    rows = inputs["execution_ledger_rows"]
    event = ledger_event(inputs, event_type)
    if mutation == "absent":
        rows.remove(event)
    elif mutation == "changed":
        event["generated_at"] = "2026-09-08T10:00:00+08:00"
    else:
        event.pop("record_checksum")
    with pytest.raises(ValueError, match="seal"):
        validate(inputs)


def test_linked_intent_reference_must_exist_in_actual_ledger():
    inputs = json.loads(json.dumps(sealed_arguments()))
    rows = inputs["execution_ledger_rows"]
    linked = next(row for row in rows if row.get("event_type") == "reserved")
    rows.remove(linked)
    with pytest.raises(ValueError, match="seal.*reference"):
        validate(inputs)
    rows.insert(0, copy.deepcopy(linked))
    assert validate(inputs)["confirmed"]


@pytest.mark.parametrize("changes", [
    {"broker_trade_date": "20260908"}, {"broker_trading_day": "20260907"},
    {"broker_open_date": "20260907"}, {"broker_hedge_flag": "3"},
    {"broker_trade_metadata_source": "claimed_verified"},
])
def test_raw_canonical_metadata_cannot_be_overwritten_by_valid_seal(changes):
    with pytest.raises(ValueError):
        validate(sealed_arguments(canonical_changes=changes))


@pytest.mark.parametrize("field,value", [
    ("broker_trade_date", "20260908"), ("broker_trading_day", "20260907"),
    ("broker_open_date", "20260907"), ("broker_hedge_flag", "3"),
])
def test_linked_payload_raw_metadata_cannot_be_hidden_by_canonical_merge(field, value):
    inputs = sealed_arguments(canonical_changes={"broker_trade_date": "20260907", "broker_trading_day": "20260908",
                                               "broker_open_date": "20260908", "broker_hedge_flag": "1"},
                              payload_changes={field: value})
    with pytest.raises(ValueError, match="seal.*conflict"):
        validate(inputs)


@pytest.mark.parametrize("native_sidecar", [False, True])
def test_matching_on_rtn_trade_metadata_and_validated_query_seal_coexist(native_sidecar):
    metadata = {"broker_trade_date": "20260907", "broker_trading_day": "20260908",
                "broker_hedge_flag": "1", "broker_trade_metadata_source": "ctp_on_rtn_trade"}
    inputs = sealed_arguments(canonical_changes=None if native_sidecar else metadata)
    if native_sidecar:
        inputs["execution_ledger_rows"].append(ownership_sidecar(ledger_event(inputs, "filled_or_part_filled"), **metadata))
    assert validate(inputs)["confirmed"]


def test_same_identity_fresh_query_proofs_are_idempotent_but_date_conflict_rejects():
    from qmt_roll_official_live_broker_open_date_seal import build_open_date_seals

    original = seal_inputs()
    first = build_open_date_seals(**original)[0]
    bundle = original["query_bundle"]
    for query in bundle["queries"].values():
        query["reqid"] += 10
        for callback in query["callbacks"]:
            callback["reqid"] += 10
    for name in ("query_watermark_before", "query_watermark_after"):
        bundle[name]["reqid"] += 10
    second = build_open_date_seals(**original)[0]
    assert first["seal_identity"] == second["seal_identity"]
    assert first["proof_sha256"] != second["proof_sha256"]
    inputs = arguments(execution_ledger_rows=original["execution_ledger_rows"] + [first, second],
                       broker_gross_volume=2, position_detail_rows=[detail(Volume=2, OpenDate="20260908")])
    assert validate(inputs)["confirmed"]
    bundle["queries"]["position_details"]["callbacks"][0]["data"]["OpenDate"] = "20260907"
    conflict = build_open_date_seals(**original)[0]
    inputs["execution_ledger_rows"].append(conflict)
    with pytest.raises(ValueError, match="seal.*conflict"):
        validate(inputs)


@pytest.mark.parametrize("symbol", [None, "", "SH611.CZCE"])
def test_seal_conflict_sentinel_revokes_symbol_ownership(symbol):
    inputs = sealed_arguments()
    inputs["execution_ledger_rows"].append({"event_type": "broker_position_open_date_seal_conflict", "vt_symbol": symbol})
    with pytest.raises(ValueError, match="seal.*conflict"):
        validate(inputs)


@pytest.mark.parametrize("field,value", [
    ("broker_trade_date", "20260908"), ("broker_trading_day", "20260907"),
    ("broker_open_date", "20260907"), ("broker_hedge_flag", "3"),
])
def test_on_rtn_sidecar_conflict_cannot_be_replaced_by_query_seal(field, value):
    inputs = sealed_arguments()
    metadata = ownership_sidecar(ledger_event(inputs, "filled_or_part_filled"), **{"broker_trading_day": "20260908", field: value})
    inputs["execution_ledger_rows"].append(metadata)
    with pytest.raises(ValueError, match="conflict|unverified"):
        validate(inputs)


@pytest.mark.parametrize("mutation", ["date", "proof", "canonical_checksum", "evidence_checksum", "invented_verified"])
def test_seal_tampering_cannot_change_owned_open_date(mutation):
    from test_official_live_broker_open_date_seal import digest

    inputs = json.loads(json.dumps(sealed_arguments()))
    seal = inputs["execution_ledger_rows"][-1]
    if mutation == "date":
        seal["broker_open_date"] = "20260907"
    elif mutation == "proof":
        seal["proof_sha256"] = "0" * 64
    elif mutation == "canonical_checksum":
        seal["canonical_fill_record_checksum"] = "0" * 64
    elif mutation == "evidence_checksum":
        seal["evidence"]["native_order_events"][0]["record_checksum"] = "0" * 64
    else:
        seal["verified"] = True
        seal["proof_sha256"] = digest({name: value for name, value in seal.items() if name != "proof_sha256"})
    with pytest.raises(ValueError, match="seal"):
        validate(inputs)


def test_existing_legacy_owner_cannot_hide_orphan_seal_for_same_symbol():
    seal = sealed_arguments()["execution_ledger_rows"][-1]
    with pytest.raises(ValueError, match="seal.*reference"):
        validate(arguments(execution_ledger_rows=[fill(), seal]))


def test_seal_for_other_explicit_symbol_does_not_block_current_owner():
    assert validate(arguments(execution_ledger_rows=[fill(), {
        "event_type": "broker_position_open_date_sealed", "vt_symbol": "MA609.CZCE", "evidence": None,
    }]))["confirmed"]


def test_seal_cannot_omit_conflicting_native_record_in_same_actual_batch():
    from test_official_live_broker_open_date_seal import digest

    inputs = json.loads(json.dumps(sealed_arguments()))
    conflicting = copy.deepcopy(ledger_event(inputs, "native_order_identity_persisted_before_insert"))
    conflicting["root_position_id"] = "other-root"
    conflicting["record_checksum"] = digest({name: value for name, value in conflicting.items() if name != "record_checksum"})
    inputs["execution_ledger_rows"].append(conflicting)
    with pytest.raises(ValueError, match="seal.*native.*conflict"):
        validate(inputs)


def test_sealed_historical_lot_and_today_native_lot_keep_separate_buckets():
    inputs = sealed_arguments()
    inputs["execution_ledger_rows"].append(fill(
        root_position_id="root", position_epoch_id="epoch", volume=2, trade_volume_delta=2,
        tradeid="T2", vt_tradeid="CTP.T2", trade_fill_key="ctp:CZCE:T2", vt_orderid="CTP.1_2_4",
        broker_trade_at="2026-09-09T09:30:00+08:00", broker_trading_day="20260909",
        broker_trade_date="20260909", broker_hedge_flag="1", broker_trade_metadata_source="ctp_on_rtn_trade",
    ))
    inputs["broker_gross_volume"] = 4
    inputs["position_detail_rows"].append(detail(TradeID="T2", Volume=2, OpenDate="20260909", TradingDay="20260909"))
    proof = validate(inputs)
    assert proof["today_volume"] == proof["yesterday_volume"] == 2


def test_restarted_sealed_ledger_enters_next_day_full_close_gate_with_empty_trade_order_queries(monkeypatch):
    import test_stage931_broker_sizing_gate as gate

    inputs = json.loads(json.dumps(sealed_arguments()))
    original_init = gate.FakeCloseTdApi.__init__
    original_request = gate.request

    def initialize(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.brokerid, self.userid = "broker", "account"

    def request(**changes):
        return original_request(**{**changes, "volume": 2})

    def change(row, trade, order, position, ledger):
        ledger[:] = copy.deepcopy(inputs["execution_ledger_rows"])
        trade.clear()
        order.clear()
        position.update(BrokerID="broker", InvestorID="account", Position=2, TodayPosition=0,
                        YdPosition=2, TradingDay="20260909")
        row.update(target_date="2026-09-09", planned_volume=2, volume=2)
        row["broker_close_sizing"].update(volume=2, broker_gross_volume=2, owned_net_volume=2,
                                         root_position_id="root", position_epoch_id="epoch",
                                         account_fingerprint=FINGERPRINT, target_date="2026-09-09")
        row["order_request"].update(volume=2, broker_close_sizing=copy.deepcopy(row["broker_close_sizing"]))
        row["order_request_json"] = json.dumps(row["order_request"])

    monkeypatch.setattr(gate.FakeCloseTdApi, "__init__", initialize)
    monkeypatch.setattr(gate.FakeCloseTdApi, "getTradingDay", lambda self: "20260909")
    monkeypatch.setattr(gate, "request", request)
    result, funds, td_api, _, _, _ = gate.run_close_gate(monkeypatch, change=change, details=inputs["position_detail_rows"])
    assert result["confirmed"], result["blockers"]
    assert funds["confirmed"], funds["blockers"]
    assert [call["kind"] for call in td_api.calls] == ["detail", "trade", "order", "position", "order"]
    assert td_api.native_calls == 0


def checksummed(event):
    from test_official_live_broker_open_date_seal import digest

    result = copy.deepcopy(event)
    result["record_checksum"] = digest({name: value for name, value in result.items() if name != "record_checksum"})
    return result


def test_seal_cannot_omit_additional_canonical_fill_for_terminal_order():
    from qmt_roll_official_live_broker_open_date_seal import build_open_date_seals

    inputs = sealed_arguments()
    extra = checksummed({**ledger_event(inputs, "filled_or_part_filled"),
        "tradeid": "T2", "vt_tradeid": "CTP.T2", "trade_fill_key": "ctp:CZCE:T2", "broker_callback_key": "extra-fill",
        "volume": 1, "trade_volume_delta": 1, "account_fingerprint": FINGERPRINT,
        "broker_trade_date": "20260907", "broker_trading_day": "20260908",
        "broker_hedge_flag": "1", "broker_trade_metadata_source": "ctp_on_rtn_trade"})
    inputs["execution_ledger_rows"].append(extra)
    inputs["broker_gross_volume"] = 3
    inputs["position_detail_rows"].append(detail(TradeID="T2", Volume=1, OpenDate="20260907", TradingDay="20260909"))
    native = ledger_event(inputs, "native_order_identity_persisted_before_insert")
    seal = ledger_event(inputs, "broker_position_open_date_sealed")
    with pytest.raises(ValueError, match="trade_coverage"):
        build_open_date_seals(execution_ledger_rows=[row for row in inputs["execution_ledger_rows"] if row.get("event_type") != "broker_position_open_date_sealed"], native_order_event=native,
                             flat_baseline_event=native["flat_baseline_event"], query_bundle=seal["evidence"]["query_bundle"],
                             account_fingerprint=FINGERPRINT)
    with pytest.raises(ValueError, match="seal.*canonical.*(complete|conflict)"):
        validate(inputs)


def test_seal_cannot_omit_other_lease_reservation_without_safe_terminal():
    inputs = sealed_arguments()
    history = seal_inputs(prior_safe_retry=True)["execution_ledger_rows"]
    prior = next(row for row in history if row.get("event_type") == "reserved" and row.get("spool_lease_token") == "old-lease")
    inputs["execution_ledger_rows"].insert(0, prior)
    with pytest.raises(ValueError, match="seal.*(history|linked).*(complete|conflict)"):
        validate(inputs)


@pytest.mark.parametrize("recovery", [False, True])
def test_real_safe_reservation_history_survives_restart_and_unrelated_audits(recovery):
    inputs = json.loads(json.dumps(sealed_arguments(prior_safe_retry=not recovery, prior_recovery=recovery)))
    rows = inputs["execution_ledger_rows"]
    assert rows[0]["event_type"] == "reserved"
    assert rows[2]["event_type"] == "reserved"
    original = validate(inputs)
    current = ledger_event(inputs, "filled_or_part_filled")
    for event_type in ("broker_order_query_terminal_observed", "reconciliation_completed", "execution_audit"):
        rows.append(checksummed({"event_type": event_type, "intent_fingerprint": current["intent_fingerprint"],
                                "vt_symbol": current["vt_symbol"], "spool_lease_owner": current["spool_lease_owner"],
                                "spool_lease_token": current["spool_lease_token"], "traded": 2}))
    assert validate(inputs)["open_trade_bindings"] == original["open_trade_bindings"]


def repriced_retry_arguments(tmp_path, recovery):
    from qmt_roll_official_live_execution_ledger import (
        append_pre_api_slot_no_side_effect_terminal, read_execution_ledger,
        recover_expired_spool_lease, reserve_execution_ledger_intent,
    )
    from qmt_roll_official_live_broker_open_date_seal import build_open_date_seals, validate_open_date_seal
    from test_official_live_broker_open_date_seal import resign_inputs

    inputs = seal_inputs()
    owner = ledger_event(inputs, "reserved")
    native = inputs["native_order_event"]
    canonical = ledger_event(inputs, "filled_or_part_filled")
    request = inputs["flat_baseline_event"]["physical_requests"][0]
    reserve_args = dict(target_date=owner["target_date"], row=owner["intent_payload"],
                        close_retry_after_cancel_seconds=30, path=tmp_path / "ledger.ndjson")
    prior = reserve_execution_ledger_intent(**reserve_args, order_request={**request, "price": 1947},
                                          base_event={**owner, "spool_lease_token": "old-lease"})
    assert prior["reserved"]
    if recovery:
        result = recover_expired_spool_lease(**reserve_args, order_request={**request, "price": 1947},
                                            spool_lease_owner=owner["spool_lease_owner"], spool_lease_token="old-lease")
        assert result.disposition == "requeue_pre_send"
    else:
        terminal = append_pre_api_slot_no_side_effect_terminal(
            **{name: prior["latest_ledger_event"][name] for name in
               ("target_date", "intent_id", "intent_payload_sha256", "intent_kind", "intent_fingerprint", "spool_lease_owner", "spool_lease_token")},
            reservation_record_checksum=prior["latest_ledger_event"]["record_checksum"],
            blockers=["authorization_expired"], blocked_phase="pre_api_slot", path=reserve_args["path"])
        assert terminal["appended"]
    current = reserve_execution_ledger_intent(**reserve_args, order_request=request, base_event=owner)
    assert current["reserved"]
    assert prior["intent_fingerprint"] == current["intent_fingerprint"] == native["intent_fingerprint"]
    inputs["execution_ledger_rows"] = read_execution_ledger(reserve_args["path"]) + [native, canonical]
    resign_inputs(inputs)
    seals = build_open_date_seals(**inputs)
    validate_open_date_seal(seals[0], canonical, inputs["account_fingerprint"])
    return arguments(execution_ledger_rows=inputs["execution_ledger_rows"] + seals, broker_gross_volume=2,
                     trading_day="20260909", position_detail_rows=[detail(Volume=2, OpenDate="20260908", TradingDay="20260909")])


@pytest.mark.parametrize("recovery", [False, True])
def test_sealed_repriced_safe_retry_uses_exact_current_reservation(tmp_path, recovery):
    inputs = repriced_retry_arguments(tmp_path, recovery)
    reservations = [row for row in inputs["execution_ledger_rows"] if row.get("event_type") == "reserved"]
    assert [row["intent_payload"]["limit_price"] for row in reservations] == [1947, 1948]
    proof = validate(json.loads(json.dumps(inputs)))
    assert proof["confirmed"] and proof["owned_net_volume"] == 2


@pytest.mark.parametrize("recovery", [False, True])
@pytest.mark.parametrize("mutation", ["absent", "modified", "no_seal"])
def test_repriced_retry_requires_verified_safe_history(tmp_path, recovery, mutation):
    inputs = repriced_retry_arguments(tmp_path, recovery)
    rows = inputs["execution_ledger_rows"]
    kind = "spool_crash_recovery_pre_send_safe_terminal" if recovery else "pre_api_slot_no_side_effect_safe_terminal"
    terminal = ledger_event(inputs, kind)
    if mutation == "absent":
        rows.remove(terminal)
    elif mutation == "modified":
        terminal["spool_lease_token"] = "unproven-lease"
    else:
        rows.remove(ledger_event(inputs, "broker_position_open_date_sealed"))
    with pytest.raises(ValueError, match="linked_payload_conflict" if mutation == "no_seal" else "seal.*(reference|history)"):
        validate(inputs)


@pytest.mark.parametrize("recovery", [False, True])
@pytest.mark.parametrize("mutation", ["absent", "modified", "reordered"])
def test_reservation_safe_terminal_requires_exact_actual_record_and_order(recovery, mutation):
    inputs = json.loads(json.dumps(sealed_arguments(prior_safe_retry=not recovery, prior_recovery=recovery)))
    rows = inputs["execution_ledger_rows"]
    kind = "spool_crash_recovery_pre_send_safe_terminal" if recovery else "pre_api_slot_no_side_effect_safe_terminal"
    terminal = ledger_event(inputs, kind)
    if mutation == "absent":
        rows.remove(terminal)
    elif mutation == "modified":
        terminal["spool_lease_token"] = "not-the-original-lease"
    else:
        rows.remove(terminal)
        rows.append(terminal)
    with pytest.raises(ValueError, match="seal.*(reference|history)"):
        validate(inputs)


@pytest.mark.parametrize("event_type", [
    "api_slot_reserved", "send_order_called", "send_order_returned", "submitted_to_ctp",
    "adapter_exception_after_reserve", "native_order_identity_persisted_before_insert", "post_api_slot_no_native_safe_terminal",
])
@pytest.mark.parametrize("identity", ["fingerprint", "lease_only", "slot_child", "other_fingerprint"])
def test_seal_cannot_omit_later_side_effect_for_historical_safe_lease(event_type, identity):
    inputs = sealed_arguments(prior_safe_retry=True)
    prior = ledger_event(inputs, "reserved")
    effect = {name: prior[name] for name in ("intent_fingerprint", "spool_lease_owner", "spool_lease_token", "vt_symbol")}
    effect.update(event_type=event_type, send_slot_reserved=1)
    if identity != "fingerprint":
        effect.pop("intent_fingerprint")
    if identity == "other_fingerprint":
        effect["intent_fingerprint"] = "f" * 64
    if identity == "slot_child":
        effect["api_slot_batch_children"] = [{name: effect.pop(name) for name in ("spool_lease_owner", "spool_lease_token")}]
    inputs["execution_ledger_rows"].append(checksummed(effect))
    with pytest.raises(ValueError, match="seal.*(history|native).*(complete|conflict)"):
        validate(inputs)


@pytest.mark.parametrize("event_type", ["native_order_identity_persisted_before_insert", "filled_or_part_filled"])
def test_identical_native_and_canonical_replay_is_idempotent(event_type):
    inputs = sealed_arguments()
    expected = validate(inputs)
    inputs["execution_ledger_rows"].append(copy.deepcopy(ledger_event(inputs, event_type)))
    assert validate(inputs)["open_trade_bindings"] == expected["open_trade_bindings"]


def test_seal_cannot_omit_same_order_native_under_another_batch():
    inputs = sealed_arguments()
    extra = checksummed({**ledger_event(inputs, "native_order_identity_persisted_before_insert"), "physical_batch_id": "other-batch"})
    inputs["execution_ledger_rows"].append(extra)
    with pytest.raises(ValueError, match="seal.*native.*conflict"):
        validate(inputs)


def test_same_trade_with_different_record_checksum_is_not_identical_replay():
    inputs = sealed_arguments()
    original = ledger_event(inputs, "filled_or_part_filled")
    extra = checksummed({**original, "broker_callback_key": "not-the-original-canonical-record"})
    inputs["execution_ledger_rows"].append(extra)
    with pytest.raises(ValueError, match="seal.*canonical.*(complete|conflict)"):
        validate(inputs)


def test_complete_multi_fill_seals_restore_owned_lots_after_partial_persist_reuse(tmp_path):
    from test_official_live_broker_open_date_seal import resign_inputs, shift_bundle
    from qmt_roll_official_live_broker_open_date_seal import build_open_date_seals
    from qmt_roll_official_live_execution_ledger import append_broker_callback_event_once

    inputs = seal_inputs()
    first = ledger_event(inputs, "filled_or_part_filled")
    second = checksummed({**first, "tradeid": "T2", "vt_tradeid": "CTP.T2", "trade_fill_key": "ctp:CZCE:T2",
                          "broker_callback_key": "second-fill", "volume": 1, "trade_volume_delta": 1})
    inputs["execution_ledger_rows"].append(second)
    queries = inputs["query_bundle"]["queries"]
    for name in ("trades", "position_details"):
        callback = copy.deepcopy(queries[name]["callbacks"][0])
        callback["data"].update(TradeID="T2", Volume=1)
        queries[name]["callbacks"].insert(1, callback)
    for name in ("order_before", "order_after"):
        queries[name]["callbacks"][0]["data"].update(VolumeTraded=3, VolumeTotal=1)
    queries["positions"]["callbacks"][0]["data"].update(Position=3, TodayPosition=3)
    resign_inputs(inputs)
    seals = build_open_date_seals(**inputs)
    saved = append_broker_callback_event_once(seals[0], tmp_path / "ledger")["ledger_event"]
    inputs["execution_ledger_rows"].append(saved)
    shift_bundle(inputs["query_bundle"], reqid_delta=10, time_delta=1000)
    restored = build_open_date_seals(**inputs)
    assert restored[0] == saved
    inputs["execution_ledger_rows"].extend(restored[1:])
    proof = validate(arguments(execution_ledger_rows=json.loads(json.dumps(inputs["execution_ledger_rows"])),
        broker_gross_volume=3, trading_day="20260909", position_detail_rows=[
            detail(Volume=2, OpenDate="20260908", TradingDay="20260909"),
            detail(TradeID="T2", Volume=1, OpenDate="20260908", TradingDay="20260909"),
        ]))
    assert proof["owned_net_volume"] == proof["yesterday_volume"] == 3
    assert len(proof["open_trade_bindings"]) == 2
