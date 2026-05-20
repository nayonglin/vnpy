#!/usr/bin/env python3
"""Stage274: isolated CTP MD-only subscription probe for broker CP Mac SDK.

Read-only probe: connect market-data front, login, subscribe symbols, and count
depth-market-data ticks.  It never creates a trading API and never sends orders.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from vnpy_ctp.api import MdApi


def env_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required env: {name}")
    return value


def mask_state(name: str, value: str) -> str:
    if name in {"CTP_USERID", "CTP_PASSWORD"}:
        return f"set(len={len(value)})"
    return value


class MdSubscribeProbe(MdApi):
    def __init__(self, *, wait_seconds: int, symbols: list[str]) -> None:
        super().__init__()
        self.wait_seconds = wait_seconds
        self.symbols = symbols
        self.reqid = 0
        self.start = time.time()

        self.front_connected = False
        self.login_ok = False
        self.subscription_responses: list[dict] = []
        self.tick_count = 0
        self.latest_ticks: dict[str, dict] = {}

        self.userid = env_required("CTP_USERID")
        self.password = env_required("CTP_PASSWORD")
        self.brokerid = env_required("CTP_BROKERID")
        self.md_address = env_required("CTP_MD_ADDRESS")

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
        flow_dir = Path("/private/tmp/stage274_ctp_md_subscribe_flow/Md")
        flow_dir.mkdir(parents=True, exist_ok=True)
        flow_path = (str(flow_dir) + os.sep).encode("GBK", errors="ignore")

        self.log("MD-only subscribe probe starting")
        for key, value in [
            ("CTP_BROKERID", self.brokerid),
            ("CTP_MD_ADDRESS", self.md_address),
            ("CTP_USERID", self.userid),
            ("CTP_PASSWORD", self.password),
        ]:
            self.log(f"{key}={mask_state(key, value)}")
        self.log(f"symbols={','.join(self.symbols)}")

        self.createFtdcMdApi(flow_path)
        self.registerFront(self.md_address)
        self.init()

        deadline = time.time() + self.wait_seconds
        while time.time() < deadline:
            time.sleep(0.2)

        self.log(
            "summary "
            f"front_connected={self.front_connected} "
            f"login_ok={self.login_ok} "
            f"subscription_response_count={len(self.subscription_responses)} "
            f"tick_count={self.tick_count}"
        )
        for symbol in self.symbols:
            tick = self.latest_ticks.get(symbol)
            if tick:
                self.log(
                    "latest_tick "
                    f"symbol={symbol} "
                    f"trading_day={tick.get('TradingDay')} "
                    f"action_day={tick.get('ActionDay')} "
                    f"update_time={tick.get('UpdateTime')}.{tick.get('UpdateMillisec')} "
                    f"last_price={tick.get('LastPrice')} "
                    f"bid1={tick.get('BidPrice1')} "
                    f"ask1={tick.get('AskPrice1')} "
                    f"volume={tick.get('Volume')} "
                    f"open_interest={tick.get('OpenInterest')}"
                )
            else:
                self.log(f"latest_tick symbol={symbol} none")

        try:
            self.exit()
        except Exception as exc:
            self.log(f"exit exception ignored: {exc!r}")

    def onFrontConnected(self) -> None:
        self.front_connected = True
        self.log("onFrontConnected: market-data front connected")
        req = {
            "UserID": self.userid,
            "Password": self.password,
            "BrokerID": self.brokerid,
        }
        ret = self.reqUserLogin(req, self.next_reqid())
        self.log(f"reqUserLogin ret={ret}")

    def onFrontDisconnected(self, reason: int) -> None:
        self.log(f"onFrontDisconnected reason={reason}")

    def onRspUserLogin(self, data: dict, error: dict, reqid: int, last: bool) -> None:
        self.log(f"onRspUserLogin reqid={reqid} last={last} {self.error_text(error)}")
        if error and error.get("ErrorID"):
            return
        self.login_ok = True
        for symbol in self.symbols:
            ret = self.subscribeMarketData(symbol)
            self.log(f"subscribeMarketData symbol={symbol} ret={ret}")

    def onRspSubMarketData(self, data: dict, error: dict, reqid: int, last: bool) -> None:
        row = {
            "InstrumentID": data.get("InstrumentID") if data else "",
            "ErrorID": error.get("ErrorID") if error else 0,
            "ErrorMsg": error.get("ErrorMsg") if error else "",
            "last": last,
        }
        self.subscription_responses.append(row)
        self.log(
            "onRspSubMarketData "
            f"instrument={row['InstrumentID']} "
            f"last={last} "
            f"ErrorID={row['ErrorID']} "
            f"ErrorMsg={row['ErrorMsg']}"
        )

    def onRspError(self, error: dict, reqid: int, last: bool) -> None:
        self.log(f"onRspError reqid={reqid} last={last} {self.error_text(error)}")

    def onRtnDepthMarketData(self, data: dict) -> None:
        symbol = data.get("InstrumentID", "")
        self.tick_count += 1
        self.latest_ticks[symbol] = dict(data)
        if self.tick_count <= 5:
            self.log(
                "onRtnDepthMarketData "
                f"symbol={symbol} "
                f"trading_day={data.get('TradingDay')} "
                f"action_day={data.get('ActionDay')} "
                f"update_time={data.get('UpdateTime')}.{data.get('UpdateMillisec')} "
                f"last_price={data.get('LastPrice')} "
                f"bid1={data.get('BidPrice1')} "
                f"ask1={data.get('AskPrice1')}"
            )


def main() -> int:
    wait_seconds = int(os.environ.get("CTP_MD_SUBSCRIBE_WAIT_SECONDS", "45"))
    raw_symbols = os.environ.get("CTP_MD_SUBSCRIBE_SYMBOLS", "MA609,ru2609")
    symbols = [item.strip() for item in raw_symbols.split(",") if item.strip()]
    if not symbols:
        raise SystemExit("No symbols configured in CTP_MD_SUBSCRIBE_SYMBOLS")

    probe = MdSubscribeProbe(wait_seconds=wait_seconds, symbols=symbols)
    probe.start_probe()

    if probe.login_ok:
        return 0
    if probe.front_connected:
        return 3
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
