#!/usr/bin/env python3
"""Stage655: read-only raw CTP account margin probe.

This probe deliberately bypasses vn.py's generic AccountData conversion because
vnpy_ctp does not persist CTP CurrMargin into AccountData. It authenticates,
logs in, confirms settlement, and queries trading account/positions only when
called with --connect. It never sends or cancels orders.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from vnpy_ctp.api import TdApi
    TDAPI_IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - depends on local CTP framework install
    TdApi = object  # type: ignore[assignment,misc]
    TDAPI_IMPORT_ERROR = repr(exc)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage655_readonly_account_margin_probe_v1"
OUTPUT_PREFIX = "qmt_roll_stage655_readonly_account_margin_probe"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
ACCOUNT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_accounts_{MODEL_TAG}.csv"
POSITION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
LOG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_logs_{MODEL_TAG}.csv"

CTP_ENV_KEYS = {
    "userid": "CTP_USERID",
    "password": "CTP_PASSWORD",
    "brokerid": "CTP_BROKERID",
    "td_address": "CTP_TD_ADDRESS",
    "appid": "CTP_APPID",
    "auth_code": "CTP_AUTH_CODE",
    "product_info": "CTP_PRODUCT_INFO",
}

RAW_ACCOUNT_FIELDS = [
    "AccountID",
    "Balance",
    "Available",
    "CurrMargin",
    "FrozenMargin",
    "FrozenCash",
    "FrozenCommission",
    "CloseProfit",
    "PositionProfit",
    "Commission",
    "PreBalance",
    "Deposit",
    "Withdraw",
]


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
    required = ["userid", "password", "brokerid", "td_address", "appid", "auth_code"]
    return [CTP_ENV_KEYS[name] for name in required if not os.getenv(CTP_ENV_KEYS[name], "")]


def _env_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env: {name}")
    return value


def _error_text(error: dict[str, Any] | None) -> str:
    if not error:
        return "ErrorID=0 ErrorMsg="
    return f"ErrorID={error.get('ErrorID')} ErrorMsg={error.get('ErrorMsg')}"


def _clean_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return value


def _write_df(path: Path, rows: list[dict[str, Any]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


class RawAccountMarginProbe(TdApi):
    def __init__(self, *, wait_seconds: int, hard_exit_on_finish: bool = False) -> None:
        super().__init__()
        self.wait_seconds = wait_seconds
        self.hard_exit_on_finish = hard_exit_on_finish
        self.reqid = 0
        self.done = False
        self.front_connected = False
        self.auth_ok = False
        self.login_ok = False
        self.settlement_ok = False
        self.account_rows: list[dict[str, Any]] = []
        self.position_rows: list[dict[str, Any]] = []
        self.log_rows: list[dict[str, Any]] = []
        self.start = time.time()

        self.userid = _env_required("CTP_USERID")
        self.password = _env_required("CTP_PASSWORD")
        self.brokerid = _env_required("CTP_BROKERID")
        self.td_address = _env_required("CTP_TD_ADDRESS")
        self.appid = _env_required("CTP_APPID")
        self.auth_code = _env_required("CTP_AUTH_CODE")
        self.product_info = os.environ.get("CTP_PRODUCT_INFO", "")

    def next_reqid(self) -> int:
        self.reqid += 1
        return self.reqid

    def log(self, msg: str) -> None:
        row = {
            "elapsed_seconds": round(time.time() - self.start, 3),
            "logged_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message": msg,
        }
        self.log_rows.append(row)
        print(f"[{row['elapsed_seconds']:7.2f}s] {msg}", flush=True)

    def start_probe(self) -> None:
        flow_dir = Path("/private/tmp/stage655_ctp_readonly_account_margin_flow")
        td_flow_dir = flow_dir / "Td"
        td_flow_dir.mkdir(parents=True, exist_ok=True)
        flow_path = (str(td_flow_dir) + os.sep).encode("GBK", errors="ignore")

        self.log("read-only raw account margin probe starting")
        self.createFtdcTraderApi(flow_path)
        self.subscribePrivateTopic(0)
        self.subscribePublicTopic(0)
        self.registerFront(self.td_address)
        self.init()

        deadline = time.time() + self.wait_seconds
        while time.time() < deadline and not self.done:
            time.sleep(0.2)

        self.log(
            "summary "
            f"front_connected={self.front_connected} auth_ok={self.auth_ok} "
            f"login_ok={self.login_ok} settlement_ok={self.settlement_ok} "
            f"account_rows={len(self.account_rows)} position_rows={len(self.position_rows)}"
        )
        if self.hard_exit_on_finish:
            self.persist_and_hard_exit()

    def persist_and_hard_exit(self) -> None:
        summary = {
            "model_tag": MODEL_TAG,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "connect_requested": True,
            "wait_seconds": self.wait_seconds,
            "env_status": _env_status(),
            "missing_required_env": _required_env_missing(),
            "tdapi_import_available": not bool(TDAPI_IMPORT_ERROR),
            "tdapi_import_error": TDAPI_IMPORT_ERROR,
            "raw_account_fields": RAW_ACCOUNT_FIELDS,
            "real_order_enabled": False,
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
            "status": "readonly_account_margin_received" if self.account_rows else "readonly_no_account_margin_received",
            "outputs": {
                "summary": str(SUMMARY_PATH),
                "accounts": str(ACCOUNT_PATH),
                "positions": str(POSITION_PATH),
                "logs": str(LOG_PATH),
            },
            "front_connected": self.front_connected,
            "auth_ok": self.auth_ok,
            "login_ok": self.login_ok,
            "settlement_ok": self.settlement_ok,
            "account_rows": len(self.account_rows),
            "position_rows": len(self.position_rows),
            "explicit_margin_rows": sum(1 for row in self.account_rows if row.get("curr_margin") not in {"", None}),
        }
        _write_df(ACCOUNT_PATH, self.account_rows)
        _write_df(POSITION_PATH, self.position_rows)
        _write_df(LOG_PATH, self.log_rows)
        SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"summary json: {SUMMARY_PATH}")
        sys.stdout.flush()
        sys.stderr.flush()
        if self.account_rows:
            exit_code = 0
        elif self.front_connected:
            exit_code = 3
        else:
            exit_code = 4
        os._exit(exit_code)

    def onFrontConnected(self) -> None:
        self.front_connected = True
        self.log("onFrontConnected")
        req = {
            "UserID": self.userid,
            "BrokerID": self.brokerid,
            "AuthCode": self.auth_code,
            "AppID": self.appid,
        }
        if self.product_info:
            req["UserProductInfo"] = self.product_info
        ret = self.reqAuthenticate(req, self.next_reqid())
        self.log(f"reqAuthenticate ret={ret}")

    def onFrontDisconnected(self, reason: int) -> None:
        self.log(f"onFrontDisconnected reason={reason}")
        self.done = True

    def onRspAuthenticate(self, data: dict, error: dict, reqid: int, last: bool) -> None:
        self.log(f"onRspAuthenticate reqid={reqid} last={last} {_error_text(error)}")
        if error and error.get("ErrorID"):
            self.done = True
            return
        self.auth_ok = True
        req = {
            "UserID": self.userid,
            "Password": self.password,
            "BrokerID": self.brokerid,
        }
        ret = self.reqUserLogin(req, self.next_reqid())
        self.log(f"reqUserLogin ret={ret}")

    def onRspUserLogin(self, data: dict, error: dict, reqid: int, last: bool) -> None:
        self.log(f"onRspUserLogin reqid={reqid} last={last} {_error_text(error)}")
        if error and error.get("ErrorID"):
            self.done = True
            return
        self.login_ok = True
        ret = self.reqSettlementInfoConfirm(
            {"BrokerID": self.brokerid, "InvestorID": self.userid},
            self.next_reqid(),
        )
        self.log(f"reqSettlementInfoConfirm ret={ret}")

    def onRspSettlementInfoConfirm(self, data: dict, error: dict, reqid: int, last: bool) -> None:
        self.log(f"onRspSettlementInfoConfirm reqid={reqid} last={last} {_error_text(error)}")
        if error and error.get("ErrorID"):
            self.done = True
            return
        self.settlement_ok = True
        account_ret = self.reqQryTradingAccount(
            {"BrokerID": self.brokerid, "InvestorID": self.userid},
            self.next_reqid(),
        )
        self.log(f"reqQryTradingAccount ret={account_ret}")
        time.sleep(1.1)
        position_ret = self.reqQryInvestorPosition(
            {"BrokerID": self.brokerid, "InvestorID": self.userid},
            self.next_reqid(),
        )
        self.log(f"reqQryInvestorPosition ret={position_ret}")

    def onRspQryTradingAccount(self, data: dict, error: dict, reqid: int, last: bool) -> None:
        if data and data.get("AccountID"):
            row = {field: _clean_value(data.get(field, "")) for field in RAW_ACCOUNT_FIELDS}
            row.update(
                {
                    "accountid": data.get("AccountID", ""),
                    "balance": data.get("Balance", ""),
                    "available": data.get("Available", ""),
                    "curr_margin": data.get("CurrMargin", ""),
                    "margin": data.get("CurrMargin", ""),
                    "frozen_margin": data.get("FrozenMargin", ""),
                    "frozen_cash": data.get("FrozenCash", ""),
                    "frozen_commission": data.get("FrozenCommission", ""),
                    "reqid": reqid,
                    "last": bool(last),
                    "snapshot_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            self.account_rows.append(row)
            self.log(
                "onRspQryTradingAccount account_received "
                f"balance={row['balance']} available={row['available']} curr_margin={row['curr_margin']}"
            )
        if error and error.get("ErrorID"):
            self.log(f"onRspQryTradingAccount error {_error_text(error)}")

    def onRspQryInvestorPosition(self, data: dict, error: dict, reqid: int, last: bool) -> None:
        if data and data.get("InstrumentID"):
            self.position_rows.append(
                {
                    "instrument": data.get("InstrumentID", ""),
                    "direction": data.get("PosiDirection", ""),
                    "position": data.get("Position", ""),
                    "today_position": data.get("TodayPosition", ""),
                    "yd_position": data.get("YdPosition", ""),
                    "use_margin": data.get("UseMargin", ""),
                    "position_cost": data.get("PositionCost", ""),
                    "position_profit": data.get("PositionProfit", ""),
                    "reqid": reqid,
                    "last": bool(last),
                    "snapshot_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        if error and error.get("ErrorID"):
            self.log(f"onRspQryInvestorPosition error {_error_text(error)}")
        if last:
            self.log("onRspQryInvestorPosition last=True")
            self.done = True

    def onRspError(self, error: dict, reqid: int, last: bool) -> None:
        self.log(f"onRspError reqid={reqid} last={last} {_error_text(error)}")


def run_probe(connect: bool, wait_seconds: int) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "connect_requested": bool(connect),
        "wait_seconds": int(wait_seconds),
        "env_status": _env_status(),
        "missing_required_env": _required_env_missing(),
        "tdapi_import_available": not bool(TDAPI_IMPORT_ERROR),
        "tdapi_import_error": TDAPI_IMPORT_ERROR,
        "raw_account_fields": RAW_ACCOUNT_FIELDS,
        "real_order_enabled": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "status": "dry_run_not_connected",
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "accounts": str(ACCOUNT_PATH),
            "positions": str(POSITION_PATH),
            "logs": str(LOG_PATH),
        },
    }
    rows = {"accounts": [], "positions": [], "logs": []}
    if connect:
        if TDAPI_IMPORT_ERROR:
            summary["status"] = "blocked_ctp_tdapi_import_error"
            summary["tdapi_import_error"] = TDAPI_IMPORT_ERROR
            _write_df(ACCOUNT_PATH, rows["accounts"])
            _write_df(POSITION_PATH, rows["positions"])
            _write_df(LOG_PATH, rows["logs"])
            SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            return summary
        missing = _required_env_missing()
        if missing:
            summary["status"] = "blocked_missing_env"
        else:
            probe = RawAccountMarginProbe(wait_seconds=wait_seconds, hard_exit_on_finish=True)
            probe.start_probe()
            rows = {
                "accounts": probe.account_rows,
                "positions": probe.position_rows,
                "logs": probe.log_rows,
            }
            summary.update(
                {
                    "status": "readonly_account_margin_received" if probe.account_rows else "readonly_no_account_margin_received",
                    "front_connected": probe.front_connected,
                    "auth_ok": probe.auth_ok,
                    "login_ok": probe.login_ok,
                    "settlement_ok": probe.settlement_ok,
                    "account_rows": len(probe.account_rows),
                    "position_rows": len(probe.position_rows),
                    "explicit_margin_rows": sum(1 for row in probe.account_rows if row.get("curr_margin") not in {"", None}),
                }
            )
    summary.setdefault("account_rows", len(rows["accounts"]))
    summary.setdefault("position_rows", len(rows["positions"]))
    summary.setdefault("explicit_margin_rows", sum(1 for row in rows["accounts"] if row.get("curr_margin") not in {"", None}))
    _write_df(ACCOUNT_PATH, rows["accounts"])
    _write_df(POSITION_PATH, rows["positions"])
    _write_df(LOG_PATH, rows["logs"])
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only raw CTP account margin probe. No orders are sent.")
    parser.add_argument("--connect", action="store_true", help="Actually attempt CTP TD connection and account query.")
    parser.add_argument("--wait-seconds", type=int, default=35)
    args = parser.parse_args()
    summary = run_probe(bool(args.connect), int(args.wait_seconds))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"summary json: {SUMMARY_PATH}")
    if not args.connect:
        return 0
    if summary.get("status") == "readonly_account_margin_received":
        exit_code = 0
    elif summary.get("front_connected"):
        exit_code = 3
    else:
        exit_code = 4

    # The Mac CTP Python wrapper can segfault during interpreter teardown after
    # a TD API init attempt. Outputs are already persisted above; for connect
    # runs, use a hard process exit so failed read-only probes return their
    # intended status code instead of masking it with exit code 139.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
