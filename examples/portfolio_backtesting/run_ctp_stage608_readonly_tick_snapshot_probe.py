from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import signal
import threading
import time
import uuid
from collections import deque
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from vnpy.event import EventEngine
from vnpy.trader.constant import Exchange
from vnpy.trader.engine import MainEngine
from vnpy.trader.event import EVENT_ACCOUNT, EVENT_CONTRACT, EVENT_LOG, EVENT_ORDER, EVENT_POSITION, EVENT_TICK, EVENT_TRADE
from vnpy.trader.object import SubscribeRequest

from qmt_roll_live_context_adapter import collect_snapshot_from_main_engine


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage608_readonly_tick_snapshot_probe_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage608_readonly_tick_snapshot_probe"
TICK_SNAPSHOT_COMMIT_SCHEMA_VERSION: int = 1


def _snapshot_stream_collections(
    lock: threading.Lock,
    *,
    logs: list[dict[str, Any]],
    tick_buffer: deque[dict[str, Any]],
    latest_by_symbol: dict[str, dict[str, Any]],
    sequence: int,
) -> dict[str, Any]:
    """Copy callback-owned state under one short critical section."""

    with lock:
        copied_ticks = list(tick_buffer)
        published_sequence = max(
            (int(row.get("stream_sequence", 0) or 0) for row in copied_ticks),
            default=0,
        )
        return {
            "logs": list(logs),
            "ticks": copied_ticks,
            "latest_by_symbol": dict(latest_by_symbol),
            # Never advertise a sequence before the same snapshot contains
            # its row; the callback may still be fsyncing the journal outside
            # this lock.
            "sequence": min(int(sequence), published_sequence),
        }


