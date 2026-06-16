from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from vnpy.trader.constant import Direction, Exchange, Offset, OrderType
from vnpy.trader.object import OrderRequest


PHASE_D_SUBMIT_CONFIRM_TEXT = "I_UNDERSTAND_THIS_ENABLES_FULL_AUTO_CTP_LIVE_TRADING"


@dataclass(frozen=True)
class PhaseDSubmitGate:
    mode: str
    phase_d_ready: bool
    executor_ready: bool
    reconciliation_aligned: bool
    kill_switch_active: bool
    real_adapter_enabled: bool
    real_submit_enabled: bool
    confirm_text: str
    allow_real_broker_side_effects: bool
    max_order_count_per_cycle: int = 3


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number


def _direction(value: Any) -> Direction | None:
    text = _clean(value).lower()
    if text in {"long", "多", "direction.long"}:
        return Direction.LONG
    if text in {"short", "空", "direction.short"}:
        return Direction.SHORT
    return None


def _offset(value: Any) -> Offset | None:
    text = _clean(value).lower()
    if text in {"open", "开", "offset.open"}:
        return Offset.OPEN
    if text in {"close", "平", "offset.close"}:
        return Offset.CLOSE
    if text in {"closetoday", "平今", "offset.closetoday"}:
        return Offset.CLOSETODAY
    if text in {"closeyesterday", "平昨", "offset.closeyesterday"}:
        return Offset.CLOSEYESTERDAY
    return None


def _order_type(value: Any) -> OrderType | None:
    text = _clean(value).lower()
    if text in {"", "limit", "限价", "ordertype.limit"}:
        return OrderType.LIMIT
    if text in {"market", "市价", "ordertype.market"}:
        return OrderType.MARKET
    return None


def _split_vt_symbol(vt_symbol: str) -> tuple[str, str]:
    if "." not in vt_symbol:
        return vt_symbol, ""
    return vt_symbol.rsplit(".", 1)


def _payload_from_row(row: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    payload_text = _clean(row.get("order_request_json"))
    payload: dict[str, Any] = {}
    if payload_text:
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            blockers.append("order_request_json_invalid")
    if not payload:
        vt_symbol = _clean(row.get("vt_symbol"))
        symbol, exchange = _split_vt_symbol(vt_symbol)
        payload = {
            "symbol": symbol,
            "exchange": exchange,
            "direction": _clean(row.get("direction")),
            "type": _clean(row.get("type") or row.get("order_type") or "limit"),
            "volume": row.get("planned_volume", row.get("volume", 0)),
            "price": row.get("limit_price", row.get("price", 0)),
            "offset": _clean(row.get("offset")),
            "reference": _clean(row.get("reference") or row.get("intent_id")),
            "gateway_name": _clean(row.get("gateway_name") or "CTP"),
        }
    return payload, blockers


def build_order_request(row: dict[str, Any]) -> tuple[OrderRequest | None, str, list[str], dict[str, Any]]:
    payload, blockers = _payload_from_row(row)
    symbol = _clean(payload.get("symbol"))
    exchange_text = _clean(payload.get("exchange"))
    direction = _direction(payload.get("direction"))
    offset = _offset(payload.get("offset"))
    order_type = _order_type(payload.get("type"))
    volume = _to_float(payload.get("volume"), 0.0)
    price = _to_float(payload.get("price"), 0.0)
    reference = _clean(payload.get("reference"))
    gateway_name = _clean(payload.get("gateway_name") or row.get("gateway_name") or "CTP")

    if not symbol:
        blockers.append("symbol_missing")
    if not exchange_text:
        blockers.append("exchange_missing")
    if direction is None:
        blockers.append("direction_invalid")
    if offset is None:
        blockers.append("offset_invalid")
    if order_type is None:
        blockers.append("order_type_invalid")
    if volume <= 0:
        blockers.append("volume_invalid")
    if not float(volume).is_integer():
        blockers.append("volume_not_integer_lots")
    if order_type == OrderType.LIMIT and price <= 0:
        blockers.append("limit_price_invalid")
    if not gateway_name:
        blockers.append("gateway_name_missing")
    if blockers:
        return None, gateway_name, list(dict.fromkeys(blockers)), payload

    req = OrderRequest(
        symbol=symbol,
        exchange=Exchange(exchange_text),
        direction=direction,
        type=order_type,
        volume=volume,
        price=price,
        offset=offset,
        reference=reference,
    )
    return req, gateway_name, [], payload


def _gate_blockers(gate: PhaseDSubmitGate, order_count: int, main_engine: Any | None) -> list[str]:
    blockers: list[str] = []
    if gate.mode != "live-real":
        blockers.append("mode_not_live_real")
    if not gate.phase_d_ready:
        blockers.append("phase_d_not_ready")
    if not gate.executor_ready:
        blockers.append("executor_not_ready")
    if not gate.reconciliation_aligned:
        blockers.append("reconciliation_not_aligned")
    if gate.kill_switch_active:
        blockers.append("kill_switch_active")
    if not gate.real_adapter_enabled:
        blockers.append("real_adapter_not_enabled")
    if not gate.real_submit_enabled:
        blockers.append("real_submit_not_enabled")
    if gate.confirm_text != PHASE_D_SUBMIT_CONFIRM_TEXT:
        blockers.append("live_submit_confirmation_missing")
    if not gate.allow_real_broker_side_effects:
        blockers.append("real_broker_side_effects_not_allowed")
    if order_count <= 0:
        blockers.append("no_ready_orders")
    if order_count > gate.max_order_count_per_cycle:
        blockers.append("order_count_above_cycle_limit")
    if main_engine is None:
        blockers.append("main_engine_not_injected")
    elif not callable(getattr(main_engine, "send_order", None)):
        blockers.append("main_engine_send_order_unavailable")
    return blockers


def submit_phase_d_orders(
    rows: list[dict[str, Any]],
    *,
    gate: PhaseDSubmitGate,
    main_engine: Any | None = None,
) -> list[dict[str, Any]]:
    gate_blockers = _gate_blockers(gate, len(rows), main_engine)
    checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    results: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        req, gateway_name, request_blockers, payload = build_order_request(row)
        blockers = list(dict.fromkeys([*gate_blockers, *request_blockers]))
        status = "blocked"
        vt_orderid = ""
        send_order_api_called = 0
        if gate.mode != "live-real" and not request_blockers:
            status = "dry_run_ready_no_submit"
        if not blockers and req is not None and main_engine is not None:
            vt_orderid = str(main_engine.send_order(req, gateway_name))
            send_order_api_called = 1
            status = "submitted"
        results.append(
            {
                "adapter_row_id": f"PHASED-SUBMIT-{index:03d}",
                "intent_id": _clean(row.get("intent_id")),
                "vt_symbol": _clean(row.get("vt_symbol") or payload.get("vt_symbol") or (req.vt_symbol if req else "")),
                "gateway_name": gateway_name,
                "submit_status": status,
                "submit_blockers": ";".join(blockers),
                "send_order_api_called": send_order_api_called,
                "vt_orderid": vt_orderid,
                "checked_at": checked_at,
                "order_request_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
            }
        )
    return results
