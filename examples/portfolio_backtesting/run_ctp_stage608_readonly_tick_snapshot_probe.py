from __future__ import annotations

import argparse
import importlib.util
import json
import os
import time
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage608 CTP/vn.py read-only tick snapshot probe.")
    parser.add_argument("--connect", action="store_true", help="Actually attempt CTP connection. No orders are sent.")
    parser.add_argument("--wait-seconds", type=int, default=20)
    parser.add_argument("--pre-subscribe-wait-seconds", type=int, default=5)
    parser.add_argument("--submit-plan", type=Path, default=DEFAULT_SUBMIT_PLAN)
    parser.add_argument("--vt-symbol", action="append", default=[], help="Additional vt_symbol to subscribe/read.")
    args = parser.parse_args()

    target_symbols = _load_target_symbols(args.submit_plan, args.vt_symbol)
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