def _symbol_tick_watermarks(
    watched_symbols: list[str],
    latest_by_symbol: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Publish one bounded, durable liveness marker per currently watched symbol."""

    result: dict[str, dict[str, Any]] = {}
    for vt_symbol in sorted({_clean(item) for item in watched_symbols if _clean(item)}):
        row = latest_by_symbol.get(vt_symbol) or {}
        result[vt_symbol] = {
            "received_at": _clean(row.get("received_at")),
            "stream_sequence": int(row.get("stream_sequence", 0) or 0),
            "symbol_stream_sequence": int(
                row.get("symbol_stream_sequence", row.get("stream_sequence", 0))
                or 0
            ),
        }
    return result


SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
ACCOUNT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_accounts_{MODEL_TAG}.csv"
POSITION_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
ORDER_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_orders_{MODEL_TAG}.csv"
TRADE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
CONTRACT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contracts_{MODEL_TAG}.csv"
TICK_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ticks_{MODEL_TAG}.csv"
LOG_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_logs_{MODEL_TAG}.csv"
TARGET_SYMBOL_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_target_symbols_{MODEL_TAG}.csv"
POSITION_QUERY_CALLBACK_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_position_query_callbacks_{MODEL_TAG}.csv"
STREAM_JOURNAL_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tick_stream_{MODEL_TAG}.ndjson"
STREAM_HEARTBEAT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tick_stream_heartbeat_{MODEL_TAG}.json"

DEFAULT_SUBMIT_PLAN = OUTPUT_DIR / (
    "qmt_roll_stage591_stage526_bridge_submit_adapter_dry_run_"
    "submit_plan_stage591_stage526_bridge_submit_adapter_dry_run_v1.csv"
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


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _split_vt_symbol(vt_symbol: str) -> tuple[str, Exchange] | None:
    if "." not in vt_symbol:
        return None
    symbol, exchange_text = vt_symbol.rsplit(".", 1)
    symbol = symbol.strip()
    exchange_text = exchange_text.strip()
    if not symbol or not exchange_text:
        return None
    try:
        return symbol, Exchange(exchange_text)
    except ValueError:
        return None


def _load_target_symbols(submit_plan: Path | None, cli_symbols: list[str]) -> list[str]:
    symbols: list[str] = []
    for item in cli_symbols:
        text = _clean(item)
        if text:
            symbols.append(text)
    if submit_plan and submit_plan.exists():
        frame = pd.read_csv(submit_plan, encoding="utf-8-sig")
        if "vt_symbol" in frame.columns:
            for item in frame["vt_symbol"].dropna().astype(str):
                text = _clean(item)
                if text:
                    symbols.append(text)
    seen: set[str] = set()
    result: list[str] = []
    for symbol in symbols:
        if symbol not in seen:
            result.append(symbol)
            seen.add(symbol)
    return result


def _object_to_row(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if is_dataclass(obj):
        row = asdict(obj)
    elif hasattr(obj, "__dict__"):
        row = dict(obj.__dict__)
    else:
        row = {"value": str(obj)}
    for attr in ["vt_symbol", "vt_orderid", "vt_tradeid", "vt_positionid", "vt_accountid", "available"]:
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
    row.setdefault("snapshot_at", datetime.now().isoformat())
    return row


def _write_df(path: Path, rows: list[dict[str, Any]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


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
    """Durably publish one complete artifact before its commit record."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    _fsync_parent(path)


def _atomic_write_text(path: Path, text: str) -> None:
    """Publish a complete file so readers never observe a partial snapshot."""

    _atomic_write_bytes(path, text.encode("utf-8"))


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _atomic_write_df(path: Path, rows: list[dict[str, Any]]) -> None:
    _atomic_write_bytes(path, _dataframe_csv_bytes(rows))


def _dataframe_csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    """Serialize once so the commit hash covers the exact bytes readers parse."""

    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")


def _publish_tick_snapshot_commit(
    *,
    tick_path: Path,
    heartbeat_path: Path,
    tick_rows: list[dict[str, Any]],
    heartbeat: dict[str, Any],
) -> dict[str, Any]:
    """Publish tick bytes first and the matching heartbeat commit last.

    Atomic rename protects each individual file.  The generation and exact
    byte hash let Stage904 distinguish a normal two-file publication window
    from a real ring-buffer gap, without trusting write order alone.
    """

    tick_bytes = _dataframe_csv_bytes(tick_rows)
    generation_uuid = str(uuid.uuid4())
    commit = {
        "schema_version": TICK_SNAPSHOT_COMMIT_SCHEMA_VERSION,
        "generation_uuid": generation_uuid,
        "sha256": hashlib.sha256(tick_bytes).hexdigest(),
        "row_count": len(tick_rows),
        "feed_session_id": _clean(heartbeat.get("feed_session_id")),
        "stream_sequence": int(heartbeat.get("stream_sequence", 0) or 0),
    }
    committed_heartbeat = {
        **heartbeat,
        "tick_snapshot_commit": commit,
        "tick_snapshot_generation_uuid": generation_uuid,
        # Every authoritative heartbeat mutation is one snapshot revision.
        # Alternate writers must either publish a new committed generation or
        # remove the commit entirely; reusing this revision is never valid.
        "heartbeat_revision_uuid": generation_uuid,
    }
    _atomic_write_bytes(tick_path, tick_bytes)
    # This is the commit point.  Never move it before the tick artifact.
    _atomic_write_json(heartbeat_path, committed_heartbeat)
    return committed_heartbeat


def _append_ndjson(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n")
        handle.flush()
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _stream_tick_row(
    tick: Any,
    *,
    feed_session_id: str,
    stream_sequence: int,
    symbol_stream_sequence: int | None = None,
    received_at: datetime | None = None,
) -> dict[str, Any]:
    now = received_at or datetime.now()
    exchange_dt = getattr(tick, "datetime", None)
    return {
        "feed_session_id": feed_session_id,
        "stream_sequence": int(stream_sequence),
        # Global sequence remains an audit identity.  Reducers consume this
        # per-symbol sequence so normal JM/RB/JM interleaving is not mistaken
        # for a lost JM event.
        "symbol_stream_sequence": int(
            stream_sequence
            if symbol_stream_sequence is None
            else symbol_stream_sequence
        ),
        "received_at": now.isoformat(timespec="microseconds"),
        "exchange_datetime": exchange_dt.isoformat() if isinstance(exchange_dt, datetime) else _clean(exchange_dt),
        "vt_symbol": _clean(getattr(tick, "vt_symbol", "")),
        "symbol": _clean(getattr(tick, "symbol", "")),
        "exchange": _clean(getattr(getattr(tick, "exchange", ""), "value", getattr(tick, "exchange", ""))),
        "last_price": getattr(tick, "last_price", 0.0),
        "bid_price_1": getattr(tick, "bid_price_1", 0.0),
        "ask_price_1": getattr(tick, "ask_price_1", 0.0),
        "bid_volume_1": getattr(tick, "bid_volume_1", 0.0),
        "ask_volume_1": getattr(tick, "ask_volume_1", 0.0),
        "limit_up": getattr(tick, "limit_up", 0.0),
        "limit_down": getattr(tick, "limit_down", 0.0),
    }


def _manifest_symbols(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []
    try:
        if path.suffix.lower() == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            values = payload.get("symbols", payload.get("vt_symbols", [])) if isinstance(payload, dict) else payload
            return [_clean(item) for item in values if _clean(item)] if isinstance(values, list) else []
        if path.suffix.lower() == ".csv":
            frame = pd.read_csv(path, encoding="utf-8-sig")
            column = "vt_symbol" if "vt_symbol" in frame.columns else "symbol" if "symbol" in frame.columns else ""
            return [_clean(item) for item in frame[column].tolist() if _clean(item)] if column else []
        return [_clean(line) for line in path.read_text(encoding="utf-8").splitlines() if _clean(line)]
    except Exception:
        return []


def _append_unique(rows: list[dict[str, Any]], new_rows: list[dict[str, Any]], key_fields: list[str]) -> None:
    seen = {tuple(str(row.get(field, "")) for field in key_fields) for row in rows}
    for row in new_rows:
        key = tuple(str(row.get(field, "")) for field in key_fields)
        if key in seen:
            continue
        rows.append(row)
        seen.add(key)


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
        "td_disconnected_after_connect": False,
        "md_disconnected_after_connect": False,
        "status_hint": "no_logs",
    }
    for message in messages:
        if "交易服务器连接成功" in message:
            analysis["td_connected"] = True
            analysis["td_disconnected_after_connect"] = False
        if "行情服务器连接成功" in message:
            analysis["md_connected"] = True
            analysis["md_disconnected_after_connect"] = False
        if "交易服务器授权验证成功" in message:
            analysis["td_auth_success"] = True
        if "行情服务器登录成功" in message:
            analysis["md_login_success"] = True
        if "交易服务器登录成功" in message:
            analysis["td_login_success"] = True
        if "交易服务器登录失败" in message:
            analysis["td_login_failed"] = True
            analysis["td_login_failed_message"] = message
        if "交易服务器连接断开" in message:
            analysis["td_connected"] = False
            analysis["td_login_success"] = False
            analysis["td_disconnected_after_connect"] = True
        if "行情服务器连接断开" in message:
            analysis["md_connected"] = False
            analysis["md_login_success"] = False
            analysis["md_disconnected_after_connect"] = True
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
    callbacks = rows.get("position_query_callbacks", [])
    position_rows = rows.get("positions", [])
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
    elif last_seen and log_analysis.get("td_login_success"):
        state = "confirmed_flat"
    elif last_seen and data_callbacks and not position_rows:
        state = "position_payload_without_position_rows"
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


def _run_probe(connect: bool, wait_seconds: int, pre_subscribe_wait_seconds: int, target_symbols: list[str]) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    gateway_import = _gateway_import_status()
    import_available = bool(gateway_import["ctp_gateway_import_available"])
    rows: dict[str, list[dict[str, Any]]] = {
        "accounts": [],
        "positions": [],
        "orders": [],
        "trades": [],
        "contracts": [],
        "ticks": [],
        "logs": [],
        "position_query_callbacks": [],
    }
    summary: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "connect_requested": connect,
        "wait_seconds": wait_seconds,
        "pre_subscribe_wait_seconds": pre_subscribe_wait_seconds,
        "target_symbols": target_symbols,
        "target_symbol_count": len(target_symbols),
        "vnpy_ctp_import_available": import_available,
        "gateway_import": gateway_import,
        "env_status": _env_status(),
        "missing_required_env": _required_env_missing(),
        "real_order_enabled": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "subscribe_api_called_count": 0,
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
            "ticks": str(TICK_PATH),
            "logs": str(LOG_PATH),
            "target_symbols": str(TARGET_SYMBOL_PATH),
            "position_query_callbacks": str(POSITION_QUERY_CALLBACK_PATH),
        },
    }
    if not connect:
        return summary | {"rows": rows}
    if not import_available:
        summary["status"] = "blocked_missing_vnpy_ctp"
        return summary | {"rows": rows}
    missing = _required_env_missing()
    if missing:
        summary["status"] = "blocked_missing_env"
        return summary | {"rows": rows}

    from vnpy_ctp import CtpGateway
    from vnpy_ctp.gateway import ctp_gateway as ctp_gateway_module

    original_position_rsp = ctp_gateway_module.CtpTdApi.onRspQryInvestorPosition

    def instrumented_position_rsp(self: Any, data: dict, error: dict, reqid: int, last: bool) -> None:
        rows["position_query_callbacks"].append(
            {
                "reqid": reqid,
                "last": bool(last),
                "has_data": bool(data),
                "instrument": str(data.get("InstrumentID", "")) if isinstance(data, dict) else "",
                "position": data.get("Position", "") if isinstance(data, dict) else "",
                "error_id": error.get("ErrorID", 0) if isinstance(error, dict) else 0,
                "error_msg": error.get("ErrorMsg", "") if isinstance(error, dict) else "",
                "received_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        return original_position_rsp(self, data, error, reqid, last)

    ctp_gateway_module.CtpTdApi.onRspQryInvestorPosition = instrumented_position_rsp
    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    main_engine.add_gateway(CtpGateway)

    def on_account(event: Any) -> None:
        rows["accounts"].append(_object_to_row(event.data))

    def on_position(event: Any) -> None:
        rows["positions"].append(_object_to_row(event.data))

    def on_order(event: Any) -> None:
        rows["orders"].append(_object_to_row(event.data))

    def on_trade(event: Any) -> None:
        rows["trades"].append(_object_to_row(event.data))

    def on_contract(event: Any) -> None:
        rows["contracts"].append(_object_to_row(event.data))

    def on_tick(event: Any) -> None:
        rows["ticks"].append(_object_to_row(event.data))

    def on_log(event: Any) -> None:
        rows["logs"].append(_object_to_row(event.data))

    event_engine.register(EVENT_ACCOUNT, on_account)
    event_engine.register(EVENT_POSITION, on_position)
    event_engine.register(EVENT_ORDER, on_order)
    event_engine.register(EVENT_TRADE, on_trade)
    event_engine.register(EVENT_CONTRACT, on_contract)
    event_engine.register(EVENT_TICK, on_tick)
    event_engine.register(EVENT_LOG, on_log)

    try:
        main_engine.connect(_ctp_setting_from_env(), "CTP")
        time.sleep(max(pre_subscribe_wait_seconds, 0))
        subscribed: list[str] = []
        invalid: list[str] = []
        for vt_symbol in target_symbols:
            parsed = _split_vt_symbol(vt_symbol)
            if parsed is None:
                invalid.append(vt_symbol)
                continue
            symbol, exchange = parsed
            main_engine.subscribe(SubscribeRequest(symbol=symbol, exchange=exchange), "CTP")
            summary["subscribe_api_called_count"] += 1
            subscribed.append(vt_symbol)
        summary["subscribed_symbols"] = subscribed
        summary["invalid_symbols"] = invalid
        time.sleep(max(wait_seconds, 1))
        cache_snapshot = collect_snapshot_from_main_engine(main_engine, target_symbols)
        _append_unique(rows["contracts"], cache_snapshot.get("contracts", []), ["vt_symbol"])
        _append_unique(rows["ticks"], cache_snapshot.get("ticks", []), ["vt_symbol"])
        _append_unique(rows["accounts"], cache_snapshot.get("accounts", []), ["vt_accountid"])
        _append_unique(rows["positions"], cache_snapshot.get("positions", []), ["vt_positionid"])
        log_analysis = _analyze_logs(rows["logs"])
        summary["log_analysis"] = log_analysis
        summary["status"] = "connected_or_attempted_readonly_tick_snapshot"
        if rows["ticks"]:
            summary["status"] = "readonly_tick_snapshots_received"
        elif log_analysis["status_hint"] == "trading_login_failed":
            summary["status"] = "readonly_trading_login_failed"
            summary["failure_reason"] = log_analysis["td_login_failed_message"]
        elif log_analysis["status_hint"] == "connected_but_no_trading_login_outcome":
            summary["status"] = "readonly_connected_no_login_outcome"
        elif log_analysis["status_hint"] == "logs_present_without_ctp_progress":
            summary["status"] = "readonly_logs_without_ctp_progress"
    except Exception as exc:
        summary["status"] = "connect_exception"
        summary["exception"] = repr(exc)
    finally:
        if "log_analysis" not in summary:
            summary["log_analysis"] = _analyze_logs(rows["logs"])
        summary["broker_snapshot"] = _analyze_position_snapshot(rows, summary["log_analysis"])
        summary["row_counts"] = {key: len(value) for key, value in rows.items()}
        main_engine.close()
        ctp_gateway_module.CtpTdApi.onRspQryInvestorPosition = original_position_rsp
    return summary | {"rows": rows}


def _run_stream(
    *,
    connect: bool,
    pre_subscribe_wait_seconds: int,
    target_symbols: list[str],
    watch_manifest: Path | None,
    journal_path: Path,
    heartbeat_path: Path,
    duration_seconds: int,
    heartbeat_seconds: float,
    max_buffer_ticks: int,
    parent_pid: int = 0,
) -> dict[str, Any]:
    """Keep one read-only market-data connection alive and journal ticks in arrival order."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    feed_session_id = f"{datetime.now():%Y%m%dT%H%M%S}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    gateway_import = _gateway_import_status()
    summary: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "mode": "continuous_tick_stream",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "feed_session_id": feed_session_id,
        "feed_started_at": datetime.now().isoformat(timespec="microseconds"),
        "connect_requested": bool(connect),
        "target_symbols": list(target_symbols),
        "watch_manifest": str(watch_manifest.resolve()) if watch_manifest else "",
        "journal_path": str(journal_path.resolve()),
        "heartbeat_path": str(heartbeat_path.resolve()),
        "tick_snapshot_path": str(TICK_PATH.resolve()),
        "duration_seconds": int(duration_seconds),
        "parent_pid": int(parent_pid),
        "real_order_enabled": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "subscribe_api_called_count": 0,
        "status": "stream_dry_run_not_connected",
        "gateway_import": gateway_import,
        "env_status": _env_status(),
        "missing_required_env": _required_env_missing(),
    }
    if not connect:
        _atomic_write_json(heartbeat_path, {**summary, "stream_ready": False, "stopped": True})
        return summary
    if not gateway_import.get("ctp_gateway_import_available"):
        summary["status"] = "stream_blocked_missing_vnpy_ctp"
        _atomic_write_json(heartbeat_path, {**summary, "stream_ready": False, "stopped": True})
        return summary
    if summary["missing_required_env"]:
        summary["status"] = "stream_blocked_missing_env"
        _atomic_write_json(heartbeat_path, {**summary, "stream_ready": False, "stopped": True})
        return summary

    from vnpy_ctp import CtpGateway

    rows: dict[str, list[dict[str, Any]]] = {"logs": []}
    tick_buffer: deque[dict[str, Any]] = deque(maxlen=max(1, int(max_buffer_ticks)))
    latest_by_symbol: dict[str, dict[str, Any]] = {}
    symbol_sequence_by_symbol: dict[str, int] = {}
    subscribed: set[str] = set()
    subscribed_at_by_symbol: dict[str, str] = {}
    invalid: set[str] = set()
    sequence = 0
    stream_state_lock = threading.Lock()
    stop_requested = False
    started_monotonic = time.monotonic()
    last_heartbeat_monotonic = 0.0

    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    main_engine.add_gateway(CtpGateway)

    def on_log(event: Any) -> None:
        with stream_state_lock:
            rows["logs"].append(_object_to_row(event.data))
            if len(rows["logs"]) > 500:
                del rows["logs"][:-500]

    def on_tick(event: Any) -> None:
        nonlocal sequence
        vt_symbol = _clean(getattr(event.data, "vt_symbol", ""))
        with stream_state_lock:
            sequence += 1
            current_sequence = sequence
            current_symbol_sequence = 0
            if vt_symbol:
                current_symbol_sequence = symbol_sequence_by_symbol.get(vt_symbol, 0) + 1
                symbol_sequence_by_symbol[vt_symbol] = current_symbol_sequence
        row = _stream_tick_row(
            event.data,
            feed_session_id=feed_session_id,
            stream_sequence=current_sequence,
            symbol_stream_sequence=current_symbol_sequence,
        )
        if not row["vt_symbol"]:
            return
        _append_ndjson(journal_path, row)
        with stream_state_lock:
            tick_buffer.append(row)
            latest_by_symbol[row["vt_symbol"]] = row

    event_engine.register(EVENT_LOG, on_log)
    event_engine.register(EVENT_TICK, on_tick)

    old_sigterm = signal.getsignal(signal.SIGTERM)
    old_sigint = signal.getsignal(signal.SIGINT)

    def request_stop(_signum: int, _frame: Any) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    def subscribe_new() -> None:
        desired = list(target_symbols) + _manifest_symbols(watch_manifest)
        seen: set[str] = set()
        for vt_symbol in desired:
            vt_symbol = _clean(vt_symbol)
            if not vt_symbol or vt_symbol in seen:
                continue
            seen.add(vt_symbol)
            if vt_symbol in subscribed or vt_symbol in invalid:
                continue
            parsed = _split_vt_symbol(vt_symbol)
            if parsed is None:
                invalid.add(vt_symbol)
                continue
            symbol, exchange = parsed
            main_engine.subscribe(SubscribeRequest(symbol=symbol, exchange=exchange), "CTP")
            summary["subscribe_api_called_count"] += 1
            subscribed.add(vt_symbol)
            subscribed_at_by_symbol[vt_symbol] = datetime.now().isoformat(timespec="microseconds")

    def publish_heartbeat(*, stopped: bool = False) -> dict[str, Any]:
        snapshot = _snapshot_stream_collections(
            stream_state_lock,
            logs=rows["logs"],
            tick_buffer=tick_buffer,
            latest_by_symbol=latest_by_symbol,
            sequence=sequence,
        )
        snapshot_latest = snapshot["latest_by_symbol"]
        snapshot_ticks = snapshot["ticks"]
        snapshot_sequence = int(snapshot["sequence"])
        log_analysis = _analyze_logs(snapshot["logs"])
        desired = set(target_symbols) | set(_manifest_symbols(watch_manifest))
        expected = sorted(item for item in desired if item and item not in invalid)
        missing_tick_symbols = sorted(item for item in expected if item not in snapshot_latest)
        published_latest = {
            vt_symbol: snapshot_latest[vt_symbol]
            for vt_symbol in expected
            if vt_symbol in snapshot_latest
        }
        symbol_tick_watermarks = _symbol_tick_watermarks(expected, published_latest)
        transport_ready = bool(log_analysis.get("md_login_success") and not stopped)
        ready = bool(transport_ready and expected and not missing_tick_symbols)
        latest_received_at = max(
            (_clean(row.get("received_at")) for row in published_latest.values()),
            default="",
        )
        heartbeat = {
            **summary,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "tick_stream_ready" if ready else "tick_stream_stopped" if stopped else "tick_stream_waiting_for_market_data",
            "stream_ready": ready,
            "transport_ready": transport_ready,
            "stopped": bool(stopped),
            "pid": os.getpid(),
            "stream_sequence": snapshot_sequence,
            "journal_tick_count": snapshot_sequence,
            "buffered_tick_count": len(snapshot_ticks),
            "subscribed_symbols": sorted(subscribed),
            "subscribed_at_by_symbol": subscribed_at_by_symbol,
            "invalid_symbols": sorted(invalid),
            "missing_tick_symbols": missing_tick_symbols,
            "latest_tick_received_at": latest_received_at,
            # Both maps are bounded to the current watch set.  The compact
            # watermark map is the authoritative per-symbol liveness contract
            # consumed by Stage904; latest_ticks remains diagnostic only.
            "symbol_tick_watermarks": symbol_tick_watermarks,
            "latest_ticks": published_latest,
            "log_analysis": log_analysis,
            "uptime_seconds": round(time.monotonic() - started_monotonic, 3),
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
            "order_api_called_count": 0,
        }
        return _publish_tick_snapshot_commit(
            tick_path=TICK_PATH,
            heartbeat_path=heartbeat_path,
            tick_rows=snapshot_ticks,
            heartbeat=heartbeat,
        )

    final_heartbeat: dict[str, Any] = {}
    try:
        main_engine.connect(_ctp_setting_from_env(), "CTP")
        deadline = time.monotonic() + max(0, int(pre_subscribe_wait_seconds))
        while time.monotonic() < deadline and not stop_requested:
            time.sleep(0.1)
        subscribe_new()
        summary["status"] = "tick_stream_running"
        while not stop_requested:
            now_monotonic = time.monotonic()
            if parent_pid > 0:
                try:
                    os.kill(parent_pid, 0)
                except ProcessLookupError:
                    summary["status"] = "tick_stream_parent_exited"
                    break
            if duration_seconds > 0 and now_monotonic - started_monotonic >= duration_seconds:
                break
            if now_monotonic - last_heartbeat_monotonic >= max(0.2, float(heartbeat_seconds)):
                subscribe_new()
                final_heartbeat = publish_heartbeat()
                last_heartbeat_monotonic = now_monotonic
            time.sleep(0.05)
    except Exception as exc:
        summary["status"] = "tick_stream_exception"
        summary["exception"] = repr(exc)
    finally:
        try:
            final_heartbeat = publish_heartbeat(stopped=True)
        finally:
            main_engine.close()
            signal.signal(signal.SIGTERM, old_sigterm)
            signal.signal(signal.SIGINT, old_sigint)
    return {
        **summary,
        "status": _clean(final_heartbeat.get("status")) or summary["status"],
        "stopped": True,
        "stream_sequence": sequence,
        "journal_tick_count": sequence,
        "subscribed_symbols": sorted(subscribed),
        "invalid_symbols": sorted(invalid),
        "latest_tick_received_at": final_heartbeat.get("latest_tick_received_at", ""),
        "order_api_called_count": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage608 CTP/vn.py read-only tick snapshot probe.")
    parser.add_argument("--connect", action="store_true", help="Actually attempt CTP connection. No orders are sent.")
    parser.add_argument("--stream", action="store_true", help="Keep one read-only market-data session alive and append ordered ticks.")
    parser.add_argument("--wait-seconds", type=int, default=20)
    parser.add_argument("--pre-subscribe-wait-seconds", type=int, default=5)
    parser.add_argument("--submit-plan", type=Path, default=DEFAULT_SUBMIT_PLAN)
    parser.add_argument("--vt-symbol", action="append", default=[], help="Additional vt_symbol to subscribe/read.")
    parser.add_argument("--watch-manifest", type=Path, default=None, help="Optional JSON/CSV/text symbol manifest reread while streaming.")
    parser.add_argument("--journal-path", type=Path, default=STREAM_JOURNAL_PATH)
    parser.add_argument("--heartbeat-path", type=Path, default=STREAM_HEARTBEAT_PATH)
    parser.add_argument("--duration-seconds", type=int, default=0, help="0 means run until SIGTERM/SIGINT.")
    parser.add_argument("--heartbeat-seconds", type=float, default=1.0)
    parser.add_argument("--max-buffer-ticks", type=int, default=2000)
    parser.add_argument("--parent-pid", type=int, default=0, help="Exit when this owning daemon process no longer exists.")
    args = parser.parse_args()

    target_symbols = _load_target_symbols(args.submit_plan, args.vt_symbol)
    if args.stream:
        result = _run_stream(
            connect=bool(args.connect),
            pre_subscribe_wait_seconds=int(args.pre_subscribe_wait_seconds),
            target_symbols=target_symbols,
            watch_manifest=args.watch_manifest,
            journal_path=args.journal_path,
            heartbeat_path=args.heartbeat_path,
            duration_seconds=int(args.duration_seconds),
            heartbeat_seconds=float(args.heartbeat_seconds),
            max_buffer_ticks=int(args.max_buffer_ticks),
            parent_pid=int(args.parent_pid),
        )
        _atomic_write_df(TARGET_SYMBOL_PATH, [{"vt_symbol": item} for item in target_symbols])
        _atomic_write_json(SUMMARY_PATH, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"summary json: {SUMMARY_PATH}")
        return
    result = _run_probe(
        connect=bool(args.connect),
        wait_seconds=int(args.wait_seconds),
        pre_subscribe_wait_seconds=int(args.pre_subscribe_wait_seconds),
        target_symbols=target_symbols,
    )
    rows = result.pop("rows")
    _write_df(ACCOUNT_PATH, rows["accounts"])
    _write_df(POSITION_PATH, rows["positions"])
    _write_df(ORDER_PATH, rows["orders"])
    _write_df(TRADE_PATH, rows["trades"])
    _write_df(CONTRACT_PATH, rows["contracts"])
    _write_df(TICK_PATH, rows["ticks"])
    _write_df(LOG_PATH, rows["logs"])
    _write_df(POSITION_QUERY_CALLBACK_PATH, rows["position_query_callbacks"])
    _write_df(TARGET_SYMBOL_PATH, [{"vt_symbol": item} for item in target_symbols])
    SUMMARY_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"summary json: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
