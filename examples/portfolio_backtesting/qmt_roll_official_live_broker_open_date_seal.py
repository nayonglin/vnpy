"""Replay durable native-to-detail ownership evidence without I/O or date inference."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
import hashlib
import json
import math
import re
from typing import Any
from zoneinfo import ZoneInfo


VERSION = "ctp_owned_open_date_seal_v1"
SOURCE = "ctp_query_open_date_seal_v1"
EVENT = "broker_position_open_date_sealed"
OWNER_FIELDS = ("intent_fingerprint", "root_position_id", "position_epoch_id", "vt_symbol")
OWNED_SOURCES = {"stage901_pending_order", "stage904_c9_intraday_retry_open"}
TERMINAL = {"0", "2", "4", "5"}
OPEN_DATE_SEAL_MAX_WINDOW_NS = 8_000_000_000
EVENT_FIELDS = {"event_order_count", "event_trade_count", "event_position_count"}
NATIVE_FIELDS = {"send_order_api_called_count", "cancel_order_api_called_count", "order_api_called_count", "order_api_evidence_complete"}
LEASE_FIELDS = ("spool_lease_owner", "spool_lease_token")
REQUEST_OPTIONAL_FIELDS = {
    "order_before": {"InstrumentID", "ExchangeID", "OrderSysID", "InsertTimeStart", "InsertTimeEnd", "InvestUnitID"},
    "order_after": {"InstrumentID", "ExchangeID", "OrderSysID", "InsertTimeStart", "InsertTimeEnd", "InvestUnitID"},
    "trades": {"InstrumentID", "ExchangeID", "TradeID", "TradeTimeStart", "TradeTimeEnd", "InvestUnitID"},
    "positions": {"InstrumentID", "ExchangeID", "InvestUnitID"},
    "position_details": {"InstrumentID", "ExchangeID", "InvestUnitID"},
}


def _fail(reason: str) -> None:
    raise ValueError(f"broker_open_date_seal:{reason}")


def _json(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("broker_open_date_seal:non_json_evidence") from exc


def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("missing_text")
    return value.strip()


def _date(value: Any) -> str:
    value = _text(value)
    if re.fullmatch(r"\d{8}", value):
        value = f"{value[:4]}-{value[4:6]}-{value[6:]}"
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        _fail("invalid_date")


def _number(value: Any, *, zero: bool = False, integer: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        _fail("invalid_number")
    if value < 0 or (not zero and value == 0) or value >= 1e100 or (integer and (int(value) != value or value > 2147483647)):
        _fail("invalid_number_range")
    return value


def _direction(value: Any) -> str:
    if value in ("long", "多", "0"):
        return "long"
    if value in ("short", "空", "1"):
        return "short"
    _fail("direction")


def _open(value: Any) -> None:
    if value not in ("open", "开", "0"):
        _fail("not_open")


def _record(row: Mapping[str, Any]) -> None:
    if not isinstance(row, Mapping) or row.get("record_checksum") != _sha({name: value for name, value in row.items() if name != "record_checksum"}):
        _fail("ledger_checksum")


def _symbol(row: Mapping[str, Any]) -> str:
    return f"{_text(row.get('InstrumentID'))}.{_text(row.get('ExchangeID'))}".upper()


def _account(row: Mapping[str, Any], fingerprint: str) -> None:
    broker = _text(row.get("BrokerID"))
    investor = _text(row.get("InvestorID"))
    if hashlib.sha256(f"{broker}\0{investor}".encode()).hexdigest() != fingerprint:
        _fail("account_mismatch")


def _watermark(value: Any, *, native: bool = False) -> dict[str, int]:
    if not isinstance(value, dict) or set(value) != (NATIVE_FIELDS if native else EVENT_FIELDS):
        _fail("watermark_fields")
    for count in value.values():
        if type(count) is not int:
            _fail("watermark_counter")
        _number(count, zero=True, integer=True)
    if native and (value["order_api_evidence_complete"] != 1 or value["order_api_called_count"] !=
                   value["send_order_api_called_count"] + value["cancel_order_api_called_count"]):
        _fail("native_api_evidence_incomplete")
    return value


def _monotonic(value: Any) -> int:
    if type(value) is not int or value <= 0:
        _fail("monotonic_timestamp")
    return value


def _query_watermark(value: Any) -> int:
    if not isinstance(value, dict) or set(value) != {"reqid"} or type(value["reqid"]) is not int:
        _fail("query_watermark")
    return int(_number(value["reqid"], zero=True, integer=True))


def _envelope(bundle: Mapping[str, Any], names: tuple[str, ...], fingerprint: str) -> dict[str, list[dict[str, Any]]]:
    _text(bundle.get("service_generation"))
    _text(bundle.get("connection_generation"))
    if _date(bundle.get("trading_day_before")) != _date(bundle.get("trading_day_after")):
        _fail("trading_day_changed")
    start = _monotonic(bundle.get("started_monotonic_ns"))
    end = _monotonic(bundle.get("completed_monotonic_ns"))
    deadline = _monotonic(bundle.get("deadline_monotonic_ns"))
    window = _monotonic(bundle.get("max_window_ns"))
    if not start <= end <= deadline or window > OPEN_DATE_SEAL_MAX_WINDOW_NS or deadline - start > window:
        _fail("deadline")
    before = _watermark(bundle.get("event_watermark_before"))
    after = _watermark(bundle.get("event_watermark_after"))
    if before != after:
        _fail("event_watermark")
    if _watermark(bundle.get("native_api_watermark_before"), native=True) != _watermark(bundle.get("native_api_watermark_after"), native=True):
        _fail("native_api_watermark")
    queries = bundle.get("queries")
    if not isinstance(queries, dict) or set(queries) != set(names):
        _fail("query_sequence")
    previous_reqid = _query_watermark(bundle.get("query_watermark_before"))
    previous_time = start
    output = {}
    for name in names:
        query = queries[name]
        reqid = _number(query.get("reqid"), integer=True)
        if type(reqid) is not int or reqid != previous_reqid + 1 or type(query.get("request_ret")) is not int or query["request_ret"] != 0:
            _fail("query_reqid_or_return")
        request = query.get("request", {})
        _account(request, fingerprint)
        if set(request) - {"BrokerID", "InvestorID"} - REQUEST_OPTIONAL_FIELDS[name] or any(
            request[field] != "" for field in set(request) - {"BrokerID", "InvestorID"}
        ):
            _fail("query_request_scope")
        issued = _monotonic(query.get("started_monotonic_ns"))
        if not previous_time <= issued <= end:
            _fail("query_started_time")
        previous_time = issued
        callbacks = query.get("callbacks")
        if not isinstance(callbacks, list) or not callbacks:
            _fail("query_callbacks_missing")
        raw = []
        for index, callback in enumerate(callbacks):
            received = _monotonic(callback.get("received_monotonic_ns"))
            if not previous_time <= received <= end:
                _fail("callback_time")
            previous_time = received
            error = callback.get("error")
            if not isinstance(error, dict) or (error and (type(error.get("ErrorID")) is not int or error["ErrorID"] != 0)):
                _fail("query_error")
            if type(callback.get("reqid")) is not int or callback["reqid"] != reqid or callback.get("last") is not (index == len(callbacks) - 1):
                _fail("query_callback_boundary")
            data = callback.get("data")
            if not isinstance(data, dict):
                _fail("query_raw_missing")
            if data:
                _account(data, fingerprint)
                raw.append(data)
        output[name] = raw
        previous_reqid = reqid
    if _query_watermark(bundle.get("query_watermark_after")) != previous_reqid:
        _fail("query_watermark")
    return output


def _orders(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    result = {}
    for row in rows:
        key = (_text(row.get("ExchangeID")), _text(row.get("OrderSysID")))
        if key in result:
            _fail("duplicate_order")
        if str(row.get("OrderStatus")) not in TERMINAL:
            _fail("active_order")
        volume = _number(row.get("VolumeTotalOriginal"), integer=True)
        traded = _number(row.get("VolumeTraded"), zero=True, integer=True)
        remaining = _number(row.get("VolumeTotal"), zero=True, integer=True)
        if traded + remaining != volume:
            _fail("order_volume")
        status = row.get("OrderStatus")
        if (status == "0" and traded != volume) or (status == "4" and traded != 0) or (status == "2" and not 0 < traded < volume):
            _fail("order_terminal_volume_conflict")
        result[key] = row
    return result


def _same_orders(first: list[dict[str, Any]], second: list[dict[str, Any]]) -> None:
    if sorted(map(_sha, first)) != sorted(map(_sha, second)):
        _fail("order_snapshot_changed")


def _positions(rows: list[dict[str, Any]], symbol: str, day: str) -> list[dict[str, Any]]:
    result = []
    identities = set()
    for row in rows:
        if _symbol(row) != symbol:
            continue
        volume = _number(row.get("Position"), zero=True, integer=True)
        today = _number(row.get("TodayPosition"), zero=True, integer=True)
        if (_date(row.get("TradingDay")) != day or row.get("PosiDirection") not in {"2", "3"}
                or row.get("HedgeFlag") != "1" or row.get("PositionDate") not in {"1", "2"}
                or row.get("InvestUnitID") not in (None, "") or today > volume):
            _fail("position_kind_or_day")
        if symbol.rpartition(".")[2] in {"SHFE", "INE"} and today != (volume if row["PositionDate"] == "1" else 0):
            _fail("position_date_volume")
        identity = (symbol, row["PosiDirection"], row["HedgeFlag"], row["PositionDate"])
        if identity in identities:
            _fail("duplicate_position")
        identities.add(identity)
        result.append(row)
    return result


def _ledger_account(row: Mapping[str, Any], fingerprint: str) -> None:
    if row.get("account_fingerprint") not in (None, "", fingerprint):
        _fail("ledger_account_conflict")
    if "BrokerID" in row or "InvestorID" in row:
        _account(row, fingerprint)


def _unique_records(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    records = {}
    for row in rows:
        _record(row)
        records.setdefault(_sha(row), row)
    return list(records.values())


def collect_open_date_reservation_history(execution_ledger_rows: Sequence[Mapping[str, Any]], native_order_event: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Project exact reservation and side-effect evidence, excluding ordinary later audits."""
    from qmt_roll_official_live_execution_ledger import (
        POST_API_SLOT_SAFE_TERMINAL_EVENT, PRE_API_SLOT_SAFE_TERMINAL_EVENT,
        RECOVERY_SIDE_EFFECT_EVENTS, _recovery_event_matches_lease,
    )

    try:
        rows, native = _json([execution_ledger_rows, native_order_event])
        intent = _text(native.get("intent_fingerprint"))
        leases = {(native.get("spool_lease_owner"), native.get("spool_lease_token"))}
        leases.update((row.get("spool_lease_owner"), row.get("spool_lease_token")) for row in rows
                      if row.get("event_type") == "reserved" and row.get("intent_fingerprint") == intent)
        kinds = RECOVERY_SIDE_EFFECT_EVENTS | {"reserved", PRE_API_SLOT_SAFE_TERMINAL_EVENT,
                                              POST_API_SLOT_SAFE_TERMINAL_EVENT, "spool_crash_recovery_pre_send_safe_terminal"}
        result = []
        for row in rows:
            if row.get("event_type") == EVENT:
                continue
            relevant = (row.get("event_type") in kinds or isinstance(row.get("intent_payload"), dict)
                        or (row.get("event_type") == "adapter_exception_after_reserve" and row.get("send_slot_reserved") == 1))
            if relevant and (row.get("intent_fingerprint") == intent or any(
                owner and token and _recovery_event_matches_lease(row, spool_lease_owner=owner, spool_lease_token=token)
                for owner, token in leases
            )):
                result.append(row)
        return _unique_records(result)
    except (KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError("broker_open_date_seal:malformed_reservation_history") from exc


def _linked_ownership(evidence: Mapping[str, Any], native: Mapping[str, Any], fingerprint: str) -> None:
    from qmt_roll_official_live_execution_ledger import (
        POST_API_SLOT_SAFE_TERMINAL_EVENT, PRE_API_SLOT_SAFE_TERMINAL_EVENT, RECOVERY_SIDE_EFFECT_EVENTS, _WARM_RESERVATION_IDENTITY_FIELDS,
        _recovery_event_matches_lease, _valid_pre_api_slot_safe_terminal, _warm_reservation_identity_blocker,
        intent_fingerprint,
    )

    linked = evidence.get("linked_intent_events")
    if not isinstance(linked, list) or not linked:
        _fail("linked_intent_missing")
    history = evidence.get("reservation_history")
    if not isinstance(history, list) or not history:
        _fail("reservation_history_missing")
    if collect_open_date_reservation_history(history, native) != history:
        _fail("reservation_history_projection")
    for row in history:
        _record(row)
        if row.get("intent_fingerprint") != native["intent_fingerprint"]:
            _fail("reservation_history_fingerprint")
    if linked != [row for row in history if isinstance(row.get("intent_payload"), dict)]:
        _fail("reservation_history_payload_references")
    identity = {name: _text(native.get(name)) for name in (*_WARM_RESERVATION_IDENTITY_FIELDS, "reservation_record_checksum")}
    blocker, current, current_index = _warm_reservation_identity_blocker(history, identity)
    if blocker or current is None:
        _fail(f"reservation_identity:{blocker}")
    if any(row.get("event_type") in {PRE_API_SLOT_SAFE_TERMINAL_EVENT, POST_API_SLOT_SAFE_TERMINAL_EVENT,
                                     "spool_crash_recovery_pre_send_safe_terminal"}
           and _recovery_event_matches_lease(row, spool_lease_owner=identity["spool_lease_owner"],
                                            spool_lease_token=identity["spool_lease_token"])
           for row in history):
        _fail("current_reservation_safe_terminal")
    if native not in history or any(fill not in history for fill in evidence.get("canonical_fills", [])):
        _fail("reservation_history_native_or_fill_missing")
    excluded = set()
    reservations = [row for row in history if row.get("event_type") == "reserved"]
    for reservation in reservations:
        _record(reservation)
        payload = reservation.get("intent_payload")
        if not isinstance(payload, dict):
            _fail("linked_intent_payload_missing")
        _number(payload.get("volume"), integer=True)
        computed, _ = intent_fingerprint(_text(payload.get("target_date")), payload, payload)
        if computed != native["intent_fingerprint"] or reservation.get("intent_fingerprint") != computed:
            _fail("reservation_payload_fingerprint")
        for field in _WARM_RESERVATION_IDENTITY_FIELDS:
            _text(reservation.get(field))
        if reservation == current:
            continue
        old_identity = {name: reservation[name] for name in _WARM_RESERVATION_IDENTITY_FIELDS}
        if all(old_identity[name] == identity[name] for name in LEASE_FIELDS):
            _fail("duplicate_current_reservation")
        old_index = history.index(reservation)
        if old_index >= current_index:
            _fail("reservation_history_order")
        old_events = [row for row in history if _recovery_event_matches_lease(
            row, spool_lease_owner=old_identity["spool_lease_owner"], spool_lease_token=old_identity["spool_lease_token"])]
        if any(row.get("event_type") in RECOVERY_SIDE_EFFECT_EVENTS or
               (row.get("event_type") == "adapter_exception_after_reserve" and row.get("send_slot_reserved") == 1)
               for row in old_events):
            _fail("historical_reservation_side_effect")
        terminals = []
        for terminal in history[old_index + 1:current_index]:
            if terminal.get("event_type") == PRE_API_SLOT_SAFE_TERMINAL_EVENT:
                if terminal.get("reservation_record_checksum") == reservation["record_checksum"]:
                    if not _valid_pre_api_slot_safe_terminal(terminal, reservation):
                        _fail("historical_reservation_safe_terminal_conflict")
                    terminals.append(terminal)
            elif terminal.get("event_type") == "spool_crash_recovery_pre_send_safe_terminal":
                if (all(terminal.get(name) == reservation.get(name) for name in
                        ("target_date", "intent_fingerprint", "intent_id", *LEASE_FIELDS))
                        and terminal.get("intent_payload") == payload
                        and terminal.get("pre_send_exception_confirmed") == 1
                        and terminal.get("send_slot_reserved") == 0
                        and terminal.get("recovered_from_event_type") == "reserved"):
                    terminals.append(terminal)
        if not terminals:
            _fail("historical_reservation_safe_terminal_missing")
        excluded.add(reservation["record_checksum"])
    payloads = []
    for row in linked:
        _record(row)
        if row.get("intent_fingerprint") != native["intent_fingerprint"]:
            _fail("linked_intent_identity")
        if row.get("record_checksum") in excluded or (
            row.get("event_type") == "spool_crash_recovery_pre_send_safe_terminal" and any(
                prior["record_checksum"] in excluded and all(row.get(name) == prior.get(name) for name in LEASE_FIELDS)
                for prior in reservations)):
            continue
        payload = row.get("intent_payload")
        if not isinstance(payload, dict) or not payload:
            _fail("linked_intent_payload_missing")
        for source in (row, payload):
            _ledger_account(source, fingerprint)
            for field in (*OWNER_FIELDS, "source", "target_date", "intent_id", "intent_payload_sha256", *LEASE_FIELDS):
                if source.get(field) not in (None, "") and source[field] != native.get(field):
                    _fail("linked_intent_conflict")
        for field in ("root_position_id", "position_epoch_id", "vt_symbol", "source", "target_date"):
            if payload.get(field) != native.get(field):
                _fail("linked_payload_owner")
        _open(payload.get("offset"))
        if _direction(payload.get("direction")) != _direction(native.get("direction")):
            _fail("linked_payload_direction")
        computed, _ = intent_fingerprint(_text(payload.get("target_date")), payload, payload)
        if computed != native["intent_fingerprint"] or _number(payload.get("volume"), integer=True) != _number(native.get("volume"), integer=True):
            _fail("reservation_payload_fingerprint_or_volume")
        if payloads and payloads[0] != payload:
            _fail("linked_payload_conflict")
        payloads.append(payload)
    if not payloads:
        _fail("current_reservation_payload_missing")


def _rebuild(evidence: Mapping[str, Any], fingerprint: str) -> list[dict[str, Any]]:
    if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        _fail("fingerprint")
    native_rows = evidence.get("native_order_events")
    if not isinstance(native_rows, list) or len(native_rows) != 1:
        _fail("single_open_child_required")
    native = native_rows[0]
    _record(native)
    if native.get("event_type") != "native_order_identity_persisted_before_insert" or native.get("source") not in OWNED_SOURCES:
        _fail("native_owner_missing")
    if native.get("account_fingerprint") != fingerprint:
        _fail("native_account")
    for field in LEASE_FIELDS:
        _text(native.get(field))
    _linked_ownership(evidence, native, fingerprint)
    owner = {name: _text(native.get(name)) for name in OWNER_FIELDS}
    symbol = owner["vt_symbol"].upper()
    baseline = evidence.get("flat_baseline_event", {})
    if native.get("flat_baseline_event") != baseline or native.get("flat_baseline_sha256") != _sha(baseline):
        _fail("durable_flat_baseline_missing")
    if baseline.get("event_type") != "broker_open_flat_baseline" or baseline.get("version") != "ctp_owned_open_flat_baseline_v1":
        _fail("baseline_version")
    if any(baseline.get(name) != value for name, value in owner.items()) or baseline.get("account_fingerprint") != fingerprint:
        _fail("baseline_owner")
    batch = _text(native.get("physical_batch_id"))
    if baseline.get("physical_batch_id") != batch:
        _fail("baseline_batch")
    requests = baseline.get("physical_requests")
    if not isinstance(requests, list) or len(requests) != 1:
        _fail("single_open_child_required")
    request = requests[0]
    for child in (request, native):
        if child.get("child_order_index") != 0 or child.get("child_order_count") != 1:
            _fail("single_open_child_required")
        _open(child.get("offset"))
    if f"{request.get('symbol')}.{request.get('exchange')}".upper() != symbol:
        _fail("physical_symbol")
    direction = _direction(native.get("direction"))
    if _direction(request.get("direction")) != direction:
        _fail("physical_direction")
    for field in ("price", "volume"):
        if _number(request.get(field), integer=field == "volume") != _number(native.get(field), integer=field == "volume"):
            _fail("physical_economics")
    before = baseline.get("proof", {})
    if baseline.get("proof_sha256") != _sha(before):
        _fail("baseline_proof_digest")
    for field in ("service_generation", "connection_generation"):
        if _text(native.get(field)) != baseline.get(field) or baseline.get(field) != before.get(field):
            _fail("baseline_generation")
    flat = _envelope(before, ("order_before", "positions", "order_after"), fingerprint)
    _same_orders(flat["order_before"], flat["order_after"])
    old_orders = _orders(flat["order_after"])
    native_reqid = _number(native.get("req_order_insert_reqid"), integer=True)
    if type(native_reqid) is not int or native_reqid != _query_watermark(native.get("query_watermark")) + 1 or native_reqid <= before["query_watermark_after"]["reqid"]:
        _fail("native_not_after_baseline")
    inserted = _monotonic(native.get("native_insert_monotonic_ns"))
    if not before["completed_monotonic_ns"] <= inserted <= before["deadline_monotonic_ns"]:
        _fail("native_baseline_time")
    if _watermark(native.get("event_watermark")) != before["event_watermark_after"] or _watermark(native.get("native_api_watermark"), native=True) != before["native_api_watermark_after"]:
        _fail("native_baseline_watermark")
    for row in _positions(flat["positions"], symbol, _date(before["trading_day_before"])):
        if row["Position"] != 0:
            _fail("baseline_not_flat")
    bundle = evidence.get("query_bundle", {})
    queried = _envelope(bundle, ("order_before", "trades", "position_details", "positions", "order_after"), fingerprint)
    if bundle["connection_generation"] == native["connection_generation"]:
        if (bundle["service_generation"] != native["service_generation"] or bundle["started_monotonic_ns"] <= inserted
                or bundle["query_watermark_before"]["reqid"] < native_reqid):
            _fail("postfill_native_sequence")
        native_counts = native["native_api_watermark"]
        post_counts = bundle["native_api_watermark_before"]
        if (post_counts["send_order_api_called_count"] <= native_counts["send_order_api_called_count"]
                or post_counts["cancel_order_api_called_count"] < native_counts["cancel_order_api_called_count"]
                or any(bundle["event_watermark_before"][field] < native["event_watermark"][field] for field in EVENT_FIELDS)):
            _fail("postfill_native_watermark")
    day = _date(bundle.get("trading_day_before"))
    if day != _date(baseline.get("trading_day")) or day != _date(before.get("trading_day_before")):
        _fail("not_opening_trading_day")
    _same_orders(queried["order_before"], queried["order_after"])
    orders = _orders(queried["order_after"])
    matching = [row for row in orders.values() if _symbol(row) == symbol and
                str(row.get("FrontID")) == _text(native.get("front_id")) and
                str(row.get("SessionID")) == _text(native.get("session_id")) and
                row.get("OrderRef") == _text(native.get("order_ref"))]
    if len(matching) != 1:
        _fail("native_order_not_unique")
    order = matching[0]
    if native.get("vt_orderid") != f"CTP.{native['front_id']}_{native['session_id']}_{native['order_ref']}":
        _fail("native_orderid")
    if order["VolumeTotalOriginal"] != request["volume"] or order.get("LimitPrice") != request["price"]:
        _fail("native_order_economics")
    _open(order.get("CombOffsetFlag"))
    if _direction(order.get("Direction")) != direction or order.get("CombHedgeFlag") != "1":
        _fail("order_direction_or_hedge")
    order_key = (order["ExchangeID"], order["OrderSysID"])
    if order_key in old_orders:
        _fail("native_order_present_before_insert")
    for key, other in orders.items():
        if _symbol(other) == symbol and key != order_key and old_orders.get(key) != other:
            _fail("external_target_order")
    fills = evidence.get("canonical_fills")
    if not isinstance(fills, list) or not fills:
        _fail("canonical_fills_missing")
    fill_by_trade = {}
    for fill in fills:
        _record(fill)
        if fill.get("event_type") != "filled_or_part_filled" or fill.get("source") not in OWNED_SOURCES:
            _fail("canonical_fill_unowned")
        _ledger_account(fill, fingerprint)
        if any(fill.get(field) != native.get(field) for field in (*LEASE_FIELDS, "source", "target_date")):
            _fail("canonical_fill_lease")
        for field in ("intent_id", "intent_payload_sha256", "child_order_id"):
            if fill.get(field) not in (None, "") and fill[field] != native.get(field):
                _fail("canonical_native_identity")
        if any(fill.get(name) != value for name, value in owner.items()) or fill.get("vt_orderid") != native["vt_orderid"]:
            _fail("canonical_fill_owner")
        _open(fill.get("offset"))
        if _direction(fill.get("direction")) != direction or fill.get("fill_price_source") != "event_trade_weighted_avg":
            _fail("canonical_fill_economics")
        tradeid = _text(fill.get("tradeid"))
        if tradeid in fill_by_trade or fill.get("trade_fill_key") != f"ctp:{order['ExchangeID']}:{tradeid}":
            _fail("aggregate_or_duplicate_fill")
        if _number(fill.get("volume"), integer=True) != _number(fill.get("trade_volume_delta"), integer=True):
            _fail("aggregate_fill_volume")
        fill_by_trade[tradeid] = fill
    trades = {}
    seen_trades = set()
    old_trade_totals = {}
    for trade in queried["trades"]:
        key = (_text(trade.get("ExchangeID")), _text(trade.get("TradeID")))
        if key in seen_trades or _date(trade.get("TradingDay")) != day:
            _fail("duplicate_trade_or_wrong_day")
        seen_trades.add(key)
        if _symbol(trade) != symbol:
            continue
        syskey = (trade["ExchangeID"], _text(trade.get("OrderSysID")))
        if syskey != order_key:
            if syskey not in old_orders:
                _fail("external_target_trade")
            old_trade_totals[syskey] = old_trade_totals.get(syskey, 0) + _number(trade.get("Volume"), integer=True)
            continue
        tradeid = trade["TradeID"]
        fill = fill_by_trade.get(tradeid)
        if trade.get("OrderRef") not in (None, "") and trade["OrderRef"] != native["order_ref"]:
            _fail("trade_order_ref_conflict")
        _open(trade.get("OffsetFlag"))
        if fill is None or _direction(trade.get("Direction")) != direction or trade.get("HedgeFlag") != "1":
            _fail("trade_fill_identity")
        for field, raw_field in (("price", "Price"), ("volume", "Volume")):
            if _number(trade.get(raw_field), integer=field == "volume") != _number(fill.get(field), integer=field == "volume"):
                _fail("trade_fill_economics")
        try:
            stamp = datetime.fromisoformat(_text(fill.get("broker_trade_at")))
            raw_stamp = datetime.fromisoformat(f"{_date(trade.get('TradeDate'))}T{_text(trade.get('TradeTime'))}")
        except ValueError:
            _fail("trade_timestamp")
        if stamp.tzinfo is None or stamp.astimezone(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None) != raw_stamp:
            _fail("trade_timestamp")
        trades[tradeid] = trade
    if set(trades) != set(fill_by_trade) or sum(row["Volume"] for row in trades.values()) != order["VolumeTraded"]:
        _fail("trade_coverage")
    for key, total in old_trade_totals.items():
        if total != old_orders[key]["VolumeTraded"]:
            _fail("old_order_trade_changed")
    details = {}
    for detail in queried["position_details"]:
        if _date(detail.get("TradingDay")) != day:
            _fail("detail_day")
        if _symbol(detail) != symbol:
            continue
        remaining = _number(detail.get("Volume"), zero=True, integer=True)
        if not remaining:
            continue
        tradeid = _text(detail.get("TradeID"))
        if tradeid in details or tradeid not in trades:
            _fail("detail_identity")
        trade = trades[tradeid]
        if _direction(detail.get("Direction")) != direction or detail.get("HedgeFlag") != "1" or detail.get("TradeType") != "0":
            _fail("detail_kind")
        if any(detail.get(name) not in (None, "") for name in ("InvestUnitID", "CombInstrumentID")) or detail.get("SpecPosiType") not in (None, "", "#"):
            _fail("special_detail")
        if remaining != trade["Volume"] or _number(detail.get("OpenPrice")) != trade["Price"]:
            _fail("detail_economics")
        if not _date(trade.get("TradeDate")) <= _date(detail.get("OpenDate")) <= day:
            _fail("detail_open_date_bounds")
        details[tradeid] = detail
    if set(details) != set(trades):
        _fail("detail_coverage")
    gross = today = 0
    for position in _positions(queried["positions"], symbol, day):
        volume = _number(position.get("Position"), zero=True, integer=True)
        current = _number(position.get("TodayPosition"), zero=True, integer=True)
        if current > volume or position.get("HedgeFlag") != "1" or position.get("PosiDirection") not in {"2", "3"}:
            _fail("position_kind")
        if volume and position["PosiDirection"] != ("2" if direction == "long" else "3"):
            _fail("opposite_position")
        gross += volume
        today += current
    if gross != order["VolumeTraded"] or today != gross:
        _fail("gross_coverage")
    result = []
    for tradeid in sorted(trades):
        trade, detail, fill = trades[tradeid], details[tradeid], fill_by_trade[tradeid]
        identity = _sha({"version": VERSION, "account": fingerprint, "exchange": order["ExchangeID"],
                         "day": day, "tradeid": tradeid, "vt_orderid": native["vt_orderid"], **owner})
        sidecar = {"event_type": EVENT, "version": VERSION, "seal_identity": identity,
                   "broker_callback_key": f"open-date-seal:{identity}", "physical_batch_id": batch,
                   "target_date": _text(fill.get("target_date")), "account_fingerprint": fingerprint, **owner,
                   "direction": direction, "offset": "open", "vt_orderid": native["vt_orderid"], "tradeid": tradeid,
                   "price": fill["price"], "volume": fill["volume"], "broker_trade_at": fill["broker_trade_at"],
                   "broker_trade_date": _date(trade["TradeDate"]), "broker_trading_day": day,
                   "broker_hedge_flag": "1", "broker_open_date": _date(detail["OpenDate"]),
                   "broker_trade_metadata_source": SOURCE, "canonical_fill_record_checksum": fill["record_checksum"],
                   "evidence": evidence}
        sidecar["proof_sha256"] = _sha(sidecar)
        result.append(sidecar)
    return result


def validate_open_date_seal(sidecar: Mapping[str, Any], canonical_fill: Mapping[str, Any], account_fingerprint: str) -> dict[str, Any]:
    try:
        sidecar, canonical_fill = _json(sidecar), _json(canonical_fill)
        _record(canonical_fill)
        if sidecar.get("record_checksum"):
            _record(sidecar)
        body = {name: value for name, value in sidecar.items() if name not in {"record_checksum", "schema_version", "generated_at", "proof_sha256"}}
        if sidecar.get("proof_sha256") != _sha(body):
            _fail("proof_digest")
        candidates = _rebuild(sidecar.get("evidence", {}), account_fingerprint)
        exact = [item for item in candidates if item["canonical_fill_record_checksum"] == canonical_fill["record_checksum"]]
        if len(exact) != 1 or any(sidecar.get(name) != value for name, value in exact[0].items()):
            _fail("seal_replay_mismatch")
        fields = ("seal_identity", "proof_sha256", "account_fingerprint", "vt_symbol", "tradeid", "vt_orderid",
                  "intent_fingerprint", "root_position_id", "position_epoch_id", "broker_open_date", "broker_trade_date",
                  "broker_trading_day", "broker_hedge_flag", "broker_trade_metadata_source")
        return {name: exact[0][name] for name in fields}
    except (KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError("broker_open_date_seal:malformed_evidence") from exc


def build_open_date_seals(*, execution_ledger_rows: Sequence[Mapping[str, Any]], native_order_event: Mapping[str, Any],
                          flat_baseline_event: Mapping[str, Any], query_bundle: Mapping[str, Any],
                          account_fingerprint: str) -> list[dict[str, Any]]:
    try:
        rows, native, baseline, bundle = _json([execution_ledger_rows, native_order_event, flat_baseline_event, query_bundle])
        if native not in rows:
            _fail("native_not_in_ledger")
        symbol = _text(native.get("vt_symbol")).upper()
        for row in rows:
            _record(row)
            if row.get("event_type") in {"broker_position_open_date_seal_conflict", "broker_trade_ownership_metadata_conflict", "broker_trade_callback_unbound", "broker_trade_callback_unidentified"}:
                conflict_symbol = row.get("vt_symbol")
                if not isinstance(conflict_symbol, str) or not conflict_symbol.strip() or conflict_symbol.strip().upper() == symbol:
                    _fail("unbound_or_metadata_conflict")
        rows = _unique_records(rows)
        natives = [row for row in rows if row.get("event_type") == "native_order_identity_persisted_before_insert"
                   and row.get("physical_batch_id") == native.get("physical_batch_id")]
        fills = [row for row in rows if row.get("event_type") == "filled_or_part_filled" and row.get("vt_orderid") == native.get("vt_orderid")]
        history = collect_open_date_reservation_history(rows, native)
        linked = [row for row in history if isinstance(row.get("intent_payload"), dict)]
        evidence = {"native_order_events": natives, "flat_baseline_event": baseline, "canonical_fills": fills,
                    "linked_intent_events": linked, "reservation_history": history, "query_bundle": bundle}
        seals = _rebuild(evidence, account_fingerprint)
        result = []
        for seal in seals:
            existing = [row for row in rows if row.get("event_type") == EVENT and row.get("seal_identity") == seal["seal_identity"]]
            if len(existing) > 1:
                _fail("duplicate_seal_identity")
            if existing:
                fill = next(row for row in fills if row["record_checksum"] == seal["canonical_fill_record_checksum"])
                validate_open_date_seal(existing[0], fill, account_fingerprint)
                if any(item not in rows for field in ("native_order_events", "linked_intent_events", "canonical_fills", "reservation_history")
                       for item in existing[0]["evidence"][field]):
                    _fail("seal_evidence_not_in_ledger")
                if any(existing[0].get(name) != value for name, value in seal.items() if name not in {"evidence", "proof_sha256"}):
                    _fail("existing_seal_conflict")
                result.append(existing[0])
            else:
                result.append(seal)
        return result
    except (KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError("broker_open_date_seal:malformed_evidence") from exc
