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
    event = fill(broker_trade_at="2026-09-07T21:30:00+08:00", target_date="2026-09-08",
                 broker_trading_day="20260908", broker_open_date="20260908")
    inputs = arguments(execution_ledger_rows=[event], trading_day="20260909",
                       position_detail_rows=[detail(OpenDate="20260908", TradingDay="20260909")])
    assert validate(inputs)["confirmed"]
    del event["broker_open_date"]
    with pytest.raises(ValueError, match="open.*(date|fill)|unmatched"):
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
    old = fill(volume=2, trade_volume_delta=2)
    night = fill(volume=2, trade_volume_delta=2, tradeid="N1", vt_tradeid="CTP.N1", trade_fill_key="ctp:CZCE:N1",
                 broker_trade_at="2026-09-07T21:30:00+08:00", broker_trading_day="2026-09-08", broker_open_date="2026-09-08")
    proof = validate(arguments(execution_ledger_rows=[old, night],
                               position_detail_rows=[detail(Volume=2), detail(TradeID="N1", Volume=2, OpenDate="20260908")]))
    assert proof["today_volume"] == proof["yesterday_volume"] == 2
    assert proof["trading_day"] == "2026-09-08"


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
