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


def _object_to_row(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if is_dataclass(obj):
        row = asdict(obj)
    elif hasattr(obj, "__dict__"):
        row = dict(obj.__dict__)
    else:
        row = {"value": str(obj)}
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
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _run_probe(connect: bool, wait_seconds: int) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    gateway_import = _gateway_import_status()
    import_available = bool(gateway_import["ctp_gateway_import_available"])
    rows: dict[str, list[dict[str, Any]]] = {
        "accounts": [],
        "positions": [],
        "orders": [],
        "trades": [],
        "contracts": [],
        "logs": [],
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
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "accounts": str(ACCOUNT_PATH),
            "positions": str(POSITION_PATH),
            "orders": str(ORDER_PATH),
            "trades": str(TRADE_PATH),
            "contracts": str(CONTRACT_PATH),
            "logs": str(LOG_PATH),
        },
    }

    if not connect:
        summary["status"] = "dry_run_not_connected"
        return summary | {"rows": rows}

    if not import_available:
        summary["status"] = "blocked_missing_vnpy_ctp"
        return summary | {"rows": rows}

    missing = _required_env_missing()
    if missing:
        summary["status"] = "blocked_missing_env"
        return summary | {"rows": rows}

    from vnpy_ctp import CtpGateway

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

    def on_log(event: Any) -> None:
        rows["logs"].append(_object_to_row(event.data))

    event_engine.register(EVENT_ACCOUNT, on_account)
    event_engine.register(EVENT_POSITION, on_position)
    event_engine.register(EVENT_ORDER, on_order)
    event_engine.register(EVENT_TRADE, on_trade)
    event_engine.register(EVENT_CONTRACT, on_contract)
    event_engine.register(EVENT_LOG, on_log)

    try:
        main_engine.connect(_ctp_setting_from_env(), "CTP")
        time.sleep(max(wait_seconds, 1))
        summary["status"] = "connected_or_attempted_readonly"
    except Exception as exc:
        summary["status"] = "connect_exception"
        summary["exception"] = repr(exc)
    finally:
        main_engine.close()

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
    SUMMARY_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"summary json: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
