from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import threading
import time
import urllib.request
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.event import (
    EVENT_ACCOUNT,
    EVENT_CONTRACT,
    EVENT_LOG,
    EVENT_ORDER,
    EVENT_POSITION,
    EVENT_TIMER,
    EVENT_TRADE,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage174_ctp_vnpy_readonly_probe_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage174_ctp_vnpy_readonly_probe"

SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
ACCOUNT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_accounts_{MODEL_TAG}.csv"
POSITION_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
ORDER_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_orders_{MODEL_TAG}.csv"
TRADE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
CONTRACT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contracts_{MODEL_TAG}.csv"
LOG_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_logs_{MODEL_TAG}.csv"
POSITION_QUERY_CALLBACK_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_position_query_callbacks_{MODEL_TAG}.csv"
ORDER_QUERY_CALLBACK_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_order_query_callbacks_{MODEL_TAG}.csv"
TRADE_QUERY_CALLBACK_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_query_callbacks_{MODEL_TAG}.csv"
QUERY_BUNDLE_MANIFEST_PATH: Path = (
    OUTPUT_DIR / f"{OUTPUT_PREFIX}_query_bundle_manifest_{MODEL_TAG}.json"
)
QUERY_BUNDLE_SCHEMA_VERSION: int = 1

CTP_ENV_KEYS: dict[str, str] = {
    "userid": "CTP_USERID",
    "password": "CTP_PASSWORD",
    "brokerid": "CTP_BROKERID",
    "td_address": "CTP_TD_ADDRESS",
    "md_address": "CTP_MD_ADDRESS",
    "appid": "CTP_APPID",
    "auth_code": "CTP_AUTH_CODE",
    "product_info": "CTP_PRODUCT_INFO",
}


def _new_order_api_counters() -> dict[str, int]:
    return {
        "send_order_api_attempted_count": 0,
        "cancel_order_api_attempted_count": 0,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
    }


def _install_readonly_order_api_firewall(
    gateway_class: type,
    td_api_class: type,
    counters: dict[str, int],
) -> dict[tuple[type, str], Any]:
    """Block every order mutation at both vn.py CTP boundaries.

    Attempted calls are counted, but the original API is never invoked.  The
    separate called counters therefore remain authoritative exact zeros.
    """
    originals: dict[tuple[type, str], Any] = {}
    for owner in (gateway_class, td_api_class):
        for method_name, counter_name in (
            ("send_order", "send_order_api_attempted_count"),
            ("cancel_order", "cancel_order_api_attempted_count"),
        ):
            original = getattr(owner, method_name)
            originals[(owner, method_name)] = original

            def blocked(
                self: Any,
                *args: Any,
                _counter_name: str = counter_name,
                _method_name: str = method_name,
                **kwargs: Any,
            ) -> Any:
                counters[_counter_name] += 1
                raise RuntimeError(f"readonly_order_api_blocked:{_method_name}")

            setattr(owner, method_name, blocked)
    return originals


def _restore_readonly_order_api_firewall(
    gateway_class: type,
    td_api_class: type,
    originals: dict[tuple[type, str], Any],
) -> None:
    for owner in (gateway_class, td_api_class):
        for method_name in ("send_order", "cancel_order"):
            original = originals.get((owner, method_name))
            if original is not None:
                setattr(owner, method_name, original)


def _publish_order_api_counters(
    summary: dict[str, Any], counters: dict[str, int]
) -> None:
    summary.update(counters)
    summary["order_api_called_count"] = (
        counters["send_order_api_called_count"]
        + counters["cancel_order_api_called_count"]
    )
    summary["order_api_called"] = bool(summary["order_api_called_count"])


def _finalize_connection_lifecycle(
    lifecycle: dict[str, Any],
    *,
    query_requests: dict[str, dict[str, Any]],
    query_bundle_complete: bool,
    order_api_counters: dict[str, int],
    restored_epoch_ns: int,
) -> dict[str, Any]:
    old_generation = str(lifecycle.get("old_connection_generation") or "")
    new_generation = str(lifecycle.get("new_connection_generation") or "")
    query_generations = {
        name: str((query_requests.get(name) or {}).get("connection_generation") or "")
        for name in ("orders", "trades", "positions")
    }
    fresh_queries_on_new_generation = bool(
        new_generation
        and all(value == new_generation for value in query_generations.values())
    )
    one_shot_query_proof_complete = bool(
        lifecycle.get("disconnect_observed") == 1
        and lifecycle.get("reconnect_observed") == 1
        and old_generation
        and new_generation
        and old_generation != new_generation
        and type(lifecycle.get("readiness_revoked_epoch_ns")) is int
        and lifecycle["readiness_revoked_epoch_ns"] > 0
        and query_bundle_complete
        and fresh_queries_on_new_generation
        and all(value == 0 for value in order_api_counters.values())
    )
    authoritative_transition_complete = bool(
        lifecycle.get("model_tag") == "stage174_ctp_connection_lifecycle_v2"
        and type(lifecycle.get("authoritative_readiness_transition_complete")) is int
        and lifecycle.get("authoritative_readiness_transition_complete") == 1
        and type(lifecycle.get("full_snapshot_generation_complete")) is int
        and lifecycle.get("full_snapshot_generation_complete") == 1
    )
    proof_complete = bool(
        one_shot_query_proof_complete and authoritative_transition_complete
    )
    proof_blockers: list[str] = []
    if one_shot_query_proof_complete and not authoritative_transition_complete:
        proof_blockers.append(
            "authoritative_current_generation_readiness_transition_missing"
        )
    evidence_id = ""
    if proof_complete:
        evidence_id = hashlib.sha256(
            f"{old_generation}:{new_generation}:{restored_epoch_ns}".encode("utf-8")
        ).hexdigest()
    return {
        **lifecycle,
        "old_connection_generation": old_generation,
        "new_connection_generation": new_generation,
        "query_connection_generations": query_generations,
        "fresh_queries_on_new_generation": int(fresh_queries_on_new_generation),
        "one_shot_query_proof_complete": int(one_shot_query_proof_complete),
        "authoritative_readiness_transition_complete": int(
            authoritative_transition_complete
        ),
        "full_snapshot_generation_complete": int(
            type(lifecycle.get("full_snapshot_generation_complete")) is int
            and lifecycle.get("full_snapshot_generation_complete") == 1
        ),
        "proof_complete": int(proof_complete),
        "proof_blockers": proof_blockers,
        "disconnect_evidence_id": evidence_id,
        "readiness_restored_epoch_ns": restored_epoch_ns if proof_complete else None,
        "send_order_api_called_count": order_api_counters[
            "send_order_api_called_count"
        ],
        "cancel_order_api_called_count": order_api_counters[
            "cancel_order_api_called_count"
        ],
    }


# #region debug-point A:reporting
def _debug_report(hypothesis_id: str, location: str, msg: str, data: dict[str, Any] | None = None) -> None:
    payload = {
        "sessionId": "simnow-snapshot-probe",
        "runId": "pre-fix",
        "hypothesisId": hypothesis_id,
        "location": location,
        "msg": msg,
        "data": data or {},
    }
    url = "http://127.0.0.1:7777/event"
    env_path = PROJECT_DIR.parent / ".dbg" / "simnow-snapshot-probe.env"
    try:
        env_text = env_path.read_text(encoding="utf-8")
        for line in env_text.splitlines():
            if line.startswith("DEBUG_SERVER_URL="):
                url = line.split("=", 1)[1].strip() or url
            elif line.startswith("DEBUG_SESSION_ID="):
                payload["sessionId"] = line.split("=", 1)[1].strip() or payload["sessionId"]
    except Exception:
        pass
    try:
        urllib.request.urlopen(
            urllib.request.Request(
                url,
                data=json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            ),
            timeout=1.5,
        ).read()
    except Exception:
        pass


# #endregion


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return f"{value[:2]}***{value[-2:]}"


def _env_status() -> dict[str, Any]:
    status: dict[str, Any] = {}
    for logical_name, env_key in CTP_ENV_KEYS.items():
        value = os.getenv(env_key, "")
        status[logical_name] = {
            "env_key": env_key,
            "configured": bool(value),
            "masked_value": _mask(value) if logical_name in {"userid", "brokerid"} else "",
        }
    return status


def _required_env_missing() -> list[str]:
    required = ["userid", "password", "brokerid", "td_address", "md_address", "appid", "auth_code"]
    return [CTP_ENV_KEYS[name] for name in required if not os.getenv(CTP_ENV_KEYS[name], "")]


def _gateway_import_status() -> dict[str, Any]:
    if not importlib.util.find_spec("vnpy_ctp"):
        return {
            "vnpy_ctp_spec_available": False,
            "ctp_gateway_import_available": False,
            "error": "vnpy_ctp module spec not found",
        }
    try:
        from vnpy_ctp import CtpGateway

        return {
            "vnpy_ctp_spec_available": True,
            "ctp_gateway_import_available": True,
            "default_name": getattr(CtpGateway, "default_name", ""),
            "error": "",
        }
    except Exception as exc:
        return {
            "vnpy_ctp_spec_available": True,
            "ctp_gateway_import_available": False,
            "default_name": "",
            "error": repr(exc),
        }


def _ctp_setting_from_env() -> dict[str, Any]:
    return {
        "用户名": os.getenv("CTP_USERID", ""),
        "密码": os.getenv("CTP_PASSWORD", ""),
        "经纪商代码": os.getenv("CTP_BROKERID", ""),
        "交易服务器": os.getenv("CTP_TD_ADDRESS", ""),
        "行情服务器": os.getenv("CTP_MD_ADDRESS", ""),
        "产品名称": os.getenv("CTP_APPID", ""),
        "授权编码": os.getenv("CTP_AUTH_CODE", ""),
        "产品信息": os.getenv("CTP_PRODUCT_INFO", ""),
    }


def _object_to_row(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if is_dataclass(obj):
        row = asdict(obj)
    elif hasattr(obj, "__dict__"):
        row = dict(obj.__dict__)
    else:
        row = {"value": str(obj)}
    for attr in ["vt_symbol", "vt_orderid", "vt_accountid", "available"]:
        if hasattr(obj, attr):
            row[attr] = getattr(obj, attr)
    for key, value in list(row.items()):
        if isinstance(value, (datetime, pd.Timestamp)):
            row[key] = value.isoformat()
        elif hasattr(value, "value"):
            row[key] = value.value
        elif isinstance(value, (dict, list, tuple, set)):
            row[key] = json.dumps(value, ensure_ascii=False, default=str)
        elif value is None:
            row[key] = ""
    return row


def _normalized_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.drop_duplicates().reset_index(drop=True)
    return frame


def _fsync_parent(path: Path) -> None:
    try:
        directory_fd = os.open(str(path.parent), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_parent(path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _atomic_write_df(path: Path, rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = _normalized_frame(rows)
    payload = frame.to_csv(index=False).encode("utf-8-sig")
    _atomic_write_bytes(path, payload)
    return frame


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_bytes(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
    )


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _clean_ctp_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        for encoding in ("utf-8", "gbk", "latin1"):
            try:
                return value.decode(encoding).strip()
            except UnicodeDecodeError:
                continue
        return value.decode("utf-8", errors="replace").strip()
    return str(value).strip()


def _account_fingerprint(broker_id: Any, account_id: Any) -> str:
    broker = _clean_ctp_text(broker_id)
    account = _clean_ctp_text(account_id)
    if not broker or not account:
        return ""
    return hashlib.sha256(f"{broker}\0{account}".encode("utf-8")).hexdigest()


def _ctp_enum_value(mapping: dict[Any, Any], raw: Any) -> str:
    value = mapping.get(raw)
    if value is None:
        return _clean_ctp_text(raw)
    return _clean_ctp_text(getattr(value, "value", value))


def _query_callback_state(
    callbacks: list[dict[str, Any]],
    *,
    expected_reqid: int | None,
    request_return_code: int | None,
    request_sent_at: str | None = None,
) -> dict[str, Any]:
    matched = [
        row for row in callbacks
        if expected_reqid is not None and int(row.get("reqid", -1)) == expected_reqid
    ]
    error_rows = [row for row in matched if int(row.get("error_id") or 0) != 0]
    last_seen = any(bool(row.get("last")) for row in matched)
    completed_at = next(
        (
            _clean_ctp_text(row.get("received_at"))
            for row in reversed(matched)
            if bool(row.get("last")) and _clean_ctp_text(row.get("received_at"))
        ),
        "",
    )
    request_sent = expected_reqid is not None and request_return_code is not None
    complete = bool(
        request_sent
        and request_return_code == 0
        and _clean_ctp_text(request_sent_at)
        and matched
        and last_seen
        and completed_at
        and not error_rows
    )
    return {
        "reqid": expected_reqid,
        "request_sent": request_sent,
        "request_sent_at": _clean_ctp_text(request_sent_at),
        "request_return_code": request_return_code,
        "callback_count": len(matched),
        "data_callback_count": sum(bool(row.get("has_data")) for row in matched),
        "last_seen": last_seen,
        "completed_at": completed_at,
        "error_rows": len(error_rows),
        "complete": complete,
    }


def _stable_order_id(data: dict[str, Any]) -> tuple[str, str]:
    front = _clean_ctp_text(data.get("FrontID"))
    session = _clean_ctp_text(data.get("SessionID"))
    order_ref = _clean_ctp_text(data.get("OrderRef"))
    if not front or not session or not order_ref:
        return "", ""
    orderid = f"{front}_{session}_{order_ref}"
    return orderid, f"CTP.{orderid}"


def _order_sysid_key(data: dict[str, Any]) -> tuple[str, str]:
    return (
        _clean_ctp_text(data.get("ExchangeID")).upper(),
        _clean_ctp_text(data.get("OrderSysID")),
    )


def _normalize_queried_order(
    data: dict[str, Any],
    *,
    generation_uuid: str,
    ctp_gateway_module: Any,
) -> dict[str, Any]:
    orderid, vt_orderid = _stable_order_id(data)
    symbol = _clean_ctp_text(data.get("InstrumentID"))
    exchange = _ctp_enum_value(
        getattr(ctp_gateway_module, "EXCHANGE_CTP2VT", {}), data.get("ExchangeID")
    )
    insert_date = _clean_ctp_text(data.get("InsertDate"))
    insert_time = _clean_ctp_text(data.get("InsertTime"))
    return {
        "query_generation_uuid": generation_uuid,
        "query_source": "ctp_req_qry_order",
        "broker_id": _clean_ctp_text(data.get("BrokerID")),
        "account_id": _clean_ctp_text(data.get("InvestorID")),
        "trading_day": _clean_ctp_text(data.get("TradingDay")),
        "symbol": symbol,
        "exchange": exchange,
        "vt_symbol": f"{symbol}.{exchange}" if symbol and exchange else symbol,
        "direction": _ctp_enum_value(
            getattr(ctp_gateway_module, "DIRECTION_CTP2VT", {}), data.get("Direction")
        ),
        "offset": _ctp_enum_value(
            getattr(ctp_gateway_module, "OFFSET_CTP2VT", {}), data.get("CombOffsetFlag")
        ),
        "price": data.get("LimitPrice", ""),
        "volume": data.get("VolumeTotalOriginal", ""),
        "traded": data.get("VolumeTraded", ""),
        "status": _ctp_enum_value(
            getattr(ctp_gateway_module, "STATUS_CTP2VT", {}), data.get("OrderStatus")
        ),
        "orderid": orderid,
        "vt_orderid": vt_orderid,
        "front_id": data.get("FrontID", ""),
        "session_id": data.get("SessionID", ""),
        "order_ref": _clean_ctp_text(data.get("OrderRef")),
        "order_sys_id": _clean_ctp_text(data.get("OrderSysID")),
        "exchange_id_raw": _clean_ctp_text(data.get("ExchangeID")),
        "datetime": f"{insert_date} {insert_time}".strip(),
        "status_msg": _clean_ctp_text(data.get("StatusMsg")),
        "gateway_name": "CTP",
        "stable_order_identity_complete": int(bool(vt_orderid)),
    }


def _normalize_queried_trade(
    data: dict[str, Any],
    *,
    generation_uuid: str,
    ctp_gateway_module: Any,
    order_matches: list[dict[str, Any]],
) -> dict[str, Any]:
    symbol = _clean_ctp_text(data.get("InstrumentID"))
    exchange = _ctp_enum_value(
        getattr(ctp_gateway_module, "EXCHANGE_CTP2VT", {}), data.get("ExchangeID")
    )
    tradeid = _clean_ctp_text(data.get("TradeID"))
    trade_date = _clean_ctp_text(data.get("TradeDate"))
    trade_time = _clean_ctp_text(data.get("TradeTime"))
    unique_orderids = list(
        dict.fromkeys(
            _clean_ctp_text(row.get("vt_orderid"))
            for row in order_matches
            if _clean_ctp_text(row.get("vt_orderid"))
        )
    )
    vt_orderid = unique_orderids[0] if len(unique_orderids) == 1 else ""
    mapping_status = (
        "joined_unique_order_sys_id"
        if len(unique_orderids) == 1
        else "order_sys_id_not_found"
        if not order_matches
        else "order_sys_id_ambiguous_or_unstable"
    )
    broker_id = _clean_ctp_text(data.get("BrokerID"))
    account_id = _clean_ctp_text(data.get("InvestorID"))
    order_sys_id = _clean_ctp_text(data.get("OrderSysID"))
    stable_trade_identity = ""
    if (
        tradeid
        and order_sys_id
        and broker_id
        and account_id
        and exchange
        and trade_date
    ):
        stable_trade_identity = (
            f"ctp:{broker_id}:"
            f"{account_id}:{exchange}:"
            f"{trade_date}:{order_sys_id}:{tradeid}"
        )
    return {
        "query_generation_uuid": generation_uuid,
        "query_source": "ctp_req_qry_trade",
        "broker_id": broker_id,
        "account_id": account_id,
        "trading_day": _clean_ctp_text(data.get("TradingDay") or trade_date),
        "symbol": symbol,
        "exchange": exchange,
        "vt_symbol": f"{symbol}.{exchange}" if symbol and exchange else symbol,
        "direction": _ctp_enum_value(
            getattr(ctp_gateway_module, "DIRECTION_CTP2VT", {}), data.get("Direction")
        ),
        "offset": _ctp_enum_value(
            getattr(ctp_gateway_module, "OFFSET_CTP2VT", {}), data.get("OffsetFlag")
        ),
        "price": data.get("Price", ""),
        "volume": data.get("Volume", ""),
        "tradeid": tradeid,
        "vt_tradeid": f"CTP.{tradeid}" if tradeid else "",
        "broker_trade_identity": stable_trade_identity,
        "order_sys_id": order_sys_id,
        "exchange_id_raw": _clean_ctp_text(data.get("ExchangeID")),
        "vt_orderid": vt_orderid,
        "order_mapping_status": mapping_status,
        "order_mapping_complete": int(bool(vt_orderid)),
        "datetime": f"{trade_date} {trade_time}".strip(),
        "gateway_name": "CTP",
        "stable_trade_identity_complete": int(bool(stable_trade_identity)),
    }


def _normalize_query_bundle_rows(
    raw_orders: list[dict[str, Any]],
    raw_trades: list[dict[str, Any]],
    *,
    generation_uuid: str,
    ctp_gateway_module: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    orders = [
        _normalize_queried_order(
            row,
            generation_uuid=generation_uuid,
            ctp_gateway_module=ctp_gateway_module,
        )
        for row in raw_orders
    ]
    pair_map: dict[tuple[str, str], list[dict[str, Any]]] = {}
    sysid_map: dict[str, list[dict[str, Any]]] = {}
    for order in orders:
        key = (
            _clean_ctp_text(order.get("exchange_id_raw")).upper(),
            _clean_ctp_text(order.get("order_sys_id")),
        )
        if not key[1]:
            continue
        pair_map.setdefault(key, []).append(order)
        sysid_map.setdefault(key[1], []).append(order)

    trades: list[dict[str, Any]] = []
    for raw in raw_trades:
        key = _order_sysid_key(raw)
        matches = pair_map.get(key, [])
        if not matches and key[1]:
            # Some broker trade rows omit ExchangeID.  A globally unique
            # OrderSysID in the same queried order generation remains stable.
            unique = sysid_map.get(key[1], [])
            if len(unique) == 1:
                matches = unique
        trades.append(
            _normalize_queried_trade(
                raw,
                generation_uuid=generation_uuid,
                ctp_gateway_module=ctp_gateway_module,
                order_matches=matches,
            )
        )

    return orders, trades, {
        "trade_order_join_complete": all(
            int(row.get("order_mapping_complete") or 0) == 1 for row in trades
        ),
        "trade_identity_complete": all(
            int(row.get("stable_trade_identity_complete") or 0) == 1 for row in trades
        ),
        "unmapped_trade_count": sum(
            int(row.get("order_mapping_complete") or 0) != 1 for row in trades
        ),
        "unstable_trade_identity_count": sum(
            int(row.get("stable_trade_identity_complete") or 0) != 1 for row in trades
        ),
    }


def _number_or_none(value: Any) -> float | None:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return None
    return float(number)


def _normalize_queried_positions(
    raw_positions: list[dict[str, Any]],
    *,
    generation_uuid: str,
    broker_trading_day: str,
    ctp_gateway_module: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Aggregate only the rows returned by this generation's position reqid.

    This deliberately does not depend on the asynchronous contract query.  A
    missing exchange/direction/account identity therefore fails the generation
    closed instead of borrowing contract state from a prior or concurrent
    callback.  Price remains zero because CTP position cost needs the contract
    multiplier; Stage904 reconstructs the entry price from the same-generation
    trade rows.
    """

    grouped: dict[tuple[str, ...], dict[str, Any]] = {}
    invalid_rows = 0
    for raw in raw_positions:
        broker_id = _clean_ctp_text(raw.get("BrokerID"))
        account_id = _clean_ctp_text(raw.get("InvestorID"))
        trading_day = _clean_ctp_text(raw.get("TradingDay")) or broker_trading_day
        symbol = _clean_ctp_text(raw.get("InstrumentID"))
        exchange_raw = _clean_ctp_text(raw.get("ExchangeID"))
        exchange = _ctp_enum_value(
            getattr(ctp_gateway_module, "EXCHANGE_CTP2VT", {}),
            raw.get("ExchangeID"),
        )
        direction = _ctp_enum_value(
            getattr(ctp_gateway_module, "DIRECTION_CTP2VT", {}),
            raw.get("PosiDirection"),
        )
        volume = _number_or_none(raw.get("Position"))
        today_volume = _number_or_none(raw.get("TodayPosition"))
        yd_volume = _number_or_none(raw.get("YdPosition"))
        pnl = _number_or_none(raw.get("PositionProfit"))
        if (
            not broker_id
            or not account_id
            or not trading_day
            or not symbol
            or not exchange_raw
            or not exchange
            or not direction
            or volume is None
        ):
            invalid_rows += 1
            continue

        direction_token = direction.strip().lower()
        raw_direction = _clean_ctp_text(raw.get("PosiDirection"))
        long_constant = _clean_ctp_text(
            getattr(ctp_gateway_module, "THOST_FTDC_PD_Long", "")
        )
        is_long = bool(
            direction_token in {"long", "多"}
            or (long_constant and raw_direction == long_constant)
        )
        frozen = _number_or_none(
            raw.get("ShortFrozen") if is_long else raw.get("LongFrozen")
        )
        if frozen is None:
            frozen = 0.0
        if yd_volume is None:
            yd_volume = max(volume - (today_volume or 0.0), 0.0)

        key = (
            broker_id,
            account_id,
            trading_day,
            symbol,
            exchange,
            direction,
        )
        aggregate = grouped.setdefault(
            key,
            {
                "query_generation_uuid": generation_uuid,
                "query_source": "ctp_req_qry_investor_position",
                "broker_id": broker_id,
                "account_id": account_id,
                "trading_day": trading_day,
                "symbol": symbol,
                "exchange": exchange,
                "vt_symbol": f"{symbol}.{exchange}",
                "direction": direction,
                "volume": 0.0,
                "frozen": 0.0,
                "pnl": 0.0,
                "yd_volume": 0.0,
                "price": 0.0,
                "gateway_name": "CTP",
                "source_row_count": 0,
            },
        )
        aggregate["volume"] += volume
        aggregate["frozen"] += frozen
        aggregate["pnl"] += pnl or 0.0
        aggregate["yd_volume"] += yd_volume
        aggregate["source_row_count"] += 1

    positions = list(grouped.values())
    return positions, {
        "position_normalization_complete": invalid_rows == 0,
        "position_raw_row_count": len(raw_positions),
        "position_normalized_row_count": len(positions),
        "position_invalid_row_count": invalid_rows,
    }


def _analyze_logs(log_rows: list[dict[str, Any]]) -> dict[str, Any]:
    messages = [str(row.get("msg", "")).strip() for row in log_rows]
    analysis: dict[str, Any] = {
        "td_connected": False,
        "md_connected": False,
        "td_auth_success": False,
        "md_login_success": False,
        "td_login_success": False,
        "td_login_failed": False,
        "td_login_failed_message": "",
        "status_hint": "no_logs",
    }
    for message in messages:
        if "交易服务器连接成功" in message:
            analysis["td_connected"] = True
        if "行情服务器连接成功" in message:
            analysis["md_connected"] = True
        if "交易服务器授权验证成功" in message:
            analysis["td_auth_success"] = True
        if "行情服务器登录成功" in message:
            analysis["md_login_success"] = True
        if "交易服务器登录成功" in message:
            analysis["td_login_success"] = True
        if "交易服务器登录失败" in message:
            analysis["td_login_failed"] = True
            analysis["td_login_failed_message"] = message

    if analysis["td_login_success"]:
        analysis["status_hint"] = "trading_login_success"
    elif analysis["td_login_failed"]:
        analysis["status_hint"] = "trading_login_failed"
    elif analysis["td_connected"] or analysis["md_connected"]:
        analysis["status_hint"] = "connected_but_no_trading_login_outcome"
    elif messages:
        analysis["status_hint"] = "logs_present_without_ctp_progress"
    return analysis


def _analyze_position_snapshot(rows: dict[str, list[dict[str, Any]]], log_analysis: dict[str, Any]) -> dict[str, Any]:
    callbacks = [
        row
        for row in rows.get("position_query_callbacks", [])
        if int(row.get("reqid_matched", 0) or 0) == 1
    ]
    position_rows = pd.DataFrame(rows.get("positions", [])).drop_duplicates().to_dict(orient="records")
    data_callbacks = [row for row in callbacks if row.get("has_data")]
    error_callbacks = [row for row in callbacks if int(row.get("error_id") or 0) != 0]
    last_seen = any(bool(row.get("last")) for row in callbacks)
    nonzero_position_rows = []
    for row in position_rows:
        volume = pd.to_numeric(row.get("volume", row.get("position", 0)), errors="coerce")
        frozen = pd.to_numeric(row.get("frozen", 0), errors="coerce")
        if pd.notna(volume) and abs(float(volume)) > 1e-12:
            nonzero_position_rows.append(row)
        elif pd.notna(frozen) and abs(float(frozen)) > 1e-12:
            nonzero_position_rows.append(row)

    state = "position_query_not_available"
    if nonzero_position_rows:
        state = "positions_received"
    elif error_callbacks:
        state = "position_query_error"
    elif last_seen and data_callbacks and not position_rows:
        state = "position_payload_without_position_rows"
    elif last_seen:
        # These callbacks have already been filtered to the explicit position
        # reqid.  A zero-error last callback with no non-zero normalized row is
        # direct flat evidence and does not depend on log-event timing.
        state = "confirmed_flat"
    elif log_analysis.get("td_login_success"):
        state = "position_query_not_completed"

    return {
        "position_snapshot_state": state,
        "position_rows": len(position_rows),
        "nonzero_position_rows": len(nonzero_position_rows),
        "position_query_callback_rows": len(callbacks),
        "position_query_data_callback_rows": len(data_callbacks),
        "position_query_last_seen": bool(last_seen),
        "position_query_error_rows": len(error_callbacks),
    }


def _run_probe(connect: bool, wait_seconds: int) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    query_generation_uuid = str(uuid.uuid4())
    order_api_counters = _new_order_api_counters()
    gateway_import = _gateway_import_status()
    import_available = bool(gateway_import["ctp_gateway_import_available"])
    # #region debug-point A:probe-start
    _debug_report(
        "A",
        "run_ctp_stage174_readonly_probe.py:_run_probe:start",
        "[DEBUG] probe started",
        {
            "connect": bool(connect),
            "wait_seconds": int(wait_seconds),
            "import_available": import_available,
            "missing_env": _required_env_missing(),
        },
    )
    # #endregion
    rows: dict[str, list[dict[str, Any]]] = {
        "accounts": [],
        "positions": [],
        "orders": [],
        "trades": [],
        "contracts": [],
        "logs": [],
        "position_query_callbacks": [],
        "order_query_callbacks": [],
        "trade_query_callbacks": [],
        "event_orders": [],
        "event_trades": [],
        "raw_queried_orders": [],
        "raw_queried_trades": [],
        "raw_queried_positions": [],
    }

    query_requests: dict[str, dict[str, Any]] = {
        "orders": {"reqid": None, "return_code": None, "request_sent_at": "", "connection_generation": ""},
        "trades": {"reqid": None, "return_code": None, "request_sent_at": "", "connection_generation": ""},
        "positions": {"reqid": None, "return_code": None, "request_sent_at": "", "connection_generation": ""},
    }
    connection_lifecycle: dict[str, Any] = {
        "model_tag": "stage174_ctp_connection_lifecycle_v1",
        "disconnect_observed": 0,
        "reconnect_observed": 0,
        "old_connection_generation": "",
        "new_connection_generation": "",
        "current_connection_generation": "",
        "readiness_revoked_epoch_ns": None,
        "probe_closing": 0,
        "events": [],
    }

    summary: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().astimezone().isoformat(),
        "query_generation_uuid": query_generation_uuid,
        "connect_requested": connect,
        "wait_seconds": wait_seconds,
        "vnpy_ctp_import_available": import_available,
        "gateway_import": gateway_import,
        "env_status": _env_status(),
        "missing_required_env": _required_env_missing(),
        "real_order_enabled": False,
        "status": "dry_run_not_connected",
        "connection_target": {
            "td_address": os.getenv("CTP_TD_ADDRESS", ""),
            "md_address": os.getenv("CTP_MD_ADDRESS", ""),
        },
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "accounts": str(ACCOUNT_PATH),
            "positions": str(POSITION_PATH),
            "orders": str(ORDER_PATH),
            "trades": str(TRADE_PATH),
            "contracts": str(CONTRACT_PATH),
            "logs": str(LOG_PATH),
            "position_query_callbacks": str(POSITION_QUERY_CALLBACK_PATH),
            "order_query_callbacks": str(ORDER_QUERY_CALLBACK_PATH),
            "trade_query_callbacks": str(TRADE_QUERY_CALLBACK_PATH),
            "query_bundle_manifest": str(QUERY_BUNDLE_MANIFEST_PATH),
        },
    }
    _publish_order_api_counters(summary, order_api_counters)
    summary["connection_lifecycle"] = dict(connection_lifecycle)

    if not connect:
        summary["status"] = "dry_run_not_connected"
        # #region debug-point A:dry-run
        _debug_report("A", "run_ctp_stage174_readonly_probe.py:_run_probe:dry_run", "[DEBUG] probe exited dry-run", {"status": summary["status"]})
        # #endregion
        return summary | {"rows": rows}

    if not import_available:
        summary["status"] = "blocked_missing_vnpy_ctp"
        # #region debug-point A:import-blocked
        _debug_report("A", "run_ctp_stage174_readonly_probe.py:_run_probe:import_blocked", "[DEBUG] probe blocked by missing vnpy_ctp", {"status": summary["status"], "gateway_import": gateway_import})
        # #endregion
        return summary | {"rows": rows}

    missing = _required_env_missing()
    if missing:
        summary["status"] = "blocked_missing_env"
        # #region debug-point A:env-blocked
        _debug_report("A", "run_ctp_stage174_readonly_probe.py:_run_probe:env_blocked", "[DEBUG] probe blocked by missing env", {"status": summary["status"], "missing": missing})
        # #endregion
        return summary | {"rows": rows}

    from vnpy_ctp import CtpGateway
    from vnpy_ctp.gateway import ctp_gateway as ctp_gateway_module

    original_position_rsp = ctp_gateway_module.CtpTdApi.onRspQryInvestorPosition
    original_settlement_rsp = ctp_gateway_module.CtpTdApi.onRspSettlementInfoConfirm
    original_order_query_rsp = ctp_gateway_module.CtpTdApi.onRspQryOrder
    original_trade_query_rsp = ctp_gateway_module.CtpTdApi.onRspQryTrade
    original_front_connected = ctp_gateway_module.CtpTdApi.onFrontConnected
    original_front_disconnected = ctp_gateway_module.CtpTdApi.onFrontDisconnected
    settlement_confirmed = threading.Event()
    order_query_completed = threading.Event()
    trade_query_completed = threading.Event()
    position_query_completed = threading.Event()
    settlement_response: dict[str, Any] = {
        "reqid": None,
        "last_seen": False,
        "error_id": None,
    }

    def instrumented_position_rsp(self: Any, data: dict, error: dict, reqid: int, last: bool) -> None:
        expected_reqid = query_requests["positions"].get("reqid")
        matched = expected_reqid is not None and int(reqid) == int(expected_reqid)
        rows["position_query_callbacks"].append(
            {
                "query_generation_uuid": query_generation_uuid,
                "reqid": int(reqid),
                "expected_reqid": expected_reqid,
                "reqid_matched": int(matched),
                "last": bool(last),
                "has_data": bool(data),
                "instrument": _clean_ctp_text(data.get("InstrumentID")) if isinstance(data, dict) else "",
                "position": data.get("Position", "") if isinstance(data, dict) else "",
                "error_id": error.get("ErrorID", 0) if isinstance(error, dict) else 0,
                "error_msg": _clean_ctp_text(error.get("ErrorMsg")) if isinstance(error, dict) else "",
                "received_at": datetime.now().astimezone().isoformat(),
            }
        )
        if matched and isinstance(data, dict) and data:
            rows["raw_queried_positions"].append(dict(data))
        if matched and last:
            position_query_completed.set()
        if not matched:
            return original_position_rsp(self, data, error, reqid, last)
        return None

    def instrumented_settlement_rsp(
        self: Any, data: dict, error: dict, reqid: int, last: bool
    ) -> None:
        error_id = int(error.get("ErrorID", 0) or 0) if isinstance(error, dict) else 0
        settlement_response.update(
            {"reqid": int(reqid), "last_seen": bool(last), "error_id": error_id}
        )
        if last and error_id == 0:
            settlement_confirmed.set()
        # Defer vn.py's implicit instrument query.  It contains an unbounded
        # retry loop and otherwise competes for CTP query flow with the
        # generation-bound order/trade/position requests below.
        return None

    def instrumented_order_query_rsp(
        self: Any, data: dict, error: dict, reqid: int, last: bool
    ) -> None:
        expected_reqid = query_requests["orders"].get("reqid")
        matched = expected_reqid is not None and int(reqid) == int(expected_reqid)
        rows["order_query_callbacks"].append(
            {
                "query_generation_uuid": query_generation_uuid,
                "reqid": int(reqid),
                "expected_reqid": expected_reqid,
                "reqid_matched": int(matched),
                "last": bool(last),
                "has_data": bool(data),
                "order_sys_id": _clean_ctp_text(data.get("OrderSysID")) if isinstance(data, dict) else "",
                "error_id": error.get("ErrorID", 0) if isinstance(error, dict) else 0,
                "error_msg": _clean_ctp_text(error.get("ErrorMsg")) if isinstance(error, dict) else "",
                "received_at": datetime.now().astimezone().isoformat(),
            }
        )
        if matched and isinstance(data, dict) and data:
            rows["raw_queried_orders"].append(dict(data))
        if matched and last:
            order_query_completed.set()

    def instrumented_trade_query_rsp(
        self: Any, data: dict, error: dict, reqid: int, last: bool
    ) -> None:
        expected_reqid = query_requests["trades"].get("reqid")
        matched = expected_reqid is not None and int(reqid) == int(expected_reqid)
        rows["trade_query_callbacks"].append(
            {
                "query_generation_uuid": query_generation_uuid,
                "reqid": int(reqid),
                "expected_reqid": expected_reqid,
                "reqid_matched": int(matched),
                "last": bool(last),
                "has_data": bool(data),
                "trade_id": _clean_ctp_text(data.get("TradeID")) if isinstance(data, dict) else "",
                "order_sys_id": _clean_ctp_text(data.get("OrderSysID")) if isinstance(data, dict) else "",
                "error_id": error.get("ErrorID", 0) if isinstance(error, dict) else 0,
                "error_msg": _clean_ctp_text(error.get("ErrorMsg")) if isinstance(error, dict) else "",
                "received_at": datetime.now().astimezone().isoformat(),
            }
        )
        if matched and isinstance(data, dict) and data:
            rows["raw_queried_trades"].append(dict(data))
        if matched and last:
            trade_query_completed.set()

    def instrumented_front_connected(self: Any) -> None:
        now_epoch_ns = time.time_ns()
        generation = uuid.uuid4().hex
        connection_lifecycle["current_connection_generation"] = generation
        if connection_lifecycle.get("disconnect_observed") == 1:
            connection_lifecycle["reconnect_observed"] = 1
            connection_lifecycle["new_connection_generation"] = generation
        connection_lifecycle["events"].append(
            {
                "event": "front_connected",
                "connection_generation": generation,
                "epoch_ns": now_epoch_ns,
            }
        )
        return original_front_connected(self)

    def instrumented_front_disconnected(self: Any, reason: int) -> None:
        now_epoch_ns = time.time_ns()
        current_generation = str(
            connection_lifecycle.get("current_connection_generation") or ""
        )
        if connection_lifecycle.get("probe_closing") == 1:
            connection_lifecycle["events"].append(
                {
                    "event": "front_disconnected_during_probe_close",
                    "connection_generation": current_generation,
                    "reason": int(reason),
                    "epoch_ns": now_epoch_ns,
                }
            )
            return original_front_disconnected(self, reason)
        connection_lifecycle["disconnect_observed"] = 1
        connection_lifecycle["old_connection_generation"] = current_generation
        connection_lifecycle["readiness_revoked_epoch_ns"] = now_epoch_ns
        connection_lifecycle["events"].append(
            {
                "event": "front_disconnected",
                "connection_generation": current_generation,
                "reason": int(reason),
                "epoch_ns": now_epoch_ns,
            }
        )
        return original_front_disconnected(self, reason)

    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    main_engine.add_gateway(CtpGateway)

    def on_account(event: Any) -> None:
        rows["accounts"].append(_object_to_row(event.data))
        # #region debug-point C:account-event
        _debug_report("C", "run_ctp_stage174_readonly_probe.py:on_account", "[DEBUG] account callback received", {"account_rows": len(rows["accounts"])})
        # #endregion

    def on_position(event: Any) -> None:
        rows["positions"].append(_object_to_row(event.data))
        # #region debug-point C:position-event
        _debug_report("C", "run_ctp_stage174_readonly_probe.py:on_position", "[DEBUG] position callback received", {"position_rows": len(rows["positions"])})
        # #endregion

    def on_order(event: Any) -> None:
        rows["event_orders"].append(_object_to_row(event.data))
        # #region debug-point C:order-event
        _debug_report("C", "run_ctp_stage174_readonly_probe.py:on_order", "[DEBUG] order callback received", {"order_rows": len(rows["event_orders"])})
        # #endregion

    def on_trade(event: Any) -> None:
        rows["event_trades"].append(_object_to_row(event.data))
        # #region debug-point C:trade-event
        _debug_report("C", "run_ctp_stage174_readonly_probe.py:on_trade", "[DEBUG] trade callback received", {"trade_rows": len(rows["event_trades"])})
        # #endregion

    def on_contract(event: Any) -> None:
        rows["contracts"].append(_object_to_row(event.data))
        # #region debug-point C:contract-event
        _debug_report("C", "run_ctp_stage174_readonly_probe.py:on_contract", "[DEBUG] contract callback received", {"contract_rows": len(rows["contracts"])})
        # #endregion

    def on_log(event: Any) -> None:
        rows["logs"].append(_object_to_row(event.data))
        # #region debug-point B:log-event
        _debug_report("B", "run_ctp_stage174_readonly_probe.py:on_log", "[DEBUG] log callback received", {"log_rows": len(rows["logs"]), "last_log": rows["logs"][-1] if rows["logs"] else {}})
        # #endregion

    event_engine.register(EVENT_ACCOUNT, on_account)
    event_engine.register(EVENT_POSITION, on_position)
    event_engine.register(EVENT_ORDER, on_order)
    event_engine.register(EVENT_TRADE, on_trade)
    event_engine.register(EVENT_CONTRACT, on_contract)
    event_engine.register(EVENT_LOG, on_log)

    # Install callback instrumentation only after all engine construction and
    # event registration has succeeded.  Any constructor failure therefore
    # leaves the process-wide CTP class untouched; the inner finally restores
    # every installed method even when MainEngine.close itself raises.
    ctp_gateway_module.CtpTdApi.onRspQryInvestorPosition = instrumented_position_rsp
    ctp_gateway_module.CtpTdApi.onRspSettlementInfoConfirm = instrumented_settlement_rsp
    ctp_gateway_module.CtpTdApi.onRspQryOrder = instrumented_order_query_rsp
    ctp_gateway_module.CtpTdApi.onRspQryTrade = instrumented_trade_query_rsp
    ctp_gateway_module.CtpTdApi.onFrontConnected = instrumented_front_connected
    ctp_gateway_module.CtpTdApi.onFrontDisconnected = instrumented_front_disconnected
    order_api_originals = _install_readonly_order_api_firewall(
        CtpGateway,
        ctp_gateway_module.CtpTdApi,
        order_api_counters,
    )

    td_api: Any = None
    gateway: Any = None
    timer_query_paused = False
    try:
        # #region debug-point A:before-connect
        _debug_report("A", "run_ctp_stage174_readonly_probe.py:_run_probe:before_connect", "[DEBUG] connecting readonly probe", {"td_address": os.getenv("CTP_TD_ADDRESS", ""), "md_address": os.getenv("CTP_MD_ADDRESS", "")})
        # #endregion
        main_engine.connect(_ctp_setting_from_env(), "CTP")
        # #region debug-point D:after-connect-call
        _debug_report("D", "run_ctp_stage174_readonly_probe.py:_run_probe:after_connect", "[DEBUG] main_engine.connect returned", {"wait_seconds": int(wait_seconds)})
        # #endregion
        deadline = time.monotonic() + max(wait_seconds, 1)
        gateway = main_engine.get_gateway("CTP")
        td_api = getattr(gateway, "td_api", None)
        if gateway is not None:
            event_engine.unregister(EVENT_TIMER, gateway.process_timer_event)
            timer_query_paused = True
        while time.monotonic() < deadline:
            if (
                settlement_confirmed.is_set()
                and bool(getattr(td_api, "login_status", False))
            ):
                break
            time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))

        if settlement_confirmed.is_set() and td_api is not None:
            summary["broker_trading_day"] = _clean_ctp_text(td_api.getTradingDay())
            query_account = {
                "BrokerID": os.getenv("CTP_BROKERID", ""),
                "InvestorID": os.getenv("CTP_USERID", ""),
            }
            flow_gap_seconds = 1.05
            max_callback_wait_seconds = 3.0
            last_query_sent_at: float | None = None

            def send_bound_query(
                name: str,
                request: Any,
                completed: threading.Event,
                *,
                reserve_seconds: float,
            ) -> bool:
                nonlocal last_query_sent_at
                if last_query_sent_at is not None:
                    flow_wait = flow_gap_seconds - (
                        time.monotonic() - last_query_sent_at
                    )
                    if flow_wait > 0:
                        if time.monotonic() + flow_wait + reserve_seconds >= deadline:
                            return False
                        time.sleep(flow_wait)
                if time.monotonic() + reserve_seconds >= deadline:
                    return False
                td_api.reqid += 1
                reqid = int(td_api.reqid)
                query_requests[name]["reqid"] = reqid
                last_query_sent_at = time.monotonic()
                query_requests[name]["request_sent_at"] = (
                    datetime.now().astimezone().isoformat()
                )
                query_requests[name]["connection_generation"] = str(
                    connection_lifecycle.get("current_connection_generation") or ""
                )
                query_requests[name]["return_code"] = int(
                    request(query_account, reqid)
                )
                if query_requests[name]["return_code"] != 0:
                    return False
                callback_budget = min(
                    max_callback_wait_seconds,
                    max(0.0, deadline - time.monotonic() - reserve_seconds),
                )
                return bool(
                    callback_budget > 0
                    and completed.wait(timeout=callback_budget)
                )

            # CTP query flow control is serial.  A timed-out or rejected query
            # stops the sequence; issuing a later query while its predecessor
            # is unresolved would make callback attribution ambiguous.
            order_done = send_bound_query(
                "orders",
                td_api.reqQryOrder,
                order_query_completed,
                reserve_seconds=4.25,
            )
            trade_done = bool(
                order_done
                and send_bound_query(
                    "trades",
                    td_api.reqQryTrade,
                    trade_query_completed,
                    reserve_seconds=2.1,
                )
            )
            position_done = bool(
                trade_done
                and send_bound_query(
                    "positions",
                    td_api.reqQryInvestorPosition,
                    position_query_completed,
                    reserve_seconds=0.0,
                )
            )
            summary["query_sequence"] = {
                "order_last_received": order_done,
                "trade_last_received": trade_done,
                "position_last_received": position_done,
                "flow_gap_seconds": flow_gap_seconds,
                "max_callback_wait_seconds": max_callback_wait_seconds,
            }

            # Preserve the contract snapshot without gating the evidence
            # bundle on contract initialization.  This replaces vn.py's
            # unbounded settlement callback loop with one bounded attempt.
            contract_query = {
                "reqid": None,
                "request_return_code": None,
            }
            if position_done and last_query_sent_at is not None:
                flow_wait = flow_gap_seconds - (
                    time.monotonic() - last_query_sent_at
                )
                if flow_wait > 0 and time.monotonic() + flow_wait < deadline:
                    time.sleep(flow_wait)
                if time.monotonic() < deadline:
                    td_api.reqid += 1
                    contract_query["reqid"] = int(td_api.reqid)
                    contract_query["request_return_code"] = int(
                        td_api.reqQryInstrument({}, td_api.reqid)
                    )
            summary["contract_query"] = contract_query

            if contract_query["request_return_code"] == 0:
                while (
                    time.monotonic() < deadline
                    and not bool(getattr(td_api, "contract_inited", False))
                ):
                    time.sleep(
                        min(0.1, max(0.0, deadline - time.monotonic()))
                    )
            # Once contracts are complete, the remaining timer budget may
            # refresh the legacy account artifact.  Any later automatic
            # position callbacks have a different reqid and are excluded from
            # this generation's normalized position artifact.
            if (
                timer_query_paused
                and gateway is not None
                and bool(getattr(td_api, "contract_inited", False))
                and deadline - time.monotonic() > 2.0
            ):
                event_engine.register(EVENT_TIMER, gateway.process_timer_event)
                timer_query_paused = False

        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)
        summary["status"] = "connected_or_attempted_readonly"
        log_analysis = _analyze_logs(rows["logs"])
        summary["log_analysis"] = log_analysis
        if rows["accounts"] or position_query_completed.is_set():
            summary["status"] = "readonly_snapshots_received"
        elif log_analysis["status_hint"] == "trading_login_failed":
            summary["status"] = "readonly_trading_login_failed"
            summary["failure_reason"] = log_analysis["td_login_failed_message"]
        elif log_analysis["status_hint"] == "connected_but_no_trading_login_outcome":
            summary["status"] = "readonly_connected_no_login_outcome"
        elif log_analysis["status_hint"] == "logs_present_without_ctp_progress":
            summary["status"] = "readonly_logs_without_ctp_progress"
        # #region debug-point D:after-wait
        _debug_report(
            "D",
            "run_ctp_stage174_readonly_probe.py:_run_probe:after_wait",
            "[DEBUG] readonly wait finished",
            {
                "status": summary["status"],
                "account_rows": len(rows["accounts"]),
                "position_rows": len(rows["positions"]),
                "order_rows": len(rows["orders"]),
                "trade_rows": len(rows["trades"]),
                "contract_rows": len(rows["contracts"]),
                "log_rows": len(rows["logs"]),
            },
        )
        # #endregion
    except Exception as exc:
        summary["status"] = "connect_exception"
        summary["exception"] = repr(exc)
        # #region debug-point B:connect-exception
        _debug_report("B", "run_ctp_stage174_readonly_probe.py:_run_probe:exception", "[DEBUG] connect raised exception", {"exception": repr(exc)})
        # #endregion
    finally:
        summary["timer_query_paused_until_close"] = bool(timer_query_paused)
        connection_lifecycle["probe_closing"] = 1
        try:
            main_engine.close()
        except Exception as exc:
            summary["close_exception"] = repr(exc)
            summary["status"] = "readonly_close_failed"
        finally:
            ctp_gateway_module.CtpTdApi.onRspQryInvestorPosition = original_position_rsp
            ctp_gateway_module.CtpTdApi.onRspSettlementInfoConfirm = original_settlement_rsp
            ctp_gateway_module.CtpTdApi.onRspQryOrder = original_order_query_rsp
            ctp_gateway_module.CtpTdApi.onRspQryTrade = original_trade_query_rsp
            ctp_gateway_module.CtpTdApi.onFrontConnected = original_front_connected
            ctp_gateway_module.CtpTdApi.onFrontDisconnected = original_front_disconnected
            _restore_readonly_order_api_firewall(
                CtpGateway,
                ctp_gateway_module.CtpTdApi,
                order_api_originals,
            )

        _publish_order_api_counters(summary, order_api_counters)

        if "log_analysis" not in summary:
            summary["log_analysis"] = _analyze_logs(rows["logs"])
        expected_broker_id = os.getenv("CTP_BROKERID", "")
        expected_account_id = os.getenv("CTP_USERID", "")
        broker_trading_day = _clean_ctp_text(
            summary.get("broker_trading_day")
            or getattr(td_api, "getTradingDay", lambda: "")()
        )
        normalized_orders, normalized_trades, join_status = _normalize_query_bundle_rows(
            rows["raw_queried_orders"],
            rows["raw_queried_trades"],
            generation_uuid=query_generation_uuid,
            ctp_gateway_module=ctp_gateway_module,
        )
        normalized_positions, position_status = _normalize_queried_positions(
            rows["raw_queried_positions"],
            generation_uuid=query_generation_uuid,
            broker_trading_day=broker_trading_day,
            ctp_gateway_module=ctp_gateway_module,
        )
        rows["orders"] = normalized_orders
        rows["trades"] = normalized_trades
        rows["positions"] = normalized_positions
        order_query = _query_callback_state(
            rows["order_query_callbacks"],
            expected_reqid=query_requests["orders"].get("reqid"),
            request_return_code=query_requests["orders"].get("return_code"),
            request_sent_at=query_requests["orders"].get("request_sent_at"),
        )
        trade_query = _query_callback_state(
            rows["trade_query_callbacks"],
            expected_reqid=query_requests["trades"].get("reqid"),
            request_return_code=query_requests["trades"].get("return_code"),
            request_sent_at=query_requests["trades"].get("request_sent_at"),
        )
        position_query = _query_callback_state(
            rows["position_query_callbacks"],
            expected_reqid=query_requests["positions"].get("reqid"),
            request_return_code=query_requests["positions"].get("return_code"),
            request_sent_at=query_requests["positions"].get("request_sent_at"),
        )
        position_query.update(position_status)
        response_rows = normalized_orders + normalized_trades + normalized_positions
        response_account_match = bool(
            all(
            _clean_ctp_text(row.get("broker_id")) == expected_broker_id
            and _clean_ctp_text(row.get("account_id")) == expected_account_id
            for row in response_rows
            )
            and (
                bool(response_rows)
                or (
                    order_query["complete"]
                    and trade_query["complete"]
                    and position_query["complete"]
                    and sum(
                        int(query["data_callback_count"])
                        for query in (order_query, trade_query, position_query)
                    )
                    == 0
                )
            )
        )
        login_account_match = bool(
            _clean_ctp_text(getattr(td_api, "brokerid", "")) == expected_broker_id
            and _clean_ctp_text(getattr(td_api, "userid", "")) == expected_account_id
        )
        summary["generated_at"] = datetime.now().astimezone().isoformat()
        summary["broker_trading_day"] = broker_trading_day
        summary["settlement_confirmation"] = dict(settlement_response)
        summary["broker_query_bundle"] = {
            "schema_version": QUERY_BUNDLE_SCHEMA_VERSION,
            "generation_uuid": query_generation_uuid,
            "generated_at": summary["generated_at"],
            "broker_trading_day": broker_trading_day,
            "account": {
                "account_fingerprint": _account_fingerprint(
                    expected_broker_id, expected_account_id
                ),
                "login_account_match": login_account_match,
                "response_account_match": response_account_match,
            },
            "queries": {
                "orders": order_query,
                "trades": trade_query,
                "positions": position_query,
            },
            "trade_order_join_complete": bool(join_status["trade_order_join_complete"]),
            "trade_identity_complete": bool(join_status["trade_identity_complete"]),
            "unmapped_trade_count": int(join_status["unmapped_trade_count"]),
            "unstable_trade_identity_count": int(join_status["unstable_trade_identity_count"]),
            "complete": bool(
                order_query["complete"]
                and trade_query["complete"]
                and position_query["complete"]
                and position_status["position_normalization_complete"]
                and position_status["position_raw_row_count"]
                == position_query["data_callback_count"]
                and summary.get("status") == "readonly_snapshots_received"
                and not summary.get("close_exception")
                and broker_trading_day
                and login_account_match
                and response_account_match
                and join_status["trade_order_join_complete"]
                and join_status["trade_identity_complete"]
            ),
        }
        summary["connection_lifecycle"] = _finalize_connection_lifecycle(
            connection_lifecycle,
            query_requests=query_requests,
            query_bundle_complete=bool(summary["broker_query_bundle"]["complete"]),
            order_api_counters=order_api_counters,
            restored_epoch_ns=time.time_ns(),
        )
        summary["broker_snapshot"] = _analyze_position_snapshot(rows, summary["log_analysis"])
        # #region debug-point D:before-close
        _debug_report(
            "D",
            "run_ctp_stage174_readonly_probe.py:_run_probe:finally",
            "[DEBUG] probe closed main_engine and finalized query bundle",
            {
                "status": summary["status"],
                "account_rows": len(rows["accounts"]),
                "position_rows": len(rows["positions"]),
                "order_rows": len(rows["orders"]),
                "trade_rows": len(rows["trades"]),
                "contract_rows": len(rows["contracts"]),
                "log_rows": len(rows["logs"]),
                "position_snapshot_state": summary["broker_snapshot"]["position_snapshot_state"],
                "position_query_callback_rows": len(rows["position_query_callbacks"]),
            },
        )
        # #endregion

    return summary | {"rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage174 CTP/vn.py read-only probe.")
    parser.add_argument("--connect", action="store_true", help="Actually attempt CTP connection. No orders are sent.")
    parser.add_argument("--wait-seconds", type=int, default=15)
    args = parser.parse_args()

    result = _run_probe(connect=bool(args.connect), wait_seconds=int(args.wait_seconds))
    rows = result.pop("rows")
    frames = {
        "accounts": _atomic_write_df(ACCOUNT_PATH, rows["accounts"]),
        "positions": _atomic_write_df(POSITION_PATH, rows["positions"]),
        "orders": _atomic_write_df(ORDER_PATH, rows["orders"]),
        "trades": _atomic_write_df(TRADE_PATH, rows["trades"]),
        "contracts": _atomic_write_df(CONTRACT_PATH, rows["contracts"]),
        "logs": _atomic_write_df(LOG_PATH, rows["logs"]),
        "position_query_callbacks": _atomic_write_df(
            POSITION_QUERY_CALLBACK_PATH, rows["position_query_callbacks"]
        ),
        "order_query_callbacks": _atomic_write_df(
            ORDER_QUERY_CALLBACK_PATH, rows["order_query_callbacks"]
        ),
        "trade_query_callbacks": _atomic_write_df(
            TRADE_QUERY_CALLBACK_PATH, rows["trade_query_callbacks"]
        ),
    }
    result["row_counts"] = {name: int(len(frame)) for name, frame in frames.items()}
    query_bundle = result.setdefault(
        "broker_query_bundle",
        {
            "schema_version": QUERY_BUNDLE_SCHEMA_VERSION,
            "generation_uuid": _clean_ctp_text(result.get("query_generation_uuid")),
            "generated_at": _clean_ctp_text(result.get("generated_at")),
            "broker_trading_day": "",
            "account": {
                "account_fingerprint": "",
                "login_account_match": False,
                "response_account_match": False,
            },
            "queries": {
                "orders": _query_callback_state([], expected_reqid=None, request_return_code=None),
                "trades": _query_callback_state([], expected_reqid=None, request_return_code=None),
                "positions": _query_callback_state([], expected_reqid=None, request_return_code=None),
            },
            "trade_order_join_complete": False,
            "trade_identity_complete": False,
            "complete": False,
        },
    )
    artifact_paths = {
        "orders": ORDER_PATH,
        "trades": TRADE_PATH,
        "positions": POSITION_PATH,
    }
    artifacts = {
        name: {
            "path": str(path.resolve()),
            "row_count": int(len(frames[name])),
            "sha256": _sha256_path(path),
        }
        for name, path in artifact_paths.items()
    }
    query_bundle["artifacts"] = artifacts
    query_bundle["manifest_path"] = str(QUERY_BUNDLE_MANIFEST_PATH.resolve())

    generation_uuid = _clean_ctp_text(query_bundle.get("generation_uuid"))
    account_fingerprint = _clean_ctp_text(
        (query_bundle.get("account") or {}).get("account_fingerprint")
    )
    for name in ("orders", "trades", "positions"):
        frame = frames[name]
        generations = (
            set(frame["query_generation_uuid"].dropna().astype(str).str.strip())
            if "query_generation_uuid" in frame.columns
            else set()
        )
        artifacts[name]["row_generation_match"] = bool(
            not generations or generations == {generation_uuid}
        )
        fingerprints = set()
        if {"broker_id", "account_id"}.issubset(frame.columns):
            fingerprints = {
                fingerprint
                for broker_id, account_id in zip(
                    frame["broker_id"], frame["account_id"], strict=False
                )
                if (fingerprint := _account_fingerprint(broker_id, account_id))
            }
        artifacts[name]["row_account_match"] = bool(
            not fingerprints or fingerprints == {account_fingerprint}
        )
    queries = query_bundle.get("queries", {})
    query_reqids = [
        int((queries.get(name, {}) or {}).get("reqid") or 0)
        for name in ("orders", "trades", "positions")
    ]
    position_query = queries.get("positions", {}) or {}
    query_bundle["complete"] = bool(
        query_bundle.get("complete")
        and artifacts["orders"]["row_generation_match"]
        and artifacts["trades"]["row_generation_match"]
        and artifacts["positions"]["row_generation_match"]
        and artifacts["orders"]["row_account_match"]
        and artifacts["trades"]["row_account_match"]
        and artifacts["positions"]["row_account_match"]
        and all(query_reqids)
        and len(set(query_reqids)) == len(query_reqids)
        and artifacts["orders"]["row_count"]
        == int((queries.get("orders", {}) or {}).get("data_callback_count", -1))
        and artifacts["trades"]["row_count"]
        == int((queries.get("trades", {}) or {}).get("data_callback_count", -1))
        and int(position_query.get("position_raw_row_count", -1))
        == int(position_query.get("data_callback_count", -2))
        and artifacts["positions"]["row_count"]
        == int(position_query.get("position_normalized_row_count", -1))
        and position_query.get("position_normalization_complete") is True
    )

    # Summary is published before the manifest.  A crash at any earlier point
    # leaves either the prior manifest or no matching manifest, so consumers
    # fail closed instead of combining files from different generations.
    _atomic_write_json(SUMMARY_PATH, result)
    manifest = {
        "schema_version": QUERY_BUNDLE_SCHEMA_VERSION,
        "generation_uuid": generation_uuid,
        "generated_at": _clean_ctp_text(query_bundle.get("generated_at")),
        "published_at": datetime.now().astimezone().isoformat(),
        "broker_trading_day": _clean_ctp_text(query_bundle.get("broker_trading_day")),
        "account": dict(query_bundle.get("account") or {}),
        "queries": dict(query_bundle.get("queries") or {}),
        "trade_order_join_complete": bool(query_bundle.get("trade_order_join_complete")),
        "trade_identity_complete": bool(query_bundle.get("trade_identity_complete")),
        "complete": bool(query_bundle.get("complete")),
        "artifacts": artifacts,
        "summary_binding": {
            "path": str(SUMMARY_PATH.resolve()),
            "generated_at": _clean_ctp_text(result.get("generated_at")),
            "status": _clean_ctp_text(result.get("status")),
        },
    }
    _atomic_write_json(QUERY_BUNDLE_MANIFEST_PATH, manifest)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"summary json: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
