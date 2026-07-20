from __future__ import annotations

import argparse
from contextlib import nullcontext
import copy
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
QUERY_BUNDLE_SCHEMA_VERSION: int = 2
FULL_READINESS_SNAPSHOT_COMPONENTS: tuple[str, ...] = (
    "settlement",
    "account",
    "contracts",
    "orders",
    "trades",
    "positions",
)
NATIVE_CTP_MUTATION_METHODS: tuple[str, ...] = (
    "reqBatchOrderAction",
    "reqCombActionInsert",
    "reqExecOrderAction",
    "reqExecOrderInsert",
    "reqForQuoteInsert",
    "reqFromBankToFutureByFuture",
    "reqFromFutureToBankByFuture",
    "reqOptionSelfCloseAction",
    "reqOptionSelfCloseInsert",
    "reqOrderAction",
    "reqOrderInsert",
    "reqParkedOrderAction",
    "reqParkedOrderInsert",
    "reqQuoteAction",
    "reqQuoteInsert",
    "reqRemoveParkedOrder",
    "reqRemoveParkedOrderAction",
    "reqTradingAccountPasswordUpdate",
    "reqUserPasswordUpdate",
)

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
        "native_mutation_api_attempted_count": 0,
        "native_mutation_api_called_count": 0,
    }


def _new_probe_state_lock() -> Any:
    return threading.RLock()


def _new_order_api_evidence_window() -> dict[str, Any]:
    return {
        "model_tag": "stage174_order_api_evidence_window_v1",
        "closed": 0,
        "closed_epoch_ns": None,
    }


def _state_guard(state_lock: Any | None) -> Any:
    return state_lock if state_lock is not None else nullcontext()


def _close_order_api_evidence_window(
    state_lock: Any | None,
    evidence_window: dict[str, Any],
) -> dict[str, Any]:
    with _state_guard(state_lock):
        evidence_window["closed"] = 1
        evidence_window["closed_epoch_ns"] = time.time_ns()
        return dict(evidence_window)


def _freeze_order_api_evidence(
    state_lock: Any | None,
    evidence_window: dict[str, Any],
    counters: dict[str, int],
) -> tuple[dict[str, Any], dict[str, int]]:
    with _state_guard(state_lock):
        evidence_window["closed"] = 1
        evidence_window["closed_epoch_ns"] = time.time_ns()
        return dict(evidence_window), dict(counters)


def _install_readonly_order_api_firewall(
    gateway_class: type,
    td_api_class: type,
    counters: dict[str, int],
    state_lock: Any | None = None,
    evidence_window: dict[str, Any] | None = None,
) -> dict[tuple[type, str], tuple[bool, Any]]:
    """Block every order mutation at both vn.py CTP boundaries.

    Attempted calls are counted, but the original API is never invoked.  The
    separate called counters therefore remain authoritative exact zeros.
    """
    originals: dict[tuple[type, str], tuple[bool, Any]] = {}
    for owner in (gateway_class, td_api_class):
        for method_name in ("send_order", "cancel_order"):
            originals[(owner, method_name)] = (
                method_name in owner.__dict__,
                getattr(owner, method_name),
            )
    for method_name in NATIVE_CTP_MUTATION_METHODS:
        original = getattr(td_api_class, method_name, None)
        if original is not None:
            originals[(td_api_class, method_name)] = (
                method_name in td_api_class.__dict__,
                original,
            )

    for owner in (gateway_class, td_api_class):
        for method_name, counter_name in (
            ("send_order", "send_order_api_attempted_count"),
            ("cancel_order", "cancel_order_api_attempted_count"),
        ):
            def blocked(
                self: Any,
                *args: Any,
                _counter_name: str = counter_name,
                _method_name: str = method_name,
                _state_lock: Any | None = state_lock,
                _evidence_window: dict[str, Any] | None = evidence_window,
                **kwargs: Any,
            ) -> Any:
                with _state_guard(_state_lock):
                    if _evidence_window is not None and _evidence_window.get("closed") == 1:
                        raise RuntimeError(
                            f"readonly_order_api_blocked_after_evidence_window:{_method_name}"
                        )
                    counters[_counter_name] += 1
                raise RuntimeError(f"readonly_order_api_blocked:{_method_name}")

            setattr(owner, method_name, blocked)
    for method_name in NATIVE_CTP_MUTATION_METHODS:
        if (td_api_class, method_name) not in originals:
            continue

        def blocked_native(
            self: Any,
            *args: Any,
            _method_name: str = method_name,
            _state_lock: Any | None = state_lock,
            _evidence_window: dict[str, Any] | None = evidence_window,
            **kwargs: Any,
        ) -> Any:
            with _state_guard(_state_lock):
                if _evidence_window is not None and _evidence_window.get("closed") == 1:
                    raise RuntimeError(
                        f"readonly_native_ctp_mutation_blocked_after_evidence_window:{_method_name}"
                    )
                counters["native_mutation_api_attempted_count"] += 1
            raise RuntimeError(f"readonly_native_ctp_mutation_blocked:{_method_name}")

        setattr(td_api_class, method_name, blocked_native)
    return originals


