"""Translate proven whole-shadow closes into broker gross lots without I/O."""

from __future__ import annotations

import math
import re
from typing import Any, Mapping, Sequence

import pandas as pd


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _direction(value: Any) -> str:
    text = _text(value).lower()
    if text in {"long", "多", "direction.long"}:
        return "long"
    if text in {"short", "空", "direction.short"}:
        return "short"
    raise ValueError("broker_full_close_direction_invalid")


def _is_close(value: Any) -> bool:
    return _text(value).lower() in {"close", "平", "offset.close"}


def _lots(value: Any, *, signed: bool = False) -> int:
    if isinstance(value, bool):
        raise ValueError("broker_full_close_lots_invalid")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("broker_full_close_lots_invalid") from None
    if not math.isfinite(number) or not number.is_integer() or (not signed and number < 0):
        raise ValueError("broker_full_close_lots_invalid")
    return int(number)


def _pending_identity(row: Mapping[str, Any]) -> tuple:
    return (
        _text(row.get("vt_symbol")).upper(), _direction(row.get("direction")), _is_close(row.get("offset")),
        _lots(row.get("volume")), _lots(row.get("traded", 0)),
        _text(row.get("cohort_id")), _text(row.get("target_date")),
        _text(row.get("vt_orderid") or row.get("orderid")),
    )


def _trade_symbol(row: Mapping[str, Any]) -> str:
    symbol = _text(row.get("vt_symbol"))
    if not symbol and row.get("symbol") and row.get("exchange"):
        symbol = f"{_text(row['symbol'])}.{_text(row['exchange'])}"
    return symbol.upper()


def _trade_evidence(row: Mapping[str, Any], symbol: str, *, ledger: bool) -> tuple[tuple, tuple]:
    tradeid = _text(row.get("tradeid") or row.get("trade_id"))
    vt_tradeid = _text(row.get("vt_tradeid"))
    if vt_tradeid.startswith("CTP."):
        derived = vt_tradeid.split(".")[-1]
        if tradeid and tradeid != derived:
            raise ValueError("broker_full_close_owned_trade_identity_conflict")
        tradeid = tradeid or derived
    fill_key = _text(row.get("trade_fill_key"))
    exchange = symbol.rpartition(".")[2]
    if fill_key.startswith("ctp:"):
        parts = fill_key.split(":")
        if len(parts) != 3 or parts[1].upper() != exchange or (tradeid and parts[2] != tradeid):
            raise ValueError("broker_full_close_owned_trade_identity_conflict")
        tradeid = tradeid or parts[2]
    if not tradeid or not exchange:
        raise ValueError("broker_full_close_owned_trade_identity_missing")
    if row.get("exchange") and _text(row["exchange"]).upper() != exchange:
        raise ValueError("broker_full_close_owned_trade_exchange_conflict")
    timestamp = _text(row.get("broker_trade_at") or row.get("datetime"))
    trade_date = ""
    if timestamp:
        try:
            parsed = pd.Timestamp(timestamp)
            if pd.isna(parsed):
                raise ValueError
            trade_date = parsed.date().isoformat()
        except (ValueError, TypeError):
            raise ValueError("broker_full_close_owned_trade_time_invalid") from None
    direction = _direction(row.get("direction"))
    offset = _text(row.get("offset")).lower()
    opening = offset in {"open", "开", "offset.open"}
    closing = _is_close(offset) or offset in {
        "closetoday", "closeyesterday", "平今", "平昨", "offset.closetoday", "offset.closeyesterday",
    }
    if not opening and not closing:
        raise ValueError("broker_full_close_owned_trade_offset_invalid")
    volume = _lots(row.get("trade_volume_delta", row.get("volume")) if ledger else row.get("volume"))
    price = float(row.get("price", 0))
    if volume <= 0 or not math.isfinite(price) or price <= 0:
        raise ValueError("broker_full_close_owned_fill_invalid")
    return (exchange, tradeid, trade_date), (direction, opening, volume, price)


