#!/usr/bin/env python3
"""Stage273: isolated CTP TD-only probe for broker CP Mac SDK.

This probe deliberately does not create a vn.py MainEngine/Gateway and does not
touch the market-data API.  It is read-only: authenticate, login, confirm
settlement, then query account and positions if login succeeds.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from vnpy_ctp.api import TdApi


def env_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required env: {name}")
    return value


def mask_state(name: str, value: str) -> str:
    if name in {"CTP_USERID", "CTP_PASSWORD", "CTP_APPID", "CTP_AUTH_CODE"}:
        return f"set(len={len(value)})"
    return value


class TdOnlyProbe(TdApi):
    def __init__(self, *, wait_seconds: int) -> None:
        super().__init__()
        self.wait_seconds = wait_seconds
        self.reqid = 0
        self.done = False
        self.front_connected = False
        self.auth_ok = False
        self.login_ok = False
        self.settlement_ok = False
        self.account_count = 0
        self.position_count = 0
        self.start = time.time()

        self.userid = env_required("CTP_USERID")
        self.password = env_required("CTP_PASSWORD")
        self.brokerid = env_required("CTP_BROKERID")
        self.td_address = env_required("CTP_TD_ADDRESS")
        self.appid = env_required("CTP_APPID")
        self.auth_code = env_required("CTP_AUTH_CODE")
        self.product_info = os.environ.get("CTP_PRODUCT_INFO", "")

    def next_reqid(self) -> int:
        self.reqid += 1
        return self.reqid

    def log(self, msg: str) -> None:
        elapsed = time.time() - self.start
        print(f"[{elapsed:7.2f}s] {msg}", flush=True)

    def error_text(self, error: dict) -> str:
        if not error:
            return "ErrorID=0 ErrorMsg="
        return f"ErrorID={error.get('ErrorID')} ErrorMsg={error.get('ErrorMsg')}"

    def start_probe(self) -> None:
        flow_dir = Path("/private/tmp/stage273_ctp_td_only_flow")
        td_flow_dir = flow_dir / "Td"
        td_flow_dir.mkdir(parents=True, exist_ok=True)
        flow_path = (str(td_flow_dir) + os.sep).encode("GBK", errors="ignore")

        self.log("TD-only probe starting")
        for key, value in [
            ("CTP_BROKERID", self.brokerid),
            ("CTP_TD_ADDRESS", self.td_address),
            ("CTP_USERID", self.userid),
            ("CTP_PASSWORD", self.password),
            ("CTP_APPID", self.appid),
            ("CTP_AUTH_CODE", self.auth_code),
        ]:
            self.log(f"{key}={mask_state(key, value)}")

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
            f"front_connected={self.front_connected} "
            f"auth_ok={self.auth_ok} "
            f"login_ok={self.login_ok} "
            f"settlement_ok={self.settlement_ok} "
            f"account_count={self.account_count} "
            f"position_count={self.position_count}"
        )

    def onFrontConnected(self) -> None:
        self.front_connected = True
        self.log("onFrontConnected: trading front connected")
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
        self.log(f"onRspAuthenticate reqid={reqid} last={last} {self.error_text(error)}")
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
        self.log(f"onRspUserLogin reqid={reqid} last={last} {self.error_text(error)}")
        if error and error.get("ErrorID"):
            self.done = True
            return
        self.login_ok = True
        req = {
            "BrokerID": self.brokerid,
            "InvestorID": self.userid,
        }
        ret = self.reqSettlementInfoConfirm(req, self.next_reqid())
        self.log(f"reqSettlementInfoConfirm ret={ret}")

    def onRspSettlementInfoConfirm(self, data: dict, error: dict, reqid: int, last: bool) -> None:
        self.log(f"onRspSettlementInfoConfirm reqid={reqid} last={last} {self.error_text(error)}")
        if error and error.get("ErrorID"):
            self.done = True
            return
        self.settlement_ok = True
        ret = self.reqQryTradingAccount({"BrokerID": self.brokerid, "InvestorID": self.userid}, self.next_reqid())
        self.log(f"reqQryTradingAccount ret={ret}")
        time.sleep(1.1)
        ret = self.reqQryInvestorPosition({"BrokerID": self.brokerid, "InvestorID": self.userid}, self.next_reqid())
        self.log(f"reqQryInvestorPosition ret={ret}")

    def onRspQryTradingAccount(self, data: dict, error: dict, reqid: int, last: bool) -> None:
        if data and data.get("AccountID"):
            self.account_count += 1
            balance = data.get("Balance")
            available = data.get("Available")
            self.log(f"onRspQryTradingAccount account_received balance={balance} available={available}")
        if error and error.get("ErrorID"):
            self.log(f"onRspQryTradingAccount error {self.error_text(error)}")

    def onRspQryInvestorPosition(self, data: dict, error: dict, reqid: int, last: bool) -> None:
        if data and data.get("InstrumentID"):
            self.position_count += 1
            instrument = data.get("InstrumentID")
            direction = data.get("PosiDirection")
            volume = data.get("Position")
            self.log(f"onRspQryInvestorPosition instrument={instrument} direction={direction} volume={volume}")
        if error and error.get("ErrorID"):
            self.log(f"onRspQryInvestorPosition error {self.error_text(error)}")
        if last:
            self.log("onRspQryInvestorPosition last=True")
            self.done = True

    def onRspError(self, error: dict, reqid: int, last: bool) -> None:
        self.log(f"onRspError reqid={reqid} last={last} {self.error_text(error)}")


def main() -> int:
    wait_seconds = int(os.environ.get("CTP_TD_ONLY_WAIT_SECONDS", "35"))
    probe = TdOnlyProbe(wait_seconds=wait_seconds)
    probe.start_probe()

    if probe.login_ok and probe.settlement_ok:
        return 0
    if probe.front_connected:
        return 3
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