def _restore_readonly_order_api_firewall(
    gateway_class: type,
    td_api_class: type,
    originals: dict[tuple[type, str], tuple[bool, Any]],
) -> None:
    for (owner, method_name), (was_owned, original) in originals.items():
        if was_owned:
            setattr(owner, method_name, original)
        elif method_name in owner.__dict__:
            delattr(owner, method_name)


def _publish_order_api_counters(
    summary: dict[str, Any],
    counters: dict[str, int],
    state_lock: Any | None = None,
) -> None:
    with _state_guard(state_lock):
        summary.update(counters)
        summary["order_api_attempted_count"] = (
            counters["send_order_api_attempted_count"]
            + counters["cancel_order_api_attempted_count"]
            + counters["native_mutation_api_attempted_count"]
        )
        summary["order_api_called_count"] = (
            counters["send_order_api_called_count"]
            + counters["cancel_order_api_called_count"]
            + counters["native_mutation_api_called_count"]
        )
        summary["order_api_called"] = bool(summary["order_api_called_count"])


def _new_connection_lifecycle() -> dict[str, Any]:
    return {
        "model_tag": "stage174_ctp_connection_lifecycle_v2",
        "state_synchronization": "threading_rlock_v1",
        "disconnect_observed": 0,
        "reconnect_observed": 0,
        "old_connection_generation": "",
        "new_connection_generation": "",
        "current_connection_generation": "",
        "readiness_generation": "",
        "readiness_generation_before_disconnect": "",
        "readiness_was_ready_before_disconnect": 0,
        "readiness_revoked_epoch_ns": None,
        "reconnect_connected_epoch_ns": None,
        "readiness_restored_epoch_ns": None,
        "snapshot_connection_generations": {},
        "probe_closing": 0,
        "events": [],
    }


def _record_front_connected(
    lifecycle: dict[str, Any], *, generation: str, epoch_ns: int
) -> None:
    lifecycle["current_connection_generation"] = generation
    if lifecycle.get("disconnect_observed") == 1:
        lifecycle["reconnect_observed"] = 1
        lifecycle["new_connection_generation"] = generation
        lifecycle["reconnect_connected_epoch_ns"] = epoch_ns
    lifecycle["events"].append(
        {
            "event": "front_connected",
            "connection_generation": generation,
            "epoch_ns": epoch_ns,
        }
    )


def _record_front_disconnected(
    lifecycle: dict[str, Any], *, reason: int, epoch_ns: int
) -> None:
    current_generation = str(
        lifecycle.get("current_connection_generation") or ""
    )
    readiness_generation = str(lifecycle.get("readiness_generation") or "")
    lifecycle["disconnect_observed"] = 1
    lifecycle["old_connection_generation"] = current_generation
    if current_generation and readiness_generation == current_generation:
        lifecycle["readiness_was_ready_before_disconnect"] = 1
        lifecycle["readiness_generation_before_disconnect"] = current_generation
        lifecycle["readiness_revoked_epoch_ns"] = epoch_ns
    lifecycle["current_connection_generation"] = ""
    lifecycle["readiness_generation"] = ""
    lifecycle["snapshot_connection_generations"] = {}
    lifecycle["events"].append(
        {
            "event": "front_disconnected",
            "connection_generation": current_generation,
            "reason": reason,
            "epoch_ns": epoch_ns,
        }
    )