def validate_owned_full_close(
    *, execution_ledger_rows: Sequence[Mapping[str, Any]] | None, vt_symbol: str,
    position_direction: str, broker_gross_volume: int,
    broker_trade_rows: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Validate unique owned net lots AND coverage of a completed broker trade query.

    Callers must validate account, query completeness, generation and freshness
    before passing rows. None is missing evidence; [] is a proven empty query.
    Query coverage applies to the queried trading day, not unqueried history.
    Ambiguous/unbound same-symbol callbacks and aggregate-only fills fail closed.
    """
    try:
        return _owned_epoch(execution_ledger_rows, symbol=_text(vt_symbol).upper(),
                            direction=_direction(position_direction), gross=_lots(broker_gross_volume),
                            broker_trade_rows=broker_trade_rows)
    except (KeyError, TypeError, AttributeError, OverflowError):
        raise ValueError("broker_full_close_owned_metadata_invalid") from None


def _owned_epoch(
    rows: Sequence[Mapping[str, Any]] | None, *, symbol: str, direction: str, gross: int,
    broker_trade_rows: Sequence[Mapping[str, Any]] | None,
    require_broker_trade_coverage: bool = True,
) -> dict[str, Any]:
    if not rows:
        raise ValueError("broker_full_close_owned_ledger_required")
    if broker_trade_rows is None and require_broker_trade_coverage:
        raise ValueError("broker_full_close_owned_trade_query_required")
    if gross <= 0 or not symbol or "." not in symbol:
        raise ValueError("broker_full_close_owned_position_invalid")
    payloads = {str(row.get("intent_fingerprint")): row["intent_payload"] for row in rows
                if row.get("intent_fingerprint") and isinstance(row.get("intent_payload"), Mapping)}
    net: dict[tuple[str, str], int] = {}
    seen: dict[tuple, tuple] = {}
    fills: dict[tuple, tuple] = {}
    for row in rows:
        event_type = _text(row.get("event_type"))
        if event_type not in {"filled_or_part_filled", "broker_trade_callback_unbound", "broker_trade_callback_unidentified"}:
            continue
        payload = payloads.get(str(row.get("intent_fingerprint")), {})
        payload = row.get("intent_payload") if isinstance(row.get("intent_payload"), Mapping) else payload
        event = {**payload, **{key: value for key, value in row.items() if value is not None and _text(value)}}
        event_symbol = _trade_symbol(event)
        if not event_symbol:
            raise ValueError("broker_full_close_owned_trade_symbol_missing")
        if event_symbol != symbol:
            continue
        if event_type != "filled_or_part_filled":
            raise ValueError("broker_full_close_owned_trade_unbound")
        close_audit = event.get("broker_close_sizing") or {}
        root = _text(event.get("root_position_id") or close_audit.get("root_position_id"))
        epoch = _text(event.get("position_epoch_id") or close_audit.get("position_epoch_id"))
        owned = event.get("source") in {"stage901_pending_order", "stage904_c9_intraday_close", "stage904_c9_intraday_retry_open"}
        if not owned:
            raise ValueError("broker_full_close_owned_trade_unbound")
        if not root or not epoch or event.get("fill_price_source") != "event_trade_weighted_avg":
            raise ValueError("broker_full_close_owned_fill_unverified")
        identity, economics = _trade_evidence(event, symbol, ledger=True)
        event_direction, opening, volume, price = economics
        value = (root, epoch, economics)
        if identity in seen:
            if seen[identity] != value:
                raise ValueError("broker_full_close_owned_fill_conflict")
            continue
        seen[identity] = value
        fills[identity] = economics
        if not ((opening and event_direction == direction) or (not opening and event_direction != direction)):
            continue
        key = (root, epoch)
        net[key] = net.get(key, 0) + (volume if opening else -volume)
    covered: set[tuple] = set()
    for trade in broker_trade_rows if require_broker_trade_coverage else []:
        trade_symbol = _trade_symbol(trade)
        if not trade_symbol:
            raise ValueError("broker_full_close_owned_trade_symbol_missing")
        if trade_symbol != symbol:
            continue
        identity, economics = _trade_evidence(trade, symbol, ledger=False)
        if fills.get(identity) != economics:
            raise ValueError("broker_full_close_owned_trade_coverage_incomplete")
        covered.add(identity)
    if any(volume < 0 for volume in net.values()):
        raise ValueError("broker_full_close_owned_negative_epoch")
    active = [(key, volume) for key, volume in net.items() if volume > 0]
    if len(active) != 1 or active[0][1] != gross:
        raise ValueError("broker_full_close_owned_net_volume_mismatch")
    (root, epoch), volume = active[0]
    return {"root_position_id": root, "position_epoch_id": epoch, "owned_net_volume": volume,
            "broker_trade_coverage_count": len(covered),
            "broker_trade_coverage_verified": require_broker_trade_coverage,
            "final_broker_trade_coverage_required": True}


def size_full_close_intent(
    *, intent: Mapping[str, Any], pending_orders: pd.DataFrame, current_positions: pd.DataFrame,
    official_summary: Mapping[str, Any], broker_positions: pd.DataFrame,
    execution_ledger_rows: Sequence[Mapping[str, Any]] | None = None,
    broker_trade_rows: Sequence[Mapping[str, Any]] | None = None,
    require_broker_trade_coverage: bool = True,
) -> dict[str, Any]:
    """Use data materialized from ONE validated pending artifact cohort.

    The caller owns byte/hash validation through the existing pending-artifact
    loader and broker snapshot validator. This pure function checks semantic
    agreement; it cannot authenticate arbitrary caller-constructed DataFrames.
    Partial orders, traded pending orders and adjusted shadow epochs are not
    supported. Resizing requires a unique owned root/epoch with net fills equal
    to gross broker lots. Draft callers may explicitly defer broker trade query
    coverage; the returned audit then requires the strict final owned validator.
    Zero lots means already flat, never an order to submit.
    """
    try:
        if not isinstance(require_broker_trade_coverage, bool):
            raise ValueError("broker_full_close_coverage_mode_invalid")
        symbol = _text(intent.get("vt_symbol"))
        direction = _direction(intent.get("direction"))
        position_direction = "long" if direction == "short" else "short"
        if not symbol or not _is_close(intent.get("offset")):
            raise ValueError("broker_full_close_intent_invalid")
        cohort = _text(official_summary.get("cohort_id"))
        target_date = _text(official_summary.get("analysis_end"))
        if not re.fullmatch(r"[0-9a-f]{64}", cohort) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", target_date):
            raise ValueError("broker_full_close_cohort_missing")
        pending_rows = pending_orders.to_dict(orient="records")
        if any(_text(row.get("cohort_id")) != cohort or _text(row.get("target_date")) != target_date for row in pending_rows):
            raise ValueError("broker_full_close_cohort_mismatch")
        matches = [row for row in pending_rows if _text(row.get("vt_symbol")).upper() == symbol.upper()
                   and _is_close(row.get("offset")) and _direction(row.get("direction")) == direction]
        if len(matches) != 1:
            raise ValueError("broker_full_close_pending_missing_or_ambiguous")
        pending = matches[0]
        summary_pending = official_summary.get("pending_orders")
        if not isinstance(summary_pending, list) or sum(_pending_identity(row) == _pending_identity(pending) for row in summary_pending) != 1:
            raise ValueError("broker_full_close_summary_pending_mismatch")
        shadow_volume = _lots(pending.get("volume"))
        if _lots(pending.get("traded", 0)) != 0 or shadow_volume <= 0:
            raise ValueError("broker_full_close_pending_not_unfilled")
        if "planned_volume" in intent and _lots(intent["planned_volume"]) != shadow_volume:
            raise ValueError("broker_full_close_intent_volume_mismatch")
        alignment = official_summary.get("live_stop_alignment") or {}
        if symbol.upper() in {_text(item).upper() for item in alignment.get("quarantined_symbols", [])}:
            raise ValueError("broker_full_close_shadow_epoch_quarantined")
        for adjustment in alignment.get("position_adjustments", []):
            if (_text(adjustment.get("vt_symbol")).upper() == symbol.upper()
                    and _direction(adjustment.get("direction")) == position_direction):
                raise ValueError("broker_full_close_shadow_epoch_adjusted_or_quarantined")
        positions = [row for row in current_positions.to_dict(orient="records")
                     if _text(row.get("vt_symbol")).upper() == symbol.upper()
                     and _direction(row.get("direction")) == position_direction]
        if len(positions) != 1:
            raise ValueError("broker_full_close_shadow_position_missing_or_ambiguous")
        position = positions[0]
        signed_volume = _lots(position.get("end_pos"), signed=True)
        if (_text(position.get("date"))[:10] != target_date or signed_volume == 0
                or (signed_volume > 0) != (position_direction == "long")):
            raise ValueError("broker_full_close_shadow_position_invalid")
        delta = position.get("live_stop_alignment_delta_volume", 0)
        if pd.notna(delta) and _lots(delta, signed=True) != 0:
            raise ValueError("broker_full_close_shadow_position_adjusted")
        if shadow_volume != abs(signed_volume):
            raise ValueError("broker_full_close_partial_or_oversized_not_supported")
        gross = 0
        for row in broker_positions.to_dict(orient="records"):
            broker_symbol = _text(row.get("vt_symbol")) or f"{_text(row.get('symbol'))}.{_text(row.get('exchange'))}"
            if broker_symbol.upper() != symbol.upper():
                continue
            if _direction(row.get("direction")) != position_direction:
                continue
            volume = _lots(row.get("volume"))
            if _lots(row.get("frozen")) != 0:
                raise ValueError("broker_full_close_frozen_position")
            gross += volume
        ownership = _owned_epoch(
            execution_ledger_rows, symbol=symbol.upper(), direction=position_direction,
            gross=gross, broker_trade_rows=broker_trade_rows,
            require_broker_trade_coverage=require_broker_trade_coverage,
        ) if gross and gross != shadow_volume else {}
        return {
            "mode": "full_close", "volume": gross, "broker_gross_volume": gross,
            "shadow_volume": shadow_volume, "shadow_position_volume": abs(signed_volume),
            "cohort_id": cohort, "target_date": target_date, "vt_symbol": symbol,
            "position_direction": position_direction,
            **ownership,
        }
    except (KeyError, TypeError, AttributeError):
        raise ValueError("broker_full_close_metadata_invalid") from None
