from __future__ import annotations

import argparse
import importlib.util
import json
import os
import time
import urllib.request
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.event import EVENT_ACCOUNT, EVENT_CONTRACT, EVENT_LOG, EVENT_ORDER, EVENT_POSITION, EVENT_TRADE


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


def _write_df(path: Path, rows: list[dict[str, Any]]) -> None:
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.drop_duplicates().reset_index(drop=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


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


def _run_probe(connect: bool, wait_seconds: int) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
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
    }

    summary: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "connect_requested": connect,
        "wait_seconds": wait_seconds,
        "vnpy_ctp_import_available": import_available,
        "gateway_import": gateway_import,
        "env_status": _env_status(),
        "missing_required_env": _required_env_missing(),
        "real_order_enabled": False,
        "order_api_called": False,
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
        },
    }

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
        # #region debug-point C:account-event
        _debug_report("C", "run_ctp_stage174_readonly_probe.py:on_account", "[DEBUG] account callback received", {"account_rows": len(rows["accounts"])})
        # #endregion

    def on_position(event: Any) -> None:
        rows["positions"].append(_object_to_row(event.data))
        # #region debug-point C:position-event
        _debug_report("C", "run_ctp_stage174_readonly_probe.py:on_position", "[DEBUG] position callback received", {"position_rows": len(rows["positions"])})
        # #endregion

    def on_order(event: Any) -> None:
        rows["orders"].append(_object_to_row(event.data))
        # #region debug-point C:order-event
        _debug_report("C", "run_ctp_stage174_readonly_probe.py:on_order", "[DEBUG] order callback received", {"order_rows": len(rows["orders"])})
        # #endregion

    def on_trade(event: Any) -> None:
        rows["trades"].append(_object_to_row(event.data))
        # #region debug-point C:trade-event
        _debug_report("C", "run_ctp_stage174_readonly_probe.py:on_trade", "[DEBUG] trade callback received", {"trade_rows": len(rows["trades"])})
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

    try:
        # #region debug-point A:before-connect
        _debug_report("A", "run_ctp_stage174_readonly_probe.py:_run_probe:before_connect", "[DEBUG] connecting readonly probe", {"td_address": os.getenv("CTP_TD_ADDRESS", ""), "md_address": os.getenv("CTP_MD_ADDRESS", "")})
        # #endregion
        main_engine.connect(_ctp_setting_from_env(), "CTP")
        # #region debug-point D:after-connect-call
        _debug_report("D", "run_ctp_stage174_readonly_probe.py:_run_probe:after_connect", "[DEBUG] main_engine.connect returned", {"wait_seconds": int(wait_seconds)})
        # #endregion
        time.sleep(max(wait_seconds, 1))
        summary["status"] = "connected_or_attempted_readonly"
        log_analysis = _analyze_logs(rows["logs"])
        summary["log_analysis"] = log_analysis
        if rows["accounts"] or rows["positions"]:
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
        if "log_analysis" not in summary:
            summary["log_analysis"] = _analyze_logs(rows["logs"])
        summary["broker_snapshot"] = _analyze_position_snapshot(rows, summary["log_analysis"])
        # #region debug-point D:before-close
        _debug_report(
            "D",
            "run_ctp_stage174_readonly_probe.py:_run_probe:finally",
            "[DEBUG] probe closing main_engine",
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
        main_engine.close()
        ctp_gateway_module.CtpTdApi.onRspQryInvestorPosition = original_position_rsp

    return summary | {"rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage174 CTP/vn.py read-only probe.")
    parser.add_argument("--connect", action="store_true", help="Actually attempt CTP connection. No orders are sent.")
    parser.add_argument("--wait-seconds", type=int, default=15)
    args = parser.parse_args()

    result = _run_probe(connect=bool(args.connect), wait_seconds=int(args.wait_seconds))
    rows = result.pop("rows")
    _write_df(ACCOUNT_PATH, rows["accounts"])
    _write_df(POSITION_PATH, rows["positions"])
    _write_df(ORDER_PATH, rows["orders"])
    _write_df(TRADE_PATH, rows["trades"])
    _write_df(CONTRACT_PATH, rows["contracts"])
    _write_df(LOG_PATH, rows["logs"])
    _write_df(POSITION_QUERY_CALLBACK_PATH, rows["position_query_callbacks"])
    SUMMARY_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"summary json: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
