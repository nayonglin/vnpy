"""Bind raw CTP remaining lots to durable owned fills, without I/O or date inference.

CTP defines OpenDate, TradeDate and TradingDay separately. The vnpy gateway
constructs TradeData.datetime from TradeDate/TradeTime, not TradingDay. Historical
fills therefore require a persisted raw broker_trading_day; differing OpenDate
also requires a persisted broker_open_date from broker position-detail evidence.
Neither target_date nor a calendar heuristic supplies these missing fields.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
import hashlib
import json
import math
import re
from typing import Any
from zoneinfo import ZoneInfo


PROOF_VERSION = "ctp_position_detail_owned_lots_v1"
OWNED_SOURCES = frozenset({"stage901_pending_order", "stage904_c9_intraday_close", "stage904_c9_intraday_retry_open"})
SIDECAR_FIELDS = ("account_fingerprint", "broker_trade_date", "broker_trading_day", "broker_hedge_flag", "broker_trade_metadata_source")


def _fail(reason: str) -> None:
    raise ValueError(f"broker_position_ownership:{reason}")


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{field}_missing")
    return value.strip()


def _date(value: Any, field: str) -> str:
    text = _text(value, field)
    if re.fullmatch(r"\d{8}", text):
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        _fail(f"{field}_invalid")
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        _fail(f"{field}_invalid")


def _number(value: Any, field: str, *, lots: bool = False, zero: bool = False) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{field}_invalid")
    number = float(value)
    if not math.isfinite(number) or number >= 1e100 or number < 0 or (not zero and number == 0):
        _fail(f"{field}_invalid")
    if lots and (not number.is_integer() or number > 2_147_483_647):
        _fail(f"{field}_outside_ctp_integer_range")
    return int(number) if lots else number


def _direction(value: Any) -> str:
    text = _text(value, "direction").lower()
    if text in {"long", "多", "direction.long"}:
        return "long"
    if text in {"short", "空", "direction.short"}:
        return "short"
    _fail("direction_invalid")


def _offset(value: Any) -> str:
    text = _text(value, "offset").lower()
    if text in {"open", "开", "offset.open"}:
        return "open"
    if text in {"close", "closetoday", "closeyesterday", "平", "平今", "平昨", "offset.close", "offset.closetoday", "offset.closeyesterday"}:
        return "close"
    _fail("offset_invalid")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _account_values(event: Mapping[str, Any]) -> list[str]:
    values = []
    if event.get("account_fingerprint") is not None:
        values.append(_text(event["account_fingerprint"], "account_fingerprint"))
    for name in ("broker_sizing", "broker_close_sizing"):
        audit = event.get(name)
        if isinstance(audit, Mapping) and "account_fingerprint" in audit:
            values.append(_text(audit["account_fingerprint"], "account_fingerprint"))
    inputs = event.get("broker_sizing_inputs")
    if isinstance(inputs, Mapping) and isinstance(inputs.get("account"), Mapping):
        values.append(_text(inputs["account"].get("account_fingerprint"), "account_fingerprint"))
    return values


def _owner(event: Mapping[str, Any], field: str) -> str:
    audit = event.get("broker_close_sizing") or {}
    if not isinstance(audit, Mapping):
        _fail("close_audit_invalid")
    values = [_text(source[field], field) for source in (event, audit) if source.get(field) not in (None, "")]
    if not values or len(set(values)) != 1:
        _fail(f"{field}_missing_or_conflicting")
    return values[0]


def _sidecar_timestamp(event: Mapping[str, Any]) -> str:
    try:
        timestamp = datetime.fromisoformat(_text(event.get("broker_trade_at"), "sidecar_broker_trade_at"))
    except ValueError:
        _fail("sidecar_broker_trade_at_invalid")
    if timestamp.tzinfo is None:
        _fail("sidecar_broker_trade_at_timezone_missing")
    return timestamp.astimezone(ZoneInfo("Asia/Shanghai")).isoformat()


def _sidecar_signature(event: Mapping[str, Any]) -> tuple[Any, ...]:
    volume = _number(event.get("volume"), "sidecar_volume", lots=True)
    if event.get("trade_volume_delta") is not None and _number(event["trade_volume_delta"], "sidecar_trade_volume_delta", lots=True) != volume:
        _fail("sidecar_trade_volume_conflict")
    return (
        _text(event.get("vt_symbol"), "sidecar_symbol").upper(),
        _text(event.get("tradeid"), "sidecar_tradeid"),
        _sidecar_timestamp(event),
        _text(event.get("vt_orderid"), "sidecar_orderid"),
        _direction(event.get("direction")), _offset(event.get("offset")),
        volume, _number(event.get("price"), "sidecar_price"),
        _owner(event, "root_position_id"), _owner(event, "position_epoch_id"),
        _text(event.get("intent_fingerprint"), "sidecar_intent_fingerprint"),
    )


def _sidecar_value(name: str, value: Any) -> str:
    return _date(value, name) if name in {"broker_trade_date", "broker_trading_day"} else _text(value, name)


def _ownership_sidecars(rows: Sequence[Mapping[str, Any]], symbol: str, fingerprint: str) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    indexed: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for index, row in enumerate(rows):
        if row.get("event_type") != "broker_trade_ownership_metadata":
            continue
        if _text(row.get("vt_symbol"), "sidecar_symbol").upper() != symbol:
            continue
        signature = _sidecar_signature(row)
        metadata = {name: _sidecar_value(name, row.get(name)) for name in SIDECAR_FIELDS}
        if metadata["account_fingerprint"] != fingerprint:
            _fail("sidecar_account_fingerprint_mismatch")
        if metadata["broker_trade_date"] != signature[2][:10]:
            _fail("sidecar_trade_date_conflict")
        if metadata["broker_hedge_flag"] != "1" or metadata["broker_trade_metadata_source"] != "ctp_on_rtn_trade":
            _fail("sidecar_native_metadata_unverified")
        tradeid = signature[1]
        exchange = symbol.rpartition(".")[2]
        if row.get("vt_tradeid") not in (None, "", f"CTP.{tradeid}") or row.get("trade_fill_key") not in (None, "", f"ctp:{exchange}:{tradeid}"):
            _fail("sidecar_trade_identity_conflict")
        key = (symbol, tradeid, signature[2][:10])
        indexed.setdefault(key, []).append({"index": index, "signature": signature, "metadata": metadata})
    return indexed


def _ledger_fills(rows: Sequence[Mapping[str, Any]], symbol: str, fingerprint: str, trading_day: str) -> list[dict[str, Any]]:
    payloads: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            _fail("ledger_row_invalid")
        if row.get("event_type") == "broker_trade_ownership_metadata_conflict":
            conflict_symbol = row.get("vt_symbol")
            if not isinstance(conflict_symbol, str) or not conflict_symbol.strip() or conflict_symbol.strip().upper() == symbol:
                _fail("broker_trade_ownership_metadata_conflict")
        key = row.get("intent_fingerprint")
        payload = row.get("intent_payload")
        if key and isinstance(payload, Mapping):
            if key in payloads and payloads[key] != payload:
                _fail("linked_payload_conflict")
            payloads[key] = payload
    sidecars = _ownership_sidecars(rows, symbol, fingerprint)
    matched_sidecars: set[int] = set()
    fills: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        if row.get("event_type") not in {"filled_or_part_filled", "broker_trade_callback_unbound", "broker_trade_callback_unidentified"}:
            continue
        payload = row.get("intent_payload") or payloads.get(row.get("intent_fingerprint"), {})
        if not isinstance(payload, Mapping):
            _fail("linked_payload_invalid")
        event = {**payload, **{name: value for name, value in row.items() if value not in (None, "")}}
        event_symbol = _text(event.get("vt_symbol"), "ledger_trade_symbol").upper()
        if event_symbol != symbol:
            continue
        if event["event_type"] != "filled_or_part_filled" or event.get("source") not in OWNED_SOURCES:
            _fail("unbound_or_unowned_trade")
        for name in ("root_position_id", "position_epoch_id", "vt_symbol", "direction", "offset"):
            if row.get(name) not in (None, "") and payload.get(name) not in (None, "") and row[name] != payload[name]:
                _fail(f"linked_{name}_conflict")
        if sidecars:
            key = (symbol, _text(event.get("tradeid"), "tradeid"), _sidecar_timestamp(event)[:10])
            for sidecar in sidecars.get(key, []):
                signature = _sidecar_signature(event)
                if sidecar["signature"] != signature:
                    _fail("sidecar_fill_identity_or_economics_conflict")
                for name, value in sidecar["metadata"].items():
                    if event.get(name) not in (None, "") and _sidecar_value(name, event[name]) != value:
                        _fail(f"sidecar_existing_{name}_conflict")
                    event[name] = value
                matched_sidecars.add(sidecar["index"])
        account_values = _account_values(event) + _account_values(payload)
        if not account_values or any(value != fingerprint for value in account_values):
            _fail("ledger_account_fingerprint_missing_or_mismatch")
        if event.get("fill_price_source") != "event_trade_weighted_avg":
            _fail("durable_priced_fill_required")
        tradeid = _text(event.get("tradeid"), "tradeid")
        exchange = symbol.rpartition(".")[2]
        if event.get("vt_tradeid") not in (None, "", f"CTP.{tradeid}"):
            _fail("trade_identity_conflict")
        if event.get("trade_fill_key") not in (None, "", f"ctp:{exchange}:{tradeid}"):
            _fail("aggregate_or_conflicting_trade_identity")
        if event.get("exchange") not in (None, "", exchange):
            _fail("ledger_exchange_conflict")
        try:
            timestamp = datetime.fromisoformat(_text(event.get("broker_trade_at"), "broker_trade_at"))
        except ValueError:
            _fail("broker_trade_at_invalid")
        if timestamp.tzinfo is None:
            _fail("broker_trade_at_timezone_missing")
        trade_date = timestamp.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
        if "broker_trade_date" in event and _date(event["broker_trade_date"], "broker_trade_date") != trade_date:
            _fail("broker_trade_date_conflict")
        if "broker_hedge_flag" in event and event["broker_hedge_flag"] != "1":
            _fail("broker_hedge_flag_uncovered")
        if "broker_trade_metadata_source" in event and event["broker_trade_metadata_source"] != "ctp_on_rtn_trade":
            _fail("broker_trade_metadata_source_unverified")
        raw_day = event.get("broker_trading_day")
        broker_day = _date(raw_day, "broker_trading_day") if raw_day not in (None, "") else None
        if broker_day is None and trade_date != trading_day:
            _fail("historical_broker_trading_day_missing")
        if trade_date > trading_day or (broker_day and (broker_day > trading_day or broker_day < trade_date)):
            _fail("broker_trading_day_out_of_bounds")
        raw_open_date = event.get("broker_open_date")
        open_date = _date(raw_open_date, "broker_open_date") if raw_open_date not in (None, "") else trade_date
        if open_date > trading_day or (broker_day is None and open_date != trade_date):
            _fail("broker_open_date_unproven")
        fill = {
            "tradeid": tradeid, "exchange": exchange, "trade_date": trade_date,
            "broker_trading_day": broker_day, "open_date": open_date,
            "root_position_id": _owner(event, "root_position_id"),
            "position_epoch_id": _owner(event, "position_epoch_id"),
            "vt_orderid": _text(event.get("vt_orderid"), "vt_orderid"),
            "direction": _direction(event.get("direction")), "offset": _offset(event.get("offset")),
            "volume": _number(event.get("trade_volume_delta", event.get("volume")), "fill_volume", lots=True),
            "price": _number(event.get("price"), "fill_price"),
        }
        if event.get("volume") is not None and _number(event["volume"], "fill_volume", lots=True) != fill["volume"]:
            _fail("fill_volume_conflict")
        identity = (exchange, broker_day or trade_date, tradeid)
        if identity in fills and fills[identity] != fill:
            _fail("durable_fill_conflict")
        fills[identity] = fill
    if matched_sidecars != {sidecar["index"] for candidates in sidecars.values() for sidecar in candidates}:
        _fail("sidecar_without_matching_canonical_fill")
    return list(fills.values())


def validate_position_detail_ownership(
    *, execution_ledger_rows: Sequence[Mapping[str, Any]], position_detail_rows: Sequence[Mapping[str, Any]],
    vt_symbol: str, position_direction: str, broker_gross_volume: int,
    account_fingerprint: str, trading_day: str,
) -> dict[str, Any]:
    """Return a JSON proof or raise ValueError; never authenticate caller-made data.

    Caller owns durable ledger integrity and raw detail reqid/completeness,
    account-query scope, freshness, connection generation and final send gates.
    broker_trading_day must come from the original raw CTP fill TradingDay.
    broker_open_date, when needed, must be durable broker detail evidence for
    that exact opening TradeID, not target_date or a next-business-day guess.
    Old fills without broker_trading_day are usable only on the same natural
    day as the supplied trading_day, with an exactly matching detail OpenDate.
    Today/yesterday lots use the opening fill's broker_trading_day, independently
    of the exact OpenDate used to identify its remaining position detail.
    This function verifies lot ownership, not authorization or executable size.
    Native metadata may reside in broker_trade_ownership_metadata sidecars.
    Sidecars must exactly bind the canonical fill's order, trade time, economic
    fields and existing intent/root/epoch. Only the five raw metadata fields
    are enriched in a local copy; conflicts and orphan sidecars fail closed.
    """
    try:
        if isinstance(execution_ledger_rows, (str, bytes)) or not isinstance(execution_ledger_rows, Sequence):
            _fail("ledger_rows_missing")
        if isinstance(position_detail_rows, (str, bytes)) or not isinstance(position_detail_rows, Sequence):
            _fail("detail_rows_missing")
        ledger_digest = _digest(execution_ledger_rows)
        detail_digest = _digest(position_detail_rows)
        symbol = _text(vt_symbol, "vt_symbol").upper()
        if not re.fullmatch(r"[A-Z]+[0-9]{3,4}\.(CZCE|CFFEX|SHFE|INE|DCE|GFEX)", symbol):
            _fail("futures_symbol_required")
        direction = _direction(position_direction)
        gross = _number(broker_gross_volume, "broker_gross_volume", lots=True)
        fingerprint = _text(account_fingerprint, "account_fingerprint")
        if not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
            _fail("account_fingerprint_invalid")
        day = _date(trading_day, "trading_day")
        fills = _ledger_fills(execution_ledger_rows, symbol, fingerprint, day)
        net: dict[tuple[str, str], int] = {}
        for fill in fills:
            relevant_open = fill["offset"] == "open" and fill["direction"] == direction
            relevant_close = fill["offset"] == "close" and fill["direction"] != direction
            if relevant_open or relevant_close:
                owner = (fill["root_position_id"], fill["position_epoch_id"])
                net[owner] = net.get(owner, 0) + (fill["volume"] if relevant_open else -fill["volume"])
        if any(volume < 0 for volume in net.values()):
            _fail("negative_owned_epoch_net")
        active = [(owner, volume) for owner, volume in net.items() if volume > 0]
        if len(active) != 1:
            _fail("active_owned_epoch_missing_or_ambiguous")
        owner, net_volume = active[0]
        if net_volume != gross:
            _fail("owned_net_volume_mismatch")
        bindings = []
        identities: set[tuple[str, str, str, str]] = set()
        total = today = yesterday = 0
        for row in position_detail_rows:
            if not isinstance(row, Mapping):
                _fail("detail_row_invalid")
            broker = _text(row.get("BrokerID"), "BrokerID")
            investor = _text(row.get("InvestorID"), "InvestorID")
            if hashlib.sha256(f"{broker}\0{investor}".encode()).hexdigest() != fingerprint:
                _fail("detail_account_fingerprint_mismatch")
            if _date(row.get("TradingDay"), "detail_TradingDay") != day:
                _fail("detail_trading_day_mismatch")
            exchange = _text(row.get("ExchangeID"), "ExchangeID").upper()
            instrument = _text(row.get("InstrumentID"), "InstrumentID").upper()
            raw_direction = _text(row.get("Direction"), "detail_Direction")
            if raw_direction not in {"0", "1"}:
                _fail("detail_direction_invalid")
            detail_direction = "long" if raw_direction == "0" else "short"
            if f"{instrument}.{exchange}" != symbol or detail_direction != direction:
                continue
            if row.get("HedgeFlag") != "1" or row.get("TradeType", "0") != "0":
                _fail("non_speculative_or_nonstandard_trade")
            if row.get("CombInstrumentID") or row.get("InvestUnitID") or row.get("SpecPosiType", "#") not in ("", "#"):
                _fail("special_position_detail_uncovered")
            remaining = _number(row.get("Volume"), "detail_Volume", lots=True, zero=True)
            open_price = _number(row.get("OpenPrice"), "detail_OpenPrice")
            open_date = _date(row.get("OpenDate"), "detail_OpenDate")
            if open_date > day:
                _fail("detail_open_date_future")
            tradeid = _text(row.get("TradeID"), "detail_TradeID")
            identity = (exchange, open_date, tradeid, detail_direction)
            if identity in identities:
                _fail("duplicate_position_detail")
            identities.add(identity)
            if remaining == 0:
                continue
            candidates = [fill for fill in fills if fill["offset"] == "open" and fill["direction"] == direction
                          and fill["tradeid"] == tradeid and fill["exchange"] == exchange and fill["open_date"] == open_date]
            if len(candidates) != 1:
                _fail("unmatched_or_ambiguous_open_date_fill")
            opening = candidates[0]
            if (opening["root_position_id"], opening["position_epoch_id"]) != owner:
                _fail("detail_belongs_to_old_or_other_epoch")
            if opening["price"] != open_price or remaining > opening["volume"]:
                _fail("detail_open_price_or_volume_mismatch")
            bindings.append({
                "exchange": exchange, "tradeid": tradeid, "open_date": open_date,
                "broker_trading_day": opening["broker_trading_day"],
                "vt_orderid": opening["vt_orderid"], "open_price": open_price,
                "ledger_open_volume": opening["volume"], "remaining_volume": remaining,
            })
            total += remaining
            if (opening["broker_trading_day"] or opening["trade_date"]) == day:
                today += remaining
            else:
                yesterday += remaining
        if total != gross:
            _fail("detail_volume_sum_mismatch")
        proof = {
            "version": PROOF_VERSION, "confirmed": True, "account_fingerprint": fingerprint,
            "vt_symbol": vt_symbol, "position_direction": direction, "trading_day": day,
            "root_position_id": owner[0], "position_epoch_id": owner[1], "owned_net_volume": net_volume,
            "broker_gross_volume": gross, "detail_volume": total, "today_volume": today, "yesterday_volume": yesterday,
            "detail_count": len(bindings), "open_trade_bindings": sorted(bindings, key=lambda item: (item["exchange"], item["open_date"], item["tradeid"])),
            "execution_ledger_sha256": ledger_digest, "position_detail_sha256": detail_digest,
        }
        proof["proof_sha256"] = _digest(proof)
        return proof
    except (TypeError, KeyError, OverflowError, AttributeError) as exc:
        raise ValueError(f"broker_position_ownership:invalid_evidence:{type(exc).__name__}") from None