def _record_snapshot_readiness(
    lifecycle: dict[str, Any],
    *,
    generation: str,
    snapshot_generations: dict[str, str],
    epoch_ns: int,
) -> bool:
    complete = bool(
        generation
        and str(lifecycle.get("current_connection_generation") or "")
        == generation
        and all(
            str(snapshot_generations.get(name) or "") == generation
            for name in FULL_READINESS_SNAPSHOT_COMPONENTS
        )
    )
    if not complete:
        return False
    lifecycle["snapshot_connection_generations"] = dict(snapshot_generations)
    lifecycle["readiness_generation"] = generation
    event_name = "initial_readiness_established"
    if (
        lifecycle.get("reconnect_observed") == 1
        and str(lifecycle.get("new_connection_generation") or "") == generation
        and lifecycle.get("readiness_was_ready_before_disconnect") == 1
    ):
        lifecycle["readiness_restored_epoch_ns"] = epoch_ns
        event_name = "reconnect_readiness_restored"
    lifecycle["events"].append(
        {
            "event": event_name,
            "connection_generation": generation,
            "epoch_ns": epoch_ns,
        }
    )
    return True


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
    snapshot_generations = lifecycle.get("snapshot_connection_generations")
    if not isinstance(snapshot_generations, dict):
        snapshot_generations = {}
    full_snapshot_generation_complete = bool(
        new_generation
        and str(lifecycle.get("current_connection_generation") or "")
        == new_generation
        and str(lifecycle.get("readiness_generation") or "") == new_generation
        and all(
            str(snapshot_generations.get(name) or "") == new_generation
            for name in FULL_READINESS_SNAPSHOT_COMPONENTS
        )
        and all(value == new_generation for value in query_generations.values())
    )
    revoked_epoch_ns = lifecycle.get("readiness_revoked_epoch_ns")
    connected_epoch_ns = lifecycle.get("reconnect_connected_epoch_ns")
    lifecycle_restored_epoch_ns = lifecycle.get("readiness_restored_epoch_ns")
    authoritative_transition_complete = bool(
        lifecycle.get("model_tag") == "stage174_ctp_connection_lifecycle_v2"
        and lifecycle.get("readiness_was_ready_before_disconnect") == 1
        and str(lifecycle.get("readiness_generation_before_disconnect") or "")
        == old_generation
        and type(revoked_epoch_ns) is int
        and type(connected_epoch_ns) is int
        and type(lifecycle_restored_epoch_ns) is int
        and 0 < revoked_epoch_ns <= connected_epoch_ns <= lifecycle_restored_epoch_ns
        and full_snapshot_generation_complete
    )
    proof_complete = bool(
        one_shot_query_proof_complete and authoritative_transition_complete
    )
    proof_blockers: list[str] = []
    if one_shot_query_proof_complete and not full_snapshot_generation_complete:
        proof_blockers.append("full_current_generation_snapshot_missing")
    if one_shot_query_proof_complete and not authoritative_transition_complete:
        proof_blockers.append("authoritative_readiness_transition_missing")
        proof_blockers.append(
            "authoritative_current_generation_readiness_transition_missing"
        )
    evidence_id = ""
    if proof_complete:
        evidence_id = hashlib.sha256(
            (
                f"{old_generation}:{new_generation}:"
                f"{revoked_epoch_ns}:{connected_epoch_ns}:"
                f"{lifecycle_restored_epoch_ns}"
            ).encode("utf-8")
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
        "full_snapshot_generation_complete": int(full_snapshot_generation_complete),
        "proof_complete": int(proof_complete),
        "proof_blockers": proof_blockers,
        "disconnect_evidence_id": evidence_id,
        "readiness_restored_epoch_ns": (
            lifecycle_restored_epoch_ns if proof_complete else None
        ),
        "send_order_api_called_count": order_api_counters[
            "send_order_api_called_count"
        ],
        "cancel_order_api_called_count": order_api_counters[
            "cancel_order_api_called_count"
        ],
        "native_mutation_api_attempted_count": order_api_counters[
            "native_mutation_api_attempted_count"
        ],
        "native_mutation_api_called_count": order_api_counters[
            "native_mutation_api_called_count"
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


def _run_probe(
    connect: bool,
    wait_seconds: int,
    observe_reconnect: bool = False,
    query_flow_gap_seconds: float = 1.05,
) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    query_generation_uuid = str(uuid.uuid4())
    state_lock = _new_probe_state_lock()
    order_api_counters = _new_order_api_counters()
    order_api_evidence_window = _new_order_api_evidence_window()
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
        "account_query_callbacks": [],
        "contract_query_callbacks": [],
        "event_orders": [],
        "event_trades": [],
        "raw_queried_orders": [],
        "raw_queried_trades": [],
        "raw_queried_positions": [],
        "raw_queried_accounts": [],
    }
    result_rows = rows

    query_requests: dict[str, dict[str, Any]] = {
        "orders": {"reqid": None, "return_code": None, "request_sent_at": "", "connection_generation": ""},
        "trades": {"reqid": None, "return_code": None, "request_sent_at": "", "connection_generation": ""},
        "positions": {"reqid": None, "return_code": None, "request_sent_at": "", "connection_generation": ""},
        "account": {"reqid": None, "return_code": None, "request_sent_at": "", "connection_generation": ""},
        "contracts": {"reqid": None, "return_code": None, "request_sent_at": "", "connection_generation": ""},
    }
    connection_lifecycle = _new_connection_lifecycle()

    summary: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().astimezone().isoformat(),
        "query_generation_uuid": query_generation_uuid,
        "connect_requested": connect,
        "wait_seconds": wait_seconds,
        "observe_reconnect": int(observe_reconnect),
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
    _publish_order_api_counters(summary, order_api_counters, state_lock)
    summary["order_api_evidence_window"] = dict(order_api_evidence_window)
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
    original_settlement_request = ctp_gateway_module.CtpTdApi.reqSettlementInfoConfirm
    original_order_query_rsp = ctp_gateway_module.CtpTdApi.onRspQryOrder
    original_trade_query_rsp = ctp_gateway_module.CtpTdApi.onRspQryTrade
    original_account_query_rsp = ctp_gateway_module.CtpTdApi.onRspQryTradingAccount
    original_contract_query_rsp = ctp_gateway_module.CtpTdApi.onRspQryInstrument
    original_front_connected = ctp_gateway_module.CtpTdApi.onFrontConnected
    original_front_disconnected = ctp_gateway_module.CtpTdApi.onFrontDisconnected
    settlement_confirmed = threading.Event()
    order_query_completed = threading.Event()
    trade_query_completed = threading.Event()
    position_query_completed = threading.Event()
    account_query_completed = threading.Event()
    contract_query_completed = threading.Event()
    settlement_response: dict[str, Any] = {
        "reqid": None,
        "last_seen": False,
        "error_id": None,
    }
    settlement_request: dict[str, Any] = {
        "reqid": None,
        "connection_generation": "",
        "request_sent_at": "",
        "return_code": None,
    }

    def instrumented_settlement_request(
        self: Any, request: dict, reqid: int
    ) -> int:
        with state_lock:
            if connection_lifecycle.get("probe_closing") == 1:
                return -1
            generation = str(
                connection_lifecycle.get("current_connection_generation") or ""
            )
            settlement_request.update(
                {
                    "reqid": int(reqid),
                    "connection_generation": generation,
                    "request_sent_at": datetime.now().astimezone().isoformat(),
                }
            )
        return_code = int(original_settlement_request(self, request, reqid))
        with state_lock:
            settlement_request["return_code"] = return_code
        return return_code

    def instrumented_position_rsp(self: Any, data: dict, error: dict, reqid: int, last: bool) -> None:
        with state_lock:
            if connection_lifecycle.get("probe_closing") == 1:
                return None
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
        with state_lock:
            if connection_lifecycle.get("probe_closing") == 1:
                return None
            current_generation = str(
                connection_lifecycle.get("current_connection_generation") or ""
            )
            matched = bool(
                settlement_request.get("reqid") is not None
                and int(reqid) == int(settlement_request["reqid"])
                and str(settlement_request.get("connection_generation") or "")
                == current_generation
            )
            settlement_response.update(
                {
                    "reqid": int(reqid),
                    "last_seen": bool(last),
                    "error_id": error_id,
                    "reqid_matched": int(matched),
                    "connection_generation": current_generation if matched else "",
                }
            )
            if last and error_id == 0 and matched:
                settlement_confirmed.set()
        # Defer vn.py's implicit instrument query.  It contains an unbounded
        # retry loop and otherwise competes for CTP query flow with the
        # generation-bound order/trade/position requests below.
        return None

    def instrumented_order_query_rsp(
        self: Any, data: dict, error: dict, reqid: int, last: bool
    ) -> None:
        with state_lock:
            if connection_lifecycle.get("probe_closing") == 1:
                return None
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
        with state_lock:
            if connection_lifecycle.get("probe_closing") == 1:
                return None
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

    def instrumented_account_query_rsp(
        self: Any, data: dict, error: dict, reqid: int, last: bool
    ) -> None:
        with state_lock:
            if connection_lifecycle.get("probe_closing") == 1:
                return None
            expected_reqid = query_requests["account"].get("reqid")
            matched = expected_reqid is not None and int(reqid) == int(expected_reqid)
            rows["account_query_callbacks"].append(
                {
                    "query_generation_uuid": query_generation_uuid,
                    "reqid": int(reqid),
                    "expected_reqid": expected_reqid,
                    "reqid_matched": int(matched),
                    "last": bool(last),
                    "has_data": bool(data),
                    "account_id": _clean_ctp_text(data.get("AccountID"))
                    if isinstance(data, dict)
                    else "",
                    "error_id": error.get("ErrorID", 0)
                    if isinstance(error, dict)
                    else 0,
                    "error_msg": _clean_ctp_text(error.get("ErrorMsg"))
                    if isinstance(error, dict)
                    else "",
                    "received_at": datetime.now().astimezone().isoformat(),
                }
            )
            if matched and isinstance(data, dict) and data:
                rows["raw_queried_accounts"].append(dict(data))
        result = original_account_query_rsp(self, data, error, reqid, last)
        with state_lock:
            if (
                matched
                and last
                and query_requests["account"].get("reqid") == int(reqid)
            ):
                account_query_completed.set()
        return result

    def instrumented_contract_query_rsp(
        self: Any, data: dict, error: dict, reqid: int, last: bool
    ) -> None:
        with state_lock:
            if connection_lifecycle.get("probe_closing") == 1:
                return None
            expected_reqid = query_requests["contracts"].get("reqid")
            matched = expected_reqid is not None and int(reqid) == int(expected_reqid)
            rows["contract_query_callbacks"].append(
                {
                    "query_generation_uuid": query_generation_uuid,
                    "reqid": int(reqid),
                    "expected_reqid": expected_reqid,
                    "reqid_matched": int(matched),
                    "last": bool(last),
                    "has_data": bool(data),
                    "instrument": _clean_ctp_text(data.get("InstrumentID"))
                    if isinstance(data, dict)
                    else "",
                    "error_id": error.get("ErrorID", 0)
                    if isinstance(error, dict)
                    else 0,
                    "error_msg": _clean_ctp_text(error.get("ErrorMsg"))
                    if isinstance(error, dict)
                    else "",
                    "received_at": datetime.now().astimezone().isoformat(),
                }
            )
        result = original_contract_query_rsp(self, data, error, reqid, last)
        with state_lock:
            if (
                matched
                and last
                and query_requests["contracts"].get("reqid") == int(reqid)
            ):
                contract_query_completed.set()
        return result

    def instrumented_front_connected(self: Any) -> None:
        now_epoch_ns = time.time_ns()
        generation = uuid.uuid4().hex
        with state_lock:
            if connection_lifecycle.get("probe_closing") == 1:
                connection_lifecycle["events"].append(
                    {
                        "event": "front_connected_during_probe_close_ignored",
                        "connection_generation": generation,
                        "epoch_ns": now_epoch_ns,
                    }
                )
                return None
            settlement_confirmed.clear()
            settlement_request.update(
                {
                    "reqid": None,
                    "connection_generation": "",
                    "request_sent_at": "",
                    "return_code": None,
                }
            )
            _record_front_connected(
                connection_lifecycle,
                generation=generation,
                epoch_ns=now_epoch_ns,
            )
        return original_front_connected(self)

    def instrumented_front_disconnected(self: Any, reason: int) -> None:
        now_epoch_ns = time.time_ns()
        with state_lock:
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
            else:
                settlement_confirmed.clear()
                _record_front_disconnected(
                    connection_lifecycle,
                    reason=int(reason),
                    epoch_ns=now_epoch_ns,
                )
        return original_front_disconnected(self, reason)

    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    main_engine.add_gateway(CtpGateway)

    def on_account(event: Any) -> None:
        with state_lock:
            if connection_lifecycle.get("probe_closing") == 1:
                return
            rows["accounts"].append(_object_to_row(event.data))
            row_count = len(rows["accounts"])
        # #region debug-point C:account-event
        _debug_report("C", "run_ctp_stage174_readonly_probe.py:on_account", "[DEBUG] account callback received", {"account_rows": row_count})
        # #endregion

    def on_position(event: Any) -> None:
        with state_lock:
            if connection_lifecycle.get("probe_closing") == 1:
                return
            rows["positions"].append(_object_to_row(event.data))
            row_count = len(rows["positions"])
        # #region debug-point C:position-event
        _debug_report("C", "run_ctp_stage174_readonly_probe.py:on_position", "[DEBUG] position callback received", {"position_rows": row_count})
        # #endregion

    def on_order(event: Any) -> None:
        with state_lock:
            if connection_lifecycle.get("probe_closing") == 1:
                return
            rows["event_orders"].append(_object_to_row(event.data))
            row_count = len(rows["event_orders"])
        # #region debug-point C:order-event
        _debug_report("C", "run_ctp_stage174_readonly_probe.py:on_order", "[DEBUG] order callback received", {"order_rows": row_count})
        # #endregion

    def on_trade(event: Any) -> None:
        with state_lock:
            if connection_lifecycle.get("probe_closing") == 1:
                return
            rows["event_trades"].append(_object_to_row(event.data))
            row_count = len(rows["event_trades"])
        # #region debug-point C:trade-event
        _debug_report("C", "run_ctp_stage174_readonly_probe.py:on_trade", "[DEBUG] trade callback received", {"trade_rows": row_count})
        # #endregion

    def on_contract(event: Any) -> None:
        with state_lock:
            if connection_lifecycle.get("probe_closing") == 1:
                return
            rows["contracts"].append(_object_to_row(event.data))
            row_count = len(rows["contracts"])
        # #region debug-point C:contract-event
        _debug_report("C", "run_ctp_stage174_readonly_probe.py:on_contract", "[DEBUG] contract callback received", {"contract_rows": row_count})
        # #endregion

    def on_log(event: Any) -> None:
        with state_lock:
            if connection_lifecycle.get("probe_closing") == 1:
                return
            rows["logs"].append(_object_to_row(event.data))
            row_count = len(rows["logs"])
            last_log = dict(rows["logs"][-1]) if rows["logs"] else {}
        # #region debug-point B:log-event
        _debug_report("B", "run_ctp_stage174_readonly_probe.py:on_log", "[DEBUG] log callback received", {"log_rows": row_count, "last_log": last_log})
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
    ctp_gateway_module.CtpTdApi.reqSettlementInfoConfirm = instrumented_settlement_request
    ctp_gateway_module.CtpTdApi.onRspSettlementInfoConfirm = instrumented_settlement_rsp
    ctp_gateway_module.CtpTdApi.onRspQryOrder = instrumented_order_query_rsp
    ctp_gateway_module.CtpTdApi.onRspQryTrade = instrumented_trade_query_rsp
    ctp_gateway_module.CtpTdApi.onRspQryTradingAccount = instrumented_account_query_rsp
    ctp_gateway_module.CtpTdApi.onRspQryInstrument = instrumented_contract_query_rsp
    ctp_gateway_module.CtpTdApi.onFrontConnected = instrumented_front_connected
    ctp_gateway_module.CtpTdApi.onFrontDisconnected = instrumented_front_disconnected
    order_api_originals = _install_readonly_order_api_firewall(
        CtpGateway,
        ctp_gateway_module.CtpTdApi,
        order_api_counters,
        state_lock,
        order_api_evidence_window,
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
        flow_gap_seconds = max(0.0, float(query_flow_gap_seconds))
        snapshot_generation_attempts: dict[str, int] = {}
        exhausted_snapshot_generations: set[str] = set()
        completion_events = {
            "orders": order_query_completed,
            "trades": trade_query_completed,
            "positions": position_query_completed,
            "account": account_query_completed,
            "contracts": contract_query_completed,
        }
        callback_row_names = {
            "orders": "order_query_callbacks",
            "trades": "trade_query_callbacks",
            "positions": "position_query_callbacks",
            "account": "account_query_callbacks",
            "contracts": "contract_query_callbacks",
        }

        def reset_snapshot_cycle() -> None:
            with state_lock:
                for event in completion_events.values():
                    event.clear()
                for request_state in query_requests.values():
                    request_state.update(
                        {
                            "reqid": None,
                            "return_code": None,
                            "request_sent_at": "",
                            "connection_generation": "",
                        }
                    )
                for row_name in callback_row_names.values():
                    rows[row_name].clear()
                for row_name in (
                    "raw_queried_orders",
                    "raw_queried_trades",
                    "raw_queried_positions",
                    "raw_queried_accounts",
                    "accounts",
                    "positions",
                    "orders",
                    "trades",
                    "contracts",
                ):
                    rows[row_name].clear()

        def run_full_snapshot_cycle(generation: str) -> bool:
            reset_snapshot_cycle()
            query_account = {
                "BrokerID": os.getenv("CTP_BROKERID", ""),
                "InvestorID": os.getenv("CTP_USERID", ""),
            }
            last_query_sent_at: float | None = None

            def send_bound_query(
                name: str,
                request: Any,
                payload: dict[str, Any],
                *,
                reserve_seconds: float,
            ) -> bool:
                nonlocal last_query_sent_at
                with state_lock:
                    if (
                        str(
                            connection_lifecycle.get("current_connection_generation")
                            or ""
                        )
                        != generation
                    ):
                        return False
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
                with state_lock:
                    if (
                        str(
                            connection_lifecycle.get("current_connection_generation")
                            or ""
                        )
                        != generation
                    ):
                        return False
                    td_api.reqid += 1
                    reqid = int(td_api.reqid)
                    request_state = query_requests[name]
                    request_state["reqid"] = reqid
                    last_query_sent_at = time.monotonic()
                    request_state["request_sent_at"] = (
                        datetime.now().astimezone().isoformat()
                    )
                    request_state["connection_generation"] = generation
                return_code = int(request(payload, reqid))
                with state_lock:
                    request_state["return_code"] = return_code
                if return_code != 0:
                    return False
                callback_budget = max(
                    0.0, deadline - time.monotonic() - reserve_seconds
                )
                completed = completion_events[name]
                if not callback_budget > 0 or not completed.wait(
                    timeout=callback_budget
                ):
                    return False
                with state_lock:
                    return bool(
                        str(
                            connection_lifecycle.get(
                                "current_connection_generation"
                            )
                            or ""
                        )
                        == generation
                        and query_requests[name].get("reqid") == reqid
                    )

            query_plan = (
                ("orders", td_api.reqQryOrder, query_account, flow_gap_seconds * 4),
                ("trades", td_api.reqQryTrade, query_account, flow_gap_seconds * 3),
                ("positions", td_api.reqQryInvestorPosition, query_account, flow_gap_seconds * 2),
                ("account", td_api.reqQryTradingAccount, query_account, flow_gap_seconds),
                ("contracts", td_api.reqQryInstrument, {}, 0.0),
            )
            query_results: dict[str, bool] = {}
            predecessor_complete = True
            for (
                name,
                request,
                payload,
                reserve_seconds,
            ) in query_plan:
                query_results[name] = bool(
                    predecessor_complete
                    and send_bound_query(
                        name,
                        request,
                        payload,
                        reserve_seconds=reserve_seconds,
                    )
                )
                predecessor_complete = query_results[name]
            summary["query_sequence"] = {
                **{
                    f"{name}_last_received": query_results[name]
                    for name in query_results
                },
                "connection_generation": generation,
                "flow_gap_seconds": flow_gap_seconds,
                "callback_wait_policy": "global_deadline_minus_downstream_flow_gaps",
            }
            with state_lock:
                snapshot_generations = {
                    "settlement": str(
                        settlement_response.get("connection_generation") or ""
                    ),
                    **{
                        name: str(
                            query_requests[name].get("connection_generation") or ""
                        )
                        for name in (
                            "account",
                            "contracts",
                            "orders",
                            "trades",
                            "positions",
                        )
                    },
                }
                full_callbacks_complete = bool(
                    all(query_results.values())
                    and settlement_confirmed.is_set()
                    and snapshot_generations["settlement"] == generation
                )
                if full_callbacks_complete:
                    full_callbacks_complete = _record_snapshot_readiness(
                        connection_lifecycle,
                        generation=generation,
                        snapshot_generations=snapshot_generations,
                        epoch_ns=time.time_ns(),
                    )
            return full_callbacks_complete

        while time.monotonic() < deadline:
            with state_lock:
                generation = str(
                    connection_lifecycle.get("current_connection_generation") or ""
                )
                settlement_generation = str(
                    settlement_response.get("connection_generation") or ""
                )
            if (
                td_api is not None
                and generation
                and generation not in exhausted_snapshot_generations
                and settlement_confirmed.is_set()
                and settlement_generation == generation
                and bool(getattr(td_api, "login_status", False))
            ):
                attempt = snapshot_generation_attempts.get(generation, 0) + 1
                snapshot_generation_attempts[generation] = attempt
                summary["broker_trading_day"] = _clean_ctp_text(
                    td_api.getTradingDay()
                )
                snapshot_complete = run_full_snapshot_cycle(generation)
                if snapshot_complete:
                    if not observe_reconnect:
                        break
                    with state_lock:
                        readiness_restored = bool(
                            connection_lifecycle.get("readiness_restored_epoch_ns")
                        )
                    if readiness_restored:
                        break
                    while time.monotonic() < deadline:
                        with state_lock:
                            same_generation = bool(
                                str(
                                    connection_lifecycle.get(
                                        "current_connection_generation"
                                    )
                                    or ""
                                )
                                == generation
                            )
                        if not same_generation:
                            break
                        time.sleep(
                            min(0.1, max(0.0, deadline - time.monotonic()))
                        )
                elif time.monotonic() + flow_gap_seconds * 4 < deadline:
                    time.sleep(
                        min(flow_gap_seconds, max(0.0, deadline - time.monotonic()))
                    )
                else:
                    exhausted_snapshot_generations.add(generation)
                continue
            time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))

        summary["status"] = "connected_or_attempted_readonly"
        with state_lock:
            log_analysis = _analyze_logs(list(rows["logs"]))
            debug_row_counts = {
                "account_rows": len(rows["accounts"]),
                "position_rows": len(rows["positions"]),
                "order_rows": len(rows["orders"]),
                "trade_rows": len(rows["trades"]),
                "contract_rows": len(rows["contracts"]),
                "log_rows": len(rows["logs"]),
            }
        summary["log_analysis"] = log_analysis
        with state_lock:
            readiness_generation_present = bool(
                connection_lifecycle.get("readiness_generation")
            )
        if readiness_generation_present:
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
                **debug_row_counts,
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
        with state_lock:
            connection_lifecycle["probe_closing"] = 1
        try:
            main_engine.close()
        except Exception as exc:
            summary["close_exception"] = repr(exc)
            summary["status"] = "readonly_close_failed"
        finally:
            ctp_gateway_module.CtpTdApi.onRspQryInvestorPosition = original_position_rsp
            ctp_gateway_module.CtpTdApi.reqSettlementInfoConfirm = original_settlement_request
            ctp_gateway_module.CtpTdApi.onRspSettlementInfoConfirm = original_settlement_rsp
            ctp_gateway_module.CtpTdApi.onRspQryOrder = original_order_query_rsp
            ctp_gateway_module.CtpTdApi.onRspQryTrade = original_trade_query_rsp
            ctp_gateway_module.CtpTdApi.onRspQryTradingAccount = original_account_query_rsp
            ctp_gateway_module.CtpTdApi.onRspQryInstrument = original_contract_query_rsp
            ctp_gateway_module.CtpTdApi.onFrontConnected = original_front_connected
            ctp_gateway_module.CtpTdApi.onFrontDisconnected = original_front_disconnected
        try:
            (
                final_order_api_evidence_window,
                final_order_api_counters,
            ) = _freeze_order_api_evidence(
                state_lock,
                order_api_evidence_window,
                order_api_counters,
            )
            with state_lock:
                final_rows = copy.deepcopy(rows)
                final_query_requests = copy.deepcopy(query_requests)
                final_connection_lifecycle = copy.deepcopy(connection_lifecycle)
                final_settlement_response = copy.deepcopy(settlement_response)
                final_settlement_request = copy.deepcopy(settlement_request)
        finally:
            # Keep every mutation surface fail-closed until all authoritative
            # evidence has been frozen.  Restoring earlier permits a fresh
            # method lookup to bypass both the firewall and exact counters.
            _restore_readonly_order_api_firewall(
                CtpGateway,
                ctp_gateway_module.CtpTdApi,
                order_api_originals,
            )
        result_rows = final_rows
        _publish_order_api_counters(summary, final_order_api_counters)
        summary["order_api_evidence_window"] = final_order_api_evidence_window

        if "log_analysis" not in summary:
            summary["log_analysis"] = _analyze_logs(final_rows["logs"])
        expected_broker_id = os.getenv("CTP_BROKERID", "")
        expected_account_id = os.getenv("CTP_USERID", "")
        broker_trading_day = _clean_ctp_text(
            summary.get("broker_trading_day")
            or getattr(td_api, "getTradingDay", lambda: "")()
        )
        normalized_orders, normalized_trades, join_status = _normalize_query_bundle_rows(
            final_rows["raw_queried_orders"],
            final_rows["raw_queried_trades"],
            generation_uuid=query_generation_uuid,
            ctp_gateway_module=ctp_gateway_module,
        )
        normalized_positions, position_status = _normalize_queried_positions(
            final_rows["raw_queried_positions"],
            generation_uuid=query_generation_uuid,
            broker_trading_day=broker_trading_day,
            ctp_gateway_module=ctp_gateway_module,
        )
        final_rows["orders"] = normalized_orders
        final_rows["trades"] = normalized_trades
        final_rows["positions"] = normalized_positions
        order_query = _query_callback_state(
            final_rows["order_query_callbacks"],
            expected_reqid=final_query_requests["orders"].get("reqid"),
            request_return_code=final_query_requests["orders"].get("return_code"),
            request_sent_at=final_query_requests["orders"].get("request_sent_at"),
        )
        trade_query = _query_callback_state(
            final_rows["trade_query_callbacks"],
            expected_reqid=final_query_requests["trades"].get("reqid"),
            request_return_code=final_query_requests["trades"].get("return_code"),
            request_sent_at=final_query_requests["trades"].get("request_sent_at"),
        )
        position_query = _query_callback_state(
            final_rows["position_query_callbacks"],
            expected_reqid=final_query_requests["positions"].get("reqid"),
            request_return_code=final_query_requests["positions"].get("return_code"),
            request_sent_at=final_query_requests["positions"].get("request_sent_at"),
        )
        position_query.update(position_status)
        account_query = _query_callback_state(
            final_rows["account_query_callbacks"],
            expected_reqid=final_query_requests["account"].get("reqid"),
            request_return_code=final_query_requests["account"].get("return_code"),
            request_sent_at=final_query_requests["account"].get("request_sent_at"),
        )
        contract_query = _query_callback_state(
            final_rows["contract_query_callbacks"],
            expected_reqid=final_query_requests["contracts"].get("reqid"),
            request_return_code=final_query_requests["contracts"].get("return_code"),
            request_sent_at=final_query_requests["contracts"].get("request_sent_at"),
        )
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
        trading_account_response_match = bool(
            final_rows["raw_queried_accounts"]
            and all(
                _clean_ctp_text(row.get("BrokerID")) == expected_broker_id
                and _clean_ctp_text(
                    row.get("AccountID") or row.get("InvestorID")
                )
                == expected_account_id
                for row in final_rows["raw_queried_accounts"]
            )
        )
        readiness_generation = str(
            final_connection_lifecycle.get("readiness_generation") or ""
        )
        snapshot_generations = final_connection_lifecycle.get(
            "snapshot_connection_generations"
        )
        if not isinstance(snapshot_generations, dict):
            snapshot_generations = {}
        full_snapshot_current_generation = bool(
            readiness_generation
            and all(
                str(snapshot_generations.get(name) or "")
                == readiness_generation
                for name in FULL_READINESS_SNAPSHOT_COMPONENTS
            )
        )
        summary["generated_at"] = datetime.now().astimezone().isoformat()
        summary["broker_trading_day"] = broker_trading_day
        summary["settlement_confirmation"] = dict(final_settlement_response)
        summary["settlement_request"] = dict(final_settlement_request)
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
                "trading_account_response_match": trading_account_response_match,
            },
            "queries": {
                "orders": order_query,
                "trades": trade_query,
                "positions": position_query,
                "account": account_query,
                "contracts": contract_query,
            },
            "snapshot_connection_generation": readiness_generation,
            "snapshot_connection_generations": dict(snapshot_generations),
            "full_snapshot_current_generation": full_snapshot_current_generation,
            "trade_order_join_complete": bool(join_status["trade_order_join_complete"]),
            "trade_identity_complete": bool(join_status["trade_identity_complete"]),
            "unmapped_trade_count": int(join_status["unmapped_trade_count"]),
            "unstable_trade_identity_count": int(join_status["unstable_trade_identity_count"]),
            "complete": bool(
                order_query["complete"]
                and trade_query["complete"]
                and position_query["complete"]
                and account_query["complete"]
                and contract_query["complete"]
                and account_query["data_callback_count"] > 0
                and contract_query["data_callback_count"] > 0
                and position_status["position_normalization_complete"]
                and position_status["position_raw_row_count"]
                == position_query["data_callback_count"]
                and summary.get("status") == "readonly_snapshots_received"
                and not summary.get("close_exception")
                and broker_trading_day
                and login_account_match
                and response_account_match
                and trading_account_response_match
                and full_snapshot_current_generation
                and join_status["trade_order_join_complete"]
                and join_status["trade_identity_complete"]
            ),
        }
        summary["connection_lifecycle"] = _finalize_connection_lifecycle(
            final_connection_lifecycle,
            query_requests=final_query_requests,
            query_bundle_complete=bool(summary["broker_query_bundle"]["complete"]),
            order_api_counters=final_order_api_counters,
            restored_epoch_ns=time.time_ns(),
        )
        summary["broker_snapshot"] = _analyze_position_snapshot(
            final_rows, summary["log_analysis"]
        )
        # #region debug-point D:before-close
        _debug_report(
            "D",
            "run_ctp_stage174_readonly_probe.py:_run_probe:finally",
            "[DEBUG] probe closed main_engine and finalized query bundle",
            {
                "status": summary["status"],
                "account_rows": len(final_rows["accounts"]),
                "position_rows": len(final_rows["positions"]),
                "order_rows": len(final_rows["orders"]),
                "trade_rows": len(final_rows["trades"]),
                "contract_rows": len(final_rows["contracts"]),
                "log_rows": len(final_rows["logs"]),
                "position_snapshot_state": summary["broker_snapshot"]["position_snapshot_state"],
                "position_query_callback_rows": len(
                    final_rows["position_query_callbacks"]
                ),
            },
        )
        # #endregion

    return summary | {"rows": result_rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage174 CTP/vn.py read-only probe.")
    parser.add_argument("--connect", action="store_true", help="Actually attempt CTP connection. No orders are sent.")
    parser.add_argument("--wait-seconds", type=int, default=15)
    parser.add_argument("--invocation-id", default="")
    parser.add_argument("--observe-reconnect", action="store_true")
    args = parser.parse_args()

    result = _run_probe(
        connect=bool(args.connect),
        wait_seconds=int(args.wait_seconds),
        observe_reconnect=bool(args.observe_reconnect),
    )
    result["invocation_id"] = str(args.invocation_id).strip()
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
                "account": _query_callback_state([], expected_reqid=None, request_return_code=None),
                "contracts": _query_callback_state([], expected_reqid=None, request_return_code=None),
            },
            "snapshot_connection_generation": "",
            "snapshot_connection_generations": {},
            "full_snapshot_current_generation": False,
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
        for name in ("orders", "trades", "positions", "account", "contracts")
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
        and query_bundle.get("full_snapshot_current_generation") is True
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
