#!/usr/bin/env python3
"""Stage656: parse native CP TD-only account margin probe logs.

The native C++ probe is the working path for the broker CP front. This parser
converts its sanitized console log into the same account-margin evidence shape
used by the Stage654 live gate. It does not connect CTP or send orders.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage656_native_cp_account_margin_probe_v1"
OUTPUT_PREFIX = "qmt_roll_stage656_native_cp_account_margin_probe"

RAW_LOG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_raw_{MODEL_TAG}.log"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
ACCOUNT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_accounts_{MODEL_TAG}.csv"
POSITION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
LOG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_logs_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

SUMMARY_RE = re.compile(
    r"summary front_connected=(?P<front_connected>true|false) "
    r"auth_ok=(?P<auth_ok>true|false) "
    r"login_ok=(?P<login_ok>true|false) "
    r"settlement_ok=(?P<settlement_ok>true|false) "
    r"account_count=(?P<account_count>\d+) "
    r"position_count=(?P<position_count>\d+)"
)

ACCOUNT_RE = re.compile(
    r"OnRspQryTradingAccount .*?"
    r"Balance=(?P<balance>[-0-9.]+) "
    r"Available=(?P<available>[-0-9.]+) "
    r"CurrMargin=(?P<curr_margin>[-0-9.]+) "
    r"FrozenMargin=(?P<frozen_margin>[-0-9.]+) "
    r"FrozenCash=(?P<frozen_cash>[-0-9.]+) "
    r"FrozenCommission=(?P<frozen_commission>[-0-9.]+)"
)

POSITION_RE = re.compile(
    r"OnRspQryInvestorPosition .*?"
    r"InstrumentID=(?P<instrument>\S+) "
    r"PosiDirection=(?P<posi_direction>\S+) "
    r"Position=(?P<position>[-0-9.]+)"
)

LOGIN_RE = re.compile(
    r"OnRspUserLogin .*?"
    r"FrontID=(?P<front_id>[-0-9]+) "
    r"SessionID=(?P<session_id>[-0-9]+) "
    r"TradingDay=(?P<trading_day>\S+) "
    r"LoginTime=(?P<login_time>\S+)"
)

SYSTEM_RE = re.compile(r"CTP_SYSTEM_INFO_SOURCE=(?P<source>\S+)")
SYSTEM_LEN_RE = re.compile(r"CTP_CLIENT_SYSTEM_INFO=set\(len=(?P<len>\d+)\)")


def _bool_text(value: str) -> bool:
    return value == "true"


def _float_text(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _write_df(path: Path, rows: list[dict[str, Any]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def parse_log(raw_log: Path, native_exit_code: int) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = raw_log.read_text(encoding="utf-8", errors="ignore") if raw_log.exists() else ""
    lines = text.splitlines()

    log_rows = [{"line_no": index + 1, "message": line} for index, line in enumerate(lines)]
    summary_match = None
    login_match = None
    system_source = ""
    system_len = 0
    accounts: list[dict[str, Any]] = []
    positions: list[dict[str, Any]] = []

    for line in lines:
        if summary_match is None:
            summary_match = SUMMARY_RE.search(line)
        if login_match is None:
            login_match = LOGIN_RE.search(line)
        if not system_source:
            match = SYSTEM_RE.search(line)
            if match:
                system_source = match.group("source")
        if not system_len:
            match = SYSTEM_LEN_RE.search(line)
            if match:
                system_len = int(match.group("len"))

        account_match = ACCOUNT_RE.search(line)
        if account_match:
            row = account_match.groupdict()
            balance = _float_text(row["balance"])
            available = _float_text(row["available"])
            curr_margin = _float_text(row["curr_margin"])
            row.update(
                {
                    "snapshot_at": generated_at,
                    "source": "native_cpp_stage278_cp_sdk",
                    "accountid": "",
                    "Balance": balance,
                    "Available": available,
                    "CurrMargin": curr_margin,
                    "balance": balance,
                    "available": available,
                    "curr_margin": curr_margin,
                    "margin": curr_margin,
                    "frozen_margin": _float_text(row["frozen_margin"]),
                    "frozen_cash": _float_text(row["frozen_cash"]),
                    "frozen_commission": _float_text(row["frozen_commission"]),
                }
            )
            accounts.append(row)

        position_match = POSITION_RE.search(line)
        if position_match:
            row = position_match.groupdict()
            row.update(
                {
                    "snapshot_at": generated_at,
                    "source": "native_cpp_stage278_cp_sdk",
                    "symbol": row["instrument"],
                    "position": _float_text(row["position"]),
                }
            )
            positions.append(row)

    summary_fields: dict[str, Any] = {}
    if summary_match:
        summary_fields = summary_match.groupdict()

    login_fields: dict[str, Any] = login_match.groupdict() if login_match else {}
    status = "readonly_native_cp_account_margin_received" if accounts else "readonly_native_cp_no_account_margin_received"
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": generated_at,
        "native_exit_code": native_exit_code,
        "connect_requested": True,
        "front_connected": _bool_text(summary_fields.get("front_connected", "false")),
        "auth_ok": _bool_text(summary_fields.get("auth_ok", "false")),
        "login_ok": _bool_text(summary_fields.get("login_ok", "false")),
        "settlement_ok": _bool_text(summary_fields.get("settlement_ok", "false")),
        "account_rows": len(accounts),
        "position_rows": len(positions),
        "explicit_margin_rows": sum(1 for row in accounts if row.get("curr_margin") not in {"", None}),
        "status": status,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "system_info_source": system_source,
        "system_info_len": system_len,
        "session": login_fields,
        "outputs": {
            "raw_log": str(raw_log),
            "summary": str(SUMMARY_PATH),
            "accounts": str(ACCOUNT_PATH),
            "positions": str(POSITION_PATH),
            "logs": str(LOG_PATH),
            "report": str(REPORT_PATH),
        },
    }

    _write_df(ACCOUNT_PATH, accounts)
    _write_df(POSITION_PATH, positions)
    _write_df(LOG_PATH, log_rows)
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_report(summary), encoding="utf-8")
    return summary


def build_report(summary: dict[str, Any]) -> str:
    return f"""# Stage656 Native CP Account Margin Probe

- generated_at: `{summary['generated_at']}`
- status: `{summary['status']}`
- native_exit_code: `{summary['native_exit_code']}`
- connect_requested: `{summary['connect_requested']}`
- front_connected: `{summary['front_connected']}`
- auth_ok: `{summary['auth_ok']}`
- login_ok: `{summary['login_ok']}`
- settlement_ok: `{summary['settlement_ok']}`
- account_rows: `{summary['account_rows']}`
- position_rows: `{summary['position_rows']}`
- explicit_margin_rows: `{summary['explicit_margin_rows']}`
- system_info_source: `{summary['system_info_source']}`
- system_info_len: `{summary['system_info_len']}`
- send_order_api_called_count: `0`
- cancel_order_api_called_count: `0`

## Judgement

The native CP SDK route is the usable read-only path for the broker CP front.
It captures raw CTP `CurrMargin` directly from `OnRspQryTradingAccount`, so it
can satisfy the Stage654 explicit-margin account snapshot requirement. It does
not prove order execution quality or `vt_orderid` mapping.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse Stage656 native CP account margin probe log.")
    parser.add_argument("--raw-log", type=Path, default=RAW_LOG_PATH)
    parser.add_argument("--native-exit-code", type=int, default=0)
    args = parser.parse_args()
    summary = parse_log(args.raw_log, args.native_exit_code)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"summary json: {SUMMARY_PATH}")
    return 0 if summary["account_rows"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
